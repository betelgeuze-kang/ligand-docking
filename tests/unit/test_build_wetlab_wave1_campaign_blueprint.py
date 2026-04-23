from __future__ import annotations

from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_wave1_campaign_blueprint as mod


def test_build_wetlab_wave1_campaign_blueprint() -> None:
    payload = mod.build_payload(portfolio_mod.build_payload())
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_wave1_campaign_blueprint_ready"
    assert summary["wave1_target_count"] == 8
    assert rows["T. cruzi PDE"]["repurposing_lane_slots"] == 3
    assert "human PDE" in rows["T. cruzi PDE"]["anti_target_panel"]
    assert rows["T. cruzi PDE"]["outreach_track_id"] == "DNDi_IPK"
    assert rows["CA IX"]["first_partner_type"].startswith("oncology")
