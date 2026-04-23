#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_MD = "runs/wetlab_wave2_gate_refresh_current.md"

DEFAULT_STEPS: list[tuple[str, list[str], str]] = [
    ("partner_target_portfolio", ["tools/build_wetlab_partner_target_portfolio.py"], "runs/wetlab_partner_target_portfolio_current.json"),
    ("validation_companion_panels", ["tools/build_wetlab_validation_companion_panels.py"], "runs/wetlab_validation_companion_panels_current.json"),
    ("cathepsin_k_repurposing_fill_map", ["tools/build_wetlab_cathepsin_k_repurposing_fill_map.py"], "runs/wetlab_cathepsin_k_repurposing_fill_map_current.json"),
    ("cathepsin_k_novelty_fill_map", ["tools/build_wetlab_cathepsin_k_novelty_fill_map.py"], "runs/wetlab_cathepsin_k_novelty_fill_map_current.json"),
    ("cathepsin_k_render_suite", ["tools/build_cathepsin_k_render_suite.py"], "runs/cathepsin_k_render_suite_current.json"),
    ("cathepsin_k_launch_packet", ["tools/build_cathepsin_k_launch_packet.py"], "runs/cathepsin_k_launch_packet_current.json"),
    ("cathepsin_k_result_review", ["tools/build_cathepsin_k_result_review.py"], "runs/cathepsin_k_result_review_current.json"),
    ("cathepsin_k_run_record", ["tools/build_cathepsin_k_run_record.py"], "runs/cathepsin_k_run_record_current.json"),
    ("cathepsin_k_result_review_refresh", ["tools/build_cathepsin_k_result_review.py"], "runs/cathepsin_k_result_review_current.json"),
    ("dengue_ns2b_ns3_protease_repurposing_fill_map", ["tools/build_wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map.py"], "runs/wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map_current.json"),
    ("dengue_ns2b_ns3_protease_novelty_fill_map", ["tools/build_wetlab_dengue_ns2b_ns3_protease_novelty_fill_map.py"], "runs/wetlab_dengue_ns2b_ns3_protease_novelty_fill_map_current.json"),
    ("dengue_ns2b_ns3_protease_render_suite", ["tools/build_dengue_ns2b_ns3_protease_render_suite.py"], "runs/dengue_ns2b_ns3_protease_render_suite_current.json"),
    ("dengue_ns2b_ns3_protease_launch_packet", ["tools/build_dengue_ns2b_ns3_protease_launch_packet.py"], "runs/dengue_ns2b_ns3_protease_launch_packet_current.json"),
    ("dengue_ns2b_ns3_protease_result_review", ["tools/build_dengue_ns2b_ns3_protease_result_review.py"], "runs/dengue_ns2b_ns3_protease_result_review_current.json"),
    ("dengue_ns2b_ns3_protease_run_record", ["tools/build_dengue_ns2b_ns3_protease_run_record.py"], "runs/dengue_ns2b_ns3_protease_run_record_current.json"),
    ("dengue_ns2b_ns3_protease_result_review_refresh", ["tools/build_dengue_ns2b_ns3_protease_result_review.py"], "runs/dengue_ns2b_ns3_protease_result_review_current.json"),
    ("dpre1_repurposing_fill_map", ["tools/build_wetlab_dpre1_repurposing_fill_map.py"], "runs/wetlab_dpre1_repurposing_fill_map_current.json"),
    ("dpre1_novelty_fill_map", ["tools/build_wetlab_dpre1_novelty_fill_map.py"], "runs/wetlab_dpre1_novelty_fill_map_current.json"),
    ("dpre1_render_suite", ["tools/build_dpre1_render_suite.py"], "runs/dpre1_render_suite_current.json"),
    ("dpre1_launch_packet", ["tools/build_dpre1_launch_packet.py"], "runs/dpre1_launch_packet_current.json"),
    ("dpre1_result_review", ["tools/build_dpre1_result_review.py"], "runs/dpre1_result_review_current.json"),
    ("dpre1_run_record", ["tools/build_dpre1_run_record.py"], "runs/dpre1_run_record_current.json"),
    ("dpre1_result_review_refresh", ["tools/build_dpre1_result_review.py"], "runs/dpre1_result_review_current.json"),
    ("tcruzi_krs1_repurposing_fill_map", ["tools/build_wetlab_tcruzi_krs1_repurposing_fill_map.py"], "runs/wetlab_tcruzi_krs1_repurposing_fill_map_current.json"),
    ("tcruzi_krs1_novelty_fill_map", ["tools/build_wetlab_tcruzi_krs1_novelty_fill_map.py"], "runs/wetlab_tcruzi_krs1_novelty_fill_map_current.json"),
    ("tcruzi_krs1_render_suite", ["tools/build_tcruzi_krs1_render_suite.py"], "runs/tcruzi_krs1_render_suite_current.json"),
    ("tcruzi_krs1_launch_packet", ["tools/build_tcruzi_krs1_launch_packet.py"], "runs/tcruzi_krs1_launch_packet_current.json"),
    ("tcruzi_krs1_result_review", ["tools/build_tcruzi_krs1_result_review.py"], "runs/tcruzi_krs1_result_review_current.json"),
    ("tcruzi_krs1_run_record", ["tools/build_tcruzi_krs1_run_record.py"], "runs/tcruzi_krs1_run_record_current.json"),
    ("tcruzi_krs1_result_review_refresh", ["tools/build_tcruzi_krs1_result_review.py"], "runs/tcruzi_krs1_result_review_current.json"),
    ("lrrk2_repurposing_fill_map", ["tools/build_wetlab_lrrk2_repurposing_fill_map.py"], "runs/wetlab_lrrk2_repurposing_fill_map_current.json"),
    ("lrrk2_novelty_fill_map", ["tools/build_wetlab_lrrk2_novelty_fill_map.py"], "runs/wetlab_lrrk2_novelty_fill_map_current.json"),
    ("lrrk2_render_suite", ["tools/build_lrrk2_render_suite.py"], "runs/lrrk2_render_suite_current.json"),
    ("lrrk2_launch_packet", ["tools/build_lrrk2_launch_packet.py"], "runs/lrrk2_launch_packet_current.json"),
    ("lrrk2_result_review", ["tools/build_lrrk2_result_review.py"], "runs/lrrk2_result_review_current.json"),
    ("lrrk2_run_record", ["tools/build_lrrk2_run_record.py"], "runs/lrrk2_run_record_current.json"),
    ("lrrk2_result_review_refresh", ["tools/build_lrrk2_result_review.py"], "runs/lrrk2_result_review_current.json"),
    ("wave2_run_queue", ["tools/build_wetlab_wave2_protein_run_queue.py"], "runs/wetlab_wave2_protein_run_queue_current.json"),
    ("wave2_chain_stack", ["tools/build_wetlab_wave2_chain_stack.py"], "runs/wetlab_wave2_chain_stack_current.json"),
]


