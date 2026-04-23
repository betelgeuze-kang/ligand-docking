#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CAPTURE_SHEET_CSV = "runs/ca2_negative_evidence_capture_sheet_current.csv"
DEFAULT_UPDATES_JSON = "runs/ca2_negative_evidence_capture_updates_current.json"
DEFAULT_COMMIT_JSON = "runs/ca2_evidence_closure_commit_packet_current.json"
DEFAULT_COMMIT_CSV = "runs/ca2_evidence_closure_commit_packet_current.csv"
DEFAULT_COMMIT_MD = "runs/ca2_evidence_closure_commit_packet_current.md"
DEFAULT_OUT_JSON = "runs/ca2_negative_evidence_capture_intake_current.json"
DEFAULT_OUT_MD = "runs/ca2_negative_evidence_capture_intake_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CA2 Negative Evidence Capture Intake",
        "",
        f"- capture_row_count: `{summary['capture_row_count']}`",
        f"- unique_packet_step_count: `{summary['unique_packet_step_count']}`",
        f"- validation_error_count: `{summary['validation_error_count']}`",
        f"- direct_negative_evidence_count: `{summary['direct_negative_evidence_count']}`",
        f"- direct_conflict_row_count: `{summary['direct_conflict_row_count']}`",
        f"- no_direct_negative_found_count: `{summary['no_direct_negative_found_count']}`",
        f"- source_linked_count: `{summary['source_linked_count']}`",
        f"- pending_capture_count: `{summary['pending_capture_count']}`",
        f"- confirmed_commit_count: `{summary['confirmed_commit_count']}`",
        f"- closure_mode: `{summary['closure_mode']}`",
        f"- review_only_conflict_or_gap_only: `{summary['review_only_conflict_or_gap_only']}`",
        f"- authoritative_negative_closure_allowed: `{summary['authoritative_negative_closure_allowed']}`",
        f"- remaining_blank_field: `{summary['remaining_blank_field']}`",
        f"- intake_applied: `{summary['intake_applied']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
    ]
    if payload["validation_errors"]:
        lines.extend(["", "## Validation Errors", ""])
        for err in payload["validation_errors"]:
            lines.append(f"- {err}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _existing_overlay(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    overlay = {}
    for row in rows:
        packet_step = str(row.get("packet_step", "")).strip()
        if not packet_step:
            continue
        overlay[packet_step] = {
            "manual_review_bucket": str(row.get("manual_review_bucket", "")).strip(),
            "manual_assay_type_honesty": str(row.get("manual_assay_type_honesty", "")).strip(),
            "manual_promotion_blocker": str(row.get("manual_promotion_blocker", "")).strip(),
            "manual_next_required_action": str(row.get("manual_next_required_action", "")).strip(),
            "manual_recommended_resolution": str(row.get("manual_recommended_resolution", "")).strip(),
            "manual_decision_note": str(row.get("manual_decision_note", "")).strip(),
            "commit_status": str(row.get("commit_status", "pending_manual_commit")).strip(),
        }
    return overlay


def _build_updates_payload(rows: list[dict[str, str]]) -> dict[str, Any]:
    update_rows: list[dict[str, str]] = []
    for row in rows:
        packet_step = str(row.get("packet_step", "")).strip()
        if not packet_step:
            continue
        direct_negative = str(row.get("supports_direct_ca2_negative", "")).strip().lower() in {"yes", "true", "1"}
        source_url = str(row.get("source_url", "")).strip()
        source_title = str(row.get("source_title", "")).strip()
        source_id = str(row.get("source_id", "")).strip() or "manual_source"
        capture_status = str(row.get("capture_status", "")).strip()
        if not (direct_negative and (source_url or source_title) and capture_status != "pending_capture"):
            continue
        provenance_parts = [
            "ca2_direct_negative_evidence",
            source_id,
            str(row.get("evidence_scope", "")).strip() or "target_specific_negative",
            str(row.get("assay_context", "")).strip() or "manual_review_only",
        ]
        note_parts = [
            "Direct CA2-specific negative evidence captured as review-only closure.",
            f"Source title: {source_title}." if source_title else "",
            f"Curator note: {str(row.get('manual_decision_note', '')).strip()}" if str(row.get("manual_decision_note", "")).strip() else "",
        ]
        update_rows.append(
            {
                "packet_step": packet_step,
                "verify_reference_binding_kcal_mol": "",
                "verify_provenance_source": "::".join(provenance_parts),
                "verify_source_url": source_url,
                "verification_status": "verified_direct_negative_evidence_review_only",
                "evidence_note": " ".join(part for part in note_parts if part).strip(),
            }
        )
    return {
        "summary": {
            "family": "ca2",
            "update_row_count": len(update_rows),
            "next_required_step": "Rows with direct CA2-specific negative evidence were applied as verified review-only negatives; keep quantitative value blank.",
        },
        "rows": update_rows,
    }


def build_payload(rows: list[dict[str, str]], updates_payload: dict[str, Any]) -> dict[str, Any]:
    validation_errors: list[str] = []
    step_counts: dict[str, int] = {}
    for row in rows:
        packet_step = str(row.get("packet_step", "")).strip()
        if not packet_step:
            validation_errors.append("blank packet_step row detected")
            continue
        step_counts[packet_step] = step_counts.get(packet_step, 0) + 1
    duplicates = [step for step, count in step_counts.items() if count > 1]
    for packet_step in duplicates:
        validation_errors.append(f"duplicate packet_step in capture sheet: {packet_step}")
    direct_negative_evidence_count = sum(
        1 for row in rows if str(row.get("supports_direct_ca2_negative", "")).strip().lower() in {"yes", "true", "1"}
    )
    direct_conflict_row_count = sum(
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
    pending_capture_count = sum(1 for row in rows if str(row.get("capture_status", "")).strip() == "pending_capture")
    confirmed_commit_count = sum(1 for row in rows if str(row.get("commit_status", "")).strip() != "pending_manual_commit")
    summary = {
        "capture_row_count": len(rows),
        "unique_packet_step_count": len(step_counts),
        "validation_error_count": len(validation_errors),
        "direct_negative_evidence_count": direct_negative_evidence_count,
        "direct_conflict_row_count": direct_conflict_row_count,
        "no_direct_negative_found_count": no_direct_negative_found_count,
        "source_linked_count": source_linked_count,
        "update_row_count": len(updates_payload.get("rows", []) or []),
        "pending_capture_count": pending_capture_count,
        "confirmed_commit_count": confirmed_commit_count,
        "closure_mode": "review_only_conflict_closure",
        "review_only_conflict_or_gap_only": True,
        "authoritative_negative_closure_allowed": False,
        "remaining_blank_field": "replacement_reference_binding_kcal_mol",
        "intake_applied": len(validation_errors) == 0,
        "next_required_step": (
            "Validation passed. CA2 remains review-only: five rows have direct inhibitor conflict and one row still lacks a direct CA2-specific negative source."
            if not validation_errors and direct_negative_evidence_count == 0
            else "Validation passed. Binding verification sheet, commit packet, and downstream CA2 reviewer surfaces were refreshed from the capture sheet."
            if not validation_errors
            else "Fix validation errors in the capture sheet, then rerun the intake updater."
        ),
    }
    return {"summary": summary, "validation_errors": validation_errors}


def _run(script_name: str, *args: str) -> None:
    script = ROOT / "tools" / script_name
    subprocess.run([sys.executable, str(script), *args], check=True, cwd=str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply the CA2 direct negative-evidence capture sheet into the commit packet and downstream reviewer surfaces.")
    parser.add_argument("--capture-sheet-csv", default=DEFAULT_CAPTURE_SHEET_CSV)
    parser.add_argument("--updates-json", default=DEFAULT_UPDATES_JSON)
    parser.add_argument("--commit-json", default=DEFAULT_COMMIT_JSON)
    parser.add_argument("--commit-csv", default=DEFAULT_COMMIT_CSV)
    parser.add_argument("--commit-md", default=DEFAULT_COMMIT_MD)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    capture_sheet_csv = _resolve(args.capture_sheet_csv)
    rows = _read_csv(capture_sheet_csv)
    updates_payload = _build_updates_payload(rows)
    payload = build_payload(rows, updates_payload)
    updates_json = _resolve(args.updates_json)
    updates_json.parent.mkdir(parents=True, exist_ok=True)
    updates_json.write_text(json.dumps(updates_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if payload["summary"]["intake_applied"]:
        _run(
            "apply_binding_verification_updates.py",
            "--family",
            "ca2",
            "--updates-json",
            str(updates_json),
        )
        _run("build_family_pending_row_disposition.py", "--family", "ca2")
        _run("build_family_manual_review_queue.py", "--family", "ca2")
        _run("build_ca2_next_verification_slice.py")
        _run("build_ca2_evidence_closure_day_plan.py")
        _run("build_ca2_review_only_negative_packet.py")
        _run("build_ca2_reviewer_workbench.py")
        _run("build_ca2_negative_reviewer_draft_packet.py")
        _run(
            "build_ca2_evidence_closure_commit_packet.py",
            "--existing-sheet-csv",
            str(capture_sheet_csv),
            "--out-json",
            str(_resolve(args.commit_json)),
            "--out-csv",
            str(_resolve(args.commit_csv)),
            "--out-md",
            str(_resolve(args.commit_md)),
        )
        _run("build_ca2_negative_review_day_plan.py")
        _run("build_ca2_pending_burndown_console.py")
        _run("build_partial_authoritative_commit_launchboard.py")
        _run("build_family_packet_catalog.py")
        payload["applied_commit_summary"] = _load_json(args.commit_json).get("summary", {})
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
