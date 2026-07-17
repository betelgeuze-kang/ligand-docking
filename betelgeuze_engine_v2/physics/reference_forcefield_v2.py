"""Versioned improper-torsion and distance-constraint extension for reference physics."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from numbers import Real
import operator
import struct
from types import MappingProxyType
from typing import Any, Mapping

import torch

from betelgeuze_engine_v2.contracts import QuantityDescriptor
from betelgeuze_engine_v2.geometry import CompactNeighborList
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from .composition import EnergyTermResult
from .reference_forcefield import evaluate_reference_force_field
from .reference_parameters import ReferenceForceFieldParameters


REFERENCE_FORCEFIELD_V2_PARAMETER_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_forcefield_parameters/2.0.0"
)
REFERENCE_FORCEFIELD_V2_EVALUATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_forcefield_evaluation/2.0.0"
)
REFERENCE_DISTANCE_CONSTRAINT_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_distance_constraint_projection/2.0.0"
)
REFERENCE_DISTANCE_CONSTRAINT_PROJECTION_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_distance_constraint_projection_config/2.0.0"
)
REFERENCE_FORCEFIELD_V2_MAX_IMPROPERS = 4_096
REFERENCE_FORCEFIELD_V2_MAX_CONSTRAINTS = 4_096
REFERENCE_CONSTRAINT_PROJECTION_MAX_ITERATIONS = 1_000
REFERENCE_FORCEFIELD_V2_SCIENTIFIC_BLOCKERS = (
    "caller_supplied_extension_parameters_not_independently_reviewed",
    "harmonic_out_of_plane_improper_not_scientifically_validated",
    "equal_weight_distance_constraints_ignore_atomic_masses",
    "equal_weight_constrained_minimization_not_scientifically_validated",
    "independent_constrained_minimization_evidence_missing",
    "general_improper_parameter_assignment_and_coverage_not_implemented",
    "independent_force_constraint_validation_missing",
    "long_range_vacuum_electrostatics_not_supported",
    "solvation_scope_limited_to_fixed_radius_polar_gb_capability",
    "product_integration_not_qualified",
)


class ReferenceForceFieldV2Error(ValueError):
    """The v2 extension parameter, topology, or numerical contract is invalid."""


class ReferenceForceFieldV2ApplicabilityError(RuntimeError):
    """The v2 extension cannot safely evaluate the supplied molecular state."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ReferenceForceFieldV2Error(
            "reference forcefield v2 payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _finite_float(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceForceFieldV2Error(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise ReferenceForceFieldV2Error(f"{name} must be finite")
    return result


def _positive_float(value: object, *, name: str, maximum: float) -> float:
    result = _finite_float(value, name=name)
    if result <= 0.0 or result > maximum:
        raise ReferenceForceFieldV2Error(f"{name} must be in (0,{maximum}]")
    return result


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise ReferenceForceFieldV2Error(f"{name} must be an integer")
    try:
        result = int(operator.index(value))
    except TypeError:
        raise ReferenceForceFieldV2Error(f"{name} must be an integer") from None
    if result < minimum or result > maximum:
        raise ReferenceForceFieldV2Error(
            f"{name} must be in [{minimum},{maximum}]"
        )
    return result


def _atom_index(value: object, *, name: str) -> int:
    return _exact_int(value, name=name, minimum=0, maximum=2**31 - 1)


