#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from typing import Any

from tools import run_wetlab_final2_runtime_event as final2_runner
from tools import run_wetlab_next3_runtime_event as next3_runner
from tools import run_wetlab_priority3_runtime_event as priority3_runner
from tools import run_wetlab_wave2_runtime_event as wave2_runner
from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_MASTER_QUEUE_JSON = "runs/wetlab_master_execution_queue_current.json"
DEFAULT_MASTER_RUNBOOK_JSON = "runs/wetlab_master_runtime_runbook_current.json"
DEFAULT_MASTER_CONSOLE_JSON = "runs/wetlab_master_execution_console_current.json"
DEFAULT_OUT_MD = "runs/wetlab_master_runtime_event_current.md"

CHAIN_RUNNERS: dict[str, dict[str, Any]] = {
    "priority3": {
        "runner_module": priority3_runner,
        "runner_script": "tools/run_wetlab_priority3_runtime_event.py",
    },
    "next3": {
        "runner_module": next3_runner,
        "runner_script": "tools/run_wetlab_next3_runtime_event.py",
    },
    "final2": {
        "runner_module": final2_runner,
        "runner_script": "tools/run_wetlab_final2_runtime_event.py",
    },
    "wave2": {
        "runner_module": wave2_runner,
        "runner_script": "tools/run_wetlab_wave2_runtime_event.py",
    },
}


def _event_module(runner_module: Any) -> Any:
    module = getattr(runner_module, "runtime_event_mod", None)
    if module is not None:
        return module
    module = getattr(runner_module, "event_mod", None)
    if module is not None:
        return module
    raise AttributeError(f"{runner_module!r} does not expose a runtime event module.")


def _build_target_registry() -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for chain_id, chain_meta in CHAIN_RUNNERS.items():
        runner_module = chain_meta["runner_module"]
        event_module = _event_module(runner_module)
        target_registry = getattr(event_module, "TARGETS", None)
        if not target_registry:
            target_registry = {
                target_key: {"target_id": target_id}
                for target_key, target_id in getattr(runner_module, "TARGETS", {}).items()
            }
        for target_key, target_meta in target_registry.items():
            targets[target_key] = {
                "target_key": target_key,
                "target_id": str(target_meta["target_id"]).strip(),
                "chain_id": chain_id,
                "runner_module": runner_module,
                "runner_script": chain_meta["runner_script"],
                "runtime_event_artifact": str(getattr(event_module, "DEFAULT_OUT_MD", "")).strip(),
                "chain_log_path": str(runner_module.DEFAULT_LOG_PATH),
            }
    return targets


TARGETS = _build_target_registry()
EVENTS = set().union(
    priority3_runner.runtime_event_mod.EVENTS,
    next3_runner.runtime_event_mod.EVENTS,
    final2_runner.runtime_event_mod.EVENTS,
    getattr(_event_module(wave2_runner), "EVENTS", {"reset", "start", "heartbeat", "complete", "hold"}),
)


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def _queue_row_for_target(master_queue_payload: dict[str, Any], target_id: str) -> dict[str, Any]:
    for row in master_queue_payload.get("rows", []) or []:
        if str(row.get("target_id", "")).strip() == target_id:
            return dict(row)
    raise ValueError(f"Target {target_id!r} is missing from the master execution queue payload.")


def _queue_status(row: dict[str, Any]) -> str:
    return str(row.get("queue_status", "")).strip()


def _is_blocked(queue_status: str) -> bool:
    return not queue_status or queue_status.startswith("blocked_on")


def _dispatch_allowed(event: str, queue_status: str) -> bool:
    if event == "reset":
        return True
    return not _is_blocked(queue_status)


