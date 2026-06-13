from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/goal", tags=["goal"])
ROOT = Path(__file__).resolve().parents[1]

GOAL_READINESS_ROLLUP_ARTIFACT = ROOT / "runs" / "goal_readiness_rollup_current.json"
GOAL_OPERATOR_ACTION_BOARD_ARTIFACT = ROOT / "runs" / "goal_operator_action_board_current.json"
GOAL_OPERATOR_INTAKE_KIT_MANIFEST = ROOT / "runs" / "goal_operator_intake_kit_current" / "manifest.json"
GOAL_RELEASE_DECISION_ARTIFACT = ROOT / "runs" / "goal_release_decision_gate_current.json"
GOAL_RELEASE_BURNDOWN_ARTIFACT = ROOT / "runs" / "goal_release_burndown_work_order_current.json"
GOAL_BOTTLENECK_BRIEFING_ARTIFACT = ROOT / "runs" / "goal_bottleneck_briefing_current.json"
GOAL_API_SURFACE_CONTRACT_ARTIFACT = ROOT / "runs" / "goal_api_surface_contract_current.json"
PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT = ROOT / "runs" / "product_goal_completion_audit_current.json"
PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT = (
    ROOT / "runs" / "product_commercial_readiness_handoff_bundle_current.json"
)
PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT = (
    ROOT / "runs" / "product_full_commercial_blocker_evidence_matrix_current.json"
)
PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_ARTIFACT = (
    ROOT / "runs" / "product_scope_breadth_evidence_receipt_current.json"
)
ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_ARTIFACT = (
    ROOT / "runs" / "engine_refinement_claim_evidence_receipt_current.json"
)
CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_ARTIFACT = (
    ROOT / "runs" / "cameo_official_result_fetch_preflight_current.json"
)

FULL_COMMERCIAL_RELEASE_BLOCKER_IDS = (
    "R8_full_scope_claim_closure",
    "R9_engine_refinement_claim_promotion",
    "MASTER:SCI-CLAIM",
    "ACCURACY:ligand_ranking",
)

FULL_COMMERCIAL_EVIDENCE_RECEIPT_STATUS_KEYS = (
    "product_scope_breadth_evidence_receipt_status",
    "product_scope_breadth_evidence_receipt_ready",
    "product_scope_breadth_evidence_receipt_artifact_path",
    "product_scope_breadth_evidence_receipt_csv",
    "product_scope_breadth_evidence_receipt_csv_present",
    "product_scope_breadth_evidence_receipt_approval_token_required",
    "product_scope_breadth_evidence_receipt_receipt_row_count",
    "product_scope_breadth_evidence_receipt_pass_row_count",
    "product_scope_breadth_evidence_receipt_blocked_row_count",
    "product_scope_breadth_evidence_receipt_blocker_count",
    "product_scope_breadth_evidence_receipt_evidence_artifact_present_count",
    "product_scope_breadth_evidence_receipt_evidence_status_verified_count",
    "product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id",
    "product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact",
    "product_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status",
    "product_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status",
    "product_scope_breadth_evidence_receipt_first_blocked_missing_true_fields",
    "product_scope_breadth_evidence_receipt_first_blocked_row_blockers",
    "product_scope_breadth_evidence_receipt_most_common_row_blocker",
    "product_scope_breadth_evidence_receipt_required_blocker_count",
    "product_scope_breadth_evidence_receipt_required_blockers",
    "product_scope_breadth_evidence_receipt_next_required_step",
    "product_scope_breadth_evidence_receipt_external_state_mutated",
    "engine_refinement_claim_evidence_receipt_status",
    "engine_refinement_claim_evidence_receipt_ready",
    "engine_refinement_claim_evidence_receipt_artifact_path",
    "engine_refinement_claim_evidence_receipt_csv",
    "engine_refinement_claim_evidence_receipt_csv_present",
    "engine_refinement_claim_evidence_receipt_approval_token_required",
    "engine_refinement_claim_evidence_receipt_receipt_row_count",
    "engine_refinement_claim_evidence_receipt_pass_row_count",
    "engine_refinement_claim_evidence_receipt_blocked_row_count",
    "engine_refinement_claim_evidence_receipt_blocker_count",
    "engine_refinement_claim_evidence_receipt_evidence_artifact_present_count",
    "engine_refinement_claim_evidence_receipt_evidence_status_verified_count",
    "engine_refinement_claim_evidence_receipt_first_blocked_blocker_id",
    "engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact",
    "engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status",
    "engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status",
    "engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields",
    "engine_refinement_claim_evidence_receipt_first_blocked_row_blockers",
    "engine_refinement_claim_evidence_receipt_most_common_row_blocker",
    "engine_refinement_claim_evidence_receipt_required_blocker_count",
    "engine_refinement_claim_evidence_receipt_required_blockers",
    "engine_refinement_claim_evidence_receipt_next_required_step",
    "engine_refinement_claim_evidence_receipt_external_state_mutated",
)

CLAIM_BOUNDARY = (
    "Goal endpoints are read-only local status surfaces for the commercial product, CAMEO validation, "
    "CASP17 transition, and cleanup objective. They do not run docking, assemble bundles, install packages, "
    "submit predictions, register servers, send email, delete, archive, externalize, upload, or mutate external state."
)


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _blockers(packet: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = packet.get("blockers")
    return [row for row in blockers if isinstance(row, dict)] if isinstance(blockers, list) else []


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _accuracy_parity_release_fields(release: dict[str, Any]) -> dict[str, Any]:
    return {
        "accuracy_parity_scorecard_gate_present": bool(
            release.get("accuracy_parity_scorecard_gate_present") is True
        ),
        "accuracy_parity_scorecard_status": release.get("accuracy_parity_scorecard_status", ""),
        "accuracy_parity_scorecard_recorded": bool(
            release.get("accuracy_parity_scorecard_recorded") is True
        ),
        "accuracy_parity_scorecard_row_count": _int(
            release.get("accuracy_parity_scorecard_row_count")
        ),
        "accuracy_parity_scorecard_pass_row_count": _int(
            release.get("accuracy_parity_scorecard_pass_row_count")
        ),
        "accuracy_parity_scorecard_restricted_pass_row_count": _int(
            release.get("accuracy_parity_scorecard_restricted_pass_row_count")
        ),
        "accuracy_parity_scorecard_blocked_row_count": _int(
            release.get("accuracy_parity_scorecard_blocked_row_count")
        ),
        "accuracy_parity_scorecard_missing_row_count": _int(
            release.get("accuracy_parity_scorecard_missing_row_count")
        ),
        "accuracy_parity_scorecard_top_blocker_count": _int(
            release.get("accuracy_parity_scorecard_top_blocker_count")
        ),
        "accuracy_parity_scorecard_top_blockers": _string_list(
            release.get("accuracy_parity_scorecard_top_blockers")
        ),
        "accuracy_parity_scorecard_overall_commercial_tool_accuracy_parity_allowed": bool(
            release.get("accuracy_parity_scorecard_overall_commercial_tool_accuracy_parity_allowed")
            is True
        ),
        "accuracy_parity_scorecard_schrodinger_class_claim_allowed": bool(
            release.get("accuracy_parity_scorecard_schrodinger_class_claim_allowed") is True
        ),
        "accuracy_parity_scorecard_openmm_class_claim_allowed": bool(
            release.get("accuracy_parity_scorecard_openmm_class_claim_allowed") is True
        ),
        "accuracy_parity_scorecard_current_broad_accuracy_parity_estimate_pct": release.get(
            "accuracy_parity_scorecard_current_broad_accuracy_parity_estimate_pct", ""
        ),
        "accuracy_parity_scorecard_current_broad_commercial_platform_estimate_pct": release.get(
            "accuracy_parity_scorecard_current_broad_commercial_platform_estimate_pct", ""
        ),
        "accuracy_parity_ligand_ranking_status": release.get(
            "accuracy_parity_ligand_ranking_status", ""
        ),
        "accuracy_parity_ligand_ranking_claim_promotion_allowed": bool(
            release.get("accuracy_parity_ligand_ranking_claim_promotion_allowed") is True
        ),
        "accuracy_parity_ligand_ranking_commercial_parity_claim_allowed": bool(
            release.get("accuracy_parity_ligand_ranking_commercial_parity_claim_allowed") is True
        ),
        "accuracy_parity_ligand_ranking_blocker_count": _int(
            release.get("accuracy_parity_ligand_ranking_blocker_count")
        ),
        "accuracy_parity_ligand_ranking_blockers": _string_list(
            release.get("accuracy_parity_ligand_ranking_blockers")
        ),
        "accuracy_parity_ligand_ranking_pr_auc": _float(
            release.get("accuracy_parity_ligand_ranking_pr_auc")
        ),
        "accuracy_parity_ligand_ranking_pr_auc_ci_low": _float(
            release.get("accuracy_parity_ligand_ranking_pr_auc_ci_low")
        ),
        "accuracy_parity_ligand_ranking_topk_hit_rate": _float(
            release.get("accuracy_parity_ligand_ranking_topk_hit_rate")
        ),
        "accuracy_parity_ligand_ranking_positive_count": _int(
            release.get("accuracy_parity_ligand_ranking_positive_count")
        ),
        "accuracy_parity_ligand_ranking_score_col_used": release.get(
            "accuracy_parity_ligand_ranking_score_col_used", ""
        ),
        "accuracy_parity_ligand_ranking_pr_auc_threshold": _float(
            release.get("accuracy_parity_ligand_ranking_pr_auc_threshold")
        ),
        "accuracy_parity_ligand_ranking_pr_auc_ci_low_threshold": _float(
            release.get("accuracy_parity_ligand_ranking_pr_auc_ci_low_threshold")
        ),
        "accuracy_parity_ligand_ranking_topk_hit_rate_threshold": _float(
            release.get("accuracy_parity_ligand_ranking_topk_hit_rate_threshold")
        ),
        "accuracy_parity_ligand_ranking_next_required_step": release.get(
            "accuracy_parity_ligand_ranking_next_required_step", ""
        ),
    }


def _api_runner_profile_receipt_release_fields(release: dict[str, Any]) -> dict[str, Any]:
    return {
        "api_runner_profile_promotion_operator_receipt_gate_present": bool(
            release.get("api_runner_profile_promotion_operator_receipt_gate_present") is True
        ),
        "api_runner_profile_promotion_operator_receipt_status": release.get(
            "api_runner_profile_promotion_operator_receipt_status", ""
        ),
        "api_runner_profile_promotion_operator_receipt_recorded": bool(
            release.get("api_runner_profile_promotion_operator_receipt_recorded") is True
        ),
        "api_runner_profile_promotion_operator_receipt_ready": bool(
            release.get("api_runner_profile_promotion_operator_receipt_ready") is True
        ),
        "api_runner_profile_promotion_operator_receipt_readiness_status": release.get(
            "api_runner_profile_promotion_operator_receipt_readiness_status", ""
        ),
        "api_runner_profile_promotion_operator_receipt_profile_count": _int(
            release.get("api_runner_profile_promotion_operator_receipt_profile_count")
        ),
        "api_runner_profile_promotion_operator_receipt_receipt_row_count": _int(
            release.get("api_runner_profile_promotion_operator_receipt_receipt_row_count")
        ),
        "api_runner_profile_promotion_operator_receipt_pass_row_count": _int(
            release.get("api_runner_profile_promotion_operator_receipt_pass_row_count")
        ),
        "api_runner_profile_promotion_operator_receipt_blocked_row_count": _int(
            release.get("api_runner_profile_promotion_operator_receipt_blocked_row_count")
        ),
        "api_runner_profile_promotion_operator_receipt_blocker_count": _int(
            release.get("api_runner_profile_promotion_operator_receipt_blocker_count")
        ),
        "api_runner_profile_promotion_operator_receipt_blockers": _string_list(
            release.get("api_runner_profile_promotion_operator_receipt_blockers")
        ),
        "api_runner_profile_promotion_operator_receipt_first_blocked_profile_id": release.get(
            "api_runner_profile_promotion_operator_receipt_first_blocked_profile_id", ""
        ),
        "api_runner_profile_promotion_operator_receipt_first_blocked_row_blocker": release.get(
            "api_runner_profile_promotion_operator_receipt_first_blocked_row_blocker", ""
        ),
        "api_runner_profile_promotion_operator_receipt_first_blocked_row_blockers": _string_list(
            release.get("api_runner_profile_promotion_operator_receipt_first_blocked_row_blockers")
        ),
        "api_runner_profile_promotion_operator_receipt_most_common_row_blocker": release.get(
            "api_runner_profile_promotion_operator_receipt_most_common_row_blocker", ""
        ),
        "api_runner_profile_promotion_operator_receipt_approval_token_required": release.get(
            "api_runner_profile_promotion_operator_receipt_approval_token_required", ""
        ),
        "api_runner_profile_promotion_operator_receipt_operator_template_csv": release.get(
            "api_runner_profile_promotion_operator_receipt_operator_template_csv", ""
        ),
        "api_runner_profile_promotion_operator_receipt_next_required_step": release.get(
            "api_runner_profile_promotion_operator_receipt_next_required_step", ""
        ),
        "api_runner_profile_promotion_operator_receipt_profile_enabled_by_this_tool": bool(
            release.get("api_runner_profile_promotion_operator_receipt_profile_enabled_by_this_tool")
            is True
        ),
        "api_runner_profile_promotion_operator_receipt_runner_executed": bool(
            release.get("api_runner_profile_promotion_operator_receipt_runner_executed") is True
        ),
        "api_runner_profile_promotion_operator_receipt_external_state_mutated": bool(
            release.get("api_runner_profile_promotion_operator_receipt_external_state_mutated")
            is True
        ),
    }


def _pose_sampling_release_fields(release: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_pose_sampling_readiness_gate_present": bool(
            release.get("product_pose_sampling_readiness_gate_present") is True
        ),
        "product_pose_sampling_readiness_status": release.get(
            "product_pose_sampling_readiness_status", ""
        ),
        "product_pose_sampling_readiness_recorded": bool(
            release.get("product_pose_sampling_readiness_recorded") is True
        ),
        "product_pose_sampling_readiness_ready": bool(
            release.get("product_pose_sampling_readiness_ready") is True
        ),
        "product_pose_sampling_readiness_pose_generation_contract_ready": bool(
            release.get("product_pose_sampling_readiness_pose_generation_contract_ready")
            is True
        ),
        "product_pose_sampling_readiness_pocket_detection_ready": bool(
            release.get("product_pose_sampling_readiness_pocket_detection_ready") is True
        ),
        "product_pose_sampling_readiness_multi_start_pose_ensemble_ready": bool(
            release.get("product_pose_sampling_readiness_multi_start_pose_ensemble_ready")
            is True
        ),
        "product_pose_sampling_readiness_pose_centroid_pocket_bound_ready": bool(
            release.get("product_pose_sampling_readiness_pose_centroid_pocket_bound_ready")
            is True
        ),
        "product_pose_sampling_readiness_pose_rmsd_diversity_surface_ready": bool(
            release.get("product_pose_sampling_readiness_pose_rmsd_diversity_surface_ready")
            is True
        ),
        "product_pose_sampling_readiness_bounded_cross_docking_induced_fit_guard_ready": bool(
            release.get(
                "product_pose_sampling_readiness_bounded_cross_docking_induced_fit_guard_ready"
            )
            is True
        ),
        "product_pose_sampling_readiness_pose_claim_boundary_guard_ready": bool(
            release.get("product_pose_sampling_readiness_pose_claim_boundary_guard_ready")
            is True
        ),
        "product_pose_sampling_readiness_check_count": _int(
            release.get("product_pose_sampling_readiness_check_count")
        ),
        "product_pose_sampling_readiness_pass_count": _int(
            release.get("product_pose_sampling_readiness_pass_count")
        ),
        "product_pose_sampling_readiness_blocker_count": _int(
            release.get("product_pose_sampling_readiness_blocker_count")
        ),
        "product_pose_sampling_readiness_requested_pose_start_count": _int(
            release.get("product_pose_sampling_readiness_requested_pose_start_count")
        ),
        "product_pose_sampling_readiness_pose_count": _int(
            release.get("product_pose_sampling_readiness_pose_count")
        ),
        "product_pose_sampling_readiness_cluster_count": _int(
            release.get("product_pose_sampling_readiness_cluster_count")
        ),
        "product_pose_sampling_readiness_cross_docking_pose_count": _int(
            release.get("product_pose_sampling_readiness_cross_docking_pose_count")
        ),
        "product_pose_sampling_readiness_pocket_method": release.get(
            "product_pose_sampling_readiness_pocket_method", ""
        ),
        "product_pose_sampling_readiness_claim_grade_pose_accuracy_ready": bool(
            release.get("product_pose_sampling_readiness_claim_grade_pose_accuracy_ready")
            is True
        ),
        "product_pose_sampling_readiness_claim_grade_induced_fit_ready": bool(
            release.get("product_pose_sampling_readiness_claim_grade_induced_fit_ready")
            is True
        ),
        "product_pose_sampling_readiness_claim_grade_cross_docking_ready": bool(
            release.get("product_pose_sampling_readiness_claim_grade_cross_docking_ready")
            is True
        ),
        "product_pose_sampling_readiness_docking_results_emitted": bool(
            release.get("product_pose_sampling_readiness_docking_results_emitted") is True
        ),
        "product_pose_sampling_readiness_execution_enabled": bool(
            release.get("product_pose_sampling_readiness_execution_enabled") is True
        ),
        "product_pose_sampling_readiness_external_state_mutated": bool(
            release.get("product_pose_sampling_readiness_external_state_mutated") is True
        ),
        "product_pose_sampling_readiness_next_required_step": release.get(
            "product_pose_sampling_readiness_next_required_step", ""
        ),
    }


