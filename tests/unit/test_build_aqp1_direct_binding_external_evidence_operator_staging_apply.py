from __future__ import annotations

from tools.product.build_aqp1_direct_binding_external_evidence_operator_staging_apply import (
    EXAMPLE_NOTE_PREFIX,
    build_payload,
)


def _staging_row(**overrides: str) -> dict[str, str]:
    row = {
        "review_row_id": "aqp1_external_direct_binding_core_binder_01",
        "packet_step": "core_binder_01",
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "candidate_name": "bacopaside II",
        "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
        "replacement_reference_binding_kcal_mol": "-8.19",
        "direct_binding_method": "SPR",
        "standard_type": "Kd",
        "standard_value_nM": "1200",
        "source_locator_or_raw_report": "https://doi.org/10.1000/example",
        "target_match_confirmed": "true",
        "assay_is_direct_binding": "true",
        "data_validity_accepted": "true",
        "operator_claim_safe_decision": "APPROVE_CLAIM_SAFE",
        "review_decision": "APPROVE",
        "authoritative_apply_requested": "true",
        "reviewer_notes": f"{EXAMPLE_NOTE_PREFIX}: illustrative only",
    }
    row.update(overrides)
    return row


def test_staging_rehearsal_allows_example_markers() -> None:
    payload = build_payload(
        staging_rows=[_staging_row()],
        live_supplement_rows=[],
        procurement_packet={},
        operator_candidate_packet={},
        functional_packet={},
        staging_csv="runs/example.csv",
        live_supplement_csv="runs/live.csv",
        mode="rehearsal",
    )
    assert payload["summary"]["status"] == "aqp1_operator_staging_rehearsal_green"
    assert payload["summary"]["staging_claim_safe_approved_count"] == 1
    assert payload["summary"]["live_apply_allowed"] is False


def test_live_apply_blocks_example_markers() -> None:
    payload = build_payload(
        staging_rows=[_staging_row()],
        live_supplement_rows=[],
        procurement_packet={},
        operator_candidate_packet={},
        functional_packet={},
        staging_csv="runs/example.csv",
        live_supplement_csv="runs/live.csv",
        mode="live_apply",
    )
    assert payload["summary"]["status"] == "blocked_aqp1_operator_staging_apply"
    assert payload["summary"]["live_apply_allowed"] is False
    assert any("EXAMPLE" in err for err in payload["validation_errors"])
