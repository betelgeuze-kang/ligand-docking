from __future__ import annotations

from tools.wetlab import build_wetlab_tcruzi_krs1_branch_review_surface as mod


def test_build_wetlab_tcruzi_krs1_branch_review_surface_uses_lrrk2_successor_contract() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "tcruzi_krs1_result_review_ready"}},
        {"summary": {"status": "completed"}},
        {"summary": {"status": "tcruzi_krs1_launch_packet_ready"}},
        {
            "summary": {
                "status": "wetlab_tcruzi_krs1_stage6_tuning_surface_ready",
                "recommended_observed_threshold_A": 5.05,
                "immediately_runnable_command_kind": "throughput_preflight_tuned_gate51",
                "next_required_step": "Run the T. cruzi KRS1 exploratory gate5.1 retry for 04_of_20; use gate5.1 as the immediately runnable family for the observed 5.05A band and keep the default lane closed until the result is reviewed.",
            }
        },
        {
            "summary": {
                "status": "wetlab_tcruzi_krs1_exploratory_retry_lane_ready",
                "lane_label": "exploratory_gate5.1_candidate",
                "selected_command_kind": "throughput_preflight_tuned_gate51",
                "selected_threshold_A": 5.1,
                "next_required_step": "Run the T. cruzi KRS1 exploratory gate5.1 retry for 04_of_20; use gate5.1 as the immediately runnable family for the observed 5.05A band and keep the default lane closed until the result is reviewed.",
                "shard_id": "04_of_20",
            }
        },
        {
            "summary": {
                "status": "wetlab_tcruzi_krs1_guarded_operator_packet_ready",
                "next_required_step": "Use the T. cruzi KRS1 guarded gate5.1 operator packet as the review unit for 04_of_20, keep the default lane closed, and review the gate5.1 exploratory retry before any reopen decision.",
            }
        },
        {
            "summary": {
                "status": "wetlab_tcruzi_krs1_guarded_branch_summary_ready",
                "branch_label": "tcruzi_krs1_guarded_gate51_branch",
                "branch_state": "guarded_gate51_review_default_lane_closed",
                "next_required_step": "Review T. cruzi KRS1 through the guarded gate5.1 branch for 04_of_20, keep the default lane closed, and do not reopen auto-start until the gate5.1 exploratory retry is explicitly resolved.",
            }
        },
        {"summary": {"status": "tcruzi_krs1_run_record_ready"}},
    )

    summary = payload["summary"]
    assert summary["branch_label"] == "tcruzi_krs1_guarded_gate51_branch"
    assert summary["branch_state"] == "guarded_gate51_review_default_lane_closed"
    assert summary["serialized_queue_rank"] == 4
    assert summary["serialized_run_order"] == "guarded_review_hold"
    assert summary["partner_track_id"] == "DNDi_Chagas_backup"
    assert summary["successor_target"] == "LRRK2"
    assert summary["successor_gate_state"] == "blocked_pending_tcruzi_krs1_guarded_review"
    assert summary["successor_gate_open"] is False
    assert "Run the T. cruzi KRS1 exploratory gate5.1 retry for 04_of_20" in summary["next_required_step"]

    rows = payload["rows"]
    branch_row = next(row for row in rows if row["row_kind"] == "branch_review_source")
    launch_row = next(row for row in rows if row["row_kind"] == "launch_packet_source")
    successor_row = next(row for row in rows if row["row_kind"] == "successor_gate")
    assert branch_row["source_artifact"] == "runs/wetlab_tcruzi_krs1_guarded_branch_summary_current.md"
    assert "resolves the serialized slot" not in branch_row["queue_phrase"]
    assert "Wave 2" not in launch_row["queue_phrase"]
    assert successor_row["source_artifact"] == "runs/lrrk2_launch_packet_current.md"
    assert successor_row["queue_phrase"] == "LRRK2 stays blocked behind T. cruzi KRS1 until the guarded review branch is cleared."


