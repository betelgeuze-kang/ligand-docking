from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_scope_breadth_contract as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def _ready_payload() -> dict[str, object]:
    return mod.build_product_scope_breadth_contract(
        capability_packet=_packet({"allowed_scope_families": ["gpcr", "ion_channel", "kinase", "transporter", "ca2", "pxr"], "general_protein_ligand_platform_ready": True}),
        transporter_packet=_packet({"supportive_target_specific_packet_evidence_count": 6, "pending_capture_count": 0, "placeholder_driven_rows": 0, "donor_policy_reopen_ready": True}),
        ca2_packet=_packet({"verified_row_count": 6, "binder_row_count": 3}),
        pxr_packet={"summary": {"intake_applied": True, "captured_supportive_count": 3}, "applied_commit_summary": {"blocked_row_count": 0, "ready_for_apply_row_count": 6}},
        pxr_fill_readiness_packet=_packet({"queue_row_count": 6, "ready_for_apply_row_count": 6, "blocked_row_count": 0}),
        idp_scaffold_packet=_packet({"broader_promotion_blocked": False, "controlled_target_count": 8, "additional_anchor_backed_target_count": 1}),
        allatom_packet=_packet({"claim_readiness_ready": True, "strict_release_targets_supported": True, "missing_inputs": []}),
    )


def test_product_scope_breadth_contract_ready_when_all_domains_ready() -> None:
    payload = _ready_payload()

    summary = payload["summary"]
    assert summary["status"] == "product_scope_breadth_contract_ready"
    assert summary["scope_breadth_ready"] is True
    assert summary["missing_domains"] == []
    assert summary["ready_domain_count"] == 6
    assert summary["scope_claim_posture_ready"] is True
    assert summary["restricted_scope_claim_allowed"] is True
    assert summary["general_platform_claim_allowed"] is True
    assert summary["blocked_claim_scopes"] == []
    assert "general_protein_ligand_platform" in summary["allowed_claim_scopes"]
    assert summary["scope_acceptance_matrix_ready"] is True
    assert summary["scope_claim_expansion_contract_ready"] is True
    assert summary["scope_claim_expansion_currently_satisfied"] is True
    assert summary["scope_claim_expansion_current_blocked_stage_count"] == 0
    assert summary["scope_claim_expansion_current_next_stage_id"] == ""
    assert summary["scope_acceptance_stage_count"] == 5
    assert summary["scope_acceptance_blocked_stage_count"] == 0
    assert summary["scope_acceptance_next_stage_id"] == ""
    assert summary["scope_acceptance_stage_evidence_matrix_count"] == 5
    assert summary["scope_acceptance_current_blocked_stage_evidence_matrix_count"] == 0
    assert summary["first_blocked_domain"] == ""
    assert summary["first_blocked_domain_artifact"] == ""


