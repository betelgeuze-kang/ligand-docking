from __future__ import annotations

from tools.product.build_ca2_next_verification_slice import build_payload


def test_build_ca2_next_verification_slice_selects_core_rows_after_verified_top3() -> None:
    rows = [
        {
            "priority_rank": "1",
            "packet": "core",
            "packet_step": "core_binder_01",
            "replacement_ligand_id": "acetazolamide",
            "replacement_is_binder": "1",
            "verification_status": "verified_chembl_binding",
        },
        {
            "priority_rank": "2",
            "packet": "core",
            "packet_step": "core_binder_02",
            "replacement_ligand_id": "methazolamide",
            "replacement_is_binder": "1",
            "verification_status": "verified_chembl_binding",
        },
        {
            "priority_rank": "3",
            "packet": "core",
            "packet_step": "core_binder_03",
            "replacement_ligand_id": "ethoxzolamide",
            "replacement_is_binder": "1",
            "verification_status": "verified_chembl_binding",
        },
        {
            "priority_rank": "4",
            "packet": "core",
            "packet_step": "core_non_binder_01",
            "replacement_ligand_id": "acetaminophen",
            "replacement_is_binder": "0",
            "verification_status": "pending_binding_provenance_review",
        },
        {
            "priority_rank": "5",
            "packet": "core",
            "packet_step": "core_non_binder_02",
            "replacement_ligand_id": "metformin",
            "replacement_is_binder": "0",
            "verification_status": "pending_binding_provenance_review",
        },
        {
            "priority_rank": "6",
            "packet": "core",
            "packet_step": "core_non_binder_03",
            "replacement_ligand_id": "caffeine",
            "replacement_is_binder": "0",
            "verification_status": "pending_binding_provenance_review",
        },
        {
            "priority_rank": "7",
            "packet": "ood",
            "packet_step": "ood_binder_01",
            "replacement_ligand_id": "dorzolamide",
            "replacement_is_binder": "1",
            "verification_status": "pending_binding_provenance_review",
        },
    ]
    payload = build_payload(rows, limit=3)
    assert payload["summary"]["row_count"] == 3
    assert payload["summary"]["contains_only_core_rows"] is True
    assert [row["packet_step"] for row in payload["rows"]] == [
        "core_non_binder_01",
        "core_non_binder_02",
        "core_non_binder_03",
    ]
    assert payload["rows"][0]["assay_type_honesty"] == "review_only_negative_conflict_with_weak_activity"
    assert payload["rows"][0]["next_required_action"] == "manual_negative_evidence_review"
