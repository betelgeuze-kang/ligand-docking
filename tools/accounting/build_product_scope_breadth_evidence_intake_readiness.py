#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_PRIORITY_JSON = RUNS / "product_scope_breadth_evidence_priority_packet_current.json"
DEFAULT_TRANSPORTER_TRIAGE_JSON = RUNS / "transporter_local_crosscheck_triage_packet_current.json"
DEFAULT_TRANSPORTER_CANDIDATE_WORKBOOK_JSON = RUNS / "transporter_slot_assignment_candidate_workbook_current.json"
DEFAULT_TRANSPORTER_MANUAL_REVIEW_INTAKE_JSON = RUNS / "transporter_manual_review_intake_template_current.json"
DEFAULT_OUT_JSON = RUNS / "product_scope_breadth_evidence_intake_readiness_current.json"
DEFAULT_OUT_CSV = RUNS / "product_scope_breadth_evidence_intake_readiness_current.csv"
DEFAULT_OUT_MD = RUNS / "product_scope_breadth_evidence_intake_readiness_current.md"

CLAIM_BOUNDARY = (
    "Product scope breadth evidence intake readiness only; it verifies that prioritized scope-breadth evidence rows "
    "have concrete intake requirements and, for local crosscheck lanes, readable local crosscheck payloads. It does "
    "not accept evidence, authoritatively apply rows, widen API scope, run docking, promote claims, upload, submit, "
    "email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_json_payload(path_like: str | Path) -> tuple[bool, str]:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return False, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "unreadable_json"
    if not isinstance(payload, (dict, list)):
        return False, "unexpected_json_shape"
    return True, "json_readable"


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _split_paths(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _triage_by_item(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("item_id")): row for row in _rows(packet) if _text(row.get("item_id"))}


def _required_intake_columns(row: dict[str, Any]) -> list[str]:
    bucket = _text(row.get("evidence_priority_bucket"))
    domain = _text(row.get("domain"))
    if bucket == "claim_gate_waits_on_domain_evidence":
        return ["prerequisite_domain", "required_gate", "current_value", "required_value", "source_artifact"]
    if bucket == "review_only_keep_blocked_until_direct_binding":
        return [
            "target_id",
            "candidate_ligand_id",
            "direct_binding_source_url_or_doi",
            "direct_binding_reference_binding_kcal_mol",
            "review_guardrail_decision",
        ]
    if domain == "pxr":
        return [
            "target_id",
            "candidate_name",
            "human_nr1i2_pxr_evidence_mode",
            "replacement_reference_binding_kcal_mol",
            "replacement_source_url_or_doi",
            "replacement_smiles",
            "replacement_scaffold",
        ]
    return [
        "target_id",
        "candidate_ligand_id",
        "reference_binding_kcal_mol",
        "source_url_or_doi",
        "smiles",
        "scaffold",
        "evidence_type",
    ]


def _intake_mode(row: dict[str, Any]) -> str:
    bucket = _text(row.get("evidence_priority_bucket"))
    if bucket == "claim_gate_waits_on_domain_evidence":
        return "deferred_claim_gate"
    if bucket == "external_primary_exact_evidence_required":
        return "external_exact_source_required"
    if bucket == "review_only_keep_blocked_until_direct_binding":
        return "review_only_guardrail"
    return "local_crosscheck_triage"


def _operator_binding_ready(row: dict[str, Any]) -> bool:
    return bool(
        _text(row.get("item_id"))
        and _text(row.get("domain"))
        and _text(row.get("required_evidence_type"))
        and _text(row.get("review_template_artifact"))
        and _text(row.get("apply_gate_artifact"))
        and _text(row.get("regeneration_commands"))
        and row.get("operator_packet_binding_ready") is True
    )


def build_payload(
    *,
    priority_packet: dict[str, Any],
    transporter_triage_packet: dict[str, Any] | None = None,
    transporter_candidate_workbook_packet: dict[str, Any] | None = None,
    transporter_manual_review_intake_packet: dict[str, Any] | None = None,
    priority_path: str = DEFAULT_PRIORITY_JSON.as_posix(),
    transporter_triage_path: str = DEFAULT_TRANSPORTER_TRIAGE_JSON.as_posix(),
    transporter_candidate_workbook_path: str = DEFAULT_TRANSPORTER_CANDIDATE_WORKBOOK_JSON.as_posix(),
    transporter_manual_review_intake_path: str = DEFAULT_TRANSPORTER_MANUAL_REVIEW_INTAKE_JSON.as_posix(),
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    transporter_triage_rows = _triage_by_item(transporter_triage_packet or {})
    for source_row in _rows(priority_packet):
        item_id = _text(source_row.get("item_id"))
        transporter_triage = transporter_triage_rows.get(item_id, {})
        local_paths = _split_paths(source_row.get("local_crosscheck_paths"))
        path_statuses = [_read_json_payload(path) for path in local_paths]
        readable_count = sum(1 for ok, _reason in path_statuses if ok)
        missing_reasons = sorted({reason for ok, reason in path_statuses if not ok})
        required_columns = _required_intake_columns(source_row)
        mode = _intake_mode(source_row)
        local_payloads_ready = bool(local_paths) and readable_count == len(local_paths)
        external_exact_required = mode == "external_exact_source_required"
        guardrail_ready = mode in {"review_only_guardrail", "deferred_claim_gate"}
        operator_binding_ready = _operator_binding_ready(source_row)
        evidence_intake_ready = mode == "local_crosscheck_triage" and local_payloads_ready and bool(required_columns)
        rows.append(
            {
                "priority": _int(source_row.get("priority")),
                "domain": _text(source_row.get("domain")),
                "item_id": item_id,
                "target_id": _text(source_row.get("target_id")),
                "target_promotion_status": _text(source_row.get("target_promotion_status")),
                "target_ready_for_promotion": source_row.get("target_ready_for_promotion") is True,
                "target_blocked_for_promotion": source_row.get("target_blocked_for_promotion") is True,
                "candidate_or_check": _text(source_row.get("candidate_or_check")),
                "evidence_priority_bucket": _text(source_row.get("evidence_priority_bucket")),
                "intake_mode": mode,
                "transporter_slot_triage_bucket": _text(transporter_triage.get("slot_triage_bucket")),
                "transporter_direct_quantitative_record_count": _int(
                    transporter_triage.get("direct_quantitative_record_count")
                ),
                "transporter_functional_quantitative_record_count": _int(
                    transporter_triage.get("functional_quantitative_record_count")
                ),
                "transporter_not_active_nonquantitative_record_count": _int(
                    transporter_triage.get("not_active_nonquantitative_record_count")
                ),
                "transporter_claim_safe_local_evidence_ready": (
                    transporter_triage.get("claim_safe_local_evidence_ready") is True
                ),
                "transporter_claim_safe_blocker": _text(transporter_triage.get("claim_safe_blocker")),
                "transporter_operator_next_verdict": _text(transporter_triage.get("operator_next_verdict")),
                "transporter_best_evidence_source_file": _text(transporter_triage.get("best_evidence_source_file")),
                "transporter_best_evidence_activity_type": _text(transporter_triage.get("best_evidence_activity_type")),
                "transporter_best_evidence_value": _text(transporter_triage.get("best_evidence_value")),
                "transporter_best_evidence_units": _text(transporter_triage.get("best_evidence_units")),
                "transporter_best_evidence_document_id": _text(transporter_triage.get("best_evidence_document_id")),
                "required_intake_columns": ",".join(required_columns),
                "required_intake_column_count": len(required_columns),
                "required_evidence_type": _text(source_row.get("required_evidence_type")),
                "review_template_artifact": _text(source_row.get("review_template_artifact")),
                "apply_gate_artifact": _text(source_row.get("apply_gate_artifact")),
                "regeneration_commands": _text(source_row.get("regeneration_commands")),
                "operator_packet_binding_key": _text(source_row.get("operator_packet_binding_key")),
                "operator_packet_binding_ready": operator_binding_ready,
                "local_crosscheck_path_count": len(local_paths),
                "local_crosscheck_readable_count": readable_count,
                "local_crosscheck_payloads_ready": local_payloads_ready,
                "external_exact_evidence_required": external_exact_required,
                "guardrail_ready": guardrail_ready,
                "evidence_intake_ready": evidence_intake_ready,
                "unreadable_local_payload_reasons": ",".join(missing_reasons),
                "source_artifact": _text(source_row.get("source_artifact")) or priority_path,
                "authoritative_apply_allowed": False,
                "scope_promotion_allowed": False,
                "external_state_mutated": False,
            }
        )

    source_summary = _summary(priority_packet)
    local_rows = [row for row in rows if row["intake_mode"] == "local_crosscheck_triage"]
    external_rows = [row for row in rows if row["external_exact_evidence_required"]]
    guardrail_rows = [row for row in rows if row["guardrail_ready"]]
    ready_local_rows = [row for row in local_rows if row["evidence_intake_ready"]]
    unreadable_rows = [row for row in local_rows if not row["local_crosscheck_payloads_ready"]]
    operator_bound_rows = [row for row in rows if row["operator_packet_binding_ready"]]
    unbound_rows = [row for row in rows if not row["operator_packet_binding_ready"]]
    transporter_triage_summary = _summary(transporter_triage_packet or {})
    transporter_candidate_summary = _summary(transporter_candidate_workbook_packet or {})
    transporter_manual_review_summary = _summary(transporter_manual_review_intake_packet or {})
    transporter_candidate_manual_review_count = _int(
        transporter_candidate_summary.get("candidate_ready_for_manual_review_count")
    )
    transporter_manual_review_intake_ready = (
        transporter_manual_review_summary.get("manual_review_intake_ready") is True
    )
    transporter_manual_review_template_row_count = _int(
        transporter_manual_review_summary.get("manual_review_template_row_count")
    )
    transporter_manual_review_row_count_matches_workbook = bool(
        transporter_candidate_manual_review_count == 0
        or transporter_manual_review_template_row_count == transporter_candidate_manual_review_count
    )
    transporter_manual_review_required = transporter_candidate_manual_review_count > 0
    intake_readiness_ready = bool(rows) and _int(source_summary.get("queue_item_count")) == len(rows)
    intake_readiness_ready = bool(
        intake_readiness_ready
        and len(ready_local_rows) == len(local_rows)
        and not unreadable_rows
        and not unbound_rows
        and (
            not transporter_manual_review_required
            or (transporter_manual_review_intake_ready and transporter_manual_review_row_count_matches_workbook)
        )
    )
    review_template_artifacts = _unique([str(row["review_template_artifact"]) for row in rows])
    apply_gate_artifacts = _unique([str(row["apply_gate_artifact"]) for row in rows])
    validation_commands = _unique(
        [
            command
            for row in rows
            for command in _split_paths(row.get("regeneration_commands"))
        ]
    )
    operator_transfer_outbound_artifacts = _unique(
        [
            priority_path,
            transporter_triage_path,
            transporter_candidate_workbook_path,
            transporter_manual_review_intake_path,
            *review_template_artifacts,
            *apply_gate_artifacts,
            "readable local crosscheck payloads referenced by local_crosscheck_paths",
        ]
    )
    operator_transfer_inbound_artifacts = [
        "completed runs/transporter_manual_review_intake_template_current.csv with OPERATOR_FILL placeholders resolved",
        "completed runs/transporter_manual_review_intake_template_current.json if JSON review path is used",
        "completed runs/pxr_exact_evidence_review_intake_template_current.csv with exact human NR1I2/PXR values",
        "completed runs/pxr_exact_evidence_review_intake_template_current.json if JSON review path is used",
    ]
    operator_transfer_manifest_ready = bool(
        intake_readiness_ready
        and operator_transfer_outbound_artifacts
        and operator_transfer_inbound_artifacts
        and validation_commands
    )
    next_operator_row = (ready_local_rows or local_rows or rows or [{}])[0]
    next_operator_required_columns = [
        part.strip()
        for part in _text(next_operator_row.get("required_intake_columns")).split(",")
        if part.strip()
    ]
    summary = {
        "packet_type": "product_scope_breadth_evidence_intake_readiness",
        "intake_readiness_ready": intake_readiness_ready,
        "source_priority_packet_ready": source_summary.get("priority_packet_ready") is True,
        "source_queue_item_count": _int(source_summary.get("queue_item_count")),
        "row_count": len(rows),
        "local_crosscheck_triage_item_count": len(local_rows),
        "local_crosscheck_intake_ready_count": len(ready_local_rows),
        "local_crosscheck_unreadable_item_count": len(unreadable_rows),
        "external_exact_evidence_required_count": len(external_rows),
        "guardrail_item_count": len(guardrail_rows),
        "operator_packet_binding_ready_count": len(operator_bound_rows),
        "operator_packet_binding_missing_count": len(unbound_rows),
        "all_operator_packet_bindings_ready": bool(rows) and not unbound_rows,
        "top_unbound_item_id": unbound_rows[0]["item_id"] if unbound_rows else "",
        "top_unbound_required_evidence_type": unbound_rows[0]["required_evidence_type"] if unbound_rows else "",
        "next_operator_completion_item_id": _text(next_operator_row.get("item_id")),
        "next_operator_completion_target_id": _text(next_operator_row.get("target_id")),
        "next_operator_completion_target_promotion_status": _text(
            next_operator_row.get("target_promotion_status")
        ),
        "next_operator_completion_target_ready_for_promotion": (
            next_operator_row.get("target_ready_for_promotion") is True
        ),
        "next_operator_completion_target_blocked_for_promotion": (
            next_operator_row.get("target_blocked_for_promotion") is True
        ),
        "next_operator_completion_domain": _text(next_operator_row.get("domain")),
        "next_operator_completion_candidate_or_check": _text(next_operator_row.get("candidate_or_check")),
        "next_operator_completion_intake_mode": _text(next_operator_row.get("intake_mode")),
        "next_operator_completion_required_evidence_type": _text(
            next_operator_row.get("required_evidence_type")
        ),
        "next_operator_completion_required_intake_columns": next_operator_required_columns,
        "next_operator_completion_required_intake_column_count": len(next_operator_required_columns),
        "next_operator_completion_review_template_artifact": _text(
            next_operator_row.get("review_template_artifact")
        ),
        "next_operator_completion_apply_gate_artifact": _text(next_operator_row.get("apply_gate_artifact")),
        "next_operator_completion_regeneration_commands": _text(
            next_operator_row.get("regeneration_commands")
        ),
        "next_operator_completion_operator_packet_binding_key": _text(
            next_operator_row.get("operator_packet_binding_key")
        ),
        "next_operator_completion_operator_packet_binding_ready": bool(
            next_operator_row.get("operator_packet_binding_ready") is True
        ),
        "next_operator_completion_transporter_claim_safe_blocker": _text(
            next_operator_row.get("transporter_claim_safe_blocker")
        ),
        "next_operator_completion_transporter_operator_next_verdict": _text(
            next_operator_row.get("transporter_operator_next_verdict")
        ),
        "next_operator_completion_transporter_best_evidence_source_file": _text(
            next_operator_row.get("transporter_best_evidence_source_file")
        ),
        "next_operator_completion_transporter_best_evidence_activity_type": _text(
            next_operator_row.get("transporter_best_evidence_activity_type")
        ),
        "next_operator_completion_transporter_best_evidence_value": _text(
            next_operator_row.get("transporter_best_evidence_value")
        ),
        "next_operator_completion_transporter_best_evidence_units": _text(
            next_operator_row.get("transporter_best_evidence_units")
        ),
        "next_operator_completion_transporter_best_evidence_document_id": _text(
            next_operator_row.get("transporter_best_evidence_document_id")
        ),
        "transporter_target_ready_for_promotion_ids": _text_list(
            source_summary.get("transporter_target_ready_for_promotion_ids")
        ),
        "transporter_target_blocked_for_promotion_ids": _text_list(
            source_summary.get("transporter_target_blocked_for_promotion_ids")
        ),
        "transporter_priority_target_ready_item_count": _int(
            source_summary.get("transporter_priority_target_ready_item_count")
        ),
        "transporter_priority_target_blocked_item_count": _int(
            source_summary.get("transporter_priority_target_blocked_item_count")
        ),
        "transporter_primary_blocker_target_id": _text(
            source_summary.get("transporter_primary_blocker_target_id")
        ),
        "transporter_primary_blocker_packet_step": _text(
            source_summary.get("transporter_primary_blocker_packet_step")
        ),
        "transporter_primary_blocker_candidate_name": _text(
            source_summary.get("transporter_primary_blocker_candidate_name")
        ),
        "transporter_primary_blocker_signal": _text(
            source_summary.get("transporter_primary_blocker_signal")
        ),
        "transporter_triage_packet_ready": transporter_triage_summary.get("triage_packet_ready") is True,
        "transporter_operator_review_evidence_matrix_ready": (
            transporter_triage_summary.get("operator_review_evidence_matrix_ready") is True
        ),
        "transporter_triage_row_count": _int(transporter_triage_summary.get("triage_row_count")),
        "transporter_claim_safe_local_evidence_ready_count": _int(
            transporter_triage_summary.get("claim_safe_local_evidence_ready_count")
        ),
        "transporter_claim_safe_local_evidence_blocked_count": _int(
            transporter_triage_summary.get("claim_safe_local_evidence_blocked_count")
        ),
        "transporter_direct_binding_claim_blocked_count": _int(
            transporter_triage_summary.get("direct_binding_claim_blocked_count")
        ),
        "transporter_negative_value_claim_blocked_count": _int(
            transporter_triage_summary.get("negative_value_claim_blocked_count")
        ),
        "transporter_top_claim_safe_blocker": _text(transporter_triage_summary.get("top_claim_safe_blocker")),
        "transporter_top_operator_next_verdict": _text(transporter_triage_summary.get("top_operator_next_verdict")),
        "transporter_candidate_assignment_required_count": _int(
            transporter_triage_summary.get("candidate_assignment_required_count")
        ),
        "transporter_named_candidate_manual_match_required_count": _int(
            transporter_triage_summary.get("named_candidate_manual_match_required_count")
        ),
        "transporter_functional_quantitative_only_direct_gap_open_count": _int(
            transporter_triage_summary.get("functional_quantitative_only_direct_gap_open_count")
        ),
        "transporter_review_only_direct_binding_gap_count": _int(
            transporter_triage_summary.get("review_only_direct_binding_gap_count")
        ),
        "transporter_external_exact_candidate_required_count": _int(
            transporter_triage_summary.get("external_exact_candidate_required_count")
        ),
        "transporter_local_crosscheck_can_close_slots_without_manual_assignment": (
            transporter_triage_summary.get("local_crosscheck_can_close_slots_without_manual_assignment") is True
        ),
        "transporter_candidate_workbook_ready": (
            transporter_candidate_summary.get("candidate_workbook_ready") is True
        ),
        "transporter_candidate_row_count": _int(transporter_candidate_summary.get("candidate_row_count")),
        "transporter_candidate_ready_for_manual_review_count": _int(
            transporter_candidate_summary.get("candidate_ready_for_manual_review_count")
        ),
        "transporter_candidate_ready_for_apply_count": _int(
            transporter_candidate_summary.get("candidate_ready_for_apply_count")
        ),
        "transporter_candidate_blocked_review_only_count": _int(
            transporter_candidate_summary.get("blocked_review_only_count")
        ),
        "transporter_candidate_negative_value_review_required_count": _int(
            transporter_candidate_summary.get("negative_value_review_required_count")
        ),
        "transporter_manual_review_intake_required": transporter_manual_review_required,
        "transporter_manual_review_intake_ready": transporter_manual_review_intake_ready,
        "transporter_manual_review_template_row_count": transporter_manual_review_template_row_count,
        "transporter_manual_review_row_count_matches_workbook": transporter_manual_review_row_count_matches_workbook,
        "transporter_manual_review_direct_binding_evidence_required_count": _int(
            transporter_manual_review_summary.get("direct_binding_evidence_required_count")
        ),
        "transporter_manual_review_negative_quantitative_value_required_count": _int(
            transporter_manual_review_summary.get("negative_quantitative_value_required_count")
        ),
        "transporter_manual_review_decision_placeholder_count": _int(
            transporter_manual_review_summary.get("review_decision_placeholder_count")
        ),
        "transporter_manual_review_p0_slot_overlay_row_count": _int(
            transporter_manual_review_summary.get("p0_slot_overlay_row_count")
        ),
        "transporter_manual_review_p0_slot_overlay_candidate_changed_count": _int(
            transporter_manual_review_summary.get("p0_slot_overlay_candidate_changed_count")
        ),
        "transporter_manual_review_p0_slot_overlay_first_item_id": _text(
            transporter_manual_review_summary.get("p0_slot_overlay_first_item_id")
        ),
        "transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id": _text(
            transporter_manual_review_summary.get("p0_slot_overlay_first_candidate_ligand_id")
        ),
        "transporter_manual_review_p0_slot_overlay_first_source": _text(
            transporter_manual_review_summary.get("p0_slot_overlay_first_source")
        ),
        "first_review_row_id": _text(transporter_manual_review_summary.get("first_review_row_id")),
        "first_review_item_id": _text(transporter_manual_review_summary.get("first_review_item_id")),
        "first_review_target_id": _text(transporter_manual_review_summary.get("first_review_target_id")),
        "first_review_candidate_ligand_id": _text(
            transporter_manual_review_summary.get("first_review_candidate_ligand_id")
        ),
        "first_review_replacement_source": _text(
            transporter_manual_review_summary.get("first_review_replacement_source")
        ),
        "first_review_replacement_reference_binding_kcal_mol": _text(
            transporter_manual_review_summary.get("first_review_replacement_reference_binding_kcal_mol")
        ),
        "first_review_direct_binding_evidence_required": (
            transporter_manual_review_summary.get("first_review_direct_binding_evidence_required") is True
        ),
        "first_review_direct_binding_source_url_or_doi": _text(
            transporter_manual_review_summary.get("first_review_direct_binding_source_url_or_doi")
        ),
        "first_review_negative_quantitative_value_required": (
            transporter_manual_review_summary.get("first_review_negative_quantitative_value_required") is True
        ),
        "first_review_negative_reference_binding_kcal_mol": _text(
            transporter_manual_review_summary.get("first_review_negative_reference_binding_kcal_mol")
        ),
        "first_review_review_decision": _text(
            transporter_manual_review_summary.get("first_review_review_decision")
        ),
        "first_review_authoritative_apply_requested": _text(
            transporter_manual_review_summary.get("first_review_authoritative_apply_requested")
        ),
        "first_review_manual_review_blockers": _text(
            transporter_manual_review_summary.get("first_review_manual_review_blockers")
        ),
        "first_review_review_requirements": _text(
            transporter_manual_review_summary.get("first_review_review_requirements")
        ),
        "first_review_p0_slot_overlay_required_missing_fields": _text(
            transporter_manual_review_summary.get("first_review_p0_slot_overlay_required_missing_fields")
        ),
        "first_review_p0_slot_overlay_claim_safe_step_ready": (
            transporter_manual_review_summary.get("first_review_p0_slot_overlay_claim_safe_step_ready") is True
        ),
        "first_review_p0_slot_overlay_authoritative_apply_allowed": (
            transporter_manual_review_summary.get("first_review_p0_slot_overlay_authoritative_apply_allowed")
            is True
        ),
        "first_review_p0_slot_overlay_scope_promotion_allowed": (
            transporter_manual_review_summary.get("first_review_p0_slot_overlay_scope_promotion_allowed") is True
        ),
        "scope_operator_transfer_manifest_ready": operator_transfer_manifest_ready,
        "scope_operator_transfer_outbound_artifact_count": len(operator_transfer_outbound_artifacts),
        "scope_operator_transfer_outbound_artifacts": operator_transfer_outbound_artifacts,
        "scope_operator_transfer_inbound_artifact_count": len(operator_transfer_inbound_artifacts),
        "scope_operator_transfer_inbound_artifacts": operator_transfer_inbound_artifacts,
        "scope_operator_transfer_first_return_artifact": operator_transfer_inbound_artifacts[0],
        "scope_operator_transfer_acceptance_artifact": "runs/product_scope_breadth_contract_current.json",
        "scope_operator_transfer_acceptance_ready_key": "scope_breadth_ready",
        "scope_operator_transfer_next_acceptance_stage": "transporter_claim_acceptance",
        "scope_operator_transfer_post_return_validation_command": " && ".join(validation_commands),
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
        "source_artifacts": [
            priority_path,
            transporter_triage_path,
            transporter_candidate_workbook_path,
            transporter_manual_review_intake_path,
        ],
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use ready local crosscheck rows and the transporter manual-review template for evidence triage, keep "
            "guardrail rows blocked, and acquire exact external primary evidence before any authoritative apply or "
            "broad platform claim."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Scope Breadth Evidence Intake Readiness",
        "",
        f"- intake_readiness_ready: `{s['intake_readiness_ready']}`",
        f"- row_count: `{s['row_count']}`",
        f"- local_crosscheck_triage_item_count: `{s['local_crosscheck_triage_item_count']}`",
        f"- local_crosscheck_intake_ready_count: `{s['local_crosscheck_intake_ready_count']}`",
        f"- external_exact_evidence_required_count: `{s['external_exact_evidence_required_count']}`",
        f"- guardrail_item_count: `{s['guardrail_item_count']}`",
        f"- all_operator_packet_bindings_ready: `{s['all_operator_packet_bindings_ready']}`",
        f"- operator_packet_binding_missing_count: `{s['operator_packet_binding_missing_count']}`",
        f"- next_operator_completion_target_id: `{s['next_operator_completion_target_id'] or '-'}`",
        f"- next_operator_completion_target_promotion_status: `{s['next_operator_completion_target_promotion_status'] or '-'}`",
        f"- next_operator_completion_target_blocked_for_promotion: `{s['next_operator_completion_target_blocked_for_promotion']}`",
        f"- transporter_target_ready_for_promotion_ids: `{';'.join(s['transporter_target_ready_for_promotion_ids']) or '-'}`",
        f"- transporter_target_blocked_for_promotion_ids: `{';'.join(s['transporter_target_blocked_for_promotion_ids']) or '-'}`",
        f"- transporter_primary_blocker_target_id: `{s['transporter_primary_blocker_target_id'] or '-'}`",
        f"- transporter_primary_blocker_packet_step: `{s['transporter_primary_blocker_packet_step'] or '-'}`",
        f"- transporter_primary_blocker_candidate_name: `{s['transporter_primary_blocker_candidate_name'] or '-'}`",
        f"- transporter_triage_packet_ready: `{s['transporter_triage_packet_ready']}`",
        f"- transporter_operator_review_evidence_matrix_ready: `{s['transporter_operator_review_evidence_matrix_ready']}`",
        f"- transporter_claim_safe_local_evidence_ready_count: `{s['transporter_claim_safe_local_evidence_ready_count']}`",
        f"- transporter_claim_safe_local_evidence_blocked_count: `{s['transporter_claim_safe_local_evidence_blocked_count']}`",
        f"- transporter_direct_binding_claim_blocked_count: `{s['transporter_direct_binding_claim_blocked_count']}`",
        f"- transporter_negative_value_claim_blocked_count: `{s['transporter_negative_value_claim_blocked_count']}`",
        f"- transporter_candidate_assignment_required_count: `{s['transporter_candidate_assignment_required_count']}`",
        f"- transporter_functional_quantitative_only_direct_gap_open_count: `{s['transporter_functional_quantitative_only_direct_gap_open_count']}`",
        f"- transporter_candidate_workbook_ready: `{s['transporter_candidate_workbook_ready']}`",
        f"- transporter_candidate_ready_for_manual_review_count: `{s['transporter_candidate_ready_for_manual_review_count']}`",
        f"- transporter_candidate_ready_for_apply_count: `{s['transporter_candidate_ready_for_apply_count']}`",
        f"- transporter_manual_review_intake_ready: `{s['transporter_manual_review_intake_ready']}`",
        f"- transporter_manual_review_template_row_count: `{s['transporter_manual_review_template_row_count']}`",
        f"- transporter_manual_review_direct_binding_evidence_required_count: `{s['transporter_manual_review_direct_binding_evidence_required_count']}`",
        f"- transporter_manual_review_negative_quantitative_value_required_count: `{s['transporter_manual_review_negative_quantitative_value_required_count']}`",
        f"- first_review_item_id: `{s['first_review_item_id'] or '-'}`",
        f"- first_review_candidate_ligand_id: `{s['first_review_candidate_ligand_id'] or '-'}`",
        f"- first_review_p0_slot_overlay_required_missing_fields: `{s['first_review_p0_slot_overlay_required_missing_fields'] or '-'}`",
        f"- first_review_p0_slot_overlay_scope_promotion_allowed: `{s['first_review_p0_slot_overlay_scope_promotion_allowed']}`",
        f"- scope_operator_transfer_manifest_ready: `{s['scope_operator_transfer_manifest_ready']}`",
        f"- scope_operator_transfer_outbound_artifact_count: `{s['scope_operator_transfer_outbound_artifact_count']}`",
        f"- scope_operator_transfer_inbound_artifact_count: `{s['scope_operator_transfer_inbound_artifact_count']}`",
        f"- scope_operator_transfer_first_return_artifact: `{s['scope_operator_transfer_first_return_artifact']}`",
        f"- scope_operator_transfer_acceptance_artifact: `{s['scope_operator_transfer_acceptance_artifact']}`",
        f"- scope_promotion_allowed: `{s['scope_promotion_allowed']}`",
        "",
        "## Operator Evidence Transfer Manifest",
        "",
        "### Review Inputs",
        "",
    ]
    for artifact in s["scope_operator_transfer_outbound_artifacts"]:
        lines.append(f"- `{artifact}`")
    lines.extend(
        [
            "",
            "### Completed Evidence Returns",
            "",
        ]
    )
    for artifact in s["scope_operator_transfer_inbound_artifacts"]:
        lines.append(f"- `{artifact}`")
    lines.extend(
        [
            "",
            f"- acceptance artifact: `{s['scope_operator_transfer_acceptance_artifact']}`",
            f"- acceptance ready key: `{s['scope_operator_transfer_acceptance_ready_key']}`",
            f"- next acceptance stage: `{s['scope_operator_transfer_next_acceptance_stage']}`",
            "",
            "### Post-Return Validation Command",
            "",
            "```bash",
            s["scope_operator_transfer_post_return_validation_command"],
            "```",
            "",
        "## Intake Rows",
        "",
        "| priority | domain | target | item | target status | mode | ready | operator binding | local payloads | transporter triage | claim safe | claim blocker | required columns |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['domain']}` | `{row['target_id'] or '-'}` | "
            f"`{row['item_id']}` | `{row['target_promotion_status'] or '-'}` | `{row['intake_mode']}` | "
            f"`{row['evidence_intake_ready']}` | `{row['operator_packet_binding_ready']}` | "
            f"{row['local_crosscheck_readable_count']}/{row['local_crosscheck_path_count']} | "
            f"`{row['transporter_slot_triage_bucket'] or '-'}` | "
            f"`{row['transporter_claim_safe_local_evidence_ready']}` | "
            f"`{row['transporter_claim_safe_blocker'] or '-'}` | "
            f"`{row['required_intake_columns']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product scope breadth evidence intake readiness packet.")
    parser.add_argument("--priority-json", default=str(DEFAULT_PRIORITY_JSON))
    parser.add_argument("--transporter-triage-json", default=str(DEFAULT_TRANSPORTER_TRIAGE_JSON))
    parser.add_argument("--transporter-candidate-workbook-json", default=str(DEFAULT_TRANSPORTER_CANDIDATE_WORKBOOK_JSON))
    parser.add_argument("--transporter-manual-review-intake-json", default=str(DEFAULT_TRANSPORTER_MANUAL_REVIEW_INTAKE_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        priority_packet=_load_json(args.priority_json),
        transporter_triage_packet=_load_json(args.transporter_triage_json),
        transporter_candidate_workbook_packet=_load_json(args.transporter_candidate_workbook_json),
        transporter_manual_review_intake_packet=_load_json(args.transporter_manual_review_intake_json),
        priority_path=args.priority_json,
        transporter_triage_path=args.transporter_triage_json,
        transporter_candidate_workbook_path=args.transporter_candidate_workbook_json,
        transporter_manual_review_intake_path=args.transporter_manual_review_intake_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
