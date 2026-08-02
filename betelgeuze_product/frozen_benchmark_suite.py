"""Frozen public docking benchmark suite contract (P1-8).

A docking accuracy claim needs a benchmark that was fixed *before* the results
were seen, with a stated denominator and stated stratification. Without that,
a suite can be silently reshaped after the fact: drop the hard cases, report
success over the cases that happened to succeed, and the number looks fine.

This module encodes the suite contract the roadmap requires:

- a frozen case set of 100-300 cases, identified by a content hash;
- stratification across every required axis, so a suite cannot be all-easy;
- the full required metric set, including the failure denominator, candidate
  budget, bootstrap CI, and the paired Vina/GNINA baseline delta;
- subgroup metrics by rotor count and ligand size, which is where flexibility
  and size bias hide.

Anything missing fails closed. A suite that omits the failure denominator or a
required stratification axis is reported as blocked, not as a smaller valid
suite, because a partial benchmark reads as a full one downstream.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

FROZEN_BENCHMARK_SUITE_SCHEMA_VERSION = "frozen_public_docking_benchmark_suite_v1"

#: The roadmap requires at least 100 frozen cases; above 300 the suite is no
#: longer the bounded MVP suite this contract describes.
MIN_FROZEN_CASE_COUNT = 100
MAX_FROZEN_CASE_COUNT = 300

#: Stratification axes. Every axis must be populated with more than one bucket,
#: otherwise the suite cannot show that a result generalizes along that axis.
REQUIRED_STRATIFICATION_AXES = (
    "ligand_size",
    "rotor_count",
    "ring_count",
    "target_family",
    "pocket_polarity",
    "charge_class",
    "metal_or_cofactor_present",
    "apo_or_holo",
    "input_quality",
)

#: Metrics that must be present for the suite to be reportable.
REQUIRED_METRICS = (
    "top1_rmsd_success_rate_2a",
    "top3_success_rate",
    "top5_success_rate",
    "geometric_validity_rate",
    "chemical_validity_rate",
    "full_case_failure_rate",
    "runtime_seconds_median",
    "candidate_budget",
    "rotor_subgroup_success",
    "size_subgroup_success",
    "bootstrap_ci",
    "paired_baseline_delta",
)

#: Offline baselines that may serve as the paired oracle.
ALLOWED_BASELINE_ENGINES = ("vina", "gnina", "smina")

STATUS_READY = "frozen_benchmark_suite_ready"
STATUS_BLOCKED = "blocked_frozen_benchmark_suite"

CLAIM_BOUNDARY = (
    "Frozen public benchmark suite contract only. It validates case-set size, stratification coverage, metric "
    "completeness, failure denominator, and paired-baseline presence before any result may be reported. It does "
    "not download datasets, run docking, compute metrics, or promote a claim."
)


@dataclass(frozen=True)
class BenchmarkCase:
    """One frozen benchmark case with its stratification labels."""

    case_id: str
    target_id: str
    ligand_id: str
    provenance_id: str
    strata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def missing_axes(self) -> tuple[str, ...]:
        return tuple(
            axis
            for axis in REQUIRED_STRATIFICATION_AXES
            if not str(self.strata.get(axis) or "").strip()
        )


@dataclass(frozen=True)
class BootstrapInterval:
    """Bootstrap confidence interval for a reported rate."""

    metric_id: str
    point_estimate: float
    ci_low: float
    ci_high: float
    iterations: int
    seed: int

    @property
    def valid(self) -> bool:
        return (
            self.ci_low <= self.point_estimate <= self.ci_high
            and int(self.iterations) > 0
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["valid"] = self.valid
        return payload


@dataclass(frozen=True)
class PairedBaselineDelta:
    """Paired delta against an offline oracle on the same frozen cases."""

    baseline_engine: str
    metric_id: str
    subject_value: float
    baseline_value: float
    paired_case_count: int

    @property
    def delta(self) -> float:
        return float(self.subject_value - self.baseline_value)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["delta"] = self.delta
        return payload


@dataclass(frozen=True)
class FrozenBenchmarkSuite:
    """A frozen case set plus the metrics reported over it."""

    suite_id: str
    frozen_at_utc: str
    cases: tuple[BenchmarkCase, ...]
    metrics: dict[str, Any] = field(default_factory=dict)
    bootstrap_intervals: tuple[BootstrapInterval, ...] = ()
    paired_baseline_deltas: tuple[PairedBaselineDelta, ...] = ()

    @property
    def case_count(self) -> int:
        return len(self.cases)

    @property
    def case_set_hash(self) -> str:
        """Content hash of the frozen case set: proves it was not reshaped."""

        payload = [
            {
                "case_id": case.case_id,
                "target_id": case.target_id,
                "ligand_id": case.ligand_id,
                "provenance_id": case.provenance_id,
                "strata": dict(sorted(case.strata.items())),
            }
            for case in sorted(self.cases, key=lambda item: item.case_id)
        ]
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def stratification_coverage(self) -> dict[str, list[str]]:
        coverage: dict[str, set[str]] = {axis: set() for axis in REQUIRED_STRATIFICATION_AXES}
        for case in self.cases:
            for axis in REQUIRED_STRATIFICATION_AXES:
                value = str(case.strata.get(axis) or "").strip()
                if value:
                    coverage[axis].add(value)
        return {axis: sorted(values) for axis, values in coverage.items()}

    def blockers(self) -> list[str]:
        reasons: list[str] = []
        if not str(self.suite_id or "").strip():
            reasons.append("suite_id_missing")
        if not str(self.frozen_at_utc or "").strip():
            reasons.append("frozen_at_utc_missing")
        if self.case_count < MIN_FROZEN_CASE_COUNT:
            reasons.append(
                f"case_count_below_minimum:{self.case_count}<{MIN_FROZEN_CASE_COUNT}"
            )
        if self.case_count > MAX_FROZEN_CASE_COUNT:
            reasons.append(
                f"case_count_above_maximum:{self.case_count}>{MAX_FROZEN_CASE_COUNT}"
            )
        case_ids = [case.case_id for case in self.cases]
        if len(set(case_ids)) != len(case_ids):
            reasons.append("duplicate_case_id")

        incomplete = [case.case_id for case in self.cases if case.missing_axes]
        if incomplete:
            reasons.append(f"cases_missing_stratification_labels:{len(incomplete)}")

        coverage = self.stratification_coverage()
        for axis in REQUIRED_STRATIFICATION_AXES:
            if not coverage[axis]:
                reasons.append(f"stratification_axis_unpopulated:{axis}")
            elif len(coverage[axis]) < 2:
                # A single bucket means the suite cannot separate that axis at all.
                reasons.append(f"stratification_axis_single_bucket:{axis}")

        for metric_id in REQUIRED_METRICS:
            if metric_id not in self.metrics:
                reasons.append(f"required_metric_missing:{metric_id}")

        denominator = self.metrics.get("full_case_failure_rate")
        attempted = self.metrics.get("attempted_case_count")
        if attempted is not None and int(attempted) != self.case_count:
            reasons.append("attempted_case_count_does_not_match_frozen_case_count")
        if denominator is None:
            reasons.append("failure_denominator_missing")

        if not self.bootstrap_intervals:
            reasons.append("bootstrap_ci_missing")
        for interval in self.bootstrap_intervals:
            if not interval.valid:
                reasons.append(f"bootstrap_ci_invalid:{interval.metric_id}")

        if not self.paired_baseline_deltas:
            reasons.append("paired_baseline_delta_missing")
        for delta in self.paired_baseline_deltas:
            if delta.baseline_engine not in ALLOWED_BASELINE_ENGINES:
                reasons.append(f"unsupported_baseline_engine:{delta.baseline_engine}")
            if int(delta.paired_case_count) != self.case_count:
                # A "paired" delta computed over a subset is not paired.
                reasons.append(
                    f"baseline_delta_not_paired_over_full_suite:{delta.baseline_engine}"
                )

        for subgroup_metric in ("rotor_subgroup_success", "size_subgroup_success"):
            value = self.metrics.get(subgroup_metric)
            if isinstance(value, Mapping) and len(value) < 2:
                reasons.append(f"subgroup_metric_needs_multiple_buckets:{subgroup_metric}")

        return list(dict.fromkeys(reasons))

    @property
    def ready(self) -> bool:
        return not self.blockers()

    @property
    def status(self) -> str:
        return STATUS_READY if self.ready else STATUS_BLOCKED

    def to_dict(self) -> dict[str, Any]:
        blockers = self.blockers()
        return {
            "schema_version": FROZEN_BENCHMARK_SUITE_SCHEMA_VERSION,
            "status": STATUS_READY if not blockers else STATUS_BLOCKED,
            "ready": not blockers,
            "suite_id": str(self.suite_id),
            "frozen_at_utc": str(self.frozen_at_utc),
            "case_count": self.case_count,
            "case_count_bounds": [MIN_FROZEN_CASE_COUNT, MAX_FROZEN_CASE_COUNT],
            "case_set_hash": self.case_set_hash,
            "stratification_axes": list(REQUIRED_STRATIFICATION_AXES),
            "stratification_coverage": self.stratification_coverage(),
            "required_metrics": list(REQUIRED_METRICS),
            "metrics": dict(self.metrics),
            "bootstrap_intervals": [interval.to_dict() for interval in self.bootstrap_intervals],
            "paired_baseline_deltas": [delta.to_dict() for delta in self.paired_baseline_deltas],
            "allowed_baseline_engines": list(ALLOWED_BASELINE_ENGINES),
            "blockers": blockers,
            "claim_boundary": CLAIM_BOUNDARY,
        }


def build_frozen_benchmark_suite(
    *,
    suite_id: str,
    frozen_at_utc: str,
    cases: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any] | None = None,
    bootstrap_intervals: Sequence[Mapping[str, Any]] | None = None,
    paired_baseline_deltas: Sequence[Mapping[str, Any]] | None = None,
) -> FrozenBenchmarkSuite:
    """Build a suite from plain mappings, without validating away problems."""

    case_rows = tuple(
        BenchmarkCase(
            case_id=str(row.get("case_id") or ""),
            target_id=str(row.get("target_id") or ""),
            ligand_id=str(row.get("ligand_id") or ""),
            provenance_id=str(row.get("provenance_id") or ""),
            strata={
                str(key): str(value)
                for key, value in (row.get("strata") or {}).items()
            },
        )
        for row in cases
    )
    intervals = tuple(
        BootstrapInterval(
            metric_id=str(row.get("metric_id") or ""),
            point_estimate=float(row.get("point_estimate") or 0.0),
            ci_low=float(row.get("ci_low") or 0.0),
            ci_high=float(row.get("ci_high") or 0.0),
            iterations=int(row.get("iterations") or 0),
            seed=int(row.get("seed") or 0),
        )
        for row in bootstrap_intervals or ()
    )
    deltas = tuple(
        PairedBaselineDelta(
            baseline_engine=str(row.get("baseline_engine") or ""),
            metric_id=str(row.get("metric_id") or ""),
            subject_value=float(row.get("subject_value") or 0.0),
            baseline_value=float(row.get("baseline_value") or 0.0),
            paired_case_count=int(row.get("paired_case_count") or 0),
        )
        for row in paired_baseline_deltas or ()
    )
    return FrozenBenchmarkSuite(
        suite_id=str(suite_id),
        frozen_at_utc=str(frozen_at_utc),
        cases=case_rows,
        metrics=dict(metrics or {}),
        bootstrap_intervals=intervals,
        paired_baseline_deltas=deltas,
    )


__all__ = [
    "ALLOWED_BASELINE_ENGINES",
    "CLAIM_BOUNDARY",
    "FROZEN_BENCHMARK_SUITE_SCHEMA_VERSION",
    "MAX_FROZEN_CASE_COUNT",
    "MIN_FROZEN_CASE_COUNT",
    "REQUIRED_METRICS",
    "REQUIRED_STRATIFICATION_AXES",
    "STATUS_BLOCKED",
    "STATUS_READY",
    "BenchmarkCase",
    "BootstrapInterval",
    "FrozenBenchmarkSuite",
    "PairedBaselineDelta",
    "build_frozen_benchmark_suite",
]
