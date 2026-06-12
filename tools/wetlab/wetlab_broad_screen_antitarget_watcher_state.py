#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any

from tools.wetlab_broad_screen_watch_utils import (
    antitarget_active_row,
    detect_throughput_summary,
    first_ready_row,
    process_alive,
    throughput_failed,
    throughput_ok,
)
from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_execution_queue_current.json"
DEFAULT_HEARTBEAT_PID = ROOT / "runs" / "wetlab_broad_screen_antitarget_heartbeat_loop.pid"
DEFAULT_HEARTBEAT_LOG = ROOT / "runs" / "wetlab_broad_screen_antitarget_heartbeat_loop.log"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_antitarget_watcher_state_current.md"
DEFAULT_SUPERVISION_MAX_HEARTBEATS = 4


def _parse_ts(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text)
    except Exception:
        return None


def _signal_age_minutes(row: dict[str, Any], *, now: dt.datetime) -> float:
    ts = (
        _parse_ts(row.get("progress_updated_at"))
        or _parse_ts(row.get("updated_at"))
        or _parse_ts(row.get("last_event_at"))
        or _parse_ts(row.get("completed_at"))
        or _parse_ts(row.get("started_at"))
    )
    if ts is None:
        return 0.0
    return max((now - ts).total_seconds() / 60.0, 0.0)


def _runner_kind(row: dict[str, Any]) -> str:
    runner_kind = str(row.get("runner_kind", "")).strip()
    if runner_kind:
        return runner_kind
    notes = str(row.get("notes", "")).strip()
    if "runtime_validation_only" in notes or "supervision_only" in notes:
        return "heartbeat_only"
    if bool(row.get("compute_pid_path")) or bool(row.get("compute_log_path")):
        return "compute_attached"
    return "heartbeat_only"


def _heartbeat_count(row: dict[str, Any]) -> int:
    return int(row.get("heartbeat_count", 0) or 0)


