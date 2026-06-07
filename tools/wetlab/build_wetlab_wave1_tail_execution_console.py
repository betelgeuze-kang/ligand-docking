#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_QUEUE_JSON = "runs/wetlab_wave1_tail_protein_run_queue_current.json"
DEFAULT_REFRESH_JSON = "runs/wetlab_wave1_tail_gate_refresh_current.json"
DEFAULT_RUNTIME_EVENT_JSON = "runs/wetlab_wave1_tail_runtime_event_current.json"
DEFAULT_RUNTIME_RUNBOOK_JSON = "runs/wetlab_wave1_tail_runtime_runbook_current.json"
DEFAULT_EVENT_LOG = "runs/wetlab_wave1_tail_runtime_event_log.jsonl"
DEFAULT_OUT_MD = "runs/wetlab_wave1_tail_execution_console_current.md"


def _load_event_log_rows(path_like: str, limit: int = 6) -> list[dict[str, Any]]:
    path = Path(path_like)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        rows.append(dict(json.loads(text)))
    return rows[-limit:]


def build_payload(
    queue_payload: dict[str, Any],
    refresh_payload: dict[str, Any],
    runtime_event_payload: dict[str, Any] | None = None,
    runtime_runbook_payload: dict[str, Any] | None = None,
    event_log_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    queue_s = dict(queue_payload.get("summary", {}) or {})
    refresh_s = dict(refresh_payload.get("summary", {}) or {})
    runtime_s = dict((runtime_event_payload or {}).get("summary", {}) or {})
    runbook_s = dict((runtime_runbook_payload or {}).get("summary", {}) or {})
    log_rows = list(event_log_rows or [])

    rows: list[dict[str, Any]] = []
    for row in queue_payload.get("rows", []) or []:
        item = dict(row)
        item["console_role"] = "serialized_queue_status"
        rows.append(item)

    for log_row in log_rows:
        rows.append(
            {
                "queue_order": "",
                "target_id": str(log_row.get("target_id", "")).strip(),
                "launch_packet_artifact": "",
                "transition_artifact": "",
                "partner_track_id": "",
                "transition_status": str(log_row.get("gate_status", "")).strip(),
                "queue_status": str(log_row.get("queue_status_now", "")).strip(),
                "advance_gate": str(log_row.get("event", "")).strip(),
                "parallel_lane_artifact": str(log_row.get("event_timestamp", "")).strip(),
                "console_role": "recent_runtime_event",
            }
        )

    return {
        "summary": {
            "status": "wetlab_wave1_tail_execution_console_ready",
            "queue_target_count": int(queue_s.get("queue_target_count", 0) or 0),
            "ready_now_target_count": int(queue_s.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(queue_s.get("blocked_on_previous_review_count", 0) or 0),
            "running_target_count": int(queue_s.get("running_target_count", 0) or 0),
            "resolved_target_count": int(queue_s.get("resolved_target_count", 0) or 0),
            "refresh_status": str(refresh_s.get("status", "")).strip(),
            "runtime_event_status": str(runtime_s.get("status", "")).strip() or "not_present",
            "runtime_runbook_status": str(runbook_s.get("status", "")).strip() or "not_present",
            "stk17b_execution_state": str(refresh_s.get("stk17b_execution_state", "")).strip(),
            "lbdhodh_review_state": str(refresh_s.get("lbdhodh_review_state", "")).strip(),
            "recent_runtime_event_count": len(log_rows),
            "last_runtime_target": str(log_rows[-1].get("target_id", "")).strip() if log_rows else "",
            "last_runtime_event": str(log_rows[-1].get("event", "")).strip() if log_rows else "",
            "last_runtime_timestamp": str(log_rows[-1].get("event_timestamp", "")).strip() if log_rows else "",
            "next_required_step": "If STK17B is still only blocked_on_previous_review, finish next3 first. Otherwise follow the latest gate state shown here and only advance LbDHODH when the upstream STK17B result is resolved.",
        },
        "structured": {
            "queue_artifact": "runs/wetlab_wave1_tail_protein_run_queue_current.md",
            "refresh_artifact": "runs/wetlab_wave1_tail_gate_refresh_current.md",
            "runtime_event_artifact": "runs/wetlab_wave1_tail_runtime_event_current.md",
            "runtime_runbook_artifact": "runs/wetlab_wave1_tail_runtime_runbook_current.md",
            "event_log_path": DEFAULT_EVENT_LOG,
        },
        "rows": rows,
    }


def main() -> None:
    payload = build_payload(
        load_json(DEFAULT_QUEUE_JSON),
        load_json(DEFAULT_REFRESH_JSON),
        maybe_load_json(DEFAULT_RUNTIME_EVENT_JSON),
        maybe_load_json(DEFAULT_RUNTIME_RUNBOOK_JSON),
        _load_event_log_rows(DEFAULT_EVENT_LOG),
    )
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Wave1 Tail Execution Console", payload)


if __name__ == "__main__":
    main()
