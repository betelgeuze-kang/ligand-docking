#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_MD = "runs/wetlab_wave1_tail_gate_refresh_current.md"

STEP_SPECS: list[tuple[str, list[str], str]] = [
    ("stk17b_run_record", ["tools/wetlab/build_stk17b_run_record.py"], "runs/stk17b_run_record_current.json"),
    ("stk17b_run_status", ["tools/wetlab/build_stk17b_run_status.py"], "runs/stk17b_run_status_current.json"),
    ("lbdhodh_result_review", ["tools/build_lbdhodh_result_review.py"], "runs/lbdhodh_result_review_current.json"),
    ("lbdhodh_run_record", ["tools/wetlab/build_lbdhodh_run_record.py"], "runs/lbdhodh_run_record_current.json"),
    ("wave1_tail_run_queue", ["tools/wetlab/build_wetlab_wave1_tail_protein_run_queue.py"], "runs/wetlab_wave1_tail_protein_run_queue_current.json"),
    ("wave1_tail_chain_stack", ["tools/wetlab/build_wetlab_wave1_tail_chain_stack.py"], "runs/wetlab_wave1_tail_chain_stack_current.json"),
]


def _summary(path_like: str) -> dict[str, Any]:
    return dict(load_json(path_like).get("summary", {}) or {})


def _run(cmd: list[str], python_bin: str) -> None:
    subprocess.run([python_bin, *cmd], cwd=ROOT, check=True)


def build_payload(step_rows: list[dict[str, Any]], summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    stk17b = summaries["stk17b_run_status"]
    lbdhodh = summaries["lbdhodh_result_review"]
    queue = summaries["wave1_tail_run_queue"]
    return {
        "summary": {
            "status": "wetlab_wave1_tail_gate_refresh_ready",
            "step_count": len(step_rows),
            "stk17b_execution_state": str(stk17b.get("execution_state", "")).strip(),
            "lbdhodh_review_state": str(lbdhodh.get("lbdhodh_review_state", "")).strip(),
            "ready_now_target_count": int(queue.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(queue.get("blocked_on_previous_review_count", 0) or 0),
            "running_target_count": int(queue.get("running_target_count", 0) or 0),
            "resolved_target_count": int(queue.get("resolved_target_count", 0) or 0),
            "next_required_step": "If next3 is not yet resolved, keep STK17B blocked. Once the next3 final review opens the Wave 1 tail chain, use the serialized order STK17B -> LbDHODH and refresh this artifact after every runtime event.",
        },
        "structured": {
            "execution_policy": "serialized_by_target_after_next3",
            "queue_artifact": "runs/wetlab_wave1_tail_protein_run_queue_current.md",
            "chain_stack_artifact": "runs/wetlab_wave1_tail_chain_stack_current.md",
        },
        "rows": step_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the Wave 1 tail run-record and gate chain in serialized order.")
    parser.add_argument("--python-bin", default=sys.executable)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, Any]] = {}
    for step_id, cmd, output_json in STEP_SPECS:
        _run(cmd, args.python_bin)
        summary = _summary(output_json)
        summaries[step_id] = summary
        rows.append(
            {
                "step_id": step_id,
                "command": " ".join(cmd),
                "output_artifact": output_json.replace(".json", ".md"),
                "output_status": str(summary.get("status", "")).strip(),
            }
        )
    payload = build_payload(rows, summaries)
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Wave1 Tail Gate Refresh", payload)


if __name__ == "__main__":
    main()
