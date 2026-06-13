from __future__ import annotations

from typing import Any


def commercial_production_ai_return_fields(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "production_ai_return_action_id": summary.get("production_ai_return_action_id", ""),
        "production_ai_return_action_artifact": summary.get(
            "production_ai_return_action_artifact", ""
        ),
        "production_ai_return_action_next_action": summary.get(
            "production_ai_return_action_next_action", ""
        ),
        "production_ai_return_action_execution_command": summary.get(
            "production_ai_return_action_execution_command", ""
        ),
        "production_ai_return_action_validation_command": summary.get(
            "production_ai_return_action_validation_command", ""
        ),
        "production_ai_return_action_blocked_by_action_id": summary.get(
            "production_ai_return_action_blocked_by_action_id", ""
        ),
        "production_ai_return_action_required_operator_inputs": summary.get(
            "production_ai_return_action_required_operator_inputs", ""
        ),
        "production_ai_return_action_required_evidence": summary.get(
            "production_ai_return_action_required_evidence", ""
        ),
        "production_ai_return_operator_completion_packet_ready": bool(
            summary.get("production_ai_return_operator_completion_packet_ready") is True
        ),
        "production_ai_return_operator_completion_artifact_id": summary.get(
            "production_ai_return_operator_completion_artifact_id", ""
        ),
        "production_ai_return_operator_completion_artifact_path": summary.get(
            "production_ai_return_operator_completion_artifact_path", ""
        ),
        "production_ai_return_operator_completion_required_fields_or_columns": list(
            summary.get("production_ai_return_operator_completion_required_fields_or_columns")
            or []
        ),
        "production_ai_return_operator_completion_expected_queue_rows": int(
            summary.get("production_ai_return_operator_completion_expected_queue_rows") or 0
        ),
        "production_ai_return_operator_completion_completion_rule": summary.get(
            "production_ai_return_operator_completion_completion_rule", ""
        ),
        "production_ai_return_operator_completion_backend_provenance_completion_rule": summary.get(
            "production_ai_return_operator_completion_backend_provenance_completion_rule", ""
        ),
        "production_ai_return_bundle_required_artifact_count": int(
            summary.get("production_ai_return_bundle_required_artifact_count") or 0
        ),
        "production_ai_return_bundle_required_artifacts": list(
            summary.get("production_ai_return_bundle_required_artifacts") or []
        ),
        "production_ai_return_bundle_next_artifact_id": summary.get(
            "production_ai_return_bundle_next_artifact_id", ""
        ),
        "production_ai_return_bundle_next_artifact_path": summary.get(
            "production_ai_return_bundle_next_artifact_path", ""
        ),
        "production_ai_return_bundle_next_artifact_failed_check_ids": list(
            summary.get("production_ai_return_bundle_next_artifact_failed_check_ids") or []
        ),
        "production_ai_return_bundle_manifest_required_columns": list(
            summary.get("production_ai_return_bundle_manifest_required_columns") or []
        ),
        "production_ai_return_bundle_post_return_validation_command": summary.get(
            "production_ai_return_bundle_post_return_validation_command", ""
        ),
        "production_ai_return_bundle_guardrail": summary.get(
            "production_ai_return_bundle_guardrail", ""
        ),
    }


