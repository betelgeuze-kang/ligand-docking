#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools import build_wetlab_broad_screen_antitarget_throughput_bridge as bridge_mod
from tools import run_wetlab_broad_screen_antitarget_runtime_event as runtime_mod
from tools.wetlab_broad_screen_watch_utils import primary_bridge_paths
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANTITARGET_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_execution_queue_current.json"
DEFAULT_PRIMARY_QUEUE_JSON = "runs/wetlab_broad_screen_queue_current.json"
DEFAULT_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_TARGET_NATIVE_CSV = "config/real_drug_targets_native_v1.csv"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_antitarget_runner_current.md"
DEFAULT_WATCH_LAUNCHER = "tools/launch_wetlab_broad_screen_antitarget_watch_loop.py"
COMMAND_PREFERENCE = [
    "throughput_preflight_tuned_gate55",
    "throughput_preflight_tuned",
    "throughput_preflight",
]


def _select_command(bridge_payload: dict[str, Any], requested_kind: str) -> tuple[str, str]:
    rows = [dict(row) for row in (bridge_payload.get("rows", []) or [])]
    if requested_kind != "auto":
        for row in rows:
            if str(row.get("command_kind", "")).strip() == requested_kind:
                return requested_kind, str(row.get("command", "")).strip()
        return requested_kind, ""
    for kind in COMMAND_PREFERENCE:
        for row in rows:
            if str(row.get("command_kind", "")).strip() == kind and bool(row.get("enabled", False)):
                return kind, str(row.get("command", "")).strip()
    return "", ""


