#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch4_archive_first_manifest import FAMILY_SPECS, _matches
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_JSON = "runs/runs_cleanup_batch4_archive_first_manifest_current.json"
DEFAULT_ARCHIVE_ROOT = "runs/archive/runs_cleanup_batch4_archive_first_current"
DEFAULT_OUT_JSON = "runs/runs_cleanup_batch4_archive_first_apply_report_current.json"
DEFAULT_OUT_CSV = "runs/runs_cleanup_batch4_archive_first_apply_report_current.csv"
DEFAULT_OUT_MD = "runs/runs_cleanup_batch4_archive_first_apply_report_current.md"
ARCHIVE_FIRST = "archive_first"
VALID_GROUP_IDS = {"stage1_all", "stage2_light_bundle", "stage3_summary_only"}

FAMILY_BY_ID = {str(family["family_id"]): family for family in FAMILY_SPECS}


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


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _size_bytes(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _planned_archive_dir(archive_root: Path, family_id: str, group_id: str) -> Path:
    return archive_root / family_id / group_id


def _collect_matches_by_family(root: Path) -> dict[str, dict[str, list[Path]]]:
    matched_by_family: dict[str, dict[str, list[Path]]] = {}
    for family in FAMILY_SPECS:
        files = sorted(path for path in root.glob(str(family["family_glob"])) if path.is_file())
        matched_by_group: dict[str, list[Path]] = {}
        for group_id in sorted(VALID_GROUP_IDS):
            matched = [path for path in files if _matches(path.name, group_id)]
            if matched:
                matched_by_group[group_id] = matched
        matched_by_family[str(family["family_id"])] = matched_by_group
    return matched_by_family


def apply_manifest(manifest: dict[str, Any], archive_root: str = DEFAULT_ARCHIVE_ROOT) -> dict[str, Any]:
    summary = dict(manifest.get("summary", {}) or {})
    root = _resolve(str(summary.get("runs_dir", "runs")))
    archive_root_path = _resolve(archive_root)
    archive_root_path.mkdir(parents=True, exist_ok=True)
    matches_by_family = _collect_matches_by_family(root)

    rows: list[dict[str, Any]] = []
    manifest_rows = list(manifest.get("rows", []) or [])
    moved_file_count = 0
    moved_bytes = 0
    applied_row_count = 0
    skipped_row_count = 0
    eligible_archive_first_row_count = 0
    already_archived_row_count = 0
    already_archived_file_count = 0

    for manifest_row in manifest_rows:
        family_id = str(manifest_row.get("family_id", "")).strip()
        group_id = str(manifest_row.get("group_id", "")).strip()
        recommended_disposition = str(manifest_row.get("recommended_disposition", "")).strip()
        planned_archive_dir = _planned_archive_dir(archive_root_path, family_id, group_id)
        out_row = {
            "family_id": family_id,
            "group_id": group_id,
            "stage_id": str(manifest_row.get("stage_id", "")).strip(),
            "recommended_disposition": recommended_disposition,
            "expected_match_count": _as_int(manifest_row.get("match_count")),
            "matched_file_count": 0,
            "moved_file_count": 0,
            "source_size_mb": float(manifest_row.get("size_mb", 0.0) or 0.0),
            "moved_size_mb": 0.0,
            "archive_subdir": _display_path(planned_archive_dir),
            "status": "",
        }

        if recommended_disposition != ARCHIVE_FIRST:
            out_row["archive_subdir"] = ""
            out_row["status"] = "skipped_non_archive_first"
            rows.append(out_row)
            skipped_row_count += 1
            continue

        eligible_archive_first_row_count += 1
        family = FAMILY_BY_ID.get(family_id)
        if family is None or group_id not in VALID_GROUP_IDS:
            out_row["status"] = "unknown_manifest_row_skipped"
            rows.append(out_row)
            skipped_row_count += 1
            continue

        matched_files = list(matches_by_family.get(family_id, {}).get(group_id, []))
        out_row["matched_file_count"] = len(matched_files)
        out_row["moved_size_mb"] = round(sum(_size_bytes(path) for path in matched_files) / (1024 * 1024), 2)

        if not matched_files:
            archived_files = sorted(path for path in planned_archive_dir.glob("*") if path.is_file()) if planned_archive_dir.exists() else []
            if archived_files and (
                not out_row["expected_match_count"] or out_row["expected_match_count"] == len(archived_files)
            ):
                out_row["already_archived_file_count"] = len(archived_files)
                out_row["status"] = "already_archived"
                rows.append(out_row)
                skipped_row_count += 1
                already_archived_row_count += 1
                already_archived_file_count += len(archived_files)
                continue
            out_row["status"] = "no_matches"
            rows.append(out_row)
            skipped_row_count += 1
            continue

        if out_row["expected_match_count"] and out_row["expected_match_count"] != len(matched_files):
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

    out_summary = {
        "status": "runs_cleanup_batch4_archive_first_apply_report_ready",
        "runs_dir": str(root),
        "archive_root": str(archive_root_path),
        "manifest_row_count": len(manifest_rows),
        "eligible_archive_first_row_count": eligible_archive_first_row_count,
        "applied_row_count": applied_row_count,
        "already_archived_row_count": already_archived_row_count,
        "already_archived_file_count": already_archived_file_count,
        "skipped_row_count": skipped_row_count,
        "moved_file_count": moved_file_count,
        "moved_size_gb": round(moved_bytes / (1024 * 1024 * 1024), 2),
        "next_required_step": "Regenerate the batch4 archive-first manifest or the stage review manifest if you want to confirm the active runs root only retains the heavier stage2/stage3 tables and score CSVs.",
    }
    return {"summary": out_summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Runs Cleanup Batch4 Archive-First Apply Report",
        "",
        f"- status: `{summary['status']}`",
        f"- runs_dir: `{summary['runs_dir']}`",
        f"- archive_root: `{summary['archive_root']}`",
        f"- manifest_row_count: `{summary['manifest_row_count']}`",
        f"- eligible_archive_first_row_count: `{summary['eligible_archive_first_row_count']}`",
        f"- applied_row_count: `{summary['applied_row_count']}`",
        f"- already_archived_row_count: `{summary['already_archived_row_count']}`",
        f"- already_archived_file_count: `{summary['already_archived_file_count']}`",
        f"- skipped_row_count: `{summary['skipped_row_count']}`",
        f"- moved_file_count: `{summary['moved_file_count']}`",
        f"- moved_size_gb: `{summary['moved_size_gb']}`",
        "",
        "| family_id | group_id | stage_id | expected_match_count | matched_file_count | moved_file_count | moved_size_mb | archive_subdir | status |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family_id']}` | `{row['group_id']}` | `{row['stage_id']}` | `{row['expected_match_count']}` | `{row['matched_file_count']}` | `{row['moved_file_count']}` | `{row['moved_size_mb']}` | `{row['archive_subdir']}` | `{row['status']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply batch4 archive-first rows into a dedicated archive root.")
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