def test_product_scope_breadth_contract_blocks_partial_scope() -> None:
    payload = mod.build_product_scope_breadth_contract(
        capability_packet=_packet({"allowed_scope_families": ["gpcr", "ion_channel", "kinase"]}),
        transporter_packet=_packet({"supportive_target_specific_packet_evidence_count": 6, "pending_capture_count": 0, "placeholder_driven_rows": 6, "donor_policy_reopen_ready": False}),
        ca2_packet=_packet({"verified_row_count": 7, "binder_row_count": 6}),
        pxr_packet={"summary": {"intake_applied": True, "captured_supportive_count": 6}, "applied_commit_summary": {"blocked_row_count": 6, "ready_for_apply_row_count": 8}},
        idp_scaffold_packet=_packet({"broader_promotion_blocked": True, "controlled_target_count": 7, "additional_anchor_backed_target_count": 0}),
        allatom_packet=_packet({"claim_readiness_ready": False, "strict_release_targets_supported": True, "missing_inputs": ["strict_summary_json"]}),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_scope_breadth_contract"
    assert summary["scope_breadth_ready"] is False
    assert summary["ready_domains"] == ["ca2"]
    assert "transporter" in summary["missing_domains"]
    assert "general_protein_ligand" in summary["missing_domains"]
    assert summary["first_blocked_domain"] == "transporter"
    assert summary["first_blocked_domain_artifact"] == "runs/transporter_blocker_capture_sheet_current.json"
    assert "placeholder=6" in summary["first_blocked_domain_observed"]
    assert "supportive transporter evidence" in summary["first_blocked_domain_requirement"]
    assert "Replace placeholder transporter packet rows" in summary["first_blocked_domain_next_action"]
    assert summary["scope_claim_posture_ready"] is True
    assert summary["restricted_scope_claim_allowed"] is True
    assert summary["general_platform_claim_allowed"] is False
    assert summary["general_platform_claim_blocked"] is True
    assert "transporter_domain_promotion" in summary["blocked_claim_scopes"]
    assert "pxr_domain_promotion" in summary["blocked_claim_scopes"]
    assert "general_protein_ligand_platform" in summary["blocked_claim_scopes"]
    assert summary["allowed_claim_scopes"] == ["current_restricted_delivery_scope"]
    assert summary["scope_acceptance_matrix_ready"] is False
    assert summary["scope_claim_expansion_contract_ready"] is False
    assert summary["scope_claim_expansion_currently_satisfied"] is False
    assert summary["scope_acceptance_next_stage_id"] == "scope_evidence_acquisition_preflight"


def test_product_scope_breadth_contract_surfaces_acquisition_plan_for_blocked_scope() -> None:
    payload = mod.build_product_scope_breadth_contract(
        capability_packet=_packet({"allowed_scope_families": ["gpcr", "ion_channel", "kinase"]}),
        transporter_packet=_packet({"supportive_target_specific_packet_evidence_count": 6, "pending_capture_count": 0, "placeholder_driven_rows": 6, "donor_policy_reopen_ready": False}),
        ca2_packet=_packet({"verified_row_count": 7, "binder_row_count": 6}),
        pxr_packet={"summary": {"intake_applied": True, "captured_supportive_count": 6}, "applied_commit_summary": {"blocked_row_count": 6, "ready_for_apply_row_count": 8}},
        idp_scaffold_packet=_packet({"broader_promotion_blocked": True, "controlled_target_count": 7, "additional_anchor_backed_target_count": 0}),
        allatom_packet=_packet({"claim_readiness_ready": False, "strict_release_targets_supported": True, "missing_inputs": ["strict_summary_json"]}),
        evidence_queue_packet=_packet(
            {
                "queue_ready": True,
                "queue_item_count": 9,
                "scientific_evidence_request_count": 6,
                "claim_gate_prerequisite_count": 3,
                "next_operator_completion_packet_ready": True,
                "next_operator_completion_slot_id": "AQP1.core_binder_01",
                "next_operator_completion_expected_evidence_type": "direct_or_claim_safe_binding_kcal",
                "next_operator_completion_required_exact_evidence_field_count": 3,
                "next_operator_completion_required_exact_evidence_fields": (
                    "target_uniprot_accession;source_pmid_or_document_id;evidence_sentence_or_table_locator"
                ),
                "next_operator_completion_required_operator_intake_columns": (
                    "target_id;candidate_ligand_id;reference_binding_kcal_mol;source_url_or_doi"
                ),
                "next_operator_completion_required_claim_guardrails": (
                    "functional_surrogate_does_not_authorize_direct_binding_claim;"
                    "scope_promotion_allowed_false_until_all_transporter_p0_slots_green"
                ),
                "next_operator_completion_operator_review_artifact": (
                    "runs/transporter_manual_review_intake_template_current.csv"
                ),
                "next_operator_completion_post_intake_synchronization_targets": (
                    "config/ligand_binding_reference_blind_aqp1_v1.csv;"
                    "config/ligand_eval_splits_blind_aqp1_v1.csv"
                ),
                "next_operator_completion_acceptance_gate_commands": (
                    "python3 tools/build_transporter_binder_promotion_gate.py;"
                    "python3 tools/build_product_scope_breadth_contract.py"
                ),
                "next_operator_completion_contract_artifact": (
                    "runs/transporter_p0_evidence_acquisition_packet_current.json#next_slot_completion_packet"
                ),
                "next_operator_completion_aqp1_review_sidecar_ready": True,
                "next_operator_completion_aqp1_functional_surrogate_artifact": (
                    "runs/aqp1_functional_kcal_surrogate_packet_current.json"
                ),
                "next_operator_completion_aqp1_candidate_ledger_artifact": (
                    "runs/aqp1_candidate_evidence_ledger_current.json"
                ),
                "next_operator_completion_aqp1_review_candidate_name": "bacopaside II",
                "next_operator_completion_aqp1_review_source_anchor": "PMID 27474162",
                "next_operator_completion_aqp1_review_source_url": (
                    "https://pubmed.ncbi.nlm.nih.gov/27474162/"
                ),
                "next_operator_completion_aqp1_review_target_uniprot": "P29972",
                "next_operator_completion_aqp1_review_functional_measure": "IC50;18;uM",
                "next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": "-6.47",
                "next_operator_completion_aqp1_review_assay_type_honesty": (
                    "functional_ic50_derived_surrogate_not_direct_binding"
                ),
                "next_operator_completion_aqp1_review_direct_binding_claim_allowed": "no",
                "next_operator_completion_aqp1_review_binding_kcal_claim_allowed": "no",
                "next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": "yes",
                "next_operator_completion_aqp1_review_claim_safe_functional_kcal_ready": "yes",
                "next_operator_completion_aqp1_review_ledger_review_bucket": "review_only_first_wave",
                "next_operator_completion_aqp1_review_ledger_promotion_policy": (
                    "draft_first_wave_manual_review"
                ),
                "pxr_exact_review_sidecar_row_count": 6,
                "next_pxr_exact_review_sidecar_ready": True,
                "next_pxr_exact_review_row_id": "pxr_review_d603772038dff21e",
                "next_pxr_exact_review_candidate_name": "acetaminophen",
                "next_pxr_exact_review_required_evidence_mode": (
                    "exact_human_nr1i2_pxr_conflict_resolution_or_negative_value_required"
                ),
                "next_pxr_exact_review_target_match_confirmed": "OPERATOR_FILL_TRUE_OR_FALSE",
                "next_pxr_exact_review_replacement_reference_binding_kcal_mol": (
                    "OPERATOR_FILL_EXACT_HUMAN_NR1I2_PXR_KCAL_OR_KEEP_BLOCKED"
                ),
                "next_pxr_exact_review_replacement_source_url_or_doi": (
                    "OPERATOR_FILL_EXACT_SOURCE_URL_OR_DOI_OR_KEEP_BLOCKED"
                ),
                "next_pxr_exact_review_authoritative_apply_allowed": False,
                "next_pxr_exact_review_scope_promotion_allowed": False,
                "next_required_step": "work queue",
            }
        ),
        evidence_priority_packet=_packet(
            {
                "priority_packet_ready": True,
                "queue_item_count": 9,
                "scientific_evidence_request_count": 6,
                "claim_gate_prerequisite_count": 3,
                "local_crosscheck_candidate_count": 2,
                "external_primary_exact_evidence_required_count": 4,
                "review_only_keep_blocked_count": 1,
                "next_required_step": "triage priority",
            }
        ),
        evidence_intake_readiness_packet=_packet(
            {
                "intake_readiness_ready": True,
                "row_count": 9,
                "local_crosscheck_intake_ready_count": 2,
                "local_crosscheck_unreadable_item_count": 0,
                "external_exact_evidence_required_count": 4,
                "guardrail_item_count": 3,
                "transporter_triage_packet_ready": True,
                "transporter_operator_review_evidence_matrix_ready": True,
                "transporter_claim_safe_local_evidence_ready_count": 0,
                "transporter_claim_safe_local_evidence_blocked_count": 2,
                "transporter_direct_binding_claim_blocked_count": 1,
                "transporter_negative_value_claim_blocked_count": 1,
                "transporter_top_claim_safe_blocker": "functional_assay_quantitative_but_not_direct_binding_claim_safe",
                "transporter_top_operator_next_verdict": "keep_functional_surrogate_review_only_until_direct_binding_source",
                "transporter_candidate_assignment_required_count": 2,
                "transporter_functional_quantitative_only_direct_gap_open_count": 1,
                "transporter_review_only_direct_binding_gap_count": 1,
                "transporter_local_crosscheck_can_close_slots_without_manual_assignment": False,
                "transporter_candidate_workbook_ready": True,
                "transporter_candidate_row_count": 11,
                "transporter_candidate_ready_for_manual_review_count": 11,
                "transporter_candidate_ready_for_apply_count": 0,
                "transporter_candidate_negative_value_review_required_count": 6,
                "transporter_manual_review_intake_ready": True,
                "transporter_manual_review_template_row_count": 11,
                "transporter_manual_review_direct_binding_evidence_required_count": 4,
                "transporter_manual_review_negative_quantitative_value_required_count": 6,
                "transporter_manual_review_decision_placeholder_count": 11,
                "scope_operator_transfer_manifest_ready": True,
                "scope_operator_transfer_outbound_artifact_count": 10,
                "scope_operator_transfer_outbound_artifacts": [
                    "runs/product_scope_breadth_evidence_priority_packet_current.json",
                    "runs/transporter_manual_review_intake_template_current.json",
                    "runs/pxr_exact_evidence_review_intake_template_current.json",
                ],
                "scope_operator_transfer_inbound_artifact_count": 4,
                "scope_operator_transfer_inbound_artifacts": [
                    "completed runs/transporter_manual_review_intake_template_current.csv with OPERATOR_FILL placeholders resolved",
                    "completed runs/pxr_exact_evidence_review_intake_template_current.csv with exact human NR1I2/PXR values",
                ],
                "scope_operator_transfer_first_return_artifact": (
                    "completed runs/transporter_manual_review_intake_template_current.csv with OPERATOR_FILL placeholders resolved"
                ),
                "scope_operator_transfer_acceptance_artifact": "runs/product_scope_breadth_contract_current.json",
                "scope_operator_transfer_acceptance_ready_key": "scope_breadth_ready",
                "scope_operator_transfer_next_acceptance_stage": "transporter_claim_acceptance",
                "scope_operator_transfer_post_return_validation_command": (
                    "python3 tools/build_transporter_manual_review_intake_template.py"
                ),
                "next_required_step": "triage intake readiness",
            }
        ),
        pxr_source_modality_triage_packet=_packet(
            {
                "source_modality_guard_ready": True,
                "status": "blocked_pxr_source_modality_triage",
                "triage_artifact": "runs/pxr_source_modality_triage_current.json",
                "triage_decision": (
                    "keep_blocked_until_all_pxr_rows_have_exact_human_nr1i2_pxr_direct_or_claim_safe_quantitative_evidence"
                ),
                "activity_proxy_or_conflict_surrogate_row_count": 3,
                "direct_or_claim_safe_quantitative_ready_count": 0,
                "accepted_for_scope_promotion_count": 0,
                "direct_replacement_candidate_packet_ready": True,
                "direct_replacement_selected_claim_safe_candidate_count": 6,
                "direct_replacement_apply_draft_ready": True,
                "direct_replacement_apply_draft_status": (
                    "pxr_direct_binding_replacement_apply_draft_ready"
                ),
                "direct_replacement_apply_draft_artifact": (
                    "runs/pxr_direct_binding_replacement_apply_draft_current.json"
                ),
                "direct_replacement_apply_draft_workbook_row_count": 14,
                "direct_replacement_apply_draft_blocked_row_count_before_draft": 6,
                "direct_replacement_apply_draft_overlay_row_count": 6,
                "direct_replacement_apply_draft_ready_for_apply_row_count_after_draft": 14,
                "direct_replacement_apply_draft_blocked_row_count_after_draft": 0,
                "direct_replacement_apply_draft_first_overlay_ligand_id": "e_guggulsterone",
                "direct_replacement_apply_draft_authoritative_fields_touched": False,
                "next_review_row_id": "pxr_review_d603772038dff21e",
                "next_review_candidate_name": "acetaminophen",
                "next_review_source_modality": "activity_proxy_or_conflict_surrogate",
                "next_review_rejection_reason": (
                    "activity_proxy_conflict_requires_exact_human_nr1i2_pxr_resolution"
                ),
            }
        ),
        transporter_p0_closure_packet=_packet(
            {
                "p0_closure_packet_ready": True,
                "current_membrane_p0_open_count": 6,
                "closure_row_count": 6,
                "p0_count_matches_readiness": True,
                "aqp1_core_p0_open_count": 3,
                "glut1_core_p0_open_count": 3,
                "glut1_reference_placeholder_rows_after_apply": 5,
                "glut1_split_placeholder_rows_after_apply": 5,
                "glut1_meta_placeholder_rows_after_apply": 5,
                "next_required_step": "close transporter P0 rows",
            }
        ),
        transporter_p0_readiness_matrix_packet=_packet(
            {
                "readiness_matrix_ready": True,
                "auto_close_ready_artifact_count": 0,
                "manual_or_external_required_artifact_count": 6,
                "unresolved_slot_count": 11,
                "auto_close_ready_slot_count": 0,
                "external_exact_evidence_required_slot_count": 11,
                "first_manual_or_external_required_step_id": "aqp1_ligand_reference",
                "first_manual_or_external_required_slot_step": "core_binder_01",
                "first_manual_or_external_required_action": "Acquire exact target-pair quantitative evidence.",
            }
        ),
        transporter_p0_evidence_acquisition_packet={
            "summary": {
                "evidence_acquisition_packet_ready": True,
                "exact_evidence_request_slot_count": 11,
                "unresolved_slot_count": 11,
                "next_slot_completion_packet_ready": True,
                "next_evidence_slot_id": "AQP1.core_binder_01",
                "next_evidence_slot_operator_review_artifact": (
                    "runs/transporter_manual_review_intake_template_current.csv"
                ),
                "next_slot_return_bundle_required_artifacts": [
                    "runs/transporter_manual_review_intake_template_current.csv",
                    "config/ligand_binding_reference_blind_aqp1_v1.csv",
                    "config/ligand_eval_splits_blind_aqp1_v1.csv",
                    "config/ligand_meta_blind_aqp1_v1.csv",
                    "runs/transporter_binder_promotion_gate_current.json",
                ],
                "next_slot_return_bundle_required_artifact_count": 5,
                "next_slot_return_bundle_completion_matrix": [
                    {
                        "artifact_id": "operator_review_row",
                        "status": "blocked",
                        "artifact_path": "runs/transporter_manual_review_intake_template_current.csv",
                    }
                ],
                "next_slot_return_bundle_completion_matrix_count": 5,
                "next_slot_return_bundle_blocker_count": 5,
                "next_slot_return_bundle_next_artifact_id": "operator_review_row",
                "next_slot_return_bundle_next_artifact_path": (
                    "runs/transporter_manual_review_intake_template_current.csv"
                ),
                "next_slot_return_bundle_next_artifact_failed_check_ids": [
                    "next_slot_required_missing_fields",
                    "operator_review_row_not_operator_verified",
                ],
                "next_slot_source_modality_guard_ready": True,
                "next_slot_source_modality": "functional_quantitative_surrogate",
                "next_slot_source_modality_claim_safe": False,
                "next_slot_source_modality_direct_binding_claim_allowed": False,
                "next_slot_source_modality_decision": (
                    "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
                ),
                "next_slot_source_modality_guardrails": [
                    "functional_quantitative_surrogate_is_review_only",
                    "scope_promotion_allowed_false_until_source_modality_upgrade",
                ],
                "next_slot_source_modality_observed_signal": (
                    "request_mode=exact_target_pair_quantitative_binder_kcal_required;"
                    "source_signal=https://pubmed.ncbi.nlm.nih.gov/27474162/;"
                    "missing_fields=replacement_reference_binding_kcal_mol"
                ),
                "next_slot_source_modality_required_upgrade": (
                    "exact target-pair direct/claim-safe binding kcal/mol with source locator, target match, "
                    "and operator review decision"
                ),
                "aqp1_binding_source_modality_triage_ready": True,
                "aqp1_binding_source_modality_triage_status": (
                    "blocked_aqp1_binding_source_modality_triage"
                ),
                "aqp1_binding_source_modality_triage_artifact": (
                    "runs/aqp1_binding_source_modality_triage_current.json"
                ),
                "aqp1_binding_source_modality_triage_decision": (
                    "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
                ),
                "aqp1_binding_source_modality_direct_experimental_binding_row_count": 0,
                "aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count": 0,
                "aqp1_binding_source_modality_public_direct_binding_recheck_ready": True,
                "aqp1_binding_source_modality_public_direct_binding_recheck_source_count": 6,
                "aqp1_binding_source_modality_public_direct_binding_recheck_result": (
                    "no_public_direct_experimental_or_claim_safe_binding_kcal_for_aqp1_bacopaside_ii;"
                    "chembl_aqp1_bacopaside_ii_rows=0;bindingdb_p29972_affinities=0;"
                    "functional_ic50_identity_mismatch=CHEMBL195380_not_CHEMBL390758"
                ),
                "aqp1_binding_source_modality_public_database_recheck_row_count": 2,
                "aqp1_binding_source_modality_ligand_identity_mismatch_row_count": 1,
                "aqp1_binding_source_modality_bacopaside_ii_pubchem_cid": "9876264",
                "aqp1_binding_source_modality_bacopaside_ii_chembl_id": "CHEMBL390758",
                "aqp1_binding_source_modality_aqp1_chembl_target_id": "CHEMBL4523210",
                "aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count": 0,
                "aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count": 0,
                "aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail": (
                    "AQP1 functional IC50 2700 nM row is CHEMBL195380, "
                    "while bacopaside II is CHEMBL390758."
                ),
                "aqp1_binding_source_modality_replacement_reference_binding_kcal_mol_action": (
                    "keep_blank_until_direct_binding_or_operator_verified_claim_safe_kcal"
                ),
                "aqp1_binding_source_modality_computational_binding_energy_row_count": 1,
                "aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol": "-34.48",
                "next_slot_completion_packet": {
                    "slot_id": "AQP1.core_binder_01",
                    "target_id": "AQP1",
                    "packet_step": "core_binder_01",
                    "candidate_ligand_id": "aqp1_bacopaside_ii_review_seed",
                    "required_operator_intake_columns": [
                        "target_id",
                        "candidate_ligand_id",
                        "reference_binding_kcal_mol",
                        "source_url_or_doi",
                        "smiles",
                        "scaffold",
                        "evidence_type",
                    ],
                },
            },
            "rows": [
                {
                    "target_id": "AQP1",
                    "packet_step": "core_binder_01",
                    "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                    "request_mode": "exact_target_pair_quantitative_binder_kcal_required",
                    "source_signal": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "required_missing_fields": "replacement_reference_binding_kcal_mol",
                    "next_required_action": "Acquire exact target-pair quantitative evidence.",
                }
            ],
        },
    )

    summary = payload["summary"]
    assert summary["scope_breadth_ready"] is False
    assert summary["first_blocked_domain"] == "transporter"
    assert "authoritative_binders=0" in summary["first_blocked_domain_observed"]
    assert "p0_closure_rows=6" in summary["first_blocked_domain_observed"]
    assert "p0_manual_or_external_artifacts=6" in summary["first_blocked_domain_observed"]
    assert "Replace placeholder transporter packet rows" in summary["first_blocked_domain_next_action"]
    assert summary["transporter_p0_closure_packet_ready"] is True
    assert summary["transporter_p0_current_membrane_open_count"] == 6
    assert summary["transporter_p0_closure_row_count"] == 6
    assert summary["transporter_p0_count_matches_readiness"] is True
    assert summary["transporter_p0_aqp1_core_open_count"] == 3
    assert summary["transporter_p0_glut1_core_open_count"] == 3
    assert summary["transporter_p0_glut1_reference_placeholder_rows_after_apply"] == 5
    assert summary["transporter_p0_next_required_step"] == "close transporter P0 rows"
    assert summary["transporter_p0_readiness_matrix_ready"] is True
    assert summary["transporter_p0_auto_close_ready_artifact_count"] == 0
    assert summary["transporter_p0_manual_or_external_required_artifact_count"] == 6
    assert summary["transporter_p0_unresolved_slot_count"] == 11
    assert summary["transporter_p0_auto_close_ready_slot_count"] == 0
    assert summary["transporter_p0_external_exact_evidence_required_slot_count"] == 11
    assert summary["transporter_p0_first_manual_or_external_required_step_id"] == "aqp1_ligand_reference"
    assert summary["transporter_p0_first_manual_or_external_required_slot_step"] == "core_binder_01"
    assert summary["transporter_p0_first_manual_or_external_required_action"].startswith("Acquire exact")
    assert summary["transporter_p0_evidence_acquisition_packet_ready"] is True
    assert summary["transporter_p0_evidence_acquisition_artifact"] == (
        "runs/transporter_p0_evidence_acquisition_packet_current.json"
    )
    assert summary["transporter_p0_evidence_acquisition_exact_request_slot_count"] == 11
    assert summary["transporter_p0_evidence_acquisition_unresolved_slot_count"] == 11
    assert summary["transporter_p0_evidence_acquisition_first_target_id"] == "AQP1"
    assert summary["transporter_p0_evidence_acquisition_first_packet_step"] == "core_binder_01"
    assert summary["transporter_p0_evidence_acquisition_first_replacement_ligand_id"] == (
        "aqp1_bacopaside_ii_review_seed"
    )
    assert summary["transporter_p0_evidence_acquisition_first_request_mode"] == (
        "exact_target_pair_quantitative_binder_kcal_required"
    )
    assert summary["transporter_p0_evidence_acquisition_first_source_signal"].startswith("https://pubmed")
    assert summary["transporter_p0_evidence_acquisition_first_required_missing_fields"] == (
        "replacement_reference_binding_kcal_mol"
    )
    assert summary["transporter_p0_evidence_acquisition_first_next_required_action"].startswith(
        "Acquire exact"
    )
    assert summary["transporter_p0_evidence_acquisition_next_slot_completion_packet_ready"] is True
    assert summary["transporter_p0_evidence_acquisition_next_slot_id"] == "AQP1.core_binder_01"
    assert summary["transporter_p0_evidence_acquisition_next_slot_operator_review_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert summary["transporter_p0_evidence_acquisition_next_slot_completion_packet"][
        "required_operator_intake_columns"
    ][0] == "target_id"
    assert summary[
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count"
    ] == 5
    assert summary["transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count"] == 5
    assert summary[
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id"
    ] == "operator_review_row"
    assert summary[
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix"
    ][0]["artifact_id"] == "operator_review_row"
    assert summary[
        "transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready"
    ] is True
    assert summary[
        "transporter_p0_evidence_acquisition_next_slot_source_modality"
    ] == "functional_quantitative_surrogate"
    assert summary[
        "transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe"
    ] is False
    assert summary[
        "transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed"
    ] is False
    assert summary[
        "transporter_p0_evidence_acquisition_next_slot_source_modality_decision"
    ] == "keep_blocked_until_exact_direct_binding_or_claim_safe_kcal"
    assert "scope_promotion_allowed_false_until_source_modality_upgrade" in summary[
        "transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails"
    ]
    assert "missing_fields=replacement_reference_binding_kcal_mol" in summary[
        "transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal"
    ]
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_ready"
    ] is True
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_artifact"
    ] == "runs/aqp1_binding_source_modality_triage_current.json"
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_decision"
    ] == "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_experimental_binding_row_count"
    ] == 0
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count"
    ] == 0
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_ready"
    ] is True
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count"
    ] == 6
    public_recheck_result = summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result"
    ]
    assert "chembl_aqp1_bacopaside_ii_rows=0" in public_recheck_result
    assert "bindingdb_p29972_affinities=0" in public_recheck_result
    assert "CHEMBL195380_not_CHEMBL390758" in public_recheck_result
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count"
    ] == 2
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count"
    ] == 1
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid"
    ] == "9876264"
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id"
    ] == "CHEMBL390758"
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id"
    ] == "CHEMBL4523210"
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count"
    ] == 0
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count"
    ] == 0
    assert "CHEMBL195380" in summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail"
    ]
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_replacement_reference_binding_kcal_mol_action"
    ] == "keep_blank_until_direct_binding_or_operator_verified_claim_safe_kcal"
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_computational_binding_energy_row_count"
    ] == 1
    assert summary[
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol"
    ] == "-34.48"
    assert summary["scope_breadth_acquisition_plan_ready"] is True
    assert summary["evidence_intake_readiness_ready"] is True
    assert summary["evidence_queue_item_count"] == 9
    assert summary["evidence_queue_next_operator_completion_packet_ready"] is True
    assert summary["evidence_queue_next_operator_completion_slot_id"] == "AQP1.core_binder_01"
    assert summary["evidence_queue_next_operator_completion_expected_evidence_type"] == (
        "direct_or_claim_safe_binding_kcal"
    )
    assert summary["evidence_queue_next_operator_completion_required_exact_evidence_field_count"] == 3
    assert "target_uniprot_accession" in summary[
        "evidence_queue_next_operator_completion_required_exact_evidence_fields"
    ]
    assert "reference_binding_kcal_mol" in summary[
        "evidence_queue_next_operator_completion_required_operator_intake_columns"
    ]
    assert "functional_surrogate_does_not_authorize_direct_binding_claim" in summary[
        "evidence_queue_next_operator_completion_required_claim_guardrails"
    ]
    assert summary["evidence_queue_next_operator_completion_operator_review_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert "ligand_binding_reference_blind_aqp1" in summary[
        "evidence_queue_next_operator_completion_post_intake_synchronization_targets"
    ]
    assert "build_product_scope_breadth_contract.py" in summary[
        "evidence_queue_next_operator_completion_acceptance_gate_commands"
    ]
    assert summary["evidence_queue_next_operator_completion_contract_artifact"].endswith(
        "#next_slot_completion_packet"
    )
    assert summary["evidence_queue_next_operator_completion_aqp1_review_sidecar_ready"] is True
    assert summary["evidence_queue_next_operator_completion_aqp1_review_candidate_name"] == (
        "bacopaside II"
    )
    assert summary["evidence_queue_next_operator_completion_aqp1_review_source_anchor"] == (
        "PMID 27474162"
    )
    assert summary["evidence_queue_pxr_exact_review_sidecar_row_count"] == 6
    assert summary["evidence_queue_next_pxr_exact_review_sidecar_ready"] is True
    assert summary["evidence_queue_next_pxr_exact_review_row_id"] == "pxr_review_d603772038dff21e"
    assert summary["evidence_queue_next_pxr_exact_review_candidate_name"] == "acetaminophen"
    assert summary["evidence_queue_next_pxr_exact_review_required_evidence_mode"] == (
        "exact_human_nr1i2_pxr_conflict_resolution_or_negative_value_required"
    )
    assert summary["evidence_queue_next_pxr_exact_review_target_match_confirmed"] == (
        "OPERATOR_FILL_TRUE_OR_FALSE"
    )
    assert summary["evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol"].startswith(
        "OPERATOR_FILL_EXACT_HUMAN_NR1I2_PXR_KCAL"
    )
    assert summary["evidence_queue_next_pxr_exact_review_authoritative_apply_allowed"] is False
    assert summary["evidence_queue_next_pxr_exact_review_scope_promotion_allowed"] is False
    assert summary["pxr_source_modality_triage_ready"] is True
    assert summary["pxr_source_modality_triage_artifact"] == "runs/pxr_source_modality_triage_current.json"
    assert summary["pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count"] == 3
    assert summary["pxr_source_modality_direct_or_claim_safe_quantitative_ready_count"] == 0
    assert summary["pxr_source_modality_direct_replacement_candidate_packet_ready"] is True
    assert summary["pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count"] == 6
    assert summary["pxr_source_modality_direct_replacement_apply_draft_ready"] is True
    assert summary["pxr_source_modality_direct_replacement_apply_draft_overlay_row_count"] == 6
    assert (
        summary["pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft"]
        == 14
    )
    assert summary["pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft"] == 0
    assert (
        summary["pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched"]
        is False
    )
    assert summary["pxr_source_modality_next_review_candidate_name"] == "acetaminophen"
    assert summary["pxr_source_modality_next_review_source_modality"] == (
        "activity_proxy_or_conflict_surrogate"
    )
    assert summary["evidence_queue_next_operator_completion_aqp1_review_target_uniprot"] == "P29972"
    assert summary[
        "evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol"
    ] == "-6.47"
    assert summary[
        "evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed"
    ] == "no"
    assert summary[
        "evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank"
    ] == "yes"
    assert summary["scientific_evidence_request_count"] == 6
    assert summary["local_crosscheck_intake_ready_count"] == 2
    assert summary["local_crosscheck_unreadable_item_count"] == 0
    assert summary["transporter_triage_packet_ready"] is True
    assert summary["transporter_operator_review_evidence_matrix_ready"] is True
    assert summary["transporter_claim_safe_local_evidence_ready_count"] == 0
    assert summary["transporter_claim_safe_local_evidence_blocked_count"] == 2
    assert summary["transporter_direct_binding_claim_blocked_count"] == 1
    assert summary["transporter_negative_value_claim_blocked_count"] == 1
    assert summary["transporter_top_claim_safe_blocker"] == (
        "functional_assay_quantitative_but_not_direct_binding_claim_safe"
    )
    assert summary["transporter_candidate_assignment_required_count"] == 2
    assert summary["transporter_functional_direct_gap_count"] == 1
    assert summary["transporter_review_only_direct_binding_gap_count"] == 1
    assert summary["transporter_local_crosscheck_can_close_slots_without_manual_assignment"] is False
    assert summary["transporter_candidate_workbook_ready"] is True
    assert summary["transporter_candidate_row_count"] == 11
    assert summary["transporter_candidate_ready_for_manual_review_count"] == 11
    assert summary["transporter_candidate_ready_for_apply_count"] == 0
    assert summary["transporter_candidate_negative_value_review_required_count"] == 6
    assert summary["transporter_manual_review_intake_ready"] is True
    assert summary["transporter_manual_review_template_row_count"] == 11
    assert summary["transporter_manual_review_direct_binding_evidence_required_count"] == 4
    assert summary["transporter_manual_review_negative_quantitative_value_required_count"] == 6
    assert summary["transporter_manual_review_decision_placeholder_count"] == 11
    assert summary["scope_operator_transfer_manifest_ready"] is True
    assert summary["scope_operator_transfer_outbound_artifact_count"] == 10
    assert "runs/transporter_manual_review_intake_template_current.json" in summary[
        "scope_operator_transfer_outbound_artifacts"
    ]
    assert summary["scope_operator_transfer_inbound_artifact_count"] == 4
    assert summary["scope_operator_transfer_first_return_artifact"] == (
        "completed runs/transporter_manual_review_intake_template_current.csv with OPERATOR_FILL placeholders resolved"
    )
    assert summary["scope_operator_transfer_acceptance_artifact"] == (
        "runs/product_scope_breadth_contract_current.json"
    )
    assert summary["scope_operator_transfer_acceptance_ready_key"] == "scope_breadth_ready"
    assert summary["scope_operator_transfer_next_acceptance_stage"] == "transporter_claim_acceptance"
    assert summary["external_primary_exact_evidence_required_count"] == 4
    assert summary["intake_external_exact_evidence_required_count"] == 4
    assert summary["intake_guardrail_item_count"] == 3
    assert summary["scope_acceptance_matrix_ready"] is True
    assert summary["scope_claim_expansion_contract_ready"] is True
    assert summary["scope_claim_expansion_currently_satisfied"] is False
    assert summary["scope_claim_expansion_current_blocked_stage_count"] == 4
    assert summary["scope_claim_expansion_current_blocked_stage_ids"][0] == "transporter_claim_acceptance"
    assert summary["scope_claim_expansion_current_next_stage_id"] == "transporter_claim_acceptance"
    assert summary["scope_claim_expansion_current_next_stage_unlock_claim_scopes"] == [
        "transporter_domain_promotion"
    ]
    assert summary["scope_acceptance_stage_count"] == 5
    assert summary["scope_acceptance_ready_stage_count"] == 1
    assert summary["scope_acceptance_blocked_stage_count"] == 4
    assert summary["scope_acceptance_ready_stage_ids"] == ["scope_evidence_acquisition_preflight"]
    assert summary["scope_acceptance_blocked_stage_ids"][0] == "transporter_claim_acceptance"
    assert summary["scope_acceptance_next_stage_id"] == "transporter_claim_acceptance"
    assert summary["scope_acceptance_next_stage_artifact"] == (
        "runs/transporter_blocker_capture_sheet_current.json;"
        "runs/transporter_binder_promotion_gate_current.json;"
        "runs/product_scope_breadth_evidence_intake_readiness_current.json;"
        "runs/transporter_p0_closure_readiness_matrix_current.json"
    )
    assert "build_transporter_binder_promotion_gate.py" in summary[
        "scope_acceptance_next_stage_validation_command"
    ]
    assert summary["scope_acceptance_next_stage_unlock_claim_scopes"] == [
        "transporter_domain_promotion"
    ]
    assert summary["scope_acceptance_next_stage_required_checks"][0] == (
        "transporter_claim_safe_local_evidence_ready"
    )
    assert summary["scope_acceptance_stage_evidence_matrix_count"] == 5
    assert summary["scope_acceptance_current_blocked_stage_evidence_matrix_count"] == 4
    transporter_stage = payload["scope_acceptance_stage_evidence_matrix"][1]
    assert transporter_stage["stage_id"] == "transporter_claim_acceptance"
    assert transporter_stage["evidence_row_count"] == 1
    assert transporter_stage["blocked_evidence_row_count"] == 1
    assert transporter_stage["first_blocked_evidence_row"]["evidence_row_id"] == "AQP1.core_binder_01"
    assert transporter_stage["first_blocked_evidence_row"]["required_missing_fields"] == (
        "replacement_reference_binding_kcal_mol"
    )
    assert summary["next_required_step"] == "triage intake readiness"


