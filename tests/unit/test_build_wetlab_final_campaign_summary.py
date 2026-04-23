from __future__ import annotations

import pytest

from tools import build_wetlab_final_campaign_summary as mod
from tools.wetlab_allatom_refinement_utils import compute_commercial_grade_schema_v1


def test_build_wetlab_final_campaign_summary_rolls_up_chains() -> None:
    terminal_review = {
        "summary": {"campaign_terminal_state": "complete", "chain_count": 4},
        "rows": [
            {"chain_id": "priority3", "chain_rank": 1, "queue_target_count": 3, "resolved_target_count": 3, "all_rows_resolved": True, "terminal_state": "complete"},
            {"chain_id": "wave2", "chain_rank": 4, "queue_target_count": 5, "resolved_target_count": 5, "all_rows_resolved": True, "terminal_state": "complete"},
        ],
    }
    master_queue = {"summary": {"queue_target_count": 13, "resolved_target_count": 13}, "rows": [{"chain_id": "priority3", "target_id": "SARS-CoV-2 Mpro"}, {"chain_id": "wave2", "target_id": "LRRK2"}]}
    export_bundle = {"summary": {"track_count": 5, "ready_to_send_count": 5}}
    outbound_board = {"summary": {"target_count": 13}, "rows": [{"target_id": "T. cruzi PDE"}, {"target_id": "CA IX"}]}
    portfolio = {"summary": {"target_count": 14}}
    blueprint = {"summary": {"wave1_target_count": 8}}
    broad_screen_queue = {
        "summary": {
            "status": "wetlab_broad_screen_queue_ready",
            "library_size": 100000,
            "target_count": 13,
            "total_queue_rows": 260,
        }
    }
    broad_screen_bridge = {
        "summary": {
            "status": "wetlab_broad_screen_bridge_ready",
            "library_size": 100000,
            "final_packet_shape": "top-3 repurposing + top-3 novelty",
        }
    }
    broad_screen_compound_universe = {
        "summary": {
            "status": "wetlab_broad_screen_compound_universe_ready",
            "deduped_compound_count": 158,
            "coverage_gap_to_target_size": 99842,
        }
    }
    broad_screen_execution_queue = {
        "summary": {
            "status": "wetlab_broad_screen_execution_queue_ready",
            "ready_now_row_count": 1,
            "first_actionable_target_id": "CA IX",
            "first_actionable_shard_id": "01_of_20",
        }
    }
    broad_screen_autofill = {
        "summary": {
            "status": "wetlab_broad_screen_repurposing_autofill_ready",
            "override_target_count": 0,
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
    broad_screen_dpre1_branch_review_surface = {
        "summary": {
            "status": "wetlab_dpre1_branch_review_surface_ready",
            "target_id": "DprE1",
            "branch_label": "dpre1_guarded_review_branch",
            "exploratory_retry_next_required_step": "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying.",
            "next_required_step": "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying.",
        }
    }
    broad_screen_target_retry_policy_templates = {
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
    broad_screen_tcruzi_pde_rescue_only_branch_summary = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_only_branch_summary_ready",
            "next_required_step": "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, and use the promoted top-4 packet as the review unit before any reopen decision.",
        }
    }
    broad_screen_tcruzi_pde_rescue_operator_packet = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_operator_packet_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "packet_scope": "partner_operator_rescue_only_review",
            "operator_packet_ready": True,
            "wetlab_final_gate_pass": False,
            "claim_ready_for_allatom": False,
            "next_required_step": "Review the rescue operator packet.",
        }
    }
    broad_screen_retry_handoff_summary = {
        "summary": {
            "status": "wetlab_retry_handoff_summary_ready",
            "selected_rescue_branch_surface_label": "pde_rescue_only_branch",
            "selected_rescue_branch_next_required_step": "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, and use the promoted top-4 packet as the review unit before any reopen decision.",
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
        }
    }

    payload = mod.build_payload(
        terminal_review,
        master_queue,
        export_bundle,
        outbound_board,
        portfolio,
        blueprint,
        broad_screen_queue,
        broad_screen_bridge,
        broad_screen_compound_universe,
        broad_screen_execution_queue,
        broad_screen_autofill,
        broad_screen_lbdhodh_stage6_tuning_surface=broad_screen_lbdhodh_stage6_tuning_surface,
        broad_screen_lbdhodh_exploratory_retry_lane=broad_screen_lbdhodh_exploratory_retry_lane,
        broad_screen_lbdhodh_gate51_validation_review_surface=broad_screen_lbdhodh_gate51_validation_review_surface,
        broad_screen_dpre1_branch_review_surface=broad_screen_dpre1_branch_review_surface,
        broad_screen_target_retry_policy_templates=broad_screen_target_retry_policy_templates,
        broad_screen_mapping_fix_retry_policy_templates=broad_screen_mapping_fix_retry_policy_templates,
        broad_screen_hard_target_rescue_lane=broad_screen_hard_target_rescue_lane,
        broad_screen_rescue_anchor_artifacts=broad_screen_rescue_anchor_artifacts,
        broad_screen_rescue_three_bead_candidates=broad_screen_rescue_three_bead_candidates,
        broad_screen_tcruzi_pde_rescue_only_branch_summary=broad_screen_tcruzi_pde_rescue_only_branch_summary,
        broad_screen_tcruzi_pde_rescue_operator_packet=broad_screen_tcruzi_pde_rescue_operator_packet,
        broad_screen_retry_handoff_summary=broad_screen_retry_handoff_summary,
        broad_screen_selected_allatom_visual_bundle={
            "summary": {
                "status": "selected_allatom_visual_bundle_ready",
                "target_id": "Cathepsin K",
                "assets_dir": "/tmp/cathepsin_visuals",
                "dashboard_html": "/tmp/cathepsin_visuals/dashboard.html",
                "primary_figure_path": "/tmp/cathepsin_visuals/hero.png",
                "primary_movie_script_path": "/tmp/cathepsin_visuals/hero.cxc",
                "primary_movie_mp4_path": "/tmp/cathepsin_visuals/hero.mp4",
                "topk_count": 4,
                "figure_count": 2,
                "movie_plan_count": 4,
                "binding_event_candidate_count": 2,
                "human_summary": "Cathepsin K selected-allatom visuals ready.",
            }
        },
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_final_campaign_summary_ready"
    assert summary["campaign_terminal_state"] == "complete"
    assert summary["serialized_resolved_target_count"] == 13
    assert summary["ready_to_send_track_count"] == 5
    assert summary["broad_screen_queue_ready"] is True
    assert summary["broad_screen_bridge_ready"] is True
    assert summary["broad_screen_library_size"] == 100000
    assert summary["broad_screen_total_queue_rows"] == 260
    assert summary["broad_screen_compound_universe_ready"] is True
    assert summary["broad_screen_ingested_compound_count"] == 158
    assert summary["broad_screen_execution_queue_ready"] is True
    assert summary["broad_screen_first_actionable_target_id"] == "CA IX"
    assert summary["broad_screen_repurposing_autofill_ready"] is True
    assert summary["broad_screen_lbdhodh_stage6_tuning_surface_ready"] is True
    assert summary["broad_screen_lbdhodh_stage6_recommended_threshold_A"] == 5.1
    assert summary["broad_screen_lbdhodh_stage6_immediately_runnable_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["broad_screen_lbdhodh_gate51_validation_review_surface_ready"] is True
    assert summary["broad_screen_lbdhodh_gate51_validated"] is True
    assert summary["broad_screen_lbdhodh_gate51_validation_decision"] == "promote_gate51_validated_keep_default_closed"
    assert summary["broad_screen_lbdhodh_gate51_validation_validated_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["broad_screen_lbdhodh_gate51_validation_validated_threshold_A"] == 5.1
    assert summary["selected_validated_target_id"] == "Leishmania braziliensis DHODH"
    assert summary["selected_validated_surface_label"] == "gate5.1_validation_review"
    assert summary["selected_validated_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["selected_validated_threshold_A"] == 5.1
    assert summary["selected_validated_next_required_step"].startswith("Promote DHODH gate5.1 as validated")
    assert summary["broad_screen_dpre1_branch_review_ready"] is True
    assert summary["broad_screen_dpre1_branch_review_next_required_step"] == "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying."
    assert summary["broad_screen_lbdhodh_retry_lane_ready"] is True
    assert summary["broad_screen_lbdhodh_retry_ready_for_manual_retry"] is True
    assert summary["broad_screen_lbdhodh_retry_target_id"] == "Leishmania braziliensis DHODH"
    assert summary["broad_screen_lbdhodh_retry_shard_id"] == "20_of_20"
    assert summary["broad_screen_lbdhodh_retry_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["broad_screen_target_retry_policy_templates_ready"] is True
    assert summary["broad_screen_target_retry_template_target_count"] == 6
    assert summary["broad_screen_target_retry_empirical_validated_target_count"] == 2
    assert summary["broad_screen_target_retry_focus_target_id"] == "Leishmania braziliensis DHODH"
    assert summary["broad_screen_target_retry_focus_template_label"] == "gate51_branch_only_empirical"
    assert summary["broad_screen_target_retry_focus_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["broad_screen_target_retry_focus_selected_threshold_A"] == 5.1
    assert summary["broad_screen_mapping_fix_retry_policy_templates_ready"] is True
    assert summary["broad_screen_mapping_fix_retry_template_target_count"] == 2
    assert summary["broad_screen_mapping_fix_retry_ready_target_count"] == 2
    assert summary["broad_screen_mapping_fix_retry_focus_target_id"] == "SARS-CoV-2 Mpro"
    assert summary["broad_screen_mapping_fix_retry_focus_template_label"] == "mapping_fix_branch_only"
    assert summary["broad_screen_mapping_fix_retry_focus_selected_command_kind"] == "throughput_preflight"
    assert summary["broad_screen_hard_target_rescue_lane_ready"] is True
    assert summary["broad_screen_hard_target_rescue_lane_target_id"] == "Cathepsin K"
    assert summary["broad_screen_hard_target_rescue_lane_shard_id"] == "05_of_20"
    assert summary["broad_screen_hard_target_rescue_lane_stage1_ok"] is True
    assert summary["broad_screen_hard_target_rescue_lane_stage6_fail"] is True
    assert summary["broad_screen_hard_target_rescue_lane_auto_hold_streak"] == 4
    assert summary["broad_screen_hard_target_rescue_lane_selected_command_kind"] == "hard_target_rescue_lane"
    assert summary["broad_screen_hard_target_rescue_lane_lane_label"] == "hard_target_rescue_lane"
    assert summary["broad_screen_hard_target_rescue_lane_next_required_step"].startswith("Run the hard-target rescue lane for Cathepsin K")
    assert summary["broad_screen_rescue_anchor_artifacts_ready"] is True
    assert summary["broad_screen_rescue_anchor_target_id"] == "Cathepsin K"
    assert summary["broad_screen_rescue_anchor_artifact_count"] == 2
    assert summary["broad_screen_rescue_anchor_rescue_only"] is True
    assert summary["broad_screen_rescue_anchor_native_anchor_artifact"] == "cathepsin_native_anchor.csv"
    assert summary["broad_screen_rescue_anchor_pocket_anchor_artifact"] == "cathepsin_pocket_anchor.csv"
    assert summary["broad_screen_rescue_anchor_next_required_step"].startswith("Review rescue anchors for Cathepsin K")
    assert summary["broad_screen_rescue_three_bead_candidates_ready"] is True
    assert summary["broad_screen_rescue_three_bead_candidate_target_id"] == "T. cruzi PDE"
    assert summary["broad_screen_rescue_three_bead_candidate_count"] == 3
    assert summary["broad_screen_rescue_three_bead_candidate_top_n"] == 3
    assert summary["broad_screen_rescue_three_bead_candidate_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["broad_screen_rescue_three_bead_candidate_selected_threshold_A"] == 5.1
    assert summary["broad_screen_rescue_three_bead_candidate_next_required_step"].startswith("Review 3-bead rescue candidates for T. cruzi PDE")
    assert summary["selected_rescue_branch_surface_label"] == "pde_rescue_only_branch"
    assert summary["selected_rescue_branch_next_required_step"].startswith("Operate T. cruzi PDE through the dedicated rescue-only branch")
    assert summary["selected_rescue_branch_operator_packet_ready"] is True
    assert summary["broad_screen_tcruzi_pde_rescue_operator_packet_ready"] is True
    assert summary["selected_allatom_target_id"] == "Cathepsin K"
    assert summary["selected_allatom_surface_label"] == "cathepsin_k_allatom_review_packet"
    assert summary["selected_allatom_selected_command_kind"] == "allatom_refinement"
    assert summary["selected_allatom_selected_threshold_A"] == 2.5
    assert summary["selected_allatom_packet_scope"] == "selected_allatom_review_packet"
    assert summary["selected_allatom_focus_available"] is True
    assert summary["selected_allatom_focus_label"] == "Cathepsin K / cathepsin_k_allatom_review_packet"
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
    assert summary["selected_allatom_gate_rollup"] == "operator review ready | final gate blocked | claim gate available"
    assert summary["selected_allatom_gate_detail_rollup"] == (
        "wetlab gate blocked | semantics=explicit split-gate fields | "
        "best compound Cathepsin Lead | best mean min distance 1.234A | "
        "candidate bands promoted=4, strict<2.5A=1, near<3.0A=3"
    )
    assert summary["selected_allatom_commercial_schema_version"] == "wetlab_commercial_grade_v1"
    assert summary["selected_allatom_commercial_reported"] is True
    assert summary["selected_allatom_commercial_hard_gate_reported"] is True
    assert summary["selected_allatom_commercial_hard_gate_pass_v1"] is False
    assert summary["selected_allatom_commercial_overall_score_v1"] == 44.6
    assert summary["selected_allatom_commercial_risk_bucket_v1"] == "critical"
    assert summary["selected_allatom_commercial_decision_class_v1"] == "commercial_recycle_or_rework"
    assert summary["selected_allatom_commercial_primary_upgrade_actions_v1"] == [
        "tighten_pose_geometry_under_strict_gate",
        "raise_trajectory_stability",
        "increase_trajectory_support",
    ]
    assert summary["selected_allatom_commercial_rollup"] == "commercial overall 44.6 | risk critical | decision commercial_recycle_or_rework"
    assert summary["selected_allatom_commercial_detail_rollup"] == (
        "commercial hard gate blocked | primary upgrades "
        "tighten_pose_geometry_under_strict_gate, raise_trajectory_stability, increase_trajectory_support"
    )
    assert summary["selected_allatom_commercial_summary"] == (
        "Commercial-grade v1: overall 44.6, risk critical, decision commercial_recycle_or_rework, "
        "primary upgrades tighten_pose_geometry_under_strict_gate, raise_trajectory_stability, increase_trajectory_support."
    )
    assert summary["selected_allatom_visual_bundle_ready"] is True
    assert summary["selected_allatom_visual_target_id"] == "Cathepsin K"
    assert summary["selected_allatom_visual_topk_count"] == 4
    assert summary["selected_allatom_visual_availability_rollup"] == (
        "top-k 4 | figures 2 | movie plans 4 | binding-event candidates 2"
    )
    assert summary["selected_allatom_visual_media_ready_rollup"] == (
        "dashboard ready | figure ready | movie scripts 0/4 | movie mp4 0/4 | binding-event clips 0/2"
    )
    assert summary["selected_allatom_visual_human_summary"] == "Cathepsin K selected-allatom visuals ready."
    assert summary["selected_allatom_human_summary"].startswith(
        "Selected all-atom focus Cathepsin K / cathepsin_k_allatom_review_packet: "
        "operator review ready, final gate blocked, claim gate available."
    )
    assert "Commercial-grade v2 is not yet reported for this focus." in summary["selected_allatom_human_summary"]
    assert "Translation-gate and stronger-physics shortlist signals are not yet reported for this focus." in summary["selected_allatom_human_summary"]
    assert summary["selected_allatom_best_compound_name"] == "Cathepsin Lead"
    assert summary["selected_allatom_best_compound_name_human_readable"] == "Cathepsin Lead"
    assert summary["selected_allatom_best_compound_name_resolution"] == "human_readable"
    assert summary["selected_allatom_best_mean_min_distance_A"] == 1.234
    assert summary["selected_allatom_promoted_candidate_count"] == 4
    assert summary["selected_allatom_under_2p5_candidate_count"] == 1
    assert summary["selected_allatom_near_candidate_count"] == 3
    assert summary["selected_allatom_next_required_step"] == "Review Cathepsin K selected all-atom packet before any wetlab decision."
    assert payload["rows"][0]["chain_id"] == "priority3"
    assert summary["next_required_step"] == "Review Cathepsin K selected all-atom packet before any wetlab decision."


def test_build_wetlab_final_campaign_summary_commercial_grade_schema_v1_scores_selected_allatom() -> None:
    commercial_schema = compute_commercial_grade_schema_v1(
        promoted_rows=[
            {
                "packet_rank": 1,
                "mean_min_distance_A": 3.705,
                "binding_energy_proxy": -0.1682,
                "stability_score": 0.3648,
                "contact_fraction": 0.85,
                "binding_energy_mmpbsa_std": 0.12,
                "trajectory_frames": 220,
            }
        ],
        selected_threshold_A=2.5,
        strict_threshold_A=2.5,
        near_threshold_A=3.0,
        wetlab_gate_summary={
            "strict_candidate_count": 0,
            "near_candidate_count": 2,
            "wetlab_gate_pass": False,
            "packet_ready_for_operator_review": True,
        },
        claim_gate_summary={
            "claim_gate_available": False,
            "claim_ready_for_allatom": False,
        },
        final_gate_summary={
            "wetlab_final_gate_pass": False,
            "wetlab_final_gate_failed_metrics": ["mean_min_distance_A"],
        },
    )
    summary = commercial_schema["summary"]
    row = commercial_schema["rows"][0]

    assert summary["commercial_schema_version"] == "wetlab_commercial_grade_v1"
    assert summary["commercial_primary_row_packet_rank_v1"] == 1
    assert summary["commercial_hard_gate_pass_v1"] is False
    assert summary["commercial_hard_gate_failed_metrics_v1"] == ["mean_min_distance_A"]
    assert summary["commercial_soft_score_v1"] == 52.8
    assert summary["commercial_confidence_score_v1"] == 65.9
    assert summary["commercial_overall_score_v1"] == 56.1
    assert summary["commercial_claim_observability_score_v1"] == 65.0
    assert summary["commercial_final_gate_support_score_v1"] == 35.0
    assert summary["commercial_risk_bucket_v1"] == "high"
    assert summary["commercial_decision_class_v1"] == "commercial_review_only"
    assert summary["commercial_primary_upgrade_actions_v1"] == ["tighten_pose_geometry_under_strict_gate"]
    assert summary["commercial_score_thresholds_v1"] == {
        "selected_threshold_A": 2.5,
        "strict_threshold_A": 2.5,
        "near_threshold_A": 3.0,
        "binding_energy_proxy_max_kcal_mol": -0.05,
        "stability_score_min": 0.35,
        "contact_fraction_min": 0.5,
        "binding_energy_mmpbsa_std_max": 0.18,
        "trajectory_frames_min": 180,
    }

    assert row["commercial_schema_version"] == "wetlab_commercial_grade_v1"
    assert row["commercial_distance_score_v1"] == 0.0
    assert row["commercial_energy_score_v1"] == 90.0
    assert row["commercial_stability_score_v1"] == 75.0
    assert row["commercial_contact_score_v1"] == 100.0
    assert row["commercial_uncertainty_score_v1"] == 85.0
    assert row["commercial_support_score_v1"] == 85.0
    assert row["commercial_soft_score_v1"] == 52.8
    assert row["commercial_confidence_score_v1"] == 71.0
    assert row["commercial_overall_score_v1"] == 57.3
    assert row["commercial_hard_gate_pass_v1"] is False
    assert row["commercial_hard_gate_failed_metrics_v1"] == ["mean_min_distance_A"]
    assert row["commercial_risk_bucket_v1"] == "high"
    assert row["commercial_decision_class_v1"] == "commercial_review_only"
    assert row["commercial_strict_margin_A_v1"] == -1.205


def test_build_wetlab_final_campaign_summary_prefers_dengue_queue_source_priority(tmp_path) -> None:
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
    assert summary["next_required_step"].startswith("Continue or complete Dengue NS2B-NS3 protease shard 17_of_20")


def test_build_wetlab_final_campaign_summary_selected_allatom_additive_surface_contract() -> None:
    empty = {"summary": {}}
    payload = mod.build_payload(
        {"summary": {"campaign_terminal_state": "complete", "chain_count": 1}, "rows": [{"chain_id": "selected", "chain_rank": 1, "queue_target_count": 1, "resolved_target_count": 1, "all_rows_resolved": True, "terminal_state": "complete"}]},
        {"summary": {"queue_target_count": 1, "resolved_target_count": 1}, "rows": [{"chain_id": "selected", "target_id": "T. cruzi PDE"}]},
        {"summary": {"track_count": 1, "ready_to_send_count": 1}},
        {"summary": {"target_count": 1}, "rows": [{"target_id": "T. cruzi PDE"}]},
        {"summary": {"target_count": 1}},
        {"summary": {"wave1_target_count": 1}},
        {"summary": {"status": "wetlab_broad_screen_queue_ready", "library_size": 1, "target_count": 1, "total_queue_rows": 1}},
        {"summary": {"status": "wetlab_broad_screen_bridge_ready", "library_size": 1, "final_packet_shape": "top-3 repurposing + top-3 novelty"}},
        broad_screen_retry_handoff_summary={
            "summary": {
                "status": "wetlab_retry_handoff_summary_ready",
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_surface_label": "synthetic_missing_selected_allatom_review_packet",
                "selected_allatom_selected_command_kind": "allatom_refinement",
                "selected_allatom_selected_threshold_A": 2.5,
                "selected_allatom_packet_scope": "selected_allatom_review_packet",
                "selected_allatom_operator_review_ready_reported": True,
                "selected_allatom_operator_review_ready": True,
                "selected_allatom_wetlab_gate_reported": True,
                "selected_allatom_wetlab_gate_pass": False,
                "selected_allatom_final_gate_reported": True,
                "selected_allatom_final_gate_pass": False,
                "selected_allatom_claim_gate_available_reported": True,
                "selected_allatom_claim_gate_available": False,
                "selected_allatom_claim_ready_for_allatom_reported": True,
                "selected_allatom_claim_ready_for_allatom": False,
                "selected_allatom_packet_ready_for_operator_review": True,
                "selected_allatom_wetlab_final_gate_pass": False,
                "selected_allatom_commercial_schema_version": "wetlab_commercial_grade_v1",
                "selected_allatom_commercial_reported": True,
                "selected_allatom_commercial_hard_gate_reported": True,
                "selected_allatom_commercial_hard_gate_pass_v1": False,
                "selected_allatom_commercial_overall_score_v1": 54.7,
                "selected_allatom_commercial_risk_bucket_v1": "high",
                "selected_allatom_commercial_decision_class_v1": "commercial_review_only",
                "selected_allatom_commercial_primary_upgrade_actions_v1": ["tighten_pose_geometry_under_strict_gate"],
                "selected_allatom_best_compound_name": "chembl_cache_e6069e85050b",
                "selected_allatom_best_compound_name_human_readable": "",
                "selected_allatom_best_compound_name_resolution": "cache_placeholder",
                "selected_allatom_best_mean_min_distance_A": 3.705,
                "selected_allatom_promoted_candidate_count": 4,
                "selected_allatom_under_2p5_candidate_count": 0,
                "selected_allatom_near_candidate_count": 2,
                "selected_allatom_next_required_step": (
                    "Review the promoted PDE pseudo all-atom top-4 packet manually only, keep the default lane closed, "
                    "and do not treat this rescue-only packet as wetlab-ready because the strict_only gate did not pass. "
                    "translation_gate=fail shortlist_tier=defer recommended_next_expensive_lane=defer_expensive_lane"
                ),
            }
        },
    )
    summary = payload["summary"]
    assert summary["selected_allatom_target_id"] == "T. cruzi PDE"
    assert summary["selected_allatom_commercial_schema_version"] == "wetlab_commercial_grade_v1"
    assert summary["selected_allatom_commercial_overall_score_v1"] == 54.7
    assert summary["selected_allatom_commercial_decision_class_v1"] == "commercial_review_only"
    assert summary["selected_allatom_commercial_human_summary_v2"] == (
        "Commercial-grade v2 is not yet reported for this focus."
    )
    assert summary["selected_allatom_commercial_provenance_mode_v2"] == "not_reported"
    assert summary["selected_allatom_commercial_human_summary_v2"] == (
        "Commercial-grade v2 is not yet reported for this focus."
    )
    assert summary["selected_allatom_translation_gate_version"] == "three_bead_to_allatom_translation_v1"
    assert summary["selected_allatom_translation_gate_focus_status"] == "fail"
    assert summary["selected_allatom_translation_gate_focus_score"] == 0.0
    assert summary["selected_allatom_translation_gate_focus_reason"] == ""
    assert summary["selected_allatom_focus_shortlist_tier"] == "defer"
    assert summary["selected_allatom_recommended_next_expensive_lane"] == "defer_expensive_lane"
    assert summary["selected_allatom_recommended_next_expensive_lane_reason"] == ""
    assert summary["selected_allatom_translation_provenance_mode"] == "inferred_from_partial_upstream"
    assert summary["selected_allatom_hybrid_policy"] == (
        "canonical_selected_allatom_source_driven_with_translation_text_fallback"
    )
    assert summary["selected_allatom_effective_actionability_status"] == "hard_blocked"
    assert summary["selected_allatom_effective_actionability_claim_requirement_mode"] == "not_applicable"
    assert summary["selected_allatom_effective_blocking_order"] == "hard_block_first"
    assert summary["selected_allatom_effective_primary_blocking_domain"] == "translation"
    assert "recompute_mean_min_distance_A" in summary["selected_allatom_action_recipe_codes"]
    assert "run_short_replicated_md" in summary["selected_allatom_action_recipe_rollup_text"]
    assert "produce_claim_equivalence_packet" in summary["selected_allatom_action_recipe_codes"]
    assert "defer_expensive_lane" in summary["selected_allatom_action_recipe_codes"]
    assert "blocking order hard_block_first" in summary["selected_allatom_claim_actionability_split_summary"]
    assert summary["selected_allatom_translation_summary"].startswith(
        "Translation/shortlist fallback (inferred from partial upstream; three_bead_to_allatom_translation_v1): status fail"
    )


def test_build_wetlab_final_campaign_summary_prefers_selected_allatom_canonical_resolver(monkeypatch) -> None:
    empty = {"summary": {}}

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

    payload = mod.build_payload(
        {"summary": {"campaign_terminal_state": "complete", "chain_count": 1}, "rows": []},
        empty,
        empty,
        empty,
        empty,
        empty,
        {"summary": {"status": "wetlab_broad_screen_queue_ready", "library_size": 1, "target_count": 1, "total_queue_rows": 1}},
        {"summary": {"status": "wetlab_broad_screen_bridge_ready", "library_size": 1, "final_packet_shape": "top-3 repurposing + top-3 novelty"}},
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
    assert summary["selected_allatom_hybrid_policy"] == "canonical_test_policy"
