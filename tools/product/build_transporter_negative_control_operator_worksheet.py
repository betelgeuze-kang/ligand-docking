#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_TEMPLATE_JSON = RUNS / "transporter_manual_review_intake_template_current.json"
DEFAULT_OUT_JSON = RUNS / "transporter_negative_control_operator_worksheet_current.json"
DEFAULT_WORKSHEET_CSV = RUNS / "transporter_negative_control_operator_worksheet_current.csv"
DEFAULT_INTAKE_CSV = RUNS / "transporter_negative_control_operator_intake_export_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_negative_control_operator_worksheet_current.md"

NEGATIVE_ITEM_IDS = (
    "AQP1.core_non_binder_01",
    "AQP1.core_non_binder_02",
    "AQP1.core_non_binder_03",
    "GLUT1_4PYP.core_non_binder_01",
    "GLUT1_4PYP.core_non_binder_02",
    "GLUT1_4PYP.core_non_binder_03",
)

FIELD_SPECS: list[dict[str, str]] = [
    {
        "field_name": "replacement_reference_binding_kcal_mol",
        "required_for_apply": "yes",
        "operator_action": "exact inactive/non-binder quantitative kcal from primary source; weak binders are not negatives",
        "valid_example": "-4.2",
    },
    {
        "field_name": "negative_reference_binding_kcal_mol",
        "required_for_apply": "yes",
        "operator_action": "mirror replacement kcal or KEEP_BLOCKED until evidence is verified",
        "valid_example": "-4.2",
    },
    {
        "field_name": "manual_ligand_identity_confirmed",
        "required_for_apply": "yes",
        "operator_action": "true only after SMILES/ligand id matches primary source",
        "valid_example": "true",
    },
    {
        "field_name": "manual_scaffold_confirmed",
        "required_for_apply": "yes",
        "operator_action": "true only after scaffold class review",
        "valid_example": "true",
    },
    {
        "field_name": "manual_source_provenance_confirmed",
        "required_for_apply": "yes",
        "operator_action": "true only after PMID/DOI/CHEMBL provenance review",
        "valid_example": "true",
    },
    {
        "field_name": "manual_split_meta_sync_confirmed",
        "required_for_apply": "yes",
        "operator_action": "true only after split/meta alignment review",
        "valid_example": "true",
    },
    {
        "field_name": "review_decision",
        "required_for_apply": "yes",
        "operator_action": "APPROVE_FOR_DRAFT only when all quantitative + manual gates pass; else KEEP_BLOCKED",
        "valid_example": "APPROVE_FOR_DRAFT",
    },
    {
        "field_name": "authoritative_apply_requested",
        "required_for_apply": "no",
        "operator_action": "true only after draft approval and scope chain rerun",
        "valid_example": "false",
    },
    {
        "field_name": "reviewer_notes",
        "required_for_apply": "yes",
        "operator_action": "cite primary source locator and assay type; no placeholder markers",
        "valid_example": "PMID 12345678: exact inactive Kd for human target pair",
    },
]

INTAKE_EXPORT_COLUMNS = (
    "review_row_id",
    "item_id",
    "target_id",
    "packet_step",
    "replacement_ligand_id",
    "replacement_smiles",
    "replacement_scaffold",
    "replacement_source",
    "replacement_reference_binding_kcal_mol",
    "negative_reference_binding_kcal_mol",
    "manual_ligand_identity_confirmed",
    "manual_scaffold_confirmed",
    "manual_source_provenance_confirmed",
    "manual_split_meta_sync_confirmed",
    "review_decision",
    "authoritative_apply_requested",
    "reviewer_notes",
)

OPERATOR_PLACEHOLDER_MARKERS = (
    "OPERATOR_FILL",
    "KEEP_BLOCKED",
)

KCAL_FIELD_NAMES = frozenset(
    {
        "replacement_reference_binding_kcal_mol",
        "negative_reference_binding_kcal_mol",
    }
)

