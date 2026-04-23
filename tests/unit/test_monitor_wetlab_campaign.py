import datetime as dt
import json
import os
from pathlib import Path

from tools import monitor_wetlab_campaign as mon


class _FixedDateTime(dt.datetime):
    frozen_now = dt.datetime(2026, 3, 30, 3, 20, 0)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.frozen_now
        return cls.frozen_now.replace(tzinfo=tz)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _write_pid(path: Path, pid: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid if pid is not None else os.getpid()), encoding="utf-8")


def _write_exploratory_branch_artifacts(mon) -> None:
    _write_json(
        mon.DEFAULT_CATHEPSIN_EXPLORATORY_LANE_JSON,
        {
            "summary": {
                "status": "wetlab_cathepsin_k_exploratory_retry_lane_ready",
                "target_id": "Cathepsin K",
                "shard_id": "11_of_20",
                "lane_phase": "followup",
                "lane_label": "exploratory_gate4.5_followup",
                "ready_for_manual_retry": False,
                "prior_tuned_success_count": 2,
                "prior_tuned_hold_count": 8,
                "selected_threshold_A": 4.5,
            }
        },
    )
    _write_json(
        mon.DEFAULT_MPRO_EXPLORATORY_LANE_JSON,
        {
            "summary": {
                "status": "wetlab_sarscov2_mpro_exploratory_retry_lane_ready",
                "target_id": "SARS-CoV-2 Mpro",
                "shard_id": "01_of_20",
                "lane_label": "exploratory_gate4.5_candidate",
                "ready_for_manual_retry": True,
                "selected_threshold_A": 4.5,
            }
        },
    )
    _write_json(
        mon.DEFAULT_TCRUZI_PDE_EXPLORATORY_LANE_JSON,
        {
            "summary": {
                "status": "wetlab_tcruzi_pde_exploratory_retry_lane_ready",
                "target_id": "T. cruzi PDE",
                "shard_id": "07_of_20",
                "lane_label": "exploratory_gate5.1_candidate",
                "ready_for_manual_retry": True,
                "selected_threshold_A": 5.1,
            }
        },
    )


def _write_dengue_stage6_artifacts(mon) -> None:
    _write_json(
        mon.DEFAULT_CURRENT_RESULTS_INDEX_JSON,
        {
            "summary": {
                "dengue_stage6_retry_target_id": "Dengue NS2B-NS3 protease",
                "dengue_stage6_retry_lane_label": "stage6_followup_index",
                "dengue_stage6_retry_selected_command_kind": "throughput_preflight_tuned_gate51",
                "dengue_stage6_retry_selected_threshold_A": 5.1,
                "dengue_stage6_retry_status": "ready",
                "dengue_stage6_retry_next_required_step": "Run the Dengue NS2B-NS3 follow-up lane from current index.",
            }
        },
    )
    _write_json(
        mon.DEFAULT_DENGUE_STAGE6_TUNING_SURFACE_JSON,
        {
            "summary": {
                "target_id": "Dengue NS2B-NS3 protease",
                "recommended_observed_threshold_A": 5.5,
                "immediately_runnable_command_kind": "throughput_preflight_tuned_gate55",
                "next_required_step": "Tune Dengue stage6 from the dedicated surface.",
            }
        },
    )
    _write_json(
        mon.DEFAULT_DENGUE_EXPLORATORY_LANE_JSON,
        {
            "summary": {
                "target_id": "Dengue NS2B-NS3 protease",
                "lane_label": "exploratory_gate5.1_followup",
                "selected_command_kind": "throughput_preflight_tuned_gate55",
                "selected_threshold_A": 5.5,
                "ready_for_manual_retry": True,
            }
        },
    )
    _write_json(
        mon.DEFAULT_DENGUE_FOLLOWUP_LANE_JSON,
        {
            "summary": {
                "target_id": "Dengue NS2B-NS3 protease",
                "lane_label": "exploratory_gate5.1_followup",
                "selected_command_kind": "throughput_preflight_tuned_gate55",
                "selected_threshold_A": 5.5,
                "ready_for_manual_retry": True,
            }
        },
    )


def _write_dpre1_wave2_artifacts(mon) -> None:
    _write_json(
        mon.DEFAULT_DPRE1_RESULT_REVIEW_JSON,
        {
            "summary": {
                "status": "dpre1_result_review_ready",
                "target_id": "DprE1",
                "serialized_run_order": "3_of_5_in_wave2",
                "queue_status_now": "result_ready_for_successor",
                "next_required_step": "Advance DprE1 wave2 to successor gate.",
            }
        },
    )
    _write_json(
        mon.DEFAULT_DPRE1_RUN_RECORD_JSON,
        {
            "summary": {
                "status": "result_ready",
                "target_id": "DprE1",
                "serialized_run_order": "3_of_5_in_wave2",
                "execution_state": "result_ready",
                "queue_status_now": "result_ready_for_review",
                "successor_target": "T. cruzi KRS1",
            }
        },
    )
    _write_json(
        mon.DEFAULT_DPRE1_RESULT_SUMMARY_JSON,
        {
            "summary": {
                "status": "completed",
                "target_id": "DprE1",
                "action": "advance_to_successor_gate",
                "execution_state": "result_ready",
                "queue_status_now": "result_ready_for_successor",
                "successor_target": "T. cruzi KRS1",
            }
        },
    )


def test_refresh_mode_uses_light_or_full_script_sets(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon, "DEFAULT_LIGHT_REFRESH_SCRIPTS", ["tools/light_a.py"])
    monkeypatch.setattr(mon, "DEFAULT_FULL_REFRESH_SCRIPTS", ["tools/full_a.py", "tools/full_b.py"])

    calls: list[str] = []

    def _fake_run(cmd, cwd=None, check=None):
        calls.append(str(cmd[-1]))
        return None

    monkeypatch.setattr(mon.subprocess, "run", _fake_run)

    mon._refresh("light")
    assert calls == [str(tmp_path / "tools/light_a.py")]

    calls.clear()
    mon._refresh("full")
    assert calls == [str(tmp_path / "tools/full_a.py"), str(tmp_path / "tools/full_b.py")]

    calls.clear()
    mon._refresh("none")
    assert calls == []


