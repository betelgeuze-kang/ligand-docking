from __future__ import annotations

from tools.product import build_aqp1_manual_verdict_handoff_packet as mod


def test_build_aqp1_manual_verdict_handoff_packet() -> None:
    payload = mod.build_payload(
        {
            "target_rows": [
                {
                    "target_id": "AQP1",
                    "local_evidence_status": "draft_only_local_evidence_blocked",
                    "binder_pending_manual_verdict_count": 3,
                    "placeholder_rows": 6,
                    "p0_todo_count": 5,
                    "next_required_step": "Keep blocked until review is complete.",
                }
            ]
        },
        {
            "summary": {
                "endpoint_status": "draft_only_local_evidence_blocked",
                "temporary_fit_donor_target": "EGFR_KINASE",
            }
        },
        {
            "rows": [
                {
                    "candidate_name": "bacopaside II",
                    "mechanism_bucket": "functional_aqp1_water_channel_inhibitor",
                    "assay_surface": "Xenopus assay",
                    "confidence": "medium",
                    "potency_or_signal": "IC50 18 uM",
                },
                {
                    "candidate_name": "tetraethylammonium",
                    "mechanism_bucket": "tool",
                    "assay_surface": "native assay",
                    "confidence": "low",
                    "potency_or_signal": "1-10 mM",
                },
            ]
        },
        {
            "rows": [
                {
                    "candidate_name": "bacopaside II",
                    "proposed_packet_step": "core_binder_01",
                    "review_bucket": "review_only_first_wave",
                    "recommended_verdict": "keep_review_only",
                    "source_anchor": "PMID 27474162",
                    "promotion_policy": "draft_first_wave_manual_review",
                    "caution": "functional only",
                },
                {
                    "candidate_name": "tetraethylammonium",
                    "proposed_packet_step": "caution_only",
                    "review_bucket": "review_only_tool_reference",
                    "recommended_verdict": "caution_only",
                    "source_anchor": "BMC Physiol 2002",
                    "promotion_policy": "caution_only_not_for_authoritative_apply",
                    "caution": "tool only",
                },
            ]
        },
        {
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "source_anchor": "PMID 27474162",
                    "current_review_bucket": "review_only_first_wave",
                    "current_recommended_verdict": "keep_review_only",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                    "evidence_strength": "medium",
                    "potency_or_signal": "IC50 18 uM",
                    "next_required_action": "manual_curated_search_or_defer",
                    "caution": "functional only",
                }
            ]
        },
        {
            "rows": [
                {
                    "candidate_name": "bacopaside II",
                    "draft_manual_verdict_update": "keep_review_only",
                    "draft_manual_confidence_update": "medium",
                    "reviewer_checklist": "confirm_anchor_scope;confirm_review_only_hold;record_manual_note",
                }
            ]
        },
        {
            "rows": [
                {
                    "priority_rank": 1,
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "aqp1_placeholder_binder_01",
                    "review_bucket": "defer_pending_target_specific_evidence",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                    "notes": "binder blocked",
                },
                {
                    "priority_rank": 4,
                    "packet_step": "core_non_binder_01",
                    "current_ligand_id": "aqp1_placeholder_nonbinder_01",
                    "review_bucket": "review_only_negative_evidence",
                    "promotion_blocker": "no_quantitative_transporter_negative_evidence_curated",
                    "next_required_action": "manual_negative_evidence_review",
                    "notes": "negative blocked",
                },
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "next_action": "review_primary_source_and_decide_keep_review_only_or_defer",
                },
                {
                    "packet_step": "caution_only",
                    "next_action": "review_primary_source_and_decide_keep_review_only_or_defer",
                },
            ]
        },
    )

    assert payload["summary"]["target_id"] == "AQP1"
    assert payload["summary"]["authoritative_apply_allowed"] is False
    assert payload["summary"]["binder_first_wave_count"] == 1
    assert payload["summary"]["caution_or_defer_reference_count"] == 1
    assert payload["summary"]["negative_slot_policy_count"] == 1
    assert len(payload["checklist"]) == 4
    assert payload["rows"][0]["section"] == "binder_first_wave"
    assert payload["rows"][0]["draft_manual_verdict_update"] == "keep_review_only"
    assert payload["rows"][1]["section"] == "caution_or_defer_reference"
    assert payload["rows"][2]["section"] == "negative_slot_policy"