def commercial_production_ai_registry_promotion_fields(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "production_ai_registry_promotion_action_id": summary.get(
            "production_ai_registry_promotion_action_id", ""
        ),
        "production_ai_registry_promotion_action_artifact": summary.get(
            "production_ai_registry_promotion_action_artifact", ""
        ),
        "production_ai_registry_promotion_action_next_action": summary.get(
            "production_ai_registry_promotion_action_next_action", ""
        ),
        "production_ai_registry_promotion_action_validation_command": summary.get(
            "production_ai_registry_promotion_action_validation_command", ""
        ),
        "production_ai_registry_promotion_action_blocked_by_action_id": summary.get(
            "production_ai_registry_promotion_action_blocked_by_action_id", ""
        ),
        "production_ai_registry_promotion_action_required_operator_inputs": summary.get(
            "production_ai_registry_promotion_action_required_operator_inputs", ""
        ),
        "production_ai_registry_promotion_action_required_evidence": summary.get(
            "production_ai_registry_promotion_action_required_evidence", ""
        ),
        "production_ai_registry_promotion_operator_completion_packet_ready": bool(
            summary.get("production_ai_registry_promotion_operator_completion_packet_ready") is True
        ),
        "production_ai_registry_promotion_operator_completion_packet_keys": list(
            summary.get("production_ai_registry_promotion_operator_completion_packet_keys")
            or []
        ),
        "production_ai_registry_promotion_operator_completion_artifact_id": summary.get(
            "production_ai_registry_promotion_operator_completion_artifact_id", ""
        ),
        "production_ai_registry_promotion_operator_completion_artifact_path": summary.get(
            "production_ai_registry_promotion_operator_completion_artifact_path", ""
        ),
        "production_ai_registry_promotion_operator_completion_required_fields_or_columns": list(
            summary.get(
                "production_ai_registry_promotion_operator_completion_required_fields_or_columns"
            )
            or []
        ),
        "production_ai_registry_promotion_operator_completion_diagnostic_commands": list(
            summary.get("production_ai_registry_promotion_operator_completion_diagnostic_commands")
            or []
        ),
        "production_ai_registry_promotion_operator_completion_diagnostic_command_count": int(
            summary.get(
                "production_ai_registry_promotion_operator_completion_diagnostic_command_count"
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_completion_completion_rule": summary.get(
            "production_ai_registry_promotion_operator_completion_completion_rule", ""
        ),
        "production_ai_registry_promotion_operator_completion_failed_check_ids": list(
            summary.get("production_ai_registry_promotion_operator_completion_failed_check_ids")
            or []
        ),
        "production_ai_registry_promotion_operator_completion_packet": dict(
            summary.get("production_ai_registry_promotion_operator_completion_packet") or {}
        ),
        "production_ai_registry_promotion_operator_receipt_artifact": summary.get(
            "production_ai_registry_promotion_operator_receipt_artifact", ""
        ),
        "production_ai_registry_promotion_operator_receipt_status": summary.get(
            "production_ai_registry_promotion_operator_receipt_status", ""
        ),
        "production_ai_registry_promotion_operator_receipt_ready": bool(
            summary.get("production_ai_registry_promotion_operator_receipt_ready") is True
        ),
        "production_ai_registry_promotion_operator_receipt_present": bool(
            summary.get("production_ai_registry_promotion_operator_receipt_present") is True
        ),
        "production_ai_registry_promotion_operator_receipt_csv": summary.get(
            "production_ai_registry_promotion_operator_receipt_csv", ""
        ),
        "production_ai_registry_promotion_operator_receipt_row_count": int(
            summary.get("production_ai_registry_promotion_operator_receipt_row_count") or 0
        ),
        "production_ai_registry_promotion_operator_receipt_blocker_count": int(
            summary.get("production_ai_registry_promotion_operator_receipt_blocker_count") or 0
        ),
        "production_ai_registry_promotion_operator_receipt_blocked_row_count": int(
            summary.get("production_ai_registry_promotion_operator_receipt_blocked_row_count") or 0
        ),
        "production_ai_registry_promotion_operator_receipt_blockers": list(
            summary.get("production_ai_registry_promotion_operator_receipt_blockers") or []
        ),
        "production_ai_registry_promotion_operator_receipt_first_blocked_artifact_id": summary.get(
            "production_ai_registry_promotion_operator_receipt_first_blocked_artifact_id", ""
        ),
        "production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker": summary.get(
            "production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker", ""
        ),
        "production_ai_registry_promotion_operator_receipt_first_blocked_row_blockers": list(
            summary.get(
                "production_ai_registry_promotion_operator_receipt_first_blocked_row_blockers"
            )
            or []
        ),
        "production_ai_registry_promotion_operator_receipt_most_common_row_blocker": summary.get(
            "production_ai_registry_promotion_operator_receipt_most_common_row_blocker", ""
        ),
        "production_ai_registry_promotion_operator_receipt_approval_token_required": summary.get(
            "production_ai_registry_promotion_operator_receipt_approval_token_required", ""
        ),
        "production_ai_registry_promotion_operator_receipt_next_required_step": summary.get(
            "production_ai_registry_promotion_operator_receipt_next_required_step", ""
        ),
        "production_ai_registry_promotion_operator_receipt_registry_artifact": summary.get(
            "production_ai_registry_promotion_operator_receipt_registry_artifact", ""
        ),
        "production_ai_registry_promotion_operator_receipt_checkpoint_readiness_artifact": summary.get(
            "production_ai_registry_promotion_operator_receipt_checkpoint_readiness_artifact",
            "",
        ),
        "production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode": summary.get(
            "production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode",
            "",
        ),
        "production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count": int(
            summary.get(
                "production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count"
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_currently_satisfied": bool(
            summary.get(
                "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_currently_satisfied"
            )
            is True
        ),
        "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_missing_gate_ids": list(
            summary.get(
                "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_missing_gate_ids"
            )
            or []
        ),
        "production_ai_registry_promotion_operator_receipt_registry_edited_by_this_tool": bool(
            summary.get(
                "production_ai_registry_promotion_operator_receipt_registry_edited_by_this_tool"
            )
            is True
        ),
        "production_ai_registry_promotion_operator_receipt_checkpoint_created_by_this_tool": bool(
            summary.get(
                "production_ai_registry_promotion_operator_receipt_checkpoint_created_by_this_tool"
            )
            is True
        ),
        "production_ai_registry_promotion_priority_artifact": summary.get(
            "production_ai_registry_promotion_priority_artifact", ""
        ),
        "production_ai_registry_promotion_priority_status": summary.get(
            "production_ai_registry_promotion_priority_status", ""
        ),
        "production_ai_registry_promotion_priority_packet_ready": bool(
            summary.get("production_ai_registry_promotion_priority_packet_ready") is True
        ),
        "production_ai_registry_promotion_priority_registry_promotion_ready": bool(
            summary.get("production_ai_registry_promotion_priority_registry_promotion_ready")
            is True
        ),
        "production_ai_registry_promotion_priority_operator_input_required_count": int(
            summary.get("production_ai_registry_promotion_priority_operator_input_required_count")
            or 0
        ),
        "production_ai_registry_promotion_priority_blocked_priority_item_count": int(
            summary.get("production_ai_registry_promotion_priority_blocked_priority_item_count")
            or 0
        ),
        "production_ai_registry_promotion_priority_missing_gate_count": int(
            summary.get("production_ai_registry_promotion_priority_missing_gate_count") or 0
        ),
        "production_ai_registry_promotion_priority_missing_gate_ids": list(
            summary.get("production_ai_registry_promotion_priority_missing_gate_ids") or []
        ),
        "production_ai_registry_promotion_priority_top_gate_id": summary.get(
            "production_ai_registry_promotion_priority_top_gate_id", ""
        ),
        "production_ai_registry_promotion_priority_top_priority_bucket": summary.get(
            "production_ai_registry_promotion_priority_top_priority_bucket", ""
        ),
        "production_ai_registry_promotion_priority_top_required_input": summary.get(
            "production_ai_registry_promotion_priority_top_required_input", ""
        ),
        "production_ai_registry_promotion_priority_top_acceptance_artifact": summary.get(
            "production_ai_registry_promotion_priority_top_acceptance_artifact", ""
        ),
        "production_ai_registry_promotion_priority_top_verification_command": summary.get(
            "production_ai_registry_promotion_priority_top_verification_command", ""
        ),
        "production_ai_registry_promotion_priority_top_next_operator_step": summary.get(
            "production_ai_registry_promotion_priority_top_next_operator_step", ""
        ),
        "production_ai_registry_promotion_priority_model_promoted": bool(
            summary.get("production_ai_registry_promotion_priority_model_promoted") is True
        ),
        "production_ai_registry_promotion_priority_customer_facing_mutation_enabled": bool(
            summary.get(
                "production_ai_registry_promotion_priority_customer_facing_mutation_enabled"
            )
            is True
        ),
        "production_ai_registry_promotion_priority_external_state_mutated": bool(
            summary.get("production_ai_registry_promotion_priority_external_state_mutated") is True
        ),
    }


def commercial_delta_force_closure_fields(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "delta_force_closure_acceptance_packet_artifact": summary.get(
            "delta_force_closure_acceptance_packet_artifact", ""
        ),
        "delta_force_closure_acceptance_packet_ready": bool(
            summary.get("delta_force_closure_acceptance_packet_ready") is True
        ),
        "delta_force_closure_ready": bool(summary.get("delta_force_closure_ready") is True),
        "delta_force_closure_first_blocked_output_field": summary.get(
            "delta_force_closure_first_blocked_output_field", ""
        ),
        "delta_force_closure_ready_output_field_count": int(
            summary.get("delta_force_closure_ready_output_field_count") or 0
        ),
        "delta_force_closure_blocked_output_field_count": int(
            summary.get("delta_force_closure_blocked_output_field_count") or 0
        ),
        "delta_force_closure_failed_stage_count": int(
            summary.get("delta_force_closure_failed_stage_count") or 0
        ),
        "delta_force_closure_failed_stage_ids": list(
            summary.get("delta_force_closure_failed_stage_ids") or []
        ),
        "delta_force_closure_next_stage_id": summary.get(
            "delta_force_closure_next_stage_id", ""
        ),
        "delta_force_closure_next_stage_artifact": summary.get(
            "delta_force_closure_next_stage_artifact", ""
        ),
        "delta_force_closure_next_stage_validation_command": summary.get(
            "delta_force_closure_next_stage_validation_command", ""
        ),
        "delta_force_closure_next_required_step": summary.get(
            "delta_force_closure_next_required_step", ""
        ),
        "delta_force_closure_operator_return_required_artifact_count": int(
            summary.get("delta_force_closure_operator_return_required_artifact_count") or 0
        ),
        "delta_force_closure_operator_return_required_artifacts": list(
            summary.get("delta_force_closure_operator_return_required_artifacts") or []
        ),
        "delta_force_closure_return_summary_required_fields": list(
            summary.get("delta_force_closure_return_summary_required_fields") or []
        ),
        "delta_force_closure_post_return_validation_command": summary.get(
            "delta_force_closure_post_return_validation_command", ""
        ),
    }


def commercial_scope_closure_fields(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope_closure_acceptance_packet_artifact": summary.get(
            "scope_closure_acceptance_packet_artifact", ""
        ),
        "scope_closure_acceptance_packet_ready": bool(
            summary.get("scope_closure_acceptance_packet_ready") is True
        ),
        "scope_closure_ready": bool(summary.get("scope_closure_ready") is True),
        "scope_closure_stage_count": int(summary.get("scope_closure_stage_count") or 0),
        "scope_closure_blocked_stage_count": int(
            summary.get("scope_closure_blocked_stage_count") or 0
        ),
        "scope_closure_blocked_stage_ids": list(
            summary.get("scope_closure_blocked_stage_ids") or []
        ),
        "scope_closure_next_stage_id": summary.get("scope_closure_next_stage_id", ""),
        "scope_closure_next_stage_artifact": summary.get(
            "scope_closure_next_stage_artifact", ""
        ),
        "scope_closure_next_stage_validation_command": summary.get(
            "scope_closure_next_stage_validation_command", ""
        ),
        "scope_closure_first_blocked_evidence_row_id": summary.get(
            "scope_closure_first_blocked_evidence_row_id", ""
        ),
        "scope_closure_first_blocked_target_id": summary.get(
            "scope_closure_first_blocked_target_id", ""
        ),
        "scope_closure_first_blocked_candidate": summary.get(
            "scope_closure_first_blocked_candidate", ""
        ),
        "scope_closure_first_blocked_required_missing_fields": summary.get(
            "scope_closure_first_blocked_required_missing_fields", ""
        ),
        "scope_closure_transporter_unresolved_slot_count": int(
            summary.get("scope_closure_transporter_unresolved_slot_count") or 0
        ),
        "scope_closure_pxr_direct_or_claim_safe_quantitative_ready_count": int(
            summary.get("scope_closure_pxr_direct_or_claim_safe_quantitative_ready_count") or 0
        ),
        "scope_closure_general_platform_claim_allowed": bool(
            summary.get("scope_closure_general_platform_claim_allowed") is True
        ),
        "scope_closure_next_required_step": summary.get(
            "scope_closure_next_required_step", ""
        ),
    }


def commercial_scope_breadth_evidence_receipt_fields(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_scope_breadth_evidence_receipt_status": summary.get(
            "product_scope_breadth_evidence_receipt_status", ""
        ),
        "product_scope_breadth_evidence_receipt_ready": bool(
            summary.get("product_scope_breadth_evidence_receipt_ready") is True
        ),
        "product_scope_breadth_evidence_receipt_blocker_count": int(
            summary.get("product_scope_breadth_evidence_receipt_blocker_count") or 0
        ),
        "product_scope_breadth_evidence_receipt_blocked_row_count": int(
            summary.get("product_scope_breadth_evidence_receipt_blocked_row_count") or 0
        ),
        "product_scope_breadth_evidence_receipt_required_scope_blocker_count": int(
            summary.get("product_scope_breadth_evidence_receipt_required_scope_blocker_count")
            or 0
        ),
        "product_scope_breadth_evidence_receipt_artifact": summary.get(
            "product_scope_breadth_evidence_receipt_artifact", ""
        ),
        "product_scope_breadth_evidence_receipt_csv": summary.get(
            "product_scope_breadth_evidence_receipt_csv", ""
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id": summary.get(
            "product_scope_breadth_evidence_receipt_first_blocked_scope_blocker_id", ""
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact": summary.get(
            "product_scope_breadth_evidence_receipt_first_blocked_evidence_artifact", ""
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status": summary.get(
            "product_scope_breadth_evidence_receipt_first_blocked_expected_evidence_status",
            "",
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status": summary.get(
            "product_scope_breadth_evidence_receipt_first_blocked_observed_evidence_status",
            "",
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_missing_true_fields": list(
            summary.get(
                "product_scope_breadth_evidence_receipt_first_blocked_missing_true_fields"
            )
            or []
        ),
        "product_scope_breadth_evidence_receipt_first_blocked_row_blockers": list(
            summary.get("product_scope_breadth_evidence_receipt_first_blocked_row_blockers")
            or []
        ),
        "product_scope_breadth_evidence_receipt_most_common_row_blocker": summary.get(
            "product_scope_breadth_evidence_receipt_most_common_row_blocker", ""
        ),
    }


