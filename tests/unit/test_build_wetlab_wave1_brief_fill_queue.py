from __future__ import annotations

from tools import build_wetlab_one_page_brief_schema as schema_mod
from tools import build_wetlab_next3_novelty_fill_map as next_novelty_mod
from tools import build_wetlab_next3_repurposing_fill_map as next_fill_mod
from tools import build_wetlab_priority3_novelty_fill_map as novelty_fill_mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_priority3_repurposing_fill_map as fill_map_mod
from tools import build_wetlab_priority3_repurposing_seed_pool as seed_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_brief_fill_queue as mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_packet_queue as queue_mod
from tools import build_wetlab_stk17b_novelty_fill_map as stk17b_novelty_mod
from tools import build_wetlab_stk17b_repurposing_fill_map as stk17b_fill_mod


def test_build_wetlab_wave1_brief_fill_queue() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    schema = schema_mod.build_payload()
    initial_fill_queue = mod.build_payload(queue, schema)
    fill_map = fill_map_mod.build_payload(seed_mod.build_payload(), initial_fill_queue, queue)
    novelty_fill = novelty_fill_mod.build_payload(fill_map)
    next_fill = next_fill_mod.build_payload(initial_fill_queue, queue)
    next_novelty = next_novelty_mod.build_payload(next_fill)
    stk17b_fill = stk17b_fill_mod.build_payload(initial_fill_queue, queue)
    stk17b_novelty = stk17b_novelty_mod.build_payload(stk17b_fill)
    payload = mod.build_payload(queue, schema, fill_map, novelty_fill, next_fill, next_novelty, stk17b_fill, stk17b_novelty)
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_wave1_brief_fill_queue_ready"
    assert summary["row_count"] == 8
    assert summary["repurposing_filled_target_count"] == 0
    assert summary["novelty_filled_target_count"] == 7
    assert rows["ALK2"]["fill_status"] == "repurposing_and_novelty_filled_pending_export"
    assert rows["T. cruzi PDE"]["fill_status"] == "repurposing_and_novelty_filled_pending_export"
    assert rows["Cruzain"]["repurposing_filled_slot_count"] == 3
    assert rows["Cruzain"]["novelty_filled_slot_count"] == 3
    assert rows["SARS-CoV-2 Mpro"]["repurposing_slot_count"] == 3
    assert rows["SARS-CoV-2 Mpro"]["repurposing_filled_slot_count"] == 3
    assert rows["SARS-CoV-2 Mpro"]["novelty_filled_slot_count"] == 3
    assert rows["STK17B (DRAK2)"]["fill_status"] == "repurposing_and_novelty_filled_pending_export"
    assert rows["STK17B (DRAK2)"]["repurposing_filled_slot_count"] == 3
    assert rows["STK17B (DRAK2)"]["novelty_filled_slot_count"] == 3
    assert rows["T. cruzi PDE"]["brief_artifact_planned"] == "runs/wetlab_target_brief_tcruzi_pde_current.md"