def _ledger_privacy_scan_release_fields(release: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_ledger_privacy_scan_gate_present": bool(
            release.get("product_ledger_privacy_scan_gate_present") is True
        ),
        "product_ledger_privacy_scan_status": release.get(
            "product_ledger_privacy_scan_status", ""
        ),
        "product_ledger_privacy_scan_recorded": bool(
            release.get("product_ledger_privacy_scan_recorded") is True
        ),
        "product_ledger_privacy_scan_ready": bool(
            release.get("product_ledger_privacy_scan_ready") is True
        ),
        "product_ledger_privacy_scan_scan_file_count": _int(
            release.get("product_ledger_privacy_scan_scan_file_count")
        ),
        "product_ledger_privacy_scan_scan_glob_count": _int(
            release.get("product_ledger_privacy_scan_scan_glob_count")
        ),
        "product_ledger_privacy_scan_pass_count": _int(
            release.get("product_ledger_privacy_scan_pass_count")
        ),
        "product_ledger_privacy_scan_blocker_count": _int(
            release.get("product_ledger_privacy_scan_blocker_count")
        ),
        "product_ledger_privacy_scan_leak_count": _int(
            release.get("product_ledger_privacy_scan_leak_count")
        ),
        "product_ledger_privacy_scan_invalid_json_count": _int(
            release.get("product_ledger_privacy_scan_invalid_json_count")
        ),
        "product_ledger_privacy_scan_blocked_artifact_path_count": _int(
            release.get("product_ledger_privacy_scan_blocked_artifact_path_count")
        ),
        "product_ledger_privacy_scan_invalid_json_path_count": _int(
            release.get("product_ledger_privacy_scan_invalid_json_path_count")
        ),
        "product_ledger_privacy_scan_execution_enabled": bool(
            release.get("product_ledger_privacy_scan_execution_enabled") is True
        ),
        "product_ledger_privacy_scan_external_state_mutated": bool(
            release.get("product_ledger_privacy_scan_external_state_mutated") is True
        ),
        "product_ledger_privacy_scan_next_required_step": release.get(
            "product_ledger_privacy_scan_next_required_step", ""
        ),
    }