def test_product_scope_breadth_contract_blocks_acquisition_plan_on_unreadable_intake_packet() -> None:
    payload = mod.build_product_scope_breadth_contract(
        capability_packet=_packet({"allowed_scope_families": ["gpcr", "ion_channel", "kinase"]}),
        transporter_packet=_packet({"supportive_target_specific_packet_evidence_count": 6, "pending_capture_count": 0, "placeholder_driven_rows": 6, "donor_policy_reopen_ready": False}),
        ca2_packet=_packet({"verified_row_count": 7, "binder_row_count": 6}),
        pxr_packet={"summary": {"intake_applied": True, "captured_supportive_count": 6}, "applied_commit_summary": {"blocked_row_count": 6, "ready_for_apply_row_count": 8}},
        idp_scaffold_packet=_packet({"broader_promotion_blocked": True, "controlled_target_count": 7, "additional_anchor_backed_target_count": 0}),
        allatom_packet=_packet({"claim_readiness_ready": False, "strict_release_targets_supported": True, "missing_inputs": ["strict_summary_json"]}),
        evidence_queue_packet=_packet(
            {
                "queue_ready": True,
                "queue_item_count": 9,
                "scientific_evidence_request_count": 6,
                "claim_gate_prerequisite_count": 3,
            }
        ),
        evidence_priority_packet=_packet(
            {
                "priority_packet_ready": True,
                "queue_item_count": 9,
                "scientific_evidence_request_count": 6,
                "claim_gate_prerequisite_count": 3,
                "local_crosscheck_candidate_count": 2,
            }
        ),
        evidence_intake_readiness_packet=_packet(
            {
                "intake_readiness_ready": False,
                "local_crosscheck_intake_ready_count": 1,
                "local_crosscheck_unreadable_item_count": 1,
            }
        ),
    )

    summary = payload["summary"]
    assert summary["scope_breadth_ready"] is False
    assert summary["scope_breadth_acquisition_plan_ready"] is False
    assert summary["evidence_intake_readiness_ready"] is False
    assert summary["local_crosscheck_unreadable_item_count"] == 1


