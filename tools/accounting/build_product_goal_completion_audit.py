#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARCHITECTURE_JSON = "runs/product_architecture_contract_current.json"
DEFAULT_RELEASE_DOSSIER_JSON = "runs/product_release_operations_dossier_current.json"
DEFAULT_PUBLIC_BENCHMARK_JSON = "runs/product_public_benchmark_contract_current.json"
DEFAULT_COMMERCIAL_INDEPENDENCE_JSON = "runs/product_commercial_independence_gate_current.json"
DEFAULT_LICENSE_WORK_ORDER_JSON = "runs/product_license_file_creation_work_order_current.json"
DEFAULT_CAMEO_ARCHITECTURE_JSON = "runs/cameo_architecture_validation_contract_current.json"
DEFAULT_RELEASE_GATE_JSON = "runs/goal_release_decision_gate_current.json"
DEFAULT_BOTTLENECK_JSON = "runs/goal_bottleneck_briefing_current.json"
DEFAULT_BURNDOWN_JSON = "runs/goal_release_burndown_work_order_current.json"
DEFAULT_PRODUCT_AI_ARCHITECTURE_GAP_JSON = "runs/product_ai_architecture_gap_closure_current.json"
DEFAULT_PRODUCT_AI_EXECUTION_BACKLOG_JSON = "runs/product_ai_architecture_execution_backlog_current.json"
DEFAULT_RESIDUAL_MODEL_REGISTRY_JSON = "runs/residual_model_registry_current.json"
DEFAULT_PRODUCTION_AI_CHECKPOINT_READINESS_JSON = "runs/product_production_ai_checkpoint_readiness_current.json"
DEFAULT_PRODUCTION_AI_GPU_RETURN_INTAKE_JSON = "runs/product_production_ai_gpu_return_intake_current.json"
DEFAULT_PRODUCTION_AI_PROMOTION_WORKBENCH_JSON = "runs/product_production_ai_promotion_workbench_current.json"
DEFAULT_PRODUCT_SCOPE_BREADTH_CONTRACT_JSON = "runs/product_scope_breadth_contract_current.json"
DEFAULT_SCOPE_EVIDENCE_PRIORITY_JSON = "runs/product_scope_breadth_evidence_priority_packet_current.json"
DEFAULT_SCOPE_EVIDENCE_INTAKE_READINESS_JSON = "runs/product_scope_breadth_evidence_intake_readiness_current.json"
DEFAULT_SCOPE_BREADTH_EVIDENCE_RECEIPT_JSON = "runs/product_scope_breadth_evidence_receipt_current.json"
DEFAULT_PXR_EXACT_REVIEW_INTAKE_JSON = "runs/pxr_exact_evidence_review_intake_template_current.json"
DEFAULT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_JSON = "runs/product_commercial_readiness_handoff_bundle_current.json"
DEFAULT_DELTA_FORCE_CLOSURE_ACCEPTANCE_JSON = "runs/residual_delta_force_closure_acceptance_packet_current.json"
DEFAULT_SCOPE_CLOSURE_ACCEPTANCE_JSON = "runs/product_scope_closure_acceptance_packet_current.json"
DEFAULT_SCOPE_CLOSURE_CHECKLIST_JSON = "runs/product_scope_breadth_closure_checklist_current.json"
DEFAULT_REPORT_UX_JSON = "runs/product_ai_report_ux_contract_current.json"
DEFAULT_TRAJECTORY_SLA_JSON = "runs/product_trajectory_sla_contract_current.json"
DEFAULT_SECURITY_DEPLOYMENT_JSON = "runs/product_security_deployment_contract_current.json"
DEFAULT_DECISION_GRAPH_JSON = "runs/product_ai_decision_graph_contract_current.json"
DEFAULT_SERVICE_BOUNDARY_JSON = "runs/product_service_boundary_contract_current.json"
DEFAULT_PRODUCT_API_CONTRACT_JSON = "runs/product_api_contract_current.json"
DEFAULT_JOB_ORCHESTRATION_JSON = "runs/product_job_orchestration_contract_current.json"
DEFAULT_ENGINE_REFINEMENT_TIER_READINESS_JSON = "runs/engine_refinement_tier_readiness_current.json"
DEFAULT_OUT_JSON = "runs/product_goal_completion_audit_current.json"
DEFAULT_OUT_CSV = "runs/product_goal_completion_audit_current.csv"
DEFAULT_OUT_MD = "runs/product_goal_completion_audit_current.md"

CLAIM_BOUNDARY = (
    "Product goal completion audit only; it verifies objective-level readiness from existing local JSON artifacts. "
    "It does not choose a license, create LICENSE, run docking, download data, submit CAMEO predictions, register a "
    "server, send email, delete/archive/externalize/upload files, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def _join(values: list[Any]) -> str:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in _text(value).split(";"):
            part = part.strip()
            if not part or part in seen:
                continue
            seen.add(part)
            output.append(part)
    return ";".join(output)


def _primary_bottleneck_command(burndown_packet: dict[str, Any], primary_phase: str) -> str:
    for row in _rows(burndown_packet):
        if _text(row.get("phase")) == primary_phase:
            return _text(row.get("command"))
    return ""


def _primary_bottleneck_command_candidates(burndown_packet: dict[str, Any], primary_phase: str) -> list[str]:
    for row in _rows(burndown_packet):
        if _text(row.get("phase")) != primary_phase:
            continue
        examples = _text(row.get("license_local_source_command_examples"))
        return [part.strip() for part in examples.split("||") if part.strip()]
    return []


def _product_ai_gap_next_command(primary_phase: str, primary_next_command: str) -> str:
    if primary_phase.startswith("P0_product_ai_architecture_") and primary_next_command:
        return primary_next_command
    return (
        "python3 tools/build_product_ai_architecture_execution_backlog.py && "
        "python3 tools/build_product_ai_architecture_gap_closure.py && "
        "python3 tools/build_product_goal_completion_audit.py"
    )


def _first_present_value(source_packets: list[dict[str, Any]], keys: list[str]) -> Any:
    for packet in source_packets:
        for key in keys:
            if key in packet:
                return packet.get(key)
    return None


def _release_blocker_summary(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "primary_release_blocker_requirement_id": "",
            "primary_release_blocker_tier": "",
            "primary_release_blocker": "",
            "primary_release_blocker_next_command": "",
            "primary_release_blocker_observed": "",
            "primary_release_blocker_required": "",
        }
    return {
        "primary_release_blocker_requirement_id": _text(row.get("requirement_id")),
        "primary_release_blocker_tier": _text(row.get("requirement_tier")),
        "primary_release_blocker": _text(row.get("blocker")),
        "primary_release_blocker_next_command": _text(row.get("next_command")),
        "primary_release_blocker_observed": _text(row.get("observed")),
        "primary_release_blocker_required": _text(row.get("required")),
    }


def _next_command_candidates(
    *,
    primary_next_command: str,
    burndown_candidates: list[str],
    primary_backlog: dict[str, Any],
    product_ai_architecture_ready: bool,
) -> list[str]:
    candidates: list[str] = []
    for command in burndown_candidates:
        if command and command not in candidates:
            candidates.append(command)
    if not product_ai_architecture_ready:
        backlog_command = _text(primary_backlog.get("verification_command"))
        if backlog_command and backlog_command not in candidates:
            candidates.append(backlog_command)
        if primary_next_command and primary_next_command not in candidates:
            candidates.append(primary_next_command)
    return candidates


def _primary_backlog_row(backlog_packet: dict[str, Any]) -> dict[str, Any]:
    summary = _summary(backlog_packet)
    primary_id = _text(summary.get("primary_work_item_id"))
    rows = _rows(backlog_packet)
    for row in rows:
        if primary_id and _text(row.get("work_item_id")) == primary_id:
            return row
    return rows[0] if rows else {}


def _top_priority_row(priority_packet: dict[str, Any]) -> dict[str, Any]:
    rows = _rows(priority_packet)
    if not rows:
        return {}
    return sorted(rows, key=lambda row: _int(row.get("priority")) or 999999)[0]


def _gap_row_by_id(gap_packet: dict[str, Any], gap_id: str) -> dict[str, Any]:
    for row in _rows(gap_packet):
        if _text(row.get("gap_id")) == gap_id:
            return row
    return {}


def _gap_closed(gap_packet: dict[str, Any], gap_id: str, *, fallback_ready: bool = False) -> bool:
    row = _gap_row_by_id(gap_packet, gap_id)
    if row:
        return _text(row.get("status")) == "closed"
    return fallback_ready


def _gap_observed(gap_packet: dict[str, Any], gap_id: str) -> str:
    return _text(_gap_row_by_id(gap_packet, gap_id).get("observed"))


def _live_production_ai_checkpoint_observed(
    *,
    registry: dict[str, Any],
    production_ai_checkpoint: dict[str, Any],
) -> str:
    missing_sidecar = [
        str(item)
        for item in (
            registry.get("selected_sidecar_missing_output_fields")
            or production_ai_checkpoint.get("selected_sidecar_missing_output_fields")
            or registry.get("checkpoint_missing_output_fields")
            or []
        )
    ]
    return (
        f"product_model_layer_ready={registry.get('product_model_layer_ready')};"
        f"default_residual_mode={registry.get('default_residual_mode')};"
        f"production_promotion_allowed={registry.get('production_promotion_allowed')};"
        f"customer_facing_auto_correction_allowed={registry.get('customer_facing_auto_correction_allowed')};"
        f"customer_facing_score_mutation_allowed={registry.get('customer_facing_score_mutation_allowed')};"
        f"customer_facing_ranking_mutation_allowed={registry.get('customer_facing_ranking_mutation_allowed')};"
        f"checkpoint_preflight_ready={registry.get('checkpoint_preflight_ready')};"
        f"candidate_checkpoint_count={registry.get('candidate_checkpoint_count')};"
        f"trained_model_checkpoint_count={registry.get('trained_model_checkpoint_count')};"
        f"selected_sidecar_ready={registry.get('selected_sidecar_ready')};"
        f"selected_sidecar_missing_output_fields={','.join(missing_sidecar)};"
        f"production_checkpoint_blocked={registry.get('production_checkpoint_blocked')};"
        f"checkpoint_primary_blocker={registry.get('checkpoint_primary_blocker')};"
        f"production_training_data_ready={production_ai_checkpoint.get('production_training_data_ready')};"
        f"force_gpu_worker_return_receipt_ready={production_ai_checkpoint.get('force_gpu_worker_return_receipt_ready')};"
        f"production_output_heads_complete={production_ai_checkpoint.get('production_output_heads_complete')}"
    )


def _live_gpu_return_receipt_blockers(
    *,
    production_ai_gpu_return_intake: dict[str, Any],
) -> list[str]:
    receipt_blockers = [str(item) for item in (production_ai_gpu_return_intake.get("receipt_blockers") or []) if _text(item)]
    if receipt_blockers:
        return receipt_blockers
    mapped: list[str] = []
    for check_id in production_ai_gpu_return_intake.get("failed_check_ids") or []:
        text = _text(check_id)
        if text.startswith("actual_summary") and "full_regeneration_summary_complete" not in mapped:
            mapped.append("full_regeneration_summary_complete")
        elif text == "post_run_force_derivation_validation":
            mapped.append(text)
    return mapped


def _live_missing_production_output_labels(
    *,
    residual_model_registry: dict[str, Any],
    production_ai_checkpoint: dict[str, Any],
) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for source in (
        production_ai_checkpoint.get("production_output_head_blocked_fields"),
        production_ai_checkpoint.get("missing_production_output_labels"),
        residual_model_registry.get("selected_sidecar_missing_output_fields"),
        residual_model_registry.get("checkpoint_missing_output_fields"),
    ):
        for item in source or []:
            text = _text(item)
            if text and text not in seen:
                seen.add(text)
                labels.append(text)
    for part in _text(production_ai_checkpoint.get("first_failed_observed")).split(";"):
        key, sep, value = part.partition("=")
        if not sep or key.strip() != "missing":
            continue
        for field in value.split(","):
            field = field.strip()
            if field and field not in seen:
                seen.add(field)
                labels.append(field)
    return labels


def _live_primary_observed_pairs(
    *,
    production_ai_gpu_return_intake: dict[str, Any],
    production_ai_checkpoint: dict[str, Any],
    residual_model_registry: dict[str, Any],
) -> dict[str, str]:
    blockers = _live_gpu_return_receipt_blockers(production_ai_gpu_return_intake=production_ai_gpu_return_intake)
    missing_output_labels = _live_missing_production_output_labels(
        residual_model_registry=residual_model_registry,
        production_ai_checkpoint=production_ai_checkpoint,
    )
    return {
        "gpu_worker_return_receipt_ready": _bool_text(
            production_ai_checkpoint.get("force_gpu_worker_return_receipt_ready")
        ),
        "gpu_worker_return_receipt_blockers": ",".join(blockers),
        "gpu_worker_return_expected_queue_rows": str(
            production_ai_gpu_return_intake.get("expected_queue_rows")
            or production_ai_gpu_return_intake.get("operator_return_handoff_queue_row_count")
            or 0
        ),
        "gpu_worker_return_manifest_ok_row_count": str(
            production_ai_gpu_return_intake.get("manifest_ok_row_count")
            or production_ai_checkpoint.get("gpu_receipt_manifest_ok_row_count")
            or 0
        ),
        "gpu_worker_return_manifest_status_placeholder_count": str(
            production_ai_gpu_return_intake.get("manifest_status_placeholder_count") or 0
        ),
        "gpu_worker_return_manifest_status_invalid_count": str(
            production_ai_gpu_return_intake.get("manifest_status_invalid_count") or 0
        ),
        "gpu_worker_return_manifest_operator_verified": _bool_text(
            production_ai_gpu_return_intake.get("manifest_operator_verified")
        ),
        "gpu_worker_return_operator_verified_true_count": str(
            production_ai_gpu_return_intake.get("manifest_operator_verified_true_count") or 0
        ),
        "gpu_worker_return_operator_verification_column_present": _bool_text(
            production_ai_gpu_return_intake.get("manifest_operator_verification_column_present")
        ),
        "gpu_worker_return_identity_coverage_ready": _bool_text(
            production_ai_gpu_return_intake.get("manifest_identity_coverage_ready")
        ),
        "gpu_worker_return_matched_queue_fingerprints": str(
            production_ai_gpu_return_intake.get("matched_queue_fingerprint_count") or 0
        ),
        "gpu_worker_return_queue_fingerprints": str(
            production_ai_gpu_return_intake.get("queue_fingerprint_count")
            or production_ai_gpu_return_intake.get("expected_queue_rows")
            or production_ai_gpu_return_intake.get("manifest_template_row_count")
            or 0
        ),
        "force_derivation_input_ready": _bool_text(
            production_ai_checkpoint.get("force_derivation_input_ready")
        ),
        "delta_force_derivation_validation_ready": _bool_text(
            production_ai_checkpoint.get("delta_force_derivation_validation_ready")
        ),
        "missing_production_output_labels": ",".join(missing_output_labels),
    }


def _live_primary_backlog_observed_string(pairs: dict[str, str]) -> str:
    return ";".join(f"{key}={value}" for key, value in pairs.items() if value != "")


def _live_closed_loop_observed(decision_graph: dict[str, Any]) -> str:
    if not decision_graph:
        return ""
    return (
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
    )


def _live_durable_job_observed(
    *,
    service: dict[str, Any],
    api: dict[str, Any],
    job_contract: dict[str, Any],
) -> str:
    if not service and not api and not job_contract:
        return ""
    return (
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
    )


def _live_gap_observed(
    gap_id: str,
    *,
    registry: dict[str, Any],
    production_ai_checkpoint: dict[str, Any],
    report_ux: dict[str, Any],
    trajectory_sla: dict[str, Any],
    security: dict[str, Any],
    decision_graph: dict[str, Any],
    service: dict[str, Any],
    api: dict[str, Any],
    job_contract: dict[str, Any],
    gap_packet: dict[str, Any],
    scope_breadth: dict[str, Any] | None = None,
    capability: dict[str, Any] | None = None,
    scope_closure_checklist: dict[str, Any] | None = None,
    scope_closure_acceptance: dict[str, Any] | None = None,
) -> str:
    if gap_id == "production_ai_inference_checkpoint":
        if registry or production_ai_checkpoint:
            return _live_production_ai_checkpoint_observed(
                registry=registry,
                production_ai_checkpoint=production_ai_checkpoint,
            )
        row = _gap_row_by_id(gap_packet, gap_id)
        stale_observed = _text(row.get("observed"))
        if stale_observed:
            return stale_observed
        return _live_production_ai_checkpoint_observed(
            registry=registry,
            production_ai_checkpoint=production_ai_checkpoint,
        )
    if gap_id == "ai_analysis_report_ux" and report_ux:
        return (
            f"customer_report_delivery_contract_ready={report_ux.get('customer_report_delivery_contract_ready')};"
            f"customer_report_evidence_binding_ready={report_ux.get('customer_report_evidence_binding_ready')};"
            f"customer_report_viewer_binding_ready={report_ux.get('customer_report_viewer_binding_ready')};"
            f"viewer_customer_report_binding_ready={report_ux.get('viewer_customer_report_binding_ready')};"
            f"customer_report_ready_block_count={report_ux.get('customer_report_ready_block_count')};"
            f"customer_report_required_block_count={report_ux.get('customer_report_required_block_count')};"
            f"customer_report_blocked_block_count={report_ux.get('customer_report_blocked_block_count')}"
        )
    if gap_id == "production_trajectory_sla" and trajectory_sla:
        return (
            f"sla_claim_tier={trajectory_sla.get('sla_claim_tier')};"
            f"restricted_sla_backed_by_historical_profile_artifacts={trajectory_sla.get('restricted_sla_backed_by_historical_profile_artifacts')};"
            f"broad_platform_sla_allowed={trajectory_sla.get('broad_platform_sla_allowed')};"
            f"current_rocm_baseline_claim_scope={trajectory_sla.get('current_rocm_baseline_claim_scope')};"
            f"current_rocm_baseline_production_profile_enabled={trajectory_sla.get('current_rocm_baseline_production_profile_enabled')};"
            f"rocm_baseline_profile_gap_acknowledged={trajectory_sla.get('rocm_baseline_profile_gap_acknowledged')}"
        )
    if gap_id == "closed_loop_structure_docking_ai_graph" and decision_graph:
        return _live_closed_loop_observed(decision_graph)
    if gap_id == "durable_job_orchestration" and (service or api or job_contract):
        return _live_durable_job_observed(service=service, api=api, job_contract=job_contract)
    if gap_id == "security_deployment_operations" and security:
        return (
            f"security_deployment_ready={security.get('security_deployment_ready')};"
            f"auth_ready={security.get('auth_ready')};"
            f"tenant_isolation_ready={security.get('tenant_isolation_ready')};"
            f"tenant_quota_ready={security.get('tenant_quota_ready')};"
            f"audit_retention_ready={security.get('audit_retention_ready')};"
            f"secret_rotation_contract_ready={security.get('secret_rotation_contract_ready')};"
            f"backup_dr_contract_ready={security.get('backup_dr_contract_ready')};"
            f"pager_alert_contract_ready={security.get('pager_alert_contract_ready')};"
            f"hosted_deployment_contract_ready={security.get('hosted_deployment_contract_ready')};"
            f"hosted_deployment_currently_satisfied={security.get('hosted_deployment_currently_satisfied')};"
            f"hosted_deployment_next_stage_id={security.get('hosted_deployment_next_stage_id')};"
            f"hosted_external_exposure_allowed={security.get('hosted_external_exposure_allowed')};"
            f"hosted_secret_injection_ready={security.get('hosted_secret_injection_ready')};"
            f"tls_termination_operator_verified={security.get('tls_termination_operator_verified')};"
            f"sbom_ready={security.get('sbom_ready')};"
            f"container_image_ready={security.get('container_image_ready')}"
        )
    if gap_id == "scope_breadth_expansion" and scope_breadth:
        return _live_scope_breadth_observed(
            scope_breadth,
            capability=capability,
            scope_closure_checklist=scope_closure_checklist,
            scope_closure_acceptance=scope_closure_acceptance,
        )
    row = _gap_row_by_id(gap_packet, gap_id)
    stale_observed = _text(row.get("observed"))
    if stale_observed:
        return stale_observed
    return f"gap_status={_text(row.get('status'))};gap_id={gap_id};live_observed_rebuilt=true"


def _count_map_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return ",".join(f"{key}={value[key]}" for key in sorted(value))


def _live_scope_breadth_observed(
    scope_breadth: dict[str, Any],
    *,
    capability: dict[str, Any] | None = None,
    scope_closure_checklist: dict[str, Any] | None = None,
    scope_closure_acceptance: dict[str, Any] | None = None,
) -> str:
    if not scope_breadth:
        return ""
    capability = capability or {}
    scope_closure_checklist = scope_closure_checklist or {}
    scope_closure_acceptance = scope_closure_acceptance or {}
    allowed_families = (
        scope_breadth.get("allowed_scope_families")
        or capability.get("allowed_scope_families")
        or []
    )
    blocked_claim_scopes = list(scope_breadth.get("blocked_claim_scopes") or [])
    if not blocked_claim_scopes:
        blocked_claim_scopes = list(
            scope_breadth.get("scope_acceptance_next_stage_unlock_claim_scopes")
            or scope_breadth.get("scope_claim_expansion_current_next_stage_unlock_claim_scopes")
            or []
        )
    general_platform_ready = capability.get("general_protein_ligand_platform_ready")
    if general_platform_ready is None:
        general_platform_ready = scope_breadth.get("general_protein_ligand_platform_ready")
    return (
        f"allowed_scope_families={','.join(str(item) for item in allowed_families)};"
        f"general_platform={general_platform_ready};"
        f"scope_breadth_ready={scope_breadth.get('scope_breadth_ready')};"
        f"scope_claim_posture_ready={scope_breadth.get('scope_claim_posture_ready')};"
        f"general_platform_claim_allowed={scope_breadth.get('general_platform_claim_allowed')};"
        f"blocked_claim_scopes={','.join(str(item) for item in blocked_claim_scopes)};"
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
        f"review_only_keep_blocked={scope_breadth.get('review_only_keep_blocked_count')};"
        f"scope_acceptance_blocked_stage_count={scope_breadth.get('scope_acceptance_blocked_stage_count')};"
        f"scope_acceptance_next_stage_id={scope_breadth.get('scope_acceptance_next_stage_id')};"
        f"scope_closure_authoritative_apply_allowed={scope_closure_checklist.get('authoritative_apply_allowed')};"
        f"scope_closure_acceptance_ready={scope_closure_acceptance.get('scope_closure_acceptance_ready')}"
    )


def _live_scope_closure_detail(closure: dict[str, Any]) -> str:
    if not closure:
        return ""
    return (
        f"scope_closure_blocker_classes={_count_map_text(closure.get('blocker_class_counts'))};"
        f"scope_closure_first_scientific_blocker={_text(closure.get('first_scientific_blocker'))};"
        f"scope_closure_manual_review_subcheck_count={closure.get('manual_review_subcheck_count')};"
        f"scope_closure_transporter_manual_review_subcheck_count={closure.get('transporter_manual_review_subcheck_count')};"
        f"scope_closure_transporter_identity_scaffold_confirmation_required_count={closure.get('transporter_identity_scaffold_confirmation_required_count')};"
        f"scope_closure_transporter_direct_binding_or_kcal_confirmation_required_count={closure.get('transporter_direct_binding_or_kcal_confirmation_required_count')};"
        f"scope_closure_transporter_negative_quantitative_confirmation_required_count={closure.get('transporter_negative_quantitative_confirmation_required_count')};"
        f"scope_closure_transporter_direct_binding_missing_count={closure.get('transporter_direct_binding_missing_count')};"
        f"scope_closure_transporter_negative_quantitative_missing_count={closure.get('transporter_negative_quantitative_missing_count')};"
        f"scope_closure_pxr_reconciled_blocked_row_count={closure.get('pxr_reconciled_blocked_row_count')};"
        f"scope_closure_pxr_conflict_resolution_count={closure.get('pxr_conflict_resolution_count')};"
        f"scope_closure_pxr_quantitative_missing_count={closure.get('pxr_quantitative_missing_count')};"
        f"scope_closure_general_claim_blocker_count={closure.get('general_claim_blocker_count')};"
        f"scope_closure_ready_for_apply_count={closure.get('ready_for_apply_count')};"
        f"scope_closure_authoritative_apply_allowed={closure.get('authoritative_apply_allowed')};"
        f"scope_claim_boundary={_text(closure.get('claim_boundary_detail'))}"
    )


def _primary_backlog_detail(backlog_packet: dict[str, Any], *, live_observed: str) -> str:
    summary = _summary(backlog_packet)
    primary = _primary_backlog_row(backlog_packet)
    if not summary and not primary:
        return ""
    return (
        f"primary_backlog_work_item_id={_text(summary.get('primary_work_item_id'))};"
        f"primary_backlog_observed={live_observed};"
        f"primary_backlog_next_action={_text(primary.get('next_action'))}"
    )


def _observed_pairs(observed: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for part in _text(observed).split(";"):
        key, sep, value = part.partition("=")
        if not sep:
            continue
        pairs[key.strip()] = value.strip()
    return pairs


def _list_from_text(value: Any) -> list[str]:
    text = _text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _bool_text(value: Any) -> bool:
    return _text(value).lower() == "true"


def _counts_from_text(value: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for part in _text(value).split(","):
        key, sep, count = part.rpartition("=")
        if not sep:
            continue
        key = key.strip()
        if key:
            counts[key] = _int(count)
    return counts


def _commercial_readiness_next_action_matrix(
    *,
    production_ai_checkpoint: dict[str, Any],
    production_ai_gpu_return_intake: dict[str, Any],
    product_scope_breadth_contract: dict[str, Any],
    product_scope_acceptance_current_blocked_stage_evidence_matrix: list[dict[str, Any]] | None = None,
    pxr_exact_review: dict[str, Any],
) -> list[dict[str, Any]]:
    gpu_packet = production_ai_gpu_return_intake.get("operator_return_next_artifact_completion_packet")
    gpu_packet = gpu_packet if isinstance(gpu_packet, dict) else {}
    transporter_packet = product_scope_breadth_contract.get(
        "transporter_p0_evidence_acquisition_next_slot_completion_packet"
    )
    transporter_packet = transporter_packet if isinstance(transporter_packet, dict) else {}
    transporter_target_scope_guardrail = (
        "Ready transporter targets do not authorize blocked transporter target promotion; keep blocked "
        "targets out of scope promotion until their target-pair evidence is claim-safe."
    )
    transporter_target_scope_completion_packet = {
        "target_ready_for_promotion_ids": [
            str(item)
            for item in (
                product_scope_breadth_contract.get("transporter_target_ready_for_promotion_ids")
                or []
            )
        ],
        "target_blocked_for_promotion_ids": [
            str(item)
            for item in (
                product_scope_breadth_contract.get("transporter_target_blocked_for_promotion_ids")
                or []
            )
        ],
        "primary_blocker_target_id": _text(
            product_scope_breadth_contract.get("transporter_primary_blocker_target_id")
        ),
        "primary_blocker_packet_step": _text(
            product_scope_breadth_contract.get("transporter_primary_blocker_packet_step")
        ),
        "primary_blocker_candidate_name": _text(
            product_scope_breadth_contract.get("transporter_primary_blocker_candidate_name")
        ),
        "claim_safe_guardrail": transporter_target_scope_guardrail,
    }
    pxr_packet = pxr_exact_review.get("next_review_completion_packet")
    pxr_packet = pxr_packet if isinstance(pxr_packet, dict) else {}
    scope_acceptance = product_scope_breadth_contract.get("scope_acceptance_current_blocked_stage_evidence_matrix")
    scope_acceptance_count = len(scope_acceptance) if isinstance(scope_acceptance, list) else _int(
        product_scope_breadth_contract.get("scope_acceptance_current_blocked_stage_evidence_matrix_count")
    )
    scope_blocked_stage_ids = [
        _text(row.get("stage_id"))
        for row in scope_acceptance
        if isinstance(row, dict) and _text(row.get("stage_id"))
    ] if isinstance(scope_acceptance, list) else []
    if not scope_blocked_stage_ids:
        scope_blocked_stage_ids = [
            str(item)
            for item in (
                product_scope_breadth_contract.get("scope_acceptance_blocked_stage_ids")
                or product_scope_breadth_contract.get("scope_claim_expansion_current_blocked_stage_ids")
                or []
            )
        ]
    scope_stage_dependency_matrix: list[dict[str, Any]] = []
    for row in product_scope_acceptance_current_blocked_stage_evidence_matrix or []:
        if not isinstance(row, dict):
            continue
        first_blocked = row.get("first_blocked_evidence_row")
        first_blocked = first_blocked if isinstance(first_blocked, dict) else {}
        scope_stage_dependency_matrix.append(
            {
                "stage_id": _text(row.get("stage_id")),
                "status": _text(row.get("status")),
                "blocked_evidence_row_count": _int(row.get("blocked_evidence_row_count")),
                "first_blocked_evidence_row_id": _text(
                    first_blocked.get("evidence_row_id")
                    or first_blocked.get("review_row_id")
                    or first_blocked.get("domain")
                ),
                "first_blocked_target_id": _text(
                    first_blocked.get("target_id")
                    or first_blocked.get("target_gene")
                    or first_blocked.get("domain")
                ),
                "first_blocked_packet_step": _text(first_blocked.get("packet_step")),
                "first_blocked_candidate": _text(
                    first_blocked.get("candidate_name")
                    or first_blocked.get("replacement_ligand_id")
                    or first_blocked.get("workbook_replacement_ligand_id")
                ),
                "first_blocked_required_missing_fields": _text(
                    first_blocked.get("required_missing_fields")
                    or first_blocked.get("readiness_missing_fields")
                ),
                "first_blocked_request_mode": _text(
                    first_blocked.get("request_mode") or first_blocked.get("required_evidence_mode")
                ),
                "next_action": _text(row.get("next_action") or first_blocked.get("next_action")),
                "validation_command": _text(row.get("validation_command")),
                "unlock_claim_scopes": [
                    str(item) for item in (row.get("unlock_claim_scopes") or [])
                ],
            }
        )
    first_scope_stage_dependency = scope_stage_dependency_matrix[0] if scope_stage_dependency_matrix else {}
    scope_contract_present = bool(product_scope_breadth_contract)
    pxr_review_present = bool(pxr_exact_review)
    gpu_ready = _bool(production_ai_gpu_return_intake.get("gpu_return_artifacts_ready"))
    transporter_ready = scope_contract_present and (
        _text(product_scope_breadth_contract.get("scope_acceptance_next_stage_id"))
        != "transporter_claim_acceptance"
        and _int(product_scope_breadth_contract.get("transporter_p0_evidence_acquisition_unresolved_slot_count"))
        == 0
    )
    pxr_ready = scope_contract_present and pxr_review_present and (
        _text(product_scope_breadth_contract.get("scope_claim_expansion_current_next_stage_id"))
        != "pxr_claim_acceptance"
        and _int(pxr_exact_review.get("expected_blocked_row_count")) == 0
        and _int(pxr_exact_review.get("review_decision_placeholder_count")) == 0
    )
    breadth_ready = scope_contract_present and _bool(
        product_scope_breadth_contract.get("scope_claim_expansion_currently_satisfied")
    )
    env_actionable_check = (
        _text(production_ai_checkpoint.get("production_inference_actionable_blocker_check_id"))
        == "production_gpu_execution_environment_ready"
    )
    env_artifact = _text(
        production_ai_checkpoint.get("production_gpu_execution_environment_artifact_path")
        or (
            production_ai_checkpoint.get("production_inference_actionable_blocker_artifact")
            if env_actionable_check
            else ""
        )
        or "runs/rocm_environment_manifest_current.json"
    )
    env_ready = _bool(production_ai_checkpoint.get("production_gpu_execution_environment_ready"))
    env_actionable = env_actionable_check or "production_gpu_execution_environment_ready" in production_ai_checkpoint
    env_next_action = _text(
        production_ai_checkpoint.get("production_gpu_rocm_next_required_step")
        or (
            production_ai_checkpoint.get("production_inference_actionable_blocker_next_action")
            if env_actionable_check
            else ""
        )
        or production_ai_checkpoint.get("next_required_step")
        or "Expose at least one AMD ROCm/HIP device to PyTorch before running production regeneration."
    )
    env_worker_runtime_receipt_contract = (
        dict(production_ai_checkpoint.get("production_inference_worker_runtime_receipt_contract"))
        if isinstance(
            production_ai_checkpoint.get("production_inference_worker_runtime_receipt_contract"),
            dict,
        )
        else {}
    )
    env_worker_runtime_receipt_required_fields = [
        str(item)
        for item in (
            production_ai_checkpoint.get(
                "production_inference_worker_runtime_receipt_required_fields_or_columns"
            )
            or env_worker_runtime_receipt_contract.get("required_fields_or_columns")
            or []
        )
    ]
    env_worker_runtime_receipt_guardrails = [
        str(item)
        for item in (
            production_ai_checkpoint.get("production_inference_worker_runtime_receipt_guardrails")
            or env_worker_runtime_receipt_contract.get("guardrails")
            or []
        )
    ]
    env_diagnostic_commands = [
        str(item)
        for item in (
            production_ai_checkpoint.get("production_gpu_rocm_visibility_diagnostic_commands")
            or production_ai_checkpoint.get(
                "production_inference_actionable_operator_completion_diagnostic_commands"
            )
            or []
        )
    ]
    env_diagnostic_required_fields = [
        str(item)
        for item in (
            production_ai_checkpoint.get("production_gpu_rocm_visibility_diagnostic_required_fields")
            or production_ai_checkpoint.get(
                "production_inference_actionable_operator_completion_diagnostic_required_fields"
            )
            or []
        )
    ]
    env_diagnostic_return_artifacts = [
        str(item)
        for item in (
            production_ai_checkpoint.get("production_gpu_rocm_visibility_diagnostic_return_artifacts")
            or production_ai_checkpoint.get(
                "production_inference_actionable_operator_completion_diagnostic_return_artifacts"
            )
            or []
        )
    ]
    return_bundle_artifacts = [
        str(item) for item in (production_ai_gpu_return_intake.get("operator_return_required_artifacts") or [])
    ]
    return_bundle_next_packet = production_ai_gpu_return_intake.get(
        "operator_return_next_artifact_completion_packet"
    )
    return_bundle_next_packet = return_bundle_next_packet if isinstance(return_bundle_next_packet, dict) else {}
    return_bundle_next_artifact_id = _text(
        production_ai_gpu_return_intake.get("operator_return_next_artifact_id")
        or return_bundle_next_packet.get("artifact_id")
    )
    return_bundle_next_artifact_path = _text(
        production_ai_gpu_return_intake.get("operator_return_next_artifact_path")
        or return_bundle_next_packet.get("artifact_path")
    )
    return_bundle_next_failed_check_ids = [
        str(item)
        for item in (
            production_ai_gpu_return_intake.get("operator_return_next_artifact_failed_check_ids")
            or return_bundle_next_packet.get("failed_check_ids")
            or []
        )
    ]
    return_bundle_manifest_required_columns = [
        str(item)
        for item in (production_ai_gpu_return_intake.get("operator_return_manifest_required_columns") or [])
    ]
    return_bundle_completion_matrix = [
        dict(item)
        for item in (production_ai_gpu_return_intake.get("operator_return_artifact_completion_matrix") or [])
        if isinstance(item, dict)
    ]
    return_bundle_guardrail = (
        "Returned summary alone does not unlock production AI; manifest CSV, regenerated NPZ bundle "
        "schema/identity/operator verification, GPU backend provenance, and post-run force derivation "
        "validation must also pass."
    )
    actions: list[dict[str, Any]] = []
    if env_actionable:
        actions.append(
            {
                "action_id": "production_gpu_execution_environment",
                "gap_id": "production_ai_inference_checkpoint",
                "status": "ready" if env_ready else "blocked",
                "release_blocker": not env_ready,
                "artifact": env_artifact,
                "required_evidence": (
                    "ROCm/HIP runtime is ready with at least one visible AMD GPU device for the full "
                    "production regeneration run"
                ),
                "next_action": env_next_action,
                "validation_command": _text(
                    (
                        production_ai_checkpoint.get(
                            "production_inference_actionable_blocker_validation_command"
                        )
                        if env_actionable_check
                        else ""
                    )
                    or "python3 tools/build_rocm_environment_manifest.py"
                ),
                "execution_command": "python3 tools/build_rocm_environment_manifest.py",
                "required_operator_inputs": [
                    "manifest_ready",
                    "rocm_stack_detected",
                    "torch_rocm_ready",
                    "amd_gpu_detected",
                    "visible_device_count",
                ],
                "workstream_lane_id": "primary_gpu_environment",
                "parallelizable_with_primary_blocker": False,
                "parallel_lane_precondition": "",
                "parallel_lane_priority": 0,
                "operator_completion_packet_ready": True,
                "operator_completion_packet": {
                    "artifact_id": "rocm_environment_manifest_json",
                    "artifact_path": env_artifact,
                    "packet_ready": True,
                    "required_fields_or_columns": [
                        "manifest_ready",
                        "rocm_stack_detected",
                        "torch_rocm_ready",
                        "amd_gpu_detected",
                        "visible_device_count",
                    ],
                    "completion_rule": (
                        "manifest_ready=true; torch_rocm_ready=true; amd_gpu_detected=true; "
                        "visible_device_count>0"
                    ),
                    "validation_command": "python3 tools/build_rocm_environment_manifest.py",
                    "next_action": env_next_action,
                    "worker_runtime_receipt_contract": env_worker_runtime_receipt_contract,
                    "worker_runtime_receipt_required_fields_or_columns": (
                        env_worker_runtime_receipt_required_fields
                    ),
                    "worker_runtime_receipt_required_field_count": _int(
                        production_ai_checkpoint.get(
                            "production_inference_worker_runtime_receipt_required_field_count"
                        )
                    )
                    or len(env_worker_runtime_receipt_required_fields),
                    "worker_runtime_receipt_completion_rule": _text(
                        production_ai_checkpoint.get(
                            "production_inference_worker_runtime_receipt_completion_rule"
                        )
                        or env_worker_runtime_receipt_contract.get("completion_rule")
                    ),
                    "post_environment_next_stage_id": _text(
                        production_ai_checkpoint.get(
                            "production_inference_worker_runtime_receipt_post_environment_next_stage_id"
                        )
                        or env_worker_runtime_receipt_contract.get(
                            "post_environment_next_stage_id"
                        )
                    ),
                    "post_environment_next_artifact": _text(
                        production_ai_checkpoint.get(
                            "production_inference_worker_runtime_receipt_post_environment_next_artifact"
                        )
                        or env_worker_runtime_receipt_contract.get(
                            "post_environment_next_artifact"
                        )
                    ),
                    "post_environment_validation_command": _text(
                        production_ai_checkpoint.get(
                            "production_inference_worker_runtime_receipt_post_environment_validation_command"
                        )
                        or env_worker_runtime_receipt_contract.get(
                            "post_environment_validation_command"
                        )
                    ),
                    "full_regeneration_command": _text(
                        production_ai_checkpoint.get(
                            "production_inference_worker_runtime_receipt_full_regeneration_command"
                        )
                        or env_worker_runtime_receipt_contract.get("full_regeneration_command")
                    ),
                    "worker_runtime_receipt_guardrails": env_worker_runtime_receipt_guardrails,
                    "diagnostic_commands": env_diagnostic_commands,
                    "diagnostic_command_count": _int(
                        production_ai_checkpoint.get("production_gpu_rocm_visibility_diagnostic_command_count")
                        or production_ai_checkpoint.get(
                            "production_inference_actionable_operator_completion_diagnostic_command_count"
                        )
                    )
                    or len(env_diagnostic_commands),
                    "diagnostic_required_fields": env_diagnostic_required_fields,
                    "diagnostic_required_field_count": _int(
                        production_ai_checkpoint.get(
                            "production_gpu_rocm_visibility_diagnostic_required_field_count"
                        )
                        or production_ai_checkpoint.get(
                            "production_inference_actionable_operator_completion_diagnostic_required_field_count"
                        )
                    )
                    or len(env_diagnostic_required_fields),
                    "diagnostic_completion_rule": _text(
                        production_ai_checkpoint.get("production_gpu_rocm_visibility_diagnostic_completion_rule")
                        or production_ai_checkpoint.get(
                            "production_inference_actionable_operator_completion_diagnostic_completion_rule"
                        )
                    ),
                    "diagnostic_return_artifacts": env_diagnostic_return_artifacts,
                    "torch_visibility_probe_command": _text(
                        production_ai_checkpoint.get(
                            "production_inference_actionable_operator_completion_torch_visibility_probe_command"
                        )
                    ),
                },
                "unlock_claim": "production_ai_full_gpu_regeneration_authority",
                "next_after_actionable_blocker_stage_id": _text(
                    (
                        production_ai_checkpoint.get(
                        "production_inference_next_after_actionable_blocker_stage_id"
                    )
                        if env_actionable_check
                        else ""
                    )
                ),
                "next_after_actionable_blocker_artifact": _text(
                    (
                        production_ai_checkpoint.get(
                        "production_inference_next_after_actionable_blocker_artifact"
                    )
                        if env_actionable_check
                        else ""
                    )
                ),
                "next_after_actionable_blocker_validation_command": _text(
                    (
                        production_ai_checkpoint.get(
                        "production_inference_next_after_actionable_blocker_validation_command"
                    )
                        if env_actionable_check
                        else ""
                    )
                ),
                "next_after_actionable_blocker_required_checks": [
                    str(item)
                    for item in (
                        (
                            production_ai_checkpoint.get(
                            "production_inference_next_after_actionable_blocker_required_checks"
                        )
                            if env_actionable_check
                            else []
                        )
                        or []
                    )
                ],
                "next_after_actionable_blocker_unlock_fields": [
                    str(item)
                    for item in (
                        (
                            production_ai_checkpoint.get(
                            "production_inference_next_after_actionable_blocker_unlock_fields"
                        )
                            if env_actionable_check
                            else []
                        )
                        or []
                    )
                ],
                "next_after_actionable_blocker_next_action": _text(
                    (
                        production_ai_checkpoint.get(
                        "production_inference_next_after_actionable_blocker_next_action"
                    )
                        if env_actionable_check
                        else ""
                    )
                ),
            }
        )
    actions.extend(
        [
        {
            "action_id": "production_ai_return_summary",
            "gap_id": "production_ai_inference_checkpoint",
            "status": "ready" if gpu_ready else "blocked",
            "release_blocker": not gpu_ready,
            "artifact": _text(
                production_ai_gpu_return_intake.get("operator_return_next_artifact_path")
                or gpu_packet.get("artifact_path")
                or production_ai_gpu_return_intake.get("actual_summary_return_path")
            ),
            "required_evidence": _text(
                gpu_packet.get("completion_rule")
                or production_ai_gpu_return_intake.get("summary_template_completion_rule")
            ),
            "next_action": _text(
                gpu_packet.get("next_action")
                or production_ai_gpu_return_intake.get("first_failed_next_action")
                or production_ai_gpu_return_intake.get("next_required_step")
            ),
            "validation_command": _text(
                gpu_packet.get("validation_command")
                or production_ai_gpu_return_intake.get("post_return_validation_command")
            ),
            "execution_command": _text(
                gpu_packet.get("full_regeneration_command")
                or production_ai_gpu_return_intake.get("operator_return_handoff_full_regeneration_command")
            ),
            "required_operator_inputs": [
                str(item)
                for item in (
                    gpu_packet.get("required_fields_or_columns")
                    or production_ai_gpu_return_intake.get("summary_template_required_fields")
                    or []
                )
            ],
            "operator_completion_packet_ready": bool(gpu_packet),
            "operator_completion_packet": dict(gpu_packet),
            "return_bundle_required_artifacts": return_bundle_artifacts,
            "return_bundle_required_artifact_count": _int(
                production_ai_gpu_return_intake.get("operator_return_required_artifact_count")
            )
            or len(return_bundle_artifacts),
            "return_bundle_artifact_completion_matrix": return_bundle_completion_matrix,
            "return_bundle_artifact_completion_matrix_count": _int(
                production_ai_gpu_return_intake.get("operator_return_artifact_completion_matrix_count")
            )
            or len(return_bundle_completion_matrix),
            "return_bundle_next_artifact_id": return_bundle_next_artifact_id,
            "return_bundle_next_artifact_path": return_bundle_next_artifact_path,
            "return_bundle_next_artifact_failed_check_ids": return_bundle_next_failed_check_ids,
            "return_bundle_manifest_required_columns": return_bundle_manifest_required_columns,
            "return_bundle_post_return_validation_command": _text(
                production_ai_gpu_return_intake.get("post_return_validation_command")
            ),
            "return_bundle_guardrail": return_bundle_guardrail,
            "workstream_lane_id": "gpu_return_after_environment",
            "parallelizable_with_primary_blocker": False,
            "parallel_lane_precondition": "production_gpu_execution_environment_ready",
            "parallel_lane_priority": 0,
            "blocked_by_action_id": "production_gpu_execution_environment",
            "unlock_claim": "production_ai_inference_subject",
        },
        {
            "action_id": "transporter_next_slot_exact_evidence",
            "gap_id": "scope_breadth_expansion",
            "status": "ready" if transporter_ready else "blocked",
            "release_blocker": not transporter_ready,
            "artifact": _text(
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_next_slot_operator_review_artifact"
                )
                or product_scope_breadth_contract.get("scope_acceptance_next_stage_artifact")
            ),
            "required_evidence": _text(
                transporter_packet.get("required_evidence_type")
                or product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_first_request_mode"
                )
                or "exact target-pair quantitative transporter evidence"
            ),
            "next_action": _text(
                transporter_packet.get("next_action")
                or product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_first_next_required_action"
                )
                or product_scope_breadth_contract.get("scope_acceptance_next_stage_next_action")
            ),
            "validation_command": _text(
                product_scope_breadth_contract.get("scope_acceptance_next_stage_validation_command")
            ),
            "execution_command": _text(
                product_scope_breadth_contract.get("scope_acceptance_next_stage_validation_command")
            ),
            "required_operator_inputs": [
                str(item) for item in (transporter_packet.get("required_operator_intake_columns") or [])
            ],
            "required_exact_evidence_fields": [
                str(item) for item in (transporter_packet.get("required_exact_evidence_fields") or [])
            ],
            "required_claim_guardrails": [
                str(item) for item in (transporter_packet.get("required_claim_guardrails") or [])
            ],
            "claim_safe_completion_rule": _text(transporter_packet.get("completion_rule")),
            "next_slot_source_modality_guard_ready": _bool(
                transporter_packet.get("next_slot_source_modality_guard_ready")
            ),
            "next_slot_source_modality": _text(
                transporter_packet.get("next_slot_source_modality")
            ),
            "next_slot_source_modality_claim_safe": _bool(
                transporter_packet.get("next_slot_source_modality_claim_safe")
            ),
            "next_slot_source_modality_direct_binding_claim_allowed": _bool(
                transporter_packet.get("next_slot_source_modality_direct_binding_claim_allowed")
            ),
            "next_slot_source_modality_decision": _text(
                transporter_packet.get("next_slot_source_modality_decision")
            ),
            "next_slot_source_modality_guardrails": [
                str(item)
                for item in (
                    transporter_packet.get("next_slot_source_modality_guardrails") or []
                )
            ],
            "next_slot_source_modality_observed_signal": _text(
                transporter_packet.get("next_slot_source_modality_observed_signal")
            ),
            "next_slot_source_modality_required_upgrade": _text(
                transporter_packet.get("next_slot_source_modality_required_upgrade")
            ),
            "next_slot_source_modality_triage_artifact": _text(
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_artifact"
                )
            ),
            "next_slot_source_modality_triage_decision": _text(
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_decision"
                )
            ),
            "next_slot_source_modality_direct_experimental_binding_row_count": _int(
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_experimental_binding_row_count"
                )
            ),
            "next_slot_source_modality_claim_safe_binding_kcal_ready_count": _int(
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count"
                )
            ),
            "next_slot_source_modality_computational_binding_energy_row_count": _int(
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_computational_binding_energy_row_count"
                )
            ),
            "next_slot_source_modality_best_computational_binding_energy_kcal_mol": _text(
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol"
                )
            ),
            "operator_completion_packet_ready": bool(transporter_packet),
            "operator_completion_packet": dict(transporter_packet),
            "return_bundle_required_artifacts": [
                str(item)
                for item in (
                    transporter_packet.get("return_bundle_required_artifacts")
                    or product_scope_breadth_contract.get(
                        "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts"
                    )
                    or []
                )
            ],
            "return_bundle_required_artifact_count": _int(
                transporter_packet.get("return_bundle_required_artifact_count")
                or product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count"
                )
            ),
            "return_bundle_artifact_completion_matrix": [
                dict(row)
                for row in (
                    product_scope_breadth_contract.get(
                        "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix"
                    )
                    or transporter_packet.get("return_bundle_completion_matrix")
                    or []
                )
                if isinstance(row, dict)
            ],
            "return_bundle_artifact_completion_matrix_count": _int(
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count"
                )
            ),
            "return_bundle_blocker_count": _int(
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count"
                )
            ),
            "return_bundle_next_artifact_id": _text(
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id"
                )
            ),
            "return_bundle_next_artifact_path": _text(
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path"
                )
            ),
            "return_bundle_next_artifact_failed_check_ids": [
                str(item)
                for item in (
                    product_scope_breadth_contract.get(
                        "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_failed_check_ids"
                    )
                    or []
                )
            ],
            "target_scope_completion_packet": transporter_target_scope_completion_packet,
            "target_scope_guardrail": transporter_target_scope_guardrail,
            "target_ready_for_promotion_ids": transporter_target_scope_completion_packet[
                "target_ready_for_promotion_ids"
            ],
            "target_blocked_for_promotion_ids": transporter_target_scope_completion_packet[
                "target_blocked_for_promotion_ids"
            ],
            "primary_blocker_target_id": transporter_target_scope_completion_packet[
                "primary_blocker_target_id"
            ],
            "primary_blocker_packet_step": transporter_target_scope_completion_packet[
                "primary_blocker_packet_step"
            ],
            "primary_blocker_candidate_name": transporter_target_scope_completion_packet[
                "primary_blocker_candidate_name"
            ],
            "workstream_lane_id": "parallel_scope_evidence",
            "parallelizable_with_primary_blocker": True,
            "parallel_lane_precondition": (
                "Can be completed while ROCm/GPU environment is being prepared; does not require "
                "production GPU execution."
            ),
            "parallel_lane_priority": 1,
            "parallel_primary_blocker_action_id": (
                "production_gpu_execution_environment" if env_actionable and not env_ready else ""
            ),
            "unlock_claim": "transporter_domain_promotion",
            "next_slot_id": _text(
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_next_slot_id"
                )
                or transporter_packet.get("slot_id")
            ),
            "candidate_ligand_id": _text(transporter_packet.get("candidate_ligand_id")),
        },
        {
            "action_id": "pxr_next_exact_review",
            "gap_id": "scope_breadth_expansion",
            "status": "ready" if pxr_ready else "blocked",
            "release_blocker": not pxr_ready,
            "artifact": _text(
                pxr_exact_review.get("next_review_operator_review_artifact")
                or "runs/pxr_exact_evidence_review_intake_template_current.csv"
            ),
            "required_evidence": "exact human NR1I2/PXR kcal/source/assay/target-match/conflict decision",
            "next_action": _text(pxr_exact_review.get("next_required_step")),
            "validation_command": "python3 tools/build_pxr_exact_evidence_review_intake_template.py",
            "execution_command": "python3 tools/build_pxr_exact_evidence_review_intake_template.py",
            "required_operator_inputs": [
                str(item) for item in (pxr_packet.get("required_operator_intake_columns") or [])
            ],
            "required_exact_evidence_fields": [
                str(item)
                for item in (
                    pxr_packet.get("required_exact_evidence_fields")
                    or pxr_packet.get("required_operator_intake_columns")
                    or []
                )
            ],
            "required_claim_guardrails": [
                str(item) for item in (pxr_packet.get("required_claim_guardrails") or [])
            ],
            "claim_safe_completion_rule": _text(pxr_packet.get("completion_rule")),
            "operator_completion_packet_ready": bool(pxr_packet),
            "operator_completion_packet": dict(pxr_packet),
            "return_bundle_required_artifacts": [
                str(item)
                for item in (
                    pxr_exact_review.get("next_review_return_bundle_required_artifacts")
                    or pxr_packet.get("return_bundle_required_artifacts")
                    or []
                )
            ],
            "return_bundle_required_artifact_count": _int(
                pxr_exact_review.get("next_review_return_bundle_required_artifact_count")
                or pxr_packet.get("return_bundle_required_artifact_count")
            ),
            "return_bundle_blocker_count": _int(
                pxr_exact_review.get("next_review_return_bundle_blocker_count")
            ),
            "return_bundle_next_artifact_id": _text(
                pxr_exact_review.get("next_review_return_bundle_next_artifact_id")
            ),
            "return_bundle_next_artifact_path": _text(
                pxr_exact_review.get("next_review_return_bundle_next_artifact_path")
            ),
            "return_bundle_next_artifact_failed_check_ids": [
                str(item)
                for item in (
                    pxr_exact_review.get("next_review_return_bundle_next_artifact_failed_check_ids") or []
                )
            ],
            "return_bundle_artifact_completion_matrix": [
                dict(item)
                for item in (
                    pxr_exact_review.get("next_review_return_bundle_completion_matrix") or []
                )
                if isinstance(item, dict)
            ],
            "workstream_lane_id": "parallel_scope_evidence",
            "parallelizable_with_primary_blocker": True,
            "parallel_lane_precondition": (
                "Can be completed while ROCm/GPU environment is being prepared; does not require "
                "production GPU execution."
            ),
            "parallel_lane_priority": 2,
            "parallel_primary_blocker_action_id": (
                "production_gpu_execution_environment" if env_actionable and not env_ready else ""
            ),
            "unlock_claim": "pxr_domain_promotion",
            "next_review_row_id": _text(pxr_exact_review.get("next_review_row_id") or pxr_packet.get("review_row_id")),
            "candidate_name": _text(pxr_exact_review.get("next_review_candidate_name") or pxr_packet.get("candidate_name")),
        },
        {
            "action_id": "broad_platform_claim_floor",
            "gap_id": "scope_breadth_expansion",
            "status": "ready" if breadth_ready else "blocked",
            "release_blocker": not breadth_ready,
            "artifact": DEFAULT_PRODUCT_SCOPE_BREADTH_CONTRACT_JSON,
            "required_evidence": "transporter and PXR acceptance stages ready; broad platform claim remains blocked until breadth floor passes",
            "next_action": _text(
                product_scope_breadth_contract.get("scope_claim_expansion_current_next_stage_validation_command")
                or product_scope_breadth_contract.get("scope_acceptance_next_stage_validation_command")
            ),
            "validation_command": "python3 tools/build_product_scope_breadth_contract.py",
            "execution_command": _text(
                product_scope_breadth_contract.get("scope_claim_expansion_current_next_stage_validation_command")
                or "python3 tools/build_product_scope_breadth_contract.py"
            ),
            "required_operator_inputs": scope_blocked_stage_ids,
            "required_claim_guardrails": [
                "general_platform_claim_allowed_false_until_all_scope_acceptance_stages_green",
                "transporter_and_pxr_domain_promotions_required_before_general_platform_claim",
                "breadth_domain_floor_acceptance_required_before_capability_surface_widening",
                "ready_restricted_families_do_not_authorize_general_protein_ligand_claim",
            ],
            "claim_safe_completion_rule": (
                "Keep general protein-ligand platform wording blocked until transporter, PXR, "
                "breadth-domain floor, and capability-surface acceptance stages are all green."
            ),
            "operator_completion_packet_ready": scope_contract_present,
            "operator_completion_packet": {
                "blocked_stage_evidence_count": scope_acceptance_count,
                "blocked_stage_ids": scope_blocked_stage_ids,
                "blocked_stage_dependency_matrix": scope_stage_dependency_matrix,
                "first_blocked_stage_id": _text(first_scope_stage_dependency.get("stage_id")),
                "first_blocked_evidence_row_id": _text(
                    first_scope_stage_dependency.get("first_blocked_evidence_row_id")
                ),
                "first_blocked_required_missing_fields": _text(
                    first_scope_stage_dependency.get("first_blocked_required_missing_fields")
                ),
                "first_blocked_target_id": _text(
                    first_scope_stage_dependency.get("first_blocked_target_id")
                ),
                "first_blocked_candidate": _text(
                    first_scope_stage_dependency.get("first_blocked_candidate")
                ),
                "required_claim_guardrails": [
                    "general_platform_claim_allowed_false_until_all_scope_acceptance_stages_green",
                    "transporter_and_pxr_domain_promotions_required_before_general_platform_claim",
                    "breadth_domain_floor_acceptance_required_before_capability_surface_widening",
                    "ready_restricted_families_do_not_authorize_general_protein_ligand_claim",
                ],
                "completion_rule": (
                    "Keep general protein-ligand platform wording blocked until transporter, PXR, "
                    "breadth-domain floor, and capability-surface acceptance stages are all green."
                ),
                "scope_acceptance_artifact": DEFAULT_PRODUCT_SCOPE_BREADTH_CONTRACT_JSON,
            },
            "unlock_claim": "general_protein_ligand_platform",
            "blocked_stage_evidence_count": scope_acceptance_count,
            "blocked_stage_dependency_matrix": scope_stage_dependency_matrix,
            "blocked_stage_dependency_count": len(scope_stage_dependency_matrix),
            "first_blocked_stage_id": _text(first_scope_stage_dependency.get("stage_id")),
            "first_blocked_evidence_row_id": _text(
                first_scope_stage_dependency.get("first_blocked_evidence_row_id")
            ),
            "first_blocked_target_id": _text(
                first_scope_stage_dependency.get("first_blocked_target_id")
            ),
            "first_blocked_candidate": _text(
                first_scope_stage_dependency.get("first_blocked_candidate")
            ),
            "first_blocked_required_missing_fields": _text(
                first_scope_stage_dependency.get("first_blocked_required_missing_fields")
            ),
            "workstream_lane_id": "scope_claim_floor_after_evidence",
            "parallelizable_with_primary_blocker": True,
            "parallel_lane_precondition": (
                "Can be prepared while ROCm/GPU environment is being prepared, but cannot unlock broad "
                "claims until transporter/PXR evidence stages are green."
            ),
            "parallel_lane_priority": 3,
            "parallel_primary_blocker_action_id": (
                "production_gpu_execution_environment" if env_actionable and not env_ready else ""
            ),
        },
        ]
    )
    return actions


