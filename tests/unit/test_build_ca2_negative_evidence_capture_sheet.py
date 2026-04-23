from __future__ import annotations

from tools import build_ca2_negative_evidence_capture_sheet as mod


def test_build_ca2_negative_evidence_capture_sheet_promotes_no_direct_source_row_with_overlay() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_02",
                    "ligand": "metformin",
                    "review_phase": "today_focus",
                    "staged_assay_type_honesty": "no_quantitative_nonbinder_value_curated",
                    "staged_promotion_blocker": "no_direct_ca2_negative_evidence_located_after_research",
                    "staged_next_required_action": "keep_review_only_no_direct_negative_source",
                    "staged_recommended_resolution": "keep_review_only_until_direct_ca2_negative_evidence_is_curated",
                    "draft_manual_decision_note": "old note",
                    "commit_status": "confirmed_review_only",
                }
            ]
        },
        {"rows": []},
        existing_sheet={
            "core_non_binder_02": {
                "packet_step": "core_non_binder_02",
                "capture_status": "captured_no_direct_negative_source_found",
                "manual_promotion_blocker": "no_direct_ca2_negative_evidence_located_after_research",
                "source_title": "Old source",
                "source_url": "https://example.org/old",
            }
        },
        overlay_payload={
            "rows": [
                {
                    "packet_step": "core_non_binder_02",
                    "capture_status": "captured_direct_negative_review_only",
                    "supports_direct_ca2_negative": "yes",
                    "evidence_scope": "target_specific_direct_negative_upper_bound",
                    "assay_context": "direct_ca2_enzyme_inhibition_upper_bound",
                    "source_title": "ChEMBL direct negative-like evidence",
                    "source_id": "CHEMBL1909123",
                    "source_url": "https://example.org/chembl",
                    "manual_review_bucket": "standard_review",
                    "manual_assay_type_honesty": "direct_ca2_negative_like_upper_bound_review_only",
                    "manual_promotion_blocker": "direct_ca2_negative_evidence_curated_review_only",
                    "manual_next_required_action": "apply_direct_negative_evidence_review_only",
                    "manual_recommended_resolution": "keep_review_only_with_direct_ca2_negative_evidence",
                    "manual_decision_note": "new note",
                    "commit_status": "confirmed_review_only",
                }
            ]
        },
    )

    row = payload["rows"][0]
    assert row["capture_status"] == "captured_direct_negative_review_only"
    assert row["supports_direct_ca2_negative"] == "yes"
    assert row["source_title"] == "ChEMBL direct negative-like evidence"
    assert row["manual_promotion_blocker"] == "direct_ca2_negative_evidence_curated_review_only"
    assert payload["summary"]["direct_negative_evidence_count"] == 1
    assert payload["summary"]["no_direct_negative_found_count"] == 0


def test_build_ca2_negative_evidence_capture_sheet_preserves_existing_direct_negative_row_when_commit_packet_omits_it() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "ligand": "acetaminophen",
                    "review_phase": "today_focus",
                    "staged_assay_type_honesty": "direct_ca2_inhibitor_conflict_present",
                    "staged_promotion_blocker": "direct_ca2_inhibitor_conflict_present",
                    "staged_next_required_action": "keep_review_only_conflict",
                    "staged_recommended_resolution": "keep_review_only_conflict",
                    "draft_manual_decision_note": "conflict",
                    "commit_status": "confirmed_review_only",
                }
            ]
        },
        {"rows": []},
        existing_sheet={
            "core_non_binder_02": {
                "capture_rank": "2",
                "packet_step": "core_non_binder_02",
                "ligand": "metformin",
                "review_phase": "today_focus",
                "capture_status": "captured_direct_negative_review_only",
                "supports_direct_ca2_negative": "yes",
                "evidence_scope": "target_specific_direct_negative_upper_bound",
                "assay_context": "direct_ca2_enzyme_inhibition_upper_bound",
                "source_title": "ChEMBL direct negative-like evidence",
                "source_id": "CHEMBL1909123",
                "source_url": "https://example.org/chembl",
                "manual_review_bucket": "standard_review",
                "manual_assay_type_honesty": "direct_ca2_negative_like_upper_bound_review_only",
                "manual_promotion_blocker": "direct_ca2_negative_evidence_curated_review_only",
                "manual_next_required_action": "apply_direct_negative_evidence_review_only",
                "manual_recommended_resolution": "keep_review_only_with_direct_ca2_negative_evidence",
                "manual_decision_note": "new note",
                "commit_status": "confirmed_review_only",
                "current_missing_fields": "replacement_reference_binding_kcal_mol",
                "must_remain_blank_fields": "replacement_reference_binding_kcal_mol",
                "review_reason": "direct negative evidence preserved",
                "operator_note_template": "review metformin",
            }
        },
    )

    rows_by_step = {row["packet_step"]: row for row in payload["rows"]}
    assert "core_non_binder_02" in rows_by_step
    metformin_row = rows_by_step["core_non_binder_02"]
    assert metformin_row["ligand"] == "metformin"
    assert metformin_row["capture_status"] == "captured_direct_negative_review_only"
    assert metformin_row["supports_direct_ca2_negative"] == "yes"
    assert metformin_row["source_title"] == "ChEMBL direct negative-like evidence"
    assert payload["summary"]["capture_row_count"] == 2
    assert payload["summary"]["direct_negative_evidence_count"] == 1


def test_build_ca2_negative_evidence_capture_sheet_rehydrates_verified_direct_negative_row_from_binding_sheet() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "ligand": "acetaminophen",
                    "review_phase": "today_focus",
                    "staged_assay_type_honesty": "direct_ca2_inhibitor_conflict_present",
                    "staged_promotion_blocker": "direct_ca2_inhibitor_conflict_present",
                    "staged_next_required_action": "keep_review_only_conflict",
                    "staged_recommended_resolution": "keep_review_only_conflict",
                    "draft_manual_decision_note": "conflict",
                    "commit_status": "confirmed_review_only",
                }
            ]
        },
        {"rows": []},
        verification_sheet_payload={
            "sheet_rows": [
                {
                    "packet_step": "core_non_binder_02",
                    "replacement_ligand_id": "metformin",
                    "verify_provenance_source": "ca2_direct_negative_evidence::CHEMBL1909123::target_specific_direct_negative_upper_bound::direct_ca2_enzyme_inhibition_upper_bound",
                    "verify_source_url": "https://example.org/chembl",
                    "verification_status": "verified_direct_negative_evidence_review_only",
                    "notes": "Direct negative evidence was already captured.",
                }
            ]
        },
    )

    rows_by_step = {row["packet_step"]: row for row in payload["rows"]}
    assert "core_non_binder_02" in rows_by_step
    metformin_row = rows_by_step["core_non_binder_02"]
    assert metformin_row["ligand"] == "metformin"
    assert metformin_row["review_phase"] == "today_focus"
    assert metformin_row["capture_status"] == "captured_direct_negative_review_only"
    assert metformin_row["supports_direct_ca2_negative"] == "yes"
    assert metformin_row["source_id"] == "CHEMBL1909123"
    assert metformin_row["source_url"] == "https://example.org/chembl"
    assert payload["summary"]["capture_row_count"] == 2
    assert payload["summary"]["direct_negative_evidence_count"] == 1
