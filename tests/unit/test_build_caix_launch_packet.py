from __future__ import annotations

from tools import build_caix_launch_packet as mod


def test_build_caix_launch_packet() -> None:
    payload = mod.build_payload(
        mod._load_json(mod.DEFAULT_BRIEF_INDEX_JSON),
        mod._load_json(mod.DEFAULT_RENDER_SUITE_JSON),
        mod._load_json(mod.DEFAULT_EXPORT_JSON),
        mod._load_json(mod.DEFAULT_CONDITION_CARD_JSON),
    )
    summary = payload["summary"]

    assert summary["status"] == "caix_launch_packet_ready"
    assert summary["serialized_queue_rank"] == 2
    assert summary["serialized_run_order"] == "2_of_3"
    assert summary["partner_track_id"] == "oncology_condition_aware"
    assert summary["required_artifact_count"] == 5
    assert summary["acidic_primary_arm"] == "MES-buffered acidic arm centered on pH 6.6"
