from __future__ import annotations

import json
from pathlib import Path

from tools import build_goal_bottleneck_briefing as mod


def _release_gate() -> dict:
    return {
        "summary": {
            "status": "blocked_goal_release_decision",
            "release_allowed": False,
            "blocker_count": 5,
            "check_count": 15,
            "cleanup_completion_transition_approval_gated_reclaim_size_gb": 43.206,
            "cleanup_completion_ligand_heavy_candidate_size_gb": 6.011,
            "protected_cleanup_payload_size_gb": 396.794,
        }
    }


def _burndown() -> dict:
    return {
        "summary": {
            "status": "goal_release_burndown_work_order_ready",
            "approval_reclaim_size_gb": 49.216,
        },
        "rows": [
            {
                "sequence": 1,
                "phase": "P1_product_execution_and_bundle_validation",
                "lane_id": "commercial_product_release",
                "burndown_status": "approval_required",
                "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "release_checks": "product_architecture_release_ready;pilot_delivery_ready",
                "release_check_count": 2,
                "release_observed": "pilot_delivery_ready=false",
                "release_required": "pilot_delivery_ready=true",
                "requires_operator_action": True,
                "source_artifact": "runs/product_execution_work_order_current.json",
                "command": "python3 tools/run_ligand_htvs_pipeline.py --no-dry-run",
                "recommended_action": "Review and approve product execution.",
            },
            {
                "sequence": 3,
                "phase": "P2_cameo_official_validation_and_registration",
                "lane_id": "cameo_architecture_validation",
                "burndown_status": "official_results_required",
                "approval_token_required": "",
                "release_checks": "official_cameo_validation_evidence_ready;official_cameo_results_used",
                "release_check_count": 2,
                "release_observed": "official_cameo_results_used=false",
                "release_required": "official_cameo_results_used=true",
                "requires_operator_action": True,
                "source_artifact": "runs/cameo_official_results_intake_gate_current.json",
                "command": "python3 tools/build_cameo_official_results_intake_gate.py",
                "recommended_action": "Attach official CAMEO result rows.",
            },
            {
                "sequence": 6,
                "phase": "P3_cleanup_execution_or_policy_resolution",
                "lane_id": "cleanup_release",
                "burndown_status": "approval_required",
                "approval_token_required": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "release_checks": "transition_cleanup_complete",
                "release_check_count": 1,
                "release_observed": "approval_awaiting=5",
                "release_required": "transition_cleanup_execution_complete",
                "requires_operator_action": True,
                "source_artifact": "runs/transition_cleanup_work_order_current.json",
                "command": "",
                "recommended_action": "Review transition cleanup approvals.",
            },
            {
                "sequence": 8,
                "phase": "P3_cleanup_execution_or_policy_resolution",
                "lane_id": "cleanup_release",
                "burndown_status": "policy_decision_required",
                "approval_token_required": "",
                "release_checks": "protected_cleanup_policy_resolved",
                "release_check_count": 1,
                "release_observed": "policy_resolved=false",
                "release_required": "policy_resolved=true",
                "requires_operator_action": True,
                "source_artifact": "runs/protected_cleanup_payload_review_current.json",
                "command": "",
                "recommended_action": "Review protected cleanup policy.",
            },
        ],
    }


def _action_board() -> dict:
    return {
        "summary": {
            "status": "operator_actions_required",
            "approval_reclaim_size_gb": 49.216,
            "parallel_product_action_count": 1,
            "parallel_product_action_ids": [
                "product_scope_expansion:curate_scope_evidence_priority_item"
            ],
            "first_parallel_product_action_id": (
                "product_scope_expansion:curate_scope_evidence_priority_item"
            ),
            "first_parallel_product_action_lane_id": "product_scope_expansion",
            "first_parallel_product_action_type": "curate_scope_evidence_priority_item",
            "first_parallel_product_action_required_input": "AQP1.core_binder_01",
            "first_parallel_product_action_artifact_path": (
                "runs/product_goal_completion_audit_current.json"
            ),
            "first_parallel_product_action_recommended_action": (
                "Acquire exact target-pair quantitative evidence for AQP1."
            ),
            "first_parallel_product_action_primary_action_id": (
                "product_ai_production:return_gpu_force_regeneration_receipt"
            ),
            "first_parallel_product_action_precondition": (
                "Can be completed while production GPU work proceeds; does not require production GPU execution."
            ),
        },
        "rows": [
            {
                "lane_id": "commercial_product_execution",
                "action_type": "review_product_execution_approval",
                "status": "approval_required",
                "approval_token": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "artifact_path": "runs/product_execution_work_order_current.json",
                "required_input": "",
                "size_gb": 0,
            },
            {
                "lane_id": "cameo_validation",
                "action_type": "fill_cameo_official_results_intake",
                "status": "required",
                "approval_token": "",
                "artifact_path": "runs/cameo_official_results_intake_gate_current.json",
                "required_input": "official CAMEO results operator intake CSV;runs/cameo_official_results_operator_intake.csv",
                "reason": "missing_required_columns=target_id;candidate_id;cameo_model_rank;blocker_codes=official_result_rows_missing",
                "size_gb": 0,
            },
            {
                "lane_id": "transition_cleanup",
                "action_type": "review_cleanup_approval_token",
                "status": "approval_required",
                "approval_token": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
                "artifact_path": "runs/transition_cleanup_work_order_current.json",
                "required_input": "",
                "size_gb": 32.36,
            },
            {
                "lane_id": "ligand_heavy_cleanup",
                "action_type": "review_protected_ligand_heavy_policy",
                "status": "policy_decision_required",
                "approval_token": "",
                "artifact_path": "runs/protected_cleanup_payload_review_current.json",
                "required_input": "protected cleanup policy decision intake CSV",
                "size_gb": 396.794,
            },
        ],
    }


