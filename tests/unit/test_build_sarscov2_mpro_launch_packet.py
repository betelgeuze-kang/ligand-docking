from __future__ import annotations

from tools import build_sarscov2_mpro_launch_packet as mod
from tools.wetlab_target_render_utils import load_json


def test_build_sarscov2_mpro_launch_packet() -> None:
    payload = mod.build_payload(
        load_json(mod.DEFAULT_RENDER_SUITE_JSON),
        load_json(mod.DEFAULT_EXPORT_JSON),
        load_json(mod.DEFAULT_VENDOR_COST_JSON),
    )
    summary = payload["summary"]

    assert summary["status"] == "sarscov2_mpro_launch_packet_ready"
    assert summary["execution_rank"] == 1
    assert summary["gate_to_start"] == "none"
    assert summary["partner_track_id"] == "READDI_Korea"
    assert payload["rows"][0]["artifact_kind"] == "condition_card"
    assert payload["rows"][-1]["artifact_kind"] == "vendor_cost_sheet"
