from __future__ import annotations

from tools import build_wetlab_priority3_novelty_fill_map as mod
from tools import build_wetlab_priority3_repurposing_fill_map as rep_mod
from tools import build_wetlab_priority3_repurposing_seed_pool as seed_mod
from tools import build_wetlab_wave1_brief_fill_queue as fill_queue_mod
from tools import build_wetlab_wave1_packet_queue as queue_mod
from tools import build_wetlab_one_page_brief_schema as schema_mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod


def test_build_wetlab_priority3_novelty_fill_map() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    fill_queue = fill_queue_mod.build_payload(queue, schema_mod.build_payload())
    repurposing_fill = rep_mod.build_payload(seed_mod.build_payload(), fill_queue, queue)
    payload = mod.build_payload(repurposing_fill)
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_priority3_novelty_fill_map_ready"
    assert summary["priority_target_count"] == 3
    assert summary["row_count"] == 9
    assert rows[0]["target_id"] == "T. cruzi PDE"
    assert rows[3]["target_id"] == "CA IX"
    assert rows[6]["target_id"] == "SARS-CoV-2 Mpro"
    assert rows[0]["novelty_fill_status"] == "ready"
    assert rows[6]["first_contact_use_mode"] in {"proceed_now", "comparator_only"}
    assert rows[8]["row_status"] == "ready"
