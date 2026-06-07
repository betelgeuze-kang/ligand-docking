#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_MD = "runs/wetlab_priority3_runtime_event_current.md"

TARGETS: dict[str, dict[str, str]] = {
    "sarscov2_mpro": {
        "target_id": "SARS-CoV-2 Mpro",
        "progress_builder": "tools/build_sarscov2_mpro_live_progress.py",
        "result_builder": "tools/build_sarscov2_mpro_result_summary.py",
        "run_record_json": "runs/sarscov2_mpro_run_record_current.json",
        "gate_json": "runs/sarscov2_mpro_run_status_current.json",
    },
    "caix": {
        "target_id": "CA IX",
        "progress_builder": "tools/build_caix_live_progress.py",
        "result_builder": "tools/build_caix_result_summary.py",
        "run_record_json": "runs/caix_run_record_current.json",
        "gate_json": "runs/caix_result_review_current.json",
    },
    "tcruzi_pde": {
        "target_id": "T. cruzi PDE",
        "progress_builder": "tools/build_tcruzi_pde_live_progress.py",
        "result_builder": "tools/build_tcruzi_pde_result_summary.py",
        "run_record_json": "runs/tcruzi_pde_run_record_current.json",
        "gate_json": "runs/tcruzi_pde_result_review_current.json",
    },
}

EVENTS = {"reset", "start", "heartbeat", "complete", "hold"}


def _summary(path_like: str) -> dict[str, Any]:
    return dict(load_json(path_like).get("summary", {}) or {})


def _run(cmd: list[str], python_bin: str) -> None:
    subprocess.run([python_bin, *cmd], cwd=ROOT, check=True)


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
) -> dict[str, Any]:
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
    _run(["tools/build_wetlab_priority3_gate_refresh.py"], python_bin)

    run_record_s = _summary(target["run_record_json"])
    gate_s = _summary(target["gate_json"])
    return {
        "target_id": target["target_id"],
        "event": event,
        "progress_command": " ".join(progress_cmd),
        "result_command": " ".join(result_cmd) if event in {"reset", "complete", "hold"} else "",
        "run_record_status": str(run_record_s.get("status", "")).strip(),
        "execution_state": str(run_record_s.get("execution_state", run_record_s.get("status", ""))).strip(),
        "queue_status_now": str(run_record_s.get("queue_status_now", gate_s.get("queue_status_now", ""))).strip(),
        "gate_status": str(gate_s.get("status", "")).strip(),
        "gate_execution_state": str(gate_s.get("execution_state", gate_s.get("result_review_gate_status", ""))).strip(),
    }


def build_payload(event_result: dict[str, Any]) -> dict[str, Any]:
    target_key = next(k for k, v in TARGETS.items() if v["target_id"] == event_result["target_id"])
    target = TARGETS[target_key]
    return {
        "summary": {
            "status": "wetlab_priority3_runtime_event_applied",
            "target_id": event_result["target_id"],
            "event": event_result["event"],
            "run_record_artifact": target["run_record_json"].replace(".json", ".md"),
            "gate_artifact": target["gate_json"].replace(".json", ".md"),
            "run_record_status": event_result["run_record_status"],
            "execution_state": event_result["execution_state"],
            "queue_status_now": event_result["queue_status_now"],
            "gate_status": event_result["gate_status"],
            "gate_execution_state": event_result["gate_execution_state"],
            "next_required_step": "If this target is still running, keep updating it with `start`/`heartbeat` style events. If it completed or hit an explicit hold, read the downstream gate artifact to confirm the next serialized target opened as expected.",
        },
        "structured": {
            "progress_command": event_result["progress_command"],
            "result_command": event_result["result_command"],
            "refresh_command": "tools/build_wetlab_priority3_gate_refresh.py",
        },
        "rows": [
            {
                "artifact_kind": "run_record",
                "artifact_path": target["run_record_json"].replace(".json", ".md"),
                "status": event_result["run_record_status"],
                "detail": event_result["execution_state"],
            },
            {
                "artifact_kind": "downstream_gate",
                "artifact_path": target["gate_json"].replace(".json", ".md"),
                "status": event_result["gate_status"],
                "detail": event_result["gate_execution_state"],
            },
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a runtime event to a priority3 serialized wet-lab target and refresh downstream gates.")
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
    )
    payload = build_payload(event_result)
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Priority3 Runtime Event", payload)


if __name__ == "__main__":
    main()
