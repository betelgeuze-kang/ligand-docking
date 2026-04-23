from __future__ import annotations

from tools import build_wetlab_dpre1_branch_review_surface as mod


def test_build_wetlab_dpre1_branch_review_surface_prefers_guarded_gate51_review_language() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "dpre1_result_review_ready", "serialized_queue_rank": 3}},
        {"summary": {"status": "completed"}},
        {"summary": {"status": "dpre1_launch_packet_ready"}},
        {
            "summary": {
                "status": "wetlab_dpre1_stage6_tuning_surface_ready",
                "recommended_observed_threshold_A": 5.05,
                "immediately_runnable_command_kind": "throughput_preflight_tuned_gate51",
                "next_required_step": "Run the DprE1 exploratory gate5.1 retry for 04_of_20; use gate5.1 as the immediately runnable family for the observed 5.05A band and keep the default lane closed until the result is reviewed.",
            }
        },
        {
            "summary": {
                "status": "wetlab_dpre1_exploratory_retry_lane_ready",
                "lane_label": "exploratory_gate5.1_candidate",
                "selected_command_kind": "throughput_preflight_tuned_gate51",
                "selected_threshold_A": 5.1,
                "next_required_step": "Run the DprE1 exploratory gate5.1 retry for 04_of_20; use gate5.1 as the immediately runnable family for the observed 5.05A band and keep the default lane closed until the result is reviewed.",
                "shard_id": "04_of_20",
            }
        },
        {
            "summary": {
                "status": "wetlab_dpre1_guarded_operator_packet_ready",
                "next_required_step": "Use the DprE1 guarded gate5.1 operator packet as the review unit for 04_of_20, keep the default lane closed, and review the tuned branch before any reopen decision.",
            }
        },
        {
            "summary": {
                "status": "wetlab_dpre1_guarded_branch_summary_ready",
                "branch_label": "dpre1_guarded_tuned_branch",
                "branch_state": "guarded_tuned_branch_review_default_lane_closed",
                "next_required_step": "Review DprE1 through the guarded tuned branch for 04_of_20, keep the default lane closed, and do not reopen auto-start until the tuned review is explicitly resolved.",
            }
        },
        {"summary": {"status": "dpre1_run_record_ready"}},
    )

    summary = payload["summary"]
    assert summary["branch_label"] == "dpre1_guarded_tuned_branch"
    assert summary["branch_state"] == "guarded_tuned_branch_review_default_lane_closed"
    assert summary["serialized_run_order"] == "guarded_review_hold"
    assert "Run the DprE1 exploratory gate5.1 retry for 04_of_20" in summary["next_required_step"]

    rows = payload["rows"]
    branch_row = next(row for row in rows if row["row_kind"] == "branch_review_source")
    launch_row = next(row for row in rows if row["row_kind"] == "launch_packet_source")
    successor_row = next(row for row in rows if row["row_kind"] == "successor_gate")
    assert branch_row["source_artifact"] == "runs/wetlab_dpre1_guarded_branch_summary_current.md"
    assert "resolves the serialized slot" not in branch_row["queue_phrase"]
    assert "Wave 2" not in launch_row["queue_phrase"]
    assert "resolved DprE1 review" not in successor_row["queue_phrase"]
