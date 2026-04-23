from __future__ import annotations

from tools import build_wetlab_stk17b_novelty_fill_map as mod
from tools import build_wetlab_stk17b_repurposing_fill_map as rep_mod
from tools import build_wetlab_one_page_brief_schema as schema_mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_brief_fill_queue as fill_queue_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_packet_queue as queue_mod


def test_build_wetlab_stk17b_novelty_fill_map() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    schema = schema_mod.build_payload()
    fill_queue = fill_queue_mod.build_payload(queue, schema)
    rep = rep_mod.build_payload(fill_queue, queue)

    payload = mod.build_payload(rep)
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_stk17b_novelty_fill_map_ready"
    assert summary["row_count"] == 3
    assert rows[0]["novelty_compound_name"] == "SGC-STK17B-1 (11s)"
    assert rows[1]["novelty_compound_name"] == "11h quinazoline analog"
    assert rows[1]["first_contact_use_mode"] == "proceed_now"
    assert rows[2]["novelty_compound_name"] == "11aa quinazoline analog"
    assert rows[2]["first_contact_use_mode"] == "benchmark_control"
