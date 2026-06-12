#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_aqp1_direct_binding_external_evidence_operator_fill_guide import (
    build_payload as build_fill_guide_payload,
)
from tools.product.build_aqp1_direct_binding_external_evidence_operator_worksheet import (
    FIELD_SPECS,
    _field_status,
)

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_PROCUREMENT_JSON = RUNS / "aqp1_direct_binding_procurement_packet_current.json"
DEFAULT_OPERATOR_CANDIDATE_JSON = RUNS / "aqp1_operator_validation_candidate_packet_current.json"
DEFAULT_FUNCTIONAL_JSON = RUNS / "aqp1_functional_kcal_surrogate_packet_current.json"
DEFAULT_LIVE_SUPPLEMENT_CSV = RUNS / "aqp1_direct_binding_external_evidence_intake_supplement_current.csv"
DEFAULT_BLANK_CSV = RUNS / "aqp1_direct_binding_live_supplement_blank_current.csv"
DEFAULT_OUT_JSON = RUNS / "aqp1_direct_binding_live_supplement_blank_current.json"
DEFAULT_CHECKLIST_CSV = RUNS / "aqp1_direct_binding_live_supplement_field_checklist_current.csv"
DEFAULT_CHECKLIST_MD = RUNS / "aqp1_direct_binding_live_supplement_field_checklist_current.md"

CLAIM_BOUNDARY = (
    "AQP1 live supplement blank template and field checklist only; emits operator-fillable blank rows "
    "without illustrative claim-safe numbers. It does not approve evidence, apply workbook rows, or mutate "
    "external state beyond writing local operator intake artifacts."
)


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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_field_checklist_rows(blank_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    checklist_rows: list[dict[str, str]] = []
    for blank_row in blank_rows:
        review_row_id = _text(blank_row.get("review_row_id"))
        intake_status = "missing_live_row"
        for spec in FIELD_SPECS:
            field_name = spec["field_name"]
            current_value = _text(blank_row.get(field_name))
            checklist_rows.append(
                {
                    "review_row_id": review_row_id,
                    "candidate_name": _text(blank_row.get("candidate_name")),
                    "packet_step": _text(blank_row.get("packet_step")),
                    "field_name": field_name,
                    "required_for_apply": spec["required_for_apply"],
                    "current_value": current_value,
                    "field_status": _field_status(field_name, current_value, intake_status),
                    "operator_action": spec["operator_action"],
                    "valid_example": spec["valid_example"],
                }
            )
    return checklist_rows


def build_payload(
    *,
    procurement_packet: dict[str, Any],
    operator_candidate_packet: dict[str, Any],
    functional_packet: dict[str, Any],
) -> dict[str, Any]:
    fill_guide = build_fill_guide_payload(
        procurement_packet=procurement_packet,
        operator_candidate_packet=operator_candidate_packet,
        functional_packet=functional_packet,
    )
    blank_rows = [dict(row) for row in fill_guide.get("rows", []) or [] if isinstance(row, dict)]
    checklist_rows = build_field_checklist_rows(blank_rows)
    pending_fields = sum(1 for row in checklist_rows if row["field_status"] == "operator_fill_pending")
    summary = {
        "packet_type": "aqp1_direct_binding_live_supplement_blank",
        "status": (
            "aqp1_direct_binding_live_supplement_blank_ready"
            if blank_rows
            else "blocked_aqp1_direct_binding_live_supplement_blank"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "blank_row_count": len(blank_rows),
        "field_checklist_row_count": len(checklist_rows),
        "operator_fill_pending_field_count": pending_fields,
        "kcal_policy": fill_guide["summary"].get(
            "kcal_policy",
            "never_promote_functional_surrogate_to_replacement_reference_binding_kcal_mol",
        ),
        "blank_supplement_csv": str(DEFAULT_BLANK_CSV),
        "live_supplement_csv": str(DEFAULT_LIVE_SUPPLEMENT_CSV),
        "field_checklist_csv": str(DEFAULT_CHECKLIST_CSV),
        "supplement_example_csv": fill_guide["summary"].get("supplement_example_csv", ""),
        "next_required_step": (
            "Fill runs/aqp1_direct_binding_live_supplement_blank_current.csv using the field checklist, "
            "copy verified rows into runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv, "
            "then run tools/product/build_aqp1_direct_binding_external_evidence_one_shot_chain.py."
            if blank_rows
            else "Regenerate AQP1 procurement/fill-guide packets before building the blank live supplement."
        ),
    }
    return {
        "summary": summary,
        "blank_rows": blank_rows,
        "field_checklist_rows": checklist_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# AQP1 Live Supplement Blank + Field Checklist",
        "",
        f"- status: `{summary['status']}`",
        f"- blank_row_count: `{summary['blank_row_count']}`",
        f"- operator_fill_pending_field_count: `{summary['operator_fill_pending_field_count']}`",
        f"- kcal_policy: `{summary['kcal_policy']}`",
        "",
        "## Artifacts",
        "",
        f"- blank_supplement_csv: `{summary['blank_supplement_csv']}`",
        f"- live_supplement_csv: `{summary['live_supplement_csv']}`",
        f"- field_checklist_csv: `{summary['field_checklist_csv']}`",
        f"- supplement_example_csv: `{summary.get('supplement_example_csv', '')}` (illustrative only; do not copy numbers)",
        "",
        "## Priority Row",
        "",
        "| review_row_id | candidate | packet_step |",
        "| --- | --- | --- |",
    ]
    for row in payload["blank_rows"]:
        if _text(row.get("review_row_id")) == "aqp1_external_direct_binding_core_binder_01":
            lines.append(
                f"| `{row['review_row_id']}` | `{row.get('candidate_name', '')}` | `{row.get('packet_step', '')}` |"
            )
    lines.extend(
        [
            "",
            "## Field Checklist",
            "",
            "| review_row_id | field | status | current_value | operator_action |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["field_checklist_rows"]:
        lines.append(
            f"| `{row['review_row_id']}` | `{row['field_name']}` | `{row['field_status']}` | "
            f"`{row['current_value']}` | {row['operator_action']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build blank AQP1 live supplement CSV and operator field checklist (no illustrative claim-safe numbers)."
    )
    parser.add_argument("--procurement-json", default=str(DEFAULT_PROCUREMENT_JSON))
    parser.add_argument("--operator-candidate-json", default=str(DEFAULT_OPERATOR_CANDIDATE_JSON))
    parser.add_argument("--functional-json", default=str(DEFAULT_FUNCTIONAL_JSON))
    parser.add_argument("--blank-csv", default=str(DEFAULT_BLANK_CSV))
    parser.add_argument("--live-supplement-csv", default=str(DEFAULT_LIVE_SUPPLEMENT_CSV))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--checklist-csv", default=str(DEFAULT_CHECKLIST_CSV))
    parser.add_argument("--checklist-md", default=str(DEFAULT_CHECKLIST_MD))
    parser.add_argument(
        "--also-write-live-supplement",
        action="store_true",
        help="Also write blank rows to the live supplement CSV path (default: blank artifact only).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        procurement_packet=_read_json(args.procurement_json),
        operator_candidate_packet=_read_json(args.operator_candidate_json),
        functional_packet=_read_json(args.functional_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.blank_csv), payload["blank_rows"])
    write_csv_rows(_resolve(args.checklist_csv), payload["field_checklist_rows"])
    _write_markdown(_resolve(args.checklist_md), payload)
    if args.also_write_live_supplement:
        write_csv_rows(_resolve(args.live_supplement_csv), payload["blank_rows"])
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
