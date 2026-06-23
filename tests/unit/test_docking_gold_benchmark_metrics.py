from __future__ import annotations

import pytest

from betelgeuze_engine.benchmark.docking_gold import DockingGoldRow, evaluate_docking_gold_slice


def test_docking_gold_metrics_compute_pose_ranking_enrichment_and_resource_fields() -> None:
    rows = [
        DockingGoldRow(
            "1abc",
            "1abc_pose1",
            1,
            pose_rmsd_a=1.0,
            score=-9.0,
            baseline_score=-3.0,
            affinity_label=9.0,
            active_label=True,
            runtime_ms=10,
            peak_memory_mb=100,
        ),
        DockingGoldRow(
            "1abc",
            "1abc_decoy1",
            2,
            pose_rmsd_a=4.0,
            score=-2.0,
            baseline_score=-5.0,
            affinity_label=1.0,
            active_label=False,
            runtime_ms=12,
            peak_memory_mb=110,
        ),
        DockingGoldRow(
            "2def",
            "2def_pose1",
            1,
            pose_rmsd_a=3.0,
            score=-8.0,
            baseline_score=-4.0,
            affinity_label=8.0,
            active_label=True,
            runtime_ms=20,
            peak_memory_mb=120,
        ),
        DockingGoldRow(
            "2def",
            "2def_pose2",
            2,
            pose_rmsd_a=1.5,
            score=-7.0,
            baseline_score=-2.0,
            affinity_label=7.0,
            active_label=True,
            runtime_ms=22,
            peak_memory_mb=130,
        ),
        DockingGoldRow(
            "2def",
            "2def_decoy1",
            3,
            pose_rmsd_a=6.0,
            score=-1.0,
            baseline_score=-1.0,
            affinity_label=2.0,
            active_label=False,
            abstained=True,
            chemistry_failures=("unassigned_ligand_chirality", "protonation_state_not_enumerated"),
            runtime_ms=24,
            peak_memory_mb=140,
        ),
    ]

    metrics = evaluate_docking_gold_slice(rows, pose_success_rmsd_a=2.0, top_k=5)
    payload = metrics.to_dict()

    assert payload["schema_version"] == "tier_beta_docking_gold_metrics_v1"
    assert payload["status"] == "pass"
    assert payload["complex_count"] == 2
    assert payload["row_count"] == 5
    assert payload["pose_success_rmsd_threshold_a"] == 2.0
    assert payload["reference_pose_present"] is True
    assert payload["native_pose_present"] is True
    assert payload["top1_mean_rmsd_a"] == 2.0
    assert payload["top5_best_mean_rmsd_a"] == 1.25
    assert payload["top1_pose_success_rate"] == 0.5
    assert payload["top5_pose_success_rate"] == 1.0
    assert payload["ranking_spearman"] > 0.8
    assert payload["pr_auc"] == pytest.approx(1.0)
    assert payload["topk_hit_rate"] == 1.0
    assert payload["decoy_rejection_rate"] == 1.0
    assert payload["baseline_ranking_spearman"] < payload["ranking_spearman"]
    assert payload["refine_ranking_spearman_delta"] > 0.0
    assert payload["refine_improvement_observed"] is True
    assert payload["heldout_complex_count"] == 2
    assert payload["chirality_failure_rate"] == 0.2
    assert payload["tautomer_failure_rate"] == 0.0
    assert payload["protonation_failure_rate"] == 0.2
    assert payload["abstention_precision"] == 1.0
    assert payload["mean_runtime_ms"] == pytest.approx(17.6)
    assert payload["peak_memory_mb"] == 140
    assert payload["blockers"] == []
    assert "calibrate affinity" in payload["claim_boundary"]


