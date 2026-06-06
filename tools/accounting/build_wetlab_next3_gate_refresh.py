#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_MD = "runs/wetlab_next3_gate_refresh_current.md"

STEP_SPECS: list[tuple[str, list[str], str]] = [
    ("cruzain_run_record", ["tools/wetlab/build_cruzain_run_record.py"], "runs/cruzain_run_record_current.json"),
    ("cruzain_run_status", ["tools/wetlab/build_cruzain_run_status.py"], "runs/cruzain_run_status_current.json"),
    ("plpro_result_review", ["tools/wetlab/build_sarscov2_plpro_result_review.py"], "runs/sarscov2_plpro_result_review_current.json"),
    ("plpro_run_record", ["tools/wetlab/build_sarscov2_plpro_run_record.py"], "runs/sarscov2_plpro_run_record_current.json"),
    ("alk2_result_review", ["tools/build_alk2_result_review.py"], "runs/alk2_result_review_current.json"),
    ("alk2_run_record", ["tools/build_alk2_run_record.py"], "runs/alk2_run_record_current.json"),
    ("next3_run_queue", ["tools/build_wetlab_next3_protein_run_queue.py"], "runs/wetlab_next3_protein_run_queue_current.json"),
    ("next3_chain_stack", ["tools/build_wetlab_next3_chain_stack.py"], "runs/wetlab_next3_chain_stack_current.json"),
    ("partnering_stack", ["tools/build_wetlab_partnering_stack.py"], "runs/wetlab_partnering_stack_current.json"),
]


def _summary(path_like: str) -> dict[str, Any]:
    return dict(load_json(path_like).get("summary", {}) or {})


def _run(cmd: list[str], python_bin: str) -> None:
    subprocess.run([python_bin, *cmd], cwd=ROOT, check=True)


def build_payload(step_rows: list[dict[str, Any]], summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cruzain = summaries["cruzain_run_status"]
    plpro = summaries["plpro_result_review"]
    alk2 = summaries["alk2_result_review"]
    queue = summaries["next3_run_queue"]
    return {
        "summary": {
            "status": "wetlab_next3_gate_refresh_ready",
            "step_count": len(step_rows),
            "cruzain_execution_state": str(cruzain.get("execution_state", "")).strip(),
            "plpro_review_state": str(plpro.get("plpro_review_state", "")).strip(),
            "alk2_execution_state": str(alk2.get("alk2_execution_state", "")).strip(),
            "ready_now_target_count": int(queue.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(queue.get("blocked_on_previous_review_count", 0) or 0),
            "running_target_count": int(queue.get("running_target_count", 0) or 0),
            "resolved_target_count": int(queue.get("resolved_target_count", 0) or 0),
            "next_required_step": "If priority3 is not yet resolved, keep Cruzain blocked. Once the priority3 final review opens the next3 chain, use the serialized order Cruzain -> PLpro -> ALK2 and refresh this artifact after every runtime event.",
        },
        "structured": {
            "execution_policy": "serialized_by_target_after_priority3",
            "queue_artifact": "runs/wetlab_next3_protein_run_queue_current.md",
            "chain_stack_artifact": "runs/wetlab_next3_chain_stack_current.md",
        },
        "rows": step_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the next3 run-record and gate chain in serialized order.")
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
        rows.append({"step_id": step_id, "command": " ".join(cmd), "output_artifact": output_json.replace(".json", ".md"), "output_status": str(summary.get("status", "")).strip()})
    payload = build_payload(rows, summaries)
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Next3 Gate Refresh", payload)


if __name__ == "__main__":
    main()
