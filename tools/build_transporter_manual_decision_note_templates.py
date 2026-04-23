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
DEFAULT_OUT_JSON = "runs/transporter_manual_decision_note_templates_current.json"
DEFAULT_OUT_CSV = "runs/transporter_manual_decision_note_templates_current.csv"
DEFAULT_OUT_MD = "runs/transporter_manual_decision_note_templates_current.md"


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


def _build_note_template(row: dict[str, Any]) -> str:
    candidate_name = str(row.get("candidate_name", "")).strip()
    verdict = str(row.get("suggested_manual_verdict", "")).strip() or "keep_review_only"
    source_anchor = str(row.get("source_anchor", "")).strip() or "external anchor pending confirmation"
    evidence_strength = str(row.get("evidence_strength", "")).strip() or "unlabeled"
    potency_or_signal = str(row.get("potency_or_signal", "")).strip() or "transporter-context evidence exists"
    blocker = str(row.get("promotion_blocker", "")).strip() or "transporter packet evidence is still incomplete"
    next_step = str(row.get("next_required_action", "")).strip() or "manual_curated_search_or_defer"
    return (
        f"Manual review note template: keep `{candidate_name}` as `{verdict}` for now. "
        f"Anchor `{source_anchor}` provides `{evidence_strength}` evidence (`{potency_or_signal}`). "
        f"Do not promote to authoritative transporter packet rows yet because `{blocker}`. "
        f"Next action: `{next_step}`."
    )


def _collect_rows(target_id: str, sheet_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in sheet_payload.get("sheet_rows", []) or []:
        template = _build_note_template(row)
        rows.append(
            {
                "target_id": target_id,
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "candidate_name": str(row.get("candidate_name", "")).strip(),
                "source_anchor": str(row.get("source_anchor", "")).strip(),
                "suggested_manual_verdict": str(row.get("suggested_manual_verdict", "")).strip(),
                "update_status": str(row.get("update_status", "")).strip(),
                "manual_decision_note_template": template,
                "template_ready": "1" if template else "0",
            }
        )
    return rows


def build_payload(aqp1_sheet: dict[str, Any], glut1_sheet: dict[str, Any]) -> dict[str, Any]:
    rows = _collect_rows("AQP1", aqp1_sheet) + _collect_rows("GLUT1", glut1_sheet)
    summary = {
        "target_count": len({row["target_id"] for row in rows}),
        "template_row_count": len(rows),
        "template_ready_count": sum(1 for row in rows if row["template_ready"] == "1"),
        "pending_manual_verdict_count": sum(1 for row in rows if row["update_status"] == "pending_manual_verdict"),
        "completed_manual_verdict_count": sum(1 for row in rows if row["update_status"] != "pending_manual_verdict"),
        "aqp1_template_count": sum(1 for row in rows if row["target_id"] == "AQP1"),
        "glut1_template_count": sum(1 for row in rows if row["target_id"] == "GLUT1"),
        "note_template_ready": bool(rows),
        "next_required_step": "Use these note templates as reviewer-facing starting points, keep manual_verdict_update explicit, and do not auto-promote transporter binders from template text alone.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Manual Decision Note Templates",
        "",
        f"- target_count: `{s['target_count']}`",
        f"- template_row_count: `{s['template_row_count']}`",
        f"- template_ready_count: `{s['template_ready_count']}`",
        f"- pending_manual_verdict_count: `{s['pending_manual_verdict_count']}`",
        f"- completed_manual_verdict_count: `{s['completed_manual_verdict_count']}`",
        f"- aqp1_template_count: `{s['aqp1_template_count']}`",
        f"- glut1_template_count: `{s['glut1_template_count']}`",
        f"- note_template_ready: `{s['note_template_ready']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Templates",
        "",
        "| target_id | priority_rank | packet_step | candidate_name | suggested_manual_verdict | update_status | manual_decision_note_template |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['target_id']} | {row['priority_rank']} | `{row['packet_step']}` | "
            f"`{row['candidate_name']}` | `{row['suggested_manual_verdict']}` | `{row['update_status']}` | {row['manual_decision_note_template']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build reviewer-facing manual decision note templates for transporter binder slots.")
    parser.add_argument("--aqp1-binder-sheet-json", default=DEFAULT_AQP1_BINDER_SHEET_JSON)
    parser.add_argument("--glut1-binder-sheet-json", default=DEFAULT_GLUT1_BINDER_SHEET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_binder_sheet_json),
        _load_json(args.glut1_binder_sheet_json),
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
