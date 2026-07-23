"""Claim-closed constrained stationarity candidate for CPU float64 reference physics.

This module is deliberately separate from the frozen constrained-minimization
implementation.  It does not rewrite an existing protocol or receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
import operator
import struct
from typing import Mapping

import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from .reference_forcefield_v2 import (
    ReferenceForceFieldV2ApplicabilityError,
    ReferenceForceFieldV2Parameters,
    evaluate_reference_force_field_v2,
)
from .reference_solvation import (
    FixedBornPolarSolvationParameters,
    ReferenceFixedBornSolvationApplicabilityError,
    evaluate_reference_force_field_v2_with_fixed_born,
)


REFERENCE_CONSTRAINT_STATIONARITY_ALGORITHM_ID = (
    "betelgeuze.engine_v2_reference_constraint_consistent_stationarity/1.0.0"
)
REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_constraint_stationarity_config/1.0.0"
)
REFERENCE_CONSTRAINT_STATIONARITY_CHECKPOINT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_constraint_stationarity_checkpoint/1.0.0"
)
REFERENCE_CONSTRAINT_STATIONARITY_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_constraint_stationarity_result/1.0.0"
)
REFERENCE_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256 = (
    "5642654a25a2d024f7cb8c1de024815f6bf6032b06f6c57509d7b784b708f708"
)
REFERENCE_CONSTRAINT_STATIONARITY_MAX_ITERATIONS = 10_000
REFERENCE_CONSTRAINT_STATIONARITY_MAX_BACKTRACKS = 64
REFERENCE_CONSTRAINT_STATIONARITY_MAX_PROJECTION_SWEEPS = 10_000
REFERENCE_CONSTRAINT_STATIONARITY_SCIENTIFIC_BLOCKERS = (
    "candidate_not_part_of_frozen_14_case_production_receipt",
    "native_openmm_lbfgs_fixed_born_endpoint_remains_rejected",
    "same_coordinate_openmm_comparison_not_yet_bound",
    "equal_weight_distance_constraints_ignore_atomic_masses",
    "supported_scope_limited_to_reference_v2_and_optional_fixed_born",
    "independent_review_missing",
    "two_cpu_host_reproduction_missing",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)

_ACCEPTED_OUTCOMES = (
    "accepted_armijo",
    "accepted_stationarity_polish",
)
_REJECTED_OUTCOMES = (
    "rejected_constraint_projection",
    "rejected_displacement",
    "rejected_tangent_projection",
    "rejected_acceptance",
    "rejected_evaluation",
)
_OBSERVATION_OUTCOMES = ("initial", *_ACCEPTED_OUTCOMES, *_REJECTED_OUTCOMES)


class ReferenceConstraintStationarityError(ValueError):
    """The stationarity candidate request violates its bounded contract."""


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
        raise ReferenceConstraintStationarityError(
            "stationarity payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ReferenceConstraintStationarityError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ReferenceConstraintStationarityError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return normalized


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise ReferenceConstraintStationarityError(f"{name} must be an integer")
    try:
        result = int(operator.index(value))
    except TypeError:
        raise ReferenceConstraintStationarityError(
            f"{name} must be an integer"
        ) from None
    if result < minimum or result > maximum:
        raise ReferenceConstraintStationarityError(
            f"{name} must be in [{minimum},{maximum}]"
        )
    return result


def _finite_float(
    value: object,
    *,
    name: str,
    minimum: float | None = None,
    maximum: float | None = None,
    minimum_inclusive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceConstraintStationarityError(
            f"{name} must be a finite real number"
        )
    result = float(value)
    if not math.isfinite(result):
        raise ReferenceConstraintStationarityError(f"{name} must be finite")
    if minimum is not None:
        invalid = result < minimum if minimum_inclusive else result <= minimum
        if invalid:
            relation = ">=" if minimum_inclusive else ">"
            raise ReferenceConstraintStationarityError(
                f"{name} must be {relation} {minimum}"
            )
    if maximum is not None and result > maximum:
        raise ReferenceConstraintStationarityError(
            f"{name} must be <= {maximum}"
        )
    return result


def _optional_float(value: object, *, name: str) -> float | None:
    if value is None:
        return None
    return _finite_float(value, name=name, minimum=0.0, minimum_inclusive=True)


def _same_float(first: float, second: float) -> bool:
    return struct.pack("<d", first) == struct.pack("<d", second)


def _coordinate_bytes(coordinates: torch.Tensor) -> bytes:
    values = coordinates.detach().to(dtype=torch.float64, device="cpu").contiguous()
    payload = bytearray(8 * values.numel())
    for index, value in enumerate(values.view(-1).tolist()):
        struct.pack_into("<d", payload, 8 * index, float(value))
    return bytes(payload)


def _coordinate_digest(coordinates: torch.Tensor) -> str:
    return hashlib.sha256(_coordinate_bytes(coordinates)).hexdigest()


def _coordinate_hex_rows(
    coordinates: torch.Tensor,
) -> tuple[tuple[str, str, str], ...]:
    if coordinates.device.type != "cpu" or coordinates.dtype != torch.float64:
        raise ReferenceConstraintStationarityError(
            "stationarity coordinates must be CPU float64"
        )
    if coordinates.ndim != 3 or coordinates.shape[0] != 1 or coordinates.shape[2] != 3:
        raise ReferenceConstraintStationarityError(
            "stationarity coordinates must have shape [1,N,3]"
        )
    return tuple(
        tuple(float(value).hex() for value in row)  # type: ignore[misc]
        for row in coordinates[0].tolist()
    )


def _require_coordinate_hex_rows(
    value: object,
) -> tuple[tuple[str, str, str], ...]:
    if not isinstance(value, list) or not value:
        raise ReferenceConstraintStationarityError(
            "checkpoint coordinates must cover every atom"
        )
    rows: list[tuple[str, str, str]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != 3:
            raise ReferenceConstraintStationarityError(
                "checkpoint coordinates must have [atom,3] shape"
            )
        values: list[str] = []
        for item in row:
            if not isinstance(item, str):
                raise ReferenceConstraintStationarityError(
                    "checkpoint coordinates must use canonical binary64 hex"
                )
            try:
                number = float.fromhex(item)
            except ValueError as exc:
                raise ReferenceConstraintStationarityError(
                    "checkpoint coordinates must use canonical binary64 hex"
                ) from exc
            if not math.isfinite(number) or number.hex() != item:
                raise ReferenceConstraintStationarityError(
                    "checkpoint coordinates must use canonical finite binary64 hex"
                )
            values.append(item)
        rows.append((values[0], values[1], values[2]))
    return tuple(rows)


def _coordinates_from_hex(
    rows: tuple[tuple[str, str, str], ...],
) -> torch.Tensor:
    return torch.tensor(
        [[[float.fromhex(item) for item in row] for row in rows]],
        dtype=torch.float64,
        device="cpu",
    )


def _expect_keys(
    value: Mapping[str, object],
    expected: set[str],
    *,
    name: str,
) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        unexpected = sorted(set(value) - expected)
        raise ReferenceConstraintStationarityError(
            f"{name} keys mismatch; missing={missing}, unexpected={unexpected}"
        )


@dataclass(frozen=True, slots=True)
class ReferenceConstraintStationarityConfig:
    """Frozen numerical bounds for the candidate optimizer."""

    max_iterations: int = 512
    max_backtracks: int = 24
    initial_step_size_angstrom2_mol_per_kcal: float = 1.0e-3
    backtrack_factor: float = 0.5
    armijo_constant: float = 1.0e-4
    maximum_atom_displacement_angstrom: float = 5.0e-2
    tangent_force_tolerance_kcal_per_mol_angstrom: float = 1.0e-8
    constraint_acceptance_tolerance_angstrom: float = 1.0e-10
    strict_projection_tolerance_angstrom: float = 1.0e-14
    projection_max_sweeps: int = 1_000
    projection_max_pair_correction_angstrom: float = 0.25
    tangent_projection_max_sweeps: int = 1_000
    tangent_projection_tolerance_kcal_per_mol_angstrom: float = 1.0e-12
    stationarity_energy_relaxation_kcal_per_mol: float = 1.0e-10
    max_neighbors: int = 16
    max_atoms_per_cell: int = 16
    schema_id: str = REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SCHEMA_ID:
            raise ReferenceConstraintStationarityError(
                "unsupported stationarity config schema"
            )
        object.__setattr__(
            self,
            "max_iterations",
            _exact_int(
                self.max_iterations,
                name="max_iterations",
                minimum=1,
                maximum=REFERENCE_CONSTRAINT_STATIONARITY_MAX_ITERATIONS,
            ),
        )
        object.__setattr__(
            self,
            "max_backtracks",
            _exact_int(
                self.max_backtracks,
                name="max_backtracks",
                minimum=0,
                maximum=REFERENCE_CONSTRAINT_STATIONARITY_MAX_BACKTRACKS,
            ),
        )
        object.__setattr__(
            self,
            "projection_max_sweeps",
            _exact_int(
                self.projection_max_sweeps,
                name="projection_max_sweeps",
                minimum=1,
                maximum=REFERENCE_CONSTRAINT_STATIONARITY_MAX_PROJECTION_SWEEPS,
            ),
        )
        object.__setattr__(
            self,
            "tangent_projection_max_sweeps",
            _exact_int(
                self.tangent_projection_max_sweeps,
                name="tangent_projection_max_sweeps",
                minimum=1,
                maximum=REFERENCE_CONSTRAINT_STATIONARITY_MAX_PROJECTION_SWEEPS,
            ),
        )
        object.__setattr__(
            self,
            "max_neighbors",
            _exact_int(
                self.max_neighbors,
                name="max_neighbors",
                minimum=1,
                maximum=65_536,
            ),
        )
        object.__setattr__(
            self,
            "max_atoms_per_cell",
            _exact_int(
                self.max_atoms_per_cell,
                name="max_atoms_per_cell",
                minimum=1,
                maximum=65_536,
            ),
        )
        positive_fields = (
            "initial_step_size_angstrom2_mol_per_kcal",
            "maximum_atom_displacement_angstrom",
            "tangent_force_tolerance_kcal_per_mol_angstrom",
            "constraint_acceptance_tolerance_angstrom",
            "strict_projection_tolerance_angstrom",
            "projection_max_pair_correction_angstrom",
            "tangent_projection_tolerance_kcal_per_mol_angstrom",
            "stationarity_energy_relaxation_kcal_per_mol",
        )
        for field_name in positive_fields:
            object.__setattr__(
                self,
                field_name,
                _finite_float(
                    getattr(self, field_name),
                    name=field_name,
                    minimum=0.0,
                ),
            )
        backtrack = _finite_float(
            self.backtrack_factor,
            name="backtrack_factor",
            minimum=0.0,
            maximum=1.0,
        )
        if backtrack >= 1.0:
            raise ReferenceConstraintStationarityError(
                "backtrack_factor must be less than 1"
            )
        object.__setattr__(self, "backtrack_factor", backtrack)
        object.__setattr__(
            self,
            "armijo_constant",
            _finite_float(
                self.armijo_constant,
                name="armijo_constant",
                minimum=0.0,
                maximum=0.5,
            ),
        )
        if (
            self.strict_projection_tolerance_angstrom
            > self.constraint_acceptance_tolerance_angstrom
        ):
            raise ReferenceConstraintStationarityError(
                "strict projection tolerance must not exceed acceptance tolerance"
            )
        if (
            self.tangent_projection_tolerance_kcal_per_mol_angstrom
            > self.tangent_force_tolerance_kcal_per_mol_angstrom
        ):
            raise ReferenceConstraintStationarityError(
                "tangent projection tolerance must not exceed force tolerance"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_CONSTRAINT_STATIONARITY_ALGORITHM_ID,
            "max_iterations": self.max_iterations,
            "max_backtracks": self.max_backtracks,
            "initial_step_size_angstrom2_mol_per_kcal": (
                self.initial_step_size_angstrom2_mol_per_kcal
            ),
            "backtrack_factor": self.backtrack_factor,
            "armijo_constant": self.armijo_constant,
            "maximum_atom_displacement_angstrom": (
                self.maximum_atom_displacement_angstrom
            ),
            "tangent_force_tolerance_kcal_per_mol_angstrom": (
                self.tangent_force_tolerance_kcal_per_mol_angstrom
            ),
            "constraint_acceptance_tolerance_angstrom": (
                self.constraint_acceptance_tolerance_angstrom
            ),
            "strict_projection_tolerance_angstrom": (
                self.strict_projection_tolerance_angstrom
            ),
            "projection_max_sweeps": self.projection_max_sweeps,
            "projection_max_pair_correction_angstrom": (
                self.projection_max_pair_correction_angstrom
            ),
            "tangent_projection_max_sweeps": (
                self.tangent_projection_max_sweeps
            ),
            "tangent_projection_tolerance_kcal_per_mol_angstrom": (
                self.tangent_projection_tolerance_kcal_per_mol_angstrom
            ),
            "stationarity_energy_relaxation_kcal_per_mol": (
                self.stationarity_energy_relaxation_kcal_per_mol
            ),
            "max_neighbors": self.max_neighbors,
            "max_atoms_per_cell": self.max_atoms_per_cell,
            "constraint_weighting": "equal_weight_without_atomic_masses",
            "stationarity_polish_rule": (
                "strict_tangent_decrease_and_energy_within_best_plus_relaxation"
            ),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class ReferenceConstraintStationarityObservation:
    """One initial, accepted, or rejected candidate state."""

    attempt_index: int
    iteration: int
    trial: int
    outcome: str
    phase: str
    raw_coordinates_sha256: str
    coordinates_angstrom_hex: tuple[tuple[str, str, str], ...]
    coordinates_sha256: str
    step_size_angstrom2_mol_per_kcal: float
    energy_kcal_per_mol: float | None
    energy_above_best_kcal_per_mol: float | None
    max_tangent_force_kcal_per_mol_angstrom: float | None
    max_constraint_residual_angstrom: float
    max_constraint_force_residual_kcal_per_mol_angstrom: float | None
    projection_sweeps: int
    tangent_projection_sweeps: int | None
    directional_derivative_kcal_per_mol: float | None
    armijo_limit_kcal_per_mol: float | None
    failure_code: str | None = None

    def __post_init__(self) -> None:
        if self.outcome not in _OBSERVATION_OUTCOMES:
            raise ReferenceConstraintStationarityError(
                f"unsupported stationarity observation outcome {self.outcome!r}"
            )
        if self.outcome == "initial":
            expected_phase = "initial"
        elif self.outcome == "accepted_armijo":
            expected_phase = "armijo_descent"
        elif self.outcome == "accepted_stationarity_polish":
            expected_phase = "stationarity_polish"
        else:
            expected_phase = "trial_rejection"
        if self.phase != expected_phase:
            raise ReferenceConstraintStationarityError(
                "stationarity observation phase does not match outcome"
            )
        if (self.failure_code is None) != (self.outcome not in _REJECTED_OUTCOMES):
            raise ReferenceConstraintStationarityError(
                "only rejected stationarity observations require a failure code"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "attempt_index": self.attempt_index,
            "iteration": self.iteration,
            "trial": self.trial,
            "outcome": self.outcome,
            "phase": self.phase,
            "raw_coordinates_sha256": self.raw_coordinates_sha256,
            "coordinates_angstrom_hex": [
                list(row) for row in self.coordinates_angstrom_hex
            ],
            "coordinates_sha256": self.coordinates_sha256,
            "step_size_angstrom2_mol_per_kcal": (
                self.step_size_angstrom2_mol_per_kcal
            ),
            "energy_kcal_per_mol": self.energy_kcal_per_mol,
            "energy_above_best_kcal_per_mol": (
                self.energy_above_best_kcal_per_mol
            ),
            "max_tangent_force_kcal_per_mol_angstrom": (
                self.max_tangent_force_kcal_per_mol_angstrom
            ),
            "max_constraint_residual_angstrom": (
                self.max_constraint_residual_angstrom
            ),
            "max_constraint_force_residual_kcal_per_mol_angstrom": (
                self.max_constraint_force_residual_kcal_per_mol_angstrom
            ),
            "projection_sweeps": self.projection_sweeps,
            "tangent_projection_sweeps": self.tangent_projection_sweeps,
            "directional_derivative_kcal_per_mol": (
                self.directional_derivative_kcal_per_mol
            ),
            "armijo_limit_kcal_per_mol": self.armijo_limit_kcal_per_mol,
            "failure_code": self.failure_code,
        }


def _observation_from_dict(
    value: object,
) -> ReferenceConstraintStationarityObservation:
    if not isinstance(value, Mapping):
        raise ReferenceConstraintStationarityError(
            "checkpoint observation must be a mapping"
        )
    expected = {
        "attempt_index",
        "iteration",
        "trial",
        "outcome",
        "phase",
        "raw_coordinates_sha256",
        "coordinates_angstrom_hex",
        "coordinates_sha256",
        "step_size_angstrom2_mol_per_kcal",
        "energy_kcal_per_mol",
        "energy_above_best_kcal_per_mol",
        "max_tangent_force_kcal_per_mol_angstrom",
        "max_constraint_residual_angstrom",
        "max_constraint_force_residual_kcal_per_mol_angstrom",
        "projection_sweeps",
        "tangent_projection_sweeps",
        "directional_derivative_kcal_per_mol",
        "armijo_limit_kcal_per_mol",
        "failure_code",
    }
    _expect_keys(value, expected, name="checkpoint observation")
    outcome = value["outcome"]
    phase = value["phase"]
    if not isinstance(outcome, str) or not isinstance(phase, str):
        raise ReferenceConstraintStationarityError(
            "checkpoint observation outcome and phase must be strings"
        )
    failure = value["failure_code"]
    if failure is not None and not isinstance(failure, str):
        raise ReferenceConstraintStationarityError(
            "checkpoint observation failure code must be a string or null"
        )
    rows = _require_coordinate_hex_rows(value["coordinates_angstrom_hex"])
    coordinates = _coordinates_from_hex(rows)
    observation = ReferenceConstraintStationarityObservation(
        attempt_index=_exact_int(
            value["attempt_index"],
            name="observation attempt_index",
            minimum=0,
            maximum=2**31 - 1,
        ),
        iteration=_exact_int(
            value["iteration"],
            name="observation iteration",
            minimum=0,
            maximum=REFERENCE_CONSTRAINT_STATIONARITY_MAX_ITERATIONS,
        ),
        trial=_exact_int(
            value["trial"],
            name="observation trial",
            minimum=0,
            maximum=REFERENCE_CONSTRAINT_STATIONARITY_MAX_BACKTRACKS,
        ),
        outcome=outcome,
        phase=phase,
        raw_coordinates_sha256=_digest(
            value["raw_coordinates_sha256"],
            name="observation raw coordinate digest",
        ),
        coordinates_angstrom_hex=rows,
        coordinates_sha256=_digest(
            value["coordinates_sha256"],
            name="observation coordinate digest",
        ),
        step_size_angstrom2_mol_per_kcal=_finite_float(
            value["step_size_angstrom2_mol_per_kcal"],
            name="observation step size",
            minimum=0.0,
            minimum_inclusive=True,
        ),
        energy_kcal_per_mol=(
            None
            if value["energy_kcal_per_mol"] is None
            else _finite_float(
                value["energy_kcal_per_mol"],
                name="observation energy",
            )
        ),
        energy_above_best_kcal_per_mol=_optional_float(
            value["energy_above_best_kcal_per_mol"],
            name="observation energy above best",
        ),
        max_tangent_force_kcal_per_mol_angstrom=_optional_float(
            value["max_tangent_force_kcal_per_mol_angstrom"],
            name="observation tangent force",
        ),
        max_constraint_residual_angstrom=_finite_float(
            value["max_constraint_residual_angstrom"],
            name="observation constraint residual",
            minimum=0.0,
            minimum_inclusive=True,
        ),
        max_constraint_force_residual_kcal_per_mol_angstrom=_optional_float(
            value["max_constraint_force_residual_kcal_per_mol_angstrom"],
            name="observation constraint force residual",
        ),
        projection_sweeps=_exact_int(
            value["projection_sweeps"],
            name="observation projection sweeps",
            minimum=0,
            maximum=REFERENCE_CONSTRAINT_STATIONARITY_MAX_PROJECTION_SWEEPS,
        ),
        tangent_projection_sweeps=(
            None
            if value["tangent_projection_sweeps"] is None
            else _exact_int(
                value["tangent_projection_sweeps"],
                name="observation tangent projection sweeps",
                minimum=0,
                maximum=REFERENCE_CONSTRAINT_STATIONARITY_MAX_PROJECTION_SWEEPS,
            )
        ),
        directional_derivative_kcal_per_mol=(
            None
            if value["directional_derivative_kcal_per_mol"] is None
            else _finite_float(
                value["directional_derivative_kcal_per_mol"],
                name="observation directional derivative",
            )
        ),
        armijo_limit_kcal_per_mol=(
            None
            if value["armijo_limit_kcal_per_mol"] is None
            else _finite_float(
                value["armijo_limit_kcal_per_mol"],
                name="observation Armijo limit",
            )
        ),
        failure_code=failure,
    )
    if observation.coordinates_sha256 != _coordinate_digest(coordinates):
        raise ReferenceConstraintStationarityError(
            "checkpoint observation coordinate digest mismatch"
        )
    if observation.to_dict() != dict(value):
        raise ReferenceConstraintStationarityError(
            "checkpoint observation is not canonical"
        )
    return observation


@dataclass(frozen=True, slots=True)
class ReferenceConstraintStationarityCheckpoint:
    """Replay-verifiable exact restart state."""

    source_system_sha256: str
    topology_sha256: str
    parameter_fingerprint_sha256: str
    solvation_parameter_fingerprint_sha256: str | None
    config_fingerprint_sha256: str
    accepted_iterations: int
    rejected_trials: int
    energy_evaluation_count: int
    current_energy_kcal_per_mol: float
    best_energy_kcal_per_mol: float
    current_max_tangent_force_kcal_per_mol_angstrom: float
    current_max_constraint_residual_angstrom: float
    coordinates_angstrom_hex: tuple[tuple[str, str, str], ...]
    coordinates_sha256: str
    observations: tuple[ReferenceConstraintStationarityObservation, ...]
    schema_id: str = REFERENCE_CONSTRAINT_STATIONARITY_CHECKPOINT_SCHEMA_ID

    def projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_CONSTRAINT_STATIONARITY_ALGORITHM_ID,
            "source_system_sha256": self.source_system_sha256,
            "topology_sha256": self.topology_sha256,
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "solvation_parameter_fingerprint_sha256": (
                self.solvation_parameter_fingerprint_sha256
            ),
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "accepted_iterations": self.accepted_iterations,
            "rejected_trials": self.rejected_trials,
            "energy_evaluation_count": self.energy_evaluation_count,
            "current_energy_kcal_per_mol": self.current_energy_kcal_per_mol,
            "best_energy_kcal_per_mol": self.best_energy_kcal_per_mol,
            "current_max_tangent_force_kcal_per_mol_angstrom": (
                self.current_max_tangent_force_kcal_per_mol_angstrom
            ),
            "current_max_constraint_residual_angstrom": (
                self.current_max_constraint_residual_angstrom
            ),
            "coordinates_angstrom_hex": [
                list(row) for row in self.coordinates_angstrom_hex
            ],
            "coordinates_sha256": self.coordinates_sha256,
            "observations": [row.to_dict() for row in self.observations],
        }

    @property
    def checkpoint_sha256(self) -> str:
        return _sha256(self.projection())

    def to_dict(self) -> dict[str, object]:
        return {**self.projection(), "checkpoint_sha256": self.checkpoint_sha256}

    def coordinates(self) -> torch.Tensor:
        return _coordinates_from_hex(self.coordinates_angstrom_hex)


def require_reference_constraint_stationarity_checkpoint_document(
    value: object,
) -> ReferenceConstraintStationarityCheckpoint:
    """Parse and verify one canonical candidate checkpoint document."""

    if isinstance(value, ReferenceConstraintStationarityCheckpoint):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise ReferenceConstraintStationarityError(
            "stationarity checkpoint must be a mapping"
        )
    expected = {
        "schema_id",
        "algorithm_id",
        "source_system_sha256",
        "topology_sha256",
        "parameter_fingerprint_sha256",
        "solvation_parameter_fingerprint_sha256",
        "config_fingerprint_sha256",
        "accepted_iterations",
        "rejected_trials",
        "energy_evaluation_count",
        "current_energy_kcal_per_mol",
        "best_energy_kcal_per_mol",
        "current_max_tangent_force_kcal_per_mol_angstrom",
        "current_max_constraint_residual_angstrom",
        "coordinates_angstrom_hex",
        "coordinates_sha256",
        "observations",
        "checkpoint_sha256",
    }
    _expect_keys(value, expected, name="stationarity checkpoint")
    if value["schema_id"] != REFERENCE_CONSTRAINT_STATIONARITY_CHECKPOINT_SCHEMA_ID:
        raise ReferenceConstraintStationarityError(
            "unsupported stationarity checkpoint schema"
        )
    if value["algorithm_id"] != REFERENCE_CONSTRAINT_STATIONARITY_ALGORITHM_ID:
        raise ReferenceConstraintStationarityError(
            "stationarity checkpoint algorithm mismatch"
        )
    solvation = value["solvation_parameter_fingerprint_sha256"]
    if solvation is not None:
        solvation = _digest(solvation, name="checkpoint solvation fingerprint")
    observation_values = value["observations"]
    if not isinstance(observation_values, list) or not observation_values:
        raise ReferenceConstraintStationarityError(
            "stationarity checkpoint must retain its full observation trace"
        )
    observations = tuple(_observation_from_dict(row) for row in observation_values)
    if tuple(row.attempt_index for row in observations) != tuple(
        range(len(observations))
    ):
        raise ReferenceConstraintStationarityError(
            "checkpoint observation attempt indices must be contiguous"
        )
    if observations[0].outcome != "initial":
        raise ReferenceConstraintStationarityError(
            "checkpoint observation trace must begin with the initial state"
        )
    accepted = sum(row.outcome in _ACCEPTED_OUTCOMES for row in observations)
    rejected = sum(row.outcome in _REJECTED_OUTCOMES for row in observations)
    evaluated = sum(row.energy_kcal_per_mol is not None for row in observations)
    rows = _require_coordinate_hex_rows(value["coordinates_angstrom_hex"])
    checkpoint = ReferenceConstraintStationarityCheckpoint(
        source_system_sha256=_digest(
            value["source_system_sha256"],
            name="checkpoint source system digest",
        ),
        topology_sha256=_digest(
            value["topology_sha256"],
            name="checkpoint topology digest",
        ),
        parameter_fingerprint_sha256=_digest(
            value["parameter_fingerprint_sha256"],
            name="checkpoint parameter fingerprint",
        ),
        solvation_parameter_fingerprint_sha256=solvation,
        config_fingerprint_sha256=_digest(
            value["config_fingerprint_sha256"],
            name="checkpoint config fingerprint",
        ),
        accepted_iterations=_exact_int(
            value["accepted_iterations"],
            name="checkpoint accepted_iterations",
            minimum=0,
            maximum=REFERENCE_CONSTRAINT_STATIONARITY_MAX_ITERATIONS,
        ),
        rejected_trials=_exact_int(
            value["rejected_trials"],
            name="checkpoint rejected_trials",
            minimum=0,
            maximum=(REFERENCE_CONSTRAINT_STATIONARITY_MAX_ITERATIONS)
            * (REFERENCE_CONSTRAINT_STATIONARITY_MAX_BACKTRACKS + 1),
        ),
        energy_evaluation_count=_exact_int(
            value["energy_evaluation_count"],
            name="checkpoint energy_evaluation_count",
            minimum=1,
            maximum=(REFERENCE_CONSTRAINT_STATIONARITY_MAX_ITERATIONS)
            * (REFERENCE_CONSTRAINT_STATIONARITY_MAX_BACKTRACKS + 1)
            + 1,
        ),
        current_energy_kcal_per_mol=_finite_float(
            value["current_energy_kcal_per_mol"],
            name="checkpoint current energy",
        ),
        best_energy_kcal_per_mol=_finite_float(
            value["best_energy_kcal_per_mol"],
            name="checkpoint best energy",
        ),
        current_max_tangent_force_kcal_per_mol_angstrom=_finite_float(
            value["current_max_tangent_force_kcal_per_mol_angstrom"],
            name="checkpoint current tangent force",
            minimum=0.0,
            minimum_inclusive=True,
        ),
        current_max_constraint_residual_angstrom=_finite_float(
            value["current_max_constraint_residual_angstrom"],
            name="checkpoint current constraint residual",
            minimum=0.0,
            minimum_inclusive=True,
        ),
        coordinates_angstrom_hex=rows,
        coordinates_sha256=_digest(
            value["coordinates_sha256"],
            name="checkpoint coordinate digest",
        ),
        observations=observations,
    )
    if checkpoint.accepted_iterations != accepted:
        raise ReferenceConstraintStationarityError(
            "checkpoint accepted iteration count does not match trace"
        )
    if checkpoint.rejected_trials != rejected:
        raise ReferenceConstraintStationarityError(
            "checkpoint rejected trial count does not match trace"
        )
    if checkpoint.energy_evaluation_count != evaluated:
        raise ReferenceConstraintStationarityError(
            "checkpoint energy evaluation count does not match trace"
        )
    coordinates = checkpoint.coordinates()
    if checkpoint.coordinates_sha256 != _coordinate_digest(coordinates):
        raise ReferenceConstraintStationarityError(
            "checkpoint coordinate digest mismatch"
        )
    accepted_rows = (
        observations[0],
        *(row for row in observations[1:] if row.outcome in _ACCEPTED_OUTCOMES),
    )
    final_row = accepted_rows[-1]
    if (
        final_row.coordinates_sha256 != checkpoint.coordinates_sha256
        or final_row.energy_kcal_per_mol is None
        or final_row.max_tangent_force_kcal_per_mol_angstrom is None
        or not _same_float(
            final_row.energy_kcal_per_mol,
            checkpoint.current_energy_kcal_per_mol,
        )
        or not _same_float(
            final_row.max_tangent_force_kcal_per_mol_angstrom,
            checkpoint.current_max_tangent_force_kcal_per_mol_angstrom,
        )
        or not _same_float(
            final_row.max_constraint_residual_angstrom,
            checkpoint.current_max_constraint_residual_angstrom,
        )
    ):
        raise ReferenceConstraintStationarityError(
            "checkpoint current state does not match its accepted trace"
        )
    accepted_energies = [
        row.energy_kcal_per_mol
        for row in accepted_rows
        if row.energy_kcal_per_mol is not None
    ]
    if not _same_float(min(accepted_energies), checkpoint.best_energy_kcal_per_mol):
        raise ReferenceConstraintStationarityError(
            "checkpoint best energy does not match its accepted trace"
        )
    supplied_digest = _digest(
        value["checkpoint_sha256"],
        name="checkpoint document digest",
    )
    if supplied_digest != checkpoint.checkpoint_sha256:
        raise ReferenceConstraintStationarityError(
            "checkpoint document digest mismatch"
        )
    if checkpoint.to_dict() != dict(value):
        raise ReferenceConstraintStationarityError(
            "stationarity checkpoint is not canonical"
        )
    return checkpoint


@dataclass(frozen=True, slots=True)
class _ProjectionResult:
    coordinates: torch.Tensor
    max_residual_angstrom: float
    sweeps: int
    converged: bool
    failure_code: str | None


@dataclass(frozen=True, slots=True)
class _EvaluationResult:
    energy_kcal_per_mol: float
    tangent_forces: torch.Tensor
    max_tangent_force_kcal_per_mol_angstrom: float
    max_constraint_force_residual_kcal_per_mol_angstrom: float
    tangent_projection_sweeps: int


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


def _constraint_vector(
    coordinates: torch.Tensor,
    system: AllAtomSystem,
    atom_i: int,
    atom_j: int,
) -> torch.Tensor:
    return _minimum_image(
        coordinates[0, atom_i] - coordinates[0, atom_j],
        system,
    )


def _project_constraints_strict(
    system: AllAtomSystem,
    coordinates: torch.Tensor,
    parameters: ReferenceForceFieldV2Parameters,
    config: ReferenceConstraintStationarityConfig,
) -> _ProjectionResult:
    projected = coordinates.detach().clone()
    degrees = [0] * system.atom_count
    for constraint in parameters.constraints:
        degrees[constraint.atom_i] += 1
        degrees[constraint.atom_j] += 1
    relaxation_degree = float(max(degrees, default=1))
    maximum_residual = math.inf
    for sweep in range(config.projection_max_sweeps + 1):
        residuals: list[float] = []
        degenerate = False
        for constraint in parameters.constraints:
            vector = _constraint_vector(
                projected,
                system,
                constraint.atom_i,
                constraint.atom_j,
            )
            distance = float(torch.linalg.vector_norm(vector).item())
            if distance <= 1.0e-12:
                residuals.append(
                    abs(distance - constraint.target_distance_angstrom)
                )
                degenerate = True
                break
            residuals.append(abs(distance - constraint.target_distance_angstrom))
        if degenerate:
            return _ProjectionResult(
                projected,
                max(residuals, default=0.0),
                sweep,
                False,
                "constraint_pair_has_zero_distance",
            )
        maximum_residual = max(residuals, default=0.0)
        if maximum_residual <= config.strict_projection_tolerance_angstrom:
            return _ProjectionResult(
                projected,
                maximum_residual,
                sweep,
                True,
                None,
            )
        if sweep == config.projection_max_sweeps:
            break
        updates = torch.zeros_like(projected)
        for constraint in parameters.constraints:
            vector = _constraint_vector(
                projected,
                system,
                constraint.atom_i,
                constraint.atom_j,
            )
            distance = float(torch.linalg.vector_norm(vector).item())
            residual = distance - constraint.target_distance_angstrom
            correction = max(
                -config.projection_max_pair_correction_angstrom,
                min(config.projection_max_pair_correction_angstrom, residual),
            )
            direction = vector / distance
            updates[0, constraint.atom_i] -= 0.5 * correction * direction
            updates[0, constraint.atom_j] += 0.5 * correction * direction
        projected += updates / relaxation_degree
    return _ProjectionResult(
        projected,
        maximum_residual,
        config.projection_max_sweeps,
        False,
        "strict_constraint_projection_budget_exhausted",
    )


def _project_forces_to_tangent(
    system: AllAtomSystem,
    coordinates: torch.Tensor,
    forces: torch.Tensor,
    parameters: ReferenceForceFieldV2Parameters,
    config: ReferenceConstraintStationarityConfig,
) -> tuple[torch.Tensor, float, float, int, bool]:
    projected = forces.detach().clone()
    degrees = [0] * system.atom_count
    for constraint in parameters.constraints:
        degrees[constraint.atom_i] += 1
        degrees[constraint.atom_j] += 1
    relaxation_degree = float(max(degrees, default=1))
    maximum_residual = math.inf
    for sweep in range(1, config.tangent_projection_max_sweeps + 1):
        updates = torch.zeros_like(projected)
        for constraint in parameters.constraints:
            vector = _constraint_vector(
                coordinates,
                system,
                constraint.atom_i,
                constraint.atom_j,
            )
            distance = float(torch.linalg.vector_norm(vector).item())
            if distance <= 1.0e-12:
                raise ReferenceConstraintStationarityError(
                    "constraint tangent is undefined at zero pair distance"
                )
            direction = vector / distance
            relative = torch.dot(
                projected[0, constraint.atom_i]
                - projected[0, constraint.atom_j],
                direction,
            )
            correction = 0.5 * relative * direction
            updates[0, constraint.atom_i] -= correction
            updates[0, constraint.atom_j] += correction
        projected += updates / relaxation_degree
        residuals = []
        for constraint in parameters.constraints:
            vector = _constraint_vector(
                coordinates,
                system,
                constraint.atom_i,
                constraint.atom_j,
            )
            direction = vector / torch.linalg.vector_norm(vector)
            residuals.append(
                abs(
                    float(
                        torch.dot(
                            projected[0, constraint.atom_i]
                            - projected[0, constraint.atom_j],
                            direction,
                        ).item()
                    )
                )
            )
        maximum_residual = max(residuals, default=0.0)
        if (
            maximum_residual
            <= config.tangent_projection_tolerance_kcal_per_mol_angstrom
        ):
            maximum = float(
                torch.linalg.vector_norm(projected[0], dim=-1).max().item()
            )
            return projected, maximum, maximum_residual, sweep, True
    maximum = float(torch.linalg.vector_norm(projected[0], dim=-1).max().item())
    return (
        projected,
        maximum,
        maximum_residual,
        config.tangent_projection_max_sweeps,
        False,
    )


def _evaluate(
    source_system: AllAtomSystem,
    coordinates: torch.Tensor,
    parameters: ReferenceForceFieldV2Parameters,
    solvation_parameters: FixedBornPolarSolvationParameters | None,
    config: ReferenceConstraintStationarityConfig,
    *,
    operation: str,
) -> _EvaluationResult:
    state = source_system.with_coordinates(coordinates, operation=operation)
    neighbors = build_compact_radius_graph(
        state.coordinates,
        RadiusGraphConfig(
            cutoff_angstrom=parameters.base_parameters.cutoff_angstrom,
            max_neighbors=config.max_neighbors,
            max_atoms_per_cell=config.max_atoms_per_cell,
        ),
        cell=state.cell,
    )
    if solvation_parameters is None:
        evaluated = evaluate_reference_force_field_v2(state, neighbors, parameters)
    else:
        evaluated = evaluate_reference_force_field_v2_with_fixed_born(
            state,
            neighbors,
            parameters,
            solvation_parameters,
        )
    energy = float(evaluated.term.energy[0].item())
    forces = evaluated.term.forces.detach().clone()
    if not math.isfinite(energy) or not bool(torch.isfinite(forces).all().item()):
        raise FloatingPointError("stationarity evaluation produced non-finite values")
    tangent, maximum, residual, sweeps, converged = _project_forces_to_tangent(
        source_system,
        coordinates,
        forces,
        parameters,
        config,
    )
    if not converged:
        raise ReferenceConstraintStationarityError(
            "constraint tangent projection exhausted its budget"
        )
    return _EvaluationResult(
        energy,
        tangent,
        maximum,
        residual,
        sweeps,
    )


def _validate_source(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldV2Parameters,
    solvation_parameters: FixedBornPolarSolvationParameters | None,
) -> None:
    if not isinstance(system, AllAtomSystem):
        raise ReferenceConstraintStationarityError(
            "system must be an AllAtomSystem"
        )
    if not isinstance(parameters, ReferenceForceFieldV2Parameters):
        raise ReferenceConstraintStationarityError(
            "parameters must be ReferenceForceFieldV2Parameters"
        )
    if solvation_parameters is not None and not isinstance(
        solvation_parameters,
        FixedBornPolarSolvationParameters,
    ):
        raise ReferenceConstraintStationarityError(
            "solvation_parameters must be FixedBornPolarSolvationParameters or null"
        )
    if system.coordinates.device.type != "cpu" or system.coordinates.dtype != torch.float64:
        raise ReferenceConstraintStationarityError(
            "stationarity candidate requires CPU float64 coordinates"
        )
    if system.model_count != 1:
        raise ReferenceConstraintStationarityError(
            "stationarity candidate requires exactly one model"
        )
    if tuple(system.coordinates.shape) != (1, system.atom_count, 3):
        raise ReferenceConstraintStationarityError(
            "system identity and coordinate shape mismatch"
        )
    if not bool(torch.isfinite(system.coordinates).all().item()):
        raise ReferenceConstraintStationarityError(
            "stationarity coordinates must be finite"
        )
    if not parameters.constraints:
        raise ReferenceConstraintStationarityError(
            "stationarity candidate requires at least one distance constraint"
        )


def _make_observation(
    *,
    attempt_index: int,
    iteration: int,
    trial: int,
    outcome: str,
    raw_coordinates: torch.Tensor,
    coordinates: torch.Tensor,
    step: float,
    energy: float | None,
    best_energy: float,
    tangent_force: float | None,
    constraint_residual: float,
    constraint_force_residual: float | None,
    projection_sweeps: int,
    tangent_projection_sweeps: int | None,
    directional_derivative: float | None,
    armijo_limit: float | None,
    failure_code: str | None = None,
) -> ReferenceConstraintStationarityObservation:
    if outcome == "initial":
        phase = "initial"
    elif outcome == "accepted_armijo":
        phase = "armijo_descent"
    elif outcome == "accepted_stationarity_polish":
        phase = "stationarity_polish"
    else:
        phase = "trial_rejection"
    return ReferenceConstraintStationarityObservation(
        attempt_index=attempt_index,
        iteration=iteration,
        trial=trial,
        outcome=outcome,
        phase=phase,
        raw_coordinates_sha256=_coordinate_digest(raw_coordinates),
        coordinates_angstrom_hex=_coordinate_hex_rows(coordinates),
        coordinates_sha256=_coordinate_digest(coordinates),
        step_size_angstrom2_mol_per_kcal=step,
        energy_kcal_per_mol=energy,
        energy_above_best_kcal_per_mol=(
            None if energy is None else max(0.0, energy - best_energy)
        ),
        max_tangent_force_kcal_per_mol_angstrom=tangent_force,
        max_constraint_residual_angstrom=constraint_residual,
        max_constraint_force_residual_kcal_per_mol_angstrom=(
            constraint_force_residual
        ),
        projection_sweeps=projection_sweeps,
        tangent_projection_sweeps=tangent_projection_sweeps,
        directional_derivative_kcal_per_mol=directional_derivative,
        armijo_limit_kcal_per_mol=armijo_limit,
        failure_code=failure_code,
    )


def _build_checkpoint(
    *,
    system: AllAtomSystem,
    parameters: ReferenceForceFieldV2Parameters,
    solvation_parameters: FixedBornPolarSolvationParameters | None,
    config: ReferenceConstraintStationarityConfig,
    coordinates: torch.Tensor,
    accepted_iterations: int,
    rejected_trials: int,
    energy_evaluation_count: int,
    current_energy: float,
    best_energy: float,
    current_tangent_force: float,
    current_constraint_residual: float,
    observations: list[ReferenceConstraintStationarityObservation],
) -> ReferenceConstraintStationarityCheckpoint:
    return ReferenceConstraintStationarityCheckpoint(
        source_system_sha256=canonical_system_sha256(system),
        topology_sha256=canonical_topology_sha256(system),
        parameter_fingerprint_sha256=parameters.fingerprint_sha256,
        solvation_parameter_fingerprint_sha256=(
            None
            if solvation_parameters is None
            else solvation_parameters.fingerprint_sha256
        ),
        config_fingerprint_sha256=config.fingerprint_sha256,
        accepted_iterations=accepted_iterations,
        rejected_trials=rejected_trials,
        energy_evaluation_count=energy_evaluation_count,
        current_energy_kcal_per_mol=current_energy,
        best_energy_kcal_per_mol=best_energy,
        current_max_tangent_force_kcal_per_mol_angstrom=current_tangent_force,
        current_max_constraint_residual_angstrom=current_constraint_residual,
        coordinates_angstrom_hex=_coordinate_hex_rows(coordinates),
        coordinates_sha256=_coordinate_digest(coordinates),
        observations=tuple(observations),
    )


@dataclass(frozen=True, slots=True)
class ReferenceConstraintStationarityResult:
    """Bounded candidate result retaining its complete coordinate/failure trace."""

    status: str
    failure_code: str | None
    system: AllAtomSystem
    config_fingerprint_sha256: str
    initial_energy_kcal_per_mol: float
    final_energy_kcal_per_mol: float
    best_energy_kcal_per_mol: float
    initial_max_tangent_force_kcal_per_mol_angstrom: float
    final_max_tangent_force_kcal_per_mol_angstrom: float
    final_max_constraint_residual_angstrom: float
    accepted_iterations: int
    accepted_armijo_iterations: int
    accepted_stationarity_polish_iterations: int
    rejected_trials: int
    energy_evaluation_count: int
    checkpoint: ReferenceConstraintStationarityCheckpoint
    scientific_blockers: tuple[str, ...] = (
        REFERENCE_CONSTRAINT_STATIONARITY_SCIENTIFIC_BLOCKERS
    )
    schema_id: str = REFERENCE_CONSTRAINT_STATIONARITY_RESULT_SCHEMA_ID

    @property
    def converged(self) -> bool:
        return self.status == "converged"

    @property
    def observations(self) -> tuple[ReferenceConstraintStationarityObservation, ...]:
        return self.checkpoint.observations

    def projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_CONSTRAINT_STATIONARITY_ALGORITHM_ID,
            "status": self.status,
            "failure_code": self.failure_code,
            "converged": self.converged,
            "final_system_sha256": canonical_system_sha256(self.system),
            "final_coordinates_sha256": _coordinate_digest(self.system.coordinates),
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "initial_energy_kcal_per_mol": self.initial_energy_kcal_per_mol,
            "final_energy_kcal_per_mol": self.final_energy_kcal_per_mol,
            "best_energy_kcal_per_mol": self.best_energy_kcal_per_mol,
            "final_energy_above_best_kcal_per_mol": max(
                0.0,
                self.final_energy_kcal_per_mol - self.best_energy_kcal_per_mol,
            ),
            "initial_max_tangent_force_kcal_per_mol_angstrom": (
                self.initial_max_tangent_force_kcal_per_mol_angstrom
            ),
            "final_max_tangent_force_kcal_per_mol_angstrom": (
                self.final_max_tangent_force_kcal_per_mol_angstrom
            ),
            "final_max_constraint_residual_angstrom": (
                self.final_max_constraint_residual_angstrom
            ),
            "accepted_iterations": self.accepted_iterations,
            "accepted_armijo_iterations": self.accepted_armijo_iterations,
            "accepted_stationarity_polish_iterations": (
                self.accepted_stationarity_polish_iterations
            ),
            "rejected_trials": self.rejected_trials,
            "energy_evaluation_count": self.energy_evaluation_count,
            "coordinate_trace": [
                {
                    "attempt_index": row.attempt_index,
                    "iteration": row.iteration,
                    "trial": row.trial,
                    "outcome": row.outcome,
                    "coordinates_angstrom_hex": [
                        list(coordinate) for coordinate in row.coordinates_angstrom_hex
                    ],
                    "coordinates_sha256": row.coordinates_sha256,
                }
                for row in self.observations
            ],
            "energy_trace_kcal_per_mol": [
                row.energy_kcal_per_mol for row in self.observations
            ],
            "all_observations": [row.to_dict() for row in self.observations],
            "checkpoint": self.checkpoint.to_dict(),
            "scientifically_validated": False,
            "claim_safe": False,
            "scientific_blockers": list(self.scientific_blockers),
        }

    @property
    def result_sha256(self) -> str:
        return _sha256(self.projection())

    def to_dict(self) -> dict[str, object]:
        return {**self.projection(), "result_sha256": self.result_sha256}


def minimize_reference_constraint_stationarity(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldV2Parameters,
    config: ReferenceConstraintStationarityConfig | None = None,
    *,
    solvation_parameters: FixedBornPolarSolvationParameters | None = None,
    pause_after_accepted_iterations: int | None = None,
    checkpoint: ReferenceConstraintStationarityCheckpoint
    | Mapping[str, object]
    | None = None,
) -> ReferenceConstraintStationarityResult:
    """Run strict projected descent with a bounded stationarity-polish phase."""

    config = ReferenceConstraintStationarityConfig() if config is None else config
    if not isinstance(config, ReferenceConstraintStationarityConfig):
        raise ReferenceConstraintStationarityError(
            "config must be ReferenceConstraintStationarityConfig"
        )
    _validate_source(system, parameters, solvation_parameters)
    source_sha256 = canonical_system_sha256(system)
    topology_sha256 = canonical_topology_sha256(system)
    solvation_fingerprint = (
        None
        if solvation_parameters is None
        else solvation_parameters.fingerprint_sha256
    )

    checkpoint_row = (
        None
        if checkpoint is None
        else require_reference_constraint_stationarity_checkpoint_document(checkpoint)
    )
    if checkpoint_row is None:
        initial_projection = _project_constraints_strict(
            system,
            system.coordinates,
            parameters,
            config,
        )
        if not initial_projection.converged:
            raise ReferenceConstraintStationarityError(
                "initial strict constraint projection failed: "
                f"{initial_projection.failure_code}"
            )
        coordinates = initial_projection.coordinates
        try:
            evaluated = _evaluate(
                system,
                coordinates,
                parameters,
                solvation_parameters,
                config,
                operation="reference_constraint_stationarity_initial",
            )
        except (
            ReferenceForceFieldV2ApplicabilityError,
            ReferenceFixedBornSolvationApplicabilityError,
            FloatingPointError,
        ) as exc:
            raise ReferenceConstraintStationarityError(
                f"initial stationarity state is not evaluable: {exc}"
            ) from exc
        current_energy = evaluated.energy_kcal_per_mol
        current_forces = evaluated.tangent_forces
        current_tangent_force = (
            evaluated.max_tangent_force_kcal_per_mol_angstrom
        )
        current_constraint_residual = initial_projection.max_residual_angstrom
        best_energy = current_energy
        observations = [
            _make_observation(
                attempt_index=0,
                iteration=0,
                trial=0,
                outcome="initial",
                raw_coordinates=system.coordinates,
                coordinates=coordinates,
                step=0.0,
                energy=current_energy,
                best_energy=best_energy,
                tangent_force=current_tangent_force,
                constraint_residual=current_constraint_residual,
                constraint_force_residual=(
                    evaluated.max_constraint_force_residual_kcal_per_mol_angstrom
                ),
                projection_sweeps=initial_projection.sweeps,
                tangent_projection_sweeps=evaluated.tangent_projection_sweeps,
                directional_derivative=None,
                armijo_limit=None,
            )
        ]
        accepted_iterations = 0
        rejected_trials = 0
        energy_evaluation_count = 1
        initial_energy = current_energy
        initial_tangent_force = current_tangent_force
    else:
        expected_identities = (
            (checkpoint_row.source_system_sha256, source_sha256, "source system"),
            (checkpoint_row.topology_sha256, topology_sha256, "topology"),
            (
                checkpoint_row.parameter_fingerprint_sha256,
                parameters.fingerprint_sha256,
                "parameter",
            ),
            (
                checkpoint_row.config_fingerprint_sha256,
                config.fingerprint_sha256,
                "config",
            ),
        )
        for observed, expected, name in expected_identities:
            if observed != expected:
                raise ReferenceConstraintStationarityError(
                    f"checkpoint {name} identity mismatch"
                )
        if (
            checkpoint_row.solvation_parameter_fingerprint_sha256
            != solvation_fingerprint
        ):
            raise ReferenceConstraintStationarityError(
                "checkpoint solvation parameter identity mismatch"
            )
        replay = minimize_reference_constraint_stationarity(
            system,
            parameters,
            config,
            solvation_parameters=solvation_parameters,
            pause_after_accepted_iterations=checkpoint_row.accepted_iterations,
        )
        if replay.checkpoint.to_dict() != checkpoint_row.to_dict():
            raise ReferenceConstraintStationarityError(
                "checkpoint does not replay exactly from its source state"
            )
        coordinates = checkpoint_row.coordinates()
        verification_projection = _project_constraints_strict(
            system,
            coordinates,
            parameters,
            config,
        )
        if not verification_projection.converged or not torch.equal(
            verification_projection.coordinates,
            coordinates,
        ):
            raise ReferenceConstraintStationarityError(
                "checkpoint coordinates are not idempotent on the strict constraint surface"
            )
        evaluated = _evaluate(
            system,
            coordinates,
            parameters,
            solvation_parameters,
            config,
            operation="reference_constraint_stationarity_restart_verification",
        )
        if not _same_float(
            evaluated.energy_kcal_per_mol,
            checkpoint_row.current_energy_kcal_per_mol,
        ) or not _same_float(
            evaluated.max_tangent_force_kcal_per_mol_angstrom,
            checkpoint_row.current_max_tangent_force_kcal_per_mol_angstrom,
        ):
            raise ReferenceConstraintStationarityError(
                "checkpoint state does not reproduce stored energy and tangent force"
            )
        current_energy = evaluated.energy_kcal_per_mol
        current_forces = evaluated.tangent_forces
        current_tangent_force = (
            evaluated.max_tangent_force_kcal_per_mol_angstrom
        )
        current_constraint_residual = (
            checkpoint_row.current_max_constraint_residual_angstrom
        )
        best_energy = checkpoint_row.best_energy_kcal_per_mol
        observations = list(checkpoint_row.observations)
        accepted_iterations = checkpoint_row.accepted_iterations
        rejected_trials = checkpoint_row.rejected_trials
        energy_evaluation_count = checkpoint_row.energy_evaluation_count
        initial_row = observations[0]
        assert initial_row.energy_kcal_per_mol is not None
        assert initial_row.max_tangent_force_kcal_per_mol_angstrom is not None
        initial_energy = initial_row.energy_kcal_per_mol
        initial_tangent_force = (
            initial_row.max_tangent_force_kcal_per_mol_angstrom
        )

    pause_at: int | None = None
    if pause_after_accepted_iterations is not None:
        pause_at = _exact_int(
            pause_after_accepted_iterations,
            name="pause_after_accepted_iterations",
            minimum=0,
            maximum=config.max_iterations,
        )
        if pause_at < accepted_iterations:
            raise ReferenceConstraintStationarityError(
                "pause_after_accepted_iterations precedes checkpoint progress"
            )

    status = "max_iterations_reached"
    failure_code: str | None = "maximum_iteration_budget_exhausted"
    while accepted_iterations < config.max_iterations:
        if (
            current_tangent_force
            <= config.tangent_force_tolerance_kcal_per_mol_angstrom
            and current_constraint_residual
            <= config.constraint_acceptance_tolerance_angstrom
        ):
            status = "converged"
            failure_code = None
            break
        if pause_at is not None and accepted_iterations >= pause_at:
            status = "checkpointed"
            failure_code = None
            break
        iteration = accepted_iterations + 1
        step = config.initial_step_size_angstrom2_mol_per_kcal
        direction = current_forces.clone()
        raw_max_displacement = step * current_tangent_force
        if raw_max_displacement > config.maximum_atom_displacement_angstrom:
            direction.mul_(
                config.maximum_atom_displacement_angstrom / raw_max_displacement
            )
        accepted = False
        for trial in range(config.max_backtracks + 1):
            raw_coordinates = coordinates + step * direction
            projected = _project_constraints_strict(
                system,
                raw_coordinates,
                parameters,
                config,
            )
            attempt_index = len(observations)
            if not projected.converged:
                rejected_trials += 1
                observations.append(
                    _make_observation(
                        attempt_index=attempt_index,
                        iteration=iteration,
                        trial=trial,
                        outcome="rejected_constraint_projection",
                        raw_coordinates=raw_coordinates,
                        coordinates=projected.coordinates,
                        step=step,
                        energy=None,
                        best_energy=best_energy,
                        tangent_force=None,
                        constraint_residual=projected.max_residual_angstrom,
                        constraint_force_residual=None,
                        projection_sweeps=projected.sweeps,
                        tangent_projection_sweeps=None,
                        directional_derivative=None,
                        armijo_limit=None,
                        failure_code=(
                            projected.failure_code
                            or "strict_constraint_projection_failed"
                        ),
                    )
                )
                step *= config.backtrack_factor
                continue
            trial_coordinates = projected.coordinates
            maximum_displacement = float(
                torch.linalg.vector_norm(
                    trial_coordinates[0] - coordinates[0],
                    dim=-1,
                ).max()
            )
            if (
                maximum_displacement
                > config.maximum_atom_displacement_angstrom + 1.0e-12
            ):
                rejected_trials += 1
                observations.append(
                    _make_observation(
                        attempt_index=attempt_index,
                        iteration=iteration,
                        trial=trial,
                        outcome="rejected_displacement",
                        raw_coordinates=raw_coordinates,
                        coordinates=trial_coordinates,
                        step=step,
                        energy=None,
                        best_energy=best_energy,
                        tangent_force=None,
                        constraint_residual=projected.max_residual_angstrom,
                        constraint_force_residual=None,
                        projection_sweeps=projected.sweeps,
                        tangent_projection_sweeps=None,
                        directional_derivative=None,
                        armijo_limit=None,
                        failure_code="projected_displacement_bound_exceeded",
                    )
                )
                step *= config.backtrack_factor
                continue
            try:
                trial_evaluated = _evaluate(
                    system,
                    trial_coordinates,
                    parameters,
                    solvation_parameters,
                    config,
                    operation=(
                        f"reference_constraint_stationarity_{iteration}_{trial}"
                    ),
                )
            except ReferenceConstraintStationarityError:
                rejected_trials += 1
                observations.append(
                    _make_observation(
                        attempt_index=attempt_index,
                        iteration=iteration,
                        trial=trial,
                        outcome="rejected_tangent_projection",
                        raw_coordinates=raw_coordinates,
                        coordinates=trial_coordinates,
                        step=step,
                        energy=None,
                        best_energy=best_energy,
                        tangent_force=None,
                        constraint_residual=projected.max_residual_angstrom,
                        constraint_force_residual=None,
                        projection_sweeps=projected.sweeps,
                        tangent_projection_sweeps=None,
                        directional_derivative=None,
                        armijo_limit=None,
                        failure_code="tangent_projection_budget_exhausted",
                    )
                )
                step *= config.backtrack_factor
                continue
            except (
                ReferenceForceFieldV2ApplicabilityError,
                ReferenceFixedBornSolvationApplicabilityError,
                FloatingPointError,
            ) as exc:
                rejected_trials += 1
                observations.append(
                    _make_observation(
                        attempt_index=attempt_index,
                        iteration=iteration,
                        trial=trial,
                        outcome="rejected_evaluation",
                        raw_coordinates=raw_coordinates,
                        coordinates=trial_coordinates,
                        step=step,
                        energy=None,
                        best_energy=best_energy,
                        tangent_force=None,
                        constraint_residual=projected.max_residual_angstrom,
                        constraint_force_residual=None,
                        projection_sweeps=projected.sweeps,
                        tangent_projection_sweeps=None,
                        directional_derivative=None,
                        armijo_limit=None,
                        failure_code=(
                            "reference_evaluation_failed:"
                            + str(exc).split(":", 1)[0]
                        ),
                    )
                )
                step *= config.backtrack_factor
                continue
            energy_evaluation_count += 1
            displacement = trial_coordinates - coordinates
            directional_derivative = -float(
                (current_forces * displacement).sum().item()
            )
            armijo_limit = (
                current_energy + config.armijo_constant * directional_derivative
            )
            armijo_accepted = (
                directional_derivative < 0.0
                and trial_evaluated.energy_kcal_per_mol <= armijo_limit
            )
            stationarity_accepted = (
                not armijo_accepted
                and trial_evaluated.max_tangent_force_kcal_per_mol_angstrom
                < current_tangent_force
                and trial_evaluated.energy_kcal_per_mol
                <= (
                    best_energy
                    + config.stationarity_energy_relaxation_kcal_per_mol
                )
            )
            if not armijo_accepted and not stationarity_accepted:
                rejected_trials += 1
                observations.append(
                    _make_observation(
                        attempt_index=attempt_index,
                        iteration=iteration,
                        trial=trial,
                        outcome="rejected_acceptance",
                        raw_coordinates=raw_coordinates,
                        coordinates=trial_coordinates,
                        step=step,
                        energy=trial_evaluated.energy_kcal_per_mol,
                        best_energy=best_energy,
                        tangent_force=(
                            trial_evaluated.max_tangent_force_kcal_per_mol_angstrom
                        ),
                        constraint_residual=projected.max_residual_angstrom,
                        constraint_force_residual=(
                            trial_evaluated.max_constraint_force_residual_kcal_per_mol_angstrom
                        ),
                        projection_sweeps=projected.sweeps,
                        tangent_projection_sweeps=(
                            trial_evaluated.tangent_projection_sweeps
                        ),
                        directional_derivative=directional_derivative,
                        armijo_limit=armijo_limit,
                        failure_code=(
                            "armijo_and_stationarity_polish_not_satisfied"
                        ),
                    )
                )
                step *= config.backtrack_factor
                continue
            outcome = (
                "accepted_armijo"
                if armijo_accepted
                else "accepted_stationarity_polish"
            )
            updated_best_energy = min(
                best_energy,
                trial_evaluated.energy_kcal_per_mol,
            )
            observations.append(
                _make_observation(
                    attempt_index=attempt_index,
                    iteration=iteration,
                    trial=trial,
                    outcome=outcome,
                    raw_coordinates=raw_coordinates,
                    coordinates=trial_coordinates,
                    step=step,
                    energy=trial_evaluated.energy_kcal_per_mol,
                    best_energy=updated_best_energy,
                    tangent_force=(
                        trial_evaluated.max_tangent_force_kcal_per_mol_angstrom
                    ),
                    constraint_residual=projected.max_residual_angstrom,
                    constraint_force_residual=(
                        trial_evaluated.max_constraint_force_residual_kcal_per_mol_angstrom
                    ),
                    projection_sweeps=projected.sweeps,
                    tangent_projection_sweeps=(
                        trial_evaluated.tangent_projection_sweeps
                    ),
                    directional_derivative=directional_derivative,
                    armijo_limit=armijo_limit,
                )
            )
            coordinates = trial_coordinates
            current_energy = trial_evaluated.energy_kcal_per_mol
            current_forces = trial_evaluated.tangent_forces
            current_tangent_force = (
                trial_evaluated.max_tangent_force_kcal_per_mol_angstrom
            )
            current_constraint_residual = projected.max_residual_angstrom
            best_energy = updated_best_energy
            accepted_iterations += 1
            accepted = True
            break
        if not accepted:
            status = "line_search_failed"
            failure_code = "bounded_stationarity_backtracking_exhausted"
            break
    else:
        status = "max_iterations_reached"
        failure_code = "maximum_iteration_budget_exhausted"

    if (
        current_tangent_force
        <= config.tangent_force_tolerance_kcal_per_mol_angstrom
        and current_constraint_residual
        <= config.constraint_acceptance_tolerance_angstrom
    ):
        status = "converged"
        failure_code = None

    checkpoint_result = _build_checkpoint(
        system=system,
        parameters=parameters,
        solvation_parameters=solvation_parameters,
        config=config,
        coordinates=coordinates,
        accepted_iterations=accepted_iterations,
        rejected_trials=rejected_trials,
        energy_evaluation_count=energy_evaluation_count,
        current_energy=current_energy,
        best_energy=best_energy,
        current_tangent_force=current_tangent_force,
        current_constraint_residual=current_constraint_residual,
        observations=observations,
    )
    final_system = system.with_coordinates(
        coordinates,
        operation="reference_constraint_stationarity_candidate_final",
        operation_evidence_sha256=checkpoint_result.checkpoint_sha256,
    )
    armijo_count = sum(
        row.outcome == "accepted_armijo" for row in observations
    )
    polish_count = sum(
        row.outcome == "accepted_stationarity_polish" for row in observations
    )
    return ReferenceConstraintStationarityResult(
        status=status,
        failure_code=failure_code,
        system=final_system,
        config_fingerprint_sha256=config.fingerprint_sha256,
        initial_energy_kcal_per_mol=initial_energy,
        final_energy_kcal_per_mol=current_energy,
        best_energy_kcal_per_mol=best_energy,
        initial_max_tangent_force_kcal_per_mol_angstrom=initial_tangent_force,
        final_max_tangent_force_kcal_per_mol_angstrom=current_tangent_force,
        final_max_constraint_residual_angstrom=current_constraint_residual,
        accepted_iterations=accepted_iterations,
        accepted_armijo_iterations=armijo_count,
        accepted_stationarity_polish_iterations=polish_count,
        rejected_trials=rejected_trials,
        energy_evaluation_count=energy_evaluation_count,
        checkpoint=checkpoint_result,
    )


def reference_constraint_stationarity_default_configuration_document() -> dict[str, object]:
    """Return the preregistered, result-free candidate configuration."""

    config = ReferenceConstraintStationarityConfig()
    if (
        config.fingerprint_sha256
        != REFERENCE_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256
    ):
        raise ReferenceConstraintStationarityError(
            "default stationarity configuration drifted from its preregistration"
        )
    return {
        "schema_id": (
            "betelgeuze.engine_v2_reference_constraint_stationarity_candidate_config/"
            "1.0.0"
        ),
        "configuration": config.to_dict(),
        "configuration_sha256": config.fingerprint_sha256,
        "eligible_frozen_case_ids": [
            "v2_constrained_angle_energy_decrease",
            "v2_constrained_checkpoint_restart_exact",
            "v2_fixed_born_constrained_energy_decrease",
            "v2_fixed_born_checkpoint_restart_exact",
        ],
        "retained_public_thresholds": {
            "constraint_max_abs_residual_angstrom": 1.0e-10,
            "absolute_tangent_force_max_kcal_per_mol_angstrom": 1.0e-8,
        },
        "frozen_receipts_modified": False,
        "native_openmm_lbfgs_claim": "unchanged_rejected_6_of_8",
        "validation_receipt": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "scientific_blockers": list(
            REFERENCE_CONSTRAINT_STATIONARITY_SCIENTIFIC_BLOCKERS
        ),
    }


__all__ = [
    "REFERENCE_CONSTRAINT_STATIONARITY_ALGORITHM_ID",
    "REFERENCE_CONSTRAINT_STATIONARITY_CHECKPOINT_SCHEMA_ID",
    "REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SCHEMA_ID",
    "REFERENCE_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256",
    "REFERENCE_CONSTRAINT_STATIONARITY_RESULT_SCHEMA_ID",
    "REFERENCE_CONSTRAINT_STATIONARITY_SCIENTIFIC_BLOCKERS",
    "ReferenceConstraintStationarityCheckpoint",
    "ReferenceConstraintStationarityConfig",
    "ReferenceConstraintStationarityError",
    "ReferenceConstraintStationarityObservation",
    "ReferenceConstraintStationarityResult",
    "minimize_reference_constraint_stationarity",
    "reference_constraint_stationarity_default_configuration_document",
    "require_reference_constraint_stationarity_checkpoint_document",
]
