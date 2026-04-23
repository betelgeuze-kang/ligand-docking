from __future__ import annotations

from tools import build_wetlab_antiviral_wave1_rail as antiviral_mod
from tools import build_wetlab_antiviral_first_contact_packets as antiviral_fc_mod
from tools import build_ca_ix_one_page_brief as caix_brief_mod
from tools import build_wetlab_mpro_vendor_cost_check as vendor_mod
from tools import build_wetlab_neglected_first_contact_packets as neglected_fc_mod
from tools import build_wetlab_neglected_wave1_rows as neglected_rows_mod
from tools import build_wetlab_oncology_first_contact_packet as oncology_fc_mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_next3_novelty_fill_map as next_novelty_mod
from tools import build_wetlab_next3_repurposing_fill_map as next_fill_mod
from tools import build_wetlab_priority3_novelty_fill_map as novelty_fill_mod
from tools import build_wetlab_priority3_repurposing_fill_map as fill_map_mod
from tools import build_wetlab_priority3_repurposing_seed_pool as seed_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_brief_fill_queue as fill_queue_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_packet_queue as queue_mod
from tools import build_wetlab_wave1_kinase_first_contact_packets as kinase_fc_mod
from tools import build_wetlab_wave1_kinase_rail_packets as kinase_mod
from tools import build_wetlab_wave1_rail_packet_index as mod
from tools import build_wetlab_first_contact_brief_bundle as bundle_mod
from tools import build_wetlab_one_page_brief_schema as schema_mod
from tools import build_wetlab_stk17b_novelty_fill_map as stk17b_novelty_mod
from tools import build_wetlab_stk17b_repurposing_fill_map as stk17b_fill_mod


def test_build_wetlab_wave1_rail_packet_index() -> None:
    neglected_rows = neglected_rows_mod.build_payload()
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    schema = schema_mod.build_payload()
    fill_queue = fill_queue_mod.build_payload(queue, schema)
    fill_map = fill_map_mod.build_payload(seed_mod.build_payload(), fill_queue, queue)
    novelty_fill = novelty_fill_mod.build_payload(fill_map)
    next_fill = next_fill_mod.build_payload(fill_queue, queue)
    next_novelty = next_novelty_mod.build_payload(next_fill)
    stk17b_fill = stk17b_fill_mod.build_payload(fill_queue, queue)
    stk17b_novelty = stk17b_novelty_mod.build_payload(stk17b_fill)
    vendor_cost = vendor_mod.build_payload(fill_map)
    bundle = bundle_mod.build_payload(fill_map, novelty_fill, vendor_cost)
    neglected_first_contact = neglected_fc_mod.build_payload(bundle, next_fill, next_novelty)
    kinase_rail = kinase_mod.build_payload(portfolio, blueprint, companion, outreach)
    kinase_first_contact = kinase_fc_mod.build_payload(kinase_rail, bundle, schema, outreach, next_fill, next_novelty, stk17b_fill, stk17b_novelty)
    antiviral_rail = antiviral_mod.build_payload(portfolio, blueprint, companion, outreach)
    antiviral_first_contact = antiviral_fc_mod.build_payload(antiviral_rail, bundle, outreach, fill_map, novelty_fill, next_fill, next_novelty, vendor_cost)
    caix_brief = caix_brief_mod.build_payload(portfolio, blueprint, companion, outreach)
    oncology_first_contact = oncology_fc_mod.build_payload(caix_brief, bundle, outreach, companion, fill_map, novelty_fill)

    payload = mod.build_payload(
        neglected_rows,
        neglected_first_contact,
        kinase_rail,
        kinase_first_contact,
        antiviral_rail,
        antiviral_first_contact,
        oncology_first_contact,
        fill_map,
        novelty_fill,
        next_fill,
        next_novelty,
        stk17b_fill,
        stk17b_novelty,
        vendor_cost,
    )
    summary = payload["summary"]
    rows = {row["rail_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_wave1_rail_packet_index_ready"
    assert summary["rail_count"] == 5
    assert summary["priority3_repurposing_fill_target_count"] == 3
    assert summary["priority3_novelty_fill_target_count"] == 3
    assert summary["next3_repurposing_fill_target_count"] == 3
    assert summary["next3_novelty_fill_target_count"] == 3
    assert summary["stk17b_repurposing_fill_target_count"] == 1
    assert summary["stk17b_novelty_fill_target_count"] == 1
    assert summary["mpro_vendor_cost_check_ready"] is True
    assert summary["mpro_vendor_cost_check_artifact"] == "runs/wetlab_mpro_vendor_cost_check_current.md"
    assert summary["domain_generation_schema_artifact"] == "runs/wetlab_domain_generation_schema_current.md"
    assert summary["partner_export_schema_artifact"] == "runs/wetlab_partner_export_schema_current.md"
    assert summary["priority3_target_render_split_artifact"] == "runs/wetlab_priority3_target_render_split_current.md"
    assert summary["priority3_protein_run_queue_artifact"] == "runs/wetlab_priority3_protein_run_queue_current.md"
    assert summary["prep_artifact_lane_artifact"] == "runs/wetlab_prep_artifact_lane_current.md"
    assert summary["pending_high_lane_count"] == 0
    assert summary["compound_fill_ready_count"] == 0
    assert summary["first_contact_exported_count"] == 5
    assert rows["DNDi_IPK"]["outbound_status"] == "first_contact_exported"
    assert rows["M4K_open_science"]["outbound_status"] == "first_contact_exported"
    assert rows["M4K_open_science"]["target_ids"] == "ALK2"
    assert rows["M4K_open_science"]["lead_gate_status"] == "lead_packet_export_ready"
    assert rows["SGC_dark_kinase"]["rail_artifact_status"] == "wetlab_wave1_kinase_rail_packets_ready"
    assert rows["SGC_dark_kinase"]["outbound_status"] == "first_contact_exported"
    assert rows["SGC_dark_kinase"]["lead_gate_status"] == "lead_packet_export_ready"
    assert rows["READDI_Korea"]["first_contact_status"] == "wetlab_antiviral_first_contact_packets_ready"
    assert rows["READDI_Korea"]["outbound_status"] == "first_contact_exported"
    assert rows["READDI_Korea"]["lead_gate_status"] == "mpro_vendor_cost_ready"
    assert rows["oncology_condition_aware"]["outbound_status"] == "first_contact_exported"
