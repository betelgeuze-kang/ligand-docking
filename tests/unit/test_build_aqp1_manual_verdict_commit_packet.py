from __future__ import annotations

from tools import build_aqp1_manual_verdict_commit_packet as mod


def test_build_aqp1_manual_verdict_commit_packet() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "workbench_section": "binder_first_wave",
                    "packet_step": "core_binder_01",
                    "current_focus": "Confirm review-only hold.",
                }
            ]
        },
        {
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                }
            ]
        },
        {
            "rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "source_anchor": "PMID 27474162",
                    "current_focus": "Confirm review-only hold.",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "medium",
                    "suggested_manual_decision_note": "Suggested hold note",
                    "manual_decision_note_template": "Manual review note template",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
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
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "review_focus": "Confirm review-only hold.",
                }
            ]
        },
    )

    assert payload["summary"]["target_id"] == "AQP1"
    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["commit_ready_count"] == 1
    assert payload["summary"]["manual_fields_committed_count"] == 0
    assert payload["summary"]["authoritative_commit_allowed"] is False
    assert payload["summary"]["stop_condition_count"] == 1
    assert payload["rows"][0]["commit_field_verdict"] == "manual_verdict_update"
    assert payload["rows"][0]["commit_value_verdict"] == "keep_review_only"
    assert payload["rows"][0]["authoritative_commit_allowed"] == "no"
