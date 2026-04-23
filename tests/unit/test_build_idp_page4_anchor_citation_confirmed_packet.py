from __future__ import annotations

from tools import build_idp_page4_anchor_citation_confirmed_packet as mod


def test_build_idp_page4_anchor_citation_confirmed_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "first_open_source_anchor": "PMC3077599 (2011)",
                "first_open_source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3077599/",
            }
        },
        {
            "summary": {
                "candidate_anchor_citation": "PMC3077599 (2011)",
                "candidate_anchor_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3077599/",
                "construct_mapping": "synthetic page4 target likely maps to PAGE4 full-length 102-aa construct candidate",
                "current_wrong_conditions": ["base", "ph_low", "ph_high"],
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "page4_anchor_citation_confirmed_packet_ready"
    assert s["confirmed_anchor_citation"] == "PMC3077599 (2011)"
    assert s["construct_confirmation_status"] == "construct_citation_confirmed"
    assert s["identity_status"] == "construct_citation_confirmed_state_followup_required"
    assert s["followup_packet_artifact"] == "runs/idp_page4_phosphorylation_followup_packet_current.md"
    assert s["phosphorylation_state_followup_required"] is True
    assert s["followup_source_anchors"] == "PMID 26242913 ; PMID 28289210"
    assert s["promotion_ready"] is False
    assert "phosphorylation-state follow-up" in s["next_required_step"]
    assert payload["rows"][0]["freeze_status"] == "citation_confirmed"