def commercial_engine_refinement_claim_fields(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "engine_refinement_claim_promotion_ready": bool(
            summary.get("engine_refinement_claim_promotion_ready") is True
        ),
        "engine_refinement_claim_promotion_blocker_count": int(
            summary.get("engine_refinement_claim_promotion_blocker_count") or 0
        ),
        "engine_refinement_claim_promotion_action_row_count": int(
            summary.get("engine_refinement_claim_promotion_action_row_count") or 0
        ),
        "engine_refinement_claim_promotion_blockers": list(
            summary.get("engine_refinement_claim_promotion_blockers") or []
        ),
        "engine_refinement_claim_promotion_action_board_csv": summary.get(
            "engine_refinement_claim_promotion_action_board_csv", ""
        ),
        "engine_refinement_claim_evidence_receipt_ready": bool(
            summary.get("engine_refinement_claim_evidence_receipt_ready") is True
        ),
        "engine_refinement_claim_evidence_receipt_status": summary.get(
            "engine_refinement_claim_evidence_receipt_status", ""
        ),
        "engine_refinement_claim_evidence_receipt_blocked_row_count": int(
            summary.get("engine_refinement_claim_evidence_receipt_blocked_row_count") or 0
        ),
        "engine_refinement_claim_evidence_receipt_artifact": summary.get(
            "engine_refinement_claim_evidence_receipt_artifact", ""
        ),
        "engine_refinement_claim_evidence_receipt_csv": summary.get(
            "engine_refinement_claim_evidence_receipt_csv", ""
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_blocker_id": summary.get(
            "engine_refinement_claim_evidence_receipt_first_blocked_blocker_id", ""
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact": summary.get(
            "engine_refinement_claim_evidence_receipt_first_blocked_evidence_artifact", ""
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status": summary.get(
            "engine_refinement_claim_evidence_receipt_first_blocked_expected_evidence_status",
            "",
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status": summary.get(
            "engine_refinement_claim_evidence_receipt_first_blocked_observed_evidence_status",
            "",
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields": list(
            summary.get(
                "engine_refinement_claim_evidence_receipt_first_blocked_missing_true_fields"
            )
            or []
        ),
        "engine_refinement_claim_evidence_receipt_first_blocked_row_blockers": list(
            summary.get("engine_refinement_claim_evidence_receipt_first_blocked_row_blockers")
            or []
        ),
        "engine_refinement_claim_evidence_receipt_most_common_row_blocker": summary.get(
            "engine_refinement_claim_evidence_receipt_most_common_row_blocker", ""
        ),
        "engine_refinement_claim_promotion_next_required_step": summary.get(
            "engine_refinement_claim_promotion_next_required_step", ""
        ),
    }


