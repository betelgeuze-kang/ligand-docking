#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch4_stage_review_manifest import _resolve
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_DIR = "runs"
DEFAULT_OUT_JSON = "runs/idp_3bead_release_cleanup_review_manifest_current.json"
DEFAULT_OUT_CSV = "runs/idp_3bead_release_cleanup_review_manifest_current.csv"
DEFAULT_OUT_MD = "runs/idp_3bead_release_cleanup_review_manifest_current.md"

CURRENT_KEEP_GLOBS = [
    "idp_3bead_release_baseline_current.*",
    "idp_3bead_release_manifest_current.*",
    "idp_3bead_release_regression_current.*",
    "idp_3bead_release_report_current.*",
    "idp_3bead_release_smoke_*current.*",
    "idp_3bead_release_ci_smoke_current*",
    "idp_3bead_global_aggregation_*current.*",
]
SKIP_REFERENCE_SOURCE_TOKENS = (
    "cleanup",
    "archive_first",
    "apply_report",
    "cold_storage_offload",
)
REFERENCE_RE = re.compile(r"idp_3bead_release[\w.\-]+")
TRAILING_SUFFIXES = [
    "_baseline_manifest",
    "_release_candidate_eval",
    "_global_aggregation_calibrator",
    "_global_aggregation_dashboard",
    "_global_aggregation_predictions",
    "_summary",
    "_manifest",
    "_regression",
    "_runner",
]


def _file_size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def _smoke_prefix(name: str) -> str:
    stem = Path(name).stem
    if "_fold" in stem:
        return stem.split("_fold", 1)[0]
    for suffix in TRAILING_SUFFIXES:
        if suffix in stem:
            return stem.split(suffix, 1)[0]
    return stem


def _gather_current_keep_files(runs_root: Path) -> set[Path]:
    keep: set[Path] = set()
    for pattern in CURRENT_KEEP_GLOBS:
        keep.update(path for path in runs_root.glob(pattern) if path.is_file())
    return keep


def _gather_reference_historical_files(runs_root: Path, current_keep_files: set[Path]) -> dict[str, set[str]]:
    references: dict[str, set[str]] = defaultdict(set)
    for artifact in runs_root.glob("*_current.*"):
        if artifact.suffix not in {".json", ".md", ".csv", ".html"} or not artifact.is_file():
            continue
        if any(token in artifact.name for token in SKIP_REFERENCE_SOURCE_TOKENS):
            continue
        try:
            text = artifact.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for token in REFERENCE_RE.findall(text):
            ref_name = Path(token).name
            if "_current." in ref_name:
                continue
            ref_path = runs_root / ref_name
            if not ref_path.exists() or ref_path in current_keep_files:
                continue
            if ref_name.startswith("idp_3bead_release_smoke_current_"):
                prefix = _smoke_prefix(ref_name)
            else:
                prefix = Path(ref_name).stem
            references[prefix].add(artifact.name)
    return references


