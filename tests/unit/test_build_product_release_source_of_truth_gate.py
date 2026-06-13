from __future__ import annotations

import json
import os
from pathlib import Path

from tools.product import build_product_release_source_of_truth_gate as mod
from tools.product import run_product_release_current_refresh as refresh_mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _accuracy_payload() -> dict:
    return {
        "summary": {
            "status": "green",
            "row_count": 5,
            "pass_row_count": 4,
            "restricted_pass_row_count": 1,
            "blocked_row_count": 0,
            "missing_row_count": 0,
        }
    }


def _last_refresh_index(command: str) -> int:
    return len(mod.RELEASE_REFRESH_COMMANDS) - 1 - list(
        reversed(mod.RELEASE_REFRESH_COMMANDS)
    ).index(command)


def _refresh_release_decision_ready() -> dict:
    return {
        "summary": {
            "status": "goal_release_ready",
            "release_allowed": True,
            "blocker_count": 0,
            "cameo_official_result_fetch_preflight_recorded": True,
            "cameo_official_result_fetch_preflight_network_request_opened": False,
            "cameo_official_result_fetch_preflight_official_results_fetched": False,
            "cameo_official_result_fetch_preflight_native_local_accuracy_used": False,
            "cameo_official_result_fetch_preflight_outbound_email_enabled": False,
            "cameo_official_result_fetch_preflight_external_state_mutated": False,
            "self_hosted_license_distribution_audit_recorded": True,
            "self_hosted_license_distribution_audit_product_license_hash_matches_approved_source": True,
            "self_hosted_license_distribution_audit_third_party_license_review_gate_ready": True,
            "self_hosted_license_distribution_audit_hard_blocker_count": 0,
            "self_hosted_license_distribution_audit_legal_advice_provided": False,
            "self_hosted_license_distribution_audit_third_party_license_review_gate_blocker_count": 0,
            "self_hosted_license_distribution_audit_external_state_mutated": False,
            "third_party_license_review_gate_recorded": True,
            "third_party_license_review_gate_ready": True,
            "third_party_license_review_gate_blocker_count": 0,
            "third_party_license_review_gate_missing_review_asset_count": 0,
            "third_party_license_review_gate_deferred_review_asset_count": 0,
            "third_party_license_review_gate_legal_advice_provided": False,
            "third_party_license_review_gate_asset_modified": False,
            "third_party_license_review_gate_external_state_mutated": False,
            "goal_bottleneck_briefing_full_commercial_receipts_recorded": True,
            "goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded": True,
            "goal_bottleneck_briefing_production_ai_registry_promotion_priority_packet_ready": True,
            "production_ai_registry_promotion_priority_packet_recorded": True,
            "production_ai_registry_promotion_priority_packet_ready": True,
            "production_ai_checkpoint_readiness_recorded": True,
            "production_ai_checkpoint_readiness_product_model_layer_ready": True,
            "production_ai_checkpoint_readiness_production_gpu_execution_environment_ready": True,
            "production_ai_checkpoint_readiness_delta_force_derivation_validation_ready": True,
            "production_ai_checkpoint_readiness_selected_sidecar_ready": True,
            "production_ai_checkpoint_readiness_checkpoint_preflight_ready": True,
            "production_ai_checkpoint_readiness_production_training_data_ready": True,
            "production_ai_checkpoint_readiness_production_output_heads_complete": True,
            "production_ai_checkpoint_readiness_production_inference_acceptance_matrix_ready": True,
            "production_ai_checkpoint_readiness_registry_promotion_upstream_acceptance_ready": True,
            "production_ai_checkpoint_readiness_production_ai_checkpoint_ready": False,
            "production_ai_checkpoint_readiness_production_ai_inference_subject_active": False,
            "production_ai_checkpoint_readiness_registry_promotion_currently_satisfied": False,
            "production_ai_checkpoint_readiness_production_promotion_allowed": False,
            "production_ai_checkpoint_readiness_customer_facing_auto_correction_allowed": False,
            "production_ai_checkpoint_readiness_customer_facing_score_mutation_allowed": False,
            "production_ai_checkpoint_readiness_customer_facing_ranking_mutation_allowed": False,
            "production_ai_checkpoint_readiness_model_promoted": False,
            "production_ai_checkpoint_readiness_docking_results_emitted": False,
            "production_ai_checkpoint_readiness_execution_enabled": False,
            "production_ai_checkpoint_readiness_external_state_mutated": False,
            "production_ai_promotion_workbench_recorded": True,
            "production_ai_promotion_workbench_ready": True,
            "production_ai_promotion_workbench_registry_promotion_upstream_acceptance_ready": True,
            "production_ai_promotion_workbench_production_ai_promotion_ready": False,
            "production_ai_promotion_workbench_production_ai_checkpoint_ready": False,
            "production_ai_promotion_workbench_production_ai_inference_subject_active": False,
            "production_ai_promotion_workbench_registry_promotion_currently_satisfied": False,
            "production_ai_promotion_workbench_production_promotion_allowed": False,
            "production_ai_promotion_workbench_model_promoted": False,
            "production_ai_promotion_workbench_docking_results_emitted": False,
            "production_ai_promotion_workbench_execution_enabled": False,
            "production_ai_promotion_workbench_external_state_mutated": False,
            "accuracy_parity_scorecard_recorded": True,
            "master_gap_closure_rollup_recorded": True,
            "master_gap_closure_rollup_all_gaps_closed": False,
            "master_gap_closure_rollup_claim_promotion_allowed": False,
            "master_gap_closure_rollup_science_claim_release_blocker": True,
            "science_claim_promotion_gap_closure_recorded": True,
            "science_claim_promotion_gap_closure_all_gaps_closed": False,
            "science_claim_promotion_gap_closure_claim_promotion_allowed": False,
            "science_claim_promotion_gap_closure_gpcr_release_blocker": True,
            "science_claim_promotion_gap_closure_openmm_release_blocker": True,
            "api_runner_profile_promotion_operator_receipt_recorded": True,
            "product_scope_breadth_evidence_receipt_recorded": True,
            "engine_refinement_claim_evidence_receipt_recorded": True,
            "engine_refinement_claim_evidence_priority_packet_recorded": True,
            "engine_refinement_claim_evidence_priority_packet_ready": True,
            "source_goal_bottleneck_briefing_status": "goal_bottleneck_briefing_ready",
            "goal_bottleneck_briefing_completion_audit_release_blocker_bottleneck_count": 2,
            "goal_bottleneck_briefing_full_commercial_evidence_receipt_entry_count": 2,
            "goal_bottleneck_briefing_full_commercial_evidence_receipt_operator_input_required_count": 2,
            "goal_bottleneck_briefing_full_commercial_evidence_receipt_current_action_required_count": 2,
            "goal_bottleneck_briefing_full_commercial_evidence_receipt_template_required_count": 2,
            "goal_bottleneck_briefing_full_commercial_evidence_receipt_template_present_count": 2,
            "goal_bottleneck_briefing_full_commercial_evidence_receipt_approval_token_count": 2,
            "goal_bottleneck_briefing_production_ai_registry_promotion_priority_operator_input_required_count": 3,
            "goal_bottleneck_briefing_production_ai_registry_promotion_priority_blocked_priority_item_count": 3,
            "goal_bottleneck_briefing_production_ai_registry_promotion_priority_missing_gate_count": 3,
            "production_ai_registry_promotion_priority_required_gate_count": 4,
            "production_ai_registry_promotion_priority_priority_item_count": 4,
            "production_ai_registry_promotion_priority_operator_input_required_count": 3,
            "production_ai_registry_promotion_priority_blocked_priority_item_count": 3,
            "production_ai_registry_promotion_priority_missing_gate_count": 3,
            "production_ai_registry_promotion_priority_approval_token_count": 1,
            "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count": 1,
            "production_ai_checkpoint_readiness_check_count": 8,
            "production_ai_checkpoint_readiness_pass_check_count": 7,
            "production_ai_checkpoint_readiness_fail_check_count": 1,
            "production_ai_checkpoint_readiness_production_inference_acceptance_stage_count": 8,
            "production_ai_checkpoint_readiness_production_inference_acceptance_ready_stage_count": 7,
            "production_ai_checkpoint_readiness_production_inference_acceptance_blocked_stage_count": 1,
            "production_ai_checkpoint_readiness_registry_promotion_missing_gate_count": 3,
            "production_ai_checkpoint_readiness_candidate_checkpoint_count": 1,
            "production_ai_checkpoint_readiness_ready_checkpoint_count": 1,
            "production_ai_checkpoint_readiness_trained_model_checkpoint_count": 1,
            "production_ai_promotion_workbench_post_return_ladder_stage_count": 10,
            "production_ai_promotion_workbench_post_return_ladder_ready_stage_count": 8,
            "production_ai_promotion_workbench_post_return_ladder_blocked_stage_count": 2,
            "production_ai_promotion_workbench_registry_promotion_missing_gate_count": 3,
            "production_ai_promotion_workbench_candidate_checkpoint_count": 1,
            "production_ai_promotion_workbench_ready_checkpoint_count": 1,
            "production_ai_promotion_workbench_trained_model_checkpoint_count": 1,
            "accuracy_parity_scorecard_row_count": 5,
            "accuracy_parity_scorecard_pass_row_count": 4,
            "accuracy_parity_scorecard_blocked_row_count": 1,
            "accuracy_parity_scorecard_top_blocker_count": 4,
            "accuracy_parity_ligand_ranking_blocker_count": 4,
            "accuracy_parity_ligand_ranking_positive_count": 13,
            "api_runner_profile_promotion_operator_receipt_profile_count": 4,
            "api_runner_profile_promotion_operator_receipt_receipt_row_count": 4,
            "api_runner_profile_promotion_operator_receipt_pass_row_count": 0,
            "api_runner_profile_promotion_operator_receipt_blocked_row_count": 4,
            "api_runner_profile_promotion_operator_receipt_blocker_count": 1,
            "product_scope_breadth_evidence_receipt_receipt_row_count": 6,
            "product_scope_breadth_evidence_receipt_pass_row_count": 0,
            "product_scope_breadth_evidence_receipt_blocked_row_count": 6,
            "product_scope_breadth_evidence_receipt_blocker_count": 1,
            "product_scope_breadth_evidence_receipt_required_scope_blocker_count": 6,
            "engine_refinement_claim_evidence_receipt_receipt_row_count": 6,
            "engine_refinement_claim_evidence_receipt_pass_row_count": 0,
            "engine_refinement_claim_evidence_receipt_blocked_row_count": 6,
            "engine_refinement_claim_evidence_receipt_blocker_count": 1,
            "engine_refinement_claim_evidence_receipt_required_blocker_count": 6,
            "engine_refinement_claim_evidence_priority_packet_priority_item_count": 6,
            "engine_refinement_claim_evidence_priority_packet_operator_input_required_count": 6,
            "engine_refinement_claim_evidence_priority_packet_blocked_priority_item_count": 6,
            "engine_refinement_claim_evidence_priority_packet_required_blocker_count": 6,
            "engine_refinement_claim_evidence_priority_packet_missing_required_blocker_count": 0,
            "engine_refinement_claim_evidence_priority_packet_blocker_count": 1,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_work_order_row_count": 8,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_work_order_apply_blocked_row_count": 8,
            "engine_refinement_claim_evidence_priority_packet_approval_token_count": 1,
            "cameo_official_result_fetch_preflight_blocked_row_count": 1,
            "cameo_official_result_fetch_preflight_blocker_count": 2,
            "cameo_official_result_fetch_preflight_awaiting_operator_fetch_approval_row_count": 1,
            "self_hosted_license_distribution_audit_operator_review_item_count": 1,
            "third_party_license_review_gate_expected_review_asset_count": 1,
            "third_party_license_review_gate_review_row_count": 1,
            "third_party_license_review_gate_approved_review_asset_count": 1,
            "third_party_license_review_gate_source_hard_blocker_count": 0,
            "third_party_license_review_gate_source_operator_review_item_count": 1,
            "master_gap_closure_rollup_open_gap_count": 1,
            "master_gap_closure_rollup_closed_gap_count": 8,
            "master_gap_closure_rollup_release_blocker_row_count": 1,
            "science_claim_promotion_gap_closure_open_gap_count": 2,
            "science_claim_promotion_gap_closure_closed_gap_count": 3,
            "science_claim_promotion_gap_closure_release_blocker_row_count": 2,
            "goal_bottleneck_briefing_full_commercial_evidence_receipt_source_gate_statuses": (
                "product_scope_breadth_evidence_receipt=blocked_product_scope_breadth_evidence_receipt;"
                "engine_refinement_claim_evidence_receipt=blocked_engine_refinement_claim_evidence_receipt"
            ),
            "goal_bottleneck_briefing_full_commercial_evidence_receipt_required_inputs": (
                "config/product_scope_breadth_evidence_receipt_current.csv;"
                "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
            ),
            "goal_bottleneck_briefing_full_commercial_evidence_receipt_approval_tokens": (
                "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT;"
                "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
            ),
            "goal_bottleneck_briefing_production_ai_registry_promotion_priority_source_json": (
                "runs/production_ai_registry_promotion_priority_packet_current.json"
            ),
            "goal_bottleneck_briefing_production_ai_registry_promotion_priority_status": (
                "blocked_production_ai_registry_promotion_priority_packet"
            ),
            "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_gate_id": (
                "default_residual_mode_guarded"
            ),
            "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_priority_bucket": (
                "guarded_residual_mode_selection_required"
            ),
            "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_acceptance_artifact": (
                "runs/residual_model_registry_current.json"
            ),
            "production_ai_registry_promotion_priority_packet_status": (
                "blocked_production_ai_registry_promotion_priority_packet"
            ),
            "production_ai_registry_promotion_priority_top_gate_id": (
                "default_residual_mode_guarded"
            ),
            "production_ai_registry_promotion_priority_top_priority_bucket": (
                "guarded_residual_mode_selection_required"
            ),
            "production_ai_registry_promotion_priority_top_acceptance_artifact": (
                "runs/residual_model_registry_current.json"
            ),
            "production_ai_registry_promotion_priority_approval_token_required": (
                "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
            ),
            "production_ai_registry_promotion_priority_operator_receipt_artifact": (
                "runs/production_ai_registry_promotion_operator_receipt_current.json"
            ),
            "production_ai_registry_promotion_priority_operator_receipt_csv": (
                "config/production_ai_registry_promotion_operator_receipt_current.csv"
            ),
            "production_ai_registry_promotion_priority_operator_receipt_status": (
                "blocked_production_ai_registry_promotion_operator_receipt"
            ),
            "production_ai_registry_promotion_priority_observed_registry_default_residual_mode": (
                "shadow"
            ),
            "production_ai_checkpoint_readiness_status": (
                "blocked_product_production_ai_checkpoint_readiness"
            ),
            "production_ai_checkpoint_readiness_production_inference_acceptance_blocked_stage_ids": (
                "registry_guarded_promotion_acceptance"
            ),
            "production_ai_checkpoint_readiness_first_failed_check_id": (
                "registry_customer_facing_promotion_allowed"
            ),
            "production_ai_checkpoint_readiness_first_failed_source_artifact": (
                "runs/residual_model_registry_current.json"
            ),
            "production_ai_checkpoint_readiness_actionable_blocker_stage_id": (
                "registry_guarded_promotion_acceptance"
            ),
            "production_ai_checkpoint_readiness_actionable_blocker_check_id": (
                "registry_customer_facing_promotion_allowed"
            ),
            "production_ai_checkpoint_readiness_actionable_blocker_artifact": (
                "runs/residual_model_registry_current.json"
            ),
            "production_ai_checkpoint_readiness_registry_promotion_missing_gate_ids": (
                "production_promotion_allowed;customer_facing_mutation_flags;"
                "default_residual_mode_guarded"
            ),
            "production_ai_checkpoint_readiness_default_residual_mode": "shadow",
            "production_ai_promotion_workbench_status": (
                "blocked_product_production_ai_promotion_workbench"
            ),
            "production_ai_promotion_workbench_checkpoint_readiness_artifact_path": (
                "runs/product_production_ai_checkpoint_readiness_current.json"
            ),
            "production_ai_promotion_workbench_blocked_stage_ids": (
                "residual_model_registry;product_goal_completion_audit"
            ),
            "production_ai_promotion_workbench_first_blocked_stage_id": (
                "residual_model_registry"
            ),
            "production_ai_promotion_workbench_first_blocked_stage_artifact": (
                "runs/residual_model_registry_current.json"
            ),
            "production_ai_promotion_workbench_first_blocked_stage_ready_key": (
                "production_promotion_allowed"
            ),
            "production_ai_promotion_workbench_registry_promotion_missing_gate_ids": (
                "production_promotion_allowed;customer_facing_mutation_flags;"
                "default_residual_mode_guarded"
            ),
            "production_ai_promotion_workbench_default_residual_mode": "shadow",
            "cameo_official_result_fetch_preflight_status": (
                "blocked_cameo_official_result_fetch_preflight"
            ),
            "cameo_official_result_fetch_preflight_operator_fetch_csv": (
                "runs/cameo_official_result_fetch_operator_approval_intake.csv"
            ),
            "cameo_official_result_fetch_preflight_operator_template_csv": (
                "runs/cameo_official_result_fetch_operator_approval_template_current.csv"
            ),
            "cameo_official_result_fetch_preflight_fetch_approval_token_required": (
                "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH"
            ),
            "self_hosted_license_distribution_audit_status": (
                "self_hosted_license_distribution_audit_recorded"
            ),
            "self_hosted_license_distribution_audit_product_license_path": "LICENSE",
            "self_hosted_license_distribution_audit_approved_license_text_source": "LICENSE",
            "self_hosted_license_distribution_audit_spdx_license_id": (
                "ProprietaryRef-Betelgeuze"
            ),
            "self_hosted_license_distribution_audit_copyright_holder": "JIHOON KANG",
            "self_hosted_license_distribution_audit_third_party_license_review_gate_status": (
                "third_party_license_review_gate_ready"
            ),
            "self_hosted_license_distribution_audit_third_party_dual_license_assets": "jszip",
            "self_hosted_license_distribution_audit_viewer_third_party_notice_path": (
                "viewer/vendor/THIRD_PARTY_NOTICES.md"
            ),
            "third_party_license_review_gate_status": "third_party_license_review_gate_ready",
            "third_party_license_review_gate_approved_assets": "jszip",
            "third_party_license_review_gate_allowed_license_paths": (
                "GPL-3.0-or-later;MIT;remove_or_replace_asset"
            ),
            "third_party_license_review_gate_review_csv": (
                "runs/third_party_license_review_operator_intake.csv"
            ),
            "third_party_license_review_gate_operator_template_csv": (
                "runs/third_party_license_review_operator_template_current.csv"
            ),
            "third_party_license_review_gate_approval_token_required": (
                "APPROVE_THIRD_PARTY_LICENSE_REVIEW"
            ),
            "third_party_license_review_gate_source_license_audit_status": (
                "self_hosted_license_distribution_audit_recorded"
            ),
            "accuracy_parity_scorecard_status": "blocked_accuracy_parity",
            "accuracy_parity_scorecard_current_broad_accuracy_parity_estimate_pct": "40-50",
            "accuracy_parity_scorecard_current_broad_commercial_platform_estimate_pct": "35-45",
            "accuracy_parity_ligand_ranking_status": "blocked",
            "accuracy_parity_ligand_ranking_score_col_used": (
                "binding_score_composite_v7_residual_active"
            ),
            "master_gap_closure_rollup_status": "blocked_master_gap_closure_rollup",
            "master_gap_closure_rollup_open_gap_ids_joined": "SCI-CLAIM",
            "master_gap_closure_rollup_closed_gap_ids_joined": (
                "COMMERCIAL;PRODUCT-AI;DATA-SCIENCE;INFRA;DEPLOY-OPS;STORAGE;TOOLS;API-RUNNER"
            ),
            "master_gap_closure_rollup_current_primary_open_gap_id": "SCI-CLAIM",
            "master_gap_closure_rollup_science_claim_rollup_status": (
                "blocked_science_claim_promotion_gap_closure"
            ),
            "master_gap_closure_rollup_science_claim_evidence": (
                "runs/science_claim_promotion_gap_closure_current.json"
            ),
            "api_runner_profile_promotion_operator_receipt_status": (
                "blocked_api_runner_profile_promotion_operator_receipt"
            ),
            "api_runner_profile_promotion_operator_receipt_readiness_status": (
                "api_runner_profile_promotion_ready"
            ),
            "api_runner_profile_promotion_operator_receipt_first_blocked_profile_id": (
                "backmapping_scoring.example"
            ),
            "api_runner_profile_promotion_operator_receipt_first_blocked_row_blocker": (
                "operator_decision_missing"
            ),
            "api_runner_profile_promotion_operator_receipt_approval_token_required": (
                "APPROVE_API_RUNNER_PROFILE_PROMOTION"
            ),
            "product_scope_breadth_evidence_receipt_status": (
                "blocked_product_scope_breadth_evidence_receipt"
            ),
            "product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id": (
                "direct_binding_evidence_missing"
            ),
            "product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact": (
                "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
            ),
            "product_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status": (
                "missing"
            ),
            "product_scope_breadth_evidence_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "product_scope_breadth_evidence_receipt_approval_token_required": (
                "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
            ),
            "engine_refinement_claim_evidence_receipt_status": (
                "blocked_engine_refinement_claim_evidence_receipt"
            ),
            "engine_refinement_claim_evidence_receipt_first_blocked_blocker_id": (
                "public_benchmark_gate_not_ready"
            ),
            "engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact": (
                "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
            ),
            "engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status": (
                "missing"
            ),
            "engine_refinement_claim_evidence_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "engine_refinement_claim_evidence_receipt_approval_token_required": (
                "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
            ),
            "engine_refinement_claim_evidence_priority_packet_status": (
                "blocked_engine_refinement_claim_evidence_priority_packet"
            ),
            "engine_refinement_claim_evidence_priority_packet_claim_evidence_receipt_status": (
                "blocked_engine_refinement_claim_evidence_receipt"
            ),
            "engine_refinement_claim_evidence_priority_packet_top_blocker_id": (
                "public_benchmark_gate_not_ready"
            ),
            "engine_refinement_claim_evidence_priority_packet_top_priority_bucket": (
                "public_benchmark_work_order_apply_required"
            ),
            "engine_refinement_claim_evidence_priority_packet_top_required_input": (
                "runs/refine_tier_public_benchmark_work_order_current.csv"
            ),
            "engine_refinement_claim_evidence_priority_packet_top_acceptance_artifact": (
                "runs/refine_tier_public_benchmark_readiness_current.json"
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_status": (
                "blocked_refine_tier_public_benchmark_readiness"
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_work_order_apply_status": (
                "blocked_refine_tier_public_benchmark_work_order_apply"
            ),
            "engine_refinement_claim_evidence_priority_packet_approval_token_required": (
                "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
            ),
            "science_claim_promotion_gap_closure_status": (
                "blocked_science_claim_promotion_gap_closure"
            ),
            "science_claim_promotion_gap_closure_open_gap_ids_joined": "SCI-GPCR;SCI-OPENMM",
            "science_claim_promotion_gap_closure_closed_gap_ids_joined": (
                "SCI-TRANS;SCI-CA2-PXR;SCI-WETLAB"
            ),
            "science_claim_promotion_gap_closure_current_primary_open_gap_id": "SCI-GPCR",
            "science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status": (
                "blocked_ci_low_oprm1"
            ),
            "science_claim_promotion_gap_closure_gpcr_claim_promotion_status": (
                "blocked_ci_low_oprm1"
            ),
            "science_claim_promotion_gap_closure_gpcr_evidence": (
                "runs/gpcr_conditional_prior_promotion_gate_current.json"
            ),
            "science_claim_promotion_gap_closure_openmm_claim_promotion_status": (
                "restricted_2bead_only"
            ),
            "science_claim_promotion_gap_closure_openmm_evidence": (
                "runs/wetlab_openmm_claim_promotion_boundary_current.json; "
                "runs/accuracy_parity_scorecard_current.json"
            ),
        }
    }


