#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from tools import run_wetlab_broad_screen_antitarget_runner as runner_mod
from tools import run_wetlab_broad_screen_antitarget_runtime_event as runtime_event
from tools import wetlab_broad_screen_antitarget_watcher_state as state_mod
from tools.wetlab_broad_screen_watch_utils import antitarget_active_row, first_ready_row, stop_pid_file
from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_execution_queue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_antitarget_watcher_current.md"
DEFAULT_HEARTBEAT_PID = ROOT / "runs" / "wetlab_broad_screen_antitarget_heartbeat_loop.pid"
DEFAULT_HEARTBEAT_LOG = ROOT / "runs" / "wetlab_broad_screen_antitarget_heartbeat_loop.log"
DEFAULT_STALE_MINUTES = 20.0
DEFAULT_SUPERVISION_MAX_HEARTBEATS = 4
POST_ACTION_SCRIPTS = [
    "tools/build_wetlab_broad_screen_antitarget_execution_queue.py",
    "tools/build_wetlab_broad_screen_antitarget_runtime_runbook.py",
    "tools/build_wetlab_broad_screen_antitarget_throughput_bridge.py",
    "tools/build_wetlab_broad_screen_precision_monitor.py",
    "tools/build_wetlab_final_campaign_summary.py",
    "tools/build_wetlab_master_handoff_dashboard.py",
    "tools/build_wetlab_partnering_stack.py",
]


def _refresh_support(*, python_bin: str) -> None:
    for script in POST_ACTION_SCRIPTS:
        subprocess.run([python_bin, str(ROOT / script)], cwd=ROOT, check=True)


