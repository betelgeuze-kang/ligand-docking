#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Launch the winner-informed post-gauntlet external-validation candidate run.")
    ap.add_argument("--tag", default=f"{dt.date.today().isoformat()}_biorxiv_v7_bestofgauntlet1")
    ap.add_argument("--sets", default="set3_operational_smoke,set1_core_blind,set2_expanded_ood")
    ap.add_argument("--set-spec-json", default="config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json")
    ap.add_argument("--out-root", default="runs/external_validation_blind_runs")
    ap.add_argument("--package-out-root", default="runs")
    ap.add_argument("--heartbeat-interval-sec", type=float, default=5.0)
    args = ap.parse_args(argv)

    cmd = [
        sys.executable,
        str(ROOT / "tools/run_biorxiv_external_validation_current.py"),
        "--tag", str(args.tag),
        "--sets", str(args.sets),
        "--set-spec-json", str(args.set_spec_json),
        "--out-root", str(args.out_root),
        "--package-out-root", str(args.package_out_root),
        "--heartbeat-interval-sec", str(args.heartbeat_interval_sec),
    ]
    return subprocess.run(cmd, cwd=str(ROOT)).returncode


if __name__ == "__main__":
    raise SystemExit(main())