def _intake_kit() -> dict:
    return {
        "summary": {
            "status": "goal_operator_intake_kit_ready",
            "release_burndown_linked_entry_count": 4,
            "primary_action_id": "product_ai_production:return_gpu_force_regeneration_receipt",
            "top_action_id": "product_ai_production:return_gpu_force_regeneration_receipt",
            "primary_action_priority": 0,
            "primary_action_lane_id": "product_ai_production",
            "primary_action_type": "return_gpu_force_regeneration_receipt",
            "primary_action_status": "required",
            "primary_action_required_input": "GPU full-regeneration summary and manifest with operator verification",
            "primary_action_artifact_path": (
                "runs/product_goal_completion_audit_current.json;"
                "runs/product_production_ai_gpu_return_intake_current.json"
            ),
            "primary_action_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",
            "primary_action_recommended_action": (
                "Run the full regeneration command on a GPU worker, return the identity-locked manifest and summary."
            ),
            "full_commercial_release_allowed": False,
            "full_commercial_release_blocker_count": 3,
            "full_commercial_release_blocker_ids": [
                "R8_full_scope_claim_closure",
                "R9_engine_refinement_claim_promotion",
                "ACCURACY:ligand_ranking",
            ],
            "full_commercial_release_next_required_step": "Fill the R8/R9 receipt CSVs.",
            "science_claim_promotion_gap_closure_open_gap_ids": [],
            "science_claim_promotion_gap_closure_current_next_action": (
                "All science claim promotion boundary gaps are closed."
            ),
            "product_accuracy_parity_ligand_ranking_action_id": (
                "product_accuracy_parity:close_ligand_ranking_claim_scope"
            ),
            "product_accuracy_parity_ligand_ranking_action_present": True,
            "product_accuracy_parity_ligand_ranking_required_input": "ACCURACY:ligand_ranking",
            "product_accuracy_parity_ligand_ranking_artifact_path": (
                "runs/accuracy_parity_scorecard_current.json"
            ),
            "product_accuracy_parity_ligand_ranking_recommended_action": (
                "Keep broad GPCR/Schrodinger-class promotion locked until target-held-out "
                "broad-scope review and scorer/router promotion gates are approved."
            ),
            "accuracy_parity_ligand_ranking_status": "restricted_pass",
            "accuracy_parity_ligand_ranking_pr_auc": 0.871853,
            "accuracy_parity_ligand_ranking_pr_auc_ci_low": 0.761168,
            "accuracy_parity_ligand_ranking_topk_hit_rate": 1.0,
            "accuracy_parity_ligand_ranking_next_required_step": (
                "Keep broad GPCR/Schrodinger-class promotion locked until target-held-out "
                "broad-scope review and scorer/router promotion gates are approved."
            ),
            "primary_full_commercial_release_blocker_id": "R8_full_scope_claim_closure",
            "primary_full_commercial_release_blocker_requirement_id": "R8_full_scope_claim_closure",
            "primary_full_commercial_release_blocker_tier": "full_commercial_scope",
            "primary_full_commercial_release_blocker_blocked_row_count": 6,
            "primary_full_commercial_release_blocker_first_blocked_evidence_row_id": (
                "direct_binding_evidence_missing"
            ),
            "primary_full_commercial_release_blocker_receipt_csv": (
                "config/product_scope_breadth_evidence_receipt_current.csv"
            ),
            "primary_full_commercial_release_blocker_approval_token_required": (
                "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
            ),
            "primary_full_commercial_release_blocker_next_required_step": (
                "Replace placeholder receipt rows with reviewed local evidence."
            ),
            "full_commercial_evidence_receipt_entry_count": 2,
            "full_commercial_evidence_receipt_operator_input_required_count": 2,
            "full_commercial_evidence_receipt_current_action_required_count": 2,
            "full_commercial_evidence_receipt_template_required_count": 2,
            "full_commercial_evidence_receipt_template_present_count": 2,
            "full_commercial_evidence_receipt_approval_token_count": 2,
            "full_commercial_evidence_receipt_entry_ids": [
                "product_scope_breadth_evidence_receipt",
                "engine_refinement_claim_evidence_receipt",
            ],
            "full_commercial_evidence_receipt_source_gate_statuses": (
                "product_scope_breadth_evidence_receipt=blocked_product_scope_breadth_evidence_receipt;"
                "engine_refinement_claim_evidence_receipt=blocked_engine_refinement_claim_evidence_receipt"
            ),
            "full_commercial_evidence_receipt_required_inputs": (
                "config/product_scope_breadth_evidence_receipt_current.csv;"
                "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
            ),
            "full_commercial_evidence_receipt_approval_tokens": (
                "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT;"
                "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
            ),
            "product_goal_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id": (
                "direct_binding_evidence_missing"
            ),
            "product_goal_scope_breadth_evidence_receipt_first_blocked_evidence_artifact": (
                "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
            ),
            "product_goal_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status": (
                "product_scope_transporter_direct_binding_evidence_ready"
            ),
            "product_goal_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status": (
                "missing"
            ),
            "product_goal_scope_breadth_evidence_receipt_first_blocked_missing_true_fields": [
                "transporter_direct_binding_evidence_ready",
            ],
            "product_goal_scope_breadth_evidence_receipt_first_blocked_row_blockers": [
                "operator_placeholders_unfilled",
                "evidence_artifact_not_found",
            ],
            "product_goal_scope_breadth_evidence_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_blocker_id": (
                "public_benchmark_gate_not_ready"
            ),
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact": (
                "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
            ),
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status": (
                "refine_tier_public_benchmark_ready"
            ),
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status": (
                "missing"
            ),
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields": [
                "claim_grade_public_benchmark_ready",
            ],
            "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_row_blockers": [
                "operator_placeholders_unfilled",
                "evidence_artifact_not_found",
            ],
            "product_goal_engine_refinement_claim_evidence_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "product_scope_breadth_evidence_priority_source_json": (
                "runs/product_scope_breadth_evidence_priority_packet_current.json"
            ),
            "product_scope_breadth_evidence_priority_status": (
                "product_scope_breadth_evidence_priority_packet_ready"
            ),
            "product_scope_breadth_evidence_priority_packet_ready": True,
            "product_scope_breadth_evidence_priority_scope_promotion_allowed": False,
            "product_scope_breadth_evidence_priority_authoritative_apply_allowed": False,
            "product_scope_breadth_evidence_priority_queue_item_count": 15,
            "product_scope_breadth_evidence_priority_open_item_count": 15,
            "product_scope_breadth_evidence_priority_scientific_evidence_request_count": 11,
            "product_scope_breadth_evidence_priority_local_crosscheck_candidate_count": 11,
            "product_scope_breadth_evidence_priority_external_primary_exact_evidence_required_count": 0,
            "product_scope_breadth_evidence_priority_review_only_keep_blocked_count": 1,
            "product_scope_breadth_evidence_priority_top_item_id": "AQP1.core_binder_01",
            "product_scope_breadth_evidence_priority_top_domain": "transporter",
            "product_scope_breadth_evidence_priority_top_bucket": (
                "local_crosscheck_review_present_but_exact_quant_required"
            ),
            "product_scope_breadth_evidence_priority_top_required_evidence_type": (
                "exact_transporter_target_pair_quantitative_binder_kcal"
            ),
            "product_scope_breadth_evidence_priority_top_review_template_artifact": (
                "runs/transporter_manual_review_intake_template_current.json"
            ),
            "product_scope_breadth_evidence_priority_top_apply_gate_artifact": (
                "runs/transporter_binder_promotion_gate_current.json"
            ),
            "product_scope_breadth_evidence_priority_top_next_step": (
                "Review local crosscheck files, capture exact evidence if present."
            ),
            "product_scope_breadth_evidence_priority_external_state_mutated": False,
            "production_ai_registry_promotion_priority_source_json": (
                "runs/production_ai_registry_promotion_priority_packet_current.json"
            ),
            "production_ai_registry_promotion_priority_status": (
                "blocked_production_ai_registry_promotion_priority_packet"
            ),
            "production_ai_registry_promotion_priority_packet_ready": True,
            "production_ai_registry_promotion_priority_registry_promotion_ready": False,
            "production_ai_registry_promotion_priority_operator_input_required_count": 3,
            "production_ai_registry_promotion_priority_blocked_priority_item_count": 3,
            "production_ai_registry_promotion_priority_missing_gate_count": 3,
            "production_ai_registry_promotion_priority_missing_gate_ids": [
                "default_residual_mode_guarded",
                "production_promotion_allowed",
                "customer_facing_mutation_flags",
            ],
            "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count": 1,
            "production_ai_registry_promotion_priority_top_gate_id": (
                "default_residual_mode_guarded"
            ),
            "production_ai_registry_promotion_priority_top_priority_bucket": (
                "guarded_residual_mode_selection_required"
            ),
            "production_ai_registry_promotion_priority_top_required_input": (
                "Set the guarded default residual mode in the production AI registry promotion operator receipt."
            ),
            "production_ai_registry_promotion_priority_top_acceptance_artifact": (
                "runs/residual_model_registry_current.json"
            ),
            "production_ai_registry_promotion_priority_top_verification_command": (
                "python3 tools/build_residual_model_registry.py"
            ),
            "production_ai_registry_promotion_priority_top_next_operator_step": (
                "Fill the guarded promotion operator receipt."
            ),
            "production_ai_registry_promotion_priority_model_promoted": False,
            "production_ai_registry_promotion_priority_customer_facing_mutation_enabled": False,
            "production_ai_registry_promotion_priority_external_state_mutated": False,
        },
        "rows": [
            {
                "kit_entry_id": "product_execution",
                "kit_status": "approval_required",
                "release_checks": "product_architecture_release_ready;pilot_delivery_ready",
                "action_types": "review_product_execution_approval",
                "operator_input_required": True,
                "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "intake_path": "runs/product_execution_operator_approval_intake.csv",
                "source_artifacts": "runs/product_execution_work_order_current.json",
            },
            {
                "kit_entry_id": "cameo_official_results",
                "kit_status": "operator_input_required",
                "release_checks": "official_cameo_validation_evidence_ready;official_cameo_results_used",
                "action_types": "fill_cameo_official_results_intake",
                "operator_input_required": True,
                "approval_token_required": "",
                "intake_path": "runs/cameo_official_results_operator_intake.csv",
                "source_artifacts": "runs/cameo_official_results_intake_gate_current.json",
            },
            {
                "kit_entry_id": "cleanup_execution_approval",
                "kit_status": "approval_required",
                "release_checks": "transition_cleanup_complete;ligand_heavy_cleanup_complete",
                "action_types": "review_cleanup_approval_token;review_ligand_heavy_cleanup_approval",
                "operator_input_required": True,
                "approval_token_required": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS;APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
                "intake_path": "runs/cleanup_execution_operator_approval_intake.csv",
                "source_artifacts": "runs/transition_cleanup_work_order_current.json",
            },
            {
                "kit_entry_id": "protected_cleanup_policy",
                "kit_status": "policy_decision_required",
                "release_checks": "protected_cleanup_policy_resolved",
                "action_types": "review_protected_ligand_heavy_policy",
                "operator_input_required": True,
                "approval_token_required": "",
                "intake_path": "runs/protected_cleanup_policy_decision_intake.csv",
                "source_artifacts": "runs/protected_cleanup_payload_review_current.json",
            },
        ],
    }


