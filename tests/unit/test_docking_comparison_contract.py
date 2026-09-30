from __future__ import annotations

import pytest

from betelgeuze_product.docking_comparison_contract import (
    CONTROLLED_CORE,
    FULL_WORKFLOW,
    SCOPED_POSE_SCHEMA_VERSION,
    DockingComparisonError,
    build_enrichment_comparison,
    build_pose_success_comparison,
    build_scoped_pose_success_comparison,
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


def _scoped(tool_id: str, kind: str, scope: str, **over):
    row = {
        "schema_version": SCOPED_POSE_SCHEMA_VERSION,
        "comparison_scope": scope,
        "tool_id": tool_id,
        "tool_kind": kind,
        "tool_version": "test-version",
        "dataset_id": "fixture",
        "dataset_manifest_sha256": "dataset-hash",
        "candidate_manifest_sha256": "candidate-hash",
        "metric_def_version": "pose-v1",
        "pose_success_rmsd_threshold_a": 2.0,
        "complex_count": 10,
        "completed_complex_count": 7,
        "failed_complex_count": 2,
        "unprocessed_complex_count": 1,
        "top1_success_count": 4,
        "top5_success_count": 6,
        "result_artifact_sha256": "result-hash",
    }
    if scope == CONTROLLED_CORE:
        row.update(
            chemical_state_sha256="chemical-hash",
            receptor_state_sha256="receptor-hash",
            pocket_definition_sha256="pocket-hash",
            shared_preparation_sha256="shared-prep-hash",
            canonical_prepared_input_sha256="core-input-hash",
            input_conversion={"method": "sdf-to-pdbqt", "version": "1", "source_sha256": "core-input-hash", "output_sha256": "converted-hash"},
        )
    else:
        row.update(
            preparation_policy_sha256=f"{tool_id}-recommended-prep",
            preparation_recommendation_ref=f"{tool_id}-manual-version",
            preparation_wall_seconds=2.0,
            compute_wall_seconds=3.0,
            validation_wall_seconds=1.0,
            recovery_wall_seconds=1.0,
            preparation_failed_complex_count=1,
            peak_rss_kib=1024,
            expert_intervention_count=0,
            expert_intervention_wall_seconds=0.0,
            expert_intervention_log_sha256="empty-intervention-log-hash",
            elapsed_wall_seconds=8.0,
        )
    row.update(over)
    return row


def test_scoped_core_uses_full_universe_and_records_conversions() -> None:
    rows = [
        _scoped("subject", "subject", CONTROLLED_CORE),
        _scoped("baseline", "baseline", CONTROLLED_CORE, top1_success_count=5),
    ]
    out = build_scoped_pose_success_comparison(rows, scope=CONTROLLED_CORE)
    assert out["summary"]["comparison_valid"] is True
    assert out["summary"]["status"] == "declared_comparison_consistent_unverified"
    assert out["summary"]["source_artifacts_verified"] is False
    assert out["summary"]["metrics_independently_recomputed"] is False
    assert out["rows"][0]["top1_pose_success_rate"] == 0.4
    assert out["rows"][0]["input_conversion"]["output_sha256"] == "converted-hash"
    assert out["summary"]["subject_vs_baseline_deltas"][0]["top1_success_delta"] == -0.1


def test_scoped_core_rejects_cross_scope_and_missing_conversion() -> None:
    core = _scoped("subject", "subject", CONTROLLED_CORE)
    full = _scoped("baseline", "baseline", FULL_WORKFLOW)
    with pytest.raises(DockingComparisonError, match="mixed_or_missing_comparison_scope"):
        build_scoped_pose_success_comparison([core, full], scope=CONTROLLED_CORE)
    core.pop("input_conversion")
    with pytest.raises(DockingComparisonError, match="missing input_conversion"):
        build_scoped_pose_success_comparison([core], scope=CONTROLLED_CORE)


def test_scoped_core_rejects_conversion_from_another_input() -> None:
    core = _scoped("subject", "subject", CONTROLLED_CORE)
    core["input_conversion"]["source_sha256"] = "different-prepared-input"
    with pytest.raises(DockingComparisonError, match="conversion_source_mismatch"):
        build_scoped_pose_success_comparison([core], scope=CONTROLLED_CORE)


def test_scoped_full_workflow_accepts_tool_preparation_and_accounts_cost() -> None:
    rows = [
        _scoped("subject", "subject", FULL_WORKFLOW, expert_intervention_count=1,
                expert_intervention_wall_seconds=0.5),
        _scoped("baseline", "baseline", FULL_WORKFLOW),
    ]
    out = build_scoped_pose_success_comparison(rows, scope=FULL_WORKFLOW)
    assert out["summary"]["comparison_valid"] is True
    assert out["rows"][0]["preparation_policy_sha256"] != out["rows"][1]["preparation_policy_sha256"]
    assert out["rows"][0]["cost_wall_seconds"]["recovery"] == 1.0
    assert out["rows"][0]["failed_complex_count"] == 2
    assert out["rows"][0]["preparation_failed_complex_count"] == 1
    assert out["rows"][0]["peak_rss_kib"] == 1024
    assert out["rows"][0]["expert_intervention_wall_seconds"] == 0.5
    assert out["rows"][0]["other_wall_seconds"] == 0.5


def test_scoped_denominators_and_cost_fail_closed() -> None:
    bad = _scoped("subject", "subject", FULL_WORKFLOW, failed_complex_count=1)
    with pytest.raises(DockingComparisonError, match="complex_denominator_mismatch"):
        build_scoped_pose_success_comparison([bad], scope=FULL_WORKFLOW)
    bad = _scoped("subject", "subject", FULL_WORKFLOW, recovery_wall_seconds=4.0)
    with pytest.raises(DockingComparisonError, match="phase_cost_exceeds_elapsed_wall_seconds"):
        build_scoped_pose_success_comparison([bad], scope=FULL_WORKFLOW)
    bad = _scoped("subject", "subject", FULL_WORKFLOW, preparation_failed_complex_count=3)
    with pytest.raises(DockingComparisonError, match="preparation_failures_exceed_failed_complexes"):
        build_scoped_pose_success_comparison([bad], scope=FULL_WORKFLOW)
    bad = _scoped("subject", "subject", FULL_WORKFLOW, peak_rss_kib=0)
    with pytest.raises(DockingComparisonError, match="peak_rss_kib_must_be_measured"):
        build_scoped_pose_success_comparison([bad], scope=FULL_WORKFLOW)
    bad = _scoped("subject", "subject", FULL_WORKFLOW, expert_intervention_count=1)
    with pytest.raises(DockingComparisonError, match="expert_intervention_count_time_mismatch"):
        build_scoped_pose_success_comparison([bad], scope=FULL_WORKFLOW)


def test_scoped_shared_state_mismatch_blocks_deltas() -> None:
    rows = [
        _scoped("subject", "subject", CONTROLLED_CORE),
        _scoped("baseline", "baseline", CONTROLLED_CORE, receptor_state_sha256="different"),
    ]
    out = build_scoped_pose_success_comparison(rows, scope=CONTROLLED_CORE)
    assert out["summary"]["comparison_valid"] is False
    assert "mismatched_receptor_state_sha256" in out["summary"]["unfairness_reasons"]
    assert out["summary"]["subject_vs_baseline_deltas"] == []
