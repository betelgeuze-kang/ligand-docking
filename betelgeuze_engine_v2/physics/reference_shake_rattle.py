"""Deterministic mass-weighted SHAKE/RATTLE reference constraints.

This module is intentionally separate from the frozen equal-weight constraint
projection used by reference constrained minimization.  It implements the
kinematic constraint layer needed by the provisional CPU ``float64`` NVE path:

* SHAKE position corrections use the previous constrained bond vectors;
* RATTLE removes radial relative velocity along the constrained vectors;
* corrections are applied in canonical atom-pair order with inverse-mass
  weighting; and
* non-periodic or full three-dimensional orthorhombic minimum-image geometry is
  accepted, while ambiguous periodic target distances fail closed.

The implementation and its reports are numerical contracts only.  They do not
assign constraints, atomic masses, or parameters and are not scientific
validation evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
import struct
from typing import Mapping

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    require_valid_all_atom_system,
)


REFERENCE_SHAKE_RATTLE_ALGORITHM_ID = (
    "cpu_float64_canonical_pair_mass_weighted_shake_rattle/1.0.0"
)
REFERENCE_SHAKE_RATTLE_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_shake_rattle_config/1.0.0"
)
REFERENCE_SHAKE_REPORT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_shake_report/1.0.0"
)
REFERENCE_RATTLE_REPORT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_rattle_report/1.0.0"
)
REFERENCE_SHAKE_RATTLE_MAX_CONSTRAINTS = 4096
REFERENCE_SHAKE_RATTLE_MAX_ITERATIONS = 1000
REFERENCE_SHAKE_RATTLE_CONVERGENCE_TOLERANCE_SCALE = 0.5
REFERENCE_SHAKE_RATTLE_SCIENTIFIC_BLOCKERS = (
    "caller_supplied_constraints_not_independently_reviewed",
    "constraint_assignment_and_hydrogen_bond_selection_not_implemented",
    "atom_mass_assignment_not_implemented",
    "shake_rattle_reference_path_not_independently_validated",
    "constrained_nve_energy_drift_acceptance_evidence_missing",
    "product_integration_not_qualified",
)


class ReferenceSHAKERATTLEError(ValueError):
    """A SHAKE/RATTLE request or canonical constraint payload failed closed."""


def _finite_float(
    value: object,
    *,
    name: str,
    positive: bool = False,
    nonnegative: bool = False,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceSHAKERATTLEError(f"{name} must be a finite real number")
    number = float(value)
    if not math.isfinite(number):
        raise ReferenceSHAKERATTLEError(f"{name} must be finite")
    if positive and number <= 0.0:
        raise ReferenceSHAKERATTLEError(f"{name} must be positive")
    if nonnegative and number < 0.0:
        raise ReferenceSHAKERATTLEError(f"{name} must be non-negative")
    if maximum is not None and number > maximum:
        raise ReferenceSHAKERATTLEError(f"{name} exceeds the bounded limit")
    return number


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReferenceSHAKERATTLEError(f"{name} must be an integer")
    integer = int(value)
    if integer < minimum or (maximum is not None and integer > maximum):
        upper = "" if maximum is None else f" and at most {maximum}"
        raise ReferenceSHAKERATTLEError(
            f"{name} must be at least {minimum}{upper}"
        )
    return integer


def _require_float_hex(value: object, *, name: str) -> float:
    if not isinstance(value, str):
        raise ReferenceSHAKERATTLEError(f"{name} must be canonical binary64 hex")
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise ReferenceSHAKERATTLEError(
            f"{name} must be canonical binary64 hex"
        ) from exc
    if not math.isfinite(number) or number.hex() != value:
        raise ReferenceSHAKERATTLEError(
            f"{name} must be canonical finite binary64 hex"
        )
    return number


def _canonical_sha256(payload: object) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()


def _tensor_sha256(value: torch.Tensor) -> str:
    rows = value.detach().to(dtype=torch.float64, device="cpu").contiguous().reshape(-1)
    payload = bytearray(8 * rows.numel())
    for index, item in enumerate(rows.tolist()):
        struct.pack_into("<d", payload, index * 8, float(item))
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class ReferenceSHAKERATTLEDistanceConstraint:
    """One exact minimum-image distance constraint for SHAKE/RATTLE."""

    atom_i: int
    atom_j: int
    target_distance_angstrom: float
    tolerance_angstrom: float = 1.0e-8

    def __post_init__(self) -> None:
        i = _exact_int(self.atom_i, name="constraint atom_i", minimum=0)
        j = _exact_int(self.atom_j, name="constraint atom_j", minimum=0)
        if i == j:
            raise ReferenceSHAKERATTLEError(
                "distance constraint atom indices must be distinct"
            )
        i, j = sorted((i, j))
        object.__setattr__(self, "atom_i", i)
        object.__setattr__(self, "atom_j", j)
        object.__setattr__(
            self,
            "target_distance_angstrom",
            _finite_float(
                self.target_distance_angstrom,
                name="constraint target_distance_angstrom",
                positive=True,
                maximum=1.0e6,
            ),
        )
        object.__setattr__(
            self,
            "tolerance_angstrom",
            _finite_float(
                self.tolerance_angstrom,
                name="constraint tolerance_angstrom",
                positive=True,
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
            "target_distance_angstrom_hex": self.target_distance_angstrom.hex(),
            "tolerance_angstrom_hex": self.tolerance_angstrom.hex(),
            "distance_semantics": "minimum_image_euclidean_angstrom",
            "projection_weighting": "inverse_atomic_mass",
        }

    @classmethod
    def from_dict(cls, value: object) -> "ReferenceSHAKERATTLEDistanceConstraint":
        expected = {
            "atom_i",
            "atom_j",
            "target_distance_angstrom_hex",
            "tolerance_angstrom_hex",
            "distance_semantics",
            "projection_weighting",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ReferenceSHAKERATTLEError("distance constraint payload is invalid")
        if value["distance_semantics"] != "minimum_image_euclidean_angstrom":
            raise ReferenceSHAKERATTLEError("unsupported constraint distance semantics")
        if value["projection_weighting"] != "inverse_atomic_mass":
            raise ReferenceSHAKERATTLEError("unsupported constraint mass weighting")
        result = cls(
            atom_i=_exact_int(value["atom_i"], name="constraint atom_i"),
            atom_j=_exact_int(value["atom_j"], name="constraint atom_j"),
            target_distance_angstrom=_require_float_hex(
                value["target_distance_angstrom_hex"],
                name="constraint target distance",
            ),
            tolerance_angstrom=_require_float_hex(
                value["tolerance_angstrom_hex"],
                name="constraint tolerance",
            ),
        )
        if result.to_dict() != dict(value):
            raise ReferenceSHAKERATTLEError(
                "distance constraint payload is not canonical"
            )
        return result


@dataclass(frozen=True, slots=True)
class ReferenceSHAKERATTLEConfig:
    constraints: tuple[ReferenceSHAKERATTLEDistanceConstraint, ...] = ()
    velocity_tolerance_angstrom_per_ps: float = 1.0e-10
    max_position_iterations: int = 100
    max_velocity_iterations: int = 100
    max_pair_position_correction_angstrom: float = 0.25
    convergence_tolerance_scale: float = (
        REFERENCE_SHAKE_RATTLE_CONVERGENCE_TOLERANCE_SCALE
    )
    schema_id: str = REFERENCE_SHAKE_RATTLE_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_SHAKE_RATTLE_CONFIG_SCHEMA_ID:
            raise ReferenceSHAKERATTLEError("unsupported SHAKE/RATTLE config schema")
        rows = tuple(self.constraints)
        if len(rows) > REFERENCE_SHAKE_RATTLE_MAX_CONSTRAINTS:
            raise ReferenceSHAKERATTLEError("distance constraint capacity exceeded")
        if not all(
            isinstance(row, ReferenceSHAKERATTLEDistanceConstraint) for row in rows
        ):
            raise ReferenceSHAKERATTLEError(
                "constraints must contain ReferenceSHAKERATTLEDistanceConstraint rows"
            )
        pairs = [row.pair for row in rows]
        if len(pairs) != len(set(pairs)):
            raise ReferenceSHAKERATTLEError(
                "distance constraint atom pairs must be unique"
            )
        object.__setattr__(self, "constraints", tuple(sorted(rows, key=lambda row: row.pair)))
        object.__setattr__(
            self,
            "velocity_tolerance_angstrom_per_ps",
            _finite_float(
                self.velocity_tolerance_angstrom_per_ps,
                name="velocity_tolerance_angstrom_per_ps",
                positive=True,
                maximum=1.0,
            ),
        )
        object.__setattr__(
            self,
            "max_position_iterations",
            _exact_int(
                self.max_position_iterations,
                name="max_position_iterations",
                minimum=1,
                maximum=REFERENCE_SHAKE_RATTLE_MAX_ITERATIONS,
            ),
        )
        object.__setattr__(
            self,
            "max_velocity_iterations",
            _exact_int(
                self.max_velocity_iterations,
                name="max_velocity_iterations",
                minimum=1,
                maximum=REFERENCE_SHAKE_RATTLE_MAX_ITERATIONS,
            ),
        )
        object.__setattr__(
            self,
            "max_pair_position_correction_angstrom",
            _finite_float(
                self.max_pair_position_correction_angstrom,
                name="max_pair_position_correction_angstrom",
                positive=True,
                maximum=100.0,
            ),
        )
        scale = _finite_float(
            self.convergence_tolerance_scale,
            name="convergence_tolerance_scale",
        )
        if scale != REFERENCE_SHAKE_RATTLE_CONVERGENCE_TOLERANCE_SCALE:
            raise ReferenceSHAKERATTLEError(
                "convergence_tolerance_scale must equal the frozen value"
            )
        object.__setattr__(self, "convergence_tolerance_scale", scale)

    @property
    def enabled(self) -> bool:
        return bool(self.constraints)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_SHAKE_RATTLE_ALGORITHM_ID,
            "constraints": [row.to_dict() for row in self.constraints],
            "velocity_tolerance_angstrom_per_ps_hex": (
                self.velocity_tolerance_angstrom_per_ps.hex()
            ),
            "max_position_iterations": self.max_position_iterations,
            "max_velocity_iterations": self.max_velocity_iterations,
            "max_pair_position_correction_angstrom_hex": (
                self.max_pair_position_correction_angstrom.hex()
            ),
            "convergence_tolerance_scale_hex": (
                self.convergence_tolerance_scale.hex()
            ),
            "constraint_order": "ascending_canonical_atom_pair",
            "position_algorithm": (
                "iterative_shake_previous_constrained_pair_vector"
            ),
            "velocity_algorithm": "iterative_rattle_current_pair_vector",
        }

    @classmethod
    def from_dict(cls, value: object) -> "ReferenceSHAKERATTLEConfig":
        expected = {
            "schema_id",
            "algorithm_id",
            "constraints",
            "velocity_tolerance_angstrom_per_ps_hex",
            "max_position_iterations",
            "max_velocity_iterations",
            "max_pair_position_correction_angstrom_hex",
            "convergence_tolerance_scale_hex",
            "constraint_order",
            "position_algorithm",
            "velocity_algorithm",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ReferenceSHAKERATTLEError("SHAKE/RATTLE config payload is invalid")
        if value["algorithm_id"] != REFERENCE_SHAKE_RATTLE_ALGORITHM_ID:
            raise ReferenceSHAKERATTLEError("unsupported SHAKE/RATTLE algorithm")
        if value["constraint_order"] != "ascending_canonical_atom_pair":
            raise ReferenceSHAKERATTLEError("unsupported constraint order")
        if value["position_algorithm"] != (
            "iterative_shake_previous_constrained_pair_vector"
        ):
            raise ReferenceSHAKERATTLEError("unsupported SHAKE position algorithm")
        if value["velocity_algorithm"] != "iterative_rattle_current_pair_vector":
            raise ReferenceSHAKERATTLEError("unsupported RATTLE velocity algorithm")
        raw_constraints = value["constraints"]
        if not isinstance(raw_constraints, list):
            raise ReferenceSHAKERATTLEError("constraints must be a list")
        result = cls(
            constraints=tuple(
                ReferenceSHAKERATTLEDistanceConstraint.from_dict(row)
                for row in raw_constraints
            ),
            velocity_tolerance_angstrom_per_ps=_require_float_hex(
                value["velocity_tolerance_angstrom_per_ps_hex"],
                name="velocity tolerance",
            ),
            max_position_iterations=_exact_int(
                value["max_position_iterations"],
                name="max_position_iterations",
            ),
            max_velocity_iterations=_exact_int(
                value["max_velocity_iterations"],
                name="max_velocity_iterations",
            ),
            max_pair_position_correction_angstrom=_require_float_hex(
                value["max_pair_position_correction_angstrom_hex"],
                name="maximum pair position correction",
            ),
            convergence_tolerance_scale=_require_float_hex(
                value["convergence_tolerance_scale_hex"],
                name="convergence tolerance scale",
            ),
            schema_id=str(value["schema_id"]),
        )
        if result.to_dict() != dict(value):
            raise ReferenceSHAKERATTLEError(
                "SHAKE/RATTLE config payload is not canonical"
            )
        return result

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class ReferencePositionConstraintObservation:
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
            "observed_distance_angstrom_hex": self.observed_distance_angstrom.hex(),
            "target_distance_angstrom_hex": self.target_distance_angstrom.hex(),
            "residual_angstrom_hex": self.residual_angstrom.hex(),
            "tolerance_angstrom_hex": self.tolerance_angstrom.hex(),
            "satisfied": self.satisfied,
        }


@dataclass(frozen=True, slots=True)
class ReferenceVelocityConstraintObservation:
    atom_i: int
    atom_j: int
    radial_relative_velocity_angstrom_per_ps: float
    tolerance_angstrom_per_ps: float
    satisfied: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "atom_i": self.atom_i,
            "atom_j": self.atom_j,
            "radial_relative_velocity_angstrom_per_ps_hex": (
                self.radial_relative_velocity_angstrom_per_ps.hex()
            ),
            "tolerance_angstrom_per_ps_hex": self.tolerance_angstrom_per_ps.hex(),
            "satisfied": self.satisfied,
        }


@dataclass(frozen=True, slots=True)
class ReferenceSHAKEReport:
    status: str
    failure_code: str | None
    coordinates: torch.Tensor
    iteration_count: int
    correction_count: int
    clipped_correction_count: int
    max_abs_residual_trace_angstrom: tuple[float, ...]
    observations: tuple[ReferencePositionConstraintObservation, ...]
    source_system_sha256: str
    config_fingerprint_sha256: str
    masses_sha256: str
    reference_coordinates_sha256: str
    predicted_coordinates_sha256: str
    schema_id: str = REFERENCE_SHAKE_REPORT_SCHEMA_ID

    @property
    def converged(self) -> bool:
        return self.status == "converged"

    @property
    def scientifically_validated(self) -> bool:
        return False

    @property
    def max_abs_residual_angstrom(self) -> float:
        return max(
            (abs(row.residual_angstrom) for row in self.observations),
            default=0.0,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_SHAKE_RATTLE_ALGORITHM_ID,
            "status": self.status,
            "failure_code": self.failure_code,
            "source_system_sha256": self.source_system_sha256,
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "masses_sha256": self.masses_sha256,
            "reference_coordinates_sha256": self.reference_coordinates_sha256,
            "predicted_coordinates_sha256": self.predicted_coordinates_sha256,
            "iteration_count": self.iteration_count,
            "correction_count": self.correction_count,
            "clipped_correction_count": self.clipped_correction_count,
            "max_abs_residual_trace_angstrom_hex": [
                value.hex() for value in self.max_abs_residual_trace_angstrom
            ],
            "max_abs_residual_angstrom_hex": (
                self.max_abs_residual_angstrom.hex()
            ),
            "observations": [row.to_dict() for row in self.observations],
            "coordinates_sha256": _tensor_sha256(self.coordinates),
            "scientifically_validated": False,
            "claim_safe": False,
            "scientific_blockers": list(
                REFERENCE_SHAKE_RATTLE_SCIENTIFIC_BLOCKERS
            ),
        }


@dataclass(frozen=True, slots=True)
class ReferenceRATTLEReport:
    status: str
    failure_code: str | None
    velocities_angstrom_per_ps: torch.Tensor
    iteration_count: int
    correction_count: int
    max_abs_residual_trace_angstrom_per_ps: tuple[float, ...]
    observations: tuple[ReferenceVelocityConstraintObservation, ...]
    source_system_sha256: str
    config_fingerprint_sha256: str
    masses_sha256: str
    coordinates_sha256: str
    input_velocities_sha256: str
    schema_id: str = REFERENCE_RATTLE_REPORT_SCHEMA_ID

    @property
    def converged(self) -> bool:
        return self.status == "converged"

    @property
    def scientifically_validated(self) -> bool:
        return False

    @property
    def max_abs_residual_angstrom_per_ps(self) -> float:
        return max(
            (
                abs(row.radial_relative_velocity_angstrom_per_ps)
                for row in self.observations
            ),
            default=0.0,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_SHAKE_RATTLE_ALGORITHM_ID,
            "status": self.status,
            "failure_code": self.failure_code,
            "source_system_sha256": self.source_system_sha256,
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "masses_sha256": self.masses_sha256,
            "coordinates_sha256": self.coordinates_sha256,
            "input_velocities_sha256": self.input_velocities_sha256,
            "iteration_count": self.iteration_count,
            "correction_count": self.correction_count,
            "max_abs_residual_trace_angstrom_per_ps_hex": [
                value.hex()
                for value in self.max_abs_residual_trace_angstrom_per_ps
            ],
            "max_abs_residual_angstrom_per_ps_hex": (
                self.max_abs_residual_angstrom_per_ps.hex()
            ),
            "observations": [row.to_dict() for row in self.observations],
            "velocities_sha256": _tensor_sha256(self.velocities_angstrom_per_ps),
            "scientifically_validated": False,
            "claim_safe": False,
            "scientific_blockers": list(
                REFERENCE_SHAKE_RATTLE_SCIENTIFIC_BLOCKERS
            ),
        }


def _require_tensor(
    value: torch.Tensor,
    *,
    name: str,
    atom_count: int,
) -> torch.Tensor:
    if (
        not isinstance(value, torch.Tensor)
        or value.dtype != torch.float64
        or value.device.type != "cpu"
        or value.shape != (1, atom_count, 3)
        or not bool(torch.isfinite(value).all().item())
    ):
        raise ReferenceSHAKERATTLEError(
            f"{name} must be finite CPU float64 [1,N,3]"
        )
    return value.detach().clone()


def _require_masses(masses: torch.Tensor, *, atom_count: int) -> torch.Tensor:
    if (
        not isinstance(masses, torch.Tensor)
        or masses.dtype != torch.float64
        or masses.device.type != "cpu"
        or masses.shape != (atom_count,)
        or not bool(torch.isfinite(masses).all().item())
        or bool((masses <= 0.0).any().item())
    ):
        raise ReferenceSHAKERATTLEError(
            "masses must be positive finite CPU float64 [N]"
        )
    return masses.detach().clone()


def _periodic_lengths(system: AllAtomSystem) -> torch.Tensor | None:
    if system.cell is None:
        return None
    if system.cell.periodic != (True, True, True):
        raise ReferenceSHAKERATTLEError(
            "SHAKE/RATTLE periodic cells must be periodic in all three dimensions"
        )
    try:
        lengths = system.cell.orthorhombic_lengths().to(
            dtype=torch.float64,
            device="cpu",
        )
    except ValueError as exc:
        raise ReferenceSHAKERATTLEError(
            "SHAKE/RATTLE supports orthorhombic periodic cells only"
        ) from exc
    if not bool(torch.isfinite(lengths).all().item()) or bool(
        (lengths <= 0.0).any().item()
    ):
        raise ReferenceSHAKERATTLEError(
            "SHAKE/RATTLE periodic lengths must be finite and positive"
        )
    return lengths


def _validate_constraint_domain(
    system: AllAtomSystem,
    config: ReferenceSHAKERATTLEConfig,
) -> None:
    if not isinstance(system, AllAtomSystem):
        raise ReferenceSHAKERATTLEError("system must be AllAtomSystem")
    require_valid_all_atom_system(system)
    if system.model_count != 1:
        raise ReferenceSHAKERATTLEError(
            "SHAKE/RATTLE requires exactly one coordinate model"
        )
    if not isinstance(config, ReferenceSHAKERATTLEConfig):
        raise ReferenceSHAKERATTLEError(
            "config must be ReferenceSHAKERATTLEConfig"
        )
    lengths = _periodic_lengths(system)
    for constraint in config.constraints:
        if constraint.atom_j >= system.atom_count:
            raise ReferenceSHAKERATTLEError(
                "distance constraint index is outside topology"
            )
        if lengths is not None and (
            constraint.target_distance_angstrom + constraint.tolerance_angstrom
            >= 0.5 * float(lengths.min().item())
        ):
            raise ReferenceSHAKERATTLEError(
                "periodic constraint target must be below half the shortest box length"
            )


def validate_reference_shake_rattle_inputs(
    system: AllAtomSystem,
    masses: torch.Tensor,
    config: ReferenceSHAKERATTLEConfig,
) -> torch.Tensor:
    """Validate topology, mass, and periodic applicability and return masses."""

    _validate_constraint_domain(system, config)
    active_masses = _require_masses(masses, atom_count=system.atom_count)
    return active_masses


def minimum_image_displacement(
    delta: torch.Tensor,
    system: AllAtomSystem,
) -> torch.Tensor:
    """Return a full-orthorhombic minimum-image displacement."""

    if (
        not isinstance(delta, torch.Tensor)
        or delta.dtype != torch.float64
        or delta.device.type != "cpu"
        or delta.ndim < 1
        or delta.shape[-1] != 3
        or not bool(torch.isfinite(delta).all().item())
    ):
        raise ReferenceSHAKERATTLEError(
            "minimum-image displacement must be finite CPU float64 [...,3]"
        )
    lengths = _periodic_lengths(system)
    if lengths is None:
        return delta
    shape = (1,) * (delta.ndim - 1) + (3,)
    active_lengths = lengths.view(shape)
    return delta - torch.round(delta / active_lengths) * active_lengths


def _wrap_coordinates(coordinates: torch.Tensor, system: AllAtomSystem) -> torch.Tensor:
    lengths = _periodic_lengths(system)
    if lengths is None:
        return coordinates
    return coordinates - torch.floor(
        coordinates / lengths.view(1, 1, 3)
    ) * lengths.view(1, 1, 3)


def _pair_vector(
    coordinates: torch.Tensor,
    system: AllAtomSystem,
    atom_i: int,
    atom_j: int,
) -> torch.Tensor:
    delta = coordinates[:, atom_i] - coordinates[:, atom_j]
    return minimum_image_displacement(delta.unsqueeze(1), system)[:, 0]


def observe_reference_position_constraints(
    system: AllAtomSystem,
    coordinates: torch.Tensor,
    config: ReferenceSHAKERATTLEConfig,
) -> tuple[ReferencePositionConstraintObservation, ...]:
    """Measure declared distance residuals without changing coordinates."""

    _validate_constraint_domain(system, config)
    active = _require_tensor(
        coordinates,
        name="coordinates",
        atom_count=system.atom_count,
    )
    rows: list[ReferencePositionConstraintObservation] = []
    for constraint in config.constraints:
        vector = _pair_vector(
            active,
            system,
            constraint.atom_i,
            constraint.atom_j,
        )[0]
        distance = float(torch.linalg.vector_norm(vector).item())
        residual = distance - constraint.target_distance_angstrom
        rows.append(
            ReferencePositionConstraintObservation(
                atom_i=constraint.atom_i,
                atom_j=constraint.atom_j,
                observed_distance_angstrom=distance,
                target_distance_angstrom=constraint.target_distance_angstrom,
                residual_angstrom=residual,
                tolerance_angstrom=constraint.tolerance_angstrom,
                satisfied=abs(residual) <= constraint.tolerance_angstrom,
            )
        )
    return tuple(rows)


def observe_reference_velocity_constraints(
    system: AllAtomSystem,
    coordinates: torch.Tensor,
    velocities_angstrom_per_ps: torch.Tensor,
    config: ReferenceSHAKERATTLEConfig,
) -> tuple[ReferenceVelocityConstraintObservation, ...]:
    """Measure radial relative velocities without changing the state."""

    _validate_constraint_domain(system, config)
    active_coordinates = _require_tensor(
        coordinates,
        name="coordinates",
        atom_count=system.atom_count,
    )
    active_velocities = _require_tensor(
        velocities_angstrom_per_ps,
        name="velocities_angstrom_per_ps",
        atom_count=system.atom_count,
    )
    rows: list[ReferenceVelocityConstraintObservation] = []
    for constraint in config.constraints:
        vector = _pair_vector(
            active_coordinates,
            system,
            constraint.atom_i,
            constraint.atom_j,
        )[0]
        distance = float(torch.linalg.vector_norm(vector).item())
        if distance <= 1.0e-12:
            raise ReferenceSHAKERATTLEError(
                "constraint_pair_has_zero_distance"
            )
        relative_velocity = (
            active_velocities[0, constraint.atom_i]
            - active_velocities[0, constraint.atom_j]
        )
        radial = float(torch.dot(vector / distance, relative_velocity).item())
        rows.append(
            ReferenceVelocityConstraintObservation(
                atom_i=constraint.atom_i,
                atom_j=constraint.atom_j,
                radial_relative_velocity_angstrom_per_ps=radial,
                tolerance_angstrom_per_ps=(
                    config.velocity_tolerance_angstrom_per_ps
                ),
                satisfied=(
                    abs(radial) <= config.velocity_tolerance_angstrom_per_ps
                ),
            )
        )
    return tuple(rows)


def _position_max(
    observations: tuple[ReferencePositionConstraintObservation, ...],
) -> float:
    return max((abs(row.residual_angstrom) for row in observations), default=0.0)


def _velocity_max(
    observations: tuple[ReferenceVelocityConstraintObservation, ...],
) -> float:
    return max(
        (
            abs(row.radial_relative_velocity_angstrom_per_ps)
            for row in observations
        ),
        default=0.0,
    )


def _positions_converged(
    observations: tuple[ReferencePositionConstraintObservation, ...],
    config: ReferenceSHAKERATTLEConfig,
) -> bool:
    return all(
        abs(row.residual_angstrom)
        <= config.convergence_tolerance_scale * row.tolerance_angstrom
        for row in observations
    )


def _velocities_converged(
    observations: tuple[ReferenceVelocityConstraintObservation, ...],
    config: ReferenceSHAKERATTLEConfig,
) -> bool:
    internal_tolerance = (
        config.convergence_tolerance_scale
        * config.velocity_tolerance_angstrom_per_ps
    )
    return all(
        abs(row.radial_relative_velocity_angstrom_per_ps) <= internal_tolerance
        for row in observations
    )


def project_reference_shake_positions(
    system: AllAtomSystem,
    reference_coordinates: torch.Tensor,
    predicted_coordinates: torch.Tensor,
    masses: torch.Tensor,
    config: ReferenceSHAKERATTLEConfig,
) -> ReferenceSHAKEReport:
    """Apply bounded iterative SHAKE position corrections.

    ``reference_coordinates`` must be the previously constrained state.  Its
    minimum-image pair vectors remain fixed during each SHAKE solve, matching
    the standard linearized SHAKE correction.  Returned coordinates are wrapped
    into the supported periodic cell after every sweep.
    """

    active_masses = validate_reference_shake_rattle_inputs(system, masses, config)
    reference = _require_tensor(
        reference_coordinates,
        name="reference_coordinates",
        atom_count=system.atom_count,
    )
    coordinates = _require_tensor(
        predicted_coordinates,
        name="predicted_coordinates",
        atom_count=system.atom_count,
    )
    source_system_sha256 = canonical_system_sha256(system)
    config_fingerprint_sha256 = config.fingerprint_sha256
    masses_sha256 = _tensor_sha256(active_masses)
    reference_coordinates_sha256 = _tensor_sha256(reference)
    predicted_coordinates_sha256 = _tensor_sha256(coordinates)
    reference_observations = observe_reference_position_constraints(
        system,
        reference,
        config,
    )
    if not _positions_converged(reference_observations, config):
        observations = observe_reference_position_constraints(
            system,
            coordinates,
            config,
        )
        return ReferenceSHAKEReport(
            status="invalid_reference_state",
            failure_code="reference_coordinates_violate_constraints",
            coordinates=coordinates,
            iteration_count=0,
            correction_count=0,
            clipped_correction_count=0,
            max_abs_residual_trace_angstrom=(_position_max(observations),),
            observations=observations,
            source_system_sha256=source_system_sha256,
            config_fingerprint_sha256=config_fingerprint_sha256,
            masses_sha256=masses_sha256,
            reference_coordinates_sha256=reference_coordinates_sha256,
            predicted_coordinates_sha256=predicted_coordinates_sha256,
        )

    observations = observe_reference_position_constraints(system, coordinates, config)
    trace = [_position_max(observations)]
    if _positions_converged(observations, config):
        return ReferenceSHAKEReport(
            status="converged",
            failure_code=None,
            coordinates=coordinates,
            iteration_count=0,
            correction_count=0,
            clipped_correction_count=0,
            max_abs_residual_trace_angstrom=tuple(trace),
            observations=observations,
            source_system_sha256=source_system_sha256,
            config_fingerprint_sha256=config_fingerprint_sha256,
            masses_sha256=masses_sha256,
            reference_coordinates_sha256=reference_coordinates_sha256,
            predicted_coordinates_sha256=predicted_coordinates_sha256,
        )

    inverse_masses = 1.0 / active_masses
    reference_vectors = {
        constraint.pair: _pair_vector(
            reference,
            system,
            constraint.atom_i,
            constraint.atom_j,
        )[0]
        for constraint in config.constraints
    }
    correction_count = 0
    clipped_count = 0
    status = "max_iterations_reached"
    failure_code: str | None = "shake_iteration_budget_exhausted"
    iterations = 0
    for iteration in range(1, config.max_position_iterations + 1):
        iterations = iteration
        degenerate = False
        for constraint in config.constraints:
            current = _pair_vector(
                coordinates,
                system,
                constraint.atom_i,
                constraint.atom_j,
            )[0]
            reference_vector = reference_vectors[constraint.pair]
            current_squared = float(torch.dot(current, current).item())
            target_squared = constraint.target_distance_angstrom**2
            squared_residual = current_squared - target_squared
            if abs(
                math.sqrt(max(current_squared, 0.0))
                - constraint.target_distance_angstrom
            ) <= (
                config.convergence_tolerance_scale
                * constraint.tolerance_angstrom
            ):
                continue
            inverse_mass_sum = float(
                inverse_masses[constraint.atom_i].item()
                + inverse_masses[constraint.atom_j].item()
            )
            denominator = (
                2.0
                * inverse_mass_sum
                * float(torch.dot(current, reference_vector).item())
            )
            if not math.isfinite(denominator) or abs(denominator) <= 1.0e-18:
                status = "degenerate_constraint_geometry"
                failure_code = "shake_reference_current_pair_dot_is_zero"
                degenerate = True
                break
            multiplier = squared_residual / denominator
            relative_correction = (
                inverse_mass_sum
                * abs(multiplier)
                * float(torch.linalg.vector_norm(reference_vector).item())
            )
            if relative_correction > config.max_pair_position_correction_angstrom:
                multiplier *= (
                    config.max_pair_position_correction_angstrom
                    / relative_correction
                )
                clipped_count += 1
            correction_i = (
                -float(inverse_masses[constraint.atom_i].item())
                * multiplier
                * reference_vector
            )
            correction_j = (
                float(inverse_masses[constraint.atom_j].item())
                * multiplier
                * reference_vector
            )
            coordinates[0, constraint.atom_i] += correction_i
            coordinates[0, constraint.atom_j] += correction_j
            correction_count += 1
        coordinates = _wrap_coordinates(coordinates, system)
        observations = observe_reference_position_constraints(
            system,
            coordinates,
            config,
        )
        trace.append(_position_max(observations))
        if degenerate:
            break
        if _positions_converged(observations, config):
            status = "converged"
            failure_code = None
            break
    return ReferenceSHAKEReport(
        status=status,
        failure_code=failure_code,
        coordinates=coordinates,
        iteration_count=iterations,
        correction_count=correction_count,
        clipped_correction_count=clipped_count,
        max_abs_residual_trace_angstrom=tuple(trace),
        observations=observations,
        source_system_sha256=source_system_sha256,
        config_fingerprint_sha256=config_fingerprint_sha256,
        masses_sha256=masses_sha256,
        reference_coordinates_sha256=reference_coordinates_sha256,
        predicted_coordinates_sha256=predicted_coordinates_sha256,
    )


def project_reference_rattle_velocities(
    system: AllAtomSystem,
    coordinates: torch.Tensor,
    velocities_angstrom_per_ps: torch.Tensor,
    masses: torch.Tensor,
    config: ReferenceSHAKERATTLEConfig,
) -> ReferenceRATTLEReport:
    """Apply bounded iterative RATTLE radial-velocity corrections."""

    active_masses = validate_reference_shake_rattle_inputs(system, masses, config)
    active_coordinates = _require_tensor(
        coordinates,
        name="coordinates",
        atom_count=system.atom_count,
    )
    velocities = _require_tensor(
        velocities_angstrom_per_ps,
        name="velocities_angstrom_per_ps",
        atom_count=system.atom_count,
    )
    source_system_sha256 = canonical_system_sha256(system)
    config_fingerprint_sha256 = config.fingerprint_sha256
    masses_sha256 = _tensor_sha256(active_masses)
    coordinates_sha256 = _tensor_sha256(active_coordinates)
    input_velocities_sha256 = _tensor_sha256(velocities)
    position_observations = observe_reference_position_constraints(
        system,
        active_coordinates,
        config,
    )
    if not _positions_converged(position_observations, config):
        observations = observe_reference_velocity_constraints(
            system,
            active_coordinates,
            velocities,
            config,
        )
        return ReferenceRATTLEReport(
            status="invalid_position_state",
            failure_code="rattle_coordinates_violate_constraints",
            velocities_angstrom_per_ps=velocities,
            iteration_count=0,
            correction_count=0,
            max_abs_residual_trace_angstrom_per_ps=(_velocity_max(observations),),
            observations=observations,
            source_system_sha256=source_system_sha256,
            config_fingerprint_sha256=config_fingerprint_sha256,
            masses_sha256=masses_sha256,
            coordinates_sha256=coordinates_sha256,
            input_velocities_sha256=input_velocities_sha256,
        )

    observations = observe_reference_velocity_constraints(
        system,
        active_coordinates,
        velocities,
        config,
    )
    trace = [_velocity_max(observations)]
    if _velocities_converged(observations, config):
        return ReferenceRATTLEReport(
            status="converged",
            failure_code=None,
            velocities_angstrom_per_ps=velocities,
            iteration_count=0,
            correction_count=0,
            max_abs_residual_trace_angstrom_per_ps=tuple(trace),
            observations=observations,
            source_system_sha256=source_system_sha256,
            config_fingerprint_sha256=config_fingerprint_sha256,
            masses_sha256=masses_sha256,
            coordinates_sha256=coordinates_sha256,
            input_velocities_sha256=input_velocities_sha256,
        )

    inverse_masses = 1.0 / active_masses
    correction_count = 0
    status = "max_iterations_reached"
    failure_code: str | None = "rattle_iteration_budget_exhausted"
    iterations = 0
    for iteration in range(1, config.max_velocity_iterations + 1):
        iterations = iteration
        degenerate = False
        for constraint in config.constraints:
            vector = _pair_vector(
                active_coordinates,
                system,
                constraint.atom_i,
                constraint.atom_j,
            )[0]
            squared_distance = float(torch.dot(vector, vector).item())
            if not math.isfinite(squared_distance) or squared_distance <= 1.0e-24:
                status = "degenerate_constraint_geometry"
                failure_code = "constraint_pair_has_zero_distance"
                degenerate = True
                break
            relative_velocity = (
                velocities[0, constraint.atom_i]
                - velocities[0, constraint.atom_j]
            )
            radial = float(
                torch.dot(vector, relative_velocity).item()
                / math.sqrt(squared_distance)
            )
            if abs(radial) <= (
                config.convergence_tolerance_scale
                * config.velocity_tolerance_angstrom_per_ps
            ):
                continue
            inverse_mass_sum = float(
                inverse_masses[constraint.atom_i].item()
                + inverse_masses[constraint.atom_j].item()
            )
            multiplier = float(torch.dot(vector, relative_velocity).item()) / (
                inverse_mass_sum * squared_distance
            )
            velocities[0, constraint.atom_i] -= (
                float(inverse_masses[constraint.atom_i].item())
                * multiplier
                * vector
            )
            velocities[0, constraint.atom_j] += (
                float(inverse_masses[constraint.atom_j].item())
                * multiplier
                * vector
            )
            correction_count += 1
        observations = observe_reference_velocity_constraints(
            system,
            active_coordinates,
            velocities,
            config,
        )
        trace.append(_velocity_max(observations))
        if degenerate:
            break
        if _velocities_converged(observations, config):
            status = "converged"
            failure_code = None
            break
    return ReferenceRATTLEReport(
        status=status,
        failure_code=failure_code,
        velocities_angstrom_per_ps=velocities,
        iteration_count=iterations,
        correction_count=correction_count,
        max_abs_residual_trace_angstrom_per_ps=tuple(trace),
        observations=observations,
        source_system_sha256=source_system_sha256,
        config_fingerprint_sha256=config_fingerprint_sha256,
        masses_sha256=masses_sha256,
        coordinates_sha256=coordinates_sha256,
        input_velocities_sha256=input_velocities_sha256,
    )


__all__ = [
    "REFERENCE_RATTLE_REPORT_SCHEMA_ID",
    "REFERENCE_SHAKE_RATTLE_ALGORITHM_ID",
    "REFERENCE_SHAKE_RATTLE_CONFIG_SCHEMA_ID",
    "REFERENCE_SHAKE_RATTLE_CONVERGENCE_TOLERANCE_SCALE",
    "REFERENCE_SHAKE_RATTLE_MAX_CONSTRAINTS",
    "REFERENCE_SHAKE_RATTLE_MAX_ITERATIONS",
    "REFERENCE_SHAKE_RATTLE_SCIENTIFIC_BLOCKERS",
    "REFERENCE_SHAKE_REPORT_SCHEMA_ID",
    "ReferencePositionConstraintObservation",
    "ReferenceRATTLEReport",
    "ReferenceSHAKERATTLEConfig",
    "ReferenceSHAKERATTLEDistanceConstraint",
    "ReferenceSHAKERATTLEError",
    "ReferenceSHAKEReport",
    "ReferenceVelocityConstraintObservation",
    "minimum_image_displacement",
    "observe_reference_position_constraints",
    "observe_reference_velocity_constraints",
    "project_reference_rattle_velocities",
    "project_reference_shake_positions",
    "validate_reference_shake_rattle_inputs",
]
