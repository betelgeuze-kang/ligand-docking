#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_PROCUREMENT_JSON = RUNS / "aqp1_direct_binding_procurement_packet_current.json"
DEFAULT_OPERATOR_CANDIDATE_JSON = RUNS / "aqp1_operator_validation_candidate_packet_current.json"
DEFAULT_FUNCTIONAL_JSON = RUNS / "aqp1_functional_kcal_surrogate_packet_current.json"
DEFAULT_OUT_JSON = RUNS / "aqp1_direct_binding_external_evidence_operator_fill_guide_current.json"
DEFAULT_OUT_CSV = RUNS / "aqp1_direct_binding_external_evidence_intake_supplement_current.csv"
DEFAULT_OUT_MD = RUNS / "aqp1_direct_binding_external_evidence_operator_fill_guide_current.md"
EXAMPLE_CSV = RUNS / "aqp1_direct_binding_external_evidence_intake_supplement_example_current.csv"
EXAMPLE_MD = RUNS / "aqp1_direct_binding_external_evidence_supplement_example_current.md"

OPERATOR_FILL = "OPERATOR_FILL"
KEEP_BLOCKED = "KEEP_BLOCKED"


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


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _functional_by_step(functional_packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("packet_step")): dict(row)
        for row in functional_packet.get("rows", []) or []
        if isinstance(row, dict) and _text(row.get("packet_step"))
    }


