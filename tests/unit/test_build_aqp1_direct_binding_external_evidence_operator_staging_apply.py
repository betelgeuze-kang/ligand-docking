from __future__ import annotations

from tools.product.build_aqp1_direct_binding_external_evidence_operator_staging_apply import (
    EXAMPLE_NOTE_PREFIX,
    _live_apply_rows,
    build_payload,
)


def _row(**overrides: str) -> dict[str, str]:
    base = {
        "review_row_id": "aqp1_external_direct_binding_core_binder_01",
        "packet_step": "core_binder_01",
        "operator_claim_safe_decision": "APPROVE_CLAIM_SAFE",
        "replacement_reference_binding_kcal_mol": "-8.19",
        "source_locator_or_raw_report": "https://doi.org/10.1000/verified",
        "reviewer_notes": "verified primary source",
        "target_match_confirmed": "true",
        "assay_is_direct_binding": "true",
        "data_validity_accepted": "true",
        "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
        "standard_value_nM": "1200",
        "direct_binding_method": "SPR",
        "standard_type": "Kd",
    }
    base.update(overrides)
    return base


def test_live_apply_rows_exclude_example_markers() -> None:
    rows = _live_apply_rows(
        [
            _row(),
            _row(reviewer_notes=f"{EXAMPLE_NOTE_PREFIX}: do not copy"),
        ]
    )
    assert len(rows) == 1


def test_live_apply_payload_ready_without_example_markers() -> None:
    payload = build_payload(
        staging_rows=[_row()],
        live_supplement_rows=[],
        procurement_packet={},
        operator_candidate_packet={},
        functional_packet={},
        staging_csv="runs/staging.csv",
        live_supplement_csv="runs/live.csv",
        mode="live_apply",
    )
    assert payload["summary"]["live_apply_allowed"] is True
    assert payload["summary"]["status"] == "aqp1_operator_staging_apply_ready_for_live_copy"
