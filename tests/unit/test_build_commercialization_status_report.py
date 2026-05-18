from __future__ import annotations

from tools import build_commercialization_status_report as mod


def test_build_commercialization_status_report() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
                "strongest_ready_families": "kinase, ion_channel, gpcr",
                "aqp1_first_wave_primary_focus_ligand": "bacopaside II",
                "aqp1_exact_human_reference_ligand": "AqB013",
                "aqp1_first_wave_follow_on_lane_label": "core_binder_02/03",
                "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": "cytochalasin B",
            },
            "rows": [
                {
                    "family": "transporter",
                    "primary_blocker": "top_queue_id=seed_core_binder_01; placeholder_driven_rows=9",
                    "claim_safe_scope": "non-authoritative transporter lane only",
                }
            ],
        },
        {
            "summary": {
                "highest_gap_family": "transporter",
                "next_required_step": "Reduce transporter placeholder rows first.",
            }
        },
        {
            "summary": {
                "next_required_step": "Keep transporter blocker closure first and keep cytochalasin B parked.",
            }
        },
        {
            "summary": {
                "placeholder_driven_rows": 9,
                "reducible_now_placeholder_rows": 3,
                "evidence_blocked_placeholder_rows": 6,
                "immediate_reduction_target": "GLUT1 binder staging surfaces",
                "immediate_reduction_target_queue_start": 4,
                "immediate_reduction_target_queue_end": 6,
                "immediate_reduction_delta_if_completed": 3,
            }
        },
        {"summary": {}},
    )

    summary = payload["summary"]
    assert summary["top_blocker_family"] == "transporter"
    assert summary["transporter_placeholder_driven_rows"] == 9
    assert summary["reducible_now_placeholder_rows"] == 3
    assert summary["evidence_blocked_placeholder_rows"] == 6
    assert summary["immediate_reduction_target"] == "GLUT1 binder staging surfaces"
    assert summary["immediate_reduction_target_queue_start"] == 4
    assert summary["immediate_reduction_target_queue_end"] == 6
    assert summary["immediate_reduction_delta_if_completed"] == 3
    assert summary["local_only_mode"] is True
    assert any("local-run commercialization gaps" in item for item in summary["report_gaps"])
    assert any("GLUT1 staging surfaces" in item for item in summary["fix_plan"])


def test_delivery_ready_is_not_effective_when_engine_queue_is_blocked() -> None:
    payload = mod.build_payload(
        {"summary": {"core_commercial_lane_score": 80.0, "all_category_expansion_score": 60.0}},
        {"summary": {"highest_gap_family": "transporter"}},
        {"summary": {}},
        {"summary": {"placeholder_driven_rows": 0, "reducible_now_placeholder_rows": 0}},
        local_engine_queue_payload={
            "summary": {
                "queue_clear": False,
                "blocked_count": 1,
                "top_priority_id": "wetlab_execution_readiness",
                "top_priority_status": "blocked",
            }
        },
        local_delivery_verdict_payload={
            "summary": {
                "delivery_ready": True,
                "verdict": "delivery_ready",
                "p0_blocker_count": 0,
                "hard_blocker_count": 0,
                "status_line": "delivery-ready verdict may be issued for the restricted local scope.",
            }
        },
    )

    summary = payload["summary"]
    assert summary["local_delivery_ready"] is True
    assert summary["effective_delivery_ready"] is False
    assert summary["local_delivery_queue_mismatch"] is True
    assert "stale or inconsistent" in summary["effective_delivery_status_line"]


