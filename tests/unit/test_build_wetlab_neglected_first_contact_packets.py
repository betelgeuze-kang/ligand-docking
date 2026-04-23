from __future__ import annotations

from tools import build_wetlab_neglected_first_contact_packets as mod
from tools import build_wetlab_first_contact_brief_bundle as first_contact_mod
from tools import build_wetlab_one_page_brief_schema as schema_mod
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


def test_build_wetlab_neglected_first_contact_packets() -> None:
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
    first_contact = first_contact_mod.build_payload(fill_map, novelty_fill)
    payload = mod.build_payload(first_contact, next_fill, next_novelty)
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_neglected_first_contact_packets_ready"
    assert summary["target_count"] == 3
    assert summary["partner_track_id"] == "DNDi_IPK"
    assert summary["export_ready_count"] == 2
    assert "human PDE" in rows["T. cruzi PDE"]["anti_target_panel"]
    assert rows["T. cruzi PDE"]["repurposing_fill_artifact"] == "runs/wetlab_priority3_repurposing_fill_map_current.md"
    assert "Dipyridamole" in rows["T. cruzi PDE"]["repurposing_compounds"]
    assert rows["T. cruzi PDE"]["novelty_fill_artifact"] == "runs/wetlab_priority3_novelty_fill_map_current.md"
    assert "NPD-227" in rows["T. cruzi PDE"]["novelty_compounds"]
    assert rows["T. cruzi PDE"]["status"] == "ready_for_outbound_send"
    assert rows["Cruzain"]["repurposing_fill_artifact"] == "runs/wetlab_next3_repurposing_fill_map_current.md"
    assert "Benidipine" in rows["Cruzain"]["repurposing_compounds"]
    assert rows["Cruzain"]["novelty_fill_artifact"] == "runs/wetlab_next3_novelty_fill_map_current.md"
    assert "ML217" in rows["Cruzain"]["novelty_compounds"]
    assert rows["Cruzain"]["status"] == "ready_for_outbound_send"
    assert "host DHODH" in rows["Leishmania braziliensis DHODH"]["anti_target_panel"]
    assert rows["Leishmania braziliensis DHODH"]["status"] == "awaiting_compound_fill"