def test_release_source_of_truth_gate_blocks_stale_artifact_and_readme_drift(tmp_path: Path) -> None:
    artifact = tmp_path / "runs" / "operator_packet.json"
    dependency = tmp_path / "runs" / "goal_audit.json"
    _write_json(artifact, {"summary": {"status": "old_operator_packet"}})
    _write_json(dependency, {"summary": {"status": "new_goal_audit"}})
    os.utime(artifact, (1_700_000_000, 1_700_000_000))
    os.utime(dependency, (1_700_000_100, 1_700_000_100))

    _write_json(tmp_path / "runs" / "accuracy_parity_scorecard_current.json", _accuracy_payload())
    (tmp_path / "README.md").write_text(
        "runs/accuracy_parity_scorecard_current.json status=green pass=5 blocked=0\n",
        encoding="utf-8",
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[
            {
                "artifact_id": "operator_packet",
                "artifact_path": "runs/operator_packet.json",
                "builder_command": "python3 tools/build_operator_packet.py",
                "depends_on": ["runs/goal_audit.json"],
            }
        ],
        readme_paths=["README.md"],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_release_source_of_truth_gate"
    assert summary["release_source_of_truth_ready"] is False
    assert summary["stale_artifact_count"] == 1
    assert summary["readme_drift_count"] == 1
    assert summary["blocked_artifact_ids"] == ["operator_packet", "readme_accuracy_parity:README.md"]
    stale_row = next(row for row in payload["rows"] if row["artifact_id"] == "operator_packet")
    assert stale_row["stale_dependency_paths"] == ["runs/goal_audit.json"]
    readme_row = next(row for row in payload["rows"] if row["row_type"] == "readme_metric_drift")
    assert "pass=5" in readme_row["obsolete_fragments_present"]


def test_release_source_of_truth_gate_passes_current_artifact_and_readme_metrics(tmp_path: Path) -> None:
    artifact = tmp_path / "runs" / "operator_packet.json"
    dependency = tmp_path / "runs" / "goal_audit.json"
    _write_json(artifact, {"summary": {"status": "current_operator_packet"}})
    _write_json(dependency, {"summary": {"status": "current_goal_audit"}})
    os.utime(dependency, (1_700_000_000, 1_700_000_000))
    os.utime(artifact, (1_700_000_100, 1_700_000_100))

    _write_json(tmp_path / "runs" / "accuracy_parity_scorecard_current.json", _accuracy_payload())
    (tmp_path / "README.md").write_text(
        "runs/accuracy_parity_scorecard_current.json status=green pass=4 restricted_pass=1 blocked=0\n",
        encoding="utf-8",
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[
            {
                "artifact_id": "operator_packet",
                "artifact_path": "runs/operator_packet.json",
                "builder_command": "python3 tools/build_operator_packet.py",
                "depends_on": ["runs/goal_audit.json"],
            }
        ],
        readme_paths=["README.md"],
    )

    assert payload["summary"]["status"] == "product_release_source_of_truth_gate_ready"
    assert payload["summary"]["release_source_of_truth_ready"] is True
    assert payload["blockers"] == []


def test_product_release_current_refresh_defaults_to_dry_run_plan(tmp_path: Path) -> None:
    payload = refresh_mod.run_product_release_current_refresh(
        root=tmp_path,
        commands=["python3 tools/build_example.py"],
    )

    assert payload["summary"]["status"] == "product_release_current_refresh_planned"
    assert payload["summary"]["execute"] is False
    assert payload["summary"]["command_count"] == 1
    assert payload["rows"][0]["executed"] is False
    assert payload["rows"][0]["status"] == "planned"
    assert payload["summary"]["final_gate_verification_ready"] is False
    assert payload["verification_rows"] == []


def test_product_release_current_refresh_blocks_if_final_gate_is_blocked(tmp_path: Path, monkeypatch) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        {
            "summary": {
                "status": "blocked_product_release_source_of_truth_gate",
                "release_source_of_truth_ready": False,
                "blocker_count": 1,
                "stale_artifact_count": 1,
                "readme_drift_count": 0,
            }
        },
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _refresh_release_decision_ready(),
    )

    monkeypatch.setattr(
        refresh_mod,
        "_run_command",
        lambda command, *, cwd, timeout_seconds: {"returncode": 0, "timed_out": False},
    )

    payload = refresh_mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=["python3 tools/build_example.py"],
    )

    assert payload["summary"]["status"] == "blocked_product_release_current_refresh"
    assert payload["summary"]["final_gate_verification_ready"] is False
    assert payload["summary"]["final_gate_blocker_count"] == 1
    assert payload["verification_rows"][0]["gate_id"] == "product_release_source_of_truth_gate"
    assert payload["verification_rows"][0]["status"] == "fail"


