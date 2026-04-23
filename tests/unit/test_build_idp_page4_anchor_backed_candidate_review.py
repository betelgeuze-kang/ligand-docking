from __future__ import annotations

from tools import build_idp_page4_anchor_backed_candidate_review as mod


def test_build_idp_page4_anchor_backed_candidate_review() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "construct_confirmation_status": "construct_citation_confirmed",
                "draft_followup_note_count": 2,
            }
        },
        {
            "summary": {
                "source_anchor": "PMID 26242913",
            }
        },
        {
            "summary": {
                "source_anchor": "PMID 28289210",
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "page4_anchor_backed_candidate_review_packet_ready"
    assert s["draft_note_count"] == 2
    assert s["review_item_count"] == 3
    assert s["review_decision_ready"] is True
    assert s["anchor_backed_candidate_ready_now"] is False
    assert "decide" in s["next_required_step"].lower()
    assert payload["rows"][1]["review_item"] == "ph_low_draft_note"
    assert payload["rows"][2]["source_anchor"] == "PMID 28289210"
