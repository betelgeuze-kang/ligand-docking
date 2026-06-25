from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-production-ai"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_ARTIFACT = (
    ROOT / "runs" / "product_production_ai_checkpoint_readiness_current.json"
)
PRODUCT_PRODUCTION_AI_PROMOTION_WORKBENCH_ARTIFACT = (
    ROOT / "runs" / "product_production_ai_promotion_workbench_current.json"
)
PRODUCT_PRODUCTION_AI_GPU_RETURN_INTAKE_ARTIFACT = (
    ROOT / "runs" / "product_production_ai_gpu_return_intake_current.json"
)
PRODUCTION_AI_REGISTRY_PROMOTION_OPERATOR_RECEIPT_ARTIFACT = (
    ROOT / "runs" / "production_ai_registry_promotion_operator_receipt_current.json"
)
PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_ARTIFACT = (
    ROOT / "runs" / "production_ai_registry_promotion_priority_packet_current.json"
)
RESIDUAL_MODEL_REGISTRY_ARTIFACT = ROOT / "runs" / "residual_model_registry_current.json"
RESIDUAL_PRODUCTION_CHECKPOINT_WORK_ORDER_ARTIFACT = (
    ROOT / "runs" / "residual_production_checkpoint_work_order_current.json"
)
RESIDUAL_PRODUCTION_TRAINING_DATA_CONTRACT_ARTIFACT = (
    ROOT / "runs" / "residual_production_training_data_contract_current.json"
)
RESIDUAL_FORCE_GPU_WORKER_RETURN_RECEIPT_ARTIFACT = ROOT / "runs" / "residual_force_gpu_worker_return_receipt_current.json"
RESIDUAL_FORCE_GPU_WORKER_HANDOFF_ARTIFACT = ROOT / "runs" / "residual_force_gpu_worker_handoff_package_current.json"
RESIDUAL_FORCE_GPU_WORKER_DISPATCH_MANIFEST_ARTIFACT = (
    ROOT / "runs" / "residual_force_gpu_worker_dispatch_manifest_current.json"
)
RESIDUAL_FORCE_GPU_WORKER_DISPATCH_BUNDLE_ARTIFACT = (
    ROOT / "runs" / "residual_force_gpu_worker_dispatch_bundle_current.json"
)
RESIDUAL_FORCE_GPU_WORKER_EXECUTION_RUNBOOK_ARTIFACT = (
    ROOT / "runs" / "residual_force_gpu_worker_execution_runbook_current.json"
)
ROCM_ENVIRONMENT_MANIFEST_ARTIFACT = ROOT / "runs" / "rocm_environment_manifest_current.json"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


