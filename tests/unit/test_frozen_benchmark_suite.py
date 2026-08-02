"""Frozen public benchmark suite contract tests (P1-8)."""

from __future__ import annotations

from typing import Any

import pytest

from betelgeuze_product.frozen_benchmark_suite import (
    ALLOWED_BASELINE_ENGINES,
    FROZEN_BENCHMARK_SUITE_SCHEMA_VERSION,
    MAX_FROZEN_CASE_COUNT,
    MIN_FROZEN_CASE_COUNT,
    REQUIRED_METRICS,
    REQUIRED_STRATIFICATION_AXES,
    STATUS_BLOCKED,
    STATUS_READY,
    build_frozen_benchmark_suite,
)


def _cases(count: int, *, buckets: int = 2) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(count):
        rows.append(
            {
                "case_id": f"case_{index:03d}",
                "target_id": f"target_{index % 7}",
                "ligand_id": f"ligand_{index}",
                "provenance_id": "pdbbind_public",
                "strata": {
                    axis: f"{axis}_bucket_{index % max(buckets, 1)}"
                    for axis in REQUIRED_STRATIFICATION_AXES
                },
            }
        )
    return rows


def _metrics(case_count: int) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        metric_id: 0.5
        for metric_id in REQUIRED_METRICS
        if metric_id not in {"rotor_subgroup_success", "size_subgroup_success"}
    }
    metrics["rotor_subgroup_success"] = {"rotors_0_3": 0.62, "rotors_4_plus": 0.31}
    metrics["size_subgroup_success"] = {"small": 0.60, "large": 0.28}
    metrics["attempted_case_count"] = case_count
    return metrics


def _suite(case_count: int = 120, **overrides):
    kwargs: dict[str, Any] = {
        "suite_id": "public_docking_frozen_v1",
        "frozen_at_utc": "2026-07-01T00:00:00Z",
        "cases": _cases(case_count),
        "metrics": _metrics(case_count),
        "bootstrap_intervals": [
            {
                "metric_id": "top1_rmsd_success_rate_2a",
                "point_estimate": 0.50,
                "ci_low": 0.41,
                "ci_high": 0.59,
                "iterations": 2000,
                "seed": 7,
            }
        ],
        "paired_baseline_deltas": [
            {
                "baseline_engine": "vina",
                "metric_id": "top1_rmsd_success_rate_2a",
                "subject_value": 0.50,
                "baseline_value": 0.55,
                "paired_case_count": case_count,
            }
        ],
    }
    kwargs.update(overrides)
    return build_frozen_benchmark_suite(**kwargs)


def test_complete_suite_is_ready() -> None:
    payload = _suite().to_dict()

    assert payload["schema_version"] == FROZEN_BENCHMARK_SUITE_SCHEMA_VERSION
    assert payload["status"] == STATUS_READY
    assert payload["ready"] is True
    assert payload["blockers"] == []
    assert payload["case_count"] == 120


def test_case_count_bounds_follow_the_roadmap() -> None:
    assert MIN_FROZEN_CASE_COUNT == 100
    assert MAX_FROZEN_CASE_COUNT == 300
    assert _suite(100).ready is True
    assert _suite(300).ready is True


def test_too_few_cases_is_blocked() -> None:
    suite = _suite(99)

    assert suite.status == STATUS_BLOCKED
    assert any(b.startswith("case_count_below_minimum") for b in suite.blockers())


def test_too_many_cases_is_blocked() -> None:
    suite = _suite(301)

    assert any(b.startswith("case_count_above_maximum") for b in suite.blockers())


def test_case_set_hash_is_deterministic_and_order_independent() -> None:
    cases = _cases(120)
    forward = _suite(cases=cases, metrics=_metrics(120))
    reversed_order = _suite(cases=list(reversed(cases)), metrics=_metrics(120))

    assert forward.case_set_hash == reversed_order.case_set_hash


def test_case_set_hash_changes_when_a_case_changes() -> None:
    baseline = _suite()
    mutated_cases = _cases(120)
    mutated_cases[0]["ligand_id"] = "swapped_ligand"
    mutated = _suite(cases=mutated_cases)

    assert baseline.case_set_hash != mutated.case_set_hash


def test_every_required_stratification_axis_is_covered() -> None:
    coverage = _suite().stratification_coverage()

    assert set(coverage) == set(REQUIRED_STRATIFICATION_AXES)
    for axis in REQUIRED_STRATIFICATION_AXES:
        assert len(coverage[axis]) >= 2


