from __future__ import annotations

from tools import build_wetlab_next3_repurposing_fill_map as mod
from tools import build_wetlab_one_page_brief_schema as schema_mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_brief_fill_queue as fill_queue_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_packet_queue as queue_mod


def test_build_wetlab_next3_repurposing_fill_map() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    fill_queue = fill_queue_mod.build_payload(queue, schema_mod.build_payload())
    payload = mod.build_payload(fill_queue, queue)
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_next3_repurposing_fill_map_ready"
    assert summary["next3_target_count"] == 3
    assert summary["row_count"] == 9
    assert rows[0]["target_id"] == "Cruzain"
    assert rows[0]["compound_name"] == "Benidipine"
    assert any(row["target_id"] == "SARS-CoV-2 PLpro" and row["compound_name"] == "Sitagliptin" for row in rows)
    assert any(row["target_id"] == "ALK2" and row["compound_name"] == "Vandetanib" for row in rows)
