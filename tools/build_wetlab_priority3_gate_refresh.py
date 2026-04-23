#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_MD = "runs/wetlab_priority3_gate_refresh_current.md"

DEFAULT_STEPS = [
    ("mpro_run_record", ["tools/build_sarscov2_mpro_run_record.py"], "runs/sarscov2_mpro_run_record_current.json"),
    ("mpro_run_status", ["tools/build_sarscov2_mpro_run_status.py"], "runs/sarscov2_mpro_run_status_current.json"),
    ("caix_run_record", ["tools/build_caix_run_record.py"], "runs/caix_run_record_current.json"),
    ("caix_result_review", ["tools/build_caix_result_review.py"], "runs/caix_result_review_current.json"),
    ("tcruzi_run_record", ["tools/build_tcruzi_pde_run_record.py"], "runs/tcruzi_pde_run_record_current.json"),
    ("tcruzi_result_review", ["tools/build_tcruzi_pde_result_review.py"], "runs/tcruzi_pde_result_review_current.json"),
    ("priority3_run_queue", ["tools/build_wetlab_priority3_protein_run_queue.py"], "runs/wetlab_priority3_protein_run_queue_current.json"),
    ("partnering_stack", ["tools/build_wetlab_partnering_stack.py"], "runs/wetlab_partnering_stack_current.json"),
]


def _summary(path_like: str) -> dict[str, Any]:
    return dict(load_json(path_like).get("summary", {}) or {})


def run_refresh(python_bin: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step_id, command_parts, output_json in DEFAULT_STEPS:
        subprocess.run([python_bin, *command_parts], cwd=ROOT, check=True)
        summary = _summary(output_json)
        rows.append(
            {
                "step_id": step_id,
                "output_artifact": output_json.replace(".json", ".md"),
                "output_status": str(summary.get("status", "")).strip(),
                "queue_status": str(summary.get("queue_status_now", "")).strip(),
                "execution_state": str(summary.get("execution_state", "")).strip(),
            }
        )
    return rows


def build_payload(step_rows: list[dict[str, Any]]) -> dict[str, Any]:
    queue_summary = _summary("runs/wetlab_priority3_protein_run_queue_current.json")
    stack_summary = _summary("runs/wetlab_partnering_stack_current.json")
    mpro_progress = _summary("runs/sarscov2_mpro_live_progress_current.json") if Path(ROOT / "runs/sarscov2_mpro_live_progress_current.json").exists() else {}
    mpro_result = _summary("runs/sarscov2_mpro_result_summary_current.json") if Path(ROOT / "runs/sarscov2_mpro_result_summary_current.json").exists() else {}
    caix_progress = _summary("runs/caix_live_progress_current.json") if Path(ROOT / "runs/caix_live_progress_current.json").exists() else {}
    caix_result = _summary("runs/caix_result_summary_current.json") if Path(ROOT / "runs/caix_result_summary_current.json").exists() else {}
    tcruzi_progress = _summary("runs/tcruzi_pde_live_progress_current.json") if Path(ROOT / "runs/tcruzi_pde_live_progress_current.json").exists() else {}
    tcruzi_result = _summary("runs/tcruzi_pde_result_summary_current.json") if Path(ROOT / "runs/tcruzi_pde_result_summary_current.json").exists() else {}
    tcruzi_run_record = _summary("runs/tcruzi_pde_run_record_current.json") if Path(ROOT / "runs/tcruzi_pde_run_record_current.json").exists() else {}
    return {
        "summary": {
            "status": "wetlab_priority3_gate_refresh_ready",
            "step_count": len(step_rows),
            "mpro_live_progress_status": str(mpro_progress.get("status", "not_present")).strip() or "not_present",
            "mpro_result_summary_status": str(mpro_result.get("status", "not_present")).strip() or "not_present",
            "caix_live_progress_status": str(caix_progress.get("status", "not_present")).strip() or "not_present",
            "caix_result_summary_status": str(caix_result.get("status", "not_present")).strip() or "not_present",
            "tcruzi_live_progress_status": str(tcruzi_progress.get("status", "not_present")).strip() or "not_present",
            "tcruzi_result_summary_status": str(tcruzi_result.get("status", "not_present")).strip() or "not_present",
            "ready_now_target_count": int(queue_summary.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(queue_summary.get("blocked_on_previous_review_count", 0) or 0),
            "running_target_count": int(queue_summary.get("running_target_count", 0) or 0),
            "resolved_target_count": int(queue_summary.get("resolved_target_count", 0) or 0),
            "mpro_execution_state": str(stack_summary.get("mpro_execution_state", "")).strip(),
            "caix_review_state": str(stack_summary.get("caix_review_state", "")).strip(),
            "tcruzi_run_record_status": str(tcruzi_run_record.get("status", "not_present")).strip() or "not_present",
            "tcruzi_execution_state": str(stack_summary.get("tcruzi_execution_state", tcruzi_run_record.get("execution_state", ""))).strip(),
            "tcruzi_queue_status_now": str(tcruzi_run_record.get("queue_status_now", "")).strip(),
            "tcruzi_result_review_gate_status": str(stack_summary.get("tcruzi_result_review_gate_status", "")).strip(),
            "next_required_step": "Update the live progress or result summary writers for the active target, then rerun this refresh script to propagate serialized gate changes through CA IX and T. cruzi PDE.",
        },
        "structured": {
            "execution_policy": "serialized_by_target",
            "refresh_role": "rebuild_all_priority3_gate_artifacts_from_live_writer_inputs",
        },
        "rows": step_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the serialized priority3 wet-lab gate chain from live writer inputs.")
    parser.add_argument("--python-bin", default=sys.executable)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = run_refresh(args.python_bin)
    payload = build_payload(rows)
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Priority3 Gate Refresh", payload)


if __name__ == "__main__":
    main()
