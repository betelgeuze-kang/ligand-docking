from __future__ import annotations

from tools.build_family_pending_row_disposition import build_payload


def test_build_payload_ca2_keeps_remaining_negative_rows_review_only() -> None:
    rows = [
        {"priority_rank": "1", "packet": "core", "packet_step": "core_binder_01", "replacement_ligand_id": "acetazolamide", "replacement_is_binder": "1", "verification_status": "verified_chembl_binding"},
        {"priority_rank": "4", "packet": "core", "packet_step": "core_non_binder_01", "replacement_ligand_id": "acetaminophen", "replacement_is_binder": "0", "verification_status": "pending_binding_provenance_review"},
        {"priority_rank": "10", "packet": "ood", "packet_step": "ood_non_binder_01", "replacement_ligand_id": "aspirin", "replacement_is_binder": "0", "verification_status": "pending_binding_provenance_review"},
    ]
    payload = build_payload("ca2", rows)
    assert payload["summary"]["verified_rows"] == 1
    assert payload["summary"]["review_only_rows"] == 2
    assert payload["summary"]["defer_rows"] == 0
    rows_by_ligand = {row["replacement_ligand_id"]: row for row in payload["rows"]}
    assert rows_by_ligand["acetaminophen"]["disposition"] == "review_only_negative_evidence"
    assert rows_by_ligand["aspirin"]["disposition"] == "review_only_negative_evidence"


def test_build_payload_pxr_keeps_bexarotene_on_supportive_manual_confirmation_lane() -> None:
    rows = [
        {"priority_rank": "1", "packet": "core", "packet_step": "core_eval_binder_01", "replacement_ligand_id": "rifampicin", "replacement_is_binder": "1", "verification_status": "verified_chembl_activity_pending_workbook_copy"},
        {"priority_rank": "5", "packet": "core", "packet_step": "core_eval_non_binder_01", "replacement_ligand_id": "acetaminophen", "replacement_is_binder": "0", "verification_status": "pending_binding_provenance_review"},
        {"priority_rank": "10", "packet": "ood", "packet_step": "ood_fit_binder_01", "replacement_ligand_id": "bexarotene", "replacement_is_binder": "1", "verification_status": "pending_binding_provenance_review"},
        {"priority_rank": "13", "packet": "ood", "packet_step": "ood_eval_non_binder_02", "replacement_ligand_id": "ibuprofen", "replacement_is_binder": "0", "verification_status": "pending_binding_provenance_review"},
    ]
    payload = build_payload(
        "pxr",
        rows,
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "supports_local_target_specific_human_pxr": "yes",
                    "manual_promotion_blocker": "activity_present_manual_confirmation_required",
                    "manual_next_required_action": "manual_curated_search_or_defer",
                    "source_note": "PubChem human PXR qHTS proxy exists but still needs manual confirmation.",
                }
            ]
        },
    )
    assert payload["summary"]["review_only_rows"] == 1
    assert payload["summary"]["defer_rows"] == 2
    assert payload["summary"]["pending_binder_rows"] == 0
    assert "manual-confirmation lane" in payload["summary"]["next_required_step"]
    rows_by_ligand = {row["replacement_ligand_id"]: row for row in payload["rows"]}
    assert rows_by_ligand["acetaminophen"]["disposition"] == "defer_pending_target_specific_evidence"
    assert rows_by_ligand["bexarotene"]["disposition"] == "defer_pending_target_specific_evidence"
    assert rows_by_ligand["bexarotene"]["promotion_blocker"] == "activity_present_manual_confirmation_required"
    assert "manual confirmation" in rows_by_ligand["bexarotene"]["notes"].lower()
    assert rows_by_ligand["ibuprofen"]["disposition"] == "review_only_negative_evidence"


def test_build_payload_pxr_prefers_capture_sheet_manual_fields_for_non_pending_rows() -> None:
    rows = [
        {
            "priority_rank": "6",
            "packet": "core",
            "packet_step": "core_eval_non_binder_02",
            "replacement_ligand_id": "caffeine",
            "replacement_is_binder": "0",
            "verification_status": "pending_binding_provenance_review",
        }
    ]
    payload = build_payload(
        "pxr",
        rows,
        {
            "rows": [
                {
                    "packet_step": "core_eval_non_binder_02",
                    "policy_bucket": "defer",
                    "capture_status": "captured_supportive",
                    "manual_assay_type_honesty": "human_pxr_upper_bound_only_manual_review_required",
                    "manual_promotion_blocker": "upper_bound_only_manual_review_required",
                    "manual_next_required_action": "manual_negative_evidence_review",
                    "source_note": "A stronger target-specific upper-bound source exists and should drive the row now.",
                }
            ]
        },
    )
    row = payload["rows"][0]
    assert row["disposition"] == "defer_pending_target_specific_evidence"
    assert row["promotion_blocker"] == "upper_bound_only_manual_review_required"
    assert row["next_required_action"] == "manual_negative_evidence_review"
    assert "stronger target-specific upper-bound source" in row["notes"]


def test_build_payload_pxr_promotes_inactive_only_pubchem_lane_to_review_only() -> None:
    rows = [
        {
            "priority_rank": "8",
            "packet": "ood",
            "packet_step": "ood_eval_non_binder_01",
            "replacement_ligand_id": "nicotinamide",
            "replacement_is_binder": "0",
            "verification_status": "pending_binding_provenance_review",
        }
    ]
    payload = build_payload(
        "pxr",
        rows,
        {
            "rows": [
                {
                    "packet_step": "ood_eval_non_binder_01",
                    "policy_bucket": "defer",
                    "capture_status": "captured_review_only",
                    "manual_assay_type_honesty": "inactive_only_human_pxr_qhts_review_only",
                    "manual_promotion_blocker": "inactive_only_human_pxr_qhts_review_only",
                    "manual_next_required_action": "manual_negative_evidence_review",
                    "source_note": "Inactive-only human PXR qHTS rows are currently available.",
                }
            ]
        },
    )
    row = payload["rows"][0]
    assert row["disposition"] == "review_only_negative_evidence"
    assert row["promotion_blocker"] == "inactive_only_human_pxr_qhts_review_only"
    assert row["next_required_action"] == "manual_negative_evidence_review"
    assert "Inactive-only human PXR qHTS rows" in row["notes"]
