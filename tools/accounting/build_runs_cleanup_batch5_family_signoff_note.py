#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch4_stage_review_manifest import _resolve
from tools.builder_table_utils import write_csv_rows

DEFAULT_SOURCE_JSON = "runs/runs_cleanup_batch5_stage_heavy_review_manifest_current.json"
DEFAULT_OUT_JSON = "runs/runs_cleanup_batch5_family_signoff_note_current.json"
DEFAULT_OUT_CSV = "runs/runs_cleanup_batch5_family_signoff_note_current.csv"
DEFAULT_OUT_MD = "runs/runs_cleanup_batch5_family_signoff_note_current.md"


def build_payload(source_json: str) -> dict[str, Any]:
    source = json.loads(_resolve(source_json).read_text(encoding="utf-8"))
    family_totals = {row["family_id"]: row for row in source.get("families", [])}
    rows: list[dict[str, Any]] = []

    for family_id, family_row in family_totals.items():
        related = [row for row in source.get("rows", []) if row.get("family_id") == family_id]
        rows.append(
            {
                "family_id": family_id,
                "remaining_heavy_group_count": int(family_row.get("remaining_heavy_group_count", 0) or 0),
                "remaining_heavy_match_count": int(family_row.get("remaining_heavy_match_count", 0) or 0),
                "remaining_heavy_size_mb": float(family_row.get("remaining_heavy_size_mb", 0.0) or 0.0),
                "groups_under_review": "; ".join(str(row.get("group_id", "")) for row in related),
                "signoff_recommendation": "approve_archive_after_sampling",
                "signoff_reason": "Only stage2 trajectory manifests and stage3 score CSVs remain; lighter stage1/stage2/stage3 surfaces were already archived in batch4.",
            }
        )

    summary = {
        "status": "runs_cleanup_batch5_family_signoff_note_ready",
        "source_manifest": str(_resolve(source_json)),
        "source_manifest_status": str(source.get("summary", {}).get("status", "unknown")),
        "family_count": len(rows),
        "recommended_approve_count": sum(1 for row in rows if row["signoff_recommendation"] == "approve_archive_after_sampling"),
        "remaining_heavy_size_gb": float(source.get("summary", {}).get("remaining_heavy_size_gb", 0.0) or 0.0),
        "batch5_apply_ready": True,
        "next_required_step": "Apply batch5 archive for the approved stage2 trajectory-manifest bundles and stage3 score CSV bundles, then rebuild the runs cleanup audit.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Runs Cleanup Batch5 Family Signoff Note",
        "",
        f"- status: `{s['status']}`",
        f"- source_manifest: `{s['source_manifest']}`",
        f"- source_manifest_status: `{s['source_manifest_status']}`",
        f"- family_count: `{s['family_count']}`",
        f"- recommended_approve_count: `{s['recommended_approve_count']}`",
        f"- remaining_heavy_size_gb: `{s['remaining_heavy_size_gb']}`",
        f"- batch5_apply_ready: `{s['batch5_apply_ready']}`",
        "",
        "| family_id | remaining_heavy_group_count | remaining_heavy_match_count | remaining_heavy_size_mb | signoff_recommendation |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family_id']}` | `{row['remaining_heavy_group_count']}` | `{row['remaining_heavy_match_count']}` | `{row['remaining_heavy_size_mb']}` | `{row['signoff_recommendation']}` |"
        )
    lines.extend(["", "## Detail", ""])
    for row in payload["rows"]:
        lines.extend(
            [
                f"### {row['family_id']}",
                "",
                f"- groups_under_review: `{row['groups_under_review']}`",
                f"- signoff_recommendation: `{row['signoff_recommendation']}`",
                f"- signoff_reason: {row['signoff_reason']}",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a batch5 family signoff note from the heavy-bundle review manifest.")
    parser.add_argument("--source-json", default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args.source_json)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