def test_product_release_current_refresh_verifies_final_gates_after_execute(tmp_path: Path, monkeypatch) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        {
            "summary": {
                "status": "product_release_source_of_truth_gate_ready",
                "release_source_of_truth_ready": True,
                "blocker_count": 0,
                "stale_artifact_count": 0,
                "readme_drift_count": 0,
            }
        },
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _refresh_release_decision_ready(),
    )

    monkeypatch.setattr(
        refresh_mod,
        "_run_command",
        lambda command, *, cwd, timeout_seconds: {"returncode": 0, "timed_out": False},
    )

    payload = refresh_mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=["python3 tools/build_example.py"],
    )

    assert payload["summary"]["status"] == "product_release_current_refresh_verified"
    assert payload["summary"]["final_gate_verification_ready"] is True
    assert payload["summary"]["final_gate_blocker_count"] == 0
    release_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert (
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded"
        in release_row["required_true_fields"]
    )
    assert (
        "production_ai_registry_promotion_priority_packet_recorded"
        in release_row["required_true_fields"]
    )
    assert "production_ai_checkpoint_readiness_recorded" in release_row["required_true_fields"]
    assert (
        "production_ai_checkpoint_readiness_production_inference_acceptance_matrix_ready"
        in release_row["required_true_fields"]
    )
    assert (
        "production_ai_promotion_workbench_recorded"
        in release_row["required_true_fields"]
    )
    assert "cameo_official_result_fetch_preflight_recorded" in release_row["required_true_fields"]
    assert "self_hosted_license_distribution_audit_recorded" in release_row["required_true_fields"]
    assert (
        "self_hosted_license_distribution_audit_product_license_hash_matches_approved_source"
        in release_row["required_true_fields"]
    )
    assert "third_party_license_review_gate_recorded" in release_row["required_true_fields"]
    assert "third_party_license_review_gate_ready" in release_row["required_true_fields"]
    assert (
        "cameo_official_result_fetch_preflight_network_request_opened"
        in release_row["required_zero_fields"]
    )
    assert (
        "self_hosted_license_distribution_audit_legal_advice_provided"
        in release_row["required_zero_fields"]
    )
    assert "third_party_license_review_gate_asset_modified" in release_row["required_zero_fields"]
    assert (
        "production_ai_checkpoint_readiness_production_promotion_allowed"
        in release_row["required_zero_fields"]
    )
    assert (
        "production_ai_checkpoint_readiness_customer_facing_score_mutation_allowed"
        in release_row["required_zero_fields"]
    )
    assert (
        "production_ai_promotion_workbench_production_ai_promotion_ready"
        in release_row["required_zero_fields"]
    )
    assert "accuracy_parity_scorecard_recorded" in release_row["required_true_fields"]
    assert (
        "api_runner_profile_promotion_operator_receipt_recorded"
        in release_row["required_true_fields"]
    )
    assert "product_scope_breadth_evidence_receipt_recorded" in release_row["required_true_fields"]
    assert (
        "engine_refinement_claim_evidence_receipt_recorded"
        in release_row["required_true_fields"]
    )
    assert (
        "engine_refinement_claim_evidence_priority_packet_recorded"
        in release_row["required_true_fields"]
    )
    assert release_row["required_int_exact_fields"][
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_missing_gate_count"
    ] == 3
    assert release_row["required_int_exact_fields"][
        "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count"
    ] == 1
    assert release_row["required_int_exact_fields"][
        "production_ai_checkpoint_readiness_production_inference_acceptance_blocked_stage_count"
    ] == 1
    assert release_row["required_int_exact_fields"][
        "production_ai_checkpoint_readiness_trained_model_checkpoint_count"
    ] == 1
    assert release_row["required_int_exact_fields"][
        "production_ai_promotion_workbench_post_return_ladder_blocked_stage_count"
    ] == 2
    assert release_row["required_int_exact_fields"][
        "cameo_official_result_fetch_preflight_blocker_count"
    ] == 2
    assert release_row["required_int_exact_fields"][
        "self_hosted_license_distribution_audit_operator_review_item_count"
    ] == 1
    assert release_row["required_int_exact_fields"][
        "third_party_license_review_gate_expected_review_asset_count"
    ] == 1
    assert release_row["required_int_exact_fields"][
        "accuracy_parity_scorecard_top_blocker_count"
    ] == 4
    assert release_row["required_int_exact_fields"][
        "accuracy_parity_ligand_ranking_positive_count"
    ] == 13
    assert release_row["required_int_exact_fields"][
        "api_runner_profile_promotion_operator_receipt_blocked_row_count"
    ] == 4
    assert release_row["required_int_exact_fields"][
        "product_scope_breadth_evidence_receipt_blocked_row_count"
    ] == 6
    assert release_row["required_int_exact_fields"][
        "engine_refinement_claim_evidence_receipt_required_blocker_count"
    ] == 6
    assert release_row["required_int_exact_fields"][
        "engine_refinement_claim_evidence_priority_packet_public_benchmark_work_order_apply_blocked_row_count"
    ] == 8
    assert release_row["required_text_exact_fields"][
        "goal_bottleneck_briefing_production_ai_registry_promotion_priority_top_gate_id"
    ] == "default_residual_mode_guarded"
    assert release_row["required_text_exact_fields"][
        "production_ai_registry_promotion_priority_operator_receipt_status"
    ] == "blocked_production_ai_registry_promotion_operator_receipt"
    assert release_row["required_text_exact_fields"][
        "cameo_official_result_fetch_preflight_fetch_approval_token_required"
    ] == "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH"
    assert release_row["required_text_exact_fields"][
        "self_hosted_license_distribution_audit_spdx_license_id"
    ] == "ProprietaryRef-Betelgeuze"
    assert release_row["required_text_exact_fields"][
        "self_hosted_license_distribution_audit_third_party_dual_license_assets"
    ] == "jszip"
    assert release_row["required_text_exact_fields"][
        "third_party_license_review_gate_approval_token_required"
    ] == "APPROVE_THIRD_PARTY_LICENSE_REVIEW"
    assert release_row["required_text_exact_fields"][
        "third_party_license_review_gate_approved_assets"
    ] == "jszip"
    assert release_row["required_text_exact_fields"][
        "production_ai_registry_promotion_priority_observed_registry_default_residual_mode"
    ] == "shadow"
    assert release_row["required_text_exact_fields"][
        "production_ai_checkpoint_readiness_actionable_blocker_stage_id"
    ] == "registry_guarded_promotion_acceptance"
    assert release_row["required_text_exact_fields"][
        "production_ai_checkpoint_readiness_registry_promotion_missing_gate_ids"
    ] == (
        "production_promotion_allowed;customer_facing_mutation_flags;"
        "default_residual_mode_guarded"
    )
    assert release_row["required_text_exact_fields"][
        "production_ai_promotion_workbench_blocked_stage_ids"
    ] == "residual_model_registry;product_goal_completion_audit"
    assert release_row["required_text_exact_fields"][
        "accuracy_parity_scorecard_status"
    ] == "blocked_accuracy_parity"
    assert release_row["required_text_exact_fields"][
        "accuracy_parity_ligand_ranking_score_col_used"
    ] == "binding_score_composite_v7_residual_active"
    assert release_row["required_true_fields"].count("master_gap_closure_rollup_recorded") == 1
    assert release_row["required_true_fields"].count(
        "science_claim_promotion_gap_closure_gpcr_release_blocker"
    ) == 1
    assert release_row["required_zero_fields"].count(
        "science_claim_promotion_gap_closure_claim_promotion_allowed"
    ) == 1
    assert release_row["required_int_exact_fields"][
        "master_gap_closure_rollup_open_gap_count"
    ] == 1
    assert release_row["required_int_exact_fields"][
        "master_gap_closure_rollup_release_blocker_row_count"
    ] == 1
    assert release_row["required_text_exact_fields"][
        "master_gap_closure_rollup_open_gap_ids_joined"
    ] == "SCI-CLAIM"
    assert release_row["required_text_exact_fields"][
        "master_gap_closure_rollup_science_claim_rollup_status"
    ] == "blocked_science_claim_promotion_gap_closure"
    assert release_row["required_text_exact_fields"][
        "api_runner_profile_promotion_operator_receipt_first_blocked_profile_id"
    ] == "backmapping_scoring.example"
    assert release_row["required_text_exact_fields"][
        "product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id"
    ] == "direct_binding_evidence_missing"
    assert release_row["required_text_exact_fields"][
        "engine_refinement_claim_evidence_receipt_first_blocked_blocker_id"
    ] == "public_benchmark_gate_not_ready"
    assert release_row["required_text_exact_fields"][
        "engine_refinement_claim_evidence_priority_packet_top_priority_bucket"
    ] == "public_benchmark_work_order_apply_required"
    assert release_row["required_int_exact_fields"][
        "science_claim_promotion_gap_closure_open_gap_count"
    ] == 2
    assert release_row["required_int_exact_fields"][
        "science_claim_promotion_gap_closure_closed_gap_count"
    ] == 3
    assert release_row["required_int_exact_fields"][
        "science_claim_promotion_gap_closure_release_blocker_row_count"
    ] == 2
    assert release_row["required_text_exact_fields"][
        "science_claim_promotion_gap_closure_open_gap_ids_joined"
    ] == "SCI-GPCR;SCI-OPENMM"
    assert release_row["required_text_exact_fields"][
        "science_claim_promotion_gap_closure_current_primary_open_gap_id"
    ] == "SCI-GPCR"
    assert release_row["required_text_exact_fields"][
        "science_claim_promotion_gap_closure_gpcr_claim_promotion_status"
    ] == "blocked_ci_low_oprm1"
    assert release_row["required_text_exact_fields"][
        "science_claim_promotion_gap_closure_openmm_claim_promotion_status"
    ] == "restricted_2bead_only"


