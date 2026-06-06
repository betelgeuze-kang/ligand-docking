#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_stage6_tuning_utils import build_stage6_tuning_payload
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

TARGET_ID = "SARS-CoV-2 Mpro"
TARGET_SLUG = "sars_cov_2_mpro"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_OUT_MD = "runs/wetlab_sarscov2_mpro_stage6_tuning_surface_current.md"


def build_payload(execution_queue_payload: dict, throughput_bridge_payload: dict) -> dict:
    payload = build_stage6_tuning_payload(
        target_id=TARGET_ID,
        target_slug=TARGET_SLUG,
        status="wetlab_sarscov2_mpro_stage6_tuning_surface_ready",
        execution_queue_payload=execution_queue_payload,
        throughput_bridge_payload=throughput_bridge_payload,
        maybe_load_json=maybe_load_json,
        candidate_thresholds=[
            ("candidate_4.45", 4.45),
            ("candidate_4.5", 4.5),
            ("candidate_5.1", 5.1),
            ("candidate_5.5", 5.5),
        ],
        next_step_template=(
            "Keep the {target_id} default lane closed and reopen it only through the gate4.5 tuned retry family; "
            "the observed band is {recommended_threshold}A and the next staged retry is {shard_id}."
        ),
    )
    payload["structured"] = {
        "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
        "throughput_bridge_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
    }
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the SARS-CoV-2 Mpro stage6 tuning surface.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--throughput-bridge-json", default=DEFAULT_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab SARS-CoV-2 Mpro Stage6 Tuning Surface",
        build_payload(load_json(args.execution_queue_json), load_json(args.throughput_bridge_json)),
    )


if __name__ == "__main__":
    main()
