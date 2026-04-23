from __future__ import annotations

from tools import build_wetlab_antiviral_first_contact_packets as mod
from tools import build_wetlab_antiviral_wave1_rail as rail_mod
from tools import build_wetlab_first_contact_brief_bundle as bundle_mod
from tools import build_wetlab_mpro_vendor_cost_check as vendor_mod
from tools import build_wetlab_next3_novelty_fill_map as next_novelty_mod
from tools import build_wetlab_next3_repurposing_fill_map as next_fill_mod
from tools import build_wetlab_priority3_novelty_fill_map as novelty_fill_mod
from tools import build_wetlab_priority3_repurposing_fill_map as fill_map_mod
from tools import build_wetlab_priority3_repurposing_seed_pool as seed_mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_brief_fill_queue as fill_queue_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_packet_queue as queue_mod
from tools import build_wetlab_one_page_brief_schema as schema_mod


def test_build_wetlab_antiviral_first_contact_packets() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    fill_queue = fill_queue_mod.build_payload(queue, schema_mod.build_payload())
    fill_map = fill_map_mod.build_payload(seed_mod.build_payload(), fill_queue, queue)
    novelty_fill = novelty_fill_mod.build_payload(fill_map)
    next_fill = next_fill_mod.build_payload(fill_queue, queue)
    next_novelty = next_novelty_mod.build_payload(next_fill)
    vendor_cost = vendor_mod.build_payload(fill_map)
    rail = rail_mod.build_payload(portfolio, blueprint, companion, outreach)
    bundle = bundle_mod.build_payload(fill_map, novelty_fill, vendor_cost)

    payload = mod.build_payload(
        rail,
        bundle,
        outreach,
        fill_map,
        novelty_fill,
        next_fill,
        next_novelty,
        vendor_cost,
    )
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_antiviral_first_contact_packets_ready"
    assert summary["row_count"] == 2
    assert summary["partner_track_id"] == "READDI_Korea"
    assert summary["bundle_style_anchor_status"] == "wetlab_first_contact_brief_bundle_ready"
    assert summary["mpro_vendor_cost_check_ready"] is True
    assert summary["export_ready_count"] == 2

    plpro = rows["SARS-CoV-2 PLpro"]
    assert plpro["partner_track_id"] == "READDI_Korea"
    assert "DUB" in plpro["anti_target_panel"]
    assert "READDI" in plpro["source_anchor"]
    assert "shallow-pocket" in plpro["main_external_objection"]
    assert plpro["repurposing_fill_artifact"] == "runs/wetlab_next3_repurposing_fill_map_current.md"
    assert "Sitagliptin" in plpro["repurposing_compounds"]
    assert plpro["novelty_fill_artifact"] == "runs/wetlab_next3_novelty_fill_map_current.md"
    assert "PF-07957472" in plpro["novelty_compounds"]
    assert plpro["status"] == "ready_for_outbound_send"

    mpro = rows["SARS-CoV-2 Mpro"]
    assert mpro["partner_track_id"] == "READDI_Korea"
    assert "cathepsin" in mpro["anti_target_panel"].lower()
    assert "Moonshot" in mpro["source_anchor"]
    assert "crowded" in mpro["main_external_objection"].lower()
    assert mpro["repurposing_fill_artifact"] == "runs/wetlab_priority3_repurposing_fill_map_current.md"
    assert "Nirmatrelvir" in mpro["repurposing_compounds"]
    assert mpro["novelty_fill_artifact"] == "runs/wetlab_priority3_novelty_fill_map_current.md"
    assert "WU-04" in mpro["novelty_compounds"]
    assert mpro["mpro_vendor_cost_check_artifact"] == "runs/wetlab_mpro_vendor_cost_check_current.md"
    assert mpro["status"] == "ready_for_outbound_send"
