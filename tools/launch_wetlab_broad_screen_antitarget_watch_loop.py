#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "runs" / "wetlab_broad_screen_antitarget_watcher_loop.log"
DEFAULT_PID = ROOT / "runs" / "wetlab_broad_screen_antitarget_watcher_loop.pid"


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
    parser = argparse.ArgumentParser(description="Launch a detached anti-target watcher loop.")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--pid-file", default=str(DEFAULT_PID))
    parser.add_argument("--log-file", default=str(DEFAULT_LOG))
    parser.add_argument("--interval-sec", type=float, default=5.0)
    parser.add_argument("--supervision-max-heartbeats", type=int, default=4)
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
        args.python_bin,
        str(ROOT / "tools" / "run_wetlab_broad_screen_antitarget_watcher.py"),
        "--auto-start-next",
        "--supervision-max-heartbeats",
        str(args.supervision_max_heartbeats),
        "--loop",
        "--interval-sec",
        str(args.interval_sec),
    ]

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
