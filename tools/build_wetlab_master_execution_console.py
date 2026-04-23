#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_MASTER_QUEUE_JSON = "runs/wetlab_master_execution_queue_current.json"
DEFAULT_PRIORITY3_CONSOLE_JSON = "runs/wetlab_priority3_execution_console_current.json"
DEFAULT_NEXT3_CONSOLE_JSON = "runs/wetlab_next3_execution_console_current.json"
DEFAULT_FINAL2_CONSOLE_JSON = "runs/wetlab_final2_execution_console_current.json"
DEFAULT_WAVE2_CONSOLE_JSON = "runs/wetlab_wave2_execution_console_current.json"
DEFAULT_NEXT3_CHAIN_STACK_JSON = "runs/wetlab_next3_chain_stack_current.json"
DEFAULT_FINAL2_CHAIN_STACK_JSON = "runs/wetlab_final2_chain_stack_current.json"
DEFAULT_WAVE2_CHAIN_STACK_JSON = "runs/wetlab_wave2_chain_stack_current.json"
DEFAULT_MASTER_RUNBOOK_JSON = "runs/wetlab_master_runtime_runbook_current.json"
DEFAULT_OUT_MD = "runs/wetlab_master_execution_console_current.md"


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def build_payload(
    master_queue: dict[str, Any],
    priority3_console: dict[str, Any],
    next3_console: dict[str, Any],
    final2_console: dict[str, Any],
    next3_chain_stack: dict[str, Any],
    final2_chain_stack: dict[str, Any],
    master_runbook: dict[str, Any],
    wave2_console: dict[str, Any] | None = None,
    wave2_chain_stack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mqs = _summary(master_queue)
    p3s = _summary(priority3_console)
    n3s = _summary(next3_console)
    f2s = _summary(final2_console)
    w2s = _summary(wave2_console or {})
    n3cs = _summary(next3_chain_stack)
    f2cs = _summary(final2_chain_stack)
    w2cs = _summary(wave2_chain_stack or {})
    mrs = _summary(master_runbook)
    active_chain = str(mqs.get("active_stack_level", "")).strip()
    active_target = str(mqs.get("active_target_id", "")).strip()
    active_queue_status = str(mqs.get("active_target_queue_status", "")).strip()
    active_execution_state = str(mqs.get("active_target_execution_state", "")).strip()
    stack_gate_states = dict(mqs.get("stack_gate_states", {}) or {})
    lbdhodh_blockers = dict(f2cs.get("lbdhodh_blockers", {}) or mqs.get("lbdhodh_blockers", {}) or {})
    rows = [
        {"chain_id": "priority3", "console_artifact": "runs/wetlab_priority3_execution_console_current.md", "ready_now_target_count": int(p3s.get("ready_now_target_count", 0) or 0), "blocked_on_previous_review_count": int(p3s.get("blocked_on_previous_review_count", 0) or 0), "running_target_count": int(p3s.get("running_target_count", 0) or 0), "last_runtime_target": str(p3s.get("last_runtime_target", "")).strip(), "last_runtime_event": str(p3s.get("last_runtime_event", "")).strip()},
        {"chain_id": "next3", "console_artifact": "runs/wetlab_next3_execution_console_current.md", "ready_now_target_count": int(n3s.get("ready_now_target_count", 0) or 0), "blocked_on_previous_review_count": int(n3s.get("blocked_on_previous_review_count", 0) or 0), "running_target_count": int(n3s.get("running_target_count", 0) or 0), "last_runtime_target": str(n3s.get("last_runtime_target", "")).strip(), "last_runtime_event": str(n3s.get("last_runtime_event", "")).strip()},
        {"chain_id": "final2", "console_artifact": "runs/wetlab_final2_execution_console_current.md", "ready_now_target_count": int(f2s.get("ready_now_target_count", 0) or 0), "blocked_on_previous_review_count": int(f2s.get("blocked_on_previous_review_count", 0) or 0), "running_target_count": int(f2s.get("running_target_count", 0) or 0), "last_runtime_target": str(f2s.get("last_runtime_target", "")).strip(), "last_runtime_event": str(f2s.get("last_runtime_event", "")).strip()},
        {"chain_id": "wave2", "console_artifact": "runs/wetlab_wave2_execution_console_current.md", "ready_now_target_count": int(w2s.get("ready_now_target_count", 0) or 0), "blocked_on_previous_review_count": int(w2s.get("blocked_on_previous_review_count", 0) or 0), "running_target_count": int(w2s.get("running_target_count", 0) or 0), "last_runtime_target": str(w2s.get("last_runtime_target", "")).strip(), "last_runtime_event": str(w2s.get("last_runtime_event", "")).strip()},
    ]
    if wave2_console is None:
        rows = rows[:-1]
    return {
        "summary": {
            "status": "wetlab_master_execution_console_ready",
            "chain_count": 4 if wave2_console is not None else 3,
            "queue_target_count": int(mqs.get("queue_target_count", 0) or 0),
            "ready_now_target_count": int(mqs.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(mqs.get("blocked_on_previous_review_count", 0) or 0),
            "blocked_on_target_content_count": int(mqs.get("blocked_on_target_content_count", 0) or 0),
            "running_target_count": int(mqs.get("running_target_count", 0) or 0),
            "resolved_target_count": int(mqs.get("resolved_target_count", 0) or 0),
            "active_stack_level": active_chain,
            "active_target_id": active_target,
            "active_target_queue_status": active_queue_status,
            "active_target_execution_state": active_execution_state,
            "stack_gate_states": stack_gate_states,
            "lbdhodh_blockers": lbdhodh_blockers,
            "wave2_release_gate_status": str(mqs.get("wave2_release_gate_status", "")).strip(),
            "wave2_release_blocked": bool(mqs.get("wave2_release_blocked", True)),
            "wave2_ready": bool(mqs.get("wave2_ready", False)),
            "wave2_queue_status": str(mqs.get("wave2_queue_status", "")).strip(),
            "first_actionable_target": str(mqs.get("first_actionable_target", "")).strip(),
            "first_actionable_chain": str(mqs.get("first_actionable_chain", "")).strip(),
            "next3_gate_open": bool(n3cs.get("priority3_final_gate_open", False)),
            "final2_gate_open": bool(f2cs.get("next3_final_gate_open", False)),
            "wave2_gate_open": bool(w2cs.get("final2_final_gate_open", False)),
            "lbdhodh_stk17b_gate_state": str(f2cs.get("rows", [{}])[0].get("current_signal", "")).strip() if isinstance(f2cs.get("rows"), list) else "",
            "lbdhodh_queue_status_now": str(f2cs.get("lbdhodh_queue_status", "")).strip() or ("blocked_on_target_content" if bool(f2cs.get("next3_final_gate_open", False)) and not bool(f2cs.get("lbdhodh_content_ready", False)) else "blocked_on_previous_review" if not bool(f2cs.get("next3_final_gate_open", False)) else ""),
            "lbdhodh_launch_readiness": "ready_for_serialized_execution" if bool(f2cs.get("lbdhodh_content_ready", False)) else "blocked_on_compound_fill",
            "lbdhodh_content_ready": bool(f2cs.get("lbdhodh_content_ready", False)),
            "lbdhodh_blockers": lbdhodh_blockers,
            "master_runbook_status": str(mrs.get("status", "")).strip(),
            "next_required_step": str(mqs.get("next_required_step", "")).strip() or "Follow the first actionable target from the master queue.",
        },
        "structured": {
            "master_queue_artifact": "runs/wetlab_master_execution_queue_current.md",
            "master_runbook_artifact": "runs/wetlab_master_runtime_runbook_current.md",
            "next3_chain_stack_artifact": "runs/wetlab_next3_chain_stack_current.md",
            "final2_chain_stack_artifact": "runs/wetlab_final2_chain_stack_current.md",
            "wave2_chain_stack_artifact": "runs/wetlab_wave2_chain_stack_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the master execution console across all serialized wet-lab chains.")
    parser.add_argument("--master-queue-json", default=DEFAULT_MASTER_QUEUE_JSON)
    parser.add_argument("--priority3-console-json", default=DEFAULT_PRIORITY3_CONSOLE_JSON)
    parser.add_argument("--next3-console-json", default=DEFAULT_NEXT3_CONSOLE_JSON)
    parser.add_argument("--final2-console-json", default=DEFAULT_FINAL2_CONSOLE_JSON)
    parser.add_argument("--wave2-console-json", default=DEFAULT_WAVE2_CONSOLE_JSON)
    parser.add_argument("--next3-chain-stack-json", default=DEFAULT_NEXT3_CHAIN_STACK_JSON)
    parser.add_argument("--final2-chain-stack-json", default=DEFAULT_FINAL2_CHAIN_STACK_JSON)
    parser.add_argument("--wave2-chain-stack-json", default=DEFAULT_WAVE2_CHAIN_STACK_JSON)
    parser.add_argument("--master-runbook-json", default=DEFAULT_MASTER_RUNBOOK_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.master_queue_json),
        load_json(args.priority3_console_json),
        load_json(args.next3_console_json),
        load_json(args.final2_console_json),
        load_json(args.next3_chain_stack_json),
        load_json(args.final2_chain_stack_json),
        load_json(args.master_runbook_json),
        load_json(args.wave2_console_json),
        load_json(args.wave2_chain_stack_json),
    )
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Master Execution Console", payload)


if __name__ == "__main__":
    main()
