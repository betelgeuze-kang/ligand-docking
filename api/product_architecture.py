from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-architecture"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ARCHITECTURE_ARTIFACT = ROOT / "runs" / "product_architecture_contract_current.json"
ARCHITECTURE_VALIDATION_REPORT_ARTIFACT = ROOT / "runs" / "architecture_validation_package_report_current.json"
COMPETITION_EXTERNAL_OPERATOR_TRACK_ARTIFACT = ROOT / "runs" / "competition_external_operator_track_current.json"


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
    return summary if isinstance(summary, dict) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


@router.get("/architecture")
async def get_product_architecture() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_ARCHITECTURE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    approval_required = packet.get("approval_required") if isinstance(packet.get("approval_required"), list) else []
    if not summary:
        return {
            "status": "missing_product_architecture_contract",
            "artifact_path": str(PRODUCT_ARCHITECTURE_ARTIFACT),
            "local_architecture_surface_ready": False,
            "architecture_release_ready": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "cameo_submission_executed": False,
            "casp_submission_executed": False,
            "cleanup_executed": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product architecture endpoint only; the local product architecture contract is missing or invalid. "
                "It does not run docking, submit predictions, delete files, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status")
        or (
            "product_scope_breadth_closure_checklist_ready"
            if summary.get("closure_checklist_ready") is True
            else "blocked_product_scope_breadth_closure_checklist"
        ),
        "artifact_path": str(PRODUCT_ARCHITECTURE_ARTIFACT),
        "local_architecture_surface_ready": bool(summary.get("local_architecture_surface_ready") is True),
        "architecture_release_ready": bool(summary.get("architecture_release_ready") is True),
        "lane_count": int(summary.get("lane_count") or 0),
        "ready_lane_count": int(summary.get("ready_lane_count") or 0),
        "blocked_lane_count": int(summary.get("blocked_lane_count") or 0),
        "approval_required_lane_count": int(summary.get("approval_required_lane_count") or 0),
        "structure_analysis_product_surface_ready": bool(summary.get("structure_analysis_product_surface_ready") is True),
        "ligand_docking_execution_contract_ready": bool(summary.get("ligand_docking_execution_contract_ready") is True),
        "commercial_independence_ready": bool(summary.get("commercial_independence_ready") is True),
        "product_service_boundary_ready": bool(summary.get("product_service_boundary_ready") is True),
        "product_api_contract_ready": bool(summary.get("product_api_contract_ready") is True),
        "cameo_local_surface_ready": bool(summary.get("cameo_local_surface_ready") is True),
        "cameo_service_boundary_ready": bool(summary.get("cameo_service_boundary_ready") is True),
        "cameo_service_boundary_status": summary.get("cameo_service_boundary_status", ""),
        "cameo_service_boundary_api_route_count": int(summary.get("cameo_service_boundary_api_route_count") or 0),
        "cameo_service_boundary_cli_command_count": int(summary.get("cameo_service_boundary_cli_command_count") or 0),
        "cameo_api_contract_ready": bool(summary.get("cameo_api_contract_ready") is True),
        "cameo_api_contract_status": summary.get("cameo_api_contract_status", ""),
        "cameo_api_contract_expected_route_count": int(summary.get("cameo_api_contract_expected_route_count") or 0),
        "cameo_api_contract_missing_route_count": int(summary.get("cameo_api_contract_missing_route_count") or 0),
        "cameo_api_contract_status_response_missing_key_count": int(
            summary.get("cameo_api_contract_status_response_missing_key_count") or 0
        ),
        "cameo_architecture_validation_ready": bool(summary.get("cameo_architecture_validation_ready") is True),
        "cleanup_control_surface_ready": bool(summary.get("cleanup_control_surface_ready") is True),
        "cleanup_postcheck_contract_ready": bool(summary.get("cleanup_postcheck_contract_ready") is True),
        "cleanup_postcheck_row_count": int(summary.get("cleanup_postcheck_row_count") or 0),
        "cleanup_postcheck_blocked_row_count": int(summary.get("cleanup_postcheck_blocked_row_count") or 0),
        "cleanup_postcheck_global_refresh_command_count": int(
            summary.get("cleanup_postcheck_global_refresh_command_count") or 0
        ),
        "ligand_heavy_cleanup_preflight_ready": bool(summary.get("ligand_heavy_cleanup_preflight_ready") is True),
        "casp17_transition_surface_ready": bool(summary.get("casp17_transition_surface_ready") is True),
        "cleanup_execution_approved": bool(summary.get("cleanup_execution_approved") is True),
        "cleanup_reclaim_size_gb": float(summary.get("cleanup_reclaim_size_gb") or 0.0),
        "release_allowed": bool(summary.get("release_allowed") is True),
        "lanes": rows,
        "blockers": blockers,
        "approval_required": approval_required,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "cameo_submission_executed": False,
        "casp_submission_executed": False,
        "cleanup_executed": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/architecture-validation")
