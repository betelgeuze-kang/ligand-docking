#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_queue_current.json"
DEFAULT_PROGRESS_JSON = "runs/wetlab_broad_screen_antitarget_progress_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_antitarget_execution_queue_current.md"
DEFAULT_STALE_MINUTES = 20.0


def _progress_rows(payload: dict[str, Any] | None) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {
        (
            str(row.get("primary_target_id", "")).strip(),
            str(row.get("anti_target_id", "")).strip(),
            str(row.get("primary_shard_id", "")).strip(),
        ): dict(row)
        for row in ((payload or {}).get("rows", []) or [])
        if str(row.get("primary_target_id", "")).strip()
        and str(row.get("anti_target_id", "")).strip()
        and str(row.get("primary_shard_id", "")).strip()
    }


def _is_resolved(status: str) -> bool:
    return "result_ready" in status or "explicit_hold" in status


def _parse_ts(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text)
    except Exception:
        return None


def _minutes_since(value: Any, now: dt.datetime) -> float:
    stamp = _parse_ts(value)
    if stamp is None:
        return 0.0
    return max((now - stamp).total_seconds() / 60.0, 0.0)


def _runner_kind(persisted: dict[str, Any]) -> str:
    runner_kind = str(persisted.get("runner_kind", "")).strip()
    if runner_kind:
        return runner_kind
    notes = str(persisted.get("notes", "")).strip()
    if "runtime_validation_only" in notes or "supervision_only" in notes:
        return "heartbeat_only"
    if bool(persisted.get("compute_pid_path")) or bool(persisted.get("compute_log_path")):
        return "compute_attached"
    return "unknown"


def _row_command(primary_target_id: str, anti_target_id: str, shard_id: str, event: str) -> str:
    if event == "start":
        return (
            "python3 tools/run_wetlab_broad_screen_antitarget_runner.py "
            f"--primary-target-id \"{primary_target_id}\" "
            f"--anti-target-id \"{anti_target_id}\" "
            f"--shard-id {shard_id} --replace-heartbeat"
        )
    return (
        "python3 tools/run_wetlab_broad_screen_antitarget_runtime_event.py "
        f"--primary-target-id \"{primary_target_id}\" "
        f"--anti-target-id \"{anti_target_id}\" "
        f"--shard-id {shard_id} --event {event}"
    )


