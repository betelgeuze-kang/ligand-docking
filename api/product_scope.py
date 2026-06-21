from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_SCOPE_BREADTH_CONTRACT_ARTIFACT = ROOT / "runs" / "product_scope_breadth_contract_current.json"
PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT = ROOT / "runs" / "product_scope_breadth_closure_checklist_current.json"
PRODUCT_SCOPE_EVIDENCE_PRIORITY_ARTIFACT = (
    ROOT / "runs" / "product_scope_breadth_evidence_priority_packet_current.json"
)
PRODUCT_SCOPE_EVIDENCE_INTAKE_READINESS_ARTIFACT = (
    ROOT / "runs" / "product_scope_breadth_evidence_intake_readiness_current.json"
)
TRANSPORTER_MANUAL_REVIEW_INTAKE_ARTIFACT = ROOT / "runs" / "transporter_manual_review_intake_template_current.json"
PXR_EXACT_REVIEW_INTAKE_ARTIFACT = ROOT / "runs" / "pxr_exact_evidence_review_intake_template_current.json"
AQP1_OPERATOR_VALIDATION_CANDIDATE_ARTIFACT = (
    ROOT / "runs" / "aqp1_operator_validation_candidate_packet_current.json"
)
AQP1_DIRECT_BINDING_PROCUREMENT_ARTIFACT = (
    ROOT / "runs" / "aqp1_direct_binding_procurement_packet_current.json"
)


def _read_json_object(path: Path) -> dict[str, Any]:
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


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.replace(",", ";").split(";") if part.strip()]


