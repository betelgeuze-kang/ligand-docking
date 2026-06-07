#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.product import ca2_packet_bridge as bridge

DEFAULT_WORKBOOK_CSV = "runs/ca2_packet_replacement_workbook_current.csv"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        import csv

        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _next_required_step(
    workbook_rows: list[dict[str, Any]],
    packet_summaries: list[dict[str, Any]],
    *,
    materialization_applied: bool,
) -> str:
    ready_rows = [row for row in workbook_rows if row["row_ready_for_apply"] == "yes"]
    freeze_pending_rows = [row for row in workbook_rows if row["row_freeze_pending"] == "yes"]
    blocked_rows = [row for row in workbook_rows if row["row_ready_for_apply"] != "yes"]
    missing_counter = Counter()
    for row in blocked_rows:
        for field in str(row.get("missing_fields", "")).split(","):
            field = field.strip()
            if field:
                missing_counter[field] += 1
    packet_ready_after_freeze = sum(1 for row in packet_summaries if row["packet_ready_after_freeze"])
    if freeze_pending_rows and blocked_rows:
        return (
            f"Freeze the {len(freeze_pending_rows)} workbook rows that are already fully specified into the CA2 packet CSVs, "
            f"then close the {len(blocked_rows)} remaining blocker rows that still need "
            f"{missing_counter.most_common(1)[0][0] if missing_counter else 'authoritative binding fields'}."
        )
    if freeze_pending_rows:
        return f"Freeze the {len(freeze_pending_rows)} remaining workbook rows into the CA2 packet CSVs to sync config with the reviewed workbook."
    if blocked_rows:
        prefix = "Continue closing the remaining workbook blockers." if materialization_applied or ready_rows else "No CA2 rows are freeze-ready yet."
        if missing_counter:
            return f"{prefix} Most common missing field: {missing_counter.most_common(1)[0][0]}."
        return prefix
    if packet_ready_after_freeze == len(packet_summaries):
        return "Every CA2 workbook row is fully specified and all packet CSV rows are now frozen."
    return "Workbook rows are fully specified, but packet CSV coverage still needs a final consistency pass."


def _packet_ready_now(packet_summary: dict[str, Any]) -> bool:
    return bool(packet_summary["row_count"]) and packet_summary["applied_row_count"] >= packet_summary["row_count"] and packet_summary["blocked_row_count"] == 0


def _packet_ready_after_freeze(packet_summary: dict[str, Any]) -> bool:
    return bool(packet_summary["row_count"]) and packet_summary["projected_complete_ligand_count"] >= packet_summary["row_count"] and packet_summary["blocked_row_count"] == 0