def build_intake_rows(
    *,
    procurement_rows: list[dict[str, Any]],
    operator_candidate_rows: list[dict[str, Any]],
    functional_by_step: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for action in procurement_rows:
        action_id = _text(action.get("action_id"))
        if action_id == "procure_aqp1_bacopaside_ii_direct_binding_measurement":
            functional = functional_by_step.get("core_binder_01", {})
            rows.append(
                {
                    "review_row_id": "aqp1_external_direct_binding_core_binder_01",
                    "packet_step": "core_binder_01",
                    "target_id": "AQP1",
                    "target_uniprot": "P29972",
                    "candidate_name": _text(action.get("ligand_identity")) or "bacopaside II",
                    "replacement_ligand_id": _text(functional.get("replacement_ligand_id")) or "aqp1_bacopaside_ii_review_seed",
                    "required_evidence_mode": "exact_human_aqp1_direct_binding_kd_or_ki",
                    "functional_surrogate_kcal_mol": _text(functional.get("functional_delta_g_surrogate_kcal_mol")),
                    "replacement_reference_binding_kcal_mol": KEEP_BLOCKED,
                    "direct_binding_method": f"{OPERATOR_FILL}_SPR_ITC_MST_or_validated_competition_Ki",
                    "standard_type": f"{OPERATOR_FILL}_Kd_or_Ki",
                    "standard_value_nM": f"{OPERATOR_FILL}_numeric",
                    "source_locator_or_raw_report": f"{OPERATOR_FILL}_PMID_DOI_or_primary_report",
                    "target_match_confirmed": "false",
                    "assay_is_direct_binding": "false",
                    "data_validity_accepted": "false",
                    "operator_claim_safe_decision": f"{OPERATOR_FILL}_APPROVE_CLAIM_SAFE_OR_KEEP_BLOCKED",
                    "review_decision": KEEP_BLOCKED,
                    "authoritative_apply_requested": "false",
                    "reviewer_notes": (
                        "Functional IC50-derived surrogate (-6.47 kcal) is review-only. "
                        "Fill direct-binding Kd/Ki with primary source only; otherwise KEEP_BLOCKED "
                        "and leave replacement_reference_binding_kcal_mol blank."
                    ),
                }
            )
        elif action_id == "reject_current_chembl20_candidate_for_claim_safe_apply":
            candidate = operator_candidate_rows[0] if operator_candidate_rows else {}
            rows.append(
                {
                    "review_row_id": "aqp1_operator_validation_chembl20_acetazolamide",
                    "packet_step": "core_binder_01",
                    "target_id": "AQP1",
                    "target_uniprot": "P29972",
                    "candidate_name": _text(action.get("ligand_identity")) or "acetazolamide",
                    "replacement_ligand_id": _text(candidate.get("candidate_ligand_external_identifier")) or "CHEMBL20",
                    "required_evidence_mode": "operator_reject_or_upgrade_chembl_direct_like_candidate",
                    "functional_surrogate_kcal_mol": "",
                    "replacement_reference_binding_kcal_mol": KEEP_BLOCKED,
                    "direct_binding_method": f"{OPERATOR_FILL}_assay_origin_and_validity_review",
                    "standard_type": _text(candidate.get("candidate_standard_type")) or "Kd",
                    "standard_value_nM": _text(candidate.get("candidate_standard_value_nM")) or "174000.0",
                    "source_locator_or_raw_report": _text(candidate.get("candidate_source_locator")),
                    "target_match_confirmed": "false",
                    "assay_is_direct_binding": "false",
                    "data_validity_accepted": "false",
                    "operator_claim_safe_decision": "KEEP_BLOCKED",
                    "review_decision": KEEP_BLOCKED,
                    "authoritative_apply_requested": "false",
                    "reviewer_notes": (
                        "Default recommendation: KEEP_BLOCKED for CHEMBL20 acetazolamide "
                        "(assay origin unknown, validity out of range). Only upgrade if operator "
                        "confirms exact human AQP1 direct-binding provenance."
                    ),
                }
            )
        elif action_id == "or_curate_claim_safe_replacement_aqp1_blocker":
            rows.append(
                {
                    "review_row_id": "aqp1_external_replacement_blocker_curation",
                    "packet_step": "core_binder_01",
                    "target_id": "AQP1",
                    "target_uniprot": "P29972",
                    "candidate_name": f"{OPERATOR_FILL}_replacement_ligand_name",
                    "replacement_ligand_id": f"{OPERATOR_FILL}_replacement_ligand_id",
                    "required_evidence_mode": "claim_safe_replacement_aqp1_binder_or_blocker",
                    "functional_surrogate_kcal_mol": "",
                    "replacement_reference_binding_kcal_mol": KEEP_BLOCKED,
                    "direct_binding_method": f"{OPERATOR_FILL}_direct_binding_method",
                    "standard_type": f"{OPERATOR_FILL}_Kd_or_Ki",
                    "standard_value_nM": f"{OPERATOR_FILL}_numeric",
                    "source_locator_or_raw_report": f"{OPERATOR_FILL}_primary_source_locator",
                    "target_match_confirmed": "false",
                    "assay_is_direct_binding": "false",
                    "data_validity_accepted": "false",
                    "operator_claim_safe_decision": f"{OPERATOR_FILL}_APPROVE_CLAIM_SAFE_OR_KEEP_BLOCKED",
                    "review_decision": KEEP_BLOCKED,
                    "authoritative_apply_requested": "false",
                    "reviewer_notes": (
                        "Optional alternate path if bacopaside II direct binding cannot be sourced. "
                        "Must be exact human AQP1 (P29972) direct quantitative binding before any apply."
                    ),
                }
            )
    return rows


def build_payload(
    *,
    procurement_packet: dict[str, Any],
    operator_candidate_packet: dict[str, Any],
    functional_packet: dict[str, Any],
) -> dict[str, Any]:
    procurement_summary = procurement_packet.get("summary", {}) if isinstance(procurement_packet.get("summary"), dict) else {}
    intake_rows = build_intake_rows(
        procurement_rows=_rows(procurement_packet),
        operator_candidate_rows=_rows(operator_candidate_packet),
        functional_by_step=_functional_by_step(functional_packet),
    )
    external_required = procurement_summary.get("external_primary_evidence_required") is True
    summary = {
        "packet_type": "aqp1_direct_binding_external_evidence_operator_fill_guide",
        "status": (
            "aqp1_direct_binding_external_evidence_operator_fill_guide_ready"
            if intake_rows and external_required
            else "blocked_aqp1_direct_binding_external_evidence_operator_fill_guide"
        ),
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "external_primary_evidence_required": external_required,
        "direct_binding_gap_open": procurement_summary.get("direct_binding_gap_open") is True,
        "functional_surrogate_row_count": len(_functional_by_step(functional_packet)),
        "operator_fill_row_count": len(intake_rows),
        "operator_fill_policy": "exact_direct_binding_or_KEEP_BLOCKED",
        "kcal_policy": "never_promote_functional_surrogate_to_replacement_reference_binding_kcal_mol",
        "first_required_external_action_id": _text(procurement_summary.get("first_required_external_action_id")),
        "supplement_example_csv": str(EXAMPLE_CSV),
        "supplement_example_md": str(EXAMPLE_MD),
        "operator_worksheet_json": str(RUNS / "aqp1_direct_binding_external_evidence_operator_worksheet_current.json"),
        "next_required_step": (
            "Review runs/aqp1_direct_binding_external_evidence_intake_supplement_example_current.md, run "
            "build_aqp1_direct_binding_external_evidence_operator_worksheet.py for the field checklist, copy verified "
            "rows into the live supplement CSV, then run build_aqp1_direct_binding_external_evidence_intake.py, "
            "rebuild the AQP1 workbook overlay, apply with apply_aqp1_ready_workbook_rows.py, and rerun transporter "
            "P0 / scope gates."
            if intake_rows
            else "Regenerate AQP1 direct-binding procurement packet before building operator fill guide."
        ),
    }
    return {"summary": summary, "rows": intake_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Direct Binding External Evidence Operator Fill Guide",
        "",
        f"- status: `{s['status']}`",
        f"- external_primary_evidence_required: `{s['external_primary_evidence_required']}`",
        f"- operator_fill_row_count: `{s['operator_fill_row_count']}`",
        f"- first_required_external_action_id: `{s['first_required_external_action_id']}`",
        "",
        "## Rows",
        "",
        "| review_row_id | packet_step | candidate | required_evidence_mode | review_decision |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['review_row_id']}` | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['required_evidence_mode']}` | `{row['review_decision']}` |"
        )
    lines.extend(
        [
            "",
            "## Operator Example",
            "",
            f"- example_csv: `{s.get('supplement_example_csv', EXAMPLE_CSV)}`",
            f"- example_md: `{s.get('supplement_example_md', EXAMPLE_MD)}`",
            "- Generate with: `python3 tools/product/build_aqp1_direct_binding_external_evidence_supplement_example.py`",
            "",
            "## Next Step",
            "",
            f"- {s['next_required_step']}",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AQP1 external direct-binding operator fill guide.")
    parser.add_argument("--procurement-json", default=str(DEFAULT_PROCUREMENT_JSON))
    parser.add_argument("--operator-candidate-json", default=str(DEFAULT_OPERATOR_CANDIDATE_JSON))
    parser.add_argument("--functional-json", default=str(DEFAULT_FUNCTIONAL_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        procurement_packet=_read_json(args.procurement_json),
        operator_candidate_packet=_read_json(args.operator_candidate_json),
        functional_packet=_read_json(args.functional_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
