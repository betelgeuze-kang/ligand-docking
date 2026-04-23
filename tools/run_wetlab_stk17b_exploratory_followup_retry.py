#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from tools import build_wetlab_broad_screen_throughput_bridge as bridge_mod
from tools import run_wetlab_broad_screen_primary_watch as primary_watch_mod
from tools import run_wetlab_broad_screen_primary_runner as primary_runner_mod
from tools.wetlab_broad_screen_watch_utils import (
    canonicalize_preferred_summary,
    detect_throughput_summary,
    primary_bridge_paths,
    process_alive,
    primary_active_row,
    stop_pid_file,
    throughput_failed,
    throughput_ok,
)
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

TARGET_ID = "STK17B (DRAK2)"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LANE_JSON = "runs/wetlab_stk17b_exploratory_followup_lane_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_TARGET_NATIVE_CSV = "config/real_drug_targets_native_v1.csv"
DEFAULT_OUT_MD = "runs/wetlab_stk17b_exploratory_followup_retry_runner_current.md"
DEFAULT_SETTLE_TIMEOUT_SEC = 180.0
DEFAULT_SETTLE_POLL_SEC = 2.0
DEFAULT_PRIMARY_WATCH_LOOP_PID = "runs/wetlab_broad_screen_primary_watch_loop.pid"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(*values: Any) -> str:
    for value in values:
        if value not in {None, ""}:
            return str(value).strip()
    return ""


def _followup_shard_ids(summary: dict[str, Any]) -> list[str]:
    return [part.strip() for part in str(summary.get("followup_shard_ids", "") or "").split(";") if part.strip()]


def _canonical_followup_command_kind(command_kind: str) -> str:
    selected = _text(command_kind)
    if not selected:
        return "throughput_preflight_tuned_gate45"
    if "gate45" not in selected:
        raise SystemExit(f"STK17B exploratory follow-up retry must use a gate45 command, got: {selected}")
    return selected


def _resolve_followup_shard(summary: dict[str, Any], explicit_shard_id: str) -> tuple[str, bool]:
    allowed_ids = _followup_shard_ids(summary)
    if explicit_shard_id:
        if explicit_shard_id not in allowed_ids:
            raise SystemExit(
                f"explicit shard_id {explicit_shard_id} is not in STK17B exploratory follow-up lane ids: {';'.join(allowed_ids)}"
            )
        return explicit_shard_id, True
    selected_shard = _text(summary.get("shard_id"))
    if selected_shard:
        return selected_shard, bool(summary.get("ready_for_manual_retry", False))
    raise SystemExit("no shard_id available for STK17B exploratory follow-up retry")


def _current_queue_status(execution_queue_json: str, target_id: str, shard_id: str) -> str:
    payload = maybe_load_json(execution_queue_json) or {}
    for row in payload.get("rows", []) or []:
        if _text((row or {}).get("target_id")) == target_id and _text((row or {}).get("shard_id")) == shard_id:
            return _text((row or {}).get("queue_status"))
    return ""


def _archive_existing_followup_artifacts(shard_id: str) -> list[str]:
    artifact_dir = ROOT / "runs" / "wetlab_broad_screen_throughput" / "stk17b_drak2" / shard_id
    archived: list[str] = []
    if not artifact_dir.exists():
        return archived
    suffix = ".pre_gate45_followup_rerun"
    for path in sorted(artifact_dir.iterdir()):
        if not path.is_file():
            continue
        if not (
            path.name.startswith("throughput_run")
            and (path.name.endswith("_summary.json") or path.name.endswith("_summary.md"))
        ):
            continue
        archived_path = path.with_name(path.name + suffix)
        if archived_path.exists():
            archived_path.unlink()
        path.rename(archived_path)
        archived.append(str(archived_path))
    return archived


