from __future__ import annotations

from tools import build_idp_page4_phosphorylation_followup_packet as mod


def test_build_idp_page4_phosphorylation_followup_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "construct_confirmation_status": "construct_citation_confirmed",
                "confirmed_anchor_citation": "PMC3077599 (2011)",
            }
        },
        {
            "summary": {
                "first_open_source_anchor": "PMC3077599 (2011)",
            }
        },
        {
            "summary": {
                "current_wrong_conditions": ["hydro_high", "salt_high"],
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "page4_phosphorylation_followup_packet_ready"
    assert s["focus_condition_count"] == 2
    assert s["focus_conditions"] == "ph_low ; ph_high"
    assert s["construct_confirmation_status"] == "construct_citation_confirmed"
    assert s["low_state_source_anchor"] == "PMID 26242913"
    assert s["high_state_source_anchor"] == "PMID 28289210"
    assert s["fill_draft_artifact"] == "runs/idp_page4_phosphorylation_fill_draft_current.md"
    assert s["state_mixing_allowed"] is False
    assert s["promotion_ready"] is False
    assert "phosphorylation fill draft" in s["next_required_step"]
    assert payload["rows"][0]["followup_condition"] == "ph_low"
    assert payload["rows"][1]["followup_condition"] == "ph_high"
