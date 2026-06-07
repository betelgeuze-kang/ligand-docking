#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch4_stage_review_manifest import _resolve
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_DIR = "runs"
DEFAULT_OUT_JSON = "runs/runs_cold_storage_offload_review_manifest_current.json"
DEFAULT_OUT_CSV = "runs/runs_cold_storage_offload_review_manifest_current.csv"
DEFAULT_OUT_MD = "runs/runs_cold_storage_offload_review_manifest_current.md"


def _file_size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def build_payload(runs_dir: str) -> dict[str, Any]:
    runs_root = _resolve(runs_dir)
    display_root = runs_root.parent
    rows: list[dict[str, Any]] = []

    for path in sorted(runs_root.glob("archive*.tar.gz")):
        rows.append(
            {
                "path": str(path.relative_to(display_root)),
                "classification": "large_top_level_archive",
                "size_mb": round(_file_size(path) / (1024 * 1024), 2),
                "recommended_disposition": "external_offload_candidate" if _file_size(path) >= 500 * 1024 * 1024 else "keep_local_compact",
                "reason": "Compressed historical validation archive; move off-machine for real disk recovery if you still need provenance.",
            }
        )

    archive_dir = runs_root / "archive"
    for path in sorted(archive_dir.glob("*.tar.gz")):
        rows.append(
            {
                "path": str(path.relative_to(display_root)),
                "classification": "local_compact_archive",
                "size_mb": round(_file_size(path) / (1024 * 1024), 2),
                "recommended_disposition": "keep_local_compact",
                "reason": "Already compressed and relatively small; keep local unless you want a dedicated cold-storage export sweep.",
            }
        )

    summary = {
        "status": "runs_cold_storage_offload_review_manifest_ready",
        "runs_dir": str(runs_root),
        "archive_item_count": len(rows),
        "external_offload_candidate_count": len([row for row in rows if row["recommended_disposition"] == "external_offload_candidate"]),
        "external_offload_candidate_size_gb": round(sum(row["size_mb"] for row in rows if row["recommended_disposition"] == "external_offload_candidate") / 1024, 2),
        "next_required_step": "If you want more real disk recovery, move the large external-validation tarball to external storage before touching the smaller local compact archives.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Runs Cold-Storage Offload Review Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- runs_dir: `{s['runs_dir']}`",
        f"- archive_item_count: `{s['archive_item_count']}`",
        f"- external_offload_candidate_count: `{s['external_offload_candidate_count']}`",
        f"- external_offload_candidate_size_gb: `{s['external_offload_candidate_size_gb']}`",
        "",
        "| path | classification | size_mb | recommended_disposition |",
        "| --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['path']}` | `{row['classification']}` | `{row['size_mb']}` | `{row['recommended_disposition']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a review manifest for cold-storage offload candidates under runs/.")
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
