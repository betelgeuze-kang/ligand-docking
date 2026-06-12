from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from betelgeuze_product.payload_privacy import sanitize_request_for_ledger

CLAIM_BOUNDARY = (
    "Product job orchestration ledger only; it lists and updates local fail-closed docking job records. "
    "It does not run docking, retry compute, cancel an external worker, emit scientific results, upload data, "
    "or mutate external state outside the local job ledger."
)
MAX_RETRY_ATTEMPTS = 3
JOB_RETRY_POLICY = "operator_requested_retry_child_preserves_request_sha256_max_3"
JOB_LEASE_TIMEOUT_SECONDS = 1800


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_utc_iso(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _job_path(jobs_dir: Path, job_id: str) -> Path:
    return jobs_dir / f"{job_id}.json"


def _root_job_id(record: dict[str, Any]) -> str:
    return _text(record.get("root_job_id") or record.get("retry_of_job_id") or record.get("job_id"))


def _event_actors(record: dict[str, Any]) -> list[str]:
    actors = {
        _text(event.get("actor"))
        for event in record.get("event_history") or []
        if isinstance(event, dict) and _text(event.get("actor"))
    }
    return sorted(actors)


def _workflow_controls(record: dict[str, Any]) -> dict[str, Any]:
    job_id = _text(record.get("job_id"))
    cancellable = record.get("cancellable") is True
    retryable = record.get("retryable") is True
    retry_limit_reached = record.get("retry_limit_reached") is True
    allowed_actions = ["view_status", "view_history"]
    if cancellable:
        allowed_actions.append("cancel")
    if retryable and not retry_limit_reached:
        allowed_actions.append("retry")
    disabled_actions = [
        action for action in ("cancel", "retry") if action not in allowed_actions
    ]
    return {
        "workflow_controls_ready": True,
        "workflow_control_links": {
            "self": f"/product/docking/jobs/{job_id}",
            "history": f"/product/docking/jobs/{job_id}/history",
            "cancel": f"/product/docking/jobs/{job_id}/cancel",
            "retry": f"/product/docking/jobs/{job_id}/retry",
        },
        "workflow_allowed_actions": allowed_actions,
        "workflow_disabled_actions": disabled_actions,
        "workflow_next_customer_actions": allowed_actions,
        "status_transition_contract": {
            "current_status": _text(record.get("status")),
            "queue_status": _text(record.get("queue_status")),
            "cancellable": cancellable,
            "retryable": retryable,
            "retry_limit_reached": retry_limit_reached,
            "terminal_state": False,
            "fail_closed": True,
            "execution_enabled": False,
            "docking_results_emitted": False,
        },
    }


def _status_snapshot(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": _text(record.get("job_id")),
        "root_job_id": _root_job_id(record),
        "request_sha256": _text(record.get("request_sha256")),
        "customer_id": _text(record.get("customer_id")),
        "user_id": _text(record.get("user_id")),
        "status": _text(record.get("status")),
        "progress_percent": float(record.get("progress_percent") or 0.0),
        "progress_state": _text(record.get("progress_state")),
        "current_step": _text(record.get("current_step")),
        "worker_state": _text(record.get("worker_state")),
        "worker_lease_id": _text(record.get("worker_lease_id")),
        "worker_id": _text(record.get("worker_id")),
        "heartbeat_at_utc": _text(record.get("heartbeat_at_utc")),
        "stale_worker_lease_detected": record.get("stale_worker_lease_detected") is True,
        "stale_worker_lease_timeout_seconds": int(record.get("stale_worker_lease_timeout_seconds") or 0),
        "stale_worker_lease_previous_heartbeat_at_utc": _text(
            record.get("stale_worker_lease_previous_heartbeat_at_utc")
        ),
        "queue_status": _text(record.get("queue_status")),
        "progress_percent_range_valid": record.get("progress_percent_range_valid") is True,
        "status_progress_contract_ready": record.get("status_progress_contract_ready") is True,
        "workflow_controls_ready": record.get("workflow_controls_ready") is True,
        "workflow_allowed_actions": list(record.get("workflow_allowed_actions") or []),
        "workflow_disabled_actions": list(record.get("workflow_disabled_actions") or []),
        "workflow_control_links": record.get("workflow_control_links")
        if isinstance(record.get("workflow_control_links"), dict)
        else {},
        "last_event_type": _text(record.get("last_event_type")),
        "production_ai_abstention_reason": _text(record.get("production_ai_abstention_reason")),
        "production_ai_what_would_change_decision": _text(record.get("production_ai_what_would_change_decision")),
        "scope_claim_guard_ready": record.get("scope_claim_guard_ready") is True,
        "scope_claim_allowed_for_request": record.get("scope_claim_allowed_for_request") is True,
        "scope_claim_status": _text(record.get("scope_claim_status")),
        "blocked_claim_scopes": list(record.get("blocked_claim_scopes") or []),
        "claim_blocked_domains": list(record.get("claim_blocked_domains") or []),
        "general_platform_claim_allowed": record.get("general_platform_claim_allowed") is True,
        "ai_decision_graph_trace_ready": record.get("ai_decision_graph_trace_ready") is True,
        "ai_decision_graph_ordered_path": list(record.get("ai_decision_graph_ordered_path") or []),
        "ai_decision_graph_node_count": int(record.get("ai_decision_graph_node_count") or 0),
        "ai_decision_graph_edge_count": int(record.get("ai_decision_graph_edge_count") or 0),
        "ai_decision_graph_abstention_node_id": _text(
            record.get("ai_decision_graph_abstention_node_id")
        ),
        "ai_decision_graph_current_node_id": _text(record.get("ai_decision_graph_current_node_id")),
        "customer_report_explanation_ready": record.get("customer_report_explanation_ready") is True,
        "customer_report_card_ready": record.get("customer_report_card_ready") is True,
        "customer_report_delivery_contract_ready": record.get(
            "customer_report_delivery_contract_ready"
        )
        is True,
        "customer_report_evidence_binding_ready": record.get(
            "customer_report_evidence_binding_ready"
        )
        is True,
        "customer_report_selection_rationale_ready": record.get(
            "customer_report_selection_rationale_ready"
        )
        is True,
        "customer_report_uncertainty_posture_ready": record.get(
            "customer_report_uncertainty_posture_ready"
        )
        is True,
        "customer_report_prohibited_claims_ready": record.get(
            "customer_report_prohibited_claims_ready"
        )
        is True,
        "customer_report_selection_rationale": _text(record.get("customer_report_selection_rationale")),
        "customer_report_uncertainty_posture": _text(record.get("customer_report_uncertainty_posture")),
        "customer_report_prohibited_claims": list(record.get("customer_report_prohibited_claims") or []),
        "customer_report_required_block_count": int(
            record.get("customer_report_required_block_count") or 0
        ),
        "customer_report_ready_block_count": int(record.get("customer_report_ready_block_count") or 0),
        "customer_report_blocked_block_count": int(
            record.get("customer_report_blocked_block_count") or 0
        ),
        "customer_report_section_count": int(record.get("customer_report_section_count") or 0),
        "customer_report_primary_abstention_reason": _text(record.get("customer_report_primary_abstention_reason")),
        "customer_report_what_would_change_decision": _text(
            record.get("customer_report_what_would_change_decision")
        ),
        "customer_report_card": record.get("customer_report_card")
        if isinstance(record.get("customer_report_card"), dict)
        else {},
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


def _rerun_manifest(record: dict[str, Any]) -> dict[str, Any]:
    root_job_id = _root_job_id(record)
    return {
        "manifest_type": "docking_job_rerun_manifest",
        "root_job_id": root_job_id,
        "request_sha256": _text(record.get("request_sha256")),
        "idempotency_key": _text(record.get("idempotency_key") or record.get("request_sha256")),
        "source_host": _text(record.get("source_host")),
        "customer_id": _text(record.get("customer_id")),
        "user_id": _text(record.get("user_id")),
        "required_replay_policy": "same_request_sha256_and_operator_retry_event",
        "rerun_command": f"POST /product/docking/jobs/{root_job_id}/retry",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


def _progress_percent(record: dict[str, Any]) -> float:
    try:
        return float(record.get("progress_percent") or 0.0)
    except (TypeError, ValueError):
        return -1.0


def _queue_status(record: dict[str, Any]) -> str:
    status = _text(record.get("status"))
    progress_state = _text(record.get("progress_state"))
    if status == "running_fail_closed":
        return "worker_lease_active_fail_closed"
    if status == "failed_fail_closed":
        return "failed_retryable_fail_closed"
    if status == "accepted_fail_closed":
        return "queued_fail_closed"
    if status == "blocked_contract_validation":
        return "blocked_contract_validation"
    if status == "cancel_requested_fail_closed":
        return "cancel_requested_fail_closed"
    if status == "retry_requested_fail_closed" and progress_state == "retry_attempt_recorded":
        return "retry_attempt_recorded_fail_closed"
    if status == "retry_requested_fail_closed":
        return "retry_requested_fail_closed"
    return "unknown_fail_closed"


def _status_progress_contract_ready(record: dict[str, Any]) -> bool:
    status = _text(record.get("status"))
    progress_state = _text(record.get("progress_state"))
    current_step = _text(record.get("current_step"))
    worker_state = _text(record.get("worker_state"))
    queue_status = _text(record.get("queue_status"))
    progress = _progress_percent(record)
    progress_range_valid = 0.0 <= progress <= 100.0
    if not progress_range_valid:
        return False
    if status == "running_fail_closed":
        return (
            progress_state == "worker_heartbeat_recorded"
            and bool(current_step)
            and worker_state in {"leased_fail_closed", "active_fail_closed", "cancel_acknowledged_fail_closed"}
            and queue_status == "worker_lease_active_fail_closed"
            and bool(_text(record.get("worker_lease_id")))
            and bool(_text(record.get("worker_id")))
            and bool(_text(record.get("heartbeat_at_utc")))
        )
    if status == "failed_fail_closed":
        return (
            progress_state == "worker_failed_retryable"
            and current_step == "worker_failure_recorded"
            and worker_state == "failed_retryable_fail_closed"
            and queue_status == "failed_retryable_fail_closed"
            and record.get("retryable") is True
        )
    if status == "cancel_requested_fail_closed" and worker_state == "cancel_acknowledged_fail_closed":
        return (
            progress_state in {"cancel_requested_fail_closed", "worker_heartbeat_recorded"}
            and current_step in {"operator_cancel_request", "worker_cancel_acknowledged"}
            and queue_status == "cancel_requested_fail_closed"
            and record.get("cancellable") is False
            and record.get("retryable") is True
            and record.get("worker_cancel_acknowledged") is True
        )
    if worker_state != "not_started_fail_closed":
        return False
    if status == "accepted_fail_closed":
        return progress == 0.0 and progress_state == "ledger_intake_recorded" and current_step == "contract_validation" and queue_status == "queued_fail_closed"
    if status == "blocked_contract_validation":
        return progress == 0.0 and progress_state == "ledger_intake_recorded" and current_step == "contract_validation" and queue_status == "blocked_contract_validation"
    if status == "cancel_requested_fail_closed":
        return (
            progress == 0.0
            and progress_state == "cancel_requested_fail_closed"
            and current_step == "operator_cancel_request"
            and queue_status == "cancel_requested_fail_closed"
            and record.get("cancellable") is False
            and record.get("retryable") is True
        )
    if status == "retry_requested_fail_closed":
        if progress_state == "retry_attempt_recorded":
            return (
                progress == 0.0
                and bool(_text(record.get("parent_job_id")))
                and current_step == "contract_validation"
                and queue_status == "retry_attempt_recorded_fail_closed"
            )
        return progress == 0.0 and progress_state == "retry_requested_fail_closed" and current_step == "operator_retry_request" and queue_status == "retry_requested_fail_closed"
    return False


def _refresh_status_metadata(record: dict[str, Any]) -> dict[str, Any]:
    updated = dict(record)
    updated["queue_status"] = _queue_status(updated)
    updated["queue_position"] = int(updated.get("queue_position") or 0)
    updated["max_retry_attempts"] = int(updated.get("max_retry_attempts") or MAX_RETRY_ATTEMPTS)
    updated["retry_policy"] = _text(updated.get("retry_policy")) or JOB_RETRY_POLICY
    updated["progress_percent_range_valid"] = 0.0 <= _progress_percent(updated) <= 100.0
    updated["status_progress_contract_ready"] = _status_progress_contract_ready(updated)
    updated["retry_limit_reached"] = int(updated.get("attempt_index") or 1) >= int(updated.get("max_retry_attempts") or MAX_RETRY_ATTEMPTS)
    updated.update(_workflow_controls(updated))
    updated["job_retention_policy"] = _text(updated.get("job_retention_policy")) or "local_job_ledger_retain_90_days_minimum"
    updated["job_retention_days"] = int(updated.get("job_retention_days") or 90)
    updated["rerun_manifest"] = _rerun_manifest(updated)
    updated["rerun_manifest_ready"] = True
    updated["reproducible_rerun_ready"] = True
    updated["long_running_status_persistence_ready"] = True
    updated["status_snapshot"] = _status_snapshot(updated)
    updated["status_snapshot_persisted"] = True
    return updated


def read_job_record(jobs_dir: Path, job_id: str) -> dict[str, Any]:
    path = _job_path(jobs_dir, job_id)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_job_record(jobs_dir: Path, record: dict[str, Any]) -> Path:
    jobs_dir.mkdir(parents=True, exist_ok=True)
    path = _job_path(jobs_dir, _text(record.get("job_id")))
    safe_record = sanitize_request_for_ledger(record)
    path.write_text(json.dumps(safe_record, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return path


def append_job_event(
    record: dict[str, Any],
    *,
    event_type: str,
    reason: str = "",
    actor: str = "",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    events = list(record.get("event_history") or [])
    event = {
        "event_type": event_type,
        "created_at_utc": utc_now_iso(),
        "reason": reason,
        "actor": actor,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }
    if details:
        event.update(details)
    events.append(event)
    updated = dict(record)
    updated["event_history"] = events
    updated["last_event_type"] = event_type
    updated["updated_at_utc"] = event["created_at_utc"]
    updated["execution_enabled"] = False
    updated["docking_results_emitted"] = False
    updated["external_state_mutated"] = False
    updated["claim_boundary"] = updated.get("claim_boundary") or CLAIM_BOUNDARY
    return _refresh_status_metadata(updated)


def _retry_attempt_job_id(jobs_dir: Path, root_job_id: str, retry_index: int) -> str:
    candidate = f"{root_job_id}-retry-{retry_index}"
    while _job_path(jobs_dir, candidate).exists():
        retry_index += 1
        candidate = f"{root_job_id}-retry-{retry_index}"
    return candidate


def list_job_records(
    jobs_dir: Path,
    *,
    limit: int = 50,
    source_host: str = "",
    root_job_id: str = "",
    customer_id: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    if jobs_dir.exists():
        for path in sorted(jobs_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            record = read_job_record(jobs_dir, path.stem)
            if not record:
                continue
            if source_host and _text(record.get("source_host")) != source_host:
                continue
            if root_job_id and _root_job_id(record) != root_job_id:
                continue
            if customer_id and _text(record.get("customer_id")) != customer_id:
                continue
            if user_id and _text(record.get("user_id")) != user_id:
                continue
            records.append(record)
    root_counts: dict[str, int] = {}
    for record in records:
        root_counts[_root_job_id(record)] = root_counts.get(_root_job_id(record), 0) + 1
    rows: list[dict[str, Any]] = []
    for record in records:
        root_id = _root_job_id(record)
        rows.append(
            {
                "job_id": _text(record.get("job_id")),
                "root_job_id": root_id,
                "status": _text(record.get("status")),
                "target_id": _text(record.get("target_id")),
                "family": _text(record.get("family")),
                "ligand_count": int(record.get("ligand_count") or 0),
                "attempt_index": int(record.get("attempt_index") or 1),
                "root_attempt_count": root_counts.get(root_id, 0),
                "retry_of_job_id": _text(record.get("retry_of_job_id")),
                "parent_job_id": _text(record.get("parent_job_id")),
                "source_host": _text(record.get("source_host")),
                "customer_id": _text(record.get("customer_id")),
                "user_id": _text(record.get("user_id")),
                "event_actors": _event_actors(record),
                "request_sha256": _text(record.get("request_sha256")),
                "idempotency_key": _text(record.get("idempotency_key")),
                "progress_percent": float(record.get("progress_percent") or 0.0),
                "progress_state": _text(record.get("progress_state")),
                "current_step": _text(record.get("current_step")),
                "worker_state": _text(record.get("worker_state")),
                "worker_lease_id": _text(record.get("worker_lease_id")),
                "worker_id": _text(record.get("worker_id")),
                "heartbeat_at_utc": _text(record.get("heartbeat_at_utc")),
                "stale_worker_lease_detected": record.get("stale_worker_lease_detected") is True,
                "stale_worker_lease_timeout_seconds": int(record.get("stale_worker_lease_timeout_seconds") or 0),
                "stale_worker_lease_previous_heartbeat_at_utc": _text(
                    record.get("stale_worker_lease_previous_heartbeat_at_utc")
                ),
                "stale_worker_lease_detected_at_utc": _text(record.get("stale_worker_lease_detected_at_utc")),
                "queue_status": _text(record.get("queue_status")),
                "queue_position": int(record.get("queue_position") or 0),
                "max_retry_attempts": int(record.get("max_retry_attempts") or MAX_RETRY_ATTEMPTS),
                "retry_policy": _text(record.get("retry_policy")),
                "retry_limit_reached": record.get("retry_limit_reached") is True,
                "progress_percent_range_valid": record.get("progress_percent_range_valid") is True,
                "status_progress_contract_ready": record.get("status_progress_contract_ready") is True,
                "workflow_controls_ready": record.get("workflow_controls_ready") is True,
                "workflow_control_links": record.get("workflow_control_links")
                if isinstance(record.get("workflow_control_links"), dict)
                else {},
                "workflow_allowed_actions": list(record.get("workflow_allowed_actions") or []),
                "workflow_disabled_actions": list(record.get("workflow_disabled_actions") or []),
                "workflow_next_customer_actions": list(record.get("workflow_next_customer_actions") or []),
                "status_transition_contract": record.get("status_transition_contract")
                if isinstance(record.get("status_transition_contract"), dict)
                else {},
                "status_snapshot_persisted": record.get("status_snapshot_persisted") is True,
                "status_snapshot": record.get("status_snapshot") if isinstance(record.get("status_snapshot"), dict) else {},
                "job_retention_policy": _text(record.get("job_retention_policy")),
                "job_retention_days": int(record.get("job_retention_days") or 0),
                "rerun_manifest": record.get("rerun_manifest") if isinstance(record.get("rerun_manifest"), dict) else {},
                "rerun_manifest_ready": record.get("rerun_manifest_ready") is True,
                "reproducible_rerun_ready": record.get("reproducible_rerun_ready") is True,
                "long_running_status_persistence_ready": record.get("long_running_status_persistence_ready") is True,
                "production_ai_inference_subject_active": record.get("production_ai_inference_subject_active") is True,
                "production_ai_correction_applied": record.get("production_ai_correction_applied") is True,
                "production_ai_abstention_enforced": record.get("production_ai_abstention_enforced") is True,
                "production_ai_default_residual_mode": _text(record.get("production_ai_default_residual_mode")),
                "production_ai_promotion_allowed": record.get("production_ai_promotion_allowed") is True,
                "production_ai_customer_facing_auto_correction_allowed": record.get(
                    "production_ai_customer_facing_auto_correction_allowed"
                )
                is True,
                "production_ai_customer_facing_score_mutation_allowed": record.get(
                    "production_ai_customer_facing_score_mutation_allowed"
                )
                is True,
                "production_ai_customer_facing_ranking_mutation_allowed": record.get(
                    "production_ai_customer_facing_ranking_mutation_allowed"
                )
                is True,
                "production_ai_trained_checkpoint_count": int(record.get("production_ai_trained_checkpoint_count") or 0),
                "production_ai_abstention_reason": _text(record.get("production_ai_abstention_reason")),
                "production_ai_what_would_change_decision": _text(
                    record.get("production_ai_what_would_change_decision")
                ),
                "scope_claim_guard_ready": record.get("scope_claim_guard_ready") is True,
                "scope_claim_allowed_for_request": record.get("scope_claim_allowed_for_request") is True,
                "scope_claim_status": _text(record.get("scope_claim_status")),
                "blocked_claim_scopes": list(record.get("blocked_claim_scopes") or []),
                "claim_blocked_domains": list(record.get("claim_blocked_domains") or []),
                "general_platform_claim_allowed": record.get("general_platform_claim_allowed") is True,
                "ai_decision_graph_trace_ready": record.get("ai_decision_graph_trace_ready") is True,
                "ai_decision_graph_ordered_path": list(
                    record.get("ai_decision_graph_ordered_path") or []
                ),
                "ai_decision_graph_node_count": int(record.get("ai_decision_graph_node_count") or 0),
                "ai_decision_graph_edge_count": int(record.get("ai_decision_graph_edge_count") or 0),
                "ai_decision_graph_abstention_node_id": _text(
                    record.get("ai_decision_graph_abstention_node_id")
                ),
                "ai_decision_graph_current_node_id": _text(
                    record.get("ai_decision_graph_current_node_id")
                ),
                "customer_report_explanation_ready": record.get("customer_report_explanation_ready") is True,
                "customer_report_card_ready": record.get("customer_report_card_ready") is True,
                "customer_report_delivery_contract_ready": record.get(
                    "customer_report_delivery_contract_ready"
                )
                is True,
                "customer_report_evidence_binding_ready": record.get(
                    "customer_report_evidence_binding_ready"
                )
                is True,
                "customer_report_selection_rationale_ready": record.get(
                    "customer_report_selection_rationale_ready"
                )
                is True,
                "customer_report_uncertainty_posture_ready": record.get(
                    "customer_report_uncertainty_posture_ready"
                )
                is True,
                "customer_report_prohibited_claims_ready": record.get(
                    "customer_report_prohibited_claims_ready"
                )
                is True,
                "customer_report_selection_rationale": _text(
                    record.get("customer_report_selection_rationale")
                ),
                "customer_report_uncertainty_posture": _text(record.get("customer_report_uncertainty_posture")),
                "customer_report_prohibited_claims": list(record.get("customer_report_prohibited_claims") or []),
                "customer_report_required_block_count": int(
                    record.get("customer_report_required_block_count") or 0
                ),
                "customer_report_ready_block_count": int(
                    record.get("customer_report_ready_block_count") or 0
                ),
                "customer_report_blocked_block_count": int(
                    record.get("customer_report_blocked_block_count") or 0
                ),
                "customer_report_section_count": int(record.get("customer_report_section_count") or 0),
                "customer_report_primary_abstention_reason": _text(
                    record.get("customer_report_primary_abstention_reason")
                ),
                "customer_report_what_would_change_decision": _text(
                    record.get("customer_report_what_would_change_decision")
                ),
                "customer_report_card": record.get("customer_report_card")
                if isinstance(record.get("customer_report_card"), dict)
                else {},
                "created_at_utc": _text(record.get("created_at_utc")),
                "updated_at_utc": _text(record.get("updated_at_utc")),
                "last_event_type": _text(record.get("last_event_type")),
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        )
        if len(rows) >= limit:
            break
    return {
        "status": "product_job_history_ready",
        "job_count": len(rows),
        "source_host_filter": source_host,
        "root_job_id_filter": root_job_id,
        "customer_id_filter": customer_id,
        "user_id_filter": user_id,
        "jobs": rows,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def cancel_job_record(jobs_dir: Path, job_id: str, *, reason: str = "", actor: str = "") -> dict[str, Any]:
    record = read_job_record(jobs_dir, job_id)
    if not record:
        return {
            "job_id": job_id,
            "status": "missing",
            "cancel_recorded": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    updated = append_job_event(record, event_type="cancel_requested", reason=reason, actor=actor)
    updated["status"] = "cancel_requested_fail_closed"
    updated["cancel_recorded"] = True
    updated["progress_state"] = "cancel_requested_fail_closed"
    updated["current_step"] = "operator_cancel_request"
    updated["worker_state"] = "not_started_fail_closed"
    if _text(record.get("worker_lease_id")):
        updated["worker_state"] = "cancel_acknowledged_fail_closed"
        updated["worker_cancel_acknowledged"] = True
        updated["worker_cancel_acknowledged_at_utc"] = updated["updated_at_utc"]
    updated["cancellable"] = False
    updated["retryable"] = True
    updated = _refresh_status_metadata(updated)
    write_job_record(jobs_dir, updated)
    return updated


def lease_job_record(jobs_dir: Path, job_id: str, *, worker_id: str, actor: str = "") -> dict[str, Any]:
    record = read_job_record(jobs_dir, job_id)
    if not record:
        return {
            "job_id": job_id,
            "status": "missing",
            "worker_lease_acquired": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    created = utc_now_iso()
    lease_id = f"{job_id}:lease:1"
    updated = append_job_event(
        record,
        event_type="worker_lease_acquired",
        reason="worker lifecycle contract probe",
        actor=actor or worker_id,
        details={"worker_id": worker_id, "worker_lease_id": lease_id},
    )
    updated["status"] = "running_fail_closed"
    updated["progress_percent"] = max(_progress_percent(updated), 1.0)
    updated["progress_state"] = "worker_heartbeat_recorded"
    updated["current_step"] = "worker_lease_acquired"
    updated["worker_state"] = "leased_fail_closed"
    updated["worker_id"] = worker_id
    updated["worker_lease_id"] = lease_id
    updated["worker_lease_acquired"] = True
    updated["worker_lease_acquired_at_utc"] = created
    updated["heartbeat_at_utc"] = created
    updated["cancellable"] = True
    updated["retryable"] = False
    updated = _refresh_status_metadata(updated)
    write_job_record(jobs_dir, updated)
    return updated


def heartbeat_job_record(
    jobs_dir: Path,
    job_id: str,
    *,
    worker_id: str,
    progress_percent: float,
    current_step: str,
    actor: str = "",
) -> dict[str, Any]:
    record = read_job_record(jobs_dir, job_id)
    if not record:
        return {
            "job_id": job_id,
            "status": "missing",
            "heartbeat_recorded": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    lease_id = _text(record.get("worker_lease_id"))
    lease_valid = bool(lease_id and _text(record.get("worker_id")) == worker_id)
    heartbeat_at = utc_now_iso()
    updated = append_job_event(
        record,
        event_type="worker_heartbeat",
        reason="worker lifecycle contract probe",
        actor=actor or worker_id,
        details={
            "worker_id": worker_id,
            "worker_lease_id": lease_id,
            "lease_valid": lease_valid,
            "progress_percent": progress_percent,
            "current_step": current_step,
        },
    )
    updated["status"] = "running_fail_closed" if lease_valid else "blocked_contract_validation"
    updated["heartbeat_recorded"] = lease_valid
    updated["progress_percent"] = min(99.0, max(0.0, float(progress_percent)))
    updated["progress_state"] = "worker_heartbeat_recorded"
    updated["current_step"] = _text(current_step) or "worker_heartbeat"
    updated["worker_state"] = "active_fail_closed" if lease_valid else "not_started_fail_closed"
    updated["heartbeat_at_utc"] = heartbeat_at
    updated["cancellable"] = lease_valid
    updated["retryable"] = not lease_valid
    updated = _refresh_status_metadata(updated)
    write_job_record(jobs_dir, updated)
    return updated


def acknowledge_cancel_job_record(
    jobs_dir: Path,
    job_id: str,
    *,
    worker_id: str,
    reason: str = "",
    actor: str = "",
) -> dict[str, Any]:
    record = read_job_record(jobs_dir, job_id)
    if not record:
        return {
            "job_id": job_id,
            "status": "missing",
            "worker_cancel_acknowledged": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    lease_valid = _text(record.get("worker_id")) == worker_id and bool(_text(record.get("worker_lease_id")))
    updated = append_job_event(
        record,
        event_type="worker_cancel_acknowledged",
        reason=reason,
        actor=actor or worker_id,
        details={"worker_id": worker_id, "lease_valid": lease_valid},
    )
    updated["status"] = "cancel_requested_fail_closed"
    updated["worker_cancel_acknowledged"] = lease_valid
    updated["worker_cancel_acknowledged_at_utc"] = updated["updated_at_utc"]
    updated["progress_state"] = "worker_heartbeat_recorded"
    updated["current_step"] = "worker_cancel_acknowledged"
    updated["worker_state"] = "cancel_acknowledged_fail_closed" if lease_valid else "not_started_fail_closed"
    updated["cancellable"] = False
    updated["retryable"] = True
    updated = _refresh_status_metadata(updated)
    write_job_record(jobs_dir, updated)
    return updated


def fail_job_record(jobs_dir: Path, job_id: str, *, reason: str, actor: str = "") -> dict[str, Any]:
    record = read_job_record(jobs_dir, job_id)
    if not record:
        return {
            "job_id": job_id,
            "status": "missing",
            "failure_recorded": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    updated = append_job_event(
        record,
        event_type="worker_failed",
        reason=reason,
        actor=actor,
        details={"retryable": True},
    )
    updated["status"] = "failed_fail_closed"
    updated["failure_recorded"] = True
    updated["progress_state"] = "worker_failed_retryable"
    updated["current_step"] = "worker_failure_recorded"
    updated["worker_state"] = "failed_retryable_fail_closed"
    updated["cancellable"] = False
    updated["retryable"] = True
    updated = _refresh_status_metadata(updated)
    write_job_record(jobs_dir, updated)
    return updated


def mark_stale_worker_leases(
    jobs_dir: Path,
    *,
    lease_timeout_seconds: int = JOB_LEASE_TIMEOUT_SECONDS,
    actor: str = "orchestration-watchdog",
) -> dict[str, Any]:
    timeout_seconds = max(1, int(lease_timeout_seconds or JOB_LEASE_TIMEOUT_SECONDS))
    now = datetime.now(timezone.utc)
    scanned_count = 0
    stale_count = 0
    updated_jobs: list[dict[str, Any]] = []
    if jobs_dir.exists():
        for path in sorted(jobs_dir.glob("*.json")):
            record = read_job_record(jobs_dir, path.stem)
            if not record:
                continue
            scanned_count += 1
            if _text(record.get("status")) != "running_fail_closed":
                continue
            if not _text(record.get("worker_lease_id")) or not _text(record.get("worker_id")):
                continue
            heartbeat_at = _parse_utc_iso(record.get("heartbeat_at_utc"))
            if heartbeat_at is None:
                age_seconds = timeout_seconds + 1
            else:
                age_seconds = int((now - heartbeat_at).total_seconds())
            if age_seconds <= timeout_seconds:
                continue
            stale_count += 1
            updated = append_job_event(
                record,
                event_type="worker_lease_stale",
                reason="worker heartbeat exceeded lease timeout",
                actor=actor,
                details={
                    "worker_id": _text(record.get("worker_id")),
                    "worker_lease_id": _text(record.get("worker_lease_id")),
                    "heartbeat_age_seconds": age_seconds,
                    "lease_timeout_seconds": timeout_seconds,
                    "retryable": True,
                },
            )
            updated["status"] = "failed_fail_closed"
            updated["failure_recorded"] = True
            updated["failure_reason"] = "worker_lease_stale_timeout"
            updated["progress_state"] = "worker_failed_retryable"
            updated["current_step"] = "worker_failure_recorded"
            updated["worker_state"] = "failed_retryable_fail_closed"
            updated["stale_worker_lease_detected"] = True
            updated["stale_worker_lease_timeout_seconds"] = timeout_seconds
            updated["stale_worker_lease_previous_heartbeat_at_utc"] = _text(record.get("heartbeat_at_utc"))
            updated["stale_worker_lease_detected_at_utc"] = updated["updated_at_utc"]
            updated["cancellable"] = False
            updated["retryable"] = True
            updated = _refresh_status_metadata(updated)
            write_job_record(jobs_dir, updated)
            updated_jobs.append(updated)
    return {
        "status": "stale_worker_lease_sweep_ready",
        "stale_worker_lease_sweep_ready": True,
        "lease_timeout_seconds": timeout_seconds,
        "scanned_job_count": scanned_count,
        "stale_worker_lease_detected_count": stale_count,
        "stale_worker_lease_updated_count": len(updated_jobs),
        "retryable_after_stale_count": sum(1 for row in updated_jobs if row.get("retryable") is True),
        "updated_job_ids": [_text(row.get("job_id")) for row in updated_jobs],
        "jobs": updated_jobs,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def retry_job_record(jobs_dir: Path, job_id: str, *, reason: str = "", actor: str = "") -> dict[str, Any]:
    record = read_job_record(jobs_dir, job_id)
    if not record:
        return {
            "job_id": job_id,
            "status": "missing",
            "retry_recorded": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    retry_events = [
        event for event in record.get("event_history", []) or []
        if isinstance(event, dict) and _text(event.get("event_type")) == "retry_requested"
    ]
    retry_request_count = len(retry_events) + 1
    root_job_id = _text(record.get("retry_of_job_id")) or _text(record.get("job_id"))
    retry_job_id = _retry_attempt_job_id(jobs_dir, root_job_id, retry_request_count)
    next_attempt_index = int(record.get("attempt_index") or 1) + 1
    updated = append_job_event(
        record,
        event_type="retry_requested",
        reason=reason,
        actor=actor,
        details={
            "retry_job_id": retry_job_id,
            "retry_attempt_index": next_attempt_index,
            "retry_of_job_id": root_job_id,
        },
    )
    updated["status"] = "retry_requested_fail_closed"
    updated["retry_recorded"] = True
    updated["retry_request_count"] = retry_request_count
    updated["retry_of_job_id"] = _text(record.get("retry_of_job_id"))
    updated["progress_percent"] = 0.0
    updated["progress_state"] = "retry_requested_fail_closed"
    updated["current_step"] = "operator_retry_request"
    updated["worker_state"] = "not_started_fail_closed"
    updated = _refresh_status_metadata(updated)
    write_job_record(jobs_dir, updated)
    created = utc_now_iso()
    retry_record = dict(record)
    retry_record["job_id"] = retry_job_id
    retry_record["status"] = "retry_requested_fail_closed"
    retry_record["created_at_utc"] = created
    retry_record["updated_at_utc"] = created
    retry_record["attempt_index"] = next_attempt_index
    retry_record["root_job_id"] = root_job_id
    retry_record["retry_of_job_id"] = root_job_id
    retry_record["parent_job_id"] = _text(record.get("job_id"))
    retry_record["last_event_type"] = "retry_attempt_created"
    retry_record["event_history"] = [
        {
            "event_type": "retry_attempt_created",
            "created_at_utc": created,
            "reason": reason,
            "actor": actor,
            "retry_of_job_id": root_job_id,
            "parent_job_id": _text(record.get("job_id")),
            "request_sha256": _text(record.get("request_sha256")),
            "idempotency_key": _text(record.get("idempotency_key") or record.get("request_sha256")),
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    ]
    retry_record["retry_recorded"] = True
    retry_record["retry_request_count"] = retry_request_count
    retry_record["request_sha256"] = _text(record.get("request_sha256"))
    retry_record["idempotency_key"] = _text(record.get("idempotency_key") or record.get("request_sha256"))
    retry_record["progress_percent"] = 0.0
    retry_record["progress_state"] = "retry_attempt_recorded"
    retry_record["current_step"] = "contract_validation"
    retry_record["worker_state"] = "not_started_fail_closed"
    retry_record["status_snapshot"] = _status_snapshot(retry_record)
    retry_record["status_snapshot_persisted"] = True
    retry_record["job_retention_policy"] = _text(retry_record.get("job_retention_policy")) or "local_job_ledger_retain_90_days_minimum"
    retry_record["job_retention_days"] = int(retry_record.get("job_retention_days") or 90)
    retry_record["rerun_manifest"] = _rerun_manifest(retry_record)
    retry_record["rerun_manifest_ready"] = True
    retry_record["reproducible_rerun_ready"] = True
    retry_record["long_running_status_persistence_ready"] = True
    retry_record["cancellable"] = True
    retry_record["retryable"] = True
    retry_record["execution_enabled"] = False
    retry_record["docking_results_emitted"] = False
    retry_record["external_state_mutated"] = False
    retry_record["claim_boundary"] = retry_record.get("claim_boundary") or CLAIM_BOUNDARY
    retry_record = _refresh_status_metadata(retry_record)
    write_job_record(jobs_dir, retry_record)
    return retry_record


def job_history(jobs_dir: Path, job_id: str) -> dict[str, Any]:
    record = read_job_record(jobs_dir, job_id)
    if not record:
        return {
            "job_id": job_id,
            "status": "missing",
            "event_count": 0,
            "events": [],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    events = list(record.get("event_history") or [])
    return {
        "job_id": _text(record.get("job_id")),
        "root_job_id": _root_job_id(record),
        "status": _text(record.get("status")),
        "source_host": _text(record.get("source_host")),
        "customer_id": _text(record.get("customer_id")),
        "user_id": _text(record.get("user_id")),
        "attempt_index": int(record.get("attempt_index") or 1),
        "retry_of_job_id": _text(record.get("retry_of_job_id")),
        "parent_job_id": _text(record.get("parent_job_id")),
        "request_sha256": _text(record.get("request_sha256")),
        "idempotency_key": _text(record.get("idempotency_key")),
        "progress_percent": _progress_percent(record),
        "progress_state": _text(record.get("progress_state")),
        "current_step": _text(record.get("current_step")),
        "worker_state": _text(record.get("worker_state")),
        "worker_lease_id": _text(record.get("worker_lease_id")),
        "worker_id": _text(record.get("worker_id")),
        "heartbeat_at_utc": _text(record.get("heartbeat_at_utc")),
        "stale_worker_lease_detected": record.get("stale_worker_lease_detected") is True,
        "stale_worker_lease_timeout_seconds": int(record.get("stale_worker_lease_timeout_seconds") or 0),
        "stale_worker_lease_previous_heartbeat_at_utc": _text(
            record.get("stale_worker_lease_previous_heartbeat_at_utc")
        ),
        "stale_worker_lease_detected_at_utc": _text(record.get("stale_worker_lease_detected_at_utc")),
        "worker_cancel_acknowledged": record.get("worker_cancel_acknowledged") is True,
        "worker_cancel_acknowledged_at_utc": _text(record.get("worker_cancel_acknowledged_at_utc")),
        "cancellable": record.get("cancellable") is True,
        "retryable": record.get("retryable") is True,
        "queue_status": _text(record.get("queue_status")),
        "queue_position": int(record.get("queue_position") or 0),
        "max_retry_attempts": int(record.get("max_retry_attempts") or MAX_RETRY_ATTEMPTS),
        "retry_policy": _text(record.get("retry_policy")),
        "retry_limit_reached": record.get("retry_limit_reached") is True,
        "progress_percent_range_valid": record.get("progress_percent_range_valid") is True,
        "status_progress_contract_ready": record.get("status_progress_contract_ready") is True,
        "workflow_controls_ready": record.get("workflow_controls_ready") is True,
        "workflow_control_links": record.get("workflow_control_links")
        if isinstance(record.get("workflow_control_links"), dict)
        else {},
        "workflow_allowed_actions": list(record.get("workflow_allowed_actions") or []),
        "workflow_disabled_actions": list(record.get("workflow_disabled_actions") or []),
        "workflow_next_customer_actions": list(record.get("workflow_next_customer_actions") or []),
        "status_transition_contract": record.get("status_transition_contract")
        if isinstance(record.get("status_transition_contract"), dict)
        else {},
        "event_actors": _event_actors(record),
        "event_count": len(events),
        "events": events,
        "status_snapshot": record.get("status_snapshot") if isinstance(record.get("status_snapshot"), dict) else {},
        "status_snapshot_persisted": record.get("status_snapshot_persisted") is True,
        "job_retention_policy": _text(record.get("job_retention_policy")),
        "job_retention_days": int(record.get("job_retention_days") or 0),
        "rerun_manifest": record.get("rerun_manifest") if isinstance(record.get("rerun_manifest"), dict) else {},
        "rerun_manifest_ready": record.get("rerun_manifest_ready") is True,
        "reproducible_rerun_ready": record.get("reproducible_rerun_ready") is True,
        "long_running_status_persistence_ready": record.get("long_running_status_persistence_ready") is True,
        "production_ai_inference_subject_active": record.get("production_ai_inference_subject_active") is True,
        "production_ai_correction_applied": record.get("production_ai_correction_applied") is True,
        "production_ai_abstention_enforced": record.get("production_ai_abstention_enforced") is True,
        "production_ai_default_residual_mode": _text(record.get("production_ai_default_residual_mode")),
        "production_ai_promotion_allowed": record.get("production_ai_promotion_allowed") is True,
        "production_ai_customer_facing_auto_correction_allowed": record.get(
            "production_ai_customer_facing_auto_correction_allowed"
        )
        is True,
        "production_ai_customer_facing_score_mutation_allowed": record.get(
            "production_ai_customer_facing_score_mutation_allowed"
        )
        is True,
        "production_ai_customer_facing_ranking_mutation_allowed": record.get(
            "production_ai_customer_facing_ranking_mutation_allowed"
        )
        is True,
        "production_ai_trained_checkpoint_count": int(record.get("production_ai_trained_checkpoint_count") or 0),
        "production_ai_selected_sidecar_missing_output_fields": list(
            record.get("production_ai_selected_sidecar_missing_output_fields") or []
        ),
        "production_ai_abstention_reason": _text(record.get("production_ai_abstention_reason")),
        "production_ai_what_would_change_decision": _text(record.get("production_ai_what_would_change_decision")),
        "scope_claim_guard_ready": record.get("scope_claim_guard_ready") is True,
        "scope_claim_allowed_for_request": record.get("scope_claim_allowed_for_request") is True,
        "scope_claim_status": _text(record.get("scope_claim_status")),
        "blocked_claim_scopes": list(record.get("blocked_claim_scopes") or []),
        "claim_blocked_domains": list(record.get("claim_blocked_domains") or []),
        "general_platform_claim_allowed": record.get("general_platform_claim_allowed") is True,
        "ai_decision_graph_trace_ready": record.get("ai_decision_graph_trace_ready") is True,
        "ai_decision_graph_ordered_path": list(record.get("ai_decision_graph_ordered_path") or []),
        "ai_decision_graph_node_count": int(record.get("ai_decision_graph_node_count") or 0),
        "ai_decision_graph_edge_count": int(record.get("ai_decision_graph_edge_count") or 0),
        "ai_decision_graph_blocked_node_ids": list(
            record.get("ai_decision_graph_blocked_node_ids") or []
        ),
        "ai_decision_graph_abstention_node_id": _text(
            record.get("ai_decision_graph_abstention_node_id")
        ),
        "ai_decision_graph_current_node_id": _text(record.get("ai_decision_graph_current_node_id")),
        "ai_decision_graph_trace": record.get("ai_decision_graph_trace")
        if isinstance(record.get("ai_decision_graph_trace"), list)
        else [],
        "ai_decision_graph_edges": record.get("ai_decision_graph_edges")
        if isinstance(record.get("ai_decision_graph_edges"), list)
        else [],
        "customer_report_explanation_ready": record.get("customer_report_explanation_ready") is True,
        "customer_report_card_ready": record.get("customer_report_card_ready") is True,
        "customer_report_delivery_contract_ready": record.get(
            "customer_report_delivery_contract_ready"
        )
        is True,
        "customer_report_evidence_binding_ready": record.get(
            "customer_report_evidence_binding_ready"
        )
        is True,
        "customer_report_selection_rationale_ready": record.get(
            "customer_report_selection_rationale_ready"
        )
        is True,
        "customer_report_uncertainty_posture_ready": record.get(
            "customer_report_uncertainty_posture_ready"
        )
        is True,
        "customer_report_prohibited_claims_ready": record.get(
            "customer_report_prohibited_claims_ready"
        )
        is True,
        "customer_report_selection_rationale": _text(record.get("customer_report_selection_rationale")),
        "customer_report_uncertainty_posture": _text(record.get("customer_report_uncertainty_posture")),
        "customer_report_prohibited_claims": list(record.get("customer_report_prohibited_claims") or []),
        "customer_report_required_block_count": int(
            record.get("customer_report_required_block_count") or 0
        ),
        "customer_report_ready_block_count": int(record.get("customer_report_ready_block_count") or 0),
        "customer_report_blocked_block_count": int(
            record.get("customer_report_blocked_block_count") or 0
        ),
        "customer_report_section_count": int(record.get("customer_report_section_count") or 0),
        "customer_report_primary_abstention_reason": _text(record.get("customer_report_primary_abstention_reason")),
        "customer_report_what_would_change_decision": _text(record.get("customer_report_what_would_change_decision")),
        "customer_report_card": record.get("customer_report_card")
        if isinstance(record.get("customer_report_card"), dict)
        else {},
        "customer_report_sections": record.get("customer_report_sections")
        if isinstance(record.get("customer_report_sections"), list)
        else [],
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
