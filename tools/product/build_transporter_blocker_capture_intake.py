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

DEFAULT_CAPTURE_SHEET_CSV = "runs/transporter_blocker_capture_sheet_current.csv"
DEFAULT_UPDATES_JSON = "runs/transporter_blocker_capture_updates_current.json"
DEFAULT_OUT_JSON = "runs/transporter_blocker_capture_intake_current.json"
DEFAULT_OUT_MD = "runs/transporter_blocker_capture_intake_current.md"


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


def _run(script_name: str, *args: str) -> None:
    script = ROOT / "tools" / script_name
    subprocess.run([sys.executable, str(script), *args], check=True, cwd=str(ROOT))


def _build_updates_payload(rows: list[dict[str, str]]) -> dict[str, Any]:
    update_rows: list[dict[str, str]] = []
    for row in rows:
        supportive = str(row.get("supports_target_specific_packet_evidence", "")).strip().lower() in {"yes", "true", "1"}
        replacement_identifier = str(row.get("replacement_identifier", "")).strip()
        capture_status = str(row.get("capture_status", "")).strip()
        if not (supportive and replacement_identifier and capture_status != "pending_capture"):
            continue
        update_rows.append(
            {
                "target_id": str(row.get("target_id", "")).strip(),
                "lane_type": str(row.get("lane_type", "")).strip(),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "replacement_identifier": replacement_identifier,
                "replacement_source": str(row.get("replacement_source", "")).strip(),
                "source_title": str(row.get("source_title", "")).strip(),
                "source_url": str(row.get("source_url", "")).strip(),
                "capture_status": capture_status,
            }
        )
    return {
        "summary": {
            "family": "transporter",
            "update_row_count": len(update_rows),
            "next_required_step": "Rows with supportive target-specific packet evidence and explicit replacement identifiers were staged for blocker-closure follow-up.",
        },
        "rows": update_rows,
    }


def build_payload(rows: list[dict[str, str]], updates_payload: dict[str, Any]) -> dict[str, Any]:
    validation_errors: list[str] = []
    composite_counts: dict[str, int] = {}
    for row in rows:
        key = "::".join(
            [
                str(row.get("target_id", "")).strip(),
                str(row.get("lane_type", "")).strip(),
                str(row.get("packet_step", "")).strip(),
            ]
        )
        if not key.strip(":"):
            validation_errors.append("blank transporter capture key detected")
            continue
        composite_counts[key] = composite_counts.get(key, 0) + 1
    for key, count in composite_counts.items():
        if count > 1:
            validation_errors.append(f"duplicate transporter capture row: {key}")

    supportive_count = sum(
        1 for row in rows if str(row.get("supports_target_specific_packet_evidence", "")).strip().lower() in {"yes", "true", "1"}
    )
    source_linked_count = sum(1 for row in rows if str(row.get("source_title", "")).strip() or str(row.get("source_url", "")).strip())
    summary = {
        "row_count": len(rows),
        "binder_seed_row_count": sum(1 for row in rows if str(row.get("lane_type", "")).strip() == "binder_seed"),
        "negative_slot_row_count": sum(1 for row in rows if str(row.get("lane_type", "")).strip() == "negative_slot"),
        "source_linked_count": source_linked_count,
        "supportive_target_specific_packet_evidence_count": supportive_count,
        "captured_supportive_count": sum(
            1
            for row in rows
            if str(row.get("capture_status", "")).strip() != "pending_capture"
            and str(row.get("supports_target_specific_packet_evidence", "")).strip().lower() in {"yes", "true", "1"}
        ),
        "captured_review_only_count": sum(1 for row in rows if str(row.get("capture_status", "")).strip() == "captured_review_only"),
        "pending_capture_count": sum(1 for row in rows if str(row.get("capture_status", "")).strip() == "pending_capture"),
        "identifier_filled_count": sum(1 for row in rows if str(row.get("replacement_identifier", "")).strip()),
        "validation_error_count": len(validation_errors),
        "update_row_count": len(updates_payload.get("rows", []) or []),
        "intake_applied": len(validation_errors) == 0,
        "next_required_step": (
            "Validation passed. Transporter blocker capture sheet was accepted and downstream quickstart/dashboard/catalog surfaces were refreshed."
            if not validation_errors
            else "Fix validation errors in the transporter blocker capture sheet, then rerun the intake updater."
        ),
    }
    return {"summary": summary, "validation_errors": validation_errors}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Transporter Blocker Capture Intake",
        "",
        f"- row_count: `{summary['row_count']}`",
        f"- binder_seed_row_count: `{summary['binder_seed_row_count']}`",
        f"- negative_slot_row_count: `{summary['negative_slot_row_count']}`",
        f"- source_linked_count: `{summary['source_linked_count']}`",
        f"- supportive_target_specific_packet_evidence_count: `{summary['supportive_target_specific_packet_evidence_count']}`",
        f"- captured_supportive_count: `{summary['captured_supportive_count']}`",
        f"- captured_review_only_count: `{summary['captured_review_only_count']}`",
        f"- pending_capture_count: `{summary['pending_capture_count']}`",
        f"- identifier_filled_count: `{summary['identifier_filled_count']}`",
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
    parser = argparse.ArgumentParser(description="Apply the transporter blocker capture sheet and refresh current blocker-closure surfaces.")
    parser.add_argument("--capture-sheet-csv", default=DEFAULT_CAPTURE_SHEET_CSV)
    parser.add_argument("--updates-json", default=DEFAULT_UPDATES_JSON)
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
        _run("product/build_transporter_manual_review_quickstart_packet.py")
        _run("product/build_transporter_apply_draft_status.py")
        _run("product/build_transporter_manual_review_dashboard.py")
        _run("product/build_transporter_seed_row_promotion_board.py")
        _run("product/build_transporter_manual_review_launchboard.py")
        _run("build_execution_handoff_dashboard.py")
        _run("build_family_packet_catalog.py")
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
