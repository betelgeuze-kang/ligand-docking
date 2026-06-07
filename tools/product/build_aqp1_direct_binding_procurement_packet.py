#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRIAGE_JSON = "runs/aqp1_binding_source_modality_triage_current.json"
DEFAULT_OPERATOR_CANDIDATE_JSON = "runs/aqp1_operator_validation_candidate_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_direct_binding_procurement_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_direct_binding_procurement_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_direct_binding_procurement_packet_current.md"

CLAIM_BOUNDARY = (
    "AQP1 direct-binding procurement packet only; records why current public evidence cannot be promoted and defines "
    "the exact external evidence contract needed to unblock transporter scope. It does not approve claim-safe kcal, "
    "edit reference CSVs, run assays, run docking, promote scope, or mutate external state."
)

ACCEPTANCE_FIELDS = [
    "target_id",
    "target_uniprot",
    "ligand_identity",
    "direct_binding_method",
    "standard_type",
    "standard_value_nM",
    "reference_binding_kcal_mol",
    "source_locator_or_raw_report",
    "target_match_confirmed",
    "assay_is_direct_binding",
    "data_validity_accepted",
    "operator_claim_safe_decision",
]

POST_RETURN_VALIDATION_COMMANDS = [
    "python3 tools/product/build_aqp1_binding_source_modality_triage.py",
    "python3 tools/product/build_aqp1_operator_validation_candidate_packet.py",
    "python3 tools/product/build_aqp1_direct_binding_procurement_packet.py",
    "python3 tools/build_transporter_p0_evidence_acquisition_packet.py",
    "python3 tools/build_product_scope_breadth_contract.py",
    "python3 tools/build_product_goal_completion_audit.py",
]


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
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _candidate(operator_packet: dict[str, Any]) -> dict[str, Any]:
    rows = _rows(operator_packet)
    return rows[0] if rows else {}


