#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PENDING_JSON = "runs/ca2_pending_row_disposition_current.json"
DEFAULT_NEXT_SLICE_JSON = "runs/ca2_next_verification_slice_current.json"
DEFAULT_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_WORKBOOK_CSV = "runs/ca2_packet_replacement_workbook_current.csv"
DEFAULT_CAPTURE_SHEET_JSON = "runs/ca2_negative_evidence_capture_sheet_current.json"
DEFAULT_LOCAL_HINTS_JSON = "runs/ca2_local_candidate_source_hints_current.json"
DEFAULT_OUT_JSON = "runs/ca2_review_only_negative_packet_current.json"
DEFAULT_OUT_CSV = "runs/ca2_review_only_negative_packet_current.csv"
DEFAULT_OUT_MD = "runs/ca2_review_only_negative_packet_current.md"
DEFAULT_CHECKLIST_MD = "runs/ca2_review_only_negative_checklist_current.md"


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


def _load_optional_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_csv(path_like: str) -> list[dict[str, str]]:
    with _resolve(path_like).open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _operator_note_template(ligand: str, blocker: str, next_action: str) -> str:
    if ligand == "acetaminophen":
        return (
            "Check whether any CA2-specific weak-activity or conflicting evidence exists; "
            "if conflict remains unresolved, keep review-only and do not assign a quantitative non-binder value."
        )
    return (
        f"Review CA2-specific negative evidence for {ligand}; if no direct curated evidence is found, "
        f"keep review-only, leave authoritative workbook unchanged, and record blocker `{blocker}` with `{next_action}`."
    )


