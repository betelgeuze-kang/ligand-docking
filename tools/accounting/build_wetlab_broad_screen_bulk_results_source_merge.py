#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, resolve, write_artifact

DEFAULT_SOURCE_MD = "runs/wetlab_broad_screen_bulk_results_source_current.md"
DEFAULT_ROWS_JSON = "runs/wetlab_broad_screen_bulk_result_row_examples_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_bulk_results_source_merge_current.md"


def _read_rows_payload(path_like: str) -> dict[str, Any]:
    path = resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if isinstance(payload, list):
        return {"rows": payload}
    if isinstance(payload, dict):
        return payload
    return {}


def _normalize_row(raw: dict[str, Any]) -> dict[str, Any]:
    row = dict(raw)
    row["target_id"] = str(row.get("target_id", "")).strip()
    row["compound_name"] = str(row.get("compound_name", "")).strip()
    if row.get("bulk_rank", "") not in {"", None}:
        row["bulk_rank"] = int(row["bulk_rank"])
    if row.get("bulk_score", "") not in {"", None}:
        row["bulk_score"] = float(row["bulk_score"])
    return row


def _row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("target_id", "")).strip(),
        str(row.get("compound_name", "")).strip().lower(),
    )


def _is_bootstrap(row: dict[str, Any]) -> bool:
    seed_status = str(row.get("seed_status", "")).strip().lower()
    return seed_status.startswith("bootstrap_")


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("target_id", "")).strip().lower(),
            int(row.get("bulk_rank", 10**9) or 10**9),
            -float(row.get("bulk_score", 0.0) or 0.0),
            str(row.get("compound_name", "")).strip().lower(),
        ),
    )


def build_updated_source_payload(
    source_payload: dict[str, Any] | None,
    incoming_payload: dict[str, Any] | None,
    *,
    source_rows_artifact: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    existing_rows = [_normalize_row(row) for row in ((source_payload or {}).get("rows", []) or [])]
    incoming_rows = [_normalize_row(row) for row in ((incoming_payload or {}).get("rows", []) or [])]

    existing_by_key = {_row_key(row): row for row in existing_rows if _row_key(row)[0] and _row_key(row)[1]}
    incoming_by_key = {_row_key(row): row for row in incoming_rows if _row_key(row)[0] and _row_key(row)[1]}

    overwritten_keys = sorted(existing_by_key.keys() & incoming_by_key.keys())
    for key, row in incoming_by_key.items():
        existing_by_key[key] = row

    merged_rows = _sort_rows(list(existing_by_key.values()))
    bootstrap_row_count = sum(1 for row in merged_rows if _is_bootstrap(row))
    actual_row_count = len(merged_rows) - bootstrap_row_count
    target_count = len({str(row.get("target_id", "")).strip() for row in merged_rows if str(row.get("target_id", "")).strip()})
    actual_target_count = len(
        {
            str(row.get("target_id", "")).strip()
            for row in merged_rows
            if str(row.get("target_id", "")).strip() and not _is_bootstrap(row)
        }
    )

    updated_source_payload = {
        "summary": {
            "status": "wetlab_broad_screen_bulk_results_source_ready",
            "target_count": target_count,
            "row_count": len(merged_rows),
            "bootstrap_mode": "manual_fill_map_seed_plus_actual_rows" if actual_row_count > 0 else "manual_fill_map_seed",
            "bootstrap_row_count": bootstrap_row_count,
            "actual_row_count": actual_row_count,
            "actual_target_count": actual_target_count,
            "last_merge_row_count": len(incoming_rows),
            "next_required_step": "Materialize these source rows into bulk results, rerun the repurposing autofill, then refresh target-level fill maps for covered targets.",
        },
        "structured": {
            "source_artifacts": str((source_payload or {}).get("structured", {}).get("source_artifacts", "")).strip(),
            "last_merge_source_artifact": source_rows_artifact,
            "merge_policy": "replace_by_target_and_compound_name",
        },
        "rows": merged_rows,
    }

    report_payload = {
        "summary": {
            "status": "wetlab_broad_screen_bulk_results_source_merge_ready",
            "incoming_row_count": len(incoming_rows),
            "overwritten_row_count": len(overwritten_keys),
            "merged_row_count": len(merged_rows),
            "actual_row_count_after_merge": actual_row_count,
            "bootstrap_row_count_after_merge": bootstrap_row_count,
            "source_target_count_after_merge": target_count,
            "next_required_step": "Rebuild bulk results and repurposing autofill so merged actual rows can flow into the target-level repurposing packets.",
        },
        "structured": {
            "source_artifact": DEFAULT_SOURCE_MD,
            "incoming_rows_artifact": source_rows_artifact,
            "merge_policy": "replace_by_target_and_compound_name",
        },
        "rows": incoming_rows,
    }
    return updated_source_payload, report_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append or merge actual shard-level bulk result rows into the broad-screen source artifact.")
    parser.add_argument("--source-md", default=DEFAULT_SOURCE_MD)
    parser.add_argument("--rows-json", default=DEFAULT_ROWS_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    source_payload = maybe_load_json(args.source_md.replace(".md", ".json"))
    incoming_payload = _read_rows_payload(args.rows_json)
    updated_source_payload, report_payload = build_updated_source_payload(
        source_payload,
        incoming_payload,
        source_rows_artifact=str(Path(args.rows_json).with_suffix(".md")) if args.rows_json.endswith(".json") else args.rows_json,
    )
    write_artifact(args.source_md, "Wet-Lab Broad Screen Bulk Results Source", updated_source_payload)
    write_artifact(args.out_md, "Wet-Lab Broad Screen Bulk Results Source Merge", report_payload)
