from __future__ import annotations

import pytest

from betelgeuze_product.docking_comparison_contract import (
    DockingComparisonError,
    build_enrichment_comparison,
    build_pose_success_comparison,
)

_FAIR = {
    "dataset_id": "CASF-2016-core",
    "dataset_manifest_sha256": "abc",
    "prep_policy_sha256": "prep1",
    "metric_def_version": "docking_gold_v1",
    "pose_success_rmsd_threshold_a": 2.0,
}


def _pose(tool_id, kind, top1, top5, **over):
    row = {
        "tool_id": tool_id,
        "tool_kind": kind,
        "complex_count": 285,
        "evaluated_complex_count": 285,
        "top1_pose_success_rate": top1,
        "top5_pose_success_rate": top5,
        **_FAIR,
    }
    row.update(over)
    return row


def test_fair_pose_comparison_declares_deltas() -> None:
    rows = [
        _pose("betelgeuze", "subject", 0.74, 0.88),
        _pose("autodock_vina", "baseline", 0.70, 0.85),
        _pose("gnina", "baseline", 0.78, 0.90),
    ]
    out = build_pose_success_comparison(rows)
    s = out["summary"]
    assert s["comparison_valid"] is True
    assert s["status"] == "fair_comparison_ready"
    assert s["unfairness_reasons"] == []
    assert s["tool_count"] == 3
    deltas = {d["baseline_tool_id"]: d for d in s["subject_vs_baseline_deltas"]}
    assert deltas["autodock_vina"]["top1_success_delta"] == pytest.approx(0.04)
    assert deltas["gnina"]["top1_success_delta"] == pytest.approx(-0.04)


def test_mismatched_prep_policy_blocks_comparison() -> None:
    rows = [
        _pose("betelgeuze", "subject", 0.74, 0.88),
        _pose("autodock_vina", "baseline", 0.70, 0.85, prep_policy_sha256="DIFFERENT"),
    ]
    out = build_pose_success_comparison(rows)
    s = out["summary"]
    assert s["comparison_valid"] is False
    assert s["status"] == "blocked_unfair_comparison"
    assert "mismatched_prep_policy_sha256" in s["unfairness_reasons"]
    assert s["subject_vs_baseline_deltas"] == []


def test_mismatched_dataset_manifest_blocks() -> None:
    rows = [
        _pose("betelgeuze", "subject", 0.74, 0.88),
        _pose("gnina", "baseline", 0.78, 0.90, dataset_manifest_sha256="other"),
    ]
    out = build_pose_success_comparison(rows)
    assert out["summary"]["comparison_valid"] is False
    assert "mismatched_dataset_manifest_sha256" in out["summary"]["unfairness_reasons"]


def test_mismatched_threshold_blocks() -> None:
    rows = [
        _pose("betelgeuze", "subject", 0.74, 0.88),
        _pose("gnina", "baseline", 0.78, 0.90, pose_success_rmsd_threshold_a=5.0),
    ]
    out = build_pose_success_comparison(rows)
    assert out["summary"]["comparison_valid"] is False
    assert "mismatched_pose_success_rmsd_threshold_a" in out["summary"]["unfairness_reasons"]


def test_requires_subject_and_baseline() -> None:
    rows = [
        _pose("betelgeuze", "subject", 0.74, 0.88),
        _pose("betelgeuze2", "subject", 0.70, 0.85),
    ]
    out = build_pose_success_comparison(rows)
    assert out["summary"]["comparison_valid"] is False
    assert "no_baseline_tool" in out["summary"]["unfairness_reasons"]


def test_single_tool_blocks() -> None:
    out = build_pose_success_comparison([_pose("betelgeuze", "subject", 0.74, 0.88)])
    assert out["summary"]["comparison_valid"] is False
    assert "need_at_least_two_tools" in out["summary"]["unfairness_reasons"]


def test_duplicate_tool_id_blocks() -> None:
    rows = [
        _pose("vina", "subject", 0.74, 0.88),
        _pose("vina", "baseline", 0.70, 0.85),
    ]
    out = build_pose_success_comparison(rows)
    assert "duplicate_tool_id" in out["summary"]["unfairness_reasons"]


def test_missing_required_field_raises() -> None:
    bad = _pose("betelgeuze", "subject", 0.74, 0.88)
    del bad["complex_count"]
    with pytest.raises(DockingComparisonError):
        build_pose_success_comparison([bad, _pose("vina", "baseline", 0.7, 0.8)])


def test_unknown_tool_kind_raises() -> None:
    bad = _pose("betelgeuze", "champion", 0.74, 0.88)
    with pytest.raises(DockingComparisonError):
        build_pose_success_comparison([bad, _pose("vina", "baseline", 0.7, 0.8)])


def test_failure_accounting_preserved() -> None:
    rows = [
        _pose("betelgeuze", "subject", 0.74, 0.88, missing_complex_count=3, failed_pose_complex_count=2),
        _pose("vina", "baseline", 0.70, 0.85, missing_complex_count=0, failed_pose_complex_count=1),
    ]
    out = build_pose_success_comparison(rows)
    by_id = {r["tool_id"]: r for r in out["rows"]}
    assert by_id["betelgeuze"]["missing_complex_count"] == 3
    assert by_id["betelgeuze"]["failed_pose_complex_count"] == 2
    assert by_id["vina"]["failed_pose_complex_count"] == 1


# --- enrichment ---


def _enr(tool_id, kind, ef1, ef01, bedroc, **over):
    row = {
        "tool_id": tool_id,
        "tool_kind": kind,
        "ef1": ef1,
        "ef_point1": ef01,
        "bedroc": bedroc,
        "active_count": 30,
        "decoy_count": 1500,
        **_FAIR,
    }
    row.update(over)
    return row


def test_fair_enrichment_comparison() -> None:
    rows = [
        _enr("betelgeuze", "subject", 12.0, 30.0, 0.6),
        _enr("autodock_vina", "baseline", 9.0, 22.0, 0.5),
    ]
    out = build_enrichment_comparison(rows)
    s = out["summary"]
    assert s["comparison_valid"] is True
    assert s["comparison_kind"] == "enrichment"
    d = s["subject_vs_baseline_deltas"][0]
    assert d["ef1_delta"] == pytest.approx(3.0)
    assert d["bedroc_delta"] == pytest.approx(0.1)


def test_enrichment_mismatched_metric_def_blocks() -> None:
    rows = [
        _enr("betelgeuze", "subject", 12.0, 30.0, 0.6),
        _enr("gnina", "baseline", 13.0, 31.0, 0.62, metric_def_version="other_v2"),
    ]
    out = build_enrichment_comparison(rows)
    assert out["summary"]["comparison_valid"] is False
    assert "mismatched_metric_def_version" in out["summary"]["unfairness_reasons"]
