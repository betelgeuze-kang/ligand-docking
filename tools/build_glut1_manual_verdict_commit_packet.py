#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path


RUNS = Path("runs")

WORKBENCH_JSON = RUNS / "glut1_manual_review_queue_current.json"
VERDICT_UPDATE_JSON = RUNS / "glut1_binder_verdict_update_sheet_current.json"
DRAFT_PACKET_JSON = RUNS / "glut1_manual_verdict_draft_packet_current.json"
CANDIDATE_SHEET_JSON = RUNS / "glut1_candidate_verdict_sheet_current.json"
NOTE_TEMPLATES_JSON = RUNS / "transporter_manual_decision_note_templates_current.json"

OUT_JSON = RUNS / "glut1_manual_verdict_commit_packet_current.json"
OUT_CSV = RUNS / "glut1_manual_verdict_commit_packet_current.csv"
OUT_MD = RUNS / "glut1_manual_verdict_commit_packet_current.md"


def load_json(path: Path) -> dict:
    with path.open() as fh:
        return json.load(fh)


def index_by(rows: list[dict], key: str) -> dict[str, dict]:
    return {row[key]: row for row in rows}


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def existing_by_step(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {
        str(row.get("packet_step", "")).strip(): row
        for row in read_csv(path)
        if str(row.get("packet_step", "")).strip()
    }


def prefer_nonempty(*values: object) -> str:
    for value in values:
        text = str(value).strip()
        if text:
            return text
    return ""


def build_rows(
    workbench: dict,
    verdict_update: dict,
    draft_packet: dict,
    candidate_sheet: dict,
    note_templates: dict,
    existing_rows: dict[str, dict] | None = None,
) -> list[dict]:
    existing_rows = existing_rows or {}
    binder_rows = [row for row in workbench["rows"] if row["replacement_is_binder"] == "1"]
    verdict_map = index_by(verdict_update["sheet_rows"], "packet_step")
    draft_map = index_by(draft_packet["rows"], "packet_step")
    candidate_map = index_by(candidate_sheet["rows"], "proposed_packet_step")
    note_map = {
        row["packet_step"]: row
        for row in note_templates["rows"]
        if row["target_id"].lower() == "glut1"
    }

    rows: list[dict] = []
    for row in binder_rows:
        step = row["packet_step"]
        existing = existing_rows.get(step, {})
        verdict = verdict_map[step]
        draft = draft_map[step]
        candidate = candidate_map[step]
        note = note_map[step]
        rows.append(
            {
                "priority_rank": row["priority_rank"],
                "packet_step": step,
                "candidate_name": row["suggested_external_candidate"],
                "source_anchor": row["suggested_external_source_anchor"],
                "staged_manual_verdict": verdict["suggested_manual_verdict"],
                "staged_manual_confidence_update": verdict["suggested_manual_confidence_update"],
                "staged_manual_decision_note": note["manual_decision_note_template"],
                "staged_review_bucket": candidate["review_bucket"],
                "staged_promotion_policy": candidate["promotion_policy"],
                "promotion_blocker": row["promotion_blocker"],
                "next_required_action": row["next_required_action"],
                "confirm_fields": "manual_verdict_update,manual_confidence_update,manual_decision_note",
                "manual_verdict_update": prefer_nonempty(verdict.get("manual_verdict_update", ""), existing.get("manual_verdict_update", "")),
                "manual_confidence_update": prefer_nonempty(verdict.get("manual_confidence_update", ""), existing.get("manual_confidence_update", "")),
                "manual_decision_note": prefer_nonempty(verdict.get("manual_decision_note", ""), existing.get("manual_decision_note", "")),
                "update_status": prefer_nonempty(verdict.get("update_status", ""), existing.get("update_status", ""), draft["update_status"]),
            }
        )
    return rows


def build_summary(rows: list[dict]) -> dict:
    pending_count = sum(1 for row in rows if str(row.get("update_status", "")).strip() == "pending_manual_verdict")
    return {
        "family": "glut1",
        "binder_slot_count": len(rows),
        "staged_confirmation_count": len(rows),
        "manual_fields_committed_count": sum(
            1 for row in rows if row["manual_verdict_update"] or row["manual_confidence_update"] or row["manual_decision_note"]
        ),
        "pending_manual_confirmation_count": pending_count,
        "next_required_step": (
            "Use this commit packet as the final non-authoritative confirmation surface; the reviewer-side manual fields are now present, but transporter authoritative apply stays blocked."
            if pending_count == 0
            else "Use this commit packet as the final reviewer confirmation surface, but keep all manual_* fields empty until a reviewer explicitly confirms them."
        ),
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
        "# GLUT1 Manual Verdict Commit Packet",
        "",
        f"- family: `{summary['family']}`",
        f"- binder_slot_count: `{summary['binder_slot_count']}`",
        f"- staged_confirmation_count: `{summary['staged_confirmation_count']}`",
        f"- pending_manual_confirmation_count: `{summary['pending_manual_confirmation_count']}`",
        f"- manual_fields_committed_count: `{summary['manual_fields_committed_count']}`",
        "",
        "## Rule",
        "",
        "- This packet stages the exact verdict/confidence/note fields to confirm.",
        (
            "- Reviewer-side manual fields are already present here, but they remain non-authoritative and must not be treated as transporter apply approval."
            if summary["pending_manual_confirmation_count"] == 0
            else "- Manual fields are still pending explicit reviewer confirmation."
        ),
        "",
        "## Staged Confirmations",
        "",
        "| step | candidate | staged verdict | staged confidence | blocker | confirm fields |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| `{packet_step}` | `{candidate_name}` | `{staged_manual_verdict}` | `{staged_manual_confidence_update}` | `{promotion_blocker}` | `{confirm_fields}` |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Reviewer Use",
            "",
            "- Open this after the GLUT1 draft packet if you want the exact staged fields to confirm.",
            "- Cross-check the staged values against `runs/glut1_binder_verdict_update_sheet_current.md`.",
            "- Do not treat these reviewer-side confirmations as authoritative transporter apply approval.",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    workbench = load_json(WORKBENCH_JSON)
    verdict_update = load_json(VERDICT_UPDATE_JSON)
    draft_packet = load_json(DRAFT_PACKET_JSON)
    candidate_sheet = load_json(CANDIDATE_SHEET_JSON)
    note_templates = load_json(NOTE_TEMPLATES_JSON)

    rows = build_rows(
        workbench,
        verdict_update,
        draft_packet,
        candidate_sheet,
        note_templates,
        existing_rows=existing_by_step(OUT_CSV),
    )
    summary = build_summary(rows)
    payload = {"summary": summary, "rows": rows}

    write_json(OUT_JSON, payload)
    write_csv(OUT_CSV, rows)
    write_md(OUT_MD, summary, rows)


if __name__ == "__main__":
    main()
