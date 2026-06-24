from __future__ import annotations

from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def apply_terminal_job_state(
    record: dict[str, Any],
    *,
    simulation_status: str,
    result_file: str = "",
    error: str = "",
) -> dict[str, Any]:
    """Apply a persisted terminal state to a product docking ledger record."""

    completed = str(simulation_status).strip() == "completed"
    updated = dict(record)
    retry_limit_reached = updated.get("retry_limit_reached") is True

    if completed:
        status = "completed_fail_closed"
        progress_percent = 100.0
        progress_state = "worker_dispatch_completed"
        current_step = "worker_dispatch_completed"
        worker_state = "completed_fail_closed"
        queue_status = "completed_fail_closed"
        retryable = False
    else:
        status = "failed_fail_closed"
        progress_percent = min(max(float(updated.get("progress_percent") or 0.0), 0.0), 99.0)
        progress_state = "worker_failed_retryable"
        current_step = "worker_failure_recorded"
        worker_state = "failed_retryable_fail_closed"
        queue_status = "failed_retryable_fail_closed"
        retryable = not retry_limit_reached

    updated.update(
        {
            "status": status,
            "progress_percent": progress_percent,
            "progress_state": progress_state,
            "current_step": current_step,
            "worker_state": worker_state,
            "queue_status": queue_status,
            "cancellable": False,
            "retryable": retryable,
            "simulation_sync_status": str(simulation_status),
            "simulation_result_file": str(result_file or ""),
            "simulation_error": str(error or ""),
            "progress_percent_range_valid": True,
            "status_progress_contract_ready": True,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    )

    job_id = _text(updated.get("job_id"))
    allowed_actions = ["view_status", "view_history"]
    if retryable:
        allowed_actions.append("retry")
    updated.update(
        {
            "workflow_controls_ready": True,
            "workflow_control_links": {
                "self": f"/product/docking/jobs/{job_id}",
                "history": f"/product/docking/jobs/{job_id}/history",
                "cancel": f"/product/docking/jobs/{job_id}/cancel",
                "retry": f"/product/docking/jobs/{job_id}/retry",
            },
            "workflow_allowed_actions": allowed_actions,
            "workflow_disabled_actions": [
                action for action in ("cancel", "retry") if action not in allowed_actions
            ],
            "workflow_next_customer_actions": allowed_actions,
            "status_transition_contract": {
                "current_status": status,
                "queue_status": queue_status,
                "cancellable": False,
                "retryable": retryable,
                "retry_limit_reached": retry_limit_reached,
                "terminal_state": True,
                "fail_closed": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
            },
        }
    )

    snapshot = dict(updated.get("status_snapshot") or {})
    snapshot.update(
        {
            "job_id": job_id,
            "status": status,
            "progress_percent": progress_percent,
            "progress_state": progress_state,
            "current_step": current_step,
            "worker_state": worker_state,
            "queue_status": queue_status,
            "progress_percent_range_valid": True,
            "status_progress_contract_ready": True,
            "workflow_controls_ready": True,
            "workflow_allowed_actions": list(allowed_actions),
            "workflow_disabled_actions": list(updated["workflow_disabled_actions"]),
            "workflow_control_links": dict(updated["workflow_control_links"]),
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    )
    updated["status_snapshot"] = snapshot
    updated["status_snapshot_persisted"] = True
    return updated
