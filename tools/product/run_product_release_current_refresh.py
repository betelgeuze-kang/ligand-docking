#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import shlex
import subprocess
from pathlib import Path
from typing import Any

from tools.product.build_product_release_source_of_truth_gate import RELEASE_REFRESH_COMMANDS

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_release_current_refresh_plan_current.json"
DEFAULT_OUT_MD = "runs/product_release_current_refresh_plan_current.md"
DEFAULT_COMMAND_TIMEOUT_SECONDS = 420

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
            "row_count": 96,
            "artifact_row_count": 64,
            "semantic_status_row_count": 30,
            "readme_row_count": 2,
            "pass_count": 96,
            "release_refresh_command_count": 89,
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
            "master_gap_closure_rollup_recorded",
            "master_gap_closure_rollup_science_claim_release_blocker",
            "science_claim_promotion_gap_closure_recorded",
            "science_claim_promotion_gap_closure_gpcr_release_blocker",
            "science_claim_promotion_gap_closure_openmm_release_blocker",
            "api_runner_profile_promotion_operator_receipt_recorded",
            "product_scope_breadth_evidence_receipt_recorded",
            "engine_refinement_claim_evidence_receipt_recorded",
            "engine_refinement_claim_evidence_priority_packet_recorded",
            "engine_refinement_claim_evidence_priority_packet_ready",
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
            "master_gap_closure_rollup_all_gaps_closed",
            "master_gap_closure_rollup_claim_promotion_allowed",
            "science_claim_promotion_gap_closure_all_gaps_closed",
            "science_claim_promotion_gap_closure_claim_promotion_allowed",
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
            "master_gap_closure_rollup_open_gap_count": 1,
            "master_gap_closure_rollup_closed_gap_count": 8,
            "master_gap_closure_rollup_release_blocker_row_count": 1,
            "science_claim_promotion_gap_closure_open_gap_count": 2,
            "science_claim_promotion_gap_closure_closed_gap_count": 3,
            "science_claim_promotion_gap_closure_release_blocker_row_count": 2,
        },
        "required_text_exact_fields": {
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
            "science_claim_promotion_gap_closure_status": (
                "blocked_science_claim_promotion_gap_closure"
            ),
            "science_claim_promotion_gap_closure_open_gap_ids_joined": "SCI-GPCR;SCI-OPENMM",
            "science_claim_promotion_gap_closure_closed_gap_ids_joined": (
                "SCI-TRANS;SCI-CA2-PXR;SCI-WETLAB"
            ),
            "science_claim_promotion_gap_closure_current_primary_open_gap_id": "SCI-GPCR",
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


def _run_command(command: str, *, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
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
    required_text_exact_fields = {
        str(field): str(expected)
        for field, expected in (spec.get("required_text_exact_fields") or {}).items()
    }
    missing_true_fields = [field for field in required_true_fields if summary.get(field) is not True]
    nonzero_fields = [field for field in required_zero_fields if _int(summary.get(field)) != 0]
    failed_int_exact_fields = [
        field for field, expected in required_int_exact_fields.items() if _int(summary.get(field)) != expected
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
        "required_text_exact_fields": required_text_exact_fields,
        "failed_text_exact_fields": failed_text_exact_fields,
        "observed": (
            f"status={observed_status};missing_true_fields={len(missing_true_fields)};"
            f"nonzero_fields={len(nonzero_fields)};"
            f"failed_int_exact_fields={len(failed_int_exact_fields)};"
            f"failed_text_exact_fields={len(failed_text_exact_fields)}"
        ),
        "required": (
            f"status={required_status};true={','.join(required_true_fields) or 'none'};"
            f"zero={','.join(required_zero_fields) or 'none'};"
            f"int_exact={','.join(required_int_exact_fields) or 'none'};"
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
