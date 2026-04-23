from __future__ import annotations

from pathlib import Path

from tools import build_wetlab_next3_novelty_fill_map as next_novelty_mod
from tools import build_wetlab_next3_repurposing_fill_map as next_fill_mod
from tools import build_wetlab_priority3_novelty_fill_map as novelty_fill_mod
from tools import build_wetlab_one_page_brief_schema as schema_mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_priority3_repurposing_fill_map as fill_map_mod
from tools import build_wetlab_priority3_repurposing_seed_pool as seed_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_brief_fill_queue as fill_queue_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_packet_queue as queue_mod
from tools import build_wetlab_stk17b_novelty_fill_map as stk17b_novelty_mod
from tools import build_wetlab_stk17b_repurposing_fill_map as stk17b_fill_mod
from tools import build_wetlab_wave1_target_brief_packets as mod


def test_build_wetlab_wave1_target_brief_packets() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    schema = schema_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    fill_queue = fill_queue_mod.build_payload(queue, schema)
    fill_map = fill_map_mod.build_payload(seed_mod.build_payload(), fill_queue, queue)
    novelty_fill = novelty_fill_mod.build_payload(fill_map)
    next_fill = next_fill_mod.build_payload(fill_queue, queue)
    next_novelty = next_novelty_mod.build_payload(next_fill)
    stk17b_fill = stk17b_fill_mod.build_payload(fill_queue, queue)
    stk17b_novelty = stk17b_novelty_mod.build_payload(stk17b_fill)
    payload = mod.build_payload(portfolio, blueprint, companion, outreach, schema, fill_map, novelty_fill, next_fill, next_novelty, stk17b_fill, stk17b_novelty)
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_wave1_target_brief_packets_ready"
    assert summary["target_count"] == 8
    assert rows["T. cruzi PDE"]["partner_track"] == "DNDi_IPK"
    assert rows["T. cruzi PDE"]["repurposing_filled_slot_count"] == 3
    assert rows["T. cruzi PDE"]["novelty_filled_slot_count"] == 3
    assert rows["CA IX"]["anti_target_panel"] == "CA II plus CA XII counterscreen"
    assert rows["CA IX"]["repurposing_fill_status"] == "actual_priority_fill_bound"
    assert rows["CA IX"]["novelty_filled_slot_count"] == 3
    assert rows["SARS-CoV-2 Mpro"]["artifact_path"].endswith("wetlab_target_brief_sarscov2_mpro_current.md")
    assert rows["SARS-CoV-2 Mpro"]["novelty_filled_slot_count"] == 3
    assert rows["Cruzain"]["repurposing_filled_slot_count"] == 3
    assert rows["Cruzain"]["novelty_filled_slot_count"] == 3
    assert rows["SARS-CoV-2 PLpro"]["novelty_filled_slot_count"] == 3
    assert rows["ALK2"]["repurposing_filled_slot_count"] == 3
    assert rows["ALK2"]["novelty_filled_slot_count"] == 3
    assert rows["STK17B (DRAK2)"]["repurposing_filled_slot_count"] == 3
    assert rows["STK17B (DRAK2)"]["novelty_filled_slot_count"] == 3
    assert "Dipyridamole" in Path(rows["T. cruzi PDE"]["artifact_path"]).read_text(encoding="utf-8")
    assert "## Current Novelty Fill" in Path(rows["T. cruzi PDE"]["artifact_path"]).read_text(encoding="utf-8")
    assert "NPD-227 pyrazolone series" in Path(rows["T. cruzi PDE"]["artifact_path"]).read_text(encoding="utf-8")
    assert "Benidipine" in Path(rows["Cruzain"]["artifact_path"]).read_text(encoding="utf-8")
    assert "ML217 benzimidazole series" in Path(rows["Cruzain"]["artifact_path"]).read_text(encoding="utf-8")
    assert "Sitagliptin" in Path(rows["SARS-CoV-2 PLpro"]["artifact_path"]).read_text(encoding="utf-8")
    assert "PF-07957472" in Path(rows["SARS-CoV-2 PLpro"]["artifact_path"]).read_text(encoding="utf-8")
    assert "Vandetanib" in Path(rows["ALK2"]["artifact_path"]).read_text(encoding="utf-8")
    assert "M4K2009" in Path(rows["ALK2"]["artifact_path"]).read_text(encoding="utf-8")
    stk17b_text = Path(rows["STK17B (DRAK2)"]["artifact_path"]).read_text(encoding="utf-8")
    assert "PFE-PKIS 43 (4)" in stk17b_text
    assert "Current Cheap-Validation / Open-Set Fill" in stk17b_text
    assert "SGC-STK17B-1 (11s)" in stk17b_text
