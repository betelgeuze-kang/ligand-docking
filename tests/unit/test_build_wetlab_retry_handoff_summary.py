from __future__ import annotations

import json
from pathlib import Path

from tools import build_wetlab_tcruzi_pde_promoted_top4_review_packet as pde_promoted_top4_packet_mod
from tools import build_wetlab_tcruzi_pde_rescue_only_branch_summary as pde_rescue_only_branch_summary_mod
from tools import build_wetlab_tcruzi_pde_rescue_operator_packet as pde_rescue_operator_packet_mod
from tools.wetlab import build_wetlab_retry_handoff_summary as mod

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
    assert all(
        action in packet_summary["commercial_primary_upgrade_actions_v1"]
        for action in expected_primary_upgrade_actions
    )


def test_build_wetlab_retry_handoff_summary_prioritizes_guard_then_retry_modes() -> None:
    hold_guard = {
        "summary": {
            "status": "wetlab_primary_hold_guard_surface_ready",
            "guard_limit": 3,
            "triggered_target_count": 1,
        },
        "rows": [
            {
                "target_id": "SARS-CoV-2 PLpro",
                "total_auto_hold_count": 15,
                "recent_consecutive_auto_hold_streak": 15,
                "guard_limit": 3,
                "guard_triggered_now": True,
                "last_auto_hold_shard_id": "15_of_20",
                "recommended_policy_action": "pause_target_autostart_and_review_retry_preset",
            }
        ],
    }
    retry_preset = {
        "summary": {
            "status": "wetlab_primary_retry_preset_surface_ready",
            "guard_blocked_target_count": 3,
        },
        "rows": [
            {
                "target_id": "ALK2",
                "stage1_mapping_failed_count": 0,
                "stage6_distance_gate_failed_count": 20,
                "consecutive_auto_hold_guard_recommendation": "guard_stop_target_now_20_ge_3",
                "recommended_retry_mode": "do_not_autoadvance",
                "target_specific_next_step": "Keep auto-advance disabled for ALK2; review 06_of_20 and only reopen the lane after a manual retry plan replaces the current 3-hold guard.",
            },
            {
                "target_id": "SARS-CoV-2 Mpro",
                "stage1_mapping_failed_count": 1,
                "stage6_distance_gate_failed_count": 19,
                "consecutive_auto_hold_guard_recommendation": "guard_stop_target_now_20_ge_3",
                "recommended_retry_mode": "mapping_fix_required",
                "target_specific_next_step": "Repair stage1 ligand mapping for SARS-CoV-2 Mpro and rerun 01_of_20 with mapping diagnostics enabled before any further auto-start.",
            },
            {
                "target_id": "T. cruzi PDE",
                "stage1_mapping_failed_count": 1,
                "stage6_distance_gate_failed_count": 19,
                "consecutive_auto_hold_guard_recommendation": "guard_stop_target_now_20_ge_3",
                "recommended_retry_mode": "mapping_fix_required",
                "target_specific_next_step": "Repair stage1 ligand mapping for T. cruzi PDE and rerun 07_of_20 with mapping diagnostics enabled before any further auto-start.",
            },
        ],
    }
    current_results_index = {
        "summary": {
            "status": "wetlab_current_results_index_ready",
            "group_count": 8,
            "surface_count": 18,
            "next_required_step": "Run the SARS-CoV-2 PLpro tuned gate55 manual retry runner for 17_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
        }
    }
    stk17b_manual_retry_lane = {
        "summary": {
            "status": "wetlab_stk17b_manual_retry_lane_ready",
            "target_id": "STK17B (DRAK2)",
            "shard_id": "05_of_20",
            "selected_command_kind": "throughput_preflight",
            "ready_for_manual_retry": True,
            "next_required_step": "Run the STK17B (DRAK2) manual retry runner for 05_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
        }
    }
    plpro_manual_retry_lane = {
        "summary": {
            "status": "wetlab_plpro_manual_retry_lane_ready",
            "target_id": "SARS-CoV-2 PLpro",
            "shard_id": "17_of_20",
            "selected_command_kind": "throughput_preflight_tuned_gate55",
            "ready_for_manual_retry": True,
            "next_required_step": "Run the PLpro manual retry runner for 17_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
        }
    }
    monitor_semantics = {
        "summary": {
            "status": "wetlab_monitor_semantics_ready",
            "guard_active": True,
            "guard_blocked_target_id": "SARS-CoV-2 PLpro",
            "guard_hold_streak": 3,
        }
    }
    lbdhodh_gate51_validation_review_surface = {
        "summary": {
            "status": "wetlab_lbdhodh_gate51_validation_review_surface_ready",
            "target_id": "Leishmania braziliensis DHODH",
            "gate51_validated": True,
            "decision": "promote_gate51_validated_keep_default_closed",
            "validated_command_kind": "throughput_preflight_tuned_gate51",
            "validated_threshold_A": 5.1,
            "gate51_validation_success_count": 12,
            "gate51_validation_row_count": 12,
            "next_required_step": "Promote DHODH gate5.1 as validated, keep the default lane closed, and reserve any future DHODH reopen for an explicit new review.",
        }
    }
    dpre1_branch_review_surface = {
        "summary": {
            "status": "wetlab_dpre1_branch_review_surface_ready",
            "target_id": "DprE1",
            "branch_label": "dpre1_guarded_review_branch",
            "exploratory_retry_next_required_step": "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying.",
            "next_required_step": "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying.",
        }
    }

    payload = mod.build_payload(
        hold_guard,
        retry_preset,
        current_results_index,
        monitor_semantics,
        dpre1_branch_review_surface_payload=dpre1_branch_review_surface,
        lbdhodh_gate51_validation_review_surface_payload=lbdhodh_gate51_validation_review_surface,
        stk17b_manual_retry_lane_payload=stk17b_manual_retry_lane,
        plpro_manual_retry_lane_payload=plpro_manual_retry_lane,
    )
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_retry_handoff_summary_ready"
    assert summary["source_surface_count"] == 4
    assert summary["current_results_group_count"] == 8
    assert summary["current_results_surface_count"] == 18
    assert summary["guard_active"] is True
    assert summary["guard_blocked_target_id"] == "SARS-CoV-2 PLpro"
    assert summary["guard_hold_streak"] == 3
    assert summary["guard_limit"] == 3
    assert summary["manual_retry_decision_count"] == 4
    assert summary["pause_candidate_count"] == 1
    assert summary["mapping_fix_candidate_count"] == 2
    assert summary["do_not_autoadvance_candidate_count"] == 1
    assert summary["manual_retry_priority_targets"] == "SARS-CoV-2 PLpro -> SARS-CoV-2 Mpro -> T. cruzi PDE -> ALK2"
    assert summary["manual_retry_focus_target_id"] == "SARS-CoV-2 PLpro"
    assert summary["manual_retry_focus_decision"] == "pause_auto_start"
    assert summary["stk17b_manual_retry_target_id"] == "STK17B (DRAK2)"
    assert summary["stk17b_manual_retry_shard_id"] == "05_of_20"
    assert summary["stk17b_manual_retry_selected_command_kind"] == "throughput_preflight"
    assert summary["plpro_manual_retry_target_id"] == "SARS-CoV-2 PLpro"
    assert summary["plpro_manual_retry_shard_id"] == "17_of_20"
    assert summary["plpro_manual_retry_selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert summary["lbdhodh_gate51_validated"] is True
    assert summary["selected_validated_target_id"] == "Leishmania braziliensis DHODH"
    assert summary["selected_validated_surface_label"] == "gate5.1_validation_review"
    assert summary["selected_validated_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["selected_validated_threshold_A"] == 5.1
    assert summary["dpre1_branch_review_ready"] is True
    assert summary["dpre1_branch_review_next_required_step"] == "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying."
    assert summary["selected_manual_retry_target_id"] == "SARS-CoV-2 PLpro"
    assert summary["selected_manual_retry_shard_id"] == "17_of_20"
    assert summary["selected_manual_retry_selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert summary["current_results_next_required_step"] == "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying."
    assert summary["next_required_step"] == "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying."

    assert [row["target_id"] for row in rows] == [
        "SARS-CoV-2 PLpro",
        "SARS-CoV-2 Mpro",
        "T. cruzi PDE",
        "ALK2",
    ]
    assert rows[0]["decision"] == "pause_auto_start"
    assert rows[1]["decision"] == "mapping_fix_required"
    assert rows[2]["decision"] == "mapping_fix_required"
    assert rows[3]["decision"] == "do_not_autoadvance"
    assert rows[1]["source_surface"] == "retry_preset_surface"
    assert rows[0]["source_surface"] == "hold_guard_surface"


def test_build_wetlab_retry_handoff_summary_prefers_krs1_guarded_branch_when_index_exposes_it() -> None:
    krs1_next_step = "Keep the T. cruzi KRS1 default lane paused and refresh the stage6 tuning surface before retrying."

    hold_guard = {"summary": {"status": "wetlab_primary_hold_guard_surface_ready", "guard_limit": 3}, "rows": []}
    retry_preset = {"summary": {"status": "wetlab_primary_retry_preset_surface_ready"}, "rows": []}
    current_results_index = {
        "summary": {
            "status": "wetlab_current_results_index_ready",
            "group_count": 9,
            "surface_count": 19,
            "selected_krs1_branch_review_next_required_step": krs1_next_step,
            "next_required_step": "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying.",
        }
    }
    monitor_semantics = {
        "summary": {
            "status": "wetlab_monitor_semantics_ready",
            "guard_active": True,
            "guard_blocked_target_id": "T. cruzi KRS1",
            "guard_hold_streak": 3,
        }
    }
    dpre1_branch_review_surface = {
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
    }
    krs1_branch_review_surface = {
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
    }

    payload = mod.build_payload(
        hold_guard,
        retry_preset,
        current_results_index,
        monitor_semantics,
        dpre1_branch_review_surface_payload=dpre1_branch_review_surface,
        tcruzi_krs1_branch_review_surface_payload=krs1_branch_review_surface,
    )

    summary = payload["summary"]
    assert summary["source_surface_count"] == 5
    assert summary["krs1_branch_review_ready"] is True
    assert summary["krs1_branch_review_target_id"] == "T. cruzi KRS1"
    assert summary["krs1_branch_review_branch_label"] == "tcruzi_krs1_guarded_gate51_branch"
    assert summary["selected_krs1_branch_review_target_id"] == "T. cruzi KRS1"
    assert summary["selected_krs1_branch_review_surface_label"] == "krs1_branch_review_surface"
    assert summary["selected_krs1_branch_review_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["selected_krs1_branch_review_selected_threshold_A"] == 5.1
    assert summary["current_results_next_required_step"] == krs1_next_step
    assert summary["next_required_step"] == krs1_next_step
    assert summary["dpre1_branch_review_next_required_step"] == "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying."


def test_build_wetlab_retry_handoff_summary_selects_stk17b_exploratory_lane_and_dedupes_targets() -> None:
    hold_guard = {
        "summary": {
            "status": "wetlab_primary_hold_guard_surface_ready",
            "guard_limit": 3,
            "triggered_target_count": 1,
        },
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "total_auto_hold_count": 4,
                "recent_consecutive_auto_hold_streak": 3,
                "guard_limit": 3,
                "guard_triggered_now": True,
                "last_auto_hold_shard_id": "16_of_20",
                "recommended_policy_action": "pause_target_autostart_and_review_retry_preset",
            }
        ],
    }
    retry_preset = {
        "summary": {
            "status": "wetlab_primary_retry_preset_surface_ready",
            "guard_blocked_target_count": 1,
        },
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "stage1_mapping_failed_count": 0,
                "stage6_distance_gate_failed_count": 14,
                "consecutive_auto_hold_guard_recommendation": "guard_stop_target_now_3_ge_3",
                "recommended_retry_mode": "do_not_autoadvance",
                "target_specific_next_step": "Keep auto-advance disabled for STK17B (DRAK2); review 16_of_20 and only reopen the lane after an exploratory retry lane is reviewed.",
            },
            {
                "target_id": "SARS-CoV-2 Mpro",
                "stage1_mapping_failed_count": 1,
                "stage6_distance_gate_failed_count": 19,
                "consecutive_auto_hold_guard_recommendation": "guard_stop_target_now_20_ge_3",
                "recommended_retry_mode": "mapping_fix_required",
                "target_specific_next_step": "Repair stage1 ligand mapping for SARS-CoV-2 Mpro.",
            },
        ],
    }
    current_results_index = {
        "summary": {
            "status": "wetlab_current_results_index_ready",
            "group_count": 8,
            "surface_count": 19,
            "next_required_step": "Fallback current-results step.",
        }
    }
    stk17b_manual_retry_lane = {
        "summary": {
            "status": "wetlab_stk17b_manual_retry_lane_ready",
            "target_id": "STK17B (DRAK2)",
            "shard_id": "01_of_20",
            "selected_command_kind": "throughput_preflight_tuned_gate55",
            "ready_for_manual_retry": False,
        }
    }
    stk17b_exploratory_retry_lane = {
        "summary": {
            "status": "wetlab_stk17b_exploratory_retry_lane_ready",
            "target_id": "STK17B (DRAK2)",
            "shard_id": "17_of_20",
            "selected_command_kind": "throughput_preflight_tuned_gate45",
            "ready_for_manual_retry": True,
        }
    }
    stk17b_exploratory_followup_lane = {
        "summary": {
            "status": "wetlab_stk17b_exploratory_followup_lane_ready",
            "target_id": "STK17B (DRAK2)",
            "shard_id": "18_of_20",
            "selected_command_kind": "throughput_preflight_tuned_gate45",
            "followup_lane_label": "exploratory_gate4.5_followup",
            "ready_for_manual_retry": True,
            "next_required_step": "Run the STK17B (DRAK2) exploratory gate4.5 follow-up runner for 18_of_20; keep auto-start hard-frozen after the gate4.5 success and review shards 18-20 separately before reopening.",
        }
    }
    plpro_manual_retry_lane = {
        "summary": {
            "status": "wetlab_plpro_manual_retry_lane_ready",
            "target_id": "SARS-CoV-2 PLpro",
            "shard_id": "17_of_20",
            "selected_command_kind": "throughput_preflight_tuned_gate55",
            "ready_for_manual_retry": True,
        }
    }
    monitor_semantics = {
        "summary": {
            "status": "wetlab_monitor_semantics_ready",
            "guard_active": True,
            "guard_blocked_target_id": "STK17B (DRAK2)",
            "guard_hold_streak": 3,
        }
    }

    payload = mod.build_payload(
        hold_guard,
        retry_preset,
        current_results_index,
        monitor_semantics,
        stk17b_manual_retry_lane_payload=stk17b_manual_retry_lane,
        stk17b_exploratory_retry_lane_payload=stk17b_exploratory_retry_lane,
        stk17b_exploratory_followup_lane_payload=stk17b_exploratory_followup_lane,
        plpro_manual_retry_lane_payload=plpro_manual_retry_lane,
    )
    summary = payload["summary"]

    assert summary["manual_retry_priority_targets"] == "STK17B (DRAK2) -> SARS-CoV-2 Mpro"
    assert summary["selected_manual_retry_target_id"] == "STK17B (DRAK2)"
    assert summary["selected_manual_retry_shard_id"] == "18_of_20"
    assert summary["selected_manual_retry_selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["selected_manual_retry_lane_label"] == "exploratory_gate4.5_followup"


def test_build_wetlab_retry_handoff_summary_keeps_blocked_followup_as_actionable_soft_surface() -> None:
    hold_guard = {"summary": {"status": "wetlab_primary_hold_guard_surface_ready", "guard_limit": 3, "triggered_target_count": 1}, "rows": []}
    retry_preset = {"summary": {"status": "wetlab_primary_retry_preset_surface_ready", "guard_blocked_target_count": 1}, "rows": []}
    current_results_index = {"summary": {"status": "wetlab_current_results_index_ready", "group_count": 8, "surface_count": 19, "next_required_step": "Fallback current-results step."}}
    monitor_semantics = {
        "summary": {
            "status": "wetlab_monitor_semantics_ready",
            "guard_active": True,
            "guard_blocked_target_id": "Leishmania braziliensis DHODH",
            "guard_hold_streak": 3,
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
            "selected_command_kind": "throughput_preflight_tuned_gate55",
            "ready_for_manual_retry": True,
            "next_required_step": "Run the PLpro manual retry runner for 17_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
        }
    }

    payload = mod.build_payload(
        hold_guard,
        retry_preset,
        current_results_index,
        monitor_semantics,
        stk17b_exploratory_followup_lane_payload=stk17b_exploratory_followup_lane,
        plpro_manual_retry_lane_payload=plpro_manual_retry_lane,
    )
    summary = payload["summary"]
    assert summary["selected_manual_retry_target_id"] == "STK17B (DRAK2)"
    assert summary["selected_manual_retry_lane_label"] == "exploratory_gate4.5_followup"
    assert summary["stk17b_exploratory_followup_shard_id"] == "18_of_20;19_of_20;20_of_20"
    assert summary["selected_manual_retry_shard_id"] == "18_of_20;19_of_20;20_of_20"
    assert summary["current_results_next_required_step"].startswith("Keep auto-start hard-frozen and review completed follow-up shards 18_of_20;19_of_20;20_of_20")
    assert summary["next_required_step"].startswith("Keep auto-start hard-frozen and review completed follow-up shards 18_of_20;19_of_20;20_of_20")
    assert summary["selected_manual_retry_ready_for_manual_retry"] is False


def test_build_wetlab_retry_handoff_summary_builds_tcruzi_pde_promoted_top4_packet_and_rescue_only_branch_summary() -> None:
    rescue_review_surface = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_review_surface_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "surface_label": "pde_rescue_review",
            "rescue_only_review": True,
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": True,
            "decision": "promote_rescue_only_branch_keep_default_closed",
            "decision_rationale": "The PDE hard-target rescue lane produced 1 top-8 3-bead candidate(s) at or below 2.5A and 3 additional candidate(s) within the 3.0A near band, so the default broad-screen lane should stay closed and PDE should move forward only through the rescue branch.",
            "strict_threshold_A": 2.5,
            "near_threshold_A": 3.0,
            "source_candidate_count": 32,
            "slice_candidate_count": 8,
            "promoted_candidate_count": 4,
            "under_2p5_candidate_count": 1,
            "near_candidate_count": 3,
            "promoted_ligand_ids": "t_cruzi_pde_20_of_20_095609;t_cruzi_pde_20_of_20_095204;t_cruzi_pde_20_of_20_095202;t_cruzi_pde_20_of_20_095028",
            "best_ligand_id": "t_cruzi_pde_20_of_20_095609",
            "best_mean_min_distance_A": 0.6724306486050288,
            "best_binding_energy_proxy": 0.11340234672349846,
            "best_stability_score": 0.4936000403063831,
            "promoted_metric_name": "mean_min_distance_A",
            "promoted_metric_min_A": 0.6724306486050288,
            "promoted_metric_median_A": 2.775,
            "promoted_metric_mean_A": 2.284,
            "promoted_metric_max_A": 2.9151266292730966,
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.5,
            "rescue_branch_kind": "three_bead_rescue_branch_only",
            "rescue_anchor_artifact_count": 3,
            "rescue_only": True,
            "next_required_step": "Operate T. cruzi PDE as a rescue-only branch, keep the default lane closed, and review the promoted top-8 3-bead rescue subset (1 at or below 2.5A; 3 additional within 3.0A).",
        },
        "rows": [
            {
                "ligand_id": "t_cruzi_pde_20_of_20_095609",
                "mean_min_distance_A": 0.6724306486050288,
                "binding_energy_proxy": 0.11340234672349846,
                "stability_score": 0.4936000403063831,
                "contact_fraction": 0.5288888888888889,
                "trajectory_frames": 300,
                "queue_id": "T_cruzi_PDE__rep0608__t_cruzi_pde_20_of_20_095609",
                "ligand_model": "3bead_implicit_hbond",
                "rescue_review_band": "strict_under_2p5A",
            },
            {
                "ligand_id": "t_cruzi_pde_20_of_20_095204",
                "mean_min_distance_A": 2.7564589381217957,
                "binding_energy_proxy": -0.08691659728888865,
                "stability_score": 0.31872994338483907,
                "contact_fraction": 0.6711111111111111,
                "trajectory_frames": 300,
                "queue_id": "T_cruzi_PDE__rep0203__t_cruzi_pde_20_of_20_095204",
                "ligand_model": "3bead_implicit_hbond",
                "rescue_review_band": "near_under_3p0A",
            },
            {
                "ligand_id": "t_cruzi_pde_20_of_20_095202",
                "mean_min_distance_A": 2.7927404389778774,
                "binding_energy_proxy": -0.1364531274916764,
                "stability_score": 0.32253720343699893,
                "contact_fraction": 0.6311111111111112,
                "trajectory_frames": 300,
                "queue_id": "T_cruzi_PDE__rep0201__t_cruzi_pde_20_of_20_095202",
                "ligand_model": "3bead_implicit_hbond",
                "rescue_review_band": "near_under_3p0A",
            },
            {
                "ligand_id": "t_cruzi_pde_20_of_20_095028",
                "mean_min_distance_A": 2.9151266292730966,
                "binding_energy_proxy": -0.1451422188662038,
                "stability_score": 0.3194753203834841,
                "contact_fraction": 0.6144444444444443,
                "trajectory_frames": 300,
                "queue_id": "T_cruzi_PDE__rep0027__t_cruzi_pde_20_of_20_095028",
                "ligand_model": "3bead_implicit_hbond",
                "rescue_review_band": "near_under_3p0A",
            },
        ],
    }
    three_bead_slice = {
        "summary": {
            "status": "wetlab_rescue_three_bead_slice_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.5,
            "slice_candidate_count": 8,
            "execution_mode": "local_refine_scoring_executed",
            "scoring_status": "pass",
            "three_bead_scores_csv": "runs/wetlab_rescue_three_bead/t_cruzi_pde/20_of_20/top_8/three_bead_slice_scores.csv",
            "three_bead_summary_json": "runs/wetlab_rescue_three_bead/t_cruzi_pde/20_of_20/top_8/three_bead_slice_summary.json",
        }
    }

    promoted_top4_packet = pde_promoted_top4_packet_mod.build_payload(rescue_review_surface, three_bead_slice)
    packet_summary = promoted_top4_packet["summary"]
    assert packet_summary["status"] == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready"
    assert packet_summary["packet_scope"] == "promoted_top4_three_bead_rescue_review"
    assert packet_summary["packet_ready"] is True
    assert packet_summary["packet_ready_for_operator_review"] is True
    assert packet_summary["wetlab_gate_pass"] is False
    assert packet_summary["wetlab_final_gate_pass"] is False
    assert packet_summary["claim_gate_available"] is False
    assert packet_summary["claim_ready_for_allatom"] is False
    assert packet_summary["rescue_only_branch"] is True
    assert packet_summary["default_lane_reopen_allowed"] is False
    assert packet_summary["branch_to_rescue_only"] is True
    assert packet_summary["selected_command_kind"] == "three_bead_rescue_local_refine"
    assert packet_summary["strict_threshold_A"] == 2.5
    assert packet_summary["near_threshold_A"] == 3.0
    assert packet_summary["source_slice_candidate_count"] == 8
    assert packet_summary["promoted_candidate_count"] == 4
    assert packet_summary["under_2p5_candidate_count"] == 1
    assert packet_summary["near_candidate_count"] == 3
    assert packet_summary["best_ligand_id"] == "t_cruzi_pde_20_of_20_095609"
    assert packet_summary["best_mean_min_distance_A"] == 0.672
    assert packet_summary["best_binding_energy_proxy"] == 0.11340234672349846
    assert packet_summary["best_stability_score"] == 0.4936000403063831
    assert packet_summary["next_required_step"] == "Use this promoted top-4 packet as the PDE rescue-only review unit, keep the default lane closed, and review only these promoted rescue candidates before any reopen decision."
    assert [row["packet_rank"] for row in promoted_top4_packet["rows"]] == [1, 2, 3, 4]
    assert promoted_top4_packet["rows"][0]["review_action"] == "strict_promote_rescue_only_branch"
    assert promoted_top4_packet["rows"][1]["review_action"] == "near_band_manual_review_rescue_only_branch"

    branch_runner = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_only_branch_runner_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "branch_state": "adopted_from_generic_rescue_lane",
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": True,
            "promoted_top4_packet_ready": True,
            "promoted_candidate_count": 4,
            "under_2p5_candidate_count": 1,
            "source_runner_status": "wetlab_hard_target_rescue_runner_ready",
            "source_slice_status": "wetlab_rescue_three_bead_slice_ready",
            "execution_mode": "adopted_from_generic_rescue_lane",
            "scoring_status": "pass",
        }
    }
    branch_summary = pde_rescue_only_branch_summary_mod.build_payload(
        rescue_review_surface,
        promoted_top4_packet,
        branch_runner,
        three_bead_slice,
    )
    branch_summary_summary = branch_summary["summary"]
    assert branch_summary_summary["status"] == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready"
    assert branch_summary_summary["branch_label"] == "tcruzi_pde_rescue_only_branch"
    assert branch_summary_summary["branch_state"] == "promoted_top4_packet_ready_default_lane_closed"
    assert branch_summary_summary["default_lane_reopen_allowed"] is False
    assert branch_summary_summary["branch_to_rescue_only"] is True
    assert branch_summary_summary["selected_command_kind"] == "three_bead_rescue_local_refine"
    assert branch_summary_summary["selected_threshold_A"] == 2.5
    assert branch_summary_summary["promoted_top4_packet_ready"] is True
    assert branch_summary_summary["promoted_candidate_count"] == 4
    assert branch_summary_summary["under_2p5_candidate_count"] == 1
    assert branch_summary_summary["near_candidate_count"] == 3
    assert branch_summary_summary["best_ligand_id"] == "t_cruzi_pde_20_of_20_095609"
    assert branch_summary_summary["best_mean_min_distance_A"] == 0.672
    assert branch_summary_summary["runner_status"] == "wetlab_tcruzi_pde_rescue_only_branch_runner_ready"
    assert branch_summary_summary["three_bead_scoring_status"] == "pass"
    assert branch_summary_summary["execution_mode"] == "adopted_from_generic_rescue_lane"
    assert branch_summary_summary["review_packet_ready_for_operator_review"] is True
    assert branch_summary_summary["review_packet_final_gate_pass"] is False
    assert branch_summary_summary["branch_ready_for_operator_review"] is True
    assert branch_summary_summary["branch_ready_for_final_wetlab"] is False
    assert branch_summary_summary["next_required_step"].startswith(
        "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, and use the promoted top-4 packet as the review unit before any reopen decision."
    )
    assert "operator-review only" in branch_summary_summary["next_required_step"]
    assert [row["step_id"] for row in branch_summary["rows"]] == [
        "rescue_review_surface",
        "promoted_top4_review_packet",
        "rescue_only_branch_runner",
        "three_bead_slice",
    ]