@router.get("/scope-breadth-contract")
async def get_product_scope_breadth_contract() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_SCOPE_BREADTH_CONTRACT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    scope_acceptance_matrix = (
        packet.get("scope_acceptance_matrix") if isinstance(packet.get("scope_acceptance_matrix"), list) else []
    )
    scope_acceptance_stage_evidence_matrix = (
        packet.get("scope_acceptance_stage_evidence_matrix")
        if isinstance(packet.get("scope_acceptance_stage_evidence_matrix"), list)
        else []
    )
    scope_acceptance_current_blocked_stage_evidence_matrix = (
        packet.get("scope_acceptance_current_blocked_stage_evidence_matrix")
        if isinstance(packet.get("scope_acceptance_current_blocked_stage_evidence_matrix"), list)
        else []
    )
    if not summary:
        return {
            "status": "missing_product_scope_breadth_contract",
            "artifact_path": str(PRODUCT_SCOPE_BREADTH_CONTRACT_ARTIFACT),
            "scope_breadth_ready": False,
            "scope_widened": False,
            "scope_claim_posture_ready": False,
            "restricted_scope_claim_allowed": False,
            "allowed_scope_families": [],
            "domain_count": 0,
            "ready_domain_count": 0,
            "missing_domain_count": 0,
            "ready_domains": [],
            "missing_domains": [],
            "first_blocked_domain": "",
            "first_blocked_domain_artifact": "",
            "first_blocked_domain_observed": "",
            "first_blocked_domain_requirement": "",
            "first_blocked_domain_next_action": "",
            "transporter_p0_closure_packet_ready": False,
            "transporter_p0_closure_artifact": "",
            "transporter_p0_current_membrane_open_count": 0,
            "transporter_p0_closure_row_count": 0,
            "transporter_p0_count_matches_readiness": False,
            "transporter_p0_aqp1_core_open_count": 0,
            "transporter_p0_glut1_core_open_count": 0,
            "transporter_p0_glut1_reference_placeholder_rows_after_apply": 0,
            "transporter_p0_glut1_split_placeholder_rows_after_apply": 0,
            "transporter_p0_glut1_meta_placeholder_rows_after_apply": 0,
            "transporter_p0_next_required_step": "",
            "transporter_p0_readiness_matrix_ready": False,
            "transporter_p0_readiness_matrix_artifact": "",
            "transporter_p0_auto_close_ready_artifact_count": 0,
            "transporter_p0_manual_or_external_required_artifact_count": 0,
            "transporter_p0_unresolved_slot_count": 0,
            "transporter_p0_auto_close_ready_slot_count": 0,
            "transporter_p0_external_exact_evidence_required_slot_count": 0,
            "transporter_p0_first_manual_or_external_required_step_id": "",
            "transporter_p0_first_manual_or_external_required_slot_step": "",
            "transporter_p0_first_manual_or_external_required_action": "",
            "transporter_p0_evidence_acquisition_packet_ready": False,
            "transporter_p0_evidence_acquisition_artifact": "",
            "transporter_p0_evidence_acquisition_exact_request_slot_count": 0,
            "transporter_p0_evidence_acquisition_unresolved_slot_count": 0,
            "transporter_p0_evidence_acquisition_first_target_id": "",
            "transporter_p0_evidence_acquisition_first_packet_step": "",
            "transporter_p0_evidence_acquisition_first_replacement_ligand_id": "",
            "transporter_p0_evidence_acquisition_first_request_mode": "",
            "transporter_p0_evidence_acquisition_first_source_signal": "",
            "transporter_p0_evidence_acquisition_first_required_missing_fields": "",
            "transporter_p0_evidence_acquisition_first_next_required_action": "",
            "transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": False,
            "transporter_p0_evidence_acquisition_next_slot_completion_packet": {},
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts": [],
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count": 0,
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix": [],
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count": 0,
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count": 0,
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id": "",
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path": "",
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_failed_check_ids": [],
            "transporter_p0_evidence_acquisition_next_slot_id": "",
            "transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": "",
            "transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready": False,
            "transporter_p0_evidence_acquisition_next_slot_source_modality": "",
            "transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe": False,
            "transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed": False,
            "transporter_p0_evidence_acquisition_next_slot_source_modality_decision": "",
            "transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails": [],
            "transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal": "",
            "transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade": "",
            "evidence_queue_next_operator_completion_aqp1_review_sidecar_ready": False,
            "evidence_queue_next_operator_completion_aqp1_review_candidate_name": "",
            "evidence_queue_next_operator_completion_aqp1_review_source_anchor": "",
            "evidence_queue_next_operator_completion_aqp1_review_target_uniprot": "",
            "evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": "",
            "evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed": "",
            "evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": "",
            "evidence_queue_pxr_exact_review_sidecar_row_count": 0,
            "evidence_queue_next_pxr_exact_review_sidecar_ready": False,
            "evidence_queue_next_pxr_exact_review_row_id": "",
            "evidence_queue_next_pxr_exact_review_candidate_name": "",
            "evidence_queue_next_pxr_exact_review_required_evidence_mode": "",
            "evidence_queue_next_pxr_exact_review_target_match_confirmed": "",
            "evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol": "",
            "evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi": "",
            "evidence_queue_next_pxr_exact_review_authoritative_apply_allowed": False,
            "evidence_queue_next_pxr_exact_review_scope_promotion_allowed": False,
            "transporter_target_ready_for_promotion_count": 0,
            "transporter_target_blocked_for_promotion_count": 0,
            "transporter_target_ready_for_promotion_ids": [],
            "transporter_target_blocked_for_promotion_ids": [],
            "transporter_primary_blocker_target_id": "",
            "transporter_primary_blocker_packet_step": "",
            "transporter_primary_blocker_candidate_name": "",
            "allowed_claim_scopes": [],
            "blocked_claim_scopes": ["product_scope_breadth_contract_missing"],
            "blocked_claim_scope_count": 1,
            "general_platform_claim_allowed": False,
            "general_platform_claim_blocked": True,
            "general_protein_ligand_platform_ready": False,
            "scope_claim_boundary_detail": "",
            "pxr_exact_review_intake_ready": False,
            "pxr_exact_review_template_row_count": 0,
            "pxr_exact_review_next_review_completion_packet_ready": False,
            "pxr_exact_review_next_review_completion_packet": {},
            "pxr_exact_review_next_review_return_bundle_required_artifacts": [],
            "pxr_exact_review_next_review_return_bundle_required_artifact_count": 0,
            "pxr_exact_review_next_review_return_bundle_completion_matrix": [],
            "pxr_exact_review_next_review_return_bundle_completion_matrix_count": 0,
            "pxr_exact_review_next_review_return_bundle_blocker_count": 0,
            "pxr_exact_review_next_review_return_bundle_next_artifact_id": "",
            "pxr_exact_review_next_review_return_bundle_next_artifact_path": "",
            "pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids": [],
            "pxr_exact_review_next_review_row_id": "",
            "pxr_exact_review_next_review_candidate_name": "",
            "pxr_exact_review_next_review_operator_review_artifact": "",
            "pxr_source_modality_triage_ready": False,
            "pxr_source_modality_triage_status": "",
            "pxr_source_modality_triage_artifact": "",
            "pxr_source_modality_triage_decision": "",
            "pxr_source_modality_public_evidence_recheck_ready": False,
            "pxr_source_modality_public_recheck_artifact": "",
            "pxr_source_modality_public_recheck_candidate_count": 0,
            "pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count": 0,
            "pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count": 0,
            "pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count": 0,
            "pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count": 0,
            "pxr_source_modality_public_recheck_all_candidates_remain_blocked": False,
            "pxr_source_modality_public_recheck_first_blocked_candidate_name": "",
            "pxr_source_modality_public_recheck_first_blocked_reason": "",
            "pxr_source_modality_direct_replacement_candidate_packet_ready": False,
            "pxr_source_modality_direct_replacement_artifact": "",
            "pxr_source_modality_direct_replacement_candidate_count": 0,
            "pxr_source_modality_direct_replacement_selected_candidate_count": 0,
            "pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count": 0,
            "pxr_source_modality_direct_replacement_first_ligand_id": "",
            "pxr_source_modality_direct_replacement_first_molecule_chembl_id": "",
            "pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol": "",
            "pxr_source_modality_direct_replacement_first_source": "",
            "pxr_source_modality_direct_replacement_apply_draft_ready": False,
            "pxr_source_modality_direct_replacement_apply_draft_status": "",
            "pxr_source_modality_direct_replacement_apply_draft_artifact": "",
            "pxr_source_modality_direct_replacement_apply_draft_workbook_row_count": 0,
            "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft": 0,
            "pxr_source_modality_direct_replacement_apply_draft_overlay_row_count": 0,
            "pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft": 0,
            "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft": 0,
            "pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id": "",
            "pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched": False,
            "pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count": 0,
            "pxr_source_modality_direct_or_claim_safe_quantitative_ready_count": 0,
            "pxr_source_modality_accepted_for_scope_promotion_count": 0,
            "pxr_source_modality_next_review_row_id": "",
            "pxr_source_modality_next_review_candidate_name": "",
            "pxr_source_modality_next_review_source_modality": "",
            "pxr_source_modality_next_review_rejection_reason": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_ready": False,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_status": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_artifact": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_decision": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_experimental_binding_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_ready": False,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_replacement_reference_binding_kcal_mol_action": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_computational_binding_energy_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol": "",
            "scope_acceptance_matrix_ready": False,
            "scope_acceptance_stage_count": 0,
            "scope_acceptance_ready_stage_count": 0,
            "scope_acceptance_blocked_stage_count": 0,
            "scope_acceptance_stage_ids": [],
            "scope_acceptance_ready_stage_ids": [],
            "scope_acceptance_blocked_stage_ids": [],
            "scope_acceptance_next_stage_id": "",
            "scope_acceptance_next_stage_artifact": "",
            "scope_acceptance_next_stage_validation_command": "",
            "scope_acceptance_next_stage_release_effect": "",
            "scope_acceptance_next_stage_unlock_claim_scopes": [],
            "scope_acceptance_next_stage_required_checks": [],
            "scope_acceptance_next_stage_next_action": "",
            "scope_acceptance_stage_evidence_matrix": [],
            "scope_acceptance_stage_evidence_matrix_count": 0,
            "scope_acceptance_current_blocked_stage_evidence_matrix": [],
            "scope_acceptance_current_blocked_stage_evidence_matrix_count": 0,
            "domain_rows": [],
            "scope_acceptance_matrix": [],
            "next_required_step": "Run python3 tools/build_product_scope_breadth_contract.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened_by_endpoint": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product scope-breadth-contract endpoint only; the local breadth contract artifact is missing. "
                "It does not acquire evidence, widen claims, run docking, promote scope, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(PRODUCT_SCOPE_BREADTH_CONTRACT_ARTIFACT),
        "scope_breadth_ready": bool(summary.get("scope_breadth_ready") is True),
        "scope_widened": bool(summary.get("scope_widened") is True),
        "scope_claim_posture_ready": bool(summary.get("scope_claim_posture_ready") is True),
        "restricted_scope_claim_allowed": bool(summary.get("restricted_scope_claim_allowed") is True),
        "allowed_scope_families": list(summary.get("allowed_scope_families") or []),
        "domain_count": int(summary.get("domain_count") or 0),
        "ready_domain_count": int(summary.get("ready_domain_count") or 0),
        "missing_domain_count": int(summary.get("missing_domain_count") or 0),
        "ready_domains": list(summary.get("ready_domains") or []),
        "missing_domains": list(summary.get("missing_domains") or []),
        "first_blocked_domain": summary.get("first_blocked_domain", ""),
        "first_blocked_domain_artifact": summary.get("first_blocked_domain_artifact", ""),
        "first_blocked_domain_observed": summary.get("first_blocked_domain_observed", ""),
        "first_blocked_domain_requirement": summary.get("first_blocked_domain_requirement", ""),
        "first_blocked_domain_next_action": summary.get("first_blocked_domain_next_action", ""),
        "transporter_p0_closure_packet_ready": bool(summary.get("transporter_p0_closure_packet_ready") is True),
        "transporter_p0_closure_artifact": summary.get("transporter_p0_closure_artifact", ""),
        "transporter_p0_current_membrane_open_count": int(
            summary.get("transporter_p0_current_membrane_open_count") or 0
        ),
        "transporter_p0_closure_row_count": int(summary.get("transporter_p0_closure_row_count") or 0),
        "transporter_p0_count_matches_readiness": bool(
            summary.get("transporter_p0_count_matches_readiness") is True
        ),
        "transporter_p0_aqp1_core_open_count": int(summary.get("transporter_p0_aqp1_core_open_count") or 0),
        "transporter_p0_glut1_core_open_count": int(summary.get("transporter_p0_glut1_core_open_count") or 0),
        "transporter_p0_glut1_reference_placeholder_rows_after_apply": int(
            summary.get("transporter_p0_glut1_reference_placeholder_rows_after_apply") or 0
        ),
        "transporter_p0_glut1_split_placeholder_rows_after_apply": int(
            summary.get("transporter_p0_glut1_split_placeholder_rows_after_apply") or 0
        ),
        "transporter_p0_glut1_meta_placeholder_rows_after_apply": int(
            summary.get("transporter_p0_glut1_meta_placeholder_rows_after_apply") or 0
        ),
        "transporter_p0_next_required_step": summary.get("transporter_p0_next_required_step", ""),
        "transporter_p0_readiness_matrix_ready": bool(
            summary.get("transporter_p0_readiness_matrix_ready") is True
        ),
        "transporter_p0_readiness_matrix_artifact": summary.get(
            "transporter_p0_readiness_matrix_artifact", ""
        ),
        "transporter_p0_auto_close_ready_artifact_count": int(
            summary.get("transporter_p0_auto_close_ready_artifact_count") or 0
        ),
        "transporter_p0_manual_or_external_required_artifact_count": int(
            summary.get("transporter_p0_manual_or_external_required_artifact_count") or 0
        ),
        "transporter_p0_unresolved_slot_count": int(summary.get("transporter_p0_unresolved_slot_count") or 0),
        "transporter_p0_auto_close_ready_slot_count": int(
            summary.get("transporter_p0_auto_close_ready_slot_count") or 0
        ),
        "transporter_p0_external_exact_evidence_required_slot_count": int(
            summary.get("transporter_p0_external_exact_evidence_required_slot_count") or 0
        ),
        "transporter_p0_first_manual_or_external_required_step_id": summary.get(
            "transporter_p0_first_manual_or_external_required_step_id", ""
        ),
        "transporter_p0_first_manual_or_external_required_slot_step": summary.get(
            "transporter_p0_first_manual_or_external_required_slot_step", ""
        ),
        "transporter_p0_first_manual_or_external_required_action": summary.get(
            "transporter_p0_first_manual_or_external_required_action", ""
        ),
        "transporter_p0_evidence_acquisition_packet_ready": bool(
            summary.get("transporter_p0_evidence_acquisition_packet_ready") is True
        ),
        "transporter_p0_evidence_acquisition_artifact": summary.get(
            "transporter_p0_evidence_acquisition_artifact", ""
        ),
        "transporter_p0_evidence_acquisition_exact_request_slot_count": int(
            summary.get("transporter_p0_evidence_acquisition_exact_request_slot_count") or 0
        ),
        "transporter_p0_evidence_acquisition_unresolved_slot_count": int(
            summary.get("transporter_p0_evidence_acquisition_unresolved_slot_count") or 0
        ),
        "transporter_p0_evidence_acquisition_first_target_id": summary.get(
            "transporter_p0_evidence_acquisition_first_target_id", ""
        ),
        "transporter_p0_evidence_acquisition_first_packet_step": summary.get(
            "transporter_p0_evidence_acquisition_first_packet_step", ""
        ),
        "transporter_p0_evidence_acquisition_first_replacement_ligand_id": summary.get(
            "transporter_p0_evidence_acquisition_first_replacement_ligand_id", ""
        ),
        "transporter_p0_evidence_acquisition_first_request_mode": summary.get(
            "transporter_p0_evidence_acquisition_first_request_mode", ""
        ),
        "transporter_p0_evidence_acquisition_first_source_signal": summary.get(
            "transporter_p0_evidence_acquisition_first_source_signal", ""
        ),
        "transporter_p0_evidence_acquisition_first_required_missing_fields": summary.get(
            "transporter_p0_evidence_acquisition_first_required_missing_fields", ""
        ),
        "transporter_p0_evidence_acquisition_first_next_required_action": summary.get(
            "transporter_p0_evidence_acquisition_first_next_required_action", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": bool(
            summary.get("transporter_p0_evidence_acquisition_next_slot_completion_packet_ready") is True
        ),
        "transporter_p0_evidence_acquisition_next_slot_completion_packet": dict(
            summary.get("transporter_p0_evidence_acquisition_next_slot_completion_packet") or {}
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts": list(
            summary.get("transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts") or []
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count": int(
            summary.get("transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count") or 0
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix": list(
            summary.get("transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix") or []
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count": int(
            summary.get("transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count") or 0
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count": int(
            summary.get("transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count") or 0
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_failed_check_ids": list(
            summary.get("transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_failed_check_ids")
            or []
        ),
        "transporter_p0_evidence_acquisition_next_slot_id": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_id", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_operator_review_artifact", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready": bool(
            summary.get("transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready") is True
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_source_modality", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe": bool(
            summary.get("transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe") is True
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed": bool(
            summary.get(
                "transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed"
            )
            is True
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_decision": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_source_modality_decision", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails": list(
            summary.get("transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails") or []
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade", ""
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_ready": bool(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_ready"
            )
            is True
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_status": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_status", ""
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_artifact": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_artifact", ""
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_decision": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_decision", ""
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_experimental_binding_row_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_experimental_binding_row_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_ready": bool(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_ready"
            )
            is True
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result",
            "",
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid",
            "",
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id",
            "",
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id",
            "",
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail",
            "",
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_replacement_reference_binding_kcal_mol_action": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_replacement_reference_binding_kcal_mol_action",
            "",
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_computational_binding_energy_row_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_computational_binding_energy_row_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol",
            "",
        ),
        "evidence_queue_next_operator_completion_aqp1_review_sidecar_ready": bool(
            summary.get("evidence_queue_next_operator_completion_aqp1_review_sidecar_ready") is True
        ),
        "evidence_queue_next_operator_completion_aqp1_review_candidate_name": summary.get(
            "evidence_queue_next_operator_completion_aqp1_review_candidate_name", ""
        ),
        "evidence_queue_next_operator_completion_aqp1_review_source_anchor": summary.get(
            "evidence_queue_next_operator_completion_aqp1_review_source_anchor", ""
        ),
        "evidence_queue_next_operator_completion_aqp1_review_target_uniprot": summary.get(
            "evidence_queue_next_operator_completion_aqp1_review_target_uniprot", ""
        ),
        "evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": summary.get(
            "evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol",
            "",
        ),
        "evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed": summary.get(
            "evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed",
            "",
        ),
        "evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": summary.get(
            "evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank",
            "",
        ),
        "evidence_queue_pxr_exact_review_sidecar_row_count": int(
            summary.get("evidence_queue_pxr_exact_review_sidecar_row_count") or 0
        ),
        "evidence_queue_next_pxr_exact_review_sidecar_ready": bool(
            summary.get("evidence_queue_next_pxr_exact_review_sidecar_ready") is True
        ),
        "evidence_queue_next_pxr_exact_review_row_id": summary.get(
            "evidence_queue_next_pxr_exact_review_row_id", ""
        ),
        "evidence_queue_next_pxr_exact_review_candidate_name": summary.get(
            "evidence_queue_next_pxr_exact_review_candidate_name", ""
        ),
        "evidence_queue_next_pxr_exact_review_required_evidence_mode": summary.get(
            "evidence_queue_next_pxr_exact_review_required_evidence_mode", ""
        ),
        "evidence_queue_next_pxr_exact_review_target_match_confirmed": summary.get(
            "evidence_queue_next_pxr_exact_review_target_match_confirmed", ""
        ),
        "evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol": summary.get(
            "evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol", ""
        ),
        "evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi": summary.get(
            "evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi", ""
        ),
        "evidence_queue_next_pxr_exact_review_authoritative_apply_allowed": bool(
            summary.get("evidence_queue_next_pxr_exact_review_authoritative_apply_allowed") is True
        ),
        "evidence_queue_next_pxr_exact_review_scope_promotion_allowed": bool(
            summary.get("evidence_queue_next_pxr_exact_review_scope_promotion_allowed") is True
        ),
        "transporter_target_ready_for_promotion_count": int(
            summary.get("transporter_target_ready_for_promotion_count") or 0
        ),
        "transporter_target_blocked_for_promotion_count": int(
            summary.get("transporter_target_blocked_for_promotion_count") or 0
        ),
        "transporter_target_ready_for_promotion_ids": list(
            summary.get("transporter_target_ready_for_promotion_ids") or []
        ),
        "transporter_target_blocked_for_promotion_ids": list(
            summary.get("transporter_target_blocked_for_promotion_ids") or []
        ),
        "transporter_primary_blocker_target_id": summary.get("transporter_primary_blocker_target_id", ""),
        "transporter_primary_blocker_packet_step": summary.get("transporter_primary_blocker_packet_step", ""),
        "transporter_primary_blocker_candidate_name": summary.get(
            "transporter_primary_blocker_candidate_name", ""
        ),
        "allowed_claim_scopes": list(summary.get("allowed_claim_scopes") or []),
        "blocked_claim_scopes": list(summary.get("blocked_claim_scopes") or []),
        "blocked_claim_scope_count": int(summary.get("blocked_claim_scope_count") or 0),
        "general_platform_claim_allowed": bool(summary.get("general_platform_claim_allowed") is True),
        "general_platform_claim_blocked": bool(summary.get("general_platform_claim_blocked") is True),
        "general_protein_ligand_platform_ready": bool(
            summary.get("general_protein_ligand_platform_ready") is True
        ),
        "scope_claim_boundary_detail": summary.get("scope_claim_boundary_detail", ""),
        "pxr_exact_review_intake_ready": bool(summary.get("pxr_exact_review_intake_ready") is True),
        "pxr_exact_review_template_row_count": int(summary.get("pxr_exact_review_template_row_count") or 0),
        "pxr_exact_review_next_review_completion_packet_ready": bool(
            summary.get("pxr_exact_review_next_review_completion_packet_ready") is True
        ),
        "pxr_exact_review_next_review_completion_packet": dict(
            summary.get("pxr_exact_review_next_review_completion_packet") or {}
        ),
        "pxr_exact_review_next_review_return_bundle_required_artifacts": list(
            summary.get("pxr_exact_review_next_review_return_bundle_required_artifacts") or []
        ),
        "pxr_exact_review_next_review_return_bundle_required_artifact_count": int(
            summary.get("pxr_exact_review_next_review_return_bundle_required_artifact_count") or 0
        ),
        "pxr_exact_review_next_review_return_bundle_completion_matrix": list(
            summary.get("pxr_exact_review_next_review_return_bundle_completion_matrix") or []
        ),
        "pxr_exact_review_next_review_return_bundle_completion_matrix_count": int(
            summary.get("pxr_exact_review_next_review_return_bundle_completion_matrix_count") or 0
        ),
        "pxr_exact_review_next_review_return_bundle_blocker_count": int(
            summary.get("pxr_exact_review_next_review_return_bundle_blocker_count") or 0
        ),
        "pxr_exact_review_next_review_return_bundle_next_artifact_id": summary.get(
            "pxr_exact_review_next_review_return_bundle_next_artifact_id", ""
        ),
        "pxr_exact_review_next_review_return_bundle_next_artifact_path": summary.get(
            "pxr_exact_review_next_review_return_bundle_next_artifact_path", ""
        ),
        "pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids": list(
            summary.get("pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids") or []
        ),
        "pxr_exact_review_next_review_row_id": summary.get("pxr_exact_review_next_review_row_id", ""),
        "pxr_exact_review_next_review_candidate_name": summary.get(
            "pxr_exact_review_next_review_candidate_name", ""
        ),
        "pxr_exact_review_next_review_operator_review_artifact": summary.get(
            "pxr_exact_review_next_review_operator_review_artifact", ""
        ),
        "pxr_source_modality_triage_ready": bool(
            summary.get("pxr_source_modality_triage_ready") is True
        ),
        "pxr_source_modality_triage_status": summary.get("pxr_source_modality_triage_status", ""),
        "pxr_source_modality_triage_artifact": summary.get("pxr_source_modality_triage_artifact", ""),
        "pxr_source_modality_triage_decision": summary.get("pxr_source_modality_triage_decision", ""),
        "pxr_source_modality_public_evidence_recheck_ready": bool(
            summary.get("pxr_source_modality_public_evidence_recheck_ready") is True
        ),
        "pxr_source_modality_public_recheck_artifact": summary.get(
            "pxr_source_modality_public_recheck_artifact", ""
        ),
        "pxr_source_modality_public_recheck_candidate_count": int(
            summary.get("pxr_source_modality_public_recheck_candidate_count") or 0
        ),
        "pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count": int(
            summary.get("pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count") or 0
        ),
        "pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count": int(
            summary.get("pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count") or 0
        ),
        "pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count": int(
            summary.get("pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count") or 0
        ),
        "pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count": int(
            summary.get("pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count") or 0
        ),
        "pxr_source_modality_public_recheck_all_candidates_remain_blocked": bool(
            summary.get("pxr_source_modality_public_recheck_all_candidates_remain_blocked") is True
        ),
        "pxr_source_modality_public_recheck_first_blocked_candidate_name": summary.get(
            "pxr_source_modality_public_recheck_first_blocked_candidate_name", ""
        ),
        "pxr_source_modality_public_recheck_first_blocked_reason": summary.get(
            "pxr_source_modality_public_recheck_first_blocked_reason", ""
        ),
        "pxr_source_modality_direct_replacement_candidate_packet_ready": bool(
            summary.get("pxr_source_modality_direct_replacement_candidate_packet_ready") is True
        ),
        "pxr_source_modality_direct_replacement_artifact": summary.get(
            "pxr_source_modality_direct_replacement_artifact", ""
        ),
        "pxr_source_modality_direct_replacement_candidate_count": int(
            summary.get("pxr_source_modality_direct_replacement_candidate_count") or 0
        ),
        "pxr_source_modality_direct_replacement_selected_candidate_count": int(
            summary.get("pxr_source_modality_direct_replacement_selected_candidate_count") or 0
        ),
        "pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count": int(
            summary.get("pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count") or 0
        ),
        "pxr_source_modality_direct_replacement_first_ligand_id": summary.get(
            "pxr_source_modality_direct_replacement_first_ligand_id", ""
        ),
        "pxr_source_modality_direct_replacement_first_molecule_chembl_id": summary.get(
            "pxr_source_modality_direct_replacement_first_molecule_chembl_id", ""
        ),
        "pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol": summary.get(
            "pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol", ""
        ),
        "pxr_source_modality_direct_replacement_first_source": summary.get(
            "pxr_source_modality_direct_replacement_first_source", ""
        ),
        "pxr_source_modality_direct_replacement_apply_draft_ready": bool(
            summary.get("pxr_source_modality_direct_replacement_apply_draft_ready") is True
        ),
        "pxr_source_modality_direct_replacement_apply_draft_status": summary.get(
            "pxr_source_modality_direct_replacement_apply_draft_status", ""
        ),
        "pxr_source_modality_direct_replacement_apply_draft_artifact": summary.get(
            "pxr_source_modality_direct_replacement_apply_draft_artifact", ""
        ),
        "pxr_source_modality_direct_replacement_apply_draft_workbook_row_count": int(
            summary.get("pxr_source_modality_direct_replacement_apply_draft_workbook_row_count") or 0
        ),
        "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft": int(
            summary.get("pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft")
            or 0
        ),
        "pxr_source_modality_direct_replacement_apply_draft_overlay_row_count": int(
            summary.get("pxr_source_modality_direct_replacement_apply_draft_overlay_row_count") or 0
        ),
        "pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft": int(
            summary.get(
                "pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft"
            )
            or 0
        ),
        "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft": int(
            summary.get("pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft")
            or 0
        ),
        "pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id": summary.get(
            "pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id", ""
        ),
        "pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched": bool(
            summary.get("pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched")
            is True
        ),
        "pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count": int(
            summary.get("pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count") or 0
        ),
        "pxr_source_modality_direct_or_claim_safe_quantitative_ready_count": int(
            summary.get("pxr_source_modality_direct_or_claim_safe_quantitative_ready_count") or 0
        ),
        "pxr_source_modality_accepted_for_scope_promotion_count": int(
            summary.get("pxr_source_modality_accepted_for_scope_promotion_count") or 0
        ),
        "pxr_source_modality_next_review_row_id": summary.get(
            "pxr_source_modality_next_review_row_id", ""
        ),
        "pxr_source_modality_next_review_candidate_name": summary.get(
            "pxr_source_modality_next_review_candidate_name", ""
        ),
        "pxr_source_modality_next_review_source_modality": summary.get(
            "pxr_source_modality_next_review_source_modality", ""
        ),
        "pxr_source_modality_next_review_rejection_reason": summary.get(
            "pxr_source_modality_next_review_rejection_reason", ""
        ),
        "scope_acceptance_matrix_ready": bool(summary.get("scope_acceptance_matrix_ready") is True),
        "scope_acceptance_stage_count": int(summary.get("scope_acceptance_stage_count") or 0),
        "scope_acceptance_ready_stage_count": int(summary.get("scope_acceptance_ready_stage_count") or 0),
        "scope_acceptance_blocked_stage_count": int(summary.get("scope_acceptance_blocked_stage_count") or 0),
        "scope_acceptance_stage_ids": list(summary.get("scope_acceptance_stage_ids") or []),
        "scope_acceptance_ready_stage_ids": list(summary.get("scope_acceptance_ready_stage_ids") or []),
        "scope_acceptance_blocked_stage_ids": list(summary.get("scope_acceptance_blocked_stage_ids") or []),
        "scope_acceptance_next_stage_id": summary.get("scope_acceptance_next_stage_id", ""),
        "scope_acceptance_next_stage_artifact": summary.get("scope_acceptance_next_stage_artifact", ""),
        "scope_acceptance_next_stage_validation_command": summary.get(
            "scope_acceptance_next_stage_validation_command", ""
        ),
        "scope_acceptance_next_stage_release_effect": summary.get(
            "scope_acceptance_next_stage_release_effect", ""
        ),
        "scope_acceptance_next_stage_unlock_claim_scopes": list(
            summary.get("scope_acceptance_next_stage_unlock_claim_scopes") or []
        ),
        "scope_acceptance_next_stage_required_checks": list(
            summary.get("scope_acceptance_next_stage_required_checks") or []
        ),
        "scope_acceptance_next_stage_next_action": summary.get(
            "scope_acceptance_next_stage_next_action", ""
        ),
        "scope_acceptance_stage_evidence_matrix": scope_acceptance_stage_evidence_matrix,
        "scope_acceptance_stage_evidence_matrix_count": int(
            summary.get("scope_acceptance_stage_evidence_matrix_count") or 0
        ),
        "scope_acceptance_current_blocked_stage_evidence_matrix": (
            scope_acceptance_current_blocked_stage_evidence_matrix
        ),
        "scope_acceptance_current_blocked_stage_evidence_matrix_count": int(
            summary.get("scope_acceptance_current_blocked_stage_evidence_matrix_count") or 0
        ),
        "domain_rows": rows,
        "scope_acceptance_matrix": scope_acceptance_matrix,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened_by_endpoint": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/scope-claim-guard")
