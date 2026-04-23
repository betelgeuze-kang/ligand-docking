from __future__ import annotations

from tools import build_tcruzi_pde_launch_packet as mod


def test_build_tcruzi_pde_launch_packet() -> None:
    payload = mod.build_payload(
        mod._load_json(mod.DEFAULT_BRIEF_INDEX_JSON),
        mod._load_json(mod.DEFAULT_RENDER_SUITE_JSON),
        mod._load_json(mod.DEFAULT_EXPORT_JSON),
        mod._load_json(mod.DEFAULT_CONDITION_CARD_JSON),
    )
    summary = payload["summary"]

    assert summary["status"] == "tcruzi_pde_launch_packet_ready"
    assert summary["serialized_queue_rank"] == 3
    assert summary["serialized_run_order"] == "3_of_3"
    assert summary["partner_track_id"] == "DNDi_IPK"
    assert summary["required_artifact_count"] == 5
    assert "Sildenafil" in summary["comparison_controls"]
