"""Explicit ordered periodic star terms for bounded OpenMM source projections.

This versioned development model preserves signed Fourier terms and a declared
constant energy offset. It is not the legacy harmonic out-of-plane model. The
NoCutoff equivalence domain is checked at EVERY coordinate evaluation: all
internal pair distances must remain strictly below the base switch start.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
import math
from numbers import Real
from types import MappingProxyType

import torch

from betelgeuze_engine_v2.molecular import AllAtomSystem, canonical_system_sha256
from betelgeuze_engine_v2.physics.reference_forcefield import (
    ReferencePhysicsApplicabilityError, _torsion_angle,
)
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    DistanceConstraintParameter,
    HarmonicOutOfPlaneImproperParameter,
    REFERENCE_FORCEFIELD_V2_SCIENTIFIC_BLOCKERS,
    ReferenceForceFieldV2Parameters,
    _constraint_observations,
    _out_of_plane_angle,
    _validate_extension_topology,
)
from betelgeuze_engine_v2.physics.reference_parameters import (
    PeriodicTorsionParameter,
    ReferenceForceFieldParameters,
)
from betelgeuze_product.cpu_refinement.reference_forcefield_v1_1 import (
    evaluate_reference_force_field,
)
from .provenance import ResearchError, canonical, digest, exact_fields, integer

OPENMM_PERIODIC_PARAMETER_SCHEMA = "cpu_openmm_periodic_parameters/1.0.0"
OPENMM_PERIODIC_EVALUATOR_ID = "cpu_openmm_periodic_reference/1.0.0"
NO_CUTOFF_DOMAIN = "nocutoff_equivalent_inside_switch"
MAX_PERIODIC_IMPROPERS = 4096


class OpenMMPeriodicApplicabilityError(ReferencePhysicsApplicabilityError):
    """A trial left the declared source-equivalent coordinate domain."""


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ResearchError(f"finite {name} required")
    return float(value)


@dataclass(frozen=True, slots=True)
class PeriodicImproperParameter:
    """One signed Fourier term in the exact serialized four-atom order.

The center is explicit topology evidence, not a request to reorder the atoms.
The angle is the same signed ordered dihedral used by PeriodicTorsionForce.
Multiple cyclic permutations of a star are separate terms.
"""

    atom_i: int
    atom_j: int
    atom_k: int
    atom_l: int
    center_atom: int
    periodicity: int
    phase_radians: float
    amplitude_kcal_per_mol: float

    def __post_init__(self):
        indices = tuple(integer(getattr(self, key), 0, 2**31 - 1)
                        for key in ("atom_i", "atom_j", "atom_k", "atom_l"))
        if len(set(indices)) != 4:
            raise ResearchError("periodic improper requires four distinct atoms")
        integer(self.center_atom, 0, 2**31 - 1)
        if self.center_atom not in indices:
            raise ResearchError("periodic improper center must be in the ordered quartet")
        integer(self.periodicity, 1, 12)
        object.__setattr__(self, "phase_radians", _number(self.phase_radians, "improper phase"))
        object.__setattr__(self, "amplitude_kcal_per_mol",
                           _number(self.amplitude_kcal_per_mol, "signed improper amplitude"))

    def to_dict(self):
        return {row.name: getattr(self, row.name) for row in fields(self)}


def normalize_signed_proper(*, atom_i, atom_j, atom_k, atom_l, periodicity,
                            phase_radians, amplitude_kcal_per_mol):
    """Return an existing nonnegative proper term and its exact energy offset.