@router.get("/production-ai-checkpoint-readiness")
async def get_product_production_ai_checkpoint_readiness() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_production_ai_checkpoint_readiness_artifact",
            "artifact_path": str(PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_ARTIFACT),
            "registry_artifact_path": str(RESIDUAL_MODEL_REGISTRY_ARTIFACT),
            "checkpoint_work_order_artifact_path": str(RESIDUAL_PRODUCTION_CHECKPOINT_WORK_ORDER_ARTIFACT),
            "training_data_artifact_path": str(RESIDUAL_PRODUCTION_TRAINING_DATA_CONTRACT_ARTIFACT),
            "force_gpu_worker_return_receipt_artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_RETURN_RECEIPT_ARTIFACT),
            "force_gpu_worker_handoff_artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_HANDOFF_ARTIFACT),
            "production_gpu_execution_environment_artifact_path": str(ROCM_ENVIRONMENT_MANIFEST_ARTIFACT),
            "check_count": 0,
            "pass_check_count": 0,
            "fail_check_count": 1,
            "failed_check_ids": ["missing_product_production_ai_checkpoint_readiness_artifact"],
            "first_failed_check_id": "missing_product_production_ai_checkpoint_readiness_artifact",
            "first_failed_source_artifact": str(PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_ARTIFACT),
            "first_failed_observed": "missing",
            "first_failed_required": "product production AI checkpoint readiness artifact exists",
            "first_failed_next_action": "Run python3 tools/build_product_production_ai_checkpoint_readiness.py.",
            "production_ai_checkpoint_ready": False,
            "production_ai_inference_subject_active": False,
            "product_model_layer_ready": False,
            "default_residual_mode": "",
            "production_promotion_allowed": False,
            "registry_promotion_required_gate_ids": [],
            "registry_promotion_missing_gate_ids": [],
            "registry_promotion_missing_gate_count": 0,
            "registry_promotion_upstream_acceptance_ready": False,
            "registry_promotion_currently_satisfied": False,
            "customer_facing_auto_correction_allowed": False,
            "customer_facing_score_mutation_allowed": False,
            "customer_facing_ranking_mutation_allowed": False,
            "trained_model_checkpoint_count": 0,
            "candidate_checkpoint_count": 0,
            "ready_checkpoint_count": 0,
            "checkpoint_preflight_ready": False,
            "production_training_data_ready": False,
            "production_output_head_gap_contract_ready": False,
            "production_output_heads_complete": False,
            "production_output_head_required_field_count": 0,
            "production_output_head_ready_field_count": 0,
            "production_output_head_blocked_field_count": 0,
            "production_output_head_blocked_fields": [],
            "production_output_head_first_blocked_field": "",
            "production_output_head_first_blocked_field_blockers": [],
            "production_output_head_gap_contract_artifact_path": "",
            "force_gpu_worker_return_receipt_ready": False,
            "force_gpu_worker_handoff_ready": False,
            "production_gpu_execution_environment_ready": False,
            "production_gpu_execution_environment_status": "",
            "production_gpu_rocm_manifest_ready": False,
            "production_gpu_rocm_stack_detected": False,
            "production_gpu_rocm_torch_ready": False,
            "production_gpu_rocm_amd_gpu_detected": False,
            "production_gpu_rocm_visible_device_count": 0,
            "production_gpu_rocm_device_names": [],
            "production_gpu_rocm_torch_version": "",
            "production_gpu_rocm_torch_hip_version": "",
            "production_gpu_rocm_visibility_diagnostic_packet_ready": False,
            "production_gpu_rocm_visibility_diagnostic_command_count": 0,
            "production_gpu_rocm_visibility_diagnostic_commands": [],
            "production_gpu_rocm_visibility_diagnostic_required_fields": [],
            "production_gpu_rocm_visibility_diagnostic_required_field_count": 0,
            "production_gpu_rocm_visibility_diagnostic_completion_rule": "",
            "production_gpu_rocm_visibility_diagnostic_return_artifacts": [],
            "production_gpu_rocm_visibility_torch_probe_command": "",
            "production_gpu_rocm_next_required_step": "",
            "force_gpu_worker_handoff_required": False,
            "force_gpu_worker_operator_action_required": False,
            "force_gpu_worker_handoff_next_required_step": "",
            "force_gpu_worker_operator_transfer_manifest_ready": False,
            "force_gpu_worker_operator_transfer_outbound_artifact_count": 0,
            "force_gpu_worker_operator_transfer_outbound_artifacts": [],
            "force_gpu_worker_operator_transfer_inbound_artifact_count": 0,
            "force_gpu_worker_operator_transfer_inbound_artifacts": [],
            "force_gpu_worker_operator_transfer_first_return_artifact": "",
            "force_gpu_worker_operator_transfer_return_manifest_artifact": "",
            "force_gpu_worker_operator_transfer_acceptance_artifact": "",
            "force_gpu_worker_operator_transfer_acceptance_ready_key": "",
            "force_gpu_worker_operator_transfer_post_return_validation_command": "",
            "force_gpu_worker_return_summary_template_payload_json": "",
            "force_gpu_worker_full_regeneration_command": "",
            "force_gpu_worker_post_return_validation_command": "",
            "force_gpu_worker_post_return_output_contract_ready": False,
            "force_gpu_worker_post_return_required_production_output_fields": [],
            "force_gpu_worker_post_return_gpu_unlock_artifacts": [],
            "force_gpu_worker_post_return_unlock_output_fields": [],
            "force_gpu_worker_post_return_min_expected_label_rows": 0,
            "force_gpu_worker_post_return_promotion_ladder_ready": False,
            "force_gpu_worker_post_return_promotion_ladder_contract_ready": False,
            "force_gpu_worker_post_return_promotion_ladder_currently_satisfied": False,
            "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_count": 0,
            "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_ids": [],
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_id": "",
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_artifact": "",
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_validation_command": "",
            "force_gpu_worker_post_return_promotion_ladder_stage_count": 0,
            "force_gpu_worker_post_return_promotion_ladder_stage_ids": [],
            "force_gpu_worker_post_return_promotion_ladder": [],
            "force_gpu_worker_post_return_promotion_ladder_ready_keys": [],
            "force_gpu_worker_post_return_promotion_ladder_missing_stages": [],
            "force_gpu_worker_post_return_promotion_ladder_missing_ready_keys": [],
            "production_inference_acceptance_matrix_ready": False,
            "production_inference_acceptance_stage_count": 0,
            "production_inference_acceptance_ready_stage_count": 0,
            "production_inference_acceptance_blocked_stage_count": 0,
            "production_inference_acceptance_stage_ids": [],
            "production_inference_acceptance_ready_stage_ids": [],
            "production_inference_acceptance_blocked_stage_ids": [],
            "production_inference_acceptance_next_stage_id": "",
            "production_inference_acceptance_next_stage_artifact": "",
            "production_inference_acceptance_next_stage_validation_command": "",
            "production_inference_acceptance_next_stage_release_effect": "",
            "production_inference_acceptance_next_stage_unlock_fields": [],
            "production_inference_acceptance_next_stage_required_checks": [],
            "production_inference_acceptance_next_stage_next_action": "",
            "production_inference_actionable_blocker_stage_id": "",
            "production_inference_actionable_blocker_check_id": "",
            "production_inference_actionable_blocker_artifact": "",
            "production_inference_actionable_blocker_observed": "",
            "production_inference_actionable_blocker_required": "",
            "production_inference_actionable_blocker_next_action": "",
            "production_inference_actionable_blocker_validation_command": "",
            "production_inference_actionable_blocker_unlock_fields": [],
            "production_inference_actionable_blocker_downstream_blocked_stage_count": 0,
            "production_inference_next_after_actionable_blocker_stage_id": "",
            "production_inference_next_after_actionable_blocker_artifact": "",
            "production_inference_next_after_actionable_blocker_validation_command": "",
            "production_inference_next_after_actionable_blocker_required_checks": [],
            "production_inference_next_after_actionable_blocker_unlock_fields": [],
            "production_inference_next_after_actionable_blocker_next_action": "",
            "production_inference_actionable_blocker_blocks_registry_promotion": False,
            "production_inference_actionable_operator_completion_packet_ready": False,
            "production_inference_actionable_operator_completion_packet_artifact": "",
            "production_inference_actionable_operator_completion_artifact_id": "",
            "production_inference_actionable_operator_completion_artifact_path": "",
            "production_inference_actionable_operator_completion_expected_queue_rows": 0,
            "production_inference_actionable_operator_completion_required_fields_or_columns": [],
            "production_inference_actionable_operator_completion_diagnostic_commands": [],
            "production_inference_actionable_operator_completion_diagnostic_command_count": 0,
            "production_inference_actionable_operator_completion_diagnostic_required_fields": [],
            "production_inference_actionable_operator_completion_diagnostic_required_field_count": 0,
            "production_inference_actionable_operator_completion_diagnostic_completion_rule": "",
            "production_inference_actionable_operator_completion_diagnostic_return_artifacts": [],
            "production_inference_actionable_operator_completion_torch_visibility_probe_command": "",
            "production_inference_actionable_operator_completion_failed_check_ids": [],
            "production_inference_actionable_operator_completion_template_payload_json": "",
            "production_inference_actionable_operator_completion_actual_summary_return_path": "",
            "production_inference_actionable_operator_completion_actual_manifest_return_path": "",
            "production_inference_actionable_operator_completion_validation_command": "",
            "production_inference_actionable_operator_completion_full_regeneration_command": "",
            "production_inference_actionable_operator_completion_completion_rule": "",
            "production_inference_actionable_operator_completion_backend_provenance_completion_rule": "",
            "production_inference_actionable_operator_completion_next_action": "",
            "production_inference_actionable_operator_completion_packet": {},
            "production_inference_worker_runtime_receipt_contract_ready": False,
            "production_inference_worker_runtime_receipt_contract": {},
            "production_inference_worker_runtime_receipt_required_fields_or_columns": [],
            "production_inference_worker_runtime_receipt_required_field_count": 0,
            "production_inference_worker_runtime_receipt_completion_rule": "",
            "production_inference_worker_runtime_receipt_post_environment_next_stage_id": "",
            "production_inference_worker_runtime_receipt_post_environment_next_artifact": "",
            "production_inference_worker_runtime_receipt_post_environment_validation_command": "",
            "production_inference_worker_runtime_receipt_full_regeneration_command": "",
            "production_inference_worker_runtime_receipt_guardrails": [],
            "production_inference_acceptance_matrix": [],
            "force_gpu_worker_post_run_validation_chain_current": False,
            "force_gpu_worker_post_run_validation_command_count": 0,
            "force_gpu_worker_post_run_validation_commands": [],
            "checkpoint_closure_blockers": ["missing_registry_or_checkpoint_work_order"],
            "checkpoint_missing_output_fields": [],
            "checkpoint_missing_adapter_output_policy_fields": [],
            "selected_sidecar_ready": False,
            "selected_sidecar_status": "",
            "selected_sidecar_blockers": [],
            "selected_sidecar_missing_output_fields": [],
            "selected_sidecar_training_contract_ready": False,
            "selected_sidecar_training_contract_missing_label_fields": [],
            "selected_sidecar_force_receipt_ready": False,
            "selected_sidecar_force_receipt_operator_verified": False,
            "selected_sidecar_force_receipt_operator_verified_true_count": 0,
            "selected_sidecar_force_receipt_expected_queue_rows": 0,
            "gpu_receipt_blockers": [],
            "gpu_receipt_summary_manifest_bound": False,
            "gpu_receipt_summary_out_manifest_csv_bound": False,
            "gpu_receipt_summary_out_summary_json_bound": False,
            "gpu_receipt_summary_manifest_row_counts_consistent": False,
            "gpu_receipt_summary_manifest_csv": "",
            "gpu_receipt_summary_out_manifest_csv": "",
            "gpu_receipt_summary_out_summary_json": "",
            "gpu_receipt_production_gpu_backend_provenance_ready": False,
            "gpu_receipt_production_gpu_backend_rows": 0,
            "gpu_receipt_production_gpu_backend_non_production_rows": 0,
            "gpu_receipt_production_gpu_backend_prod_mode": False,
            "gpu_receipt_production_gpu_backend_require_rust_hip": False,
            "gpu_receipt_expected_queue_rows": 0,
            "gpu_receipt_expected_npz_count": 0,
            "gpu_receipt_queue_id_count": 0,
            "gpu_receipt_queue_fingerprint_count": 0,
            "gpu_receipt_manifest_ok_row_count": 0,
            "gpu_receipt_manifest_row_count": 0,
            "gpu_receipt_manifest_identity_row_count": 0,
            "gpu_receipt_manifest_matched_queue_id_count": 0,
            "gpu_receipt_manifest_matched_expected_npz_count": 0,
            "gpu_receipt_manifest_matched_queue_fingerprint_count": 0,
            "gpu_receipt_manifest_operator_verified": False,
            "gpu_receipt_operator_verified_true_count": 0,
            "gpu_receipt_identity_coverage_ready": False,
            "training_data_failed_check_ids": [],
            "training_data_missing_output_labels": [],
            "next_required_step": "Run python3 tools/build_product_production_ai_checkpoint_readiness.py.",
            "requirements": [],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "model_promoted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Production AI checkpoint-readiness endpoint only; local registry/work-order artifacts are missing. "
                "It does not run inference, train models, create checkpoints, promote production mode, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_ARTIFACT),
        "registry_artifact_path": summary.get("registry_artifact_path", ""),
        "checkpoint_work_order_artifact_path": summary.get("checkpoint_work_order_artifact_path", ""),
        "training_data_artifact_path": summary.get("training_data_artifact_path", ""),
        "force_gpu_worker_return_receipt_artifact_path": summary.get("force_gpu_worker_return_receipt_artifact_path", ""),
        "force_gpu_worker_handoff_artifact_path": summary.get("force_gpu_worker_handoff_artifact_path", ""),
        "production_gpu_execution_environment_artifact_path": summary.get(
            "production_gpu_execution_environment_artifact_path", ""
        ),
        "check_count": int(summary.get("check_count") or 0),
        "pass_check_count": int(summary.get("pass_check_count") or 0),
        "fail_check_count": int(summary.get("fail_check_count") or 0),
        "failed_check_ids": list(summary.get("failed_check_ids") or []),
        "first_failed_check_id": summary.get("first_failed_check_id", ""),
        "first_failed_source_artifact": summary.get("first_failed_source_artifact", ""),
        "first_failed_observed": summary.get("first_failed_observed", ""),
        "first_failed_required": summary.get("first_failed_required", ""),
        "first_failed_next_action": summary.get("first_failed_next_action", ""),
        "production_ai_checkpoint_ready": bool(summary.get("production_ai_checkpoint_ready") is True),
        "production_ai_inference_subject_active": bool(
            summary.get("production_ai_inference_subject_active") is True
        ),
        "product_model_layer_ready": bool(summary.get("product_model_layer_ready") is True),
        "default_residual_mode": summary.get("default_residual_mode", ""),
        "production_promotion_allowed": bool(summary.get("production_promotion_allowed") is True),
        "registry_promotion_required_gate_ids": list(summary.get("registry_promotion_required_gate_ids") or []),
        "registry_promotion_missing_gate_ids": list(summary.get("registry_promotion_missing_gate_ids") or []),
        "registry_promotion_missing_gate_count": int(summary.get("registry_promotion_missing_gate_count") or 0),
        "registry_promotion_upstream_acceptance_ready": bool(
            summary.get("registry_promotion_upstream_acceptance_ready") is True
        ),
        "registry_promotion_currently_satisfied": bool(
            summary.get("registry_promotion_currently_satisfied") is True
        ),
        "customer_facing_auto_correction_allowed": bool(
            summary.get("customer_facing_auto_correction_allowed") is True
        ),
        "customer_facing_score_mutation_allowed": bool(
            summary.get("customer_facing_score_mutation_allowed") is True
        ),
        "customer_facing_ranking_mutation_allowed": bool(
            summary.get("customer_facing_ranking_mutation_allowed") is True
        ),
        "trained_model_checkpoint_count": int(summary.get("trained_model_checkpoint_count") or 0),
        "candidate_checkpoint_count": int(summary.get("candidate_checkpoint_count") or 0),
        "ready_checkpoint_count": int(summary.get("ready_checkpoint_count") or 0),
        "checkpoint_preflight_ready": bool(summary.get("checkpoint_preflight_ready") is True),
        "production_training_data_ready": bool(summary.get("production_training_data_ready") is True),
        "production_output_head_gap_contract_ready": bool(
            summary.get("production_output_head_gap_contract_ready") is True
        ),
        "production_output_heads_complete": bool(summary.get("production_output_heads_complete") is True),
        "production_output_head_required_field_count": int(
            summary.get("production_output_head_required_field_count") or 0
        ),
        "production_output_head_ready_field_count": int(
            summary.get("production_output_head_ready_field_count") or 0
        ),
        "production_output_head_blocked_field_count": int(
            summary.get("production_output_head_blocked_field_count") or 0
        ),
        "production_output_head_blocked_fields": list(
            summary.get("production_output_head_blocked_fields") or []
        ),
        "production_output_head_first_blocked_field": summary.get(
            "production_output_head_first_blocked_field", ""
        ),
        "production_output_head_first_blocked_field_blockers": list(
            summary.get("production_output_head_first_blocked_field_blockers") or []
        ),
        "production_output_head_gap_contract_artifact_path": summary.get(
            "production_output_head_gap_contract_artifact_path", ""
        ),
        "force_gpu_worker_return_receipt_ready": bool(
            summary.get("force_gpu_worker_return_receipt_ready") is True
        ),
        "force_gpu_worker_handoff_ready": bool(summary.get("force_gpu_worker_handoff_ready") is True),
        "production_gpu_execution_environment_ready": bool(
            summary.get("production_gpu_execution_environment_ready") is True
        ),
        "production_gpu_execution_environment_status": summary.get("production_gpu_execution_environment_status", ""),
        "production_gpu_rocm_manifest_ready": bool(summary.get("production_gpu_rocm_manifest_ready") is True),
        "production_gpu_rocm_stack_detected": bool(summary.get("production_gpu_rocm_stack_detected") is True),
        "production_gpu_rocm_torch_ready": bool(summary.get("production_gpu_rocm_torch_ready") is True),
        "production_gpu_rocm_amd_gpu_detected": bool(summary.get("production_gpu_rocm_amd_gpu_detected") is True),
        "production_gpu_rocm_visible_device_count": int(
            summary.get("production_gpu_rocm_visible_device_count") or 0
        ),
        "production_gpu_rocm_device_names": list(summary.get("production_gpu_rocm_device_names") or []),
        "production_gpu_rocm_torch_version": summary.get("production_gpu_rocm_torch_version", ""),
        "production_gpu_rocm_torch_hip_version": summary.get("production_gpu_rocm_torch_hip_version", ""),
        "production_gpu_rocm_visibility_diagnostic_packet_ready": bool(
            summary.get("production_gpu_rocm_visibility_diagnostic_packet_ready") is True
        ),
        "production_gpu_rocm_visibility_diagnostic_command_count": int(
            summary.get("production_gpu_rocm_visibility_diagnostic_command_count") or 0
        ),
        "production_gpu_rocm_visibility_diagnostic_commands": list(
            summary.get("production_gpu_rocm_visibility_diagnostic_commands") or []
        ),
        "production_gpu_rocm_visibility_diagnostic_required_fields": list(
            summary.get("production_gpu_rocm_visibility_diagnostic_required_fields") or []
        ),
        "production_gpu_rocm_visibility_diagnostic_required_field_count": int(
            summary.get("production_gpu_rocm_visibility_diagnostic_required_field_count") or 0
        ),
        "production_gpu_rocm_visibility_diagnostic_completion_rule": summary.get(
            "production_gpu_rocm_visibility_diagnostic_completion_rule", ""
        ),
        "production_gpu_rocm_visibility_diagnostic_return_artifacts": list(
            summary.get("production_gpu_rocm_visibility_diagnostic_return_artifacts") or []
        ),
        "production_gpu_rocm_visibility_torch_probe_command": summary.get(
            "production_gpu_rocm_visibility_torch_probe_command", ""
        ),
        "production_gpu_rocm_next_required_step": summary.get("production_gpu_rocm_next_required_step", ""),
        "force_gpu_worker_handoff_required": bool(summary.get("force_gpu_worker_handoff_required") is True),
        "force_gpu_worker_operator_action_required": bool(
            summary.get("force_gpu_worker_operator_action_required") is True
        ),
        "force_gpu_worker_handoff_next_required_step": summary.get(
            "force_gpu_worker_handoff_next_required_step", ""
        ),
        "force_gpu_worker_operator_transfer_manifest_ready": bool(
            summary.get("force_gpu_worker_operator_transfer_manifest_ready") is True
        ),
        "force_gpu_worker_operator_transfer_outbound_artifact_count": int(
            summary.get("force_gpu_worker_operator_transfer_outbound_artifact_count") or 0
        ),
        "force_gpu_worker_operator_transfer_outbound_artifacts": list(
            summary.get("force_gpu_worker_operator_transfer_outbound_artifacts") or []
        ),
        "force_gpu_worker_operator_transfer_inbound_artifact_count": int(
            summary.get("force_gpu_worker_operator_transfer_inbound_artifact_count") or 0
        ),
        "force_gpu_worker_operator_transfer_inbound_artifacts": list(
            summary.get("force_gpu_worker_operator_transfer_inbound_artifacts") or []
        ),
        "force_gpu_worker_operator_transfer_first_return_artifact": summary.get(
            "force_gpu_worker_operator_transfer_first_return_artifact", ""
        ),
        "force_gpu_worker_operator_transfer_return_manifest_artifact": summary.get(
            "force_gpu_worker_operator_transfer_return_manifest_artifact", ""
        ),
        "force_gpu_worker_operator_transfer_acceptance_artifact": summary.get(
            "force_gpu_worker_operator_transfer_acceptance_artifact", ""
        ),
        "force_gpu_worker_operator_transfer_acceptance_ready_key": summary.get(
            "force_gpu_worker_operator_transfer_acceptance_ready_key", ""
        ),
        "force_gpu_worker_operator_transfer_post_return_validation_command": summary.get(
            "force_gpu_worker_operator_transfer_post_return_validation_command", ""
        ),
        "force_gpu_worker_return_summary_template_payload_json": summary.get(
            "force_gpu_worker_return_summary_template_payload_json", ""
        ),
        "force_gpu_worker_full_regeneration_command": summary.get("force_gpu_worker_full_regeneration_command", ""),
        "force_gpu_worker_post_return_validation_command": summary.get(
            "force_gpu_worker_post_return_validation_command", ""
        ),
        "force_gpu_worker_post_return_output_contract_ready": bool(
            summary.get("force_gpu_worker_post_return_output_contract_ready") is True
        ),
        "force_gpu_worker_post_return_required_production_output_fields": list(
            summary.get("force_gpu_worker_post_return_required_production_output_fields") or []
        ),
        "force_gpu_worker_post_return_gpu_unlock_artifacts": list(
            summary.get("force_gpu_worker_post_return_gpu_unlock_artifacts") or []
        ),
        "force_gpu_worker_post_return_unlock_output_fields": list(
            summary.get("force_gpu_worker_post_return_unlock_output_fields") or []
        ),
        "force_gpu_worker_post_return_min_expected_label_rows": int(
            summary.get("force_gpu_worker_post_return_min_expected_label_rows") or 0
        ),
        "force_gpu_worker_post_return_promotion_ladder_ready": bool(
            summary.get("force_gpu_worker_post_return_promotion_ladder_ready") is True
        ),
        "force_gpu_worker_post_return_promotion_ladder_contract_ready": bool(
            summary.get("force_gpu_worker_post_return_promotion_ladder_contract_ready") is True
        ),
        "force_gpu_worker_post_return_promotion_ladder_currently_satisfied": bool(
            summary.get("force_gpu_worker_post_return_promotion_ladder_currently_satisfied") is True
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_count": int(
            summary.get("force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_count") or 0
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_ids": list(
            summary.get("force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_ids") or []
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_next_stage_id": summary.get(
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_id", ""
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_next_stage_artifact": summary.get(
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_artifact", ""
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_next_stage_validation_command": summary.get(
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_validation_command", ""
        ),
        "force_gpu_worker_post_return_promotion_ladder_stage_count": int(
            summary.get("force_gpu_worker_post_return_promotion_ladder_stage_count") or 0
        ),
        "force_gpu_worker_post_return_promotion_ladder_stage_ids": list(
            summary.get("force_gpu_worker_post_return_promotion_ladder_stage_ids") or []
        ),
        "force_gpu_worker_post_return_promotion_ladder": list(
            summary.get("force_gpu_worker_post_return_promotion_ladder") or []
        ),
        "force_gpu_worker_post_return_promotion_ladder_ready_keys": list(
            summary.get("force_gpu_worker_post_return_promotion_ladder_ready_keys") or []
        ),
        "force_gpu_worker_post_return_promotion_ladder_missing_stages": list(
            summary.get("force_gpu_worker_post_return_promotion_ladder_missing_stages") or []
        ),
        "force_gpu_worker_post_return_promotion_ladder_missing_ready_keys": list(
            summary.get("force_gpu_worker_post_return_promotion_ladder_missing_ready_keys") or []
        ),
        "production_inference_acceptance_matrix_ready": bool(
            summary.get("production_inference_acceptance_matrix_ready") is True
        ),
        "production_inference_acceptance_stage_count": int(
            summary.get("production_inference_acceptance_stage_count") or 0
        ),
        "production_inference_acceptance_ready_stage_count": int(
            summary.get("production_inference_acceptance_ready_stage_count") or 0
        ),
        "production_inference_acceptance_blocked_stage_count": int(
            summary.get("production_inference_acceptance_blocked_stage_count") or 0
        ),
        "production_inference_acceptance_stage_ids": list(
            summary.get("production_inference_acceptance_stage_ids") or []
        ),
        "production_inference_acceptance_ready_stage_ids": list(
            summary.get("production_inference_acceptance_ready_stage_ids") or []
        ),
        "production_inference_acceptance_blocked_stage_ids": list(
            summary.get("production_inference_acceptance_blocked_stage_ids") or []
        ),
        "production_inference_acceptance_next_stage_id": summary.get(
            "production_inference_acceptance_next_stage_id", ""
        ),
        "production_inference_acceptance_next_stage_artifact": summary.get(
            "production_inference_acceptance_next_stage_artifact", ""
        ),
        "production_inference_acceptance_next_stage_validation_command": summary.get(
            "production_inference_acceptance_next_stage_validation_command", ""
        ),
        "production_inference_acceptance_next_stage_release_effect": summary.get(
            "production_inference_acceptance_next_stage_release_effect", ""
        ),
        "production_inference_acceptance_next_stage_unlock_fields": list(
            summary.get("production_inference_acceptance_next_stage_unlock_fields") or []
        ),
        "production_inference_acceptance_next_stage_required_checks": list(
            summary.get("production_inference_acceptance_next_stage_required_checks") or []
        ),
        "production_inference_acceptance_next_stage_next_action": summary.get(
            "production_inference_acceptance_next_stage_next_action", ""
        ),
        "production_inference_actionable_blocker_stage_id": summary.get(
            "production_inference_actionable_blocker_stage_id", ""
        ),
        "production_inference_actionable_blocker_check_id": summary.get(
            "production_inference_actionable_blocker_check_id", ""
        ),
        "production_inference_actionable_blocker_artifact": summary.get(
            "production_inference_actionable_blocker_artifact", ""
        ),
        "production_inference_actionable_blocker_observed": summary.get(
            "production_inference_actionable_blocker_observed", ""
        ),
        "production_inference_actionable_blocker_required": summary.get(
            "production_inference_actionable_blocker_required", ""
        ),
        "production_inference_actionable_blocker_next_action": summary.get(
            "production_inference_actionable_blocker_next_action", ""
        ),
        "production_inference_actionable_blocker_validation_command": summary.get(
            "production_inference_actionable_blocker_validation_command", ""
        ),
        "production_inference_actionable_blocker_unlock_fields": list(
            summary.get("production_inference_actionable_blocker_unlock_fields") or []
        ),
        "production_inference_actionable_blocker_downstream_blocked_stage_count": int(
            summary.get("production_inference_actionable_blocker_downstream_blocked_stage_count") or 0
        ),
        "production_inference_next_after_actionable_blocker_stage_id": summary.get(
            "production_inference_next_after_actionable_blocker_stage_id", ""
        ),
        "production_inference_next_after_actionable_blocker_artifact": summary.get(
            "production_inference_next_after_actionable_blocker_artifact", ""
        ),
        "production_inference_next_after_actionable_blocker_validation_command": summary.get(
            "production_inference_next_after_actionable_blocker_validation_command", ""
        ),
        "production_inference_next_after_actionable_blocker_required_checks": list(
            summary.get("production_inference_next_after_actionable_blocker_required_checks") or []
        ),
        "production_inference_next_after_actionable_blocker_unlock_fields": list(
            summary.get("production_inference_next_after_actionable_blocker_unlock_fields") or []
        ),
        "production_inference_next_after_actionable_blocker_next_action": summary.get(
            "production_inference_next_after_actionable_blocker_next_action", ""
        ),
        "production_inference_actionable_blocker_blocks_registry_promotion": bool(
            summary.get("production_inference_actionable_blocker_blocks_registry_promotion") is True
        ),
        "production_inference_actionable_operator_completion_packet_ready": bool(
            summary.get("production_inference_actionable_operator_completion_packet_ready") is True
        ),
        "production_inference_actionable_operator_completion_packet_artifact": summary.get(
            "production_inference_actionable_operator_completion_packet_artifact", ""
        ),
        "production_inference_actionable_operator_completion_artifact_id": summary.get(
            "production_inference_actionable_operator_completion_artifact_id", ""
        ),
        "production_inference_actionable_operator_completion_artifact_path": summary.get(
            "production_inference_actionable_operator_completion_artifact_path", ""
        ),
        "production_inference_actionable_operator_completion_expected_queue_rows": int(
            summary.get("production_inference_actionable_operator_completion_expected_queue_rows") or 0
        ),
        "production_inference_actionable_operator_completion_required_fields_or_columns": list(
            summary.get("production_inference_actionable_operator_completion_required_fields_or_columns") or []
        ),
        "production_inference_actionable_operator_completion_diagnostic_commands": list(
            summary.get("production_inference_actionable_operator_completion_diagnostic_commands") or []
        ),
        "production_inference_actionable_operator_completion_diagnostic_command_count": int(
            summary.get("production_inference_actionable_operator_completion_diagnostic_command_count") or 0
        ),
        "production_inference_actionable_operator_completion_diagnostic_required_fields": list(
            summary.get("production_inference_actionable_operator_completion_diagnostic_required_fields") or []
        ),
        "production_inference_actionable_operator_completion_diagnostic_required_field_count": int(
            summary.get("production_inference_actionable_operator_completion_diagnostic_required_field_count") or 0
        ),
        "production_inference_actionable_operator_completion_diagnostic_completion_rule": summary.get(
            "production_inference_actionable_operator_completion_diagnostic_completion_rule", ""
        ),
        "production_inference_actionable_operator_completion_diagnostic_return_artifacts": list(
            summary.get("production_inference_actionable_operator_completion_diagnostic_return_artifacts") or []
        ),
        "production_inference_actionable_operator_completion_torch_visibility_probe_command": summary.get(
            "production_inference_actionable_operator_completion_torch_visibility_probe_command", ""
        ),
        "production_inference_actionable_operator_completion_failed_check_ids": list(
            summary.get("production_inference_actionable_operator_completion_failed_check_ids") or []
        ),
        "production_inference_actionable_operator_completion_template_payload_json": summary.get(
            "production_inference_actionable_operator_completion_template_payload_json", ""
        ),
        "production_inference_actionable_operator_completion_actual_summary_return_path": summary.get(
            "production_inference_actionable_operator_completion_actual_summary_return_path", ""
        ),
        "production_inference_actionable_operator_completion_actual_manifest_return_path": summary.get(
            "production_inference_actionable_operator_completion_actual_manifest_return_path", ""
        ),
        "production_inference_actionable_operator_completion_validation_command": summary.get(
            "production_inference_actionable_operator_completion_validation_command", ""
        ),
        "production_inference_actionable_operator_completion_full_regeneration_command": summary.get(
            "production_inference_actionable_operator_completion_full_regeneration_command", ""
        ),
        "production_inference_actionable_operator_completion_completion_rule": summary.get(
            "production_inference_actionable_operator_completion_completion_rule", ""
        ),
        "production_inference_actionable_operator_completion_backend_provenance_completion_rule": summary.get(
            "production_inference_actionable_operator_completion_backend_provenance_completion_rule", ""
        ),
        "production_inference_actionable_operator_completion_next_action": summary.get(
            "production_inference_actionable_operator_completion_next_action", ""
        ),
        "production_inference_actionable_operator_completion_packet": dict(
            summary.get("production_inference_actionable_operator_completion_packet") or {}
        ),
        "production_inference_worker_runtime_receipt_contract_ready": bool(
            summary.get("production_inference_worker_runtime_receipt_contract_ready") is True
        ),
        "production_inference_worker_runtime_receipt_contract": dict(
            summary.get("production_inference_worker_runtime_receipt_contract") or {}
        ),
        "production_inference_worker_runtime_receipt_required_fields_or_columns": list(
            summary.get("production_inference_worker_runtime_receipt_required_fields_or_columns") or []
        ),
        "production_inference_worker_runtime_receipt_required_field_count": int(
            summary.get("production_inference_worker_runtime_receipt_required_field_count") or 0
        ),
        "production_inference_worker_runtime_receipt_completion_rule": summary.get(
            "production_inference_worker_runtime_receipt_completion_rule", ""
        ),
        "production_inference_worker_runtime_receipt_post_environment_next_stage_id": summary.get(
            "production_inference_worker_runtime_receipt_post_environment_next_stage_id", ""
        ),
        "production_inference_worker_runtime_receipt_post_environment_next_artifact": summary.get(
            "production_inference_worker_runtime_receipt_post_environment_next_artifact", ""
        ),
        "production_inference_worker_runtime_receipt_post_environment_validation_command": summary.get(
            "production_inference_worker_runtime_receipt_post_environment_validation_command", ""
        ),
        "production_inference_worker_runtime_receipt_full_regeneration_command": summary.get(
            "production_inference_worker_runtime_receipt_full_regeneration_command", ""
        ),
        "production_inference_worker_runtime_receipt_guardrails": list(
            summary.get("production_inference_worker_runtime_receipt_guardrails") or []
        ),
        "production_inference_acceptance_matrix": list(
            packet.get("production_inference_acceptance_matrix") or []
        ),
        "force_gpu_worker_post_run_validation_chain_current": bool(
            summary.get("force_gpu_worker_post_run_validation_chain_current") is True
        ),
        "force_gpu_worker_post_run_validation_command_count": int(
            summary.get("force_gpu_worker_post_run_validation_command_count") or 0
        ),
        "force_gpu_worker_post_run_validation_commands": list(
            summary.get("force_gpu_worker_post_run_validation_commands") or []
        ),
        "checkpoint_closure_blockers": list(summary.get("checkpoint_closure_blockers") or []),
        "checkpoint_missing_output_fields": list(summary.get("checkpoint_missing_output_fields") or []),
        "checkpoint_missing_adapter_output_policy_fields": list(
            summary.get("checkpoint_missing_adapter_output_policy_fields") or []
        ),
        "selected_sidecar_ready": bool(summary.get("selected_sidecar_ready") is True),
        "selected_sidecar_status": summary.get("selected_sidecar_status", ""),
        "selected_sidecar_blockers": list(summary.get("selected_sidecar_blockers") or []),
        "selected_sidecar_missing_output_fields": list(summary.get("selected_sidecar_missing_output_fields") or []),
        "selected_sidecar_training_contract_ready": bool(
            summary.get("selected_sidecar_training_contract_ready") is True
        ),
        "selected_sidecar_training_contract_missing_label_fields": list(
            summary.get("selected_sidecar_training_contract_missing_label_fields") or []
        ),
        "selected_sidecar_force_receipt_ready": bool(summary.get("selected_sidecar_force_receipt_ready") is True),
        "selected_sidecar_force_receipt_operator_verified": bool(
            summary.get("selected_sidecar_force_receipt_operator_verified") is True
        ),
        "selected_sidecar_force_receipt_operator_verified_true_count": int(
            summary.get("selected_sidecar_force_receipt_operator_verified_true_count") or 0
        ),
        "selected_sidecar_force_receipt_expected_queue_rows": int(
            summary.get("selected_sidecar_force_receipt_expected_queue_rows") or 0
        ),
        "gpu_receipt_blockers": list(summary.get("gpu_receipt_blockers") or []),
        "gpu_receipt_summary_manifest_bound": bool(summary.get("gpu_receipt_summary_manifest_bound") is True),
        "gpu_receipt_summary_out_manifest_csv_bound": bool(
            summary.get("gpu_receipt_summary_out_manifest_csv_bound") is True
        ),
        "gpu_receipt_summary_out_summary_json_bound": bool(
            summary.get("gpu_receipt_summary_out_summary_json_bound") is True
        ),
        "gpu_receipt_summary_manifest_row_counts_consistent": bool(
            summary.get("gpu_receipt_summary_manifest_row_counts_consistent") is True
        ),
        "gpu_receipt_summary_manifest_csv": summary.get("gpu_receipt_summary_manifest_csv", ""),
        "gpu_receipt_summary_out_manifest_csv": summary.get("gpu_receipt_summary_out_manifest_csv", ""),
        "gpu_receipt_summary_out_summary_json": summary.get("gpu_receipt_summary_out_summary_json", ""),
        "gpu_receipt_production_gpu_backend_provenance_ready": bool(
            summary.get("gpu_receipt_production_gpu_backend_provenance_ready") is True
        ),
        "gpu_receipt_production_gpu_backend_rows": int(
            summary.get("gpu_receipt_production_gpu_backend_rows") or 0
        ),
        "gpu_receipt_production_gpu_backend_non_production_rows": int(
            summary.get("gpu_receipt_production_gpu_backend_non_production_rows") or 0
        ),
        "gpu_receipt_production_gpu_backend_prod_mode": bool(
            summary.get("gpu_receipt_production_gpu_backend_prod_mode") is True
        ),
        "gpu_receipt_production_gpu_backend_require_rust_hip": bool(
            summary.get("gpu_receipt_production_gpu_backend_require_rust_hip") is True
        ),
        "gpu_receipt_expected_queue_rows": int(summary.get("gpu_receipt_expected_queue_rows") or 0),
        "gpu_receipt_expected_npz_count": int(summary.get("gpu_receipt_expected_npz_count") or 0),
        "gpu_receipt_queue_id_count": int(summary.get("gpu_receipt_queue_id_count") or 0),
        "gpu_receipt_queue_fingerprint_count": int(summary.get("gpu_receipt_queue_fingerprint_count") or 0),
        "gpu_receipt_manifest_ok_row_count": int(summary.get("gpu_receipt_manifest_ok_row_count") or 0),
        "gpu_receipt_manifest_row_count": int(summary.get("gpu_receipt_manifest_row_count") or 0),
        "gpu_receipt_manifest_identity_row_count": int(summary.get("gpu_receipt_manifest_identity_row_count") or 0),
        "gpu_receipt_manifest_matched_queue_id_count": int(
            summary.get("gpu_receipt_manifest_matched_queue_id_count") or 0
        ),
        "gpu_receipt_manifest_matched_expected_npz_count": int(
            summary.get("gpu_receipt_manifest_matched_expected_npz_count") or 0
        ),
        "gpu_receipt_manifest_matched_queue_fingerprint_count": int(
            summary.get("gpu_receipt_manifest_matched_queue_fingerprint_count") or 0
        ),
        "gpu_receipt_manifest_operator_verified": bool(
            summary.get("gpu_receipt_manifest_operator_verified") is True
        ),
        "gpu_receipt_operator_verified_true_count": int(summary.get("gpu_receipt_operator_verified_true_count") or 0),
        "gpu_receipt_identity_coverage_ready": bool(summary.get("gpu_receipt_identity_coverage_ready") is True),
        "training_data_failed_check_ids": list(summary.get("training_data_failed_check_ids") or []),
        "training_data_missing_output_labels": list(summary.get("training_data_missing_output_labels") or []),
        "next_required_step": summary.get("next_required_step", ""),
        "requirements": rows,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/production-ai-gpu-worker-dispatch-manifest")
