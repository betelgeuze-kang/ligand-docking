#!/usr/bin/env python3
"""Strict entrypoint for the repeatable Engine V2 D1 development lane.

Version 2 preserves the v1 report schema and metrics while rejecting non-string
manifest result paths before the v1 analyzer can normalize them with ``str``.
It does not execute docking or grant Fresh-128, Stage 0, benchmark, scientific,
product, customer, or performance authority.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_engine_v2_d1_development_v1",
    ROOT / "tools/run_engine_v2_d1_development_v1.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load D1 development v1 implementation")
V1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V1)


class D1DevelopmentV2Error(ValueError):
    """The strict v2 D1 input is malformed or crosses authority."""


def _strict_manifest(path: Path) -> dict[str, Any]:
    document = V1._load_json(path)
    if document.get("schema_id") != V1.MANIFEST_SCHEMA_ID:
        raise D1DevelopmentV2Error("D1 manifest schema changed")
    if document.get("profile_id") != V1.PROFILE_ID:
        raise D1DevelopmentV2Error("D1 manifest profile changed")
    rows = document.get("cases")
    if type(rows) is not list or len(rows) != V1.CASE_COUNT:
        raise D1DevelopmentV2Error("D1 manifest must contain exactly 32 cases")
    for index, row in enumerate(rows):
        if type(row) is not dict or set(row) != {"case_id", "result_path"}:
            raise D1DevelopmentV2Error(f"manifest row {index} has an invalid shape")
        V1._case_id(row["case_id"], name=f"manifest case {index}")
        result_path = row["result_path"]
        if type(result_path) is not str or not result_path:
            raise D1DevelopmentV2Error(
                f"manifest row {index} result_path must be a non-empty string"
            )
    return document


def build_report(
    *,
    profile_path: Path,
    manifest_path: Path,
    fresh_registry_path: Path,
    result_root: Path,
    baseline_manifest_path: Path | None = None,
    baseline_result_root: Path | None = None,
) -> dict[str, Any]:
    _strict_manifest(manifest_path)
    if baseline_manifest_path is not None:
        _strict_manifest(baseline_manifest_path)
    return V1.build_report(
        profile_path=profile_path,
        manifest_path=manifest_path,
        fresh_registry_path=fresh_registry_path,
        result_root=result_root,
        baseline_manifest_path=baseline_manifest_path,
        baseline_result_root=baseline_result_root,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        type=Path,
        default=ROOT / "config/engine_v2_d1_development_profile_v1.json",
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--fresh-case-registry", type=Path, required=True)
    parser.add_argument("--result-root", type=Path, required=True)
    parser.add_argument("--baseline-manifest", type=Path)
    parser.add_argument("--baseline-result-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = build_report(
            profile_path=args.profile,
            manifest_path=args.manifest,
            fresh_registry_path=args.fresh_case_registry,
            result_root=args.result_root,
            baseline_manifest_path=args.baseline_manifest,
            baseline_result_root=args.baseline_result_root,
        )
        V1._write_absent(args.output, report)
    except (D1DevelopmentV2Error, V1.D1DevelopmentError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(args.output.resolve()),
                "report_sha256": report["report_sha256"],
                "authority_granted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
