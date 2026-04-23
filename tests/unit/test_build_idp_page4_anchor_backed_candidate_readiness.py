from __future__ import annotations

from tools import build_idp_page4_anchor_backed_candidate_readiness as mod


def test_build_idp_page4_anchor_backed_candidate_readiness() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "construct_confirmation_status": "construct_citation_confirmed",
                "confirmed_anchor_citation": "PMC3077599 (2011)",
            }
        },
        {
            "summary": {
                "focus_conditions": "ph_low ; ph_high",
            }
        },
        {
            "summary": {
                "current_wrong_conditions": ["hydro_high", "salt_high"],
            }
        },
        {
            "summary": {
                "status": "page4_ph_low_fill_value_packet_ready",
            }
        },
        {
            "summary": {
                "status": "page4_ph_high_fill_value_packet_ready",
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "page4_anchor_backed_candidate_review_ready"
    assert s["construct_confirmation_status"] == "construct_citation_confirmed"
    assert s["followup_fill_draft_ready"] is True
    assert s["fill_value_packets_ready"] is True
    assert s["required_followup_note_count"] == 2
    assert s["pending_followup_note_count"] == 0
    assert s["draft_followup_note_count"] == 2
    assert s["anchor_backed_candidate_ready_now"] is False
    assert "review" in s["next_required_step"].lower()
    assert payload["rows"][0]["current_status"] == "ready"
    assert payload["rows"][1]["current_status"] == "draft_ready"
