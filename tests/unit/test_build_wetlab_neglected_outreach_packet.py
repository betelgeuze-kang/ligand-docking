from __future__ import annotations

from tools import build_wetlab_neglected_outreach_packet as mod


def test_build_wetlab_neglected_outreach_packet() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_neglected_outreach_packet_ready"
    assert summary["partner_track_id"] == "DNDi_IPK"
    assert summary["row_count"] == 3
    assert "mission-aligned micro-validation" in summary["offer_model"]
    assert summary["target_sequence"] == "T. cruzi PDE -> Cruzain -> Leishmania braziliensis DHODH"
    assert rows[0]["target_id"] == "T. cruzi PDE"
    assert rows[1]["target_id"] == "Cruzain"
    assert rows[2]["target_id"] == "Leishmania braziliensis DHODH"
    assert "human PDE" in rows[0]["anti_target_panel"]
