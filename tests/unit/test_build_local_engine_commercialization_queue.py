from __future__ import annotations

from tools import build_local_engine_commercialization_queue as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_local_engine_commercialization_queue() -> None:
    payload = mod.build_payload(
        latest_nightly_payload={
            "pass": False,
            "failed_stage": "smoke",
            "generated_at_local": "2026-04-20T19:13:16",
            "service_result": {"error_code": "HTVS_SMOKE_FAILED"},
            "stages": {
                "smoke": {
                    "failed_stage": "stage2_trajectory_generation",
                    "stages": {
                        "stage2_trajectory_generation": {
                            "returncode": 1,
                        }
                    },
                }
            },
        },
        latest_nightly_artifact="runs/ligand_htvs_nightly_2026-04-20_summary.json",
        import_anchor={
            "artifact": "runs/ligand_htvs_nightly_2026-04-17_smoke_summary.json",
            "generated_at_local": "2026-04-17T22:15:29",
            "failed_stage": "stage1_ligand_mapping",
            "stderr_tail": "ModuleNotFoundError: No module named 'core'",
        },
        recent_nightly_payloads=[
            {
                "pass": False,
                "failed_stage": "smoke",
                "stages": {"smoke": {"failed_stage": "stage2_trajectory_generation"}},
            },
            {
                "pass": False,
                "failed_stage": "smoke",
                "stages": {"smoke": {"failed_stage": "stage2_trajectory_generation"}},
            },
            {
                "pass": False,
                "failed_stage": "smoke",
                "stages": {"smoke": {"failed_stage": "stage1_ligand_mapping"}},
            },
        ],
        nightly_gate_payload={},
        nightly_tuning_payload={},
        nightly_followup_payload={},
        nightly_probe_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_probe_result_packet_current.md",
                "primary_probe_row_key": "HIV1_PROTEASE::aspirin",
                "projected_gate_mean_min_distance_A": 2.2686680442094804,
                "projected_gate_pass": True,
            }
        },
        nightly_promotion_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_probe_promotion_packet_current.md",
                "primary_promoted_row_key": "HIV1_PROTEASE::aspirin",
                "primary_canonical_fallback_preset_id": "target_forced_adress_uncapped_probe",
                "projected_gate_pass": True,
                "canonical_retry_lane_ready": True,
            }
        },
        nightly_realization_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_realization_packet_current.md",
                "primary_realization_row_key": "HIV1_PROTEASE::aspirin",
                "primary_canonical_retry_preset_id": "target_forced_adress_uncapped_probe",
                "realized_gate_mean_min_distance_A": 2.2707623770833014,
                "realized_gate_pass": True,
                "realization_ready": True,
            }
        },
        viewer_payload={
            "overall_ok": True,
            "geometry_access": {
                "single_canvas_probe_ready": False,
                "compareA_canvas_probe_ready": False,
                "compareB_canvas_probe_ready": False,
                "single_wrapper_gap": True,
                "compareA_wrapper_gap": True,
                "compareB_wrapper_gap": True,
            },
            "geometry_probe_compact": {
                "single": {"renderable_count": 0},
                "compareA": {"renderable_count": 0},
                "compareB": {"renderable_count": 0},
            },
        },
        wetlab_dashboard_payload={
            "broad_screen_primary_watch_liveness": "stale",
            "broad_screen_antitarget_watch_liveness": "detached",
            "selected_allatom_wetlab_gate_pass": False,
        },
        wetlab_final_payload={
            "ready_to_send_track_count": 5,
            "broad_screen_execution_ready_now_row_count": 0,
        },
        wetlab_readiness_payload={
            "summary": {
                "blocked_row_count": 3,
                "partial_row_count": 1,
                "ready_row_count": 1,
                "measured_assay_artifact_count": 0,
                "status_line": (
                    "send=5 ready | primary_exec=0 ready_now (stale) | antitarget_exec=1 ready_now (detached) | "
                    "selected_allatom=fail | measured_assays=0"
                ),
                "next_required_step": "Recover the primary dispatch lane before treating wetlab as execution-ready.",
            }
        },
        refresh_payload={
            "overall_ok": True,
            "ok_count": 103,
            "step_count": 103,
            "first_failed_step": "",
        },
        negative_queue_payload={
            "summary": {
                "row_count": 6,
                "top_target_id": "AQP1",
                "top_packet_step": "core_non_binder_01",
                "placeholder_driven_rows_remaining": 6,
            }
        },
        gap_payload={
            "summary": {
                "highest_gap_family": "transporter",
            }
        },
    )

    summary = payload["summary"]
    assert summary["local_only_mode"] is True
    assert summary["row_count"] == 5
    assert summary["blocked_count"] == 2
    assert summary["partial_count"] == 1
    assert summary["keep_green_count"] == 1
    assert summary["parked_science_blocker_count"] == 1
    assert summary["top_priority_id"] == "nightly_reliability"
    rows = {row["blocker_id"]: row for row in payload["rows"]}
    assert rows["nightly_reliability"]["status"] == "blocked"
    assert rows["viewer_usability"]["status"] == "partial"
    assert rows["wetlab_execution_readiness"]["status"] == "blocked"
    assert rows["local_reproducibility_guardrail"]["status"] == "keep_green"
    assert rows["transporter_science_blocker"]["status"] == "parked"
    _contains_tokens(
        rows["nightly_reliability"]["source_signal"],
        "stage2_trajectory_generation",
        "htvs_smoke_failed",
        "import_anchor=2026-04-17t22:15:29",
    )
    _contains_tokens(
        rows["viewer_usability"]["source_signal"],
        "single_canvas_probe_ready=false",
        "single_wrapper_gap=true",
        "single_renderables=0",
    )
    _contains_tokens(
        rows["wetlab_execution_readiness"]["source_signal"],
        "primary_exec=0 ready_now (stale)",
        "antitarget_exec=1 ready_now (detached)",
        "blocked_row_count=3",
    )
    _contains_tokens(
        summary["next_required_step"],
        "nightly reliability",
        "viewer mesh/canvas gap",
        "wetlab execution readiness",
        "transporter negative-evidence mining parked",
    )
    _contains_tokens(
        rows["nightly_reliability"]["next_required_action"],
        "nightly_stage6_probe_result_packet_current.md",
        "nightly_stage6_probe_promotion_packet_current.md",
    )
    _contains_tokens(summary["viewer_status_line"], "unavailable")
    _contains_tokens(summary["wetlab_status_line"], "send=5 ready", "primary_exec=0", "antitarget_exec=1", "measured_assays=0")


