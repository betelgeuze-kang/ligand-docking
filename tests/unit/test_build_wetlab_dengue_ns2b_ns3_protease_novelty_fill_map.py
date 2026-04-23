from __future__ import annotations

from tools import build_wetlab_dengue_ns2b_ns3_protease_novelty_fill_map as mod


REPURPOSING = {"rows": [{"target_id": "Dengue NS2B-NS3 protease"}]}


def test_build_wetlab_dengue_ns2b_ns3_protease_novelty_fill_map() -> None:
    payload = mod.build_payload(REPURPOSING)
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_dengue_ns2b_ns3_protease_novelty_fill_map_ready"
    assert summary["target_count"] == 1
    assert summary["row_count"] == 3
    assert summary["novelty_slot_count"] == 3

    assert rows[0]["novelty_compound_name"] == "BP2109"
    assert rows[0]["novelty_axis"] == "benchmark_control"
    assert rows[0]["first_contact_use_mode"] == "benchmark_control"

    assert rows[1]["novelty_compound_name"] == "Curcumin"
    assert rows[1]["novelty_axis"] == "state_novelty"
    assert rows[1]["first_contact_use_mode"] == "proceed_now"

    assert rows[2]["novelty_compound_name"] == "Punicalagin"
    assert rows[2]["novelty_axis"] == "condition_novelty"
    assert rows[2]["first_contact_use_mode"] == "comparator_only"

    assert all(row["target_id"] == "Dengue NS2B-NS3 protease" for row in rows)
    assert all(row["outreach_track_id"] == "IPK_dengue" for row in rows)
    assert all(row["target_brief_artifact"] == "runs/dengue_ns2b_ns3_protease_render_suite_current.md" for row in rows)
    assert all(row["first_contact_packet_artifact"] == "runs/dengue_ns2b_ns3_protease_ipk_export_current.md" for row in rows)
    assert all(row["source_repurposing_fill_bound"] is True for row in rows)
