#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_CLOSURE_JSON = RUNS / "transporter_p0_closure_packet_current.json"
DEFAULT_AQP1_WORKBOOK_JSON = RUNS / "aqp1_packet_replacement_workbook_current.json"
DEFAULT_AQP1_NEGATIVE_JSON = RUNS / "aqp1_negative_evidence_request_packet_current.json"
DEFAULT_AQP1_NEGATIVE_INTAKE_JSON = RUNS / "aqp1_negative_evidence_intake_gate_current.json"
DEFAULT_AQP1_NEGATIVE_SLOT_CLOSURE_JSON = RUNS / "aqp1_negative_slot_closure_packet_current.json"
DEFAULT_AQP1_BINDING_SOURCE_MODALITY_TRIAGE_JSON = RUNS / "aqp1_binding_source_modality_triage_current.json"
DEFAULT_GLUT1_WORKBOOK_JSON = RUNS / "glut1_packet_replacement_workbook_current.json"
DEFAULT_GLUT1_SECOND_WAVE_JSON = RUNS / "glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_GLUT1_CLAIM_SAFE_JSON = RUNS / "glut1_claim_safe_binding_kcal_packet_current.json"
DEFAULT_OUT_JSON = RUNS / "transporter_p0_evidence_acquisition_packet_current.json"
DEFAULT_OUT_CSV = RUNS / "transporter_p0_evidence_acquisition_packet_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_p0_evidence_acquisition_packet_current.md"

CLAIM_BOUNDARY = (
    "Transporter P0 evidence acquisition packet only; maps unresolved AQP1/GLUT1 ligand slots to exact evidence or "
    "workbook synchronization actions. It does not authoritatively apply rows, reopen donor policy, run docking, widen "
    "product scope, upload, submit, email, delete, or mutate external state."
)

BINDER_EXACT_EVIDENCE_FIELDS = [
    "target_id",
    "target_uniprot_accession",
    "target_species",
    "candidate_ligand_id",
    "ligand_name",
    "ligand_smiles",
    "ligand_external_identifier",
    "assay_type",
    "direct_binding_or_claim_safe_kcal_basis",
    "quantitative_value",
    "quantitative_units",
    "quantitative_relation",
    "reference_binding_kcal_mol",
    "delta_g_derivation_note",
    "source_url_or_doi",
    "source_pmid_or_document_id",
    "evidence_sentence_or_table_locator",
    "target_match_decision",
    "operator_review_decision",
]

NEGATIVE_EXACT_EVIDENCE_FIELDS = [
    "target_id",
    "target_uniprot_accession",
    "target_species",
    "candidate_ligand_id",
    "ligand_name",
    "ligand_smiles",
    "ligand_external_identifier",
    "assay_type",
    "negative_or_inactive_value",
    "negative_or_inactive_units",
    "negative_or_inactive_relation",
    "negative_threshold_rationale",
    "source_url_or_doi",
    "source_pmid_or_document_id",
    "evidence_sentence_or_table_locator",
    "target_match_decision",
    "operator_review_decision",
]

NEXT_SLOT_GUARDRAILS = [
    "authoritative_apply_allowed_false_until_gate_green",
    "scope_promotion_allowed_false_until_all_transporter_p0_slots_green",
    "functional_surrogate_does_not_authorize_direct_binding_claim",
    "docking_only_or_target_ambiguous_source_rejected",
    "reference_split_meta_rows_must_be_synchronized_before_promotion",
]
NEXT_SLOT_SOURCE_MODALITY_GUARDRAILS = [
    "functional_quantitative_surrogate_is_review_only",
    "direct_binding_claim_requires_exact_target_pair_source",
    "claim_safe_kcal_requires_operator_confirmed_basis",
    "reference_binding_kcal_mol_must_remain_blank_until_claim_safe",
    "scope_promotion_allowed_false_until_source_modality_upgrade",
]

NEXT_SLOT_SYNC_TARGETS = [
    "config/ligand_binding_reference_blind_aqp1_v1.csv",
    "config/ligand_eval_splits_blind_aqp1_v1.csv",
    "config/ligand_meta_blind_aqp1_v1.csv",
    "runs/transporter_manual_review_intake_template_current.csv",
]
NEXT_SLOT_RETURN_ARTIFACTS = [
    "runs/transporter_manual_review_intake_template_current.csv",
    "config/ligand_binding_reference_blind_aqp1_v1.csv",
    "config/ligand_eval_splits_blind_aqp1_v1.csv",
    "config/ligand_meta_blind_aqp1_v1.csv",
    "runs/transporter_binder_promotion_gate_current.json",
]

NEXT_SLOT_VALIDATION_COMMANDS = [
    "python3 tools/build_transporter_manual_review_intake_template.py",
    "python3 tools/build_transporter_binder_promotion_gate.py",
    "python3 tools/build_transporter_p0_closure_packet.py",
    "python3 tools/build_transporter_p0_closure_readiness_matrix.py",
    "python3 tools/build_transporter_p0_evidence_acquisition_packet.py",
    "python3 tools/build_product_scope_breadth_contract.py",
    "python3 tools/build_product_goal_completion_audit.py",
]


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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _workbook_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in payload.get("workbook_rows", []) or [] if isinstance(row, dict)]