def _release_gate_ready() -> dict:
    return {
        "summary": {
            "status": "goal_release_ready",
            "release_allowed": True,
            "blocker_count": 0,
            "check_count": 16,
            "cleanup_objective_ready": True,
            "cleanup_completion_complete": True,
        }
    }


def _completion_audit_full_commercial_blockers() -> dict:
    return {
        "summary": {
            "status": "blocked_product_goal_completion_audit",
            "goal_complete": False,
            "release_blocker_fail_count": 2,
        },
        "rows": [
            {
                "requirement_id": "R8_full_scope_claim_closure",
                "requirement_tier": "full_commercial_scope",
                "requirement": "Full independent commercial-product claims stay blocked.",
                "status": "fail",
                "release_blocker": True,
                "blocker": "full_scope_claim_closure_not_ready",
                "evidence_artifacts": (
                    "runs/product_scope_breadth_contract_current.json;"
                    "runs/product_scope_breadth_evidence_intake_readiness_current.json"
                ),
                "observed": (
                    "scope_closure_ready=False;first_blocked_evidence_row_id=AQP1.core_binder_01;"
                    "first_blocked_required_missing_fields=replacement_reference_binding_kcal_mol"
                ),
                "required": "scope_closure_ready=true;authoritative_apply_allowed=true",
                "next_command": "python3 tools/build_product_scope_breadth_contract.py",
            },
            {
                "requirement_id": "R9_engine_refinement_claim_promotion",
                "requirement_tier": "full_commercial_science_claim",
                "requirement": "Refine-tier science claims stay blocked.",
                "status": "fail",
                "release_blocker": True,
                "blocker": "engine_refinement_claim_promotion_not_ready",
                "evidence_artifacts": (
                    "runs/engine_refinement_tier_readiness_current.json;"
                    "runs/engine_refinement_claim_evidence_receipt_current.json"
                ),
                "observed": (
                    "engine_refinement_status=engine_refinement_tier_ready;"
                    "claim_promotion_allowed=False;claim_promotion_blocker_count=6"
                ),
                "required": "claim_promotion_allowed=true;claim_promotion_evidence_receipt_ready=true",
                "next_command": "python3 tools/product/build_engine_refinement_tier_readiness.py",
            },
        ],
    }


def _burndown_with_scientific_scope_before_refresh() -> dict:
    return {
        "summary": {"status": "goal_release_burndown_work_order_ready"},
        "rows": [
            {
                "sequence": 1,
                "phase": "P0_product_ai_architecture_scope_closure",
                "lane_id": "commercial_product_release",
                "burndown_status": "scientific_scope_evidence_required",
                "approval_token_required": "",
                "release_checks": "product_ai_architecture_gap_closure_ready",
                "release_check_count": 1,
                "release_observed": "open_gap_count=1;work_item_count=21",
                "release_required": "all_gaps_closed=true;work_item_count=0",
                "requires_operator_action": True,
                "source_artifact": "runs/product_ai_architecture_gap_closure_current.json;runs/product_ai_architecture_execution_backlog_current.json",
                "command": "python3 tools/build_product_ai_architecture_execution_backlog.py",
                "recommended_action": "Close product AI architecture scope breadth blockers.",
            },
            {
                "sequence": 2,
                "phase": "P4_refresh_release_evidence",
                "lane_id": "goal_release",
                "burndown_status": "blocked_until_prior_phases_clear",
                "approval_token_required": "",
                "release_checks": "product_release_evidence_ready",
                "release_check_count": 1,
                "release_observed": "blocked_goal_readiness",
                "release_required": "no blocked rollup lanes",
                "requires_operator_action": True,
                "source_artifact": "runs/goal_release_decision_gate_current.json",
                "command": "python3 tools/build_goal_readiness_rollup.py",
                "recommended_action": "Refresh release evidence after prior phases.",
            },
        ],
    }


