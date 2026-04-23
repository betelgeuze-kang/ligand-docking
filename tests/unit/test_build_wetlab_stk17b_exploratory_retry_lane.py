from __future__ import annotations

from tools import build_wetlab_stk17b_exploratory_retry_lane as mod


def test_build_wetlab_stk17b_exploratory_retry_lane_selects_gate45() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "target_id": "STK17B (DRAK2)",
                "shard_id": "17_of_20",
                "campaign_start_shard_id": "13_of_20",
                "guard_active": True,
                "ready_for_manual_retry": True,
            }
        },
        {
            "summary": {"throughput_execute_ready": True},
            "rows": [
                {
                    "command_kind": "throughput_preflight_tuned_gate45",
                    "enabled": True,
                    "command": "python3 tools/run_ligand_htvs_pipeline.py --gate-max-mean-min-distance-A 4.5",
                }
            ],
        },
        {
            "summary": {
                "recommended_relaxed_threshold_A": 4.5,
                "exploratory_median_threshold_A": 4.4,
            }
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_stk17b_exploratory_retry_lane_ready"
    assert summary["target_id"] == "STK17B (DRAK2)"
    assert summary["shard_id"] == "17_of_20"
    assert summary["selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["selected_threshold_A"] == 4.5
    assert summary["ready_for_manual_retry"] is True
