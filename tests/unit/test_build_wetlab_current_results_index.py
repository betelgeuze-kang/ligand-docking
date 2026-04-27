from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tools import build_wetlab_current_results_index as mod

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_current_packet_summary(filename: str) -> dict:
    return json.loads((REPO_ROOT / "runs" / filename).read_text(encoding="utf-8"))["summary"]


def _load_current_packet_payload(filename: str) -> dict:
    return json.loads((REPO_ROOT / "runs" / filename).read_text(encoding="utf-8"))


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
    assert packet_summary["commercial_primary_upgrade_actions_v1"] == expected_primary_upgrade_actions


def test_build_wetlab_current_results_index_rejects_placeholder_partnering_stack_evidence() -> None:
    placeholder_payload = mod.build_payload(partnering_stack={"summary": {"status": "ok"}})
    placeholder_summary = placeholder_payload["summary"]
    assert placeholder_summary["partnering_stack_artifact_status"] == "ok"
    assert placeholder_summary["partnering_stack_artifact_complete"] is False
    assert placeholder_summary["campaign_terminal_state"] == ""
    assert placeholder_summary["ready_to_send_track_count"] == 0
    placeholder_rows = {
        row["surface"]: row
        for group in placeholder_payload["groups"]
        for row in group["rows"]
        if group["group"] == "stack/handoff/final summary"
    }
    assert placeholder_rows["partnering_stack"]["status"] == "missing"

    minimal_ready_payload = mod.build_payload(
        partnering_stack={"summary": {"status": "wetlab_partnering_stack_ready"}}
    )
    minimal_ready_summary = minimal_ready_payload["summary"]
    assert minimal_ready_summary["partnering_stack_artifact_status"] == "wetlab_partnering_stack_ready"
    assert minimal_ready_summary["partnering_stack_artifact_complete"] is False
    assert minimal_ready_summary["campaign_terminal_state"] == ""
    assert minimal_ready_summary["ready_to_send_track_count"] == 0

    marker_only_payload = mod.build_payload(
        partnering_stack={
            "summary": {
                "status": "wetlab_partnering_stack_ready",
                "artifact_kind": "wetlab_partnering_stack",
                "artifact_completeness": "full_partnering_stack",
            }
        }
    )
    marker_only_summary = marker_only_payload["summary"]
    assert marker_only_summary["partnering_stack_artifact_status"] == "wetlab_partnering_stack_ready"
    assert marker_only_summary["partnering_stack_artifact_complete"] is False
    assert marker_only_summary["campaign_terminal_state"] == ""
    assert marker_only_summary["ready_to_send_track_count"] == 0

    full_payload = mod.build_payload(
        partnering_stack={
            "summary": {
                "status": "wetlab_partnering_stack_ready",
                "artifact_kind": "wetlab_partnering_stack",
                "artifact_schema_version": "wetlab_partnering_stack.v1",
                "artifact_completeness": "full_partnering_stack",
                "portfolio_target_count": 14,
                "wave1_target_count": 8,
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_surface_label": "tcruzi_pde_allatom_review_packet",
                "selected_allatom_best_mean_min_distance_A": 3.375,
                "selected_allatom_best_mean_min_distance_A_source": (
                    "tcruzi_pde_allatom_review_packet.best_mean_min_distance_A"
                ),
                "selected_allatom_wetlab_gate_pass": False,
                "selected_allatom_final_gate_pass": False,
                "campaign_terminal_state": "complete",
                "ready_to_send_track_count": 5,
            }
        }
    )
    full_summary = full_payload["summary"]
    assert full_summary["partnering_stack_artifact_complete"] is True
    assert full_summary["campaign_terminal_state"] == "complete"
    assert full_summary["ready_to_send_track_count"] == 5