def test_build_commercialization_status_report_handles_closed_reducible_slice() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
                "strongest_ready_families": "kinase, ion_channel, gpcr",
                "aqp1_first_wave_primary_focus_ligand": "bacopaside II",
                "aqp1_exact_human_reference_ligand": "AqB013",
                "aqp1_first_wave_follow_on_lane_label": "core_binder_02/03",
                "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": "cytochalasin B",
            },
            "rows": [
                {
                    "family": "transporter",
                    "primary_blocker": "top_queue_id=seed_core_binder_01; placeholder_driven_rows=6",
                    "claim_safe_scope": "non-authoritative transporter lane only",
                }
            ],
        },
        {"summary": {"highest_gap_family": "transporter", "next_required_step": "hold transporter negatives"}},
        {"summary": {"next_required_step": "keep transporter blocker closure first"}},
        {
            "summary": {
                "placeholder_driven_rows": 6,
                "reducible_now_placeholder_rows": 0,
                "evidence_blocked_placeholder_rows": 6,
                "immediate_reduction_target": "",
                "immediate_reduction_target_queue_start": 0,
                "immediate_reduction_target_queue_end": 0,
                "immediate_reduction_delta_if_completed": 0,
            }
        },
        {
            "summary": {
                "top_target_id": "AQP1",
                "top_packet_step": "core_non_binder_01",
            }
        },
        {"summary": {}},
        {
            "summary": {
                "top_priority_id": "nightly_reliability",
                "top_priority_status": "partial",
                "blocked_count": 1,
                "partial_count": 2,
                "parked_science_blocker_count": 1,
                "nightly_gate_burndown_artifact": "runs/nightly_gate_burndown_packet_current.md",
                "nightly_gate_primary_metric": "mean_min_distance_A",
                "nightly_gate_primary_value": 2.655165582969785,
                "nightly_gate_primary_threshold": 2.5,
                "nightly_gate_primary_delta": 0.15516558296978494,
                "nightly_status_line": "stage2 trajectory-generation now completes; the nightly lane is currently blocked by the operational gate at mean_min_distance_A=2.655 versus threshold 2.500.",
                "nightly_stage6_tuning_artifact": "runs/nightly_stage6_tuning_packet_current.md",
                "nightly_stage6_tuning_primary_focus_row_key": "EGFR_KINASE::aspirin",
                "nightly_stage6_followup_artifact": "runs/nightly_stage6_followup_retry_packet_current.md",
                "nightly_stage6_followup_primary_focus_row_key": "EGFR_KINASE::aspirin",
                "nightly_stage6_sweep_artifact": "runs/nightly_stage6_tuning_sweep_packet_current.md",
                "nightly_stage6_sweep_primary_focus_row_key": "HIV1_PROTEASE::imatinib",
                "nightly_stage6_sweep_primary_preset_id": "anchor_replay_baseline",
                "nightly_stage6_probe_artifact": "runs/nightly_stage6_probe_result_packet_current.md",
                "nightly_stage6_probe_primary_focus_row_key": "HIV1_PROTEASE::aspirin",
                "nightly_stage6_probe_projected_gate_pass": True,
                "nightly_stage6_promotion_artifact": "runs/nightly_stage6_probe_promotion_packet_current.md",
                "nightly_stage6_promotion_primary_focus_row_key": "HIV1_PROTEASE::aspirin",
                "nightly_stage6_promotion_projected_gate_pass": True,
                "nightly_stage6_realization_artifact": "runs/nightly_stage6_realization_packet_current.md",
                "nightly_stage6_realization_primary_focus_row_key": "HIV1_PROTEASE::aspirin",
                "nightly_stage6_realization_primary_preset_id": "target_forced_adress_uncapped_probe",
                "nightly_stage6_realization_gate_pass": True,
                "nightly_stage6_rescored_gate_artifact": "runs/nightly_stage6_rescored_gate_packet_current.md",
                "nightly_stage6_rescored_gate_primary_focus_row_key": "HIV1_PROTEASE::aspirin",
                "nightly_stage6_rescored_gate_primary_preset_id": "target_forced_adress_uncapped_probe",
                "nightly_stage6_rescored_gate_pass": True,
                "nightly_stage6_downstream_rerun_artifact": "runs/nightly_stage6_downstream_rerun_packet_current.md",
                "nightly_stage6_downstream_rerun_primary_focus_row_key": "HIV1_PROTEASE::aspirin",
                "nightly_stage6_downstream_rerun_primary_preset_id": "target_forced_adress_uncapped_probe",
                "nightly_stage6_downstream_rerun_target_subset": "EGFR_KINASE,HIV1_PROTEASE",
                "nightly_stage6_downstream_rerun_profile_json_artifact": "runs/nightly_stage6_downstream_rerun_profile_current.json",
                "nightly_stage6_downstream_rerun_dry_run_status_artifact": "runs/nightly_stage6_downstream_rerun_current_status.json",
                "nightly_stage6_downstream_rerun_dry_run_validated": True,
                "nightly_stage6_downstream_rerun_payload_pass": True,
                "nightly_stage6_execute_artifact": "runs/nightly_stage6_execute_result_packet_current.md",
                "nightly_stage6_execute_primary_focus_row_key": "HIV1_PROTEASE::aspirin",
                "nightly_stage6_execute_primary_preset_id": "target_forced_adress_uncapped_probe",
                "nightly_stage6_execute_target_subset": "EGFR_KINASE,HIV1_PROTEASE",
                "nightly_stage6_execute_status_json_artifact": "runs/nightly_stage6_downstream_execute_current_status.json",
                "nightly_stage6_execute_pipeline_summary_json_artifact": "runs/nightly_stage6_downstream_execute_current_summary.json",
                "nightly_stage6_execute_gate_mean_min_distance_A": 2.268931970372796,
                "nightly_stage6_execute_gate_pass": True,
                "nightly_stage6_execute_payload_pass": True,
                "nightly_stage6_execute_matches_rescored_gate": True,
                "viewer_status_line": "single=canvas missing · renderables 0",
                "wetlab_status_line": "ready_now=0; primary_watch=stale; antitarget_watch=detached; selected_allatom_gate=False",
                "next_required_step": "Raise engine commercialization first: keep the recovered nightly writer/import path green while tuning the stage6 gate.",
            }
        },
    )

    summary = payload["summary"]
    assert summary["transporter_placeholder_driven_rows"] == 6
    assert summary["reducible_now_placeholder_rows"] == 0
    assert summary["immediate_reduction_target"] == ""
    assert summary["immediate_reduction_target_queue_start"] == 0
    assert summary["immediate_reduction_target_queue_end"] == 0
    assert summary["immediate_reduction_delta_if_completed"] == 0
    assert summary["negative_evidence_queue_ready"] is True
    assert summary["negative_evidence_queue_top_target_id"] == "AQP1"
    assert summary["negative_evidence_queue_top_packet_step"] == "core_non_binder_01"
    assert summary["negative_target_packets_ready"] is False
    assert summary["local_engine_queue_top_priority_status"] == "partial"
    assert summary["local_engine_queue_nightly_gate_artifact"] == "runs/nightly_gate_burndown_packet_current.md"
    assert summary["local_engine_queue_nightly_tuning_artifact"] == "runs/nightly_stage6_tuning_packet_current.md"
    assert summary["local_engine_queue_nightly_tuning_focus_row_key"] == "EGFR_KINASE::aspirin"
    assert summary["local_engine_queue_nightly_followup_artifact"] == "runs/nightly_stage6_followup_retry_packet_current.md"
    assert summary["local_engine_queue_nightly_followup_focus_row_key"] == "EGFR_KINASE::aspirin"
    assert summary["local_engine_queue_nightly_sweep_artifact"] == "runs/nightly_stage6_tuning_sweep_packet_current.md"
    assert summary["local_engine_queue_nightly_sweep_focus_row_key"] == "HIV1_PROTEASE::imatinib"
    assert summary["local_engine_queue_nightly_sweep_primary_preset_id"] == "anchor_replay_baseline"
    assert summary["local_engine_queue_nightly_probe_artifact"] == "runs/nightly_stage6_probe_result_packet_current.md"
    assert summary["local_engine_queue_nightly_probe_focus_row_key"] == "HIV1_PROTEASE::aspirin"
    assert summary["local_engine_queue_nightly_probe_projected_gate_pass"] is True
    assert summary["local_engine_queue_nightly_promotion_artifact"] == "runs/nightly_stage6_probe_promotion_packet_current.md"
    assert summary["local_engine_queue_nightly_promotion_focus_row_key"] == "HIV1_PROTEASE::aspirin"
    assert summary["local_engine_queue_nightly_promotion_projected_gate_pass"] is True
    assert summary["local_engine_queue_nightly_realization_artifact"] == "runs/nightly_stage6_realization_packet_current.md"
    assert summary["local_engine_queue_nightly_realization_focus_row_key"] == "HIV1_PROTEASE::aspirin"
    assert summary["local_engine_queue_nightly_realization_primary_preset_id"] == "target_forced_adress_uncapped_probe"
    assert summary["local_engine_queue_nightly_realization_gate_pass"] is True
    assert summary["local_engine_queue_nightly_rescored_gate_artifact"] == "runs/nightly_stage6_rescored_gate_packet_current.md"
    assert summary["local_engine_queue_nightly_rescored_gate_focus_row_key"] == "HIV1_PROTEASE::aspirin"
    assert summary["local_engine_queue_nightly_rescored_gate_primary_preset_id"] == "target_forced_adress_uncapped_probe"
    assert summary["local_engine_queue_nightly_rescored_gate_pass"] is True
    assert summary["local_engine_queue_nightly_downstream_rerun_artifact"] == "runs/nightly_stage6_downstream_rerun_packet_current.md"
    assert summary["local_engine_queue_nightly_downstream_rerun_focus_row_key"] == "HIV1_PROTEASE::aspirin"
    assert summary["local_engine_queue_nightly_downstream_rerun_primary_preset_id"] == "target_forced_adress_uncapped_probe"
    assert summary["local_engine_queue_nightly_downstream_rerun_target_subset"] == "EGFR_KINASE,HIV1_PROTEASE"
    assert summary["local_engine_queue_nightly_downstream_rerun_profile_json_artifact"] == "runs/nightly_stage6_downstream_rerun_profile_current.json"
    assert summary["local_engine_queue_nightly_downstream_rerun_dry_run_status_artifact"] == "runs/nightly_stage6_downstream_rerun_current_status.json"
    assert summary["local_engine_queue_nightly_downstream_rerun_dry_run_validated"] is True
    assert summary["local_engine_queue_nightly_downstream_rerun_payload_pass"] is True
    assert summary["local_engine_queue_nightly_execute_artifact"] == "runs/nightly_stage6_execute_result_packet_current.md"
    assert summary["local_engine_queue_nightly_execute_focus_row_key"] == "HIV1_PROTEASE::aspirin"
    assert summary["local_engine_queue_nightly_execute_primary_preset_id"] == "target_forced_adress_uncapped_probe"
    assert summary["local_engine_queue_nightly_execute_target_subset"] == "EGFR_KINASE,HIV1_PROTEASE"
    assert summary["local_engine_queue_nightly_execute_status_json_artifact"] == "runs/nightly_stage6_downstream_execute_current_status.json"
    assert summary["local_engine_queue_nightly_execute_pipeline_summary_json_artifact"] == "runs/nightly_stage6_downstream_execute_current_summary.json"
    assert summary["local_engine_queue_nightly_execute_gate_pass"] is True
    assert summary["local_engine_queue_nightly_execute_payload_pass"] is True
    assert summary["local_engine_queue_nightly_execute_matches_rescored_gate"] is True
    assert "mean_min_distance_A=2.655" in summary["local_engine_queue_nightly_status_line"]
    assert "canvas missing" in summary["local_engine_queue_viewer_status_line"]
    assert "ready_now=0" in summary["local_engine_queue_wetlab_status_line"]
    assert any("runs/transporter_negative_evidence_closure_queue_current.md" in item for item in summary["immediate_priority"])
    assert any("Nightly status line:" in item for item in summary["immediate_priority"])
    assert any("runs/nightly_gate_burndown_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/nightly_stage6_tuning_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/nightly_stage6_followup_retry_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/nightly_stage6_probe_result_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/nightly_stage6_probe_promotion_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/nightly_stage6_realization_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/nightly_stage6_rescored_gate_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/nightly_stage6_downstream_rerun_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/nightly_stage6_execute_result_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/nightly_stage6_tuning_sweep_packet_current.md" in item for item in summary["artifacts"])
    assert any("runs/nightly_stage6_probe_result_packet_current.md" in item for item in summary["artifacts"])
    assert any("runs/nightly_stage6_probe_promotion_packet_current.md" in item for item in summary["artifacts"])
    assert any("runs/nightly_stage6_realization_packet_current.md" in item for item in summary["artifacts"])
    assert any("runs/nightly_stage6_rescored_gate_packet_current.md" in item for item in summary["artifacts"])
    assert any("runs/nightly_stage6_downstream_rerun_packet_current.md" in item for item in summary["artifacts"])
    assert any("runs/nightly_stage6_execute_result_packet_current.md" in item for item in summary["artifacts"])
    assert any("evidence-blocked negative rows" in item for item in summary["fix_plan"])


