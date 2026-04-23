from __future__ import annotations

import json

from tools import build_wetlab_broad_screen_precision_monitor as mod


def test_build_wetlab_broad_screen_precision_monitor_tracks_progress_and_eta() -> None:
    payload = mod.build_payload(
        execution_queue={
            "summary": {"queue_row_count": 40, "resolved_row_count": 6, "running_row_count": 1, "first_actionable_target_id": "CA IX", "first_actionable_shard_id": "07_of_20"},
            "rows": [
                {"target_id": "CA IX", "shard_id": "01_of_20", "queue_status": "result_ready"},
                {"target_id": "CA IX", "shard_id": "02_of_20", "queue_status": "result_ready"},
                {"target_id": "CA IX", "shard_id": "03_of_20", "queue_status": "result_ready"},
                {"target_id": "CA IX", "shard_id": "04_of_20", "queue_status": "result_ready"},
                {"target_id": "CA IX", "shard_id": "05_of_20", "queue_status": "result_ready"},
                {"target_id": "CA IX", "shard_id": "06_of_20", "queue_status": "result_ready"},
                {
                    "target_id": "CA IX",
                    "shard_id": "07_of_20",
                    "queue_status": "running",
                    "progress_started_at": "2026-03-30T00:45:00",
                },
                {"target_id": "DprE1", "shard_id": "01_of_20", "queue_status": "blocked_on_previous_target"},
            ],
        },
        progress_payload={
            "summary": {"row_count": 7},
            "rows": [
                {"target_id": "CA IX", "shard_id": "01_of_20", "queue_status": "result_ready", "started_at": "2026-03-29T22:45:00", "completed_at": "2026-03-29T23:10:00"},
                {"target_id": "CA IX", "shard_id": "02_of_20", "queue_status": "result_ready", "started_at": "2026-03-29T23:11:00", "completed_at": "2026-03-29T23:32:00"},
                {"target_id": "CA IX", "shard_id": "03_of_20", "queue_status": "result_ready", "started_at": "2026-03-29T23:33:00", "completed_at": "2026-03-29T23:58:00"},
                {"target_id": "CA IX", "shard_id": "04_of_20", "queue_status": "result_ready", "started_at": "2026-03-29T23:59:00", "completed_at": "2026-03-30T00:18:00"},
                {"target_id": "CA IX", "shard_id": "05_of_20", "queue_status": "result_ready", "started_at": "2026-03-30T00:21:00", "completed_at": "2026-03-30T00:41:00"},
                {"target_id": "CA IX", "shard_id": "06_of_20", "queue_status": "result_ready", "started_at": "2026-03-30T00:45:00", "completed_at": "2026-03-30T01:02:00"},
                {"target_id": "CA IX", "shard_id": "07_of_20", "queue_status": "running", "started_at": "2026-03-30T01:04:00"},
            ],
        },
        rerank_payload={
            "summary": {"full_bulk_ready_target_count": 1, "partial_actual_target_count": 0},
            "rows": [
                {
                    "target_id": "CA IX",
                    "actual_row_count": 3,
                    "bootstrap_row_count": 0,
                    "actual_top3_count": 3,
                    "rerank_status": "full_bulk_top3_ready",
                    "top1_compound": "Acetazolamide",
                    "top2_compound": "Methazolamide",
                    "top3_compound": "Dichlorphenamide",
                }
            ],
        },
        source_payload={"rows": [{"target_id": "CA IX"}, {"target_id": "CA IX"}, {"target_id": "CA IX"}]},
        compound_universe={"summary": {"target_library_size": 100000, "deduped_compound_count": 105700}},
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_broad_screen_precision_monitor_ready"
    assert summary["resolved_shards"] == 6
    assert summary["running_shards"] == 1
    assert summary["focus_mode"] == "running"
    assert summary["focus_target_id"] == "CA IX"
    assert summary["focus_shard_id"] == "07_of_20"
    assert summary["active_target_id"] == "CA IX"
    assert summary["active_shard_id"] == "07_of_20"
    row = payload["rows"][0]
    assert row["target_id"] == "CA IX"
    assert row["completed_shards"] == 6
    assert row["rerank_status"] == "full_bulk_top3_ready"


def test_build_wetlab_broad_screen_precision_monitor_handles_stale_queue_summary() -> None:
    payload = mod.build_payload(
        execution_queue={
            "summary": {
                "queue_row_count": 40,
                "resolved_row_count": 6,
                "running_row_count": 0,
                "stale_row_count": 1,
                "first_actionable_target_id": "CA IX",
                "first_actionable_shard_id": "08_of_20",
                "first_actionable_queue_status": "stale_running_needs_recovery",
            },
            "rows": [
                {"target_id": "CA IX", "shard_id": "01_of_20", "queue_status": "result_ready"},
                {"target_id": "CA IX", "shard_id": "08_of_20", "queue_status": "stale_running_needs_recovery"},
            ],
        },
        progress_payload={"summary": {"row_count": 1}, "rows": [{"target_id": "CA IX", "shard_id": "01_of_20", "queue_status": "result_ready"}]},
        rerank_payload={"summary": {"full_bulk_ready_target_count": 0, "partial_actual_target_count": 0}, "rows": []},
        source_payload={"rows": []},
        compound_universe={"summary": {"target_library_size": 100000, "deduped_compound_count": 105700}},
    )
    assert payload["summary"]["running_shards"] == 0
    assert payload["summary"]["focus_mode"] == "stale"
    assert payload["summary"]["focus_target_id"] == "CA IX"
    assert payload["summary"]["focus_shard_id"] == "08_of_20"


def test_build_wetlab_broad_screen_precision_monitor_marks_dispatch_ready_without_fake_active_lane() -> None:
    payload = mod.build_payload(
        execution_queue={
            "summary": {
                "queue_row_count": 40,
                "resolved_row_count": 7,
                "running_row_count": 0,
                "first_actionable_target_id": "CA IX",
                "first_actionable_shard_id": "08_of_20",
                "first_actionable_queue_status": "ready_after_previous_shard",
            },
            "rows": [
                {"target_id": "CA IX", "shard_id": "01_of_20", "queue_status": "result_ready"},
                {"target_id": "CA IX", "shard_id": "08_of_20", "queue_status": "ready_after_previous_shard"},
            ],
        },
        progress_payload={"summary": {"row_count": 7}, "rows": [{"target_id": "CA IX", "shard_id": "01_of_20", "queue_status": "result_ready"}]},
        rerank_payload={"summary": {"full_bulk_ready_target_count": 1, "partial_actual_target_count": 0}, "rows": []},
        source_payload={"rows": []},
        compound_universe={"summary": {"target_library_size": 100000, "deduped_compound_count": 105700}},
    )
    summary = payload["summary"]
    assert summary["running_shards"] == 0
    assert summary["focus_mode"] == "dispatch_ready"
    assert summary["focus_target_id"] == "CA IX"
    assert summary["focus_shard_id"] == "08_of_20"
    assert summary["active_target_id"] == ""
    assert summary["active_shard_id"] == ""


def test_build_wetlab_broad_screen_precision_monitor_splits_success_and_hold_resolution(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    mapping_summary = tmp_path / "runs/wetlab_broad_screen_throughput/sars_cov_2_mpro/02_of_20/throughput_run_summary.json"
    mapping_summary.parent.mkdir(parents=True, exist_ok=True)
    mapping_summary.write_text(
        json.dumps(
            {
                "failed_stage": "stage1_ligand_mapping",
                "service_result": {"failed_stage": "stage1_ligand_mapping"},
            }
        ),
        encoding="utf-8",
    )
    gate_summary = tmp_path / "runs/wetlab_broad_screen_throughput/sars_cov_2_mpro/03_of_20/throughput_run_summary.json"
    gate_summary.parent.mkdir(parents=True, exist_ok=True)
    gate_summary.write_text(
        json.dumps(
            {
                "failed_stage": "stage6_operational_gate",
                "service_result": {"failed_stage": "stage6_operational_gate"},
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(
        execution_queue={
            "summary": {"queue_row_count": 4, "resolved_row_count": 3, "running_row_count": 1, "first_actionable_target_id": "SARS-CoV-2 Mpro", "first_actionable_shard_id": "04_of_20"},
            "rows": [
                {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "queue_status": "result_ready"},
                {"target_id": "SARS-CoV-2 Mpro", "shard_id": "02_of_20", "queue_status": "explicit_hold"},
                {"target_id": "SARS-CoV-2 Mpro", "shard_id": "03_of_20", "queue_status": "explicit_hold"},
                {"target_id": "SARS-CoV-2 Mpro", "shard_id": "04_of_20", "queue_status": "running"},
            ],
        },
        progress_payload={
            "rows": [
                {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "queue_status": "result_ready", "started_at": "2026-04-02T00:10:00", "completed_at": "2026-04-02T00:20:00"},
                {"target_id": "SARS-CoV-2 Mpro", "shard_id": "02_of_20", "queue_status": "explicit_hold", "started_at": "2026-04-02T00:21:00", "completed_at": "2026-04-02T00:23:00"},
                {"target_id": "SARS-CoV-2 Mpro", "shard_id": "03_of_20", "queue_status": "explicit_hold", "started_at": "2026-04-02T00:24:00", "completed_at": "2026-04-02T00:26:00"},
                {"target_id": "SARS-CoV-2 Mpro", "shard_id": "04_of_20", "queue_status": "running", "started_at": "2026-04-02T00:27:00"},
            ],
        },
        rerank_payload={"summary": {"full_bulk_ready_target_count": 0, "partial_actual_target_count": 0}, "rows": []},
        source_payload={"rows": []},
        compound_universe={"summary": {"target_library_size": 100000, "deduped_compound_count": 105700}},
    )
    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["successful_resolved_shards"] == 1
    assert summary["mapping_failed_resolved_shards"] == 1
    assert summary["gate_failed_resolved_shards"] == 1
    assert summary["hold_other_resolved_shards"] == 0
    assert summary["held_resolved_shards"] == 2
    assert summary["successful_completion_pct"] == 25.0
    assert summary["mapping_failed_completion_pct"] == 25.0
    assert summary["gate_failed_completion_pct"] == 25.0
    assert summary["hold_other_completion_pct"] == 0.0
    assert summary["held_completion_pct"] == 50.0
    assert row["completed_shards"] == 1
    assert row["mapping_failed_shards"] == 1
    assert row["gate_failed_shards"] == 1
    assert row["hold_other_shards"] == 0
    assert row["held_shards"] == 2
    assert row["successful_completion_pct"] == 25.0
    assert row["mapping_failed_completion_pct"] == 25.0
    assert row["gate_failed_completion_pct"] == 25.0
    assert row["hold_other_completion_pct"] == 0.0
    assert row["held_completion_pct"] == 50.0


def test_build_wetlab_broad_screen_precision_monitor_tracks_stk17b_retry_split() -> None:
    payload = mod.build_payload(
        execution_queue={
            "summary": {
                "queue_row_count": 20,
                "resolved_row_count": 12,
                "running_row_count": 0,
                "first_actionable_target_id": "STK17B (DRAK2)",
                "first_actionable_shard_id": "13_of_20",
                "first_actionable_queue_status": "ready_after_previous_shard",
            },
            "rows": [
                {"target_id": "STK17B (DRAK2)", "shard_id": "11_of_20", "queue_status": "explicit_hold"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "12_of_20", "queue_status": "explicit_hold"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "13_of_20", "queue_status": "ready_after_previous_shard"},
            ],
        },
        progress_payload={"summary": {"row_count": 12}, "rows": []},
        rerank_payload={"summary": {"full_bulk_ready_target_count": 1, "partial_actual_target_count": 0}, "rows": []},
        source_payload={"rows": []},
        compound_universe={"summary": {"target_library_size": 100000, "deduped_compound_count": 105700}},
        stk17b_manual_retry_lane={
            "summary": {
                "status": "wetlab_stk17b_manual_retry_lane_ready",
                "target_id": "STK17B (DRAK2)",
                "shard_id": "13_of_20",
                "campaign_start_shard_id": "12_of_20",
                "ready_for_manual_retry": True,
                "selected_command_kind": "throughput_preflight_tuned_gate55",
            }
        },
    )
    summary = payload["summary"]
    assert summary["stk17b_retry_ready_for_manual_retry"] is True
    assert summary["stk17b_retry_target_id"] == "STK17B (DRAK2)"
    assert summary["stk17b_retry_start_shard_id"] == "12_of_20"
    assert summary["stk17b_retry_total_seen_shards"] == 2
    assert summary["stk17b_retry_resolved_shards"] == 1
    assert summary["stk17b_retry_success_shards"] == 0
    assert summary["stk17b_retry_hold_shards"] == 1
    assert summary["stk17b_retry_running_shards"] == 0
    assert summary["stk17b_retry_success_pct"] == 0.0
    assert summary["stk17b_retry_hold_pct"] == 100.0
    assert summary["stk17b_retry_last_outcome"] == "hold"
    assert summary["stk17b_retry_last_outcome_shard_id"] == "12_of_20"
