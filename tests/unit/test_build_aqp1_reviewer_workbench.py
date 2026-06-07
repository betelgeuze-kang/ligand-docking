from __future__ import annotations

from tools.product import build_aqp1_reviewer_workbench as mod


def test_build_aqp1_reviewer_workbench() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "target_id": "AQP1",
                "endpoint_status": "draft_only_local_evidence_blocked",
                "binder_first_wave_count": 1,
                "pending_manual_verdict_count": 1,
            },
            "rows": [
                {
                    "section": "binder_first_wave",
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "recommended_verdict": "keep_review_only",
                    "draft_manual_verdict_update": "keep_review_only",
                    "anchor": "PMID 27474162",
                    "assay_surface": "Xenopus assay",
                    "next_action": "review_primary_source_and_decide_keep_review_only_or_defer",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                }
            ],
        },
        {
            "summary": {
                "negative_slot_count": 1,
                "caution_or_defer_reference_count": 1,
            },
            "rows": [
                {
                    "section": "negative_slot_policy",
                    "priority_rank": "4",
                    "packet_step": "core_non_binder_01",
                    "label": "aqp1_placeholder_nonbinder_01",
                    "recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
                    "next_action": "manual_negative_evidence_review",
                    "promotion_blocker": "no_quantitative_transporter_negative_evidence_curated",
                },
                {
                    "section": "caution_or_defer_signal",
                    "priority_rank": "1",
                    "packet_step": "caution_only",
                    "label": "tetraethylammonium",
                    "recommended_resolution": "caution_only",
                    "next_action": "review_primary_source_and_keep_out_of_negative_packet_rows",
                    "promotion_blocker": "caution_only_not_for_authoritative_apply",
                },
            ],
        },
        {
            "summary": {
                "draft_prefill_count": 1,
                "exact_human_provenance_count": 1,
            },
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "draft_manual_verdict_update": "keep_review_only",
                    "draft_manual_confidence_update": "medium",
                    "public_provenance_status": "exact_human_aqp1_quantitative_activity_present_nonbinding",
                    "public_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
                }
            ],
        },
        {
            "summary": {
                "ready_for_reviewer_fill_count": 1,
            },
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "review_focus": "Confirm the exact human AQP1 target-activity provenance is recorded correctly.",
                    "public_provenance_status": "exact_human_aqp1_quantitative_activity_present_nonbinding",
                }
            ],
        },
        {"summary": {"direct_quantitative_binding_candidate_count": 0}},
        {
            "summary": {
                "evidence_mode": "functional_potency_staged_review_only",
                "quantitative_binding_status": "quantitative_binding_absent_claim_safe_kcal_missing",
                "remaining_unresolved_fields": "replacement_reference_binding_kcal_mol",
                "remaining_unresolved_field_count": 1,
            }
        },
        {"summary": {}},
    )

    assert payload["summary"]["target_id"] == "AQP1"
    assert payload["summary"]["authoritative_apply_allowed"] is False
    assert payload["summary"]["binder_first_wave_count"] == 1
    assert payload["summary"]["negative_slot_count"] == 1
    assert payload["summary"]["caution_or_defer_reference_count"] == 1
    assert payload["summary"]["draft_prefill_count"] == 1
    assert payload["summary"]["exact_human_provenance_count"] == 1
    assert payload["rows"][0]["workbench_section"] == "binder_first_wave"
    assert payload["rows"][0]["public_provenance_status"] == "exact_human_aqp1_quantitative_activity_present_nonbinding"
    assert "keep replacement_reference_binding_kcal_mol blank" in payload["rows"][0]["current_focus"]
    assert payload["rows"][1]["workbench_section"] == "negative_slot_policy"
    assert payload["rows"][2]["workbench_section"] == "caution_or_defer_signal"
    assert len(payload["checklist"]) == 4