def _freeze_json(value: Any, *, path: str = "metadata") -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ReferenceForceFieldV2Error(f"{path} contains a non-finite float")
        return float(value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ReferenceForceFieldV2Error(f"{path} keys must be strings")
        return MappingProxyType(
            {
                key: _freeze_json(value[key], path=f"{path}.{key}")
                for key in sorted(value)
            }
        )
    if isinstance(value, (tuple, list)):
        return tuple(
            _freeze_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    raise ReferenceForceFieldV2Error(
        f"{path} contains unsupported JSON value {type(value).__name__}"
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _tensor_sha256(value: torch.Tensor) -> str:
    values = value.detach().to(dtype=torch.float64, device="cpu").contiguous().view(-1)
    payload = bytearray(8 * values.numel())
    for index, item in enumerate(values.tolist()):
        struct.pack_into("<d", payload, index * 8, float(item))
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class HarmonicOutOfPlaneImproperParameter:
    """One ordered star-topology out-of-plane harmonic restraint."""

    center_atom: int
    plane_atom_i: int
    plane_atom_j: int
    out_of_plane_atom: int
    equilibrium_radians: float
    force_constant_kcal_per_mol_radian2: float

    def __post_init__(self) -> None:
        indices = tuple(
            _atom_index(value, name="improper atom index")
            for value in (
                self.center_atom,
                self.plane_atom_i,
                self.plane_atom_j,
                self.out_of_plane_atom,
            )
        )
        if len(set(indices)) != 4:
            raise ReferenceForceFieldV2Error("improper atom indices must be distinct")
        equilibrium = _finite_float(
            self.equilibrium_radians,
            name="improper equilibrium_radians",
        )
        if not -0.5 * math.pi < equilibrium < 0.5 * math.pi:
            raise ReferenceForceFieldV2Error(
                "improper equilibrium_radians must be in (-pi/2,pi/2)"
            )
        object.__setattr__(self, "center_atom", indices[0])
        object.__setattr__(self, "plane_atom_i", indices[1])
        object.__setattr__(self, "plane_atom_j", indices[2])
        object.__setattr__(self, "out_of_plane_atom", indices[3])
        object.__setattr__(self, "equilibrium_radians", equilibrium)
        object.__setattr__(
            self,
            "force_constant_kcal_per_mol_radian2",
            _positive_float(
                self.force_constant_kcal_per_mol_radian2,
                name="improper force constant",
                maximum=1.0e9,
            ),
        )

    @property
    def unordered_star_key(self) -> tuple[int, tuple[int, int, int]]:
        return self.center_atom, tuple(
            sorted((self.plane_atom_i, self.plane_atom_j, self.out_of_plane_atom))
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "center_atom": self.center_atom,
            "plane_atom_i": self.plane_atom_i,
            "plane_atom_j": self.plane_atom_j,
            "out_of_plane_atom": self.out_of_plane_atom,
            "equilibrium_radians": self.equilibrium_radians,
            "force_constant_kcal_per_mol_radian2": (
                self.force_constant_kcal_per_mol_radian2
            ),
            "angle_semantics": (
                "asin(dot(out_center, cross(plane_i_center, plane_j_center)) / "
                "(|out_center|*|cross|))"
            ),
        }


@dataclass(frozen=True, slots=True)
class DistanceConstraintParameter:
    """One exact atom-pair distance target and convergence tolerance."""

    atom_i: int
    atom_j: int
    target_distance_angstrom: float
    tolerance_angstrom: float = 1.0e-8

    def __post_init__(self) -> None:
        i, j = sorted(
            (
                _atom_index(self.atom_i, name="constraint atom_i"),
                _atom_index(self.atom_j, name="constraint atom_j"),
            )
        )
        if i == j:
            raise ReferenceForceFieldV2Error(
                "distance constraint atom indices must be distinct"
            )
        object.__setattr__(self, "atom_i", i)
        object.__setattr__(self, "atom_j", j)
        object.__setattr__(
            self,
            "target_distance_angstrom",
            _positive_float(
                self.target_distance_angstrom,
                name="constraint target_distance_angstrom",
                maximum=1.0e6,
            ),
        )
        object.__setattr__(
            self,
            "tolerance_angstrom",
            _positive_float(
                self.tolerance_angstrom,
                name="constraint tolerance_angstrom",
                maximum=1.0,
            ),
        )

    @property
    def pair(self) -> tuple[int, int]:
        return self.atom_i, self.atom_j

    def to_dict(self) -> dict[str, object]:
        return {
            "atom_i": self.atom_i,
            "atom_j": self.atom_j,
            "target_distance_angstrom": self.target_distance_angstrom,
            "tolerance_angstrom": self.tolerance_angstrom,
            "projection_weighting": "equal_weight_without_atomic_masses",
        }


@dataclass(frozen=True, slots=True)
class ReferenceForceFieldV2Parameters:
    """Immutable extension around one frozen v1 explicit parameter set."""

    base_parameters: ReferenceForceFieldParameters
    impropers: tuple[HarmonicOutOfPlaneImproperParameter, ...] = ()
    constraints: tuple[DistanceConstraintParameter, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    scientifically_validated: bool = False
    schema_id: str = REFERENCE_FORCEFIELD_V2_PARAMETER_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_FORCEFIELD_V2_PARAMETER_SCHEMA_ID:
            raise ReferenceForceFieldV2Error("unsupported forcefield v2 parameter schema")
        if not isinstance(self.base_parameters, ReferenceForceFieldParameters):
            raise ReferenceForceFieldV2Error(
                "base_parameters must be ReferenceForceFieldParameters"
            )
        impropers = tuple(self.impropers)
        constraints = tuple(self.constraints)
        if len(impropers) > REFERENCE_FORCEFIELD_V2_MAX_IMPROPERS:
            raise ReferenceForceFieldV2Error("improper parameter capacity exceeded")
        if len(constraints) > REFERENCE_FORCEFIELD_V2_MAX_CONSTRAINTS:
            raise ReferenceForceFieldV2Error("distance constraint capacity exceeded")
        if not all(
            isinstance(row, HarmonicOutOfPlaneImproperParameter) for row in impropers
        ):
            raise ReferenceForceFieldV2Error(
                "impropers must contain HarmonicOutOfPlaneImproperParameter rows"
            )
        if not all(isinstance(row, DistanceConstraintParameter) for row in constraints):
            raise ReferenceForceFieldV2Error(
                "constraints must contain DistanceConstraintParameter rows"
            )
        improper_keys = [row.unordered_star_key for row in impropers]
        if len(improper_keys) != len(set(improper_keys)):
            raise ReferenceForceFieldV2Error(
                "improper star parameter definitions must be unique"
            )
        constraint_pairs = [row.pair for row in constraints]
        if len(constraint_pairs) != len(set(constraint_pairs)):
            raise ReferenceForceFieldV2Error(
                "distance constraint pair definitions must be unique"
            )
        if not isinstance(self.metadata, Mapping):
            raise ReferenceForceFieldV2Error("metadata must be a mapping")
        if not isinstance(self.scientifically_validated, bool):
            raise ReferenceForceFieldV2Error(
                "scientifically_validated must be a boolean"
            )
        if self.scientifically_validated:
            raise ReferenceForceFieldV2Error(
                "forcefield v2 scientific promotion requires external evidence"
            )
        object.__setattr__(self, "impropers", impropers)
        object.__setattr__(self, "constraints", constraints)
        object.__setattr__(self, "metadata", _freeze_json(self.metadata))
        object.__setattr__(self, "scientifically_validated", False)

    @property
    def topology_sha256(self) -> str:
        return self.base_parameters.topology_sha256

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "base_parameter_fingerprint_sha256": (
                self.base_parameters.fingerprint_sha256
            ),
            "base_parameter_schema_id": self.base_parameters.schema_id,
            "topology_sha256": self.topology_sha256,
            "improper_angle_semantics": "ordered_star_out_of_plane_asin",
            "constraint_semantics": (
                "simultaneous_equal_weight_degree_relaxed_jacobi_projection"
            ),
            "impropers": [row.to_dict() for row in self.impropers],
            "constraints": [row.to_dict() for row in self.constraints],
            "metadata": _thaw_json(self.metadata),
            "scientifically_validated": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class DistanceConstraintObservation:
    atom_i: int
    atom_j: int
    observed_distance_angstrom: float
    target_distance_angstrom: float
    residual_angstrom: float
    tolerance_angstrom: float
    satisfied: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "atom_i": self.atom_i,
            "atom_j": self.atom_j,
            "observed_distance_angstrom": self.observed_distance_angstrom,
            "target_distance_angstrom": self.target_distance_angstrom,
            "residual_angstrom": self.residual_angstrom,
            "tolerance_angstrom": self.tolerance_angstrom,
            "satisfied": self.satisfied,
        }


@dataclass(frozen=True, slots=True)
class ReferenceForceFieldV2Evaluation:
    term: EnergyTermResult
    component_energies: Mapping[str, torch.Tensor]
    improper_forces: torch.Tensor
    constraint_observations: tuple[DistanceConstraintObservation, ...]
    parameter_fingerprint_sha256: str
    scientific_blockers: tuple[str, ...] = REFERENCE_FORCEFIELD_V2_SCIENTIFIC_BLOCKERS
    schema_id: str = REFERENCE_FORCEFIELD_V2_EVALUATION_SCHEMA_ID

    @property
    def constraints_satisfied(self) -> bool:
        return all(row.satisfied for row in self.constraint_observations)

    @property
    def scientifically_validated(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "component_names": list(self.component_energies),
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "improper_force_sha256": _tensor_sha256(self.improper_forces),
            "constraint_count": len(self.constraint_observations),
            "constraints_satisfied": self.constraints_satisfied,
            "constraint_observations": [
                row.to_dict() for row in self.constraint_observations
            ],
            "scientifically_validated": False,
            "claim_safe": False,
            "scientific_blockers": list(self.scientific_blockers),
        }


def _minimum_image(delta: torch.Tensor, system: AllAtomSystem) -> torch.Tensor:
    if system.cell is None:
        return delta
    lengths = system.cell.orthorhombic_lengths().to(
        dtype=delta.dtype,
        device=delta.device,
    )
    periodic = torch.tensor(system.cell.periodic, dtype=torch.bool, device=delta.device)
    safe_lengths = torch.where(periodic, lengths, torch.ones_like(lengths))
    wrapped = delta - torch.round(delta / safe_lengths) * safe_lengths
    return torch.where(periodic, wrapped, delta)


def _vector(
    coordinates: torch.Tensor,
    system: AllAtomSystem,
    first: int,
    second: int,
) -> torch.Tensor:
    return _minimum_image(coordinates[:, first] - coordinates[:, second], system)


def _out_of_plane_angle(
    coordinates: torch.Tensor,
    system: AllAtomSystem,
    row: HarmonicOutOfPlaneImproperParameter,
) -> torch.Tensor:
    plane_i = _vector(coordinates, system, row.plane_atom_i, row.center_atom)
    plane_j = _vector(coordinates, system, row.plane_atom_j, row.center_atom)
    out = _vector(coordinates, system, row.out_of_plane_atom, row.center_atom)
    normal = torch.cross(plane_i, plane_j, dim=-1)
    normal_norm = torch.linalg.vector_norm(normal, dim=-1)
    out_norm = torch.linalg.vector_norm(out, dim=-1)
    if bool((normal_norm <= 1.0e-12).any().item()):
        raise ReferenceForceFieldV2ApplicabilityError(
            "improper reference plane is collinear"
        )
    if bool((out_norm <= 1.0e-12).any().item()):
        raise ReferenceForceFieldV2ApplicabilityError(
            "improper out-of-plane vector has zero length"
        )
    sine = (out * normal).sum(dim=-1) / (out_norm * normal_norm)
    if bool((sine.abs() >= 1.0 - 1.0e-10).any().item()):
        raise ReferenceForceFieldV2ApplicabilityError(
            "improper angle is too close to derivative singularity"
        )
    return torch.asin(sine.clamp(-1.0, 1.0))


def _validate_extension_topology(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldV2Parameters,
) -> None:
    if canonical_topology_sha256(system) != parameters.topology_sha256:
        raise ReferenceForceFieldV2ApplicabilityError(
            "forcefield v2 topology identity mismatch"
        )
    atom_count = system.atom_count
    bonds = {
        tuple(sorted((int(row.atom_i), int(row.atom_j)))) for row in system.bonds
    }
    for row in parameters.impropers:
        indices = (
            row.center_atom,
            row.plane_atom_i,
            row.plane_atom_j,
            row.out_of_plane_atom,
        )
        if max(indices) >= atom_count:
            raise ReferenceForceFieldV2ApplicabilityError(
                "improper parameter index is outside topology"
            )
        required = {
            tuple(sorted((row.center_atom, row.plane_atom_i))),
            tuple(sorted((row.center_atom, row.plane_atom_j))),
            tuple(sorted((row.center_atom, row.out_of_plane_atom))),
        }
        if not required <= bonds:
            raise ReferenceForceFieldV2ApplicabilityError(
                "improper star is not fully bonded to its center atom"
            )
    for row in parameters.constraints:
        if row.atom_j >= atom_count:
            raise ReferenceForceFieldV2ApplicabilityError(
                "distance constraint index is outside topology"
            )


def _constraint_observations(
    coordinates: torch.Tensor,
    system: AllAtomSystem,
    constraints: tuple[DistanceConstraintParameter, ...],
) -> tuple[DistanceConstraintObservation, ...]:
    rows: list[DistanceConstraintObservation] = []
    for row in constraints:
        distance = float(
            torch.linalg.vector_norm(
                _vector(coordinates, system, row.atom_i, row.atom_j),
                dim=-1,
            )[0].item()
        )
        residual = distance - row.target_distance_angstrom
        rows.append(
            DistanceConstraintObservation(
                atom_i=row.atom_i,
                atom_j=row.atom_j,
                observed_distance_angstrom=distance,
                target_distance_angstrom=row.target_distance_angstrom,
                residual_angstrom=residual,
                tolerance_angstrom=row.tolerance_angstrom,
                satisfied=abs(residual) <= row.tolerance_angstrom,
            )
        )
    return tuple(rows)


def evaluate_reference_force_field_v2(
    system: AllAtomSystem,
    neighbors: CompactNeighborList,
    parameters: ReferenceForceFieldV2Parameters,
) -> ReferenceForceFieldV2Evaluation:
    """Evaluate frozen v1 terms plus ordered-star harmonic improper terms."""

    if not isinstance(parameters, ReferenceForceFieldV2Parameters):
        raise ReferenceForceFieldV2Error(
            "parameters must be ReferenceForceFieldV2Parameters"
        )
    _validate_extension_topology(system, parameters)
    base = evaluate_reference_force_field(system, neighbors, parameters.base_parameters)
    coordinates = system.coordinates.detach().clone().requires_grad_(True)
    improper_energy = coordinates.sum(dim=(1, 2)) * 0.0
    for row in parameters.impropers:
        angle = _out_of_plane_angle(coordinates, system, row)
        improper_energy = improper_energy + 0.5 * (
            row.force_constant_kcal_per_mol_radian2
        ) * (angle - row.equilibrium_radians).pow(2)
    improper_gradient = torch.autograd.grad(
        improper_energy.sum(),
        coordinates,
        create_graph=False,
    )[0]
    improper_forces = -improper_gradient
    total_energy = base.term.energy + improper_energy.detach()
    total_forces = base.term.forces + improper_forces.detach()
    components = {
        **base.component_energies,
        "harmonic_out_of_plane_improper": improper_energy.detach(),
    }
    provenance = _sha256(
        {
            "base_evaluation_provenance_sha256": base.term.provenance_sha256,
            "source_system_sha256": canonical_system_sha256(system),
            "topology_sha256": canonical_topology_sha256(system),
            "v2_parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        }
    )
    term = EnergyTermResult(
        name="reference_force_field_v2:improper_constraint_extension",
        energy=total_energy,
        forces=total_forces,
        energy_descriptor=QuantityDescriptor(
            name="reference_force_field_v2_energy",
            unit="kcal/mol",
            semantics=(
                "frozen_v1_total_plus_harmonic_ordered_star_out_of_plane_improper"
            ),
            physical_quantity=True,
            calibrated=False,
            reference_method=None,
        ),
        force_descriptor=QuantityDescriptor(
            name="reference_force_field_v2_force",
            unit="kcal/mol/angstrom",
            semantics="negative_coordinate_gradient_of_v2_extension_energy",
            physical_quantity=True,
            calibrated=False,
            reference_method=None,
        ),
        validated_for_composition=False,
        provenance_sha256=provenance,
    )
    return ReferenceForceFieldV2Evaluation(
        term=term,
        component_energies=MappingProxyType(components),
        improper_forces=improper_forces.detach(),
        constraint_observations=_constraint_observations(
            system.coordinates,
            system,
            parameters.constraints,
        ),
        parameter_fingerprint_sha256=parameters.fingerprint_sha256,
    )


@dataclass(frozen=True, slots=True)
class DistanceConstraintProjectionConfig:
    max_iterations: int = 100
    max_pair_correction_angstrom: float = 0.25
    schema_id: str = REFERENCE_DISTANCE_CONSTRAINT_PROJECTION_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_DISTANCE_CONSTRAINT_PROJECTION_CONFIG_SCHEMA_ID:
            raise ReferenceForceFieldV2Error(
                "unsupported distance constraint projection config schema"
            )
        object.__setattr__(
            self,
            "max_iterations",
            _exact_int(
                self.max_iterations,
                name="max_iterations",
                minimum=1,
                maximum=REFERENCE_CONSTRAINT_PROJECTION_MAX_ITERATIONS,
            ),
        )
        object.__setattr__(
            self,
            "max_pair_correction_angstrom",
            _positive_float(
                self.max_pair_correction_angstrom,
                name="max_pair_correction_angstrom",
                maximum=100.0,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm": (
                "simultaneous_equal_weight_degree_relaxed_jacobi_"
                "distance_projection"
            ),
            "max_iterations": self.max_iterations,
            "max_pair_correction_angstrom": self.max_pair_correction_angstrom,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class DistanceConstraintProjectionIteration:
    iteration: int
    max_absolute_residual_angstrom: float
    satisfied_constraint_count: int
    constraint_observations: tuple[DistanceConstraintObservation, ...]
    failure_code: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "iteration": self.iteration,
            "max_absolute_residual_angstrom": self.max_absolute_residual_angstrom,
            "satisfied_constraint_count": self.satisfied_constraint_count,
            "constraint_observations": [
                row.to_dict() for row in self.constraint_observations
            ],
            "failure_code": self.failure_code,
        }


@dataclass(frozen=True, slots=True)
class DistanceConstraintProjectionResult:
    status: str
    failure_code: str | None
    source_system_sha256: str
    parameter_fingerprint_sha256: str
    config_fingerprint_sha256: str
    system: AllAtomSystem
    iterations: tuple[DistanceConstraintProjectionIteration, ...]
    projection_sha256: str
    scientific_blockers: tuple[str, ...] = REFERENCE_FORCEFIELD_V2_SCIENTIFIC_BLOCKERS
    schema_id: str = REFERENCE_DISTANCE_CONSTRAINT_PROJECTION_SCHEMA_ID

    @property
    def converged(self) -> bool:
        return self.status == "converged"

    @property
    def final_observation(self) -> DistanceConstraintProjectionIteration:
        return self.iterations[-1]

    @property
    def scientifically_validated(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "status": self.status,
            "failure_code": self.failure_code,
            "converged": self.converged,
            "source_system_sha256": self.source_system_sha256,
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "final_system_sha256": canonical_system_sha256(self.system),
            "final_coordinates_sha256": _tensor_sha256(self.system.coordinates),
            "projection_sha256": self.projection_sha256,
            "iteration_count": len(self.iterations) - 1,
            "iterations": [row.to_dict() for row in self.iterations],
            "scientifically_validated": False,
            "claim_safe": False,
            "scientific_blockers": list(self.scientific_blockers),
        }


def project_distance_constraints(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldV2Parameters,
    config: DistanceConstraintProjectionConfig | None = None,
) -> DistanceConstraintProjectionResult:
    """Project distances with symmetric degree-relaxed equal-weight Jacobi sweeps."""

    config = DistanceConstraintProjectionConfig() if config is None else config
    if not isinstance(config, DistanceConstraintProjectionConfig):
        raise ReferenceForceFieldV2Error(
            "config must be DistanceConstraintProjectionConfig"
        )
    if not isinstance(parameters, ReferenceForceFieldV2Parameters):
        raise ReferenceForceFieldV2Error(
            "parameters must be ReferenceForceFieldV2Parameters"
        )
    if system.coordinates.device.type != "cpu" or system.coordinates.dtype != torch.float64:
        raise ReferenceForceFieldV2Error(
            "distance constraint projection requires CPU float64 coordinates"
        )
    if system.model_count != 1:
        raise ReferenceForceFieldV2Error(
            "distance constraint projection requires exactly one model"
        )
    _validate_extension_topology(system, parameters)
    coordinates = system.coordinates.detach().clone()
    rows: list[DistanceConstraintProjectionIteration] = []

    def observe(iteration: int, failure_code: str | None = None) -> None:
        observations = _constraint_observations(
            coordinates,
            system,
            parameters.constraints,
        )
        rows.append(
            DistanceConstraintProjectionIteration(
                iteration=iteration,
                max_absolute_residual_angstrom=max(
                    (abs(row.residual_angstrom) for row in observations),
                    default=0.0,
                ),
                satisfied_constraint_count=sum(row.satisfied for row in observations),
                constraint_observations=observations,
                failure_code=failure_code,
            )
        )

    observe(0)
    status = "converged"
    failure_code: str | None = None
    if not all(row.satisfied for row in rows[-1].constraint_observations):
        constraint_degrees = [0] * system.atom_count
        for constraint in parameters.constraints:
            constraint_degrees[constraint.atom_i] += 1
            constraint_degrees[constraint.atom_j] += 1
        relaxation_degree = max(constraint_degrees, default=1)
        status = "max_iterations_reached"
        failure_code = "constraint_iteration_budget_exhausted"
        for iteration in range(1, config.max_iterations + 1):
            degenerate = False
            updates = torch.zeros_like(coordinates)
            for constraint in parameters.constraints:
                vector = _vector(
                    coordinates,
                    system,
                    constraint.atom_i,
                    constraint.atom_j,
                )[0]
                distance = float(torch.linalg.vector_norm(vector).item())
                if distance <= 1.0e-12:
                    status = "degenerate_constraint_geometry"
                    failure_code = "constraint_pair_has_zero_distance"
                    degenerate = True
                    break
                residual = distance - constraint.target_distance_angstrom
                correction = max(
                    -config.max_pair_correction_angstrom,
                    min(config.max_pair_correction_angstrom, residual),
                )
                direction = vector / distance
                updates[0, constraint.atom_i] -= 0.5 * correction * direction
                updates[0, constraint.atom_j] += 0.5 * correction * direction
            if not degenerate:
                coordinates += updates / float(relaxation_degree)
            observe(iteration, failure_code if degenerate else None)
            if degenerate:
                break
            if all(row.satisfied for row in rows[-1].constraint_observations):
                status = "converged"
                failure_code = None
                break

    source_sha256 = canonical_system_sha256(system)
    projection_projection = {
        "schema_id": REFERENCE_DISTANCE_CONSTRAINT_PROJECTION_SCHEMA_ID,
        "source_system_sha256": source_sha256,
        "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        "config_fingerprint_sha256": config.fingerprint_sha256,
        "status": status,
        "failure_code": failure_code,
        "final_coordinates_sha256": _tensor_sha256(coordinates),
        "iterations": [row.to_dict() for row in rows],
    }
    projection_sha256 = _sha256(projection_projection)
    projected_system = system.with_coordinates(
        coordinates,
        operation="equal_weight_distance_constraint_projection",
        operation_evidence_sha256=projection_sha256,
    )
    return DistanceConstraintProjectionResult(
        status=status,
        failure_code=failure_code,
        source_system_sha256=source_sha256,
        parameter_fingerprint_sha256=parameters.fingerprint_sha256,
        config_fingerprint_sha256=config.fingerprint_sha256,
        system=projected_system,
        iterations=tuple(rows),
        projection_sha256=projection_sha256,
    )


__all__ = [
    "REFERENCE_CONSTRAINT_PROJECTION_MAX_ITERATIONS",
    "REFERENCE_DISTANCE_CONSTRAINT_PROJECTION_CONFIG_SCHEMA_ID",
    "REFERENCE_DISTANCE_CONSTRAINT_PROJECTION_SCHEMA_ID",
    "REFERENCE_FORCEFIELD_V2_EVALUATION_SCHEMA_ID",
    "REFERENCE_FORCEFIELD_V2_MAX_CONSTRAINTS",
    "REFERENCE_FORCEFIELD_V2_MAX_IMPROPERS",
    "REFERENCE_FORCEFIELD_V2_PARAMETER_SCHEMA_ID",
    "REFERENCE_FORCEFIELD_V2_SCIENTIFIC_BLOCKERS",
    "DistanceConstraintObservation",
    "DistanceConstraintParameter",
    "DistanceConstraintProjectionConfig",
    "DistanceConstraintProjectionIteration",
    "DistanceConstraintProjectionResult",
    "HarmonicOutOfPlaneImproperParameter",
    "ReferenceForceFieldV2ApplicabilityError",
    "ReferenceForceFieldV2Error",
    "ReferenceForceFieldV2Evaluation",
    "ReferenceForceFieldV2Parameters",
    "evaluate_reference_force_field_v2",
    "project_distance_constraints",
]
