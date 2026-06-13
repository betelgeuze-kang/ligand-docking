from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_commercial_readiness_operator_packet as mod


def _goal_audit() -> dict:
    return {
        "summary": {
            "goal_complete": False,
            "engine_refinement_claim_promotion_ready": False,
            "engine_refinement_claim_promotion_blocker_count": 6,
            "engine_refinement_claim_promotion_action_row_count": 6,
            "engine_refinement_claim_promotion_blockers": [
                "public_benchmark_gate_not_ready",
                "parameter_calibration_claim_not_ready",
                "metal_cofactor_parameterization_not_ready",
                "charged_residue_protonation_and_charge_calibration_not_ready",
                "solvent_fep_public_pair_calibration_not_ready",
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
            "primary_release_blocker_requirement_id": "R8_full_scope_claim_closure",
            "primary_release_blocker_tier": "full_commercial_scope",
            "primary_release_blocker": "full_scope_claim_closure_not_ready",
            "primary_release_blocker_next_command": (
                "python3 tools/build_transporter_manual_review_intake_template.py"
            ),
            "product_scope_breadth_evidence_receipt_approval_token_required": (
                "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
            ),
            "product_scope_breadth_evidence_receipt_next_required_step": (
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
            "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet": {
                "slot_id": "AQP1.core_binder_01"
            },
            "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": (
                "runs/transporter_manual_review_intake_template_current.csv"
            ),
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count": 5,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts": [
                "runs/transporter_manual_review_intake_template_current.csv",
                "config/ligand_binding_reference_blind_aqp1_v1.csv",
                "config/ligand_eval_splits_blind_aqp1_v1.csv",
                "runs/transporter_binder_promotion_gate_current.json",
                "runs/product_scope_breadth_contract_current.json",
            ],
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count": 5,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id": (
                "operator_review_row"
            ),
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path": (
                "runs/transporter_manual_review_intake_template_current.csv"
            ),
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
            "product_ai_architecture_open_gap_ids": [
                "production_ai_inference_checkpoint",
                "scope_breadth_expansion",
            ],
            "commercial_readiness_next_action_matrix": [
                {
                    "action_id": "production_gpu_execution_environment",
                    "status": "blocked",
                    "gap_id": "production_ai_inference_checkpoint",
                    "release_blocker": True,
                    "artifact": "runs/rocm_environment_manifest_current.json",
                    "required_operator_inputs": [
                        "manifest_ready",
                        "rocm_stack_detected",
                        "torch_rocm_ready",
                        "amd_gpu_detected",
                        "visible_device_count",
                    ],
                    "operator_completion_packet_ready": True,
                    "operator_completion_packet": {
                        "artifact_id": "rocm_environment_manifest_json",
                        "artifact_path": "runs/rocm_environment_manifest_current.json",
                        "required_fields_or_columns": [
                            "manifest_ready",
                            "rocm_stack_detected",
                            "torch_rocm_ready",
                            "amd_gpu_detected",
                            "visible_device_count",
                        ],
                        "validation_command": "python3 tools/build_rocm_environment_manifest.py",
                        "next_action": "Expose an AMD ROCm/HIP device to PyTorch.",
                        "worker_runtime_receipt_contract": {
                            "manifest_ready": True,
                            "torch_rocm_ready": True,
                            "amd_gpu_detected": True,
                            "visible_device_count": 1,
                        },
                        "worker_runtime_receipt_required_fields_or_columns": [
                            "manifest_ready",
                            "torch_rocm_ready",
                            "amd_gpu_detected",
                            "visible_device_count",
                            "backend_counts",
                        ],
                        "worker_runtime_receipt_required_field_count": 5,
                        "worker_runtime_receipt_completion_rule": (
                            "manifest_ready=true; torch_rocm_ready=true; visible_device_count>0"
                        ),
                        "post_environment_next_stage_id": "gpu_return_acceptance",
                        "post_environment_next_artifact": (
                            "runs/residual_force_gpu_worker_return_receipt_current.json"
                        ),
                        "post_environment_validation_command": (
                            "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                        ),
                        "full_regeneration_command": (
                            "python3 tools/generate_ligand_trajectory_engine.py --prod-mode"
                        ),
                        "worker_runtime_receipt_guardrails": [
                            "cpu_fallback_does_not_satisfy_production_inference",
                            "registry_promotion_blocked_until_gpu_receipt_and_sidecar_ready",
                        ],
                        "diagnostic_commands": [
                            "python3 tools/build_rocm_environment_manifest.py",
                            "rocminfo",
                            "python3 -c \"import torch; print(torch.cuda.device_count())\"",
                        ],
                        "diagnostic_command_count": 3,
                        "diagnostic_required_fields": [
                            "torch_rocm_ready",
                            "visible_device_count",
                            "device_names",
                        ],
                        "diagnostic_required_field_count": 3,
                        "diagnostic_completion_rule": (
                            "torch_rocm_ready=true; visible_device_count>0; device_names nonempty"
                        ),
                        "diagnostic_return_artifacts": [
                            "runs/rocm_environment_manifest_current.json",
                        ],
                        "torch_visibility_probe_command": (
                            "python3 -c \"import torch; print(torch.cuda.device_count())\""
                        ),
                    },
                    "next_action": "Expose an AMD ROCm/HIP device to PyTorch.",
                    "execution_command": "python3 tools/build_rocm_environment_manifest.py",
                    "validation_command": "python3 tools/build_rocm_environment_manifest.py",
                    "unlock_claim": "production_ai_full_gpu_regeneration_authority",
                    "workstream_lane_id": "primary_gpu_environment",
                    "parallelizable_with_primary_blocker": False,
                    "parallel_lane_priority": 0,
                    "next_after_actionable_blocker_stage_id": "gpu_return_acceptance",
                    "next_after_actionable_blocker_artifact": (
                        "runs/residual_force_gpu_worker_return_receipt_current.json"
                    ),
                    "next_after_actionable_blocker_validation_command": (
                        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                    ),
                    "next_after_actionable_blocker_required_checks": [
                        "force_gpu_worker_return_receipt_ready"
                    ],
                    "next_after_actionable_blocker_unlock_fields": [
                        "delta_force",
                        "uncertainty",
                        "abstention_reason",
                        "stage2_route_decision",
                    ],
                },
                {
                    "action_id": "production_ai_return_summary",
                    "status": "blocked",
                    "gap_id": "production_ai_inference_checkpoint",
                    "release_blocker": True,
                    "artifact": "runs/residual_force_trajectory_regeneration_current_summary.json",
                    "required_operator_inputs": ["queue_rows", "processed_rows", "ok_rows"],
                    "operator_completion_packet_ready": True,
                    "operator_completion_packet": {
                        "artifact_id": "returned_summary_json",
                        "artifact_path": "runs/residual_force_trajectory_regeneration_current_summary.json",
                        "required_fields_or_columns": ["queue_rows", "processed_rows", "ok_rows"],
                        "expected_queue_rows": 768,
                        "completion_rule": (
                            "queue_rows equals expected_queue_rows; processed_rows>=expected_queue_rows"
                        ),
                        "backend_provenance_completion_rule": (
                            "prod_mode=true; require_rust_hip=true"
                        ),
                        "failed_check_ids": [
                            "actual_summary_returned_complete",
                            "production_gpu_backend_provenance",
                        ],
                        "template_payload": {"queue_rows": 768},
                        "template_payload_json": (
                            "runs/residual_force_trajectory_regeneration_current_summary_template.json"
                        ),
                        "validation_command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                        "next_action": "Return the completed GPU summary JSON.",
                    },
                    "next_action": "Return the completed GPU summary JSON.",
                    "execution_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",
                    "validation_command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                    "return_bundle_required_artifacts": [
                        "runs/residual_force_trajectory_regeneration_current_summary.json",
                        "runs/residual_force_trajectory_regeneration_current_manifest.csv",
                        "regenerated NPZ bundles referenced by the returned manifest",
                        "runs/residual_force_derivation_validation_current.json",
                    ],
                    "return_bundle_required_artifact_count": 4,
                    "return_bundle_artifact_completion_matrix": [
                        {"artifact_id": "returned_summary_json", "status": "blocked"},
                        {"artifact_id": "returned_manifest_csv", "status": "blocked"},
                        {"artifact_id": "returned_npz_bundles", "status": "blocked"},
                        {"artifact_id": "post_run_force_derivation_validation", "status": "blocked"},
                    ],
                    "return_bundle_artifact_completion_matrix_count": 4,
                    "return_bundle_next_artifact_id": "returned_summary_json",
                    "return_bundle_next_artifact_path": (
                        "runs/residual_force_trajectory_regeneration_current_summary.json"
                    ),
                    "return_bundle_next_artifact_failed_check_ids": [
                        "actual_summary_returned_complete"
                    ],
                    "return_bundle_manifest_required_columns": [
                        "queue_id",
                        "expected_regenerated_trajectory_npz",
                        "status",
                        "operator_verified_npz_exists",
                    ],
                    "return_bundle_post_return_validation_command": (
                        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                    ),
                    "return_bundle_guardrail": (
                        "Returned summary alone does not unlock production AI."
                    ),
                    "unlock_claim": "production_ai_inference_subject",
                    "workstream_lane_id": "gpu_return_after_environment",
                    "parallelizable_with_primary_blocker": False,
                    "parallel_lane_precondition": "production_gpu_execution_environment_ready",
                    "parallel_lane_priority": 0,
                    "blocked_by_action_id": "production_gpu_execution_environment",
                },
                {
                    "action_id": "transporter_next_slot_exact_evidence",
                    "status": "blocked",
                    "gap_id": "scope_breadth_expansion",
                    "release_blocker": True,
                    "artifact": "runs/transporter_manual_review_intake_template_current.csv",
                    "required_operator_inputs": [
                        "target_id",
                        "candidate_ligand_id",
                        "reference_binding_kcal_mol",
                        "source_url_or_doi",
                    ],
                    "required_exact_evidence_fields": [
                        "target_id",
                        "candidate_ligand_id",
                        "direct_binding_or_claim_safe_kcal_basis",
                        "reference_binding_kcal_mol",
                        "source_url_or_doi",
                        "target_match_decision",
                        "operator_review_decision",
                    ],
                    "required_claim_guardrails": [
                        "functional_surrogate_does_not_authorize_direct_binding_claim",
                        "reference_split_meta_rows_must_be_synchronized_before_promotion",
                    ],
                    "claim_safe_completion_rule": (
                        "Provide exact target-pair quantitative evidence before promotion."
                    ),
                    "operator_completion_packet_ready": True,
                    "operator_completion_packet": {
                        "completion_contract_version": "transporter_next_slot_exact_evidence_v2",
                        "slot_id": "AQP1.core_binder_01",
                        "expected_evidence_type": "direct_or_claim_safe_binding_kcal",
                        "required_exact_evidence_fields": ["target_id", "candidate_ligand_id"],
                        "required_claim_guardrails": ["functional_surrogate_does_not_authorize_direct_binding_claim"],
                        "required_missing_fields": ["replacement_reference_binding_kcal_mol"],
                        "next_slot_source_modality_guard_ready": True,
                        "next_slot_source_modality": "functional_quantitative_surrogate",
                        "next_slot_source_modality_claim_safe": False,
                        "next_slot_source_modality_direct_binding_claim_allowed": False,
                        "next_slot_source_modality_decision": (
                            "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
                        ),
                        "next_slot_source_modality_guardrails": [
                            "functional_quantitative_surrogate_is_review_only",
                            "direct_binding_claim_requires_exact_target_pair_source",
                        ],
                        "next_slot_source_modality_observed_signal": (
                            "request_mode=exact_target_pair_quantitative_binder_kcal_required"
                        ),
                        "next_slot_source_modality_required_upgrade": (
                            "exact target-pair direct/claim-safe binding kcal/mol"
                        ),
                        "next_slot_source_modality_triage_artifact": (
                            "runs/aqp1_binding_source_modality_triage_current.json"
                        ),
                        "next_slot_source_modality_triage_decision": (
                            "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
                        ),
                        "next_slot_source_modality_direct_experimental_binding_row_count": 0,
                        "next_slot_source_modality_claim_safe_binding_kcal_ready_count": 0,
                        "next_slot_source_modality_computational_binding_energy_row_count": 1,
                        "next_slot_source_modality_best_computational_binding_energy_kcal_mol": "-34.48",
                        "operator_validation_candidate_ready": True,
                        "operator_validation_candidate_status": "operator_validation_required",
                        "operator_validation_candidate_ligand_external_identifier": "CHEMBL20",
                        "operator_validation_candidate_reference_binding_kcal_mol": "-5.13",
                        "operator_validation_candidate_blocker": (
                            "data_validity_outside_typical_range_and_assay_origin_unknown"
                        ),
                        "operator_validation_candidate_claim_safe_ready": False,
                        "operator_review_artifact": "runs/transporter_manual_review_intake_template_current.csv",
                        "post_intake_synchronization_targets": [
                            "config/ligand_binding_reference_blind_aqp1_v1.csv",
                            "config/ligand_eval_splits_blind_aqp1_v1.csv",
                        ],
                        "acceptance_gate_commands": [
                            "python3 tools/build_transporter_binder_promotion_gate.py",
                            "python3 tools/build_product_scope_breadth_contract.py",
                        ],
                        "source_signal": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    },
                    "return_bundle_required_artifacts": [
                        "runs/transporter_manual_review_intake_template_current.csv",
                        "config/ligand_binding_reference_blind_aqp1_v1.csv",
                        "config/ligand_eval_splits_blind_aqp1_v1.csv",
                        "runs/transporter_binder_promotion_gate_current.json",
                        "runs/product_scope_breadth_contract_current.json",
                    ],
                    "return_bundle_required_artifact_count": 5,
                    "return_bundle_next_artifact_id": "operator_review_row",
                    "return_bundle_next_artifact_path": (
                        "runs/transporter_manual_review_intake_template_current.csv"
                    ),
                    "return_bundle_next_artifact_failed_check_ids": [
                        "next_slot_required_missing_fields"
                    ],
                    "next_action": "Acquire exact transporter evidence.",
                    "execution_command": "python3 tools/build_product_scope_breadth_contract.py",
                    "validation_command": "python3 tools/build_product_scope_breadth_contract.py",
                    "unlock_claim": "transporter_domain_promotion",
                    "workstream_lane_id": "parallel_scope_evidence",
                    "parallelizable_with_primary_blocker": True,
                    "parallel_lane_precondition": (
                        "Can be completed while ROCm/GPU environment is being prepared."
                    ),
                    "parallel_lane_priority": 1,
                    "parallel_primary_blocker_action_id": "production_gpu_execution_environment",
                    "next_slot_id": "AQP1.core_binder_01",
                    "candidate_ligand_id": "aqp1_bacopaside_ii_review_seed",
                    "target_scope_completion_packet": {
                        "target_ready_for_promotion_ids": ["GLUT1"],
                        "target_blocked_for_promotion_ids": ["AQP1"],
                        "primary_blocker_target_id": "AQP1",
                        "primary_blocker_packet_step": "core_binder_01",
                        "primary_blocker_candidate_name": "bacopaside II",
                        "claim_safe_guardrail": (
                            "Ready transporter targets do not authorize blocked transporter target promotion."
                        ),
                    },
                    "target_scope_guardrail": (
                        "Ready transporter targets do not authorize blocked transporter target promotion."
                    ),
                    "target_ready_for_promotion_ids": ["GLUT1"],
                    "target_blocked_for_promotion_ids": ["AQP1"],
                    "primary_blocker_target_id": "AQP1",
                    "primary_blocker_packet_step": "core_binder_01",
                    "primary_blocker_candidate_name": "bacopaside II",
                },
                {
                    "action_id": "pxr_next_exact_review",
                    "status": "blocked",
                    "gap_id": "scope_breadth_expansion",
                    "release_blocker": True,
                    "artifact": "runs/pxr_exact_evidence_review_intake_template_current.csv",
                    "required_operator_inputs": [
                        "review_row_id",
                        "replacement_reference_binding_kcal_mol",
                        "replacement_source_url_or_doi",
                    ],
                    "required_exact_evidence_fields": [
                        "review_row_id",
                        "target_gene",
                        "target_species",
                        "candidate_name",
                        "replacement_reference_binding_kcal_mol",
                        "replacement_source_url_or_doi",
                        "assay_type_and_endpoint",
                        "assay_is_direct_or_claim_safe",
                        "target_match_confirmed",
                        "review_decision",
                        "authoritative_apply_requested",
                        "conflict_resolution_decision",
                    ],
                    "required_claim_guardrails": [
                        "human_NR1I2_PXR_target_match_required",
                        "activity_proxy_conflict_must_be_resolved_or_deferred",
                        "review_only_or_deferred_rows_do_not_authorize_pxr_promotion",
                        "authoritative_apply_requested_only_when_direct_or_claim_safe",
                        "scope_promotion_allowed_false_until_gate_green",
                    ],
                    "claim_safe_completion_rule": (
                        "Provide exact human NR1I2/PXR quantitative kcal/source evidence, confirm target match "
                        "and assay type, resolve any activity-proxy conflict or keep the row deferred."
                    ),
                    "operator_completion_packet_ready": True,
                    "operator_completion_packet": {"review_row_id": "pxr_review_d603772038dff21e"},
                    "return_bundle_required_artifacts": [
                        "runs/pxr_exact_evidence_review_intake_template_current.csv",
                        "runs/pxr_packet_fill_readiness_current.json",
                        "runs/pxr_blocked_row_promotion_gate_current.json",
                        "runs/pxr_authoritative_reconciliation_packet_current.json",
                        "runs/product_scope_breadth_contract_current.json",
                    ],
                    "return_bundle_required_artifact_count": 5,
                    "next_action": "Complete exact human NR1I2/PXR review rows.",
                    "execution_command": "python3 tools/build_pxr_exact_evidence_review_intake_template.py",
                    "validation_command": "python3 tools/build_pxr_exact_evidence_review_intake_template.py",
                    "unlock_claim": "pxr_domain_promotion",
                    "next_review_row_id": "pxr_review_d603772038dff21e",
                    "candidate_name": "acetaminophen",
                },
                {
                    "action_id": "broad_platform_claim_floor",
                    "status": "blocked",
                    "gap_id": "scope_breadth_expansion",
                    "release_blocker": True,
                    "artifact": "runs/product_scope_breadth_contract_current.json",
                    "required_operator_inputs": [
                        "transporter_claim_acceptance",
                        "pxr_claim_acceptance",
                        "breadth_domain_floor_acceptance",
                        "general_platform_claim_acceptance",
                    ],
                    "required_claim_guardrails": [
                        "general_platform_claim_allowed_false_until_all_scope_acceptance_stages_green",
                        "transporter_and_pxr_domain_promotions_required_before_general_platform_claim",
                        "breadth_domain_floor_acceptance_required_before_capability_surface_widening",
                        "ready_restricted_families_do_not_authorize_general_protein_ligand_claim",
                    ],
                    "claim_safe_completion_rule": (
                        "Keep general protein-ligand platform wording blocked until transporter, PXR, "
                        "breadth-domain floor, and capability-surface acceptance stages are all green."
                    ),
                    "operator_completion_packet_ready": True,
                    "operator_completion_packet": {
                        "blocked_stage_evidence_count": 4,
                        "blocked_stage_ids": [
                            "transporter_claim_acceptance",
                            "pxr_claim_acceptance",
                            "breadth_domain_floor_acceptance",
                            "general_platform_claim_acceptance",
                        ],
                        "blocked_stage_dependency_matrix": [
                            {
                                "stage_id": "transporter_claim_acceptance",
                                "first_blocked_evidence_row_id": "AQP1.core_binder_01",
                                "unlock_claim_scopes": ["transporter_domain_promotion"],
                            },
                            {
                                "stage_id": "pxr_claim_acceptance",
                                "first_blocked_evidence_row_id": "pxr_review_d603772038dff21e",
                                "unlock_claim_scopes": ["pxr_domain_promotion"],
                            },
                        ],
                        "first_blocked_stage_id": "transporter_claim_acceptance",
                        "first_blocked_evidence_row_id": "AQP1.core_binder_01",
                        "first_blocked_target_id": "AQP1",
                        "first_blocked_candidate": "aqp1_bacopaside_ii_review_seed",
                        "first_blocked_required_missing_fields": "replacement_reference_binding_kcal_mol",
                        "required_claim_guardrails": [
                            "general_platform_claim_allowed_false_until_all_scope_acceptance_stages_green",
                            "ready_restricted_families_do_not_authorize_general_protein_ligand_claim",
                        ],
                        "completion_rule": (
                            "Keep general protein-ligand platform wording blocked until transporter, PXR, "
                            "breadth-domain floor, and capability-surface acceptance stages are all green."
                        ),
                    },
                    "next_action": "Keep broad platform claim blocked.",
                    "execution_command": "python3 tools/build_product_scope_breadth_contract.py",
                    "validation_command": "python3 tools/build_product_scope_breadth_contract.py",
                    "unlock_claim": "general_protein_ligand_platform",
                    "blocked_stage_dependency_count": 4,
                    "first_blocked_stage_id": "transporter_claim_acceptance",
                    "first_blocked_evidence_row_id": "AQP1.core_binder_01",
                    "first_blocked_target_id": "AQP1",
                    "first_blocked_candidate": "aqp1_bacopaside_ii_review_seed",
                    "first_blocked_required_missing_fields": "replacement_reference_binding_kcal_mol",
                },
            ],
        }
    }


def _aqp1_procurement() -> dict:
    return {
        "summary": {
            "status": "aqp1_direct_binding_procurement_packet_ready",
            "procurement_packet_ready": True,
            "direct_binding_gap_open": True,
            "external_primary_evidence_required": True,
            "first_required_external_action_id": "procure_aqp1_bacopaside_ii_direct_binding_measurement",
            "current_operator_candidate_blocker": (
                "data_validity_outside_typical_range_and_assay_origin_unknown"
            ),
            "minimum_acceptance_rule": (
                "target_uniprot=P29972; standard_type in Kd,Ki; operator_claim_safe_decision=approve_claim_safe"
            ),
            "accepted_direct_binding_methods": ["SPR equilibrium Kd", "ITC Kd"],
            "acceptance_fields": ["target_uniprot", "standard_value_nM", "operator_claim_safe_decision"],
        }
    }


def _aqp1_external_fill_guide() -> dict:
    return {
        "summary": {
            "status": "aqp1_direct_binding_external_evidence_operator_fill_guide_ready",
            "operator_fill_row_count": 3,
            "next_required_step": "Fill exact AQP1 direct-binding evidence rows.",
        }
    }


def _aqp1_external_worksheet() -> dict:
    return {
        "summary": {
            "status": "aqp1_direct_binding_external_evidence_operator_worksheet_ready",
            "worksheet_field_row_count": 42,
            "operator_fill_pending_field_count": 19,
            "validation_error_count": 0,
            "supplement_csv": "runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv",
            "next_required_step": "Complete every operator_fill_pending field.",
        }
    }


def _aqp1_external_staging_apply() -> dict:
    return {
        "summary": {
            "status": "blocked_aqp1_operator_staging_apply",
            "mode": "preview",
            "live_apply_allowed": False,
            "validation_error_count": 2,
            "staging_claim_safe_approved_count": 0,
            "next_required_step": "Replace illustrative placeholders with verified direct Kd/Ki.",
        }
    }


def _registry_receipt() -> dict:
    return {
        "summary": {
            "status": "blocked_production_ai_registry_promotion_operator_receipt",
            "operator_receipt_ready": False,
            "receipt_present": True,
            "receipt_csv": "config/production_ai_registry_promotion_operator_receipt_current.csv",
            "receipt_row_count": 1,
            "blocker_count": 1,
            "blocked_row_count": 1,
            "blockers": ["blocked_receipt_rows_present"],
            "first_blocked_artifact_id": "residual_model_registry_guarded_promotion",
            "first_blocked_row_blocker": "operator_placeholders_unfilled",
            "first_blocked_row_blockers": [
                "operator_placeholders_unfilled",
                "default_residual_mode_not_guarded",
            ],
            "most_common_row_blocker": "operator_placeholders_unfilled",
            "approval_token_required": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",
            "next_required_step": "Fill the production AI registry promotion receipt.",
            "registry_artifact": "runs/residual_model_registry_current.json",
            "checkpoint_readiness_artifact": (
                "runs/product_production_ai_checkpoint_readiness_current.json"
            ),
            "observed_registry_default_residual_mode": "shadow",
            "observed_registry_trained_model_checkpoint_count": 0,
            "observed_checkpoint_registry_promotion_currently_satisfied": False,
            "observed_checkpoint_registry_promotion_missing_gate_ids": [
                "production_promotion_allowed",
                "default_residual_mode_guarded",
            ],
            "registry_edited_by_this_tool": False,
            "checkpoint_created_by_this_tool": False,
        }
    }


def _registry_priority() -> dict:
    return {
        "summary": {
            "status": "blocked_production_ai_registry_promotion_priority_packet",
            "priority_packet_ready": True,
            "registry_promotion_ready": False,
            "operator_input_required_count": 4,
            "blocked_priority_item_count": 4,
            "registry_promotion_missing_gate_count": 4,
            "registry_promotion_missing_gate_ids": [
                "trained_model_checkpoint_count_positive",
                "default_residual_mode_guarded",
                "production_promotion_allowed",
                "customer_facing_mutation_flags",
            ],
            "operator_receipt_csv": "config/production_ai_registry_promotion_operator_receipt_current.csv",
            "approval_token_required": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",
            "observed_registry_default_residual_mode": "shadow",
            "observed_registry_production_promotion_allowed": False,
            "observed_registry_customer_facing_mutation_flags_ready": False,
            "observed_registry_trained_model_checkpoint_count": 0,
            "top_gate_id": "trained_model_checkpoint_count_positive",
            "top_priority_bucket": "trained_checkpoint_registration_required",
            "top_required_input": "Register a trained production residual checkpoint.",
            "top_acceptance_artifact": "runs/residual_model_registry_current.json",
            "top_verification_command": "python3 tools/build_residual_model_registry.py",
            "top_next_operator_step": "Register checkpoint, then rerun registry readiness.",
            "model_promoted": False,
            "customer_facing_mutation_enabled": False,
            "external_state_mutated": False,
        }
    }


def _registry_field_worksheet() -> dict:
    return {
        "summary": {
            "status": "production_ai_registry_promotion_operator_field_worksheet_ready",
            "field_worksheet_ready": True,
            "operator_fill_complete": False,
            "worksheet_field_row_count": 20,
            "required_receipt_field_count": 19,
            "operator_fill_pending_field_count": 13,
            "diagnostic_required_field_count": 6,
            "diagnostic_required_pending_field_count": 6,
            "pending_field_names": [
                "operator_decision",
                "production_promotion_allowed",
                "default_residual_mode",
            ],
            "top_gate_id": "trained_model_checkpoint_count_positive",
            "top_required_input": "Register a trained production residual checkpoint.",
            "approval_token_required": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",
            "observed_registry_default_residual_mode": "shadow",
            "observed_registry_trained_model_checkpoint_count": 0,
            "model_promoted": False,
            "customer_facing_mutation_enabled": False,
            "external_state_mutated": False,
            "next_required_step": "Fill every operator_fill_pending field.",
        }
    }


def _engine_refinement_claim_evidence_field_worksheet() -> dict:
    return {
        "summary": {
            "status": "engine_refinement_claim_evidence_operator_field_worksheet_ready",
            "field_worksheet_ready": True,
            "operator_fill_complete": False,
            "worksheet_field_row_count": 144,
            "required_receipt_field_count": 66,
            "operator_fill_pending_field_count": 108,
            "receipt_operator_fill_pending_field_count": 36,
            "public_benchmark_work_order_pending_field_count": 72,
            "top_blocker_id": "public_benchmark_gate_not_ready",
            "top_priority_bucket": "public_benchmark_work_order_apply_required",
            "top_blocker_pending_field_count": 78,
            "public_benchmark_work_order_apply_blocked_row_count": 8,
            "claim_promoted": False,
            "external_engine_calls_executed": False,
            "external_state_mutated": False,
        }
    }


def _product_scope_breadth_evidence_field_worksheet() -> dict:
    return {
        "summary": {
            "status": "product_scope_breadth_evidence_operator_field_worksheet_ready",
            "field_worksheet_ready": True,
            "operator_fill_complete": False,
            "receipt_field_row_count": 72,
            "required_receipt_field_count": 66,
            "operator_fill_pending_field_count": 36,
            "top_blocker_id": "direct_binding_evidence_missing",
            "top_blocker_pending_field_count": 6,
            "top_item_id": "AQP1.core_binder_01",
            "top_bucket": "local_crosscheck_review_present_but_exact_quant_required",
            "top_required_evidence_type": "exact_transporter_target_pair_quantitative_binder_kcal",
            "priority_open_item_count": 15,
            "priority_local_crosscheck_candidate_count": 11,
            "scope_checklist_manual_review_subcheck_count": 39,
            "claim_promoted": False,
            "external_state_mutated": False,
        }
    }


def _product_scope_breadth_evidence_staging_apply() -> dict:
    return {
        "summary": {
            "status": "blocked_product_scope_breadth_evidence_operator_staging_apply",
            "candidate_receipt_ready": False,
            "candidate_blocked_row_count": 6,
            "candidate_pass_row_count": 0,
            "staging_placeholder_row_count": 6,
            "field_worksheet_pending_field_count": 36,
            "candidate_first_blocked_scope_blocker_id": "direct_binding_evidence_missing",
            "candidate_most_common_row_blocker": "operator_placeholders_unfilled",
            "live_copy_allowed": False,
            "canonical_receipt_written": False,
            "external_state_mutated": False,
        }
    }


def test_build_product_commercial_readiness_operator_packet_flattens_next_actions() -> None:
    payload = mod.build_product_commercial_readiness_operator_packet(
        goal_audit_packet=_goal_audit(),
        aqp1_direct_binding_procurement_packet=_aqp1_procurement(),
        aqp1_external_operator_fill_guide_packet=_aqp1_external_fill_guide(),
        aqp1_external_operator_worksheet_packet=_aqp1_external_worksheet(),
        aqp1_external_operator_staging_apply_packet=_aqp1_external_staging_apply(),
        production_ai_registry_promotion_operator_receipt_packet=_registry_receipt(),
        production_ai_registry_promotion_priority_packet=_registry_priority(),
        production_ai_registry_promotion_field_worksheet_packet=_registry_field_worksheet(),
        product_scope_breadth_evidence_field_worksheet_packet=(
            _product_scope_breadth_evidence_field_worksheet()
        ),
        product_scope_breadth_evidence_staging_apply_packet=(
            _product_scope_breadth_evidence_staging_apply()
        ),
        engine_refinement_claim_evidence_field_worksheet_packet=(
            _engine_refinement_claim_evidence_field_worksheet()
        ),
        delta_force_closure_packet={
            "summary": {
                "packet_ready": True,
                "delta_force_closure_ready": False,
                "first_blocked_output_field": "delta_force",
                "ready_output_field_count": 6,
                "blocked_output_field_count": 1,
                "closure_failed_stage_count": 9,
                "closure_failed_stage_ids": ["gpu_worker_return_receipt"],
                "next_stage_id": "gpu_worker_return_receipt",
                "next_stage_artifact": "runs/product_production_ai_gpu_return_intake_current.json",
                "next_stage_validation_command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                "next_required_step": "Return GPU summary.",
                "operator_return_required_artifact_count": 5,
                "operator_return_required_artifacts": ["summary.json", "manifest.csv"],
                "return_summary_required_fields": ["queue_rows", "backend_counts"],
                "post_return_validation_command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
            }
        },
        scope_closure_packet={
            "summary": {
                "packet_ready": True,
                "scope_closure_ready": False,
                "scope_acceptance_stage_count": 5,
                "scope_acceptance_blocked_stage_count": 4,
                "scope_acceptance_blocked_stage_ids": [
                    "transporter_claim_acceptance",
                    "pxr_claim_acceptance",
                ],
                "scope_acceptance_next_stage_id": "transporter_claim_acceptance",
                "scope_acceptance_next_stage_artifact": "runs/transporter.json",
                "scope_acceptance_next_stage_validation_command": "python3 tools/build_product_scope_breadth_contract.py",
                "first_blocked_evidence_row_id": "AQP1.core_binder_01",
                "first_blocked_target_id": "AQP1",
                "first_blocked_candidate": "aqp1_bacopaside_ii_review_seed",
                "first_blocked_required_missing_fields": "replacement_reference_binding_kcal_mol",
                "transporter_unresolved_slot_count": 11,
                "pxr_direct_or_claim_safe_quantitative_ready_count": 0,
                "general_platform_claim_allowed": False,
                "next_required_step": "Acquire exact transporter evidence.",
            }
        },
        goal_audit_path="runs/nonexistent_unit_goal_audit.json",
        delta_force_closure_packet_path="runs/unit_delta_force_closure.json",
        scope_closure_packet_path="runs/unit_scope_closure.json",
    )

    summary = payload["summary"]
    assert summary["status"] == "product_commercial_readiness_operator_packet_ready"
    assert summary["packet_ready"] is True
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
            "engine_refinement_claim_evidence_operator_field_worksheet_receipt_pending_field_count"
        ]
        == 36
    )
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
            "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_pending_field_count"
        ]
        == 78
    )
    assert (
        summary[
            "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_apply_blocked_row_count"
        ]
        == 8
    )
    assert summary["engine_refinement_claim_evidence_operator_field_worksheet_claim_promoted"] is False
    assert (
        summary[
            "engine_refinement_claim_evidence_operator_field_worksheet_external_engine_calls_executed"
        ]
        is False
    )
    assert (
        summary["engine_refinement_claim_evidence_operator_field_worksheet_external_state_mutated"]
        is False
    )
    assert "curated public benchmark rows" in summary[
        "engine_refinement_claim_promotion_next_required_step"
    ]
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
    assert summary["product_scope_breadth_evidence_operator_field_worksheet_status"] == (
        "product_scope_breadth_evidence_operator_field_worksheet_ready"
    )
    assert summary["product_scope_breadth_evidence_operator_field_worksheet_ready"] is True
    assert (
        summary["product_scope_breadth_evidence_operator_field_worksheet_operator_fill_complete"]
        is False
    )
    assert summary["product_scope_breadth_evidence_operator_field_worksheet_field_row_count"] == 72
    assert (
        summary[
            "product_scope_breadth_evidence_operator_field_worksheet_required_receipt_field_count"
        ]
        == 66
    )
    assert summary["product_scope_breadth_evidence_operator_field_worksheet_pending_field_count"] == 36
    assert summary["product_scope_breadth_evidence_operator_field_worksheet_top_blocker_id"] == (
        "direct_binding_evidence_missing"
    )
    assert (
        summary[
            "product_scope_breadth_evidence_operator_field_worksheet_top_blocker_pending_field_count"
        ]
        == 6
    )
    assert summary["product_scope_breadth_evidence_operator_field_worksheet_top_item_id"] == (
        "AQP1.core_binder_01"
    )
    assert summary["product_scope_breadth_evidence_operator_field_worksheet_top_bucket"] == (
        "local_crosscheck_review_present_but_exact_quant_required"
    )
    assert (
        summary["product_scope_breadth_evidence_operator_field_worksheet_priority_open_item_count"]
        == 15
    )
    assert (
        summary[
            "product_scope_breadth_evidence_operator_field_worksheet_scope_checklist_manual_review_subcheck_count"
        ]
        == 39
    )
    assert summary["product_scope_breadth_evidence_operator_field_worksheet_claim_promoted"] is False
    assert (
        summary["product_scope_breadth_evidence_operator_field_worksheet_external_state_mutated"]
        is False
    )
    assert summary["product_scope_breadth_evidence_operator_staging_apply_status"] == (
        "blocked_product_scope_breadth_evidence_operator_staging_apply"
    )
    assert (
        summary["product_scope_breadth_evidence_operator_staging_apply_candidate_receipt_ready"]
        is False
    )
    assert (
        summary["product_scope_breadth_evidence_operator_staging_apply_candidate_blocked_row_count"]
        == 6
    )
    assert (
        summary["product_scope_breadth_evidence_operator_staging_apply_staging_placeholder_row_count"]
        == 6
    )
    assert (
        summary[
            "product_scope_breadth_evidence_operator_staging_apply_field_worksheet_pending_field_count"
        ]
        == 36
    )
    assert (
        summary["product_scope_breadth_evidence_operator_staging_apply_first_blocked_scope_blocker_id"]
        == "direct_binding_evidence_missing"
    )
    assert (
        summary["product_scope_breadth_evidence_operator_staging_apply_most_common_row_blocker"]
        == "operator_placeholders_unfilled"
    )
    assert summary["product_scope_breadth_evidence_operator_staging_apply_live_copy_allowed"] is False
    assert (
        summary["product_scope_breadth_evidence_operator_staging_apply_canonical_receipt_written"]
        is False
    )
    assert (
        summary["product_scope_breadth_evidence_operator_staging_apply_external_state_mutated"]
        is False
    )
    assert summary["primary_full_commercial_release_blocker_id"] == (
        "R8_full_scope_claim_closure"
    )
    assert summary["primary_full_commercial_release_blocker_tier"] == "full_commercial_scope"
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
    assert (
        summary["product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready"]
        is True
    )
    assert summary["product_scope_transporter_p0_return_bundle_required_artifact_count"] == 5
    assert "config/ligand_binding_reference_blind_aqp1_v1.csv" in summary[
        "product_scope_transporter_p0_return_bundle_required_artifacts"
    ]
    assert summary["product_scope_transporter_p0_return_bundle_blocker_count"] == 5
    assert summary["product_scope_transporter_p0_return_bundle_next_artifact_id"] == (
        "operator_review_row"
    )
    assert summary["product_scope_transporter_p0_return_bundle_next_artifact_path"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert "next_slot_required_missing_fields" in summary[
        "product_scope_transporter_p0_return_bundle_next_artifact_failed_check_ids"
    ]
    assert summary["product_goal_scope_transporter_p0_operator_validation_candidate_status"] == (
        "operator_validation_required"
    )
    assert summary["product_goal_scope_transporter_p0_return_bundle_next_artifact_path"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert summary["open_gap_ids"] == [
        "production_ai_inference_checkpoint",
        "scope_breadth_expansion",
    ]
    assert len(summary["commercial_readiness_matrix_sha256"]) == 64
    assert len(summary["goal_audit_sha256"]) == 64
    assert summary["source_fingerprint_ready"] is True
    assert summary["action_count"] == 5
    assert summary["blocked_action_count"] == 5
    assert summary["parallelizable_action_count"] == 1
    assert summary["parallelizable_action_ids"] == ["transporter_next_slot_exact_evidence"]
    assert summary["first_parallelizable_action_id"] == "transporter_next_slot_exact_evidence"
    assert summary["first_parallelizable_action_lane_id"] == "parallel_scope_evidence"
    assert "ROCm/GPU environment" in summary["first_parallelizable_action_precondition"]
    assert "reference_binding_kcal_mol" in summary[
        "first_parallelizable_action_required_operator_inputs"
    ]
    assert "direct_binding_or_claim_safe_kcal_basis" in summary[
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
        "first_parallelizable_action_next_slot_source_modality_direct_experimental_binding_row_count"
    ] == 0
    assert summary[
        "first_parallelizable_action_next_slot_source_modality_claim_safe_binding_kcal_ready_count"
    ] == 0
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
    assert (
        summary["first_parallelizable_action_direct_binding_procurement_first_required_external_action_id"]
        == "procure_aqp1_bacopaside_ii_direct_binding_measurement"
    )
    assert summary[
        "first_parallelizable_action_direct_binding_procurement_direct_binding_gap_open"
    ] is True
    assert "standard_type in Kd,Ki" in summary[
        "first_parallelizable_action_direct_binding_procurement_minimum_acceptance_rule"
    ]
    assert "SPR equilibrium Kd" in summary[
        "first_parallelizable_action_direct_binding_procurement_accepted_direct_binding_methods"
    ]
    assert "functional_quantitative_surrogate_is_review_only" in summary[
        "first_parallelizable_action_next_slot_source_modality_guardrails"
    ]
    assert summary["product_scope_transporter_p0_external_operator_artifacts"] == [
        "runs/aqp1_direct_binding_external_evidence_operator_fill_guide_current.json",
        "runs/aqp1_direct_binding_external_evidence_operator_worksheet_current.json",
        "runs/aqp1_direct_binding_external_evidence_operator_staging_apply_current.json",
    ]
    assert summary[
        "product_scope_transporter_p0_external_operator_fill_guide_ready"
    ] is True
    assert summary[
        "product_scope_transporter_p0_external_operator_fill_guide_row_count"
    ] == 3
    assert summary[
        "product_scope_transporter_p0_external_operator_worksheet_pending_field_count"
    ] == 19
    assert summary[
        "product_scope_transporter_p0_external_operator_worksheet_supplement_csv"
    ] == "runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv"
    assert summary[
        "product_scope_transporter_p0_external_operator_staging_apply_live_apply_allowed"
    ] is False
    assert summary[
        "product_scope_transporter_p0_external_operator_staging_apply_validation_error_count"
    ] == 2
    assert summary[
        "product_goal_scope_transporter_p0_external_operator_worksheet_pending_field_count"
    ] == 19
    assert summary["first_action_id"] == "production_gpu_execution_environment"
    assert summary["first_artifact"] == "runs/rocm_environment_manifest_current.json"
    assert summary["first_execution_command"] == "python3 tools/build_rocm_environment_manifest.py"
    assert summary["first_operator_completion_packet_ready"] is True
    assert summary["first_operator_completion_artifact_id"] == "rocm_environment_manifest_json"
    assert summary["first_operator_completion_artifact_path"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert summary["first_operator_completion_required_fields_or_columns"] == [
        "manifest_ready",
        "rocm_stack_detected",
        "torch_rocm_ready",
        "amd_gpu_detected",
        "visible_device_count",
    ]
    assert summary["first_operator_completion_validation_command"] == (
        "python3 tools/build_rocm_environment_manifest.py"
    )
    assert "required_fields_or_columns" in summary["first_operator_completion_packet_keys"]
    assert summary["first_operator_completion_worker_runtime_receipt_contract_ready"] is True
    assert summary["first_operator_completion_worker_runtime_receipt_required_field_count"] == 5
    assert "backend_counts" in summary[
        "first_operator_completion_worker_runtime_receipt_required_fields_or_columns"
    ]
    assert "visible_device_count>0" in summary[
        "first_operator_completion_worker_runtime_receipt_completion_rule"
    ]
    assert summary[
        "first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id"
    ] == "gpu_return_acceptance"
    assert summary[
        "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact"
    ] == "runs/residual_force_gpu_worker_return_receipt_current.json"
    assert "build_residual_force_gpu_worker_return_receipt.py" in summary[
        "first_operator_completion_worker_runtime_receipt_post_environment_validation_command"
    ]
    assert "prod-mode" in summary[
        "first_operator_completion_worker_runtime_receipt_full_regeneration_command"
    ]
    assert "cpu_fallback_does_not_satisfy_production_inference" in summary[
        "first_operator_completion_worker_runtime_receipt_guardrails"
    ]
    assert summary["first_operator_completion_diagnostic_command_count"] == 3
    assert "rocminfo" in summary["first_operator_completion_diagnostic_commands"]
    assert "visible_device_count>0" in summary[
        "first_operator_completion_diagnostic_completion_rule"
    ]
    assert "runs/rocm_environment_manifest_current.json" in summary[
        "first_operator_completion_diagnostic_return_artifacts"
    ]
    assert summary["first_operator_completion_torch_visibility_probe_command"].startswith(
        "python3 -c"
    )
    assert payload["rows"][0]["operator_completion_worker_runtime_receipt_contract_ready"] is True
    assert "backend_counts" in payload["rows"][0][
        "operator_completion_worker_runtime_receipt_required_fields_or_columns"
    ]
    assert payload["rows"][0][
        "operator_completion_worker_runtime_receipt_post_environment_next_artifact"
    ] == "runs/residual_force_gpu_worker_return_receipt_current.json"
    assert payload["rows"][0]["operator_completion_diagnostic_command_count"] == 3
    assert "torch.cuda.device_count" in payload["rows"][0][
        "operator_completion_torch_visibility_probe_command"
    ]
    assert summary["production_ai_return_action_id"] == "production_ai_return_summary"
    assert summary["production_ai_return_action_blocked_by_action_id"] == (
        "production_gpu_execution_environment"
    )
    assert summary["production_ai_return_action_artifact"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert summary["production_ai_return_operator_completion_packet_ready"] is True
    assert summary["production_ai_return_operator_completion_artifact_id"] == (
        "returned_summary_json"
    )
    assert summary["production_ai_return_operator_completion_artifact_path"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert "queue_rows" in summary[
        "production_ai_return_operator_completion_required_fields_or_columns"
    ]
    assert summary["production_ai_return_operator_completion_expected_queue_rows"] == 768
    assert "processed_rows" in summary[
        "production_ai_return_operator_completion_completion_rule"
    ]
    assert "require_rust_hip" in summary[
        "production_ai_return_operator_completion_backend_provenance_completion_rule"
    ]
    assert "production_gpu_backend_provenance" in summary[
        "production_ai_return_operator_completion_failed_check_ids"
    ]
    assert summary["production_ai_return_bundle_required_artifact_count"] == 4
    assert any(
        "residual_force_trajectory_regeneration_current_manifest.csv" in artifact
        for artifact in summary["production_ai_return_bundle_required_artifacts"]
    )
    assert summary["production_ai_return_bundle_next_artifact_id"] == "returned_summary_json"
    assert "actual_summary_returned_complete" in summary[
        "production_ai_return_bundle_next_artifact_failed_check_ids"
    ]
    assert "operator_verified_npz_exists" in summary[
        "production_ai_return_bundle_manifest_required_columns"
    ]
    assert "build_residual_force_gpu_worker_return_receipt.py" in summary[
        "production_ai_return_bundle_post_return_validation_command"
    ]
    assert "summary alone does not unlock" in summary["production_ai_return_bundle_guardrail"]
    assert summary["production_ai_registry_promotion_operator_receipt_status"] == (
        "blocked_production_ai_registry_promotion_operator_receipt"
    )
    assert summary["production_ai_registry_promotion_operator_receipt_ready"] is False
    assert summary["production_ai_registry_promotion_operator_receipt_present"] is True
    assert summary["production_ai_registry_promotion_operator_receipt_csv"] == (
        "config/production_ai_registry_promotion_operator_receipt_current.csv"
    )
    assert summary["production_ai_registry_promotion_operator_receipt_blocker_count"] == 1
    assert summary["production_ai_registry_promotion_operator_receipt_blocked_row_count"] == 1
    assert summary["production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker"] == (
        "operator_placeholders_unfilled"
    )
    assert "default_residual_mode_guarded" in summary[
        "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_missing_gate_ids"
    ]
    assert summary[
        "production_ai_registry_promotion_operator_receipt_approval_token_required"
    ] == "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
    assert summary[
        "production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode"
    ] == "shadow"
    assert summary[
        "production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count"
    ] == 0
    assert (
        summary[
            "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_currently_satisfied"
        ]
        is False
    )
    assert summary["production_ai_registry_promotion_priority_status"] == (
        "blocked_production_ai_registry_promotion_priority_packet"
    )
    assert summary["production_ai_registry_promotion_priority_packet_ready"] is True
    assert summary["production_ai_registry_promotion_priority_registry_promotion_ready"] is False
    assert summary["production_ai_registry_promotion_priority_operator_input_required_count"] == 4
    assert summary["production_ai_registry_promotion_priority_missing_gate_count"] == 4
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
    assert summary["production_ai_registry_promotion_priority_top_acceptance_artifact"] == (
        "runs/residual_model_registry_current.json"
    )
    assert summary["production_ai_registry_promotion_priority_model_promoted"] is False
    assert summary["production_ai_registry_promotion_priority_customer_facing_mutation_enabled"] is False
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
    assert "default_residual_mode" in summary[
        "production_ai_registry_promotion_operator_field_worksheet_pending_field_names"
    ]
    assert summary[
        "production_ai_registry_promotion_operator_field_worksheet_external_state_mutated"
    ] is False
    assert summary["delta_force_closure_acceptance_packet_artifact"] == (
        "runs/unit_delta_force_closure.json"
    )
    assert summary["delta_force_closure_acceptance_packet_ready"] is True
    assert summary["delta_force_closure_ready"] is False
    assert summary["delta_force_closure_first_blocked_output_field"] == "delta_force"
    assert summary["delta_force_closure_ready_output_field_count"] == 6
    assert summary["delta_force_closure_blocked_output_field_count"] == 1
    assert summary["delta_force_closure_failed_stage_count"] == 9
    assert summary["delta_force_closure_failed_stage_ids"] == ["gpu_worker_return_receipt"]
    assert summary["delta_force_closure_next_stage_id"] == "gpu_worker_return_receipt"
    assert summary["delta_force_closure_next_stage_artifact"] == (
        "runs/product_production_ai_gpu_return_intake_current.json"
    )
    assert "build_residual_force_gpu_worker_return_receipt.py" in summary[
        "delta_force_closure_next_stage_validation_command"
    ]
    assert summary["delta_force_closure_operator_return_required_artifact_count"] == 5
    assert summary["delta_force_closure_operator_return_required_artifacts"] == [
        "summary.json",
        "manifest.csv",
    ]
    assert summary["delta_force_closure_return_summary_required_fields"] == [
        "queue_rows",
        "backend_counts",
    ]
    assert summary["scope_closure_acceptance_packet_artifact"] == (
        "runs/unit_scope_closure.json"
    )
    assert summary["scope_closure_acceptance_packet_ready"] is True
    assert summary["scope_closure_ready"] is False
    assert summary["scope_closure_stage_count"] == 5
    assert summary["scope_closure_blocked_stage_count"] == 4
    assert summary["scope_closure_blocked_stage_ids"] == [
        "transporter_claim_acceptance",
        "pxr_claim_acceptance",
    ]
    assert summary["scope_closure_next_stage_id"] == "transporter_claim_acceptance"
    assert summary["scope_closure_first_blocked_evidence_row_id"] == "AQP1.core_binder_01"
    assert summary["scope_closure_first_blocked_target_id"] == "AQP1"
    assert summary["scope_closure_first_blocked_required_missing_fields"] == (
        "replacement_reference_binding_kcal_mol"
    )
    assert summary["scope_closure_transporter_unresolved_slot_count"] == 11
    assert summary["scope_closure_pxr_direct_or_claim_safe_quantitative_ready_count"] == 0
    assert summary["scope_closure_general_platform_claim_allowed"] is False
    assert payload["rows"][0]["next_after_actionable_blocker_stage_id"] == "gpu_return_acceptance"
    assert payload["rows"][0]["next_after_actionable_blocker_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert payload["rows"][0]["next_after_actionable_blocker_required_checks"] == (
        "force_gpu_worker_return_receipt_ready"
    )
    assert "delta_force" in payload["rows"][0]["next_after_actionable_blocker_unlock_fields"]
    assert payload["rows"][1]["return_bundle_required_artifact_count"] == 4
    assert "residual_force_trajectory_regeneration_current_manifest.csv" in payload["rows"][1][
        "return_bundle_required_artifacts"
    ]
    assert payload["rows"][1]["return_bundle_artifact_completion_matrix_count"] == 4
    assert payload["rows"][1]["return_bundle_next_artifact_id"] == "returned_summary_json"
    assert payload["rows"][1]["return_bundle_next_artifact_path"] == (
        "runs/residual_force_trajectory_regeneration_current_summary.json"
    )
    assert payload["rows"][1]["return_bundle_next_artifact_failed_check_ids"] == (
        "actual_summary_returned_complete"
    )
    assert "operator_verified_npz_exists" in payload["rows"][1][
        "return_bundle_manifest_required_columns"
    ]
    assert payload["rows"][1]["return_bundle_post_return_validation_command"] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert "summary alone does not unlock" in payload["rows"][1]["return_bundle_guardrail"]
    assert payload["rows"][1]["blocked_by_action_id"] == "production_gpu_execution_environment"
    assert summary["operator_completion_packet_ready_count"] == 5
    assert summary["operator_input_total_count"] == 19
    assert summary["release_blocker_action_ids"] == [
        "production_gpu_execution_environment",
        "production_ai_return_summary",
        "transporter_next_slot_exact_evidence",
        "pxr_next_exact_review",
        "broad_platform_claim_floor",
    ]
    assert payload["rows"][2]["next_slot_id"] == "AQP1.core_binder_01"
    assert payload["rows"][2]["parallelizable_with_primary_blocker"] is True
    assert payload["rows"][2]["parallel_primary_blocker_action_id"] == (
        "production_gpu_execution_environment"
    )
    assert payload["rows"][2]["parallel_lane_priority"] == 1
    assert "reference_binding_kcal_mol" in payload["rows"][2]["required_operator_inputs"]
    assert "direct_binding_or_claim_safe_kcal_basis" in payload["rows"][2][
        "required_exact_evidence_fields"
    ]
    assert "target_match_decision" in payload["rows"][2]["required_exact_evidence_fields"]
    assert "functional_surrogate_does_not_authorize_direct_binding_claim" in payload["rows"][2][
        "required_claim_guardrails"
    ]
    assert payload["rows"][2]["expected_evidence_type"] == "direct_or_claim_safe_binding_kcal"
    assert "replacement_reference_binding_kcal_mol" in payload["rows"][2]["required_missing_fields"]
    assert payload["rows"][2]["operator_review_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert "ligand_binding_reference_blind_aqp1" in payload["rows"][2][
        "post_intake_synchronization_targets"
    ]
    assert "build_product_scope_breadth_contract.py" in payload["rows"][2][
        "acceptance_gate_commands"
    ]
    assert payload["rows"][2]["source_signal"].startswith("https://pubmed")
    assert payload["rows"][2]["next_slot_source_modality_guard_ready"] is True
    assert payload["rows"][2]["next_slot_source_modality"] == "functional_quantitative_surrogate"
    assert payload["rows"][2]["next_slot_source_modality_direct_binding_claim_allowed"] is False
    assert payload["rows"][2]["next_slot_source_modality_decision"] == (
        "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
    )
    assert payload["rows"][2]["operator_validation_candidate_ready"] is True
    assert payload["rows"][2]["operator_validation_candidate_status"] == (
        "operator_validation_required"
    )
    assert payload["rows"][2]["operator_validation_candidate_ligand_external_identifier"] == (
        "CHEMBL20"
    )
    assert payload["rows"][2]["operator_validation_candidate_reference_binding_kcal_mol"] == (
        "-5.13"
    )
    assert payload["rows"][2]["operator_validation_candidate_claim_safe_ready"] is False
    assert payload["rows"][2]["direct_binding_procurement_packet_ready"] is True
    assert payload["rows"][2]["direct_binding_procurement_packet_artifact"] == (
        "runs/aqp1_direct_binding_procurement_packet_current.json"
    )
    assert payload["rows"][2]["direct_binding_procurement_external_primary_evidence_required"] is True
    assert "exact target-pair quantitative evidence" in payload["rows"][2][
        "claim_safe_completion_rule"
    ]
    assert "completion_contract_version" in payload["rows"][2]["operator_completion_packet_keys"]
    assert "required_exact_evidence_fields" in payload["rows"][2]["operator_completion_packet_keys"]
    assert payload["rows"][2]["target_ready_for_promotion_ids"] == "GLUT1"
    assert payload["rows"][2]["target_blocked_for_promotion_ids"] == "AQP1"
    assert payload["rows"][2]["primary_blocker_target_id"] == "AQP1"
    assert payload["rows"][2]["primary_blocker_packet_step"] == "core_binder_01"
    assert payload["rows"][2]["primary_blocker_candidate_name"] == "bacopaside II"
    assert "blocked transporter target promotion" in payload["rows"][2]["target_scope_guardrail"]
    assert payload["operator_completion_packets"][2]["target_scope_completion_packet"][
        "target_blocked_for_promotion_ids"
    ] == ["AQP1"]
    assert payload["rows"][3]["next_review_row_id"] == "pxr_review_d603772038dff21e"
    assert "target_match_confirmed" in payload["rows"][3]["required_exact_evidence_fields"]
    assert "conflict_resolution_decision" in payload["rows"][3]["required_exact_evidence_fields"]
    assert "human_NR1I2_PXR_target_match_required" in payload["rows"][3]["required_claim_guardrails"]
    assert "activity-proxy conflict" in payload["rows"][3]["claim_safe_completion_rule"]
    assert "pxr_authoritative_reconciliation_packet_current.json" in payload["rows"][3][
        "return_bundle_required_artifacts"
    ]
    assert payload["rows"][4]["first_blocked_stage_id"] == "transporter_claim_acceptance"
    assert payload["rows"][4]["first_blocked_evidence_row_id"] == "AQP1.core_binder_01"
    assert payload["rows"][4]["first_blocked_target_id"] == "AQP1"
    assert payload["rows"][4]["first_blocked_required_missing_fields"] == (
        "replacement_reference_binding_kcal_mol"
    )
    assert payload["rows"][4]["blocked_stage_evidence_count"] == 4
    assert payload["rows"][4]["blocked_stage_dependency_matrix_count"] == 2
    assert "pxr_claim_acceptance" in payload["rows"][4]["blocked_stage_dependency_stage_ids"]
    assert "pxr_domain_promotion" in payload["rows"][4][
        "blocked_stage_dependency_unlock_claim_scopes"
    ]
    assert "general_platform_claim_allowed_false" in payload["rows"][4][
        "required_claim_guardrails"
    ]
    assert "general protein-ligand platform wording blocked" in payload["rows"][4][
        "claim_safe_completion_rule"
    ]
    assert payload["operator_completion_packets"][1]["operator_completion_packet"]["template_payload"]["queue_rows"] == 768
    assert payload["summary"]["execution_enabled"] is False
    assert payload["summary"]["checkpoint_promoted"] is False


def test_build_product_commercial_readiness_operator_packet_tool_writes_outputs(tmp_path: Path) -> None:
    goal_audit = tmp_path / "goal_audit.json"
    delta_force_closure = tmp_path / "delta_force_closure.json"
    scope_closure = tmp_path / "scope_closure.json"
    out_json = tmp_path / "operator_packet.json"
    out_csv = tmp_path / "operator_packet.csv"
    out_md = tmp_path / "operator_packet.md"
    goal_audit.write_text(json.dumps(_goal_audit()) + "\n", encoding="utf-8")
    delta_force_closure.write_text(
        json.dumps({"summary": {"packet_ready": True, "next_stage_id": "gpu_worker_return_receipt"}}) + "\n",
        encoding="utf-8",
    )
    scope_closure.write_text(
        json.dumps({"summary": {"packet_ready": True, "scope_acceptance_next_stage_id": "transporter_claim_acceptance"}})
        + "\n",
        encoding="utf-8",
    )

    mod.main(
        [
            "--goal-audit-json",
            str(goal_audit),
            "--delta-force-closure-packet-json",
            str(delta_force_closure),
            "--scope-closure-packet-json",
            str(scope_closure),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_ready"] is True
    assert len(payload["summary"]["goal_audit_sha256"]) == 64
    assert len(payload["summary"]["commercial_readiness_matrix_sha256"]) == 64
    assert payload["summary"]["source_fingerprint_ready"] is True
    assert payload["summary"]["delta_force_closure_acceptance_packet_ready"] is True
    assert payload["summary"]["scope_closure_acceptance_packet_ready"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("action_id,status,gap_id,")
    md_text = out_md.read_text(encoding="utf-8")
    assert "Product Commercial Readiness Operator Packet" in md_text
    assert "commercial_readiness_matrix_sha256" in md_text
    assert "First Operator Completion Packet" in md_text
    assert "rocm_environment_manifest_json" in md_text
    assert "production_ai_return_summary" in md_text
    assert "product_scope_breadth_evidence_receipt_current.json" in md_text
    assert "Delta Force Closure Acceptance" in md_text
    assert "Scope Closure Acceptance" in md_text
