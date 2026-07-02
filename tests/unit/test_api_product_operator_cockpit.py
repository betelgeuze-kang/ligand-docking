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
                "allowed_claim_ids": [
                    "operator_cockpit_surface",
                    "restricted_scope_claim_guard",
                    "gpcr_hard_decoy_metric_review",
                    "evidence_bundle_export",
                ],
                "disallowed_claim_ids": [
                    "paid_pilot_wording",
                    "general_platform_claim",
                    "broad_gpcr_claim",
                    "pocketmd_lite_customer_claim",
                    "public_benchmark_claim",
                    "enterprise_on_prem_platform_claim",
                ],
                "allowed_claim_text": (
                    "operator_cockpit_surface; restricted_scope_claim_guard; "
                    "gpcr_hard_decoy_metric_review; evidence_bundle_export"
                ),
                "disallowed_claim_text": (
                    "paid_pilot_wording; general_platform_claim; broad_gpcr_claim; "
                    "pocketmd_lite_customer_claim; public_benchmark_claim; "
                    "enterprise_on_prem_platform_claim"
                ),
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
                "pocketmd_lite_claim_grade_metric_ready_row_count": 2,
                "pocketmd_lite_local_min_ligand_rmsd_a_max": 1.29,
                "pocketmd_lite_hbond_persistence_min": 0.8,
                "pocketmd_lite_contact_persistence_min": 0.9,
                "pocketmd_lite_initial_clash_count_total": 79,
                "pocketmd_lite_final_clash_count_total": 1,
                "pocketmd_lite_clash_relief_count_total": 78,
                "pocketmd_lite_green_band_condition_text": (
                    "green requires local-min RMSD, hbond/contact persistence, and clash relief."
                ),
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
                "public_benchmark_field_work_order_primary_lane_id": "vina_gnina_same_input_scores",
                "public_benchmark_field_work_order_primary_pending_row_count": 16,
                "public_benchmark_field_work_order_primary_required_value": (
                    "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES for approval_token"
                ),
                "public_benchmark_field_work_order_primary_required_action": (
                    "Fill approval_token with APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES "
                    "after operator review."
                ),
                "public_benchmark_field_work_order_primary_approval_token_required": (
                    "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES"
                ),
                "public_benchmark_field_work_order_primary_operator_csv": (
                    "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
                ),
                "public_benchmark_field_work_order_primary_source_artifact": (
                    "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
                ),
                "public_benchmark_primary_blocker_id": "vina_gnina_same_input_scores",
                "public_benchmark_primary_blocker": "vina_gnina_same_input_score_evidence_missing",
                "public_benchmark_primary_next_required_step": (
                    "Fill every score-template row, then rebuild the receipt."
                ),
                "public_benchmark_vina_gnina_score_template_csv": (
                    "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
                ),
                "public_benchmark_vina_gnina_score_template_receipt_json": (
                    "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
                ),
                "public_benchmark_metric_source_receipt_csv": (
                    "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
                ),
                "public_benchmark_vina_gnina_adapter_command_after_fill": (
                    "python3 tools/build_pdbbind_casf_pose_affinity_results.py --comparison-scores-csv "
                    "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
                ),
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
                "customer_shadow_work_order_primary_operator_csv": (
                    "config/customer_shadow_evidence_intake_template.csv"
                ),
                "customer_shadow_work_order_primary_required_row_kind": "customer_shadow",
                "customer_shadow_work_order_primary_required_raw_data_custody": "customer_retained",
                "customer_shadow_work_order_primary_required_customer_retained_raw_data": True,
                "customer_shadow_work_order_primary_required_redistribution_allowed": False,
                "customer_shadow_work_order_primary_required_raw_data_stored_in_repo": False,
                "customer_shadow_work_order_primary_required_derived_metadata_fields": [
                    "artifact_fingerprint",
                    "case_domain",
                    "input_size_class",
                    "result_metric_summary",
                    "runner_profile",
                ],
                "customer_shadow_work_order_primary_required_reviewer_signoff_status": "approved",
                "customer_shadow_work_order_primary_required_source_artifact_fingerprint": "sha256",
                "customer_shadow_intake_schema_ready": True,
                "customer_shadow_minimum_met": False,
                "customer_shadow_raw_data_stored_in_repo": False,
                "customer_shadow_invalid_row_count": 0,
                "customer_shadow_mock_fixture_row_count": 0,
                "customer_shadow_required_column_count": 12,
                "customer_shadow_redistribution_allowed_required_value": False,
                "developer_preview_clean_baseline_ready": False,
                "developer_preview_gate_count": 6,
                "developer_preview_ready_gate_count": 3,
                "developer_preview_blocked_gate_count": 3,
                "developer_preview_receipt_work_order_row_count": 29,
                "developer_preview_receipt_blocker_count": 12,
                "developer_preview_primary_blocker_id": "benchmark_results_clean_checkout_regenerated",
                "developer_preview_receipt_work_order_primary_gate_id": (
                    "benchmark_results_clean_checkout_regenerated"
                ),
                "developer_preview_receipt_work_order_primary_receipt_artifact": (
                    ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
                ),
                "developer_preview_receipt_work_order_primary_required_receipt_status": (
                    "developer_preview_clean_checkout_benchmark_receipt_ready"
                ),
                "developer_preview_receipt_work_order_primary_required_true_fields": [
                    "clean_checkout_benchmark_regenerated",
                    "ai_verify_passed",
                    "reviewed_receipt_attached",
                ],
                "developer_preview_receipt_work_order_primary_required_zero_fields": [
                    "blocker_count",
                    "failed_count",
                ],
                "enterprise_on_prem_readiness_present": True,
                "enterprise_on_prem_ready": False,
                "enterprise_on_prem_claim_allowed": False,
                "enterprise_on_prem_control_count": 10,
                "enterprise_on_prem_ready_control_count": 4,
                "enterprise_on_prem_blocked_control_count": 6,
                "enterprise_on_prem_primary_blocker_id": "oidc_rbac_tenant_isolation",
                "enterprise_on_prem_primary_blocker": "oidc_rbac_claim_grade_evidence_missing",
                "enterprise_on_prem_next_required_step": (
                    "Add reviewed OIDC provider, RBAC role matrix, and tenant-isolation test receipts."
                ),
                "enterprise_on_prem_oidc_rbac_ready": False,
                "enterprise_on_prem_object_storage_ready": False,
                "enterprise_on_prem_gpu_scheduler_ready": False,
                "enterprise_on_prem_audit_provenance_metrics_tracing_ready": False,
                "enterprise_on_prem_license_control_ready": True,
                "enterprise_on_prem_support_bundle_recovery_drill_ready": False,
                "enterprise_on_prem_rollback_retry_idempotency_ready": True,
                "f2g_f2h_preflight_present": True,
                "f2g_f2h_recovery_packet_present": True,
                "f2g_f2h_preflight_status": "blocked_f2g_f2h_surface_preflight",
                "f2g_f2h_recovery_status": "f2g_f2h_authoritative_surface_recovery_packet_ready",
                "f2g_f2h_recovery_required": True,
                "f2g_f2h_preflight_blocker_count": 8,
                "f2g_f2h_blocked_recovery_item_count": 8,
                "f2g_f2h_recovery_item_count": 8,
                "f2g_f2h_primary_recovery_item_id": "restore_implementation_phase1_tree",
                "f2g_f2h_primary_required_surface": "implementation/phase1",
                "f2g_f2h_primary_blocker": "implementation_phase1_dir_missing",
                "f2g_f2h_primary_operator_action": (
                    "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
                ),
                "f2g_f2h_audit_ready": False,
                "f2h_continuation_allowed": False,
                "f2g_f2h_placeholder_surface_creation_allowed": False,
                "f2g_f2h_surface_restore_executed": False,
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
    assert response["allowed_claim_count"] == 4
    assert response["disallowed_claim_count"] == 6
    assert response["allowed_claim_ids"] == [
        "operator_cockpit_surface",
        "restricted_scope_claim_guard",
        "gpcr_hard_decoy_metric_review",
        "evidence_bundle_export",
    ]
    assert response["disallowed_claim_ids"] == [
        "paid_pilot_wording",
        "general_platform_claim",
        "broad_gpcr_claim",
        "pocketmd_lite_customer_claim",
        "public_benchmark_claim",
        "enterprise_on_prem_platform_claim",
    ]
    assert response["allowed_claim_text"] == (
        "operator_cockpit_surface; restricted_scope_claim_guard; "
        "gpcr_hard_decoy_metric_review; evidence_bundle_export"
    )
    assert response["disallowed_claim_text"] == (
        "paid_pilot_wording; general_platform_claim; broad_gpcr_claim; "
        "pocketmd_lite_customer_claim; public_benchmark_claim; "
        "enterprise_on_prem_platform_claim"
    )
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
    assert response["pocketmd_lite_claim_grade_metric_ready_row_count"] == 2
    assert response["pocketmd_lite_local_min_ligand_rmsd_a_max"] == 1.29
    assert response["pocketmd_lite_hbond_persistence_min"] == 0.8
    assert response["pocketmd_lite_contact_persistence_min"] == 0.9
    assert response["pocketmd_lite_initial_clash_count_total"] == 79
    assert response["pocketmd_lite_final_clash_count_total"] == 1
    assert response["pocketmd_lite_clash_relief_count_total"] == 78
    assert response["pocketmd_lite_green_band_condition_text"] == (
        "green requires local-min RMSD, hbond/contact persistence, and clash relief."
    )
    assert response["public_benchmark_receipt_attach_packet_ready"] is False
    assert response["public_benchmark_receipt_attach_packet_present"] is True
    assert response["public_benchmark_vina_gnina_pending_score_count"] == 32
    assert response["public_benchmark_vina_gnina_pending_field_count"] == 192
    assert response["public_benchmark_metric_source_pending_field_count"] == 510
    assert response["public_benchmark_metric_source_pending_approval_token_count"] == 51
    assert response["public_benchmark_field_work_order_row_count"] == 22
    assert response["public_benchmark_field_work_order_pending_field_count"] == 702
    assert response["public_benchmark_field_work_order_primary_field_name"] == "approval_token"
    assert response["public_benchmark_field_work_order_primary_lane_id"] == (
        "vina_gnina_same_input_scores"
    )
    assert response["public_benchmark_field_work_order_primary_pending_row_count"] == 16
    assert response["public_benchmark_field_work_order_primary_required_value"] == (
        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES for approval_token"
    )
    assert response["public_benchmark_field_work_order_primary_required_action"] == (
        "Fill approval_token with APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES "
        "after operator review."
    )
    assert response["public_benchmark_field_work_order_primary_approval_token_required"] == (
        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES"
    )
    assert response["public_benchmark_field_work_order_primary_operator_csv"] == (
        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    )
    assert response["public_benchmark_field_work_order_primary_source_artifact"] == (
        "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
    )
    assert response["public_benchmark_primary_blocker_id"] == "vina_gnina_same_input_scores"
    assert response["public_benchmark_primary_blocker"] == (
        "vina_gnina_same_input_score_evidence_missing"
    )
    assert response["public_benchmark_primary_next_required_step"] == (
        "Fill every score-template row, then rebuild the receipt."
    )
    assert response["public_benchmark_vina_gnina_score_template_csv"] == (
        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    )
    assert response["public_benchmark_vina_gnina_score_template_receipt_json"] == (
        "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
    )
    assert response["public_benchmark_metric_source_receipt_csv"] == (
        "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
    )
    assert response["public_benchmark_vina_gnina_adapter_command_after_fill"] == (
        "python3 tools/build_pdbbind_casf_pose_affinity_results.py --comparison-scores-csv "
        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    )
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
    assert response["customer_shadow_work_order_primary_operator_csv"] == (
        "config/customer_shadow_evidence_intake_template.csv"
    )
    assert response["customer_shadow_work_order_primary_required_row_kind"] == "customer_shadow"
    assert response["customer_shadow_work_order_primary_required_raw_data_custody"] == "customer_retained"
    assert response["customer_shadow_work_order_primary_required_customer_retained_raw_data"] is True
    assert response["customer_shadow_work_order_primary_required_redistribution_allowed"] is False
    assert response["customer_shadow_work_order_primary_required_raw_data_stored_in_repo"] is False
    assert response["customer_shadow_work_order_primary_required_derived_metadata_fields"] == [
        "artifact_fingerprint",
        "case_domain",
        "input_size_class",
        "result_metric_summary",
        "runner_profile",
    ]
    assert response["customer_shadow_work_order_primary_required_reviewer_signoff_status"] == "approved"
    assert response["customer_shadow_work_order_primary_required_source_artifact_fingerprint"] == "sha256"
    assert response["customer_shadow_intake_schema_ready"] is True
    assert response["customer_shadow_minimum_met"] is False
    assert response["customer_shadow_raw_data_stored_in_repo"] is False
    assert response["customer_shadow_invalid_row_count"] == 0
    assert response["customer_shadow_mock_fixture_row_count"] == 0
    assert response["customer_shadow_required_column_count"] == 12
    assert response["customer_shadow_redistribution_allowed_required_value"] is False
    assert response["developer_preview_clean_baseline_ready"] is False
    assert response["developer_preview_gate_count"] == 6
    assert response["developer_preview_ready_gate_count"] == 3
    assert response["developer_preview_blocked_gate_count"] == 3
    assert response["developer_preview_receipt_work_order_row_count"] == 29
    assert response["developer_preview_receipt_blocker_count"] == 12
    assert response["developer_preview_primary_blocker_id"] == (
        "benchmark_results_clean_checkout_regenerated"
    )
    assert response["developer_preview_receipt_work_order_primary_gate_id"] == (
        "benchmark_results_clean_checkout_regenerated"
    )
    assert response["developer_preview_receipt_work_order_primary_receipt_artifact"] == (
        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
    )
    assert response["developer_preview_receipt_work_order_primary_required_receipt_status"] == (
        "developer_preview_clean_checkout_benchmark_receipt_ready"
    )
    assert response["developer_preview_receipt_work_order_primary_required_true_fields"] == [
        "clean_checkout_benchmark_regenerated",
        "ai_verify_passed",
        "reviewed_receipt_attached",
    ]
    assert response["developer_preview_receipt_work_order_primary_required_zero_fields"] == [
        "blocker_count",
        "failed_count",
    ]
    assert response["enterprise_on_prem_readiness_present"] is True
    assert response["enterprise_on_prem_ready"] is False
    assert response["enterprise_on_prem_claim_allowed"] is False
    assert response["enterprise_on_prem_control_count"] == 10
    assert response["enterprise_on_prem_ready_control_count"] == 4
    assert response["enterprise_on_prem_blocked_control_count"] == 6
    assert response["enterprise_on_prem_primary_blocker_id"] == "oidc_rbac_tenant_isolation"
    assert response["enterprise_on_prem_primary_blocker"] == (
        "oidc_rbac_claim_grade_evidence_missing"
    )
    assert response["enterprise_on_prem_oidc_rbac_ready"] is False
    assert response["enterprise_on_prem_object_storage_ready"] is False
    assert response["enterprise_on_prem_gpu_scheduler_ready"] is False
    assert response["enterprise_on_prem_audit_provenance_metrics_tracing_ready"] is False
    assert response["enterprise_on_prem_license_control_ready"] is True
    assert response["enterprise_on_prem_support_bundle_recovery_drill_ready"] is False
    assert response["enterprise_on_prem_rollback_retry_idempotency_ready"] is True
    assert response["f2g_f2h_preflight_present"] is True
    assert response["f2g_f2h_recovery_packet_present"] is True
    assert response["f2g_f2h_preflight_status"] == "blocked_f2g_f2h_surface_preflight"
    assert response["f2g_f2h_recovery_status"] == (
        "f2g_f2h_authoritative_surface_recovery_packet_ready"
    )
    assert response["f2g_f2h_recovery_required"] is True
    assert response["f2g_f2h_preflight_blocker_count"] == 8
    assert response["f2g_f2h_blocked_recovery_item_count"] == 8
    assert response["f2g_f2h_recovery_item_count"] == 8
    assert response["f2g_f2h_primary_recovery_item_id"] == "restore_implementation_phase1_tree"
    assert response["f2g_f2h_primary_required_surface"] == "implementation/phase1"
    assert response["f2g_f2h_primary_blocker"] == "implementation_phase1_dir_missing"
    assert response["f2g_f2h_primary_operator_action"] == (
        "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
    )
    assert response["f2g_f2h_audit_ready"] is False
    assert response["f2h_continuation_allowed"] is False
    assert response["f2g_f2h_placeholder_surface_creation_allowed"] is False
    assert response["f2g_f2h_surface_restore_executed"] is False
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
    assert response["allowed_claim_count"] == 0
    assert response["disallowed_claim_count"] == 0
    assert response["allowed_claim_ids"] == []
    assert response["disallowed_claim_ids"] == []
    assert response["allowed_claim_text"] == ""
    assert response["disallowed_claim_text"] == ""
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
    assert response["pocketmd_lite_claim_grade_metric_ready_row_count"] == 0
    assert response["pocketmd_lite_local_min_ligand_rmsd_a_max"] == 0.0
    assert response["pocketmd_lite_hbond_persistence_min"] == 0.0
    assert response["pocketmd_lite_contact_persistence_min"] == 0.0
    assert response["pocketmd_lite_initial_clash_count_total"] == 0.0
    assert response["pocketmd_lite_final_clash_count_total"] == 0.0
    assert response["pocketmd_lite_clash_relief_count_total"] == 0.0
    assert response["pocketmd_lite_green_band_condition_text"] == ""
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
    assert response["public_benchmark_field_work_order_primary_lane_id"] == ""
    assert response["public_benchmark_field_work_order_primary_pending_row_count"] == 0
    assert response["public_benchmark_field_work_order_primary_required_value"] == ""
    assert response["public_benchmark_field_work_order_primary_required_action"] == ""
    assert response["public_benchmark_field_work_order_primary_approval_token_required"] == ""
    assert response["public_benchmark_field_work_order_primary_operator_csv"] == ""
    assert response["public_benchmark_field_work_order_primary_source_artifact"] == ""
    assert response["public_benchmark_primary_blocker_id"] == ""
    assert response["public_benchmark_primary_blocker"] == ""
    assert response["public_benchmark_primary_next_required_step"] == ""
    assert response["public_benchmark_vina_gnina_score_template_csv"] == ""
    assert response["public_benchmark_vina_gnina_score_template_receipt_json"] == ""
    assert response["public_benchmark_metric_source_receipt_csv"] == ""
    assert response["public_benchmark_vina_gnina_adapter_command_after_fill"] == ""
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
    assert response["customer_shadow_work_order_primary_operator_csv"] == ""
    assert response["customer_shadow_work_order_primary_required_row_kind"] == ""
    assert response["customer_shadow_work_order_primary_required_raw_data_custody"] == ""
    assert response["customer_shadow_work_order_primary_required_customer_retained_raw_data"] is False
    assert response["customer_shadow_work_order_primary_required_redistribution_allowed"] is False
    assert response["customer_shadow_work_order_primary_required_raw_data_stored_in_repo"] is False
    assert response["customer_shadow_work_order_primary_required_derived_metadata_fields"] == []
    assert response["customer_shadow_work_order_primary_required_reviewer_signoff_status"] == ""
    assert response["customer_shadow_work_order_primary_required_source_artifact_fingerprint"] == ""
    assert response["customer_shadow_intake_schema_ready"] is False
    assert response["customer_shadow_minimum_met"] is False
    assert response["customer_shadow_raw_data_stored_in_repo"] is False
    assert response["customer_shadow_invalid_row_count"] == 0
    assert response["customer_shadow_mock_fixture_row_count"] == 0
    assert response["customer_shadow_required_column_count"] == 0
    assert response["customer_shadow_redistribution_allowed_required_value"] is False
    assert response["developer_preview_clean_baseline_ready"] is False
    assert response["developer_preview_gate_count"] == 0
    assert response["developer_preview_ready_gate_count"] == 0
    assert response["developer_preview_blocked_gate_count"] == 0
    assert response["developer_preview_receipt_work_order_row_count"] == 0
    assert response["developer_preview_receipt_blocker_count"] == 0
    assert response["developer_preview_primary_blocker_id"] == ""
    assert response["developer_preview_receipt_work_order_primary_gate_id"] == ""
    assert response["developer_preview_receipt_work_order_primary_receipt_artifact"] == ""
    assert response["developer_preview_receipt_work_order_primary_required_receipt_status"] == ""
    assert response["developer_preview_receipt_work_order_primary_required_true_fields"] == []
    assert response["developer_preview_receipt_work_order_primary_required_zero_fields"] == []
    assert response["enterprise_on_prem_readiness_present"] is False
    assert response["enterprise_on_prem_ready"] is False
    assert response["enterprise_on_prem_claim_allowed"] is False
    assert response["enterprise_on_prem_control_count"] == 0
    assert response["enterprise_on_prem_ready_control_count"] == 0
    assert response["enterprise_on_prem_blocked_control_count"] == 0
    assert response["enterprise_on_prem_primary_blocker_id"] == ""
    assert response["enterprise_on_prem_primary_blocker"] == ""
    assert response["enterprise_on_prem_next_required_step"] == ""
    assert response["enterprise_on_prem_oidc_rbac_ready"] is False
    assert response["enterprise_on_prem_object_storage_ready"] is False
    assert response["enterprise_on_prem_gpu_scheduler_ready"] is False
    assert response["enterprise_on_prem_audit_provenance_metrics_tracing_ready"] is False
    assert response["enterprise_on_prem_license_control_ready"] is False
    assert response["enterprise_on_prem_support_bundle_recovery_drill_ready"] is False
    assert response["enterprise_on_prem_rollback_retry_idempotency_ready"] is False
    assert response["f2g_f2h_preflight_present"] is False
    assert response["f2g_f2h_recovery_packet_present"] is False
    assert response["f2g_f2h_preflight_status"] == ""
    assert response["f2g_f2h_recovery_status"] == ""
    assert response["f2g_f2h_recovery_required"] is False
    assert response["f2g_f2h_preflight_blocker_count"] == 0
    assert response["f2g_f2h_blocked_recovery_item_count"] == 0
    assert response["f2g_f2h_recovery_item_count"] == 0
    assert response["f2g_f2h_primary_recovery_item_id"] == ""
    assert response["f2g_f2h_primary_required_surface"] == ""
    assert response["f2g_f2h_primary_blocker"] == ""
    assert response["f2g_f2h_primary_operator_action"] == ""
    assert response["f2g_f2h_audit_ready"] is False
    assert response["f2h_continuation_allowed"] is False
    assert response["f2g_f2h_placeholder_surface_creation_allowed"] is False
    assert response["f2g_f2h_surface_restore_executed"] is False
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