def _summary(path_like: str) -> dict[str, Any]:
    return dict(load_json(path_like).get("summary", {}) or {})


def _run(cmd: list[str], python_bin: str) -> None:
    subprocess.run([python_bin, *cmd], cwd=ROOT, check=True)


def run_refresh(python_bin: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step_id, cmd, output_json in DEFAULT_STEPS:
        _run(cmd, python_bin)
        summary = _summary(output_json)
        rows.append(
            {
                "step_id": step_id,
                "command": " ".join(cmd),
                "output_artifact": output_json.replace(".json", ".md"),
                "output_status": str(summary.get("status", "")).strip(),
            }
        )
    return rows


def build_payload(step_rows: list[dict[str, Any]], queue_summary: dict[str, Any] | None = None, chain_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    qs = dict(queue_summary or {})
    cs = dict(chain_summary or {})
    return {
        "summary": {
            "status": "wetlab_wave2_gate_refresh_ready",
            "step_count": len(step_rows),
            "ready_now_target_count": int(qs.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(qs.get("blocked_on_previous_review_count", 0) or 0),
            "blocked_on_target_content_count": int(qs.get("blocked_on_target_content_count", 0) or 0),
            "placeholder_target_count": int(qs.get("placeholder_target_count", 0) or 0),
            "final2_final_gate_open": bool(cs.get("final2_final_gate_open", False)),
            "next_required_step": "Refresh wave2 after any upstream final2 change or after landing new Cathepsin K/Dengue/DprE1/KRS1/LRRK2 launch-run artifacts, with the Cathepsin K fill maps rebuilt before launch/readiness is recomputed.",
        },
        "structured": {
            "execution_policy": "serialized_by_target_after_final2",
            "queue_artifact": "runs/wetlab_wave2_protein_run_queue_current.md",
            "chain_stack_artifact": "runs/wetlab_wave2_chain_stack_current.md",
        },
        "rows": step_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the wave2 queue and chain-stack surfaces.")
    parser.add_argument("--python-bin", default=sys.executable)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = run_refresh(args.python_bin)
    payload = build_payload(
        rows,
        _summary("runs/wetlab_wave2_protein_run_queue_current.json"),
        _summary("runs/wetlab_wave2_chain_stack_current.json"),
    )
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Wave2 Gate Refresh", payload)


if __name__ == "__main__":
    main()
