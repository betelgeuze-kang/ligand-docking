from __future__ import annotations

from typing import Any

BENCHMARK_CONTRACT_SCHEMA_VERSION = "product_scientific_benchmark_contract_v1"

CLAIM_BOUNDARY = (
    "Scientific benchmark contract only. It defines required benchmark lanes, metrics, split policy, "
    "row-level evidence, and artifact-hash requirements. It does not download datasets, run docking, "
    "compute scores, mutate external state, or promote a scientific claim."
)

REQUIRED_BENCHMARK_LANES: tuple[dict[str, Any], ...] = (
    {
        "lane_id": "pose_redocking_validity",
        "claim_scope": "restricted_docking_pose",
        "dataset_split_policy": "posebusters_or_casf_fixed_split_no_training_leakage",
        "required_metrics": [
            "top1_rmsd_lte_2a_rate",
            "top5_rmsd_lte_2a_rate",
            "posebusters_valid_rate",
            "chirality_preservation_rate",
            "protein_clash_free_rate",
        ],
        "minimum_thresholds": {
            "top1_rmsd_lte_2a_rate": 0.40,
            "top5_rmsd_lte_2a_rate": 0.60,
            "posebusters_valid_rate": 0.80,
            "chirality_preservation_rate": 0.99,
            "protein_clash_free_rate": 0.95,
        },
        "row_level_evidence_required": True,
        "artifact_hash_required": True,
        "promotion_allowed": False,
        "blockers": ["external_pose_benchmark_not_run"],
    },
    {
        "lane_id": "cross_docking_generalization",
        "claim_scope": "restricted_cross_docking",
        "dataset_split_policy": "target_heldout_and_scaffold_heldout",
        "required_metrics": [
            "top1_rmsd_lte_2a_rate",
            "top5_rmsd_lte_2a_rate",
            "target_holdout_count",
            "scaffold_holdout_count",
        ],
        "minimum_thresholds": {
            "top1_rmsd_lte_2a_rate": 0.30,
            "top5_rmsd_lte_2a_rate": 0.50,
            "target_holdout_count": 10,
            "scaffold_holdout_count": 50,
        },
        "row_level_evidence_required": True,
        "artifact_hash_required": True,
        "promotion_allowed": False,
        "blockers": ["cross_docking_holdout_not_run"],
    },
    {
        "lane_id": "virtual_screening_enrichment",
        "claim_scope": "restricted_ligand_ranking",
        "dataset_split_policy": "target_heldout_active_decoy_split",
        "required_metrics": [
            "roc_auc",
            "pr_auc",
            "ef1",
            "bedroc",
            "topk_hit_rate",
            "calibration_ece",
            "brier_score",
        ],
        "minimum_thresholds": {
            "roc_auc": 0.65,
            "pr_auc": 0.35,
            "ef1": 2.0,
            "bedroc": 0.20,
            "topk_hit_rate": 0.30,
            "calibration_ece": 0.20,
            "brier_score": 0.25,
        },
        "row_level_evidence_required": True,
        "artifact_hash_required": True,
        "promotion_allowed": False,
        "blockers": ["active_decoy_holdout_not_run"],
    },
    {
        "lane_id": "affinity_correlation_proxy",
        "claim_scope": "internal_affinity_proxy_only",
        "dataset_split_policy": "heldout_public_affinity_with_no_target_or_ligand_leakage",
        "required_metrics": [
            "spearman_r",
            "kendall_tau",
            "rmse_kcal_mol",
            "mae_kcal_mol",
            "uncertainty_coverage",
        ],
        "minimum_thresholds": {
            "spearman_r": 0.35,
            "kendall_tau": 0.25,
            "rmse_kcal_mol": 3.0,
            "mae_kcal_mol": 2.0,
            "uncertainty_coverage": 0.80,
        },
        "row_level_evidence_required": True,
        "artifact_hash_required": True,
        "promotion_allowed": False,
        "blockers": ["calibrated_affinity_evidence_not_run"],
    },
)


def benchmark_contract_packet() -> dict[str, Any]:
    lanes = [dict(row) for row in REQUIRED_BENCHMARK_LANES]
    required_metrics = sorted(
        {metric for row in lanes for metric in row.get("required_metrics", [])}
    )
    blockers = sorted({blocker for row in lanes for blocker in row.get("blockers", [])})
    return {
        "schema_version": BENCHMARK_CONTRACT_SCHEMA_VERSION,
        "status": "product_scientific_benchmark_contract_ready",
        "lane_count": len(lanes),
        "required_metric_count": len(required_metrics),
        "required_metrics": required_metrics,
        "lanes": lanes,
        "promotion_allowed": False,
        "claim_promotion_allowed": False,
        "row_level_evidence_required": True,
        "artifact_hash_required": True,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def validate_benchmark_scorecard_contract(scorecard: dict[str, Any]) -> dict[str, Any]:
    """Validate shape-only benchmark evidence without treating it as green science.

    This deliberately checks only row/schema completeness. Passing this function
    means the scorecard is reviewable; it does not mean the benchmark thresholds
    passed or that any product/science claim is promoted.
    """

    rows = scorecard.get("rows") if isinstance(scorecard.get("rows"), list) else []
    rows_by_lane = {
        str(row.get("lane_id") or ""): row for row in rows if isinstance(row, dict)
    }
    missing_lanes: list[str] = []
    missing_metrics: dict[str, list[str]] = {}
    missing_artifact_hash_lanes: list[str] = []
    missing_row_evidence_lanes: list[str] = []

    for lane in REQUIRED_BENCHMARK_LANES:
        lane_id = str(lane["lane_id"])
        row = rows_by_lane.get(lane_id)
        if row is None:
            missing_lanes.append(lane_id)
            continue
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        missing = [metric for metric in lane["required_metrics"] if metric not in metrics]
        if missing:
            missing_metrics[lane_id] = missing
        if lane.get("artifact_hash_required") is True and not str(row.get("artifact_sha256") or ""):
            missing_artifact_hash_lanes.append(lane_id)
        if lane.get("row_level_evidence_required") is True and not row.get("row_level_evidence_present") is True:
            missing_row_evidence_lanes.append(lane_id)

    ready = not (
        missing_lanes
        or missing_metrics
        or missing_artifact_hash_lanes
        or missing_row_evidence_lanes
    )
    blockers: list[str] = []
    if missing_lanes:
        blockers.append("missing_benchmark_lanes")
    if missing_metrics:
        blockers.append("missing_required_metrics")
    if missing_artifact_hash_lanes:
        blockers.append("missing_artifact_hashes")
    if missing_row_evidence_lanes:
        blockers.append("missing_row_level_evidence")
    return {
        "schema_version": BENCHMARK_CONTRACT_SCHEMA_VERSION,
        "status": "benchmark_scorecard_contract_review_ready" if ready else "blocked_benchmark_scorecard_contract",
        "review_ready": ready,
        "claim_promotion_allowed": False,
        "missing_lanes": missing_lanes,
        "missing_metrics": missing_metrics,
        "missing_artifact_hash_lanes": missing_artifact_hash_lanes,
        "missing_row_evidence_lanes": missing_row_evidence_lanes,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
    }