def _burndown_with_production_inference_before_refresh() -> dict:
    return {
        "summary": {"status": "goal_release_burndown_work_order_ready"},
        "rows": [
            {
                "sequence": 1,
                "phase": "P0_product_ai_architecture_production_inference_closure",
                "lane_id": "commercial_product_release",
                "burndown_status": "production_ai_checkpoint_evidence_required",
                "approval_token_required": "",
                "release_checks": "product_ai_architecture_gap_closure_ready",
                "release_check_count": 1,
                "release_observed": "current_primary_open_gap=production_ai_inference_checkpoint;primary_work_item_id=training_data.production_residual_output_head",
                "release_required": "all_gaps_closed=true;work_item_count=0",
                "requires_operator_action": True,
                "source_artifact": "runs/product_ai_architecture_gap_closure_current.json;runs/product_ai_architecture_execution_backlog_current.json",
                "command": "python3 tools/build_residual_production_checkpoint_preflight.py",
                "recommended_action": "Close product AI production checkpoint evidence.",
            },
            {
                "sequence": 2,
                "phase": "P4_refresh_release_evidence",
                "lane_id": "goal_release",
                "burndown_status": "blocked_until_prior_phases_clear",
                "approval_token_required": "",
                "release_checks": "product_release_evidence_ready",
                "release_check_count": 1,
                "release_observed": "blocked_goal_readiness",
                "release_required": "no blocked rollup lanes",
                "requires_operator_action": True,
                "source_artifact": "runs/goal_release_decision_gate_current.json",
                "command": "python3 tools/build_goal_readiness_rollup.py",
                "recommended_action": "Refresh release evidence after prior phases.",
            },
        ],
    }


def test_goal_bottleneck_briefing_links_release_blockers_to_intake_and_actions() -> None:
    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=_release_gate(),
        burndown_packet=_burndown(),
        action_board_packet=_action_board(),
        intake_kit_packet=_intake_kit(),
    )

    summary = payload["summary"]
    by_sequence = {row["sequence"]: row for row in payload["rows"]}
    assert summary["status"] == "goal_bottleneck_briefing_ready"
    assert summary["release_allowed"] is False
    assert summary["source_release_blocker_count"] == 5
    assert summary["bottleneck_count"] == 4
    assert summary["approval_required_bottleneck_count"] == 2
    assert summary["official_results_required_bottleneck_count"] == 1
    assert summary["policy_decision_required_bottleneck_count"] == 1
    assert summary["approval_reclaim_size_gb"] == 49.216
    assert summary["cleanup_transition_approval_gated_reclaim_size_gb"] == 43.206
    assert summary["cleanup_ligand_heavy_candidate_size_gb"] == 6.011
    assert summary["protected_cleanup_payload_size_gb"] == 396.794
    assert summary["operator_intake_kit_release_burndown_linked_entry_count"] == 4
    assert summary["production_ai_registry_promotion_priority_status"] == (
        "blocked_production_ai_registry_promotion_priority_packet"
    )
    assert summary["production_ai_registry_promotion_priority_top_gate_id"] == (
        "default_residual_mode_guarded"
    )
    assert summary["product_scope_breadth_evidence_priority_status"] == (
        "product_scope_breadth_evidence_priority_packet_ready"
    )
    assert summary["product_scope_breadth_evidence_priority_packet_ready"] is True
    assert summary["product_scope_breadth_evidence_priority_top_item_id"] == "AQP1.core_binder_01"
    assert summary["product_scope_breadth_evidence_priority_top_domain"] == "transporter"
    assert summary["product_scope_breadth_evidence_priority_top_bucket"] == (
        "local_crosscheck_review_present_but_exact_quant_required"
    )
    assert summary["product_scope_breadth_evidence_priority_top_required_evidence_type"] == (
        "exact_transporter_target_pair_quantitative_binder_kcal"
    )
    assert summary["primary_action_id"] == "product_ai_production:return_gpu_force_regeneration_receipt"
    assert summary["top_action_id"] == summary["primary_action_id"]
    assert summary["primary_action_priority"] == 0
    assert summary["primary_action_lane_id"] == "product_ai_production"
    assert summary["primary_action_type"] == "return_gpu_force_regeneration_receipt"
    assert summary["primary_action_status"] == "required"
    assert summary["primary_action_required_input"] == (
        "GPU full-regeneration summary and manifest with operator verification"
    )
    assert "generate_ligand_trajectory_engine.py" in summary["primary_action_command"]
    assert "Run the full regeneration command on a GPU worker" in summary[
        "primary_action_recommended_action"
    ]
    assert summary["parallel_product_action_count"] == 1
    assert summary["parallel_product_action_ids"] == [
        "product_scope_expansion:curate_scope_evidence_priority_item"
    ]
    assert summary["first_parallel_product_action_required_input"] == "AQP1.core_binder_01"
    assert summary["first_parallel_product_action_primary_action_id"] == summary["primary_action_id"]
    assert "does not require production GPU execution" in summary[
        "first_parallel_product_action_precondition"
    ]
    assert summary["primary_bottleneck_sequence"] == 1
    assert summary["primary_bottleneck_command"] == "python3 tools/run_ligand_htvs_pipeline.py --no-dry-run"
    assert summary["primary_bottleneck_command_candidate_count"] == 0
    assert "APPROVE_PRODUCT_DOCKING_EXECUTION" in summary["approval_tokens_required"]
    assert "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS" in summary["approval_tokens_required"]
    assert by_sequence[1]["bottleneck_kind"] == "operator_approval_required"
    assert by_sequence[1]["operator_intake_entries"] == "product_execution"
    assert by_sequence[1]["approval_token_required"] == "APPROVE_PRODUCT_DOCKING_EXECUTION"
    assert by_sequence[3]["bottleneck_kind"] == "official_cameo_results_missing"
    assert "runs/cameo_official_results_operator_intake.csv" in by_sequence[3]["required_inputs"]
    assert "missing_required_columns=target_id" in by_sequence[3]["operator_action_reasons"]
    assert "official_result_rows_missing" in by_sequence[3]["operator_action_reasons"]
    assert by_sequence[6]["size_gb"] == 32.36
    assert "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS" in by_sequence[6]["approval_token_required"]
    assert by_sequence[8]["bottleneck_kind"] == "protected_payload_policy_decision"
    assert "protected cleanup policy decision intake CSV" in by_sequence[8]["required_inputs"]
    assert summary["execution_enabled"] is False
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False