def _second_wave_by_step(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("packet_step")): dict(row)
        for row in payload.get("rows", []) or []
        if isinstance(row, dict) and _text(row.get("packet_step"))
    }


def _claim_safe_steps(payload: dict[str, Any]) -> set[str]:
    return {
        _text(row.get("packet_step"))
        for row in payload.get("rows", []) or []
        if isinstance(row, dict) and _text(row.get("ready")).lower() == "yes"
    }


def _is_ready(row: dict[str, Any]) -> bool:
    return _text(row.get("row_ready_for_apply")).lower() == "yes" and not _text(row.get("required_missing_fields"))


def _aqp1_negative_authoritative_ready(
    *,
    request_payload: dict[str, Any],
    intake_payload: dict[str, Any],
    slot_closure_payload: dict[str, Any],
) -> bool:
    request = _summary(request_payload)
    intake = _summary(intake_payload)
    slot_closure = _summary(slot_closure_payload)
    if intake or slot_closure:
        return (
            _int(intake.get("authoritative_negative_apply_allowed_count")) >= 3
            and intake.get("negative_evidence_closure_allowed") is True
            and slot_closure.get("authoritative_negative_apply_allowed") is True
        )
    return (
        _int(request.get("authoritative_negative_apply_allowed_count")) >= 3
        and request.get("negative_evidence_closure_allowed") is True
    )


def _request_mode(target_id: str, row: dict[str, Any], *, has_negative_cover: bool, second_wave: dict[str, Any] | None) -> str:
    binder = _text(row.get("replacement_is_binder"))
    if binder == "1":
        if target_id == "GLUT1_4PYP" and second_wave:
            signal = _text(second_wave.get("public_provenance_signal"))
            if "apparent_functional" in signal:
                return "direct_binding_kcal_or_keep_functional_review_only_required"
            if "leave_kcal_blank" in signal:
                return "claim_safe_direct_binding_kcal_required_before_apply"
        return "exact_target_pair_quantitative_binder_kcal_required"
    if has_negative_cover:
        return "sync_exact_negative_evidence_into_workbook_required"
    return "exact_target_pair_quantitative_negative_evidence_required"


def _evidence_state(target_id: str, row: dict[str, Any], *, has_negative_cover: bool, second_wave: dict[str, Any] | None) -> str:
    if _is_ready(row):
        return "ready_for_apply"
    binder = _text(row.get("replacement_is_binder"))
    missing = _text(row.get("required_missing_fields"))
    if binder == "0" and has_negative_cover:
        return "negative_evidence_packet_covers_slot_but_workbook_columns_missing"
    if target_id == "AQP1" and binder == "1" and _text(row.get("replacement_ligand_id")):
        return "staged_non_authoritative_binder_missing_reference_kcal"
    if target_id == "GLUT1_4PYP" and second_wave:
        return _text(second_wave.get("public_provenance_signal")) or "second_wave_review_context_present"
    if missing:
        return "missing_replacement_fields"
    return "unresolved"


def _next_action(target_id: str, row: dict[str, Any], request_mode: str) -> str:
    step = _text(row.get("packet_step"))
    if request_mode == "sync_exact_negative_evidence_into_workbook_required":
        return f"Fill {target_id} {step} replacement identity/source/kcal-or-negative-reference/meta fields from the covered negative evidence packet, then rerun apply gates."
    if request_mode == "direct_binding_kcal_or_keep_functional_review_only_required":
        return f"Keep {target_id} {step} review-only unless an exact direct binding kcal source is curated."
    if request_mode == "claim_safe_direct_binding_kcal_required_before_apply":
        return f"Attach a claim-safe direct binding kcal value for {target_id} {step}, otherwise keep the row out of authoritative apply."
    return f"Acquire exact target-pair quantitative evidence for {target_id} {step} and synchronize reference/split/meta rows."


def _source_modality_guard(next_row: dict[str, Any], *, packet_ready: bool) -> dict[str, Any]:
    if not packet_ready:
        return {
            "next_slot_source_modality_guard_ready": False,
            "next_slot_source_modality": "",
            "next_slot_source_modality_claim_safe": False,
            "next_slot_source_modality_direct_binding_claim_allowed": False,
            "next_slot_source_modality_decision": "",
            "next_slot_source_modality_guardrails": [],
            "next_slot_source_modality_observed_signal": "",
            "next_slot_source_modality_required_upgrade": "",
        }
    request_mode = _text(next_row.get("request_mode"))
    source_signal = _text(next_row.get("source_signal"))
    missing_fields = _text(next_row.get("required_missing_fields"))
    evidence_state = _text(next_row.get("evidence_state"))
    functional_or_review_only = (
        "functional" in request_mode
        or "functional" in source_signal.lower()
        or "reference_binding_kcal_mol" in missing_fields
        or evidence_state == "staged_non_authoritative_binder_missing_reference_kcal"
    )
    source_modality = (
        "functional_quantitative_surrogate"
        if functional_or_review_only
        else "unresolved_exact_target_pair_evidence_request"
    )
    observed_parts = [
        f"request_mode={request_mode}" if request_mode else "",
        f"source_signal={source_signal}" if source_signal else "",
        f"evidence_state={evidence_state}" if evidence_state else "",
        f"missing_fields={missing_fields}" if missing_fields else "",
    ]
    return {
        "next_slot_source_modality_guard_ready": True,
        "next_slot_source_modality": source_modality,
        "next_slot_source_modality_claim_safe": False,
        "next_slot_source_modality_direct_binding_claim_allowed": False,
        "next_slot_source_modality_decision": (
            "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
        ),
        "next_slot_source_modality_guardrails": NEXT_SLOT_SOURCE_MODALITY_GUARDRAILS,
        "next_slot_source_modality_observed_signal": ";".join(
            part for part in observed_parts if part
        ),
        "next_slot_source_modality_required_upgrade": (
            "exact target-pair direct/claim-safe binding kcal/mol with source locator, target match, "
            "and operator review decision"
        ),
    }


