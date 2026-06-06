from __future__ import annotations

from tools.product import build_pxr_source_modality_triage as mod


def test_build_pxr_source_modality_triage_blocks_activity_proxy_conflict_rows() -> None:
    exact_review_packet = {
        "summary": {
            "pxr_exact_review_intake_ready": True,
            "kcal_placeholder_count": 1,
            "source_placeholder_count": 1,
            "target_match_placeholder_count": 1,
        },
        "rows": [
            {
                "review_row_id": "pxr_review_d603772038dff21e",
                "candidate_name": "acetaminophen",
                "packet_step": "core_eval_non_binder_01",
                "target_gene": "NR1I2",
                "target_alias": "PXR",
                "target_species": "human",
                "current_label": "non_binder",
                "request_mode": "exact_human_pxr_conflict_resolution_or_negative_quantitative_value_required",
                "required_evidence_mode": "exact_human_nr1i2_pxr_conflict_resolution_or_negative_value_required",
                "replacement_reference_binding_kcal_mol": (
                    "OPERATOR_FILL_EXACT_HUMAN_NR1I2_PXR_KCAL_OR_KEEP_BLOCKED"
                ),
                "replacement_source_url_or_doi": "OPERATOR_FILL_EXACT_SOURCE_URL_OR_DOI_OR_KEEP_BLOCKED",
                "target_match_confirmed": "OPERATOR_FILL_TRUE_OR_FALSE",
                "assay_is_direct_or_claim_safe": "OPERATOR_FILL_TRUE_OR_FALSE",
                "conflict_resolution_required": True,
                "conflict_resolution_decision": "OPERATOR_FILL_RESOLVE_CONFLICT_OR_KEEP_DEFERRED",
                "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                "fail_closed_blockers": "activity_proxy_conflicts_with_non_binder",
                "scope_promotion_allowed": False,
                "authoritative_apply_allowed": False,
            }
        ],
    }
    blocked_gate_packet = {
        "summary": {
            "promotion_ready": False,
            "claim_safe_quantitative_ready_count": 0,
            "authoritative_apply_allowed_count": 0,
        },
        "rows": [
            {
                "ligand": "acetaminophen",
                "promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                "evidence_signal": "exact_human_dual_mode_activity_conflict",
            }
        ],
    }
    reconciliation_packet = {"summary": {"reconciliation_packet_ready": True}}
    public_recheck_packet = {
        "summary": {
            "public_evidence_recheck_ready": True,
            "candidate_count": 1,
            "chembl_direct_binding_total_record_count": 0,
            "chembl_functional_activity_total_record_count": 1,
            "bindingdb_pxr_like_total_record_count": 0,
            "all_candidates_remain_blocked": True,
            "first_blocked_candidate_name": "acetaminophen",
            "first_blocked_reason": "functional_activity_proxy_only",
        },
        "rows": [
            {
                "candidate_name": "acetaminophen",
                "public_recheck_decision": "keep_blocked_functional_activity_not_binding_kcal_claim_safe",
                "public_recheck_blocker": "functional_activity_proxy_only",
                "chembl_activity_record_count": 2,
                "chembl_direct_binding_record_count": 0,
                "chembl_functional_activity_record_count": 2,
                "bindingdb_pxr_like_record_count": 0,
                "public_direct_or_claim_safe_binding_kcal_ready": False,
            }
        ],
    }
    direct_replacement_packet = {
        "summary": {
            "replacement_candidate_packet_ready": True,
            "direct_binding_candidate_count": 12,
            "selected_replacement_candidate_count": 6,
            "selected_claim_safe_candidate_count": 6,
            "first_replacement_ligand_id": "e_guggulsterone",
            "first_replacement_molecule_chembl_id": "CHEMBL402063",
            "first_replacement_reference_binding_kcal_mol": "-11.7595",
            "first_replacement_source": "chembl_direct_binding::CHEMBL3401::CHEMBL402063::activity_1610264",
        }
    }
    direct_replacement_apply_draft_packet = {
        "summary": {
            "draft_ready": True,
            "status": "pxr_direct_binding_replacement_apply_draft_ready",
            "workbook_row_count": 14,
            "blocked_row_count_before_draft": 6,
            "direct_binding_overlay_row_count": 6,
            "ready_for_apply_row_count_after_draft": 14,
            "blocked_row_count_after_draft": 0,
            "first_overlay_replacement_ligand_id": "e_guggulsterone",
            "authoritative_replacement_fields_touched": False,
        }
    }

    payload = mod.build_payload(
        exact_review_packet=exact_review_packet,
        blocked_gate_packet=blocked_gate_packet,
        reconciliation_packet=reconciliation_packet,
        public_recheck_packet=public_recheck_packet,
        direct_replacement_packet=direct_replacement_packet,
        direct_replacement_apply_draft_packet=direct_replacement_apply_draft_packet,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pxr_source_modality_triage"
    assert summary["source_modality_guard_ready"] is True
    assert summary["row_count"] == 1
    assert summary["conflict_resolution_required_count"] == 1
    assert summary["activity_proxy_or_conflict_surrogate_row_count"] == 1
    assert summary["direct_or_claim_safe_quantitative_ready_count"] == 0
    assert summary["accepted_for_scope_promotion_count"] == 0
    assert summary["public_evidence_recheck_ready"] is True
    assert summary["public_recheck_candidate_count"] == 1
    assert summary["public_recheck_chembl_direct_binding_total_record_count"] == 0
    assert summary["public_recheck_chembl_functional_activity_total_record_count"] == 1
    assert summary["public_recheck_bindingdb_pxr_like_total_record_count"] == 0
    assert summary["public_recheck_direct_or_claim_safe_binding_kcal_ready_count"] == 0
    assert summary["public_recheck_all_candidates_remain_blocked"] is True
    assert summary["public_recheck_first_blocked_candidate_name"] == "acetaminophen"
    assert summary["public_recheck_first_blocked_reason"] == "functional_activity_proxy_only"
    assert summary["direct_replacement_candidate_packet_ready"] is True
    assert summary["direct_replacement_candidate_count"] == 12
    assert summary["direct_replacement_selected_candidate_count"] == 6
    assert summary["direct_replacement_selected_claim_safe_candidate_count"] == 6
    assert summary["direct_replacement_first_ligand_id"] == "e_guggulsterone"
    assert summary["direct_replacement_first_reference_binding_kcal_mol"] == "-11.7595"
    assert summary["direct_replacement_apply_draft_ready"] is True
    assert summary["direct_replacement_apply_draft_overlay_row_count"] == 6
    assert summary["direct_replacement_apply_draft_ready_for_apply_row_count_after_draft"] == 14
    assert summary["direct_replacement_apply_draft_blocked_row_count_after_draft"] == 0
    assert summary["direct_replacement_apply_draft_first_overlay_ligand_id"] == "e_guggulsterone"
    assert summary["direct_replacement_apply_draft_authoritative_fields_touched"] is False
    assert summary["next_review_candidate_name"] == "acetaminophen"
    assert summary["next_review_source_modality"] == "activity_proxy_or_conflict_surrogate"
    assert summary["triage_decision"] == (
        "keep_blocked_until_all_pxr_rows_have_exact_human_nr1i2_pxr_direct_or_claim_safe_quantitative_evidence"
    )
    row = payload["rows"][0]
    assert row["direct_or_claim_safe_quantitative_evidence_ready"] is False
    assert row["accepted_for_scope_promotion"] is False
    assert row["gate_promotion_blocker"] == "activity_proxy_conflicts_with_non_binder"
    assert row["public_recheck_blocker"] == "functional_activity_proxy_only"
    assert row["public_recheck_chembl_functional_activity_record_count"] == 2
    assert row["public_direct_or_claim_safe_binding_kcal_ready"] is False
    assert row["rejection_reason"] == "activity_proxy_conflict_requires_exact_human_nr1i2_pxr_resolution"