def test_goal_bottleneck_briefing_prioritizes_scientific_scope_before_refresh() -> None:
    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=_release_gate(),
        burndown_packet=_burndown_with_scientific_scope_before_refresh(),
        action_board_packet={"summary": {"status": "operator_actions_required"}, "rows": []},
        intake_kit_packet={"summary": {"status": "goal_operator_intake_kit_ready"}, "rows": []},
    )

    summary = payload["summary"]
    assert summary["primary_bottleneck_sequence"] == 1
    assert summary["primary_bottleneck_kind"] == "scientific_scope_evidence_required"
    assert summary["primary_bottleneck_phase"] == "P0_product_ai_architecture_scope_closure"
    assert summary["primary_bottleneck_root_cause_category"] == "external_exact_scope_evidence"
    assert summary["primary_bottleneck_locally_closable_without_operator_return"] is False
    assert "replacement_reference_binding_kcal_mol" in summary[
        "primary_bottleneck_required_external_return"
    ]
    assert summary["primary_bottleneck_first_acceptance_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert "build_product_ai_architecture_execution_backlog.py" in summary["primary_bottleneck_command"]
    assert summary["kind_counts"]["scientific_scope_evidence_required"] == 1
    assert "product AI architecture scope closure" in summary["next_required_step"]
    assert "release evidence refresh" in summary["next_required_step"]


def test_goal_bottleneck_briefing_prioritizes_production_inference_before_refresh() -> None:
    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=_release_gate(),
        burndown_packet=_burndown_with_production_inference_before_refresh(),
        action_board_packet={"summary": {"status": "operator_actions_required"}, "rows": []},
        intake_kit_packet={"summary": {"status": "goal_operator_intake_kit_ready"}, "rows": []},
    )

    summary = payload["summary"]
    assert summary["primary_bottleneck_sequence"] == 1
    assert summary["primary_bottleneck_kind"] == "production_ai_checkpoint_evidence_required"
    assert summary["primary_bottleneck_phase"] == "P0_product_ai_architecture_production_inference_closure"
    assert summary["primary_bottleneck_root_cause_category"] == (
        "external_gpu_runtime_and_return_receipt"
    )
    assert summary["primary_bottleneck_locally_closable_without_operator_return"] is False
    assert "visible_device_count>0" in summary["primary_bottleneck_required_external_return"]
    assert summary["primary_bottleneck_first_acceptance_artifact"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert summary["primary_bottleneck_post_return_acceptance_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert summary["irreducible_external_return_bottleneck_count"] == 1
    assert "build_residual_production_checkpoint_preflight.py" in summary["primary_bottleneck_command"]
    assert summary["kind_counts"]["production_ai_checkpoint_evidence_required"] == 1
    assert "product AI production inference closure" in summary["next_required_step"]
    assert "release evidence refresh" in summary["next_required_step"]
    first_row = payload["rows"][0]
    assert first_row["root_cause_category"] == "external_gpu_runtime_and_return_receipt"
    assert first_row["locally_closable_without_operator_return"] is False


def test_goal_bottleneck_briefing_keeps_full_commercial_completion_blockers_when_release_is_clear() -> None:
    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=_release_gate_ready(),
        burndown_packet={"summary": {"status": "goal_release_burndown_clear"}, "rows": []},
        action_board_packet=_action_board(),
        intake_kit_packet=_intake_kit(),
        completion_audit_packet=_completion_audit_full_commercial_blockers(),
    )

    summary = payload["summary"]
    by_id = {row["bottleneck_id"]: row for row in payload["rows"]}
    assert summary["status"] == "goal_bottleneck_briefing_ready"
    assert summary["release_allowed"] is True
    assert summary["source_burndown_status"] == "goal_release_burndown_clear"
    assert summary["source_completion_audit_status"] == "blocked_product_goal_completion_audit"
    assert summary["completion_audit_goal_complete"] is False
    assert summary["completion_audit_release_blocker_fail_count"] == 2
    assert summary["completion_audit_release_blocker_bottleneck_count"] == 2
    assert summary["full_commercial_release_allowed"] is False
    assert summary["full_commercial_release_blocker_count"] == 3
    assert summary["full_commercial_release_blocker_ids"] == [
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
        "ACCURACY:ligand_ranking",
    ]
    assert "R8/R9 receipt CSVs" in summary["full_commercial_release_next_required_step"]
    assert summary["science_claim_promotion_gap_closure_open_gap_ids"] == []
    assert "All science claim promotion boundary gaps are closed" in summary[
        "science_claim_promotion_gap_closure_current_next_action"
    ]
    assert summary["accuracy_parity_ligand_ranking_status"] == "restricted_pass"
    assert summary["product_accuracy_parity_ligand_ranking_action_id"] == (
        "product_accuracy_parity:close_ligand_ranking_claim_scope"
    )
    assert summary["product_accuracy_parity_ligand_ranking_action_present"] is True
    assert summary["product_accuracy_parity_ligand_ranking_required_input"] == (
        "ACCURACY:ligand_ranking"
    )
    assert summary["product_accuracy_parity_ligand_ranking_artifact_path"] == (
        "runs/accuracy_parity_scorecard_current.json"
    )
    assert summary["accuracy_parity_ligand_ranking_pr_auc"] == 0.871853
    assert summary["accuracy_parity_ligand_ranking_pr_auc_ci_low"] == 0.761168
    assert summary["accuracy_parity_ligand_ranking_topk_hit_rate"] == 1.0
    assert "target-held-out broad-scope review" in summary[
        "accuracy_parity_ligand_ranking_next_required_step"
    ]
    assert summary["primary_full_commercial_release_blocker_id"] == "R8_full_scope_claim_closure"
    assert summary["primary_full_commercial_release_blocker_requirement_id"] == (
        "R8_full_scope_claim_closure"
    )
    assert summary["primary_full_commercial_release_blocker_tier"] == "full_commercial_scope"
    assert summary["primary_full_commercial_release_blocker_blocked_row_count"] == 6
    assert summary["primary_full_commercial_release_blocker_first_blocked_evidence_row_id"] == (
        "direct_binding_evidence_missing"
    )
    assert summary["primary_full_commercial_release_blocker_receipt_csv"] == (
        "config/product_scope_breadth_evidence_receipt_current.csv"
    )
    assert summary["primary_full_commercial_release_blocker_approval_token_required"] == (
        "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
    )
    assert "placeholder receipt rows" in summary[
        "primary_full_commercial_release_blocker_next_required_step"
    ]
    assert summary["full_commercial_evidence_receipt_entry_count"] == 2
    assert summary["full_commercial_evidence_receipt_operator_input_required_count"] == 2
    assert summary["full_commercial_evidence_receipt_current_action_required_count"] == 2
    assert summary["full_commercial_evidence_receipt_template_required_count"] == 2
    assert summary["full_commercial_evidence_receipt_template_present_count"] == 2
    assert summary["full_commercial_evidence_receipt_approval_token_count"] == 2
    assert summary["full_commercial_evidence_receipt_entry_ids"] == [
        "product_scope_breadth_evidence_receipt",
        "engine_refinement_claim_evidence_receipt",
    ]
    assert "blocked_product_scope_breadth_evidence_receipt" in summary[
        "full_commercial_evidence_receipt_source_gate_statuses"
    ]
    assert "config/engine_refinement_claim_promotion_evidence_receipt_current.csv" in summary[
        "full_commercial_evidence_receipt_required_inputs"
    ]
    assert "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT" in summary[
        "full_commercial_evidence_receipt_approval_tokens"
    ]
    assert summary[
        "product_goal_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id"
    ] == "direct_binding_evidence_missing"
    assert summary[
        "product_goal_scope_breadth_evidence_receipt_first_blocked_evidence_artifact"
    ] == "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
    assert summary[
        "product_goal_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status"
    ] == "product_scope_transporter_direct_binding_evidence_ready"
    assert summary[
        "product_goal_scope_breadth_evidence_receipt_first_blocked_missing_true_fields"
    ] == ["transporter_direct_binding_evidence_ready"]
    assert "operator_placeholders_unfilled" in summary[
        "product_goal_scope_breadth_evidence_receipt_first_blocked_row_blockers"
    ]
    assert summary[
        "product_goal_scope_breadth_evidence_receipt_most_common_row_blocker"
    ] == "operator_placeholders_unfilled"
    assert summary[
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_blocker_id"
    ] == "public_benchmark_gate_not_ready"
    assert summary[
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact"
    ] == "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
    assert summary[
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status"
    ] == "refine_tier_public_benchmark_ready"
    assert summary[
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields"
    ] == ["claim_grade_public_benchmark_ready"]
    assert "operator_placeholders_unfilled" in summary[
        "product_goal_engine_refinement_claim_evidence_receipt_first_blocked_row_blockers"
    ]
    assert summary[
        "product_goal_engine_refinement_claim_evidence_receipt_most_common_row_blocker"
    ] == "operator_placeholders_unfilled"
    assert summary["production_ai_registry_promotion_priority_status"] == (
        "blocked_production_ai_registry_promotion_priority_packet"
    )
    assert summary["production_ai_registry_promotion_priority_packet_ready"] is True
    assert summary["production_ai_registry_promotion_priority_registry_promotion_ready"] is False
    assert summary["production_ai_registry_promotion_priority_operator_input_required_count"] == 3
    assert summary["production_ai_registry_promotion_priority_blocked_priority_item_count"] == 3
    assert summary["production_ai_registry_promotion_priority_missing_gate_count"] == 3
    assert summary["production_ai_registry_promotion_priority_missing_gate_ids"] == [
        "default_residual_mode_guarded",
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
    ]
    assert summary[
        "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count"
    ] == 1
    assert summary["production_ai_registry_promotion_priority_top_gate_id"] == (
        "default_residual_mode_guarded"
    )
    assert summary["production_ai_registry_promotion_priority_top_priority_bucket"] == (
        "guarded_residual_mode_selection_required"
    )
    assert summary["product_scope_breadth_evidence_priority_open_item_count"] == 15
    assert summary["product_scope_breadth_evidence_priority_top_item_id"] == "AQP1.core_binder_01"
    assert summary["product_scope_breadth_evidence_priority_authoritative_apply_allowed"] is False
    assert summary["production_ai_registry_promotion_priority_model_promoted"] is False
    assert summary["production_ai_registry_promotion_priority_external_state_mutated"] is False
    assert summary["bottleneck_count"] == 2
    assert summary["current_bottleneck_count"] == 2
    assert summary["kind_counts"]["scientific_scope_evidence_required"] == 1
    assert summary["kind_counts"]["engine_refinement_claim_promotion_required"] == 1
    assert summary["primary_bottleneck_sequence"] == 8
    assert summary["primary_bottleneck_kind"] == "scientific_scope_evidence_required"
    assert summary["primary_action_id"] == "full_commercial_scope:scientific_scope_evidence_required"
    assert summary["top_action_id"] == summary["primary_action_id"]
    assert summary["primary_action_status"] == "required"
    assert "replacement_reference_binding_kcal_mol" in summary["primary_bottleneck_required_external_return"]
    assert "engine refinement claim evidence" in summary["next_required_step"]
    assert by_id["R8_full_scope_claim_closure"]["row_source"] == "completion_audit"
    assert by_id["R8_full_scope_claim_closure"]["root_cause_category"] == "external_exact_scope_evidence"
    assert by_id["R9_engine_refinement_claim_promotion"]["root_cause_category"] == (
        "external_public_benchmark_and_calibration_evidence"
    )
    assert by_id["R9_engine_refinement_claim_promotion"]["post_return_acceptance_artifact"] == (
        "runs/engine_refinement_claim_evidence_receipt_current.json"
    )


def test_goal_bottleneck_briefing_filters_stale_intake_tokens_when_burndown_token_is_current() -> None:
    burndown = {
        "summary": {"status": "goal_release_burndown_work_order_ready"},
        "rows": [
            {
                "sequence": 4,
                "phase": "P2_cameo_official_validation_and_registration",
                "lane_id": "cameo_architecture_validation",
                "burndown_status": "approval_required",
                "approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL",
                "release_checks": "cameo_public_registration_allowed",
                "release_check_count": 1,
                "release_observed": "public_registration_allowed=false",
                "release_required": "public_registration_allowed=true",
                "requires_operator_action": True,
                "source_artifact": "runs/cameo_capability_preflight_current.json",
                "command": "",
                "recommended_action": "Review registration/email approval.",
            }
        ],
    }
    intake = {
        "summary": {"status": "goal_operator_intake_kit_ready", "release_burndown_linked_entry_count": 2},
        "rows": [
            {
                "kit_entry_id": "cameo_api_dependency_install",
                "kit_status": "approval_required",
                "release_checks": "cameo_public_registration_allowed",
                "action_types": "repair_cameo_receiver_runtime_smoke",
                "operator_input_required": True,
                "approval_token_required": "APPROVE_API_DEPENDENCY_INSTALL",
                "source_artifacts": "runs/cameo_runtime_repair_work_order_current.json",
            },
            {
                "kit_entry_id": "cameo_public_registration",
                "kit_status": "approval_required",
                "release_checks": "cameo_public_registration_allowed",
                "action_types": "fill_cameo_public_registration_approval",
                "operator_input_required": True,
                "approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL",
                "intake_path": "runs/cameo_public_registration_operator_approval_intake.csv",
                "source_artifacts": "runs/cameo_public_registration_approval_gate_current.json",
            },
        ],
    }

    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=_release_gate(),
        burndown_packet=burndown,
        action_board_packet={"summary": {"status": "operator_actions_required"}, "rows": []},
        intake_kit_packet=intake,
    )

    row = payload["rows"][0]
    assert row["approval_token_required"] == "APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL"
    assert row["operator_intake_entries"] == "cameo_public_registration"
    assert "APPROVE_API_DEPENDENCY_INSTALL" not in payload["summary"]["approval_tokens_required"]


