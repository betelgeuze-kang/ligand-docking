#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from tools import build_wetlab_next3_runtime_event as runtime_event_mod
from tools.wetlab_target_render_utils import write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_PATH = ROOT / "runs/wetlab_next3_runtime_event_log.jsonl"


def _append_event_log(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _rebuild_support_artifacts(python_bin: str) -> None:
    subprocess.run([python_bin, "tools/build_wetlab_next3_protein_run_queue.py"], cwd=ROOT, check=True)
    subprocess.run([python_bin, "tools/build_wetlab_next3_runtime_runbook.py"], cwd=ROOT, check=True)
    subprocess.run([python_bin, "tools/build_wetlab_next3_execution_console.py"], cwd=ROOT, check=True)
    subprocess.run([python_bin, "tools/build_wetlab_partnering_stack.py"], cwd=ROOT, check=True)


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
    )
    payload = runtime_event_mod.build_payload(event_result)
    write_artifact(runtime_event_mod.DEFAULT_OUT_MD, "Wet-Lab Next3 Runtime Event", payload)

    event_timestamp = completed_at or updated_at or started_at or datetime.now().isoformat(timespec="seconds")
    log_row = dict(event_result)
    log_row["event_timestamp"] = event_timestamp
    _append_event_log(log_path, log_row)
    _rebuild_support_artifacts(python_bin)
    return log_row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply and log a next3 runtime event, then rebuild the execution console.")
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
