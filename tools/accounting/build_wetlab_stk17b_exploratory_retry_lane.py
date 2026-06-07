#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

TARGET_ID = "STK17B (DRAK2)"
DEFAULT_MANUAL_RETRY_LANE_JSON = "runs/wetlab_stk17b_manual_retry_lane_current.json"
DEFAULT_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_stk17b_stage6_tuning_surface_current.json"
DEFAULT_OUT_MD = "runs/wetlab_stk17b_exploratory_retry_lane_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def _find_command_row(bridge_payload: dict[str, Any], command_kind: str) -> dict[str, Any]:
    for row in bridge_payload.get("rows", []) or []:
        candidate = dict(row or {})
        if _text(candidate.get("command_kind")) == command_kind:
            return candidate
    return {}


def build_payload(
    manual_retry_lane_payload: dict[str, Any],
    throughput_bridge_payload: dict[str, Any],
    stage6_tuning_surface_payload: dict[str, Any],
) -> dict[str, Any]:
    manual_summary = _summary(manual_retry_lane_payload)
    bridge_summary = _summary(throughput_bridge_payload)
    tuning_summary = _summary(stage6_tuning_surface_payload)
    target_id = _text(manual_summary.get("target_id")) or TARGET_ID
    shard_id = _text(manual_summary.get("shard_id"))
    command_row = _find_command_row(throughput_bridge_payload, "throughput_preflight_tuned_gate45")
    command_kind = _text(command_row.get("command_kind"))
    command = _text(command_row.get("command"))
    ready = (
        target_id == TARGET_ID
        and bool(manual_summary.get("guard_active", False))
        and bool(manual_summary.get("ready_for_manual_retry", False))
        and bool(command)
    )
    recommended_threshold = float(tuning_summary.get("recommended_relaxed_threshold_A", 0.0) or 0.0)
    exploratory_threshold = float(tuning_summary.get("exploratory_median_threshold_A", 0.0) or 0.0)
    return {
        "summary": {
            "status": "wetlab_stk17b_exploratory_retry_lane_ready",
            "target_id": target_id,
            "shard_id": shard_id,
            "campaign_start_shard_id": _text(manual_summary.get("campaign_start_shard_id")) or shard_id,
            "guard_active": bool(manual_summary.get("guard_active", False)),
            "selected_command_kind": command_kind,
            "selected_threshold_A": 4.5,
            "recommended_relaxed_threshold_A": recommended_threshold,
            "exploratory_median_threshold_A": exploratory_threshold,
            "throughput_execute_ready": bool(bridge_summary.get("throughput_execute_ready", False)),
            "ready_for_manual_retry": ready,
            "next_required_step": (
                f"Run the STK17B exploratory gate4.5 manual retry runner for {shard_id}; compare the outcome against the retry campaign band before relaxing broader kinase gates."
                if ready
                else "STK17B exploratory gate4.5 retry is not ready yet; refresh the bridge and tuning surface first."
            ),
        },
        "structured": {
            "manual_retry_lane_artifact": "runs/wetlab_stk17b_manual_retry_lane_current.md",
            "throughput_bridge_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
            "stage6_tuning_surface_artifact": "runs/wetlab_stk17b_stage6_tuning_surface_current.md",
            "selected_summary_json": _text((throughput_bridge_payload.get("structured", {}) or {}).get("preferred_summary_json")),
        },
        "rows": [
            {
                "row_kind": "exploratory_retry_selection",
                "target_id": target_id,
                "shard_id": shard_id,
                "selected_command_kind": command_kind,
                "selected_threshold_A": 4.5,
                "recommended_relaxed_threshold_A": recommended_threshold,
                "exploratory_median_threshold_A": exploratory_threshold,
                "command": command,
                "ready_for_manual_retry": ready,
            }
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the STK17B exploratory gate4.5 retry lane.")
    parser.add_argument("--manual-retry-lane-json", default=DEFAULT_MANUAL_RETRY_LANE_JSON)
    parser.add_argument("--throughput-bridge-json", default=DEFAULT_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--stage6-tuning-surface-json", default=DEFAULT_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab STK17B Exploratory Retry Lane",
        build_payload(
            load_json(args.manual_retry_lane_json),
            load_json(args.throughput_bridge_json),
            load_json(args.stage6_tuning_surface_json),
        ),
    )


if __name__ == "__main__":
    main()
