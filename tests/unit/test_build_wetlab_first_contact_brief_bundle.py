from __future__ import annotations

from tools import build_wetlab_first_contact_brief_bundle as mod
from tools import build_wetlab_mpro_vendor_cost_check as vendor_mod
from tools import build_wetlab_priority3_novelty_fill_map as novelty_fill_mod
from tools import build_wetlab_priority3_repurposing_fill_map as fill_map_mod
from tools import build_wetlab_priority3_repurposing_seed_pool as seed_mod
from tools import build_wetlab_wave1_brief_fill_queue as fill_queue_mod
from tools import build_wetlab_wave1_packet_queue as queue_mod
from tools import build_wetlab_one_page_brief_schema as schema_mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod


def test_build_wetlab_first_contact_brief_bundle() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    fill_queue = fill_queue_mod.build_payload(queue, schema_mod.build_payload())
    fill_map = fill_map_mod.build_payload(seed_mod.build_payload(), fill_queue, queue)
    novelty_fill = novelty_fill_mod.build_payload(fill_map)
    vendor_cost = vendor_mod.build_payload(fill_map)
    payload = mod.build_payload(fill_map, novelty_fill, vendor_cost)
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_first_contact_brief_bundle_ready"
    assert summary["row_count"] == 3
    assert summary["priority3_repurposing_fill_ready_count"] == 3
    assert summary["priority3_novelty_fill_ready_count"] == 3
    assert summary["priority3_target_render_split_artifact"] == "runs/wetlab_priority3_target_render_split_current.md"
    assert summary["priority3_protein_run_queue_artifact"] == "runs/wetlab_priority3_protein_run_queue_current.md"
    assert summary["prep_artifact_lane_artifact"] == "runs/wetlab_prep_artifact_lane_current.md"
    assert rows["T. cruzi PDE"]["outreach_track_id"] == "DNDi_IPK"
    assert rows["T. cruzi PDE"]["launch_packet_artifact"] == "runs/tcruzi_pde_launch_packet_current.md"
    assert rows["T. cruzi PDE"]["repurposing_fill_status"] == "priority3_repurposing_seed_fill_bound"
    assert rows["T. cruzi PDE"]["novelty_fill_status"] == "priority3_novelty_seed_fill_bound"
    assert rows["CA IX"]["anti_target_panel"] == "CA II plus CA XII selectivity panel"
    assert "Acetazolamide" in rows["CA IX"]["repurposing_compounds"]
    assert "SLC-0111 ureido-benzenesulfonamide" in rows["CA IX"]["novelty_compounds"]
    assert rows["SARS-CoV-2 Mpro"]["priority_rank"] == 3
    assert rows["SARS-CoV-2 Mpro"]["launch_packet_artifact"] == "runs/sarscov2_mpro_launch_packet_current.md"
    assert rows["SARS-CoV-2 Mpro"]["mpro_vendor_cost_check_ready"] is True
