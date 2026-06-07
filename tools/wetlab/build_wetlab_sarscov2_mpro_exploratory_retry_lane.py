#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

TARGET_ID = "SARS-CoV-2 Mpro"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_sarscov2_mpro_stage6_tuning_bridge_current.json"
DEFAULT_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_sarscov2_mpro_stage6_tuning_surface_current.json"
DEFAULT_LEGACY_MAPPING_FIX_LANE_JSON = "runs/sarscov2_mpro_mapping_fix_retry_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_sarscov2_mpro_exploratory_retry_lane_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def _find_queue_row(payload: dict[str, Any]) -> dict[str, Any]:
    rows = [dict(row or {}) for row in (payload.get("rows", []) or [])]
    priority_statuses = {"ready_after_previous_shard", "running", "ready_first"}
    for row in rows:
        if _text(row.get("target_id")) == TARGET_ID and _text(row.get("queue_status")) in priority_statuses:
            return row
    return {}


def _find_bridge_row(payload: dict[str, Any], command_kind: str) -> dict[str, Any]:
    for row in payload.get("rows", []) or []:
        candidate = dict(row or {})
        if _text(candidate.get("command_kind")) == command_kind and _text(candidate.get("command")):
            return candidate
    return {}


def build_payload(
    execution_queue_payload: dict[str, Any],
    throughput_bridge_payload: dict[str, Any],
    stage6_tuning_surface_payload: dict[str, Any],
    legacy_mapping_fix_lane_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tuning_summary = _summary(stage6_tuning_surface_payload)
    queue_row = _find_queue_row(execution_queue_payload)
    legacy_summary = _summary(legacy_mapping_fix_lane_payload)
    selected_row = _find_bridge_row(throughput_bridge_payload, "throughput_preflight_tuned_gate45")
    selected_execute_row = _find_bridge_row(throughput_bridge_payload, "throughput_execute_tuned_gate45")

    shard_id = _text(queue_row.get("shard_id")) or _text(legacy_summary.get("shard_id")) or _text(tuning_summary.get("next_retry_shard_id"))
    queue_status = _text(queue_row.get("queue_status")) or "explicit_hold"
    selected_kind = _text(selected_row.get("command_kind"))
    selected_command = _text(selected_row.get("command"))
    ready = bool(selected_command and shard_id)
    running = bool(queue_status == "running" and selected_command)
    status = "wetlab_sarscov2_mpro_exploratory_retry_lane_running" if running else "wetlab_sarscov2_mpro_exploratory_retry_lane_ready"
    next_step = (
        f"Watch {TARGET_ID} {shard_id} through the primary watcher; keep the default lane closed until this gate4.5 candidate retry lands clean or is held again."
        if running and shard_id
        else f"Run the {TARGET_ID} exploratory gate4.5 retry for {shard_id}; use gate4.5 as the immediately runnable family for the observed {float(tuning_summary.get('recommended_observed_threshold_A', 0.0) or 0.0):.1f}A band and keep the default lane closed until the result is reviewed."
        if ready and shard_id
        else f"Keep the {TARGET_ID} default lane closed until the stage6 tuning surface selects a runnable retry shard."
    )
    return {
        "summary": {
            "status": status,
            "target_id": TARGET_ID,
            "shard_id": shard_id,
            "campaign_start_shard_id": _text(tuning_summary.get("campaign_start_shard_id")),
            "lane_label": "exploratory_gate4.5_candidate",
            "selected_command_kind": selected_kind,
            "selected_threshold_A": 4.5,
            "recommended_observed_threshold_A": float(tuning_summary.get("recommended_observed_threshold_A", 0.0) or 0.0),
            "recommended_retry_mode": "guarded_tuned_gate45_candidate",
            "throughput_execute_ready": bool(_text(selected_execute_row.get("command_kind"))),
            "queue_status": queue_status,
            "ready_for_manual_retry": ready,
            "next_required_step": next_step,
        },
        "structured": {
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "throughput_bridge_artifact": "runs/wetlab_sarscov2_mpro_stage6_tuning_bridge_current.md",
            "stage6_tuning_surface_artifact": "runs/wetlab_sarscov2_mpro_stage6_tuning_surface_current.md",
            "legacy_mapping_fix_lane_artifact": "runs/sarscov2_mpro_mapping_fix_retry_lane_current.md",
        },
        "rows": [
            {
                "row_kind": "exploratory_retry_selection",
                "target_id": TARGET_ID,
                "shard_id": shard_id,
                "lane_label": "exploratory_gate4.5_candidate",
                "selected_command_kind": selected_kind,
                "selected_threshold_A": 4.5,
                "recommended_observed_threshold_A": float(tuning_summary.get("recommended_observed_threshold_A", 0.0) or 0.0),
                "command": selected_command,
                "queue_status": queue_status,
                "ready_for_manual_retry": ready,
            }
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the SARS-CoV-2 Mpro exploratory retry lane.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--throughput-bridge-json", default=DEFAULT_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--stage6-tuning-surface-json", default=DEFAULT_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--legacy-mapping-fix-lane-json", default=DEFAULT_LEGACY_MAPPING_FIX_LANE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab SARS-CoV-2 Mpro Exploratory Retry Lane",
        build_payload(
            load_json(args.execution_queue_json),
            load_json(args.throughput_bridge_json),
            load_json(args.stage6_tuning_surface_json),
            maybe_load_json(args.legacy_mapping_fix_lane_json),
        ),
    )


if __name__ == "__main__":
    main()