async def get_product_scope_claim_guard() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_scope_claim_guard",
            "artifact_path": str(PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT),
            "scope_breadth_ready": False,
            "closure_checklist_ready": False,
            "scope_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "allowed_scope_families": [],
            "allowed_scope_family_count": 0,
            "blocked_claim_scopes": ["product_scope_claim_guard_artifact_missing"],
            "blocked_claim_scope_count": 1,
            "claim_blocked_domains": [],
            "general_platform_claim_allowed": False,
            "ready_for_apply_count": 0,
            "authoritative_apply_allowed_count": 0,
            "checklist_row_count": 0,
            "manual_review_blocked_row_count": 0,
            "manual_review_subcheck_count": 0,
            "field_missing_row_count": 0,
            "first_scientific_blocker": "",
            "blocker_class_counts": {},
            "blocker_classes": [],
            "transporter_manual_review_subcheck_count": 0,
            "transporter_identity_scaffold_confirmation_required_count": 0,
            "transporter_direct_binding_or_kcal_confirmation_required_count": 0,
            "transporter_negative_quantitative_confirmation_required_count": 0,
            "transporter_direct_binding_missing_count": 0,
            "transporter_negative_quantitative_missing_count": 0,
            "transporter_candidate_ready_for_apply_count": 0,
            "pxr_reconciled_blocked_row_count": 0,
            "pxr_conflict_resolution_count": 0,
            "pxr_quantitative_missing_count": 0,
            "general_claim_blocker_count": 0,
            "general_claim_gate_blocker_count": 0,
            "claim_boundary_detail": "",
            "claim_boundary_matrix": [],
            "source_artifacts": [],
            "closure_items": [],
            "next_required_step": "Run python3 tools/build_product_scope_breadth_closure_checklist.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product scope-claim-guard endpoint only; the local scope closure checklist artifact is missing. "
                "It does not acquire evidence, widen claims, run docking, promote scope, or mutate external state."
            ),
        }
    return {
        "artifact_path": str(PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT),
        "status": summary.get("status")
        or (
            "product_scope_breadth_closure_checklist_ready"
            if summary.get("closure_checklist_ready") is True
            else "blocked_product_scope_breadth_closure_checklist"
        ),
        "scope_breadth_ready": bool(summary.get("scope_breadth_ready") is True),
        "closure_checklist_ready": bool(summary.get("closure_checklist_ready") is True),
        "scope_promotion_allowed": bool(summary.get("scope_promotion_allowed") is True),
        "authoritative_apply_allowed": bool(summary.get("authoritative_apply_allowed") is True),
        "allowed_scope_families": list(summary.get("allowed_scope_families") or []),
        "allowed_scope_family_count": int(summary.get("allowed_scope_family_count") or 0),
        "blocked_claim_scopes": list(summary.get("blocked_claim_scopes") or []),
        "blocked_claim_scope_count": int(summary.get("blocked_claim_scope_count") or 0),
        "claim_blocked_domains": list(summary.get("claim_blocked_domains") or []),
        "general_platform_claim_allowed": bool(summary.get("general_platform_claim_allowed") is True),
        "ready_for_apply_count": int(summary.get("ready_for_apply_count") or 0),
        "authoritative_apply_allowed_count": int(summary.get("authoritative_apply_allowed_count") or 0),
        "checklist_row_count": int(summary.get("checklist_row_count") or 0),
        "manual_review_blocked_row_count": int(summary.get("manual_review_blocked_row_count") or 0),
        "manual_review_subcheck_count": int(summary.get("manual_review_subcheck_count") or 0),
        "field_missing_row_count": int(summary.get("field_missing_row_count") or 0),
        "first_scientific_blocker": summary.get("first_scientific_blocker", ""),
        "blocker_class_counts": (
            summary.get("blocker_class_counts") if isinstance(summary.get("blocker_class_counts"), dict) else {}
        ),
        "blocker_classes": list(summary.get("blocker_classes") or []),
        "transporter_manual_review_subcheck_count": int(
            summary.get("transporter_manual_review_subcheck_count") or 0
        ),
        "transporter_identity_scaffold_confirmation_required_count": int(
            summary.get("transporter_identity_scaffold_confirmation_required_count") or 0
        ),
        "transporter_direct_binding_or_kcal_confirmation_required_count": int(
            summary.get("transporter_direct_binding_or_kcal_confirmation_required_count") or 0
        ),
        "transporter_negative_quantitative_confirmation_required_count": int(
            summary.get("transporter_negative_quantitative_confirmation_required_count") or 0
        ),
        "transporter_direct_binding_missing_count": int(
            summary.get("transporter_direct_binding_missing_count") or 0
        ),
        "transporter_negative_quantitative_missing_count": int(
            summary.get("transporter_negative_quantitative_missing_count") or 0
        ),
        "transporter_candidate_ready_for_apply_count": int(
            summary.get("transporter_candidate_ready_for_apply_count") or 0
        ),
        "pxr_reconciled_blocked_row_count": int(summary.get("pxr_reconciled_blocked_row_count") or 0),
        "pxr_conflict_resolution_count": int(summary.get("pxr_conflict_resolution_count") or 0),
        "pxr_quantitative_missing_count": int(summary.get("pxr_quantitative_missing_count") or 0),
        "general_claim_blocker_count": int(summary.get("general_claim_blocker_count") or 0),
        "general_claim_gate_blocker_count": int(summary.get("general_claim_gate_blocker_count") or 0),
        "claim_boundary_detail": summary.get("claim_boundary_detail", ""),
        "claim_boundary_matrix": list(summary.get("claim_boundary_matrix") or []),
        "source_artifacts": list(summary.get("source_artifacts") or []),
        "closure_items": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/scope-evidence-priority")
async def get_product_scope_evidence_priority() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_SCOPE_EVIDENCE_PRIORITY_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_scope_evidence_priority",
            "artifact_path": str(PRODUCT_SCOPE_EVIDENCE_PRIORITY_ARTIFACT),
            "priority_packet_ready": False,
            "scope_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "queue_item_count": 0,
            "source_queue_item_count": 0,
            "open_item_count": 0,
            "scientific_evidence_request_count": 0,
            "local_crosscheck_candidate_count": 0,
            "external_primary_exact_evidence_required_count": 0,
            "review_only_keep_blocked_count": 0,
            "claim_gate_prerequisite_count": 0,
            "operator_packet_binding_ready_count": 0,
            "operator_packet_binding_missing_count": 0,
            "all_operator_packet_bindings_ready": False,
            "top_item_id": "",
            "top_required_evidence_type": "",
            "top_review_template_artifact": "",
            "top_apply_gate_artifact": "",
            "receipt_status": "",
            "receipt_ready": False,
            "receipt_csv": "",
            "receipt_row_count": 0,
            "receipt_blocked_row_count": 0,
            "receipt_operator_review_surface_ready_count": 0,
            "receipt_operator_review_surface_blocked_count": 0,
            "receipt_manual_field_pending_count": 0,
            "receipt_evidence_artifact_pending_count": 0,
            "receipt_claim_ready_pending_count": 0,
            "receipt_reviewer_pending_count": 0,
            "receipt_reviewed_at_utc_pending_count": 0,
            "receipt_license_ok_pending_count": 0,
            "receipt_approval_token_pending_count": 0,
            "receipt_first_blocked_scope_blocker_id": "",
            "receipt_first_blocked_evidence_artifact": "",
            "receipt_first_blocked_expected_evidence_status": "",
            "receipt_first_blocked_observed_evidence_status": "",
            "receipt_first_blocked_missing_true_fields": [],
            "receipt_first_blocked_row_blockers": [],
            "receipt_most_common_row_blocker": "",
            "receipt_approval_token_required": "",
            "authoritative_apply_allowed_count": 0,
            "source_artifacts": [],
            "top_priority_items": [],
            "priority_items": [],
            "next_required_step": "Run python3 tools/build_product_scope_breadth_evidence_priority_packet.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product scope-evidence-priority endpoint only; the local priority artifact is missing. "
                "It does not acquire evidence, widen scope, run docking, promote claims, or mutate external state."
            ),
        }
    sorted_rows = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=lambda row: int(row.get("priority") or 999999),
    )
    return {
        "status": summary.get("status") or "product_scope_breadth_evidence_priority_packet_ready",
        "artifact_path": str(PRODUCT_SCOPE_EVIDENCE_PRIORITY_ARTIFACT),
        "priority_packet_ready": bool(summary.get("priority_packet_ready") is True),
        "scope_promotion_allowed": bool(summary.get("scope_promotion_allowed") is True),
        "authoritative_apply_allowed": bool(summary.get("authoritative_apply_allowed") is True),
        "queue_item_count": int(summary.get("queue_item_count") or 0),
        "source_queue_item_count": int(summary.get("source_queue_item_count") or 0),
        "open_item_count": int(summary.get("open_item_count") or 0),
        "scientific_evidence_request_count": int(summary.get("scientific_evidence_request_count") or 0),
        "local_crosscheck_candidate_count": int(summary.get("local_crosscheck_candidate_count") or 0),
        "external_primary_exact_evidence_required_count": int(
            summary.get("external_primary_exact_evidence_required_count") or 0
        ),
        "review_only_keep_blocked_count": int(summary.get("review_only_keep_blocked_count") or 0),
        "claim_gate_prerequisite_count": int(summary.get("claim_gate_prerequisite_count") or 0),
        "operator_packet_binding_ready_count": int(summary.get("operator_packet_binding_ready_count") or 0),
        "operator_packet_binding_missing_count": int(summary.get("operator_packet_binding_missing_count") or 0),
        "all_operator_packet_bindings_ready": bool(summary.get("all_operator_packet_bindings_ready") is True),
        "top_item_id": summary.get("top_item_id", ""),
        "top_required_evidence_type": summary.get("top_required_evidence_type", ""),
        "top_review_template_artifact": summary.get("top_review_template_artifact", ""),
        "top_apply_gate_artifact": summary.get("top_apply_gate_artifact", ""),
        "receipt_status": summary.get("receipt_status", ""),
        "receipt_ready": bool(summary.get("receipt_ready") is True),
        "receipt_csv": summary.get("receipt_csv", ""),
        "receipt_row_count": int(summary.get("receipt_row_count") or 0),
        "receipt_blocked_row_count": int(summary.get("receipt_blocked_row_count") or 0),
        "receipt_operator_review_surface_ready_count": int(
            summary.get("receipt_operator_review_surface_ready_count") or 0
        ),
        "receipt_operator_review_surface_blocked_count": int(
            summary.get("receipt_operator_review_surface_blocked_count") or 0
        ),
        "receipt_manual_field_pending_count": int(
            summary.get("receipt_manual_field_pending_count") or 0
        ),
        "receipt_evidence_artifact_pending_count": int(
            summary.get("receipt_evidence_artifact_pending_count") or 0
        ),
        "receipt_claim_ready_pending_count": int(
            summary.get("receipt_claim_ready_pending_count") or 0
        ),
        "receipt_reviewer_pending_count": int(
            summary.get("receipt_reviewer_pending_count") or 0
        ),
        "receipt_reviewed_at_utc_pending_count": int(
            summary.get("receipt_reviewed_at_utc_pending_count") or 0
        ),
        "receipt_license_ok_pending_count": int(
            summary.get("receipt_license_ok_pending_count") or 0
        ),
        "receipt_approval_token_pending_count": int(
            summary.get("receipt_approval_token_pending_count") or 0
        ),
        "receipt_first_blocked_scope_blocker_id": summary.get(
            "receipt_first_blocked_scope_blocker_id", ""
        ),
        "receipt_first_blocked_evidence_artifact": summary.get(
            "receipt_first_blocked_evidence_artifact", ""
        ),
        "receipt_first_blocked_expected_evidence_status": summary.get(
            "receipt_first_blocked_expected_evidence_status", ""
        ),
        "receipt_first_blocked_observed_evidence_status": summary.get(
            "receipt_first_blocked_observed_evidence_status", ""
        ),
        "receipt_first_blocked_missing_true_fields": _text_list(
            summary.get("receipt_first_blocked_missing_true_fields") or []
        ),
        "receipt_first_blocked_row_blockers": _text_list(
            summary.get("receipt_first_blocked_row_blockers") or []
        ),
        "receipt_most_common_row_blocker": summary.get("receipt_most_common_row_blocker", ""),
        "receipt_approval_token_required": summary.get("receipt_approval_token_required", ""),
        "authoritative_apply_allowed_count": int(summary.get("authoritative_apply_allowed_count") or 0),
        "source_artifacts": list(summary.get("source_artifacts") or []),
        "top_priority_items": sorted_rows[:5],
        "priority_items": sorted_rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/scope-evidence-intake-readiness")
async def get_product_scope_evidence_intake_readiness() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_SCOPE_EVIDENCE_INTAKE_READINESS_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_scope_evidence_intake_readiness",
            "artifact_path": str(PRODUCT_SCOPE_EVIDENCE_INTAKE_READINESS_ARTIFACT),
            "intake_readiness_ready": False,
            "scope_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "row_count": 0,
            "local_crosscheck_triage_item_count": 0,
            "local_crosscheck_intake_ready_count": 0,
            "external_exact_evidence_required_count": 0,
            "guardrail_item_count": 0,
            "operator_packet_binding_ready_count": 0,
            "operator_packet_binding_missing_count": 0,
            "all_operator_packet_bindings_ready": False,
            "top_unbound_item_id": "",
            "top_unbound_required_evidence_type": "",
            "next_operator_completion_item_id": "",
            "next_operator_completion_domain": "",
            "next_operator_completion_candidate_or_check": "",
            "next_operator_completion_intake_mode": "",
            "next_operator_completion_required_evidence_type": "",
            "next_operator_completion_required_intake_columns": [],
            "next_operator_completion_required_intake_column_count": 0,
            "next_operator_completion_review_template_artifact": "",
            "next_operator_completion_apply_gate_artifact": "",
            "next_operator_completion_regeneration_commands": "",
            "next_operator_completion_operator_packet_binding_key": "",
            "next_operator_completion_operator_packet_binding_ready": False,
            "next_operator_completion_transporter_claim_safe_blocker": "",
            "next_operator_completion_transporter_operator_next_verdict": "",
            "next_operator_completion_transporter_best_evidence_source_file": "",
            "next_operator_completion_transporter_best_evidence_activity_type": "",
            "next_operator_completion_transporter_best_evidence_value": "",
            "next_operator_completion_transporter_best_evidence_units": "",
            "next_operator_completion_transporter_best_evidence_document_id": "",
            "transporter_triage_packet_ready": False,
            "transporter_operator_review_evidence_matrix_ready": False,
            "transporter_claim_safe_local_evidence_ready_count": 0,
            "transporter_claim_safe_local_evidence_blocked_count": 0,
            "transporter_direct_binding_claim_blocked_count": 0,
            "transporter_negative_value_claim_blocked_count": 0,
            "transporter_top_claim_safe_blocker": "",
            "transporter_top_operator_next_verdict": "",
            "transporter_candidate_row_count": 0,
            "transporter_candidate_ready_for_manual_review_count": 0,
            "transporter_candidate_ready_for_apply_count": 0,
            "transporter_candidate_assignment_required_count": 0,
            "transporter_functional_quantitative_only_direct_gap_open_count": 0,
            "transporter_review_only_direct_binding_gap_count": 0,
            "transporter_manual_review_intake_ready": False,
            "transporter_manual_review_template_row_count": 0,
            "transporter_manual_review_direct_binding_evidence_required_count": 0,
            "transporter_manual_review_negative_quantitative_value_required_count": 0,
            "transporter_manual_review_decision_placeholder_count": 0,
            "first_review_row_id": "",
            "first_review_item_id": "",
            "first_review_target_id": "",
            "first_review_candidate_ligand_id": "",
            "first_review_replacement_source": "",
            "first_review_replacement_reference_binding_kcal_mol": "",
            "first_review_direct_binding_evidence_required": False,
            "first_review_direct_binding_source_url_or_doi": "",
            "first_review_negative_quantitative_value_required": False,
            "first_review_negative_reference_binding_kcal_mol": "",
            "first_review_review_decision": "",
            "first_review_authoritative_apply_requested": "",
            "first_review_manual_review_blockers": "",
            "first_review_review_requirements": "",
            "first_review_p0_slot_overlay_required_missing_fields": "",
            "first_review_p0_slot_overlay_claim_safe_step_ready": False,
            "first_review_p0_slot_overlay_authoritative_apply_allowed": False,
            "first_review_p0_slot_overlay_scope_promotion_allowed": False,
            "scope_operator_transfer_manifest_ready": False,
            "scope_operator_transfer_outbound_artifact_count": 0,
            "scope_operator_transfer_outbound_artifacts": [],
            "scope_operator_transfer_inbound_artifact_count": 0,
            "scope_operator_transfer_inbound_artifacts": [],
            "scope_operator_transfer_first_return_artifact": "",
            "scope_operator_transfer_acceptance_artifact": "",
            "scope_operator_transfer_acceptance_ready_key": "",
            "scope_operator_transfer_next_acceptance_stage": "",
            "scope_operator_transfer_post_return_validation_command": "",
            "source_artifacts": [],
            "intake_items": [],
            "next_required_step": "Run python3 tools/build_product_scope_breadth_evidence_intake_readiness.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product scope evidence intake-readiness endpoint only; local artifact is missing. It does not accept "
                "evidence, authoritatively apply rows, widen API scope, run docking, promote claims, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status") or "product_scope_breadth_evidence_intake_readiness_ready",
        "artifact_path": str(PRODUCT_SCOPE_EVIDENCE_INTAKE_READINESS_ARTIFACT),
        "intake_readiness_ready": bool(summary.get("intake_readiness_ready") is True),
        "scope_promotion_allowed": bool(summary.get("scope_promotion_allowed") is True),
        "authoritative_apply_allowed": bool(summary.get("authoritative_apply_allowed") is True),
        "row_count": int(summary.get("row_count") or 0),
        "local_crosscheck_triage_item_count": int(summary.get("local_crosscheck_triage_item_count") or 0),
        "local_crosscheck_intake_ready_count": int(summary.get("local_crosscheck_intake_ready_count") or 0),
        "external_exact_evidence_required_count": int(summary.get("external_exact_evidence_required_count") or 0),
        "guardrail_item_count": int(summary.get("guardrail_item_count") or 0),
        "operator_packet_binding_ready_count": int(summary.get("operator_packet_binding_ready_count") or 0),
        "operator_packet_binding_missing_count": int(summary.get("operator_packet_binding_missing_count") or 0),
        "all_operator_packet_bindings_ready": bool(summary.get("all_operator_packet_bindings_ready") is True),
        "top_unbound_item_id": summary.get("top_unbound_item_id", ""),
        "top_unbound_required_evidence_type": summary.get("top_unbound_required_evidence_type", ""),
        "next_operator_completion_item_id": summary.get("next_operator_completion_item_id", ""),
        "next_operator_completion_domain": summary.get("next_operator_completion_domain", ""),
        "next_operator_completion_candidate_or_check": summary.get(
            "next_operator_completion_candidate_or_check", ""
        ),
        "next_operator_completion_intake_mode": summary.get("next_operator_completion_intake_mode", ""),
        "next_operator_completion_required_evidence_type": summary.get(
            "next_operator_completion_required_evidence_type", ""
        ),
        "next_operator_completion_required_intake_columns": list(
            summary.get("next_operator_completion_required_intake_columns") or []
        ),
        "next_operator_completion_required_intake_column_count": int(
            summary.get("next_operator_completion_required_intake_column_count") or 0
        ),
        "next_operator_completion_review_template_artifact": summary.get(
            "next_operator_completion_review_template_artifact", ""
        ),
        "next_operator_completion_apply_gate_artifact": summary.get(
            "next_operator_completion_apply_gate_artifact", ""
        ),
        "next_operator_completion_regeneration_commands": summary.get(
            "next_operator_completion_regeneration_commands", ""
        ),
        "next_operator_completion_operator_packet_binding_key": summary.get(
            "next_operator_completion_operator_packet_binding_key", ""
        ),
        "next_operator_completion_operator_packet_binding_ready": bool(
            summary.get("next_operator_completion_operator_packet_binding_ready") is True
        ),
        "next_operator_completion_transporter_claim_safe_blocker": summary.get(
            "next_operator_completion_transporter_claim_safe_blocker", ""
        ),
        "next_operator_completion_transporter_operator_next_verdict": summary.get(
            "next_operator_completion_transporter_operator_next_verdict", ""
        ),
        "next_operator_completion_transporter_best_evidence_source_file": summary.get(
            "next_operator_completion_transporter_best_evidence_source_file", ""
        ),
        "next_operator_completion_transporter_best_evidence_activity_type": summary.get(
            "next_operator_completion_transporter_best_evidence_activity_type", ""
        ),
        "next_operator_completion_transporter_best_evidence_value": summary.get(
            "next_operator_completion_transporter_best_evidence_value", ""
        ),
        "next_operator_completion_transporter_best_evidence_units": summary.get(
            "next_operator_completion_transporter_best_evidence_units", ""
        ),
        "next_operator_completion_transporter_best_evidence_document_id": summary.get(
            "next_operator_completion_transporter_best_evidence_document_id", ""
        ),
        "transporter_triage_packet_ready": bool(summary.get("transporter_triage_packet_ready") is True),
        "transporter_operator_review_evidence_matrix_ready": bool(
            summary.get("transporter_operator_review_evidence_matrix_ready") is True
        ),
        "transporter_claim_safe_local_evidence_ready_count": int(
            summary.get("transporter_claim_safe_local_evidence_ready_count") or 0
        ),
        "transporter_claim_safe_local_evidence_blocked_count": int(
            summary.get("transporter_claim_safe_local_evidence_blocked_count") or 0
        ),
        "transporter_direct_binding_claim_blocked_count": int(
            summary.get("transporter_direct_binding_claim_blocked_count") or 0
        ),
        "transporter_negative_value_claim_blocked_count": int(
            summary.get("transporter_negative_value_claim_blocked_count") or 0
        ),
        "transporter_top_claim_safe_blocker": summary.get("transporter_top_claim_safe_blocker", ""),
        "transporter_top_operator_next_verdict": summary.get("transporter_top_operator_next_verdict", ""),
        "transporter_candidate_row_count": int(summary.get("transporter_candidate_row_count") or 0),
        "transporter_candidate_ready_for_manual_review_count": int(
            summary.get("transporter_candidate_ready_for_manual_review_count") or 0
        ),
        "transporter_candidate_ready_for_apply_count": int(
            summary.get("transporter_candidate_ready_for_apply_count") or 0
        ),
        "transporter_candidate_assignment_required_count": int(
            summary.get("transporter_candidate_assignment_required_count") or 0
        ),
        "transporter_functional_quantitative_only_direct_gap_open_count": int(
            summary.get("transporter_functional_quantitative_only_direct_gap_open_count") or 0
        ),
        "transporter_review_only_direct_binding_gap_count": int(
            summary.get("transporter_review_only_direct_binding_gap_count") or 0
        ),
        "transporter_manual_review_intake_ready": bool(
            summary.get("transporter_manual_review_intake_ready") is True
        ),
        "transporter_manual_review_template_row_count": int(
            summary.get("transporter_manual_review_template_row_count") or 0
        ),
        "transporter_manual_review_direct_binding_evidence_required_count": int(
            summary.get("transporter_manual_review_direct_binding_evidence_required_count") or 0
        ),
        "transporter_manual_review_negative_quantitative_value_required_count": int(
            summary.get("transporter_manual_review_negative_quantitative_value_required_count") or 0
        ),
        "transporter_manual_review_decision_placeholder_count": int(
            summary.get("transporter_manual_review_decision_placeholder_count") or 0
        ),
        "first_review_row_id": summary.get("first_review_row_id", ""),
        "first_review_item_id": summary.get("first_review_item_id", ""),
        "first_review_target_id": summary.get("first_review_target_id", ""),
        "first_review_candidate_ligand_id": summary.get("first_review_candidate_ligand_id", ""),
        "first_review_replacement_source": summary.get("first_review_replacement_source", ""),
        "first_review_replacement_reference_binding_kcal_mol": summary.get(
            "first_review_replacement_reference_binding_kcal_mol", ""
        ),
        "first_review_direct_binding_evidence_required": bool(
            summary.get("first_review_direct_binding_evidence_required") is True
        ),
        "first_review_direct_binding_source_url_or_doi": summary.get(
            "first_review_direct_binding_source_url_or_doi", ""
        ),
        "first_review_negative_quantitative_value_required": bool(
            summary.get("first_review_negative_quantitative_value_required") is True
        ),
        "first_review_negative_reference_binding_kcal_mol": summary.get(
            "first_review_negative_reference_binding_kcal_mol", ""
        ),
        "first_review_review_decision": summary.get("first_review_review_decision", ""),
        "first_review_authoritative_apply_requested": summary.get(
            "first_review_authoritative_apply_requested", ""
        ),
        "first_review_manual_review_blockers": summary.get("first_review_manual_review_blockers", ""),
        "first_review_review_requirements": summary.get("first_review_review_requirements", ""),
        "first_review_p0_slot_overlay_required_missing_fields": summary.get(
            "first_review_p0_slot_overlay_required_missing_fields", ""
        ),
        "first_review_p0_slot_overlay_claim_safe_step_ready": bool(
            summary.get("first_review_p0_slot_overlay_claim_safe_step_ready") is True
        ),
        "first_review_p0_slot_overlay_authoritative_apply_allowed": bool(
            summary.get("first_review_p0_slot_overlay_authoritative_apply_allowed") is True
        ),
        "first_review_p0_slot_overlay_scope_promotion_allowed": bool(
            summary.get("first_review_p0_slot_overlay_scope_promotion_allowed") is True
        ),
        "scope_operator_transfer_manifest_ready": bool(
            summary.get("scope_operator_transfer_manifest_ready") is True
        ),
        "scope_operator_transfer_outbound_artifact_count": int(
            summary.get("scope_operator_transfer_outbound_artifact_count") or 0
        ),
        "scope_operator_transfer_outbound_artifacts": list(
            summary.get("scope_operator_transfer_outbound_artifacts") or []
        ),
        "scope_operator_transfer_inbound_artifact_count": int(
            summary.get("scope_operator_transfer_inbound_artifact_count") or 0
        ),
        "scope_operator_transfer_inbound_artifacts": list(
            summary.get("scope_operator_transfer_inbound_artifacts") or []
        ),
        "scope_operator_transfer_first_return_artifact": summary.get(
            "scope_operator_transfer_first_return_artifact", ""
        ),
        "scope_operator_transfer_acceptance_artifact": summary.get(
            "scope_operator_transfer_acceptance_artifact", ""
        ),
        "scope_operator_transfer_acceptance_ready_key": summary.get(
            "scope_operator_transfer_acceptance_ready_key", ""
        ),
        "scope_operator_transfer_next_acceptance_stage": summary.get(
            "scope_operator_transfer_next_acceptance_stage", ""
        ),
        "scope_operator_transfer_post_return_validation_command": summary.get(
            "scope_operator_transfer_post_return_validation_command", ""
        ),
        "transporter_manual_review_p0_slot_overlay_row_count": int(
            summary.get("transporter_manual_review_p0_slot_overlay_row_count") or 0
        ),
        "transporter_manual_review_p0_slot_overlay_candidate_changed_count": int(
            summary.get("transporter_manual_review_p0_slot_overlay_candidate_changed_count") or 0
        ),
        "transporter_manual_review_p0_slot_overlay_first_item_id": summary.get(
            "transporter_manual_review_p0_slot_overlay_first_item_id",
            "",
        ),
        "transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id": summary.get(
            "transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id",
            "",
        ),
        "transporter_manual_review_p0_slot_overlay_first_source": summary.get(
            "transporter_manual_review_p0_slot_overlay_first_source",
            "",
        ),
        "source_artifacts": list(summary.get("source_artifacts") or []),
        "intake_items": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/transporter-manual-review-intake")
