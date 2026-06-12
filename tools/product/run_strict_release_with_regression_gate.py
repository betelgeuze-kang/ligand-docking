#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from types import SimpleNamespace
from typing import Any, Dict, Optional, Sequence

from tools import check_strict_release_regression as regression_gate
from tools import run_openmm_2bead_strict_release as strict_release


def _build_strict_args(args: argparse.Namespace) -> argparse.Namespace:
    parser = strict_release.build_parser()
    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.strict_out_prefix).strip() or f"runs/openmm_2bead_strict_{date_tag}_candidate"

    argv = [
        "--targets",
        str(args.targets),
        "--date-tag",
        date_tag,
        "--profile-json",
        str(args.profile_json),
        "--out-prefix",
        out_prefix,
        "--submission-dir",
        str(args.submission_dir),
        "--gate-speedup-threshold",
        str(float(args.gate_speedup_threshold)),
        "--speed-mode",
        str(args.speed_mode),
        "--speed-mode-replicas",
        str(int(args.speed_mode_replicas)),
        "--speed-profile-max-replicas",
        str(int(args.speed_profile_max_replicas)),
        "--artifact-level",
        str(args.artifact_level),
    ]

    if str(args.external_manifest).strip():
        argv.extend(["--external-manifest", str(args.external_manifest)])
    if bool(args.skip_openmm_generate):
        argv.append("--skip-openmm-generate")
    if bool(args.force_rust):
        argv.append("--force-rust")
    else:
        argv.append("--no-force-rust")
    if bool(args.publish_release):
        argv.append("--publish-release")
    else:
        argv.append("--no-publish-release")
    if str(args.publish_release_tag).strip():
        argv.extend(["--publish-release-tag", str(args.publish_release_tag)])
    if bool(args.prune_runs):
        argv.append("--prune-runs")
    else:
        argv.append("--no-prune-runs")
    if bool(args.archive_intermediate):
        argv.append("--archive-intermediate")
    else:
        argv.append("--no-archive-intermediate")
    if bool(args.strict_fail_fast):
        argv.append("--strict-fail-fast")
    else:
        argv.append("--no-strict-fail-fast")

    return parser.parse_args(argv)


def _build_regression_args(
    args: argparse.Namespace,
    candidate_summary_json: str,
    candidate_accuracy_csv: str,
) -> argparse.Namespace:
    return SimpleNamespace(
        baseline_summary_json=str(args.baseline_summary_json),
        candidate_summary_json=str(candidate_summary_json),
        baseline_accuracy_csv=str(args.baseline_accuracy_csv),
        candidate_accuracy_csv=str(candidate_accuracy_csv),
        min_speedup_ratio=float(args.min_speedup_ratio),
        max_avg_e2e_rmse_increase=float(args.max_avg_e2e_rmse_increase),
        max_avg_e2e_rel_rmse_increase=float(args.max_avg_e2e_rel_rmse_increase),
        max_avg_neighbor_jaccard_drop=float(args.max_avg_neighbor_jaccard_drop),
        max_avg_rmsd_aligned_increase=float(args.max_avg_rmsd_aligned_increase),
        max_avg_rmsd_vs_native_aligned_increase=float(args.max_avg_rmsd_vs_native_aligned_increase),
        require_candidate_pass=bool(args.require_candidate_pass),
        out_json=str(args.regression_out_json),
        out_csv=str(args.regression_out_csv),
    )


