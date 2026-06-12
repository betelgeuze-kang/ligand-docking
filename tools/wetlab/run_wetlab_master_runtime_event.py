#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from tools import build_wetlab_master_runtime_event as runtime_event_mod
from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_PATH = ROOT / "runs/wetlab_master_runtime_event_log.jsonl"

MASTER_REFRESH_BUILDERS = [
    "tools/build_wetlab_priority3_gate_refresh.py",
    "tools/build_wetlab_priority3_protein_run_queue.py",
    "tools/build_wetlab_priority3_runtime_runbook.py",
    "tools/build_wetlab_priority3_execution_console.py",
    "tools/wetlab/build_wetlab_next3_gate_refresh.py",
    "tools/build_wetlab_next3_protein_run_queue.py",
    "tools/build_wetlab_next3_chain_stack.py",
    "tools/build_wetlab_next3_runtime_runbook.py",
    "tools/build_wetlab_next3_execution_console.py",
    "tools/wetlab/wetlab/build_wetlab_final2_gate_refresh.py",
    "tools/build_wetlab_final2_protein_run_queue.py",
    "tools/build_wetlab_final2_chain_stack.py",
    "tools/wetlab/wetlab/build_wetlab_final2_runtime_runbook.py",
    "tools/build_wetlab_final2_execution_console.py",
    "tools/wetlab/wetlab/build_wetlab_wave2_gate_refresh.py",
    "tools/build_wetlab_wave2_protein_run_queue.py",
    "tools/build_wetlab_wave2_chain_stack.py",
    "tools/build_wetlab_wave2_runtime_runbook.py",
    "tools/build_wetlab_wave2_execution_console.py",
    "tools/build_wetlab_master_execution_queue.py",
    "tools/build_wetlab_master_runtime_runbook.py",
    "tools/build_wetlab_master_execution_console.py",
    "tools/build_wetlab_partnering_stack.py",
]


def _append_event_log(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _rebuild_master_support_artifacts(python_bin: str) -> None:
    for script in MASTER_REFRESH_BUILDERS:
        subprocess.run([python_bin, script], cwd=ROOT, check=True)


def apply_and_log_event(
    *,
    target: str,
    event: str,
    python_bin: str,
    active_stage_label: str = "",
    decision_case: str = "",
    action: str = "",
    started_at: str = "",
    updated_at: str = "",
    completed_at: str = "",
    notes: str = "",
    log_path: Path = DEFAULT_LOG_PATH,
) -> dict[str, Any]:
    _rebuild_master_support_artifacts(python_bin)
    master_queue_before = load_json(runtime_event_mod.DEFAULT_MASTER_QUEUE_JSON)

    event_result = runtime_event_mod.apply_runtime_event(
        target_key=target,
        event=event,
        python_bin=python_bin,
        active_stage_label=active_stage_label,
        decision_case=decision_case,
        action=action,
        started_at=started_at,
        updated_at=updated_at,
        completed_at=completed_at,
        notes=notes,
        master_queue_payload=master_queue_before,
    )

    _rebuild_master_support_artifacts(python_bin)
    master_queue_after = load_json(runtime_event_mod.DEFAULT_MASTER_QUEUE_JSON)
    master_runbook_after = load_json(runtime_event_mod.DEFAULT_MASTER_RUNBOOK_JSON)
    master_console_after = load_json(runtime_event_mod.DEFAULT_MASTER_CONSOLE_JSON)
    payload = runtime_event_mod.build_payload(
        event_result,
        master_queue_after,
        master_runbook_after,
        master_console_after,
    )
    write_artifact(runtime_event_mod.DEFAULT_OUT_MD, "Wet-Lab Master Runtime Event", payload)

    event_timestamp = completed_at or updated_at or started_at or datetime.now().isoformat(timespec="seconds")
    summary = dict(payload.get("summary", {}) or {})
    log_row = dict(event_result)
    log_row["target_queue_status_after"] = str(summary.get("target_queue_status_after", "")).strip()
    log_row["target_blocked_after"] = bool(summary.get("target_blocked_after", False))
    log_row["first_actionable_target"] = str(summary.get("first_actionable_target", "")).strip()
    log_row["first_actionable_chain"] = str(summary.get("first_actionable_chain", "")).strip()
    log_row["master_console_status"] = str(summary.get("master_console_status", "")).strip()
    log_row["event_timestamp"] = event_timestamp
    _append_event_log(log_path, log_row)
    return log_row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch, log, and refresh a wet-lab runtime event from the master serialized queue.")
    parser.add_argument("--target", choices=sorted(runtime_event_mod.TARGETS), required=True)
    parser.add_argument("--event", choices=sorted(runtime_event_mod.EVENTS), required=True)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--active-stage-label", default="")
    parser.add_argument("--decision-case", default="")
    parser.add_argument("--action", default="")
    parser.add_argument("--started-at", default="")
    parser.add_argument("--updated-at", default="")
    parser.add_argument("--completed-at", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    apply_and_log_event(
        target=args.target,
        event=args.event,
        python_bin=args.python_bin,
        active_stage_label=args.active_stage_label,
        decision_case=args.decision_case,
        action=args.action,
        started_at=args.started_at,
        updated_at=args.updated_at,
        completed_at=args.completed_at,
        notes=args.notes,
        log_path=Path(args.log_path),
    )


if __name__ == "__main__":
    main()
