#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_COMMIT_PACKET_JSON = "runs/glut1_manual_verdict_commit_packet_current.json"
DEFAULT_UPDATE_SHEET_JSON = "runs/glut1_binder_verdict_update_sheet_current.json"
DEFAULT_OUT_JSON = "runs/glut1_binder_confirmation_card_current.json"
DEFAULT_OUT_CSV = "runs/glut1_binder_confirmation_card_current.csv"
DEFAULT_OUT_MD = "runs/glut1_binder_confirmation_card_current.md"


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(
    commit_packet: dict[str, Any],
    update_sheet: dict[str, Any],
) -> dict[str, Any]:
    sheet_by_step = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in update_sheet.get("sheet_rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }
    rows: list[dict[str, Any]] = []
    for row in commit_packet.get("rows", []) or []:
        step = str(row.get("packet_step", "")).strip()
        sheet = sheet_by_step.get(step, {})
        rows.append(
            {
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": step,
                "update_sheet_row_ref": step,
                "candidate_name": str(row.get("candidate_name", "")).strip(),
                "source_anchor": str(row.get("source_anchor", "")).strip(),
                "source_anchor_short": str(row.get("source_anchor", "")).strip(),
                "confirm_fields": str(row.get("confirm_fields", "manual_verdict_update,manual_confidence_update,manual_decision_note")).strip(),
                "staged_manual_verdict": str(row.get("staged_manual_verdict", "")).strip(),
                "staged_manual_confidence_update": str(row.get("staged_manual_confidence_update", "")).strip(),
                "staged_manual_decision_note": str(row.get("staged_manual_decision_note", "")).strip(),
                "commit_value_note_short": str(row.get("staged_manual_decision_note", "")).strip(),
                "manual_verdict_update": str(sheet.get("manual_verdict_update", row.get("manual_verdict_update", ""))).strip(),
                "manual_confidence_update": str(sheet.get("manual_confidence_update", row.get("manual_confidence_update", ""))).strip(),
                "manual_decision_note": str(sheet.get("manual_decision_note", row.get("manual_decision_note", ""))).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "stop_condition": str(row.get("promotion_blocker", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "update_status": str(row.get("update_status", "pending_manual_verdict")).strip(),
            }
        )
    summary = {
        "target_id": "GLUT1",
        "row_count": len(rows),
        "pending_manual_verdict_count": sum(1 for row in rows if not row["manual_verdict_update"]),
        "completed_manual_verdict_count": sum(1 for row in rows if row["manual_verdict_update"]),
        "confirm_field_count": 3,
        "next_required_step": "Use this card to confirm the exact GLUT1 binder values to copy into manual_* fields. Keep all rows non-authoritative and leave GLUT1 behind AQP1 in wave order.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GLUT1 Binder Confirmation Card",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- row_count: `{s['row_count']}`",
        f"- pending_manual_verdict_count: `{s['pending_manual_verdict_count']}`",
        f"- completed_manual_verdict_count: `{s['completed_manual_verdict_count']}`",
        f"- confirm_field_count: `{s['confirm_field_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Binder Rows",
        "",
        "| priority_rank | packet_step | update_sheet_row_ref | candidate_name | source_anchor_short | staged_manual_verdict | staged_manual_confidence_update | confirm_fields | promotion_blocker |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['update_sheet_row_ref']}` | `{row['candidate_name']}` | "
            f"`{row['source_anchor_short']}` | `{row['staged_manual_verdict']}` | `{row['staged_manual_confidence_update']}` | "
            f"`{row['confirm_fields']}` | `{row['promotion_blocker']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a GLUT1-only binder confirmation card from the commit packet and update sheet.")
    parser.add_argument("--commit-packet-json", default=DEFAULT_COMMIT_PACKET_JSON)
    parser.add_argument("--update-sheet-json", default=DEFAULT_UPDATE_SHEET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.commit_packet_json),
        _load_json(args.update_sheet_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
