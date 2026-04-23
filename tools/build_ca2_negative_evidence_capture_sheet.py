#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_COMMIT_JSON = "runs/ca2_evidence_closure_commit_packet_current.json"
DEFAULT_REVIEW_PACKET_JSON = "runs/ca2_review_only_negative_packet_current.json"
DEFAULT_VERIFICATION_SHEET_JSON = "runs/ca2_binding_verification_sheet_current.json"
DEFAULT_AUTO_OVERLAY_JSON = "runs/ca2_public_negative_evidence_overlay_current.json"
DEFAULT_OUT_JSON = "runs/ca2_negative_evidence_capture_sheet_current.json"
DEFAULT_OUT_CSV = "runs/ca2_negative_evidence_capture_sheet_current.csv"
DEFAULT_OUT_MD = "runs/ca2_negative_evidence_capture_sheet_current.md"


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _overlay_by_step(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    payload = payload or {}
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }


def _verified_direct_negative_by_step(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    payload = payload or {}
    verified_rows: dict[str, dict[str, Any]] = {}
    source_rows = payload.get("sheet_rows", []) or payload.get("rows", []) or []
    for row in source_rows:
        packet_step = str(row.get("packet_step", "")).strip()
        verification_status = str(row.get("verification_status", "")).strip()
        if not packet_step or verification_status != "verified_direct_negative_evidence_review_only":
            continue
        provenance_parts = [part.strip() for part in str(row.get("verify_provenance_source", "")).split("::")]
        source_id = provenance_parts[1] if len(provenance_parts) > 1 else ""
        evidence_scope = provenance_parts[2] if len(provenance_parts) > 2 else "target_specific_direct_negative_upper_bound"
        assay_context = provenance_parts[3] if len(provenance_parts) > 3 else "direct_ca2_enzyme_inhibition_upper_bound"
        ligand = str(row.get("replacement_ligand_id", "")).strip()
        verified_rows[packet_step] = {
            "packet_step": packet_step,
            "ligand": ligand,
            "review_phase": "today_focus" if packet_step.startswith("core_") else "later_queue",
            "capture_status": "captured_direct_negative_review_only",
            "supports_direct_ca2_negative": "yes",
            "evidence_scope": evidence_scope,
            "assay_context": assay_context,
            "source_title": "",
            "source_id": source_id,
            "source_url": str(row.get("verify_source_url", "")).strip(),
            "weak_activity_conflict_present": "no",
            "manual_review_bucket": "standard_review",
            "manual_assay_type_honesty": "direct_ca2_negative_like_upper_bound_review_only",
            "manual_promotion_blocker": "direct_ca2_negative_evidence_curated_review_only",
            "manual_next_required_action": "apply_direct_negative_evidence_review_only",
            "manual_recommended_resolution": "keep_review_only_with_direct_ca2_negative_evidence",
            "manual_decision_note": str(row.get("notes", "")).strip(),
            "commit_status": "confirmed_review_only",
            "current_missing_fields": "replacement_reference_binding_kcal_mol",
            "must_remain_blank_fields": "replacement_reference_binding_kcal_mol",
            "review_reason": "direct CA2-specific negative evidence captured as review-only closure",
            "operator_note_template": (
                f"Review CA2-specific negative evidence for {ligand}; keep review-only, "
                "leave authoritative workbook unchanged, and preserve the direct negative evidence provenance."
            ),
        }
    return verified_rows


def build_payload(
    commit_payload: dict[str, Any],
    review_packet: dict[str, Any],
    existing_sheet: dict[str, dict[str, str]] | None = None,
    overlay_payload: dict[str, Any] | None = None,
    verification_sheet_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing_sheet = existing_sheet or {}
    overlay_rows = _overlay_by_step(overlay_payload)
    verified_rows = _verified_direct_negative_by_step(verification_sheet_payload)
    commit_rows = list(commit_payload.get("rows", []) or [])
    commit_by_step = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in commit_rows
        if str(row.get("packet_step", "")).strip()
    }
    review_rows = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in review_packet.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }
    ordered_steps: list[str] = []
    seen_steps: set[str] = set()

    def _append_step(step: str) -> None:
        step = str(step).strip()
        if not step or step in seen_steps:
            return
        seen_steps.add(step)
        ordered_steps.append(step)

    for row in commit_rows:
        _append_step(row.get("packet_step", ""))

    existing_items = sorted(
        existing_sheet.items(),
        key=lambda item: (
            int(str(item[1].get("capture_rank", "9999")) or "9999")
            if str(item[1].get("capture_rank", "")).strip().isdigit()
            else 9999,
            item[0],
        ),
    )
    for step, _ in existing_items:
        _append_step(step)
    for row in review_packet.get("rows", []) or []:
        _append_step(row.get("packet_step", ""))
    for step in verified_rows:
        _append_step(step)
    for step in overlay_rows:
        _append_step(step)

    rows: list[dict[str, Any]] = []
    for rank, packet_step in enumerate(ordered_steps, start=1):
        row = commit_by_step.get(packet_step, {})
        review_row = review_rows.get(packet_step, {})
        existing = existing_sheet.get(packet_step, {})
        overlay = overlay_rows.get(packet_step, {})
        verified = verified_rows.get(packet_step, {})
        existing_capture_status = str(existing.get("capture_status", "")).strip()
        existing_blocker = str(
            existing.get("manual_promotion_blocker", row.get("manual_promotion_blocker", row.get("staged_promotion_blocker", "")))
        ).strip()
        overlay_supports = str(overlay.get("supports_direct_ca2_negative", "")).strip().lower() in {"yes", "true", "1"}
        use_overlay = bool(overlay) and (
            existing_capture_status in {"", "pending_capture", "captured_no_direct_negative_source_found"}
            or existing_blocker in {
                "no_direct_ca2_negative_evidence_curated",
                "no_direct_ca2_negative_evidence_located_after_research",
            }
            or overlay_supports
        )
        rows.append(
            {
                "capture_rank": rank,
                "packet_step": packet_step,
                "ligand": str(
                    row.get("ligand")
                    or existing.get("ligand")
                    or verified.get("ligand")
                    or review_row.get("replacement_ligand_id")
                    or ""
                ).strip(),
                "review_phase": str(
                    row.get("review_phase")
                    or existing.get("review_phase")
                    or verified.get("review_phase")
                    or ("today_focus" if packet_step.startswith("core_") else "later_queue")
                ).strip(),
                "capture_status": str(
                    (overlay.get("capture_status") if use_overlay else "")
                    or existing.get("capture_status")
                    or verified.get("capture_status")
                    or "pending_capture"
                ).strip(),
                "supports_direct_ca2_negative": str(
                    (overlay.get("supports_direct_ca2_negative") if use_overlay else "")
                    or existing.get("supports_direct_ca2_negative")
                    or verified.get("supports_direct_ca2_negative")
                    or ""
                ).strip(),
                "evidence_scope": str(
                    (overlay.get("evidence_scope") if use_overlay else "")
                    or existing.get("evidence_scope")
                    or verified.get("evidence_scope")
                    or "target_specific_negative"
                ).strip(),
                "assay_context": str(
                    (overlay.get("assay_context") if use_overlay else "")
                    or existing.get("assay_context")
                    or verified.get("assay_context")
                    or row.get("staged_assay_type_honesty", "")
                ).strip(),
                "source_title": str(
                    (overlay.get("source_title") if use_overlay else "")
                    or existing.get("source_title", "")
                    or verified.get("source_title", "")
                ).strip(),
                "source_id": str(
                    (overlay.get("source_id") if use_overlay else "")
                    or existing.get("source_id", "")
                    or verified.get("source_id", "")
                ).strip(),
                "source_url": str(
                    (overlay.get("source_url") if use_overlay else "")
                    or existing.get("source_url", "")
                    or verified.get("source_url", "")
                ).strip(),
                "weak_activity_conflict_present": str(
                    (overlay.get("weak_activity_conflict_present") if use_overlay else "")
                    or existing.get("weak_activity_conflict_present")
                    or verified.get("weak_activity_conflict_present")
                    or ""
                ).strip(),
                "manual_review_bucket": str(
                    (overlay.get("manual_review_bucket") if use_overlay else "")
                    or existing.get("manual_review_bucket")
                    or verified.get("manual_review_bucket")
                    or row.get("manual_review_bucket")
                    or row.get("staged_review_bucket", "")
                ).strip(),
                "manual_assay_type_honesty": str(
                    (overlay.get("manual_assay_type_honesty") if use_overlay else "")
                    or existing.get("manual_assay_type_honesty")
                    or verified.get("manual_assay_type_honesty")
                    or row.get("manual_assay_type_honesty")
                    or row.get("staged_assay_type_honesty", "")
                ).strip(),
                "manual_promotion_blocker": str(
                    (overlay.get("manual_promotion_blocker") if use_overlay else "")
                    or existing.get("manual_promotion_blocker")
                    or verified.get("manual_promotion_blocker")
                    or row.get("manual_promotion_blocker")
                    or row.get("staged_promotion_blocker", "")
                ).strip(),
                "manual_next_required_action": str(
                    (overlay.get("manual_next_required_action") if use_overlay else "")
                    or existing.get("manual_next_required_action")
                    or verified.get("manual_next_required_action")
                    or row.get("manual_next_required_action")
                    or row.get("staged_next_required_action", "")
                ).strip(),
                "manual_recommended_resolution": str(
                    (overlay.get("manual_recommended_resolution") if use_overlay else "")
                    or existing.get("manual_recommended_resolution")
                    or verified.get("manual_recommended_resolution")
                    or row.get("manual_recommended_resolution")
                    or row.get("staged_recommended_resolution", "")
                ).strip(),
                "manual_decision_note": str(
                    (overlay.get("manual_decision_note") if use_overlay else "")
                    or existing.get("manual_decision_note")
                    or verified.get("manual_decision_note")
                    or row.get("manual_decision_note")
                    or row.get("draft_manual_decision_note", "")
                ).strip(),
                "commit_status": str(
                    (overlay.get("commit_status") if use_overlay else "")
                    or existing.get("commit_status")
                    or verified.get("commit_status")
                    or row.get("commit_status")
                    or "pending_manual_commit"
                ).strip(),
                "current_missing_fields": str(
                    row.get("current_missing_fields")
                    or existing.get("current_missing_fields")
                    or verified.get("current_missing_fields")
                    or ""
                ).strip(),
                "must_remain_blank_fields": str(
                    row.get("must_remain_blank_fields")
                    or existing.get("must_remain_blank_fields")
                    or verified.get("must_remain_blank_fields")
                    or "replacement_reference_binding_kcal_mol"
                ).strip(),
                "review_reason": str(
                    row.get("review_reason")
                    or existing.get("review_reason")
                    or verified.get("review_reason")
                    or review_row.get("review_reason", "")
                ).strip(),
                "operator_note_template": str(
                    review_row.get("operator_note_template")
                    or existing.get("operator_note_template")
                    or verified.get("operator_note_template")
                    or ""
                ).strip(),
            }
        )

    direct_evidence_count = sum(1 for row in rows if str(row.get("supports_direct_ca2_negative", "")).strip().lower() in {"yes", "true", "1"})
    conflict_row_count = sum(
        1
        for row in rows
        if str(row.get("manual_promotion_blocker", "")).strip() == "direct_ca2_inhibitor_conflict_present"
    )
    no_direct_negative_found_count = sum(
        1
        for row in rows
        if str(row.get("manual_promotion_blocker", "")).strip()
        in {
            "no_direct_ca2_negative_evidence_curated",
            "no_direct_ca2_negative_evidence_located_after_research",
        }
    )
    source_linked_count = sum(1 for row in rows if str(row.get("source_url", "")).strip())
    confirmed_commit_count = sum(1 for row in rows if str(row.get("commit_status", "")).strip() != "pending_manual_commit")
    summary = {
        "family": "ca2",
        "capture_row_count": len(rows),
        "today_focus_row_count": sum(1 for row in rows if row["review_phase"] == "today_focus"),
        "later_queue_row_count": sum(1 for row in rows if row["review_phase"] == "later_queue"),
        "direct_negative_evidence_count": direct_evidence_count,
        "direct_conflict_row_count": conflict_row_count,
        "no_direct_negative_found_count": no_direct_negative_found_count,
        "source_linked_count": source_linked_count,
        "confirmed_commit_count": confirmed_commit_count,
        "pending_capture_count": sum(1 for row in rows if str(row.get("capture_status", "")).strip() == "pending_capture"),
        "closure_mode": "review_only_conflict_closure",
        "review_only_conflict_or_gap_only": True,
        "authoritative_negative_closure_allowed": False,
        "remaining_blank_field": "replacement_reference_binding_kcal_mol",
        "next_required_step": (
            "No direct CA2-specific negative evidence is currently curated. "
            "Keep all six rows review-only, keep replacement_reference_binding_kcal_mol blank, "
            "and treat five rows as direct inhibitor conflicts plus one row as no-direct-negative-source-located "
            "until primary CA2-specific negative evidence is found."
            if direct_evidence_count == 0 and source_linked_count
            else "Capture direct CA2-specific negative evidence row by row, keep replacement_reference_binding_kcal_mol blank, then feed this sheet into the intake updater to refresh the commit packet and launchboard."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CA2 Negative Evidence Capture Sheet",
        "",
        f"- family: `{summary['family']}`",
        f"- capture_row_count: `{summary['capture_row_count']}`",
        f"- today_focus_row_count: `{summary['today_focus_row_count']}`",
        f"- later_queue_row_count: `{summary['later_queue_row_count']}`",
        f"- direct_negative_evidence_count: `{summary['direct_negative_evidence_count']}`",
        f"- direct_conflict_row_count: `{summary['direct_conflict_row_count']}`",
        f"- no_direct_negative_found_count: `{summary['no_direct_negative_found_count']}`",
        f"- source_linked_count: `{summary['source_linked_count']}`",
        f"- confirmed_commit_count: `{summary['confirmed_commit_count']}`",
        f"- pending_capture_count: `{summary['pending_capture_count']}`",
        f"- closure_mode: `{summary['closure_mode']}`",
        f"- review_only_conflict_or_gap_only: `{summary['review_only_conflict_or_gap_only']}`",
        f"- authoritative_negative_closure_allowed: `{summary['authoritative_negative_closure_allowed']}`",
        f"- remaining_blank_field: `{summary['remaining_blank_field']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Rows",
        "",
        "| rank | packet_step | ligand | review_phase | capture_status | supports_direct_ca2_negative | source_id | source_url | commit_status |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['capture_rank']} | `{row['packet_step']}` | `{row['ligand']}` | "
            f"`{row['review_phase']}` | `{row['capture_status']}` | "
            f"`{row['supports_direct_ca2_negative'] or '-'} ` | `{row['source_id'] or '-'}` | "
            f"`{row['source_url'] or '-'}` | `{row['commit_status']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2-specific negative evidence capture sheet for the six review-only non-binders.")
    parser.add_argument("--commit-json", default=DEFAULT_COMMIT_JSON)
    parser.add_argument("--review-packet-json", default=DEFAULT_REVIEW_PACKET_JSON)
    parser.add_argument("--verification-sheet-json", default=DEFAULT_VERIFICATION_SHEET_JSON)
    parser.add_argument("--auto-overlay-json", default=DEFAULT_AUTO_OVERLAY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_csv = _resolve(args.out_csv)
    payload = build_payload(
        _load_json(args.commit_json),
        _load_json(args.review_packet_json),
        existing_sheet=_existing_by_step(out_csv),
        overlay_payload=_maybe_load_json(args.auto_overlay_json),
        verification_sheet_payload=_maybe_load_json(args.verification_sheet_json),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
