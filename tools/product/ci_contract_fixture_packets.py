from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


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
    domain_rows = [
        {"domain": "ca2", "status": "ready"},
        {"domain": "pxr", "status": "ready"},
        {"domain": "all_atom", "status": "ready"},
        {"domain": "transporter", "status": "blocked"},
        {"domain": "idp_broad", "status": "blocked"},
        {"domain": "general_protein_ligand", "status": "blocked"},
    ]
    scope_acceptance_matrix = [
        {"stage_id": "scope_evidence_acquisition_preflight", "status": "ready"},
        {"stage_id": "transporter_claim_acceptance", "status": "blocked"},
        {"stage_id": "pxr_claim_acceptance", "status": "blocked"},
        {"stage_id": "breadth_domain_floor_acceptance", "status": "ready"},
        {"stage_id": "general_platform_claim_acceptance", "status": "blocked"},
    ]
    blocked_acceptance_matrix = [
        row for row in scope_acceptance_matrix if row["status"] == "blocked"
    ]
    summary.update(
        {
            "status": "blocked_product_scope_breadth_contract",
            "scope_breadth_ready": False,
            "scope_widened": False,
            "scope_claim_posture_ready": True,
            "restricted_scope_claim_allowed": True,
            "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
            "domain_count": 6,
            "ready_domain_count": 3,
            "missing_domain_count": 3,
            "ready_domains": ["ca2", "pxr", "all_atom"],
            "missing_domains": ["transporter", "idp_broad", "general_protein_ligand"],
            "first_blocked_domain": "transporter",
            "first_blocked_domain_artifact": "runs/transporter_blocker_capture_sheet_current.json",
            "first_blocked_domain_observed": (
                "supportive=6;pending=0;placeholder=0;donor_reopen=True;p0_open=1;"
                "claim_safe_binders=0;target_ready_for_promotion=GLUT1;"
                "target_blocked_for_promotion=AQP1;primary_blocker_target=AQP1;"
                "primary_blocker_step=core_binder_01;primary_blocker_candidate=bacopaside II;"
                "p0_closure_rows=1;p0_membrane_open=1;p0_aqp1_open=1;p0_glut1_open=0;"
                "p0_count_matches_readiness=True"
            ),
            "first_blocked_domain_requirement": (
                "supportive transporter evidence, zero pending capture, zero placeholder rows, "
                "donor policy reopen ready, P0 open count zero, and at least one claim-safe binder row"
            ),
            "first_blocked_domain_next_action": (
                "Close the remaining AQP1 core_binder_01 blocker before transporter domain promotion."
            ),
            "transporter_p0_closure_packet_ready": True,
            "transporter_p0_current_membrane_open_count": 1,
            "transporter_p0_closure_row_count": 1,
            "transporter_p0_count_matches_readiness": True,
            "transporter_p0_aqp1_core_open_count": 1,
            "transporter_p0_glut1_core_open_count": 0,
            "evidence_queue_next_operator_completion_aqp1_review_sidecar_ready": True,
            "evidence_queue_next_operator_completion_aqp1_review_candidate_name": "bacopaside II",
            "evidence_queue_next_operator_completion_aqp1_review_source_anchor": "PMID 27474162",
            "evidence_queue_next_operator_completion_aqp1_review_target_uniprot": "P29972",
            "evidence_queue_pxr_exact_review_sidecar_row_count": 0,
            "evidence_queue_next_pxr_exact_review_sidecar_ready": False,
            "evidence_queue_next_pxr_exact_review_row_id": "",
            "evidence_queue_next_pxr_exact_review_candidate_name": "",
            "evidence_queue_next_pxr_exact_review_required_evidence_mode": "",
            "evidence_queue_next_pxr_exact_review_target_match_confirmed": "",
            "evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol": "",
            "evidence_queue_next_pxr_exact_review_authoritative_apply_allowed": False,
            "evidence_queue_next_pxr_exact_review_scope_promotion_allowed": False,
            "pxr_source_modality_triage_ready": True,
            "pxr_source_modality_triage_artifact": "runs/pxr_source_modality_triage_current.json",
            "pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count": 0,
            "pxr_source_modality_direct_or_claim_safe_quantitative_ready_count": 0,
            "pxr_source_modality_next_review_candidate_name": "",
            "pxr_source_modality_next_review_source_modality": "",
            "transporter_target_ready_for_promotion_count": 1,
            "transporter_target_blocked_for_promotion_count": 1,
            "transporter_target_ready_for_promotion_ids": ["GLUT1"],
            "transporter_target_blocked_for_promotion_ids": ["AQP1"],
            "transporter_primary_blocker_target_id": "AQP1",
            "transporter_primary_blocker_packet_step": "core_binder_01",
            "transporter_primary_blocker_candidate_name": "bacopaside II",
            "allowed_claim_scopes": ["current_restricted_delivery_scope"],
            "blocked_claim_scopes": [
                "transporter_domain_promotion",
                "general_protein_ligand_platform",
            ],
            "blocked_claim_scope_count": 2,
            "general_platform_claim_allowed": False,
            "general_platform_claim_blocked": True,
            "general_protein_ligand_platform_ready": False,
            "scope_claim_boundary_detail": (
                "allowed_claim_scopes=current_restricted_delivery_scope;"
                "blocked_claim_scopes=transporter_domain_promotion,general_protein_ligand_platform;"
                "restricted_scope_claim_allowed=True;general_platform_claim_allowed=False;"
                "ready_domains=ca2,pxr,all_atom;missing_domains=transporter,idp_broad,general_protein_ligand"
            ),
            "scope_acceptance_matrix_ready": True,
            "scope_acceptance_stage_count": 5,
            "scope_acceptance_ready_stage_count": 2,
            "scope_acceptance_blocked_stage_count": 3,
            "scope_acceptance_stage_ids": [row["stage_id"] for row in scope_acceptance_matrix],
            "scope_acceptance_ready_stage_ids": [
                "scope_evidence_acquisition_preflight",
                "breadth_domain_floor_acceptance",
            ],
            "scope_acceptance_blocked_stage_ids": [
                "transporter_claim_acceptance",
                "pxr_claim_acceptance",
                "general_platform_claim_acceptance",
            ],
            "scope_acceptance_next_stage_id": "transporter_claim_acceptance",
            "scope_acceptance_next_stage_artifact": (
                "runs/transporter_manual_review_intake_template_current.json;"
                "runs/transporter_binder_promotion_gate_current.json"
            ),
            "scope_acceptance_next_stage_validation_command": (
                "python3 tools/build_transporter_manual_review_intake_template.py && "
                "python3 tools/build_transporter_binder_promotion_gate.py && "
                "python3 tools/build_product_scope_breadth_contract.py"
            ),
            "scope_acceptance_next_stage_release_effect": (
                "transporter claim-safe evidence is accepted for scope promotion review"
            ),
            "scope_acceptance_next_stage_unlock_claim_scopes": ["transporter_domain_promotion"],
            "scope_acceptance_next_stage_required_checks": [
                "transporter_direct_binding_evidence_ready",
                "transporter_negative_quantitative_value_ready",
                "transporter_identity_scaffold_confirmed",
            ],
            "scope_acceptance_next_stage_next_action": (
                "Close the remaining AQP1 transporter review packet and rerun scope breadth gates."
            ),
            "scope_acceptance_stage_evidence_matrix_count": 5,
            "scope_acceptance_current_blocked_stage_evidence_matrix_count": 3,
            "next_required_step": (
                "Close the remaining AQP1 transporter review packet before widening scope."
            ),
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    )
    payload["summary"] = summary
    payload["rows"] = domain_rows
    payload["scope_acceptance_matrix"] = scope_acceptance_matrix
    payload["scope_acceptance_stage_evidence_matrix"] = scope_acceptance_matrix
    payload["scope_acceptance_current_blocked_stage_evidence_matrix"] = blocked_acceptance_matrix
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
        runs_dir / "product_public_benchmark_work_order_current.json",
        {
            "summary": {
                "status": "product_public_benchmark_work_order_clear",
                "source_public_benchmark_status": "product_public_benchmark_contract_ready",
                "public_benchmark_validation_ready": True,
                "suite_count": 5,
                "open_suite_count": 0,
                "materialization_required_suite_count": 0,
                "scorecard_required_suite_count": 0,
                "continuous_validation_command_count": 5,
                "suite_run_command_count": 5,
                "suite_materialization_run_command_count": 5,
                "suite_scorecard_command_count": 5,
                "suite_result_provenance_command_count": 5,
                "suite_result_provenance_present_count": 5,
                "suite_threshold_count": 5,
                "suite_blocker_count": 0,
                "suite_materialization_manifest_count": 5,
                "suite_scorecard_row_csv_count": 5,
                "suite_required_output_count": 5,
                "suite_no_external_dependency_count": 5,
                "local_artifact_preflight_ready_suite_count": 5,
                "local_artifact_preflight_blocked_suite_count": 0,
                "requires_24h_server": False,
                "requires_competition_season": False,
                "requires_paid_vps": False,
                "execution_enabled": False,
                "download_executed": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
                "claim_boundary": "CI fixture public benchmark work order only; it records pre-existing local fixture readiness and does not download data, run docking, compute metrics, or mutate external state.",
            },
            "rows": [],
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
    approval_csv = runs_dir / "product_execution_operator_approval_intake.csv"
    approval_template = runs_dir / "product_execution_operator_approval_template_current.csv"
    approval_header = (
        "target_id,family,bundle_tag,operator_decision,operator_approval_token,operator_note\n"
    )
    approval_csv.write_text(
        approval_header
        + "ADRB2,gpcr,product-developer-preview,approve,APPROVE_PRODUCT_DOCKING_EXECUTION,"
        "CI fixture authorizes only the separate operator execution path\n",
        encoding="utf-8",
    )
    approval_template.write_text(approval_header, encoding="utf-8")
    _write(
        runs_dir / "product_execution_approval_gate_current.json",
        {
            "summary": {
                "packet_type": "product_execution_operator_approval_gate",
                "status": "product_execution_operator_approval_gate_ready",
                "source_product_execution_preflight_status": "product_execution_preflight_ready",
                "source_product_execution_work_order_status": "product_execution_work_order_ready",
                "operator_approval_csv": "runs/product_execution_operator_approval_intake.csv",
                "operator_approval_csv_present": True,
                "operator_template_csv": "runs/product_execution_operator_approval_template_current.csv",
                "target_id": "ADRB2",
                "family": "gpcr",
                "bundle_tag": "product-developer-preview",
                "authorized_for_execution": True,
                "authorized_row_count": 1,
                "awaiting_operator_approval_row_count": 0,
                "skipped_row_count": 0,
                "blocked_row_count": 0,
                "unknown_operator_approval_row_count": 0,
                "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                "blocker_count": 0,
                "blockers": [],
                "execution_enabled": False,
                "docking_results_emitted": False,
                "bundle_assembled": False,
                "external_state_mutated": False,
            },
            "rows": [
                {
                    "target_id": "ADRB2",
                    "family": "gpcr",
                    "bundle_tag": "product-developer-preview",
                    "approval_gate_status": "authorized_for_operator_execution",
                    "operator_decision": "approve",
                    "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                    "operator_approval_token_present": True,
                    "execution_enabled": False,
                    "docking_results_emitted": False,
                    "bundle_assembled": False,
                    "external_state_mutated": False,
                }
            ],
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
            "production_output_head_required_field_count": 7,
            "production_output_head_ready_field_count": 7,
            "production_output_head_blocked_field_count": 0,
            "production_output_head_blocked_fields": [],
            "production_output_head_first_blocked_field": "",
            "production_output_head_first_blocked_field_blockers": [],
            "force_gpu_worker_return_receipt_ready": True,
            "force_gpu_worker_handoff_ready": True,
            "force_gpu_worker_handoff_required": True,
            "force_gpu_worker_operator_action_required": True,
            "force_gpu_worker_operator_transfer_manifest_ready": True,
            "force_gpu_worker_operator_transfer_outbound_artifact_count": 10,
            "force_gpu_worker_operator_transfer_outbound_artifacts": [
                "tools/generate_ligand_trajectory_engine.py",
                "tools/build_rocm_environment_manifest.py",
                "tools/build_residual_force_gpu_worker_return_receipt.py",
                "tools/build_residual_force_gpu_worker_handoff_package.py",
                "tools/build_product_production_ai_checkpoint_readiness.py",
                "runs/residual_force_gpu_worker_handoff_package_current.json",
                "runs/residual_force_trajectory_regeneration_current_manifest.csv",
                "runs/residual_force_trajectory_regeneration_current_summary_template.json",
                "runs/rocm_environment_manifest_current.json",
                "runs/residual_model_registry_current.json",
            ],
            "force_gpu_worker_operator_transfer_inbound_artifact_count": 5,
            "force_gpu_worker_operator_transfer_inbound_artifacts": [
                "runs/rocm_environment_manifest_current.json",
                "runs/residual_force_trajectory_regeneration_current_manifest.csv",
                "runs/residual_force_trajectory_regeneration_current_summary.json",
                "runs/residual_force_gpu_worker_return_receipt_current.json",
                "runs/residual_production_checkpoint_sidecar_current.json",
            ],
            "force_gpu_worker_operator_transfer_first_return_artifact": (
                "runs/rocm_environment_manifest_current.json"
            ),
            "force_gpu_worker_operator_transfer_return_manifest_artifact": (
                "runs/residual_force_trajectory_regeneration_current_manifest.csv"
            ),
            "force_gpu_worker_operator_transfer_acceptance_artifact": (
                "runs/residual_force_gpu_worker_return_receipt_current.json"
            ),
            "force_gpu_worker_operator_transfer_acceptance_ready_key": (
                "gpu_worker_return_receipt_ready"
            ),
            "force_gpu_worker_return_summary_template_payload_json": (
                "runs/residual_force_trajectory_regeneration_current_summary_template.json"
            ),
            "force_gpu_worker_full_regeneration_command": (
                "python3 tools/generate_ligand_trajectory_engine.py --manifest "
                "runs/residual_force_trajectory_regeneration_current_manifest.csv"
            ),
            "force_gpu_worker_post_return_validation_command": (
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
            ),
            "force_gpu_worker_post_return_output_contract_ready": True,
            "force_gpu_worker_post_return_required_production_output_fields": [
                "delta_score",
                "corrected_score",
                "delta_energy",
                "delta_force",
                "uncertainty",
                "abstention_reason",
                "stage2_route_decision",
            ],
            "force_gpu_worker_post_return_unlock_output_fields": [
                "delta_force",
                "uncertainty",
                "abstention_reason",
                "stage2_route_decision",
            ],
            "force_gpu_worker_post_return_gpu_unlock_artifacts": [
                "runs/residual_force_gpu_worker_return_receipt_current.json",
                "runs/residual_production_checkpoint_sidecar_current.json",
            ],
            "force_gpu_worker_post_return_min_expected_label_rows": 768,
            "force_gpu_worker_post_return_promotion_ladder_ready": True,
            "force_gpu_worker_post_return_promotion_ladder_contract_ready": True,
            "force_gpu_worker_post_return_promotion_ladder_stage_count": 10,
            "force_gpu_worker_post_return_promotion_ladder_stage_ids": [
                "gpu_return_receipt",
                "force_derivation_validation",
                "energy_force_label_evidence",
                "production_training_data_contract",
                "production_score_model",
                "production_checkpoint_sidecar",
                "production_checkpoint_preflight",
                "residual_model_registry",
                "product_ai_architecture_gap_closure",
                "product_goal_completion_audit",
            ],
            "force_gpu_worker_post_return_promotion_ladder": [
                {
                    "stage_id": "gpu_return_receipt",
                    "artifact": "runs/product_production_ai_gpu_return_intake_current.json",
                    "ready_key": "gpu_return_intake_ready",
                    "required_value": True,
                    "release_effect": "GPU return intake is available for promotion review.",
                },
                {
                    "stage_id": "force_derivation_validation",
                    "artifact": "runs/residual_force_derivation_validation_current.json",
                    "ready_key": "force_derivation_validation_ready",
                    "required_value": True,
                    "release_effect": "Residual force derivation validation is accepted.",
                },
                {
                    "stage_id": "energy_force_label_evidence",
                    "artifact": "runs/residual_force_derivation_validation_current.json",
                    "ready_key": "energy_force_label_evidence_ready",
                    "required_value": True,
                    "release_effect": "Energy/force label evidence is ready.",
                },
                {
                    "stage_id": "production_training_data_contract",
                    "artifact": "runs/residual_production_training_data_contract_current.json",
                    "ready_key": "training_data_contract_ready",
                    "required_value": True,
                    "release_effect": "Production training-data contract is ready.",
                },
                {
                    "stage_id": "production_score_model",
                    "artifact": "runs/residual_production_score_model_current.json",
                    "ready_key": "score_model_production_checkpoint_ready",
                    "required_value": True,
                    "release_effect": "Score model checkpoint evidence is ready.",
                },
                {
                    "stage_id": "production_checkpoint_sidecar",
                    "artifact": "runs/residual_production_checkpoint_sidecar_current.json",
                    "ready_key": "checkpoint_sidecar_ready",
                    "required_value": True,
                    "release_effect": "Production checkpoint sidecar is ready.",
                },
                {
                    "stage_id": "production_checkpoint_preflight",
                    "artifact": "runs/residual_production_checkpoint_preflight_current.json",
                    "ready_key": "checkpoint_preflight_ready",
                    "required_value": True,
                    "release_effect": "Production checkpoint preflight is green.",
                },
                {
                    "stage_id": "residual_model_registry",
                    "artifact": "runs/residual_model_registry_current.json",
                    "ready_key": "production_promotion_allowed",
                    "required_value": True,
                    "release_effect": "Residual model registry allows guarded promotion.",
                },
                {
                    "stage_id": "product_ai_architecture_gap_closure",
                    "artifact": "runs/product_ai_architecture_gap_closure_current.json",
                    "ready_key": "product_ai_architecture_gap_closure_ready",
                    "required_value": True,
                    "release_effect": "Product AI architecture gap closure is complete.",
                },
                {
                    "stage_id": "product_goal_completion_audit",
                    "artifact": "runs/product_goal_completion_audit_current.json",
                    "ready_key": "goal_complete",
                    "required_value": True,
                    "release_effect": "Product goal completion audit is green.",
                },
            ],
            "force_gpu_worker_post_return_promotion_ladder_ready_keys": [
                "gpu_return_intake_ready",
                "force_derivation_validation_ready",
                "energy_force_label_evidence_ready",
                "training_data_contract_ready",
                "score_model_production_checkpoint_ready",
                "checkpoint_sidecar_ready",
                "checkpoint_preflight_ready",
                "production_promotion_allowed",
                "product_ai_architecture_gap_closure_ready",
                "goal_complete",
            ],
            "force_gpu_worker_post_return_promotion_ladder_missing_stages": [],
            "force_gpu_worker_post_return_promotion_ladder_missing_ready_keys": [],
            "production_gpu_execution_environment_ready": True,
            "production_gpu_execution_environment_artifact_path": (
                "runs/rocm_environment_manifest_current.json"
            ),
            "production_gpu_execution_environment_status": (
                "rocm_environment_manifest_ready"
            ),
            "production_gpu_rocm_manifest_ready": True,
            "production_gpu_rocm_stack_detected": True,
            "production_gpu_rocm_torch_ready": True,
            "production_gpu_rocm_amd_gpu_detected": True,
            "production_gpu_rocm_visible_device_count": 1,
            "production_gpu_rocm_device_names": ["AMD Radeon RX 6900 XT"],
            "production_gpu_rocm_torch_version": "2.4.0+rocm6.1",
            "production_gpu_rocm_torch_hip_version": "6.1.0",
            "production_gpu_rocm_visibility_diagnostic_packet_ready": True,
            "production_gpu_rocm_visibility_diagnostic_command_count": 5,
            "production_gpu_rocm_visibility_diagnostic_commands": [
                "rocminfo",
                "python3 tools/build_rocm_environment_manifest.py",
                "python3 scripts/run_gpu_newton_terminal_certification.py",
                "python3 tools/build_product_production_ai_checkpoint_readiness.py",
                "python3 tools/build_product_production_ai_promotion_workbench.py",
            ],
            "production_gpu_rocm_visibility_diagnostic_required_field_count": 4,
            "production_gpu_rocm_visibility_diagnostic_required_fields": [
                "rocm_stack_detected",
                "torch_ready",
                "amd_gpu_detected",
                "visible_device_count",
            ],
            "production_gpu_rocm_visibility_diagnostic_completion_rule": (
                "visible_device_count>0 and torch_ready=true"
            ),
            "production_gpu_rocm_visibility_diagnostic_return_artifacts": [
                "runs/rocm_environment_manifest_current.json",
                "runs/rocm_workstation_gpu_receipt_current.json",
            ],
            "production_gpu_rocm_visibility_torch_probe_command": (
                "python3 -c 'import torch; print(torch.version.hip)'"
            ),
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
            "production_inference_worker_runtime_receipt_completion_rule": "",
            "production_inference_worker_runtime_receipt_post_environment_next_stage_id": "",
            "production_inference_worker_runtime_receipt_post_environment_next_artifact": "",
            "production_inference_worker_runtime_receipt_post_environment_validation_command": "",
            "production_inference_worker_runtime_receipt_full_regeneration_command": (
                "python3 tools/generate_ligand_trajectory_engine.py --manifest "
                "runs/residual_force_trajectory_regeneration_current_manifest.csv"
            ),
            "production_inference_worker_runtime_receipt_guardrails": [],
            "force_gpu_worker_post_run_validation_chain_current": True,
            "force_gpu_worker_post_run_validation_command_count": 18,
            "force_gpu_worker_post_run_validation_commands": [
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                "python3 tools/build_rocm_environment_manifest.py",
                "python3 tools/build_residual_production_checkpoint_sidecar.py",
                "python3 tools/build_product_production_ai_checkpoint_readiness.py",
                "python3 tools/build_product_production_ai_promotion_workbench.py",
                "python3 tools/build_production_ai_registry_promotion_operator_receipt.py",
                "python3 tools/product/build_production_ai_registry_promotion_priority_packet.py",
                "python3 tools/build_goal_readiness_rollup.py",
                "python3 tools/build_goal_release_decision_gate.py",
                "python3 tools/build_goal_release_burndown_work_order.py",
                "python3 tools/build_goal_operator_action_board.py",
                "python3 tools/build_goal_operator_intake_kit.py",
                "python3 tools/build_goal_bottleneck_briefing.py",
                "python3 tools/build_goal_api_surface_contract.py",
                "python3 tools/build_product_goal_completion_audit.py",
                "python3 tools/product/build_product_full_commercial_blocker_evidence_matrix.py",
                "python3 tools/build_residual_model_registry.py",
                "python3 tools/product/build_product_launch_r4_preflight.py",
            ],
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
    _write(
        runs_dir / "residual_force_derivation_validation_current.json",
        {
            "summary": {
                "status": "residual_force_derivation_validation_ready",
                "force_derivation_validation_ready": True,
                "energy_force_label_evidence_ready": True,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "residual_production_score_model_current.json",
        {
            "summary": {
                "status": "residual_production_score_model_ready",
                "production_checkpoint_ready": True,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "residual_production_checkpoint_sidecar_current.json",
        {
            "summary": {
                "status": "residual_production_checkpoint_sidecar_ready",
                "checkpoint_sidecar_ready": True,
                "selected_sidecar_ready": True,
                "missing_output_fields": [],
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        },
    )

    queue_csv = "runs/residual_force_trajectory_regeneration_queue_current.csv"
    manifest_csv = "runs/residual_force_trajectory_regeneration_current_manifest.csv"
    handoff_package = "runs/residual_force_gpu_worker_handoff_package_current.json"
    full_regeneration_command = (
        "python3 tools/generate_ligand_trajectory_engine.py --manifest "
        "runs/residual_force_trajectory_regeneration_current_manifest.csv"
    )
    tiny_pilot_command = (
        "python3 tools/generate_ligand_trajectory_engine.py --manifest "
        "runs/residual_force_trajectory_regeneration_current_manifest.csv --limit 1"
    )
    post_return_validation_command = (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    acceptance_contract = {
        "return_receipt_ready_key": "gpu_worker_return_receipt_ready",
        "return_manifest_artifact": manifest_csv,
        "return_receipt_artifact": "runs/residual_force_gpu_worker_return_receipt_current.json",
    }
    outbound_artifacts = [
        "tools/generate_ligand_trajectory_engine.py",
        "tools/build_rocm_environment_manifest.py",
        "tools/build_residual_force_gpu_worker_return_receipt.py",
        "tools/build_residual_force_gpu_worker_handoff_package.py",
        "tools/build_product_production_ai_checkpoint_readiness.py",
        handoff_package,
        manifest_csv,
        "runs/residual_force_trajectory_regeneration_current_summary_template.json",
        "runs/rocm_environment_manifest_current.json",
        "runs/residual_model_registry_current.json",
    ]
    inbound_artifacts = [
        "runs/rocm_environment_manifest_current.json",
        manifest_csv,
        "runs/residual_force_trajectory_regeneration_current_summary.json",
        "runs/residual_force_gpu_worker_return_receipt_current.json",
        "runs/residual_production_checkpoint_sidecar_current.json",
    ]
    dispatch_rows = [
        {
            "artifact_id": f"dispatch_artifact_{index:02d}",
            "artifact_path": artifact_path,
            "local_file_reference": True,
            "present": True,
        }
        for index, artifact_path in enumerate(outbound_artifacts, start=1)
    ]
    shared_gpu_worker_summary = {
        "dispatch_manifest_ready": True,
        "handoff_package_ready": True,
        "handoff_package_artifact": handoff_package,
        "queue_rows": 768,
        "queue_csv": queue_csv,
        "queue_csv_sha256": "a" * 64,
        "outbound_artifact_count": len(outbound_artifacts),
        "inbound_artifact_count": len(inbound_artifacts),
        "local_artifact_reference_count": len(outbound_artifacts),
        "local_artifact_present_count": len(outbound_artifacts),
        "local_artifact_missing_count": 0,
        "local_artifact_missing": [],
        "native_pdb_dependency_count": 3,
        "native_pdb_missing_count": 0,
        "native_pdb_missing": [],
        "tiny_pilot_command": tiny_pilot_command,
        "full_regeneration_command": full_regeneration_command,
        "post_run_validation_commands": [
            post_return_validation_command,
            "python3 tools/build_rocm_environment_manifest.py",
            "python3 tools/build_product_production_ai_checkpoint_readiness.py",
        ],
        "post_run_validation_command_count": 3,
        "acceptance_contract": acceptance_contract,
        "return_summary_completion_rule": (
            "Return summary must bind regenerated trajectory NPZ files to manifest rows."
        ),
        "return_manifest_required_identity_rule": (
            "Each return row must preserve queue_row_fingerprint and queue_id."
        ),
        "worker_rocm_manifest_completion_rule": "visible_device_count>0 and torch_ready=true",
        "next_required_step": (
            "Transfer the dispatch bundle to the GPU worker and return the required receipt artifacts."
        ),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": (
            "Restricted clean-checkout fixture for API contract verification only; it does not run GPU jobs, "
            "regenerate trajectories, train models, promote checkpoints, or mutate external state."
        ),
    }
    _write(
        runs_dir / "residual_force_gpu_worker_dispatch_manifest_current.json",
        {
            "summary": {
                **shared_gpu_worker_summary,
                "status": "residual_force_gpu_worker_dispatch_manifest_ready",
            },
            "rows": dispatch_rows,
            "blockers": [],
        },
    )
    bundle_summary = {
        **shared_gpu_worker_summary,
        "status": "residual_force_gpu_worker_dispatch_bundle_ready",
        "dispatch_bundle_ready": True,
        "dispatch_manifest_ready": True,
        "dispatch_manifest_artifact": (
            "runs/residual_force_gpu_worker_dispatch_manifest_current.json"
        ),
        "bundle_tar_path": "runs/residual_force_gpu_worker_dispatch_bundle_current.tar.gz",
        "bundle_tar_exists": True,
        "bundle_tar_size_bytes": 4096,
        "bundle_tar_sha256": "b" * 64,
        "bundle_member_count": len(outbound_artifacts),
        "source_artifact_count": len(outbound_artifacts),
    }
    _write(
        runs_dir / "residual_force_gpu_worker_dispatch_bundle_current.json",
        {
            "summary": bundle_summary,
            "rows": dispatch_rows,
            "blockers": [],
        },
    )
    worker_script_path = runs_dir / "residual_force_gpu_worker_execution_runbook_current.sh"
    worker_script_path.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "python3 tools/generate_ligand_trajectory_engine.py --manifest "
        "runs/residual_force_trajectory_regeneration_current_manifest.csv\n",
        encoding="utf-8",
    )
    worker_script_path.chmod(0o755)
    packager_script_path = runs_dir / "residual_force_gpu_worker_return_bundle_packager_current.sh"
    packager_script_path.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py\n",
        encoding="utf-8",
    )
    packager_script_path.chmod(0o755)
    _write(
        runs_dir / "residual_force_gpu_worker_execution_runbook_current.json",
        {
            "summary": {
                **bundle_summary,
                "status": "residual_force_gpu_worker_execution_runbook_ready",
                "execution_runbook_ready": True,
                "dispatch_bundle_ready": True,
                "dispatch_bundle_artifact": (
                    "runs/residual_force_gpu_worker_dispatch_bundle_current.json"
                ),
                "worker_script_path": (
                    "runs/residual_force_gpu_worker_execution_runbook_current.sh"
                ),
                "worker_script_exists": True,
                "worker_script_executable": True,
                "return_packager_script_path": (
                    "runs/residual_force_gpu_worker_return_bundle_packager_current.sh"
                ),
                "return_packager_script_exists": True,
                "return_packager_script_executable": True,
                "return_bundle_tar_path": (
                    "runs/residual_force_gpu_worker_return_bundle_current.tar.gz"
                ),
                "return_bundle_sha256_path": (
                    "runs/residual_force_gpu_worker_return_bundle_current.tar.gz.sha256"
                ),
                "manifest_npz_path_columns": [
                    "expected_regenerated_trajectory_npz",
                    "observed_regenerated_trajectory_npz",
                ],
                "required_return_core_files": [
                    "runs/residual_force_trajectory_regeneration_current_summary.json",
                    manifest_csv,
                    "runs/residual_force_gpu_worker_return_receipt_current.json",
                ],
                "return_packager_command": (
                    "bash runs/residual_force_gpu_worker_return_bundle_packager_current.sh"
                ),
                "step_count": 8,
                "worker_executable_step_count": 6,
                "local_post_return_step_count": 2,
                "rocm_diagnostic_command_count": 2,
                "required_return_artifact_count": len(inbound_artifacts),
                "required_return_artifacts": inbound_artifacts,
                "post_return_validation_command": post_return_validation_command,
            },
            "rows": dispatch_rows,
            "blockers": [],
        },
    )

    return_required_artifacts = [
        "runs/residual_force_trajectory_regeneration_current_summary.json",
        manifest_csv,
        "regenerated NPZ bundles referenced by the returned manifest",
        "runs/residual_force_derivation_validation_current.json",
        "runs/rocm_environment_manifest_current.json",
    ]
    return_failed_check_ids = [
        "actual_manifest_npz_files_exist",
        "actual_manifest_npz_files_valid",
        "actual_manifest_npz_schema_valid",
        "actual_manifest_npz_identity_valid",
        "post_run_force_derivation_validation",
    ]
    return_passed_check_ids = [
        "gpu_handoff_ready",
        "manifest_template_ready",
        "summary_template_ready",
        "actual_summary_returned_complete",
        "actual_summary_manifest_bound",
        "actual_summary_out_manifest_csv_present",
        "actual_summary_out_manifest_csv_bound",
        "actual_summary_out_summary_json_bound",
        "actual_summary_manifest_row_counts_consistent",
        "production_gpu_backend_provenance",
        "worker_rocm_environment_manifest_ready",
        "actual_manifest_returned_complete",
        "actual_manifest_npz_paths_complete",
        "actual_manifest_operator_verified",
        "queue_manifest_identity_coverage",
    ]
    return_checks = [
        {
            "check_id": check_id,
            "status": "pass",
            "release_blocker": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        }
        for check_id in return_passed_check_ids
    ] + [
        {
            "check_id": check_id,
            "status": "fail",
            "release_blocker": True,
            "execution_enabled": False,
            "external_state_mutated": False,
        }
        for check_id in return_failed_check_ids
    ]
    return_blockers = [
        {
            "code": check_id,
            "check_id": check_id,
            "status": "fail",
            "release_blocker": True,
            "execution_enabled": False,
            "external_state_mutated": False,
        }
        for check_id in return_failed_check_ids
    ]
    operator_acceptance_matrix = [
        {
            "stage_id": "gpu_return_templates_preflight",
            "status": "ready",
            "failed_check_ids": [],
        },
        {
            "stage_id": "returned_summary_acceptance",
            "status": "ready",
            "failed_check_ids": [],
        },
        {
            "stage_id": "returned_manifest_npz_acceptance",
            "status": "blocked",
            "failed_check_ids": return_failed_check_ids[:-1],
        },
        {
            "stage_id": "force_derivation_acceptance",
            "status": "blocked",
            "failed_check_ids": ["post_run_force_derivation_validation"],
        },
        {
            "stage_id": "post_return_promotion_chain",
            "status": "blocked",
            "failed_check_ids": ["post_run_force_derivation_validation"],
        },
    ]
    operator_return_artifact_completion_matrix = [
        {
            "artifact_id": "returned_summary_json",
            "artifact_path": "runs/residual_force_trajectory_regeneration_current_summary.json",
            "status": "ready",
            "failed_check_ids": [],
        },
        {
            "artifact_id": "returned_manifest_csv",
            "artifact_path": manifest_csv,
            "status": "ready",
            "failed_check_ids": [],
        },
        {
            "artifact_id": "regenerated_npz_bundles",
            "artifact_path": "regenerated NPZ bundles referenced by the returned manifest",
            "status": "blocked",
            "failed_check_ids": return_failed_check_ids[:-1],
        },
        {
            "artifact_id": "post_run_force_derivation_validation",
            "artifact_path": "runs/residual_force_derivation_validation_current.json",
            "status": "blocked",
            "failed_check_ids": ["post_run_force_derivation_validation"],
        },
        {
            "artifact_id": "worker_rocm_environment_manifest",
            "artifact_path": "runs/rocm_environment_manifest_current.json",
            "status": "ready",
            "failed_check_ids": [],
        },
    ]
    return_summary_template_payload = {
        "queue_rows": 768,
        "processed_rows": 768,
        "ok_rows": 768,
        "failed_rows": 0,
        "aborted_early": False,
        "out_manifest_csv": manifest_csv,
        "out_summary_json": "runs/residual_force_trajectory_regeneration_current_summary.json",
        "prod_mode": True,
        "require_rust_hip": True,
        "backend_counts": {"rust_hip": 768},
    }
    return_post_run_validation_commands = [
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
        "python3 tools/build_rocm_environment_manifest.py",
        "python3 tools/build_residual_production_checkpoint_sidecar.py",
        "python3 tools/build_product_production_ai_checkpoint_readiness.py",
        "python3 tools/build_product_production_ai_promotion_workbench.py",
        "python3 tools/build_production_ai_registry_promotion_operator_receipt.py",
        "python3 tools/product/build_production_ai_registry_promotion_priority_packet.py",
        "python3 tools/build_goal_readiness_rollup.py",
        "python3 tools/build_goal_release_decision_gate.py",
        "python3 tools/build_goal_release_burndown_work_order.py",
        "python3 tools/build_goal_operator_action_board.py",
        "python3 tools/build_goal_operator_intake_kit.py",
        "python3 tools/build_goal_bottleneck_briefing.py",
        "python3 tools/build_goal_api_surface_contract.py",
        "python3 tools/build_product_goal_completion_audit.py",
        "python3 tools/product/build_product_full_commercial_blocker_evidence_matrix.py",
        "python3 tools/build_residual_model_registry.py",
        "python3 tools/product/build_product_launch_r4_preflight.py",
    ]
    _write(
        runs_dir / "product_production_ai_gpu_return_intake_current.json",
        {
            "summary": {
                "status": "blocked_product_production_ai_gpu_return_intake",
                "gpu_return_intake_ready": True,
                "gpu_return_artifacts_ready": False,
                "check_count": 20,
                "pass_check_count": 15,
                "fail_check_count": 5,
                "failed_check_ids": return_failed_check_ids,
                "operator_return_blocker_count": 5,
                "first_failed_check_id": "actual_manifest_npz_files_exist",
                "first_failed_source_artifact": (
                    "runs/residual_force_gpu_worker_return_receipt_current.json"
                ),
                "first_failed_required": (
                    "actual returned manifest NPZ paths resolve to local files for every ok and "
                    "operator-verified row"
                ),
                "first_failed_observed": (
                    "npz_file_existing_count=0;npz_file_missing_count=768"
                ),
                "first_failed_next_action": (
                    "Restore or return the regenerated NPZ files at the manifest paths before accepting "
                    "the GPU return."
                ),
                "expected_queue_rows": 768,
                "operator_return_bundle_contract_ready": True,
                "operator_return_required_artifacts": return_required_artifacts,
                "operator_return_required_artifact_count": len(return_required_artifacts),
                "operator_return_artifact_completion_matrix_count": 5,
                "operator_return_artifact_completion_blocker_count": 2,
                "operator_return_next_artifact_completion_packet_ready": True,
                "operator_return_next_artifact_completion_packet": {
                    "artifact_id": "regenerated_npz_bundles",
                    "artifact_path": (
                        "regenerated NPZ bundles referenced by the returned manifest"
                    ),
                    "packet_ready": True,
                    "template_payload": return_summary_template_payload,
                    "failed_check_ids": return_failed_check_ids[:-1],
                    "execution_enabled": False,
                    "external_state_mutated": False,
                },
                "operator_return_next_artifact_id": "regenerated_npz_bundles",
                "operator_return_next_artifact_path": (
                    "regenerated NPZ bundles referenced by the returned manifest"
                ),
                "operator_return_next_artifact_failed_check_ids": return_failed_check_ids[:-1],
                "operator_return_manifest_required_columns": [
                    "queue_id",
                    "expected_regenerated_trajectory_npz",
                    "status",
                    "operator_verified_npz_exists",
                ],
                "operator_return_manifest_required_column_count": 4,
                "operator_return_validation_ladder_ready": True,
                "operator_return_handoff_binding_ready": True,
                "operator_return_handoff_queue_csv": queue_csv,
                "operator_return_handoff_queue_csv_sha256": "a" * 64,
                "operator_return_handoff_full_regeneration_command": full_regeneration_command,
                "operator_return_handoff_return_manifest_schema_contract_ready": True,
                "operator_return_handoff_return_manifest_required_identity_rule": (
                    "Returned manifest rows must preserve queue_id and queue_row_fingerprint."
                ),
                "operator_return_handoff_return_manifest_fingerprint_columns": [
                    "queue_row_fingerprint"
                ],
                "operator_return_handoff_return_manifest_queue_id_columns": ["queue_id"],
                "operator_return_handoff_return_manifest_npz_columns": [
                    "expected_regenerated_trajectory_npz"
                ],
                "operator_acceptance_matrix_ready": True,
                "operator_acceptance_stage_count": 5,
                "operator_acceptance_ready_stage_count": 2,
                "operator_acceptance_blocked_stage_count": 3,
                "operator_acceptance_stage_ids": [
                    row["stage_id"] for row in operator_acceptance_matrix
                ],
                "operator_acceptance_ready_stage_ids": [
                    "gpu_return_templates_preflight",
                    "returned_summary_acceptance",
                ],
                "operator_acceptance_blocked_stage_ids": [
                    "returned_manifest_npz_acceptance",
                    "force_derivation_acceptance",
                    "post_return_promotion_chain",
                ],
                "operator_acceptance_next_stage_id": "returned_manifest_npz_acceptance",
                "operator_acceptance_next_stage_artifact": (
                    "runs/residual_force_trajectory_regeneration_current_manifest.csv;regenerated NPZ "
                    "bundles referenced by manifest"
                ),
                "operator_acceptance_next_stage_validation_command": (
                    "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                ),
                "operator_acceptance_next_stage_release_effect": (
                    "returned manifest, NPZ bundle existence, schema, identity, and operator "
                    "verification are accepted"
                ),
                "operator_acceptance_next_stage_unlock_fields": [],
                "operator_acceptance_next_stage_required_checks": [
                    "actual_manifest_returned_complete",
                    "actual_manifest_npz_paths_complete",
                    "actual_manifest_npz_files_exist",
                    "actual_manifest_npz_files_valid",
                    "actual_manifest_npz_schema_valid",
                    "actual_manifest_npz_identity_valid",
                    "actual_manifest_operator_verified",
                    "queue_manifest_identity_coverage",
                ],
                "operator_acceptance_next_stage_next_action": (
                    "Return regenerated NPZ bundles and rerun the GPU return receipt builder."
                ),
                "operator_acceptance_stage_check_matrix": operator_acceptance_matrix,
                "operator_acceptance_stage_check_matrix_count": 5,
                "operator_acceptance_current_blocked_stage_check_matrix": (
                    operator_acceptance_matrix[2:]
                ),
                "operator_acceptance_current_blocked_stage_check_matrix_count": 3,
                "handoff_ready": True,
                "operator_action_required": True,
                "manifest_template_ready": True,
                "manifest_template_csv": (
                    "runs/residual_force_gpu_worker_return_manifest_template_current.csv"
                ),
                "manifest_template_row_count": 768,
                "manifest_status_placeholder_count": 768,
                "manifest_operator_verification_placeholder_count": 768,
                "summary_template_ready": True,
                "summary_template_csv": (
                    "runs/residual_force_gpu_worker_return_summary_template_current.csv"
                ),
                "summary_template_payload_json": (
                    "runs/residual_force_trajectory_regeneration_current_summary_template.json"
                ),
                "summary_template_payload": return_summary_template_payload,
                "summary_template_field_count": 10,
                "summary_template_required_fields": [
                    "queue_rows",
                    "processed_rows",
                    "ok_rows",
                    "failed_rows",
                    "aborted_early",
                    "out_manifest_csv",
                    "out_summary_json",
                    "prod_mode",
                    "require_rust_hip",
                    "backend_counts",
                ],
                "summary_template_completion_rule": (
                    "processed_rows>=expected_queue_rows and ok_rows==expected_queue_rows"
                ),
                "summary_template_backend_provenance_contract_ready": True,
                "summary_template_required_backend_provenance_fields": [
                    "prod_mode",
                    "require_rust_hip",
                    "backend_counts",
                ],
                "summary_template_backend_provenance_completion_rule": (
                    "backend_counts has rust_hip* rows and no CPU fallback rows"
                ),
                "actual_summary_return_path": (
                    "runs/residual_force_trajectory_regeneration_current_summary.json"
                ),
                "actual_manifest_return_path": manifest_csv,
                "receipt_status": "blocked_residual_force_gpu_worker_return_receipt",
                "receipt_blockers": return_failed_check_ids,
                "summary_returned": True,
                "summary_complete": True,
                "summary_manifest_bound": True,
                "summary_manifest_csv": manifest_csv,
                "summary_out_manifest_csv_present": True,
                "summary_out_manifest_csv": manifest_csv,
                "summary_out_manifest_csv_bound": True,
                "summary_out_summary_json_bound": True,
                "summary_out_summary_json": (
                    "runs/residual_force_trajectory_regeneration_current_summary.json"
                ),
                "summary_manifest_row_counts_consistent": True,
                "production_gpu_backend_provenance_ready": True,
                "production_gpu_backend_rows": 768,
                "production_gpu_backend_non_production_rows": 0,
                "production_gpu_backend_prod_mode": True,
                "production_gpu_backend_require_rust_hip": True,
                "worker_rocm_manifest_artifact": "runs/rocm_environment_manifest_current.json",
                "worker_rocm_manifest_ready": True,
                "worker_rocm_manifest_generation_command": (
                    "python3 tools/build_rocm_environment_manifest.py"
                ),
                "worker_rocm_manifest_completion_rule": (
                    "manifest_ready=true;rocm_stack_detected=true;torch_rocm_ready=true;"
                    "amd_gpu_detected=true;visible_device_count>0"
                ),
                "worker_rocm_stack_detected": True,
                "worker_rocm_torch_ready": True,
                "worker_rocm_amd_gpu_detected": True,
                "worker_rocm_visible_device_count": 1,
                "worker_rocm_device_names": ["AMD Radeon RX 6900 XT"],
                "worker_rocm_next_required_step": "",
                "manifest_returned": True,
                "manifest_complete": True,
                "manifest_npz_paths_complete": True,
                "manifest_npz_files_exist": False,
                "manifest_npz_files_valid": False,
                "manifest_npz_schema_valid": False,
                "manifest_npz_identity_valid": False,
                "manifest_npz_path_column_present": True,
                "manifest_npz_path_present_count": 768,
                "manifest_npz_path_missing_count": 0,
                "manifest_ok_row_missing_npz_path_count": 0,
                "manifest_operator_verified_missing_npz_path_count": 0,
                "manifest_npz_file_existing_count": 0,
                "manifest_npz_file_missing_count": 768,
                "manifest_ok_row_missing_npz_file_count": 768,
                "manifest_operator_verified_missing_npz_file_count": 768,
                "manifest_npz_file_valid_count": 0,
                "manifest_npz_file_invalid_count": 0,
                "manifest_ok_row_invalid_npz_file_count": 0,
                "manifest_operator_verified_invalid_npz_file_count": 0,
                "manifest_npz_schema_valid_count": 0,
                "manifest_npz_schema_invalid_count": 0,
                "manifest_ok_row_invalid_npz_schema_count": 0,
                "manifest_operator_verified_invalid_npz_schema_count": 0,
                "manifest_npz_identity_valid_count": 0,
                "manifest_npz_identity_invalid_count": 768,
                "manifest_ok_row_invalid_npz_identity_count": 768,
                "manifest_operator_verified_invalid_npz_identity_count": 768,
                "manifest_operator_verified": True,
                "identity_coverage_ready": True,
                "post_run_derivation_validation_ready": False,
                "post_return_validation_command": (
                    "python3 tools/build_residual_force_gpu_worker_return_receipt.py && "
                    "python3 tools/build_residual_model_registry.py"
                ),
                "post_run_validation_command_count": 18,
                "post_run_validation_commands": return_post_run_validation_commands,
                "next_required_step": (
                    "Return regenerated NPZ bundles and rerun the GPU return receipt builder."
                ),
                "execution_enabled": False,
                "docking_results_emitted": False,
                "full_regeneration_executed": False,
                "force_labels_created": False,
                "training_executed": False,
                "checkpoint_created": False,
                "model_promoted": False,
                "external_state_mutated": False,
                "claim_boundary": (
                    "Production AI GPU-return intake fixture only; it surfaces operator return gaps "
                    "without running GPU jobs, creating force labels, training, promoting checkpoints, "
                    "or mutating external state."
                ),
            },
            "rows": return_checks,
            "blockers": return_blockers,
            "operator_acceptance_matrix": operator_acceptance_matrix,
            "operator_return_artifact_completion_matrix": operator_return_artifact_completion_matrix,
            "operator_return_artifact_completion_blocker_matrix": (
                operator_return_artifact_completion_matrix[2:4]
            ),
        },
    )


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
            "production_ai_registry_promotion_priority_top_gate_id": (
                "default_residual_mode_guarded"
            ),
            "production_ai_registry_promotion_priority_top_priority_bucket": (
                "guarded_residual_mode_selection_required"
            ),
            "production_ai_registry_promotion_priority_missing_gate_count": 3,
            "production_ai_registry_promotion_priority_missing_gate_ids": [
                "default_residual_mode_guarded",
                "production_promotion_allowed",
                "customer_facing_mutation_flags",
            ],
        }
    )
    manifest = summary.get("artifact_reference_manifest")
    if isinstance(manifest, list):
        existing_ids = {
            str(row.get("artifact_id"))
            for row in manifest
            if isinstance(row, dict)
        }
        additional_references = [
            (
                "product_production_ai_gpu_return_intake",
                "runs/product_production_ai_gpu_return_intake_current.json",
                "Local GPU-return intake packet that binds operator return gaps to the commercial-readiness handoff.",
                "local_gpu_return_intake",
            ),
            (
                "residual_force_gpu_worker_dispatch_manifest",
                "runs/residual_force_gpu_worker_dispatch_manifest_current.json",
                "Local dispatch manifest for the GPU worker handoff bundle.",
                "local_gpu_worker_dispatch_manifest",
            ),
            (
                "residual_force_gpu_worker_dispatch_bundle",
                "runs/residual_force_gpu_worker_dispatch_bundle_current.json",
                "Local dispatch bundle summary for the GPU worker handoff package.",
                "local_gpu_worker_dispatch_bundle",
            ),
        ]
        for artifact_id, artifact_path, note, reference_role in additional_references:
            if artifact_id in existing_ids:
                continue
            artifact_file = runs_dir / artifact_path.removeprefix("runs/")
            artifact_exists = artifact_file.is_file()
            manifest.append(
                {
                    "artifact_id": artifact_id,
                    "artifact_path": artifact_path,
                    "reference_role": reference_role,
                    "note": note,
                    "local_file_reference": True,
                    "required_now": True,
                    "exists_now": artifact_exists,
                    "missing_now": not artifact_exists,
                    "release_blocker_if_missing_now": True,
                    "expected_from_operator_return": False,
                    "execution_enabled": False,
                    "external_state_mutated": False,
                }
            )
            existing_ids.add(artifact_id)
        summary["artifact_reference_manifest"] = manifest
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


def write_restricted_engine_refinement_claim_evidence_priority_packet(runs_dir: Path) -> None:
    path = runs_dir / "engine_refinement_claim_evidence_priority_packet_current.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    required_blockers = [
        "public_benchmark_gate_not_ready",
        "parameter_calibration_claim_not_ready",
        "metal_cofactor_parameterization_not_ready",
        "charged_residue_protonation_and_charge_calibration_not_ready",
        "solvent_fep_public_pair_calibration_not_ready",
        "external_structure_quality_parity_not_ready",
    ]
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    summary.update(
        {
            "packet_type": "engine_refinement_claim_evidence_priority_packet",
            "status": "blocked_engine_refinement_claim_evidence_priority_packet",
            "priority_packet_ready": True,
            "claim_promotion_allowed": False,
            "claim_evidence_receipt_ready": False,
            "claim_evidence_receipt_status": "blocked_engine_refinement_claim_evidence_receipt",
            "priority_item_count": 6,
            "operator_input_required_count": 6,
            "blocked_priority_item_count": 6,
            "required_blocker_count": 6,
            "missing_required_blocker_count": 0,
            "missing_required_blockers": [],
            "public_benchmark_gate_ready": False,
            "public_benchmark_status": "blocked_refine_tier_public_benchmark_readiness",
            "public_benchmark_work_order_present": True,
            "public_benchmark_work_order_row_count": 8,
            "public_benchmark_work_order_apply_status": (
                "blocked_refine_tier_public_benchmark_work_order_apply"
            ),
            "public_benchmark_work_order_apply_ready": False,
            "public_benchmark_work_order_apply_blocked_row_count": 8,
            "top_blocker_id": "public_benchmark_gate_not_ready",
            "top_priority_bucket": "public_benchmark_work_order_apply_required",
            "top_required_input": (
                "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
            ),
            "top_acceptance_artifact": "runs/refine_tier_public_benchmark_readiness_current.json",
            "top_verification_command": (
                "python3 tools/build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt.py; "
                "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py; "
                "python3 tools/product/build_refine_tier_public_benchmark_readiness.py; "
                "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py"
            ),
            "top_next_operator_step": (
                "Fill and validate the public benchmark statistical-support metric-source payload operator receipt, "
                "then rerun the public benchmark readiness and R9 evidence receipt gates."
            ),
            "approval_token_required": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
            "approval_token_count": 1,
            "blocker_count": 1,
            "blockers": ["operator_evidence_rows_pending"],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_promoted": False,
        }
    )
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    if len(rows) < len(required_blockers):
        rows = [
            {
                "priority": index,
                "blocker_id": blocker_id,
                "priority_bucket": (
                    "public_benchmark_work_order_apply_required"
                    if index == 1
                    else "operator_evidence_receipt_required"
                ),
                "operator_input_required": True,
                "claim_promotion_allowed": False,
                "external_state_mutated": False,
            }
            for index, blocker_id in enumerate(required_blockers, start=1)
        ]
    for index, row in enumerate(rows[: len(required_blockers)], start=1):
        row["priority"] = index
        row["blocker_id"] = required_blockers[index - 1]
        row["operator_input_required"] = True
        row["claim_promotion_allowed"] = False
        row["external_state_mutated"] = False
        if index == 1:
            row.update(
                {
                    "priority_bucket": "public_benchmark_work_order_apply_required",
                    "acceptance_artifact": (
                        "runs/refine_tier_public_benchmark_readiness_current.json"
                    ),
                    "current_status": "blocked_refine_tier_public_benchmark_readiness",
                    "owner_action": (
                        "Fill the public benchmark statistical-support metric-source payload operator receipt."
                    ),
                    "next_operator_step": summary["top_next_operator_step"],
                }
            )
    payload["summary"] = summary
    payload["rows"] = rows[: len(required_blockers)]
    _write(path, payload)


def write_commercial_readiness_operator_surface_fixture_packets(runs_dir: Path) -> None:
    _write(
        runs_dir / "residual_delta_force_closure_acceptance_packet_current.json",
        {
            "summary": {
                "packet_type": "residual_delta_force_closure_acceptance_packet",
                "status": "blocked_residual_delta_force_closure_acceptance_packet",
                "packet_ready": True,
                "delta_force_closure_ready": False,
                "first_blocked_output_field": "delta_force",
                "ready_output_field_count": 6,
                "blocked_output_field_count": 1,
                "closure_failed_stage_count": 9,
                "closure_failed_stage_ids": [
                    "gpu_worker_return_receipt",
                    "force_derivation_validation",
                    "energy_force_label_evidence",
                    "production_training_data_contract",
                    "production_score_model",
                    "production_checkpoint_sidecar",
                    "production_checkpoint_preflight",
                    "residual_model_registry",
                    "product_goal_completion_audit",
                ],
                "next_stage_id": "gpu_worker_return_receipt",
                "next_stage_artifact": "runs/product_production_ai_gpu_return_intake_current.json",
                "next_stage_validation_command": (
                    "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                ),
                "operator_return_required_artifact_count": 5,
                "operator_return_required_artifacts": [
                    "runs/residual_force_trajectory_regeneration_current_manifest.csv",
                    "runs/product_production_ai_gpu_return_intake_current.json",
                    "runs/rocm_environment_manifest_current.json",
                    "runs/residual_force_derivation_validation_current.json",
                    "runs/residual_energy_force_label_evidence_current.json",
                ],
                "return_summary_required_fields": [
                    "queue_rows",
                    "operator_verified_npz_exists",
                    "backend_provenance",
                    "delta_force",
                ],
                "post_return_validation_command": (
                    "python3 tools/build_residual_force_gpu_worker_return_receipt.py && "
                    "python3 tools/build_residual_force_derivation_validation.py"
                ),
                "next_required_step": (
                    "Return GPU worker NPZ artifacts and rerun residual force validation."
                ),
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            "rows": [],
        },
    )
    _write(
        runs_dir / "product_scope_closure_acceptance_packet_current.json",
        {
            "summary": {
                "packet_type": "product_scope_closure_acceptance_packet",
                "status": "blocked_product_scope_closure_acceptance_packet",
                "packet_ready": True,
                "scope_closure_ready": False,
                "scope_acceptance_stage_count": 5,
                "scope_acceptance_blocked_stage_count": 3,
                "scope_acceptance_blocked_stage_ids": [
                    "transporter_claim_acceptance",
                    "idp_broad_claim_acceptance",
                    "general_platform_claim_acceptance",
                ],
                "scope_acceptance_next_stage_id": "transporter_claim_acceptance",
                "scope_acceptance_next_stage_artifact": (
                    "runs/product_scope_breadth_contract_current.json"
                ),
                "scope_acceptance_next_stage_validation_command": (
                    "python3 tools/build_product_scope_breadth_contract.py"
                ),
                "first_blocked_evidence_row_id": "AQP1.core_binder_01",
                "first_blocked_target_id": "AQP1",
                "first_blocked_candidate": "aqp1_bacopaside_ii_review_seed",
                "first_blocked_required_missing_fields": (
                    "replacement_reference_binding_kcal_mol"
                ),
                "transporter_unresolved_slot_count": 11,
                "pxr_direct_or_claim_safe_quantitative_ready_count": 0,
                "general_platform_claim_allowed": False,
                "next_required_step": (
                    "Close AQP1 transporter exact-evidence rows before scope promotion."
                ),
                "execution_enabled": False,
                "external_state_mutated": False,
            },
            "rows": [],
        },
    )
    _write(
        runs_dir / "engine_refinement_claim_evidence_operator_field_worksheet_current.json",
        {
            "summary": {
                "packet_type": "engine_refinement_claim_evidence_operator_field_worksheet",
                "status": "engine_refinement_claim_evidence_operator_field_worksheet_ready",
                "field_worksheet_ready": True,
                "operator_fill_complete": False,
                "worksheet_field_row_count": 389,
                "operator_fill_pending_field_count": 296,
                "work_order_pending_field_count": 56,
                "top_blocker_id": "public_benchmark_gate_not_ready",
                "top_priority_bucket": "public_benchmark_work_order_apply_required",
                "claim_promoted": False,
                "claim_promotion_allowed": False,
                "external_engine_calls_executed": False,
                "external_state_mutated": False,
                "next_required_step": (
                    "Fill public benchmark work-order fields and matching claim evidence receipt fields."
                ),
            },
            "rows": [],
        },
    )
    _write(
        runs_dir / "engine_refinement_claim_evidence_operator_staging_apply_current.json",
        {
            "summary": {
                "packet_type": "engine_refinement_claim_evidence_operator_staging_apply",
                "status": "blocked_engine_refinement_claim_evidence_operator_staging_apply",
                "mode": "preview",
                "candidate_receipt_ready": False,
                "candidate_receipt_status": "blocked_engine_refinement_claim_evidence_receipt",
                "candidate_receipt_blocked_row_count": 6,
                "candidate_receipt_pass_row_count": 0,
                "staging_receipt_placeholder_row_count": 6,
                "candidate_public_benchmark_work_order_ready": False,
                "candidate_public_benchmark_work_order_status": (
                    "blocked_refine_tier_public_benchmark_work_order_apply"
                ),
                "candidate_public_benchmark_blocked_row_count": 6,
                "staging_public_benchmark_work_order_placeholder_row_count": 56,
                "field_worksheet_pending_field_count": 296,
                "field_worksheet_receipt_pending_field_count": 36,
                "field_worksheet_work_order_pending_field_count": 56,
                "first_blocked_blocker_id": "public_benchmark_gate_not_ready",
                "first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
                "first_blocked_expected_evidence_status": "refine_tier_public_benchmark_ready",
                "first_blocked_observed_evidence_status": "missing",
                "live_copy_allowed": False,
                "claim_promoted": False,
                "claim_promotion_allowed": False,
                "external_engine_calls_executed": False,
                "external_state_mutated": False,
            },
            "rows": [],
        },
    )

    operator_path = runs_dir / "product_commercial_readiness_operator_packet_current.json"
    try:
        operator_payload = json.loads(operator_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        operator_payload = {}
    if isinstance(operator_payload, dict):
        summary = operator_payload.get("summary")
        if isinstance(summary, dict):
            first_parallel_required_operator_inputs = (
                "reference_binding_kcal_mol;source_url_or_doi;operator_decision;"
                "reviewer;reviewed_at_utc;approval_token"
            )
            first_parallel_required_exact_fields = (
                "target_match_decision;reference_binding_kcal_mol;source_url_or_doi;"
                "smiles;scaffold"
            )
            first_parallel_claim_guardrails = (
                "functional_surrogate_does_not_authorize_direct_binding_claim;"
                "no_docking_only;claim_safe_kcal_required"
            )
            summary.update(
                {
                    "first_parallelizable_action_required_operator_inputs": (
                        first_parallel_required_operator_inputs
                    ),
                    "first_parallelizable_action_required_exact_evidence_fields": (
                        first_parallel_required_exact_fields
                    ),
                    "first_parallelizable_action_required_claim_guardrails": (
                        first_parallel_claim_guardrails
                    ),
                    "first_parallelizable_action_expected_evidence_type": (
                        "direct_or_claim_safe_binding_kcal"
                    ),
                    "first_parallelizable_action_operator_review_artifact": (
                        "runs/transporter_manual_review_intake_template_current.csv"
                    ),
                    "first_parallelizable_action_acceptance_gate_commands": (
                        "python3 tools/build_product_scope_breadth_contract.py && "
                        "python3 tools/build_product_goal_completion_audit.py"
                    ),
                    "first_parallelizable_action_next_slot_source_modality_guard_ready": True,
                    "first_parallelizable_action_next_slot_source_modality": (
                        "functional_quantitative_surrogate"
                    ),
                    "first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed": False,
                    "first_parallelizable_action_next_slot_source_modality_decision": (
                        "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
                    ),
                    "first_parallelizable_action_next_slot_source_modality_triage_artifact": (
                        "runs/aqp1_binding_source_modality_triage_current.json"
                    ),
                    "first_parallelizable_action_next_slot_source_modality_triage_decision": (
                        "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
                    ),
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
                    "operator_completion_packet_ready_count": 6,
                    "production_ai_return_action_required_operator_inputs": (
                        "queue_rows;processed_rows;ok_rows;failed_rows;aborted_early;"
                        "out_manifest_csv;out_summary_json;prod_mode;require_rust_hip;"
                        "backend_counts;protein_ca"
                    ),
                    "production_ai_return_operator_completion_expected_queue_rows": 768,
                    "production_ai_return_operator_completion_backend_provenance_completion_rule": "",
                    "production_ai_registry_promotion_operator_completion_diagnostic_commands": [
                        "python3 tools/build_residual_model_registry.py",
                        "python3 tools/build_product_production_ai_checkpoint_readiness.py",
                        "python3 tools/product/build_product_production_ai_promotion_workbench.py",
                    ],
                    "production_ai_registry_promotion_operator_completion_diagnostic_command_count": 3,
                    "production_ai_registry_promotion_operator_completion_completion_rule": (
                        "registry_promotion_missing_gate_count=0 after guarded operator approval"
                    ),
                    "first_operator_completion_diagnostic_commands": [
                        "python3 tools/build_residual_model_registry.py",
                        "python3 tools/build_product_production_ai_checkpoint_readiness.py",
                        "python3 tools/product/build_product_production_ai_promotion_workbench.py",
                    ],
                    "first_operator_completion_diagnostic_command_count": 3,
                    "first_operator_completion_diagnostic_required_fields": [
                        "production_promotion_allowed",
                        "customer_facing_auto_correction_allowed",
                        "customer_facing_score_mutation_allowed",
                        "customer_facing_ranking_mutation_allowed",
                        "default_residual_mode",
                        "trained_model_checkpoint_count",
                    ],
                    "first_operator_completion_diagnostic_required_field_count": 6,
                    "first_operator_completion_diagnostic_completion_rule": (
                        "production_promotion_allowed=true requires guarded residual mode, "
                        "trained_model_checkpoint_count>0, and explicit customer-facing mutation approval."
                    ),
                    "commercial_readiness_followup_diagnostic_command_count": 2,
                    "commercial_readiness_followup_diagnostic_commands": [
                        "python3 tools/product/build_product_full_commercial_blocker_evidence_matrix.py",
                        "python3 tools/product/build_product_launch_r4_preflight.py",
                    ],
                    "engine_refinement_claim_evidence_operator_field_worksheet_status": (
                        "engine_refinement_claim_evidence_operator_field_worksheet_ready"
                    ),
                    "engine_refinement_claim_evidence_operator_field_worksheet_ready": True,
                    "engine_refinement_claim_evidence_operator_field_worksheet_operator_fill_complete": False,
                    "engine_refinement_claim_evidence_operator_field_worksheet_field_row_count": 389,
                    "engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count": 296,
                    "engine_refinement_claim_evidence_operator_field_worksheet_receipt_pending_field_count": 36,
                    "engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count": 56,
                    "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id": (
                        "public_benchmark_gate_not_ready"
                    ),
                    "engine_refinement_claim_evidence_operator_field_worksheet_top_priority_bucket": (
                        "public_benchmark_work_order_apply_required"
                    ),
                    "engine_refinement_claim_evidence_operator_field_worksheet_external_state_mutated": False,
                    "delta_force_closure_acceptance_packet_artifact": (
                        "runs/residual_delta_force_closure_acceptance_packet_current.json"
                    ),
                    "delta_force_closure_acceptance_packet_ready": True,
                    "delta_force_closure_ready": False,
                    "delta_force_closure_first_blocked_output_field": "delta_force",
                    "delta_force_closure_ready_output_field_count": 6,
                    "delta_force_closure_blocked_output_field_count": 1,
                    "delta_force_closure_failed_stage_count": 9,
                    "delta_force_closure_next_stage_id": "gpu_worker_return_receipt",
                    "delta_force_closure_next_stage_artifact": (
                        "runs/product_production_ai_gpu_return_intake_current.json"
                    ),
                    "delta_force_closure_next_stage_validation_command": (
                        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
                    ),
                    "delta_force_closure_return_summary_required_fields": [
                        "queue_rows",
                        "operator_verified_npz_exists",
                        "backend_provenance",
                        "delta_force",
                    ],
                    "scope_closure_acceptance_packet_artifact": (
                        "runs/product_scope_closure_acceptance_packet_current.json"
                    ),
                    "scope_closure_acceptance_packet_ready": True,
                    "scope_closure_ready": False,
                    "scope_closure_stage_count": 5,
                    "scope_closure_blocked_stage_count": 3,
                    "scope_closure_blocked_stage_ids": [
                        "transporter_claim_acceptance",
                        "idp_broad_claim_acceptance",
                        "general_platform_claim_acceptance",
                    ],
                    "scope_closure_next_stage_id": "transporter_claim_acceptance",
                    "scope_closure_next_stage_artifact": (
                        "runs/product_scope_breadth_contract_current.json"
                    ),
                    "scope_closure_next_stage_validation_command": (
                        "python3 tools/build_product_scope_breadth_contract.py"
                    ),
                    "scope_closure_first_blocked_evidence_row_id": "AQP1.core_binder_01",
                    "scope_closure_first_blocked_target_id": "AQP1",
                    "scope_closure_first_blocked_required_missing_fields": (
                        "replacement_reference_binding_kcal_mol"
                    ),
                    "scope_closure_transporter_unresolved_slot_count": 11,
                    "scope_closure_pxr_direct_or_claim_safe_quantitative_ready_count": 0,
                    "scope_closure_general_platform_claim_allowed": False,
                }
            )
            operator_payload["summary"] = summary
            rows = operator_payload.get("rows")
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    if row.get("action_id") == "production_gpu_execution_environment":
                        row["operator_completion_diagnostic_commands"] = (
                            "rocminfo;python3 -c \"import torch; print(torch.cuda.device_count())\";"
                            "python3 tools/build_rocm_environment_manifest.py;"
                            "python3 scripts/run_gpu_newton_terminal_certification.py;"
                            "python3 tools/build_product_production_ai_checkpoint_readiness.py;"
                            "python3 tools/build_product_production_ai_promotion_workbench.py"
                        )
                        row["operator_completion_diagnostic_command_count"] = 5
                        row["operator_completion_diagnostic_completion_rule"] = (
                            "visible_device_count>0 and torch_ready=true"
                        )
                    if row.get("action_id") == "production_ai_registry_guarded_promotion":
                        row["operator_completion_diagnostic_commands"] = (
                            "python3 tools/build_residual_model_registry.py;"
                            "python3 tools/build_product_production_ai_checkpoint_readiness.py;"
                            "python3 tools/product/build_product_production_ai_promotion_workbench.py"
                        )
                    if row.get("action_id") == "production_ai_return_summary":
                        row["required_operator_inputs"] = (
                            "queue_rows;processed_rows;ok_rows;failed_rows;aborted_early;"
                            "out_manifest_csv;out_summary_json;prod_mode;require_rust_hip;"
                            "backend_counts;protein_ca"
                        )
                    if row.get("action_id") != "transporter_next_slot_exact_evidence":
                        continue
                    row.update(
                        {
                            "next_slot_id": "AQP1.core_binder_01",
                            "required_operator_inputs": first_parallel_required_operator_inputs,
                            "required_exact_evidence_fields": first_parallel_required_exact_fields,
                            "required_claim_guardrails": first_parallel_claim_guardrails,
                            "expected_evidence_type": "direct_or_claim_safe_binding_kcal",
                            "operator_review_artifact": (
                                "runs/transporter_manual_review_intake_template_current.csv"
                            ),
                            "acceptance_gate_commands": (
                                "python3 tools/build_product_scope_breadth_contract.py && "
                                "python3 tools/build_product_goal_completion_audit.py"
                            ),
                            "next_slot_source_modality_guard_ready": True,
                            "next_slot_source_modality": "functional_quantitative_surrogate",
                            "next_slot_source_modality_direct_binding_claim_allowed": False,
                            "next_slot_source_modality_decision": (
                                "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
                            ),
                            "next_slot_source_modality_triage_artifact": (
                                "runs/aqp1_binding_source_modality_triage_current.json"
                            ),
                            "next_slot_source_modality_triage_decision": (
                                "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
                            ),
                            "next_slot_source_modality_computational_binding_energy_row_count": 1,
                            "next_slot_source_modality_best_computational_binding_energy_kcal_mol": (
                                "-34.48"
                            ),
                            "operator_validation_candidate_ready": True,
                            "operator_validation_candidate_status": "operator_validation_required",
                            "operator_validation_candidate_ligand_external_identifier": "CHEMBL20",
                            "operator_validation_candidate_reference_binding_kcal_mol": "-5.13",
                            "operator_validation_candidate_blocker": (
                                "data_validity_outside_typical_range_and_assay_origin_unknown"
                            ),
                            "operator_validation_candidate_claim_safe_ready": False,
                            "operator_completion_packet_ready": True,
                        }
                    )
                operator_payload["rows"] = rows
            _write(operator_path, operator_payload)


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
            "product_scope_claim_expansion_current_blocked_stage_count": 3,
            "product_scope_claim_expansion_current_blocked_stage_ids": [
                "transporter_claim_acceptance",
                "pxr_claim_acceptance",
                "general_platform_claim_acceptance",
            ],
            "product_scope_acceptance_stage_evidence_matrix": [
                {"stage_id": "scope_evidence_acquisition_preflight", "status": "ready"},
                {
                    "stage_id": "transporter_claim_acceptance",
                    "status": "blocked",
                    "first_blocked_evidence_row": {
                        "evidence_row_id": "AQP1.core_binder_01",
                        "target_id": "AQP1",
                        "required_missing_fields": (
                            "replacement_reference_binding_kcal_mol"
                        ),
                    },
                },
                {"stage_id": "pxr_claim_acceptance", "status": "blocked"},
                {"stage_id": "breadth_domain_floor_acceptance", "status": "ready"},
                {"stage_id": "general_platform_claim_acceptance", "status": "blocked"},
            ],
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


def write_restricted_goal_release_decision_gate(runs_dir: Path) -> None:
    path = runs_dir / "goal_release_decision_gate_current.json"
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
            "status": "blocked_goal_release_decision",
            "release_allowed": False,
            "blocker_count": len(blocker_ids),
            "full_commercial_release_blocker_count": len(blocker_ids),
            "full_commercial_release_blocker_ids": blocker_ids,
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


def write_restricted_accuracy_parity_scorecard(runs_dir: Path) -> None:
    _write(
        runs_dir / "accuracy_parity_scorecard_current.json",
        {
            "summary": {
                "status": "blocked_accuracy_parity",
                "row_count": 1,
                "pass_row_count": 0,
                "restricted_pass_row_count": 1,
                "blocked_row_count": 0,
                "top_blockers": ["ligand_ranking:broad_gpcr_claim_not_allowed"],
                "overall_commercial_tool_accuracy_parity_allowed": False,
                "next_required_step": "Close the ligand-ranking claim scope before any broad GPCR/router promotion.",
            },
            "rows": [
                {
                    "axis": "ligand_ranking",
                    "status": "restricted_pass",
                    "claim_scope": "restricted_gpcr_ligand_ranking",
                    "comparator": "public_benchmark_fixture",
                    "claim_promotion_allowed": False,
                    "commercial_parity_claim_allowed": False,
                    "blockers": ["broad_gpcr_claim_not_allowed"],
                    "metrics": {
                        "ranking_pr_auc": 0.871853,
                        "ranking_pr_auc_ci_low": 0.761168,
                        "ranking_topk_hit_rate": 1.0,
                    },
                    "thresholds": {
                        "ranking_pr_auc_min": 0.55,
                        "ranking_pr_auc_ci_low_min": 0.45,
                        "ranking_topk_hit_rate_min": 0.50,
                    },
                    "source_artifacts": [
                        "runs/product_public_benchmark_work_order_current.json"
                    ],
                    "next_required_step": "Record the broad GPCR claim-scope closure before promotion.",
                }
            ],
        },
    )


def write_cameo_api_surface_fixture_packets(runs_dir: Path) -> None:
    official_results_csv = runs_dir / "cameo_official_results_operator_intake.csv"
    official_results_template = runs_dir / "cameo_official_results_operator_template_current.csv"
    registration_csv = runs_dir / "cameo_public_registration_operator_approval_intake.csv"
    registration_template = runs_dir / "cameo_public_registration_operator_approval_template_current.csv"
    fetch_template = runs_dir / "cameo_official_result_fetch_operator_approval_template_current.csv"

    official_results_csv.parent.mkdir(parents=True, exist_ok=True)
    official_header = (
        "target_id,candidate_id,cameo_model_rank,result_source_kind,"
        "result_source_url,result_record_id,retrieved_at_utc,assessment_date,"
        "lddt,tm_score,qs_score,rmsd_A\n"
    )
    official_results_csv.write_text(
        official_header
        + "CAMEO_DRY_RUN_FORMAT_SMOKE,cameo_local_format_smoke_model1,1,"
        "official_cameo,https://cameo3d.org/modeling/CAMEO_DRY_RUN_FORMAT_SMOKE,"
        "CAMEO_DRY_RUN_FORMAT_SMOKE:model1,2026-06-03T00:00:00Z,2026-06-03,"
        "0.72,0.61,0.42,2.8\n",
        encoding="utf-8",
    )
    official_results_template.write_text(official_header, encoding="utf-8")

    registration_header = (
        "target_id,operator_decision,registration_approval_token,"
        "outbound_email_approval_token,public_endpoint_url,results_email,"
        "contact_email,operator_note\n"
    )
    registration_csv.write_text(
        registration_header
        + "CAMEO_DRY_RUN_FORMAT_SMOKE,approve,APPROVE_CAMEO_SERVER_REGISTRATION,"
        "APPROVE_CAMEO_OUTBOUND_EMAIL,https://example.org/cameo/targets,"
        "results@example.org,contact@example.org,CI fixture separate registration review only\n",
        encoding="utf-8",
    )
    registration_template.write_text(registration_header, encoding="utf-8")

    fetch_header = (
        "target_id,operator_decision,official_result_url,official_result_record_id,"
        "candidate_id,fetch_approval_token,operator_note\n"
    )
    fetch_template.write_text(fetch_header, encoding="utf-8")

    required_columns = [
        "target_id",
        "candidate_id",
        "cameo_model_rank",
        "result_source_kind",
        "result_source_url",
        "result_record_id",
        "retrieved_at_utc",
        "assessment_date",
    ]
    metric_columns = ["lddt", "tm_score", "qs_score", "rmsd_A"]
    disallowed_columns = ["native_accuracy", "local_native_score", "template_hit"]

    _write(
        runs_dir / "cameo_official_results_intake_gate_current.json",
        {
            "summary": {
                "packet_type": "cameo_official_results_intake_gate",
                "status": "cameo_official_results_intake_ready",
                "operator_template_csv": "runs/cameo_official_results_operator_template_current.csv",
                "operator_intake_csv": "runs/cameo_official_results_operator_intake.csv",
                "result_row_count": 1,
                "accepted_official_result_count": 1,
                "rejected_official_result_count": 0,
                "model1_official_result_ready": True,
                "blocker_count": 0,
                "blocker_codes": [],
                "required_columns": required_columns,
                "missing_required_columns": [],
                "official_metric_columns": metric_columns,
                "disallowed_local_accuracy_columns": disallowed_columns,
                "official_cameo_results_used": True,
                "native_local_accuracy_used": False,
                "official_results_fetched": False,
                "external_state_mutated": False,
            },
            "rows": [
                {
                    "target_id": "CAMEO_DRY_RUN_FORMAT_SMOKE",
                    "candidate_id": "cameo_local_format_smoke_model1",
                    "cameo_model_rank": "1",
                    "result_status": "accepted_official_result",
                }
            ],
        },
    )
    _write(
        runs_dir / "cameo_validation_readiness_gate_current.json",
        {
            "summary": {
                "packet_type": "cameo_validation_readiness_gate",
                "status": "cameo_validation_evidence_ready",
                "target_id": "CAMEO_DRY_RUN_FORMAT_SMOKE",
                "stage_count": 4,
                "ready_stage_count": 4,
                "missing_stage_count": 0,
                "blocker_count": 0,
                "performance_status": "cameo_performance_evidence_ready",
                "official_cameo_results_used": True,
                "native_local_accuracy_used": False,
                "outbound_email_enabled": False,
                "external_state_mutated": False,
            },
            "rows": [],
        },
    )
    _write(
        runs_dir / "cameo_repair_execution_preflight_current.json",
        {
            "summary": {
                "packet_type": "cameo_repair_execution_preflight",
                "status": "cameo_repair_execution_not_required",
                "source_operator_input_validation_status": "cameo_operator_inputs_ready_with_official_results",
                "command_count": 0,
                "blocker_count": 0,
                "input_blocker_count": 0,
                "action_executed": False,
                "native_local_accuracy_used": False,
                "outbound_email_enabled": False,
                "external_state_mutated": False,
            },
            "rows": [],
        },
    )
    _write(
        runs_dir / "cameo_api_dependency_readiness_current.json",
        {
            "summary": {
                "packet_type": "cameo_api_dependency_readiness",
                "status": "cameo_api_dependency_ready",
                "missing_or_unimportable_count": 0,
                "blocker_count": 0,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "cameo_receiver_smoke_contract_current.json",
        {
            "summary": {
                "packet_type": "cameo_receiver_smoke_contract",
                "status": "cameo_receiver_smoke_ready",
                "source_api_dependency_status": "cameo_api_dependency_ready",
                "api_dependency_ready": True,
                "api_dependency_blocker_count": 0,
                "post_200_ok": True,
                "blocker_count": 0,
                "server_started": False,
                "prediction_generation_enabled": False,
                "outbound_email_enabled": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "cameo_capability_preflight_current.json",
        {
            "summary": {
                "packet_type": "cameo_capability_preflight",
                "status": "cameo_public_registration_preflight_ready",
                "capability_lane": "polymer_complex_receiver_dry_run",
                "receiver_scaffold_present": True,
                "api_route_registered": True,
                "api_operations_route_registered": True,
                "local_status_cli_present": True,
                "source_validation_status": "cameo_validation_evidence_ready",
                "source_repair_execution_preflight_status": "cameo_repair_execution_not_required",
                "source_receiver_smoke_status": "cameo_receiver_smoke_ready",
                "source_api_dependency_status": "cameo_api_dependency_ready",
                "api_dependency_ready": True,
                "receiver_smoke_post_200_ok": True,
                "public_registration_requested": True,
                "public_registration_allowed": True,
                "public_registration_blocker_count": 0,
                "blocker_count": 0,
                "warning_count": 0,
                "registration_approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION",
                "outbound_email_approval_token_required": "APPROVE_CAMEO_OUTBOUND_EMAIL",
                "server_registration_mutated": False,
                "prediction_generation_enabled": False,
                "outbound_email_enabled": False,
                "external_state_mutated": False,
            },
            "rows": [],
        },
    )
    _write(
        runs_dir / "cameo_public_registration_approval_gate_current.json",
        {
            "summary": {
                "packet_type": "cameo_public_registration_approval_gate",
                "status": "cameo_public_registration_approval_gate_ready",
                "source_capability_status": "cameo_public_registration_preflight_ready",
                "source_operations_dossier_status": "blocked_cameo_validation_operations_dossier",
                "operator_template_csv": "runs/cameo_public_registration_operator_approval_template_current.csv",
                "operator_approval_csv": "runs/cameo_public_registration_operator_approval_intake.csv",
                "operator_approval_csv_present": True,
                "target_id": "CAMEO_DRY_RUN_FORMAT_SMOKE",
                "capability_public_registration_ready": True,
                "official_cameo_validation_evidence_ready": True,
                "receiver_smoke_ready": True,
                "authorized_for_registration_review": True,
                "authorized_row_count": 1,
                "blocked_row_count": 0,
                "blocker_count": 0,
                "blockers": [],
                "registration_approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION",
                "outbound_email_approval_token_required": "APPROVE_CAMEO_OUTBOUND_EMAIL",
                "server_registration_mutated": False,
                "prediction_generation_enabled": False,
                "outbound_email_enabled": False,
                "external_state_mutated": False,
            },
            "rows": [
                {
                    "target_id": "CAMEO_DRY_RUN_FORMAT_SMOKE",
                    "approval_gate_status": "approved_for_separate_registration_review",
                    "operator_decision": "approve",
                    "server_registration_mutated": False,
                    "outbound_email_enabled": False,
                    "external_state_mutated": False,
                }
            ],
        },
    )
    _write(
        runs_dir / "cameo_evidence_integrity_contract_current.json",
        {
            "summary": {
                "packet_type": "cameo_evidence_integrity_contract",
                "status": "cameo_evidence_integrity_contract_ready",
                "evidence_integrity_ready": True,
                "check_count": 5,
                "pass_count": 5,
                "blocker_count": 0,
                "official_result_provenance_honest": True,
                "official_result_schema_visible": True,
                "official_results_ready": True,
                "official_results_pending_honest": True,
                "no_local_native_accuracy_substitution": True,
                "external_mutation_flags_clear": True,
                "registration_and_email_gated": True,
                "local_protocol_connected": True,
                "operator_intake_csv": "runs/cameo_official_results_operator_intake.csv",
                "missing_required_columns": [],
                "server_started": False,
                "server_registration_mutated": False,
                "prediction_generation_enabled": False,
                "outbound_email_enabled": False,
                "official_results_fetched": False,
                "native_local_accuracy_used": False,
                "external_state_mutated": False,
            },
            "rows": [],
            "blockers": [],
        },
    )
    _write(
        runs_dir / "cameo_official_result_fetch_preflight_current.json",
        {
            "summary": {
                "packet_type": "cameo_official_result_fetch_preflight",
                "status": "blocked_cameo_official_result_fetch_preflight",
                "source_operations_dossier_status": "blocked_cameo_validation_operations_dossier",
                "operator_fetch_csv": "runs/cameo_official_result_fetch_operator_approval_intake.csv",
                "operator_fetch_csv_present": False,
                "operator_template_csv": "runs/cameo_official_result_fetch_operator_approval_template_current.csv",
                "target_id": "CAMEO_DRY_RUN_FORMAT_SMOKE",
                "operations_surface_ready": True,
                "receiver_smoke_ready": True,
                "authorized_for_separate_operator_fetch": False,
                "authorized_row_count": 0,
                "awaiting_operator_fetch_approval_row_count": 1,
                "skipped_row_count": 0,
                "blocked_row_count": 1,
                "blocker_count": 2,
                "blockers": ["operator_decision_missing", "operator_fetch_csv_missing"],
                "fetch_approval_token_required": "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH",
                "network_request_opened": False,
                "official_results_fetched": False,
                "native_local_accuracy_used": False,
                "outbound_email_enabled": False,
                "external_state_mutated": False,
            },
            "rows": [
                {
                    "target_id": "CAMEO_DRY_RUN_FORMAT_SMOKE",
                    "fetch_preflight_status": "awaiting_operator_fetch_approval",
                    "operator_decision": "",
                    "fetch_approval_token_required": "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH",
                    "blockers": "operator_decision_missing",
                    "network_request_opened": False,
                    "official_results_fetched": False,
                    "native_local_accuracy_used": False,
                    "outbound_email_enabled": False,
                    "external_state_mutated": False,
                }
            ],
        },
    )
    _write(
        runs_dir / "cameo_validation_operations_dossier_current.json",
        {
            "summary": {
                "packet_type": "cameo_validation_operations_dossier",
                "status": "blocked_cameo_validation_operations_dossier",
                "target_id": "CAMEO_DRY_RUN_FORMAT_SMOKE",
                "stage_count": 10,
                "blocked_stage_count": 1,
                "approval_required_stage_count": 1,
                "approval_token_count": 2,
                "approval_tokens_required": [
                    "APPROVE_CAMEO_OUTBOUND_EMAIL",
                    "APPROVE_CAMEO_SERVER_REGISTRATION",
                ],
                "first_blocked_stage_id": "official_result_fetch_preflight",
                "first_blocked_stage_source_status": "blocked_cameo_official_result_fetch_preflight",
                "first_blocked_stage_artifact": "runs/cameo_official_result_fetch_preflight_current.json",
                "first_blocked_stage_blocker_count": 2,
                "first_approval_required_stage_id": "public_registration_and_email",
                "first_approval_required_stage_source_status": "cameo_public_registration_preflight_ready",
                "first_approval_required_stage_artifact": "runs/cameo_capability_preflight_current.json",
                "first_approval_required_stage_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL",
                "operator_input_required_count": 0,
                "operator_input_blocker_count": 0,
                "validation_readiness_status": "cameo_validation_evidence_ready",
                "validation_ready": True,
                "official_results_intake_status": "cameo_official_results_intake_ready",
                "official_results_intake_ready": True,
                "official_results_intake_blocker_count": 0,
                "official_model1_result_ready": True,
                "official_result_required": False,
                "official_cameo_results_used": True,
                "official_result_fetch_preflight_status": "blocked_cameo_official_result_fetch_preflight",
                "official_result_fetch_preflight_ready": False,
                "official_result_fetch_preflight_authorized": False,
                "official_result_fetch_preflight_network_request_opened": False,
                "official_result_fetch_preflight_results_fetched": False,
                "evidence_integrity_ready": True,
                "evidence_integrity_status": "cameo_evidence_integrity_contract_ready",
                "evidence_integrity_blocker_count": 0,
                "official_results_pending_honest": True,
                "no_local_native_accuracy_substitution": True,
                "external_mutation_flags_clear": True,
                "api_dependency_status": "cameo_api_dependency_ready",
                "receiver_smoke_status": "cameo_receiver_smoke_ready",
                "runtime_install_approval_required": False,
                "public_registration_allowed": True,
                "registration_approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION",
                "outbound_email_approval_token_required": "APPROVE_CAMEO_OUTBOUND_EMAIL",
                "package_install_executed": False,
                "server_started": False,
                "server_registration_mutated": False,
                "prediction_generation_enabled": False,
                "outbound_email_enabled": False,
                "native_local_accuracy_used": False,
                "external_state_mutated": False,
                "claim_boundary": "CAMEO validation operations dossier CI fixture only; it exposes fail-closed read-only operator gates and does not fetch official results, register a server, send email, generate predictions, or mutate external state.",
            },
            "rows": [
                {
                    "priority": 3,
                    "stage": "official_result_fetch_preflight",
                    "status": "blocked",
                    "source_status": "blocked_cameo_official_result_fetch_preflight",
                    "blocker_count": 2,
                    "source_artifact": "runs/cameo_official_result_fetch_preflight_current.json",
                    "external_state_mutated": False,
                },
                {
                    "priority": 10,
                    "stage": "public_registration_and_email",
                    "status": "approval_required",
                    "source_status": "cameo_public_registration_preflight_ready",
                    "blocker_count": 0,
                    "approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL",
                    "source_artifact": "runs/cameo_capability_preflight_current.json",
                    "external_state_mutated": False,
                },
            ],
        },
    )


def write_product_scope_breadth_priority_fixture_packets(runs_dir: Path) -> None:
    priority_row = {
        "priority": 1,
        "domain": "transporter",
        "target_id": "AQP1",
        "target_promotion_status": "target_blocked_for_promotion",
        "target_ready_for_promotion": False,
        "target_blocked_for_promotion": True,
        "item_id": "AQP1.core_binder_01",
        "item_type": "scientific_evidence_request",
        "candidate_or_check": "AQP1 core_binder_01",
        "evidence_priority_bucket": "local_crosscheck_review_present_but_exact_quant_required",
        "action_lane": "local_crosscheck_triage_then_exact_source_capture",
        "local_crosscheck_present": True,
        "local_crosscheck_path_count": 1,
        "local_crosscheck_paths": "runs/life_science_skill_crosscheck/aqp1_core_binder_01_crosscheck.md",
        "request_mode": "quantitative_binder_exact_source_required",
        "acceptance_criteria": "Accept only exact target-pair quantitative binder evidence with claim-safe kcal provenance and synchronized reference/split/meta rows.",
        "rejection_criteria": "Reject docking-only, target-ambiguous, qualitative-only, or replacement rows missing ligand/source/SMILES/scaffold synchronization.",
        "next_step": "Review local crosscheck files.",
        "required_evidence_type": "exact_transporter_target_pair_quantitative_binder_kcal",
        "review_template_artifact": "runs/transporter_manual_review_intake_template_current.json",
        "apply_gate_artifact": "runs/transporter_binder_promotion_gate_current.json",
        "regeneration_commands": "python3 tools/build_transporter_manual_review_intake_template.py; python3 tools/build_transporter_binder_promotion_gate.py; python3 tools/build_product_scope_breadth_evidence_priority_packet.py",
        "operator_packet_binding_key": "transporter:AQP1.core_binder_01",
        "operator_packet_binding_ready": True,
        "source_artifact": "runs/product_scope_breadth_evidence_acquisition_queue_current.json",
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
    }
    priority_rows = [priority_row] + [
        {
            **priority_row,
            "priority": index,
            "item_id": f"transporter.review_{index:02d}",
            "target_id": "AQP1" if index <= 8 else "GLUT1",
            "candidate_or_check": f"transporter review item {index:02d}",
            "operator_packet_binding_key": f"transporter:review_{index:02d}",
        }
        for index in range(2, 16)
    ]
    priority_summary = {
        "packet_type": "product_scope_breadth_evidence_priority_packet",
        "status": "product_scope_breadth_evidence_priority_packet_ready",
        "priority_packet_ready": True,
        "queue_item_count": 15,
        "source_queue_item_count": 15,
        "scientific_evidence_request_count": 11,
        "claim_gate_prerequisite_count": 0,
        "local_crosscheck_candidate_count": 11,
        "external_primary_exact_evidence_required_count": 0,
        "review_only_keep_blocked_count": 0,
        "transporter_binder_gate_present": True,
        "transporter_binder_gate_path": "runs/transporter_binder_promotion_gate_current.json",
        "transporter_binder_gate_status": "blocked_transporter_binder_promotion_gate",
        "transporter_binder_promotion_ready": False,
        "transporter_target_ready_for_promotion_count": 0,
        "transporter_target_blocked_for_promotion_count": 1,
        "transporter_target_ready_for_promotion_ids": [],
        "transporter_target_blocked_for_promotion_ids": ["AQP1"],
        "transporter_priority_target_ready_item_count": 0,
        "transporter_priority_target_blocked_item_count": 1,
        "transporter_primary_blocker_target_id": "AQP1",
        "operator_packet_binding_ready_count": 15,
        "operator_packet_binding_missing_count": 0,
        "all_operator_packet_bindings_ready": True,
        "top_item_id": "AQP1.core_binder_01",
        "top_target_id": "AQP1",
        "top_target_promotion_status": "target_blocked_for_promotion",
        "top_target_blocked_for_promotion": True,
        "top_domain": "transporter",
        "top_bucket": "local_crosscheck_review_present_but_exact_quant_required",
        "top_required_evidence_type": "exact_transporter_target_pair_quantitative_binder_kcal",
        "top_review_template_artifact": "runs/transporter_manual_review_intake_template_current.json",
        "top_apply_gate_artifact": "runs/transporter_binder_promotion_gate_current.json",
        "top_next_step": "Review local crosscheck files.",
        "receipt_source_json": "runs/product_scope_breadth_evidence_receipt_current.json",
        "receipt_status": "blocked_product_scope_breadth_evidence_receipt",
        "receipt_ready": False,
        "receipt_csv": "config/product_scope_breadth_evidence_receipt_current.csv",
        "receipt_row_count": 6,
        "receipt_blocked_row_count": 6,
        "receipt_operator_review_surface_ready_count": 6,
        "receipt_operator_review_surface_blocked_count": 0,
        "receipt_manual_field_pending_count": 36,
        "receipt_evidence_artifact_pending_count": 6,
        "receipt_claim_ready_pending_count": 6,
        "receipt_reviewer_pending_count": 6,
        "receipt_reviewed_at_utc_pending_count": 6,
        "receipt_license_ok_pending_count": 6,
        "receipt_approval_token_pending_count": 6,
        "receipt_first_blocked_scope_blocker_id": "direct_binding_evidence_missing",
        "receipt_first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
        "receipt_first_blocked_expected_evidence_status": "product_scope_transporter_direct_binding_evidence_ready",
        "receipt_first_blocked_observed_evidence_status": "missing",
        "receipt_first_blocked_missing_true_fields": ["transporter_direct_binding_evidence_ready"],
        "receipt_first_blocked_row_blockers": [
            "operator_placeholders_unfilled",
            "evidence_artifact_not_found",
            "evidence_true_fields_missing:transporter_direct_binding_evidence_ready",
            "claim_ready_not_true",
        ],
        "receipt_most_common_row_blocker": "operator_placeholders_unfilled",
        "receipt_approval_token_required": "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT",
        "open_item_count": 15,
        "authoritative_apply_allowed_count": 0,
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
        "source_artifacts": [
            "runs/product_scope_breadth_evidence_acquisition_queue_current.json",
            "runs/life_science_skill_crosscheck",
            "runs/transporter_binder_promotion_gate_current.json",
            "runs/product_scope_breadth_evidence_receipt_current.json",
        ],
    }
    _write(
        runs_dir / "product_scope_breadth_evidence_priority_packet_current.json",
        {"summary": priority_summary, "rows": priority_rows},
    )
    _write(
        runs_dir / "product_scope_breadth_evidence_acquisition_queue_current.json",
        {
            "summary": {
                "packet_type": "product_scope_breadth_evidence_acquisition_queue",
                "status": "product_scope_breadth_evidence_acquisition_queue_ready",
                "queue_ready": True,
                "scope_breadth_ready": False,
                "queue_item_count": 6,
                "scientific_evidence_request_count": 6,
                "claim_gate_prerequisite_count": 0,
                "next_operator_completion_packet_ready": True,
                "next_operator_completion_slot_id": "AQP1.core_binder_01",
                "next_operator_completion_expected_evidence_type": "exact_transporter_target_pair_quantitative_binder_kcal",
                "next_operator_completion_required_exact_evidence_field_count": 6,
                "next_operator_completion_required_exact_evidence_fields": "target_id;candidate_id;source_url;smiles;scaffold;binding_kcal_mol",
                "next_operator_completion_required_operator_intake_columns": "operator_decision;reviewer;reviewed_at_utc;approval_token",
                "next_operator_completion_required_claim_guardrails": "no_docking_only;no_target_ambiguous;claim_safe_kcal_required",
                "next_operator_completion_operator_review_artifact": "runs/transporter_manual_review_intake_template_current.json",
                "next_operator_completion_acceptance_gate_commands": "python3 tools/build_transporter_binder_promotion_gate.py; python3 tools/build_product_scope_breadth_evidence_priority_packet.py",
                "next_operator_completion_contract_artifact": "runs/product_scope_breadth_evidence_priority_packet_current.json",
                "next_operator_completion_aqp1_review_sidecar_ready": True,
                "next_operator_completion_aqp1_review_candidate_name": "AQP1 core_binder_01",
                "next_operator_completion_aqp1_review_source_anchor": "operator crosscheck",
                "next_operator_completion_aqp1_review_source_url": "runs/life_science_skill_crosscheck/aqp1_core_binder_01_crosscheck.md",
                "next_operator_completion_aqp1_review_target_uniprot": "P29972",
                "next_operator_completion_aqp1_review_functional_measure": "review_only_functional_surrogate",
                "next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": "",
                "next_operator_completion_aqp1_review_assay_type_honesty": "direct_binding_not_claimed",
                "next_operator_completion_aqp1_review_direct_binding_claim_allowed": "false",
                "next_operator_completion_aqp1_review_binding_kcal_claim_allowed": "false",
                "next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": "true",
                "external_state_mutated": False,
            },
            "rows": [priority_row],
        },
    )
    _write(
        runs_dir / "product_scope_breadth_evidence_intake_readiness_current.json",
        {
            "summary": {
                "packet_type": "product_scope_breadth_evidence_intake_readiness",
                "status": "product_scope_breadth_evidence_intake_readiness_ready",
                "intake_readiness_ready": True,
                "scope_promotion_allowed": False,
                "authoritative_apply_allowed": False,
                "row_count": 15,
                "local_crosscheck_triage_item_count": 11,
                "local_crosscheck_intake_ready_count": 10,
                "external_exact_evidence_required_count": 0,
                "guardrail_item_count": 4,
                "operator_packet_binding_ready_count": 15,
                "operator_packet_binding_missing_count": 0,
                "all_operator_packet_bindings_ready": True,
                "top_unbound_item_id": "",
                "top_unbound_required_evidence_type": "",
                "next_operator_completion_item_id": "AQP1.core_binder_01",
                "next_operator_completion_domain": "transporter",
                "next_operator_completion_candidate_or_check": "aqp1_bacopaside_ii_review_seed",
                "next_operator_completion_intake_mode": "local_crosscheck_triage",
                "next_operator_completion_required_evidence_type": (
                    "exact_transporter_target_pair_quantitative_binder_kcal"
                ),
                "next_operator_completion_required_intake_columns": [
                    "target_id",
                    "candidate_ligand_id",
                    "reference_binding_kcal_mol",
                    "source_url_or_doi",
                    "smiles",
                    "scaffold",
                    "evidence_type",
                ],
                "next_operator_completion_required_intake_column_count": 7,
                "next_operator_completion_review_template_artifact": (
                    "runs/transporter_manual_review_intake_template_current.json"
                ),
                "next_operator_completion_apply_gate_artifact": (
                    "runs/transporter_binder_promotion_gate_current.json"
                ),
                "next_operator_completion_regeneration_commands": (
                    "python3 tools/build_transporter_manual_review_intake_template.py; "
                    "python3 tools/build_transporter_binder_promotion_gate.py; "
                    "python3 tools/build_product_scope_breadth_evidence_priority_packet.py"
                ),
                "next_operator_completion_operator_packet_binding_key": (
                    "transporter:AQP1.core_binder_01"
                ),
                "next_operator_completion_operator_packet_binding_ready": True,
                "next_operator_completion_transporter_claim_safe_blocker": (
                    "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed"
                ),
                "next_operator_completion_transporter_operator_next_verdict": "KEEP_BLOCKED",
                "next_operator_completion_transporter_best_evidence_source_file": (
                    "runs/life_science_skill_crosscheck/aqp1_core_binder_01_crosscheck.md"
                ),
                "next_operator_completion_transporter_best_evidence_activity_type": "KD",
                "next_operator_completion_transporter_best_evidence_value": "100",
                "next_operator_completion_transporter_best_evidence_units": "nM",
                "next_operator_completion_transporter_best_evidence_document_id": "PMID 27474162",
                "transporter_triage_packet_ready": True,
                "transporter_operator_review_evidence_matrix_ready": True,
                "transporter_claim_safe_local_evidence_ready_count": 0,
                "transporter_claim_safe_local_evidence_blocked_count": 11,
                "transporter_direct_binding_claim_blocked_count": 4,
                "transporter_negative_value_claim_blocked_count": 6,
                "transporter_top_claim_safe_blocker": (
                    "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed"
                ),
                "transporter_top_operator_next_verdict": "KEEP_BLOCKED",
                "transporter_candidate_row_count": 11,
                "transporter_candidate_ready_for_manual_review_count": 8,
                "transporter_candidate_ready_for_apply_count": 0,
                "transporter_candidate_assignment_required_count": 1,
                "transporter_functional_quantitative_only_direct_gap_open_count": 4,
                "transporter_review_only_direct_binding_gap_count": 4,
                "transporter_manual_review_intake_ready": True,
                "transporter_manual_review_template_row_count": 8,
                "transporter_manual_review_direct_binding_evidence_required_count": 1,
                "transporter_manual_review_negative_quantitative_value_required_count": 6,
                "transporter_manual_review_decision_placeholder_count": 0,
                "first_review_row_id": "AQP1.core_non_binder_01",
                "first_review_item_id": "AQP1.core_non_binder_01",
                "first_review_target_id": "AQP1",
                "first_review_candidate_ligand_id": "chembl_chembl2179173",
                "first_review_replacement_source": (
                    "chembl_activity::CHEMBL2179173::INHIBITION__%::source_CHEMBL4421726"
                ),
                "first_review_replacement_reference_binding_kcal_mol": "",
                "first_review_direct_binding_evidence_required": False,
                "first_review_direct_binding_source_url_or_doi": "",
                "first_review_negative_quantitative_value_required": True,
                "first_review_negative_reference_binding_kcal_mol": "",
                "first_review_review_decision": "KEEP_BLOCKED",
                "first_review_authoritative_apply_requested": "false",
                "first_review_manual_review_blockers": (
                    "replacement_ligand_id,replacement_reference_binding_kcal_mol,"
                    "replacement_source,replacement_smiles,replacement_scaffold"
                ),
                "first_review_review_requirements": "operator confirmed replacement fields",
                "first_review_p0_slot_overlay_required_missing_fields": (
                    "replacement_ligand_id,replacement_reference_binding_kcal_mol,"
                    "replacement_source,replacement_smiles,replacement_scaffold"
                ),
                "first_review_p0_slot_overlay_claim_safe_step_ready": False,
                "first_review_p0_slot_overlay_authoritative_apply_allowed": False,
                "first_review_p0_slot_overlay_scope_promotion_allowed": False,
                "scope_operator_transfer_manifest_ready": True,
                "scope_operator_transfer_outbound_artifact_count": 8,
                "scope_operator_transfer_outbound_artifacts": [
                    "runs/product_scope_breadth_evidence_priority_packet_current.json",
                    "runs/transporter_local_crosscheck_triage_packet_current.json",
                    "runs/transporter_slot_assignment_candidate_workbook_current.json",
                    "runs/transporter_manual_review_intake_template_current.json",
                    "runs/transporter_manual_review_intake_template_current.csv",
                    "runs/transporter_binder_promotion_gate_current.json",
                    "runs/product_scope_breadth_contract_current.json",
                    "readable local crosscheck payloads referenced by local_crosscheck_paths",
                ],
                "scope_operator_transfer_inbound_artifact_count": 4,
                "scope_operator_transfer_inbound_artifacts": [
                    "completed runs/transporter_manual_review_intake_template_current.csv with OPERATOR_FILL placeholders resolved",
                    "completed runs/transporter_manual_review_intake_template_current.json if JSON review path is used",
                    "completed runs/pxr_exact_evidence_review_intake_template_current.csv with exact human NR1I2/PXR values",
                    "completed runs/pxr_exact_evidence_review_intake_template_current.json if JSON review path is used",
                ],
                "scope_operator_transfer_first_return_artifact": (
                    "completed runs/transporter_manual_review_intake_template_current.csv with OPERATOR_FILL placeholders resolved"
                ),
                "scope_operator_transfer_acceptance_artifact": (
                    "runs/product_scope_breadth_contract_current.json"
                ),
                "scope_operator_transfer_acceptance_ready_key": "scope_breadth_ready",
                "scope_operator_transfer_next_acceptance_stage": "transporter_claim_acceptance",
                "scope_operator_transfer_post_return_validation_command": (
                    "python3 tools/build_transporter_manual_review_intake_template.py && "
                    "python3 tools/build_transporter_binder_promotion_gate.py && "
                    "python3 tools/build_product_scope_breadth_evidence_priority_packet.py"
                ),
                "source_artifacts": [
                    "runs/product_scope_breadth_evidence_priority_packet_current.json",
                    "runs/transporter_manual_review_intake_template_current.json",
                ],
                "next_required_step": (
                    "Complete the AQP1 manual review template and rerun transporter scope gates."
                ),
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            },
            "rows": priority_rows,
        },
    )
    first_manual_review_row = {
        "row_id": "AQP1.core_non_binder_01",
        "item_id": "AQP1.core_non_binder_01",
        "target_id": "AQP1",
        "candidate_ligand_id": "chembl_chembl2179173",
        "replacement_source": (
            "chembl_activity::CHEMBL2179173::INHIBITION__%::source_CHEMBL4421726"
        ),
        "replacement_reference_binding_kcal_mol": "",
        "direct_binding_evidence_required": False,
        "direct_binding_source_url_or_doi": "",
        "negative_quantitative_value_required": True,
        "negative_reference_binding_kcal_mol": "",
        "review_decision": "KEEP_BLOCKED",
        "authoritative_apply_requested": "false",
        "manual_review_blockers": (
            "replacement_ligand_id,replacement_reference_binding_kcal_mol,"
            "replacement_source,replacement_smiles,replacement_scaffold"
        ),
        "p0_slot_overlay_required_missing_fields": (
            "replacement_ligand_id,replacement_reference_binding_kcal_mol,"
            "replacement_source,replacement_smiles,replacement_scaffold"
        ),
        "p0_slot_overlay_claim_safe_step_ready": False,
        "p0_slot_overlay_scope_promotion_allowed": False,
    }
    manual_review_rows = [first_manual_review_row] + [
        {
            **first_manual_review_row,
            "row_id": f"AQP1.review_{index:02d}",
            "item_id": f"AQP1.review_{index:02d}",
            "candidate_ligand_id": f"chembl_review_{index:02d}",
        }
        for index in range(2, 9)
    ]
    _write(
        runs_dir / "transporter_manual_review_intake_template_current.json",
        {
            "summary": {
                "packet_type": "transporter_manual_review_intake_template",
                "status": "transporter_manual_review_intake_template_ready",
                "manual_review_intake_ready": True,
                "scope_promotion_allowed": False,
                "authoritative_apply_allowed": False,
                "manual_review_template_row_count": 8,
                "expected_manual_review_row_count": 8,
                "manual_review_row_count_matches_workbook": True,
                "manual_confirmation_required_count": 8,
                "direct_binding_evidence_required_count": 1,
                "negative_quantitative_value_required_count": 6,
                "review_decision_placeholder_count": 0,
                "authoritative_apply_requested_placeholder_count": 0,
                "p0_slot_overlay_row_count": 8,
                "p0_slot_overlay_candidate_changed_count": 0,
                "p0_slot_overlay_first_item_id": "AQP1.core_non_binder_01",
                "p0_slot_overlay_first_candidate_ligand_id": "chembl_chembl2179173",
                "p0_slot_overlay_first_source": (
                    "chembl_activity::CHEMBL2179173::INHIBITION__%::source_CHEMBL4421726"
                ),
                "p0_slot_overlay_claim_safe_step_ready_count": 0,
                "first_review_row_id": "AQP1.core_non_binder_01",
                "first_review_item_id": "AQP1.core_non_binder_01",
                "first_review_target_id": "AQP1",
                "first_review_candidate_ligand_id": "chembl_chembl2179173",
                "first_review_replacement_source": (
                    "chembl_activity::CHEMBL2179173::INHIBITION__%::source_CHEMBL4421726"
                ),
                "first_review_replacement_reference_binding_kcal_mol": "",
                "first_review_direct_binding_evidence_required": False,
                "first_review_direct_binding_source_url_or_doi": "",
                "first_review_negative_quantitative_value_required": True,
                "first_review_negative_reference_binding_kcal_mol": "",
                "first_review_review_decision": "KEEP_BLOCKED",
                "first_review_authoritative_apply_requested": "false",
                "first_review_manual_review_blockers": (
                    "replacement_ligand_id,replacement_reference_binding_kcal_mol,"
                    "replacement_source,replacement_smiles,replacement_scaffold"
                ),
                "first_review_review_requirements": "operator confirmed replacement fields",
                "first_review_p0_slot_overlay_required_missing_fields": (
                    "replacement_ligand_id,replacement_reference_binding_kcal_mol,"
                    "replacement_source,replacement_smiles,replacement_scaffold"
                ),
                "first_review_p0_slot_overlay_claim_safe_step_ready": False,
                "first_review_p0_slot_overlay_authoritative_apply_allowed": False,
                "first_review_p0_slot_overlay_scope_promotion_allowed": False,
                "candidate_workbook_ready": True,
                "candidate_workbook_row_count": 8,
                "unique_review_row_ids_ready": True,
                "next_required_step": (
                    "Fill replacement ligand/source fields before transporter scope promotion."
                ),
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            },
            "rows": manual_review_rows,
        },
    )
    (runs_dir / "transporter_manual_review_intake_template_current.csv").write_text(
        "row_id,item_id,target_id,candidate_ligand_id,review_decision\n"
        + "\n".join(
            f"{row['row_id']},{row['item_id']},{row['target_id']},{row['candidate_ligand_id']},{row['review_decision']}"
            for row in manual_review_rows
        )
        + "\n",
        encoding="utf-8",
    )
    aqp1_candidate_row = {
        "candidate_id": "aqp1_operator_validation_chembl20_acetazolamide",
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "candidate_ligand_external_identifier": "CHEMBL20",
        "candidate_ligand_name": "acetazolamide",
        "candidate_activity_id": "29308926",
        "candidate_standard_type": "Kd",
        "candidate_standard_value_nM": "174000.0",
        "candidate_reference_binding_kcal_mol": "-5.13",
        "candidate_blocker": "data_validity_outside_typical_range_and_assay_origin_unknown",
        "candidate_claim_safe_ready": False,
        "candidate_source_locator": "chembl_activity::CHEMBL20::activity_29308926",
        "operator_assay_origin_confirmed": "OPERATOR_FILL_TRUE_OR_FALSE",
        "operator_data_validity_override": "OPERATOR_FILL_TRUE_OR_FALSE",
        "operator_claim_safe_decision": "OPERATOR_FILL_APPROVE_CLAIM_SAFE_OR_KEEP_BLOCKED",
        "operator_reviewed_by": "OPERATOR_FILL_REVIEWER",
        "operator_reviewed_at_utc": "OPERATOR_FILL_UTC_TIMESTAMP",
        "operator_approval_token": "OPERATOR_FILL_APPROVAL_TOKEN",
        "automated_public_recheck_ready": True,
        "automated_target_match_confirmed": True,
        "automated_endpoint_binding_like": True,
        "automated_endpoint_binding_like_confirmed": True,
        "automated_bacopaside_absence_confirmed": True,
        "automated_bindingdb_cutoff100_empty_confirmed": True,
        "automated_data_validity_blocker_present": True,
        "automated_assay_origin_unknown_blocker_present": True,
    }
    aqp1_required_operator_fields = [
        "operator_assay_origin_confirmed",
        "operator_data_validity_override",
        "operator_claim_safe_decision",
        "operator_reviewed_by",
        "operator_reviewed_at_utc",
        "operator_approval_token",
    ]
    aqp1_validation_blockers = [
        "data_validity_outside_typical_range",
        "assay_origin_unknown",
    ]
    _write(
        runs_dir / "aqp1_operator_validation_candidate_packet_current.json",
        {
            "summary": {
                "packet_type": "aqp1_operator_validation_candidate_packet",
                "status": "aqp1_operator_validation_candidate_packet_ready",
                "packet_ready": True,
                "candidate_ready": True,
                "candidate_count": 1,
                "candidate_claim_safe_ready_count": 0,
                "operator_validation_required_count": 1,
                "operator_placeholder_count": 6,
                "required_operator_decision_fields": aqp1_required_operator_fields,
                "required_operator_decision_field_count": 6,
                "validation_blockers": aqp1_validation_blockers,
                "validation_blocker_count": 2,
                "first_candidate_id": "aqp1_operator_validation_chembl20_acetazolamide",
                "first_candidate_target_id": "AQP1",
                "first_candidate_target_uniprot": "P29972",
                "first_candidate_ligand_external_identifier": "CHEMBL20",
                "first_candidate_ligand_name": "acetazolamide",
                "first_candidate_activity_id": "29308926",
                "first_candidate_standard_type": "Kd",
                "first_candidate_standard_value_nM": "174000.0",
                "first_candidate_reference_binding_kcal_mol": "-5.13",
                "first_candidate_blocker": "data_validity_outside_typical_range_and_assay_origin_unknown",
                "first_candidate_claim_safe_ready": False,
                "first_candidate_source_locator": "chembl_activity::CHEMBL20::activity_29308926",
                "return_bundle_required_artifacts": [
                    "runs/aqp1_operator_validation_candidate_packet_current.csv",
                    "runs/aqp1_direct_binding_procurement_packet_current.json",
                    "runs/product_scope_breadth_contract_current.json",
                ],
                "return_bundle_required_artifact_count": 3,
                "post_return_validation_commands": [
                    "python3 tools/product/build_aqp1_operator_validation_candidate_packet.py",
                    "python3 tools/product/build_aqp1_direct_binding_procurement_packet.py",
                    "python3 tools/build_product_scope_breadth_contract.py",
                ],
                "post_return_validation_command_count": 3,
                "claim_promotion_allowed": False,
                "authoritative_apply_allowed": False,
                "next_required_step": (
                    "Operator must keep CHEMBL20 blocked or provide claim-safe direct binding evidence."
                ),
                "claim_boundary": (
                    "AQP1 operator-validation candidate packet only; it does not approve claim-safe kcal, "
                    "promote transporter scope, run docking, or mutate external state."
                ),
            },
            "rows": [aqp1_candidate_row],
            "blockers": [
                {"code": "data_validity_outside_typical_range"},
                {"code": "assay_origin_unknown"},
            ],
        },
    )
    (runs_dir / "aqp1_operator_validation_candidate_packet_current.csv").write_text(
        "candidate_id,target_id,target_uniprot,candidate_ligand_external_identifier,"
        "candidate_ligand_name,candidate_activity_id,candidate_standard_type,"
        "candidate_standard_value_nM,candidate_reference_binding_kcal_mol,"
        "operator_claim_safe_decision\n"
        "aqp1_operator_validation_chembl20_acetazolamide,AQP1,P29972,CHEMBL20,"
        "acetazolamide,29308926,Kd,174000.0,-5.13,"
        "OPERATOR_FILL_APPROVE_CLAIM_SAFE_OR_KEEP_BLOCKED\n",
        encoding="utf-8",
    )
    _write(
        runs_dir / "aqp1_direct_binding_procurement_packet_current.json",
        {
            "summary": {
                "packet_type": "aqp1_direct_binding_procurement_packet",
                "status": "aqp1_direct_binding_procurement_packet_ready",
                "procurement_packet_ready": True,
                "target_id": "AQP1",
                "target_uniprot": "P29972",
                "current_direct_experimental_binding_row_count": 0,
                "current_claim_safe_binding_kcal_ready_count": 0,
                "direct_binding_gap_open": True,
                "public_direct_binding_recheck_ready": True,
                "public_direct_binding_recheck_result": (
                    "raw_activity_verified=True; bacopaside_absence=True; "
                    "bindingdb_cutoff100_empty=True"
                ),
                "current_operator_candidate_id": "aqp1_operator_validation_chembl20_acetazolamide",
                "current_operator_candidate_ligand_external_identifier": "CHEMBL20",
                "current_operator_candidate_reference_binding_kcal_mol": "-5.13",
                "current_operator_candidate_blocker": (
                    "data_validity_outside_typical_range_and_assay_origin_unknown"
                ),
                "current_operator_candidate_claim_safe_ready": False,
                "external_primary_evidence_required": True,
                "accepted_direct_binding_methods": ["Kd", "Ki", "SPR", "ITC", "radioligand"],
                "acceptance_fields": [
                    "target_id",
                    "target_uniprot",
                    "ligand_id",
                    "standard_type",
                    "standard_value_nM",
                    "reference_binding_kcal_mol",
                    "source_url_or_doi",
                    "operator_claim_safe_decision",
                ],
                "acceptance_field_count": 8,
                "minimum_acceptance_rule": (
                    "target_uniprot=P29972; standard_type in Kd,Ki; "
                    "source must support direct or operator-verified claim-safe binding kcal"
                ),
                "first_required_external_action_id": (
                    "procure_aqp1_bacopaside_ii_direct_binding_measurement"
                ),
                "post_return_validation_commands": [
                    "python3 tools/product/build_aqp1_direct_binding_procurement_packet.py",
                    "python3 tools/build_product_scope_breadth_contract.py",
                ],
                "post_return_validation_command_count": 2,
                "claim_promotion_allowed": False,
                "authoritative_apply_allowed": False,
                "next_required_step": (
                    "Procure or curate exact AQP1 direct-binding evidence before transporter claim promotion."
                ),
                "claim_boundary": (
                    "AQP1 procurement packet only; it records the direct-binding gap and does not run "
                    "experiments, approve claims, or mutate external state."
                ),
            },
            "rows": [
                {
                    "action_id": "reject_current_chembl20_candidate_for_claim_safe_apply",
                    "action_type": "operator_validation_rejection_guard",
                    "evidence_verdict": "keep_blocked",
                    "public_recheck_raw_activity_verified": True,
                    "public_recheck_bacopaside_absence_confirmed": True,
                    "public_recheck_bindingdb_cutoff100_empty_confirmed": True,
                    "public_absence_claim_supported": True,
                    "public_recheck_data_validity_blocker_present": True,
                    "public_recheck_assay_origin_unknown_blocker_present": True,
                },
                {
                    "action_id": "procure_aqp1_bacopaside_ii_direct_binding_measurement",
                    "action_type": "external_primary_evidence_request",
                    "target_id": "AQP1",
                    "target_uniprot": "P29972",
                },
                {
                    "action_id": "or_curate_claim_safe_replacement_aqp1_blocker",
                    "action_type": "replacement_reference_evidence_request",
                    "target_id": "AQP1",
                    "target_uniprot": "P29972",
                },
            ],
            "blockers": [
                {"code": "direct_binding_gap_open"},
                {"code": "operator_candidate_claim_safe_not_ready"},
            ],
        },
    )
    (runs_dir / "aqp1_direct_binding_procurement_packet_current.csv").write_text(
        "action_id,action_type,target_id,target_uniprot\n"
        "reject_current_chembl20_candidate_for_claim_safe_apply,"
        "operator_validation_rejection_guard,AQP1,P29972\n"
        "procure_aqp1_bacopaside_ii_direct_binding_measurement,"
        "external_primary_evidence_request,AQP1,P29972\n"
        "or_curate_claim_safe_replacement_aqp1_blocker,"
        "replacement_reference_evidence_request,AQP1,P29972\n",
        encoding="utf-8",
    )
    _write(
        runs_dir / "pxr_exact_evidence_review_intake_template_current.json",
        {
            "summary": {
                "packet_type": "pxr_exact_evidence_review_intake_template",
                "status": "pxr_exact_evidence_review_intake_template_ready",
                "pxr_exact_review_intake_ready": True,
                "scope_promotion_allowed": True,
                "authoritative_apply_allowed": False,
                "review_template_row_count": 0,
                "expected_blocked_row_count": 0,
                "review_row_count_matches_reconciliation": True,
                "binder_review_row_count": 0,
                "non_binder_review_row_count": 0,
                "conflict_resolution_required_count": 0,
                "kcal_placeholder_count": 0,
                "source_placeholder_count": 0,
                "target_match_placeholder_count": 0,
                "review_decision_placeholder_count": 0,
                "next_review_completion_packet_ready": False,
                "next_review_completion_packet": {"packet_ready": False},
                "next_review_return_bundle_required_artifacts": [],
                "next_review_return_bundle_required_artifact_count": 0,
                "next_review_return_bundle_completion_matrix": [],
                "next_review_return_bundle_completion_matrix_count": 0,
                "next_review_return_bundle_blocker_count": 0,
                "next_review_return_bundle_next_artifact_id": "",
                "next_review_return_bundle_next_artifact_path": "",
                "next_review_return_bundle_next_artifact_failed_check_ids": [],
                "next_review_row_id": "",
                "next_review_candidate_name": "",
                "next_review_packet_step": "",
                "next_review_required_evidence_mode": "",
                "next_review_operator_review_artifact": "",
                "reconciliation_packet_ready": True,
                "reconciliation_artifact": "runs/product_scope_breadth_contract_current.json",
                "unique_review_row_ids_ready": True,
                "next_required_step": "",
                "claim_boundary": (
                    "PXR exact review intake has no pending rows in the PR39 bootstrap fixture; "
                    "it does not authoritatively apply rows or mutate external state."
                ),
            },
            "rows": [],
        },
    )
    (runs_dir / "pxr_exact_evidence_review_intake_template_current.csv").write_text(
        "row_id,target_id,candidate_name,review_decision\n",
        encoding="utf-8",
    )
    _write(
        runs_dir / "product_scope_breadth_closure_checklist_current.json",
        {
            "summary": {
                "packet_type": "product_scope_breadth_closure_checklist",
                "status": "product_scope_breadth_closure_checklist_ready",
                "scope_breadth_ready": False,
                "closure_checklist_ready": True,
                "scope_promotion_allowed": False,
                "authoritative_apply_allowed": False,
                "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
                "allowed_scope_family_count": 3,
                "blocked_claim_scopes": [
                    "transporter_domain_promotion",
                    "general_protein_ligand_platform",
                ],
                "blocked_claim_scope_count": 2,
                "claim_blocked_domains": ["transporter", "idp_broad"],
                "general_platform_claim_allowed": False,
                "ready_for_apply_count": 0,
                "authoritative_apply_allowed_count": 0,
                "checklist_row_count": 1,
                "manual_review_blocked_row_count": 1,
                "manual_review_subcheck_count": 39,
                "field_missing_row_count": 1,
                "first_scientific_blocker": "AQP1.core_binder_01",
                "blocker_class_counts": {
                    "direct_binding_evidence_missing": 1,
                    "general_claim_gate": 4,
                },
                "blocker_classes": [
                    "direct_binding_evidence_missing",
                    "general_claim_gate",
                ],
                "transporter_manual_review_subcheck_count": 39,
                "transporter_identity_scaffold_confirmation_required_count": 1,
                "transporter_direct_binding_or_kcal_confirmation_required_count": 1,
                "transporter_negative_quantitative_confirmation_required_count": 6,
                "transporter_direct_binding_missing_count": 1,
                "transporter_negative_quantitative_missing_count": 6,
                "transporter_candidate_ready_for_apply_count": 0,
                "pxr_reconciled_blocked_row_count": 0,
                "pxr_conflict_resolution_count": 0,
                "pxr_quantitative_missing_count": 0,
                "general_claim_blocker_count": 4,
                "general_claim_gate_blocker_count": 4,
                "claim_boundary_detail": (
                    "restricted scope remains allowed for gpcr, ion_channel, and kinase; "
                    "transporter and broad platform claims remain blocked."
                ),
                "claim_boundary_matrix": [
                    {"claim_scope": "transporter_domain_promotion", "allowed": False},
                    {"claim_scope": "idp_broad", "allowed": False},
                    {"claim_scope": "general_protein_ligand_platform", "allowed": False},
                    {"claim_scope": "authoritative_apply", "allowed": False},
                ],
                "source_artifacts": [
                    "runs/product_scope_breadth_contract_current.json",
                    "runs/product_scope_breadth_evidence_priority_packet_current.json",
                ],
                "first_blocked_evidence_row_id": "AQP1.core_binder_01",
                "next_operator_completion_slot_id": "AQP1.core_binder_01",
                "transporter_p0_evidence_acquisition_next_slot_id": "AQP1.core_binder_01",
                "evidence_queue_next_operator_completion_slot_id": "AQP1.core_binder_01",
                "next_required_step": (
                    "Resolve the AQP1 manual review packet before transporter scope promotion."
                ),
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            },
            "rows": [
                {
                    "item_id": "AQP1.core_binder_01",
                    "domain": "transporter",
                    "ready_for_apply": False,
                    "blocker_class": "direct_binding_evidence_missing",
                    "manual_review_subchecks": "direct_binding_source_url_or_doi=false;replacement_reference_binding_kcal_mol=false",
                }
            ],
        },
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
    _write(
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
        runs_dir / "cleanup_execution_approval_gate_current.json",
        {
            "summary": {
                "status": "cleanup_execution_operator_approval_gate_ready",
                "payload_lock_required": True,
                "operator_approval_csv_present": True,
                "approval_row_count": 5,
                "authorized_row_count": 5,
                "skipped_row_count": 0,
                "awaiting_operator_approval_row_count": 0,
                "blocked_row_count": 0,
                "protected_not_promoted_row_count": 0,
                "authorized_reclaim_size_gb": 49.216,
                "total_reclaim_size_gb": 49.216,
                "protected_payload_size_gb": 0.0,
                "operator_template_csv": "runs/cleanup_execution_operator_approval_template_current.csv",
                "operator_approval_csv": "runs/cleanup_execution_operator_approval_intake.csv",
                "blocker_count": 0,
                "blockers": [],
                "execution_enabled": False,
                "delete_executed": False,
                "external_state_mutated": False,
                "claim_boundary": "CI fixture cleanup approval gate only; it records prior operator-approved cleanup receipts and does not delete, move, archive, externalize, upload, or mutate external state.",
            },
            "rows": [
                {
                    "lane": f"cleanup_fixture_lane_{index}",
                    "recommended_action": "delete_candidate",
                    "path": f"runs/cleanup_fixture_payload_{index}",
                    "approval_token_required": "APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS",
                    "approval_gate_status": "authorized_for_operator_execution",
                }
                for index in range(1, 6)
            ],
        },
    )
    _write(
        runs_dir / "cleanup_postcheck_contract_current.json",
        {
            "summary": {
                "status": "cleanup_postcheck_contract_ready",
                "postcheck_contract_ready": True,
                "row_count": 5,
                "approval_row_count": 5,
                "protected_policy_row_count": 0,
                "blocked_row_count": 0,
                "blocker_count": 0,
                "approval_reclaim_size_gb": 49.216,
                "protected_payload_size_gb": 0.0,
                "global_refresh_command_count": 9,
                "global_refresh_commands": ["python3 tools/build_goal_release_decision_gate.py"],
                "delete_executed": False,
                "archive_executed": False,
                "externalize_executed": False,
                "external_state_mutated": False,
                "claim_boundary": "CI fixture cleanup postcheck contract only; it records prior cleanup verification and does not delete, move, archive, externalize, upload, or mutate external state.",
            },
            "rows": [
                {
                    "lane": f"cleanup_fixture_lane_{index}",
                    "operation_class": "delete_candidate",
                    "postcheck_status": "pass",
                    "blocked": False,
                }
                for index in range(1, 6)
            ],
            "blockers": [],
        },
    )
    _write(
        runs_dir / "cleanup_completion_gate_current.json",
        {
            "summary": {
                "status": "cleanup_completion_gate_ready",
                "cleanup_complete": True,
                "stage_count": 5,
                "authorized_reclaim_size_gb": 49.216,
                "total_reclaim_size_gb": 49.216,
                "protected_payload_size_gb": 0.0,
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
        runs_dir / "large_cleanup_surface_drilldown_current.json",
        {
            "summary": {
                "status": "large_cleanup_surface_drilldown_ready",
                "known_payload_row_count": 0,
                "known_payload_total_size_gb": 0.0,
                "dry_run_delete_payload_row_count": 0,
                "dry_run_delete_payload_size_gb": 0.0,
                "dry_run_protected_payload_row_count": 0,
                "dry_run_protected_payload_size_gb": 0.0,
                "delete_executed": False,
                "external_state_mutated": False,
                "claim_boundary": "CI fixture cleanup drilldown only; it does not delete, move, archive, externalize, upload, or mutate external state.",
            },
            "rows": [],
        },
    )
    _write(
        runs_dir / "protected_cleanup_payload_review_current.json",
        {
            "summary": {
                "status": "protected_cleanup_payload_review_ready",
                "protected_payload_row_count": 0,
                "protected_payload_size_gb": 0.0,
                "delete_executed": False,
                "external_state_mutated": False,
            },
            "rows": [],
        },
    )
    _write(
        runs_dir / "protected_ligand_heavy_payload_deep_review_current.json",
        {
            "summary": {
                "status": "protected_ligand_heavy_payload_deep_review_ready",
                "known_payload_child_count": 0,
                "known_payload_child_size_gb": 0.0,
                "preservation_sibling_count": 0,
                "preservation_sibling_size_gb": 0.0,
                "largest_known_payload_child_size_gb": 0.0,
                "policy_change_required_for_deletion_count": 0,
                "approval_promoted_count": 0,
                "blocker_count": 0,
                "delete_executed": False,
                "external_state_mutated": False,
                "claim_boundary": "CI fixture protected ligand-heavy review only; it does not promote protected rows, delete, move, archive, externalize, upload, or mutate external state.",
            },
            "rows": [],
        },
    )
    _write(
        runs_dir / "protected_cleanup_policy_decision_gate_current.json",
        {
            "summary": {
                "status": "protected_cleanup_policy_decision_gate_ready",
                "policy_resolved": True,
                "approval_promoted": False,
                "protected_payload_row_count": 0,
                "protected_payload_size_gb": 0.0,
                "known_payload_child_count": 0,
                "known_payload_child_size_gb": 0.0,
                "preservation_sibling_count": 0,
                "policy_change_required_for_deletion_count": 0,
                "awaiting_policy_decision_row_count": 0,
                "blocked_row_count": 0,
                "operator_policy_csv_present": True,
                "operator_template_csv": "runs/protected_cleanup_policy_operator_template_current.csv",
                "operator_policy_csv": "runs/protected_cleanup_policy_operator_intake.csv",
                "delete_executed": False,
                "external_state_mutated": False,
                "claim_boundary": "CI fixture protected cleanup policy gate only; it does not promote protected rows, delete, move, archive, externalize, upload, or mutate external state.",
            },
            "rows": [],
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
    license_template = runs_dir / "product_license_decision_operator_template_current.csv"
    license_intake = runs_dir / "product_license_decision_operator_intake.csv"
    license_header = (
        "operator_decision,spdx_license_id,license_text_source,copyright_holder,"
        "effective_year,approval_token,operator_note\n"
    )
    license_template.parent.mkdir(parents=True, exist_ok=True)
    license_template.write_text(license_header, encoding="utf-8")
    license_intake.write_text(
        license_header
        + "create_license_file,ProprietaryRef-Betelgeuze,LICENSE,JIHOON KANG,"
        "2026,APPROVE_PRODUCT_LICENSE_FILE_CREATION,CI fixture license review only\n",
        encoding="utf-8",
    )
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
        runs_dir / "product_license_decision_packet_current.json",
        {
            "summary": {
                "packet_type": "product_license_decision_packet",
                "status": "product_license_decision_packet_ready",
                "option_count": 1,
                "blocker_count": 0,
                "hard_blocker_count": 0,
                "review_item_count": 1,
                "commercial_gate_only_license_blocked": False,
                "commercial_independence_ready": True,
                "license_decision_gate_status": "product_license_decision_gate_ready",
                "license_decision_gate_ready": True,
                "license_decision_authorized_for_file_creation_review": True,
                "operator_template_csv": "runs/product_license_decision_operator_template_current.csv",
                "operator_intake_csv": "runs/product_license_decision_operator_intake.csv",
                "operator_intake_csv_present": True,
                "required_fields": [
                    "operator_decision",
                    "spdx_license_id",
                    "license_text_source",
                    "copyright_holder",
                    "effective_year",
                    "approval_token",
                ],
                "required_decision": "create_license_file",
                "approval_token_required": "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
                "license_present": True,
                "legal_advice_provided": False,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            },
            "rows": [
                {
                    "decision_id": "create_license_file",
                    "required_decision": "create_license_file",
                    "spdx_license_id": "ProprietaryRef-Betelgeuze",
                    "license_text_source": "LICENSE",
                    "operator_review_required": True,
                    "approval_token_required": "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
                    "legal_advice_provided": False,
                    "external_state_mutated": False,
                }
            ],
            "blockers": [],
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
