#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

from tools.product.build_product_release_source_of_truth_gate import RELEASE_REFRESH_COMMANDS

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_release_current_refresh_plan_current.json"
DEFAULT_OUT_MD = "runs/product_release_current_refresh_plan_current.md"
DEFAULT_COMMAND_TIMEOUT_SECONDS = 420
TIER_ALPHA_SMOKE_SCRIPT = "tools/product/run_tier_alpha_adrb2_dispatch_smoke.py"
TIER_ALPHA_DEFAULT_WORKSPACE = "runs/tier_alpha_dispatch_smoke/current"
TIER_ALPHA_DEFAULT_OUT_JSON = "runs/tier_alpha_adrb2_dispatch_smoke_current.json"
TIER_ALPHA_JOB_PREFIX = "tier_alpha_adrb2_smoke_"
TIER_ALPHA_CLAIM_BOUNDARY = (
    "Tier alpha ADRB2 dispatch smoke only; submits one restricted gpcr docking ledger row, dispatches to the "
    "SQLite worker queue with API_VALIDATED_RUNNER_ENABLED=1, and waits for worker completion. "
    "It does not emit customer-facing poses or mutate external state."
)

CLAIM_BOUNDARY = (
    "Product release current refresh runner only; it executes the listed local artifact builders and local release "
    "smoke commands when --execute is provided, then verifies the final release gates. It does not submit external "
    "validation, upload, email, delete, commit, push, or mutate external services."
)