def _refine_tier_public_benchmark_release_fields(release: dict[str, Any]) -> dict[str, Any]:
    return {
        "refine_tier_public_benchmark_gate_present": bool(
            release.get("refine_tier_public_benchmark_gate_present") is True
        ),
        "refine_tier_public_benchmark_status": release.get(
            "refine_tier_public_benchmark_status", ""
        ),
        "refine_tier_public_benchmark_recorded": bool(
            release.get("refine_tier_public_benchmark_recorded") is True
        ),
        "refine_tier_public_benchmark_input_csv": release.get(
            "refine_tier_public_benchmark_input_csv", ""
        ),
        "refine_tier_public_benchmark_input_csv_present": bool(
            release.get("refine_tier_public_benchmark_input_csv_present") is True
        ),
        "refine_tier_public_benchmark_claim_grade_public_benchmark_ready": bool(
            release.get("refine_tier_public_benchmark_claim_grade_public_benchmark_ready")
            is True
        ),
        "refine_tier_public_benchmark_benchmark_metric_surface_ready": bool(
            release.get("refine_tier_public_benchmark_benchmark_metric_surface_ready") is True
        ),
        "refine_tier_public_benchmark_row_count": _int(
            release.get("refine_tier_public_benchmark_row_count")
        ),
        "refine_tier_public_benchmark_valid_row_count": _int(
            release.get("refine_tier_public_benchmark_valid_row_count")
        ),
        "refine_tier_public_benchmark_pose_metric_row_count": _int(
            release.get("refine_tier_public_benchmark_pose_metric_row_count")
        ),
        "refine_tier_public_benchmark_pose_metric_pass_count": _int(
            release.get("refine_tier_public_benchmark_pose_metric_pass_count")
        ),
        "refine_tier_public_benchmark_free_energy_pair_count": _int(
            release.get("refine_tier_public_benchmark_free_energy_pair_count")
        ),
        "refine_tier_public_benchmark_blocker_count": _int(
            release.get("refine_tier_public_benchmark_blocker_count")
        ),
        "refine_tier_public_benchmark_min_total_rows_required": _int(
            release.get("refine_tier_public_benchmark_min_total_rows_required")
        ),
        "refine_tier_public_benchmark_min_pose_rows_required": _int(
            release.get("refine_tier_public_benchmark_min_pose_rows_required")
        ),
        "refine_tier_public_benchmark_min_free_energy_pairs_required": _int(
            release.get("refine_tier_public_benchmark_min_free_energy_pairs_required")
        ),
        "refine_tier_public_benchmark_operator_work_order_ready": bool(
            release.get("refine_tier_public_benchmark_operator_work_order_ready") is True
        ),
        "refine_tier_public_benchmark_work_order_csv": release.get(
            "refine_tier_public_benchmark_work_order_csv", ""
        ),
        "refine_tier_public_benchmark_work_order_row_count": _int(
            release.get("refine_tier_public_benchmark_work_order_row_count")
        ),
        "refine_tier_public_benchmark_write_intake_approval_token_required": release.get(
            "refine_tier_public_benchmark_write_intake_approval_token_required", ""
        ),
        "refine_tier_public_benchmark_external_state_mutated": bool(
            release.get("refine_tier_public_benchmark_external_state_mutated") is True
        ),
        "refine_tier_public_benchmark_next_required_step": release.get(
            "refine_tier_public_benchmark_next_required_step", ""
        ),
        "refine_tier_public_benchmark_work_order_apply_gate_present": bool(
            release.get("refine_tier_public_benchmark_work_order_apply_gate_present") is True
        ),
        "refine_tier_public_benchmark_work_order_apply_status": release.get(
            "refine_tier_public_benchmark_work_order_apply_status", ""
        ),
        "refine_tier_public_benchmark_work_order_apply_recorded": bool(
            release.get("refine_tier_public_benchmark_work_order_apply_recorded") is True
        ),
        "refine_tier_public_benchmark_work_order_apply_aggregate_readiness_required": bool(
            release.get(
                "refine_tier_public_benchmark_work_order_apply_aggregate_readiness_required"
            )
            is True
        ),
        "refine_tier_public_benchmark_work_order_apply_apply_ready": bool(
            release.get("refine_tier_public_benchmark_work_order_apply_apply_ready") is True
        ),
        "refine_tier_public_benchmark_work_order_apply_work_order_csv": release.get(
            "refine_tier_public_benchmark_work_order_apply_work_order_csv", ""
        ),
        "refine_tier_public_benchmark_work_order_apply_work_order_csv_present": bool(
            release.get(
                "refine_tier_public_benchmark_work_order_apply_work_order_csv_present"
            )
            is True
        ),
        "refine_tier_public_benchmark_work_order_apply_work_order_row_count": _int(
            release.get("refine_tier_public_benchmark_work_order_apply_work_order_row_count")
        ),
        "refine_tier_public_benchmark_work_order_apply_blocked_row_count": _int(
            release.get("refine_tier_public_benchmark_work_order_apply_blocked_row_count")
        ),
        "refine_tier_public_benchmark_work_order_apply_valid_intake_row_count": _int(
            release.get("refine_tier_public_benchmark_work_order_apply_valid_intake_row_count")
        ),
        "refine_tier_public_benchmark_work_order_apply_blocker_count": _int(
            release.get("refine_tier_public_benchmark_work_order_apply_blocker_count")
        ),
        "refine_tier_public_benchmark_work_order_apply_duplicate_benchmark_id_count": _int(
            release.get(
                "refine_tier_public_benchmark_work_order_apply_duplicate_benchmark_id_count"
            )
        ),
        "refine_tier_public_benchmark_work_order_apply_candidate_intake_written": bool(
            release.get(
                "refine_tier_public_benchmark_work_order_apply_candidate_intake_written"
            )
            is True
        ),
        "refine_tier_public_benchmark_work_order_apply_candidate_readiness_checked": bool(
            release.get(
                "refine_tier_public_benchmark_work_order_apply_candidate_readiness_checked"
            )
            is True
        ),
        "refine_tier_public_benchmark_work_order_apply_candidate_claim_grade_public_benchmark_ready": bool(
            release.get(
                "refine_tier_public_benchmark_work_order_apply_candidate_claim_grade_public_benchmark_ready"
            )
            is True
        ),
        "refine_tier_public_benchmark_work_order_apply_intake_written": bool(
            release.get("refine_tier_public_benchmark_work_order_apply_intake_written") is True
        ),
        "refine_tier_public_benchmark_work_order_apply_write_intake_requested": bool(
            release.get("refine_tier_public_benchmark_work_order_apply_write_intake_requested")
            is True
        ),
        "refine_tier_public_benchmark_work_order_apply_approval_token_present": bool(
            release.get("refine_tier_public_benchmark_work_order_apply_approval_token_present")
            is True
        ),
        "refine_tier_public_benchmark_work_order_apply_approval_token_accepted": bool(
            release.get("refine_tier_public_benchmark_work_order_apply_approval_token_accepted")
            is True
        ),
        "refine_tier_public_benchmark_work_order_apply_target_intake_csv": release.get(
            "refine_tier_public_benchmark_work_order_apply_target_intake_csv", ""
        ),
        "refine_tier_public_benchmark_work_order_apply_external_state_mutated": bool(
            release.get("refine_tier_public_benchmark_work_order_apply_external_state_mutated")
            is True
        ),
        "refine_tier_public_benchmark_work_order_apply_next_required_step": release.get(
            "refine_tier_public_benchmark_work_order_apply_next_required_step", ""
        ),
    }


def _bottleneck_id(row: dict[str, Any]) -> str:
    return str(row.get("bottleneck_id") or row.get("requirement_id") or row.get("phase") or "").strip()


