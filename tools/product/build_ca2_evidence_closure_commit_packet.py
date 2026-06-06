#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORKBENCH_JSON = "runs/ca2_reviewer_workbench_current.json"
DEFAULT_DAY_PLAN_JSON = "runs/ca2_evidence_closure_day_plan_current.json"
DEFAULT_DRAFT_PACKET_JSON = "runs/ca2_negative_reviewer_draft_packet_current.json"
DEFAULT_NEXT_SLICE_JSON = "runs/ca2_next_verification_slice_current.json"
DEFAULT_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_OUT_JSON = "runs/ca2_evidence_closure_commit_packet_current.json"
DEFAULT_OUT_CSV = "runs/ca2_evidence_closure_commit_packet_current.csv"
DEFAULT_OUT_MD = "runs/ca2_evidence_closure_commit_packet_current.md"


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


def build_payload(
    workbench: dict[str, Any],
    day_plan: dict[str, Any],
    draft_packet: dict[str, Any],
    next_slice: dict[str, Any],
    readiness: dict[str, Any],
    existing_sheet: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    existing_sheet = existing_sheet or {}
    workbench_rows = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in workbench.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }
    draft_rows = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in draft_packet.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }
    next_rows = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in next_slice.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }
    readiness_rows = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in readiness.get("workbook_rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }

    rows: list[dict[str, Any]] = []
    day_rows = day_plan.get("rows", []) or day_plan.get("today_focus_rows", []) or []
    for day_row in day_rows:
        step = str(day_row.get("packet_step", "")).strip()
        existing = existing_sheet.get(step, {})
        wb = workbench_rows.get(step, {})
        draft = draft_rows.get(step, {})
        nxt = next_rows.get(step, {})
        ready = readiness_rows.get(step, {})
        review_phase = "today_focus" if str(day_row.get("today_focus", "")).strip() == "yes" else "later_queue"

        rows.append(
            {
                "day_queue_rank": day_row.get("day_queue_rank", ""),
                "packet_step": step,
                "ligand": str(day_row.get("ligand", "")).strip(),
                "review_phase": review_phase,
                "commit_scope": "review_only_evidence_closure",
                "confirm_now_fields": "manual_decision_note,review_bucket,assay_type_honesty,promotion_blocker,next_required_action,recommended_resolution",
                "must_remain_blank_fields": "replacement_reference_binding_kcal_mol",
                "must_not_change_fields": "replacement_smiles,replacement_scaffold,replacement_is_binder,authoritative_workbook_apply_state",
                "current_missing_fields": str(wb.get("current_missing_fields", ready.get("missing_fields", ""))).strip(),
                "quantitative_value_available": str(nxt.get("quantitative_value_available", "no")).strip(),
                "authoritative_apply_allowed_now": "no",
                "auto_promote_allowed": "no",
                "staged_review_bucket": str(wb.get("operator_review_bucket", draft.get("review_bucket", ""))).strip(),
                "staged_assay_type_honesty": str(wb.get("assay_type_honesty", day_row.get("assay_type_honesty", ""))).strip(),
                "staged_promotion_blocker": str(wb.get("promotion_blocker", "")).strip(),
                "staged_next_required_action": str(wb.get("next_required_action", "")).strip(),
                "staged_recommended_resolution": str(wb.get("recommended_resolution", day_row.get("recommended_resolution", ""))).strip(),
                "staged_manual_decision_note": str(draft.get("draft_manual_decision_note", "")).strip(),
                "next_required_action": str(wb.get("next_required_action", "")).strip(),
                "review_reason": str(nxt.get("review_reason", "")).strip(),
                "draft_manual_decision_note": str(draft.get("draft_manual_decision_note", "")).strip(),
                "capture_status": str(existing.get("capture_status", wb.get("capture_status", ""))).strip(),
                "evidence_scope": str(existing.get("evidence_scope", wb.get("evidence_scope", ""))).strip(),
                "assay_context": str(existing.get("assay_context", wb.get("assay_context", ""))).strip(),
                "source_title": str(existing.get("source_title", wb.get("source_title", ""))).strip(),
                "source_id": str(existing.get("source_id", wb.get("source_id", ""))).strip(),
                "source_url": str(existing.get("source_url", wb.get("source_url", ""))).strip(),
                "evidence_anchor": str(wb.get("evidence_anchor", "")).strip(),
                "local_exact_match_hint_count": int(str(wb.get("local_exact_match_hint_count", "0")) or "0"),
                "local_exact_match_candidate_ids": str(wb.get("local_exact_match_candidate_ids", "")).strip(),
                "local_hint_next_move": str(wb.get("local_hint_next_move", "")).strip(),
                "blocker_action_summary": str(wb.get("blocker_action_summary", "")).strip(),
                "manual_review_bucket": str(existing.get("manual_review_bucket", "")).strip(),
                "manual_assay_type_honesty": str(existing.get("manual_assay_type_honesty", "")).strip(),
                "manual_promotion_blocker": str(existing.get("manual_promotion_blocker", "")).strip(),
                "manual_next_required_action": str(existing.get("manual_next_required_action", "")).strip(),
                "manual_recommended_resolution": str(existing.get("manual_recommended_resolution", "")).strip(),
                "manual_decision_note": str(existing.get("manual_decision_note", "")).strip(),
                "commit_status": str(existing.get("commit_status", "pending_manual_commit")).strip(),
            }
        )

    conflict_review_row_count = sum(
        1 for row in rows if str(row.get("manual_promotion_blocker", "")).strip() == "direct_ca2_inhibitor_conflict_present"
    )
    no_direct_negative_source_row_count = sum(
        1
        for row in rows
        if str(row.get("manual_promotion_blocker", "")).strip()
        in {
            "no_direct_ca2_negative_evidence_curated",
            "no_direct_ca2_negative_evidence_located_after_research",
        }
    )
    summary = {
        "family": "ca2",
        "commit_row_count": len(rows),
        "confirm_now_row_count": len(rows),
        "today_focus_row_count": sum(1 for row in rows if row["review_phase"] == "today_focus"),
        "later_queue_row_count": sum(1 for row in rows if row["review_phase"] == "later_queue"),
        "must_remain_blank_field_count": 1,
        "remaining_blank_field": "replacement_reference_binding_kcal_mol",
        "authoritative_apply_allowed_count": 0,
        "auto_promote_allowed_count": 0,
        "closure_mode": "review_only_conflict_closure",
        "review_only_conflict_or_gap_only": True,
        "authoritative_negative_closure_allowed": False,
        "conflict_review_row_count": conflict_review_row_count,
        "review_only_conflict_row_count": conflict_review_row_count,
        "no_direct_negative_source_row_count": no_direct_negative_source_row_count,
        "rows_with_cited_source": sum(
            1 for row in rows if row["source_id"] or row["source_title"] or row["source_url"]
        ),
        "rows_with_local_exact_match_hint": sum(1 for row in rows if row["local_exact_match_hint_count"] > 0),
        "pending_manual_commit_count": sum(1 for row in rows if row["commit_status"] == "pending_manual_commit"),
        "confirmed_manual_commit_count": sum(1 for row in rows if row["commit_status"] != "pending_manual_commit"),
        "next_required_step": (
            "Confirm reviewer-facing evidence-closure fields for all six CA2 non-binder rows, keep "
            "replacement_reference_binding_kcal_mol blank for every row, and use the cited source anchors plus "
            "any local exact-match hints only as review context while preserving review-only status."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# CA2 Evidence-Closure Commit Packet",
        "",
        f"- family: `{s['family']}`",
        f"- commit_row_count: `{s['commit_row_count']}`",
        f"- confirm_now_row_count: `{s['confirm_now_row_count']}`",
        f"- today_focus_row_count: `{s['today_focus_row_count']}`",
        f"- later_queue_row_count: `{s['later_queue_row_count']}`",
        f"- must_remain_blank_field_count: `{s['must_remain_blank_field_count']}`",
        f"- remaining_blank_field: `{s['remaining_blank_field']}`",
        f"- authoritative_apply_allowed_count: `{s['authoritative_apply_allowed_count']}`",
        f"- auto_promote_allowed_count: `{s['auto_promote_allowed_count']}`",
        f"- closure_mode: `{s['closure_mode']}`",
        f"- review_only_conflict_or_gap_only: `{s['review_only_conflict_or_gap_only']}`",
        f"- authoritative_negative_closure_allowed: `{s['authoritative_negative_closure_allowed']}`",
        f"- conflict_review_row_count: `{s['conflict_review_row_count']}`",
        f"- review_only_conflict_row_count: `{s['review_only_conflict_row_count']}`",
        f"- no_direct_negative_source_row_count: `{s['no_direct_negative_source_row_count']}`",
        f"- rows_with_cited_source: `{s['rows_with_cited_source']}`",
        f"- rows_with_local_exact_match_hint: `{s['rows_with_local_exact_match_hint']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Commit Rows",
        "",
        "| rank | review_phase | packet_step | ligand | confirm_now_fields | must_remain_blank_fields | must_not_change_fields | next_required_action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['day_queue_rank']} | `{row['review_phase']}` | `{row['packet_step']}` | `{row['ligand']}` | "
            f"`{row['confirm_now_fields']}` | `{row['must_remain_blank_fields']}` | "
            f"`{row['must_not_change_fields']}` | `{row['next_required_action']}` |"
        )
    lines.extend(["", "## Draft Commit Notes", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['packet_step']}`: {row['draft_manual_decision_note']}")
    lines.extend(["", "## Evidence Anchors", ""])
    for row in payload["rows"]:
        source_anchor = row["evidence_anchor"] or "no_curated_anchor"
        local_exact = row["local_exact_match_candidate_ids"] or "none"
        lines.append(
            f"- `{row['packet_step']}`: `{source_anchor}` | local_exact_match_candidates=`{local_exact}` | {row['blocker_action_summary']}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2 evidence-closure commit packet for today's review-only negatives.")
    parser.add_argument("--workbench-json", default=DEFAULT_WORKBENCH_JSON)
    parser.add_argument("--day-plan-json", default=DEFAULT_DAY_PLAN_JSON)
    parser.add_argument("--draft-packet-json", default=DEFAULT_DRAFT_PACKET_JSON)
    parser.add_argument("--next-slice-json", default=DEFAULT_NEXT_SLICE_JSON)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--existing-sheet-csv", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_csv = _resolve(args.out_csv)
    existing_sheet = _existing_by_step(_resolve(args.existing_sheet_csv)) if str(args.existing_sheet_csv).strip() else _existing_by_step(out_csv)
    payload = build_payload(
        _load_json(args.workbench_json),
        _load_json(args.day_plan_json),
        _load_json(args.draft_packet_json),
        _load_json(args.next_slice_json),
        _load_json(args.readiness_json),
        existing_sheet=existing_sheet,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
