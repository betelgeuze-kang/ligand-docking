#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WORKBENCH_JSON = "runs/ca2_reviewer_workbench_current.json"
DEFAULT_DAY_PLAN_JSON = "runs/ca2_evidence_closure_day_plan_current.json"
DEFAULT_MANUAL_QUEUE_JSON = "runs/ca2_manual_review_queue_current.json"
DEFAULT_OUT_JSON = "runs/ca2_negative_reviewer_draft_packet_current.json"
DEFAULT_OUT_CSV = "runs/ca2_negative_reviewer_draft_packet_current.csv"
DEFAULT_OUT_MD = "runs/ca2_negative_reviewer_draft_packet_current.md"


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


def _draft_note(row: dict[str, Any], queue_row: dict[str, Any]) -> str:
    ligand = str(row.get("ligand", "")).strip()
    blocker = str(row.get("promotion_blocker", "")).strip()
    action = str(row.get("next_required_action", "")).strip()
    queue_note = str(queue_row.get("notes", "")).strip()
    if ligand == "acetaminophen":
        lead = "Check for any CA2-specific weak-activity or conflicting evidence before treating this row as a clean negative."
    else:
        lead = f"Look for direct CA2-specific negative evidence for {ligand} before changing this row."
    notes = [
        lead,
        (
            f"If no direct curated evidence is found, keep review-only, leave authoritative workbook unchanged, "
            f"keep blocker `{blocker}`, and record `{action}`."
        ),
    ]
    blocker_action_summary = str(row.get("blocker_action_summary", "")).strip()
    if blocker_action_summary:
        notes.append(blocker_action_summary)
    source_url = str(row.get("source_url", "")).strip()
    if source_url:
        notes.append(f"Source URL: {source_url}.")
    queue_note = queue_note.strip()
    if queue_note:
        notes.append(queue_note)
    return " ".join(part for part in notes if part).strip()