def test_build_wetlab_tcruzi_krs1_branch_review_surface_opens_lrrk2_when_guarded_branch_is_validated() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "tcruzi_krs1_result_review_ready"}},
        {"summary": {"status": "completed"}},
        {"summary": {"status": "tcruzi_krs1_launch_packet_ready"}},
        {
            "summary": {
                "status": "wetlab_tcruzi_krs1_stage6_tuning_surface_ready",
                "recommended_observed_threshold_A": 5.05,
                "immediately_runnable_command_kind": "throughput_preflight_tuned_gate51",
                "gate51_validation_row_count": 16,
                "gate51_validation_success_count": 16,
                "gate51_validation_all_post_hold_success": True,
                "gate51_validation_start_shard_id": "05_of_20",
                "gate51_validation_end_shard_id": "20_of_20",
                "gate51_validation_observed_metric_mean_A": 5.021,
            }
        },
        {
            "summary": {
                "status": "wetlab_tcruzi_krs1_exploratory_retry_lane_ready",
                "lane_label": "exploratory_gate5.1_candidate",
                "selected_command_kind": "throughput_preflight_tuned_gate51",
                "selected_threshold_A": 5.1,
                "next_required_step": "Keep the T. cruzi KRS1 default lane paused and refresh the stage6 tuning surface before retrying.",
                "shard_id": "09_of_20",
            }
        },
        {
            "summary": {
                "status": "wetlab_tcruzi_krs1_guarded_operator_packet_pending",
                "next_required_step": "Use the T. cruzi KRS1 guarded gate5.1 operator packet as the review unit for 09_of_20, keep the default lane closed, and review the gate5.1 exploratory retry before any reopen decision.",
            }
        },
        {
            "summary": {
                "status": "wetlab_tcruzi_krs1_guarded_branch_summary_validated",
                "branch_validated": True,
                "branch_label": "tcruzi_krs1_guarded_gate51_branch",
                "branch_state": "guarded_gate51_validated_default_lane_closed",
                "gate51_validation_row_count": 16,
                "gate51_validation_success_count": 16,
                "gate51_validation_all_post_hold_success": True,
                "gate51_validation_start_shard_id": "05_of_20",
                "gate51_validation_end_shard_id": "20_of_20",
                "gate51_validation_observed_metric_mean_A": 5.021,
                "next_required_step": "Promote T. cruzi KRS1 guarded gate5.1 as validated, keep the default lane closed, and allow LRRK2 to continue as the successor broad lane.",
            }
        },
        {"summary": {"status": "tcruzi_krs1_run_record_ready"}},
    )

    summary = payload["summary"]
    assert summary["branch_state"] == "guarded_gate51_validated_default_lane_closed"
    assert summary["decision_source_priority"] == "guarded_branch_summary"
    assert summary["serialized_run_order"] == "lrrk2_successor_continuation_allowed"
    assert summary["successor_gate_state"] == "open_for_lrrk2_execution"
    assert summary["successor_gate_open"] is True
    assert summary["branch_validated"] is True
    assert summary["gate51_validation_row_count"] == 16
    assert summary["gate51_validation_success_count"] == 16
    assert summary["gate51_validation_all_post_hold_success"] is True
    assert summary["gate51_validation_start_shard_id"] == "05_of_20"
    assert summary["gate51_validation_end_shard_id"] == "20_of_20"
    assert summary["gate51_validation_observed_metric_mean_A"] == 5.021
    assert "allow LRRK2 to continue" in summary["next_required_step"]

    decision_row = next(row for row in payload["rows"] if row["row_kind"] == "result_summary_source")
    launch_row = next(row for row in payload["rows"] if row["row_kind"] == "launch_packet_source")
    successor_row = next(row for row in payload["rows"] if row["row_kind"] == "successor_gate")
    assert decision_row["source_artifact"] == "runs/wetlab_tcruzi_krs1_guarded_branch_summary_current.md"
    assert "allows LRRK2 successor continuation" in launch_row["queue_phrase"]
    assert successor_row["queue_phrase"] == "LRRK2 may continue now that the T. cruzi KRS1 guarded gate5.1 branch is validated; keep the KRS1 default lane closed."
