#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path


RUNS = Path("runs")

CONFIRMATION_CARD_JSON = RUNS / "aqp1_binder_confirmation_card_current.json"
UPDATE_SHEET_JSON = RUNS / "aqp1_binder_verdict_update_sheet_current.json"
COMMIT_PACKET_JSON = RUNS / "aqp1_manual_verdict_commit_packet_current.json"

OUT_JSON = RUNS / "aqp1_manual_verdict_staging_sheet_current.json"
OUT_CSV = RUNS / "aqp1_manual_verdict_staging_sheet_current.csv"
OUT_MD = RUNS / "aqp1_manual_verdict_staging_sheet_current.md"


def load_json(path: Path) -> dict:
    with path.open() as fh:
        return json.load(fh)


def index_rows(rows: list[dict], key: str) -> dict[str, dict]:
    return {str(row[key]): row for row in rows}


def build_rows(card: dict, update_sheet: dict, commit_packet: dict) -> list[dict]:
    update_map = index_rows(update_sheet["sheet_rows"], "packet_step")
    commit_map = index_rows(commit_packet["rows"], "packet_step")

    rows: list[dict] = []
    for row in card["rows"]:
        step = str(row["packet_step"])
        update_row = update_map[step]
        commit_row = commit_map[step]
        rows.append(
            {
                "priority_rank": row["priority_rank"],
                "packet_step": step,
                "candidate_name": row["candidate_name"],
                "source_anchor": row["source_anchor"],
                "review_focus": row["review_focus"],
                "staged_manual_verdict": row["staged_manual_verdict"],
                "staged_manual_confidence_update": row["staged_manual_confidence_update"],
                "staged_manual_decision_note": row["staged_manual_decision_note"],
                "confirm_fields": row["confirm_fields"],
                "promotion_blocker": update_row["promotion_blocker"],
                "next_required_action": update_row["next_required_action"],
                "stop_condition": commit_row["stop_condition"],
                "stop_reason": commit_row["stop_reason"],
                "manual_verdict_update": "",
                "manual_confidence_update": "",
                "manual_decision_note": "",
                "staging_status": "ready_for_manual_fill",
            }
        )
    return rows


def build_summary(card: dict, rows: list[dict]) -> dict:
    return {
        "target_id": "AQP1",
        "row_count": len(rows),
        "pending_manual_verdict_count": card["summary"]["pending_manual_verdict_count"],
        "ready_for_manual_fill_count": len(rows),
        "manual_fields_committed_count": 0,
        "stop_condition_count": len({row["stop_condition"] for row in rows}),
        "next_required_step": "Use this staging sheet immediately before filling manual_* fields. Confirm the staged values and stop rule, then write into the update sheet by reviewer decision only.",
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, summary: dict, rows: list[dict]) -> None:
    lines = [
        "# AQP1 Manual Verdict Staging Sheet",
        "",
        f"- target_id: `{summary['target_id']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- pending_manual_verdict_count: `{summary['pending_manual_verdict_count']}`",
        f"- ready_for_manual_fill_count: `{summary['ready_for_manual_fill_count']}`",
        f"- manual_fields_committed_count: `{summary['manual_fields_committed_count']}`",
        f"- stop_condition_count: `{summary['stop_condition_count']}`",
        "",
        "## Rule",
        "",
        "- Review the staged verdict, confidence, note, and stop rule here first. Keep all `manual_*` fields empty until the reviewer explicitly decides to fill them in the update sheet.",
        "",
        "## Staging Rows",
        "",
        "| step | candidate | staged verdict | staged confidence | blocker | stop condition | status |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| `{packet_step}` | `{candidate_name}` | `{staged_manual_verdict}` | `{staged_manual_confidence_update}` | `{promotion_blocker}` | `{stop_condition}` | `{staging_status}` |".format(
                **row
            )
        )
        lines.append("")
        lines.append(f"- Review focus: {row['review_focus']}")
        lines.append(f"- Staged note: {row['staged_manual_decision_note']}")
        lines.append(f"- Stop reason: {row['stop_reason']}")
    lines.extend(
        [
            "",
            "## Fill Next",
            "",
            "- `manual_verdict_update`",
            "- `manual_confidence_update`",
            "- `manual_decision_note`",
            "",
            "## Source Companions",
            "",
            "- `runs/aqp1_binder_confirmation_card_current.md`",
            "- `runs/aqp1_binder_verdict_update_sheet_current.md`",
            "- `runs/aqp1_manual_verdict_commit_packet_current.md`",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    card = load_json(CONFIRMATION_CARD_JSON)
    update_sheet = load_json(UPDATE_SHEET_JSON)
    commit_packet = load_json(COMMIT_PACKET_JSON)

    rows = build_rows(card, update_sheet, commit_packet)
    summary = build_summary(card, rows)
    payload = {"summary": summary, "rows": rows}

    write_json(OUT_JSON, payload)
    write_csv(OUT_CSV, rows)
    write_md(OUT_MD, summary, rows)


if __name__ == "__main__":
    main()
