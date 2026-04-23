#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "runs" / "wetlab_broad_screen_antitarget_heartbeat_loop.log"
DEFAULT_PID = ROOT / "runs" / "wetlab_broad_screen_antitarget_heartbeat_loop.pid"


def _stop_existing(pid_file: Path) -> None:
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except Exception:
        pid_file.unlink(missing_ok=True)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    pid_file.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch a detached anti-target heartbeat loop.")
    parser.add_argument("--primary-target-id", required=True)
    parser.add_argument("--anti-target-id", required=True)
    parser.add_argument("--shard-id", required=True)
    parser.add_argument("--active-stage-label", default="antitarget_counterscreen_primary_shard")
    parser.add_argument("--interval-sec", type=float, default=30.0)
    parser.add_argument("--max-heartbeats", type=int, default=0)
    parser.add_argument("--pid-file", default=str(DEFAULT_PID))
    parser.add_argument("--log-file", default=str(DEFAULT_LOG))
    parser.add_argument("--notes", default="")
    parser.add_argument("--runner-kind", default="")
    parser.add_argument("--compute-pid", type=int, default=0)
    parser.add_argument("--compute-pid-path", default="")
    parser.add_argument("--compute-log-path", default="")
    parser.add_argument("--compute-summary-json", default="")
    parser.add_argument("--compute-summary-md", default="")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    pid_file = Path(args.pid_file)
    log_file = Path(args.log_file)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    if args.replace:
        _stop_existing(pid_file)

    log_handle = log_file.open("ab")
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "run_wetlab_broad_screen_antitarget_runtime_event.py"),
        "--primary-target-id",
        args.primary_target_id,
        "--anti-target-id",
        args.anti_target_id,
        "--shard-id",
        args.shard_id,
        "--event",
        "heartbeat",
        "--loop",
        "--interval-sec",
        str(args.interval_sec),
        "--max-heartbeats",
        str(args.max_heartbeats),
        "--active-stage-label",
        args.active_stage_label,
    ]
    if args.notes:
        cmd.extend(["--notes", args.notes])
    if args.runner_kind:
        cmd.extend(["--runner-kind", args.runner_kind])
    if args.compute_pid:
        cmd.extend(["--compute-pid", str(args.compute_pid)])
    if args.compute_pid_path:
        cmd.extend(["--compute-pid-path", args.compute_pid_path])
    if args.compute_log_path:
        cmd.extend(["--compute-log-path", args.compute_log_path])
    if args.compute_summary_json:
        cmd.extend(["--compute-summary-json", args.compute_summary_json])
    if args.compute_summary_md:
        cmd.extend(["--compute-summary-md", args.compute_summary_md])

    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    pid_file.write_text(str(proc.pid), encoding="utf-8")
    print(proc.pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
