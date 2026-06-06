#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUEUE_JSON = "runs/wetlab_wave1_packet_queue_current.json"
DEFAULT_SCHEMA_JSON = "runs/wetlab_one_page_brief_schema_current.json"
DEFAULT_PRIORITY3_FILL_MAP_JSON = "runs/wetlab_priority3_repurposing_fill_map_current.json"
DEFAULT_PRIORITY3_NOVELTY_FILL_MAP_JSON = "runs/wetlab_priority3_novelty_fill_map_current.json"
DEFAULT_NEXT3_FILL_MAP_JSON = "runs/wetlab_next3_repurposing_fill_map_current.json"
DEFAULT_NEXT3_NOVELTY_FILL_MAP_JSON = "runs/wetlab_next3_novelty_fill_map_current.json"
DEFAULT_STK17B_FILL_MAP_JSON = "runs/wetlab_stk17b_repurposing_fill_map_current.json"
DEFAULT_STK17B_NOVELTY_FILL_MAP_JSON = "runs/wetlab_stk17b_novelty_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_wave1_brief_fill_queue_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_wave1_brief_fill_queue_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_wave1_brief_fill_queue_current.md"


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


def _maybe_load_json(path_like: str) -> dict[str, Any] | None:
    path = _resolve(path_like)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(
    queue: dict[str, Any],
    schema: dict[str, Any],
    priority3_fill_map: dict[str, Any] | None = None,
    priority3_novelty_fill_map: dict[str, Any] | None = None,
    next3_fill_map: dict[str, Any] | None = None,
    next3_novelty_fill_map: dict[str, Any] | None = None,
    stk17b_fill_map: dict[str, Any] | None = None,
    stk17b_novelty_fill_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    schema_summary = dict(schema.get("summary", {}) or {})
    fill_counts: dict[str, int] = {}
    novelty_counts: dict[str, int] = {}
    for payload in (priority3_fill_map or {}, next3_fill_map or {}, stk17b_fill_map or {}):
        for row in payload.get("rows", []) or []:
            target_id = str(row.get("target_id", "")).strip()
            if target_id:
                fill_counts[target_id] = fill_counts.get(target_id, 0) + 1
    for payload in (priority3_novelty_fill_map or {}, next3_novelty_fill_map or {}, stk17b_novelty_fill_map or {}):
        for row in payload.get("rows", []) or []:
            target_id = str(row.get("target_id", "")).strip()
            if target_id:
                novelty_counts[target_id] = novelty_counts.get(target_id, 0) + 1
    rows = []
    for row in queue.get("rows", []) or []:
        fill_count = int(fill_counts.get(str(row["target_id"]), 0) or 0)
        novelty_count = int(novelty_counts.get(str(row["target_id"]), 0) or 0)
        rep_slots = int(row["repurposing_slot_count"])
        novelty_slots = int(row["novelty_slot_count"])
        if fill_count and fill_count >= rep_slots and novelty_count and novelty_count >= novelty_slots:
            fill_status = "repurposing_and_novelty_filled_pending_export"
            next_step = "Target-specific compound content is bound; export the matching first-contact packet."
        elif fill_count and fill_count >= rep_slots:
            fill_status = "repurposing_filled_pending_novelty"
            next_step = "Novelty slots and one explicit negative/control lane still need target-specific content."
        elif fill_count:
            fill_status = "partial_repurposing_fill"
            next_step = "Finish repurposing fill, then add novelty and one explicit negative/control lane."
        else:
            fill_status = "pending_target_specific_content"
            next_step = "Insert target-specific headline, objections, top-3 repurposing, top-3 novelty, and negative/control lane content."
        rows.append(
            {
                "target_id": row["target_id"],
                "track_id": row["track_id"],
                "brief_artifact_planned": row["brief_artifact_planned"],
                "summary_field_count": schema_summary.get("summary_field_count", 0),
                "row_field_count": schema_summary.get("row_field_count", 0),
                "repurposing_slot_count": row["repurposing_slot_count"],
                "novelty_slot_count": row["novelty_slot_count"],
                "repurposing_filled_slot_count": fill_count,
                "novelty_filled_slot_count": novelty_count,
                "fill_status": fill_status,
                "next_required_step": next_step,
            }
        )
    summary = {
        "status": "wetlab_wave1_brief_fill_queue_ready",
        "row_count": len(rows),
        "pending_target_specific_content_count": sum(1 for row in rows if row["fill_status"] == "pending_target_specific_content"),
        "repurposing_filled_target_count": sum(1 for row in rows if row["fill_status"] == "repurposing_filled_pending_novelty"),
        "novelty_filled_target_count": sum(1 for row in rows if row["novelty_filled_slot_count"] >= row["novelty_slot_count"]),
        "next_required_step": "Use this queue as the immediate handoff surface for target-specific one-page brief filling, then export any targets whose repurposing and novelty lanes are both already bound.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Wave 1 Brief Fill Queue",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- pending_target_specific_content_count: `{s['pending_target_specific_content_count']}`",
        f"- repurposing_filled_target_count: `{s['repurposing_filled_target_count']}`",
        f"- novelty_filled_target_count: `{s['novelty_filled_target_count']}`",
        "",
        "| target_id | track_id | brief_artifact_planned | repurposing_slots | repurposing_filled | novelty_slots | novelty_filled | fill_status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['track_id']}` | `{row['brief_artifact_planned']}` | `{row['repurposing_slot_count']}` | `{row['repurposing_filled_slot_count']}` | `{row['novelty_slot_count']}` | `{row['novelty_filled_slot_count']}` | `{row['fill_status']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Wave 1 brief fill queue for target-specific content insertion.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--schema-json", default=DEFAULT_SCHEMA_JSON)
    parser.add_argument("--priority3-fill-map-json", default=DEFAULT_PRIORITY3_FILL_MAP_JSON)
    parser.add_argument("--priority3-novelty-fill-map-json", default=DEFAULT_PRIORITY3_NOVELTY_FILL_MAP_JSON)
    parser.add_argument("--next3-fill-map-json", default=DEFAULT_NEXT3_FILL_MAP_JSON)
    parser.add_argument("--next3-novelty-fill-map-json", default=DEFAULT_NEXT3_NOVELTY_FILL_MAP_JSON)
    parser.add_argument("--stk17b-fill-map-json", default=DEFAULT_STK17B_FILL_MAP_JSON)
    parser.add_argument("--stk17b-novelty-fill-map-json", default=DEFAULT_STK17B_NOVELTY_FILL_MAP_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.queue_json),
        _load_json(args.schema_json),
        _maybe_load_json(args.priority3_fill_map_json),
        _maybe_load_json(args.priority3_novelty_fill_map_json),
        _maybe_load_json(args.next3_fill_map_json),
        _maybe_load_json(args.next3_novelty_fill_map_json),
        _maybe_load_json(args.stk17b_fill_map_json),
        _maybe_load_json(args.stk17b_novelty_fill_map_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