async def get_product_production_ai_gpu_worker_dispatch_manifest() -> dict[str, Any]:
    packet = _read_json_object(RESIDUAL_FORCE_GPU_WORKER_DISPATCH_MANIFEST_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_residual_force_gpu_worker_dispatch_manifest",
            "artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_DISPATCH_MANIFEST_ARTIFACT),
            "dispatch_manifest_ready": False,
            "handoff_package_ready": False,
            "handoff_package_artifact": "",
            "queue_rows": 0,
            "queue_csv": "",
            "queue_csv_sha256": "",
            "outbound_artifact_count": 0,
            "inbound_artifact_count": 0,
            "local_artifact_reference_count": 0,
            "local_artifact_present_count": 0,
            "local_artifact_missing_count": 1,
            "local_artifact_missing": ["missing_residual_force_gpu_worker_dispatch_manifest"],
            "native_pdb_dependency_count": 0,
            "native_pdb_missing_count": 0,
            "native_pdb_missing": [],
            "tiny_pilot_command": "",
            "full_regeneration_command": "",
            "post_run_validation_commands": [],
            "post_run_validation_command_count": 0,
            "acceptance_contract": {},
            "return_summary_completion_rule": "",
            "return_manifest_required_identity_rule": "",
            "worker_rocm_manifest_completion_rule": "",
            "rows": [],
            "blockers": [{"code": "missing_residual_force_gpu_worker_dispatch_manifest"}],
            "next_required_step": "Run python3 tools/build_residual_force_gpu_worker_dispatch_manifest.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "full_regeneration_executed": False,
            "force_labels_created": False,
            "training_executed": False,
            "checkpoint_created": False,
            "model_promoted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Residual force GPU worker dispatch manifest endpoint only; local manifest is missing. It does not "
                "run GPU jobs, regenerate trajectories, create force labels, train models, promote checkpoints, or "
                "mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_DISPATCH_MANIFEST_ARTIFACT),
        "dispatch_manifest_ready": bool(summary.get("dispatch_manifest_ready") is True),
        "handoff_package_ready": bool(summary.get("handoff_package_ready") is True),
        "handoff_package_artifact": summary.get("handoff_package_artifact", ""),
        "queue_rows": int(summary.get("queue_rows") or 0),
        "queue_csv": summary.get("queue_csv", ""),
        "queue_csv_sha256": summary.get("queue_csv_sha256", ""),
        "outbound_artifact_count": int(summary.get("outbound_artifact_count") or 0),
        "inbound_artifact_count": int(summary.get("inbound_artifact_count") or 0),
        "local_artifact_reference_count": int(summary.get("local_artifact_reference_count") or 0),
        "local_artifact_present_count": int(summary.get("local_artifact_present_count") or 0),
        "local_artifact_missing_count": int(summary.get("local_artifact_missing_count") or 0),
        "local_artifact_missing": list(summary.get("local_artifact_missing") or []),
        "native_pdb_dependency_count": int(summary.get("native_pdb_dependency_count") or 0),
        "native_pdb_missing_count": int(summary.get("native_pdb_missing_count") or 0),
        "native_pdb_missing": list(summary.get("native_pdb_missing") or []),
        "tiny_pilot_command": summary.get("tiny_pilot_command", ""),
        "full_regeneration_command": summary.get("full_regeneration_command", ""),
        "post_run_validation_commands": list(summary.get("post_run_validation_commands") or []),
        "post_run_validation_command_count": int(summary.get("post_run_validation_command_count") or 0),
        "acceptance_contract": dict(summary.get("acceptance_contract") or {}),
        "return_summary_completion_rule": summary.get("return_summary_completion_rule", ""),
        "return_manifest_required_identity_rule": summary.get("return_manifest_required_identity_rule", ""),
        "worker_rocm_manifest_completion_rule": summary.get("worker_rocm_manifest_completion_rule", ""),
        "rows": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/production-ai-gpu-worker-dispatch-bundle")
async def get_product_production_ai_gpu_worker_dispatch_bundle() -> dict[str, Any]:
    packet = _read_json_object(RESIDUAL_FORCE_GPU_WORKER_DISPATCH_BUNDLE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_residual_force_gpu_worker_dispatch_bundle",
            "artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_DISPATCH_BUNDLE_ARTIFACT),
            "dispatch_bundle_ready": False,
            "dispatch_manifest_ready": False,
            "dispatch_manifest_artifact": "",
            "bundle_tar_path": "",
            "bundle_tar_exists": False,
            "bundle_tar_size_bytes": 0,
            "bundle_tar_sha256": "",
            "bundle_member_count": 0,
            "source_artifact_count": 0,
            "local_artifact_missing_count": 1,
            "native_pdb_dependency_count": 0,
            "native_pdb_missing_count": 0,
            "queue_rows": 0,
            "outbound_artifact_count": 0,
            "inbound_artifact_count": 0,
            "acceptance_contract": {},
            "tiny_pilot_command": "",
            "full_regeneration_command": "",
            "post_run_validation_commands": [],
            "post_run_validation_command_count": 0,
            "rows": [],
            "blockers": [{"code": "missing_residual_force_gpu_worker_dispatch_bundle"}],
            "next_required_step": "Run python3 tools/build_residual_force_gpu_worker_dispatch_bundle.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "full_regeneration_executed": False,
            "force_labels_created": False,
            "training_executed": False,
            "checkpoint_created": False,
            "model_promoted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Residual force GPU worker dispatch bundle endpoint only; local bundle artifact is missing. It does "
                "not run GPU jobs, regenerate trajectories, upload, submit, email, delete files, train models, "
                "promote checkpoints, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_DISPATCH_BUNDLE_ARTIFACT),
        "dispatch_bundle_ready": bool(summary.get("dispatch_bundle_ready") is True),
        "dispatch_manifest_ready": bool(summary.get("dispatch_manifest_ready") is True),
        "dispatch_manifest_artifact": summary.get("dispatch_manifest_artifact", ""),
        "bundle_tar_path": summary.get("bundle_tar_path", ""),
        "bundle_tar_exists": bool(summary.get("bundle_tar_exists") is True),
        "bundle_tar_size_bytes": int(summary.get("bundle_tar_size_bytes") or 0),
        "bundle_tar_sha256": summary.get("bundle_tar_sha256", ""),
        "bundle_member_count": int(summary.get("bundle_member_count") or 0),
        "source_artifact_count": int(summary.get("source_artifact_count") or 0),
        "local_artifact_missing_count": int(summary.get("local_artifact_missing_count") or 0),
        "native_pdb_dependency_count": int(summary.get("native_pdb_dependency_count") or 0),
        "native_pdb_missing_count": int(summary.get("native_pdb_missing_count") or 0),
        "queue_rows": int(summary.get("queue_rows") or 0),
        "outbound_artifact_count": int(summary.get("outbound_artifact_count") or 0),
        "inbound_artifact_count": int(summary.get("inbound_artifact_count") or 0),
        "acceptance_contract": dict(summary.get("acceptance_contract") or {}),
        "tiny_pilot_command": summary.get("tiny_pilot_command", ""),
        "full_regeneration_command": summary.get("full_regeneration_command", ""),
        "post_run_validation_commands": list(summary.get("post_run_validation_commands") or []),
        "post_run_validation_command_count": int(summary.get("post_run_validation_command_count") or 0),
        "rows": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/production-ai-gpu-worker-execution-runbook")
async def get_product_production_ai_gpu_worker_execution_runbook() -> dict[str, Any]:
    packet = _read_json_object(RESIDUAL_FORCE_GPU_WORKER_EXECUTION_RUNBOOK_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_residual_force_gpu_worker_execution_runbook",
            "artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_EXECUTION_RUNBOOK_ARTIFACT),
            "execution_runbook_ready": False,
            "dispatch_bundle_ready": False,
            "dispatch_bundle_artifact": "",
            "bundle_tar_path": "",
            "bundle_tar_exists": False,
            "bundle_tar_sha256": "",
            "queue_rows": 0,
            "worker_script_path": "",
            "worker_script_exists": False,
            "worker_script_executable": False,
            "return_packager_script_path": "",
            "return_packager_script_exists": False,
            "return_packager_script_executable": False,
            "return_bundle_tar_path": "",
            "return_bundle_sha256_path": "",
            "manifest_npz_path_columns": [],
            "required_return_core_files": [],
            "return_packager_command": "",
            "step_count": 0,
            "worker_executable_step_count": 0,
            "local_post_return_step_count": 0,
            "rocm_diagnostic_command_count": 0,
            "required_return_artifact_count": 0,
            "required_return_artifacts": [],
            "acceptance_contract": {},
            "tiny_pilot_command": "",
            "full_regeneration_command": "",
            "post_return_validation_command": "",
            "rows": [],
            "blockers": [{"code": "missing_residual_force_gpu_worker_execution_runbook"}],
            "next_required_step": "Run python3 tools/build_residual_force_gpu_worker_execution_runbook.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "full_regeneration_executed": False,
            "force_labels_created": False,
            "training_executed": False,
            "checkpoint_created": False,
            "model_promoted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Residual force GPU worker execution runbook endpoint only; local runbook artifact is missing. "
                "It does not run GPU jobs, extract bundles, regenerate trajectories, upload, train models, promote "
                "checkpoints, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_EXECUTION_RUNBOOK_ARTIFACT),
        "execution_runbook_ready": bool(summary.get("execution_runbook_ready") is True),
        "dispatch_bundle_ready": bool(summary.get("dispatch_bundle_ready") is True),
        "dispatch_bundle_artifact": summary.get("dispatch_bundle_artifact", ""),
        "bundle_tar_path": summary.get("bundle_tar_path", ""),
        "bundle_tar_exists": bool(summary.get("bundle_tar_exists") is True),
        "bundle_tar_sha256": summary.get("bundle_tar_sha256", ""),
        "queue_rows": int(summary.get("queue_rows") or 0),
        "worker_script_path": summary.get("worker_script_path", ""),
        "worker_script_exists": bool(summary.get("worker_script_exists") is True),
        "worker_script_executable": bool(summary.get("worker_script_executable") is True),
        "return_packager_script_path": summary.get("return_packager_script_path", ""),
        "return_packager_script_exists": bool(summary.get("return_packager_script_exists") is True),
        "return_packager_script_executable": bool(
            summary.get("return_packager_script_executable") is True
        ),
        "return_bundle_tar_path": summary.get("return_bundle_tar_path", ""),
        "return_bundle_sha256_path": summary.get("return_bundle_sha256_path", ""),
        "manifest_npz_path_columns": list(summary.get("manifest_npz_path_columns") or []),
        "required_return_core_files": list(summary.get("required_return_core_files") or []),
        "return_packager_command": summary.get("return_packager_command", ""),
        "step_count": int(summary.get("step_count") or 0),
        "worker_executable_step_count": int(summary.get("worker_executable_step_count") or 0),
        "local_post_return_step_count": int(summary.get("local_post_return_step_count") or 0),
        "rocm_diagnostic_command_count": int(summary.get("rocm_diagnostic_command_count") or 0),
        "required_return_artifact_count": int(summary.get("required_return_artifact_count") or 0),
        "required_return_artifacts": list(summary.get("required_return_artifacts") or []),
        "acceptance_contract": dict(summary.get("acceptance_contract") or {}),
        "tiny_pilot_command": summary.get("tiny_pilot_command", ""),
        "full_regeneration_command": summary.get("full_regeneration_command", ""),
        "post_return_validation_command": summary.get("post_return_validation_command", ""),
        "rows": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/production-ai-gpu-return-intake")
async def get_product_production_ai_gpu_return_intake() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_PRODUCTION_AI_GPU_RETURN_INTAKE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    operator_acceptance_matrix = (
        packet.get("operator_acceptance_matrix")
        if isinstance(packet.get("operator_acceptance_matrix"), list)
        else []
    )
    operator_return_artifact_completion_matrix = (
        packet.get("operator_return_artifact_completion_matrix")
        if isinstance(packet.get("operator_return_artifact_completion_matrix"), list)
        else []
    )
    operator_return_artifact_completion_blocker_matrix = (
        packet.get("operator_return_artifact_completion_blocker_matrix")
        if isinstance(packet.get("operator_return_artifact_completion_blocker_matrix"), list)
        else []
    )
    if not summary:
        return {
            "status": "missing_product_production_ai_gpu_return_intake_artifact",
            "artifact_path": str(PRODUCT_PRODUCTION_AI_GPU_RETURN_INTAKE_ARTIFACT),
            "gpu_return_intake_ready": False,
            "gpu_return_artifacts_ready": False,
            "check_count": 0,
            "pass_check_count": 0,
            "fail_check_count": 1,
            "failed_check_ids": ["missing_product_production_ai_gpu_return_intake_artifact"],
            "operator_return_blocker_count": 1,
            "first_failed_check_id": "missing_product_production_ai_gpu_return_intake_artifact",
            "first_failed_source_artifact": str(PRODUCT_PRODUCTION_AI_GPU_RETURN_INTAKE_ARTIFACT),
            "first_failed_required": "product production AI GPU return intake artifact exists",
            "first_failed_observed": "missing",
            "first_failed_next_action": "Run python3 tools/build_product_production_ai_gpu_return_intake.py.",
            "expected_queue_rows": 0,
            "operator_return_bundle_contract_ready": False,
            "operator_return_required_artifacts": [],
            "operator_return_required_artifact_count": 0,
            "operator_return_artifact_completion_matrix": [],
            "operator_return_artifact_completion_matrix_count": 0,
            "operator_return_artifact_completion_blocker_matrix": [],
            "operator_return_artifact_completion_blocker_count": 0,
            "operator_return_next_artifact_completion_packet_ready": False,
            "operator_return_next_artifact_completion_packet": {},
            "operator_return_next_artifact_id": "",
            "operator_return_next_artifact_path": "",
            "operator_return_next_artifact_failed_check_ids": [],
            "operator_return_manifest_required_columns": [],
            "operator_return_manifest_required_column_count": 0,
            "operator_return_validation_ladder_ready": False,
            "operator_return_handoff_binding_ready": False,
            "operator_return_handoff_queue_csv": "",
            "operator_return_handoff_queue_csv_sha256": "",
            "operator_return_handoff_full_regeneration_command": "",
            "operator_return_handoff_return_manifest_schema_contract_ready": False,
            "operator_return_handoff_return_manifest_required_identity_rule": "",
            "operator_return_handoff_return_manifest_fingerprint_columns": [],
            "operator_return_handoff_return_manifest_queue_id_columns": [],
            "operator_return_handoff_return_manifest_npz_columns": [],
            "operator_acceptance_matrix_ready": False,
            "operator_acceptance_stage_count": 0,
            "operator_acceptance_ready_stage_count": 0,
            "operator_acceptance_blocked_stage_count": 0,
            "operator_acceptance_stage_ids": [],
            "operator_acceptance_ready_stage_ids": [],
            "operator_acceptance_blocked_stage_ids": [],
            "operator_acceptance_next_stage_id": "",
            "operator_acceptance_next_stage_artifact": "",
            "operator_acceptance_next_stage_validation_command": "",
            "operator_acceptance_next_stage_release_effect": "",
            "operator_acceptance_next_stage_unlock_fields": [],
            "operator_acceptance_next_stage_required_checks": [],
            "operator_acceptance_next_stage_next_action": "",
            "operator_acceptance_matrix": [],
            "operator_acceptance_stage_check_matrix": [],
            "operator_acceptance_stage_check_matrix_count": 0,
            "operator_acceptance_current_blocked_stage_check_matrix": [],
            "operator_acceptance_current_blocked_stage_check_matrix_count": 0,
            "handoff_ready": False,
            "operator_action_required": True,
            "manifest_template_ready": False,
            "manifest_template_csv": "",
            "manifest_template_row_count": 0,
            "manifest_status_placeholder_count": 0,
            "manifest_operator_verification_placeholder_count": 0,
            "summary_template_ready": False,
            "summary_template_csv": "",
            "summary_template_payload_json": "",
            "summary_template_payload": {},
            "summary_template_field_count": 0,
            "summary_template_required_fields": [],
            "summary_template_completion_rule": "",
            "summary_template_backend_provenance_contract_ready": False,
            "summary_template_required_backend_provenance_fields": [],
            "summary_template_backend_provenance_completion_rule": "",
            "actual_summary_return_path": "",
            "actual_manifest_return_path": "",
            "receipt_status": "",
            "receipt_blockers": [],
            "summary_returned": False,
            "summary_complete": False,
            "summary_manifest_bound": False,
            "summary_manifest_csv": "",
            "summary_out_manifest_csv_present": False,
            "summary_out_manifest_csv": "",
            "summary_out_manifest_csv_bound": False,
            "summary_out_summary_json_bound": False,
            "summary_out_summary_json": "",
            "summary_manifest_row_counts_consistent": False,
            "production_gpu_backend_provenance_ready": False,
            "production_gpu_backend_rows": 0,
            "production_gpu_backend_non_production_rows": 0,
            "production_gpu_backend_prod_mode": False,
            "production_gpu_backend_require_rust_hip": False,
            "worker_rocm_manifest_artifact": "",
            "worker_rocm_manifest_ready": False,
            "worker_rocm_manifest_generation_command": "",
            "worker_rocm_manifest_completion_rule": "",
            "worker_rocm_stack_detected": False,
            "worker_rocm_torch_ready": False,
            "worker_rocm_amd_gpu_detected": False,
            "worker_rocm_visible_device_count": 0,
            "worker_rocm_device_names": [],
            "worker_rocm_next_required_step": "",
            "manifest_returned": False,
            "manifest_complete": False,
            "manifest_npz_paths_complete": False,
            "manifest_npz_files_exist": False,
            "manifest_npz_files_valid": False,
            "manifest_npz_schema_valid": False,
            "manifest_npz_identity_valid": False,
            "manifest_npz_path_column_present": False,
            "manifest_npz_path_present_count": 0,
            "manifest_npz_path_missing_count": 0,
            "manifest_ok_row_missing_npz_path_count": 0,
            "manifest_operator_verified_missing_npz_path_count": 0,
            "manifest_npz_file_existing_count": 0,
            "manifest_npz_file_missing_count": 0,
            "manifest_ok_row_missing_npz_file_count": 0,
            "manifest_operator_verified_missing_npz_file_count": 0,
            "manifest_npz_file_valid_count": 0,
            "manifest_npz_file_invalid_count": 0,
            "manifest_ok_row_invalid_npz_file_count": 0,
            "manifest_operator_verified_invalid_npz_file_count": 0,
            "manifest_npz_schema_valid_count": 0,
            "manifest_npz_schema_invalid_count": 0,
            "manifest_ok_row_invalid_npz_schema_count": 0,
            "manifest_operator_verified_invalid_npz_schema_count": 0,
            "manifest_npz_identity_valid_count": 0,
            "manifest_npz_identity_invalid_count": 0,
            "manifest_ok_row_invalid_npz_identity_count": 0,
            "manifest_operator_verified_invalid_npz_identity_count": 0,
            "manifest_operator_verified": False,
            "identity_coverage_ready": False,
            "post_run_derivation_validation_ready": False,
            "post_return_validation_command": "",
            "post_run_validation_command_count": 0,
            "post_run_validation_commands": [],
            "checks": [],
            "blockers": [],
            "next_required_step": "Run python3 tools/build_product_production_ai_gpu_return_intake.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "full_regeneration_executed": False,
            "force_labels_created": False,
            "training_executed": False,
            "checkpoint_created": False,
            "model_promoted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Production AI GPU-return intake endpoint only; the local intake artifact is missing. "
                "It does not run GPU jobs, train models, promote production mode, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_PRODUCTION_AI_GPU_RETURN_INTAKE_ARTIFACT),
        "gpu_return_intake_ready": bool(summary.get("gpu_return_intake_ready") is True),
        "gpu_return_artifacts_ready": bool(summary.get("gpu_return_artifacts_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_check_count": int(summary.get("pass_check_count") or 0),
        "fail_check_count": int(summary.get("fail_check_count") or 0),
        "failed_check_ids": list(summary.get("failed_check_ids") or []),
        "operator_return_blocker_count": int(summary.get("operator_return_blocker_count") or 0),
        "first_failed_check_id": summary.get("first_failed_check_id", ""),
        "first_failed_source_artifact": summary.get("first_failed_source_artifact", ""),
        "first_failed_required": summary.get("first_failed_required", ""),
        "first_failed_observed": summary.get("first_failed_observed", ""),
        "first_failed_next_action": summary.get("first_failed_next_action", ""),
        "expected_queue_rows": int(summary.get("expected_queue_rows") or 0),
        "operator_return_bundle_contract_ready": bool(
            summary.get("operator_return_bundle_contract_ready") is True
        ),
        "operator_return_required_artifacts": list(summary.get("operator_return_required_artifacts") or []),
        "operator_return_required_artifact_count": int(
            summary.get("operator_return_required_artifact_count") or 0
        ),
        "operator_return_artifact_completion_matrix": operator_return_artifact_completion_matrix,
        "operator_return_artifact_completion_matrix_count": int(
            summary.get("operator_return_artifact_completion_matrix_count") or 0
        ),
        "operator_return_artifact_completion_blocker_matrix": (
            operator_return_artifact_completion_blocker_matrix
        ),
        "operator_return_artifact_completion_blocker_count": int(
            summary.get("operator_return_artifact_completion_blocker_count") or 0
        ),
        "operator_return_next_artifact_completion_packet_ready": bool(
            summary.get("operator_return_next_artifact_completion_packet_ready") is True
        ),
        "operator_return_next_artifact_completion_packet": dict(
            summary.get("operator_return_next_artifact_completion_packet") or {}
        ),
        "operator_return_next_artifact_id": summary.get("operator_return_next_artifact_id", ""),
        "operator_return_next_artifact_path": summary.get("operator_return_next_artifact_path", ""),
        "operator_return_next_artifact_failed_check_ids": list(
            summary.get("operator_return_next_artifact_failed_check_ids") or []
        ),
        "operator_return_manifest_required_columns": list(
            summary.get("operator_return_manifest_required_columns") or []
        ),
        "operator_return_manifest_required_column_count": int(
            summary.get("operator_return_manifest_required_column_count") or 0
        ),
        "operator_return_validation_ladder_ready": bool(
            summary.get("operator_return_validation_ladder_ready") is True
        ),
        "operator_return_handoff_binding_ready": bool(
            summary.get("operator_return_handoff_binding_ready") is True
        ),
        "operator_return_handoff_queue_csv": summary.get("operator_return_handoff_queue_csv", ""),
        "operator_return_handoff_queue_csv_sha256": summary.get("operator_return_handoff_queue_csv_sha256", ""),
        "operator_return_handoff_full_regeneration_command": summary.get(
            "operator_return_handoff_full_regeneration_command", ""
        ),
        "operator_return_handoff_return_manifest_schema_contract_ready": bool(
            summary.get("operator_return_handoff_return_manifest_schema_contract_ready") is True
        ),
        "operator_return_handoff_return_manifest_required_identity_rule": summary.get(
            "operator_return_handoff_return_manifest_required_identity_rule", ""
        ),
        "operator_return_handoff_return_manifest_fingerprint_columns": list(
            summary.get("operator_return_handoff_return_manifest_fingerprint_columns") or []
        ),
        "operator_return_handoff_return_manifest_queue_id_columns": list(
            summary.get("operator_return_handoff_return_manifest_queue_id_columns") or []
        ),
        "operator_return_handoff_return_manifest_npz_columns": list(
            summary.get("operator_return_handoff_return_manifest_npz_columns") or []
        ),
        "operator_acceptance_matrix_ready": bool(summary.get("operator_acceptance_matrix_ready") is True),
        "operator_acceptance_stage_count": int(summary.get("operator_acceptance_stage_count") or 0),
        "operator_acceptance_ready_stage_count": int(
            summary.get("operator_acceptance_ready_stage_count") or 0
        ),
        "operator_acceptance_blocked_stage_count": int(
            summary.get("operator_acceptance_blocked_stage_count") or 0
        ),
        "operator_acceptance_stage_ids": list(summary.get("operator_acceptance_stage_ids") or []),
        "operator_acceptance_ready_stage_ids": list(
            summary.get("operator_acceptance_ready_stage_ids") or []
        ),
        "operator_acceptance_blocked_stage_ids": list(
            summary.get("operator_acceptance_blocked_stage_ids") or []
        ),
        "operator_acceptance_next_stage_id": summary.get("operator_acceptance_next_stage_id", ""),
        "operator_acceptance_next_stage_artifact": summary.get(
            "operator_acceptance_next_stage_artifact", ""
        ),
        "operator_acceptance_next_stage_validation_command": summary.get(
            "operator_acceptance_next_stage_validation_command", ""
        ),
        "operator_acceptance_next_stage_release_effect": summary.get(
            "operator_acceptance_next_stage_release_effect", ""
        ),
        "operator_acceptance_next_stage_unlock_fields": list(
            summary.get("operator_acceptance_next_stage_unlock_fields") or []
        ),
        "operator_acceptance_next_stage_required_checks": list(
            summary.get("operator_acceptance_next_stage_required_checks") or []
        ),
        "operator_acceptance_next_stage_next_action": summary.get(
            "operator_acceptance_next_stage_next_action", ""
        ),
        "operator_acceptance_matrix": operator_acceptance_matrix,
        "operator_acceptance_stage_check_matrix": list(
            summary.get("operator_acceptance_stage_check_matrix") or []
        ),
        "operator_acceptance_stage_check_matrix_count": int(
            summary.get("operator_acceptance_stage_check_matrix_count") or 0
        ),
        "operator_acceptance_current_blocked_stage_check_matrix": list(
            summary.get("operator_acceptance_current_blocked_stage_check_matrix") or []
        ),
        "operator_acceptance_current_blocked_stage_check_matrix_count": int(
            summary.get("operator_acceptance_current_blocked_stage_check_matrix_count") or 0
        ),
        "handoff_ready": bool(summary.get("handoff_ready") is True),
        "operator_action_required": bool(summary.get("operator_action_required") is True),
        "manifest_template_ready": bool(summary.get("manifest_template_ready") is True),
        "manifest_template_csv": summary.get("manifest_template_csv", ""),
        "manifest_template_row_count": int(summary.get("manifest_template_row_count") or 0),
        "manifest_status_placeholder_count": int(summary.get("manifest_status_placeholder_count") or 0),
        "manifest_operator_verification_placeholder_count": int(
            summary.get("manifest_operator_verification_placeholder_count") or 0
        ),
        "summary_template_ready": bool(summary.get("summary_template_ready") is True),
        "summary_template_csv": summary.get("summary_template_csv", ""),
        "summary_template_payload_json": summary.get("summary_template_payload_json", ""),
        "summary_template_payload": (
            dict(summary.get("summary_template_payload"))
            if isinstance(summary.get("summary_template_payload"), dict)
            else {}
        ),
        "summary_template_field_count": int(summary.get("summary_template_field_count") or 0),
        "summary_template_required_fields": list(summary.get("summary_template_required_fields") or []),
        "summary_template_completion_rule": summary.get("summary_template_completion_rule", ""),
        "summary_template_backend_provenance_contract_ready": bool(
            summary.get("summary_template_backend_provenance_contract_ready") is True
        ),
        "summary_template_required_backend_provenance_fields": list(
            summary.get("summary_template_required_backend_provenance_fields") or []
        ),
        "summary_template_backend_provenance_completion_rule": summary.get(
            "summary_template_backend_provenance_completion_rule", ""
        ),
        "actual_summary_return_path": summary.get("actual_summary_return_path", ""),
        "actual_manifest_return_path": summary.get("actual_manifest_return_path", ""),
        "receipt_status": summary.get("receipt_status", ""),
        "receipt_blockers": list(summary.get("receipt_blockers") or []),
        "summary_returned": bool(summary.get("summary_returned") is True),
        "summary_complete": bool(summary.get("summary_complete") is True),
        "summary_manifest_bound": bool(summary.get("summary_manifest_bound") is True),
        "summary_manifest_csv": summary.get("summary_manifest_csv", ""),
        "summary_out_manifest_csv_present": bool(summary.get("summary_out_manifest_csv_present") is True),
        "summary_out_manifest_csv": summary.get("summary_out_manifest_csv", ""),
        "summary_out_manifest_csv_bound": bool(summary.get("summary_out_manifest_csv_bound") is True),
        "summary_out_summary_json_bound": bool(summary.get("summary_out_summary_json_bound") is True),
        "summary_out_summary_json": summary.get("summary_out_summary_json", ""),
        "summary_manifest_row_counts_consistent": bool(
            summary.get("summary_manifest_row_counts_consistent") is True
        ),
        "production_gpu_backend_provenance_ready": bool(
            summary.get("production_gpu_backend_provenance_ready") is True
        ),
        "production_gpu_backend_rows": int(summary.get("production_gpu_backend_rows") or 0),
        "production_gpu_backend_non_production_rows": int(
            summary.get("production_gpu_backend_non_production_rows") or 0
        ),
        "production_gpu_backend_prod_mode": bool(summary.get("production_gpu_backend_prod_mode") is True),
        "production_gpu_backend_require_rust_hip": bool(
            summary.get("production_gpu_backend_require_rust_hip") is True
        ),
        "worker_rocm_manifest_artifact": summary.get("worker_rocm_manifest_artifact", ""),
        "worker_rocm_manifest_ready": bool(summary.get("worker_rocm_manifest_ready") is True),
        "worker_rocm_manifest_generation_command": summary.get(
            "worker_rocm_manifest_generation_command", ""
        ),
        "worker_rocm_manifest_completion_rule": summary.get("worker_rocm_manifest_completion_rule", ""),
        "worker_rocm_stack_detected": bool(summary.get("worker_rocm_stack_detected") is True),
        "worker_rocm_torch_ready": bool(summary.get("worker_rocm_torch_ready") is True),
        "worker_rocm_amd_gpu_detected": bool(summary.get("worker_rocm_amd_gpu_detected") is True),
        "worker_rocm_visible_device_count": int(summary.get("worker_rocm_visible_device_count") or 0),
        "worker_rocm_device_names": list(summary.get("worker_rocm_device_names") or []),
        "worker_rocm_next_required_step": summary.get("worker_rocm_next_required_step", ""),
        "manifest_returned": bool(summary.get("manifest_returned") is True),
        "manifest_complete": bool(summary.get("manifest_complete") is True),
        "manifest_npz_paths_complete": bool(summary.get("manifest_npz_paths_complete") is True),
        "manifest_npz_files_exist": bool(summary.get("manifest_npz_files_exist") is True),
        "manifest_npz_files_valid": bool(summary.get("manifest_npz_files_valid") is True),
        "manifest_npz_schema_valid": bool(summary.get("manifest_npz_schema_valid") is True),
        "manifest_npz_identity_valid": bool(summary.get("manifest_npz_identity_valid") is True),
        "manifest_npz_path_column_present": bool(summary.get("manifest_npz_path_column_present") is True),
        "manifest_npz_path_present_count": int(summary.get("manifest_npz_path_present_count") or 0),
        "manifest_npz_path_missing_count": int(summary.get("manifest_npz_path_missing_count") or 0),
        "manifest_ok_row_missing_npz_path_count": int(summary.get("manifest_ok_row_missing_npz_path_count") or 0),
        "manifest_operator_verified_missing_npz_path_count": int(
            summary.get("manifest_operator_verified_missing_npz_path_count") or 0
        ),
        "manifest_npz_file_existing_count": int(summary.get("manifest_npz_file_existing_count") or 0),
        "manifest_npz_file_missing_count": int(summary.get("manifest_npz_file_missing_count") or 0),
        "manifest_ok_row_missing_npz_file_count": int(summary.get("manifest_ok_row_missing_npz_file_count") or 0),
        "manifest_operator_verified_missing_npz_file_count": int(
            summary.get("manifest_operator_verified_missing_npz_file_count") or 0
        ),
        "manifest_npz_file_valid_count": int(summary.get("manifest_npz_file_valid_count") or 0),
        "manifest_npz_file_invalid_count": int(summary.get("manifest_npz_file_invalid_count") or 0),
        "manifest_ok_row_invalid_npz_file_count": int(summary.get("manifest_ok_row_invalid_npz_file_count") or 0),
        "manifest_operator_verified_invalid_npz_file_count": int(
            summary.get("manifest_operator_verified_invalid_npz_file_count") or 0
        ),
        "manifest_npz_schema_valid_count": int(summary.get("manifest_npz_schema_valid_count") or 0),
        "manifest_npz_schema_invalid_count": int(summary.get("manifest_npz_schema_invalid_count") or 0),
        "manifest_ok_row_invalid_npz_schema_count": int(
            summary.get("manifest_ok_row_invalid_npz_schema_count") or 0
        ),
        "manifest_operator_verified_invalid_npz_schema_count": int(
            summary.get("manifest_operator_verified_invalid_npz_schema_count") or 0
        ),
        "manifest_npz_identity_valid_count": int(summary.get("manifest_npz_identity_valid_count") or 0),
        "manifest_npz_identity_invalid_count": int(summary.get("manifest_npz_identity_invalid_count") or 0),
        "manifest_ok_row_invalid_npz_identity_count": int(
            summary.get("manifest_ok_row_invalid_npz_identity_count") or 0
        ),
        "manifest_operator_verified_invalid_npz_identity_count": int(
            summary.get("manifest_operator_verified_invalid_npz_identity_count") or 0
        ),
        "manifest_operator_verified": bool(summary.get("manifest_operator_verified") is True),
        "identity_coverage_ready": bool(summary.get("identity_coverage_ready") is True),
        "post_run_derivation_validation_ready": bool(
            summary.get("post_run_derivation_validation_ready") is True
        ),
        "post_return_validation_command": summary.get("post_return_validation_command", ""),
        "post_run_validation_command_count": int(summary.get("post_run_validation_command_count") or 0),
        "post_run_validation_commands": list(summary.get("post_run_validation_commands") or []),
        "checks": rows,
        "blockers": blockers,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/production-ai-promotion-workbench")
async def get_product_production_ai_promotion_workbench() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_PRODUCTION_AI_PROMOTION_WORKBENCH_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_production_ai_promotion_workbench_artifact",
            "artifact_path": str(PRODUCT_PRODUCTION_AI_PROMOTION_WORKBENCH_ARTIFACT),
            "checkpoint_readiness_artifact_path": str(PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_ARTIFACT),
            "promotion_workbench_ready": False,
            "production_ai_promotion_ready": False,
            "production_ai_checkpoint_ready": False,
            "production_ai_inference_subject_active": False,
            "production_promotion_allowed": False,
            "registry_promotion_required_gate_ids": [],
            "registry_promotion_missing_gate_ids": [],
            "registry_promotion_missing_gate_count": 0,
            "registry_promotion_upstream_acceptance_ready": False,
            "registry_promotion_currently_satisfied": False,
            "default_residual_mode": "",
            "trained_model_checkpoint_count": 0,
            "candidate_checkpoint_count": 0,
            "ready_checkpoint_count": 0,
            "checkpoint_preflight_ready": False,
            "production_training_data_ready": False,
            "gpu_handoff_ready": False,
            "gpu_operator_action_required": False,
            "gpu_return_receipt_ready": False,
            "gpu_receipt_expected_queue_rows": 0,
            "gpu_receipt_expected_npz_count": 0,
            "gpu_receipt_manifest_row_count": 0,
            "gpu_receipt_manifest_ok_row_count": 0,
            "gpu_receipt_manifest_identity_row_count": 0,
            "gpu_receipt_manifest_matched_queue_id_count": 0,
            "gpu_receipt_manifest_matched_expected_npz_count": 0,
            "gpu_receipt_manifest_matched_queue_fingerprint_count": 0,
            "gpu_receipt_manifest_operator_verified": False,
            "gpu_receipt_operator_verified_true_count": 0,
            "gpu_receipt_identity_coverage_ready": False,
            "post_return_promotion_ladder_stage_count": 0,
            "post_return_promotion_ladder_ready_stage_count": 0,
            "post_return_promotion_ladder_blocked_stage_count": 1,
            "post_return_promotion_ladder_stage_ids": [],
            "ready_key_alias_used_count": 0,
            "ready_key_alias_used_stage_ids": [],
            "blocked_stage_ids": ["missing_product_production_ai_promotion_workbench_artifact"],
            "first_blocked_stage_id": "missing_product_production_ai_promotion_workbench_artifact",
            "first_blocked_stage_artifact": str(PRODUCT_PRODUCTION_AI_PROMOTION_WORKBENCH_ARTIFACT),
            "first_blocked_stage_ready_key": "promotion_workbench_ready",
            "first_blocked_stage_observed_value": None,
            "checkpoint_failed_check_ids": [],
            "checkpoint_closure_blockers": [],
            "checkpoint_missing_output_fields": [],
            "checkpoint_missing_adapter_output_policy_fields": [],
            "selected_sidecar_ready": False,
            "selected_sidecar_status": "",
            "selected_sidecar_blockers": [],
            "selected_sidecar_missing_output_fields": [],
            "training_data_failed_check_ids": [],
            "training_data_missing_output_labels": [],
            "force_gpu_worker_full_regeneration_command": "",
            "force_gpu_worker_post_return_validation_command": "",
            "force_gpu_worker_post_run_validation_command_count": 0,
            "force_gpu_worker_post_run_validation_commands": [],
            "promotion_stages": [],
            "blockers": [],
            "next_required_step": "Run python3 tools/build_product_production_ai_promotion_workbench.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "model_promoted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Production AI promotion-workbench endpoint only; the local workbench artifact is missing. "
                "It does not run inference, train models, promote production mode, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_PRODUCTION_AI_PROMOTION_WORKBENCH_ARTIFACT),
        "checkpoint_readiness_artifact_path": summary.get("checkpoint_readiness_artifact_path", ""),
        "promotion_workbench_ready": bool(summary.get("promotion_workbench_ready") is True),
        "production_ai_promotion_ready": bool(summary.get("production_ai_promotion_ready") is True),
        "production_ai_checkpoint_ready": bool(summary.get("production_ai_checkpoint_ready") is True),
        "production_ai_inference_subject_active": bool(
            summary.get("production_ai_inference_subject_active") is True
        ),
        "production_promotion_allowed": bool(summary.get("production_promotion_allowed") is True),
        "registry_promotion_required_gate_ids": list(summary.get("registry_promotion_required_gate_ids") or []),
        "registry_promotion_missing_gate_ids": list(summary.get("registry_promotion_missing_gate_ids") or []),
        "registry_promotion_missing_gate_count": int(summary.get("registry_promotion_missing_gate_count") or 0),
        "registry_promotion_upstream_acceptance_ready": bool(
            summary.get("registry_promotion_upstream_acceptance_ready") is True
        ),
        "registry_promotion_currently_satisfied": bool(
            summary.get("registry_promotion_currently_satisfied") is True
        ),
        "default_residual_mode": summary.get("default_residual_mode", ""),
        "trained_model_checkpoint_count": int(summary.get("trained_model_checkpoint_count") or 0),
        "candidate_checkpoint_count": int(summary.get("candidate_checkpoint_count") or 0),
        "ready_checkpoint_count": int(summary.get("ready_checkpoint_count") or 0),
        "checkpoint_preflight_ready": bool(summary.get("checkpoint_preflight_ready") is True),
        "production_training_data_ready": bool(summary.get("production_training_data_ready") is True),
        "gpu_handoff_ready": bool(summary.get("gpu_handoff_ready") is True),
        "gpu_operator_action_required": bool(summary.get("gpu_operator_action_required") is True),
        "gpu_return_receipt_ready": bool(summary.get("gpu_return_receipt_ready") is True),
        "gpu_receipt_expected_queue_rows": int(summary.get("gpu_receipt_expected_queue_rows") or 0),
        "gpu_receipt_expected_npz_count": int(summary.get("gpu_receipt_expected_npz_count") or 0),
        "gpu_receipt_manifest_row_count": int(summary.get("gpu_receipt_manifest_row_count") or 0),
        "gpu_receipt_manifest_ok_row_count": int(summary.get("gpu_receipt_manifest_ok_row_count") or 0),
        "gpu_receipt_manifest_identity_row_count": int(summary.get("gpu_receipt_manifest_identity_row_count") or 0),
        "gpu_receipt_manifest_matched_queue_id_count": int(
            summary.get("gpu_receipt_manifest_matched_queue_id_count") or 0
        ),
        "gpu_receipt_manifest_matched_expected_npz_count": int(
            summary.get("gpu_receipt_manifest_matched_expected_npz_count") or 0
        ),
        "gpu_receipt_manifest_matched_queue_fingerprint_count": int(
            summary.get("gpu_receipt_manifest_matched_queue_fingerprint_count") or 0
        ),
        "gpu_receipt_manifest_operator_verified": bool(
            summary.get("gpu_receipt_manifest_operator_verified") is True
        ),
        "gpu_receipt_operator_verified_true_count": int(summary.get("gpu_receipt_operator_verified_true_count") or 0),
        "gpu_receipt_identity_coverage_ready": bool(summary.get("gpu_receipt_identity_coverage_ready") is True),
        "post_return_promotion_ladder_stage_count": int(
            summary.get("post_return_promotion_ladder_stage_count") or 0
        ),
        "post_return_promotion_ladder_ready_stage_count": int(
            summary.get("post_return_promotion_ladder_ready_stage_count") or 0
        ),
        "post_return_promotion_ladder_blocked_stage_count": int(
            summary.get("post_return_promotion_ladder_blocked_stage_count") or 0
        ),
        "post_return_promotion_ladder_stage_ids": list(
            summary.get("post_return_promotion_ladder_stage_ids") or []
        ),
        "ready_key_alias_used_count": int(summary.get("ready_key_alias_used_count") or 0),
        "ready_key_alias_used_stage_ids": list(summary.get("ready_key_alias_used_stage_ids") or []),
        "blocked_stage_ids": list(summary.get("blocked_stage_ids") or []),
        "first_blocked_stage_id": summary.get("first_blocked_stage_id", ""),
        "first_blocked_stage_artifact": summary.get("first_blocked_stage_artifact", ""),
        "first_blocked_stage_ready_key": summary.get("first_blocked_stage_ready_key", ""),
        "first_blocked_stage_observed_value": summary.get("first_blocked_stage_observed_value"),
        "checkpoint_failed_check_ids": list(summary.get("checkpoint_failed_check_ids") or []),
        "checkpoint_closure_blockers": list(summary.get("checkpoint_closure_blockers") or []),
        "checkpoint_missing_output_fields": list(summary.get("checkpoint_missing_output_fields") or []),
        "checkpoint_missing_adapter_output_policy_fields": list(
            summary.get("checkpoint_missing_adapter_output_policy_fields") or []
        ),
        "selected_sidecar_ready": bool(summary.get("selected_sidecar_ready") is True),
        "selected_sidecar_status": summary.get("selected_sidecar_status", ""),
        "selected_sidecar_blockers": list(summary.get("selected_sidecar_blockers") or []),
        "selected_sidecar_missing_output_fields": list(summary.get("selected_sidecar_missing_output_fields") or []),
        "training_data_failed_check_ids": list(summary.get("training_data_failed_check_ids") or []),
        "training_data_missing_output_labels": list(summary.get("training_data_missing_output_labels") or []),
        "force_gpu_worker_full_regeneration_command": summary.get("force_gpu_worker_full_regeneration_command", ""),
        "force_gpu_worker_post_return_validation_command": summary.get(
            "force_gpu_worker_post_return_validation_command", ""
        ),
        "force_gpu_worker_post_run_validation_command_count": int(
            summary.get("force_gpu_worker_post_run_validation_command_count") or 0
        ),
        "force_gpu_worker_post_run_validation_commands": list(
            summary.get("force_gpu_worker_post_run_validation_commands") or []
        ),
        "promotion_stages": rows,
        "blockers": blockers,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/production-ai-registry-promotion-operator-receipt")
async def get_product_production_ai_registry_promotion_operator_receipt() -> dict[str, Any]:
    packet = _read_json_object(PRODUCTION_AI_REGISTRY_PROMOTION_OPERATOR_RECEIPT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_production_ai_registry_promotion_operator_receipt",
            "artifact_path": str(PRODUCTION_AI_REGISTRY_PROMOTION_OPERATOR_RECEIPT_ARTIFACT),
            "operator_receipt_ready": False,
            "receipt_csv": "",
            "receipt_present": False,
            "receipt_row_count": 0,
            "pass_row_count": 0,
            "blocked_row_count": 0,
            "first_blocked_artifact_id": "",
            "first_blocked_row_blocker": "",
            "first_blocked_row_blockers": [],
            "most_common_row_blocker": "",
            "approval_token_required": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",
            "registry_artifact": "",
            "registry_artifact_present": False,
            "checkpoint_readiness_artifact": "",
            "checkpoint_readiness_artifact_present": False,
            "registry_promotion_required_gate_ids": [],
            "observed_registry_default_residual_mode": "",
            "observed_registry_production_promotion_allowed": False,
            "observed_registry_customer_facing_auto_correction_allowed": False,
            "observed_registry_customer_facing_score_mutation_allowed": False,
            "observed_registry_customer_facing_ranking_mutation_allowed": False,
            "observed_registry_trained_model_checkpoint_count": 0,
            "observed_checkpoint_registry_promotion_currently_satisfied": False,
            "observed_checkpoint_registry_promotion_missing_gate_ids": [],
            "blocker_count": 1,
            "blockers": [],
            "receipt_rows": [],
            "next_required_step": "",
            "registry_edited_by_this_tool": False,
            "checkpoint_created_by_this_tool": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "model_promoted": False,
            "claim_boundary": (
                "Production AI registry promotion operator receipt endpoint only; the local receipt artifact is "
                "missing or invalid. It does not edit the registry, create checkpoints, enable customer-facing "
                "mutation, run GPU jobs, deploy, upload, email, delete, commit, push, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCTION_AI_REGISTRY_PROMOTION_OPERATOR_RECEIPT_ARTIFACT),
        "operator_receipt_ready": bool(summary.get("operator_receipt_ready") is True),
        "receipt_csv": summary.get("receipt_csv", ""),
        "receipt_present": bool(summary.get("receipt_present") is True),
        "receipt_row_count": int(summary.get("receipt_row_count") or 0),
        "pass_row_count": int(summary.get("pass_row_count") or 0),
        "blocked_row_count": int(summary.get("blocked_row_count") or 0),
        "first_blocked_artifact_id": summary.get("first_blocked_artifact_id", ""),
        "first_blocked_row_blocker": summary.get("first_blocked_row_blocker", ""),
        "first_blocked_row_blockers": list(summary.get("first_blocked_row_blockers") or []),
        "most_common_row_blocker": summary.get("most_common_row_blocker", ""),
        "approval_token_required": summary.get(
            "approval_token_required", "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
        ),
        "registry_artifact": summary.get("registry_artifact", ""),
        "registry_artifact_present": bool(summary.get("registry_artifact_present") is True),
        "checkpoint_readiness_artifact": summary.get("checkpoint_readiness_artifact", ""),
        "checkpoint_readiness_artifact_present": bool(
            summary.get("checkpoint_readiness_artifact_present") is True
        ),
        "registry_promotion_required_gate_ids": list(
            summary.get("registry_promotion_required_gate_ids") or []
        ),
        "observed_registry_default_residual_mode": summary.get(
            "observed_registry_default_residual_mode", ""
        ),
        "observed_registry_production_promotion_allowed": bool(
            summary.get("observed_registry_production_promotion_allowed") is True
        ),
        "observed_registry_customer_facing_auto_correction_allowed": bool(
            summary.get("observed_registry_customer_facing_auto_correction_allowed") is True
        ),
        "observed_registry_customer_facing_score_mutation_allowed": bool(
            summary.get("observed_registry_customer_facing_score_mutation_allowed") is True
        ),
        "observed_registry_customer_facing_ranking_mutation_allowed": bool(
            summary.get("observed_registry_customer_facing_ranking_mutation_allowed") is True
        ),
        "observed_registry_trained_model_checkpoint_count": int(
            summary.get("observed_registry_trained_model_checkpoint_count") or 0
        ),
        "observed_checkpoint_registry_promotion_currently_satisfied": bool(
            summary.get("observed_checkpoint_registry_promotion_currently_satisfied") is True
        ),
        "observed_checkpoint_registry_promotion_missing_gate_ids": list(
            summary.get("observed_checkpoint_registry_promotion_missing_gate_ids") or []
        ),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": list(summary.get("blockers") or []),
        "receipt_rows": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "registry_edited_by_this_tool": bool(summary.get("registry_edited_by_this_tool") is True),
        "checkpoint_created_by_this_tool": bool(
            summary.get("checkpoint_created_by_this_tool") is True
        ),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "model_promoted": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/production-ai-registry-promotion-priority")
async def get_product_production_ai_registry_promotion_priority() -> dict[str, Any]:
    packet = _read_json_object(PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_production_ai_registry_promotion_priority_packet",
            "artifact_path": str(PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_ARTIFACT),
            "priority_packet_ready": False,
            "registry_promotion_ready": False,
            "operator_receipt_ready": False,
            "operator_receipt_status": "",
            "priority_item_count": 0,
            "operator_input_required_count": 0,
            "blocked_priority_item_count": 0,
            "required_gate_count": 0,
            "registry_promotion_missing_gate_ids": [],
            "registry_promotion_missing_gate_count": 0,
            "observed_checkpoint_registry_promotion_missing_gate_ids": [],
            "observed_workbench_registry_promotion_missing_gate_ids": [],
            "top_gate_id": "",
            "top_priority_bucket": "",
            "top_required_input": "",
            "top_acceptance_artifact": "",
            "top_verification_command": "",
            "top_next_operator_step": "",
            "operator_receipt_csv": "",
            "operator_receipt_csv_present": False,
            "operator_receipt_artifact": "",
            "operator_receipt_artifact_present": False,
            "residual_registry_artifact": "",
            "residual_registry_artifact_present": False,
            "checkpoint_readiness_artifact": "",
            "checkpoint_readiness_artifact_present": False,
            "promotion_workbench_artifact": "",
            "promotion_workbench_artifact_present": False,
            "observed_registry_default_residual_mode": "",
            "observed_registry_trained_model_checkpoint_count": 0,
            "observed_registry_production_promotion_allowed": False,
            "observed_registry_customer_facing_mutation_flags_ready": False,
            "observed_checkpoint_registry_promotion_currently_satisfied": False,
            "approval_token_required": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",
            "approval_token_count": 0,
            "blocker_count": 1,
            "blockers": ["production_ai_registry_promotion_priority_packet_missing"],
            "source_artifacts": [],
            "top_priority_items": [],
            "priority_items": [],
            "next_required_step": (
                "Run python3 tools/product/build_production_ai_registry_promotion_priority_packet.py."
            ),
            "registry_edited_by_this_tool": False,
            "checkpoint_created_by_this_tool": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "model_promoted": False,
            "customer_facing_mutation_enabled": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Production AI registry promotion priority endpoint only; the local priority packet is missing. "
                "It does not edit the registry, create checkpoints, enable customer-facing mutation, promote "
                "models, run GPU jobs, deploy, upload, email, delete, commit, push, or mutate external state."
            ),
        }
    sorted_rows = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=lambda row: int(row.get("priority") or 999999),
    )
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCTION_AI_REGISTRY_PROMOTION_PRIORITY_ARTIFACT),
        "priority_packet_ready": bool(summary.get("priority_packet_ready") is True),
        "registry_promotion_ready": bool(summary.get("registry_promotion_ready") is True),
        "operator_receipt_ready": bool(summary.get("operator_receipt_ready") is True),
        "operator_receipt_status": summary.get("operator_receipt_status", ""),
        "priority_item_count": int(summary.get("priority_item_count") or 0),
        "operator_input_required_count": int(summary.get("operator_input_required_count") or 0),
        "blocked_priority_item_count": int(summary.get("blocked_priority_item_count") or 0),
        "required_gate_count": int(summary.get("required_gate_count") or 0),
        "registry_promotion_missing_gate_ids": list(
            summary.get("registry_promotion_missing_gate_ids") or []
        ),
        "registry_promotion_missing_gate_count": int(
            summary.get("registry_promotion_missing_gate_count") or 0
        ),
        "observed_checkpoint_registry_promotion_missing_gate_ids": list(
            summary.get("observed_checkpoint_registry_promotion_missing_gate_ids") or []
        ),
        "observed_workbench_registry_promotion_missing_gate_ids": list(
            summary.get("observed_workbench_registry_promotion_missing_gate_ids") or []
        ),
        "top_gate_id": summary.get("top_gate_id", ""),
        "top_priority_bucket": summary.get("top_priority_bucket", ""),
        "top_required_input": summary.get("top_required_input", ""),
        "top_acceptance_artifact": summary.get("top_acceptance_artifact", ""),
        "top_verification_command": summary.get("top_verification_command", ""),
        "top_next_operator_step": summary.get("top_next_operator_step", ""),
        "operator_receipt_csv": summary.get("operator_receipt_csv", ""),
        "operator_receipt_csv_present": bool(summary.get("operator_receipt_csv_present") is True),
        "operator_receipt_artifact": summary.get("operator_receipt_artifact", ""),
        "operator_receipt_artifact_present": bool(
            summary.get("operator_receipt_artifact_present") is True
        ),
        "residual_registry_artifact": summary.get("residual_registry_artifact", ""),
        "residual_registry_artifact_present": bool(
            summary.get("residual_registry_artifact_present") is True
        ),
        "checkpoint_readiness_artifact": summary.get("checkpoint_readiness_artifact", ""),
        "checkpoint_readiness_artifact_present": bool(
            summary.get("checkpoint_readiness_artifact_present") is True
        ),
        "promotion_workbench_artifact": summary.get("promotion_workbench_artifact", ""),
        "promotion_workbench_artifact_present": bool(
            summary.get("promotion_workbench_artifact_present") is True
        ),
        "observed_registry_default_residual_mode": summary.get(
            "observed_registry_default_residual_mode", ""
        ),
        "observed_registry_trained_model_checkpoint_count": int(
            summary.get("observed_registry_trained_model_checkpoint_count") or 0
        ),
        "observed_registry_production_promotion_allowed": bool(
            summary.get("observed_registry_production_promotion_allowed") is True
        ),
        "observed_registry_customer_facing_mutation_flags_ready": bool(
            summary.get("observed_registry_customer_facing_mutation_flags_ready") is True
        ),
        "observed_checkpoint_registry_promotion_currently_satisfied": bool(
            summary.get("observed_checkpoint_registry_promotion_currently_satisfied") is True
        ),
        "approval_token_required": summary.get(
            "approval_token_required", "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
        ),
        "approval_token_count": int(summary.get("approval_token_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": list(summary.get("blockers") or []),
        "source_artifacts": list(summary.get("source_artifacts") or []),
        "top_priority_items": sorted_rows[:2],
        "priority_items": sorted_rows,
        "next_required_step": summary.get("next_required_step", ""),
        "registry_edited_by_this_tool": bool(summary.get("registry_edited_by_this_tool") is True),
        "checkpoint_created_by_this_tool": bool(
            summary.get("checkpoint_created_by_this_tool") is True
        ),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "customer_facing_mutation_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