def test_build_local_engine_commercialization_queue_marks_stage6_gate_failure_as_partial() -> None:
    payload = mod.build_payload(
        latest_nightly_payload={
            "pass": False,
            "failed_stage": "stage6_operational_gate",
            "generated_at_local": "2026-04-21T21:38:48",
            "service_result": {"error_code": "HTVS_GATE_FAILED"},
            "stages": {
                "stage2_trajectory_generation": {
                    "ok": True,
                    "returncode": 0,
                },
                "stage6_operational_gate": {
                    "pass": False,
                    "failed_metrics": [
                        {
                            "metric": "mean_min_distance_A",
                            "value": 2.655165582969785,
                            "threshold": 2.5,
                        }
                    ],
                },
            },
        },
        latest_nightly_artifact="runs/ligand_htvs_nightly_2026-04-21_summary.json",
        import_anchor={
            "artifact": "runs/ligand_htvs_nightly_2026-04-17_smoke_summary.json",
            "generated_at_local": "2026-04-17T22:15:29",
            "failed_stage": "stage1_ligand_mapping",
            "stderr_tail": "ModuleNotFoundError: No module named 'core'",
        },
        recent_nightly_payloads=[
            {
                "pass": False,
                "failed_stage": "stage2_trajectory_generation",
                "service_result": {"error_code": "HTVS_SMOKE_FAILED"},
            },
            {
                "pass": False,
                "failed_stage": "stage2_trajectory_generation",
                "service_result": {"error_code": "HTVS_SMOKE_FAILED"},
            },
            {
                "pass": False,
                "failed_stage": "stage6_operational_gate",
                "service_result": {"error_code": "HTVS_GATE_FAILED"},
            },
        ],
        nightly_gate_payload={
            "summary": {
                "packet_artifact": "runs/nightly_gate_burndown_packet_current.md",
                "status": "nightly_gate_burndown_ready",
                "status_line": (
                    "stage2 is recovered and the nightly lane is now burning down the stage6 gate at "
                    "mean_min_distance_A=2.655 versus 2.500 (+0.155 over threshold)."
                ),
                "primary_gate_metric": "mean_min_distance_A",
                "primary_gate_value": 2.655165582969785,
                "primary_gate_threshold": 2.5,
                "primary_gate_delta": 0.15516558296978494,
                "recent_transition_line": "2026-04-19:stage2_trajectory_generation -> 2026-04-20:stage2_trajectory_generation -> 2026-04-21:stage6_operational_gate",
                "recent_stage6_fail_count": 1,
                "next_required_step": (
                    "Keep stage2 recovered and tune the stage6 operational gate via "
                    "`runs/nightly_gate_burndown_packet_current.md`: move `mean_min_distance_A` down by `0.155` "
                    "from `2.655` to at most `2.500` while recent stage6 fails stay at `1/3`."
                ),
            }
        },
        nightly_tuning_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_tuning_packet_current.md",
                "topk_equals_full_unique_band": True,
                "rows_above_threshold_count": 3,
                "minimum_rows_to_touch_if_clamped_to_threshold": 3,
                "primary_focus_row_key": "EGFR_KINASE::aspirin",
            }
        },
        nightly_followup_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_followup_retry_packet_current.md",
                "primary_execution_focus_row_key": "EGFR_KINASE::aspirin",
                "retry_row_count": 2,
                "closure_row_count": 2,
            }
        },
        nightly_sweep_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_tuning_sweep_packet_current.md",
                "primary_focus_row_key": "HIV1_PROTEASE::imatinib",
                "primary_preset_id": "anchor_replay_baseline",
                "sweep_preset_row_count": 6,
                "retry_subset_queue_count": 2,
            }
        },
        nightly_probe_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_probe_result_packet_current.md",
                "primary_probe_row_key": "HIV1_PROTEASE::aspirin",
                "projected_gate_mean_min_distance_A": 2.2686680442094804,
                "projected_gate_pass": True,
            }
        },
        nightly_promotion_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_probe_promotion_packet_current.md",
                "primary_promoted_row_key": "HIV1_PROTEASE::aspirin",
                "primary_canonical_fallback_preset_id": "target_forced_adress_uncapped_probe",
                "projected_gate_pass": True,
                "canonical_retry_lane_ready": True,
            }
        },
        nightly_realization_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_realization_packet_current.md",
                "primary_realization_row_key": "HIV1_PROTEASE::aspirin",
                "primary_canonical_retry_preset_id": "target_forced_adress_uncapped_probe",
                "realized_gate_mean_min_distance_A": 2.2707623770833014,
                "realized_gate_pass": True,
                "realization_ready": True,
            }
        },
        nightly_rescored_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_rescored_gate_packet_current.md",
                "primary_applied_row_key": "HIV1_PROTEASE::aspirin",
                "primary_canonical_retry_preset_id": "target_forced_adress_uncapped_probe",
                "rescored_gate_mean_min_distance_A": 2.2707623770833014,
                "rescored_gate_pass": True,
                "downstream_rerun_ready": True,
            }
        },
        nightly_downstream_rerun_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_downstream_rerun_packet_current.md",
                "primary_focus_row_key": "HIV1_PROTEASE::aspirin",
                "primary_canonical_retry_preset_id": "target_forced_adress_uncapped_probe",
                "target_subset": "EGFR_KINASE,HIV1_PROTEASE",
                "downstream_profile_json_artifact": "runs/nightly_stage6_downstream_rerun_profile_current.json",
                "dry_run_status_json_artifact": "runs/nightly_stage6_downstream_rerun_current_status.json",
                "downstream_rerun_ready": True,
                "dry_run_status_present": True,
                "dry_run_command_validated": True,
                "dry_run_payload_pass": True,
            }
        },
        nightly_execute_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_execute_result_packet_current.md",
                "primary_focus_row_key": "HIV1_PROTEASE::aspirin",
                "primary_canonical_retry_preset_id": "target_forced_adress_uncapped_probe",
                "target_subset": "EGFR_KINASE,HIV1_PROTEASE",
                "execute_status_json_artifact": "runs/nightly_stage6_downstream_execute_current_status.json",
                "execute_pipeline_summary_json_artifact": "runs/nightly_stage6_downstream_execute_current_summary.json",
                "execute_gate_mean_min_distance_A": 2.268931970372796,
                "execute_gate_pass": True,
                "execute_payload_pass": True,
                "execute_matches_rescored_gate": True,
            }
        },
        viewer_payload={
            "overall_ok": True,
            "compare_writeback_geometry_status_line": "single=canvas missing · renderables 0",
        },
        wetlab_dashboard_payload={
            "broad_screen_primary_watch_liveness": "stale",
            "broad_screen_antitarget_watch_liveness": "detached",
            "selected_allatom_wetlab_gate_pass": False,
        },
        wetlab_final_payload={
            "ready_to_send_track_count": 5,
            "broad_screen_execution_ready_now_row_count": 0,
        },
        wetlab_readiness_payload={
            "summary": {
                "blocked_row_count": 3,
                "partial_row_count": 1,
                "ready_row_count": 1,
                "measured_assay_artifact_count": 0,
                "status_line": (
                    "send=5 ready | primary_exec=0 ready_now (stale) | antitarget_exec=1 ready_now (detached) | "
                    "selected_allatom=fail | measured_assays=0"
                ),
                "next_required_step": "Recover the primary dispatch lane before treating wetlab as execution-ready.",
            }
        },
        refresh_payload={
            "overall_ok": True,
            "ok_count": 104,
            "step_count": 104,
            "first_failed_step": "",
        },
        negative_queue_payload={
            "summary": {
                "row_count": 6,
                "top_target_id": "AQP1",
                "top_packet_step": "core_non_binder_01",
                "placeholder_driven_rows_remaining": 6,
            }
        },
        gap_payload={
            "summary": {
                "highest_gap_family": "transporter",
            }
        },
    )

    summary = payload["summary"]
    rows = {row["blocker_id"]: row for row in payload["rows"]}
    assert summary["blocked_count"] == 1
    assert summary["partial_count"] == 2
    assert rows["nightly_reliability"]["status"] == "partial"
    _contains_tokens(
        rows["nightly_reliability"]["source_signal"],
        "latest_failed_stage=stage6_operational_gate",
        "latest_error_code=htvs_gate_failed",
        "stage2_ok=true",
        "stage6_gate_metric=mean_min_distance_a",
        "stage6_gate_burndown_artifact=runs/nightly_gate_burndown_packet_current.md",
        "stage6_tuning_artifact=runs/nightly_stage6_tuning_packet_current.md",
        "stage6_tuning_rows_above_threshold=3",
        "stage6_followup_artifact=runs/nightly_stage6_followup_retry_packet_current.md",
        "stage6_followup_retry_rows=2",
        "stage6_sweep_artifact=runs/nightly_stage6_tuning_sweep_packet_current.md",
        "stage6_sweep_preset_rows=6",
        "stage6_probe_artifact=runs/nightly_stage6_probe_result_packet_current.md",
        "stage6_probe_projected_gate_pass=true",
        "stage6_promotion_artifact=runs/nightly_stage6_probe_promotion_packet_current.md",
        "stage6_promotion_primary_preset=target_forced_adress_uncapped_probe",
        "stage6_promotion_projected_gate_pass=true",
        "stage6_promotion_lane_ready=true",
        "stage6_realization_artifact=runs/nightly_stage6_realization_packet_current.md",
        "stage6_realization_primary_preset=target_forced_adress_uncapped_probe",
        "stage6_realization_gate_pass=true",
        "stage6_realization_ready=true",
        "stage6_rescored_artifact=runs/nightly_stage6_rescored_gate_packet_current.md",
        "stage6_rescored_primary_preset=target_forced_adress_uncapped_probe",
        "stage6_rescored_gate_pass=true",
        "stage6_rescored_rerun_ready=true",
        "stage6_downstream_rerun_artifact=runs/nightly_stage6_downstream_rerun_packet_current.md",
        "stage6_downstream_rerun_primary_preset=target_forced_adress_uncapped_probe",
        "stage6_downstream_rerun_target_subset=egfr_kinase,hiv1_protease",
        "stage6_downstream_rerun_dry_run_validated=true",
        "stage6_downstream_rerun_dry_run_payload_pass=true",
        "stage6_execute_artifact=runs/nightly_stage6_execute_result_packet_current.md",
        "stage6_execute_status_artifact=runs/nightly_stage6_downstream_execute_current_status.json",
        "stage6_execute_gate_pass=true",
        "stage6_execute_payload_pass=true",
    )
    _contains_tokens(
        rows["nightly_reliability"]["source_signal"],
        "stage6_execute_status_artifact=runs/nightly_stage6_downstream_execute_current_status.json",
        "stage6_execute_payload_pass=true",
    )
    _contains_tokens(
        summary["nightly_status_line"],
        "stage2 is recovered",
        "mean_min_distance_a=2.655",
        "2.500",
    )
    _contains_tokens(
        summary["next_required_step"],
        "recovered nightly writer/import path green",
        "nightly_gate_burndown_packet_current.md",
        "mean_min_distance_a",
        "nightly_stage6_followup_retry_packet_current.md",
        "nightly_stage6_tuning_sweep_packet_current.md",
        "nightly_stage6_rescored_gate_packet_current.md",
        "nightly_stage6_downstream_rerun_packet_current.md",
        "nightly_stage6_execute_result_packet_current.md",
    )
    assert summary["nightly_gate_burndown_ready"] is True
    _contains_tokens(summary["nightly_gate_burndown_artifact"], "nightly_gate_burndown_packet_current.md")
    _contains_tokens(summary["nightly_gate_primary_metric"], "mean_min_distance_a")
    _contains_tokens(summary["nightly_gate_next_required_step"], "nightly_gate_burndown_packet_current.md", "1/3")
    assert summary["nightly_stage6_tuning_ready"] is True
    _contains_tokens(summary["nightly_stage6_tuning_artifact"], "nightly_stage6_tuning_packet_current.md")
    _contains_tokens(summary["nightly_stage6_tuning_primary_focus_row_key"], "egfr_kinase::aspirin")
    assert summary["nightly_stage6_followup_ready"] is True
    _contains_tokens(summary["nightly_stage6_followup_artifact"], "nightly_stage6_followup_retry_packet_current.md")
    _contains_tokens(summary["nightly_stage6_followup_primary_focus_row_key"], "egfr_kinase::aspirin")
    assert summary["nightly_stage6_sweep_ready"] is True
    _contains_tokens(summary["nightly_stage6_sweep_artifact"], "nightly_stage6_tuning_sweep_packet_current.md")
    _contains_tokens(summary["nightly_stage6_sweep_primary_focus_row_key"], "hiv1_protease::imatinib")
    _contains_tokens(summary["nightly_stage6_sweep_primary_preset_id"], "anchor_replay_baseline")
    assert summary["nightly_stage6_probe_ready"] is True
    _contains_tokens(summary["nightly_stage6_probe_artifact"], "nightly_stage6_probe_result_packet_current.md")
    _contains_tokens(summary["nightly_stage6_probe_primary_focus_row_key"], "hiv1_protease::aspirin")
    assert summary["nightly_stage6_probe_projected_gate_pass"] is True
    assert summary["nightly_stage6_promotion_ready"] is True
    _contains_tokens(summary["nightly_stage6_promotion_artifact"], "nightly_stage6_probe_promotion_packet_current.md")
    _contains_tokens(summary["nightly_stage6_promotion_primary_focus_row_key"], "hiv1_protease::aspirin")
    _contains_tokens(summary["nightly_stage6_promotion_primary_preset_id"], "target_forced_adress_uncapped_probe")
    assert summary["nightly_stage6_promotion_projected_gate_pass"] is True
    assert summary["nightly_stage6_promotion_canonical_retry_lane_ready"] is True
    assert summary["nightly_stage6_realization_ready"] is True
    _contains_tokens(summary["nightly_stage6_realization_artifact"], "nightly_stage6_realization_packet_current.md")
    _contains_tokens(summary["nightly_stage6_realization_primary_focus_row_key"], "hiv1_protease::aspirin")
    _contains_tokens(summary["nightly_stage6_realization_primary_preset_id"], "target_forced_adress_uncapped_probe")
    assert summary["nightly_stage6_realization_gate_pass"] is True
    assert summary["nightly_stage6_rescored_gate_ready"] is True
    _contains_tokens(summary["nightly_stage6_rescored_gate_artifact"], "nightly_stage6_rescored_gate_packet_current.md")
    _contains_tokens(summary["nightly_stage6_rescored_gate_primary_focus_row_key"], "hiv1_protease::aspirin")
    _contains_tokens(summary["nightly_stage6_rescored_gate_primary_preset_id"], "target_forced_adress_uncapped_probe")
    assert summary["nightly_stage6_rescored_gate_pass"] is True
    assert summary["nightly_stage6_rescored_gate_packet_ready"] is True
    assert summary["nightly_stage6_downstream_rerun_ready"] is True
    _contains_tokens(summary["nightly_stage6_downstream_rerun_artifact"], "nightly_stage6_downstream_rerun_packet_current.md")
    _contains_tokens(summary["nightly_stage6_downstream_rerun_primary_focus_row_key"], "hiv1_protease::aspirin")
    _contains_tokens(summary["nightly_stage6_downstream_rerun_primary_preset_id"], "target_forced_adress_uncapped_probe")
    _contains_tokens(summary["nightly_stage6_downstream_rerun_target_subset"], "egfr_kinase,hiv1_protease")
    _contains_tokens(summary["nightly_stage6_downstream_rerun_profile_json_artifact"], "nightly_stage6_downstream_rerun_profile_current.json")
    _contains_tokens(summary["nightly_stage6_downstream_rerun_dry_run_status_artifact"], "nightly_stage6_downstream_rerun_current_status.json")
    assert summary["nightly_stage6_downstream_rerun_dry_run_validated"] is True
    assert summary["nightly_stage6_downstream_rerun_payload_pass"] is True
    _contains_tokens(summary["nightly_stage6_execute_artifact"], "nightly_stage6_execute_result_packet_current.md")
    _contains_tokens(summary["nightly_stage6_execute_primary_focus_row_key"], "hiv1_protease::aspirin")
    _contains_tokens(summary["nightly_stage6_execute_primary_preset_id"], "target_forced_adress_uncapped_probe")
    _contains_tokens(summary["nightly_stage6_execute_target_subset"], "egfr_kinase,hiv1_protease")
    _contains_tokens(summary["nightly_stage6_execute_status_json_artifact"], "nightly_stage6_downstream_execute_current_status.json")
    _contains_tokens(summary["nightly_stage6_execute_pipeline_summary_json_artifact"], "nightly_stage6_downstream_execute_current_summary.json")
    assert summary["nightly_stage6_execute_gate_pass"] is True
    assert summary["nightly_stage6_execute_payload_pass"] is True
    assert summary["nightly_stage6_execute_matches_rescored_gate"] is True


