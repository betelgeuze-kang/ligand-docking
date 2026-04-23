#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch4_stage_review_manifest import _resolve
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_JSON = "runs/idp_3bead_holdout_archive_first_manifest_current.json"
DEFAULT_ARCHIVE_ROOT = "runs/archive/idp_3bead_holdout_archive_first_current"
DEFAULT_OUT_JSON = "runs/idp_3bead_holdout_archive_first_apply_report_current.json"
DEFAULT_OUT_CSV = "runs/idp_3bead_holdout_archive_first_apply_report_current.csv"
DEFAULT_OUT_MD = "runs/idp_3bead_holdout_archive_first_apply_report_current.md"


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _size_bytes(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def apply_manifest(manifest: dict[str, Any], *, archive_root: str = DEFAULT_ARCHIVE_ROOT) -> dict[str, Any]:
    runs_root = _resolve("runs")
    archive_root_path = _resolve(archive_root)
    archive_root_path.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    moved_file_count = 0
    moved_bytes = 0
    applied_row_count = 0
    skipped_row_count = 0
    already_archived_row_count = 0

    for manifest_row in manifest.get("rows", []) or []:
        prefix = str(manifest_row.get("prefix", "")).strip()
        planned_archive_dir = archive_root_path / prefix
        matched_files = sorted(path for path in runs_root.glob(prefix + "*") if path.is_file())
        out_row = {
            "prefix": prefix,
            "classification": str(manifest_row.get("classification", "")),
            "expected_file_count": int(manifest_row.get("file_count", 0) or 0),
            "matched_file_count": len(matched_files),
            "moved_file_count": 0,
            "source_size_mb": float(manifest_row.get("size_mb", 0.0) or 0.0),
            "moved_size_mb": 0.0,
            "archive_subdir": _display_path(planned_archive_dir),
            "status": "",
        }

        if not matched_files:
            archived_files = sorted(path for path in planned_archive_dir.glob("*") if path.is_file()) if planned_archive_dir.exists() else []
            if archived_files and len(archived_files) == out_row["expected_file_count"]:
                out_row["status"] = "already_archived"
                out_row["already_archived_file_count"] = len(archived_files)
                rows.append(out_row)
                skipped_row_count += 1
                already_archived_row_count += 1
                continue
            out_row["status"] = "no_matches"
            rows.append(out_row)
            skipped_row_count += 1
            continue

        if out_row["expected_file_count"] and out_row["expected_file_count"] != len(matched_files):
            out_row["status"] = "count_mismatch_skipped"
            rows.append(out_row)
            skipped_row_count += 1
            continue

        conflicts = [path.name for path in matched_files if (planned_archive_dir / path.name).exists()]
        if conflicts:
            out_row["status"] = "destination_conflict_skipped"
            out_row["destination_conflict_count"] = len(conflicts)
            rows.append(out_row)
            skipped_row_count += 1
            continue

        planned_archive_dir.mkdir(parents=True, exist_ok=True)
        batch_bytes = 0
        for path in matched_files:
            batch_bytes += _size_bytes(path)
            shutil.move(str(path), str(planned_archive_dir / path.name))
        moved_file_count += len(matched_files)
        moved_bytes += batch_bytes
        applied_row_count += 1
        out_row["moved_file_count"] = len(matched_files)
        out_row["moved_size_mb"] = round(batch_bytes / (1024 * 1024), 2)
        out_row["status"] = "archived"
        rows.append(out_row)

    summary = {
        "status": "idp_3bead_holdout_archive_first_apply_report_ready",
        "archive_root": str(archive_root_path),
        "manifest_row_count": len(manifest.get("rows", []) or []),
        "applied_row_count": applied_row_count,
        "already_archived_row_count": already_archived_row_count,
        "skipped_row_count": skipped_row_count,
        "moved_file_count": moved_file_count,
        "moved_size_gb": round(moved_bytes / (1024 * 1024 * 1024), 2),
        "next_required_step": "Compress the archive root for actual disk recovery, then rebuild the runs cleanup audit and re-check which IDP prefixes still need a thinner baseline reference pack.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP 3-Bead Holdout Archive-First Apply Report",
        "",
        f"- status: `{s['status']}`",
        f"- archive_root: `{s['archive_root']}`",
        f"- manifest_row_count: `{s['manifest_row_count']}`",
        f"- applied_row_count: `{s['applied_row_count']}`",
        f"- already_archived_row_count: `{s['already_archived_row_count']}`",
        f"- skipped_row_count: `{s['skipped_row_count']}`",
        f"- moved_file_count: `{s['moved_file_count']}`",
        f"- moved_size_gb: `{s['moved_size_gb']}`",
        "",
        "| prefix | classification | expected_file_count | matched_file_count | moved_file_count | moved_size_mb | status |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['prefix']}` | `{row['classification']}` | `{row['expected_file_count']}` | `{row['matched_file_count']}` | `{row['moved_file_count']}` | `{row['moved_size_mb']}` | `{row['status']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive-first apply for stale idp_3bead_holdout prefixes.")
    parser.add_argument("--manifest-json", default=DEFAULT_MANIFEST_JSON)
    parser.add_argument("--archive-root", default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = apply_manifest(_load_json(args.manifest_json), archive_root=args.archive_root)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