def test_docking_gold_metrics_fail_closed_without_ranking_labels() -> None:
    rows = [
        DockingGoldRow("1abc", "1abc_pose1", 1, pose_rmsd_a=1.0, score=-9.0),
        DockingGoldRow("1abc", "1abc_pose2", 2, pose_rmsd_a=4.0, score=-2.0),
    ]

    metrics = evaluate_docking_gold_slice(rows)
    payload = metrics.to_dict()

    assert payload["status"] == "blocked"
    assert payload["top1_pose_success_rate"] == 1.0
    assert payload["top5_pose_success_rate"] == 1.0
    assert payload["reference_pose_present"] is True
    assert payload["ranking_spearman"] is None
    assert payload["pr_auc"] is None
    assert "ranking_labels_missing" in payload["blockers"]
    assert "ranking_spearman_not_computable" in payload["blockers"]
    assert "pr_auc_not_computable" in payload["blockers"]
    assert "baseline_ranking_spearman_not_computable" in payload["blockers"]
    assert "runtime_metric_incomplete" in payload["blockers"]
    assert "peak_memory_metric_incomplete" in payload["blockers"]


def test_docking_gold_metrics_block_without_decoy_or_refine_improvement() -> None:
    rows = [
        DockingGoldRow(
            "1abc",
            "1abc_pose1",
            1,
            pose_rmsd_a=1.0,
            score=-3.0,
            baseline_score=-3.0,
            affinity_label=9.0,
            active_label=True,
            runtime_ms=10,
            peak_memory_mb=100,
        ),
        DockingGoldRow(
            "2def",
            "2def_pose1",
            1,
            pose_rmsd_a=1.5,
            score=-2.0,
            baseline_score=-2.0,
            affinity_label=8.0,
            active_label=True,
            runtime_ms=11,
            peak_memory_mb=101,
        ),
    ]

    payload = evaluate_docking_gold_slice(rows).to_dict()

    assert payload["status"] == "blocked"
    assert payload["decoy_rejection_rate"] is None
    assert payload["baseline_ranking_spearman"] == pytest.approx(payload["ranking_spearman"])
    assert payload["refine_ranking_spearman_delta"] == pytest.approx(0.0)
    assert "decoy_rejection_not_computable" in payload["blockers"]
    assert "heldout_refine_ranking_spearman_not_improved" in payload["blockers"]


def test_docking_gold_metrics_block_without_reference_pose_rmsd() -> None:
    rows = [
        DockingGoldRow("tier_beta", "pose1", 1, score=-4.0, abstained=True),
        DockingGoldRow("tier_beta", "pose2", 2, score=-3.0, abstained=True),
    ]

    payload = evaluate_docking_gold_slice(rows).to_dict()

    assert payload["status"] == "blocked"
    assert payload["reference_pose_present"] is False
    assert payload["native_pose_present"] is False
    assert payload["top1_mean_rmsd_a"] is None
    assert payload["top5_best_mean_rmsd_a"] is None
    assert "native_or_reference_pose_missing" in payload["blockers"]
    assert "pose_rmsd_not_computable" in payload["blockers"]


def test_docking_gold_metrics_block_partial_reference_pose_coverage() -> None:
    rows = [
        DockingGoldRow("1abc", "1abc_pose1", 1, pose_rmsd_a=1.0, score=-9.0, active_label=True),
        DockingGoldRow("1abc", "1abc_decoy1", 2, pose_rmsd_a=4.0, score=-2.0, active_label=False),
        DockingGoldRow("2def", "2def_pose1", 1, pose_rmsd_a=None, score=-8.0, active_label=True),
        DockingGoldRow("2def", "2def_decoy1", 2, pose_rmsd_a=None, score=-1.0, active_label=False),
    ]

    payload = evaluate_docking_gold_slice(rows).to_dict()

    assert payload["status"] == "blocked"
    assert payload["reference_pose_present"] is False
    assert payload["native_pose_present"] is False
    assert payload["top1_mean_rmsd_a"] == 1.0
    assert payload["top5_best_mean_rmsd_a"] == 1.0
    assert "native_or_reference_pose_missing" in payload["blockers"]
    assert "reference_pose_coverage_incomplete" in payload["blockers"]
