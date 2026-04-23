from __future__ import annotations

from tools import build_wetlab_broad_screen_compound_universe as universe_mod
from tools import build_wetlab_broad_screen_execution_queue as mod
from tools import build_wetlab_broad_screen_library_spec as library_mod
from tools import build_wetlab_broad_screen_queue as queue_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod


def test_build_wetlab_broad_screen_execution_queue_serializes_target_shards() -> None:
    portfolio = portfolio_mod.build_payload()
    library = library_mod.build_payload()
    broad_queue = queue_mod.build_payload(portfolio, library)
    universe = universe_mod.build_payload()

    payload = mod.build_payload(broad_queue, universe)
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_broad_screen_execution_queue_ready"
    assert summary["queue_row_count"] == 260
    assert summary["ready_now_row_count"] == 1
    assert summary["running_row_count"] == 0
    assert summary["first_actionable_target_id"] == "CA IX"
    assert summary["first_actionable_shard_id"] == "01_of_20"
    assert rows[0]["queue_status"] == "ready_first_shard"
    assert rows[20]["queue_status"] == "blocked_on_previous_target"


def test_build_wetlab_broad_screen_execution_queue_marks_stale_primary_row_for_recovery() -> None:
    payload = mod.build_payload(
        broad_queue={
            "summary": {"library_lane": "broad_procurement_100k"},
            "rows": [
                {"target_id": "CA IX", "shard_id": "01_of_20"},
                {"target_id": "CA IX", "shard_id": "02_of_20"},
            ],
        },
        compound_universe={"summary": {"target_library_size": 100000, "deduped_compound_count": 100000}},
        progress_payload={
            "rows": [
                {
                    "target_id": "CA IX",
                    "shard_id": "01_of_20",
                    "queue_status": "running",
                    "started_at": "2026-03-30T00:00:00",
                    "updated_at": "2026-03-30T00:00:00",
                }
            ]
        },
        stale_minutes=1.0,
    )

    summary = payload["summary"]
    assert summary["stale_row_count"] == 1
    assert summary["first_actionable_queue_status"] == "stale_running_needs_recovery"
    assert payload["rows"][0]["queue_status"] == "stale_running_needs_recovery"
    assert payload["rows"][1]["queue_status"] == "blocked_on_previous_shard"


def test_build_wetlab_broad_screen_execution_queue_advances_to_next_shard_after_result_ready() -> None:
    payload = mod.build_payload(
        broad_queue={
            "summary": {"library_lane": "broad_procurement_100k"},
            "rows": [
                {"target_id": "CA IX", "shard_id": "01_of_20"},
                {"target_id": "CA IX", "shard_id": "02_of_20"},
            ],
        },
        compound_universe={"summary": {"target_library_size": 100000, "deduped_compound_count": 100000}},
        progress_payload={
            "rows": [
                {
                    "target_id": "CA IX",
                    "shard_id": "01_of_20",
                    "queue_status": "result_ready",
                    "started_at": "2026-03-30T00:00:00",
                    "completed_at": "2026-03-30T00:05:00",
                }
            ]
        },
    )

    summary = payload["summary"]
    assert summary["resolved_row_count"] == 1
    assert summary["first_actionable_target_id"] == "CA IX"
    assert summary["first_actionable_shard_id"] == "02_of_20"
    assert summary["first_actionable_queue_status"] == "ready_after_previous_shard"
    assert summary["next_required_step"] == "Dispatch CA IX shard 02_of_20 through the broad-screen runtime runner."
    assert payload["rows"][0]["queue_status"] == "result_ready"
    assert payload["rows"][1]["queue_status"] == "ready_after_previous_shard"
