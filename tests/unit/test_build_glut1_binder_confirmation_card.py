from __future__ import annotations

from tools import build_glut1_binder_confirmation_card as mod


def test_build_glut1_binder_confirmation_card() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "priority_rank": 1,
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "source_anchor": "PMID 27078104",
                    "confirm_fields": "manual_verdict_update,manual_confidence_update,manual_decision_note",
                    "staged_manual_verdict": "keep_review_only",
                    "staged_manual_confidence_update": "strong_structural",
                    "staged_manual_decision_note": "note g",
                    "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                    "update_status": "pending_manual_verdict",
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

    assert payload["summary"]["target_id"] == "GLUT1"
    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["pending_manual_verdict_count"] == 1
    assert payload["rows"][0]["candidate_name"] == "cytochalasin B"
    assert payload["rows"][0]["update_sheet_row_ref"] == "core_binder_01"
    assert payload["rows"][0]["source_anchor_short"] == "PMID 27078104"
    assert payload["rows"][0]["commit_value_note_short"] == "note g"
    assert payload["rows"][0]["stop_condition"] == "no_local_glut1_binder_evidence_curated"
    assert payload["rows"][0]["promotion_blocker"] == "no_local_glut1_binder_evidence_curated"
