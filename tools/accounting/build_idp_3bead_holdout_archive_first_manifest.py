#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch4_stage_review_manifest import _resolve
from tools.builder_table_utils import write_csv_rows

DEFAULT_REVIEW_JSON = "runs/idp_3bead_holdout_cleanup_review_manifest_current.json"
DEFAULT_OUT_JSON = "runs/idp_3bead_holdout_archive_first_manifest_current.json"
DEFAULT_OUT_CSV = "runs/idp_3bead_holdout_archive_first_manifest_current.csv"
DEFAULT_OUT_MD = "runs/idp_3bead_holdout_archive_first_manifest_current.md"


def build_payload(review_json: str) -> dict[str, Any]:
    review = json.loads(_resolve(review_json).read_text(encoding="utf-8"))
    candidate_rows = [
        {
            "prefix": row["prefix"],
            "classification": row["classification"],
            "recommended_disposition": "archive_first",
            "file_count": int(row["file_count"]),
            "size_mb": float(row["size_mb"]),
            "sample_artifacts": row["sample_artifacts"],
            "reason": row["reason"],
        }
        for row in review.get("rows", [])
        if row.get("recommended_disposition") == "review_for_archive_after_prefix_signoff"
    ]
    candidate_rows.sort(key=lambda row: (row["size_mb"], row["file_count"]), reverse=True)
    summary = {
        "status": "idp_3bead_holdout_archive_first_manifest_ready",
        "source_review_status": str(review.get("summary", {}).get("status", "unknown")),
        "archive_candidate_prefix_count": len(candidate_rows),
        "archive_candidate_size_gb": round(sum(row["size_mb"] for row in candidate_rows) / 1024, 2),
        "next_required_step": "Archive these stale IDP historical prefixes as a batch, then compress the archive root to recover actual disk space.",
    }
    return {"summary": summary, "rows": candidate_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP 3-Bead Holdout Archive-First Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- source_review_status: `{s['source_review_status']}`",
        f"- archive_candidate_prefix_count: `{s['archive_candidate_prefix_count']}`",
        f"- archive_candidate_size_gb: `{s['archive_candidate_size_gb']}`",
        "",
        "| prefix | classification | file_count | size_mb | recommended_disposition |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['prefix']}` | `{row['classification']}` | `{row['file_count']}` | `{row['size_mb']}` | `{row['recommended_disposition']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an archive-first manifest for stale idp_3bead_holdout prefixes.")
    parser.add_argument("--review-json", default=DEFAULT_REVIEW_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args.review_json)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