def test_build_commercialization_status_report_uses_keep_green_wording_when_queue_clear() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
                "strongest_ready_families": "kinase, ion_channel, gpcr",
                "aqp1_first_wave_primary_focus_ligand": "bacopaside II",
                "aqp1_exact_human_reference_ligand": "AqB013",
                "aqp1_first_wave_follow_on_lane_label": "core_binder_02/03",
                "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": "cytochalasin B",
            },
            "rows": [{"family": "transporter", "primary_blocker": "negative evidence", "claim_safe_scope": "local-only"}],
        },
        {"summary": {"highest_gap_family": "transporter"}},
        {"summary": {"next_required_step": "keep green"}},
        {
            "summary": {
                "placeholder_driven_rows": 6,
                "reducible_now_placeholder_rows": 0,
                "evidence_blocked_placeholder_rows": 6,
            }
        },
        {
            "summary": {
                "top_target_id": "AQP1",
                "top_packet_step": "core_non_binder_01",
                "top_source_context_artifact": "runs/aqp1_negative_evidence_confirmation_packet_current.md",
                "top_source_context_role": "exact_source_confirmation_not_authoritative_negative",
                "aqp1_source_context_focus_ligand": "sodium nitroprusside",
                "aqp1_source_context_direct_negative_quantitative_row_found_count": 0,
                "aqp1_source_context_authoritative_negative_apply_allowed_count": 0,
                "glut1_negative_handoff_artifact": "runs/glut1_negative_review_handoff_packet_current.md",
            }
        },
        {"summary": {}},
        {
            "summary": {
                "queue_clear": True,
                "top_priority_id": "transporter_science_blocker",
                "top_priority_status": "parked",
                "blocked_count": 0,
                "partial_count": 0,
                "keep_green_count": 4,
                "parked_science_blocker_count": 1,
                "nightly_gate_burndown_artifact": "runs/nightly_gate_burndown_packet_current.md",
                "nightly_status_line": "latest nightly pass is green",
                "nightly_stage6_execute_artifact": "runs/nightly_stage6_execute_result_packet_current.md",
                "nightly_stage6_execute_target_subset": "EGFR_KINASE,HIV1_PROTEASE",
                "nightly_stage6_execute_gate_mean_min_distance_A": "2.2689",
                "nightly_stage6_execute_gate_pass": True,
                "nightly_stage6_execute_payload_pass": True,
                "nightly_stage6_execute_matches_rescored_gate": True,
                "viewer_status": "keep_green",
                "viewer_status_line": "viewer green",
                "wetlab_status_line": "wetlab green",
                "wetlab_selected_allatom_gate_burndown_artifact": "runs/wetlab_selected_allatom_gate_burndown_packet_current.md",
                "wetlab_selected_allatom_target_id": "T. cruzi PDE",
                "wetlab_selected_allatom_primary_burndown_metric": "mean_min_distance_A",
                "wetlab_selected_allatom_primary_burndown_value": "2.120",
                "wetlab_selected_allatom_primary_burndown_threshold": "2.500",
            }
        },
        {
            "summary": {
                "delivery_ready": True,
                "verdict": "delivery_ready",
                "p0_blocker_count": 0,
                "hard_blocker_count": 0,
                "status_line": "delivery-ready verdict may be issued for the restricted local scope.",
            }
        },
        {
            "summary": {
                "packet_artifact": "runs/keep_green_regression_trend_packet_current.md",
                "commercial_trend_status": "baseline_green_needs_repeated_history",
                "all_current_green": True,
                "sufficient_repeated_history": False,
                "current_green_lane_count": 4,
                "lane_count": 4,
                "repeated_history_ready_lane_count": 1,
                "insufficient_history_lane_count": 3,
                "minimum_repeated_sample_count": 3,
                "nightly_recent_pass_streak": 2,
            }
        },
        {
            "summary": {
                "packet_artifact": "runs/platform_gap_taxonomy_packet_current.md",
                "current_delivery_blocker_count": 0,
                "expansion_blocker_count": 23,
                "non_transporter_gap_count": 4,
                "transporter_specific_split_resolved": True,
                "top_expansion_gap_id": "keep_green_repeated_history",
                "top_expansion_gap_class": "keep_green_history",
                "ligand_scaleup_claim_safe_status": "regression_guardrail_failed",
            }
        },
    )

    summary = payload["summary"]
    assert summary["local_engine_queue_clear"] is True
    assert summary["local_engine_queue_keep_green_count"] == 4
    assert summary["local_delivery_ready"] is True
    assert summary["local_delivery_verdict"] == "delivery_ready"
    assert summary["keep_green_trend_artifact"] == "runs/keep_green_regression_trend_packet_current.md"
    assert summary["keep_green_trend_status"] == "baseline_green_needs_repeated_history"
    assert summary["keep_green_trend_all_current_green"] is True
    assert summary["keep_green_trend_sufficient_repeated_history"] is False
    assert summary["keep_green_trend_current_green_lane_count"] == 4
    assert summary["keep_green_trend_repeated_history_ready_lane_count"] == 1
    assert summary["keep_green_trend_nightly_recent_pass_streak"] == 2
    assert summary["platform_gap_taxonomy_artifact"] == "runs/platform_gap_taxonomy_packet_current.md"
    assert summary["platform_gap_taxonomy_current_delivery_blocker_count"] == 0
    assert summary["platform_gap_taxonomy_expansion_blocker_count"] == 23
    assert summary["platform_gap_taxonomy_non_transporter_gap_count"] == 4
    assert summary["platform_gap_taxonomy_transporter_specific_split_resolved"] is True
    assert summary["platform_gap_taxonomy_top_expansion_gap_id"] == "keep_green_repeated_history"
    assert summary["platform_gap_taxonomy_ligand_scaleup_claim_safe_status"] == "regression_guardrail_failed"
    assert any("keep-green board" in item for item in summary["immediate_priority"])
    assert any("Local delivery verdict is `delivery_ready`" in item for item in summary["immediate_priority"])
    assert any("nightly gate regression artifact" in item for item in summary["immediate_priority"])
    assert any("runs/keep_green_regression_trend_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/platform_gap_taxonomy_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("platform-wide gap taxonomy" in item for item in summary["immediate_priority"])
    assert not any("Burn down engine blockers" in item for item in summary["immediate_priority"])
    assert not any("burndown packet: tune" in item for item in summary["immediate_priority"])
    assert any("restricted local scope" in item for item in summary["report_gaps"])
    assert any("repeated-history sufficiency is not complete" in item for item in summary["report_gaps"])
    assert any(
        "transporter placeholder counts are no longer the only commercialization split" in item
        for item in summary["report_gaps"]
    )
    assert any("recurrent canonical nightly" in item for item in summary["fix_plan"])
    assert any("runs/keep_green_regression_trend_packet_current.md" in item for item in summary["artifacts"])
    assert any("runs/platform_gap_taxonomy_packet_current.md" in item for item in summary["artifacts"])


def test_build_commercialization_status_report_exposes_negative_target_packets() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
                "strongest_ready_families": "kinase, ion_channel, gpcr",
                "aqp1_first_wave_primary_focus_ligand": "bacopaside II",
                "aqp1_exact_human_reference_ligand": "AqB013",
                "aqp1_first_wave_follow_on_lane_label": "core_binder_02/03",
                "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": "cytochalasin B",
            },
            "rows": [{"family": "transporter", "primary_blocker": "negative evidence", "claim_safe_scope": "local-only"}],
        },
        {"summary": {"highest_gap_family": "transporter", "next_required_step": "hold transporter negatives"}},
        {"summary": {"next_required_step": "keep transporter blocker closure first"}},
        {
            "summary": {
                "placeholder_driven_rows": 6,
                "reducible_now_placeholder_rows": 0,
                "evidence_blocked_placeholder_rows": 6,
            }
        },
        {
            "summary": {
                "top_target_id": "AQP1",
                "top_packet_step": "core_non_binder_01",
                "top_source_context_artifact": "runs/aqp1_negative_evidence_confirmation_packet_current.md",
                "top_source_context_role": "exact_source_confirmation_not_authoritative_negative",
                "aqp1_source_context_focus_ligand": "sodium nitroprusside",
                "aqp1_source_context_direct_negative_quantitative_row_found_count": 0,
                "aqp1_source_context_authoritative_negative_apply_allowed_count": 0,
                "glut1_negative_handoff_artifact": "runs/glut1_negative_review_handoff_packet_current.md",
            }
        },
        {
            "summary": {
                "top_target_id": "AQP1",
                "top_queue_rank_start": 1,
                "top_queue_rank_end": 3,
                "aqp1_slot_closure_artifact": "runs/aqp1_negative_slot_closure_packet_current.md",
                "aqp1_slot_closure_top_packet_step": "core_non_binder_01",
                "aqp1_negative_confirmation_artifact": "runs/aqp1_negative_evidence_confirmation_packet_current.md",
                "aqp1_negative_confirmation_primary_anchor_pmid": "23123479",
                "aqp1_negative_confirmation_boundary_positive_pmid": "40359885",
                "aqp1_negative_confirmation_decision": "keep_review_only_no_authoritative_negative_promotion",
                "aqp1_negative_slot_resolution_artifact": "runs/aqp1_negative_slot_resolution_packet_current.md",
                "aqp1_negative_slot_resolution_top_packet_step": "core_non_binder_01",
                "aqp1_negative_slot_resolution_primary_anchor_pmid": "23123479",
                "aqp1_negative_candidate_frontier_artifact": "runs/aqp1_negative_candidate_frontier_packet_current.md",
                "aqp1_negative_candidate_frontier_primary_frontier_candidate": "sodium nitroprusside",
                "aqp1_negative_frontier_resolution_artifact": "runs/aqp1_negative_frontier_resolution_packet_current.md",
                "aqp1_negative_frontier_resolution_primary_frontier_candidate": "sodium nitroprusside",
                "aqp1_negative_frontier_resolution_solvent_fallback_candidate": "dimethyl sulfoxide",
                "aqp1_negative_primary_probe_artifact": "runs/aqp1_negative_primary_probe_packet_current.md",
                "aqp1_negative_primary_probe_candidate": "sodium nitroprusside",
                "aqp1_negative_primary_probe_source_anchor_pmid": "23123479",
                "aqp1_negative_primary_probe_resolution_artifact": "runs/aqp1_negative_primary_probe_resolution_packet_current.md",
                "aqp1_negative_primary_probe_resolution_candidate": "sodium nitroprusside",
                "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": "dimethyl sulfoxide",
                "aqp1_negative_primary_probe_resolution_decision": "keep_review_only_no_authoritative_negative_promotion",
                "aqp1_negative_direct_evidence_audit_artifact": "runs/aqp1_negative_direct_evidence_audit_packet_current.md",
                "aqp1_negative_direct_evidence_audit_pubmed_exact_ligand_target_hit_count": 8,
                "aqp1_negative_direct_evidence_audit_chembl_exact_target_pair_activity_count": 0,
                "aqp1_negative_direct_evidence_audit_direct_negative_quantitative_row_found_count": 0,
                "aqp1_negative_direct_evidence_audit_no_direct_negative_source_row_count": 3,
                "aqp1_negative_direct_evidence_audit_decision": "keep_review_only_no_authoritative_negative_promotion",
                "aqp1_negative_acquisition_artifact": "runs/aqp1_negative_evidence_acquisition_packet_current.md",
                "aqp1_negative_acquisition_primary_query_label": "pressure_induced_hemolysis_reinvestigation",
                "glut1_negative_direct_evidence_audit_artifact": "runs/glut1_negative_direct_evidence_audit_packet_current.md",
                "glut1_negative_direct_evidence_audit_placeholder_negative_candidate_count": 3,
                "glut1_negative_direct_evidence_audit_source_context_positive_or_binder_candidate_count": 3,
                "glut1_negative_direct_evidence_audit_direct_negative_quantitative_row_found_count": 0,
                "glut1_negative_direct_evidence_audit_decision": "keep_placeholder_negative_slots_review_only_no_authoritative_negative_promotion",
            }
        },
    )

    summary = payload["summary"]
    assert summary["negative_target_packets_ready"] is True
    assert summary["negative_evidence_queue_top_source_context_artifact"] == "runs/aqp1_negative_evidence_confirmation_packet_current.md"
    assert summary["negative_evidence_queue_top_source_context_role"] == "exact_source_confirmation_not_authoritative_negative"
    assert summary["negative_evidence_queue_aqp1_source_context_focus_ligand"] == "sodium nitroprusside"
    assert summary["negative_evidence_queue_aqp1_direct_negative_quantitative_row_found_count"] == 0
    assert summary["negative_evidence_queue_aqp1_authoritative_negative_apply_allowed_count"] == 0
    assert summary["negative_evidence_queue_glut1_negative_handoff_artifact"] == "runs/glut1_negative_review_handoff_packet_current.md"
    assert summary["negative_target_packets_top_target_id"] == "AQP1"
    assert summary["negative_target_packets_top_queue_rank_start"] == 1
    assert summary["negative_target_packets_top_queue_rank_end"] == 3
    assert summary["negative_target_packets_aqp1_direct_evidence_audit_artifact"] == "runs/aqp1_negative_direct_evidence_audit_packet_current.md"
    assert summary["negative_target_packets_aqp1_direct_evidence_audit_pubmed_exact_ligand_target_hit_count"] == 8
    assert summary["negative_target_packets_aqp1_direct_evidence_audit_chembl_exact_target_pair_activity_count"] == 0
    assert summary["negative_target_packets_aqp1_direct_evidence_audit_direct_negative_quantitative_row_found_count"] == 0
    assert summary["negative_target_packets_aqp1_direct_evidence_audit_decision"] == "keep_review_only_no_authoritative_negative_promotion"
    assert summary["negative_target_packets_glut1_direct_evidence_audit_artifact"] == "runs/glut1_negative_direct_evidence_audit_packet_current.md"
    assert summary["negative_target_packets_glut1_direct_evidence_audit_placeholder_negative_candidate_count"] == 3
    assert summary["negative_target_packets_glut1_direct_evidence_audit_source_context_positive_or_binder_candidate_count"] == 3
    assert summary["negative_target_packets_glut1_direct_evidence_audit_direct_negative_quantitative_row_found_count"] == 0
    assert summary["negative_target_packets_glut1_direct_evidence_audit_decision"] == "keep_placeholder_negative_slots_review_only_no_authoritative_negative_promotion"
    assert any("runs/transporter_negative_evidence_target_packets_current.md" in item for item in summary["immediate_priority"])
    assert any("exact_source_confirmation_not_authoritative_negative" in item for item in summary["immediate_priority"])
    assert any("runs/glut1_negative_review_handoff_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/aqp1_negative_slot_closure_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/aqp1_negative_evidence_confirmation_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/aqp1_negative_slot_resolution_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/aqp1_negative_candidate_frontier_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/aqp1_negative_frontier_resolution_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/aqp1_negative_primary_probe_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/aqp1_negative_primary_probe_resolution_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/aqp1_negative_direct_evidence_audit_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("PubMed exact ligand/target hits=`8`" in item for item in summary["immediate_priority"])
    assert any("runs/aqp1_negative_evidence_acquisition_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("runs/glut1_negative_direct_evidence_audit_packet_current.md" in item for item in summary["immediate_priority"])
    assert any("placeholder negative slots=`3`" in item for item in summary["immediate_priority"])
    assert any("runs/aqp1_negative_direct_evidence_audit_packet_current.md" in item for item in summary["artifacts"])
    assert any("runs/glut1_negative_direct_evidence_audit_packet_current.md" in item for item in summary["artifacts"])


def test_build_commercialization_status_report_exposes_external_evidence_crosscheck() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
                "strongest_ready_families": "kinase, ion_channel, gpcr",
                "aqp1_first_wave_primary_focus_ligand": "bacopaside II",
                "aqp1_exact_human_reference_ligand": "AqB013",
                "aqp1_first_wave_follow_on_lane_label": "core_binder_02/03",
                "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": "cytochalasin B",
            },
            "rows": [{"family": "transporter", "primary_blocker": "negative evidence", "claim_safe_scope": "local-only"}],
        },
        {"summary": {"highest_gap_family": "transporter"}},
        {"summary": {"next_required_step": "Keep transporter negative evidence parked."}},
        {"summary": {"placeholder_driven_rows": 6, "reducible_now_placeholder_rows": 0, "evidence_blocked_placeholder_rows": 6}},
        external_evidence_crosscheck_payload={
            "summary": {
                "crosscheck_ready": True,
                "skill_family": "life_science_research",
                "skill_source_count": 6,
                "target_count": 2,
                "row_count": 5,
                "aqp1_uniprot_accession": "P29972",
                "glut1_uniprot_accession": "P11166",
                "aqp1_chembl_target_id": "CHEMBL4523210",
                "glut1_chembl_target_id": "CHEMBL2535",
                "rcsb_glut1_entry": "4PYP",
                "aqp1_bindingdb_affinity_count": 0,
                "glut1_bindingdb_affinity_count": 123,
                "glut1_positive_exact_activity_count": 5,
                "direct_negative_quantitative_row_found_count": 0,
                "authoritative_negative_apply_allowed_count": 0,
                "negative_evidence_closure_allowed": False,
                "current_decision": "keep_transporter_negative_slots_review_only",
            }
        },
    )

    summary = payload["summary"]
    assert summary["external_evidence_crosscheck_ready"] is True
    assert summary["external_evidence_crosscheck_artifact"] == "runs/transporter_external_evidence_crosscheck_current.md"
    assert summary["external_evidence_crosscheck_skill_family"] == "life_science_research"
    assert summary["external_evidence_crosscheck_skill_source_count"] == 6
    assert summary["external_evidence_crosscheck_target_count"] == 2
    assert summary["external_evidence_crosscheck_row_count"] == 5
    assert summary["external_evidence_crosscheck_aqp1_uniprot_accession"] == "P29972"
    assert summary["external_evidence_crosscheck_glut1_uniprot_accession"] == "P11166"
    assert summary["external_evidence_crosscheck_aqp1_chembl_target_id"] == "CHEMBL4523210"
    assert summary["external_evidence_crosscheck_glut1_chembl_target_id"] == "CHEMBL2535"
    assert summary["external_evidence_crosscheck_rcsb_glut1_entry"] == "4PYP"
    assert summary["external_evidence_crosscheck_aqp1_bindingdb_affinity_count"] == 0
    assert summary["external_evidence_crosscheck_glut1_bindingdb_affinity_count"] == 123
    assert summary["external_evidence_crosscheck_glut1_positive_exact_activity_count"] == 5
    assert summary["external_evidence_crosscheck_direct_negative_quantitative_row_found_count"] == 0
    assert summary["external_evidence_crosscheck_authoritative_negative_apply_allowed_count"] == 0
    assert summary["external_evidence_crosscheck_negative_evidence_closure_allowed"] is False
    assert summary["external_evidence_crosscheck_current_decision"] == "keep_transporter_negative_slots_review_only"
    assert any("Life Science Research external crosscheck" in item for item in summary["strengths"])
    assert any("skill-backed external evidence crosscheck" in item for item in summary["immediate_priority"])
    assert any("External life-science database crosscheck" in item for item in summary["report_gaps"])
    assert any("exact target-pair quantitative negative evidence" in item for item in summary["fix_plan"])
    assert any("runs/transporter_external_evidence_crosscheck_current.md" in item for item in summary["artifacts"])


