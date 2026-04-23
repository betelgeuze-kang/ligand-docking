from __future__ import annotations

from tools import build_wetlab_mpro_vendor_cost_check as mod
from tools import build_wetlab_one_page_brief_schema as schema_mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_priority3_repurposing_fill_map as fill_map_mod
from tools import build_wetlab_priority3_repurposing_seed_pool as seed_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_brief_fill_queue as fill_queue_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_packet_queue as queue_mod


def test_build_wetlab_mpro_vendor_cost_check() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    fill_queue = fill_queue_mod.build_payload(queue, schema_mod.build_payload())
    fill_map = fill_map_mod.build_payload(seed_mod.build_payload(), fill_queue, queue)
    payload = mod.build_payload(fill_map)
    summary = payload["summary"]
    rows = {row["compound_name"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_mpro_vendor_cost_check_ready"
    assert summary["target_id"] == "SARS-CoV-2 Mpro"
    assert summary["row_count"] == 3
    assert summary["source_priority3_repurposing_fill_map_artifact"] == "runs/wetlab_priority3_repurposing_fill_map_current.md"
    assert rows["Nirmatrelvir"]["vendor_name"] == "MedKoo Biosciences"
    assert rows["Nirmatrelvir"]["procurement_action"] == "benchmark_control"
    assert rows["Boceprevir"]["listed_currency"] == "USD"
    assert rows["Boceprevir"]["procurement_action"] == "proceed_now"
    assert rows["Telaprevir"]["availability_status"] == "Ready to ship"
