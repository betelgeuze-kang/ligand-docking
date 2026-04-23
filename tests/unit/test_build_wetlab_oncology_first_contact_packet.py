from __future__ import annotations

from tools import build_ca_ix_one_page_brief as caix_brief_mod
from tools import build_wetlab_first_contact_brief_bundle as first_contact_mod
from tools import build_wetlab_priority3_novelty_fill_map as novelty_fill_mod
from tools import build_wetlab_priority3_repurposing_fill_map as fill_map_mod
from tools import build_wetlab_priority3_repurposing_seed_pool as seed_mod
from tools import build_wetlab_oncology_first_contact_packet as mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_brief_fill_queue as fill_queue_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_packet_queue as queue_mod
from tools import build_wetlab_one_page_brief_schema as schema_mod


def test_build_wetlab_oncology_first_contact_packet() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    fill_queue = fill_queue_mod.build_payload(queue, schema_mod.build_payload())
    fill_map = fill_map_mod.build_payload(seed_mod.build_payload(), fill_queue, queue)
    novelty_fill = novelty_fill_mod.build_payload(fill_map)
    caix_brief = caix_brief_mod.build_payload(portfolio, blueprint, companion, outreach)
    first_contact = first_contact_mod.build_payload(fill_map, novelty_fill)

    payload = mod.build_payload(caix_brief, first_contact, outreach, companion, fill_map, novelty_fill)
    summary = payload["summary"]
    structured = payload["structured"]

    assert summary["status"] == "wetlab_oncology_first_contact_packet_ready"
    assert summary["target_id"] == "CA IX"
    assert summary["validation_companion_target"] == "CA XII"
    assert summary["housekeeping_deselection_target"] == "CA II"
    assert structured["partner_track_id"] == "oncology_condition_aware"
    assert "MES-buffered acidic arm" in structured["buffer_program"]["primary_buffer_arm"]
    assert "CA XII" in structured["anti_target_panel"]
    assert structured["repurposing_fill_artifact"] == "runs/wetlab_priority3_repurposing_fill_map_current.md"
    assert structured["novelty_fill_artifact"] == "runs/wetlab_priority3_novelty_fill_map_current.md"
    assert "Acetazolamide" in structured["repurposing_compounds"]
    assert "SLC-0111" in structured["novelty_compounds"]
