from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_commercial_readiness_execution_ladder as mod


def _operator_packet() -> dict:
    return {
        "summary": {
            "packet_ready": True,
            "goal_complete": False,
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
        },
        "rows": [
            {
                "action_id": "production_gpu_execution_environment",
                "status": "blocked",
                "gap_id": "production_ai_inference_checkpoint",
                "release_blocker": True,
                "artifact": "runs/rocm_environment_manifest_current.json",
                "required_operator_inputs": (
                    "manifest_ready;rocm_stack_detected;torch_rocm_ready;"
                    "amd_gpu_detected;visible_device_count"
                ),
                "execution_command": "python3 tools/build_rocm_environment_manifest.py",
                "validation_command": "python3 tools/build_rocm_environment_manifest.py",
                "unlock_claim": "production_ai_full_gpu_regeneration_authority",
                "next_action": "Expose an AMD ROCm/HIP device to PyTorch.",
                "workstream_lane_id": "primary_gpu_environment",
                "operator_completion_worker_runtime_receipt_contract_ready": True,
                "operator_completion_worker_runtime_receipt_required_fields_or_columns": (
                    "manifest_ready;torch_rocm_ready;amd_gpu_detected;"
                    "visible_device_count;backend_counts"
                ),
                "operator_completion_worker_runtime_receipt_required_field_count": 5,
                "operator_completion_worker_runtime_receipt_completion_rule": (
                    "manifest_ready=true; torch_rocm_ready=true; visible_device_count>0"
                ),
                "operator_completion_worker_runtime_receipt_post_environment_next_stage_id": (
                    "gpu_return_acceptance"
                ),
                "operator_completion_worker_runtime_receipt_post_environment_next_artifact": (
                    "runs/residual_force_gpu_worker_return_receipt_current.json"
                ),
                "operator_completion_worker_runtime_receipt_post_environment_validation_command": (
                    "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                ),
                "operator_completion_worker_runtime_receipt_full_regeneration_command": (
                    "python3 tools/generate_ligand_trajectory_engine.py --prod-mode"
                ),
                "operator_completion_worker_runtime_receipt_guardrails": (
                    "cpu_fallback_does_not_satisfy_production_inference"
                ),
                "operator_completion_diagnostic_commands": (
                    "python3 tools/build_rocm_environment_manifest.py;"
                    "rocminfo;"
                    "python3 -c \"import torch; print(torch.cuda.device_count())\""
                ),
                "operator_completion_diagnostic_command_count": 3,
                "operator_completion_diagnostic_required_fields": (
                    "torch_rocm_ready;visible_device_count;device_names"
                ),
                "operator_completion_diagnostic_required_field_count": 3,
                "operator_completion_diagnostic_completion_rule": (
                    "torch_rocm_ready=true; visible_device_count>0; device_names nonempty"
                ),
                "operator_completion_diagnostic_return_artifacts": (
                    "runs/rocm_environment_manifest_current.json"
                ),
                "operator_completion_torch_visibility_probe_command": (
                    "python3 -c \"import torch; print(torch.cuda.device_count())\""
                ),
                "parallelizable_with_primary_blocker": False,
                "parallel_lane_priority": 0,
            },
            {
                "action_id": "production_ai_return_summary",
                "status": "blocked",
                "gap_id": "production_ai_inference_checkpoint",
                "release_blocker": True,
                "artifact": "runs/residual_force_trajectory_regeneration_current_summary.json",
                "required_operator_inputs": "queue_rows;processed_rows;ok_rows",
                "required_evidence": (
                    "queue_rows equals expected_queue_rows; processed_rows>=expected_queue_rows"
                ),
                "execution_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",
                "validation_command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                "unlock_claim": "production_ai_inference_subject",
                "next_action": "Return the completed GPU summary JSON.",
                "workstream_lane_id": "gpu_return_after_environment",
                "parallelizable_with_primary_blocker": False,
                "parallel_lane_precondition": "production_gpu_execution_environment_ready",
                "parallel_lane_priority": 0,
                "blocked_by_action_id": "production_gpu_execution_environment",
                "return_bundle_required_artifact_count": 4,
                "return_bundle_required_artifacts": (
                    "runs/residual_force_trajectory_regeneration_current_summary.json;"
                    "runs/residual_force_trajectory_regeneration_current_manifest.csv"
                ),
                "return_bundle_next_artifact_id": "returned_summary_json",
                "return_bundle_next_artifact_path": (
                    "runs/residual_force_trajectory_regeneration_current_summary.json"
                ),
                "return_bundle_next_artifact_failed_check_ids": (
                    "actual_summary_returned_complete"
                ),
                "return_bundle_manifest_required_columns": (
                    "queue_id;operator_verified_npz_exists"
                ),
                "return_bundle_post_return_validation_command": (
                    "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                ),
                "return_bundle_guardrail": (
                    "Returned summary alone does not unlock production AI."
                ),
            },
            {
                "action_id": "transporter_next_slot_exact_evidence",
                "status": "blocked",
                "gap_id": "scope_breadth_expansion",
                "release_blocker": True,
                "artifact": "runs/transporter_manual_review_intake_template_current.csv",
                "required_operator_inputs": "target_id;candidate_ligand_id;reference_binding_kcal_mol",
                "required_exact_evidence_fields": (
                    "target_id;direct_binding_or_claim_safe_kcal_basis;reference_binding_kcal_mol;"
                    "target_match_decision"
                ),
                "required_claim_guardrails": (
                    "functional_surrogate_does_not_authorize_direct_binding_claim;"
                    "reference_split_meta_rows_must_be_synchronized_before_promotion"
                ),
                "expected_evidence_type": "direct_or_claim_safe_binding_kcal",
                "required_missing_fields": "replacement_reference_binding_kcal_mol",
                "operator_review_artifact": "runs/transporter_manual_review_intake_template_current.csv",
                "post_intake_synchronization_targets": (
                    "config/ligand_binding_reference_blind_aqp1_v1.csv;"
                    "config/ligand_eval_splits_blind_aqp1_v1.csv"
                ),
                "acceptance_gate_commands": (
                    "python3 tools/build_transporter_binder_promotion_gate.py;"
                    "python3 tools/build_product_scope_breadth_contract.py"
                ),
                "next_slot_source_modality_guard_ready": True,
                "next_slot_source_modality": "functional_quantitative_surrogate",
                "next_slot_source_modality_claim_safe": False,
                "next_slot_source_modality_direct_binding_claim_allowed": False,
                "next_slot_source_modality_decision": (
                    "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
                ),
                "next_slot_source_modality_guardrails": (
                    "functional_quantitative_surrogate_is_review_only;"
                    "direct_binding_claim_requires_exact_target_pair_source"
                ),
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
                "direct_binding_procurement_packet_ready": True,
                "direct_binding_procurement_packet_status": (
                    "aqp1_direct_binding_procurement_packet_ready"
                ),
                "direct_binding_procurement_packet_artifact": (
                    "runs/aqp1_direct_binding_procurement_packet_current.json"
                ),
                "direct_binding_procurement_direct_binding_gap_open": True,
                "direct_binding_procurement_external_primary_evidence_required": True,
                "direct_binding_procurement_first_required_external_action_id": (
                    "procure_aqp1_bacopaside_ii_direct_binding_measurement"
                ),
                "direct_binding_procurement_current_operator_candidate_blocker": (
                    "data_validity_outside_typical_range_and_assay_origin_unknown"
                ),
                "direct_binding_procurement_minimum_acceptance_rule": (
                    "target_uniprot=P29972; standard_type in Kd,Ki; operator_claim_safe_decision=approve_claim_safe"
                ),
                "direct_binding_procurement_accepted_direct_binding_methods": (
                    "SPR equilibrium Kd;ITC Kd"
                ),
                "direct_binding_procurement_acceptance_fields": (
                    "target_uniprot;standard_value_nM;operator_claim_safe_decision"
                ),
                "execution_command": "python3 tools/build_product_scope_breadth_contract.py",
                "validation_command": "python3 tools/build_product_scope_breadth_contract.py",
                "unlock_claim": "transporter_domain_promotion",
                "next_action": "Acquire exact transporter evidence.",
                "workstream_lane_id": "parallel_scope_evidence",
                "parallelizable_with_primary_blocker": True,
                "parallel_lane_precondition": (
                    "Can be completed while ROCm/GPU environment is being prepared."
                ),
                "parallel_lane_priority": 1,
                "parallel_primary_blocker_action_id": "production_gpu_execution_environment",
            },
        ],
    }


def _freshness(ready: bool = True) -> dict:
    return {
        "summary": {
            "freshness_ready": ready,
        }
    }


def test_product_commercial_readiness_execution_ladder_orders_fresh_actions() -> None:
    payload = mod.build_product_commercial_readiness_execution_ladder(
        operator_packet=_operator_packet(),
        freshness_packet=_freshness(),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_commercial_readiness_execution_ladder_ready"
    assert summary["ladder_ready"] is True
    assert summary["operator_packet_ready"] is True
    assert summary["freshness_ready"] is True
    assert summary["action_count"] == 3
    assert summary["blocked_action_count"] == 3
    assert summary["parallelizable_action_count"] == 1
    assert summary["parallelizable_action_ids"] == ["transporter_next_slot_exact_evidence"]
    assert summary["first_parallelizable_action_id"] == "transporter_next_slot_exact_evidence"
    assert summary["first_parallelizable_action_order"] == 3
    assert summary["first_parallelizable_action_lane_id"] == "parallel_scope_evidence"
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
    assert summary[
        "first_parallelizable_action_direct_binding_procurement_first_required_external_action_id"
    ] == "procure_aqp1_bacopaside_ii_direct_binding_measurement"
    assert summary[
        "first_parallelizable_action_direct_binding_procurement_external_primary_evidence_required"
    ] is True
    assert "standard_type in Kd,Ki" in summary[
        "first_parallelizable_action_direct_binding_procurement_minimum_acceptance_rule"
    ]
    assert summary["first_execution_order"] == 1
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
        "first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id"
    ] == "gpu_return_acceptance"
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
    assert payload["rows"][0]["operator_completion_worker_runtime_receipt_contract_ready"] is True
    assert "visible_device_count" in payload["rows"][0][
        "operator_completion_worker_runtime_receipt_required_fields_or_columns"
    ]
    assert payload["rows"][0]["operator_completion_diagnostic_command_count"] == 3
    assert "torch.cuda.device_count" in payload["rows"][0][
        "operator_completion_torch_visibility_probe_command"
    ]
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
    assert "actual_summary_returned_complete" in summary[
        "production_ai_return_bundle_next_artifact_failed_check_ids"
    ]
    assert "operator_verified_npz_exists" in summary[
        "production_ai_return_bundle_manifest_required_columns"
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
    assert summary[
        "production_ai_registry_promotion_operator_receipt_approval_token_required"
    ] == "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
    assert summary[
        "production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker"
    ] == "operator_placeholders_unfilled"
    assert summary[
        "production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode"
    ] == "shadow"
    assert summary[
        "production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count"
    ] == 0
    assert summary["all_preconditions_satisfied"] is True
    assert payload["rows"][1]["post_validation_rebuild_command"].endswith(
        "python3 tools/build_product_goal_completion_audit.py"
    )
    assert payload["rows"][1]["return_bundle_next_artifact_id"] == "returned_summary_json"
    assert "operator_verified_npz_exists" in payload["rows"][1][
        "return_bundle_manifest_required_columns"
    ]
    assert payload["rows"][2]["operator_input_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert "target_match_decision" in payload["rows"][2]["required_exact_evidence_fields"]
    assert "functional_surrogate_does_not_authorize_direct_binding_claim" in payload["rows"][2][
        "required_claim_guardrails"
    ]
    assert payload["rows"][2]["operator_review_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert "build_product_scope_breadth_contract.py" in payload["rows"][2]["acceptance_gate_commands"]
    assert payload["rows"][2]["next_slot_source_modality"] == "functional_quantitative_surrogate"
    assert payload["rows"][2]["next_slot_source_modality_direct_binding_claim_allowed"] is False
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
    assert payload["rows"][2]["parallelizable_with_primary_blocker"] is True
    assert payload["rows"][2]["parallel_primary_blocker_action_id"] == (
        "production_gpu_execution_environment"
    )
    assert payload["summary"]["execution_enabled"] is False
    assert payload["summary"]["checkpoint_promoted"] is False


def test_product_commercial_readiness_execution_ladder_blocks_when_freshness_is_stale() -> None:
    payload = mod.build_product_commercial_readiness_execution_ladder(
        operator_packet=_operator_packet(),
        freshness_packet=_freshness(False),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_commercial_readiness_execution_ladder"
    assert summary["ladder_ready"] is False
    assert summary["freshness_ready"] is False
    assert summary["all_preconditions_satisfied"] is False
    assert summary["next_required_step"].startswith("Rebuild the commercial-readiness operator packet")
    assert payload["rows"][0]["precondition_satisfied"] is False


def test_product_commercial_readiness_execution_ladder_tool_writes_outputs(tmp_path: Path) -> None:
    operator_path = tmp_path / "operator.json"
    freshness_path = tmp_path / "freshness.json"
    out_json = tmp_path / "ladder.json"
    out_csv = tmp_path / "ladder.csv"
    out_md = tmp_path / "ladder.md"
    operator_path.write_text(json.dumps(_operator_packet()) + "\n", encoding="utf-8")
    freshness_path.write_text(json.dumps(_freshness()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--operator-packet-json",
            str(operator_path),
            "--freshness-json",
            str(freshness_path),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["ladder_ready"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("execution_order,action_id,")
    md_text = out_md.read_text(encoding="utf-8")
    assert "Product Commercial Readiness Execution Ladder" in md_text
    assert "production_ai_return_summary" in md_text