def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    candidate_summary_json = str(args.candidate_summary_json).strip()
    candidate_accuracy_csv = str(args.candidate_accuracy_csv).strip()
    strict_payload: Dict[str, Any] = {}

    if bool(args.skip_strict_run):
        if not candidate_summary_json:
            raise ValueError("--candidate-summary-json is required when --skip-strict-run is set")
    else:
        strict_args = _build_strict_args(args)
        strict_payload = strict_release.run_release(strict_args)
        candidate_summary_json = str(strict_payload.get("artifacts", {}).get("summary_json", "")).strip()
        candidate_accuracy_csv = str(strict_payload.get("artifacts", {}).get("accuracy_external_csv", "")).strip()
        if not candidate_summary_json:
            raise RuntimeError("strict release did not produce artifacts.summary_json")

    reg_args = _build_regression_args(
        args=args,
        candidate_summary_json=candidate_summary_json,
        candidate_accuracy_csv=candidate_accuracy_csv,
    )
    regression_payload = regression_gate.run_check(reg_args)

    result = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "pass": bool(regression_payload.get("summary", {}).get("pass", False)),
            "strict_run_executed": bool(not args.skip_strict_run),
            "candidate_summary_json": candidate_summary_json,
            "candidate_accuracy_csv": (
                candidate_accuracy_csv
                or regression_payload.get("inputs", {}).get("candidate_accuracy_csv", "")
            ),
        },
        "strict_payload_summary": strict_payload.get("summary", {}),
        "regression_summary": regression_payload.get("summary", {}),
        "regression_failures": regression_payload.get("failures", []),
        "files": {
            "regression_json": str(args.regression_out_json),
            "regression_csv": str(args.regression_out_csv),
        },
    }
    os.makedirs(os.path.dirname(str(args.out_json)) or ".", exist_ok=True)
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return result


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Run strict OpenMM 2-bead release and immediately enforce regression gate "
            "(speed/accuracy) against a baseline summary."
        )
    )
    p.add_argument("--baseline-summary-json", type=str, required=True)
    p.add_argument("--baseline-accuracy-csv", type=str, default="")
    p.add_argument("--candidate-summary-json", type=str, default="")
    p.add_argument("--candidate-accuracy-csv", type=str, default="")
    p.add_argument("--skip-strict-run", action=argparse.BooleanOptionalAction, default=False)

    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--targets", type=str, default="noncyclic")
    p.add_argument("--profile-json", type=str, default="config/long_stability_target_tuned_all10_2026-02-17_v2.json")
    p.add_argument("--external-manifest", type=str, default="")
    p.add_argument("--skip-openmm-generate", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--strict-out-prefix", type=str, default="")
    p.add_argument("--submission-dir", type=str, default="runs/external_eval_submission")
    p.add_argument("--gate-speedup-threshold", type=float, default=12.0)
    p.add_argument(
        "--speed-mode",
        type=str,
        default="max",
        choices=["balanced", "fast", "ultra", "turbo", "extreme", "warp", "titan", "max"],
    )
    p.add_argument("--speed-mode-replicas", type=int, default=128)
    p.add_argument("--speed-profile-max-replicas", type=int, default=128)
    p.add_argument("--artifact-level", type=str, default="minimal", choices=["minimal", "full"])
    p.add_argument("--publish-release", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--publish-release-tag", type=str, default="")
    p.add_argument("--prune-runs", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--archive-intermediate", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--strict-fail-fast", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--force-rust", action=argparse.BooleanOptionalAction, default=True)

    p.add_argument("--min-speedup-ratio", type=float, default=0.95)
    p.add_argument("--max-avg-e2e-rmse-increase", type=float, default=0.005)
    p.add_argument("--max-avg-e2e-rel-rmse-increase", type=float, default=1e-6)
    p.add_argument("--max-avg-neighbor-jaccard-drop", type=float, default=0.0)
    p.add_argument("--max-avg-rmsd-aligned-increase", type=float, default=0.02)
    p.add_argument("--max-avg-rmsd-vs-native-aligned-increase", type=float, default=0.01)
    p.add_argument("--require-candidate-pass", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--regression-out-json", type=str, default=f"runs/strict_release_regression_{stamp}.json")
    p.add_argument("--regression-out-csv", type=str, default=f"runs/strict_release_regression_{stamp}.csv")

    p.add_argument("--out-json", type=str, default=f"runs/strict_release_e2e_gate_{stamp}.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        payload = run_pipeline(args)
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(2)

    print(json.dumps(payload.get("summary", {}), indent=2, ensure_ascii=False))
    print(f"Wrote: {args.out_json}")
    if not bool(payload.get("summary", {}).get("pass", False)):
        sys.exit(2)


if __name__ == "__main__":
    main()

