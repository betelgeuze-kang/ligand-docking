from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_commercial_readiness_handoff_bundle as mod


def _operator_packet(ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "product_commercial_readiness_operator_packet_ready" if ready else "blocked",
            "packet_ready": ready,
            "source_fingerprint_ready": ready,
            "goal_complete": False,
            "engine_refinement_claim_promotion_ready": False,
            "engine_refinement_claim_promotion_blocker_count": 6,
            "engine_refinement_claim_promotion_action_row_count": 6,
            "engine_refinement_claim_promotion_blockers": [
                "public_benchmark_gate_not_ready",
                "external_structure_quality_parity_not_ready",
            ],
            "engine_refinement_claim_promotion_action_board_csv": (
                "runs/engine_refinement_claim_promotion_action_board_current.csv"
            ),
            "engine_refinement_claim_evidence_receipt_ready": False,
            "engine_refinement_claim_evidence_receipt_status": (
                "blocked_engine_refinement_claim_evidence_receipt"
            ),
            "engine_refinement_claim_evidence_receipt_blocked_row_count": 6,
            "engine_refinement_claim_evidence_receipt_artifact": (
                "runs/engine_refinement_claim_evidence_receipt_current.json"
            ),
            "engine_refinement_claim_evidence_receipt_csv": (
                "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
            ),
            "engine_refinement_claim_evidence_receipt_first_blocked_blocker_id": (
                "public_benchmark_gate_not_ready"
            ),
            "engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact": (
                "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
            ),
            "engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status": (
                "refine_tier_public_benchmark_ready"
            ),
            "engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status": (
                "missing"
            ),
            "engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields": [
                "claim_grade_public_benchmark_ready"
            ],
            "engine_refinement_claim_evidence_receipt_first_blocked_row_blockers": [
                "operator_placeholders_unfilled",
                "evidence_artifact_not_found",
            ],
            "engine_refinement_claim_evidence_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "engine_refinement_claim_evidence_operator_field_worksheet_artifact": (
                "runs/engine_refinement_claim_evidence_operator_field_worksheet_current.json"
            ),
            "engine_refinement_claim_evidence_operator_field_worksheet_status": (
                "engine_refinement_claim_evidence_operator_field_worksheet_ready"
            ),
            "engine_refinement_claim_evidence_operator_field_worksheet_ready": True,
            "engine_refinement_claim_evidence_operator_field_worksheet_operator_fill_complete": False,
            "engine_refinement_claim_evidence_operator_field_worksheet_field_row_count": 144,
            "engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count": 108,
            "engine_refinement_claim_evidence_operator_field_worksheet_receipt_pending_field_count": 36,
            "engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count": 72,
            "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id": (
                "public_benchmark_gate_not_ready"
            ),
            "engine_refinement_claim_evidence_operator_field_worksheet_top_priority_bucket": (
                "public_benchmark_work_order_apply_required"
            ),
            "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_pending_field_count": 78,
            "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_apply_blocked_row_count": 8,
            "engine_refinement_claim_evidence_operator_field_worksheet_claim_promoted": False,
            "engine_refinement_claim_evidence_operator_field_worksheet_external_engine_calls_executed": False,
            "engine_refinement_claim_evidence_operator_field_worksheet_external_state_mutated": False,
            "engine_refinement_claim_promotion_next_required_step": (
                "Fill and apply curated public benchmark rows, then calibrate claim-grade parameterization gates."
            ),
            "product_scope_breadth_evidence_receipt_status": (
                "blocked_product_scope_breadth_evidence_receipt"
            ),
            "product_scope_breadth_evidence_receipt_ready": False,
            "product_scope_breadth_evidence_receipt_blocker_count": 1,
            "product_scope_breadth_evidence_receipt_blocked_row_count": 6,
            "product_scope_breadth_evidence_receipt_required_scope_blocker_count": 6,
            "product_scope_breadth_evidence_receipt_artifact": (
                "runs/product_scope_breadth_evidence_receipt_current.json"
            ),
            "product_scope_breadth_evidence_receipt_csv": (
                "config/product_scope_breadth_evidence_receipt_current.csv"
            ),
            "product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id": (
                "direct_binding_evidence_missing"
            ),
            "product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact": (
                "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
            ),
            "product_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status": (
                "product_scope_transporter_direct_binding_evidence_ready"
            ),
            "product_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status": (
                "missing"
            ),
            "product_scope_breadth_evidence_receipt_first_blocked_missing_true_fields": [
                "transporter_direct_binding_evidence_ready"
            ],
            "product_scope_breadth_evidence_receipt_first_blocked_row_blockers": [
                "operator_placeholders_unfilled",
                "evidence_artifact_not_found",
            ],
            "product_scope_breadth_evidence_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "primary_full_commercial_release_blocker_id": "R8_full_scope_claim_closure",
            "primary_full_commercial_release_blocker_requirement_id": (
                "R8_full_scope_claim_closure"
            ),
            "primary_full_commercial_release_blocker_tier": "full_commercial_scope",
            "primary_full_commercial_release_blocker": "full_scope_claim_closure_not_ready",
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
                "Fill the full-scope evidence receipt rows."
            ),
            "product_scope_next_operator_completion_intake_mode": "local_crosscheck_triage",
            "product_scope_next_operator_completion_item_id": "AQP1.core_binder_01",
            "product_scope_next_operator_completion_required_evidence_type": (
                "exact_transporter_target_pair_quantitative_binder_kcal"
            ),
            "product_scope_next_operator_completion_transporter_best_evidence_activity_type": "KD",
            "product_scope_next_operator_completion_transporter_best_evidence_value": "174000.0",
            "product_scope_next_operator_completion_transporter_best_evidence_units": "nM",
            "product_scope_next_operator_completion_transporter_best_evidence_document_id": (
                "CHEMBL6182835"
            ),
            "product_scope_next_operator_completion_transporter_best_evidence_source_file": (
                "runs/life_science_skill_crosscheck/chembl_activity_aqp1_target_current_recheck.json"
            ),
            "product_scope_next_operator_completion_transporter_claim_safe_blocker": (
                "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed"
            ),
            "product_scope_next_operator_completion_transporter_operator_next_verdict": (
                "manual_match_candidate_to_exact_source_then_sync_reference_split_meta"
            ),
            "product_scope_transporter_p0_evidence_acquisition_next_slot_id": (
                "AQP1.core_binder_01"
            ),
            "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": True,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": (
                "runs/transporter_manual_review_intake_template_current.csv"
            ),
            "product_scope_transporter_p0_return_bundle_required_artifact_count": 5,
            "product_scope_transporter_p0_return_bundle_required_artifacts": [
                "runs/transporter_manual_review_intake_template_current.csv",
                "config/ligand_binding_reference_blind_aqp1_v1.csv",
                "config/ligand_eval_splits_blind_aqp1_v1.csv",
                "runs/transporter_binder_promotion_gate_current.json",
                "runs/product_scope_breadth_contract_current.json",
            ],
            "product_scope_transporter_p0_return_bundle_blocker_count": 5,
            "product_scope_transporter_p0_return_bundle_next_artifact_id": (
                "operator_review_row"
            ),
            "product_scope_transporter_p0_return_bundle_next_artifact_path": (
                "runs/transporter_manual_review_intake_template_current.csv"
            ),
            "product_scope_transporter_p0_return_bundle_next_artifact_failed_check_ids": [
                "next_slot_required_missing_fields"
            ],
            "product_scope_transporter_p0_operator_validation_candidate_ready": True,
            "product_scope_transporter_p0_operator_validation_candidate_status": (
                "operator_validation_required"
            ),
            "product_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier": (
                "CHEMBL20"
            ),
            "product_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol": (
                "-5.13"
            ),
            "product_scope_transporter_p0_operator_validation_candidate_blocker": (
                "data_validity_outside_typical_range_and_assay_origin_unknown"
            ),
            "product_scope_transporter_p0_operator_validation_candidate_claim_safe_ready": False,
            "product_scope_transporter_p0_operator_validation_candidate_placeholder_count": 6,
            "product_scope_transporter_p0_operator_validation_candidate_required_decision_field_count": 6,
            "product_scope_transporter_p0_external_operator_artifacts": [
                "runs/aqp1_direct_binding_external_evidence_operator_fill_guide_current.json",
                "runs/aqp1_direct_binding_external_evidence_operator_worksheet_current.json",
                "runs/aqp1_direct_binding_external_evidence_operator_staging_apply_current.json",
            ],
            "product_scope_transporter_p0_external_operator_fill_guide_artifact": (
                "runs/aqp1_direct_binding_external_evidence_operator_fill_guide_current.json"
            ),
            "product_scope_transporter_p0_external_operator_fill_guide_status": (
                "aqp1_direct_binding_external_evidence_operator_fill_guide_ready"
            ),
            "product_scope_transporter_p0_external_operator_fill_guide_ready": True,
            "product_scope_transporter_p0_external_operator_fill_guide_row_count": 3,
            "product_scope_transporter_p0_external_operator_worksheet_artifact": (
                "runs/aqp1_direct_binding_external_evidence_operator_worksheet_current.json"
            ),
            "product_scope_transporter_p0_external_operator_worksheet_status": (
                "aqp1_direct_binding_external_evidence_operator_worksheet_ready"
            ),
            "product_scope_transporter_p0_external_operator_worksheet_ready": True,
            "product_scope_transporter_p0_external_operator_worksheet_field_row_count": 42,
            "product_scope_transporter_p0_external_operator_worksheet_pending_field_count": 19,
            "product_scope_transporter_p0_external_operator_worksheet_validation_error_count": 0,
            "product_scope_transporter_p0_external_operator_worksheet_supplement_csv": (
                "runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv"
            ),
            "product_scope_transporter_p0_external_operator_staging_apply_artifact": (
                "runs/aqp1_direct_binding_external_evidence_operator_staging_apply_current.json"
            ),
            "product_scope_transporter_p0_external_operator_staging_apply_status": (
                "blocked_aqp1_operator_staging_apply"
            ),
            "product_scope_transporter_p0_external_operator_staging_apply_mode": "preview",
            "product_scope_transporter_p0_external_operator_staging_apply_live_apply_allowed": False,
            "product_scope_transporter_p0_external_operator_staging_apply_validation_error_count": 2,
            "product_scope_transporter_p0_external_operator_staging_apply_claim_safe_approved_count": 0,
            "action_count": 4,
            "blocked_action_count": 4,
            "parallelizable_action_count": 2,
            "parallelizable_action_ids": [
                "transporter_next_slot_exact_evidence",
                "pxr_next_exact_review",
            ],
            "first_parallelizable_action_id": "transporter_next_slot_exact_evidence",
            "first_parallelizable_action_artifact": (
                "runs/transporter_manual_review_intake_template_current.csv"
            ),
            "first_parallelizable_action_next_action": "Acquire exact transporter evidence.",
            "first_parallelizable_action_validation_command": (
                "python3 tools/build_product_scope_breadth_contract.py"
            ),
            "first_parallelizable_action_required_operator_inputs": (
                "target_id;candidate_ligand_id;reference_binding_kcal_mol"
            ),
            "first_parallelizable_action_required_exact_evidence_fields": (
                "target_id;direct_binding_or_claim_safe_kcal_basis;target_match_decision"
            ),
            "first_parallelizable_action_required_claim_guardrails": (
                "functional_surrogate_does_not_authorize_direct_binding_claim"
            ),
            "first_parallelizable_action_expected_evidence_type": (
                "direct_or_claim_safe_binding_kcal"
            ),
            "first_parallelizable_action_required_missing_fields": (
                "replacement_reference_binding_kcal_mol"
            ),
            "first_parallelizable_action_operator_review_artifact": (
                "runs/transporter_manual_review_intake_template_current.csv"
            ),
            "first_parallelizable_action_post_intake_synchronization_targets": (
                "config/ligand_binding_reference_blind_aqp1_v1.csv"
            ),
            "first_parallelizable_action_acceptance_gate_commands": (
                "python3 tools/build_product_scope_breadth_contract.py"
            ),
            "first_parallelizable_action_next_slot_source_modality_guard_ready": True,
            "first_parallelizable_action_next_slot_source_modality": (
                "functional_quantitative_surrogate"
            ),
            "first_parallelizable_action_next_slot_source_modality_claim_safe": False,
            "first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed": False,
            "first_parallelizable_action_next_slot_source_modality_decision": (
                "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
            ),
            "first_parallelizable_action_next_slot_source_modality_guardrails": [
                "functional_quantitative_surrogate_is_review_only",
            ],
            "first_parallelizable_action_next_slot_source_modality_observed_signal": (
                "request_mode=exact_target_pair_quantitative_binder_kcal_required"
            ),
            "first_parallelizable_action_next_slot_source_modality_required_upgrade": (
                "exact target-pair direct/claim-safe binding kcal/mol"
            ),
            "first_parallelizable_action_next_slot_source_modality_triage_artifact": (
                "runs/aqp1_binding_source_modality_triage_current.json"
            ),
            "first_parallelizable_action_next_slot_source_modality_triage_decision": (
                "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
            ),
            "first_parallelizable_action_next_slot_source_modality_direct_experimental_binding_row_count": 0,
            "first_parallelizable_action_next_slot_source_modality_claim_safe_binding_kcal_ready_count": 0,
            "first_parallelizable_action_next_slot_source_modality_computational_binding_energy_row_count": 1,
            "first_parallelizable_action_next_slot_source_modality_best_computational_binding_energy_kcal_mol": "-34.48",
            "first_parallelizable_action_operator_validation_candidate_ready": True,
            "first_parallelizable_action_operator_validation_candidate_status": (
                "operator_validation_required"
            ),
            "first_parallelizable_action_operator_validation_candidate_ligand_external_identifier": (
                "CHEMBL20"
            ),
            "first_parallelizable_action_operator_validation_candidate_reference_binding_kcal_mol": (
                "-5.13"
            ),
            "first_parallelizable_action_operator_validation_candidate_blocker": (
                "data_validity_outside_typical_range_and_assay_origin_unknown"
            ),
            "first_parallelizable_action_operator_validation_candidate_claim_safe_ready": False,
            "first_parallelizable_action_direct_binding_procurement_packet_ready": True,
            "first_parallelizable_action_direct_binding_procurement_packet_status": (
                "aqp1_direct_binding_procurement_packet_ready"
            ),
            "first_parallelizable_action_direct_binding_procurement_packet_artifact": (
                "runs/aqp1_direct_binding_procurement_packet_current.json"
            ),
            "first_parallelizable_action_direct_binding_procurement_direct_binding_gap_open": True,
            "first_parallelizable_action_direct_binding_procurement_external_primary_evidence_required": True,
            "first_parallelizable_action_direct_binding_procurement_first_required_external_action_id": (
                "procure_aqp1_bacopaside_ii_direct_binding_measurement"
            ),
            "first_parallelizable_action_direct_binding_procurement_current_operator_candidate_blocker": (
                "data_validity_outside_typical_range_and_assay_origin_unknown"
            ),
            "first_parallelizable_action_direct_binding_procurement_minimum_acceptance_rule": (
                "target_uniprot=P29972; standard_type in Kd,Ki; operator_claim_safe_decision=approve_claim_safe"
            ),
            "first_parallelizable_action_direct_binding_procurement_accepted_direct_binding_methods": (
                "SPR equilibrium Kd;ITC Kd"
            ),
            "first_parallelizable_action_direct_binding_procurement_acceptance_fields": (
                "target_uniprot;standard_value_nM;operator_claim_safe_decision"
            ),
            "first_parallelizable_action_lane_id": "parallel_scope_evidence",
            "first_parallelizable_action_precondition": (
                "Can be completed while ROCm/GPU environment is being prepared."
            ),
            "production_ai_return_action_id": "production_ai_return_summary",
            "production_ai_return_action_artifact": (
                "runs/residual_force_trajectory_regeneration_current_summary.json"
            ),
            "production_ai_return_action_next_action": "Return the completed GPU summary JSON.",
            "production_ai_return_action_execution_command": (
                "python3 tools/generate_ligand_trajectory_engine.py --prod-mode"
            ),
            "production_ai_return_action_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "production_ai_return_action_blocked_by_action_id": (
                "production_gpu_execution_environment"
            ),
            "production_ai_return_action_required_operator_inputs": "queue_rows;processed_rows;ok_rows",
            "production_ai_return_action_required_evidence": (
                "queue_rows equals expected_queue_rows; processed_rows>=expected_queue_rows"
            ),
            "production_ai_return_operator_completion_packet_ready": True,
            "production_ai_return_operator_completion_artifact_id": "returned_summary_json",
            "production_ai_return_operator_completion_artifact_path": (
                "runs/residual_force_trajectory_regeneration_current_summary.json"
            ),
            "production_ai_return_operator_completion_required_fields_or_columns": [
                "queue_rows",
                "processed_rows",
                "ok_rows",
            ],
            "production_ai_return_operator_completion_expected_queue_rows": 768,
            "production_ai_return_operator_completion_completion_rule": (
                "queue_rows equals expected_queue_rows; processed_rows>=expected_queue_rows"
            ),
            "production_ai_return_operator_completion_backend_provenance_completion_rule": (
                "prod_mode=true; require_rust_hip=true"
            ),
            "production_ai_return_bundle_required_artifact_count": 4,
            "production_ai_return_bundle_required_artifacts": [
                "runs/residual_force_trajectory_regeneration_current_summary.json",
                "runs/residual_force_trajectory_regeneration_current_manifest.csv",
            ],
            "production_ai_return_bundle_next_artifact_id": "returned_summary_json",
            "production_ai_return_bundle_next_artifact_path": (
                "runs/residual_force_trajectory_regeneration_current_summary.json"
            ),
            "production_ai_return_bundle_next_artifact_failed_check_ids": [
                "actual_summary_returned_complete"
            ],
            "production_ai_return_bundle_manifest_required_columns": [
                "queue_id",
                "operator_verified_npz_exists",
            ],
            "production_ai_return_bundle_post_return_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "production_ai_return_bundle_guardrail": (
                "Returned summary alone does not unlock production AI."
            ),
            "delta_force_closure_acceptance_packet_artifact": (
                "runs/residual_delta_force_closure_acceptance_packet_current.json"
            ),
            "delta_force_closure_acceptance_packet_ready": True,
            "delta_force_closure_ready": False,
            "delta_force_closure_first_blocked_output_field": "delta_force",
            "delta_force_closure_ready_output_field_count": 6,
            "delta_force_closure_blocked_output_field_count": 1,
            "delta_force_closure_failed_stage_count": 9,
            "delta_force_closure_failed_stage_ids": [
                "gpu_worker_return_receipt",
                "force_derivation_validation",
            ],
            "delta_force_closure_next_stage_id": "gpu_worker_return_receipt",
            "delta_force_closure_next_stage_artifact": (
                "runs/residual_force_gpu_worker_return_receipt_current.json"
            ),
            "delta_force_closure_next_stage_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "delta_force_closure_next_required_step": "Return GPU worker receipt.",
            "delta_force_closure_operator_return_required_artifact_count": 2,
            "delta_force_closure_operator_return_required_artifacts": [
                "runs/residual_force_trajectory_regeneration_current_summary.json",
                "runs/residual_force_trajectory_regeneration_current_manifest.csv",
            ],
            "delta_force_closure_return_summary_required_fields": [
                "queue_rows",
                "processed_rows",
            ],
            "delta_force_closure_post_return_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "scope_closure_acceptance_packet_artifact": (
                "runs/product_scope_closure_acceptance_packet_current.json"
            ),
            "scope_closure_acceptance_packet_ready": True,
            "scope_closure_ready": False,
            "scope_closure_stage_count": 5,
            "scope_closure_blocked_stage_count": 4,
            "scope_closure_blocked_stage_ids": [
                "transporter_claim_acceptance",
                "pxr_claim_acceptance",
            ],
            "scope_closure_next_stage_id": "transporter_claim_acceptance",
            "scope_closure_next_stage_artifact": (
                "runs/transporter_manual_review_intake_template_current.csv"
            ),
            "scope_closure_next_stage_validation_command": (
                "python3 tools/build_product_scope_breadth_contract.py"
            ),
            "scope_closure_first_blocked_evidence_row_id": "AQP1.core_binder_01",
            "scope_closure_first_blocked_target_id": "AQP1",
            "scope_closure_first_blocked_candidate": "aqp1_bacopaside_ii_review_seed",
            "scope_closure_first_blocked_required_missing_fields": (
                "replacement_reference_binding_kcal_mol"
            ),
            "scope_closure_transporter_unresolved_slot_count": 11,
            "scope_closure_pxr_direct_or_claim_safe_quantitative_ready_count": 0,
            "scope_closure_general_platform_claim_allowed": False,
            "scope_closure_next_required_step": "Acquire exact target-pair evidence.",
            "first_operator_completion_worker_runtime_receipt_contract_ready": True,
            "first_operator_completion_worker_runtime_receipt_contract": {
                "manifest_ready": True,
                "torch_rocm_ready": True,
                "amd_gpu_detected": True,
                "visible_device_count": 1,
            },
            "first_operator_completion_worker_runtime_receipt_required_fields_or_columns": [
                "manifest_ready",
                "torch_rocm_ready",
                "amd_gpu_detected",
                "visible_device_count",
                "backend_counts",
            ],
            "first_operator_completion_worker_runtime_receipt_required_field_count": 5,
            "first_operator_completion_worker_runtime_receipt_completion_rule": (
                "manifest_ready=true; torch_rocm_ready=true; visible_device_count>0"
            ),
            "first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id": (
                "gpu_return_acceptance"
            ),
            "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact": (
                "runs/residual_force_gpu_worker_return_receipt_current.json"
            ),
            "first_operator_completion_worker_runtime_receipt_post_environment_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "first_operator_completion_worker_runtime_receipt_full_regeneration_command": (
                "python3 tools/generate_ligand_trajectory_engine.py --prod-mode"
            ),
            "first_operator_completion_worker_runtime_receipt_guardrails": [
                "cpu_fallback_does_not_satisfy_production_inference",
            ],
            "first_operator_completion_diagnostic_commands": [
                "python3 tools/build_rocm_environment_manifest.py",
                "rocminfo",
                "python3 -c \"import torch; print(torch.cuda.device_count())\"",
            ],
            "first_operator_completion_diagnostic_command_count": 3,
            "first_operator_completion_diagnostic_required_fields": [
                "torch_rocm_ready",
                "visible_device_count",
                "device_names",
            ],
            "first_operator_completion_diagnostic_required_field_count": 3,
            "first_operator_completion_diagnostic_completion_rule": (
                "torch_rocm_ready=true; visible_device_count>0; device_names nonempty"
            ),
            "first_operator_completion_diagnostic_return_artifacts": [
                "runs/rocm_environment_manifest_current.json",
            ],
            "first_operator_completion_torch_visibility_probe_command": (
                "python3 -c \"import torch; print(torch.cuda.device_count())\""
            ),
        }
    }


