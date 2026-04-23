from __future__ import annotations

from tools import build_wetlab_cathepsin_k_novelty_fill_map as mod


def test_build_wetlab_cathepsin_k_novelty_fill_map() -> None:
    payload = mod.build_payload({"rows": [{"target_id": "Cathepsin K"}]})
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_cathepsin_k_novelty_fill_map_ready"
    assert summary["target_count"] == 1
    assert summary["row_count"] == 3
    assert summary["novelty_slot_count"] == 3

    assert rows[0]["novelty_compound_name"] == "Odanacatib (MK-0822)"
    assert rows[0]["novelty_axis"] == "benchmark_control"
    assert rows[0]["first_contact_use_mode"] == "benchmark_control"

    assert rows[1]["novelty_compound_name"] == "MIV-711"
    assert rows[1]["novelty_axis"] == "selectivity_novelty"
    assert rows[1]["first_contact_use_mode"] == "proceed_now"

    assert rows[2]["novelty_compound_name"] == "T06 ectosteric Cathepsin K inhibitor"
    assert rows[2]["novelty_axis"] == "condition_novelty"
    assert rows[2]["first_contact_use_mode"] == "comparator_only"

    assert all(row["target_id"] == "Cathepsin K" for row in rows)
    assert all(row["outreach_track_id"] == "acidic_protease_wave2" for row in rows)
    assert all(row["target_brief_artifact"] == "runs/cathepsin_k_render_suite_current.md" for row in rows)
    assert all(row["first_contact_packet_artifact"] == "runs/cathepsin_k_acidic_protease_export_current.md" for row in rows)
    assert all(row["source_repurposing_fill_bound"] is True for row in rows)