CLAIM_BOUNDARY = (
    "Transporter negative-control operator worksheet only; exports the six scope-deferred "
    "core_non_binder slots into a field checklist and paste-back intake CSV. It does not "
    "authoritatively apply rows or mutate external state."
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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_intake_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _is_operator_placeholder(value: Any) -> bool:
    text = _text(value)
    if not text:
        return True
    if text.startswith("OPERATOR_FILL"):
        return True
    return any(marker in text for marker in OPERATOR_PLACEHOLDER_MARKERS)


def _has_primary_source_locator(notes: Any) -> bool:
    text = _text(notes)
    if not text:
        return False
    upper = text.upper()
    return any(token in upper for token in ("PMID", "DOI", "HTTP://", "HTTPS://", "CHEMBL"))


def _is_negative_control_row(row: dict[str, Any]) -> bool:
    item_id = _text(row.get("item_id"))
    if item_id in NEGATIVE_ITEM_IDS:
        return True
    packet_step = _text(row.get("packet_step"))
    return packet_step.startswith("core_non_binder") and row.get("negative_quantitative_value_required") is True


def _field_status(field_name: str, value: Any, *, reviewer_notes: str = "") -> str:
    text = _text(value)
    if field_name in KCAL_FIELD_NAMES:
        if not text or text == "KEEP_BLOCKED":
            if _has_primary_source_locator(reviewer_notes):
                return "documented_blocked"
            return "operator_fill_pending"
        if _is_operator_placeholder(text):
            return "operator_fill_pending"
        try:
            float(text)
        except ValueError:
            return "invalid_or_blocked"
        return "filled"
    if not text:
        return "operator_fill_pending"
    if _is_operator_placeholder(text):
        return "operator_fill_pending"
    if field_name in {"manual_ligand_identity_confirmed", "manual_scaffold_confirmed", "manual_source_provenance_confirmed", "manual_split_meta_sync_confirmed"}:
        return "ready" if text.lower() == "true" else "operator_fill_pending"
    if field_name == "review_decision":
        return "ready" if text.upper() in {"APPROVE_FOR_DRAFT", "APPROVE"} else "keep_blocked"
    return "filled"


def _should_preserve_intake_value(field_name: str, value: str, *, reviewer_notes: str) -> bool:
    text = _text(value)
    if not text:
        return False
    if field_name in KCAL_FIELD_NAMES and text == "KEEP_BLOCKED":
        return _has_primary_source_locator(reviewer_notes)
    return not _is_operator_placeholder(text)


def merge_intake_export_with_template_rows(
    template_rows: list[dict[str, Any]],
    intake_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], int]:
    intake_by_item_id = {_text(row.get("item_id")): row for row in intake_rows if _text(row.get("item_id"))}
    merged_rows: list[dict[str, Any]] = []
    preserved_row_count = 0
    for template_row in template_rows:
        merged = dict(template_row)
        intake = intake_by_item_id.get(_text(template_row.get("item_id")))
        if intake:
            notes = _text(intake.get("reviewer_notes"))
            row_preserved = False
            for column in INTAKE_EXPORT_COLUMNS:
                if column == "review_row_id":
                    continue
                intake_value = _text(intake.get(column))
                if _should_preserve_intake_value(column, intake_value, reviewer_notes=notes):
                    if _text(merged.get(column)) != intake_value:
                        row_preserved = True
                    merged[column] = intake_value
            if row_preserved:
                preserved_row_count += 1
        merged_rows.append(merged)
    return merged_rows, preserved_row_count


