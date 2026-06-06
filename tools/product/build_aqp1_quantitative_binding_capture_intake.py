#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CAPTURE_SHEET_CSV = "runs/aqp1_quantitative_binding_capture_sheet_current.csv"
DEFAULT_UPDATES_JSON = "runs/aqp1_quantitative_binding_capture_updates_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_quantitative_binding_capture_intake_current.json"
DEFAULT_OUT_MD = "runs/aqp1_quantitative_binding_capture_intake_current.md"


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


def _build_updates_payload(rows: list[dict[str, str]]) -> dict[str, Any]:
    update_rows: list[dict[str, str]] = []
    for row in rows:
        supportive = str(row.get("supports_direct_quantitative_binding", "")).strip().lower() in {"yes", "true", "1"}
        capture_status = str(row.get("capture_status", "")).strip()
        source_title = str(row.get("source_title", "")).strip()
        source_url = str(row.get("source_url", "")).strip()
        quantitative_measure_value = str(row.get("quantitative_measure_value", "")).strip()
        replacement_binding = str(row.get("replacement_reference_binding_kcal_mol", "")).strip()
        if not (supportive and capture_status != "pending_capture" and (source_title or source_url)):
            continue
        if not (quantitative_measure_value or replacement_binding):
            continue
        update_rows.append(
            {
                "packet_step": str(row.get("packet_step", "")).strip(),
                "candidate_name": str(row.get("candidate_name", "")).strip(),
                "replacement_ligand_id": str(row.get("replacement_ligand_id", "")).strip(),
                "source_anchor": str(row.get("source_anchor", "")).strip(),
                "source_title": source_title,
                "source_url": source_url,
                "assay_type_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "quantitative_measure_kind": str(row.get("quantitative_measure_kind", "")).strip(),
                "quantitative_measure_value": quantitative_measure_value,
                "quantitative_measure_units": str(row.get("quantitative_measure_units", "")).strip(),
                "replacement_reference_binding_kcal_mol": replacement_binding,
                "capture_status": capture_status,
            }
        )
    return {
        "summary": {
            "family": "aqp1",
            "update_row_count": len(update_rows),
            "next_required_step": (
                "AQP1 rows with direct quantitative binding support were extracted into an overlay-ready updates artifact."
            ),
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
    for packet_step, count in step_counts.items():
        if count > 1:
            validation_errors.append(f"duplicate packet_step in AQP1 quantitative-binding capture sheet: {packet_step}")
    supportive_count = sum(
        1 for row in rows if str(row.get("supports_direct_quantitative_binding", "")).strip().lower() in {"yes", "true", "1"}
    )
    source_linked_count = sum(
        1 for row in rows if str(row.get("source_title", "")).strip() or str(row.get("source_url", "")).strip()
    )
    summary = {
        "row_count": len(rows),
        "source_linked_count": source_linked_count,
        "supportive_direct_quantitative_binding_count": supportive_count,
        "captured_supportive_count": sum(
            1
            for row in rows
            if str(row.get("capture_status", "")).strip() != "pending_capture"
            and str(row.get("supports_direct_quantitative_binding", "")).strip().lower() in {"yes", "true", "1"}
        ),
        "captured_review_only_gap_count": sum(
            1 for row in rows if str(row.get("capture_status", "")).strip() == "captured_review_only_gap"
        ),
        "pending_capture_count": sum(
            1 for row in rows if str(row.get("capture_status", "")).strip() == "pending_capture"
        ),
        "kcal_overlay_ready_count": sum(
            1 for row in rows if str(row.get("replacement_reference_binding_kcal_mol", "")).strip()
        ),
        "validation_error_count": len(validation_errors),
        "update_row_count": len(updates_payload.get("rows", []) or []),
        "intake_applied": len(validation_errors) == 0,
        "next_required_step": (
            "Validation passed. AQP1 quantitative-binding capture state is current."
            if not validation_errors
            else "Fix validation errors in the AQP1 quantitative-binding capture sheet, then rerun the intake updater."
        ),
    }
    return {"summary": summary, "validation_errors": validation_errors}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# AQP1 Quantitative-Binding Capture Intake",
        "",
        f"- row_count: `{summary['row_count']}`",
        f"- source_linked_count: `{summary['source_linked_count']}`",
        f"- supportive_direct_quantitative_binding_count: `{summary['supportive_direct_quantitative_binding_count']}`",
        f"- captured_supportive_count: `{summary['captured_supportive_count']}`",
        f"- captured_review_only_gap_count: `{summary['captured_review_only_gap_count']}`",
        f"- pending_capture_count: `{summary['pending_capture_count']}`",
        f"- kcal_overlay_ready_count: `{summary['kcal_overlay_ready_count']}`",
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
    parser = argparse.ArgumentParser(description="Validate the AQP1 quantitative-binding capture sheet and emit overlay-ready updates.")
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
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
