from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.api_contract import EXPECTED_ROUTES
from betelgeuze_product.api_contract import REQUIRED_STATUS_DOMAIN_KEYS
from tools import build_product_api_contract as mod


def test_build_product_api_contract_tool_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "product_api_contract.json"
    out_csv = tmp_path / "product_api_contract.csv"
    out_md = tmp_path / "product_api_contract.md"

    mod.main(
        [
            "--root",
            ".",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "product_api_contract_ready"
    assert payload["summary"]["api_contract_ready"] is True
    assert payload["summary"]["docking_response_missing_key_count"] == 0
    docking_response = mod.build_product_api_contract.__globals__[
        "REQUIRED_DOCKING_RESPONSE_KEYS"
    ]
    assert "ai_decision_graph_trace_ready" in docking_response
    assert "ai_decision_graph_ordered_path" in docking_response
    assert "ai_decision_graph_node_count" in docking_response
    assert "ai_decision_graph_edge_count" in docking_response
    assert "ai_decision_graph_abstention_node_id" in docking_response
    assert "ai_decision_graph_current_node_id" in docking_response
    assert "ai_decision_graph_trace" in docking_response
    assert "ai_decision_graph_edges" in docking_response
    assert "workflow_controls_ready" in docking_response
    assert "workflow_control_links" in docking_response
    assert "workflow_allowed_actions" in docking_response
    assert "workflow_disabled_actions" in docking_response
    assert "workflow_next_customer_actions" in docking_response
    assert "status_transition_contract" in docking_response
    assert "customer_report_card_ready" in docking_response
    assert "customer_report_delivery_contract_ready" in docking_response
    assert "customer_report_evidence_binding_ready" in docking_response
    assert "customer_report_required_block_count" in docking_response
    assert "customer_report_ready_block_count" in docking_response
    assert "customer_report_blocked_block_count" in docking_response
    assert "customer_report_section_count" in docking_response
    assert "customer_report_required_blocks" in docking_response
    assert "customer_report_card" in docking_response
    assert "customer_report_sections" in docking_response
    assert EXPECTED_ROUTES["get_product_trajectory_sla_contract"] == ("GET", "/trajectory-sla-contract")
    trajectory_sla_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_trajectory_sla_contract"]
    assert "sla_claim_tier" in trajectory_sla_keys
    assert "broad_platform_sla_allowed" in trajectory_sla_keys
    assert "allowed_sla_claims" in trajectory_sla_keys
    assert "blocked_sla_claims" in trajectory_sla_keys
    assert "customer_sla_disclosure_card" in trajectory_sla_keys
    assert "customer_sla_disclosure_ready" in trajectory_sla_keys
    assert "general_platform_sla_allowed" in trajectory_sla_keys
    assert "current_rocm_baseline_claim_scope" in trajectory_sla_keys
    assert "current_rocm_baseline_production_trajectory_profile_enabled" in trajectory_sla_keys
    assert "family_sla_matrix" in trajectory_sla_keys
    assert EXPECTED_ROUTES["get_product_security_deployment_contract"] == (
        "GET",
        "/security-deployment-contract",
    )
    security_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_security_deployment_contract"]
    assert "security_deployment_ready" in security_keys
    assert "hosted_deployment_contract_ready" in security_keys
    assert "hosted_deployment_currently_satisfied" in security_keys
    assert "hosted_external_exposure_allowed" in security_keys
    assert "hosted_deployment_blocked_stage_ids" in security_keys
    assert EXPECTED_ROUTES["get_product_job_orchestration_contract"] == (
        "GET",
        "/job-orchestration-contract",
    )
    job_orchestration_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_job_orchestration_contract"]
    assert "product_job_orchestration_contract_ready" in job_orchestration_keys
    assert "queue_lifecycle_progress_ready" in job_orchestration_keys
    assert "customer_run_history_lineage_ready" in job_orchestration_keys
    assert "rerun_manifest_ready" in job_orchestration_keys
    assert "long_running_status_persistence_ready" in job_orchestration_keys
    assert "worker_backend_contract_ready" in job_orchestration_keys
    assert "worker_lease_heartbeat_ready" in job_orchestration_keys
    assert "retryable_failure_resume_ready" in job_orchestration_keys
    assert "running_cancel_ack_ready" in job_orchestration_keys
    assert "stale_worker_lease_recovery_ready" in job_orchestration_keys
    assert "stale_worker_lease_sweep_ready" in job_orchestration_keys
    assert "stale_worker_lease_detected_count" in job_orchestration_keys
    assert "retryable_after_stale_count" in job_orchestration_keys
    assert EXPECTED_ROUTES["get_product_scope_breadth_contract"] == ("GET", "/scope-breadth-contract")
    scope_breadth_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_scope_breadth_contract"]
    assert "ready_domains" in scope_breadth_keys
    assert "missing_domains" in scope_breadth_keys
    assert "first_blocked_domain" in scope_breadth_keys
    assert "first_blocked_domain_artifact" in scope_breadth_keys
    assert "first_blocked_domain_next_action" in scope_breadth_keys
    assert "transporter_p0_closure_packet_ready" in scope_breadth_keys
    assert "transporter_p0_current_membrane_open_count" in scope_breadth_keys
    assert "transporter_p0_closure_row_count" in scope_breadth_keys
    assert "transporter_p0_next_required_step" in scope_breadth_keys
    assert "transporter_p0_readiness_matrix_ready" in scope_breadth_keys
    assert "transporter_p0_auto_close_ready_artifact_count" in scope_breadth_keys
    assert "transporter_p0_manual_or_external_required_artifact_count" in scope_breadth_keys
    assert "transporter_p0_unresolved_slot_count" in scope_breadth_keys
    assert "transporter_p0_first_manual_or_external_required_action" in scope_breadth_keys
    assert "transporter_p0_evidence_acquisition_next_slot_completion_packet" in scope_breadth_keys
    assert (
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count"
        in scope_breadth_keys
    )
    assert "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix" in scope_breadth_keys
    assert "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id" in scope_breadth_keys
    assert "transporter_p0_evidence_acquisition_next_slot_id" in scope_breadth_keys
    assert "transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready" in scope_breadth_keys
    assert "transporter_p0_evidence_acquisition_next_slot_source_modality" in scope_breadth_keys
    assert (
        "transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed"
        in scope_breadth_keys
    )
    assert "transporter_p0_evidence_acquisition_next_slot_source_modality_decision" in scope_breadth_keys
    assert (
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_ready"
        in scope_breadth_keys
    )
    assert (
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result"
        in scope_breadth_keys
    )
    assert (
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_replacement_reference_binding_kcal_mol_action"
        in scope_breadth_keys
    )
    assert "evidence_queue_next_operator_completion_aqp1_review_sidecar_ready" in scope_breadth_keys
    assert "evidence_queue_next_operator_completion_aqp1_review_candidate_name" in scope_breadth_keys
    assert (
        "evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed"
        in scope_breadth_keys
    )
    intake_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_scope_evidence_intake_readiness"]
    assert "transporter_manual_review_p0_slot_overlay_row_count" in intake_keys
    assert "transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id" in intake_keys
    assert "first_review_item_id" in intake_keys
    assert "first_review_direct_binding_source_url_or_doi" in intake_keys
    assert "first_review_p0_slot_overlay_required_missing_fields" in intake_keys
    assert "first_review_p0_slot_overlay_scope_promotion_allowed" in intake_keys
    assert "next_operator_completion_item_id" in intake_keys
    assert "next_operator_completion_required_evidence_type" in intake_keys
    assert "next_operator_completion_required_intake_columns" in intake_keys
    assert "next_operator_completion_review_template_artifact" in intake_keys
    assert "next_operator_completion_operator_packet_binding_ready" in intake_keys
    assert "next_operator_completion_transporter_claim_safe_blocker" in intake_keys
    assert "scope_operator_transfer_manifest_ready" in intake_keys
    assert "scope_operator_transfer_outbound_artifact_count" in intake_keys
    assert "scope_operator_transfer_inbound_artifact_count" in intake_keys
    assert "scope_operator_transfer_first_return_artifact" in intake_keys
    assert "scope_operator_transfer_acceptance_artifact" in intake_keys
    assert "scope_operator_transfer_post_return_validation_command" in intake_keys
    manual_review_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_transporter_manual_review_intake"]
    assert "p0_slot_overlay_row_count" in manual_review_keys
    assert "p0_slot_overlay_first_candidate_ligand_id" in manual_review_keys
    assert "first_review_item_id" in manual_review_keys
    assert "first_review_candidate_ligand_id" in manual_review_keys
    assert "first_review_direct_binding_source_url_or_doi" in manual_review_keys
    assert "first_review_review_decision" in manual_review_keys
    assert "first_review_p0_slot_overlay_required_missing_fields" in manual_review_keys
    assert "first_review_p0_slot_overlay_scope_promotion_allowed" in manual_review_keys
    assert EXPECTED_ROUTES["get_product_aqp1_operator_validation_candidate"] == (
        "GET",
        "/aqp1-operator-validation-candidate",
    )
    aqp1_candidate_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_aqp1_operator_validation_candidate"]
    assert "candidate_claim_safe_ready_count" in aqp1_candidate_keys
    assert "operator_validation_required_count" in aqp1_candidate_keys
    assert "first_candidate_ligand_external_identifier" in aqp1_candidate_keys
    assert "first_candidate_reference_binding_kcal_mol" in aqp1_candidate_keys
    assert "first_candidate_claim_safe_ready" in aqp1_candidate_keys
    assert "claim_promotion_allowed" in aqp1_candidate_keys
    assert "authoritative_apply_allowed" in aqp1_candidate_keys
    assert EXPECTED_ROUTES["get_product_aqp1_direct_binding_procurement_packet"] == (
        "GET",
        "/aqp1-direct-binding-procurement-packet",
    )
    aqp1_procurement_keys = REQUIRED_STATUS_DOMAIN_KEYS[
        "get_product_aqp1_direct_binding_procurement_packet"
    ]
    assert "procurement_packet_ready" in aqp1_procurement_keys
    assert "direct_binding_gap_open" in aqp1_procurement_keys
    assert "external_primary_evidence_required" in aqp1_procurement_keys
    assert "accepted_direct_binding_methods" in aqp1_procurement_keys
    assert "minimum_acceptance_rule" in aqp1_procurement_keys
    assert "first_required_external_action_id" in aqp1_procurement_keys
    assert "evidence_queue_pxr_exact_review_sidecar_row_count" in scope_breadth_keys
    assert "evidence_queue_next_pxr_exact_review_sidecar_ready" in scope_breadth_keys
    assert "evidence_queue_next_pxr_exact_review_candidate_name" in scope_breadth_keys
    assert "evidence_queue_next_pxr_exact_review_required_evidence_mode" in scope_breadth_keys
    assert "evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol" in scope_breadth_keys
    assert "pxr_exact_review_next_review_return_bundle_required_artifact_count" in scope_breadth_keys
    assert "pxr_exact_review_next_review_return_bundle_completion_matrix" in scope_breadth_keys
    assert "pxr_exact_review_next_review_return_bundle_next_artifact_id" in scope_breadth_keys
    assert "scope_acceptance_matrix" in scope_breadth_keys
    assert "scope_acceptance_stage_evidence_matrix" in scope_breadth_keys
    assert "scope_acceptance_current_blocked_stage_evidence_matrix" in scope_breadth_keys
    assert "scope_acceptance_next_stage_id" in scope_breadth_keys
    assert EXPECTED_ROUTES["get_product_residual_model_registry"] == ("GET", "/residual-model-registry")
    registry_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_residual_model_registry"]
    assert "product_model_layer_ready" in registry_keys
    assert "production_ai_inference_subject_active" in registry_keys
    assert "default_residual_mode" in registry_keys
    assert "production_promotion_allowed" in registry_keys
    assert "trained_model_checkpoint_count" in registry_keys
    assert "selected_sidecar_missing_output_fields" in registry_keys
    checkpoint_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_production_ai_checkpoint_readiness"]
    assert "first_failed_check_id" in checkpoint_keys
    assert "first_failed_source_artifact" in checkpoint_keys
    assert "first_failed_observed" in checkpoint_keys
    assert "first_failed_required" in checkpoint_keys
    assert "first_failed_next_action" in checkpoint_keys
    assert "production_inference_actionable_blocker_stage_id" in checkpoint_keys
    assert "production_inference_actionable_blocker_check_id" in checkpoint_keys
    assert "production_inference_actionable_blocker_next_action" in checkpoint_keys
    assert "production_inference_actionable_blocker_downstream_blocked_stage_count" in checkpoint_keys
    assert "production_inference_actionable_blocker_blocks_registry_promotion" in checkpoint_keys
    assert "production_inference_actionable_operator_completion_packet_ready" in checkpoint_keys
    assert "production_inference_actionable_operator_completion_artifact_id" in checkpoint_keys
    assert "production_inference_actionable_operator_completion_required_fields_or_columns" in checkpoint_keys
    assert "production_inference_actionable_operator_completion_diagnostic_commands" in checkpoint_keys
    assert "production_inference_actionable_operator_completion_diagnostic_completion_rule" in checkpoint_keys
    assert "production_inference_actionable_operator_completion_torch_visibility_probe_command" in checkpoint_keys
    assert "production_inference_actionable_operator_completion_packet" in checkpoint_keys
    assert "production_inference_worker_runtime_receipt_contract_ready" in checkpoint_keys
    assert "production_inference_worker_runtime_receipt_required_fields_or_columns" in checkpoint_keys
    assert "production_inference_worker_runtime_receipt_completion_rule" in checkpoint_keys
    assert "production_inference_worker_runtime_receipt_post_environment_next_stage_id" in checkpoint_keys
    assert "production_inference_worker_runtime_receipt_guardrails" in checkpoint_keys
    assert "production_gpu_execution_environment_ready" in checkpoint_keys
    assert EXPECTED_ROUTES["get_product_production_ai_gpu_worker_dispatch_manifest"] == (
        "GET",
        "/production-ai-gpu-worker-dispatch-manifest",
    )
    gpu_dispatch_keys = REQUIRED_STATUS_DOMAIN_KEYS[
        "get_product_production_ai_gpu_worker_dispatch_manifest"
    ]
    assert "dispatch_manifest_ready" in gpu_dispatch_keys
    assert "local_artifact_missing_count" in gpu_dispatch_keys
    assert "native_pdb_dependency_count" in gpu_dispatch_keys
    assert "acceptance_contract" in gpu_dispatch_keys
    assert "return_manifest_required_identity_rule" in gpu_dispatch_keys
    assert "worker_rocm_manifest_completion_rule" in gpu_dispatch_keys
    assert EXPECTED_ROUTES["get_product_production_ai_gpu_worker_dispatch_bundle"] == (
        "GET",
        "/production-ai-gpu-worker-dispatch-bundle",
    )
    gpu_bundle_keys = REQUIRED_STATUS_DOMAIN_KEYS[
        "get_product_production_ai_gpu_worker_dispatch_bundle"
    ]
    assert "dispatch_bundle_ready" in gpu_bundle_keys
    assert "bundle_tar_sha256" in gpu_bundle_keys
    assert "bundle_member_count" in gpu_bundle_keys
    assert "source_artifact_count" in gpu_bundle_keys
    assert "acceptance_contract" in gpu_bundle_keys
    assert EXPECTED_ROUTES["get_product_production_ai_gpu_worker_execution_runbook"] == (
        "GET",
        "/production-ai-gpu-worker-execution-runbook",
    )
    gpu_runbook_keys = REQUIRED_STATUS_DOMAIN_KEYS[
        "get_product_production_ai_gpu_worker_execution_runbook"
    ]
    assert "execution_runbook_ready" in gpu_runbook_keys
    assert "worker_script_path" in gpu_runbook_keys
    assert "worker_script_executable" in gpu_runbook_keys
    assert "return_packager_script_path" in gpu_runbook_keys
    assert "return_packager_script_executable" in gpu_runbook_keys
    assert "return_bundle_tar_path" in gpu_runbook_keys
    assert "manifest_npz_path_columns" in gpu_runbook_keys
    assert "return_packager_command" in gpu_runbook_keys
    assert "required_return_artifacts" in gpu_runbook_keys
    assert "post_return_validation_command" in gpu_runbook_keys
    assert "production_gpu_rocm_visible_device_count" in checkpoint_keys
    assert "production_gpu_rocm_visibility_diagnostic_commands" in checkpoint_keys
    assert "production_gpu_rocm_visibility_diagnostic_completion_rule" in checkpoint_keys
    assert "production_gpu_rocm_next_required_step" in checkpoint_keys
    gpu_return_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_production_ai_gpu_return_intake"]
    assert "summary_template_payload" in gpu_return_keys
    assert "summary_template_required_fields" in gpu_return_keys
    assert "summary_template_completion_rule" in gpu_return_keys
    assert "summary_template_backend_provenance_contract_ready" in gpu_return_keys
    assert "summary_template_required_backend_provenance_fields" in gpu_return_keys
    assert "summary_template_backend_provenance_completion_rule" in gpu_return_keys
    assert "worker_rocm_manifest_ready" in gpu_return_keys
    assert "worker_rocm_visible_device_count" in gpu_return_keys
    assert "worker_rocm_manifest_completion_rule" in gpu_return_keys
    assert "operator_return_artifact_completion_matrix" in gpu_return_keys
    assert "operator_return_artifact_completion_blocker_matrix" in gpu_return_keys
    assert "operator_return_next_artifact_completion_packet" in gpu_return_keys
    assert "operator_return_next_artifact_id" in gpu_return_keys
    pxr_review_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_pxr_exact_review_intake"]
    assert "next_review_completion_packet" in pxr_review_keys
    assert "next_review_return_bundle_required_artifact_count" in pxr_review_keys
    assert "next_review_return_bundle_completion_matrix" in pxr_review_keys
    assert "next_review_return_bundle_next_artifact_id" in pxr_review_keys
    assert "next_review_row_id" in pxr_review_keys
    assert "next_review_candidate_name" in pxr_review_keys
    assert EXPECTED_ROUTES["get_product_commercial_readiness_operator_packet"] == (
        "GET",
        "/commercial-readiness-operator-packet",
    )
    operator_packet_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_commercial_readiness_operator_packet"]
    assert "packet_ready" in operator_packet_keys
    assert "goal_audit_sha256" in operator_packet_keys
    assert "commercial_readiness_matrix_sha256" in operator_packet_keys
    assert "source_fingerprint_ready" in operator_packet_keys
    assert "actions" in operator_packet_keys
    assert "operator_completion_packets" in operator_packet_keys
    assert "first_execution_command" in operator_packet_keys
    assert "parallelizable_action_count" in operator_packet_keys
    assert "first_parallelizable_action_id" in operator_packet_keys
    assert "first_parallelizable_action_required_exact_evidence_fields" in operator_packet_keys
    assert "first_parallelizable_action_operator_review_artifact" in operator_packet_keys
    assert "first_parallelizable_action_acceptance_gate_commands" in operator_packet_keys
    assert "first_parallelizable_action_lane_id" in operator_packet_keys
    assert (
        "first_parallelizable_action_next_slot_source_modality_decision"
        in operator_packet_keys
    )
    assert (
        "first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed"
        in operator_packet_keys
    )
    assert (
        "first_operator_completion_worker_runtime_receipt_contract_ready"
        in operator_packet_keys
    )
    assert (
        "first_operator_completion_worker_runtime_receipt_required_fields_or_columns"
        in operator_packet_keys
    )
    assert (
        "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact"
        in operator_packet_keys
    )
    assert "first_operator_completion_diagnostic_commands" in operator_packet_keys
    assert "first_operator_completion_diagnostic_completion_rule" in operator_packet_keys
    assert "first_operator_completion_torch_visibility_probe_command" in operator_packet_keys
    assert "production_ai_return_action_id" in operator_packet_keys
    assert "production_ai_return_operator_completion_artifact_path" in operator_packet_keys
    assert "production_ai_return_operator_completion_completion_rule" in operator_packet_keys
    assert (
        "production_ai_return_operator_completion_backend_provenance_completion_rule"
        in operator_packet_keys
    )
    assert "production_ai_return_bundle_required_artifacts" in operator_packet_keys
    assert "production_ai_return_bundle_next_artifact_failed_check_ids" in operator_packet_keys
    assert "production_ai_return_bundle_manifest_required_columns" in operator_packet_keys
    assert "production_ai_return_bundle_post_return_validation_command" in operator_packet_keys
    assert "checkpoint_promoted" in operator_packet_keys
    assert EXPECTED_ROUTES["get_product_commercial_readiness_operator_packet_freshness"] == (
        "GET",
        "/commercial-readiness-operator-packet-freshness",
    )
    operator_freshness_keys = REQUIRED_STATUS_DOMAIN_KEYS[
        "get_product_commercial_readiness_operator_packet_freshness"
    ]
    assert "freshness_ready" in operator_freshness_keys
    assert "current_goal_audit_sha256" in operator_freshness_keys
    assert "operator_goal_audit_sha256" in operator_freshness_keys
    assert "current_commercial_readiness_matrix_sha256" in operator_freshness_keys
    assert "operator_commercial_readiness_matrix_sha256" in operator_freshness_keys
    assert "command_references_ready" in operator_freshness_keys
    assert "operator_python_tool_reference_count" in operator_freshness_keys
    assert "operator_missing_python_tool_reference_count" in operator_freshness_keys
    assert "operator_missing_python_tool_references" in operator_freshness_keys
    assert "failed_check_ids" in operator_freshness_keys
    assert EXPECTED_ROUTES["get_product_commercial_readiness_execution_ladder"] == (
        "GET",
        "/commercial-readiness-execution-ladder",
    )
    execution_ladder_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_commercial_readiness_execution_ladder"]
    assert "ladder_ready" in execution_ladder_keys
    assert "first_operator_input_artifact" in execution_ladder_keys
    assert "all_preconditions_satisfied" in execution_ladder_keys
    assert "parallelizable_action_count" in execution_ladder_keys
    assert "first_parallelizable_action_id" in execution_ladder_keys
    assert "first_parallelizable_action_required_exact_evidence_fields" in execution_ladder_keys
    assert "first_parallelizable_action_operator_review_artifact" in execution_ladder_keys
    assert "first_parallelizable_action_acceptance_gate_commands" in execution_ladder_keys
    assert "first_parallelizable_action_order" in execution_ladder_keys
    assert (
        "first_parallelizable_action_next_slot_source_modality_decision"
        in execution_ladder_keys
    )
    assert (
        "first_operator_completion_worker_runtime_receipt_contract_ready"
        in execution_ladder_keys
    )
    assert (
        "first_operator_completion_worker_runtime_receipt_post_environment_validation_command"
        in execution_ladder_keys
    )
    assert "first_operator_completion_diagnostic_commands" in execution_ladder_keys
    assert "first_operator_completion_diagnostic_completion_rule" in execution_ladder_keys
    assert "first_operator_completion_torch_visibility_probe_command" in execution_ladder_keys
    assert "production_ai_return_action_id" in execution_ladder_keys
    assert "production_ai_return_operator_completion_artifact_path" in execution_ladder_keys
    assert "production_ai_return_operator_completion_completion_rule" in execution_ladder_keys
    assert (
        "production_ai_return_operator_completion_backend_provenance_completion_rule"
        in execution_ladder_keys
    )
    assert "production_ai_return_bundle_required_artifacts" in execution_ladder_keys
    assert "production_ai_return_bundle_next_artifact_failed_check_ids" in execution_ladder_keys
    assert "production_ai_return_bundle_manifest_required_columns" in execution_ladder_keys
    assert "production_ai_return_bundle_post_return_validation_command" in execution_ladder_keys
    assert "ladder" in execution_ladder_keys
    assert "checkpoint_promoted" in execution_ladder_keys
    assert EXPECTED_ROUTES["get_product_commercial_readiness_handoff_bundle"] == (
        "GET",
        "/commercial-readiness-handoff-bundle",
    )
    handoff_bundle_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_commercial_readiness_handoff_bundle"]
    assert "handoff_bundle_ready" in handoff_bundle_keys
    assert "artifacts" in handoff_bundle_keys
    assert "first_operator_input_artifact" in handoff_bundle_keys
    assert "source_fingerprint_ready" in handoff_bundle_keys
    assert "operator_parallelizable_action_count" in handoff_bundle_keys
    assert "first_parallelizable_action_id" in handoff_bundle_keys
    assert "first_parallelizable_action_required_exact_evidence_fields" in handoff_bundle_keys
    assert "first_parallelizable_action_operator_review_artifact" in handoff_bundle_keys
    assert "first_parallelizable_action_acceptance_gate_commands" in handoff_bundle_keys
    assert "first_parallelizable_action_lane_id" in handoff_bundle_keys
    assert (
        "first_parallelizable_action_next_slot_source_modality_decision"
        in handoff_bundle_keys
    )
    assert (
        "first_operator_completion_worker_runtime_receipt_contract_ready"
        in handoff_bundle_keys
    )
    assert (
        "first_operator_completion_worker_runtime_receipt_post_environment_next_artifact"
        in handoff_bundle_keys
    )
    assert "first_operator_completion_diagnostic_commands" in handoff_bundle_keys
    assert "first_operator_completion_diagnostic_completion_rule" in handoff_bundle_keys
    assert "first_operator_completion_torch_visibility_probe_command" in handoff_bundle_keys
    assert "production_ai_return_action_id" in handoff_bundle_keys
    assert "production_ai_return_operator_completion_artifact_path" in handoff_bundle_keys
    assert "production_ai_return_operator_completion_completion_rule" in handoff_bundle_keys
    assert (
        "production_ai_return_operator_completion_backend_provenance_completion_rule"
        in handoff_bundle_keys
    )
    assert "production_ai_return_bundle_required_artifacts" in handoff_bundle_keys
    assert "production_ai_return_bundle_next_artifact_failed_check_ids" in handoff_bundle_keys
    assert "production_ai_return_bundle_manifest_required_columns" in handoff_bundle_keys
    assert "production_ai_return_bundle_post_return_validation_command" in handoff_bundle_keys
    assert "delta_force_closure_acceptance_packet_artifact" in handoff_bundle_keys
    assert "delta_force_closure_acceptance_packet_ready" in handoff_bundle_keys
    assert "delta_force_closure_ready" in handoff_bundle_keys
    assert "delta_force_closure_failed_stage_count" in handoff_bundle_keys
    assert "delta_force_closure_next_stage_id" in handoff_bundle_keys
    assert "delta_force_closure_next_stage_validation_command" in handoff_bundle_keys
    assert "delta_force_closure_return_summary_required_fields" in handoff_bundle_keys
    assert "scope_closure_acceptance_packet_artifact" in handoff_bundle_keys
    assert "scope_closure_acceptance_packet_ready" in handoff_bundle_keys
    assert "scope_closure_ready" in handoff_bundle_keys
    assert "scope_closure_stage_count" in handoff_bundle_keys
    assert "scope_closure_blocked_stage_count" in handoff_bundle_keys
    assert "scope_closure_next_stage_id" in handoff_bundle_keys
    assert "scope_closure_first_blocked_evidence_row_id" in handoff_bundle_keys
    assert "scope_closure_first_blocked_required_missing_fields" in handoff_bundle_keys
    assert "scope_closure_general_platform_claim_allowed" in handoff_bundle_keys
    assert "artifact_reference_contract_ready" in handoff_bundle_keys
    assert "artifact_reference_count" in handoff_bundle_keys
    assert "artifact_reference_manifest" in handoff_bundle_keys
    assert "local_required_artifact_reference_count" in handoff_bundle_keys
    assert "local_missing_artifact_reference_count" in handoff_bundle_keys
    assert "local_missing_artifact_references" in handoff_bundle_keys
    assert "operator_return_artifact_reference_count" in handoff_bundle_keys
    assert "operator_return_pending_artifact_reference_count" in handoff_bundle_keys
    assert "abstract_artifact_reference_count" in handoff_bundle_keys
    assert "checkpoint_promoted" in handoff_bundle_keys
    goal_completion_keys = REQUIRED_STATUS_DOMAIN_KEYS["get_product_goal_completion_audit"]
    assert "product_ai_trajectory_sla_claim_tier" in goal_completion_keys
    assert "product_ai_trajectory_sla_broad_platform_allowed" in goal_completion_keys
    assert "product_ai_trajectory_sla_current_rocm_baseline_claim_scope" in goal_completion_keys
    assert "product_scope_ready_domains" in goal_completion_keys
    assert "product_scope_missing_domains" in goal_completion_keys
    assert "product_scope_first_blocked_domain" in goal_completion_keys
    assert "product_scope_first_blocked_domain_artifact" in goal_completion_keys
    assert "product_scope_first_blocked_domain_next_action" in goal_completion_keys
    assert "product_scope_evidence_queue_next_operator_completion_slot_id" in goal_completion_keys
    assert (
        "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_fields"
        in goal_completion_keys
    )
    assert (
        "product_scope_evidence_queue_next_operator_completion_acceptance_gate_commands"
        in goal_completion_keys
    )
    assert (
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_sidecar_ready"
        in goal_completion_keys
    )
    assert (
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_candidate_name"
        in goal_completion_keys
    )
    assert (
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_anchor"
        in goal_completion_keys
    )
    assert (
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol"
        in goal_completion_keys
    )
    assert (
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed"
        in goal_completion_keys
    )
    assert (
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank"
        in goal_completion_keys
    )
    assert "product_scope_evidence_queue_pxr_exact_review_sidecar_row_count" in goal_completion_keys
    assert "product_scope_evidence_queue_next_pxr_exact_review_sidecar_ready" in goal_completion_keys
    assert "product_scope_evidence_queue_next_pxr_exact_review_candidate_name" in goal_completion_keys
    assert "product_scope_evidence_queue_next_pxr_exact_review_required_evidence_mode" in goal_completion_keys
    assert (
        "product_scope_evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol"
        in goal_completion_keys
    )
    assert "product_scope_transporter_p0_readiness_matrix_ready" in goal_completion_keys
    assert "product_scope_transporter_p0_auto_close_ready_artifact_count" in goal_completion_keys
    assert "product_scope_transporter_p0_manual_or_external_required_artifact_count" in goal_completion_keys
    assert "product_scope_transporter_p0_unresolved_slot_count" in goal_completion_keys
    assert "product_scope_transporter_p0_first_manual_or_external_required_action" in goal_completion_keys
    assert "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet" in goal_completion_keys
    assert (
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count"
        in goal_completion_keys
    )
    assert (
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix"
        in goal_completion_keys
    )
    assert (
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id"
        in goal_completion_keys
    )
    assert "product_scope_transporter_p0_evidence_acquisition_next_slot_id" in goal_completion_keys
    assert (
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready"
        in goal_completion_keys
    )
    assert (
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality"
        in goal_completion_keys
    )
    assert (
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed"
        in goal_completion_keys
    )
    assert (
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_decision"
        in goal_completion_keys
    )
    assert "product_scope_transporter_manual_review_first_review_item_id" in goal_completion_keys
    assert (
        "product_scope_transporter_manual_review_first_review_direct_binding_source_url_or_doi"
        in goal_completion_keys
    )
    assert (
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_required_missing_fields"
        in goal_completion_keys
    )
    assert (
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_scope_promotion_allowed"
        in goal_completion_keys
    )
    assert "product_scope_pxr_exact_review_next_review_completion_packet" in goal_completion_keys
    assert (
        "product_scope_pxr_exact_review_next_review_return_bundle_required_artifact_count"
        in goal_completion_keys
    )
    assert "product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix" in goal_completion_keys
    assert "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_id" in goal_completion_keys
    assert "product_scope_pxr_exact_review_next_review_row_id" in goal_completion_keys
    assert "product_scope_general_platform_domain_floor_missing_domains" in goal_completion_keys
    assert "product_scope_acceptance_matrix" in goal_completion_keys
    assert "product_scope_acceptance_stage_evidence_matrix" in goal_completion_keys
    assert "product_scope_acceptance_current_blocked_stage_evidence_matrix" in goal_completion_keys
    assert "product_scope_acceptance_release_blocker_stage_ids" in goal_completion_keys
    assert "production_ai_checkpoint_acceptance_matrix" in goal_completion_keys
    assert "production_ai_checkpoint_acceptance_release_blocker_stage_ids" in goal_completion_keys
    assert "production_ai_checkpoint_first_failed_check_id" in goal_completion_keys
    assert "production_ai_checkpoint_first_failed_source_artifact" in goal_completion_keys
    assert "production_ai_checkpoint_first_failed_next_action" in goal_completion_keys
    assert "production_ai_checkpoint_actionable_blocker_stage_id" in goal_completion_keys
    assert "production_ai_checkpoint_actionable_blocker_check_id" in goal_completion_keys
    assert "production_ai_checkpoint_actionable_blocker_next_action" in goal_completion_keys
    assert "production_ai_checkpoint_actionable_blocker_downstream_blocked_stage_count" in goal_completion_keys
    assert "production_ai_checkpoint_actionable_blocker_blocks_registry_promotion" in goal_completion_keys
    assert "production_ai_checkpoint_actionable_operator_completion_packet_ready" in goal_completion_keys
    assert "production_ai_checkpoint_actionable_operator_completion_artifact_id" in goal_completion_keys
    assert (
        "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns"
        in goal_completion_keys
    )
    assert (
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands"
        in goal_completion_keys
    )
    assert (
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_completion_rule"
        in goal_completion_keys
    )
    assert "production_ai_checkpoint_actionable_operator_completion_completion_rule" in goal_completion_keys
    assert "production_ai_checkpoint_actionable_operator_completion_packet" in goal_completion_keys
    assert "production_ai_checkpoint_worker_runtime_receipt_contract_ready" in goal_completion_keys
    assert "production_ai_checkpoint_worker_runtime_receipt_required_fields_or_columns" in goal_completion_keys
    assert "production_ai_checkpoint_worker_runtime_receipt_completion_rule" in goal_completion_keys
    assert "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_stage_id" in goal_completion_keys
    assert "production_ai_checkpoint_worker_runtime_receipt_guardrails" in goal_completion_keys
    assert "production_ai_gpu_return_summary_template_backend_provenance_contract_ready" in goal_completion_keys
    assert "production_ai_gpu_return_summary_template_required_fields" in goal_completion_keys
    assert "production_ai_gpu_return_summary_template_completion_rule" in goal_completion_keys
    assert "production_ai_gpu_return_summary_template_required_backend_provenance_fields" in goal_completion_keys
    assert "production_ai_gpu_return_summary_template_backend_provenance_completion_rule" in goal_completion_keys
    assert "production_ai_gpu_return_operator_return_artifact_completion_matrix" in goal_completion_keys
    assert "production_ai_gpu_return_operator_return_artifact_completion_blocker_matrix" in goal_completion_keys
    assert "production_ai_gpu_return_operator_return_next_artifact_completion_packet" in goal_completion_keys
    assert "production_ai_gpu_return_operator_return_next_artifact_id" in goal_completion_keys
    assert "production_ai_gpu_worker_rocm_manifest_ready" in goal_completion_keys
    assert "production_ai_gpu_worker_rocm_visible_device_count" in goal_completion_keys
    assert "production_ai_gpu_worker_rocm_manifest_completion_rule" in goal_completion_keys
    assert "commercial_readiness_next_action_matrix" in goal_completion_keys
    assert "commercial_readiness_next_action_blocker_matrix" in goal_completion_keys
    assert "commercial_readiness_first_next_action_id" in goal_completion_keys
    assert "commercial_readiness_handoff_bundle_ready" in goal_completion_keys
    assert (
        "commercial_readiness_handoff_bundle_artifact_reference_contract_ready"
        in goal_completion_keys
    )
    assert "commercial_readiness_handoff_bundle_artifact_reference_count" in goal_completion_keys
    assert (
        "commercial_readiness_handoff_bundle_local_missing_artifact_reference_count"
        in goal_completion_keys
    )
    assert (
        "commercial_readiness_handoff_bundle_operator_return_pending_artifact_reference_count"
        in goal_completion_keys
    )
    assert "commercial_readiness_handoff_bundle_first_operator_input_artifact" in goal_completion_keys
    assert "production_ai_residual_model_registry_status" in goal_completion_keys
    assert "production_ai_residual_model_registry_ready" in goal_completion_keys
    assert "production_ai_registry_checkpoint_missing_output_fields" in goal_completion_keys
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Product API Contract" in out_md.read_text(encoding="utf-8")
