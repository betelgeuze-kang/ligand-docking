from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_ai_architecture_gap_closure as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def test_product_ai_architecture_gap_closure_tracks_current_open_gaps() -> None:
    payload = mod.build_product_ai_architecture_gap_closure(
        registry_packet=_packet(
            {
                "product_model_layer_ready": True,
                "default_residual_mode": "shadow",
                "production_promotion_allowed": False,
                "trained_model_checkpoint_count": 0,
            }
        ),
        e2e_packet=_packet(
            {
                "status": "product_end_to_end_rocm_benchmark_ready",
                "benchmark_ready": True,
                "production_trajectory_profile_enabled": False,
                "jobs_per_hour": 10,
                "unique_ligands_per_hour": 2,
                "failure_rate": 0.0,
            }
        ),
        service_boundary_packet=_packet(
            {
                "status": "product_service_boundary_contract_ready",
                "service_boundary_ready": True,
                "api_route_count": 21,
                "missing_api_route_count": 0,
            }
        ),
        api_contract_packet=_packet(
            {
                "status": "product_api_contract_ready",
                "api_contract_ready": True,
                "expected_route_count": 21,
                "missing_route_count": 0,
            }
        ),
        job_orchestration_packet=_packet(
            {
                "status": "product_job_orchestration_contract_ready",
                "product_job_orchestration_contract_ready": True,
                "retry_child_attempt_created": True,
                "idempotency_preserved": True,
                "progress_fields_present": True,
                "listed_status_progress_contract_ready": True,
                "queue_lifecycle_progress_ready": True,
                "customer_run_history_lineage_ready": True,
                "status_snapshot_persistence_ready": True,
                "rerun_manifest_ready": True,
                "retention_policy_ready": True,
                "long_running_status_persistence_ready": True,
                "worker_backend_contract_ready": True,
                "worker_lease_heartbeat_ready": True,
                "retryable_failure_resume_ready": True,
                "running_cancel_ack_ready": True,
            }
        ),
        capability_packet=_packet({"allowed_scope_families": ["gpcr", "ion_channel", "kinase"]}),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_ai_architecture_gap_closure"
    assert summary["closed_gap_ids"] == ["durable_job_orchestration"]
    assert summary["open_gap_count"] == 6
    assert summary["current_primary_open_gap"] == "production_ai_inference_checkpoint"
    assert summary["gap_blocker_matrix_ready"] is True
    assert summary["gap_blocker_matrix_count"] == 2
    assert summary["current_primary_blocker_id"] == "production_checkpoint_preflight"


def test_product_ai_architecture_gap_closure_complete_when_all_evidence_is_ready() -> None:
    ready_bool = {
        "closed_loop_decision_graph_ready": True,
        "structure_quality_node_ready": True,
        "binding_site_node_ready": True,
        "pose_generation_node_ready": True,
        "scoring_node_ready": True,
        "uncertainty_abstention_node_ready": True,
        "report_node_ready": True,
        "customer_report_ux_node_ready": True,
        "viewer_interaction_surface_ready": True,
        "customer_report_card_ready": True,
        "interaction_rationale_ready": True,
        "counterfactual_rescue_suggestion_ready": True,
        "evidence_traceability_ready": True,
        "fail_closed_transition_ready": True,
        "ready_edge_count": 6,
        "required_edge_count": 6,
    }
    report = {
        "ai_report_ux_ready": True,
        "binding_site_explanation_ready": True,
        "pose_comparison_ready": True,
        "interaction_rationale_ready": True,
        "ligand_selection_rationale_ready": True,
        "viewer_interaction_surface_ready": True,
        "uncertainty_narrative_ready": True,
        "counterfactual_rescue_suggestion_ready": True,
        "structured_customer_report_ready": True,
        "customer_report_delivery_contract_ready": True,
        "customer_report_evidence_binding_ready": True,
        "customer_report_viewer_binding_ready": True,
        "viewer_customer_report_binding_ready": True,
        "customer_report_required_block_count": 7,
        "customer_report_ready_block_count": 7,
        "customer_report_blocked_block_count": 0,
        "customer_report_card_ready": True,
        "evidence_traceability_ready": True,
        "ranking_score_col": "binding_score_composite_v5",
        "primary_abstention_reason": "production_residual_checkpoint_not_promoted",
        "what_would_change_decision": "Return delta_force labels and promote the checkpoint.",
    }
    security = {
        "security_deployment_ready": True,
        "auth_ready": True,
        "tenant_isolation_ready": True,
        "rate_limit_ready": True,
        "payload_limit_ready": True,
        "path_allowlist_ready": True,
        "audit_log_ready": True,
        "hosted_external_exposure_guard_ready": True,
        "hosted_external_exposure_allowed": False,
        "hosted_deployment_contract_ready": True,
        "hosted_deployment_currently_satisfied": False,
        "hosted_deployment_next_stage_id": "operator_exposure_approval",
        "hosted_exposure_approval_token_required": "APPROVE_HOSTED_PRODUCT_API_EXPOSURE",
        "tls_termination_operator_verified": False,
        "hosted_secret_injection_ready": False,
        "sbom_ready": True,
        "container_image_ready": True,
        "metrics_endpoint_ready": True,
        "rollback_ready": True,
    }

    payload = mod.build_product_ai_architecture_gap_closure(
        registry_packet=_packet(
            {
                "product_model_layer_ready": True,
                "default_residual_mode": "production_guarded",
                "production_promotion_allowed": True,
                "customer_facing_auto_correction_allowed": True,
                "customer_facing_score_mutation_allowed": True,
                "customer_facing_ranking_mutation_allowed": True,
                "trained_model_checkpoint_count": 2,
            }
        ),
        e2e_packet=_packet(
            {
                "status": "product_end_to_end_rocm_benchmark_ready",
                "benchmark_ready": True,
                "production_trajectory_profile_enabled": True,
                "jobs_per_hour": 10,
                "unique_ligands_per_hour": 2,
                "failure_rate": 0.0,
            }
        ),
        service_boundary_packet=_packet(
            {
                "status": "product_service_boundary_contract_ready",
                "service_boundary_ready": True,
                "api_route_count": 21,
                "missing_api_route_count": 0,
            }
        ),
        api_contract_packet=_packet(
            {
                "status": "product_api_contract_ready",
                "api_contract_ready": True,
                "expected_route_count": 21,
                "missing_route_count": 0,
            }
        ),
        job_orchestration_packet=_packet(
            {
                "status": "product_job_orchestration_contract_ready",
                "product_job_orchestration_contract_ready": True,
                "retry_child_attempt_created": True,
                "idempotency_preserved": True,
                "progress_fields_present": True,
                "listed_status_progress_contract_ready": True,
                "queue_lifecycle_progress_ready": True,
                "customer_run_history_lineage_ready": True,
                "status_snapshot_persistence_ready": True,
                "rerun_manifest_ready": True,
                "retention_policy_ready": True,
                "long_running_status_persistence_ready": True,
                "worker_backend_contract_ready": True,
                "worker_lease_heartbeat_ready": True,
                "retryable_failure_resume_ready": True,
                "running_cancel_ack_ready": True,
            }
        ),
        capability_packet=_packet({"general_protein_ligand_platform_ready": True}),
        decision_graph_packet=_packet(ready_bool),
        report_ux_packet=_packet(report),
        security_deployment_packet=_packet(security),
        scope_breadth_packet=_packet(
            {
                "status": "product_scope_breadth_contract_ready",
                "scope_breadth_ready": True,
                "scope_claim_posture_ready": True,
                "general_platform_claim_allowed": True,
                "blocked_claim_scopes": [],
                "ready_domains": ["transporter", "ca2", "pxr", "idp_broad", "all_atom", "general_protein_ligand"],
                "missing_domains": [],
            }
        ),
        training_data_packet=_packet({"production_training_data_ready": True}),
    )

    assert payload["summary"]["status"] == "product_ai_architecture_gap_closure_complete"
    assert payload["summary"]["open_gap_count"] == 0
    assert payload["summary"]["all_gaps_closed"] is True
    assert payload["summary"]["gap_blocker_matrix_ready"] is True
    assert payload["summary"]["gap_blocker_matrix_count"] == 0
    security_row = next(row for row in payload["rows"] if row["gap_id"] == "security_deployment_operations")
    assert "hosted_deployment_contract_ready=True" in security_row["observed"]
    assert "hosted_deployment_currently_satisfied=False" in security_row["observed"]


def test_product_ai_architecture_gap_closure_requires_customer_facing_correction_permission() -> None:
    payload = mod.build_product_ai_architecture_gap_closure(
        registry_packet=_packet(
            {
                "product_model_layer_ready": True,
                "default_residual_mode": "production_guarded",
                "production_promotion_allowed": True,
                "customer_facing_auto_correction_allowed": False,
                "customer_facing_score_mutation_allowed": False,
                "customer_facing_ranking_mutation_allowed": False,
                "trained_model_checkpoint_count": 2,
            }
        ),
        e2e_packet=_packet({}),
        service_boundary_packet=_packet({}),
        api_contract_packet=_packet({}),
        capability_packet=_packet({}),
        training_data_packet=_packet({"production_training_data_ready": True}),
    )

    row = next(row for row in payload["rows"] if row["gap_id"] == "production_ai_inference_checkpoint")
    assert row["status"] == "open"
    assert "customer_facing_auto_correction_allowed=False" in row["observed"]
    assert "customer_facing_score_mutation_allowed=False" in row["observed"]
    assert "customer_facing_ranking_mutation_allowed=False" in row["observed"]


def test_product_ai_architecture_gap_closure_requires_decision_graph_edges() -> None:
    node_only_graph = {
        "closed_loop_decision_graph_ready": True,
        "structure_quality_node_ready": True,
        "binding_site_node_ready": True,
        "pose_generation_node_ready": True,
        "scoring_node_ready": True,
        "uncertainty_abstention_node_ready": True,
        "report_node_ready": True,
    }

    payload = mod.build_product_ai_architecture_gap_closure(
        registry_packet=_packet({"product_model_layer_ready": True}),
        e2e_packet=_packet({}),
        service_boundary_packet=_packet({}),
        api_contract_packet=_packet({}),
        capability_packet=_packet({}),
        decision_graph_packet=_packet(node_only_graph),
    )

    row = next(row for row in payload["rows"] if row["gap_id"] == "closed_loop_structure_docking_ai_graph")
    assert row["status"] == "open"
    assert "ready_edges=None/None" in row["observed"]
    assert "fail_closed_transition=None" in row["observed"]


def test_product_ai_architecture_gap_closure_requires_job_orchestration_contract() -> None:
    payload = mod.build_product_ai_architecture_gap_closure(
        registry_packet=_packet({"product_model_layer_ready": True}),
        e2e_packet=_packet({}),
        service_boundary_packet=_packet(
            {
                "status": "product_service_boundary_contract_ready",
                "service_boundary_ready": True,
                "api_route_count": 21,
                "missing_api_route_count": 0,
            }
        ),
        api_contract_packet=_packet(
            {
                "status": "product_api_contract_ready",
                "api_contract_ready": True,
                "expected_route_count": 21,
                "missing_route_count": 0,
            }
        ),
        capability_packet=_packet({}),
    )

    row = next(row for row in payload["rows"] if row["gap_id"] == "durable_job_orchestration")
    assert row["status"] == "open"
    assert "job_contract_status" in row["observed"]


def test_product_ai_architecture_gap_closure_accepts_trajectory_sla_contract() -> None:
    payload = mod.build_product_ai_architecture_gap_closure(
        registry_packet=_packet({"product_model_layer_ready": True}),
        e2e_packet=_packet(
            {
                "status": "product_end_to_end_rocm_benchmark_ready",
                "benchmark_ready": True,
                "production_trajectory_profile_enabled": False,
                "jobs_per_hour": 10,
                "unique_ligands_per_hour": 2,
                "failure_rate": 0.0,
            }
        ),
        service_boundary_packet=_packet({}),
        api_contract_packet=_packet({}),
        capability_packet=_packet({}),
        trajectory_sla_packet=_packet(
            {
                "status": "product_trajectory_sla_contract_ready",
                "production_trajectory_sla_ready": True,
                "ready_run_count": 3,
                "qualified_ready_run_count": 3,
                "minimum_ready_run_count": 3,
                "minimum_ready_rows_per_family": 10000,
                "min_throughput_rows_per_sec": 100,
                "max_failure_rate": 0.0,
                "ready_families": ["gpcr", "ion_channel", "kinase"],
                "qualified_ready_families": ["gpcr", "ion_channel", "kinase"],
                "missing_qualified_families": [],
                "sla_claim_tier": "restricted_family_sla",
                "restricted_family_sla_allowed": True,
                "broad_platform_sla_allowed": False,
                "current_rocm_baseline_claim_scope": "single_target_gpcr_baseline",
                "current_rocm_baseline_production_trajectory_profile_enabled": False,
                "current_rocm_baseline_supports_broad_platform_sla": False,
                "restricted_sla_backed_by_historical_profile_artifacts": True,
                "rocm_baseline_profile_gap_acknowledged": True,
            }
        ),
    )

    row = next(row for row in payload["rows"] if row["gap_id"] == "production_trajectory_sla")
    assert row["status"] == "closed"
    assert "current_rocm_baseline_claim_scope=single_target_gpcr_baseline" in row["observed"]
    assert "rocm_baseline_profile_gap_acknowledged=True" in row["observed"]


def test_product_ai_architecture_gap_closure_closes_restricted_scope_delivery_posture() -> None:
    payload = mod.build_product_ai_architecture_gap_closure(
        registry_packet=_packet({"product_model_layer_ready": True}),
        e2e_packet=_packet({}),
        service_boundary_packet=_packet({}),
        api_contract_packet=_packet({}),
        capability_packet=_packet({"allowed_scope_families": ["gpcr", "ion_channel", "kinase"]}),
        scope_breadth_packet=_packet(
            {
                "status": "blocked_product_scope_breadth_contract",
                "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
                "scope_breadth_ready": False,
                "scope_claim_posture_ready": True,
                "general_platform_claim_allowed": False,
                "blocked_claim_scopes": [
                    "transporter_domain_promotion",
                    "general_protein_ligand_platform",
                ],
                "missing_domains": ["transporter", "idp_broad", "general_protein_ligand"],
            }
        ),
    )

    row = next(row for row in payload["rows"] if row["gap_id"] == "scope_breadth_expansion")
    assert row["status"] == "closed"


def test_product_ai_architecture_gap_closure_accepts_scope_breadth_contract() -> None:
    payload = mod.build_product_ai_architecture_gap_closure(
        registry_packet=_packet({"product_model_layer_ready": True}),
        e2e_packet=_packet({}),
        service_boundary_packet=_packet({}),
        api_contract_packet=_packet({}),
        capability_packet=_packet({"allowed_scope_families": ["gpcr", "ion_channel", "kinase"]}),
        scope_breadth_packet=_packet(
            {
                "status": "product_scope_breadth_contract_ready",
                "scope_breadth_ready": True,
                "scope_claim_posture_ready": True,
                "general_platform_claim_allowed": True,
                "blocked_claim_scopes": [],
                "ready_domains": ["transporter", "ca2", "pxr", "idp_broad", "all_atom", "general_protein_ligand"],
                "missing_domains": [],
            }
        ),
    )

    row = next(row for row in payload["rows"] if row["gap_id"] == "scope_breadth_expansion")
    assert row["status"] == "closed"


def test_product_ai_architecture_gap_closure_does_not_accept_capability_only_scope_claim() -> None:
    payload = mod.build_product_ai_architecture_gap_closure(
        registry_packet=_packet({"product_model_layer_ready": True}),
        e2e_packet=_packet({}),
        service_boundary_packet=_packet({}),
        api_contract_packet=_packet({}),
        capability_packet=_packet(
            {
                "allowed_scope_families": ["gpcr", "ion_channel", "kinase", "transporter", "ca2", "pxr"],
                "general_protein_ligand_platform_ready": True,
            }
        ),
        scope_breadth_packet=_packet(
            {
                "status": "blocked_product_scope_breadth_contract",
                "scope_breadth_ready": False,
                "scope_claim_posture_ready": True,
                "general_platform_claim_allowed": False,
                "blocked_claim_scopes": ["general_protein_ligand_platform"],
                "ready_domains": ["ca2"],
                "missing_domains": ["transporter", "pxr", "general_protein_ligand"],
            }
        ),
    )

    row = next(row for row in payload["rows"] if row["gap_id"] == "scope_breadth_expansion")
    assert row["status"] == "open"
    assert "general_platform=True" in row["observed"]
    assert "general_platform_claim_allowed=False" in row["observed"]
    assert "blocked_claim_scopes=general_protein_ligand_platform" in row["observed"]


def test_product_ai_architecture_gap_closure_surfaces_scope_intake_readiness() -> None:
    payload = mod.build_product_ai_architecture_gap_closure(
        registry_packet=_packet({"product_model_layer_ready": True}),
        e2e_packet=_packet({}),
        service_boundary_packet=_packet({}),
        api_contract_packet=_packet({}),
        capability_packet=_packet({"allowed_scope_families": ["gpcr", "ion_channel", "kinase"]}),
        scope_breadth_packet=_packet(
            {
                "status": "blocked_product_scope_breadth_contract",
                "scope_breadth_ready": False,
                "scope_claim_posture_ready": True,
                "general_platform_claim_allowed": False,
                "blocked_claim_scopes": [
                    "transporter_domain_promotion",
                    "pxr_domain_promotion",
                    "general_protein_ligand_platform",
                ],
                "ready_domains": ["ca2", "idp_broad", "all_atom"],
                "missing_domains": ["transporter", "pxr", "general_protein_ligand"],
                "scope_breadth_acquisition_plan_ready": True,
                "evidence_intake_readiness_ready": True,
                "local_crosscheck_intake_ready_count": 10,
                "local_crosscheck_unreadable_item_count": 0,
                "transporter_triage_packet_ready": True,
                "transporter_operator_review_evidence_matrix_ready": True,
                "transporter_claim_safe_local_evidence_ready_count": 0,
                "transporter_claim_safe_local_evidence_blocked_count": 11,
                "transporter_direct_binding_claim_blocked_count": 4,
                "transporter_negative_value_claim_blocked_count": 6,
                "transporter_top_claim_safe_blocker": "functional_assay_quantitative_but_not_direct_binding_claim_safe",
                "transporter_candidate_assignment_required_count": 7,
                "transporter_functional_direct_gap_count": 3,
                "transporter_candidate_workbook_ready": True,
                "transporter_candidate_ready_for_manual_review_count": 11,
                "transporter_candidate_ready_for_apply_count": 0,
                "transporter_manual_review_intake_ready": True,
                "transporter_manual_review_template_row_count": 11,
                "transporter_manual_review_direct_binding_evidence_required_count": 4,
                "transporter_manual_review_negative_quantitative_value_required_count": 6,
                "pxr_exact_review_intake_ready": True,
                "pxr_exact_review_template_row_count": 6,
                "pxr_exact_review_conflict_resolution_required_count": 3,
                "pxr_exact_review_kcal_placeholder_count": 6,
                "scientific_evidence_request_count": 17,
                "external_primary_exact_evidence_required_count": 6,
                "intake_external_exact_evidence_required_count": 6,
                "review_only_keep_blocked_count": 1,
            }
        ),
    )

    row = next(row for row in payload["rows"] if row["gap_id"] == "scope_breadth_expansion")
    assert row["status"] == "closed"
    assert "scope_claim_posture_ready=True" in row["observed"]
    assert "general_platform_claim_allowed=False" in row["observed"]
    assert "blocked_claim_scopes=transporter_domain_promotion,pxr_domain_promotion,general_protein_ligand_platform" in row["observed"]
    assert "intake_readiness_ready=True" in row["observed"]
    assert "local_crosscheck_intake_ready=10" in row["observed"]
    assert "local_crosscheck_unreadable=0" in row["observed"]
    assert "transporter_triage_ready=True" in row["observed"]
    assert "transporter_operator_review_evidence_matrix_ready=True" in row["observed"]
    assert "transporter_claim_safe_local_evidence_ready=0" in row["observed"]
    assert "transporter_claim_safe_local_evidence_blocked=11" in row["observed"]
    assert "transporter_direct_binding_claim_blocked=4" in row["observed"]
    assert "transporter_negative_value_claim_blocked=6" in row["observed"]
    assert "transporter_top_claim_safe_blocker=functional_assay_quantitative_but_not_direct_binding_claim_safe" in row[
        "observed"
    ]
    assert "transporter_candidate_assignment_required=7" in row["observed"]
    assert "transporter_functional_direct_gap=3" in row["observed"]
    assert "transporter_candidate_workbook_ready=True" in row["observed"]
    assert "transporter_candidate_manual_review=11" in row["observed"]
    assert "transporter_candidate_apply_ready=0" in row["observed"]
    assert "transporter_manual_review_intake_ready=True" in row["observed"]
    assert "transporter_manual_review_template_rows=11" in row["observed"]
    assert "transporter_manual_review_direct_binding_required=4" in row["observed"]
    assert "transporter_manual_review_negative_value_required=6" in row["observed"]
    assert "pxr_exact_review_intake_ready=True" in row["observed"]
    assert "pxr_exact_review_template_rows=6" in row["observed"]
    assert "pxr_exact_review_conflict_required=3" in row["observed"]
    assert "pxr_exact_review_kcal_placeholders=6" in row["observed"]
    assert "intake_external_exact_required=6" in row["observed"]


def test_product_ai_architecture_gap_closure_builds_open_gap_blocker_matrix() -> None:
    payload = mod.build_product_ai_architecture_gap_closure(
        registry_packet=_packet(
            {
                "product_model_layer_ready": True,
                "default_residual_mode": "shadow",
                "production_promotion_allowed": False,
                "trained_model_checkpoint_count": 0,
            }
        ),
        e2e_packet=_packet({}),
        service_boundary_packet=_packet({}),
        api_contract_packet=_packet({}),
        capability_packet=_packet({"allowed_scope_families": ["gpcr", "ion_channel", "kinase"]}),
        production_ai_checkpoint_readiness_packet=_packet(
            {
                "production_ai_checkpoint_ready": False,
                "production_inference_actionable_blocker_check_id": (
                    "production_gpu_execution_environment_ready"
                ),
                "production_inference_actionable_blocker_stage_id": (
                    "production_gpu_execution_environment_acceptance"
                ),
                "production_inference_actionable_blocker_artifact": (
                    "runs/rocm_environment_manifest_current.json"
                ),
                "production_inference_actionable_blocker_observed": (
                    "torch_rocm_ready=False;visible_device_count=0"
                ),
                "production_inference_actionable_blocker_required": (
                    "ROCm/HIP runtime is visible to PyTorch with at least one AMD GPU"
                ),
                "production_gpu_rocm_next_required_step": (
                    "Expose a visible ROCm/HIP AMD GPU device to PyTorch before production regeneration."
                ),
                "production_inference_actionable_blocker_validation_command": (
                    "python3 tools/build_rocm_environment_manifest.py"
                ),
                "production_inference_next_after_actionable_blocker_stage_id": (
                    "gpu_return_acceptance"
                ),
                "production_inference_next_after_actionable_blocker_artifact": (
                    "runs/residual_force_gpu_worker_return_receipt_current.json"
                ),
                "production_inference_next_after_actionable_blocker_validation_command": (
                    "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                ),
                "production_inference_next_after_actionable_blocker_next_action": (
                    "Return full regeneration summary/manifest, NPZ paths, operator verification, identity coverage, and post-run force derivation validation."
                ),
                "production_inference_next_after_actionable_blocker_required_checks": [
                    "gpu_worker_return_receipt_ready"
                ],
                "production_inference_next_after_actionable_blocker_unlock_fields": [
                    "summary_manifest_bound",
                    "identity_coverage_ready",
                    "post_run_derivation_validation_ready",
                    "production_gpu_backend_provenance_ready",
                ],
            }
        ),
        scope_breadth_packet=_packet(
            {
                "status": "blocked_product_scope_breadth_contract",
                "scope_breadth_ready": False,
                "scope_claim_posture_ready": True,
                "general_platform_claim_allowed": False,
                "blocked_claim_scopes": [
                    "transporter_domain_promotion",
                    "pxr_domain_promotion",
                    "general_protein_ligand_platform",
                ],
                "scope_acceptance_next_stage_id": "transporter_claim_acceptance",
                "scope_acceptance_next_stage_artifact": (
                    "runs/product_scope_breadth_contract_current.json"
                ),
                "scope_acceptance_next_stage_validation_command": (
                    "python3 tools/build_product_scope_breadth_contract.py"
                ),
                "transporter_p0_evidence_acquisition_unresolved_slot_count": 11,
                "transporter_manual_review_direct_binding_evidence_required_count": 4,
                "transporter_manual_review_negative_quantitative_value_required_count": 6,
                "transporter_p0_evidence_acquisition_next_slot_id": "AQP1.core_binder_01",
                "transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": (
                    "runs/transporter_manual_review_intake_template_current.csv"
                ),
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_artifact": (
                    "runs/aqp1_binding_source_modality_triage_current.json"
                ),
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_decision": (
                    "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
                ),
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_experimental_binding_row_count": 0,
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count": 0,
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_computational_binding_energy_row_count": 1,
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol": (
                    "-34.48"
                ),
                "transporter_p0_evidence_acquisition_next_slot_completion_packet": {
                    "slot_id": "AQP1.core_binder_01",
                    "next_action": "Acquire exact AQP1 binder kcal evidence.",
                    "required_operator_intake_columns": [
                        "target_id",
                        "candidate_ligand_id",
                        "reference_binding_kcal_mol",
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
                    "completion_rule": (
                        "Provide exact target-pair quantitative evidence before promotion."
                    ),
                },
            }
        ),
    )

    summary = payload["summary"]
    assert summary["open_gap_count"] == 6
    assert summary["gap_blocker_matrix_ready"] is True
    assert summary["gap_blocker_matrix_count"] == 1
    assert summary["current_primary_blocker_id"] == "production_gpu_execution_environment_ready"
    assert summary["current_primary_blocker_artifact"] == "runs/rocm_environment_manifest_current.json"
    assert summary["current_next_action"] == (
        "Expose a visible ROCm/HIP AMD GPU device to PyTorch before production regeneration."
    )
    assert summary["current_primary_blocker_next_action"] == (
        "Expose a visible ROCm/HIP AMD GPU device to PyTorch before production regeneration."
    )
    assert summary["current_primary_blocker_operator_input_fields"] == [
        "manifest_ready",
        "rocm_stack_detected",
        "torch_rocm_ready",
        "amd_gpu_detected",
        "visible_device_count",
    ]
    assert summary["current_primary_blocker_unlock_claim"] == "production_ai_inference_subject"
    assert summary["current_primary_blocker_next_after_stage_id"] == "gpu_return_acceptance"
    assert summary["current_primary_blocker_next_after_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert summary["current_primary_blocker_next_after_validation_command"] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert "Return full regeneration summary/manifest" in summary[
        "current_primary_blocker_next_after_next_action"
    ]
    assert summary["current_primary_blocker_next_after_required_checks"] == [
        "gpu_worker_return_receipt_ready"
    ]
    assert "identity_coverage_ready" in summary[
        "current_primary_blocker_next_after_unlock_fields"
    ]
    assert summary["parallelizable_gap_blocker_count"] == 0
    assert summary["gap_blocker_matrix"][0]["parallelizable_workstream"] is False
    assert summary["gap_blocker_matrix"][0]["operator_input_fields"] == [
        "manifest_ready",
        "rocm_stack_detected",
        "torch_rocm_ready",
        "amd_gpu_detected",
        "visible_device_count",
    ]
    production_gap = next(row for row in payload["rows"] if row["gap_id"] == "production_ai_inference_checkpoint")
    assert production_gap["next_action"] == summary["current_next_action"]
    assert production_gap["immediate_actionable_blocker_id"] == (
        "production_gpu_execution_environment_ready"
    )
    assert production_gap["immediate_actionable_blocker_stage_id"] == (
        "production_gpu_execution_environment_acceptance"
    )
    assert production_gap["immediate_actionable_blocker_artifact"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert production_gap["immediate_actionable_blocker_validation_command"] == (
        "python3 tools/build_rocm_environment_manifest.py"
    )
    assert "visible_device_count" in production_gap["immediate_actionable_blocker_operator_input_fields"]
    assert production_gap["immediate_actionable_blocker_unlock_claim"] == (
        "production_ai_inference_subject"
    )


def test_product_ai_architecture_gap_closure_cli_writes_outputs(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    e2e = tmp_path / "e2e.json"
    service = tmp_path / "service.json"
    api = tmp_path / "api.json"
    capability = tmp_path / "capability.json"
    for path, payload in {
        registry: _packet({"product_model_layer_ready": True}),
        e2e: _packet({"status": "product_end_to_end_rocm_benchmark_ready"}),
        service: _packet({"status": "product_service_boundary_contract_ready"}),
        api: _packet({"status": "product_api_contract_ready"}),
        capability: _packet({"allowed_scope_families": []}),
    }.items():
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    mod.main(
        [
            "--registry-json",
            str(registry),
            "--e2e-json",
            str(e2e),
            "--service-boundary-json",
            str(service),
            "--api-contract-json",
            str(api),
            "--capability-json",
            str(capability),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["gap_count"] == 7
    assert payload["summary"]["gap_blocker_matrix_ready"] is True
    assert out_csv.exists()
    md_text = out_md.read_text(encoding="utf-8")
    assert "# Product AI Architecture Gap Closure" in md_text
    assert "## Gap Blockers" in md_text
