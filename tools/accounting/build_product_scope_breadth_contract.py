#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPABILITY_JSON = "runs/product_capability_surface_contract_current.json"
DEFAULT_TRANSPORTER_JSON = "runs/transporter_blocker_capture_sheet_current.json"
DEFAULT_TRANSPORTER_REOPEN_JSON = "runs/transporter_donor_policy_reopen_checklist_current.json"
DEFAULT_TRANSPORTER_BINDER_GATE_JSON = "runs/transporter_binder_promotion_gate_current.json"
DEFAULT_TRANSPORTER_P0_CLOSURE_JSON = "runs/transporter_p0_closure_packet_current.json"
DEFAULT_TRANSPORTER_P0_READINESS_MATRIX_JSON = "runs/transporter_p0_closure_readiness_matrix_current.json"
DEFAULT_TRANSPORTER_P0_EVIDENCE_ACQUISITION_JSON = "runs/transporter_p0_evidence_acquisition_packet_current.json"
DEFAULT_CA2_JSON = "runs/ca2_binding_verification_sheet_current.json"
DEFAULT_PXR_JSON = "runs/pxr_unresolved_evidence_capture_intake_current.json"
DEFAULT_PXR_FILL_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_PXR_BLOCKED_GATE_JSON = "runs/pxr_blocked_row_promotion_gate_current.json"
DEFAULT_PXR_EXACT_REVIEW_INTAKE_JSON = "runs/pxr_exact_evidence_review_intake_template_current.json"
DEFAULT_PXR_SOURCE_MODALITY_TRIAGE_JSON = "runs/pxr_source_modality_triage_current.json"
DEFAULT_IDP_SCAFFOLD_JSON = "runs/idp_broader_anchor_shadow_scaffold_current.json"
DEFAULT_IDP_PROMOTION_RESOLUTION_JSON = "runs/idp_broader_promotion_resolution_current.json"
DEFAULT_ALLATOM_JSON = "runs/allatom_claim_evidence_handoff_current.json"
DEFAULT_EVIDENCE_QUEUE_JSON = "runs/product_scope_breadth_evidence_acquisition_queue_current.json"
DEFAULT_EVIDENCE_PRIORITY_JSON = "runs/product_scope_breadth_evidence_priority_packet_current.json"
DEFAULT_EVIDENCE_INTAKE_READINESS_JSON = "runs/product_scope_breadth_evidence_intake_readiness_current.json"
DEFAULT_OUT_JSON = "runs/product_scope_breadth_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_scope_breadth_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_scope_breadth_contract_current.md"

REQUIRED_BREADTH_DOMAINS = ["transporter", "ca2", "pxr", "idp_broad", "all_atom", "general_protein_ligand"]

CLAIM_BOUNDARY = (
    "Product scope breadth contract only; audits local evidence for widening the product surface beyond the current "
    "restricted families. It does not widen API scope, run docking, generate structures, promote claims, upload, "
    "submit, email, delete, or mutate external state."
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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _first_packet_row(packet: dict[str, Any]) -> dict[str, Any]:
    rows = packet.get("rows")
    if not isinstance(rows, list):
        return {}
    return next((dict(row) for row in rows if isinstance(row, dict)), {})


def _packet_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _compact_transporter_evidence_row(row: dict[str, Any]) -> dict[str, Any]:
    target_id = _text(row.get("target_id"))
    packet_step = _text(row.get("packet_step"))
    return {
        "evidence_row_id": ".".join(item for item in [target_id, packet_step] if item),
        "target_id": target_id,
        "packet_step": packet_step,
        "replacement_ligand_id": _text(row.get("replacement_ligand_id")),
        "current_ligand_id": _text(row.get("current_ligand_id")),
        "request_mode": _text(row.get("request_mode")),
        "required_missing_fields": _text(row.get("required_missing_fields")),
        "source_signal": _text(row.get("source_signal")),
        "evidence_state": _text(row.get("evidence_state")),
        "next_required_action": _text(row.get("next_required_action")),
        "claim_safe_step_ready": bool(row.get("claim_safe_step_ready") is True),
        "scope_promotion_allowed": bool(row.get("scope_promotion_allowed") is True),
        "authoritative_apply_allowed": bool(row.get("authoritative_apply_allowed") is True),
    }


def _compact_pxr_review_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_row_id": _text(row.get("review_row_id")) or _text(row.get("source_row_fingerprint")),
        "target_gene": _text(row.get("target_gene")),
        "target_alias": _text(row.get("target_alias")),
        "target_species": _text(row.get("target_species")),
        "candidate_name": _text(row.get("candidate_name")),
        "workbook_replacement_ligand_id": _text(row.get("workbook_replacement_ligand_id")),
        "packet_step": _text(row.get("packet_step")),
        "request_mode": _text(row.get("request_mode")),
        "required_evidence_mode": _text(row.get("required_evidence_mode")),
        "readiness_missing_fields": _text(row.get("readiness_missing_fields")),
        "fail_closed_blockers": _text(row.get("fail_closed_blockers")),
        "replacement_reference_binding_kcal_mol": _text(row.get("replacement_reference_binding_kcal_mol")),
        "replacement_source_url_or_doi": _text(row.get("replacement_source_url_or_doi")),
        "target_match_confirmed": _text(row.get("target_match_confirmed")),
        "review_decision": _text(row.get("review_decision")),
        "conflict_resolution_required": bool(row.get("conflict_resolution_required") is True),
        "scope_promotion_allowed": bool(row.get("scope_promotion_allowed") is True),
        "authoritative_apply_allowed": bool(row.get("authoritative_apply_allowed") is True),
    }


def _compact_intake_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_row_id": _text(row.get("item_id")) or _text(row.get("operator_packet_binding_key")),
        "domain": _text(row.get("domain")),
        "priority": _text(row.get("priority")),
        "candidate_or_check": _text(row.get("candidate_or_check")),
        "required_evidence_type": _text(row.get("required_evidence_type")),
        "evidence_priority_bucket": _text(row.get("evidence_priority_bucket")),
        "source_artifact": _text(row.get("source_artifact")),
        "review_template_artifact": _text(row.get("review_template_artifact")),
        "operator_packet_binding_key": _text(row.get("operator_packet_binding_key")),
        "operator_packet_binding_ready": bool(row.get("operator_packet_binding_ready") is True),
        "evidence_intake_ready": bool(row.get("evidence_intake_ready") is True),
        "guardrail_ready": bool(row.get("guardrail_ready") is True),
        "scope_promotion_allowed": bool(row.get("scope_promotion_allowed") is True),
    }


def _compact_domain_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_row_id": _text(row.get("domain")),
        "domain": _text(row.get("domain")),
        "status": _text(row.get("status")),
        "artifact": _text(row.get("artifact")),
        "observed": _text(row.get("observed")),
        "requirement": _text(row.get("requirement")),
        "next_action": _text(row.get("next_action")),
        "release_blocker": bool(row.get("release_blocker") is True),
        "scope_widened": bool(row.get("scope_widened") is True),
    }


def _stage_evidence_row(
    *,
    stage: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    evidence_artifacts: list[str],
    blocked_evidence_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    blockers = blocked_evidence_rows if blocked_evidence_rows is not None else [
        row for row in evidence_rows if row.get("scope_promotion_allowed") is False or row.get("release_blocker") is True
    ]
    return {
        "stage_id": _text(stage.get("stage_id")),
        "status": _text(stage.get("status")),
        "artifact": _text(stage.get("artifact")),
        "required_checks": [str(item) for item in (stage.get("required_checks") or [])],
        "evidence_artifacts": [str(item) for item in evidence_artifacts if str(item)],
        "evidence_rows": evidence_rows,
        "evidence_row_count": len(evidence_rows),
        "blocked_evidence_rows": blockers,
        "blocked_evidence_row_count": len(blockers),
        "first_evidence_row": evidence_rows[0] if evidence_rows else {},
        "first_blocked_evidence_row": blockers[0] if blockers else {},
        "validation_command": _text(stage.get("validation_command")),
        "release_effect": _text(stage.get("release_effect")),
        "unlock_claim_scopes": [str(item) for item in (stage.get("unlock_claim_scopes") or [])],
        "next_action": _text(stage.get("next_action")),
        "release_blocker": bool(stage.get("release_blocker") is True),
        "execution_enabled": False,
        "scope_widened": False,
        "external_state_mutated": False,
    }


def _row(domain: str, ready: bool, artifact: str, observed: str, requirement: str, next_action: str) -> dict[str, Any]:
    return {
        "domain": domain,
        "status": "ready" if ready else "blocked",
        "artifact": artifact,
        "observed": observed,
        "requirement": requirement,
        "next_action": next_action,
        "release_blocker": not ready,
        "execution_enabled": False,
        "scope_widened": False,
        "external_state_mutated": False,
    }


def _acceptance_stage(
    *,
    stage_id: str,
    ready: bool,
    artifact: str,
    required_checks: list[str],
    release_effect: str,
    unlock_claim_scopes: list[str] | None = None,
    validation_command: str = "",
    next_action: str,
) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "status": "ready" if ready else "blocked",
        "artifact": artifact,
        "required_checks": required_checks,
        "validation_command": validation_command,
        "release_effect": release_effect,
        "unlock_claim_scopes": unlock_claim_scopes or [],
        "next_action": "" if ready else next_action,
        "release_blocker": not ready,
        "execution_enabled": False,
        "scope_widened": False,
        "external_state_mutated": False,
    }


