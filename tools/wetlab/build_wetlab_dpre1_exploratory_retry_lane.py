#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

TARGET_ID = "DprE1"
DEFAULT_HOLD_GUARD_JSON = "runs/wetlab_primary_hold_guard_surface_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_dpre1_stage6_tuning_surface_current.json"
DEFAULT_OUT_MD = "runs/wetlab_dpre1_exploratory_retry_lane_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {None, ""}:
            return default
        return int(value)
    except Exception:
        return default


def _find_guard_row(payload: dict[str, Any]) -> dict[str, Any]:
    for row in payload.get("rows", []) or []:
        candidate = dict(row or {})
        if _text(candidate.get("target_id")) == TARGET_ID:
            return candidate
    return {}


def _find_queue_row(payload: dict[str, Any]) -> dict[str, Any]:
    rows = [dict(row or {}) for row in (payload.get("rows", []) or [])]
    for row in rows:
        if _text(row.get("target_id")) == TARGET_ID and _text(row.get("queue_status")) in {"ready_after_previous_shard", "running", "ready_first"}:
            return row
    for row in rows:
        if _text(row.get("target_id")) == TARGET_ID:
            return row
    return {}


def _find_bridge_row(payload: dict[str, Any], command_kind: str) -> dict[str, Any]:
    for row in payload.get("rows", []) or []:
        candidate = dict(row or {})
        if _text(candidate.get("command_kind")) == command_kind and _text(candidate.get("command")):
            return candidate
    return {}


def _selected_gate_row(throughput_bridge_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], float, str]:
    gate51_row = _find_bridge_row(throughput_bridge_payload, "throughput_preflight_tuned_gate51")
    gate51_execute_row = _find_bridge_row(throughput_bridge_payload, "throughput_execute_tuned_gate51")
    if _text(gate51_row.get("command")):
        return gate51_row, gate51_execute_row, 5.1, "exploratory_gate5.1_candidate"
    gate55_row = _find_bridge_row(throughput_bridge_payload, "throughput_preflight_tuned_gate55")
    gate55_execute_row = _find_bridge_row(throughput_bridge_payload, "throughput_execute_tuned_gate55")
    return gate55_row, gate55_execute_row, 5.5, "exploratory_gate5.5_candidate"


def _gate_label(threshold: float) -> str:
    return "gate5.1" if abs(threshold - 5.1) < 0.01 else "gate55"


def build_payload(
    hold_guard_payload: dict[str, Any],
    execution_queue_payload: dict[str, Any],
    throughput_bridge_payload: dict[str, Any],
    stage6_tuning_surface_payload: dict[str, Any],
) -> dict[str, Any]:
    hold_summary = _summary(hold_guard_payload)
    tuning_summary = _summary(stage6_tuning_surface_payload)
    guard_row = _find_guard_row(hold_guard_payload)
    queue_row = _find_queue_row(execution_queue_payload)
    selected_row, selected_execute_row, selected_threshold, lane_label = _selected_gate_row(throughput_bridge_payload)

    shard_id = _text(queue_row.get("shard_id")) or _text(tuning_summary.get("next_retry_shard_id"))
    queue_status = _text(queue_row.get("queue_status"))
    selected_kind = _text(selected_row.get("command_kind"))
    selected_command = _text(selected_row.get("command"))
    ready = bool(
        _text(guard_row.get("recommended_policy_action")) == "pause_target_autostart_and_review_retry_preset"
        and queue_status in {"ready_after_previous_shard", "ready_first"}
        and selected_command
    )
    running = bool(queue_status == "running" and selected_command)
    status = "wetlab_dpre1_exploratory_retry_lane_running" if running else "wetlab_dpre1_exploratory_retry_lane_ready"

    threshold = float(tuning_summary.get("recommended_observed_threshold_A", 0.0) or 0.0)
    next_step = (
        f"Watch {TARGET_ID} {shard_id} through the primary watcher; keep the default lane closed until this {_gate_label(selected_threshold)} candidate retry lands clean or is held again."
        if running and shard_id
        else f"Run the {TARGET_ID} exploratory {_gate_label(selected_threshold)} retry for {shard_id}; use {_gate_label(selected_threshold)} as the immediately runnable family for the observed {threshold:.2f}A band and keep the default lane closed until the result is reviewed."
        if ready and shard_id
        else f"Keep the {TARGET_ID} default lane paused and refresh the stage6 tuning surface before retrying."
    )

    return {
        "summary": {
            "status": status,
            "target_id": TARGET_ID,
            "shard_id": shard_id,
            "campaign_start_shard_id": _text(tuning_summary.get("campaign_start_shard_id")),
            "lane_label": lane_label,
            "guard_active": bool(_text(guard_row.get("target_id"))),
            "guard_limit": _safe_int(hold_summary.get("guard_limit"), 0),
            "guard_hold_streak": _safe_int(guard_row.get("recent_consecutive_auto_hold_streak"), 0),
            "selected_command_kind": selected_kind,
            "selected_threshold_A": selected_threshold,
            "recommended_observed_threshold_A": threshold,
            "recommended_retry_mode": "guarded_tuned_gate51_candidate" if abs(selected_threshold - 5.1) < 0.01 else "guarded_tuned_gate55_candidate",
            "throughput_execute_ready": bool(_text(selected_execute_row.get("command_kind"))),
            "queue_status": queue_status,
            "ready_for_manual_retry": ready,
            "next_required_step": next_step,
        },
        "structured": {
            "hold_guard_artifact": "runs/wetlab_primary_hold_guard_surface_current.md",
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "throughput_bridge_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
            "stage6_tuning_surface_artifact": "runs/wetlab_dpre1_stage6_tuning_surface_current.md",
        },
        "rows": [
            {
                "row_kind": "exploratory_retry_selection",
                "target_id": TARGET_ID,
                "shard_id": shard_id,
                "lane_label": lane_label,
                "selected_command_kind": selected_kind,
                "selected_threshold_A": selected_threshold,
                "recommended_observed_threshold_A": threshold,
                "command": selected_command,
                "queue_status": queue_status,
                "ready_for_manual_retry": ready,
            }
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the DprE1 exploratory observed-band retry lane.")
    parser.add_argument("--hold-guard-json", default=DEFAULT_HOLD_GUARD_JSON)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--throughput-bridge-json", default=DEFAULT_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--stage6-tuning-surface-json", default=DEFAULT_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab DprE1 Exploratory Retry Lane",
        build_payload(
            load_json(args.hold_guard_json),
            load_json(args.execution_queue_json),
            load_json(args.throughput_bridge_json),
            load_json(args.stage6_tuning_surface_json),
        ),
    )


if __name__ == "__main__":
    main()
