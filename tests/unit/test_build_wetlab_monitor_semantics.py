from __future__ import annotations

import json
from pathlib import Path

from tools import build_wetlab_monitor_semantics as mod

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_current_packet_summary(filename: str) -> dict:
    return json.loads((REPO_ROOT / "runs" / filename).read_text(encoding="utf-8"))["summary"]


def _assert_selected_allatom_commercial_schema(
    filename: str,
    *,
    expected_target_id: str,
    expected_decision_class: str,
    expected_risk_bucket: str,
    expected_primary_upgrade_actions: list[str],
) -> None:
    packet_summary = _load_current_packet_summary(filename)
    assert packet_summary["target_id"] == expected_target_id
    assert packet_summary["commercial_schema_version"] == "wetlab_commercial_grade_v1"
    assert packet_summary["commercial_hard_gate_pass_v1"] is False
    assert packet_summary["commercial_decision_class_v1"] == expected_decision_class
    assert packet_summary["commercial_risk_bucket_v1"] == expected_risk_bucket
    assert all(
        action in packet_summary["commercial_primary_upgrade_actions_v1"]
        for action in expected_primary_upgrade_actions
    )


def _assert_selected_allatom_commercial_v2_translation_contract(
    filename: str,
    *,
    expected_target_id: str,
    expected_translation_status: str,
    expected_shortlist_tier: str,
    expected_recommended_lane: str,
) -> dict:
    packet_summary = _load_current_packet_summary(filename)
    assert packet_summary["target_id"] == expected_target_id
    assert packet_summary["commercial_schema_version_v2"] == "wetlab_commercial_grade_v2"
    assert packet_summary["commercial_hard_gate_pass_v2"] is (expected_translation_status == "pass")
    assert round(float(packet_summary["commercial_overall_score_v2"]), 1) >= 50.0
    assert round(float(packet_summary["commercial_consistency_score_v2"]), 1) >= 60.0
    assert packet_summary["translation_gate_focus_status"] == expected_translation_status
    assert packet_summary["focus_shortlist_tier"] == expected_shortlist_tier
    assert packet_summary["recommended_next_expensive_lane"] == expected_recommended_lane
    return packet_summary


