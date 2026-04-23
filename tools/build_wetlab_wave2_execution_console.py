#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_QUEUE_JSON = "runs/wetlab_wave2_protein_run_queue_current.json"
DEFAULT_CHAIN_STACK_JSON = "runs/wetlab_wave2_chain_stack_current.json"
DEFAULT_RUNTIME_EVENT_JSON = "runs/wetlab_wave2_runtime_event_current.json"
DEFAULT_RUNTIME_RUNBOOK_JSON = "runs/wetlab_wave2_runtime_runbook_current.json"
DEFAULT_EVENT_LOG = "runs/wetlab_wave2_runtime_event_log.jsonl"
DEFAULT_OUT_MD = "runs/wetlab_wave2_execution_console_current.md"


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


def build_payload(queue_payload: dict[str, Any], chain_stack: dict[str, Any], runtime_event_payload: dict[str, Any] | None, runbook_payload: dict[str, Any] | None, recent_events: list[dict[str, Any]]) -> dict[str, Any]:
    qs = dict(queue_payload.get("summary", {}) or {})
    cs = dict(chain_stack.get("summary", {}) or {})
    es = dict((runtime_event_payload or {}).get("summary", {}) or {})
    rs = dict((runbook_payload or {}).get("summary", {}) or {})
    rows = [dict(row) | {"console_role": "serialized_queue_status"} for row in queue_payload.get("rows", []) or []]
    for event in recent_events:
        rows.append({"console_role": "recent_runtime_event", "target_id": event.get("target_id", ""), "queue_status": event.get("queue_status_now", ""), "detail": f"{event.get('event','')} @ {event.get('event_timestamp','')}"})
    return {
        "summary": {
            "status": "wetlab_wave2_execution_console_ready",
            "queue_target_count": int(qs.get("queue_target_count", 0) or 0),
            "ready_now_target_count": int(qs.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(qs.get("blocked_on_previous_review_count", 0) or 0),
            "blocked_on_target_content_count": int(qs.get("blocked_on_target_content_count", 0) or 0),
            "running_target_count": int(qs.get("running_target_count", 0) or 0),
            "resolved_target_count": int(qs.get("resolved_target_count", 0) or 0),
            "final2_final_gate_open": bool(cs.get("final2_final_gate_open", False)),
            "last_runtime_target": str(es.get("target_id", "")).strip() or "none",
            "last_runtime_event": str(es.get("event", "")).strip() or "none",
            "recent_runtime_event_count": len(recent_events),
            "next_required_step": str(qs.get("next_required_step", "")).strip()
            or "Use the queue summary as the active Wave 2 execution guide.",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Wave 2 execution console.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--chain-stack-json", default=DEFAULT_CHAIN_STACK_JSON)
    parser.add_argument("--runtime-event-json", default=DEFAULT_RUNTIME_EVENT_JSON)
    parser.add_argument("--runbook-json", default=DEFAULT_RUNTIME_RUNBOOK_JSON)
    parser.add_argument("--event-log", default=DEFAULT_EVENT_LOG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.queue_json), load_json(args.chain_stack_json), maybe_load_json(args.runtime_event_json), maybe_load_json(args.runbook_json), _recent_events(args.event_log))
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Wave2 Execution Console", payload)


if __name__ == "__main__":
    main()