def _join_unique(values: list[str]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ",".join(ordered)


def _format_evidence_anchor(source_id: str, source_title: str) -> str:
    parts = [part for part in (source_id.strip(), source_title.strip()) if part]
    return " | ".join(parts)


def _build_blocker_action_summary(
    blocker: str,
    evidence_anchor: str,
    local_exact_match_candidate_ids: str,
    local_hint_next_move: str,
) -> str:
    if blocker == "direct_ca2_inhibitor_conflict_present":
        lead = (
            f"Conflict anchor {evidence_anchor} keeps this row review-only."
            if evidence_anchor
            else "Direct CA2 inhibitor conflict keeps this row review-only."
        )
    elif blocker in {
        "no_direct_ca2_negative_evidence_curated",
        "no_direct_ca2_negative_evidence_located_after_research",
    }:
        lead = (
            f"No direct CA2-specific negative evidence is curated yet; last searched anchor {evidence_anchor}."
            if evidence_anchor
            else "No direct CA2-specific negative evidence is curated yet."
        )
    else:
        lead = (
            f"Blocker `{blocker}` remains active with anchor {evidence_anchor}."
            if blocker and evidence_anchor
            else f"Blocker `{blocker}` remains active."
            if blocker
            else "Reviewer confirmation is still required."
        )
    if local_exact_match_candidate_ids:
        return (
            f"{lead} Local exact-match repo hint(s): {local_exact_match_candidate_ids} "
            "(provenance-only, not CA2 evidence)."
        )
    if local_hint_next_move:
        return f"{lead} Local repo next move: {local_hint_next_move}."
    return lead


def build_payload(
    pending_payload: dict[str, Any],
    next_slice_payload: dict[str, Any],
    readiness_payload: dict[str, Any],
    workbook_rows: list[dict[str, str]],
    capture_sheet_payload: dict[str, Any],
    local_hints_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    local_hints_payload = local_hints_payload or {}
    workbook_by_step = {
        str(row.get("packet_step", "")).strip(): row for row in workbook_rows if str(row.get("packet_step", "")).strip()
    }
    next_slice_by_step = {
        str(row.get("packet_step", "")).strip(): row for row in next_slice_payload.get("rows", []) if str(row.get("packet_step", "")).strip()
    }
    readiness_by_step = {
        str(row.get("packet_step", "")).strip(): row
        for row in readiness_payload.get("workbook_rows", [])
        if str(row.get("packet_step", "")).strip()
    }
    capture_by_step = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in capture_sheet_payload.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }
    hint_rows_by_step: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in local_hints_payload.get("hint_rows", []) or []:
        step = str(row.get("packet_step", "")).strip()
        if step:
            hint_rows_by_step[step].append(dict(row))
    slot_hints_by_step = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in local_hints_payload.get("slot_summary", []) or []
        if str(row.get("packet_step", "")).strip()
    }

    packet_rows: list[dict[str, Any]] = []
    core_count = 0
    ood_count = 0
    high_conflict_count = 0

    for row in pending_payload.get("rows", []):
        if str(row.get("disposition", "")).strip() != "review_only_negative_evidence":
            continue
        step = str(row.get("packet_step", "")).strip()
        packet = str(row.get("packet", "")).strip()
        ligand = str(row.get("replacement_ligand_id", "")).strip()
        workbook_row = workbook_by_step.get(step, {})
        slice_row = next_slice_by_step.get(step, {})
        readiness_row = readiness_by_step.get(step, {})
        capture_row = capture_by_step.get(step, {})
        assay_honesty = str(capture_row.get("manual_assay_type_honesty", "")).strip() or str(slice_row.get("assay_type_honesty", "")).strip()
        review_reason = str(slice_row.get("review_reason", "")).strip()
        if packet == "core":
            core_count += 1
        elif packet == "ood":
            ood_count += 1
        operator_bucket = "conflict_review" if "conflict" in assay_honesty else "standard_review"
        if operator_bucket == "conflict_review":
            high_conflict_count += 1
        blocker = str(capture_row.get("manual_promotion_blocker", "")).strip() or str(row.get("promotion_blocker", "")).strip()
        next_action = str(capture_row.get("manual_next_required_action", "")).strip() or str(row.get("next_required_action", "")).strip()
        source_title = str(capture_row.get("source_title", "")).strip()
        source_id = str(capture_row.get("source_id", "")).strip()
        source_url = str(capture_row.get("source_url", "")).strip()
        evidence_anchor = _format_evidence_anchor(source_id, source_title)
        exact_hint_rows = [
            hint_row
            for hint_row in hint_rows_by_step.get(step, [])
            if str(hint_row.get("evidence_strength", "")).strip() == "exact_smiles_local_curated"
        ]
        local_exact_match_candidate_ids = _join_unique(
            [str(hint_row.get("candidate_ligand_id", "")).strip() for hint_row in exact_hint_rows]
        )
        local_exact_match_source_paths = _join_unique(
            [str(hint_row.get("repo_source_path", "")).strip() for hint_row in exact_hint_rows]
        )
        slot_hint = slot_hints_by_step.get(step, {})
        local_hint_next_move = str(slot_hint.get("recommended_next_move", "")).strip()
        packet_rows.append(
            {
                "priority_rank": int(str(row.get("priority_rank", "999"))),
                "packet": packet,
                "packet_step": step,
                "replacement_ligand_id": ligand,
                "replacement_source": str(workbook_row.get("replacement_source", "")).strip(),
                "replacement_smiles": str(workbook_row.get("replacement_smiles", "")).strip(),
                "replacement_scaffold": str(workbook_row.get("replacement_scaffold", "")).strip(),
                "current_missing_fields": str(readiness_row.get("missing_fields", "")).strip(),
                "review_reason": review_reason,
                "assay_type_honesty": assay_honesty,
                "disposition": str(row.get("disposition", "")).strip(),
                "promotion_blocker": blocker,
                "next_required_action": next_action,
                "capture_status": str(capture_row.get("capture_status", "")).strip(),
                "supports_direct_ca2_negative": str(capture_row.get("supports_direct_ca2_negative", "")).strip(),
                "evidence_scope": str(capture_row.get("evidence_scope", "")).strip(),
                "assay_context": str(capture_row.get("assay_context", "")).strip(),
                "weak_activity_conflict_present": str(capture_row.get("weak_activity_conflict_present", "")).strip(),
                "source_title": source_title,
                "source_id": source_id,
                "source_url": source_url,
                "evidence_anchor": evidence_anchor,
                "manual_decision_note": str(capture_row.get("manual_decision_note", "")).strip(),
                "local_hint_count": int(str(slot_hint.get("hint_count", len(hint_rows_by_step.get(step, [])))) or "0"),
                "local_exact_match_hint_count": len(exact_hint_rows),
                "local_exact_match_candidate_ids": local_exact_match_candidate_ids,
                "local_exact_match_source_paths": local_exact_match_source_paths,
                "local_hint_next_move": local_hint_next_move,
                "blocker_action_summary": _build_blocker_action_summary(
                    blocker,
                    evidence_anchor,
                    local_exact_match_candidate_ids,
                    local_hint_next_move,
                ),
                "operator_review_bucket": operator_bucket,
                "operator_goal": "keep_review_only_without_quantitative_fill",
                "authoritative_apply_allowed_now": "no",
                "operator_note_template": _operator_note_template(ligand, blocker, next_action),
            }
        )

    packet_rows.sort(key=lambda item: int(item["priority_rank"]))
    direct_conflict_row_count = sum(
        1 for row in packet_rows if str(row.get("promotion_blocker", "")).strip() == "direct_ca2_inhibitor_conflict_present"
    )
    no_direct_negative_found_count = sum(
        1
        for row in packet_rows
        if str(row.get("promotion_blocker", "")).strip()
        in {
            "no_direct_ca2_negative_evidence_curated",
            "no_direct_ca2_negative_evidence_located_after_research",
        }
    )
    summary = {
        "family": "ca2",
        "review_only_row_count": len(packet_rows),
        "core_review_only_count": core_count,
        "ood_review_only_count": ood_count,
        "high_conflict_row_count": high_conflict_count,
        "direct_conflict_row_count": direct_conflict_row_count,
        "no_direct_negative_found_count": no_direct_negative_found_count,
        "rows_with_cited_source": sum(
            1
            for row in packet_rows
            if row["source_id"] or row["source_title"] or row["source_url"]
        ),
        "rows_with_local_exact_match_hint": sum(1 for row in packet_rows if row["local_exact_match_hint_count"] > 0),
        "closure_mode": "review_only_conflict_closure",
        "authoritative_negative_closure_allowed": False,
        "most_common_missing_field": readiness_payload.get("summary", {}).get("most_common_missing_field", ""),
        "packet_ready_for_operator_review": True,
        "policy_statement": "CA2 negative-like rows are locked to review-only/conflict closure. Five rows have direct inhibitor conflict and one row still lacks a direct CA2-specific negative source, so authoritative negative closure is not allowed.",
        "next_required_step": (
            "Use this packet for reviewer-only negative evidence triage. Keep all six rows review-only, "
            "keep replacement_reference_binding_kcal_mol blank, and treat cited source anchors plus any "
            "local exact-match hints as reviewer context only, not claim-ready apply evidence."
        ),
    }
    return {"summary": summary, "rows": packet_rows}