def test_build_wetlab_monitor_semantics_builds_success_hold_semantics(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)

    (runs / "wetlab_broad_screen_precision_monitor_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_broad_screen_precision_monitor_ready",
                    "target_count": 2,
                    "library_size": 100000,
                    "ingested_compound_count": 105700,
                    "total_shards": 40,
                    "resolved_shards": 12,
                    "successful_resolved_shards": 9,
                    "held_resolved_shards": 3,
                    "running_shards": 1,
                    "pending_shards": 27,
                    "completion_pct": 30.0,
                    "successful_completion_pct": 22.5,
                    "held_completion_pct": 7.5,
                    "focus_target_id": "CA IX",
                    "focus_shard_id": "07_of_20",
                    "focus_queue_status": "running",
                    "median_completed_shard_minutes": 20.0,
                    "recent_median_completed_shard_minutes": 18.0,
                    "focus_elapsed_minutes": 12.0,
                    "focus_signal_age_minutes": 0.0,
                    "focus_heartbeat_count": 3,
                    "focus_event_count": 5,
                    "focus_estimated_running_shard_pct": 60.0,
                },
                "rows": [
                    {
                        "target_id": "CA IX",
                        "completed_shards": 6,
                        "held_shards": 0,
                        "median_completed_shard_minutes": 20.0,
                        "recent_median_completed_shard_minutes": 18.0,
                        "hold_median_completed_shard_minutes": 0.0,
                    },
                    {
                        "target_id": "SARS-CoV-2 Mpro",
                        "completed_shards": 3,
                        "held_shards": 1,
                        "median_completed_shard_minutes": 22.0,
                        "recent_median_completed_shard_minutes": 21.0,
                        "hold_median_completed_shard_minutes": 17.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    (runs / "wetlab_broad_screen_execution_queue_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "queue_row_count": 40,
                    "resolved_row_count": 12,
                    "running_row_count": 1,
                    "first_actionable_target_id": "CA IX",
                    "first_actionable_shard_id": "07_of_20",
                    "first_actionable_queue_status": "running",
                },
                "rows": [
                    {"target_id": "CA IX", "shard_id": "07_of_20", "queue_status": "running"},
                ],
            }
        ),
        encoding="utf-8",
    )

    (runs / "wetlab_broad_screen_antitarget_execution_queue_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "queue_row_count": 20,
                    "ready_now_row_count": 0,
                    "running_row_count": 1,
                    "resolved_row_count": 4,
                    "first_actionable_primary_target_id": "CA IX",
                    "first_actionable_anti_target_id": "CA XII",
                    "first_actionable_shard_id": "02_of_20",
                    "first_actionable_queue_status": "running",
                },
                "rows": [
                    {"primary_target_id": "CA IX", "anti_target_id": "CA XII", "primary_shard_id": "02_of_20", "queue_status": "running"},
                ],
            }
        ),
        encoding="utf-8",
    )

    (runs / "wetlab_broad_screen_antitarget_progress_current.json").write_text(
        json.dumps(
            {
                "summary": {"status": "wetlab_broad_screen_antitarget_progress_ready", "row_count": 4, "running_row_count": 1, "resolved_row_count": 3},
                "rows": [
                    {"primary_target_id": "CA IX", "anti_target_id": "CA II", "primary_shard_id": "01_of_20", "queue_status": "result_ready", "started_at": "2026-04-01T01:00:00", "completed_at": "2026-04-01T01:10:00"},
                    {"primary_target_id": "CA IX", "anti_target_id": "CA II", "primary_shard_id": "02_of_20", "queue_status": "explicit_hold", "started_at": "2026-04-01T01:11:00", "completed_at": "2026-04-01T01:16:00"},
                    {"primary_target_id": "CA IX", "anti_target_id": "CA XII", "primary_shard_id": "01_of_20", "queue_status": "result_ready", "started_at": "2026-04-01T01:20:00", "completed_at": "2026-04-01T01:40:00"},
                ],
            }
        ),
        encoding="utf-8",
    )

    (runs / "wetlab_primary_stage6_failure_surface_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_primary_stage6_failure_surface_ready",
                    "target_count": 1,
                    "auto_hold_row_count": 3,
                    "stage1_mapping_failed_count": 1,
                    "stage6_failed_count": 2,
                    "max_stage6_distance_over_threshold_A": 2.0,
                },
                "rows": [
                    {"target_id": "SARS-CoV-2 Mpro", "auto_hold_row_count": 3, "stage1_mapping_failed_count": 1, "stage6_failed_count": 2, "recommended_action": "fix stage1 mapping contract before further auto-start"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (runs / "wetlab_lbdhodh_stage6_tuning_surface_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_lbdhodh_stage6_tuning_surface_ready",
                    "recommended_observed_threshold_A": 5.1,
                    "immediately_runnable_command_kind": "throughput_preflight_tuned_gate51",
                }
            }
        ),
        encoding="utf-8",
    )
    (runs / "wetlab_lbdhodh_exploratory_retry_lane_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_lbdhodh_exploratory_retry_lane_ready",
                    "target_id": "Leishmania braziliensis DHODH",
                    "shard_id": "20_of_20",
                    "ready_for_manual_retry": True,
                    "selected_command_kind": "throughput_preflight_tuned_gate51",
                    "lane_label": "exploratory_gate5.1_candidate",
                    "next_required_step": "Run the Leishmania braziliensis DHODH exploratory gate5.1 candidate retry for 20_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
                }
            }
        ),
        encoding="utf-8",
    )

    (runs / "wetlab_retry_handoff_summary_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_retry_handoff_summary_ready",
                    "manual_retry_focus_target_id": "STK17B (DRAK2)",
                    "manual_retry_focus_decision": "pause_auto_start",
                    "manual_retry_priority_targets": "STK17B (DRAK2) -> SARS-CoV-2 PLpro -> SARS-CoV-2 Mpro -> T. cruzi PDE -> ALK2",
                    "selected_manual_retry_target_id": "STK17B (DRAK2)",
                    "selected_manual_retry_shard_id": "18_of_20",
                    "selected_manual_retry_selected_command_kind": "throughput_preflight_tuned_gate45",
                    "selected_manual_retry_lane_label": "exploratory_gate4.5_followup",
                    "selected_rescue_branch_surface_label": "pde_rescue_only_branch",
                    "selected_rescue_branch_next_required_step": "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, and use the promoted top-4 packet as the review unit before any reopen decision.",
                    "current_results_next_required_step": "Run the STK17B (DRAK2) exploratory gate4.5 follow-up runner for 18_of_20; keep auto-start hard-frozen after the gate4.5 success and review shards 18-20 separately before reopening.",
                    "next_required_step": "Run the STK17B (DRAK2) exploratory gate4.5 follow-up runner for 18_of_20; keep auto-start hard-frozen after the gate4.5 success and review shards 18-20 separately before reopening.",
                }
            }
        ),
        encoding="utf-8",
    )
    (runs / "wetlab_stk17b_manual_retry_lane_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_stk17b_manual_retry_lane_ready",
                    "target_id": "STK17B (DRAK2)",
                    "shard_id": "05_of_20",
                    "ready_for_manual_retry": True,
                    "selected_command_kind": "throughput_preflight",
                    "next_required_step": "Run the STK17B (DRAK2) manual retry runner for 05_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
                }
            }
        ),
        encoding="utf-8",
    )
    (runs / "wetlab_plpro_manual_retry_lane_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_plpro_manual_retry_lane_ready",
                    "target_id": "SARS-CoV-2 PLpro",
                    "shard_id": "17_of_20",
                    "ready_for_manual_retry": True,
                    "selected_command_kind": "throughput_preflight_tuned_gate55",
                    "next_required_step": "Run the PLpro manual retry runner for 17_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
                }
            }
        ),
        encoding="utf-8",
    )
    (runs / "wetlab_kinase_retry_policy_templates_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_kinase_retry_policy_templates_ready",
                    "template_target_count": 3,
                    "empirical_validated_target_count": 1,
                    "gate45_only_target_count": 1,
                    "guarded_gate55_candidate_target_count": 1,
                    "focus_target_id": "STK17B (DRAK2)",
                    "focus_template_label": "gate45_branch_only_empirical",
                    "focus_selected_command_kind": "throughput_preflight_tuned_gate45",
                    "next_required_step": "Keep STK17B on the gate4.5 branch-only kinase template and leave ALK2 on the guarded gate55 template.",
                }
            }
        ),
        encoding="utf-8",
    )
    (runs / "wetlab_target_retry_policy_templates_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_target_retry_policy_templates_ready",
                    "template_target_count": 6,
                    "empirical_validated_target_count": 2,
                    "non_kinase_template_target_count": 3,
                    "focus_target_id": "Leishmania braziliensis DHODH",
                    "focus_template_label": "gate51_branch_only_empirical",
                    "focus_selected_command_kind": "throughput_preflight_tuned_gate51",
                    "focus_selected_threshold_A": 5.1,
                    "next_required_step": "Promote DHODH gate5.1 as validated, keep the default lane closed, and reserve any future DHODH reopen for an explicit new review.",
                }
            }
        ),
        encoding="utf-8",
    )
    (runs / "wetlab_mapping_fix_retry_policy_templates_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_mapping_fix_retry_policy_templates_ready",
                    "template_target_count": 2,
                    "ready_target_count": 2,
                    "ready_targets": "SARS-CoV-2 Mpro; T. cruzi PDE",
                    "focus_target_id": "SARS-CoV-2 Mpro",
                    "focus_template_label": "mapping_fix_branch_only",
                    "focus_selected_command_kind": "throughput_preflight",
                    "next_required_step": "Run the mapping-fix retry runner for SARS-CoV-2 Mpro 01_of_20; keep auto-start blocked until the mapping diagnostics rerun lands a clean summary.",
                }
            }
        ),
        encoding="utf-8",
    )
    (runs / "wetlab_stk17b_exploratory_followup_lane_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_stk17b_exploratory_followup_lane_ready",
                    "target_id": "STK17B (DRAK2)",
                    "shard_id": "18_of_20",
                    "ready_for_manual_retry": True,
                    "selected_command_kind": "throughput_preflight_tuned_gate45",
                    "followup_lane_label": "exploratory_gate4.5_followup",
                    "followup_shard_ids": "18_of_20;19_of_20;20_of_20",
                    "hard_freeze_state": "hard_freeze_after_exploratory_success",
                    "freeze_note": "Auto-start remains hard-frozen after the gate4.5 success; shards 18-20 are routed to the exploratory gate4.5 follow-up lane and should be reviewed separately before reopening.",
                    "next_required_step": "Run the STK17B (DRAK2) exploratory gate4.5 follow-up runner for 18_of_20; keep auto-start hard-frozen after the gate4.5 success and review shards 18-20 separately before reopening.",
                }
            }
        ),
        encoding="utf-8",
    )

    (runs / "wetlab_lbdhodh_gate51_validation_review_surface_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_lbdhodh_gate51_validation_review_surface_ready",
                    "target_id": "Leishmania braziliensis DHODH",
                    "promotion_label": "gate5.1_validated",
                    "gate51_validated": True,
                    "default_lane_reopen_allowed": False,
                    "branch_to_gate51_only": True,
                    "decision": "promote_gate51_validated_keep_default_closed",
                    "decision_rationale": "Default-lane shards 01_of_20-08_of_20 held, while gate5.1 validation shards starting at 09_of_20 all reached result_ready with HTVS_OK summaries, so DHODH should be promoted as validated and the default lane should remain closed.",
                    "gate51_validation_row_count": 12,
                    "gate51_validation_success_count": 12,
                    "validated_command_kind": "throughput_preflight_tuned_gate51",
                    "validated_threshold_A": 5.1,
                    "next_required_step": "Promote DHODH gate5.1 as validated, keep the default lane closed, and reserve any future DHODH reopen for an explicit new review.",
                }
            }
        ),
        encoding="utf-8",
    )
    (runs / "wetlab_dpre1_branch_review_surface_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_dpre1_branch_review_surface_ready",
                    "target_id": "DprE1",
                    "branch_label": "dpre1_guarded_review_branch",
                    "exploratory_retry_next_required_step": "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying.",
                    "next_required_step": "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying.",
                }
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(
        json.loads((runs / "wetlab_broad_screen_precision_monitor_current.json").read_text(encoding="utf-8")),
        json.loads((runs / "wetlab_broad_screen_execution_queue_current.json").read_text(encoding="utf-8")),
        json.loads((runs / "wetlab_broad_screen_antitarget_execution_queue_current.json").read_text(encoding="utf-8")),
        antitarget_progress=json.loads((runs / "wetlab_broad_screen_antitarget_progress_current.json").read_text(encoding="utf-8")),
        failure_surface=json.loads((runs / "wetlab_primary_stage6_failure_surface_current.json").read_text(encoding="utf-8")),
        retry_handoff_summary=json.loads((runs / "wetlab_retry_handoff_summary_current.json").read_text(encoding="utf-8")),
        dpre1_branch_review_surface=json.loads((runs / "wetlab_dpre1_branch_review_surface_current.json").read_text(encoding="utf-8")),
        lbdhodh_stage6_tuning_surface=json.loads((runs / "wetlab_lbdhodh_stage6_tuning_surface_current.json").read_text(encoding="utf-8")),
        lbdhodh_exploratory_retry_lane=json.loads((runs / "wetlab_lbdhodh_exploratory_retry_lane_current.json").read_text(encoding="utf-8")),
        lbdhodh_gate51_validation_review_surface=json.loads((runs / "wetlab_lbdhodh_gate51_validation_review_surface_current.json").read_text(encoding="utf-8")),
        stk17b_manual_retry_lane=json.loads((runs / "wetlab_stk17b_manual_retry_lane_current.json").read_text(encoding="utf-8")),
        stk17b_exploratory_followup_lane=json.loads((runs / "wetlab_stk17b_exploratory_followup_lane_current.json").read_text(encoding="utf-8")),
        plpro_manual_retry_lane=json.loads((runs / "wetlab_plpro_manual_retry_lane_current.json").read_text(encoding="utf-8")),
        kinase_retry_policy_templates=json.loads((runs / "wetlab_kinase_retry_policy_templates_current.json").read_text(encoding="utf-8")),
        target_retry_policy_templates=json.loads((runs / "wetlab_target_retry_policy_templates_current.json").read_text(encoding="utf-8")),
        mapping_fix_retry_policy_templates=json.loads((runs / "wetlab_mapping_fix_retry_policy_templates_current.json").read_text(encoding="utf-8")),
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_monitor_semantics_ready"
    assert summary["resolved_shards"] == 12
    assert summary["successful_resolved_shards"] == 9
    assert summary["held_resolved_shards"] == 3
    assert summary["resolved_share_success_pct"] == 75.0
    assert summary["resolved_share_held_pct"] == 25.0
    assert summary["primary_success_rate_shards_per_hour"] == 3.0
    assert summary["primary_hold_rate_shards_per_hour"] == 3.53
    assert summary["counter_success_rate_shards_per_hour"] == 4.0
    assert summary["guard_active"] is True
    assert summary["guard_hold_limit"] == 3
    assert summary["guard_blocked_target_id"] == "CA IX"
    assert summary["guard_hold_streak"] == 3
    assert "auto-start is blocked" in summary["guard_note"]
    assert summary["lbdhodh_gate51_validation_review_surface_ready"] is True
    assert summary["lbdhodh_gate51_validated"] is True
    assert summary["lbdhodh_gate51_validation_decision"] == "promote_gate51_validated_keep_default_closed"
    assert summary["lbdhodh_gate51_validation_validated_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["lbdhodh_gate51_validation_validated_threshold_A"] == 5.1
    assert summary["selected_validated_target_id"] == "Leishmania braziliensis DHODH"
    assert summary["selected_validated_surface_label"] == "gate5.1_validation_review"
    assert summary["selected_validated_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["selected_validated_threshold_A"] == 5.1
    assert summary["selected_validated_next_required_step"] == "Promote DHODH gate5.1 as validated, keep the default lane closed, and reserve any future DHODH reopen for an explicit new review."
    assert summary["dpre1_branch_review_ready"] is True
    assert summary["dpre1_branch_review_next_required_step"] == "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying."
    assert summary["selected_rescue_branch_surface_label"] == "pde_rescue_only_branch"
    assert summary["selected_rescue_branch_next_required_step"] == "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, and use the promoted top-4 packet as the review unit before any reopen decision."
    assert summary["stk17b_manual_retry_target_id"] == "STK17B (DRAK2)"
    assert summary["stk17b_manual_retry_shard_id"] == "05_of_20"
    assert summary["stk17b_manual_retry_selected_command_kind"] == "throughput_preflight"
    assert summary["stk17b_exploratory_followup_lane_label"] == "exploratory_gate4.5_followup"
    assert summary["stk17b_exploratory_followup_freeze_state"] == "hard_freeze_after_exploratory_success"
    assert summary["stk17b_exploratory_followup_freeze_note"].startswith("Auto-start remains hard-frozen after the gate4.5 success")
    assert summary["stk17b_followup_lane_label"] == "exploratory_gate4.5_followup"
    assert summary["stk17b_followup_freeze_state"] == "hard_freeze_after_exploratory_success"
    assert summary["stk17b_followup_freeze_note"].startswith("Auto-start remains hard-frozen after the gate4.5 success")
    assert summary["stk17b_followup_followup_shard_ids"] == "18_of_20;19_of_20;20_of_20"
    assert summary["kinase_retry_policy_templates_ready"] is True
    assert summary["kinase_retry_template_target_count"] == 3
    assert summary["kinase_retry_empirical_validated_target_count"] == 1
    assert summary["kinase_retry_gate45_only_target_count"] == 1
    assert summary["kinase_retry_guarded_gate55_candidate_target_count"] == 1
    assert summary["kinase_retry_focus_target_id"] == "STK17B (DRAK2)"
    assert summary["kinase_retry_focus_template_label"] == "gate45_branch_only_empirical"
    assert summary["kinase_retry_focus_selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["kinase_retry_next_required_step"].startswith("Keep STK17B on the gate4.5 branch-only kinase template")
    assert summary["target_retry_policy_templates_ready"] is True
    assert summary["target_retry_template_target_count"] == 6
    assert summary["target_retry_non_kinase_template_target_count"] == 3
    assert summary["target_retry_focus_target_id"] == "Leishmania braziliensis DHODH"
    assert summary["target_retry_focus_template_label"] == "gate51_branch_only_empirical"
    assert summary["target_retry_focus_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["target_retry_focus_selected_threshold_A"] == 5.1
    assert summary["mapping_fix_retry_policy_templates_ready"] is True
    assert summary["mapping_fix_retry_template_target_count"] == 2
    assert summary["mapping_fix_retry_ready_target_count"] == 2
    assert summary["mapping_fix_retry_ready_targets"] == "SARS-CoV-2 Mpro; T. cruzi PDE"
    assert summary["mapping_fix_retry_focus_target_id"] == "SARS-CoV-2 Mpro"
    assert summary["mapping_fix_retry_focus_template_label"] == "mapping_fix_branch_only"
    assert summary["mapping_fix_retry_focus_selected_command_kind"] == "throughput_preflight"
    assert summary["selected_manual_retry_target_id"] == "STK17B (DRAK2)"
    assert summary["selected_manual_retry_shard_id"] == "18_of_20"
    assert summary["selected_manual_retry_selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["selected_manual_retry_lane_label"] == "exploratory_gate4.5_followup"
    assert summary["primary_focus_shard_id"] == "18_of_20"
    assert summary["retry_focus_shard_id"] == "18_of_20"
    assert summary["next_required_step"] == "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying."
    assert "successful_resolved" in payload["markdown"]
    assert "held_resolved" in payload["markdown"]
    assert "Why It Can Look Fast" in payload["markdown"]
    assert "Guard Checklist" in payload["markdown"]
    assert "stk17b_followup_lane_label" in payload["markdown"]
    assert "hard_freeze_after_exploratory_success" in payload["markdown"]
    assert "generic_retry_templates" in payload["markdown"]
    assert "mapping_fix_retry_templates" in payload["markdown"]


def test_build_wetlab_monitor_semantics_surfaces_selected_allatom_v2_translation_and_shortlist(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)

    packet_summary = _assert_selected_allatom_commercial_v2_translation_contract(
        "wetlab_tcruzi_pde_allatom_review_packet_current.json",
        expected_target_id="T. cruzi PDE",
        expected_translation_status="pass",
        expected_shortlist_tier="tier2_silver",
        expected_recommended_lane="atomized_openmm_local_min_validated_repair",
    )

    selected_next_step = (
        "Selected all-atom delivery P0 is green; broader/default wetlab lane remains closed; "
        f"translation gate remains {packet_summary['translation_gate_focus_status']}; "
        f"next expensive lane {packet_summary['recommended_next_expensive_lane']}."
    )

    payload = mod.build_payload(
        {"summary": {"status": "wetlab_broad_screen_precision_monitor_ready"}},
        {"summary": {"status": "wetlab_broad_screen_execution_queue_ready"}},
        {"summary": {"status": "wetlab_broad_screen_antitarget_execution_queue_ready"}},
        {"summary": {"status": "wetlab_broad_screen_antitarget_progress_ready"}, "rows": []},
        {"summary": {"auto_hold_row_count": 0, "guard_hold_limit": 3}, "rows": []},
        retry_handoff_summary={
            "summary": {
                "status": "wetlab_retry_handoff_summary_ready",
                "selected_allatom_target_id": packet_summary["target_id"],
                "selected_allatom_surface_label": "tcruzi_pde_allatom_review_packet",
                "selected_allatom_selected_command_kind": "pseudo_allatom_backmapping_rescore",
                "selected_allatom_selected_threshold_A": 2.5,
                "selected_allatom_packet_scope": "partner_operator_allatom_rescue_review",
                "selected_allatom_packet_ready_for_operator_review": True,
                "selected_allatom_wetlab_gate_pass": False,
                "selected_allatom_wetlab_final_gate_pass": False,
                "selected_allatom_claim_gate_available": False,
                "selected_allatom_claim_ready_for_allatom": False,
                "selected_allatom_commercial_schema_version": packet_summary["commercial_schema_version_v2"],
                "selected_allatom_commercial_hard_gate_pass_v1": packet_summary["commercial_hard_gate_pass_v2"],
                "selected_allatom_commercial_soft_score_v1": packet_summary["commercial_soft_score_v2"],
                "selected_allatom_commercial_confidence_score_v1": packet_summary["commercial_confidence_score_v2"],
                "selected_allatom_commercial_overall_score_v1": packet_summary["commercial_overall_score_v2"],
                "selected_allatom_commercial_risk_bucket_v1": packet_summary["commercial_risk_bucket_v2"],
                "selected_allatom_commercial_decision_class_v1": packet_summary["commercial_decision_class_v2"],
                "selected_allatom_commercial_primary_upgrade_actions_v1": list(
                    packet_summary["commercial_primary_upgrade_actions_v2"]
                ),
                "selected_allatom_translation_gate_reason": packet_summary["translation_gate_focus_reason"],
                "selected_allatom_recommended_next_expensive_lane_reason": packet_summary[
                    "recommended_next_expensive_lane_reason"
                ],
                "selected_allatom_best_compound_name": "chembl_cache_e6069e85050b",
                "selected_allatom_best_compound_name_resolution": "cache_placeholder",
                "selected_allatom_best_mean_min_distance_A": 3.705,
                "selected_allatom_promoted_candidate_count": 4,
                "selected_allatom_under_2p5_candidate_count": 0,
                "selected_allatom_near_candidate_count": 2,
                "selected_allatom_next_required_step": selected_next_step,
            }
        },
    )

    summary = payload["summary"]
    assert summary["selected_allatom_commercial_schema_version"] == "wetlab_commercial_grade_v2"
    assert summary["selected_allatom_translation_gate_reason"] == packet_summary["translation_gate_focus_reason"]
    assert summary["selected_allatom_recommended_next_expensive_lane_reason"] == packet_summary[
        "recommended_next_expensive_lane_reason"
    ]
    assert summary["selected_allatom_raw_claim_requirement_mode"] == "semi_hard"
    assert summary["selected_allatom_raw_claim_required_for_final_wetlab"] is True
    assert summary["selected_allatom_effective_actionability_status"] == "semi_hard_blocked"
    assert summary["selected_allatom_effective_actionability_claim_requirement_mode"] == "semi_hard"
    assert summary["selected_allatom_effective_blocking_order"] == "claim_block_first"
    assert summary["selected_allatom_effective_primary_blocking_domain"] == "claim_equivalence"
    assert "recompute_mean_min_distance_A" not in summary["selected_allatom_action_recipe_codes"]
    assert not any(
        row.get("category") == "translation_commercial_hard_gate"
        for row in summary["selected_allatom_action_recipe_rows"]
    )
    assert packet_summary["recommended_next_expensive_lane_reason"] in summary["selected_allatom_translation_human_summary"]
    assert summary["selected_allatom_next_required_step"] == selected_next_step
    assert "translation gate remains pass" in summary["selected_allatom_next_required_step"]
    assert "broader/default wetlab lane remains closed" in summary["selected_allatom_next_required_step"]
    assert "atomized_openmm_local_min_validated_repair" in summary["selected_allatom_next_required_step"]
    assert "translation gate remains pass" in payload["markdown"]
    assert "broader/default wetlab lane remains closed" in payload["markdown"]
    assert "atomized_openmm_local_min_validated_repair" in payload["markdown"]


def test_build_wetlab_monitor_semantics_prefers_krs1_guarded_review_when_focus_matches(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)

    payload = mod.build_payload(
        {
            "summary": {
                "status": "wetlab_broad_screen_precision_monitor_ready",
                "focus_target_id": "T. cruzi KRS1",
                "focus_shard_id": "09_of_20",
                "focus_queue_status": "running",
                "resolved_shards": 1,
                "successful_resolved_shards": 1,
                "held_resolved_shards": 0,
                "total_shards": 2,
            },
            "rows": [],
        },
        {"summary": {"status": "wetlab_broad_screen_execution_queue_ready"}, "rows": []},
        {"summary": {"status": "wetlab_broad_screen_antitarget_execution_queue_ready"}, "rows": []},
        {"summary": {"status": "wetlab_broad_screen_antitarget_progress_ready"}, "rows": []},
        {"summary": {"status": "wetlab_primary_stage6_failure_surface_ready", "auto_hold_row_count": 3, "guard_hold_limit": 3}},
        {"summary": {"status": "wetlab_retry_handoff_summary_ready"}},
        dpre1_branch_review_surface={
            "summary": {
                "status": "wetlab_dpre1_branch_review_surface_ready",
                "target_id": "DprE1",
                "branch_label": "dpre1_guarded_review_branch",
                "branch_state": "guarded_gate51_review_default_lane_closed",
                "source_priority": "result_review",
                "decision_source_priority": "result_summary",
                "stage6_tuning_recommended_threshold_A": 5.05,
                "exploratory_retry_selected_threshold_A": 5.1,
                "successor_target": "T. cruzi KRS1",
                "successor_gate_state": "blocked_pending_dpre1_guarded_review",
                "next_required_step": "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying.",
            }
        },
        tcruzi_krs1_branch_review_surface={
            "summary": {
                "status": "wetlab_tcruzi_krs1_branch_review_surface_ready",
                "target_id": "T. cruzi KRS1",
                "branch_label": "tcruzi_krs1_guarded_gate51_branch",
                "branch_state": "guarded_gate51_review_default_lane_closed",
                "source_priority": "guarded_branch_summary",
                "decision_source_priority": "guarded_operator_packet",
                "stage6_tuning_recommended_threshold_A": 5.05,
                "stage6_tuning_immediately_runnable_command_kind": "throughput_preflight_tuned_gate51",
                "stage6_tuning_next_required_step": "Run the T. cruzi KRS1 exploratory gate5.1 retry for 09_of_20; use gate5.1 as the immediately runnable family for the observed 5.05A band and keep the default lane closed until the result is reviewed.",
                "exploratory_retry_lane_ready": True,
                "exploratory_source_priority": "exploratory_lane",
                "exploratory_retry_lane_label": "exploratory_gate5.1_candidate",
                "exploratory_retry_selected_command_kind": "throughput_preflight_tuned_gate51",
                "exploratory_retry_selected_threshold_A": 5.1,
                "exploratory_retry_next_required_step": "Keep the T. cruzi KRS1 default lane paused and refresh the stage6 tuning surface before retrying.",
                "successor_target": "LRRK2",
                "successor_gate_state": "blocked_pending_tcruzi_krs1_guarded_review",
                "next_required_step": "Keep the T. cruzi KRS1 default lane paused and refresh the stage6 tuning surface before retrying.",
                "branch_review_ready": True,
            }
        },
    )
    summary = payload["summary"]
    assert summary["primary_focus_target_id"] == "T. cruzi KRS1"
    assert summary["guard_blocked_target_id"] == "T. cruzi KRS1"
    assert summary["krs1_branch_review_ready"] is True
    assert summary["selected_krs1_branch_review_target_id"] == "T. cruzi KRS1"
    assert summary["selected_krs1_branch_review_surface_label"] == "krs1_branch_review_surface"
    assert summary["selected_krs1_branch_review_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["selected_krs1_branch_review_selected_threshold_A"] == 5.1
    assert summary["selected_krs1_branch_review_next_required_step"] == "Keep the T. cruzi KRS1 default lane paused and refresh the stage6 tuning surface before retrying."
    assert summary["next_required_step"] == "Keep the T. cruzi KRS1 default lane paused and refresh the stage6 tuning surface before retrying."
    assert summary["dpre1_branch_review_next_required_step"] == "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying."
    assert summary["krs1_branch_review_successor_target"] == "LRRK2"


def test_build_wetlab_monitor_semantics_tracks_selected_allatom_commercial_packet_schema(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    payload = mod.build_payload(
        {
            "summary": {
                "status": "wetlab_broad_screen_precision_monitor_ready",
                "focus_target_id": "Cathepsin K",
                "focus_shard_id": "19_of_20",
                "focus_queue_status": "running",
                "resolved_shards": 1,
                "successful_resolved_shards": 1,
                "held_resolved_shards": 0,
            },
            "rows": [],
        },
        {"summary": {"status": "wetlab_broad_screen_execution_queue_ready"}, "rows": []},
        {"summary": {"status": "wetlab_broad_screen_antitarget_execution_queue_ready"}, "rows": []},
        {"summary": {"status": "wetlab_broad_screen_antitarget_progress_ready"}, "rows": []},
        {"summary": {"status": "wetlab_primary_stage6_failure_surface_ready", "auto_hold_row_count": 0, "guard_hold_limit": 3}},
        {
            "summary": {
                "status": "wetlab_retry_handoff_summary_ready",
                "allatom_family_ready": True,
                "allatom_family_target_count": 1,
                "allatom_family_surface_count": 1,
                "allatom_family_focus_target_id": "Cathepsin K",
                "allatom_family_focus_surface_label": "cathepsin_k_allatom_review_packet",
                "selected_allatom_target_id": "Cathepsin K",
                "selected_allatom_surface_label": "cathepsin_k_allatom_review_packet",
                "selected_allatom_selected_command_kind": "allatom_refinement",
                "selected_allatom_selected_threshold_A": 2.5,
                "selected_allatom_packet_scope": "selected_allatom_review_packet",
                "selected_allatom_packet_ready_for_operator_review": True,
                "selected_allatom_wetlab_gate_pass": False,
                "selected_allatom_wetlab_final_gate_pass": False,
                "selected_allatom_claim_gate_available": True,
                "selected_allatom_claim_ready_for_allatom": False,
                "selected_allatom_readiness_semantics": "explicit_split_gate_fields",
                "selected_allatom_best_compound_name": "Cathepsin Lead",
                "selected_allatom_best_compound_name_human_readable": "Cathepsin Lead",
                "selected_allatom_best_compound_name_resolution": "human_readable",
                "selected_allatom_best_mean_min_distance_A": 1.234,
                "selected_allatom_promoted_candidate_count": 4,
                "selected_allatom_under_2p5_candidate_count": 1,
                "selected_allatom_near_candidate_count": 3,
                "selected_allatom_next_required_step": "Review Cathepsin K selected all-atom packet before any wetlab decision.",
            }
        },
        {"summary": {}},
    )

    summary = payload["summary"]
    assert summary["allatom_family_ready"] is True
    assert summary["allatom_family_focus_target_id"] == "Cathepsin K"
    assert summary["selected_allatom_target_id"] == "Cathepsin K"
    assert summary["selected_allatom_surface_label"] == "cathepsin_k_allatom_review_packet"
    assert summary["selected_allatom_packet_ready_for_operator_review"] is True
    assert summary["selected_allatom_wetlab_gate_pass"] is False
    assert summary["selected_allatom_wetlab_final_gate_pass"] is False
    assert summary["selected_allatom_claim_gate_available"] is True
    assert summary["selected_allatom_claim_ready_for_allatom"] is False
    assert summary["selected_allatom_readiness_semantics"] == "explicit_split_gate_fields"
    assert summary["selected_allatom_actionability_status"] == "semi_hard_blocked"
    assert summary["selected_allatom_actionability_claim_requirement_mode"] == "semi_hard"
    assert summary["selected_allatom_actionability_claim_requirement_status"] == "blocked"
    assert "resolve_claim_equivalence_gate" in summary["selected_allatom_actionability_required_calculations_text"]
    assert "Actionability:" in summary["selected_allatom_human_summary"]
    assert summary["selected_allatom_best_compound_name_resolution"] == "human_readable"
    assert summary["selected_allatom_next_required_step"] == "Review Cathepsin K selected all-atom packet before any wetlab decision."
    assert any(row["topic"] == "allatom_family" for row in payload["rows"])
    assert any(row["topic"] == "selected_allatom_actionability" for row in payload["rows"])
    _assert_selected_allatom_commercial_schema(
        "wetlab_cathepsin_k_allatom_review_packet_current.json",
        expected_target_id="Cathepsin K",
        expected_decision_class="commercial_recycle_or_rework",
        expected_risk_bucket="critical",
        expected_primary_upgrade_actions=[
            "tighten_pose_geometry_under_strict_gate",
            "raise_trajectory_stability",
            "increase_trajectory_support",
        ],
    )


def test_build_wetlab_monitor_semantics_keeps_selected_krs1_review_fields_after_successor_shift() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "wetlab_broad_screen_precision_monitor_ready", "focus_target_id": "LRRK2", "focus_shard_id": "02_of_20", "resolved_shards": 1, "successful_resolved_shards": 1, "held_resolved_shards": 0}},
        {"summary": {"first_actionable_target_id": "LRRK2", "first_actionable_shard_id": "02_of_20", "first_actionable_queue_status": "ready_after_previous_shard"}, "rows": []},
        {"summary": {"first_actionable_primary_target_id": "", "first_actionable_anti_target_id": "", "first_actionable_shard_id": "", "first_actionable_queue_status": ""}, "rows": []},
        {"summary": {}, "rows": []},
        {"summary": {}, "rows": []},
        {
            "summary": {
                "status": "wetlab_retry_handoff_summary_ready",
                "selected_krs1_branch_review_target_id": "T. cruzi KRS1",
                "selected_krs1_branch_review_branch_label": "tcruzi_krs1_guarded_gate51_branch",
                "selected_krs1_branch_review_branch_state": "guarded_gate51_validated_default_lane_closed",
                "selected_krs1_branch_review_selected_command_kind": "throughput_preflight_tuned_gate51",
                "selected_krs1_branch_review_selected_threshold_A": 5.1,
                "selected_krs1_branch_review_next_required_step": "Promote T. cruzi KRS1 guarded gate5.1 as validated, keep the default lane closed, and allow LRRK2 to continue as the successor broad lane.",
                "next_required_step": "Promote T. cruzi KRS1 guarded gate5.1 as validated, keep the default lane closed, and allow LRRK2 to continue as the successor broad lane.",
            }
        },
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        {
            "summary": {
                "status": "wetlab_tcruzi_krs1_branch_review_surface_ready",
                "target_id": "T. cruzi KRS1",
                "branch_label": "tcruzi_krs1_guarded_gate51_branch",
                "branch_state": "guarded_gate51_validated_default_lane_closed",
                "exploratory_retry_selected_command_kind": "throughput_preflight_tuned_gate51",
                "exploratory_retry_selected_threshold_A": 5.1,
                "next_required_step": "Promote T. cruzi KRS1 guarded gate5.1 as validated, keep the default lane closed, and allow LRRK2 to continue as the successor broad lane.",
            }
        },
    )

    summary = payload["summary"]
    assert summary["primary_focus_target_id"] == "LRRK2"
    assert summary["selected_krs1_branch_review_target_id"] == "T. cruzi KRS1"
    assert summary["selected_krs1_branch_review_branch_state"] == "guarded_gate51_validated_default_lane_closed"
    assert summary["selected_krs1_branch_review_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["selected_krs1_branch_review_selected_threshold_A"] == 5.1
    assert summary["selected_krs1_branch_review_next_required_step"].startswith("Promote T. cruzi KRS1 guarded gate5.1 as validated")
    assert summary["next_required_step"].startswith("Promote T. cruzi KRS1 guarded gate5.1 as validated")


def test_build_wetlab_monitor_semantics_uses_followup_shard_scope_when_blocked_review_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)

    (runs / "wetlab_broad_screen_precision_monitor_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_broad_screen_precision_monitor_ready",
                    "resolved_shards": 1,
                    "successful_resolved_shards": 0,
                    "held_resolved_shards": 1,
                    "focus_target_id": "STK17B (DRAK2)",
                    "focus_shard_id": "20_of_20",
                },
                "rows": [],
            }
        ),
        encoding="utf-8",
    )
    (runs / "wetlab_broad_screen_execution_queue_current.json").write_text(
        json.dumps({"summary": {"status": "wetlab_broad_screen_execution_queue_ready"}, "rows": []}),
        encoding="utf-8",
    )
    (runs / "wetlab_broad_screen_antitarget_execution_queue_current.json").write_text(
        json.dumps({"summary": {"status": "wetlab_broad_screen_antitarget_execution_queue_ready"}, "rows": []}),
        encoding="utf-8",
    )
    (runs / "wetlab_broad_screen_antitarget_progress_current.json").write_text(
        json.dumps({"summary": {"status": "wetlab_broad_screen_antitarget_progress_ready"}, "rows": []}),
        encoding="utf-8",
    )
    (runs / "wetlab_primary_stage6_failure_surface_current.json").write_text(
        json.dumps({"summary": {"status": "wetlab_primary_stage6_failure_surface_ready"}, "rows": []}),
        encoding="utf-8",
    )
    (runs / "wetlab_retry_handoff_summary_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_retry_handoff_summary_ready",
                    "selected_manual_retry_target_id": "STK17B (DRAK2)",
                    "selected_manual_retry_shard_id": "18_of_20;19_of_20;20_of_20",
                    "selected_manual_retry_selected_command_kind": "throughput_preflight_tuned_gate45",
                    "selected_manual_retry_lane_label": "exploratory_gate4.5_followup",
                    "current_results_next_required_step": "Keep auto-start hard-frozen and review completed follow-up shards 18_of_20;19_of_20;20_of_20 before reopening the STK17B (DRAK2) default lane.",
                    "next_required_step": "Keep auto-start hard-frozen and review completed follow-up shards 18_of_20;19_of_20;20_of_20 before reopening the STK17B (DRAK2) default lane.",
                }
            }
        ),
        encoding="utf-8",
    )
    (runs / "wetlab_lbdhodh_gate51_validation_review_surface_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_lbdhodh_gate51_validation_review_surface_ready",
                    "target_id": "Leishmania braziliensis DHODH",
                    "gate51_validated": True,
                    "decision": "promote_gate51_validated_keep_default_closed",
                    "validated_command_kind": "throughput_preflight_tuned_gate51",
                    "validated_threshold_A": 5.1,
                    "gate51_validation_row_count": 12,
                    "gate51_validation_success_count": 12,
                    "next_required_step": "Promote DHODH gate5.1 as validated, keep the default lane closed, and reserve any future DHODH reopen for an explicit new review.",
                }
            }
        ),
        encoding="utf-8",
    )
    (runs / "wetlab_stk17b_exploratory_followup_lane_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_stk17b_exploratory_followup_lane_blocked",
                    "target_id": "STK17B (DRAK2)",
                    "shard_id": "",
                    "selected_command_kind": "throughput_preflight_tuned_gate45",
                    "followup_lane_label": "exploratory_gate4.5_followup",
                    "followup_shard_ids": "18_of_20;19_of_20;20_of_20",
                    "hard_freeze_state": "hard_freeze_after_exploratory_success",
                    "freeze_note": "Auto-start remains hard-frozen after the gate4.5 success; follow-up shards 18_of_20;19_of_20;20_of_20 are routed to the exploratory gate4.5 follow-up lane and should be reviewed separately before reopening.",
                    "next_required_step": "Keep auto-start hard-frozen and review completed follow-up shards 18_of_20;19_of_20;20_of_20 before reopening the STK17B (DRAK2) default lane.",
                }
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(
        json.loads((runs / "wetlab_broad_screen_precision_monitor_current.json").read_text(encoding="utf-8")),
        json.loads((runs / "wetlab_broad_screen_execution_queue_current.json").read_text(encoding="utf-8")),
        json.loads((runs / "wetlab_broad_screen_antitarget_execution_queue_current.json").read_text(encoding="utf-8")),
        json.loads((runs / "wetlab_broad_screen_antitarget_progress_current.json").read_text(encoding="utf-8")),
        json.loads((runs / "wetlab_primary_stage6_failure_surface_current.json").read_text(encoding="utf-8")),
        json.loads((runs / "wetlab_retry_handoff_summary_current.json").read_text(encoding="utf-8")),
        lbdhodh_gate51_validation_review_surface=json.loads((runs / "wetlab_lbdhodh_gate51_validation_review_surface_current.json").read_text(encoding="utf-8")),
        stk17b_exploratory_followup_lane=json.loads((runs / "wetlab_stk17b_exploratory_followup_lane_current.json").read_text(encoding="utf-8")),
    )
    summary = payload["summary"]
    assert summary["selected_manual_retry_lane_label"] == "exploratory_gate4.5_followup"
    assert summary["selected_manual_retry_shard_id"] == "18_of_20;19_of_20;20_of_20"
    assert summary["stk17b_exploratory_followup_shard_id"] == "18_of_20;19_of_20;20_of_20"
    assert summary["next_required_step"] == "Promote DHODH gate5.1 as validated, keep the default lane closed, and reserve any future DHODH reopen for an explicit new review."