def build_payload(workbook_rows: list[dict[str, str]], *, freeze_ready_rows: bool) -> dict[str, Any]:
    live_packet_tables = bridge.load_packet_tables()
    preview = bridge.materialize_ready_workbook_rows(workbook_rows, packet_tables=live_packet_tables, apply_changes=False)
    applied_summary = {
        "materialized_row_count": 0,
        "slot_action_counts": {},
        "apply_changes": False,
    }
    if freeze_ready_rows:
        applied = bridge.materialize_ready_workbook_rows(workbook_rows, packet_tables=live_packet_tables, apply_changes=True)
        applied_summary = dict(applied.get("summary", {}))
        live_packet_tables = bridge.load_packet_tables()

    current_packet_summaries = bridge.summarize_packet_tables(live_packet_tables)
    projected_packet_summaries = bridge.summarize_packet_tables(preview["packet_tables"])
    classified_rows = [bridge.classify_workbook_row(row, live_packet_tables) for row in workbook_rows]

    missing_counter = Counter()
    packet_summaries: list[dict[str, Any]] = []
    packets = sorted({str(row.get("packet", "")).strip() for row in workbook_rows if str(row.get("packet", "")).strip()})
    for row in classified_rows:
        for field in str(row.get("missing_fields", "")).split(","):
            field = field.strip()
            if field:
                missing_counter[field] += 1

    for packet in packets:
        packet_rows = [row for row in classified_rows if row.get("packet") == packet]
        ready_rows = [row for row in packet_rows if row["row_ready_for_apply"] == "yes"]
        applied_rows = [row for row in packet_rows if row["row_applied_in_config"] == "yes"]
        freeze_pending_rows = [row for row in packet_rows if row["row_freeze_pending"] == "yes"]
        blocked_rows = [row for row in packet_rows if row["row_ready_for_apply"] != "yes"]
        current = current_packet_summaries.get(packet, {})
        projected = projected_packet_summaries.get(packet, {})
        packet_summaries.append(
            {
                "packet": packet,
                "row_count": len(packet_rows),
                "ready_row_count": len(ready_rows),
                "applied_row_count": len(applied_rows),
                "freeze_pending_row_count": len(freeze_pending_rows),
                "blocked_row_count": len(blocked_rows),
                "completion_fraction": round(len(applied_rows) / len(packet_rows), 4) if packet_rows else 0.0,
                "current_complete_ligand_count": int(current.get("complete_ligand_count", 0)),
                "current_placeholder_ligand_count": int(current.get("placeholder_ligand_count", 0)),
                "projected_complete_ligand_count": int(projected.get("complete_ligand_count", 0)),
                "projected_placeholder_ligand_count": int(projected.get("placeholder_ligand_count", 0)),
                "packet_status_now": str(current.get("status", "")),
                "packet_status_after_freeze": str(projected.get("status", "")),
            }
        )
        packet_summaries[-1]["packet_ready_now"] = _packet_ready_now(packet_summaries[-1])
        packet_summaries[-1]["packet_ready_after_freeze"] = _packet_ready_after_freeze(packet_summaries[-1])

    summary = {
        "workbook_row_count": len(classified_rows),
        "ready_row_count": sum(1 for row in classified_rows if row["row_ready_for_apply"] == "yes"),
        "applied_row_count": sum(1 for row in classified_rows if row["row_applied_in_config"] == "yes"),
        "freeze_pending_row_count": sum(1 for row in classified_rows if row["row_freeze_pending"] == "yes"),
        "blocked_row_count": sum(1 for row in classified_rows if row["row_ready_for_apply"] != "yes"),
        "current_packet_ready_count": sum(1 for row in packet_summaries if _packet_ready_now(row)),
        "projected_packet_ready_count": sum(1 for row in packet_summaries if _packet_ready_after_freeze(row)),
        "most_common_missing_field": missing_counter.most_common(1)[0][0] if missing_counter else "",
        "missing_field_counts": dict(missing_counter),
    }
    summary["next_required_step"] = _next_required_step(
        classified_rows,
        packet_summaries,
        materialization_applied=bool(applied_summary.get("apply_changes")),
    )
    return {
        "summary": summary,
        "packet_summaries": packet_summaries,
        "workbook_rows": classified_rows,
        "current_packet_summaries": [current_packet_summaries.get(packet, {}) for packet in packets],
        "projected_packet_summaries": [projected_packet_summaries.get(packet, {}) for packet in packets],
        "materialization_preview": {
            "summary": preview.get("summary", {}),
            "rows": preview.get("materialized_rows", []),
        },
        "materialization_applied": applied_summary,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload["summary"]
    lines = [
        "# CA2 Packet Replacement Readiness",
        "",
        f"- workbook_row_count: `{summary['workbook_row_count']}`",
        f"- ready_row_count: `{summary['ready_row_count']}`",
        f"- applied_row_count: `{summary['applied_row_count']}`",
        f"- freeze_pending_row_count: `{summary['freeze_pending_row_count']}`",
        f"- blocked_row_count: `{summary['blocked_row_count']}`",
        f"- current_packet_ready_count: `{summary['current_packet_ready_count']}`",
        f"- projected_packet_ready_count: `{summary['projected_packet_ready_count']}`",
        f"- most_common_missing_field: `{summary['most_common_missing_field']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Packet Summary",
        "",
        "| packet | ready_row_count | applied_row_count | freeze_pending_row_count | blocked_row_count | current_status | projected_status |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["packet_summaries"]:
        lines.append(
            f"| {row['packet']} | {row['ready_row_count']} | {row['applied_row_count']} | {row['freeze_pending_row_count']} | {row['blocked_row_count']} | {row['packet_status_now']} | {row['packet_status_after_freeze']} |"
        )
    lines.extend([
        "",
        "## Missing Field Counts",
        "",
        "| field | count |",
        "| --- | ---: |",
    ])
    for field, count in sorted(summary["missing_field_counts"].items()):
        lines.append(f"| {field} | {count} |")
    lines.extend([
        "",
        "## Workbook Rows",
        "",
        "| packet_step | replacement_ligand_id | missing_fields | row_ready_for_apply | row_applied_in_config | row_freeze_pending | reference_slot_action | split_slot_action | meta_slot_action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for row in payload["workbook_rows"]:
        lines.append(
            f"| {row['packet_step']} | `{row.get('replacement_ligand_id', '')}` | {row['missing_fields']} | {row['row_ready_for_apply']} | {row['row_applied_in_config']} | {row['row_freeze_pending']} | {row['reference_slot_action']} | {row['split_slot_action']} | {row['meta_slot_action']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CA2 packet replacement readiness from the current CA2 workbook and live packet CSVs.")
    parser.add_argument("--workbook-csv", default=DEFAULT_WORKBOOK_CSV)
    parser.add_argument("--out-json", default="runs/ca2_packet_replacement_readiness_current.json")
    parser.add_argument("--out-csv", default="runs/ca2_packet_replacement_readiness_current.csv")
    parser.add_argument("--out-md", default="runs/ca2_packet_replacement_readiness_current.md")
    parser.add_argument("--freeze-ready-rows", action=argparse.BooleanOptionalAction, default=False)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _, workbook_rows = bridge.read_csv_rows(args.workbook_csv)
    payload = build_payload(workbook_rows, freeze_ready_rows=bool(args.freeze_ready_rows))
    out_json = bridge.resolve_path(args.out_json)
    out_csv = bridge.resolve_path(args.out_csv)
    out_md = bridge.resolve_path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["workbook_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
