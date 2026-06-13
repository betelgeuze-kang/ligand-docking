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
        "production_ai_registry_promotion_priority_operator_receipt_csv": summary.get(
            "production_ai_registry_promotion_priority_operator_receipt_csv", ""
        ),
        "production_ai_registry_promotion_priority_approval_token_required": summary.get(
            "production_ai_registry_promotion_priority_approval_token_required", ""
        ),
        "production_ai_registry_promotion_priority_observed_registry_default_residual_mode": summary.get(
            "production_ai_registry_promotion_priority_observed_registry_default_residual_mode",
            "",
        ),
        "production_ai_registry_promotion_priority_observed_registry_production_promotion_allowed": bool(
            summary.get(
                "production_ai_registry_promotion_priority_observed_registry_production_promotion_allowed"
            )
            is True
        ),
        "production_ai_registry_promotion_priority_observed_registry_customer_facing_mutation_flags_ready": bool(
            summary.get(
                "production_ai_registry_promotion_priority_observed_registry_customer_facing_mutation_flags_ready"
            )
            is True
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
        "production_ai_registry_promotion_operator_field_worksheet_artifact": summary.get(
            "production_ai_registry_promotion_operator_field_worksheet_artifact", ""
        ),
        "production_ai_registry_promotion_operator_field_worksheet_status": summary.get(
            "production_ai_registry_promotion_operator_field_worksheet_status", ""
        ),
        "production_ai_registry_promotion_operator_field_worksheet_ready": bool(
            summary.get("production_ai_registry_promotion_operator_field_worksheet_ready") is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_operator_fill_complete": bool(
            summary.get(
                "production_ai_registry_promotion_operator_field_worksheet_operator_fill_complete"
            )
            is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_field_row_count": int(
            summary.get("production_ai_registry_promotion_operator_field_worksheet_field_row_count")
            or 0
        ),
        "production_ai_registry_promotion_operator_field_worksheet_required_field_count": int(
            summary.get(
                "production_ai_registry_promotion_operator_field_worksheet_required_field_count"
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_field_worksheet_pending_field_count": int(
            summary.get(
                "production_ai_registry_promotion_operator_field_worksheet_pending_field_count"
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_field_worksheet_diagnostic_required_field_count": int(
            summary.get(
                "production_ai_registry_promotion_operator_field_worksheet_diagnostic_required_field_count"
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_field_worksheet_diagnostic_pending_field_count": int(
            summary.get(
                "production_ai_registry_promotion_operator_field_worksheet_diagnostic_pending_field_count"
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_field_worksheet_pending_field_names": list(
            summary.get("production_ai_registry_promotion_operator_field_worksheet_pending_field_names")
            or []
        ),
        "production_ai_registry_promotion_operator_field_worksheet_top_gate_id": summary.get(
            "production_ai_registry_promotion_operator_field_worksheet_top_gate_id", ""
        ),
        "production_ai_registry_promotion_operator_field_worksheet_top_required_input": summary.get(
            "production_ai_registry_promotion_operator_field_worksheet_top_required_input", ""
        ),
        "production_ai_registry_promotion_operator_field_worksheet_approval_token_required": summary.get(
            "production_ai_registry_promotion_operator_field_worksheet_approval_token_required",
            "",
        ),
        "production_ai_registry_promotion_operator_field_worksheet_observed_registry_default_residual_mode": summary.get(
            "production_ai_registry_promotion_operator_field_worksheet_observed_registry_default_residual_mode",
            "",
        ),
        "production_ai_registry_promotion_operator_field_worksheet_observed_registry_trained_model_checkpoint_count": int(
            summary.get(
                "production_ai_registry_promotion_operator_field_worksheet_observed_registry_trained_model_checkpoint_count"
            )
            or 0
        ),
        "production_ai_registry_promotion_operator_field_worksheet_model_promoted": bool(
            summary.get("production_ai_registry_promotion_operator_field_worksheet_model_promoted")
            is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_customer_facing_mutation_enabled": bool(
            summary.get(
                "production_ai_registry_promotion_operator_field_worksheet_customer_facing_mutation_enabled"
            )
            is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_external_state_mutated": bool(
            summary.get(
                "production_ai_registry_promotion_operator_field_worksheet_external_state_mutated"
            )
            is True
        ),
        "production_ai_registry_promotion_operator_field_worksheet_next_required_step": summary.get(
            "production_ai_registry_promotion_operator_field_worksheet_next_required_step",
            "",
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
        "product_scope_breadth_evidence_operator_field_worksheet_artifact": summary.get(
            "product_scope_breadth_evidence_operator_field_worksheet_artifact", ""
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_status": summary.get(
            "product_scope_breadth_evidence_operator_field_worksheet_status", ""
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_ready": bool(
            summary.get("product_scope_breadth_evidence_operator_field_worksheet_ready")
            is True
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_operator_fill_complete": bool(
            summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_operator_fill_complete"
            )
            is True
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_field_row_count": int(
            summary.get("product_scope_breadth_evidence_operator_field_worksheet_field_row_count")
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_required_receipt_field_count": int(
            summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_required_receipt_field_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_pending_field_count": int(
            summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_pending_field_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_blocker_id": summary.get(
            "product_scope_breadth_evidence_operator_field_worksheet_top_blocker_id", ""
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_blocker_pending_field_count": int(
            summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_top_blocker_pending_field_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_item_id": summary.get(
            "product_scope_breadth_evidence_operator_field_worksheet_top_item_id", ""
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_bucket": summary.get(
            "product_scope_breadth_evidence_operator_field_worksheet_top_bucket", ""
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_top_required_evidence_type": summary.get(
            "product_scope_breadth_evidence_operator_field_worksheet_top_required_evidence_type",
            "",
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_priority_open_item_count": int(
            summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_priority_open_item_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_priority_local_crosscheck_candidate_count": int(
            summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_priority_local_crosscheck_candidate_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_scope_checklist_manual_review_subcheck_count": int(
            summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_scope_checklist_manual_review_subcheck_count"
            )
            or 0
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_claim_promoted": bool(
            summary.get("product_scope_breadth_evidence_operator_field_worksheet_claim_promoted")
            is True
        ),
        "product_scope_breadth_evidence_operator_field_worksheet_external_state_mutated": bool(
            summary.get(
                "product_scope_breadth_evidence_operator_field_worksheet_external_state_mutated"
            )
            is True
        ),
    }


def commercial_full_scope_operator_handoff_fields(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary_full_commercial_release_blocker_id": summary.get(
            "primary_full_commercial_release_blocker_id", ""
        ),
        "primary_full_commercial_release_blocker_requirement_id": summary.get(
            "primary_full_commercial_release_blocker_requirement_id", ""
        ),
        "primary_full_commercial_release_blocker_tier": summary.get(
            "primary_full_commercial_release_blocker_tier", ""
        ),
        "primary_full_commercial_release_blocker": summary.get(
            "primary_full_commercial_release_blocker", ""
        ),
        "primary_full_commercial_release_blocker_blocked_row_count": int(
            summary.get("primary_full_commercial_release_blocker_blocked_row_count") or 0
        ),
        "primary_full_commercial_release_blocker_first_blocked_evidence_row_id": summary.get(
            "primary_full_commercial_release_blocker_first_blocked_evidence_row_id", ""
        ),
        "primary_full_commercial_release_blocker_receipt_csv": summary.get(
            "primary_full_commercial_release_blocker_receipt_csv", ""
        ),
        "primary_full_commercial_release_blocker_approval_token_required": summary.get(
            "primary_full_commercial_release_blocker_approval_token_required", ""
        ),
        "primary_full_commercial_release_blocker_next_required_step": summary.get(
            "primary_full_commercial_release_blocker_next_required_step", ""
        ),
        "product_scope_next_operator_completion_item_id": summary.get(
            "product_scope_next_operator_completion_item_id", ""
        ),
        "product_scope_next_operator_completion_intake_mode": summary.get(
            "product_scope_next_operator_completion_intake_mode", ""
        ),
        "product_scope_next_operator_completion_required_evidence_type": summary.get(
            "product_scope_next_operator_completion_required_evidence_type", ""
        ),
        "product_scope_next_operator_completion_transporter_best_evidence_activity_type": summary.get(
            "product_scope_next_operator_completion_transporter_best_evidence_activity_type",
            "",
        ),
        "product_scope_next_operator_completion_transporter_best_evidence_value": summary.get(
            "product_scope_next_operator_completion_transporter_best_evidence_value", ""
        ),
        "product_scope_next_operator_completion_transporter_best_evidence_units": summary.get(
            "product_scope_next_operator_completion_transporter_best_evidence_units", ""
        ),
        "product_scope_next_operator_completion_transporter_best_evidence_document_id": summary.get(
            "product_scope_next_operator_completion_transporter_best_evidence_document_id",
            "",
        ),
        "product_scope_next_operator_completion_transporter_best_evidence_source_file": summary.get(
            "product_scope_next_operator_completion_transporter_best_evidence_source_file",
            "",
        ),
        "product_scope_next_operator_completion_transporter_claim_safe_blocker": summary.get(
            "product_scope_next_operator_completion_transporter_claim_safe_blocker", ""
        ),
        "product_scope_next_operator_completion_transporter_operator_next_verdict": summary.get(
            "product_scope_next_operator_completion_transporter_operator_next_verdict", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_id", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": bool(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready"
            )
            is True
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact",
            "",
        ),
        "product_scope_transporter_p0_return_bundle_required_artifact_count": int(
            summary.get("product_scope_transporter_p0_return_bundle_required_artifact_count")
            or 0
        ),
        "product_scope_transporter_p0_return_bundle_required_artifacts": list(
            summary.get("product_scope_transporter_p0_return_bundle_required_artifacts") or []
        ),
        "product_scope_transporter_p0_return_bundle_blocker_count": int(
            summary.get("product_scope_transporter_p0_return_bundle_blocker_count") or 0
        ),
        "product_scope_transporter_p0_return_bundle_next_artifact_id": summary.get(
            "product_scope_transporter_p0_return_bundle_next_artifact_id", ""
        ),
        "product_scope_transporter_p0_return_bundle_next_artifact_path": summary.get(
            "product_scope_transporter_p0_return_bundle_next_artifact_path", ""
        ),
        "product_scope_transporter_p0_return_bundle_next_artifact_failed_check_ids": list(
            summary.get(
                "product_scope_transporter_p0_return_bundle_next_artifact_failed_check_ids"
            )
            or []
        ),
        "product_scope_transporter_p0_operator_validation_candidate_ready": bool(
            summary.get("product_scope_transporter_p0_operator_validation_candidate_ready")
            is True
        ),
        "product_scope_transporter_p0_operator_validation_candidate_status": summary.get(
            "product_scope_transporter_p0_operator_validation_candidate_status", ""
        ),
        "product_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier": summary.get(
            "product_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier",
            "",
        ),
        "product_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol": summary.get(
            "product_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol",
            "",
        ),
        "product_scope_transporter_p0_operator_validation_candidate_blocker": summary.get(
            "product_scope_transporter_p0_operator_validation_candidate_blocker", ""
        ),
        "product_scope_transporter_p0_operator_validation_candidate_claim_safe_ready": bool(
            summary.get(
                "product_scope_transporter_p0_operator_validation_candidate_claim_safe_ready"
            )
            is True
        ),
        "product_scope_transporter_p0_operator_validation_candidate_placeholder_count": int(
            summary.get("product_scope_transporter_p0_operator_validation_candidate_placeholder_count")
            or 0
        ),
        "product_scope_transporter_p0_operator_validation_candidate_required_decision_field_count": int(
            summary.get(
                "product_scope_transporter_p0_operator_validation_candidate_required_decision_field_count"
            )
            or 0
        ),
        "product_goal_scope_next_operator_completion_item_id": summary.get(
            "product_goal_scope_next_operator_completion_item_id",
            summary.get("product_scope_next_operator_completion_item_id", ""),
        ),
        "product_goal_scope_next_operator_completion_intake_mode": summary.get(
            "product_goal_scope_next_operator_completion_intake_mode",
            summary.get("product_scope_next_operator_completion_intake_mode", ""),
        ),
        "product_goal_scope_next_operator_completion_required_evidence_type": summary.get(
            "product_goal_scope_next_operator_completion_required_evidence_type",
            summary.get("product_scope_next_operator_completion_required_evidence_type", ""),
        ),
        "product_goal_scope_next_operator_completion_transporter_best_evidence_activity_type": summary.get(
            "product_goal_scope_next_operator_completion_transporter_best_evidence_activity_type",
            summary.get(
                "product_scope_next_operator_completion_transporter_best_evidence_activity_type",
                "",
            ),
        ),
        "product_goal_scope_next_operator_completion_transporter_best_evidence_value": summary.get(
            "product_goal_scope_next_operator_completion_transporter_best_evidence_value",
            summary.get("product_scope_next_operator_completion_transporter_best_evidence_value", ""),
        ),
        "product_goal_scope_next_operator_completion_transporter_best_evidence_units": summary.get(
            "product_goal_scope_next_operator_completion_transporter_best_evidence_units",
            summary.get("product_scope_next_operator_completion_transporter_best_evidence_units", ""),
        ),
        "product_goal_scope_next_operator_completion_transporter_best_evidence_document_id": summary.get(
            "product_goal_scope_next_operator_completion_transporter_best_evidence_document_id",
            summary.get(
                "product_scope_next_operator_completion_transporter_best_evidence_document_id",
                "",
            ),
        ),
        "product_goal_scope_next_operator_completion_transporter_best_evidence_source_file": summary.get(
            "product_goal_scope_next_operator_completion_transporter_best_evidence_source_file",
            summary.get(
                "product_scope_next_operator_completion_transporter_best_evidence_source_file",
                "",
            ),
        ),
        "product_goal_scope_next_operator_completion_transporter_claim_safe_blocker": summary.get(
            "product_goal_scope_next_operator_completion_transporter_claim_safe_blocker",
            summary.get("product_scope_next_operator_completion_transporter_claim_safe_blocker", ""),
        ),
        "product_goal_scope_next_operator_completion_transporter_operator_next_verdict": summary.get(
            "product_goal_scope_next_operator_completion_transporter_operator_next_verdict",
            summary.get(
                "product_scope_next_operator_completion_transporter_operator_next_verdict",
                "",
            ),
        ),
        "product_goal_scope_transporter_p0_evidence_acquisition_next_slot_id": summary.get(
            "product_goal_scope_transporter_p0_evidence_acquisition_next_slot_id",
            summary.get("product_scope_transporter_p0_evidence_acquisition_next_slot_id", ""),
        ),
        "product_goal_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": bool(
            summary.get(
                "product_goal_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready"
            )
            is True
            or summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready"
            )
            is True
        ),
        "product_goal_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": summary.get(
            "product_goal_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact",
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact",
                "",
            ),
        ),
        "product_goal_scope_transporter_p0_return_bundle_required_artifact_count": int(
            summary.get(
                "product_goal_scope_transporter_p0_return_bundle_required_artifact_count",
                summary.get("product_scope_transporter_p0_return_bundle_required_artifact_count"),
            )
            or 0
        ),
        "product_goal_scope_transporter_p0_return_bundle_required_artifacts": list(
            summary.get(
                "product_goal_scope_transporter_p0_return_bundle_required_artifacts",
                summary.get("product_scope_transporter_p0_return_bundle_required_artifacts"),
            )
            or []
        ),
        "product_goal_scope_transporter_p0_return_bundle_blocker_count": int(
            summary.get(
                "product_goal_scope_transporter_p0_return_bundle_blocker_count",
                summary.get("product_scope_transporter_p0_return_bundle_blocker_count"),
            )
            or 0
        ),
        "product_goal_scope_transporter_p0_return_bundle_next_artifact_id": summary.get(
            "product_goal_scope_transporter_p0_return_bundle_next_artifact_id",
            summary.get("product_scope_transporter_p0_return_bundle_next_artifact_id", ""),
        ),
        "product_goal_scope_transporter_p0_return_bundle_next_artifact_path": summary.get(
            "product_goal_scope_transporter_p0_return_bundle_next_artifact_path",
            summary.get("product_scope_transporter_p0_return_bundle_next_artifact_path", ""),
        ),
        "product_goal_scope_transporter_p0_return_bundle_next_artifact_failed_check_ids": list(
            summary.get(
                "product_goal_scope_transporter_p0_return_bundle_next_artifact_failed_check_ids",
                summary.get(
                    "product_scope_transporter_p0_return_bundle_next_artifact_failed_check_ids"
                ),
            )
            or []
        ),
        "product_goal_scope_transporter_p0_operator_validation_candidate_ready": bool(
            summary.get("product_goal_scope_transporter_p0_operator_validation_candidate_ready")
            is True
            or summary.get("product_scope_transporter_p0_operator_validation_candidate_ready")
            is True
        ),
        "product_goal_scope_transporter_p0_operator_validation_candidate_status": summary.get(
            "product_goal_scope_transporter_p0_operator_validation_candidate_status",
            summary.get("product_scope_transporter_p0_operator_validation_candidate_status", ""),
        ),
        "product_goal_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier": summary.get(
            "product_goal_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier",
            summary.get(
                "product_scope_transporter_p0_operator_validation_candidate_ligand_external_identifier",
                "",
            ),
        ),
        "product_goal_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol": summary.get(
            "product_goal_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol",
            summary.get(
                "product_scope_transporter_p0_operator_validation_candidate_reference_binding_kcal_mol",
                "",
            ),
        ),
        "product_goal_scope_transporter_p0_operator_validation_candidate_blocker": summary.get(
            "product_goal_scope_transporter_p0_operator_validation_candidate_blocker",
            summary.get("product_scope_transporter_p0_operator_validation_candidate_blocker", ""),
        ),
        "product_goal_scope_transporter_p0_operator_validation_candidate_claim_safe_ready": bool(
            summary.get(
                "product_goal_scope_transporter_p0_operator_validation_candidate_claim_safe_ready"
            )
            is True
            or summary.get(
                "product_scope_transporter_p0_operator_validation_candidate_claim_safe_ready"
            )
            is True
        ),
        "product_goal_scope_transporter_p0_operator_validation_candidate_placeholder_count": int(
            summary.get(
                "product_goal_scope_transporter_p0_operator_validation_candidate_placeholder_count",
                summary.get(
                    "product_scope_transporter_p0_operator_validation_candidate_placeholder_count"
                ),
            )
            or 0
        ),
        "product_goal_scope_transporter_p0_operator_validation_candidate_required_decision_field_count": int(
            summary.get(
                "product_goal_scope_transporter_p0_operator_validation_candidate_required_decision_field_count",
                summary.get(
                    "product_scope_transporter_p0_operator_validation_candidate_required_decision_field_count"
                ),
            )
            or 0
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
        "engine_refinement_claim_evidence_operator_field_worksheet_artifact": summary.get(
            "engine_refinement_claim_evidence_operator_field_worksheet_artifact", ""
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_status": summary.get(
            "engine_refinement_claim_evidence_operator_field_worksheet_status", ""
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_ready": bool(
            summary.get("engine_refinement_claim_evidence_operator_field_worksheet_ready")
            is True
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_operator_fill_complete": bool(
            summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_operator_fill_complete"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_field_row_count": int(
            summary.get("engine_refinement_claim_evidence_operator_field_worksheet_field_row_count")
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count": int(
            summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_receipt_pending_field_count": int(
            summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_receipt_pending_field_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count": int(
            summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id": summary.get(
            "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id", ""
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_top_priority_bucket": summary.get(
            "engine_refinement_claim_evidence_operator_field_worksheet_top_priority_bucket",
            "",
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_pending_field_count": int(
            summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_pending_field_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_apply_blocked_row_count": int(
            summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_apply_blocked_row_count"
            )
            or 0
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_claim_promoted": bool(
            summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_claim_promoted"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_external_engine_calls_executed": bool(
            summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_external_engine_calls_executed"
            )
            is True
        ),
        "engine_refinement_claim_evidence_operator_field_worksheet_external_state_mutated": bool(
            summary.get(
                "engine_refinement_claim_evidence_operator_field_worksheet_external_state_mutated"
            )
            is True
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