For k<0, k*(1+cos(x)) = (-k)*(1+cos(x-pi)) + 2*k.
The offset is required for absolute-energy equivalence; it has zero force.
"""
    amplitude = _number(amplitude_kcal_per_mol, "proper amplitude")
    phase = _number(phase_radians, "proper phase")
    term = PeriodicTorsionParameter(atom_i, atom_j, atom_k, atom_l, periodicity,
        phase + math.pi if amplitude < 0 else phase, abs(amplitude))
    offset = _number(2.0 * amplitude if amplitude < 0 else 0.0, "proper normalization offset")
    return term, offset


@dataclass(frozen=True, slots=True)
class OpenMMPeriodicParameters(ReferenceForceFieldV2Parameters):
    periodic_impropers: tuple[PeriodicImproperParameter, ...] = ()
    constant_energy_offset_kcal_per_mol: float = 0.0
    nonbonded_domain: str = NO_CUTOFF_DOMAIN
    schema_id: str = OPENMM_PERIODIC_PARAMETER_SCHEMA

    def __post_init__(self):
        if self.schema_id != OPENMM_PERIODIC_PARAMETER_SCHEMA:
            raise ResearchError("unsupported OpenMM periodic extension schema")
        # Validate inherited fields without changing the frozen legacy contract.
        legacy = ReferenceForceFieldV2Parameters(
            self.base_parameters, self.impropers, self.constraints,
            self.metadata, self.scientifically_validated)
        for key in ("impropers", "constraints", "metadata", "scientifically_validated"):
            object.__setattr__(self, key, getattr(legacy, key))
        rows = tuple(self.periodic_impropers)
        if len(rows) > MAX_PERIODIC_IMPROPERS or any(type(row) is not PeriodicImproperParameter for row in rows):
            raise ResearchError("bounded explicit periodic improper parameters required")
        keys = [(row.atom_i, row.atom_j, row.atom_k, row.atom_l, row.center_atom,
                 row.periodicity, row.phase_radians) for row in rows]
        if len(keys) != len(set(keys)):
            raise ResearchError("duplicate ordered periodic improper term")
        object.__setattr__(self, "periodic_impropers", rows)
        object.__setattr__(self, "constant_energy_offset_kcal_per_mol",
            _number(self.constant_energy_offset_kcal_per_mol, "constant energy offset"))
        if self.nonbonded_domain != NO_CUTOFF_DOMAIN:
            raise ResearchError("unsupported OpenMM periodic nonbonded domain")
        if self.base_parameters.dielectric != 1.0 or self.base_parameters.screening_kappa_per_angstrom != 0.0:
            raise ResearchError("NoCutoff domain requires vacuum dielectric and no screening")

    def to_dict(self):
        return {**ReferenceForceFieldV2Parameters.to_dict(self),
            "periodic_improper_angle_semantics": "ordered_signed_dihedral_atan2",
            "periodic_impropers": [row.to_dict() for row in self.periodic_impropers],
            "constant_energy_offset_kcal_per_mol": self.constant_energy_offset_kcal_per_mol,
            "nonbonded_domain": self.nonbonded_domain}

    @classmethod
    def from_dict(cls, document, base):
        if type(document) is not dict or not isinstance(base, ReferenceForceFieldParameters):
            raise ResearchError("explicit OpenMM periodic extension and base parameters required")
        def row(kind, item):
            if type(item) is not dict:
                raise ResearchError("explicit extension parameter row required")
            names = {field.name for field in fields(kind) if field.init}
            try:
                value = kind(**{name: item[name] for name in names})
            except (KeyError, TypeError) as exc:
                raise ResearchError("incomplete extension parameter row") from exc
            if canonical(value.to_dict()) != canonical(item):
                raise ResearchError("noncanonical extension parameter row")
            return value
        try:
            result = cls(base,
                impropers=tuple(row(HarmonicOutOfPlaneImproperParameter, item) for item in document["impropers"]),
                constraints=tuple(row(DistanceConstraintParameter, item) for item in document["constraints"]),
                metadata=document["metadata"], scientifically_validated=document["scientifically_validated"],
                schema_id=document["schema_id"],
                periodic_impropers=tuple(row(PeriodicImproperParameter, item) for item in document["periodic_impropers"]),
                constant_energy_offset_kcal_per_mol=document["constant_energy_offset_kcal_per_mol"],
                nonbonded_domain=document["nonbonded_domain"])
        except (KeyError, TypeError) as exc:
            raise ResearchError("incomplete OpenMM periodic extension") from exc
        exact_fields(document, set(result.to_dict()))
        if canonical(result.to_dict()) != canonical(document):
            raise ResearchError("OpenMM periodic extension or base identity mismatch")
        return result


def validate_periodic_domain(system, parameters):
    if type(parameters) is not OpenMMPeriodicParameters:
        raise ResearchError("explicit OpenMM periodic parameters required")
    if (not isinstance(system, AllAtomSystem) or system.model_count != 1
            or not 1 <= system.atom_count <= 256 or system.cell is not None
            or system.coordinates.device.type != "cpu" or system.coordinates.dtype != torch.float64
            or not bool(torch.isfinite(system.coordinates).all())):
        raise ResearchError("OpenMM periodic domain requires nonperiodic single-model CPU float64")
    _validate_extension_topology(system, parameters)
    bonds = {tuple(sorted((bond.atom_i, bond.atom_j))) for bond in system.bonds}
    for row in parameters.periodic_impropers:
        indices = (row.atom_i, row.atom_j, row.atom_k, row.atom_l)
        if max(indices) >= system.atom_count:
            raise ResearchError("periodic improper index outside topology")
        if any(tuple(sorted((row.center_atom, atom))) not in bonds
               for atom in indices if atom != row.center_atom):
            raise ResearchError("periodic improper star is not fully bonded to its declared center")
    distances = torch.pdist(system.coordinates[0])
    if (not bool(torch.isfinite(distances).all())
            or bool((distances >= parameters.base_parameters.switch_start_angstrom).any())):
        raise OpenMMPeriodicApplicabilityError("NoCutoff equivalence domain exceeded: internal pair distance at or beyond switch start")


def evaluate_extension(system, neighbors, parameters):
    """Evaluate the versioned extension, preserving legacy constraints unchanged."""
    from .evaluation import ExtendedEvaluation  # Lazy to permit explicit dispatcher.

    validate_periodic_domain(system, parameters)
    base = evaluate_reference_force_field(system, neighbors, parameters.base_parameters)
    coordinates = system.coordinates.detach().clone().requires_grad_(True)
    zero = coordinates.sum(dim=(1, 2)) * 0.0
    harmonic = zero.clone()
    periodic = zero.clone()
    for row in parameters.impropers:
        angle = _out_of_plane_angle(coordinates, system, row)
        harmonic = harmonic + .5 * row.force_constant_kcal_per_mol_radian2 * (angle - row.equilibrium_radians).pow(2)
    for row in parameters.periodic_impropers:
        angle = _torsion_angle(coordinates, system, row.atom_i, row.atom_j, row.atom_k, row.atom_l)
        periodic = periodic + row.amplitude_kcal_per_mol * (1.0 + torch.cos(row.periodicity * angle - row.phase_radians))
    additional = harmonic + periodic
    extra_force = -torch.autograd.grad(additional.sum(), coordinates)[0]
    offset = torch.full_like(zero, parameters.constant_energy_offset_kcal_per_mol)
    components = {**base.component_energies,
        "harmonic_out_of_plane_improper": harmonic.detach(),
        "periodic_star_improper": periodic.detach(),
        "constant_energy_offset": offset.detach()}
    energy = base.term.energy + additional.detach() + offset.detach()
    forces = base.term.forces + extra_force.detach()
    if not bool(torch.isfinite(energy).all()) or not bool(torch.isfinite(forces).all()):
        raise FloatingPointError("nonfinite OpenMM periodic extension energy or force")
    identity = {"evaluator_id": OPENMM_PERIODIC_EVALUATOR_ID,
        "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        "solvation_fingerprint_sha256": None}
    term = replace(base.term, name=OPENMM_PERIODIC_EVALUATOR_ID, energy=energy, forces=forces,
        energy_descriptor=replace(base.term.energy_descriptor,
            name="openmm_periodic_projection_energy",
            semantics="bounded_nocutoff_base_plus_ordered_periodic_improper_plus_constant"),
        force_descriptor=replace(base.term.force_descriptor,
            name="openmm_periodic_projection_force",
            semantics="negative_coordinate_gradient_of_bounded_periodic_projection"),
        provenance_sha256=digest({"evaluator": identity, "system": canonical_system_sha256(system),
            "base": base.term.provenance_sha256, "constant_energy_offset_kcal_per_mol": parameters.constant_energy_offset_kcal_per_mol}))
    blockers = (*base.scientific_blockers, *REFERENCE_FORCEFIELD_V2_SCIENTIFIC_BLOCKERS,
        "openmm_periodic_source_projection_not_scientifically_validated",
        "nocutoff_equivalence_limited_to_declared_coordinate_domain",
        "periodic_improper_source_coverage_requires_external_translation_audit")
    return ExtendedEvaluation(term, MappingProxyType(components),
        _constraint_observations(system.coordinates, system, parameters.constraints),
        digest(identity), tuple(dict.fromkeys(blockers)))
