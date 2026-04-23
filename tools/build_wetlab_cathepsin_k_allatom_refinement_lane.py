#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_allatom_refinement_utils import build_target_allatom_refinement_lane_payload
from tools.wetlab_target_render_utils import load_json, write_artifact

TARGET_ID = "Cathepsin K"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_BRANCH_SUMMARY_JSON = "runs/wetlab_cathepsin_k_tuned_branch_summary_current.json"
DEFAULT_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_cathepsin_k_stage6_tuning_surface_current.json"
DEFAULT_OUT_MD = "runs/wetlab_cathepsin_k_allatom_refinement_lane_current.md"
DEFAULT_TOP_N = 32


def build_payload(
    execution_queue_payload: dict[str, Any],
    branch_summary_payload: dict[str, Any],
    stage6_tuning_surface_payload: dict[str, Any],
    *,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    payload = build_target_allatom_refinement_lane_payload(
        target_id=TARGET_ID,
        execution_queue_payload=execution_queue_payload,
        branch_summary_payload=branch_summary_payload,
        stage6_tuning_surface_payload=stage6_tuning_surface_payload,
        top_n=max(1, int(top_n)),
        lane_label="cathepsin_k_allatom_top32_refinement",
        selected_command_kind="pseudo_allatom_local_refine",
        selected_threshold_A=2.5,
        review_unit_label="all-atom top-4 review packet",
    )
    payload.setdefault("structured", {})
    payload["structured"]["branch_summary_artifact"] = "runs/wetlab_cathepsin_k_tuned_branch_summary_current.md"
    payload["structured"]["stage6_tuning_surface_artifact"] = "runs/wetlab_cathepsin_k_stage6_tuning_surface_current.md"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Cathepsin K pseudo all-atom top-32 refinement lane.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--branch-summary-json", default=DEFAULT_BRANCH_SUMMARY_JSON)
    parser.add_argument("--stage6-tuning-surface-json", default=DEFAULT_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.execution_queue_json),
        load_json(args.branch_summary_json),
        load_json(args.stage6_tuning_surface_json),
        top_n=args.top_n,
    )
    write_artifact(args.out_md, "Wet-Lab Cathepsin K All-Atom Refinement Lane", payload)


if __name__ == "__main__":
    main()