def test_goal_bottleneck_briefing_does_not_attach_stale_tokens_to_blocked_until_rows() -> None:
    burndown = {
        "summary": {"status": "goal_release_burndown_work_order_ready"},
        "rows": [
            {
                "sequence": 1,
                "phase": "P1_product_execution_and_bundle_validation",
                "lane_id": "commercial_product_release",
                "burndown_status": "blocked_until_cameo_architecture_validation",
                "approval_token_required": "",
                "release_checks": "product_architecture_release_ready",
                "release_check_count": 1,
                "release_observed": "architecture_release_ready=false",
                "release_required": "architecture_release_ready=true",
                "requires_operator_action": True,
                "source_artifact": "runs/product_architecture_contract_current.json",
                "command": "",
                "recommended_action": "Clear CAMEO architecture validation.",
            }
        ],
    }
    action_board = {
        "summary": {"status": "operator_actions_required"},
        "rows": [
            {
                "lane_id": "commercial_product_execution",
                "action_type": "review_product_execution_approval",
                "status": "approval_required",
                "approval_token": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "artifact_path": "runs/product_execution_work_order_current.json",
            }
        ],
    }
    intake = {
        "summary": {"status": "goal_operator_intake_kit_ready"},
        "rows": [
            {
                "kit_entry_id": "product_execution",
                "kit_status": "approval_required",
                "release_checks": "product_architecture_release_ready",
                "action_types": "review_product_execution_approval",
                "operator_input_required": True,
                "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "intake_path": "runs/product_execution_operator_approval_intake.csv",
                "source_artifacts": "runs/product_execution_work_order_current.json",
            }
        ],
    }

    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=_release_gate(),
        burndown_packet=burndown,
        action_board_packet=action_board,
        intake_kit_packet=intake,
    )

    assert payload["summary"]["approval_tokens_required"] == []
    assert payload["rows"][0]["approval_token_required"] == ""
    assert payload["rows"][0]["operator_intake_entries"] == ""


