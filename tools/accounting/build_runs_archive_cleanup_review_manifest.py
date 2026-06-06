#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch4_stage_review_manifest import _resolve
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE_DIR = "runs/archive"
DEFAULT_OUT_JSON = "runs/runs_archive_cleanup_review_manifest_current.json"
DEFAULT_OUT_CSV = "runs/runs_archive_cleanup_review_manifest_current.csv"
DEFAULT_OUT_MD = "runs/runs_archive_cleanup_review_manifest_current.md"


def _size_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def _classify_archive(path: Path) -> tuple[str, str, str]:
    name = path.name
    if path.is_dir():
        return (
            "compress_then_remove_dir",
            "apply_now",
            "Live archive directory should be converted to a tar.gz so the archive root itself stays compact.",
        )
    if name.startswith("archive_2026-03-29_external"):
        return (
            "external_cold_archive",
            "offload_candidate",
            "Already cold storage; biggest remaining space win will come from moving this tarball off-machine, not expanding or rewriting it.",
        )
    if name.endswith(".tar.gz"):
        return (
            "local_compact_archive",
            "keep_local_compact",
            "Already compact and referenced only for audit/provenance; keep unless external offload is available.",
        )
    return (
        "manual_review",
        "review_only",
        "Unclassified archive item; keep until manually reviewed.",
    )


def build_payload(archive_dir: str = DEFAULT_ARCHIVE_DIR) -> dict[str, Any]:
    archive_root = _resolve(archive_dir)
    rows: list[dict[str, Any]] = []
    for path in sorted(archive_root.iterdir()):
        classification, recommended_disposition, reason = _classify_archive(path)
        rows.append(
            {
                "archive_item": path.name,
                "item_type": "dir" if path.is_dir() else "file",
                "size_mb": round(_size_bytes(path) / (1024 * 1024), 2),
                "classification": classification,
                "recommended_disposition": recommended_disposition,
                "reason": reason,
            }
        )

    summary = {
        "status": "runs_archive_cleanup_review_manifest_ready",
        "archive_item_count": len(rows),
        "apply_now_count": sum(1 for row in rows if row["recommended_disposition"] == "apply_now"),
        "offload_candidate_count": sum(1 for row in rows if row["recommended_disposition"] == "offload_candidate"),
        "keep_local_compact_count": sum(1 for row in rows if row["recommended_disposition"] == "keep_local_compact"),
        "total_archive_size_gb": round(sum(row["size_mb"] for row in rows) / 1024, 2),
        "next_required_step": "Compress any remaining live archive directories now, then treat large tarballs as offload candidates rather than deleting them blindly.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Runs Archive Cleanup Review Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- archive_item_count: `{s['archive_item_count']}`",
        f"- apply_now_count: `{s['apply_now_count']}`",
        f"- offload_candidate_count: `{s['offload_candidate_count']}`",
        f"- keep_local_compact_count: `{s['keep_local_compact_count']}`",
        f"- total_archive_size_gb: `{s['total_archive_size_gb']}`",
        "",
        "| archive_item | item_type | size_mb | classification | recommended_disposition |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['archive_item']}` | `{row['item_type']}` | `{row['size_mb']}` | `{row['classification']}` | `{row['recommended_disposition']}` |"
        )
    lines.extend(["", "## Detail", ""])
    for row in payload["rows"]:
        lines.extend(
            [
                f"### {row['archive_item']}",
                "",
                f"- item_type: `{row['item_type']}`",
                f"- size_mb: `{row['size_mb']}`",
                f"- classification: `{row['classification']}`",
                f"- recommended_disposition: `{row['recommended_disposition']}`",
                f"- reason: {row['reason']}",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a cleanup review manifest for runs/archive.")
    parser.add_argument("--archive-dir", default=DEFAULT_ARCHIVE_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args.archive_dir)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