def test_build_local_engine_commercialization_queue_promotes_viewer_to_keep_green_when_mesh_proof_is_present() -> None:
    payload = mod.build_payload(
        latest_nightly_payload={
            "pass": False,
            "failed_stage": "stage6_operational_gate",
            "generated_at_local": "2026-04-22T22:41:00",
            "service_result": {"error_code": "HTVS_GATE_FAILED"},
            "stages": {
                "stage2_trajectory_generation": {"ok": True, "returncode": 0},
                "stage6_operational_gate": {
                    "pass": False,
                    "failed_metrics": [
                        {
                            "metric": "mean_min_distance_A",
                            "value": 2.656,
                            "threshold": 2.5,
                        }
                    ],
                },
            },
        },
        latest_nightly_artifact="runs/ligand_htvs_nightly_2026-04-22_summary.json",
        import_anchor={},
        recent_nightly_payloads=[{"pass": False, "failed_stage": "stage6_operational_gate"}],
        nightly_gate_payload={
            "summary": {
                "packet_artifact": "runs/nightly_gate_burndown_packet_current.md",
                "status_line": (
                    "stage2 is recovered and the nightly lane is now burning down the stage6 gate at "
                    "mean_min_distance_A=2.656 versus 2.500 (+0.156 over threshold)."
                ),
                "primary_gate_metric": "mean_min_distance_A",
                "primary_gate_delta": 0.156,
            }
        },
        nightly_tuning_payload={},
        nightly_followup_payload={},
        viewer_payload={
            "overall_ok": True,
            "summary": {
                "compare_writeback_compare_pane_state_rep_count": 2,
                "compare_writeback_wrapper_gap_count": 0,
                "compare_writeback_mesh_probe_unavailable_count": 0,
                "compare_writeback_geometry_burndown_status_line": (
                    "compare writeback smoke passes and both compare panes now expose mesh-backed geometry proof with no wrapper gaps."
                ),
            },
            "geometry_access": {
                "compare_writeback": {
                    "single_canvas_probe_ready": True,
                    "compareA_canvas_probe_ready": True,
                    "compareB_canvas_probe_ready": True,
                    "single_wrapper_gap": False,
                    "compareA_wrapper_gap": False,
                    "compareB_wrapper_gap": False,
                }
            },
            "geometry_probe": {
                "compare_writeback": {
                    "single": {"renderable_count": 0},
                    "compareA": {"renderable_count": 9},
                    "compareB": {"renderable_count": 9},
                }
            },
        },
        wetlab_dashboard_payload={
            "broad_screen_primary_watch_liveness": "stale",
            "broad_screen_antitarget_watch_liveness": "detached",
            "selected_allatom_wetlab_gate_pass": False,
        },
        wetlab_final_payload={
            "ready_to_send_track_count": 5,
            "broad_screen_execution_ready_now_row_count": 0,
        },
        wetlab_readiness_payload={
            "summary": {
                "blocked_row_count": 3,
                "partial_row_count": 1,
                "ready_row_count": 1,
                "status_line": (
                    "send=5 ready | primary_exec=0 ready_now (stale) | antitarget_exec=1 ready_now (detached) | "
                    "selected_allatom=fail"
                ),
            }
        },
        refresh_payload={
            "overall_ok": True,
            "ok_count": 115,
            "step_count": 115,
            "first_failed_step": "",
        },
        negative_queue_payload={
            "summary": {
                "row_count": 6,
                "top_target_id": "AQP1",
                "top_packet_step": "core_non_binder_01",
                "placeholder_driven_rows_remaining": 6,
            }
        },
        gap_payload={"summary": {"highest_gap_family": "transporter"}},
    )

    rows = {row["blocker_id"]: row for row in payload["rows"]}
    viewer = rows["viewer_usability"]
    assert viewer["status"] == "keep_green"
    _contains_tokens(viewer["status_line"], "mesh-backed geometry proof", "no wrapper gaps")
    _contains_tokens(viewer["next_required_action"], "regression guardrail")
    _contains_tokens(payload["summary"]["next_required_step"], "keep the viewer mesh-backed compare-pane proof green")


