from __future__ import annotations

from tools.product.build_aqp1_direct_binding_external_evidence_operator_worksheet import build_payload


def test_aqp1_operator_worksheet_flags_pending_fields_from_live_supplement() -> None:
    payload = build_payload(
        procurement_packet={
            "summary": {
                "external_primary_evidence_required": True,
                "direct_binding_gap_open": True,
                "first_required_external_action_id": "procure_aqp1_bacopaside_ii_direct_binding_measurement",
            },
            "rows": [
                {"action_id": "procure_aqp1_bacopaside_ii_direct_binding_measurement", "ligand_identity": "bacopaside II"},
            ],
        },
        operator_candidate_packet={"rows": []},
        functional_packet={
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                    "functional_delta_g_surrogate_kcal_mol": "-6.47",
                }
            ]
        },
        supplement_rows=[
            {
                "review_row_id": "aqp1_external_direct_binding_core_binder_01",
                "packet_step": "core_binder_01",
                "target_id": "AQP1",
                "target_uniprot": "P29972",
                "candidate_name": "bacopaside II",
                "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                "required_evidence_mode": "exact_human_aqp1_direct_binding_kd_or_ki",
                "functional_surrogate_kcal_mol": "-6.47",
                "replacement_reference_binding_kcal_mol": "KEEP_BLOCKED",
                "direct_binding_method": "OPERATOR_FILL_SPR_ITC_MST_or_validated_competition_Ki",
                "standard_type": "OPERATOR_FILL_Kd_or_Ki",
                "standard_value_nM": "OPERATOR_FILL_numeric",
                "source_locator_or_raw_report": "OPERATOR_FILL_PMID_DOI_or_primary_report",
                "target_match_confirmed": "false",
                "assay_is_direct_binding": "false",
                "data_validity_accepted": "false",
                "operator_claim_safe_decision": "OPERATOR_FILL_APPROVE_CLAIM_SAFE_OR_KEEP_BLOCKED",
                "review_decision": "KEEP_BLOCKED",
                "authoritative_apply_requested": "false",
                "reviewer_notes": "pending",
            }
        ],
    )
    summary = payload["summary"]
    assert summary["status"] == "aqp1_direct_binding_external_evidence_operator_worksheet_ready"
    assert summary["live_supplement_row_count"] == 1
    assert summary["operator_fill_pending_field_count"] > 0
    assert summary["claim_safe_approved_count"] == 0
    pending = [row for row in payload["rows"] if row["field_status"] == "operator_fill_pending"]
    assert any(row["field_name"] == "replacement_reference_binding_kcal_mol" for row in pending)