def _row(
    *,
    requirement_id: str,
    requirement: str,
    passed: bool,
    observed: str,
    required: str,
    evidence_artifacts: str,
    blocker: str = "",
    approval_token_required: str = "",
    next_command: str = "",
    release_blocker: bool = True,
    requirement_tier: str = "release",
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "requirement": requirement,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "evidence_artifacts": evidence_artifacts,
        "blocker": blocker if not passed else "",
        "approval_token_required": approval_token_required if not passed else "",
        "next_command": next_command if not passed else "",
        "release_blocker": bool(release_blocker and not passed),
        "requirement_tier": requirement_tier,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_product_goal_completion_audit(
    *,
    architecture_packet: dict[str, Any],
    release_dossier_packet: dict[str, Any],
    public_benchmark_packet: dict[str, Any],
    commercial_independence_packet: dict[str, Any],
    license_work_order_packet: dict[str, Any],
    cameo_architecture_packet: dict[str, Any],
    release_gate_packet: dict[str, Any],
    bottleneck_packet: dict[str, Any],
    burndown_packet: dict[str, Any],
    product_ai_architecture_gap_packet: dict[str, Any] | None = None,
    product_ai_execution_backlog_packet: dict[str, Any] | None = None,
    residual_model_registry_packet: dict[str, Any] | None = None,
    production_ai_checkpoint_readiness_packet: dict[str, Any] | None = None,
    production_ai_gpu_return_intake_packet: dict[str, Any] | None = None,
    production_ai_promotion_workbench_packet: dict[str, Any] | None = None,
    product_scope_breadth_contract_packet: dict[str, Any] | None = None,
    scope_evidence_priority_packet: dict[str, Any] | None = None,
    scope_evidence_intake_readiness_packet: dict[str, Any] | None = None,
    scope_breadth_evidence_receipt_packet: dict[str, Any] | None = None,
    pxr_exact_review_intake_packet: dict[str, Any] | None = None,
    commercial_readiness_handoff_bundle_packet: dict[str, Any] | None = None,
    delta_force_closure_acceptance_packet: dict[str, Any] | None = None,
    scope_closure_acceptance_packet: dict[str, Any] | None = None,
    product_scope_breadth_closure_checklist_packet: dict[str, Any] | None = None,
    report_ux_packet: dict[str, Any] | None = None,
    trajectory_sla_packet: dict[str, Any] | None = None,
    security_deployment_packet: dict[str, Any] | None = None,
    decision_graph_packet: dict[str, Any] | None = None,
    service_boundary_packet: dict[str, Any] | None = None,
    product_api_contract_packet: dict[str, Any] | None = None,
    job_orchestration_packet: dict[str, Any] | None = None,
    engine_refinement_tier_readiness_packet: dict[str, Any] | None = None,
    architecture_path: str = DEFAULT_ARCHITECTURE_JSON,
    release_dossier_path: str = DEFAULT_RELEASE_DOSSIER_JSON,
    public_benchmark_path: str = DEFAULT_PUBLIC_BENCHMARK_JSON,
    commercial_independence_path: str = DEFAULT_COMMERCIAL_INDEPENDENCE_JSON,
    license_work_order_path: str = DEFAULT_LICENSE_WORK_ORDER_JSON,
    cameo_architecture_path: str = DEFAULT_CAMEO_ARCHITECTURE_JSON,
    release_gate_path: str = DEFAULT_RELEASE_GATE_JSON,
    bottleneck_path: str = DEFAULT_BOTTLENECK_JSON,
    burndown_path: str = DEFAULT_BURNDOWN_JSON,
    product_ai_architecture_gap_path: str = DEFAULT_PRODUCT_AI_ARCHITECTURE_GAP_JSON,
    product_ai_execution_backlog_path: str = DEFAULT_PRODUCT_AI_EXECUTION_BACKLOG_JSON,
    residual_model_registry_path: str = DEFAULT_RESIDUAL_MODEL_REGISTRY_JSON,
    production_ai_checkpoint_readiness_path: str = DEFAULT_PRODUCTION_AI_CHECKPOINT_READINESS_JSON,
    production_ai_gpu_return_intake_path: str = DEFAULT_PRODUCTION_AI_GPU_RETURN_INTAKE_JSON,
    production_ai_promotion_workbench_path: str = DEFAULT_PRODUCTION_AI_PROMOTION_WORKBENCH_JSON,
    product_scope_breadth_contract_path: str = DEFAULT_PRODUCT_SCOPE_BREADTH_CONTRACT_JSON,
    scope_evidence_priority_path: str = DEFAULT_SCOPE_EVIDENCE_PRIORITY_JSON,
    scope_evidence_intake_readiness_path: str = DEFAULT_SCOPE_EVIDENCE_INTAKE_READINESS_JSON,
    scope_breadth_evidence_receipt_path: str = DEFAULT_SCOPE_BREADTH_EVIDENCE_RECEIPT_JSON,
    pxr_exact_review_intake_path: str = DEFAULT_PXR_EXACT_REVIEW_INTAKE_JSON,
    commercial_readiness_handoff_bundle_path: str = DEFAULT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_JSON,
    delta_force_closure_acceptance_path: str = DEFAULT_DELTA_FORCE_CLOSURE_ACCEPTANCE_JSON,
    scope_closure_acceptance_path: str = DEFAULT_SCOPE_CLOSURE_ACCEPTANCE_JSON,
    product_scope_breadth_closure_checklist_path: str = DEFAULT_SCOPE_CLOSURE_CHECKLIST_JSON,
    report_ux_path: str = DEFAULT_REPORT_UX_JSON,
    trajectory_sla_path: str = DEFAULT_TRAJECTORY_SLA_JSON,
    security_deployment_path: str = DEFAULT_SECURITY_DEPLOYMENT_JSON,
    decision_graph_path: str = DEFAULT_DECISION_GRAPH_JSON,
    service_boundary_path: str = DEFAULT_SERVICE_BOUNDARY_JSON,
    product_api_contract_path: str = DEFAULT_PRODUCT_API_CONTRACT_JSON,
    job_orchestration_path: str = DEFAULT_JOB_ORCHESTRATION_JSON,
    engine_refinement_tier_readiness_path: str = DEFAULT_ENGINE_REFINEMENT_TIER_READINESS_JSON,
) -> dict[str, Any]:
    architecture = _summary(architecture_packet)
    release_dossier = _summary(release_dossier_packet)
    public_benchmark = _summary(public_benchmark_packet)
    commercial = _summary(commercial_independence_packet)
    license_work_order = _summary(license_work_order_packet)
    cameo = _summary(cameo_architecture_packet)
    release_gate = _summary(release_gate_packet)
    bottleneck = _summary(bottleneck_packet)
    product_ai_architecture = _summary(product_ai_architecture_gap_packet or {})
    product_ai_backlog = _summary(product_ai_execution_backlog_packet or {})
    residual_model_registry = _summary(residual_model_registry_packet or {})
    production_ai_checkpoint = _summary(production_ai_checkpoint_readiness_packet or {})
    raw_production_ai_checkpoint_acceptance_matrix = (
        (production_ai_checkpoint_readiness_packet or {}).get("production_inference_acceptance_matrix")
        if isinstance(production_ai_checkpoint_readiness_packet or {}, dict)
        else []
    )
    production_ai_checkpoint_acceptance_matrix = [
        dict(row)
        for row in (raw_production_ai_checkpoint_acceptance_matrix or [])
        if isinstance(row, dict)
    ]
    production_ai_checkpoint_acceptance_current_blocked_stage_matrix = [
        row for row in production_ai_checkpoint_acceptance_matrix if _text(row.get("status")) != "ready"
    ]
    production_ai_checkpoint_acceptance_release_blocker_stage_ids = [
        _text(row.get("stage_id"))
        for row in production_ai_checkpoint_acceptance_matrix
        if row.get("release_blocker") is True and _text(row.get("stage_id"))
    ]
    production_ai_gpu_return_intake = _summary(production_ai_gpu_return_intake_packet or {})
    production_ai_gpu_return_blocker_matrix = [
        dict(row)
        for row in ((production_ai_gpu_return_intake_packet or {}).get("blockers") or [])
        if isinstance(row, dict)
    ]
    production_ai_gpu_return_operator_acceptance_matrix = [
        dict(row)
        for row in ((production_ai_gpu_return_intake_packet or {}).get("operator_acceptance_matrix") or [])
        if isinstance(row, dict)
    ]
    production_ai_gpu_return_operator_acceptance_current_blocked_stage_matrix = [
        row
        for row in production_ai_gpu_return_operator_acceptance_matrix
        if _text(row.get("status")) != "ready"
    ]
    production_ai_gpu_return_operator_return_artifact_completion_matrix = [
        dict(row)
        for row in (
            (production_ai_gpu_return_intake_packet or {}).get(
                "operator_return_artifact_completion_matrix"
            )
            or []
        )
        if isinstance(row, dict)
    ]
    production_ai_gpu_return_operator_return_artifact_completion_blocker_matrix = [
        dict(row)
        for row in (
            (production_ai_gpu_return_intake_packet or {}).get(
                "operator_return_artifact_completion_blocker_matrix"
            )
            or []
        )
        if isinstance(row, dict)
    ]
    production_ai_promotion_workbench = _summary(production_ai_promotion_workbench_packet or {})
    product_scope_breadth_contract = _summary(product_scope_breadth_contract_packet or {})
    raw_scope_acceptance_matrix = (
        (product_scope_breadth_contract_packet or {}).get("scope_acceptance_matrix")
        if isinstance(product_scope_breadth_contract_packet or {}, dict)
        else []
    )
    product_scope_acceptance_matrix = [
        dict(row) for row in (raw_scope_acceptance_matrix or []) if isinstance(row, dict)
    ]
    product_scope_acceptance_current_blocked_stage_matrix = [
        row for row in product_scope_acceptance_matrix if _text(row.get("status")) != "ready"
    ]
    raw_scope_stage_evidence_matrix = (
        (product_scope_breadth_contract_packet or {}).get("scope_acceptance_stage_evidence_matrix")
        if isinstance(product_scope_breadth_contract_packet or {}, dict)
        else []
    )
    product_scope_acceptance_stage_evidence_matrix = [
        dict(row) for row in (raw_scope_stage_evidence_matrix or []) if isinstance(row, dict)
    ]
    raw_scope_current_blocked_stage_evidence_matrix = (
        (product_scope_breadth_contract_packet or {}).get(
            "scope_acceptance_current_blocked_stage_evidence_matrix"
        )
        if isinstance(product_scope_breadth_contract_packet or {}, dict)
        else []
    )
    product_scope_acceptance_current_blocked_stage_evidence_matrix = [
        dict(row)
        for row in (raw_scope_current_blocked_stage_evidence_matrix or [])
        if isinstance(row, dict)
    ]
    product_scope_acceptance_release_blocker_stage_ids = [
        _text(row.get("stage_id"))
        for row in product_scope_acceptance_matrix
        if row.get("release_blocker") is True and _text(row.get("stage_id"))
    ]
    scope_priority = _summary(scope_evidence_priority_packet or {})
    scope_top_priority = _top_priority_row(scope_evidence_priority_packet or {})
    scope_intake = _summary(scope_evidence_intake_readiness_packet or {})
    scope_breadth_evidence_receipt = _summary(scope_breadth_evidence_receipt_packet or {})
    pxr_exact_review = _summary(pxr_exact_review_intake_packet or {})
    commercial_handoff = _summary(commercial_readiness_handoff_bundle_packet or {})
    delta_force_closure = _summary(delta_force_closure_acceptance_packet or {})
    scope_closure = _summary(scope_closure_acceptance_packet or {})
    scope_closure_checklist = _summary(product_scope_breadth_closure_checklist_packet or {})
    commercial_next_action_matrix = _commercial_readiness_next_action_matrix(
        production_ai_checkpoint=production_ai_checkpoint,
        production_ai_gpu_return_intake=production_ai_gpu_return_intake,
        product_scope_breadth_contract=product_scope_breadth_contract,
        product_scope_acceptance_current_blocked_stage_evidence_matrix=(
            product_scope_acceptance_current_blocked_stage_evidence_matrix
        ),
        pxr_exact_review=pxr_exact_review,
    )
    commercial_next_action_blocker_matrix = [
        row for row in commercial_next_action_matrix if _text(row.get("status")) != "ready"
    ]
    commercial_first_next_action = (
        commercial_next_action_blocker_matrix[0] if commercial_next_action_blocker_matrix else {}
    )
    primary_backlog = _primary_backlog_row(product_ai_execution_backlog_packet or {})
    report_ux = _summary(report_ux_packet or {})
    trajectory_sla = _summary(trajectory_sla_packet or {})
    security_deployment = _summary(security_deployment_packet or {})
    decision_graph = _summary(decision_graph_packet or {})
    service_boundary = _summary(service_boundary_packet or {})
    product_api_contract = _summary(product_api_contract_packet or {})
    job_orchestration = _summary(job_orchestration_packet or {})
    engine_refinement = _summary(engine_refinement_tier_readiness_packet or {})
    engine_refinement_claim_action_rows = [
        dict(row)
        for row in ((engine_refinement_tier_readiness_packet or {}).get("claim_promotion_action_rows") or [])
        if isinstance(row, dict)
    ]
    engine_refinement_claim_blockers = [
        str(item) for item in (engine_refinement.get("claim_promotion_blockers") or [])
    ]
    engine_refinement_claim_action_row_count = _int(
        engine_refinement.get("claim_promotion_action_row_count")
    )
    if not engine_refinement_claim_action_row_count and engine_refinement_claim_action_rows:
        engine_refinement_claim_action_row_count = len(engine_refinement_claim_action_rows)
    engine_refinement_claim_blocker_count = _int(
        engine_refinement.get("claim_promotion_blocker_count")
    )
    if not engine_refinement_claim_blocker_count and engine_refinement_claim_blockers:
        engine_refinement_claim_blocker_count = len(engine_refinement_claim_blockers)
    engine_refinement_claim_evidence_receipt_ready = _bool(
        engine_refinement.get("claim_promotion_evidence_receipt_ready")
    )
    engine_refinement_claim_promotion_ready = (
        not engine_refinement
        or all(
            [
                _bool(engine_refinement.get("claim_promotion_allowed")),
                engine_refinement_claim_evidence_receipt_ready,
                engine_refinement_claim_blocker_count == 0,
                engine_refinement_claim_action_row_count == 0,
                _bool(engine_refinement.get("claim_grade_public_benchmark_ready")),
            ]
        )
    )
    gap_observed_live_inputs = {
        "registry": residual_model_registry,
        "production_ai_checkpoint": production_ai_checkpoint,
        "report_ux": report_ux,
        "trajectory_sla": trajectory_sla,
        "security": security_deployment,
        "decision_graph": decision_graph,
        "service": service_boundary,
        "api": product_api_contract,
        "job_contract": job_orchestration,
        "gap_packet": product_ai_architecture_gap_packet or {},
        "scope_breadth": product_scope_breadth_contract,
        "capability": product_scope_breadth_contract,
        "scope_closure_checklist": scope_closure_checklist,
        "scope_closure_acceptance": scope_closure,
    }
    primary_observed_pairs = _live_primary_observed_pairs(
        production_ai_gpu_return_intake=production_ai_gpu_return_intake,
        production_ai_checkpoint=production_ai_checkpoint,
        residual_model_registry=residual_model_registry,
    )
    live_primary_backlog_observed = _live_primary_backlog_observed_string(primary_observed_pairs)
    product_ai_backlog_detail = _primary_backlog_detail(
        product_ai_execution_backlog_packet or {},
        live_observed=live_primary_backlog_observed,
    )
    live_scope_closure_detail = _live_scope_closure_detail(scope_closure_checklist)
    product_ai_scope_backlog_detail = live_scope_closure_detail or _text(
        product_ai_backlog.get("scope_closure_detail")
    )
    scope_observed_pairs = _observed_pairs(product_ai_scope_backlog_detail)
    scope_claim_boundary_pairs = _observed_pairs(scope_observed_pairs.get("scope_claim_boundary", ""))
    current_scope_ready_domains = [
        str(item) for item in (product_scope_breadth_contract.get("ready_domains") or [])
    ]
    current_scope_missing_domains = [
        str(item) for item in (product_scope_breadth_contract.get("missing_domains") or [])
    ]
    current_scope_blocked_claim_scopes = [
        str(item) for item in (product_scope_breadth_contract.get("blocked_claim_scopes") or [])
    ]
    current_scope_claim_blocked_domains = [
        item for item in current_scope_missing_domains if item != "general_protein_ligand"
    ]
    current_scope_allowed_families = [
        str(item) for item in (product_scope_breadth_contract.get("allowed_scope_families") or [])
    ]
    pxr_currently_ready = "pxr" in current_scope_ready_domains
    scope_breadth_evidence_receipt_ready = _bool(
        scope_breadth_evidence_receipt.get("full_scope_evidence_receipt_ready")
    )

    primary_phase = _text(bottleneck.get("primary_bottleneck_phase"))
    primary_kind = _text(bottleneck.get("primary_bottleneck_kind"))
    approval_tokens = list(bottleneck.get("approval_tokens_required") or [])
    primary_next_command = _primary_bottleneck_command(burndown_packet, primary_phase)
    primary_next_command_candidates = _primary_bottleneck_command_candidates(burndown_packet, primary_phase)
    primary_token = _join(approval_tokens)

    local_product_ready = all(
        [
            _bool(architecture.get("structure_analysis_product_surface_ready")),
            _bool(architecture.get("ligand_docking_execution_contract_ready")),
            _bool(architecture.get("scoring_ranking_contract_ready")),
            _bool(architecture.get("local_delivery_bundle_validation_ready")),
            _bool(architecture.get("product_service_boundary_ready")),
            _bool(architecture.get("product_api_contract_ready")),
            _bool(commercial.get("local_self_hosted_operation_ready")),
            _int(commercial.get("external_saas_runtime_dependency_count")) == 0,
        ]
    )
    benchmark_ready = all(
        [
            _bool(public_benchmark.get("public_benchmark_validation_ready")),
            _int(public_benchmark.get("ready_required_suite_count")) >= 5,
            _int(public_benchmark.get("blocked_suite_count")) == 0,
            _int(public_benchmark.get("suite_no_external_dependency_count")) >= 5,
            _bool(architecture.get("public_benchmark_validation_ready")),
            not _bool(architecture.get("public_benchmark_requires_24h_server")),
            not _bool(architecture.get("public_benchmark_requires_competition_season")),
            not _bool(architecture.get("public_benchmark_requires_paid_vps")),
        ]
    )
    commercial_ready = all(
        [
            _text(commercial.get("status")) == "product_commercial_independence_gate_ready",
            _bool(commercial.get("commercial_independent_product_claim_allowed")),
            _bool(commercial.get("license_present")),
            _bool(commercial.get("dependency_provenance_manifest_present")),
            _bool(commercial.get("reproducible_install_manifest_ready")),
            _bool(commercial.get("local_delivery_bundle_ready")),
            _bool(commercial.get("local_self_hosted_api_cli_ready")),
            _bool(public_benchmark.get("public_benchmark_validation_ready")),
        ]
    )
    cameo_release_sources = [cameo, release_gate]
    cameo_live_required_for_release = _first_present_value(
        cameo_release_sources,
        ["cameo_live_validation_required_for_product_release", "live_validation_required_for_product_release"],
    )
    cameo_registration_required_for_release = _first_present_value(
        cameo_release_sources,
        ["cameo_registration_required_for_product_release", "registration_required_for_product_release"],
    )
    cameo_official_results_required_for_release = _first_present_value(
        cameo_release_sources,
        ["cameo_official_results_required_for_product_release", "official_results_required_for_product_release"],
    )
    cameo_official_results_pending_honest = _first_present_value(
        cameo_release_sources,
        ["cameo_official_results_pending_honest", "official_results_pending_honest"],
    )
    cameo_no_local_native_accuracy_substitution = _first_present_value(
        cameo_release_sources,
        ["cameo_no_local_native_accuracy_substitution", "no_local_native_accuracy_substitution"],
    )
    cameo_optional_ready = all(
        [
            _bool(cameo.get("receiver_api_readiness_ready")),
            _bool(cameo.get("validation_operations_surface_ready")),
            _bool(cameo.get("local_validation_protocol_ready")),
            cameo_live_required_for_release is False,
            cameo_registration_required_for_release is False,
            cameo_official_results_required_for_release is False,
            _bool(cameo_official_results_pending_honest),
            _bool(cameo_no_local_native_accuracy_substitution),
        ]
    )
    release_artifact_ready = all(
        [
            _text(release_gate.get("status")) == "goal_release_ready",
            _bool(release_gate.get("release_allowed")),
            _bool(release_dossier.get("architecture_release_ready")),
            _bool(release_dossier.get("commercial_independence_ready")),
        ]
    )
    release_blocking_work_item_count = _int(
        product_ai_backlog.get(
            "release_blocking_work_item_count",
            product_ai_backlog.get("work_item_count"),
        )
    )
    product_ai_architecture_ready = all(
        [
            _bool(product_ai_architecture.get("all_gaps_closed")),
            _int(product_ai_architecture.get("open_gap_count")) == 0,
            release_blocking_work_item_count == 0,
        ]
    )
    product_ai_optional_lane_ready = product_ai_architecture_ready and _bool(
        product_ai_backlog.get("backlog_clear")
    )
    product_ai_scope_deferred_work_item_count = _int(
        product_ai_backlog.get("scope_deferred_work_item_count")
    )
    restricted_delivery_ready = all(
        [
            local_product_ready,
            _bool(release_dossier.get("bundle_validation_passed")),
            _bool(release_dossier.get("delivery_ready_claim_allowed")),
            _bool(release_dossier.get("pilot_delivery_ready")),
        ]
    )
    product_ai_all_gaps_closed = _bool(product_ai_architecture.get("all_gaps_closed"))
    product_ai_gap_open_ids = [str(item) for item in (product_ai_architecture.get("open_gap_ids") or [])]
    product_ai_gap_closed_ids = [str(item) for item in (product_ai_architecture.get("closed_gap_ids") or [])]
    product_ai_production_checkpoint_gap_ready = _gap_closed(
        product_ai_architecture_gap_packet or {},
        "production_ai_inference_checkpoint",
        fallback_ready=product_ai_all_gaps_closed,
    )
    product_ai_closed_loop_decision_graph_ready = _gap_closed(
        product_ai_architecture_gap_packet or {},
        "closed_loop_structure_docking_ai_graph",
        fallback_ready=product_ai_all_gaps_closed,
    )
    product_ai_durable_job_orchestration_ready = _gap_closed(
        product_ai_architecture_gap_packet or {},
        "durable_job_orchestration",
        fallback_ready=product_ai_all_gaps_closed,
    )
    product_ai_trajectory_sla_ready = _gap_closed(
        product_ai_architecture_gap_packet or {},
        "production_trajectory_sla",
        fallback_ready=product_ai_all_gaps_closed,
    )
    product_ai_scope_breadth_ready = _gap_closed(
        product_ai_architecture_gap_packet or {},
        "scope_breadth_expansion",
        fallback_ready=product_ai_all_gaps_closed,
    )
    product_ai_report_ux_ready = _gap_closed(
        product_ai_architecture_gap_packet or {},
        "ai_analysis_report_ux",
        fallback_ready=product_ai_all_gaps_closed,
    )
    product_ai_security_deployment_ready = _gap_closed(
        product_ai_architecture_gap_packet or {},
        "security_deployment_operations",
        fallback_ready=product_ai_all_gaps_closed,
    )
    next_command_candidates = _next_command_candidates(
        primary_next_command=primary_next_command,
        burndown_candidates=primary_next_command_candidates,
        primary_backlog=primary_backlog,
        product_ai_architecture_ready=product_ai_architecture_ready,
    )
    product_ai_report_ux_observed = _live_gap_observed("ai_analysis_report_ux", **gap_observed_live_inputs)
    product_ai_report_ux_observed_pairs = _observed_pairs(product_ai_report_ux_observed)
    product_ai_trajectory_sla_observed = _live_gap_observed("production_trajectory_sla", **gap_observed_live_inputs)
    product_ai_trajectory_sla_observed_pairs = _observed_pairs(product_ai_trajectory_sla_observed)
    product_ai_security_deployment_observed = _live_gap_observed(
        "security_deployment_operations",
        **gap_observed_live_inputs,
    )
    product_ai_security_deployment_observed_pairs = _observed_pairs(product_ai_security_deployment_observed)
    product_ai_closed_loop_decision_graph_observed = _live_gap_observed(
        "closed_loop_structure_docking_ai_graph",
        **gap_observed_live_inputs,
    )
    product_ai_durable_job_orchestration_observed = _live_gap_observed(
        "durable_job_orchestration",
        **gap_observed_live_inputs,
    )

    rows = [
        _row(
            requirement_id="R1_local_self_hosted_product",
            requirement="Local/self-hosted structure analysis, ligand docking, scoring, ranking, API/CLI, and bundle surfaces are ready without external SaaS runtime dependency.",
            passed=local_product_ready,
            observed=(
                f"structure={_bool(architecture.get('structure_analysis_product_surface_ready'))};"
                f"ligand_docking={_bool(architecture.get('ligand_docking_execution_contract_ready'))};"
                f"scoring={_bool(architecture.get('scoring_ranking_contract_ready'))};"
                f"bundle={_bool(architecture.get('local_delivery_bundle_validation_ready'))};"
                f"api={_bool(architecture.get('product_api_contract_ready'))};"
                f"external_saas_runtime_dependency_count={_int(commercial.get('external_saas_runtime_dependency_count'))}"
            ),
            required="all local product surfaces ready; external_saas_runtime_dependency_count=0",
            evidence_artifacts=_join([architecture_path, commercial_independence_path]),
            blocker="local_product_surface_not_ready",
        ),
        _row(
            requirement_id="R2_public_benchmark_continuous_validation",
            requirement="Public benchmark continuous validation covers LIT-PCBA, DUDE-Z, PDBbind/CASF, BM5, and CASP archive without 24h server, season, or paid VPS dependency.",
            passed=benchmark_ready,
            observed=(
                f"status={_text(public_benchmark.get('status'))};"
                f"ready_required_suite_count={_int(public_benchmark.get('ready_required_suite_count'))};"
                f"blocked_suite_count={_int(public_benchmark.get('blocked_suite_count'))};"
                f"requires_24h_server={_bool(architecture.get('public_benchmark_requires_24h_server'))}"
            ),
            required="public_benchmark_validation_ready=true;ready_required_suite_count>=5;blocked_suite_count=0;no 24h/season/VPS requirement",
            evidence_artifacts=_join([public_benchmark_path, architecture_path]),
            blocker="public_benchmark_validation_not_ready",
        ),
        _row(
            requirement_id="R3_commercial_independence",
            requirement="Commercial independence evidence includes LICENSE, dependency provenance, reproducible install, local delivery bundle, API/CLI execution, and benchmark evidence.",
            passed=commercial_ready,
            observed=(
                f"commercial_status={_text(commercial.get('status'))};"
                f"license_present={_bool(commercial.get('license_present'))};"
                f"license_work_order_status={_text(license_work_order.get('status'))};"
                f"dependency_provenance={_bool(commercial.get('dependency_provenance_manifest_present'))};"
                f"reproducible_install={_bool(commercial.get('reproducible_install_manifest_ready'))};"
                f"api_cli={_bool(commercial.get('local_self_hosted_api_cli_ready'))};"
                f"benchmark={_bool(public_benchmark.get('public_benchmark_validation_ready'))}"
            ),
            required="product_commercial_independence_gate_ready with non-empty LICENSE and all commercial evidence present",
            evidence_artifacts=_join(
                [commercial_independence_path, license_work_order_path, public_benchmark_path, release_dossier_path]
            ),
            blocker="commercial_independence_license_not_ready",
            approval_token_required=primary_token,
            next_command=primary_next_command,
        ),
        _row(
            requirement_id="R4_cameo_optional_live_validation",
            requirement="CAMEO remains an optional/live external validation lane with receiver/API readiness, registration evidence, and official result intake separated from product release blocking.",
            passed=cameo_optional_ready,
            observed=(
                f"receiver_api={_bool(cameo.get('receiver_api_readiness_ready'))};"
                f"live_required_for_release={_bool(cameo_live_required_for_release)};"
                f"registration_required_for_release={_bool(cameo_registration_required_for_release)};"
                f"official_results_required_for_release={_bool(cameo_official_results_required_for_release)};"
                f"official_results_pending_honest={_bool(cameo_official_results_pending_honest)}"
            ),
            required="CAMEO local receiver/API ready; live official results honest but not product-release blocking",
            evidence_artifacts=_join([cameo_architecture_path, release_gate_path]),
            blocker="cameo_optional_live_lane_not_clean",
        ),
        _row(
            requirement_id="R5_release_decision_artifacts",
            requirement="Release decision is proven by JSON/CSV/MD gates rather than declaration, and release remains blocked until required evidence is complete.",
            passed=release_artifact_ready,
            observed=(
                f"release_gate_status={_text(release_gate.get('status'))};"
                f"release_allowed={_bool(release_gate.get('release_allowed'))};"
                f"architecture_release_ready={_bool(release_dossier.get('architecture_release_ready'))};"
                f"commercial_independence_ready={_bool(release_dossier.get('commercial_independence_ready'))};"
                f"primary_bottleneck={primary_phase or primary_kind}"
            ),
            required="goal_release_ready and release_allowed=true after architecture/commercial evidence passes",
            evidence_artifacts=_join([release_gate_path, release_dossier_path, bottleneck_path]),
            blocker="release_decision_blocked_by_primary_bottleneck",
            approval_token_required=primary_token,
            next_command=primary_next_command,
        ),
        _row(
            requirement_id="R7_restricted_local_delivery_ready",
            requirement=(
                "Restricted local product delivery is proven by validated bundle assembly, delivery-ready claim policy, "
                "and pilot handoff readiness without requiring production-AI promotion or broad platform scope."
            ),
            passed=restricted_delivery_ready,
            observed=(
                f"local_product_ready={local_product_ready};"
                f"bundle_validation_passed={_bool(release_dossier.get('bundle_validation_passed'))};"
                f"delivery_ready_claim_allowed={_bool(release_dossier.get('delivery_ready_claim_allowed'))};"
                f"pilot_delivery_ready={_bool(release_dossier.get('pilot_delivery_ready'))};"
                f"release_gate_status={_text(release_gate.get('status'))}"
            ),
            required="local product surfaces ready; bundle_validation_passed=true; delivery_ready_claim_allowed=true; pilot_delivery_ready=true",
            evidence_artifacts=_join([release_dossier_path, architecture_path]),
            blocker="restricted_local_delivery_not_ready",
            requirement_tier="restricted_delivery",
        ),
        _row(
            requirement_id="R6_product_ai_architecture_gap_closure",
            requirement=(
                "Production AI inference, closed-loop analysis, durable job orchestration, trajectory SLA, scope breadth, "
                "report UX, and security/deployment remain optional/deferred lanes tracked separately from restricted delivery."
            ),
            passed=product_ai_optional_lane_ready,
            observed=(
                f"ai_gap_status={_text(product_ai_architecture.get('status'))};"
                f"all_gaps_closed={_bool(product_ai_architecture.get('all_gaps_closed'))};"
                f"open_gap_count={_int(product_ai_architecture.get('open_gap_count'))};"
                f"current_primary_open_gap={_text(product_ai_architecture.get('current_primary_open_gap'))};"
                f"release_blocking_work_item_count={release_blocking_work_item_count};"
                f"backlog_clear={_bool(product_ai_backlog.get('backlog_clear'))};"
                f"work_item_count={_int(product_ai_backlog.get('work_item_count'))};"
                f"scope_deferred_work_item_count={_int(product_ai_backlog.get('scope_deferred_work_item_count'))};"
                f"primary_work_item_id={_text(product_ai_backlog.get('primary_work_item_id'))}"
                + (f";{product_ai_backlog_detail}" if product_ai_backlog_detail else "")
                + (f";{product_ai_scope_backlog_detail}" if product_ai_scope_backlog_detail else "")
            ),
            required="all_gaps_closed=true;open_gap_count=0;release_blocking_work_item_count=0;optional backlog may remain deferred",
            evidence_artifacts=_join(
                [
                    product_ai_architecture_gap_path,
                    product_ai_execution_backlog_path,
                    production_ai_checkpoint_readiness_path,
                    production_ai_gpu_return_intake_path,
                    production_ai_promotion_workbench_path,
                    scope_evidence_priority_path,
                    scope_evidence_intake_readiness_path,
                ]
            ),
            blocker="product_ai_optional_lane_not_closed",
            next_command=_product_ai_gap_next_command(primary_phase, primary_next_command),
            release_blocker=False,
            requirement_tier="optional_production_ai",
        ),
        _row(
            requirement_id="R8_full_scope_claim_closure",
            requirement=(
                "Full independent commercial-product claims stay blocked until scope-closure acceptance is green, "
                "transporter evidence is claim-safe, and broad/general protein-ligand wording is explicitly allowed."
            ),
            passed=(
                _bool(scope_closure.get("scope_closure_ready"))
                and _bool(product_scope_breadth_contract.get("scope_breadth_ready"))
                and _bool(scope_closure.get("general_platform_claim_allowed"))
                and scope_breadth_evidence_receipt_ready
            ),
            observed=(
                f"scope_closure_ready={_bool(scope_closure.get('scope_closure_ready'))};"
                f"scope_breadth_ready={_bool(product_scope_breadth_contract.get('scope_breadth_ready'))};"
                f"full_scope_evidence_receipt_ready={scope_breadth_evidence_receipt_ready};"
                f"scope_evidence_receipt_status={_text(scope_breadth_evidence_receipt.get('status'))};"
                f"scope_evidence_receipt_blocked_row_count={_int(scope_breadth_evidence_receipt.get('blocked_row_count'))};"
                f"blocked_stage_count={_int(scope_closure.get('scope_acceptance_blocked_stage_count'))};"
                f"next_stage_id={_text(scope_closure.get('scope_acceptance_next_stage_id'))};"
                f"first_blocked_evidence_row_id={_text(scope_closure.get('first_blocked_evidence_row_id'))};"
                f"first_blocked_target_id={_text(scope_closure.get('first_blocked_target_id'))};"
                f"first_blocked_required_missing_fields={_text(scope_closure.get('first_blocked_required_missing_fields'))};"
                f"general_platform_claim_allowed={_bool(scope_closure.get('general_platform_claim_allowed'))};"
                f"authoritative_apply_allowed={_bool(product_scope_breadth_contract.get('authoritative_apply_allowed'))}"
            ),
            required=(
                "scope_closure_ready=true;scope_breadth_ready=true;general_platform_claim_allowed=true;"
                "authoritative_apply_allowed=true;full_scope_evidence_receipt_ready=true for broadened commercial claims"
            ),
            evidence_artifacts=_join(
                [
                    scope_closure_acceptance_path,
                    product_scope_breadth_contract_path,
                    scope_evidence_priority_path,
                    scope_evidence_intake_readiness_path,
                    scope_breadth_evidence_receipt_path,
                ]
            ),
            blocker="full_scope_claim_closure_not_ready",
            next_command=_text(scope_closure.get("next_stage_validation_command"))
            or _text(product_scope_breadth_contract.get("validation_command"))
            or _text(scope_top_priority.get("regeneration_commands")),
            release_blocker=True,
            requirement_tier="full_commercial_scope",
        ),
    ]
    if engine_refinement:
        rows.append(
            _row(
                requirement_id="R9_engine_refinement_claim_promotion",
                requirement=(
                    "Refine-tier science claims stay blocked until public benchmark intake, parameter calibration, "
                    "metal/cofactor handling, protonation/charge calibration, solvent/FEP calibration, and external "
                    "structure-quality parity evidence are all claim-grade."
                ),
                passed=engine_refinement_claim_promotion_ready,
                observed=(
                    f"engine_refinement_status={_text(engine_refinement.get('status'))};"
                    f"engine_refinement_tier_ready={_bool(engine_refinement.get('engine_refinement_tier_ready'))};"
                    f"claim_promotion_allowed={_bool(engine_refinement.get('claim_promotion_allowed'))};"
                    f"claim_promotion_evidence_receipt_ready={engine_refinement_claim_evidence_receipt_ready};"
                    f"claim_promotion_blocker_count={engine_refinement_claim_blocker_count};"
                    f"claim_promotion_action_row_count={engine_refinement_claim_action_row_count};"
                    f"claim_grade_public_benchmark_ready={_bool(engine_refinement.get('claim_grade_public_benchmark_ready'))};"
                    f"public_benchmark_gate_status={_text(engine_refinement.get('public_benchmark_gate_status'))};"
                    f"claim_promotion_blockers={','.join(engine_refinement_claim_blockers)}"
                ),
                required=(
                    "claim_promotion_allowed=true;claim_promotion_evidence_receipt_ready=true;"
                    "claim_promotion_blocker_count=0;"
                    "claim_promotion_action_row_count=0;claim_grade_public_benchmark_ready=true"
                ),
                evidence_artifacts=_join(
                    [
                        engine_refinement_tier_readiness_path,
                        engine_refinement.get("claim_promotion_action_board_csv"),
                        engine_refinement.get("claim_promotion_evidence_receipt_artifact"),
                    ]
                ),
                blocker="engine_refinement_claim_promotion_not_ready",
                next_command=(
                    "python3 tools/product/build_engine_refinement_tier_readiness.py && "
                    "python3 tools/build_product_goal_completion_audit.py"
                ),
                release_blocker=True,
                requirement_tier="full_commercial_science_claim",
            )
        )
    failed = [row for row in rows if row["status"] != "pass"]
    release_failed = [row for row in failed if row.get("release_blocker")]
    optional_failed = [row for row in failed if not row.get("release_blocker")]
    primary_release_blocker = release_failed[0] if release_failed else None
    primary_release_blocker_summary = _release_blocker_summary(primary_release_blocker)
    status = (
        "product_goal_completion_audit_pass"
        if not release_failed
        else "blocked_product_goal_completion_audit"
    )
    product_ai_gap_blocker_matrix = [
        dict(row)
        for row in (product_ai_architecture.get("gap_blocker_matrix") or [])
        if isinstance(row, dict)
    ]
    product_ai_current_primary_blocker = (
        product_ai_gap_blocker_matrix[0] if product_ai_gap_blocker_matrix else {}
    )
    product_ai_parallelizable_gap_blockers = [
        row for row in product_ai_gap_blocker_matrix if row.get("parallelizable_workstream") is True
    ]
    product_ai_first_parallelizable_blocker = (
        product_ai_parallelizable_gap_blockers[0] if product_ai_parallelizable_gap_blockers else {}
    )
    summary = {
        "packet_type": "product_goal_completion_audit",
        "status": status,
        "requirement_count": len(rows),
        "pass_count": len(rows) - len(failed),
        "fail_count": len(failed),
        "release_blocker_fail_count": len(release_failed),
        "release_blocker_requirement_ids": [
            _text(row.get("requirement_id")) for row in release_failed
        ],
        "release_blocker_tiers": [
            _text(row.get("requirement_tier")) for row in release_failed
        ],
        **primary_release_blocker_summary,
        "optional_requirement_fail_count": len(optional_failed),
        "goal_complete": not release_failed,
        "restricted_delivery_complete": restricted_delivery_ready,
        "product_ai_optional_lane_ready": product_ai_optional_lane_ready,
        "product_ai_scope_deferred_work_item_count": product_ai_scope_deferred_work_item_count,
        "product_scope_breadth_evidence_receipt_status": _text(
            scope_breadth_evidence_receipt.get("status")
        ),
        "product_scope_breadth_evidence_receipt_ready": scope_breadth_evidence_receipt_ready,
        "product_scope_breadth_evidence_receipt_blocker_count": _int(
            scope_breadth_evidence_receipt.get("blocker_count")
        ),
        "product_scope_breadth_evidence_receipt_blocked_row_count": _int(
            scope_breadth_evidence_receipt.get("blocked_row_count")
        ),
        "product_scope_breadth_evidence_receipt_required_scope_blocker_count": _int(
            scope_breadth_evidence_receipt.get("required_scope_blocker_count")
        ),
        "product_scope_breadth_evidence_receipt_artifact": _text(
            scope_breadth_evidence_receipt.get("artifact_path")
            or scope_breadth_evidence_receipt_path
        ),
        "product_scope_breadth_evidence_receipt_csv": _text(
            scope_breadth_evidence_receipt.get("receipt_csv")
        ),
        "engine_refinement_claim_promotion_evidence_present": bool(engine_refinement),
        "engine_refinement_claim_promotion_ready": engine_refinement_claim_promotion_ready,
        "engine_refinement_status": _text(engine_refinement.get("status")),
        "engine_refinement_claim_promotion_allowed": _bool(
            engine_refinement.get("claim_promotion_allowed")
        ),
        "engine_refinement_claim_promotion_blocker_count": engine_refinement_claim_blocker_count,
        "engine_refinement_claim_promotion_blockers": engine_refinement_claim_blockers,
        "engine_refinement_claim_promotion_action_row_count": engine_refinement_claim_action_row_count,
        "engine_refinement_claim_promotion_action_board_csv": _text(
            engine_refinement.get("claim_promotion_action_board_csv")
        ),
        "engine_refinement_claim_evidence_receipt_status": _text(
            engine_refinement.get("claim_promotion_evidence_receipt_status")
        ),
        "engine_refinement_claim_evidence_receipt_ready": engine_refinement_claim_evidence_receipt_ready,
        "engine_refinement_claim_evidence_receipt_blocker_count": _int(
            engine_refinement.get("claim_promotion_evidence_receipt_blocker_count")
        ),
        "engine_refinement_claim_evidence_receipt_blocked_row_count": _int(
            engine_refinement.get("claim_promotion_evidence_receipt_blocked_row_count")
        ),
        "engine_refinement_claim_evidence_receipt_artifact": _text(
            engine_refinement.get("claim_promotion_evidence_receipt_artifact")
        ),
        "engine_refinement_claim_evidence_receipt_csv": _text(
            engine_refinement.get("claim_promotion_evidence_receipt_csv")
        ),
        "engine_refinement_public_benchmark_gate_status": _text(
            engine_refinement.get("public_benchmark_gate_status")
        ),
        "engine_refinement_claim_promotion_next_required_step": _text(
            engine_refinement.get("claim_promotion_next_required_step")
        ),
        "primary_bottleneck_phase": primary_phase,
        "primary_bottleneck_kind": primary_kind,
        "approval_tokens_required": approval_tokens,
        "next_command": primary_next_command,
        "next_command_candidate_count": len(next_command_candidates),
        "next_command_candidates": next_command_candidates,
        "release_allowed": _bool(release_gate.get("release_allowed")),
        "commercial_independence_ready": commercial_ready,
        "public_benchmark_validation_ready": benchmark_ready,
        "local_self_hosted_product_ready": local_product_ready,
        "cameo_optional_live_validation_ready": cameo_optional_ready,
        "release_artifact_ready": release_artifact_ready,
        "product_ai_architecture_ready": product_ai_architecture_ready,
        "product_ai_architecture_gap_status": _text(product_ai_architecture.get("status")),
        "product_ai_architecture_all_gaps_closed": product_ai_all_gaps_closed,
        "product_ai_architecture_gap_count": _int(product_ai_architecture.get("gap_count")),
        "product_ai_architecture_closed_gap_count": _int(product_ai_architecture.get("closed_gap_count")),
        "product_ai_architecture_open_gap_count": _int(product_ai_architecture.get("open_gap_count")),
        "product_ai_architecture_open_gap_ids": product_ai_gap_open_ids,
        "product_ai_architecture_closed_gap_ids": product_ai_gap_closed_ids,
        "product_ai_architecture_gap_blocker_matrix_ready": _bool(
            product_ai_architecture.get("gap_blocker_matrix_ready")
        ),
        "product_ai_architecture_gap_blocker_matrix_count": _int(
            product_ai_architecture.get("gap_blocker_matrix_count")
        ),
        "product_ai_architecture_gap_blocker_matrix": product_ai_gap_blocker_matrix,
        "product_ai_architecture_current_primary_blocker_gap_id": _text(
            product_ai_architecture.get("current_primary_blocker_gap_id")
            or product_ai_current_primary_blocker.get("gap_id")
        ),
        "product_ai_architecture_current_primary_blocker_id": _text(
            product_ai_architecture.get("current_primary_blocker_id")
            or product_ai_current_primary_blocker.get("primary_blocker_id")
        ),
        "product_ai_architecture_current_primary_blocker_artifact": _text(
            product_ai_architecture.get("current_primary_blocker_artifact")
            or product_ai_current_primary_blocker.get("blocker_artifact")
        ),
        "product_ai_architecture_current_primary_blocker_validation_command": _text(
            product_ai_architecture.get("current_primary_blocker_validation_command")
            or product_ai_current_primary_blocker.get("validation_command")
        ),
        "product_ai_architecture_current_primary_blocker_next_action": _text(
            product_ai_architecture.get("current_primary_blocker_next_action")
            or product_ai_current_primary_blocker.get("next_action")
        ),
        "product_ai_architecture_current_primary_blocker_operator_input_fields": [
            str(item)
            for item in (
                product_ai_architecture.get("current_primary_blocker_operator_input_fields")
                or product_ai_current_primary_blocker.get("operator_input_fields")
                or []
            )
        ],
        "product_ai_architecture_current_primary_blocker_unlock_claim": _text(
            product_ai_architecture.get("current_primary_blocker_unlock_claim")
            or product_ai_current_primary_blocker.get("unlock_claim")
        ),
        "product_ai_architecture_current_primary_blocker_next_after_stage_id": _text(
            product_ai_architecture.get("current_primary_blocker_next_after_stage_id")
            or product_ai_current_primary_blocker.get("next_after_blocker_stage_id")
        ),
        "product_ai_architecture_current_primary_blocker_next_after_artifact": _text(
            product_ai_architecture.get("current_primary_blocker_next_after_artifact")
            or product_ai_current_primary_blocker.get("next_after_blocker_artifact")
        ),
        "product_ai_architecture_current_primary_blocker_next_after_validation_command": _text(
            product_ai_architecture.get("current_primary_blocker_next_after_validation_command")
            or product_ai_current_primary_blocker.get("next_after_blocker_validation_command")
        ),
        "product_ai_architecture_current_primary_blocker_next_after_next_action": _text(
            product_ai_architecture.get("current_primary_blocker_next_after_next_action")
            or product_ai_current_primary_blocker.get("next_after_blocker_next_action")
        ),
        "product_ai_architecture_current_primary_blocker_next_after_required_checks": [
            str(item)
            for item in (
                product_ai_architecture.get("current_primary_blocker_next_after_required_checks")
                or product_ai_current_primary_blocker.get("next_after_blocker_required_checks")
                or []
            )
        ],
        "product_ai_architecture_current_primary_blocker_next_after_unlock_fields": [
            str(item)
            for item in (
                product_ai_architecture.get("current_primary_blocker_next_after_unlock_fields")
                or product_ai_current_primary_blocker.get("next_after_blocker_unlock_fields")
                or []
            )
        ],
        "product_ai_architecture_parallelizable_gap_blocker_count": _int(
            product_ai_architecture.get("parallelizable_gap_blocker_count")
        ),
        "product_ai_architecture_parallelizable_gap_blocker_ids": [
            str(item) for item in (product_ai_architecture.get("parallelizable_gap_blocker_ids") or [])
        ],
        "product_ai_architecture_first_parallelizable_gap_id": _text(
            product_ai_architecture.get("first_parallelizable_gap_id")
        ),
        "product_ai_architecture_first_parallelizable_blocker_id": _text(
            product_ai_architecture.get("first_parallelizable_blocker_id")
        ),
        "product_ai_architecture_first_parallelizable_blocker_artifact": _text(
            product_ai_architecture.get("first_parallelizable_blocker_artifact")
        ),
        "product_ai_architecture_first_parallelizable_blocker_next_action": _text(
            product_ai_architecture.get("first_parallelizable_blocker_next_action")
        ),
        "product_ai_architecture_first_parallelizable_blocker_validation_command": _text(
            product_ai_architecture.get("first_parallelizable_blocker_validation_command")
            or product_ai_first_parallelizable_blocker.get("validation_command")
        ),
        "product_ai_architecture_first_parallelizable_blocker_operator_input_fields": [
            str(item)
            for item in (
                product_ai_architecture.get("first_parallelizable_blocker_operator_input_fields")
                or product_ai_first_parallelizable_blocker.get("operator_input_fields")
                or []
            )
        ],
        "product_ai_architecture_first_parallelizable_blocker_required_exact_evidence_fields": [
            str(item)
            for item in (
                product_ai_architecture.get(
                    "first_parallelizable_blocker_required_exact_evidence_fields"
                )
                or product_ai_first_parallelizable_blocker.get("required_exact_evidence_fields")
                or []
            )
        ],
        "product_ai_architecture_first_parallelizable_blocker_required_claim_guardrails": [
            str(item)
            for item in (
                product_ai_architecture.get("first_parallelizable_blocker_required_claim_guardrails")
                or product_ai_first_parallelizable_blocker.get("required_claim_guardrails")
                or []
            )
        ],
        "product_ai_architecture_first_parallelizable_blocker_claim_safe_completion_rule": _text(
            product_ai_architecture.get("first_parallelizable_blocker_claim_safe_completion_rule")
            or product_ai_first_parallelizable_blocker.get("claim_safe_completion_rule")
        ),
        "product_ai_architecture_first_parallelizable_blocker_unlock_claim": _text(
            product_ai_architecture.get("first_parallelizable_blocker_unlock_claim")
            or product_ai_first_parallelizable_blocker.get("unlock_claim")
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_artifact": _text(
            product_ai_architecture.get("first_parallelizable_blocker_source_modality_triage_artifact")
            or product_ai_first_parallelizable_blocker.get("source_modality_triage_artifact")
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_decision": _text(
            product_ai_architecture.get("first_parallelizable_blocker_source_modality_triage_decision")
            or product_ai_first_parallelizable_blocker.get("source_modality_triage_decision")
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_direct_experimental_binding_row_count": _int(
            product_ai_architecture.get(
                "first_parallelizable_blocker_source_modality_direct_experimental_binding_row_count"
            )
            or product_ai_first_parallelizable_blocker.get(
                "source_modality_direct_experimental_binding_row_count"
            )
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_claim_safe_binding_kcal_ready_count": _int(
            product_ai_architecture.get(
                "first_parallelizable_blocker_source_modality_claim_safe_binding_kcal_ready_count"
            )
            or product_ai_first_parallelizable_blocker.get(
                "source_modality_claim_safe_binding_kcal_ready_count"
            )
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_computational_binding_energy_row_count": _int(
            product_ai_architecture.get(
                "first_parallelizable_blocker_source_modality_computational_binding_energy_row_count"
            )
            or product_ai_first_parallelizable_blocker.get(
                "source_modality_computational_binding_energy_row_count"
            )
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_best_computational_binding_energy_kcal_mol": _text(
            product_ai_architecture.get(
                "first_parallelizable_blocker_source_modality_best_computational_binding_energy_kcal_mol"
            )
            or product_ai_first_parallelizable_blocker.get(
                "source_modality_best_computational_binding_energy_kcal_mol"
            )
        ),
        "commercial_readiness_next_action_matrix_ready": bool(commercial_next_action_matrix),
        "commercial_readiness_next_action_matrix": commercial_next_action_matrix,
        "commercial_readiness_next_action_matrix_count": len(commercial_next_action_matrix),
        "commercial_readiness_next_action_blocker_matrix": commercial_next_action_blocker_matrix,
        "commercial_readiness_next_action_blocker_count": len(commercial_next_action_blocker_matrix),
        "commercial_readiness_first_next_action_id": _text(commercial_first_next_action.get("action_id")),
        "commercial_readiness_first_next_action_artifact": _text(commercial_first_next_action.get("artifact")),
        "commercial_readiness_first_next_action_validation_command": _text(
            commercial_first_next_action.get("validation_command")
        ),
        "commercial_readiness_handoff_bundle_status": _text(commercial_handoff.get("status")),
        "commercial_readiness_handoff_bundle_artifact_path": commercial_readiness_handoff_bundle_path,
        "commercial_readiness_handoff_bundle_ready": _bool(
            commercial_handoff.get("handoff_bundle_ready")
        ),
        "commercial_readiness_handoff_bundle_artifact_count": _int(
            commercial_handoff.get("artifact_count")
        ),
        "commercial_readiness_handoff_bundle_blocked_artifact_count": _int(
            commercial_handoff.get("blocked_artifact_count")
        ),
        "commercial_readiness_handoff_bundle_blocked_artifact_ids": [
            str(item) for item in (commercial_handoff.get("blocked_artifact_ids") or [])
        ],
        "commercial_readiness_handoff_bundle_artifact_reference_contract_ready": _bool(
            commercial_handoff.get("artifact_reference_contract_ready")
        ),
        "commercial_readiness_handoff_bundle_artifact_reference_count": _int(
            commercial_handoff.get("artifact_reference_count")
        ),
        "commercial_readiness_handoff_bundle_local_missing_artifact_reference_count": _int(
            commercial_handoff.get("local_missing_artifact_reference_count")
        ),
        "commercial_readiness_handoff_bundle_operator_return_pending_artifact_reference_count": _int(
            commercial_handoff.get("operator_return_pending_artifact_reference_count")
        ),
        "commercial_readiness_handoff_bundle_first_action_id": _text(
            commercial_handoff.get("first_action_id")
        ),
        "commercial_readiness_handoff_bundle_first_operator_input_artifact": _text(
            commercial_handoff.get("first_operator_input_artifact")
        ),
        "commercial_readiness_handoff_bundle_next_required_step": _text(
            commercial_handoff.get("next_required_step")
        ),
        "production_ai_delta_force_closure_acceptance_artifact_path": delta_force_closure_acceptance_path,
        "production_ai_delta_force_closure_acceptance_packet_ready": _bool(
            delta_force_closure.get("packet_ready")
        ),
        "production_ai_delta_force_closure_ready": _bool(
            delta_force_closure.get("delta_force_closure_ready")
        ),
        "production_ai_delta_force_closure_first_blocked_output_field": _text(
            delta_force_closure.get("first_blocked_output_field")
        ),
        "production_ai_delta_force_closure_failed_stage_count": _int(
            delta_force_closure.get("closure_failed_stage_count")
        ),
        "production_ai_delta_force_closure_failed_stage_ids": [
            str(item) for item in (delta_force_closure.get("closure_failed_stage_ids") or [])
        ],
        "production_ai_delta_force_closure_next_stage_id": _text(
            delta_force_closure.get("next_stage_id")
        ),
        "production_ai_delta_force_closure_next_stage_artifact": _text(
            delta_force_closure.get("next_stage_artifact")
        ),
        "production_ai_delta_force_closure_next_stage_validation_command": _text(
            delta_force_closure.get("next_stage_validation_command")
        ),
        "production_ai_delta_force_closure_next_required_step": _text(
            delta_force_closure.get("next_required_step")
        ),
        "product_scope_closure_acceptance_artifact_path": scope_closure_acceptance_path,
        "product_scope_closure_acceptance_packet_ready": _bool(
            scope_closure.get("packet_ready")
        ),
        "product_scope_closure_acceptance_ready": _bool(
            scope_closure.get("scope_closure_ready")
        ),
        "product_scope_closure_acceptance_stage_count": _int(
            scope_closure.get("scope_acceptance_stage_count")
        ),
        "product_scope_closure_acceptance_blocked_stage_count": _int(
            scope_closure.get("scope_acceptance_blocked_stage_count")
        ),
        "product_scope_closure_acceptance_blocked_stage_ids": [
            str(item) for item in (scope_closure.get("scope_acceptance_blocked_stage_ids") or [])
        ],
        "product_scope_closure_acceptance_next_stage_id": _text(
            scope_closure.get("scope_acceptance_next_stage_id")
        ),
        "product_scope_closure_acceptance_first_blocked_evidence_row_id": _text(
            scope_closure.get("first_blocked_evidence_row_id")
        ),
        "product_scope_closure_acceptance_first_blocked_target_id": _text(
            scope_closure.get("first_blocked_target_id")
        ),
        "product_scope_closure_acceptance_first_blocked_required_missing_fields": _text(
            scope_closure.get("first_blocked_required_missing_fields")
        ),
        "product_scope_closure_acceptance_transporter_unresolved_slot_count": _int(
            scope_closure.get("transporter_unresolved_slot_count")
        ),
        "product_scope_closure_acceptance_pxr_direct_or_claim_safe_quantitative_ready_count": _int(
            scope_closure.get("pxr_direct_or_claim_safe_quantitative_ready_count")
        ),
        "product_scope_closure_acceptance_general_platform_claim_allowed": _bool(
            scope_closure.get("general_platform_claim_allowed")
        ),
        "product_scope_closure_acceptance_next_required_step": _text(
            scope_closure.get("next_required_step")
        ),
        "product_ai_production_checkpoint_gap_ready": product_ai_production_checkpoint_gap_ready,
        "product_ai_production_checkpoint_gap_observed": _live_gap_observed(
            "production_ai_inference_checkpoint",
            **gap_observed_live_inputs,
        ),
        "product_ai_observed_rebuilt_from_live_artifacts": True,
        "product_ai_closed_loop_decision_graph_ready": product_ai_closed_loop_decision_graph_ready,
        "product_ai_closed_loop_decision_graph_observed": product_ai_closed_loop_decision_graph_observed,
        "product_ai_durable_job_orchestration_ready": product_ai_durable_job_orchestration_ready,
        "product_ai_durable_job_orchestration_observed": product_ai_durable_job_orchestration_observed,
        "product_ai_trajectory_sla_ready": product_ai_trajectory_sla_ready,
        "product_ai_trajectory_sla_observed": product_ai_trajectory_sla_observed,
        "product_ai_trajectory_sla_claim_tier": _text(
            product_ai_trajectory_sla_observed_pairs.get("sla_claim_tier")
        ),
        "product_ai_trajectory_sla_restricted_family_allowed": _bool_text(
            product_ai_trajectory_sla_observed_pairs.get("restricted_sla_backed_by_historical_profile_artifacts")
        ),
        "product_ai_trajectory_sla_broad_platform_allowed": _bool_text(
            product_ai_trajectory_sla_observed_pairs.get("broad_platform_sla_allowed")
        ),
        "product_ai_trajectory_sla_current_rocm_baseline_claim_scope": _text(
            product_ai_trajectory_sla_observed_pairs.get("current_rocm_baseline_claim_scope")
        ),
        "product_ai_trajectory_sla_current_rocm_baseline_production_profile_enabled": _bool_text(
            product_ai_trajectory_sla_observed_pairs.get("current_rocm_baseline_production_profile_enabled")
        ),
        "product_ai_trajectory_sla_rocm_baseline_profile_gap_acknowledged": _bool_text(
            product_ai_trajectory_sla_observed_pairs.get("rocm_baseline_profile_gap_acknowledged")
        ),
        "product_ai_scope_breadth_ready": product_ai_scope_breadth_ready,
        "product_ai_scope_breadth_observed": _live_gap_observed(
            "scope_breadth_expansion",
            **gap_observed_live_inputs,
        ),
        "product_ai_report_ux_ready": product_ai_report_ux_ready,
        "product_ai_report_ux_observed": product_ai_report_ux_observed,
        "product_ai_report_ux_customer_report_delivery_contract_ready": _bool_text(
            product_ai_report_ux_observed_pairs.get("customer_report_delivery_contract_ready")
        ),
        "product_ai_report_ux_customer_report_evidence_binding_ready": _bool_text(
            product_ai_report_ux_observed_pairs.get("customer_report_evidence_binding_ready")
        ),
        "product_ai_report_ux_customer_report_viewer_binding_ready": _bool_text(
            product_ai_report_ux_observed_pairs.get("customer_report_viewer_binding_ready")
        ),
        "product_ai_report_ux_viewer_customer_report_binding_ready": _bool_text(
            product_ai_report_ux_observed_pairs.get("viewer_customer_report_binding_ready")
        ),
        "product_ai_report_ux_customer_report_ready_block_count": _int(
            product_ai_report_ux_observed_pairs.get("customer_report_ready_block_count")
        ),
        "product_ai_report_ux_customer_report_required_block_count": _int(
            product_ai_report_ux_observed_pairs.get("customer_report_required_block_count")
        ),
        "product_ai_report_ux_customer_report_blocked_block_count": _int(
            product_ai_report_ux_observed_pairs.get("customer_report_blocked_block_count")
        ),
        "product_ai_security_deployment_ready": product_ai_security_deployment_ready,
        "product_ai_security_deployment_observed": product_ai_security_deployment_observed,
        "product_ai_security_hosted_deployment_contract_ready": _bool_text(
            product_ai_security_deployment_observed_pairs.get("hosted_deployment_contract_ready")
        ),
        "product_ai_security_hosted_deployment_currently_satisfied": _bool_text(
            product_ai_security_deployment_observed_pairs.get("hosted_deployment_currently_satisfied")
        ),
        "product_ai_security_hosted_deployment_next_stage_id": _text(
            product_ai_security_deployment_observed_pairs.get("hosted_deployment_next_stage_id")
        ),
        "product_ai_security_hosted_external_exposure_allowed": _bool_text(
            product_ai_security_deployment_observed_pairs.get("hosted_external_exposure_allowed")
        ),
        "product_ai_security_hosted_secret_injection_ready": _bool_text(
            product_ai_security_deployment_observed_pairs.get("hosted_secret_injection_ready")
        ),
        "product_ai_security_tls_termination_operator_verified": _bool_text(
            product_ai_security_deployment_observed_pairs.get("tls_termination_operator_verified")
        ),
        "production_ai_inference_subject_active": bool(
            _bool(residual_model_registry.get("production_promotion_allowed"))
            and _bool(residual_model_registry.get("production_mode_allowed"))
            and _int(residual_model_registry.get("trained_model_checkpoint_count")) > 0
            and _text(residual_model_registry.get("default_residual_mode")) != "shadow"
        ),
        "production_ai_default_residual_mode": _text(
            residual_model_registry.get("default_residual_mode")
            or production_ai_checkpoint.get("default_residual_mode")
        ),
        "production_ai_promotion_allowed": _bool(
            residual_model_registry.get("production_promotion_allowed")
            if residual_model_registry
            else production_ai_checkpoint.get("production_promotion_allowed")
        ),
        "production_ai_customer_facing_auto_correction_allowed": _bool(
            residual_model_registry.get("customer_facing_auto_correction_allowed")
            if residual_model_registry
            else production_ai_checkpoint.get("customer_facing_auto_correction_allowed")
        ),
        "production_ai_customer_facing_score_mutation_allowed": _bool(
            residual_model_registry.get("customer_facing_score_mutation_allowed")
            if residual_model_registry
            else production_ai_checkpoint.get("customer_facing_score_mutation_allowed")
        ),
        "production_ai_customer_facing_ranking_mutation_allowed": _bool(
            residual_model_registry.get("customer_facing_ranking_mutation_allowed")
            if residual_model_registry
            else production_ai_checkpoint.get("customer_facing_ranking_mutation_allowed")
        ),
        "production_ai_trained_checkpoint_count": _int(
            residual_model_registry.get("trained_model_checkpoint_count")
            if residual_model_registry
            else production_ai_checkpoint.get("trained_model_checkpoint_count")
        ),
        "production_ai_selected_sidecar_ready": _bool(
            residual_model_registry.get("selected_sidecar_ready")
            if residual_model_registry
            else production_ai_checkpoint.get("selected_sidecar_ready")
        ),
        "production_ai_selected_sidecar_missing_output_fields": [
            str(item)
            for item in (
                residual_model_registry.get("selected_sidecar_missing_output_fields")
                if residual_model_registry
                else production_ai_checkpoint.get("selected_sidecar_missing_output_fields")
            )
            or []
        ],
        "production_ai_blocked_reason": _text(
            residual_model_registry.get("production_promotion_blocked_reason")
            or production_ai_checkpoint.get("next_required_step")
        ),
        "production_ai_residual_model_registry_status": _text(residual_model_registry.get("status")),
        "production_ai_residual_model_registry_artifact_path": residual_model_registry_path,
        "production_ai_residual_model_registry_ready": _bool(residual_model_registry.get("registry_ready")),
        "production_ai_product_model_layer_ready": _bool(
            residual_model_registry.get("product_model_layer_ready")
            if residual_model_registry
            else production_ai_checkpoint.get("product_model_layer_ready")
        ),
        "production_ai_registry_checkpoint_preflight_ready": _bool(
            residual_model_registry.get("checkpoint_preflight_ready")
            if residual_model_registry
            else production_ai_checkpoint.get("checkpoint_preflight_ready")
        ),
        "production_ai_registry_production_checkpoint_blocked": _bool(
            residual_model_registry.get("production_checkpoint_blocked")
        ),
        "production_ai_registry_checkpoint_primary_blocker": _text(
            residual_model_registry.get("checkpoint_primary_blocker")
        ),
        "production_ai_registry_checkpoint_missing_output_fields": [
            str(item) for item in (residual_model_registry.get("checkpoint_missing_output_fields") or [])
        ],
        "production_ai_registry_checkpoint_missing_adapter_output_policy_fields": [
            str(item)
            for item in (
                residual_model_registry.get("checkpoint_missing_adapter_output_policy_fields") or []
            )
        ],
        "product_ai_primary_backlog_detail": product_ai_backlog_detail,
        "product_ai_primary_backlog_work_item_id": _text(product_ai_backlog.get("primary_work_item_id")),
        "product_ai_primary_backlog_acceptance_criteria": _text(primary_backlog.get("acceptance_criteria")),
        "product_ai_primary_backlog_next_action": _text(primary_backlog.get("next_action")),
        "product_ai_primary_backlog_source_artifact": _text(primary_backlog.get("source_artifact")),
        "product_ai_primary_backlog_verification_command": _text(primary_backlog.get("verification_command")),
        "production_ai_gpu_worker_return_receipt_ready": _bool_text(
            primary_observed_pairs.get("gpu_worker_return_receipt_ready")
        ),
        "production_ai_gpu_worker_return_receipt_blockers": _list_from_text(
            primary_observed_pairs.get("gpu_worker_return_receipt_blockers")
        ),
        "production_ai_gpu_expected_queue_rows": _int(
            primary_observed_pairs.get("gpu_worker_return_expected_queue_rows")
        ),
        "production_ai_gpu_manifest_ok_row_count": _int(
            primary_observed_pairs.get("gpu_worker_return_manifest_ok_row_count")
        ),
        "production_ai_gpu_manifest_status_placeholder_count": _int(
            primary_observed_pairs.get("gpu_worker_return_manifest_status_placeholder_count")
        ),
        "production_ai_gpu_manifest_status_invalid_count": _int(
            primary_observed_pairs.get("gpu_worker_return_manifest_status_invalid_count")
        ),
        "production_ai_gpu_manifest_operator_verified": _bool_text(
            primary_observed_pairs.get("gpu_worker_return_manifest_operator_verified")
        ),
        "production_ai_gpu_manifest_npz_paths_complete": _bool(
            production_ai_gpu_return_intake.get("manifest_npz_paths_complete")
        ),
        "production_ai_gpu_manifest_npz_files_exist": _bool(
            production_ai_gpu_return_intake.get("manifest_npz_files_exist")
        ),
        "production_ai_gpu_manifest_npz_files_valid": _bool(
            production_ai_gpu_return_intake.get("manifest_npz_files_valid")
        ),
        "production_ai_gpu_manifest_npz_schema_valid": _bool(
            production_ai_gpu_return_intake.get("manifest_npz_schema_valid")
        ),
        "production_ai_gpu_manifest_npz_identity_valid": _bool(
            production_ai_gpu_return_intake.get("manifest_npz_identity_valid")
        ),
        "production_ai_gpu_manifest_npz_path_present_count": _int(
            production_ai_gpu_return_intake.get("manifest_npz_path_present_count")
        ),
        "production_ai_gpu_manifest_npz_path_missing_count": _int(
            production_ai_gpu_return_intake.get("manifest_npz_path_missing_count")
        ),
        "production_ai_gpu_manifest_ok_row_missing_npz_path_count": _int(
            production_ai_gpu_return_intake.get("manifest_ok_row_missing_npz_path_count")
        ),
        "production_ai_gpu_manifest_operator_verified_missing_npz_path_count": _int(
            production_ai_gpu_return_intake.get("manifest_operator_verified_missing_npz_path_count")
        ),
        "production_ai_gpu_manifest_npz_file_existing_count": _int(
            production_ai_gpu_return_intake.get("manifest_npz_file_existing_count")
        ),
        "production_ai_gpu_manifest_npz_file_missing_count": _int(
            production_ai_gpu_return_intake.get("manifest_npz_file_missing_count")
        ),
        "production_ai_gpu_manifest_ok_row_missing_npz_file_count": _int(
            production_ai_gpu_return_intake.get("manifest_ok_row_missing_npz_file_count")
        ),
        "production_ai_gpu_manifest_operator_verified_missing_npz_file_count": _int(
            production_ai_gpu_return_intake.get("manifest_operator_verified_missing_npz_file_count")
        ),
        "production_ai_gpu_manifest_npz_file_valid_count": _int(
            production_ai_gpu_return_intake.get("manifest_npz_file_valid_count")
        ),
        "production_ai_gpu_manifest_npz_file_invalid_count": _int(
            production_ai_gpu_return_intake.get("manifest_npz_file_invalid_count")
        ),
        "production_ai_gpu_manifest_ok_row_invalid_npz_file_count": _int(
            production_ai_gpu_return_intake.get("manifest_ok_row_invalid_npz_file_count")
        ),
        "production_ai_gpu_manifest_operator_verified_invalid_npz_file_count": _int(
            production_ai_gpu_return_intake.get("manifest_operator_verified_invalid_npz_file_count")
        ),
        "production_ai_gpu_manifest_npz_schema_valid_count": _int(
            production_ai_gpu_return_intake.get("manifest_npz_schema_valid_count")
        ),
        "production_ai_gpu_manifest_npz_schema_invalid_count": _int(
            production_ai_gpu_return_intake.get("manifest_npz_schema_invalid_count")
        ),
        "production_ai_gpu_manifest_ok_row_invalid_npz_schema_count": _int(
            production_ai_gpu_return_intake.get("manifest_ok_row_invalid_npz_schema_count")
        ),
        "production_ai_gpu_manifest_operator_verified_invalid_npz_schema_count": _int(
            production_ai_gpu_return_intake.get("manifest_operator_verified_invalid_npz_schema_count")
        ),
        "production_ai_gpu_manifest_npz_identity_valid_count": _int(
            production_ai_gpu_return_intake.get("manifest_npz_identity_valid_count")
        ),
        "production_ai_gpu_manifest_npz_identity_invalid_count": _int(
            production_ai_gpu_return_intake.get("manifest_npz_identity_invalid_count")
        ),
        "production_ai_gpu_manifest_ok_row_invalid_npz_identity_count": _int(
            production_ai_gpu_return_intake.get("manifest_ok_row_invalid_npz_identity_count")
        ),
        "production_ai_gpu_manifest_operator_verified_invalid_npz_identity_count": _int(
            production_ai_gpu_return_intake.get("manifest_operator_verified_invalid_npz_identity_count")
        ),
        "production_ai_gpu_operator_verified_true_count": _int(
            primary_observed_pairs.get("gpu_worker_return_operator_verified_true_count")
        ),
        "production_ai_gpu_operator_verification_column_present": _bool_text(
            primary_observed_pairs.get("gpu_worker_return_operator_verification_column_present")
        ),
        "production_ai_gpu_identity_coverage_ready": _bool_text(
            primary_observed_pairs.get("gpu_worker_return_identity_coverage_ready")
        ),
        "production_ai_gpu_matched_queue_fingerprints": _int(
            primary_observed_pairs.get("gpu_worker_return_matched_queue_fingerprints")
        ),
        "production_ai_gpu_queue_fingerprints": _int(primary_observed_pairs.get("gpu_worker_return_queue_fingerprints")),
        "production_ai_force_derivation_input_ready": _bool_text(
            primary_observed_pairs.get("force_derivation_input_ready")
        ),
        "production_ai_delta_force_derivation_validation_ready": _bool_text(
            primary_observed_pairs.get("delta_force_derivation_validation_ready")
        ),
        "production_ai_missing_output_labels": _list_from_text(
            primary_observed_pairs.get("missing_production_output_labels")
        ),
        "production_ai_checkpoint_readiness_status": _text(production_ai_checkpoint.get("status")),
        "production_ai_checkpoint_ready": _bool(production_ai_checkpoint.get("production_ai_checkpoint_ready")),
        "production_ai_checkpoint_output_head_gap_contract_ready": _bool(
            production_ai_checkpoint.get("production_output_head_gap_contract_ready")
        ),
        "production_ai_checkpoint_output_heads_complete": _bool(
            production_ai_checkpoint.get("production_output_heads_complete")
        ),
        "production_ai_checkpoint_output_head_required_field_count": _int(
            production_ai_checkpoint.get("production_output_head_required_field_count")
        ),
        "production_ai_checkpoint_output_head_ready_field_count": _int(
            production_ai_checkpoint.get("production_output_head_ready_field_count")
        ),
        "production_ai_checkpoint_output_head_blocked_field_count": _int(
            production_ai_checkpoint.get("production_output_head_blocked_field_count")
        ),
        "production_ai_checkpoint_output_head_blocked_fields": [
            str(item) for item in (production_ai_checkpoint.get("production_output_head_blocked_fields") or [])
        ],
        "production_ai_checkpoint_output_head_first_blocked_field": _text(
            production_ai_checkpoint.get("production_output_head_first_blocked_field")
        ),
        "production_ai_checkpoint_output_head_first_blocked_field_blockers": [
            str(item)
            for item in (
                production_ai_checkpoint.get("production_output_head_first_blocked_field_blockers") or []
            )
        ],
        "production_ai_checkpoint_output_head_gap_contract_artifact_path": _text(
            production_ai_checkpoint.get("production_output_head_gap_contract_artifact_path")
        ),
        "production_ai_checkpoint_failed_check_ids": [
            str(item) for item in (production_ai_checkpoint.get("failed_check_ids") or [])
        ],
        "production_ai_checkpoint_first_failed_check_id": _text(
            production_ai_checkpoint.get("first_failed_check_id")
        ),
        "production_ai_checkpoint_first_failed_source_artifact": _text(
            production_ai_checkpoint.get("first_failed_source_artifact")
        ),
        "production_ai_checkpoint_first_failed_observed": _text(
            production_ai_checkpoint.get("first_failed_observed")
        ),
        "production_ai_checkpoint_first_failed_required": _text(
            production_ai_checkpoint.get("first_failed_required")
        ),
        "production_ai_checkpoint_first_failed_next_action": _text(
            production_ai_checkpoint.get("first_failed_next_action")
        ),
        "production_ai_checkpoint_actionable_blocker_stage_id": _text(
            production_ai_checkpoint.get("production_inference_actionable_blocker_stage_id")
        ),
        "production_ai_checkpoint_actionable_blocker_check_id": _text(
            production_ai_checkpoint.get("production_inference_actionable_blocker_check_id")
        ),
        "production_ai_checkpoint_actionable_blocker_artifact": _text(
            production_ai_checkpoint.get("production_inference_actionable_blocker_artifact")
        ),
        "production_ai_checkpoint_actionable_blocker_observed": _text(
            production_ai_checkpoint.get("production_inference_actionable_blocker_observed")
        ),
        "production_ai_checkpoint_actionable_blocker_required": _text(
            production_ai_checkpoint.get("production_inference_actionable_blocker_required")
        ),
        "production_ai_checkpoint_actionable_blocker_next_action": _text(
            production_ai_checkpoint.get("production_inference_actionable_blocker_next_action")
        ),
        "production_ai_checkpoint_actionable_blocker_validation_command": _text(
            production_ai_checkpoint.get("production_inference_actionable_blocker_validation_command")
        ),
        "production_ai_checkpoint_actionable_blocker_unlock_fields": [
            str(item)
            for item in (
                production_ai_checkpoint.get("production_inference_actionable_blocker_unlock_fields") or []
            )
        ],
        "production_ai_checkpoint_actionable_blocker_downstream_blocked_stage_count": _int(
            production_ai_checkpoint.get(
                "production_inference_actionable_blocker_downstream_blocked_stage_count"
            )
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_stage_id": _text(
            production_ai_checkpoint.get("production_inference_next_after_actionable_blocker_stage_id")
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_artifact": _text(
            production_ai_checkpoint.get("production_inference_next_after_actionable_blocker_artifact")
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_validation_command": _text(
            production_ai_checkpoint.get(
                "production_inference_next_after_actionable_blocker_validation_command"
            )
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_required_checks": [
            str(item)
            for item in (
                production_ai_checkpoint.get(
                    "production_inference_next_after_actionable_blocker_required_checks"
                )
                or []
            )
        ],
        "production_ai_checkpoint_next_after_actionable_blocker_unlock_fields": [
            str(item)
            for item in (
                production_ai_checkpoint.get(
                    "production_inference_next_after_actionable_blocker_unlock_fields"
                )
                or []
            )
        ],
        "production_ai_checkpoint_next_after_actionable_blocker_next_action": _text(
            production_ai_checkpoint.get(
                "production_inference_next_after_actionable_blocker_next_action"
            )
        ),
        "production_ai_checkpoint_actionable_blocker_blocks_registry_promotion": _bool(
            production_ai_checkpoint.get("production_inference_actionable_blocker_blocks_registry_promotion")
        ),
        "production_ai_checkpoint_actionable_operator_completion_packet_ready": _bool(
            production_ai_checkpoint.get("production_inference_actionable_operator_completion_packet_ready")
        ),
        "production_ai_checkpoint_actionable_operator_completion_packet_artifact": _text(
            production_ai_checkpoint.get("production_inference_actionable_operator_completion_packet_artifact")
        ),
        "production_ai_checkpoint_actionable_operator_completion_artifact_id": _text(
            production_ai_checkpoint.get("production_inference_actionable_operator_completion_artifact_id")
        ),
        "production_ai_checkpoint_actionable_operator_completion_artifact_path": _text(
            production_ai_checkpoint.get("production_inference_actionable_operator_completion_artifact_path")
        ),
        "production_ai_checkpoint_actionable_operator_completion_expected_queue_rows": _int(
            production_ai_checkpoint.get("production_inference_actionable_operator_completion_expected_queue_rows")
        ),
        "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns": [
            str(item)
            for item in (
                production_ai_checkpoint.get(
                    "production_inference_actionable_operator_completion_required_fields_or_columns"
                )
                or []
            )
        ],
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands": [
            str(item)
            for item in (
                production_ai_checkpoint.get(
                    "production_inference_actionable_operator_completion_diagnostic_commands"
                )
                or []
            )
        ],
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count": _int(
            production_ai_checkpoint.get(
                "production_inference_actionable_operator_completion_diagnostic_command_count"
            )
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_required_fields": [
            str(item)
            for item in (
                production_ai_checkpoint.get(
                    "production_inference_actionable_operator_completion_diagnostic_required_fields"
                )
                or []
            )
        ],
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_required_field_count": _int(
            production_ai_checkpoint.get(
                "production_inference_actionable_operator_completion_diagnostic_required_field_count"
            )
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_completion_rule": _text(
            production_ai_checkpoint.get(
                "production_inference_actionable_operator_completion_diagnostic_completion_rule"
            )
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_return_artifacts": [
            str(item)
            for item in (
                production_ai_checkpoint.get(
                    "production_inference_actionable_operator_completion_diagnostic_return_artifacts"
                )
                or []
            )
        ],
        "production_ai_checkpoint_actionable_operator_completion_torch_visibility_probe_command": _text(
            production_ai_checkpoint.get(
                "production_inference_actionable_operator_completion_torch_visibility_probe_command"
            )
        ),
        "production_ai_checkpoint_actionable_operator_completion_failed_check_ids": [
            str(item)
            for item in (
                production_ai_checkpoint.get(
                    "production_inference_actionable_operator_completion_failed_check_ids"
                )
                or []
            )
        ],
        "production_ai_checkpoint_actionable_operator_completion_template_payload_json": _text(
            production_ai_checkpoint.get(
                "production_inference_actionable_operator_completion_template_payload_json"
            )
        ),
        "production_ai_checkpoint_actionable_operator_completion_validation_command": _text(
            production_ai_checkpoint.get("production_inference_actionable_operator_completion_validation_command")
        ),
        "production_ai_checkpoint_actionable_operator_completion_full_regeneration_command": _text(
            production_ai_checkpoint.get(
                "production_inference_actionable_operator_completion_full_regeneration_command"
            )
        ),
        "production_ai_checkpoint_actionable_operator_completion_completion_rule": _text(
            production_ai_checkpoint.get("production_inference_actionable_operator_completion_completion_rule")
        ),
        "production_ai_checkpoint_actionable_operator_completion_backend_provenance_completion_rule": _text(
            production_ai_checkpoint.get(
                "production_inference_actionable_operator_completion_backend_provenance_completion_rule"
            )
        ),
        "production_ai_checkpoint_actionable_operator_completion_next_action": _text(
            production_ai_checkpoint.get("production_inference_actionable_operator_completion_next_action")
        ),
        "production_ai_checkpoint_actionable_operator_completion_packet": (
            dict(production_ai_checkpoint.get("production_inference_actionable_operator_completion_packet"))
            if isinstance(
                production_ai_checkpoint.get("production_inference_actionable_operator_completion_packet"), dict
            )
            else {}
        ),
        "production_ai_checkpoint_worker_runtime_receipt_contract_ready": _bool(
            production_ai_checkpoint.get("production_inference_worker_runtime_receipt_contract_ready")
        ),
        "production_ai_checkpoint_worker_runtime_receipt_contract": (
            dict(production_ai_checkpoint.get("production_inference_worker_runtime_receipt_contract"))
            if isinstance(production_ai_checkpoint.get("production_inference_worker_runtime_receipt_contract"), dict)
            else {}
        ),
        "production_ai_checkpoint_worker_runtime_receipt_required_fields_or_columns": [
            str(item)
            for item in (
                production_ai_checkpoint.get(
                    "production_inference_worker_runtime_receipt_required_fields_or_columns"
                )
                or []
            )
        ],
        "production_ai_checkpoint_worker_runtime_receipt_required_field_count": _int(
            production_ai_checkpoint.get("production_inference_worker_runtime_receipt_required_field_count")
        ),
        "production_ai_checkpoint_worker_runtime_receipt_completion_rule": _text(
            production_ai_checkpoint.get("production_inference_worker_runtime_receipt_completion_rule")
        ),
        "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_stage_id": _text(
            production_ai_checkpoint.get(
                "production_inference_worker_runtime_receipt_post_environment_next_stage_id"
            )
        ),
        "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_artifact": _text(
            production_ai_checkpoint.get(
                "production_inference_worker_runtime_receipt_post_environment_next_artifact"
            )
        ),
        "production_ai_checkpoint_worker_runtime_receipt_post_environment_validation_command": _text(
            production_ai_checkpoint.get(
                "production_inference_worker_runtime_receipt_post_environment_validation_command"
            )
        ),
        "production_ai_checkpoint_worker_runtime_receipt_full_regeneration_command": _text(
            production_ai_checkpoint.get(
                "production_inference_worker_runtime_receipt_full_regeneration_command"
            )
        ),
        "production_ai_checkpoint_worker_runtime_receipt_guardrails": [
            str(item)
            for item in (
                production_ai_checkpoint.get("production_inference_worker_runtime_receipt_guardrails") or []
            )
        ],
        "production_ai_gpu_return_intake_status": _text(production_ai_gpu_return_intake.get("status")),
        "production_ai_gpu_return_intake_artifact_path": production_ai_gpu_return_intake_path,
        "production_ai_gpu_return_intake_ready": _bool(
            production_ai_gpu_return_intake.get("gpu_return_intake_ready")
        ),
        "production_ai_gpu_return_artifacts_ready": _bool(
            production_ai_gpu_return_intake.get("gpu_return_artifacts_ready")
        ),
        "production_ai_gpu_return_check_count": _int(production_ai_gpu_return_intake.get("check_count")),
        "production_ai_gpu_return_fail_check_count": _int(production_ai_gpu_return_intake.get("fail_check_count")),
        "production_ai_gpu_return_failed_check_ids": [
            str(item) for item in (production_ai_gpu_return_intake.get("failed_check_ids") or [])
        ],
        "production_ai_gpu_return_blocker_matrix": production_ai_gpu_return_blocker_matrix,
        "production_ai_gpu_return_blocker_matrix_count": len(production_ai_gpu_return_blocker_matrix),
        "production_ai_gpu_return_operator_return_bundle_contract_ready": _bool(
            production_ai_gpu_return_intake.get("operator_return_bundle_contract_ready")
        ),
        "production_ai_gpu_return_operator_return_blocker_count": _int(
            production_ai_gpu_return_intake.get("operator_return_blocker_count")
        ),
        "production_ai_gpu_return_first_failed_check_id": _text(
            production_ai_gpu_return_intake.get("first_failed_check_id")
        ),
        "production_ai_gpu_return_first_failed_source_artifact": _text(
            production_ai_gpu_return_intake.get("first_failed_source_artifact")
        ),
        "production_ai_gpu_return_first_failed_observed": _text(
            production_ai_gpu_return_intake.get("first_failed_observed")
        ),
        "production_ai_gpu_return_first_failed_required": _text(
            production_ai_gpu_return_intake.get("first_failed_required")
        ),
        "production_ai_gpu_return_first_failed_next_action": _text(
            production_ai_gpu_return_intake.get("first_failed_next_action")
        ),
        "production_ai_gpu_return_required_artifacts": [
            str(item) for item in (production_ai_gpu_return_intake.get("operator_return_required_artifacts") or [])
        ],
        "production_ai_gpu_return_required_artifact_count": _int(
            production_ai_gpu_return_intake.get("operator_return_required_artifact_count")
        ),
        "production_ai_gpu_return_operator_return_artifact_completion_matrix": (
            production_ai_gpu_return_operator_return_artifact_completion_matrix
        ),
        "production_ai_gpu_return_operator_return_artifact_completion_matrix_count": _int(
            production_ai_gpu_return_intake.get("operator_return_artifact_completion_matrix_count")
        ),
        "production_ai_gpu_return_operator_return_artifact_completion_blocker_matrix": (
            production_ai_gpu_return_operator_return_artifact_completion_blocker_matrix
        ),
        "production_ai_gpu_return_operator_return_artifact_completion_blocker_count": _int(
            production_ai_gpu_return_intake.get("operator_return_artifact_completion_blocker_count")
        ),
        "production_ai_gpu_return_operator_return_next_artifact_completion_packet_ready": _bool(
            production_ai_gpu_return_intake.get("operator_return_next_artifact_completion_packet_ready")
        ),
        "production_ai_gpu_return_operator_return_next_artifact_completion_packet": dict(
            production_ai_gpu_return_intake.get("operator_return_next_artifact_completion_packet") or {}
        ),
        "production_ai_gpu_return_operator_return_next_artifact_id": _text(
            production_ai_gpu_return_intake.get("operator_return_next_artifact_id")
        ),
        "production_ai_gpu_return_operator_return_next_artifact_path": _text(
            production_ai_gpu_return_intake.get("operator_return_next_artifact_path")
        ),
        "production_ai_gpu_return_operator_return_next_artifact_failed_check_ids": [
            str(item)
            for item in (
                production_ai_gpu_return_intake.get(
                    "operator_return_next_artifact_failed_check_ids"
                )
                or []
            )
        ],
        "production_ai_gpu_return_manifest_required_columns": [
            str(item)
            for item in (production_ai_gpu_return_intake.get("operator_return_manifest_required_columns") or [])
        ],
        "production_ai_gpu_return_validation_ladder_ready": _bool(
            production_ai_gpu_return_intake.get("operator_return_validation_ladder_ready")
        ),
        "production_ai_gpu_return_handoff_binding_ready": _bool(
            production_ai_gpu_return_intake.get("operator_return_handoff_binding_ready")
        ),
        "production_ai_gpu_return_handoff_queue_csv": _text(
            production_ai_gpu_return_intake.get("operator_return_handoff_queue_csv")
        ),
        "production_ai_gpu_return_handoff_queue_csv_sha256": _text(
            production_ai_gpu_return_intake.get("operator_return_handoff_queue_csv_sha256")
        ),
        "production_ai_gpu_return_handoff_full_regeneration_command": _text(
            production_ai_gpu_return_intake.get("operator_return_handoff_full_regeneration_command")
        ),
        "production_ai_gpu_return_handoff_return_manifest_schema_contract_ready": _bool(
            production_ai_gpu_return_intake.get("operator_return_handoff_return_manifest_schema_contract_ready")
        ),
        "production_ai_gpu_return_handoff_return_manifest_required_identity_rule": _text(
            production_ai_gpu_return_intake.get("operator_return_handoff_return_manifest_required_identity_rule")
        ),
        "production_ai_gpu_return_handoff_return_manifest_fingerprint_columns": [
            str(item)
            for item in (
                production_ai_gpu_return_intake.get(
                    "operator_return_handoff_return_manifest_fingerprint_columns"
                )
                or []
            )
        ],
        "production_ai_gpu_return_handoff_return_manifest_queue_id_columns": [
            str(item)
            for item in (
                production_ai_gpu_return_intake.get("operator_return_handoff_return_manifest_queue_id_columns")
                or []
            )
        ],
        "production_ai_gpu_return_handoff_return_manifest_npz_columns": [
            str(item)
            for item in (
                production_ai_gpu_return_intake.get("operator_return_handoff_return_manifest_npz_columns") or []
            )
        ],
        "production_ai_gpu_return_operator_acceptance_matrix_ready": _bool(
            production_ai_gpu_return_intake.get("operator_acceptance_matrix_ready")
        ),
        "production_ai_gpu_return_operator_acceptance_matrix": (
            production_ai_gpu_return_operator_acceptance_matrix
        ),
        "production_ai_gpu_return_operator_acceptance_current_blocked_stage_matrix": (
            production_ai_gpu_return_operator_acceptance_current_blocked_stage_matrix
        ),
        "production_ai_gpu_return_operator_acceptance_stage_check_matrix": [
            dict(row)
            for row in (
                production_ai_gpu_return_intake.get("operator_acceptance_stage_check_matrix") or []
            )
            if isinstance(row, dict)
        ],
        "production_ai_gpu_return_operator_acceptance_stage_check_matrix_count": _int(
            production_ai_gpu_return_intake.get("operator_acceptance_stage_check_matrix_count")
        ),
        "production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix": [
            dict(row)
            for row in (
                production_ai_gpu_return_intake.get("operator_acceptance_current_blocked_stage_check_matrix")
                or []
            )
            if isinstance(row, dict)
        ],
        "production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix_count": _int(
            production_ai_gpu_return_intake.get(
                "operator_acceptance_current_blocked_stage_check_matrix_count"
            )
        ),
        "production_ai_gpu_return_operator_acceptance_stage_count": _int(
            production_ai_gpu_return_intake.get("operator_acceptance_stage_count")
        ),
        "production_ai_gpu_return_operator_acceptance_ready_stage_count": _int(
            production_ai_gpu_return_intake.get("operator_acceptance_ready_stage_count")
        ),
        "production_ai_gpu_return_operator_acceptance_blocked_stage_count": _int(
            production_ai_gpu_return_intake.get("operator_acceptance_blocked_stage_count")
        ),
        "production_ai_gpu_return_operator_acceptance_stage_ids": [
            str(item) for item in (production_ai_gpu_return_intake.get("operator_acceptance_stage_ids") or [])
        ],
        "production_ai_gpu_return_operator_acceptance_ready_stage_ids": [
            str(item)
            for item in (production_ai_gpu_return_intake.get("operator_acceptance_ready_stage_ids") or [])
        ],
        "production_ai_gpu_return_operator_acceptance_blocked_stage_ids": [
            str(item)
            for item in (production_ai_gpu_return_intake.get("operator_acceptance_blocked_stage_ids") or [])
        ],
        "production_ai_gpu_return_operator_acceptance_next_stage_id": _text(
            production_ai_gpu_return_intake.get("operator_acceptance_next_stage_id")
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_artifact": _text(
            production_ai_gpu_return_intake.get("operator_acceptance_next_stage_artifact")
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_validation_command": _text(
            production_ai_gpu_return_intake.get("operator_acceptance_next_stage_validation_command")
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_release_effect": _text(
            production_ai_gpu_return_intake.get("operator_acceptance_next_stage_release_effect")
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_unlock_fields": [
            str(item)
            for item in (
                production_ai_gpu_return_intake.get("operator_acceptance_next_stage_unlock_fields") or []
            )
        ],
        "production_ai_gpu_return_operator_acceptance_next_stage_required_checks": [
            str(item)
            for item in (
                production_ai_gpu_return_intake.get("operator_acceptance_next_stage_required_checks") or []
            )
        ],
        "production_ai_gpu_return_operator_acceptance_next_stage_next_action": _text(
            production_ai_gpu_return_intake.get("operator_acceptance_next_stage_next_action")
        ),
        "production_ai_gpu_return_expected_queue_rows": _int(
            production_ai_gpu_return_intake.get("expected_queue_rows")
        ),
        "production_ai_gpu_return_manifest_template_csv": _text(
            production_ai_gpu_return_intake.get("manifest_template_csv")
        ),
        "production_ai_gpu_return_summary_template_csv": _text(
            production_ai_gpu_return_intake.get("summary_template_csv")
        ),
        "production_ai_gpu_return_summary_template_payload_json": _text(
            production_ai_gpu_return_intake.get("summary_template_payload_json")
        ),
        "production_ai_gpu_return_summary_template_required_fields": [
            str(item)
            for item in (production_ai_gpu_return_intake.get("summary_template_required_fields") or [])
        ],
        "production_ai_gpu_return_summary_template_completion_rule": _text(
            production_ai_gpu_return_intake.get("summary_template_completion_rule")
        ),
        "production_ai_gpu_return_summary_template_backend_provenance_contract_ready": _bool(
            production_ai_gpu_return_intake.get("summary_template_backend_provenance_contract_ready")
        ),
        "production_ai_gpu_return_summary_template_required_backend_provenance_fields": [
            str(item)
            for item in (
                production_ai_gpu_return_intake.get(
                    "summary_template_required_backend_provenance_fields"
                )
                or []
            )
        ],
        "production_ai_gpu_return_summary_template_backend_provenance_completion_rule": _text(
            production_ai_gpu_return_intake.get("summary_template_backend_provenance_completion_rule")
        ),
        "production_ai_gpu_return_manifest_template_row_count": _int(
            production_ai_gpu_return_intake.get("manifest_template_row_count")
        ),
        "production_ai_gpu_return_manifest_operator_verification_placeholder_count": _int(
            production_ai_gpu_return_intake.get("manifest_operator_verification_placeholder_count")
        ),
        "production_ai_gpu_return_actual_summary_return_path": _text(
            production_ai_gpu_return_intake.get("actual_summary_return_path")
        ),
        "production_ai_gpu_return_actual_manifest_return_path": _text(
            production_ai_gpu_return_intake.get("actual_manifest_return_path")
        ),
        "production_ai_gpu_summary_manifest_bound": _bool(
            production_ai_gpu_return_intake.get("summary_manifest_bound")
        ),
        "production_ai_gpu_summary_manifest_csv": _text(
            production_ai_gpu_return_intake.get("summary_manifest_csv")
        ),
        "production_ai_gpu_summary_out_manifest_csv_present": _bool(
            production_ai_gpu_return_intake.get("summary_out_manifest_csv_present")
        ),
        "production_ai_gpu_summary_out_manifest_csv": _text(
            production_ai_gpu_return_intake.get("summary_out_manifest_csv")
        ),
        "production_ai_gpu_summary_out_manifest_csv_bound": _bool(
            production_ai_gpu_return_intake.get("summary_out_manifest_csv_bound")
        ),
        "production_ai_gpu_summary_out_summary_json_bound": _bool(
            production_ai_gpu_return_intake.get("summary_out_summary_json_bound")
        ),
        "production_ai_gpu_summary_out_summary_json": _text(
            production_ai_gpu_return_intake.get("summary_out_summary_json")
        ),
        "production_ai_gpu_summary_manifest_row_counts_consistent": _bool(
            production_ai_gpu_return_intake.get("summary_manifest_row_counts_consistent")
        ),
        "production_ai_gpu_backend_provenance_ready": _bool(
            production_ai_gpu_return_intake.get("production_gpu_backend_provenance_ready")
        ),
        "production_ai_gpu_backend_rows": _int(
            production_ai_gpu_return_intake.get("production_gpu_backend_rows")
        ),
        "production_ai_gpu_backend_non_production_rows": _int(
            production_ai_gpu_return_intake.get("production_gpu_backend_non_production_rows")
        ),
        "production_ai_gpu_backend_prod_mode": _bool(
            production_ai_gpu_return_intake.get("production_gpu_backend_prod_mode")
        ),
        "production_ai_gpu_backend_require_rust_hip": _bool(
            production_ai_gpu_return_intake.get("production_gpu_backend_require_rust_hip")
        ),
        "production_ai_gpu_worker_rocm_manifest_artifact": _text(
            production_ai_gpu_return_intake.get("worker_rocm_manifest_artifact")
        ),
        "production_ai_gpu_worker_rocm_manifest_ready": _bool(
            production_ai_gpu_return_intake.get("worker_rocm_manifest_ready")
        ),
        "production_ai_gpu_worker_rocm_manifest_generation_command": _text(
            production_ai_gpu_return_intake.get("worker_rocm_manifest_generation_command")
        ),
        "production_ai_gpu_worker_rocm_manifest_completion_rule": _text(
            production_ai_gpu_return_intake.get("worker_rocm_manifest_completion_rule")
        ),
        "production_ai_gpu_worker_rocm_stack_detected": _bool(
            production_ai_gpu_return_intake.get("worker_rocm_stack_detected")
        ),
        "production_ai_gpu_worker_rocm_torch_ready": _bool(
            production_ai_gpu_return_intake.get("worker_rocm_torch_ready")
        ),
        "production_ai_gpu_worker_rocm_amd_gpu_detected": _bool(
            production_ai_gpu_return_intake.get("worker_rocm_amd_gpu_detected")
        ),
        "production_ai_gpu_worker_rocm_visible_device_count": _int(
            production_ai_gpu_return_intake.get("worker_rocm_visible_device_count")
        ),
        "production_ai_gpu_worker_rocm_device_names": [
            str(item) for item in (production_ai_gpu_return_intake.get("worker_rocm_device_names") or [])
        ],
        "production_ai_gpu_worker_rocm_next_required_step": _text(
            production_ai_gpu_return_intake.get("worker_rocm_next_required_step")
        ),
        "production_ai_checkpoint_gpu_backend_provenance_ready": _bool(
            production_ai_checkpoint.get("gpu_receipt_production_gpu_backend_provenance_ready")
        ),
        "production_ai_checkpoint_gpu_backend_rows": _int(
            production_ai_checkpoint.get("gpu_receipt_production_gpu_backend_rows")
        ),
        "production_ai_checkpoint_gpu_backend_non_production_rows": _int(
            production_ai_checkpoint.get("gpu_receipt_production_gpu_backend_non_production_rows")
        ),
        "production_ai_gpu_return_post_return_validation_command": _text(
            production_ai_gpu_return_intake.get("post_return_validation_command")
        ),
        "production_ai_gpu_return_next_required_step": _text(
            production_ai_gpu_return_intake.get("next_required_step")
        ),
        "production_ai_promotion_workbench_status": _text(production_ai_promotion_workbench.get("status")),
        "production_ai_promotion_workbench_ready": _bool(
            production_ai_promotion_workbench.get("promotion_workbench_ready")
        ),
        "production_ai_promotion_ready": _bool(
            production_ai_promotion_workbench.get("production_ai_promotion_ready")
        ),
        "production_ai_promotion_first_blocked_stage_id": _text(
            production_ai_promotion_workbench.get("first_blocked_stage_id")
        ),
        "production_ai_promotion_first_blocked_stage_artifact": _text(
            production_ai_promotion_workbench.get("first_blocked_stage_artifact")
        ),
        "production_ai_promotion_first_blocked_stage_ready_key": _text(
            production_ai_promotion_workbench.get("first_blocked_stage_ready_key")
        ),
        "production_ai_promotion_blocked_stage_count": _int(
            production_ai_promotion_workbench.get("post_return_promotion_ladder_blocked_stage_count")
        ),
        "production_ai_promotion_blocked_stage_ids": [
            str(item) for item in (production_ai_promotion_workbench.get("blocked_stage_ids") or [])
        ],
        "production_ai_force_gpu_worker_handoff_ready": _bool(
            production_ai_checkpoint.get("force_gpu_worker_handoff_ready")
        ),
        "production_ai_force_gpu_worker_operator_action_required": _bool(
            production_ai_checkpoint.get("force_gpu_worker_operator_action_required")
        ),
        "production_ai_force_gpu_operator_transfer_manifest_ready": _bool(
            production_ai_checkpoint.get("force_gpu_worker_operator_transfer_manifest_ready")
        ),
        "production_ai_force_gpu_operator_transfer_outbound_artifact_count": _int(
            production_ai_checkpoint.get("force_gpu_worker_operator_transfer_outbound_artifact_count")
        ),
        "production_ai_force_gpu_operator_transfer_outbound_artifacts": [
            str(item)
            for item in (
                production_ai_checkpoint.get("force_gpu_worker_operator_transfer_outbound_artifacts") or []
            )
        ],
        "production_ai_force_gpu_operator_transfer_inbound_artifact_count": _int(
            production_ai_checkpoint.get("force_gpu_worker_operator_transfer_inbound_artifact_count")
        ),
        "production_ai_force_gpu_operator_transfer_inbound_artifacts": [
            str(item)
            for item in (
                production_ai_checkpoint.get("force_gpu_worker_operator_transfer_inbound_artifacts") or []
            )
        ],
        "production_ai_force_gpu_operator_transfer_first_return_artifact": _text(
            production_ai_checkpoint.get("force_gpu_worker_operator_transfer_first_return_artifact")
        ),
        "production_ai_force_gpu_operator_transfer_return_manifest_artifact": _text(
            production_ai_checkpoint.get("force_gpu_worker_operator_transfer_return_manifest_artifact")
        ),
        "production_ai_force_gpu_operator_transfer_acceptance_artifact": _text(
            production_ai_checkpoint.get("force_gpu_worker_operator_transfer_acceptance_artifact")
        ),
        "production_ai_force_gpu_operator_transfer_acceptance_ready_key": _text(
            production_ai_checkpoint.get("force_gpu_worker_operator_transfer_acceptance_ready_key")
        ),
        "production_ai_force_gpu_operator_transfer_post_return_validation_command": _text(
            production_ai_checkpoint.get("force_gpu_worker_operator_transfer_post_return_validation_command")
        ),
        "production_ai_force_gpu_full_regeneration_command": _text(
            production_ai_checkpoint.get("force_gpu_worker_full_regeneration_command")
        ),
        "production_ai_force_gpu_post_return_validation_command": _text(
            production_ai_checkpoint.get("force_gpu_worker_post_return_validation_command")
        ),
        "production_ai_force_gpu_post_run_validation_commands": [
            str(item) for item in (production_ai_checkpoint.get("force_gpu_worker_post_run_validation_commands") or [])
        ],
        "production_ai_force_gpu_post_return_required_production_output_fields": [
            str(item)
            for item in (
                production_ai_checkpoint.get("force_gpu_worker_post_return_required_production_output_fields") or []
            )
        ],
        "production_ai_force_gpu_post_return_gpu_unlock_artifacts": [
            str(item) for item in (production_ai_checkpoint.get("force_gpu_worker_post_return_gpu_unlock_artifacts") or [])
        ],
        "production_ai_force_gpu_post_return_unlock_output_fields": [
            str(item) for item in (production_ai_checkpoint.get("force_gpu_worker_post_return_unlock_output_fields") or [])
        ],
        "production_ai_force_gpu_post_return_min_expected_label_rows": _int(
            production_ai_checkpoint.get("force_gpu_worker_post_return_min_expected_label_rows")
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_stage_count": _int(
            production_ai_checkpoint.get("force_gpu_worker_post_return_promotion_ladder_stage_count")
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_contract_ready": _bool(
            production_ai_checkpoint.get("force_gpu_worker_post_return_promotion_ladder_contract_ready")
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_currently_satisfied": _bool(
            production_ai_checkpoint.get("force_gpu_worker_post_return_promotion_ladder_currently_satisfied")
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_count": _int(
            production_ai_checkpoint.get(
                "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_count"
            )
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_ids": [
            str(item)
            for item in (
                production_ai_checkpoint.get(
                    "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_ids"
                )
                or []
            )
        ],
        "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_id": _text(
            production_ai_checkpoint.get("force_gpu_worker_post_return_promotion_ladder_current_next_stage_id")
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_artifact": _text(
            production_ai_checkpoint.get("force_gpu_worker_post_return_promotion_ladder_current_next_stage_artifact")
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_validation_command": _text(
            production_ai_checkpoint.get(
                "force_gpu_worker_post_return_promotion_ladder_current_next_stage_validation_command"
            )
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_stage_ids": [
            str(item)
            for item in (
                production_ai_checkpoint.get("force_gpu_worker_post_return_promotion_ladder_stage_ids") or []
            )
        ],
        "production_ai_force_gpu_post_return_promotion_ladder_missing_ready_keys": [
            str(item)
            for item in (
                production_ai_checkpoint.get("force_gpu_worker_post_return_promotion_ladder_missing_ready_keys")
                or []
            )
        ],
        "production_ai_checkpoint_acceptance_matrix_ready": _bool(
            production_ai_checkpoint.get("production_inference_acceptance_matrix_ready")
        ),
        "production_ai_checkpoint_acceptance_stage_count": _int(
            production_ai_checkpoint.get("production_inference_acceptance_stage_count")
        ),
        "production_ai_checkpoint_acceptance_ready_stage_count": _int(
            production_ai_checkpoint.get("production_inference_acceptance_ready_stage_count")
        ),
        "production_ai_checkpoint_acceptance_blocked_stage_count": _int(
            production_ai_checkpoint.get("production_inference_acceptance_blocked_stage_count")
        ),
        "production_ai_checkpoint_acceptance_stage_ids": [
            str(item) for item in (production_ai_checkpoint.get("production_inference_acceptance_stage_ids") or [])
        ],
        "production_ai_checkpoint_acceptance_ready_stage_ids": [
            str(item)
            for item in (production_ai_checkpoint.get("production_inference_acceptance_ready_stage_ids") or [])
        ],
        "production_ai_checkpoint_acceptance_blocked_stage_ids": [
            str(item)
            for item in (production_ai_checkpoint.get("production_inference_acceptance_blocked_stage_ids") or [])
        ],
        "production_ai_checkpoint_acceptance_matrix": production_ai_checkpoint_acceptance_matrix,
        "production_ai_checkpoint_acceptance_current_blocked_stage_matrix": (
            production_ai_checkpoint_acceptance_current_blocked_stage_matrix
        ),
        "production_ai_checkpoint_acceptance_release_blocker_stage_count": len(
            production_ai_checkpoint_acceptance_release_blocker_stage_ids
        ),
        "production_ai_checkpoint_acceptance_release_blocker_stage_ids": (
            production_ai_checkpoint_acceptance_release_blocker_stage_ids
        ),
        "production_ai_checkpoint_acceptance_next_stage_id": _text(
            production_ai_checkpoint.get("production_inference_acceptance_next_stage_id")
        ),
        "production_ai_checkpoint_acceptance_next_stage_artifact": _text(
            production_ai_checkpoint.get("production_inference_acceptance_next_stage_artifact")
        ),
        "production_ai_checkpoint_acceptance_next_stage_validation_command": _text(
            production_ai_checkpoint.get("production_inference_acceptance_next_stage_validation_command")
        ),
        "production_ai_checkpoint_acceptance_next_stage_release_effect": _text(
            production_ai_checkpoint.get("production_inference_acceptance_next_stage_release_effect")
        ),
        "production_ai_checkpoint_acceptance_next_stage_unlock_fields": [
            str(item)
            for item in (production_ai_checkpoint.get("production_inference_acceptance_next_stage_unlock_fields") or [])
        ],
        "production_ai_checkpoint_acceptance_next_stage_required_checks": [
            str(item)
            for item in (
                production_ai_checkpoint.get("production_inference_acceptance_next_stage_required_checks") or []
            )
        ],
        "production_ai_checkpoint_acceptance_next_stage_next_action": _text(
            production_ai_checkpoint.get("production_inference_acceptance_next_stage_next_action")
        ),
        "production_ai_force_gpu_receipt_manifest_identity_row_count": _int(
            production_ai_checkpoint.get("gpu_receipt_manifest_identity_row_count")
        ),
        "production_ai_force_gpu_receipt_matched_queue_id_count": _int(
            production_ai_checkpoint.get("gpu_receipt_manifest_matched_queue_id_count")
        ),
        "production_ai_force_gpu_receipt_matched_expected_npz_count": _int(
            production_ai_checkpoint.get("gpu_receipt_manifest_matched_expected_npz_count")
        ),
        "production_ai_force_gpu_receipt_matched_queue_fingerprint_count": _int(
            production_ai_checkpoint.get("gpu_receipt_manifest_matched_queue_fingerprint_count")
        ),
        "product_ai_scope_backlog_detail": product_ai_scope_backlog_detail,
        "product_scope_closure_blocker_class_counts": _counts_from_text(
            scope_observed_pairs.get("scope_closure_blocker_classes")
        ),
        "product_scope_first_scientific_blocker": _text(
            scope_observed_pairs.get("scope_closure_first_scientific_blocker")
        ),
        "product_scope_manual_review_subcheck_count": _int(
            scope_observed_pairs.get("scope_closure_manual_review_subcheck_count")
        ),
        "product_scope_transporter_manual_review_subcheck_count": _int(
            scope_observed_pairs.get("scope_closure_transporter_manual_review_subcheck_count")
        ),
        "product_scope_transporter_identity_scaffold_confirmation_required_count": _int(
            scope_observed_pairs.get("scope_closure_transporter_identity_scaffold_confirmation_required_count")
        ),
        "product_scope_transporter_direct_binding_or_kcal_confirmation_required_count": _int(
            scope_observed_pairs.get("scope_closure_transporter_direct_binding_or_kcal_confirmation_required_count")
        ),
        "product_scope_transporter_negative_quantitative_confirmation_required_count": _int(
            scope_observed_pairs.get("scope_closure_transporter_negative_quantitative_confirmation_required_count")
        ),
        "product_scope_transporter_direct_binding_missing_count": _int(
            scope_observed_pairs.get("scope_closure_transporter_direct_binding_missing_count")
        ),
        "product_scope_transporter_negative_quantitative_missing_count": _int(
            scope_observed_pairs.get("scope_closure_transporter_negative_quantitative_missing_count")
        ),
        "product_scope_pxr_reconciled_blocked_row_count": _int(
            0
            if pxr_currently_ready
            else scope_observed_pairs.get("scope_closure_pxr_reconciled_blocked_row_count")
        ),
        "product_scope_pxr_conflict_resolution_count": _int(
            0
            if pxr_currently_ready
            else scope_observed_pairs.get("scope_closure_pxr_conflict_resolution_count")
        ),
        "product_scope_pxr_quantitative_missing_count": _int(
            0
            if pxr_currently_ready
            else scope_observed_pairs.get("scope_closure_pxr_quantitative_missing_count")
        ),
        "product_scope_general_claim_blocker_count": _int(
            max(
                0,
                _int(scope_observed_pairs.get("scope_closure_general_claim_blocker_count"))
                - (1 if pxr_currently_ready and _int(scope_observed_pairs.get("scope_closure_general_claim_blocker_count")) else 0),
            )
        ),
        "product_scope_ready_for_apply_count": _int(scope_observed_pairs.get("scope_closure_ready_for_apply_count")),
        "product_scope_authoritative_apply_allowed": _bool_text(
            scope_observed_pairs.get("scope_closure_authoritative_apply_allowed")
        ),
        "product_scope_domain_count": _int(product_scope_breadth_contract.get("domain_count")),
        "product_scope_ready_domain_count": _int(product_scope_breadth_contract.get("ready_domain_count")),
        "product_scope_missing_domain_count": _int(product_scope_breadth_contract.get("missing_domain_count")),
        "product_scope_ready_domains": [
            str(item) for item in current_scope_ready_domains
        ],
        "product_scope_missing_domains": [
            str(item) for item in current_scope_missing_domains
        ],
        "product_scope_first_blocked_domain": _text(
            product_scope_breadth_contract.get("first_blocked_domain")
        ),
        "product_scope_first_blocked_domain_artifact": _text(
            product_scope_breadth_contract.get("first_blocked_domain_artifact")
        ),
        "product_scope_first_blocked_domain_observed": _text(
            product_scope_breadth_contract.get("first_blocked_domain_observed")
        ),
        "product_scope_first_blocked_domain_requirement": _text(
            product_scope_breadth_contract.get("first_blocked_domain_requirement")
        ),
        "product_scope_first_blocked_domain_next_action": _text(
            product_scope_breadth_contract.get("first_blocked_domain_next_action")
        ),
        "product_scope_transporter_p0_readiness_matrix_ready": _bool(
            product_scope_breadth_contract.get("transporter_p0_readiness_matrix_ready")
        ),
        "product_scope_transporter_p0_readiness_matrix_artifact": _text(
            product_scope_breadth_contract.get("transporter_p0_readiness_matrix_artifact")
        ),
        "product_scope_transporter_p0_auto_close_ready_artifact_count": _int(
            product_scope_breadth_contract.get("transporter_p0_auto_close_ready_artifact_count")
        ),
        "product_scope_transporter_p0_manual_or_external_required_artifact_count": _int(
            product_scope_breadth_contract.get("transporter_p0_manual_or_external_required_artifact_count")
        ),
        "product_scope_transporter_p0_unresolved_slot_count": _int(
            product_scope_breadth_contract.get("transporter_p0_unresolved_slot_count")
        ),
        "product_scope_transporter_p0_auto_close_ready_slot_count": _int(
            product_scope_breadth_contract.get("transporter_p0_auto_close_ready_slot_count")
        ),
        "product_scope_transporter_p0_external_exact_evidence_required_slot_count": _int(
            product_scope_breadth_contract.get("transporter_p0_external_exact_evidence_required_slot_count")
        ),
        "product_scope_transporter_p0_first_manual_or_external_required_step_id": _text(
            product_scope_breadth_contract.get("transporter_p0_first_manual_or_external_required_step_id")
        ),
        "product_scope_transporter_p0_first_manual_or_external_required_slot_step": _text(
            product_scope_breadth_contract.get("transporter_p0_first_manual_or_external_required_slot_step")
        ),
        "product_scope_transporter_p0_first_manual_or_external_required_action": _text(
            product_scope_breadth_contract.get("transporter_p0_first_manual_or_external_required_action")
        ),
        "product_scope_transporter_p0_evidence_acquisition_packet_ready": _bool(
            product_scope_breadth_contract.get("transporter_p0_evidence_acquisition_packet_ready")
        ),
        "product_scope_transporter_p0_evidence_acquisition_artifact": _text(
            product_scope_breadth_contract.get("transporter_p0_evidence_acquisition_artifact")
        ),
        "product_scope_transporter_p0_evidence_acquisition_exact_request_slot_count": _int(
            product_scope_breadth_contract.get("transporter_p0_evidence_acquisition_exact_request_slot_count")
        ),
        "product_scope_transporter_p0_evidence_acquisition_unresolved_slot_count": _int(
            product_scope_breadth_contract.get("transporter_p0_evidence_acquisition_unresolved_slot_count")
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_target_id": _text(
            product_scope_breadth_contract.get("transporter_p0_evidence_acquisition_first_target_id")
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_packet_step": _text(
            product_scope_breadth_contract.get("transporter_p0_evidence_acquisition_first_packet_step")
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_replacement_ligand_id": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_first_replacement_ligand_id"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_request_mode": _text(
            product_scope_breadth_contract.get("transporter_p0_evidence_acquisition_first_request_mode")
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_source_signal": _text(
            product_scope_breadth_contract.get("transporter_p0_evidence_acquisition_first_source_signal")
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_required_missing_fields": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_first_required_missing_fields"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_next_required_action": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_first_next_required_action"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": _bool(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_completion_packet_ready"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet": dict(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_completion_packet"
            )
            or {}
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts": [
            str(item)
            for item in (
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts"
                )
                or []
            )
        ],
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count": _int(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix": [
            dict(row)
            for row in (
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix"
                )
                or []
            )
            if isinstance(row, dict)
        ],
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count": _int(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count": _int(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_id": _text(
            product_scope_breadth_contract.get("transporter_p0_evidence_acquisition_next_slot_id")
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_operator_review_artifact"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready": _bool(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_source_modality"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe": _bool(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed": _bool(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_decision": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_source_modality_decision"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails": [
            str(item)
            for item in (
                product_scope_breadth_contract.get(
                    "transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails"
                )
                or []
            )
        ],
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count": _int(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count": _int(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count": _int(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_row_count": _int(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_row_count"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_claim_safe_ready_count": _int(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_claim_safe_ready_count"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_chembl_id": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_chembl_id"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_blocker": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_blocker"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_affinity_row_count": _int(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_affinity_row_count"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count": _int(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count": _int(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count": _int(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count"
            )
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail": _text(
            product_scope_breadth_contract.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_packet_ready": _bool(
            product_scope_breadth_contract.get("evidence_queue_next_operator_completion_packet_ready")
        ),
        "product_scope_evidence_queue_next_operator_completion_slot_id": _text(
            product_scope_breadth_contract.get("evidence_queue_next_operator_completion_slot_id")
        ),
        "product_scope_evidence_queue_next_operator_completion_expected_evidence_type": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_expected_evidence_type"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_field_count": _int(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_required_exact_evidence_field_count"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_fields": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_required_exact_evidence_fields"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_required_operator_intake_columns": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_required_operator_intake_columns"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_required_claim_guardrails": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_required_claim_guardrails"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_operator_review_artifact": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_operator_review_artifact"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_post_intake_synchronization_targets": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_post_intake_synchronization_targets"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_acceptance_gate_commands": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_acceptance_gate_commands"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_contract_artifact": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_contract_artifact"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_sidecar_ready": _bool(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_sidecar_ready"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_functional_surrogate_artifact": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_functional_surrogate_artifact"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_candidate_ledger_artifact": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_candidate_ledger_artifact"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_candidate_name": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_candidate_name"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_anchor": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_source_anchor"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_url": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_source_url"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_target_uniprot": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_target_uniprot"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_measure": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_functional_measure"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_assay_type_honesty": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_assay_type_honesty"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_binding_kcal_claim_allowed": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_binding_kcal_claim_allowed"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_claim_safe_functional_kcal_ready": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_claim_safe_functional_kcal_ready"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_review_bucket": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_ledger_review_bucket"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_promotion_policy": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_ledger_promotion_policy"
            )
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_caution": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_operator_completion_aqp1_review_ledger_caution"
            )
        ),
        "product_scope_general_platform_domain_floor_ready": (
            bool(product_scope_breadth_contract)
            and not [
                str(item)
                for item in (product_scope_breadth_contract.get("missing_domains") or [])
                if str(item) != "general_protein_ligand"
            ]
        ),
        "product_scope_general_platform_domain_floor_missing_domain_count": len(
            [
                str(item)
                for item in (product_scope_breadth_contract.get("missing_domains") or [])
                if str(item) != "general_protein_ligand"
            ]
        ),
        "product_scope_general_platform_domain_floor_missing_domains": [
            str(item)
            for item in (product_scope_breadth_contract.get("missing_domains") or [])
            if str(item) != "general_protein_ligand"
        ],
        "product_scope_allowed_families": _list_from_text(
            scope_observed_pairs.get("allowed_scope_families")
            or scope_claim_boundary_pairs.get("allowed_scope_families")
        )
        or current_scope_allowed_families,
        "product_scope_blocked_claim_scopes": (
            current_scope_blocked_claim_scopes
            or _list_from_text(scope_observed_pairs.get("blocked_claim_scopes"))
        ),
        "product_scope_claim_blocked_domains": (
            current_scope_claim_blocked_domains
            or _list_from_text(scope_observed_pairs.get("claim_blocked_domains"))
        ),
        "product_scope_general_platform_claim_allowed": _bool_text(
            str(product_scope_breadth_contract.get("general_platform_claim_allowed"))
            if "general_platform_claim_allowed" in product_scope_breadth_contract
            else scope_observed_pairs.get("general_platform_claim_allowed")
        ),
        "product_scope_evidence_priority_ready": _bool(scope_priority.get("priority_packet_ready")),
        "product_scope_evidence_priority_queue_item_count": _int(scope_priority.get("queue_item_count")),
        "product_scope_evidence_priority_open_item_count": _int(scope_priority.get("open_item_count")),
        "product_scope_evidence_priority_local_crosscheck_candidate_count": _int(
            scope_priority.get("local_crosscheck_candidate_count")
        ),
        "product_scope_evidence_priority_external_primary_exact_required_count": _int(
            scope_priority.get("external_primary_exact_evidence_required_count")
        ),
        "product_scope_evidence_priority_all_operator_packet_bindings_ready": _bool(
            scope_priority.get("all_operator_packet_bindings_ready")
        ),
        "product_scope_evidence_priority_operator_packet_binding_ready_count": _int(
            scope_priority.get("operator_packet_binding_ready_count")
        ),
        "product_scope_evidence_priority_operator_packet_binding_missing_count": _int(
            scope_priority.get("operator_packet_binding_missing_count")
        ),
        "product_scope_evidence_priority_top_item_id": _text(scope_top_priority.get("item_id")),
        "product_scope_evidence_priority_top_domain": _text(scope_top_priority.get("domain")),
        "product_scope_evidence_priority_top_bucket": _text(scope_top_priority.get("evidence_priority_bucket")),
        "product_scope_evidence_priority_top_required_evidence_type": _text(
            scope_top_priority.get("required_evidence_type") or scope_priority.get("top_required_evidence_type")
        ),
        "product_scope_evidence_priority_top_review_template_artifact": _text(
            scope_top_priority.get("review_template_artifact") or scope_priority.get("top_review_template_artifact")
        ),
        "product_scope_evidence_priority_top_apply_gate_artifact": _text(
            scope_top_priority.get("apply_gate_artifact") or scope_priority.get("top_apply_gate_artifact")
        ),
        "product_scope_evidence_priority_top_next_step": _text(scope_top_priority.get("next_step")),
        "product_scope_evidence_priority_next_required_step": _text(scope_priority.get("next_required_step")),
        "product_scope_evidence_intake_ready": _bool(scope_intake.get("intake_readiness_ready")),
        "product_scope_evidence_intake_row_count": _int(scope_intake.get("row_count")),
        "product_scope_evidence_intake_all_operator_packet_bindings_ready": _bool(
            scope_intake.get("all_operator_packet_bindings_ready")
        ),
        "product_scope_evidence_intake_operator_packet_binding_ready_count": _int(
            scope_intake.get("operator_packet_binding_ready_count")
        ),
        "product_scope_evidence_intake_operator_packet_binding_missing_count": _int(
            scope_intake.get("operator_packet_binding_missing_count")
        ),
        "product_scope_local_crosscheck_triage_item_count": _int(
            scope_intake.get("local_crosscheck_triage_item_count")
        ),
        "product_scope_local_crosscheck_intake_ready_count": _int(
            scope_intake.get("local_crosscheck_intake_ready_count")
        ),
        "product_scope_external_exact_evidence_required_count": _int(
            scope_intake.get("external_exact_evidence_required_count")
        ),
        "product_scope_guardrail_item_count": _int(scope_intake.get("guardrail_item_count")),
        "product_scope_transporter_triage_packet_ready": _bool(scope_intake.get("transporter_triage_packet_ready")),
        "product_scope_transporter_operator_review_evidence_matrix_ready": _bool(
            scope_intake.get("transporter_operator_review_evidence_matrix_ready")
        ),
        "product_scope_transporter_claim_safe_local_evidence_ready_count": _int(
            scope_intake.get("transporter_claim_safe_local_evidence_ready_count")
        ),
        "product_scope_transporter_claim_safe_local_evidence_blocked_count": _int(
            scope_intake.get("transporter_claim_safe_local_evidence_blocked_count")
        ),
        "product_scope_transporter_direct_binding_claim_blocked_count": _int(
            scope_intake.get("transporter_direct_binding_claim_blocked_count")
        ),
        "product_scope_transporter_negative_value_claim_blocked_count": _int(
            scope_intake.get("transporter_negative_value_claim_blocked_count")
        ),
        "product_scope_transporter_top_claim_safe_blocker": _text(
            scope_intake.get("transporter_top_claim_safe_blocker")
        ),
        "product_scope_transporter_top_operator_next_verdict": _text(
            scope_intake.get("transporter_top_operator_next_verdict")
        ),
        "product_scope_transporter_target_ready_for_promotion_count": _int(
            product_scope_breadth_contract.get("transporter_target_ready_for_promotion_count")
        ),
        "product_scope_transporter_target_blocked_for_promotion_count": _int(
            product_scope_breadth_contract.get("transporter_target_blocked_for_promotion_count")
        ),
        "product_scope_transporter_target_ready_for_promotion_ids": [
            str(item)
            for item in (
                product_scope_breadth_contract.get("transporter_target_ready_for_promotion_ids") or []
            )
        ],
        "product_scope_transporter_target_blocked_for_promotion_ids": [
            str(item)
            for item in (
                product_scope_breadth_contract.get("transporter_target_blocked_for_promotion_ids") or []
            )
        ],
        "product_scope_transporter_primary_blocker_target_id": _text(
            product_scope_breadth_contract.get("transporter_primary_blocker_target_id")
        ),
        "product_scope_transporter_primary_blocker_packet_step": _text(
            product_scope_breadth_contract.get("transporter_primary_blocker_packet_step")
        ),
        "product_scope_transporter_primary_blocker_candidate_name": _text(
            product_scope_breadth_contract.get("transporter_primary_blocker_candidate_name")
        ),
        "product_scope_transporter_candidate_assignment_required_count": _int(
            scope_intake.get("transporter_candidate_assignment_required_count")
        ),
        "product_scope_transporter_functional_quantitative_only_direct_gap_open_count": _int(
            scope_intake.get("transporter_functional_quantitative_only_direct_gap_open_count")
        ),
        "product_scope_transporter_review_only_direct_binding_gap_count": _int(
            scope_intake.get("transporter_review_only_direct_binding_gap_count")
        ),
        "product_scope_transporter_candidate_ready_for_manual_review_count": _int(
            scope_intake.get("transporter_candidate_ready_for_manual_review_count")
        ),
        "product_scope_transporter_candidate_ready_for_apply_count": _int(
            scope_intake.get("transporter_candidate_ready_for_apply_count")
        ),
        "product_scope_transporter_manual_review_intake_ready": _bool(
            scope_intake.get("transporter_manual_review_intake_ready")
        ),
        "product_scope_transporter_manual_review_template_row_count": _int(
            scope_intake.get("transporter_manual_review_template_row_count")
        ),
        "product_scope_transporter_manual_review_direct_binding_evidence_required_count": _int(
            scope_intake.get("transporter_manual_review_direct_binding_evidence_required_count")
        ),
        "product_scope_transporter_manual_review_negative_quantitative_value_required_count": _int(
            scope_intake.get("transporter_manual_review_negative_quantitative_value_required_count")
        ),
        "product_scope_transporter_manual_review_decision_placeholder_count": _int(
            scope_intake.get("transporter_manual_review_decision_placeholder_count")
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_row_count": _int(
            scope_intake.get("transporter_manual_review_p0_slot_overlay_row_count")
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_candidate_changed_count": _int(
            scope_intake.get("transporter_manual_review_p0_slot_overlay_candidate_changed_count")
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_first_item_id": _text(
            scope_intake.get("transporter_manual_review_p0_slot_overlay_first_item_id")
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id": _text(
            scope_intake.get("transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id")
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_first_source": _text(
            scope_intake.get("transporter_manual_review_p0_slot_overlay_first_source")
        ),
        "product_scope_transporter_manual_review_first_review_row_id": _text(
            scope_intake.get("first_review_row_id")
        ),
        "product_scope_transporter_manual_review_first_review_item_id": _text(
            scope_intake.get("first_review_item_id")
        ),
        "product_scope_transporter_manual_review_first_review_target_id": _text(
            scope_intake.get("first_review_target_id")
        ),
        "product_scope_transporter_manual_review_first_review_candidate_ligand_id": _text(
            scope_intake.get("first_review_candidate_ligand_id")
        ),
        "product_scope_transporter_manual_review_first_review_replacement_source": _text(
            scope_intake.get("first_review_replacement_source")
        ),
        "product_scope_transporter_manual_review_first_review_replacement_reference_binding_kcal_mol": _text(
            scope_intake.get("first_review_replacement_reference_binding_kcal_mol")
        ),
        "product_scope_transporter_manual_review_first_review_direct_binding_evidence_required": _bool(
            scope_intake.get("first_review_direct_binding_evidence_required")
        ),
        "product_scope_transporter_manual_review_first_review_direct_binding_source_url_or_doi": _text(
            scope_intake.get("first_review_direct_binding_source_url_or_doi")
        ),
        "product_scope_transporter_manual_review_first_review_negative_quantitative_value_required": _bool(
            scope_intake.get("first_review_negative_quantitative_value_required")
        ),
        "product_scope_transporter_manual_review_first_review_negative_reference_binding_kcal_mol": _text(
            scope_intake.get("first_review_negative_reference_binding_kcal_mol")
        ),
        "product_scope_transporter_manual_review_first_review_review_decision": _text(
            scope_intake.get("first_review_review_decision")
        ),
        "product_scope_transporter_manual_review_first_review_authoritative_apply_requested": _text(
            scope_intake.get("first_review_authoritative_apply_requested")
        ),
        "product_scope_transporter_manual_review_first_review_manual_review_blockers": _text(
            scope_intake.get("first_review_manual_review_blockers")
        ),
        "product_scope_transporter_manual_review_first_review_review_requirements": _text(
            scope_intake.get("first_review_review_requirements")
        ),
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_required_missing_fields": _text(
            scope_intake.get("first_review_p0_slot_overlay_required_missing_fields")
        ),
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_claim_safe_step_ready": _bool(
            scope_intake.get("first_review_p0_slot_overlay_claim_safe_step_ready")
        ),
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_authoritative_apply_allowed": _bool(
            scope_intake.get("first_review_p0_slot_overlay_authoritative_apply_allowed")
        ),
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_scope_promotion_allowed": _bool(
            scope_intake.get("first_review_p0_slot_overlay_scope_promotion_allowed")
        ),
        "product_scope_evidence_intake_next_required_step": _text(scope_intake.get("next_required_step")),
        "product_scope_breadth_contract_status": _text(product_scope_breadth_contract.get("status")),
        "product_scope_breadth_contract_artifact_path": product_scope_breadth_contract_path,
        "product_scope_operator_transfer_manifest_ready": _bool(
            product_scope_breadth_contract.get("scope_operator_transfer_manifest_ready")
        ),
        "product_scope_operator_transfer_outbound_artifact_count": _int(
            product_scope_breadth_contract.get("scope_operator_transfer_outbound_artifact_count")
        ),
        "product_scope_operator_transfer_outbound_artifacts": [
            str(item)
            for item in (product_scope_breadth_contract.get("scope_operator_transfer_outbound_artifacts") or [])
        ],
        "product_scope_operator_transfer_inbound_artifact_count": _int(
            product_scope_breadth_contract.get("scope_operator_transfer_inbound_artifact_count")
        ),
        "product_scope_operator_transfer_inbound_artifacts": [
            str(item)
            for item in (product_scope_breadth_contract.get("scope_operator_transfer_inbound_artifacts") or [])
        ],
        "product_scope_operator_transfer_first_return_artifact": _text(
            product_scope_breadth_contract.get("scope_operator_transfer_first_return_artifact")
        ),
        "product_scope_operator_transfer_acceptance_artifact": _text(
            product_scope_breadth_contract.get("scope_operator_transfer_acceptance_artifact")
        ),
        "product_scope_operator_transfer_acceptance_ready_key": _text(
            product_scope_breadth_contract.get("scope_operator_transfer_acceptance_ready_key")
        ),
        "product_scope_operator_transfer_next_acceptance_stage": _text(
            product_scope_breadth_contract.get("scope_operator_transfer_next_acceptance_stage")
        ),
        "product_scope_operator_transfer_post_return_validation_command": _text(
            product_scope_breadth_contract.get("scope_operator_transfer_post_return_validation_command")
        ),
        "product_scope_acceptance_matrix_ready": _bool(
            product_scope_breadth_contract.get("scope_acceptance_matrix_ready")
        ),
        "product_scope_claim_expansion_contract_ready": _bool(
            product_scope_breadth_contract.get("scope_claim_expansion_contract_ready")
        ),
        "product_scope_claim_expansion_currently_satisfied": _bool(
            product_scope_breadth_contract.get("scope_claim_expansion_currently_satisfied")
        ),
        "product_scope_claim_expansion_current_blocked_stage_count": _int(
            product_scope_breadth_contract.get("scope_claim_expansion_current_blocked_stage_count")
        ),
        "product_scope_claim_expansion_current_blocked_stage_ids": [
            str(item)
            for item in (
                product_scope_breadth_contract.get("scope_claim_expansion_current_blocked_stage_ids") or []
            )
        ],
        "product_scope_claim_expansion_current_next_stage_id": _text(
            product_scope_breadth_contract.get("scope_claim_expansion_current_next_stage_id")
        ),
        "product_scope_claim_expansion_current_next_stage_artifact": _text(
            product_scope_breadth_contract.get("scope_claim_expansion_current_next_stage_artifact")
        ),
        "product_scope_claim_expansion_current_next_stage_validation_command": _text(
            product_scope_breadth_contract.get("scope_claim_expansion_current_next_stage_validation_command")
        ),
        "product_scope_claim_expansion_current_next_stage_unlock_claim_scopes": [
            str(item)
            for item in (
                product_scope_breadth_contract.get(
                    "scope_claim_expansion_current_next_stage_unlock_claim_scopes"
                )
                or []
            )
        ],
        "product_scope_acceptance_stage_count": _int(
            product_scope_breadth_contract.get("scope_acceptance_stage_count")
        ),
        "product_scope_acceptance_ready_stage_count": _int(
            product_scope_breadth_contract.get("scope_acceptance_ready_stage_count")
        ),
        "product_scope_acceptance_blocked_stage_count": _int(
            product_scope_breadth_contract.get("scope_acceptance_blocked_stage_count")
        ),
        "product_scope_acceptance_stage_ids": [
            str(item) for item in (product_scope_breadth_contract.get("scope_acceptance_stage_ids") or [])
        ],
        "product_scope_acceptance_ready_stage_ids": [
            str(item) for item in (product_scope_breadth_contract.get("scope_acceptance_ready_stage_ids") or [])
        ],
        "product_scope_acceptance_blocked_stage_ids": [
            str(item) for item in (product_scope_breadth_contract.get("scope_acceptance_blocked_stage_ids") or [])
        ],
        "product_scope_acceptance_matrix": product_scope_acceptance_matrix,
        "product_scope_acceptance_current_blocked_stage_matrix": product_scope_acceptance_current_blocked_stage_matrix,
        "product_scope_acceptance_release_blocker_stage_count": len(product_scope_acceptance_release_blocker_stage_ids),
        "product_scope_acceptance_release_blocker_stage_ids": product_scope_acceptance_release_blocker_stage_ids,
        "product_scope_acceptance_next_stage_id": _text(
            product_scope_breadth_contract.get("scope_acceptance_next_stage_id")
        ),
        "product_scope_acceptance_next_stage_artifact": _text(
            product_scope_breadth_contract.get("scope_acceptance_next_stage_artifact")
        ),
        "product_scope_acceptance_next_stage_validation_command": _text(
            product_scope_breadth_contract.get("scope_acceptance_next_stage_validation_command")
        ),
        "product_scope_acceptance_next_stage_release_effect": _text(
            product_scope_breadth_contract.get("scope_acceptance_next_stage_release_effect")
        ),
        "product_scope_acceptance_next_stage_unlock_claim_scopes": [
            str(item)
            for item in (
                product_scope_breadth_contract.get("scope_acceptance_next_stage_unlock_claim_scopes") or []
            )
        ],
        "product_scope_acceptance_next_stage_required_checks": [
            str(item)
            for item in (
                product_scope_breadth_contract.get("scope_acceptance_next_stage_required_checks") or []
            )
        ],
        "product_scope_acceptance_next_stage_next_action": _text(
            product_scope_breadth_contract.get("scope_acceptance_next_stage_next_action")
        ),
        "product_scope_acceptance_stage_evidence_matrix": product_scope_acceptance_stage_evidence_matrix,
        "product_scope_acceptance_stage_evidence_matrix_count": _int(
            product_scope_breadth_contract.get("scope_acceptance_stage_evidence_matrix_count")
        ),
        "product_scope_acceptance_current_blocked_stage_evidence_matrix": (
            product_scope_acceptance_current_blocked_stage_evidence_matrix
        ),
        "product_scope_acceptance_current_blocked_stage_evidence_matrix_count": _int(
            product_scope_breadth_contract.get(
                "scope_acceptance_current_blocked_stage_evidence_matrix_count"
            )
        ),
        "product_scope_pxr_exact_review_intake_ready": _bool(
            pxr_exact_review.get("pxr_exact_review_intake_ready")
        ),
        "product_scope_pxr_exact_review_template_row_count": _int(
            pxr_exact_review.get("review_template_row_count")
        ),
        "product_scope_pxr_exact_review_expected_blocked_row_count": _int(
            pxr_exact_review.get("expected_blocked_row_count")
        ),
        "product_scope_pxr_exact_review_conflict_resolution_required_count": _int(
            pxr_exact_review.get("conflict_resolution_required_count")
        ),
        "product_scope_pxr_exact_review_kcal_placeholder_count": _int(
            pxr_exact_review.get("kcal_placeholder_count")
        ),
        "product_scope_pxr_exact_review_source_placeholder_count": _int(
            pxr_exact_review.get("source_placeholder_count")
        ),
        "product_scope_pxr_exact_review_target_match_placeholder_count": _int(
            pxr_exact_review.get("target_match_placeholder_count")
        ),
        "product_scope_pxr_exact_review_decision_placeholder_count": _int(
            pxr_exact_review.get("review_decision_placeholder_count")
        ),
        "product_scope_pxr_exact_review_next_review_completion_packet_ready": _bool(
            pxr_exact_review.get("next_review_completion_packet_ready")
        ),
        "product_scope_pxr_exact_review_next_review_completion_packet": dict(
            pxr_exact_review.get("next_review_completion_packet") or {}
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_required_artifacts": [
            str(item) for item in (pxr_exact_review.get("next_review_return_bundle_required_artifacts") or [])
        ],
        "product_scope_pxr_exact_review_next_review_return_bundle_required_artifact_count": _int(
            pxr_exact_review.get("next_review_return_bundle_required_artifact_count")
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix": [
            dict(item)
            for item in (pxr_exact_review.get("next_review_return_bundle_completion_matrix") or [])
            if isinstance(item, dict)
        ],
        "product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix_count": _int(
            pxr_exact_review.get("next_review_return_bundle_completion_matrix_count")
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_blocker_count": _int(
            pxr_exact_review.get("next_review_return_bundle_blocker_count")
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_id": _text(
            pxr_exact_review.get("next_review_return_bundle_next_artifact_id")
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_path": _text(
            pxr_exact_review.get("next_review_return_bundle_next_artifact_path")
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids": [
            str(item)
            for item in (
                pxr_exact_review.get("next_review_return_bundle_next_artifact_failed_check_ids") or []
            )
        ],
        "product_scope_pxr_exact_review_next_review_row_id": _text(
            pxr_exact_review.get("next_review_row_id")
        ),
        "product_scope_pxr_exact_review_next_review_candidate_name": _text(
            pxr_exact_review.get("next_review_candidate_name")
        ),
        "product_scope_pxr_exact_review_next_review_operator_review_artifact": _text(
            pxr_exact_review.get("next_review_operator_review_artifact")
        ),
        "product_scope_pxr_exact_review_next_required_step": _text(
            pxr_exact_review.get("next_required_step")
        ),
        "product_scope_pxr_source_modality_triage_ready": _bool(
            product_scope_breadth_contract.get("pxr_source_modality_triage_ready")
        ),
        "product_scope_pxr_source_modality_triage_status": _text(
            product_scope_breadth_contract.get("pxr_source_modality_triage_status")
        ),
        "product_scope_pxr_source_modality_triage_artifact": _text(
            product_scope_breadth_contract.get("pxr_source_modality_triage_artifact")
        ),
        "product_scope_pxr_source_modality_triage_decision": _text(
            product_scope_breadth_contract.get("pxr_source_modality_triage_decision")
        ),
        "product_scope_pxr_source_modality_public_evidence_recheck_ready": _bool(
            product_scope_breadth_contract.get("pxr_source_modality_public_evidence_recheck_ready")
        ),
        "product_scope_pxr_source_modality_public_recheck_artifact": _text(
            product_scope_breadth_contract.get("pxr_source_modality_public_recheck_artifact")
        ),
        "product_scope_pxr_source_modality_public_recheck_candidate_count": _int(
            product_scope_breadth_contract.get("pxr_source_modality_public_recheck_candidate_count")
        ),
        "product_scope_pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count": _int(
            product_scope_breadth_contract.get(
                "pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count"
            )
        ),
        "product_scope_pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count": _int(
            product_scope_breadth_contract.get(
                "pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count"
            )
        ),
        "product_scope_pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count": _int(
            product_scope_breadth_contract.get(
                "pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count"
            )
        ),
        "product_scope_pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count": _int(
            product_scope_breadth_contract.get(
                "pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count"
            )
        ),
        "product_scope_pxr_source_modality_public_recheck_all_candidates_remain_blocked": _bool(
            product_scope_breadth_contract.get("pxr_source_modality_public_recheck_all_candidates_remain_blocked")
        ),
        "product_scope_pxr_source_modality_public_recheck_first_blocked_candidate_name": _text(
            product_scope_breadth_contract.get(
                "pxr_source_modality_public_recheck_first_blocked_candidate_name"
            )
        ),
        "product_scope_pxr_source_modality_public_recheck_first_blocked_reason": _text(
            product_scope_breadth_contract.get("pxr_source_modality_public_recheck_first_blocked_reason")
        ),
        "product_scope_pxr_source_modality_direct_replacement_candidate_packet_ready": _bool(
            product_scope_breadth_contract.get("pxr_source_modality_direct_replacement_candidate_packet_ready")
        ),
        "product_scope_pxr_source_modality_direct_replacement_artifact": _text(
            product_scope_breadth_contract.get("pxr_source_modality_direct_replacement_artifact")
        ),
        "product_scope_pxr_source_modality_direct_replacement_candidate_count": _int(
            product_scope_breadth_contract.get("pxr_source_modality_direct_replacement_candidate_count")
        ),
        "product_scope_pxr_source_modality_direct_replacement_selected_candidate_count": _int(
            product_scope_breadth_contract.get("pxr_source_modality_direct_replacement_selected_candidate_count")
        ),
        "product_scope_pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count": _int(
            product_scope_breadth_contract.get(
                "pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count"
            )
        ),
        "product_scope_pxr_source_modality_direct_replacement_first_ligand_id": _text(
            product_scope_breadth_contract.get("pxr_source_modality_direct_replacement_first_ligand_id")
        ),
        "product_scope_pxr_source_modality_direct_replacement_first_molecule_chembl_id": _text(
            product_scope_breadth_contract.get("pxr_source_modality_direct_replacement_first_molecule_chembl_id")
        ),
        "product_scope_pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol": _text(
            product_scope_breadth_contract.get(
                "pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol"
            )
        ),
        "product_scope_pxr_source_modality_direct_replacement_first_source": _text(
            product_scope_breadth_contract.get("pxr_source_modality_direct_replacement_first_source")
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_ready": _bool(
            product_scope_breadth_contract.get(
                "pxr_source_modality_direct_replacement_apply_draft_ready"
            )
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_status": _text(
            product_scope_breadth_contract.get(
                "pxr_source_modality_direct_replacement_apply_draft_status"
            )
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_artifact": _text(
            product_scope_breadth_contract.get(
                "pxr_source_modality_direct_replacement_apply_draft_artifact"
            )
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_workbook_row_count": _int(
            product_scope_breadth_contract.get(
                "pxr_source_modality_direct_replacement_apply_draft_workbook_row_count"
            )
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft": _int(
            product_scope_breadth_contract.get(
                "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft"
            )
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_overlay_row_count": _int(
            product_scope_breadth_contract.get(
                "pxr_source_modality_direct_replacement_apply_draft_overlay_row_count"
            )
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft": _int(
            product_scope_breadth_contract.get(
                "pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft"
            )
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft": _int(
            product_scope_breadth_contract.get(
                "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft"
            )
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id": _text(
            product_scope_breadth_contract.get(
                "pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id"
            )
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched": _bool(
            product_scope_breadth_contract.get(
                "pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched"
            )
        ),
        "product_scope_pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count": _int(
            product_scope_breadth_contract.get(
                "pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count"
            )
        ),
        "product_scope_pxr_source_modality_direct_or_claim_safe_quantitative_ready_count": _int(
            product_scope_breadth_contract.get(
                "pxr_source_modality_direct_or_claim_safe_quantitative_ready_count"
            )
        ),
        "product_scope_pxr_source_modality_accepted_for_scope_promotion_count": _int(
            product_scope_breadth_contract.get("pxr_source_modality_accepted_for_scope_promotion_count")
        ),
        "product_scope_pxr_source_modality_next_review_row_id": _text(
            product_scope_breadth_contract.get("pxr_source_modality_next_review_row_id")
        ),
        "product_scope_pxr_source_modality_next_review_candidate_name": _text(
            product_scope_breadth_contract.get("pxr_source_modality_next_review_candidate_name")
        ),
        "product_scope_pxr_source_modality_next_review_source_modality": _text(
            product_scope_breadth_contract.get("pxr_source_modality_next_review_source_modality")
        ),
        "product_scope_pxr_source_modality_next_review_rejection_reason": _text(
            product_scope_breadth_contract.get("pxr_source_modality_next_review_rejection_reason")
        ),
        "product_scope_evidence_queue_pxr_exact_review_sidecar_row_count": _int(
            product_scope_breadth_contract.get("evidence_queue_pxr_exact_review_sidecar_row_count")
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_sidecar_ready": _bool(
            product_scope_breadth_contract.get("evidence_queue_next_pxr_exact_review_sidecar_ready")
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_row_id": _text(
            product_scope_breadth_contract.get("evidence_queue_next_pxr_exact_review_row_id")
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_candidate_name": _text(
            product_scope_breadth_contract.get("evidence_queue_next_pxr_exact_review_candidate_name")
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_required_evidence_mode": _text(
            product_scope_breadth_contract.get("evidence_queue_next_pxr_exact_review_required_evidence_mode")
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_target_match_confirmed": _text(
            product_scope_breadth_contract.get("evidence_queue_next_pxr_exact_review_target_match_confirmed")
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol"
            )
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi": _text(
            product_scope_breadth_contract.get(
                "evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi"
            )
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_authoritative_apply_allowed": _bool(
            product_scope_breadth_contract.get(
                "evidence_queue_next_pxr_exact_review_authoritative_apply_allowed"
            )
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_scope_promotion_allowed": _bool(
            product_scope_breadth_contract.get(
                "evidence_queue_next_pxr_exact_review_scope_promotion_allowed"
            )
        ),
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Goal completion is proven by current artifacts."
            if not failed
            else "Resolve the primary bottleneck, rerun release gates, and rebuild this completion audit."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Goal Completion Audit",
        "",
        f"- status: `{s['status']}`",
        f"- goal_complete: `{s['goal_complete']}`",
        f"- restricted_delivery_complete: `{s['restricted_delivery_complete']}`",
        f"- release_blocker_fail_count: `{s['release_blocker_fail_count']}`",
        f"- optional_requirement_fail_count: `{s['optional_requirement_fail_count']}`",
        f"- product_ai_optional_lane_ready: `{s['product_ai_optional_lane_ready']}`",
        f"- product_scope_breadth_evidence_receipt_ready: `{s['product_scope_breadth_evidence_receipt_ready']}`",
        f"- product_scope_breadth_evidence_receipt_status: `{s['product_scope_breadth_evidence_receipt_status']}`",
        f"- product_scope_breadth_evidence_receipt_artifact: `{s['product_scope_breadth_evidence_receipt_artifact']}`",
        f"- engine_refinement_claim_promotion_ready: `{s['engine_refinement_claim_promotion_ready']}`",
        f"- engine_refinement_claim_promotion_blocker_count: `{s['engine_refinement_claim_promotion_blocker_count']}`",
        f"- engine_refinement_claim_promotion_action_board_csv: `{s['engine_refinement_claim_promotion_action_board_csv']}`",
        f"- engine_refinement_claim_evidence_receipt_ready: `{s['engine_refinement_claim_evidence_receipt_ready']}`",
        f"- engine_refinement_claim_evidence_receipt_artifact: `{s['engine_refinement_claim_evidence_receipt_artifact']}`",
        f"- requirement_count: `{s['requirement_count']}`",
        f"- pass_count: `{s['pass_count']}`",
        f"- fail_count: `{s['fail_count']}`",
        f"- primary_bottleneck_phase: `{s['primary_bottleneck_phase']}`",
        f"- primary_bottleneck_kind: `{s['primary_bottleneck_kind']}`",
        f"- product_ai_primary_backlog_detail: `{s['product_ai_primary_backlog_detail']}`",
        f"- product_ai_primary_backlog_work_item_id: `{s['product_ai_primary_backlog_work_item_id']}`",
        f"- product_ai_primary_backlog_acceptance_criteria: `{s['product_ai_primary_backlog_acceptance_criteria']}`",
        f"- product_ai_primary_backlog_next_action: `{s['product_ai_primary_backlog_next_action']}`",
        f"- product_ai_architecture_gap_status: `{s['product_ai_architecture_gap_status']}`",
        f"- product_ai_architecture_all_gaps_closed: `{s['product_ai_architecture_all_gaps_closed']}`",
        f"- product_ai_architecture_closed_gap_count: `{s['product_ai_architecture_closed_gap_count']}` / `{s['product_ai_architecture_gap_count']}`",
        f"- product_ai_architecture_open_gap_count: `{s['product_ai_architecture_open_gap_count']}`",
        f"- product_ai_architecture_open_gap_ids: `{';'.join(s['product_ai_architecture_open_gap_ids'])}`",
        f"- product_ai_production_checkpoint_gap_ready: `{s['product_ai_production_checkpoint_gap_ready']}`",
        f"- product_ai_closed_loop_decision_graph_ready: `{s['product_ai_closed_loop_decision_graph_ready']}`",
        f"- product_ai_durable_job_orchestration_ready: `{s['product_ai_durable_job_orchestration_ready']}`",
        f"- product_ai_trajectory_sla_ready: `{s['product_ai_trajectory_sla_ready']}`",
        f"- product_ai_trajectory_sla_claim_tier: `{s['product_ai_trajectory_sla_claim_tier']}`",
        f"- product_ai_trajectory_sla_restricted_family_allowed: `{s['product_ai_trajectory_sla_restricted_family_allowed']}`",
        f"- product_ai_trajectory_sla_broad_platform_allowed: `{s['product_ai_trajectory_sla_broad_platform_allowed']}`",
        f"- product_ai_trajectory_sla_current_rocm_baseline_claim_scope: `{s['product_ai_trajectory_sla_current_rocm_baseline_claim_scope']}`",
        f"- product_ai_trajectory_sla_current_rocm_baseline_production_profile_enabled: `{s['product_ai_trajectory_sla_current_rocm_baseline_production_profile_enabled']}`",
        f"- product_ai_scope_breadth_ready: `{s['product_ai_scope_breadth_ready']}`",
        f"- product_ai_report_ux_ready: `{s['product_ai_report_ux_ready']}`",
        f"- product_ai_report_ux_customer_report_viewer_binding_ready: `{s['product_ai_report_ux_customer_report_viewer_binding_ready']}`",
        f"- product_ai_security_deployment_ready: `{s['product_ai_security_deployment_ready']}`",
        f"- product_ai_security_hosted_deployment_contract_ready: `{s['product_ai_security_hosted_deployment_contract_ready']}`",
        f"- product_ai_security_hosted_deployment_currently_satisfied: `{s['product_ai_security_hosted_deployment_currently_satisfied']}`",
        f"- product_ai_security_hosted_deployment_next_stage_id: `{s['product_ai_security_hosted_deployment_next_stage_id']}`",
        f"- production_ai_gpu_worker_return_receipt_ready: `{s['production_ai_gpu_worker_return_receipt_ready']}`",
        f"- production_ai_gpu_worker_return_receipt_blockers: `{';'.join(s['production_ai_gpu_worker_return_receipt_blockers'])}`",
        f"- production_ai_gpu_expected_queue_rows: `{s['production_ai_gpu_expected_queue_rows']}`",
        f"- production_ai_gpu_manifest_ok_row_count: `{s['production_ai_gpu_manifest_ok_row_count']}`",
        f"- production_ai_gpu_manifest_npz_paths_complete: `{s['production_ai_gpu_manifest_npz_paths_complete']}`",
        f"- production_ai_gpu_manifest_npz_files_exist: `{s['production_ai_gpu_manifest_npz_files_exist']}`",
        f"- production_ai_gpu_manifest_npz_files_valid: `{s['production_ai_gpu_manifest_npz_files_valid']}`",
        f"- production_ai_gpu_manifest_npz_schema_valid: `{s['production_ai_gpu_manifest_npz_schema_valid']}`",
        f"- production_ai_gpu_manifest_npz_identity_valid: `{s['production_ai_gpu_manifest_npz_identity_valid']}`",
        f"- production_ai_gpu_manifest_npz_path_present_count: `{s['production_ai_gpu_manifest_npz_path_present_count']}`",
        f"- production_ai_gpu_manifest_npz_file_existing_count: `{s['production_ai_gpu_manifest_npz_file_existing_count']}`",
        f"- production_ai_gpu_manifest_npz_file_valid_count: `{s['production_ai_gpu_manifest_npz_file_valid_count']}`",
        f"- production_ai_gpu_manifest_npz_schema_valid_count: `{s['production_ai_gpu_manifest_npz_schema_valid_count']}`",
        f"- production_ai_gpu_manifest_npz_identity_valid_count: `{s['production_ai_gpu_manifest_npz_identity_valid_count']}`",
        f"- production_ai_gpu_manifest_operator_verified: `{s['production_ai_gpu_manifest_operator_verified']}`",
        f"- production_ai_gpu_summary_manifest_row_counts_consistent: `{s['production_ai_gpu_summary_manifest_row_counts_consistent']}`",
        f"- production_ai_force_derivation_input_ready: `{s['production_ai_force_derivation_input_ready']}`",
        f"- production_ai_delta_force_derivation_validation_ready: `{s['production_ai_delta_force_derivation_validation_ready']}`",
        f"- production_ai_checkpoint_readiness_status: `{s['production_ai_checkpoint_readiness_status']}`",
        f"- production_ai_checkpoint_ready: `{s['production_ai_checkpoint_ready']}`",
        f"- production_ai_checkpoint_failed_check_ids: `{';'.join(s['production_ai_checkpoint_failed_check_ids'])}`",
        f"- production_ai_checkpoint_first_failed_check_id: `{s['production_ai_checkpoint_first_failed_check_id']}`",
        f"- production_ai_checkpoint_first_failed_source_artifact: `{s['production_ai_checkpoint_first_failed_source_artifact']}`",
        f"- production_ai_checkpoint_first_failed_next_action: `{s['production_ai_checkpoint_first_failed_next_action']}`",
        f"- production_ai_checkpoint_actionable_blocker_stage_id: `{s['production_ai_checkpoint_actionable_blocker_stage_id']}`",
        f"- production_ai_checkpoint_actionable_blocker_check_id: `{s['production_ai_checkpoint_actionable_blocker_check_id']}`",
        f"- production_ai_checkpoint_actionable_blocker_artifact: `{s['production_ai_checkpoint_actionable_blocker_artifact']}`",
        f"- production_ai_checkpoint_actionable_blocker_downstream_blocked_stage_count: `{s['production_ai_checkpoint_actionable_blocker_downstream_blocked_stage_count']}`",
        f"- production_ai_checkpoint_actionable_operator_completion_packet_ready: `{s['production_ai_checkpoint_actionable_operator_completion_packet_ready']}`",
        f"- production_ai_checkpoint_actionable_operator_completion_artifact_id: `{s['production_ai_checkpoint_actionable_operator_completion_artifact_id'] or '-'}`",
        f"- production_ai_checkpoint_actionable_operator_completion_artifact_path: `{s['production_ai_checkpoint_actionable_operator_completion_artifact_path'] or '-'}`",
        f"- production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count: `{s['production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count']}`",
        f"- production_ai_checkpoint_actionable_operator_completion_diagnostic_completion_rule: `{s['production_ai_checkpoint_actionable_operator_completion_diagnostic_completion_rule'] or '-'}`",
        f"- production_ai_checkpoint_actionable_operator_completion_completion_rule: `{s['production_ai_checkpoint_actionable_operator_completion_completion_rule'] or '-'}`",
        f"- production_ai_checkpoint_worker_runtime_receipt_contract_ready: `{s['production_ai_checkpoint_worker_runtime_receipt_contract_ready']}`",
        f"- production_ai_checkpoint_worker_runtime_receipt_required_field_count: `{s['production_ai_checkpoint_worker_runtime_receipt_required_field_count']}`",
        f"- production_ai_checkpoint_worker_runtime_receipt_post_environment_next_stage_id: `{s['production_ai_checkpoint_worker_runtime_receipt_post_environment_next_stage_id']}`",
        f"- production_ai_checkpoint_worker_runtime_receipt_post_environment_next_artifact: `{s['production_ai_checkpoint_worker_runtime_receipt_post_environment_next_artifact']}`",
        f"- production_ai_checkpoint_acceptance_matrix_ready: `{s['production_ai_checkpoint_acceptance_matrix_ready']}`",
        f"- production_ai_checkpoint_acceptance_ready_stage_count: `{s['production_ai_checkpoint_acceptance_ready_stage_count']}`",
        f"- production_ai_checkpoint_acceptance_blocked_stage_count: `{s['production_ai_checkpoint_acceptance_blocked_stage_count']}`",
        f"- production_ai_checkpoint_acceptance_release_blocker_stage_ids: `{';'.join(s['production_ai_checkpoint_acceptance_release_blocker_stage_ids'])}`",
        f"- production_ai_checkpoint_acceptance_next_stage_id: `{s['production_ai_checkpoint_acceptance_next_stage_id']}`",
        f"- production_ai_checkpoint_acceptance_next_stage_artifact: `{s['production_ai_checkpoint_acceptance_next_stage_artifact']}`",
        f"- production_ai_checkpoint_acceptance_next_stage_validation_command: `{s['production_ai_checkpoint_acceptance_next_stage_validation_command']}`",
        f"- production_ai_gpu_return_intake_status: `{s['production_ai_gpu_return_intake_status']}`",
        f"- production_ai_gpu_return_intake_ready: `{s['production_ai_gpu_return_intake_ready']}`",
        f"- production_ai_gpu_return_artifacts_ready: `{s['production_ai_gpu_return_artifacts_ready']}`",
        f"- production_ai_gpu_return_failed_check_ids: `{';'.join(s['production_ai_gpu_return_failed_check_ids'])}`",
        f"- production_ai_gpu_return_blocker_matrix_count: `{s['production_ai_gpu_return_blocker_matrix_count']}`",
        f"- production_ai_gpu_return_operator_return_bundle_contract_ready: `{s['production_ai_gpu_return_operator_return_bundle_contract_ready']}`",
        f"- production_ai_gpu_return_operator_return_blocker_count: `{s['production_ai_gpu_return_operator_return_blocker_count']}`",
        f"- production_ai_gpu_return_operator_return_artifact_completion_matrix_count: `{s['production_ai_gpu_return_operator_return_artifact_completion_matrix_count']}`",
        f"- production_ai_gpu_return_operator_return_artifact_completion_blocker_count: `{s['production_ai_gpu_return_operator_return_artifact_completion_blocker_count']}`",
        f"- production_ai_gpu_return_operator_return_next_artifact_completion_packet_ready: `{s['production_ai_gpu_return_operator_return_next_artifact_completion_packet_ready']}`",
        f"- production_ai_gpu_return_operator_return_next_artifact_id: `{s['production_ai_gpu_return_operator_return_next_artifact_id']}`",
        f"- production_ai_gpu_return_operator_return_next_artifact_path: `{s['production_ai_gpu_return_operator_return_next_artifact_path']}`",
        f"- production_ai_gpu_return_first_failed_check_id: `{s['production_ai_gpu_return_first_failed_check_id']}`",
        f"- production_ai_gpu_return_first_failed_source_artifact: `{s['production_ai_gpu_return_first_failed_source_artifact']}`",
        f"- production_ai_gpu_return_first_failed_observed: `{s['production_ai_gpu_return_first_failed_observed']}`",
        f"- production_ai_gpu_return_first_failed_next_action: `{s['production_ai_gpu_return_first_failed_next_action']}`",
        f"- production_ai_gpu_return_required_artifacts: `{';'.join(s['production_ai_gpu_return_required_artifacts'])}`",
        f"- production_ai_gpu_return_manifest_required_columns: `{';'.join(s['production_ai_gpu_return_manifest_required_columns'])}`",
        f"- production_ai_gpu_return_handoff_binding_ready: `{s['production_ai_gpu_return_handoff_binding_ready']}`",
        f"- production_ai_gpu_return_handoff_queue_csv: `{s['production_ai_gpu_return_handoff_queue_csv']}`",
        f"- production_ai_gpu_return_handoff_queue_csv_sha256: `{s['production_ai_gpu_return_handoff_queue_csv_sha256']}`",
        f"- production_ai_gpu_return_handoff_return_manifest_required_identity_rule: `{s['production_ai_gpu_return_handoff_return_manifest_required_identity_rule']}`",
        f"- production_ai_gpu_return_summary_template_csv: `{s['production_ai_gpu_return_summary_template_csv']}`",
        f"- production_ai_gpu_return_summary_template_payload_json: `{s['production_ai_gpu_return_summary_template_payload_json']}`",
        f"- production_ai_gpu_return_summary_template_required_fields: `{','.join(s['production_ai_gpu_return_summary_template_required_fields'])}`",
        f"- production_ai_gpu_return_summary_template_completion_rule: `{s['production_ai_gpu_return_summary_template_completion_rule']}`",
        f"- production_ai_gpu_return_summary_template_backend_provenance_contract_ready: `{s['production_ai_gpu_return_summary_template_backend_provenance_contract_ready']}`",
        f"- production_ai_gpu_return_summary_template_required_backend_provenance_fields: `{','.join(s['production_ai_gpu_return_summary_template_required_backend_provenance_fields'])}`",
        f"- production_ai_gpu_return_operator_acceptance_stage_check_matrix_count: `{s['production_ai_gpu_return_operator_acceptance_stage_check_matrix_count']}`",
        f"- production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix_count: `{s['production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix_count']}`",
        f"- production_ai_gpu_return_actual_summary_return_path: `{s['production_ai_gpu_return_actual_summary_return_path']}`",
        f"- production_ai_gpu_return_actual_manifest_return_path: `{s['production_ai_gpu_return_actual_manifest_return_path']}`",
        f"- production_ai_gpu_summary_manifest_bound: `{s['production_ai_gpu_summary_manifest_bound']}`",
        f"- production_ai_gpu_summary_out_manifest_csv_present: `{s['production_ai_gpu_summary_out_manifest_csv_present']}`",
        f"- production_ai_gpu_summary_out_manifest_csv: `{s['production_ai_gpu_summary_out_manifest_csv']}`",
        f"- production_ai_gpu_summary_out_manifest_csv_bound: `{s['production_ai_gpu_summary_out_manifest_csv_bound']}`",
        f"- production_ai_gpu_summary_out_summary_json_bound: `{s['production_ai_gpu_summary_out_summary_json_bound']}`",
        f"- production_ai_gpu_summary_out_summary_json: `{s['production_ai_gpu_summary_out_summary_json']}`",
        f"- production_ai_gpu_summary_manifest_csv: `{s['production_ai_gpu_summary_manifest_csv']}`",
        f"- production_ai_gpu_worker_rocm_manifest_ready: `{s['production_ai_gpu_worker_rocm_manifest_ready']}`",
        f"- production_ai_gpu_worker_rocm_manifest_artifact: `{s['production_ai_gpu_worker_rocm_manifest_artifact']}`",
        f"- production_ai_gpu_worker_rocm_manifest_completion_rule: `{s['production_ai_gpu_worker_rocm_manifest_completion_rule']}`",
        f"- production_ai_gpu_worker_rocm_visible_device_count: `{s['production_ai_gpu_worker_rocm_visible_device_count']}`",
        f"- production_ai_gpu_worker_rocm_device_names: `{','.join(s['production_ai_gpu_worker_rocm_device_names'])}`",
        f"- production_ai_promotion_workbench_status: `{s['production_ai_promotion_workbench_status']}`",
        f"- production_ai_promotion_workbench_ready: `{s['production_ai_promotion_workbench_ready']}`",
        f"- production_ai_promotion_ready: `{s['production_ai_promotion_ready']}`",
        f"- production_ai_promotion_first_blocked_stage_id: `{s['production_ai_promotion_first_blocked_stage_id']}`",
        f"- production_ai_promotion_blocked_stage_count: `{s['production_ai_promotion_blocked_stage_count']}`",
        f"- production_ai_promotion_blocked_stage_ids: `{';'.join(s['production_ai_promotion_blocked_stage_ids'])}`",
        f"- production_ai_force_gpu_worker_handoff_ready: `{s['production_ai_force_gpu_worker_handoff_ready']}`",
        f"- production_ai_force_gpu_worker_operator_action_required: `{s['production_ai_force_gpu_worker_operator_action_required']}`",
        f"- production_ai_force_gpu_operator_transfer_manifest_ready: `{s['production_ai_force_gpu_operator_transfer_manifest_ready']}`",
        f"- production_ai_force_gpu_operator_transfer_outbound_artifact_count: `{s['production_ai_force_gpu_operator_transfer_outbound_artifact_count']}`",
        f"- production_ai_force_gpu_operator_transfer_inbound_artifact_count: `{s['production_ai_force_gpu_operator_transfer_inbound_artifact_count']}`",
        f"- production_ai_force_gpu_operator_transfer_first_return_artifact: `{s['production_ai_force_gpu_operator_transfer_first_return_artifact']}`",
        f"- production_ai_force_gpu_operator_transfer_acceptance_artifact: `{s['production_ai_force_gpu_operator_transfer_acceptance_artifact']}`",
        f"- production_ai_force_gpu_post_return_unlock_output_fields: `{';'.join(s['production_ai_force_gpu_post_return_unlock_output_fields'])}`",
        f"- production_ai_force_gpu_post_return_min_expected_label_rows: `{s['production_ai_force_gpu_post_return_min_expected_label_rows']}`",
        f"- production_ai_force_gpu_post_return_promotion_ladder_stage_count: `{s['production_ai_force_gpu_post_return_promotion_ladder_stage_count']}`",
        f"- production_ai_force_gpu_post_return_promotion_ladder_currently_satisfied: `{s['production_ai_force_gpu_post_return_promotion_ladder_currently_satisfied']}`",
        f"- production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_id: `{s['production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_id']}`",
        f"- production_ai_force_gpu_post_return_promotion_ladder_stage_ids: `{';'.join(s['production_ai_force_gpu_post_return_promotion_ladder_stage_ids'])}`",
        f"- production_ai_force_gpu_post_run_validation_command_count: `{len(s['production_ai_force_gpu_post_run_validation_commands'])}`",
        f"- production_ai_force_gpu_receipt_manifest_identity_row_count: `{s['production_ai_force_gpu_receipt_manifest_identity_row_count']}`",
        f"- production_ai_force_gpu_receipt_matched_queue_id_count: `{s['production_ai_force_gpu_receipt_matched_queue_id_count']}`",
        f"- production_ai_force_gpu_receipt_matched_expected_npz_count: `{s['production_ai_force_gpu_receipt_matched_expected_npz_count']}`",
        f"- production_ai_force_gpu_receipt_matched_queue_fingerprint_count: `{s['production_ai_force_gpu_receipt_matched_queue_fingerprint_count']}`",
        f"- production_ai_delta_force_closure_acceptance_packet_ready: `{s['production_ai_delta_force_closure_acceptance_packet_ready']}`",
        f"- production_ai_delta_force_closure_ready: `{s['production_ai_delta_force_closure_ready']}`",
        f"- production_ai_delta_force_closure_next_stage_id: `{s['production_ai_delta_force_closure_next_stage_id']}`",
        f"- production_ai_delta_force_closure_failed_stage_count: `{s['production_ai_delta_force_closure_failed_stage_count']}`",
        f"- product_scope_closure_acceptance_packet_ready: `{s['product_scope_closure_acceptance_packet_ready']}`",
        f"- product_scope_closure_acceptance_ready: `{s['product_scope_closure_acceptance_ready']}`",
        f"- product_scope_closure_acceptance_next_stage_id: `{s['product_scope_closure_acceptance_next_stage_id']}`",
        f"- product_scope_closure_acceptance_blocked_stage_count: `{s['product_scope_closure_acceptance_blocked_stage_count']}`",
        f"- product_ai_scope_backlog_detail: `{s['product_ai_scope_backlog_detail']}`",
        f"- product_scope_first_scientific_blocker: `{s['product_scope_first_scientific_blocker']}`",
        f"- product_scope_manual_review_subcheck_count: `{s['product_scope_manual_review_subcheck_count']}`",
        f"- product_scope_transporter_manual_review_subcheck_count: `{s['product_scope_transporter_manual_review_subcheck_count']}`",
        f"- product_scope_transporter_identity_scaffold_confirmation_required_count: `{s['product_scope_transporter_identity_scaffold_confirmation_required_count']}`",
        f"- product_scope_transporter_direct_binding_or_kcal_confirmation_required_count: `{s['product_scope_transporter_direct_binding_or_kcal_confirmation_required_count']}`",
        f"- product_scope_transporter_negative_quantitative_confirmation_required_count: `{s['product_scope_transporter_negative_quantitative_confirmation_required_count']}`",
        f"- product_scope_transporter_direct_binding_missing_count: `{s['product_scope_transporter_direct_binding_missing_count']}`",
        f"- product_scope_transporter_negative_quantitative_missing_count: `{s['product_scope_transporter_negative_quantitative_missing_count']}`",
        f"- product_scope_pxr_reconciled_blocked_row_count: `{s['product_scope_pxr_reconciled_blocked_row_count']}`",
        f"- product_scope_general_claim_blocker_count: `{s['product_scope_general_claim_blocker_count']}`",
        f"- product_scope_authoritative_apply_allowed: `{s['product_scope_authoritative_apply_allowed']}`",
        f"- product_scope_first_blocked_domain: `{s['product_scope_first_blocked_domain']}`",
        f"- product_scope_first_blocked_domain_artifact: `{s['product_scope_first_blocked_domain_artifact']}`",
        f"- product_scope_first_blocked_domain_next_action: `{s['product_scope_first_blocked_domain_next_action']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_packet_ready: `{s['product_scope_transporter_p0_evidence_acquisition_packet_ready']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_first_target_id: `{s['product_scope_transporter_p0_evidence_acquisition_first_target_id']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_first_packet_step: `{s['product_scope_transporter_p0_evidence_acquisition_first_packet_step']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_first_request_mode: `{s['product_scope_transporter_p0_evidence_acquisition_first_request_mode']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count: `{s['product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count: `{s['product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id: `{s['product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path: `{s['product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready: `{s['product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality: `{s['product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed: `{s['product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_decision: `{s['product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_decision']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count: `{s['product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result: `{s['product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result']}`",
        f"- product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail: `{s['product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail']}`",
        f"- product_scope_allowed_families: `{';'.join(s['product_scope_allowed_families'])}`",
        f"- product_scope_blocked_claim_scopes: `{';'.join(s['product_scope_blocked_claim_scopes'])}`",
        f"- product_scope_general_platform_claim_allowed: `{s['product_scope_general_platform_claim_allowed']}`",
        f"- product_scope_evidence_priority_ready: `{s['product_scope_evidence_priority_ready']}`",
        f"- product_scope_evidence_priority_queue_item_count: `{s['product_scope_evidence_priority_queue_item_count']}`",
        f"- product_scope_evidence_priority_open_item_count: `{s['product_scope_evidence_priority_open_item_count']}`",
        f"- product_scope_evidence_priority_local_crosscheck_candidate_count: `{s['product_scope_evidence_priority_local_crosscheck_candidate_count']}`",
        f"- product_scope_evidence_priority_external_primary_exact_required_count: `{s['product_scope_evidence_priority_external_primary_exact_required_count']}`",
        f"- product_scope_evidence_priority_all_operator_packet_bindings_ready: `{s['product_scope_evidence_priority_all_operator_packet_bindings_ready']}`",
        f"- product_scope_evidence_priority_operator_packet_binding_missing_count: `{s['product_scope_evidence_priority_operator_packet_binding_missing_count']}`",
        f"- product_scope_evidence_priority_top_item_id: `{s['product_scope_evidence_priority_top_item_id']}`",
        f"- product_scope_evidence_priority_top_domain: `{s['product_scope_evidence_priority_top_domain']}`",
        f"- product_scope_evidence_priority_top_bucket: `{s['product_scope_evidence_priority_top_bucket']}`",
        f"- product_scope_evidence_priority_top_required_evidence_type: `{s['product_scope_evidence_priority_top_required_evidence_type']}`",
        f"- product_scope_evidence_priority_top_review_template_artifact: `{s['product_scope_evidence_priority_top_review_template_artifact']}`",
        f"- product_scope_evidence_priority_top_apply_gate_artifact: `{s['product_scope_evidence_priority_top_apply_gate_artifact']}`",
        f"- product_scope_evidence_priority_top_next_step: `{s['product_scope_evidence_priority_top_next_step']}`",
        f"- product_scope_evidence_intake_ready: `{s['product_scope_evidence_intake_ready']}`",
        f"- product_scope_evidence_intake_row_count: `{s['product_scope_evidence_intake_row_count']}`",
        f"- product_scope_evidence_intake_all_operator_packet_bindings_ready: `{s['product_scope_evidence_intake_all_operator_packet_bindings_ready']}`",
        f"- product_scope_evidence_intake_operator_packet_binding_missing_count: `{s['product_scope_evidence_intake_operator_packet_binding_missing_count']}`",
        f"- product_scope_breadth_contract_status: `{s['product_scope_breadth_contract_status']}`",
        f"- product_scope_evidence_queue_next_operator_completion_slot_id: `{s['product_scope_evidence_queue_next_operator_completion_slot_id']}`",
        f"- product_scope_evidence_queue_next_operator_completion_required_exact_evidence_fields: `{s['product_scope_evidence_queue_next_operator_completion_required_exact_evidence_fields']}`",
        f"- product_scope_evidence_queue_next_operator_completion_operator_review_artifact: `{s['product_scope_evidence_queue_next_operator_completion_operator_review_artifact']}`",
        f"- product_scope_evidence_queue_next_operator_completion_acceptance_gate_commands: `{s['product_scope_evidence_queue_next_operator_completion_acceptance_gate_commands']}`",
        f"- product_scope_evidence_queue_next_operator_completion_aqp1_review_sidecar_ready: `{s['product_scope_evidence_queue_next_operator_completion_aqp1_review_sidecar_ready']}`",
        f"- product_scope_evidence_queue_next_operator_completion_aqp1_review_candidate_name: `{s['product_scope_evidence_queue_next_operator_completion_aqp1_review_candidate_name']}`",
        f"- product_scope_evidence_queue_next_operator_completion_aqp1_review_source_anchor: `{s['product_scope_evidence_queue_next_operator_completion_aqp1_review_source_anchor']}`",
        f"- product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol: `{s['product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol']}`",
        f"- product_scope_evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed: `{s['product_scope_evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed']}`",
        f"- product_scope_operator_transfer_manifest_ready: `{s['product_scope_operator_transfer_manifest_ready']}`",
        f"- product_scope_operator_transfer_outbound_artifact_count: `{s['product_scope_operator_transfer_outbound_artifact_count']}`",
        f"- product_scope_operator_transfer_inbound_artifact_count: `{s['product_scope_operator_transfer_inbound_artifact_count']}`",
        f"- product_scope_operator_transfer_first_return_artifact: `{s['product_scope_operator_transfer_first_return_artifact']}`",
        f"- product_scope_operator_transfer_acceptance_artifact: `{s['product_scope_operator_transfer_acceptance_artifact']}`",
        f"- product_scope_acceptance_matrix_ready: `{s['product_scope_acceptance_matrix_ready']}`",
        f"- product_scope_claim_expansion_contract_ready: `{s['product_scope_claim_expansion_contract_ready']}`",
        f"- product_scope_claim_expansion_currently_satisfied: `{s['product_scope_claim_expansion_currently_satisfied']}`",
        f"- product_scope_claim_expansion_current_next_stage_id: `{s['product_scope_claim_expansion_current_next_stage_id']}`",
        f"- product_scope_acceptance_ready_stage_count: `{s['product_scope_acceptance_ready_stage_count']}`",
        f"- product_scope_acceptance_blocked_stage_count: `{s['product_scope_acceptance_blocked_stage_count']}`",
        f"- product_scope_acceptance_release_blocker_stage_ids: `{';'.join(s['product_scope_acceptance_release_blocker_stage_ids'])}`",
        f"- product_scope_acceptance_next_stage_id: `{s['product_scope_acceptance_next_stage_id']}`",
        f"- product_scope_acceptance_stage_evidence_matrix_count: `{s['product_scope_acceptance_stage_evidence_matrix_count']}`",
        f"- product_scope_acceptance_current_blocked_stage_evidence_matrix_count: `{s['product_scope_acceptance_current_blocked_stage_evidence_matrix_count']}`",
        f"- product_scope_acceptance_next_stage_artifact: `{s['product_scope_acceptance_next_stage_artifact']}`",
        f"- product_scope_acceptance_next_stage_validation_command: `{s['product_scope_acceptance_next_stage_validation_command']}`",
        f"- product_scope_acceptance_next_stage_unlock_claim_scopes: `{';'.join(s['product_scope_acceptance_next_stage_unlock_claim_scopes'])}`",
        f"- product_scope_local_crosscheck_intake_ready_count: `{s['product_scope_local_crosscheck_intake_ready_count']}`",
        f"- product_scope_external_exact_evidence_required_count: `{s['product_scope_external_exact_evidence_required_count']}`",
        f"- product_scope_transporter_operator_review_evidence_matrix_ready: `{s['product_scope_transporter_operator_review_evidence_matrix_ready']}`",
        f"- product_scope_transporter_claim_safe_local_evidence_ready_count: `{s['product_scope_transporter_claim_safe_local_evidence_ready_count']}`",
        f"- product_scope_transporter_claim_safe_local_evidence_blocked_count: `{s['product_scope_transporter_claim_safe_local_evidence_blocked_count']}`",
        f"- product_scope_transporter_direct_binding_claim_blocked_count: `{s['product_scope_transporter_direct_binding_claim_blocked_count']}`",
        f"- product_scope_transporter_negative_value_claim_blocked_count: `{s['product_scope_transporter_negative_value_claim_blocked_count']}`",
        f"- product_scope_transporter_candidate_assignment_required_count: `{s['product_scope_transporter_candidate_assignment_required_count']}`",
        f"- product_scope_transporter_functional_quantitative_only_direct_gap_open_count: `{s['product_scope_transporter_functional_quantitative_only_direct_gap_open_count']}`",
        f"- product_scope_transporter_candidate_ready_for_manual_review_count: `{s['product_scope_transporter_candidate_ready_for_manual_review_count']}`",
        f"- product_scope_transporter_candidate_ready_for_apply_count: `{s['product_scope_transporter_candidate_ready_for_apply_count']}`",
        f"- product_scope_transporter_manual_review_direct_binding_evidence_required_count: `{s['product_scope_transporter_manual_review_direct_binding_evidence_required_count']}`",
        f"- product_scope_transporter_manual_review_negative_quantitative_value_required_count: `{s['product_scope_transporter_manual_review_negative_quantitative_value_required_count']}`",
        f"- product_scope_transporter_manual_review_decision_placeholder_count: `{s['product_scope_transporter_manual_review_decision_placeholder_count']}`",
        f"- product_scope_transporter_manual_review_p0_slot_overlay_row_count: `{s['product_scope_transporter_manual_review_p0_slot_overlay_row_count']}`",
        f"- product_scope_transporter_manual_review_p0_slot_overlay_first_item_id: `{s['product_scope_transporter_manual_review_p0_slot_overlay_first_item_id'] or '-'}`",
        f"- product_scope_transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id: `{s['product_scope_transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id'] or '-'}`",
        f"- product_scope_transporter_manual_review_first_review_item_id: `{s['product_scope_transporter_manual_review_first_review_item_id'] or '-'}`",
        f"- product_scope_transporter_manual_review_first_review_candidate_ligand_id: `{s['product_scope_transporter_manual_review_first_review_candidate_ligand_id'] or '-'}`",
        f"- product_scope_transporter_manual_review_first_review_p0_slot_overlay_required_missing_fields: `{s['product_scope_transporter_manual_review_first_review_p0_slot_overlay_required_missing_fields'] or '-'}`",
        f"- product_scope_transporter_manual_review_first_review_p0_slot_overlay_scope_promotion_allowed: `{s['product_scope_transporter_manual_review_first_review_p0_slot_overlay_scope_promotion_allowed']}`",
        f"- product_scope_pxr_exact_review_intake_ready: `{s['product_scope_pxr_exact_review_intake_ready']}`",
        f"- product_scope_pxr_exact_review_template_row_count: `{s['product_scope_pxr_exact_review_template_row_count']}`",
        f"- product_scope_pxr_exact_review_conflict_resolution_required_count: `{s['product_scope_pxr_exact_review_conflict_resolution_required_count']}`",
        f"- product_scope_pxr_exact_review_kcal_placeholder_count: `{s['product_scope_pxr_exact_review_kcal_placeholder_count']}`",
        f"- product_scope_pxr_exact_review_source_placeholder_count: `{s['product_scope_pxr_exact_review_source_placeholder_count']}`",
        f"- product_scope_pxr_exact_review_target_match_placeholder_count: `{s['product_scope_pxr_exact_review_target_match_placeholder_count']}`",
        f"- product_scope_pxr_exact_review_next_review_return_bundle_required_artifact_count: `{s['product_scope_pxr_exact_review_next_review_return_bundle_required_artifact_count']}`",
        f"- product_scope_pxr_exact_review_next_review_return_bundle_blocker_count: `{s['product_scope_pxr_exact_review_next_review_return_bundle_blocker_count']}`",
        f"- product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_id: `{s['product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_id']}`",
        f"- commercial_readiness_handoff_bundle_ready: `{s['commercial_readiness_handoff_bundle_ready']}`",
        f"- commercial_readiness_handoff_bundle_artifact_count: `{s['commercial_readiness_handoff_bundle_artifact_count']}`",
        f"- commercial_readiness_handoff_bundle_blocked_artifact_count: `{s['commercial_readiness_handoff_bundle_blocked_artifact_count']}`",
        f"- commercial_readiness_handoff_bundle_artifact_reference_contract_ready: `{s['commercial_readiness_handoff_bundle_artifact_reference_contract_ready']}`",
        f"- commercial_readiness_handoff_bundle_artifact_reference_count: `{s['commercial_readiness_handoff_bundle_artifact_reference_count']}`",
        f"- commercial_readiness_handoff_bundle_local_missing_artifact_reference_count: `{s['commercial_readiness_handoff_bundle_local_missing_artifact_reference_count']}`",
        f"- commercial_readiness_handoff_bundle_operator_return_pending_artifact_reference_count: `{s['commercial_readiness_handoff_bundle_operator_return_pending_artifact_reference_count']}`",
        f"- commercial_readiness_handoff_bundle_first_action_id: `{s['commercial_readiness_handoff_bundle_first_action_id']}`",
        f"- commercial_readiness_handoff_bundle_first_operator_input_artifact: `{s['commercial_readiness_handoff_bundle_first_operator_input_artifact']}`",
        f"- approval_tokens_required: `{';'.join(s['approval_tokens_required'])}`",
        f"- next_command: `{s['next_command']}`",
        f"- next_command_candidate_count: `{s['next_command_candidate_count']}`",
        "",
        "## Next Command Candidates",
        "",
    ]
    if s["next_command_candidates"]:
        lines.extend(f"- `{command}`" for command in s["next_command_candidates"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Commercial Readiness Next Actions",
            "",
            "| action | status | artifact | operator inputs | next action | execution | validation |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in s.get("commercial_readiness_next_action_matrix") or []:
        if not isinstance(row, dict):
            continue
        required_inputs = ";".join(str(item) for item in (row.get("required_operator_inputs") or []))
        lines.append(
            f"| `{_text(row.get('action_id'))}` | `{_text(row.get('status'))}` | "
            f"`{_text(row.get('artifact'))}` | `{required_inputs}` | "
            f"`{_text(row.get('next_action'))}` | `{_text(row.get('execution_command'))}` | "
            f"`{_text(row.get('validation_command'))}` |"
        )
    lines.extend(
        [
        "",
        "## Requirements",
        "",
        "| id | status | observed | required | blocker |",
        "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['requirement_id']}` | `{row['status']}` | `{row['observed']}` | "
            f"`{row['required']}` | `{row['blocker']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an objective-level product goal completion audit.")
    parser.add_argument("--architecture-json", default=DEFAULT_ARCHITECTURE_JSON)
    parser.add_argument("--release-dossier-json", default=DEFAULT_RELEASE_DOSSIER_JSON)
    parser.add_argument("--public-benchmark-json", default=DEFAULT_PUBLIC_BENCHMARK_JSON)
    parser.add_argument("--commercial-independence-json", default=DEFAULT_COMMERCIAL_INDEPENDENCE_JSON)
    parser.add_argument("--license-work-order-json", default=DEFAULT_LICENSE_WORK_ORDER_JSON)
    parser.add_argument("--cameo-architecture-json", default=DEFAULT_CAMEO_ARCHITECTURE_JSON)
    parser.add_argument("--release-gate-json", default=DEFAULT_RELEASE_GATE_JSON)
    parser.add_argument("--bottleneck-json", default=DEFAULT_BOTTLENECK_JSON)
    parser.add_argument("--burndown-json", default=DEFAULT_BURNDOWN_JSON)
    parser.add_argument("--product-ai-architecture-gap-json", default=DEFAULT_PRODUCT_AI_ARCHITECTURE_GAP_JSON)
    parser.add_argument("--product-ai-execution-backlog-json", default=DEFAULT_PRODUCT_AI_EXECUTION_BACKLOG_JSON)
    parser.add_argument("--residual-model-registry-json", default=DEFAULT_RESIDUAL_MODEL_REGISTRY_JSON)
    parser.add_argument("--production-ai-checkpoint-readiness-json", default=DEFAULT_PRODUCTION_AI_CHECKPOINT_READINESS_JSON)
    parser.add_argument("--production-ai-gpu-return-intake-json", default=DEFAULT_PRODUCTION_AI_GPU_RETURN_INTAKE_JSON)
    parser.add_argument("--production-ai-promotion-workbench-json", default=DEFAULT_PRODUCTION_AI_PROMOTION_WORKBENCH_JSON)
    parser.add_argument("--product-scope-breadth-contract-json", default=DEFAULT_PRODUCT_SCOPE_BREADTH_CONTRACT_JSON)
    parser.add_argument("--scope-evidence-priority-json", default=DEFAULT_SCOPE_EVIDENCE_PRIORITY_JSON)
    parser.add_argument("--scope-evidence-intake-readiness-json", default=DEFAULT_SCOPE_EVIDENCE_INTAKE_READINESS_JSON)
    parser.add_argument("--scope-breadth-evidence-receipt-json", default=DEFAULT_SCOPE_BREADTH_EVIDENCE_RECEIPT_JSON)
    parser.add_argument("--pxr-exact-review-intake-json", default=DEFAULT_PXR_EXACT_REVIEW_INTAKE_JSON)
    parser.add_argument("--commercial-readiness-handoff-bundle-json", default=DEFAULT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_JSON)
    parser.add_argument("--delta-force-closure-acceptance-json", default=DEFAULT_DELTA_FORCE_CLOSURE_ACCEPTANCE_JSON)
    parser.add_argument("--scope-closure-acceptance-json", default=DEFAULT_SCOPE_CLOSURE_ACCEPTANCE_JSON)
    parser.add_argument(
        "--product-scope-breadth-closure-checklist-json",
        default=DEFAULT_SCOPE_CLOSURE_CHECKLIST_JSON,
    )
    parser.add_argument("--report-ux-json", default=DEFAULT_REPORT_UX_JSON)
    parser.add_argument("--trajectory-sla-json", default=DEFAULT_TRAJECTORY_SLA_JSON)
    parser.add_argument("--security-deployment-json", default=DEFAULT_SECURITY_DEPLOYMENT_JSON)
    parser.add_argument("--decision-graph-json", default=DEFAULT_DECISION_GRAPH_JSON)
    parser.add_argument("--service-boundary-json", default=DEFAULT_SERVICE_BOUNDARY_JSON)
    parser.add_argument("--product-api-contract-json", default=DEFAULT_PRODUCT_API_CONTRACT_JSON)
    parser.add_argument("--job-orchestration-json", default=DEFAULT_JOB_ORCHESTRATION_JSON)
    parser.add_argument(
        "--engine-refinement-tier-readiness-json",
        default=DEFAULT_ENGINE_REFINEMENT_TIER_READINESS_JSON,
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_goal_completion_audit(
        architecture_packet=_read_json_if_present(args.architecture_json),
        release_dossier_packet=_read_json_if_present(args.release_dossier_json),
        public_benchmark_packet=_read_json_if_present(args.public_benchmark_json),
        commercial_independence_packet=_read_json_if_present(args.commercial_independence_json),
        license_work_order_packet=_read_json_if_present(args.license_work_order_json),
        cameo_architecture_packet=_read_json_if_present(args.cameo_architecture_json),
        release_gate_packet=_read_json_if_present(args.release_gate_json),
        bottleneck_packet=_read_json_if_present(args.bottleneck_json),
        burndown_packet=_read_json_if_present(args.burndown_json),
        product_ai_architecture_gap_packet=_read_json_if_present(args.product_ai_architecture_gap_json),
        product_ai_execution_backlog_packet=_read_json_if_present(args.product_ai_execution_backlog_json),
        residual_model_registry_packet=_read_json_if_present(args.residual_model_registry_json),
        production_ai_checkpoint_readiness_packet=_read_json_if_present(args.production_ai_checkpoint_readiness_json),
        production_ai_gpu_return_intake_packet=_read_json_if_present(args.production_ai_gpu_return_intake_json),
        production_ai_promotion_workbench_packet=_read_json_if_present(args.production_ai_promotion_workbench_json),
        product_scope_breadth_contract_packet=_read_json_if_present(args.product_scope_breadth_contract_json),
        scope_evidence_priority_packet=_read_json_if_present(args.scope_evidence_priority_json),
        scope_evidence_intake_readiness_packet=_read_json_if_present(args.scope_evidence_intake_readiness_json),
        scope_breadth_evidence_receipt_packet=_read_json_if_present(args.scope_breadth_evidence_receipt_json),
        pxr_exact_review_intake_packet=_read_json_if_present(args.pxr_exact_review_intake_json),
        commercial_readiness_handoff_bundle_packet=_read_json_if_present(args.commercial_readiness_handoff_bundle_json),
        delta_force_closure_acceptance_packet=_read_json_if_present(args.delta_force_closure_acceptance_json),
        scope_closure_acceptance_packet=_read_json_if_present(args.scope_closure_acceptance_json),
        product_scope_breadth_closure_checklist_packet=_read_json_if_present(
            args.product_scope_breadth_closure_checklist_json
        ),
        report_ux_packet=_read_json_if_present(args.report_ux_json),
        trajectory_sla_packet=_read_json_if_present(args.trajectory_sla_json),
        security_deployment_packet=_read_json_if_present(args.security_deployment_json),
        decision_graph_packet=_read_json_if_present(args.decision_graph_json),
        service_boundary_packet=_read_json_if_present(args.service_boundary_json),
        product_api_contract_packet=_read_json_if_present(args.product_api_contract_json),
        job_orchestration_packet=_read_json_if_present(args.job_orchestration_json),
        engine_refinement_tier_readiness_packet=_read_json_if_present(args.engine_refinement_tier_readiness_json),
        architecture_path=args.architecture_json,
        release_dossier_path=args.release_dossier_json,
        public_benchmark_path=args.public_benchmark_json,
        commercial_independence_path=args.commercial_independence_json,
        license_work_order_path=args.license_work_order_json,
        cameo_architecture_path=args.cameo_architecture_json,
        release_gate_path=args.release_gate_json,
        bottleneck_path=args.bottleneck_json,
        burndown_path=args.burndown_json,
        product_ai_architecture_gap_path=args.product_ai_architecture_gap_json,
        product_ai_execution_backlog_path=args.product_ai_execution_backlog_json,
        residual_model_registry_path=args.residual_model_registry_json,
        production_ai_checkpoint_readiness_path=args.production_ai_checkpoint_readiness_json,
        production_ai_gpu_return_intake_path=args.production_ai_gpu_return_intake_json,
        production_ai_promotion_workbench_path=args.production_ai_promotion_workbench_json,
        product_scope_breadth_contract_path=args.product_scope_breadth_contract_json,
        scope_evidence_priority_path=args.scope_evidence_priority_json,
        scope_evidence_intake_readiness_path=args.scope_evidence_intake_readiness_json,
        scope_breadth_evidence_receipt_path=args.scope_breadth_evidence_receipt_json,
        pxr_exact_review_intake_path=args.pxr_exact_review_intake_json,
        commercial_readiness_handoff_bundle_path=args.commercial_readiness_handoff_bundle_json,
        delta_force_closure_acceptance_path=args.delta_force_closure_acceptance_json,
        scope_closure_acceptance_path=args.scope_closure_acceptance_json,
        product_scope_breadth_closure_checklist_path=args.product_scope_breadth_closure_checklist_json,
        report_ux_path=args.report_ux_json,
        trajectory_sla_path=args.trajectory_sla_json,
        security_deployment_path=args.security_deployment_json,
        decision_graph_path=args.decision_graph_json,
        service_boundary_path=args.service_boundary_json,
        product_api_contract_path=args.product_api_contract_json,
        job_orchestration_path=args.job_orchestration_json,
        engine_refinement_tier_readiness_path=args.engine_refinement_tier_readiness_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