def test_product_scope_breadth_contract_accepts_bounded_idp_wider_shadow_lane() -> None:
    payload = mod.build_product_scope_breadth_contract(
        capability_packet=_packet({"allowed_scope_families": ["gpcr", "ion_channel", "kinase"]}),
        transporter_packet=_packet({"supportive_target_specific_packet_evidence_count": 6, "pending_capture_count": 0, "placeholder_driven_rows": 6, "donor_policy_reopen_ready": False}),
        ca2_packet=_packet({"verified_row_count": 7, "binder_row_count": 6}),
        pxr_packet={"summary": {"intake_applied": True, "captured_supportive_count": 6}, "applied_commit_summary": {"blocked_row_count": 6, "ready_for_apply_row_count": 8}},
        idp_scaffold_packet=_packet({"broader_promotion_blocked": True, "controlled_target_count": 7, "additional_anchor_backed_target_count": 0}),
        idp_promotion_resolution_packet=_packet({
            "wider_shadow_safe_lane_admitted": True,
            "shadow_safe_retained": True,
            "frozen_validated_current_target_count": 7,
            "frozen_additional_anchor_backed_target_count": 1,
            "frozen_total_target_count": 8,
            "page4_fold_pass": True,
            "tau_k18_fold_pass": True,
            "blocked_scope": "broader_full_idp_promotion",
        }),
        allatom_packet=_packet({"claim_readiness_ready": True, "strict_release_targets_supported": True, "missing_inputs": []}),
    )

    idp_row = next(row for row in payload["rows"] if row["domain"] == "idp_broad")
    assert idp_row["status"] == "ready"
    assert "bounded_wider_lane=True" in idp_row["observed"]
    assert "additional_anchor=1" in idp_row["observed"]
    assert "broader_full_idp_promotion" in idp_row["observed"]
    assert "unrestricted" in idp_row["next_action"]
    assert "idp_broad" in payload["summary"]["ready_domains"]


