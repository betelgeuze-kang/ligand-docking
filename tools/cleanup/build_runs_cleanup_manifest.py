#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_DIR = "runs"
DEFAULT_AUDIT_JSON = "runs/runs_cleanup_audit_current.json"
DEFAULT_OUT_JSON = "runs/runs_cleanup_manifest_current.json"
DEFAULT_OUT_CSV = "runs/runs_cleanup_manifest_current.csv"
DEFAULT_OUT_MD = "runs/runs_cleanup_manifest_current.md"
ARCHIVE_PREFIXES = [
    "external_validation_2026-03-21",
    "external_validation_2026-03-22",
    "external_validation_2026-03-23",
    "external_validation_2026-03-25",
    "external_validation_2026-03-26",
]


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(runs_dir: str, audit: dict[str, Any], archive_stamp: str) -> dict[str, Any]:
    root = _resolve(runs_dir)
    archive_root = root / f"archive_{archive_stamp}_external_validation_batch1"
    rows: list[dict[str, Any]] = []
    archive_candidate_file_count = 0
    archive_candidate_size_bytes = 0
    for prefix in ARCHIVE_PREFIXES:
        files = [path for path in root.glob(prefix + "*") if path.is_file()]
        size_bytes = sum(path.stat().st_size for path in files)
        archive_candidate_file_count += len(files)
        archive_candidate_size_bytes += size_bytes
        rows.append(
            {
                "batch_id": "external_validation_batch1",
                "prefix": prefix,
                "file_count": len(files),
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "archive_subdir": str(Path(archive_root.name) / prefix),
                "archive_now": bool(files),
                "reason": "Large stale external-validation intermediates already superseded by current summary artifacts.",
            }
        )
    rows.append(
        {
            "batch_id": "protect_hold",
            "prefix": "idp_3bead_holdout",
            "file_count": 0,
            "size_mb": 0.0,
            "archive_subdir": "",
            "archive_now": False,
            "reason": "Protected for now because current IDP decision surfaces still depend on these experimental outputs.",
        }
    )
    rows.append(
        {
            "batch_id": "protect_hold",
            "prefix": "*_current.*",
            "file_count": 0,
            "size_mb": 0.0,
            "archive_subdir": "",
            "archive_now": False,
            "reason": "Always protect current artifacts and outbound wet-lab packets.",
        }
    )
    summary = {
        "status": "runs_cleanup_manifest_ready",
        "runs_dir": str(root),
        "archive_root": str(archive_root),
        "archive_candidate_batch_count": sum(1 for row in rows if row["archive_now"]),
        "archive_candidate_file_count": archive_candidate_file_count,
        "archive_candidate_size_gb": round(archive_candidate_size_bytes / (1024 * 1024 * 1024), 2),
        "protected_pattern_count": 2,
        "audit_source_artifact": "runs/runs_cleanup_audit_current.md",
        "raw_prune_safe_to_execute_now": bool(audit.get("summary", {}).get("raw_prune_safe_to_execute_now", False)),
        "next_required_step": "Apply this manifest as an archive-only move. Do not run raw prune_runs_files.py.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Runs Cleanup Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- runs_dir: `{s['runs_dir']}`",
        f"- archive_root: `{s['archive_root']}`",
        f"- archive_candidate_batch_count: `{s['archive_candidate_batch_count']}`",
        f"- archive_candidate_file_count: `{s['archive_candidate_file_count']}`",
        f"- archive_candidate_size_gb: `{s['archive_candidate_size_gb']}`",
        f"- protected_pattern_count: `{s['protected_pattern_count']}`",
        f"- audit_source_artifact: `{s['audit_source_artifact']}`",
        f"- raw_prune_safe_to_execute_now: `{s['raw_prune_safe_to_execute_now']}`",
        "",
        "| batch_id | prefix | file_count | size_mb | archive_now | archive_subdir |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['batch_id']}` | `{row['prefix']}` | `{row['file_count']}` | `{row['size_mb']}` | `{row['archive_now']}` | `{row['archive_subdir']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a targeted archive-only cleanup manifest for runs/.")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--audit-json", default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--archive-stamp", default="2026-03-29")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(args.runs_dir, _load_json(args.audit_json), args.archive_stamp)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
