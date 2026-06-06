#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_MD = "runs/wetlab_final2_runtime_event_current.md"

TARGETS: dict[str, dict[str, str]] = {
    "stk17b": {
        "target_id": "STK17B (DRAK2)",
        "progress_builder": "tools/build_stk17b_live_progress.py",
        "result_builder": "tools/build_stk17b_result_summary.py",
        "run_record_json": "runs/stk17b_run_record_current.json",
        "gate_json": "runs/stk17b_run_status_current.json",
    },
    "lbdhodh": {
        "target_id": "Leishmania braziliensis DHODH",
        "progress_builder": "tools/build_lbdhodh_live_progress.py",
        "result_builder": "tools/build_lbdhodh_result_summary.py",
        "run_record_json": "runs/lbdhodh_run_record_current.json",
        "gate_json": "runs/lbdhodh_result_review_current.json",
    },
}

EVENTS = {"reset", "start", "heartbeat", "complete", "hold"}


def _summary(path_like: str) -> dict[str, Any]:
    return dict(load_json(path_like).get("summary", {}) or {})


def _run(cmd: list[str], python_bin: str) -> None:
    subprocess.run([python_bin, *cmd], cwd=ROOT, check=True)


def apply_runtime_event(*, target_key: str, event: str, python_bin: str, active_stage_label: str = "", decision_case: str = "", action: str = "", started_at: str = "", updated_at: str = "", completed_at: str = "", notes: str = "") -> dict[str, Any]:
    target = TARGETS[target_key]
    progress_cmd = [target["progress_builder"]]
    result_cmd = [target["result_builder"]]

    if event == "reset":
        progress_cmd += ["--status", "not_started"]
        result_cmd += ["--status", "not_ready"]
    elif event in {"start", "heartbeat"}:
        progress_cmd += ["--status", "running"]
        if active_stage_label:
            progress_cmd += ["--active-stage-label", active_stage_label]
        if started_at:
            progress_cmd += ["--started-at", started_at]
        if updated_at:
            progress_cmd += ["--updated-at", updated_at]
        if notes:
            progress_cmd += ["--notes", notes]
    elif event == "complete":
        progress_cmd += ["--status", "completed"]
        result_cmd += ["--status", "completed"]
        if active_stage_label:
            progress_cmd += ["--active-stage-label", active_stage_label]
        if started_at:
            progress_cmd += ["--started-at", started_at]
            result_cmd += ["--started-at", started_at]
        if updated_at:
            progress_cmd += ["--updated-at", updated_at]
            result_cmd += ["--updated-at", updated_at]
        if completed_at:
            result_cmd += ["--completed-at", completed_at]
        if decision_case:
            result_cmd += ["--decision-case", decision_case]
        if action:
            result_cmd += ["--action", action]
        if notes:
            progress_cmd += ["--notes", notes]
            result_cmd += ["--notes", notes]
    elif event == "hold":
        progress_cmd += ["--status", "explicit_hold"]
        result_cmd += ["--status", "explicit_hold"]
        if active_stage_label:
            progress_cmd += ["--active-stage-label", active_stage_label]
        if started_at:
            progress_cmd += ["--started-at", started_at]
            result_cmd += ["--started-at", started_at]
        if updated_at:
            progress_cmd += ["--updated-at", updated_at]
            result_cmd += ["--updated-at", updated_at]
        if completed_at:
            result_cmd += ["--completed-at", completed_at]
        if decision_case:
            result_cmd += ["--decision-case", decision_case]
        if action:
            result_cmd += ["--action", action]
        if notes:
            progress_cmd += ["--notes", notes]
            result_cmd += ["--notes", notes]
    else:
        raise ValueError(f"Unsupported event: {event}")

    _run(progress_cmd, python_bin)
    if event in {"reset", "complete", "hold"}:
        _run(result_cmd, python_bin)
    _run(["tools/wetlab/wetlab/build_wetlab_final2_gate_refresh.py", "--run"], python_bin)

    run_record_s = _summary(target["run_record_json"])
    gate_s = _summary(target["gate_json"])
    return {
        "target_id": target["target_id"],
        "event": event,
        "progress_command": " ".join(progress_cmd),
        "result_command": " ".join(result_cmd) if event in {"reset", "complete", "hold"} else "",
        "run_record_status": str(run_record_s.get("status", "")).strip(),
        "execution_state": str(run_record_s.get("execution_state", "")).strip(),
        "queue_status_now": str(run_record_s.get("queue_status_now", gate_s.get("queue_status_now", ""))).strip(),
        "gate_status": str(gate_s.get("status", "")).strip(),
        "gate_execution_state": str(gate_s.get("execution_state", gate_s.get("lbdhodh_review_state", ""))).strip(),
    }


def build_payload(event_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": {
            "status": "wetlab_final2_runtime_event_applied",
            "target_id": event_result["target_id"],
            "event": event_result["event"],
            "queue_status_now": event_result["queue_status_now"],
            "gate_status": event_result["gate_status"],
            "next_required_step": "Inspect the final2 execution console to confirm the serialized tail gate moved as expected.",
        },
        "rows": [
            {"field": key, "value": value}
            for key, value in event_result.items()
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a final2 runtime event and refresh downstream gates.")
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(apply_runtime_event(target_key=args.target, event=args.event, python_bin=args.python_bin, active_stage_label=args.active_stage_label, decision_case=args.decision_case, action=args.action, started_at=args.started_at, updated_at=args.updated_at, completed_at=args.completed_at, notes=args.notes))
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Final2 Runtime Event", payload)


if __name__ == "__main__":
    main()
