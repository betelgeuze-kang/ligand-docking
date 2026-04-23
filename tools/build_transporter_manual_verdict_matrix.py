#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_AQP1_BINDER_SHEET_JSON = "runs/aqp1_binder_verdict_update_sheet_current.json"
DEFAULT_GLUT1_BINDER_SHEET_JSON = "runs/glut1_binder_verdict_update_sheet_current.json"
DEFAULT_NOTE_TEMPLATES_JSON = "runs/transporter_manual_decision_note_templates_current.json"
DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_OUT_JSON = "runs/transporter_manual_verdict_matrix_current.json"
DEFAULT_OUT_CSV = "runs/transporter_manual_verdict_matrix_current.csv"
DEFAULT_OUT_MD = "runs/transporter_manual_verdict_matrix_current.md"
GLUT1_SOURCE_CONFIRMATION_PACKET_MD = "runs/glut1_second_wave_source_confirmation_packet_current.md"


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


def _maybe_load_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
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


def _note_lookup(note_templates: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in note_templates.get("rows", []) or []:
        key = (str(row.get("target_id", "")).strip(), str(row.get("packet_step", "")).strip())
        if key[0] and key[1]:
            lookup[key] = dict(row)
    return lookup


def _glut1_source_confirmation_handoff(payload: dict[str, Any] | None) -> dict[str, Any]:
    summary = dict((payload or {}).get("summary", {}) or {})
    ready = bool(summary)
    return {
        "open_source_confirmation": GLUT1_SOURCE_CONFIRMATION_PACKET_MD if ready else "",
        "second_wave_source_confirmation_ready": ready,
        "primary_focus_ligand": str(summary.get("primary_focus_ligand", "") or "").strip(),
        "direct_quantitative_binding_count": int(summary.get("direct_quantitative_binding_count", 0) or 0),
        "exact_target_pair_activity_count": int(summary.get("exact_target_pair_activity_count", 0) or 0),
        "structured_pair_absent_count": int(summary.get("structured_pair_absent_count", 0) or 0),
    }


def _collect_rows(
    target_id: str,
    sheet_payload: dict[str, Any],
    note_lookup: dict[tuple[str, str], dict[str, Any]],
    glut1_source_confirmation: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in sheet_payload.get("sheet_rows", []) or []:
        packet_step = str(row.get("packet_step", "")).strip()
        note_row = note_lookup.get((target_id, packet_step), {})
        open_source_confirmation = ""
        source_confirmation_primary_focus_ligand = ""
        source_confirmation_direct_quantitative_binding_count = 0
        source_confirmation_exact_target_pair_activity_count = 0
        source_confirmation_structured_pair_absent_count = 0
        if target_id == "GLUT1" and glut1_source_confirmation:
            open_source_confirmation = str(glut1_source_confirmation.get("open_source_confirmation", "")).strip()
            source_confirmation_primary_focus_ligand = str(
                glut1_source_confirmation.get("primary_focus_ligand", "")
            ).strip()
            source_confirmation_direct_quantitative_binding_count = int(
                glut1_source_confirmation.get("direct_quantitative_binding_count", 0) or 0
            )
            source_confirmation_exact_target_pair_activity_count = int(
                glut1_source_confirmation.get("exact_target_pair_activity_count", 0) or 0
            )
            source_confirmation_structured_pair_absent_count = int(
                glut1_source_confirmation.get("structured_pair_absent_count", 0) or 0
            )
        rows.append(
            {
                "target_id": target_id,
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": packet_step,
                "candidate_name": str(row.get("candidate_name", "")).strip(),
                "current_recommended_verdict": str(row.get("current_recommended_verdict", "")).strip(),
                "suggested_manual_verdict": str(row.get("suggested_manual_verdict", "")).strip(),
                "manual_verdict_update": str(row.get("manual_verdict_update", "")).strip(),
                "update_status": str(row.get("update_status", "")).strip(),
                "note_template_ready": "1" if note_row else "0",
                "manual_decision_note_template": str(note_row.get("manual_decision_note_template", "")).strip(),
                "open_source_confirmation": open_source_confirmation,
                "source_confirmation_primary_focus_ligand": source_confirmation_primary_focus_ligand,
                "source_confirmation_direct_quantitative_binding_count": source_confirmation_direct_quantitative_binding_count,
                "source_confirmation_exact_target_pair_activity_count": source_confirmation_exact_target_pair_activity_count,
                "source_confirmation_structured_pair_absent_count": source_confirmation_structured_pair_absent_count,
            }
        )
    return rows


def build_payload(
    aqp1_sheet: dict[str, Any],
    glut1_sheet: dict[str, Any],
    note_templates: dict[str, Any],
    glut1_source_confirmation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lookup = _note_lookup(note_templates)
    glut1_handoff = _glut1_source_confirmation_handoff(glut1_source_confirmation)
    rows = _collect_rows("AQP1", aqp1_sheet, lookup) + _collect_rows("GLUT1", glut1_sheet, lookup, glut1_handoff)
    summary = {
        "target_count": len({row["target_id"] for row in rows}),
        "row_count": len(rows),
        "pending_manual_verdict_count": sum(1 for row in rows if row["update_status"] == "pending_manual_verdict"),
        "completed_manual_verdict_count": sum(1 for row in rows if row["update_status"] != "pending_manual_verdict"),
        "note_template_ready_count": sum(1 for row in rows if row["note_template_ready"] == "1"),
        "aqp1_pending_count": sum(1 for row in rows if row["target_id"] == "AQP1" and row["update_status"] == "pending_manual_verdict"),
        "glut1_pending_count": sum(1 for row in rows if row["target_id"] == "GLUT1" and row["update_status"] == "pending_manual_verdict"),
        "glut1_open_source_confirmation": glut1_handoff["open_source_confirmation"],
        "glut1_second_wave_source_confirmation_ready": glut1_handoff["second_wave_source_confirmation_ready"],
        "glut1_second_wave_source_confirmation_primary_focus_ligand": glut1_handoff["primary_focus_ligand"],
        "glut1_direct_quantitative_binding_count": glut1_handoff["direct_quantitative_binding_count"],
        "glut1_exact_target_pair_activity_count": glut1_handoff["exact_target_pair_activity_count"],
        "glut1_structured_pair_absent_count": glut1_handoff["structured_pair_absent_count"],
        "next_required_step": "Work through AQP1 first-wave rows first, then GLUT1 second-wave rows, and keep all transporter manual verdicts non-authoritative until donor policy and packet evidence reopen."
        + (
            f" Before GLUT1 reviewer-side wording changes, open {glut1_handoff['open_source_confirmation'] or GLUT1_SOURCE_CONFIRMATION_PACKET_MD}, start with {glut1_handoff['primary_focus_ligand'] or 'cytochalasin B'}, and carry direct_quantitative_binding_count={glut1_handoff['direct_quantitative_binding_count']}, exact_target_pair_activity_count={glut1_handoff['exact_target_pair_activity_count']}, structured_pair_absent_count={glut1_handoff['structured_pair_absent_count']} as context only."
            if glut1_handoff["second_wave_source_confirmation_ready"]
            else ""
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Manual Verdict Matrix",
        "",
        f"- target_count: `{s['target_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- pending_manual_verdict_count: `{s['pending_manual_verdict_count']}`",
        f"- completed_manual_verdict_count: `{s['completed_manual_verdict_count']}`",
        f"- note_template_ready_count: `{s['note_template_ready_count']}`",
        f"- aqp1_pending_count: `{s['aqp1_pending_count']}`",
        f"- glut1_pending_count: `{s['glut1_pending_count']}`",
        f"- glut1_open_source_confirmation: `{s['glut1_open_source_confirmation']}`",
        f"- glut1_second_wave_source_confirmation_ready: `{s['glut1_second_wave_source_confirmation_ready']}`",
        f"- glut1_second_wave_source_confirmation_primary_focus_ligand: `{s['glut1_second_wave_source_confirmation_primary_focus_ligand']}`",
        f"- glut1_direct_quantitative_binding_count: `{s['glut1_direct_quantitative_binding_count']}`",
        f"- glut1_exact_target_pair_activity_count: `{s['glut1_exact_target_pair_activity_count']}`",
        f"- glut1_structured_pair_absent_count: `{s['glut1_structured_pair_absent_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Matrix",
        "",
        "| target_id | priority_rank | packet_step | candidate_name | current_recommended_verdict | suggested_manual_verdict | manual_verdict_update | update_status | note_template_ready | open_source_confirmation |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['target_id']} | {row['priority_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['current_recommended_verdict']}` | `{row['suggested_manual_verdict']}` | `{row['manual_verdict_update']}` | `{row['update_status']}` | {row['note_template_ready']} | `{row['open_source_confirmation']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a single transporter manual-verdict matrix across AQP1 and GLUT1.")
    parser.add_argument("--aqp1-binder-sheet-json", default=DEFAULT_AQP1_BINDER_SHEET_JSON)
    parser.add_argument("--glut1-binder-sheet-json", default=DEFAULT_GLUT1_BINDER_SHEET_JSON)
    parser.add_argument("--note-templates-json", default=DEFAULT_NOTE_TEMPLATES_JSON)
    parser.add_argument("--glut1-source-confirmation-json", default=DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_binder_sheet_json),
        _load_json(args.glut1_binder_sheet_json),
        _load_json(args.note_templates_json),
        _maybe_load_json(args.glut1_source_confirmation_json),
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
