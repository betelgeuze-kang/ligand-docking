#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from tools import run_wetlab_broad_screen_primary_runner as primary_runner_mod
from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LANE_JSON = "runs/wetlab_mapping_fix_retry_lane_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_TARGET_NATIVE_CSV = "config/real_drug_targets_native_v1.csv"
DEFAULT_OUT_MD = "runs/wetlab_mapping_fix_retry_runner_current.md"
TARGET_LANE_JSON_BY_ID = {
    "SARS-CoV-2 Mpro": "runs/sarscov2_mpro_mapping_fix_retry_lane_current.json",
    "T. cruzi PDE": "runs/tcruzi_pde_mapping_fix_retry_lane_current.json",
}


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _resolve_lane_json(target_id: str, lane_json: str) -> str:
    requested = Path(lane_json)
    if requested.exists():
        return str(requested)
    mapped = TARGET_LANE_JSON_BY_ID.get(str(target_id or "").strip(), "")
    if not mapped:
        return lane_json
    mapped_path = ROOT / mapped
    return str(mapped_path) if mapped_path.exists() else lane_json


def run(
    *,
    lane_json: str,
    python_bin: str,
    target_id: str,
    shard_id: str,
    command_kind: str,
    execution_queue_json: str,
    compound_universe_json: str,
    portfolio_json: str,
    target_native_csv: str,
    interval_sec: float,
    replace_heartbeat: bool,
    out_md: str = DEFAULT_OUT_MD,
) -> dict[str, Any]:
    selected_target = str(target_id or "").strip()
    resolved_lane_json = _resolve_lane_json(selected_target, lane_json)
    lane_payload = load_json(resolved_lane_json)
    summary = _summary(lane_payload)
    selected_target = selected_target or str(summary.get("target_id", "")).strip()
    if resolved_lane_json != lane_json and not summary:
        resolved_lane_json = _resolve_lane_json(selected_target, lane_json)
        lane_payload = load_json(resolved_lane_json)
        summary = _summary(lane_payload)
    selected_shard = shard_id or str(summary.get("shard_id", "")).strip()
    selected_kind = command_kind or str(summary.get("selected_command_kind", "")).strip()
    if not bool(summary.get("ready_for_mapping_fix_retry", False)):
        raise SystemExit("mapping-fix retry lane is not ready_for_mapping_fix_retry")
    if not selected_target:
        raise SystemExit("no target_id available for mapping-fix retry")
    if not selected_shard:
        raise SystemExit("no shard_id available for mapping-fix retry")
    if not selected_kind:
        raise SystemExit("no selected command kind available for mapping-fix retry")

    execution_queue = load_json(execution_queue_json)
    compound_universe = load_json(compound_universe_json)
    portfolio = load_json(portfolio_json)
    primary_runner_mod.prepare_fresh_stage_artifacts(
        target_id=selected_target,
        shard_id=selected_shard,
        execution_queue=execution_queue,
        compound_universe=compound_universe,
        portfolio=portfolio,
        target_native_csv=target_native_csv,
        clear_stage_artifacts=True,
    )

    runner_payload = primary_runner_mod.run(
        target_id=selected_target,
        shard_id=selected_shard,
        python_bin=python_bin,
        command_kind=selected_kind,
        execution_queue_json=execution_queue_json,
        compound_universe_json=compound_universe_json,
        portfolio_json=portfolio_json,
        target_native_csv=target_native_csv,
        interval_sec=interval_sec,
        replace_heartbeat=replace_heartbeat,
    )

    payload = {
        "summary": {
            "status": "wetlab_mapping_fix_retry_runner_ready",
            "target_id": selected_target,
            "shard_id": selected_shard,
            "selected_command_kind": selected_kind,
            "mapping_fix_launch_completed": True,
            "next_required_step": (
                f"Watch {selected_target} {selected_shard} through the primary watcher; only reopen broader auto-start policy if this mapping-fix retry lands clean."
            ),
        },
        "structured": {
            "mapping_fix_retry_lane_artifact": resolved_lane_json,
            "primary_runner_artifact": "runs/wetlab_broad_screen_primary_runner_current.md",
        },
        "rows": [
            {
                "target_id": selected_target,
                "shard_id": selected_shard,
                "selected_command_kind": selected_kind,
                "compute_pid": _summary(runner_payload).get("compute_pid", 0),
                "heartbeat_pid": _summary(runner_payload).get("heartbeat_pid", 0),
            }
        ],
    }
    write_artifact(out_md, "Wet-Lab Mapping-Fix Retry Runner", payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the guarded mapping-fix retry lane for a primary broad-screen target.")
    parser.add_argument("--lane-json", default=DEFAULT_LANE_JSON)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--target-id", default="")
    parser.add_argument("--shard-id", default="")
    parser.add_argument("--command-kind", default="")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--compound-universe-json", default=DEFAULT_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--target-native-csv", default=DEFAULT_TARGET_NATIVE_CSV)
    parser.add_argument("--interval-sec", type=float, default=30.0)
    parser.add_argument("--replace-heartbeat", action="store_true")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(
        lane_json=args.lane_json,
        python_bin=args.python_bin,
        target_id=args.target_id,
        shard_id=args.shard_id,
        command_kind=args.command_kind,
        execution_queue_json=args.execution_queue_json,
        compound_universe_json=args.compound_universe_json,
        portfolio_json=args.portfolio_json,
        target_native_csv=args.target_native_csv,
        interval_sec=args.interval_sec,
        replace_heartbeat=args.replace_heartbeat,
        out_md=args.out_md,
    )


if __name__ == "__main__":
    main()