def build_payload(*, triage_packet: dict[str, Any], operator_candidate_packet: dict[str, Any]) -> dict[str, Any]:
    triage = _summary(triage_packet)
    operator_summary = _summary(operator_candidate_packet)
    candidate = _candidate(operator_candidate_packet)
    candidate_claim_safe = candidate.get("candidate_claim_safe_ready") is True
    current_claim_safe_count = int(triage.get("claim_safe_binding_kcal_ready_count") or 0)
    direct_count = int(triage.get("direct_experimental_binding_row_count") or 0)
    target_id = _text(triage.get("target_id")) or "AQP1"
    target_uniprot = _text(triage.get("target_uniprot")) or "P29972"
    candidate_ligand = _text(candidate.get("candidate_ligand_name")) or _text(
        operator_summary.get("first_candidate_ligand_name")
    )
    candidate_external_id = _text(candidate.get("candidate_ligand_external_identifier")) or _text(
        operator_summary.get("first_candidate_ligand_external_identifier")
    )
    candidate_blocker = _text(candidate.get("candidate_blocker")) or _text(
        operator_summary.get("first_candidate_blocker")
    )
    rows = [
        {
            "action_id": "reject_current_chembl20_candidate_for_claim_safe_apply",
            "action_type": "source_audit",
            "target_id": target_id,
            "target_uniprot": target_uniprot,
            "ligand_identity": candidate_ligand,
            "ligand_external_identifier": candidate_external_id,
            "source_locator_or_raw_report": _text(candidate.get("candidate_source_locator"))
            or _text(operator_summary.get("first_candidate_source_locator")),
            "observed_value": _text(candidate.get("candidate_reference_binding_kcal_mol"))
            or _text(operator_summary.get("first_candidate_reference_binding_kcal_mol")),
            "observed_units": "kcal/mol derived from reported Kd",
            "evidence_verdict": "keep_blocked",
            "blocker": candidate_blocker,
            "claim_safe_evidence_currently_available": candidate_claim_safe,
            "authoritative_apply_allowed": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        },
        {
            "action_id": "procure_aqp1_bacopaside_ii_direct_binding_measurement",
            "action_type": "external_primary_evidence_request",
            "target_id": target_id,
            "target_uniprot": target_uniprot,
            "ligand_identity": _text(triage.get("candidate_name")) or "bacopaside II",
            "ligand_external_identifier": _text(triage.get("bacopaside_ii_chembl_id")) or "CHEMBL390758",
            "source_locator_or_raw_report": "operator_return_raw_report_or_primary_literature_locator",
            "observed_value": "",
            "observed_units": "nM Kd_or_Ki plus kcal/mol conversion",
            "evidence_verdict": "external_evidence_required",
            "blocker": "no_public_direct_experimental_or_claim_safe_binding_kcal_for_aqp1_bacopaside_ii",
            "claim_safe_evidence_currently_available": False,
            "authoritative_apply_allowed": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        },
        {
            "action_id": "or_curate_claim_safe_replacement_aqp1_blocker",
            "action_type": "replacement_reference_evidence_request",
            "target_id": target_id,
            "target_uniprot": target_uniprot,
            "ligand_identity": "operator_selected_AQP1_replacement_blocker",
            "ligand_external_identifier": "operator_fill",
            "source_locator_or_raw_report": "primary_source_or_public_db_activity_locator",
            "observed_value": "",
            "observed_units": "nM Kd_or_Ki plus kcal/mol conversion",
            "evidence_verdict": "external_evidence_required",
            "blocker": "replacement_must_be_exact_human_aqp1_direct_binding_or_claim_safe_quantitative",
            "claim_safe_evidence_currently_available": False,
            "authoritative_apply_allowed": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        },
    ]
    procurement_ready = bool(operator_summary.get("packet_ready") is True and target_id and target_uniprot)
    direct_binding_gap_open = bool(current_claim_safe_count == 0 and not candidate_claim_safe)
    summary = {
        "packet_type": "aqp1_direct_binding_procurement_packet",
        "status": (
            "aqp1_direct_binding_procurement_packet_ready"
            if procurement_ready
            else "blocked_aqp1_direct_binding_procurement_packet"
        ),
        "procurement_packet_ready": procurement_ready,
        "target_id": target_id,
        "target_uniprot": target_uniprot,
        "current_direct_experimental_binding_row_count": direct_count,
        "current_claim_safe_binding_kcal_ready_count": current_claim_safe_count,
        "direct_binding_gap_open": direct_binding_gap_open,
        "public_direct_binding_recheck_ready": bool(triage.get("public_direct_binding_recheck_ready") is True),
        "public_direct_binding_recheck_result": _text(triage.get("public_direct_binding_recheck_result")),
        "current_operator_candidate_id": _text(candidate.get("candidate_id"))
        or _text(operator_summary.get("first_candidate_id")),
        "current_operator_candidate_ligand_external_identifier": candidate_external_id,
        "current_operator_candidate_reference_binding_kcal_mol": _text(
            candidate.get("candidate_reference_binding_kcal_mol")
        )
        or _text(operator_summary.get("first_candidate_reference_binding_kcal_mol")),
        "current_operator_candidate_blocker": candidate_blocker,
        "current_operator_candidate_claim_safe_ready": candidate_claim_safe,
        "external_primary_evidence_required": direct_binding_gap_open,
        "accepted_direct_binding_methods": [
            "SPR equilibrium Kd",
            "ITC Kd",
            "MST Kd",
            "radioligand or validated competition Ki",
            "operator-verified primary literature direct Kd/Ki",
        ],
        "acceptance_fields": ACCEPTANCE_FIELDS,
        "acceptance_field_count": len(ACCEPTANCE_FIELDS),
        "minimum_acceptance_rule": (
            "target_uniprot=P29972; target organism Homo sapiens; assay_is_direct_binding=true; "
            "standard_type in Kd,Ki; standard_value_nM numeric; data_validity_accepted=true; "
            "operator_claim_safe_decision=approve_claim_safe"
        ),
        "first_required_external_action_id": "procure_aqp1_bacopaside_ii_direct_binding_measurement",
        "post_return_validation_commands": POST_RETURN_VALIDATION_COMMANDS,
        "post_return_validation_command_count": len(POST_RETURN_VALIDATION_COMMANDS),
        "claim_promotion_allowed": False,
        "authoritative_apply_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "next_required_step": (
            "Return exact human AQP1 direct-binding Kd/Ki evidence for bacopaside II, or curate a replacement AQP1 "
            "blocker with exact claim-safe direct quantitative binding; then rerun the AQP1 and scope breadth gates."
            if procurement_ready
            else "Regenerate the AQP1 triage and operator-validation candidate packet before procurement handoff."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    blockers = []
    if not procurement_ready:
        blockers.append({"code": "operator_candidate_packet_not_ready"})
    if direct_binding_gap_open:
        blockers.append({"code": "direct_binding_gap_open"})
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# AQP1 Direct Binding Procurement Packet",
        "",
        f"- status: `{s['status']}`",
        f"- procurement_packet_ready: `{s['procurement_packet_ready']}`",
        f"- direct_binding_gap_open: `{s['direct_binding_gap_open']}`",
        f"- current_operator_candidate: `{s['current_operator_candidate_ligand_external_identifier']}`",
        f"- current_operator_candidate_blocker: `{s['current_operator_candidate_blocker']}`",
        f"- first_required_external_action_id: `{s['first_required_external_action_id']}`",
        "",
        "## Acceptance Rule",
        "",
        s["minimum_acceptance_rule"],
        "",
        "## Actions",
        "",
        "| action_id | action_type | ligand | verdict | blocker |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['action_id']}` | `{row['action_type']}` | `{row['ligand_identity']}` | "
            f"`{row['evidence_verdict']}` | `{row['blocker']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 direct-binding procurement packet.")
    parser.add_argument("--triage-json", default=DEFAULT_TRIAGE_JSON)
    parser.add_argument("--operator-candidate-json", default=DEFAULT_OPERATOR_CANDIDATE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        triage_packet=_read_json(args.triage_json),
        operator_candidate_packet=_read_json(args.operator_candidate_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
