#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the provisional bioRxiv temporal validation scaffold using the current dataset-level freeze spec.")
    ap.add_argument("--tag", default=f"{dt.date.today().isoformat()}_biorxiv_temporal_v1")
    ap.add_argument("--sets", default="set_temporal_core_blind,set_temporal_expanded_ood")
    ap.add_argument(
        "--set-spec-json",
        default="config/external_validation_biorxiv_temporal_sets_v1_provisional.json",
    )
    ap.add_argument("--out-root", default="runs/external_validation_blind_runs")
    ap.add_argument("--package-out-root", default="runs")
    ap.add_argument("--heartbeat-interval-sec", type=float, default=5.0)
    args = ap.parse_args()

    cmd = [
        sys.executable,
        str(ROOT / "tools/run_biorxiv_external_validation_current.py"),
        "--tag",
        str(args.tag),
        "--sets",
        str(args.sets),
        "--set-spec-json",
        str(args.set_spec_json),
        "--out-root",
        str(args.out_root),
        "--package-out-root",
        str(args.package_out_root),
        "--heartbeat-interval-sec",
        str(args.heartbeat_interval_sec),
    ]
    return subprocess.run(cmd, cwd=str(ROOT)).returncode


if __name__ == "__main__":
    raise SystemExit(main())

