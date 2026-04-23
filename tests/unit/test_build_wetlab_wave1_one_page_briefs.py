from __future__ import annotations

from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_one_page_briefs as mod


def test_build_wetlab_wave1_one_page_briefs() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    payload = mod.build_payload(portfolio, blueprint, outreach)
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_wave1_one_page_briefs_ready"
    assert summary["row_count"] == 8
    assert rows["CA IX"]["partner_track"] == "Condition-aware oncology labs"
    assert "crowded" in rows["SARS-CoV-2 Mpro"]["main_objection"].lower()
