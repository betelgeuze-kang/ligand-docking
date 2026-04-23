#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_DIR = "runs"
DEFAULT_OUT_JSON = "runs/runs_cleanup_batch3_review_manifest_current.json"
DEFAULT_OUT_CSV = "runs/runs_cleanup_batch3_review_manifest_current.csv"
DEFAULT_OUT_MD = "runs/runs_cleanup_batch3_review_manifest_current.md"

FAMILY_SPECS: list[dict[str, str]] = [
    {
        "family_id": "ligand_blind_gpcr",
        "family_glob": "ligand_blind_gpcr*",
        "family_label": "Blind GPCR screening",
        "why_review_only": "Large historical blind-screen family with multi-stage outputs that still document earlier GPCR triage behavior.",
    },
    {
        "family_id": "ligand_blind_trpv1",
        "family_glob": "ligand_blind_trpv1*",
        "family_label": "Blind TRPV1 screening",
        "why_review_only": "Ion-channel blind-screen family with stage-linked outputs and some heavier trajectory references that should not be swept automatically.",
    },
    {
        "family_id": "ligand_stress_commercial",
        "family_glob": "ligand_stress_commercial*",
        "family_label": "Commercial ligand stress runs",
        "why_review_only": "Commercial stress-test family that still provides historical failure and calibration context for stress rails.",
    },
]

GROUP_SPECS: list[dict[str, Any]] = [
    {
        "subgroup_id": "state_snapshots",
        "label": "state snapshots",
        "suffixes": ["_state.json"],
        "recommended_disposition": "keep_until_family_reopen_decision",
        "reason": "Useful for reconstructing orchestration state; small enough to keep until the family itself is explicitly retired.",
    },
    {
        "subgroup_id": "hard_decoy_artifacts",
        "label": "hard-decoy artifacts",
        "contains": ["_hard_decoy_"],
        "suffixes": ["_hard_decoy_split.csv"],
        "recommended_disposition": "archive_after_family_signoff",
        "reason": "Important for retrospective benchmarking, but not usually needed in the active root once the family is retired.",
    },
    {
        "subgroup_id": "stage0_leakage",
        "label": "stage0 leakage summaries",
        "contains": ["_stage0_leakage_"],
        "recommended_disposition": "archive_first",
        "reason": "Tiny diagnostic surfaces with low operational value once the family is no longer active.",
    },
    {
        "subgroup_id": "stage1_queue_inputs",
        "label": "stage1 queue and input artifacts",
        "contains": ["_stage1_"],
        "recommended_disposition": "review_for_archive_after_sampling",
        "reason": "Often the heaviest retained CSV family; likely archiveable after spot-checking that no active replay depends on them.",
    },
    {
        "subgroup_id": "stage2_active_learning",
        "label": "stage2 active-learning artifacts",
        "contains": ["_stage2_"],
        "recommended_disposition": "review_for_archive_after_sampling",
        "reason": "Historically useful, but the active root usually does not need the whole stage2 stack once a family has been abandoned.",
    },
    {
        "subgroup_id": "stage3_delivery_scores",
        "label": "stage3 delivery and score artifacts",
        "contains": ["_stage3_"],
        "recommended_disposition": "review_for_archive_after_sampling",
        "reason": "Can carry larger score outputs or references to heavy trajectory runs, so review before moving.",
    },
    {
        "subgroup_id": "stage4_or_45_integrity",
        "label": "stage4/stage45 integrity artifacts",
        "contains": ["_stage4", "_stage45_"],
        "recommended_disposition": "archive_first",
        "reason": "Usually small integrity checks that can move early once family-level review approves cleanup.",
    },
    {
        "subgroup_id": "stage5_ranking",
        "label": "stage5 ranking artifacts",
        "contains": ["_stage5_"],
        "recommended_disposition": "review_for_archive_after_sampling",
        "reason": "Compact enough to sample quickly, but still worth a manual look because they summarize final ranking behavior.",
    },
    {
        "subgroup_id": "top_level_summaries",
        "label": "top-level summaries",
        "suffixes": ["_summary.json", "_summary.md"],
        "recommended_disposition": "archive_with_parent_stage",
        "reason": "Small files that should follow whichever parent stage is retained or archived.",
    },
    {
        "subgroup_id": "row_bundles",
        "label": "row bundles",
        "extensions": [".npz"],
        "recommended_disposition": "manual_review_heavy_bundle",
        "reason": "Binary bundles are small in count but can be meaningful or expensive to recreate, so keep them review-only.",
    },
    {
        "subgroup_id": "aggregate_misc",
        "label": "aggregate, runs, and claim-split misc",
        "contains": ["_aggregate", "_runs", "_claim_split", "_rows", "_score_decomp", "_trajectory_aux", "_leakage_"],
        "recommended_disposition": "review_for_archive_after_sampling",
        "reason": "Catch-all historical traces that are often safe to archive, but they need a manual pass because they summarize non-stage-specific behavior.",
    },
]


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _file_size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def _matches_group(name: str, group: dict[str, Any]) -> bool:
    if any(name.endswith(suffix) for suffix in group.get("suffixes", [])):
        return True
    if any(token in name for token in group.get("contains", [])):
        return True
    if any(name.endswith(ext) for ext in group.get("extensions", [])):
        return True
    return False


