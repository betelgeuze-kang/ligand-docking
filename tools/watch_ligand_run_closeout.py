#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Sequence


def _read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _run(cmd: list[str], log_path: str) -> int:
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n$ {' '.join(cmd)}\n")
        f.flush()
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, text=True)
    return int(proc.returncode)


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = argparse.ArgumentParser(description="Watch a ligand run summary and emit closeout/post-report artifacts.")
    p.add_argument("--summary-json", type=str, required=True)
    p.add_argument("--prefix", type=str, required=True)
    p.add_argument("--sizes", type=str, default="10000")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--wait-sec", type=float, default=20.0)
    p.add_argument("--timeout-sec", type=float, default=0.0)
    p.add_argument("--log-path", type=str, default="")
    args = p.parse_args(argv)

    summary_json = str(args.summary_json)
    prefix = str(args.prefix)
    log_path = str(args.log_path).strip() or f"{prefix}_closeout_watch.log"
    started = time.time()
    while True:
        if os.path.exists(summary_json):
            break
        if float(args.timeout_sec) > 0.0 and (time.time() - started) >= float(args.timeout_sec):
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("timeout waiting for summary\n")
            sys.exit(2)
        time.sleep(float(max(args.wait_sec, 2.0)))

    _run(
        [
            "python3",
            "tools/update_closeout_latest.py",
            "--summary-json",
            summary_json,
            "--out-dir",
            "runs",
            "--prefix",
            "CLOSEOUT",
        ],
        log_path,
    )
    _run(
        [
            "python3",
            "tools/build_ligand_stress_post_report.py",
            "--prefix",
            prefix,
            "--sizes",
            str(args.sizes),
            "--repeats",
            str(int(args.repeats)),
            "--out-runs-csv",
            f"{prefix}_post_runs.csv",
            "--out-size-csv",
            f"{prefix}_post_sizes.csv",
            "--out-json",
            f"{prefix}_post_summary.json",
            "--out-md",
            f"{prefix}_post_summary.md",
        ],
        log_path,
    )
    _run(
        [
            "python3",
            "tools/summarize_ligand_gate_failure.py",
            "--summary-json",
            summary_json,
            "--out-json",
            f"{prefix}_failure_summary.json",
            "--out-md",
            f"{prefix}_failure_summary.md",
        ],
        log_path,
    )


if __name__ == "__main__":
    main()
