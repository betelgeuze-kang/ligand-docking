from __future__ import annotations

from tools import build_wetlab_cathepsin_k_repurposing_fill_map as mod


BRIEF_FILL_QUEUE = {
    "rows": [
        {
            "target_id": "Cathepsin K",
            "brief_artifact_planned": "runs/wetlab_target_brief_cathepsin_k_current.md",
        }
    ]
}
PACKET_QUEUE = {
    "rows": [
        {
            "target_id": "Cathepsin K",
            "track_label": "acidic protease condition-aware rail",
        }
    ]
}


def test_build_wetlab_cathepsin_k_repurposing_fill_map() -> None:
    payload = mod.build_payload(BRIEF_FILL_QUEUE, PACKET_QUEUE)
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_cathepsin_k_repurposing_fill_map_ready"
    assert summary["target_count"] == 1
    assert summary["row_count"] == 3
    assert rows[0]["compound_name"] == "Odanacatib"
    assert rows[0]["first_contact_use_mode"] == "benchmark_control"
    assert rows[1]["compound_name"] == "Balicatib"
    assert rows[1]["first_contact_use_mode"] == "benchmark_control"
    assert rows[2]["compound_name"] == "Relacatib"
    assert rows[2]["first_contact_use_mode"] == "comparator_only"
    assert rows[0]["target_brief_artifact"] == "runs/wetlab_target_brief_cathepsin_k_current.md"
    assert rows[0]["first_contact_packet_artifact"] == "runs/cathepsin_k_launch_packet_current.md"
