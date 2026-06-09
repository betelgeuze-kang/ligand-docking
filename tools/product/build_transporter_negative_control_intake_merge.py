#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.product.build_transporter_negative_control_operator_worksheet import (
    INTAKE_EXPORT_COLUMNS,
    NEGATIVE_ITEM_IDS,
    _field_status,
    _has_primary_source_locator,
    _is_operator_placeholder,
    _text,
)

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_INTAKE_CSV = RUNS / "transporter_negative_control_operator_intake_export_current.csv"
DEFAULT_TEMPLATE_JSON = RUNS / "transporter_manual_review_intake_template_current.json"
DEFAULT_OUT_JSON = RUNS / "transporter_negative_control_intake_merge_current.json"
DEFAULT_OUT_MD = RUNS / "transporter_negative_control_intake_merge_current.md"

MERGE_FIELDS = tuple(column for column in INTAKE_EXPORT_COLUMNS if column != "review_row_id")

CLAIM_BOUNDARY = (
    "Transporter negative-control intake merge only; patches operator-reviewed intake export rows "
    "into the transporter manual review intake template for the six core_non_binder slots. "
    "It does not authoritatively apply scope promotion or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _should_apply_intake_value(field_name: str, value: str, *, reviewer_notes: str) -> bool:
    text = _text(value)
    if not text:
        return False
    if not _is_operator_placeholder(text):
        return True
    if text == "KEEP_BLOCKED" and field_name in {"replacement_reference_binding_kcal_mol", "negative_reference_binding_kcal_mol"}:
        return _has_primary_source_locator(reviewer_notes)
    return False


def merge_intake_into_template(
    template_packet: dict[str, Any],
    intake_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], int, int]:
    intake_by_item_id = {_text(row.get("item_id")): row for row in intake_rows if _text(row.get("item_id"))}
    merged_rows: list[dict[str, Any]] = []
    patched_field_count = 0
    patched_row_count = 0
    for row in template_packet.get("rows", []) or []:
        if not isinstance(row, dict):
            continue
        item_id = _text(row.get("item_id"))
        intake = intake_by_item_id.get(item_id)
        merged = dict(row)
        if intake:
            notes = _text(intake.get("reviewer_notes"))
            row_patched = False
            for field_name in MERGE_FIELDS:
                if field_name not in merged:
                    continue
                value = _text(intake.get(field_name))
                if _should_apply_intake_value(field_name, value, reviewer_notes=notes):
                    merged[field_name] = value
                    patched_field_count += 1
                    row_patched = True
            if row_patched:
                patched_row_count += 1
        merged_rows.append(merged)
    return merged_rows, patched_field_count, patched_row_count


def build_payload(
    *,
    template_packet: dict[str, Any],
    intake_rows: list[dict[str, str]],
    template_path: str,
    intake_path: str,
) -> dict[str, Any]:
    merged_rows, patched_field_count, patched_row_count = merge_intake_into_template(template_packet, intake_rows)
    negative_rows = [row for row in merged_rows if _text(row.get("item_id")) in NEGATIVE_ITEM_IDS]
    documented_blocked = 0
    pending = 0
    for row in negative_rows:
        notes = _text(row.get("reviewer_notes"))
        for field_name in MERGE_FIELDS:
            status = _field_status(field_name, row.get(field_name), reviewer_notes=notes)
            if status == "documented_blocked":
                documented_blocked += 1
            elif status == "operator_fill_pending":
                pending += 1
    ready = patched_row_count > 0 or bool(intake_rows)
    summary = {
        "packet_type": "transporter_negative_control_intake_merge",
        "status": "transporter_negative_control_intake_merge_ready" if ready else "blocked_transporter_negative_control_intake_merge",
        "claim_boundary": CLAIM_BOUNDARY,
        "template_json": template_path,
        "intake_export_csv": intake_path,
        "intake_row_count": len(intake_rows),
        "patched_row_count": patched_row_count,
        "patched_field_count": patched_field_count,
        "documented_blocked_field_count": documented_blocked,
        "operator_fill_pending_field_count": pending,
        "next_required_step": (
            "Rerun tools/build_product_scope_optional_lane_refresh_chain.py after operator intake merge."
            if patched_row_count > 0
            else "Fill transporter_negative_control_operator_intake_export_current.csv before merge."
        ),
    }
    return {"summary": summary, "rows": merged_rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge negative-control intake export into transporter manual review template.")
    parser.add_argument("--intake-csv", default=str(DEFAULT_INTAKE_CSV))
    parser.add_argument("--template-json", default=str(DEFAULT_TEMPLATE_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    parser.add_argument("--write-template", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    template_packet = _read_json(args.template_json)
    intake_rows = _read_csv(args.intake_csv)
    payload = build_payload(
        template_packet=template_packet,
        intake_rows=intake_rows,
        template_path=args.template_json,
        intake_path=args.intake_csv,
    )
    if args.write_template and template_packet:
        template_packet["rows"] = payload["rows"]
        summary = template_packet.get("summary")
        if isinstance(summary, dict):
            summary["transporter_negative_control_intake_merge_applied"] = True
            summary["transporter_negative_control_intake_merge_patched_row_count"] = payload["summary"]["patched_row_count"]
        _write_json(args.template_json, template_packet)
        payload["summary"]["template_written"] = True
    _write_json(args.out_json, payload)
    _resolve(args.out_md).write_text(
        "\n".join(
            [
                "# Transporter Negative Control Intake Merge",
                "",
                f"- status: `{payload['summary']['status']}`",
                f"- patched_row_count: `{payload['summary']['patched_row_count']}`",
                f"- patched_field_count: `{payload['summary']['patched_field_count']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
