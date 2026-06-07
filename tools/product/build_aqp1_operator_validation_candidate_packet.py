#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_TRIAGE_JSON = "runs/aqp1_binding_source_modality_triage_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_operator_validation_candidate_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_operator_validation_candidate_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_operator_validation_candidate_packet_current.md"

CLAIM_BOUNDARY = (
    "AQP1 operator-validation candidate packet only; prepares the current direct-like public evidence candidate "
    "for human validation. It does not approve claim-safe binding kcal, promote transporter scope, edit reference "
    "CSVs, run docking, run experiments, or mutate external state."
)

REQUIRED_OPERATOR_DECISION_FIELDS = [
    "operator_target_match_confirmed",
    "operator_assay_origin_confirmed",
    "operator_data_validity_accepted",
    "operator_endpoint_is_direct_binding",
    "operator_source_locator_verified",
    "operator_claim_safe_decision",
]

VALIDATION_BLOCKERS = [
    "assay_origin_unknown",
    "data_validity_outside_typical_range",
    "source_locator_requires_operator_verification",
    "direct_binding_claim_requires_exact_target_pair_source",
]

RETURN_ARTIFACTS = [
    "completed runs/aqp1_operator_validation_candidate_packet_current.csv with operator_* fields resolved",
    "runs/aqp1_binding_source_modality_triage_current.json",
    "runs/transporter_p0_evidence_acquisition_packet_current.json",
    "runs/product_scope_breadth_contract_current.json",
]

