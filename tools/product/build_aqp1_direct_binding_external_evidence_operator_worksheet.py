#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_aqp1_direct_binding_external_evidence_intake import (
    APPROVE_DECISIONS,
    KEEP_BLOCKED,
    OPERATOR_FILL,
    build_payload as build_intake_payload,
)
from tools.product.build_aqp1_direct_binding_external_evidence_operator_fill_guide import (
    build_payload as build_fill_guide_payload,
)

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_PROCUREMENT_JSON = RUNS / "aqp1_direct_binding_procurement_packet_current.json"
DEFAULT_OPERATOR_CANDIDATE_JSON = RUNS / "aqp1_operator_validation_candidate_packet_current.json"
DEFAULT_FUNCTIONAL_JSON = RUNS / "aqp1_functional_kcal_surrogate_packet_current.json"
DEFAULT_SUPPLEMENT_CSV = RUNS / "aqp1_direct_binding_external_evidence_intake_supplement_current.csv"
DEFAULT_OUT_JSON = RUNS / "aqp1_direct_binding_external_evidence_operator_worksheet_current.json"
DEFAULT_OUT_CSV = RUNS / "aqp1_direct_binding_external_evidence_operator_worksheet_current.csv"
DEFAULT_OUT_MD = RUNS / "aqp1_direct_binding_external_evidence_operator_worksheet_current.md"

