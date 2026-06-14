from tools.product.build_aqp1_direct_binding_external_evidence_intake import build_payload


def test_aqp1_external_evidence_intake_marks_placeholder_rows_pending() -> None:
    payload = build_payload(
        [
            {
                "review_row_id": "aqp1_external_direct_binding_core_binder_01",
                "packet_step": "core_binder_01",
                "target_uniprot": "P29972",
                "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                "replacement_reference_binding_kcal_mol": "KEEP_BLOCKED",
                "source_locator_or_raw_report": "OPERATOR_FILL_PMID_DOI_or_primary_report",
                "standard_value_nM": "OPERATOR_FILL_numeric",
                "operator_claim_safe_decision": "OPERATOR_FILL_APPROVE_CLAIM_SAFE_OR_KEEP_BLOCKED",
                "review_decision": "KEEP_BLOCKED",
                "target_match_confirmed": "false",
                "assay_is_direct_binding": "false",
                "data_validity_accepted": "false",
            }
        ]
    )
    summary = payload["summary"]
    assert summary["status"] == "aqp1_direct_binding_external_evidence_intake_ready"
    assert summary["claim_safe_approved_count"] == 0
    assert summary["operator_fill_pending_count"] == 1
    assert summary["workbook_overlay_row_count"] == 0
    assert summary["direct_binding_gap_open"] is True
    assert summary["transporter_direct_binding_evidence_ready"] is False
    assert summary["primary_source_direct_binding_evidence_ready"] is False
    assert summary["claim_safe_direct_binding_kcal_ready"] is False
    assert summary["claim_safe_direct_binding_row_count"] == 0
    assert summary["primary_source_verified_count"] == 0
    assert summary["functional_surrogate_promoted_to_kcal"] is False


def test_aqp1_external_evidence_intake_collects_claim_safe_overlay() -> None:
    payload = build_payload(
        [
            {
                "review_row_id": "aqp1_external_direct_binding_core_binder_01",
                "packet_step": "core_binder_01",
                "target_uniprot": "P29972",
                "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                "replacement_reference_binding_kcal_mol": "-8.2",
                "direct_binding_method": "SPR",
                "standard_type": "Kd",
                "standard_value_nM": "1200",
                "source_locator_or_raw_report": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                "operator_claim_safe_decision": "APPROVE_CLAIM_SAFE",
                "review_decision": "APPROVE",
                "target_match_confirmed": "true",
                "assay_is_direct_binding": "true",
                "data_validity_accepted": "true",
            }
        ]
    )
    summary = payload["summary"]
    assert summary["claim_safe_approved_count"] == 1
    assert summary["claim_safe_direct_binding_row_count"] == 1
    assert summary["primary_source_verified_count"] == 1
    assert summary["standard_type_kd_ki_row_count"] == 1
    assert summary["exact_direct_binding_value_row_count"] == 1
    assert summary["product_scope_evidence_status"] == "product_scope_transporter_direct_binding_evidence_ready"
    assert summary["transporter_direct_binding_evidence_ready"] is True
    assert summary["primary_source_direct_binding_evidence_ready"] is True
    assert summary["claim_safe_direct_binding_kcal_ready"] is True
    assert summary["workbook_overlay_row_count"] == 1
    assert payload["workbook_overlay_rows"][0]["replacement_reference_binding_kcal_mol"] == "-8.2"
    assert summary["direct_binding_gap_open"] is False
    assert summary["source_locator_invalid_count"] == 0


def test_aqp1_external_evidence_intake_rejects_example_or_nonprimary_source() -> None:
    payload = build_payload(
        [
            {
                "review_row_id": "aqp1_external_direct_binding_core_binder_01",
                "packet_step": "core_binder_01",
                "target_uniprot": "P29972",
                "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                "replacement_reference_binding_kcal_mol": "-8.2",
                "direct_binding_method": "SPR",
                "standard_type": "Kd",
                "standard_value_nM": "1200",
                "source_locator_or_raw_report": "https://pubmed.ncbi.nlm.nih.gov/EXAMPLE_REPLACE_WITH_PRIMARY_PMID/",
                "operator_claim_safe_decision": "APPROVE_CLAIM_SAFE",
                "review_decision": "APPROVE",
                "target_match_confirmed": "true",
                "assay_is_direct_binding": "true",
                "data_validity_accepted": "true",
            }
        ]
    )
    summary = payload["summary"]
    assert summary["status"] == "blocked_aqp1_direct_binding_external_evidence_intake"
    assert summary["claim_safe_approved_count"] == 0
    assert summary["transporter_direct_binding_evidence_ready"] is False
    assert summary["source_locator_invalid_count"] == 1
    assert summary["validation_error_count"] == 1
    assert "APPROVE_CLAIM_SAFE requires PMID/DOI/internal primary-source locator" in payload[
        "validation_errors"
    ][0]