def test_build_local_engine_commercialization_queue_exposes_selected_allatom_burndown_packet() -> None:
    payload = mod.build_payload(
        latest_nightly_payload={"pass": True},
        latest_nightly_artifact="runs/ligand_htvs_nightly_2026-04-23_summary.json",
        import_anchor={},
        recent_nightly_payloads=[{"pass": True}],
        nightly_gate_payload={},
        nightly_tuning_payload={},
        nightly_followup_payload={},
        viewer_payload={"overall_ok": True},
        wetlab_dashboard_payload={
            "summary": {
                "broad_screen_primary_watch_liveness": "attached",
                "broad_screen_antitarget_watch_liveness": "attached",
                "selected_allatom_wetlab_gate_pass": False,
            }
        },
        wetlab_final_payload={"summary": {"ready_to_send_track_count": 5, "broad_screen_execution_ready_now_row_count": 0}},
        wetlab_readiness_payload={
            "summary": {
                "blocked_count": 1,
                "partial_count": 0,
                "ready_count": 4,
                "status_line": "send=5 ready | primary_exec=0 ready_now (attached; dispatch_complete) | antitarget_exec=1 ready_now (attached) | selected_allatom=fail",
                "next_required_step": "Keep the completed primary dispatch lane warm and clear the selected all-atom wetlab gate while keeping both watch loops attached.",
            }
        },
        wetlab_selected_allatom_payload={
            "summary": {
                "packet_artifact": "runs/wetlab_selected_allatom_gate_burndown_packet_current.md",
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_focus_artifact": "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
                "primary_burndown_code": "recompute_mean_min_distance_A",
                "primary_burndown_metric": "mean_min_distance_A",
                "primary_burndown_value": "3.705",
                "primary_burndown_threshold": "2.500",
                "primary_burndown_delta": "1.205",
                "hard_block_count": 2,
                "semi_hard_block_count": 2,
                "missing_metric_count": 1,
            }
        },
        refresh_payload={"overall_ok": True, "ok_count": 115, "step_count": 115},
        negative_queue_payload={"summary": {"row_count": 6, "top_target_id": "AQP1", "top_packet_step": "core_non_binder_01"}},
        gap_payload={"summary": {"highest_gap_family": "transporter"}},
    )

    wetlab_row = {row["blocker_id"]: row for row in payload["rows"]}["wetlab_execution_readiness"]
    assert wetlab_row["source_artifact"] == "runs/wetlab_selected_allatom_gate_burndown_packet_current.md"
    _contains_tokens(
        wetlab_row["source_signal"],
        "selected_allatom_primary_burndown_code=recompute_mean_min_distance_a",
        "selected_allatom_primary_burndown_delta=1.205",
        "selected_allatom_hard_block_count=2",
    )
    _contains_tokens(
        wetlab_row["next_required_action"],
        "wetlab_selected_allatom_gate_burndown_packet_current.md",
        "recompute_mean_min_distance_a",
        "claim/equivalence",
    )
    summary = payload["summary"]
    assert summary["wetlab_selected_allatom_gate_burndown_artifact"] == "runs/wetlab_selected_allatom_gate_burndown_packet_current.md"
    assert summary["wetlab_selected_allatom_primary_burndown_code"] == "recompute_mean_min_distance_A"
    assert summary["wetlab_selected_allatom_primary_burndown_delta"] == "1.205"