def test_build_wetlab_retry_handoff_summary_uses_pde_operator_packet_when_branch_summary_missing() -> None:
    rescue_review_surface = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_review_surface_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "decision": "promote_rescue_only_branch_keep_default_closed",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "strict_threshold_A": 2.5,
            "near_threshold_A": 3.0,
            "promoted_candidate_count": 4,
            "under_2p5_candidate_count": 1,
            "near_candidate_count": 3,
            "next_required_step": "Fallback rescue review step.",
        },
        "rows": [
            {
                "ligand_id": "ligand_strict",
                "rescue_review_band": "strict_under_2p5A",
                "mean_min_distance_A": 0.6724,
                "binding_energy_proxy": -9.1,
                "stability_score": 0.88,
                "contact_fraction": 0.81,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q1",
            },
            {
                "ligand_id": "ligand_near_1",
                "rescue_review_band": "near_under_3p0A",
                "mean_min_distance_A": 2.7565,
                "binding_energy_proxy": -8.4,
                "stability_score": 0.74,
                "contact_fraction": 0.67,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q2",
            },
        ],
    }
    three_bead_slice = {
        "summary": {
            "status": "wetlab_rescue_three_bead_slice_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.5,
            "slice_candidate_count": 8,
        }
    }
    promoted_top4_packet = pde_promoted_top4_packet_mod.build_payload(rescue_review_surface, three_bead_slice)
    promoted_top4_packet["summary"].pop("packet_ready_for_operator_review", None)
    rescue_operator_packet = pde_rescue_operator_packet_mod.build_payload(promoted_top4_packet)
    cathepsin_k_allatom_review_packet = {
        "summary": {
            "status": "wetlab_cathepsin_k_allatom_review_packet_ready",
            "target_id": "Cathepsin K",
            "surface_label": "cathepsin_k_allatom_review_packet",
            "packet_scope": "selected_allatom_review_packet",
            "selected_command_kind": "allatom_refinement",
            "selected_threshold_A": 2.5,
            "best_compound_name": "Cathepsin Lead",
            "best_compound_name_human_readable": "Cathepsin Lead",
            "best_compound_name_resolution": "human_readable",
            "best_mean_min_distance_A": 1.234,
            "promoted_candidate_count": 4,
            "under_2p5_candidate_count": 1,
            "near_candidate_count": 3,
            "commercial_schema_version": "wetlab_commercial_grade_v1",
            "commercial_hard_gate_pass_v1": False,
            "commercial_soft_score_v1": 43.0,
            "commercial_confidence_score_v1": 49.5,
            "commercial_overall_score_v1": 44.6,
            "commercial_risk_bucket_v1": "critical",
            "commercial_decision_class_v1": "commercial_recycle_or_rework",
            "commercial_primary_upgrade_actions_v1": (
                "tighten_pose_geometry_under_strict_gate",
                "raise_trajectory_stability",
                "increase_trajectory_support",
            ),
            "next_required_step": "Review Cathepsin K selected all-atom packet before any wetlab decision.",
        }
    }

    payload = mod.build_payload(
        {},
        {},
        {},
        {},
        tcruzi_pde_rescue_review_surface_payload=rescue_review_surface,
        tcruzi_pde_promoted_top4_review_packet_payload=promoted_top4_packet,
        tcruzi_pde_rescue_operator_packet_payload=rescue_operator_packet,
        cathepsin_k_allatom_review_packet_payload=cathepsin_k_allatom_review_packet,
    )

    summary = payload["summary"]
    assert summary["tcruzi_pde_rescue_operator_packet_ready"] is True
    assert summary["tcruzi_pde_rescue_operator_packet_wetlab_final_gate_pass"] is False
    assert summary["selected_rescue_branch_operator_packet_ready"] is True
    assert summary["selected_rescue_branch_operator_packet_wetlab_final_gate_pass"] is False
    assert summary["selected_rescue_branch_wetlab_final_gate_pass"] is False
    assert summary["selected_rescue_branch_operator_packet_scope"] == "partner_operator_rescue_only_review"
    assert summary["tcruzi_pde_rescue_operator_packet_next_required_step"] == rescue_operator_packet["summary"]["next_required_step"]
    assert summary["selected_rescue_branch_operator_packet_next_required_step"] == rescue_operator_packet["summary"]["next_required_step"]
    assert rescue_operator_packet["summary"]["packet_ready_source"] == "review_packet.packet_ready"
    assert rescue_operator_packet["summary"]["wetlab_final_gate_pass"] is False
    assert rescue_operator_packet["summary"]["wetlab_final_gate_source"] == "review_packet.wetlab_final_gate_pass"
    assert rescue_operator_packet["summary"]["wetlab_final_gate_legacy_fallback"] is False
    assert summary["selected_allatom_target_id"] == "Cathepsin K"
    assert summary["selected_allatom_surface_label"] == "cathepsin_k_allatom_review_packet"
    assert summary["selected_allatom_selected_command_kind"] == "allatom_refinement"
    assert summary["selected_allatom_selected_threshold_A"] == 2.5
    assert summary["selected_allatom_packet_scope"] == "selected_allatom_review_packet"
    assert summary["selected_allatom_best_compound_name"] == "Cathepsin Lead"
    assert summary["selected_allatom_best_compound_name_human_readable"] == "Cathepsin Lead"
    assert summary["selected_allatom_best_compound_name_resolution"] == "human_readable"
    assert summary["selected_allatom_best_mean_min_distance_A"] == 1.234
    assert summary["selected_allatom_promoted_candidate_count"] == 4
    assert summary["selected_allatom_under_2p5_candidate_count"] == 1
    assert summary["selected_allatom_near_candidate_count"] == 3
    assert summary["selected_allatom_next_required_step"] == "Review Cathepsin K selected all-atom packet before any wetlab decision."
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
    assert summary["current_results_next_required_step"] == rescue_operator_packet["summary"]["next_required_step"]
    assert summary["next_required_step"] == "Review Cathepsin K selected all-atom packet before any wetlab decision."


