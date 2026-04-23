#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch4_stage_review_manifest import _resolve
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_DIR = "runs"
DEFAULT_OUT_JSON = "runs/idp_3bead_holdout_cleanup_review_manifest_current.json"
DEFAULT_OUT_CSV = "runs/idp_3bead_holdout_cleanup_review_manifest_current.csv"
DEFAULT_OUT_MD = "runs/idp_3bead_holdout_cleanup_review_manifest_current.md"

PROTECTED_PREFIXES = [
    "idp_3bead_holdout_v7_anchor_commercial_pretest_r1",
    "idp_3bead_holdout_v7_anchor_commercial_pretest_r16validation_r1",
    "idp_3bead_holdout_v7_anchor_commercial_pretest_r18validation_r1",
    "idp_3bead_holdout_v7_anchor_commercial_pretest_processcheck_r1",
    "idp_3bead_holdout_v7_broader_shadow_full_r1_debug",
    "idp_3bead_holdout_v7_onewider_repeatability_r1",
    "idp_3bead_holdout_v7_literature_anchor_kfrgsasa_r1",
]

CURRENT_SUFFIXES = {".json", ".md", ".csv"}
IGNORED_CURRENT_REFERENCE_TOKENS = (
    "cleanup",
    "archive_first_",
    "release_smoke_current",
)

STALE_CLASS_REASONS = [
    ("_batch_", "legacy_batch_candidate", "Older batch tuning lineage superseded by current admitted/pretest lanes."),
    ("_sb_rust_", "legacy_branch_candidate", "Historical sb_rust branch lineage now mostly useful only as frozen-label provenance."),
    ("_vhbond_rust_", "legacy_branch_candidate", "Older vhbond branch lineage superseded by current accepted lanes."),
    ("_fastpair_", "legacy_branch_candidate", "Fastpair exploratory lineage predates the current admitted wider-lane decision."),
    ("_kfshadow_", "legacy_branch_candidate", "KF-shadow exploratory lineage predates the final admitted wider-lane repeatability pass unless still referenced by current artifacts."),
    ("_rewired_", "legacy_branch_candidate", "Rewired exploratory lineage no longer drives the active IDP lane."),
    ("_on1_", "legacy_branch_candidate", "Older ON1 exploration lineage is review-only unless explicitly referenced by a current artifact."),
]

PREFIX_CUT_MARKERS = [
    "_fold_inputs",
    "_fold",
    "_baseline_eval_summary",
    "_branch_summary",
    "_candidate_regression_check",
    "_combined_gate_summary",
    "_corrected_eval_summary",
    "_global_aggregation_dashboard",
    "_global_aggregation_calibrator",
    "_release_candidate_eval",
    "_release_regression",
    "_release_manifest",
    "_release_promotion",
    "_quick_summary",
    "_stop_note",
    "_summary",
    "_launch",
    "_live",
    ".launch",
    ".nohup",
]


def _prefix_for_name(name: str) -> str:
    stem = name
    for marker in PREFIX_CUT_MARKERS:
        if marker in stem:
            return stem.split(marker, 1)[0]
    if "." in stem:
        return stem.rsplit(".", 1)[0]
    return stem


