#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from typing import Any

from tools.wetlab import build_wetlab_dpre1_exploratory_retry_lane as lane_mod
from tools import run_wetlab_broad_screen_primary_runner as primary_runner_mod
from tools.wetlab_target_render_utils import load_json, write_artifact

TARGET_ID = "DprE1"
DEFAULT_LANE_JSON = "runs/wetlab_dpre1_exploratory_retry_lane_current.json"
DEFAULT_HOLD_GUARD_JSON = "runs/wetlab_primary_hold_guard_surface_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_TARGET_NATIVE_CSV = "config/real_drug_targets_native_v1.csv"
DEFAULT_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_dpre1_stage6_tuning_surface_current.json"
DEFAULT_OUT_MD = "runs/wetlab_dpre1_exploratory_retry_runner_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _gate_label(command_kind: str) -> str:
    text = str(command_kind or "").strip()
    if "gate51" in text:
        return "gate5.1"
    if "gate55" in text:
        return "gate55"
    return "observed-band"


def _prefer_execute_command_kind(selected_kind: str, lane_summary: dict[str, Any], *, preflight_only: bool) -> str:
    if preflight_only:
        return selected_kind
    if not bool(lane_summary.get("throughput_execute_ready", False)):
        return selected_kind
    text = str(selected_kind or "").strip()
    if not text.startswith("throughput_preflight"):
        return text
    return text.replace("throughput_preflight", "throughput_execute", 1)


def run(
    *,
    lane_json: str,
    hold_guard_json: str,
    python_bin: str,
    shard_id: str,
    command_kind: str,
    execution_queue_json: str,
    throughput_bridge_json: str,
    compound_universe_json: str,
    portfolio_json: str,
    stage6_tuning_surface_json: str,
    target_native_csv: str,
    interval_sec: float,
    replace_heartbeat: bool,
    preflight_only: bool = False,
    refresh_lane: bool = True,
) -> dict[str, Any]:
    if refresh_lane:
        lane_payload = lane_mod.build_payload(
            load_json(hold_guard_json),
            load_json(execution_queue_json),
            load_json(throughput_bridge_json),
            load_json(stage6_tuning_surface_json),
        )
        write_artifact(lane_json.replace(".json", ".md"), "Wet-Lab DprE1 Exploratory Retry Lane", lane_payload)
    else:
        lane_payload = load_json(lane_json)
    summary = _summary(lane_payload)
    target_id = str(summary.get("target_id", TARGET_ID)).strip() or TARGET_ID
    selected_shard = shard_id or str(summary.get("shard_id", "")).strip()
    selected_kind = command_kind or str(summary.get("selected_command_kind", "")).strip()
    if target_id != TARGET_ID:
        raise SystemExit(f"exploratory retry lane target mismatch: expected {TARGET_ID}, got {target_id}")
    if not bool(summary.get("ready_for_manual_retry", False)):
        raise SystemExit("DprE1 exploratory retry lane is not ready_for_manual_retry")
    if not selected_shard:
        raise SystemExit("no shard_id available for DprE1 exploratory retry")
    if not selected_kind:
        raise SystemExit("no selected command kind available for DprE1 exploratory retry")
    launch_kind = _prefer_execute_command_kind(selected_kind, summary, preflight_only=preflight_only)

    runner_payload = primary_runner_mod.run(
        target_id=target_id,
        shard_id=selected_shard,
        python_bin=python_bin,
        command_kind=launch_kind,
        execution_queue_json=execution_queue_json,
        compound_universe_json=compound_universe_json,
        portfolio_json=portfolio_json,
        target_native_csv=target_native_csv,
        interval_sec=interval_sec,
        replace_heartbeat=replace_heartbeat,
    )

    payload = {
        "summary": {
            "status": "wetlab_dpre1_exploratory_retry_runner_ready",
            "target_id": target_id,
            "shard_id": selected_shard,
            "selected_command_kind": selected_kind,
            "launched_command_kind": launch_kind,
            "guarded_launch_completed": True,
            "next_required_step": f"Watch {target_id} {selected_shard} through the primary watcher; keep the default lane closed until this {_gate_label(launch_kind)} candidate retry lands clean or is held again.",
        },
        "structured": {
            "exploratory_retry_lane_artifact": "runs/wetlab_dpre1_exploratory_retry_lane_current.md",
            "primary_runner_artifact": "runs/wetlab_broad_screen_primary_runner_current.md",
        },
        "rows": [
            {
                "target_id": target_id,
                "shard_id": selected_shard,
                "selected_command_kind": selected_kind,
                "launched_command_kind": launch_kind,
                "compute_pid": _summary(runner_payload).get("compute_pid", 0),
                "heartbeat_pid": _summary(runner_payload).get("heartbeat_pid", 0),
            }
        ],
    }
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab DprE1 Exploratory Retry Runner", payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the DprE1 exploratory observed-band retry lane.")
    parser.add_argument("--lane-json", default=DEFAULT_LANE_JSON)
    parser.add_argument("--hold-guard-json", default=DEFAULT_HOLD_GUARD_JSON)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--shard-id", default="")
    parser.add_argument("--command-kind", default="")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--throughput-bridge-json", default=DEFAULT_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--compound-universe-json", default=DEFAULT_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--stage6-tuning-surface-json", default=DEFAULT_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--target-native-csv", default=DEFAULT_TARGET_NATIVE_CSV)
    parser.add_argument("--interval-sec", type=float, default=30.0)
    parser.add_argument("--replace-heartbeat", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--no-refresh-lane", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(
        lane_json=args.lane_json,
        hold_guard_json=args.hold_guard_json,
        python_bin=args.python_bin,
        shard_id=args.shard_id,
        command_kind=args.command_kind,
        execution_queue_json=args.execution_queue_json,
        throughput_bridge_json=args.throughput_bridge_json,
        compound_universe_json=args.compound_universe_json,
        portfolio_json=args.portfolio_json,
        stage6_tuning_surface_json=args.stage6_tuning_surface_json,
        target_native_csv=args.target_native_csv,
        interval_sec=args.interval_sec,
        replace_heartbeat=args.replace_heartbeat,
        preflight_only=args.preflight_only,
        refresh_lane=not args.no_refresh_lane,
    )


if __name__ == "__main__":
    main()