async def get_product_transporter_manual_review_intake() -> dict[str, Any]:
    packet = _read_json_object(TRANSPORTER_MANUAL_REVIEW_INTAKE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_transporter_manual_review_intake_template",
            "artifact_path": str(TRANSPORTER_MANUAL_REVIEW_INTAKE_ARTIFACT),
            "manual_review_intake_ready": False,
            "scope_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "manual_review_template_row_count": 0,
            "expected_manual_review_row_count": 0,
            "manual_review_row_count_matches_workbook": False,
            "manual_confirmation_required_count": 0,
            "direct_binding_evidence_required_count": 0,
            "negative_quantitative_value_required_count": 0,
            "review_decision_placeholder_count": 0,
            "authoritative_apply_requested_placeholder_count": 0,
            "p0_slot_overlay_row_count": 0,
            "p0_slot_overlay_candidate_changed_count": 0,
            "p0_slot_overlay_first_item_id": "",
            "p0_slot_overlay_first_candidate_ligand_id": "",
            "p0_slot_overlay_first_source": "",
            "p0_slot_overlay_claim_safe_step_ready_count": 0,
            "first_review_row_id": "",
            "first_review_item_id": "",
            "first_review_target_id": "",
            "first_review_candidate_ligand_id": "",
            "first_review_replacement_source": "",
            "first_review_replacement_reference_binding_kcal_mol": "",
            "first_review_direct_binding_evidence_required": False,
            "first_review_direct_binding_source_url_or_doi": "",
            "first_review_negative_quantitative_value_required": False,
            "first_review_negative_reference_binding_kcal_mol": "",
            "first_review_review_decision": "",
            "first_review_authoritative_apply_requested": "",
            "first_review_manual_review_blockers": "",
            "first_review_review_requirements": "",
            "first_review_p0_slot_overlay_required_missing_fields": "",
            "first_review_p0_slot_overlay_claim_safe_step_ready": False,
            "first_review_p0_slot_overlay_authoritative_apply_allowed": False,
            "first_review_p0_slot_overlay_scope_promotion_allowed": False,
            "candidate_workbook_ready": False,
            "candidate_workbook_row_count": 0,
            "unique_review_row_ids_ready": False,
            "review_rows": [],
            "next_required_step": "Run python3 tools/build_transporter_manual_review_intake_template.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Transporter manual review endpoint only; local template artifact is missing. It does not write config "
                "CSVs, authoritatively apply rows, run docking, widen product scope, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status") or "transporter_manual_review_intake_template_ready",
        "artifact_path": str(TRANSPORTER_MANUAL_REVIEW_INTAKE_ARTIFACT),
        "manual_review_intake_ready": bool(summary.get("manual_review_intake_ready") is True),
        "scope_promotion_allowed": bool(summary.get("scope_promotion_allowed") is True),
        "authoritative_apply_allowed": bool(summary.get("authoritative_apply_allowed") is True),
        "manual_review_template_row_count": int(summary.get("manual_review_template_row_count") or 0),
        "expected_manual_review_row_count": int(summary.get("expected_manual_review_row_count") or 0),
        "manual_review_row_count_matches_workbook": bool(
            summary.get("manual_review_row_count_matches_workbook") is True
        ),
        "manual_confirmation_required_count": int(summary.get("manual_confirmation_required_count") or 0),
        "direct_binding_evidence_required_count": int(summary.get("direct_binding_evidence_required_count") or 0),
        "negative_quantitative_value_required_count": int(
            summary.get("negative_quantitative_value_required_count") or 0
        ),
        "review_decision_placeholder_count": int(summary.get("review_decision_placeholder_count") or 0),
        "authoritative_apply_requested_placeholder_count": int(
            summary.get("authoritative_apply_requested_placeholder_count") or 0
        ),
        "p0_slot_overlay_row_count": int(summary.get("p0_slot_overlay_row_count") or 0),
        "p0_slot_overlay_candidate_changed_count": int(
            summary.get("p0_slot_overlay_candidate_changed_count") or 0
        ),
        "p0_slot_overlay_first_item_id": summary.get("p0_slot_overlay_first_item_id", ""),
        "p0_slot_overlay_first_candidate_ligand_id": summary.get(
            "p0_slot_overlay_first_candidate_ligand_id",
            "",
        ),
        "p0_slot_overlay_first_source": summary.get("p0_slot_overlay_first_source", ""),
        "p0_slot_overlay_claim_safe_step_ready_count": int(
            summary.get("p0_slot_overlay_claim_safe_step_ready_count") or 0
        ),
        "first_review_row_id": summary.get("first_review_row_id", ""),
        "first_review_item_id": summary.get("first_review_item_id", ""),
        "first_review_target_id": summary.get("first_review_target_id", ""),
        "first_review_candidate_ligand_id": summary.get("first_review_candidate_ligand_id", ""),
        "first_review_replacement_source": summary.get("first_review_replacement_source", ""),
        "first_review_replacement_reference_binding_kcal_mol": summary.get(
            "first_review_replacement_reference_binding_kcal_mol", ""
        ),
        "first_review_direct_binding_evidence_required": bool(
            summary.get("first_review_direct_binding_evidence_required") is True
        ),
        "first_review_direct_binding_source_url_or_doi": summary.get(
            "first_review_direct_binding_source_url_or_doi", ""
        ),
        "first_review_negative_quantitative_value_required": bool(
            summary.get("first_review_negative_quantitative_value_required") is True
        ),
        "first_review_negative_reference_binding_kcal_mol": summary.get(
            "first_review_negative_reference_binding_kcal_mol", ""
        ),
        "first_review_review_decision": summary.get("first_review_review_decision", ""),
        "first_review_authoritative_apply_requested": summary.get(
            "first_review_authoritative_apply_requested", ""
        ),
        "first_review_manual_review_blockers": summary.get("first_review_manual_review_blockers", ""),
        "first_review_review_requirements": summary.get("first_review_review_requirements", ""),
        "first_review_p0_slot_overlay_required_missing_fields": summary.get(
            "first_review_p0_slot_overlay_required_missing_fields", ""
        ),
        "first_review_p0_slot_overlay_claim_safe_step_ready": bool(
            summary.get("first_review_p0_slot_overlay_claim_safe_step_ready") is True
        ),
        "first_review_p0_slot_overlay_authoritative_apply_allowed": bool(
            summary.get("first_review_p0_slot_overlay_authoritative_apply_allowed") is True
        ),
        "first_review_p0_slot_overlay_scope_promotion_allowed": bool(
            summary.get("first_review_p0_slot_overlay_scope_promotion_allowed") is True
        ),
        "candidate_workbook_ready": bool(summary.get("candidate_workbook_ready") is True),
        "candidate_workbook_row_count": int(summary.get("candidate_workbook_row_count") or 0),
        "unique_review_row_ids_ready": bool(summary.get("unique_review_row_ids_ready") is True),
        "review_rows": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/pxr-exact-review-intake")
