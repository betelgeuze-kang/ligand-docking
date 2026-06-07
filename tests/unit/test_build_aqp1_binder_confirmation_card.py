from __future__ import annotations

from tools.product import build_aqp1_binder_confirmation_card as mod


def test_build_aqp1_binder_confirmation_card() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "source_anchor": "PMID 27474162",
                    "review_focus": "Confirm evidence.",
                    "commit_value_verdict": "keep_review_only",
                    "commit_value_confidence": "medium",
                    "commit_value_note": "note a",
                    "stop_condition": "no_local_aqp1_binder_evidence_curated",
                    "stop_reason": "stop a",
                }
            ]
        },
        {
            "sheet_rows": [
                {
                    "packet_step": "core_binder_01",
                    "manual_verdict_update": "",
                    "manual_confidence_update": "",
                    "manual_decision_note": "",
                }
            ]
        },
    )

    assert payload["summary"]["target_id"] == "AQP1"
    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["pending_manual_verdict_count"] == 1
    assert payload["rows"][0]["candidate_name"] == "bacopaside II"
    assert payload["rows"][0]["update_sheet_row_ref"] == "core_binder_01"
    assert payload["rows"][0]["source_anchor_short"] == "PMID 27474162"
    assert payload["rows"][0]["commit_value_note_short"] == "note a"
    assert payload["rows"][0]["confirm_fields"] == "manual_verdict_update,manual_confidence_update,manual_decision_note"
