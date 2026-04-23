from __future__ import annotations

from tools import build_wetlab_broad_screen_library_spec as mod


def test_build_wetlab_broad_screen_library_spec_prefers_100k_broad_lane() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]

    assert summary["status"] == "wetlab_broad_screen_library_spec_ready"
    assert summary["strict_fda_only_feasible_at_100k"] is False
    assert summary["recommended_execution_lane"] == "broad_procurement_100k"
    assert summary["strict_lane_target_size"] == 3000
    assert summary["broad_lane_target_size"] == 100000
    assert len(payload["rows"]) == 2
