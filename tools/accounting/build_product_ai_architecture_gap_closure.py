#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_JSON = "runs/residual_model_registry_current.json"
DEFAULT_E2E_JSON = "runs/product_end_to_end_rocm_benchmark_current.json"
DEFAULT_SERVICE_BOUNDARY_JSON = "runs/product_service_boundary_contract_current.json"
DEFAULT_API_CONTRACT_JSON = "runs/product_api_contract_current.json"
DEFAULT_JOB_ORCHESTRATION_JSON = "runs/product_job_orchestration_contract_current.json"
DEFAULT_CAPABILITY_JSON = "runs/product_capability_surface_contract_current.json"
DEFAULT_DECISION_GRAPH_JSON = "runs/product_ai_decision_graph_contract_current.json"
DEFAULT_REPORT_UX_JSON = "runs/product_ai_report_ux_contract_current.json"
DEFAULT_SECURITY_DEPLOYMENT_JSON = "runs/product_security_deployment_contract_current.json"
DEFAULT_TRAJECTORY_SLA_JSON = "runs/product_trajectory_sla_contract_current.json"
DEFAULT_SCOPE_BREADTH_JSON = "runs/product_scope_breadth_contract_current.json"
DEFAULT_TRAINING_DATA_JSON = "runs/residual_production_training_data_contract_current.json"
DEFAULT_PRODUCTION_AI_CHECKPOINT_READINESS_JSON = "runs/product_production_ai_checkpoint_readiness_current.json"
DEFAULT_OUT_JSON = "runs/product_ai_architecture_gap_closure_current.json"
DEFAULT_OUT_CSV = "runs/product_ai_architecture_gap_closure_current.csv"
DEFAULT_OUT_MD = "runs/product_ai_architecture_gap_closure_current.md"