def test_product_scope_breadth_contract_uses_pxr_packet_fill_readiness_when_present() -> None:
    payload = mod.build_product_scope_breadth_contract(
        capability_packet=_packet({"allowed_scope_families": ["gpcr", "ion_channel", "kinase", "transporter", "ca2", "pxr"], "general_protein_ligand_platform_ready": True}),
        transporter_packet=_packet({"supportive_target_specific_packet_evidence_count": 6, "pending_capture_count": 0, "placeholder_driven_rows": 0, "donor_policy_reopen_ready": True}),
        ca2_packet=_packet({"verified_row_count": 6, "binder_row_count": 3}),
        pxr_packet={"summary": {"intake_applied": True, "captured_supportive_count": 6}, "applied_commit_summary": {"blocked_row_count": 0, "ready_for_apply_row_count": 14}},
        pxr_fill_readiness_packet=_packet({"queue_row_count": 14, "ready_for_apply_row_count": 8, "blocked_row_count": 6, "most_common_missing_field": "replacement_reference_binding_kcal_mol"}),
        pxr_blocked_gate_packet=_packet({
            "promotion_ready": False,
            "claim_safe_quantitative_ready_count": 0,
            "authoritative_apply_allowed_count": 0,
            "primary_blocker_signal": "blocked_rows=6;review_only=3;defer=3",
        }),
        pxr_exact_review_intake_packet=_packet({
            "pxr_exact_review_intake_ready": True,
            "review_template_row_count": 6,
            "conflict_resolution_required_count": 3,
            "kcal_placeholder_count": 6,
            "next_review_completion_packet_ready": True,
            "next_review_row_id": "pxr_review_1",
            "next_review_candidate_name": "acetaminophen",
            "next_review_operator_review_artifact": (
                "runs/pxr_exact_evidence_review_intake_template_current.csv"
            ),
            "next_review_return_bundle_required_artifacts": [
                "runs/pxr_exact_evidence_review_intake_template_current.csv",
                "runs/pxr_packet_fill_readiness_current.json",
                "runs/pxr_blocked_row_promotion_gate_current.json",
                "runs/pxr_authoritative_reconciliation_packet_current.json",
                "runs/product_scope_breadth_contract_current.json",
            ],
            "next_review_return_bundle_required_artifact_count": 5,
            "next_review_return_bundle_completion_matrix": [
                {
                    "artifact_id": "operator_review_row",
                    "status": "blocked",
                    "artifact_path": "runs/pxr_exact_evidence_review_intake_template_current.csv",
                    "failed_check_ids": ["next_review_placeholder_fields"],
                }
            ],
            "next_review_return_bundle_completion_matrix_count": 1,
            "next_review_return_bundle_blocker_count": 1,
            "next_review_return_bundle_next_artifact_id": "operator_review_row",
            "next_review_return_bundle_next_artifact_path": (
                "runs/pxr_exact_evidence_review_intake_template_current.csv"
            ),
            "next_review_return_bundle_next_artifact_failed_check_ids": [
                "next_review_placeholder_fields"
            ],
            "next_review_completion_packet": {
                "review_row_id": "pxr_review_1",
                "candidate_name": "acetaminophen",
                "required_operator_intake_columns": [
                    "review_row_id",
                    "replacement_reference_binding_kcal_mol",
                    "replacement_source_url_or_doi",
                ],
            },
        })
        | {
            "rows": [
                {
                    "review_row_id": "pxr_review_1",
                    "target_gene": "NR1I2",
                    "target_alias": "PXR",
                    "candidate_name": "acetaminophen",
                    "packet_step": "core_eval_non_binder_01",
                    "request_mode": "exact_human_pxr_conflict_resolution_or_negative_quantitative_value_required",
                    "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                    "fail_closed_blockers": "replacement_reference_binding_kcal_mol",
                    "replacement_reference_binding_kcal_mol": "OPERATOR_FILL_EXACT_HUMAN_NR1I2_PXR_KCAL_OR_KEEP_BLOCKED",
                    "replacement_source_url_or_doi": "OPERATOR_FILL_EXACT_SOURCE_URL_OR_DOI_OR_KEEP_BLOCKED",
                    "target_match_confirmed": "OPERATOR_FILL_TRUE_OR_FALSE",
                    "review_decision": "OPERATOR_FILL_APPROVE_FOR_DRAFT_OR_KEEP_BLOCKED",
                    "conflict_resolution_required": True,
                    "scope_promotion_allowed": False,
                    "authoritative_apply_allowed": False,
                }
            ]
        },
        idp_scaffold_packet=_packet({"broader_promotion_blocked": False, "controlled_target_count": 8, "additional_anchor_backed_target_count": 1}),
        allatom_packet=_packet({"claim_readiness_ready": True, "strict_release_targets_supported": True, "missing_inputs": []}),
    )

    pxr_row = next(row for row in payload["rows"] if row["domain"] == "pxr")
    assert pxr_row["status"] == "blocked"
    assert "ready_for_apply=8" in pxr_row["observed"]
    assert "blocked_rows=6" in pxr_row["observed"]
    assert "replacement_reference_binding_kcal_mol" in pxr_row["observed"]
    assert "promotion_ready=False" in pxr_row["observed"]
    assert "claim_safe_quantitative=0" in pxr_row["observed"]
    assert "gate_signal=blocked_rows=6;review_only=3;defer=3" in pxr_row["observed"]
    assert "exact_review_intake_ready=True" in pxr_row["observed"]
    assert "exact_review_rows=6" in pxr_row["observed"]
    assert "exact_review_conflict_required=3" in pxr_row["observed"]
    assert "exact_review_kcal_placeholders=6" in pxr_row["observed"]
    assert payload["summary"]["pxr_exact_review_intake_ready"] is True
    assert payload["summary"]["pxr_exact_review_template_row_count"] == 6
    assert payload["summary"]["pxr_exact_review_conflict_resolution_required_count"] == 3
    assert payload["summary"]["pxr_exact_review_kcal_placeholder_count"] == 6
    assert payload["summary"]["pxr_exact_review_next_review_completion_packet_ready"] is True
    assert payload["summary"]["pxr_exact_review_next_review_return_bundle_required_artifact_count"] == 5
    assert payload["summary"]["pxr_exact_review_next_review_return_bundle_blocker_count"] == 1
    assert payload["summary"]["pxr_exact_review_next_review_return_bundle_next_artifact_id"] == (
        "operator_review_row"
    )
    assert payload["summary"]["pxr_exact_review_next_review_return_bundle_completion_matrix"][0][
        "artifact_id"
    ] == "operator_review_row"
    assert payload["summary"]["pxr_exact_review_next_review_row_id"] == "pxr_review_1"
    assert payload["summary"]["pxr_exact_review_next_review_candidate_name"] == "acetaminophen"
    assert payload["summary"]["pxr_exact_review_next_review_completion_packet"][
        "required_operator_intake_columns"
    ][0] == "review_row_id"
    pxr_stage = payload["scope_acceptance_stage_evidence_matrix"][2]
    assert pxr_stage["stage_id"] == "pxr_claim_acceptance"
    assert pxr_stage["evidence_row_count"] == 1
    assert pxr_stage["blocked_evidence_row_count"] == 1
    assert pxr_stage["first_blocked_evidence_row"]["evidence_row_id"] == "pxr_review_1"
    assert pxr_stage["first_blocked_evidence_row"]["target_gene"] == "NR1I2"


