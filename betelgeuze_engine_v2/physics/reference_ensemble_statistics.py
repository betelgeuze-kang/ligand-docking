"""All-step NVT/NPT statistics and exact-restart evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
from statistics import NormalDist
from typing import Mapping

import torch

from .reference_canonical_ensemble import (
    REFERENCE_CANONICAL_ENSEMBLE_ALGORITHM_ID,
    ReferenceCanonicalEnsembleResult,
)


REFERENCE_ENSEMBLE_STATISTICS_ALGORITHM_ID = (
    "all_step_nvt_npt_autocorrelation_ci_exact_restart_analysis/1.0.0"
)
REFERENCE_ENSEMBLE_STATISTICS_ACCEPTANCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_ensemble_statistics_acceptance/1.0.0"
)
REFERENCE_ENSEMBLE_SERIES_STATISTICS_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_ensemble_series_statistics/1.0.0"
)
REFERENCE_ENSEMBLE_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_ensemble_metric/1.0.0"
)
REFERENCE_ENSEMBLE_RESTART_EQUALITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_ensemble_restart_equality/1.0.0"
)
REFERENCE_ENSEMBLE_STATISTICS_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_ensemble_statistics_result/1.0.0"
)

REFERENCE_ENSEMBLE_COMMON_METRIC_IDS = (
    "exact_checkpoint_restart_equality",
    "temperature_absolute_bias_kelvin",
    "temperature_effective_sample_size",
    "temperature_target_inside_confidence_interval",
    "max_position_constraint_residual_angstrom",
    "max_velocity_constraint_residual_angstrom_per_ps",
)
REFERENCE_ENSEMBLE_NPT_METRIC_IDS = (
    "pressure_absolute_bias_bar",
    "pressure_effective_sample_size",
    "pressure_target_inside_confidence_interval",
    "barostat_acceptance_fraction_minimum",
    "barostat_acceptance_fraction_maximum",
    "minimum_barostat_attempt_count",
)
REFERENCE_ENSEMBLE_SERIES_IDS = (
    "potential_energy_kcal_per_mol",
    "kinetic_energy_kcal_per_mol",
    "total_energy_kcal_per_mol",
    "kinetic_temperature_kelvin",
    "volume_angstrom3",
    "instantaneous_pressure_bar",
)

REFERENCE_ENSEMBLE_STATISTICS_SCIENTIFIC_BLOCKERS = (
    "caller_supplied_acceptance_thresholds_not_independently_reviewed",
    "finite_trajectory_may_not_be_equilibrated",
    "burn_in_selection_not_independently_reviewed",
    "initial_positive_autocorrelation_estimator_not_independently_validated",
    "normal_approximation_confidence_interval_not_independently_validated",
    "temperature_and_pressure_observables_not_independently_compared",
    "ensemble_distribution_against_external_oracle_missing",
    "liquid_density_compressibility_and_heat_capacity_evidence_missing",
    "two_cpu_host_reproduction_missing",
    "cpu_gpu_parity_evidence_missing",
    "independent_scientific_review_missing",
    "product_integration_not_qualified",
)


class ReferenceEnsembleStatisticsError(ValueError):
    """An ensemble statistics request failed closed."""


def _finite_float(
    value: object,
    *,
    name: str,
    nonnegative: bool = False,
    positive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceEnsembleStatisticsError(
            f"{name} must be a finite real number"
        )
    number = float(value)
    if not math.isfinite(number):
        raise ReferenceEnsembleStatisticsError(f"{name} must be finite")
    if nonnegative and number < 0.0:
        raise ReferenceEnsembleStatisticsError(f"{name} must be non-negative")
    if positive and number <= 0.0:
        raise ReferenceEnsembleStatisticsError(f"{name} must be positive")
    return number


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReferenceEnsembleStatisticsError(f"{name} must be an integer")
    integer = int(value)
    if integer < minimum or (maximum is not None and integer > maximum):
        upper = "" if maximum is None else f" and at most {maximum}"
        raise ReferenceEnsembleStatisticsError(
            f"{name} must be at least {minimum}{upper}"
        )
    return integer


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ReferenceEnsembleStatisticsError(f"{name} must be a SHA-256")
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ReferenceEnsembleStatisticsError(
            f"{name} must be a lowercase SHA-256"
        )
    return digest


def _canonical_sha256(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ReferenceEnsembleStatisticsError(
            "ensemble statistics payload is not canonical JSON"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _require_float_hex(value: object, *, name: str) -> float:
    if not isinstance(value, str):
        raise ReferenceEnsembleStatisticsError(
            f"{name} must be canonical binary64 hex"
        )
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise ReferenceEnsembleStatisticsError(
            f"{name} must be canonical binary64 hex"
        ) from exc
    if not math.isfinite(number) or number.hex() != value:
        raise ReferenceEnsembleStatisticsError(
            f"{name} must be canonical finite binary64 hex"
        )
    return number


@dataclass(frozen=True)
class ReferenceEnsembleStatisticsAcceptanceConfig:
    burn_in_steps: int
    max_abs_temperature_bias_kelvin: float
    min_temperature_effective_sample_size: float
    max_abs_pressure_bias_bar: float
    min_pressure_effective_sample_size: float
    min_barostat_acceptance_fraction: float
    max_barostat_acceptance_fraction: float
    min_barostat_attempt_count: int
    max_position_constraint_residual_angstrom: float
    max_velocity_constraint_residual_angstrom_per_ps: float
    confidence_level: float = 0.95
    require_temperature_target_inside_confidence_interval: bool = True
    require_pressure_target_inside_confidence_interval: bool = True
    schema_id: str = REFERENCE_ENSEMBLE_STATISTICS_ACCEPTANCE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_ENSEMBLE_STATISTICS_ACCEPTANCE_SCHEMA_ID:
            raise ReferenceEnsembleStatisticsError(
                "unsupported ensemble acceptance schema"
            )
        object.__setattr__(
            self,
            "burn_in_steps",
            _exact_int(self.burn_in_steps, name="burn_in_steps", minimum=0),
        )
        for name in (
            "max_abs_temperature_bias_kelvin",
            "min_temperature_effective_sample_size",
            "max_abs_pressure_bias_bar",
            "min_pressure_effective_sample_size",
            "max_position_constraint_residual_angstrom",
            "max_velocity_constraint_residual_angstrom_per_ps",
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(getattr(self, name), name=name, nonnegative=True),
            )
        minimum_fraction = _finite_float(
            self.min_barostat_acceptance_fraction,
            name="min_barostat_acceptance_fraction",
            nonnegative=True,
        )
        maximum_fraction = _finite_float(
            self.max_barostat_acceptance_fraction,
            name="max_barostat_acceptance_fraction",
            nonnegative=True,
        )
        if maximum_fraction > 1.0 or minimum_fraction > maximum_fraction:
            raise ReferenceEnsembleStatisticsError(
                "barostat acceptance fraction bounds are invalid"
            )
        object.__setattr__(
            self,
            "min_barostat_acceptance_fraction",
            minimum_fraction,
        )
        object.__setattr__(
            self,
            "max_barostat_acceptance_fraction",
            maximum_fraction,
        )
        object.__setattr__(
            self,
            "min_barostat_attempt_count",
            _exact_int(
                self.min_barostat_attempt_count,
                name="min_barostat_attempt_count",
                minimum=0,
            ),
        )
        confidence = _finite_float(
            self.confidence_level,
            name="confidence_level",
            positive=True,
        )
        if confidence < 0.5 or confidence >= 1.0:
            raise ReferenceEnsembleStatisticsError(
                "confidence_level must be in [0.5, 1.0)"
            )
        object.__setattr__(self, "confidence_level", confidence)
        for name in (
            "require_temperature_target_inside_confidence_interval",
            "require_pressure_target_inside_confidence_interval",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ReferenceEnsembleStatisticsError(f"{name} must be boolean")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_ENSEMBLE_STATISTICS_ALGORITHM_ID,
            "burn_in_steps": self.burn_in_steps,
            "max_abs_temperature_bias_kelvin_hex": (
                self.max_abs_temperature_bias_kelvin.hex()
            ),
            "min_temperature_effective_sample_size_hex": (
                self.min_temperature_effective_sample_size.hex()
            ),
            "max_abs_pressure_bias_bar_hex": self.max_abs_pressure_bias_bar.hex(),
            "min_pressure_effective_sample_size_hex": (
                self.min_pressure_effective_sample_size.hex()
            ),
            "min_barostat_acceptance_fraction_hex": (
                self.min_barostat_acceptance_fraction.hex()
            ),
            "max_barostat_acceptance_fraction_hex": (
                self.max_barostat_acceptance_fraction.hex()
            ),
            "min_barostat_attempt_count": self.min_barostat_attempt_count,
            "max_position_constraint_residual_angstrom_hex": (
                self.max_position_constraint_residual_angstrom.hex()
            ),
            "max_velocity_constraint_residual_angstrom_per_ps_hex": (
                self.max_velocity_constraint_residual_angstrom_per_ps.hex()
            ),
            "confidence_level_hex": self.confidence_level.hex(),
            "require_temperature_target_inside_confidence_interval": (
                self.require_temperature_target_inside_confidence_interval
            ),
            "require_pressure_target_inside_confidence_interval": (
                self.require_pressure_target_inside_confidence_interval
            ),
            "trace_policy": "fresh_run_all_steps_after_caller_fixed_burn_in",
            "restart_policy": "exact_checkpoint_rng_cell_and_trace_heads_required",
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "ReferenceEnsembleStatisticsAcceptanceConfig":
        expected = {
            "schema_id",
            "algorithm_id",
            "burn_in_steps",
            "max_abs_temperature_bias_kelvin_hex",
            "min_temperature_effective_sample_size_hex",
            "max_abs_pressure_bias_bar_hex",
            "min_pressure_effective_sample_size_hex",
            "min_barostat_acceptance_fraction_hex",
            "max_barostat_acceptance_fraction_hex",
            "min_barostat_attempt_count",
            "max_position_constraint_residual_angstrom_hex",
            "max_velocity_constraint_residual_angstrom_per_ps_hex",
            "confidence_level_hex",
            "require_temperature_target_inside_confidence_interval",
            "require_pressure_target_inside_confidence_interval",
            "trace_policy",
            "restart_policy",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ReferenceEnsembleStatisticsError(
                "ensemble acceptance config payload is invalid"
            )
        if value["algorithm_id"] != REFERENCE_ENSEMBLE_STATISTICS_ALGORITHM_ID:
            raise ReferenceEnsembleStatisticsError(
                "unsupported ensemble statistics algorithm"
            )
        if value["trace_policy"] != (
            "fresh_run_all_steps_after_caller_fixed_burn_in"
        ):
            raise ReferenceEnsembleStatisticsError(
                "unsupported ensemble trace policy"
            )
        if value["restart_policy"] != (
            "exact_checkpoint_rng_cell_and_trace_heads_required"
        ):
            raise ReferenceEnsembleStatisticsError(
                "unsupported ensemble restart policy"
            )
        result = cls(
            burn_in_steps=_exact_int(
                value["burn_in_steps"],
                name="burn_in_steps",
            ),
            max_abs_temperature_bias_kelvin=_require_float_hex(
                value["max_abs_temperature_bias_kelvin_hex"],
                name="max_abs_temperature_bias_kelvin_hex",
            ),
            min_temperature_effective_sample_size=_require_float_hex(
                value["min_temperature_effective_sample_size_hex"],
                name="min_temperature_effective_sample_size_hex",
            ),
            max_abs_pressure_bias_bar=_require_float_hex(
                value["max_abs_pressure_bias_bar_hex"],
                name="max_abs_pressure_bias_bar_hex",
            ),
            min_pressure_effective_sample_size=_require_float_hex(
                value["min_pressure_effective_sample_size_hex"],
                name="min_pressure_effective_sample_size_hex",
            ),
            min_barostat_acceptance_fraction=_require_float_hex(
                value["min_barostat_acceptance_fraction_hex"],
                name="min_barostat_acceptance_fraction_hex",
            ),
            max_barostat_acceptance_fraction=_require_float_hex(
                value["max_barostat_acceptance_fraction_hex"],
                name="max_barostat_acceptance_fraction_hex",
            ),
            min_barostat_attempt_count=_exact_int(
                value["min_barostat_attempt_count"],
                name="min_barostat_attempt_count",
            ),
            max_position_constraint_residual_angstrom=_require_float_hex(
                value["max_position_constraint_residual_angstrom_hex"],
                name="max_position_constraint_residual_angstrom_hex",
            ),
            max_velocity_constraint_residual_angstrom_per_ps=(
                _require_float_hex(
                    value[
                        "max_velocity_constraint_residual_angstrom_per_ps_hex"
                    ],
                    name=(
                        "max_velocity_constraint_residual_angstrom_per_ps_hex"
                    ),
                )
            ),
            confidence_level=_require_float_hex(
                value["confidence_level_hex"],
                name="confidence_level_hex",
            ),
            require_temperature_target_inside_confidence_interval=value[
                "require_temperature_target_inside_confidence_interval"
            ],
            require_pressure_target_inside_confidence_interval=value[
                "require_pressure_target_inside_confidence_interval"
            ],
            schema_id=str(value["schema_id"]),
        )
        if result.to_dict() != dict(value):
            raise ReferenceEnsembleStatisticsError(
                "ensemble acceptance config is not canonical"
            )
        return result

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class ReferenceEnsembleSeriesStatistics:
    series_id: str
    sample_count: int
    mean: float
    sample_standard_deviation: float
    minimum: float
    maximum: float
    integrated_autocorrelation_time: float
    effective_sample_size: float
    standard_error: float
    confidence_level: float
    confidence_interval_low: float
    confidence_interval_high: float
    target: float | None = None
    schema_id: str = REFERENCE_ENSEMBLE_SERIES_STATISTICS_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_ENSEMBLE_SERIES_STATISTICS_SCHEMA_ID:
            raise ReferenceEnsembleStatisticsError(
                "unsupported ensemble series statistics schema"
            )
        if self.series_id not in REFERENCE_ENSEMBLE_SERIES_IDS:
            raise ReferenceEnsembleStatisticsError(
                "unsupported ensemble series identifier"
            )
        count = _exact_int(self.sample_count, name="sample_count", minimum=2)
        object.__setattr__(self, "sample_count", count)
        for name in (
            "mean",
            "minimum",
            "maximum",
            "confidence_interval_low",
            "confidence_interval_high",
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(getattr(self, name), name=name),
            )
        for name in (
            "sample_standard_deviation",
            "integrated_autocorrelation_time",
            "effective_sample_size",
            "standard_error",
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(getattr(self, name), name=name, nonnegative=True),
            )
        confidence = _finite_float(
            self.confidence_level,
            name="confidence_level",
            positive=True,
        )
        if confidence < 0.5 or confidence >= 1.0:
            raise ReferenceEnsembleStatisticsError(
                "series confidence level is invalid"
            )
        object.__setattr__(self, "confidence_level", confidence)
        if self.minimum > self.mean or self.mean > self.maximum:
            raise ReferenceEnsembleStatisticsError(
                "series minimum, mean, and maximum are inconsistent"
            )
        if self.confidence_interval_low > self.mean or (
            self.mean > self.confidence_interval_high
        ):
            raise ReferenceEnsembleStatisticsError(
                "series confidence interval does not contain mean"
            )
        if self.integrated_autocorrelation_time < 1.0:
            raise ReferenceEnsembleStatisticsError(
                "integrated autocorrelation time must be at least one"
            )
        if self.effective_sample_size <= 0.0 or (
            self.effective_sample_size > count
        ):
            raise ReferenceEnsembleStatisticsError(
                "effective sample size is outside its valid range"
            )
        if self.target is not None:
            object.__setattr__(
                self,
                "target",
                _finite_float(self.target, name="series target"),
            )

    @property
    def target_inside_confidence_interval(self) -> bool | None:
        if self.target is None:
            return None
        return self.confidence_interval_low <= self.target <= (
            self.confidence_interval_high
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "series_id": self.series_id,
            "sample_count": self.sample_count,
            "mean_hex": self.mean.hex(),
            "sample_standard_deviation_hex": (
                self.sample_standard_deviation.hex()
            ),
            "minimum_hex": self.minimum.hex(),
            "maximum_hex": self.maximum.hex(),
            "integrated_autocorrelation_time_hex": (
                self.integrated_autocorrelation_time.hex()
            ),
            "effective_sample_size_hex": self.effective_sample_size.hex(),
            "standard_error_hex": self.standard_error.hex(),
            "confidence_level_hex": self.confidence_level.hex(),
            "confidence_interval_low_hex": self.confidence_interval_low.hex(),
            "confidence_interval_high_hex": self.confidence_interval_high.hex(),
            "target_hex": None if self.target is None else self.target.hex(),
            "target_inside_confidence_interval": (
                self.target_inside_confidence_interval
            ),
            "autocorrelation_policy": "initial_positive_sequence",
            "confidence_interval_policy": "normal_approximation_using_ess",
        }


@dataclass(frozen=True)
class ReferenceEnsembleMetric:
    metric_id: str
    observed: float
    threshold: float
    comparison: str
    passed: bool
    schema_id: str = REFERENCE_ENSEMBLE_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_ENSEMBLE_METRIC_SCHEMA_ID:
            raise ReferenceEnsembleStatisticsError(
                "unsupported ensemble metric schema"
            )
        allowed_ids = set(REFERENCE_ENSEMBLE_COMMON_METRIC_IDS) | set(
            REFERENCE_ENSEMBLE_NPT_METRIC_IDS
        )
        if self.metric_id not in allowed_ids:
            raise ReferenceEnsembleStatisticsError(
                "unsupported ensemble metric identifier"
            )
        object.__setattr__(
            self,
            "observed",
            _finite_float(self.observed, name="metric observed"),
        )
        object.__setattr__(
            self,
            "threshold",
            _finite_float(self.threshold, name="metric threshold"),
        )
        if self.comparison not in {"less_or_equal", "greater_or_equal", "equal"}:
            raise ReferenceEnsembleStatisticsError(
                "unsupported ensemble metric comparison"
            )
        expected = {
            "less_or_equal": self.observed <= self.threshold,
            "greater_or_equal": self.observed >= self.threshold,
            "equal": self.observed == self.threshold,
        }[self.comparison]
        if self.passed != expected:
            raise ReferenceEnsembleStatisticsError(
                "ensemble metric disposition is inconsistent"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "metric_id": self.metric_id,
            "observed_hex": self.observed.hex(),
            "threshold_hex": self.threshold.hex(),
            "comparison": self.comparison,
            "passed": self.passed,
            "failure_disposition": (
                "accepted" if self.passed else "rejected_threshold_failure"
            ),
        }


@dataclass(frozen=True)
class ReferenceEnsembleRestartEquality:
    same_end_step: bool
    same_coordinates: bool
    same_velocities: bool
    same_cell: bool
    same_energies: bool
    same_temperature: bool
    same_pressure_observation: bool
    same_random_word_index: bool
    same_trajectory_head: bool
    same_barostat_head: bool
    same_checkpoint_sha256: bool
    uninterrupted_checkpoint_sha256: str
    restarted_checkpoint_sha256: str
    schema_id: str = REFERENCE_ENSEMBLE_RESTART_EQUALITY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_ENSEMBLE_RESTART_EQUALITY_SCHEMA_ID:
            raise ReferenceEnsembleStatisticsError(
                "unsupported ensemble restart equality schema"
            )
        for name in (
            "same_end_step",
            "same_coordinates",
            "same_velocities",
            "same_cell",
            "same_energies",
            "same_temperature",
            "same_pressure_observation",
            "same_random_word_index",
            "same_trajectory_head",
            "same_barostat_head",
            "same_checkpoint_sha256",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ReferenceEnsembleStatisticsError(
                    f"{name} must be boolean"
                )
        for name in (
            "uninterrupted_checkpoint_sha256",
            "restarted_checkpoint_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if self.same_checkpoint_sha256 != (
            self.uninterrupted_checkpoint_sha256
            == self.restarted_checkpoint_sha256
        ):
            raise ReferenceEnsembleStatisticsError(
                "restart checkpoint digest disposition is inconsistent"
            )

    @property
    def exact(self) -> bool:
        return all(
            (
                self.same_end_step,
                self.same_coordinates,
                self.same_velocities,
                self.same_cell,
                self.same_energies,
                self.same_temperature,
                self.same_pressure_observation,
                self.same_random_word_index,
                self.same_trajectory_head,
                self.same_barostat_head,
                self.same_checkpoint_sha256,
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "same_end_step": self.same_end_step,
            "same_coordinates": self.same_coordinates,
            "same_velocities": self.same_velocities,
            "same_cell": self.same_cell,
            "same_energies": self.same_energies,
            "same_temperature": self.same_temperature,
            "same_pressure_observation": self.same_pressure_observation,
            "same_random_word_index": self.same_random_word_index,
            "same_trajectory_head": self.same_trajectory_head,
            "same_barostat_head": self.same_barostat_head,
            "same_checkpoint_sha256": self.same_checkpoint_sha256,
            "uninterrupted_checkpoint_sha256": (
                self.uninterrupted_checkpoint_sha256
            ),
            "restarted_checkpoint_sha256": self.restarted_checkpoint_sha256,
            "exact": self.exact,
        }


@dataclass(frozen=True)
class ReferenceEnsembleStatisticsResult:
    ensemble: str
    acceptance_config: ReferenceEnsembleStatisticsAcceptanceConfig
    restart_equality: ReferenceEnsembleRestartEquality
    series: tuple[ReferenceEnsembleSeriesStatistics, ...]
    metrics: tuple[ReferenceEnsembleMetric, ...]
    burn_in_steps: int
    analyzed_start_step: int
    analyzed_end_step: int
    analyzed_frame_count: int
    source_checkpoint_sha256: str
    restarted_checkpoint_sha256: str
    source_trajectory_head_sha256: str
    source_barostat_head_sha256: str
    scientific_blockers: tuple[str, ...] = (
        REFERENCE_ENSEMBLE_STATISTICS_SCIENTIFIC_BLOCKERS
    )
    schema_id: str = REFERENCE_ENSEMBLE_STATISTICS_RESULT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_ENSEMBLE_STATISTICS_RESULT_SCHEMA_ID:
            raise ReferenceEnsembleStatisticsError(
                "unsupported ensemble statistics result schema"
            )
        if self.ensemble not in {"NVT", "NPT"}:
            raise ReferenceEnsembleStatisticsError(
                "ensemble statistics result ensemble is invalid"
            )
        if not isinstance(
            self.acceptance_config,
            ReferenceEnsembleStatisticsAcceptanceConfig,
        ):
            raise ReferenceEnsembleStatisticsError(
                "ensemble acceptance config type is invalid"
            )
        if not isinstance(
            self.restart_equality,
            ReferenceEnsembleRestartEquality,
        ):
            raise ReferenceEnsembleStatisticsError(
                "ensemble restart equality type is invalid"
            )
        series = tuple(self.series)
        metrics = tuple(self.metrics)
        if len({row.series_id for row in series}) != len(series):
            raise ReferenceEnsembleStatisticsError(
                "ensemble series identifiers must be unique"
            )
        if len({row.metric_id for row in metrics}) != len(metrics):
            raise ReferenceEnsembleStatisticsError(
                "ensemble metric identifiers must be unique"
            )
        expected_metrics = set(REFERENCE_ENSEMBLE_COMMON_METRIC_IDS)
        if self.ensemble == "NPT":
            expected_metrics.update(REFERENCE_ENSEMBLE_NPT_METRIC_IDS)
        if {row.metric_id for row in metrics} != expected_metrics:
            raise ReferenceEnsembleStatisticsError(
                "ensemble result metric coverage is incomplete"
            )
        expected_series = {
            "potential_energy_kcal_per_mol",
            "kinetic_energy_kcal_per_mol",
            "total_energy_kcal_per_mol",
            "kinetic_temperature_kelvin",
        }
        if self.ensemble == "NPT":
            expected_series.update(
                {"volume_angstrom3", "instantaneous_pressure_bar"}
            )
        if {row.series_id for row in series} != expected_series:
            raise ReferenceEnsembleStatisticsError(
                "ensemble result series coverage is incomplete"
            )
        object.__setattr__(self, "series", series)
        object.__setattr__(self, "metrics", metrics)
        burn = _exact_int(self.burn_in_steps, name="burn_in_steps", minimum=0)
        if burn != self.acceptance_config.burn_in_steps:
            raise ReferenceEnsembleStatisticsError(
                "result burn-in does not match acceptance config"
            )
        object.__setattr__(self, "burn_in_steps", burn)
        start = _exact_int(
            self.analyzed_start_step,
            name="analyzed_start_step",
            minimum=0,
        )
        end = _exact_int(
            self.analyzed_end_step,
            name="analyzed_end_step",
            minimum=start + 1,
        )
        count = _exact_int(
            self.analyzed_frame_count,
            name="analyzed_frame_count",
            minimum=2,
        )
        if count != end - start + 1:
            raise ReferenceEnsembleStatisticsError(
                "analyzed frame count is inconsistent"
            )
        object.__setattr__(self, "analyzed_start_step", start)
        object.__setattr__(self, "analyzed_end_step", end)
        object.__setattr__(self, "analyzed_frame_count", count)
        for name in (
            "source_checkpoint_sha256",
            "restarted_checkpoint_sha256",
            "source_trajectory_head_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if self.ensemble == "NPT":
            object.__setattr__(
                self,
                "source_barostat_head_sha256",
                _digest(
                    self.source_barostat_head_sha256,
                    name="source_barostat_head_sha256",
                ),
            )
        elif self.source_barostat_head_sha256 != "":
            raise ReferenceEnsembleStatisticsError(
                "NVT statistics cannot carry a barostat head"
            )
        if tuple(self.scientific_blockers) != (
            REFERENCE_ENSEMBLE_STATISTICS_SCIENTIFIC_BLOCKERS
        ):
            raise ReferenceEnsembleStatisticsError(
                "ensemble statistics scientific blockers are fixed"
            )

    @property
    def passed(self) -> bool:
        return all(metric.passed for metric in self.metrics)

    @property
    def failure_rows(self) -> tuple[str, ...]:
        return tuple(
            metric.metric_id for metric in self.metrics if not metric.passed
        )

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        payload = {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_ENSEMBLE_STATISTICS_ALGORITHM_ID,
            "source_integrator_algorithm_id": (
                REFERENCE_CANONICAL_ENSEMBLE_ALGORITHM_ID
            ),
            "ensemble": self.ensemble,
            "acceptance_config": self.acceptance_config.to_dict(),
            "acceptance_config_fingerprint_sha256": (
                self.acceptance_config.fingerprint_sha256
            ),
            "restart_equality": self.restart_equality.to_dict(),
            "burn_in_steps": self.burn_in_steps,
            "analyzed_start_step": self.analyzed_start_step,
            "analyzed_end_step": self.analyzed_end_step,
            "analyzed_frame_count": self.analyzed_frame_count,
            "series": [row.to_dict() for row in self.series],
            "metrics": [row.to_dict() for row in self.metrics],
            "failure_rows": list(self.failure_rows),
            "passed": self.passed,
            "source_checkpoint_sha256": self.source_checkpoint_sha256,
            "restarted_checkpoint_sha256": self.restarted_checkpoint_sha256,
            "source_trajectory_head_sha256": (
                self.source_trajectory_head_sha256
            ),
            "source_barostat_head_sha256": self.source_barostat_head_sha256,
            "scientific_blockers": list(self.scientific_blockers),
            "claim_safe": False,
        }
        return {**payload, "result_sha256": _canonical_sha256(payload)}


def _series_statistics(
    series_id: str,
    values: list[float],
    *,
    confidence_level: float,
    target: float | None = None,
) -> ReferenceEnsembleSeriesStatistics:
    if len(values) < 2:
        raise ReferenceEnsembleStatisticsError(
            f"series {series_id} requires at least two samples"
        )
    rows = [_finite_float(item, name=f"{series_id} sample") for item in values]
    count = len(rows)
    mean = math.fsum(rows) / count
    centered = [item - mean for item in rows]
    sum_squares = math.fsum(item * item for item in centered)
    sample_variance = sum_squares / (count - 1)
    population_variance = sum_squares / count
    autocorrelation_sum = 0.0
    if population_variance > 0.0:
        for lag in range(1, min(count - 1, count // 2) + 1):
            covariance = math.fsum(
                centered[index] * centered[index + lag]
                for index in range(count - lag)
            ) / (count - lag)
            correlation = covariance / population_variance
            if correlation <= 0.0:
                break
            autocorrelation_sum += correlation
    integrated_time = max(1.0, 1.0 + 2.0 * autocorrelation_sum)
    effective_count = min(float(count), count / integrated_time)
    standard_deviation = math.sqrt(max(0.0, sample_variance))
    standard_error = standard_deviation / math.sqrt(effective_count)
    quantile = NormalDist().inv_cdf(0.5 + confidence_level / 2.0)
    half_width = quantile * standard_error
    return ReferenceEnsembleSeriesStatistics(
        series_id=series_id,
        sample_count=count,
        mean=mean,
        sample_standard_deviation=standard_deviation,
        minimum=min(rows),
        maximum=max(rows),
        integrated_autocorrelation_time=integrated_time,
        effective_sample_size=effective_count,
        standard_error=standard_error,
        confidence_level=confidence_level,
        confidence_interval_low=mean - half_width,
        confidence_interval_high=mean + half_width,
        target=target,
    )


def _restart_equality(
    uninterrupted: ReferenceCanonicalEnsembleResult,
    restarted: ReferenceCanonicalEnsembleResult,
) -> ReferenceEnsembleRestartEquality:
    first = uninterrupted.checkpoint
    second = restarted.checkpoint
    return ReferenceEnsembleRestartEquality(
        same_end_step=uninterrupted.end_step == restarted.end_step,
        same_coordinates=torch.equal(first.coordinates, second.coordinates),
        same_velocities=torch.equal(
            first.velocities_angstrom_per_ps,
            second.velocities_angstrom_per_ps,
        ),
        same_cell=first.cell_lengths_angstrom == second.cell_lengths_angstrom,
        same_energies=(
            first.current_potential_energy_kcal_per_mol.hex()
            == second.current_potential_energy_kcal_per_mol.hex()
            and first.current_kinetic_energy_kcal_per_mol.hex()
            == second.current_kinetic_energy_kcal_per_mol.hex()
            and first.current_total_energy_kcal_per_mol.hex()
            == second.current_total_energy_kcal_per_mol.hex()
        ),
        same_temperature=(
            first.current_kinetic_temperature_kelvin.hex()
            == second.current_kinetic_temperature_kelvin.hex()
        ),
        same_pressure_observation=(
            first.current_instantaneous_pressure_bar
            == second.current_instantaneous_pressure_bar
        ),
        same_random_word_index=(
            first.random_word_index == second.random_word_index
        ),
        same_trajectory_head=(
            first.trajectory_head_sha256 == second.trajectory_head_sha256
        ),
        same_barostat_head=(
            first.barostat_head_sha256 == second.barostat_head_sha256
        ),
        same_checkpoint_sha256=(
            first.checkpoint_sha256 == second.checkpoint_sha256
        ),
        uninterrupted_checkpoint_sha256=first.checkpoint_sha256,
        restarted_checkpoint_sha256=second.checkpoint_sha256,
    )


def _metric(
    metric_id: str,
    observed: float,
    threshold: float,
    comparison: str,
) -> ReferenceEnsembleMetric:
    passed = {
        "less_or_equal": observed <= threshold,
        "greater_or_equal": observed >= threshold,
        "equal": observed == threshold,
    }[comparison]
    return ReferenceEnsembleMetric(
        metric_id=metric_id,
        observed=observed,
        threshold=threshold,
        comparison=comparison,
        passed=passed,
    )


def analyze_reference_ensemble_statistics(
    uninterrupted: ReferenceCanonicalEnsembleResult,
    restarted: ReferenceCanonicalEnsembleResult,
    acceptance_config: ReferenceEnsembleStatisticsAcceptanceConfig,
) -> ReferenceEnsembleStatisticsResult:
    """Analyze one all-step fresh run and its genuine pause/resume endpoint."""

    if not isinstance(uninterrupted, ReferenceCanonicalEnsembleResult) or not isinstance(
        restarted,
        ReferenceCanonicalEnsembleResult,
    ):
        raise ReferenceEnsembleStatisticsError(
            "ensemble statistics inputs must be canonical-ensemble results"
        )
    if not isinstance(
        acceptance_config,
        ReferenceEnsembleStatisticsAcceptanceConfig,
    ):
        raise ReferenceEnsembleStatisticsError(
            "acceptance_config type is invalid"
        )
    if uninterrupted.start_step != 0:
        raise ReferenceEnsembleStatisticsError(
            "ensemble statistics require a fresh uninterrupted run"
        )
    if not 0 < restarted.start_step < restarted.end_step:
        raise ReferenceEnsembleStatisticsError(
            "restart comparison requires a genuine pause/resume segment"
        )
    if uninterrupted.end_step != restarted.end_step:
        raise ReferenceEnsembleStatisticsError(
            "uninterrupted and restarted endpoints differ"
        )
    first_config = uninterrupted.checkpoint.config
    second_config = restarted.checkpoint.config
    if first_config.fingerprint_sha256 != second_config.fingerprint_sha256:
        raise ReferenceEnsembleStatisticsError(
            "uninterrupted and restarted configs differ"
        )
    if uninterrupted.provenance.to_dict() != restarted.provenance.to_dict():
        raise ReferenceEnsembleStatisticsError(
            "uninterrupted and restarted provenance differ"
        )
    if first_config.trajectory_stride != 1:
        raise ReferenceEnsembleStatisticsError(
            "ensemble statistics require trajectory_stride=1"
        )
    if len(uninterrupted.frames) != uninterrupted.end_step + 1:
        raise ReferenceEnsembleStatisticsError(
            "fresh all-step ensemble trace is incomplete"
        )
    if any(
        frame.step != index
        for index, frame in enumerate(uninterrupted.frames)
    ):
        raise ReferenceEnsembleStatisticsError(
            "fresh ensemble frame steps are not contiguous"
        )
    burn = acceptance_config.burn_in_steps
    if burn >= uninterrupted.end_step:
        raise ReferenceEnsembleStatisticsError(
            "burn_in_steps leaves fewer than two analyzed frames"
        )
    analyzed = list(uninterrupted.frames[burn:])
    if len(analyzed) < 2:
        raise ReferenceEnsembleStatisticsError(
            "ensemble statistics require at least two analyzed frames"
        )
    restart = _restart_equality(uninterrupted, restarted)
    target_temperature = first_config.thermostat.temperature_kelvin
    series = [
        _series_statistics(
            "potential_energy_kcal_per_mol",
            [frame.potential_energy_kcal_per_mol for frame in analyzed],
            confidence_level=acceptance_config.confidence_level,
        ),
        _series_statistics(
            "kinetic_energy_kcal_per_mol",
            [frame.kinetic_energy_kcal_per_mol for frame in analyzed],
            confidence_level=acceptance_config.confidence_level,
        ),
        _series_statistics(
            "total_energy_kcal_per_mol",
            [frame.total_energy_kcal_per_mol for frame in analyzed],
            confidence_level=acceptance_config.confidence_level,
        ),
        _series_statistics(
            "kinetic_temperature_kelvin",
            [frame.kinetic_temperature_kelvin for frame in analyzed],
            confidence_level=acceptance_config.confidence_level,
            target=target_temperature,
        ),
    ]
    temperature = series[-1]
    metrics = [
        _metric(
            "exact_checkpoint_restart_equality",
            1.0 if restart.exact else 0.0,
            1.0,
            "equal",
        ),
        _metric(
            "temperature_absolute_bias_kelvin",
            abs(temperature.mean - target_temperature),
            acceptance_config.max_abs_temperature_bias_kelvin,
            "less_or_equal",
        ),
        _metric(
            "temperature_effective_sample_size",
            temperature.effective_sample_size,
            acceptance_config.min_temperature_effective_sample_size,
            "greater_or_equal",
        ),
        _metric(
            "temperature_target_inside_confidence_interval",
            1.0
            if temperature.target_inside_confidence_interval
            or not acceptance_config.require_temperature_target_inside_confidence_interval
            else 0.0,
            1.0,
            "equal",
        ),
        _metric(
            "max_position_constraint_residual_angstrom",
            uninterrupted.checkpoint.max_abs_position_constraint_residual_angstrom,
            acceptance_config.max_position_constraint_residual_angstrom,
            "less_or_equal",
        ),
        _metric(
            "max_velocity_constraint_residual_angstrom_per_ps",
            uninterrupted.checkpoint.max_abs_velocity_constraint_residual_angstrom_per_ps,
            acceptance_config.max_velocity_constraint_residual_angstrom_per_ps,
            "less_or_equal",
        ),
    ]
    ensemble = first_config.ensemble
    if ensemble == "NPT":
        barostat = first_config.barostat
        assert barostat is not None
        if barostat.pressure_observation_stride != 1:
            raise ReferenceEnsembleStatisticsError(
                "NPT statistics require pressure_observation_stride=1"
            )
        volumes = [frame.volume_angstrom3 for frame in analyzed]
        pressures = [frame.instantaneous_pressure_bar for frame in analyzed]
        if any(value is None for value in volumes) or any(
            value is None for value in pressures
        ):
            raise ReferenceEnsembleStatisticsError(
                "NPT all-step volume or pressure trace is incomplete"
            )
        volume = _series_statistics(
            "volume_angstrom3",
            [float(value) for value in volumes if value is not None],
            confidence_level=acceptance_config.confidence_level,
        )
        pressure = _series_statistics(
            "instantaneous_pressure_bar",
            [float(value) for value in pressures if value is not None],
            confidence_level=acceptance_config.confidence_level,
            target=barostat.pressure_bar,
        )
        series.extend((volume, pressure))
        attempts = uninterrupted.checkpoint.cumulative_barostat_attempt_count
        acceptance_fraction = (
            0.0
            if attempts == 0
            else uninterrupted.checkpoint.cumulative_barostat_accept_count
            / attempts
        )
        metrics.extend(
            (
                _metric(
                    "pressure_absolute_bias_bar",
                    abs(pressure.mean - barostat.pressure_bar),
                    acceptance_config.max_abs_pressure_bias_bar,
                    "less_or_equal",
                ),
                _metric(
                    "pressure_effective_sample_size",
                    pressure.effective_sample_size,
                    acceptance_config.min_pressure_effective_sample_size,
                    "greater_or_equal",
                ),
                _metric(
                    "pressure_target_inside_confidence_interval",
                    1.0
                    if pressure.target_inside_confidence_interval
                    or not acceptance_config.require_pressure_target_inside_confidence_interval
                    else 0.0,
                    1.0,
                    "equal",
                ),
                _metric(
                    "barostat_acceptance_fraction_minimum",
                    acceptance_fraction,
                    acceptance_config.min_barostat_acceptance_fraction,
                    "greater_or_equal",
                ),
                _metric(
                    "barostat_acceptance_fraction_maximum",
                    acceptance_fraction,
                    acceptance_config.max_barostat_acceptance_fraction,
                    "less_or_equal",
                ),
                _metric(
                    "minimum_barostat_attempt_count",
                    float(attempts),
                    float(acceptance_config.min_barostat_attempt_count),
                    "greater_or_equal",
                ),
            )
        )
    return ReferenceEnsembleStatisticsResult(
        ensemble=ensemble,
        acceptance_config=acceptance_config,
        restart_equality=restart,
        series=tuple(series),
        metrics=tuple(metrics),
        burn_in_steps=burn,
        analyzed_start_step=analyzed[0].step,
        analyzed_end_step=analyzed[-1].step,
        analyzed_frame_count=len(analyzed),
        source_checkpoint_sha256=uninterrupted.checkpoint.checkpoint_sha256,
        restarted_checkpoint_sha256=restarted.checkpoint.checkpoint_sha256,
        source_trajectory_head_sha256=(
            uninterrupted.checkpoint.trajectory_head_sha256
        ),
        source_barostat_head_sha256=(
            uninterrupted.checkpoint.barostat_head_sha256
        ),
    )


__all__ = [
    "REFERENCE_ENSEMBLE_COMMON_METRIC_IDS",
    "REFERENCE_ENSEMBLE_METRIC_SCHEMA_ID",
    "REFERENCE_ENSEMBLE_NPT_METRIC_IDS",
    "REFERENCE_ENSEMBLE_RESTART_EQUALITY_SCHEMA_ID",
    "REFERENCE_ENSEMBLE_SERIES_IDS",
    "REFERENCE_ENSEMBLE_SERIES_STATISTICS_SCHEMA_ID",
    "REFERENCE_ENSEMBLE_STATISTICS_ACCEPTANCE_SCHEMA_ID",
    "REFERENCE_ENSEMBLE_STATISTICS_ALGORITHM_ID",
    "REFERENCE_ENSEMBLE_STATISTICS_RESULT_SCHEMA_ID",
    "REFERENCE_ENSEMBLE_STATISTICS_SCIENTIFIC_BLOCKERS",
    "ReferenceEnsembleMetric",
    "ReferenceEnsembleRestartEquality",
    "ReferenceEnsembleSeriesStatistics",
    "ReferenceEnsembleStatisticsAcceptanceConfig",
    "ReferenceEnsembleStatisticsError",
    "ReferenceEnsembleStatisticsResult",
    "analyze_reference_ensemble_statistics",
]