def test_render_snapshot_shows_primary_and_counterscreen_rates(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon.dt, "datetime", _FixedDateTime)
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_MONITOR_JSON", tmp_path / "runs/wetlab_broad_screen_precision_monitor_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_QUEUE_JSON", tmp_path / "runs/wetlab_broad_screen_execution_queue_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_PROGRESS_JSON", tmp_path / "runs/wetlab_broad_screen_progress_current.json")
    monkeypatch.setattr(mon, "DEFAULT_ANTITARGET_QUEUE_JSON", tmp_path / "runs/wetlab_broad_screen_antitarget_execution_queue_current.json")
    monkeypatch.setattr(mon, "DEFAULT_ANTITARGET_PROGRESS_JSON", tmp_path / "runs/wetlab_broad_screen_antitarget_progress_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_WATCH_LOOP_PID", tmp_path / "runs/wetlab_broad_screen_primary_watch_loop.pid")
    monkeypatch.setattr(mon, "DEFAULT_ANTITARGET_WATCHER_LOOP_PID", tmp_path / "runs/wetlab_broad_screen_antitarget_watcher_loop.pid")
    monkeypatch.setattr(mon, "DEFAULT_ENGINEERING_JSON", tmp_path / "runs/wetlab_engineering_progress_current.json")
    monkeypatch.setattr(mon, "DEFAULT_STACK_JSON", tmp_path / "runs/wetlab_partnering_stack_current.json")
    monkeypatch.setattr(mon, "DEFAULT_HANDOFF_JSON", tmp_path / "runs/wetlab_master_handoff_dashboard_current.json")
    monkeypatch.setattr(mon, "DEFAULT_CURRENT_RESULTS_INDEX_JSON", tmp_path / "runs/wetlab_current_results_index_current.json")
    monkeypatch.setattr(mon, "DEFAULT_RERANK_JSON", tmp_path / "runs/wetlab_broad_screen_target_rerank_current.json")
    monkeypatch.setattr(mon, "DEFAULT_STABILITY_JSON", tmp_path / "runs/wetlab_broad_screen_stability_score_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRELAUNCH_JSON", tmp_path / "runs/sarscov2_mpro_broad_screen_prelaunch_current.json")
    monkeypatch.setattr(mon, "DEFAULT_CATHEPSIN_EXPLORATORY_LANE_JSON", tmp_path / "runs/wetlab_cathepsin_k_exploratory_retry_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_MPRO_EXPLORATORY_LANE_JSON", tmp_path / "runs/wetlab_sarscov2_mpro_exploratory_retry_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_TCRUZI_PDE_EXPLORATORY_LANE_JSON", tmp_path / "runs/wetlab_tcruzi_pde_exploratory_retry_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DENGUE_STAGE6_TUNING_SURFACE_JSON", tmp_path / "runs/wetlab_dengue_ns2b_ns3_stage6_tuning_surface_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DENGUE_EXPLORATORY_LANE_JSON", tmp_path / "runs/wetlab_dengue_ns2b_ns3_exploratory_retry_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DENGUE_FOLLOWUP_LANE_JSON", tmp_path / "runs/wetlab_dengue_ns2b_ns3_exploratory_followup_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DPRE1_RESULT_REVIEW_JSON", tmp_path / "runs/dpre1_result_review_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DPRE1_RUN_RECORD_JSON", tmp_path / "runs/dpre1_run_record_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DPRE1_RESULT_SUMMARY_JSON", tmp_path / "runs/dpre1_result_summary_current.json")
    monkeypatch.setattr(mon, "DEFAULT_MPRO_STAGE1_MAPPING_FIX_LANE_JSON", tmp_path / "runs/sarscov2_mpro_stage1_mapping_fix_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_TCRUZI_PDE_STAGE1_MAPPING_FIX_LANE_JSON", tmp_path / "runs/tcruzi_pde_stage1_mapping_fix_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_MAPPING_FIX_RETRY_RUNNER_JSON", tmp_path / "runs/wetlab_mapping_fix_retry_runner_current.json")
    monkeypatch.setattr(mon, "DEFAULT_MPRO_MAPPING_FIX_RETRY_RUNNER_JSON", tmp_path / "runs/wetlab_mapping_fix_retry_runner_mpro_current.json")
    monkeypatch.setattr(mon, "DEFAULT_TCRUZI_PDE_MAPPING_FIX_RETRY_RUNNER_JSON", tmp_path / "runs/wetlab_mapping_fix_retry_runner_tcruzi_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_EVENT_LOG", tmp_path / "runs/wetlab_broad_screen_runtime_event_log.jsonl")
    monkeypatch.setattr(mon, "DEFAULT_ANTITARGET_EVENT_LOG", tmp_path / "runs/wetlab_broad_screen_antitarget_runtime_event_log.jsonl")

    _write_json(
        mon.DEFAULT_PRIMARY_MONITOR_JSON,
        {
            "summary": {
                "resolved_shards": 7,
                "total_shards": 260,
                "running_shards": 1,
                "pending_shards": 252,
                "completion_pct": 2.7,
                "successful_resolved_shards": 4,
                "mapping_failed_resolved_shards": 2,
                "gate_failed_resolved_shards": 1,
                "hold_other_resolved_shards": 0,
                "successful_completion_pct": 1.5,
                "stk17b_retry_ready_for_manual_retry": True,
                "stk17b_retry_target_id": "STK17B (DRAK2)",
                "stk17b_retry_start_shard_id": "12_of_20",
                "stk17b_retry_total_seen_shards": 1,
                "stk17b_retry_resolved_shards": 1,
                "stk17b_retry_success_shards": 0,
                "stk17b_retry_hold_shards": 1,
                "stk17b_retry_running_shards": 0,
                "stk17b_retry_success_pct": 0.0,
                "stk17b_retry_hold_pct": 100.0,
                "stk17b_retry_last_outcome": "hold",
                "stk17b_retry_last_outcome_shard_id": "12_of_20",
                "full_bulk_ready_target_count": 1,
                "partial_actual_target_count": 0,
                "active_target_id": "CA IX",
                "active_shard_id": "08_of_20",
                "active_target_completion_pct": 35.0,
                "next_required_step": "Continue CA IX 08_of_20",
            },
            "rows": [
                {
                    "target_id": "CA IX",
                    "completed_shards": 7,
                    "total_shards": 20,
                    "completion_pct": 35.0,
                    "current_running_shard": "08_of_20",
                    "actual_top3_count": 3,
                    "rerank_status": "full_bulk_top3_ready",
                },
                {
                    "target_id": "SARS-CoV-2 Mpro",
                    "completed_shards": 0,
                    "total_shards": 20,
                    "completion_pct": 0.0,
                    "current_running_shard": "",
                    "actual_top3_count": 0,
                    "rerank_status": "bootstrap_only",
                },
            ],
        },
    )
    _write_json(
        mon.DEFAULT_PRIMARY_QUEUE_JSON,
        {
            "summary": {"resolved_row_count": 7, "running_row_count": 1},
            "rows": [
                {"target_id": "CA IX", "shard_id": "08_of_20", "queue_status": "running"},
                {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "queue_status": "running"},
                {"target_id": "T. cruzi PDE", "shard_id": "07_of_20", "queue_status": "explicit_hold"},
            ],
        },
    )
    _write_json(
        mon.DEFAULT_PRIMARY_PROGRESS_JSON,
        {
            "summary": {"row_count": 8},
            "rows": [
                {"target_id": "CA IX", "shard_id": "01_of_20", "queue_status": "result_ready", "started_at": "2026-03-29T22:45:00", "completed_at": "2026-03-29T23:10:00"},
                {"target_id": "CA IX", "shard_id": "02_of_20", "queue_status": "result_ready", "started_at": "2026-03-29T23:11:00", "completed_at": "2026-03-29T23:32:00"},
                {"target_id": "CA IX", "shard_id": "03_of_20", "queue_status": "result_ready", "started_at": "2026-03-29T23:33:00", "completed_at": "2026-03-29T23:58:00"},
                {"target_id": "CA IX", "shard_id": "04_of_20", "queue_status": "result_ready", "started_at": "2026-03-29T23:59:00", "completed_at": "2026-03-30T00:18:00"},
                {"target_id": "CA IX", "shard_id": "05_of_20", "queue_status": "result_ready", "started_at": "2026-03-30T00:21:00", "completed_at": "2026-03-30T00:41:00"},
                {"target_id": "CA IX", "shard_id": "06_of_20", "queue_status": "result_ready", "started_at": "2026-03-30T00:45:00", "completed_at": "2026-03-30T01:02:00"},
                {"target_id": "CA IX", "shard_id": "07_of_20", "queue_status": "result_ready", "started_at": "2026-03-30T01:04:00", "completed_at": "2026-03-30T02:15:00"},
                {"target_id": "CA IX", "shard_id": "08_of_20", "queue_status": "running", "started_at": "2026-03-30T03:05:00", "updated_at": "2026-03-30T03:05:00"},
            ],
        },
    )
    _write_json(
        mon.DEFAULT_ANTITARGET_QUEUE_JSON,
        {
            "summary": {
                "queue_row_count": 440,
                "resolved_row_count": 1,
                "running_row_count": 1,
                "first_actionable_primary_target_id": "CA IX",
                "first_actionable_anti_target_id": "CA II",
                "first_actionable_shard_id": "02_of_20",
                "first_actionable_queue_status": "running",
                "next_required_step": "Continue CA IX -> CA II 02_of_20",
            }
        },
    )
    _write_json(
        mon.DEFAULT_ANTITARGET_PROGRESS_JSON,
        {
            "summary": {"row_count": 2},
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "01_of_20",
                    "queue_status": "explicit_hold",
                    "started_at": "2026-03-30T02:20:00",
                    "completed_at": "2026-03-30T02:34:00",
                },
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "02_of_20",
                    "queue_status": "running",
                    "started_at": "2026-03-30T03:06:00",
                    "updated_at": "2026-03-30T03:06:00",
                },
            ],
        },
    )
    _write_json(mon.DEFAULT_ENGINEERING_JSON, {"summary": {"overall_progress_band": "active_buildout", "auto_append_ready": True, "anti_target_execution_queue_ready": True}})
    _write_json(mon.DEFAULT_STACK_JSON, {"summary": {"broad_screen_override_target_count": 13, "broad_screen_ingested_compound_count": 105700}})
    _write_json(
        mon.DEFAULT_HANDOFF_JSON,
        {
            "summary": {
                "next_required_step": "Continue the active broad-procurement shard for CA IX 08_of_20.",
                "broad_screen_target_retry_focus_target_id": "Leishmania braziliensis DHODH",
                "broad_screen_target_retry_focus_template_label": "gate51_branch_only_empirical",
                "broad_screen_target_retry_focus_selected_command_kind": "throughput_preflight_tuned_gate51",
                "broad_screen_target_retry_template_target_count": 6,
                "broad_screen_target_retry_empirical_validated_target_count": 2,
                "broad_screen_target_retry_focus_selected_threshold_A": 5.1,
                "broad_screen_mapping_fix_retry_focus_target_id": "SARS-CoV-2 Mpro",
                "broad_screen_mapping_fix_retry_focus_template_label": "mapping_fix_branch_only",
                "broad_screen_mapping_fix_retry_focus_selected_command_kind": "throughput_preflight",
                "broad_screen_mapping_fix_retry_template_target_count": 2,
                "broad_screen_mapping_fix_retry_ready_target_count": 2,
                "broad_screen_mapping_fix_retry_ready_targets": "SARS-CoV-2 Mpro; T. cruzi PDE",
            }
        },
    )
    _write_json(
        mon.DEFAULT_RERANK_JSON,
        {
            "rows": [
                {"target_id": "CA IX", "actual_row_count": 3},
                {"target_id": "SARS-CoV-2 Mpro", "actual_row_count": 0},
            ]
        },
    )
    _write_json(
        mon.DEFAULT_STABILITY_JSON,
        {
            "summary": {"stable_high_confidence_target_count": 0, "stable_provisional_target_count": 1},
            "rows": [
                {"target_id": "CA IX", "stability_score": 80.0, "stability_band": "stable_provisional"},
                {"target_id": "SARS-CoV-2 Mpro", "stability_score": 0.0, "stability_band": "no_actual_signal"},
            ],
        },
    )
    _write_json(
        mon.DEFAULT_PRELAUNCH_JSON,
        {
            "summary": {
                "target_id": "SARS-CoV-2 Mpro",
                "primary_shard_id": "01_of_20",
                "primary_queue_status": "blocked_on_previous_target",
                "anti_target_id": "host cysteine protease sanity panel",
            }
        },
    )
    _write_exploratory_branch_artifacts(mon)
    _write_dengue_stage6_artifacts(mon)
    _write_dpre1_wave2_artifacts(mon)
    _write_json(
        mon.DEFAULT_MPRO_STAGE1_MAPPING_FIX_LANE_JSON,
        {"summary": {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "ready_for_mapping_fix_retry": True, "selected_command_kind": "throughput_preflight"}},
    )
    _write_json(
        mon.DEFAULT_TCRUZI_PDE_STAGE1_MAPPING_FIX_LANE_JSON,
        {"summary": {"target_id": "T. cruzi PDE", "shard_id": "07_of_20", "ready_for_mapping_fix_retry": True, "selected_command_kind": "throughput_preflight"}},
    )
    _write_json(
        mon.DEFAULT_MAPPING_FIX_RETRY_RUNNER_JSON,
        {"summary": {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "mapping_fix_launch_completed": True}},
    )
    _write_json(
        mon.DEFAULT_MPRO_MAPPING_FIX_RETRY_RUNNER_JSON,
        {"summary": {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "mapping_fix_launch_completed": True}},
    )
    _write_json(
        mon.DEFAULT_TCRUZI_PDE_MAPPING_FIX_RETRY_RUNNER_JSON,
        {"summary": {"target_id": "T. cruzi PDE", "shard_id": "07_of_20", "mapping_fix_launch_completed": True}},
    )
    _write_jsonl(
        mon.DEFAULT_PRIMARY_EVENT_LOG,
        [
            {"event_timestamp": "2026-03-30T02:15:00", "event": "complete", "target_id": "CA IX", "shard_id": "07_of_20"},
            {"event_timestamp": "2026-03-30T03:05:00", "event": "start", "target_id": "CA IX", "shard_id": "08_of_20"},
        ],
    )
    _write_jsonl(
        mon.DEFAULT_ANTITARGET_EVENT_LOG,
        [
            {"event_timestamp": "2026-03-30T02:34:00", "event": "hold", "primary_target_id": "CA IX", "anti_target_id": "CA II", "primary_shard_id": "01_of_20"},
            {"event_timestamp": "2026-03-30T03:06:00", "event": "start", "primary_target_id": "CA IX", "anti_target_id": "CA II", "primary_shard_id": "02_of_20"},
        ],
    )
    _write_pid(mon.DEFAULT_PRIMARY_WATCH_LOOP_PID)
    _write_pid(mon.DEFAULT_ANTITARGET_WATCHER_LOOP_PID)

    text = mon.render_snapshot(mon._build_snapshot(), color=False, compact=False)

    assert "Wet-Lab Campaign Monitor" in text
    assert "success overall 2.12/h" in text
    assert "success recent 1.67/h" in text
    assert "resolved split" in text
    assert "success 4 | mapping 2 | gate 1 | other 0" in text
    assert "success med 21.0m" in text
    assert "success recent-med 20.0m" in text
    assert "CA IX 08_of_20" in text
    assert "CA IX -> CA II 02_of_20" in text
    assert "mode compute-attached" in text
    assert "primary watch" in text
    assert "watch loop attached yes" in text
    assert "generic retry" in text
    assert "gate51_branch_only_empirical" in text
    assert "mapping-fix" in text
    assert "mapping_fix_branch_only" in text
    assert "mpro fix lane" in text
    assert "tcruzi fix lane" in text
    assert "01_of_20 running | hb 0 ev 0" in text
    assert "07_of_20 explicit_hold | runner-launched" in text
    assert "stk17b retry" in text
    assert "success 0 (0.0%) | hold 1 (100.0%)" in text
    assert "SARS-CoV-2 Mpro 01_of_20" in text
    assert "stable_provisional" in text
    assert "signal start | age 15m" in text


