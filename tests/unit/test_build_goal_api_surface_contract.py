from __future__ import annotations

import json
from pathlib import Path

from tools import build_goal_api_surface_contract as mod


def _write_goal_api_surface(root: Path, *, include_router: bool = True, include_status_key: bool = True) -> None:
    (root / "api").mkdir()
    status_key = '"product_cli_status_set_status": "blocked_product_cli_status_set",' if include_status_key else ""
    (root / "api" / "goal.py").write_text(
        "GOAL_READINESS_ROLLUP_ARTIFACT = 'runs/goal_readiness_rollup_current.json'\n"
        "GOAL_OPERATOR_ACTION_BOARD_ARTIFACT = 'runs/goal_operator_action_board_current.json'\n"
        "GOAL_OPERATOR_INTAKE_KIT_MANIFEST = 'runs/goal_operator_intake_kit_current/manifest.json'\n"
        "GOAL_RELEASE_DECISION_ARTIFACT = 'runs/goal_release_decision_gate_current.json'\n"
        "GOAL_RELEASE_BURNDOWN_ARTIFACT = 'runs/goal_release_burndown_work_order_current.json'\n"
        "GOAL_BOTTLENECK_BRIEFING_ARTIFACT = 'runs/goal_bottleneck_briefing_current.json'\n"
        "GOAL_API_SURFACE_CONTRACT_ARTIFACT = 'runs/goal_api_surface_contract_current.json'\n"
        "PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT = 'runs/product_goal_completion_audit_current.json'\n"
        "PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT = 'runs/product_commercial_readiness_handoff_bundle_current.json'\n"
        "PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT = 'runs/product_full_commercial_blocker_evidence_matrix_current.json'\n"
        "PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_ARTIFACT = 'runs/product_scope_breadth_evidence_receipt_current.json'\n"
        "ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_ARTIFACT = 'runs/engine_refinement_claim_evidence_receipt_current.json'\n"
        "CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_ARTIFACT = 'runs/cameo_official_result_fetch_preflight_current.json'\n"
        "FULL_COMMERCIAL_RELEASE_BLOCKER_IDS = ('R8_full_scope_claim_closure', 'R9_engine_refinement_claim_promotion')\n"
        "FULL_COMMERCIAL_EVIDENCE_RECEIPT_STATUS_KEYS = ('product_scope_breadth_evidence_receipt_status', 'engine_refinement_claim_evidence_receipt_status')\n"
        '@router.get("/status")\n'
        "async def get_goal_status():\n"
        "    return {"
        + status_key
        + '"cameo_cli_status_set_status": "blocked_cameo_cli_status_set",'
        '"cleanup_cli_status_set_status": "blocked_cleanup_cli_status_set",'
        '"approval_tokens": [],'
        '"approval_reclaim_size_gb": 0.0,'
        '"protected_cleanup_payload_size_gb": 0.0,'
        '"product_operational_quality_ready": True,'
        '"product_operational_quality_status": "product_operational_quality_contract_ready",'
        '"product_operational_quality_blocker_count": 0,'
        '"product_operational_quality_artifact": "runs/product_operational_quality_contract_current.json",'
        '"cameo_evidence_integrity_ready": True,'
        '"cameo_evidence_integrity_status": "cameo_evidence_integrity_contract_ready",'
        '"cameo_evidence_integrity_blocker_count": 0,'
        '"cameo_evidence_integrity_artifact": "runs/cameo_evidence_integrity_contract_current.json",'
        '"cameo_official_results_pending_honest": True,'
        '"cameo_no_local_native_accuracy_substitution": True,'
        '"release_allowed": False,'
        '"restricted_release_allowed": True,'
        '"full_commercial_release_allowed": False,'
        '"release_blocker_count": 0,'
        '"bottleneck_count": 0,'
        '"primary_bottleneck_kind": "operator_approval_required",'
        '"primary_bottleneck_phase": "P1_product_execution_and_bundle_validation",'
        '"primary_bottleneck_root_cause_category": "operator_decision_or_external_result_required",'
        '"primary_bottleneck_locally_closable_without_operator_return": False,'
        '"primary_bottleneck_required_external_return": "approval token",'
        '"primary_bottleneck_post_return_acceptance_artifact": "runs/product_scope_breadth_contract_current.json",'
        '"completion_audit_release_blocker_bottleneck_count": 2,'
        '"irreducible_external_return_bottleneck_count": 2,'
        '"expected_full_commercial_release_blocker_ids": list(FULL_COMMERCIAL_RELEASE_BLOCKER_IDS),'
        '"full_commercial_release_blocker_ids": ["R8_full_scope_claim_closure", "R9_engine_refinement_claim_promotion"],'
        '"full_commercial_release_blocker_count": 2,'
        '"missing_full_commercial_release_blocker_ids": [],'
        '"full_commercial_release_blocker_visibility_ready": True,'
        '"primary_full_commercial_release_blocker_id": "R8_full_scope_claim_closure",'
        '"primary_full_commercial_release_blocker": "direct_binding_evidence_missing",'
        '"full_commercial_release_next_required_step": "Fill the R8/R9 receipt CSVs",'
        '"science_claim_promotion_gap_closure_status": "blocked_science_claim_promotion_gap_closure",'
        '"science_claim_promotion_gap_closure_recorded": True,'
        '"science_claim_promotion_gap_closure_all_gaps_closed": False,'
        '"science_claim_promotion_gap_closure_claim_promotion_allowed": False,'
        '"science_claim_promotion_gap_closure_open_gap_count": 2,'
        '"science_claim_promotion_gap_closure_open_gap_ids": ["SCI-GPCR", "SCI-OPENMM"],'
        '"science_claim_promotion_gap_closure_current_primary_open_gap_id": "SCI-GPCR",'
        '"science_claim_promotion_gap_closure_current_next_action": "Maintain conditional prior gate",'
        '"science_claim_promotion_gap_closure_primary_open_gap_area": "GPCR broad family",'
        '"science_claim_promotion_gap_closure_primary_open_gap_claim_promotion_status": "blocked_ci_low_oprm1",'
        '"science_claim_promotion_gap_closure_primary_open_gap_evidence": "runs/gpcr_conditional_prior_promotion_gate_current.json",'
        '"science_claim_promotion_gap_closure_primary_open_gap_next_action": "Maintain conditional prior gate",'
        '"science_claim_promotion_gap_closure_primary_open_gap_release_blocker": True,'
        '"accuracy_parity_scorecard_gate_present": True,'
        '"accuracy_parity_scorecard_status": "blocked_accuracy_parity",'
        '"accuracy_parity_scorecard_recorded": True,'
        '"accuracy_parity_scorecard_row_count": 5,'
        '"accuracy_parity_scorecard_pass_row_count": 4,'
        '"accuracy_parity_scorecard_restricted_pass_row_count": 0,'
        '"accuracy_parity_scorecard_blocked_row_count": 1,'
        '"accuracy_parity_scorecard_missing_row_count": 0,'
        '"accuracy_parity_scorecard_top_blocker_count": 4,'
        '"accuracy_parity_scorecard_top_blockers": ["ligand_ranking:claim_promotion_not_allowed", "ligand_ranking:ranking_pr_auc_below_threshold", "ligand_ranking:ranking_pr_auc_ci_low_below_threshold", "ligand_ranking:topk_hit_rate_below_threshold"],'
        '"accuracy_parity_scorecard_overall_commercial_tool_accuracy_parity_allowed": False,'
        '"accuracy_parity_scorecard_schrodinger_class_claim_allowed": False,'
        '"accuracy_parity_scorecard_openmm_class_claim_allowed": True,'
        '"accuracy_parity_scorecard_current_broad_accuracy_parity_estimate_pct": "40-50",'
        '"accuracy_parity_scorecard_current_broad_commercial_platform_estimate_pct": "35-45",'
        '"accuracy_parity_ligand_ranking_status": "blocked",'
        '"accuracy_parity_ligand_ranking_claim_promotion_allowed": False,'
        '"accuracy_parity_ligand_ranking_commercial_parity_claim_allowed": False,'
        '"accuracy_parity_ligand_ranking_blocker_count": 4,'
        '"accuracy_parity_ligand_ranking_blockers": ["claim_promotion_not_allowed", "ranking_pr_auc_below_threshold", "ranking_pr_auc_ci_low_below_threshold", "topk_hit_rate_below_threshold"],'
        '"accuracy_parity_ligand_ranking_pr_auc": 0.15749,'
        '"accuracy_parity_ligand_ranking_pr_auc_ci_low": 0.001347,'
        '"accuracy_parity_ligand_ranking_topk_hit_rate": 0.1,'
        '"accuracy_parity_ligand_ranking_positive_count": 13,'
        '"accuracy_parity_ligand_ranking_score_col_used": "binding_score_composite_v7_residual_active",'
        '"accuracy_parity_ligand_ranking_pr_auc_threshold": 0.55,'
        '"accuracy_parity_ligand_ranking_pr_auc_ci_low_threshold": 0.45,'
        '"accuracy_parity_ligand_ranking_topk_hit_rate_threshold": 0.5,'
        '"accuracy_parity_ligand_ranking_next_required_step": "Repair GPCR ligand-ranking parity",'
        '"api_runner_profile_promotion_operator_receipt_gate_present": True,'
        '"api_runner_profile_promotion_operator_receipt_status": "blocked_api_runner_profile_promotion_operator_receipt",'
        '"api_runner_profile_promotion_operator_receipt_recorded": True,'
        '"api_runner_profile_promotion_operator_receipt_ready": False,'
        '"api_runner_profile_promotion_operator_receipt_readiness_status": "api_runner_profile_promotion_ready",'
        '"api_runner_profile_promotion_operator_receipt_profile_count": 4,'
        '"api_runner_profile_promotion_operator_receipt_receipt_row_count": 4,'
        '"api_runner_profile_promotion_operator_receipt_pass_row_count": 0,'
        '"api_runner_profile_promotion_operator_receipt_blocked_row_count": 4,'
        '"api_runner_profile_promotion_operator_receipt_blocker_count": 1,'
        '"api_runner_profile_promotion_operator_receipt_blockers": ["blocked_receipt_rows_present"],'
        '"api_runner_profile_promotion_operator_receipt_first_blocked_profile_id": "backmapping_scoring.example",'
        '"api_runner_profile_promotion_operator_receipt_first_blocked_row_blocker": "operator_decision_missing",'
        '"api_runner_profile_promotion_operator_receipt_first_blocked_row_blockers": ["operator_decision_missing", "approval_token_invalid"],'
        '"api_runner_profile_promotion_operator_receipt_most_common_row_blocker": "operator_decision_missing",'
        '"api_runner_profile_promotion_operator_receipt_approval_token_required": "APPROVE_API_RUNNER_PROFILE_PROMOTION",'
        '"api_runner_profile_promotion_operator_receipt_operator_template_csv": "runs/api_runner_profile_promotion_operator_template_current.csv",'
        '"api_runner_profile_promotion_operator_receipt_next_required_step": "Fill the operator receipt",'
        '"api_runner_profile_promotion_operator_receipt_profile_enabled_by_this_tool": False,'
        '"api_runner_profile_promotion_operator_receipt_runner_executed": False,'
        '"api_runner_profile_promotion_operator_receipt_external_state_mutated": False,'
        '"product_goal_release_blocker_fail_count": 2,'
        '"product_goal_release_blocker_requirement_ids": ["R8_full_scope_claim_closure", "R9_engine_refinement_claim_promotion"],'
        '"product_goal_primary_release_blocker_requirement_id": "R8_full_scope_claim_closure",'
        '"product_goal_primary_release_blocker_tier": "full_commercial_scope",'
        '"product_goal_primary_release_blocker": "full_scope_claim_closure_not_ready",'
        '"product_goal_primary_release_blocker_next_command": "python3 tools/build_product_scope_breadth_closure_checklist.py",'
        '"primary_release_blocker_action_id": "product_scope_expansion:resolve_full_scope_breadth_evidence_receipt",'
        '"primary_release_blocker_action_status": "required",'
        '"primary_release_blocker_action_required_input": "config/product_scope_breadth_evidence_receipt_current.csv",'
        '"primary_release_blocker_action_artifact_path": "runs/product_scope_breadth_evidence_receipt_current.json",'
        '"primary_release_blocker_action_recommended_action": "Fill the full-scope evidence receipt",'
        '"product_goal_completion_audit_artifact_path": PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT,'
        '"production_ai_checkpoint_registry_promotion_required_gate_ids": ["production_promotion_allowed", "customer_facing_mutation_flags", "default_residual_mode_guarded", "trained_model_checkpoint_count_positive"],'
        '"production_ai_checkpoint_registry_promotion_missing_gate_ids": ["production_promotion_allowed", "customer_facing_mutation_flags", "default_residual_mode_guarded", "trained_model_checkpoint_count_positive"],'
        '"production_ai_checkpoint_registry_promotion_missing_gate_count": 4,'
        '"production_ai_checkpoint_registry_promotion_upstream_acceptance_ready": True,'
        '"production_ai_checkpoint_registry_promotion_currently_satisfied": False,'
        '"production_ai_checkpoint_actionable_operator_completion_packet_ready": True,'
        '"production_ai_checkpoint_actionable_operator_completion_artifact_id": "residual_model_registry_guarded_promotion",'
        '"production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns": ["production_promotion_allowed", "customer_facing_auto_correction_allowed", "customer_facing_score_mutation_allowed", "customer_facing_ranking_mutation_allowed", "default_residual_mode", "trained_model_checkpoint_count"],'
        '"production_ai_checkpoint_actionable_operator_completion_diagnostic_commands": ["python3 tools/build_residual_model_registry.py", "python3 tools/build_product_production_ai_checkpoint_readiness.py", "python3 tools/build_product_production_ai_promotion_workbench.py"],'
        '"production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count": 3,'
        '"production_ai_checkpoint_actionable_operator_completion_completion_rule": "registry_promotion_missing_gate_count=0 and registry_promotion_currently_satisfied=true",'
        '"production_ai_checkpoint_actionable_operator_completion_next_action": "Register or promote a trained preflight-ready production checkpoint",'
        '"commercial_readiness_handoff_bundle_status": "product_commercial_readiness_handoff_bundle_ready",'
        '"commercial_readiness_handoff_bundle_ready": True,'
        '"commercial_readiness_handoff_bundle_artifact_path": PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT,'
        '"commercial_readiness_handoff_bundle_artifact_reference_count": 28,'
        '"commercial_readiness_handoff_bundle_local_missing_artifact_reference_count": 0,'
        '"operator_intake_kit_full_commercial_evidence_receipt_entry_count": 2,'
        '"operator_intake_kit_full_commercial_evidence_receipt_operator_input_required_count": 2,'
        '"operator_intake_kit_full_commercial_evidence_receipt_current_action_required_count": 2,'
        '"operator_intake_kit_full_commercial_evidence_receipt_template_required_count": 2,'
        '"operator_intake_kit_full_commercial_evidence_receipt_template_present_count": 2,'
        '"operator_intake_kit_full_commercial_evidence_receipt_approval_token_count": 2,'
        '"operator_intake_kit_full_commercial_evidence_receipt_entry_ids": ["product_scope_breadth_evidence_receipt", "engine_refinement_claim_evidence_receipt"],'
        '"operator_intake_kit_full_commercial_evidence_receipt_source_gate_statuses": "product_scope_breadth_evidence_receipt=blocked_product_scope_breadth_evidence_receipt;engine_refinement_claim_evidence_receipt=blocked_engine_refinement_claim_evidence_receipt",'
        '"operator_intake_kit_full_commercial_evidence_receipt_required_inputs": "config/product_scope_breadth_evidence_receipt_current.csv;config/engine_refinement_claim_promotion_evidence_receipt_current.csv",'
        '"operator_intake_kit_full_commercial_evidence_receipt_approval_tokens": "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT;APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",'
        '"bottleneck_briefing_full_commercial_evidence_receipt_entry_count": 2,'
        '"bottleneck_briefing_full_commercial_evidence_receipt_operator_input_required_count": 2,'
        '"bottleneck_briefing_full_commercial_evidence_receipt_current_action_required_count": 2,'
        '"bottleneck_briefing_full_commercial_evidence_receipt_template_required_count": 2,'
        '"bottleneck_briefing_full_commercial_evidence_receipt_template_present_count": 2,'
        '"bottleneck_briefing_full_commercial_evidence_receipt_approval_token_count": 2,'
        '"bottleneck_briefing_full_commercial_evidence_receipt_entry_ids": ["product_scope_breadth_evidence_receipt", "engine_refinement_claim_evidence_receipt"],'
        '"bottleneck_briefing_full_commercial_evidence_receipt_source_gate_statuses": "product_scope_breadth_evidence_receipt=blocked_product_scope_breadth_evidence_receipt;engine_refinement_claim_evidence_receipt=blocked_engine_refinement_claim_evidence_receipt",'
        '"bottleneck_briefing_full_commercial_evidence_receipt_required_inputs": "config/product_scope_breadth_evidence_receipt_current.csv;config/engine_refinement_claim_promotion_evidence_receipt_current.csv",'
        '"bottleneck_briefing_full_commercial_evidence_receipt_approval_tokens": "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT;APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",'
        '"production_ai_registry_promotion_operator_receipt_status": "blocked_production_ai_registry_promotion_operator_receipt",'
        '"production_ai_registry_promotion_operator_receipt_ready": False,'
        '"production_ai_registry_promotion_operator_receipt_artifact": "runs/production_ai_registry_promotion_operator_receipt_current.json",'
        '"production_ai_registry_promotion_operator_receipt_csv": "config/production_ai_registry_promotion_operator_receipt_current.csv",'
        '"production_ai_registry_promotion_operator_receipt_approval_token_required": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",'
        '"production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker": "operator_placeholders_unfilled",'
        '"production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode": "shadow",'
        '"production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count": 0,'
        '"production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_currently_satisfied": False,'
        '"production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_missing_gate_ids": ["production_promotion_allowed", "default_residual_mode_guarded"],'
        '"production_ai_registry_promotion_priority_artifact": "runs/production_ai_registry_promotion_priority_packet_current.json",'
        '"production_ai_registry_promotion_priority_status": "blocked_production_ai_registry_promotion_priority_packet",'
        '"production_ai_registry_promotion_priority_packet_ready": True,'
        '"production_ai_registry_promotion_priority_registry_promotion_ready": False,'
        '"production_ai_registry_promotion_priority_operator_input_required_count": 4,'
        '"production_ai_registry_promotion_priority_blocked_priority_item_count": 4,'
        '"production_ai_registry_promotion_priority_missing_gate_count": 4,'
        '"production_ai_registry_promotion_priority_missing_gate_ids": ["trained_model_checkpoint_count_positive"],'
        '"production_ai_registry_promotion_priority_top_gate_id": "trained_model_checkpoint_count_positive",'
        '"production_ai_registry_promotion_priority_top_priority_bucket": "trained_checkpoint_registration_required",'
        '"production_ai_registry_promotion_priority_top_required_input": "Register a trained checkpoint",'
        '"production_ai_registry_promotion_priority_top_acceptance_artifact": "runs/residual_model_registry_current.json",'
        '"production_ai_registry_promotion_priority_top_verification_command": "python3 tools/build_residual_model_registry.py",'
        '"production_ai_registry_promotion_priority_top_next_operator_step": "Register checkpoint, then rerun registry readiness.",'
        '"production_ai_registry_promotion_priority_model_promoted": False,'
        '"production_ai_registry_promotion_priority_customer_facing_mutation_enabled": False,'
        '"production_ai_registry_promotion_priority_external_state_mutated": False,'
        '"cameo_official_result_fetch_preflight_status": "blocked_cameo_official_result_fetch_preflight",'
        '"cameo_official_result_fetch_preflight_ready": False,'
        '"cameo_official_result_fetch_preflight_artifact_path": CAMEO_OFFICIAL_RESULT_FETCH_PREFLIGHT_ARTIFACT,'
        '"cameo_official_result_fetch_preflight_operator_template_csv": "runs/cameo_official_result_fetch_operator_approval_template_current.csv",'
        '"cameo_official_result_fetch_preflight_operator_intake_csv": "runs/cameo_official_result_fetch_operator_approval_intake.csv",'
        '"cameo_official_result_fetch_preflight_kit_template_path": "runs/goal_operator_intake_kit_current/templates/cameo_official_result_fetch_operator_approval_template_current.csv",'
        '"cameo_official_result_fetch_preflight_approval_token_required": "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH",'
        '"cameo_official_result_fetch_preflight_kit_status": "approval_required",'
        '"cameo_official_result_fetch_preflight_operator_fetch_csv_present": False,'
        '"cameo_official_result_fetch_preflight_authorized_for_separate_operator_fetch": False,'
        '"cameo_official_result_fetch_preflight_network_request_opened": False,'
        '"cameo_official_result_fetch_preflight_official_results_fetched": False,'
        '"cameo_official_result_fetch_preflight_native_local_accuracy_used": False,'
        '"cameo_official_result_fetch_preflight_external_state_mutated": False,'
        '"cameo_official_result_fetch_preflight_blocker_count": 2,'
        '"cameo_official_result_fetch_preflight_blockers": ["operator_decision_missing", "operator_fetch_csv_missing"],'
        '"product_scope_breadth_evidence_receipt_status": "blocked_product_scope_breadth_evidence_receipt",'
        '"product_scope_breadth_evidence_receipt_ready": False,'
        '"product_scope_breadth_evidence_receipt_artifact_path": PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT_ARTIFACT,'
        '"product_scope_breadth_evidence_receipt_csv": "config/product_scope_breadth_evidence_receipt_current.csv",'
        '"product_scope_breadth_evidence_receipt_csv_present": True,'
        '"product_scope_breadth_evidence_receipt_approval_token_required": "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT",'
        '"product_scope_breadth_evidence_receipt_receipt_row_count": 6,'
        '"product_scope_breadth_evidence_receipt_pass_row_count": 0,'
        '"product_scope_breadth_evidence_receipt_blocked_row_count": 6,'
        '"product_scope_breadth_evidence_receipt_blocker_count": 1,'
        '"product_scope_breadth_evidence_receipt_evidence_artifact_present_count": 0,'
        '"product_scope_breadth_evidence_receipt_evidence_status_verified_count": 0,'
        '"product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id": "direct_binding_evidence_missing",'
        '"product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",'
        '"product_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status": "product_scope_transporter_direct_binding_evidence_ready",'
        '"product_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status": "missing",'
        '"product_scope_breadth_evidence_receipt_first_blocked_missing_true_fields": ["transporter_direct_binding_evidence_ready"],'
        '"product_scope_breadth_evidence_receipt_first_blocked_row_blockers": ["operator_placeholders_unfilled"],'
        '"product_scope_breadth_evidence_receipt_most_common_row_blocker": "operator_placeholders_unfilled",'
        '"product_scope_breadth_evidence_receipt_required_blocker_count": 6,'
        '"product_scope_breadth_evidence_receipt_required_blockers": ["direct_binding_evidence_missing"],'
        '"product_scope_breadth_evidence_receipt_next_required_step": "Replace placeholder receipt rows",'
        '"product_scope_breadth_evidence_receipt_external_state_mutated": False,'
        '"engine_refinement_claim_evidence_receipt_status": "blocked_engine_refinement_claim_evidence_receipt",'
        '"engine_refinement_claim_evidence_receipt_ready": False,'
        '"engine_refinement_claim_evidence_receipt_artifact_path": ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT_ARTIFACT,'
        '"engine_refinement_claim_evidence_receipt_csv": "config/engine_refinement_claim_promotion_evidence_receipt_current.csv",'
        '"engine_refinement_claim_evidence_receipt_csv_present": True,'
        '"engine_refinement_claim_evidence_receipt_approval_token_required": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",'
        '"engine_refinement_claim_evidence_receipt_receipt_row_count": 6,'
        '"engine_refinement_claim_evidence_receipt_pass_row_count": 0,'
        '"engine_refinement_claim_evidence_receipt_blocked_row_count": 6,'
        '"engine_refinement_claim_evidence_receipt_blocker_count": 1,'
        '"engine_refinement_claim_evidence_receipt_evidence_artifact_present_count": 0,'
        '"engine_refinement_claim_evidence_receipt_evidence_status_verified_count": 0,'
        '"engine_refinement_claim_evidence_receipt_first_blocked_blocker_id": "public_benchmark_gate_not_ready",'
        '"engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",'
        '"engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status": "refine_tier_public_benchmark_ready",'
        '"engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status": "missing",'
        '"engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields": ["claim_grade_public_benchmark_ready"],'
        '"engine_refinement_claim_evidence_receipt_first_blocked_row_blockers": ["operator_placeholders_unfilled"],'
        '"engine_refinement_claim_evidence_receipt_most_common_row_blocker": "operator_placeholders_unfilled",'
        '"engine_refinement_claim_evidence_receipt_required_blocker_count": 6,'
        '"engine_refinement_claim_evidence_receipt_required_blockers": ["public_benchmark_gate_not_ready"],'
        '"engine_refinement_claim_evidence_receipt_next_required_step": "Replace placeholder receipt rows",'
        '"engine_refinement_claim_evidence_receipt_external_state_mutated": False,'
        '"full_commercial_blocker_evidence_matrix_status": "blocked_product_full_commercial_blocker_evidence_matrix",'
        '"full_commercial_blocker_evidence_matrix_ready": False,'
        '"full_commercial_blocker_evidence_matrix_artifact_path": PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT,'
        '"full_commercial_blocker_evidence_matrix_release_blocker_visibility_ready": True,'
        '"full_commercial_blocker_evidence_matrix_row_count": 12,'
        '"full_commercial_blocker_evidence_matrix_blocked_row_count": 12,'
        '"full_commercial_blocker_evidence_matrix_approval_token_count": 2,'
        '"full_commercial_blocker_evidence_matrix_first_blocked_release_blocker_id": "R8_full_scope_claim_closure",'
        '"full_commercial_blocker_evidence_matrix_first_blocked_evidence_row_id": "direct_binding_evidence_missing",'
        '"full_commercial_blocker_evidence_matrix_first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",'
        '"full_commercial_blocker_evidence_matrix_first_blocked_expected_evidence_status": "product_scope_transporter_direct_binding_evidence_ready",'
        '"full_commercial_blocker_evidence_matrix_first_blocked_observed_evidence_status": "missing",'
        '"full_commercial_blocker_evidence_matrix_first_blocked_row_blockers": "operator_placeholders_unfilled",'
        '"full_commercial_blocker_evidence_matrix_first_blocked_acceptance_artifact": "runs/product_scope_breadth_evidence_receipt_current.json",'
        '"full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker": "operator_placeholders_unfilled",'
        '"full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker": "operator_placeholders_unfilled",'
        '"operator_action_count": 0,'
        '"operator_intake_kit_status": "goal_operator_intake_kit_ready",'
        '"operator_intake_kit_release_burndown_linked_entry_count": 0,'
        '"primary_action_id": "product_ai_production:return_gpu_force_regeneration_receipt",'
        '"primary_action_status": "required",'
        '"primary_action_required_input": "GPU full-regeneration summary and manifest with operator verification",'
        '"primary_action_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",'
        '"primary_action_recommended_action": "Run the full regeneration command on a GPU worker",'
        '"primary_action_artifact_path": "runs/product_goal_completion_audit_current.json",'
        '"goal_api_surface_contract_status": "goal_api_surface_contract_ready",'
        '"release_complete_vs_operator_pending_lane": "release_complete_operator_pending_split",'
        '"goal_completion_audit_goal_complete": True,'
        '"release_complete_lane_ready": True,'
        '"operator_pending_lane_ready": False,'
        '"execution_enabled": False,'
        '"action_executed": False,'
        '"delete_executed": False,'
        '"archive_executed": False,'
        '"externalize_executed": False,'
        '"upload_executed": False,'
        '"docking_results_emitted": False,'
        '"prediction_generation_enabled": False,'
        '"server_registration_mutated": False,'
        '"outbound_email_enabled": False,'
        '"external_state_mutated": False}\n'
        '@router.get("/readiness")\n'
        "async def get_goal_readiness(): pass\n"
        '@router.get("/actions")\n'
        "async def get_goal_actions(): pass\n"
        '@router.get("/operator-intake-kit")\n'
        "async def get_goal_operator_intake_kit(): pass\n"
        '@router.get("/release-decision")\n'
        "async def get_goal_release_decision(): pass\n"
        '@router.get("/burndown")\n'
        "async def get_goal_burndown(): pass\n"
        '@router.get("/bottlenecks")\n'
        "async def get_goal_bottlenecks(): pass\n"
        '@router.get("/api-contract")\n'
        "async def get_goal_api_contract():\n"
        "    return {'status': 'missing_goal_api_surface_contract', 'artifact_path': GOAL_API_SURFACE_CONTRACT_ARTIFACT}\n",
        encoding="utf-8",
    )
    (root / "api" / "main.py").write_text(
        "from api.goal import router as goal_router\napp.include_router(goal_router)\n" if include_router else "",
        encoding="utf-8",
    )
    (root / "api" / "security.py").write_text(
        'ALLOWED_PRODUCT_PREFIXES = ("/product", "/goal", "/metrics")\n',
        encoding="utf-8",
    )


