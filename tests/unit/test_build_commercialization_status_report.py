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
    )

    summary = payload["summary"]
    assert summary["local_engine_queue_clear"] is True
    assert summary["local_engine_queue_keep_green_count"] == 4
    assert summary["local_delivery_ready"] is True
    assert summary["local_delivery_verdict"] == "delivery_ready"
    assert any("keep-green board" in item for item in summary["immediate_priority"])
    assert any("Local delivery verdict is `delivery_ready`" in item for item in summary["immediate_priority"])
    assert any("nightly gate regression artifact" in item for item in summary["immediate_priority"])
    assert not any("Burn down engine blockers" in item for item in summary["immediate_priority"])
    assert not any("burndown packet: tune" in item for item in summary["immediate_priority"])
    assert any("restricted local scope" in item for item in summary["report_gaps"])
    assert any("recurrent canonical nightly" in item for item in summary["fix_plan"])


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
                "aqp1_negative_acquisition_artifact": "runs/aqp1_negative_evidence_acquisition_packet_current.md",
                "aqp1_negative_acquisition_primary_query_label": "pressure_induced_hemolysis_reinvestigation",
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
    assert any("runs/aqp1_negative_evidence_acquisition_packet_current.md" in item for item in summary["immediate_priority"])


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