async def get_product_pxr_exact_review_intake() -> dict[str, Any]:
    packet = _read_json_object(PXR_EXACT_REVIEW_INTAKE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_pxr_exact_evidence_review_intake_template",
            "artifact_path": str(PXR_EXACT_REVIEW_INTAKE_ARTIFACT),
            "pxr_exact_review_intake_ready": False,
            "scope_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "review_template_row_count": 0,
            "expected_blocked_row_count": 0,
            "review_row_count_matches_reconciliation": False,
            "binder_review_row_count": 0,
            "non_binder_review_row_count": 0,
            "conflict_resolution_required_count": 0,
            "kcal_placeholder_count": 0,
            "source_placeholder_count": 0,
            "target_match_placeholder_count": 0,
            "review_decision_placeholder_count": 0,
            "next_review_completion_packet_ready": False,
            "next_review_completion_packet": {},
            "next_review_return_bundle_required_artifacts": [],
            "next_review_return_bundle_required_artifact_count": 0,
            "next_review_return_bundle_completion_matrix": [],
            "next_review_return_bundle_completion_matrix_count": 0,
            "next_review_return_bundle_blocker_count": 0,
            "next_review_return_bundle_next_artifact_id": "",
            "next_review_return_bundle_next_artifact_path": "",
            "next_review_return_bundle_next_artifact_failed_check_ids": [],
            "next_review_row_id": "",
            "next_review_candidate_name": "",
            "next_review_packet_step": "",
            "next_review_required_evidence_mode": "",
            "next_review_operator_review_artifact": "",
            "reconciliation_packet_ready": False,
            "reconciliation_artifact": "",
            "unique_review_row_ids_ready": False,
            "review_rows": [],
            "next_required_step": "Run python3 tools/build_pxr_exact_evidence_review_intake_template.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "PXR exact review endpoint only; local template artifact is missing. It does not authoritatively apply "
                "rows, promote PXR scope, run docking, upload, submit, email, delete, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status") or "pxr_exact_evidence_review_intake_template_ready",
        "artifact_path": str(PXR_EXACT_REVIEW_INTAKE_ARTIFACT),
        "pxr_exact_review_intake_ready": bool(summary.get("pxr_exact_review_intake_ready") is True),
        "scope_promotion_allowed": bool(summary.get("scope_promotion_allowed") is True),
        "authoritative_apply_allowed": bool(summary.get("authoritative_apply_allowed") is True),
        "review_template_row_count": int(summary.get("review_template_row_count") or 0),
        "expected_blocked_row_count": int(summary.get("expected_blocked_row_count") or 0),
        "review_row_count_matches_reconciliation": bool(
            summary.get("review_row_count_matches_reconciliation") is True
        ),
        "binder_review_row_count": int(summary.get("binder_review_row_count") or 0),
        "non_binder_review_row_count": int(summary.get("non_binder_review_row_count") or 0),
        "conflict_resolution_required_count": int(summary.get("conflict_resolution_required_count") or 0),
        "kcal_placeholder_count": int(summary.get("kcal_placeholder_count") or 0),
        "source_placeholder_count": int(summary.get("source_placeholder_count") or 0),
        "target_match_placeholder_count": int(summary.get("target_match_placeholder_count") or 0),
        "review_decision_placeholder_count": int(summary.get("review_decision_placeholder_count") or 0),
        "next_review_completion_packet_ready": bool(
            summary.get("next_review_completion_packet_ready") is True
        ),
        "next_review_completion_packet": dict(summary.get("next_review_completion_packet") or {}),
        "next_review_return_bundle_required_artifacts": list(
            summary.get("next_review_return_bundle_required_artifacts") or []
        ),
        "next_review_return_bundle_required_artifact_count": int(
            summary.get("next_review_return_bundle_required_artifact_count") or 0
        ),
        "next_review_return_bundle_completion_matrix": list(
            summary.get("next_review_return_bundle_completion_matrix") or []
        ),
        "next_review_return_bundle_completion_matrix_count": int(
            summary.get("next_review_return_bundle_completion_matrix_count") or 0
        ),
        "next_review_return_bundle_blocker_count": int(
            summary.get("next_review_return_bundle_blocker_count") or 0
        ),
        "next_review_return_bundle_next_artifact_id": summary.get(
            "next_review_return_bundle_next_artifact_id", ""
        ),
        "next_review_return_bundle_next_artifact_path": summary.get(
            "next_review_return_bundle_next_artifact_path", ""
        ),
        "next_review_return_bundle_next_artifact_failed_check_ids": list(
            summary.get("next_review_return_bundle_next_artifact_failed_check_ids") or []
        ),
        "next_review_row_id": summary.get("next_review_row_id", ""),
        "next_review_candidate_name": summary.get("next_review_candidate_name", ""),
        "next_review_packet_step": summary.get("next_review_packet_step", ""),
        "next_review_required_evidence_mode": summary.get("next_review_required_evidence_mode", ""),
        "next_review_operator_review_artifact": summary.get("next_review_operator_review_artifact", ""),
        "reconciliation_packet_ready": bool(summary.get("reconciliation_packet_ready") is True),
        "reconciliation_artifact": summary.get("reconciliation_artifact", ""),
        "unique_review_row_ids_ready": bool(summary.get("unique_review_row_ids_ready") is True),
        "review_rows": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/aqp1-operator-validation-candidate")
