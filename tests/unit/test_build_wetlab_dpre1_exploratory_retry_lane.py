from __future__ import annotations

from tools import build_wetlab_dpre1_exploratory_retry_lane as mod


def test_build_wetlab_dpre1_exploratory_retry_lane_selects_gate51_when_available() -> None:
    payload = mod.build_payload(
        {
            "summary": {"guard_limit": 3},
            "rows": [
                {
                    "target_id": "DprE1",
                    "recent_consecutive_auto_hold_streak": 3,
                    "recommended_policy_action": "pause_target_autostart_and_review_retry_preset",
                }
            ],
        },
        {
            "rows": [
                {"target_id": "DprE1", "shard_id": "04_of_20", "queue_status": "ready_after_previous_shard"}
            ]
        },
        {
            "rows": [
                {
                    "command_kind": "throughput_preflight_tuned_gate51",
                    "command": "python3 tools/run_ligand_htvs_pipeline.py --gate-max-mean-min-distance-A 5.1",
                },
                {
                    "command_kind": "throughput_execute_tuned_gate51",
                    "command": "python3 tools/run_ligand_htvs_pipeline.py --gate-max-mean-min-distance-A 5.1 --no-dry-run",
                },
                {
                    "command_kind": "throughput_preflight_tuned_gate55",
                    "command": "python3 tools/run_ligand_htvs_pipeline.py --gate-max-mean-min-distance-A 5.5",
                },
            ]
        },
        {
            "summary": {
                "campaign_start_shard_id": "01_of_20",
                "recommended_observed_threshold_A": 5.05,
            }
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_dpre1_exploratory_retry_lane_ready"
    assert summary["target_id"] == "DprE1"
    assert summary["shard_id"] == "04_of_20"
    assert summary["selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["selected_threshold_A"] == 5.1
    assert summary["lane_label"] == "exploratory_gate5.1_candidate"
    assert summary["recommended_retry_mode"] == "guarded_tuned_gate51_candidate"
    assert summary["recommended_observed_threshold_A"] == 5.05
    assert summary["ready_for_manual_retry"] is True


def test_build_wetlab_dpre1_exploratory_retry_lane_falls_back_to_gate55() -> None:
    payload = mod.build_payload(
        {
            "summary": {"guard_limit": 3},
            "rows": [
                {
                    "target_id": "DprE1",
                    "recent_consecutive_auto_hold_streak": 3,
                    "recommended_policy_action": "pause_target_autostart_and_review_retry_preset",
                }
            ],
        },
        {
            "rows": [
                {"target_id": "DprE1", "shard_id": "04_of_20", "queue_status": "ready_after_previous_shard"}
            ]
        },
        {
            "rows": [
                {
                    "command_kind": "throughput_preflight_tuned_gate55",
                    "command": "python3 tools/run_ligand_htvs_pipeline.py --gate-max-mean-min-distance-A 5.5",
                },
                {
                    "command_kind": "throughput_execute_tuned_gate55",
                    "command": "python3 tools/run_ligand_htvs_pipeline.py --gate-max-mean-min-distance-A 5.5 --no-dry-run",
                },
            ]
        },
        {
            "summary": {
                "campaign_start_shard_id": "01_of_20",
                "recommended_observed_threshold_A": 5.05,
            }
        },
    )

    summary = payload["summary"]
    assert summary["selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert summary["selected_threshold_A"] == 5.5
    assert summary["lane_label"] == "exploratory_gate5.5_candidate"
