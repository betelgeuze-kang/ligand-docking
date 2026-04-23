from __future__ import annotations

from tools import build_wetlab_broad_screen_antitarget_queue as mod


def test_build_wetlab_broad_screen_antitarget_queue_opens_first_caix_panel_when_primary_ready() -> None:
    payload = mod.build_payload(
        broad_queue_payload={
            "rows": [
                {"target_id": "CA IX", "wave": "Wave 1", "shard_id": "01_of_20"},
                {"target_id": "CA IX", "wave": "Wave 1", "shard_id": "02_of_20"},
                {"target_id": "SARS-CoV-2 Mpro", "wave": "Wave 1", "shard_id": "01_of_20"},
            ]
        },
        companion_payload={
            "rows": [
                {"target_id": "CA IX", "primary_companion_panel": "CA II plus CA XII counterscreen"},
                {"target_id": "SARS-CoV-2 Mpro", "primary_companion_panel": "host cysteine protease sanity panel"},
            ]
        },
        rerank_payload={
            "rows": [
                {"target_id": "CA IX", "rerank_status": "full_bulk_top3_ready"},
                {"target_id": "SARS-CoV-2 Mpro", "rerank_status": "bootstrap_only"},
            ]
        },
    )
    summary = payload["summary"]
    first = payload["rows"][0]
    assert summary["status"] == "wetlab_broad_screen_antitarget_queue_ready"
    assert summary["ready_now_row_count"] == 1
    assert summary["first_actionable_primary_target_id"] == "CA IX"
    assert summary["first_actionable_anti_target_id"] == "CA II"
    assert first["queue_status"] == "ready_after_primary_bulk_ready"