def test_build_wetlab_retry_handoff_summary_propagates_pde_selected_allatom_v2_and_translation_shortlist_guidance() -> None:
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

    hold_guard = {"summary": {"status": "wetlab_primary_hold_guard_surface_ready", "guard_limit": 3}, "rows": []}
    retry_preset = {"summary": {"status": "wetlab_primary_retry_preset_surface_ready"}, "rows": []}
    current_results_index = {
        "summary": {
            "status": "wetlab_current_results_index_ready",
            "group_count": 1,
            "surface_count": 1,
            "next_required_step": "Fallback current-results step.",
        }
    }
    monitor_semantics = {
        "summary": {
            "status": "wetlab_monitor_semantics_ready",
            "guard_active": False,
            "guard_blocked_target_id": "",
            "guard_hold_streak": 0,
        }
    }

    payload = mod.build_payload(
        hold_guard,
        retry_preset,
        current_results_index,
        monitor_semantics,
        tcruzi_pde_allatom_review_packet_payload=adjusted_pde_review_packet,
    )

    summary = payload["summary"]
    assert summary["allatom_family_focus_target_id"] == pde_review_summary["target_id"]
    assert summary["allatom_family_focus_surface_label"] == pde_review_summary["surface_label"]
    assert summary["allatom_family_focus_commercial_reported_v1"] is True
    assert summary["allatom_family_focus_commercial_schema_version"] == "wetlab_commercial_grade_v2"
    assert summary["allatom_family_focus_commercial_hard_gate_pass_v1"] is pde_review_summary["commercial_hard_gate_pass_v2"]
    assert summary["allatom_family_focus_commercial_overall_score_v1"] == pde_review_summary["commercial_overall_score_v2"]
    assert summary["allatom_family_focus_commercial_risk_bucket_v1"] == pde_review_summary["commercial_risk_bucket_v2"]
    assert summary["allatom_family_focus_commercial_decision_class_v1"] == pde_review_summary["commercial_decision_class_v2"]
    assert summary["allatom_family_focus_commercial_primary_upgrade_actions_v1"] == pde_review_summary[
        "commercial_primary_upgrade_actions_v2"
    ]
    assert summary["allatom_family_focus_commercial_primary_upgrade_actions_text_v1"] == pde_review_summary[
        "commercial_action_rollup_v2"
    ]
    assert summary["selected_allatom_commercial_schema_version"] == "wetlab_commercial_grade_v2"
    assert summary["selected_allatom_commercial_hard_gate_pass_v1"] is pde_review_summary["commercial_hard_gate_pass_v2"]
    assert summary["selected_allatom_commercial_overall_score_v1"] == pde_review_summary["commercial_overall_score_v2"]
    assert summary["selected_allatom_commercial_risk_bucket_v1"] == pde_review_summary["commercial_risk_bucket_v2"]
    assert summary["selected_allatom_commercial_decision_class_v1"] == pde_review_summary["commercial_decision_class_v2"]
    assert summary["selected_allatom_commercial_primary_upgrade_actions_v1"] == pde_review_summary[
        "commercial_primary_upgrade_actions_v2"
    ]
    assert summary["selected_allatom_commercial_primary_upgrade_actions_text_v1"] == pde_review_summary[
        "commercial_action_rollup_v2"
    ]
    assert summary["selected_allatom_next_required_step"] == translation_shortlist_guidance
    assert summary["current_results_next_required_step"] == translation_shortlist_guidance
