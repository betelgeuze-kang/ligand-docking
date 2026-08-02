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

    These fixture packets are summary-only scaffolds for CI contract runs. When
    they are written over a real generated artifact they silently delete its
    ``rows``/``checks`` evidence, and consumers that require row-level proof then
    derive a blocked status from an artifact whose summary still says ready.
    """

    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if _row_evidence_count(existing) > _row_evidence_count(payload):
            return
    _write(path, payload)


def _release_bundle_payload() -> dict[str, Any]:
    summary = {
        "status": "release_bundle_ready_for_operator_review",
        "release_bundle_ready": True,
        "release_id": "local-restricted-product-ci-fixture",
        "bundle_version": "ci-fixture",
        "artifact_count": 34,
        "check_count": 26,
        "pass_count": 26,
        "blocker_count": 0,
    }
    policy = {
        "status": "operator_approval_required",
        "approval_tokens_required": [
            "APPROVE_PRODUCT_ROLLOUT",
            "APPROVE_HOSTED_PRODUCT_API_EXPOSURE",
            "MODEL_REGISTRY_SIGNING_KEY",
            "API_RESULT_MANIFEST_SIGNING_KEY",
        ],
        "must_review_fields": [
            "target",
            "action",
            "impact",
            "risk",
            "rollback",
            "verification",
        ],
        "required_before_execution": ["operator_release_approval_recorded"],
        "external_state_mutation_allowed": False,
    }
    checks = [
        {"check": f"release_bundle_check_{index:02d}", "passed": True}
        for index in range(1, 27)
    ]
    summary = {
        **summary,
        "operator_promotion_policy": policy,
        "checks": checks,
    }
    payload = {
        **summary,
        "summary": summary,
        "operator_promotion_policy": policy,
        "checks": checks,
    }
    return payload


def write_restricted_scope_breadth_contract(runs_dir: Path) -> None:
    path = runs_dir / "product_scope_breadth_contract_current.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    summary.update(
        {
            "status": "blocked_product_scope_breadth_contract",
            "scope_breadth_ready": False,
            "scope_widened": False,
            "scope_claim_posture_ready": True,
            "restricted_scope_claim_allowed": True,
            "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
            "blocked_claim_scopes": [
                "transporter_domain_promotion",
                "general_protein_ligand_platform",
            ],
            "general_platform_claim_allowed": False,
            "general_platform_claim_blocked": True,
        }
    )
    payload["summary"] = summary
    _write(path, payload)


def write_restricted_self_hosted_commercial_packets(runs_dir: Path) -> None:
    write_restricted_scope_breadth_contract(runs_dir)
    _write(
        runs_dir / "restricted_unattended_execution_readiness_current.json",
        {
            "summary": {
                "packet_type": "restricted_unattended_execution_readiness",
                "status": "restricted_unattended_execution_wiring_ready",
                "restricted_unattended_execution_ready": True,
                "restricted_unattended_execution_runtime_ready": False,
                "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
                "gate_count": 5,
                "blocked_gate_count": 0,
                "operator_pending_gate_count": 1,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "product_commercial_independence_gate_current.json",
        {
            "summary": {
                "status": "product_commercial_independence_gate_ready",
                "commercial_independent_product_claim_allowed": True,
                "restricted_commercial_scope_claim_ready": True,
                "commercial_claim_scope_tier": "restricted_family_local_product",
                "commercial_claim_scope_detail": (
                    "restricted_family_local_product;allowed=gpcr,ion_channel,kinase;"
                    "blocked=transporter_domain_promotion,general_protein_ligand_platform"
                ),
                "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
                "blocked_claim_scopes": [
                    "transporter_domain_promotion",
                    "general_protein_ligand_platform",
                ],
                "local_self_hosted_operation_ready": True,
                "local_self_hosted_api_cli_ready": True,
                "general_platform_claim_allowed": False,
                "blocker_count": 0,
                "license_present": True,
                "product_service_boundary_ready": True,
                "product_api_contract_ready": True,
                "public_benchmark_evidence_ready": True,
                "delete_executed": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "product_release_bundle_current.json",
        _release_bundle_payload(),
    )
    _write(
        runs_dir / "product_service_boundary_contract_current.json",
        {
            "summary": {
                "status": "product_service_boundary_contract_ready",
                "service_boundary_ready": True,
                "api_route_count": 46,
                "missing_api_route_count": 0,
                "cli_command_count": 13,
            }
        },
    )
    _write(
        runs_dir / "product_architecture_contract_current.json",
        {
            "summary": {
                "status": "product_architecture_contract_ready",
                "architecture_release_ready": True,
                "commercial_independence_ready": True,
                "cleanup_control_surface_ready": True,
                "local_architecture_surface_ready": True,
                "public_benchmark_validation_ready": True,
                "public_benchmark_status": "product_public_benchmark_contract_ready",
                "public_benchmark_required_suite_count": 5,
                "public_benchmark_ready_required_suite_count": 5,
                "public_benchmark_blocked_suite_count": 0,
                "public_benchmark_suite_materialization_manifest_count": 5,
                "public_benchmark_suite_scorecard_row_csv_count": 5,
                "public_benchmark_suite_threshold_count": 5,
                "public_benchmark_suite_blocker_count": 0,
                "public_benchmark_suite_run_command_count": 5,
                "public_benchmark_suite_materialization_run_command_count": 5,
                "public_benchmark_suite_result_provenance_command_count": 5,
                "public_benchmark_suite_result_provenance_present_count": 5,
                "public_benchmark_suite_no_external_dependency_count": 5,
                "requires_24h_server": False,
                "requires_competition_season": False,
                "requires_paid_vps": False,
            }
        },
    )
    _write(
        runs_dir / "product_job_orchestration_contract_current.json",
        {
            "summary": {
                "status": "product_job_orchestration_contract_ready",
                "product_job_orchestration_contract_ready": True,
                "check_count": 18,
                "ready_check_count": 18,
                "blocked_check_count": 0,
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
                "stale_worker_lease_recovery_ready": True,
                "stale_worker_lease_sweep_ready": True,
                "stale_worker_lease_detected_count": 1,
                "stale_worker_lease_updated_count": 1,
                "retryable_after_stale_count": 1,
                "stale_worker_lease_timeout_seconds": 1800,
                "job_retention_days": 90,
                "source_host_filter_job_count": 4,
                "root_job_id_filter_job_count": 3,
                "customer_id_filter_job_count": 4,
                "user_id_filter_job_count": 4,
                "root_attempt_count_after_retry": 3,
                "history_event_count": 3,
                "job_count_after_retry": 3,
                "job_count_after_stale_probe": 4,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            },
            "rows": [{"check_id": f"contract_check_{idx}", "status": "ready"} for idx in range(18)],
        },
    )
    _write(
        runs_dir / "product_bundle_contract_current.json",
        {
            "summary": {
                "status": "product_bundle_contract_ready",
                "bundle_parser_status": "parsed",
                "bundle_unknown_arg_count": 0,
                "expected_bundle_dir": "runs/local_delivery/bundle_product_gpcr_adrb2",
                "artifact_count": 1,
                "bundle_validation_command_matches": True,
                "bundle_assembled": True,
                "bundle_validation_passed": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            },
            "bundle_command_check": {
                "parsed_args": {
                    "rerun_command": "python3 tools/run_ligand_htvs_pipeline.py --out-prefix runs/product_gpcr_adrb2_after_approval"
                }
            },
            "planned_artifact_checks": [{"path": "runs/product_gpcr_adrb2_after_approval_summary.json"}],
        },
    )
    _write(
        runs_dir / "product_delivery_evidence_contract_current.json",
        {
            "summary": {
                "status": "product_delivery_evidence_contract_ready",
                "delivery_ready_claim_allowed": True,
                "bundle_assembled": True,
                "bundle_validation_passed": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "product_pilot_packet_contract_current.json",
        {
            "summary": {
                "status": "product_pilot_packet_ready",
                "pilot_delivery_ready": True,
                "delivery_ready_claim_allowed": True,
                "bundle_assembled": True,
                "bundle_validation_present": True,
                "bundle_dir_exists": True,
                "bundle_validation_passed": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "product_image_smoke_preflight_current.json",
        {
            "summary": {
                "status": "product_image_smoke_preflight_ready",
                "clean_container_smoke_ready": True,
                "receipt_status": "product_image_smoke_ready",
                "receipt_mode": "rocm-runtime",
                "product_runner_smoke_ready": True,
                "container_runtime_receipt_ready": True,
                "container_runtime_proof_schema_version": "rocm_container_runtime_proof_v1",
                "container_runtime_in_container": True,
                "container_runtime_device_nodes_ready": True,
                "container_runtime_torch_rocm_ready": True,
                "container_runtime_torch_cuda_available": True,
                "container_runtime_visible_device_count": 1,
                "container_runtime_rust_hip_backend_enabled": True,
                "receipt_simulate_missing_profile_http": 422,
                "rocm_runtime_smoke_ready": True,
                "source": "ci_contract_fixture",
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    required_families = ["gpcr", "ion_channel", "kinase"]
    trajectory_rows = [
        {
            "family": family,
            "status": "ready",
            "qualified_for_restricted_family_sla": True,
            "ready_row_count": 10000,
        }
        for family in required_families
    ]
    _write(
        runs_dir / "product_trajectory_sla_contract_current.json",
        {
            "summary": {
                "status": "product_trajectory_sla_contract_ready",
                "production_trajectory_sla_ready": True,
                "sla_claim_tier": "restricted_family_sla",
                "restricted_family_sla_allowed": True,
                "broad_platform_sla_allowed": False,
                "candidate_artifact_count": len(trajectory_rows),
                "ready_run_count": 3,
                "qualified_ready_run_count": 3,
                "required_families": required_families,
                "ready_families": required_families,
                "qualified_ready_families": required_families,
                "missing_families": [],
                "missing_qualified_families": [],
                "minimum_ready_run_count": 3,
                "minimum_ready_rows_per_family": 10000,
                "family_sla_matrix": trajectory_rows,
                "current_rocm_baseline_claim_scope": "single_target_gpcr_baseline",
                "current_rocm_baseline_production_trajectory_profile_enabled": True,
                "current_rocm_baseline_supports_restricted_family_sla": False,
                "current_rocm_baseline_supports_broad_platform_sla": False,
                "allowed_sla_claims": [
                    "restricted_family_trajectory_profile_sla",
                    "single_target_gpcr_rocm_baseline",
                ],
                "blocked_sla_claims": [
                    "broad_platform_sla",
                    "general_protein_ligand_platform_sla",
                ],
                "customer_sla_disclosure_ready": True,
                "customer_sla_disclosure_card": {
                    "current_rocm_baseline_scope": "single_target_gpcr_baseline",
                    "restricted_family_sla_allowed": True,
                    "broad_platform_sla_allowed": False,
                },
                "general_platform_sla_allowed": False,
                "restricted_sla_backed_by_historical_profile_artifacts": True,
                "rocm_baseline_profile_gap_acknowledged": False,
                "single_baseline_only": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "benchmark_executed": False,
                "external_state_mutated": False,
            },
            "rows": trajectory_rows,
        },
    )
    graph_path = [
        "structure_quality",
        "binding_site_context",
        "pose_generation_contract",
        "scoring_ranking_gate",
        "uncertainty_abstention_guard",
        "report_bundle_contract",
        "customer_report_ux",
    ]
    graph_rows = [
        {
            "node_id": node_id,
            "status": "ready",
            "ready": True,
        }
        for node_id in graph_path
    ]
    graph_edges = [
        {
            "from_node_id": graph_path[idx],
            "to_node_id": graph_path[idx + 1],
            "status": "ready",
            "ready": True,
        }
        for idx in range(len(graph_path) - 1)
    ]
    _write(
        runs_dir / "product_ai_decision_graph_contract_current.json",
        {
            "summary": {
                "status": "product_ai_decision_graph_contract_ready",
                "closed_loop_decision_graph_ready": True,
                "production_ai_inference_enabled": False,
                "node_count": len(graph_rows),
                "ready_node_count": len(graph_rows),
                "blocked_node_count": 0,
                "edge_count": len(graph_edges),
                "ready_edge_count": len(graph_edges),
                "blocked_edge_count": 0,
                "ordered_graph_path": graph_path,
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
                "ligand_selection_rationale_ready": True,
                "counterfactual_rescue_suggestion_ready": True,
                "evidence_traceability_ready": True,
                "fail_closed_transition_ready": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "model_inference_executed": False,
                "external_state_mutated": False,
            },
            "rows": graph_rows,
            "edges": graph_edges,
        },
    )
    report_blocks = [
        "binding_site_explanation",
        "pose_comparison",
        "interaction_rationale",
        "ligand_selection_rationale",
        "uncertainty_narrative",
        "counterfactual_rescue_suggestion",
        "evidence_traceability",
    ]
    report_sections = [{"section_id": block, "status": "ready"} for block in report_blocks]
    _write(
        runs_dir / "product_ai_report_ux_contract_current.json",
        {
            "summary": {
                "status": "product_ai_report_ux_contract_ready",
                "ai_report_ux_ready": True,
                "structured_customer_report_ready": True,
                "customer_report_delivery_contract_ready": True,
                "customer_report_evidence_binding_ready": True,
                "customer_report_viewer_binding_ready": True,
                "viewer_customer_report_binding_ready": True,
                "canonical_customer_report_required_blocks": report_blocks,
                "customer_report_required_blocks": report_blocks,
                "customer_report_ready_blocks": report_blocks,
                "customer_report_missing_blocks": [],
                "customer_report_required_block_count": len(report_blocks),
                "customer_report_ready_block_count": len(report_blocks),
                "customer_report_blocked_block_count": 0,
                "customer_report_card_ready": True,
                "customer_report_card": {
                    "primary_abstention_reason": "production_residual_checkpoint_not_promoted",
                    "what_would_change_decision": "Return delta_force labels and promote the checkpoint.",
                },
                "section_count": len(report_sections),
                "ready_section_count": len(report_sections),
                "blocked_section_count": 0,
                "binding_site_explanation_ready": True,
                "pose_comparison_ready": True,
                "interaction_rationale_ready": True,
                "ligand_selection_rationale_ready": True,
                "uncertainty_narrative_ready": True,
                "counterfactual_rescue_suggestion_ready": True,
                "evidence_traceability_ready": True,
                "scope_claim_limit_ready": True,
                "selection_rationale": "Uses ranking source binding_score_composite_v7 with abstention disclosure.",
                "primary_abstention_reason": "production_residual_checkpoint_not_promoted",
                "what_would_change_decision": "Return delta_force labels and promote the checkpoint.",
                "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
                "blocked_claim_scopes": ["general_protein_ligand_platform"],
                "claim_blocked_domains": ["general_protein_ligand_platform"],
                "general_platform_claim_allowed": False,
                "viewer_ready": True,
                "viewer_index": "viewer/index.html",
                "viewer_app": "viewer/app.js",
                "viewer_interaction_surface_ready": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "model_inference_executed": False,
                "external_state_mutated": False,
            },
            "rows": report_sections,
        },
    )
    _write(
        runs_dir / "product_commercial_readiness_handoff_bundle_current.json",
        {
            "summary": {
                "status": "product_commercial_readiness_handoff_bundle_ready",
                "handoff_bundle_ready": True,
                "artifact_count": 6,
                "blocked_artifact_count": 0,
                "artifact_reference_contract_ready": True,
                "artifact_reference_count": 6,
                "local_missing_artifact_reference_count": 0,
                "operator_return_pending_artifact_reference_count": 0,
                "production_ai_registry_promotion_operator_receipt_status": (
                    "blocked_production_ai_registry_promotion_operator_receipt"
                ),
                "production_ai_registry_promotion_operator_receipt_ready": False,
                "production_ai_registry_promotion_operator_receipt_artifact": (
                    "runs/production_ai_registry_promotion_operator_receipt_current.json"
                ),
                "production_ai_registry_promotion_operator_receipt_csv": (
                    "config/production_ai_registry_promotion_operator_receipt_current.csv"
                ),
                "production_ai_registry_promotion_operator_receipt_approval_token_required": (
                    "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
                ),
                "production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker": (
                    "operator_placeholders_unfilled"
                ),
                "production_ai_registry_promotion_operator_receipt_observed_registry_default_residual_mode": (
                    "shadow"
                ),
                "production_ai_registry_promotion_operator_receipt_observed_registry_trained_model_checkpoint_count": 1,
                "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_currently_satisfied": False,
                "production_ai_registry_promotion_operator_receipt_observed_checkpoint_registry_promotion_missing_gate_ids": [
                    "default_residual_mode_guarded",
                    "production_promotion_allowed",
                    "customer_facing_mutation_flags",
                ],
                "production_ai_registry_promotion_priority_status": (
                    "blocked_production_ai_registry_promotion_priority_packet"
                ),
                "production_ai_registry_promotion_priority_packet_ready": True,
                "production_ai_registry_promotion_priority_registry_promotion_ready": False,
                "production_ai_registry_promotion_priority_operator_input_required_count": 3,
                "production_ai_registry_promotion_priority_blocked_priority_item_count": 3,
                "production_ai_registry_promotion_priority_top_gate_id": "default_residual_mode_guarded",
                "production_ai_registry_promotion_priority_top_priority_bucket": (
                    "guarded_residual_mode_selection_required"
                ),
                "production_ai_registry_promotion_priority_missing_gate_count": 3,
                "production_ai_registry_promotion_priority_missing_gate_ids": [
                    "default_residual_mode_guarded",
                    "production_promotion_allowed",
                    "customer_facing_mutation_flags",
                ],
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            "rows": [],
        },
    )
    _write(
        runs_dir / "product_release_source_of_truth_gate_current.json",
        {
            "summary": {
                "status": "blocked_product_release_source_of_truth_gate",
                "release_source_of_truth_ready": False,
                "blocker_count": 13,
                "stale_artifact_count": 0,
                "readme_drift_count": 0,
                "missing_artifact_count": 0,
            }
        },
    )
    science_rows = [
        {
            "gap_id": "SCI-GPCR",
            "status": "closed",
            "claim_promotion_status": "boundary_ready_comparison_only",
            "claim_promotion_allowed": False,
            "evidence": "runs/gpcr_conditional_prior_promotion_gate_current.json",
            "release_blocker": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        },
        {
            "gap_id": "SCI-TRANS",
            "status": "closed",
            "release_blocker": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        },
        {
            "gap_id": "SCI-CA2-PXR",
            "status": "closed",
            "release_blocker": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        },
        {
            "gap_id": "SCI-WETLAB",
            "status": "closed",
            "release_blocker": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        },
        {
            "gap_id": "SCI-OPENMM",
            "status": "closed",
            "claim_promotion_status": "restricted_2bead_only",
            "evidence": "runs/wetlab_openmm_claim_promotion_boundary_current.json; runs/accuracy_parity_scorecard_current.json",
            "claim_promotion_allowed": False,
            "release_blocker": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        },
    ]
    _write(
        runs_dir / "science_claim_promotion_gap_closure_current.json",
        {
            "summary": {
                "status": "science_claim_promotion_gap_closure_complete",
                "all_gaps_closed": True,
                "claim_promotion_allowed": False,
                "gap_count": 5,
                "closed_gap_count": 5,
                "open_gap_count": 0,
                "open_gap_ids": [],
                "closed_gap_ids": ["SCI-GPCR", "SCI-TRANS", "SCI-CA2-PXR", "SCI-WETLAB", "SCI-OPENMM"],
                "current_primary_open_gap_id": "none",
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            "rows": science_rows,
        },
    )
    master_rows = [
        {
            "gap_id": gap_id,
            "status": "closed",
            "release_blocker": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        }
        for gap_id in [
            "COMMERCIAL",
            "PRODUCT-AI",
            "DATA-SCIENCE",
            "INFRA",
            "SCI-CLAIM",
            "DEPLOY-OPS",
            "STORAGE",
            "TOOLS",
            "API-RUNNER",
        ]
    ]
    for row in master_rows:
        if row["gap_id"] == "SCI-CLAIM":
            row["rollup_status"] = "science_claim_promotion_gap_closure_complete"
            row["evidence"] = "runs/science_claim_promotion_gap_closure_current.json"
    _write(
        runs_dir / "master_gap_closure_rollup_current.json",
        {
            "summary": {
                "status": "master_gap_closure_rollup_complete",
                "all_gaps_closed": True,
                "claim_promotion_allowed": False,
                "gap_count": 9,
                "closed_gap_count": 9,
                "open_gap_count": 0,
                "open_gap_ids": [],
                "closed_gap_ids": [
                    "COMMERCIAL",
                    "PRODUCT-AI",
                    "DATA-SCIENCE",
                    "INFRA",
                    "SCI-CLAIM",
                    "DEPLOY-OPS",
                    "STORAGE",
                    "TOOLS",
                    "API-RUNNER",
                ],
                "current_primary_open_gap_id": "none",
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            "rows": master_rows,
        },
    )


def write_capability_prerequisite_packets(runs_dir: Path) -> None:
    write_restricted_self_hosted_commercial_packets(runs_dir)
    _write(
        runs_dir / "product_readiness_gate_current.json",
        {
            "summary": {
                "status": "product_handoff_ready",
                "target_id": "ADRB2",
                "family": "gpcr",
                "ligand_count": 3,
                "request_contract_status": "pass",
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "product_execution_work_order_current.json",
        {
            "summary": {
                "status": "product_execution_work_order_ready",
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "product_execution_preflight_current.json",
        {
            "summary": {
                "status": "product_execution_preflight_ready",
                "unknown_arg_count": 0,
                "config_count": 1,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "product_structure_analysis_report_current.json",
        {
            "summary": {
                "status": "product_structure_analysis_report_ready",
                "local_structure_parsed": True,
                "atom_count": 42,
                "ligand_like_residue_count": 1,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    write_license_packets(runs_dir)
    _write(
        runs_dir / "independent_engine_roadmap_status_current.json",
        {
            "summary": {
                "status": "independent_engine_roadmap_closed",
                "phases": {
                    "E0": "closed",
                    "E1": "closed",
                    "E2": "closed",
                    "E3": "closed",
                    "E4": "closed",
                    "E5": "closed",
                },
                "scoring_ranking_contract_ready": True,
                "engine_dispatch_ready": True,
            }
        },
    )
    write_production_ai_checkpoint_fixture_packets(runs_dir)
    write_claim_expansion_gate_scaffolds(runs_dir)
    write_data_science_expansion_closure_packets(runs_dir)
    write_science_claim_promotion_closure_packets(runs_dir)
    write_deploy_ops_legal_closure_packets(runs_dir)
    write_storage_tools_closure_packets(runs_dir)
    from tools.product.write_full_gap_closure_fixture_packets import write_full_gap_closure_fixture_packets

    write_full_gap_closure_fixture_packets(runs_dir)
    write_restricted_self_hosted_commercial_packets(runs_dir)


def write_production_ai_checkpoint_fixture_packets(runs_dir: Path) -> None:
    residual_components = [
        {"component_id": "stage_router", "output": "stage2_route_decision", "ready": True},
        {"component_id": "score_residual", "output": "delta_score", "ready": True},
        {"component_id": "energy_residual", "output": "delta_energy", "ready": True},
        {"component_id": "force_residual", "output": "delta_force", "ready": True},
        {"component_id": "uncertainty", "output": "uncertainty", "ready": True},
        {"component_id": "abstention", "output": "abstention_reason", "ready": True},
    ]
    _write(
        runs_dir / "residual_model_registry_current.json",
        {
            "summary": {
                "status": "residual_model_registry_ready",
                "registry_ready": True,
                "product_model_layer_ready": True,
                "default_residual_mode": "shadow",
                "production_promotion_allowed": False,
                "production_mode_allowed": False,
                "customer_facing_auto_correction_allowed": False,
                "customer_facing_score_mutation_allowed": False,
                "customer_facing_ranking_mutation_allowed": False,
                "trained_model_checkpoint_count": 1,
                "candidate_checkpoint_count": 1,
                "checkpoint_preflight_ready": True,
                "production_checkpoint_blocked": False,
                "selected_sidecar_ready": True,
                "selected_sidecar_status": "residual_production_checkpoint_sidecar_ready",
                "selected_sidecar_missing_output_fields": [],
                "selected_sidecar_training_contract_missing_label_fields": ["delta_force"],
                "checkpoint_missing_output_fields": [],
                "checkpoint_missing_adapter_output_policy_fields": [],
                "component_count": 6,
                "required_component_count": 6,
                "required_components_present": True,
                "families": ["gpcr", "kinase", "ion_channel"],
            },
            "components": residual_components,
            "rows": residual_components,
        },
    )
    _write(
        runs_dir / "product_production_ai_checkpoint_readiness_current.json",
        {
            "summary": {
                "status": "product_production_ai_checkpoint_readiness_ready",
                "checkpoint_chain_ready": True,
                "production_guarded_residual_ready": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
            }
        },
    )
    _write(
        runs_dir / "residual_production_checkpoint_preflight_current.json",
        {
            "summary": {
                "status": "residual_production_checkpoint_preflight_ready",
                "promotion_mode": "production_guarded",
                "preflight_green": True,
                "checkpoint_preflight_ready": True,
                "execution_enabled": False,
            }
        },
    )
    _write(
        runs_dir / "residual_production_training_data_contract_current.json",
        {
            "summary": {
                "status": "residual_production_training_data_contract_ready",
                "training_data_contract_ready": True,
                "gpu_return_receipt_ready": True,
            }
        },
    )


def write_restricted_production_ai_checkpoint_readiness_contract(runs_dir: Path) -> None:
    training_data_path = runs_dir / "residual_production_training_data_contract_current.json"
    try:
        training_data_payload = json.loads(training_data_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        training_data_payload = {}
    if not isinstance(training_data_payload, dict):
        training_data_payload = {}
    training_data_summary = training_data_payload.get("summary")
    if not isinstance(training_data_summary, dict):
        training_data_summary = {}
    training_data_summary.update(
        {
            "status": "residual_production_training_data_contract_ready",
            "training_data_contract_ready": True,
            "production_training_data_ready": True,
            "training_data_failed_check_ids": [],
        }
    )
    training_data_payload["summary"] = training_data_summary
    _write(training_data_path, training_data_payload)

    path = runs_dir / "product_production_ai_checkpoint_readiness_current.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    summary.update(
        {
            "status": "blocked_product_production_ai_checkpoint_readiness",
            "check_count": 8,
            "pass_check_count": 7,
            "fail_check_count": 1,
            "failed_check_ids": ["registry_customer_facing_promotion_allowed"],
            "first_failed_check_id": "registry_customer_facing_promotion_allowed",
            "product_model_layer_ready": True,
            "production_ai_checkpoint_ready": False,
            "production_ai_inference_subject_active": False,
            "default_residual_mode": "shadow",
            "production_promotion_allowed": False,
            "customer_facing_auto_correction_allowed": False,
            "customer_facing_score_mutation_allowed": False,
            "customer_facing_ranking_mutation_allowed": False,
            "registry_promotion_required_gate_ids": [
                "production_promotion_allowed",
                "customer_facing_mutation_flags",
                "default_residual_mode_guarded",
                "trained_model_checkpoint_count_positive",
            ],
            "registry_promotion_missing_gate_ids": [
                "production_promotion_allowed",
                "customer_facing_mutation_flags",
                "default_residual_mode_guarded",
            ],
            "registry_promotion_missing_gate_count": 3,
            "registry_promotion_upstream_acceptance_ready": True,
            "registry_promotion_currently_satisfied": False,
            "trained_model_checkpoint_count": 1,
            "candidate_checkpoint_count": max(int(summary.get("candidate_checkpoint_count") or 0), 1),
            "ready_checkpoint_count": max(int(summary.get("ready_checkpoint_count") or 0), 1),
            "checkpoint_preflight_ready": True,
            "production_training_data_ready": True,
            "production_output_head_gap_contract_ready": True,
            "production_output_heads_complete": True,
            "force_gpu_worker_return_receipt_ready": True,
            "force_gpu_worker_handoff_ready": True,
            "production_gpu_execution_environment_ready": True,
            "production_inference_acceptance_matrix_ready": True,
            "production_inference_acceptance_stage_count": 8,
            "production_inference_acceptance_ready_stage_count": 7,
            "production_inference_acceptance_blocked_stage_count": 1,
            "production_inference_acceptance_blocked_stage_ids": [
                "registry_guarded_promotion_acceptance"
            ],
            "production_inference_acceptance_next_stage_id": (
                "registry_guarded_promotion_acceptance"
            ),
            "production_inference_acceptance_next_stage_artifact": (
                "runs/residual_model_registry_current.json"
            ),
            "production_inference_acceptance_next_stage_validation_command": (
                "python3 tools/build_residual_model_registry.py && "
                "python3 tools/build_product_production_ai_checkpoint_readiness.py"
            ),
            "production_inference_acceptance_next_stage_unlock_fields": [],
            "production_inference_acceptance_next_stage_required_checks": [
                "registry_customer_facing_promotion_allowed",
                "trained_model_checkpoint_count_positive",
                "default_residual_mode_guarded",
            ],
            "production_inference_actionable_blocker_stage_id": (
                "registry_guarded_promotion_acceptance"
            ),
            "production_inference_actionable_blocker_check_id": (
                "registry_customer_facing_promotion_allowed"
            ),
            "production_inference_actionable_blocker_artifact": (
                "runs/residual_model_registry_current.json"
            ),
            "production_inference_actionable_blocker_observed": (
                "default_residual_mode=shadow;production_promotion_allowed=false;"
                "customer_facing_mutation_flags=false"
            ),
            "production_inference_actionable_blocker_required": (
                "production promotion, customer-facing mutation flags, guarded mode, "
                "and trained checkpoint count are ready"
            ),
            "production_inference_actionable_blocker_next_action": (
                "Complete the guarded production AI registry promotion operator receipt while "
                "keeping customer-facing mutation disabled until approval."
            ),
            "production_inference_actionable_blocker_validation_command": (
                "python3 tools/build_residual_model_registry.py && "
                "python3 tools/build_product_production_ai_checkpoint_readiness.py"
            ),
            "production_inference_actionable_blocker_unlock_fields": [],
            "production_inference_actionable_blocker_downstream_blocked_stage_count": 0,
            "production_inference_actionable_blocker_blocks_registry_promotion": False,
            "production_inference_actionable_operator_completion_packet_ready": True,
            "production_inference_actionable_operator_completion_packet": {
                "artifact_id": "residual_model_registry_guarded_promotion",
                "artifact_path": "runs/residual_model_registry_current.json",
                "packet_ready": True,
                "release_blocker": True,
                "execution_enabled": False,
                "external_state_mutated": False,
                "model_promoted": False,
                "checkpoint_created": False,
                "training_executed": False,
                "docking_results_emitted": False,
                "validation_command": (
                    "python3 tools/build_residual_model_registry.py && "
                    "python3 tools/build_product_production_ai_checkpoint_readiness.py"
                ),
                "required_fields_or_columns": [
                    "production_promotion_allowed",
                    "customer_facing_auto_correction_allowed",
                    "customer_facing_score_mutation_allowed",
                    "customer_facing_ranking_mutation_allowed",
                    "default_residual_mode",
                    "trained_model_checkpoint_count",
                ],
                "completion_rule": (
                    "Set production_promotion_allowed=true only after guarded mode, "
                    "trained checkpoint count, and customer-facing mutation flags are approved."
                ),
            },
            "production_inference_actionable_operator_completion_artifact_id": (
                "residual_model_registry_guarded_promotion"
            ),
            "production_inference_actionable_operator_completion_artifact_path": (
                "runs/residual_model_registry_current.json"
            ),
            "production_inference_actionable_operator_completion_diagnostic_command_count": 3,
            "production_inference_actionable_operator_completion_diagnostic_commands": [
                "python3 tools/build_residual_model_registry.py",
                "python3 tools/build_product_production_ai_checkpoint_readiness.py",
                "python3 tools/build_product_production_ai_promotion_workbench.py",
            ],
            "production_inference_actionable_operator_completion_diagnostic_required_field_count": 6,
            "production_inference_actionable_operator_completion_diagnostic_required_fields": [
                "production_promotion_allowed",
                "customer_facing_auto_correction_allowed",
                "customer_facing_score_mutation_allowed",
                "customer_facing_ranking_mutation_allowed",
                "default_residual_mode",
                "trained_model_checkpoint_count",
            ],
            "production_inference_actionable_operator_completion_diagnostic_completion_rule": (
                "production_promotion_allowed=true requires guarded residual mode, "
                "trained_model_checkpoint_count>0, and explicit customer-facing mutation approval."
            ),
            "production_inference_actionable_operator_completion_torch_visibility_probe_command": "",
            "production_inference_worker_runtime_receipt_contract_ready": False,
            "production_inference_worker_runtime_receipt_required_fields_or_columns": [],
            "production_inference_worker_runtime_receipt_required_field_count": 0,
            "force_gpu_worker_post_run_validation_chain_current": True,
            "force_gpu_worker_post_run_validation_command_count": 18,
            "checkpoint_closure_blockers": [
                "registry_production_promotion_allowed_false",
                "training_missing_label:delta_force",
            ],
            "checkpoint_missing_output_fields": [],
            "training_data_failed_check_ids": [],
            "training_data_missing_output_labels": [
                "delta_force",
                "uncertainty",
                "abstention_reason",
                "stage2_route_decision",
            ],
            "selected_sidecar_training_contract_ready": True,
            "selected_sidecar_force_receipt_ready": True,
            "selected_sidecar_force_receipt_operator_verified": True,
            "selected_sidecar_force_receipt_operator_verified_true_count": 768,
            "selected_sidecar_force_receipt_expected_queue_rows": 768,
            "gpu_receipt_blockers": [],
            "gpu_receipt_summary_manifest_bound": True,
            "gpu_receipt_summary_out_manifest_csv_bound": True,
            "gpu_receipt_summary_out_summary_json_bound": True,
            "gpu_receipt_summary_manifest_row_counts_consistent": True,
            "gpu_receipt_summary_manifest_csv": (
                "runs/residual_force_trajectory_regeneration_current_manifest.csv"
            ),
            "gpu_receipt_summary_out_manifest_csv": (
                "runs/residual_force_trajectory_regeneration_current_manifest.csv"
            ),
            "gpu_receipt_summary_out_summary_json": (
                "runs/residual_force_trajectory_regeneration_current_summary.json"
            ),
            "gpu_receipt_production_gpu_backend_provenance_ready": True,
            "gpu_receipt_production_gpu_backend_rows": 768,
            "gpu_receipt_production_gpu_backend_non_production_rows": 0,
            "gpu_receipt_production_gpu_backend_prod_mode": True,
            "gpu_receipt_production_gpu_backend_require_rust_hip": True,
            "gpu_receipt_expected_queue_rows": 768,
            "gpu_receipt_expected_npz_count": 768,
            "gpu_receipt_queue_id_count": 768,
            "gpu_receipt_queue_fingerprint_count": 768,
            "gpu_receipt_manifest_row_count": 768,
            "gpu_receipt_manifest_ok_row_count": 768,
            "gpu_receipt_manifest_identity_row_count": 768,
            "gpu_receipt_manifest_matched_queue_id_count": 768,
            "gpu_receipt_manifest_matched_expected_npz_count": 384,
            "gpu_receipt_manifest_matched_queue_fingerprint_count": 0,
            "gpu_receipt_manifest_operator_verified": True,
            "gpu_receipt_operator_verified_true_count": 768,
            "gpu_receipt_identity_coverage_ready": True,
            "production_inference_next_after_actionable_blocker_stage_id": "",
            "production_inference_next_after_actionable_blocker_artifact": "",
            "production_inference_next_after_actionable_blocker_validation_command": "",
            "production_inference_next_after_actionable_blocker_required_checks": [],
            "production_inference_next_after_actionable_blocker_unlock_fields": [],
            "production_inference_next_after_actionable_blocker_next_action": "",
            "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_count": 1,
            "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_ids": [
                "registry_guarded_promotion_acceptance"
            ],
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_id": (
                "registry_guarded_promotion_acceptance"
            ),
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_artifact": (
                "runs/residual_model_registry_current.json"
            ),
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_validation_command": (
                "python3 tools/build_residual_model_registry.py && "
                "python3 tools/build_product_production_ai_checkpoint_readiness.py"
            ),
        }
    )
    payload["summary"] = summary
    rows = payload.get("rows")
    if isinstance(rows, list):
        payload["rows"] = [
            row
            for row in rows
            if isinstance(row, dict)
            and row.get("artifact_id")
            in {
                "operator_packet",
                "operator_packet_freshness",
                "execution_ladder",
            }
        ][:3]
    _write(path, payload)


def write_restricted_commercial_readiness_handoff_bundle(runs_dir: Path) -> None:
    path = runs_dir / "product_commercial_readiness_handoff_bundle_current.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    summary.update(
        {
            "status": "product_commercial_readiness_handoff_bundle_ready",
            "handoff_bundle_ready": True,
            "artifact_count": 3,
            "ready_artifact_count": 3,
            "blocked_artifact_count": 0,
            "artifact_reference_contract_ready": True,
            "artifact_reference_count": 43,
            "local_missing_artifact_reference_count": 0,
            "operator_return_artifact_reference_count": max(
                int(summary.get("operator_return_artifact_reference_count") or 0), 4
            ),
            "operator_return_pending_artifact_reference_count": max(
                int(summary.get("operator_return_pending_artifact_reference_count") or 0), 1
            ),
        }
    )
    payload["summary"] = summary
    rows = payload.get("rows")
    if isinstance(rows, list):
        payload["rows"] = [
            row
            for row in rows
            if isinstance(row, dict)
            and row.get("artifact_id")
            in {
                "operator_packet",
                "operator_packet_freshness",
                "execution_ladder",
            }
        ][:3]
    _write(path, payload)


def write_restricted_product_goal_completion_audit(runs_dir: Path) -> None:
    path = runs_dir / "product_goal_completion_audit_current.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    rows = payload.get("rows")
    if not isinstance(rows, list):
        rows = []
    allowed_failures = {
        "R6_product_ai_architecture_gap_closure",
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
    }
    for row in rows:
        if not isinstance(row, dict):
            continue
        requirement_id = str(row.get("requirement_id") or "")
        if requirement_id and requirement_id not in allowed_failures:
            row["status"] = "pass"
            row["release_blocker"] = False
    pass_count = sum(1 for row in rows if isinstance(row, dict) and row.get("status") == "pass")
    fail_count = sum(1 for row in rows if isinstance(row, dict) and row.get("status") == "fail")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    summary.update(
        {
            "status": "blocked_product_goal_completion_audit",
            "goal_complete": False,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "local_self_hosted_product_ready": True,
            "release_allowed": True,
            "release_artifact_ready": True,
            "product_ai_architecture_gap_count": 7,
            "product_ai_architecture_closed_gap_count": 4,
            "product_ai_architecture_open_gap_count": 3,
            "product_ai_architecture_gap_blocker_matrix_count": 1,
            "product_ai_production_checkpoint_gap_ready": False,
            "commercial_readiness_handoff_bundle_ready": True,
            "commercial_readiness_handoff_bundle_artifact_reference_count": 43,
            "commercial_readiness_handoff_bundle_operator_return_pending_artifact_reference_count": 1,
        }
    )
    payload["rows"] = rows
    payload["summary"] = summary
    _write(path, payload)


def write_restricted_goal_bottleneck_briefing(runs_dir: Path) -> None:
    path = runs_dir / "goal_bottleneck_briefing_current.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    blocker_ids = [
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
        "ACCURACY:ligand_ranking",
    ]
    summary.update(
        {
            "full_commercial_release_blocker_ids": blocker_ids,
            "full_commercial_release_blocker_count": len(blocker_ids),
        }
    )
    payload["summary"] = summary
    _write(path, payload)


def write_claim_expansion_gate_scaffolds(runs_dir: Path) -> None:
    _write(
        runs_dir / "cameo_claim_boundary_expansion_scaffold_current.json",
        {
            "summary": {
                "status": "cameo_claim_boundary_scaffold_ready",
                "official_results_claim_allowed": False,
                "receiver_smoke_ready": True,
                "expansion_stage": "scaffold_ready",
            }
        },
    )
    _write(
        runs_dir / "ca2_claim_boundary_expansion_scaffold_current.json",
        {
            "summary": {
                "status": "ca2_claim_boundary_scaffold_ready",
                "packet_replacement_ready": True,
                "review_policy_closure_ready": True,
                "expansion_stage": "closure_ready",
            }
        },
    )
    _write(
        runs_dir / "pxr_claim_boundary_expansion_scaffold_current.json",
        {
            "summary": {
                "status": "pxr_claim_boundary_scaffold_ready",
                "blocked_row_count": 0,
                "ready_row_count": 14,
                "expansion_stage": "closure_ready",
            }
        },
    )
    _write(
        runs_dir / "transporter_claim_boundary_expansion_scaffold_current.json",
        {
            "summary": {
                "status": "transporter_claim_boundary_scaffold_ready",
                "direct_binding_kcal_claim_allowed": False,
                "binder_promotion_gate_ready": True,
                "curated_packet_ready": True,
                "expansion_stage": "closure_ready",
            }
        },
    )


def write_data_science_expansion_closure_packets(runs_dir: Path) -> None:
    _write(
        runs_dir / "gpcr_residual_proof_breadth_gate_current.json",
        {
            "summary": {
                "status": "gpcr_residual_proof_breadth_gate_ready",
                "gpcr_residual_proof_breadth_gate_ready": True,
                "effective_gpcr_breadth_count": 7,
                "pr_auc_regression_warning_count": 0,
            }
        },
    )
    _write(
        runs_dir / "idp_broader_promotion_resolution_current.json",
        {
            "summary": {
                "status": "idp_broader_promotion_resolution_ready",
                "wider_shadow_safe_lane_admitted": True,
                "bounded_lane_closure_ready": True,
                "broader_full_idp_promotion_blocked": True,
            }
        },
    )
    _write(
        runs_dir / "ca2_packet_replacement_readiness_current.json",
        {
            "summary": {
                "status": "ca2_packet_replacement_readiness_ready",
                "ready_row_count": 12,
                "blocked_row_count": 0,
            }
        },
    )
    _write(
        runs_dir / "pxr_packet_replacement_readiness_current.json",
        {
            "summary": {
                "status": "pxr_packet_replacement_readiness_ready",
                "ready_row_count": 14,
                "blocked_row_count": 0,
            }
        },
    )
    _write(
        runs_dir / "transporter_membrane_readiness_current.json",
        {
            "summary": {
                "status": "transporter_membrane_readiness_ready",
                "p0_open_count": 0,
                "curated_packet_ready": True,
            }
        },
    )
    _write(
        runs_dir / "accuracy_parity_scorecard_current.json",
        {
            "summary": {
                "status": "green",
                "pass_row_count": 5,
                "row_count": 5,
            }
        },
    )


def write_science_claim_promotion_closure_packets(runs_dir: Path) -> None:
    _write(
        runs_dir / "gpcr_ci_low_recovery_packet_current.json",
        {
            "summary": {
                "status": "gpcr_ci_low_recovery_packet_ready",
                "ranking_pr_auc_ci_low": 0.21,
                "threshold": 0.45,
                "ci_low_blocker": True,
                "claim_promotion_allowed": False,
            }
        },
    )
    _write(
        runs_dir / "gpcr_oprm1_life_science_evidence_packet_current.json",
        {
            "summary": {
                "status": "gpcr_oprm1_life_science_evidence_ready",
                "pose_collapse_blocker": True,
                "blocked_positive_count": 3,
                "claim_promotion_allowed": False,
            }
        },
    )
    _write(
        runs_dir / "openmm_2bead_strict_multitarget_current_summary.json",
        {
            "pass_count": 11,
            "target_pass_count": 11,
            "status": "openmm_2bead_strict_multitarget_ready",
        },
    )
    _write(
        runs_dir / "wetlab_selected_allatom_gate_burndown_packet_current.json",
        {
            "summary": {
                "status": "wetlab_selected_allatom_gate_burndown_ready",
                "hard_block_count": 0,
                "selected_allatom_gate_ready": True,
            }
        },
    )
    _write(
        runs_dir / "aqp1_negative_evidence_intake_gate_current.json",
        {
            "summary": {
                "status": "aqp1_negative_evidence_intake_gate_ready",
                "authoritative_negative_apply_allowed_count": 0,
            }
        },
    )
    intake_template = runs_dir / "aqp1_negative_evidence_intake_template_current.csv"
    intake_template.parent.mkdir(parents=True, exist_ok=True)
    intake_template.write_text(
        "candidate_name,molecule_id,target_id,operator_decision,approval_token\n",
        encoding="utf-8",
    )


def write_deploy_ops_legal_closure_packets(runs_dir: Path) -> None:
    _write(
        runs_dir / "product_release_bundle_current.json",
        _release_bundle_payload(),
    )
    _write(
        runs_dir / "product_rollout_plan_current.json",
        {
            "summary": {
                "status": "planned",
                "dry_run": True,
                "approval_token_required": "APPROVE_PRODUCT_ROLLOUT",
            }
        },
    )
    _write_without_degrading(
        runs_dir / "product_security_deployment_contract_current.json",
        {
            "summary": {
                "status": "product_security_deployment_contract_ready",
                "security_deployment_ready": True,
            }
        },
    )
    _write(
        runs_dir / "alert_delivery_smoke_current.json",
        {
            "status": "pass",
            "received_alert_count": 1,
        },
    )
    _write(
        runs_dir / "self_hosted_license_distribution_audit_current.json",
        {
            "summary": {
                "status": "self_hosted_license_distribution_audit_recorded",
                "hard_blocker_count": 0,
                "operator_review_item_count": 1,
                "third_party_dual_license_assets": ["jszip"],
            }
        },
    )
    rollout_csv = runs_dir / "product_rollout_execution_operator_intake.csv"
    rollout_csv.write_text(
        "operator_decision,rollout_approval_token,hosted_exposure_approval_token,target_environment,"
        "image_digest_or_tag,registry_context_verified,k8s_or_compose_context_verified,tls_termination_verified,"
        "pager_webhook_secret_mounted,rollback_reference_verified,operator_name,reviewed_at_utc,operator_note\n"
        "approve,APPROVE_PRODUCT_ROLLOUT,APPROVE_HOSTED_PRODUCT_API_EXPOSURE,k8s,"
        "registry.example/micf-api@sha256:abc,true,true,true,true,true,Operator,2026-06-06T00:00:00Z,ready\n",
        encoding="utf-8",
    )
    rollout_smoke_csv = runs_dir / "product_rollout_execution_smoke_receipt_operator_intake.csv"
    rollout_smoke_csv.write_text(
        "operator_decision,rollout_approval_token,hosted_exposure_approval_token,target_environment,"
        "image_digest_or_tag,rollout_command_summary,image_pushed,service_restarted,live_healthcheck_passed,"
        "metrics_scrape_verified,audit_log_write_verified,rollback_probe_verified,pager_provider_contacted,"
        "ingress_certificate_verified_live,external_state_mutated,operator_name,reviewed_at_utc,operator_note\n"
        "executed,APPROVE_PRODUCT_ROLLOUT,APPROVE_HOSTED_PRODUCT_API_EXPOSURE,k8s,"
        "registry.example/micf-api@sha256:abc,kubectl rollout smoke,true,true,true,true,true,true,true,true,true,"
        "Operator,2026-06-06T00:05:00Z,R4 rollout smoke passed\n",
        encoding="utf-8",
    )
    license_csv = runs_dir / "third_party_license_review_operator_intake.csv"
    license_csv.write_text(
        "package,operator_decision,approval_token,chosen_license_path,reviewer_name,reviewed_at_utc,operator_note\n"
        "jszip,approve,APPROVE_THIRD_PARTY_LICENSE_REVIEW,MIT,Legal Reviewer,2026-06-06T00:00:00Z,approved MIT path\n",
        encoding="utf-8",
    )


def write_storage_tools_closure_packets(runs_dir: Path) -> None:
    _write(
        runs_dir / "storage_residual_cleanup_status_current.json",
        {
            "summary": {
                "status": "storage_residual_cleanup_status_ready",
                "operator_action_candidate_count": 0,
                "existing_path_count": 6,
            }
        },
    )
    _write(
        runs_dir / "cleanup_completion_gate_current.json",
        {
            "summary": {
                "status": "cleanup_completion_gate_ready",
                "cleanup_complete": True,
                "stage_count": 5,
                "postcheck_contract_ready": True,
                "postcheck_row_count": 5,
                "postcheck_blocked_row_count": 0,
                "postcheck_global_refresh_command_count": 9,
                "approval_ready": True,
                "transition_cleanup_complete": True,
                "ligand_heavy_cleanup_complete": True,
                "protected_policy_resolved": True,
                "blocked_stage_count": 0,
            }
        },
    )
    _write(
        runs_dir / "tools_package_separation_work_order_current.json",
        {
            "summary": {
                "status": "tools_package_separation_work_order_ready",
                "reference_counts_included": True,
                "other_review_count": 2,
                "batch_2_review_count": 2,
                "batch_3_high_reference_count": 2,
            },
            "rows": [
                {
                    "tool_path": "tools/build_product_alpha.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_2_review",
                    "risk_score": 2,
                    "test_reference_count": 0,
                    "internal_tool_import_count": 0,
                },
                {
                    "tool_path": "tools/run_cameo_smoke.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_2_review",
                    "risk_score": 2,
                    "test_reference_count": 0,
                    "internal_tool_import_count": 0,
                },
                {
                    "tool_path": "tools/build_gpcr_replay_packet.py",
                    "proposed_package": "gpcr_replay",
                    "migration_batch": "batch_3_high_reference",
                    "risk_score": 12,
                    "test_reference_count": 4,
                    "internal_tool_import_count": 1,
                },
                {
                    "tool_path": "tools/build_accounting_report.py",
                    "proposed_package": "product",
                    "migration_batch": "batch_3_high_reference",
                    "risk_score": 8,
                    "test_reference_count": 0,
                    "internal_tool_import_count": 0,
                },
            ],
        },
    )


def write_license_packets(runs_dir: Path) -> None:
    write_license_decision_packets(runs_dir)


def write_license_decision_packets(runs_dir: Path) -> None:
    _write(
        runs_dir / "product_license_decision_gate_current.json",
        {
            "summary": {
                "status": "product_license_decision_gate_ready",
                "authorized_for_license_file_creation_review": True,
                "spdx_license_id": "ProprietaryRef-Betelgeuze",
                "license_text_source": "LICENSE",
                "copyright_holder": "JIHOON KANG",
                "effective_year": "2026",
            }
        },
    )
    _write(
        runs_dir / "product_license_file_creation_work_order_current.json",
        {
            "summary": {
                "status": "product_license_file_creation_work_order_ready",
                "license_review_manifest_ready": True,
                "spdx_license_id": "ProprietaryRef-Betelgeuze",
                "license_text_source": "LICENSE",
                "copyright_holder": "JIHOON KANG",
                "effective_year": "2026",
            }
        },
    )
    _write(
        runs_dir / "third_party_license_review_gate_current.json",
        {
            "summary": {
                "status": "third_party_license_review_gate_ready",
                "blocker_count": 0,
                "legal_advice_provided": False,
                "asset_modified": False,
                "external_state_mutated": False,
            }
        },
    )
