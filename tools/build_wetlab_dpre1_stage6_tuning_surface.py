#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_stage6_tuning_utils import build_stage6_tuning_payload
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

TARGET_ID = "DprE1"
TARGET_SLUG = "dpre1"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_OUT_MD = "runs/wetlab_dpre1_stage6_tuning_surface_current.md"


def build_payload(execution_queue_payload: dict, throughput_bridge_payload: dict) -> dict:
    payload = build_stage6_tuning_payload(
        target_id=TARGET_ID,
        target_slug=TARGET_SLUG,
        status="wetlab_dpre1_stage6_tuning_surface_ready",
        execution_queue_payload=execution_queue_payload,
        throughput_bridge_payload=throughput_bridge_payload,
        maybe_load_json=maybe_load_json,
        candidate_thresholds=[
            ("candidate_5.0", 5.0),
            ("candidate_5.05", 5.05),
            ("candidate_5.1", 5.1),
            ("candidate_5.5", 5.5),
        ],
        next_step_template=(
            "Run the {target_id} exploratory gate5.1 retry for {shard_id}; "
            "use gate5.1 as the immediately runnable family for the observed {recommended_threshold}A band "
            "and keep the default lane closed until the result is reviewed."
        ),
    )
    payload["structured"] = {
        "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
        "throughput_bridge_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
    }
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the DprE1 stage6 tuning surface.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--throughput-bridge-json", default=DEFAULT_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab DprE1 Stage6 Tuning Surface",
        build_payload(load_json(args.execution_queue_json), load_json(args.throughput_bridge_json)),
    )


if __name__ == "__main__":
    main()
