#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Sequence

import pandas as pd

from core.definitions import ResearchConstants


def _run_cmd(cmd: List[str], dry_run: bool = False) -> None:
    print("[RUN]", " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def _read_manifest_targets(path: str) -> List[str]:
    df = pd.read_csv(path)
    if "target" not in df.columns:
        raise ValueError(f"Manifest missing required column 'target': {path}")
    targets = [str(x).strip() for x in df["target"].tolist() if str(x).strip()]
    if len(targets) == 0:
        raise ValueError(f"Manifest has no valid targets: {path}")
    return targets


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _validate_baseline_target_set(manifest_targets: List[str]) -> None:
    expected = {_normalize_target_key(x) for x in ResearchConstants.CHALLENGES.keys()}
    got = {_normalize_target_key(x) for x in manifest_targets}
    if expected != got:
        missing = sorted(expected - got)
        extra = sorted(got - expected)
        raise ValueError(
            "strict baseline target set mismatch: "
            f"missing={missing}, extra={extra}, expected_n={len(expected)}, got_n={len(got)}"
        )


def _extract_worst_targets(report_csv: str, top_k: int) -> List[str]:
    df = pd.read_csv(report_csv)
    if "target" not in df.columns or "avg_rmsd" not in df.columns:
        raise ValueError(f"Report missing required columns target/avg_rmsd: {report_csv}")
    sub = df[["target", "avg_rmsd"]].copy()
    sub["avg_rmsd"] = pd.to_numeric(sub["avg_rmsd"], errors="coerce")
    sub = sub.dropna(subset=["avg_rmsd"])
    sub = sub.sort_values("avg_rmsd", ascending=False)
    return [str(x).strip() for x in sub["target"].head(max(int(top_k), 1)).tolist() if str(x).strip()]


def _copy_with_stamp(src: str, dst_dir: str, stem: str, stamp: str, suffix: str) -> str:
    src_path = Path(src)
    if not src_path.exists():
        raise FileNotFoundError(f"source file not found: {src}")
    dst_path = Path(dst_dir) / f"{stem}_{stamp}{suffix}"
    shutil.copy2(src_path, dst_path)
    return str(dst_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="One-command refresh for external evaluation submission artifacts."
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="runs/external_ref_manifest_all_native_proxy.csv",
        help="External reference manifest CSV for benchmark/accuracy_bench.py",
    )
    parser.add_argument("--external-steps", type=int, default=60)
    parser.add_argument("--external-runs", type=int, default=3)
    parser.add_argument("--focus-steps", type=int, default=300)
    parser.add_argument("--focus-runs", type=int, default=5)
    parser.add_argument("--focus-top-k", type=int, default=3)
    parser.add_argument("--packet-version", type=str, choices=["v1", "v2", "v3"], default="v2")
    parser.add_argument("--pdb-glob", type=str, default="data/native/*.pdb")
    parser.add_argument(
        "--quality-manifest-csv",
        type=str,
        default=None,
        help="If set, run structure quality curation from manifest path/target/source_kind columns.",
    )
    parser.add_argument("--submission-dir", type=str, default="runs/external_eval_submission")
    parser.add_argument("--status-json", type=str, default="runs/baseline_mode_status.json")
    parser.add_argument("--build-md-only-manifest", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--md-only-manifest", type=str, default="runs/external_ref_manifest_md_only.csv")
    parser.add_argument(
        "--md-only-summary-json",
        type=str,
        default="runs/external_ref_manifest_md_only_summary.json",
    )
    parser.add_argument("--md-engine-regex", type=str, default=r"(openmm|amber|gromacs)")
    parser.add_argument("--require-existing-md-paths", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--strict-md-only-target-count", type=int, default=None)
    parser.add_argument("--validate-md-references", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--md-reference-validation-json", type=str, default="runs/md_reference_validation.json")
    parser.add_argument("--md-reference-validation-csv", type=str, default="runs/md_reference_validation.csv")
    parser.add_argument("--strict-md-reference-validation", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--update-md-gap-report", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--md-gap-json", type=str, default=None)
    parser.add_argument("--expected-target-count", type=int, default=len(ResearchConstants.CHALLENGES))
    parser.add_argument("--strict-baseline", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--full-param-optimization",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="If enabled, records planned transition out of baseline-only mode.",
    )
    parser.add_argument("--skip-focus", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    manifest = str(args.manifest)
    if not os.path.exists(manifest):
        raise FileNotFoundError(f"manifest not found: {manifest}")
    manifest_targets = _read_manifest_targets(manifest)
    if bool(args.strict_baseline):
        _validate_baseline_target_set(manifest_targets)

    report_csv = "runs/accuracy_external_report.csv"
    report_json = "runs/accuracy_external_report.json"
    quality_csv = "runs/structure_quality_curated.csv"
    quality_json = "runs/structure_quality_curated.json"
    packet_json = f"runs/external_eval_packet_{args.packet_version}_plus_sources.json"
    focus_csv = "runs/accuracy_external_focus_worst3.csv"
    focus_json = "runs/accuracy_external_focus_worst3.json"
    stamp = dt.date.today().isoformat()
    md_only_manifest = str(args.md_only_manifest)
    md_only_summary_json = str(args.md_only_summary_json)
    md_ref_validation_json = str(args.md_reference_validation_json)
    md_ref_validation_csv = str(args.md_reference_validation_csv)
    md_gap_json = str(args.md_gap_json) if args.md_gap_json else f"runs/md_gap_report_{stamp}.json"

    # 1) Full external accuracy report
    _run_cmd(
        [
            "python3",
            "benchmark/accuracy_bench.py",
            "--targets",
            "all",
            "--reference-source",
            "external",
            "--external-manifest",
            manifest,
            "--steps",
            str(int(args.external_steps)),
            "--runs",
            str(int(args.external_runs)),
            "--out-csv",
            report_csv,
            "--out-json",
            report_json,
        ],
        dry_run=bool(args.dry_run),
    )

    # 2) Structure quality curation
    quality_cmd = ["python3", "tools/curate_structure_quality.py"]
    if str(args.quality_manifest_csv or "").strip():
        quality_cmd.extend(["--manifest-csv", str(args.quality_manifest_csv)])
    else:
        quality_cmd.extend(["--pdb-glob", str(args.pdb_glob)])
    quality_cmd.extend(["--out-csv", quality_csv, "--out-json", quality_json])
    _run_cmd(quality_cmd, dry_run=bool(args.dry_run))

    # 3) Unified packet build
    _run_cmd(
        [
            "python3",
            "tools/build_external_eval_packet.py",
            "--packet-version",
            str(args.packet_version),
            "--accuracy-external-csv",
            report_csv,
            "--quality-curation-csv",
            quality_csv,
            "--out-json",
            packet_json,
        ],
        dry_run=bool(args.dry_run),
    )

    # 4) Worst-target focused rerun
    if not bool(args.skip_focus):
        worst_targets = _extract_worst_targets(report_csv=report_csv, top_k=int(args.focus_top_k))
        if len(worst_targets) > 0:
            _run_cmd(
                [
                    "python3",
                    "benchmark/accuracy_bench.py",
                    "--targets",
                    ",".join(worst_targets),
                    "--reference-source",
                    "external",
                    "--external-manifest",
                    manifest,
                    "--steps",
                    str(int(args.focus_steps)),
                    "--runs",
                    str(int(args.focus_runs)),
                    "--out-csv",
                    focus_csv,
                    "--out-json",
                    focus_json,
                ],
                dry_run=bool(args.dry_run),
            )

    # 5) Submission folder fixed snapshots
    subdir = Path(str(args.submission_dir))
    if not bool(args.dry_run):
        subdir.mkdir(parents=True, exist_ok=True)
        fixed_packet = _copy_with_stamp(
            src=packet_json,
            dst_dir=str(subdir),
            stem=f"external_eval_packet_{args.packet_version}_fixed",
            stamp=stamp,
            suffix=".json",
        )
        _copy_with_stamp(
            src=report_csv,
            dst_dir=str(subdir),
            stem="accuracy_external_report",
            stamp=stamp,
            suffix=".csv",
        )
        _copy_with_stamp(
            src=quality_csv,
            dst_dir=str(subdir),
            stem="structure_quality_curated",
            stamp=stamp,
            suffix=".csv",
        )
        send_link = subdir / "SEND_THIS_FILE.json"
        if send_link.exists() or send_link.is_symlink():
            send_link.unlink()
        send_link.symlink_to(Path(fixed_packet).name)

    # 6) Build MD-only manifest view
    if bool(args.build_md_only_manifest):
        cmd = [
            "python3",
            "tools/build_md_only_manifest.py",
            "--input-manifest",
            manifest,
            "--out-manifest",
            md_only_manifest,
            "--out-json",
            md_only_summary_json,
            "--md-engine-regex",
            str(args.md_engine_regex),
        ]
        if bool(args.require_existing_md_paths):
            cmd.append("--require-existing-paths")
        else:
            cmd.append("--no-require-existing-paths")
        if args.strict_md_only_target_count is not None:
            cmd.extend(["--strict-target-count", str(int(args.strict_md_only_target_count))])
        _run_cmd(cmd, dry_run=bool(args.dry_run))

    # 7) Baseline mode status snapshot
    status = {
        "date_local": dt.date.today().isoformat(),
        "mode": "baseline_10_targets",
        "strict_baseline": bool(args.strict_baseline),
        "full_param_optimization_deferred": not bool(args.full_param_optimization),
        "manifest": manifest,
        "manifest_target_count": int(len(manifest_targets)),
        "expected_target_count": int(len(ResearchConstants.CHALLENGES)),
        "outputs": {
            "accuracy_external_report_csv": report_csv,
            "structure_quality_curated_csv": quality_csv,
            "external_eval_packet_json": packet_json,
            "accuracy_external_focus_csv": focus_csv if not bool(args.skip_focus) else None,
            "md_only_manifest_csv": md_only_manifest if bool(args.build_md_only_manifest) else None,
            "md_only_summary_json": md_only_summary_json if bool(args.build_md_only_manifest) else None,
            "md_reference_validation_json": md_ref_validation_json if bool(args.validate_md_references) else None,
            "md_reference_validation_csv": md_ref_validation_csv if bool(args.validate_md_references) else None,
            "md_gap_report_json": md_gap_json if bool(args.update_md_gap_report) else None,
            "submission_dir": str(subdir),
        },
    }
    status_json = str(args.status_json)
    if not bool(args.dry_run):
        os.makedirs(os.path.dirname(status_json) or ".", exist_ok=True)
        with open(status_json, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2)
        print("status_json:", status_json)

    # 8) MD reference validation
    if bool(args.validate_md_references):
        validate_manifest = md_only_manifest if bool(args.build_md_only_manifest) else manifest
        cmd = [
            "python3",
            "tools/validate_md_reference_set.py",
            "--manifest-csv",
            validate_manifest,
            "--out-json",
            md_ref_validation_json,
            "--out-csv",
            md_ref_validation_csv,
            "--md-engine-regex",
            str(args.md_engine_regex),
            "--expected-target-count",
            str(int(args.expected_target_count)),
        ]
        if bool(args.strict_md_reference_validation):
            cmd.append("--strict")
        else:
            cmd.append("--no-strict")
        _run_cmd(cmd, dry_run=bool(args.dry_run))

    # 9) MD gap report update
    if bool(args.update_md_gap_report):
        _run_cmd(
            [
                "python3",
                "tools/report_md_gap.py",
                "--accuracy-csv",
                report_csv,
                "--manifest-csv",
                manifest,
                "--md-only-manifest-csv",
                md_only_manifest,
                "--baseline-status-json",
                status_json,
                "--md-engine-regex",
                str(args.md_engine_regex),
                "--expected-target-count",
                str(int(args.expected_target_count)),
                "--out-json",
                md_gap_json,
            ],
            dry_run=bool(args.dry_run),
        )

    # 10) Refresh runs index
    _run_cmd(
        ["python3", "tools/classify_runs_files.py"],
        dry_run=bool(args.dry_run),
    )

    print("Done.")
    print("manifest:", manifest)
    print("report_csv:", report_csv)
    print("quality_csv:", quality_csv)
    print("packet_json:", packet_json)
    print("md_only_manifest:", md_only_manifest if bool(args.build_md_only_manifest) else None)
    print("md_reference_validation_json:", md_ref_validation_json if bool(args.validate_md_references) else None)
    print("md_gap_json:", md_gap_json if bool(args.update_md_gap_report) else None)
    print("submission_dir:", str(subdir))


if __name__ == "__main__":
    main()
