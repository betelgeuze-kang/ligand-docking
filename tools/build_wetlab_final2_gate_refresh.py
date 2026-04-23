#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_MD = "runs/wetlab_final2_gate_refresh_current.md"

STEP_COMMANDS = [
    ("stk17b_run_record", "tools/build_stk17b_run_record.py"),
    ("stk17b_run_status", "tools/build_stk17b_run_status.py"),
    ("lbdhodh_repurposing_fill_map", "tools/build_wetlab_lbdhodh_repurposing_fill_map.py"),
    ("lbdhodh_novelty_fill_map", "tools/build_wetlab_lbdhodh_novelty_fill_map.py"),
    ("neglected_first_contact_packets", "tools/build_wetlab_neglected_first_contact_packets.py"),
    ("neglected_outreach_packet", "tools/build_wetlab_neglected_outreach_packet.py"),
    ("lbdhodh_render_suite", "tools/build_lbdhodh_render_suite.py"),
    ("lbdhodh_launch_packet", "tools/build_lbdhodh_launch_packet.py"),
    ("lbdhodh_result_review", "tools/build_lbdhodh_result_review.py"),
    ("lbdhodh_run_record", "tools/build_lbdhodh_run_record.py"),
    ("final2_run_queue", "tools/build_wetlab_final2_protein_run_queue.py"),
    ("final2_chain_stack", "tools/build_wetlab_final2_chain_stack.py"),
    ("partnering_stack", "tools/build_wetlab_partnering_stack.py"),
]


def build_payload() -> dict:
    return {
        "summary": {
            "status": "wetlab_final2_gate_refresh_ready",
            "step_count": len(STEP_COMMANDS),
            "next_required_step": "Use this refresh after every final2 live-progress or result-summary update.",
        },
        "rows": [
            {"step_rank": idx, "step_id": step_id, "command": command, "stage_role": "refresh_serialized_tail_gate"}
            for idx, (step_id, command) in enumerate(STEP_COMMANDS, start=1)
        ],
    }


def _run(python_bin: str) -> None:
    for _, command in STEP_COMMANDS:
        subprocess.run([python_bin, command], cwd=ROOT, check=True)


def _write(payload: dict) -> None:
    from tools.wetlab_target_render_utils import write_artifact
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Final2 Gate Refresh", payload)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Refresh all final2 gate artifacts.")
    p.add_argument("--python-bin", default=sys.executable)
    p.add_argument("--run", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload()
    _write(payload)
    _run(args.python_bin)


if __name__ == "__main__":
    main()
