from __future__ import annotations

from tools import build_idp_page4_anchor_backed_candidate_decision as mod


def test_build_idp_page4_anchor_backed_candidate_decision() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "page4_anchor_backed_candidate_review_packet_ready"}},
        {"summary": {"source_anchor": "PMID 26242913"}},
        {"summary": {"source_anchor": "PMID 28289210"}},
    )
    s = payload["summary"]
    assert s["status"] == "page4_anchor_backed_candidate_decision_pending_manual_confirmation"
    assert s["review_packet_ready"] is True
    assert s["ph_low_freeze_ready"] is True
    assert s["ph_high_freeze_ready"] is True
    assert s["manual_confirmation_required_count"] == 2
    assert payload["rows"][1]["decision_item"] == "ph_low_freeze_packet"
