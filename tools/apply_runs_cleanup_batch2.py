#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import tarfile
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_JSON = "runs/runs_cleanup_batch2_manifest_current.json"
DEFAULT_OUT_JSON = "runs/runs_cleanup_batch2_apply_report_current.json"
DEFAULT_OUT_CSV = "runs/runs_cleanup_batch2_apply_report_current.csv"
DEFAULT_OUT_MD = "runs/runs_cleanup_batch2_apply_report_current.md"


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


def _size_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return 0


def apply_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    summary = dict(manifest.get("summary", {}) or {})
    root = Path(summary["runs_dir"])
    archive_root = Path(summary["archive_root"])
    compressed_archive_output = Path(summary["compressed_archive_output"])
    archive_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    moved_file_count = 0
    moved_bytes = 0
    reclaimed_bytes = 0

    for row in manifest.get("rows", []) or []:
        action = str(row.get("action", ""))
        pattern = str(row.get("match_pattern", ""))
        apply_now = bool(row.get("apply_now"))
        if not apply_now:
            rows.append(
                {
                    "action": action,
                    "match_pattern": pattern,
                    "matched_count": 0,
                    "moved_or_compressed_count": 0,
                    "size_mb": 0.0,
                    "status": "skipped",
                }
            )
            continue

        if action == "archive_compress":
            source_dir = root / pattern
            original_size = _size_bytes(source_dir)
            if compressed_archive_output.exists():
                compressed_archive_output.unlink()
            with tarfile.open(compressed_archive_output, "w:gz") as tar:
                tar.add(source_dir, arcname=source_dir.name)
            compressed_size = compressed_archive_output.stat().st_size
            shutil.rmtree(source_dir)
            reclaimed_bytes += max(0, original_size - compressed_size)
            rows.append(
                {
                    "action": action,
                    "match_pattern": pattern,
                    "matched_count": 1,
                    "moved_or_compressed_count": 1,
                    "size_mb": round(original_size / (1024 * 1024), 2),
                    "status": "compressed_and_removed",
                }
            )
            continue

        matches = [path for path in root.glob(pattern) if path.exists()]
        if not matches:
            rows.append(
                {
                    "action": action,
                    "match_pattern": pattern,
                    "matched_count": 0,
                    "moved_or_compressed_count": 0,
                    "size_mb": 0.0,
                    "status": "no_matches",
                }
            )
            continue

        dest_dir = archive_root / pattern.replace("*", "_glob")
        dest_dir.mkdir(parents=True, exist_ok=True)
        batch_bytes = 0
        batch_count = 0
        for path in matches:
            if not path.is_file():
                continue
            size = path.stat().st_size
            shutil.move(str(path), str(dest_dir / path.name))
            batch_bytes += size
            batch_count += 1
        moved_file_count += batch_count
        moved_bytes += batch_bytes
        reclaimed_bytes += batch_bytes
        rows.append(
            {
                "action": action,
                "match_pattern": pattern,
                "matched_count": len(matches),
                "moved_or_compressed_count": batch_count,
                "size_mb": round(batch_bytes / (1024 * 1024), 2),
                "status": "archived",
            }
        )

    out_summary = {
        "status": "runs_cleanup_batch2_apply_report_ready",
        "archive_root": str(archive_root),
        "compressed_archive_output": str(compressed_archive_output),
        "moved_file_count": moved_file_count,
        "moved_size_gb": round(moved_bytes / (1024 * 1024 * 1024), 2),
        "reclaimed_size_gb": round(reclaimed_bytes / (1024 * 1024 * 1024), 2),
        "next_required_step": "Rebuild the cleanup audit and confirm the reduced active footprint under runs/.",
    }
    return {"summary": out_summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Runs Cleanup Batch2 Apply Report",
        "",
        f"- status: `{s['status']}`",
        f"- archive_root: `{s['archive_root']}`",
        f"- compressed_archive_output: `{s['compressed_archive_output']}`",
        f"- moved_file_count: `{s['moved_file_count']}`",
        f"- moved_size_gb: `{s['moved_size_gb']}`",
        f"- reclaimed_size_gb: `{s['reclaimed_size_gb']}`",
        "",
        "| action | match_pattern | matched_count | moved_or_compressed_count | size_mb | status |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['action']}` | `{row['match_pattern']}` | `{row['matched_count']}` | `{row['moved_or_compressed_count']}` | `{row['size_mb']}` | `{row['status']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply the safe batch2 cleanup manifest.")
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