def build_payload(
    workbench: dict[str, Any],
    day_plan: dict[str, Any],
    manual_queue: dict[str, Any],
) -> dict[str, Any]:
    workbench_rows = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in workbench.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }
    queue_rows = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in manual_queue.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }

    rows: list[dict[str, Any]] = []
    for day_row in day_plan.get("today_focus_rows", []) or []:
        step = str(day_row.get("packet_step", "")).strip()
        wb_row = workbench_rows.get(step, {})
        q_row = queue_rows.get(step, {})
        rows.append(
            {
                "day_queue_rank": day_row.get("day_queue_rank", ""),
                "packet_step": step,
                "ligand": str(day_row.get("ligand", "")).strip(),
                "review_phase": str(wb_row.get("review_phase", "today_focus")).strip(),
                "review_bucket": str(wb_row.get("operator_review_bucket", "")).strip(),
                "assay_type_honesty": str(wb_row.get("assay_type_honesty", day_row.get("assay_type_honesty", ""))).strip(),
                "promotion_blocker": str(wb_row.get("promotion_blocker", "")).strip(),
                "next_required_action": str(wb_row.get("next_required_action", "")).strip(),
                "recommended_resolution": str(wb_row.get("recommended_resolution", day_row.get("recommended_resolution", ""))).strip(),
                "authoritative_apply_allowed_now": "no",
                "auto_promote_allowed": "no",
                "draft_reviewer_prompt": str(wb_row.get("operator_note_template", "")).strip(),
                "draft_manual_decision_note": _draft_note(wb_row or day_row, q_row),
                "capture_status": str(wb_row.get("capture_status", "")).strip(),
                "source_id": str(wb_row.get("source_id", "")).strip(),
                "source_title": str(wb_row.get("source_title", "")).strip(),
                "source_url": str(wb_row.get("source_url", "")).strip(),
                "evidence_anchor": str(wb_row.get("evidence_anchor", "")).strip(),
                "local_exact_match_hint_count": int(str(wb_row.get("local_exact_match_hint_count", "0")) or "0"),
                "local_exact_match_candidate_ids": str(wb_row.get("local_exact_match_candidate_ids", "")).strip(),
                "local_hint_next_move": str(wb_row.get("local_hint_next_move", "")).strip(),
                "blocker_action_summary": str(wb_row.get("blocker_action_summary", "")).strip(),
                "source_queue_note": str(q_row.get("notes", "")).strip(),
            }
        )

    summary = {
        "family": "ca2",
        "draft_row_count": len(rows),
        "today_focus_count": len(rows),
        "auto_promote_allowed_count": 0,
        "authoritative_apply_allowed_count": 0,
        "closure_mode": str(workbench.get("summary", {}).get("closure_mode", "review_only_conflict_closure")).strip(),
        "review_only_conflict_or_gap_only": True,
        "direct_conflict_row_count": int(workbench.get("summary", {}).get("direct_conflict_row_count", 0) or 0),
        "no_direct_negative_found_count": int(workbench.get("summary", {}).get("no_direct_negative_found_count", 0) or 0),
        "rows_with_cited_source": int(workbench.get("summary", {}).get("rows_with_cited_source", 0) or 0),
        "rows_with_local_exact_match_hint": int(workbench.get("summary", {}).get("rows_with_local_exact_match_hint", 0) or 0),
        "authoritative_negative_closure_allowed": False,
        "remaining_blank_field": str(workbench.get("summary", {}).get("most_common_missing_field", "replacement_reference_binding_kcal_mol")).strip(),
        "next_required_step": "Use these draft notes to review today's three CA2 core negatives. Keep every row review-only, preserve review-only/conflict closure across all six rows, and leave replacement_reference_binding_kcal_mol blank because five rows are direct inhibitor conflicts while one still lacks a direct CA2-specific negative source.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# CA2 Negative Reviewer Draft Packet",
        "",
        f"- family: `{s['family']}`",
        f"- draft_row_count: `{s['draft_row_count']}`",
        f"- today_focus_count: `{s['today_focus_count']}`",
        f"- auto_promote_allowed_count: `{s['auto_promote_allowed_count']}`",
        f"- authoritative_apply_allowed_count: `{s['authoritative_apply_allowed_count']}`",
        f"- closure_mode: `{s['closure_mode']}`",
        f"- review_only_conflict_or_gap_only: `{s['review_only_conflict_or_gap_only']}`",
        f"- direct_conflict_row_count: `{s['direct_conflict_row_count']}`",
        f"- no_direct_negative_found_count: `{s['no_direct_negative_found_count']}`",
        f"- rows_with_cited_source: `{s['rows_with_cited_source']}`",
        f"- rows_with_local_exact_match_hint: `{s['rows_with_local_exact_match_hint']}`",
        f"- authoritative_negative_closure_allowed: `{s['authoritative_negative_closure_allowed']}`",
        f"- remaining_blank_field: `{s['remaining_blank_field']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Draft Rows",
        "",
        "| rank | packet_step | ligand | next_required_action | recommended_resolution | promotion_blocker | auto_promote_allowed |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['day_queue_rank']} | `{row['packet_step']}` | `{row['ligand']}` | "
            f"`{row['next_required_action']}` | `{row['recommended_resolution']}` | "
            f"`{row['promotion_blocker']}` | `{row['auto_promote_allowed']}` |"
        )
    lines.extend(["", "## Draft Reviewer Notes", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['packet_step']}`: {row['draft_manual_decision_note']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a reviewer-facing draft packet for today's CA2 review-only negatives.")
    parser.add_argument("--workbench-json", default=DEFAULT_WORKBENCH_JSON)
    parser.add_argument("--day-plan-json", default=DEFAULT_DAY_PLAN_JSON)
    parser.add_argument("--manual-queue-json", default=DEFAULT_MANUAL_QUEUE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.workbench_json),
        _load_json(args.day_plan_json),
        _load_json(args.manual_queue_json),
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
