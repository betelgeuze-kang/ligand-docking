from __future__ import annotations

from tools import build_idp_page4_ph_high_freeze_packet as mod


def test_build_idp_page4_ph_high_freeze_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {"condition_name": "ph_high", "source_anchor": "PMID 28289210"},
            "rows": [
                {"fill_field": "ph_high_candidate_state_note", "source_anchor": "PMID 28289210", "guardrail": "g1"},
                {"fill_field": "ph_high_candidate_aggregation_note", "source_anchor": "PMID 28289210", "guardrail": "g2"},
            ],
        }
    )
    s = payload["summary"]
    assert s["status"] == "page4_ph_high_freeze_packet_ready"
    assert s["freeze_row_count"] == 2
    assert s["freeze_ready"] is True
    assert payload["rows"][1]["freeze_decision"] == "draft_ready_review_only"