def _settle_followup_run(
    *,
    python_bin: str,
    target_id: str,
    shard_id: str,
    execution_queue_json: str,
    compound_universe_json: str,
    portfolio_json: str,
    target_native_csv: str,
    settle_timeout_sec: float,
    settle_poll_sec: float,
) -> dict[str, Any]:
    deadline = time.time() + max(settle_timeout_sec, settle_poll_sec, 1.0)
    last_summary_path = ""
    last_summary_payload: dict[str, Any] = {}
    last_watch_action: dict[str, Any] = {}
    while time.time() <= deadline:
        execution_queue = load_json(execution_queue_json)
        active_row = primary_active_row(execution_queue)
        queue_status = _current_queue_status(execution_queue_json, target_id, shard_id)
        if active_row and _text(active_row.get("target_id")) == target_id and _text(active_row.get("shard_id")) == shard_id:
            compound_universe = load_json(compound_universe_json)
            portfolio = maybe_load_json(portfolio_json) or load_json(portfolio_json)
            bridge_payload = bridge_mod.build_payload(
                execution_queue=execution_queue,
                compound_universe=compound_universe,
                portfolio=portfolio,
                target_native_csv=target_native_csv,
                target_id=target_id,
                shard_id=shard_id,
            )
            paths = primary_bridge_paths(bridge_payload)
            pid_alive, _pid = process_alive(paths.get("preferred_pid_path", ""))
            if pid_alive:
                time.sleep(max(settle_poll_sec, 0.5))
                continue
            canonicalize_preferred_summary(paths)
            summary_payload, detected_summary_path = detect_throughput_summary(paths)
            last_summary_payload = summary_payload
            last_summary_path = detected_summary_path or paths.get("preferred_summary_json", "")
            if throughput_ok(summary_payload) or throughput_failed(summary_payload) or paths.get("preferred_pid_path"):
                last_watch_action = primary_watch_mod.run_once(
                    python_bin=python_bin,
                    execution_queue_json=execution_queue_json,
                    compound_universe_json=compound_universe_json,
                    portfolio_json=portfolio_json,
                    target_native_csv=target_native_csv,
                    auto_start_next=False,
                )
                queue_status = _current_queue_status(execution_queue_json, target_id, shard_id)
                if queue_status and "running" not in queue_status:
                    return {
                        "settled": True,
                        "queue_status": queue_status,
                        "summary_path": last_summary_path,
                        "summary_payload": last_summary_payload,
                        "watch_action": _summary(last_watch_action),
                    }
        else:
            if queue_status and "running" not in queue_status:
                return {
                    "settled": True,
                    "queue_status": queue_status,
                    "summary_path": last_summary_path,
                    "summary_payload": last_summary_payload,
                    "watch_action": _summary(last_watch_action),
                }
        time.sleep(max(settle_poll_sec, 0.5))
    return {
        "settled": False,
        "queue_status": _current_queue_status(execution_queue_json, target_id, shard_id),
        "summary_path": last_summary_path,
        "summary_payload": last_summary_payload,
        "watch_action": _summary(last_watch_action),
    }