def test_goal_bottleneck_briefing_uses_current_release_gate_observed_fields() -> None:
    release_gate = {
        "summary": {"status": "goal_release_ready", "release_allowed": True},
        "rows": [
            {
                "check": "goal_bottleneck_briefing_full_commercial_receipts_recorded",
                "observed": (
                    "goal_bottleneck_briefing_ready;"
                    "completion_audit_release_blocker_bottleneck_count=2"
                ),
                "required": "goal_bottleneck_briefing_ready with R8/R9 blockers",
            }
        ],
    }
    burndown = {
        "summary": {"status": "goal_release_burndown_work_order_ready"},
        "rows": [
            {
                "sequence": 1,
                "phase": "P1_product_execution_and_bundle_validation",
                "lane_id": "commercial_product_release",
                "burndown_status": "approval_required",
                "release_checks": "goal_bottleneck_briefing_full_commercial_receipts_recorded",
                "release_check_count": 1,
                "release_observed": (
                    "goal_bottleneck_briefing_ready;"
                    "completion_audit_release_blocker_bottleneck_count=3"
                ),
                "release_required": "stale required text",
                "requires_operator_action": True,
                "source_artifact": "runs/product_execution_work_order_current.json",
                "command": "",
                "recommended_action": "Refresh stale observed data.",
            }
        ],
    }

    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=release_gate,
        burndown_packet=burndown,
        action_board_packet={"summary": {"status": "operator_actions_required"}, "rows": []},
        intake_kit_packet={"summary": {"status": "goal_operator_intake_kit_ready"}, "rows": []},
    )

    row = payload["rows"][0]
    assert "completion_audit_release_blocker_bottleneck_count=2" in row["release_observed"]
    assert "completion_audit_release_blocker_bottleneck_count=3" not in row["release_observed"]
    assert "goal_bottleneck_briefing_ready with R8/R9 blockers" in row["release_required"]


def test_goal_bottleneck_briefing_zeroes_cleanup_sizes_when_cleanup_objective_ready() -> None:
    release = _release_gate()
    release["summary"] = {
        **release["summary"],
        "cleanup_objective_ready": True,
        "cleanup_completion_complete": True,
    }

    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=release,
        burndown_packet=_burndown(),
        action_board_packet=_action_board(),
        intake_kit_packet=_intake_kit(),
    )

    summary = payload["summary"]
    assert summary["cleanup_transition_approval_gated_reclaim_size_gb"] == 0.0
    assert summary["cleanup_ligand_heavy_candidate_size_gb"] == 0.0
    assert "cleanup approvals/policy" not in summary["next_required_step"]


def test_goal_bottleneck_briefing_links_public_benchmark_work_order() -> None:
    burndown = {
        "summary": {"status": "goal_release_burndown_work_order_ready"},
        "rows": [
            {
                "sequence": 1,
                "phase": "P1_product_execution_and_bundle_validation",
                "lane_id": "commercial_product_release",
                "burndown_status": "blocked_until_public_benchmark_validation",
                "approval_token_required": "",
                "release_checks": "product_architecture_release_ready",
                "release_check_count": 1,
                "release_observed": "public_benchmark_ready=false",
                "release_required": "architecture_release_ready=true",
                "requires_operator_action": True,
                "source_artifact": "runs/product_pilot_packet_contract_current.json",
                "command": "python3 tools/build_product_public_benchmark_work_order.py",
                "recommended_action": "Run and attach public benchmark scorecards.",
            }
        ],
    }
    work_order = {
        "summary": {
            "status": "product_public_benchmark_work_order_ready",
            "open_suite_count": 5,
            "materialization_required_suite_count": 5,
            "scorecard_required_suite_count": 0,
            "continuous_validation_command_count": 5,
            "suite_run_command_count": 5,
            "suite_blocker_count": 5,
            "suite_threshold_count": 5,
            "suite_materialization_manifest_count": 5,
            "suite_materialization_run_command_count": 5,
            "suite_scorecard_command_count": 5,
            "suite_scorecard_row_csv_count": 5,
            "suite_no_external_dependency_count": 5,
            "local_artifact_preflight_ready_suite_count": 0,
            "local_artifact_preflight_blocked_suite_count": 5,
            "missing_local_input_artifact_count": 6,
            "missing_local_output_artifact_count": 6,
            "result_generation_required_suite_count": 5,
            "benchmark_result_missing_artifact_count": 6,
            "benchmark_result_missing_artifacts": ["runs/lit_pcba_scores_current.csv"],
            "result_generation_approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
            "missing_local_input_artifacts": ["data/public_benchmarks/lit_pcba/archive.tar.xz"],
            "missing_local_output_artifacts": ["runs/lit_pcba_scores_current.csv"],
            "continuous_validation_command": "python3 tools/build_lit_pcba_materialization_manifest.py && python3 tools/build_lit_pcba_scorecard.py",
        }
    }

    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=_release_gate(),
        burndown_packet=burndown,
        action_board_packet={"summary": {"status": "operator_actions_required"}, "rows": []},
        intake_kit_packet={"summary": {"status": "goal_operator_intake_kit_ready"}, "rows": []},
        public_benchmark_work_order_packet=work_order,
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["public_benchmark_work_order_status"] == "product_public_benchmark_work_order_ready"
    assert summary["public_benchmark_open_suite_count"] == 5
    assert summary["public_benchmark_materialization_required_suite_count"] == 5
    assert summary["public_benchmark_continuous_validation_command_count"] == 5
    assert summary["public_benchmark_suite_run_command_count"] == 5
    assert summary["public_benchmark_suite_blocker_count"] == 5
    assert summary["public_benchmark_suite_threshold_count"] == 5
    assert summary["public_benchmark_suite_materialization_manifest_count"] == 5
    assert summary["public_benchmark_suite_materialization_run_command_count"] == 5
    assert summary["public_benchmark_suite_scorecard_command_count"] == 5
    assert summary["public_benchmark_suite_scorecard_row_csv_count"] == 5
    assert summary["public_benchmark_suite_no_external_dependency_count"] == 5
    assert summary["public_benchmark_local_artifact_preflight_ready_suite_count"] == 0
    assert summary["public_benchmark_local_artifact_preflight_blocked_suite_count"] == 5
    assert summary["public_benchmark_missing_local_input_artifact_count"] == 6
    assert summary["public_benchmark_missing_local_output_artifact_count"] == 6
    assert summary["public_benchmark_result_generation_required_suite_count"] == 5
    assert summary["public_benchmark_result_generation_approval_token_required"] == "APPROVE_PRODUCT_DOCKING_EXECUTION"
    assert summary["public_benchmark_benchmark_result_missing_artifact_count"] == 6
    assert summary["public_benchmark_benchmark_result_missing_artifacts"] == ["runs/lit_pcba_scores_current.csv"]
    assert summary["public_benchmark_missing_local_input_artifacts"] == ["data/public_benchmarks/lit_pcba/archive.tar.xz"]
    assert summary["public_benchmark_missing_local_output_artifacts"] == ["runs/lit_pcba_scores_current.csv"]
    assert "build_lit_pcba_scorecard.py" in summary["public_benchmark_continuous_validation_command"]
    assert row["bottleneck_kind"] == "blocked_until_public_benchmark_validation"
    assert row["public_benchmark_work_order_json"] == "runs/product_public_benchmark_work_order_current.json"
    assert row["public_benchmark_open_suite_count"] == 5
    assert row["public_benchmark_continuous_validation_command_count"] == 5
    assert row["public_benchmark_suite_run_command_count"] == 5
    assert row["public_benchmark_suite_blocker_count"] == 5
    assert row["public_benchmark_suite_materialization_run_command_count"] == 5
    assert row["public_benchmark_suite_scorecard_command_count"] == 5
    assert row["public_benchmark_suite_scorecard_row_csv_count"] == 5
    assert row["public_benchmark_suite_no_external_dependency_count"] == 5
    assert row["public_benchmark_local_artifact_preflight_blocked_suite_count"] == 5
    assert row["public_benchmark_missing_local_input_artifact_count"] == 6
    assert row["public_benchmark_missing_local_output_artifact_count"] == 6
    assert row["public_benchmark_result_generation_required_suite_count"] == 5
    assert row["public_benchmark_result_generation_approval_token_required"] == "APPROVE_PRODUCT_DOCKING_EXECUTION"
    assert row["public_benchmark_benchmark_result_missing_artifact_count"] == 6
    assert "build_lit_pcba_scorecard.py" in row["public_benchmark_continuous_validation_command"]
    assert "runs/product_public_benchmark_work_order_current.json" in row["source_artifacts"]