def build_payload(
    antitarget_queue: dict[str, Any],
    progress_payload: dict[str, Any] | None = None,
    stale_minutes: float = DEFAULT_STALE_MINUTES,
) -> dict[str, Any]:
    base_rows = [dict(row) for row in (antitarget_queue.get("rows", []) or [])]
    progress_map = _progress_rows(progress_payload)
    now = dt.datetime.now()

    open_rows = [row for row in base_rows if bool(row.get("primary_gate_open", False))]
    open_keys = [
        (
            str(row.get("primary_target_id", "")).strip(),
            str(row.get("anti_target_id", "")).strip(),
            str(row.get("primary_shard_id", "")).strip(),
        )
        for row in open_rows
    ]
    persisted_statuses: list[str] = []
    for key in open_keys:
        persisted = progress_map.get(key, {})
        status = str(persisted.get("queue_status", "")).strip()
        if "running" in status:
            update_age_minutes = _minutes_since(persisted.get("updated_at") or persisted.get("started_at"), now)
            if update_age_minutes > float(stale_minutes):
                status = "stale_running_needs_recovery"
            elif status == "running" and _runner_kind(persisted) == "heartbeat_only":
                status = "running_supervision_only"
        persisted_statuses.append(status)

    stale_index = next((idx for idx, status in enumerate(persisted_statuses) if "stale_running" in status), None)
    running_index = next((idx for idx, status in enumerate(persisted_statuses) if "running" in status), None)
    if stale_index is not None:
        actionable_index = stale_index
        actionable_status = "stale_running_needs_recovery"
    elif running_index is not None:
        actionable_index = running_index
        actionable_status = persisted_statuses[running_index]
    else:
        actionable_index = next((idx for idx, status in enumerate(persisted_statuses) if not _is_resolved(status)), None)
        actionable_status = (
            "ready_first_counterscreen" if actionable_index == 0 else "ready_after_previous_antitarget_resolution"
        ) if actionable_index is not None else ""

    actionable_key: tuple[str, str, str] | None = None
    if actionable_index is not None and actionable_index < len(open_keys):
        actionable_key = open_keys[actionable_index]

    rows: list[dict[str, Any]] = []
    for row in base_rows:
        primary_target_id = str(row.get("primary_target_id", "")).strip()
        anti_target_id = str(row.get("anti_target_id", "")).strip()
        primary_shard_id = str(row.get("primary_shard_id", "")).strip()
        key = (primary_target_id, anti_target_id, primary_shard_id)
        persisted = progress_map.get(key, {})
        queue_status = str(persisted.get("queue_status", "")).strip()
        runner_kind = _runner_kind(persisted)
        concrete_compute_attached = bool(persisted.get("concrete_compute_attached", False)) or runner_kind == "compute_attached"
        progress_update_age_minutes = _minutes_since(persisted.get("updated_at") or persisted.get("started_at"), now)
        if "running" in queue_status and progress_update_age_minutes > float(stale_minutes):
            queue_status = "stale_running_needs_recovery"
        elif queue_status == "running" and runner_kind == "heartbeat_only":
            queue_status = "running_supervision_only"

        if not queue_status:
            if not bool(row.get("primary_gate_open", False)):
                queue_status = "blocked_on_primary_full_bulk_ready"
            elif actionable_key is None:
                queue_status = "result_ready"
            elif key == actionable_key:
                queue_status = actionable_status
            elif key in set(open_keys[: actionable_index or 0]):
                queue_status = "result_ready"
            else:
                queue_status = "blocked_on_previous_antitarget_resolution"

        rows.append(
            {
                **row,
                "queue_status": queue_status,
                "execution_state": (
                    "stale"
                    if "stale_running" in queue_status
                    else "watch_only"
                    if queue_status == "running_supervision_only"
                    else "running"
                    if "running" in queue_status
                    else "result_ready"
                    if _is_resolved(queue_status) and "explicit_hold" not in queue_status
                    else "explicit_hold"
                    if "explicit_hold" in queue_status
                    else "blocked"
                    if queue_status.startswith("blocked")
                    else "ready_to_launch"
                ),
                "progress_started_at": str(persisted.get("started_at", "")).strip(),
                "progress_updated_at": str(persisted.get("updated_at", "")).strip(),
                "progress_completed_at": str(persisted.get("completed_at", "")).strip(),
                "progress_update_age_minutes": round(progress_update_age_minutes, 1),
                "notes": str(persisted.get("notes", "")).strip(),
                "heartbeat_count": int(persisted.get("heartbeat_count", 0) or 0),
                "event_count": int(persisted.get("event_count", 0) or 0),
                "run_attempt": int(persisted.get("run_attempt", 0) or 0),
                "last_event": str(persisted.get("last_event", "")).strip(),
                "last_event_at": str(persisted.get("last_event_at", "")).strip(),
                "runner_kind": runner_kind,
                "concrete_compute_attached": concrete_compute_attached,
                "compute_pid": int(persisted.get("compute_pid", 0) or 0),
                "compute_pid_path": str(persisted.get("compute_pid_path", "")).strip(),
                "compute_log_path": str(persisted.get("compute_log_path", "")).strip(),
                "compute_summary_json": str(persisted.get("compute_summary_json", "")).strip(),
                "compute_summary_md": str(persisted.get("compute_summary_md", "")).strip(),
                "throughput_bridge_artifact": "runs/wetlab_broad_screen_antitarget_throughput_bridge_current.md",
                "watcher_resolution_hint": (
                    "watcher_can_auto_complete_after_short_heartbeat_budget"
                    if queue_status == "running_supervision_only"
                    else ""
                ),
                "launch_command": _row_command(primary_target_id, anti_target_id, primary_shard_id, "start"),
                "complete_command": _row_command(primary_target_id, anti_target_id, primary_shard_id, "complete"),
                "hold_command": _row_command(primary_target_id, anti_target_id, primary_shard_id, "hold"),
                "reset_command": _row_command(primary_target_id, anti_target_id, primary_shard_id, "reset"),
            }
        )

    first_actionable = next(
        (
            row
            for row in rows
            if str(row.get("queue_status", "")).startswith("ready")
            or "running" in str(row.get("queue_status", ""))
            or "stale_running" in str(row.get("queue_status", ""))
        ),
        None,
    )
    first_status = str(first_actionable.get("queue_status", "")).strip() if first_actionable else ""
    if first_actionable and first_status == "running_supervision_only":
        next_required_step = (
            f"Watcher-only supervision is active for {first_actionable['primary_target_id']} -> {first_actionable['anti_target_id']} shard {first_actionable['primary_shard_id']}; let the watcher auto-complete it or emit complete manually."
        )
    elif first_actionable and "running" in first_status:
        next_required_step = (
            f"Continue or complete {first_actionable['primary_target_id']} -> {first_actionable['anti_target_id']} shard {first_actionable['primary_shard_id']}."
        )
    elif first_actionable and "stale_running" in first_status:
        next_required_step = (
            f"Recover stale {first_actionable['primary_target_id']} -> {first_actionable['anti_target_id']} shard {first_actionable['primary_shard_id']} with reset or hold, then relaunch it."
        )
    elif first_actionable:
        next_required_step = (
            f"Dispatch {first_actionable['primary_target_id']} -> {first_actionable['anti_target_id']} shard {first_actionable['primary_shard_id']}."
        )
    else:
        next_required_step = "No anti-target counterscreen row is currently open; keep driving primary bulk screens until another target reaches full_bulk_top3_ready."

    return {
        "summary": {
            "status": "wetlab_broad_screen_antitarget_execution_queue_ready",
            "queue_row_count": len(rows),
            "ready_now_row_count": sum(1 for row in rows if str(row.get("queue_status", "")).startswith("ready")),
            "running_row_count": sum(1 for row in rows if "running" in str(row.get("queue_status", ""))),
            "supervision_only_running_row_count": sum(1 for row in rows if str(row.get("queue_status", "")) == "running_supervision_only"),
            "stale_row_count": sum(1 for row in rows if "stale_running" in str(row.get("queue_status", ""))),
            "resolved_row_count": sum(1 for row in rows if _is_resolved(str(row.get("queue_status", "")))),
            "first_actionable_primary_target_id": str(first_actionable.get("primary_target_id", "")).strip() if first_actionable else "",
            "first_actionable_anti_target_id": str(first_actionable.get("anti_target_id", "")).strip() if first_actionable else "",
            "first_actionable_shard_id": str(first_actionable.get("primary_shard_id", "")).strip() if first_actionable else "",
            "first_actionable_queue_status": first_status,
            "next_required_step": next_required_step,
        },
        "structured": {
            "antitarget_queue_artifact": "runs/wetlab_broad_screen_antitarget_queue_current.md",
            "progress_artifact": "runs/wetlab_broad_screen_antitarget_progress_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the anti-target counterscreen execution queue.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--progress-json", default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--stale-minutes", type=float, default=DEFAULT_STALE_MINUTES)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Anti-Target Execution Queue",
        build_payload(
            antitarget_queue=load_json(args.queue_json),
            progress_payload=maybe_load_json(args.progress_json),
            stale_minutes=args.stale_minutes,
        ),
    )