def apply_runtime_event(
    *,
    target_key: str,
    event: str,
    python_bin: str,
    active_stage_label: str = "",
    decision_case: str = "",
    action: str = "",
    started_at: str = "",
    updated_at: str = "",
    completed_at: str = "",
    notes: str = "",
    master_queue_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = TARGETS[target_key]
    master_queue = master_queue_payload if master_queue_payload is not None else load_json(DEFAULT_MASTER_QUEUE_JSON)
    queue_row = _queue_row_for_target(master_queue, target["target_id"])
    queue_status_before = _queue_status(queue_row)
    blocked_before = _is_blocked(queue_status_before)

    result: dict[str, Any] = {
        "target_key": target_key,
        "target_id": target["target_id"],
        "chain_id": target["chain_id"],
        "event": event,
        "runner_script": target["runner_script"],
        "transition_artifact": str(queue_row.get("transition_artifact", "")).strip(),
        "advance_gate": str(queue_row.get("advance_gate", "")).strip(),
        "target_queue_status_before": queue_status_before or "unknown_master_queue_status",
        "target_blocked_before": blocked_before,
        "chain_runtime_event_artifact": target["runtime_event_artifact"],
        "chain_log_path": target["chain_log_path"],
    }

    if not _dispatch_allowed(event, queue_status_before):
        result.update(
            {
                "dispatch_status": "blocked_target",
                "chain_event_applied": False,
                "blocked_reason": str(queue_row.get("advance_gate", "")).strip() or "Resolve the upstream gate before dispatching this target.",
                "chain_queue_status_now": queue_status_before,
                "gate_status": str(queue_row.get("transition_status", "")).strip(),
                "chain_execution_state": "",
                "gate_execution_state": "",
            }
        )
        return result

    chain_row = target["runner_module"].apply_and_log_event(
        target=target_key,
        event=event,
        python_bin=python_bin,
        active_stage_label=active_stage_label,
        decision_case=decision_case,
        action=action,
        started_at=started_at,
        updated_at=updated_at,
        completed_at=completed_at,
        notes=notes,
    )
    result.update(
        {
            "dispatch_status": "dispatched_to_chain_runner",
            "chain_event_applied": True,
            "blocked_reason": "",
            "chain_queue_status_now": str(chain_row.get("queue_status_now", "")).strip(),
            "gate_status": str(chain_row.get("gate_status", "")).strip(),
            "chain_execution_state": str(chain_row.get("execution_state", "")).strip(),
            "gate_execution_state": str(chain_row.get("gate_execution_state", "")).strip(),
        }
    )
    return result


def build_payload(
    event_result: dict[str, Any],
    master_queue_payload: dict[str, Any],
    master_runbook_payload: dict[str, Any],
    master_console_payload: dict[str, Any],
) -> dict[str, Any]:
    queue_summary = _summary(master_queue_payload)
    runbook_summary = _summary(master_runbook_payload)
    console_summary = _summary(master_console_payload)
    queue_row_after = _queue_row_for_target(master_queue_payload, str(event_result.get("target_id", "")).strip())
    queue_status_after = _queue_status(queue_row_after)
    blocked_after = _is_blocked(queue_status_after)
    blocked_dispatch = str(event_result.get("dispatch_status", "")).strip() == "blocked_target"

    if blocked_dispatch:
        next_required_step = (
            f"Do not dispatch {event_result['target_id']} while it is {queue_status_after or event_result['target_queue_status_before']}. "
            f"{str(event_result.get('blocked_reason', '')).strip() or str(queue_summary.get('next_required_step', '')).strip()}"
        ).strip()
        status = "wetlab_master_runtime_event_blocked"
    else:
        next_required_step = str(queue_summary.get("next_required_step", "")).strip() or "Follow the refreshed master queue."
        status = "wetlab_master_runtime_event_applied"

    rows = [
        {
            "record_kind": "dispatch_request",
            "artifact_path": str(event_result.get("runner_script", "")).strip(),
            "status": str(event_result.get("dispatch_status", "")).strip(),
            "detail": f"{event_result['event']} -> {event_result['target_id']} ({event_result['chain_id']})",
        },
        {
            "record_kind": "target_queue_before",
            "artifact_path": str(event_result.get("transition_artifact", "")).strip(),
            "status": str(event_result.get("target_queue_status_before", "")).strip(),
            "detail": str(event_result.get("advance_gate", "")).strip(),
        },
        {
            "record_kind": "target_queue_after",
            "artifact_path": str(queue_row_after.get("transition_artifact", "")).strip(),
            "status": queue_status_after,
            "detail": str(event_result.get("gate_status", "")).strip() or str(event_result.get("blocked_reason", "")).strip() or str(queue_row_after.get("advance_gate", "")).strip(),
        },
        {
            "record_kind": "master_console",
            "artifact_path": "runs/wetlab_master_execution_console_current.md",
            "status": str(console_summary.get("status", "")).strip(),
            "detail": (
                f"first_actionable={str(queue_summary.get('first_actionable_target', '')).strip() or 'none'}"
                f" ({str(queue_summary.get('first_actionable_chain', '')).strip() or 'n/a'})"
            ),
        },
    ]

    return {
        "summary": {
            "status": status,
            "target_key": str(event_result.get("target_key", "")).strip(),
            "target_id": str(event_result.get("target_id", "")).strip(),
            "chain_id": str(event_result.get("chain_id", "")).strip(),
            "event": str(event_result.get("event", "")).strip(),
            "dispatch_status": str(event_result.get("dispatch_status", "")).strip(),
            "chain_event_applied": bool(event_result.get("chain_event_applied", False)),
            "target_queue_status_before": str(event_result.get("target_queue_status_before", "")).strip(),
            "target_queue_status_after": queue_status_after,
            "target_blocked_before": bool(event_result.get("target_blocked_before", False)),
            "target_blocked_after": blocked_after,
            "first_actionable_target": str(queue_summary.get("first_actionable_target", "")).strip(),
            "first_actionable_chain": str(queue_summary.get("first_actionable_chain", "")).strip(),
            "master_runbook_status": str(runbook_summary.get("status", "")).strip(),
            "master_console_status": str(console_summary.get("status", "")).strip(),
            "gate_status": str(event_result.get("gate_status", "")).strip(),
            "chain_execution_state": str(event_result.get("chain_execution_state", "")).strip(),
            "gate_execution_state": str(event_result.get("gate_execution_state", "")).strip(),
            "next_required_step": next_required_step,
        },
        "structured": {
            "master_queue_artifact": "runs/wetlab_master_execution_queue_current.md",
            "master_runbook_artifact": "runs/wetlab_master_runtime_runbook_current.md",
            "master_console_artifact": "runs/wetlab_master_execution_console_current.md",
            "chain_runtime_event_artifact": str(event_result.get("chain_runtime_event_artifact", "")).strip(),
            "chain_log_path": str(event_result.get("chain_log_path", "")).strip(),
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch a wet-lab runtime event through the master serialized chain view.")
    parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    parser.add_argument("--event", choices=sorted(EVENTS), required=True)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--active-stage-label", default="")
    parser.add_argument("--decision-case", default="")
    parser.add_argument("--action", default="")
    parser.add_argument("--started-at", default="")
    parser.add_argument("--updated-at", default="")
    parser.add_argument("--completed-at", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--master-queue-json", default=DEFAULT_MASTER_QUEUE_JSON)
    parser.add_argument("--master-runbook-json", default=DEFAULT_MASTER_RUNBOOK_JSON)
    parser.add_argument("--master-console-json", default=DEFAULT_MASTER_CONSOLE_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    event_result = apply_runtime_event(
        target_key=args.target,
        event=args.event,
        python_bin=args.python_bin,
        active_stage_label=args.active_stage_label,
        decision_case=args.decision_case,
        action=args.action,
        started_at=args.started_at,
        updated_at=args.updated_at,
        completed_at=args.completed_at,
        notes=args.notes,
        master_queue_payload=load_json(args.master_queue_json),
    )
    payload = build_payload(
        event_result,
        load_json(args.master_queue_json),
        load_json(args.master_runbook_json),
        load_json(args.master_console_json),
    )
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Master Runtime Event", payload)


if __name__ == "__main__":
    main()