def commercial_handoff_closure_acceptance_fields(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        **commercial_delta_force_closure_fields(summary),
        **commercial_scope_closure_fields(summary),
    }


def commercial_first_worker_runtime_receipt_fields(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "first_operator_completion_worker_runtime_receipt_contract_ready": bool(
            summary.get("first_operator_completion_worker_runtime_receipt_contract_ready")
            is True
        ),
        "first_operator_completion_worker_runtime_receipt_contract": dict(
            summary.get("first_operator_completion_worker_runtime_receipt_contract") or {}
        ),
        "first_operator_completion_worker_runtime_receipt_required_fields_or_columns": list(
            summary.get(
                "first_operator_completion_worker_runtime_receipt_required_fields_or_columns"
            )
            or []
        ),
        "first_operator_completion_worker_runtime_receipt_required_field_count": int(
            summary.get(
                "first_operator_completion_worker_runtime_receipt_required_field_count"
            )
            or 0
        ),
        "first_operator_completion_worker_runtime_receipt_completion_rule": summary.get(
            "first_operator_completion_worker_runtime_receipt_completion_rule", ""
        ),
        "first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id": summary.get(
            "first_operator_completion_worker_runtime_receipt_post_environment_next_stage_id",
            "",
        ),
        "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact": summary.get(
            "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact",
            "",
        ),
        "first_operator_completion_worker_runtime_receipt_post_environment_validation_command": summary.get(
            "first_operator_completion_worker_runtime_receipt_post_environment_validation_command",
            "",
        ),
        "first_operator_completion_worker_runtime_receipt_full_regeneration_command": summary.get(
            "first_operator_completion_worker_runtime_receipt_full_regeneration_command",
            "",
        ),
        "first_operator_completion_worker_runtime_receipt_guardrails": list(
            summary.get("first_operator_completion_worker_runtime_receipt_guardrails")
            or []
        ),
        "first_operator_completion_diagnostic_commands": list(
            summary.get("first_operator_completion_diagnostic_commands") or []
        ),
        "first_operator_completion_diagnostic_command_count": int(
            summary.get("first_operator_completion_diagnostic_command_count") or 0
        ),
        "first_operator_completion_diagnostic_required_fields": list(
            summary.get("first_operator_completion_diagnostic_required_fields") or []
        ),
        "first_operator_completion_diagnostic_required_field_count": int(
            summary.get("first_operator_completion_diagnostic_required_field_count") or 0
        ),
        "first_operator_completion_diagnostic_completion_rule": summary.get(
            "first_operator_completion_diagnostic_completion_rule", ""
        ),
        "first_operator_completion_diagnostic_return_artifacts": list(
            summary.get("first_operator_completion_diagnostic_return_artifacts") or []
        ),
        "first_operator_completion_torch_visibility_probe_command": summary.get(
            "first_operator_completion_torch_visibility_probe_command", ""
        ),
    }