def test_goal_bottleneck_briefing_demotes_stale_public_benchmark_block_when_work_order_is_clear() -> None:
    burndown = {
        "summary": {"status": "goal_release_burndown_work_order_ready"},
        "rows": [
            {
                "sequence": 1,
                "phase": "P1_product_execution_and_bundle_validation",
                "lane_id": "commercial_product_release",
                "burndown_status": "blocked_until_public_benchmark_validation",
                "approval_token_required": "",
                "release_checks": "product_architecture_release_ready",
                "release_check_count": 1,
                "release_observed": "public_benchmark_ready=true;public_benchmark_blocked_suites=0",
                "release_required": "architecture_release_ready=true",
                "requires_operator_action": True,
                "source_artifact": "runs/product_architecture_contract_current.json",
                "command": "python3 tools/build_product_public_benchmark_work_order.py",
                "recommended_action": "Run and attach public benchmark scorecards.",
            },
            {
                "sequence": 2,
                "phase": "P2_commercial_independence",
                "lane_id": "commercial_independence",
                "burndown_status": "approval_required",
                "approval_token_required": "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
                "release_checks": "commercial_independence_ready",
                "release_check_count": 1,
                "release_observed": "commercial_independence_ready=false",
                "release_required": "commercial_independence_ready=true",
                "requires_operator_action": True,
                "source_artifact": "runs/product_license_file_creation_work_order_current.json",
                "command": "python3 tools/write_product_license_file.py",
                "license_local_source_command_examples": (
                    "python3 tools/fill_product_license_decision_operator_intake.py "
                    "--approval-token APPROVE_PRODUCT_LICENSE_FILE_CREATION "
                    "--spdx-license-id Apache-2.0 "
                    "--license-text-source /usr/share/common-licenses/Apache-2.0"
                ),
                "recommended_action": "Approve and create LICENSE file.",
            },
        ],
    }
    work_order = {
        "summary": {
            "status": "product_public_benchmark_work_order_clear",
            "public_benchmark_validation_ready": True,
            "ready_required_suite_count": 5,
            "blocked_suite_count": 0,
            "benchmark_result_missing_artifact_count": 0,
        }
    }

    payload = mod.build_goal_bottleneck_briefing(
        release_gate_packet=_release_gate(),
        burndown_packet=burndown,
        action_board_packet={"summary": {"status": "operator_actions_required"}, "rows": []},
        intake_kit_packet={"summary": {"status": "goal_operator_intake_kit_ready"}, "rows": []},
        public_benchmark_work_order_packet=work_order,
    )

    summary = payload["summary"]
    first, second = payload["rows"]
    assert first["bottleneck_kind"] == "stale_blocked_until_public_benchmark_validation"
    assert first["is_current_bottleneck"] is False
    assert first["superseded_by_current_evidence"] is True
    assert first["requires_operator_action"] is False
    assert second["bottleneck_kind"] == "operator_approval_required"
    assert summary["primary_bottleneck_sequence"] == 2
    assert summary["primary_bottleneck_kind"] == "operator_approval_required"
    assert summary["primary_bottleneck_command"] == "python3 tools/write_product_license_file.py"
    assert summary["primary_bottleneck_command_candidate_count"] == 1
    assert "--spdx-license-id Apache-2.0" in summary["primary_bottleneck_command_candidates"][0]
    assert summary["current_bottleneck_count"] == 1
    assert summary["superseded_bottleneck_count"] == 1
    assert summary["approval_tokens_required"] == ["APPROVE_PRODUCT_LICENSE_FILE_CREATION"]


def test_goal_bottleneck_briefing_tool_writes_outputs(tmp_path: Path) -> None:
    release = tmp_path / "release.json"
    burndown = tmp_path / "burndown.json"
    actions = tmp_path / "actions.json"
    intake = tmp_path / "intake.json"
    release.write_text(json.dumps(_release_gate()) + "\n", encoding="utf-8")
    burndown.write_text(json.dumps(_burndown()) + "\n", encoding="utf-8")
    actions.write_text(json.dumps(_action_board()) + "\n", encoding="utf-8")
    intake.write_text(json.dumps(_intake_kit()) + "\n", encoding="utf-8")
    out_json = tmp_path / "bottlenecks.json"
    out_csv = tmp_path / "bottlenecks.csv"
    out_md = tmp_path / "bottlenecks.md"

    mod.main(
        [
            "--release-gate-json",
            str(release),
            "--burndown-json",
            str(burndown),
            "--action-board-json",
            str(actions),
            "--intake-kit-json",
            str(intake),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "goal_bottleneck_briefing_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("bottleneck_id,sequence,")
    assert "Goal Bottleneck Briefing" in out_md.read_text(encoding="utf-8")