def _operator_validation_candidate(source_triage: dict[str, Any], *, target_id: str) -> dict[str, Any]:
    if target_id != "AQP1":
        return {}
    candidate_id = _text(
        source_triage.get("chembl_aqp1_direct_like_binding_candidate_chembl_id")
    )
    if not candidate_id:
        return {}
    return {
        "candidate_source": "aqp1_binding_source_modality_triage",
        "candidate_status": "operator_validation_required",
        "candidate_target_id": "AQP1",
        "candidate_target_uniprot": "P29972",
        "candidate_ligand_external_identifier": candidate_id,
        "candidate_ligand_name": _text(
            source_triage.get("chembl_aqp1_direct_like_binding_candidate_name")
        ),
        "candidate_activity_id": _text(
            source_triage.get("chembl_aqp1_direct_like_binding_candidate_activity_id")
        ),
        "candidate_standard_type": _text(
            source_triage.get("chembl_aqp1_direct_like_binding_candidate_standard_type")
        ),
        "candidate_standard_value_nM": _text(
            source_triage.get("chembl_aqp1_direct_like_binding_candidate_standard_value_nM")
        ),
        "candidate_reference_binding_kcal_mol": _text(
            source_triage.get("chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol")
        ),
        "candidate_blocker": _text(
            source_triage.get("chembl_aqp1_direct_like_binding_candidate_blocker")
        ),
        "candidate_claim_safe_ready": bool(
            _int(source_triage.get("direct_like_binding_candidate_claim_safe_ready_count")) > 0
        ),
        "candidate_required_operator_decision": (
            "confirm target/assay validity and either approve as claim-safe direct-like binding kcal "
            "or keep AQP1.core_binder_01 blocked"
        ),
        "candidate_source_artifact": "runs/aqp1_binding_source_modality_triage_current.json",
    }