def _freshness(ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "product_commercial_readiness_operator_packet_freshness_ready" if ready else "blocked",
            "freshness_ready": ready,
        }
    }


def _ladder(ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "product_commercial_readiness_execution_ladder_ready" if ready else "blocked",
            "ladder_ready": ready,
            "action_count": 5,
            "parallelizable_action_count": 2,
            "parallelizable_action_ids": [
                "transporter_next_slot_exact_evidence",
                "pxr_next_exact_review",
            ],
            "first_parallelizable_action_id": "transporter_next_slot_exact_evidence",
            "first_parallelizable_action_order": 3,
            "first_parallelizable_action_artifact": (
                "runs/transporter_manual_review_intake_template_current.csv"
            ),
            "first_parallelizable_action_next_action": "Acquire exact transporter evidence.",
            "first_parallelizable_action_validation_command": (
                "python3 tools/build_product_scope_breadth_contract.py"
            ),
            "first_parallelizable_action_required_operator_inputs": (
                "target_id;candidate_ligand_id;reference_binding_kcal_mol"
            ),
            "first_parallelizable_action_required_exact_evidence_fields": (
                "target_id;direct_binding_or_claim_safe_kcal_basis;target_match_decision"
            ),
            "first_parallelizable_action_required_claim_guardrails": (
                "functional_surrogate_does_not_authorize_direct_binding_claim"
            ),
            "first_parallelizable_action_expected_evidence_type": (
                "direct_or_claim_safe_binding_kcal"
            ),
            "first_parallelizable_action_required_missing_fields": (
                "replacement_reference_binding_kcal_mol"
            ),
            "first_parallelizable_action_operator_review_artifact": (
                "runs/transporter_manual_review_intake_template_current.csv"
            ),
            "first_parallelizable_action_post_intake_synchronization_targets": (
                "config/ligand_binding_reference_blind_aqp1_v1.csv"
            ),
            "first_parallelizable_action_acceptance_gate_commands": (
                "python3 tools/build_product_scope_breadth_contract.py"
            ),
            "first_parallelizable_action_next_slot_source_modality_guard_ready": True,
            "first_parallelizable_action_next_slot_source_modality": (
                "functional_quantitative_surrogate"
            ),
            "first_parallelizable_action_next_slot_source_modality_claim_safe": False,
            "first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed": False,
            "first_parallelizable_action_next_slot_source_modality_decision": (
                "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
            ),
            "first_parallelizable_action_next_slot_source_modality_guardrails": [
                "functional_quantitative_surrogate_is_review_only",
            ],
            "first_parallelizable_action_next_slot_source_modality_observed_signal": (
                "request_mode=exact_target_pair_quantitative_binder_kcal_required"
            ),
            "first_parallelizable_action_next_slot_source_modality_required_upgrade": (
                "exact target-pair direct/claim-safe binding kcal/mol"
            ),
            "first_parallelizable_action_next_slot_source_modality_triage_artifact": (
                "runs/aqp1_binding_source_modality_triage_current.json"
            ),
            "first_parallelizable_action_next_slot_source_modality_triage_decision": (
                "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
            ),
            "first_parallelizable_action_next_slot_source_modality_direct_experimental_binding_row_count": 0,
            "first_parallelizable_action_next_slot_source_modality_claim_safe_binding_kcal_ready_count": 0,
            "first_parallelizable_action_next_slot_source_modality_computational_binding_energy_row_count": 1,
            "first_parallelizable_action_next_slot_source_modality_best_computational_binding_energy_kcal_mol": "-34.48",
            "first_parallelizable_action_operator_validation_candidate_ready": True,
            "first_parallelizable_action_operator_validation_candidate_status": (
                "operator_validation_required"
            ),
            "first_parallelizable_action_operator_validation_candidate_ligand_external_identifier": (
                "CHEMBL20"
            ),
            "first_parallelizable_action_operator_validation_candidate_reference_binding_kcal_mol": (
                "-5.13"
            ),
            "first_parallelizable_action_operator_validation_candidate_blocker": (
                "data_validity_outside_typical_range_and_assay_origin_unknown"
            ),
            "first_parallelizable_action_operator_validation_candidate_claim_safe_ready": False,
            "first_parallelizable_action_lane_id": "parallel_scope_evidence",
            "first_parallelizable_action_precondition": (
                "Can be completed while ROCm/GPU environment is being prepared."
            ),
            "first_action_id": "production_gpu_execution_environment",
            "first_operator_input_artifact": "runs/rocm_environment_manifest_current.json",
            "first_execution_command": "python3 tools/build_rocm_environment_manifest.py",
            "first_validation_command": "python3 tools/build_rocm_environment_manifest.py",
            "production_ai_return_action_id": "production_ai_return_summary",
            "production_ai_return_action_artifact": (
                "runs/residual_force_trajectory_regeneration_current_summary.json"
            ),
            "production_ai_return_action_next_action": "Return the completed GPU summary JSON.",
            "production_ai_return_action_execution_command": (
                "python3 tools/generate_ligand_trajectory_engine.py --prod-mode"
            ),
            "production_ai_return_action_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "production_ai_return_action_blocked_by_action_id": (
                "production_gpu_execution_environment"
            ),
            "production_ai_return_action_required_operator_inputs": "queue_rows;processed_rows;ok_rows",
            "production_ai_return_action_required_evidence": (
                "queue_rows equals expected_queue_rows; processed_rows>=expected_queue_rows"
            ),
            "production_ai_return_operator_completion_packet_ready": True,
            "production_ai_return_operator_completion_artifact_id": "returned_summary_json",
            "production_ai_return_operator_completion_artifact_path": (
                "runs/residual_force_trajectory_regeneration_current_summary.json"
            ),
            "production_ai_return_operator_completion_required_fields_or_columns": [
                "queue_rows",
                "processed_rows",
                "ok_rows",
            ],
            "production_ai_return_operator_completion_expected_queue_rows": 768,
            "production_ai_return_operator_completion_completion_rule": (
                "queue_rows equals expected_queue_rows; processed_rows>=expected_queue_rows"
            ),
            "production_ai_return_operator_completion_backend_provenance_completion_rule": (
                "prod_mode=true; require_rust_hip=true"
            ),
            "production_ai_return_bundle_required_artifact_count": 4,
            "production_ai_return_bundle_required_artifacts": [
                "runs/residual_force_trajectory_regeneration_current_summary.json",
                "runs/residual_force_trajectory_regeneration_current_manifest.csv",
            ],
            "production_ai_return_bundle_next_artifact_id": "returned_summary_json",
            "production_ai_return_bundle_next_artifact_path": (
                "runs/residual_force_trajectory_regeneration_current_summary.json"
            ),
            "production_ai_return_bundle_next_artifact_failed_check_ids": [
                "actual_summary_returned_complete"
            ],
            "production_ai_return_bundle_manifest_required_columns": [
                "queue_id",
                "operator_verified_npz_exists",
            ],
            "production_ai_return_bundle_post_return_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "production_ai_return_bundle_guardrail": (
                "Returned summary alone does not unlock production AI."
            ),
            "production_ai_registry_promotion_operator_receipt_artifact": (
                "runs/production_ai_registry_promotion_operator_receipt_current.json"
            ),
            "production_ai_registry_promotion_operator_receipt_status": (
                "blocked_production_ai_registry_promotion_operator_receipt"
            ),
            "production_ai_registry_promotion_operator_receipt_ready": False,
            "production_ai_registry_promotion_operator_receipt_present": True,
            "production_ai_registry_promotion_operator_receipt_csv": (
                "config/production_ai_registry_promotion_operator_receipt_current.csv"
            ),
            "production_ai_registry_promotion_operator_receipt_row_count": 1,
            "production_ai_registry_promotion_operator_receipt_blocker_count": 1,
            "production_ai_registry_promotion_operator_receipt_blocked_row_count": 1,
            "production_ai_registry_promotion_operator_receipt_blockers": [
                "blocked_receipt_rows_present"
            ],
            "production_ai_registry_promotion_operator_receipt_first_blocked_artifact_id": (
                "residual_model_registry_guarded_promotion"
            ),
            "production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "production_ai_registry_promotion_operator_receipt_first_blocked_row_blockers": [
                "operator_placeholders_unfilled",
                "default_residual_mode_not_guarded",
            ],
            "production_ai_registry_promotion_operator_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "production_ai_registry_promotion_operator_receipt_approval_token_required": (
                "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
            ),
            "production_ai_registry_promotion_operator_receipt_next_required_step": (
                "Fill the production AI registry promotion receipt."
            ),
            "production_ai_registry_promotion_operator_receipt_registry_artifact": (
                "runs/residual_model_registry_current.json"
            ),
            "production_ai_registry_promotion_operator_receipt_checkpoint_readiness_artifact": (
                "runs/product_production_ai_checkpoint_readiness_current.json"
            ),
            "production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode": (
                "shadow"
            ),
            "production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count": 0,
            "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_currently_satisfied": False,
            "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_missing_gate_ids": [
                "production_promotion_allowed",
                "default_residual_mode_guarded",
            ],
            "production_ai_registry_promotion_operator_receipt_registry_edited_by_this_tool": False,
            "production_ai_registry_promotion_operator_receipt_checkpoint_created_by_this_tool": False,
            "production_ai_registry_promotion_priority_artifact": (
                "runs/production_ai_registry_promotion_priority_packet_current.json"
            ),
            "production_ai_registry_promotion_priority_status": (
                "blocked_production_ai_registry_promotion_priority_packet"
            ),
            "production_ai_registry_promotion_priority_packet_ready": True,
            "production_ai_registry_promotion_priority_registry_promotion_ready": False,
            "production_ai_registry_promotion_priority_operator_input_required_count": 4,
            "production_ai_registry_promotion_priority_blocked_priority_item_count": 4,
            "production_ai_registry_promotion_priority_missing_gate_count": 4,
            "production_ai_registry_promotion_priority_missing_gate_ids": [
                "trained_model_checkpoint_count_positive",
                "default_residual_mode_guarded",
            ],
            "production_ai_registry_promotion_priority_operator_receipt_csv": (
                "config/production_ai_registry_promotion_operator_receipt_current.csv"
            ),
            "production_ai_registry_promotion_priority_approval_token_required": (
                "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
            ),
            "production_ai_registry_promotion_priority_observed_registry_default_residual_mode": (
                "shadow"
            ),
            "production_ai_registry_promotion_priority_observed_registry_production_promotion_allowed": False,
            "production_ai_registry_promotion_priority_observed_registry_customer_facing_mutation_flags_ready": False,
            "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count": 0,
            "production_ai_registry_promotion_priority_top_gate_id": (
                "trained_model_checkpoint_count_positive"
            ),
            "production_ai_registry_promotion_priority_top_priority_bucket": (
                "trained_checkpoint_registration_required"
            ),
            "production_ai_registry_promotion_priority_top_required_input": (
                "Register a trained production residual checkpoint."
            ),
            "production_ai_registry_promotion_priority_top_acceptance_artifact": (
                "runs/residual_model_registry_current.json"
            ),
            "production_ai_registry_promotion_priority_top_verification_command": (
                "python3 tools/build_residual_model_registry.py"
            ),
            "production_ai_registry_promotion_priority_top_next_operator_step": (
                "Register checkpoint, then rerun registry readiness."
            ),
            "production_ai_registry_promotion_priority_model_promoted": False,
            "production_ai_registry_promotion_priority_customer_facing_mutation_enabled": False,
            "production_ai_registry_promotion_priority_external_state_mutated": False,
            "production_ai_registry_promotion_operator_field_worksheet_artifact": (
                "runs/production_ai_registry_promotion_operator_field_worksheet_current.json"
            ),
            "production_ai_registry_promotion_operator_field_worksheet_status": (
                "production_ai_registry_promotion_operator_field_worksheet_ready"
            ),
            "production_ai_registry_promotion_operator_field_worksheet_ready": True,
            "production_ai_registry_promotion_operator_field_worksheet_operator_fill_complete": False,
            "production_ai_registry_promotion_operator_field_worksheet_field_row_count": 20,
            "production_ai_registry_promotion_operator_field_worksheet_required_field_count": 19,
            "production_ai_registry_promotion_operator_field_worksheet_pending_field_count": 13,
            "production_ai_registry_promotion_operator_field_worksheet_diagnostic_required_field_count": 6,
            "production_ai_registry_promotion_operator_field_worksheet_diagnostic_pending_field_count": 6,
            "production_ai_registry_promotion_operator_field_worksheet_pending_field_names": [
                "operator_decision",
                "default_residual_mode",
            ],
            "production_ai_registry_promotion_operator_field_worksheet_top_gate_id": (
                "trained_model_checkpoint_count_positive"
            ),
            "production_ai_registry_promotion_operator_field_worksheet_top_required_input": (
                "Register a trained production residual checkpoint."
            ),
            "production_ai_registry_promotion_operator_field_worksheet_approval_token_required": (
                "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
            ),
            "production_ai_registry_promotion_operator_field_worksheet_observed_registry_default_residual_mode": (
                "shadow"
            ),
            "production_ai_registry_promotion_operator_field_worksheet_observed_registry_trained_model_checkpoint_count": 0,
            "production_ai_registry_promotion_operator_field_worksheet_model_promoted": False,
            "production_ai_registry_promotion_operator_field_worksheet_customer_facing_mutation_enabled": False,
            "production_ai_registry_promotion_operator_field_worksheet_external_state_mutated": False,
            "production_ai_registry_promotion_operator_field_worksheet_next_required_step": (
                "Fill every operator_fill_pending field."
            ),
            "first_operator_completion_worker_runtime_receipt_contract_ready": True,
            "first_operator_completion_worker_runtime_receipt_contract": {
                "manifest_ready": True,
                "torch_rocm_ready": True,
                "amd_gpu_detected": True,
                "visible_device_count": 1,
            },
            "first_operator_completion_worker_runtime_receipt_required_fields_or_columns": [
                "manifest_ready",
                "torch_rocm_ready",
                "amd_gpu_detected",
                "visible_device_count",
                "backend_counts",
            ],
            "first_operator_completion_worker_runtime_receipt_required_field_count": 5,
            "first_operator_completion_worker_runtime_receipt_completion_rule": (
                "manifest_ready=true; torch_rocm_ready=true; visible_device_count>0"
            ),
            "first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id": (
                "gpu_return_acceptance"
            ),
            "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact": (
                "runs/residual_force_gpu_worker_return_receipt_current.json"
            ),
            "first_operator_completion_worker_runtime_receipt_post_environment_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "first_operator_completion_worker_runtime_receipt_full_regeneration_command": (
                "python3 tools/generate_ligand_trajectory_engine.py --prod-mode"
            ),
            "first_operator_completion_worker_runtime_receipt_guardrails": [
                "cpu_fallback_does_not_satisfy_production_inference",
            ],
            "first_operator_completion_diagnostic_commands": [
                "python3 tools/build_rocm_environment_manifest.py",
                "rocminfo",
                "python3 -c \"import torch; print(torch.cuda.device_count())\"",
            ],
            "first_operator_completion_diagnostic_command_count": 3,
            "first_operator_completion_diagnostic_required_fields": [
                "torch_rocm_ready",
                "visible_device_count",
                "device_names",
            ],
            "first_operator_completion_diagnostic_required_field_count": 3,
            "first_operator_completion_diagnostic_completion_rule": (
                "torch_rocm_ready=true; visible_device_count>0; device_names nonempty"
            ),
            "first_operator_completion_diagnostic_return_artifacts": [
                "runs/rocm_environment_manifest_current.json",
            ],
            "first_operator_completion_torch_visibility_probe_command": (
                "python3 -c \"import torch; print(torch.cuda.device_count())\""
            ),
            "next_required_step": "Expose an AMD ROCm/HIP device to PyTorch.",
        },
        "rows": [
            {
                "execution_order": 1,
                "action_id": "production_gpu_execution_environment",
                "operator_input_artifact": "runs/rocm_environment_manifest_current.json",
                "execution_command": "python3 tools/build_rocm_environment_manifest.py",
                "validation_command": "python3 tools/build_rocm_environment_manifest.py",
            }
        ],
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_product_commercial_readiness_handoff_bundle_ready_when_all_artifacts_ready(tmp_path: Path) -> None:
    operator_path = tmp_path / "operator.json"
    freshness_path = tmp_path / "freshness.json"
    ladder_path = tmp_path / "ladder.json"
    _write_json(operator_path, _operator_packet())
    _write_json(freshness_path, _freshness())
    _write_json(ladder_path, _ladder())

    payload = mod.build_product_commercial_readiness_handoff_bundle(
        operator_packet=_operator_packet(),
        freshness_packet=_freshness(),
        execution_ladder_packet=_ladder(),
        operator_packet_path=str(operator_path),
        freshness_path=str(freshness_path),
        execution_ladder_path=str(ladder_path),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_commercial_readiness_handoff_bundle_ready"
    assert summary["handoff_bundle_ready"] is True
    assert summary["goal_complete"] is False
    assert summary["engine_refinement_claim_promotion_ready"] is False
    assert summary["engine_refinement_claim_promotion_blocker_count"] == 6
    assert summary["engine_refinement_claim_promotion_action_row_count"] == 6
    assert "public_benchmark_gate_not_ready" in summary["engine_refinement_claim_promotion_blockers"]
    assert (
        summary["engine_refinement_claim_promotion_action_board_csv"]
        == "runs/engine_refinement_claim_promotion_action_board_current.csv"
    )
    assert summary["engine_refinement_claim_evidence_receipt_ready"] is False
    assert summary["engine_refinement_claim_evidence_receipt_status"] == (
        "blocked_engine_refinement_claim_evidence_receipt"
    )
    assert summary["engine_refinement_claim_evidence_receipt_blocked_row_count"] == 6
    assert (
        summary["engine_refinement_claim_evidence_receipt_artifact"]
        == "runs/engine_refinement_claim_evidence_receipt_current.json"
    )
    assert summary["engine_refinement_claim_evidence_receipt_csv"] == (
        "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
    )
    assert summary["engine_refinement_claim_evidence_receipt_first_blocked_blocker_id"] == (
        "public_benchmark_gate_not_ready"
    )
    assert summary[
        "engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact"
    ] == "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
    assert summary[
        "engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields"
    ] == ["claim_grade_public_benchmark_ready"]
    assert summary["engine_refinement_claim_evidence_receipt_most_common_row_blocker"] == (
        "operator_placeholders_unfilled"
    )
    assert summary["engine_refinement_claim_evidence_operator_field_worksheet_status"] == (
        "engine_refinement_claim_evidence_operator_field_worksheet_ready"
    )
    assert summary["engine_refinement_claim_evidence_operator_field_worksheet_ready"] is True
    assert (
        summary["engine_refinement_claim_evidence_operator_field_worksheet_operator_fill_complete"]
        is False
    )
    assert summary["engine_refinement_claim_evidence_operator_field_worksheet_field_row_count"] == 144
    assert summary["engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count"] == 108
    assert (
        summary[
            "engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count"
        ]
        == 72
    )
    assert summary["engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id"] == (
        "public_benchmark_gate_not_ready"
    )
    assert (
        summary["engine_refinement_claim_evidence_operator_field_worksheet_top_priority_bucket"]
        == "public_benchmark_work_order_apply_required"
    )
    assert (
        summary[
            "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_apply_blocked_row_count"
        ]
        == 8
    )
    assert summary["product_scope_breadth_evidence_receipt_ready"] is False
    assert summary["product_scope_breadth_evidence_receipt_status"] == (
        "blocked_product_scope_breadth_evidence_receipt"
    )
    assert summary["product_scope_breadth_evidence_receipt_blocker_count"] == 1
    assert summary["product_scope_breadth_evidence_receipt_blocked_row_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_required_scope_blocker_count"] == 6
    assert summary["product_scope_breadth_evidence_receipt_artifact"] == (
        "runs/product_scope_breadth_evidence_receipt_current.json"
    )
    assert summary["product_scope_breadth_evidence_receipt_csv"] == (
        "config/product_scope_breadth_evidence_receipt_current.csv"
    )
    assert summary["product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id"] == (
        "direct_binding_evidence_missing"
    )
    assert summary[
        "product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact"
    ] == "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
    assert summary[
        "product_scope_breadth_evidence_receipt_first_blocked_missing_true_fields"
    ] == ["transporter_direct_binding_evidence_ready"]
    assert summary["product_scope_breadth_evidence_receipt_most_common_row_blocker"] == (
        "operator_placeholders_unfilled"
    )
    assert summary["primary_full_commercial_release_blocker_id"] == (
        "R8_full_scope_claim_closure"
    )
    assert summary["primary_full_commercial_release_blocker_receipt_csv"] == (
        "config/product_scope_breadth_evidence_receipt_current.csv"
    )
    assert summary["primary_full_commercial_release_blocker_approval_token_required"] == (
        "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
    )
    assert summary["product_scope_next_operator_completion_item_id"] == "AQP1.core_binder_01"
    assert summary["product_scope_next_operator_completion_required_evidence_type"] == (
        "exact_transporter_target_pair_quantitative_binder_kcal"
    )
    assert (
        summary["product_scope_next_operator_completion_transporter_best_evidence_value"]
        == "174000.0"
    )
    assert summary[
        "product_scope_next_operator_completion_transporter_best_evidence_document_id"
    ] == "CHEMBL6182835"
    assert summary["product_scope_transporter_p0_return_bundle_required_artifact_count"] == 5
    assert "config/ligand_binding_reference_blind_aqp1_v1.csv" in summary[
        "product_scope_transporter_p0_return_bundle_required_artifacts"
    ]
    assert summary["product_scope_transporter_p0_return_bundle_next_artifact_path"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert summary["product_goal_scope_transporter_p0_operator_validation_candidate_status"] == (
        "operator_validation_required"
    )
    assert summary["artifact_count"] == 3
    assert summary["ready_artifact_count"] == 3
    assert summary["blocked_artifact_count"] == 0
    assert summary["operator_packet_ready"] is True
    assert summary["source_fingerprint_ready"] is True
    assert summary["freshness_ready"] is True
    assert summary["execution_ladder_ready"] is True
    assert summary["operator_parallelizable_action_count"] == 2
    assert summary["operator_parallelizable_action_ids"] == [
        "transporter_next_slot_exact_evidence",
        "pxr_next_exact_review",
    ]
    assert summary["ladder_parallelizable_action_count"] == 2
    assert summary["first_parallelizable_action_id"] == "transporter_next_slot_exact_evidence"
    assert summary["first_parallelizable_action_lane_id"] == "parallel_scope_evidence"
    assert "ROCm/GPU environment" in summary["first_parallelizable_action_precondition"]
    assert "reference_binding_kcal_mol" in summary[
        "first_parallelizable_action_required_operator_inputs"
    ]
    assert "target_match_decision" in summary[
        "first_parallelizable_action_required_exact_evidence_fields"
    ]
    assert "functional_surrogate_does_not_authorize_direct_binding_claim" in summary[
        "first_parallelizable_action_required_claim_guardrails"
    ]
    assert summary["first_parallelizable_action_expected_evidence_type"] == (
        "direct_or_claim_safe_binding_kcal"
    )
    assert "replacement_reference_binding_kcal_mol" in summary[
        "first_parallelizable_action_required_missing_fields"
    ]
    assert summary["first_parallelizable_action_operator_review_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert "ligand_binding_reference_blind_aqp1" in summary[
        "first_parallelizable_action_post_intake_synchronization_targets"
    ]
    assert "build_product_scope_breadth_contract.py" in summary[
        "first_parallelizable_action_acceptance_gate_commands"
    ]
    assert summary[
        "first_parallelizable_action_next_slot_source_modality_guard_ready"
    ] is True
    assert summary["first_parallelizable_action_next_slot_source_modality"] == (
        "functional_quantitative_surrogate"
    )
    assert summary[
        "first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed"
    ] is False
    assert summary["first_parallelizable_action_next_slot_source_modality_decision"] == (
        "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
    )
    assert summary[
        "first_parallelizable_action_next_slot_source_modality_triage_artifact"
    ] == "runs/aqp1_binding_source_modality_triage_current.json"
    assert summary[
        "first_parallelizable_action_next_slot_source_modality_triage_decision"
    ] == "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
    assert summary[
        "first_parallelizable_action_next_slot_source_modality_computational_binding_energy_row_count"
    ] == 1
    assert summary[
        "first_parallelizable_action_next_slot_source_modality_best_computational_binding_energy_kcal_mol"
    ] == "-34.48"
    assert summary["first_parallelizable_action_operator_validation_candidate_ready"] is True
    assert summary[
        "first_parallelizable_action_operator_validation_candidate_status"
    ] == "operator_validation_required"
    assert summary[
        "first_parallelizable_action_operator_validation_candidate_ligand_external_identifier"
    ] == "CHEMBL20"
    assert summary[
        "first_parallelizable_action_operator_validation_candidate_reference_binding_kcal_mol"
    ] == "-5.13"
    assert summary[
        "first_parallelizable_action_operator_validation_candidate_blocker"
    ] == "data_validity_outside_typical_range_and_assay_origin_unknown"
    assert (
        summary["first_parallelizable_action_operator_validation_candidate_claim_safe_ready"]
        is False
    )
    assert summary["first_parallelizable_action_direct_binding_procurement_packet_ready"] is True
    assert summary["first_parallelizable_action_direct_binding_procurement_packet_artifact"] == (
        "runs/aqp1_direct_binding_procurement_packet_current.json"
    )
    assert summary[
        "first_parallelizable_action_direct_binding_procurement_first_required_external_action_id"
    ] == "procure_aqp1_bacopaside_ii_direct_binding_measurement"
    assert "standard_type in Kd,Ki" in summary[
        "first_parallelizable_action_direct_binding_procurement_minimum_acceptance_rule"
    ]
    assert summary["first_action_id"] == "production_gpu_execution_environment"
    assert summary["first_operator_input_artifact"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert summary["first_execution_command"] == "python3 tools/build_rocm_environment_manifest.py"
    assert summary["first_operator_completion_worker_runtime_receipt_contract_ready"] is True
    assert "backend_counts" in summary[
        "first_operator_completion_worker_runtime_receipt_required_fields_or_columns"
    ]
    assert summary[
        "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact"
    ] == "runs/residual_force_gpu_worker_return_receipt_current.json"
    assert "build_residual_force_gpu_worker_return_receipt.py" in summary[
        "first_operator_completion_worker_runtime_receipt_post_environment_validation_command"
    ]
    assert summary["first_operator_completion_diagnostic_command_count"] == 3
    assert "rocminfo" in summary["first_operator_completion_diagnostic_commands"]
    assert "visible_device_count>0" in summary[
        "first_operator_completion_diagnostic_completion_rule"
    ]
    assert summary["first_operator_completion_torch_visibility_probe_command"].startswith(
        "python3 -c"
    )
    assert summary["production_ai_return_action_id"] == "production_ai_return_summary"
    assert summary["production_ai_return_action_blocked_by_action_id"] == (
        "production_gpu_execution_environment"
    )
    assert "queue_rows" in summary["production_ai_return_action_required_operator_inputs"]
    assert summary["production_ai_return_operator_completion_packet_ready"] is True
    assert summary["production_ai_return_operator_completion_artifact_id"] == (
        "returned_summary_json"
    )
    assert summary["production_ai_return_operator_completion_expected_queue_rows"] == 768
    assert "require_rust_hip" in summary[
        "production_ai_return_operator_completion_backend_provenance_completion_rule"
    ]
    assert summary["production_ai_return_bundle_required_artifact_count"] == 4
    assert any(
        "residual_force_trajectory_regeneration_current_manifest.csv" in artifact
        for artifact in summary["production_ai_return_bundle_required_artifacts"]
    )
    assert summary["production_ai_registry_promotion_operator_receipt_status"] == (
        "blocked_production_ai_registry_promotion_operator_receipt"
    )
    assert summary["production_ai_registry_promotion_operator_receipt_ready"] is False
    assert summary["production_ai_registry_promotion_operator_receipt_present"] is True
    assert summary["production_ai_registry_promotion_operator_receipt_csv"] == (
        "config/production_ai_registry_promotion_operator_receipt_current.csv"
    )
    assert summary[
        "production_ai_registry_promotion_operator_receipt_approval_token_required"
    ] == "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
    assert summary[
        "production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker"
    ] == "operator_placeholders_unfilled"
    assert summary[
        "production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode"
    ] == "shadow"
    assert summary["production_ai_registry_promotion_priority_status"] == (
        "blocked_production_ai_registry_promotion_priority_packet"
    )
    assert summary["production_ai_registry_promotion_priority_packet_ready"] is True
    assert summary["production_ai_registry_promotion_priority_registry_promotion_ready"] is False
    assert summary["production_ai_registry_promotion_priority_operator_input_required_count"] == 4
    assert summary["production_ai_registry_promotion_priority_operator_receipt_csv"] == (
        "config/production_ai_registry_promotion_operator_receipt_current.csv"
    )
    assert summary[
        "production_ai_registry_promotion_priority_approval_token_required"
    ] == "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
    assert summary[
        "production_ai_registry_promotion_priority_observed_registry_default_residual_mode"
    ] == "shadow"
    assert (
        summary[
            "production_ai_registry_promotion_priority_observed_registry_production_promotion_allowed"
        ]
        is False
    )
    assert (
        summary[
            "production_ai_registry_promotion_priority_observed_registry_customer_facing_mutation_flags_ready"
        ]
        is False
    )
    assert summary[
        "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count"
    ] == 0
    assert summary["production_ai_registry_promotion_priority_top_gate_id"] == (
        "trained_model_checkpoint_count_positive"
    )
    assert summary["production_ai_registry_promotion_priority_top_priority_bucket"] == (
        "trained_checkpoint_registration_required"
    )
    assert summary["production_ai_registry_promotion_priority_model_promoted"] is False
    assert summary["production_ai_registry_promotion_priority_external_state_mutated"] is False
    assert summary["production_ai_registry_promotion_operator_field_worksheet_status"] == (
        "production_ai_registry_promotion_operator_field_worksheet_ready"
    )
    assert summary["production_ai_registry_promotion_operator_field_worksheet_ready"] is True
    assert (
        summary[
            "production_ai_registry_promotion_operator_field_worksheet_operator_fill_complete"
        ]
        is False
    )
    assert summary[
        "production_ai_registry_promotion_operator_field_worksheet_pending_field_count"
    ] == 13
    assert summary[
        "production_ai_registry_promotion_operator_field_worksheet_diagnostic_pending_field_count"
    ] == 6
    assert summary[
        "production_ai_registry_promotion_operator_field_worksheet_top_gate_id"
    ] == "trained_model_checkpoint_count_positive"
    assert summary[
        "production_ai_registry_promotion_operator_field_worksheet_external_state_mutated"
    ] is False
    assert summary["delta_force_closure_acceptance_packet_ready"] is True
    assert summary["delta_force_closure_ready"] is False
    assert summary["delta_force_closure_first_blocked_output_field"] == "delta_force"
    assert summary["delta_force_closure_failed_stage_count"] == 9
    assert summary["delta_force_closure_next_stage_id"] == "gpu_worker_return_receipt"
    assert summary["delta_force_closure_next_stage_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert "queue_rows" in summary["delta_force_closure_return_summary_required_fields"]
    assert summary["scope_closure_acceptance_packet_ready"] is True
    assert summary["scope_closure_ready"] is False
    assert summary["scope_closure_stage_count"] == 5
    assert summary["scope_closure_blocked_stage_count"] == 4
    assert summary["scope_closure_next_stage_id"] == "transporter_claim_acceptance"
    assert summary["scope_closure_first_blocked_evidence_row_id"] == "AQP1.core_binder_01"
    assert summary["scope_closure_first_blocked_target_id"] == "AQP1"
    assert summary["scope_closure_first_blocked_required_missing_fields"] == (
        "replacement_reference_binding_kcal_mol"
    )
    assert summary["scope_closure_transporter_unresolved_slot_count"] == 11
    assert summary["scope_closure_general_platform_claim_allowed"] is False
    assert summary["artifact_reference_contract_ready"] is True
    assert summary["artifact_reference_count"] >= 8
    assert summary["local_required_artifact_reference_count"] >= 6
    assert summary["local_missing_artifact_reference_count"] == 0
    assert summary["local_missing_artifact_references"] == []
    assert summary["operator_return_artifact_reference_count"] >= 2
    assert summary["operator_return_pending_artifact_reference_count"] >= 0
    assert summary["operator_return_pending_artifact_reference_count"] <= summary[
        "operator_return_artifact_reference_count"
    ]
    assert any(
        row["reference_role"] == "operator_return_artifact"
        and row["required_now"] is False
        and row["expected_from_operator_return"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "first_operator_completion_worker_runtime_receipt"
        and row["artifact_path"] == "runs/residual_force_gpu_worker_return_receipt_current.json"
        and row["expected_from_operator_return"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "first_parallelizable_action_source_modality_triage_artifact"
        and row["artifact_path"] == "runs/aqp1_binding_source_modality_triage_current.json"
        and row["reference_role"] == "local_parallel_source_modality_triage"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "first_parallelizable_action_direct_binding_procurement_packet"
        and row["artifact_path"] == "runs/aqp1_direct_binding_procurement_packet_current.json"
        and row["reference_role"] == "local_parallel_direct_binding_procurement_packet"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert summary[
        "product_scope_transporter_p0_external_operator_fill_guide_ready"
    ] is True
    assert summary[
        "product_scope_transporter_p0_external_operator_worksheet_pending_field_count"
    ] == 19
    assert summary[
        "product_scope_transporter_p0_external_operator_staging_apply_live_apply_allowed"
    ] is False
    assert any(
        row["artifact_id"] == "product_scope_transporter_p0_external_operator_fill_guide"
        and row["artifact_path"]
        == "runs/aqp1_direct_binding_external_evidence_operator_fill_guide_current.json"
        and row["reference_role"]
        == "local_scope_transporter_p0_external_operator_fill_guide"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "product_scope_transporter_p0_external_operator_worksheet"
        and row["artifact_path"]
        == "runs/aqp1_direct_binding_external_evidence_operator_worksheet_current.json"
        and row["reference_role"]
        == "local_scope_transporter_p0_external_operator_worksheet"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "product_scope_transporter_p0_external_operator_staging_apply"
        and row["artifact_path"]
        == "runs/aqp1_direct_binding_external_evidence_operator_staging_apply_current.json"
        and row["reference_role"]
        == "local_scope_transporter_p0_external_operator_staging_apply"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "production_ai_registry_promotion_operator_field_worksheet"
        and row["artifact_path"]
        == "runs/production_ai_registry_promotion_operator_field_worksheet_current.json"
        and row["reference_role"]
        == "local_production_ai_registry_promotion_field_worksheet"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "gpu_worker_execution_runbook"
        and row["artifact_path"] == "runs/residual_force_gpu_worker_execution_runbook_current.json"
        and row["reference_role"] == "local_gpu_worker_execution_runbook"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "gpu_worker_execution_runbook_script"
        and row["artifact_path"] == "runs/residual_force_gpu_worker_execution_runbook_current.sh"
        and row["reference_role"] == "local_gpu_worker_execution_runbook_script"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "gpu_worker_return_bundle_packager_script"
        and row["artifact_path"] == "runs/residual_force_gpu_worker_return_bundle_packager_current.sh"
        and row["reference_role"] == "local_gpu_worker_return_bundle_packager_script"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "product_full_commercial_blocker_evidence_matrix"
        and row["artifact_path"] == "runs/product_full_commercial_blocker_evidence_matrix_current.json"
        and row["reference_role"] == "local_full_commercial_blocker_evidence_matrix"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "delta_force_closure_acceptance_packet"
        and row["artifact_path"] == "runs/residual_delta_force_closure_acceptance_packet_current.json"
        and row["reference_role"] == "local_acceptance_evidence"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "scope_closure_acceptance_packet"
        and row["artifact_path"] == "runs/product_scope_closure_acceptance_packet_current.json"
        and row["reference_role"] == "local_acceptance_evidence"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "engine_refinement_claim_promotion_action_board"
        and row["artifact_path"] == "runs/engine_refinement_claim_promotion_action_board_current.csv"
        and row["reference_role"] == "local_engine_refinement_claim_action_board"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "engine_refinement_claim_evidence_receipt"
        and row["artifact_path"] == "runs/engine_refinement_claim_evidence_receipt_current.json"
        and row["reference_role"] == "local_engine_refinement_claim_receipt"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "engine_refinement_claim_evidence_receipt_csv"
        and row["artifact_path"] == "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
        and row["reference_role"] == "local_engine_refinement_claim_receipt_template"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "engine_refinement_claim_evidence_operator_field_worksheet"
        and row["artifact_path"]
        == "runs/engine_refinement_claim_evidence_operator_field_worksheet_current.json"
        and row["reference_role"] == "local_engine_refinement_claim_field_worksheet"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "product_scope_breadth_evidence_receipt"
        and row["artifact_path"] == "runs/product_scope_breadth_evidence_receipt_current.json"
        and row["reference_role"] == "local_scope_breadth_receipt"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "product_scope_breadth_evidence_receipt_csv"
        and row["artifact_path"] == "config/product_scope_breadth_evidence_receipt_current.csv"
        and row["reference_role"] == "local_scope_breadth_receipt_template"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "product_scope_transporter_p0_return_bundle_required_artifact_2"
        and row["artifact_path"] == "config/ligand_binding_reference_blind_aqp1_v1.csv"
        and row["reference_role"] == "local_scope_transporter_p0_return_bundle_artifact"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "production_ai_registry_promotion_operator_receipt"
        and row["artifact_path"] == "runs/production_ai_registry_promotion_operator_receipt_current.json"
        and row["reference_role"] == "local_production_ai_registry_promotion_receipt"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "production_ai_registry_promotion_priority_packet"
        and row["artifact_path"] == "runs/production_ai_registry_promotion_priority_packet_current.json"
        and row["reference_role"] == "local_production_ai_registry_promotion_priority"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert any(
        row["artifact_id"] == "production_ai_registry_promotion_operator_receipt_csv"
        and row["artifact_path"] == "config/production_ai_registry_promotion_operator_receipt_current.csv"
        and row["reference_role"] == "local_production_ai_registry_promotion_receipt_template"
        and row["required_now"] is True
        for row in summary["artifact_reference_manifest"]
    )
    assert "actual_summary_returned_complete" in summary[
        "production_ai_return_bundle_next_artifact_failed_check_ids"
    ]
    assert "operator_verified_npz_exists" in summary[
        "production_ai_return_bundle_manifest_required_columns"
    ]
    assert "summary alone does not unlock" in summary["production_ai_return_bundle_guardrail"]
    assert len(payload["rows"]) == 3
    assert all(len(row["sha256"]) == 64 for row in payload["rows"])
    assert payload["summary"]["execution_enabled"] is False
    assert payload["summary"]["checkpoint_promoted"] is False


def test_product_commercial_readiness_handoff_bundle_blocks_when_freshness_blocked(tmp_path: Path) -> None:
    operator_path = tmp_path / "operator.json"
    freshness_path = tmp_path / "freshness.json"
    ladder_path = tmp_path / "ladder.json"
    _write_json(operator_path, _operator_packet())
    _write_json(freshness_path, _freshness(False))
    _write_json(ladder_path, _ladder())

    payload = mod.build_product_commercial_readiness_handoff_bundle(
        operator_packet=_operator_packet(),
        freshness_packet=_freshness(False),
        execution_ladder_packet=_ladder(),
        operator_packet_path=str(operator_path),
        freshness_path=str(freshness_path),
        execution_ladder_path=str(ladder_path),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_commercial_readiness_handoff_bundle"
    assert summary["handoff_bundle_ready"] is False
    assert summary["blocked_artifact_ids"] == ["operator_packet_freshness"]
    assert payload["blockers"][0]["artifact_id"] == "operator_packet_freshness"


def test_product_commercial_readiness_handoff_bundle_tool_writes_outputs(tmp_path: Path) -> None:
    operator_path = tmp_path / "operator.json"
    freshness_path = tmp_path / "freshness.json"
    ladder_path = tmp_path / "ladder.json"
    out_json = tmp_path / "bundle.json"
    out_csv = tmp_path / "bundle.csv"
    out_md = tmp_path / "bundle.md"
    _write_json(operator_path, _operator_packet())
    _write_json(freshness_path, _freshness())
    _write_json(ladder_path, _ladder())

    mod.main(
        [
            "--operator-packet-json",
            str(operator_path),
            "--freshness-json",
            str(freshness_path),
            "--execution-ladder-json",
            str(ladder_path),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["handoff_bundle_ready"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("artifact_id,artifact_path,")
    md_text = out_md.read_text(encoding="utf-8")
    assert "Product Commercial Readiness Handoff Bundle" in md_text
    assert "operator_packet_freshness" in md_text
    assert "product_scope_breadth_evidence_receipt_current.json" in md_text
    assert "Artifact References" in md_text