def _mutation_flags() -> dict[str, bool]:
    return {
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "upload_executed": False,
        "docking_results_emitted": False,
        "prediction_generation_enabled": False,
        "server_registration_mutated": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


def _production_ai_registry_promotion_receipt_fields(handoff: dict[str, Any]) -> dict[str, Any]:
    return {
        "production_ai_registry_promotion_operator_receipt_status": handoff.get(
            "production_ai_registry_promotion_operator_receipt_status", ""
        ),
        "production_ai_registry_promotion_operator_receipt_ready": bool(
            handoff.get("production_ai_registry_promotion_operator_receipt_ready") is True
        ),
        "production_ai_registry_promotion_operator_receipt_artifact": handoff.get(
            "production_ai_registry_promotion_operator_receipt_artifact", ""
        ),
        "production_ai_registry_promotion_operator_receipt_csv": handoff.get(
            "production_ai_registry_promotion_operator_receipt_csv", ""
        ),
        "production_ai_registry_promotion_operator_receipt_approval_token_required": handoff.get(
            "production_ai_registry_promotion_operator_receipt_approval_token_required", ""
        ),
        "production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker": handoff.get(
            "production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker", ""
        ),
        "production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode": handoff.get(
            "production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode",
            "",
        ),
        "production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count": _int(
            handoff.get(
                "production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count"
            )
        ),
        "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_currently_satisfied": bool(
            handoff.get(
                "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_currently_satisfied"
            )
            is True
        ),
        "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_missing_gate_ids": _string_list(
            handoff.get(
                "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_missing_gate_ids"
            )
        ),
        "production_ai_registry_promotion_priority_artifact": handoff.get(
            "production_ai_registry_promotion_priority_artifact", ""
        ),
        "production_ai_registry_promotion_priority_status": handoff.get(
            "production_ai_registry_promotion_priority_status", ""
        ),
        "production_ai_registry_promotion_priority_packet_ready": bool(
            handoff.get("production_ai_registry_promotion_priority_packet_ready") is True
        ),
        "production_ai_registry_promotion_priority_registry_promotion_ready": bool(
            handoff.get("production_ai_registry_promotion_priority_registry_promotion_ready")
            is True
        ),
        "production_ai_registry_promotion_priority_operator_input_required_count": _int(
            handoff.get("production_ai_registry_promotion_priority_operator_input_required_count")
        ),
        "production_ai_registry_promotion_priority_blocked_priority_item_count": _int(
            handoff.get("production_ai_registry_promotion_priority_blocked_priority_item_count")
        ),
        "production_ai_registry_promotion_priority_missing_gate_count": _int(
            handoff.get("production_ai_registry_promotion_priority_missing_gate_count")
        ),
        "production_ai_registry_promotion_priority_missing_gate_ids": _string_list(
            handoff.get("production_ai_registry_promotion_priority_missing_gate_ids")
        ),
        "production_ai_registry_promotion_priority_top_gate_id": handoff.get(
            "production_ai_registry_promotion_priority_top_gate_id", ""
        ),
        "production_ai_registry_promotion_priority_top_priority_bucket": handoff.get(
            "production_ai_registry_promotion_priority_top_priority_bucket", ""
        ),
        "production_ai_registry_promotion_priority_top_required_input": handoff.get(
            "production_ai_registry_promotion_priority_top_required_input", ""
        ),
        "production_ai_registry_promotion_priority_top_acceptance_artifact": handoff.get(
            "production_ai_registry_promotion_priority_top_acceptance_artifact", ""
        ),
        "production_ai_registry_promotion_priority_top_verification_command": handoff.get(
            "production_ai_registry_promotion_priority_top_verification_command", ""
        ),
        "production_ai_registry_promotion_priority_top_next_operator_step": handoff.get(
            "production_ai_registry_promotion_priority_top_next_operator_step", ""
        ),
        "production_ai_registry_promotion_priority_model_promoted": bool(
            handoff.get("production_ai_registry_promotion_priority_model_promoted") is True
        ),
        "production_ai_registry_promotion_priority_customer_facing_mutation_enabled": bool(
            handoff.get(
                "production_ai_registry_promotion_priority_customer_facing_mutation_enabled"
            )
            is True
        ),
        "production_ai_registry_promotion_priority_external_state_mutated": bool(
            handoff.get("production_ai_registry_promotion_priority_external_state_mutated") is True
        ),
    }


def _intake_entry(rows: list[dict[str, Any]], entry_id: str) -> dict[str, Any]:
    for row in rows:
        if str(row.get("kit_entry_id") or "").strip() == entry_id:
            return row
    return {}


def _cameo_official_result_fetch_preflight_fields(
    fetch: dict[str, Any],
    intake_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    intake_row = _intake_entry(intake_rows, "cameo_official_result_fetch_preflight")
    status = (
        fetch.get("status")
        or intake_row.get("source_gate_status")
        or ""
    )
    return {
        "cameo_official_result_fetch_preflight_status": status,
        "cameo_official_result_fetch_preflight_ready": bool(
            status == "cameo_official_result_fetch_preflight_ready"
            and fetch.get("authorized_for_separate_operator_fetch") is True
        ),
        "cameo_official_result_fetch_preflight_artifact_path": str(
            CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_ARTIFACT
        ),
        "cameo_official_result_fetch_preflight_operator_template_csv": (
            fetch.get("operator_template_csv")
            or intake_row.get("template_path")
            or ""
        ),
        "cameo_official_result_fetch_preflight_operator_intake_csv": (
            fetch.get("operator_fetch_csv")
            or intake_row.get("intake_path")
            or ""
        ),
        "cameo_official_result_fetch_preflight_kit_template_path": intake_row.get(
            "kit_template_path", ""
        ),
        "cameo_official_result_fetch_preflight_approval_token_required": (
            fetch.get("fetch_approval_token_required")
            or intake_row.get("approval_token_required")
            or ""
        ),
        "cameo_official_result_fetch_preflight_kit_status": intake_row.get(
            "kit_status", ""
        ),
        "cameo_official_result_fetch_preflight_operator_fetch_csv_present": bool(
            fetch.get("operator_fetch_csv_present") is True
            or intake_row.get("intake_present") is True
        ),
        "cameo_official_result_fetch_preflight_authorized_for_separate_operator_fetch": bool(
            fetch.get("authorized_for_separate_operator_fetch") is True
        ),
        "cameo_official_result_fetch_preflight_network_request_opened": bool(
            fetch.get("network_request_opened") is True
        ),
        "cameo_official_result_fetch_preflight_official_results_fetched": bool(
            fetch.get("official_results_fetched") is True
        ),
        "cameo_official_result_fetch_preflight_native_local_accuracy_used": bool(
            fetch.get("native_local_accuracy_used") is True
        ),
        "cameo_official_result_fetch_preflight_external_state_mutated": bool(
            fetch.get("external_state_mutated") is True
        ),
        "cameo_official_result_fetch_preflight_blocker_count": _int(
            fetch.get("blocker_count")
        ),
        "cameo_official_result_fetch_preflight_blockers": _string_list(
            fetch.get("blockers")
        ),
    }


def _evidence_receipt_fields(
    *,
    prefix: str,
    receipt: dict[str, Any],
    artifact_path: Path,
    ready_key: str,
    first_blocked_id_source_key: str,
    first_blocked_id_status_key: str,
    required_blocker_count_key: str,
    required_blockers_key: str,
) -> dict[str, Any]:
    return {
        f"{prefix}_status": receipt.get("status", ""),
        f"{prefix}_ready": bool(receipt.get(ready_key) is True),
        f"{prefix}_artifact_path": str(artifact_path),
        f"{prefix}_csv": receipt.get("receipt_csv", ""),
        f"{prefix}_csv_present": bool(receipt.get("receipt_csv_present") is True),
        f"{prefix}_approval_token_required": receipt.get("approval_token_required", ""),
        f"{prefix}_receipt_row_count": _int(receipt.get("receipt_row_count")),
        f"{prefix}_pass_row_count": _int(receipt.get("pass_row_count")),
        f"{prefix}_blocked_row_count": _int(receipt.get("blocked_row_count")),
        f"{prefix}_blocker_count": _int(receipt.get("blocker_count")),
        f"{prefix}_evidence_artifact_present_count": _int(
            receipt.get("evidence_artifact_present_count")
        ),
        f"{prefix}_evidence_status_verified_count": _int(
            receipt.get("evidence_status_verified_count")
        ),
        f"{prefix}_{first_blocked_id_status_key}": receipt.get(
            first_blocked_id_source_key, ""
        ),
        f"{prefix}_first_blocked_evidence_artifact": receipt.get(
            "first_blocked_evidence_artifact", ""
        ),
        f"{prefix}_first_blocked_expected_evidence_status": receipt.get(
            "first_blocked_expected_evidence_status", ""
        ),
        f"{prefix}_first_blocked_observed_evidence_status": receipt.get(
            "first_blocked_observed_evidence_status", ""
        ),
        f"{prefix}_first_blocked_missing_true_fields": _string_list(
            receipt.get("first_blocked_missing_true_fields")
        ),
        f"{prefix}_first_blocked_row_blockers": _string_list(
            receipt.get("first_blocked_row_blockers")
        ),
        f"{prefix}_most_common_row_blocker": receipt.get("most_common_row_blocker", ""),
        f"{prefix}_required_blocker_count": _int(receipt.get(required_blocker_count_key)),
        f"{prefix}_required_blockers": _string_list(receipt.get(required_blockers_key)),
        f"{prefix}_next_required_step": receipt.get("next_required_step", ""),
        f"{prefix}_external_state_mutated": bool(
            receipt.get("external_state_mutated") is True
        ),
    }


@router.get("/status")
async def get_goal_status() -> dict[str, Any]:
    readiness_packet = _read_json_object(GOAL_READINESS_ROLLUP_ARTIFACT)
    action_packet = _read_json_object(GOAL_OPERATOR_ACTION_BOARD_ARTIFACT)
    intake_packet = _read_json_object(GOAL_OPERATOR_INTAKE_KIT_MANIFEST)
    release_packet = _read_json_object(GOAL_RELEASE_DECISION_ARTIFACT)
    burndown_packet = _read_json_object(GOAL_RELEASE_BURNDOWN_ARTIFACT)
    bottleneck_packet = _read_json_object(GOAL_BOTTLENECK_BRIEFING_ARTIFACT)
    api_contract_packet = _read_json_object(GOAL_API_SURFACE_CONTRACT_ARTIFACT)
    product_goal_completion_packet = _read_json_object(PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT)
    handoff_packet = _read_json_object(PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT)
    full_commercial_matrix_packet = _read_json_object(
        PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT
    )
    scope_receipt_packet = _read_json_object(PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_ARTIFACT)
    engine_receipt_packet = _read_json_object(ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_ARTIFACT)
    cameo_fetch_packet = _read_json_object(CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_ARTIFACT)

    readiness = _summary(readiness_packet)
    actions = _summary(action_packet)
    intake = _summary(intake_packet)
    release = _summary(release_packet)
    burndown = _summary(burndown_packet)
    bottlenecks = _summary(bottleneck_packet)
    api_contract = _summary(api_contract_packet)
    product_goal_completion = _summary(product_goal_completion_packet)
    handoff = _summary(handoff_packet)
    full_commercial_matrix = _summary(full_commercial_matrix_packet)
    scope_receipt = _summary(scope_receipt_packet)
    engine_receipt = _summary(engine_receipt_packet)
    cameo_fetch = _summary(cameo_fetch_packet)
    intake_rows = _rows(intake_packet)
    bottleneck_rows = _rows(bottleneck_packet)
    full_commercial_release_blocker_ids = [
        bottleneck_id
        for row in bottleneck_rows
        for bottleneck_id in [_bottleneck_id(row)]
        if bottleneck_id in FULL_COMMERCIAL_RELEASE_BLOCKER_IDS
    ]
    release_full_commercial_blocker_ids = _string_list(
        release.get("full_commercial_release_blocker_ids")
    ) or list(full_commercial_release_blocker_ids)
    missing_full_commercial_release_blocker_ids = [
        blocker_id
        for blocker_id in FULL_COMMERCIAL_RELEASE_BLOCKER_IDS
        if blocker_id not in release_full_commercial_blocker_ids
    ]
    full_commercial_release_blocker_visibility_ready = (
        not missing_full_commercial_release_blocker_ids
        and len(release_full_commercial_blocker_ids) >= len(FULL_COMMERCIAL_RELEASE_BLOCKER_IDS)
    )
    active_bottleneck_primary = (
        _int(bottlenecks.get("current_bottleneck_count") or bottlenecks.get("bottleneck_count")) > 0
        and bool(bottlenecks.get("primary_action_id"))
    )
    primary_action_source = bottlenecks if active_bottleneck_primary else intake
    if not any([readiness, actions, release, burndown]):
        return {
            "status": "missing_goal_status_artifacts",
            "readiness_artifact_path": str(GOAL_READINESS_ROLLUP_ARTIFACT),
            "action_board_artifact_path": str(GOAL_OPERATOR_ACTION_BOARD_ARTIFACT),
            "release_decision_artifact_path": str(GOAL_RELEASE_DECISION_ARTIFACT),
            "burndown_artifact_path": str(GOAL_RELEASE_BURNDOWN_ARTIFACT),
            "primary_action_id": "",
            "primary_action_status": "",
            "primary_action_required_input": "",
            "primary_action_command": "",
            "primary_action_recommended_action": "",
            "primary_action_artifact_path": "",
            "primary_bottleneck_root_cause_category": "",
            "primary_bottleneck_locally_closable_without_operator_return": False,
            "primary_bottleneck_required_external_return": "",
            "primary_bottleneck_post_return_acceptance_artifact": "",
            "completion_audit_release_blocker_bottleneck_count": 0,
            "irreducible_external_return_bottleneck_count": 0,
            "expected_full_commercial_release_blocker_ids": list(FULL_COMMERCIAL_RELEASE_BLOCKER_IDS),
            "full_commercial_release_blocker_ids": [],
            "full_commercial_release_blocker_count": 0,
            "missing_full_commercial_release_blocker_ids": list(FULL_COMMERCIAL_RELEASE_BLOCKER_IDS),
            "full_commercial_release_blocker_visibility_ready": False,
            "restricted_release_allowed": False,
            "full_commercial_release_allowed": False,
            "primary_full_commercial_release_blocker_id": "",
            "primary_full_commercial_release_blocker": "",
            "full_commercial_release_next_required_step": "",
            "master_gap_closure_rollup_status": "",
            "master_gap_closure_rollup_recorded": False,
            "master_gap_closure_rollup_all_gaps_closed": False,
            "master_gap_closure_rollup_claim_promotion_allowed": False,
            "master_gap_closure_rollup_open_gap_count": 0,
            "master_gap_closure_rollup_open_gap_ids": [],
            "master_gap_closure_rollup_closed_gap_count": 0,
            "master_gap_closure_rollup_closed_gap_ids": [],
            "master_gap_closure_rollup_release_blocker_row_count": 0,
            "master_gap_closure_rollup_current_primary_open_gap_id": "",
            "master_gap_closure_rollup_science_claim_rollup_status": "",
            "master_gap_closure_rollup_science_claim_evidence": "",
            "master_gap_closure_rollup_science_claim_release_blocker": False,
            "science_claim_promotion_gap_closure_status": "",
            "science_claim_promotion_gap_closure_recorded": False,
            "science_claim_promotion_gap_closure_all_gaps_closed": False,
            "science_claim_promotion_gap_closure_claim_promotion_allowed": False,
            "science_claim_promotion_gap_closure_open_gap_count": 0,
            "science_claim_promotion_gap_closure_open_gap_ids": [],
            "science_claim_promotion_gap_closure_closed_gap_count": 0,
            "science_claim_promotion_gap_closure_closed_gap_ids": [],
            "science_claim_promotion_gap_closure_release_blocker_row_count": 0,
            "science_claim_promotion_gap_closure_current_primary_open_gap_id": "",
            "science_claim_promotion_gap_closure_current_next_action": "",
            "science_claim_promotion_gap_closure_primary_open_gap_area": "",
            "science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status": "",
            "science_claim_promotion_gap_closure_primary_open_gap_evidence": "",
            "science_claim_promotion_gap_closure_primary_open_gap_next_action": "",
            "science_claim_promotion_gap_closure_primary_open_gap_release_blocker": False,
            "science_claim_promotion_gap_closure_gpcr_claim_promotion_status": "",
            "science_claim_promotion_gap_closure_gpcr_evidence": "",
            "science_claim_promotion_gap_closure_gpcr_release_blocker": False,
            "science_claim_promotion_gap_closure_openmm_claim_promotion_status": "",
            "science_claim_promotion_gap_closure_openmm_evidence": "",
            "science_claim_promotion_gap_closure_openmm_release_blocker": False,
            **_accuracy_parity_release_fields({}),
            **_api_runner_profile_receipt_release_fields({}),
            **_pose_sampling_release_fields({}),
            **_ledger_privacy_scan_release_fields({}),
            **_refine_tier_public_benchmark_release_fields({}),
            "product_goal_release_blocker_fail_count": 0,
            "product_goal_release_blocker_requirement_ids": [],
            "product_goal_primary_release_blocker_requirement_id": "",
            "product_goal_primary_release_blocker_tier": "",
            "product_goal_primary_release_blocker": "",
            "product_goal_primary_release_blocker_next_command": "",
            "primary_release_blocker_action_id": "",
            "primary_release_blocker_action_status": "",
            "primary_release_blocker_action_required_input": "",
            "primary_release_blocker_action_artifact_path": "",
            "primary_release_blocker_action_recommended_action": "",
            "product_accuracy_parity_action_count": 0,
            "product_accuracy_parity_ligand_ranking_action_id": "",
            "product_accuracy_parity_ligand_ranking_action_present": False,
            "product_accuracy_parity_scorecard_status": "",
            "product_accuracy_parity_ligand_ranking_action_status": "",
            "product_accuracy_parity_ligand_ranking_blocker_count": 0,
            "product_accuracy_parity_ligand_ranking_blockers": [],
            "product_accuracy_parity_ligand_ranking_pr_auc": 0.0,
            "product_accuracy_parity_ligand_ranking_pr_auc_ci_low": 0.0,
            "product_accuracy_parity_ligand_ranking_topk_hit_rate": 0.0,
            "product_accuracy_parity_ligand_ranking_next_required_step": "",
            "product_accuracy_parity_scorecard_json": "",
            "product_goal_completion_audit_artifact_path": str(PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT),
            "production_ai_checkpoint_registry_promotion_required_gate_ids": [],
            "production_ai_checkpoint_registry_promotion_missing_gate_ids": [],
            "production_ai_checkpoint_registry_promotion_missing_gate_count": 0,
            "production_ai_checkpoint_registry_promotion_upstream_acceptance_ready": False,
            "production_ai_checkpoint_registry_promotion_currently_satisfied": False,
            "production_ai_checkpoint_actionable_operator_completion_packet_ready": False,
            "production_ai_checkpoint_actionable_operator_completion_artifact_id": "",
            "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns": [],
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands": [],
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count": 0,
            "production_ai_checkpoint_actionable_operator_completion_completion_rule": "",
            "production_ai_checkpoint_actionable_operator_completion_next_action": "",
            "commercial_readiness_handoff_bundle_status": "",
            "commercial_readiness_handoff_bundle_ready": False,
            "commercial_readiness_handoff_bundle_artifact_path": str(
                PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT
            ),
            "commercial_readiness_handoff_bundle_artifact_reference_count": 0,
            "commercial_readiness_handoff_bundle_local_missing_artifact_reference_count": 0,
            "operator_intake_kit_full_commercial_evidence_receipt_entry_count": 0,
            "operator_intake_kit_full_commercial_evidence_receipt_operator_input_required_count": 0,
            "operator_intake_kit_full_commercial_evidence_receipt_current_action_required_count": 0,
            "operator_intake_kit_full_commercial_evidence_receipt_template_required_count": 0,
            "operator_intake_kit_full_commercial_evidence_receipt_template_present_count": 0,
            "operator_intake_kit_full_commercial_evidence_receipt_approval_token_count": 0,
            "operator_intake_kit_full_commercial_evidence_receipt_entry_ids": [],
            "operator_intake_kit_full_commercial_evidence_receipt_source_gate_statuses": "",
            "operator_intake_kit_full_commercial_evidence_receipt_required_inputs": "",
            "operator_intake_kit_full_commercial_evidence_receipt_approval_tokens": "",
            "operator_intake_kit_product_scope_breadth_evidence_priority_status": "",
            "operator_intake_kit_product_scope_breadth_evidence_priority_packet_ready": False,
            "operator_intake_kit_product_scope_breadth_evidence_priority_open_item_count": 0,
            "operator_intake_kit_product_scope_breadth_evidence_priority_scientific_evidence_request_count": 0,
            "operator_intake_kit_product_scope_breadth_evidence_priority_top_item_id": "",
            "operator_intake_kit_product_scope_breadth_evidence_priority_top_domain": "",
            "operator_intake_kit_product_scope_breadth_evidence_priority_top_bucket": "",
            "operator_intake_kit_product_scope_breadth_evidence_priority_top_required_evidence_type": "",
            "operator_intake_kit_product_scope_breadth_evidence_priority_top_review_template_artifact": "",
            "operator_intake_kit_product_scope_breadth_evidence_priority_top_apply_gate_artifact": "",
            "operator_intake_kit_product_scope_breadth_evidence_priority_top_next_step": "",
            "operator_intake_kit_product_scope_breadth_evidence_priority_scope_promotion_allowed": False,
            "operator_intake_kit_product_scope_breadth_evidence_priority_authoritative_apply_allowed": False,
            "operator_intake_kit_product_scope_breadth_evidence_priority_external_state_mutated": False,
            "bottleneck_briefing_full_commercial_evidence_receipt_entry_count": 0,
            "bottleneck_briefing_full_commercial_evidence_receipt_operator_input_required_count": 0,
            "bottleneck_briefing_full_commercial_evidence_receipt_current_action_required_count": 0,
            "bottleneck_briefing_full_commercial_evidence_receipt_template_required_count": 0,
            "bottleneck_briefing_full_commercial_evidence_receipt_template_present_count": 0,
            "bottleneck_briefing_full_commercial_evidence_receipt_approval_token_count": 0,
            "bottleneck_briefing_full_commercial_evidence_receipt_entry_ids": [],
            "bottleneck_briefing_full_commercial_evidence_receipt_source_gate_statuses": "",
            "bottleneck_briefing_full_commercial_evidence_receipt_required_inputs": "",
            "bottleneck_briefing_full_commercial_evidence_receipt_approval_tokens": "",
            "bottleneck_briefing_product_scope_breadth_evidence_priority_status": "",
            "bottleneck_briefing_product_scope_breadth_evidence_priority_packet_ready": False,
            "bottleneck_briefing_product_scope_breadth_evidence_priority_open_item_count": 0,
            "bottleneck_briefing_product_scope_breadth_evidence_priority_scientific_evidence_request_count": 0,
            "bottleneck_briefing_product_scope_breadth_evidence_priority_top_item_id": "",
            "bottleneck_briefing_product_scope_breadth_evidence_priority_top_domain": "",
            "bottleneck_briefing_product_scope_breadth_evidence_priority_top_bucket": "",
            "bottleneck_briefing_product_scope_breadth_evidence_priority_top_required_evidence_type": "",
            "bottleneck_briefing_product_scope_breadth_evidence_priority_top_review_template_artifact": "",
            "bottleneck_briefing_product_scope_breadth_evidence_priority_top_apply_gate_artifact": "",
            "bottleneck_briefing_product_scope_breadth_evidence_priority_top_next_step": "",
            "bottleneck_briefing_product_scope_breadth_evidence_priority_scope_promotion_allowed": False,
            "bottleneck_briefing_product_scope_breadth_evidence_priority_authoritative_apply_allowed": False,
            "bottleneck_briefing_product_scope_breadth_evidence_priority_external_state_mutated": False,
            **_production_ai_registry_promotion_receipt_fields({}),
            **_cameo_official_result_fetch_preflight_fields({}, []),
            **_evidence_receipt_fields(
                prefix="product_scope_breadth_evidence_receipt",
                receipt={},
                artifact_path=PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_ARTIFACT,
                ready_key="full_scope_evidence_receipt_ready",
                first_blocked_id_source_key="first_blocked_scope_blocker_id",
                first_blocked_id_status_key="first_blocked_scope_blocker_id",
                required_blocker_count_key="required_scope_blocker_count",
                required_blockers_key="required_scope_blockers",
            ),
            **_evidence_receipt_fields(
                prefix="engine_refinement_claim_evidence_receipt",
                receipt={},
                artifact_path=ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_ARTIFACT,
                ready_key="claim_promotion_evidence_receipt_ready",
                first_blocked_id_source_key="first_blocked_blocker_id",
                first_blocked_id_status_key="first_blocked_blocker_id",
                required_blocker_count_key="required_blocker_count",
                required_blockers_key="required_blockers",
            ),
            "full_commercial_blocker_evidence_matrix_status": "",
            "full_commercial_blocker_evidence_matrix_ready": False,
            "full_commercial_blocker_evidence_matrix_artifact_path": str(
                PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT
            ),
            "full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready": False,
            "full_commercial_blocker_evidence_matrix_row_count": 0,
            "full_commercial_blocker_evidence_matrix_blocked_row_count": 0,
            "full_commercial_blocker_evidence_matrix_approval_token_count": 0,
            "full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id": "",
            "full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id": "",
            "full_commercial_blocker_evidence_matrix_first_blocked_evidence_artifact": "",
            "full_commercial_blocker_evidence_matrix_first_blocked_expected_evidence_status": "",
            "full_commercial_blocker_evidence_matrix_first_blocked_observed_evidence_status": "",
            "full_commercial_blocker_evidence_matrix_first_blocked_row_blockers": "",
            "full_commercial_blocker_evidence_matrix_first_blocked_acceptance_artifact": "",
            "full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker": "",
            "full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker": "",
            "product_quality_gate_verification_status": "",
            "product_quality_gate_verification_recorded": False,
            "product_quality_gate_verification_ready": False,
            "product_quality_gate_verification_source_contract_status": "",
            "product_quality_gate_verification_check_count": 0,
            "product_quality_gate_verification_pass_count": 0,
            "product_quality_gate_verification_blocker_count": 0,
            "product_quality_gate_verification_execution_enabled": False,
            "product_quality_gate_verification_external_state_mutated": False,
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }

    return {
        "status": release.get("status") or readiness.get("status") or actions.get("status") or burndown.get("status"),
        "readiness_status": readiness.get("status", ""),
        "release_complete_vs_operator_pending_lane": readiness.get(
            "release_complete_vs_operator_pending_lane", ""
        ),
        "goal_completion_audit_goal_complete": readiness.get("goal_completion_audit_goal_complete"),
        "release_complete_lane_ready": readiness.get("release_complete_lane_ready"),
        "operator_pending_lane_ready": readiness.get("operator_pending_lane_ready"),
        "operator_action_board_status": actions.get("status", ""),
        "operator_intake_kit_status": intake.get("status", ""),
        "release_decision_status": release.get("status", ""),
        "release_burndown_status": burndown.get("status", ""),
        "bottleneck_briefing_status": bottlenecks.get("status", ""),
        "goal_api_surface_contract_status": api_contract.get("status", ""),
        "goal_api_surface_ready": bool(api_contract.get("surface_ready") is True),
        "release_allowed": bool(release.get("release_allowed") is True),
        "restricted_release_allowed": bool(
            release.get("restricted_release_allowed") is True
            or release.get("release_allowed") is True
        ),
        "full_commercial_release_allowed": bool(
            release.get("full_commercial_release_allowed") is True
        ),
        "commercial_independent_product_ready": bool(release.get("commercial_independent_product_ready") is True),
        "cameo_architecture_validation_ready": bool(release.get("cameo_architecture_validation_ready") is True),
        "cleanup_objective_ready": bool(release.get("cleanup_objective_ready") is True),
        "release_blocker_count": _int(release.get("blocker_count")),
        "release_check_count": _int(release.get("check_count")),
        "bottleneck_count": _int(bottlenecks.get("bottleneck_count")),
        "primary_bottleneck_kind": bottlenecks.get("primary_bottleneck_kind", ""),
        "primary_bottleneck_phase": bottlenecks.get("primary_bottleneck_phase", ""),
        "primary_bottleneck_root_cause_category": bottlenecks.get(
            "primary_bottleneck_root_cause_category", ""
        ),
        "primary_bottleneck_locally_closable_without_operator_return": bool(
            bottlenecks.get("primary_bottleneck_locally_closable_without_operator_return") is True
        ),
        "primary_bottleneck_required_external_return": bottlenecks.get(
            "primary_bottleneck_required_external_return", ""
        ),
        "primary_bottleneck_post_return_acceptance_artifact": bottlenecks.get(
            "primary_bottleneck_post_return_acceptance_artifact", ""
        ),
        "completion_audit_release_blocker_bottleneck_count": _int(
            bottlenecks.get("completion_audit_release_blocker_bottleneck_count")
        ),
        "irreducible_external_return_bottleneck_count": _int(
            bottlenecks.get("irreducible_external_return_bottleneck_count")
        ),
        "expected_full_commercial_release_blocker_ids": list(FULL_COMMERCIAL_RELEASE_BLOCKER_IDS),
        "full_commercial_release_blocker_ids": release_full_commercial_blocker_ids,
        "full_commercial_release_blocker_count": len(release_full_commercial_blocker_ids),
        "missing_full_commercial_release_blocker_ids": missing_full_commercial_release_blocker_ids,
        "full_commercial_release_blocker_visibility_ready": full_commercial_release_blocker_visibility_ready,
        "primary_full_commercial_release_blocker_id": release.get(
            "primary_full_commercial_release_blocker_id", ""
        ),
        "primary_full_commercial_release_blocker": release.get(
            "primary_full_commercial_release_blocker", ""
        ),
        "full_commercial_release_next_required_step": release.get(
            "full_commercial_release_next_required_step", ""
        ),
        "master_gap_closure_rollup_status": release.get("master_gap_closure_rollup_status", ""),
        "master_gap_closure_rollup_recorded": bool(
            release.get("master_gap_closure_rollup_recorded") is True
        ),
        "master_gap_closure_rollup_all_gaps_closed": bool(
            release.get("master_gap_closure_rollup_all_gaps_closed") is True
        ),
        "master_gap_closure_rollup_claim_promotion_allowed": bool(
            release.get("master_gap_closure_rollup_claim_promotion_allowed") is True
        ),
        "master_gap_closure_rollup_open_gap_count": _int(
            release.get("master_gap_closure_rollup_open_gap_count")
        ),
        "master_gap_closure_rollup_open_gap_ids": _string_list(
            release.get("master_gap_closure_rollup_open_gap_ids")
        ),
        "master_gap_closure_rollup_closed_gap_count": _int(
            release.get("master_gap_closure_rollup_closed_gap_count")
        ),
        "master_gap_closure_rollup_closed_gap_ids": _string_list(
            release.get("master_gap_closure_rollup_closed_gap_ids")
        ),
        "master_gap_closure_rollup_release_blocker_row_count": _int(
            release.get("master_gap_closure_rollup_release_blocker_row_count")
        ),
        "master_gap_closure_rollup_current_primary_open_gap_id": release.get(
            "master_gap_closure_rollup_current_primary_open_gap_id", ""
        ),
        "master_gap_closure_rollup_science_claim_rollup_status": release.get(
            "master_gap_closure_rollup_science_claim_rollup_status", ""
        ),
        "master_gap_closure_rollup_science_claim_evidence": release.get(
            "master_gap_closure_rollup_science_claim_evidence", ""
        ),
        "master_gap_closure_rollup_science_claim_release_blocker": bool(
            release.get("master_gap_closure_rollup_science_claim_release_blocker") is True
        ),
        "science_claim_promotion_gap_closure_status": release.get(
            "science_claim_promotion_gap_closure_status", ""
        ),
        "science_claim_promotion_gap_closure_recorded": bool(
            release.get("science_claim_promotion_gap_closure_recorded") is True
        ),
        "science_claim_promotion_gap_closure_all_gaps_closed": bool(
            release.get("science_claim_promotion_gap_closure_all_gaps_closed") is True
        ),
        "science_claim_promotion_gap_closure_claim_promotion_allowed": bool(
            release.get("science_claim_promotion_gap_closure_claim_promotion_allowed") is True
        ),
        "science_claim_promotion_gap_closure_open_gap_count": _int(
            release.get("science_claim_promotion_gap_closure_open_gap_count")
        ),
        "science_claim_promotion_gap_closure_open_gap_ids": _string_list(
            release.get("science_claim_promotion_gap_closure_open_gap_ids")
        ),
        "science_claim_promotion_gap_closure_closed_gap_count": _int(
            release.get("science_claim_promotion_gap_closure_closed_gap_count")
        ),
        "science_claim_promotion_gap_closure_closed_gap_ids": _string_list(
            release.get("science_claim_promotion_gap_closure_closed_gap_ids")
        ),
        "science_claim_promotion_gap_closure_release_blocker_row_count": _int(
            release.get("science_claim_promotion_gap_closure_release_blocker_row_count")
        ),
        "science_claim_promotion_gap_closure_current_primary_open_gap_id": release.get(
            "science_claim_promotion_gap_closure_current_primary_open_gap_id", ""
        ),
        "science_claim_promotion_gap_closure_current_next_action": release.get(
            "science_claim_promotion_gap_closure_current_next_action", ""
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_area": release.get(
            "science_claim_promotion_gap_closure_primary_open_gap_area", ""
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status": release.get(
            "science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status", ""
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_evidence": release.get(
            "science_claim_promotion_gap_closure_primary_open_gap_evidence", ""
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_next_action": release.get(
            "science_claim_promotion_gap_closure_primary_open_gap_next_action", ""
        ),
        "science_claim_promotion_gap_closure_primary_open_gap_release_blocker": bool(
            release.get("science_claim_promotion_gap_closure_primary_open_gap_release_blocker") is True
        ),
        "science_claim_promotion_gap_closure_gpcr_claim_promotion_status": release.get(
            "science_claim_promotion_gap_closure_gpcr_claim_promotion_status", ""
        ),
        "science_claim_promotion_gap_closure_gpcr_evidence": release.get(
            "science_claim_promotion_gap_closure_gpcr_evidence", ""
        ),
        "science_claim_promotion_gap_closure_gpcr_release_blocker": bool(
            release.get("science_claim_promotion_gap_closure_gpcr_release_blocker") is True
        ),
        "science_claim_promotion_gap_closure_openmm_claim_promotion_status": release.get(
            "science_claim_promotion_gap_closure_openmm_claim_promotion_status", ""
        ),
        "science_claim_promotion_gap_closure_openmm_evidence": release.get(
            "science_claim_promotion_gap_closure_openmm_evidence", ""
        ),
        "science_claim_promotion_gap_closure_openmm_release_blocker": bool(
            release.get("science_claim_promotion_gap_closure_openmm_release_blocker") is True
        ),
        **_accuracy_parity_release_fields(release),
        **_api_runner_profile_receipt_release_fields(release),
        **_pose_sampling_release_fields(release),
        **_ledger_privacy_scan_release_fields(release),
        **_refine_tier_public_benchmark_release_fields(release),
        "product_goal_release_blocker_fail_count": _int(
            actions.get("product_goal_release_blocker_fail_count")
            or intake.get("product_goal_release_blocker_fail_count")
        ),
        "product_goal_release_blocker_requirement_ids": _string_list(
            actions.get("product_goal_release_blocker_requirement_ids")
            or intake.get("product_goal_release_blocker_requirement_ids")
        ),
        "product_goal_primary_release_blocker_requirement_id": actions.get(
            "product_goal_primary_release_blocker_requirement_id"
        )
        or intake.get("product_goal_primary_release_blocker_requirement_id", ""),
        "product_goal_primary_release_blocker_tier": actions.get("product_goal_primary_release_blocker_tier")
        or intake.get("product_goal_primary_release_blocker_tier", ""),
        "product_goal_primary_release_blocker": actions.get("product_goal_primary_release_blocker")
        or intake.get("product_goal_primary_release_blocker", ""),
        "product_goal_primary_release_blocker_next_command": actions.get(
            "product_goal_primary_release_blocker_next_command", ""
        ),
        "primary_release_blocker_action_id": actions.get("primary_release_blocker_action_id")
        or intake.get("primary_release_blocker_action_id", ""),
        "primary_release_blocker_action_status": actions.get("primary_release_blocker_action_status")
        or intake.get("primary_release_blocker_action_status", ""),
        "primary_release_blocker_action_required_input": actions.get(
            "primary_release_blocker_action_required_input"
        )
        or intake.get("primary_release_blocker_action_required_input", ""),
        "primary_release_blocker_action_artifact_path": actions.get(
            "primary_release_blocker_action_artifact_path"
        )
        or intake.get("primary_release_blocker_action_artifact_path", ""),
        "primary_release_blocker_action_recommended_action": actions.get(
            "primary_release_blocker_action_recommended_action"
        )
        or intake.get("primary_release_blocker_action_recommended_action", ""),
        "product_accuracy_parity_action_count": _int(
            actions.get("product_accuracy_parity_action_count")
        ),
        "product_accuracy_parity_ligand_ranking_action_id": (
            "product_accuracy_parity:repair_ligand_ranking_parity"
            if actions.get("product_accuracy_parity_ligand_ranking_action_present") is True
            else ""
        ),
        "product_accuracy_parity_ligand_ranking_action_present": bool(
            actions.get("product_accuracy_parity_ligand_ranking_action_present") is True
        ),
        "product_accuracy_parity_scorecard_status": actions.get(
            "product_accuracy_parity_scorecard_status", ""
        ),
        "product_accuracy_parity_ligand_ranking_action_status": actions.get(
            "product_accuracy_parity_ligand_ranking_status", ""
        ),
        "product_accuracy_parity_ligand_ranking_blocker_count": _int(
            actions.get("product_accuracy_parity_ligand_ranking_blocker_count")
        ),
        "product_accuracy_parity_ligand_ranking_blockers": _string_list(
            actions.get("product_accuracy_parity_ligand_ranking_blockers")
        ),
        "product_accuracy_parity_ligand_ranking_pr_auc": _float(
            actions.get("product_accuracy_parity_ligand_ranking_pr_auc")
        ),
        "product_accuracy_parity_ligand_ranking_pr_auc_ci_low": _float(
            actions.get("product_accuracy_parity_ligand_ranking_pr_auc_ci_low")
        ),
        "product_accuracy_parity_ligand_ranking_topk_hit_rate": _float(
            actions.get("product_accuracy_parity_ligand_ranking_topk_hit_rate")
        ),
        "product_accuracy_parity_ligand_ranking_next_required_step": actions.get(
            "product_accuracy_parity_ligand_ranking_next_required_step", ""
        ),
        "product_accuracy_parity_scorecard_json": actions.get(
            "product_accuracy_parity_scorecard_json", ""
        ),
        "product_goal_completion_audit_artifact_path": str(PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT),
        "production_ai_checkpoint_registry_promotion_required_gate_ids": _string_list(
            product_goal_completion.get("production_ai_checkpoint_registry_promotion_required_gate_ids")
        ),
        "production_ai_checkpoint_registry_promotion_missing_gate_ids": _string_list(
            product_goal_completion.get("production_ai_checkpoint_registry_promotion_missing_gate_ids")
        ),
        "production_ai_checkpoint_registry_promotion_missing_gate_count": _int(
            product_goal_completion.get("production_ai_checkpoint_registry_promotion_missing_gate_count")
        ),
        "production_ai_checkpoint_registry_promotion_upstream_acceptance_ready": bool(
            product_goal_completion.get(
                "production_ai_checkpoint_registry_promotion_upstream_acceptance_ready"
            )
            is True
        ),
        "production_ai_checkpoint_registry_promotion_currently_satisfied": bool(
            product_goal_completion.get(
                "production_ai_checkpoint_registry_promotion_currently_satisfied"
            )
            is True
        ),
        "production_ai_checkpoint_actionable_operator_completion_packet_ready": bool(
            product_goal_completion.get(
                "production_ai_checkpoint_actionable_operator_completion_packet_ready"
            )
            is True
        ),
        "production_ai_checkpoint_actionable_operator_completion_artifact_id": product_goal_completion.get(
            "production_ai_checkpoint_actionable_operator_completion_artifact_id", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns": _string_list(
            product_goal_completion.get(
                "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns"
            )
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands": _string_list(
            product_goal_completion.get(
                "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands"
            )
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count": _int(
            product_goal_completion.get(
                "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count"
            )
        ),
        "production_ai_checkpoint_actionable_operator_completion_completion_rule": product_goal_completion.get(
            "production_ai_checkpoint_actionable_operator_completion_completion_rule", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_next_action": product_goal_completion.get(
            "production_ai_checkpoint_actionable_operator_completion_next_action", ""
        ),
        "commercial_readiness_handoff_bundle_status": handoff.get("status", ""),
        "commercial_readiness_handoff_bundle_ready": bool(handoff.get("handoff_bundle_ready") is True),
        "commercial_readiness_handoff_bundle_artifact_path": str(
            PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT
        ),
        "commercial_readiness_handoff_bundle_artifact_reference_count": _int(
            handoff.get("artifact_reference_count")
        ),
        "commercial_readiness_handoff_bundle_local_missing_artifact_reference_count": _int(
            handoff.get("local_missing_artifact_reference_count")
        ),
        **_production_ai_registry_promotion_receipt_fields(handoff),
        **_cameo_official_result_fetch_preflight_fields(cameo_fetch, intake_rows),
        **_evidence_receipt_fields(
            prefix="product_scope_breadth_evidence_receipt",
            receipt=scope_receipt,
            artifact_path=PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_ARTIFACT,
            ready_key="full_scope_evidence_receipt_ready",
            first_blocked_id_source_key="first_blocked_scope_blocker_id",
            first_blocked_id_status_key="first_blocked_scope_blocker_id",
            required_blocker_count_key="required_scope_blocker_count",
            required_blockers_key="required_scope_blockers",
        ),
        **_evidence_receipt_fields(
            prefix="engine_refinement_claim_evidence_receipt",
            receipt=engine_receipt,
            artifact_path=ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_ARTIFACT,
            ready_key="claim_promotion_evidence_receipt_ready",
            first_blocked_id_source_key="first_blocked_blocker_id",
            first_blocked_id_status_key="first_blocked_blocker_id",
            required_blocker_count_key="required_blocker_count",
            required_blockers_key="required_blockers",
        ),
        "full_commercial_blocker_evidence_matrix_status": full_commercial_matrix.get("status", ""),
        "full_commercial_blocker_evidence_matrix_ready": bool(
            full_commercial_matrix.get("full_commercial_blocker_evidence_matrix_ready") is True
        ),
        "full_commercial_blocker_evidence_matrix_artifact_path": str(
            PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT
        ),
        "full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready": bool(
            full_commercial_matrix.get("release_blocker_visibility_ready") is True
        ),
        "full_commercial_blocker_evidence_matrix_row_count": _int(
            full_commercial_matrix.get("matrix_row_count")
        ),
        "full_commercial_blocker_evidence_matrix_blocked_row_count": _int(
            full_commercial_matrix.get("blocked_matrix_row_count")
        ),
        "full_commercial_blocker_evidence_matrix_approval_token_count": _int(
            full_commercial_matrix.get("approval_token_count")
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id": full_commercial_matrix.get(
            "first_blocked_release_blocker_id", ""
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id": full_commercial_matrix.get(
            "first_blocked_evidence_row_id", ""
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_evidence_artifact": full_commercial_matrix.get(
            "first_blocked_evidence_artifact", ""
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_expected_evidence_status": (
            full_commercial_matrix.get("first_blocked_expected_evidence_status", "")
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_observed_evidence_status": (
            full_commercial_matrix.get("first_blocked_observed_evidence_status", "")
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_row_blockers": full_commercial_matrix.get(
            "first_blocked_row_blockers", ""
        ),
        "full_commercial_blocker_evidence_matrix_first_blocked_acceptance_artifact": full_commercial_matrix.get(
            "first_blocked_acceptance_artifact", ""
        ),
        "full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker": (
            full_commercial_matrix.get("scope_receipt_most_common_row_blocker", "")
        ),
        "full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker": (
            full_commercial_matrix.get("engine_receipt_most_common_row_blocker", "")
        ),
        "product_quality_gate_verification_status": release.get(
            "product_quality_gate_verification_status", ""
        ),
        "product_quality_gate_verification_recorded": bool(
            release.get("product_quality_gate_verification_recorded") is True
        ),
        "product_quality_gate_verification_ready": bool(
            release.get("product_quality_gate_verification_ready") is True
        ),
        "product_quality_gate_verification_source_contract_status": release.get(
            "product_quality_gate_verification_source_contract_status", ""
        ),
        "product_quality_gate_verification_check_count": _int(
            release.get("product_quality_gate_verification_check_count")
        ),
        "product_quality_gate_verification_pass_count": _int(
            release.get("product_quality_gate_verification_pass_count")
        ),
        "product_quality_gate_verification_blocker_count": _int(
            release.get("product_quality_gate_verification_blocker_count")
        ),
        "product_quality_gate_verification_execution_enabled": bool(
            release.get("product_quality_gate_verification_execution_enabled") is True
        ),
        "product_quality_gate_verification_external_state_mutated": bool(
            release.get("product_quality_gate_verification_external_state_mutated") is True
        ),
        "official_results_required_bottleneck_count": _int(
            bottlenecks.get("official_results_required_bottleneck_count")
        ),
        "work_item_count": _int(burndown.get("work_item_count")),
        "operator_action_count": _int(actions.get("action_count") or release.get("operator_action_count")),
        "operator_approval_required_count": _int(actions.get("approval_required_count") or release.get("operator_approval_required_count")),
        "operator_input_required_count": _int(intake.get("operator_input_required_count")),
        "primary_action_id": primary_action_source.get("primary_action_id") or actions.get("primary_action_id", ""),
        "primary_action_status": primary_action_source.get("primary_action_status") or actions.get("primary_action_status", ""),
        "primary_action_required_input": primary_action_source.get("primary_action_required_input")
        or actions.get("primary_action_required_input", ""),
        "primary_action_command": primary_action_source.get("primary_action_command") or actions.get("primary_action_command", ""),
        "primary_action_recommended_action": primary_action_source.get("primary_action_recommended_action")
        or actions.get("primary_action_recommended_action", ""),
        "primary_action_artifact_path": primary_action_source.get("primary_action_artifact_path")
        or actions.get("primary_action_artifact_path", ""),
        "operator_intake_kit_release_burndown_linked_entry_count": _int(
            intake.get("release_burndown_linked_entry_count")
        ),
        "operator_intake_kit_full_commercial_evidence_receipt_entry_count": _int(
            intake.get("full_commercial_evidence_receipt_entry_count")
        ),
        "operator_intake_kit_full_commercial_evidence_receipt_operator_input_required_count": _int(
            intake.get("full_commercial_evidence_receipt_operator_input_required_count")
        ),
        "operator_intake_kit_full_commercial_evidence_receipt_current_action_required_count": _int(
            intake.get("full_commercial_evidence_receipt_current_action_required_count")
        ),
        "operator_intake_kit_full_commercial_evidence_receipt_template_required_count": _int(
            intake.get("full_commercial_evidence_receipt_template_required_count")
        ),
        "operator_intake_kit_full_commercial_evidence_receipt_template_present_count": _int(
            intake.get("full_commercial_evidence_receipt_template_present_count")
        ),
        "operator_intake_kit_full_commercial_evidence_receipt_approval_token_count": _int(
            intake.get("full_commercial_evidence_receipt_approval_token_count")
        ),
        "operator_intake_kit_full_commercial_evidence_receipt_entry_ids": _string_list(
            intake.get("full_commercial_evidence_receipt_entry_ids")
        ),
        "operator_intake_kit_full_commercial_evidence_receipt_source_gate_statuses": intake.get(
            "full_commercial_evidence_receipt_source_gate_statuses", ""
        ),
        "operator_intake_kit_full_commercial_evidence_receipt_required_inputs": intake.get(
            "full_commercial_evidence_receipt_required_inputs", ""
        ),
        "operator_intake_kit_full_commercial_evidence_receipt_approval_tokens": intake.get(
            "full_commercial_evidence_receipt_approval_tokens", ""
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_status": intake.get(
            "product_scope_breadth_evidence_priority_status", ""
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_packet_ready": bool(
            intake.get("product_scope_breadth_evidence_priority_packet_ready") is True
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_open_item_count": _int(
            intake.get("product_scope_breadth_evidence_priority_open_item_count")
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_scientific_evidence_request_count": _int(
            intake.get("product_scope_breadth_evidence_priority_scientific_evidence_request_count")
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_top_item_id": intake.get(
            "product_scope_breadth_evidence_priority_top_item_id", ""
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_top_domain": intake.get(
            "product_scope_breadth_evidence_priority_top_domain", ""
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_top_bucket": intake.get(
            "product_scope_breadth_evidence_priority_top_bucket", ""
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_top_required_evidence_type": intake.get(
            "product_scope_breadth_evidence_priority_top_required_evidence_type", ""
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_top_review_template_artifact": intake.get(
            "product_scope_breadth_evidence_priority_top_review_template_artifact", ""
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_top_apply_gate_artifact": intake.get(
            "product_scope_breadth_evidence_priority_top_apply_gate_artifact", ""
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_top_next_step": intake.get(
            "product_scope_breadth_evidence_priority_top_next_step", ""
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_scope_promotion_allowed": bool(
            intake.get("product_scope_breadth_evidence_priority_scope_promotion_allowed") is True
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_authoritative_apply_allowed": bool(
            intake.get("product_scope_breadth_evidence_priority_authoritative_apply_allowed") is True
        ),
        "operator_intake_kit_product_scope_breadth_evidence_priority_external_state_mutated": bool(
            intake.get("product_scope_breadth_evidence_priority_external_state_mutated") is True
        ),
        "bottleneck_briefing_full_commercial_evidence_receipt_entry_count": _int(
            bottlenecks.get("full_commercial_evidence_receipt_entry_count")
        ),
        "bottleneck_briefing_full_commercial_evidence_receipt_operator_input_required_count": _int(
            bottlenecks.get("full_commercial_evidence_receipt_operator_input_required_count")
        ),
        "bottleneck_briefing_full_commercial_evidence_receipt_current_action_required_count": _int(
            bottlenecks.get("full_commercial_evidence_receipt_current_action_required_count")
        ),
        "bottleneck_briefing_full_commercial_evidence_receipt_template_required_count": _int(
            bottlenecks.get("full_commercial_evidence_receipt_template_required_count")
        ),
        "bottleneck_briefing_full_commercial_evidence_receipt_template_present_count": _int(
            bottlenecks.get("full_commercial_evidence_receipt_template_present_count")
        ),
        "bottleneck_briefing_full_commercial_evidence_receipt_approval_token_count": _int(
            bottlenecks.get("full_commercial_evidence_receipt_approval_token_count")
        ),
        "bottleneck_briefing_full_commercial_evidence_receipt_entry_ids": _string_list(
            bottlenecks.get("full_commercial_evidence_receipt_entry_ids")
        ),
        "bottleneck_briefing_full_commercial_evidence_receipt_source_gate_statuses": bottlenecks.get(
            "full_commercial_evidence_receipt_source_gate_statuses", ""
        ),
        "bottleneck_briefing_full_commercial_evidence_receipt_required_inputs": bottlenecks.get(
            "full_commercial_evidence_receipt_required_inputs", ""
        ),
        "bottleneck_briefing_full_commercial_evidence_receipt_approval_tokens": bottlenecks.get(
            "full_commercial_evidence_receipt_approval_tokens", ""
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_status": bottlenecks.get(
            "product_scope_breadth_evidence_priority_status", ""
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_packet_ready": bool(
            bottlenecks.get("product_scope_breadth_evidence_priority_packet_ready") is True
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_open_item_count": _int(
            bottlenecks.get("product_scope_breadth_evidence_priority_open_item_count")
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_scientific_evidence_request_count": _int(
            bottlenecks.get("product_scope_breadth_evidence_priority_scientific_evidence_request_count")
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_top_item_id": bottlenecks.get(
            "product_scope_breadth_evidence_priority_top_item_id", ""
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_top_domain": bottlenecks.get(
            "product_scope_breadth_evidence_priority_top_domain", ""
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_top_bucket": bottlenecks.get(
            "product_scope_breadth_evidence_priority_top_bucket", ""
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_top_required_evidence_type": bottlenecks.get(
            "product_scope_breadth_evidence_priority_top_required_evidence_type", ""
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_top_review_template_artifact": bottlenecks.get(
            "product_scope_breadth_evidence_priority_top_review_template_artifact", ""
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_top_apply_gate_artifact": bottlenecks.get(
            "product_scope_breadth_evidence_priority_top_apply_gate_artifact", ""
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_top_next_step": bottlenecks.get(
            "product_scope_breadth_evidence_priority_top_next_step", ""
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_scope_promotion_allowed": bool(
            bottlenecks.get("product_scope_breadth_evidence_priority_scope_promotion_allowed") is True
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_authoritative_apply_allowed": bool(
            bottlenecks.get("product_scope_breadth_evidence_priority_authoritative_apply_allowed") is True
        ),
        "bottleneck_briefing_product_scope_breadth_evidence_priority_external_state_mutated": bool(
            bottlenecks.get("product_scope_breadth_evidence_priority_external_state_mutated") is True
        ),
        "operator_template_missing_count": _int(intake.get("template_missing_count")),
        "all_required_templates_present": bool(intake.get("all_required_templates_present") is True),
        "official_results_required_count": _int(intake.get("official_results_required_count") or burndown.get("official_results_required_item_count")),
        "policy_decision_required_count": _int(intake.get("policy_decision_required_count") or burndown.get("policy_decision_required_item_count")),
        "approval_token_count": _int(
            bottlenecks.get("approval_token_count")
            or intake.get("approval_token_count")
            or burndown.get("approval_token_count")
        ),
        "approval_tokens": _string_list(
            bottlenecks.get("approval_tokens_required")
            or intake.get("approval_tokens")
            or burndown.get("approval_tokens_required")
        ),
        "approval_reclaim_size_gb": _float(actions.get("approval_reclaim_size_gb") or release.get("approval_reclaim_size_gb")),
        "protected_cleanup_payload_size_gb": _float(
            release.get("protected_cleanup_payload_size_gb")
            or actions.get("protected_cleanup_payload_size_gb")
            or readiness.get("cleanup_cli_protected_payload_size_gb")
        ),
        "product_cli_status_set_status": release.get("product_cli_status_set_status") or readiness.get("product_cli_status_set_status", ""),
        "product_cli_approval_token_count": _int(release.get("product_cli_approval_token_count") or readiness.get("product_cli_approval_token_count")),
        "product_cli_operations_blocked_stage_count": _int(
            release.get("product_cli_operations_blocked_stage_count")
            or readiness.get("product_cli_operations_blocked_stage_count")
        ),
        "product_operational_quality_ready": bool(
            release.get("product_operational_quality_ready") is True
            or release.get("product_cli_operational_quality_ready") is True
            or readiness.get("product_operational_quality_ready") is True
            or readiness.get("product_cli_operational_quality_ready") is True
            or actions.get("product_cli_operational_quality_ready") is True
        ),
        "product_operational_quality_status": release.get("product_operational_quality_status")
        or release.get("product_release_operations_source_operational_quality_status")
        or readiness.get("product_operational_quality_status")
        or actions.get("product_release_operations_source_operational_quality_status", ""),
        "product_operational_quality_blocker_count": _int(
            release.get("product_operational_quality_blocker_count")
            or readiness.get("product_operational_quality_blocker_count")
            or actions.get("product_release_operations_operational_quality_blocker_count")
        ),
        "product_operational_quality_artifact": release.get("product_operational_quality_artifact")
        or readiness.get("product_operational_quality_artifact")
        or actions.get("product_release_operations_operational_quality_artifact", ""),
        "product_cli_authorized_for_execution": bool(
            release.get("product_cli_authorized_for_execution") is True
            or readiness.get("product_cli_authorized_for_execution") is True
        ),
        "product_cli_delivery_ready_claim_allowed": bool(
            release.get("product_cli_delivery_ready_claim_allowed") is True
            or readiness.get("product_cli_delivery_ready_claim_allowed") is True
        ),
        "cameo_cli_status_set_status": release.get("cameo_cli_status_set_status") or readiness.get("cameo_cli_status_set_status", ""),
        "cameo_cli_approval_token_count": _int(release.get("cameo_cli_approval_token_count") or readiness.get("cameo_cli_approval_token_count")),
        "cameo_cli_official_result_required": bool(
            release.get("cameo_cli_official_result_required") is True
            or readiness.get("cameo_cli_official_result_required") is True
        ),
        "cameo_cli_receiver_smoke_status": release.get("cameo_cli_receiver_smoke_status") or readiness.get("cameo_cli_receiver_smoke_status", ""),
        "cameo_evidence_integrity_ready": bool(
            release.get("cameo_evidence_integrity_ready") is True
            or release.get("cameo_cli_evidence_integrity_ready") is True
            or readiness.get("cameo_evidence_integrity_ready") is True
            or readiness.get("cameo_cli_evidence_integrity_ready") is True
            or actions.get("cameo_cli_evidence_integrity_ready") is True
        ),
        "cameo_evidence_integrity_status": release.get("cameo_evidence_integrity_status")
        or release.get("cameo_validation_operations_evidence_integrity_status")
        or readiness.get("cameo_evidence_integrity_status")
        or actions.get("cameo_validation_operations_evidence_integrity_status", ""),
        "cameo_evidence_integrity_blocker_count": _int(
            release.get("cameo_evidence_integrity_blocker_count")
            or readiness.get("cameo_evidence_integrity_blocker_count")
            or actions.get("cameo_validation_operations_evidence_integrity_blocker_count")
        ),
        "cameo_evidence_integrity_artifact": release.get("cameo_evidence_integrity_artifact")
        or readiness.get("cameo_evidence_integrity_artifact")
        or actions.get("cameo_validation_operations_evidence_integrity_artifact", ""),
        "cameo_official_results_pending_honest": bool(
            release.get("cameo_official_results_pending_honest") is True
            or release.get("cameo_cli_official_results_pending_honest") is True
            or readiness.get("cameo_official_results_pending_honest") is True
            or readiness.get("cameo_cli_official_results_pending_honest") is True
            or actions.get("cameo_cli_official_results_pending_honest") is True
        ),
        "cameo_no_local_native_accuracy_substitution": bool(
            release.get("cameo_no_local_native_accuracy_substitution") is True
            or release.get("cameo_cli_no_local_native_accuracy_substitution") is True
            or readiness.get("cameo_no_local_native_accuracy_substitution") is True
            or readiness.get("cameo_cli_no_local_native_accuracy_substitution") is True
            or actions.get("cameo_cli_no_local_native_accuracy_substitution") is True
        ),
        "cleanup_cli_status_set_status": release.get("cleanup_cli_status_set_status") or readiness.get("cleanup_cli_status_set_status", ""),
        "cleanup_cli_approval_token_count": _int(release.get("cleanup_cli_approval_token_count") or readiness.get("cleanup_cli_approval_token_count")),
        "cleanup_cli_approval_reclaim_size_gb": _float(
            release.get("cleanup_cli_approval_reclaim_size_gb")
            or readiness.get("cleanup_cli_approval_reclaim_size_gb")
        ),
        "cleanup_cli_postcheck_contract_ready": bool(
            release.get("cleanup_cli_postcheck_contract_ready") is True
            or readiness.get("cleanup_cli_postcheck_contract_ready") is True
        ),
        "cleanup_cli_protected_payload_size_gb": _float(
            release.get("cleanup_cli_protected_payload_size_gb")
            or readiness.get("cleanup_cli_protected_payload_size_gb")
        ),
        "cleanup_cli_protected_policy_change_required_count": _int(
            release.get("cleanup_cli_protected_policy_change_required_count")
            or readiness.get("cleanup_cli_protected_policy_change_required_count")
        ),
        **_mutation_flags(),
        "claim_boundary": CLAIM_BOUNDARY,
    }


@router.get("/readiness")
async def get_goal_readiness() -> dict[str, Any]:
    packet = _read_json_object(GOAL_READINESS_ROLLUP_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return {
            "status": "missing_goal_readiness_rollup",
            "artifact_path": str(GOAL_READINESS_ROLLUP_ARTIFACT),
            "release_allowed": False,
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        "artifact_path": str(GOAL_READINESS_ROLLUP_ARTIFACT),
        "rows": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }


@router.get("/actions")
async def get_goal_actions() -> dict[str, Any]:
    packet = _read_json_object(GOAL_OPERATOR_ACTION_BOARD_ARTIFACT)
    intake_packet = _read_json_object(GOAL_OPERATOR_INTAKE_KIT_MANIFEST)
    summary = _summary(packet)
    intake = _summary(intake_packet)
    if not summary:
        return {
            "status": "missing_goal_operator_action_board",
            "artifact_path": str(GOAL_OPERATOR_ACTION_BOARD_ARTIFACT),
            "intake_kit_manifest_path": str(GOAL_OPERATOR_INTAKE_KIT_MANIFEST),
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        "artifact_path": str(GOAL_OPERATOR_ACTION_BOARD_ARTIFACT),
        "intake_kit_manifest_path": str(GOAL_OPERATOR_INTAKE_KIT_MANIFEST),
        "operator_intake_kit_status": intake.get("status", ""),
        "operator_intake_kit_template_missing_count": _int(intake.get("template_missing_count")),
        "operator_intake_kit_approval_token_count": _int(intake.get("approval_token_count")),
        "operator_intake_kit_approval_tokens": _string_list(intake.get("approval_tokens")),
        "actions": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }


@router.get("/operator-intake-kit")
async def get_goal_operator_intake_kit() -> dict[str, Any]:
    packet = _read_json_object(GOAL_OPERATOR_INTAKE_KIT_MANIFEST)
    summary = _summary(packet)
    if not summary:
        return {
            "status": "missing_goal_operator_intake_kit",
            "artifact_path": str(GOAL_OPERATOR_INTAKE_KIT_MANIFEST),
            "operator_input_required_count": 0,
            "release_burndown_linked_entry_count": 0,
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        "artifact_path": str(GOAL_OPERATOR_INTAKE_KIT_MANIFEST),
        "entries": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }


@router.get("/release-decision")
async def get_goal_release_decision() -> dict[str, Any]:
    packet = _read_json_object(GOAL_RELEASE_DECISION_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return {
            "status": "missing_goal_release_decision_gate",
            "artifact_path": str(GOAL_RELEASE_DECISION_ARTIFACT),
            "release_allowed": False,
            **_accuracy_parity_release_fields({}),
            **_api_runner_profile_receipt_release_fields({}),
            **_pose_sampling_release_fields({}),
            **_ledger_privacy_scan_release_fields({}),
            **_refine_tier_public_benchmark_release_fields({}),
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        **_accuracy_parity_release_fields(summary),
        **_api_runner_profile_receipt_release_fields(summary),
        **_pose_sampling_release_fields(summary),
        **_ledger_privacy_scan_release_fields(summary),
        **_refine_tier_public_benchmark_release_fields(summary),
        "artifact_path": str(GOAL_RELEASE_DECISION_ARTIFACT),
        "checks": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }


@router.get("/burndown")
async def get_goal_burndown() -> dict[str, Any]:
    packet = _read_json_object(GOAL_RELEASE_BURNDOWN_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return {
            "status": "missing_goal_release_burndown_work_order",
            "artifact_path": str(GOAL_RELEASE_BURNDOWN_ARTIFACT),
            "release_allowed": False,
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        "artifact_path": str(GOAL_RELEASE_BURNDOWN_ARTIFACT),
        "work_items": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }


@router.get("/bottlenecks")
async def get_goal_bottlenecks() -> dict[str, Any]:
    packet = _read_json_object(GOAL_BOTTLENECK_BRIEFING_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return {
            "status": "missing_goal_bottleneck_briefing",
            "artifact_path": str(GOAL_BOTTLENECK_BRIEFING_ARTIFACT),
            "bottleneck_count": 0,
            "release_allowed": False,
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        "artifact_path": str(GOAL_BOTTLENECK_BRIEFING_ARTIFACT),
        "bottlenecks": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }


@router.get("/api-contract")
async def get_goal_api_contract() -> dict[str, Any]:
    packet = _read_json_object(GOAL_API_SURFACE_CONTRACT_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return {
            "status": "missing_goal_api_surface_contract",
            "artifact_path": str(GOAL_API_SURFACE_CONTRACT_ARTIFACT),
            "surface_ready": False,
            "check_count": 0,
            "blocker_count": 1,
            **_mutation_flags(),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        **summary,
        "artifact_path": str(GOAL_API_SURFACE_CONTRACT_ARTIFACT),
        "checks": _rows(packet),
        "blockers": _blockers(packet),
        **_mutation_flags(),
    }
