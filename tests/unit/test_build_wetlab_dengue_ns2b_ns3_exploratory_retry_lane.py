from __future__ import annotations

from tools import build_wetlab_dengue_ns2b_ns3_exploratory_retry_lane as mod


def test_build_wetlab_dengue_ns2b_ns3_exploratory_retry_lane_prefers_gate45() -> None:
    payload = mod.build_payload(
        hold_guard_payload={
            "summary": {"guard_limit": 3},
            "rows": [
                {
                    "target_id": "Dengue NS2B-NS3 protease",
                    "recommended_policy_action": "pause_target_autostart_and_review_retry_preset",
                    "recent_consecutive_auto_hold_streak": 4,
                }
            ],
        },
        execution_queue_payload={
            "rows": [
                {"target_id": "Dengue NS2B-NS3 protease", "shard_id": "05_of_20", "queue_status": "ready_after_previous_shard"},
            ]
        },
        throughput_bridge_payload={
            "rows": [
                {"command_kind": "throughput_preflight_tuned_gate45", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate45"},
                {"command_kind": "throughput_execute_tuned_gate45", "command": "python3 tools/run_ligand_htvs_pipeline.py --execute-gate45"},
            ]
        },
        stage6_tuning_surface_payload={
            "summary": {
                "status": "wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_ready",
                "campaign_start_shard_id": "01_of_20",
                "recommended_observed_threshold_A": 4.5,
            }
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_ready"
    assert summary["target_id"] == "Dengue NS2B-NS3 protease"
    assert summary["shard_id"] == "05_of_20"
    assert summary["selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["selected_threshold_A"] == 4.5
    assert summary["recommended_retry_mode"] == "guarded_tuned_gate45_candidate"
    assert summary["ready_for_manual_retry"] is True


def test_build_wetlab_dengue_ns2b_ns3_exploratory_retry_lane_marks_followup_phase() -> None:
    payload = mod.build_payload(
        hold_guard_payload={
            "summary": {"guard_limit": 3},
            "rows": [
                {
                    "target_id": "Dengue NS2B-NS3 protease",
                    "recommended_policy_action": "pause_target_autostart_and_review_retry_preset",
                    "recent_consecutive_auto_hold_streak": 3,
                }
            ],
        },
        execution_queue_payload={
            "rows": [
                {"target_id": "Dengue NS2B-NS3 protease", "shard_id": "05_of_20", "queue_status": "result_ready"},
                {"target_id": "Dengue NS2B-NS3 protease", "shard_id": "06_of_20", "queue_status": "explicit_hold"},
                {"target_id": "Dengue NS2B-NS3 protease", "shard_id": "07_of_20", "queue_status": "explicit_hold"},
                {"target_id": "Dengue NS2B-NS3 protease", "shard_id": "09_of_20", "queue_status": "ready_after_previous_shard"},
            ]
        },
        throughput_bridge_payload={"rows": []},
        stage6_tuning_surface_payload={
            "summary": {
                "status": "wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_ready",
                "campaign_start_shard_id": "05_of_20",
                "recommended_observed_threshold_A": 4.5,
                "immediately_runnable_command_kind": "throughput_preflight_tuned_gate45",
            }
        },
    )

    summary = payload["summary"]
    assert summary["shard_id"] == "09_of_20"
    assert summary["lane_phase"] == "followup"
    assert summary["lane_label"] == "exploratory_gate4.5_followup"
    assert summary["recommended_retry_mode"] == "guarded_tuned_gate45_followup"
    assert summary["prior_tuned_success_count"] == 1
    assert summary["prior_tuned_hold_count"] == 2
