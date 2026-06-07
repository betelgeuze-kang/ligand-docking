from __future__ import annotations

from tools.wetlab import build_wetlab_tcruzi_krs1_exploratory_retry_lane as mod


def test_build_wetlab_tcruzi_krs1_exploratory_retry_lane_selects_gate51() -> None:
    payload = mod.build_payload(
        {
            "summary": {"guard_limit": 2},
            "rows": [
                {
                    "target_id": "T. cruzi KRS1",
                    "recommended_policy_action": "pause_target_autostart_and_review_retry_preset",
                    "recent_consecutive_auto_hold_streak": 2,
                }
            ],
        },
        {
            "rows": [
                {"target_id": "T. cruzi KRS1", "shard_id": "03_of_20", "queue_status": "ready_after_previous_shard"},
            ]
        },
        {
            "rows": [
                {"command_kind": "throughput_preflight_tuned_gate51", "command": "python3 tools/run_ligand_htvs_pipeline.py --gate51"},
                {"command_kind": "throughput_execute_tuned_gate51", "command": "python3 tools/run_ligand_htvs_pipeline.py --execute-gate51"},
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
    assert summary["status"] == "wetlab_tcruzi_krs1_exploratory_retry_lane_ready"
    assert summary["target_id"] == "T. cruzi KRS1"
    assert summary["shard_id"] == "03_of_20"
    assert summary["lane_label"] == "exploratory_gate5.1_candidate"
    assert summary["guard_active"] is True
    assert summary["guard_limit"] == 2
    assert summary["guard_hold_streak"] == 2
    assert summary["selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["selected_threshold_A"] == 5.1
    assert summary["recommended_retry_mode"] == "guarded_tuned_gate51_candidate"
    assert summary["throughput_execute_ready"] is True
    assert summary["ready_for_manual_retry"] is True
    assert "gate5.1 retry for 03_of_20" in summary["next_required_step"]