def test_build_wetlab_monitor_semantics_marks_no_guard_when_failure_surface_is_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "wetlab_broad_screen_precision_monitor_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_broad_screen_precision_monitor_ready",
                    "target_count": 1,
                    "library_size": 100000,
                    "ingested_compound_count": 105700,
                    "total_shards": 2,
                    "resolved_shards": 1,
                    "successful_resolved_shards": 1,
                    "held_resolved_shards": 0,
                    "running_shards": 1,
                    "pending_shards": 0,
                    "completion_pct": 50.0,
                    "successful_completion_pct": 50.0,
                    "held_completion_pct": 0.0,
                    "focus_target_id": "CA IX",
                    "focus_shard_id": "02_of_20",
                    "focus_queue_status": "running",
                    "median_completed_shard_minutes": 20.0,
                    "recent_median_completed_shard_minutes": 20.0,
                },
                "rows": [
                    {"target_id": "CA IX", "completed_shards": 1, "held_shards": 0, "median_completed_shard_minutes": 20.0, "recent_median_completed_shard_minutes": 20.0, "hold_median_completed_shard_minutes": 0.0},
                ],
            }
        ),
        encoding="utf-8",
    )
    (runs / "wetlab_broad_screen_execution_queue_current.json").write_text(
        json.dumps({"summary": {"queue_row_count": 2, "resolved_row_count": 1, "running_row_count": 1, "first_actionable_target_id": "CA IX", "first_actionable_shard_id": "02_of_20", "first_actionable_queue_status": "running"}, "rows": []}),
        encoding="utf-8",
    )
    (runs / "wetlab_broad_screen_antitarget_execution_queue_current.json").write_text(
        json.dumps({"summary": {"queue_row_count": 0, "ready_now_row_count": 0, "running_row_count": 0, "resolved_row_count": 0, "first_actionable_primary_target_id": "", "first_actionable_anti_target_id": "", "first_actionable_shard_id": "", "first_actionable_queue_status": ""}, "rows": []}),
        encoding="utf-8",
    )
    (runs / "wetlab_broad_screen_antitarget_progress_current.json").write_text(json.dumps({"summary": {"row_count": 0, "running_row_count": 0, "resolved_row_count": 0}, "rows": []}), encoding="utf-8")

    payload = mod.build_payload(
        json.loads((runs / "wetlab_broad_screen_precision_monitor_current.json").read_text(encoding="utf-8")),
        json.loads((runs / "wetlab_broad_screen_execution_queue_current.json").read_text(encoding="utf-8")),
        json.loads((runs / "wetlab_broad_screen_antitarget_execution_queue_current.json").read_text(encoding="utf-8")),
        json.loads((runs / "wetlab_broad_screen_antitarget_progress_current.json").read_text(encoding="utf-8")),
        {"summary": {}, "rows": []},
    )
    assert payload["summary"]["guard_active"] is False
    assert payload["summary"]["guard_blocked_target_id"] == ""
    assert "no active auto-hold guard" in payload["summary"]["guard_note"]