def test_product_release_current_refresh_blocks_timed_out_command(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        refresh_mod,
        "_run_command",
        lambda command, *, cwd, timeout_seconds: {"returncode": -9, "timed_out": True},
    )

    payload = refresh_mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=["python3 tools/hangs.py"],
        command_timeout_seconds=7,
    )

    assert payload["summary"]["status"] == "blocked_product_release_current_refresh"
    assert payload["summary"]["timed_out_count"] == 1
    assert payload["summary"]["command_timeout_seconds"] == 7
    assert payload["rows"][0]["status"] == "timeout"
    assert payload["rows"][0]["release_blocker"] is True
    assert payload["verification_rows"] == []


def test_product_release_current_refresh_uses_command_timeout_hint(tmp_path: Path, monkeypatch) -> None:
    observed: list[int] = []

    def fake_run(command: str, *, cwd: Path, timeout_seconds: int) -> dict:
        observed.append(timeout_seconds)
        return {"returncode": 0, "timed_out": False}

    monkeypatch.setattr(refresh_mod, "_run_command", fake_run)
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        {
            "summary": {
                "status": "product_release_source_of_truth_gate_ready",
                "release_source_of_truth_ready": True,
                "blocker_count": 0,
                "stale_artifact_count": 0,
                "readme_drift_count": 0,
            }
        },
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _refresh_release_decision_ready(),
    )

    payload = refresh_mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=["python3 tools/smoke.py --timeout-seconds 12"],
        command_timeout_seconds=99,
    )

    assert observed == [42]
    assert payload["rows"][0]["timeout_seconds"] == 42
    assert payload["summary"]["status"] == "product_release_current_refresh_verified"


