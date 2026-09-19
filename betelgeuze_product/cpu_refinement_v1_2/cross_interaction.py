"""Explicit noncovalent fixed-receptor LJ + screened Coulomb objective.

All receptor atoms are retained. Cartesian pairs are visited once in bounded
blocks; no periodic images, receptor flexibility, long-range correction or
parameter inference. Both terms use the same differentiable quintic switch.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
from types import MappingProxyType

import torch

from betelgeuze_engine_v2.contracts import QuantityDescriptor
from betelgeuze_engine_v2.molecular import canonical_system_sha256, canonical_topology_sha256, require_valid_all_atom_system
from betelgeuze_engine_v2.physics.reference_parameters import AtomNonbondedParameter, COULOMB_KCAL_ANGSTROM_PER_MOL_E2
from betelgeuze_product.cpu_refinement.reference_forcefield_v1_1 import ReferencePhysicsApplicabilityError
from betelgeuze_engine_v2.physics.reference_forcefield import _switch
from .evaluation import ExtendedEvaluator, ExtendedEvaluation
from .provenance import ResearchError, canonical, digest, exact_fields, finite, integer, require_digest

CROSS_SCHEMA = "fixed_receptor_nonbonded_parameters/1.0.0"
OBJECTIVE_ID = "corrected_ligand_plus_fixed_receptor_lj_screened_coulomb/1.0.0"


def _state(system, maximum):
    require_valid_all_atom_system(system)
    if (system.model_count != 1 or system.cell is not None or system.coordinate_unit != "angstrom"
            or not 1 <= system.atom_count <= maximum or system.coordinates.dtype != torch.float64
            or system.coordinates.device.type != "cpu" or not bool(torch.isfinite(system.coordinates).all())):
        raise ResearchError("bounded nonperiodic single-model CPU float64 angstrom state required")


@dataclass(frozen=True)
class CrossParameters:
    receptor_topology_sha256: str
    ligand_parameters_sha256: str
    parameter_source_sha256: str
    coordinate_frame_id: str
    receptor_atoms: tuple[AtomNonbondedParameter, ...]
    cutoff_angstrom: float
    switch_start_angstrom: float
    minimum_distance_angstrom: float
    dielectric: float
    screening_kappa_per_angstrom: float
    receptor_block_size: int
    excluded_pairs: tuple[tuple[int, int], ...]
    schema_id: str = CROSS_SCHEMA
    pair_policy: str = "all_nonperiodic_cross_pairs_except_explicit_exclusions"
    mixing_rule: str = "lorentz_berthelot"

    def __post_init__(self):
        for value in (self.receptor_topology_sha256, self.ligand_parameters_sha256, self.parameter_source_sha256):
            require_digest(value)
        if self.schema_id != CROSS_SCHEMA or self.pair_policy != "all_nonperiodic_cross_pairs_except_explicit_exclusions" or self.mixing_rule != "lorentz_berthelot":
            raise ResearchError("unsupported cross-interaction semantics")
        if type(self.coordinate_frame_id) is not str or not self.coordinate_frame_id.strip():
            raise ResearchError("explicit common coordinate frame required")
        if type(self.receptor_atoms) is not tuple or not 1 <= len(self.receptor_atoms) <= 8192:
            raise ResearchError("complete bounded receptor atom parameters required")
        for index, row in enumerate(self.receptor_atoms):
            if type(row) is not AtomNonbondedParameter or row.atom_index != index:
                raise ResearchError("canonical complete receptor atom ordering required")
        for name in ("cutoff_angstrom", "switch_start_angstrom", "minimum_distance_angstrom", "dielectric", "screening_kappa_per_angstrom"):
            finite(getattr(self, name), nonnegative=True)
        if not (0 < self.minimum_distance_angstrom < self.switch_start_angstrom < self.cutoff_angstrom <= 100
                and self.dielectric > 0):
            raise ResearchError("invalid cross-distance/dielectric bounds")
        integer(self.receptor_block_size, 1, 256)
        if type(self.excluded_pairs) is not tuple or len(self.excluded_pairs) > 65536:
            raise ResearchError("bounded explicit cross exclusions required")
        for pair in self.excluded_pairs:
            if type(pair) is not tuple or len(pair) != 2:
                raise ResearchError("cross exclusion is (ligand index, receptor index)")
            integer(pair[0], 0, 255)
            integer(pair[1], 0, len(self.receptor_atoms) - 1)
        if tuple(sorted(set(self.excluded_pairs))) != self.excluded_pairs:
            raise ResearchError("cross exclusions must be unique and ordered")

    def to_dict(self):
        return {**vars(self), "receptor_atoms": [row.to_dict() for row in self.receptor_atoms],
                "excluded_pairs": [list(pair) for pair in self.excluded_pairs]}

    @classmethod
    def from_dict(cls, document):
        exact_fields(document, {row.name for row in fields(cls)})
        values = dict(document)
        for row in values["receptor_atoms"]:
            exact_fields(row, {f.name for f in fields(AtomNonbondedParameter)})
            integer(row["atom_index"], 0, 8191)
        values["receptor_atoms"] = tuple(AtomNonbondedParameter(**row) for row in values["receptor_atoms"])
        values["excluded_pairs"] = tuple(tuple(pair) for pair in values["excluded_pairs"])
        result = cls(**values)
        if canonical(result.to_dict()) != canonical(document):
            raise ResearchError("cross parameter normalization is not admission")
        return result

    @property
    def fingerprint_sha256(self):
        return digest(self.to_dict())


class FixedReceptorEvaluator:
    """Same evaluation interface as ExtendedEvaluator; distinct bound identity."""

    def __init__(self, receptor, parameters, cross: CrossParameters, *, coordinate_frame_id: str, solvation=None):
        _state(receptor, 8192)
        if type(cross) is not CrossParameters:
            raise ResearchError("explicit cross parameters required")
        if (canonical_topology_sha256(receptor) != cross.receptor_topology_sha256
                or len(cross.receptor_atoms) != receptor.atom_count
                or parameters.base_parameters.fingerprint_sha256 != cross.ligand_parameters_sha256
                or coordinate_frame_id != cross.coordinate_frame_id):
            raise ResearchError("receptor, frame or ligand parameter binding mismatch")
        for atom, row in zip(receptor.atoms, cross.receptor_atoms, strict=True):
            if atom.partial_charge_e is None or float(atom.partial_charge_e) != row.charge_e:
                raise ResearchError("receptor charges differ from explicit state")
        self.internal = ExtendedEvaluator(parameters, solvation)
        self.parameters, self.cross = parameters, cross
        self.receptor = receptor
        self._receptor_sha256 = canonical_system_sha256(receptor)
        self._identity = {"evaluator_id": OBJECTIVE_ID, "internal": self.internal.identity(),
                          "receptor_system_sha256": self._receptor_sha256,
                          "cross_parameters_sha256": cross.fingerprint_sha256,
                          "coordinate_frame_id": coordinate_frame_id}

    def identity(self):
        try:
            current_receptor = canonical_system_sha256(self.receptor)
        except RuntimeError as exc:
            raise ResearchError("fixed receptor integrity changed") from exc
        if (current_receptor != self._receptor_sha256
                or self.cross.fingerprint_sha256 != self._identity["cross_parameters_sha256"]
                or self.internal.identity() != self._identity["internal"]):
            raise ResearchError("fixed environment or parameters changed")
        return dict(self._identity)

    def validate_ligand(self, ligand):
        self.identity()
        _state(ligand, 256)
        base = self.parameters.base_parameters
        if canonical_topology_sha256(ligand) != base.topology_sha256:
            raise ResearchError("cross ligand topology mismatch")
        if any(i >= ligand.atom_count for i, _ in self.cross.excluded_pairs):
            raise ResearchError("cross exclusion ligand index out of range")
        atom_map = base.atom_parameter_map
        if set(atom_map) != set(range(ligand.atom_count)):
            raise ResearchError("complete ligand nonbonded table required")
        for atom in ligand.atoms:
            if atom.partial_charge_e is None or float(atom.partial_charge_e) != atom_map[atom.index].charge_e:
                raise ResearchError("ligand charges differ from explicit state")
        return atom_map

    def cross_terms(self, ligand):
        atom_map = self.validate_ligand(ligand)
        left = torch.tensor([[atom_map[i].sigma_angstrom, atom_map[i].epsilon_kcal_per_mol, atom_map[i].charge_e]
                             for i in range(ligand.atom_count)], dtype=torch.float64)
        cross = self.cross
        force = torch.zeros_like(ligand.coordinates)
        totals = torch.zeros(2, dtype=torch.float64)
        evaluated_pairs = 0
        # A fresh block graph is differentiated and released before the next block.
        with torch.enable_grad():
            for start in range(0, self.receptor.atom_count, cross.receptor_block_size):
                end = min(start + cross.receptor_block_size, self.receptor.atom_count)
                x = ligand.coordinates.detach().clone().requires_grad_(True)
                fixed = self.receptor.coordinates[0, start:end].detach()
                distance = torch.linalg.vector_norm(x[0, :, None, :] - fixed[None, :, :], dim=-1)
                allowed = torch.ones_like(distance, dtype=torch.bool)
                for i, j in cross.excluded_pairs:
                    if start <= j < end:
                        allowed[i, j - start] = False
                if bool(((distance < cross.minimum_distance_angstrom) & allowed).any()):
                    raise ReferencePhysicsApplicabilityError("cross pair below declared minimum distance")
                active = allowed & (distance < cross.cutoff_angstrom)
                if not bool(active.any()):
                    continue
                i, j = torch.nonzero(active, as_tuple=True)
                right = torch.tensor([[p.sigma_angstrom, p.epsilon_kcal_per_mol, p.charge_e]
                                      for p in cross.receptor_atoms[start:end]], dtype=torch.float64)
                r = distance[i, j]
                sigma = .5 * (left[i, 0] + right[j, 0])
                epsilon = torch.sqrt(left[i, 1] * right[j, 1])
                ratio6 = (sigma / r).pow(6)
                switch = _switch(r, cross.switch_start_angstrom, cross.cutoff_angstrom)
                lj = (4 * epsilon * (ratio6.pow(2) - ratio6) * switch).sum()
                electrostatic = (COULOMB_KCAL_ANGSTROM_PER_MOL_E2 * left[i, 2] * right[j, 2]
                    * torch.exp(-cross.screening_kappa_per_angstrom * r) / (cross.dielectric * r) * switch).sum()
                gradient = torch.autograd.grad(lj + electrostatic, x)[0]
                totals += torch.stack((lj.detach(), electrostatic.detach()))
                force -= gradient.detach()
                evaluated_pairs += int(i.numel())
        if not bool(torch.isfinite(totals).all()) or not bool(torch.isfinite(force).all()):
            raise FloatingPointError("nonfinite cross energy or force")
        self.identity()
        return {"cross_lennard_jones": totals[0:1], "cross_screened_coulomb": totals[1:2]}, force, evaluated_pairs

    def evaluate(self, system, neighbors):
        identity = self.identity()
        internal = self.internal.evaluate(system, neighbors)
        components, cross_force, _ = self.cross_terms(system)
        components = {"ligand_internal": internal.term.energy, **components}
        total = sum(components.values())
        term = replace(internal.term, name=OBJECTIVE_ID, energy=total,
                       forces=internal.term.forces + cross_force,
                       energy_descriptor=QuantityDescriptor(
                           name="fixed_receptor_objective", unit="kcal/mol",
                           semantics="ligand_internal_plus_cross_lj_plus_cross_screened_coulomb",
                           physical_quantity=True, calibrated=False, reference_method=None),
                       force_descriptor=QuantityDescriptor(
                           name="fixed_receptor_ligand_force", unit="kcal/mol/angstrom",
                           semantics="negative_ligand_gradient_with_fixed_receptor",
                           physical_quantity=True, calibrated=False, reference_method=None),
                       provenance_sha256=digest({"identity": identity, "system": canonical_system_sha256(system),
                                                "internal": internal.term.provenance_sha256}))
        return ExtendedEvaluation(term, MappingProxyType(components), internal.constraint_observations,
                                  digest(identity), (*internal.scientific_blockers, "cross_objective_not_scientifically_validated"))