def test_build_wetlab_monitor_semantics_prefers_dengue_queue_source_priority(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)

    precision_monitor = {
        "summary": {
            "status": "wetlab_broad_screen_precision_monitor_ready",
            "resolved_shards": 196,
            "successful_resolved_shards": 54,
            "held_resolved_shards": 142,
            "running_shards": 1,
            "pending_shards": 63,
            "completion_pct": 75.4,
            "successful_completion_pct": 20.8,
            "held_completion_pct": 54.6,
            "focus_target_id": "Dengue NS2B-NS3 protease",
            "focus_shard_id": "17_of_20",
            "focus_queue_status": "running",
            "median_completed_shard_minutes": 24.0,
            "recent_median_completed_shard_minutes": 23.0,
            "focus_elapsed_minutes": 18.0,
            "focus_signal_age_minutes": 0.0,
            "focus_heartbeat_count": 4,
            "focus_event_count": 6,
        },
        "rows": [],
    }
    execution_queue = {
        "summary": {
            "status": "wetlab_broad_screen_execution_queue_ready",
            "queue_row_count": 260,
            "resolved_row_count": 196,
            "running_row_count": 1,
            "first_actionable_target_id": "Dengue NS2B-NS3 protease",
            "first_actionable_shard_id": "17_of_20",
            "first_actionable_queue_status": "running",
            "next_required_step": "Continue or complete Dengue NS2B-NS3 protease shard 17_of_20 through the broad-screen runtime runner.",
        }
    }
    antitarget_execution_queue = {
        "summary": {
            "status": "wetlab_broad_screen_antitarget_execution_queue_ready",
            "queue_row_count": 440,
            "ready_now_row_count": 0,
            "running_row_count": 0,
            "resolved_row_count": 0,
            "first_actionable_primary_target_id": "",
            "first_actionable_anti_target_id": "",
            "first_actionable_shard_id": "",
            "first_actionable_queue_status": "",
        }
    }
    dengue_tuning_surface = {
        "summary": {
            "status": "wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_ready",
            "target_id": "Dengue NS2B-NS3 protease",
            "recommended_observed_threshold_A": 4.5,
            "immediately_runnable_command_kind": "throughput_preflight_tuned_gate45",
        }
    }
    dengue_exploratory_retry_lane = {
        "summary": {
            "status": "wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_ready",
            "target_id": "Dengue NS2B-NS3 protease",
            "shard_id": "14_of_20",
            "ready_for_manual_retry": False,
            "selected_command_kind": "throughput_preflight_tuned_gate45",
            "lane_label": "exploratory_gate4.5_followup",
            "next_required_step": "Keep the Dengue NS2B-NS3 protease default lane paused and refresh the stage6 tuning surface before retrying.",
        }
    }

    payload = mod.build_payload(
        precision_monitor,
        execution_queue,
        antitarget_execution_queue,
        dengue_stage6_tuning_surface=dengue_tuning_surface,
        dengue_exploratory_retry_lane=dengue_exploratory_retry_lane,
        failure_surface={"summary": {}},
    )

    summary = payload["summary"]
    assert summary["dengue_stage6_tuning_ready"] is False
    assert summary["dengue_stage6_source_priority"] == "execution_queue"
    assert summary["dengue_stage6_retry_target_id"] == "Dengue NS2B-NS3 protease"
    assert summary["dengue_stage6_retry_shard_id"] == "17_of_20"
    assert summary["dengue_stage6_retry_next_required_step"] == "Continue or complete Dengue NS2B-NS3 protease shard 17_of_20 through the broad-screen runtime runner."