def _launch_heartbeat_loop(
    *,
    python_bin: str,
    primary_target_id: str,
    anti_target_id: str,
    shard_id: str,
    max_heartbeats: int,
) -> None:
    subprocess.run(
        [
            python_bin,
            str(ROOT / "tools/launch_wetlab_broad_screen_antitarget_heartbeat_loop.py"),
            "--primary-target-id",
            primary_target_id,
            "--anti-target-id",
            anti_target_id,
            "--shard-id",
            shard_id,
            "--interval-sec",
            "30",
            "--max-heartbeats",
            str(max_heartbeats),
            "--replace",
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )


def run_once(
    *,
    python_bin: str,
    execution_queue_json: str,
    out_md: str,
    pid_file: Path,
    log_file: Path,
    stale_minutes: float,
    auto_start_next: bool,
    supervision_max_heartbeats: int,
) -> dict[str, Any]:
    execution_queue = load_json(execution_queue_json)
    inspection = state_mod.inspect_state(
        execution_queue,
        pid_file=pid_file,
        stale_minutes=stale_minutes,
        supervision_max_heartbeats=supervision_max_heartbeats,
    )
    decision = str(inspection.get("decision", "")).strip()
    recommended_event = str(inspection.get("recommended_event", "")).strip()
    active = dict(inspection.get("active_row", {}) or {})
    action_parts: list[str] = []

    if active and recommended_event in {"complete", "hold"}:
        compute_pid_path = str(active.get("compute_pid_path", "")).strip()
        if compute_pid_path:
            stop_pid_file(compute_pid_path)
        stop_pid_file(pid_file)
        runtime_event.run_event(
            primary_target_id=str(active.get("primary_target_id", "")).strip(),
            anti_target_id=str(active.get("anti_target_id", "")).strip(),
            shard_id=str(active.get("primary_shard_id", "")).strip(),
            event=recommended_event,
            python_bin=python_bin,
            active_stage_label=str(active.get("active_stage_label", "")).strip() or "antitarget_counterscreen_primary_shard",
            notes=f"auto_{recommended_event}_from_antitarget_watcher_runtime_validation_only",
        )
        action_parts.append(f"auto_{recommended_event}")
        _refresh_support(python_bin=python_bin)
        execution_queue = load_json(execution_queue_json)
        inspection = state_mod.inspect_state(
            execution_queue,
            pid_file=pid_file,
            stale_minutes=stale_minutes,
            supervision_max_heartbeats=supervision_max_heartbeats,
        )

    autostart_primary = ""
    autostart_anti = ""
    autostart_shard = ""
    if auto_start_next and not antitarget_active_row(execution_queue):
        ready = first_ready_row(execution_queue, target_key="primary_target_id", shard_key="primary_shard_id")
        autostart_primary = str(ready.get("primary_target_id", "")).strip()
        autostart_anti = str(ready.get("anti_target_id", "")).strip()
        autostart_shard = str(ready.get("primary_shard_id", "")).strip()
        if autostart_primary and autostart_anti and autostart_shard:
            runner_mod.run(
                python_bin=python_bin,
                primary_target_id=autostart_primary,
                anti_target_id=autostart_anti,
                shard_id=autostart_shard,
                command_kind="auto",
                antitarget_execution_queue_json=execution_queue_json,
                primary_queue_json="runs/wetlab_broad_screen_queue_current.json",
                compound_universe_json="runs/wetlab_broad_screen_compound_universe_current.json",
                portfolio_json="runs/wetlab_partner_target_portfolio_current.json",
                target_native_csv="config/real_drug_targets_native_v1.csv",
                interval_sec=30.0,
                replace_heartbeat=True,
            )
            action_parts.append("auto_start_next")
            _refresh_support(python_bin=python_bin)
            execution_queue = load_json(execution_queue_json)
            inspection = state_mod.inspect_state(
                execution_queue,
                pid_file=pid_file,
                stale_minutes=stale_minutes,
                supervision_max_heartbeats=supervision_max_heartbeats,
            )

    last_action = "+".join(action_parts) if action_parts else "noop"
    payload = state_mod.build_payload(
        execution_queue,
        inspection,
        log_file=log_file,
        last_action=last_action,
        auto_start_next=auto_start_next,
    )
    payload["summary"]["status"] = "wetlab_broad_screen_antitarget_watcher_ready"
    payload["summary"]["action_taken"] = last_action
    payload["summary"]["autostart_primary_target_id"] = autostart_primary
    payload["summary"]["autostart_anti_target_id"] = autostart_anti
    payload["summary"]["autostart_shard_id"] = autostart_shard
    payload["structured"]["watcher_state_artifact"] = "runs/wetlab_broad_screen_antitarget_watcher_state_current.md"
    write_artifact(out_md, "Wet-Lab Broad Screen Anti-Target Watcher", payload)
    state_payload = state_mod.build_payload(
        execution_queue,
        inspection,
        log_file=log_file,
        last_action=last_action,
        auto_start_next=auto_start_next,
    )
    write_artifact(
        str(ROOT / "runs/wetlab_broad_screen_antitarget_watcher_state_current.md"),
        "Wet-Lab Broad Screen Anti-Target Watcher State",
        state_payload,
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch the active anti-target counterscreen row and auto-advance it on stale/pid exit conditions.")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--pid-file", default=str(DEFAULT_HEARTBEAT_PID))
    parser.add_argument("--log-file", default=str(DEFAULT_HEARTBEAT_LOG))
    parser.add_argument("--stale-minutes", type=float, default=DEFAULT_STALE_MINUTES)
    parser.add_argument("--supervision-max-heartbeats", type=int, default=DEFAULT_SUPERVISION_MAX_HEARTBEATS)
    parser.add_argument("--auto-start-next", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=5.0)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not args.loop:
        run_once(
            python_bin=args.python_bin,
            execution_queue_json=args.execution_queue_json,
            out_md=args.out_md,
            pid_file=Path(args.pid_file),
            log_file=Path(args.log_file),
            stale_minutes=args.stale_minutes,
            auto_start_next=args.auto_start_next,
            supervision_max_heartbeats=args.supervision_max_heartbeats,
        )
    else:
        while True:
            payload = run_once(
                python_bin=args.python_bin,
                execution_queue_json=args.execution_queue_json,
                out_md=args.out_md,
                pid_file=Path(args.pid_file),
                log_file=Path(args.log_file),
                stale_minutes=args.stale_minutes,
                auto_start_next=args.auto_start_next,
                supervision_max_heartbeats=args.supervision_max_heartbeats,
            )
            action_taken = str(payload.get("summary", {}).get("action_taken", "")).strip()
            if action_taken and action_taken != "noop":
                time.sleep(0.5)
            else:
                time.sleep(max(args.interval_sec, 1.0))
