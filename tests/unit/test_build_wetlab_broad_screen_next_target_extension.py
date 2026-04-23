from __future__ import annotations

from tools import build_wetlab_broad_screen_next_target_extension as mod


def test_next_target_extension_surfaces_mpro_after_caix() -> None:
    payload = mod.build_payload(
        broad_queue={
            "rows": [
                {"target_id": "CA IX", "shard_id": "01_of_20"},
                {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20"},
            ]
        },
        execution_queue={
            "rows": [
                {"target_id": "CA IX", "queue_status": "running"},
                {"target_id": "SARS-CoV-2 Mpro", "queue_status": "blocked_on_previous_target"},
            ]
        },
        antitarget_queue={
            "rows": [
                {
                    "primary_target_id": "SARS-CoV-2 Mpro",
                    "anti_target_id": "host cysteine protease sanity panel",
                    "queue_status": "blocked_on_primary_full_bulk_ready",
                }
            ]
        },
        actual_append={"summary": {"status": "wetlab_broad_screen_actual_append_ready"}},
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_broad_screen_next_target_extension_ready"
    assert summary["next_target_id"] == "SARS-CoV-2 Mpro"
    assert summary["anti_target_id"] == "host cysteine protease sanity panel"
