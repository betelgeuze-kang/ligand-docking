"""Failure-inclusive numerical drift analysis for the CPU reference NVE path.

The analyzer requires a fresh trajectory with every evaluated frame retained
and an independently executed pause/resume trajectory ending at the same step.
It reports energy, momentum, kinetic-temperature, and current constraint
residual traces plus one fixed row for every predeclared acceptance metric.

Passing these caller-bound numerical thresholds is implementation evidence
only.  It is not an independent integrator comparison, a two-host result, a
force-field validation, an ensemble validation, or a product claim.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
from typing import Mapping

import torch

from .reference_nve import ReferenceNVEFrame, ReferenceNVEResult
from .reference_shake_rattle import (
    ReferenceSHAKERATTLEError,
    observe_reference_position_constraints,
    observe_reference_velocity_constraints,
)


REFERENCE_NVE_DRIFT_ALGORITHM_ID = (
    "cpu_float64_all_step_nve_drift_and_exact_restart_analysis/1.0.0"
)
REFERENCE_NVE_DRIFT_ACCEPTANCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_nve_drift_acceptance/1.0.0"
)
REFERENCE_NVE_DRIFT_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_nve_drift_observation/1.0.0"
)
REFERENCE_NVE_DRIFT_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_nve_drift_metric/1.0.0"
)
REFERENCE_NVE_RESTART_EQUALITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_nve_restart_equality/1.0.0"
)
REFERENCE_NVE_DRIFT_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_nve_drift_result/1.0.0"
)
MOLAR_GAS_CONSTANT_KCAL_PER_MOL_K = 0.0019872042586408316
REFERENCE_NVE_DRIFT_MAX_FRAMES = 10_001
REFERENCE_NVE_DRIFT_MAX_FRAME_ATOM_PRODUCTS = 2_000_000
REFERENCE_NVE_DRIFT_METRIC_IDS = (
    "max_abs_energy_drift_kcal_per_mol_per_atom",
    "rms_energy_drift_kcal_per_mol_per_atom",
    "max_abs_relative_energy_drift",
    "abs_energy_drift_slope_kcal_per_mol_per_ps_per_atom",
    "max_linear_momentum_drift_da_angstrom_per_ps",
    "rms_linear_momentum_drift_da_angstrom_per_ps",
    "max_position_constraint_residual_angstrom",
    "max_velocity_constraint_residual_angstrom_per_ps",
    "exact_checkpoint_restart_equality",
)
REFERENCE_NVE_DRIFT_SCIENTIFIC_BLOCKERS = (
    "caller_supplied_nve_drift_acceptance_thresholds_not_independently_reviewed",
    "synthetic_runtime_diagnostics_are_not_independent_scientific_validation",
    "independent_external_integrator_trajectory_comparison_missing",
    "two_cpu_host_reproduction_missing",
    "cpu_gpu_parity_evidence_missing",
    "force_field_and_parameter_accuracy_not_scientifically_validated",
    "public_nve_drift_result_receipt_missing",
    "nvt_npt_ensemble_statistics_not_independently_reviewed",
)


class ReferenceNVEDriftError(ValueError):
    """The drift input, acceptance policy, or trace failed closed."""


def _finite_float(
    value: object,
    *,
    name: str,
    nonnegative: bool = False,
    positive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceNVEDriftError(f"{name} must be a finite real number")
    number = float(value)
    if not math.isfinite(number):
        raise ReferenceNVEDriftError(f"{name} must be finite")
    if nonnegative and number < 0.0:
        raise ReferenceNVEDriftError(f"{name} must be non-negative")
    if positive and number <= 0.0:
        raise ReferenceNVEDriftError(f"{name} must be positive")
    return number


def _exact_int(value: object, *, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReferenceNVEDriftError(f"{name} must be an integer")
    integer = int(value)
    if integer < minimum:
        raise ReferenceNVEDriftError(f"{name} must be at least {minimum}")
    return integer


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ReferenceNVEDriftError(f"{name} must be a SHA-256 digest")
    digest = value.strip().lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ReferenceNVEDriftError(f"{name} must be a lowercase SHA-256 digest")
    return digest


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ReferenceNVEDriftError(
            "NVE drift payload is not canonical JSON"
        ) from exc


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_float_hex(value: object, *, name: str) -> float:
    if not isinstance(value, str):
        raise ReferenceNVEDriftError(f"{name} must be a hexadecimal float")
    try:
        number = float.fromhex(value)
    except ValueError:
        raise ReferenceNVEDriftError(f"{name} is not a hexadecimal float") from None
    if not math.isfinite(number) or number.hex() != value:
        raise ReferenceNVEDriftError(f"{name} is not canonical finite binary64")
    return number


@dataclass(frozen=True)
class ReferenceNVEDriftAcceptanceConfig:
    """Caller-bound thresholds fixed before a drift trajectory is interpreted."""

    max_abs_energy_drift_kcal_per_mol_per_atom: float
    max_rms_energy_drift_kcal_per_mol_per_atom: float
    max_abs_relative_energy_drift: float
    max_abs_energy_drift_slope_kcal_per_mol_per_ps_per_atom: float
    max_linear_momentum_drift_da_angstrom_per_ps: float
    max_rms_linear_momentum_drift_da_angstrom_per_ps: float
    max_position_constraint_residual_angstrom: float
    max_velocity_constraint_residual_angstrom_per_ps: float
    relative_energy_floor_kcal_per_mol: float = 1.0e-12
    schema_id: str = REFERENCE_NVE_DRIFT_ACCEPTANCE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_NVE_DRIFT_ACCEPTANCE_SCHEMA_ID:
            raise ReferenceNVEDriftError(
                "unsupported NVE drift acceptance schema"
            )
        for name in (
            "max_abs_energy_drift_kcal_per_mol_per_atom",
            "max_rms_energy_drift_kcal_per_mol_per_atom",
            "max_abs_relative_energy_drift",
            "max_abs_energy_drift_slope_kcal_per_mol_per_ps_per_atom",
            "max_linear_momentum_drift_da_angstrom_per_ps",
            "max_rms_linear_momentum_drift_da_angstrom_per_ps",
            "max_position_constraint_residual_angstrom",
            "max_velocity_constraint_residual_angstrom_per_ps",
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(
                    getattr(self, name),
                    name=name,
                    nonnegative=True,
                ),
            )
        object.__setattr__(
            self,
            "relative_energy_floor_kcal_per_mol",
            _finite_float(
                self.relative_energy_floor_kcal_per_mol,
                name="relative_energy_floor_kcal_per_mol",
                positive=True,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_NVE_DRIFT_ALGORITHM_ID,
            "max_abs_energy_drift_kcal_per_mol_per_atom_hex": (
                self.max_abs_energy_drift_kcal_per_mol_per_atom.hex()
            ),
            "max_rms_energy_drift_kcal_per_mol_per_atom_hex": (
                self.max_rms_energy_drift_kcal_per_mol_per_atom.hex()
            ),
            "max_abs_relative_energy_drift_hex": (
                self.max_abs_relative_energy_drift.hex()
            ),
            "max_abs_energy_drift_slope_kcal_per_mol_per_ps_per_atom_hex": (
                self.max_abs_energy_drift_slope_kcal_per_mol_per_ps_per_atom.hex()
            ),
            "max_linear_momentum_drift_da_angstrom_per_ps_hex": (
                self.max_linear_momentum_drift_da_angstrom_per_ps.hex()
            ),
            "max_rms_linear_momentum_drift_da_angstrom_per_ps_hex": (
                self.max_rms_linear_momentum_drift_da_angstrom_per_ps.hex()
            ),
            "max_position_constraint_residual_angstrom_hex": (
                self.max_position_constraint_residual_angstrom.hex()
            ),
            "max_velocity_constraint_residual_angstrom_per_ps_hex": (
                self.max_velocity_constraint_residual_angstrom_per_ps.hex()
            ),
            "relative_energy_floor_kcal_per_mol_hex": (
                self.relative_energy_floor_kcal_per_mol.hex()
            ),
            "restart_policy": "exact_checkpoint_and_trajectory_chain_required",
            "trace_policy": "fresh_run_all_evaluated_frames_required",
        }

    @classmethod
    def from_dict(cls, value: object) -> "ReferenceNVEDriftAcceptanceConfig":
        expected = {
            "schema_id",
            "algorithm_id",
            "max_abs_energy_drift_kcal_per_mol_per_atom_hex",
            "max_rms_energy_drift_kcal_per_mol_per_atom_hex",
            "max_abs_relative_energy_drift_hex",
            "max_abs_energy_drift_slope_kcal_per_mol_per_ps_per_atom_hex",
            "max_linear_momentum_drift_da_angstrom_per_ps_hex",
            "max_rms_linear_momentum_drift_da_angstrom_per_ps_hex",
            "max_position_constraint_residual_angstrom_hex",
            "max_velocity_constraint_residual_angstrom_per_ps_hex",
            "relative_energy_floor_kcal_per_mol_hex",
            "restart_policy",
            "trace_policy",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ReferenceNVEDriftError(
                "NVE drift acceptance config payload is invalid"
            )
        if value["algorithm_id"] != REFERENCE_NVE_DRIFT_ALGORITHM_ID:
            raise ReferenceNVEDriftError("unsupported NVE drift algorithm")
        if value["restart_policy"] != (
            "exact_checkpoint_and_trajectory_chain_required"
        ):
            raise ReferenceNVEDriftError("unsupported NVE drift restart policy")
        if value["trace_policy"] != "fresh_run_all_evaluated_frames_required":
            raise ReferenceNVEDriftError("unsupported NVE drift trace policy")
        result = cls(
            max_abs_energy_drift_kcal_per_mol_per_atom=_require_float_hex(
                value["max_abs_energy_drift_kcal_per_mol_per_atom_hex"],
                name="maximum absolute energy drift per atom",
            ),
            max_rms_energy_drift_kcal_per_mol_per_atom=_require_float_hex(
                value["max_rms_energy_drift_kcal_per_mol_per_atom_hex"],
                name="maximum RMS energy drift per atom",
            ),
            max_abs_relative_energy_drift=_require_float_hex(
                value["max_abs_relative_energy_drift_hex"],
                name="maximum absolute relative energy drift",
            ),
            max_abs_energy_drift_slope_kcal_per_mol_per_ps_per_atom=(
                _require_float_hex(
                    value[
                        "max_abs_energy_drift_slope_kcal_per_mol_per_ps_per_atom_hex"
                    ],
                    name="maximum absolute energy drift slope",
                )
            ),
            max_linear_momentum_drift_da_angstrom_per_ps=_require_float_hex(
                value["max_linear_momentum_drift_da_angstrom_per_ps_hex"],
                name="maximum linear momentum drift",
            ),
            max_rms_linear_momentum_drift_da_angstrom_per_ps=(
                _require_float_hex(
                    value[
                        "max_rms_linear_momentum_drift_da_angstrom_per_ps_hex"
                    ],
                    name="maximum RMS linear momentum drift",
                )
            ),
            max_position_constraint_residual_angstrom=_require_float_hex(
                value["max_position_constraint_residual_angstrom_hex"],
                name="maximum position constraint residual",
            ),
            max_velocity_constraint_residual_angstrom_per_ps=_require_float_hex(
                value[
                    "max_velocity_constraint_residual_angstrom_per_ps_hex"
                ],
                name="maximum velocity constraint residual",
            ),
            relative_energy_floor_kcal_per_mol=_require_float_hex(
                value["relative_energy_floor_kcal_per_mol_hex"],
                name="relative energy floor",
            ),
            schema_id=str(value["schema_id"]),
        )
        if result.to_dict() != dict(value):
            raise ReferenceNVEDriftError(
                "NVE drift acceptance config is not canonical"
            )
        return result

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class ReferenceNVEDriftObservation:
    step: int
    time_ps: float
    potential_energy_kcal_per_mol: float
    kinetic_energy_kcal_per_mol: float
    total_energy_kcal_per_mol: float
    energy_drift_kcal_per_mol: float
    relative_energy_drift: float
    kinetic_temperature_k: float
    linear_momentum_da_angstrom_per_ps: tuple[float, float, float]
    linear_momentum_drift_norm_da_angstrom_per_ps: float
    max_position_constraint_residual_angstrom: float
    max_velocity_constraint_residual_angstrom_per_ps: float
    frame_sha256: str
    coordinate_data_sha256: str
    velocity_data_sha256: str
    schema_id: str = REFERENCE_NVE_DRIFT_OBSERVATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_NVE_DRIFT_OBSERVATION_SCHEMA_ID:
            raise ReferenceNVEDriftError(
                "unsupported NVE drift observation schema"
            )
        object.__setattr__(self, "step", _exact_int(self.step, name="step"))
        for name in (
            "time_ps",
            "potential_energy_kcal_per_mol",
            "kinetic_energy_kcal_per_mol",
            "total_energy_kcal_per_mol",
            "energy_drift_kcal_per_mol",
            "relative_energy_drift",
            "kinetic_temperature_k",
            "linear_momentum_drift_norm_da_angstrom_per_ps",
            "max_position_constraint_residual_angstrom",
            "max_velocity_constraint_residual_angstrom_per_ps",
        ):
            nonnegative = name in {
                "time_ps",
                "kinetic_energy_kcal_per_mol",
                "kinetic_temperature_k",
                "linear_momentum_drift_norm_da_angstrom_per_ps",
                "max_position_constraint_residual_angstrom",
                "max_velocity_constraint_residual_angstrom_per_ps",
            }
            object.__setattr__(
                self,
                name,
                _finite_float(
                    getattr(self, name),
                    name=name,
                    nonnegative=nonnegative,
                ),
            )
        momentum = tuple(self.linear_momentum_da_angstrom_per_ps)
        if len(momentum) != 3:
            raise ReferenceNVEDriftError("linear momentum must contain three values")
        object.__setattr__(
            self,
            "linear_momentum_da_angstrom_per_ps",
            tuple(
                _finite_float(value, name=f"linear momentum axis {axis}")
                for axis, value in enumerate(momentum)
            ),
        )
        for name in (
            "frame_sha256",
            "coordinate_data_sha256",
            "velocity_data_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if self.total_energy_kcal_per_mol.hex() != (
            self.potential_energy_kcal_per_mol
            + self.kinetic_energy_kcal_per_mol
        ).hex():
            raise ReferenceNVEDriftError(
                "observation total energy is inconsistent"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "step": self.step,
            "time_ps_hex": self.time_ps.hex(),
            "potential_energy_kcal_per_mol_hex": (
                self.potential_energy_kcal_per_mol.hex()
            ),
            "kinetic_energy_kcal_per_mol_hex": (
                self.kinetic_energy_kcal_per_mol.hex()
            ),
            "total_energy_kcal_per_mol_hex": self.total_energy_kcal_per_mol.hex(),
            "energy_drift_kcal_per_mol_hex": self.energy_drift_kcal_per_mol.hex(),
            "relative_energy_drift_hex": self.relative_energy_drift.hex(),
            "kinetic_temperature_k_hex": self.kinetic_temperature_k.hex(),
            "linear_momentum_da_angstrom_per_ps_hex": [
                value.hex() for value in self.linear_momentum_da_angstrom_per_ps
            ],
            "linear_momentum_drift_norm_da_angstrom_per_ps_hex": (
                self.linear_momentum_drift_norm_da_angstrom_per_ps.hex()
            ),
            "max_position_constraint_residual_angstrom_hex": (
                self.max_position_constraint_residual_angstrom.hex()
            ),
            "max_velocity_constraint_residual_angstrom_per_ps_hex": (
                self.max_velocity_constraint_residual_angstrom_per_ps.hex()
            ),
            "frame_sha256": self.frame_sha256,
            "coordinate_data_sha256": self.coordinate_data_sha256,
            "velocity_data_sha256": self.velocity_data_sha256,
        }


@dataclass(frozen=True)
class ReferenceNVEDriftMetric:
    metric_id: str
    observed: float
    threshold: float
    unit: str
    passed: bool
    schema_id: str = REFERENCE_NVE_DRIFT_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_NVE_DRIFT_METRIC_SCHEMA_ID:
            raise ReferenceNVEDriftError("unsupported NVE drift metric schema")
        metric_id = str(self.metric_id).strip()
        if metric_id not in REFERENCE_NVE_DRIFT_METRIC_IDS:
            raise ReferenceNVEDriftError("unsupported NVE drift metric ID")
        object.__setattr__(self, "metric_id", metric_id)
        object.__setattr__(
            self,
            "observed",
            _finite_float(self.observed, name="metric observed", nonnegative=True),
        )
        object.__setattr__(
            self,
            "threshold",
            _finite_float(self.threshold, name="metric threshold", nonnegative=True),
        )
        unit = str(self.unit).strip()
        if not unit:
            raise ReferenceNVEDriftError("metric unit must be non-empty")
        object.__setattr__(self, "unit", unit)
        if not isinstance(self.passed, bool):
            raise ReferenceNVEDriftError("metric passed must be boolean")
        expected = self.observed == 1.0 if metric_id == (
            "exact_checkpoint_restart_equality"
        ) else self.observed <= self.threshold
        if self.passed != expected:
            raise ReferenceNVEDriftError("metric pass disposition is inconsistent")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "metric_id": self.metric_id,
            "observed_hex": self.observed.hex(),
            "threshold_hex": self.threshold.hex(),
            "unit": self.unit,
            "comparison": (
                "exactly_one" if self.metric_id == (
                    "exact_checkpoint_restart_equality"
                ) else "less_than_or_equal"
            ),
            "passed": self.passed,
        }


@dataclass(frozen=True)
class ReferenceNVERestartEquality:
    same_end_step: bool
    same_source_and_runtime_provenance: bool
    same_coordinates: bool
    same_velocities: bool
    same_energy_bits: bool
    same_current_frame_sha256: bool
    same_trajectory_head_sha256: bool
    same_evaluated_frame_count: bool
    same_checkpoint_sha256: bool
    uninterrupted_checkpoint_sha256: str
    restarted_checkpoint_sha256: str
    schema_id: str = REFERENCE_NVE_RESTART_EQUALITY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_NVE_RESTART_EQUALITY_SCHEMA_ID:
            raise ReferenceNVEDriftError("unsupported NVE restart equality schema")
        for name in (
            "same_end_step",
            "same_source_and_runtime_provenance",
            "same_coordinates",
            "same_velocities",
            "same_energy_bits",
            "same_current_frame_sha256",
            "same_trajectory_head_sha256",
            "same_evaluated_frame_count",
            "same_checkpoint_sha256",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ReferenceNVEDriftError(f"{name} must be boolean")
        for name in (
            "uninterrupted_checkpoint_sha256",
            "restarted_checkpoint_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if self.same_checkpoint_sha256 != (
            self.uninterrupted_checkpoint_sha256
            == self.restarted_checkpoint_sha256
        ):
            raise ReferenceNVEDriftError(
                "checkpoint equality disposition is inconsistent"
            )

    @property
    def exact(self) -> bool:
        return all(
            getattr(self, name)
            for name in (
                "same_end_step",
                "same_source_and_runtime_provenance",
                "same_coordinates",
                "same_velocities",
                "same_energy_bits",
                "same_current_frame_sha256",
                "same_trajectory_head_sha256",
                "same_evaluated_frame_count",
                "same_checkpoint_sha256",
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "exact": self.exact,
            "same_end_step": self.same_end_step,
            "same_source_and_runtime_provenance": (
                self.same_source_and_runtime_provenance
            ),
            "same_coordinates": self.same_coordinates,
            "same_velocities": self.same_velocities,
            "same_energy_bits": self.same_energy_bits,
            "same_current_frame_sha256": self.same_current_frame_sha256,
            "same_trajectory_head_sha256": self.same_trajectory_head_sha256,
            "same_evaluated_frame_count": self.same_evaluated_frame_count,
            "same_checkpoint_sha256": self.same_checkpoint_sha256,
            "uninterrupted_checkpoint_sha256": (
                self.uninterrupted_checkpoint_sha256
            ),
            "restarted_checkpoint_sha256": self.restarted_checkpoint_sha256,
        }


@dataclass(frozen=True)
class ReferenceNVEDriftResult:
    acceptance_config: ReferenceNVEDriftAcceptanceConfig
    observations: tuple[ReferenceNVEDriftObservation, ...]
    metrics: tuple[ReferenceNVEDriftMetric, ...]
    restart_equality: ReferenceNVERestartEquality
    energy_drift_slope_kcal_per_mol_per_ps: float
    rms_energy_drift_kcal_per_mol: float
    max_abs_energy_drift_kcal_per_mol: float
    max_linear_momentum_drift_da_angstrom_per_ps: float
    rms_linear_momentum_drift_da_angstrom_per_ps: float
    atom_count: int
    constraint_count: int
    kinetic_temperature_degrees_of_freedom: int
    trajectory_head_sha256: str
    uninterrupted_checkpoint_sha256: str
    restarted_checkpoint_sha256: str
    provenance_sha256: str
    scientific_blockers: tuple[str, ...] = REFERENCE_NVE_DRIFT_SCIENTIFIC_BLOCKERS
    schema_id: str = REFERENCE_NVE_DRIFT_RESULT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_NVE_DRIFT_RESULT_SCHEMA_ID:
            raise ReferenceNVEDriftError("unsupported NVE drift result schema")
        if not isinstance(
            self.acceptance_config,
            ReferenceNVEDriftAcceptanceConfig,
        ):
            raise ReferenceNVEDriftError("invalid NVE drift acceptance config")
        observations = tuple(self.observations)
        if len(observations) < 2 or not all(
            isinstance(row, ReferenceNVEDriftObservation) for row in observations
        ):
            raise ReferenceNVEDriftError(
                "NVE drift result requires at least two observations"
            )
        if observations[0].step != 0 or [row.step for row in observations] != list(
            range(observations[-1].step + 1)
        ):
            raise ReferenceNVEDriftError("NVE drift observation steps are not contiguous")
        if any(
            right.time_ps <= left.time_ps
            for left, right in zip(observations, observations[1:])
        ):
            raise ReferenceNVEDriftError(
                "NVE drift observation times must strictly increase"
            )
        object.__setattr__(self, "observations", observations)
        metrics = tuple(self.metrics)
        if not all(isinstance(row, ReferenceNVEDriftMetric) for row in metrics) or (
            tuple(row.metric_id for row in metrics)
            != REFERENCE_NVE_DRIFT_METRIC_IDS
        ):
            raise ReferenceNVEDriftError(
                "NVE drift metric rows are incomplete or out of order"
            )
        object.__setattr__(self, "metrics", metrics)
        if not isinstance(self.restart_equality, ReferenceNVERestartEquality):
            raise ReferenceNVEDriftError("invalid NVE restart equality result")
        object.__setattr__(
            self,
            "atom_count",
            _exact_int(self.atom_count, name="atom_count", minimum=1),
        )
        object.__setattr__(
            self,
            "constraint_count",
            _exact_int(self.constraint_count, name="constraint_count"),
        )
        for name in (
            "energy_drift_slope_kcal_per_mol_per_ps",
            "rms_energy_drift_kcal_per_mol",
            "max_abs_energy_drift_kcal_per_mol",
            "max_linear_momentum_drift_da_angstrom_per_ps",
            "rms_linear_momentum_drift_da_angstrom_per_ps",
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(
                    getattr(self, name),
                    name=name,
                    nonnegative=name != "energy_drift_slope_kcal_per_mol_per_ps",
                ),
            )
        object.__setattr__(
            self,
            "kinetic_temperature_degrees_of_freedom",
            _exact_int(
                self.kinetic_temperature_degrees_of_freedom,
                name="kinetic temperature degrees of freedom",
                minimum=1,
            ),
        )
        if self.kinetic_temperature_degrees_of_freedom != (
            3 * self.atom_count - self.constraint_count
        ):
            raise ReferenceNVEDriftError(
                "kinetic temperature degrees of freedom are inconsistent"
            )
        initial_energy = observations[0].total_energy_kcal_per_mol
        relative_scale = max(
            abs(initial_energy),
            self.acceptance_config.relative_energy_floor_kcal_per_mol,
        )
        for row in observations:
            expected_drift = row.total_energy_kcal_per_mol - initial_energy
            if row.energy_drift_kcal_per_mol.hex() != expected_drift.hex():
                raise ReferenceNVEDriftError(
                    "observation energy drift is inconsistent"
                )
            if row.relative_energy_drift.hex() != (
                expected_drift / relative_scale
            ).hex():
                raise ReferenceNVEDriftError(
                    "observation relative energy drift is inconsistent"
                )
            if row.kinetic_temperature_k.hex() != (
                2.0
                * row.kinetic_energy_kcal_per_mol
                / (
                    self.kinetic_temperature_degrees_of_freedom
                    * MOLAR_GAS_CONSTANT_KCAL_PER_MOL_K
                )
            ).hex():
                raise ReferenceNVEDriftError(
                    "observation kinetic temperature is inconsistent"
                )
        energy_drifts = [row.energy_drift_kcal_per_mol for row in observations]
        momentum_drifts = [
            row.linear_momentum_drift_norm_da_angstrom_per_ps
            for row in observations
        ]
        expected_max_energy = max(abs(value) for value in energy_drifts)
        expected_rms_energy = math.sqrt(
            math.fsum(value * value for value in energy_drifts)
            / len(energy_drifts)
        )
        expected_slope = _slope(
            [row.time_ps for row in observations],
            energy_drifts,
        )
        expected_max_momentum = max(momentum_drifts)
        expected_rms_momentum = math.sqrt(
            math.fsum(value * value for value in momentum_drifts)
            / len(momentum_drifts)
        )
        for name, expected in (
            ("max_abs_energy_drift_kcal_per_mol", expected_max_energy),
            ("rms_energy_drift_kcal_per_mol", expected_rms_energy),
            ("energy_drift_slope_kcal_per_mol_per_ps", expected_slope),
            (
                "max_linear_momentum_drift_da_angstrom_per_ps",
                expected_max_momentum,
            ),
            (
                "rms_linear_momentum_drift_da_angstrom_per_ps",
                expected_rms_momentum,
            ),
        ):
            if getattr(self, name).hex() != expected.hex():
                raise ReferenceNVEDriftError(
                    f"NVE drift summary {name} is inconsistent"
                )
        expected_thresholds = (
            self.acceptance_config.max_abs_energy_drift_kcal_per_mol_per_atom,
            self.acceptance_config.max_rms_energy_drift_kcal_per_mol_per_atom,
            self.acceptance_config.max_abs_relative_energy_drift,
            self.acceptance_config.max_abs_energy_drift_slope_kcal_per_mol_per_ps_per_atom,
            self.acceptance_config.max_linear_momentum_drift_da_angstrom_per_ps,
            self.acceptance_config.max_rms_linear_momentum_drift_da_angstrom_per_ps,
            self.acceptance_config.max_position_constraint_residual_angstrom,
            self.acceptance_config.max_velocity_constraint_residual_angstrom_per_ps,
            1.0,
        )
        expected_observed = (
            expected_max_energy / self.atom_count,
            expected_rms_energy / self.atom_count,
            max(abs(row.relative_energy_drift) for row in observations),
            abs(expected_slope) / self.atom_count,
            expected_max_momentum,
            expected_rms_momentum,
            max(
                row.max_position_constraint_residual_angstrom
                for row in observations
            ),
            max(
                row.max_velocity_constraint_residual_angstrom_per_ps
                for row in observations
            ),
            1.0 if self.restart_equality.exact else 0.0,
        )
        expected_units = (
            "kcal/mol/atom",
            "kcal/mol/atom",
            "dimensionless",
            "kcal/mol/ps/atom",
            "Da*angstrom/ps",
            "Da*angstrom/ps",
            "angstrom",
            "angstrom/ps",
            "boolean",
        )
        for row, observed, threshold, unit in zip(
            metrics,
            expected_observed,
            expected_thresholds,
            expected_units,
        ):
            if (
                row.observed.hex() != observed.hex()
                or row.threshold.hex() != threshold.hex()
                or row.unit != unit
            ):
                raise ReferenceNVEDriftError(
                    f"NVE drift metric {row.metric_id} is inconsistent"
                )
        for name in (
            "trajectory_head_sha256",
            "uninterrupted_checkpoint_sha256",
            "restarted_checkpoint_sha256",
            "provenance_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if self.uninterrupted_checkpoint_sha256 != (
            self.restart_equality.uninterrupted_checkpoint_sha256
        ) or self.restarted_checkpoint_sha256 != (
            self.restart_equality.restarted_checkpoint_sha256
        ):
            raise ReferenceNVEDriftError(
                "NVE drift result restart identities are inconsistent"
            )
        blockers = tuple(self.scientific_blockers)
        if blockers != REFERENCE_NVE_DRIFT_SCIENTIFIC_BLOCKERS:
            raise ReferenceNVEDriftError(
                "NVE drift scientific blockers cannot be promoted"
            )
        object.__setattr__(self, "scientific_blockers", blockers)

    @property
    def numerical_acceptance_passed(self) -> bool:
        return all(row.passed for row in self.metrics)

    @property
    def scientifically_validated(self) -> bool:
        return False

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_NVE_DRIFT_ALGORITHM_ID,
            "status": "completed",
            "numerical_acceptance_passed": self.numerical_acceptance_passed,
            "scientifically_validated": False,
            "claim_safe": False,
            "acceptance_config": self.acceptance_config.to_dict(),
            "acceptance_config_fingerprint_sha256": (
                self.acceptance_config.fingerprint_sha256
            ),
            "observation_count": len(self.observations),
            "observations": [row.to_dict() for row in self.observations],
            "metrics": [row.to_dict() for row in self.metrics],
            "failed_metric_ids": [
                row.metric_id for row in self.metrics if not row.passed
            ],
            "restart_equality": self.restart_equality.to_dict(),
            "energy_drift_slope_kcal_per_mol_per_ps_hex": (
                self.energy_drift_slope_kcal_per_mol_per_ps.hex()
            ),
            "rms_energy_drift_kcal_per_mol_hex": (
                self.rms_energy_drift_kcal_per_mol.hex()
            ),
            "max_abs_energy_drift_kcal_per_mol_hex": (
                self.max_abs_energy_drift_kcal_per_mol.hex()
            ),
            "max_linear_momentum_drift_da_angstrom_per_ps_hex": (
                self.max_linear_momentum_drift_da_angstrom_per_ps.hex()
            ),
            "rms_linear_momentum_drift_da_angstrom_per_ps_hex": (
                self.rms_linear_momentum_drift_da_angstrom_per_ps.hex()
            ),
            "atom_count": self.atom_count,
            "constraint_count": self.constraint_count,
            "kinetic_temperature_degrees_of_freedom": (
                self.kinetic_temperature_degrees_of_freedom
            ),
            "kinetic_temperature_dof_policy": (
                "3N_minus_declared_distance_constraints_no_com_removal"
            ),
            "trajectory_head_sha256": self.trajectory_head_sha256,
            "uninterrupted_checkpoint_sha256": (
                self.uninterrupted_checkpoint_sha256
            ),
            "restarted_checkpoint_sha256": self.restarted_checkpoint_sha256,
            "provenance_sha256": self.provenance_sha256,
            "scientific_blockers": list(self.scientific_blockers),
        }


def _frame_payload_hashes(frame: ReferenceNVEFrame) -> tuple[str, str]:
    payload = frame.to_dict()
    coordinates = payload.get("coordinates_angstrom")
    velocities = payload.get("velocities_angstrom_per_ps")
    if not isinstance(coordinates, Mapping) or not isinstance(velocities, Mapping):
        raise ReferenceNVEDriftError("NVE frame tensor payload is unavailable")
    return (
        _digest(coordinates.get("data_sha256"), name="coordinate_data_sha256"),
        _digest(velocities.get("data_sha256"), name="velocity_data_sha256"),
    )


def _restart_equality(
    uninterrupted: ReferenceNVEResult,
    restarted: ReferenceNVEResult,
) -> ReferenceNVERestartEquality:
    first = uninterrupted.checkpoint
    second = restarted.checkpoint
    energy_names = (
        "initial_total_energy_kcal_per_mol",
        "current_potential_energy_kcal_per_mol",
        "current_kinetic_energy_kcal_per_mol",
        "current_total_energy_kcal_per_mol",
        "max_abs_energy_drift_kcal_per_mol",
        "max_abs_position_constraint_residual_angstrom",
        "max_abs_velocity_constraint_residual_angstrom_per_ps",
    )
    provenance_equal = uninterrupted.provenance.to_dict() == restarted.provenance.to_dict()
    return ReferenceNVERestartEquality(
        same_end_step=uninterrupted.end_step == restarted.end_step,
        same_source_and_runtime_provenance=provenance_equal,
        same_coordinates=torch.equal(first.coordinates, second.coordinates),
        same_velocities=torch.equal(
            first.velocities_angstrom_per_ps,
            second.velocities_angstrom_per_ps,
        ),
        same_energy_bits=all(
            getattr(first, name).hex() == getattr(second, name).hex()
            for name in energy_names
        ),
        same_current_frame_sha256=(
            first.current_frame_sha256 == second.current_frame_sha256
        ),
        same_trajectory_head_sha256=(
            first.trajectory_head_sha256 == second.trajectory_head_sha256
        ),
        same_evaluated_frame_count=(
            first.evaluated_frame_count == second.evaluated_frame_count
        ),
        same_checkpoint_sha256=(
            first.checkpoint_sha256 == second.checkpoint_sha256
        ),
        uninterrupted_checkpoint_sha256=first.checkpoint_sha256,
        restarted_checkpoint_sha256=second.checkpoint_sha256,
    )


def _slope(times: list[float], values: list[float]) -> float:
    time_mean = math.fsum(times) / len(times)
    value_mean = math.fsum(values) / len(values)
    numerator = math.fsum(
        (time - time_mean) * (value - value_mean)
        for time, value in zip(times, values)
    )
    denominator = math.fsum((time - time_mean) ** 2 for time in times)
    if denominator <= 0.0:
        raise ReferenceNVEDriftError("NVE drift trace has zero time span")
    return numerator / denominator


def analyze_reference_nve_drift(
    uninterrupted: ReferenceNVEResult,
    restarted: ReferenceNVEResult,
    acceptance_config: ReferenceNVEDriftAcceptanceConfig,
) -> ReferenceNVEDriftResult:
    """Analyze one full fresh NVE run and one pause/resume reproduction."""

    if not isinstance(uninterrupted, ReferenceNVEResult) or not isinstance(
        restarted,
        ReferenceNVEResult,
    ):
        raise ReferenceNVEDriftError("drift analysis requires two NVE results")
    if not isinstance(acceptance_config, ReferenceNVEDriftAcceptanceConfig):
        raise ReferenceNVEDriftError(
            "acceptance_config must be ReferenceNVEDriftAcceptanceConfig"
        )
    if uninterrupted.start_step != 0 or uninterrupted.end_step < 1:
        raise ReferenceNVEDriftError(
            "uninterrupted drift input must be a fresh nonempty NVE run"
        )
    if uninterrupted.checkpoint.config.trajectory_stride != 1:
        raise ReferenceNVEDriftError(
            "NVE drift analysis requires trajectory_stride=1"
        )
    if len(uninterrupted.frames) != uninterrupted.checkpoint.evaluated_frame_count:
        raise ReferenceNVEDriftError(
            "NVE drift analysis requires every evaluated frame"
        )
    if [frame.step for frame in uninterrupted.frames] != list(
        range(uninterrupted.end_step + 1)
    ):
        raise ReferenceNVEDriftError("NVE drift frames are incomplete")
    if len(uninterrupted.frames) > REFERENCE_NVE_DRIFT_MAX_FRAMES:
        raise ReferenceNVEDriftError("NVE drift frame count exceeds bounded limit")
    if (
        len(uninterrupted.frames) * uninterrupted.system.atom_count
        > REFERENCE_NVE_DRIFT_MAX_FRAME_ATOM_PRODUCTS
    ):
        raise ReferenceNVEDriftError(
            "NVE drift frame-atom product exceeds bounded limit"
        )
    if not 0 < restarted.start_step < restarted.end_step:
        raise ReferenceNVEDriftError(
            "restart comparison requires a genuine pause/resume segment"
        )

    masses = []
    for atom in uninterrupted.system.atoms:
        if atom.mass_da is None:
            raise ReferenceNVEDriftError(
                f"atom {atom.index} is missing mass for drift analysis"
            )
        masses.append(_finite_float(atom.mass_da, name="atom mass", positive=True))
    mass_tensor = torch.tensor(masses, dtype=torch.float64).view(1, -1, 1)
    atom_count = uninterrupted.system.atom_count
    constraint_config = uninterrupted.checkpoint.constraint_config
    degrees_of_freedom = 3 * atom_count - len(constraint_config.constraints)
    if degrees_of_freedom <= 0:
        raise ReferenceNVEDriftError(
            "kinetic-temperature degrees of freedom are not positive"
        )
    initial_energy = uninterrupted.initial_total_energy_kcal_per_mol
    relative_scale = max(
        abs(initial_energy),
        acceptance_config.relative_energy_floor_kcal_per_mol,
    )
    first_momentum: torch.Tensor | None = None
    observations: list[ReferenceNVEDriftObservation] = []
    energy_drifts: list[float] = []
    momentum_drifts: list[float] = []
    for frame in uninterrupted.frames:
        momentum = (
            mass_tensor * frame.velocities_angstrom_per_ps
        ).sum(dim=1)[0]
        if first_momentum is None:
            first_momentum = momentum.detach().clone()
        momentum_drift = float(
            torch.linalg.vector_norm(momentum - first_momentum).item()
        )
        energy_drift = frame.total_energy_kcal_per_mol - initial_energy
        try:
            position_rows = observe_reference_position_constraints(
                uninterrupted.system,
                frame.coordinates,
                constraint_config,
            )
            velocity_rows = observe_reference_velocity_constraints(
                uninterrupted.system,
                frame.coordinates,
                frame.velocities_angstrom_per_ps,
                constraint_config,
            )
        except ReferenceSHAKERATTLEError as exc:
            raise ReferenceNVEDriftError(
                f"constraint observation failed at step {frame.step}: {exc}"
            ) from exc
        position_residual = max(
            (abs(row.residual_angstrom) for row in position_rows),
            default=0.0,
        )
        velocity_residual = max(
            (
                abs(row.radial_relative_velocity_angstrom_per_ps)
                for row in velocity_rows
            ),
            default=0.0,
        )
        coordinate_sha, velocity_sha = _frame_payload_hashes(frame)
        temperature = (
            2.0
            * frame.kinetic_energy_kcal_per_mol
            / (degrees_of_freedom * MOLAR_GAS_CONSTANT_KCAL_PER_MOL_K)
        )
        observations.append(
            ReferenceNVEDriftObservation(
                step=frame.step,
                time_ps=frame.time_ps,
                potential_energy_kcal_per_mol=(
                    frame.potential_energy_kcal_per_mol
                ),
                kinetic_energy_kcal_per_mol=frame.kinetic_energy_kcal_per_mol,
                total_energy_kcal_per_mol=frame.total_energy_kcal_per_mol,
                energy_drift_kcal_per_mol=energy_drift,
                relative_energy_drift=energy_drift / relative_scale,
                kinetic_temperature_k=temperature,
                linear_momentum_da_angstrom_per_ps=tuple(
                    float(value) for value in momentum.detach().cpu().tolist()
                ),
                linear_momentum_drift_norm_da_angstrom_per_ps=momentum_drift,
                max_position_constraint_residual_angstrom=position_residual,
                max_velocity_constraint_residual_angstrom_per_ps=(
                    velocity_residual
                ),
                frame_sha256=frame.fingerprint_sha256,
                coordinate_data_sha256=coordinate_sha,
                velocity_data_sha256=velocity_sha,
            )
        )
        energy_drifts.append(energy_drift)
        momentum_drifts.append(momentum_drift)

    max_abs_energy = max(abs(value) for value in energy_drifts)
    if max_abs_energy.hex() != (
        uninterrupted.checkpoint.max_abs_energy_drift_kcal_per_mol.hex()
    ):
        raise ReferenceNVEDriftError(
            "all-step energy trace does not reproduce checkpoint maximum drift"
        )
    rms_energy = math.sqrt(
        math.fsum(value * value for value in energy_drifts) / len(energy_drifts)
    )
    slope = _slope(
        [row.time_ps for row in observations],
        [row.energy_drift_kcal_per_mol for row in observations],
    )
    max_relative = max(abs(row.relative_energy_drift) for row in observations)
    max_momentum = max(momentum_drifts)
    rms_momentum = math.sqrt(
        math.fsum(value * value for value in momentum_drifts)
        / len(momentum_drifts)
    )
    max_position = max(
        row.max_position_constraint_residual_angstrom for row in observations
    )
    max_velocity = max(
        row.max_velocity_constraint_residual_angstrom_per_ps
        for row in observations
    )
    restart = _restart_equality(uninterrupted, restarted)
    observed_values = (
        max_abs_energy / atom_count,
        rms_energy / atom_count,
        max_relative,
        abs(slope) / atom_count,
        max_momentum,
        rms_momentum,
        max_position,
        max_velocity,
        1.0 if restart.exact else 0.0,
    )
    thresholds = (
        acceptance_config.max_abs_energy_drift_kcal_per_mol_per_atom,
        acceptance_config.max_rms_energy_drift_kcal_per_mol_per_atom,
        acceptance_config.max_abs_relative_energy_drift,
        acceptance_config.max_abs_energy_drift_slope_kcal_per_mol_per_ps_per_atom,
        acceptance_config.max_linear_momentum_drift_da_angstrom_per_ps,
        acceptance_config.max_rms_linear_momentum_drift_da_angstrom_per_ps,
        acceptance_config.max_position_constraint_residual_angstrom,
        acceptance_config.max_velocity_constraint_residual_angstrom_per_ps,
        1.0,
    )
    units = (
        "kcal/mol/atom",
        "kcal/mol/atom",
        "dimensionless",
        "kcal/mol/ps/atom",
        "Da*angstrom/ps",
        "Da*angstrom/ps",
        "angstrom",
        "angstrom/ps",
        "boolean",
    )
    metrics = tuple(
        ReferenceNVEDriftMetric(
            metric_id=metric_id,
            observed=observed,
            threshold=threshold,
            unit=unit,
            passed=(
                observed == 1.0
                if metric_id == "exact_checkpoint_restart_equality"
                else observed <= threshold
            ),
        )
        for metric_id, observed, threshold, unit in zip(
            REFERENCE_NVE_DRIFT_METRIC_IDS,
            observed_values,
            thresholds,
            units,
        )
    )
    observations_payload = [row.to_dict() for row in observations]
    metrics_payload = [row.to_dict() for row in metrics]
    provenance = _canonical_sha256(
        {
            "algorithm_id": REFERENCE_NVE_DRIFT_ALGORITHM_ID,
            "acceptance_config_fingerprint_sha256": (
                acceptance_config.fingerprint_sha256
            ),
            "nve_provenance": uninterrupted.provenance.to_dict(),
            "uninterrupted_checkpoint_sha256": (
                uninterrupted.checkpoint.checkpoint_sha256
            ),
            "restarted_checkpoint_sha256": restarted.checkpoint.checkpoint_sha256,
            "trajectory_head_sha256": (
                uninterrupted.checkpoint.trajectory_head_sha256
            ),
            "observation_trace_sha256": _canonical_sha256(observations_payload),
            "metric_rows_sha256": _canonical_sha256(metrics_payload),
            "restart_equality": restart.to_dict(),
            "kinetic_temperature_degrees_of_freedom": degrees_of_freedom,
        }
    )
    return ReferenceNVEDriftResult(
        acceptance_config=acceptance_config,
        observations=tuple(observations),
        metrics=metrics,
        restart_equality=restart,
        energy_drift_slope_kcal_per_mol_per_ps=slope,
        rms_energy_drift_kcal_per_mol=rms_energy,
        max_abs_energy_drift_kcal_per_mol=max_abs_energy,
        max_linear_momentum_drift_da_angstrom_per_ps=max_momentum,
        rms_linear_momentum_drift_da_angstrom_per_ps=rms_momentum,
        atom_count=atom_count,
        constraint_count=len(constraint_config.constraints),
        kinetic_temperature_degrees_of_freedom=degrees_of_freedom,
        trajectory_head_sha256=uninterrupted.checkpoint.trajectory_head_sha256,
        uninterrupted_checkpoint_sha256=(
            uninterrupted.checkpoint.checkpoint_sha256
        ),
        restarted_checkpoint_sha256=restarted.checkpoint.checkpoint_sha256,
        provenance_sha256=provenance,
    )


__all__ = [
    "MOLAR_GAS_CONSTANT_KCAL_PER_MOL_K",
    "REFERENCE_NVE_DRIFT_ACCEPTANCE_SCHEMA_ID",
    "REFERENCE_NVE_DRIFT_ALGORITHM_ID",
    "REFERENCE_NVE_DRIFT_METRIC_IDS",
    "REFERENCE_NVE_DRIFT_MAX_FRAMES",
    "REFERENCE_NVE_DRIFT_MAX_FRAME_ATOM_PRODUCTS",
    "REFERENCE_NVE_DRIFT_METRIC_SCHEMA_ID",
    "REFERENCE_NVE_DRIFT_OBSERVATION_SCHEMA_ID",
    "REFERENCE_NVE_DRIFT_RESULT_SCHEMA_ID",
    "REFERENCE_NVE_DRIFT_SCIENTIFIC_BLOCKERS",
    "REFERENCE_NVE_RESTART_EQUALITY_SCHEMA_ID",
    "ReferenceNVEDriftAcceptanceConfig",
    "ReferenceNVEDriftError",
    "ReferenceNVEDriftMetric",
    "ReferenceNVEDriftObservation",
    "ReferenceNVEDriftResult",
    "ReferenceNVERestartEquality",
    "analyze_reference_nve_drift",
]