def test_build_commercialization_status_report_exposes_negative_candidate_harvest() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
                "strongest_ready_families": "kinase, ion_channel, gpcr",
                "aqp1_first_wave_primary_focus_ligand": "bacopaside II",
                "aqp1_exact_human_reference_ligand": "AqB013",
                "aqp1_first_wave_follow_on_lane_label": "core_binder_02/03",
                "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": "cytochalasin B",
            },
            "rows": [{"family": "transporter", "primary_blocker": "negative evidence", "claim_safe_scope": "local-only"}],
        },
        {"summary": {"highest_gap_family": "transporter"}},
        {"summary": {"next_required_step": "Keep transporter negative evidence parked."}},
        {"summary": {"placeholder_driven_rows": 6, "reducible_now_placeholder_rows": 0, "evidence_blocked_placeholder_rows": 6}},
        negative_candidate_harvest_payload={
            "summary": {
                "candidate_harvest_ready": True,
                "packet_artifact": "runs/transporter_negative_candidate_harvest_current.md",
                "candidate_harvest_status": "glut1_quantitative_candidate_review_available_aqp1_still_blocked",
                "row_count": 40,
                "aqp1_candidate_review_row_count": 2,
                "glut1_candidate_review_row_count": 38,
                "aqp1_quantitative_lower_bound_candidate_count": 0,
                "glut1_quantitative_lower_bound_candidate_count": 5,
                "potential_aqp1_negative_slot_cover_count": 0,
                "potential_glut1_negative_slot_cover_count": 3,
                "unreviewed_direct_negative_quantitative_candidate_count": 5,
                "authoritative_negative_apply_allowed_count": 0,
                "negative_evidence_closure_allowed": False,
            }
        },
    )

    summary = payload["summary"]
    assert summary["negative_candidate_harvest_ready"] is True
    assert summary["negative_candidate_harvest_artifact"] == "runs/transporter_negative_candidate_harvest_current.md"
    assert summary["negative_candidate_harvest_status"] == "glut1_quantitative_candidate_review_available_aqp1_still_blocked"
    assert summary["negative_candidate_harvest_row_count"] == 40
    assert summary["negative_candidate_harvest_aqp1_candidate_review_row_count"] == 2
    assert summary["negative_candidate_harvest_glut1_candidate_review_row_count"] == 38
    assert summary["negative_candidate_harvest_aqp1_quantitative_lower_bound_candidate_count"] == 0
    assert summary["negative_candidate_harvest_glut1_quantitative_lower_bound_candidate_count"] == 5
    assert summary["negative_candidate_harvest_potential_aqp1_negative_slot_cover_count"] == 0
    assert summary["negative_candidate_harvest_potential_glut1_negative_slot_cover_count"] == 3
    assert summary["negative_candidate_harvest_unreviewed_direct_negative_quantitative_candidate_count"] == 5
    assert summary["negative_candidate_harvest_authoritative_negative_apply_allowed_count"] == 0
    assert summary["negative_candidate_harvest_negative_evidence_closure_allowed"] is False
    assert any("negative-candidate harvest" in item for item in summary["strengths"])
    assert any("candidate harvest board" in item for item in summary["immediate_priority"])
    assert any("target-level ChEMBL harvest" in item for item in summary["report_gaps"])
    assert any("harvested GLUT1 lower-bound candidates" in item for item in summary["fix_plan"])
    assert any("runs/transporter_negative_candidate_harvest_current.md" in item for item in summary["artifacts"])


