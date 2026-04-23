from __future__ import annotations

from tools import build_wetlab_antiviral_wave1_rail as mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod


def test_build_wetlab_antiviral_wave1_rail() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()

    payload = mod.build_payload(portfolio, blueprint, companion, outreach)
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_antiviral_wave1_rail_ready"
    assert summary["target_count"] == 2
    assert summary["track_id"] == "READDI_Korea"
    assert rows["SARS-CoV-2 PLpro"]["partner_track_id"] == "READDI_Korea"
    assert "USP" in rows["SARS-CoV-2 PLpro"]["host_off_target_counterscreens"]
    assert "cathepsin L" in rows["SARS-CoV-2 Mpro"]["host_off_target_counterscreens"]
    assert rows["SARS-CoV-2 Mpro"]["open_science_source_url"].startswith("https://postera.ai/")