def test_render_snapshot_supports_target_filter_and_compact(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon.dt, "datetime", _FixedDateTime)
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_MONITOR_JSON", tmp_path / "runs/wetlab_broad_screen_precision_monitor_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_QUEUE_JSON", tmp_path / "runs/wetlab_broad_screen_execution_queue_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_PROGRESS_JSON", tmp_path / "runs/wetlab_broad_screen_progress_current.json")
    monkeypatch.setattr(mon, "DEFAULT_ANTITARGET_QUEUE_JSON", tmp_path / "runs/wetlab_broad_screen_antitarget_execution_queue_current.json")
    monkeypatch.setattr(mon, "DEFAULT_ANTITARGET_PROGRESS_JSON", tmp_path / "runs/wetlab_broad_screen_antitarget_progress_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_WATCH_LOOP_PID", tmp_path / "runs/wetlab_broad_screen_primary_watch_loop.pid")
    monkeypatch.setattr(mon, "DEFAULT_ANTITARGET_WATCHER_LOOP_PID", tmp_path / "runs/wetlab_broad_screen_antitarget_watcher_loop.pid")
    monkeypatch.setattr(mon, "DEFAULT_ENGINEERING_JSON", tmp_path / "runs/wetlab_engineering_progress_current.json")
    monkeypatch.setattr(mon, "DEFAULT_STACK_JSON", tmp_path / "runs/wetlab_partnering_stack_current.json")
    monkeypatch.setattr(mon, "DEFAULT_HANDOFF_JSON", tmp_path / "runs/wetlab_master_handoff_dashboard_current.json")
    monkeypatch.setattr(mon, "DEFAULT_CURRENT_RESULTS_INDEX_JSON", tmp_path / "runs/wetlab_current_results_index_current.json")
    monkeypatch.setattr(mon, "DEFAULT_RERANK_JSON", tmp_path / "runs/wetlab_broad_screen_target_rerank_current.json")
    monkeypatch.setattr(mon, "DEFAULT_STABILITY_JSON", tmp_path / "runs/wetlab_broad_screen_stability_score_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRELAUNCH_JSON", tmp_path / "runs/sarscov2_mpro_broad_screen_prelaunch_current.json")
    monkeypatch.setattr(mon, "DEFAULT_CATHEPSIN_EXPLORATORY_LANE_JSON", tmp_path / "runs/wetlab_cathepsin_k_exploratory_retry_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_MPRO_EXPLORATORY_LANE_JSON", tmp_path / "runs/wetlab_sarscov2_mpro_exploratory_retry_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_TCRUZI_PDE_EXPLORATORY_LANE_JSON", tmp_path / "runs/wetlab_tcruzi_pde_exploratory_retry_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DENGUE_STAGE6_TUNING_SURFACE_JSON", tmp_path / "runs/wetlab_dengue_ns2b_ns3_stage6_tuning_surface_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DENGUE_EXPLORATORY_LANE_JSON", tmp_path / "runs/wetlab_dengue_ns2b_ns3_exploratory_retry_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DENGUE_FOLLOWUP_LANE_JSON", tmp_path / "runs/wetlab_dengue_ns2b_ns3_exploratory_followup_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DPRE1_RESULT_REVIEW_JSON", tmp_path / "runs/dpre1_result_review_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DPRE1_RUN_RECORD_JSON", tmp_path / "runs/dpre1_run_record_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DPRE1_RESULT_SUMMARY_JSON", tmp_path / "runs/dpre1_result_summary_current.json")
    monkeypatch.setattr(mon, "DEFAULT_MPRO_STAGE1_MAPPING_FIX_LANE_JSON", tmp_path / "runs/sarscov2_mpro_stage1_mapping_fix_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_TCRUZI_PDE_STAGE1_MAPPING_FIX_LANE_JSON", tmp_path / "runs/tcruzi_pde_stage1_mapping_fix_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_MAPPING_FIX_RETRY_RUNNER_JSON", tmp_path / "runs/wetlab_mapping_fix_retry_runner_current.json")
    monkeypatch.setattr(mon, "DEFAULT_MPRO_MAPPING_FIX_RETRY_RUNNER_JSON", tmp_path / "runs/wetlab_mapping_fix_retry_runner_mpro_current.json")
    monkeypatch.setattr(mon, "DEFAULT_TCRUZI_PDE_MAPPING_FIX_RETRY_RUNNER_JSON", tmp_path / "runs/wetlab_mapping_fix_retry_runner_tcruzi_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_EVENT_LOG", tmp_path / "runs/wetlab_broad_screen_runtime_event_log.jsonl")
    monkeypatch.setattr(mon, "DEFAULT_ANTITARGET_EVENT_LOG", tmp_path / "runs/wetlab_broad_screen_antitarget_runtime_event_log.jsonl")

    _write_json(
        mon.DEFAULT_PRIMARY_MONITOR_JSON,
        {
            "summary": {
                "resolved_shards": 7,
                "total_shards": 260,
                "running_shards": 1,
                "pending_shards": 252,
                "completion_pct": 2.7,
                "successful_resolved_shards": 4,
                "mapping_failed_resolved_shards": 2,
                "gate_failed_resolved_shards": 1,
                "hold_other_resolved_shards": 0,
                "successful_completion_pct": 1.5,
                "full_bulk_ready_target_count": 1,
                "partial_actual_target_count": 0,
                "active_target_id": "CA IX",
                "active_shard_id": "08_of_20",
                "active_target_completion_pct": 35.0,
                "next_required_step": "Continue CA IX 08_of_20",
            },
            "rows": [
                {"target_id": "CA IX", "completed_shards": 7, "total_shards": 20, "completion_pct": 35.0, "current_running_shard": "08_of_20", "actual_top3_count": 3, "rerank_status": "full_bulk_top3_ready"},
                {"target_id": "SARS-CoV-2 Mpro", "completed_shards": 0, "total_shards": 20, "completion_pct": 0.0, "current_running_shard": "", "actual_top3_count": 0, "rerank_status": "bootstrap_only"},
            ],
        },
    )
    _write_json(mon.DEFAULT_PRIMARY_QUEUE_JSON, {"summary": {"resolved_row_count": 7, "running_row_count": 1}})
    _write_json(
        mon.DEFAULT_PRIMARY_PROGRESS_JSON,
        {
            "rows": [
                {"target_id": "CA IX", "shard_id": "01_of_20", "queue_status": "result_ready", "started_at": "2026-03-29T22:45:00", "completed_at": "2026-03-29T23:10:00"},
                {"target_id": "CA IX", "shard_id": "02_of_20", "queue_status": "result_ready", "started_at": "2026-03-29T23:11:00", "completed_at": "2026-03-29T23:32:00"},
                {"target_id": "CA IX", "shard_id": "03_of_20", "queue_status": "result_ready", "started_at": "2026-03-29T23:33:00", "completed_at": "2026-03-29T23:58:00"},
                {"target_id": "CA IX", "shard_id": "04_of_20", "queue_status": "result_ready", "started_at": "2026-03-29T23:59:00", "completed_at": "2026-03-30T00:18:00"},
                {"target_id": "CA IX", "shard_id": "05_of_20", "queue_status": "result_ready", "started_at": "2026-03-30T00:21:00", "completed_at": "2026-03-30T00:41:00"},
                {"target_id": "CA IX", "shard_id": "06_of_20", "queue_status": "result_ready", "started_at": "2026-03-30T00:45:00", "completed_at": "2026-03-30T01:02:00"},
                {"target_id": "CA IX", "shard_id": "07_of_20", "queue_status": "result_ready", "started_at": "2026-03-30T01:04:00", "completed_at": "2026-03-30T02:15:00"},
                {"target_id": "CA IX", "shard_id": "08_of_20", "queue_status": "running", "started_at": "2026-03-30T03:05:00", "updated_at": "2026-03-30T03:05:00"},
                {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "queue_status": "running", "started_at": "2026-03-30T03:07:00", "updated_at": "2026-03-30T03:09:00", "heartbeat_count": 4, "event_count": 6},
                {"target_id": "T. cruzi PDE", "shard_id": "07_of_20", "queue_status": "explicit_hold", "started_at": "2026-03-30T02:00:00", "completed_at": "2026-03-30T02:10:00", "heartbeat_count": 2, "event_count": 3},
            ]
        },
    )
    _write_json(mon.DEFAULT_ANTITARGET_QUEUE_JSON, {"summary": {"queue_row_count": 440, "resolved_row_count": 1, "running_row_count": 1, "first_actionable_primary_target_id": "CA IX", "first_actionable_anti_target_id": "CA II", "first_actionable_shard_id": "02_of_20", "first_actionable_queue_status": "running"}})
    _write_json(mon.DEFAULT_ANTITARGET_PROGRESS_JSON, {"rows": [{"primary_target_id": "CA IX", "anti_target_id": "CA II", "primary_shard_id": "01_of_20", "queue_status": "explicit_hold", "started_at": "2026-03-30T02:20:00", "completed_at": "2026-03-30T02:34:00"}, {"primary_target_id": "CA IX", "anti_target_id": "CA II", "primary_shard_id": "02_of_20", "queue_status": "running", "started_at": "2026-03-30T03:06:00", "updated_at": "2026-03-30T03:06:00"}]})
    _write_json(mon.DEFAULT_ENGINEERING_JSON, {"summary": {"overall_progress_band": "active_buildout", "auto_append_ready": True, "anti_target_execution_queue_ready": True}})
    _write_json(mon.DEFAULT_STACK_JSON, {"summary": {"broad_screen_override_target_count": 13, "broad_screen_ingested_compound_count": 105700}})
    _write_json(
        mon.DEFAULT_HANDOFF_JSON,
        {
            "summary": {
                "next_required_step": "Continue CA IX",
                "broad_screen_target_retry_focus_target_id": "Leishmania braziliensis DHODH",
                "broad_screen_target_retry_focus_template_label": "gate51_branch_only_empirical",
                "broad_screen_target_retry_focus_selected_command_kind": "throughput_preflight_tuned_gate51",
                "broad_screen_target_retry_template_target_count": 6,
                "broad_screen_target_retry_empirical_validated_target_count": 2,
                "broad_screen_target_retry_focus_selected_threshold_A": 5.1,
                "broad_screen_mapping_fix_retry_focus_target_id": "SARS-CoV-2 Mpro",
                "broad_screen_mapping_fix_retry_focus_template_label": "mapping_fix_branch_only",
                "broad_screen_mapping_fix_retry_focus_selected_command_kind": "throughput_preflight",
                "broad_screen_mapping_fix_retry_template_target_count": 2,
                "broad_screen_mapping_fix_retry_ready_target_count": 2,
                "broad_screen_mapping_fix_retry_ready_targets": "SARS-CoV-2 Mpro; T. cruzi PDE",
            }
        },
    )
    _write_json(mon.DEFAULT_RERANK_JSON, {"rows": [{"target_id": "CA IX", "actual_row_count": 3}]})
    _write_json(mon.DEFAULT_STABILITY_JSON, {"summary": {"stable_high_confidence_target_count": 0, "stable_provisional_target_count": 1}, "rows": [{"target_id": "CA IX", "stability_score": 80.0, "stability_band": "stable_provisional"}]})
    _write_json(mon.DEFAULT_PRELAUNCH_JSON, {"summary": {"target_id": "SARS-CoV-2 Mpro", "primary_shard_id": "01_of_20", "primary_queue_status": "blocked_on_previous_target", "anti_target_id": "host cysteine protease sanity panel"}})
    _write_exploratory_branch_artifacts(mon)
    _write_dengue_stage6_artifacts(mon)
    _write_dpre1_wave2_artifacts(mon)
    _write_json(mon.DEFAULT_MPRO_STAGE1_MAPPING_FIX_LANE_JSON, {"summary": {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "ready_for_mapping_fix_retry": True, "selected_command_kind": "throughput_preflight"}})
    _write_json(mon.DEFAULT_TCRUZI_PDE_STAGE1_MAPPING_FIX_LANE_JSON, {"summary": {"target_id": "T. cruzi PDE", "shard_id": "07_of_20", "ready_for_mapping_fix_retry": True, "selected_command_kind": "throughput_preflight"}})
    _write_json(mon.DEFAULT_MAPPING_FIX_RETRY_RUNNER_JSON, {"summary": {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "mapping_fix_launch_completed": True}})
    _write_json(mon.DEFAULT_MPRO_MAPPING_FIX_RETRY_RUNNER_JSON, {"summary": {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "mapping_fix_launch_completed": True}})
    _write_json(mon.DEFAULT_TCRUZI_PDE_MAPPING_FIX_RETRY_RUNNER_JSON, {"summary": {"target_id": "T. cruzi PDE", "shard_id": "07_of_20", "mapping_fix_launch_completed": True}})
    _write_jsonl(mon.DEFAULT_PRIMARY_EVENT_LOG, [{"event_timestamp": "2026-03-30T03:05:00", "event": "start", "target_id": "CA IX", "shard_id": "08_of_20"}])
    _write_jsonl(mon.DEFAULT_ANTITARGET_EVENT_LOG, [{"event_timestamp": "2026-03-30T03:06:00", "event": "start", "primary_target_id": "CA IX", "anti_target_id": "CA II", "primary_shard_id": "02_of_20"}])
    _write_pid(mon.DEFAULT_PRIMARY_WATCH_LOOP_PID)
    _write_pid(mon.DEFAULT_ANTITARGET_WATCHER_LOOP_PID)

    text = mon.render_snapshot(mon._build_snapshot(target_filter="CA IX"), color=False, compact=True)

    assert "focus: CA IX" in text
    assert "CA IX 08_of_20" in text
    assert "CA IX -> CA II 02_of_20" in text
    assert "mode compute-attached" in text
    assert "watch loop attached yes" in text
    assert "generic retry" in text
    assert "mapping-fix" in text
    assert "cathepsin follow-up" in text
    assert "mpro gate4.5" in text
    assert "pde gate5.1" in text
    assert "dpre1 guard" in text
    assert "guarded gate5.1 | 3_of_5 | KRS1" in text
    assert "wave2" not in text
    assert "advance_to_successor_gate" not in text
    assert "map 2" in text
    assert "gate 1" in text
    assert "SARS-CoV-2 Mpro 01_of_20" in text
    assert "quality" in text

    dengue_text = mon._dengue_stage6_line(mon._build_snapshot(target_filter="CA IX"))
    assert "Dengue NS2B-NS3 protease" in dengue_text
    assert "stage6_followup_index" in dengue_text
    assert "throughput_preflight_tuned_gate51" in dengue_text
    assert "5.1A" in dengue_text

    mpro_text = mon.render_snapshot(mon._build_snapshot(target_filter="SARS-CoV-2 Mpro"), color=False, compact=True)
    assert "focus: SARS-CoV-2 Mpro" in mpro_text
    assert "mpro gate4.5" in mpro_text
    assert "ready | 01_of_20 | 4.5A" in mpro_text
    assert "pde gate5.1" in mpro_text
    assert "ready | 07_of_20 | 5.1A" in mpro_text

    pde_text = mon.render_snapshot(mon._build_snapshot(target_filter="T. cruzi PDE"), color=False, compact=True)
    assert "focus: T. cruzi PDE" in pde_text
    assert "pde gate5.1" in pde_text
    assert "ready | 07_of_20 | 5.1A" in pde_text
    assert "mpro gate4.5" in pde_text
    assert "ready | 01_of_20 | 4.5A" in pde_text

    success_only_text = mon.render_snapshot(mon._build_snapshot(target_filter="CA IX"), color=False, compact=True, success_only=True)
    assert "mode: success-only compact" in success_only_text
    assert "primary success" in success_only_text
    assert "counter success" in success_only_text
    assert "hold-rate" not in success_only_text
    assert "map " not in success_only_text
    assert "gate " not in success_only_text
    assert "hold med" not in success_only_text
    assert "hold recent-med" not in success_only_text
    assert "retry family" in success_only_text
    assert "map-fix family" in success_only_text
    assert "cathepsin follow-up" in success_only_text
    assert "Dengue NS2B-NS3 protease" in success_only_text
    assert "stage6_followup_index" in success_only_text
    assert "mpro gate4.5" in success_only_text
    assert "pde gate5.1" in success_only_text
    assert "dpre1 guard" in success_only_text
    assert "guarded gate5.1 | 3_of_5 | KRS1" in success_only_text
    assert "wave2" not in success_only_text
    assert "advance_to_successor_gate" not in success_only_text


