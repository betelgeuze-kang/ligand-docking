"""Corrected angular numerics plus existing improper and fixed-Born terms.

The distance constraints are observations/projections, not hidden energy terms.
Only explicit, single-model, nonperiodic CPU binary64 inputs are admitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

import torch

from betelgeuze_engine_v2.contracts import QuantityDescriptor
from betelgeuze_engine_v2.geometry import CompactNeighborList
from betelgeuze_engine_v2.molecular import AllAtomSystem, canonical_system_sha256
from betelgeuze_engine_v2.physics.composition import EnergyTermResult
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    REFERENCE_FORCEFIELD_V2_SCIENTIFIC_BLOCKERS, ReferenceForceFieldV2Parameters,
    _constraint_observations, _out_of_plane_angle, _validate_extension_topology,
)
from betelgeuze_engine_v2.physics.reference_solvation import (
    FixedBornPolarSolvationParameters, evaluate_fixed_born_polar_solvation,
)
from betelgeuze_product.cpu_refinement.reference_forcefield_v1_1 import (
    evaluate_reference_force_field,
)
from .provenance import ResearchError, digest

EVALUATOR_ID = "cpu_corrected_extended_reference/1.2.0"


@dataclass(frozen=True)
class ExtendedEvaluation:
    term: EnergyTermResult
    component_energies: Mapping[str, torch.Tensor]
    constraint_observations: tuple
    evaluator_fingerprint_sha256: str
    scientific_blockers: tuple[str, ...]

    @property
    def constraints_satisfied(self) -> bool:
        return all(row.satisfied for row in self.constraint_observations)


@dataclass(frozen=True)
class ExtendedEvaluator:
    parameters: ReferenceForceFieldV2Parameters
    solvation: FixedBornPolarSolvationParameters | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.parameters, ReferenceForceFieldV2Parameters):
            raise ResearchError("explicit extension parameters required")
        if self.solvation is not None and not isinstance(self.solvation, FixedBornPolarSolvationParameters):
            raise ResearchError("explicit fixed-Born parameters required")
        if self.solvation is not None and (
            self.solvation.charge_parameter_fingerprint_sha256 != self.parameters.fingerprint_sha256
            or self.solvation.topology_sha256 != self.parameters.topology_sha256
        ):
            raise ResearchError("solvation charge/parameter identity mismatch")

    def identity(self) -> dict[str, object]:
        return {"evaluator_id": EVALUATOR_ID,
                "parameter_fingerprint_sha256": self.parameters.fingerprint_sha256,
                "solvation_fingerprint_sha256": (None if self.solvation is None
                                                  else self.solvation.fingerprint_sha256)}

    @property
    def fingerprint_sha256(self) -> str:
        return digest(self.identity())

    def evaluate(self, system: AllAtomSystem, neighbors: CompactNeighborList) -> ExtendedEvaluation:
        if (system.model_count != 1 or not 1 <= system.atom_count <= 256
                or system.cell is not None or system.coordinates.device.type != "cpu"
                or system.coordinates.dtype != torch.float64):
            raise ResearchError("single-model nonperiodic CPU binary64 system of 1..256 atoms required")
        _validate_extension_topology(system, self.parameters)
        base = evaluate_reference_force_field(system, neighbors, self.parameters.base_parameters)
        coordinates = system.coordinates.detach().clone().requires_grad_(True)
        improper = coordinates.sum(dim=(1, 2)) * 0.0
        for row in self.parameters.impropers:
            angle = _out_of_plane_angle(coordinates, system, row)
            improper = improper + .5 * row.force_constant_kcal_per_mol_radian2 * (
                angle - row.equilibrium_radians).pow(2)
        improper_force = -torch.autograd.grad(improper.sum(), coordinates)[0]
        energy = base.term.energy + improper.detach()
        forces = base.term.forces + improper_force.detach()
        components = {**base.component_energies,
                      "harmonic_out_of_plane_improper": improper.detach()}
        blockers = (*base.scientific_blockers, *REFERENCE_FORCEFIELD_V2_SCIENTIFIC_BLOCKERS)
        solvent_provenance = None
        if self.solvation is not None:
            solvent = evaluate_fixed_born_polar_solvation(system, self.parameters, self.solvation)
            energy = energy + solvent.term.energy
            forces = forces + solvent.term.forces
            components.update(solvent.component_energies)
            blockers += solvent.scientific_blockers
            solvent_provenance = solvent.term.provenance_sha256
        if not bool(torch.isfinite(energy).all()) or not bool(torch.isfinite(forces).all()):
            raise FloatingPointError("nonfinite extended energy or force")
        identity = self.fingerprint_sha256
        term = EnergyTermResult(
            name=EVALUATOR_ID, energy=energy, forces=forces,
            energy_descriptor=QuantityDescriptor(
                name="corrected_extended_energy", unit="kcal/mol",
                semantics="corrected_base_plus_improper_plus_optional_fixed_radius_polar_gb",
                physical_quantity=True, calibrated=False, reference_method=None),
            force_descriptor=QuantityDescriptor(
                name="corrected_extended_force", unit="kcal/mol/angstrom",
                semantics="negative_coordinate_gradient_of_corrected_extended_energy",
                physical_quantity=True, calibrated=False, reference_method=None),
            validated_for_composition=False,
            provenance_sha256=digest({"evaluator": identity,
                "system": canonical_system_sha256(system), "base": base.term.provenance_sha256,
                "solvation": solvent_provenance}),
        )
        return ExtendedEvaluation(term, MappingProxyType(components),
            _constraint_observations(system.coordinates, system, self.parameters.constraints),
            identity, tuple(dict.fromkeys(blockers)))


def make_evaluator(parameters, solvation=None, fixed_environment=None):
    """Select an explicit objective; default internal behavior is unchanged."""
    base = ExtendedEvaluator(parameters, solvation)
    if fixed_environment is None:
        return base
    from .fixed_receptor import FixedReceptorEvaluator
    return FixedReceptorEvaluator(base, fixed_environment)
