from __future__ import annotations

from tools import build_wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map as mod


def test_build_wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map_ready"
    assert summary["row_count"] == 3
    assert rows[0]["compound_name"] == "Eltrombopag"
    assert rows[0]["first_contact_use_mode"] == "proceed_now"
    assert rows[1]["compound_name"] == "Policresulen"
    assert rows[1]["first_contact_use_mode"] == "benchmark_control"
    assert rows[2]["compound_name"] == "Boceprevir"
    assert rows[2]["first_contact_use_mode"] == "comparator_only"
    assert rows[0]["target_brief_artifact"] == "runs/wetlab_target_brief_dengue_ns2b_ns3_protease_current.md"
    assert rows[0]["first_contact_packet_artifact"] == "runs/dengue_ns2b_ns3_protease_launch_packet_current.md"