async def get_product_aqp1_operator_validation_candidate() -> dict[str, Any]:
    packet = _read_json_object(AQP1_OPERATOR_VALIDATION_CANDIDATE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_aqp1_operator_validation_candidate_packet",
            "artifact_path": str(AQP1_OPERATOR_VALIDATION_CANDIDATE_ARTIFACT),
            "packet_ready": False,
            "candidate_ready": False,
            "candidate_count": 0,
            "candidate_claim_safe_ready_count": 0,
            "operator_validation_required_count": 0,
            "operator_placeholder_count": 0,
            "required_operator_decision_fields": [],
            "required_operator_decision_field_count": 0,
            "validation_blockers": ["missing_aqp1_operator_validation_candidate_packet"],
            "validation_blocker_count": 1,
            "first_candidate_id": "",
            "first_candidate_target_id": "",
            "first_candidate_target_uniprot": "",
            "first_candidate_ligand_external_identifier": "",
            "first_candidate_ligand_name": "",
            "first_candidate_activity_id": "",
            "first_candidate_standard_type": "",
            "first_candidate_standard_value_nM": "",
            "first_candidate_reference_binding_kcal_mol": "",
            "first_candidate_blocker": "",
            "first_candidate_claim_safe_ready": False,
            "first_candidate_source_locator": "",
            "return_bundle_required_artifacts": [],
            "return_bundle_required_artifact_count": 0,
            "post_return_validation_commands": [],
            "post_return_validation_command_count": 0,
            "rows": [],
            "blockers": [{"code": "missing_aqp1_operator_validation_candidate_packet"}],
            "next_required_step": "Run python3 tools/build_aqp1_operator_validation_candidate_packet.py.",
            "claim_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "AQP1 operator-validation candidate endpoint only; local packet artifact is missing. It does not "
                "approve claim-safe binding kcal, promote transporter scope, run docking, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status") or "aqp1_operator_validation_candidate_packet_ready",
        "artifact_path": str(AQP1_OPERATOR_VALIDATION_CANDIDATE_ARTIFACT),
        "packet_ready": bool(summary.get("packet_ready") is True),
        "candidate_ready": bool(summary.get("candidate_ready") is True),
        "candidate_count": int(summary.get("candidate_count") or 0),
        "candidate_claim_safe_ready_count": int(summary.get("candidate_claim_safe_ready_count") or 0),
        "operator_validation_required_count": int(summary.get("operator_validation_required_count") or 0),
        "operator_placeholder_count": int(summary.get("operator_placeholder_count") or 0),
        "required_operator_decision_fields": list(summary.get("required_operator_decision_fields") or []),
        "required_operator_decision_field_count": int(
            summary.get("required_operator_decision_field_count") or 0
        ),
        "validation_blockers": list(summary.get("validation_blockers") or []),
        "validation_blocker_count": int(summary.get("validation_blocker_count") or 0),
        "first_candidate_id": summary.get("first_candidate_id", ""),
        "first_candidate_target_id": summary.get("first_candidate_target_id", ""),
        "first_candidate_target_uniprot": summary.get("first_candidate_target_uniprot", ""),
        "first_candidate_ligand_external_identifier": summary.get(
            "first_candidate_ligand_external_identifier", ""
        ),
        "first_candidate_ligand_name": summary.get("first_candidate_ligand_name", ""),
        "first_candidate_activity_id": summary.get("first_candidate_activity_id", ""),
        "first_candidate_standard_type": summary.get("first_candidate_standard_type", ""),
        "first_candidate_standard_value_nM": summary.get("first_candidate_standard_value_nM", ""),
        "first_candidate_reference_binding_kcal_mol": summary.get(
            "first_candidate_reference_binding_kcal_mol", ""
        ),
        "first_candidate_blocker": summary.get("first_candidate_blocker", ""),
        "first_candidate_claim_safe_ready": bool(summary.get("first_candidate_claim_safe_ready") is True),
        "first_candidate_source_locator": summary.get("first_candidate_source_locator", ""),
        "return_bundle_required_artifacts": list(summary.get("return_bundle_required_artifacts") or []),
        "return_bundle_required_artifact_count": int(
            summary.get("return_bundle_required_artifact_count") or 0
        ),
        "post_return_validation_commands": list(summary.get("post_return_validation_commands") or []),
        "post_return_validation_command_count": int(
            summary.get("post_return_validation_command_count") or 0
        ),
        "rows": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "claim_promotion_allowed": False,
        "authoritative_apply_allowed": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/aqp1-direct-binding-procurement-packet")