def build_checklist(packet_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet_payload.get("rows", [])
    conflict_rows = [row for row in rows if row["operator_review_bucket"] == "conflict_review"]
    checklist = [
        {
            "order": 1,
            "check_id": "confirm_policy_lock",
            "applies_to": "all_rows",
            "instruction": "Keep all six CA2 negative-like rows review-only; do not copy any quantitative value into the authoritative workbook during this pass.",
        },
        {
            "order": 2,
            "check_id": "confirm_structure_fields_only",
            "applies_to": "all_rows",
            "instruction": "Use existing replacement ligand, SMILES, and scaffold fields only as context; the only unresolved authoritative field is the quantitative negative value.",
        },
        {
            "order": 3,
            "check_id": "review_conflict_rows_first",
            "applies_to": ",".join(row["packet_step"] for row in conflict_rows) or "none",
            "instruction": "Review conflict-tagged rows first and record any weak-activity ambiguity before touching standard review rows.",
        },
        {
            "order": 4,
            "check_id": "capture_source_if_found",
            "applies_to": "all_rows",
            "instruction": "If direct CA2-specific negative evidence is found, capture the exact source and URL in reviewer notes; otherwise leave the authoritative workbook unchanged.",
        },
        {
            "order": 5,
            "check_id": "rerun_packet_after_manual_triage",
            "applies_to": "all_rows",
            "instruction": "After manual triage, rerun the CA2 review packet builder so the reviewer-facing packet reflects any note-only status changes.",
        },
    ]
    return checklist


def _write_packet_md(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CA2 Review-Only Negative Packet",
        "",
        f"- family: `{summary['family']}`",
        f"- review_only_row_count: `{summary['review_only_row_count']}`",
        f"- core_review_only_count: `{summary['core_review_only_count']}`",
        f"- ood_review_only_count: `{summary['ood_review_only_count']}`",
        f"- high_conflict_row_count: `{summary['high_conflict_row_count']}`",
        f"- direct_conflict_row_count: `{summary['direct_conflict_row_count']}`",
        f"- no_direct_negative_found_count: `{summary['no_direct_negative_found_count']}`",
        f"- rows_with_cited_source: `{summary['rows_with_cited_source']}`",
        f"- rows_with_local_exact_match_hint: `{summary['rows_with_local_exact_match_hint']}`",
        f"- closure_mode: `{summary['closure_mode']}`",
        f"- authoritative_negative_closure_allowed: `{summary['authoritative_negative_closure_allowed']}`",
        f"- most_common_missing_field: `{summary['most_common_missing_field']}`",
        f"- packet_ready_for_operator_review: `{summary['packet_ready_for_operator_review']}`",
        "",
        "## Policy",
        "",
        f"- {summary['policy_statement']}",
        f"- {summary['next_required_step']}",
        "",
        "## Operator Rows",
        "",
        "| priority_rank | packet_step | ligand | review_bucket | assay_type_honesty | blocker | next_required_action | authoritative_apply_allowed_now |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | {row['packet_step']} | `{row['replacement_ligand_id']}` | "
            f"`{row['operator_review_bucket']}` | `{row['assay_type_honesty']}` | `{row['promotion_blocker']}` | "
            f"`{row['next_required_action']}` | `{row['authoritative_apply_allowed_now']}` |"
        )
    lines.extend(["", "## Evidence Anchors", ""])
    for row in payload["rows"]:
        source_anchor = row["evidence_anchor"] or "no_curated_anchor"
        local_exact = row["local_exact_match_candidate_ids"] or "none"
        lines.append(
            f"- `{row['packet_step']}`: `{source_anchor}` | local_exact_match_candidates=`{local_exact}` | {row['blocker_action_summary']}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_checklist_md(path: Path, checklist: list[dict[str, Any]]) -> None:
    lines = [
        "# CA2 Review-Only Negative Checklist",
        "",
        "| order | check_id | applies_to | instruction |",
        "| ---: | --- | --- | --- |",
    ]
    for row in checklist:
        lines.append(
            f"| {row['order']} | `{row['check_id']}` | `{row['applies_to']}` | {row['instruction']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2-only reviewer packet for the review-only negative tranche.")
    parser.add_argument("--pending-json", default=DEFAULT_PENDING_JSON)
    parser.add_argument("--next-slice-json", default=DEFAULT_NEXT_SLICE_JSON)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--workbook-csv", default=DEFAULT_WORKBOOK_CSV)
    parser.add_argument("--capture-sheet-json", default=DEFAULT_CAPTURE_SHEET_JSON)
    parser.add_argument("--local-hints-json", default=DEFAULT_LOCAL_HINTS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--checklist-md", default=DEFAULT_CHECKLIST_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.pending_json),
        _load_json(args.next_slice_json),
        _load_json(args.readiness_json),
        _read_csv(args.workbook_csv),
        _load_json(args.capture_sheet_json),
        _load_optional_json(args.local_hints_json),
    )
    checklist = build_checklist(payload)

    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    checklist_md = _resolve(args.checklist_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_packet_md(out_md, payload)
    _write_checklist_md(checklist_md, checklist)


if __name__ == "__main__":
    main()