def test_build_wetlab_current_results_index_groups_surfaces(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    primary_queue = {
        "summary": {
            "status": "wetlab_broad_screen_execution_queue_ready",
            "first_actionable_target_id": "SARS-CoV-2 PLpro",
            "first_actionable_shard_id": "16_of_20",
            "first_actionable_queue_status": "ready_after_previous_shard",
            "next_required_step": "Dispatch SARS-CoV-2 PLpro shard 16_of_20 through the broad-screen runtime runner.",
        }
    }
    antitarget_queue = {
        "summary": {
            "status": "wetlab_broad_screen_antitarget_execution_queue_ready",
            "first_actionable_primary_target_id": "CA IX",
            "first_actionable_anti_target_id": "CA XII",
            "first_actionable_shard_id": "08_of_20",
            "first_actionable_queue_status": "running",
            "next_required_step": "Continue or complete CA IX -> CA XII shard 08_of_20.",
        }
    }
    primary_watch_state = {
        "summary": {
            "status": "wetlab_broad_screen_primary_watch_state_ready",
            "watcher_decision": "idle_no_running_primary_row",
            "next_required_step": "No running primary broad-screen row is active; dispatch a ready shard or wait for auto-start.",
        }
    }
    antitarget_watch_state = {
        "summary": {
            "status": "wetlab_broad_screen_antitarget_watcher_state_ready",
            "watcher_decision": "continue_running_compute_attached",
            "next_required_step": "Keep monitoring the active compute-attached counterscreen row for CA IX -> CA XII 08_of_20; the watcher will auto-complete it from the throughput summary.",
        }
    }
    precision_monitor = {
        "summary": {
            "status": "wetlab_broad_screen_precision_monitor_ready",
            "completion_pct": 44.2,
            "successful_completion_pct": 6.5,
            "held_completion_pct": 37.7,
            "focus_target_id": "SARS-CoV-2 PLpro",
            "focus_shard_id": "16_of_20",
            "next_required_step": "Dispatch SARS-CoV-2 PLpro shard 16_of_20 and keep the shard-level result intake packet ready.",
        }
    }
    failure_surface = {
        "summary": {
            "status": "wetlab_primary_stage6_failure_surface_ready",
            "target_count": 3,
            "surface_row_count": 60,
            "auto_hold_row_count": 60,
            "watcher_pending_failure_row_count": 1,
            "sparse_top_level_row_count": 60,
            "stage1_mapping_failed_count": 2,
            "stage6_failed_count": 58,
            "next_required_step": "Use this surface to decide whether auto-hold guard should stop a target, and whether stage1 mapping or stage6 gate needs a target-specific preset before resuming.",
        }
    }
    primary_retry = {
        "summary": {
            "status": "wetlab_broad_screen_throughput_bridge_ready",
            "target_id": "SARS-CoV-2 PLpro",
            "shard_id": "16_of_20",
            "preferred_command_kind": "throughput_preflight",
            "next_required_step": "Use the tuned gate-relaxed throughput preflight command for SARS-CoV-2 PLpro 16_of_20; switch to the matching execute command after preflight passes.",
        }
    }
    antitarget_retry = {
        "summary": {
            "status": "wetlab_broad_screen_antitarget_throughput_bridge_ready",
            "primary_target_id": "CA IX",
            "anti_target_id": "CA XII",
            "shard_id": "08_of_20",
            "preferred_command_kind": "throughput_preflight",
            "next_required_step": "Use the preferred counterscreen throughput preflight command for CA IX -> CA XII 08_of_20; switch to execute after preflight passes.",
        }
    }
    hold_guard = {
        "summary": {
            "status": "wetlab_broad_screen_primary_watch_action_ready",
            "guard_blocked_target_id": "SARS-CoV-2 PLpro",
            "guard_hold_streak": 15,
            "guard_hold_limit": 3,
            "next_required_step": "Pause auto-advance for SARS-CoV-2 PLpro; it hit 15 consecutive auto-holds. Review the target-level gate-failure surface before continuing.",
        }
    }
    retry_handoff_summary = {
        "summary": {
            "status": "wetlab_retry_handoff_summary_ready",
            "manual_retry_focus_target_id": "STK17B (DRAK2)",
            "manual_retry_focus_decision": "do_not_autoadvance",
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
    plpro_manual_retry_lane = {
        "summary": {
            "status": "wetlab_plpro_manual_retry_lane_ready",
            "target_id": "SARS-CoV-2 PLpro",
            "shard_id": "17_of_20",
            "ready_for_manual_retry": True,
            "selected_command_kind": "throughput_preflight_tuned_gate55",
            "next_required_step": "Run the PLpro manual retry runner for 17_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
        }
    }
    stk17b_manual_retry_lane = {
        "summary": {
            "status": "wetlab_stk17b_manual_retry_lane_ready",
            "target_id": "STK17B (DRAK2)",
            "shard_id": "12_of_20",
            "ready_for_manual_retry": True,
            "selected_command_kind": "throughput_preflight_tuned_gate55",
            "next_required_step": "Run the STK17B tuned gate55 manual retry runner for 12_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
        }
    }
    stk17b_exploratory_retry_lane = {
        "summary": {
            "status": "wetlab_stk17b_exploratory_retry_lane_ready",
            "target_id": "STK17B (DRAK2)",
            "shard_id": "17_of_20",
            "ready_for_manual_retry": True,
            "selected_command_kind": "throughput_preflight_tuned_gate45",
            "next_required_step": "Run the STK17B (DRAK2) exploratory gate4.5 manual retry runner for 17_of_20; compare the outcome against the retry campaign band before relaxing broader kinase gates.",
        }
    }
    stk17b_exploratory_followup_lane = {
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
    kinase_retry_policy_templates = {
        "summary": {
            "status": "wetlab_kinase_retry_policy_templates_ready",
            "template_target_count": 3,
            "empirical_validated_target_count": 1,
            "gate45_only_target_count": 1,
            "guarded_gate55_candidate_target_count": 1,
            "focus_target_id": "STK17B (DRAK2)",
            "focus_template_label": "gate45_branch_only_empirical",
            "focus_selected_command_kind": "throughput_preflight_tuned_gate45",
            "next_required_step": "Keep STK17B on the gate4.5 branch-only kinase template, keep ALK2 on the guarded gate55 template, and treat LRRK2 as panel-first until broad failure evidence appears.",
        }
    }
    target_retry_policy_templates = {
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
    mapping_fix_retry_support = {
        "summary": {
            "status": "wetlab_mapping_fix_retry_support_ready",
            "ready_target_count": 2,
            "ready_targets": "SARS-CoV-2 Mpro; T. cruzi PDE",
            "next_required_step": "Run the mapping-fix retry runner for SARS-CoV-2 Mpro 01_of_20; keep auto-start blocked until the mapping diagnostics rerun lands a clean summary.",
        }
    }
    stage1_mapping_fix_lanes = {
        "summary": {
            "status": "wetlab_stage1_mapping_fix_lanes_ready",
            "ready_target_count": 2,
            "ready_targets": "SARS-CoV-2 Mpro; T. cruzi PDE",
            "next_required_step": "Run the stage1 mapping-fix retry runner for SARS-CoV-2 Mpro 01_of_20; keep auto-start blocked until mapping clears.",
        }
    }
    mapping_fix_retry_policy_templates = {
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
    lbdhodh_gate51_validation_review_surface = {
        "summary": {
            "status": "wetlab_lbdhodh_gate51_validation_review_surface_ready",
            "target_id": "Leishmania braziliensis DHODH",
            "promotion_label": "gate5.1_validated",
            "gate51_validated": True,
            "default_lane_reopen_allowed": False,
            "branch_to_gate51_only": True,
            "decision": "promote_gate51_validated_keep_default_closed",
            "decision_rationale": "Gate5.1 rows 09_of_20 through 20_of_20 all resolved cleanly, so DHODH should be promoted as validated and the default lane should remain closed.",
            "gate51_validation_row_count": 12,
            "gate51_validation_success_count": 12,
            "validated_command_kind": "throughput_preflight_tuned_gate51",
            "validated_threshold_A": 5.1,
            "next_required_step": "Promote DHODH gate5.1 as validated, keep the default lane closed, and reserve any future DHODH reopen for an explicit new review.",
        }
    }
    (tmp_path / "runs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "runs/wetlab_broad_screen_primary_watch_loop.pid").write_text(str(os.getpid()), encoding="utf-8")
    (tmp_path / "runs/wetlab_broad_screen_antitarget_watcher_loop.pid").write_text(str(os.getpid()), encoding="utf-8")
    partnering_stack = {
        "summary": {
            "status": "wetlab_partnering_stack_ready",
            "campaign_terminal_state": "complete",
            "ready_to_send_track_count": 5,
            "broad_screen_first_actionable_target_id": "STK17B (DRAK2)",
            "broad_screen_first_actionable_shard_id": "18_of_20",
            "next_required_step": "Run the STK17B (DRAK2) exploratory gate4.5 follow-up runner for 18_of_20; keep auto-start hard-frozen after the gate4.5 success and review shards 18-20 separately before reopening.",
        }
    }
    master_handoff = {
        "summary": {
            "status": "wetlab_master_handoff_dashboard_ready",
            "campaign_terminal_state": "complete",
            "ready_to_send_track_count": 5,
            "primary_surface_artifact": "runs/wetlab_final_campaign_summary_current.md",
            "broad_screen_first_actionable_target_id": "STK17B (DRAK2)",
            "broad_screen_first_actionable_shard_id": "18_of_20",
            "next_required_step": "Run the STK17B (DRAK2) exploratory gate4.5 follow-up runner for 18_of_20; keep auto-start hard-frozen after the gate4.5 success and review shards 18-20 separately before reopening.",
        }
    }
    final_summary = {
        "summary": {
            "status": "wetlab_final_campaign_summary_ready",
            "campaign_terminal_state": "complete",
            "ready_to_send_track_count": 5,
            "broad_screen_first_actionable_target_id": "STK17B (DRAK2)",
            "broad_screen_first_actionable_shard_id": "18_of_20",
            "next_required_step": "Run the STK17B (DRAK2) exploratory gate4.5 follow-up runner for 18_of_20; keep auto-start hard-frozen after the gate4.5 success and review shards 18-20 separately before reopening.",
        }
    }
    terminal_review = {
        "summary": {
            "status": "wetlab_master_terminal_review_ready",
            "campaign_terminal_state": "complete",
            "ready_to_send_track_count": 5,
            "next_required_step": "Use the final campaign summary and outbound execution priority board to drive partner-facing handoff.",
        }
    }

    payload = mod.build_payload(
        primary_queue,
        antitarget_queue,
        primary_watch_state,
        antitarget_watch_state,
        precision_monitor,
        failure_surface,
        primary_retry,
        antitarget_retry,
        hold_guard,
        retry_handoff_summary,
        stk17b_manual_retry_lane=stk17b_manual_retry_lane,
        stk17b_exploratory_retry_lane=stk17b_exploratory_retry_lane,
        stk17b_exploratory_followup_lane=stk17b_exploratory_followup_lane,
        kinase_retry_policy_templates=kinase_retry_policy_templates,
        target_retry_policy_templates=target_retry_policy_templates,
        plpro_manual_retry_lane=plpro_manual_retry_lane,
        mapping_fix_retry_support=mapping_fix_retry_support,
        stage1_mapping_fix_lanes=stage1_mapping_fix_lanes,
        mapping_fix_retry_policy_templates=mapping_fix_retry_policy_templates,
        partnering_stack=partnering_stack,
        master_handoff_dashboard=master_handoff,
        final_campaign_summary=final_summary,
        master_terminal_review=terminal_review,
        lbdhodh_gate51_validation_review_surface=lbdhodh_gate51_validation_review_surface,
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_current_results_index_ready"
    assert summary["group_count"] == 15
    assert summary["surface_count"] == 24
    assert summary["primary_queue_first_actionable_target_id"] == "SARS-CoV-2 PLpro"
    assert summary["counter_queue_first_actionable_primary_target_id"] == "CA IX"
    assert summary["primary_watch_loop_attached"] is True
    assert summary["primary_watch_loop_liveness"] == "attached"
    assert summary["primary_watch_loop_fallback_mode"] == "compute-attached"
    assert summary["antitarget_watch_loop_attached"] is True
    assert summary["antitarget_watch_loop_liveness"] == "attached"
    assert summary["antitarget_watch_loop_fallback_mode"] == "compute-attached"
    assert summary["hold_guard_blocked_target_id"] == "SARS-CoV-2 PLpro"
    assert summary["hold_guard_streak"] == 15
    assert summary["lbdhodh_gate51_validation_review_ready"] is True
    assert summary["lbdhodh_gate51_validation_review_target_id"] == "Leishmania braziliensis DHODH"
    assert summary["lbdhodh_gate51_validation_review_decision"] == "promote_gate51_validated_keep_default_closed"
    assert summary["lbdhodh_gate51_validation_review_success_count"] == 12
    assert summary["lbdhodh_gate51_validation_review_row_count"] == 12
    assert summary["lbdhodh_gate51_validation_review_validated_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["lbdhodh_gate51_validation_review_validated_threshold_A"] == 5.1
    assert summary["selected_validated_target_id"] == "Leishmania braziliensis DHODH"
    assert summary["selected_validated_surface_label"] == "gate5.1_validation_review"
    assert summary["selected_validated_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["selected_validated_threshold_A"] == 5.1
    assert summary["selected_validated_next_required_step"].startswith("Promote DHODH gate5.1 as validated")
    assert summary["stk17b_manual_retry_target_id"] == "STK17B (DRAK2)"
    assert summary["stk17b_manual_retry_shard_id"] == "12_of_20"
    assert summary["stk17b_manual_retry_selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert summary["stk17b_exploratory_retry_target_id"] == "STK17B (DRAK2)"
    assert summary["stk17b_exploratory_retry_shard_id"] == "17_of_20"
    assert summary["stk17b_exploratory_retry_selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["stk17b_exploratory_followup_target_id"] == "STK17B (DRAK2)"
    assert summary["stk17b_exploratory_followup_shard_id"] == "18_of_20"
    assert summary["stk17b_exploratory_followup_selected_command_kind"] == "throughput_preflight_tuned_gate45"
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
    assert summary["target_retry_policy_templates_ready"] is True
    assert summary["target_retry_template_target_count"] == 6
    assert summary["target_retry_empirical_validated_target_count"] == 2
    assert summary["target_retry_focus_target_id"] == "Leishmania braziliensis DHODH"
    assert summary["target_retry_focus_template_label"] == "gate51_branch_only_empirical"
    assert summary["target_retry_focus_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["target_retry_focus_selected_threshold_A"] == 5.1
    assert summary["mapping_fix_retry_policy_templates_ready"] is True
    assert summary["mapping_fix_retry_template_target_count"] == 2
    assert summary["mapping_fix_retry_ready_template_target_count"] == 2
    assert summary["mapping_fix_retry_focus_target_id"] == "SARS-CoV-2 Mpro"
    assert summary["mapping_fix_retry_focus_template_label"] == "mapping_fix_branch_only"
    assert summary["mapping_fix_retry_focus_selected_command_kind"] == "throughput_preflight"
    assert summary["selected_manual_retry_target_id"] == "STK17B (DRAK2)"
    assert summary["selected_manual_retry_shard_id"] == "18_of_20"
    assert summary["selected_manual_retry_selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["selected_manual_retry_lane_label"] == "exploratory_gate4.5_followup"
    assert summary["selected_rescue_branch_surface_label"] == "pde_rescue_only_branch"
    assert summary["selected_rescue_branch_next_required_step"] == "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, and use the promoted top-4 packet as the review unit before any reopen decision."
def test_build_wetlab_current_results_index_should_prefer_dpre1_guarded_review() -> None:
    root = Path(__file__).resolve().parents[2]
    load = lambda rel: json.loads((root / rel).read_text(encoding="utf-8"))

    payload = mod.build_payload(
        load("runs/wetlab_broad_screen_execution_queue_current.json"),
        load("runs/wetlab_broad_screen_antitarget_execution_queue_current.json"),
        load("runs/wetlab_broad_screen_primary_watch_state_current.json"),
        load("runs/wetlab_broad_screen_antitarget_watcher_state_current.json"),
        load("runs/wetlab_broad_screen_precision_monitor_current.json"),
        load("runs/wetlab_primary_stage6_failure_surface_current.json"),
        load("runs/wetlab_broad_screen_throughput_bridge_current.json"),
        load("runs/wetlab_broad_screen_antitarget_throughput_bridge_current.json"),
        load("runs/wetlab_broad_screen_primary_watch_action_current.json"),
        load("runs/wetlab_retry_handoff_summary_current.json"),
        load("runs/wetlab_dpre1_branch_review_surface_current.json"),
        load("runs/wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_current.json"),
        load("runs/wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_current.json"),
        load("runs/wetlab_lbdhodh_gate51_validation_review_surface_current.json"),
        load("runs/wetlab_tcruzi_pde_rescue_review_surface_current.json"),
        load("runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.json"),
        load("runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.json"),
        load("runs/wetlab_lbdhodh_stage6_tuning_surface_current.json"),
        load("runs/wetlab_lbdhodh_exploratory_retry_lane_current.json"),
        load("runs/wetlab_stk17b_manual_retry_lane_current.json"),
        load("runs/wetlab_stk17b_exploratory_retry_lane_current.json"),
        load("runs/wetlab_stk17b_exploratory_followup_lane_current.json"),
        load("runs/wetlab_stk17b_followup_review_surface_current.json"),
        load("runs/wetlab_kinase_retry_policy_templates_current.json"),
        load("runs/wetlab_target_retry_policy_templates_current.json"),
        load("runs/wetlab_plpro_manual_retry_lane_current.json"),
        load("runs/wetlab_mapping_fix_retry_support_current.json"),
        load("runs/wetlab_stage1_mapping_fix_lanes_current.json"),
        load("runs/wetlab_mapping_fix_retry_policy_templates_current.json"),
        load("runs/wetlab_hard_target_rescue_lane_current.json"),
        load("runs/wetlab_rescue_anchor_artifacts_current.json"),
        load("runs/wetlab_rescue_three_bead_candidates_current.json"),
        load("runs/wetlab_partnering_stack_current.json"),
        load("runs/wetlab_master_handoff_dashboard_current.json"),
        load("runs/wetlab_final_campaign_summary_current.json"),
        load("runs/wetlab_master_terminal_review_current.json"),
    )

    summary = payload["summary"]
    assert summary["dpre1_branch_review_ready"] is True
    assert summary["dpre1_branch_review_target_id"] == "DprE1"
    assert summary["dpre1_branch_review_branch_label"] == "dpre1_guarded_gate51_branch"
    assert summary["dpre1_branch_review_branch_state"] == "guarded_gate51_review_default_lane_closed"
    assert summary["dpre1_branch_review_stage6_tuning_recommended_threshold_A"] == 5.05
    assert summary["dpre1_branch_review_exploratory_retry_selected_threshold_A"] == 5.1
    assert summary["dpre1_branch_review_successor_target"] == "T. cruzi KRS1"
    assert summary["dpre1_branch_review_successor_gate_state"] == "blocked_pending_dpre1_guarded_review"
    assert summary["next_required_step"] == summary["dpre1_branch_review_next_required_step"]


def test_build_wetlab_current_results_index_prefers_krs1_guarded_review_when_focus_matches(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    krs1_next_step = "Keep the T. cruzi KRS1 default lane paused and refresh the stage6 tuning surface before retrying."

    payload = mod.build_payload(
        primary_queue={"summary": {"status": "wetlab_broad_screen_execution_queue_ready"}},
        antitarget_queue={"summary": {"status": "wetlab_broad_screen_antitarget_execution_queue_ready"}},
        primary_watch_state={"summary": {"status": "wetlab_broad_screen_primary_watch_state_ready"}},
        antitarget_watch_state={"summary": {"status": "wetlab_broad_screen_antitarget_watcher_state_ready"}},
        precision_monitor={
            "summary": {
                "status": "wetlab_broad_screen_precision_monitor_ready",
                "focus_target_id": "T. cruzi KRS1",
                "focus_shard_id": "09_of_20",
                "focus_queue_status": "running",
            }
        },
        failure_surface={"summary": {"status": "wetlab_primary_stage6_failure_surface_ready"}},
        retry_handoff_summary={"summary": {"status": "wetlab_retry_handoff_summary_ready"}},
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
                "next_required_step": krs1_next_step,
                "branch_review_ready": True,
            }
        },
    )

    summary = payload["summary"]
    assert summary["krs1_branch_review_ready"] is True
    assert summary["selected_krs1_branch_review_target_id"] == "T. cruzi KRS1"
    assert summary["selected_krs1_branch_review_surface_label"] == "krs1_branch_review_surface"
    assert summary["selected_krs1_branch_review_branch_label"] == "tcruzi_krs1_guarded_gate51_branch"
    assert summary["selected_krs1_branch_review_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["selected_krs1_branch_review_selected_threshold_A"] == 5.1
    assert summary["selected_krs1_branch_review_next_required_step"] == krs1_next_step
    assert summary["next_required_step"] == krs1_next_step
    assert summary["dpre1_branch_review_next_required_step"] == "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying."
    assert summary["krs1_branch_review_successor_target"] == "LRRK2"


def test_build_wetlab_current_results_index_keeps_pde_operator_readiness_separate_from_final_gate(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    retry_handoff_summary = {
        "summary": {
            "status": "wetlab_retry_handoff_summary_ready",
            "selected_rescue_branch_surface_label": "pde_rescue_only_branch",
            "selected_rescue_branch_target_id": "T. cruzi PDE",
            "selected_rescue_branch_selected_command_kind": "three_bead_rescue_local_refine",
            "selected_rescue_branch_selected_threshold_A": 2.5,
            "selected_rescue_branch_operator_packet_ready": True,
            "selected_rescue_branch_operator_packet_scope": "partner_operator_rescue_only_review",
            "selected_allatom_target_id": "Cathepsin K",
            "selected_allatom_surface_label": "cathepsin_k_allatom_review_packet",
            "selected_allatom_selected_command_kind": "allatom_refinement",
            "selected_allatom_selected_threshold_A": 2.5,
            "selected_allatom_packet_scope": "selected_allatom_review_packet",
            "selected_allatom_best_compound_name": "Cathepsin Lead",
            "selected_allatom_best_compound_name_human_readable": "Cathepsin Lead",
            "selected_allatom_best_compound_name_resolution": "human_readable",
            "selected_allatom_best_mean_min_distance_A": 1.234,
            "selected_allatom_promoted_candidate_count": 4,
            "selected_allatom_under_2p5_candidate_count": 1,
            "selected_allatom_near_candidate_count": 3,
            "selected_allatom_next_required_step": "Review Cathepsin K selected all-atom packet before any wetlab decision.",
            "selected_rescue_branch_next_required_step": (
                "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, "
                "and use the promoted top-4 packet as the review unit before any reopen decision."
            ),
        }
    }
    promoted_top4_review_packet = {
        "summary": {
            "status": "wetlab_tcruzi_pde_promoted_top4_review_packet_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "strict_threshold_A": 2.5,
            "promoted_candidate_count": 4,
            "under_2p5_candidate_count": 1,
            "best_ligand_id": "ligand_strict",
            "best_compound_name": "Strict Lead",
            "best_compound_name_human_readable": "Strict Lead",
            "best_compound_name_resolution": "human_readable",
            "best_mean_min_distance_A": 0.672,
            "packet_ready_for_operator_review": True,
            "wetlab_final_gate_pass": False,
            "claim_gate_available": True,
            "claim_ready_for_allatom": False,
            "next_required_step": "Review the promoted top-4 packet.",
        }
    }
    rescue_only_branch_summary = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_only_branch_summary_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "branch_state": "promoted_top4_packet_ready_default_lane_closed",
            "promoted_top4_packet_ready": True,
            "promoted_candidate_count": 4,
            "under_2p5_candidate_count": 1,
            "best_ligand_id": "ligand_strict",
            "best_compound_name": "Strict Lead",
            "best_compound_name_human_readable": "Strict Lead",
            "best_compound_name_resolution": "human_readable",
            "best_mean_min_distance_A": 0.672,
            "next_required_step": (
                "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, "
                "and use the promoted top-4 packet as the review unit before any reopen decision."
            ),
        }
    }

    payload = mod.build_payload(
        retry_handoff_summary=retry_handoff_summary,
        tcruzi_pde_promoted_top4_review_packet=promoted_top4_review_packet,
        tcruzi_pde_rescue_only_branch_summary=rescue_only_branch_summary,
        tcruzi_pde_allatom_review_packet={
            "summary": {
                "status": "wetlab_tcruzi_pde_allatom_review_packet_ready",
                "target_id": "T. cruzi PDE",
                "surface_label": "tcruzi_pde_allatom_review_packet",
                "best_mean_min_distance_A": 3.375,
                "packet_ready_for_operator_review": True,
                "wetlab_gate_pass": False,
                "wetlab_final_gate_pass": False,
                "claim_gate_available": False,
                "claim_ready_for_allatom": False,
            }
        },
    )

    summary = payload["summary"]
    assert summary["tcruzi_pde_promoted_top4_review_packet_ready"] is True
    assert summary["tcruzi_pde_promoted_top4_review_packet_best_ligand_id"] == "ligand_strict"
    assert summary["tcruzi_pde_rescue_only_branch_summary_ready"] is True
    assert summary["tcruzi_pde_rescue_only_branch_summary_promoted_top4_packet_ready"] is True
    assert summary["selected_rescue_branch_operator_packet_ready"] is True
    assert summary["selected_rescue_branch_operator_review_ready"] is True
    assert summary["selected_rescue_branch_wetlab_final_gate_pass"] is True
    assert summary["selected_rescue_branch_surface_label"] == "pde_rescue_only_branch"
    assert summary["selected_allatom_target_id"] == "Cathepsin K"
    assert summary["selected_allatom_surface_label"] == "cathepsin_k_allatom_review_packet"
    assert summary["selected_allatom_selected_command_kind"] == "allatom_refinement"
    assert summary["selected_allatom_selected_threshold_A"] == 2.5
    assert summary["selected_allatom_packet_scope"] == "selected_allatom_review_packet"
    assert summary["selected_allatom_best_compound_name"] == "Cathepsin Lead"
    assert summary["selected_allatom_best_mean_min_distance_A"] == 1.234
    assert summary["selected_allatom_best_mean_min_distance_A_source"] == (
        "retry_handoff_summary.selected_allatom_best_mean_min_distance_A"
    )
    assert summary["selected_allatom_promoted_candidate_count"] == 4
    assert summary["selected_allatom_under_2p5_candidate_count"] == 1
    assert summary["selected_allatom_near_candidate_count"] == 3
    assert summary["selected_allatom_next_required_step"] == "Review Cathepsin K selected all-atom packet before any wetlab decision."
    assert summary["selected_allatom_actionability_status"] == "semi_hard_blocked"
    assert summary["selected_allatom_actionability_claim_requirement_mode"] == "semi_hard"
    assert summary["selected_allatom_actionability_claim_requirement_status"] == "blocked"
    assert summary["selected_allatom_raw_claim_requirement_mode"] == "semi_hard"
    assert summary["selected_allatom_effective_actionability_status"] == "semi_hard_blocked"
    assert summary["selected_allatom_effective_blocking_order"] == "claim_block_first"
    assert summary["selected_allatom_effective_primary_blocking_domain"] == "claim_equivalence"
    assert "resolve_claim_equivalence_gate" in summary["selected_allatom_action_recipe_codes"]
    assert "semi-hard" in summary["selected_allatom_actionability_human_summary"]
    assert "resolve_claim_equivalence_gate" in summary["selected_allatom_actionability_required_calculations"]
    assert any(
        item.get("category") == "claim_equivalence" and item.get("severity") == "semi_hard"
        for item in summary["selected_allatom_actionability_action_list"]
    )
    assert summary["selected_rescue_branch_next_required_step"].startswith(
        "Operate T. cruzi PDE through the dedicated rescue-only branch"
    )


def test_build_wetlab_current_results_index_prefers_review_packet_strict_metric_over_stale_retry_value() -> None:
    payload = mod.build_payload(
        retry_handoff_summary={
            "summary": {
                "status": "wetlab_retry_handoff_summary_ready",
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_surface_label": "tcruzi_pde_allatom_review_packet",
                "selected_allatom_selected_command_kind": "pseudo_allatom_backmapping_rescore",
                "selected_allatom_selected_threshold_A": 2.5,
                "selected_allatom_best_mean_min_distance_A": 2.756,
                "selected_allatom_best_mean_min_distance_A_source": (
                    "retry_handoff_summary.selected_allatom_best_mean_min_distance_A"
                ),
            }
        },
        tcruzi_pde_allatom_review_packet={
            "summary": {
                "status": "wetlab_tcruzi_pde_allatom_review_packet_ready",
                "target_id": "T. cruzi PDE",
                "surface_label": "tcruzi_pde_allatom_review_packet",
                "selected_command_kind": "pseudo_allatom_backmapping_rescore",
                "selected_threshold_A": 2.5,
                "best_ligand_id": "t_cruzi_pde_20_of_20_095609",
                "best_mean_min_distance_A": 0.672,
                "promoted_candidate_count": 4,
                "under_2p5_candidate_count": 1,
                "near_candidate_count": 3,
                "packet_ready_for_operator_review": True,
                "wetlab_gate_pass": True,
                "wetlab_final_gate_pass": False,
            }
        },
    )

    summary = payload["summary"]
    assert summary["selected_allatom_best_mean_min_distance_A"] == 0.672
    assert summary["selected_allatom_best_mean_min_distance_A_source"] == (
        "tcruzi_pde_allatom_review_packet.best_mean_min_distance_A"
    )
    assert summary["selected_allatom_under_2p5_candidate_count"] == 1
    assert summary["selected_allatom_wetlab_gate_pass"] is True


def test_build_wetlab_current_results_index_propagates_pde_selected_allatom_v2_and_translation_shortlist_guidance() -> None:
    pde_review_packet = _load_current_packet_payload("wetlab_tcruzi_pde_allatom_review_packet_current.json")
    pde_review_summary = dict(pde_review_packet["summary"])
    translation_shortlist_guidance = (
        "Review the promoted PDE pseudo all-atom top-4 packet manually only, keep the default lane closed, "
        "and do not treat it as wetlab-ready because translation_gate=fail, shortlist_tier=defer, "
        "and recommended_next_expensive_lane=defer_expensive_lane."
    )
    adjusted_pde_review_packet = {
        **pde_review_packet,
        "summary": {
            **pde_review_summary,
            "commercial_reported_v1": True,
            "commercial_schema_version": pde_review_summary["commercial_schema_version_v2"],
            "commercial_hard_gate_pass_v1": pde_review_summary["commercial_hard_gate_pass_v2"],
            "commercial_overall_score_v1": pde_review_summary["commercial_overall_score_v2"],
            "commercial_risk_bucket_v1": pde_review_summary["commercial_risk_bucket_v2"],
            "commercial_decision_class_v1": pde_review_summary["commercial_decision_class_v2"],
            "commercial_primary_upgrade_actions_v1": list(
                pde_review_summary["commercial_primary_upgrade_actions_v2"] or []
            ),
            "commercial_primary_upgrade_actions_text_v1": pde_review_summary["commercial_action_rollup_v2"],
            "next_required_step": translation_shortlist_guidance,
        },
    }

    payload = mod.build_payload(
        retry_handoff_summary={
            "summary": {
                "status": "wetlab_retry_handoff_summary_ready",
                "selected_allatom_target_id": pde_review_summary["target_id"],
                "selected_allatom_surface_label": pde_review_summary["surface_label"],
                "selected_allatom_selected_command_kind": pde_review_summary["selected_command_kind"],
                "selected_allatom_selected_threshold_A": pde_review_summary["selected_threshold_A"],
                "selected_allatom_packet_scope": pde_review_summary["packet_scope"],
                "selected_allatom_packet_ready_for_operator_review": pde_review_summary["packet_ready_for_operator_review"],
                "selected_allatom_wetlab_gate_pass": pde_review_summary["wetlab_gate_pass"],
                "selected_allatom_wetlab_final_gate_pass": pde_review_summary["wetlab_final_gate_pass"],
                "selected_allatom_claim_gate_available": pde_review_summary["claim_gate_available"],
                "selected_allatom_claim_ready_for_allatom": pde_review_summary["claim_ready_for_allatom"],
                "selected_allatom_commercial_schema_version": pde_review_summary["commercial_schema_version_v2"],
                "selected_allatom_commercial_hard_gate_pass_v1": pde_review_summary["commercial_hard_gate_pass_v2"],
                "selected_allatom_commercial_overall_score_v1": pde_review_summary["commercial_overall_score_v2"],
                "selected_allatom_commercial_risk_bucket_v1": pde_review_summary["commercial_risk_bucket_v2"],
                "selected_allatom_commercial_decision_class_v1": pde_review_summary["commercial_decision_class_v2"],
                "selected_allatom_commercial_primary_upgrade_actions_v1": list(
                    pde_review_summary["commercial_primary_upgrade_actions_v2"] or []
                ),
                "selected_allatom_commercial_primary_upgrade_actions_text_v1": pde_review_summary[
                    "commercial_action_rollup_v2"
                ],
                "selected_allatom_best_mean_min_distance_A": 3.705,
                "selected_allatom_translation_gate_reason": pde_review_summary["translation_gate_focus_reason"],
                "selected_allatom_recommended_next_expensive_lane_reason": pde_review_summary[
                    "recommended_next_expensive_lane_reason"
                ],
                "selected_allatom_next_required_step": translation_shortlist_guidance,
            }
        },
        tcruzi_pde_allatom_review_packet=adjusted_pde_review_packet,
        selected_allatom_visual_bundle={
            "summary": {
                "status": "selected_allatom_visual_bundle_ready",
                "target_id": pde_review_summary["target_id"],
                "assets_dir": "/tmp/tcruzi_pde_visuals",
                "dashboard_html": "/tmp/tcruzi_pde_visuals/dashboard.html",
                "primary_figure_path": "/tmp/tcruzi_pde_visuals/hero.png",
                "primary_movie_script_path": "/tmp/tcruzi_pde_visuals/hero.cxc",
                "primary_movie_mp4_path": "/tmp/tcruzi_pde_visuals/hero.mp4",
                "topk_count": 4,
                "figure_count": 2,
                "movie_plan_count": 4,
                "binding_event_candidate_count": 4,
                "human_summary": "PDE selected-allatom visuals ready.",
            }
        },
    )

    summary = payload["summary"]
    assert summary["allatom_family_focus_target_id"] == pde_review_summary["target_id"]
    assert summary["allatom_family_focus_surface_label"] == pde_review_summary["surface_label"]
    assert summary["allatom_family_focus_commercial_reported_v1"] is True
    assert summary["allatom_family_focus_commercial_schema_version"] == "wetlab_commercial_grade_v2"
    assert summary["allatom_family_focus_commercial_hard_gate_pass_v1"] is False
    assert summary["allatom_family_focus_commercial_overall_score_v1"] == pde_review_summary["commercial_overall_score_v2"]
    assert summary["allatom_family_focus_commercial_risk_bucket_v1"] == pde_review_summary["commercial_risk_bucket_v2"]
    assert summary["allatom_family_focus_commercial_decision_class_v1"] == pde_review_summary[
        "commercial_decision_class_v2"
    ]
    assert summary["allatom_family_focus_commercial_primary_upgrade_actions_v1"] == adjusted_pde_review_packet[
        "summary"
    ]["commercial_primary_upgrade_actions_v1"]
    assert summary["selected_allatom_commercial_schema_version"] == "wetlab_commercial_grade_v2"
    assert summary["selected_allatom_commercial_hard_gate_pass_v1"] is False
    assert summary["selected_allatom_commercial_overall_score_v1"] == pde_review_summary["commercial_overall_score_v2"]
    assert summary["selected_allatom_commercial_risk_bucket_v1"] == pde_review_summary["commercial_risk_bucket_v2"]
    assert summary["selected_allatom_commercial_decision_class_v1"] == pde_review_summary[
        "commercial_decision_class_v2"
    ]
    assert summary["selected_allatom_commercial_primary_upgrade_actions_v1"] == adjusted_pde_review_packet[
        "summary"
    ]["commercial_primary_upgrade_actions_v1"]
    assert summary["selected_allatom_best_mean_min_distance_A"] == pde_review_summary["best_mean_min_distance_A"]
    assert summary["selected_allatom_best_mean_min_distance_A_source"] == (
        "tcruzi_pde_allatom_review_packet.best_mean_min_distance_A"
    )
    assert summary["selected_allatom_wetlab_gate_pass"] is pde_review_summary["wetlab_gate_pass"]
    assert summary["selected_allatom_final_gate_pass"] is pde_review_summary["wetlab_final_gate_pass"]
    assert summary["selected_allatom_translation_gate_focus_reason"] == pde_review_summary["translation_gate_focus_reason"]
    assert summary["selected_allatom_recommended_next_expensive_lane_reason"] == pde_review_summary[
        "recommended_next_expensive_lane_reason"
    ]
    assert summary["selected_allatom_readiness_semantics"] in {
        "operator_review_and_final_gate",
        "explicit_split_gate_fields",
    }
    selected_actions_text = summary["selected_allatom_commercial_primary_upgrade_actions_text_v1"]
    assert "strengthen_binding_energy_proxy" in selected_actions_text
    assert "tighten_pose_geometry_under_strict_gate" not in selected_actions_text
    assert "produce_claim_equivalence_packet" in selected_actions_text
    assert summary["selected_allatom_under_2p5_candidate_count"] == pde_review_summary["under_2p5_candidate_count"]
    assert summary["selected_allatom_near_candidate_count"] == pde_review_summary["near_candidate_count"]
    assert summary["selected_allatom_next_required_step"] == translation_shortlist_guidance
    assert summary["selected_allatom_actionability_status"] == "hard_blocked"
    assert summary["selected_allatom_actionability_claim_requirement_mode"] == "not_applicable"
    assert summary["selected_allatom_raw_claim_requirement_mode"] == "semi_hard"
    assert summary["selected_allatom_raw_claim_required_for_final_wetlab"] is True
    assert summary["selected_allatom_effective_actionability_status"] == "hard_blocked"
    assert summary["selected_allatom_effective_actionability_claim_requirement_mode"] == "not_applicable"
    assert summary["selected_allatom_effective_blocking_order"] == "hard_block_first"
    assert summary["selected_allatom_effective_primary_blocking_domain"] == "translation_commercial_hard_gate"
    assert "recompute_binding_energy_proxy" in summary["selected_allatom_action_recipe_codes"]
    assert "recompute_mean_min_distance_A" not in summary["selected_allatom_action_recipe_codes"]
    assert any(
        row.get("category") == "translation_commercial_hard_gate"
        for row in summary["selected_allatom_action_recipe_rows"]
    )
    assert summary["selected_allatom_actionability_next_expensive_lane"] == "defer_expensive_lane"
    assert "recompute_binding_energy_proxy" in summary["selected_allatom_actionability_required_calculations"]
    assert "recompute_mean_min_distance_A" not in summary["selected_allatom_actionability_required_calculations"]
    assert "binding_energy_proxy" in summary["selected_allatom_actionability_block_reason"]
    assert "mean_min_distance_A" not in summary["selected_allatom_actionability_block_reason"]
    assert "Actionability:" in summary["selected_allatom_human_summary"]
    assert summary["selected_allatom_visual_bundle_ready"] is True
    assert summary["selected_allatom_visual_topk_count"] == 4
    assert summary["selected_allatom_visual_primary_movie_mp4_ready"] is True
    assert summary["selected_allatom_visual_availability_rollup"] == (
        "top-k 4 | figures 2 | movie plans 4 | binding-event candidates 4"
    )
    assert summary["selected_allatom_visual_media_ready_rollup"] == (
        "dashboard ready | figure ready | movie scripts 0/4 | movie mp4 0/4 | binding-event clips 0/4"
    )
    assert summary["selected_allatom_visual_human_summary"] == "PDE selected-allatom visuals ready."
    _assert_selected_allatom_commercial_schema(
        "wetlab_cathepsin_k_allatom_review_packet_current.json",
        expected_target_id="Cathepsin K",
        expected_decision_class="commercial_recycle_or_rework",
        expected_risk_bucket="critical",
        expected_primary_upgrade_actions=[
            "tighten_pose_geometry_under_strict_gate",
            "strengthen_binding_energy_proxy",
            "raise_trajectory_stability",
            "reduce_mmpbsa_uncertainty",
            "increase_trajectory_support",
        ],
    )


def test_build_wetlab_current_results_index_prefers_dengue_queue_source_priority(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    primary_queue = {
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
    antitarget_queue = {"summary": {"status": "wetlab_broad_screen_antitarget_execution_queue_ready"}}
    primary_watch_state = {"summary": {"status": "wetlab_broad_screen_primary_watch_state_ready"}}
    antitarget_watch_state = {"summary": {"status": "wetlab_broad_screen_antitarget_watcher_state_ready"}}
    precision_monitor = {
        "summary": {
            "status": "wetlab_broad_screen_precision_monitor_ready",
            "completion_pct": 75.4,
            "successful_completion_pct": 20.8,
            "held_completion_pct": 54.6,
            "focus_target_id": "Dengue NS2B-NS3 protease",
            "focus_shard_id": "17_of_20",
            "focus_queue_status": "running",
            "next_required_step": "Continue or complete Dengue NS2B-NS3 protease shard 17_of_20 through the broad-screen runtime runner.",
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
        primary_queue,
        antitarget_queue,
        primary_watch_state,
        antitarget_watch_state,
        precision_monitor,
        dengue_stage6_tuning_surface=dengue_tuning_surface,
        dengue_exploratory_retry_lane=dengue_exploratory_retry_lane,
    )

    summary = payload["summary"]
    assert summary["dengue_stage6_retry_source_priority"] == "execution_queue"
    assert summary["dengue_stage6_retry_target_id"] == "Dengue NS2B-NS3 protease"
    assert summary["dengue_stage6_retry_shard_id"] == "17_of_20"
    assert summary["dengue_stage6_retry_next_required_step"] == "Continue or complete Dengue NS2B-NS3 protease shard 17_of_20 through the broad-screen runtime runner."
    dengue_rows = [row for row in payload["rows"] if row["group"] == "dengue stage6 retry family"]
    assert len(dengue_rows) == 1
    assert "execution_queue" in dengue_rows[0]["key_signal"]
    assert "17_of_20" in dengue_rows[0]["one_line_summary"]
    assert summary["next_required_step"].startswith("Continue or complete Dengue NS2B-NS3 protease shard 17_of_20")


def test_build_wetlab_current_results_index_keeps_blocked_followup_review_as_next_step(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "wetlab_broad_screen_primary_watch_loop.pid").write_text(str(os.getpid()), encoding="utf-8")
    (runs / "wetlab_broad_screen_antitarget_watcher_loop.pid").write_text(str(os.getpid()), encoding="utf-8")

    retry_handoff_summary = {
        "summary": {
            "status": "wetlab_retry_handoff_summary_ready",
            "manual_retry_focus_target_id": "Leishmania braziliensis DHODH",
            "manual_retry_focus_decision": "pause_auto_start",
            "selected_manual_retry_target_id": "STK17B (DRAK2)",
            "selected_manual_retry_shard_id": "",
            "selected_manual_retry_selected_command_kind": "throughput_preflight_tuned_gate45",
            "selected_manual_retry_lane_label": "exploratory_gate4.5_followup",
            "current_results_next_required_step": "Keep auto-start hard-frozen and review completed follow-up shards 18_of_20;19_of_20;20_of_20 before reopening the STK17B (DRAK2) default lane.",
            "next_required_step": "Keep auto-start hard-frozen and review completed follow-up shards 18_of_20;19_of_20;20_of_20 before reopening the STK17B (DRAK2) default lane.",
        }
    }
    stk17b_exploratory_followup_lane = {
        "summary": {
            "status": "wetlab_stk17b_exploratory_followup_lane_blocked",
            "target_id": "STK17B (DRAK2)",
            "shard_id": "",
            "selected_command_kind": "throughput_preflight_tuned_gate45",
            "followup_lane_label": "exploratory_gate4.5_followup",
            "ready_for_manual_retry": False,
            "followup_shard_ids": "18_of_20;19_of_20;20_of_20",
            "next_required_step": "Keep auto-start hard-frozen and review completed follow-up shards 18_of_20;19_of_20;20_of_20 before reopening the STK17B (DRAK2) default lane.",
        }
    }
    plpro_manual_retry_lane = {
        "summary": {
            "status": "wetlab_plpro_manual_retry_lane_ready",
            "target_id": "SARS-CoV-2 PLpro",
            "shard_id": "17_of_20",
            "ready_for_manual_retry": True,
            "selected_command_kind": "throughput_preflight_tuned_gate55",
            "next_required_step": "Run the PLpro manual retry runner for 17_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
        }
    }

    payload = mod.build_payload(
        {"summary": {"status": "wetlab_broad_screen_execution_queue_ready"}},
        {"summary": {"status": "wetlab_broad_screen_antitarget_execution_queue_ready"}},
        {"summary": {"status": "wetlab_broad_screen_primary_watch_state_ready"}},
        {"summary": {"status": "wetlab_broad_screen_antitarget_watcher_state_ready"}},
        {"summary": {"status": "wetlab_broad_screen_precision_monitor_ready"}},
        {"summary": {"status": "wetlab_primary_stage6_failure_surface_ready"}},
        {"summary": {"status": "wetlab_broad_screen_throughput_bridge_ready"}},
        {"summary": {"status": "wetlab_broad_screen_antitarget_throughput_bridge_ready"}},
        {"summary": {"status": "wetlab_primary_hold_guard_surface_ready"}},
        retry_handoff_summary,
        stk17b_exploratory_followup_lane=stk17b_exploratory_followup_lane,
        plpro_manual_retry_lane=plpro_manual_retry_lane,
        partnering_stack={"summary": {"status": "wetlab_partnering_stack_ready"}},
        master_handoff_dashboard={"summary": {"status": "wetlab_master_handoff_dashboard_ready"}},
        final_campaign_summary={"summary": {"status": "wetlab_final_campaign_summary_ready"}},
        master_terminal_review={"summary": {"status": "wetlab_master_terminal_review_ready"}},
    )
    summary = payload["summary"]
    assert summary["selected_manual_retry_target_id"] == "STK17B (DRAK2)"
    assert summary["selected_manual_retry_lane_label"] == "exploratory_gate4.5_followup"
    assert summary["stk17b_exploratory_followup_shard_id"] == "18_of_20;19_of_20;20_of_20"
    assert summary["selected_manual_retry_shard_id"] == "18_of_20;19_of_20;20_of_20"
    assert summary["next_required_step"].startswith("Keep auto-start hard-frozen and review completed follow-up shards 18_of_20;19_of_20;20_of_20")
    assert summary["plpro_manual_retry_target_id"] == "SARS-CoV-2 PLpro"
    assert summary["plpro_manual_retry_shard_id"] == "17_of_20"
    assert summary["plpro_manual_retry_selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert summary["mapping_fix_retry_support_ready"] is False
    assert summary["mapping_fix_retry_ready_target_count"] == 0
    assert summary["mapping_fix_retry_ready_targets"] == ""
    assert summary["stage1_mapping_fix_lanes_ready"] is False
    assert summary["stage1_mapping_fix_ready_target_count"] == 0
    assert summary["stage1_mapping_fix_ready_targets"] == ""
    assert summary["campaign_terminal_state"] == ""
    assert summary["ready_to_send_track_count"] == 0

    groups = {group["group"]: group for group in payload["groups"]}
    assert len(groups["manual retry lanes"]["rows"]) >= 2
    assert groups["manual retry lanes"]["rows"][0]["surface"] == "retry_handoff_summary"
    assert groups["manual retry lanes"]["rows"][1]["surface"] == "stk17b_exploratory_followup_lane"
    assert "selected" in groups["manual retry lanes"]["rows"][1]["key_signal"]
    assert "Keep auto-start hard-frozen and review completed follow-up shards" in groups["manual retry lanes"]["rows"][1]["one_line_summary"]


def test_write_index_artifact_writes_markdown_and_json(tmp_path: Path) -> None:
    payload = {
        "summary": {
            "status": "wetlab_current_results_index_ready",
            "group_count": 1,
            "surface_count": 1,
            "next_required_step": "Run the SARS-CoV-2 PLpro tuned gate55 manual retry runner for 17_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
        },
        "groups": [
            {
                "group": "primary/counterscreen queue",
                "group_signal": "SARS-CoV-2 PLpro 17_of_20 ready_after_previous_shard",
                "rows": [
                    {
                        "group": "primary/counterscreen queue",
                        "surface": "primary_execution_queue",
                        "artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
                        "status": "wetlab_broad_screen_execution_queue_ready",
                        "key_signal": "SARS-CoV-2 PLpro 17_of_20 ready_after_previous_shard",
                        "one_line_summary": "Run the SARS-CoV-2 PLpro tuned gate55 manual retry runner for 17_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
                    }
                ],
            }
        ],
        "rows": [],
        "structured": {},
    }
    out_md = tmp_path / "wetlab_current_results_index_current.md"
    mod.write_index_artifact(str(out_md), payload)
    assert out_md.exists()
    assert out_md.with_suffix(".json").exists()
    text = out_md.read_text(encoding="utf-8")
    assert "# Wet-Lab Current Results Index" in text
    assert "primary/counterscreen queue" in text
    assert "SARS-CoV-2 PLpro 17_of_20 ready_after_previous_shard" in text