def _next_slot_completion_packet(
    rows: list[dict[str, Any]],
    *,
    aqp1_source_triage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    next_row = next((dict(row) for row in rows if row.get("scope_promotion_allowed") is False), {})
    if not next_row:
        return {
            "packet_ready": False,
            "target_id": "",
            "packet_step": "",
            "operator_review_artifact": "",
            "validation_commands": [],
            "execution_enabled": False,
            "external_state_mutated": False,
            **_source_modality_guard({}, packet_ready=False),
        }
    target_id = _text(next_row.get("target_id"))
    packet_step = _text(next_row.get("packet_step"))
    request_mode = _text(next_row.get("request_mode"))
    required_missing_fields = [
        item.strip()
        for item in _text(next_row.get("required_missing_fields")).split(",")
        if item.strip()
    ]
    candidate_ligand_id = _text(next_row.get("replacement_ligand_id")) or "OPERATOR_FILL_REPLACEMENT_LIGAND_ID"
    evidence_type = (
        "negative_or_inactive_quantitative_value"
        if "negative" in request_mode
        else "direct_or_claim_safe_binding_kcal"
    )
    required_exact_evidence_fields = (
        NEGATIVE_EXACT_EVIDENCE_FIELDS
        if evidence_type == "negative_or_inactive_quantitative_value"
        else BINDER_EXACT_EVIDENCE_FIELDS
    )
    source_modality_guard = _source_modality_guard(next_row, packet_ready=True)
    validation_candidate = _operator_validation_candidate(
        aqp1_source_triage or {},
        target_id=target_id,
    )
    return {
        "completion_contract_version": "transporter_next_slot_exact_evidence_v2",
        "packet_ready": True,
        "target_id": target_id,
        "packet_step": packet_step,
        "slot_id": ".".join(item for item in [target_id, packet_step] if item),
        "current_ligand_id": _text(next_row.get("current_ligand_id")),
        "candidate_ligand_id": candidate_ligand_id,
        "candidate_is_binder": _text(next_row.get("replacement_is_binder")),
        "request_mode": request_mode,
        "evidence_state": _text(next_row.get("evidence_state")),
        "source_signal": _text(next_row.get("source_signal")),
        "required_missing_fields": required_missing_fields,
        "required_missing_field_count": len(required_missing_fields),
        "required_operator_intake_columns": [
            "target_id",
            "candidate_ligand_id",
            "reference_binding_kcal_mol",
            "source_url_or_doi",
            "smiles",
            "scaffold",
            "evidence_type",
        ],
        "required_exact_evidence_fields": required_exact_evidence_fields,
        "required_exact_evidence_field_count": len(required_exact_evidence_fields),
        "required_claim_guardrails": NEXT_SLOT_GUARDRAILS,
        "required_claim_guardrail_count": len(NEXT_SLOT_GUARDRAILS),
        "operator_validation_candidate_ready": bool(validation_candidate),
        "operator_validation_candidate": validation_candidate,
        "operator_validation_candidate_status": _text(
            validation_candidate.get("candidate_status")
        ),
        "operator_validation_candidate_ligand_external_identifier": _text(
            validation_candidate.get("candidate_ligand_external_identifier")
        ),
        "operator_validation_candidate_reference_binding_kcal_mol": _text(
            validation_candidate.get("candidate_reference_binding_kcal_mol")
        ),
        "operator_validation_candidate_blocker": _text(
            validation_candidate.get("candidate_blocker")
        ),
        "operator_validation_candidate_claim_safe_ready": bool(
            validation_candidate.get("candidate_claim_safe_ready") is True
        ),
        **source_modality_guard,
        "post_intake_synchronization_targets": NEXT_SLOT_SYNC_TARGETS,
        "post_intake_synchronization_target_count": len(NEXT_SLOT_SYNC_TARGETS),
        "return_bundle_required_artifacts": NEXT_SLOT_RETURN_ARTIFACTS,
        "return_bundle_required_artifact_count": len(NEXT_SLOT_RETURN_ARTIFACTS),
        "operator_review_artifact": "runs/transporter_manual_review_intake_template_current.csv",
        "completion_rule": (
            "Provide exact target-pair quantitative evidence for the named transporter target/ligand pair; "
            "binding claims require direct or claim-safe kcal/mol evidence, while negative rows require exact "
            "target-pair inactive/negative quantitative evidence. Review-only or functional surrogate evidence "
            "does not authorize scope promotion."
        ),
        "expected_evidence_type": evidence_type,
        "next_required_action": _text(next_row.get("next_required_action")),
        "validation_commands": NEXT_SLOT_VALIDATION_COMMANDS,
        "acceptance_gate_commands": NEXT_SLOT_VALIDATION_COMMANDS,
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _return_bundle_completion_matrix(next_packet: dict[str, Any]) -> list[dict[str, Any]]:
    if not next_packet.get("packet_ready"):
        return []
    slot_id = _text(next_packet.get("slot_id"))
    missing_fields = [str(item) for item in next_packet.get("required_missing_fields", [])]
    has_missing_fields = bool(missing_fields)
    artifact_rows = [
        (
            "operator_review_row",
            "runs/transporter_manual_review_intake_template_current.csv",
            [
                "target_match_decision",
                "operator_review_decision",
                "reference_binding_kcal_mol",
                "source_url_or_doi",
                "evidence_sentence_or_table_locator",
            ],
            "python3 tools/build_transporter_manual_review_intake_template.py",
            "Fill the next-slot operator review row with exact target-pair evidence and an explicit review decision.",
        ),
        (
            "binding_reference_sync_row",
            "config/ligand_binding_reference_blind_aqp1_v1.csv",
            ["candidate_ligand_id", "reference_binding_kcal_mol", "source_url_or_doi", "evidence_type"],
            "python3 tools/build_transporter_binder_promotion_gate.py",
            "Synchronize the accepted exact evidence into the AQP1 binding-reference CSV.",
        ),
        (
            "eval_split_sync_row",
            "config/ligand_eval_splits_blind_aqp1_v1.csv",
            ["candidate_ligand_id", "target_id", "split", "role"],
            "python3 tools/build_transporter_binder_promotion_gate.py",
            "Synchronize the accepted candidate identity into the AQP1 evaluation split CSV.",
        ),
        (
            "ligand_meta_sync_row",
            "config/ligand_meta_blind_aqp1_v1.csv",
            ["candidate_ligand_id", "ligand_smiles", "ligand_external_identifier", "scaffold"],
            "python3 tools/build_transporter_binder_promotion_gate.py",
            "Synchronize the accepted ligand identity, SMILES, external identifier, and scaffold metadata.",
        ),
        (
            "transporter_promotion_gate",
            "runs/transporter_binder_promotion_gate_current.json",
            ["claim_safe_step_ready", "authoritative_apply_allowed", "scope_promotion_allowed"],
            "python3 tools/build_transporter_binder_promotion_gate.py && python3 tools/build_transporter_p0_closure_readiness_matrix.py",
            "Rerun promotion gates after all next-slot evidence and synchronization artifacts are present.",
        ),
    ]
    matrix: list[dict[str, Any]] = []
    for artifact_id, artifact_path, required_fields, validation_command, next_action in artifact_rows:
        failed_check_ids = []
        if has_missing_fields:
            failed_check_ids.append("next_slot_required_missing_fields")
        failed_check_ids.append(f"{artifact_id}_not_operator_verified")
        matrix.append(
            {
                "artifact_id": artifact_id,
                "status": "blocked",
                "artifact_path": artifact_path,
                "slot_id": slot_id,
                "required_fields_or_columns": required_fields,
                "failed_check_ids": failed_check_ids,
                "failed_check_count": len(failed_check_ids),
                "missing_fields": missing_fields,
                "validation_command": validation_command,
                "next_action": next_action,
                "release_blocker": True,
                "execution_enabled": False,
                "scope_widened": False,
                "external_state_mutated": False,
            }
        )
    return matrix


def _append_unresolved_rows(
    rows: list[dict[str, Any]],
    *,
    target_id: str,
    workbook_payload: dict[str, Any],
    has_negative_cover: bool,
    second_wave_by_step: dict[str, dict[str, Any]] | None = None,
    claim_safe_steps: set[str] | None = None,
) -> None:
    second_wave_by_step = second_wave_by_step or {}
    claim_safe_steps = claim_safe_steps or set()
    for row in _workbook_rows(workbook_payload):
        if _is_ready(row):
            continue
        step = _text(row.get("packet_step"))
        second_wave = second_wave_by_step.get(step)
        mode = _request_mode(target_id, row, has_negative_cover=has_negative_cover, second_wave=second_wave)
        rows.append(
            {
                "target_id": target_id,
                "packet_step": step,
                "current_ligand_id": _text(row.get("current_ligand_id")),
                "replacement_ligand_id": _text(row.get("replacement_ligand_id")),
                "replacement_is_binder": _text(row.get("replacement_is_binder")),
                "replacement_role": _text(row.get("replacement_role")),
                "required_missing_fields": _text(row.get("required_missing_fields")),
                "request_mode": mode,
                "evidence_state": _evidence_state(target_id, row, has_negative_cover=has_negative_cover, second_wave=second_wave),
                "source_signal": _text(row.get("replacement_source")) or _text((second_wave or {}).get("source_anchor")),
                "claim_safe_step_ready": step in claim_safe_steps,
                "authoritative_apply_allowed": False,
                "scope_promotion_allowed": False,
                "next_required_action": _next_action(target_id, row, mode),
            }
        )


def build_payload(
    *,
    closure_payload: dict[str, Any],
    aqp1_workbook_payload: dict[str, Any],
    aqp1_negative_payload: dict[str, Any],
    glut1_workbook_payload: dict[str, Any],
    glut1_second_wave_payload: dict[str, Any],
    glut1_claim_safe_payload: dict[str, Any],
    aqp1_negative_intake_payload: dict[str, Any] | None = None,
    aqp1_negative_slot_closure_payload: dict[str, Any] | None = None,
    aqp1_binding_source_modality_triage_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    closure = _summary(closure_payload)
    aqp1_negative = _summary(aqp1_negative_payload)
    aqp1_negative_intake = _summary(aqp1_negative_intake_payload or {})
    aqp1_negative_slot_closure = _summary(aqp1_negative_slot_closure_payload or {})
    aqp1_source_triage = _summary(aqp1_binding_source_modality_triage_payload or {})
    glut1_claim = _summary(glut1_claim_safe_payload)
    rows: list[dict[str, Any]] = []
    aqp1_negative_review_ready = _int(aqp1_negative_intake.get("review_ready_row_count")) >= 3 or _int(
        aqp1_negative.get("negative_slot_cover_ready_count")
    ) >= 3
    aqp1_negative_authoritative_ready = _aqp1_negative_authoritative_ready(
        request_payload=aqp1_negative_payload,
        intake_payload=aqp1_negative_intake_payload or {},
        slot_closure_payload=aqp1_negative_slot_closure_payload or {},
    )
    _append_unresolved_rows(
        rows,
        target_id="AQP1",
        workbook_payload=aqp1_workbook_payload,
        has_negative_cover=aqp1_negative_authoritative_ready,
    )
    _append_unresolved_rows(
        rows,
        target_id="GLUT1_4PYP",
        workbook_payload=glut1_workbook_payload,
        has_negative_cover=False,
        second_wave_by_step=_second_wave_by_step(glut1_second_wave_payload),
        claim_safe_steps=_claim_safe_steps(glut1_claim_safe_payload),
    )
    binder_rows = [row for row in rows if row["replacement_is_binder"] == "1"]
    negative_rows = [row for row in rows if row["replacement_is_binder"] == "0"]
    sync_rows = [row for row in rows if row["request_mode"] == "sync_exact_negative_evidence_into_workbook_required"]
    exact_evidence_rows = [row for row in rows if "exact_target_pair" in row["request_mode"] or "direct_binding" in row["request_mode"]]
    next_slot_completion = _next_slot_completion_packet(
        rows,
        aqp1_source_triage=aqp1_source_triage,
    )
    next_slot_return_bundle_matrix = _return_bundle_completion_matrix(next_slot_completion)
    next_slot_return_bundle_blockers = [
        row for row in next_slot_return_bundle_matrix if _text(row.get("status")) != "ready"
    ]
    next_slot_return_bundle_first_blocker = (
        next_slot_return_bundle_blockers[0] if next_slot_return_bundle_blockers else {}
    )
    summary = {
        "packet_type": "transporter_p0_evidence_acquisition_packet",
        "evidence_acquisition_packet_ready": True,
        "closure_row_count": _int(closure.get("closure_row_count")),
        "current_membrane_p0_open_count": _int(closure.get("current_membrane_p0_open_count")),
        "unresolved_slot_count": len(rows),
        "binder_unresolved_slot_count": len(binder_rows),
        "negative_unresolved_slot_count": len(negative_rows),
        "negative_sync_slot_count": len(sync_rows),
        "exact_evidence_request_slot_count": len(exact_evidence_rows),
        "aqp1_negative_review_ready": aqp1_negative_review_ready,
        "aqp1_negative_authoritative_ready": aqp1_negative_authoritative_ready,
        "aqp1_negative_authoritative_apply_allowed_count": _int(
            aqp1_negative_intake.get("authoritative_negative_apply_allowed_count")
        ),
        "aqp1_negative_closure_allowed": aqp1_negative_intake.get("negative_evidence_closure_allowed") is True,
        "glut1_claim_safe_binding_kcal_ready_count": _int(glut1_claim.get("claim_safe_binding_kcal_ready_count")),
        "next_slot_completion_packet_ready": next_slot_completion["packet_ready"],
        "next_slot_completion_packet": next_slot_completion,
        "next_slot_return_bundle_required_artifacts": NEXT_SLOT_RETURN_ARTIFACTS,
        "next_slot_return_bundle_required_artifact_count": len(NEXT_SLOT_RETURN_ARTIFACTS),
        "next_slot_return_bundle_completion_matrix": next_slot_return_bundle_matrix,
        "next_slot_return_bundle_completion_matrix_count": len(next_slot_return_bundle_matrix),
        "next_slot_return_bundle_blocker_count": len(next_slot_return_bundle_blockers),
        "next_slot_return_bundle_next_artifact_id": _text(next_slot_return_bundle_first_blocker.get("artifact_id")),
        "next_slot_return_bundle_next_artifact_path": _text(next_slot_return_bundle_first_blocker.get("artifact_path")),
        "next_slot_return_bundle_next_artifact_failed_check_ids": [
            str(item) for item in (next_slot_return_bundle_first_blocker.get("failed_check_ids") or [])
        ],
        "next_evidence_slot_id": _text(next_slot_completion.get("slot_id")),
        "next_evidence_slot_target_id": _text(next_slot_completion.get("target_id")),
        "next_evidence_slot_packet_step": _text(next_slot_completion.get("packet_step")),
        "next_evidence_slot_candidate_ligand_id": _text(next_slot_completion.get("candidate_ligand_id")),
        "next_evidence_slot_request_mode": _text(next_slot_completion.get("request_mode")),
        "next_evidence_slot_source_signal": _text(next_slot_completion.get("source_signal")),
        "next_evidence_slot_required_missing_fields": ",".join(
            str(item) for item in next_slot_completion.get("required_missing_fields", [])
        ),
        "next_evidence_slot_operator_review_artifact": _text(
            next_slot_completion.get("operator_review_artifact")
        ),
        "next_slot_source_modality_guard_ready": bool(
            next_slot_completion.get("next_slot_source_modality_guard_ready") is True
        ),
        "next_slot_source_modality": _text(
            next_slot_completion.get("next_slot_source_modality")
        ),
        "next_slot_source_modality_claim_safe": bool(
            next_slot_completion.get("next_slot_source_modality_claim_safe") is True
        ),
        "next_slot_source_modality_direct_binding_claim_allowed": bool(
            next_slot_completion.get("next_slot_source_modality_direct_binding_claim_allowed") is True
        ),
        "next_slot_source_modality_decision": _text(
            next_slot_completion.get("next_slot_source_modality_decision")
        ),
        "next_slot_source_modality_guardrails": [
            str(item)
            for item in (next_slot_completion.get("next_slot_source_modality_guardrails") or [])
        ],
        "next_slot_source_modality_observed_signal": _text(
            next_slot_completion.get("next_slot_source_modality_observed_signal")
        ),
        "next_slot_source_modality_required_upgrade": _text(
            next_slot_completion.get("next_slot_source_modality_required_upgrade")
        ),
        "aqp1_binding_source_modality_triage_ready": bool(
            aqp1_source_triage.get("source_modality_guard_ready") is True
        ),
        "aqp1_binding_source_modality_triage_status": _text(
            aqp1_source_triage.get("status")
        ),
        "aqp1_binding_source_modality_triage_artifact": _text(
            aqp1_source_triage.get("triage_artifact")
            or str(DEFAULT_AQP1_BINDING_SOURCE_MODALITY_TRIAGE_JSON)
        ),
        "aqp1_binding_source_modality_triage_decision": _text(
            aqp1_source_triage.get("triage_decision")
        ),
        "aqp1_binding_source_modality_triage_next_required_step": _text(
            aqp1_source_triage.get("next_required_step")
        ),
        "aqp1_binding_source_modality_direct_experimental_binding_row_count": _int(
            aqp1_source_triage.get("direct_experimental_binding_row_count")
        ),
        "aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count": _int(
            aqp1_source_triage.get("claim_safe_binding_kcal_ready_count")
        ),
        "aqp1_binding_source_modality_public_direct_binding_recheck_ready": bool(
            aqp1_source_triage.get("public_direct_binding_recheck_ready") is True
        ),
        "aqp1_binding_source_modality_public_direct_binding_recheck_source_count": _int(
            aqp1_source_triage.get("public_direct_binding_recheck_source_count")
        ),
        "aqp1_binding_source_modality_public_direct_binding_recheck_result": _text(
            aqp1_source_triage.get("public_direct_binding_recheck_result")
        ),
        "aqp1_binding_source_modality_public_database_recheck_row_count": _int(
            aqp1_source_triage.get("public_database_recheck_row_count")
        ),
        "aqp1_binding_source_modality_ligand_identity_mismatch_row_count": _int(
            aqp1_source_triage.get("ligand_identity_mismatch_row_count")
        ),
        "aqp1_binding_source_modality_direct_like_binding_candidate_row_count": _int(
            aqp1_source_triage.get("direct_like_binding_candidate_row_count")
        ),
        "aqp1_binding_source_modality_direct_like_binding_candidate_claim_safe_ready_count": _int(
            aqp1_source_triage.get("direct_like_binding_candidate_claim_safe_ready_count")
        ),
        "aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_row_count": _int(
            aqp1_source_triage.get("chembl_aqp1_direct_like_binding_row_count")
        ),
        "aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_claim_safe_row_count": _int(
            aqp1_source_triage.get("chembl_aqp1_direct_like_binding_claim_safe_row_count")
        ),
        "aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_chembl_id": _text(
            aqp1_source_triage.get("chembl_aqp1_direct_like_binding_candidate_chembl_id")
        ),
        "aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol": _text(
            aqp1_source_triage.get("chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol")
        ),
        "aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_blocker": _text(
            aqp1_source_triage.get("chembl_aqp1_direct_like_binding_candidate_blocker")
        ),
        "aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_affinity_row_count": _int(
            aqp1_source_triage.get("bindingdb_aqp1_expanded_cutoff_affinity_row_count")
        ),
        "aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count": _int(
            aqp1_source_triage.get("bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count")
        ),
        "aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_best_functional_ic50_nM": _text(
            aqp1_source_triage.get("bindingdb_aqp1_expanded_cutoff_best_functional_ic50_nM")
        ),
        "aqp1_binding_source_modality_bacopaside_ii_pubchem_cid": _text(
            aqp1_source_triage.get("bacopaside_ii_pubchem_cid")
        ),
        "aqp1_binding_source_modality_bacopaside_ii_chembl_id": _text(
            aqp1_source_triage.get("bacopaside_ii_chembl_id")
        ),
        "aqp1_binding_source_modality_aqp1_chembl_target_id": _text(
            aqp1_source_triage.get("aqp1_chembl_target_id")
        ),
        "aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count": _int(
            aqp1_source_triage.get("aqp1_bindingdb_uniprot_affinity_row_count")
        ),
        "aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count": _int(
            aqp1_source_triage.get("bacopaside_ii_chembl_aqp1_activity_row_count")
        ),
        "aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail": _text(
            aqp1_source_triage.get("functional_ic50_identity_mismatch_detail")
        ),
        "aqp1_binding_source_modality_replacement_reference_binding_kcal_mol_action": _text(
            aqp1_source_triage.get("replacement_reference_binding_kcal_mol_action")
        ),
        "aqp1_binding_source_modality_computational_binding_energy_row_count": _int(
            aqp1_source_triage.get("computational_binding_energy_row_count")
        ),
        "aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol": _text(
            aqp1_source_triage.get("best_computational_binding_energy_kcal_mol")
        ),
        "aqp1_binding_source_modality_best_functional_delta_g_surrogate_kcal_mol": _text(
            aqp1_source_triage.get("best_functional_delta_g_surrogate_kcal_mol")
        ),
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Resolve unresolved transporter ligand slots, then regenerate AQP1/GLUT1 workbooks, P0 closure, membrane readiness, donor-policy, and scope gates."
        ),
    }
    return {
        "summary": summary,
        "rows": rows,
        "next_slot_completion_packet": next_slot_completion,
        "next_slot_return_bundle_completion_matrix": next_slot_return_bundle_matrix,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Transporter P0 Evidence Acquisition Packet",
        "",
        f"- evidence_acquisition_packet_ready: `{s['evidence_acquisition_packet_ready']}`",
        f"- current_membrane_p0_open_count: `{s['current_membrane_p0_open_count']}`",
        f"- closure_row_count: `{s['closure_row_count']}`",
        f"- unresolved_slot_count: `{s['unresolved_slot_count']}`",
        f"- binder_unresolved_slot_count: `{s['binder_unresolved_slot_count']}`",
        f"- negative_unresolved_slot_count: `{s['negative_unresolved_slot_count']}`",
        f"- negative_sync_slot_count: `{s['negative_sync_slot_count']}`",
        f"- exact_evidence_request_slot_count: `{s['exact_evidence_request_slot_count']}`",
        f"- aqp1_negative_review_ready: `{s['aqp1_negative_review_ready']}`",
        f"- aqp1_negative_authoritative_ready: `{s['aqp1_negative_authoritative_ready']}`",
        f"- aqp1_negative_authoritative_apply_allowed_count: `{s['aqp1_negative_authoritative_apply_allowed_count']}`",
        f"- aqp1_negative_closure_allowed: `{s['aqp1_negative_closure_allowed']}`",
        f"- glut1_claim_safe_binding_kcal_ready_count: `{s['glut1_claim_safe_binding_kcal_ready_count']}`",
        f"- next_slot_completion_packet_ready: `{s['next_slot_completion_packet_ready']}`",
        f"- next_slot_return_bundle_required_artifact_count: `{s['next_slot_return_bundle_required_artifact_count']}`",
        f"- next_slot_return_bundle_blocker_count: `{s['next_slot_return_bundle_blocker_count']}`",
        f"- next_slot_return_bundle_next_artifact_id: `{s['next_slot_return_bundle_next_artifact_id']}`",
        f"- next_slot_return_bundle_next_artifact_path: `{s['next_slot_return_bundle_next_artifact_path']}`",
        f"- next_evidence_slot_id: `{s['next_evidence_slot_id']}`",
        f"- next_evidence_slot_candidate_ligand_id: `{s['next_evidence_slot_candidate_ligand_id']}`",
        f"- next_evidence_slot_request_mode: `{s['next_evidence_slot_request_mode']}`",
        f"- next_evidence_slot_operator_review_artifact: `{s['next_evidence_slot_operator_review_artifact']}`",
        f"- next_slot_source_modality_guard_ready: `{s['next_slot_source_modality_guard_ready']}`",
        f"- next_slot_source_modality: `{s['next_slot_source_modality']}`",
        f"- next_slot_source_modality_claim_safe: `{s['next_slot_source_modality_claim_safe']}`",
        f"- next_slot_source_modality_direct_binding_claim_allowed: `{s['next_slot_source_modality_direct_binding_claim_allowed']}`",
        f"- next_slot_source_modality_decision: `{s['next_slot_source_modality_decision']}`",
        f"- next_slot_source_modality_required_upgrade: `{s['next_slot_source_modality_required_upgrade']}`",
        f"- scope_promotion_allowed: `{s['scope_promotion_allowed']}`",
        "",
        "## Unresolved Slots",
        "",
        "| target | step | replacement | mode | evidence state | missing | next action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['packet_step']}` | `{row['replacement_ligand_id'] or '-'}` | "
            f"`{row['request_mode']}` | `{row['evidence_state']}` | "
            f"`{row['required_missing_fields'] or '-'}` | {row['next_required_action']} |"
        )
    lines.extend([
        "",
        "## Next Slot Return Bundle",
        "",
        "| artifact | status | failed checks | validation command | next action |",
        "| --- | --- | --- | --- | --- |",
    ])
    for row in payload.get("next_slot_return_bundle_completion_matrix", []):
        lines.append(
            f"| `{row['artifact_id']}` | `{row['status']}` | "
            f"`{','.join(str(item) for item in row['failed_check_ids'])}` | "
            f"`{row['validation_command']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build transporter P0 evidence acquisition packet.")
    parser.add_argument("--closure-json", default=str(DEFAULT_CLOSURE_JSON))
    parser.add_argument("--aqp1-workbook-json", default=str(DEFAULT_AQP1_WORKBOOK_JSON))
    parser.add_argument("--aqp1-negative-json", default=str(DEFAULT_AQP1_NEGATIVE_JSON))
    parser.add_argument("--aqp1-negative-intake-json", default=str(DEFAULT_AQP1_NEGATIVE_INTAKE_JSON))
    parser.add_argument("--aqp1-negative-slot-closure-json", default=str(DEFAULT_AQP1_NEGATIVE_SLOT_CLOSURE_JSON))
    parser.add_argument(
        "--aqp1-binding-source-modality-triage-json",
        default=str(DEFAULT_AQP1_BINDING_SOURCE_MODALITY_TRIAGE_JSON),
    )
    parser.add_argument("--glut1-workbook-json", default=str(DEFAULT_GLUT1_WORKBOOK_JSON))
    parser.add_argument("--glut1-second-wave-json", default=str(DEFAULT_GLUT1_SECOND_WAVE_JSON))
    parser.add_argument("--glut1-claim-safe-json", default=str(DEFAULT_GLUT1_CLAIM_SAFE_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        closure_payload=_load_json(args.closure_json),
        aqp1_workbook_payload=_load_json(args.aqp1_workbook_json),
        aqp1_negative_payload=_load_json(args.aqp1_negative_json),
        aqp1_negative_intake_payload=_load_json(args.aqp1_negative_intake_json),
        aqp1_negative_slot_closure_payload=_load_json(args.aqp1_negative_slot_closure_json),
        aqp1_binding_source_modality_triage_payload=_load_json(
            args.aqp1_binding_source_modality_triage_json
        ),
        glut1_workbook_payload=_load_json(args.glut1_workbook_json),
        glut1_second_wave_payload=_load_json(args.glut1_second_wave_json),
        glut1_claim_safe_payload=_load_json(args.glut1_claim_safe_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