def test_build_commercialization_status_report_exposes_negative_candidate_curation_queue() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
                "strongest_ready_families": "kinase, ion_channel, gpcr",
                "aqp1_first_wave_primary_focus_ligand": "bacopaside II",
                "aqp1_exact_human_reference_ligand": "AqB013",
                "aqp1_first_wave_follow_on_lane_label": "core_binder_02/03",
                "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": "cytochalasin B",
            },
            "rows": [{"family": "transporter", "primary_blocker": "negative evidence", "claim_safe_scope": "local-only"}],
        },
        {"summary": {"highest_gap_family": "transporter"}},
        {"summary": {"next_required_step": "Keep transporter negative evidence parked."}},
        {"summary": {"placeholder_driven_rows": 6, "reducible_now_placeholder_rows": 0, "evidence_blocked_placeholder_rows": 6}},
        negative_candidate_curation_queue_payload={
            "summary": {
                "curation_queue_ready": True,
                "packet_artifact": "runs/transporter_negative_candidate_curation_queue_current.md",
                "source_harvest_artifact": "runs/transporter_negative_candidate_harvest_current.md",
                "target_id": "GLUT1",
                "available_quantitative_lower_bound_candidate_count": 5,
                "target_negative_slot_count": 3,
                "queue_row_count": 3,
                "slot_cover_ready_count": 3,
                "unused_candidate_count": 2,
                "aqp1_first_blocker_open": True,
                "candidate_apply_allowed": False,
                "authoritative_negative_apply_allowed_count": 0,
                "negative_evidence_closure_allowed": False,
                "claim_promotion_allowed": False,
                "queue_status": "glut1_curation_queue_ready_aqp1_first_blocker_still_open",
            }
        },
    )

    summary = payload["summary"]
    assert summary["negative_candidate_curation_queue_ready"] is True
    assert (
        summary["negative_candidate_curation_queue_artifact"]
        == "runs/transporter_negative_candidate_curation_queue_current.md"
    )
    assert summary["negative_candidate_curation_queue_target_id"] == "GLUT1"
    assert summary["negative_candidate_curation_queue_status"] == "glut1_curation_queue_ready_aqp1_first_blocker_still_open"
    assert summary["negative_candidate_curation_queue_source_harvest_artifact"] == "runs/transporter_negative_candidate_harvest_current.md"
    assert summary["negative_candidate_curation_queue_available_quantitative_lower_bound_candidate_count"] == 5
    assert summary["negative_candidate_curation_queue_target_negative_slot_count"] == 3
    assert summary["negative_candidate_curation_queue_row_count"] == 3
    assert summary["negative_candidate_curation_queue_slot_cover_ready_count"] == 3
    assert summary["negative_candidate_curation_queue_unused_candidate_count"] == 2
    assert summary["negative_candidate_curation_queue_aqp1_first_blocker_open"] is True
    assert summary["negative_candidate_curation_queue_candidate_apply_allowed"] is False
    assert summary["negative_candidate_curation_queue_authoritative_negative_apply_allowed_count"] == 0
    assert summary["negative_candidate_curation_queue_negative_evidence_closure_allowed"] is False
    assert summary["negative_candidate_curation_queue_claim_promotion_allowed"] is False
    assert any("GLUT1 negative-candidate curation queue" in item for item in summary["strengths"])
    assert any("GLUT1 pre-apply curation queue" in item for item in summary["immediate_priority"])
    assert any("GLUT1 curation queue now covers" in item for item in summary["report_gaps"])
    assert any("Review the GLUT1 curation queue row by row" in item for item in summary["fix_plan"])
    assert any("runs/transporter_negative_candidate_curation_queue_current.md" in item for item in summary["artifacts"])


