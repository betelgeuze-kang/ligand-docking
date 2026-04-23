#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REVIEWER_WORKBENCH_JSON = "runs/aqp1_reviewer_workbench_current.json"
DEFAULT_BINDER_VERDICT_UPDATE_SHEET_JSON = "runs/aqp1_binder_verdict_update_sheet_current.json"
DEFAULT_BINDER_REVIEW_BRIEF_JSON = "runs/aqp1_binder_review_brief_current.json"
DEFAULT_NOTE_TEMPLATES_JSON = "runs/transporter_manual_decision_note_templates_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_manual_verdict_draft_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_manual_verdict_draft_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_manual_verdict_draft_packet_current.md"


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


def _index_by(rows: list[dict[str, Any]], key: str, predicate: Any = None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if predicate and not predicate(row):
            continue
        value = str(row.get(key, "")).strip()
        if value:
            out[value] = row
    return out


def build_payload(
    reviewer_workbench_payload: dict[str, Any],
    binder_verdict_sheet_payload: dict[str, Any],
    binder_review_brief_payload: dict[str, Any],
    note_templates_payload: dict[str, Any],
) -> dict[str, Any]:
    workbench_by_step = _index_by(
        reviewer_workbench_payload.get("rows", []) or [],
        "packet_step",
        lambda row: str(row.get("workbench_section", "")).strip() == "binder_first_wave",
    )
    sheet_by_step = _index_by(binder_verdict_sheet_payload.get("sheet_rows", []) or [], "packet_step")
    brief_by_step = _index_by(binder_review_brief_payload.get("rows", []) or [], "packet_step")
    note_by_step = _index_by(
        note_templates_payload.get("rows", []) or [],
        "packet_step",
        lambda row: str(row.get("target_id", "")).strip() == "AQP1",
    )

    rows: list[dict[str, Any]] = []
    for packet_step, workbench_row in workbench_by_step.items():
        sheet_row = sheet_by_step.get(packet_step, {})
        brief_row = brief_by_step.get(packet_step, {})
        note_row = note_by_step.get(packet_step, {})
        rows.append(
            {
                "priority_rank": str(workbench_row.get("priority_rank", sheet_row.get("priority_rank", ""))).strip(),
                "packet_step": packet_step,
                "candidate_name": str(workbench_row.get("label", sheet_row.get("candidate_name", ""))).strip(),
                "source_anchor": str(workbench_row.get("anchor", sheet_row.get("source_anchor", ""))).strip(),
                "source_url": str(sheet_row.get("source_url", "")).strip(),
                "current_focus": str(workbench_row.get("current_focus", brief_row.get("review_focus", ""))).strip(),
                "reviewer_confirm_fields": str(brief_row.get("confirm_fields", "manual_verdict_update, manual_confidence_update, manual_decision_note")).strip(),
                "suggested_manual_verdict": str(sheet_row.get("suggested_manual_verdict", workbench_row.get("draft_manual_verdict_update", ""))).strip(),
                "suggested_manual_confidence_update": str(sheet_row.get("suggested_manual_confidence_update", workbench_row.get("draft_manual_confidence_update", ""))).strip(),
                "suggested_manual_decision_note": str(sheet_row.get("suggested_manual_decision_note", "")).strip(),
                "manual_decision_note_template": str(note_row.get("manual_decision_note_template", "")).strip(),
                "promotion_blocker": str(sheet_row.get("promotion_blocker", workbench_row.get("blocker_or_constraint", ""))).strip(),
                "next_required_action": str(sheet_row.get("next_required_action", workbench_row.get("next_action", ""))).strip(),
                "caution": str(sheet_row.get("caution", brief_row.get("caution", ""))).strip(),
                "manual_verdict_update": "",
                "manual_confidence_update": "",
                "manual_decision_note": "",
                "manual_fields_committed": "no",
                "draft_packet_status": "ready_for_reviewer_copy",
            }
        )

    summary = {
        "target_id": "AQP1",
        "row_count": len(rows),
        "suggested_prefill_count": sum(1 for row in rows if row["suggested_manual_verdict"]),
        "note_template_count": sum(1 for row in rows if row["manual_decision_note_template"]),
        "manual_fields_committed_count": sum(1 for row in rows if row["manual_fields_committed"] == "yes"),
        "ready_for_reviewer_copy_count": sum(1 for row in rows if row["draft_packet_status"] == "ready_for_reviewer_copy"),
        "authoritative_apply_allowed": False,
        "next_required_step": "Copy from suggested_* into manual_* only after explicit reviewer confirmation. Keep this packet draft-only and do not promote AQP1 binder rows to authoritative apply.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Manual Verdict Draft Packet",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- row_count: `{s['row_count']}`",
        f"- suggested_prefill_count: `{s['suggested_prefill_count']}`",
        f"- note_template_count: `{s['note_template_count']}`",
        f"- manual_fields_committed_count: `{s['manual_fields_committed_count']}`",
        f"- ready_for_reviewer_copy_count: `{s['ready_for_reviewer_copy_count']}`",
        f"- authoritative_apply_allowed: `{s['authoritative_apply_allowed']}`",
        "",
        "## Draft Rows",
        "",
        "| priority_rank | packet_step | candidate_name | suggested_manual_verdict | suggested_manual_confidence_update | draft_packet_status |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['suggested_manual_verdict']}` | `{row['suggested_manual_confidence_update']}` | `{row['draft_packet_status']}` |"
        )
        lines.extend(
            [
                "",
                f"- Focus: {row['current_focus']}",
                f"- Note template: {row['manual_decision_note_template']}",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 manual verdict draft packet that sits between the reviewer workbench and binder verdict update sheet.")
    parser.add_argument("--reviewer-workbench-json", default=DEFAULT_REVIEWER_WORKBENCH_JSON)
    parser.add_argument("--binder-verdict-update-sheet-json", default=DEFAULT_BINDER_VERDICT_UPDATE_SHEET_JSON)
    parser.add_argument("--binder-review-brief-json", default=DEFAULT_BINDER_REVIEW_BRIEF_JSON)
    parser.add_argument("--note-templates-json", default=DEFAULT_NOTE_TEMPLATES_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.reviewer_workbench_json),
        _load_json(args.binder_verdict_update_sheet_json),
        _load_json(args.binder_review_brief_json),
        _load_json(args.note_templates_json),
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
