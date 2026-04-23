from __future__ import annotations

from tools import build_wetlab_primary_hold_guard_surface as mod



def test_build_wetlab_primary_hold_guard_surface_flags_triggered_target() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {"queue_rank": 1, "target_id": "CA IX", "shard_id": "01_of_20", "queue_status": "result_ready", "notes": ""},
                {"queue_rank": 2, "target_id": "CA IX", "shard_id": "02_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
                {"queue_rank": 3, "target_id": "CA IX", "shard_id": "03_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
                {"queue_rank": 4, "target_id": "CA IX", "shard_id": "04_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
                {"queue_rank": 5, "target_id": "CA IX", "shard_id": "05_of_20", "queue_status": "ready_after_previous_shard", "notes": ""},
                {"queue_rank": 21, "target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "queue_status": "explicit_hold", "notes": "manual_pause"},
                {"queue_rank": 22, "target_id": "SARS-CoV-2 Mpro", "shard_id": "02_of_20", "queue_status": "result_ready", "notes": ""},
                {"queue_rank": 23, "target_id": "SARS-CoV-2 Mpro", "shard_id": "03_of_20", "queue_status": "ready_after_previous_shard", "notes": ""},
            ]
        },
        guard_limit=3,
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_primary_hold_guard_surface_ready"
    assert summary["guard_limit"] == 3
    assert summary["triggered_target_count"] == 1
    rows = {row["target_id"]: row for row in payload["rows"]}
    caix = rows["CA IX"]
    assert caix["total_auto_hold_count"] == 3
    assert caix["recent_consecutive_auto_hold_streak"] == 3
    assert caix["guard_triggered_now"] is True
    assert caix["last_auto_hold_shard_id"] == "04_of_20"
    assert caix["recommended_policy_action"] == "pause_target_autostart_and_review_retry_preset"

    mpro = rows["SARS-CoV-2 Mpro"]
    assert mpro["total_auto_hold_count"] == 0
    assert mpro["recent_consecutive_auto_hold_streak"] == 0
    assert mpro["guard_triggered_now"] is False
    assert mpro["recommended_policy_action"] == "continue_default_primary_watcher_policy"



def test_build_wetlab_primary_hold_guard_surface_handles_nontriggered_streak_and_fully_resolved_target() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {"queue_rank": 1, "target_id": "ALK2", "shard_id": "01_of_20", "queue_status": "result_ready", "notes": ""},
                {"queue_rank": 2, "target_id": "ALK2", "shard_id": "02_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
                {"queue_rank": 3, "target_id": "ALK2", "shard_id": "03_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
                {"queue_rank": 4, "target_id": "ALK2", "shard_id": "04_of_20", "queue_status": "running", "notes": ""},
                {"queue_rank": 41, "target_id": "T. cruzi PDE", "shard_id": "01_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
                {"queue_rank": 42, "target_id": "T. cruzi PDE", "shard_id": "02_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
            ]
        },
        guard_limit=3,
    )

    rows = {row["target_id"]: row for row in payload["rows"]}
    alk2 = rows["ALK2"]
    assert alk2["total_auto_hold_count"] == 2
    assert alk2["recent_consecutive_auto_hold_streak"] == 2
    assert alk2["guard_triggered_now"] is False
    assert alk2["last_auto_hold_shard_id"] == "03_of_20"
    assert alk2["recommended_policy_action"] == "prepare_target_specific_retry_preset_before_next_auto_start"

    tcruzi = rows["T. cruzi PDE"]
    assert tcruzi["total_auto_hold_count"] == 2
    assert tcruzi["recent_consecutive_auto_hold_streak"] == 2
    assert tcruzi["guard_triggered_now"] is False
    assert tcruzi["recommended_policy_action"] == "target_fully_resolved_no_guard_action_needed"
