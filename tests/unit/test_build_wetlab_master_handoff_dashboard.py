from __future__ import annotations

import json
import os
from pathlib import Path

from tools import build_wetlab_master_handoff_dashboard as mod

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
    assert packet_summary["commercial_primary_upgrade_actions_v1"] == expected_primary_upgrade_actions


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
    assert packet_summary["commercial_hard_gate_pass_v2"] is True
    assert packet_summary["commercial_hard_gate_failed_metrics_v2"] == []
    assert packet_summary["commercial_replicate_count_v2"] == 3
    assert packet_summary["commercial_mean_min_distance_iqr_A_v2"] == 0
    assert round(float(packet_summary["commercial_overall_score_v2"]), 1) >= 50.0
    assert round(float(packet_summary["commercial_consistency_score_v2"]), 1) >= 60.0
    assert packet_summary["translation_gate_focus_status"] == expected_translation_status
    assert packet_summary["focus_shortlist_tier"] == expected_shortlist_tier
    assert packet_summary["recommended_next_expensive_lane"] == expected_recommended_lane
    return packet_summary


def test_build_wetlab_master_handoff_dashboard_uses_final_campaign_as_primary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    final_campaign_summary = {"summary": {"status": "wetlab_final_campaign_summary_ready", "campaign_terminal_state": "complete", "ready_to_send_track_count": 5}}
    master_terminal_review = {"summary": {"status": "wetlab_master_terminal_review_ready", "ready_to_send_tracks": "DNDi_IPK; READDI_Korea"}}
    outbound_board = {"summary": {"status": "wetlab_outbound_execution_priority_board_ready", "top_priority_lead_targets": "T. cruzi PDE; Cruzain"}}
    send_round = {"summary": {"status": "wetlab_partner_send_round_ready", "first_dispatch_track_id": "DNDi_IPK", "first_dispatch_lead_targets": "T. cruzi PDE; Cruzain"}}
    export_bundle = {"summary": {"status": "wetlab_partner_first_contact_export_bundle_ready", "sender_name": "강지훈"}}
    broad_screen_queue = {"summary": {"status": "wetlab_broad_screen_queue_ready", "library_size": 100000, "total_queue_rows": 260}}
    broad_screen_bridge = {"summary": {"status": "wetlab_broad_screen_bridge_ready", "final_packet_shape": "top-3 repurposing + top-3 novelty"}}
    broad_screen_compound_universe = {"summary": {"status": "wetlab_broad_screen_compound_universe_ready", "deduped_compound_count": 158}}
    broad_screen_execution_queue = {"summary": {"status": "wetlab_broad_screen_execution_queue_ready", "ready_now_row_count": 1, "first_actionable_target_id": "CA IX", "first_actionable_shard_id": "01_of_20"}}
    broad_screen_autofill = {"summary": {"status": "wetlab_broad_screen_repurposing_autofill_ready", "override_target_count": 0}}
    broad_screen_antitarget_queue = {"summary": {"status": "wetlab_broad_screen_antitarget_queue_ready", "ready_now_row_count": 1}}
    broad_screen_antitarget_execution_queue = {
        "summary": {
            "status": "wetlab_broad_screen_antitarget_execution_queue_ready",
            "ready_now_row_count": 0,
            "running_row_count": 1,
            "first_actionable_primary_target_id": "CA IX",
            "first_actionable_anti_target_id": "CA II",
        }
    }
    broad_screen_primary_watch_state = {"summary": {"status": "wetlab_broad_screen_primary_watcher_ready", "compute_state": "running_under_watcher", "actions_taken_count": 0}}
    broad_screen_primary_watch = {"summary": {"status": "wetlab_broad_screen_primary_watcher_ready", "compute_state": "running_under_watcher", "actions_taken_count": 0}}
    broad_screen_antitarget_watch_state = {"summary": {"status": "wetlab_broad_screen_antitarget_watcher_state_ready", "watcher_decision": "continue_running_compute_attached"}}
    broad_screen_antitarget_watch = {"summary": {"status": "wetlab_broad_screen_antitarget_watcher_ready", "last_action": "noop"}}
    broad_screen_stk17b_manual_retry_lane = {
        "summary": {
            "status": "wetlab_stk17b_manual_retry_lane_ready",
            "target_id": "STK17B (DRAK2)",
            "shard_id": "12_of_20",
            "ready_for_manual_retry": True,
            "selected_command_kind": "throughput_preflight_tuned_gate55",
            "next_required_step": "Run the STK17B tuned gate55 manual retry runner for 12_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
        }
    }
    broad_screen_stk17b_exploratory_retry_lane = {
        "summary": {
            "status": "wetlab_stk17b_exploratory_retry_lane_ready",
            "target_id": "STK17B (DRAK2)",
            "shard_id": "17_of_20",
            "ready_for_manual_retry": True,
            "selected_command_kind": "throughput_preflight_tuned_gate45",
            "selected_threshold_A": 4.5,
            "guard_active": True,
            "guard_hold_streak": 3,
            "guard_limit": 3,
            "next_required_step": "Run the STK17B exploratory gate4.5 manual retry runner for 17_of_20; compare the outcome against the retry campaign band before relaxing broader kinase gates.",
        }
    }
    broad_screen_stk17b_exploratory_followup_lane = {
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
    broad_screen_stk17b_followup_review_surface = {
        "summary": {
            "status": "wetlab_stk17b_followup_review_surface_ready",
            "target_id": "STK17B (DRAK2)",
            "decision": "branch_to_gate45_only_keep_default_closed",
            "decision_rationale": "17_of_20 succeeded under the 4.5A exploratory gate while follow-up shards 18-20 held under the default 2.5A gate.",
            "next_required_step": "Keep the STK17B (DRAK2) default lane closed and branch this target into the gate4.5 exploratory lane only; treat 18_of_20;19_of_20;20_of_20 as default-gate follow-up holds, not as evidence against the 4.5A path, until the follow-up runner preserves the 4.5A threshold end-to-end.",
        }
    }
    broad_screen_retry_handoff_summary = {
        "summary": {
            "status": "wetlab_retry_handoff_summary_ready",
            "selected_rescue_branch_surface_label": "pde_rescue_only_branch",
            "selected_rescue_branch_next_required_step": "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, and use the promoted top-4 packet as the review unit before any reopen decision.",
        }
    }
    broad_screen_dpre1_branch_review_surface = {
        "summary": {
            "status": "wetlab_dpre1_branch_review_surface_ready",
            "target_id": "DprE1",
            "branch_label": "dpre1_guarded_review_branch",
            "exploratory_retry_next_required_step": "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying.",
            "next_required_step": "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying.",
        }
    }
    broad_screen_tcruzi_pde_rescue_only_branch_summary = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_only_branch_summary_ready",
            "next_required_step": "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, and use the promoted top-4 packet as the review unit before any reopen decision.",
        }
    }
    broad_screen_plpro_manual_retry_lane = {
        "summary": {
            "status": "wetlab_plpro_manual_retry_lane_ready",
            "target_id": "SARS-CoV-2 PLpro",
            "shard_id": "17_of_20",
            "ready_for_manual_retry": True,
            "selected_command_kind": "throughput_preflight_tuned_gate55",
            "next_required_step": "Run the PLpro manual retry runner for 17_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
        }
    }
    broad_screen_mapping_fix_retry_support = {
        "summary": {
            "status": "wetlab_mapping_fix_retry_support_ready",
            "ready_target_count": 2,
            "ready_targets": "SARS-CoV-2 Mpro; T. cruzi PDE",
            "next_required_step": "Run the mapping-fix retry runner for SARS-CoV-2 Mpro 01_of_20; keep auto-start blocked until the mapping diagnostics rerun lands a clean summary.",
        }
    }
    broad_screen_stage1_mapping_fix_lanes = {
        "summary": {
            "status": "wetlab_stage1_mapping_fix_lanes_ready",
            "ready_target_count": 2,
            "ready_targets": "SARS-CoV-2 Mpro; T. cruzi PDE",
            "next_required_step": "Run the mapping-fix retry runner for SARS-CoV-2 Mpro 01_of_20; keep auto-start blocked until the mapping diagnostics rerun lands a clean summary.",
        }
    }
    broad_screen_mapping_fix_retry_policy_templates = {
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
    broad_screen_hard_target_rescue_lane = {
        "summary": {
            "status": "wetlab_hard_target_rescue_lane_ready",
            "target_id": "Cathepsin K",
            "shard_id": "05_of_20",
            "stage1_ok": True,
            "stage6_fail": True,
            "auto_hold_streak": 4,
            "selected_command_kind": "hard_target_rescue_lane",
            "lane_label": "hard_target_rescue_lane",
            "next_required_step": "Run the hard-target rescue lane for Cathepsin K 05_of_20; keep the default lane closed.",
        }
    }
    broad_screen_rescue_anchor_artifacts = {
        "summary": {
            "status": "wetlab_rescue_anchor_artifacts_ready",
            "target_id": "Cathepsin K",
            "anchor_artifact_count": 2,
            "rescue_only": True,
            "native_anchor_artifact": "cathepsin_native_anchor.csv",
            "pocket_anchor_artifact": "cathepsin_pocket_anchor.csv",
            "next_required_step": "Review rescue anchors for Cathepsin K; keep the default lane closed.",
        }
    }
    broad_screen_rescue_three_bead_candidates = {
        "summary": {
            "status": "wetlab_rescue_three_bead_candidates_ready",
            "target_id": "T. cruzi PDE",
            "candidate_count": 3,
            "top_n": 3,
            "selected_command_kind": "throughput_preflight_tuned_gate51",
            "selected_threshold_A": 5.1,
            "next_required_step": "Review 3-bead rescue candidates for T. cruzi PDE; keep the default lane closed.",
        }
    }
    broad_screen_kinase_retry_policy_templates = {
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
    broad_screen_target_retry_policy_templates = {
        "summary": {
            "status": "wetlab_target_retry_policy_templates_ready",
            "template_target_count": 6,
            "empirical_validated_target_count": 2,
            "non_kinase_template_target_count": 3,
            "non_kinase_empirical_validated_target_count": 1,
            "guarded_gate55_candidate_target_count": 1,
            "guarded_gate51_candidate_target_count": 1,
            "focus_target_id": "Leishmania braziliensis DHODH",
            "focus_template_label": "gate51_branch_only_empirical",
            "focus_selected_command_kind": "throughput_preflight_tuned_gate51",
            "focus_selected_threshold_A": 5.1,
            "next_required_step": "Promote DHODH gate5.1 as validated, keep the default lane closed, and reserve any future DHODH reopen for an explicit new review.",
        }
    }
    broad_screen_lbdhodh_stage6_tuning_surface = {
        "summary": {
            "status": "wetlab_lbdhodh_stage6_tuning_surface_ready",
            "recommended_observed_threshold_A": 5.1,
            "immediately_runnable_command_kind": "throughput_preflight_tuned_gate51",
        }
    }
    broad_screen_lbdhodh_exploratory_retry_lane = {
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
    broad_screen_lbdhodh_gate51_validation_review_surface = {
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

    payload = mod.build_payload(
        final_campaign_summary,
        master_terminal_review,
        outbound_board,
        send_round,
        export_bundle,
        broad_screen_queue,
        broad_screen_bridge,
        broad_screen_compound_universe,
        broad_screen_execution_queue,
        broad_screen_autofill,
        broad_screen_antitarget_queue=broad_screen_antitarget_queue,
        broad_screen_antitarget_execution_queue=broad_screen_antitarget_execution_queue,
        broad_screen_primary_watch_state=broad_screen_primary_watch_state,
        broad_screen_primary_watch=broad_screen_primary_watch,
        broad_screen_antitarget_watch_state=broad_screen_antitarget_watch_state,
        broad_screen_antitarget_watch=broad_screen_antitarget_watch,
        broad_screen_retry_handoff_summary=broad_screen_retry_handoff_summary,
        broad_screen_dpre1_branch_review_surface=broad_screen_dpre1_branch_review_surface,
        broad_screen_tcruzi_pde_rescue_only_branch_summary=broad_screen_tcruzi_pde_rescue_only_branch_summary,
        broad_screen_stk17b_manual_retry_lane=broad_screen_stk17b_manual_retry_lane,
        broad_screen_stk17b_exploratory_retry_lane=broad_screen_stk17b_exploratory_retry_lane,
        broad_screen_stk17b_exploratory_followup_lane=broad_screen_stk17b_exploratory_followup_lane,
        broad_screen_stk17b_followup_review_surface=broad_screen_stk17b_followup_review_surface,
        broad_screen_plpro_manual_retry_lane=broad_screen_plpro_manual_retry_lane,
        broad_screen_mapping_fix_retry_support=broad_screen_mapping_fix_retry_support,
        broad_screen_stage1_mapping_fix_lanes=broad_screen_stage1_mapping_fix_lanes,
        broad_screen_mapping_fix_retry_policy_templates=broad_screen_mapping_fix_retry_policy_templates,
        broad_screen_hard_target_rescue_lane=broad_screen_hard_target_rescue_lane,
        broad_screen_rescue_anchor_artifacts=broad_screen_rescue_anchor_artifacts,
        broad_screen_rescue_three_bead_candidates=broad_screen_rescue_three_bead_candidates,
        broad_screen_kinase_retry_policy_templates=broad_screen_kinase_retry_policy_templates,
        broad_screen_target_retry_policy_templates=broad_screen_target_retry_policy_templates,
        broad_screen_lbdhodh_stage6_tuning_surface=broad_screen_lbdhodh_stage6_tuning_surface,
        broad_screen_lbdhodh_exploratory_retry_lane=broad_screen_lbdhodh_exploratory_retry_lane,
        broad_screen_lbdhodh_gate51_validation_review_surface=broad_screen_lbdhodh_gate51_validation_review_surface,
    )
    assert payload["summary"]["status"] == "wetlab_master_handoff_dashboard_ready"
    assert payload["summary"]["primary_surface_artifact"] == "runs/wetlab_final_campaign_summary_current.md"
    assert payload["summary"]["first_dispatch_track_id"] == "DNDi_IPK"
    assert payload["summary"]["broad_screen_total_queue_rows"] == 260
    assert payload["summary"]["broad_screen_ingested_compound_count"] == 158
    assert payload["summary"]["broad_screen_execution_ready_now_row_count"] == 1
    assert payload["summary"]["broad_screen_first_actionable_target_id"] == "CA IX"
    assert payload["summary"]["broad_screen_antitarget_ready_now_row_count"] == 1
    assert payload["summary"]["broad_screen_antitarget_running_row_count"] == 1
    assert payload["summary"]["broad_screen_antitarget_first_actionable_primary_target_id"] == "CA IX"
    assert payload["summary"]["broad_screen_antitarget_first_actionable_anti_target_id"] == "CA II"
    assert payload["summary"]["broad_screen_primary_watch_state_ready"] is True
    assert payload["summary"]["broad_screen_primary_watch_ready"] is True
    assert payload["summary"]["broad_screen_primary_watch_decision"] == "running_under_watcher"
    assert payload["summary"]["broad_screen_primary_watch_loop_attached"] is True
    assert payload["summary"]["broad_screen_primary_watch_liveness"] == "attached"
    assert payload["summary"]["broad_screen_primary_watch_fallback_mode"] == "compute-attached"
    assert payload["summary"]["broad_screen_antitarget_watch_state_ready"] is True
    assert payload["summary"]["broad_screen_antitarget_watch_ready"] is True
    assert payload["summary"]["broad_screen_antitarget_watch_decision"] == "continue_running_compute_attached"
    assert payload["summary"]["broad_screen_antitarget_watch_loop_attached"] is True
    assert payload["summary"]["broad_screen_antitarget_watch_liveness"] == "attached"
    assert payload["summary"]["broad_screen_antitarget_watch_fallback_mode"] == "compute-attached"
    assert payload["summary"]["broad_screen_dpre1_branch_review_ready"] is True
    assert payload["summary"]["broad_screen_dpre1_branch_review_next_required_step"] == "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying."
    assert payload["summary"]["selected_rescue_branch_surface_label"] == "pde_rescue_only_branch"
    assert payload["summary"]["selected_rescue_branch_next_required_step"] == "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, and use the promoted top-4 packet as the review unit before any reopen decision."
    assert payload["summary"]["broad_screen_stk17b_exploratory_retry_lane_ready"] is True
    assert payload["summary"]["broad_screen_stk17b_exploratory_retry_ready_for_manual_retry"] is True
    assert payload["summary"]["broad_screen_stk17b_exploratory_retry_target_id"] == "STK17B (DRAK2)"
    assert payload["summary"]["broad_screen_stk17b_exploratory_retry_shard_id"] == "17_of_20"
    assert payload["summary"]["broad_screen_stk17b_exploratory_retry_selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert payload["summary"]["broad_screen_stk17b_exploratory_retry_selected_threshold_A"] == 4.5
    assert payload["summary"]["broad_screen_stk17b_exploratory_freeze_state"] == "hard_freeze_after_exploratory_success"
    assert payload["summary"]["broad_screen_stk17b_exploratory_freeze_hold_streak"] == 3
    assert payload["summary"]["broad_screen_stk17b_exploratory_freeze_hold_limit"] == 3
    assert payload["summary"]["broad_screen_stk17b_exploratory_followup_lane_ready"] is True
    assert payload["summary"]["broad_screen_stk17b_exploratory_followup_target_id"] == "STK17B (DRAK2)"
    assert payload["summary"]["broad_screen_stk17b_exploratory_followup_shard_id"] == "18_of_20"
    assert payload["summary"]["broad_screen_stk17b_exploratory_followup_selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert payload["summary"]["broad_screen_stk17b_exploratory_followup_lane_label"] == "exploratory_gate4.5_followup"
    assert payload["summary"]["broad_screen_stk17b_exploratory_followup_freeze_state"] == "hard_freeze_after_exploratory_success"
    assert payload["summary"]["broad_screen_stk17b_exploratory_followup_freeze_note"].startswith("Auto-start remains hard-frozen after the gate4.5 success")
    assert payload["summary"]["broad_screen_stk17b_followup_review_surface_ready"] is True
    assert payload["summary"]["broad_screen_stk17b_followup_review_decision"] == "branch_to_gate45_only_keep_default_closed"
    assert payload["summary"]["broad_screen_stk17b_manual_retry_lane_ready"] is True
    assert payload["summary"]["broad_screen_stk17b_manual_retry_ready_for_manual_retry"] is True
    assert payload["summary"]["broad_screen_stk17b_manual_retry_target_id"] == "STK17B (DRAK2)"
    assert payload["summary"]["broad_screen_stk17b_manual_retry_shard_id"] == "12_of_20"
    assert payload["summary"]["broad_screen_stk17b_manual_retry_selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert payload["summary"]["broad_screen_plpro_manual_retry_lane_ready"] is True
    assert payload["summary"]["broad_screen_plpro_manual_retry_ready_for_manual_retry"] is True
    assert payload["summary"]["broad_screen_plpro_manual_retry_target_id"] == "SARS-CoV-2 PLpro"
    assert payload["summary"]["broad_screen_plpro_manual_retry_shard_id"] == "17_of_20"
    assert payload["summary"]["broad_screen_plpro_manual_retry_selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert payload["summary"]["broad_screen_mapping_fix_retry_support_ready"] is True
    assert payload["summary"]["broad_screen_mapping_fix_retry_ready_target_count"] == 2
    assert payload["summary"]["broad_screen_mapping_fix_retry_ready_targets"] == "SARS-CoV-2 Mpro; T. cruzi PDE"
    assert payload["summary"]["broad_screen_stage1_mapping_fix_lanes_ready"] is True
    assert payload["summary"]["broad_screen_stage1_mapping_fix_ready_target_count"] == 2
    assert payload["summary"]["broad_screen_stage1_mapping_fix_ready_targets"] == "SARS-CoV-2 Mpro; T. cruzi PDE"
    assert payload["summary"]["broad_screen_mapping_fix_retry_policy_templates_ready"] is True
    assert payload["summary"]["broad_screen_mapping_fix_retry_template_target_count"] == 2
    assert payload["summary"]["broad_screen_mapping_fix_retry_ready_target_count"] == 2
    assert payload["summary"]["broad_screen_mapping_fix_retry_focus_target_id"] == "SARS-CoV-2 Mpro"
    assert payload["summary"]["broad_screen_mapping_fix_retry_focus_template_label"] == "mapping_fix_branch_only"
    assert payload["summary"]["broad_screen_mapping_fix_retry_focus_selected_command_kind"] == "throughput_preflight"
    assert payload["summary"]["broad_screen_mapping_fix_retry_next_required_step"].startswith("Run the mapping-fix retry runner for SARS-CoV-2 Mpro")
    assert payload["summary"]["broad_screen_hard_target_rescue_lane_ready"] is True
    assert payload["summary"]["broad_screen_hard_target_rescue_lane_target_id"] == "Cathepsin K"
    assert payload["summary"]["broad_screen_hard_target_rescue_lane_shard_id"] == "05_of_20"
    assert payload["summary"]["broad_screen_hard_target_rescue_lane_stage1_ok"] is True
    assert payload["summary"]["broad_screen_hard_target_rescue_lane_stage6_fail"] is True
    assert payload["summary"]["broad_screen_hard_target_rescue_lane_auto_hold_streak"] == 4
    assert payload["summary"]["broad_screen_hard_target_rescue_lane_selected_command_kind"] == "hard_target_rescue_lane"
    assert payload["summary"]["broad_screen_hard_target_rescue_lane_lane_label"] == "hard_target_rescue_lane"
    assert payload["summary"]["broad_screen_hard_target_rescue_lane_next_required_step"].startswith("Run the hard-target rescue lane for Cathepsin K")
    assert payload["summary"]["broad_screen_rescue_anchor_artifacts_ready"] is True
    assert payload["summary"]["broad_screen_rescue_anchor_target_id"] == "Cathepsin K"
    assert payload["summary"]["broad_screen_rescue_anchor_artifact_count"] == 2
    assert payload["summary"]["broad_screen_rescue_anchor_rescue_only"] is True
    assert payload["summary"]["broad_screen_rescue_anchor_native_anchor_artifact"] == "cathepsin_native_anchor.csv"
    assert payload["summary"]["broad_screen_rescue_anchor_pocket_anchor_artifact"] == "cathepsin_pocket_anchor.csv"
    assert payload["summary"]["broad_screen_rescue_anchor_next_required_step"].startswith("Review rescue anchors for Cathepsin K")
    assert payload["summary"]["broad_screen_rescue_three_bead_candidates_ready"] is True
    assert payload["summary"]["broad_screen_rescue_three_bead_candidate_target_id"] == "T. cruzi PDE"
    assert payload["summary"]["broad_screen_rescue_three_bead_candidate_count"] == 3
    assert payload["summary"]["broad_screen_rescue_three_bead_candidate_top_n"] == 3
    assert payload["summary"]["broad_screen_rescue_three_bead_candidate_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert payload["summary"]["broad_screen_rescue_three_bead_candidate_selected_threshold_A"] == 5.1
    assert payload["summary"]["broad_screen_rescue_three_bead_candidate_next_required_step"].startswith("Review 3-bead rescue candidates for T. cruzi PDE")
    assert payload["summary"]["broad_screen_kinase_retry_policy_templates_ready"] is True
    assert payload["summary"]["broad_screen_kinase_retry_template_target_count"] == 3
    assert payload["summary"]["broad_screen_kinase_retry_empirical_validated_target_count"] == 1
    assert payload["summary"]["broad_screen_kinase_retry_gate45_only_target_count"] == 1
    assert payload["summary"]["broad_screen_kinase_retry_guarded_gate55_candidate_target_count"] == 1
    assert payload["summary"]["broad_screen_kinase_retry_focus_target_id"] == "STK17B (DRAK2)"
    assert payload["summary"]["broad_screen_kinase_retry_focus_template_label"] == "gate45_branch_only_empirical"
    assert payload["summary"]["broad_screen_kinase_retry_focus_selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert payload["summary"]["broad_screen_target_retry_policy_templates_ready"] is True
    assert payload["summary"]["broad_screen_target_retry_template_target_count"] == 6
    assert payload["summary"]["broad_screen_target_retry_empirical_validated_target_count"] == 2
    assert payload["summary"]["broad_screen_target_retry_non_kinase_template_target_count"] == 3
    assert payload["summary"]["broad_screen_target_retry_non_kinase_empirical_validated_target_count"] == 1
    assert payload["summary"]["broad_screen_target_retry_guarded_gate55_candidate_target_count"] == 1
    assert payload["summary"]["broad_screen_target_retry_guarded_gate51_candidate_target_count"] == 1
    assert payload["summary"]["broad_screen_target_retry_focus_target_id"] == "Leishmania braziliensis DHODH"
    assert payload["summary"]["broad_screen_target_retry_focus_template_label"] == "gate51_branch_only_empirical"
    assert payload["summary"]["broad_screen_target_retry_focus_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert payload["summary"]["broad_screen_target_retry_focus_selected_threshold_A"] == 5.1
    assert payload["summary"]["broad_screen_target_retry_next_required_step"].startswith("Promote DHODH gate5.1 as validated")
    assert payload["summary"]["broad_screen_target_retry_policy_templates_artifact"] == "runs/wetlab_target_retry_policy_templates_current.md"
    assert payload["summary"]["broad_screen_mapping_fix_retry_policy_templates_artifact"] == "runs/wetlab_mapping_fix_retry_policy_templates_current.md"
    assert payload["summary"]["broad_screen_lbdhodh_stage6_tuning_surface_ready"] is True
    assert payload["summary"]["broad_screen_lbdhodh_stage6_recommended_threshold_A"] == 5.1
    assert payload["summary"]["broad_screen_lbdhodh_stage6_immediately_runnable_command_kind"] == "throughput_preflight_tuned_gate51"
    assert payload["summary"]["broad_screen_lbdhodh_gate51_validation_review_surface_ready"] is True
    assert payload["summary"]["broad_screen_lbdhodh_gate51_validated"] is True
    assert payload["summary"]["broad_screen_lbdhodh_gate51_validation_decision"] == "promote_gate51_validated_keep_default_closed"
    assert payload["summary"]["broad_screen_lbdhodh_gate51_validation_validated_command_kind"] == "throughput_preflight_tuned_gate51"
    assert payload["summary"]["broad_screen_lbdhodh_gate51_validation_validated_threshold_A"] == 5.1
    assert payload["summary"]["broad_screen_lbdhodh_retry_lane_ready"] is True
    assert payload["summary"]["broad_screen_lbdhodh_retry_ready_for_manual_retry"] is True
    assert payload["summary"]["broad_screen_lbdhodh_retry_target_id"] == "Leishmania braziliensis DHODH"
    assert payload["summary"]["broad_screen_lbdhodh_retry_shard_id"] == "20_of_20"
    assert payload["summary"]["broad_screen_lbdhodh_retry_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert any(row["surface"] == "broad_screen_target_retry_policy_templates" for row in payload["rows"])
    assert any(row["surface"] == "broad_screen_mapping_fix_retry_policy_templates" for row in payload["rows"])
    assert payload["summary"]["next_required_step"].startswith("Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying.")


def test_build_wetlab_master_handoff_dashboard_surfaces_selected_allatom_v2_translation_and_shortlist(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)

    packet_summary = _assert_selected_allatom_commercial_v2_translation_contract(
        "wetlab_tcruzi_pde_allatom_review_packet_current.json",
        expected_target_id="T. cruzi PDE",
        expected_translation_status="borderline",
        expected_shortlist_tier="defer",
        expected_recommended_lane="defer_expensive_lane",
    )
    (runs / "wetlab_tcruzi_pde_allatom_review_packet_current.json").write_text(
        json.dumps({"summary": packet_summary}),
        encoding="utf-8",
    )

    selected_next_step = (
        "Review the promoted PDE pseudo all-atom top-4 packet manually only, keep the default lane closed, "
        f"and do not treat this rescue-only packet as wetlab-ready because commercial grade v2 is "
        f"{packet_summary['commercial_overall_score_v2']:.1f}, translation gate focus is "
        f"{packet_summary['translation_gate_focus_status']}, shortlist tier is {packet_summary['focus_shortlist_tier']}, "
        f"and recommended next lane is {packet_summary['recommended_next_expensive_lane']}."
    )

    final_campaign_summary = {"summary": {"status": "wetlab_final_campaign_summary_ready", "campaign_terminal_state": "complete"}}
    master_terminal_review = {"summary": {"status": "wetlab_master_terminal_review_ready"}}
    outbound_board = {"summary": {"status": "wetlab_outbound_execution_priority_board_ready"}}
    send_round = {"summary": {"status": "wetlab_partner_send_round_ready"}}
    export_bundle = {"summary": {"status": "wetlab_partner_first_contact_export_bundle_ready"}}
    broad_screen_queue = {"summary": {"status": "wetlab_broad_screen_queue_ready"}}
    broad_screen_bridge = {"summary": {"status": "wetlab_broad_screen_bridge_ready"}}
    broad_screen_compound_universe = {"summary": {"status": "wetlab_broad_screen_compound_universe_ready"}}
    broad_screen_execution_queue = {"summary": {"status": "wetlab_broad_screen_execution_queue_ready"}}
    broad_screen_repurposing_autofill = {"summary": {"status": "wetlab_broad_screen_repurposing_autofill_ready"}}
    broad_screen_retry_handoff_summary = {
        "summary": {
            "status": "wetlab_retry_handoff_summary_ready",
            "selected_allatom_target_id": packet_summary["target_id"],
            "selected_allatom_surface_label": "tcruzi_pde_allatom_review_packet",
            "selected_allatom_selected_command_kind": "pseudo_allatom_backmapping_rescore",
            "selected_allatom_selected_threshold_A": 2.5,
            "selected_allatom_packet_scope": "partner_operator_allatom_rescue_review",
            "selected_allatom_packet_ready_for_operator_review": True,
            "selected_allatom_wetlab_gate_pass": packet_summary["wetlab_gate_pass"],
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
            "selected_allatom_best_mean_min_distance_A": packet_summary["best_mean_min_distance_A"],
            "selected_allatom_promoted_candidate_count": 4,
            "selected_allatom_under_2p5_candidate_count": packet_summary["under_2p5_candidate_count"],
            "selected_allatom_near_candidate_count": packet_summary["near_candidate_count"],
            "selected_allatom_next_required_step": selected_next_step,
        }
    }

    payload = mod.build_payload(
        final_campaign_summary,
        master_terminal_review,
        outbound_board,
        send_round,
        export_bundle,
        broad_screen_queue,
        broad_screen_bridge,
        broad_screen_compound_universe,
        broad_screen_execution_queue,
        broad_screen_repurposing_autofill,
        broad_screen_retry_handoff_summary=broad_screen_retry_handoff_summary,
        broad_screen_selected_allatom_visual_bundle={
            "summary": {
                "status": "selected_allatom_visual_bundle_ready",
                "target_id": packet_summary["target_id"],
                "assets_dir": "/tmp/pde_visuals",
                "dashboard_html": "/tmp/pde_visuals/dashboard.html",
                "primary_figure_path": "/tmp/pde_visuals/hero.png",
                "primary_movie_script_path": "/tmp/pde_visuals/hero.cxc",
                "primary_movie_mp4_path": "/tmp/pde_visuals/hero.mp4",
                "topk_count": 4,
                "figure_count": 2,
                "movie_plan_count": 4,
                "binding_event_candidate_count": 4,
                "human_summary": "PDE focus visuals ready for review.",
            }
        },
    )

    summary = payload["summary"]
    assert summary["selected_allatom_commercial_schema_version"] == "wetlab_commercial_grade_v2"
    assert summary["selected_allatom_commercial_human_summary_v1"].startswith("Commercial grade v2:")
    assert summary["selected_allatom_human_summary"].startswith("Selected all-atom focus")
    assert "commercial grade v2" in summary["selected_allatom_human_summary"].lower()
    assert summary["selected_allatom_translation_gate_reason"] == packet_summary["translation_gate_focus_reason"]
    assert summary["selected_allatom_recommended_next_expensive_lane_reason"] == packet_summary[
        "recommended_next_expensive_lane_reason"
    ]
    assert packet_summary["recommended_next_expensive_lane_reason"] in summary["selected_allatom_translation_human_summary"]
    assert summary["selected_allatom_next_required_step"] == (
        "Selected all-atom delivery P0 is green; broader/default wetlab lane remains closed; "
        "translation gate remains borderline; expensive lane deferred."
    )
    assert selected_next_step not in summary["selected_allatom_next_required_step"]
    assert summary["next_required_step"] == summary["selected_allatom_next_required_step"]
    assert summary["selected_allatom_actionability_status"] == "ready"
    expected_claim_mode = "semi_hard"
    assert summary["selected_allatom_actionability_claim_requirement_mode"] == expected_claim_mode
    assert summary["selected_allatom_actionability_next_expensive_lane"] == "defer_expensive_lane"
    assert summary["selected_allatom_raw_claim_requirement_mode"] == "semi_hard"
    assert summary["selected_allatom_raw_claim_required_for_final_wetlab"] is True
    assert summary["selected_allatom_effective_actionability_status"] == summary["selected_allatom_actionability_status"]
    assert summary["selected_allatom_effective_actionability_claim_requirement_mode"] == expected_claim_mode
    assert summary["selected_allatom_effective_actionability_claim_requirement_status"] == "satisfied"
    assert summary["selected_allatom_effective_blocking_order"] == "clear"
    assert summary["selected_allatom_effective_primary_blocking_domain"] == "soft_guidance"
    assert summary["selected_allatom_commercial_hard_gate_failed_metrics_v2"] == []
    assert summary["selected_allatom_actionability_translation_gate_v2_failed_metrics"] == []
    assert "recompute_binding_energy_proxy" not in summary["selected_allatom_action_recipe_codes"]
    assert "recompute_mean_min_distance_iqr_A" not in summary["selected_allatom_action_recipe_codes"]
    assert "resolve_claim_equivalence_gate" in summary["selected_allatom_action_recipe_codes"]
    assert "recompute_claim_gate_required_unavailable" not in summary["selected_allatom_action_recipe_codes"]
    assert "defer_expensive_lane" in summary["selected_allatom_action_recipe_codes"]
    assert (
        f"blocking order {summary['selected_allatom_effective_blocking_order']}"
        in summary["selected_allatom_claim_actionability_split_summary"]
    )
    assert summary["selected_allatom_actionability_required_calculations_text"] in {
        "",
        "strengthen_three_bead_binding_energy",
    }
    assert "Actionability:" in summary["selected_allatom_human_summary"]
    assert "translation gate remains borderline" in summary["selected_allatom_next_required_step"]
    assert "broader/default wetlab lane remains closed" in summary["selected_allatom_next_required_step"]
    assert "expensive lane deferred" in summary["selected_allatom_next_required_step"]
    assert summary["selected_allatom_best_mean_min_distance_A"] == packet_summary["best_mean_min_distance_A"]
    assert summary["selected_allatom_metric_source"] == "review_packet_summary.best_mean_min_distance_A"
    assert summary["selected_allatom_visual_bundle_ready"] is True
    assert summary["selected_allatom_visual_availability_rollup"] == (
        "top-k 4 | figures 2 | movie plans 4 | binding-event candidates 4"
    )
    assert summary["selected_allatom_visual_media_ready_rollup"] == (
        "dashboard ready | figure ready | movie scripts 0/4 | movie mp4 0/4 | binding-event clips 0/4"
    )
    assert summary["selected_allatom_visual_human_summary"] == "PDE focus visuals ready for review."

    focus_row = next(row for row in payload["rows"] if row["surface"] == "broad_screen_selected_allatom_focus")
    assert "commercial grade v2" in focus_row["one_line_summary"].lower()
    assert "translation gate remains borderline" in focus_row["one_line_summary"]
    assert "broader/default wetlab lane remains closed" in focus_row["one_line_summary"]
    assert "expensive lane deferred" in focus_row["one_line_summary"]
    assert packet_summary["recommended_next_expensive_lane_reason"] in focus_row["one_line_summary"]
    assert "Visual: PDE focus visuals ready for review." in focus_row["one_line_summary"]
    assert "Media: dashboard ready | figure ready | movie scripts 0/4 | movie mp4 0/4 | binding-event clips 0/4." in focus_row["one_line_summary"]
    actionability_row = next(row for row in payload["rows"] if row["surface"] == "broad_screen_selected_allatom_actionability")
    assert actionability_row["status"] == summary["selected_allatom_actionability_status"]
    assert "resolve_claim_equivalence_gate" in actionability_row["one_line_summary"]
    assert "raw claim semi_hard" in actionability_row["one_line_summary"]
    assert f"blocking order {summary['selected_allatom_effective_blocking_order']}" in actionability_row["one_line_summary"]


def test_build_wetlab_master_handoff_dashboard_keeps_pde_final_gate_data_separate(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    final_campaign_summary = {"summary": {"status": "wetlab_final_campaign_summary_ready", "campaign_terminal_state": "complete"}}
    master_terminal_review = {"summary": {"status": "wetlab_master_terminal_review_ready"}}
    outbound_board = {"summary": {"status": "wetlab_outbound_execution_priority_board_ready"}}
    send_round = {"summary": {"status": "wetlab_partner_send_round_ready"}}
    export_bundle = {"summary": {"status": "wetlab_partner_first_contact_export_bundle_ready"}}
    broad_screen_queue = {"summary": {"status": "wetlab_broad_screen_queue_ready"}}
    broad_screen_bridge = {"summary": {"status": "wetlab_broad_screen_bridge_ready"}}
    broad_screen_compound_universe = {"summary": {"status": "wetlab_broad_screen_compound_universe_ready"}}
    broad_screen_execution_queue = {"summary": {"status": "wetlab_broad_screen_execution_queue_ready"}}
    broad_screen_repurposing_autofill = {"summary": {"status": "wetlab_broad_screen_repurposing_autofill_ready"}}
    broad_screen_retry_handoff_summary = {
        "summary": {
            "status": "wetlab_retry_handoff_summary_ready",
            "selected_rescue_branch_surface_label": "pde_rescue_only_branch",
            "selected_rescue_branch_target_id": "T. cruzi PDE",
            "selected_rescue_branch_operator_packet_ready": True,
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
    broad_screen_tcruzi_pde_promoted_top4_review_packet = {
        "summary": {
            "status": "wetlab_tcruzi_pde_promoted_top4_review_packet_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "packet_ready_for_operator_review": True,
            "wetlab_final_gate_pass": False,
            "claim_gate_available": True,
            "claim_ready_for_allatom": False,
            "packet_ready": True,
        }
    }
    broad_screen_tcruzi_pde_rescue_only_branch_summary = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_only_branch_summary_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "promoted_top4_packet_ready": True,
            "promoted_candidate_count": 4,
            "under_2p5_candidate_count": 1,
            "next_required_step": (
                "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, "
                "and use the promoted top-4 packet as the review unit before any reopen decision."
            ),
        }
    }

    payload = mod.build_payload(
        final_campaign_summary,
        master_terminal_review,
        outbound_board,
        send_round,
        export_bundle,
        broad_screen_queue,
        broad_screen_bridge,
        broad_screen_compound_universe,
        broad_screen_execution_queue,
        broad_screen_repurposing_autofill,
        broad_screen_retry_handoff_summary=broad_screen_retry_handoff_summary,
        broad_screen_tcruzi_pde_promoted_top4_review_packet=broad_screen_tcruzi_pde_promoted_top4_review_packet,
        broad_screen_tcruzi_pde_rescue_only_branch_summary=broad_screen_tcruzi_pde_rescue_only_branch_summary,
    )

    summary = payload["summary"]
    assert summary["broad_screen_tcruzi_pde_promoted_top4_review_packet_ready"] is True
    assert summary["broad_screen_tcruzi_pde_promoted_top4_packet_ready"] is True
    assert summary["broad_screen_tcruzi_pde_rescue_only_branch_summary_ready"] is True
    assert summary["selected_rescue_branch_operator_packet_ready"] is True
    assert summary["selected_rescue_branch_surface_label"] == "pde_rescue_only_branch"
    assert summary["selected_rescue_branch_next_required_step"].startswith(
        "Operate T. cruzi PDE through the dedicated rescue-only branch"
    )
    assert summary["selected_allatom_focus_available"] is True
    assert summary["selected_allatom_target_id"] == "Cathepsin K"
    assert summary["selected_allatom_surface_label"] == "cathepsin_k_allatom_review_packet"
    assert summary["selected_allatom_operator_review_ready_reported"] is True
    assert summary["selected_allatom_operator_review_ready"] is True
    assert summary["selected_allatom_wetlab_gate_reported"] is True
    assert summary["selected_allatom_wetlab_gate_pass"] is False
    assert summary["selected_allatom_final_gate_reported"] is True
    assert summary["selected_allatom_final_gate_pass"] is False
    assert summary["selected_allatom_final_wetlab_ready"] is False
    assert summary["selected_allatom_claim_gate_available_reported"] is True
    assert summary["selected_allatom_claim_gate_available"] is True
    assert summary["selected_allatom_claim_ready_for_allatom_reported"] is True
    assert summary["selected_allatom_claim_ready_for_allatom"] is False
    assert summary["selected_allatom_readiness_semantics"] == "explicit_split_gate_fields"
    assert summary["selected_allatom_actionability_status"] == "semi_hard_blocked"
    assert summary["selected_allatom_actionability_claim_requirement_mode"] == "semi_hard"
    assert summary["selected_allatom_actionability_claim_requirement_status"] == "blocked"
    assert "resolve_claim_equivalence_gate" in summary["selected_allatom_actionability_action_list_text"]
    assert summary["selected_allatom_best_compound_name_human_readable"] == "Cathepsin Lead"
    assert summary["selected_allatom_best_compound_name_resolution"] == "human_readable"
    assert "Actionability:" in summary["selected_allatom_human_summary"]
    actionability_row = next(row for row in payload["rows"] if row["surface"] == "broad_screen_selected_allatom_actionability")
    assert actionability_row["status"] == "semi_hard_blocked"
    assert "resolve_claim_equivalence_gate" in actionability_row["one_line_summary"]
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


def test_build_wetlab_master_handoff_dashboard_prefers_current_results_claim_status_over_stale_retry(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    empty = {"summary": {}}

    payload = mod.build_payload(
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        broad_screen_retry_handoff_summary={
            "summary": {
                "status": "wetlab_retry_handoff_summary_ready",
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_surface_label": "tcruzi_pde_allatom_review_packet",
                "selected_allatom_claim_gate_available": False,
                "selected_allatom_claim_ready_for_allatom": False,
            }
        },
        broad_screen_current_results_index={
            "summary": {
                "status": "wetlab_current_results_index_ready",
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_surface_label": "tcruzi_pde_allatom_review_packet",
                "selected_allatom_claim_gate_available_reported": True,
                "selected_allatom_claim_gate_available": True,
                "selected_allatom_claim_ready_for_allatom_reported": True,
                "selected_allatom_claim_ready_for_allatom": False,
            }
        },
    )

    summary = payload["summary"]
    assert summary["selected_allatom_claim_gate_available_reported"] is True
    assert summary["selected_allatom_claim_gate_available"] is True
    assert summary["selected_allatom_claim_ready_for_allatom_reported"] is True
    assert summary["selected_allatom_claim_ready_for_allatom"] is False


def test_build_wetlab_master_handoff_dashboard_prefers_selected_allatom_canonical_resolver(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    def fake_resolver(**_: object) -> dict[str, object]:
        return {
            "raw_claim_requirement_mode": "semi_hard",
            "raw_claim_required_for_final_wetlab": True,
            "raw_claim_required_for_commercial_readiness": True,
            "raw_claim_requirement_reason": "canonical raw claim reason",
            "effective_actionability_status": "hard_blocked",
            "effective_actionability_claim_requirement_mode": "not_applicable",
            "effective_actionability_claim_requirement_status": "not_applicable",
            "effective_actionability_claim_requirement_reason": "canonical effective reason",
            "effective_blocking_order": "hard_block_first",
            "effective_primary_blocking_domain": "translation_gate_v2",
            "action_recipe_codes": ["recompute_mean_min_distance_A", "produce_claim_equivalence_packet"],
            "action_recipe_rows": [
                {
                    "code": "recompute_mean_min_distance_A",
                    "priority": "hard",
                    "blocking_domain": "translation_gate_v2",
                    "next_calculation": "re-minimize pose then rerun short replicated MD",
                    "reason": "canonical geometry repair",
                }
            ],
            "action_recipe_rollup_text": "hard:recompute_mean_min_distance_A -> re-minimize pose then rerun short replicated MD",
            "hybrid_policy": "canonical_test_policy",
        }

    monkeypatch.setattr(mod, "resolve_selected_allatom_canonical", fake_resolver)

    empty = {"summary": {}}
    payload = mod.build_payload(
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        broad_screen_retry_handoff_summary={
            "summary": {
                "status": "wetlab_retry_handoff_summary_ready",
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_surface_label": "synthetic_missing_selected_allatom_review_packet",
                "selected_allatom_packet_ready_for_operator_review": True,
                "selected_allatom_wetlab_final_gate_pass": False,
                "selected_allatom_claim_gate_available": False,
                "selected_allatom_claim_ready_for_allatom": False,
                "selected_allatom_next_required_step": "translation_gate=fail shortlist_tier=defer recommended_next_expensive_lane=defer_expensive_lane",
            }
        },
    )

    summary = payload["summary"]
    assert summary["selected_allatom_raw_claim_requirement_mode"] == "semi_hard"
    assert summary["selected_allatom_effective_actionability_status"] == "hard_blocked"
    assert summary["selected_allatom_effective_blocking_order"] == "hard_block_first"
    assert summary["selected_allatom_effective_primary_blocking_domain"] == "translation_gate_v2"
    assert summary["selected_allatom_action_recipe_codes"] == [
        "recompute_mean_min_distance_A",
        "produce_claim_equivalence_packet",
    ]
    assert summary["selected_allatom_action_recipe_rollup_text"].startswith(
        "hard:recompute_mean_min_distance_A"
    )


def test_build_wetlab_master_handoff_dashboard_prefers_dengue_queue_source_priority(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    empty = {"summary": {}}
    dengue_execution_queue = {
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
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        broad_screen_execution_queue=dengue_execution_queue,
        broad_screen_dengue_stage6_tuning_surface=dengue_tuning_surface,
        broad_screen_dengue_exploratory_retry_lane=dengue_exploratory_retry_lane,
    )
    summary = payload["summary"]
    assert summary["broad_screen_dengue_stage6_retry_source_priority"] == "execution_queue"
    assert summary["broad_screen_dengue_stage6_retry_target_id"] == "Dengue NS2B-NS3 protease"
    assert summary["broad_screen_dengue_stage6_retry_shard_id"] == "17_of_20"
    assert summary["broad_screen_dengue_stage6_retry_next_required_step"] == "Continue or complete Dengue NS2B-NS3 protease shard 17_of_20 through the broad-screen runtime runner."
    assert summary["broad_screen_first_actionable_target_id"] == "Dengue NS2B-NS3 protease"
    assert summary["broad_screen_first_actionable_shard_id"] == "17_of_20"
    assert summary["next_required_step"].startswith("Continue or complete Dengue NS2B-NS3 protease shard 17_of_20")
