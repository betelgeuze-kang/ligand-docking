#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCOPE_CONTRACT_JSON = "runs/product_scope_breadth_contract_current.json"
DEFAULT_EVIDENCE_QUEUE_JSON = "runs/product_scope_breadth_evidence_acquisition_queue_current.json"
DEFAULT_TRANSPORTER_P0_PACKET_JSON = "runs/transporter_p0_evidence_acquisition_packet_current.json"
DEFAULT_PXR_REVIEW_JSON = "runs/pxr_exact_evidence_review_intake_template_current.json"
DEFAULT_PXR_TRIAGE_JSON = "runs/pxr_source_modality_triage_current.json"
DEFAULT_GENERAL_BLOCKER_JSON = "runs/general_protein_ligand_claim_blocker_packet_current.json"
DEFAULT_OUT_JSON = "runs/product_scope_closure_acceptance_packet_current.json"
DEFAULT_OUT_CSV = "runs/product_scope_closure_acceptance_packet_current.csv"
DEFAULT_OUT_MD = "runs/product_scope_closure_acceptance_packet_current.md"

CLAIM_BOUNDARY = (
    "Product scope-closure acceptance packet only; it cross-checks existing transporter, PXR, and general "
    "protein-ligand claim gates. It does not fill scientific evidence, apply authoritative rows, widen product "
    "claims, run docking, upload, submit, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
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


def _bool(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    text = _text(value)
    return [part.strip() for part in text.split(";") if part.strip()] if text else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_blocked_evidence(blocked_stage_matrix: list[dict[str, Any]]) -> dict[str, Any]:
    for stage in blocked_stage_matrix:
        rows = stage.get("blocked_evidence_rows")
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    return row
    return {}


def _stage_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    blocked_rows = row.get("blocked_evidence_rows")
    blocked_rows = blocked_rows if isinstance(blocked_rows, list) else []
    first = next((item for item in blocked_rows if isinstance(item, dict)), {})
    return {
        "stage_id": _text(row.get("stage_id")),
        "status": _text(row.get("status")),
        "artifact": _text(row.get("artifact")),
        "release_effect": _text(row.get("release_effect")),
        "unlock_claim_scopes": ";".join(_list(row.get("unlock_claim_scopes"))),
        "required_checks": ";".join(_list(row.get("required_checks"))),
        "validation_command": _text(row.get("validation_command")),
        "blocked_evidence_row_count": _int(row.get("blocked_evidence_row_count") or len(blocked_rows)),
        "first_blocked_evidence_row_id": _text(
            first.get("evidence_row_id") or first.get("review_row_id") or first.get("row_id")
        ),
        "first_blocked_target_id": _text(first.get("target_id") or first.get("target_gene")),
        "first_blocked_candidate": _text(
            first.get("candidate_or_check")
            or first.get("candidate_name")
            or first.get("replacement_ligand_id")
        ),
        "first_required_missing_fields": _text(first.get("required_missing_fields")),
        "first_required_evidence_type": _text(
            first.get("required_evidence_type") or first.get("request_mode")
        ),
        "first_review_template_artifact": _text(
            first.get("review_template_artifact") or first.get("operator_review_artifact")
        ),
        "next_action": _text(row.get("next_action")),
        "release_blocker": row.get("status") != "ready",
        "execution_enabled": False,
        "scope_widened": False,
        "external_state_mutated": False,
    }


def build_product_scope_closure_acceptance_packet(
    *,
    scope_contract_packet: dict[str, Any],
    evidence_queue_packet: dict[str, Any] | None = None,
    transporter_p0_packet: dict[str, Any] | None = None,
    pxr_review_packet: dict[str, Any] | None = None,
    pxr_triage_packet: dict[str, Any] | None = None,
    general_blocker_packet: dict[str, Any] | None = None,
    scope_contract_path: str = DEFAULT_SCOPE_CONTRACT_JSON,
    evidence_queue_path: str = DEFAULT_EVIDENCE_QUEUE_JSON,
    transporter_p0_path: str = DEFAULT_TRANSPORTER_P0_PACKET_JSON,
    pxr_review_path: str = DEFAULT_PXR_REVIEW_JSON,
    pxr_triage_path: str = DEFAULT_PXR_TRIAGE_JSON,
    general_blocker_path: str = DEFAULT_GENERAL_BLOCKER_JSON,
) -> dict[str, Any]:
    scope = _summary(scope_contract_packet)
    queue = _summary(evidence_queue_packet or {})
    transporter = _summary(transporter_p0_packet or {})
    pxr_review = _summary(pxr_review_packet or {})
    pxr_triage = _summary(pxr_triage_packet or {})
    general = _summary(general_blocker_packet or {})
    matrix = [
        dict(row)
        for row in (scope_contract_packet.get("scope_acceptance_matrix") or [])
        if isinstance(row, dict)
    ]
    stage_evidence_matrix = [
        dict(row)
        for row in (scope_contract_packet.get("scope_acceptance_stage_evidence_matrix") or [])
        if isinstance(row, dict)
    ]
    blocked_stage_matrix = [
        dict(row)
        for row in (
            scope_contract_packet.get("scope_acceptance_current_blocked_stage_evidence_matrix")
            or []
        )
        if isinstance(row, dict)
    ]
    csv_rows = [_stage_csv_row(row) for row in matrix]
    blocked_rows = [row for row in csv_rows if row["status"] != "ready"]
    first_blocked_stage = blocked_rows[0] if blocked_rows else {}
    first_blocked_evidence = _first_blocked_evidence(blocked_stage_matrix)
    packet_ready = bool(scope.get("scope_acceptance_matrix_ready") is True and matrix)
    scope_ready = _bool(scope.get("scope_breadth_ready"))
    closure_ready = packet_ready and scope_ready and not blocked_rows
    summary = {
        "packet_type": "product_scope_closure_acceptance_packet",
        "status": "product_scope_closure_acceptance_complete"
        if closure_ready
        else "blocked_product_scope_closure_acceptance_packet",
        "packet_ready": packet_ready,
        "scope_closure_ready": closure_ready,
        "scope_breadth_ready": scope_ready,
        "scope_widened": _bool(scope.get("scope_widened")),
        "ready_domain_count": _int(scope.get("ready_domain_count")),
        "missing_domain_count": _int(scope.get("missing_domain_count")),
        "ready_domains": _list(scope.get("ready_domains")),
        "missing_domains": _list(scope.get("missing_domains")),
        "scope_acceptance_stage_count": len(matrix),
        "scope_acceptance_ready_stage_count": sum(1 for row in csv_rows if row["status"] == "ready"),
        "scope_acceptance_blocked_stage_count": len(blocked_rows),
        "scope_acceptance_blocked_stage_ids": [str(row["stage_id"]) for row in blocked_rows],
        "scope_acceptance_next_stage_id": _text(
            first_blocked_stage.get("stage_id") or scope.get("scope_acceptance_next_stage_id")
        ),
        "scope_acceptance_next_stage_artifact": _text(
            first_blocked_stage.get("artifact") or scope.get("scope_acceptance_next_stage_artifact")
        ),
        "scope_acceptance_next_stage_validation_command": _text(
            first_blocked_stage.get("validation_command")
            or scope.get("scope_acceptance_next_stage_validation_command")
        ),
        "scope_acceptance_next_stage_unlock_claim_scopes": _list(
            first_blocked_stage.get("unlock_claim_scopes")
            or scope.get("scope_acceptance_next_stage_unlock_claim_scopes")
        ),
        "scope_acceptance_next_stage_required_checks": _list(
            first_blocked_stage.get("required_checks")
            or scope.get("scope_acceptance_next_stage_required_checks")
        ),
        "scope_acceptance_stage_evidence_matrix_count": len(stage_evidence_matrix),
        "scope_acceptance_current_blocked_stage_evidence_matrix_count": len(blocked_stage_matrix),
        "first_blocked_evidence_row_id": _text(
            first_blocked_evidence.get("evidence_row_id")
            or first_blocked_evidence.get("review_row_id")
        ),
        "first_blocked_target_id": _text(
            first_blocked_evidence.get("target_id") or first_blocked_evidence.get("target_gene")
        ),
        "first_blocked_candidate": _text(
            first_blocked_evidence.get("candidate_or_check")
            or first_blocked_evidence.get("candidate_name")
            or first_blocked_evidence.get("replacement_ligand_id")
        ),
        "first_blocked_required_missing_fields": _text(
            first_blocked_evidence.get("required_missing_fields")
        ),
        "first_blocked_required_evidence_type": _text(
            first_blocked_evidence.get("required_evidence_type")
            or first_blocked_evidence.get("request_mode")
        ),
        "first_blocked_review_template_artifact": _text(
            first_blocked_evidence.get("review_template_artifact")
            or first_blocked_evidence.get("operator_review_artifact")
        ),
        "transporter_next_slot_completion_packet_ready": _bool(
            transporter.get("next_slot_completion_packet_ready")
            or scope.get("transporter_p0_evidence_acquisition_next_slot_completion_packet_ready")
        ),
        "transporter_next_slot_id": _text(
            transporter.get("next_slot_id")
            or scope.get("transporter_p0_evidence_acquisition_next_slot_id")
        ),
        "transporter_unresolved_slot_count": _int(
            transporter.get("unresolved_slot_count")
            or scope.get("transporter_p0_evidence_acquisition_unresolved_slot_count")
        ),
        "transporter_external_exact_evidence_required_slot_count": _int(
            transporter.get("exact_request_slot_count")
            or scope.get("transporter_p0_evidence_acquisition_exact_request_slot_count")
        ),
        "transporter_next_slot_source_modality": _text(
            transporter.get("next_slot_source_modality")
            or scope.get("transporter_p0_evidence_acquisition_next_slot_source_modality")
        ),
        "transporter_next_slot_direct_binding_claim_allowed": _bool(
            transporter.get("next_slot_source_modality_direct_binding_claim_allowed")
            or scope.get("transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed")
        ),
        "pxr_exact_review_intake_ready": _bool(
            pxr_review.get("pxr_exact_review_intake_ready") or scope.get("pxr_exact_review_intake_ready")
        ),
        "pxr_exact_review_row_count": _int(
            pxr_review.get("review_template_row_count") or scope.get("pxr_exact_review_template_row_count")
        ),
        "pxr_exact_review_conflict_resolution_required_count": _int(
            pxr_review.get("conflict_resolution_required_count")
            or scope.get("pxr_exact_review_conflict_resolution_required_count")
        ),
        "pxr_source_modality_triage_ready": _bool(
            pxr_triage.get("triage_ready") or scope.get("pxr_source_modality_triage_ready")
        ),
        "pxr_direct_or_claim_safe_quantitative_ready_count": _int(
            pxr_triage.get("direct_or_claim_safe_quantitative_ready_count")
            or scope.get("pxr_source_modality_direct_or_claim_safe_quantitative_ready_count")
        ),
        "pxr_next_review_candidate_name": _text(
            pxr_review.get("next_review_candidate_name")
            or pxr_triage.get("next_review_candidate_name")
            or scope.get("pxr_exact_review_next_review_candidate_name")
        ),
        "general_platform_claim_allowed": _bool(
            general.get("general_platform_claim_allowed") or scope.get("general_platform_claim_allowed")
        ),
        "general_platform_claim_blocked": _bool(
            general.get("general_platform_claim_blocked") or scope.get("general_platform_claim_blocked")
        ),
        "general_platform_next_required_step": _text(
            general.get("next_required_step")
        ),
        "next_required_step": _text(first_blocked_stage.get("next_action"))
        or _text(scope.get("scope_acceptance_next_stage_next_action"))
        or _text(scope.get("next_required_step"))
        or "Scope closure acceptance is complete.",
        "source_artifacts": [
            scope_contract_path,
            evidence_queue_path,
            transporter_p0_path,
            pxr_review_path,
            pxr_triage_path,
            general_blocker_path,
        ],
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": False,
        "scope_widened_by_packet": False,
        "external_state_mutated": False,
    }
    return {
        "summary": summary,
        "rows": csv_rows,
        "scope_acceptance_stage_evidence_matrix": stage_evidence_matrix,
        "scope_acceptance_current_blocked_stage_evidence_matrix": blocked_stage_matrix,
    }


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Scope Closure Acceptance Packet",
        "",
        f"- status: `{s['status']}`",
        f"- packet_ready: `{s['packet_ready']}`",
        f"- scope_closure_ready: `{s['scope_closure_ready']}`",
        f"- scope_acceptance_blocked_stage_ids: `{';'.join(s['scope_acceptance_blocked_stage_ids'])}`",
        f"- scope_acceptance_next_stage_id: `{s['scope_acceptance_next_stage_id']}`",
        f"- first_blocked_evidence_row_id: `{s['first_blocked_evidence_row_id']}`",
        f"- first_blocked_target_id: `{s['first_blocked_target_id']}`",
        f"- first_blocked_required_missing_fields: `{s['first_blocked_required_missing_fields']}`",
        f"- transporter_unresolved_slot_count: `{s['transporter_unresolved_slot_count']}`",
        f"- pxr_direct_or_claim_safe_quantitative_ready_count: `{s['pxr_direct_or_claim_safe_quantitative_ready_count']}`",
        f"- general_platform_claim_allowed: `{s['general_platform_claim_allowed']}`",
        f"- next_required_step: `{s['next_required_step']}`",
        "",
        "## Stages",
        "",
        "| stage | status | artifact | blocked rows | validation |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['stage_id']}` | `{row['status']}` | `{row['artifact']}` | "
            f"`{row['blocked_evidence_row_count']}` | `{row['validation_command']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product scope-closure acceptance packet.")
    parser.add_argument("--scope-contract-json", default=DEFAULT_SCOPE_CONTRACT_JSON)
    parser.add_argument("--evidence-queue-json", default=DEFAULT_EVIDENCE_QUEUE_JSON)
    parser.add_argument("--transporter-p0-json", default=DEFAULT_TRANSPORTER_P0_PACKET_JSON)
    parser.add_argument("--pxr-review-json", default=DEFAULT_PXR_REVIEW_JSON)
    parser.add_argument("--pxr-triage-json", default=DEFAULT_PXR_TRIAGE_JSON)
    parser.add_argument("--general-blocker-json", default=DEFAULT_GENERAL_BLOCKER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_scope_closure_acceptance_packet(
        scope_contract_packet=_read_json_if_present(args.scope_contract_json),
        evidence_queue_packet=_read_json_if_present(args.evidence_queue_json),
        transporter_p0_packet=_read_json_if_present(args.transporter_p0_json),
        pxr_review_packet=_read_json_if_present(args.pxr_review_json),
        pxr_triage_packet=_read_json_if_present(args.pxr_triage_json),
        general_blocker_packet=_read_json_if_present(args.general_blocker_json),
        scope_contract_path=args.scope_contract_json,
        evidence_queue_path=args.evidence_queue_json,
        transporter_p0_path=args.transporter_p0_json,
        pxr_review_path=args.pxr_review_json,
        pxr_triage_path=args.pxr_triage_json,
        general_blocker_path=args.general_blocker_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
