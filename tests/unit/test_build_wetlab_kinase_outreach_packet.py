from __future__ import annotations

from tools import build_wetlab_first_contact_brief_bundle as bundle_mod
from tools import build_wetlab_kinase_outreach_packet as mod
from tools import build_wetlab_next3_novelty_fill_map as next_novelty_mod
from tools import build_wetlab_next3_repurposing_fill_map as next_fill_mod
from tools import build_wetlab_one_page_brief_schema as schema_mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_brief_fill_queue as fill_queue_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_kinase_first_contact_packets as first_contact_mod
from tools import build_wetlab_wave1_kinase_rail_packets as rail_mod
from tools import build_wetlab_wave1_packet_queue as queue_mod
from tools import build_wetlab_stk17b_novelty_fill_map as stk17b_novelty_mod
from tools import build_wetlab_stk17b_repurposing_fill_map as stk17b_fill_mod


def test_build_wetlab_kinase_outreach_packet() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    rail = rail_mod.build_payload(portfolio, blueprint, companion, outreach)
    bundle = bundle_mod.build_payload()
    schema = schema_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    fill_queue = fill_queue_mod.build_payload(queue, schema)
    next_fill = next_fill_mod.build_payload(fill_queue, queue)
    next_novelty = next_novelty_mod.build_payload(next_fill)
    stk17b_fill = stk17b_fill_mod.build_payload(fill_queue, queue)
    stk17b_novelty = stk17b_novelty_mod.build_payload(stk17b_fill)
    first_contact = first_contact_mod.build_payload(rail, bundle, schema, outreach, next_fill, next_novelty, stk17b_fill, stk17b_novelty)

    payload = mod.build_payload(first_contact, outreach)
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_kinase_outreach_packet_ready"
    assert summary["row_count"] == 2
    assert summary["track_count"] == 2
    assert "M4K_open_science" in summary["explicit_track_difference"]
    assert "SGC_dark_kinase" in summary["explicit_track_difference"]

    alk2 = rows["ALK2"]
    assert alk2["partner_track_id"] == "M4K_open_science"
    assert alk2["target_sequence"] == 1
    assert "open-science" in alk2["offer_model"]
    assert "mutant-aware" in alk2["first_email_body_brief"]
    assert alk2["repurposing_fill_status"] == "next3_repurposing_seed_fill_bound"
    assert "Vandetanib" in alk2["repurposing_compounds"]
    assert alk2["novelty_fill_status"] == "next3_novelty_seed_fill_bound"
    assert "M4K2009" in alk2["novelty_compounds"]
    assert alk2["status"] == "ready_for_partner_specific_export"

    stk17b = rows["STK17B (DRAK2)"]
    assert stk17b["partner_track_id"] == "SGC_dark_kinase"
    assert stk17b["target_sequence"] == 2
    assert "probe-benchmarked" in stk17b["what_to_send_first"]
    assert "open-set" in stk17b["first_email_body_brief"].lower()
    assert stk17b["repurposing_fill_status"] == "next3_repurposing_seed_fill_bound"
    assert "PFE-PKIS 43 (4)" in stk17b["repurposing_compounds"]
    assert stk17b["novelty_fill_status"] == "next3_novelty_seed_fill_bound"
    assert "SGC-STK17B-1 (11s)" in stk17b["novelty_compounds"]
    assert stk17b["status"] == "ready_for_partner_specific_export"