def run(
    *,
    lane_json: str,
    python_bin: str,
    shard_id: str,
    command_kind: str,
    execution_queue_json: str,
    compound_universe_json: str,
    portfolio_json: str,
    target_native_csv: str,
    interval_sec: float,
    replace_heartbeat: bool,
    settle_timeout_sec: float,
    settle_poll_sec: float,
) -> dict[str, Any]:
    lane_payload = load_json(lane_json)
    summary = _summary(lane_payload)
    target_id = _text(summary.get("target_id")) or TARGET_ID
    selected_shard, lane_ready = _resolve_followup_shard(summary, shard_id)
    selected_kind = _canonical_followup_command_kind(command_kind or _text(summary.get("selected_command_kind")))
    if target_id != TARGET_ID:
        raise SystemExit(f"exploratory follow-up lane target mismatch: expected {TARGET_ID}, got {target_id}")
    if not lane_ready and not shard_id:
        raise SystemExit("STK17B exploratory follow-up lane is not ready_for_manual_retry")
    stopped_background_watcher_pid = stop_pid_file(DEFAULT_PRIMARY_WATCH_LOOP_PID)
    archived_artifacts = _archive_existing_followup_artifacts(selected_shard)

    runner_payload = primary_runner_mod.run(
        target_id=target_id,
        shard_id=selected_shard,
        python_bin=python_bin,
        command_kind=selected_kind,
        execution_queue_json=execution_queue_json,
        compound_universe_json=compound_universe_json,
        portfolio_json=portfolio_json,
        target_native_csv=target_native_csv,
        interval_sec=interval_sec,
        replace_heartbeat=replace_heartbeat,
        launch_watcher=False,
    )
    settle_payload = _settle_followup_run(
        python_bin=python_bin,
        target_id=target_id,
        shard_id=selected_shard,
        execution_queue_json=execution_queue_json,
        compound_universe_json=compound_universe_json,
        portfolio_json=portfolio_json,
        target_native_csv=target_native_csv,
        settle_timeout_sec=settle_timeout_sec,
        settle_poll_sec=settle_poll_sec,
    )
    settle_summary = dict(settle_payload.get("watch_action", {}) or {})
    settle_action = _text(settle_summary.get("action_taken"))
    settled_queue_status = _text(settle_payload.get("queue_status"))
    detected_summary_path = _text(settle_payload.get("summary_path"))
    detected_summary_payload = dict(settle_payload.get("summary_payload", {}) or {})
    service_result = dict(detected_summary_payload.get("service_result", {}) or {})
    refreshed_lane_summary = _summary(maybe_load_json(lane_json) or {})

    payload = {
        "summary": {
            "status": "wetlab_stk17b_exploratory_followup_retry_runner_ready",
            "target_id": target_id,
            "shard_id": selected_shard,
            "selected_command_kind": selected_kind,
            "guarded_launch_completed": True,
            "stopped_background_watcher_pid": stopped_background_watcher_pid,
            "archived_artifact_count": len(archived_artifacts),
            "canonical_summary_path": detected_summary_path,
            "settle_completed": bool(settle_payload.get("settled", False)),
            "settle_action": settle_action,
            "settled_queue_status": settled_queue_status,
            "throughput_status": _text(service_result.get("status"), detected_summary_payload.get("status")),
            "throughput_error_code": _text(service_result.get("error_code"), detected_summary_payload.get("error_code")),
            "throughput_failed_stage": _text(service_result.get("failed_stage"), detected_summary_payload.get("failed_stage")),
            "next_followup_shard_id": _text(refreshed_lane_summary.get("shard_id")),
            "next_required_step": (
                _text(refreshed_lane_summary.get("next_required_step"))
                or (
                    f"Keep default auto-start frozen after settling {target_id} {selected_shard}; reopen only through the gate4.5 exploratory follow-up lane."
                    if settled_queue_status and "running" not in settled_queue_status
                    else f"Watch {target_id} {selected_shard} through the primary watcher and keep default auto-start frozen until the exploratory follow-up lane is reviewed."
                )
            ),
        },
        "structured": {
            "exploratory_followup_lane_artifact": "runs/wetlab_stk17b_exploratory_followup_lane_current.md",
            "primary_runner_artifact": "runs/wetlab_broad_screen_primary_runner_current.md",
            "canonical_summary_json": detected_summary_path,
            "primary_watch_action_artifact": "runs/wetlab_broad_screen_primary_watch_action_current.md",
        },
        "rows": [
            {
                "target_id": target_id,
                "shard_id": selected_shard,
                "selected_command_kind": selected_kind,
                "compute_pid": _summary(runner_payload).get("compute_pid", 0),
                "heartbeat_pid": _summary(runner_payload).get("heartbeat_pid", 0),
                "stopped_background_watcher_pid": stopped_background_watcher_pid,
                "archived_artifact_count": len(archived_artifacts),
                "canonical_summary_path": detected_summary_path,
                "settle_action": settle_action,
                "settled_queue_status": settled_queue_status,
                "throughput_status": _text(service_result.get("status"), detected_summary_payload.get("status")),
                "throughput_error_code": _text(service_result.get("error_code"), detected_summary_payload.get("error_code")),
                "throughput_failed_stage": _text(service_result.get("failed_stage"), detected_summary_payload.get("failed_stage")),
                "next_followup_shard_id": _text(refreshed_lane_summary.get("shard_id")),
            }
        ],
    }
    write_artifact(DEFAULT_OUT_MD, "STK17B (DRAK2) Exploratory Follow-Up Retry Runner", payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the STK17B exploratory gate4.5 follow-up lane.")
    parser.add_argument("--lane-json", default=DEFAULT_LANE_JSON)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--shard-id", default="")
    parser.add_argument("--command-kind", default="")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--compound-universe-json", default=DEFAULT_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--target-native-csv", default=DEFAULT_TARGET_NATIVE_CSV)
    parser.add_argument("--interval-sec", type=float, default=30.0)
    parser.add_argument("--replace-heartbeat", action="store_true")
    parser.add_argument("--settle-timeout-sec", type=float, default=DEFAULT_SETTLE_TIMEOUT_SEC)
    parser.add_argument("--settle-poll-sec", type=float, default=DEFAULT_SETTLE_POLL_SEC)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(
        lane_json=args.lane_json,
        python_bin=args.python_bin,
        shard_id=args.shard_id,
        command_kind=args.command_kind,
        execution_queue_json=args.execution_queue_json,
        compound_universe_json=args.compound_universe_json,
        portfolio_json=args.portfolio_json,
        target_native_csv=args.target_native_csv,
        interval_sec=args.interval_sec,
        replace_heartbeat=args.replace_heartbeat,
        settle_timeout_sec=args.settle_timeout_sec,
        settle_poll_sec=args.settle_poll_sec,
    )


if __name__ == "__main__":
    main()