def inspect_state(
    execution_queue_payload: dict[str, Any],
    *,
    pid_file: Path = DEFAULT_HEARTBEAT_PID,
    stale_minutes: float = 20.0,
    supervision_max_heartbeats: int = DEFAULT_SUPERVISION_MAX_HEARTBEATS,
) -> dict[str, Any]:
    now = dt.datetime.now()
    active_row = antitarget_active_row(execution_queue_payload)
    next_ready_row = first_ready_row(
        execution_queue_payload,
        target_key="primary_target_id",
        shard_key="primary_shard_id",
    )
    pid_alive, pid_value = process_alive(str(pid_file))
    pid_state = "alive" if pid_alive else ("dead" if pid_value else "missing")
    signal_age_minutes = _signal_age_minutes(active_row, now=now) if active_row else 0.0
    active_runner_kind = _runner_kind(active_row) if active_row else "unknown"
    active_heartbeat_count = _heartbeat_count(active_row) if active_row else 0
    supervision_only = bool(active_row) and active_runner_kind == "heartbeat_only"
    compute_pid_path = str(active_row.get("compute_pid_path", "")).strip() if active_row else ""
    compute_pid_alive, compute_pid_value = process_alive(compute_pid_path) if compute_pid_path else (False, 0)
    summary_payload, detected_summary_json = detect_throughput_summary(
        {
            "preferred_summary_json": str(active_row.get("compute_summary_json", "")).strip() if active_row else "",
            "preferred_summary_md": str(active_row.get("compute_summary_md", "")).strip() if active_row else "",
            "preferred_log_path": str(active_row.get("compute_log_path", "")).strip() if active_row else "",
            "preferred_pid_path": compute_pid_path,
            "preferred_out_prefix": "",
            "out_prefix": "",
            "artifact_dir": str(Path(compute_pid_path).parent) if compute_pid_path else "",
        }
    )

    decision = "idle_no_open_antitarget_row"
    recommended_event = ""
    decision_reason = "no_running_or_ready_row"

    if active_row:
        if supervision_only and supervision_max_heartbeats > 0 and active_heartbeat_count >= supervision_max_heartbeats:
            decision = "auto_complete"
            recommended_event = "complete"
            decision_reason = "supervision_only_heartbeat_budget_consumed"
        elif active_runner_kind == "compute_attached" and compute_pid_path:
            if compute_pid_alive:
                if throughput_ok(summary_payload):
                    decision = "auto_complete_candidate_summary_ok"
                    recommended_event = "complete"
                    decision_reason = "compute_summary_status_ok"
                elif throughput_failed(summary_payload):
                    decision = "auto_hold_candidate_summary_failed"
                    recommended_event = "hold"
                    decision_reason = "compute_summary_failed"
                elif stale_minutes > 0 and signal_age_minutes > stale_minutes:
                    decision = "auto_hold_candidate_compute_stale"
                    recommended_event = "hold"
                    decision_reason = "compute_pid_alive_but_signal_stale"
                else:
                    decision = "continue_running_compute_alive"
                    decision_reason = "compute_pid_alive_recent_signal"
            else:
                if detected_summary_json and throughput_ok(summary_payload):
                    decision = "auto_complete_candidate_summary_ok"
                    recommended_event = "complete"
                    decision_reason = "compute_pid_exited_summary_ok"
                elif detected_summary_json and throughput_failed(summary_payload):
                    decision = "auto_hold_candidate_summary_failed"
                    recommended_event = "hold"
                    decision_reason = "compute_pid_exited_summary_failed"
                else:
                    decision = "auto_hold_candidate_pid_exited_no_summary"
                    recommended_event = "hold"
                    decision_reason = "compute_pid_exited_without_summary"
        elif active_runner_kind == "compute_attached" and throughput_ok(summary_payload):
            decision = "auto_complete_candidate_summary_ok"
            recommended_event = "complete"
            decision_reason = "compute_summary_status_ok"
        elif active_runner_kind == "compute_attached" and throughput_failed(summary_payload):
            decision = "auto_hold_candidate_summary_failed"
            recommended_event = "hold"
            decision_reason = "compute_summary_failed"
        elif pid_alive:
            if stale_minutes > 0 and signal_age_minutes > stale_minutes:
                decision = "auto_hold"
                recommended_event = "hold"
                decision_reason = "heartbeat_loop_alive_but_signal_stale"
            else:
                decision = "continue_supervision_only" if supervision_only else "continue_running"
                decision_reason = (
                    "supervision_only_heartbeat_loop_alive_recent_signal"
                    if supervision_only
                    else "heartbeat_loop_alive_recent_signal"
                )
        else:
            if 0.0 < signal_age_minutes <= stale_minutes:
                decision = "auto_complete"
                recommended_event = "complete"
                decision_reason = "heartbeat_loop_exited_after_recent_signal"
            else:
                decision = "auto_hold"
                recommended_event = "hold"
                decision_reason = "heartbeat_loop_exited_without_recent_signal"
    elif next_ready_row:
        decision = "auto_start_next"
        decision_reason = "ready_row_available_after_previous_resolution"

    return {
        "active_row": dict(active_row) if active_row else {},
        "next_ready_row": dict(next_ready_row) if next_ready_row else {},
        "signal_age_minutes": round(signal_age_minutes, 1),
        "heartbeat_count": active_heartbeat_count,
        "runner_kind": active_runner_kind,
        "supervision_only": supervision_only,
        "compute_pid_alive": compute_pid_alive,
        "compute_pid": compute_pid_value,
        "compute_pid_path": compute_pid_path,
        "throughput_summary_detected": bool(summary_payload),
        "throughput_summary_json": detected_summary_json or str(active_row.get("compute_summary_json", "")).strip() if active_row else "",
        "throughput_ok": throughput_ok(summary_payload),
        "throughput_failed": throughput_failed(summary_payload),
        "recommended_event": recommended_event,
        "decision": decision,
        "decision_reason": decision_reason,
        "pid_status": {
            "pid_file": str(Path(pid_file).resolve()),
            "pid_state": pid_state,
            "pid": pid_value,
            "pid_alive": pid_alive,
        },
        "inspected_at": now.isoformat(timespec="seconds"),
    }


