from __future__ import annotations

from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_kinase_rail_packets as mod


def test_build_wetlab_wave1_kinase_rail_packets() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()

    payload = mod.build_payload(portfolio, blueprint, companion, outreach)
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_wave1_kinase_rail_packets_ready"
    assert summary["target_count"] == 2

    alk2 = rows["ALK2"]
    assert alk2["partner_track_id"] == "M4K_open_science"
    assert "6SRH" in alk2["source_anchor_2_label"]
    assert "mutant" in alk2["first_assay_stack"].lower()
    assert "ALK5" in alk2["selectivity_anti_target_panel"]

    stk17b = rows["STK17B (DRAK2)"]
    assert stk17b["partner_track_id"] == "SGC_dark_kinase"
    assert "SGC-STK17B-1" in stk17b["source_anchor_1_label"]
    assert "P-loop" in stk17b["top3_novelty_slot_1_criteria"]
    assert "negative control" in stk17b["first_assay_stack"].lower()