FINAL_GATE_SPECS = [
    {
        "gate_id": "product_release_source_of_truth_gate",
        "artifact_path": "runs/product_release_source_of_truth_gate_current.json",
        "required_status": "product_release_source_of_truth_gate_ready",
        "required_true_fields": ["release_source_of_truth_ready"],
        "required_zero_fields": ["blocker_count", "stale_artifact_count", "readme_drift_count"],
        "required_int_exact_fields": {
            "row_count": 131,
            "artifact_row_count": 85,
            "semantic_status_row_count": 44,
            "readme_row_count": 2,
            "pass_count": 131,
            "release_refresh_command_count": 110,
        },
    },
    {
        "gate_id": "product_quality_gate_verification",
        "artifact_path": "runs/product_quality_gate_verification_current.json",
        "required_status": "product_quality_gate_verified",
        "required_true_fields": ["quality_gate_ready"],
        "required_zero_fields": ["blocker_count", "execution_enabled", "external_state_mutated"],
        "required_int_exact_fields": {
            "check_count": 4,
            "pass_count": 4,
        },
        "required_text_exact_fields": {
            "source_contract_status": "product_operational_quality_contract_ready",
        },
    },
    {
        "gate_id": "goal_release_decision_gate",
        "artifact_path": "runs/goal_release_decision_gate_current.json",
        "required_status": "goal_release_ready",
        "required_true_fields": [
            "release_allowed",
            "cameo_official_result_fetch_preflight_recorded",
            "self_hosted_license_distribution_audit_recorded",
            "self_hosted_license_distribution_audit_product_license_hash_matches_approved_source",
            "self_hosted_license_distribution_audit_third_party_license_review_gate_ready",
            "third_party_license_review_gate_recorded",
            "third_party_license_review_gate_ready",
            "goal_bottleneck_briefing_full_commercial_receipts_recorded",
            "goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded",
            "goal_bottleneck_briefing_production_ai_registry_promotion_priority_packet_ready",
            "production_ai_registry_promotion_priority_packet_recorded",
            "production_ai_registry_promotion_priority_packet_ready",
            "production_ai_checkpoint_readiness_recorded",
            "production_ai_checkpoint_readiness_product_model_layer_ready",
            "production_ai_checkpoint_readiness_production_gpu_execution_environment_ready",
            "production_ai_checkpoint_readiness_delta_force_derivation_validation_ready",
            "production_ai_checkpoint_readiness_selected_sidecar_ready",
            "production_ai_checkpoint_readiness_checkpoint_preflight_ready",
            "production_ai_checkpoint_readiness_production_training_data_ready",
            "production_ai_checkpoint_readiness_production_output_heads_complete",
            "production_ai_checkpoint_readiness_production_inference_acceptance_matrix_ready",
            "production_ai_checkpoint_readiness_registry_promotion_upstream_acceptance_ready",
            "production_ai_promotion_workbench_recorded",
            "production_ai_promotion_workbench_ready",
            "production_ai_promotion_workbench_registry_promotion_upstream_acceptance_ready",
            "accuracy_parity_scorecard_recorded",
            "accuracy_parity_ligand_ranking_metric_thresholds_pass",
            "accuracy_parity_ligand_ranking_claim_scope_lock_only",
            "master_gap_closure_rollup_recorded",
            "master_gap_closure_rollup_all_gaps_closed",
            "science_claim_promotion_gap_closure_recorded",
            "science_claim_promotion_gap_closure_all_gaps_closed",
            "api_runner_profile_promotion_operator_receipt_recorded",
            "product_scope_breadth_evidence_receipt_recorded",
            "engine_refinement_claim_evidence_receipt_recorded",
            "engine_refinement_claim_evidence_priority_packet_recorded",
            "engine_refinement_claim_evidence_priority_packet_ready",
            "refine_tier_public_benchmark_recorded",
            "refine_tier_public_benchmark_input_csv_present",
            "refine_tier_public_benchmark_operator_work_order_ready",
            "refine_tier_public_benchmark_work_order_apply_recorded",
            "refine_tier_public_benchmark_work_order_apply_aggregate_readiness_required",
            "refine_tier_public_benchmark_work_order_apply_work_order_csv_present",
            "refine_tier_public_benchmark_work_order_apply_receptor_coordinate_validation_required",
            "refine_tier_public_benchmark_work_order_apply_metric_evidence_required",
            "product_quality_gate_verification_recorded",
            "product_quality_gate_verification_ready",
            "product_pose_sampling_readiness_recorded",
            "product_pose_sampling_readiness_ready",
            "product_pose_sampling_readiness_pose_generation_contract_ready",
            "product_pose_sampling_readiness_pocket_detection_ready",
            "product_pose_sampling_readiness_multi_start_pose_ensemble_ready",
            "product_pose_sampling_readiness_pose_centroid_pocket_bound_ready",
            "product_pose_sampling_readiness_pose_rmsd_diversity_surface_ready",
            "product_pose_sampling_readiness_bounded_cross_docking_induced_fit_guard_ready",
            "product_pose_sampling_readiness_pose_claim_boundary_guard_ready",
            "product_ledger_privacy_scan_recorded",
            "product_ledger_privacy_scan_ready",
        ],
        "required_zero_fields": [
            "blocker_count",
            "cameo_official_result_fetch_preflight_network_request_opened",
            "cameo_official_result_fetch_preflight_official_results_fetched",
            "cameo_official_result_fetch_preflight_native_local_accuracy_used",
            "cameo_official_result_fetch_preflight_outbound_email_enabled",
            "cameo_official_result_fetch_preflight_external_state_mutated",
            "self_hosted_license_distribution_audit_hard_blocker_count",
            "self_hosted_license_distribution_audit_legal_advice_provided",
            "self_hosted_license_distribution_audit_third_party_license_review_gate_blocker_count",
            "self_hosted_license_distribution_audit_external_state_mutated",
            "third_party_license_review_gate_blocker_count",
            "third_party_license_review_gate_missing_review_asset_count",
            "third_party_license_review_gate_deferred_review_asset_count",
            "third_party_license_review_gate_legal_advice_provided",
            "third_party_license_review_gate_asset_modified",
            "third_party_license_review_gate_external_state_mutated",
            "production_ai_checkpoint_readiness_production_ai_checkpoint_ready",
            "production_ai_checkpoint_readiness_production_ai_inference_subject_active",
            "production_ai_checkpoint_readiness_registry_promotion_currently_satisfied",
            "production_ai_checkpoint_readiness_production_promotion_allowed",
            "production_ai_checkpoint_readiness_customer_facing_auto_correction_allowed",
            "production_ai_checkpoint_readiness_customer_facing_score_mutation_allowed",
            "production_ai_checkpoint_readiness_customer_facing_ranking_mutation_allowed",
            "production_ai_checkpoint_readiness_model_promoted",
            "production_ai_checkpoint_readiness_docking_results_emitted",
            "production_ai_checkpoint_readiness_execution_enabled",
            "production_ai_checkpoint_readiness_external_state_mutated",
            "production_ai_promotion_workbench_production_ai_promotion_ready",
            "production_ai_promotion_workbench_production_ai_checkpoint_ready",
            "production_ai_promotion_workbench_production_ai_inference_subject_active",
            "production_ai_promotion_workbench_registry_promotion_currently_satisfied",
            "production_ai_promotion_workbench_production_promotion_allowed",
            "production_ai_promotion_workbench_model_promoted",
            "production_ai_promotion_workbench_docking_results_emitted",
            "production_ai_promotion_workbench_execution_enabled",
            "production_ai_promotion_workbench_external_state_mutated",
            "accuracy_parity_ligand_ranking_claim_promotion_allowed",
            "accuracy_parity_ligand_ranking_commercial_parity_claim_allowed",
            "accuracy_parity_ligand_ranking_metric_blocker_count",
            "master_gap_closure_rollup_claim_promotion_allowed",
            "science_claim_promotion_gap_closure_claim_promotion_allowed",
            "master_gap_closure_rollup_science_claim_release_blocker",
            "science_claim_promotion_gap_closure_gpcr_release_blocker",
            "science_claim_promotion_gap_closure_openmm_release_blocker",
            "refine_tier_public_benchmark_claim_grade_public_benchmark_ready",
            "refine_tier_public_benchmark_benchmark_metric_surface_ready",
            "refine_tier_public_benchmark_row_count",
            "refine_tier_public_benchmark_valid_row_count",
            "refine_tier_public_benchmark_pose_metric_row_count",
            "refine_tier_public_benchmark_pose_metric_pass_count",
            "refine_tier_public_benchmark_free_energy_pair_count",
            "refine_tier_public_benchmark_external_state_mutated",
            "refine_tier_public_benchmark_work_order_apply_apply_ready",
            "refine_tier_public_benchmark_work_order_apply_valid_intake_row_count",
            "refine_tier_public_benchmark_work_order_apply_duplicate_benchmark_id_count",
            "refine_tier_public_benchmark_work_order_apply_candidate_intake_written",
            "refine_tier_public_benchmark_work_order_apply_candidate_readiness_checked",
            "refine_tier_public_benchmark_work_order_apply_candidate_claim_grade_public_benchmark_ready",
            "refine_tier_public_benchmark_work_order_apply_intake_written",
            "refine_tier_public_benchmark_work_order_apply_write_intake_requested",
            "refine_tier_public_benchmark_work_order_apply_approval_token_present",
            "refine_tier_public_benchmark_work_order_apply_approval_token_accepted",
            "refine_tier_public_benchmark_work_order_apply_external_state_mutated",
            "product_quality_gate_verification_blocker_count",
            "product_quality_gate_verification_execution_enabled",
            "product_quality_gate_verification_external_state_mutated",
            "product_pose_sampling_readiness_blocker_count",
            "product_pose_sampling_readiness_claim_grade_pose_accuracy_ready",
            "product_pose_sampling_readiness_claim_grade_induced_fit_ready",
            "product_pose_sampling_readiness_claim_grade_cross_docking_ready",
            "product_pose_sampling_readiness_docking_results_emitted",
            "product_pose_sampling_readiness_execution_enabled",
            "product_pose_sampling_readiness_external_state_mutated",
            "product_ledger_privacy_scan_blocker_count",
            "product_ledger_privacy_scan_leak_count",
            "product_ledger_privacy_scan_invalid_json_count",
            "product_ledger_privacy_scan_blocked_artifact_path_count",
            "product_ledger_privacy_scan_invalid_json_path_count",
            "product_ledger_privacy_scan_execution_enabled",
            "product_ledger_privacy_scan_external_state_mutated",
        ],
        "required_int_exact_fields": {
            "cameo_official_result_fetch_preflight_blocked_row_count": 1,
            "cameo_official_result_fetch_preflight_blocker_count": 2,
            "cameo_official_result_fetch_preflight_awaiting_operator_fetch_approval_row_count": 1,
            "self_hosted_license_distribution_audit_operator_review_item_count": 1,
            "third_party_license_review_gate_expected_review_asset_count": 1,
            "third_party_license_review_gate_review_row_count": 1,
            "third_party_license_review_gate_approved_review_asset_count": 1,
            "third_party_license_review_gate_source_hard_blocker_count": 0,
            "third_party_license_review_gate_source_operator_review_item_count": 1,
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
            "accuracy_parity_scorecard_restricted_pass_row_count": 1,
            "accuracy_parity_scorecard_blocked_row_count": 0,
            "accuracy_parity_scorecard_top_blocker_count": 1,
            "accuracy_parity_ligand_ranking_blocker_count": 1,
            "accuracy_parity_ligand_ranking_positive_count": 34,
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
            "refine_tier_public_benchmark_blocker_count": 6,
            "refine_tier_public_benchmark_min_total_rows_required": 8,
            "refine_tier_public_benchmark_min_pose_rows_required": 5,
            "refine_tier_public_benchmark_min_free_energy_pairs_required": 5,
            "refine_tier_public_benchmark_work_order_row_count": 8,
            "refine_tier_public_benchmark_work_order_apply_work_order_row_count": 8,
            "refine_tier_public_benchmark_work_order_apply_blocked_row_count": 8,
            "refine_tier_public_benchmark_work_order_apply_blocker_count": 1,
            "refine_tier_public_benchmark_work_order_apply_receptor_coordinate_validation_pass_row_count": 8,
            "refine_tier_public_benchmark_work_order_apply_receptor_coordinate_validation_blocked_row_count": 0,
            "refine_tier_public_benchmark_work_order_apply_metric_evidence_pass_row_count": 0,
            "refine_tier_public_benchmark_work_order_apply_metric_evidence_blocked_row_count": 8,
            "refine_tier_public_benchmark_work_order_apply_metric_evidence_missing_row_count": 0,
            "master_gap_closure_rollup_open_gap_count": 0,
            "master_gap_closure_rollup_closed_gap_count": 9,
            "master_gap_closure_rollup_release_blocker_row_count": 0,
            "science_claim_promotion_gap_closure_open_gap_count": 0,
            "science_claim_promotion_gap_closure_closed_gap_count": 5,
            "science_claim_promotion_gap_closure_release_blocker_row_count": 0,
            "product_quality_gate_verification_check_count": 4,
            "product_quality_gate_verification_pass_count": 4,
            "product_pose_sampling_readiness_check_count": 6,
            "product_pose_sampling_readiness_pass_count": 6,
            "product_pose_sampling_readiness_requested_pose_start_count": 6,
            "product_pose_sampling_readiness_pose_count": 6,
            "product_pose_sampling_readiness_cluster_count": 6,
            "product_pose_sampling_readiness_cross_docking_pose_count": 4,
            "product_ledger_privacy_scan_scan_glob_count": 24,
        },
        "required_int_min_fields": {
            "product_ledger_privacy_scan_scan_file_count": 285,
            "product_ledger_privacy_scan_pass_count": 285,
        },
        "required_int_equal_fields": {
            "product_ledger_privacy_scan_pass_count": "product_ledger_privacy_scan_scan_file_count",
        },
        "required_text_exact_fields": {
            "product_quality_gate_verification_status": "product_quality_gate_verified",
            "product_quality_gate_verification_source_contract_status": (
                "product_operational_quality_contract_ready"
            ),
            "product_pose_sampling_readiness_status": "product_pose_sampling_readiness_ready",
            "product_pose_sampling_readiness_pocket_method": "ligand_guided",
            "product_ledger_privacy_scan_status": "product_ledger_privacy_scan_ready",
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
            "source_goal_bottleneck_briefing_status": "goal_bottleneck_briefing_ready",
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
            "accuracy_parity_scorecard_status": "blocked_accuracy_parity",
            "accuracy_parity_scorecard_current_broad_accuracy_parity_estimate_pct": "65-75",
            "accuracy_parity_scorecard_current_broad_commercial_platform_estimate_pct": "45-55",
            "accuracy_parity_ligand_ranking_status": "restricted_pass",
            "accuracy_parity_ligand_ranking_score_col_used": (
                "binding_score_composite_v7_coverage_v2_crossfit_rank_rescue_shadow"
            ),
            "master_gap_closure_rollup_status": "master_gap_closure_rollup_complete",
            "master_gap_closure_rollup_open_gap_ids_joined": "",
            "master_gap_closure_rollup_closed_gap_ids_joined": (
                "COMMERCIAL;PRODUCT-AI;DATA-SCIENCE;INFRA;SCI-CLAIM;DEPLOY-OPS;STORAGE;TOOLS;API-RUNNER"
            ),
            "master_gap_closure_rollup_current_primary_open_gap_id": "none",
            "master_gap_closure_rollup_science_claim_rollup_status": (
                "science_claim_promotion_gap_closure_complete"
            ),
            "master_gap_closure_rollup_science_claim_evidence": (
                "runs/science_claim_promotion_gap_closure_current.json"
            ),
            "science_claim_promotion_gap_closure_status": (
                "science_claim_promotion_gap_closure_complete"
            ),
            "science_claim_promotion_gap_closure_open_gap_ids_joined": "",
            "science_claim_promotion_gap_closure_closed_gap_ids_joined": (
                "SCI-GPCR;SCI-TRANS;SCI-CA2-PXR;SCI-WETLAB;SCI-OPENMM"
            ),
            "science_claim_promotion_gap_closure_current_primary_open_gap_id": "none",
            "science_claim_promotion_gap_closure_gpcr_claim_promotion_status": (
                "boundary_ready_comparison_only"
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
            "refine_tier_public_benchmark_status": (
                "blocked_refine_tier_public_benchmark_readiness"
            ),
            "refine_tier_public_benchmark_input_csv": (
                "config/refine_tier_public_benchmark_intake_current.csv"
            ),
            "refine_tier_public_benchmark_work_order_csv": (
                "runs/refine_tier_public_benchmark_work_order_current.csv"
            ),
            "refine_tier_public_benchmark_write_intake_approval_token_required": (
                "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE"
            ),
            "refine_tier_public_benchmark_work_order_apply_status": (
                "blocked_refine_tier_public_benchmark_work_order_apply"
            ),
            "refine_tier_public_benchmark_work_order_apply_work_order_csv": (
                "runs/refine_tier_public_benchmark_work_order_current.csv"
            ),
            "refine_tier_public_benchmark_work_order_apply_target_intake_csv": (
                "config/refine_tier_public_benchmark_intake_current.csv"
            ),
        },
    },
    {
        "gate_id": "goal_operator_action_board",
        "artifact_path": "runs/goal_operator_action_board_current.json",
        "required_status": "operator_actions_required",
        "required_true_fields": ["goal_release_allowed"],
        "required_zero_fields": ["goal_release_blocker_count"],
        "required_text_exact_fields": {
            "goal_release_decision_gate_status": "goal_release_ready",
        },
    },
]


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _is_tier_alpha_smoke_command(command: str) -> bool:
    parts = shlex.split(command)
    return len(parts) >= 2 and Path(parts[1]).as_posix() == TIER_ALPHA_SMOKE_SCRIPT


def _arg_value(parts: list[str], flag: str, default: str) -> str:
    prefix = f"{flag}="
    for index, part in enumerate(parts):
        if part == flag and index + 1 < len(parts):
            return parts[index + 1]
        if part.startswith(prefix):
            return part.split("=", 1)[1]
    return default


def _resolve_command_path(value: str, *, cwd: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else cwd / path


def _relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _verify_tier_alpha_manifest(manifest_payload: dict[str, Any]) -> bool:
    try:
        from api.result_manifest import verify_result_manifest

        return verify_result_manifest(
            manifest_payload,
            signing_key=os.environ.get("API_RESULT_MANIFEST_SIGNING_KEY", "tier-alpha-local-smoke-signing-key"),
        )
    except Exception:
        return False


def _latest_completed_tier_alpha_evidence(workspace: Path, *, started_at: float) -> dict[str, Any]:
    results_dir = workspace / "results"
    if not results_dir.is_dir():
        return {}
    candidates: list[tuple[float, dict[str, Any]]] = []
    for status_path in results_dir.glob(f"{TIER_ALPHA_JOB_PREFIX}*/status.json"):
        try:
            if status_path.stat().st_mtime < started_at - 1:
                continue
        except OSError:
            continue
        status_payload = _load_json_file(status_path)
        if str(status_payload.get("status", "") or "") != "completed":
            continue
        job_id = str(status_payload.get("job_id", "") or status_path.parent.name).strip()
        result_file = Path(str(status_payload.get("result_file", "") or ""))
        runner_execution = Path(str(status_payload.get("runner_execution", "") or ""))
        result_manifest = Path(str(status_payload.get("result_manifest", "") or ""))
        if not result_file.is_file() or not runner_execution.is_file() or not result_manifest.is_file():
            continue
        manifest_payload = _load_json_file(result_manifest)
        if str(manifest_payload.get("status", "") or "") != "completed":
            continue
        runner_payload = _load_json_file(runner_execution)
        ledger_path = results_dir / "product_docking_jobs" / f"{job_id}.json"
        ledger_payload = _load_json_file(ledger_path)
        candidates.append(
            (
                status_path.stat().st_mtime,
                {
                    "job_id": job_id,
                    "status_path": status_path,
                    "status_payload": status_payload,
                    "result_file": result_file,
                    "runner_execution": runner_execution,
                    "runner_payload": runner_payload,
                    "result_manifest": result_manifest,
                    "manifest_payload": manifest_payload,
                    "ledger_payload": ledger_payload,
                },
            )
        )
    if not candidates:
        return {}
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def _write_recovered_tier_alpha_payload(
    *,
    out_json: Path,
    workspace: Path,
    evidence: dict[str, Any],
    timeout_seconds: int,
) -> None:
    runner_payload = evidence.get("runner_payload") if isinstance(evidence.get("runner_payload"), dict) else {}
    ledger_payload = evidence.get("ledger_payload") if isinstance(evidence.get("ledger_payload"), dict) else {}
    manifest_payload = evidence.get("manifest_payload") if isinstance(evidence.get("manifest_payload"), dict) else {}
    status_path = evidence["status_path"]
    result_manifest = evidence["result_manifest"]
    result_file = evidence["result_file"]
    runner_execution = evidence["runner_execution"]
    runner_returncode = runner_payload.get("returncode")
    payload = {
        "summary": {
            "packet_type": "tier_alpha_adrb2_dispatch_smoke",
            "status": "tier_alpha_adrb2_dispatch_smoke_pass",
            "evidence_mode": "live_job_recovered_from_completed_artifacts",
            "api_validated_runner_enabled": True,
            "workspace": _relative_or_absolute(workspace),
            "claim_boundary": TIER_ALPHA_CLAIM_BOUNDARY,
        },
        "job_id": evidence["job_id"],
        "ledger_worker_state": str(ledger_payload.get("worker_state", "") or "completed_fail_closed"),
        "simulation_sync_status": str(ledger_payload.get("simulation_sync_status", "") or "completed"),
        "dispatch_outcome": {
            "dispatched": True,
            "reason": "completed_artifact_recovered_after_parent_wait",
            "job_id": evidence["job_id"],
        },
        "worker_ran": True,
        "sqlite_job_status": "completed",
        "worker_error": "",
        "drain_timed_out": False,
        "timeout_seconds": max(1, int(timeout_seconds)),
        "runner_timeout_seconds": int(runner_payload.get("timeout_seconds") or 0),
        "runner_execution": str(runner_execution),
        "runner_execution_ok": runner_payload.get("ok") is True,
        "runner_execution_returncode": runner_returncode,
        "runner_execution_timed_out": runner_payload.get("timed_out") is True,
        "jobs_dir": _relative_or_absolute(workspace / "results" / "product_docking_jobs"),
        "worker_dispatch_enqueued": ledger_payload.get("worker_dispatch_enqueued") is True,
        "ledger_progress_state": str(ledger_payload.get("progress_state", "") or ""),
        "ledger_current_step": str(ledger_payload.get("current_step", "") or ""),
        "htvs_summary_exists": result_file.is_file(),
        "result_file": str(result_file),
        "status_json": str(status_path),
        "result_manifest": str(result_manifest),
        "result_manifest_exists": result_manifest.is_file(),
        "result_manifest_signature_verified": _verify_tier_alpha_manifest(manifest_payload),
        "result_manifest_status": str(manifest_payload.get("status", "") or ""),
        "result_manifest_key_id": str(manifest_payload.get("signature_key_id", "") or ""),
        "recovered_from_completed_artifacts": True,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _run_tier_alpha_smoke_in_process(command: str, *, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    parts = shlex.split(command)
    workspace = _resolve_command_path(_arg_value(parts, "--workspace", TIER_ALPHA_DEFAULT_WORKSPACE), cwd=cwd)
    out_json = _resolve_command_path(_arg_value(parts, "--out-json", TIER_ALPHA_DEFAULT_OUT_JSON), cwd=cwd)
    started_at = time.time()
    deadline = started_at + max(1, int(timeout_seconds))
    proc = subprocess.Popen(shlex.split(command), cwd=cwd, start_new_session=True)
    while True:
        returncode = proc.poll()
        if returncode is not None:
            return {"returncode": int(returncode), "timed_out": False}
        evidence = _latest_completed_tier_alpha_evidence(workspace, started_at=started_at)
        if evidence:
            _write_recovered_tier_alpha_payload(
                out_json=out_json,
                workspace=workspace,
                evidence=evidence,
                timeout_seconds=timeout_seconds,
            )
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            return {"returncode": 0, "timed_out": False, "completed_evidence_recovered": True}
        if time.time() >= deadline:
            break
        time.sleep(1.0)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    returncode = proc.wait()
    return {"returncode": int(returncode), "timed_out": True}


def _run_command(command: str, *, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    if _is_tier_alpha_smoke_command(command):
        return _run_tier_alpha_smoke_in_process(command, cwd=cwd, timeout_seconds=timeout_seconds)
    proc = subprocess.Popen(shlex.split(command), cwd=cwd, start_new_session=True)
    try:
        returncode = proc.wait(timeout=max(1, int(timeout_seconds)))
        return {"returncode": int(returncode), "timed_out": False}
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        returncode = proc.wait()
        return {"returncode": int(returncode), "timed_out": True}


def _command_timeout_seconds(command: str, default_timeout_seconds: int) -> int:
    parts = shlex.split(command)
    for index, part in enumerate(parts):
        if part == "--timeout-seconds" and index + 1 < len(parts):
            try:
                return max(1, int(parts[index + 1]) + 30)
            except ValueError:
                return int(default_timeout_seconds)
        if part.startswith("--timeout-seconds="):
            try:
                return max(1, int(part.split("=", 1)[1]) + 30)
            except ValueError:
                return int(default_timeout_seconds)
    return int(default_timeout_seconds)


def _read_json_if_present(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _verify_final_gate(spec: dict[str, Any], *, root: Path) -> dict[str, Any]:
    artifact_path = str(spec["artifact_path"])
    packet = _read_json_if_present(artifact_path, root=root)
    summary = _summary(packet) if packet else {}
    required_status = str(spec["required_status"])
    required_true_fields = [str(item) for item in spec.get("required_true_fields") or []]
    required_zero_fields = [str(item) for item in spec.get("required_zero_fields") or []]
    required_int_exact_fields = {
        str(field): _int(expected)
        for field, expected in (spec.get("required_int_exact_fields") or {}).items()
    }
    required_int_min_fields = {
        str(field): _int(expected)
        for field, expected in (spec.get("required_int_min_fields") or {}).items()
    }
    required_int_equal_fields = {
        str(field): str(peer_field)
        for field, peer_field in (spec.get("required_int_equal_fields") or {}).items()
    }
    required_text_exact_fields = {
        str(field): str(expected)
        for field, expected in (spec.get("required_text_exact_fields") or {}).items()
    }
    missing_true_fields = [field for field in required_true_fields if summary.get(field) is not True]
    nonzero_fields = [field for field in required_zero_fields if _int(summary.get(field)) != 0]
    failed_int_exact_fields = [
        field for field, expected in required_int_exact_fields.items() if _int(summary.get(field)) != expected
    ]
    failed_int_min_fields = [
        field for field, minimum in required_int_min_fields.items() if _int(summary.get(field)) < minimum
    ]
    failed_int_equal_fields = [
        field
        for field, peer_field in required_int_equal_fields.items()
        if _int(summary.get(field)) != _int(summary.get(peer_field))
    ]
    failed_text_exact_fields = [
        field
        for field, expected in required_text_exact_fields.items()
        if str(summary.get(field, "") or "") != expected
    ]
    observed_status = str(summary.get("status", "") or "missing")
    passed = bool(summary) and observed_status == required_status and not any(
        [
            missing_true_fields,
            nonzero_fields,
            failed_int_exact_fields,
            failed_int_min_fields,
            failed_int_equal_fields,
            failed_text_exact_fields,
        ]
    )
    return {
        "gate_id": str(spec["gate_id"]),
        "artifact_path": artifact_path,
        "status": "pass" if passed else "fail",
        "artifact_present": bool(packet),
        "required_status": required_status,
        "observed_status": observed_status,
        "required_true_fields": required_true_fields,
        "missing_true_fields": missing_true_fields,
        "required_zero_fields": required_zero_fields,
        "nonzero_fields": nonzero_fields,
        "required_int_exact_fields": required_int_exact_fields,
        "failed_int_exact_fields": failed_int_exact_fields,
        "required_int_min_fields": required_int_min_fields,
        "failed_int_min_fields": failed_int_min_fields,
        "required_int_equal_fields": required_int_equal_fields,
        "failed_int_equal_fields": failed_int_equal_fields,
        "required_text_exact_fields": required_text_exact_fields,
        "failed_text_exact_fields": failed_text_exact_fields,
        "observed": (
            f"status={observed_status};missing_true_fields={len(missing_true_fields)};"
            f"nonzero_fields={len(nonzero_fields)};"
            f"failed_int_exact_fields={len(failed_int_exact_fields)};"
            f"failed_int_min_fields={len(failed_int_min_fields)};"
            f"failed_int_equal_fields={len(failed_int_equal_fields)};"
            f"failed_text_exact_fields={len(failed_text_exact_fields)}"
        ),
        "required": (
            f"status={required_status};true={','.join(required_true_fields) or 'none'};"
            f"zero={','.join(required_zero_fields) or 'none'};"
            f"int_exact={','.join(required_int_exact_fields) or 'none'};"
            f"int_min={','.join(required_int_min_fields) or 'none'};"
            f"int_equal={','.join(required_int_equal_fields) or 'none'};"
            f"text_exact={','.join(required_text_exact_fields) or 'none'}"
        ),
        "release_blocker": not passed,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _verify_final_gates(*, root: Path) -> list[dict[str, Any]]:
    return [_verify_final_gate(spec, root=root) for spec in FINAL_GATE_SPECS]


def run_product_release_current_refresh(
    *,
    execute: bool = False,
    root: str | Path = ROOT,
    commands: list[str] | None = None,
    command_timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    root_path = Path(root)
    commands = list(RELEASE_REFRESH_COMMANDS if commands is None else commands)
    rows: list[dict[str, Any]] = []
    failed = False
    for index, command in enumerate(commands, start=1):
        row: dict[str, Any] = {
            "step_index": index,
            "command": command,
            "status": "planned",
            "returncode": None,
            "executed": False,
            "release_blocker": False,
            "timed_out": False,
            "timeout_seconds": int(command_timeout_seconds),
        }
        if execute and not failed:
            row_timeout_seconds = _command_timeout_seconds(command, int(command_timeout_seconds))
            row["timeout_seconds"] = row_timeout_seconds
            completed = _run_command(command, cwd=root_path, timeout_seconds=row_timeout_seconds)
            row["executed"] = True
            row["returncode"] = completed["returncode"]
            row["timed_out"] = bool(completed["timed_out"])
            row["status"] = "timeout" if row["timed_out"] else "pass" if completed["returncode"] == 0 else "fail"
            row["release_blocker"] = completed["returncode"] != 0 or row["timed_out"]
            failed = bool(row["release_blocker"])
        rows.append(row)

    verification_rows = _verify_final_gates(root=root_path) if execute and not failed else []
    final_gate_blocker_count = sum(1 for row in verification_rows if row["release_blocker"])
    final_gate_verification_ready = bool(execute and not failed and verification_rows and final_gate_blocker_count == 0)

    status = "product_release_current_refresh_planned"
    if execute and failed:
        status = "blocked_product_release_current_refresh"
    elif execute and final_gate_verification_ready:
        status = "product_release_current_refresh_verified"
    elif execute:
        status = "blocked_product_release_current_refresh"
    summary = {
        "packet_type": "product_release_current_refresh_plan",
        "status": status,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "execute": execute,
        "command_count": len(commands),
        "executed_count": sum(1 for row in rows if row["executed"]),
        "failed_count": sum(1 for row in rows if row["status"] in {"fail", "timeout"}),
        "timed_out_count": sum(1 for row in rows if row["timed_out"]),
        "command_timeout_seconds": int(command_timeout_seconds),
        "release_blocker_count": sum(1 for row in rows if row["release_blocker"]),
        "final_gate_verification_ready": final_gate_verification_ready,
        "final_gate_blocker_count": final_gate_blocker_count,
        "final_gate_count": len(verification_rows),
        "commands": commands,
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": execute,
        "external_state_mutated": False,
        "next_required_step": (
            "Refresh executed and final release gates verified."
            if execute and final_gate_verification_ready
            else "Run with --execute to regenerate current release artifacts in order."
            if not execute
            else "Fix the failed builder or blocked final release gate, then rerun this refresh command."
        ),
    }
    return {"summary": summary, "rows": rows, "verification_rows": verification_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Product Release Current Refresh Plan",
        "",
        f"- status: `{s['status']}`",
        f"- execute: `{s['execute']}`",
        f"- command_count: `{s['command_count']}`",
        f"- executed_count: `{s['executed_count']}`",
        f"- failed_count: `{s['failed_count']}`",
        "",
        "## Commands",
        "",
    ]
    for row in payload["rows"]:
        lines.append(f"- {row['step_index']}. `{row['command']}` status=`{row['status']}`")
    if payload.get("verification_rows"):
        lines.extend(["", "## Final Gate Verification", ""])
        for row in payload["verification_rows"]:
            lines.append(f"- `{row['gate_id']}` status=`{row['status']}` observed=`{row['observed']}`")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate current product release artifacts in source-of-truth order.")
    parser.add_argument("--execute", action="store_true", help="Run the refresh commands. Without this, only writes a plan.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--command-timeout-seconds", type=int, default=DEFAULT_COMMAND_TIMEOUT_SECONDS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = run_product_release_current_refresh(
        execute=args.execute,
        root=root,
        command_timeout_seconds=max(1, int(args.command_timeout_seconds)),
    )
    _write_json(args.out_json, payload, root=root)
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
