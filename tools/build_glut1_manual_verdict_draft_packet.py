#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path


RUNS = Path("runs")

WORKBENCH_JSON = RUNS / "glut1_manual_review_queue_current.json"
VERDICT_SHEET_JSON = RUNS / "glut1_binder_verdict_update_sheet_current.json"
CANDIDATE_SHEET_JSON = RUNS / "glut1_candidate_verdict_sheet_current.json"
NOTE_TEMPLATES_JSON = RUNS / "transporter_manual_decision_note_templates_current.json"

OUT_JSON = RUNS / "glut1_manual_verdict_draft_packet_current.json"
OUT_CSV = RUNS / "glut1_manual_verdict_draft_packet_current.csv"
OUT_MD = RUNS / "glut1_manual_verdict_draft_packet_current.md"


def load_json(path: Path) -> dict:
    with path.open() as fh:
        return json.load(fh)


def index_candidate_rows(candidate_sheet: dict) -> dict[str, dict]:
    return {row["proposed_packet_step"]: row for row in candidate_sheet["rows"]}


def index_note_templates(note_templates: dict) -> dict[str, dict]:
    rows = {}
    for row in note_templates["rows"]:
        if row["target_id"].lower() == "glut1":
            rows[row["packet_step"]] = row
    return rows


def build_rows(
    workbench: dict,
    verdict_sheet: dict,
    candidate_sheet: dict,
    note_templates: dict,
) -> list[dict]:
    candidate_map = index_candidate_rows(candidate_sheet)
    note_map = index_note_templates(note_templates)

    rows: list[dict] = []
    for row in workbench["rows"]:
        if row["replacement_is_binder"] != "1":
            continue
        packet_step = row["packet_step"]
        candidate = candidate_map[packet_step]
        note = note_map[packet_step]
        rows.append(
            {
                "priority_rank": row["priority_rank"],
                "packet_step": packet_step,
                "current_ligand_id": row["current_ligand_id"],
                "candidate_name": row["suggested_external_candidate"],
                "source_anchor": row["suggested_external_source_anchor"],
                "suggested_review_bucket": candidate["review_bucket"],
                "suggested_manual_verdict": candidate["recommended_verdict"],
                "suggested_manual_confidence_update": "medium",
                "suggested_manual_decision_note": note["manual_decision_note_template"],
                "promotion_blocker": row["promotion_blocker"],
                "next_required_action": row["next_required_action"],
                "manual_verdict_update": "",
                "manual_confidence_update": "",
                "manual_decision_note": "",
                "update_status": "pending_manual_verdict",
            }
        )
    return rows


def build_summary(verdict_sheet: dict, rows: list[dict]) -> dict:
    return {
        "family": "glut1",
        "binder_slot_count": len(rows),
        "suggested_prefill_count": len(rows),
        "pending_manual_verdict_count": len(rows),
        "completed_manual_verdict_count": 0,
        "manual_fields_committed_count": 0,
        "next_required_step": "Use this draft packet to review suggested GLUT1 binder verdicts, but keep manual_* fields empty until a reviewer explicitly commits them.",
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
        "# GLUT1 Manual Verdict Draft Packet",
        "",
        f"- family: `{summary['family']}`",
        f"- binder_slot_count: `{summary['binder_slot_count']}`",
        f"- suggested_prefill_count: `{summary['suggested_prefill_count']}`",
        f"- pending_manual_verdict_count: `{summary['pending_manual_verdict_count']}`",
        f"- manual_fields_committed_count: `{summary['manual_fields_committed_count']}`",
        "",
        "## Rule",
        "",
        "- Suggested fields are prefilled for reviewer speed, but all `manual_*` fields must stay empty until a reviewer explicitly commits them.",
        "",
        "## Draft Rows",
        "",
        "| step | candidate | source | suggested verdict | blocker | next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| `{packet_step}` | `{candidate_name}` | `{source_anchor}` | `{suggested_manual_verdict}` | `{promotion_blocker}` | `{next_required_action}` |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Reviewer Use",
            "",
            "- Open this packet first if you want a suggested-only GLUT1 binder draft.",
            "- Then cross-check `runs/glut1_candidate_verdict_sheet_current.md` and `runs/glut1_binder_verdict_update_sheet_current.md`.",
            "- Do not treat this packet as authoritative apply evidence.",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    workbench = load_json(WORKBENCH_JSON)
    verdict_sheet = load_json(VERDICT_SHEET_JSON)
    candidate_sheet = load_json(CANDIDATE_SHEET_JSON)
    note_templates = load_json(NOTE_TEMPLATES_JSON)

    rows = build_rows(workbench, verdict_sheet, candidate_sheet, note_templates)
    summary = build_summary(verdict_sheet, rows)
    payload = {"summary": summary, "rows": rows}

    write_json(OUT_JSON, payload)
    write_csv(OUT_CSV, rows)
    write_md(OUT_MD, summary, rows)


if __name__ == "__main__":
    main()
