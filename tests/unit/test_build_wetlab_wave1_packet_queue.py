from __future__ import annotations

from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_packet_queue as mod


def test_build_wetlab_wave1_packet_queue() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    payload = mod.build_payload(portfolio, blueprint, companion, outreach)
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_wave1_packet_queue_ready"
    assert summary["wave1_target_count"] == 8
    assert rows["T. cruzi PDE"]["track_id"] == "DNDi_IPK"
    assert rows["T. cruzi PDE"]["brief_artifact_planned"] == "runs/wetlab_target_brief_tcruzi_pde_current.md"
    assert rows["CA IX"]["anti_target_panel"] == "CA II plus CA XII counterscreen"
    assert rows["SARS-CoV-2 Mpro"]["queue_status"] == "ready_for_target_specific_fill"
