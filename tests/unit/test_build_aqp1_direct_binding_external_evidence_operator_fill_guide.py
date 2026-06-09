from __future__ import annotations

from tools.product.build_aqp1_direct_binding_external_evidence_operator_fill_guide import build_payload


def test_aqp1_external_evidence_operator_fill_guide_includes_primary_and_chembl_rows() -> None:
    payload = build_payload(
        procurement_packet={
            "summary": {
                "external_primary_evidence_required": True,
                "direct_binding_gap_open": True,
                "first_required_external_action_id": "procure_aqp1_bacopaside_ii_direct_binding_measurement",
            },
            "rows": [
                {"action_id": "procure_aqp1_bacopaside_ii_direct_binding_measurement", "ligand_identity": "bacopaside II"},
                {"action_id": "reject_current_chembl20_candidate_for_claim_safe_apply", "ligand_identity": "acetazolamide"},
                {"action_id": "or_curate_claim_safe_replacement_aqp1_blocker"},
            ],
        },
        operator_candidate_packet={
            "rows": [
                {
                    "candidate_ligand_external_identifier": "CHEMBL20",
                    "candidate_standard_type": "Kd",
                    "candidate_standard_value_nM": "174000.0",
                    "candidate_source_locator": "https://example.test/chembl20",
                }
            ]
        },
        functional_packet={
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                    "functional_delta_g_surrogate_kcal_mol": "-6.47",
                }
            ]
        },
    )
    summary = payload["summary"]
    assert summary["status"] == "aqp1_direct_binding_external_evidence_operator_fill_guide_ready"
    assert summary["operator_fill_row_count"] == 3
    row_ids = {row["review_row_id"] for row in payload["rows"]}
    assert "aqp1_external_direct_binding_core_binder_01" in row_ids
    assert "aqp1_operator_validation_chembl20_acetazolamide" in row_ids
    assert all(row["replacement_reference_binding_kcal_mol"] == "KEEP_BLOCKED" for row in payload["rows"])
