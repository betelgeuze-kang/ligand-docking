from __future__ import annotations

from tools.product.build_aqp1_direct_binding_live_supplement_blank import build_payload


def test_aqp1_live_supplement_blank_emits_checklist_without_illustrative_kcal() -> None:
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
    )
    summary = payload["summary"]
    assert summary["status"] == "aqp1_direct_binding_live_supplement_blank_ready"
    assert summary["blank_row_count"] == 1
    assert summary["operator_fill_pending_field_count"] > 0
    bacopaside = next(
        row for row in payload["blank_rows"] if row["review_row_id"] == "aqp1_external_direct_binding_core_binder_01"
    )
    assert bacopaside["replacement_reference_binding_kcal_mol"] == "KEEP_BLOCKED"
    assert bacopaside["functional_surrogate_kcal_mol"] == "-6.47"
    assert any(row["field_name"] == "replacement_reference_binding_kcal_mol" for row in payload["field_checklist_rows"])
