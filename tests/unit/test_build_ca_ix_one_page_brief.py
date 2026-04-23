from __future__ import annotations

from tools import build_ca_ix_one_page_brief as mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod


def test_build_ca_ix_one_page_brief() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()

    payload = mod.build_payload(portfolio, blueprint, companion, outreach)
    summary = payload["summary"]
    structured = payload["structured"]
    rows = payload["rows"]

    assert summary["status"] == "ca_ix_one_page_brief_ready"
    assert summary["target_id"] == "CA IX"
    assert summary["validation_companion_target"] == "CA XII"
    assert structured["partner_track"] == "oncology_condition_aware"
    assert structured["headline"].startswith("Acidic-buffer CA IX screening")
    assert structured["first_assay_stack_under_acidic_tumor_like_buffer"]["buffer_primary_arm"] == "MES-buffered acidic arm centered on pH 6.6"
    assert structured["ca_ii_ca_xii_selectivity_counterscreen_plan"]["primary_panel"] == "CA II plus CA XII counterscreen"
    assert any(row["section"] == "selectivity_counterscreen_plan" and "CA XII" in row["content"] for row in rows)
    assert any(row["section"] == "acidic_tumor_like_first_assay_stack" and "pH 6.6" in row["content"] for row in rows)