def test_build_commercialization_status_report_exposes_aqp1_negative_evidence_gap_matrix() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
                "strongest_ready_families": "kinase, ion_channel, gpcr",
                "aqp1_first_wave_primary_focus_ligand": "bacopaside II",
                "aqp1_exact_human_reference_ligand": "AqB013",
                "aqp1_first_wave_follow_on_lane_label": "core_binder_02/03",
                "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": "cytochalasin B",
            },
            "rows": [{"family": "transporter", "primary_blocker": "negative evidence", "claim_safe_scope": "local-only"}],
        },
        {"summary": {"highest_gap_family": "transporter"}},
        {"summary": {"next_required_step": "Keep transporter negative evidence parked."}},
        {"summary": {"placeholder_driven_rows": 6, "reducible_now_placeholder_rows": 0, "evidence_blocked_placeholder_rows": 6}},
        aqp1_negative_evidence_gap_matrix_payload={
            "summary": {
                "gap_matrix_ready": True,
                "packet_artifact": "runs/aqp1_negative_evidence_gap_matrix_current.md",
                "gap_status": "aqp1_direct_negative_quantitative_evidence_absent",
                "target_uniprot_accession": "P29972",
                "target_chembl_id": "CHEMBL4523210",
                "negative_slot_count": 3,
                "evidence_route_count": 5,
                "blocked_route_count": 5,
                "review_context_route_count": 3,
                "direct_negative_quantitative_row_found_count": 0,
                "authoritative_negative_apply_allowed_count": 0,
                "negative_slot_cover_ready_count": 0,
                "negative_slot_cover_missing_count": 3,
                "claim_promotion_allowed": False,
                "commercialization_blocker": "hard_blocker_for_broad_transporter_claim",
            }
        },
    )

    summary = payload["summary"]
    assert summary["aqp1_negative_evidence_gap_matrix_ready"] is True
    assert summary["aqp1_negative_evidence_gap_matrix_artifact"] == "runs/aqp1_negative_evidence_gap_matrix_current.md"
    assert summary["aqp1_negative_evidence_gap_matrix_status"] == "aqp1_direct_negative_quantitative_evidence_absent"
    assert summary["aqp1_negative_evidence_gap_matrix_target_uniprot_accession"] == "P29972"
    assert summary["aqp1_negative_evidence_gap_matrix_target_chembl_id"] == "CHEMBL4523210"
    assert summary["aqp1_negative_evidence_gap_matrix_negative_slot_count"] == 3
    assert summary["aqp1_negative_evidence_gap_matrix_evidence_route_count"] == 5
    assert summary["aqp1_negative_evidence_gap_matrix_blocked_route_count"] == 5
    assert summary["aqp1_negative_evidence_gap_matrix_review_context_route_count"] == 3
    assert summary["aqp1_negative_evidence_gap_matrix_direct_negative_quantitative_row_found_count"] == 0
    assert summary["aqp1_negative_evidence_gap_matrix_authoritative_negative_apply_allowed_count"] == 0
    assert summary["aqp1_negative_evidence_gap_matrix_negative_slot_cover_ready_count"] == 0
    assert summary["aqp1_negative_evidence_gap_matrix_negative_slot_cover_missing_count"] == 3
    assert summary["aqp1_negative_evidence_gap_matrix_claim_promotion_allowed"] is False
    assert summary["aqp1_negative_evidence_gap_matrix_commercialization_blocker"] == "hard_blocker_for_broad_transporter_claim"
    assert any("AQP1 negative-evidence gap matrix" in item for item in summary["strengths"])
    assert any("AQP1 blocker matrix" in item for item in summary["immediate_priority"])
    assert any("AQP1 is now decomposed by evidence route" in item for item in summary["report_gaps"])
    assert any("For AQP1, stop spending cycles" in item for item in summary["fix_plan"])
    assert any("runs/aqp1_negative_evidence_gap_matrix_current.md" in item for item in summary["artifacts"])