CLAIM_BOUNDARY = (
    "Product AI architecture gap closure only; audits local evidence for production AI inference, closed-loop "
    "structure/docking analysis, job orchestration, production trajectory SLA, scope breadth, report UX, and "
    "security/deployment operations. It does not train models, run docking, promote production mode, start servers, "
    "upload, submit, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> bool:
    return bool(value is True)


GPU_ENVIRONMENT_UNLOCK_FIELDS = [
    "manifest_ready",
    "rocm_stack_detected",
    "torch_rocm_ready",
    "amd_gpu_detected",
    "visible_device_count",
]


def _row(
    gap_id: str,
    domain: str,
    status: str,
    evidence: str,
    observed: str,
    close_requirement: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "gap_id": gap_id,
        "domain": domain,
        "status": status,
        "evidence": evidence,
        "observed": observed,
        "close_requirement": close_requirement,
        "next_action": next_action,
        "release_blocker": status != "closed",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def _first_scope_blocker(scope_breadth: dict[str, Any], scope_breadth_path: str) -> dict[str, Any]:
    next_stage_id = _text(
        scope_breadth.get("scope_acceptance_next_stage_id")
        or scope_breadth.get("scope_claim_expansion_current_next_stage_id")
        or "scope_breadth_acceptance"
    )
    if next_stage_id == "transporter_claim_acceptance":
        packet = scope_breadth.get("transporter_p0_evidence_acquisition_next_slot_completion_packet")
        packet = packet if isinstance(packet, dict) else {}
        slot_id = _text(scope_breadth.get("transporter_p0_evidence_acquisition_next_slot_id") or packet.get("slot_id"))
        return {
            "primary_blocker_id": slot_id or "transporter_claim_acceptance",
            "blocker_stage_id": next_stage_id,
            "blocker_artifact": _text(
                scope_breadth.get("transporter_p0_evidence_acquisition_next_slot_operator_review_artifact")
                or scope_breadth.get("scope_acceptance_next_stage_artifact")
                or scope_breadth_path
            ),
            "observed": (
                f"transporter_unresolved_slots={scope_breadth.get('transporter_p0_evidence_acquisition_unresolved_slot_count')};"
                f"direct_binding_required={scope_breadth.get('transporter_manual_review_direct_binding_evidence_required_count')};"
                f"negative_value_required={scope_breadth.get('transporter_manual_review_negative_quantitative_value_required_count')};"
                f"next_slot_id={slot_id}"
            ),
            "required": "exact target-pair transporter evidence resolves the next open P0 slot without broadening claims",
            "next_action": _text(
                packet.get("next_action")
                or scope_breadth.get("transporter_p0_evidence_acquisition_first_next_required_action")
                or scope_breadth.get("scope_acceptance_next_stage_next_action")
            ),
            "validation_command": _text(
                scope_breadth.get("scope_acceptance_next_stage_validation_command")
                or "python3 tools/build_product_scope_breadth_contract.py"
            ),
            "operator_input_fields": [
                str(item) for item in (packet.get("required_operator_intake_columns") or [])
            ],
            "required_exact_evidence_fields": [
                str(item) for item in (packet.get("required_exact_evidence_fields") or [])
            ],
            "required_claim_guardrails": [
                str(item) for item in (packet.get("required_claim_guardrails") or [])
            ],
            "claim_safe_completion_rule": _text(packet.get("completion_rule")),
            "source_modality_triage_artifact": _text(
                scope_breadth.get(
                    "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_artifact"
                )
            ),
            "source_modality_triage_decision": _text(
                scope_breadth.get(
                    "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_decision"
                )
            ),
            "source_modality_direct_experimental_binding_row_count": _int(
                scope_breadth.get(
                    "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_experimental_binding_row_count"
                )
            ),
            "source_modality_claim_safe_binding_kcal_ready_count": _int(
                scope_breadth.get(
                    "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count"
                )
            ),
            "source_modality_computational_binding_energy_row_count": _int(
                scope_breadth.get(
                    "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_computational_binding_energy_row_count"
                )
            ),
            "source_modality_best_computational_binding_energy_kcal_mol": _text(
                scope_breadth.get(
                    "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol"
                )
            ),
            "parallelizable_workstream": True,
            "unlock_claim": "transporter_domain_promotion",
        }
    if next_stage_id == "pxr_claim_acceptance":
        packet = scope_breadth.get("pxr_exact_review_next_review_completion_packet")
        packet = packet if isinstance(packet, dict) else {}
        row_id = _text(scope_breadth.get("pxr_exact_review_next_review_row_id") or packet.get("review_row_id"))
        return {
            "primary_blocker_id": row_id or "pxr_claim_acceptance",
            "blocker_stage_id": next_stage_id,
            "blocker_artifact": _text(
                scope_breadth.get("pxr_exact_review_next_review_operator_review_artifact")
                or scope_breadth.get("scope_acceptance_next_stage_artifact")
                or scope_breadth_path
            ),
            "observed": (
                f"pxr_conflict_required={scope_breadth.get('pxr_exact_review_conflict_resolution_required_count')};"
                f"pxr_kcal_placeholders={scope_breadth.get('pxr_exact_review_kcal_placeholder_count')};"
                f"next_review_row_id={row_id}"
            ),
            "required": "exact human NR1I2/PXR quantitative review row is reconciled before PXR claim promotion",
            "next_action": _text(scope_breadth.get("scope_acceptance_next_stage_next_action") or scope_breadth.get("next_required_step")),
            "validation_command": _text(
                scope_breadth.get("scope_acceptance_next_stage_validation_command")
                or "python3 tools/build_pxr_exact_evidence_review_intake_template.py"
            ),
            "operator_input_fields": [
                str(item) for item in (packet.get("required_operator_intake_columns") or [])
            ],
            "required_exact_evidence_fields": [
                str(item) for item in (packet.get("required_exact_evidence_fields") or [])
            ],
            "required_claim_guardrails": [
                str(item) for item in (packet.get("required_claim_guardrails") or [])
            ],
            "claim_safe_completion_rule": _text(packet.get("completion_rule")),
            "parallelizable_workstream": True,
            "unlock_claim": "pxr_domain_promotion",
        }
    return {
        "primary_blocker_id": next_stage_id,
        "blocker_stage_id": next_stage_id,
        "blocker_artifact": _text(
            scope_breadth.get("scope_claim_expansion_current_next_stage_artifact")
            or scope_breadth.get("scope_acceptance_next_stage_artifact")
            or scope_breadth_path
        ),
        "observed": (
            f"blocked_claim_scopes={','.join(str(item) for item in scope_breadth.get('blocked_claim_scopes') or [])};"
            f"missing_domains={','.join(str(item) for item in scope_breadth.get('missing_domains') or [])}"
        ),
        "required": "all scope acceptance stages are green before any general protein-ligand platform claim",
        "next_action": _text(scope_breadth.get("scope_claim_expansion_current_next_stage_validation_command") or scope_breadth.get("next_required_step")),
        "validation_command": _text(
            scope_breadth.get("scope_claim_expansion_current_next_stage_validation_command")
            or "python3 tools/build_product_scope_breadth_contract.py"
        ),
        "operator_input_fields": [str(item) for item in (scope_breadth.get("scope_claim_expansion_current_blocked_stage_ids") or [])],
        "parallelizable_workstream": True,
        "unlock_claim": "general_protein_ligand_platform",
    }


def _gap_blocker_matrix(
    *,
    open_rows: list[dict[str, Any]],
    production_ai_checkpoint: dict[str, Any],
    scope_breadth: dict[str, Any],
    scope_breadth_path: str,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    open_gap_ids = {row["gap_id"] for row in open_rows}
    if "production_ai_inference_checkpoint" in open_gap_ids:
        primary_blocker_id = _text(
            production_ai_checkpoint.get("production_inference_actionable_blocker_check_id")
            or "production_checkpoint_preflight"
        )
        operator_input_fields = [
            str(item)
            for item in (
                production_ai_checkpoint.get("production_inference_actionable_blocker_unlock_fields")
                or []
            )
        ]
        if not operator_input_fields and primary_blocker_id == "production_gpu_execution_environment_ready":
            operator_input_fields = list(GPU_ENVIRONMENT_UNLOCK_FIELDS)
        blockers.append(
            {
                "gap_id": "production_ai_inference_checkpoint",
                "primary_blocker_id": primary_blocker_id,
                "blocker_stage_id": _text(
                    production_ai_checkpoint.get("production_inference_actionable_blocker_stage_id")
                    or production_ai_checkpoint.get("production_inference_acceptance_next_stage_id")
                    or "production_inference_acceptance"
                ),
                "blocker_artifact": _text(
                    production_ai_checkpoint.get("production_inference_actionable_blocker_artifact")
                    or production_ai_checkpoint.get("production_inference_acceptance_next_stage_artifact")
                    or DEFAULT_PRODUCTION_AI_CHECKPOINT_READINESS_JSON
                ),
                "observed": _text(
                    production_ai_checkpoint.get("production_inference_actionable_blocker_observed")
                    or f"production_ai_checkpoint_ready={production_ai_checkpoint.get('production_ai_checkpoint_ready')}"
                ),
                "required": _text(
                    production_ai_checkpoint.get("production_inference_actionable_blocker_required")
                    or "production AI checkpoint readiness acceptance matrix is green"
                ),
                "next_action": _text(
                    production_ai_checkpoint.get("production_gpu_rocm_next_required_step")
                    or production_ai_checkpoint.get("production_inference_actionable_blocker_next_action")
                    or production_ai_checkpoint.get("next_required_step")
                ),
                "validation_command": _text(
                    production_ai_checkpoint.get("production_inference_actionable_blocker_validation_command")
                    or "python3 tools/build_product_production_ai_checkpoint_readiness.py"
                ),
                "operator_input_fields": operator_input_fields,
                "next_after_blocker_stage_id": _text(
                    production_ai_checkpoint.get("production_inference_next_after_actionable_blocker_stage_id")
                ),
                "next_after_blocker_artifact": _text(
                    production_ai_checkpoint.get("production_inference_next_after_actionable_blocker_artifact")
                ),
                "next_after_blocker_validation_command": _text(
                    production_ai_checkpoint.get(
                        "production_inference_next_after_actionable_blocker_validation_command"
                    )
                ),
                "next_after_blocker_next_action": _text(
                    production_ai_checkpoint.get(
                        "production_inference_next_after_actionable_blocker_next_action"
                    )
                ),
                "next_after_blocker_required_checks": [
                    str(item)
                    for item in (
                        production_ai_checkpoint.get(
                            "production_inference_next_after_actionable_blocker_required_checks"
                        )
                        or []
                    )
                ],
                "next_after_blocker_unlock_fields": [
                    str(item)
                    for item in (
                        production_ai_checkpoint.get(
                            "production_inference_next_after_actionable_blocker_unlock_fields"
                        )
                        or []
                    )
                ],
                "parallelizable_workstream": False,
                "unlock_claim": "production_ai_inference_subject",
            }
        )
    if "scope_breadth_expansion" in open_gap_ids:
        scope_blocker = _first_scope_blocker(scope_breadth, scope_breadth_path)
        blockers.append({"gap_id": "scope_breadth_expansion", **scope_blocker})
    return blockers


def build_product_ai_architecture_gap_closure(
    *,
    registry_packet: dict[str, Any],
    e2e_packet: dict[str, Any],
    service_boundary_packet: dict[str, Any],
    api_contract_packet: dict[str, Any],
    capability_packet: dict[str, Any],
    job_orchestration_packet: dict[str, Any] | None = None,
    decision_graph_packet: dict[str, Any] | None = None,
    report_ux_packet: dict[str, Any] | None = None,
    security_deployment_packet: dict[str, Any] | None = None,
    trajectory_sla_packet: dict[str, Any] | None = None,
    scope_breadth_packet: dict[str, Any] | None = None,
    training_data_packet: dict[str, Any] | None = None,
    production_ai_checkpoint_readiness_packet: dict[str, Any] | None = None,
    registry_path: str = DEFAULT_REGISTRY_JSON,
    e2e_path: str = DEFAULT_E2E_JSON,
    service_boundary_path: str = DEFAULT_SERVICE_BOUNDARY_JSON,
    api_contract_path: str = DEFAULT_API_CONTRACT_JSON,
    job_orchestration_path: str = DEFAULT_JOB_ORCHESTRATION_JSON,
    capability_path: str = DEFAULT_CAPABILITY_JSON,
    decision_graph_path: str = DEFAULT_DECISION_GRAPH_JSON,
    report_ux_path: str = DEFAULT_REPORT_UX_JSON,
    security_deployment_path: str = DEFAULT_SECURITY_DEPLOYMENT_JSON,
    trajectory_sla_path: str = DEFAULT_TRAJECTORY_SLA_JSON,
    scope_breadth_path: str = DEFAULT_SCOPE_BREADTH_JSON,
    training_data_path: str = DEFAULT_TRAINING_DATA_JSON,
    production_ai_checkpoint_readiness_path: str = DEFAULT_PRODUCTION_AI_CHECKPOINT_READINESS_JSON,
) -> dict[str, Any]:
    registry = _summary(registry_packet)
    e2e = _summary(e2e_packet)
    service = _summary(service_boundary_packet)
    api = _summary(api_contract_packet)
    job_contract = _summary(job_orchestration_packet or {})
    capability = _summary(capability_packet)
    decision_graph = _summary(decision_graph_packet or {})
    report_ux = _summary(report_ux_packet or {})
    security = _summary(security_deployment_packet or {})
    trajectory_sla = _summary(trajectory_sla_packet or {})
    scope_breadth = _summary(scope_breadth_packet or {})
    training_data = _summary(training_data_packet or {})
    production_ai_checkpoint = _summary(production_ai_checkpoint_readiness_packet or {})

    production_ai_ready = (
        _bool(registry.get("product_model_layer_ready"))
        and _int(registry.get("trained_model_checkpoint_count")) > 0
        and _bool(registry.get("production_promotion_allowed"))
        and _bool(registry.get("customer_facing_auto_correction_allowed"))
        and _bool(registry.get("customer_facing_score_mutation_allowed"))
        and _bool(registry.get("customer_facing_ranking_mutation_allowed"))
        and _text(registry.get("default_residual_mode")) in {"assist", "production", "production_guarded"}
        and _bool(training_data.get("production_training_data_ready"))
    )
    closed_loop_ready = (
        _bool(decision_graph.get("closed_loop_decision_graph_ready"))
        and _bool(decision_graph.get("structure_quality_node_ready"))
        and _bool(decision_graph.get("binding_site_node_ready"))
        and _bool(decision_graph.get("pose_generation_node_ready"))
        and _bool(decision_graph.get("scoring_node_ready"))
        and _bool(decision_graph.get("uncertainty_abstention_node_ready"))
        and _bool(decision_graph.get("report_node_ready"))
        and _bool(decision_graph.get("customer_report_ux_node_ready"))
        and _bool(decision_graph.get("viewer_interaction_surface_ready"))
        and _bool(decision_graph.get("customer_report_card_ready"))
        and _bool(decision_graph.get("interaction_rationale_ready"))
        and _bool(decision_graph.get("counterfactual_rescue_suggestion_ready"))
        and _bool(decision_graph.get("evidence_traceability_ready"))
        and _bool(decision_graph.get("fail_closed_transition_ready"))
        and _int(decision_graph.get("ready_edge_count")) >= _int(decision_graph.get("required_edge_count"))
        and _int(decision_graph.get("required_edge_count")) > 0
    )
    job_orchestration_ready = (
        _text(service.get("status")) == "product_service_boundary_contract_ready"
        and _bool(service.get("service_boundary_ready"))
        and _int(service.get("missing_api_route_count")) == 0
        and _int(service.get("api_route_count")) >= 21
        and _text(api.get("status")) == "product_api_contract_ready"
        and _bool(api.get("api_contract_ready"))
        and _int(api.get("missing_route_count")) == 0
        and _int(api.get("expected_route_count")) >= 21
        and _text(job_contract.get("status")) == "product_job_orchestration_contract_ready"
        and _bool(job_contract.get("product_job_orchestration_contract_ready"))
        and _bool(job_contract.get("retry_child_attempt_created"))
        and _bool(job_contract.get("idempotency_preserved"))
        and _bool(job_contract.get("progress_fields_present"))
        and _bool(job_contract.get("listed_status_progress_contract_ready"))
        and _bool(job_contract.get("queue_lifecycle_progress_ready"))
        and _bool(job_contract.get("customer_run_history_lineage_ready"))
        and _bool(job_contract.get("status_snapshot_persistence_ready"))
        and _bool(job_contract.get("rerun_manifest_ready"))
        and _bool(job_contract.get("retention_policy_ready"))
        and _bool(job_contract.get("long_running_status_persistence_ready"))
        and _bool(job_contract.get("worker_backend_contract_ready"))
        and _bool(job_contract.get("worker_lease_heartbeat_ready"))
        and _bool(job_contract.get("retryable_failure_resume_ready"))
        and _bool(job_contract.get("running_cancel_ack_ready"))
    )
    production_sla_ready = (
        (
            _text(e2e.get("status")) == "product_end_to_end_rocm_benchmark_ready"
            and _bool(e2e.get("benchmark_ready"))
            and _bool(e2e.get("production_trajectory_profile_enabled"))
            and _float(e2e.get("jobs_per_hour")) > 0
            and _float(e2e.get("unique_ligands_per_hour")) > 0
            and _float(e2e.get("failure_rate")) <= 0.05
        )
        or (
            _text(trajectory_sla.get("status")) == "product_trajectory_sla_contract_ready"
            and _bool(trajectory_sla.get("production_trajectory_sla_ready"))
            and _int(trajectory_sla.get("qualified_ready_run_count")) >= _int(trajectory_sla.get("minimum_ready_run_count"))
            and _int(trajectory_sla.get("minimum_ready_rows_per_family")) >= 10000
            and _float(trajectory_sla.get("min_throughput_rows_per_sec")) > 0
            and _float(trajectory_sla.get("max_failure_rate")) <= 0.05
            and _text(trajectory_sla.get("sla_claim_tier")) == "restricted_family_sla"
            and _bool(trajectory_sla.get("restricted_family_sla_allowed"))
            and not _bool(trajectory_sla.get("broad_platform_sla_allowed"))
            and _bool(trajectory_sla.get("restricted_sla_backed_by_historical_profile_artifacts"))
            and _bool(trajectory_sla.get("rocm_baseline_profile_gap_acknowledged"))
            and not _bool(trajectory_sla.get("current_rocm_baseline_supports_broad_platform_sla"))
            and not trajectory_sla.get("missing_qualified_families")
        )
    )
    allowed_families = capability.get("allowed_scope_families") or []
    blocked_claim_scopes = [str(item) for item in scope_breadth.get("blocked_claim_scopes") or []]
    scope_ready = (
        _text(scope_breadth.get("status")) == "product_scope_breadth_contract_ready"
        and _bool(scope_breadth.get("scope_breadth_ready"))
        and _bool(scope_breadth.get("scope_claim_posture_ready"))
        and _bool(scope_breadth.get("general_platform_claim_allowed"))
        and not blocked_claim_scopes
    )
    missing_scope_domains = [str(item) for item in scope_breadth.get("missing_domains") or []]
    if scope_ready:
        scope_next_action = "Scope breadth contract is ready; widen platform wording only through an explicit product decision."
    elif blocked_claim_scopes:
        scope_next_action = f"Keep broad claims blocked at the product surface: {','.join(blocked_claim_scopes)}."
    elif missing_scope_domains:
        scope_next_action = (
            "Keep broad claims blocked until the remaining scope domains are green: "
            f"{','.join(missing_scope_domains)}."
        )
    else:
        scope_next_action = "Keep broad claims blocked until the scope breadth contract is green."
    report_ux_ready = (
        _bool(report_ux.get("ai_report_ux_ready"))
        and _bool(report_ux.get("binding_site_explanation_ready"))
        and _bool(report_ux.get("pose_comparison_ready"))
        and _bool(report_ux.get("interaction_rationale_ready"))
        and _bool(report_ux.get("viewer_interaction_surface_ready"))
        and _bool(report_ux.get("uncertainty_narrative_ready"))
        and _bool(report_ux.get("counterfactual_rescue_suggestion_ready"))
        and _bool(report_ux.get("structured_customer_report_ready"))
        and _bool(report_ux.get("customer_report_delivery_contract_ready"))
        and _bool(report_ux.get("customer_report_evidence_binding_ready"))
        and _bool(report_ux.get("customer_report_viewer_binding_ready"))
        and _bool(report_ux.get("viewer_customer_report_binding_ready"))
        and _int(report_ux.get("customer_report_required_block_count")) > 0
        and _int(report_ux.get("customer_report_ready_block_count"))
        == _int(report_ux.get("customer_report_required_block_count"))
        and _int(report_ux.get("customer_report_blocked_block_count")) == 0
        and _bool(report_ux.get("customer_report_card_ready"))
        and _bool(report_ux.get("evidence_traceability_ready"))
        and bool(_text(report_ux.get("ranking_score_col")))
        and bool(_text(report_ux.get("primary_abstention_reason")))
        and bool(_text(report_ux.get("what_would_change_decision")))
    )
    security_ready = (
        _bool(security.get("security_deployment_ready"))
        and _bool(security.get("auth_ready"))
        and _bool(security.get("tenant_isolation_ready"))
        and _bool(security.get("rate_limit_ready"))
        and _bool(security.get("payload_limit_ready"))
        and _bool(security.get("path_allowlist_ready"))
        and _bool(security.get("audit_log_ready"))
        and _bool(security.get("hosted_external_exposure_guard_ready"))
        and not _bool(security.get("hosted_external_exposure_allowed"))
        and _bool(security.get("sbom_ready"))
        and _bool(security.get("container_image_ready"))
        and _bool(security.get("metrics_endpoint_ready"))
        and _bool(security.get("rollback_ready"))
    )

    rows = [
        _row(
            "production_ai_inference_checkpoint",
            "ai_inference",
            "closed" if production_ai_ready else "open",
            f"{registry_path};{training_data_path}",
            (
                f"product_model_layer_ready={registry.get('product_model_layer_ready')};"
                f"default_residual_mode={registry.get('default_residual_mode')};"
                f"production_promotion_allowed={registry.get('production_promotion_allowed')};"
                f"customer_facing_auto_correction_allowed={registry.get('customer_facing_auto_correction_allowed')};"
                f"customer_facing_score_mutation_allowed={registry.get('customer_facing_score_mutation_allowed')};"
                f"customer_facing_ranking_mutation_allowed={registry.get('customer_facing_ranking_mutation_allowed')};"
                f"checkpoint_preflight_ready={registry.get('checkpoint_preflight_ready')};"
                f"candidate_checkpoint_count={registry.get('candidate_checkpoint_count')};"
                f"trained_model_checkpoint_count={registry.get('trained_model_checkpoint_count')};"
                f"production_training_data_ready={training_data.get('production_training_data_ready')};"
                f"training_primary_blocker={training_data.get('primary_blocker')}"
            ),
            "checkpoint preflight ready, trained checkpoint count >0, guarded production/assist default, production training-data contract ready, production promotion allowed by benchmark gates, and customer-facing score/ranking mutation explicitly allowed",
            "Build the production training-data contract green, add checkpoint sidecar metadata, attach benchmark gates, then allow guarded customer-facing correction only after preflight passes.",
        ),
        _row(
            "closed_loop_structure_docking_ai_graph",
            "ai_decision_graph",
            "closed" if closed_loop_ready else "open",
            decision_graph_path,
            (
                f"closed_loop={decision_graph.get('closed_loop_decision_graph_ready')};"
                f"structure_quality={decision_graph.get('structure_quality_node_ready')};"
                f"binding_site={decision_graph.get('binding_site_node_ready')};"
                f"pose_generation={decision_graph.get('pose_generation_node_ready')};"
                f"scoring={decision_graph.get('scoring_node_ready')};"
                f"uncertainty={decision_graph.get('uncertainty_abstention_node_ready')};"
                f"report={decision_graph.get('report_node_ready')};"
                f"customer_report_ux={decision_graph.get('customer_report_ux_node_ready')};"
                f"viewer_interaction={decision_graph.get('viewer_interaction_surface_ready')};"
                f"customer_report_card={decision_graph.get('customer_report_card_ready')};"
                f"interaction_rationale={decision_graph.get('interaction_rationale_ready')};"
                f"counterfactual_rescue={decision_graph.get('counterfactual_rescue_suggestion_ready')};"
                f"evidence_traceability={decision_graph.get('evidence_traceability_ready')};"
                f"ready_edges={decision_graph.get('ready_edge_count')}/{decision_graph.get('required_edge_count')};"
                f"fail_closed_transition={decision_graph.get('fail_closed_transition_ready')}"
            ),
            "single audited graph from structure quality -> binding site -> pose generation/scoring -> uncertainty/abstention -> report, with required fail-closed edges ready",
            (
                "Closed-loop AI decision graph contract is green; keep node and fail-closed edge evidence current when upstream artifacts change."
                if closed_loop_ready
                else "Create the closed-loop AI decision graph contract and wire each node and fail-closed edge to local evidence artifacts."
            ),
        ),
        _row(
            "durable_job_orchestration",
            "product_operations",
            "closed" if job_orchestration_ready else "open",
            f"{service_boundary_path};{api_contract_path};{job_orchestration_path}",
            (
                f"service_status={service.get('status')};api_routes={service.get('api_route_count')};"
                f"service_missing={service.get('missing_api_route_count')};"
                f"api_status={api.get('status')};api_expected_routes={api.get('expected_route_count')};"
                f"api_missing={api.get('missing_route_count')};"
                f"job_contract_status={job_contract.get('status')};"
                f"retry_child_attempt_created={job_contract.get('retry_child_attempt_created')};"
                f"idempotency_preserved={job_contract.get('idempotency_preserved')};"
                f"progress_fields_present={job_contract.get('progress_fields_present')};"
                f"listed_status_progress_contract_ready={job_contract.get('listed_status_progress_contract_ready')};"
                f"queue_lifecycle_progress_ready={job_contract.get('queue_lifecycle_progress_ready')};"
                f"customer_run_history_lineage_ready={job_contract.get('customer_run_history_lineage_ready')};"
                f"status_snapshot_persistence_ready={job_contract.get('status_snapshot_persistence_ready')};"
                f"rerun_manifest_ready={job_contract.get('rerun_manifest_ready')};"
                f"retention_policy_ready={job_contract.get('retention_policy_ready')};"
                f"long_running_status_persistence_ready={job_contract.get('long_running_status_persistence_ready')};"
                f"worker_backend_contract_ready={job_contract.get('worker_backend_contract_ready')};"
                f"worker_lease_heartbeat_ready={job_contract.get('worker_lease_heartbeat_ready')};"
                f"retryable_failure_resume_ready={job_contract.get('retryable_failure_resume_ready')};"
                f"running_cancel_ack_ready={job_contract.get('running_cancel_ack_ready')}"
            ),
            "API/service-boundary expose job list, status, history, cancel, and retry routes, and the job orchestration contract proves retry-child, idempotency, queue lifecycle, status-progress invariants, history lineage, status persistence, retention, rerun manifest, worker lease/heartbeat, retryable failure resume, and running cancel acknowledgment semantics",
            "Keep route contracts and the job orchestration ledger contract green; add worker-backed execution only behind explicit approval.",
        ),
        _row(
            "production_trajectory_sla",
            "runtime_sla",
            "closed" if production_sla_ready else "open",
            f"{e2e_path};{trajectory_sla_path}",
            (
                f"benchmark_ready={e2e.get('benchmark_ready')};"
                f"production_trajectory_profile_enabled={e2e.get('production_trajectory_profile_enabled')};"
                f"jobs_per_hour={e2e.get('jobs_per_hour')};"
                f"unique_ligands_per_hour={e2e.get('unique_ligands_per_hour')};"
                f"failure_rate={e2e.get('failure_rate')};"
                f"trajectory_sla_ready={trajectory_sla.get('production_trajectory_sla_ready')};"
                f"trajectory_sla_ready_runs={trajectory_sla.get('ready_run_count')};"
                f"trajectory_sla_qualified_runs={trajectory_sla.get('qualified_ready_run_count')};"
                f"trajectory_sla_families={','.join(str(item) for item in trajectory_sla.get('ready_families') or [])};"
                f"trajectory_sla_qualified_families={','.join(str(item) for item in trajectory_sla.get('qualified_ready_families') or [])};"
                f"minimum_ready_rows_per_family={trajectory_sla.get('minimum_ready_rows_per_family')};"
                f"sla_claim_tier={trajectory_sla.get('sla_claim_tier')};"
                f"current_rocm_baseline_claim_scope={trajectory_sla.get('current_rocm_baseline_claim_scope')};"
                f"current_rocm_baseline_production_profile_enabled={trajectory_sla.get('current_rocm_baseline_production_trajectory_profile_enabled')};"
                f"rocm_baseline_profile_gap_acknowledged={trajectory_sla.get('rocm_baseline_profile_gap_acknowledged')};"
                f"restricted_sla_backed_by_historical_profile_artifacts={trajectory_sla.get('restricted_sla_backed_by_historical_profile_artifacts')};"
                f"broad_platform_sla_allowed={trajectory_sla.get('broad_platform_sla_allowed')};"
                f"missing_qualified_families={','.join(str(item) for item in trajectory_sla.get('missing_qualified_families') or [])}"
            ),
            "restricted-family production trajectory profile evidence with >=10000 rows per required family, positive throughput, failure_rate<=0.05, broad platform SLA explicitly blocked, and current single-target ROCm baseline profile gap acknowledged",
            "Keep trajectory-profile SLA contract green and rerun target-specific e2e bundles under production profile when claiming per-target hosted SLA.",
        ),
        _row(
            "scope_breadth_expansion",
            "scientific_scope",
            "closed" if scope_ready else "open",
            f"{capability_path};{scope_breadth_path}",
            (
                f"allowed_scope_families={','.join(str(item) for item in allowed_families)};"
                f"general_platform={capability.get('general_protein_ligand_platform_ready')};"
                f"scope_breadth_ready={scope_breadth.get('scope_breadth_ready')};"
                f"scope_claim_posture_ready={scope_breadth.get('scope_claim_posture_ready')};"
                f"general_platform_claim_allowed={scope_breadth.get('general_platform_claim_allowed')};"
                f"blocked_claim_scopes={','.join(blocked_claim_scopes)};"
                f"scope_claim_boundary_detail={scope_breadth.get('scope_claim_boundary_detail')};"
                f"ready_domains={','.join(str(item) for item in scope_breadth.get('ready_domains') or [])};"
                f"missing_domains={','.join(str(item) for item in scope_breadth.get('missing_domains') or [])};"
                f"acquisition_plan_ready={scope_breadth.get('scope_breadth_acquisition_plan_ready')};"
                f"intake_readiness_ready={scope_breadth.get('evidence_intake_readiness_ready')};"
                f"local_crosscheck_intake_ready={scope_breadth.get('local_crosscheck_intake_ready_count')};"
                f"local_crosscheck_unreadable={scope_breadth.get('local_crosscheck_unreadable_item_count')};"
                f"transporter_triage_ready={scope_breadth.get('transporter_triage_packet_ready')};"
                f"transporter_operator_review_evidence_matrix_ready={scope_breadth.get('transporter_operator_review_evidence_matrix_ready')};"
                f"transporter_claim_safe_local_evidence_ready={scope_breadth.get('transporter_claim_safe_local_evidence_ready_count')};"
                f"transporter_claim_safe_local_evidence_blocked={scope_breadth.get('transporter_claim_safe_local_evidence_blocked_count')};"
                f"transporter_direct_binding_claim_blocked={scope_breadth.get('transporter_direct_binding_claim_blocked_count')};"
                f"transporter_negative_value_claim_blocked={scope_breadth.get('transporter_negative_value_claim_blocked_count')};"
                f"transporter_top_claim_safe_blocker={scope_breadth.get('transporter_top_claim_safe_blocker')};"
                f"transporter_candidate_assignment_required={scope_breadth.get('transporter_candidate_assignment_required_count')};"
                f"transporter_functional_direct_gap={scope_breadth.get('transporter_functional_direct_gap_count')};"
                f"transporter_candidate_workbook_ready={scope_breadth.get('transporter_candidate_workbook_ready')};"
                f"transporter_candidate_manual_review={scope_breadth.get('transporter_candidate_ready_for_manual_review_count')};"
                f"transporter_candidate_apply_ready={scope_breadth.get('transporter_candidate_ready_for_apply_count')};"
                f"transporter_manual_review_intake_ready={scope_breadth.get('transporter_manual_review_intake_ready')};"
                f"transporter_manual_review_template_rows={scope_breadth.get('transporter_manual_review_template_row_count')};"
                f"transporter_manual_review_direct_binding_required={scope_breadth.get('transporter_manual_review_direct_binding_evidence_required_count')};"
                f"transporter_manual_review_negative_value_required={scope_breadth.get('transporter_manual_review_negative_quantitative_value_required_count')};"
                f"pxr_exact_review_intake_ready={scope_breadth.get('pxr_exact_review_intake_ready')};"
                f"pxr_exact_review_template_rows={scope_breadth.get('pxr_exact_review_template_row_count')};"
                f"pxr_exact_review_conflict_required={scope_breadth.get('pxr_exact_review_conflict_resolution_required_count')};"
                f"pxr_exact_review_kcal_placeholders={scope_breadth.get('pxr_exact_review_kcal_placeholder_count')};"
                f"scientific_evidence_requests={scope_breadth.get('scientific_evidence_request_count')};"
                f"external_exact_evidence_required={scope_breadth.get('external_primary_exact_evidence_required_count')};"
                f"intake_external_exact_required={scope_breadth.get('intake_external_exact_evidence_required_count')};"
                f"review_only_keep_blocked={scope_breadth.get('review_only_keep_blocked_count')}"
            ),
            "scope breadth contract is ready, scope claim posture is explicit, general platform claim is allowed by the contract, and no blocked claim scopes remain",
            scope_next_action,
        ),
        _row(
            "ai_analysis_report_ux",
            "customer_ux",
            "closed" if report_ux_ready else "open",
            report_ux_path,
            (
                f"report_ux={report_ux.get('ai_report_ux_ready')};"
                f"binding_site={report_ux.get('binding_site_explanation_ready')};"
                f"pose_comparison={report_ux.get('pose_comparison_ready')};"
                f"interaction_rationale={report_ux.get('interaction_rationale_ready')};"
                f"viewer_interaction_surface={report_ux.get('viewer_interaction_surface_ready')};"
                f"uncertainty={report_ux.get('uncertainty_narrative_ready')};"
                f"counterfactual={report_ux.get('counterfactual_rescue_suggestion_ready')};"
                f"structured_customer_report_ready={report_ux.get('structured_customer_report_ready')};"
                f"customer_report_delivery_contract_ready={report_ux.get('customer_report_delivery_contract_ready')};"
                f"customer_report_evidence_binding_ready={report_ux.get('customer_report_evidence_binding_ready')};"
                f"customer_report_viewer_binding_ready={report_ux.get('customer_report_viewer_binding_ready')};"
                f"viewer_customer_report_binding_ready={report_ux.get('viewer_customer_report_binding_ready')};"
                f"customer_report_ready_block_count={report_ux.get('customer_report_ready_block_count')};"
                f"customer_report_required_block_count={report_ux.get('customer_report_required_block_count')};"
                f"customer_report_blocked_block_count={report_ux.get('customer_report_blocked_block_count')};"
                f"customer_report_card_ready={report_ux.get('customer_report_card_ready')};"
                f"evidence_traceability_ready={report_ux.get('evidence_traceability_ready')};"
                f"ranking_score_col={report_ux.get('ranking_score_col')};"
                f"primary_abstention_reason={report_ux.get('primary_abstention_reason')};"
                f"what_would_change_decision={report_ux.get('what_would_change_decision')}"
            ),
            "customer report includes binding-site explanation, pose comparison, interaction rationale, viewer interaction surface, uncertainty narrative, counterfactual/rescue suggestions, structured claim limits, evidence traceability, abstention reason, and decision-change conditions",
            "Build a report UX contract and viewer-ready report packet over the existing evidence artifacts.",
        ),
        _row(
            "security_deployment_operations",
            "security_deployment",
            "closed" if security_ready else "open",
            security_deployment_path,
            (
                f"security={security.get('security_deployment_ready')};auth={security.get('auth_ready')};"
                f"tenant={security.get('tenant_isolation_ready')};rate_limit={security.get('rate_limit_ready')};"
                f"hosted_external_exposure_guard={security.get('hosted_external_exposure_guard_ready')};"
                f"hosted_external_exposure_allowed={security.get('hosted_external_exposure_allowed')};"
                f"hosted_deployment_contract_ready={security.get('hosted_deployment_contract_ready')};"
                f"hosted_deployment_currently_satisfied={security.get('hosted_deployment_currently_satisfied')};"
                f"hosted_deployment_next_stage_id={security.get('hosted_deployment_next_stage_id')};"
                f"hosted_exposure_approval_token_required={security.get('hosted_exposure_approval_token_required')};"
                f"tls_termination_operator_verified={security.get('tls_termination_operator_verified')};"
                f"hosted_secret_injection_ready={security.get('hosted_secret_injection_ready')};"
                f"sbom={security.get('sbom_ready')};container={security.get('container_image_ready')};"
                f"metrics={security.get('metrics_endpoint_ready')};rollback={security.get('rollback_ready')}"
            ),
            "hosted/customer API has auth, tenancy, rate limits, payload/path controls, audit logs, fail-closed external exposure guard, SBOM, container, metrics, and rollback",
            "Add a security/deployment contract before any hosted or external customer API claim.",
        ),
    ]
    closed_rows = [row for row in rows if row["status"] == "closed"]
    open_rows = [row for row in rows if row["status"] != "closed"]
    first_open = open_rows[0] if open_rows else None
    gap_blocker_matrix = _gap_blocker_matrix(
        open_rows=open_rows,
        production_ai_checkpoint=production_ai_checkpoint,
        scope_breadth=scope_breadth,
        scope_breadth_path=scope_breadth_path,
    )
    parallelizable_gap_blockers = [
        row for row in gap_blocker_matrix if row.get("parallelizable_workstream") is True
    ]
    first_blocker = gap_blocker_matrix[0] if gap_blocker_matrix else {}
    first_parallelizable_blocker = (
        parallelizable_gap_blockers[0] if parallelizable_gap_blockers else {}
    )
    blocker_by_gap_id = {
        _text(row.get("gap_id")): row for row in gap_blocker_matrix if _text(row.get("gap_id"))
    }
    for row in rows:
        if row.get("status") == "closed":
            continue
        blocker = blocker_by_gap_id.get(_text(row.get("gap_id")))
        if not blocker:
            continue
        row["immediate_actionable_blocker_id"] = _text(blocker.get("primary_blocker_id"))
        row["immediate_actionable_blocker_stage_id"] = _text(blocker.get("blocker_stage_id"))
        row["immediate_actionable_blocker_artifact"] = _text(blocker.get("blocker_artifact"))
        row["immediate_actionable_blocker_validation_command"] = _text(blocker.get("validation_command"))
        row["immediate_actionable_blocker_operator_input_fields"] = [
            str(item) for item in (blocker.get("operator_input_fields") or [])
        ]
        row["immediate_actionable_blocker_next_action"] = _text(blocker.get("next_action"))
        row["immediate_actionable_blocker_unlock_claim"] = _text(blocker.get("unlock_claim"))
        if row["immediate_actionable_blocker_next_action"]:
            row["next_action"] = row["immediate_actionable_blocker_next_action"]
    current_next_action = (
        _text(first_blocker.get("next_action"))
        or (first_open["next_action"] if first_open else "")
        or "All AI architecture gaps are closed."
    )
    summary = {
        "packet_type": "product_ai_architecture_gap_closure",
        "status": "product_ai_architecture_gap_closure_complete" if not open_rows else "blocked_product_ai_architecture_gap_closure",
        "all_gaps_closed": not open_rows,
        "gap_count": len(rows),
        "closed_gap_count": len(closed_rows),
        "open_gap_count": len(open_rows),
        "completion_percent": round((len(closed_rows) / len(rows)) * 100.0, 3),
        "closed_gap_ids": [row["gap_id"] for row in closed_rows],
        "open_gap_ids": [row["gap_id"] for row in open_rows],
        "current_primary_open_gap": first_open["gap_id"] if first_open else "none",
        "current_next_action": current_next_action,
        "gap_blocker_matrix_ready": bool(gap_blocker_matrix) or not open_rows,
        "gap_blocker_matrix_count": len(gap_blocker_matrix),
        "gap_blocker_matrix": gap_blocker_matrix,
        "current_primary_blocker_gap_id": _text(first_blocker.get("gap_id")),
        "current_primary_blocker_id": _text(first_blocker.get("primary_blocker_id")),
        "current_primary_blocker_artifact": _text(first_blocker.get("blocker_artifact")),
        "current_primary_blocker_validation_command": _text(first_blocker.get("validation_command")),
        "current_primary_blocker_next_action": _text(first_blocker.get("next_action")),
        "current_primary_blocker_operator_input_fields": [
            str(item) for item in (first_blocker.get("operator_input_fields") or [])
        ],
        "current_primary_blocker_unlock_claim": _text(first_blocker.get("unlock_claim")),
        "current_primary_blocker_next_after_stage_id": _text(
            first_blocker.get("next_after_blocker_stage_id")
        ),
        "current_primary_blocker_next_after_artifact": _text(
            first_blocker.get("next_after_blocker_artifact")
        ),
        "current_primary_blocker_next_after_validation_command": _text(
            first_blocker.get("next_after_blocker_validation_command")
        ),
        "current_primary_blocker_next_after_next_action": _text(
            first_blocker.get("next_after_blocker_next_action")
        ),
        "current_primary_blocker_next_after_required_checks": [
            str(item) for item in (first_blocker.get("next_after_blocker_required_checks") or [])
        ],
        "current_primary_blocker_next_after_unlock_fields": [
            str(item) for item in (first_blocker.get("next_after_blocker_unlock_fields") or [])
        ],
        "parallelizable_gap_blocker_count": len(parallelizable_gap_blockers),
        "parallelizable_gap_blocker_ids": [
            _text(row.get("primary_blocker_id")) for row in parallelizable_gap_blockers
        ],
        "first_parallelizable_gap_id": _text(first_parallelizable_blocker.get("gap_id")),
        "first_parallelizable_blocker_id": _text(
            first_parallelizable_blocker.get("primary_blocker_id")
        ),
        "first_parallelizable_blocker_artifact": _text(
            first_parallelizable_blocker.get("blocker_artifact")
        ),
        "first_parallelizable_blocker_next_action": _text(
            first_parallelizable_blocker.get("next_action")
        ),
        "first_parallelizable_blocker_validation_command": _text(
            first_parallelizable_blocker.get("validation_command")
        ),
        "first_parallelizable_blocker_operator_input_fields": [
            str(item)
            for item in (first_parallelizable_blocker.get("operator_input_fields") or [])
        ],
        "first_parallelizable_blocker_required_exact_evidence_fields": [
            str(item)
            for item in (
                first_parallelizable_blocker.get("required_exact_evidence_fields") or []
            )
        ],
        "first_parallelizable_blocker_required_claim_guardrails": [
            str(item)
            for item in (first_parallelizable_blocker.get("required_claim_guardrails") or [])
        ],
        "first_parallelizable_blocker_claim_safe_completion_rule": _text(
            first_parallelizable_blocker.get("claim_safe_completion_rule")
        ),
        "first_parallelizable_blocker_unlock_claim": _text(
            first_parallelizable_blocker.get("unlock_claim")
        ),
        "first_parallelizable_blocker_source_modality_triage_artifact": _text(
            first_parallelizable_blocker.get("source_modality_triage_artifact")
        ),
        "first_parallelizable_blocker_source_modality_triage_decision": _text(
            first_parallelizable_blocker.get("source_modality_triage_decision")
        ),
        "first_parallelizable_blocker_source_modality_direct_experimental_binding_row_count": _int(
            first_parallelizable_blocker.get("source_modality_direct_experimental_binding_row_count")
        ),
        "first_parallelizable_blocker_source_modality_claim_safe_binding_kcal_ready_count": _int(
            first_parallelizable_blocker.get("source_modality_claim_safe_binding_kcal_ready_count")
        ),
        "first_parallelizable_blocker_source_modality_computational_binding_energy_row_count": _int(
            first_parallelizable_blocker.get("source_modality_computational_binding_energy_row_count")
        ),
        "first_parallelizable_blocker_source_modality_best_computational_binding_energy_kcal_mol": _text(
            first_parallelizable_blocker.get("source_modality_best_computational_binding_energy_kcal_mol")
        ),
        "production_ai_checkpoint_readiness_artifact": production_ai_checkpoint_readiness_path,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product AI Architecture Gap Closure",
        "",
        f"- status: `{s['status']}`",
        f"- all_gaps_closed: `{s['all_gaps_closed']}`",
        f"- closed_gap_count: `{s['closed_gap_count']}` / `{s['gap_count']}`",
        f"- completion_percent: `{s['completion_percent']}`",
        f"- current_primary_open_gap: `{s['current_primary_open_gap']}`",
        f"- current_primary_blocker_id: `{s['current_primary_blocker_id']}`",
        f"- first_parallelizable_blocker_id: `{s['first_parallelizable_blocker_id']}`",
        f"- gap_blocker_matrix_count: `{s['gap_blocker_matrix_count']}`",
        "",
        "## Gaps",
        "",
        "| gap | domain | status | observed | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['gap_id']}` | `{row['domain']}` | `{row['status']}` | `{row['observed']}` | {row['next_action']} |"
        )
    lines.extend(
        [
            "",
            "## Gap Blockers",
            "",
            "| gap | blocker | artifact | parallel | next action | validation |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in s.get("gap_blocker_matrix") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{_text(row.get('gap_id'))}` | `{_text(row.get('primary_blocker_id'))}` | "
            f"`{_text(row.get('blocker_artifact'))}` | `{row.get('parallelizable_workstream') is True}` | "
            f"{_text(row.get('next_action'))} | `{_text(row.get('validation_command'))}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Current Next Action", "", f"- {s['current_next_action']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build closure status for product AI architecture hardening gaps.")
    parser.add_argument("--registry-json", default=DEFAULT_REGISTRY_JSON)
    parser.add_argument("--e2e-json", default=DEFAULT_E2E_JSON)
    parser.add_argument("--service-boundary-json", default=DEFAULT_SERVICE_BOUNDARY_JSON)
    parser.add_argument("--api-contract-json", default=DEFAULT_API_CONTRACT_JSON)
    parser.add_argument("--job-orchestration-json", default=DEFAULT_JOB_ORCHESTRATION_JSON)
    parser.add_argument("--capability-json", default=DEFAULT_CAPABILITY_JSON)
    parser.add_argument("--decision-graph-json", default=DEFAULT_DECISION_GRAPH_JSON)
    parser.add_argument("--report-ux-json", default=DEFAULT_REPORT_UX_JSON)
    parser.add_argument("--security-deployment-json", default=DEFAULT_SECURITY_DEPLOYMENT_JSON)
    parser.add_argument("--trajectory-sla-json", default=DEFAULT_TRAJECTORY_SLA_JSON)
    parser.add_argument("--scope-breadth-json", default=DEFAULT_SCOPE_BREADTH_JSON)
    parser.add_argument("--training-data-json", default=DEFAULT_TRAINING_DATA_JSON)
    parser.add_argument("--production-ai-checkpoint-readiness-json", default=DEFAULT_PRODUCTION_AI_CHECKPOINT_READINESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_ai_architecture_gap_closure(
        registry_packet=_read_json(args.registry_json),
        e2e_packet=_read_json(args.e2e_json),
        service_boundary_packet=_read_json(args.service_boundary_json),
        api_contract_packet=_read_json(args.api_contract_json),
        job_orchestration_packet=_read_json(args.job_orchestration_json),
        capability_packet=_read_json(args.capability_json),
        decision_graph_packet=_read_json(args.decision_graph_json),
        report_ux_packet=_read_json(args.report_ux_json),
        security_deployment_packet=_read_json(args.security_deployment_json),
        trajectory_sla_packet=_read_json(args.trajectory_sla_json),
        scope_breadth_packet=_read_json(args.scope_breadth_json),
        training_data_packet=_read_json(args.training_data_json),
        production_ai_checkpoint_readiness_packet=_read_json(args.production_ai_checkpoint_readiness_json),
        registry_path=args.registry_json,
        e2e_path=args.e2e_json,
        service_boundary_path=args.service_boundary_json,
        api_contract_path=args.api_contract_json,
        job_orchestration_path=args.job_orchestration_json,
        capability_path=args.capability_json,
        decision_graph_path=args.decision_graph_json,
        report_ux_path=args.report_ux_json,
        security_deployment_path=args.security_deployment_json,
        trajectory_sla_path=args.trajectory_sla_json,
        scope_breadth_path=args.scope_breadth_json,
        training_data_path=args.training_data_json,
        production_ai_checkpoint_readiness_path=args.production_ai_checkpoint_readiness_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
