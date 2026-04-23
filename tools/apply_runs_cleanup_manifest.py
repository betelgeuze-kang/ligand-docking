#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_JSON = "runs/runs_cleanup_manifest_current.json"
DEFAULT_OUT_JSON = "runs/runs_cleanup_apply_report_current.json"
DEFAULT_OUT_CSV = "runs/runs_cleanup_apply_report_current.csv"
DEFAULT_OUT_MD = "runs/runs_cleanup_apply_report_current.md"


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


def apply_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    summary = dict(manifest.get("summary", {}) or {})
    root = Path(summary["runs_dir"])
    archive_root = Path(summary["archive_root"])
    archive_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    moved_count = 0
    moved_bytes = 0
    for row in manifest.get("rows", []) or []:
        prefix = str(row.get("prefix", ""))
        if not row.get("archive_now"):
            rows.append(
                {
                    "prefix": prefix,
                    "matched_file_count": 0,
                    "moved_file_count": 0,
                    "size_mb": 0.0,
                    "archive_subdir": str(row.get("archive_subdir", "")),
                    "status": "protected_or_skipped",
                }
            )
            continue
        files = [path for path in root.glob(prefix + "*") if path.is_file()]
        dest_dir = archive_root / prefix
        dest_dir.mkdir(parents=True, exist_ok=True)
        batch_bytes = 0
        for path in files:
            size = path.stat().st_size
            shutil.move(str(path), str(dest_dir / path.name))
            moved_count += 1
            batch_bytes += size
            moved_bytes += size
        rows.append(
            {
                "prefix": prefix,
                "matched_file_count": len(files),
                "moved_file_count": len(files),
                "size_mb": round(batch_bytes / (1024 * 1024), 2),
                "archive_subdir": str(dest_dir.relative_to(ROOT)),
                "status": "archived",
            }
        )
    out_summary = {
        "status": "runs_cleanup_apply_report_ready",
        "archive_root": str(archive_root),
        "moved_file_count": moved_count,
        "moved_size_gb": round(moved_bytes / (1024 * 1024 * 1024), 2),
        "next_required_step": "Rebuild the cleanup audit after the archive move to confirm the new top-level footprint.",
    }
    return {"summary": out_summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Runs Cleanup Apply Report",
        "",
        f"- status: `{s['status']}`",
        f"- archive_root: `{s['archive_root']}`",
        f"- moved_file_count: `{s['moved_file_count']}`",
        f"- moved_size_gb: `{s['moved_size_gb']}`",
        "",
        "| prefix | matched_file_count | moved_file_count | size_mb | archive_subdir | status |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['prefix']}` | `{row['matched_file_count']}` | `{row['moved_file_count']}` | `{row['size_mb']}` | `{row['archive_subdir']}` | `{row['status']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a targeted archive-only cleanup manifest to runs/.")
    parser.add_argument("--manifest-json", default=DEFAULT_MANIFEST_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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