def test_product_scope_breadth_contract_surfaces_transporter_reopen_blockers() -> None:
    payload = mod.build_product_scope_breadth_contract(
        capability_packet=_packet({"allowed_scope_families": ["gpcr", "ion_channel", "kinase"]}),
        transporter_packet=_packet({"supportive_target_specific_packet_evidence_count": 6, "pending_capture_count": 0, "placeholder_driven_rows": 0, "donor_policy_reopen_ready": False}),
        transporter_reopen_packet={
            "summary": {"reopen_ready": False},
            "rows": [{"check_id": "p0_scaffold_open_count_zero", "current_value": 9}],
        },
        transporter_binder_gate_packet=_packet({
            "claim_safe_kcal_ready_count": 0,
            "workbook_ready_binder_row_count": 0,
            "authoritative_binder_apply_allowed_count": 0,
            "primary_blocker_signal": "claim_safe_kcal_ready_count=0",
            "target_ready_for_promotion_ids": ["GLUT1"],
            "target_blocked_for_promotion_ids": ["AQP1"],
            "target_ready_for_promotion_count": 1,
            "target_blocked_for_promotion_count": 1,
            "primary_blocker_target_id": "AQP1",
            "primary_blocker_packet_step": "core_binder_01",
            "primary_blocker_candidate_name": "bacopaside II",
        }),
        ca2_packet=_packet({}),
        pxr_packet=_packet({}),
        idp_scaffold_packet=_packet({}),
        allatom_packet=_packet({}),
    )

    transporter_row = next(row for row in payload["rows"] if row["domain"] == "transporter")
    assert transporter_row["status"] == "blocked"
    assert "p0_open=9" in transporter_row["observed"]
    assert "claim_safe_binders=0" in transporter_row["observed"]
    assert "authoritative_binders=0" in transporter_row["observed"]
    assert "target_ready_for_promotion=GLUT1" in transporter_row["observed"]
    assert "target_blocked_for_promotion=AQP1" in transporter_row["observed"]
    assert "primary_blocker_target=AQP1" in transporter_row["observed"]
    assert payload["summary"]["transporter_target_ready_for_promotion_ids"] == ["GLUT1"]
    assert payload["summary"]["transporter_target_blocked_for_promotion_ids"] == ["AQP1"]
    assert payload["summary"]["transporter_primary_blocker_target_id"] == "AQP1"
    assert payload["summary"]["transporter_primary_blocker_packet_step"] == "core_binder_01"
    assert payload["summary"]["transporter_primary_blocker_candidate_name"] == "bacopaside II"
    assert payload["summary"]["transporter_target_ready_for_promotion_count"] == 1
    assert payload["summary"]["transporter_target_blocked_for_promotion_count"] == 1