def commercial_first_parallelizable_source_modality_fields(summary: dict[str, Any]) -> dict[str, Any]:
    def _summary_list(key: str) -> list[str]:
        value = summary.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
        text = str(value or "").strip()
        return [part.strip() for part in text.split(";") if part.strip()] if text else []

    return {
        "first_parallelizable_action_next_slot_source_modality_guard_ready": bool(
            summary.get("first_parallelizable_action_next_slot_source_modality_guard_ready")
            is True
        ),
        "first_parallelizable_action_next_slot_source_modality": summary.get(
            "first_parallelizable_action_next_slot_source_modality", ""
        ),
        "first_parallelizable_action_next_slot_source_modality_claim_safe": bool(
            summary.get("first_parallelizable_action_next_slot_source_modality_claim_safe")
            is True
        ),
        "first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed": bool(
            summary.get(
                "first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed"
            )
            is True
        ),
        "first_parallelizable_action_next_slot_source_modality_decision": summary.get(
            "first_parallelizable_action_next_slot_source_modality_decision", ""
        ),
        "first_parallelizable_action_next_slot_source_modality_guardrails": list(
            summary.get("first_parallelizable_action_next_slot_source_modality_guardrails")
            or []
        ),
        "first_parallelizable_action_next_slot_source_modality_observed_signal": summary.get(
            "first_parallelizable_action_next_slot_source_modality_observed_signal", ""
        ),
        "first_parallelizable_action_next_slot_source_modality_required_upgrade": summary.get(
            "first_parallelizable_action_next_slot_source_modality_required_upgrade", ""
        ),
        "first_parallelizable_action_next_slot_source_modality_triage_artifact": summary.get(
            "first_parallelizable_action_next_slot_source_modality_triage_artifact", ""
        ),
        "first_parallelizable_action_next_slot_source_modality_triage_decision": summary.get(
            "first_parallelizable_action_next_slot_source_modality_triage_decision", ""
        ),
        "first_parallelizable_action_next_slot_source_modality_direct_experimental_binding_row_count": int(
            summary.get(
                "first_parallelizable_action_next_slot_source_modality_direct_experimental_binding_row_count"
            )
            or 0
        ),
        "first_parallelizable_action_next_slot_source_modality_claim_safe_binding_kcal_ready_count": int(
            summary.get(
                "first_parallelizable_action_next_slot_source_modality_claim_safe_binding_kcal_ready_count"
            )
            or 0
        ),
        "first_parallelizable_action_next_slot_source_modality_computational_binding_energy_row_count": int(
            summary.get(
                "first_parallelizable_action_next_slot_source_modality_computational_binding_energy_row_count"
            )
            or 0
        ),
        "first_parallelizable_action_next_slot_source_modality_best_computational_binding_energy_kcal_mol": summary.get(
            "first_parallelizable_action_next_slot_source_modality_best_computational_binding_energy_kcal_mol",
            "",
        ),
        "first_parallelizable_action_operator_validation_candidate_ready": bool(
            summary.get("first_parallelizable_action_operator_validation_candidate_ready")
            is True
        ),
        "first_parallelizable_action_operator_validation_candidate_status": summary.get(
            "first_parallelizable_action_operator_validation_candidate_status", ""
        ),
        "first_parallelizable_action_operator_validation_candidate_ligand_external_identifier": summary.get(
            "first_parallelizable_action_operator_validation_candidate_ligand_external_identifier",
            "",
        ),
        "first_parallelizable_action_operator_validation_candidate_reference_binding_kcal_mol": summary.get(
            "first_parallelizable_action_operator_validation_candidate_reference_binding_kcal_mol",
            "",
        ),
        "first_parallelizable_action_operator_validation_candidate_blocker": summary.get(
            "first_parallelizable_action_operator_validation_candidate_blocker", ""
        ),
        "first_parallelizable_action_operator_validation_candidate_claim_safe_ready": bool(
            summary.get(
                "first_parallelizable_action_operator_validation_candidate_claim_safe_ready"
            )
            is True
        ),
        "first_parallelizable_action_direct_binding_procurement_packet_ready": bool(
            summary.get("first_parallelizable_action_direct_binding_procurement_packet_ready")
            is True
        ),
        "first_parallelizable_action_direct_binding_procurement_packet_status": summary.get(
            "first_parallelizable_action_direct_binding_procurement_packet_status", ""
        ),
        "first_parallelizable_action_direct_binding_procurement_packet_artifact": summary.get(
            "first_parallelizable_action_direct_binding_procurement_packet_artifact", ""
        ),
        "first_parallelizable_action_direct_binding_procurement_direct_binding_gap_open": bool(
            summary.get(
                "first_parallelizable_action_direct_binding_procurement_direct_binding_gap_open"
            )
            is True
        ),
        "first_parallelizable_action_direct_binding_procurement_external_primary_evidence_required": bool(
            summary.get(
                "first_parallelizable_action_direct_binding_procurement_external_primary_evidence_required"
            )
            is True
        ),
        "first_parallelizable_action_direct_binding_procurement_first_required_external_action_id": summary.get(
            "first_parallelizable_action_direct_binding_procurement_first_required_external_action_id",
            "",
        ),
        "first_parallelizable_action_direct_binding_procurement_current_operator_candidate_blocker": summary.get(
            "first_parallelizable_action_direct_binding_procurement_current_operator_candidate_blocker",
            "",
        ),
        "first_parallelizable_action_direct_binding_procurement_minimum_acceptance_rule": summary.get(
            "first_parallelizable_action_direct_binding_procurement_minimum_acceptance_rule",
            "",
        ),
        "first_parallelizable_action_direct_binding_procurement_accepted_direct_binding_methods": _summary_list(
            "first_parallelizable_action_direct_binding_procurement_accepted_direct_binding_methods"
        ),
        "first_parallelizable_action_direct_binding_procurement_acceptance_fields": _summary_list(
            "first_parallelizable_action_direct_binding_procurement_acceptance_fields"
        ),
    }
