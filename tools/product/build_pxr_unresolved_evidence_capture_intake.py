#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CAPTURE_SHEET_CSV = "runs/pxr_unresolved_evidence_capture_sheet_current.csv"
DEFAULT_UPDATES_JSON = "runs/pxr_unresolved_evidence_capture_updates_current.json"
DEFAULT_COMMIT_JSON = "runs/pxr_pending_resolution_commit_packet_current.json"
DEFAULT_COMMIT_CSV = "runs/pxr_pending_resolution_commit_packet_current.csv"
DEFAULT_COMMIT_MD = "runs/pxr_pending_resolution_commit_packet_current.md"
DEFAULT_OUT_JSON = "runs/pxr_unresolved_evidence_capture_intake_current.json"
DEFAULT_OUT_MD = "runs/pxr_unresolved_evidence_capture_intake_current.md"


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


def _run(script_name: str, *args: str) -> None:
    script = ROOT / "tools" / script_name
    subprocess.run([sys.executable, str(script), *args], check=True, cwd=str(ROOT))


def _build_updates_payload(rows: list[dict[str, str]]) -> dict[str, Any]:
    update_rows: list[dict[str, str]] = []
    for row in rows:
        packet_step = str(row.get("packet_step", "")).strip()
        supportive = str(row.get("supports_local_target_specific_human_pxr", "")).strip().lower() in {"yes", "true", "1"}
        source_title = str(row.get("source_title", "")).strip()
        source_url = str(row.get("source_url", "")).strip()
        capture_status = str(row.get("capture_status", "")).strip()
        if not (packet_step and supportive and (source_title or source_url) and capture_status != "pending_capture"):
            continue
        update_rows.append(
            {
                "packet_step": packet_step,
                "supports_local_target_specific_human_pxr": "yes",
                "source_title": source_title,
                "source_url": source_url,
                "capture_status": capture_status,
                "manual_commit_class_override": str(row.get("manual_commit_class_override", "")).strip(),
                "manual_commit_note": str(row.get("manual_commit_note", "")).strip(),
            }
        )
    return {
        "summary": {
            "family": "pxr",
            "update_row_count": len(update_rows),
            "next_required_step": "Rows with supportive target-specific human PXR evidence were staged for commit-packet overlay refresh.",
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
    for step, count in step_counts.items():
        if count > 1:
            validation_errors.append(f"duplicate packet_step in capture sheet: {step}")
    supportive_count = sum(
        1 for row in rows if str(row.get("supports_local_target_specific_human_pxr", "")).strip().lower() in {"yes", "true", "1"}
    )
    source_linked_count = sum(1 for row in rows if str(row.get("source_title", "")).strip() or str(row.get("source_url", "")).strip())
    summary = {
        "row_count": len(rows),
        "source_linked_count": source_linked_count,
        "supportive_target_specific_human_count": supportive_count,
        "captured_supportive_count": sum(
            1
            for row in rows
            if str(row.get("capture_status", "")).strip() != "pending_capture"
            and str(row.get("supports_local_target_specific_human_pxr", "")).strip().lower() in {"yes", "true", "1"}
        ),
        "captured_review_only_count": sum(
            1 for row in rows if str(row.get("capture_status", "")).strip() == "captured_review_only"
        ),
        "captured_conflict_or_gap_count": sum(
            1
            for row in rows
            if str(row.get("capture_status", "")).strip() in {"captured_conflict", "captured_gap", "captured_review_only_conflict"}
        ),
        "pending_capture_count": sum(1 for row in rows if str(row.get("capture_status", "")).strip() == "pending_capture"),
        "manual_commit_override_count": sum(1 for row in rows if str(row.get("manual_commit_class_override", "")).strip()),
        "validation_error_count": len(validation_errors),
        "update_row_count": len(updates_payload.get("rows", []) or []),
        "intake_applied": len(validation_errors) == 0,
        "next_required_step": (
            "Validation passed. PXR capture sheet was accepted and downstream commit, partial-authoritative, queue, shadow, and dashboard surfaces were refreshed."
            if not validation_errors
            else "Fix validation errors in the PXR capture sheet, then rerun the intake updater."
        ),
    }
    return {"summary": summary, "validation_errors": validation_errors}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# PXR Unresolved Evidence Capture Intake",
        "",
        f"- row_count: `{summary['row_count']}`",
        f"- source_linked_count: `{summary['source_linked_count']}`",
        f"- supportive_target_specific_human_count: `{summary['supportive_target_specific_human_count']}`",
        f"- captured_supportive_count: `{summary['captured_supportive_count']}`",
        f"- captured_review_only_count: `{summary['captured_review_only_count']}`",
        f"- captured_conflict_or_gap_count: `{summary['captured_conflict_or_gap_count']}`",
        f"- pending_capture_count: `{summary['pending_capture_count']}`",
        f"- manual_commit_override_count: `{summary['manual_commit_override_count']}`",
        f"- validation_error_count: `{summary['validation_error_count']}`",
        f"- update_row_count: `{summary['update_row_count']}`",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply the PXR unresolved-evidence capture sheet into current downstream reviewer surfaces.")
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
    rows = _read_csv(_resolve(args.capture_sheet_csv))
    updates_payload = _build_updates_payload(rows)
    payload = build_payload(rows, updates_payload)
    updates_json = _resolve(args.updates_json)
    updates_json.parent.mkdir(parents=True, exist_ok=True)
    updates_json.write_text(json.dumps(updates_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if payload["summary"]["intake_applied"]:
        capture_sheet_path = str(_resolve(args.capture_sheet_csv))
        _run(
            "build_family_pending_row_disposition.py",
            "--family",
            "pxr",
            "--capture-sheet-json",
            str(_resolve("runs/pxr_unresolved_evidence_capture_sheet_current.json")),
        )
        _run("build_family_manual_review_queue.py", "--family", "pxr")
        _run("product/build_pxr_pending_policy_note.py")
        _run("product/build_pxr_next_verification_slice.py", "--capture-sheet-json", str(_resolve("runs/pxr_unresolved_evidence_capture_sheet_current.json")))
        _run("product/build_pxr_pending_resolution_packet.py")
        _run("product/build_pxr_evidence_closure_day_plan.py")
        _run("product/build_pxr_reviewer_workbench.py")
        _run("product/build_pxr_pending_resolution_reviewer_draft_packet.py")
        _run("product/build_pxr_review_packet.py")
        _run(
            "product/build_pxr_pending_resolution_commit_packet.py",
            "--existing-sheet-csv",
            capture_sheet_path,
            "--out-json",
            str(_resolve(args.commit_json)),
            "--out-csv",
            str(_resolve(args.commit_csv)),
            "--out-md",
            str(_resolve(args.commit_md)),
        )
        _run("product/build_pxr_pending_burndown_console.py")
        _run("build_family_manual_review_burndown.py")
        _run("build_family_manual_review_priority_queue.py")
        _run("build_family_evidence_acquisition_queue.py")
        _run("product/build_pxr_literature_candidate_overlay.py")
        _run("build_family_evidence_investigator_packet.py")
        _run("product/build_pxr_exact_source_confirmation_packet.py")
        _run("product/build_pxr_conflict_resolver_packet.py")
        _run("build_partial_authoritative_family_handoff.py")
        _run("build_partial_authoritative_operator_console.py")
        _run("build_partial_authoritative_commit_launchboard.py")
        _run("build_partial_authoritative_quickstart_packet.py")
        _run("build_partial_authoritative_reviewer_console.py")
        _run("build_partial_authoritative_launchboard.py")
        _run("product/build_cross_family_residual_shadow_layer.py")
        _run("build_execution_handoff_dashboard.py")
        _run("build_family_packet_catalog.py")
        _run("build_family_operator_quicklink_board.py")
        payload["applied_commit_summary"] = _load_json(args.commit_json).get("summary", {})
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
