#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import first_unresolved_row, load_json, maybe_load_json, queue_status_to_execution_state, write_artifact

DEFAULT_QUEUE_JSON = "runs/wetlab_final2_protein_run_queue_current.json"
DEFAULT_REFRESH_JSON = "runs/wetlab_final2_gate_refresh_current.json"
DEFAULT_RUNTIME_EVENT_JSON = "runs/wetlab_final2_runtime_event_current.json"
DEFAULT_RUNBOOK_JSON = "runs/wetlab_final2_runtime_runbook_current.json"
DEFAULT_CHAIN_STACK_JSON = "runs/wetlab_final2_chain_stack_current.json"
DEFAULT_EVENT_LOG = "runs/wetlab_final2_runtime_event_log.jsonl"
DEFAULT_OUT_MD = "runs/wetlab_final2_execution_console_current.md"


def _recent_events(path_like: str) -> list[dict[str, Any]]:
    path = Path(path_like)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[-5:]:
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def build_payload(
    queue_payload: dict,
    refresh_payload: dict,
    runtime_event_payload: dict,
    runbook_payload: dict,
    recent_events: list[dict[str, Any]],
    chain_stack_payload: dict | None = None,
) -> dict:
    qs = dict(queue_payload.get("summary", {}) or {})
    rs = dict(refresh_payload.get("summary", {}) or {})
    es = dict(runtime_event_payload.get("summary", {}) or {})
    bs = dict(runbook_payload.get("summary", {}) or {})
    cs = dict((chain_stack_payload or queue_payload.get("chain_stack", {}) or {}).get("summary", {}) or {})

    rows = []
    for row in queue_payload.get("rows", []) or []:
        out = dict(row)
        out["console_role"] = "serialized_queue_status"
        rows.append(out)
    rows.append({
        "console_role": "gate_refresh_status",
        "target_id": "final2_gate_refresh",
        "queue_status": str(rs.get("status", "")).strip(),
        "detail": f"steps={rs.get('step_count', 0)}",
    })
    rows.append({
        "console_role": "runtime_event_status",
        "target_id": str(es.get("target_id", "")).strip() or "none",
        "queue_status": str(es.get("queue_status_now", "")).strip() or str(es.get("status", "")).strip(),
        "detail": str(es.get("event", "")).strip() or "none",
    })
    rows.append({
        "console_role": "runbook_status",
        "target_id": "final2_runbook",
        "queue_status": str(bs.get("status", "")).strip(),
        "detail": f"commands={bs.get('command_row_count', 0)}",
    })
    for event in recent_events:
        rows.append({
            "console_role": "recent_runtime_event",
            "target_id": event.get("target_id", ""),
            "queue_status": event.get("queue_status_now", ""),
            "detail": f"{event.get('event', '')} @ {event.get('event_timestamp', '')}",
        })

    queue_rows = [dict(row) for row in queue_payload.get("rows", []) or []]
    active_row = first_unresolved_row(queue_rows)
    stack_gate_states = dict(cs.get("stack_gate_states", {}) or {})
    if not stack_gate_states:
        stk17b_row = next((dict(row) for row in queue_rows if str(row.get("target_id", "")).strip() == "STK17B (DRAK2)"), {})
        lbdhodh_row = next((dict(row) for row in queue_rows if str(row.get("target_id", "")).strip() == "Leishmania braziliensis DHODH"), {})
        stack_gate_states = {
            "stk17b": {
                "target_id": "STK17B (DRAK2)",
                "queue_status": str(stk17b_row.get("queue_status", "")).strip(),
                "execution_state": queue_status_to_execution_state(stk17b_row.get("queue_status", "")),
            },
            "lbdhodh": {
                "target_id": "Leishmania braziliensis DHODH",
                "queue_status": str(lbdhodh_row.get("queue_status", "")).strip(),
                "execution_state": queue_status_to_execution_state(lbdhodh_row.get("queue_status", "")),
            },
        }
    lbdhodh_blockers = dict(cs.get("lbdhodh_blockers", {}) or {})
    if not lbdhodh_blockers:
        lbdhodh_row_state = stack_gate_states.get("lbdhodh", {})
        lbdhodh_blockers = {
            "upstream_stk17b_result_review": "blocked"
            if str(stack_gate_states.get("stk17b", {}).get("queue_status", "")).strip() == "blocked_on_previous_review"
            else "clear",
            "compound_fill": "blocked"
            if str(lbdhodh_row_state.get("queue_status", "")).strip() == "blocked_on_target_content"
            else "clear",
        }

    return {
        "summary": {
            "status": "wetlab_final2_execution_console_ready",
            "queue_target_count": int(qs.get("queue_target_count", 0) or 0),
            "active_stack_level": "final2",
            "active_target_id": str(active_row.get("target_id", "")).strip() if active_row else "",
            "active_target_queue_status": str(active_row.get("queue_status", "")).strip() if active_row else "",
            "active_target_execution_state": queue_status_to_execution_state(active_row.get("queue_status", "")) if active_row else "",
            "stack_gate_states": stack_gate_states,
            "lbdhodh_blockers": lbdhodh_blockers,
            "ready_now_target_count": int(qs.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(qs.get("blocked_on_previous_review_count", 0) or 0),
            "blocked_on_target_content_count": int(qs.get("blocked_on_target_content_count", 0) or 0),
            "running_target_count": int(qs.get("running_target_count", 0) or 0),
            "resolved_target_count": int(qs.get("resolved_target_count", 0) or 0),
            "last_runtime_target": str(es.get("target_id", "")).strip() or "none",
            "last_runtime_event": str(es.get("event", "")).strip() or "none",
            "recent_runtime_event_count": len(recent_events),
            "next_required_step": "Use this console after every final2 runtime event to confirm the serialized tail state remains honest.",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the final2 execution console.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--refresh-json", default=DEFAULT_REFRESH_JSON)
    parser.add_argument("--runtime-event-json", default=DEFAULT_RUNTIME_EVENT_JSON)
    parser.add_argument("--runbook-json", default=DEFAULT_RUNBOOK_JSON)
    parser.add_argument("--chain-stack-json", default=DEFAULT_CHAIN_STACK_JSON)
    parser.add_argument("--event-log", default=DEFAULT_EVENT_LOG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queue_payload = load_json(args.queue_json)
    payload = build_payload(queue_payload, maybe_load_json(args.refresh_json), maybe_load_json(args.runtime_event_json), maybe_load_json(args.runbook_json), _recent_events(args.event_log), maybe_load_json(args.chain_stack_json))
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Final2 Execution Console", payload)


if __name__ == "__main__":
    main()