def test_product_scope_breadth_contract_cli_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "capability.json": _packet({"allowed_scope_families": ["gpcr"]}),
        "transporter.json": _packet({}),
        "transporter_reopen.json": _packet({}),
        "transporter_binder.json": _packet({}),
        "ca2.json": _packet({}),
        "pxr.json": _packet({}),
        "pxr_fill.json": _packet({}),
        "idp.json": _packet({}),
        "idp_resolution.json": _packet({}),
        "allatom.json": _packet({}),
    }
    for name, payload in paths.items():
        (tmp_path / name).write_text(json.dumps(payload) + "\n", encoding="utf-8")
    out_json = tmp_path / "scope.json"
    out_csv = tmp_path / "scope.csv"
    out_md = tmp_path / "scope.md"

    mod.main(
        [
            "--capability-json",
            str(tmp_path / "capability.json"),
            "--transporter-json",
            str(tmp_path / "transporter.json"),
            "--transporter-reopen-json",
            str(tmp_path / "transporter_reopen.json"),
            "--transporter-binder-gate-json",
            str(tmp_path / "transporter_binder.json"),
            "--ca2-json",
            str(tmp_path / "ca2.json"),
            "--pxr-json",
            str(tmp_path / "pxr.json"),
            "--pxr-fill-readiness-json",
            str(tmp_path / "pxr_fill.json"),
            "--idp-scaffold-json",
            str(tmp_path / "idp.json"),
            "--idp-promotion-resolution-json",
            str(tmp_path / "idp_resolution.json"),
            "--allatom-json",
            str(tmp_path / "allatom.json"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["domain_count"] == 6
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["scope_acceptance_stage_count"] == 5
    assert "domain" in out_csv.read_text(encoding="utf-8")
    assert "Scope Acceptance Matrix" in out_md.read_text(encoding="utf-8")
    assert "Product Scope Breadth Contract" in out_md.read_text(encoding="utf-8")