def build_payload(
    execution_queue_payload: dict[str, Any],
    inspection: dict[str, Any],
    *,
    log_file: Path = DEFAULT_HEARTBEAT_LOG,
    last_action: str = "noop",
    auto_start_next: bool = False,
) -> dict[str, Any]:
    active = dict(inspection.get("active_row", {}) or {})
    ready = dict(inspection.get("next_ready_row", {}) or {})
    pid_status = dict(inspection.get("pid_status", {}) or {})

    rows: list[dict[str, Any]] = []
    if active:
        rows.append(
            {
                "row_kind": "active",
                **active,
                "decision": inspection.get("decision", ""),
                "decision_reason": inspection.get("decision_reason", ""),
                "recommended_event": inspection.get("recommended_event", ""),
                "signal_age_minutes": inspection.get("signal_age_minutes", 0.0),
                "heartbeat_count": inspection.get("heartbeat_count", 0),
                "runner_kind": inspection.get("runner_kind", ""),
                "supervision_only": inspection.get("supervision_only", False),
                "compute_pid": inspection.get("compute_pid", 0),
                "compute_pid_alive": inspection.get("compute_pid_alive", False),
                "compute_pid_path": inspection.get("compute_pid_path", ""),
                "throughput_summary_detected": inspection.get("throughput_summary_detected", False),
                "throughput_summary_json": inspection.get("throughput_summary_json", ""),
                "throughput_ok": inspection.get("throughput_ok", False),
                "throughput_failed": inspection.get("throughput_failed", False),
                "pid_state": pid_status.get("pid_state", ""),
                "pid": pid_status.get("pid", 0),
            }
        )
    if ready:
        rows.append(
            {
                "row_kind": "next_ready",
                **ready,
            }
        )

    summary = {
        "status": "wetlab_broad_screen_antitarget_watcher_state_ready",
        "last_action": last_action,
        "auto_start_next_enabled": auto_start_next,
        "watcher_decision": str(inspection.get("decision", "")).strip(),
        "decision_reason": str(inspection.get("decision_reason", "")).strip(),
        "recommended_event": str(inspection.get("recommended_event", "")).strip(),
        "active_primary_target_id": str(active.get("primary_target_id", "")).strip(),
        "active_anti_target_id": str(active.get("anti_target_id", "")).strip(),
        "active_shard_id": str(active.get("primary_shard_id", "")).strip(),
        "active_queue_status": str(active.get("queue_status", "")).strip(),
        "heartbeat_pid_path": str(pid_status.get("pid_file", "")).strip(),
        "heartbeat_pid": int(pid_status.get("pid", 0) or 0),
        "heartbeat_pid_alive": bool(pid_status.get("pid_alive", False)),
        "heartbeat_pid_state": str(pid_status.get("pid_state", "")).strip(),
        "signal_age_minutes": float(inspection.get("signal_age_minutes", 0.0) or 0.0),
        "heartbeat_count": int(inspection.get("heartbeat_count", 0) or 0),
        "runner_kind": str(inspection.get("runner_kind", "")).strip(),
        "supervision_only": bool(inspection.get("supervision_only", False)),
        "compute_pid": int(inspection.get("compute_pid", 0) or 0),
        "compute_pid_alive": bool(inspection.get("compute_pid_alive", False)),
        "compute_pid_path": str(inspection.get("compute_pid_path", "")).strip(),
        "throughput_summary_detected": bool(inspection.get("throughput_summary_detected", False)),
        "throughput_summary_json": str(inspection.get("throughput_summary_json", "")).strip(),
        "throughput_ok": bool(inspection.get("throughput_ok", False)),
        "throughput_failed": bool(inspection.get("throughput_failed", False)),
        "next_ready_primary_target_id": str(ready.get("primary_target_id", "")).strip(),
        "next_ready_anti_target_id": str(ready.get("anti_target_id", "")).strip(),
        "next_ready_shard_id": str(ready.get("primary_shard_id", "")).strip(),
        "heartbeat_log_path": str(Path(log_file).resolve()),
        "inspected_at": str(inspection.get("inspected_at", "")).strip(),
        "next_required_step": (
            f"Emit {inspection.get('recommended_event', '')} for {active.get('primary_target_id', '')} -> {active.get('anti_target_id', '')} {active.get('primary_shard_id', '')}."
            if inspection.get("recommended_event") and active
            else f"Keep monitoring the active compute-attached counterscreen row for {active.get('primary_target_id', '')} -> {active.get('anti_target_id', '')} {active.get('primary_shard_id', '')}; the watcher will auto-complete it from the throughput summary."
            if active and str(inspection.get("runner_kind", "")).strip() == "compute_attached"
            else f"Heartbeat-only supervision is active for {active.get('primary_target_id', '')} -> {active.get('anti_target_id', '')} {active.get('primary_shard_id', '')}; the watcher will auto-complete it after a short pulse budget."
            if active and bool(inspection.get("supervision_only", False))
            else f"Auto-start {ready.get('primary_target_id', '')} -> {ready.get('anti_target_id', '')} {ready.get('primary_shard_id', '')} when you want counterscreen supervision to keep moving."
            if inspection.get("decision") == "auto_start_next" and ready
            else "Keep monitoring the active counterscreen row."
            if active
            else "No active counterscreen row is running; wait for auto-start or dispatch the next ready row."
        ),
    }
    return {
        "summary": summary,
        "structured": {
            "execution_queue_artifact": "runs/wetlab_broad_screen_antitarget_execution_queue_current.md",
            "heartbeat_log_path": str(Path(log_file).resolve()),
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build watcher state for the active anti-target counterscreen row.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--heartbeat-pid-path", default=str(DEFAULT_HEARTBEAT_PID))
    parser.add_argument("--heartbeat-log-path", default=str(DEFAULT_HEARTBEAT_LOG))
    parser.add_argument("--stale-minutes", type=float, default=20.0)
    parser.add_argument("--supervision-max-heartbeats", type=int, default=DEFAULT_SUPERVISION_MAX_HEARTBEATS)
    parser.add_argument("--last-action", default="noop")
    parser.add_argument("--auto-start-next", action="store_true")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    queue = load_json(args.execution_queue_json)
    inspection = inspect_state(
        queue,
        pid_file=Path(args.heartbeat_pid_path),
        stale_minutes=args.stale_minutes,
        supervision_max_heartbeats=args.supervision_max_heartbeats,
    )
    payload = build_payload(
        queue,
        inspection,
        log_file=Path(args.heartbeat_log_path),
        last_action=args.last_action,
        auto_start_next=args.auto_start_next,
    )
    write_artifact(args.out_md, "Wet-Lab Broad Screen Anti-Target Watcher State", payload)
