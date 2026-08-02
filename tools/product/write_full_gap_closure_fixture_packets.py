from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _row_evidence_count(payload: Any) -> int:
    """Count row-level evidence entries in an artifact payload."""

    if not isinstance(payload, dict):
        return 0
    total = 0
    for key in ("rows", "checks"):
        value = payload.get(key)
        if isinstance(value, list):
            total += len(value)
    return total


def _write_without_degrading(path: Path, payload: dict[str, Any]) -> None:
    """Write a fixture packet unless it would drop existing row-level evidence.

    These are summary-only CI scaffolds. Written over a real generated artifact
    they delete its ``rows``/``checks`` evidence, and a consumer that requires
    row-level proof then reports blocked while the summary still says ready.
    """

    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if _row_evidence_count(existing) > _row_evidence_count(payload):
            return
    _write(path, payload)


def write_full_gap_closure_fixture_packets(runs_dir: Path) -> None:
    _write(
        runs_dir / "product_end_to_end_rocm_benchmark_current.json",
        {
            "summary": {
                "status": "product_end_to_end_rocm_benchmark_ready",
                "benchmark_ready": True,
                "docking_results_emitted": True,
                "processed_jobs": 10000,
                "scored_rows": 640,
                "jobs_per_hour": 100000.0,
                "unique_ligands_per_hour": 2000.0,
                "production_trajectory_profile_enabled": True,
                "failure_rate": 0.0,
                "bundle_zip_present": True,
                "bundle_validation_ok": True,
            }
        },
    )
    _write(
        runs_dir / "amd_workstation_server_packaging_profile_current.json",
        {
            "summary": {
                "status": "amd_workstation_server_packaging_profile_ready",
                "workstation_profile_ready": True,
                "visible_device_count": 1,
                "current_topology": "single_gpu",
                "commercial_compute_default": "rocm_hip",
                "supported_amd_gpu_family": ["AMD Radeon RX 6900 XT"],
            }
        },
    )
    _write(
        runs_dir / "residual_shadow_ab_current.json",
        {
            "summary": {
                "status": "residual_shadow_ab_scaffold_ready",
                "residual_mode": "assist",
                "assist_promotion_allowed": True,
                "production_promotion_allowed": False,
            }
        },
    )
    _write(
        runs_dir / "residual_assist_promotion_gate_current.json",
        {
            "summary": {
                "status": "residual_assist_promotion_gate_ready",
                "assist_promotion_allowed": True,
            }
        },
    )
    _write(
        runs_dir / "gpcr_hard_decoy_residual_proof_current.json",
        {
            "summary": {
                "status": "gpcr_hard_decoy_residual_proof_ready",
                "task_count": 7,
                "pr_auc_regression_warning_count": 0,
            }
        },
    )
    _write(
        runs_dir / "public_benchmark_residual_regression_gate_current.json",
        {
            "summary": {
                "status": "public_benchmark_residual_regression_gate_ready",
                "assist_promotion_allowed": True,
            }
        },
    )
    _write(
        runs_dir / "public_benchmark_residual_assist_comparison_gate_current.json",
        {
            "summary": {
                "status": "public_benchmark_residual_assist_comparison_gate_ready",
                "assist_comparison_gate_ready": True,
            }
        },
    )
    _write(
        runs_dir / "customer_alpha_bundle_manifest_current.json",
        {
            "summary": {
                "status": "customer_alpha_bundle_manifest_ready",
                "customer_alpha_bundle_ready": True,
            }
        },
    )
    _write(
        runs_dir / "residual_model_registry_current.json",
        {
            "summary": {
                "status": "residual_model_registry_ready",
                "registry_ready": True,
                "product_model_layer_ready": True,
                "default_residual_mode": "production_guarded",
                "production_promotion_allowed": True,
                "production_mode_allowed": True,
                "customer_facing_auto_correction_allowed": True,
                "customer_facing_score_mutation_allowed": True,
                "customer_facing_ranking_mutation_allowed": True,
                "trained_model_checkpoint_count": 1,
                "checkpoint_preflight_ready": True,
                "production_checkpoint_blocked": False,
                "selected_sidecar_ready": True,
                "checkpoint_missing_output_fields": [],
                "checkpoint_missing_adapter_output_policy_fields": [],
                "required_output_fields_present": True,
            }
        },
    )
    _write(
        runs_dir / "residual_production_training_data_contract_current.json",
        {
            "summary": {
                "status": "residual_production_training_data_contract_ready",
                "production_training_data_ready": True,
            }
        },
    )
    _write(
        runs_dir / "product_production_ai_checkpoint_readiness_current.json",
        {
            "summary": {
                "status": "product_production_ai_checkpoint_readiness_ready",
                "production_ai_checkpoint_ready": True,
                "production_ai_inference_subject_active": True,
                "production_promotion_allowed": True,
                "trained_model_checkpoint_count": 1,
                "ready_checkpoint_count": 1,
                "checkpoint_preflight_ready": True,
                "selected_sidecar_ready": True,
            }
        },
    )
    _write(
        runs_dir / "product_commercial_independence_gate_current.json",
        {
            "summary": {
                "status": "product_commercial_independence_gate_ready",
                "license_present": True,
                "commercial_independent_product_claim_allowed": True,
                "local_self_hosted_api_cli_ready": True,
                "product_service_boundary_ready": True,
                "product_api_contract_ready": True,
                "delete_executed": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "residual_production_checkpoint_work_order_current.json",
        {
            "summary": {
                "status": "residual_production_checkpoint_work_order_ready",
                "checkpoint_preflight_ready": True,
                "candidate_checkpoint_count": 1,
                "ready_checkpoint_count": 1,
                "compatible_candidate_count": 1,
                "sidecar_builder_ready": True,
                "sidecar_builder_status": "residual_production_checkpoint_sidecar_ready",
                "sidecar_builder_training_data_contract_ready": True,
                "sidecar_builder_force_gpu_return_receipt_ready": True,
                "sidecar_builder_force_gpu_return_receipt_operator_verified": True,
                "sidecar_builder_force_gpu_return_receipt_operator_verified_true_count": 1,
                "sidecar_builder_force_gpu_return_receipt_expected_queue_rows": 1,
                "sidecar_builder_blockers": [],
                "sidecar_builder_missing_production_output_fields": [],
                "sidecar_builder_training_contract_missing_label_fields": [],
                "checkpoint_closure_blockers": [],
                "registry_checkpoint_missing_output_fields": [],
                "registry_checkpoint_missing_adapter_output_policy_fields": [],
            }
        },
    )
    _write_without_degrading(
        runs_dir / "cameo_architecture_validation_contract_current.json",
        {
            "summary": {
                "status": "cameo_architecture_validation_contract_ready",
                "local_validation_protocol_ready": True,
                "receiver_api_readiness_ready": True,
                "validation_operations_surface_ready": True,
            }
        },
    )
    _write(
        runs_dir / "cameo_validation_readiness_gate_current.json",
        {
            "summary": {
                "status": "cameo_validation_evidence_ready",
                "blocker_count": 0,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "product_ai_decision_graph_contract_current.json",
        {
            "summary": {
                "status": "product_ai_decision_graph_contract_ready",
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
        },
    )
    _write(
        runs_dir / "product_ai_report_ux_contract_current.json",
        {
            "summary": {
                "status": "product_ai_report_ux_contract_ready",
                "ai_report_ux_ready": True,
                "binding_site_explanation_ready": True,
                "pose_comparison_ready": True,
                "interaction_rationale_ready": True,
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
                "ranking_score_col": "binding_score_composite_v7",
                "primary_abstention_reason": "production_residual_checkpoint_not_promoted",
                "what_would_change_decision": "Return delta_force labels and promote the checkpoint.",
            }
        },
    )
    _write(
        runs_dir / "product_trajectory_sla_contract_current.json",
        {
            "summary": {
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
                "rocm_baseline_profile_gap_acknowledged": True,
                "restricted_sla_backed_by_historical_profile_artifacts": True,
                "current_rocm_baseline_supports_broad_platform_sla": False,
            }
        },
    )
    _write(
        runs_dir / "product_scope_breadth_contract_current.json",
        {
            "summary": {
                "status": "product_scope_breadth_contract_ready",
                "scope_breadth_ready": True,
                "scope_claim_posture_ready": True,
                "general_platform_claim_allowed": True,
                "blocked_claim_scopes": [],
                "ready_domains": ["transporter", "ca2", "pxr", "idp_broad", "all_atom", "general_protein_ligand"],
                "missing_domains": [],
            }
        },
    )
    _write(
        runs_dir / "product_scope_breadth_closure_checklist_current.json",
        {
            "summary": {
                "status": "product_scope_breadth_closure_checklist_ready",
                "authoritative_apply_allowed": True,
                "ready_for_apply_count": 0,
            },
            "rows": [],
        },
    )
    _write(
        runs_dir / "residual_force_gpu_worker_return_receipt_current.json",
        {
            "summary": {
                "status": "residual_force_gpu_worker_return_receipt_ready",
                "gpu_worker_return_receipt_ready": True,
                "blockers": [],
            }
        },
    )
    _write(
        runs_dir / "product_api_contract_current.json",
        {
            "summary": {
                "status": "product_api_contract_ready",
                "api_contract_ready": True,
                "expected_route_count": 45,
                "missing_route_count": 0,
                "blocker_count": 0,
                "pass_count": 5,
                "check_count": 5,
            }
        },
    )
    _write(
        runs_dir / "product_service_boundary_contract_current.json",
        {
            "summary": {
                "status": "product_service_boundary_contract_ready",
                "service_boundary_ready": True,
                "api_route_count": 46,
                "missing_api_route_count": 0,
            }
        },
    )
    _write(
        runs_dir / "product_job_orchestration_contract_current.json",
        {
            "summary": {
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
        },
    )
    _write(
        runs_dir / "product_architecture_contract_current.json",
        {
            "summary": {
                "status": "product_architecture_contract_ready",
                "local_architecture_surface_ready": True,
                "architecture_release_ready": True,
                "blocked_lane_count": 0,
                "approval_required_lane_count": 0,
                "structure_analysis_product_surface_ready": True,
                "ligand_docking_execution_contract_ready": True,
                "commercial_independence_ready": True,
                "cameo_architecture_validation_ready": True,
                "cleanup_control_surface_ready": True,
                "casp17_transition_surface_ready": True,
                "product_api_contract_ready": True,
                "product_service_boundary_ready": True,
            }
        },
    )
    _write(
        runs_dir / "transition_cleanup_work_order_current.json",
        {
            "summary": {
                "status": "transition_cleanup_work_order_ready",
                "blocker_count": 0,
            }
        },
    )
    _write(
        runs_dir / "transition_cleanup_execution_preflight_current.json",
        {
            "summary": {
                "status": "transition_cleanup_execution_preflight_ready",
                "blocker_count": 0,
            }
        },
    )
    _write(
        runs_dir / "ligand_heavy_cleanup_work_order_current.json",
        {
            "summary": {
                "status": "cleanup_work_order_ready",
                "blocker_count": 0,
            }
        },
    )
    _write(
        runs_dir / "ligand_heavy_cleanup_execution_preflight_current.json",
        {
            "summary": {
                "status": "ligand_heavy_cleanup_execution_preflight_ready",
                "blocker_count": 0,
            }
        },
    )