def build_payload(runs_dir: str) -> dict[str, Any]:
    runs_root = _resolve(runs_dir)
    current_keep_files = _gather_current_keep_files(runs_root)
    reference_holds = _gather_reference_historical_files(runs_root, current_keep_files)

    rows: list[dict[str, Any]] = []
    keep_bytes = sum(_file_size(path) for path in current_keep_files)
    rows.append(
        {
            "prefix": "idp_3bead_release_current_artifacts",
            "classification": "protected_current_artifacts",
            "recommended_disposition": "keep_in_active_root",
            "file_count": len(current_keep_files),
            "size_mb": round(keep_bytes / (1024 * 1024), 2),
            "reference_examples": "",
            "sample_artifacts": "; ".join(path.name for path in sorted(current_keep_files)[:3]),
            "reason": "Current release smoke, manifest, report, and aggregation artifacts are still the active source of truth.",
        }
    )

    for prefix, refs in sorted(reference_holds.items()):
        matched = sorted(path for path in runs_root.glob(prefix + "*") if path.is_file())
        rows.append(
            {
                "prefix": prefix,
                "classification": "review_hold_current_reference",
                "recommended_disposition": "review_only_keep_until_reference_replaced",
                "file_count": len(matched),
                "size_mb": round(sum(_file_size(path) for path in matched) / (1024 * 1024), 2),
                "reference_examples": "; ".join(sorted(refs)[:5]),
                "sample_artifacts": "; ".join(path.name for path in matched[:3]),
                "reason": "Current release artifacts still point at this historical release lineage, so keep it until those references are thinned or replaced.",
            }
        )

    candidate_groups: dict[str, list[Path]] = defaultdict(list)
    for path in runs_root.glob("idp_3bead_release_smoke_current_*"):
        if not path.is_file() or path in current_keep_files:
            continue
        prefix = _smoke_prefix(path.name)
        if prefix in reference_holds:
            continue
        candidate_groups[prefix].append(path)

    for prefix, matched in sorted(candidate_groups.items(), key=lambda item: sum(_file_size(p) for p in item[1]), reverse=True):
        rows.append(
            {
                "prefix": prefix,
                "classification": "historical_release_smoke_candidate",
                "recommended_disposition": "review_for_archive_after_prefix_signoff",
                "file_count": len(matched),
                "size_mb": round(sum(_file_size(path) for path in matched) / (1024 * 1024), 2),
                "reference_examples": "",
                "sample_artifacts": "; ".join(path.name for path in matched[:3]),
                "reason": "Historical release-smoke lineage superseded by the current speedopt baseline and safe to archive as a batch once signed off.",
            }
        )

    stale_rows = [row for row in rows if row["recommended_disposition"] == "review_for_archive_after_prefix_signoff"]
    review_rows = [row for row in rows if row["classification"] == "review_hold_current_reference"]
    summary = {
        "status": "idp_3bead_release_cleanup_review_manifest_ready",
        "runs_dir": str(runs_root),
        "protected_current_file_count": len(current_keep_files),
        "protected_current_size_mb": round(keep_bytes / (1024 * 1024), 2),
        "review_hold_prefix_count": len(review_rows),
        "stale_candidate_prefix_count": len(stale_rows),
        "stale_candidate_size_gb": round(sum(row["size_mb"] for row in stale_rows) / 1024, 2),
        "next_required_step": "Archive the stale release-smoke prefixes first, keep the speedopt3full/r3/r9 baseline pack in active root, then rebuild the cleanup audit.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP 3-Bead Release Cleanup Review Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- runs_dir: `{s['runs_dir']}`",
        f"- protected_current_file_count: `{s['protected_current_file_count']}`",
        f"- protected_current_size_mb: `{s['protected_current_size_mb']}`",
        f"- review_hold_prefix_count: `{s['review_hold_prefix_count']}`",
        f"- stale_candidate_prefix_count: `{s['stale_candidate_prefix_count']}`",
        f"- stale_candidate_size_gb: `{s['stale_candidate_size_gb']}`",
        "",
        "| prefix | classification | file_count | size_mb | recommended_disposition |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['prefix']}` | `{row['classification']}` | `{row['file_count']}` | `{row['size_mb']}` | `{row['recommended_disposition']}` |"
        )
    lines.extend(["", "## Detail", ""])
    for row in payload["rows"]:
        lines.extend(
            [
                f"### {row['prefix']}",
                "",
                f"- classification: `{row['classification']}`",
                f"- recommended_disposition: `{row['recommended_disposition']}`",
                f"- file_count: `{row['file_count']}`",
                f"- size_mb: `{row['size_mb']}`",
                f"- reference_examples: `{row['reference_examples']}`" if row["reference_examples"] else "- reference_examples: `n/a`",
                f"- sample_artifacts: `{row['sample_artifacts']}`",
                f"- reason: {row['reason']}",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a cleanup review manifest for idp_3bead_release historical smoke files.")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args.runs_dir)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