def build_payload(runs_dir: str) -> dict[str, Any]:
    root = _resolve(runs_dir)
    family_rows: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    family_total_bytes = 0

    for family in FAMILY_SPECS:
        files = sorted(path for path in root.glob(family["family_glob"]) if path.is_file())
        family_bytes = sum(_file_size(path) for path in files)
        family_total_bytes += family_bytes
        remaining_names = {path.name for path in files}
        family_rows.append(
            {
                "family_id": family["family_id"],
                "family_label": family["family_label"],
                "file_count": len(files),
                "size_mb": round(family_bytes / (1024 * 1024), 2),
                "why_review_only": family["why_review_only"],
            }
        )
        for group in GROUP_SPECS:
            matched = [path for path in files if path.name in remaining_names and _matches_group(path.name, group)]
            if not matched:
                continue
            for path in matched:
                remaining_names.discard(path.name)
            rows.append(
                {
                    "family_id": family["family_id"],
                    "family_label": family["family_label"],
                    "subgroup_id": group["subgroup_id"],
                    "subgroup_label": group["label"],
                    "match_count": len(matched),
                    "size_mb": round(sum(_file_size(path) for path in matched) / (1024 * 1024), 2),
                    "recommended_disposition": group["recommended_disposition"],
                    "review_only": True,
                    "sample_artifacts": "; ".join(path.name for path in matched[:3]),
                    "reason": group["reason"],
                }
            )

    summary = {
        "status": "runs_cleanup_batch3_review_manifest_ready",
        "runs_dir": str(root),
        "family_count": len(family_rows),
        "review_row_count": len(rows),
        "review_total_size_gb": round(family_total_bytes / (1024 * 1024 * 1024), 2),
        "next_required_step": "Review these family subgroups manually, archive the obvious low-value stage0/stage4/stage45 artifacts first, and keep stage1-stage3 plus binary bundles on review-only hold until the family-level retirement decision is explicit.",
    }
    return {"summary": summary, "families": family_rows, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Runs Cleanup Batch3 Review Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- runs_dir: `{s['runs_dir']}`",
        f"- family_count: `{s['family_count']}`",
        f"- review_row_count: `{s['review_row_count']}`",
        f"- review_total_size_gb: `{s['review_total_size_gb']}`",
        "",
        "## Family Totals",
        "",
        "| family_id | file_count | size_mb | why_review_only |",
        "| --- | ---: | ---: | --- |",
    ]
    for row in payload["families"]:
        lines.append(
            f"| `{row['family_id']}` | `{row['file_count']}` | `{row['size_mb']}` | {row['why_review_only']} |"
        )
    lines.extend(
        [
            "",
            "## Review Rows",
            "",
            "| family_id | subgroup_id | match_count | size_mb | recommended_disposition | review_only |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family_id']}` | `{row['subgroup_id']}` | `{row['match_count']}` | `{row['size_mb']}` | `{row['recommended_disposition']}` | `{row['review_only']}` |"
        )
    lines.extend(["", "## Detail", ""])
    for row in payload["rows"]:
        lines.extend(
            [
                f"### {row['family_id']} / {row['subgroup_id']}",
                "",
                f"- subgroup_label: `{row['subgroup_label']}`",
                f"- match_count: `{row['match_count']}`",
                f"- size_mb: `{row['size_mb']}`",
                f"- recommended_disposition: `{row['recommended_disposition']}`",
                f"- sample_artifacts: `{row['sample_artifacts']}`",
                f"- reason: {row['reason']}",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a review-only batch3 cleanup manifest for older ligand blind/stress families.")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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