def run(
    *,
    primary_target_id: str,
    anti_target_id: str,
    shard_id: str,
    python_bin: str,
    command_kind: str,
    antitarget_execution_queue_json: str,
    primary_queue_json: str,
    compound_universe_json: str,
    portfolio_json: str,
    target_native_csv: str,
    interval_sec: float,
    replace_heartbeat: bool,
) -> dict[str, Any]:
    antitarget_execution_queue = load_json(antitarget_execution_queue_json)
    primary_queue = load_json(primary_queue_json)
    compound_universe = load_json(compound_universe_json)
    portfolio = maybe_load_json(portfolio_json) or load_json(portfolio_json)
    bridge_payload = bridge_mod.build_payload(
        antitarget_execution_queue=antitarget_execution_queue,
        primary_queue=primary_queue,
        compound_universe=compound_universe,
        portfolio=portfolio,
        target_native_csv=target_native_csv,
        primary_target_id=primary_target_id,
        anti_target_id=anti_target_id,
        shard_id=shard_id,
    )
    bridge_paths = primary_bridge_paths(bridge_payload)
    selected_kind, command = _select_command(bridge_payload, command_kind)
    if not command:
        raise SystemExit(
            f"no counterscreen throughput command available for {primary_target_id} -> {anti_target_id} {shard_id} using kind={command_kind}"
        )

    stage_label = "antitarget_counterscreen_primary_shard_tuned_gate55" if selected_kind.endswith("gate55") else "antitarget_counterscreen_primary_shard_compute"
    log_path = Path(bridge_paths["preferred_log_path"])
    pid_path = Path(bridge_paths["preferred_pid_path"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        ["bash", "-lc", command],
        cwd=ROOT,
        stdout=log_path.open("ab"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    pid_path.write_text(str(proc.pid), encoding="utf-8")

    runtime_mod.run_event(
        primary_target_id=primary_target_id,
        anti_target_id=anti_target_id,
        shard_id=shard_id,
        event="start",
        python_bin=python_bin,
        active_stage_label=stage_label,
        notes=f"launched_by_antitarget_runner_{selected_kind}_runtime_validation_only",
        runner_kind=runtime_mod.RUNNER_KIND_COMPUTE_ATTACHED,
        compute_pid=proc.pid,
        compute_pid_path=str(pid_path),
        compute_log_path=str(log_path),
        compute_summary_json=str(Path(bridge_paths["preferred_summary_json"])),
        compute_summary_md=str(Path(bridge_paths["preferred_summary_md"])),
    )

    summary_json = str(Path(bridge_paths["preferred_summary_json"]))
    summary_md = str(Path(bridge_paths["preferred_summary_md"]))
    launcher_cmd = [
        python_bin,
        str(ROOT / "tools" / "launch_wetlab_broad_screen_antitarget_heartbeat_loop.py"),
        "--primary-target-id",
        primary_target_id,
        "--anti-target-id",
        anti_target_id,
        "--shard-id",
        shard_id,
        "--active-stage-label",
        stage_label,
        "--interval-sec",
        str(interval_sec),
        "--notes",
        "compute_attached_antitarget_heartbeat_runtime_validation_only",
        "--runner-kind",
        runtime_mod.RUNNER_KIND_COMPUTE_ATTACHED,
        "--compute-pid",
        str(proc.pid),
        "--compute-pid-path",
        str(pid_path),
        "--compute-log-path",
        str(log_path),
        "--compute-summary-json",
        summary_json,
        "--compute-summary-md",
        summary_md,
    ]
    if replace_heartbeat:
        launcher_cmd.append("--replace")
    launcher = subprocess.run(launcher_cmd, cwd=ROOT, check=True, text=True, capture_output=True)
    heartbeat_pid = int((launcher.stdout or "0").strip() or 0)

    watch_launcher_cmd = [
        python_bin,
        str(ROOT / DEFAULT_WATCH_LAUNCHER),
        "--replace",
    ]
    watch_launcher = subprocess.run(
        watch_launcher_cmd,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    watcher_pid = int((watch_launcher.stdout or "0").strip() or 0)

    payload = {
        "summary": {
            "status": "wetlab_broad_screen_antitarget_runner_ready",
            "primary_target_id": primary_target_id,
            "anti_target_id": anti_target_id,
            "shard_id": shard_id,
            "selected_command_kind": selected_kind,
            "compute_pid": proc.pid,
            "compute_pid_path": str(pid_path),
            "compute_log_path": str(log_path),
            "compute_summary_json": str(Path(bridge_paths["preferred_summary_json"])),
            "compute_summary_md": str(Path(bridge_paths["preferred_summary_md"])),
            "heartbeat_pid": heartbeat_pid,
            "heartbeat_pid_path": str(ROOT / "runs" / "wetlab_broad_screen_antitarget_heartbeat_loop.pid"),
            "watcher_pid": watcher_pid,
            "watcher_pid_path": str(ROOT / "runs" / "wetlab_broad_screen_antitarget_watcher_loop.pid"),
            "next_required_step": f"Let the counterscreen watcher observe {primary_target_id} -> {anti_target_id} {shard_id} and auto-complete it when the summary lands.",
        },
        "structured": {
            "throughput_bridge_artifact": "runs/wetlab_broad_screen_antitarget_throughput_bridge_current.md",
            "watcher_state_artifact": "runs/wetlab_broad_screen_antitarget_watcher_state_current.md",
        },
        "rows": [
            {
                "primary_target_id": primary_target_id,
                "anti_target_id": anti_target_id,
                "shard_id": shard_id,
                "selected_command_kind": selected_kind,
                "command": command,
                "compute_pid": proc.pid,
                "compute_pid_path": str(pid_path),
                "compute_log_path": str(log_path),
                "compute_summary_json": str(Path(bridge_paths["preferred_summary_json"])),
                "compute_summary_md": str(Path(bridge_paths["preferred_summary_md"])),
                "heartbeat_pid": heartbeat_pid,
                "heartbeat_pid_path": str(ROOT / "runs" / "wetlab_broad_screen_antitarget_heartbeat_loop.pid"),
                "watcher_pid": watcher_pid,
                "watcher_pid_path": str(ROOT / "runs" / "wetlab_broad_screen_antitarget_watcher_loop.pid"),
            }
        ],
    }
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Broad Screen Anti-Target Runner", payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the active or requested anti-target counterscreen shard with watcher-friendly pid/log paths.")
    parser.add_argument("--primary-target-id", required=True)
    parser.add_argument("--anti-target-id", required=True)
    parser.add_argument("--shard-id", required=True)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--command-kind", default="auto")
    parser.add_argument("--antitarget-execution-queue-json", default=DEFAULT_ANTITARGET_EXECUTION_QUEUE_JSON)
    parser.add_argument("--primary-queue-json", default=DEFAULT_PRIMARY_QUEUE_JSON)
    parser.add_argument("--compound-universe-json", default=DEFAULT_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--target-native-csv", default=DEFAULT_TARGET_NATIVE_CSV)
    parser.add_argument("--interval-sec", type=float, default=30.0)
    parser.add_argument("--replace-heartbeat", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        primary_target_id=args.primary_target_id,
        anti_target_id=args.anti_target_id,
        shard_id=args.shard_id,
        python_bin=args.python_bin,
        command_kind=args.command_kind,
        antitarget_execution_queue_json=args.antitarget_execution_queue_json,
        primary_queue_json=args.primary_queue_json,
        compound_universe_json=args.compound_universe_json,
        portfolio_json=args.portfolio_json,
        target_native_csv=args.target_native_csv,
        interval_sec=args.interval_sec,
        replace_heartbeat=args.replace_heartbeat,
    )
