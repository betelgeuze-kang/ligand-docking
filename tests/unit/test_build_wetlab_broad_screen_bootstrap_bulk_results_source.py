from __future__ import annotations

from tools import build_wetlab_broad_screen_bootstrap_bulk_results_source as mod


def test_build_wetlab_broad_screen_bootstrap_bulk_results_source_rolls_up_fill_maps() -> None:
    payload = mod.build_payload(
        [
            {"rows": [{"target_id": "CA IX", "slot_rank": 1, "compound_name": "A"}, {"target_id": "CA IX", "slot_rank": 2, "compound_name": "B"}]},
            {"rows": [{"target_id": "T. cruzi PDE", "slot_rank": 1, "compound_name": "C"}]},
        ]
    )
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_broad_screen_bulk_results_source_ready"
    assert summary["target_count"] == 2
    assert summary["row_count"] == 3
    assert rows[0]["bulk_rank"] == 1
    assert rows[0]["source_anchor"] == "broad_screen_bootstrap_from_manual_fill_maps"
