#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "runs" / "wetlab_broad_screen_primary_watch_loop.log"
DEFAULT_PID = ROOT / "runs" / "wetlab_broad_screen_primary_watch_loop.pid"


def _pid_alive(pid: int) -> bool:
    if int(pid) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    stat_path = Path("/proc") / str(pid) / "stat"
    if stat_path.exists():
        try:
            stat_fields = stat_path.read_text(encoding="utf-8").split()
            if len(stat_fields) >= 3 and stat_fields[2] == "Z":
                return False
        except Exception:
            return False
    return True


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


def _recover_stale_pid(pid_file: Path) -> int:
    if not pid_file.exists():
        return 0
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except Exception:
        pid_file.unlink(missing_ok=True)
        return 0
    if _pid_alive(pid):
        return pid
    pid_file.unlink(missing_ok=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch a detached primary broad-screen watch loop.")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--pid-file", default=str(DEFAULT_PID))
    parser.add_argument("--log-file", default=str(DEFAULT_LOG))
    parser.add_argument("--interval-sec", type=float, default=5.0)
    parser.add_argument("--max-consecutive-auto-holds", type=int, default=3)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    pid_file = Path(args.pid_file)
    log_file = Path(args.log_file)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    existing_pid = _recover_stale_pid(pid_file)
    if args.replace:
        _stop_existing(pid_file)
    elif existing_pid:
        print(existing_pid)
        return 0

    log_handle = log_file.open("ab")
    cmd = [
        args.python_bin,
        str(ROOT / "tools" / "run_wetlab_broad_screen_primary_watch.py"),
        "--auto-start-next",
        "--max-consecutive-auto-holds",
        str(args.max_consecutive_auto_holds),
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
