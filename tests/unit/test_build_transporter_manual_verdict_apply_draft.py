from __future__ import annotations

from tools.product import build_transporter_manual_verdict_apply_draft as mod


def test_build_transporter_manual_verdict_apply_draft() -> None:
    payload = mod.build_payload(
        {
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "source_anchor": "PMID 27474162",
                    "current_recommended_verdict": "keep_review_only",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "medium",
                    "suggested_manual_decision_note": "note a",
                    "manual_verdict_update": "",
                    "manual_confidence_update": "",
                    "manual_decision_note": "",
                    "update_status": "pending_manual_verdict",
                }
            ]
        },
        {
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "source_anchor": "PMID 27078104",
                    "current_recommended_verdict": "keep_review_only",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "strong_structural",
                    "suggested_manual_decision_note": "note g",
                    "manual_verdict_update": "",
                    "manual_confidence_update": "",
                    "manual_decision_note": "",
                    "update_status": "pending_manual_verdict",
                }
            ]
        },
    )

    assert payload["summary"]["target_count"] == 2
    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["draft_ready_count"] == 2
    assert payload["summary"]["manual_verdict_filled_count"] == 0
    assert payload["rows"][0]["draft_manual_verdict_update"] == "keep_review_only"
    assert payload["rows"][1]["draft_manual_confidence_update"] == "strong_structural"