def test_render_snapshot_shows_dispatch_ready_without_fake_running_lane(monkeypatch, tmp_path):
    monkeypatch.setattr(mon, "ROOT", tmp_path)
    monkeypatch.setattr(mon.dt, "datetime", _FixedDateTime)
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_MONITOR_JSON", tmp_path / "runs/wetlab_broad_screen_precision_monitor_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_QUEUE_JSON", tmp_path / "runs/wetlab_broad_screen_execution_queue_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_PROGRESS_JSON", tmp_path / "runs/wetlab_broad_screen_progress_current.json")
    monkeypatch.setattr(mon, "DEFAULT_ANTITARGET_QUEUE_JSON", tmp_path / "runs/wetlab_broad_screen_antitarget_execution_queue_current.json")
    monkeypatch.setattr(mon, "DEFAULT_ANTITARGET_PROGRESS_JSON", tmp_path / "runs/wetlab_broad_screen_antitarget_progress_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_WATCH_LOOP_PID", tmp_path / "runs/wetlab_broad_screen_primary_watch_loop.pid")
    monkeypatch.setattr(mon, "DEFAULT_ANTITARGET_WATCHER_LOOP_PID", tmp_path / "runs/wetlab_broad_screen_antitarget_watcher_loop.pid")
    monkeypatch.setattr(mon, "DEFAULT_ENGINEERING_JSON", tmp_path / "runs/wetlab_engineering_progress_current.json")
    monkeypatch.setattr(mon, "DEFAULT_STACK_JSON", tmp_path / "runs/wetlab_partnering_stack_current.json")
    monkeypatch.setattr(mon, "DEFAULT_HANDOFF_JSON", tmp_path / "runs/wetlab_master_handoff_dashboard_current.json")
    monkeypatch.setattr(mon, "DEFAULT_CURRENT_RESULTS_INDEX_JSON", tmp_path / "runs/wetlab_current_results_index_current.json")
    monkeypatch.setattr(mon, "DEFAULT_RERANK_JSON", tmp_path / "runs/wetlab_broad_screen_target_rerank_current.json")
    monkeypatch.setattr(mon, "DEFAULT_STABILITY_JSON", tmp_path / "runs/wetlab_broad_screen_stability_score_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRELAUNCH_JSON", tmp_path / "runs/sarscov2_mpro_broad_screen_prelaunch_current.json")
    monkeypatch.setattr(mon, "DEFAULT_CATHEPSIN_EXPLORATORY_LANE_JSON", tmp_path / "runs/wetlab_cathepsin_k_exploratory_retry_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_MPRO_EXPLORATORY_LANE_JSON", tmp_path / "runs/wetlab_sarscov2_mpro_exploratory_retry_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_TCRUZI_PDE_EXPLORATORY_LANE_JSON", tmp_path / "runs/wetlab_tcruzi_pde_exploratory_retry_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DENGUE_STAGE6_TUNING_SURFACE_JSON", tmp_path / "runs/wetlab_dengue_ns2b_ns3_stage6_tuning_surface_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DENGUE_EXPLORATORY_LANE_JSON", tmp_path / "runs/wetlab_dengue_ns2b_ns3_exploratory_retry_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DENGUE_FOLLOWUP_LANE_JSON", tmp_path / "runs/wetlab_dengue_ns2b_ns3_exploratory_followup_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DPRE1_RESULT_REVIEW_JSON", tmp_path / "runs/dpre1_result_review_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DPRE1_RUN_RECORD_JSON", tmp_path / "runs/dpre1_run_record_current.json")
    monkeypatch.setattr(mon, "DEFAULT_DPRE1_RESULT_SUMMARY_JSON", tmp_path / "runs/dpre1_result_summary_current.json")
    monkeypatch.setattr(mon, "DEFAULT_MPRO_STAGE1_MAPPING_FIX_LANE_JSON", tmp_path / "runs/sarscov2_mpro_stage1_mapping_fix_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_TCRUZI_PDE_STAGE1_MAPPING_FIX_LANE_JSON", tmp_path / "runs/tcruzi_pde_stage1_mapping_fix_lane_current.json")
    monkeypatch.setattr(mon, "DEFAULT_MAPPING_FIX_RETRY_RUNNER_JSON", tmp_path / "runs/wetlab_mapping_fix_retry_runner_current.json")
    monkeypatch.setattr(mon, "DEFAULT_MPRO_MAPPING_FIX_RETRY_RUNNER_JSON", tmp_path / "runs/wetlab_mapping_fix_retry_runner_mpro_current.json")
    monkeypatch.setattr(mon, "DEFAULT_TCRUZI_PDE_MAPPING_FIX_RETRY_RUNNER_JSON", tmp_path / "runs/wetlab_mapping_fix_retry_runner_tcruzi_current.json")
    monkeypatch.setattr(mon, "DEFAULT_PRIMARY_EVENT_LOG", tmp_path / "runs/wetlab_broad_screen_runtime_event_log.jsonl")
    monkeypatch.setattr(mon, "DEFAULT_ANTITARGET_EVENT_LOG", tmp_path / "runs/wetlab_broad_screen_antitarget_runtime_event_log.jsonl")

    _write_json(
        mon.DEFAULT_PRIMARY_MONITOR_JSON,
        {
            "summary": {
                "resolved_shards": 7,
                "total_shards": 260,
                "running_shards": 0,
                "pending_shards": 253,
                "completion_pct": 2.7,
                "full_bulk_ready_target_count": 1,
                "partial_actual_target_count": 0,
                "focus_mode": "dispatch_ready",
                "focus_target_id": "CA IX",
                "focus_shard_id": "08_of_20",
                "focus_queue_status": "ready_after_previous_shard",
                "focus_target_completion_pct": 35.0,
                "focus_target_remaining_shards": 13,
                "active_target_id": "",
                "active_shard_id": "",
                "next_required_step": "Dispatch CA IX 08_of_20",
            },
            "rows": [
                {
                    "target_id": "CA IX",
                    "completed_shards": 7,
                    "total_shards": 20,
                    "completion_pct": 35.0,
                    "current_running_shard": "",
                    "actual_top3_count": 3,
                    "rerank_status": "full_bulk_top3_ready",
                },
            ],
        },
    )
    _write_json(mon.DEFAULT_PRIMARY_QUEUE_JSON, {"summary": {"resolved_row_count": 7, "running_row_count": 0}})
    _write_json(
        mon.DEFAULT_PRIMARY_PROGRESS_JSON,
        {"rows": [{"target_id": "CA IX", "shard_id": "07_of_20", "queue_status": "result_ready", "started_at": "2026-03-30T01:04:00", "completed_at": "2026-03-30T02:15:00"}]},
    )
    _write_json(
        mon.DEFAULT_ANTITARGET_QUEUE_JSON,
        {"summary": {"queue_row_count": 440, "resolved_row_count": 1, "running_row_count": 0, "first_actionable_primary_target_id": "CA IX", "first_actionable_anti_target_id": "CA II", "first_actionable_shard_id": "02_of_20", "first_actionable_queue_status": "ready_after_previous_antitarget_resolution"}},
    )
    _write_json(mon.DEFAULT_ANTITARGET_PROGRESS_JSON, {"rows": []})
    _write_json(mon.DEFAULT_ENGINEERING_JSON, {"summary": {"overall_progress_band": "active_buildout", "auto_append_ready": True, "anti_target_execution_queue_ready": True}})
    _write_json(mon.DEFAULT_STACK_JSON, {"summary": {"broad_screen_override_target_count": 13, "broad_screen_ingested_compound_count": 105700}})
    _write_json(mon.DEFAULT_HANDOFF_JSON, {"summary": {"next_required_step": "Dispatch CA IX 08_of_20"}})
    _write_json(mon.DEFAULT_RERANK_JSON, {"rows": [{"target_id": "CA IX", "actual_row_count": 3}]})
    _write_json(mon.DEFAULT_STABILITY_JSON, {"summary": {"stable_high_confidence_target_count": 0, "stable_provisional_target_count": 1}, "rows": [{"target_id": "CA IX", "stability_score": 80.0, "stability_band": "stable_provisional"}]})
    _write_json(mon.DEFAULT_PRELAUNCH_JSON, {"summary": {"target_id": "SARS-CoV-2 Mpro", "primary_shard_id": "01_of_20", "primary_queue_status": "blocked_on_previous_target", "anti_target_id": "host cysteine protease sanity panel"}})
    _write_exploratory_branch_artifacts(mon)
    _write_json(mon.DEFAULT_MPRO_STAGE1_MAPPING_FIX_LANE_JSON, {"summary": {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "ready_for_mapping_fix_retry": True, "selected_command_kind": "throughput_preflight"}})
    _write_json(mon.DEFAULT_TCRUZI_PDE_STAGE1_MAPPING_FIX_LANE_JSON, {"summary": {"target_id": "T. cruzi PDE", "shard_id": "07_of_20", "ready_for_mapping_fix_retry": True, "selected_command_kind": "throughput_preflight"}})
    _write_dpre1_wave2_artifacts(mon)
    _write_json(mon.DEFAULT_MAPPING_FIX_RETRY_RUNNER_JSON, {"summary": {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "mapping_fix_launch_completed": True}})
    _write_json(mon.DEFAULT_MPRO_MAPPING_FIX_RETRY_RUNNER_JSON, {"summary": {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "mapping_fix_launch_completed": True}})
    _write_json(mon.DEFAULT_TCRUZI_PDE_MAPPING_FIX_RETRY_RUNNER_JSON, {"summary": {"target_id": "T. cruzi PDE", "shard_id": "07_of_20", "mapping_fix_launch_completed": True}})
    _write_jsonl(mon.DEFAULT_PRIMARY_EVENT_LOG, [{"event_timestamp": "2026-03-30T02:15:00", "event": "complete", "target_id": "CA IX", "shard_id": "07_of_20"}])
    _write_jsonl(mon.DEFAULT_ANTITARGET_EVENT_LOG, [])
    _write_pid(mon.DEFAULT_PRIMARY_WATCH_LOOP_PID)
    _write_pid(mon.DEFAULT_ANTITARGET_WATCHER_LOOP_PID)

    text = mon.render_snapshot(mon._build_snapshot(), color=False, compact=False)

    assert "CA IX 08_of_20" in text
    assert "dispatch-ready" in text
    assert "status ready_after_previous_shard" in text
    assert "watch loop attached yes" in text
