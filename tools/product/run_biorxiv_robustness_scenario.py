#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_baseline_run_root(explicit: str, package_meta_json: str) -> str:
    if str(explicit).strip():
        return str((ROOT / explicit).resolve()) if not Path(explicit).is_absolute() else str(Path(explicit).resolve())
    meta_path = (ROOT / package_meta_json).resolve() if not Path(package_meta_json).is_absolute() else Path(package_meta_json).resolve()
    if not meta_path.exists():
        return ""
    meta = _read_json(meta_path)
    run_root = str(meta.get("run_root") or "").strip()
    if not run_root:
        return ""
    return str(Path(run_root).resolve())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run a named robustness scenario against the promoted current bioRxiv validation baseline.")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--tag", default="")
    ap.add_argument("--sets", default="set3_operational_smoke,set1_core_blind,set2_expanded_ood")
    ap.add_argument("--set-spec-json", required=True)
    ap.add_argument("--baseline-run-root", default="")
    ap.add_argument("--current-package-meta-json", default="runs/biorxiv_external_validation_package_current.json")
    ap.add_argument("--out-root", default="runs/external_validation_blind_runs")
    ap.add_argument("--package-out-root", default="runs")
    ap.add_argument("--comparison-out-root", default="runs")
    ap.add_argument("--heartbeat-interval-sec", type=float, default=5.0)
    args = ap.parse_args(argv)

    tag = str(args.tag).strip() or f"{dt.date.today().isoformat()}_{args.scenario}"
    run_cmd = [
        sys.executable,
        str(ROOT / "tools/run_biorxiv_external_validation_current.py"),
        "--tag",
        tag,
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
    run_rc = subprocess.run(run_cmd, cwd=str(ROOT)).returncode
    if run_rc != 0:
        return int(run_rc)

    candidate_run_root = ROOT / args.out_root / f"external_validation_blind_runs_{tag}"
    baseline_run_root = _resolve_baseline_run_root(args.baseline_run_root, args.current_package_meta_json)
    if not baseline_run_root:
        print(
            json.dumps(
                {
                    "ok": True,
                    "scenario": args.scenario,
                    "tag": tag,
                    "candidate_run_root": str(candidate_run_root.resolve()),
                    "comparison_skipped": True,
                    "reason": "baseline run root not found",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    compare_label = f"{tag}_vs_current"
    compare_cmd = [
        sys.executable,
        str(ROOT / "tools/compare_biorxiv_external_validation_runs.py"),
        "--baseline-run-root",
        str(baseline_run_root),
        "--candidate-run-root",
        str(candidate_run_root.resolve()),
        "--out-root",
        str(args.comparison_out_root),
        "--label",
        compare_label,
    ]
    compare_rc = subprocess.run(compare_cmd, cwd=str(ROOT)).returncode
    if compare_rc != 0:
        return int(compare_rc)

    print(
        json.dumps(
            {
                "ok": True,
                "scenario": args.scenario,
                "tag": tag,
                "baseline_run_root": str(baseline_run_root),
                "candidate_run_root": str(candidate_run_root.resolve()),
                "comparison_root": str((ROOT / args.comparison_out_root / f"biorxiv_run_comparison_{compare_label}").resolve()),
                "set_spec_json": str((ROOT / args.set_spec_json).resolve()),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