def build_worksheet_rows(negative_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    worksheet_rows: list[dict[str, str]] = []
    for template_row in negative_rows:
        item_id = _text(template_row.get("item_id"))
        reviewer_notes = _text(template_row.get("reviewer_notes"))
        for spec in FIELD_SPECS:
            field_name = spec["field_name"]
            current_value = _text(template_row.get(field_name))
            worksheet_rows.append(
                {
                    "item_id": item_id,
                    "target_id": _text(template_row.get("target_id")),
                    "packet_step": _text(template_row.get("packet_step")),
                    "review_row_id": _text(template_row.get("review_row_id")),
                    "replacement_ligand_id": _text(template_row.get("replacement_ligand_id")),
                    "field_name": field_name,
                    "required_for_apply": spec["required_for_apply"],
                    "current_value": current_value,
                    "field_status": _field_status(field_name, current_value, reviewer_notes=reviewer_notes),
                    "operator_action": spec["operator_action"],
                    "valid_example": spec["valid_example"],
                }
            )
    return worksheet_rows


def build_intake_export_rows(negative_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    export_rows: list[dict[str, str]] = []
    for template_row in negative_rows:
        export_rows.append({column: _text(template_row.get(column)) for column in INTAKE_EXPORT_COLUMNS})
    return export_rows


def build_payload(
    template_packet: dict[str, Any],
    *,
    intake_export_csv: str | Path = DEFAULT_INTAKE_CSV,
) -> dict[str, Any]:
    all_rows = [dict(row) for row in template_packet.get("rows", []) or [] if isinstance(row, dict)]
    negative_rows = [row for row in all_rows if _is_negative_control_row(row)]
    negative_rows.sort(key=lambda row: (_text(row.get("target_id")), _text(row.get("item_id"))))
    intake_rows = _read_intake_csv(intake_export_csv)
    negative_rows, intake_preserved_row_count = merge_intake_export_with_template_rows(negative_rows, intake_rows)
    worksheet_rows = build_worksheet_rows(negative_rows)
    intake_export_rows = build_intake_export_rows(negative_rows)
    pending_fields = sum(1 for row in worksheet_rows if row["field_status"] == "operator_fill_pending")
    documented_blocked_fields = sum(1 for row in worksheet_rows if row["field_status"] == "documented_blocked")
    ready_fields = sum(1 for row in worksheet_rows if row["field_status"] in {"filled", "ready"})
    summary = {
        "packet_type": "transporter_negative_control_operator_worksheet",
        "status": (
            "transporter_negative_control_operator_worksheet_ready"
            if len(negative_rows) == len(NEGATIVE_ITEM_IDS)
            else "blocked_transporter_negative_control_operator_worksheet"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "expected_negative_control_count": len(NEGATIVE_ITEM_IDS),
        "negative_control_row_count": len(negative_rows),
        "worksheet_field_row_count": len(worksheet_rows),
        "operator_fill_pending_field_count": pending_fields,
        "documented_blocked_field_count": documented_blocked_fields,
        "ready_field_count": ready_fields,
        "intake_preserved_row_count": intake_preserved_row_count,
        "worksheet_csv": str(DEFAULT_WORKSHEET_CSV),
        "intake_export_csv": str(intake_export_csv),
        "template_json": str(DEFAULT_TEMPLATE_JSON),
        "intake_merge_builder": "tools/build_transporter_negative_control_intake_merge.py",
        "next_required_step": (
            "Fill transporter_negative_control_operator_intake_export_current.csv, run "
            "tools/build_transporter_negative_control_intake_merge.py --write-template, then rerun "
            "tools/build_product_scope_optional_lane_refresh_chain.py."
            if negative_rows
            else "Regenerate transporter manual review intake template before building negative-control worksheet."
        ),
    }
    return {
        "summary": summary,
        "negative_control_rows": negative_rows,
        "worksheet_rows": worksheet_rows,
        "intake_export_rows": intake_export_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Transporter Negative Control Operator Worksheet (6 slots)",
        "",
        f"- status: `{summary['status']}`",
        f"- negative_control_row_count: `{summary['negative_control_row_count']}`",
        f"- operator_fill_pending_field_count: `{summary['operator_fill_pending_field_count']}`",
        f"- documented_blocked_field_count: `{summary['documented_blocked_field_count']}`",
        f"- intake_preserved_row_count: `{summary['intake_preserved_row_count']}`",
        "",
        "## Slots",
        "",
        "| item_id | target | ligand_id | packet_step |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["negative_control_rows"]:
        lines.append(
            f"| `{row.get('item_id', '')}` | `{row.get('target_id', '')}` | "
            f"`{row.get('replacement_ligand_id', '')}` | `{row.get('packet_step', '')}` |"
        )
    lines.extend(
        [
            "",
            "## Field Worksheet",
            "",
            "| item_id | field | status | current_value | operator_action |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["worksheet_rows"]:
        lines.append(
            f"| `{row['item_id']}` | `{row['field_name']}` | `{row['field_status']}` | "
            f"`{row['current_value']}` | {row['operator_action']} |"
        )
    lines.extend(
        [
            "",
            "## Paste-back",
            "",
            f"- intake_export_csv: `{summary['intake_export_csv']}`",
            f"- template_json: `{summary['template_json']}`",
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build transporter negative-control operator worksheet (6 slots).")
    parser.add_argument("--template-json", default=str(DEFAULT_TEMPLATE_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--worksheet-csv", default=str(DEFAULT_WORKSHEET_CSV))
    parser.add_argument("--intake-export-csv", default=str(DEFAULT_INTAKE_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_read_json(args.template_json), intake_export_csv=args.intake_export_csv)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.worksheet_csv), payload["worksheet_rows"])
    write_csv_rows(_resolve(args.intake_export_csv), payload["intake_export_rows"])
    _write_markdown(_resolve(args.out_md), payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
