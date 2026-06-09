from tools.product.build_aqp1_direct_binding_external_evidence_supplement_example import build_payload


def test_supplement_example_marks_illustrative_bacopaside_row() -> None:
    payload = build_payload(
        {
            "rows": [
                {
                    "review_row_id": "aqp1_external_direct_binding_core_binder_01",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                    "functional_surrogate_kcal_mol": "-6.47",
                    "replacement_reference_binding_kcal_mol": "KEEP_BLOCKED",
                    "review_decision": "KEEP_BLOCKED",
                    "operator_claim_safe_decision": "OPERATOR_FILL_APPROVE_CLAIM_SAFE_OR_KEEP_BLOCKED",
                }
            ]
        }
    )
    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "aqp1_direct_binding_external_evidence_supplement_example_ready"
    assert row["operator_claim_safe_decision"] == "APPROVE_CLAIM_SAFE"
    assert row["replacement_reference_binding_kcal_mol"] == "-8.19"
    assert row["reviewer_notes"].startswith("EXAMPLE_ILLUSTRATIVE_ONLY")


def test_supplement_example_keeps_chembl20_blocked() -> None:
    payload = build_payload(
        {
            "rows": [
                {
                    "review_row_id": "aqp1_operator_validation_chembl20_acetazolamide",
                    "review_decision": "KEEP_BLOCKED",
                    "operator_claim_safe_decision": "KEEP_BLOCKED",
                    "replacement_reference_binding_kcal_mol": "KEEP_BLOCKED",
                }
            ]
        }
    )
    row = payload["rows"][0]
    assert row["review_decision"] == "KEEP_BLOCKED"
    assert "EXAMPLE_ILLUSTRATIVE_ONLY" in row["reviewer_notes"]
