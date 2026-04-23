from __future__ import annotations

from tools import build_idp_page4_ph_low_fill_value_packet as mod


def test_build_idp_page4_ph_low_fill_value_packet() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {"fill_target": "ph_low_candidate_state_note", "source_anchor": "PMID 26242913"},
            ]
        }
    )
    s = payload["summary"]
    assert s["status"] == "page4_ph_low_fill_value_packet_ready"
    assert s["condition_name"] == "ph_low"
    assert s["source_anchor"] == "PMID 26242913"
    assert s["fill_row_count"] == 2
    assert s["state_mixing_allowed"] is False
    assert s["promotion_ready"] is False
    assert "review" in s["next_required_step"]