def test_single_bucket_stratification_is_blocked() -> None:
    suite = _suite(cases=_cases(120, buckets=1), metrics=_metrics(120))

    blockers = suite.blockers()
    assert any(b.startswith("stratification_axis_single_bucket") for b in blockers)


def test_missing_stratification_label_is_blocked() -> None:
    cases = _cases(120)
    cases[3]["strata"].pop("pocket_polarity")
    suite = _suite(cases=cases)

    assert any(
        b.startswith("cases_missing_stratification_labels") for b in suite.blockers()
    )


@pytest.mark.parametrize("metric_id", list(REQUIRED_METRICS))
def test_each_required_metric_is_enforced(metric_id: str) -> None:
    metrics = _metrics(120)
    metrics.pop(metric_id)
    suite = _suite(metrics=metrics)

    assert f"required_metric_missing:{metric_id}" in suite.blockers()


def test_failure_denominator_must_match_the_frozen_case_count() -> None:
    metrics = _metrics(120)
    metrics["attempted_case_count"] = 90
    suite = _suite(metrics=metrics)

    assert "attempted_case_count_does_not_match_frozen_case_count" in suite.blockers()


def test_bootstrap_ci_is_required() -> None:
    suite = _suite(bootstrap_intervals=[])

    assert "bootstrap_ci_missing" in suite.blockers()


def test_inverted_bootstrap_interval_is_rejected() -> None:
    suite = _suite(
        bootstrap_intervals=[
            {
                "metric_id": "top1_rmsd_success_rate_2a",
                "point_estimate": 0.50,
                "ci_low": 0.60,
                "ci_high": 0.55,
                "iterations": 2000,
                "seed": 7,
            }
        ]
    )

    assert "bootstrap_ci_invalid:top1_rmsd_success_rate_2a" in suite.blockers()


def test_paired_baseline_delta_is_required() -> None:
    suite = _suite(paired_baseline_deltas=[])

    assert "paired_baseline_delta_missing" in suite.blockers()


def test_baseline_delta_must_be_paired_over_the_full_suite() -> None:
    suite = _suite(
        paired_baseline_deltas=[
            {
                "baseline_engine": "gnina",
                "metric_id": "top1_rmsd_success_rate_2a",
                "subject_value": 0.5,
                "baseline_value": 0.4,
                "paired_case_count": 40,
            }
        ]
    )

    assert "baseline_delta_not_paired_over_full_suite:gnina" in suite.blockers()


def test_unsupported_baseline_engine_is_rejected() -> None:
    suite = _suite(
        paired_baseline_deltas=[
            {
                "baseline_engine": "our_own_engine",
                "metric_id": "top1_rmsd_success_rate_2a",
                "subject_value": 0.5,
                "baseline_value": 0.4,
                "paired_case_count": 120,
            }
        ]
    )

    assert "unsupported_baseline_engine:our_own_engine" in suite.blockers()
    assert set(ALLOWED_BASELINE_ENGINES) == {"vina", "gnina", "smina"}


def test_paired_delta_is_reported_signed() -> None:
    payload = _suite().to_dict()
    delta = payload["paired_baseline_deltas"][0]

    # Subject is worse than the baseline here; the delta must show it.
    assert delta["delta"] == pytest.approx(-0.05)


def test_subgroup_metrics_need_multiple_buckets() -> None:
    metrics = _metrics(120)
    metrics["rotor_subgroup_success"] = {"all": 0.5}
    suite = _suite(metrics=metrics)

    assert "subgroup_metric_needs_multiple_buckets:rotor_subgroup_success" in suite.blockers()


def test_duplicate_case_id_is_blocked() -> None:
    cases = _cases(120)
    cases[5]["case_id"] = cases[4]["case_id"]
    suite = _suite(cases=cases)

    assert "duplicate_case_id" in suite.blockers()


def test_missing_suite_identity_is_blocked() -> None:
    assert "suite_id_missing" in _suite(suite_id="  ").blockers()
    assert "frozen_at_utc_missing" in _suite(frozen_at_utc="").blockers()


def test_payload_states_no_claim_promotion() -> None:
    payload = _suite().to_dict()

    assert "does not download datasets" in payload["claim_boundary"]
    assert "promote a claim" in payload["claim_boundary"]