FIELD_SPECS: list[dict[str, str]] = [
    {
        "field_name": "review_row_id",
        "required_for_apply": "yes",
        "operator_action": "keep stable row id from fill guide",
        "valid_example": "aqp1_external_direct_binding_core_binder_01",
    },
    {
        "field_name": "packet_step",
        "required_for_apply": "yes",
        "operator_action": "must match workbook packet step",
        "valid_example": "core_binder_01",
    },
    {
        "field_name": "target_uniprot",
        "required_for_apply": "yes",
        "operator_action": "confirm exact human AQP1 accession",
        "valid_example": "P29972",
    },
    {
        "field_name": "replacement_ligand_id",
        "required_for_apply": "yes",
        "operator_action": "set exact workbook ligand id before APPROVE",
        "valid_example": "aqp1_bacopaside_ii_review_seed",
    },
    {
        "field_name": "replacement_reference_binding_kcal_mol",
        "required_for_apply": "yes",
        "operator_action": "numeric direct-binding kcal only; never copy functional surrogate",
        "valid_example": "-8.42",
    },
    {
        "field_name": "direct_binding_method",
        "required_for_apply": "yes",
        "operator_action": "record direct assay method from primary source",
        "valid_example": "SPR",
    },
    {
        "field_name": "standard_type",
        "required_for_apply": "yes",
        "operator_action": "Kd or Ki only for claim-safe direct binding",
        "valid_example": "Ki",
    },
    {
        "field_name": "standard_value_nM",
        "required_for_apply": "yes",
        "operator_action": "numeric nM from primary source",
        "valid_example": "1200",
    },
    {
        "field_name": "source_locator_or_raw_report",
        "required_for_apply": "yes",
        "operator_action": "PMID/DOI or primary report locator",
        "valid_example": "https://doi.org/10.1000/example",
    },
    {
        "field_name": "target_match_confirmed",
        "required_for_apply": "yes",
        "operator_action": "set true only after exact human AQP1 confirmation",
        "valid_example": "true",
    },
    {
        "field_name": "assay_is_direct_binding",
        "required_for_apply": "yes",
        "operator_action": "set true only for direct Kd/Ki/SPR/ITC/competition Ki evidence",
        "valid_example": "true",
    },
    {
        "field_name": "data_validity_accepted",
        "required_for_apply": "yes",
        "operator_action": "set true only after validity review",
        "valid_example": "true",
    },
    {
        "field_name": "operator_claim_safe_decision",
        "required_for_apply": "yes",
        "operator_action": "APPROVE_CLAIM_SAFE or KEEP_BLOCKED",
        "valid_example": "APPROVE_CLAIM_SAFE",
    },
    {
        "field_name": "review_decision",
        "required_for_apply": "yes",
        "operator_action": "mirror operator decision; do not invent APPROVE without evidence",
        "valid_example": "APPROVE",
    },
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    import csv

    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _is_operator_placeholder(value: Any) -> bool:
    text = _text(value)
    return not text or text.startswith(OPERATOR_FILL) or text == KEEP_BLOCKED


def _field_status(field_name: str, value: Any, intake_status: str) -> str:
    if intake_status == "claim_safe_approved":
        return "ready"
    if field_name == "functional_surrogate_kcal_mol":
        return "review_only"
    if field_name in {"reviewer_notes", "required_evidence_mode", "candidate_name", "target_id"}:
        return "informational"
    if _is_operator_placeholder(value):
        return "operator_fill_pending"
    if field_name == "operator_claim_safe_decision" and _text(value).upper() not in APPROVE_DECISIONS:
        return "keep_blocked"
    if field_name == "replacement_reference_binding_kcal_mol":
        try:
            float(_text(value))
        except ValueError:
            return "invalid_or_blocked"
    return "filled"


def build_worksheet_rows(
    *,
    fill_guide_rows: list[dict[str, str]],
    supplement_rows: list[dict[str, str]],
    intake_payload: dict[str, Any],
) -> list[dict[str, str]]:
    supplement_by_id = {_text(row.get("review_row_id")): row for row in supplement_rows if _text(row.get("review_row_id"))}
    intake_by_id = {
        _text(row.get("review_row_id")): row
        for row in intake_payload.get("rows", []) or []
        if isinstance(row, dict) and _text(row.get("review_row_id"))
    }
    worksheet_rows: list[dict[str, str]] = []
    for guide_row in fill_guide_rows:
        review_row_id = _text(guide_row.get("review_row_id"))
        live_row = supplement_by_id.get(review_row_id, {})
        intake_row = intake_by_id.get(review_row_id, {})
        intake_status = _text(intake_row.get("intake_status")) or "missing_live_row"
        for spec in FIELD_SPECS:
            field_name = spec["field_name"]
            current_value = _text(live_row.get(field_name)) or _text(guide_row.get(field_name))
            worksheet_rows.append(
                {
                    "review_row_id": review_row_id,
                    "candidate_name": _text(guide_row.get("candidate_name")),
                    "field_name": field_name,
                    "required_for_apply": spec["required_for_apply"],
                    "current_value": current_value,
                    "field_status": _field_status(field_name, current_value, intake_status),
                    "operator_action": spec["operator_action"],
                    "valid_example": spec["valid_example"],
                    "intake_status": intake_status,
                }
            )
    return worksheet_rows


def build_payload(
    *,
    procurement_packet: dict[str, Any],
    operator_candidate_packet: dict[str, Any],
    functional_packet: dict[str, Any],
    supplement_rows: list[dict[str, str]],
) -> dict[str, Any]:
    fill_guide = build_fill_guide_payload(
        procurement_packet=procurement_packet,
        operator_candidate_packet=operator_candidate_packet,
        functional_packet=functional_packet,
    )
    intake_payload = build_intake_payload(supplement_rows if supplement_rows else fill_guide["rows"])
    worksheet_rows = build_worksheet_rows(
        fill_guide_rows=[dict(row) for row in fill_guide["rows"]],
        supplement_rows=supplement_rows,
        intake_payload=intake_payload,
    )
    pending_fields = sum(1 for row in worksheet_rows if row["field_status"] == "operator_fill_pending")
    ready_fields = sum(1 for row in worksheet_rows if row["field_status"] == "ready")
    summary = {
        "packet_type": "aqp1_direct_binding_external_evidence_operator_worksheet",
        "status": (
            "aqp1_direct_binding_external_evidence_operator_worksheet_ready"
            if fill_guide["rows"]
            else "blocked_aqp1_direct_binding_external_evidence_operator_worksheet"
        ),
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "fill_guide_row_count": len(fill_guide["rows"]),
        "live_supplement_row_count": len(supplement_rows),
        "worksheet_field_row_count": len(worksheet_rows),
        "operator_fill_pending_field_count": pending_fields,
        "ready_field_count": ready_fields,
        "claim_safe_approved_count": intake_payload["summary"]["claim_safe_approved_count"],
        "operator_fill_pending_count": intake_payload["summary"]["operator_fill_pending_count"],
        "validation_error_count": intake_payload["summary"]["validation_error_count"],
        "supplement_csv": str(DEFAULT_SUPPLEMENT_CSV),
        "supplement_example_csv": fill_guide["summary"].get("supplement_example_csv", ""),
        "next_required_step": (
            "Copy the fill-guide rows into the live supplement CSV, complete every operator_fill_pending field "
            "using primary-source direct-binding evidence, set operator_claim_safe_decision=APPROVE_CLAIM_SAFE only "
            "when all validity gates pass, then rerun build_aqp1_direct_binding_external_evidence_intake.py."
            if pending_fields
            else intake_payload["summary"]["next_required_step"]
        ),
    }
    return {
        "summary": summary,
        "fill_guide_rows": fill_guide["rows"],
        "supplement_rows": supplement_rows,
        "intake_summary": intake_payload["summary"],
        "validation_errors": intake_payload.get("validation_errors", []),
        "rows": worksheet_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# AQP1 Direct Binding External Evidence Operator Worksheet",
        "",
        f"- status: `{summary['status']}`",
        f"- fill_guide_row_count: `{summary['fill_guide_row_count']}`",
        f"- live_supplement_row_count: `{summary['live_supplement_row_count']}`",
        f"- operator_fill_pending_field_count: `{summary['operator_fill_pending_field_count']}`",
        f"- claim_safe_approved_count: `{summary['claim_safe_approved_count']}`",
        f"- validation_error_count: `{summary['validation_error_count']}`",
        "",
        "## Live Supplement",
        "",
        f"- supplement_csv: `{summary['supplement_csv']}`",
        f"- supplement_example_csv: `{summary.get('supplement_example_csv', '')}`",
        "",
        "## Field Worksheet",
        "",
        "| review_row_id | field | status | current_value | operator_action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['review_row_id']}` | `{row['field_name']}` | `{row['field_status']}` | "
            f"`{row['current_value']}` | {row['operator_action']} |"
        )
    if payload.get("validation_errors"):
        lines.extend(["", "## Intake Validation Errors", ""])
        for err in payload["validation_errors"]:
            lines.append(f"- {err}")
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AQP1 operator supplement worksheet with field-level intake validation.")
    parser.add_argument("--procurement-json", default=str(DEFAULT_PROCUREMENT_JSON))
    parser.add_argument("--operator-candidate-json", default=str(DEFAULT_OPERATOR_CANDIDATE_JSON))
    parser.add_argument("--functional-json", default=str(DEFAULT_FUNCTIONAL_JSON))
    parser.add_argument("--supplement-csv", default=str(DEFAULT_SUPPLEMENT_CSV))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    supplement_rows = _read_csv(args.supplement_csv)
    payload = build_payload(
        procurement_packet=_read_json(args.procurement_json),
        operator_candidate_packet=_read_json(args.operator_candidate_json),
        functional_packet=_read_json(args.functional_json),
        supplement_rows=supplement_rows,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(_resolve(args.out_md), payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
