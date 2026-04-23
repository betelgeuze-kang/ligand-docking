#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch4_stage_review_manifest import _resolve
from tools.builder_table_utils import write_csv_rows

DEFAULT_MANIFEST_JSON = "runs/runs_archive_cleanup_review_manifest_current.json"
DEFAULT_OUT_JSON = "runs/runs_archive_cleanup_apply_report_current.json"
DEFAULT_OUT_CSV = "runs/runs_archive_cleanup_apply_report_current.csv"
DEFAULT_OUT_MD = "runs/runs_archive_cleanup_apply_report_current.md"


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _size_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def apply_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    archive_root = _resolve("runs/archive")
    rows: list[dict[str, Any]] = []
    applied_row_count = 0
    skipped_row_count = 0
    moved_bytes = 0

    for manifest_row in manifest.get("rows", []) or []:
        item_name = str(manifest_row.get("archive_item", "")).strip()
        source = archive_root / item_name
        out_row = {
            "archive_item": item_name,
            "recommended_disposition": str(manifest_row.get("recommended_disposition", "")),
            "pre_size_mb": float(manifest_row.get("size_mb", 0.0) or 0.0),
            "post_size_mb": 0.0,
            "status": "",
        }
        if out_row["recommended_disposition"] != "apply_now":
            out_row["status"] = "skipped_non_apply_now"
            rows.append(out_row)
            skipped_row_count += 1
            continue
        if not source.exists() or not source.is_dir():
            out_row["status"] = "missing_or_not_dir"
            rows.append(out_row)
            skipped_row_count += 1
            continue

        tarball = archive_root / f"{item_name}.tar.gz"
        if tarball.exists():
            out_row["status"] = "tarball_already_exists_skipped"
            out_row["post_size_mb"] = round(_size_bytes(tarball) / (1024 * 1024), 2)
            rows.append(out_row)
            skipped_row_count += 1
            continue

        pre_bytes = _size_bytes(source)
        with tarfile.open(tarball, "w:gz") as tf:
            tf.add(source, arcname=source.name)
        for child in sorted(source.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        source.rmdir()
        post_bytes = _size_bytes(tarball)
        moved_bytes += max(pre_bytes - post_bytes, 0)
        applied_row_count += 1
        out_row["post_size_mb"] = round(post_bytes / (1024 * 1024), 2)
        out_row["status"] = "compressed_and_removed_dir"
        rows.append(out_row)

    summary = {
        "status": "runs_archive_cleanup_apply_report_ready",
        "archive_root": str(archive_root),
        "manifest_row_count": len(manifest.get("rows", []) or []),
        "applied_row_count": applied_row_count,
        "skipped_row_count": skipped_row_count,
        "estimated_size_reduction_mb": round(moved_bytes / (1024 * 1024), 2),
        "next_required_step": "Keep compact tarballs locally for now, and move the largest cold tarballs off-machine only when an external storage destination is ready.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Runs Archive Cleanup Apply Report",
        "",
        f"- status: `{s['status']}`",
        f"- archive_root: `{s['archive_root']}`",
        f"- manifest_row_count: `{s['manifest_row_count']}`",
        f"- applied_row_count: `{s['applied_row_count']}`",
        f"- skipped_row_count: `{s['skipped_row_count']}`",
        f"- estimated_size_reduction_mb: `{s['estimated_size_reduction_mb']}`",
        "",
        "| archive_item | recommended_disposition | pre_size_mb | post_size_mb | status |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['archive_item']}` | `{row['recommended_disposition']}` | `{row['pre_size_mb']}` | `{row['post_size_mb']}` | `{row['status']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply safe cleanup actions inside runs/archive.")
    parser.add_argument("--manifest-json", default=DEFAULT_MANIFEST_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = apply_manifest(_load_json(args.manifest_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
