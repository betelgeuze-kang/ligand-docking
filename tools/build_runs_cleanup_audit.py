#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.prune_runs_files import prune_runs_files

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RUNS_DIR = "runs"
DEFAULT_OUT_JSON = "runs/runs_cleanup_audit_current.json"
DEFAULT_OUT_CSV = "runs/runs_cleanup_audit_current.csv"
DEFAULT_OUT_MD = "runs/runs_cleanup_audit_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _prefix_for_name(name: str) -> str:
    parts = name.split("_")
    return "_".join(parts[:3]) if len(parts) >= 3 else name


def _cleanup_hint(prefix: str) -> tuple[str, str]:
    if prefix.startswith("external_validation_"):
        return ("review_archive_candidate", "Large external-validation raw intermediates. Keep accepted/current summaries, then archive older raw json/csv batches.")
    if prefix.startswith("idp_3bead_holdout"):
        return ("review_intermediate_candidate", "High-count IDP holdout intermediates. Keep current accepted prefixes, then archive stale fold/progress/summary duplicates.")
    if prefix.startswith("idp_virtual_hbond") or prefix.startswith("idp_3bead_vhbond"):
        return ("review_archive_candidate", "Older vhbond/parity outputs are likely archive-first candidates after accepted current artifacts are protected.")
    if prefix.startswith("ligand_blind_") or prefix.startswith("ligand_htvs_") or prefix.startswith("ligand_stress_"):
        return ("manual_review_large_pipeline", "Ligand pipeline artifacts are meaningful but can accumulate. Review by accepted run prefix before archiving.")
    return ("manual_review", "Needs manual review before any archival step.")


def build_payload(runs_dir: str = DEFAULT_RUNS_DIR, *, top_n: int = 12) -> dict[str, Any]:
    root = _resolve(runs_dir)
    top_level_files = [p for p in root.iterdir() if p.is_file()]
    top_level_dirs = [p for p in root.iterdir() if p.is_dir()]

    total_size_bytes = 0
    prefix_stats: dict[str, dict[str, float]] = defaultdict(lambda: {"file_count": 0, "size_bytes": 0})
    current_artifact_file_count = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            continue
        total_size_bytes += size
        if path.parent == root:
            prefix = _prefix_for_name(path.name)
            prefix_stats[prefix]["file_count"] += 1
            prefix_stats[prefix]["size_bytes"] += size
            if "_current." in path.name:
                current_artifact_file_count += 1

    prune_preview = prune_runs_files(runs_dir=str(root), keep_per_role=2, dry_run=True)
    raw_prune_scanned_files = int(prune_preview.get("scanned_files", 0) or 0)
    raw_prune_moved_files = int(prune_preview.get("moved_files", 0) or 0)
    raw_prune_move_ratio = (
        round(raw_prune_moved_files / raw_prune_scanned_files, 4)
        if raw_prune_scanned_files
        else 0.0
    )
    raw_prune_safe_to_execute_now = raw_prune_move_ratio <= 0.25

    ranked = sorted(
        prefix_stats.items(),
        key=lambda kv: (kv[1]["size_bytes"], kv[1]["file_count"]),
        reverse=True,
    )[:top_n]
    rows = []
    for prefix, stats in ranked:
        candidate_status, cleanup_hint = _cleanup_hint(prefix)
        rows.append(
            {
                "prefix": prefix,
                "top_level_file_count": int(stats["file_count"]),
                "top_level_size_mb": round(stats["size_bytes"] / (1024 * 1024), 2),
                "candidate_status": candidate_status,
                "cleanup_hint": cleanup_hint,
            }
        )

    top_size_prefix = rows[0]["prefix"] if rows else ""
    top_size_prefix_size_mb = rows[0]["top_level_size_mb"] if rows else 0
    summary = {
        "runs_dir": str(root),
        "total_size_gb": round(total_size_bytes / (1024 * 1024 * 1024), 2),
        "top_level_file_count": len(top_level_files),
        "top_level_dir_count": len(top_level_dirs),
        "current_artifact_file_count": current_artifact_file_count,
        "top_size_prefix": top_size_prefix,
        "top_size_prefix_size_mb": top_size_prefix_size_mb,
        "raw_prune_scanned_files": raw_prune_scanned_files,
        "raw_prune_moved_files": raw_prune_moved_files,
        "raw_prune_move_ratio": raw_prune_move_ratio,
        "raw_prune_safe_to_execute_now": raw_prune_safe_to_execute_now,
        "archive_only_cleanup_recommended": True,
        "next_required_step": (
            "Do not execute raw prune_runs_files.py yet. First freeze a protection manifest for current/accepted run prefixes, then archive stale external_validation and idp_3bead_holdout intermediates in a reviewable batch."
            if not raw_prune_safe_to_execute_now
            else "A conservative archive-first cleanup is possible, but still freeze a protection manifest before moving any historical files."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Runs Cleanup Audit",
        "",
        f"- runs_dir: `{s['runs_dir']}`",
        f"- total_size_gb: `{s['total_size_gb']}`",
        f"- top_level_file_count: `{s['top_level_file_count']}`",
        f"- top_level_dir_count: `{s['top_level_dir_count']}`",
        f"- current_artifact_file_count: `{s['current_artifact_file_count']}`",
        f"- top_size_prefix: `{s['top_size_prefix']}`",
        f"- top_size_prefix_size_mb: `{s['top_size_prefix_size_mb']}`",
        f"- raw_prune_scanned_files: `{s['raw_prune_scanned_files']}`",
        f"- raw_prune_moved_files: `{s['raw_prune_moved_files']}`",
        f"- raw_prune_move_ratio: `{s['raw_prune_move_ratio']}`",
        f"- raw_prune_safe_to_execute_now: `{s['raw_prune_safe_to_execute_now']}`",
        f"- archive_only_cleanup_recommended: `{s['archive_only_cleanup_recommended']}`",
        "",
        "## Largest Top-Level Prefixes",
        "",
        "| prefix | top_level_file_count | top_level_size_mb | candidate_status | cleanup_hint |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['prefix']}` | `{row['top_level_file_count']}` | `{row['top_level_size_mb']}` | `{row['candidate_status']}` | {row['cleanup_hint']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a non-destructive storage cleanup audit for runs/.")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--top-n", type=int, default=12)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(args.runs_dir, top_n=int(args.top_n))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