async def get_product_architecture_validation() -> dict[str, Any]:
    packet = _read_json_object(ARCHITECTURE_VALIDATION_REPORT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    warnings = packet.get("overclaim_warnings") if isinstance(packet.get("overclaim_warnings"), list) else []
    external = _summary(_read_json_object(COMPETITION_EXTERNAL_OPERATOR_TRACK_ARTIFACT))
    if not summary:
        return {
            "status": "missing_architecture_validation_package_report",
            "artifact_path": str(ARCHITECTURE_VALIDATION_REPORT_ARTIFACT),
            "architecture_validation_all_packages_complete": False,
            "package_a_complete": False,
            "package_b_complete": False,
            "package_c_complete": False,
            "evidence_depth_tier": "accounting_only",
            "overclaim_warning_count": 0,
            "competition_benchmark_rollup_status": "",
            "competition_benchmark_cameo_official_intake_gate_status": "",
            "competition_benchmark_cameo_official_intake_gate_ready": False,
            "competition_benchmark_cameo_official_result_intake_ready": False,
            "competition_benchmark_cameo_official_intake_gate_artifact_path": "",
            "competition_benchmark_cameo_official_operator_intake_csv": "",
            "competition_benchmark_cameo_official_operator_template_csv": "",
            "competition_benchmark_cameo_official_result_row_count": 0,
            "competition_benchmark_cameo_official_accepted_result_count": 0,
            "competition_benchmark_cameo_official_rejected_result_count": 0,
            "competition_benchmark_cameo_official_model1_result_ready": False,
            "competition_benchmark_cameo_official_blocker_count": 0,
            "competition_benchmark_cameo_official_blocker_codes": [],
            "competition_benchmark_cameo_official_operator_action_required_count": 0,
            "competition_benchmark_cameo_official_operator_action_required_row_count": 0,
            "competition_benchmark_cameo_official_primary_blocker_code": "",
            "competition_benchmark_cameo_official_primary_required_action": "",
            "competition_benchmark_cameo_official_required_column_count": 0,
            "competition_benchmark_cameo_official_missing_required_column_count": 0,
            "competition_benchmark_cameo_official_missing_required_columns": [],
            "competition_benchmark_cameo_official_allowed_result_source_kinds": [],
            "competition_benchmark_cameo_official_source_provenance_ready_row_count": 0,
            "competition_benchmark_cameo_official_metric_ready_row_count": 0,
            "competition_benchmark_cameo_official_local_native_accuracy_blocker_count": 0,
            "competition_benchmark_cameo_official_native_local_accuracy_used": False,
            "competition_benchmark_cameo_official_external_state_mutated": False,
            "competition_benchmark_casp16_ligand_source_manifest_status": "",
            "competition_benchmark_casp16_ligand_source_manifest_ready": False,
            "competition_benchmark_casp16_ligand_materialization_ready": False,
            "competition_benchmark_casp16_ligand_scorecard_ready": False,
            "competition_benchmark_casp16_ligand_competition_credibility_ready": False,
            "competition_benchmark_casp16_ligand_raw_data_committed": False,
            "competition_benchmark_casp16_ligand_raw_data_git_tracked_file_count": 0,
            "competition_benchmark_casp16_ligand_pose_target_count": 0,
            "competition_benchmark_casp16_ligand_affinity_target_count": 0,
            "competition_benchmark_casp16_ligand_next_action": "",
            "competition_benchmark_bm5_capri_complex_source_manifest_status": "",
            "competition_benchmark_bm5_complex_benchmark_ready": False,
            "competition_benchmark_capri_score_set_ready": False,
            "competition_benchmark_bm5_capri_complex_competition_credibility_ready": False,
            "competition_benchmark_bm5_capri_complex_raw_data_committed": False,
            "competition_benchmark_bm5_capri_complex_raw_data_git_tracked_file_count": 0,
            "competition_benchmark_bm5_capri_complex_primary_metric": "",
            "competition_benchmark_bm5_capri_complex_next_action": "",
            "competition_benchmark_competition_credibility_extension_ready": False,
            "competition_benchmark_competition_credibility_extension_blocker_count": 0,
            "competition_benchmark_competition_credibility_extension_blockers": [],
            "competition_benchmark_competition_credibility_extension_primary_blocker": "",
            "competition_benchmark_competition_credibility_extension_next_actions": [],
            "competition_benchmark_competition_credibility_extension_primary_next_action": "",
            "competition_benchmark_custody_work_order_status": "",
            "competition_benchmark_custody_work_order_ready": False,
            "competition_benchmark_custody_work_order_action_count": 0,
            "competition_benchmark_custody_work_order_raw_data_blocked_row_count": 0,
            "competition_benchmark_custody_work_order_missing_receipt_row_count": 0,
            "competition_benchmark_custody_work_order_primary_work_order_id": "",
            "competition_benchmark_custody_work_order_primary_required_action": "",
            "competition_benchmark_custody_work_order_primary_verification_command": "",
            "competition_benchmark_package_b_required_for_ligand_commercial_claims": False,
            "competition_benchmark_package_b_public_benchmark_contract_status": "",
            "competition_benchmark_package_b_public_benchmark_validation_ready": False,
            "competition_benchmark_package_b_ligand_public_benchmark_foundation_ready": False,
            "competition_benchmark_package_b_ligand_suite_ids": [],
            "competition_benchmark_package_b_refine_tier_public_benchmark_status": "",
            "competition_benchmark_package_b_claim_grade_public_benchmark_ready": False,
            "competition_benchmark_package_b_claim_grade_blocker_count": 0,
            "competition_benchmark_package_b_claim_grade_blockers": [],
            "competition_benchmark_package_b_refine_tier_work_order_apply_status": "",
            "competition_benchmark_package_b_refine_tier_work_order_apply_ready": False,
            "competition_benchmark_competition_evidence_role": "",
            "competition_benchmark_competition_ligand_commercial_claim_allowed": False,
            "competition_benchmark_competition_ligand_claim_package_b_dependency_ready": False,
            "competition_benchmark_competition_ligand_claim_blocker_count": 0,
            "competition_benchmark_competition_ligand_claim_blockers": [],
            "competition_benchmark_package_b_bridge_next_action": "",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product architecture-validation endpoint only; the local architecture validation report is missing. "
                "It does not run benchmarks, promote claims, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(ARCHITECTURE_VALIDATION_REPORT_ARTIFACT),
        "architecture_validation_all_packages_complete": bool(
            summary.get("status") == "architecture_validation_all_packages_complete"
        ),
        "package_a_complete": bool(summary.get("package_a_complete") is True),
        "package_b_complete": bool(summary.get("package_b_complete") is True),
        "package_c_complete": bool(summary.get("package_c_complete") is True),
        "open_required_test_ids": list(summary.get("open_required_test_ids") or []),
        "overclaim_open_test_ids": list(summary.get("overclaim_open_test_ids") or []),
        "evidence_depth_tier": summary.get("evidence_depth_tier", "accounting_only"),
        "overclaim_warning_count": int(summary.get("overclaim_warning_count") or 0),
        "overclaim_hard_warning_count": int(summary.get("overclaim_hard_warning_count") or 0),
        "competition_external_operator_track_status": external.get("status", ""),
        "competition_external_blocked_track_count": int(external.get("blocked_track_count") or 0),
        "competition_benchmark_rollup_status": summary.get(
            "competition_benchmark_rollup_status",
            "",
        ),
        "competition_benchmark_cameo_official_intake_gate_status": summary.get(
            "competition_benchmark_cameo_official_intake_gate_status",
            "",
        ),
        "competition_benchmark_cameo_official_intake_gate_ready": bool(
            summary.get("competition_benchmark_cameo_official_intake_gate_ready") is True
        ),
        "competition_benchmark_cameo_official_result_intake_ready": bool(
            summary.get("competition_benchmark_cameo_official_result_intake_ready") is True
        ),
        "competition_benchmark_cameo_official_intake_gate_artifact_path": summary.get(
            "competition_benchmark_cameo_official_intake_gate_artifact_path",
            "",
        ),
        "competition_benchmark_cameo_official_operator_intake_csv": summary.get(
            "competition_benchmark_cameo_official_operator_intake_csv",
            "",
        ),
        "competition_benchmark_cameo_official_operator_template_csv": summary.get(
            "competition_benchmark_cameo_official_operator_template_csv",
            "",
        ),
        "competition_benchmark_cameo_official_result_row_count": int(
            summary.get("competition_benchmark_cameo_official_result_row_count") or 0
        ),
        "competition_benchmark_cameo_official_accepted_result_count": int(
            summary.get("competition_benchmark_cameo_official_accepted_result_count") or 0
        ),
        "competition_benchmark_cameo_official_rejected_result_count": int(
            summary.get("competition_benchmark_cameo_official_rejected_result_count") or 0
        ),
        "competition_benchmark_cameo_official_model1_result_ready": bool(
            summary.get("competition_benchmark_cameo_official_model1_result_ready") is True
        ),
        "competition_benchmark_cameo_official_blocker_count": int(
            summary.get("competition_benchmark_cameo_official_blocker_count") or 0
        ),
        "competition_benchmark_cameo_official_blocker_codes": _string_list(
            summary.get("competition_benchmark_cameo_official_blocker_codes")
        ),
        "competition_benchmark_cameo_official_operator_action_required_count": int(
            summary.get(
                "competition_benchmark_cameo_official_operator_action_required_count"
            )
            or 0
        ),
        "competition_benchmark_cameo_official_operator_action_required_row_count": int(
            summary.get(
                "competition_benchmark_cameo_official_operator_action_required_row_count"
            )
            or 0
        ),
        "competition_benchmark_cameo_official_primary_blocker_code": summary.get(
            "competition_benchmark_cameo_official_primary_blocker_code",
            "",
        ),
        "competition_benchmark_cameo_official_primary_required_action": summary.get(
            "competition_benchmark_cameo_official_primary_required_action",
            "",
        ),
        "competition_benchmark_cameo_official_required_column_count": int(
            summary.get("competition_benchmark_cameo_official_required_column_count") or 0
        ),
        "competition_benchmark_cameo_official_missing_required_column_count": int(
            summary.get("competition_benchmark_cameo_official_missing_required_column_count")
            or 0
        ),
        "competition_benchmark_cameo_official_missing_required_columns": _string_list(
            summary.get("competition_benchmark_cameo_official_missing_required_columns")
        ),
        "competition_benchmark_cameo_official_allowed_result_source_kinds": _string_list(
            summary.get("competition_benchmark_cameo_official_allowed_result_source_kinds")
        ),
        "competition_benchmark_cameo_official_source_provenance_ready_row_count": int(
            summary.get(
                "competition_benchmark_cameo_official_source_provenance_ready_row_count"
            )
            or 0
        ),
        "competition_benchmark_cameo_official_metric_ready_row_count": int(
            summary.get("competition_benchmark_cameo_official_metric_ready_row_count")
            or 0
        ),
        "competition_benchmark_cameo_official_local_native_accuracy_blocker_count": int(
            summary.get(
                "competition_benchmark_cameo_official_local_native_accuracy_blocker_count"
            )
            or 0
        ),
        "competition_benchmark_cameo_official_native_local_accuracy_used": bool(
            summary.get("competition_benchmark_cameo_official_native_local_accuracy_used")
            is True
        ),
        "competition_benchmark_cameo_official_external_state_mutated": bool(
            summary.get("competition_benchmark_cameo_official_external_state_mutated") is True
        ),
        "competition_benchmark_casp16_ligand_source_manifest_status": summary.get(
            "competition_benchmark_casp16_ligand_source_manifest_status",
            "",
        ),
        "competition_benchmark_casp16_ligand_source_manifest_ready": bool(
            summary.get("competition_benchmark_casp16_ligand_source_manifest_ready") is True
        ),
        "competition_benchmark_casp16_ligand_materialization_ready": bool(
            summary.get("competition_benchmark_casp16_ligand_materialization_ready") is True
        ),
        "competition_benchmark_casp16_ligand_scorecard_ready": bool(
            summary.get("competition_benchmark_casp16_ligand_scorecard_ready") is True
        ),
        "competition_benchmark_casp16_ligand_competition_credibility_ready": bool(
            summary.get("competition_benchmark_casp16_ligand_competition_credibility_ready")
            is True
        ),
        "competition_benchmark_casp16_ligand_raw_data_committed": bool(
            summary.get("competition_benchmark_casp16_ligand_raw_data_committed") is True
        ),
        "competition_benchmark_casp16_ligand_raw_data_git_tracked_file_count": int(
            summary.get("competition_benchmark_casp16_ligand_raw_data_git_tracked_file_count")
            or 0
        ),
        "competition_benchmark_casp16_ligand_pose_target_count": int(
            summary.get("competition_benchmark_casp16_ligand_pose_target_count") or 0
        ),
        "competition_benchmark_casp16_ligand_affinity_target_count": int(
            summary.get("competition_benchmark_casp16_ligand_affinity_target_count") or 0
        ),
        "competition_benchmark_casp16_ligand_next_action": summary.get(
            "competition_benchmark_casp16_ligand_next_action",
            "",
        ),
        "competition_benchmark_bm5_capri_complex_source_manifest_status": summary.get(
            "competition_benchmark_bm5_capri_complex_source_manifest_status",
            "",
        ),
        "competition_benchmark_bm5_complex_benchmark_ready": bool(
            summary.get("competition_benchmark_bm5_complex_benchmark_ready") is True
        ),
        "competition_benchmark_capri_score_set_ready": bool(
            summary.get("competition_benchmark_capri_score_set_ready") is True
        ),
        "competition_benchmark_bm5_capri_complex_competition_credibility_ready": bool(
            summary.get(
                "competition_benchmark_bm5_capri_complex_competition_credibility_ready"
            )
            is True
        ),
        "competition_benchmark_bm5_capri_complex_raw_data_committed": bool(
            summary.get("competition_benchmark_bm5_capri_complex_raw_data_committed")
            is True
        ),
        "competition_benchmark_bm5_capri_complex_raw_data_git_tracked_file_count": int(
            summary.get(
                "competition_benchmark_bm5_capri_complex_raw_data_git_tracked_file_count"
            )
            or 0
        ),
        "competition_benchmark_bm5_capri_complex_primary_metric": summary.get(
            "competition_benchmark_bm5_capri_complex_primary_metric",
            "",
        ),
        "competition_benchmark_bm5_capri_complex_next_action": summary.get(
            "competition_benchmark_bm5_capri_complex_next_action",
            "",
        ),
        "competition_benchmark_competition_credibility_extension_ready": bool(
            summary.get("competition_benchmark_competition_credibility_extension_ready")
            is True
        ),
        "competition_benchmark_competition_credibility_extension_blocker_count": int(
            summary.get(
                "competition_benchmark_competition_credibility_extension_blocker_count"
            )
            or 0
        ),
        "competition_benchmark_competition_credibility_extension_blockers": _string_list(
            summary.get("competition_benchmark_competition_credibility_extension_blockers")
        ),
        "competition_benchmark_competition_credibility_extension_primary_blocker": summary.get(
            "competition_benchmark_competition_credibility_extension_primary_blocker",
            "",
        ),
        "competition_benchmark_competition_credibility_extension_next_actions": _string_list(
            summary.get("competition_benchmark_competition_credibility_extension_next_actions")
        ),
        "competition_benchmark_competition_credibility_extension_primary_next_action": summary.get(
            "competition_benchmark_competition_credibility_extension_primary_next_action",
            "",
        ),
        "competition_benchmark_custody_work_order_status": summary.get(
            "competition_benchmark_custody_work_order_status",
            "",
        ),
        "competition_benchmark_custody_work_order_ready": bool(
            summary.get("competition_benchmark_custody_work_order_ready") is True
        ),
        "competition_benchmark_custody_work_order_action_count": int(
            summary.get("competition_benchmark_custody_work_order_action_count") or 0
        ),
        "competition_benchmark_custody_work_order_raw_data_blocked_row_count": int(
            summary.get("competition_benchmark_custody_work_order_raw_data_blocked_row_count")
            or 0
        ),
        "competition_benchmark_custody_work_order_missing_receipt_row_count": int(
            summary.get("competition_benchmark_custody_work_order_missing_receipt_row_count")
            or 0
        ),
        "competition_benchmark_custody_work_order_primary_work_order_id": summary.get(
            "competition_benchmark_custody_work_order_primary_work_order_id",
            "",
        ),
        "competition_benchmark_custody_work_order_primary_required_action": summary.get(
            "competition_benchmark_custody_work_order_primary_required_action",
            "",
        ),
        "competition_benchmark_custody_work_order_primary_verification_command": summary.get(
            "competition_benchmark_custody_work_order_primary_verification_command",
            "",
        ),
        "competition_benchmark_package_b_required_for_ligand_commercial_claims": bool(
            summary.get("competition_benchmark_package_b_required_for_ligand_commercial_claims")
            is True
        ),
        "competition_benchmark_package_b_public_benchmark_contract_status": summary.get(
            "competition_benchmark_package_b_public_benchmark_contract_status",
            "",
        ),
        "competition_benchmark_package_b_public_benchmark_validation_ready": bool(
            summary.get("competition_benchmark_package_b_public_benchmark_validation_ready")
            is True
        ),
        "competition_benchmark_package_b_ligand_public_benchmark_foundation_ready": bool(
            summary.get(
                "competition_benchmark_package_b_ligand_public_benchmark_foundation_ready"
            )
            is True
        ),
        "competition_benchmark_package_b_ligand_suite_ids": _string_list(
            summary.get("competition_benchmark_package_b_ligand_suite_ids")
        ),
        "competition_benchmark_package_b_refine_tier_public_benchmark_status": summary.get(
            "competition_benchmark_package_b_refine_tier_public_benchmark_status",
            "",
        ),
        "competition_benchmark_package_b_claim_grade_public_benchmark_ready": bool(
            summary.get("competition_benchmark_package_b_claim_grade_public_benchmark_ready")
            is True
        ),
        "competition_benchmark_package_b_claim_grade_blocker_count": int(
            summary.get("competition_benchmark_package_b_claim_grade_blocker_count") or 0
        ),
        "competition_benchmark_package_b_claim_grade_blockers": _string_list(
            summary.get("competition_benchmark_package_b_claim_grade_blockers")
        ),
        "competition_benchmark_package_b_refine_tier_work_order_apply_status": summary.get(
            "competition_benchmark_package_b_refine_tier_work_order_apply_status",
            "",
        ),
        "competition_benchmark_package_b_refine_tier_work_order_apply_ready": bool(
            summary.get("competition_benchmark_package_b_refine_tier_work_order_apply_ready")
            is True
        ),
        "competition_benchmark_competition_evidence_role": summary.get(
            "competition_benchmark_competition_evidence_role",
            "",
        ),
        "competition_benchmark_competition_ligand_commercial_claim_allowed": bool(
            summary.get("competition_benchmark_competition_ligand_commercial_claim_allowed")
            is True
        ),
        "competition_benchmark_competition_ligand_claim_package_b_dependency_ready": bool(
            summary.get(
                "competition_benchmark_competition_ligand_claim_package_b_dependency_ready"
            )
            is True
        ),
        "competition_benchmark_competition_ligand_claim_blocker_count": int(
            summary.get("competition_benchmark_competition_ligand_claim_blocker_count")
            or 0
        ),
        "competition_benchmark_competition_ligand_claim_blockers": _string_list(
            summary.get("competition_benchmark_competition_ligand_claim_blockers")
        ),
        "competition_benchmark_package_b_bridge_next_action": summary.get(
            "competition_benchmark_package_b_bridge_next_action",
            "",
        ),
        "rows": rows,
        "overclaim_warnings": warnings,
        "execution_enabled": False,
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
