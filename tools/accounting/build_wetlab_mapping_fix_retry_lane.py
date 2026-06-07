#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tools import build_wetlab_broad_screen_throughput_bridge as bridge_mod
from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RETRY_PRESET_JSON = "runs/wetlab_primary_retry_preset_surface_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_TARGET_NATIVE_CSV = "config/real_drug_targets_native_v1.csv"
DEFAULT_OUT_MD = "runs/wetlab_mapping_fix_retry_lane_current.md"
DEFAULT_TARGETS = ("SARS-CoV-2 Mpro", "T. cruzi PDE")
COMMAND_PREFERENCE = [
    "throughput_preflight",
    "throughput_preflight_tuned",
    "throughput_preflight_tuned_gate55",
]


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _find_retry_row(retry_preset_payload: dict[str, Any], target_id: str) -> dict[str, Any]:
    for row in retry_preset_payload.get("rows", []) or []:
        candidate = dict(row)
        if _text(candidate.get("target_id")) == _text(target_id):
            return candidate
    return {}


def _find_queue_row(execution_queue_payload: dict[str, Any], target_id: str, shard_id: str) -> dict[str, Any]:
    for row in execution_queue_payload.get("rows", []) or []:
        candidate = dict(row)
        if _text(candidate.get("target_id")) == _text(target_id) and _text(candidate.get("shard_id")) == _text(shard_id):
            return candidate
    return {}


def _select_bridge_rows(bridge_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = [dict(row) for row in (bridge_payload.get("rows", []) or [])]
    selected: dict[str, Any] = {}
    follow_on_execute: dict[str, Any] = {}
    for kind in COMMAND_PREFERENCE:
        for row in rows:
            if _text(row.get("command_kind")) == kind and bool(row.get("enabled", False)):
                selected = row
                break
        if selected:
            break
    if selected:
        execute_kind = _text(selected.get("command_kind")).replace("preflight", "execute", 1)
        for row in rows:
            if _text(row.get("command_kind")) == execute_kind:
                follow_on_execute = row
                break
    return selected, follow_on_execute


def build_payload(
    *,
    retry_preset_payload: dict[str, Any],
    execution_queue_payload: dict[str, Any],
    compound_universe_payload: dict[str, Any],
    portfolio_payload: dict[str, Any],
    target_native_csv: str,
    target_id: str,
    lane_artifact_md: str = DEFAULT_OUT_MD,
) -> dict[str, Any]:
    retry_summary = _summary(retry_preset_payload)
    retry_row = _find_retry_row(retry_preset_payload, target_id)
    shard_id = _text(retry_row.get("representative_stage1_mapping_failure_shard_id")) or _text(
        retry_row.get("representative_stage6_failure_shard_id")
    )
    queue_row = _find_queue_row(execution_queue_payload, target_id, shard_id)
    bridge_payload = bridge_mod.build_payload(
        execution_queue=execution_queue_payload,
        compound_universe=compound_universe_payload,
        portfolio=portfolio_payload,
        target_native_csv=target_native_csv,
        target_id=target_id,
        shard_id=shard_id,
    )
    bridge_summary = _summary(bridge_payload)
    selected_command_row, follow_on_execute_row = _select_bridge_rows(bridge_payload)
    selected_kind = _text(selected_command_row.get("command_kind"))
    selected_command = _text(selected_command_row.get("command"))
    follow_on_execute_kind = _text(follow_on_execute_row.get("command_kind"))
    follow_on_execute_command = _text(follow_on_execute_row.get("command"))
    lane_artifact_path = Path(lane_artifact_md)
    if not lane_artifact_path.is_absolute():
        lane_artifact_path = ROOT / lane_artifact_path
    ready_for_mapping_fix_retry = bool(
        _text(retry_row.get("recommended_retry_mode")) == "mapping_fix_required"
        and shard_id
        and selected_command
    )
    runner_command = (
        f'python3 tools/run_wetlab_mapping_fix_retry.py --target-id "{target_id}" --lane-json "{lane_artifact_path}" --replace-heartbeat'
        if ready_for_mapping_fix_retry
        else ""
    )
    next_step = (
        f"Run the mapping-fix retry runner for {target_id} {shard_id}; keep auto-start blocked until the mapping diagnostics rerun lands a clean summary."
        if ready_for_mapping_fix_retry
        else f"Keep {target_id} blocked; no enabled mapping-fix retry command is available yet."
    )
    return {
        "summary": {
            "status": "wetlab_mapping_fix_retry_lane_ready",
            "target_id": target_id,
            "shard_id": shard_id,
            "recommended_retry_mode": _text(retry_row.get("recommended_retry_mode")),
            "stage1_mapping_failed_count": _safe_int(retry_row.get("stage1_mapping_failed_count", 0)),
            "stage6_distance_gate_failed_count": _safe_int(retry_row.get("stage6_distance_gate_failed_count", 0)),
            "guard_limit": _safe_int(retry_summary.get("guard_limit", 0)),
            "selected_command_kind": selected_kind,
            "throughput_execute_ready": bool(bridge_summary.get("throughput_execute_ready", False)),
            "ready_for_mapping_fix_retry": ready_for_mapping_fix_retry,
            "next_required_step": next_step,
        },
        "structured": {
            "retry_preset_artifact": "runs/wetlab_primary_retry_preset_surface_current.md",
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "throughput_bridge_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
            "lane_artifact": str(lane_artifact_path),
            "selected_bridge_summary_json": _text((bridge_payload.get("structured", {}) or {}).get("preferred_summary_json")),
        },
        "rows": [
            {
                "row_kind": "retry_selection",
                "target_id": target_id,
                "shard_id": shard_id,
                "queue_status": _text(queue_row.get("queue_status")),
                "recommended_retry_mode": _text(retry_row.get("recommended_retry_mode")),
                "one_line_summary": next_step,
            },
            {
                "row_kind": "runner_command",
                "target_id": target_id,
                "shard_id": shard_id,
                "command_kind": "mapping_fix_retry_runner",
                "command": runner_command,
            },
            {
                "row_kind": "selected_bridge_command",
                "target_id": target_id,
                "shard_id": shard_id,
                "command_kind": selected_kind,
                "command": selected_command,
            },
            {
                "row_kind": "follow_on_execute_command",
                "target_id": target_id,
                "shard_id": shard_id,
                "command_kind": follow_on_execute_kind,
                "command": follow_on_execute_command,
            },
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a mapping-fix retry lane for a target blocked by stage1 ligand mapping failures.")
    parser.add_argument("--target-id", required=True, choices=list(DEFAULT_TARGETS))
    parser.add_argument("--retry-preset-json", default=DEFAULT_RETRY_PRESET_JSON)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--compound-universe-json", default=DEFAULT_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--target-native-csv", default=DEFAULT_TARGET_NATIVE_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        retry_preset_payload=load_json(args.retry_preset_json),
        execution_queue_payload=load_json(args.execution_queue_json),
        compound_universe_payload=load_json(args.compound_universe_json),
        portfolio_payload=load_json(args.portfolio_json),
        target_native_csv=args.target_native_csv,
        target_id=args.target_id,
        lane_artifact_md=args.out_md,
    )
    write_artifact(args.out_md, f"{args.target_id} Mapping-Fix Retry Lane", payload)


if __name__ == "__main__":
    main()
