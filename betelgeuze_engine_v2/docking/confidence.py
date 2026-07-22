"""Claim-closed pose-ranking confidence, abstention, and selective-risk evidence.

The confidence signal is the logistic transform of the score margin between the
top-ranked pose and its runner-up.  It is useful for evaluating whether a raw
ranking margin behaves like confidence, but it is not a probability calibrator:
no disjoint calibration fit is performed here.  Every report says so explicitly
and retains failed/unscored cases in coverage denominators.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
import random
from typing import Callable, Sequence

from .calibration import (
    MAX_BOOTSTRAP_SAMPLES,
    POSE_RANKING_EVALUATION_SCHEMA_ID,
    PoseRankingCaseEvaluation,
    PoseRankingEvaluationReport,
)


POSE_RANKING_CONFIDENCE_EVALUATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_pose_ranking_confidence_evaluation/1.0.0"
)
POSE_RANKING_MARGIN_CONFIDENCE_SIGNAL_ID = (
    "pairwise_logistic_top1_runner_up_score_margin_proxy"
)

MAX_CONFIDENCE_BINS = 100
MAX_SELECTIVE_COVERAGE_TARGETS = 20
MAX_CONFIDENCE_BOOTSTRAP_WORK_ITEMS = 25_000_000

_REPORT_BLOCKERS = (
    "raw_pairwise_margin_is_not_disjoint_probability_calibrator",
    "confidence_acceptance_threshold_not_independently_reviewed",
    "public_dataset_result_not_established",
    "independent_external_rerun_missing",
    "scientific_review_missing",
)
_CASE_BOOTSTRAP_NO_VALID = "case_cluster_bootstrap_no_valid_replicates"
_CASE_BOOTSTRAP_DROPPED = (
    "case_cluster_bootstrap_dropped_unavailable_replicates"
)


class PoseRankingConfidenceError(ValueError):
    """A confidence-evaluation input or evidence invariant failed closed."""


def _token(value: object, *, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PoseRankingConfidenceError(f"{name} must be non-empty")
    return text


def _finite_float(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PoseRankingConfidenceError(f"{name} must be a finite real number")
    number = float(value)
    if not math.isfinite(number):
        raise PoseRankingConfidenceError(f"{name} must be finite")
    return number


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PoseRankingConfidenceError(f"{name} must be an integer")
    integer = int(value)
    if integer < minimum or (maximum is not None and integer > maximum):
        upper = "" if maximum is None else f" and at most {maximum}"
        raise PoseRankingConfidenceError(
            f"{name} must be at least {minimum}{upper}"
        )
    return integer


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PoseRankingConfidenceError(f"{name} must be a SHA-256 string")
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise PoseRankingConfidenceError(f"{name} must be a lowercase SHA-256")
    return digest


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class PoseRankingConfidenceEvaluationConfig:
    confidence_threshold: float = 0.75
    bin_count: int = 10
    selective_coverage_targets: tuple[float, ...] = (0.25, 0.5, 0.75, 1.0)
    confidence_level: float = 0.95
    bootstrap_samples: int = 2_000
    seed: int = 9151

    def __post_init__(self) -> None:
        threshold = _finite_float(
            self.confidence_threshold,
            name="confidence_threshold",
        )
        if not 0.5 <= threshold <= 1.0:
            raise PoseRankingConfidenceError(
                "confidence_threshold must be in [0.5,1]"
            )
        object.__setattr__(self, "confidence_threshold", threshold)
        object.__setattr__(
            self,
            "bin_count",
            _exact_int(
                self.bin_count,
                name="bin_count",
                minimum=1,
                maximum=MAX_CONFIDENCE_BINS,
            ),
        )
        targets = tuple(
            _finite_float(value, name="selective coverage target")
            for value in self.selective_coverage_targets
        )
        if (
            not targets
            or len(targets) > MAX_SELECTIVE_COVERAGE_TARGETS
            or len(targets) != len(set(targets))
            or targets != tuple(sorted(targets))
            or any(not 0.0 < value <= 1.0 for value in targets)
        ):
            raise PoseRankingConfidenceError(
                "selective_coverage_targets must be 1..20 unique ascending values in (0,1]"
            )
        object.__setattr__(self, "selective_coverage_targets", targets)
        level = _finite_float(self.confidence_level, name="confidence_level")
        if not 0.0 < level < 1.0:
            raise PoseRankingConfidenceError("confidence_level must be in (0,1)")
        object.__setattr__(self, "confidence_level", level)
        object.__setattr__(
            self,
            "bootstrap_samples",
            _exact_int(
                self.bootstrap_samples,
                name="bootstrap_samples",
                minimum=1,
                maximum=MAX_BOOTSTRAP_SAMPLES,
            ),
        )
        object.__setattr__(self, "seed", _exact_int(self.seed, name="seed"))

    def to_dict(self) -> dict[str, object]:
        return {
            "confidence_threshold": self.confidence_threshold,
            "bin_count": self.bin_count,
            "selective_coverage_targets": list(self.selective_coverage_targets),
            "confidence_level": self.confidence_level,
            "bootstrap_samples": self.bootstrap_samples,
            "seed": self.seed,
        }


def _margin_confidence(margin: float) -> float:
    return float(1.0 / (1.0 + math.exp(-margin)))


@dataclass(frozen=True)
class PoseRankingConfidenceCaseEvaluation:
    case_id: str
    target_id: str
    target_family: str
    total_pose_count: int
    successful_pose_count: int
    failed_pose_count: int
    top1_native_like: bool
    score_margin: float | None
    confidence: float | None
    decision: str
    abstention_reason: str = ""

    def __post_init__(self) -> None:
        for name in ("case_id", "target_id", "target_family"):
            object.__setattr__(self, name, _token(getattr(self, name), name=name))
        total = _exact_int(self.total_pose_count, name="total_pose_count", minimum=1)
        successful = _exact_int(
            self.successful_pose_count,
            name="successful_pose_count",
        )
        failed = _exact_int(self.failed_pose_count, name="failed_pose_count")
        if successful + failed != total:
            raise PoseRankingConfidenceError(
                "confidence case pose counts must reconcile"
            )
        if type(self.top1_native_like) is not bool:
            raise PoseRankingConfidenceError("top1_native_like must be boolean")
        decision = _token(self.decision, name="decision")
        if decision not in {"accepted", "abstained"}:
            raise PoseRankingConfidenceError(
                "confidence decision must be accepted or abstained"
            )
        reason = str(self.abstention_reason or "").strip()
        if self.confidence is None:
            if (
                self.score_margin is not None
                or decision != "abstained"
                or reason
                not in {
                    "insufficient_successful_poses_for_margin",
                    "nonfinite_top1_runner_up_margin",
                }
            ):
                raise PoseRankingConfidenceError(
                    "unavailable confidence must be an explained abstention"
                )
        else:
            margin = _finite_float(self.score_margin, name="score_margin")
            confidence = _finite_float(self.confidence, name="confidence")
            if margin < 0.0 or not 0.5 <= confidence <= 1.0:
                raise PoseRankingConfidenceError(
                    "available confidence requires a non-negative margin and value in [0.5,1]"
                )
            if confidence != _margin_confidence(margin):
                raise PoseRankingConfidenceError(
                    "confidence does not match the logistic score-margin transform"
                )
            if (decision == "accepted") != (reason == ""):
                raise PoseRankingConfidenceError(
                    "accepted confidence must omit an abstention reason"
                )
            if decision == "abstained" and reason != "below_confidence_threshold":
                raise PoseRankingConfidenceError(
                    "available abstention requires the threshold reason"
                )
            object.__setattr__(self, "score_margin", margin)
            object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "total_pose_count", total)
        object.__setattr__(self, "successful_pose_count", successful)
        object.__setattr__(self, "failed_pose_count", failed)
        object.__setattr__(self, "decision", decision)
        object.__setattr__(self, "abstention_reason", reason)

    @property
    def squared_error(self) -> float | None:
        if self.confidence is None:
            return None
        outcome = 1.0 if self.top1_native_like else 0.0
        return float((self.confidence - outcome) ** 2)

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "target_id": self.target_id,
            "target_family": self.target_family,
            "total_pose_count": self.total_pose_count,
            "successful_pose_count": self.successful_pose_count,
            "failed_pose_count": self.failed_pose_count,
            "top1_native_like": self.top1_native_like,
            "score_margin": self.score_margin,
            "confidence": self.confidence,
            "squared_error": self.squared_error,
            "decision": self.decision,
            "abstention_reason": self.abstention_reason,
        }


@dataclass(frozen=True)
class PoseRankingReliabilityBin:
    bin_index: int
    confidence_low: float
    confidence_high: float
    confidence_high_inclusive: bool
    row_count: int
    confidence_available_case_denominator: int
    mean_confidence: float | None
    top1_native_like_rate: float | None
    absolute_calibration_gap: float | None

    def __post_init__(self) -> None:
        index = _exact_int(self.bin_index, name="bin_index")
        low = _finite_float(self.confidence_low, name="confidence_low")
        high = _finite_float(self.confidence_high, name="confidence_high")
        count = _exact_int(self.row_count, name="bin row_count")
        denominator = _exact_int(
            self.confidence_available_case_denominator,
            name="confidence_available_case_denominator",
        )
        if not 0.0 <= low < high <= 1.0 or count > denominator:
            raise PoseRankingConfidenceError("reliability bin bounds or counts are invalid")
        if type(self.confidence_high_inclusive) is not bool:
            raise PoseRankingConfidenceError(
                "confidence_high_inclusive must be boolean"
            )
        if count == 0:
            if any(
                value is not None
                for value in (
                    self.mean_confidence,
                    self.top1_native_like_rate,
                    self.absolute_calibration_gap,
                )
            ):
                raise PoseRankingConfidenceError(
                    "empty reliability bins must omit estimates"
                )
        else:
            mean = _finite_float(self.mean_confidence, name="mean_confidence")
            rate = _finite_float(
                self.top1_native_like_rate,
                name="top1_native_like_rate",
            )
            gap = _finite_float(
                self.absolute_calibration_gap,
                name="absolute_calibration_gap",
            )
            if (
                not low <= mean <= high
                or not 0.0 <= rate <= 1.0
                or not 0.0 <= gap <= 1.0
                or gap != abs(mean - rate)
            ):
                raise PoseRankingConfidenceError(
                    "reliability bin estimates are inconsistent"
                )
            object.__setattr__(self, "mean_confidence", mean)
            object.__setattr__(self, "top1_native_like_rate", rate)
            object.__setattr__(self, "absolute_calibration_gap", gap)
        object.__setattr__(self, "bin_index", index)
        object.__setattr__(self, "confidence_low", low)
        object.__setattr__(self, "confidence_high", high)
        object.__setattr__(self, "row_count", count)
        object.__setattr__(
            self,
            "confidence_available_case_denominator",
            denominator,
        )

    @property
    def weight(self) -> float:
        if self.confidence_available_case_denominator == 0:
            return 0.0
        return float(self.row_count) / float(
            self.confidence_available_case_denominator
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "bin_index": self.bin_index,
            "confidence_low": self.confidence_low,
            "confidence_high": self.confidence_high,
            "confidence_high_inclusive": self.confidence_high_inclusive,
            "row_count": self.row_count,
            "confidence_available_case_denominator": (
                self.confidence_available_case_denominator
            ),
            "weight": self.weight,
            "mean_confidence": self.mean_confidence,
            "top1_native_like_rate": self.top1_native_like_rate,
            "absolute_calibration_gap": self.absolute_calibration_gap,
        }


@dataclass(frozen=True)
class PoseRankingConfidenceMetricEstimate:
    metric_id: str
    value: float | None
    confidence_interval_low: float | None
    confidence_interval_high: float | None
    confidence_level: float
    all_case_denominator: int
    contributing_case_count: int
    bootstrap_unit: str
    bootstrap_requested_sample_count: int
    bootstrap_valid_sample_count: int
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_id", _token(self.metric_id, name="metric_id"))
        level = _finite_float(self.confidence_level, name="confidence_level")
        if not 0.0 < level < 1.0:
            raise PoseRankingConfidenceError("confidence_level must be in (0,1)")
        denominator = _exact_int(
            self.all_case_denominator,
            name="all_case_denominator",
            minimum=1,
        )
        contributing = _exact_int(
            self.contributing_case_count,
            name="contributing_case_count",
            maximum=denominator,
        )
        requested = _exact_int(
            self.bootstrap_requested_sample_count,
            name="bootstrap_requested_sample_count",
            minimum=1,
            maximum=MAX_BOOTSTRAP_SAMPLES,
        )
        valid = _exact_int(
            self.bootstrap_valid_sample_count,
            name="bootstrap_valid_sample_count",
            maximum=requested,
        )
        if self.bootstrap_unit != "case":
            raise PoseRankingConfidenceError("bootstrap_unit must be case")
        blockers = tuple(_token(value, name="metric blocker") for value in self.blockers)
        if len(blockers) != len(set(blockers)):
            raise PoseRankingConfidenceError("metric blockers must be unique")
        no_valid = _CASE_BOOTSTRAP_NO_VALID in blockers
        dropped = _CASE_BOOTSTRAP_DROPPED in blockers
        if self.value is None:
            if (
                self.confidence_interval_low is not None
                or self.confidence_interval_high is not None
                or valid != 0
                or not blockers
            ):
                raise PoseRankingConfidenceError(
                    "unavailable confidence metric evidence is inconsistent"
                )
        else:
            value = _finite_float(self.value, name="metric value")
            if not 0.0 <= value <= 1.0:
                raise PoseRankingConfidenceError("metric value must be in [0,1]")
            object.__setattr__(self, "value", value)
            if valid == 0:
                if (
                    self.confidence_interval_low is not None
                    or self.confidence_interval_high is not None
                    or not no_valid
                    or dropped
                ):
                    raise PoseRankingConfidenceError(
                        "metric with no valid bootstrap replicates is inconsistent"
                    )
            else:
                low = _finite_float(
                    self.confidence_interval_low,
                    name="confidence_interval_low",
                )
                high = _finite_float(
                    self.confidence_interval_high,
                    name="confidence_interval_high",
                )
                if not 0.0 <= low <= high <= 1.0 or no_valid:
                    raise PoseRankingConfidenceError(
                        "confidence metric interval is invalid"
                    )
                if (valid < requested) != dropped:
                    raise PoseRankingConfidenceError(
                        "bootstrap count and dropped-replicate blocker disagree"
                    )
                object.__setattr__(self, "confidence_interval_low", low)
                object.__setattr__(self, "confidence_interval_high", high)
        object.__setattr__(self, "confidence_level", level)
        object.__setattr__(self, "all_case_denominator", denominator)
        object.__setattr__(self, "contributing_case_count", contributing)
        object.__setattr__(self, "bootstrap_requested_sample_count", requested)
        object.__setattr__(self, "bootstrap_valid_sample_count", valid)
        object.__setattr__(self, "blockers", blockers)

    @property
    def available(self) -> bool:
        return self.value is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "metric_id": self.metric_id,
            "value": self.value,
            "confidence_interval_low": self.confidence_interval_low,
            "confidence_interval_high": self.confidence_interval_high,
            "confidence_level": self.confidence_level,
            "all_case_denominator": self.all_case_denominator,
            "contributing_case_count": self.contributing_case_count,
            "bootstrap_unit": self.bootstrap_unit,
            "bootstrap_requested_sample_count": self.bootstrap_requested_sample_count,
            "bootstrap_valid_sample_count": self.bootstrap_valid_sample_count,
            "available": self.available,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class PoseRankingSelectiveRiskPoint:
    target_coverage: float
    achieved_coverage: float | None
    confidence_cutoff: float | None
    selected_case_ids: tuple[str, ...]
    top1_error_count: int
    risk: PoseRankingConfidenceMetricEstimate

    def __post_init__(self) -> None:
        target = _finite_float(self.target_coverage, name="target_coverage")
        if not 0.0 < target <= 1.0:
            raise PoseRankingConfidenceError("target_coverage must be in (0,1]")
        if not isinstance(self.risk, PoseRankingConfidenceMetricEstimate):
            raise PoseRankingConfidenceError("selective risk metric type is invalid")
        selected = tuple(
            _token(value, name="selected case ID") for value in self.selected_case_ids
        )
        if selected != tuple(sorted(selected)) or len(selected) != len(set(selected)):
            raise PoseRankingConfidenceError(
                "selected case IDs must be unique and canonically ordered"
            )
        errors = _exact_int(
            self.top1_error_count,
            name="top1_error_count",
            maximum=len(selected),
        )
        if self.risk.contributing_case_count != len(selected):
            raise PoseRankingConfidenceError(
                "selective-risk contributor count disagrees with selected cases"
            )
        if self.risk.value is None:
            if (
                self.achieved_coverage is not None
                or self.confidence_cutoff is not None
                or selected
                or errors
            ):
                raise PoseRankingConfidenceError(
                    "unavailable selective-risk point must omit selection evidence"
                )
        else:
            achieved = _finite_float(
                self.achieved_coverage,
                name="achieved_coverage",
            )
            cutoff = _finite_float(self.confidence_cutoff, name="confidence_cutoff")
            if (
                not target <= achieved <= 1.0
                or not 0.5 <= cutoff <= 1.0
                or achieved
                != float(len(selected)) / float(self.risk.all_case_denominator)
                or self.risk.value != float(errors) / float(len(selected))
            ):
                raise PoseRankingConfidenceError(
                    "selective-risk selection evidence is inconsistent"
                )
            object.__setattr__(self, "achieved_coverage", achieved)
            object.__setattr__(self, "confidence_cutoff", cutoff)
        object.__setattr__(self, "target_coverage", target)
        object.__setattr__(self, "selected_case_ids", selected)
        object.__setattr__(self, "top1_error_count", errors)

    def to_dict(self) -> dict[str, object]:
        return {
            "target_coverage": self.target_coverage,
            "achieved_coverage": self.achieved_coverage,
            "confidence_cutoff": self.confidence_cutoff,
            "selected_case_ids": list(self.selected_case_ids),
            "top1_error_count": self.top1_error_count,
            "risk": self.risk.to_dict(),
        }


@dataclass(frozen=True)
class PoseRankingConfidenceScopeEvaluation:
    scope_id: str
    target_family: str | None
    all_case_denominator: int
    all_pose_denominator: int
    failed_pose_count: int
    confidence_available_case_count: int
    confidence_unavailable_case_count: int
    accepted_case_count: int
    abstained_case_count: int
    positive_confidence_outcome_count: int
    negative_confidence_outcome_count: int
    reliability_bins: tuple[PoseRankingReliabilityBin, ...]
    metrics: tuple[PoseRankingConfidenceMetricEstimate, ...]
    selective_risk_curve: tuple[PoseRankingSelectiveRiskPoint, ...]
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        scope = _token(self.scope_id, name="scope_id")
        family = None
        if self.target_family is not None:
            family = _token(self.target_family, name="target_family")
        denominator = _exact_int(
            self.all_case_denominator,
            name="all_case_denominator",
            minimum=1,
        )
        all_pose = _exact_int(
            self.all_pose_denominator,
            name="all_pose_denominator",
            minimum=1,
        )
        failed_pose = _exact_int(
            self.failed_pose_count,
            name="failed_pose_count",
            maximum=all_pose,
        )
        available = _exact_int(
            self.confidence_available_case_count,
            name="confidence_available_case_count",
            maximum=denominator,
        )
        unavailable = _exact_int(
            self.confidence_unavailable_case_count,
            name="confidence_unavailable_case_count",
            maximum=denominator,
        )
        accepted = _exact_int(
            self.accepted_case_count,
            name="accepted_case_count",
            maximum=denominator,
        )
        abstained = _exact_int(
            self.abstained_case_count,
            name="abstained_case_count",
            maximum=denominator,
        )
        positive = _exact_int(
            self.positive_confidence_outcome_count,
            name="positive_confidence_outcome_count",
            maximum=available,
        )
        negative = _exact_int(
            self.negative_confidence_outcome_count,
            name="negative_confidence_outcome_count",
            maximum=available,
        )
        if (
            available + unavailable != denominator
            or accepted + abstained != denominator
            or positive + negative != available
            or accepted > available
        ):
            raise PoseRankingConfidenceError(
                "confidence scope case counts do not reconcile"
            )
        bins = tuple(self.reliability_bins)
        metrics = tuple(self.metrics)
        curve = tuple(self.selective_risk_curve)
        if any(not isinstance(row, PoseRankingReliabilityBin) for row in bins):
            raise PoseRankingConfidenceError("reliability bin type is invalid")
        if any(
            not isinstance(row, PoseRankingConfidenceMetricEstimate)
            for row in metrics
        ):
            raise PoseRankingConfidenceError("confidence metric type is invalid")
        if any(not isinstance(row, PoseRankingSelectiveRiskPoint) for row in curve):
            raise PoseRankingConfidenceError("selective-risk point type is invalid")
        expected_metric_ids = (
            "brier_score",
            "expected_calibration_error",
            "confidence_available_case_coverage",
            "threshold_accepted_case_coverage",
            "threshold_selective_risk",
        )
        if tuple(metric.metric_id for metric in metrics) != expected_metric_ids:
            raise PoseRankingConfidenceError(
                "confidence scope metrics are incomplete or out of order"
            )
        if any(
            metric.all_case_denominator != denominator for metric in metrics
        ) or any(
            point.risk.all_case_denominator != denominator for point in curve
        ):
            raise PoseRankingConfidenceError(
                "confidence scope metrics disagree with the all-case denominator"
            )
        blockers = tuple(_token(value, name="scope blocker") for value in self.blockers)
        if len(blockers) != len(set(blockers)):
            raise PoseRankingConfidenceError("scope blockers must be unique")
        object.__setattr__(self, "scope_id", scope)
        object.__setattr__(self, "target_family", family)
        object.__setattr__(self, "all_case_denominator", denominator)
        object.__setattr__(self, "all_pose_denominator", all_pose)
        object.__setattr__(self, "failed_pose_count", failed_pose)
        object.__setattr__(self, "confidence_available_case_count", available)
        object.__setattr__(self, "confidence_unavailable_case_count", unavailable)
        object.__setattr__(self, "accepted_case_count", accepted)
        object.__setattr__(self, "abstained_case_count", abstained)
        object.__setattr__(self, "positive_confidence_outcome_count", positive)
        object.__setattr__(self, "negative_confidence_outcome_count", negative)
        object.__setattr__(self, "reliability_bins", bins)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "selective_risk_curve", curve)
        object.__setattr__(self, "blockers", blockers)

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "scope_id": self.scope_id,
            "target_family": self.target_family,
            "all_case_denominator": self.all_case_denominator,
            "all_pose_denominator": self.all_pose_denominator,
            "failed_pose_count": self.failed_pose_count,
            "confidence_available_case_count": self.confidence_available_case_count,
            "confidence_unavailable_case_count": (
                self.confidence_unavailable_case_count
            ),
            "accepted_case_count": self.accepted_case_count,
            "abstained_case_count": self.abstained_case_count,
            "positive_confidence_outcome_count": (
                self.positive_confidence_outcome_count
            ),
            "negative_confidence_outcome_count": (
                self.negative_confidence_outcome_count
            ),
            "reliability_bins": [row.to_dict() for row in self.reliability_bins],
            "metrics": [metric.to_dict() for metric in self.metrics],
            "selective_risk_curve": [
                point.to_dict() for point in self.selective_risk_curve
            ],
            "blockers": list(self.blockers),
            "claim_safe": False,
        }


def _percentile_interval(
    values: Sequence[float],
    *,
    confidence_level: float,
) -> tuple[float, float]:
    ordered = sorted(values)
    alpha = (1.0 - confidence_level) / 2.0
    low_index = min(len(ordered) - 1, int(math.floor(alpha * len(ordered))))
    high_index = min(
        len(ordered) - 1,
        int(math.ceil((1.0 - alpha) * len(ordered))) - 1,
    )
    return float(ordered[low_index]), float(ordered[high_index])


def _bootstrap_values(
    cases: Sequence[PoseRankingConfidenceCaseEvaluation],
    *,
    measure: Callable[[Sequence[PoseRankingConfidenceCaseEvaluation]], float | None],
    config: PoseRankingConfidenceEvaluationConfig,
    scope: str,
) -> list[float]:
    seed = int.from_bytes(
        hashlib.sha256(f"{config.seed}:{scope}".encode("utf-8")).digest()[:8],
        "big",
    )
    generator = random.Random(seed)
    count = len(cases)
    values: list[float] = []
    for _ in range(config.bootstrap_samples):
        sample = tuple(cases[generator.randrange(count)] for _ in range(count))
        value = measure(sample)
        if value is not None:
            values.append(_finite_float(value, name="bootstrap metric value"))
    return values


def _metric(
    metric_id: str,
    cases: Sequence[PoseRankingConfidenceCaseEvaluation],
    *,
    contributing_case_count: int,
    measure: Callable[[Sequence[PoseRankingConfidenceCaseEvaluation]], float | None],
    config: PoseRankingConfidenceEvaluationConfig,
    scope: str,
    blockers: Sequence[str] = (),
) -> PoseRankingConfidenceMetricEstimate:
    point = measure(cases)
    active_blockers = list(blockers)
    valid_values: list[float] = []
    if point is None:
        active_blockers.append("metric_value_unavailable")
    else:
        valid_values = _bootstrap_values(
            cases,
            measure=measure,
            config=config,
            scope=f"{scope}:{metric_id}",
        )
        if not valid_values:
            active_blockers.append(_CASE_BOOTSTRAP_NO_VALID)
        elif len(valid_values) != config.bootstrap_samples:
            active_blockers.append(_CASE_BOOTSTRAP_DROPPED)
    low: float | None = None
    high: float | None = None
    if valid_values:
        low, high = _percentile_interval(
            valid_values,
            confidence_level=config.confidence_level,
        )
    return PoseRankingConfidenceMetricEstimate(
        metric_id=metric_id,
        value=point,
        confidence_interval_low=low,
        confidence_interval_high=high,
        confidence_level=config.confidence_level,
        all_case_denominator=len(cases),
        contributing_case_count=contributing_case_count,
        bootstrap_unit="case",
        bootstrap_requested_sample_count=config.bootstrap_samples,
        bootstrap_valid_sample_count=len(valid_values),
        blockers=tuple(dict.fromkeys(active_blockers)),
    )


def _available(
    cases: Sequence[PoseRankingConfidenceCaseEvaluation],
) -> list[PoseRankingConfidenceCaseEvaluation]:
    return [case for case in cases if case.confidence is not None]


def _accepted(
    cases: Sequence[PoseRankingConfidenceCaseEvaluation],
) -> list[PoseRankingConfidenceCaseEvaluation]:
    return [case for case in cases if case.decision == "accepted"]


def _brier(cases: Sequence[PoseRankingConfidenceCaseEvaluation]) -> float | None:
    values = [case.squared_error for case in cases if case.squared_error is not None]
    if not values:
        return None
    return float(math.fsum(values) / len(values))


def _ece(
    cases: Sequence[PoseRankingConfidenceCaseEvaluation],
    *,
    bin_count: int,
) -> float | None:
    rows = _available(cases)
    if not rows:
        return None
    total = len(rows)
    area = 0.0
    for index in range(bin_count):
        members = [
            case
            for case in rows
            if min(int(float(case.confidence) * bin_count), bin_count - 1)
            == index
        ]
        if not members:
            continue
        mean_confidence = math.fsum(float(case.confidence) for case in members) / len(
            members
        )
        accuracy = math.fsum(float(case.top1_native_like) for case in members) / len(
            members
        )
        area += float(len(members)) / float(total) * abs(mean_confidence - accuracy)
    return float(area)


def _confidence_coverage(
    cases: Sequence[PoseRankingConfidenceCaseEvaluation],
) -> float:
    return float(len(_available(cases))) / float(len(cases))


def _accepted_coverage(
    cases: Sequence[PoseRankingConfidenceCaseEvaluation],
) -> float:
    return float(len(_accepted(cases))) / float(len(cases))


def _threshold_risk(
    cases: Sequence[PoseRankingConfidenceCaseEvaluation],
) -> float | None:
    rows = _accepted(cases)
    if not rows:
        return None
    return float(sum(not case.top1_native_like for case in rows)) / float(len(rows))


def _reliability_bins(
    cases: Sequence[PoseRankingConfidenceCaseEvaluation],
    *,
    bin_count: int,
) -> tuple[PoseRankingReliabilityBin, ...]:
    available = _available(cases)
    rows: list[PoseRankingReliabilityBin] = []
    for index in range(bin_count):
        members = [
            case
            for case in available
            if min(int(float(case.confidence) * bin_count), bin_count - 1)
            == index
        ]
        mean: float | None = None
        rate: float | None = None
        gap: float | None = None
        if members:
            mean = float(
                math.fsum(float(case.confidence) for case in members) / len(members)
            )
            rate = float(
                math.fsum(float(case.top1_native_like) for case in members)
                / len(members)
            )
            gap = float(abs(mean - rate))
        rows.append(
            PoseRankingReliabilityBin(
                bin_index=index,
                confidence_low=float(index) / float(bin_count),
                confidence_high=float(index + 1) / float(bin_count),
                confidence_high_inclusive=index == bin_count - 1,
                row_count=len(members),
                confidence_available_case_denominator=len(available),
                mean_confidence=mean,
                top1_native_like_rate=rate,
                absolute_calibration_gap=gap,
            )
        )
    return tuple(rows)


@dataclass(frozen=True)
class _RiskSelection:
    risk: float
    achieved_coverage: float
    confidence_cutoff: float
    selected: tuple[PoseRankingConfidenceCaseEvaluation, ...]


def _risk_selection(
    cases: Sequence[PoseRankingConfidenceCaseEvaluation],
    *,
    target_coverage: float,
) -> _RiskSelection | None:
    required = int(math.ceil(target_coverage * len(cases)))
    eligible = sorted(
        _available(cases),
        key=lambda case: (-float(case.confidence), case.case_id),
    )
    if len(eligible) < required:
        return None
    cutoff = float(eligible[required - 1].confidence)
    selected = tuple(case for case in eligible if float(case.confidence) >= cutoff)
    errors = sum(not case.top1_native_like for case in selected)
    return _RiskSelection(
        risk=float(errors) / float(len(selected)),
        achieved_coverage=float(len(selected)) / float(len(cases)),
        confidence_cutoff=cutoff,
        selected=selected,
    )


def _selective_risk_point(
    cases: Sequence[PoseRankingConfidenceCaseEvaluation],
    *,
    target_coverage: float,
    config: PoseRankingConfidenceEvaluationConfig,
    scope: str,
) -> PoseRankingSelectiveRiskPoint:
    selection = _risk_selection(cases, target_coverage=target_coverage)

    def measure(
        rows: Sequence[PoseRankingConfidenceCaseEvaluation],
    ) -> float | None:
        sampled = _risk_selection(rows, target_coverage=target_coverage)
        return None if sampled is None else sampled.risk

    blockers: list[str] = []
    if selection is None:
        blockers.append("target_coverage_exceeds_confidence_available_coverage")
    risk = _metric(
        f"selective_risk_at_target_coverage_{target_coverage:.12g}",
        cases,
        contributing_case_count=(0 if selection is None else len(selection.selected)),
        measure=measure,
        config=config,
        scope=scope,
        blockers=blockers,
    )
    selected = () if selection is None else tuple(
        sorted(case.case_id for case in selection.selected)
    )
    errors = 0 if selection is None else sum(
        not case.top1_native_like for case in selection.selected
    )
    return PoseRankingSelectiveRiskPoint(
        target_coverage=target_coverage,
        achieved_coverage=None if selection is None else selection.achieved_coverage,
        confidence_cutoff=None if selection is None else selection.confidence_cutoff,
        selected_case_ids=selected,
        top1_error_count=errors,
        risk=risk,
    )


def _scope_evaluation(
    scope_id: str,
    cases: Sequence[PoseRankingConfidenceCaseEvaluation],
    *,
    target_family: str | None,
    config: PoseRankingConfidenceEvaluationConfig,
) -> PoseRankingConfidenceScopeEvaluation:
    available = _available(cases)
    accepted = _accepted(cases)
    positive = sum(case.top1_native_like for case in available)
    negative = len(available) - positive
    scope_blockers: list[str] = []
    calibration_blockers: list[str] = []
    if not available:
        scope_blockers.append("confidence_available_case_count_zero")
        calibration_blockers.append("confidence_available_case_count_zero")
    if positive == 0:
        scope_blockers.append("positive_confidence_outcome_missing")
        calibration_blockers.append("positive_confidence_outcome_missing")
    if negative == 0:
        scope_blockers.append("negative_confidence_outcome_missing")
        calibration_blockers.append("negative_confidence_outcome_missing")
    if not accepted:
        scope_blockers.append("threshold_accepted_case_count_zero")
    metrics = (
        _metric(
            "brier_score",
            cases,
            contributing_case_count=len(available),
            measure=_brier,
            config=config,
            scope=scope_id,
            blockers=calibration_blockers,
        ),
        _metric(
            "expected_calibration_error",
            cases,
            contributing_case_count=len(available),
            measure=lambda rows: _ece(rows, bin_count=config.bin_count),
            config=config,
            scope=scope_id,
            blockers=calibration_blockers,
        ),
        _metric(
            "confidence_available_case_coverage",
            cases,
            contributing_case_count=len(cases),
            measure=_confidence_coverage,
            config=config,
            scope=scope_id,
        ),
        _metric(
            "threshold_accepted_case_coverage",
            cases,
            contributing_case_count=len(cases),
            measure=_accepted_coverage,
            config=config,
            scope=scope_id,
        ),
        _metric(
            "threshold_selective_risk",
            cases,
            contributing_case_count=len(accepted),
            measure=_threshold_risk,
            config=config,
            scope=scope_id,
            blockers=(
                ()
                if accepted
                else ("threshold_accepted_case_count_zero",)
            ),
        ),
    )
    curve = tuple(
        _selective_risk_point(
            cases,
            target_coverage=target,
            config=config,
            scope=scope_id,
        )
        for target in config.selective_coverage_targets
    )
    if any(point.risk.value is None for point in curve):
        scope_blockers.append("selective_risk_target_coverage_unavailable")
    return PoseRankingConfidenceScopeEvaluation(
        scope_id=scope_id,
        target_family=target_family,
        all_case_denominator=len(cases),
        all_pose_denominator=sum(case.total_pose_count for case in cases),
        failed_pose_count=sum(case.failed_pose_count for case in cases),
        confidence_available_case_count=len(available),
        confidence_unavailable_case_count=len(cases) - len(available),
        accepted_case_count=len(accepted),
        abstained_case_count=len(cases) - len(accepted),
        positive_confidence_outcome_count=positive,
        negative_confidence_outcome_count=negative,
        reliability_bins=_reliability_bins(cases, bin_count=config.bin_count),
        metrics=metrics,
        selective_risk_curve=curve,
        blockers=tuple(scope_blockers),
    )


@dataclass(frozen=True)
class PoseRankingConfidenceEvaluationReport:
    pose_ranking_evaluation_sha256: str
    model_sha256: str
    evaluation_partition_sha256: str
    config: PoseRankingConfidenceEvaluationConfig
    cases: tuple[PoseRankingConfidenceCaseEvaluation, ...]
    overall: PoseRankingConfidenceScopeEvaluation
    families: tuple[PoseRankingConfidenceScopeEvaluation, ...]
    schema_id: str = POSE_RANKING_CONFIDENCE_EVALUATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSE_RANKING_CONFIDENCE_EVALUATION_SCHEMA_ID:
            raise PoseRankingConfidenceError(
                "unsupported pose-ranking confidence evaluation schema"
            )
        for name in (
            "pose_ranking_evaluation_sha256",
            "model_sha256",
            "evaluation_partition_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if not isinstance(self.config, PoseRankingConfidenceEvaluationConfig):
            raise PoseRankingConfidenceError("confidence evaluation config is invalid")
        cases = tuple(self.cases)
        if (
            not cases
            or any(
                not isinstance(case, PoseRankingConfidenceCaseEvaluation)
                for case in cases
            )
            or tuple(case.case_id for case in cases)
            != tuple(sorted(case.case_id for case in cases))
            or len({case.case_id for case in cases}) != len(cases)
        ):
            raise PoseRankingConfidenceError(
                "confidence cases must be non-empty, unique, and canonically ordered"
            )
        if not isinstance(self.overall, PoseRankingConfidenceScopeEvaluation):
            raise PoseRankingConfidenceError("overall confidence scope is invalid")
        families = tuple(self.families)
        if any(
            not isinstance(scope, PoseRankingConfidenceScopeEvaluation)
            for scope in families
        ):
            raise PoseRankingConfidenceError("family confidence scope is invalid")
        family_names = tuple(scope.target_family for scope in families)
        cases_by_family: dict[
            str,
            list[PoseRankingConfidenceCaseEvaluation],
        ] = {}
        for case in cases:
            cases_by_family.setdefault(case.target_family, []).append(case)
        expected_families = tuple(sorted(cases_by_family))
        if family_names != expected_families:
            raise PoseRankingConfidenceError(
                "confidence family scopes are incomplete or out of order"
            )
        self._validate_scope(self.overall, cases=cases, config=self.config)
        if self.overall.scope_id != "overall" or self.overall.target_family is not None:
            raise PoseRankingConfidenceError("overall confidence scope identity is invalid")
        for scope in families:
            family_cases = tuple(cases_by_family[str(scope.target_family)])
            if scope.scope_id != f"family:{scope.target_family}":
                raise PoseRankingConfidenceError(
                    "family confidence scope identity is invalid"
                )
            self._validate_scope(scope, cases=family_cases, config=self.config)
        object.__setattr__(self, "cases", cases)
        object.__setattr__(self, "families", families)

    @staticmethod
    def _validate_scope(
        scope: PoseRankingConfidenceScopeEvaluation,
        *,
        cases: Sequence[PoseRankingConfidenceCaseEvaluation],
        config: PoseRankingConfidenceEvaluationConfig,
    ) -> None:
        available = _available(cases)
        accepted = _accepted(cases)
        positive = sum(case.top1_native_like for case in available)
        expected_bins = _reliability_bins(cases, bin_count=config.bin_count)
        expected = (
            scope.all_case_denominator == len(cases)
            and scope.all_pose_denominator
            == sum(case.total_pose_count for case in cases)
            and scope.failed_pose_count == sum(case.failed_pose_count for case in cases)
            and scope.confidence_available_case_count == len(available)
            and scope.confidence_unavailable_case_count == len(cases) - len(available)
            and scope.accepted_case_count == len(accepted)
            and scope.abstained_case_count == len(cases) - len(accepted)
            and scope.positive_confidence_outcome_count == positive
            and scope.negative_confidence_outcome_count
            == len(available) - positive
            and scope.reliability_bins == expected_bins
            and tuple(point.target_coverage for point in scope.selective_risk_curve)
            == config.selective_coverage_targets
            and all(
                metric.confidence_level == config.confidence_level
                and metric.bootstrap_requested_sample_count
                == config.bootstrap_samples
                for metric in scope.metrics
            )
            and all(
                point.risk.confidence_level == config.confidence_level
                and point.risk.bootstrap_requested_sample_count
                == config.bootstrap_samples
                for point in scope.selective_risk_curve
            )
        )
        if not expected:
            raise PoseRankingConfidenceError(
                "confidence scope evidence disagrees with retained cases or config"
            )
        expected_metrics = (
            (len(available), _brier(cases)),
            (len(available), _ece(cases, bin_count=config.bin_count)),
            (len(cases), _confidence_coverage(cases)),
            (len(cases), _accepted_coverage(cases)),
            (len(accepted), _threshold_risk(cases)),
        )
        if any(
            metric.contributing_case_count != contributor_count
            or metric.value != value
            for metric, (contributor_count, value) in zip(
                scope.metrics,
                expected_metrics,
                strict=True,
            )
        ):
            raise PoseRankingConfidenceError(
                "confidence metric values disagree with retained cases"
            )
        expected_scope_blockers: list[str] = []
        if not available:
            expected_scope_blockers.append("confidence_available_case_count_zero")
        if positive == 0:
            expected_scope_blockers.append("positive_confidence_outcome_missing")
        if len(available) - positive == 0:
            expected_scope_blockers.append("negative_confidence_outcome_missing")
        if not accepted:
            expected_scope_blockers.append("threshold_accepted_case_count_zero")
        unavailable_curve_point = False
        for point in scope.selective_risk_curve:
            selection = _risk_selection(
                cases,
                target_coverage=point.target_coverage,
            )
            if selection is None:
                unavailable_curve_point = True
                if (
                    point.risk.value is not None
                    or point.risk.contributing_case_count != 0
                    or "target_coverage_exceeds_confidence_available_coverage"
                    not in point.risk.blockers
                ):
                    raise PoseRankingConfidenceError(
                        "selective-risk point disagrees with confidence coverage"
                    )
                continue
            selected_ids = tuple(sorted(case.case_id for case in selection.selected))
            errors = sum(not case.top1_native_like for case in selection.selected)
            if (
                point.risk.value != selection.risk
                or point.risk.contributing_case_count != len(selection.selected)
                or point.achieved_coverage != selection.achieved_coverage
                or point.confidence_cutoff != selection.confidence_cutoff
                or point.selected_case_ids != selected_ids
                or point.top1_error_count != errors
            ):
                raise PoseRankingConfidenceError(
                    "selective-risk point disagrees with retained cases"
                )
        if unavailable_curve_point:
            expected_scope_blockers.append(
                "selective_risk_target_coverage_unavailable"
            )
        if scope.blockers != tuple(expected_scope_blockers):
            raise PoseRankingConfidenceError(
                "confidence scope blockers disagree with retained cases"
            )
        for case in cases:
            expected_accepted = (
                case.confidence is not None
                and case.confidence >= config.confidence_threshold
            )
            if (case.decision == "accepted") != expected_accepted:
                raise PoseRankingConfidenceError(
                    "confidence case decision disagrees with the configured threshold"
                )

    @property
    def claim_safe(self) -> bool:
        return False

    @property
    def probability_calibrated(self) -> bool:
        return False

    @property
    def blockers(self) -> tuple[str, ...]:
        return _REPORT_BLOCKERS

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "pose_ranking_evaluation_sha256": (
                self.pose_ranking_evaluation_sha256
            ),
            "model_sha256": self.model_sha256,
            "evaluation_partition_sha256": self.evaluation_partition_sha256,
            "config": self.config.to_dict(),
            "confidence_signal": {
                "signal_id": POSE_RANKING_MARGIN_CONFIDENCE_SIGNAL_ID,
                "semantics": (
                    "logistic_transform_of_runner_up_minus_top1_minimize_score_margin"
                ),
                "probability_calibrated": False,
                "disjoint_calibration_fit_present": False,
            },
            "cases": [case.to_dict() for case in self.cases],
            "overall": self.overall.to_dict(),
            "families": [scope.to_dict() for scope in self.families],
            "probability_calibrated": False,
            "public_benchmark_result_established": False,
            "claim_safe": False,
            "blockers": list(self.blockers),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _case_evaluation(
    source: PoseRankingCaseEvaluation,
    *,
    config: PoseRankingConfidenceEvaluationConfig,
) -> PoseRankingConfidenceCaseEvaluation:
    margin: float | None = None
    confidence: float | None = None
    if source.successful_pose_count < 2:
        decision = "abstained"
        reason = "insufficient_successful_poses_for_margin"
    else:
        candidate = source.ranked_scores[1] - source.ranked_scores[0]
        if not math.isfinite(candidate):
            decision = "abstained"
            reason = "nonfinite_top1_runner_up_margin"
        else:
            margin = float(candidate)
            confidence = _margin_confidence(margin)
            if confidence >= config.confidence_threshold:
                decision = "accepted"
                reason = ""
            else:
                decision = "abstained"
                reason = "below_confidence_threshold"
    return PoseRankingConfidenceCaseEvaluation(
        case_id=source.case_id,
        target_id=source.target_id,
        target_family=source.target_family,
        total_pose_count=source.total_pose_count,
        successful_pose_count=source.successful_pose_count,
        failed_pose_count=source.failed_pose_count,
        top1_native_like=source.top1_native_like,
        score_margin=margin,
        confidence=confidence,
        decision=decision,
        abstention_reason=reason,
    )


def evaluate_pose_ranking_confidence(
    ranking_report: PoseRankingEvaluationReport,
    *,
    config: PoseRankingConfidenceEvaluationConfig | None = None,
) -> PoseRankingConfidenceEvaluationReport:
    """Evaluate an uncalibrated score-margin signal without opening a claim."""

    if not isinstance(ranking_report, PoseRankingEvaluationReport):
        raise PoseRankingConfidenceError(
            "ranking_report must be PoseRankingEvaluationReport"
        )
    if ranking_report.schema_id != POSE_RANKING_EVALUATION_SCHEMA_ID:
        raise PoseRankingConfidenceError(
            "confidence evaluation requires pose-ranking evaluation schema v2"
        )
    active = config or PoseRankingConfidenceEvaluationConfig()
    cases = tuple(
        _case_evaluation(case, config=active) for case in ranking_report.cases
    )
    family_cases: dict[str, list[PoseRankingConfidenceCaseEvaluation]] = {}
    for case in cases:
        family_cases.setdefault(case.target_family, []).append(case)
    family_names = tuple(sorted(family_cases))
    work_items = (
        active.bootstrap_samples
        * (len(cases) + sum(len(rows) for rows in family_cases.values()))
        * (5 + len(active.selective_coverage_targets))
    )
    if work_items > MAX_CONFIDENCE_BOOTSTRAP_WORK_ITEMS:
        raise PoseRankingConfidenceError(
            "confidence bootstrap work exceeds MAX_CONFIDENCE_BOOTSTRAP_WORK_ITEMS"
        )
    overall = _scope_evaluation(
        "overall",
        cases,
        target_family=None,
        config=active,
    )
    families = tuple(
        _scope_evaluation(
            f"family:{family}",
            tuple(family_cases[family]),
            target_family=family,
            config=active,
        )
        for family in family_names
    )
    return PoseRankingConfidenceEvaluationReport(
        pose_ranking_evaluation_sha256=ranking_report.fingerprint_sha256,
        model_sha256=ranking_report.model_sha256,
        evaluation_partition_sha256=ranking_report.evaluation_partition_sha256,
        config=active,
        cases=cases,
        overall=overall,
        families=families,
    )


__all__ = [
    "MAX_CONFIDENCE_BINS",
    "MAX_CONFIDENCE_BOOTSTRAP_WORK_ITEMS",
    "MAX_SELECTIVE_COVERAGE_TARGETS",
    "POSE_RANKING_CONFIDENCE_EVALUATION_SCHEMA_ID",
    "POSE_RANKING_MARGIN_CONFIDENCE_SIGNAL_ID",
    "PoseRankingConfidenceCaseEvaluation",
    "PoseRankingConfidenceError",
    "PoseRankingConfidenceEvaluationConfig",
    "PoseRankingConfidenceEvaluationReport",
    "PoseRankingConfidenceMetricEstimate",
    "PoseRankingConfidenceScopeEvaluation",
    "PoseRankingReliabilityBin",
    "PoseRankingSelectiveRiskPoint",
    "evaluate_pose_ranking_confidence",
]
