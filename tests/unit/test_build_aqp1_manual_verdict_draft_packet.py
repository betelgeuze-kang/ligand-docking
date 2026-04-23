from __future__ import annotations

from tools import build_aqp1_manual_verdict_draft_packet as mod


def test_build_aqp1_manual_verdict_draft_packet() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "workbench_section": "binder_first_wave",
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "label": "bacopaside II",
                    "current_focus": "Confirm review-only hold.",
                    "draft_manual_verdict_update": "keep_review_only",
                    "draft_manual_confidence_update": "medium",
                    "anchor": "PMID 27474162",
                    "next_action": "manual_curated_search_or_defer",
                    "blocker_or_constraint": "no_local_aqp1_binder_evidence_curated",
                }
            ]
        },
        {
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "source_anchor": "PMID 27474162",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "medium",
                    "suggested_manual_decision_note": "Suggested hold note",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                    "caution": "functional only",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "confirm_fields": "manual_verdict_update, manual_confidence_update, manual_decision_note",
                    "review_focus": "Confirm review-only hold.",
                    "caution": "functional only",
                }
            ]
        },
        {
            "rows": [
                {
                    "target_id": "AQP1",
                    "packet_step": "core_binder_01",
                    "manual_decision_note_template": "Manual review note template",
                }
            ]
        },
    )

    assert payload["summary"]["target_id"] == "AQP1"
    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["suggested_prefill_count"] == 1
    assert payload["summary"]["note_template_count"] == 1
    assert payload["summary"]["manual_fields_committed_count"] == 0
    assert payload["summary"]["ready_for_reviewer_copy_count"] == 1
    assert payload["summary"]["authoritative_apply_allowed"] is False
    assert payload["rows"][0]["candidate_name"] == "bacopaside II"
    assert payload["rows"][0]["manual_fields_committed"] == "no"
