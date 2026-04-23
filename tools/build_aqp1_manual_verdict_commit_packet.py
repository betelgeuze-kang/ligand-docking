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
DEFAULT_DRAFT_PACKET_JSON = "runs/aqp1_manual_verdict_draft_packet_current.json"
DEFAULT_NOTE_TEMPLATES_JSON = "runs/transporter_manual_decision_note_templates_current.json"
DEFAULT_BINDER_REVIEW_BRIEF_JSON = "runs/aqp1_binder_review_brief_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_manual_verdict_commit_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_manual_verdict_commit_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_manual_verdict_commit_packet_current.md"


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _existing_by_step(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {
        str(row.get("packet_step", "")).strip(): row
        for row in _read_csv(path)
        if str(row.get("packet_step", "")).strip()
    }


def _prefer_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value).strip()
        if text:
            return text
    return ""


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
    draft_packet_payload: dict[str, Any],
    note_templates_payload: dict[str, Any],
    binder_review_brief_payload: dict[str, Any],
    existing_sheet: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    existing_sheet = existing_sheet or {}
    workbench_by_step = _index_by(
        reviewer_workbench_payload.get("rows", []) or [],
        "packet_step",
        lambda row: str(row.get("workbench_section", "")).strip() == "binder_first_wave",
    )
    sheet_by_step = _index_by(binder_verdict_sheet_payload.get("sheet_rows", []) or [], "packet_step")
    draft_by_step = _index_by(draft_packet_payload.get("rows", []) or [], "packet_step")
    brief_by_step = _index_by(binder_review_brief_payload.get("rows", []) or [], "packet_step")
    note_by_step = _index_by(
        note_templates_payload.get("rows", []) or [],
        "packet_step",
        lambda row: str(row.get("target_id", "")).strip() == "AQP1",
    )

    rows: list[dict[str, Any]] = []
    for packet_step, draft_row in draft_by_step.items():
        existing = existing_sheet.get(packet_step, {})
        workbench_row = workbench_by_step.get(packet_step, {})
        sheet_row = sheet_by_step.get(packet_step, {})
        brief_row = brief_by_step.get(packet_step, {})
        note_row = note_by_step.get(packet_step, {})
        blocker = str(draft_row.get("promotion_blocker", sheet_row.get("promotion_blocker", ""))).strip()
        rows.append(
            {
                "priority_rank": str(draft_row.get("priority_rank", sheet_row.get("priority_rank", ""))).strip(),
                "packet_step": packet_step,
                "candidate_name": str(draft_row.get("candidate_name", sheet_row.get("candidate_name", ""))).strip(),
                "commit_field_verdict": "manual_verdict_update",
                "commit_value_verdict": str(draft_row.get("suggested_manual_verdict", "")).strip(),
                "commit_field_confidence": "manual_confidence_update",
                "commit_value_confidence": str(draft_row.get("suggested_manual_confidence_update", "")).strip(),
                "commit_field_note": "manual_decision_note",
                "commit_value_note": str(draft_row.get("suggested_manual_decision_note", "")).strip(),
                "source_anchor": str(draft_row.get("source_anchor", "")).strip(),
                "review_focus": str(draft_row.get("current_focus", workbench_row.get("current_focus", brief_row.get("review_focus", "")))).strip(),
                "note_template": str(draft_row.get("manual_decision_note_template", note_row.get("manual_decision_note_template", ""))).strip(),
                "stop_condition": blocker,
                "stop_reason": (
                    "Stop if reviewer discovers evidence strong enough to challenge review-only status or any path would reopen authoritative apply."
                ),
                "manual_verdict_update": _prefer_nonempty(existing.get("manual_verdict_update", ""), sheet_row.get("manual_verdict_update", "")),
                "manual_confidence_update": _prefer_nonempty(existing.get("manual_confidence_update", ""), sheet_row.get("manual_confidence_update", "")),
                "manual_decision_note": _prefer_nonempty(existing.get("manual_decision_note", ""), sheet_row.get("manual_decision_note", "")),
                "update_status": _prefer_nonempty(existing.get("update_status", ""), sheet_row.get("update_status", ""), "pending_manual_verdict"),
                "authoritative_commit_allowed": "no",
            }
        )

    summary = {
        "target_id": "AQP1",
        "row_count": len(rows),
        "commit_ready_count": len(rows),
        "manual_fields_committed_count": sum(
            1
            for row in rows
            if row["manual_verdict_update"] or row["manual_confidence_update"] or row["manual_decision_note"]
        ),
        "pending_manual_confirmation_count": sum(1 for row in rows if row["update_status"] == "pending_manual_verdict"),
        "authoritative_commit_allowed": False,
        "stop_condition_count": len({row["stop_condition"] for row in rows if row["stop_condition"]}),
        "next_required_step": "Use this packet only to show the exact reviewer commit targets. Do not write into manual_* automatically, and stop if any review outcome would reopen authoritative apply or contradict review-only status.",
    }
    checklist = [
        "For each binder row, the only commit targets are manual_verdict_update, manual_confidence_update, and manual_decision_note.",
        "Keep the proposed verdicts at keep_review_only unless the reviewer explicitly overrides them.",
        "Stop immediately if new evidence would reopen authoritative apply or invalidate the review-only blocker.",
    ]
    return {"summary": summary, "checklist": checklist, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Manual Verdict Commit Packet",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- row_count: `{s['row_count']}`",
        f"- commit_ready_count: `{s['commit_ready_count']}`",
        f"- manual_fields_committed_count: `{s['manual_fields_committed_count']}`",
        f"- authoritative_commit_allowed: `{s['authoritative_commit_allowed']}`",
        f"- stop_condition_count: `{s['stop_condition_count']}`",
        "",
        "## Checklist",
        "",
    ]
    for item in payload["checklist"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Commit Rows",
            "",
            "| priority_rank | packet_step | candidate_name | commit_value_verdict | commit_value_confidence | stop_condition |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['commit_value_verdict']}` | `{row['commit_value_confidence']}` | `{row['stop_condition']}` |"
        )
        lines.extend(
            [
                "",
                f"- Commit note target for `{row['candidate_name']}`: {row['commit_value_note']}",
                f"- Stop reason: {row['stop_reason']}",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 manual verdict commit packet that sits after the draft packet and before any manual edit.")
    parser.add_argument("--reviewer-workbench-json", default=DEFAULT_REVIEWER_WORKBENCH_JSON)
    parser.add_argument("--binder-verdict-update-sheet-json", default=DEFAULT_BINDER_VERDICT_UPDATE_SHEET_JSON)
    parser.add_argument("--draft-packet-json", default=DEFAULT_DRAFT_PACKET_JSON)
    parser.add_argument("--note-templates-json", default=DEFAULT_NOTE_TEMPLATES_JSON)
    parser.add_argument("--binder-review-brief-json", default=DEFAULT_BINDER_REVIEW_BRIEF_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.reviewer_workbench_json),
        _load_json(args.binder_verdict_update_sheet_json),
        _load_json(args.draft_packet_json),
        _load_json(args.note_templates_json),
        _load_json(args.binder_review_brief_json),
        existing_sheet=_existing_by_step(_resolve(args.out_csv)),
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