POST_RETURN_VALIDATION_COMMANDS = [
    "python3 tools/product/build_aqp1_binding_source_modality_triage.py",
    "python3 tools/product/build_aqp1_operator_validation_candidate_packet.py",
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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(str(value or "").strip()))
    except ValueError:
        return 0


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _candidate_row(summary: dict[str, Any]) -> dict[str, Any]:
    candidate_id = _text(summary.get("chembl_aqp1_direct_like_binding_candidate_chembl_id"))
    if not candidate_id:
        return {}
    claim_safe_ready = _int(summary.get("direct_like_binding_candidate_claim_safe_ready_count")) > 0
    blocker = _text(summary.get("chembl_aqp1_direct_like_binding_candidate_blocker"))
    return {
        "candidate_id": "aqp1_chembl20_direct_like_kd_operator_validation",
        "candidate_status": "operator_validation_required",
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "target_chembl_id": _text(summary.get("aqp1_chembl_target_id")) or "CHEMBL4523210",
        "candidate_ligand_external_identifier": candidate_id,
        "candidate_ligand_name": _text(summary.get("chembl_aqp1_direct_like_binding_candidate_name")),
        "candidate_activity_id": _text(summary.get("chembl_aqp1_direct_like_binding_candidate_activity_id")),
        "candidate_standard_type": _text(summary.get("chembl_aqp1_direct_like_binding_candidate_standard_type")),
        "candidate_standard_value_nM": _text(summary.get("chembl_aqp1_direct_like_binding_candidate_standard_value_nM")),
        "candidate_reference_binding_kcal_mol": _text(
            summary.get("chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol")
        ),
        "candidate_source_artifact": DEFAULT_SOURCE_TRIAGE_JSON,
        "candidate_source_locator": (
            "https://www.ebi.ac.uk/chembl/api/data/activity.json?"
            f"target_chembl_id=CHEMBL4523210&molecule_chembl_id={candidate_id}"
        ),
        "candidate_blocker": blocker,
        "candidate_claim_safe_ready": claim_safe_ready,
        "operator_target_match_confirmed": "OPERATOR_FILL_TRUE_OR_FALSE",
        "operator_assay_origin_confirmed": "OPERATOR_FILL_TRUE_OR_FALSE",
        "operator_data_validity_accepted": "OPERATOR_FILL_TRUE_OR_FALSE",
        "operator_endpoint_is_direct_binding": "OPERATOR_FILL_TRUE_OR_FALSE",
        "operator_source_locator_verified": "OPERATOR_FILL_TRUE_OR_FALSE",
        "operator_claim_safe_decision": "OPERATOR_FILL_APPROVE_CLAIM_SAFE_OR_KEEP_BLOCKED",
        "operator_replacement_reference_binding_kcal_mol": (
            _text(summary.get("chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol"))
            if claim_safe_ready
            else ""
        ),
        "required_operator_decision_fields": ";".join(REQUIRED_OPERATOR_DECISION_FIELDS),
        "validation_blockers": ";".join(VALIDATION_BLOCKERS if blocker else []),
        "claim_promotion_allowed": False,
        "authoritative_apply_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_payload(*, source_triage: dict[str, Any]) -> dict[str, Any]:
    source_summary = _summary(source_triage)
    row = _candidate_row(source_summary)
    rows = [row] if row else []
    candidate_ready = bool(rows)
    claim_safe_ready_count = sum(1 for item in rows if item.get("candidate_claim_safe_ready") is True)
    operator_placeholder_count = sum(
        1
        for item in rows
        for field in REQUIRED_OPERATOR_DECISION_FIELDS
        if _text(item.get(field)).startswith("OPERATOR_FILL")
    )
    packet_ready = candidate_ready
    summary = {
        "packet_type": "aqp1_operator_validation_candidate_packet",
        "status": (
            "aqp1_operator_validation_candidate_packet_ready"
            if packet_ready
            else "blocked_aqp1_operator_validation_candidate_packet"
        ),
        "packet_ready": packet_ready,
        "candidate_ready": candidate_ready,
        "candidate_count": len(rows),
        "candidate_claim_safe_ready_count": claim_safe_ready_count,
        "operator_validation_required_count": len(rows) - claim_safe_ready_count,
        "operator_placeholder_count": operator_placeholder_count,
        "required_operator_decision_fields": REQUIRED_OPERATOR_DECISION_FIELDS,
        "required_operator_decision_field_count": len(REQUIRED_OPERATOR_DECISION_FIELDS),
        "validation_blockers": VALIDATION_BLOCKERS if rows else [],
        "validation_blocker_count": len(VALIDATION_BLOCKERS) if rows else 0,
        "first_candidate_id": _text(row.get("candidate_id")),
        "first_candidate_target_id": _text(row.get("target_id")),
        "first_candidate_target_uniprot": _text(row.get("target_uniprot")),
        "first_candidate_ligand_external_identifier": _text(
            row.get("candidate_ligand_external_identifier")
        ),
        "first_candidate_ligand_name": _text(row.get("candidate_ligand_name")),
        "first_candidate_activity_id": _text(row.get("candidate_activity_id")),
        "first_candidate_standard_type": _text(row.get("candidate_standard_type")),
        "first_candidate_standard_value_nM": _text(row.get("candidate_standard_value_nM")),
        "first_candidate_reference_binding_kcal_mol": _text(
            row.get("candidate_reference_binding_kcal_mol")
        ),
        "first_candidate_blocker": _text(row.get("candidate_blocker")),
        "first_candidate_claim_safe_ready": bool(row.get("candidate_claim_safe_ready") is True),
        "first_candidate_source_locator": _text(row.get("candidate_source_locator")),
        "return_bundle_required_artifacts": RETURN_ARTIFACTS,
        "return_bundle_required_artifact_count": len(RETURN_ARTIFACTS),
        "post_return_validation_commands": POST_RETURN_VALIDATION_COMMANDS,
        "post_return_validation_command_count": len(POST_RETURN_VALIDATION_COMMANDS),
        "next_required_step": (
            "Operator must verify target match, assay origin, data validity, direct-binding endpoint, source locator, "
            "and claim-safe decision for CHEMBL20/AQP1; otherwise keep AQP1.core_binder_01 blocked."
            if candidate_ready
            else "Regenerate AQP1 source-modality triage or provide a direct-like candidate before operator validation."
        ),
        "claim_promotion_allowed": False,
        "authoritative_apply_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "blockers": [] if packet_ready else [{"code": "missing_candidate"}]}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# AQP1 Operator Validation Candidate Packet",
        "",
        f"- status: `{s['status']}`",
        f"- packet_ready: `{s['packet_ready']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- candidate_claim_safe_ready_count: `{s['candidate_claim_safe_ready_count']}`",
        f"- operator_placeholder_count: `{s['operator_placeholder_count']}`",
        f"- first_candidate_ligand_external_identifier: `{s['first_candidate_ligand_external_identifier']}`",
        f"- first_candidate_reference_binding_kcal_mol: `{s['first_candidate_reference_binding_kcal_mol']}`",
        f"- first_candidate_blocker: `{s['first_candidate_blocker']}`",
        "",
        "## Rows",
        "",
        "| candidate_id | ligand | kcal | status | claim_safe_ready | blocker |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['candidate_id']}` | `{row['candidate_ligand_external_identifier']}` | "
            f"`{row['candidate_reference_binding_kcal_mol']}` | `{row['candidate_status']}` | "
            f"`{row['candidate_claim_safe_ready']}` | `{row['candidate_blocker']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 operator-validation candidate packet.")
    parser.add_argument("--source-triage-json", default=DEFAULT_SOURCE_TRIAGE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(source_triage=_read_json(args.source_triage_json))
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
