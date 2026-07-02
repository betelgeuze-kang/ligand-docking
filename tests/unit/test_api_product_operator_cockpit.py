from __future__ import annotations

import asyncio
import json
from pathlib import Path

from api import product_operator_cockpit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_product_operator_cockpit_endpoint_reads_current_artifact(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "runs/product_operator_cockpit_current.json"
    monkeypatch.setattr(mod, "PRODUCT_OPERATOR_COCKPIT_ARTIFACT", artifact)
    _write_json(
        artifact,
        {
            "summary": {
                "status": "product_operator_cockpit_ready_claims_blocked",
                "schema_version": "product_operator_cockpit_v1",
                "phase8_surface_ready": True,
                "required_phase8_panel_count": 9,
                "required_phase8_panel_ids": ["product_capabilities_dashboard"],
                "observed_phase8_panel_count": 9,
                "missing_required_phase8_panel_count": 0,
                "missing_required_phase8_panel_ids": [],
                "surface_ready_panel_count": 9,
                "source_artifact_ready_panel_count": 6,
                "source_artifact_blocked_panel_count": 3,
                "source_artifact_blocked_panel_ids": ["hbond_backmap_candidate_table"],
                "operator_action_required_panel_count": 8,
                "operator_action_required_panel_ids": ["release_blockers_operator_actions"],
                "allowed_claim_count": 4,
                "disallowed_claim_count": 6,
                "paid_pilot_wording_allowed": False,
                "general_platform_claim_allowed": False,
                "gpcr_hard_decoy_metric_ready": True,
                "gpcr_broad_claim_allowed": False,
                "gpcr_phase3_closure_present": True,
                "gpcr_phase3_closure_evidence_ready": True,
                "gpcr_phase3_exit_metric_conditions_ready": True,
                "gpcr_phase3_broad_promotion_locked": True,
                "gpcr_phase3_effective_ranking_pr_auc_ci_low": 0.5597832604,
                "gpcr_phase3_effective_top20_hit_rate": 1.0,
                "gpcr_phase3_effective_decoys_above_positive_total": 0,
                "gpcr_phase3_effective_metric_source": "claim_unlock_audit",
                "gpcr_phase3_promotion_blocker_count": 2,
                "gpcr_promotion_work_order_row_count": 2,
                "gpcr_promotion_work_order_lane_count": 2,
                "gpcr_promotion_work_order_primary_blocker": (
                    "broad_scope:formal_broad_claim_review_not_approved"
                ),
                "pocketmd_lite_refinement_evidence_ready": True,
                "pocketmd_lite_report_evidence_ready": False,
                "pocketmd_lite_fill_preview_evidence_ready": True,
                "pocketmd_lite_preview_requires_canonical_review": True,
                "pocketmd_lite_claim_allowed": False,
                "public_benchmark_claim_allowed": False,
                "public_benchmark_receipt_attach_packet_ready": False,
                "public_benchmark_receipt_attach_packet_present": True,
                "public_benchmark_vina_gnina_pending_score_count": 32,
                "public_benchmark_vina_gnina_pending_field_count": 192,
                "public_benchmark_metric_source_pending_field_count": 510,
                "public_benchmark_metric_source_pending_approval_token_count": 51,
                "public_benchmark_field_work_order_row_count": 22,
                "public_benchmark_field_work_order_pending_field_count": 702,
                "public_benchmark_field_work_order_primary_field_name": "approval_token",
                "evidence_bundle_export_ready": True,
                "api_customer_flow_release_evidence_present": True,
                "api_customer_flow_release_evidence_ready": True,
                "api_customer_flow_release_evidence_status": "api_customer_flow_release_evidence_ready",
                "api_customer_flow_release_evidence_pass_count": 6,
                "api_customer_flow_release_evidence_blocker_count": 0,
                "api_customer_flow_tier_alpha_smoke_status": "tier_alpha_adrb2_dispatch_smoke_pass",
                "api_customer_flow_tier_alpha_runner_execution_ok": True,
                "api_customer_flow_result_manifest_signature_verified": True,
                "api_customer_flow_restricted_runtime_ready": True,
                "api_customer_flow_bundle_validation_ready": True,
                "customer_shadow_paid_pilot_evidence_ready": False,
                "customer_shadow_real_row_count": 1,
                "customer_shadow_completed_case_count": 0,
                "customer_shadow_required_case_count": 3,
                "customer_shadow_missing_case_count": 3,
                "customer_shadow_customer_retained_raw_data_count": 1,
                "customer_shadow_redistribution_allowed_false_count": 1,
                "customer_shadow_anonymized_result_summary_count": 1,
                "customer_shadow_reviewer_signoff_count": 0,
                "customer_shadow_evidence_blocker_count": 2,
                "customer_shadow_work_order_ready": False,
                "customer_shadow_work_order_row_count": 3,
                "customer_shadow_work_order_primary_case_slot_id": "customer_shadow_case_1",
                "customer_shadow_work_order_primary_required_action": (
                    "Add one reviewed real customer-shadow metadata row."
                ),
                "pm_priority_queue_present": True,
                "pm_priority_queue_status": "blocked_pm_priority_queue",
                "pm_priority_queue_ready_item_count": 3,
                "pm_priority_queue_blocked_item_count": 5,
                "pm_priority_queue_first_blocked_item_id": "2",
                "pm_priority_queue_first_blocker": "f2g_authoritative_surfaces_missing",
                "pm_priority_queue_next_required_step": (
                    "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
                ),
                "release_allowed": False,
                "next_required_step": "Keep claims locked.",
                "claim_boundary": "cockpit boundary",
            },
            "rows": [{"panel_id": "product_capabilities_dashboard", "route": "/product/capabilities"}],
            "claim_matrix": [{"claim_id": "paid_pilot_wording", "allowed": False}],
        },
    )

    response = asyncio.run(mod.get_product_operator_cockpit())

    assert response["status"] == "product_operator_cockpit_ready_claims_blocked"
    assert response["artifact_path"] == str(artifact)
    assert response["phase8_surface_ready"] is True
    assert response["required_phase8_panel_count"] == 9
    assert response["source_artifact_blocked_panel_ids"] == ["hbond_backmap_candidate_table"]
    assert response["paid_pilot_wording_allowed"] is False
    assert response["general_platform_claim_allowed"] is False
    assert response["gpcr_hard_decoy_metric_ready"] is True
    assert response["gpcr_broad_claim_allowed"] is False
    assert response["gpcr_phase3_closure_present"] is True
    assert response["gpcr_phase3_closure_evidence_ready"] is True
    assert response["gpcr_phase3_exit_metric_conditions_ready"] is True
    assert response["gpcr_phase3_broad_promotion_locked"] is True
    assert response["gpcr_phase3_effective_ranking_pr_auc_ci_low"] == 0.5597832604
    assert response["gpcr_phase3_effective_top20_hit_rate"] == 1.0
    assert response["gpcr_phase3_effective_decoys_above_positive_total"] == 0
    assert response["gpcr_phase3_effective_metric_source"] == "claim_unlock_audit"
    assert response["gpcr_phase3_promotion_blocker_count"] == 2
    assert response["gpcr_promotion_work_order_row_count"] == 2
    assert response["gpcr_promotion_work_order_lane_count"] == 2
    assert response["gpcr_promotion_work_order_primary_blocker"] == (
        "broad_scope:formal_broad_claim_review_not_approved"
    )
    assert response["pocketmd_lite_report_evidence_ready"] is False
    assert response["pocketmd_lite_fill_preview_evidence_ready"] is True
    assert response["pocketmd_lite_preview_requires_canonical_review"] is True
    assert response["public_benchmark_receipt_attach_packet_ready"] is False
    assert response["public_benchmark_receipt_attach_packet_present"] is True
    assert response["public_benchmark_vina_gnina_pending_score_count"] == 32
    assert response["public_benchmark_vina_gnina_pending_field_count"] == 192
    assert response["public_benchmark_metric_source_pending_field_count"] == 510
    assert response["public_benchmark_metric_source_pending_approval_token_count"] == 51
    assert response["public_benchmark_field_work_order_row_count"] == 22
    assert response["public_benchmark_field_work_order_pending_field_count"] == 702
    assert response["public_benchmark_field_work_order_primary_field_name"] == "approval_token"
    assert response["evidence_bundle_export_ready"] is True
    assert response["api_customer_flow_release_evidence_present"] is True
    assert response["api_customer_flow_release_evidence_ready"] is True
    assert response["api_customer_flow_release_evidence_status"] == "api_customer_flow_release_evidence_ready"
    assert response["api_customer_flow_release_evidence_pass_count"] == 6
    assert response["api_customer_flow_release_evidence_blocker_count"] == 0
    assert response["api_customer_flow_tier_alpha_smoke_status"] == "tier_alpha_adrb2_dispatch_smoke_pass"
    assert response["api_customer_flow_tier_alpha_runner_execution_ok"] is True
    assert response["api_customer_flow_result_manifest_signature_verified"] is True
    assert response["api_customer_flow_restricted_runtime_ready"] is True
    assert response["api_customer_flow_bundle_validation_ready"] is True
    assert response["customer_shadow_paid_pilot_evidence_ready"] is False
    assert response["customer_shadow_real_row_count"] == 1
    assert response["customer_shadow_completed_case_count"] == 0
    assert response["customer_shadow_required_case_count"] == 3
    assert response["customer_shadow_missing_case_count"] == 3
    assert response["customer_shadow_customer_retained_raw_data_count"] == 1
    assert response["customer_shadow_redistribution_allowed_false_count"] == 1
    assert response["customer_shadow_anonymized_result_summary_count"] == 1
    assert response["customer_shadow_reviewer_signoff_count"] == 0
    assert response["customer_shadow_evidence_blocker_count"] == 2
    assert response["customer_shadow_work_order_ready"] is False
    assert response["customer_shadow_work_order_row_count"] == 3
    assert response["customer_shadow_work_order_primary_case_slot_id"] == "customer_shadow_case_1"
    assert response["customer_shadow_work_order_primary_required_action"] == (
        "Add one reviewed real customer-shadow metadata row."
    )
    assert response["pm_priority_queue_present"] is True
    assert response["pm_priority_queue_status"] == "blocked_pm_priority_queue"
    assert response["pm_priority_queue_ready_item_count"] == 3
    assert response["pm_priority_queue_blocked_item_count"] == 5
    assert response["pm_priority_queue_first_blocked_item_id"] == "2"
    assert response["pm_priority_queue_first_blocker"] == "f2g_authoritative_surfaces_missing"
    assert response["pm_priority_queue_next_required_step"] == (
        "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
    )
    assert response["panels"][0]["panel_id"] == "product_capabilities_dashboard"
    assert response["claim_matrix"][0]["claim_id"] == "paid_pilot_wording"
    assert response["execution_enabled"] is False
    assert response["docking_results_emitted"] is False
    assert response["external_state_mutated"] is False
    assert response["claim_boundary"] == "cockpit boundary"


def test_product_operator_cockpit_endpoint_fails_closed_when_artifact_missing(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "runs/product_operator_cockpit_current.json"
    monkeypatch.setattr(mod, "PRODUCT_OPERATOR_COCKPIT_ARTIFACT", missing)

    response = asyncio.run(mod.get_product_operator_cockpit())

    assert response["status"] == "missing_product_operator_cockpit"
    assert response["phase8_surface_ready"] is False
    assert response["required_phase8_panel_count"] == 9
    assert response["observed_phase8_panel_count"] == 0
    assert response["paid_pilot_wording_allowed"] is False
    assert response["general_platform_claim_allowed"] is False
    assert response["gpcr_broad_claim_allowed"] is False
    assert response["gpcr_phase3_closure_present"] is False
    assert response["gpcr_phase3_closure_evidence_ready"] is False
    assert response["gpcr_phase3_exit_metric_conditions_ready"] is False
    assert response["gpcr_phase3_broad_promotion_locked"] is False
    assert response["gpcr_phase3_effective_ranking_pr_auc_ci_low"] == 0.0
    assert response["gpcr_phase3_effective_top20_hit_rate"] == 0.0
    assert response["gpcr_phase3_effective_decoys_above_positive_total"] == 0
    assert response["gpcr_phase3_effective_metric_source"] == ""
    assert response["gpcr_phase3_promotion_blocker_count"] == 0
    assert response["gpcr_promotion_work_order_row_count"] == 0
    assert response["gpcr_promotion_work_order_lane_count"] == 0
    assert response["gpcr_promotion_work_order_primary_blocker"] == ""
    assert response["pocketmd_lite_report_evidence_ready"] is False
    assert response["pocketmd_lite_fill_preview_evidence_ready"] is False
    assert response["pocketmd_lite_preview_requires_canonical_review"] is False
    assert response["pocketmd_lite_claim_allowed"] is False
    assert response["public_benchmark_claim_allowed"] is False
    assert response["public_benchmark_receipt_attach_packet_ready"] is False
    assert response["public_benchmark_receipt_attach_packet_present"] is False
    assert response["public_benchmark_vina_gnina_pending_score_count"] == 0
    assert response["public_benchmark_vina_gnina_pending_field_count"] == 0
    assert response["public_benchmark_metric_source_pending_field_count"] == 0
    assert response["public_benchmark_metric_source_pending_approval_token_count"] == 0
    assert response["public_benchmark_field_work_order_row_count"] == 0
    assert response["public_benchmark_field_work_order_pending_field_count"] == 0
    assert response["public_benchmark_field_work_order_primary_field_name"] == ""
    assert response["evidence_bundle_export_ready"] is False
    assert response["api_customer_flow_release_evidence_present"] is False
    assert response["api_customer_flow_release_evidence_ready"] is False
    assert response["api_customer_flow_release_evidence_status"] == ""
    assert response["api_customer_flow_release_evidence_pass_count"] == 0
    assert response["api_customer_flow_release_evidence_blocker_count"] == 0
    assert response["api_customer_flow_tier_alpha_smoke_status"] == ""
    assert response["api_customer_flow_tier_alpha_runner_execution_ok"] is False
    assert response["api_customer_flow_result_manifest_signature_verified"] is False
    assert response["api_customer_flow_restricted_runtime_ready"] is False
    assert response["api_customer_flow_bundle_validation_ready"] is False
    assert response["customer_shadow_paid_pilot_evidence_ready"] is False
    assert response["customer_shadow_real_row_count"] == 0
    assert response["customer_shadow_completed_case_count"] == 0
    assert response["customer_shadow_required_case_count"] == 0
    assert response["customer_shadow_missing_case_count"] == 0
    assert response["customer_shadow_customer_retained_raw_data_count"] == 0
    assert response["customer_shadow_redistribution_allowed_false_count"] == 0
    assert response["customer_shadow_anonymized_result_summary_count"] == 0
    assert response["customer_shadow_reviewer_signoff_count"] == 0
    assert response["customer_shadow_evidence_blocker_count"] == 0
    assert response["customer_shadow_work_order_ready"] is False
    assert response["customer_shadow_work_order_row_count"] == 0
    assert response["customer_shadow_work_order_primary_case_slot_id"] == ""
    assert response["customer_shadow_work_order_primary_required_action"] == ""
    assert response["pm_priority_queue_present"] is False
    assert response["pm_priority_queue_status"] == ""
    assert response["pm_priority_queue_ready_item_count"] == 0
    assert response["pm_priority_queue_blocked_item_count"] == 0
    assert response["pm_priority_queue_first_blocked_item_id"] == ""
    assert response["pm_priority_queue_first_blocker"] == ""
    assert response["pm_priority_queue_next_required_step"] == ""
    assert response["panels"] == []
    assert response["claim_matrix"] == []
    assert response["execution_enabled"] is False
    assert response["external_state_mutated"] is False