async def get_product_aqp1_direct_binding_procurement_packet() -> dict[str, Any]:
    packet = _read_json_object(AQP1_DIRECT_BINDING_PROCUREMENT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_aqp1_direct_binding_procurement_packet",
            "artifact_path": str(AQP1_DIRECT_BINDING_PROCUREMENT_ARTIFACT),
            "procurement_packet_ready": False,
            "target_id": "",
            "target_uniprot": "",
            "current_direct_experimental_binding_row_count": 0,
            "current_claim_safe_binding_kcal_ready_count": 0,
            "direct_binding_gap_open": True,
            "public_direct_binding_recheck_ready": False,
            "public_direct_binding_recheck_result": "",
            "current_operator_candidate_id": "",
            "current_operator_candidate_ligand_external_identifier": "",
            "current_operator_candidate_reference_binding_kcal_mol": "",
            "current_operator_candidate_blocker": "",
            "current_operator_candidate_claim_safe_ready": False,
            "external_primary_evidence_required": True,
            "accepted_direct_binding_methods": [],
            "acceptance_fields": [],
            "acceptance_field_count": 0,
            "minimum_acceptance_rule": "",
            "first_required_external_action_id": "",
            "post_return_validation_commands": [],
            "post_return_validation_command_count": 0,
            "rows": [],
            "blockers": [{"code": "missing_aqp1_direct_binding_procurement_packet"}],
            "next_required_step": "Run python3 tools/build_aqp1_direct_binding_procurement_packet.py.",
            "claim_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "AQP1 direct-binding procurement endpoint only; local packet artifact is missing. It does not "
                "approve claim-safe binding kcal, promote transporter scope, run docking, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status") or "aqp1_direct_binding_procurement_packet_ready",
        "artifact_path": str(AQP1_DIRECT_BINDING_PROCUREMENT_ARTIFACT),
        "procurement_packet_ready": bool(summary.get("procurement_packet_ready") is True),
        "target_id": summary.get("target_id", ""),
        "target_uniprot": summary.get("target_uniprot", ""),
        "current_direct_experimental_binding_row_count": int(
            summary.get("current_direct_experimental_binding_row_count") or 0
        ),
        "current_claim_safe_binding_kcal_ready_count": int(
            summary.get("current_claim_safe_binding_kcal_ready_count") or 0
        ),
        "direct_binding_gap_open": bool(summary.get("direct_binding_gap_open") is True),
        "public_direct_binding_recheck_ready": bool(
            summary.get("public_direct_binding_recheck_ready") is True
        ),
        "public_direct_binding_recheck_result": summary.get("public_direct_binding_recheck_result", ""),
        "current_operator_candidate_id": summary.get("current_operator_candidate_id", ""),
        "current_operator_candidate_ligand_external_identifier": summary.get(
            "current_operator_candidate_ligand_external_identifier", ""
        ),
        "current_operator_candidate_reference_binding_kcal_mol": summary.get(
            "current_operator_candidate_reference_binding_kcal_mol", ""
        ),
        "current_operator_candidate_blocker": summary.get("current_operator_candidate_blocker", ""),
        "current_operator_candidate_claim_safe_ready": bool(
            summary.get("current_operator_candidate_claim_safe_ready") is True
        ),
        "external_primary_evidence_required": bool(
            summary.get("external_primary_evidence_required") is True
        ),
        "accepted_direct_binding_methods": list(summary.get("accepted_direct_binding_methods") or []),
        "acceptance_fields": list(summary.get("acceptance_fields") or []),
        "acceptance_field_count": int(summary.get("acceptance_field_count") or 0),
        "minimum_acceptance_rule": summary.get("minimum_acceptance_rule", ""),
        "first_required_external_action_id": summary.get("first_required_external_action_id", ""),
        "post_return_validation_commands": list(summary.get("post_return_validation_commands") or []),
        "post_return_validation_command_count": int(
            summary.get("post_return_validation_command_count") or 0
        ),
        "rows": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "claim_promotion_allowed": False,
        "authoritative_apply_allowed": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