def test_release_source_of_truth_tracks_customer_report_ux_artifacts() -> None:
    artifact_ids = {spec["artifact_id"] for spec in mod.DEFAULT_ARTIFACT_SPECS}
    status_ids = {spec["artifact_id"] for spec in mod.DEFAULT_STATUS_SPECS}

    assert "product_ai_report_explanation_packet" in artifact_ids
    assert "product_ai_report_ux_contract" in artifact_ids
    assert "product_pose_sampling_readiness" in artifact_ids
    assert "product_ai_decision_graph_contract" in artifact_ids
    assert "product_production_ai_checkpoint_readiness" in artifact_ids
    assert "product_production_ai_promotion_workbench" in artifact_ids
    assert "production_ai_registry_promotion_operator_receipt" in artifact_ids
    assert "product_api_contract" in artifact_ids
    assert "product_service_boundary_contract" in artifact_ids
    assert "local_delivery_environment_manifest" in artifact_ids
    assert "wetlab_selected_allatom_gate_burndown" in artifact_ids
    assert "product_bundle_contract" in artifact_ids
    assert "product_delivery_evidence_contract" in artifact_ids
    assert "product_pilot_packet_contract" in artifact_ids
    assert "self_hosted_license_distribution_audit" in artifact_ids
    assert "third_party_license_review_gate" in artifact_ids
    assert "product_execution_work_order" in artifact_ids
    assert "product_execution_preflight" in artifact_ids
    assert "product_bundle_contract_semantic_ready" in status_ids
    assert "product_delivery_evidence_contract_semantic_ready" in status_ids
    assert "product_pilot_packet_contract_semantic_ready" in status_ids
    assert "product_api_contract_semantic_ready" in status_ids
    assert "product_service_boundary_contract_semantic_ready" in status_ids
    assert "self_hosted_license_distribution_audit_semantic_ready" in status_ids
    assert "product_ai_report_explanation_packet_semantic_ready" in status_ids
    assert "product_ai_report_ux_contract_semantic_ready" in status_ids
    assert "product_pose_sampling_readiness_semantic_ready" in status_ids
    assert "product_trajectory_sla_contract_semantic_ready" in status_ids
    assert "product_job_orchestration_contract_semantic_ready" in status_ids
    assert "product_ledger_privacy_scan" in artifact_ids
    assert "product_trajectory_sla_contract" in artifact_ids
    assert "product_job_orchestration_contract" in artifact_ids
    assert "api_runner_profile_promotion_operator_receipt" in artifact_ids
    assert "product_launch_r4_preflight" in artifact_ids
    assert "production_ai_registry_promotion_priority_packet" in artifact_ids
    assert "engine_refinement_claim_promotion_action_board" in artifact_ids
    assert "engine_refinement_claim_evidence_receipt" in artifact_ids
    assert "product_scope_breadth_closure_checklist" in artifact_ids
    assert "product_scope_breadth_evidence_receipt" in artifact_ids
    assert "goal_operator_intake_kit" in artifact_ids
    assert "goal_api_surface_contract" in artifact_ids
    assert "goal_bottleneck_briefing" in artifact_ids
    assert "product_full_commercial_blocker_evidence_matrix" in artifact_ids
    assert "product_commercial_readiness_execution_ladder" in artifact_ids
    assert "product_rollout_execution_smoke_receipt" in artifact_ids
    assert "deploy_ops_legal_gap_closure" in artifact_ids
    assert "science_claim_promotion_gap_closure" in artifact_ids
    assert "master_gap_closure_rollup" in artifact_ids
    assert "python3 tools/build_api_runner_profile_promotion_operator_receipt.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_production_ai_registry_promotion_operator_receipt.py" in mod.RELEASE_REFRESH_COMMANDS
    assert (
        "python3 tools/product/build_production_ai_registry_promotion_priority_packet.py"
        in mod.RELEASE_REFRESH_COMMANDS
    )
    assert "product_release_bundle_semantic_ready" in status_ids
    assert "product_goal_completion_audit_full_commercial_release_blockers_semantic_ready" in status_ids
    assert "api_runner_profile_promotion_operator_receipt_blocked_semantic_ready" in status_ids
    assert "product_production_ai_checkpoint_shadow_blocked_semantic_ready" in status_ids
    assert "product_production_ai_promotion_workbench_shadow_blocked_semantic_ready" in status_ids
    assert "production_ai_registry_promotion_operator_receipt_blocked_semantic_ready" in status_ids
    assert "production_ai_registry_promotion_priority_packet_blocked_semantic_ready" in status_ids
    assert "cameo_validation_operations_dossier_current_bottleneck_semantic_ready" in status_ids
    assert "cameo_official_result_fetch_preflight" in artifact_ids
    assert "cameo_official_result_fetch_preflight_blocked_semantic_ready" in status_ids
    assert "product_scope_breadth_evidence_receipt_blocked_semantic_ready" in status_ids
    assert "engine_refinement_claim_evidence_receipt_blocked_semantic_ready" in status_ids
    assert "product_full_commercial_blocker_evidence_matrix_semantic_ready" in status_ids
    assert "goal_operator_action_board_primary_release_blocker_semantic_ready" in status_ids
    assert "goal_operator_intake_kit_primary_release_blocker_semantic_ready" in status_ids
    assert "goal_api_surface_contract_semantic_ready" in status_ids
    assert "goal_bottleneck_briefing_semantic_ready" in status_ids
    assert "python3 tools/build_cameo_official_result_fetch_preflight.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_cameo_validation_operations_dossier.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_cameo_architecture_validation_contract.py" in mod.RELEASE_REFRESH_COMMANDS
    goal_api_status_spec = next(
        spec
        for spec in mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "goal_api_surface_contract_semantic_ready"
    )
    assert goal_api_status_spec["required_int_exact_fields"] == {
        "blocker_count": 0,
        "missing_status_key_count": 0,
        "missing_full_commercial_visibility_token_count": 0,
        "missing_fail_closed_flag_count": 0,
    }
    intake_kit_status_spec = next(
        spec
        for spec in mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "goal_operator_intake_kit_primary_release_blocker_semantic_ready"
    )
    assert intake_kit_status_spec["required_int_exact_fields"] == {
        "product_goal_release_blocker_fail_count": 2,
        "full_commercial_evidence_receipt_entry_count": 2,
        "full_commercial_evidence_receipt_operator_input_required_count": 2,
        "full_commercial_evidence_receipt_current_action_required_count": 2,
        "full_commercial_evidence_receipt_template_required_count": 2,
        "full_commercial_evidence_receipt_template_present_count": 2,
        "full_commercial_evidence_receipt_approval_token_count": 2,
        "production_ai_registry_promotion_priority_operator_input_required_count": 3,
        "production_ai_registry_promotion_priority_blocked_priority_item_count": 3,
        "production_ai_registry_promotion_priority_missing_gate_count": 3,
        "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count": 1,
        "product_scope_breadth_evidence_priority_open_item_count": 15,
        "product_scope_breadth_evidence_priority_scientific_evidence_request_count": 11,
        "product_scope_breadth_evidence_priority_local_crosscheck_candidate_count": 11,
        "product_scope_breadth_evidence_priority_review_only_keep_blocked_count": 1,
    }
    assert intake_kit_status_spec["required_true_fields"] == [
        "product_scope_breadth_evidence_priority_packet_ready",
        "production_ai_registry_promotion_priority_packet_ready"
    ]
    assert intake_kit_status_spec["required_text_exact_fields"][
        "product_scope_breadth_evidence_priority_source_json"
    ] == "runs/product_scope_breadth_evidence_priority_packet_current.json"
    assert intake_kit_status_spec["required_text_exact_fields"][
        "product_scope_breadth_evidence_priority_status"
    ] == "product_scope_breadth_evidence_priority_packet_ready"
    assert intake_kit_status_spec["required_text_exact_fields"][
        "product_scope_breadth_evidence_priority_top_item_id"
    ] == "AQP1.core_binder_01"
    assert intake_kit_status_spec["required_text_exact_fields"][
        "product_scope_breadth_evidence_priority_top_bucket"
    ] == "local_crosscheck_review_present_but_exact_quant_required"
    assert intake_kit_status_spec["required_text_exact_fields"][
        "full_commercial_evidence_receipt_required_inputs"
    ] == (
        "config/product_scope_breadth_evidence_receipt_current.csv;"
        "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
    )
    assert intake_kit_status_spec["required_text_exact_fields"][
        "full_commercial_evidence_receipt_source_gate_statuses"
    ] == (
        "product_scope_breadth_evidence_receipt=blocked_product_scope_breadth_evidence_receipt;"
        "engine_refinement_claim_evidence_receipt=blocked_engine_refinement_claim_evidence_receipt"
    )
    assert intake_kit_status_spec["required_text_exact_fields"][
        "production_ai_registry_promotion_priority_source_json"
    ] == "runs/production_ai_registry_promotion_priority_packet_current.json"
    assert intake_kit_status_spec["required_text_exact_fields"][
        "production_ai_registry_promotion_priority_status"
    ] == "blocked_production_ai_registry_promotion_priority_packet"
    assert intake_kit_status_spec["required_text_exact_fields"][
        "production_ai_registry_promotion_priority_top_gate_id"
    ] == "default_residual_mode_guarded"
    bottleneck_status_spec = next(
        spec
        for spec in mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "goal_bottleneck_briefing_semantic_ready"
    )
    assert bottleneck_status_spec["required_true_fields"] == [
        "product_scope_breadth_evidence_priority_packet_ready",
        "production_ai_registry_promotion_priority_packet_ready"
    ]
    assert bottleneck_status_spec["required_int_exact_fields"] == {
        "completion_audit_release_blocker_bottleneck_count": 2,
        "full_commercial_evidence_receipt_entry_count": 2,
        "full_commercial_evidence_receipt_operator_input_required_count": 2,
        "full_commercial_evidence_receipt_current_action_required_count": 2,
        "full_commercial_evidence_receipt_template_required_count": 2,
        "full_commercial_evidence_receipt_template_present_count": 2,
        "full_commercial_evidence_receipt_approval_token_count": 2,
        "production_ai_registry_promotion_priority_operator_input_required_count": 3,
        "production_ai_registry_promotion_priority_blocked_priority_item_count": 3,
        "production_ai_registry_promotion_priority_missing_gate_count": 3,
        "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count": 1,
        "product_scope_breadth_evidence_priority_open_item_count": 15,
        "product_scope_breadth_evidence_priority_scientific_evidence_request_count": 11,
        "product_scope_breadth_evidence_priority_local_crosscheck_candidate_count": 11,
        "product_scope_breadth_evidence_priority_review_only_keep_blocked_count": 1,
    }
    assert bottleneck_status_spec["required_text_exact_fields"][
        "product_scope_breadth_evidence_priority_source_json"
    ] == "runs/product_scope_breadth_evidence_priority_packet_current.json"
    assert bottleneck_status_spec["required_text_exact_fields"][
        "product_scope_breadth_evidence_priority_top_item_id"
    ] == "AQP1.core_binder_01"
    assert bottleneck_status_spec["required_text_exact_fields"][
        "full_commercial_evidence_receipt_required_inputs"
    ] == (
        "config/product_scope_breadth_evidence_receipt_current.csv;"
        "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
    )
    assert bottleneck_status_spec["required_text_exact_fields"][
        "production_ai_registry_promotion_priority_source_json"
    ] == "runs/production_ai_registry_promotion_priority_packet_current.json"
    assert bottleneck_status_spec["required_text_exact_fields"][
        "production_ai_registry_promotion_priority_status"
    ] == "blocked_production_ai_registry_promotion_priority_packet"
    assert bottleneck_status_spec["required_text_exact_fields"][
        "production_ai_registry_promotion_priority_top_gate_id"
    ] == "default_residual_mode_guarded"
    full_matrix_status_spec = next(
        spec
        for spec in mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "product_full_commercial_blocker_evidence_matrix_semantic_ready"
    )
    assert full_matrix_status_spec["required_int_exact_fields"] == {
        "blocked_matrix_row_count": 12,
        "approval_token_count": 2,
        "scope_receipt_blocked_row_count": 6,
        "engine_receipt_blocked_row_count": 6,
    }
    assert full_matrix_status_spec["required_text_exact_fields"][
        "first_blocked_release_blocker_id"
    ] == "R8_full_scope_claim_closure"
    assert full_matrix_status_spec["required_text_exact_fields"][
        "scope_receipt_most_common_row_blocker"
    ] == "operator_placeholders_unfilled"
    scope_receipt_status_spec = next(
        spec
        for spec in mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "product_scope_breadth_evidence_receipt_blocked_semantic_ready"
    )
    assert scope_receipt_status_spec["required_int_exact_fields"] == {
        "full_scope_evidence_receipt_ready": 0,
        "receipt_row_count": 6,
        "pass_row_count": 0,
        "blocked_row_count": 6,
        "blocker_count": 1,
        "evidence_artifact_present_count": 0,
        "evidence_status_verified_count": 0,
        "required_scope_blocker_count": 6,
        "missing_required_scope_blocker_count": 0,
        "external_state_mutated": 0,
    }
    assert scope_receipt_status_spec["required_text_exact_fields"][
        "approval_token_required"
    ] == "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
    assert scope_receipt_status_spec["required_text_exact_fields"][
        "first_blocked_scope_blocker_id"
    ] == "direct_binding_evidence_missing"
    assert scope_receipt_status_spec["required_text_exact_fields"][
        "most_common_row_blocker"
    ] == "operator_placeholders_unfilled"
    engine_receipt_status_spec = next(
        spec
        for spec in mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "engine_refinement_claim_evidence_receipt_blocked_semantic_ready"
    )
    assert engine_receipt_status_spec["required_int_exact_fields"] == {
        "claim_promotion_evidence_receipt_ready": 0,
        "receipt_row_count": 6,
        "pass_row_count": 0,
        "blocked_row_count": 6,
        "blocker_count": 1,
        "evidence_artifact_present_count": 0,
        "evidence_status_verified_count": 0,
        "required_blocker_count": 6,
        "missing_required_blocker_count": 0,
        "external_state_mutated": 0,
    }
    assert engine_receipt_status_spec["required_text_exact_fields"][
        "approval_token_required"
    ] == "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
    assert engine_receipt_status_spec["required_text_exact_fields"][
        "first_blocked_blocker_id"
    ] == "public_benchmark_gate_not_ready"
    assert engine_receipt_status_spec["required_text_exact_fields"][
        "most_common_row_blocker"
    ] == "operator_placeholders_unfilled"
    runner_receipt_status_spec = next(
        spec
        for spec in mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "api_runner_profile_promotion_operator_receipt_blocked_semantic_ready"
    )
    assert runner_receipt_status_spec["required_int_exact_fields"] == {
        "operator_receipt_ready": 0,
        "profile_count": 4,
        "receipt_row_count": 4,
        "pass_row_count": 0,
        "blocked_row_count": 4,
        "blocker_count": 1,
    }
    assert runner_receipt_status_spec["required_text_exact_fields"][
        "first_blocked_profile_id"
    ] == "backmapping_scoring.example"
    assert runner_receipt_status_spec["required_text_exact_fields"][
        "most_common_row_blocker"
    ] == "operator_decision_missing"
    cameo_operations_status_spec = next(
        spec
        for spec in mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "cameo_validation_operations_dossier_current_bottleneck_semantic_ready"
    )
    assert cameo_operations_status_spec["required_int_exact_fields"][
        "blocked_stage_count"
    ] == 1
    assert cameo_operations_status_spec["required_int_exact_fields"][
        "first_blocked_stage_blocker_count"
    ] == 2
    assert cameo_operations_status_spec["required_text_exact_fields"][
        "first_blocked_stage_id"
    ] == "official_result_fetch_preflight"
    assert cameo_operations_status_spec["required_text_exact_fields"][
        "first_approval_required_stage_id"
    ] == "public_registration_and_email"
    cameo_fetch_artifact_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "cameo_official_result_fetch_preflight"
    )
    assert "betelgeuze_cameo/official_result_fetch_preflight.py" in cameo_fetch_artifact_spec[
        "depends_on"
    ]
    assert "runs/cameo_official_result_fetch_operator_approval_template_current.csv" in cameo_fetch_artifact_spec[
        "depends_on"
    ]
    assert "runs/cameo_official_result_fetch_operator_approval_intake.csv" not in cameo_fetch_artifact_spec[
        "depends_on"
    ]
    cameo_fetch_status_spec = next(
        spec
        for spec in mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "cameo_official_result_fetch_preflight_blocked_semantic_ready"
    )
    assert cameo_fetch_status_spec["required_int_exact_fields"][
        "operator_fetch_csv_present"
    ] == 0
    assert cameo_fetch_status_spec["required_int_exact_fields"][
        "network_request_opened"
    ] == 0
    assert cameo_fetch_status_spec["required_text_exact_fields"][
        "operator_fetch_csv"
    ] == "runs/cameo_official_result_fetch_operator_approval_intake.csv"
    assert cameo_fetch_status_spec["required_text_exact_fields"][
        "fetch_approval_token_required"
    ] == "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH"
    checkpoint_status_spec = next(
        spec
        for spec in mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "product_production_ai_checkpoint_shadow_blocked_semantic_ready"
    )
    assert checkpoint_status_spec["required_int_exact_fields"][
        "production_inference_acceptance_blocked_stage_count"
    ] == 1
    assert checkpoint_status_spec["required_text_exact_fields"][
        "production_inference_actionable_blocker_stage_id"
    ] == "registry_guarded_promotion_acceptance"
    promotion_status_spec = next(
        spec
        for spec in mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "product_production_ai_promotion_workbench_shadow_blocked_semantic_ready"
    )
    assert promotion_status_spec["required_int_exact_fields"][
        "post_return_promotion_ladder_blocked_stage_count"
    ] == 2
    assert promotion_status_spec["required_text_exact_fields"]["first_blocked_stage_id"] == "residual_model_registry"
    registry_receipt_spec = next(
        spec
        for spec in mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "production_ai_registry_promotion_operator_receipt_blocked_semantic_ready"
    )
    assert registry_receipt_spec["required_int_exact_fields"] == {
        "operator_receipt_ready": 0,
        "receipt_row_count": 1,
        "pass_row_count": 0,
        "blocked_row_count": 1,
        "blocker_count": 1,
        "observed_registry_trained_model_checkpoint_count": 1,
        "observed_checkpoint_registry_promotion_currently_satisfied": 0,
    }
    assert registry_receipt_spec["required_text_exact_fields"][
        "approval_token_required"
    ] == "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
    registry_receipt_artifact_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "production_ai_registry_promotion_operator_receipt"
    )
    assert "config/production_ai_registry_promotion_operator_receipt_current.csv" in registry_receipt_artifact_spec[
        "depends_on"
    ]
    assert "runs/product_production_ai_checkpoint_readiness_current.json" in registry_receipt_artifact_spec[
        "depends_on"
    ]
    registry_priority_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "production_ai_registry_promotion_priority_packet"
    )
    assert "runs/production_ai_registry_promotion_operator_receipt_current.json" in registry_priority_spec[
        "depends_on"
    ]
    assert "runs/product_production_ai_promotion_workbench_current.json" in registry_priority_spec[
        "depends_on"
    ]
    registry_priority_status_spec = next(
        spec
        for spec in mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "production_ai_registry_promotion_priority_packet_blocked_semantic_ready"
    )
    assert registry_priority_status_spec["required_int_exact_fields"][
        "operator_input_required_count"
    ] == 3
    assert registry_priority_status_spec["required_text_exact_fields"][
        "top_gate_id"
    ] == "default_residual_mode_guarded"
    commercial_operator_packet_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "product_commercial_readiness_operator_packet"
    )
    assert "runs/production_ai_registry_promotion_priority_packet_current.json" in commercial_operator_packet_spec[
        "depends_on"
    ]
    goal_action_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "goal_operator_action_board"
    )
    assert "runs/product_goal_completion_audit_current.json" in goal_action_spec["depends_on"]
    assert "runs/engine_refinement_claim_promotion_action_board_current.csv" in goal_action_spec["depends_on"]
    goal_audit_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_goal_completion_audit"
    )
    assert "runs/goal_operator_action_board_current.json" not in goal_audit_spec["depends_on"]
    assert "runs/engine_refinement_tier_readiness_current.json" in goal_audit_spec["depends_on"]
    assert "runs/product_scope_breadth_evidence_receipt_current.json" in goal_audit_spec["depends_on"]
    scope_closure_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_scope_breadth_closure_checklist"
    )
    assert "runs/transporter_slot_assignment_candidate_workbook_current.json" in scope_closure_spec["depends_on"]
    assert "runs/transporter_manual_review_intake_template_current.json" in scope_closure_spec["depends_on"]
    scope_receipt_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_scope_breadth_evidence_receipt"
    )
    assert "config/product_scope_breadth_evidence_receipt_current.csv" in scope_receipt_spec["depends_on"]
    assert "runs/product_scope_breadth_closure_checklist_current.json" in scope_receipt_spec["depends_on"]
    intake_kit_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "goal_operator_intake_kit"
    )
    assert "runs/goal_operator_action_board_current.json" in intake_kit_spec["depends_on"]
    assert "runs/production_ai_registry_promotion_operator_receipt_current.json" in intake_kit_spec["depends_on"]
    assert "runs/production_ai_registry_promotion_priority_packet_current.json" in intake_kit_spec["depends_on"]
    assert "config/production_ai_registry_promotion_operator_receipt_current.csv" in intake_kit_spec["depends_on"]
    assert "runs/product_scope_breadth_evidence_priority_packet_current.json" in intake_kit_spec["depends_on"]
    assert "runs/product_scope_breadth_evidence_receipt_current.json" in intake_kit_spec["depends_on"]
    assert "config/product_scope_breadth_evidence_receipt_current.csv" in intake_kit_spec["depends_on"]
    goal_api_surface_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "goal_api_surface_contract"
    )
    assert "api/goal.py" in goal_api_surface_spec["depends_on"]
    assert "api/main.py" in goal_api_surface_spec["depends_on"]
    assert "api/security.py" in goal_api_surface_spec["depends_on"]
    goal_bottleneck_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "goal_bottleneck_briefing"
    )
    assert "runs/product_goal_completion_audit_current.json" in goal_bottleneck_spec["depends_on"]
    assert "runs/goal_operator_action_board_current.json" in goal_bottleneck_spec["depends_on"]
    assert "runs/goal_operator_intake_kit_current/manifest.json" in goal_bottleneck_spec["depends_on"]
    assert "runs/product_public_benchmark_work_order_current.json" in goal_bottleneck_spec["depends_on"]
    assert "runs/goal_release_decision_gate_current.json" not in goal_bottleneck_spec["depends_on"]
    assert "runs/product_release_source_of_truth_gate_current.json" not in goal_bottleneck_spec["depends_on"]
    full_commercial_matrix_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "product_full_commercial_blocker_evidence_matrix"
    )
    assert "runs/product_scope_breadth_evidence_receipt_current.json" in full_commercial_matrix_spec["depends_on"]
    assert "runs/engine_refinement_claim_evidence_receipt_current.json" in full_commercial_matrix_spec["depends_on"]
    assert "runs/product_goal_completion_audit_current.json" in full_commercial_matrix_spec["depends_on"]
    assert "runs/goal_bottleneck_briefing_current.json" in full_commercial_matrix_spec["depends_on"]
    commercial_operator_packet_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "product_commercial_readiness_operator_packet"
    )
    assert "runs/product_goal_completion_audit_current.json" in commercial_operator_packet_spec["depends_on"]
    assert (
        "runs/production_ai_registry_promotion_operator_receipt_current.json"
        in commercial_operator_packet_spec["depends_on"]
    )
    assert (
        "config/production_ai_registry_promotion_operator_receipt_current.csv"
        in commercial_operator_packet_spec["depends_on"]
    )
    commercial_ladder_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "product_commercial_readiness_execution_ladder"
    )
    assert "runs/product_commercial_readiness_operator_packet_current.json" in commercial_ladder_spec[
        "depends_on"
    ]
    assert "runs/product_commercial_readiness_operator_packet_freshness_current.json" in commercial_ladder_spec[
        "depends_on"
    ]
    commercial_handoff_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "product_commercial_readiness_handoff_bundle"
    )
    assert "runs/product_commercial_readiness_operator_packet_current.json" in commercial_handoff_spec[
        "depends_on"
    ]
    assert "runs/product_commercial_readiness_operator_packet_freshness_current.json" in commercial_handoff_spec[
        "depends_on"
    ]
    assert "runs/product_commercial_readiness_execution_ladder_current.json" in commercial_handoff_spec[
        "depends_on"
    ]
    assert "runs/product_full_commercial_blocker_evidence_matrix_current.json" in commercial_handoff_spec[
        "depends_on"
    ]
    rollout_smoke_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "product_rollout_execution_smoke_receipt"
    )
    assert "runs/product_rollout_execution_readiness_current.json" in rollout_smoke_spec["depends_on"]
    registry_spec = next(spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "residual_model_registry")
    assert "runs/residual_shadow_ab_current.json" in registry_spec["depends_on"]
    execution_work_order_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_execution_work_order"
    )
    assert "runs/product_readiness_gate_current.json" in execution_work_order_spec["depends_on"]
    execution_preflight_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_execution_preflight"
    )
    assert "runs/product_execution_work_order_current.json" in execution_preflight_spec["depends_on"]
    api_contract_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_api_contract"
    )
    assert "api/product.py" in api_contract_spec["depends_on"]
    assert "betelgeuze_product/api_contract.py" in api_contract_spec["depends_on"]
    service_boundary_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_service_boundary_contract"
    )
    assert "api/product.py" in service_boundary_spec["depends_on"]
    assert "betelgeuze_product/cli.py" in service_boundary_spec["depends_on"]
    commercial_independence_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_commercial_independence_gate"
    )
    assert "runs/product_api_contract_current.json" in commercial_independence_spec["depends_on"]
    assert "runs/product_service_boundary_contract_current.json" in commercial_independence_spec["depends_on"]
    assert "runs/product_bundle_contract_current.json" in commercial_independence_spec["depends_on"]
    assert "runs/product_delivery_evidence_contract_current.json" in commercial_independence_spec["depends_on"]
    assert "runs/product_pilot_packet_contract_current.json" in commercial_independence_spec["depends_on"]
    license_audit_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "self_hosted_license_distribution_audit"
    )
    assert "runs/product_commercial_independence_gate_current.json" in license_audit_spec["depends_on"]
    assert "viewer/vendor/manifest.json" in license_audit_spec["depends_on"]
    third_party_review_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "third_party_license_review_gate"
    )
    assert "runs/self_hosted_license_distribution_audit_current.json" in third_party_review_spec["depends_on"]
    assert "runs/third_party_license_review_operator_intake.csv" in third_party_review_spec["depends_on"]
    decision_graph_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_ai_decision_graph_contract"
    )
    assert "runs/product_ai_report_ux_contract_current.json" in decision_graph_spec["depends_on"]
    assert "runs/product_pose_sampling_readiness_current.json" in decision_graph_spec["depends_on"]
    pose_sampling_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_pose_sampling_readiness"
    )
    assert "core/pose_generation.py" in pose_sampling_spec["depends_on"]
    assert "core/pocket_detection.py" in pose_sampling_spec["depends_on"]
    explanation_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_ai_report_explanation_packet"
    )
    assert "runs/product_ai_decision_graph_contract_current.json" not in explanation_spec["depends_on"]
    report_ux_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_ai_report_ux_contract"
    )
    assert "runs/product_ai_decision_graph_contract_current.json" not in report_ux_spec["depends_on"]
    deploy_ops_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "deploy_ops_legal_gap_closure"
    )
    assert "runs/product_rollout_execution_smoke_receipt_current.json" in deploy_ops_spec["depends_on"]
    science_claim_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "science_claim_promotion_gap_closure"
    )
    assert "runs/gpcr_conditional_prior_promotion_gate_current.json" in science_claim_spec["depends_on"]
    master_rollup_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "master_gap_closure_rollup"
    )
    assert "runs/science_claim_promotion_gap_closure_current.json" in master_rollup_spec["depends_on"]
    assert "runs/deploy_ops_legal_gap_closure_current.json" in master_rollup_spec["depends_on"]
    privacy_scan_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "product_ledger_privacy_scan"
    )
    assert "runs/goal_readiness_rollup_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/goal_operator_action_board_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/goal_operator_intake_kit_current/manifest.json" in privacy_scan_spec["depends_on"]
    assert "runs/goal_release_burndown_work_order_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/goal_api_surface_contract_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/goal_bottleneck_briefing_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/product_full_commercial_blocker_evidence_matrix_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/product_scope_breadth_evidence_priority_packet_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/engine_refinement_claim_evidence_priority_packet_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/production_ai_registry_promotion_operator_receipt_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/production_ai_registry_promotion_priority_packet_current.json" in privacy_scan_spec["depends_on"]
    release_bundle_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_release_bundle"
    )
    assert "runs/self_hosted_license_distribution_audit_current.json" in release_bundle_spec["depends_on"]
    assert "runs/third_party_license_review_gate_current.json" in release_bundle_spec["depends_on"]
    assert "runs/product_goal_completion_audit_current.json" in release_bundle_spec["depends_on"]
    assert "runs/production_ai_registry_promotion_priority_packet_current.json" in release_bundle_spec[
        "depends_on"
    ]
    assert "runs/product_pose_sampling_readiness_current.json" in release_bundle_spec["depends_on"]
    assert "runs/product_trajectory_sla_contract_current.json" in release_bundle_spec["depends_on"]
    assert "runs/engine_refinement_claim_evidence_receipt_current.json" in release_bundle_spec["depends_on"]
    assert "runs/product_scope_breadth_evidence_receipt_current.json" in release_bundle_spec["depends_on"]
    assert "runs/product_full_commercial_blocker_evidence_matrix_current.json" in release_bundle_spec[
        "depends_on"
    ]
    evidence_receipt_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "engine_refinement_claim_evidence_receipt"
    )
    assert "config/engine_refinement_claim_promotion_evidence_receipt_current.csv" in evidence_receipt_spec["depends_on"]
    assert "runs/engine_refinement_claim_promotion_action_board_current.csv" in evidence_receipt_spec["depends_on"]
    priority_packet_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "engine_refinement_claim_evidence_priority_packet"
    )
    assert "runs/engine_refinement_claim_evidence_receipt_current.json" in priority_packet_spec["depends_on"]
    assert "runs/refine_tier_public_benchmark_readiness_current.json" in priority_packet_spec["depends_on"]
    assert "runs/refine_tier_public_benchmark_work_order_current.csv" in priority_packet_spec["depends_on"]
    assert "runs/refine_tier_public_benchmark_work_order_apply_current.json" in priority_packet_spec["depends_on"]
    goal_audit_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_goal_completion_audit"
    )
    assert "runs/engine_refinement_claim_evidence_priority_packet_current.json" in goal_audit_spec["depends_on"]
    assert "engine_refinement_claim_evidence_priority_packet_blocked_semantic_ready" in status_ids
    assert "product_ledger_privacy_scan_semantic_ready" in status_ids
    assert "python3 tools/build_product_ai_report_explanation_packet.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_ai_report_ux_contract.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_pose_sampling_readiness.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_trajectory_sla_contract.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_residual_shadow_ab.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_residual_force_derivation_validation.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_production_ai_promotion_workbench.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_execution_work_order.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_execution_preflight.py" in mod.RELEASE_REFRESH_COMMANDS
    assert (
        "python3 tools/build_local_delivery_environment_manifest.py --accelerator-env "
        "TORCH_BLAS_PREFER_HIPBLASLT=0 --no-probe-accelerator-commands"
    ) in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_wetlab_selected_allatom_gate_burndown_packet.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_bundle_contract.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_delivery_evidence_contract.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_pilot_packet_contract.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_api_contract.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_service_boundary_contract.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/product/build_self_hosted_license_distribution_audit.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_third_party_license_review_gate.py" in mod.RELEASE_REFRESH_COMMANDS
    assert mod.RELEASE_REFRESH_COMMANDS.count("python3 tools/build_product_ai_decision_graph_contract.py") == 2
    assert "python3 tools/product/build_engine_refinement_tier_readiness.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/product/build_refine_tier_public_benchmark_readiness.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/product/build_engine_refinement_claim_evidence_priority_packet.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/product/build_product_launch_r4_preflight.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_ledger_privacy_scan.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_scope_breadth_closure_checklist.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_scope_breadth_evidence_receipt.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_scope_breadth_evidence_priority_packet.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_job_orchestration_contract.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_goal_operator_intake_kit.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_goal_api_surface_contract.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_goal_bottleneck_briefing.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_full_commercial_blocker_evidence_matrix.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_commercial_readiness_operator_packet.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_commercial_readiness_operator_packet_freshness.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_commercial_readiness_execution_ladder.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_commercial_readiness_handoff_bundle.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_rollout_execution_smoke_receipt.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_deploy_ops_legal_gap_closure.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_science_claim_promotion_gap_closure.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_master_gap_closure_rollup.py" in mod.RELEASE_REFRESH_COMMANDS
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_scope_breadth_closure_checklist.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_scope_breadth_evidence_receipt.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_scope_breadth_evidence_receipt.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_scope_breadth_evidence_priority_packet.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_scope_breadth_evidence_priority_packet.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 deploy/product_release_bundle.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index(
        "python3 tools/product/build_refine_tier_public_benchmark_readiness.py"
    ) < mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/product/build_engine_refinement_tier_readiness.py")
    assert mod.RELEASE_REFRESH_COMMANDS.index(
        "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py"
    ) < mod.RELEASE_REFRESH_COMMANDS.index(
        "python3 tools/product/build_engine_refinement_claim_evidence_priority_packet.py"
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index(
        "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py"
    ) < mod.RELEASE_REFRESH_COMMANDS.index(
        "python3 tools/product/build_engine_refinement_claim_evidence_priority_packet.py"
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_goal_completion_audit.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_operator_action_board.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_operator_action_board.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_operator_intake_kit.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_operator_intake_kit.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_bottleneck_briefing.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_bottleneck_briefing.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_full_commercial_blocker_evidence_matrix.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_full_commercial_blocker_evidence_matrix.py") < (
        _last_refresh_index("python3 tools/build_product_release_source_of_truth_gate.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_residual_shadow_ab.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_residual_model_registry.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_residual_model_registry.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_residual_force_derivation_validation.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_residual_force_derivation_validation.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_production_ai_checkpoint_readiness.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_production_ai_checkpoint_readiness.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_production_ai_promotion_workbench.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_production_ai_promotion_workbench.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_production_ai_registry_promotion_operator_receipt.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_production_ai_registry_promotion_operator_receipt.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index(
            "python3 tools/product/build_production_ai_registry_promotion_priority_packet.py"
        )
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_execution_work_order.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_execution_preflight.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_execution_preflight.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_bundle_contract.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_api_docking_dispatch_e2e_evidence.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_job_orchestration_contract.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_job_orchestration_contract.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/product/build_restricted_unattended_execution_readiness.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index(
        "python3 tools/build_local_delivery_environment_manifest.py --accelerator-env "
        "TORCH_BLAS_PREFER_HIPBLASLT=0 --no-probe-accelerator-commands"
    ) < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_delivery_evidence_contract.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_wetlab_selected_allatom_gate_burndown_packet.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_delivery_evidence_contract.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_bundle_contract.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_delivery_evidence_contract.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_delivery_evidence_contract.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_pilot_packet_contract.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_pilot_packet_contract.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_api_contract.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_api_contract.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_service_boundary_contract.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_service_boundary_contract.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_capability_surface_contract.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_service_boundary_contract.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_independence_gate.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_independence_gate.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/product/build_self_hosted_license_distribution_audit.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/product/build_self_hosted_license_distribution_audit.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_third_party_license_review_gate.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_third_party_license_review_gate.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 deploy/product_release_bundle.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_pose_sampling_readiness.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_trajectory_sla_contract.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_trajectory_sla_contract.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 deploy/product_release_bundle.py")
    )
    decision_graph_indices = [
        index
        for index, command in enumerate(mod.RELEASE_REFRESH_COMMANDS)
        if command == "python3 tools/build_product_ai_decision_graph_contract.py"
    ]
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_pose_sampling_readiness.py") < (
        decision_graph_indices[0]
    )
    assert decision_graph_indices[0] < mod.RELEASE_REFRESH_COMMANDS.index(
        "python3 tools/build_product_ai_report_explanation_packet.py"
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_ai_report_ux_contract.py") < (
        decision_graph_indices[1]
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_api_surface_contract.py") < (
        _last_refresh_index("python3 tools/build_product_release_source_of_truth_gate.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_api_surface_contract.py") < (
        _last_refresh_index("python3 tools/build_goal_release_decision_gate.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_bottleneck_briefing.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_ledger_privacy_scan.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_full_commercial_blocker_evidence_matrix.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_handoff_bundle.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_operator_packet.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_operator_packet_freshness.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_operator_packet_freshness.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_execution_ladder.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_execution_ladder.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_handoff_bundle.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_handoff_bundle.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_ledger_privacy_scan.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_rollout_execution_readiness.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_rollout_execution_smoke_receipt.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_rollout_execution_smoke_receipt.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_deploy_ops_legal_gap_closure.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_deploy_ops_legal_gap_closure.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_master_gap_closure_rollup.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_science_claim_promotion_gap_closure.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_master_gap_closure_rollup.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_master_gap_closure_rollup.py") < (
        _last_refresh_index("python3 tools/build_product_release_source_of_truth_gate.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_readiness_rollup.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_release_source_of_truth_gate.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_release_source_of_truth_gate.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_release_decision_gate.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_release_decision_gate.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_goal_completion_audit.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/product/build_engine_refinement_tier_readiness.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/product/build_engine_refinement_claim_evidence_receipt.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/product/build_engine_refinement_claim_evidence_receipt.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/product/build_product_launch_r4_preflight.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_goal_completion_audit.py") < (
        max(
            index
            for index, command in enumerate(mod.RELEASE_REFRESH_COMMANDS)
            if command == "python3 deploy/product_release_bundle.py"
        )
    )


def test_release_source_of_truth_blocks_fresh_but_semantically_blocked_report(tmp_path: Path) -> None:
    report = tmp_path / "runs" / "product_ai_report_ux_contract_current.json"
    _write_json(
        report,
        {
            "summary": {
                "status": "blocked_product_ai_report_ux_contract",
                "ai_report_ux_ready": False,
                "customer_report_viewer_binding_ready": False,
            }
        },
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[],
        status_specs=[
            {
                "artifact_id": "product_ai_report_ux_contract_semantic_ready",
                "artifact_path": "runs/product_ai_report_ux_contract_current.json",
                "builder_command": "python3 tools/build_product_ai_report_ux_contract.py",
                "required_status": "product_ai_report_ux_contract_ready",
                "required_true_fields": ["ai_report_ux_ready", "customer_report_viewer_binding_ready"],
            }
        ],
        readme_paths=[],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_release_source_of_truth_gate"
    assert summary["semantic_status_row_count"] == 1
    assert summary["semantic_status_blocker_count"] == 1
    row = payload["rows"][0]
    assert row["row_type"] == "artifact_semantic_status"
    assert row["observed_status"] == "blocked_product_ai_report_ux_contract"
    assert row["missing_true_fields"] == ["ai_report_ux_ready", "customer_report_viewer_binding_ready"]


def test_release_source_of_truth_blocks_semantic_status_when_required_int_fields_missing(tmp_path: Path) -> None:
    service_boundary = tmp_path / "runs" / "product_service_boundary_contract_current.json"
    _write_json(
        service_boundary,
        {
            "summary": {
                "status": "product_service_boundary_contract_ready",
                "service_boundary_ready": True,
                "console_script_ready": True,
                "api_route_count": 46,
                "missing_api_route_count": 0,
            }
        },
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[],
        status_specs=[
            {
                "artifact_id": "product_service_boundary_contract_semantic_ready",
                "artifact_path": "runs/product_service_boundary_contract_current.json",
                "builder_command": "python3 tools/build_product_service_boundary_contract.py",
                "required_status": "product_service_boundary_contract_ready",
                "required_true_fields": ["service_boundary_ready", "console_script_ready"],
                "required_int_min_fields": {"api_route_count": 1, "cli_command_count": 1},
                "required_int_exact_fields": {
                    "missing_api_route_count": 0,
                    "missing_cli_command_count": 0,
                    "artifact_registry_mismatch_count": 0,
                },
            }
        ],
        readme_paths=[],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_release_source_of_truth_gate"
    assert summary["semantic_status_blocker_count"] == 1
    row = payload["rows"][0]
    assert row["failed_int_min_fields"] == ["cli_command_count"]
    assert row["failed_int_exact_fields"] == [
        "missing_cli_command_count",
        "artifact_registry_mismatch_count",
    ]
    assert "failed_int_min_fields=1" in row["observed"]
    assert "failed_int_exact_fields=2" in row["observed"]


def test_release_source_of_truth_blocks_semantic_status_when_required_text_fields_mismatch(tmp_path: Path) -> None:
    action_board = tmp_path / "runs" / "goal_operator_action_board_current.json"
    _write_json(
        action_board,
        {
            "summary": {
                "status": "operator_actions_required",
                "product_goal_release_blocker_fail_count": 2,
                "product_goal_primary_release_blocker_requirement_id": "R9_engine_refinement_claim_promotion",
                "product_goal_primary_release_blocker_tier": "full_commercial_scope",
                "product_goal_primary_release_blocker": "engine_refinement_claim_promotion_not_ready",
                "primary_release_blocker_action_id": "product_engine_refinement:resolve_claim_promotion",
            }
        },
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[],
        status_specs=[
            {
                "artifact_id": "goal_operator_action_board_primary_release_blocker_semantic_ready",
                "artifact_path": "runs/goal_operator_action_board_current.json",
                "builder_command": "python3 tools/build_goal_operator_action_board.py",
                "required_status": "operator_actions_required",
                "required_int_exact_fields": {
                    "product_goal_release_blocker_fail_count": 2,
                },
                "required_text_exact_fields": {
                    "product_goal_primary_release_blocker_requirement_id": "R8_full_scope_claim_closure",
                    "product_goal_primary_release_blocker_tier": "full_commercial_scope",
                    "product_goal_primary_release_blocker": "full_scope_claim_closure_not_ready",
                    "primary_release_blocker_action_id": (
                        "product_scope_expansion:resolve_full_scope_breadth_evidence_receipt"
                    ),
                    "primary_release_blocker_action_required_input": (
                        "config/product_scope_breadth_evidence_receipt_current.csv"
                    ),
                },
            }
        ],
        readme_paths=[],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_release_source_of_truth_gate"
    assert summary["semantic_status_blocker_count"] == 1
    row = payload["rows"][0]
    assert row["failed_text_exact_fields"] == [
        "product_goal_primary_release_blocker_requirement_id",
        "product_goal_primary_release_blocker",
        "primary_release_blocker_action_id",
        "primary_release_blocker_action_required_input",
    ]
    assert "failed_text_exact_fields=4" in row["observed"]


def test_release_source_of_truth_blocks_goal_api_surface_contract_semantic_count_regression(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / "runs" / "goal_api_surface_contract_current.json",
        {
            "summary": {
                "status": "goal_api_surface_contract_ready",
                "surface_ready": True,
                "blocker_count": 0,
                "missing_status_key_count": 1,
                "missing_full_commercial_visibility_token_count": 0,
                "missing_fail_closed_flag_count": 0,
            }
        },
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[],
        status_specs=[
            {
                "artifact_id": "goal_api_surface_contract_semantic_ready",
                "artifact_path": "runs/goal_api_surface_contract_current.json",
                "builder_command": "python3 tools/build_goal_api_surface_contract.py",
                "required_status": "goal_api_surface_contract_ready",
                "required_true_fields": ["surface_ready"],
                "required_int_exact_fields": {
                    "blocker_count": 0,
                    "missing_status_key_count": 0,
                    "missing_full_commercial_visibility_token_count": 0,
                    "missing_fail_closed_flag_count": 0,
                },
            }
        ],
        readme_paths=[],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_release_source_of_truth_gate"
    assert summary["semantic_status_blocker_count"] == 1
    row = payload["rows"][0]
    assert row["failed_int_exact_fields"] == ["missing_status_key_count"]
    assert "failed_int_exact_fields=1" in row["observed"]


def test_release_source_of_truth_blocks_full_commercial_matrix_diagnostic_regression(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / "runs" / "product_full_commercial_blocker_evidence_matrix_current.json",
        {
            "summary": {
                "status": "blocked_product_full_commercial_blocker_evidence_matrix",
                "release_blocker_visibility_ready": True,
                "blocked_matrix_row_count": 12,
                "approval_token_count": 2,
                "scope_receipt_blocked_row_count": 6,
                "engine_receipt_blocked_row_count": 6,
                "first_blocked_release_blocker_id": "R9_engine_refinement_claim_promotion",
                "first_blocked_evidence_row_id": "public_benchmark_gate_not_ready",
                "first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
                "first_blocked_expected_evidence_status": "refine_tier_public_benchmark_ready",
                "first_blocked_observed_evidence_status": "missing",
                "scope_receipt_most_common_row_blocker": "operator_placeholders_unfilled",
                "engine_receipt_most_common_row_blocker": "operator_placeholders_unfilled",
            }
        },
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[],
        status_specs=[
            {
                "artifact_id": "product_full_commercial_blocker_evidence_matrix_semantic_ready",
                "artifact_path": "runs/product_full_commercial_blocker_evidence_matrix_current.json",
                "builder_command": "python3 tools/build_product_full_commercial_blocker_evidence_matrix.py",
                "required_status": "blocked_product_full_commercial_blocker_evidence_matrix",
                "required_true_fields": ["release_blocker_visibility_ready"],
                "required_int_exact_fields": {
                    "blocked_matrix_row_count": 12,
                    "approval_token_count": 2,
                    "scope_receipt_blocked_row_count": 6,
                    "engine_receipt_blocked_row_count": 6,
                },
                "required_text_exact_fields": {
                    "first_blocked_release_blocker_id": "R8_full_scope_claim_closure",
                    "first_blocked_evidence_row_id": "direct_binding_evidence_missing",
                    "first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
                    "first_blocked_expected_evidence_status": (
                        "product_scope_transporter_direct_binding_evidence_ready"
                    ),
                    "first_blocked_observed_evidence_status": "missing",
                    "scope_receipt_most_common_row_blocker": "operator_placeholders_unfilled",
                    "engine_receipt_most_common_row_blocker": "operator_placeholders_unfilled",
                },
            }
        ],
        readme_paths=[],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_release_source_of_truth_gate"
    assert summary["semantic_status_blocker_count"] == 1
    row = payload["rows"][0]
    assert row["failed_text_exact_fields"] == [
        "first_blocked_release_blocker_id",
        "first_blocked_evidence_row_id",
        "first_blocked_expected_evidence_status",
    ]
    assert "failed_text_exact_fields=3" in row["observed"]


def test_release_source_of_truth_blocks_minimal_bundle_fixture_semantics(tmp_path: Path) -> None:
    bundle = tmp_path / "runs" / "product_bundle_contract_current.json"
    _write_json(
        bundle,
        {
            "summary": {
                "status": "product_bundle_contract_ready",
                "bundle_validation_command_matches": True,
                "artifact_count": 1,
                "bundle_unknown_arg_count": 0,
            }
        },
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[],
        status_specs=[
            {
                "artifact_id": "product_bundle_contract_semantic_ready",
                "artifact_path": "runs/product_bundle_contract_current.json",
                "builder_command": "python3 tools/build_product_bundle_contract.py",
                "required_status": "product_bundle_contract_ready",
                "required_true_fields": [
                    "bundle_validation_command_matches",
                    "bundle_validation_present",
                    "bundle_validation_passed",
                    "bundle_assembled",
                ],
                "required_int_min_fields": {"artifact_count": 1},
                "required_int_exact_fields": {"blocker_count": 0, "bundle_unknown_arg_count": 0},
            }
        ],
        readme_paths=[],
    )

    assert payload["summary"]["status"] == "blocked_product_release_source_of_truth_gate"
    row = payload["rows"][0]
    assert row["missing_true_fields"] == [
        "bundle_validation_present",
        "bundle_validation_passed",
        "bundle_assembled",
    ]
    assert row["failed_int_exact_fields"] == ["blocker_count"]


def test_release_source_of_truth_accepts_semantic_status_required_int_fields(tmp_path: Path) -> None:
    service_boundary = tmp_path / "runs" / "product_service_boundary_contract_current.json"
    _write_json(
        service_boundary,
        {
            "summary": {
                "status": "product_service_boundary_contract_ready",
                "service_boundary_ready": True,
                "console_script_ready": True,
                "api_route_count": 48,
                "cli_command_count": 25,
                "missing_api_route_count": 0,
                "missing_cli_command_count": 0,
                "artifact_registry_mismatch_count": 0,
            }
        },
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[],
        status_specs=[
            {
                "artifact_id": "product_service_boundary_contract_semantic_ready",
                "artifact_path": "runs/product_service_boundary_contract_current.json",
                "builder_command": "python3 tools/build_product_service_boundary_contract.py",
                "required_status": "product_service_boundary_contract_ready",
                "required_true_fields": ["service_boundary_ready", "console_script_ready"],
                "required_int_min_fields": {"api_route_count": 1, "cli_command_count": 1},
                "required_int_exact_fields": {
                    "missing_api_route_count": 0,
                    "missing_cli_command_count": 0,
                    "artifact_registry_mismatch_count": 0,
                },
            }
        ],
        readme_paths=[],
    )

    assert payload["summary"]["status"] == "product_release_source_of_truth_gate_ready"
    row = payload["rows"][0]
    assert row["failed_int_min_fields"] == []
    assert row["failed_int_exact_fields"] == []


def test_release_source_of_truth_accepts_full_commercial_release_blocker_semantics(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "runs" / "product_goal_completion_audit_current.json",
        {
            "summary": {
                "status": "blocked_product_goal_completion_audit",
                "commercial_independence_ready": True,
                "restricted_delivery_complete": True,
                "release_blocker_fail_count": 2,
                "primary_release_blocker_requirement_id": "R8_full_scope_claim_closure",
                "primary_release_blocker_tier": "full_commercial_scope",
                "primary_release_blocker": "full_scope_claim_closure_not_ready",
            }
        },
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[],
        status_specs=[
            {
                "artifact_id": "product_goal_completion_audit_full_commercial_release_blockers_semantic_ready",
                "artifact_path": "runs/product_goal_completion_audit_current.json",
                "builder_command": "python3 tools/build_product_goal_completion_audit.py",
                "required_status": "blocked_product_goal_completion_audit",
                "required_true_fields": [
                    "commercial_independence_ready",
                    "restricted_delivery_complete",
                ],
                "required_int_exact_fields": {
                    "release_blocker_fail_count": 2,
                },
                "required_text_exact_fields": {
                    "primary_release_blocker_requirement_id": "R8_full_scope_claim_closure",
                    "primary_release_blocker_tier": "full_commercial_scope",
                    "primary_release_blocker": "full_scope_claim_closure_not_ready",
                },
            }
        ],
        readme_paths=[],
    )

    assert payload["summary"]["status"] == "product_release_source_of_truth_gate_ready"
    row = payload["rows"][0]
    assert row["failed_text_exact_fields"] == []
    assert row["required_text_exact_fields"]["primary_release_blocker_requirement_id"] == (
        "R8_full_scope_claim_closure"
    )


def test_release_source_of_truth_accepts_top_level_release_bundle_status(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_bundle_current.json",
        {
            "status": "release_bundle_ready_for_operator_review",
            "release_bundle_ready": True,
            "blocker_count": 0,
        },
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[],
        status_specs=[
            {
                "artifact_id": "product_release_bundle_semantic_ready",
                "artifact_path": "runs/product_release_bundle_current.json",
                "builder_command": "python3 deploy/product_release_bundle.py",
                "required_status": "release_bundle_ready_for_operator_review",
                "required_true_fields": ["release_bundle_ready"],
            }
        ],
        readme_paths=[],
    )

    assert payload["summary"]["status"] == "product_release_source_of_truth_gate_ready"
    assert payload["summary"]["semantic_status_blocker_count"] == 0
    row = payload["rows"][0]
    assert row["status"] == "pass"
    assert row["observed_status"] == "release_bundle_ready_for_operator_review"