def test_goal_api_surface_contract_reports_ready_for_current_source() -> None:
    payload = mod.build_goal_api_surface_contract(root=".")

    summary = payload["summary"]
    assert summary["status"] == "goal_api_surface_contract_ready"
    assert summary["surface_ready"] is True
    assert summary["check_count"] == 9
    assert summary["pass_count"] == 9
    assert summary["blocker_count"] == 0
    assert summary["expected_endpoint_count"] == 8
    assert summary["missing_endpoint_count"] == 0
    assert summary["missing_artifact_source_count"] == 0
    assert summary["missing_status_key_count"] == 0
    assert summary["missing_full_commercial_visibility_token_count"] == 0
    assert summary["missing_fail_closed_flag_count"] == 0
    assert summary["goal_router_registered"] is True
    assert summary["goal_security_allowlist_permits_goal_prefix"] is True
    assert summary["goal_api_contract_endpoint_present"] is True
    assert summary["goal_api_contract_endpoint_reads_contract"] is True
    assert summary["execution_enabled"] is False
    assert summary["delete_executed"] is False
    assert summary["outbound_email_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert payload["blockers"] == []


def test_goal_api_surface_contract_blocks_unmounted_router(tmp_path: Path) -> None:
    _write_goal_api_surface(tmp_path, include_router=False)

    payload = mod.build_goal_api_surface_contract(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_goal_api_surface_contract"
    assert payload["summary"]["goal_router_registered"] is False
    assert any(blocker["code"] == "goal_router_registered_not_ready" for blocker in payload["blockers"])


def test_goal_api_surface_contract_blocks_security_allowlist_without_goal_prefix(tmp_path: Path) -> None:
    _write_goal_api_surface(tmp_path)
    (tmp_path / "api" / "security.py").write_text(
        'ALLOWED_PRODUCT_PREFIXES = ("/product", "/metrics")\n',
        encoding="utf-8",
    )

    payload = mod.build_goal_api_surface_contract(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_goal_api_surface_contract"
    assert payload["summary"]["goal_security_allowlist_permits_goal_prefix"] is False
    assert any(
        blocker["code"] == "goal_security_allowlist_permits_goal_prefix_not_ready"
        for blocker in payload["blockers"]
    )


def test_goal_api_surface_contract_blocks_missing_status_key(tmp_path: Path) -> None:
    _write_goal_api_surface(tmp_path, include_status_key=False)

    payload = mod.build_goal_api_surface_contract(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_goal_api_surface_contract"
    assert payload["summary"]["missing_status_key_count"] >= 1
    assert any(blocker["check"] == "goal_status_rollup_keys_present" for blocker in payload["blockers"])


def test_goal_api_surface_contract_tool_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "goal_api_surface.json"
    out_csv = tmp_path / "goal_api_surface.csv"
    out_md = tmp_path / "goal_api_surface.md"

    mod.main(["--root", ".", "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "goal_api_surface_contract_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Goal API Surface Contract" in out_md.read_text(encoding="utf-8")
