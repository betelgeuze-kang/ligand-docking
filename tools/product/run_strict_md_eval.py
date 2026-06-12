#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from types import SimpleNamespace
from typing import Any, Dict, Optional, Sequence

from benchmark.accuracy_bench import run_accuracy_report
from core.definitions import ResearchConstants
from tools.report_md_gap import build_gap_report
from tools.validate_md_reference_set import validate_md_reference_set
from tools.validate_md_provenance import validate_md_provenance


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(text).strip().lower()).strip("_")
    return s or "run"


def _default_paths(out_dir: str, label: str, stamp: str) -> Dict[str, str]:
    safe_label = _slug(label)
    base = os.path.abspath(str(out_dir))
    return {
        "accuracy_csv": os.path.join(base, f"accuracy_external_strict_md_{safe_label}_{stamp}.csv"),
        "accuracy_json": os.path.join(base, f"accuracy_external_strict_md_{safe_label}_{stamp}.json"),
        "validation_csv": os.path.join(base, f"md_reference_validation_strict_md_{safe_label}_{stamp}.csv"),
        "validation_json": os.path.join(base, f"md_reference_validation_strict_md_{safe_label}_{stamp}.json"),
        "gap_json": os.path.join(base, f"md_gap_report_strict_md_{safe_label}_{stamp}.json"),
        "provenance_csv": os.path.join(base, f"md_reference_validation_provenance_strict_md_{safe_label}_{stamp}.csv"),
        "provenance_json": os.path.join(base, f"md_reference_validation_provenance_strict_md_{safe_label}_{stamp}.json"),
        "summary_json": os.path.join(base, f"strict_md_eval_{safe_label}_{stamp}.json"),
    }


def run_strict_md_eval(args: argparse.Namespace) -> Dict[str, Any]:
    stamp = str(args.date_stamp) if args.date_stamp else dt.date.today().isoformat()
    paths = _default_paths(out_dir=str(args.out_dir), label=str(args.label), stamp=stamp)
    os.makedirs(str(args.out_dir), exist_ok=True)

    validation = validate_md_reference_set(
        manifest_csv=str(args.manifest_csv),
        out_json=paths["validation_json"],
        out_csv=paths["validation_csv"],
        md_engine_regex=str(args.md_engine_regex),
        expected_target_count=int(args.expected_target_count),
        strict=bool(args.strict_validation),
    )

    provenance_payload = None
    provenance_ready = None
    if bool(getattr(args, "run_provenance_validation", False)):
        provenance_payload = validate_md_provenance(
            manifest_csv=str(args.manifest_csv),
            out_json=paths["provenance_json"],
            out_csv=paths["provenance_csv"],
            engine_regex=str(args.md_engine_regex),
            source_engine_regex=str(getattr(args, "provenance_source_engine_regex", args.md_engine_regex)),
            require_source_engine=bool(getattr(args, "provenance_require_source_engine", True)),
            require_source_path=bool(getattr(args, "provenance_require_source_path", False)),
            expected_target_count=int(args.expected_target_count),
            strict=bool(getattr(args, "provenance_strict", False)),
        )
        provenance_ready = bool(provenance_payload.get("summary", {}).get("ready", False))

    acc_args = SimpleNamespace(
        targets=str(args.targets),
        steps=int(args.steps),
        runs=int(args.runs),
        noise=float(args.noise),
        seed_base=int(args.seed_base),
        reference_source="external",
        external_manifest=str(args.manifest_csv),
        external_key=None,
        external_frame=-1,
        external_summary_csv=None,
        out_csv=paths["accuracy_csv"],
        out_json=paths["accuracy_json"],
    )
    accuracy = run_accuracy_report(acc_args)

    gap = build_gap_report(
        accuracy_csv=paths["accuracy_csv"],
        manifest_csv=str(args.manifest_csv),
        md_only_manifest_csv=str(args.manifest_csv),
        baseline_status_json=None,
        out_json=paths["gap_json"],
        md_engine_regex=str(args.md_engine_regex),
        expected_target_count=int(args.expected_target_count),
    )

    validation_ready = bool(validation.get("summary", {}).get("ready", False))
    gap_ready = bool(gap.get("status", {}).get("real_md_comparison_ready", False))

    failed_checks = []
    if not validation_ready:
        failed_checks.append("validation_not_ready")
    if bool(args.require_gap_ready) and not gap_ready:
        failed_checks.append("gap_not_ready")
    if bool(getattr(args, "enforce_provenance_gate", False)) and (provenance_ready is False):
        failed_checks.append("provenance_not_ready")

    payload: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "label": str(args.label),
        "manifest_csv": str(args.manifest_csv),
        "outputs": paths,
        "checks": {
            "validation_ready": validation_ready,
            "gap_ready": gap_ready,
            "provenance_ready": provenance_ready,
            "require_gap_ready": bool(args.require_gap_ready),
            "enforce_provenance_gate": bool(getattr(args, "enforce_provenance_gate", False)),
            "failed_checks": failed_checks,
            "pass": len(failed_checks) == 0,
        },
        "accuracy_summary": accuracy.get("summary", {}),
        "validation_summary": validation.get("summary", {}),
        "provenance_summary": (
            provenance_payload.get("summary", {}) if isinstance(provenance_payload, dict) else None
        ),
        "gap_status": gap.get("status", {}),
    }

    with open(paths["summary_json"], "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    if len(failed_checks) > 0:
        raise RuntimeError(f"strict md eval failed checks: {failed_checks}")

    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run strict MD external evaluation in one command: validation -> accuracy -> gap report."
    )
    parser.add_argument("--manifest-csv", type=str, default="runs/external_ref_manifest_md_only_proxy_openmm.csv")
    parser.add_argument("--label", type=str, default="proxy_openmm")
    parser.add_argument("--out-dir", type=str, default="runs")
    parser.add_argument("--date-stamp", type=str, default=None)
    parser.add_argument("--targets", type=str, default="all")
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--noise", type=float, default=0.02)
    parser.add_argument("--seed-base", type=int, default=42)
    parser.add_argument("--md-engine-regex", type=str, default=r"(openmm|amber|gromacs)")
    parser.add_argument("--expected-target-count", type=int, default=len(ResearchConstants.CHALLENGES))
    parser.add_argument("--strict-validation", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-gap-ready", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--run-provenance-validation", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--provenance-source-engine-regex", type=str, default=r"(openmm|amber|gromacs)")
    parser.add_argument("--provenance-require-source-engine", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--provenance-require-source-path", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--provenance-strict", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--enforce-provenance-gate", action=argparse.BooleanOptionalAction, default=False)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = run_strict_md_eval(args)
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(2)
    print(json.dumps(payload["checks"], indent=2, ensure_ascii=False))
    print(json.dumps(payload["accuracy_summary"], indent=2, ensure_ascii=False))
    print(f"Wrote: {payload['outputs']['summary_json']}")


if __name__ == "__main__":
    main()
