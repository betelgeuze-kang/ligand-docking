from __future__ import annotations

from tools import build_wetlab_stk17b_exploratory_followup_lane as mod


def test_build_wetlab_stk17b_exploratory_followup_lane_targets_18_to_20() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "target_id": "STK17B (DRAK2)",
                "campaign_start_shard_id": "13_of_20",
                "exploratory_success_shard_id": "17_of_20",
                "exploratory_success_command_family": "gate45_exploratory",
                "exploratory_success_threshold_A": 4.5,
            }
        }
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_stk17b_exploratory_followup_lane_ready"
    assert summary["target_id"] == "STK17B (DRAK2)"
    assert summary["shard_id"] == "18_of_20"
    assert summary["followup_shard_ids"] == "18_of_20;19_of_20;20_of_20"
    assert summary["selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["hard_freeze_state"] == "hard_freeze_after_exploratory_success"
    assert summary["ready_for_manual_retry"] is True
    assert "18_of_20" in summary["next_required_step"]

    rows = payload["rows"]
    assert len(rows) == 3
    assert all(row["followup_lane_label"] == "exploratory_gate4.5_followup" for row in rows)
    assert all(row["selected_threshold_A"] == 4.5 for row in rows)


def test_build_wetlab_stk17b_exploratory_followup_lane_blocks_after_all_followups_are_consumed() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "target_id": "STK17B (DRAK2)",
                "campaign_start_shard_id": "13_of_20",
                "exploratory_success_shard_id": "17_of_20",
                "exploratory_success_command_family": "gate45_exploratory",
                "exploratory_success_threshold_A": 4.5,
            }
        },
        {
            "rows": [
                {"target_id": "STK17B (DRAK2)", "shard_id": "18_of_20", "queue_status": "explicit_hold"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "19_of_20", "queue_status": "explicit_hold"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "20_of_20", "queue_status": "explicit_hold"},
            ]
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_stk17b_exploratory_followup_lane_blocked"
    assert summary["ready_for_manual_retry"] is False
    assert summary["shard_id"] == ""
    assert summary["hard_freeze_state"] == "hard_freeze_after_exploratory_success"
    assert summary["freeze_note"].startswith("Auto-start remains hard-frozen after the gate4.5 success")
    assert summary["remaining_followup_shard_count"] == 0
    assert summary["completed_followup_shard_count"] == 3
    assert summary["followup_shard_ids"] == "18_of_20;19_of_20;20_of_20"
    assert summary["next_required_step"].startswith("Keep auto-start hard-frozen and review completed follow-up shards 18_of_20;19_of_20;20_of_20")


def test_build_wetlab_stk17b_exploratory_followup_lane_prefers_review_surface_next_step() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "target_id": "STK17B (DRAK2)",
                "campaign_start_shard_id": "13_of_20",
                "exploratory_success_shard_id": "17_of_20",
                "exploratory_success_command_family": "gate45_exploratory",
                "exploratory_success_threshold_A": 4.5,
            }
        },
        {
            "rows": [
                {"target_id": "STK17B (DRAK2)", "shard_id": "18_of_20", "queue_status": "explicit_hold"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "19_of_20", "queue_status": "explicit_hold"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "20_of_20", "queue_status": "explicit_hold"},
            ]
        },
        {
            "summary": {
                "status": "wetlab_stk17b_followup_review_surface_ready",
                "target_id": "STK17B (DRAK2)",
                "decision": "branch_to_gate45_only_keep_default_closed",
                "next_required_step": "Keep the STK17B (DRAK2) default lane closed and branch this target into the gate4.5 exploratory lane only; treat 18_of_20;19_of_20;20_of_20 as default-gate follow-up holds, not as evidence against the 4.5A path, until the follow-up runner preserves the 4.5A threshold end-to-end.",
            }
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_stk17b_exploratory_followup_lane_ready"
    assert summary["ready_for_manual_retry"] is True
    assert summary["shard_id"] == "18_of_20"
    assert summary["hard_freeze_state"] == "hard_freeze_after_exploratory_success"
    assert summary["next_required_step"].startswith("Run the STK17B (DRAK2) exploratory gate4.5 follow-up runner for 18_of_20")


def test_build_wetlab_stk17b_exploratory_followup_lane_keeps_standard_auto_holds_retryable_when_review_branches_to_gate45() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "target_id": "STK17B (DRAK2)",
                "campaign_start_shard_id": "13_of_20",
                "exploratory_success_shard_id": "17_of_20",
                "exploratory_success_command_family": "gate45_exploratory",
                "exploratory_success_threshold_A": 4.5,
            }
        },
        {
            "rows": [
                {"target_id": "STK17B (DRAK2)", "shard_id": "18_of_20", "queue_status": "explicit_hold"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "19_of_20", "queue_status": "explicit_hold"},
                {"target_id": "STK17B (DRAK2)", "shard_id": "20_of_20", "queue_status": "explicit_hold"},
            ]
        },
        {
            "summary": {
                "status": "wetlab_stk17b_followup_review_surface_ready",
                "target_id": "STK17B (DRAK2)",
                "decision": "branch_to_gate45",
                "next_required_step": "Keep the default lane frozen and reopen STK17B only through the gate4.5 exploratory follow-up lane for shards 18_of_20, 19_of_20, 20_of_20.",
            },
            "rows": [
                {
                    "target_id": "STK17B (DRAK2)",
                    "shard_id": "18_of_20",
                    "command_family": "standard_auto",
                    "summary_json": "runs/18_of_20/throughput_run_summary.json",
                },
                {
                    "target_id": "STK17B (DRAK2)",
                    "shard_id": "19_of_20",
                    "command_family": "standard_auto",
                    "summary_json": "runs/19_of_20/throughput_run_summary.json",
                },
                {
                    "target_id": "STK17B (DRAK2)",
                    "shard_id": "20_of_20",
                    "command_family": "standard_auto",
                    "summary_json": "runs/20_of_20/throughput_run_summary.json",
                },
            ],
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_stk17b_exploratory_followup_lane_ready"
    assert summary["ready_for_manual_retry"] is True
    assert summary["shard_id"] == "18_of_20"
    assert summary["remaining_followup_shard_count"] == 3
