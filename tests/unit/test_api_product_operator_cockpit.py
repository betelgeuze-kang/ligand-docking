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
    acceptance = tmp_path / ".betelgeuze/pr38_split_acceptance_packet_current.json"
    matrix = tmp_path / ".betelgeuze/pr38_child_pr_verification_matrix_current.json"
    monkeypatch.setattr(mod, "PRODUCT_OPERATOR_COCKPIT_ARTIFACT", artifact)
    monkeypatch.setattr(mod, "PR38_SPLIT_ACCEPTANCE_PACKET_ARTIFACT", acceptance)
    monkeypatch.setattr(mod, "PR38_CHILD_PR_VERIFICATION_MATRIX_ARTIFACT", matrix)
    _write_json(
        acceptance,
        {
            "summary": {
                "status": "pr38_split_acceptance_packet_ready",
                "split_acceptance_ready": True,
                "child_pr_count": 5,
                "ready_child_pr_count": 5,
                "blocked_child_pr_count": 0,
                "blocked_slice_ids": [],
                "hunk_split_review_required_count": 7,
                "product_mode_expected_result": "pass_product_smoke_claim_boundaries_locked",
                "product_mode_claim_boundary_expected_locks": [
                    "paid_pilot_wording_allowed=false",
                    "public_benchmark_claim_allowed=false",
                ],
                "paid_pilot_wording_allowed": False,
                "branch_commit_work_allowed_by_this_packet": False,
                "patches_applied": False,
                "branches_created": False,
                "next_required_step": "Request explicit human approval for branch/commit work.",
            }
        },
    )
    _write_json(
        matrix,
        {
            "summary": {
                "status": "pr38_child_pr_verification_matrix_ready",
                "verification_matrix_ready": True,
                "split_acceptance_ready": True,
                "child_pr_count": 5,
                "ready_child_pr_count": 5,
                "blocked_child_pr_count": 0,
                "blocked_slice_ids": [],
                "focused_test_required_count": 5,
                "ai_verify_required_count": 5,
                "product_mode_required_count": 5,
                "hunk_split_review_required_count": 2,
                "claim_boundary_review_required_count": 5,
                "product_mode_expected_result": "pass_product_smoke_claim_boundaries_locked",
                "product_mode_expected_fail_closed_blockers": [],
                "product_mode_claim_boundary_expected_locks": [
                    "paid_pilot_wording_allowed=false",
                    "public_benchmark_claim_allowed=false",
                ],
                "paid_pilot_wording_allowed": False,
                "branch_commit_work_allowed_by_this_matrix": False,
                "patches_applied": False,
                "branches_created": False,
                "next_required_step": "Run each row's focused test command and ai-verify.",
            },
            "rows": [
                {
                    "sequence": 1,
                    "slice_id": "f2g_f2h_preflight",
                    "changed_file_count": 5,
                    "integration_touchpoint_count": 0,
                    "hunk_split_review_required": False,
                    "focused_test_required": True,
                    "focused_test_command": "pytest f2g",
                    "ai_verify_required": True,
                    "ai_verify_command": "./scripts/ai-verify.sh",
                    "product_mode_required": True,
                    "product_mode_command": "AI_VERIFY_MODE=product ./scripts/ai-verify.sh",
                    "product_mode_expected_result": "pass_product_smoke_claim_boundaries_locked",
                    "claim_boundary_review_required": True,
                    "child_pr_verification_matrix_ready": True,
                    "verification_blockers": [],
                    "paid_pilot_wording_allowed": False,
                    "branch_commit_work_allowed_by_this_matrix": False,
                    "execution_enabled": False,
                    "external_state_mutated": False,
                },
                {
                    "sequence": 2,
                    "slice_id": "public_benchmark_phase2",
                    "changed_file_count": 14,
                    "integration_touchpoint_count": 0,
                    "hunk_split_review_required": False,
                    "focused_test_required": True,
                    "focused_test_command": "pytest benchmark",
                    "ai_verify_required": True,
                    "ai_verify_command": "./scripts/ai-verify.sh",
                    "product_mode_required": True,
                    "product_mode_command": "AI_VERIFY_MODE=product ./scripts/ai-verify.sh",
                    "product_mode_expected_result": "pass_product_smoke_claim_boundaries_locked",
                    "claim_boundary_review_required": True,
                    "child_pr_verification_matrix_ready": True,
                    "verification_blockers": [],
                    "paid_pilot_wording_allowed": False,
                    "branch_commit_work_allowed_by_this_matrix": False,
                    "execution_enabled": False,
                    "external_state_mutated": False,
                },
            ],
        },
    )
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
                "hbond_backmap_candidate_rows": [
                    {
                        "entry_id": "ADRB2::LIG-1",
                        "evidence_tier": "claim_safe",
                        "claim_safe": True,
                        "backmap_status": "ok",
                        "mapping_source": "rdkit_etkdg",
                        "site_count": 2,
                        "mapped_site_count": 2,
                        "donor_count": 1,
                        "acceptor_count": 1,
                        "max_onsps_sites": 4,
                        "polar_site_elements": ["N", "O"],
                        "hbond_angle_score": 0.75,
                        "two_bead_vs_four_bead_delta": None,
                        "reason_code": "",
                        "reason_detail": "",
                        "report_version": "hbond_backmap_report_v1",
                        "claim_boundary": "hbond interpretability only",
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    }
                ],
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
                "gpcr_promotion_work_order_rows": [
                    {
                        "lane_id": "active_scorer",
                        "blocker": "active_scorer:operational_gate_refresh_not_complete",
                        "required_action": (
                            "Refresh the active scorer operational gate and keep broad GPCR "
                            "promotion locked."
                        ),
                        "source_artifact": (
                            "runs/gpcr_active_scorer_promotion_decision_packet_current.json"
                        ),
                        "claim_boundary": (
                            "GPCR promotion work order only; no broad claim promotion."
                        ),
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    }
                ],
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
                "pocketmd_lite_claim_grade_metric_rows": [
                    {
                        "entry_id": "ADRB2_GPCR_BLIND:carvedilol",
                        "band": "green",
                        "uncertainty_posture": "green_low_uncertainty",
                        "uncertainty_score": 0.23,
                        "claim_grade_metric_ready": True,
                        "claim_safe": True,
                        "selected_for_refine": True,
                        "local_min_ligand_rmsd_a": 1.29,
                        "local_min_survived": True,
                        "hbond_persistence": 0.8,
                        "contact_persistence": 1.0,
                        "initial_clash_count": 57,
                        "final_clash_count": 0,
                        "clash_relief_count": 57,
                        "claim_grade_missing_metrics": [],
                        "blockers": [],
                        "trajectory_probe_status": (
                            "pocketmd_lite_metric_collection_probe_ready"
                        ),
                        "candidate_metric_fill_status": "filled_from_claim_grade_probe",
                        "recommended_next_local_action": "review_green_band_metrics",
                        "candidate_csv_update_allowed": True,
                        "refinement_execution_enabled": True,
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    }
                ],
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
                "public_benchmark_field_work_order_rows": [
                    {
                        "lane_id": "vina_gnina_same_input_scores",
                        "field_name": "approval_token",
                        "pending_row_count": 16,
                        "required_value": (
                            "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES for approval_token"
                        ),
                        "required_action": (
                            "Fill approval_token with APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES "
                            "after operator review."
                        ),
                        "approval_token_required": (
                            "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES"
                        ),
                        "operator_csv": (
                            "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
                        ),
                        "source_artifact": (
                            "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
                        ),
                        "claim_boundary": "same-input Vina/GNINA score receipt only",
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    }
                ],
                "public_benchmark_external_receipt_step_rows": [
                    {
                        "step_id": "vina_gnina_same_input_comparison",
                        "status": "blocked",
                        "ready": False,
                        "evidence_artifact": (
                            "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
                        ),
                        "primary_metric": "score_rows=0/16",
                        "secondary_metric": "pending_fields=192",
                        "blocker": "vina_gnina_same_input_score_evidence_missing",
                        "next_required_step": (
                            "Fill every score-template row with same-input Vina/GNINA scores."
                        ),
                        "claim_boundary": "public benchmark audit boundary",
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    }
                ],
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
                "evidence_bundle_export_row_count": 2,
                "evidence_bundle_export_blocker_row_count": 0,
                "evidence_bundle_export_required_missing_row_count": 0,
                "evidence_bundle_export_rows": [
                    {
                        "artifact_id": "ai_md_engine_kpi_report_json",
                        "role": "local_pc_runtime_report",
                        "artifact_path": "runs/ai_md_engine_kpi_report_current.json",
                        "bundle_arcname": "runs/ai_md_engine_kpi_report_current.json",
                        "required": True,
                        "exists": True,
                        "missing": False,
                        "included_in_bundle": True,
                        "release_blocker": False,
                        "sha256": "abc123",
                        "size_bytes": 143772,
                        "claim_boundary": "bundle fixture boundary",
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    },
                    {
                        "artifact_id": "optional_runtime_plot",
                        "role": "runtime_plot",
                        "artifact_path": "runs/ai_md_runtime_scaling_plot_current.svg",
                        "bundle_arcname": "runs/ai_md_runtime_scaling_plot_current.svg",
                        "required": False,
                        "exists": True,
                        "missing": False,
                        "included_in_bundle": True,
                        "release_blocker": False,
                        "sha256": "def456",
                        "size_bytes": 2048,
                        "claim_boundary": "plot artifact row boundary",
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    },
                ],
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
                "api_customer_flow_release_evidence_row_count": 2,
                "api_customer_flow_release_evidence_blocker_row_count": 0,
                "api_customer_flow_release_evidence_rows": [
                    {
                        "check_id": "tier_alpha_smoke_live_job_ready",
                        "status": "pass",
                        "release_blocker": False,
                        "artifact_path": "runs/tier_alpha_adrb2_dispatch_smoke_current.json",
                        "required": "tier alpha smoke pass",
                        "observed": "runner_execution_ok=True",
                        "reason": "prove the validated runner drained a restricted job",
                        "claim_boundary": "api customer flow fixture boundary",
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    },
                    {
                        "check_id": "bundle_validation_ready",
                        "status": "pass",
                        "release_blocker": False,
                        "artifact_path": (
                            "runs/product_bundle_contract_current.json;"
                            "runs/product_delivery_evidence_contract_current.json"
                        ),
                        "required": "bundle validation passed",
                        "observed": "bundle_validation=True;delivery_claim=True",
                        "reason": "customer flow terminates in validated bundle gates",
                        "claim_boundary": "bundle validation row boundary",
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    },
                ],
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
                "customer_shadow_work_order_rows": [
                    {
                        "work_order_id": "customer_shadow_case_slot_1",
                        "case_slot_id": "customer_shadow_case_1",
                        "status": "missing_customer_shadow_evidence",
                        "required_row_kind": "customer_shadow",
                        "operator_csv": "config/customer_shadow_evidence_intake_template.csv",
                        "required_action": "Add one reviewed real customer-shadow metadata row.",
                        "required_raw_data_custody": "customer_retained",
                        "required_customer_retained_raw_data": True,
                        "required_redistribution_allowed": False,
                        "required_raw_data_stored_in_repo": False,
                        "required_derived_metadata_fields": [
                            "artifact_fingerprint",
                            "case_domain",
                            "input_size_class",
                            "result_metric_summary",
                            "runner_profile",
                        ],
                        "required_reviewer_signoff_status": "approved",
                        "required_source_artifact_fingerprint": "sha256",
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    }
                ],
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
                "developer_preview_receipt_work_order_source_blocker_count": 7,
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
                "developer_preview_receipt_work_order_primary_source_blocker_gate_id": (
                    "benchmark_results_clean_checkout_regenerated"
                ),
                "developer_preview_receipt_work_order_primary_source_blocker_receipt_artifact": (
                    ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
                ),
                "developer_preview_receipt_work_order_primary_source_blocker": (
                    ".betelgeuze/developer_preview_clean_checkout_ai_verify.log:missing"
                ),
                "developer_preview_receipt_work_order_primary_source_blocker_required_action": (
                    "Attach the missing source evidence required by the receipt."
                ),
                "developer_preview_receipt_work_order_rows": [
                    {
                        "gate_id": "benchmark_results_clean_checkout_regenerated",
                        "priority": "A",
                        "receipt_artifact": (
                            ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
                        ),
                        "receipt_kind": "required",
                        "blocker_scope": "receipt_contract",
                        "blocker": (
                            ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:"
                            "status=blocked_developer_preview_clean_checkout_benchmark_receipt"
                        ),
                        "blocker_detail": (
                            "status=blocked_developer_preview_clean_checkout_benchmark_receipt"
                        ),
                        "required_action": (
                            "Rebuild the receipt after clearing its source blockers."
                        ),
                        "next_required_step": "Attach the clean-checkout benchmark receipt.",
                        "required_receipt_status": (
                            "developer_preview_clean_checkout_benchmark_receipt_ready"
                        ),
                        "required_true_field_count": 3,
                        "required_true_fields": [
                            "clean_checkout_benchmark_regenerated",
                            "ai_verify_passed",
                            "reviewed_receipt_attached",
                        ],
                        "required_zero_field_count": 2,
                        "required_zero_fields": ["blocker_count", "failed_count"],
                        "claim_boundary": "developer preview boundary",
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    }
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
                "enterprise_on_prem_control_rows": [
                    {
                        "control_id": "oidc_rbac_tenant_isolation",
                        "title": "OIDC/RBAC and tenant isolation",
                        "status": "blocked_oidc_rbac_not_verified",
                        "ready": False,
                        "blocker": "oidc_rbac_claim_grade_evidence_missing",
                        "next_action": (
                            "Add reviewed OIDC provider, RBAC role matrix, and tenant-isolation test receipts."
                        ),
                        "evidence": (
                            "auth_ready=true;tenant_isolation_ready=true;oidc_ready=false;rbac_ready=false"
                        ),
                        "evidence_artifacts": [
                            "runs/product_security_deployment_contract_current.json"
                        ],
                        "claim_allowed": True,
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    }
                ],
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
                "f2g_f2h_recovery_rows": [
                    {
                        "recovery_item_id": "restore_implementation_phase1_tree",
                        "preflight_check_id": "implementation_phase1_dir",
                        "status": "fail",
                        "required_surface": "implementation/phase1",
                        "observed": "missing",
                        "blocker": "implementation_phase1_dir_missing",
                        "operator_action": (
                            "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
                        ),
                        "acceptance_rule": (
                            "Directory exists in the checkout and is the reviewed implementation tree."
                        ),
                        "authoritative_source_hint": "Original F2/G1 implementation branch.",
                        "prohibited_actions": (
                            "do_not_create_placeholder_json;do_not_promote_g1"
                        ),
                        "audit_executed": True,
                        "continuation_executed": True,
                        "surface_restore_executed": True,
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                    }
                ],
                "pm_priority_queue_present": True,
                "pm_priority_queue_status": "blocked_pm_priority_queue",
                "pm_priority_queue_ready_item_count": 3,
                "pm_priority_queue_blocked_item_count": 5,
                "pm_priority_queue_first_blocked_item_id": "2",
                "pm_priority_queue_first_blocker": "f2g_authoritative_surfaces_missing",
                "pm_priority_queue_next_required_step": (
                    "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
                ),
                "release_operator_action_row_count": 1,
                "release_operator_action_primary_lane_id": "product_ai_production",
                "release_operator_action_primary_action_type": (
                    "complete_residual_registry_guarded_promotion"
                ),
                "release_operator_action_primary_status": "required",
                "release_operator_action_primary_approval_token": (
                    "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
                ),
                "release_operator_action_primary_required_input": (
                    "production_promotion_allowed;default_residual_mode"
                ),
                "release_operator_action_primary_command": (
                    "python3 tools/build_residual_model_registry.py && "
                    "python3 tools/build_product_production_ai_checkpoint_readiness.py"
                ),
                "release_operator_action_rows": [
                    {
                        "lane_id": "product_ai_production",
                        "action_type": "complete_residual_registry_guarded_promotion",
                        "status": "required",
                        "priority": 0,
                        "approval_token": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",
                        "required_input": "production_promotion_allowed;default_residual_mode",
                        "artifact_path": (
                            "runs/product_goal_completion_audit_current.json;"
                            "runs/residual_model_registry_current.json"
                        ),
                        "command": (
                            "python3 tools/build_residual_model_registry.py && "
                            "python3 tools/build_product_production_ai_checkpoint_readiness.py"
                        ),
                        "reason": "registry promotion gates are not satisfied",
                        "recommended_action": (
                            "Complete the guarded production AI registry promotion receipt."
                        ),
                        "operator_completion_artifact_id": (
                            "residual_model_registry_guarded_promotion"
                        ),
                        "operator_completion_completion_rule": (
                            "registry_promotion_missing_gate_count=0"
                        ),
                        "operator_completion_next_action": (
                            "Complete the guarded production AI registry promotion receipt."
                        ),
                        "operator_completion_required_fields_or_columns": (
                            "production_promotion_allowed;default_residual_mode"
                        ),
                        "parallelizable_with_primary_action": True,
                        "parallel_lane_precondition": "claim promotion remains locked",
                        "action_executed": True,
                        "delete_executed": True,
                        "execution_enabled": True,
                        "external_state_mutated": True,
                        "claim_promotion_allowed": True,
                        "claim_boundary": "unsafe fixture value should be preserved as text only",
                    }
                ],
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
    assert response["hbond_backmap_candidate_rows"] == [
        {
            "entry_id": "ADRB2::LIG-1",
            "evidence_tier": "claim_safe",
            "claim_safe": True,
            "backmap_status": "ok",
            "mapping_source": "rdkit_etkdg",
            "site_count": 2,
            "mapped_site_count": 2,
            "donor_count": 1,
            "acceptor_count": 1,
            "max_onsps_sites": 4,
            "polar_site_elements": ["N", "O"],
            "hbond_angle_score": 0.75,
            "two_bead_vs_four_bead_delta": None,
            "reason_code": "",
            "reason_detail": "",
            "report_version": "hbond_backmap_report_v1",
            "claim_boundary": "hbond interpretability only",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
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
    assert response["gpcr_promotion_work_order_rows"] == [
        {
            "lane_id": "active_scorer",
            "blocker": "active_scorer:operational_gate_refresh_not_complete",
            "required_action": (
                "Refresh the active scorer operational gate and keep broad GPCR promotion locked."
            ),
            "source_artifact": "runs/gpcr_active_scorer_promotion_decision_packet_current.json",
            "claim_boundary": "GPCR promotion work order only; no broad claim promotion.",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
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
    assert response["pocketmd_lite_claim_grade_metric_rows"] == [
        {
            "entry_id": "ADRB2_GPCR_BLIND:carvedilol",
            "band": "green",
            "uncertainty_posture": "green_low_uncertainty",
            "uncertainty_score": 0.23,
            "claim_grade_metric_ready": True,
            "claim_safe": True,
            "selected_for_refine": True,
            "local_min_ligand_rmsd_a": 1.29,
            "local_min_survived": True,
            "hbond_persistence": 0.8,
            "contact_persistence": 1.0,
            "initial_clash_count": 57,
            "final_clash_count": 0,
            "clash_relief_count": 57,
            "claim_grade_missing_metrics": [],
            "blockers": [],
            "trajectory_probe_status": "pocketmd_lite_metric_collection_probe_ready",
            "candidate_metric_fill_status": "filled_from_claim_grade_probe",
            "recommended_next_local_action": "review_green_band_metrics",
            "candidate_csv_update_allowed": False,
            "refinement_execution_enabled": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
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
    assert response["public_benchmark_field_work_order_rows"] == [
        {
            "lane_id": "vina_gnina_same_input_scores",
            "field_name": "approval_token",
            "pending_row_count": 16,
            "required_value": (
                "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES for approval_token"
            ),
            "required_action": (
                "Fill approval_token with APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES "
                "after operator review."
            ),
            "approval_token_required": "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES",
            "operator_csv": "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
            "source_artifact": "runs/public_benchmark_vina_gnina_score_template_receipt_current.json",
            "claim_boundary": "same-input Vina/GNINA score receipt only",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
    assert response["public_benchmark_external_receipt_step_rows"] == [
        {
            "step_id": "vina_gnina_same_input_comparison",
            "status": "blocked",
            "ready": False,
            "evidence_artifact": (
                "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
            ),
            "primary_metric": "score_rows=0/16",
            "secondary_metric": "pending_fields=192",
            "blocker": "vina_gnina_same_input_score_evidence_missing",
            "next_required_step": (
                "Fill every score-template row with same-input Vina/GNINA scores."
            ),
            "claim_boundary": "public benchmark audit boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
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
    assert response["evidence_bundle_export_row_count"] == 2
    assert response["evidence_bundle_export_blocker_row_count"] == 0
    assert response["evidence_bundle_export_required_missing_row_count"] == 0
    assert response["evidence_bundle_export_rows"] == [
        {
            "artifact_id": "ai_md_engine_kpi_report_json",
            "role": "local_pc_runtime_report",
            "artifact_path": "runs/ai_md_engine_kpi_report_current.json",
            "bundle_arcname": "runs/ai_md_engine_kpi_report_current.json",
            "required": True,
            "exists": True,
            "missing": False,
            "included_in_bundle": True,
            "release_blocker": False,
            "sha256": "abc123",
            "size_bytes": 143772,
            "claim_boundary": "bundle fixture boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
        {
            "artifact_id": "optional_runtime_plot",
            "role": "runtime_plot",
            "artifact_path": "runs/ai_md_runtime_scaling_plot_current.svg",
            "bundle_arcname": "runs/ai_md_runtime_scaling_plot_current.svg",
            "required": False,
            "exists": True,
            "missing": False,
            "included_in_bundle": True,
            "release_blocker": False,
            "sha256": "def456",
            "size_bytes": 2048,
            "claim_boundary": "plot artifact row boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
    ]
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
    assert response["api_customer_flow_release_evidence_row_count"] == 2
    assert response["api_customer_flow_release_evidence_blocker_row_count"] == 0
    assert response["api_customer_flow_release_evidence_rows"] == [
        {
            "check_id": "tier_alpha_smoke_live_job_ready",
            "status": "pass",
            "release_blocker": False,
            "artifact_path": "runs/tier_alpha_adrb2_dispatch_smoke_current.json",
            "required": "tier alpha smoke pass",
            "observed": "runner_execution_ok=True",
            "reason": "prove the validated runner drained a restricted job",
            "claim_boundary": "api customer flow fixture boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
        {
            "check_id": "bundle_validation_ready",
            "status": "pass",
            "release_blocker": False,
            "artifact_path": (
                "runs/product_bundle_contract_current.json;"
                "runs/product_delivery_evidence_contract_current.json"
            ),
            "required": "bundle validation passed",
            "observed": "bundle_validation=True;delivery_claim=True",
            "reason": "customer flow terminates in validated bundle gates",
            "claim_boundary": "bundle validation row boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
    ]
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
    assert response["customer_shadow_work_order_rows"] == [
        {
            "work_order_id": "customer_shadow_case_slot_1",
            "case_slot_id": "customer_shadow_case_1",
            "status": "missing_customer_shadow_evidence",
            "required_row_kind": "customer_shadow",
            "operator_csv": "config/customer_shadow_evidence_intake_template.csv",
            "required_action": "Add one reviewed real customer-shadow metadata row.",
            "required_raw_data_custody": "customer_retained",
            "required_customer_retained_raw_data": True,
            "required_redistribution_allowed": False,
            "required_raw_data_stored_in_repo": False,
            "required_derived_metadata_fields": [
                "artifact_fingerprint",
                "case_domain",
                "input_size_class",
                "result_metric_summary",
                "runner_profile",
            ],
            "required_reviewer_signoff_status": "approved",
            "required_source_artifact_fingerprint": "sha256",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
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
    assert response["developer_preview_receipt_work_order_source_blocker_count"] == 7
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
    assert response["developer_preview_receipt_work_order_primary_source_blocker_gate_id"] == (
        "benchmark_results_clean_checkout_regenerated"
    )
    assert response[
        "developer_preview_receipt_work_order_primary_source_blocker_receipt_artifact"
    ] == ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
    assert response["developer_preview_receipt_work_order_primary_source_blocker"] == (
        ".betelgeuze/developer_preview_clean_checkout_ai_verify.log:missing"
    )
    assert response[
        "developer_preview_receipt_work_order_primary_source_blocker_required_action"
    ] == "Attach the missing source evidence required by the receipt."
    assert response["developer_preview_receipt_work_order_rows"] == [
        {
            "gate_id": "benchmark_results_clean_checkout_regenerated",
            "priority": "A",
            "receipt_artifact": ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
            "receipt_kind": "required",
            "blocker_scope": "receipt_contract",
            "blocker": (
                ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:"
                "status=blocked_developer_preview_clean_checkout_benchmark_receipt"
            ),
            "blocker_detail": "status=blocked_developer_preview_clean_checkout_benchmark_receipt",
            "required_action": "Rebuild the receipt after clearing its source blockers.",
            "next_required_step": "Attach the clean-checkout benchmark receipt.",
            "required_receipt_status": "developer_preview_clean_checkout_benchmark_receipt_ready",
            "required_true_field_count": 3,
            "required_true_fields": [
                "clean_checkout_benchmark_regenerated",
                "ai_verify_passed",
                "reviewed_receipt_attached",
            ],
            "required_zero_field_count": 2,
            "required_zero_fields": ["blocker_count", "failed_count"],
            "claim_boundary": "developer preview boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
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
    assert response["enterprise_on_prem_control_rows"] == [
        {
            "control_id": "oidc_rbac_tenant_isolation",
            "title": "OIDC/RBAC and tenant isolation",
            "status": "blocked_oidc_rbac_not_verified",
            "ready": False,
            "blocker": "oidc_rbac_claim_grade_evidence_missing",
            "next_action": (
                "Add reviewed OIDC provider, RBAC role matrix, and tenant-isolation test receipts."
            ),
            "evidence": "auth_ready=true;tenant_isolation_ready=true;oidc_ready=false;rbac_ready=false",
            "evidence_artifacts": ["runs/product_security_deployment_contract_current.json"],
            "claim_allowed": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
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
    assert response["f2g_f2h_recovery_rows"] == [
        {
            "recovery_item_id": "restore_implementation_phase1_tree",
            "preflight_check_id": "implementation_phase1_dir",
            "status": "fail",
            "required_surface": "implementation/phase1",
            "observed": "missing",
            "blocker": "implementation_phase1_dir_missing",
            "operator_action": (
                "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
            ),
            "acceptance_rule": "Directory exists in the checkout and is the reviewed implementation tree.",
            "authoritative_source_hint": "Original F2/G1 implementation branch.",
            "prohibited_actions": "do_not_create_placeholder_json;do_not_promote_g1",
            "audit_executed": False,
            "continuation_executed": False,
            "surface_restore_executed": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
    assert response["pm_priority_queue_present"] is True
    assert response["pm_priority_queue_status"] == "blocked_pm_priority_queue"
    assert response["pm_priority_queue_ready_item_count"] == 3
    assert response["pm_priority_queue_blocked_item_count"] == 5
    assert response["pm_priority_queue_first_blocked_item_id"] == "2"
    assert response["pm_priority_queue_first_blocker"] == "f2g_authoritative_surfaces_missing"
    assert response["pm_priority_queue_next_required_step"] == (
        "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
    )
    assert response["release_operator_action_row_count"] == 1
    assert response["release_operator_action_primary_lane_id"] == "product_ai_production"
    assert (
        response["release_operator_action_primary_action_type"]
        == "complete_residual_registry_guarded_promotion"
    )
    assert response["release_operator_action_primary_status"] == "required"
    assert (
        response["release_operator_action_primary_approval_token"]
        == "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
    )
    assert (
        response["release_operator_action_primary_required_input"]
        == "production_promotion_allowed;default_residual_mode"
    )
    assert "tools/build_residual_model_registry.py" in (
        response["release_operator_action_primary_command"]
    )
    assert response["release_operator_action_rows"] == [
        {
            "lane_id": "product_ai_production",
            "action_type": "complete_residual_registry_guarded_promotion",
            "status": "required",
            "priority": 0,
            "approval_token": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",
            "required_input": "production_promotion_allowed;default_residual_mode",
            "artifact_path": (
                "runs/product_goal_completion_audit_current.json;"
                "runs/residual_model_registry_current.json"
            ),
            "command": (
                "python3 tools/build_residual_model_registry.py && "
                "python3 tools/build_product_production_ai_checkpoint_readiness.py"
            ),
            "reason": "registry promotion gates are not satisfied",
            "recommended_action": (
                "Complete the guarded production AI registry promotion receipt."
            ),
            "operator_completion_artifact_id": (
                "residual_model_registry_guarded_promotion"
            ),
            "operator_completion_completion_rule": (
                "registry_promotion_missing_gate_count=0"
            ),
            "operator_completion_next_action": (
                "Complete the guarded production AI registry promotion receipt."
            ),
            "operator_completion_required_fields_or_columns": (
                "production_promotion_allowed;default_residual_mode"
            ),
            "parallelizable_with_primary_action": True,
            "parallel_lane_precondition": "claim promotion remains locked",
            "action_executed": False,
            "delete_executed": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
            "claim_boundary": "unsafe fixture value should be preserved as text only",
        }
    ]
    assert response["pr38_split_acceptance_present"] is True
    assert response["pr38_split_acceptance_status"] == "pr38_split_acceptance_packet_ready"
    assert response["pr38_split_acceptance_ready"] is True
    assert response["pr38_child_pr_verification_matrix_present"] is True
    assert response["pr38_child_pr_verification_matrix_status"] == (
        "pr38_child_pr_verification_matrix_ready"
    )
    assert response["pr38_child_pr_verification_matrix_ready"] is True
    assert response["pr38_split_ready_for_human_branch_approval"] is True
    assert response["pr38_operator_branch_approval_required"] is True
    assert response["pr38_child_pr_count"] == 5
    assert response["pr38_ready_child_pr_count"] == 5
    assert response["pr38_blocked_child_pr_count"] == 0
    assert response["pr38_blocked_slice_ids"] == []
    assert response["pr38_focused_test_required_count"] == 5
    assert response["pr38_ai_verify_required_count"] == 5
    assert response["pr38_product_mode_required_count"] == 5
    assert response["pr38_hunk_split_review_required_count"] == 2
    assert response["pr38_claim_boundary_review_required_count"] == 5
    assert response["pr38_product_mode_expected_result"] == (
        "pass_product_smoke_claim_boundaries_locked"
    )
    assert response["pr38_product_mode_expected_fail_closed_blockers"] == []
    assert response["pr38_product_mode_claim_boundary_expected_locks"] == [
        "paid_pilot_wording_allowed=false",
        "public_benchmark_claim_allowed=false",
    ]
    assert response["pr38_paid_pilot_wording_allowed"] is False
    assert response["pr38_branch_commit_work_allowed"] is False
    assert response["pr38_patches_applied"] is False
    assert response["pr38_branches_created"] is False
    assert response["pr38_next_slice_id"] == "f2g_f2h_preflight"
    assert response["pr38_next_focused_test_command"] == "pytest f2g"
    assert response["pr38_next_ai_verify_command"] == "./scripts/ai-verify.sh"
    assert response["pr38_next_required_step"] == "Run each row's focused test command and ai-verify."
    assert response["pr38_verification_rows"][0] == {
        "sequence": 1,
        "slice_id": "f2g_f2h_preflight",
        "changed_file_count": 5,
        "integration_touchpoint_count": 0,
        "hunk_split_review_required": False,
        "focused_test_required": True,
        "focused_test_command": "pytest f2g",
        "ai_verify_required": True,
        "ai_verify_command": "./scripts/ai-verify.sh",
        "product_mode_required": True,
        "product_mode_command": "AI_VERIFY_MODE=product ./scripts/ai-verify.sh",
        "product_mode_expected_result": "pass_product_smoke_claim_boundaries_locked",
        "claim_boundary_review_required": True,
        "child_pr_verification_matrix_ready": True,
        "verification_blockers": [],
        "paid_pilot_wording_allowed": False,
        "branch_commit_work_allowed_by_this_matrix": False,
        "execution_enabled": False,
        "external_state_mutated": False,
    }
    assert response["panels"][0]["panel_id"] == "product_capabilities_dashboard"
    assert response["claim_matrix"][0]["claim_id"] == "paid_pilot_wording"
    assert response["execution_enabled"] is False
    assert response["docking_results_emitted"] is False
    assert response["external_state_mutated"] is False
    assert response["claim_boundary"] == "cockpit boundary"


def test_product_operator_cockpit_endpoint_fails_closed_when_artifact_missing(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "runs/product_operator_cockpit_current.json"
    monkeypatch.setattr(mod, "PRODUCT_OPERATOR_COCKPIT_ARTIFACT", missing)
    monkeypatch.setattr(
        mod,
        "PR38_SPLIT_ACCEPTANCE_PACKET_ARTIFACT",
        tmp_path / ".betelgeuze/missing-pr38-split.json",
    )
    monkeypatch.setattr(
        mod,
        "PR38_CHILD_PR_VERIFICATION_MATRIX_ARTIFACT",
        tmp_path / ".betelgeuze/missing-pr38-matrix.json",
    )

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
    assert response["hbond_backmap_candidate_rows"] == []
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
    assert response["gpcr_promotion_work_order_rows"] == []
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
    assert response["pocketmd_lite_claim_grade_metric_rows"] == []
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
    assert response["public_benchmark_field_work_order_rows"] == []
    assert response["public_benchmark_external_receipt_step_rows"] == []
    assert response["public_benchmark_primary_blocker_id"] == ""
    assert response["public_benchmark_primary_blocker"] == ""
    assert response["public_benchmark_primary_next_required_step"] == ""
    assert response["public_benchmark_vina_gnina_score_template_csv"] == ""
    assert response["public_benchmark_vina_gnina_score_template_receipt_json"] == ""
    assert response["public_benchmark_metric_source_receipt_csv"] == ""
    assert response["public_benchmark_vina_gnina_adapter_command_after_fill"] == ""
    assert response["evidence_bundle_export_ready"] is False
    assert response["evidence_bundle_export_row_count"] == 0
    assert response["evidence_bundle_export_blocker_row_count"] == 0
    assert response["evidence_bundle_export_required_missing_row_count"] == 0
    assert response["evidence_bundle_export_rows"] == []
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
    assert response["api_customer_flow_release_evidence_row_count"] == 0
    assert response["api_customer_flow_release_evidence_blocker_row_count"] == 0
    assert response["api_customer_flow_release_evidence_rows"] == []
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
    assert response["customer_shadow_work_order_rows"] == []
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
    assert response["developer_preview_receipt_work_order_source_blocker_count"] == 0
    assert response["developer_preview_receipt_work_order_primary_source_blocker_gate_id"] == ""
    assert response[
        "developer_preview_receipt_work_order_primary_source_blocker_receipt_artifact"
    ] == ""
    assert response["developer_preview_receipt_work_order_primary_source_blocker"] == ""
    assert response[
        "developer_preview_receipt_work_order_primary_source_blocker_required_action"
    ] == ""
    assert response["developer_preview_receipt_work_order_rows"] == []
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
    assert response["enterprise_on_prem_control_rows"] == []
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
    assert response["f2g_f2h_recovery_rows"] == []
    assert response["pm_priority_queue_present"] is False
    assert response["pm_priority_queue_status"] == ""
    assert response["pm_priority_queue_ready_item_count"] == 0
    assert response["pm_priority_queue_blocked_item_count"] == 0
    assert response["pm_priority_queue_first_blocked_item_id"] == ""
    assert response["pm_priority_queue_first_blocker"] == ""
    assert response["pm_priority_queue_next_required_step"] == ""
    assert response["release_operator_action_row_count"] == 0
    assert response["release_operator_action_primary_lane_id"] == ""
    assert response["release_operator_action_primary_action_type"] == ""
    assert response["release_operator_action_primary_status"] == ""
    assert response["release_operator_action_primary_approval_token"] == ""
    assert response["release_operator_action_primary_required_input"] == ""
    assert response["release_operator_action_primary_command"] == ""
    assert response["release_operator_action_rows"] == []
    assert response["pr38_split_acceptance_present"] is False
    assert response["pr38_split_acceptance_status"] == ""
    assert response["pr38_split_acceptance_ready"] is False
    assert response["pr38_child_pr_verification_matrix_present"] is False
    assert response["pr38_child_pr_verification_matrix_status"] == ""
    assert response["pr38_child_pr_verification_matrix_ready"] is False
    assert response["pr38_split_ready_for_human_branch_approval"] is False
    assert response["pr38_operator_branch_approval_required"] is False
    assert response["pr38_child_pr_count"] == 0
    assert response["pr38_ready_child_pr_count"] == 0
    assert response["pr38_blocked_child_pr_count"] == 0
    assert response["pr38_blocked_slice_ids"] == []
    assert response["pr38_focused_test_required_count"] == 0
    assert response["pr38_ai_verify_required_count"] == 0
    assert response["pr38_product_mode_required_count"] == 0
    assert response["pr38_hunk_split_review_required_count"] == 0
    assert response["pr38_claim_boundary_review_required_count"] == 0
    assert response["pr38_product_mode_expected_result"] == ""
    assert response["pr38_product_mode_expected_fail_closed_blockers"] == []
    assert response["pr38_product_mode_claim_boundary_expected_locks"] == []
    assert response["pr38_paid_pilot_wording_allowed"] is False
    assert response["pr38_branch_commit_work_allowed"] is False
    assert response["pr38_patches_applied"] is False
    assert response["pr38_branches_created"] is False
    assert response["pr38_next_slice_id"] == ""
    assert response["pr38_next_focused_test_command"] == ""
    assert response["pr38_next_ai_verify_command"] == ""
    assert response["pr38_next_required_step"] == ""
    assert response["pr38_verification_rows"] == []
    assert response["panels"] == []
    assert response["claim_matrix"] == []
    assert response["execution_enabled"] is False
    assert response["external_state_mutated"] is False