def test_build_commercialization_status_report_exposes_aqp1_negative_evidence_request_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
                "strongest_ready_families": "kinase, ion_channel, gpcr",
                "aqp1_first_wave_primary_focus_ligand": "bacopaside II",
                "aqp1_exact_human_reference_ligand": "AqB013",
                "aqp1_first_wave_follow_on_lane_label": "core_binder_02/03",
                "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": "cytochalasin B",
            },
            "rows": [{"family": "transporter", "primary_blocker": "negative evidence", "claim_safe_scope": "local-only"}],
        },
        {"summary": {"highest_gap_family": "transporter"}},
        {"summary": {"next_required_step": "Keep transporter negative evidence parked."}},
        {"summary": {"placeholder_driven_rows": 6, "reducible_now_placeholder_rows": 0, "evidence_blocked_placeholder_rows": 6}},
        aqp1_negative_evidence_request_payload={
            "summary": {
                "evidence_request_ready": True,
                "packet_artifact": "runs/aqp1_negative_evidence_request_packet_current.md",
                "source_gap_matrix_artifact": "runs/aqp1_negative_evidence_gap_matrix_current.md",
                "request_status": "ready_for_public_or_internal_exact_evidence_acquisition",
                "request_mode": "exact_target_pair_quantitative_negative_evidence_required",
                "request_row_count": 3,
                "required_assignable_negative_row_count": 3,
                "current_direct_negative_quantitative_row_found_count": 0,
                "negative_slot_cover_ready_count": 0,
                "negative_slot_cover_missing_count": 3,
                "blocked_gap_route_count": 5,
                "public_reinterpretation_exhausted": True,
                "internal_wetlab_or_primary_source_required": True,
                "authoritative_negative_apply_allowed_count": 0,
                "negative_evidence_closure_allowed": False,
                "claim_promotion_allowed": False,
            }
        },
    )

    summary = payload["summary"]
    assert summary["aqp1_negative_evidence_request_ready"] is True
    assert summary["aqp1_negative_evidence_request_artifact"] == "runs/aqp1_negative_evidence_request_packet_current.md"
    assert summary["aqp1_negative_evidence_request_source_gap_matrix_artifact"] == "runs/aqp1_negative_evidence_gap_matrix_current.md"
    assert summary["aqp1_negative_evidence_request_status"] == "ready_for_public_or_internal_exact_evidence_acquisition"
    assert summary["aqp1_negative_evidence_request_mode"] == "exact_target_pair_quantitative_negative_evidence_required"
    assert summary["aqp1_negative_evidence_request_row_count"] == 3
    assert summary["aqp1_negative_evidence_request_required_assignable_negative_row_count"] == 3
    assert summary["aqp1_negative_evidence_request_current_direct_negative_quantitative_row_found_count"] == 0
    assert summary["aqp1_negative_evidence_request_negative_slot_cover_ready_count"] == 0
    assert summary["aqp1_negative_evidence_request_negative_slot_cover_missing_count"] == 3
    assert summary["aqp1_negative_evidence_request_blocked_gap_route_count"] == 5
    assert summary["aqp1_negative_evidence_request_public_reinterpretation_exhausted"] is True
    assert summary["aqp1_negative_evidence_request_internal_wetlab_or_primary_source_required"] is True
    assert summary["aqp1_negative_evidence_request_authoritative_negative_apply_allowed_count"] == 0
    assert summary["aqp1_negative_evidence_request_negative_evidence_closure_allowed"] is False
    assert summary["aqp1_negative_evidence_request_claim_promotion_allowed"] is False
    assert any("AQP1 exact-evidence request packet" in item for item in summary["strengths"])
    assert any("AQP1 exact-evidence acquisition request" in item for item in summary["immediate_priority"])
    assert any("AQP1 now has an acquisition-ready" in item for item in summary["report_gaps"])
    assert any("Execute the AQP1 evidence request" in item for item in summary["fix_plan"])
    assert any("runs/aqp1_negative_evidence_request_packet_current.md" in item for item in summary["artifacts"])


def test_build_commercialization_status_report_exposes_aqp1_negative_evidence_intake_gate() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
                "strongest_ready_families": "kinase, ion_channel, gpcr",
                "aqp1_first_wave_primary_focus_ligand": "bacopaside II",
                "aqp1_exact_human_reference_ligand": "AqB013",
                "aqp1_first_wave_follow_on_lane_label": "core_binder_02/03",
                "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": "cytochalasin B",
            },
            "rows": [{"family": "transporter", "primary_blocker": "negative evidence", "claim_safe_scope": "local-only"}],
        },
        {"summary": {"highest_gap_family": "transporter"}},
        {"summary": {"next_required_step": "Keep transporter negative evidence parked."}},
        {"summary": {"placeholder_driven_rows": 6, "reducible_now_placeholder_rows": 0, "evidence_blocked_placeholder_rows": 6}},
        aqp1_negative_evidence_intake_gate_payload={
            "summary": {
                "intake_gate_ready": True,
                "packet_artifact": "runs/aqp1_negative_evidence_intake_gate_current.md",
                "request_artifact": "runs/aqp1_negative_evidence_request_packet_current.md",
                "template_csv_artifact": "runs/aqp1_negative_evidence_intake_template_current.csv",
                "intake_csv_artifact": "runs/aqp1_negative_evidence_intake_current.csv",
                "intake_status": "awaiting_exact_aqp1_quantitative_negative_evidence_rows",
                "intake_row_count": 3,
                "intake_row_with_data_count": 0,
                "valid_intake_row_count": 0,
                "required_assignable_negative_row_count": 3,
                "missing_valid_intake_row_count": 3,
                "validation_error_row_count": 3,
                "review_ready_row_count": 0,
                "intake_gate_complete": False,
                "split_reference_meta_update_required": False,
                "authoritative_negative_apply_allowed_count": 0,
                "negative_evidence_closure_allowed": False,
                "claim_promotion_allowed": False,
            }
        },
    )

    summary = payload["summary"]
    assert summary["aqp1_negative_evidence_intake_gate_ready"] is True
    assert summary["aqp1_negative_evidence_intake_gate_artifact"] == "runs/aqp1_negative_evidence_intake_gate_current.md"
    assert summary["aqp1_negative_evidence_intake_gate_request_artifact"] == "runs/aqp1_negative_evidence_request_packet_current.md"
    assert summary["aqp1_negative_evidence_intake_gate_template_artifact"] == "runs/aqp1_negative_evidence_intake_template_current.csv"
    assert summary["aqp1_negative_evidence_intake_gate_intake_artifact"] == "runs/aqp1_negative_evidence_intake_current.csv"
    assert summary["aqp1_negative_evidence_intake_gate_status"] == "awaiting_exact_aqp1_quantitative_negative_evidence_rows"
    assert summary["aqp1_negative_evidence_intake_gate_row_count"] == 3
    assert summary["aqp1_negative_evidence_intake_gate_row_with_data_count"] == 0
    assert summary["aqp1_negative_evidence_intake_gate_valid_intake_row_count"] == 0
    assert summary["aqp1_negative_evidence_intake_gate_required_assignable_negative_row_count"] == 3
    assert summary["aqp1_negative_evidence_intake_gate_missing_valid_intake_row_count"] == 3
    assert summary["aqp1_negative_evidence_intake_gate_validation_error_row_count"] == 3
    assert summary["aqp1_negative_evidence_intake_gate_review_ready_row_count"] == 0
    assert summary["aqp1_negative_evidence_intake_gate_complete"] is False
    assert summary["aqp1_negative_evidence_intake_gate_split_reference_meta_update_required"] is False
    assert summary["aqp1_negative_evidence_intake_gate_authoritative_negative_apply_allowed_count"] == 0
    assert summary["aqp1_negative_evidence_intake_gate_negative_evidence_closure_allowed"] is False
    assert summary["aqp1_negative_evidence_intake_gate_claim_promotion_allowed"] is False
    assert any("AQP1 negative-evidence intake gate" in item for item in summary["strengths"])
    assert any("AQP1 evidence intake gate" in item for item in summary["immediate_priority"])
    assert any("row-level intake validator" in item for item in summary["report_gaps"])
    assert any("AQP1 intake template" in item for item in summary["fix_plan"])
    assert any("runs/aqp1_negative_evidence_intake_gate_current.md" in item for item in summary["artifacts"])