def _size_bytes(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def _load_current_reference_map(runs_root: Path, prefixes: list[str]) -> dict[str, list[str]]:
    references: dict[str, list[str]] = {prefix: [] for prefix in prefixes}
    current_paths = sorted(
        path
        for path in runs_root.glob("*current*")
        if path.is_file()
        and "_current" in path.name
        and path.suffix in CURRENT_SUFFIXES
        and not any(token in path.name for token in IGNORED_CURRENT_REFERENCE_TOKENS)
    )
    for current_path in current_paths:
        try:
            text = current_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for prefix in prefixes:
            if prefix in text:
                references[prefix].append(current_path.name)
    return references


def _classify_prefix(prefix: str, current_refs: list[str]) -> tuple[str, str, str]:
    if prefix in PROTECTED_PREFIXES:
        return (
            "protected_current_lane",
            "keep_in_active_root",
            "Explicitly protected current/commercial/pretest/wider-lane run prefix.",
        )
    if current_refs:
        return (
            "review_hold_current_reference",
            "review_only_keep_until_reference_replaced",
            "Current artifacts still reference this prefix, so it stays on review hold even if it looks historical.",
        )
    for token, classification, reason in STALE_CLASS_REASONS:
        if token in prefix:
            return (classification, "review_for_archive_after_prefix_signoff", reason)
    return (
        "review_hold_unclassified",
        "review_only_keep_until_prefix_signoff",
        "Unclassified holdout prefix; keep on review hold until a family-level retirement decision is explicit.",
    )


def build_payload(runs_dir: str = DEFAULT_RUNS_DIR) -> dict[str, Any]:
    runs_root = _resolve(runs_dir)
    files = sorted(path for path in runs_root.glob("idp_3bead_holdout*") if path.is_file())
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        grouped[_prefix_for_name(path.name)].append(path)

    prefixes = sorted(grouped)
    reference_map = _load_current_reference_map(runs_root, prefixes)
    rows: list[dict[str, Any]] = []
    totals = defaultdict(lambda: {"count": 0, "size": 0})

    for prefix in sorted(prefixes, key=lambda value: sum(_size_bytes(p) for p in grouped[value]), reverse=True):
        matched_files = grouped[prefix]
        total_bytes = sum(_size_bytes(path) for path in matched_files)
        current_refs = reference_map.get(prefix, [])
        classification, recommended_disposition, reason = _classify_prefix(prefix, current_refs)
        type_counts = {
            "progress_json_count": sum(1 for path in matched_files if path.name.endswith("_progress.json")),
            "summary_json_count": sum(1 for path in matched_files if path.name.endswith("_summary.json")),
            "summary_md_count": sum(1 for path in matched_files if path.name.endswith("_summary.md")),
            "csv_count": sum(1 for path in matched_files if path.name.endswith(".csv")),
            "npz_count": sum(1 for path in matched_files if path.name.endswith(".npz")),
        }
        rows.append(
            {
                "prefix": prefix,
                "classification": classification,
                "recommended_disposition": recommended_disposition,
                "file_count": len(matched_files),
                "size_mb": round(total_bytes / (1024 * 1024), 2),
                "current_reference_count": len(current_refs),
                "reference_examples": "; ".join(current_refs[:3]),
                "sample_artifacts": "; ".join(path.name for path in matched_files[:3]),
                **type_counts,
                "reason": reason,
            }
        )
        totals[classification]["count"] += 1
        totals[classification]["size"] += total_bytes

    summary = {
        "status": "idp_3bead_holdout_cleanup_review_manifest_ready",
        "runs_dir": str(runs_root),
        "prefix_count": len(rows),
        "protected_prefix_count": totals["protected_current_lane"]["count"],
        "protected_size_gb": round(totals["protected_current_lane"]["size"] / (1024 * 1024 * 1024), 2),
        "review_hold_reference_prefix_count": totals["review_hold_current_reference"]["count"],
        "review_hold_reference_size_gb": round(totals["review_hold_current_reference"]["size"] / (1024 * 1024 * 1024), 2),
        "stale_candidate_prefix_count": sum(
            1
            for row in rows
            if row["recommended_disposition"] == "review_for_archive_after_prefix_signoff"
        ),
        "stale_candidate_size_gb": round(
            sum((row["size_mb"] for row in rows if row["recommended_disposition"] == "review_for_archive_after_prefix_signoff")) / 1024,
            2,
        ),
        "next_required_step": "Keep the explicitly protected admitted/current IDP lanes in place, sample the stale-candidate historical prefixes, and only then prepare a prefix-level archive-first apply for the historical batch/sb_rust/vhbond/fastpair branches.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP 3-Bead Holdout Cleanup Review Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- runs_dir: `{s['runs_dir']}`",
        f"- prefix_count: `{s['prefix_count']}`",
        f"- protected_prefix_count: `{s['protected_prefix_count']}`",
        f"- protected_size_gb: `{s['protected_size_gb']}`",
        f"- review_hold_reference_prefix_count: `{s['review_hold_reference_prefix_count']}`",
        f"- review_hold_reference_size_gb: `{s['review_hold_reference_size_gb']}`",
        f"- stale_candidate_prefix_count: `{s['stale_candidate_prefix_count']}`",
        f"- stale_candidate_size_gb: `{s['stale_candidate_size_gb']}`",
        "",
        "| prefix | classification | recommended_disposition | file_count | size_mb | current_reference_count |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['prefix']}` | `{row['classification']}` | `{row['recommended_disposition']}` | `{row['file_count']}` | `{row['size_mb']}` | `{row['current_reference_count']}` |"
        )
    lines.extend(["", "## Detail", ""])
    for row in payload["rows"][:20]:
        lines.extend(
            [
                f"### {row['prefix']}",
                "",
                f"- classification: `{row['classification']}`",
                f"- recommended_disposition: `{row['recommended_disposition']}`",
                f"- file_count: `{row['file_count']}`",
                f"- size_mb: `{row['size_mb']}`",
                f"- current_reference_count: `{row['current_reference_count']}`",
                f"- reference_examples: `{row['reference_examples']}`",
                f"- sample_artifacts: `{row['sample_artifacts']}`",
                f"- csv_count: `{row['csv_count']}`",
                f"- summary_json_count: `{row['summary_json_count']}`",
                f"- progress_json_count: `{row['progress_json_count']}`",
                f"- npz_count: `{row['npz_count']}`",
                f"- reason: {row['reason']}",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a review-only cleanup manifest for idp_3bead_holdout historical prefixes.")
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
