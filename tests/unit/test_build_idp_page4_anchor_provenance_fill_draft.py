from __future__ import annotations

from tools import build_idp_page4_anchor_provenance_fill_draft as mod


def test_build_idp_page4_anchor_provenance_fill_draft() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "first_open_source_anchor": "PMC3077599 (2011)",
                "first_open_source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3077599/",
                "residue_count": 102,
            }
        },
        {
            "summary": {
                "current_wrong_conditions": ["hydro_high", "salt_high"],
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "page4_anchor_provenance_fill_draft_ready"
    assert s["candidate_anchor_citation"] == "PMC3077599 (2011)"
    assert s["citation_confirmed_packet_artifact"] == "runs/idp_page4_anchor_citation_confirmed_packet_current.md"
    assert s["identity_status"] == "hypothesis_only"
    assert s["identity_claim_allowed_now"] is False
    assert "PAGE4 full-length 102-aa" in s["construct_mapping"]
    assert s["fragment_evidence_policy"] == "fragment_not_sufficient"
    assert "phosphorylation-state follow-up" in s["condition_mapping"]
    assert s["state_mixing_allowed"] is False
    assert s["promotion_ready"] is False
    assert "citation-confirmed packet" in s["next_required_step"]
    assert len(payload["rows"]) == 4
    assert payload["rows"][0]["fill_field"] == "candidate_anchor_citation"
    assert payload["rows"][3]["draft_value"] == "PMID 26242913 ; PMID 28289210"