def test_build_commercialization_status_report_exposes_wetlab_selected_allatom_burndown() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
                "strongest_ready_families": "kinase, ion_channel, gpcr",
                "aqp1_first_wave_primary_focus_ligand": "bacopaside II",
                "aqp1_exact_human_reference_ligand": "AqB013",
                "aqp1_first_wave_follow_on_lane_label": "core_binder_02/03",
                "glut1_second_wave_source_confirmation_packet_primary_focus_ligand": "cytochalasin B",
            },
            "rows": [{"family": "transporter", "primary_blocker": "negative evidence", "claim_safe_scope": "local-only"}],
        },
        {"summary": {"highest_gap_family": "transporter"}},
        {"summary": {"next_required_step": "Keep local-engine blockers first."}},
        {"summary": {"placeholder_driven_rows": 6, "reducible_now_placeholder_rows": 0, "evidence_blocked_placeholder_rows": 6}},
        {"summary": {"top_target_id": "AQP1", "top_packet_step": "core_non_binder_01"}},
        {"summary": {}},
        {
            "summary": {
                "top_priority_id": "nightly_reliability",
                "top_priority_status": "partial",
                "blocked_count": 1,
                "partial_count": 1,
                "parked_science_blocker_count": 1,
                "nightly_status_line": "stage6 gate still needs burndown",
                "viewer_status_line": "compare panes are keep-green",
                "wetlab_status_line": "send=5 ready | primary_exec=0 ready_now (attached; dispatch_complete) | antitarget_exec=1 ready_now (attached) | selected_allatom=fail",
                "wetlab_selected_allatom_gate_burndown_artifact": "runs/wetlab_selected_allatom_gate_burndown_packet_current.md",
                "wetlab_selected_allatom_target_id": "T. cruzi PDE",
                "wetlab_selected_allatom_focus_artifact": "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
                "wetlab_selected_allatom_primary_burndown_code": "recompute_mean_min_distance_A",
                "wetlab_selected_allatom_primary_burndown_metric": "mean_min_distance_A",
                "wetlab_selected_allatom_primary_burndown_value": "3.705",
                "wetlab_selected_allatom_primary_burndown_threshold": "2.500",
                "wetlab_selected_allatom_primary_burndown_delta": "1.205",
                "wetlab_selected_allatom_hard_block_count": 2,
                "wetlab_selected_allatom_semi_hard_block_count": 2,
            }
        },
    )

    summary = payload["summary"]
    assert summary["local_engine_queue_wetlab_selected_allatom_gate_burndown_artifact"] == "runs/wetlab_selected_allatom_gate_burndown_packet_current.md"
    assert summary["local_engine_queue_wetlab_selected_allatom_primary_burndown_code"] == "recompute_mean_min_distance_A"
    assert any("runs/wetlab_selected_allatom_gate_burndown_packet_current.md" in item for item in summary["immediate_priority"])
    assert any(item == "runs/wetlab_selected_allatom_gate_burndown_packet_current.md" for item in summary["artifacts"])


def test_closed_accounting_surfaces_post_goal_accuracy_parity_lane() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
                "strongest_ready_families": "kinase, ion_channel, gpcr",
            },
            "rows": [],
        },
        {
            "summary": {
                "highest_gap_family": "none_tracked_commercialization_gap",
                "tracked_gap_accounting_closed": True,
                "blocked_count": 0,
                "raw_blocked_bucket_count": 2,
                "parked_or_review_only_blocked_count": 2,
                "transporter_placeholder_accounting_closed": True,
                "aqp1_functional_kcal_surrogate_closure_allowed": True,
                "aqp1_functional_kcal_surrogate_ready_count": 3,
                "aqp1_direct_binding_gap_still_open": True,
            }
        },
        {
            "summary": {
                "all_tracked_family_accounting_closed": True,
                "transporter_negative_accounting_closed": True,
            }
        },
        {"summary": {"placeholder_driven_rows": 0, "reducible_now_placeholder_rows": 0, "evidence_blocked_placeholder_rows": 0}},
        {"summary": {"negative_evidence_closure_allowed": True}},
        {"summary": {}},
        {
            "summary": {
                "queue_clear": True,
                "top_priority_id": "nightly_reliability",
                "top_priority_status": "keep_green",
                "blocked_count": 0,
                "partial_count": 0,
                "keep_green_count": 5,
                "parked_science_blocker_count": 0,
            }
        },
        {"summary": {"delivery_ready": True, "verdict": "delivery_ready", "p0_blocker_count": 0, "hard_blocker_count": 0}},
        {
            "summary": {
                "packet_artifact": "runs/keep_green_regression_trend_packet_current.md",
                "commercial_trend_status": "sufficient_repeated_history",
                "all_current_green": True,
                "sufficient_repeated_history": True,
                "current_green_lane_count": 4,
                "lane_count": 4,
                "repeated_history_ready_lane_count": 4,
                "insufficient_history_lane_count": 0,
                "minimum_repeated_sample_count": 3,
                "nightly_recent_pass_streak": 4,
            }
        },
        {
            "summary": {
                "packet_artifact": "runs/platform_gap_taxonomy_packet_current.md",
                "platform_accounting_closed": True,
                "current_delivery_blocker_count": 0,
                "expansion_blocker_count": 0,
                "top_expansion_gap_id": "none_tracked_platform_expansion",
                "top_expansion_gap_class": "closed",
                "aqp1_functional_kcal_surrogate_closure_allowed": True,
                "aqp1_functional_kcal_surrogate_ready_count": 3,
                "aqp1_direct_binding_gap_still_open": True,
                "ca2_pxr_review_policy_closure_allowed": True,
                "ca2_pxr_review_only_policy_locked_row_count": 13,
            }
        },
        {"summary": {}},
        {"summary": {}},
        {"summary": {}},
        {"summary": {}},
        {"summary": {}},
        {"summary": {}},
        {
            "summary": {
                "status": "blocked_accuracy_parity",
                "overall_commercial_tool_accuracy_parity_allowed": False,
                "pass_row_count": 0,
                "restricted_pass_row_count": 1,
                "blocked_row_count": 4,
                "missing_row_count": 0,
                "current_broad_accuracy_parity_estimate_pct": "40-50",
                "current_broad_commercial_platform_estimate_pct": "35-45",
                "top_blockers": [
                    "physics_dynamics:openmm_reference_target_count_too_small",
                    "ligand_ranking:ranking_pr_auc_ci_low_below_threshold",
                ],
            }
        },
        {
            "summary": {
                "status": "open_a1_repair_queue",
                "top_priority_repair_id": "guarded_100k_claim_review_rerun",
                "top_priority_target": "gpcr_family_balanced",
                "top_priority_blocker_group": "claim_review",
                "open_queue_row_count": 1,
                "guarded_100k_rerun_allowed_now": True,
                "next_required_step": "Run the guarded 100k claim review rerun.",
            }
        },
        {
            "summary": {
                "status": "independent_repeat_ready_claim_locked",
                "independent_repeat_ready": True,
                "blocker_count": 0,
                "repeat_tag": "repeat_r2",
                "validate_command": "python3 tools/run_external_validation_blind_sets.py --tag repeat_r2 --validate-only",
                "run_command": "python3 tools/run_external_validation_blind_sets.py --tag repeat_r2",
            }
        },
    )

    summary = payload["summary"]
    assert summary["top_blocker_family"] == "none_tracked_commercialization_gap"
    assert summary["all_tracked_commercialization_accounting_closed"] is True
    assert summary["gap_active_blocked_count"] == 0
    assert summary["gap_raw_blocked_bucket_count"] == 2
    assert summary["gap_parked_or_review_only_blocked_count"] == 2
    assert summary["post_goal_accuracy_parity_active"] is True
    assert summary["accuracy_parity_status"] == "blocked_accuracy_parity"
    assert summary["accuracy_parity_blocked_row_count"] == 4
    assert summary["accuracy_parity_top_blockers"][0] == "physics_dynamics:openmm_reference_target_count_too_small"
    assert summary["gpcr_a1_accuracy_repair_queue_top_priority_repair_id"] == "guarded_100k_claim_review_rerun"
    assert summary["gpcr_a1_accuracy_repair_queue_guarded_100k_rerun_allowed_now"] is True
    assert summary["gpcr_a1_independent_repeat_ready"] is True
    assert summary["gpcr_a1_independent_repeat_completed"] is False
    assert summary["gpcr_a1_independent_repeat_result_passed"] is False
    assert summary["gpcr_a1_independent_repeat_claim_locked"] is True
    assert summary["gpcr_a1_independent_repeat_result_state"] == "ready_to_run"
    assert summary["gpcr_a1_independent_repeat_tag"] == "repeat_r2"
    assert any("post-goal accuracy-parity lane" in item for item in summary["immediate_priority"])
    assert any("gpcr_a1_accuracy_repair_queue_current.md" in item for item in summary["immediate_priority"])
    assert any("accuracy parity remains blocked" in item for item in summary["report_gaps"])
    assert any("guarded 100k claim review rerun" in item for item in summary["fix_plan"])
    assert any("runs/accuracy_parity_scorecard_current.md" in item for item in summary["artifacts"])
    assert "post-goal commercial-tool accuracy parity" in summary["next_required_step"]