def build_product_scope_breadth_contract(
    *,
    capability_packet: dict[str, Any],
    transporter_packet: dict[str, Any],
    ca2_packet: dict[str, Any],
    pxr_packet: dict[str, Any],
    idp_scaffold_packet: dict[str, Any],
    allatom_packet: dict[str, Any],
    transporter_reopen_packet: dict[str, Any] | None = None,
    transporter_binder_gate_packet: dict[str, Any] | None = None,
    transporter_p0_closure_packet: dict[str, Any] | None = None,
    transporter_p0_readiness_matrix_packet: dict[str, Any] | None = None,
    transporter_p0_evidence_acquisition_packet: dict[str, Any] | None = None,
    pxr_fill_readiness_packet: dict[str, Any] | None = None,
    pxr_blocked_gate_packet: dict[str, Any] | None = None,
    pxr_exact_review_intake_packet: dict[str, Any] | None = None,
    pxr_source_modality_triage_packet: dict[str, Any] | None = None,
    idp_promotion_resolution_packet: dict[str, Any] | None = None,
    evidence_queue_packet: dict[str, Any] | None = None,
    evidence_priority_packet: dict[str, Any] | None = None,
    evidence_intake_readiness_packet: dict[str, Any] | None = None,
    capability_path: str = DEFAULT_CAPABILITY_JSON,
    transporter_path: str = DEFAULT_TRANSPORTER_JSON,
    transporter_reopen_path: str = DEFAULT_TRANSPORTER_REOPEN_JSON,
    transporter_binder_gate_path: str = DEFAULT_TRANSPORTER_BINDER_GATE_JSON,
    transporter_p0_closure_path: str = DEFAULT_TRANSPORTER_P0_CLOSURE_JSON,
    transporter_p0_readiness_matrix_path: str = DEFAULT_TRANSPORTER_P0_READINESS_MATRIX_JSON,
    transporter_p0_evidence_acquisition_path: str = DEFAULT_TRANSPORTER_P0_EVIDENCE_ACQUISITION_JSON,
    ca2_path: str = DEFAULT_CA2_JSON,
    pxr_path: str = DEFAULT_PXR_JSON,
    pxr_fill_readiness_path: str = DEFAULT_PXR_FILL_READINESS_JSON,
    pxr_blocked_gate_path: str = DEFAULT_PXR_BLOCKED_GATE_JSON,
    pxr_exact_review_intake_path: str = DEFAULT_PXR_EXACT_REVIEW_INTAKE_JSON,
    pxr_source_modality_triage_path: str = DEFAULT_PXR_SOURCE_MODALITY_TRIAGE_JSON,
    idp_scaffold_path: str = DEFAULT_IDP_SCAFFOLD_JSON,
    idp_promotion_resolution_path: str = DEFAULT_IDP_PROMOTION_RESOLUTION_JSON,
    allatom_path: str = DEFAULT_ALLATOM_JSON,
    evidence_queue_path: str = DEFAULT_EVIDENCE_QUEUE_JSON,
    evidence_priority_path: str = DEFAULT_EVIDENCE_PRIORITY_JSON,
    evidence_intake_readiness_path: str = DEFAULT_EVIDENCE_INTAKE_READINESS_JSON,
) -> dict[str, Any]:
    capability = _summary(capability_packet)
    transporter = _summary(transporter_packet)
    transporter_reopen = _summary(transporter_reopen_packet or {})
    transporter_binder = _summary(transporter_binder_gate_packet or {})
    transporter_p0 = _summary(transporter_p0_closure_packet or {})
    transporter_p0_matrix = _summary(transporter_p0_readiness_matrix_packet or {})
    transporter_p0_evidence = _summary(transporter_p0_evidence_acquisition_packet or {})
    transporter_p0_evidence_first_row = _first_packet_row(transporter_p0_evidence_acquisition_packet or {})
    ca2 = _summary(ca2_packet)
    pxr_raw = pxr_packet if isinstance(pxr_packet, dict) else {}
    pxr = _summary(pxr_packet)
    pxr_fill = _summary(pxr_fill_readiness_packet or {})
    pxr_gate = _summary(pxr_blocked_gate_packet or {})
    pxr_exact_review = _summary(pxr_exact_review_intake_packet or {})
    pxr_source_modality = _summary(pxr_source_modality_triage_packet or {})
    idp = _summary(idp_scaffold_packet)
    idp_resolution = _summary(idp_promotion_resolution_packet or {})
    allatom = _summary(allatom_packet)
    evidence_queue = _summary(evidence_queue_packet or {})
    evidence_priority = _summary(evidence_priority_packet or {})
    evidence_intake = _summary(evidence_intake_readiness_packet or {})

    allowed_families = [str(item) for item in capability.get("allowed_scope_families") or []]
    transporter_ready = (
        _int(transporter.get("supportive_target_specific_packet_evidence_count")) >= 6
        and _int(transporter.get("pending_capture_count")) == 0
        and _int(transporter.get("placeholder_driven_rows")) == 0
        and _bool(transporter.get("donor_policy_reopen_ready"))
    )
    transporter_p0_open = next(
        (
            row.get("current_value")
            for row in (transporter_reopen_packet or {}).get("rows", []) or []
            if isinstance(row, dict) and row.get("check_id") == "p0_scaffold_open_count_zero"
        ),
        "",
    )
    transporter_binder_signal = transporter_binder.get("primary_blocker_signal") or ""
    transporter_claim_safe_binder_count = _int(transporter_binder.get("claim_safe_kcal_ready_count"))
    transporter_workbook_binder_count = _int(transporter_binder.get("workbook_ready_binder_row_count"))
    transporter_authoritative_binder_count = _int(transporter_binder.get("authoritative_binder_apply_allowed_count"))
    transporter_target_ready_for_promotion_ids = [
        str(item) for item in (transporter_binder.get("target_ready_for_promotion_ids") or [])
    ]
    transporter_target_blocked_for_promotion_ids = [
        str(item) for item in (transporter_binder.get("target_blocked_for_promotion_ids") or [])
    ]
    transporter_target_ready_for_promotion_count = _int(
        transporter_binder.get("target_ready_for_promotion_count")
    )
    transporter_target_blocked_for_promotion_count = _int(
        transporter_binder.get("target_blocked_for_promotion_count")
    )
    transporter_primary_blocker_target_id = _text(transporter_binder.get("primary_blocker_target_id"))
    transporter_primary_blocker_packet_step = _text(transporter_binder.get("primary_blocker_packet_step"))
    transporter_primary_blocker_candidate_name = _text(transporter_binder.get("primary_blocker_candidate_name"))
    transporter_p0_closure_packet_ready = _bool(transporter_p0.get("p0_closure_packet_ready"))
    transporter_p0_closure_row_count = _int(transporter_p0.get("closure_row_count"))
    transporter_p0_current_membrane_open_count = _int(transporter_p0.get("current_membrane_p0_open_count"))
    transporter_p0_aqp1_core_open_count = _int(transporter_p0.get("aqp1_core_p0_open_count"))
    transporter_p0_glut1_core_open_count = _int(transporter_p0.get("glut1_core_p0_open_count"))
    transporter_p0_count_matches_readiness = _bool(transporter_p0.get("p0_count_matches_readiness"))
    transporter_p0_glut1_reference_placeholders = _int(
        transporter_p0.get("glut1_reference_placeholder_rows_after_apply")
    )
    transporter_p0_glut1_split_placeholders = _int(
        transporter_p0.get("glut1_split_placeholder_rows_after_apply")
    )
    transporter_p0_glut1_meta_placeholders = _int(
        transporter_p0.get("glut1_meta_placeholder_rows_after_apply")
    )
    transporter_p0_next_required_step = _text(transporter_p0.get("next_required_step"))
    transporter_p0_readiness_matrix_ready = _bool(transporter_p0_matrix.get("readiness_matrix_ready"))
    transporter_p0_auto_close_ready_artifact_count = _int(
        transporter_p0_matrix.get("auto_close_ready_artifact_count")
    )
    transporter_p0_manual_or_external_required_artifact_count = _int(
        transporter_p0_matrix.get("manual_or_external_required_artifact_count")
    )
    transporter_p0_unresolved_slot_count = _int(transporter_p0_matrix.get("unresolved_slot_count"))
    transporter_p0_auto_close_ready_slot_count = _int(
        transporter_p0_matrix.get("auto_close_ready_slot_count")
    )
    transporter_p0_external_exact_evidence_required_slot_count = _int(
        transporter_p0_matrix.get("external_exact_evidence_required_slot_count")
    )
    transporter_p0_first_required_step_id = _text(
        transporter_p0_matrix.get("first_manual_or_external_required_step_id")
    )
    transporter_p0_first_required_slot_step = _text(
        transporter_p0_matrix.get("first_manual_or_external_required_slot_step")
    )
    transporter_p0_first_required_action = _text(
        transporter_p0_matrix.get("first_manual_or_external_required_action")
    )
    transporter_p0_evidence_acquisition_ready = _bool(
        transporter_p0_evidence.get("evidence_acquisition_packet_ready")
    )
    transporter_p0_evidence_acquisition_exact_request_slot_count = _int(
        transporter_p0_evidence.get("exact_evidence_request_slot_count")
    )
    transporter_p0_evidence_acquisition_unresolved_slot_count = _int(
        transporter_p0_evidence.get("unresolved_slot_count")
    )
    transporter_p0_evidence_acquisition_first_target_id = _text(
        transporter_p0_evidence_first_row.get("target_id")
    )
    transporter_p0_evidence_acquisition_first_packet_step = _text(
        transporter_p0_evidence_first_row.get("packet_step")
    )
    transporter_p0_evidence_acquisition_first_replacement_ligand_id = _text(
        transporter_p0_evidence_first_row.get("replacement_ligand_id")
    )
    transporter_p0_evidence_acquisition_first_request_mode = _text(
        transporter_p0_evidence_first_row.get("request_mode")
    )
    transporter_p0_evidence_acquisition_first_source_signal = _text(
        transporter_p0_evidence_first_row.get("source_signal")
    )
    transporter_p0_evidence_acquisition_first_required_missing_fields = _text(
        transporter_p0_evidence_first_row.get("required_missing_fields")
    )
    transporter_p0_evidence_acquisition_first_next_required_action = _text(
        transporter_p0_evidence_first_row.get("next_required_action")
    )
    transporter_p0_next_slot_completion_packet = (
        dict(transporter_p0_evidence.get("next_slot_completion_packet"))
        if isinstance(transporter_p0_evidence.get("next_slot_completion_packet"), dict)
        else {}
    )
    transporter_p0_next_slot_completion_packet_ready = _bool(
        transporter_p0_evidence.get("next_slot_completion_packet_ready")
    )
    transporter_p0_next_slot_return_bundle_matrix = (
        list(transporter_p0_evidence.get("next_slot_return_bundle_completion_matrix"))
        if isinstance(transporter_p0_evidence.get("next_slot_return_bundle_completion_matrix"), list)
        else []
    )
    ca2_ready = _int(ca2.get("verified_row_count")) >= 6 and _int(ca2.get("binder_row_count")) >= 3
    pxr_commit = pxr_raw.get("applied_commit_summary") if isinstance(pxr_raw.get("applied_commit_summary"), dict) else {}
    pxr_fill_present = bool(pxr_fill)
    pxr_blocked_rows = _int(
        pxr_fill.get("blocked_row_count")
        if pxr_fill_present
        else pxr_commit.get("blocked_row_count")
    )
    pxr_ready_rows = _int(
        pxr_fill.get("ready_for_apply_row_count")
        if pxr_fill_present
        else pxr_commit.get("ready_for_apply_row_count")
    )
    pxr_queue_rows = _int(pxr_fill.get("queue_row_count"))
    pxr_missing_field = str(pxr_fill.get("most_common_missing_field") or "none")
    pxr_promotion_ready = _bool(pxr_gate.get("promotion_ready"))
    pxr_claim_safe_quant_count = _int(pxr_gate.get("claim_safe_quantitative_ready_count"))
    pxr_authoritative_allowed_count = _int(pxr_gate.get("authoritative_apply_allowed_count"))
    pxr_gate_signal = str(pxr_gate.get("primary_blocker_signal") or "")
    pxr_exact_review_ready = _bool(pxr_exact_review.get("pxr_exact_review_intake_ready"))
    pxr_exact_review_row_count = _int(pxr_exact_review.get("review_template_row_count"))
    pxr_exact_review_conflict_required_count = _int(pxr_exact_review.get("conflict_resolution_required_count"))
    pxr_exact_review_kcal_placeholder_count = _int(pxr_exact_review.get("kcal_placeholder_count"))
    pxr_source_modality_guard_ready = _bool(pxr_source_modality.get("source_modality_guard_ready"))
    pxr_source_modality_conflict_surrogate_count = _int(
        pxr_source_modality.get("activity_proxy_or_conflict_surrogate_row_count")
    )
    pxr_source_modality_claim_safe_ready_count = _int(
        pxr_source_modality.get("direct_or_claim_safe_quantitative_ready_count")
    )
    pxr_source_modality_accepted_count = _int(
        pxr_source_modality.get("accepted_for_scope_promotion_count")
    )
    pxr_source_modality_apply_draft_ready = _bool(
        pxr_source_modality.get("direct_replacement_apply_draft_ready")
    )
    pxr_source_modality_apply_draft_overlay_count = _int(
        pxr_source_modality.get("direct_replacement_apply_draft_overlay_row_count")
    )
    pxr_source_modality_apply_draft_blocked_after = _int(
        pxr_source_modality.get("direct_replacement_apply_draft_blocked_row_count_after_draft")
    )
    pxr_exact_next_review_completion_packet = (
        dict(pxr_exact_review.get("next_review_completion_packet"))
        if isinstance(pxr_exact_review.get("next_review_completion_packet"), dict)
        else {}
    )
    pxr_exact_next_review_return_bundle_matrix = [
        dict(item)
        for item in (pxr_exact_review.get("next_review_return_bundle_completion_matrix") or [])
        if isinstance(item, dict)
    ]
    pxr_ready = (
        _bool(pxr.get("intake_applied"))
        and _int(pxr.get("captured_supportive_count")) >= 3
        and pxr_blocked_rows == 0
        and pxr_ready_rows >= 6
        and (not pxr_fill_present or pxr_queue_rows == pxr_ready_rows)
    )
    idp_full_broader_ready = (
        _bool(idp.get("broader_promotion_blocked")) is False
        and _int(idp.get("controlled_target_count")) >= 8
        and _int(idp.get("additional_anchor_backed_target_count")) > 0
    )
    idp_bounded_wider_lane_ready = (
        _bool(idp_resolution.get("wider_shadow_safe_lane_admitted"))
        and _bool(idp_resolution.get("shadow_safe_retained"))
        and _int(idp_resolution.get("frozen_validated_current_target_count")) >= 7
        and _int(idp_resolution.get("frozen_additional_anchor_backed_target_count")) > 0
        and _int(idp_resolution.get("frozen_total_target_count")) >= 8
        and _bool(idp_resolution.get("page4_fold_pass"))
        and _bool(idp_resolution.get("tau_k18_fold_pass"))
    )
    idp_ready = idp_full_broader_ready or idp_bounded_wider_lane_ready
    idp_artifact_path = idp_promotion_resolution_path if idp_bounded_wider_lane_ready else idp_scaffold_path
    idp_observed = (
        (
            f"bounded_wider_lane={idp_resolution.get('wider_shadow_safe_lane_admitted')};"
            f"shadow_safe={idp_resolution.get('shadow_safe_retained')};"
            f"validated_current={idp_resolution.get('frozen_validated_current_target_count')};"
            f"additional_anchor={idp_resolution.get('frozen_additional_anchor_backed_target_count')};"
            f"frozen_total={idp_resolution.get('frozen_total_target_count')};"
            f"blocked_scope={idp_resolution.get('blocked_scope')}"
        )
        if idp_bounded_wider_lane_ready
        else f"broader_blocked={idp.get('broader_promotion_blocked')};controlled={idp.get('controlled_target_count')};additional_anchor={idp.get('additional_anchor_backed_target_count')}"
    )
    idp_requirement = (
        "bounded one-wider IDP shadow-safe lane admitted with >=7 validated current targets, >=1 additional anchor-backed target, frozen total >=8, and no gate/state override"
        if idp_bounded_wider_lane_ready
        else "broader promotion unblocked with additional anchor-backed target beyond controlled scaffold"
    )
    idp_next_action = (
        "Keep IDP broad limited to the admitted one-wider shadow-safe lane; do not claim unrestricted broader IDP commercialization."
        if idp_bounded_wider_lane_ready
        else "Graduate at least one provisional IDP target to anchor-backed evidence and clear broader-promotion blocker."
    )
    allatom_ready = (
        _bool(allatom.get("claim_readiness_ready"))
        and _bool(allatom.get("strict_release_targets_supported"))
        and not allatom.get("missing_inputs")
    )
    if _int(transporter.get("placeholder_driven_rows")) > 0:
        transporter_next_action = "Replace placeholder transporter packet rows and reopen donor policy only when authoritative apply is safe."
    elif transporter_authoritative_binder_count <= 0:
        transporter_next_action = "Promote at least one claim-safe transporter binder row, then rerun donor-policy reopen gates."
    elif _int(transporter_p0_open) > 0:
        transporter_next_action = (
            transporter_p0_next_required_step
            or "Reduce transporter P0 scaffold open count to zero; claim-safe binder promotion is now present."
        )
    else:
        transporter_next_action = "Rerun transporter donor-policy gates and widen scope only after explicit product approval."
    general_ready = bool(
        set(REQUIRED_BREADTH_DOMAINS[:-1]).issubset(
            {
                domain
                for domain, ready in {
                    "transporter": transporter_ready,
                    "ca2": ca2_ready,
                    "pxr": pxr_ready,
                    "idp_broad": idp_ready,
                    "all_atom": allatom_ready,
                }.items()
                if ready
            }
        )
        and len(allowed_families) >= 6
        and _bool(capability.get("general_protein_ligand_platform_ready"))
    )
    rows = [
        _row(
            "transporter",
            transporter_ready,
            transporter_path,
            (
                f"supportive={transporter.get('supportive_target_specific_packet_evidence_count')};"
                f"pending={transporter.get('pending_capture_count')};placeholder={transporter.get('placeholder_driven_rows')};"
                f"donor_reopen={transporter.get('donor_policy_reopen_ready')};p0_open={transporter_p0_open};"
                f"claim_safe_binders={transporter_claim_safe_binder_count};workbook_binders={transporter_workbook_binder_count};"
                f"authoritative_binders={transporter_authoritative_binder_count};binder_signal={transporter_binder_signal};"
                f"p0_closure_ready={transporter_p0_closure_packet_ready};"
                f"target_ready_for_promotion={','.join(transporter_target_ready_for_promotion_ids)};"
                f"target_blocked_for_promotion={','.join(transporter_target_blocked_for_promotion_ids)};"
                f"primary_blocker_target={transporter_primary_blocker_target_id};"
                f"primary_blocker_step={transporter_primary_blocker_packet_step};"
                f"primary_blocker_candidate={transporter_primary_blocker_candidate_name};"
                f"p0_closure_rows={transporter_p0_closure_row_count};"
                f"p0_membrane_open={transporter_p0_current_membrane_open_count};"
                f"p0_aqp1_open={transporter_p0_aqp1_core_open_count};"
                f"p0_glut1_open={transporter_p0_glut1_core_open_count};"
                f"p0_count_matches_readiness={transporter_p0_count_matches_readiness};"
                f"p0_matrix_ready={transporter_p0_readiness_matrix_ready};"
                f"p0_auto_close_artifacts={transporter_p0_auto_close_ready_artifact_count};"
                f"p0_manual_or_external_artifacts={transporter_p0_manual_or_external_required_artifact_count};"
                f"p0_unresolved_slots={transporter_p0_unresolved_slot_count};"
                f"p0_external_exact_slots={transporter_p0_external_exact_evidence_required_slot_count}"
            ),
            "supportive transporter evidence, zero pending capture, zero placeholder rows, donor policy reopen ready, P0 open count zero, and at least one claim-safe binder row",
            transporter_next_action,
        ),
        _row(
            "ca2",
            ca2_ready,
            ca2_path,
            f"verified={ca2.get('verified_row_count')};binders={ca2.get('binder_row_count')};rows={ca2.get('row_count')}",
            ">=6 verified CA2 rows and >=3 binder rows",
            "Copy accepted CA2 verification values into the authoritative replacement workbook before API scope widening.",
        ),
        _row(
            "pxr",
            pxr_ready,
            pxr_fill_readiness_path if pxr_fill_present else pxr_path,
            (
                f"intake={pxr.get('intake_applied')};captured_supportive={pxr.get('captured_supportive_count')};"
                f"ready_for_apply={pxr_ready_rows};blocked_rows={pxr_blocked_rows};"
                f"queue_rows={pxr_queue_rows if pxr_fill_present else 'unknown'};missing_field={pxr_missing_field};"
                f"promotion_ready={pxr_promotion_ready};claim_safe_quantitative={pxr_claim_safe_quant_count};"
                f"authoritative_allowed={pxr_authoritative_allowed_count};gate_signal={pxr_gate_signal};"
                f"exact_review_intake_ready={pxr_exact_review_ready};"
                f"exact_review_rows={pxr_exact_review_row_count};"
                f"exact_review_conflict_required={pxr_exact_review_conflict_required_count};"
                f"exact_review_kcal_placeholders={pxr_exact_review_kcal_placeholder_count};"
                f"public_recheck_direct_binding={pxr_source_modality.get('public_recheck_chembl_direct_binding_total_record_count')};"
                f"public_recheck_bindingdb_pxr_like={pxr_source_modality.get('public_recheck_bindingdb_pxr_like_total_record_count')};"
                f"public_recheck_claim_safe_ready={pxr_source_modality.get('public_recheck_direct_or_claim_safe_binding_kcal_ready_count')};"
                f"direct_replacement_ready={pxr_source_modality.get('direct_replacement_candidate_packet_ready')};"
                f"direct_replacement_claim_safe={pxr_source_modality.get('direct_replacement_selected_claim_safe_candidate_count')};"
                f"direct_replacement_apply_draft_ready={pxr_source_modality_apply_draft_ready};"
                f"direct_replacement_apply_draft_blocked_after={pxr_source_modality_apply_draft_blocked_after}"
            ),
            "PXR intake applied, supportive evidence captured, zero blocked rows, and every packet-fill row ready for apply",
            (
                "Resolve remaining PXR packet-fill blocked rows with exact human NR1I2/PXR quantitative evidence; "
                "current gate blocks review-only/deferred row promotion."
                if pxr_gate
                else "Resolve remaining PXR packet-fill blocked rows, especially missing replacement reference binding kcal values, before authoritative product-scope promotion."
            ),
        ),
        _row(
            "idp_broad",
            idp_ready,
            idp_artifact_path,
            idp_observed,
            idp_requirement,
            idp_next_action,
        ),
        _row(
            "all_atom",
            allatom_ready,
            allatom_path,
            f"claim_ready={allatom.get('claim_readiness_ready')};strict_targets={allatom.get('strict_release_targets_supported')};missing_inputs={','.join(str(item) for item in allatom.get('missing_inputs') or [])}",
            "current all-atom handoff has claim readiness, strict target support, and no missing inputs",
            "Regenerate current all-atom claim inputs and strict summary so current handoff matches earlier readiness evidence.",
        ),
        _row(
            "general_protein_ligand",
            general_ready,
            capability_path,
            f"allowed_scope_families={','.join(allowed_families)};general_platform={capability.get('general_protein_ligand_platform_ready')}",
            "all breadth domains ready, >=6 allowed scope families, and explicit general platform flag",
            "Keep general protein-ligand platform wording blocked until all breadth domains are ready and API scope is explicitly widened.",
        ),
    ]
    ready_domains = [row["domain"] for row in rows if row["status"] == "ready"]
    missing_domains = [row["domain"] for row in rows if row["status"] != "ready"]
    first_blocked_domain_row = next((row for row in rows if row["status"] != "ready"), {})
    ready = not missing_domains
    restricted_scope_claim_allowed = bool(allowed_families)
    general_platform_claim_allowed = bool(ready and general_ready)
    blocked_claim_scopes = []
    if not transporter_ready:
        blocked_claim_scopes.append("transporter_domain_promotion")
    if not pxr_ready:
        blocked_claim_scopes.append("pxr_domain_promotion")
    if not general_platform_claim_allowed:
        blocked_claim_scopes.append("general_protein_ligand_platform")
    allowed_claim_scopes = []
    if restricted_scope_claim_allowed:
        allowed_claim_scopes.append("current_restricted_delivery_scope")
    if transporter_ready:
        allowed_claim_scopes.append("transporter_domain_evidence_ready_pending_product_decision")
    if pxr_ready:
        allowed_claim_scopes.append("pxr_domain_evidence_ready_pending_product_decision")
    if general_platform_claim_allowed:
        allowed_claim_scopes.append("general_protein_ligand_platform")
    scope_claim_posture_ready = (
        restricted_scope_claim_allowed
        and bool(allowed_claim_scopes)
        and (general_platform_claim_allowed or "general_protein_ligand_platform" in blocked_claim_scopes)
    )
    scope_claim_boundary_detail = (
        f"allowed_claim_scopes={','.join(allowed_claim_scopes) or 'none'};"
        f"blocked_claim_scopes={','.join(blocked_claim_scopes) or 'none'};"
        f"restricted_scope_claim_allowed={restricted_scope_claim_allowed};"
        f"general_platform_claim_allowed={general_platform_claim_allowed};"
        f"missing_domains={','.join(missing_domains) or 'none'}"
    )
    queue_ready = _bool(evidence_queue.get("queue_ready"))
    priority_packet_ready = _bool(evidence_priority.get("priority_packet_ready"))
    queue_item_count = _int(evidence_queue.get("queue_item_count"))
    priority_queue_item_count = _int(evidence_priority.get("queue_item_count"))
    scientific_evidence_request_count = _int(evidence_priority.get("scientific_evidence_request_count"))
    claim_gate_prerequisite_count = _int(evidence_priority.get("claim_gate_prerequisite_count"))
    local_crosscheck_candidate_count = _int(evidence_priority.get("local_crosscheck_candidate_count"))
    external_primary_exact_evidence_required_count = _int(
        evidence_priority.get("external_primary_exact_evidence_required_count")
    )
    review_only_keep_blocked_count = _int(evidence_priority.get("review_only_keep_blocked_count"))
    intake_packet_present = bool(evidence_intake)
    intake_readiness_ready = _bool(evidence_intake.get("intake_readiness_ready"))
    local_crosscheck_intake_ready_count = _int(evidence_intake.get("local_crosscheck_intake_ready_count"))
    local_crosscheck_unreadable_item_count = _int(evidence_intake.get("local_crosscheck_unreadable_item_count"))
    intake_external_exact_evidence_required_count = _int(evidence_intake.get("external_exact_evidence_required_count"))
    intake_guardrail_item_count = _int(evidence_intake.get("guardrail_item_count"))
    transporter_triage_packet_ready = _bool(evidence_intake.get("transporter_triage_packet_ready"))
    transporter_operator_review_evidence_matrix_ready = _bool(
        evidence_intake.get("transporter_operator_review_evidence_matrix_ready")
    )
    transporter_claim_safe_local_evidence_ready_count = _int(
        evidence_intake.get("transporter_claim_safe_local_evidence_ready_count")
    )
    transporter_claim_safe_local_evidence_blocked_count = _int(
        evidence_intake.get("transporter_claim_safe_local_evidence_blocked_count")
    )
    transporter_direct_binding_claim_blocked_count = _int(
        evidence_intake.get("transporter_direct_binding_claim_blocked_count")
    )
    transporter_negative_value_claim_blocked_count = _int(
        evidence_intake.get("transporter_negative_value_claim_blocked_count")
    )
    transporter_top_claim_safe_blocker = _text(evidence_intake.get("transporter_top_claim_safe_blocker"))
    transporter_top_operator_next_verdict = _text(evidence_intake.get("transporter_top_operator_next_verdict"))
    transporter_candidate_assignment_required_count = _int(
        evidence_intake.get("transporter_candidate_assignment_required_count")
    )
    transporter_functional_direct_gap_count = _int(
        evidence_intake.get("transporter_functional_quantitative_only_direct_gap_open_count")
    )
    transporter_review_only_direct_binding_gap_count = _int(
        evidence_intake.get("transporter_review_only_direct_binding_gap_count")
    )
    transporter_local_can_close_without_assignment = _bool(
        evidence_intake.get("transporter_local_crosscheck_can_close_slots_without_manual_assignment")
    )
    transporter_candidate_workbook_ready = _bool(evidence_intake.get("transporter_candidate_workbook_ready"))
    transporter_candidate_row_count = _int(evidence_intake.get("transporter_candidate_row_count"))
    transporter_candidate_ready_for_manual_review_count = _int(
        evidence_intake.get("transporter_candidate_ready_for_manual_review_count")
    )
    transporter_candidate_ready_for_apply_count = _int(
        evidence_intake.get("transporter_candidate_ready_for_apply_count")
    )
    transporter_candidate_negative_value_review_required_count = _int(
        evidence_intake.get("transporter_candidate_negative_value_review_required_count")
    )
    transporter_manual_review_intake_ready = _bool(evidence_intake.get("transporter_manual_review_intake_ready"))
    transporter_manual_review_template_row_count = _int(
        evidence_intake.get("transporter_manual_review_template_row_count")
    )
    transporter_manual_review_direct_binding_required_count = _int(
        evidence_intake.get("transporter_manual_review_direct_binding_evidence_required_count")
    )
    transporter_manual_review_negative_value_required_count = _int(
        evidence_intake.get("transporter_manual_review_negative_quantitative_value_required_count")
    )
    transporter_manual_review_decision_placeholder_count = _int(
        evidence_intake.get("transporter_manual_review_decision_placeholder_count")
    )
    transporter_manual_review_p0_slot_overlay_row_count = _int(
        evidence_intake.get("transporter_manual_review_p0_slot_overlay_row_count")
    )
    transporter_manual_review_p0_slot_overlay_candidate_changed_count = _int(
        evidence_intake.get("transporter_manual_review_p0_slot_overlay_candidate_changed_count")
    )
    transporter_manual_review_p0_slot_overlay_first_item_id = _text(
        evidence_intake.get("transporter_manual_review_p0_slot_overlay_first_item_id")
    )
    transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id = _text(
        evidence_intake.get("transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id")
    )
    transporter_manual_review_p0_slot_overlay_first_source = _text(
        evidence_intake.get("transporter_manual_review_p0_slot_overlay_first_source")
    )
    acquisition_plan_ready = (
        True
        if ready
        else (
            queue_ready
            and priority_packet_ready
            and queue_item_count > 0
            and priority_queue_item_count == queue_item_count
            and scientific_evidence_request_count > 0
            and claim_gate_prerequisite_count > 0
            and (not intake_packet_present or intake_readiness_ready)
        )
    )
    acquisition_next_step = (
        _text(evidence_intake.get("next_required_step"))
        or _text(evidence_priority.get("next_required_step"))
        or _text(evidence_queue.get("next_required_step"))
    )
    scope_acceptance_rows = [
        _acceptance_stage(
            stage_id="scope_evidence_acquisition_preflight",
            ready=acquisition_plan_ready,
            artifact=f"{evidence_queue_path};{evidence_priority_path};{evidence_intake_readiness_path}",
            required_checks=[
                "evidence_queue_ready",
                "evidence_priority_packet_ready",
                "evidence_intake_readiness_ready",
                "scientific_evidence_request_count_positive",
            ],
            validation_command=(
                "python3 tools/build_product_scope_breadth_evidence_acquisition_queue.py && "
                "python3 tools/build_product_scope_breadth_evidence_priority_packet.py && "
                "python3 tools/build_product_scope_breadth_evidence_intake_readiness.py"
            ),
            release_effect="scope-evidence work queue and operator intake packets are actionable",
            next_action=(
                acquisition_next_step
                or "Rebuild scope evidence acquisition, priority, and intake-readiness packets."
            ),
        ),
        _acceptance_stage(
            stage_id="transporter_claim_acceptance",
            ready=transporter_ready,
            artifact=(
                f"{transporter_path};{transporter_binder_gate_path};{evidence_intake_readiness_path};"
                f"{transporter_p0_readiness_matrix_path}"
            ),
            required_checks=[
                "transporter_claim_safe_local_evidence_ready",
                "transporter_direct_binding_claim_blockers_zero",
                "transporter_negative_value_claim_blockers_zero",
                "transporter_p0_open_count_zero",
                "transporter_donor_policy_reopen_ready",
            ],
            validation_command=(
                "python3 tools/build_transporter_manual_review_intake_template.py && "
                "python3 tools/build_transporter_binder_promotion_gate.py && "
                "python3 tools/build_transporter_p0_closure_packet.py && "
                "python3 tools/build_transporter_p0_evidence_acquisition_packet.py && "
                "python3 tools/build_transporter_p0_closure_readiness_matrix.py && "
                "python3 tools/build_product_scope_breadth_contract.py"
            ),
            release_effect="transporter domain can move from blocked claim to evidence-ready pending product decision",
            unlock_claim_scopes=["transporter_domain_promotion"],
            next_action=transporter_next_action,
        ),
        _acceptance_stage(
            stage_id="pxr_claim_acceptance",
            ready=pxr_ready,
            artifact=(
                f"{pxr_fill_readiness_path};{pxr_blocked_gate_path};"
                f"{pxr_exact_review_intake_path};{pxr_source_modality_triage_path}"
            ),
            required_checks=[
                "pxr_exact_review_rows_filled",
                "pxr_conflicts_resolved",
                "pxr_kcal_placeholders_zero",
                "pxr_blocked_rows_zero",
                "pxr_authoritative_apply_allowed",
            ],
            validation_command=(
                "python3 tools/build_pxr_exact_evidence_review_intake_template.py && "
                "python3 tools/build_pxr_blocked_row_promotion_gate.py && "
                "python3 tools/build_pxr_authoritative_reconciliation_packet.py && "
                "python3 tools/build_product_scope_breadth_contract.py"
            ),
            release_effect="PXR domain can move from blocked claim to evidence-ready pending product decision",
            unlock_claim_scopes=["pxr_domain_promotion"],
            next_action=(
                "Resolve remaining PXR packet-fill blocked rows with exact human NR1I2/PXR quantitative evidence."
            ),
        ),
        _acceptance_stage(
            stage_id="breadth_domain_floor_acceptance",
            ready=all(row["status"] == "ready" for row in rows[:-1]),
            artifact=DEFAULT_OUT_JSON,
            required_checks=[
                "transporter_ready",
                "ca2_ready",
                "pxr_ready",
                "idp_broad_ready",
                "all_atom_ready",
            ],
            validation_command="python3 tools/build_product_scope_breadth_contract.py",
            release_effect="all named breadth domains are evidence-ready before any broad platform wording",
            unlock_claim_scopes=["domain_floor_ready_for_general_platform_review"],
            next_action="Finish transporter and PXR evidence gates before any general platform claim review.",
        ),
        _acceptance_stage(
            stage_id="general_platform_claim_acceptance",
            ready=general_platform_claim_allowed,
            artifact=capability_path,
            required_checks=[
                "all_breadth_domains_ready",
                "allowed_scope_family_count_at_least_6",
                "explicit_general_protein_ligand_platform_flag",
            ],
            validation_command=(
                "python3 tools/build_product_capability_surface_contract.py && "
                "python3 tools/build_product_scope_breadth_contract.py"
            ),
            release_effect="general protein-ligand platform claim can be allowed by the product surface",
            unlock_claim_scopes=["general_protein_ligand_platform"],
            next_action=(
                "Keep general protein-ligand platform wording blocked until all breadth domains are ready and the "
                "capability surface explicitly allows it."
            ),
        ),
    ]
    scope_acceptance_blockers = [row for row in scope_acceptance_rows if row["status"] != "ready"]
    first_scope_acceptance_blocker = scope_acceptance_blockers[0] if scope_acceptance_blockers else {}
    scope_acceptance_matrix_ready = bool(scope_acceptance_rows) and acquisition_plan_ready
    scope_claim_expansion_contract_ready = scope_acceptance_matrix_ready
    scope_claim_expansion_currently_satisfied = bool(
        ready and general_platform_claim_allowed and not scope_acceptance_blockers
    )
    scope_claim_expansion_current_blocked_stage_ids = [
        str(row["stage_id"]) for row in scope_acceptance_blockers
    ]
    evidence_intake_rows = [_compact_intake_row(row) for row in _packet_rows(evidence_intake_readiness_packet or {})]
    evidence_intake_blockers = [
        row
        for row in evidence_intake_rows
        if row.get("evidence_intake_ready") is not True or row.get("operator_packet_binding_ready") is not True
    ]
    transporter_stage_evidence_rows = [
        _compact_transporter_evidence_row(row)
        for row in _packet_rows(transporter_p0_evidence_acquisition_packet or {})
    ]
    transporter_stage_evidence_blockers = [
        row
        for row in transporter_stage_evidence_rows
        if (
            row.get("scope_promotion_allowed") is not True
            or bool(row.get("required_missing_fields"))
            or row.get("claim_safe_step_ready") is not True
        )
    ]
    pxr_stage_evidence_rows = [
        _compact_pxr_review_row(row) for row in _packet_rows(pxr_exact_review_intake_packet or {})
    ]
    pxr_stage_evidence_blockers = [
        row
        for row in pxr_stage_evidence_rows
        if (
            row.get("scope_promotion_allowed") is not True
            or row.get("authoritative_apply_allowed") is not True
            or bool(row.get("readiness_missing_fields"))
            or bool(row.get("fail_closed_blockers"))
            or bool(row.get("conflict_resolution_required"))
            or str(row.get("replacement_reference_binding_kcal_mol") or "").startswith("OPERATOR_FILL")
            or str(row.get("replacement_source_url_or_doi") or "").startswith("OPERATOR_FILL")
            or str(row.get("target_match_confirmed") or "").startswith("OPERATOR_FILL")
            or str(row.get("review_decision") or "").startswith("OPERATOR_FILL")
        )
    ]
    domain_floor_evidence_rows = [_compact_domain_row(row) for row in rows[:-1]]
    domain_floor_evidence_blockers = [
        row for row in domain_floor_evidence_rows if row.get("status") != "ready"
    ]
    general_platform_evidence_rows = [_compact_domain_row(row) for row in rows]
    general_platform_evidence_blockers = [
        row for row in general_platform_evidence_rows if row.get("status") != "ready"
    ]
    stage_by_id = {str(row["stage_id"]): row for row in scope_acceptance_rows}
    scope_acceptance_stage_evidence_matrix = [
        _stage_evidence_row(
            stage=stage_by_id["scope_evidence_acquisition_preflight"],
            evidence_rows=evidence_intake_rows,
            blocked_evidence_rows=evidence_intake_blockers,
            evidence_artifacts=[
                evidence_queue_path,
                evidence_priority_path,
                evidence_intake_readiness_path,
            ],
        ),
        _stage_evidence_row(
            stage=stage_by_id["transporter_claim_acceptance"],
            evidence_rows=transporter_stage_evidence_rows,
            blocked_evidence_rows=transporter_stage_evidence_blockers,
            evidence_artifacts=[
                transporter_p0_evidence_acquisition_path,
                transporter_p0_readiness_matrix_path,
                evidence_intake_readiness_path,
            ],
        ),
        _stage_evidence_row(
            stage=stage_by_id["pxr_claim_acceptance"],
            evidence_rows=pxr_stage_evidence_rows,
            blocked_evidence_rows=pxr_stage_evidence_blockers,
            evidence_artifacts=[
                pxr_exact_review_intake_path,
                pxr_fill_readiness_path,
                pxr_blocked_gate_path,
                pxr_source_modality_triage_path,
            ],
        ),
        _stage_evidence_row(
            stage=stage_by_id["breadth_domain_floor_acceptance"],
            evidence_rows=domain_floor_evidence_rows,
            blocked_evidence_rows=domain_floor_evidence_blockers,
            evidence_artifacts=[
                transporter_path,
                ca2_path,
                pxr_path,
                idp_artifact_path,
                allatom_path,
            ],
        ),
        _stage_evidence_row(
            stage=stage_by_id["general_platform_claim_acceptance"],
            evidence_rows=general_platform_evidence_rows,
            blocked_evidence_rows=general_platform_evidence_blockers,
            evidence_artifacts=[capability_path, DEFAULT_OUT_JSON],
        ),
    ]
    scope_acceptance_current_blocked_stage_evidence_matrix = [
        row for row in scope_acceptance_stage_evidence_matrix if row["status"] != "ready"
    ]
    summary = {
        "packet_type": "product_scope_breadth_contract",
        "status": "product_scope_breadth_contract_ready" if ready else "blocked_product_scope_breadth_contract",
        "scope_breadth_ready": ready,
        "scope_breadth_acquisition_plan_ready": acquisition_plan_ready,
        "evidence_queue_ready": queue_ready,
        "evidence_priority_packet_ready": priority_packet_ready,
        "evidence_intake_readiness_ready": intake_readiness_ready,
        "evidence_queue_item_count": queue_item_count,
        "evidence_queue_next_operator_completion_packet_ready": _bool(
            evidence_queue.get("next_operator_completion_packet_ready")
        ),
        "evidence_queue_next_operator_completion_slot_id": _text(
            evidence_queue.get("next_operator_completion_slot_id")
        ),
        "evidence_queue_next_operator_completion_expected_evidence_type": _text(
            evidence_queue.get("next_operator_completion_expected_evidence_type")
        ),
        "evidence_queue_next_operator_completion_required_exact_evidence_field_count": _int(
            evidence_queue.get("next_operator_completion_required_exact_evidence_field_count")
        ),
        "evidence_queue_next_operator_completion_required_exact_evidence_fields": _text(
            evidence_queue.get("next_operator_completion_required_exact_evidence_fields")
        ),
        "evidence_queue_next_operator_completion_required_operator_intake_columns": _text(
            evidence_queue.get("next_operator_completion_required_operator_intake_columns")
        ),
        "evidence_queue_next_operator_completion_required_claim_guardrails": _text(
            evidence_queue.get("next_operator_completion_required_claim_guardrails")
        ),
        "evidence_queue_next_operator_completion_operator_review_artifact": _text(
            evidence_queue.get("next_operator_completion_operator_review_artifact")
        ),
        "evidence_queue_next_operator_completion_post_intake_synchronization_targets": _text(
            evidence_queue.get("next_operator_completion_post_intake_synchronization_targets")
        ),
        "evidence_queue_next_operator_completion_acceptance_gate_commands": _text(
            evidence_queue.get("next_operator_completion_acceptance_gate_commands")
        ),
        "evidence_queue_next_operator_completion_contract_artifact": _text(
            evidence_queue.get("next_operator_completion_contract_artifact")
        ),
        "evidence_queue_next_operator_completion_aqp1_review_sidecar_ready": _bool(
            evidence_queue.get("next_operator_completion_aqp1_review_sidecar_ready")
        ),
        "evidence_queue_next_operator_completion_aqp1_functional_surrogate_artifact": _text(
            evidence_queue.get("next_operator_completion_aqp1_functional_surrogate_artifact")
        ),
        "evidence_queue_next_operator_completion_aqp1_candidate_ledger_artifact": _text(
            evidence_queue.get("next_operator_completion_aqp1_candidate_ledger_artifact")
        ),
        "evidence_queue_next_operator_completion_aqp1_review_candidate_name": _text(
            evidence_queue.get("next_operator_completion_aqp1_review_candidate_name")
        ),
        "evidence_queue_next_operator_completion_aqp1_review_source_anchor": _text(
            evidence_queue.get("next_operator_completion_aqp1_review_source_anchor")
        ),
        "evidence_queue_next_operator_completion_aqp1_review_source_url": _text(
            evidence_queue.get("next_operator_completion_aqp1_review_source_url")
        ),
        "evidence_queue_next_operator_completion_aqp1_review_target_uniprot": _text(
            evidence_queue.get("next_operator_completion_aqp1_review_target_uniprot")
        ),
        "evidence_queue_next_operator_completion_aqp1_review_functional_measure": _text(
            evidence_queue.get("next_operator_completion_aqp1_review_functional_measure")
        ),
        "evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": _text(
            evidence_queue.get(
                "next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol"
            )
        ),
        "evidence_queue_next_operator_completion_aqp1_review_assay_type_honesty": _text(
            evidence_queue.get("next_operator_completion_aqp1_review_assay_type_honesty")
        ),
        "evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed": _text(
            evidence_queue.get("next_operator_completion_aqp1_review_direct_binding_claim_allowed")
        ),
        "evidence_queue_next_operator_completion_aqp1_review_binding_kcal_claim_allowed": _text(
            evidence_queue.get("next_operator_completion_aqp1_review_binding_kcal_claim_allowed")
        ),
        "evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": _text(
            evidence_queue.get(
                "next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank"
            )
        ),
        "evidence_queue_next_operator_completion_aqp1_review_claim_safe_functional_kcal_ready": _text(
            evidence_queue.get("next_operator_completion_aqp1_review_claim_safe_functional_kcal_ready")
        ),
        "evidence_queue_next_operator_completion_aqp1_review_ledger_review_bucket": _text(
            evidence_queue.get("next_operator_completion_aqp1_review_ledger_review_bucket")
        ),
        "evidence_queue_next_operator_completion_aqp1_review_ledger_promotion_policy": _text(
            evidence_queue.get("next_operator_completion_aqp1_review_ledger_promotion_policy")
        ),
        "evidence_queue_next_operator_completion_aqp1_review_ledger_caution": _text(
            evidence_queue.get("next_operator_completion_aqp1_review_ledger_caution")
        ),
        "evidence_queue_pxr_exact_review_sidecar_row_count": _int(
            evidence_queue.get("pxr_exact_review_sidecar_row_count")
        ),
        "evidence_queue_next_pxr_exact_review_sidecar_ready": _bool(
            evidence_queue.get("next_pxr_exact_review_sidecar_ready")
        ),
        "evidence_queue_next_pxr_exact_review_row_id": _text(
            evidence_queue.get("next_pxr_exact_review_row_id")
        ),
        "evidence_queue_next_pxr_exact_review_candidate_name": _text(
            evidence_queue.get("next_pxr_exact_review_candidate_name")
        ),
        "evidence_queue_next_pxr_exact_review_required_evidence_mode": _text(
            evidence_queue.get("next_pxr_exact_review_required_evidence_mode")
        ),
        "evidence_queue_next_pxr_exact_review_target_match_confirmed": _text(
            evidence_queue.get("next_pxr_exact_review_target_match_confirmed")
        ),
        "evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol": _text(
            evidence_queue.get("next_pxr_exact_review_replacement_reference_binding_kcal_mol")
        ),
        "evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi": _text(
            evidence_queue.get("next_pxr_exact_review_replacement_source_url_or_doi")
        ),
        "evidence_queue_next_pxr_exact_review_authoritative_apply_allowed": _bool(
            evidence_queue.get("next_pxr_exact_review_authoritative_apply_allowed")
        ),
        "evidence_queue_next_pxr_exact_review_scope_promotion_allowed": _bool(
            evidence_queue.get("next_pxr_exact_review_scope_promotion_allowed")
        ),
        "evidence_priority_queue_item_count": priority_queue_item_count,
        "scientific_evidence_request_count": scientific_evidence_request_count,
        "claim_gate_prerequisite_count": claim_gate_prerequisite_count,
        "local_crosscheck_candidate_count": local_crosscheck_candidate_count,
        "local_crosscheck_intake_ready_count": local_crosscheck_intake_ready_count,
        "local_crosscheck_unreadable_item_count": local_crosscheck_unreadable_item_count,
        "external_primary_exact_evidence_required_count": external_primary_exact_evidence_required_count,
        "intake_external_exact_evidence_required_count": intake_external_exact_evidence_required_count,
        "review_only_keep_blocked_count": review_only_keep_blocked_count,
        "intake_guardrail_item_count": intake_guardrail_item_count,
        "transporter_triage_packet_ready": transporter_triage_packet_ready,
        "transporter_operator_review_evidence_matrix_ready": transporter_operator_review_evidence_matrix_ready,
        "transporter_claim_safe_local_evidence_ready_count": transporter_claim_safe_local_evidence_ready_count,
        "transporter_claim_safe_local_evidence_blocked_count": transporter_claim_safe_local_evidence_blocked_count,
        "transporter_direct_binding_claim_blocked_count": transporter_direct_binding_claim_blocked_count,
        "transporter_negative_value_claim_blocked_count": transporter_negative_value_claim_blocked_count,
        "transporter_top_claim_safe_blocker": transporter_top_claim_safe_blocker,
        "transporter_top_operator_next_verdict": transporter_top_operator_next_verdict,
        "transporter_target_ready_for_promotion_count": transporter_target_ready_for_promotion_count,
        "transporter_target_blocked_for_promotion_count": transporter_target_blocked_for_promotion_count,
        "transporter_target_ready_for_promotion_ids": transporter_target_ready_for_promotion_ids,
        "transporter_target_blocked_for_promotion_ids": transporter_target_blocked_for_promotion_ids,
        "transporter_primary_blocker_target_id": transporter_primary_blocker_target_id,
        "transporter_primary_blocker_packet_step": transporter_primary_blocker_packet_step,
        "transporter_primary_blocker_candidate_name": transporter_primary_blocker_candidate_name,
        "transporter_candidate_assignment_required_count": transporter_candidate_assignment_required_count,
        "transporter_functional_direct_gap_count": transporter_functional_direct_gap_count,
        "transporter_review_only_direct_binding_gap_count": transporter_review_only_direct_binding_gap_count,
        "transporter_local_crosscheck_can_close_slots_without_manual_assignment": (
            transporter_local_can_close_without_assignment
        ),
        "transporter_candidate_workbook_ready": transporter_candidate_workbook_ready,
        "transporter_candidate_row_count": transporter_candidate_row_count,
        "transporter_candidate_ready_for_manual_review_count": transporter_candidate_ready_for_manual_review_count,
        "transporter_candidate_ready_for_apply_count": transporter_candidate_ready_for_apply_count,
        "transporter_candidate_negative_value_review_required_count": (
            transporter_candidate_negative_value_review_required_count
        ),
        "transporter_manual_review_intake_ready": transporter_manual_review_intake_ready,
        "transporter_manual_review_template_row_count": transporter_manual_review_template_row_count,
        "transporter_manual_review_direct_binding_evidence_required_count": (
            transporter_manual_review_direct_binding_required_count
        ),
        "transporter_manual_review_negative_quantitative_value_required_count": (
            transporter_manual_review_negative_value_required_count
        ),
        "transporter_manual_review_decision_placeholder_count": transporter_manual_review_decision_placeholder_count,
        "transporter_manual_review_p0_slot_overlay_row_count": (
            transporter_manual_review_p0_slot_overlay_row_count
        ),
        "transporter_manual_review_p0_slot_overlay_candidate_changed_count": (
            transporter_manual_review_p0_slot_overlay_candidate_changed_count
        ),
        "transporter_manual_review_p0_slot_overlay_first_item_id": (
            transporter_manual_review_p0_slot_overlay_first_item_id
        ),
        "transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id": (
            transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id
        ),
        "transporter_manual_review_p0_slot_overlay_first_source": (
            transporter_manual_review_p0_slot_overlay_first_source
        ),
        "transporter_p0_closure_packet_ready": transporter_p0_closure_packet_ready,
        "transporter_p0_closure_artifact": transporter_p0_closure_path,
        "transporter_p0_current_membrane_open_count": transporter_p0_current_membrane_open_count,
        "transporter_p0_closure_row_count": transporter_p0_closure_row_count,
        "transporter_p0_count_matches_readiness": transporter_p0_count_matches_readiness,
        "transporter_p0_aqp1_core_open_count": transporter_p0_aqp1_core_open_count,
        "transporter_p0_glut1_core_open_count": transporter_p0_glut1_core_open_count,
        "transporter_p0_glut1_reference_placeholder_rows_after_apply": (
            transporter_p0_glut1_reference_placeholders
        ),
        "transporter_p0_glut1_split_placeholder_rows_after_apply": (
            transporter_p0_glut1_split_placeholders
        ),
        "transporter_p0_glut1_meta_placeholder_rows_after_apply": transporter_p0_glut1_meta_placeholders,
        "transporter_p0_next_required_step": transporter_p0_next_required_step,
        "transporter_p0_readiness_matrix_ready": transporter_p0_readiness_matrix_ready,
        "transporter_p0_readiness_matrix_artifact": transporter_p0_readiness_matrix_path,
        "transporter_p0_auto_close_ready_artifact_count": transporter_p0_auto_close_ready_artifact_count,
        "transporter_p0_manual_or_external_required_artifact_count": (
            transporter_p0_manual_or_external_required_artifact_count
        ),
        "transporter_p0_unresolved_slot_count": transporter_p0_unresolved_slot_count,
        "transporter_p0_auto_close_ready_slot_count": transporter_p0_auto_close_ready_slot_count,
        "transporter_p0_external_exact_evidence_required_slot_count": (
            transporter_p0_external_exact_evidence_required_slot_count
        ),
        "transporter_p0_first_manual_or_external_required_step_id": transporter_p0_first_required_step_id,
        "transporter_p0_first_manual_or_external_required_slot_step": transporter_p0_first_required_slot_step,
        "transporter_p0_first_manual_or_external_required_action": transporter_p0_first_required_action,
        "transporter_p0_evidence_acquisition_packet_ready": transporter_p0_evidence_acquisition_ready,
        "transporter_p0_evidence_acquisition_artifact": transporter_p0_evidence_acquisition_path,
        "transporter_p0_evidence_acquisition_exact_request_slot_count": (
            transporter_p0_evidence_acquisition_exact_request_slot_count
        ),
        "transporter_p0_evidence_acquisition_unresolved_slot_count": (
            transporter_p0_evidence_acquisition_unresolved_slot_count
        ),
        "transporter_p0_evidence_acquisition_first_target_id": (
            transporter_p0_evidence_acquisition_first_target_id
        ),
        "transporter_p0_evidence_acquisition_first_packet_step": (
            transporter_p0_evidence_acquisition_first_packet_step
        ),
        "transporter_p0_evidence_acquisition_first_replacement_ligand_id": (
            transporter_p0_evidence_acquisition_first_replacement_ligand_id
        ),
        "transporter_p0_evidence_acquisition_first_request_mode": (
            transporter_p0_evidence_acquisition_first_request_mode
        ),
        "transporter_p0_evidence_acquisition_first_source_signal": (
            transporter_p0_evidence_acquisition_first_source_signal
        ),
        "transporter_p0_evidence_acquisition_first_required_missing_fields": (
            transporter_p0_evidence_acquisition_first_required_missing_fields
        ),
        "transporter_p0_evidence_acquisition_first_next_required_action": (
            transporter_p0_evidence_acquisition_first_next_required_action
        ),
        "transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": (
            transporter_p0_next_slot_completion_packet_ready
        ),
        "transporter_p0_evidence_acquisition_next_slot_completion_packet": (
            transporter_p0_next_slot_completion_packet
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts": [
            str(item) for item in (transporter_p0_evidence.get("next_slot_return_bundle_required_artifacts") or [])
        ],
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count": _int(
            transporter_p0_evidence.get("next_slot_return_bundle_required_artifact_count")
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix": (
            transporter_p0_next_slot_return_bundle_matrix
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count": _int(
            transporter_p0_evidence.get("next_slot_return_bundle_completion_matrix_count")
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count": _int(
            transporter_p0_evidence.get("next_slot_return_bundle_blocker_count")
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id": _text(
            transporter_p0_evidence.get("next_slot_return_bundle_next_artifact_id")
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path": _text(
            transporter_p0_evidence.get("next_slot_return_bundle_next_artifact_path")
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_failed_check_ids": [
            str(item)
            for item in (
                transporter_p0_evidence.get("next_slot_return_bundle_next_artifact_failed_check_ids") or []
            )
        ],
        "transporter_p0_evidence_acquisition_next_slot_id": _text(
            transporter_p0_evidence.get("next_evidence_slot_id")
        ),
        "transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": _text(
            transporter_p0_evidence.get("next_evidence_slot_operator_review_artifact")
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready": _bool(
            transporter_p0_evidence.get("next_slot_source_modality_guard_ready")
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality": _text(
            transporter_p0_evidence.get("next_slot_source_modality")
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe": _bool(
            transporter_p0_evidence.get("next_slot_source_modality_claim_safe")
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed": _bool(
            transporter_p0_evidence.get("next_slot_source_modality_direct_binding_claim_allowed")
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_decision": _text(
            transporter_p0_evidence.get("next_slot_source_modality_decision")
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails": [
            str(item) for item in (transporter_p0_evidence.get("next_slot_source_modality_guardrails") or [])
        ],
        "transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal": _text(
            transporter_p0_evidence.get("next_slot_source_modality_observed_signal")
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade": _text(
            transporter_p0_evidence.get("next_slot_source_modality_required_upgrade")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_ready": _bool(
            transporter_p0_evidence.get("aqp1_binding_source_modality_triage_ready")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_status": _text(
            transporter_p0_evidence.get("aqp1_binding_source_modality_triage_status")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_artifact": _text(
            transporter_p0_evidence.get("aqp1_binding_source_modality_triage_artifact")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_decision": _text(
            transporter_p0_evidence.get("aqp1_binding_source_modality_triage_decision")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_experimental_binding_row_count": _int(
            transporter_p0_evidence.get("aqp1_binding_source_modality_direct_experimental_binding_row_count")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count": _int(
            transporter_p0_evidence.get("aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_ready": _bool(
            transporter_p0_evidence.get("aqp1_binding_source_modality_public_direct_binding_recheck_ready")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count": _int(
            transporter_p0_evidence.get("aqp1_binding_source_modality_public_direct_binding_recheck_source_count")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result": _text(
            transporter_p0_evidence.get("aqp1_binding_source_modality_public_direct_binding_recheck_result")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count": _int(
            transporter_p0_evidence.get("aqp1_binding_source_modality_public_database_recheck_row_count")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count": _int(
            transporter_p0_evidence.get("aqp1_binding_source_modality_ligand_identity_mismatch_row_count")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_row_count": _int(
            transporter_p0_evidence.get("aqp1_binding_source_modality_direct_like_binding_candidate_row_count")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_claim_safe_ready_count": _int(
            transporter_p0_evidence.get(
                "aqp1_binding_source_modality_direct_like_binding_candidate_claim_safe_ready_count"
            )
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_row_count": _int(
            transporter_p0_evidence.get(
                "aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_row_count"
            )
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_claim_safe_row_count": _int(
            transporter_p0_evidence.get(
                "aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_claim_safe_row_count"
            )
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_chembl_id": _text(
            transporter_p0_evidence.get(
                "aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_chembl_id"
            )
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol": _text(
            transporter_p0_evidence.get(
                "aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol"
            )
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_blocker": _text(
            transporter_p0_evidence.get(
                "aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_blocker"
            )
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_affinity_row_count": _int(
            transporter_p0_evidence.get(
                "aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_affinity_row_count"
            )
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count": _int(
            transporter_p0_evidence.get(
                "aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count"
            )
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_best_functional_ic50_nM": _text(
            transporter_p0_evidence.get(
                "aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_best_functional_ic50_nM"
            )
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid": _text(
            transporter_p0_evidence.get("aqp1_binding_source_modality_bacopaside_ii_pubchem_cid")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id": _text(
            transporter_p0_evidence.get("aqp1_binding_source_modality_bacopaside_ii_chembl_id")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id": _text(
            transporter_p0_evidence.get("aqp1_binding_source_modality_aqp1_chembl_target_id")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count": _int(
            transporter_p0_evidence.get("aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count": _int(
            transporter_p0_evidence.get("aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail": _text(
            transporter_p0_evidence.get("aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_replacement_reference_binding_kcal_mol_action": _text(
            transporter_p0_evidence.get("aqp1_binding_source_modality_replacement_reference_binding_kcal_mol_action")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_computational_binding_energy_row_count": _int(
            transporter_p0_evidence.get("aqp1_binding_source_modality_computational_binding_energy_row_count")
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol": _text(
            transporter_p0_evidence.get("aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol")
        ),
        "pxr_exact_review_intake_ready": pxr_exact_review_ready,
        "pxr_exact_review_template_row_count": pxr_exact_review_row_count,
        "pxr_exact_review_conflict_resolution_required_count": pxr_exact_review_conflict_required_count,
        "pxr_exact_review_kcal_placeholder_count": pxr_exact_review_kcal_placeholder_count,
        "pxr_exact_review_next_review_completion_packet_ready": _bool(
            pxr_exact_review.get("next_review_completion_packet_ready")
        ),
        "pxr_exact_review_next_review_completion_packet": pxr_exact_next_review_completion_packet,
        "pxr_exact_review_next_review_return_bundle_required_artifacts": [
            str(item) for item in (pxr_exact_review.get("next_review_return_bundle_required_artifacts") or [])
        ],
        "pxr_exact_review_next_review_return_bundle_required_artifact_count": _int(
            pxr_exact_review.get("next_review_return_bundle_required_artifact_count")
        ),
        "pxr_exact_review_next_review_return_bundle_completion_matrix": (
            pxr_exact_next_review_return_bundle_matrix
        ),
        "pxr_exact_review_next_review_return_bundle_completion_matrix_count": _int(
            pxr_exact_review.get("next_review_return_bundle_completion_matrix_count")
        ),
        "pxr_exact_review_next_review_return_bundle_blocker_count": _int(
            pxr_exact_review.get("next_review_return_bundle_blocker_count")
        ),
        "pxr_exact_review_next_review_return_bundle_next_artifact_id": _text(
            pxr_exact_review.get("next_review_return_bundle_next_artifact_id")
        ),
        "pxr_exact_review_next_review_return_bundle_next_artifact_path": _text(
            pxr_exact_review.get("next_review_return_bundle_next_artifact_path")
        ),
        "pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids": [
            str(item)
            for item in (
                pxr_exact_review.get("next_review_return_bundle_next_artifact_failed_check_ids") or []
            )
        ],
        "pxr_exact_review_next_review_row_id": _text(pxr_exact_review.get("next_review_row_id")),
        "pxr_exact_review_next_review_candidate_name": _text(
            pxr_exact_review.get("next_review_candidate_name")
        ),
        "pxr_exact_review_next_review_operator_review_artifact": _text(
            pxr_exact_review.get("next_review_operator_review_artifact")
        ),
        "pxr_source_modality_triage_ready": pxr_source_modality_guard_ready,
        "pxr_source_modality_triage_status": _text(pxr_source_modality.get("status")),
        "pxr_source_modality_triage_artifact": _text(
            pxr_source_modality.get("triage_artifact")
        )
        or pxr_source_modality_triage_path,
        "pxr_source_modality_triage_decision": _text(pxr_source_modality.get("triage_decision")),
        "pxr_source_modality_public_evidence_recheck_ready": _bool(
            pxr_source_modality.get("public_evidence_recheck_ready")
        ),
        "pxr_source_modality_public_recheck_artifact": _text(
            pxr_source_modality.get("public_recheck_artifact")
        ),
        "pxr_source_modality_public_recheck_candidate_count": _int(
            pxr_source_modality.get("public_recheck_candidate_count")
        ),
        "pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count": _int(
            pxr_source_modality.get("public_recheck_chembl_direct_binding_total_record_count")
        ),
        "pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count": _int(
            pxr_source_modality.get("public_recheck_chembl_functional_activity_total_record_count")
        ),
        "pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count": _int(
            pxr_source_modality.get("public_recheck_bindingdb_pxr_like_total_record_count")
        ),
        "pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count": _int(
            pxr_source_modality.get("public_recheck_direct_or_claim_safe_binding_kcal_ready_count")
        ),
        "pxr_source_modality_public_recheck_all_candidates_remain_blocked": _bool(
            pxr_source_modality.get("public_recheck_all_candidates_remain_blocked")
        ),
        "pxr_source_modality_public_recheck_first_blocked_candidate_name": _text(
            pxr_source_modality.get("public_recheck_first_blocked_candidate_name")
        ),
        "pxr_source_modality_public_recheck_first_blocked_reason": _text(
            pxr_source_modality.get("public_recheck_first_blocked_reason")
        ),
        "pxr_source_modality_direct_replacement_candidate_packet_ready": _bool(
            pxr_source_modality.get("direct_replacement_candidate_packet_ready")
        ),
        "pxr_source_modality_direct_replacement_artifact": _text(
            pxr_source_modality.get("direct_replacement_artifact")
        ),
        "pxr_source_modality_direct_replacement_candidate_count": _int(
            pxr_source_modality.get("direct_replacement_candidate_count")
        ),
        "pxr_source_modality_direct_replacement_selected_candidate_count": _int(
            pxr_source_modality.get("direct_replacement_selected_candidate_count")
        ),
        "pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count": _int(
            pxr_source_modality.get("direct_replacement_selected_claim_safe_candidate_count")
        ),
        "pxr_source_modality_direct_replacement_first_ligand_id": _text(
            pxr_source_modality.get("direct_replacement_first_ligand_id")
        ),
        "pxr_source_modality_direct_replacement_first_molecule_chembl_id": _text(
            pxr_source_modality.get("direct_replacement_first_molecule_chembl_id")
        ),
        "pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol": _text(
            pxr_source_modality.get("direct_replacement_first_reference_binding_kcal_mol")
        ),
        "pxr_source_modality_direct_replacement_first_source": _text(
            pxr_source_modality.get("direct_replacement_first_source")
        ),
        "pxr_source_modality_direct_replacement_apply_draft_ready": (
            pxr_source_modality_apply_draft_ready
        ),
        "pxr_source_modality_direct_replacement_apply_draft_status": _text(
            pxr_source_modality.get("direct_replacement_apply_draft_status")
        ),
        "pxr_source_modality_direct_replacement_apply_draft_artifact": _text(
            pxr_source_modality.get("direct_replacement_apply_draft_artifact")
        ),
        "pxr_source_modality_direct_replacement_apply_draft_workbook_row_count": _int(
            pxr_source_modality.get("direct_replacement_apply_draft_workbook_row_count")
        ),
        "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft": _int(
            pxr_source_modality.get("direct_replacement_apply_draft_blocked_row_count_before_draft")
        ),
        "pxr_source_modality_direct_replacement_apply_draft_overlay_row_count": (
            pxr_source_modality_apply_draft_overlay_count
        ),
        "pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft": _int(
            pxr_source_modality.get("direct_replacement_apply_draft_ready_for_apply_row_count_after_draft")
        ),
        "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft": (
            pxr_source_modality_apply_draft_blocked_after
        ),
        "pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id": _text(
            pxr_source_modality.get("direct_replacement_apply_draft_first_overlay_ligand_id")
        ),
        "pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched": _bool(
            pxr_source_modality.get("direct_replacement_apply_draft_authoritative_fields_touched")
        ),
        "pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count": (
            pxr_source_modality_conflict_surrogate_count
        ),
        "pxr_source_modality_direct_or_claim_safe_quantitative_ready_count": (
            pxr_source_modality_claim_safe_ready_count
        ),
        "pxr_source_modality_accepted_for_scope_promotion_count": pxr_source_modality_accepted_count,
        "pxr_source_modality_next_review_row_id": _text(pxr_source_modality.get("next_review_row_id")),
        "pxr_source_modality_next_review_candidate_name": _text(
            pxr_source_modality.get("next_review_candidate_name")
        ),
        "pxr_source_modality_next_review_source_modality": _text(
            pxr_source_modality.get("next_review_source_modality")
        ),
        "pxr_source_modality_next_review_rejection_reason": _text(
            pxr_source_modality.get("next_review_rejection_reason")
        ),
        "evidence_queue_artifact": evidence_queue_path,
        "evidence_priority_artifact": evidence_priority_path,
        "evidence_intake_readiness_artifact": evidence_intake_readiness_path,
        "scope_operator_transfer_manifest_ready": _bool(
            evidence_intake.get("scope_operator_transfer_manifest_ready")
        ),
        "scope_operator_transfer_outbound_artifact_count": _int(
            evidence_intake.get("scope_operator_transfer_outbound_artifact_count")
        ),
        "scope_operator_transfer_outbound_artifacts": [
            str(item) for item in (evidence_intake.get("scope_operator_transfer_outbound_artifacts") or [])
        ],
        "scope_operator_transfer_inbound_artifact_count": _int(
            evidence_intake.get("scope_operator_transfer_inbound_artifact_count")
        ),
        "scope_operator_transfer_inbound_artifacts": [
            str(item) for item in (evidence_intake.get("scope_operator_transfer_inbound_artifacts") or [])
        ],
        "scope_operator_transfer_first_return_artifact": _text(
            evidence_intake.get("scope_operator_transfer_first_return_artifact")
        ),
        "scope_operator_transfer_acceptance_artifact": _text(
            evidence_intake.get("scope_operator_transfer_acceptance_artifact")
        ),
        "scope_operator_transfer_acceptance_ready_key": _text(
            evidence_intake.get("scope_operator_transfer_acceptance_ready_key")
        ),
        "scope_operator_transfer_next_acceptance_stage": _text(
            evidence_intake.get("scope_operator_transfer_next_acceptance_stage")
        ),
        "scope_operator_transfer_post_return_validation_command": _text(
            evidence_intake.get("scope_operator_transfer_post_return_validation_command")
        ),
        "pxr_exact_review_intake_artifact": pxr_exact_review_intake_path,
        "scope_acceptance_matrix_ready": scope_acceptance_matrix_ready,
        "scope_claim_expansion_contract_ready": scope_claim_expansion_contract_ready,
        "scope_claim_expansion_currently_satisfied": scope_claim_expansion_currently_satisfied,
        "scope_claim_expansion_current_blocked_stage_count": len(
            scope_claim_expansion_current_blocked_stage_ids
        ),
        "scope_claim_expansion_current_blocked_stage_ids": scope_claim_expansion_current_blocked_stage_ids,
        "scope_claim_expansion_current_next_stage_id": _text(first_scope_acceptance_blocker.get("stage_id")),
        "scope_claim_expansion_current_next_stage_artifact": _text(first_scope_acceptance_blocker.get("artifact")),
        "scope_claim_expansion_current_next_stage_validation_command": _text(
            first_scope_acceptance_blocker.get("validation_command")
        ),
        "scope_claim_expansion_current_next_stage_unlock_claim_scopes": [
            str(item) for item in (first_scope_acceptance_blocker.get("unlock_claim_scopes") or [])
        ],
        "scope_acceptance_stage_count": len(scope_acceptance_rows),
        "scope_acceptance_ready_stage_count": len(scope_acceptance_rows) - len(scope_acceptance_blockers),
        "scope_acceptance_blocked_stage_count": len(scope_acceptance_blockers),
        "scope_acceptance_stage_ids": [str(row["stage_id"]) for row in scope_acceptance_rows],
        "scope_acceptance_ready_stage_ids": [
            str(row["stage_id"]) for row in scope_acceptance_rows if row["status"] == "ready"
        ],
        "scope_acceptance_blocked_stage_ids": [str(row["stage_id"]) for row in scope_acceptance_blockers],
        "scope_acceptance_next_stage_id": _text(first_scope_acceptance_blocker.get("stage_id")),
        "scope_acceptance_next_stage_artifact": _text(first_scope_acceptance_blocker.get("artifact")),
        "scope_acceptance_next_stage_validation_command": _text(
            first_scope_acceptance_blocker.get("validation_command")
        ),
        "scope_acceptance_next_stage_release_effect": _text(
            first_scope_acceptance_blocker.get("release_effect")
        ),
        "scope_acceptance_next_stage_unlock_claim_scopes": [
            str(item) for item in (first_scope_acceptance_blocker.get("unlock_claim_scopes") or [])
        ],
        "scope_acceptance_next_stage_required_checks": [
            str(item) for item in (first_scope_acceptance_blocker.get("required_checks") or [])
        ],
        "scope_acceptance_next_stage_next_action": _text(first_scope_acceptance_blocker.get("next_action")),
        "scope_acceptance_stage_evidence_matrix_count": len(scope_acceptance_stage_evidence_matrix),
        "scope_acceptance_current_blocked_stage_evidence_matrix_count": len(
            scope_acceptance_current_blocked_stage_evidence_matrix
        ),
        "domain_count": len(rows),
        "ready_domain_count": len(ready_domains),
        "missing_domain_count": len(missing_domains),
        "ready_domains": ready_domains,
        "missing_domains": missing_domains,
        "first_blocked_domain": _text(first_blocked_domain_row.get("domain")),
        "first_blocked_domain_artifact": _text(first_blocked_domain_row.get("artifact")),
        "first_blocked_domain_observed": _text(first_blocked_domain_row.get("observed")),
        "first_blocked_domain_requirement": _text(first_blocked_domain_row.get("requirement")),
        "first_blocked_domain_next_action": _text(first_blocked_domain_row.get("next_action")),
        "allowed_scope_families": allowed_families,
        "scope_claim_posture_ready": scope_claim_posture_ready,
        "restricted_scope_claim_allowed": restricted_scope_claim_allowed,
        "general_platform_claim_allowed": general_platform_claim_allowed,
        "general_platform_claim_blocked": not general_platform_claim_allowed,
        "allowed_claim_scopes": allowed_claim_scopes,
        "blocked_claim_scopes": blocked_claim_scopes,
        "blocked_claim_scope_count": len(blocked_claim_scopes),
        "scope_claim_boundary_detail": scope_claim_boundary_detail,
        "general_protein_ligand_platform_ready": general_ready,
        "execution_enabled": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Scope breadth contract is ready; widen API scope only through an explicit product decision."
            if ready
            else (
                acquisition_next_step
                or "Keep product scope restricted and work the blocked breadth domains before any broad platform claim."
            )
        ),
    }
    return {
        "summary": summary,
        "rows": rows,
        "scope_acceptance_matrix": scope_acceptance_rows,
        "scope_acceptance_stage_evidence_matrix": scope_acceptance_stage_evidence_matrix,
        "scope_acceptance_current_blocked_stage_evidence_matrix": (
            scope_acceptance_current_blocked_stage_evidence_matrix
        ),
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Scope Breadth Contract",
        "",
        f"- status: `{s['status']}`",
        f"- scope_breadth_ready: `{s['scope_breadth_ready']}`",
        f"- ready_domain_count: `{s['ready_domain_count']}` / `{s['domain_count']}`",
        f"- ready_domains: `{','.join(s['ready_domains'])}`",
        f"- missing_domains: `{','.join(s['missing_domains'])}`",
        f"- allowed_scope_families: `{','.join(s['allowed_scope_families'])}`",
        f"- scope_claim_posture_ready: `{s['scope_claim_posture_ready']}`",
        f"- restricted_scope_claim_allowed: `{s['restricted_scope_claim_allowed']}`",
        f"- general_platform_claim_allowed: `{s['general_platform_claim_allowed']}`",
        f"- allowed_claim_scopes: `{','.join(s['allowed_claim_scopes'])}`",
        f"- blocked_claim_scopes: `{','.join(s['blocked_claim_scopes'])}`",
        f"- scope_claim_boundary_detail: `{s['scope_claim_boundary_detail']}`",
        f"- scope_breadth_acquisition_plan_ready: `{s['scope_breadth_acquisition_plan_ready']}`",
        f"- evidence_intake_readiness_ready: `{s['evidence_intake_readiness_ready']}`",
        f"- evidence_queue_item_count: `{s['evidence_queue_item_count']}`",
        f"- evidence_queue_next_operator_completion_slot_id: `{s['evidence_queue_next_operator_completion_slot_id']}`",
        f"- evidence_queue_next_operator_completion_required_exact_evidence_fields: `{s['evidence_queue_next_operator_completion_required_exact_evidence_fields']}`",
        f"- evidence_queue_next_operator_completion_operator_review_artifact: `{s['evidence_queue_next_operator_completion_operator_review_artifact']}`",
        f"- evidence_queue_next_operator_completion_acceptance_gate_commands: `{s['evidence_queue_next_operator_completion_acceptance_gate_commands']}`",
        f"- evidence_queue_next_operator_completion_aqp1_review_sidecar_ready: `{s['evidence_queue_next_operator_completion_aqp1_review_sidecar_ready']}`",
        f"- evidence_queue_next_operator_completion_aqp1_review_candidate_name: `{s['evidence_queue_next_operator_completion_aqp1_review_candidate_name']}`",
        f"- evidence_queue_next_operator_completion_aqp1_review_source_anchor: `{s['evidence_queue_next_operator_completion_aqp1_review_source_anchor']}`",
        f"- evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol: `{s['evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol']}`",
        f"- evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed: `{s['evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed']}`",
        f"- evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank: `{s['evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank']}`",
        f"- scientific_evidence_request_count: `{s['scientific_evidence_request_count']}`",
        f"- local_crosscheck_intake_ready_count: `{s['local_crosscheck_intake_ready_count']}`",
        f"- local_crosscheck_unreadable_item_count: `{s['local_crosscheck_unreadable_item_count']}`",
        f"- transporter_triage_packet_ready: `{s['transporter_triage_packet_ready']}`",
        f"- transporter_operator_review_evidence_matrix_ready: `{s['transporter_operator_review_evidence_matrix_ready']}`",
        f"- transporter_claim_safe_local_evidence_ready_count: `{s['transporter_claim_safe_local_evidence_ready_count']}`",
        f"- transporter_claim_safe_local_evidence_blocked_count: `{s['transporter_claim_safe_local_evidence_blocked_count']}`",
        f"- transporter_direct_binding_claim_blocked_count: `{s['transporter_direct_binding_claim_blocked_count']}`",
        f"- transporter_negative_value_claim_blocked_count: `{s['transporter_negative_value_claim_blocked_count']}`",
        f"- transporter_candidate_assignment_required_count: `{s['transporter_candidate_assignment_required_count']}`",
        f"- transporter_functional_direct_gap_count: `{s['transporter_functional_direct_gap_count']}`",
        f"- transporter_candidate_workbook_ready: `{s['transporter_candidate_workbook_ready']}`",
        f"- transporter_candidate_ready_for_manual_review_count: `{s['transporter_candidate_ready_for_manual_review_count']}`",
        f"- transporter_candidate_ready_for_apply_count: `{s['transporter_candidate_ready_for_apply_count']}`",
        f"- transporter_manual_review_intake_ready: `{s['transporter_manual_review_intake_ready']}`",
        f"- transporter_manual_review_template_row_count: `{s['transporter_manual_review_template_row_count']}`",
        f"- transporter_manual_review_direct_binding_evidence_required_count: `{s['transporter_manual_review_direct_binding_evidence_required_count']}`",
        f"- transporter_manual_review_negative_quantitative_value_required_count: `{s['transporter_manual_review_negative_quantitative_value_required_count']}`",
        f"- transporter_manual_review_p0_slot_overlay_row_count: `{s['transporter_manual_review_p0_slot_overlay_row_count']}`",
        f"- transporter_manual_review_p0_slot_overlay_first_item_id: `{s['transporter_manual_review_p0_slot_overlay_first_item_id'] or '-'}`",
        f"- transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id: `{s['transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id'] or '-'}`",
        f"- transporter_p0_closure_packet_ready: `{s['transporter_p0_closure_packet_ready']}`",
        f"- transporter_p0_current_membrane_open_count: `{s['transporter_p0_current_membrane_open_count']}`",
        f"- transporter_p0_closure_row_count: `{s['transporter_p0_closure_row_count']}`",
        f"- transporter_p0_aqp1_core_open_count: `{s['transporter_p0_aqp1_core_open_count']}`",
        f"- transporter_p0_glut1_core_open_count: `{s['transporter_p0_glut1_core_open_count']}`",
        f"- transporter_p0_readiness_matrix_ready: `{s['transporter_p0_readiness_matrix_ready']}`",
        f"- transporter_p0_auto_close_ready_artifact_count: `{s['transporter_p0_auto_close_ready_artifact_count']}`",
        f"- transporter_p0_manual_or_external_required_artifact_count: `{s['transporter_p0_manual_or_external_required_artifact_count']}`",
        f"- transporter_p0_unresolved_slot_count: `{s['transporter_p0_unresolved_slot_count']}`",
        f"- transporter_p0_external_exact_evidence_required_slot_count: `{s['transporter_p0_external_exact_evidence_required_slot_count']}`",
        f"- transporter_p0_evidence_acquisition_packet_ready: `{s['transporter_p0_evidence_acquisition_packet_ready']}`",
        f"- transporter_p0_evidence_acquisition_exact_request_slot_count: `{s['transporter_p0_evidence_acquisition_exact_request_slot_count']}`",
        f"- transporter_p0_evidence_acquisition_first_target_id: `{s['transporter_p0_evidence_acquisition_first_target_id']}`",
        f"- transporter_p0_evidence_acquisition_first_packet_step: `{s['transporter_p0_evidence_acquisition_first_packet_step']}`",
        f"- transporter_p0_evidence_acquisition_first_request_mode: `{s['transporter_p0_evidence_acquisition_first_request_mode']}`",
        f"- transporter_p0_evidence_acquisition_next_slot_completion_packet_ready: `{s['transporter_p0_evidence_acquisition_next_slot_completion_packet_ready']}`",
        f"- transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count: `{s['transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count']}`",
        f"- transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count: `{s['transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count']}`",
        f"- transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id: `{s['transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id']}`",
        f"- transporter_p0_evidence_acquisition_next_slot_id: `{s['transporter_p0_evidence_acquisition_next_slot_id']}`",
        f"- transporter_p0_evidence_acquisition_next_slot_operator_review_artifact: `{s['transporter_p0_evidence_acquisition_next_slot_operator_review_artifact']}`",
        f"- transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready: `{s['transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready']}`",
        f"- transporter_p0_evidence_acquisition_next_slot_source_modality: `{s['transporter_p0_evidence_acquisition_next_slot_source_modality']}`",
        f"- transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed: `{s['transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed']}`",
        f"- transporter_p0_evidence_acquisition_next_slot_source_modality_decision: `{s['transporter_p0_evidence_acquisition_next_slot_source_modality_decision']}`",
        f"- scope_operator_transfer_manifest_ready: `{s['scope_operator_transfer_manifest_ready']}`",
        f"- scope_operator_transfer_outbound_artifact_count: `{s['scope_operator_transfer_outbound_artifact_count']}`",
        f"- scope_operator_transfer_inbound_artifact_count: `{s['scope_operator_transfer_inbound_artifact_count']}`",
        f"- scope_operator_transfer_first_return_artifact: `{s['scope_operator_transfer_first_return_artifact']}`",
        f"- scope_operator_transfer_acceptance_artifact: `{s['scope_operator_transfer_acceptance_artifact']}`",
        f"- pxr_exact_review_intake_ready: `{s['pxr_exact_review_intake_ready']}`",
        f"- pxr_exact_review_template_row_count: `{s['pxr_exact_review_template_row_count']}`",
        f"- pxr_exact_review_conflict_resolution_required_count: `{s['pxr_exact_review_conflict_resolution_required_count']}`",
        f"- pxr_exact_review_kcal_placeholder_count: `{s['pxr_exact_review_kcal_placeholder_count']}`",
        f"- pxr_exact_review_next_review_completion_packet_ready: `{s['pxr_exact_review_next_review_completion_packet_ready']}`",
        f"- pxr_exact_review_next_review_return_bundle_required_artifact_count: `{s['pxr_exact_review_next_review_return_bundle_required_artifact_count']}`",
        f"- pxr_exact_review_next_review_return_bundle_blocker_count: `{s['pxr_exact_review_next_review_return_bundle_blocker_count']}`",
        f"- pxr_exact_review_next_review_return_bundle_next_artifact_id: `{s['pxr_exact_review_next_review_return_bundle_next_artifact_id']}`",
        f"- pxr_exact_review_next_review_row_id: `{s['pxr_exact_review_next_review_row_id']}`",
        f"- pxr_exact_review_next_review_candidate_name: `{s['pxr_exact_review_next_review_candidate_name']}`",
        f"- pxr_source_modality_triage_ready: `{s['pxr_source_modality_triage_ready']}`",
        f"- pxr_source_modality_triage_artifact: `{s['pxr_source_modality_triage_artifact']}`",
        f"- pxr_source_modality_triage_decision: `{s['pxr_source_modality_triage_decision']}`",
        f"- pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count: `{s['pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count']}`",
        f"- pxr_source_modality_direct_or_claim_safe_quantitative_ready_count: `{s['pxr_source_modality_direct_or_claim_safe_quantitative_ready_count']}`",
        f"- pxr_source_modality_direct_replacement_apply_draft_ready: `{s['pxr_source_modality_direct_replacement_apply_draft_ready']}`",
        f"- pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft: `{s['pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft']}`",
        f"- external_primary_exact_evidence_required_count: `{s['external_primary_exact_evidence_required_count']}`",
        f"- scope_acceptance_matrix_ready: `{s['scope_acceptance_matrix_ready']}`",
        f"- scope_claim_expansion_contract_ready: `{s['scope_claim_expansion_contract_ready']}`",
        f"- scope_claim_expansion_currently_satisfied: `{s['scope_claim_expansion_currently_satisfied']}`",
        f"- scope_claim_expansion_current_next_stage_id: `{s['scope_claim_expansion_current_next_stage_id']}`",
        f"- scope_acceptance_ready_stage_count: `{s['scope_acceptance_ready_stage_count']}`",
        f"- scope_acceptance_blocked_stage_count: `{s['scope_acceptance_blocked_stage_count']}`",
        f"- scope_acceptance_next_stage_id: `{s['scope_acceptance_next_stage_id']}`",
        f"- scope_acceptance_next_stage_artifact: `{s['scope_acceptance_next_stage_artifact']}`",
        f"- scope_acceptance_next_stage_validation_command: `{s['scope_acceptance_next_stage_validation_command']}`",
        f"- scope_acceptance_stage_evidence_matrix_count: `{s['scope_acceptance_stage_evidence_matrix_count']}`",
        f"- scope_acceptance_current_blocked_stage_evidence_matrix_count: `{s['scope_acceptance_current_blocked_stage_evidence_matrix_count']}`",
        "",
        "## Domains",
        "",
        "| domain | status | observed | requirement | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['domain']}` | `{row['status']}` | `{row['observed']}` | `{row['requirement']}` | {row['next_action']} |")
    lines.extend(
        [
            "",
            "## Scope Acceptance Matrix",
            "",
            "| stage | status | artifact | validation command | release effect | unlock scopes | next action |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["scope_acceptance_matrix"]:
        lines.append(
            f"| `{row['stage_id']}` | `{row['status']}` | `{row['artifact']}` | "
            f"`{row['validation_command']}` | {row['release_effect']} | "
            f"`{','.join(str(item) for item in row['unlock_claim_scopes'])}` | {row['next_action']} |"
        )
    lines.extend(
        [
            "",
            "## Scope Acceptance Stage Evidence Matrix",
            "",
            "| stage | status | evidence rows | blocked evidence rows | first blocked evidence row | evidence artifacts |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["scope_acceptance_stage_evidence_matrix"]:
        first_blocked = row.get("first_blocked_evidence_row") or {}
        first_blocked_id = first_blocked.get("evidence_row_id") or first_blocked.get("domain") or ""
        lines.append(
            f"| `{row['stage_id']}` | `{row['status']}` | `{row['evidence_row_count']}` | "
            f"`{row['blocked_evidence_row_count']}` | `{first_blocked_id}` | "
            f"`{';'.join(str(item) for item in row['evidence_artifacts'])}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product scope breadth contract from local evidence.")
    parser.add_argument("--capability-json", default=DEFAULT_CAPABILITY_JSON)
    parser.add_argument("--transporter-json", default=DEFAULT_TRANSPORTER_JSON)
    parser.add_argument("--transporter-reopen-json", default=DEFAULT_TRANSPORTER_REOPEN_JSON)
    parser.add_argument("--transporter-binder-gate-json", default=DEFAULT_TRANSPORTER_BINDER_GATE_JSON)
    parser.add_argument("--transporter-p0-closure-json", default=DEFAULT_TRANSPORTER_P0_CLOSURE_JSON)
    parser.add_argument("--transporter-p0-readiness-matrix-json", default=DEFAULT_TRANSPORTER_P0_READINESS_MATRIX_JSON)
    parser.add_argument(
        "--transporter-p0-evidence-acquisition-json",
        default=DEFAULT_TRANSPORTER_P0_EVIDENCE_ACQUISITION_JSON,
    )
    parser.add_argument("--ca2-json", default=DEFAULT_CA2_JSON)
    parser.add_argument("--pxr-json", default=DEFAULT_PXR_JSON)
    parser.add_argument("--pxr-fill-readiness-json", default=DEFAULT_PXR_FILL_READINESS_JSON)
    parser.add_argument("--pxr-blocked-gate-json", default=DEFAULT_PXR_BLOCKED_GATE_JSON)
    parser.add_argument("--pxr-exact-review-intake-json", default=DEFAULT_PXR_EXACT_REVIEW_INTAKE_JSON)
    parser.add_argument("--pxr-source-modality-triage-json", default=DEFAULT_PXR_SOURCE_MODALITY_TRIAGE_JSON)
    parser.add_argument("--idp-scaffold-json", default=DEFAULT_IDP_SCAFFOLD_JSON)
    parser.add_argument("--idp-promotion-resolution-json", default=DEFAULT_IDP_PROMOTION_RESOLUTION_JSON)
    parser.add_argument("--allatom-json", default=DEFAULT_ALLATOM_JSON)
    parser.add_argument("--evidence-queue-json", default=DEFAULT_EVIDENCE_QUEUE_JSON)
    parser.add_argument("--evidence-priority-json", default=DEFAULT_EVIDENCE_PRIORITY_JSON)
    parser.add_argument("--evidence-intake-readiness-json", default=DEFAULT_EVIDENCE_INTAKE_READINESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_scope_breadth_contract(
        capability_packet=_read_json_if_present(args.capability_json),
        transporter_packet=_read_json_if_present(args.transporter_json),
        ca2_packet=_read_json_if_present(args.ca2_json),
        pxr_packet=_read_json_if_present(args.pxr_json),
        pxr_fill_readiness_packet=_read_json_if_present(args.pxr_fill_readiness_json),
        pxr_blocked_gate_packet=_read_json_if_present(args.pxr_blocked_gate_json),
        pxr_exact_review_intake_packet=_read_json_if_present(args.pxr_exact_review_intake_json),
        pxr_source_modality_triage_packet=_read_json_if_present(args.pxr_source_modality_triage_json),
        idp_scaffold_packet=_read_json_if_present(args.idp_scaffold_json),
        idp_promotion_resolution_packet=_read_json_if_present(args.idp_promotion_resolution_json),
        allatom_packet=_read_json_if_present(args.allatom_json),
        evidence_queue_packet=_read_json_if_present(args.evidence_queue_json),
        evidence_priority_packet=_read_json_if_present(args.evidence_priority_json),
        evidence_intake_readiness_packet=_read_json_if_present(args.evidence_intake_readiness_json),
        transporter_reopen_packet=_read_json_if_present(args.transporter_reopen_json),
        transporter_binder_gate_packet=_read_json_if_present(args.transporter_binder_gate_json),
        transporter_p0_closure_packet=_read_json_if_present(args.transporter_p0_closure_json),
        transporter_p0_readiness_matrix_packet=_read_json_if_present(args.transporter_p0_readiness_matrix_json),
        transporter_p0_evidence_acquisition_packet=_read_json_if_present(
            args.transporter_p0_evidence_acquisition_json
        ),
        capability_path=args.capability_json,
        transporter_path=args.transporter_json,
        transporter_reopen_path=args.transporter_reopen_json,
        transporter_binder_gate_path=args.transporter_binder_gate_json,
        transporter_p0_closure_path=args.transporter_p0_closure_json,
        transporter_p0_readiness_matrix_path=args.transporter_p0_readiness_matrix_json,
        transporter_p0_evidence_acquisition_path=args.transporter_p0_evidence_acquisition_json,
        ca2_path=args.ca2_json,
        pxr_path=args.pxr_json,
        pxr_fill_readiness_path=args.pxr_fill_readiness_json,
        pxr_blocked_gate_path=args.pxr_blocked_gate_json,
        pxr_exact_review_intake_path=args.pxr_exact_review_intake_json,
        pxr_source_modality_triage_path=args.pxr_source_modality_triage_json,
        idp_scaffold_path=args.idp_scaffold_json,
        idp_promotion_resolution_path=args.idp_promotion_resolution_json,
        allatom_path=args.allatom_json,
        evidence_queue_path=args.evidence_queue_json,
        evidence_priority_path=args.evidence_priority_json,
        evidence_intake_readiness_path=args.evidence_intake_readiness_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
