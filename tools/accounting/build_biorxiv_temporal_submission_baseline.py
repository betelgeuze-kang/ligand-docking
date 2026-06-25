#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Freeze the current temporal provenance state as a submission baseline summary.")
    ap.add_argument("--coverage-json", default="runs/biorxiv_temporal_provenance_mapping_coverage_current.json")
    ap.add_argument("--remaining-policy-json", default="runs/biorxiv_temporal_idp_remaining_policy_current.json")
    ap.add_argument("--synthetic-progress-json", default="runs/biorxiv_temporal_idp_synthetic_progress_current.json")
    ap.add_argument("--submission-assets-zip", default="runs/biorxiv_submission_assets_current.zip")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_submission_baseline_current.json")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_submission_baseline_current.md")
    args = ap.parse_args(argv)

    coverage = _read_json((ROOT / args.coverage_json).resolve())
    remaining = _read_json((ROOT / args.remaining_policy_json).resolve())
    synthetic = _read_json((ROOT / args.synthetic_progress_json).resolve())

    summary = {
        "coverage_json": str((ROOT / args.coverage_json).resolve()),
        "remaining_policy_json": str((ROOT / args.remaining_policy_json).resolve()),
        "synthetic_progress_json": str((ROOT / args.synthetic_progress_json).resolve()),
        "submission_assets_zip": str((ROOT / args.submission_assets_zip).resolve()),
        "ligand_item_ready_count": coverage.get("ligand", {}).get("item_ready_count"),
        "ligand_dataset_ready_count": coverage.get("ligand", {}).get("dataset_ready_count"),
        "idp_item_ready_count": coverage.get("idp", {}).get("item_ready_count"),
        "idp_dataset_ready_count": coverage.get("idp", {}).get("dataset_ready_count"),
        "overall_item_ready_count": coverage.get("overall_item_ready_count"),
        "overall_dataset_ready_count": coverage.get("overall_dataset_ready_count"),
        "remaining_policy_counts": remaining.get("policy_counts", {}),
        "remaining_dataset_rows": remaining.get("rows", []),
        "synthetic_item_ready_count": synthetic.get("item_ready_count"),
        "synthetic_dataset_ready_count": synthetic.get("dataset_ready_count"),
    }
    _write_json((ROOT / args.out_json).resolve(), summary)

    lines = [
        "# Temporal Submission Baseline",
        "",
        f"- coverage_json: `{summary['coverage_json']}`",
        f"- remaining_policy_json: `{summary['remaining_policy_json']}`",
        f"- synthetic_progress_json: `{summary['synthetic_progress_json']}`",
        f"- submission_assets_zip: `{summary['submission_assets_zip']}`",
        "",
        "## Counts",
        "",
        f"- ligand_item_ready_count: `{summary['ligand_item_ready_count']}`",
        f"- ligand_dataset_ready_count: `{summary['ligand_dataset_ready_count']}`",
        f"- idp_item_ready_count: `{summary['idp_item_ready_count']}`",
        f"- idp_dataset_ready_count: `{summary['idp_dataset_ready_count']}`",
        f"- overall_item_ready_count: `{summary['overall_item_ready_count']}`",
        f"- overall_dataset_ready_count: `{summary['overall_dataset_ready_count']}`",
        "",
        "## Remaining IDP Policy Counts",
        "",
    ]
    for key, value in sorted(summary["remaining_policy_counts"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Remaining Dataset-Level Rows", ""])
    for row in summary["remaining_dataset_rows"]:
        lines.extend(
            [
                f"### {row.get('holdout_name', '')}",
                "",
                f"- policy_label: `{row.get('policy_label', '')}`",
                f"- curation_status: `{row.get('curation_status', '')}`",
                "",
            ]
        )
    _write_text((ROOT / args.out_md).resolve(), "\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
