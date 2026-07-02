from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-operator-cockpit"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_OPERATOR_COCKPIT_ARTIFACT = ROOT / "runs" / "product_operator_cockpit_current.json"

CLAIM_BOUNDARY = (
    "Product operator cockpit endpoint only; it reads the local cockpit artifact and renders operator-facing "
    "status, panel rows, and claim boundaries. It does not run docking, run MD, build bundles, approve claims, "
    "upload, email, delete, commit, push, deploy, or mutate external state."
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
    return summary if isinstance(summary, dict) else {}


def _list(packet: dict[str, Any], key: str) -> list[Any]:
    value = packet.get(key)
    return list(value) if isinstance(value, list) else []


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    return []


def _missing_response() -> dict[str, Any]:
    return {
        "status": "missing_product_operator_cockpit",
        "artifact_path": str(PRODUCT_OPERATOR_COCKPIT_ARTIFACT),
        "phase8_surface_ready": False,
        "required_phase8_panel_count": 9,
        "observed_phase8_panel_count": 0,
        "missing_required_phase8_panel_count": 9,
        "missing_required_phase8_panel_ids": [
            "product_capabilities_dashboard",
            "goal_readiness_dashboard",
            "hbond_backmap_candidate_table",
            "gpcr_hard_decoy_blocker_panel",
            "pocketmd_lite_report_panel",
            "public_benchmark_scorecard",
            "release_blockers_operator_actions",
            "evidence_bundle_export",
            "claim_boundary_matrix",
        ],
        "source_artifact_ready_panel_count": 0,
        "source_artifact_blocked_panel_count": 9,
        "source_artifact_blocked_panel_ids": [],
        "operator_action_required_panel_count": 9,
        "operator_action_required_panel_ids": [],
        "paid_pilot_wording_allowed": False,
        "general_platform_claim_allowed": False,
        "gpcr_hard_decoy_metric_ready": False,
        "gpcr_broad_claim_allowed": False,
        "gpcr_phase3_closure_present": False,
        "gpcr_phase3_closure_evidence_ready": False,
        "gpcr_phase3_exit_metric_conditions_ready": False,
        "gpcr_phase3_broad_promotion_locked": False,
        "gpcr_phase3_effective_ranking_pr_auc_ci_low": 0.0,
        "gpcr_phase3_effective_top20_hit_rate": 0.0,
        "gpcr_phase3_effective_decoys_above_positive_total": 0,
        "gpcr_phase3_effective_metric_source": "",
        "gpcr_phase3_promotion_blocker_count": 0,
        "gpcr_promotion_work_order_row_count": 0,
        "gpcr_promotion_work_order_lane_count": 0,
        "gpcr_promotion_work_order_primary_blocker": "",
        "pocketmd_lite_refinement_evidence_ready": False,
        "pocketmd_lite_report_evidence_ready": False,
        "pocketmd_lite_fill_preview_evidence_ready": False,
        "pocketmd_lite_preview_requires_canonical_review": False,
        "pocketmd_lite_claim_grade_metric_ready_row_count": 0,
        "pocketmd_lite_local_min_ligand_rmsd_a_max": 0.0,
        "pocketmd_lite_hbond_persistence_min": 0.0,
        "pocketmd_lite_contact_persistence_min": 0.0,
        "pocketmd_lite_initial_clash_count_total": 0.0,
        "pocketmd_lite_final_clash_count_total": 0.0,
        "pocketmd_lite_clash_relief_count_total": 0.0,
        "pocketmd_lite_green_band_condition_text": "",
        "pocketmd_lite_claim_allowed": False,
        "public_benchmark_claim_allowed": False,
        "public_benchmark_receipt_attach_packet_ready": False,
        "public_benchmark_receipt_attach_packet_present": False,
        "public_benchmark_vina_gnina_pending_score_count": 0,
        "public_benchmark_vina_gnina_pending_field_count": 0,
        "public_benchmark_metric_source_pending_field_count": 0,
        "public_benchmark_metric_source_pending_approval_token_count": 0,
        "public_benchmark_field_work_order_row_count": 0,
        "public_benchmark_field_work_order_pending_field_count": 0,
        "public_benchmark_field_work_order_primary_field_name": "",
        "public_benchmark_field_work_order_primary_lane_id": "",
        "public_benchmark_primary_blocker_id": "",
        "public_benchmark_primary_blocker": "",
        "public_benchmark_primary_next_required_step": "",
        "public_benchmark_vina_gnina_score_template_csv": "",
        "public_benchmark_vina_gnina_score_template_receipt_json": "",
        "public_benchmark_metric_source_receipt_csv": "",
        "public_benchmark_vina_gnina_adapter_command_after_fill": "",
        "evidence_bundle_export_ready": False,
        "api_customer_flow_release_evidence_present": False,
        "api_customer_flow_release_evidence_ready": False,
        "api_customer_flow_release_evidence_status": "",
        "api_customer_flow_release_evidence_pass_count": 0,
        "api_customer_flow_release_evidence_blocker_count": 0,
        "api_customer_flow_tier_alpha_smoke_status": "",
        "api_customer_flow_tier_alpha_runner_execution_ok": False,
        "api_customer_flow_result_manifest_signature_verified": False,
        "api_customer_flow_restricted_runtime_ready": False,
        "api_customer_flow_bundle_validation_ready": False,
        "customer_shadow_paid_pilot_evidence_ready": False,
        "customer_shadow_real_row_count": 0,
        "customer_shadow_completed_case_count": 0,
        "customer_shadow_required_case_count": 0,
        "customer_shadow_missing_case_count": 0,
        "customer_shadow_customer_retained_raw_data_count": 0,
        "customer_shadow_redistribution_allowed_false_count": 0,
        "customer_shadow_anonymized_result_summary_count": 0,
        "customer_shadow_reviewer_signoff_count": 0,
        "customer_shadow_evidence_blocker_count": 0,
        "customer_shadow_work_order_ready": False,
        "customer_shadow_work_order_row_count": 0,
        "customer_shadow_work_order_primary_case_slot_id": "",
        "customer_shadow_work_order_primary_required_action": "",
        "customer_shadow_intake_schema_ready": False,
        "customer_shadow_minimum_met": False,
        "customer_shadow_raw_data_stored_in_repo": False,
        "customer_shadow_invalid_row_count": 0,
        "customer_shadow_mock_fixture_row_count": 0,
        "customer_shadow_required_column_count": 0,
        "customer_shadow_redistribution_allowed_required_value": False,
        "developer_preview_clean_baseline_ready": False,
        "developer_preview_gate_count": 0,
        "developer_preview_ready_gate_count": 0,
        "developer_preview_blocked_gate_count": 0,
        "developer_preview_receipt_work_order_row_count": 0,
        "developer_preview_receipt_blocker_count": 0,
        "developer_preview_primary_blocker_id": "",
        "developer_preview_receipt_work_order_primary_gate_id": "",
        "developer_preview_receipt_work_order_primary_receipt_artifact": "",
        "f2g_f2h_preflight_present": False,
        "f2g_f2h_recovery_packet_present": False,
        "f2g_f2h_preflight_status": "",
        "f2g_f2h_recovery_status": "",
        "f2g_f2h_recovery_required": False,
        "f2g_f2h_preflight_blocker_count": 0,
        "f2g_f2h_blocked_recovery_item_count": 0,
        "f2g_f2h_recovery_item_count": 0,
        "f2g_f2h_primary_recovery_item_id": "",
        "f2g_f2h_primary_required_surface": "",
        "f2g_f2h_primary_blocker": "",
        "f2g_f2h_primary_operator_action": "",
        "f2g_f2h_audit_ready": False,
        "f2h_continuation_allowed": False,
        "f2g_f2h_placeholder_surface_creation_allowed": False,
        "f2g_f2h_surface_restore_executed": False,
        "pm_priority_queue_present": False,
        "pm_priority_queue_status": "",
        "pm_priority_queue_ready_item_count": 0,
        "pm_priority_queue_blocked_item_count": 0,
        "pm_priority_queue_first_blocked_item_id": "",
        "pm_priority_queue_first_blocker": "",
        "pm_priority_queue_next_required_step": "",
        "release_allowed": False,
        "panels": [],
        "claim_matrix": [],
        "next_required_step": "Run python3 tools/product/build_product_operator_cockpit.py.",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


@router.get("/operator-cockpit")
async def get_product_operator_cockpit() -> dict[str, Any]:
    """Return the read-only Product Operator Cockpit surface.

    Exposes the local ``runs/product_operator_cockpit_current.json`` artifact so
    the GUI/operator API can inspect Phase 8 panels and allowed/disallowed claim
    text without running scientific workloads or promoting claims.
    """

    packet = _read_json_object(PRODUCT_OPERATOR_COCKPIT_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return _missing_response()

    return {
        "status": summary.get("status", ""),
        "artifact_path": str(PRODUCT_OPERATOR_COCKPIT_ARTIFACT),
        "schema_version": summary.get("schema_version", ""),
        "phase8_surface_ready": bool(summary.get("phase8_surface_ready") is True),
        "required_phase8_panel_count": _int(summary.get("required_phase8_panel_count")),
        "required_phase8_panel_ids": _string_list(summary.get("required_phase8_panel_ids")),
        "observed_phase8_panel_count": _int(summary.get("observed_phase8_panel_count")),
        "missing_required_phase8_panel_count": _int(summary.get("missing_required_phase8_panel_count")),
        "missing_required_phase8_panel_ids": _string_list(summary.get("missing_required_phase8_panel_ids")),
        "surface_ready_panel_count": _int(summary.get("surface_ready_panel_count")),
        "source_artifact_ready_panel_count": _int(summary.get("source_artifact_ready_panel_count")),
        "source_artifact_blocked_panel_count": _int(summary.get("source_artifact_blocked_panel_count")),
        "source_artifact_blocked_panel_ids": _string_list(summary.get("source_artifact_blocked_panel_ids")),
        "operator_action_required_panel_count": _int(summary.get("operator_action_required_panel_count")),
        "operator_action_required_panel_ids": _string_list(summary.get("operator_action_required_panel_ids")),
        "allowed_claim_count": _int(summary.get("allowed_claim_count")),
        "disallowed_claim_count": _int(summary.get("disallowed_claim_count")),
        "paid_pilot_wording_allowed": bool(summary.get("paid_pilot_wording_allowed") is True),
        "general_platform_claim_allowed": bool(summary.get("general_platform_claim_allowed") is True),
        "gpcr_hard_decoy_metric_ready": bool(summary.get("gpcr_hard_decoy_metric_ready") is True),
        "gpcr_broad_claim_allowed": bool(summary.get("gpcr_broad_claim_allowed") is True),
        "gpcr_phase3_closure_present": bool(summary.get("gpcr_phase3_closure_present") is True),
        "gpcr_phase3_closure_evidence_ready": bool(
            summary.get("gpcr_phase3_closure_evidence_ready") is True
        ),
        "gpcr_phase3_exit_metric_conditions_ready": bool(
            summary.get("gpcr_phase3_exit_metric_conditions_ready") is True
        ),
        "gpcr_phase3_broad_promotion_locked": bool(
            summary.get("gpcr_phase3_broad_promotion_locked") is True
        ),
        "gpcr_phase3_effective_ranking_pr_auc_ci_low": float(
            summary.get("gpcr_phase3_effective_ranking_pr_auc_ci_low") or 0.0
        ),
        "gpcr_phase3_effective_top20_hit_rate": float(
            summary.get("gpcr_phase3_effective_top20_hit_rate") or 0.0
        ),
        "gpcr_phase3_effective_decoys_above_positive_total": _int(
            summary.get("gpcr_phase3_effective_decoys_above_positive_total")
        ),
        "gpcr_phase3_effective_metric_source": str(
            summary.get("gpcr_phase3_effective_metric_source") or ""
        ),
        "gpcr_phase3_promotion_blocker_count": _int(
            summary.get("gpcr_phase3_promotion_blocker_count")
        ),
        "gpcr_promotion_work_order_row_count": _int(
            summary.get("gpcr_promotion_work_order_row_count")
        ),
        "gpcr_promotion_work_order_lane_count": _int(
            summary.get("gpcr_promotion_work_order_lane_count")
        ),
        "gpcr_promotion_work_order_primary_blocker": str(
            summary.get("gpcr_promotion_work_order_primary_blocker") or ""
        ),
        "pocketmd_lite_refinement_evidence_ready": bool(
            summary.get("pocketmd_lite_refinement_evidence_ready") is True
        ),
        "pocketmd_lite_report_evidence_ready": bool(
            summary.get("pocketmd_lite_report_evidence_ready") is True
        ),
        "pocketmd_lite_fill_preview_evidence_ready": bool(
            summary.get("pocketmd_lite_fill_preview_evidence_ready") is True
        ),
        "pocketmd_lite_preview_requires_canonical_review": bool(
            summary.get("pocketmd_lite_preview_requires_canonical_review") is True
        ),
        "pocketmd_lite_claim_grade_metric_ready_row_count": _int(
            summary.get("pocketmd_lite_claim_grade_metric_ready_row_count")
        ),
        "pocketmd_lite_local_min_ligand_rmsd_a_max": _float(
            summary.get("pocketmd_lite_local_min_ligand_rmsd_a_max")
        ),
        "pocketmd_lite_hbond_persistence_min": _float(
            summary.get("pocketmd_lite_hbond_persistence_min")
        ),
        "pocketmd_lite_contact_persistence_min": _float(
            summary.get("pocketmd_lite_contact_persistence_min")
        ),
        "pocketmd_lite_initial_clash_count_total": _float(
            summary.get("pocketmd_lite_initial_clash_count_total")
        ),
        "pocketmd_lite_final_clash_count_total": _float(
            summary.get("pocketmd_lite_final_clash_count_total")
        ),
        "pocketmd_lite_clash_relief_count_total": _float(
            summary.get("pocketmd_lite_clash_relief_count_total")
        ),
        "pocketmd_lite_green_band_condition_text": str(
            summary.get("pocketmd_lite_green_band_condition_text") or ""
        ),
        "pocketmd_lite_claim_allowed": bool(summary.get("pocketmd_lite_claim_allowed") is True),
        "public_benchmark_claim_allowed": bool(summary.get("public_benchmark_claim_allowed") is True),
        "public_benchmark_receipt_attach_packet_ready": bool(
            summary.get("public_benchmark_receipt_attach_packet_ready") is True
        ),
        "public_benchmark_receipt_attach_packet_present": bool(
            summary.get("public_benchmark_receipt_attach_packet_present") is True
        ),
        "public_benchmark_vina_gnina_pending_score_count": _int(
            summary.get("public_benchmark_vina_gnina_pending_score_count")
        ),
        "public_benchmark_vina_gnina_pending_field_count": _int(
            summary.get("public_benchmark_vina_gnina_pending_field_count")
        ),
        "public_benchmark_metric_source_pending_field_count": _int(
            summary.get("public_benchmark_metric_source_pending_field_count")
        ),
        "public_benchmark_metric_source_pending_approval_token_count": _int(
            summary.get("public_benchmark_metric_source_pending_approval_token_count")
        ),
        "public_benchmark_field_work_order_row_count": _int(
            summary.get("public_benchmark_field_work_order_row_count")
        ),
        "public_benchmark_field_work_order_pending_field_count": _int(
            summary.get("public_benchmark_field_work_order_pending_field_count")
        ),
        "public_benchmark_field_work_order_primary_field_name": str(
            summary.get("public_benchmark_field_work_order_primary_field_name") or ""
        ),
        "public_benchmark_field_work_order_primary_lane_id": str(
            summary.get("public_benchmark_field_work_order_primary_lane_id") or ""
        ),
        "public_benchmark_primary_blocker_id": str(
            summary.get("public_benchmark_primary_blocker_id") or ""
        ),
        "public_benchmark_primary_blocker": str(
            summary.get("public_benchmark_primary_blocker") or ""
        ),
        "public_benchmark_primary_next_required_step": str(
            summary.get("public_benchmark_primary_next_required_step") or ""
        ),
        "public_benchmark_vina_gnina_score_template_csv": str(
            summary.get("public_benchmark_vina_gnina_score_template_csv") or ""
        ),
        "public_benchmark_vina_gnina_score_template_receipt_json": str(
            summary.get("public_benchmark_vina_gnina_score_template_receipt_json") or ""
        ),
        "public_benchmark_metric_source_receipt_csv": str(
            summary.get("public_benchmark_metric_source_receipt_csv") or ""
        ),
        "public_benchmark_vina_gnina_adapter_command_after_fill": str(
            summary.get("public_benchmark_vina_gnina_adapter_command_after_fill") or ""
        ),
        "evidence_bundle_export_ready": bool(summary.get("evidence_bundle_export_ready") is True),
        "api_customer_flow_release_evidence_present": bool(
            summary.get("api_customer_flow_release_evidence_present") is True
        ),
        "api_customer_flow_release_evidence_ready": bool(
            summary.get("api_customer_flow_release_evidence_ready") is True
        ),
        "api_customer_flow_release_evidence_status": str(
            summary.get("api_customer_flow_release_evidence_status") or ""
        ),
        "api_customer_flow_release_evidence_pass_count": _int(
            summary.get("api_customer_flow_release_evidence_pass_count")
        ),
        "api_customer_flow_release_evidence_blocker_count": _int(
            summary.get("api_customer_flow_release_evidence_blocker_count")
        ),
        "api_customer_flow_tier_alpha_smoke_status": str(
            summary.get("api_customer_flow_tier_alpha_smoke_status") or ""
        ),
        "api_customer_flow_tier_alpha_runner_execution_ok": bool(
            summary.get("api_customer_flow_tier_alpha_runner_execution_ok") is True
        ),
        "api_customer_flow_result_manifest_signature_verified": bool(
            summary.get("api_customer_flow_result_manifest_signature_verified") is True
        ),
        "api_customer_flow_restricted_runtime_ready": bool(
            summary.get("api_customer_flow_restricted_runtime_ready") is True
        ),
        "api_customer_flow_bundle_validation_ready": bool(
            summary.get("api_customer_flow_bundle_validation_ready") is True
        ),
        "customer_shadow_paid_pilot_evidence_ready": bool(
            summary.get("customer_shadow_paid_pilot_evidence_ready") is True
        ),
        "customer_shadow_real_row_count": _int(summary.get("customer_shadow_real_row_count")),
        "customer_shadow_completed_case_count": _int(summary.get("customer_shadow_completed_case_count")),
        "customer_shadow_required_case_count": _int(summary.get("customer_shadow_required_case_count")),
        "customer_shadow_missing_case_count": _int(summary.get("customer_shadow_missing_case_count")),
        "customer_shadow_customer_retained_raw_data_count": _int(
            summary.get("customer_shadow_customer_retained_raw_data_count")
        ),
        "customer_shadow_redistribution_allowed_false_count": _int(
            summary.get("customer_shadow_redistribution_allowed_false_count")
        ),
        "customer_shadow_anonymized_result_summary_count": _int(
            summary.get("customer_shadow_anonymized_result_summary_count")
        ),
        "customer_shadow_reviewer_signoff_count": _int(
            summary.get("customer_shadow_reviewer_signoff_count")
        ),
        "customer_shadow_evidence_blocker_count": _int(
            summary.get("customer_shadow_evidence_blocker_count")
        ),
        "customer_shadow_work_order_ready": bool(
            summary.get("customer_shadow_work_order_ready") is True
        ),
        "customer_shadow_work_order_row_count": _int(
            summary.get("customer_shadow_work_order_row_count")
        ),
        "customer_shadow_work_order_primary_case_slot_id": str(
            summary.get("customer_shadow_work_order_primary_case_slot_id") or ""
        ),
        "customer_shadow_work_order_primary_required_action": str(
            summary.get("customer_shadow_work_order_primary_required_action") or ""
        ),
        "customer_shadow_intake_schema_ready": bool(
            summary.get("customer_shadow_intake_schema_ready") is True
        ),
        "customer_shadow_minimum_met": bool(summary.get("customer_shadow_minimum_met") is True),
        "customer_shadow_raw_data_stored_in_repo": bool(
            summary.get("customer_shadow_raw_data_stored_in_repo") is True
        ),
        "customer_shadow_invalid_row_count": _int(summary.get("customer_shadow_invalid_row_count")),
        "customer_shadow_mock_fixture_row_count": _int(
            summary.get("customer_shadow_mock_fixture_row_count")
        ),
        "customer_shadow_required_column_count": _int(
            summary.get("customer_shadow_required_column_count")
        ),
        "customer_shadow_redistribution_allowed_required_value": bool(
            summary.get("customer_shadow_redistribution_allowed_required_value") is True
        ),
        "developer_preview_clean_baseline_ready": bool(
            summary.get("developer_preview_clean_baseline_ready") is True
        ),
        "developer_preview_gate_count": _int(summary.get("developer_preview_gate_count")),
        "developer_preview_ready_gate_count": _int(
            summary.get("developer_preview_ready_gate_count")
        ),
        "developer_preview_blocked_gate_count": _int(
            summary.get("developer_preview_blocked_gate_count")
        ),
        "developer_preview_receipt_work_order_row_count": _int(
            summary.get("developer_preview_receipt_work_order_row_count")
        ),
        "developer_preview_receipt_blocker_count": _int(
            summary.get("developer_preview_receipt_blocker_count")
        ),
        "developer_preview_primary_blocker_id": str(
            summary.get("developer_preview_primary_blocker_id") or ""
        ),
        "developer_preview_receipt_work_order_primary_gate_id": str(
            summary.get("developer_preview_receipt_work_order_primary_gate_id") or ""
        ),
        "developer_preview_receipt_work_order_primary_receipt_artifact": str(
            summary.get("developer_preview_receipt_work_order_primary_receipt_artifact") or ""
        ),
        "f2g_f2h_preflight_present": bool(summary.get("f2g_f2h_preflight_present") is True),
        "f2g_f2h_recovery_packet_present": bool(
            summary.get("f2g_f2h_recovery_packet_present") is True
        ),
        "f2g_f2h_preflight_status": str(summary.get("f2g_f2h_preflight_status") or ""),
        "f2g_f2h_recovery_status": str(summary.get("f2g_f2h_recovery_status") or ""),
        "f2g_f2h_recovery_required": bool(summary.get("f2g_f2h_recovery_required") is True),
        "f2g_f2h_preflight_blocker_count": _int(
            summary.get("f2g_f2h_preflight_blocker_count")
        ),
        "f2g_f2h_blocked_recovery_item_count": _int(
            summary.get("f2g_f2h_blocked_recovery_item_count")
        ),
        "f2g_f2h_recovery_item_count": _int(summary.get("f2g_f2h_recovery_item_count")),
        "f2g_f2h_primary_recovery_item_id": str(
            summary.get("f2g_f2h_primary_recovery_item_id") or ""
        ),
        "f2g_f2h_primary_required_surface": str(
            summary.get("f2g_f2h_primary_required_surface") or ""
        ),
        "f2g_f2h_primary_blocker": str(summary.get("f2g_f2h_primary_blocker") or ""),
        "f2g_f2h_primary_operator_action": str(
            summary.get("f2g_f2h_primary_operator_action") or ""
        ),
        "f2g_f2h_audit_ready": bool(summary.get("f2g_f2h_audit_ready") is True),
        "f2h_continuation_allowed": bool(summary.get("f2h_continuation_allowed") is True),
        "f2g_f2h_placeholder_surface_creation_allowed": bool(
            summary.get("f2g_f2h_placeholder_surface_creation_allowed") is True
        ),
        "f2g_f2h_surface_restore_executed": bool(
            summary.get("f2g_f2h_surface_restore_executed") is True
        ),
        "pm_priority_queue_present": bool(summary.get("pm_priority_queue_present") is True),
        "pm_priority_queue_status": str(summary.get("pm_priority_queue_status") or ""),
        "pm_priority_queue_ready_item_count": _int(summary.get("pm_priority_queue_ready_item_count")),
        "pm_priority_queue_blocked_item_count": _int(summary.get("pm_priority_queue_blocked_item_count")),
        "pm_priority_queue_first_blocked_item_id": str(
            summary.get("pm_priority_queue_first_blocked_item_id") or ""
        ),
        "pm_priority_queue_first_blocker": str(summary.get("pm_priority_queue_first_blocker") or ""),
        "pm_priority_queue_next_required_step": str(
            summary.get("pm_priority_queue_next_required_step") or ""
        ),
        "release_allowed": bool(summary.get("release_allowed") is True),
        "panels": _list(packet, "rows"),
        "claim_matrix": _list(packet, "claim_matrix"),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary") or CLAIM_BOUNDARY,
    }
