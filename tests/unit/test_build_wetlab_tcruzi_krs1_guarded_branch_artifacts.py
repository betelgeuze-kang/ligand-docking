from __future__ import annotations

from tools import build_wetlab_tcruzi_krs1_guarded_branch_summary as branch_mod
from tools.wetlab import build_wetlab_tcruzi_krs1_guarded_operator_packet as packet_mod


def _queue_payload() -> dict:
    return {
        "summary": {
            "status": "wetlab_broad_screen_execution_queue_ready",
            "first_actionable_target_id": "T. cruzi KRS1",
            "first_actionable_shard_id": "04_of_20",
        },
        "rows": [
            {"target_id": "T. cruzi KRS1", "shard_id": "01_of_20", "queue_status": "explicit_hold"},
            {"target_id": "T. cruzi KRS1", "shard_id": "02_of_20", "queue_status": "explicit_hold"},
            {"target_id": "T. cruzi KRS1", "shard_id": "03_of_20", "queue_status": "explicit_hold"},
            {"target_id": "T. cruzi KRS1", "shard_id": "04_of_20", "queue_status": "ready_after_previous_shard"},
        ],
    }


def _hold_guard_payload() -> dict:
    return {
        "summary": {"status": "wetlab_primary_hold_guard_surface_ready"},
        "rows": [
            {
                "target_id": "T. cruzi KRS1",
                "recent_consecutive_auto_hold_streak": 3,
                "guard_limit": 3,
                "guard_triggered_now": True,
                "recommended_policy_action": "pause_target_autostart_and_review_retry_preset",
            }
        ],
    }


def _watch_action_payload() -> dict:
    return {
        "summary": {
            "status": "wetlab_broad_screen_primary_watch_action_ready",
            "action_taken": "guard_stop_target_after_holds",
            "next_required_step": "Pause auto-advance for T. cruzi KRS1; it hit 3 consecutive auto-holds.",
        }
    }


def test_build_tcruzi_krs1_guarded_operator_packet_uses_review_branch_when_only_standard_bridge_is_available() -> None:
    bridge_payload = {
        "summary": {
            "status": "wetlab_broad_screen_throughput_bridge_ready",
            "target_id": "T. cruzi KRS1",
            "preferred_command_kind": "throughput_preflight",
        },
        "rows": [
            {"command_kind": "throughput_preflight", "enabled": True},
            {"command_kind": "throughput_preflight_tuned_gate45", "enabled": False},
        ],
    }
    payload = packet_mod.build_payload(
        _queue_payload(),
        bridge_payload,
        _hold_guard_payload(),
        _watch_action_payload(),
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_tcruzi_krs1_guarded_operator_packet_ready"
    assert summary["packet_scope"] == "partner_operator_guarded_stage6_review"
    assert summary["branch_mode"] == "guarded_operator_review"
    assert summary["review_unit_label"] == "guarded stage6 operator packet"
    assert summary["selected_command_kind"] == "throughput_preflight"
    assert summary["selected_threshold_A"] == 0.0
    assert summary["decision_case"] == "tcruzi_krs1_guarded_review_required"
    assert summary["action"] == "pause_default_lane_and_select_tuned_retry"
    assert summary["success_shard_count"] == 0
    assert summary["hold_shard_count"] == 3


def test_build_tcruzi_krs1_guarded_operator_packet_prefers_exploratory_gate51_focus_over_standard_bridge() -> None:
    bridge_payload = {
        "summary": {
            "status": "wetlab_broad_screen_throughput_bridge_ready",
            "target_id": "T. cruzi KRS1",
            "preferred_command_kind": "throughput_preflight",
        },
        "rows": [
            {"command_kind": "throughput_preflight", "enabled": True},
            {"command_kind": "throughput_preflight_tuned_gate51", "enabled": True},
        ],
    }
    exploratory_lane_payload = {
        "summary": {
            "status": "wetlab_tcruzi_krs1_exploratory_retry_lane_ready",
            "target_id": "T. cruzi KRS1",
            "selected_command_kind": "throughput_preflight_tuned_gate51",
            "selected_threshold_A": 5.1,
        }
    }
    tuning_payload = {
        "summary": {
            "status": "wetlab_tcruzi_krs1_stage6_tuning_surface_ready",
            "target_id": "T. cruzi KRS1",
            "immediately_runnable_command_kind": "throughput_preflight_tuned_gate51",
            "immediately_runnable_threshold_A": 5.1,
            "gate51_validation_row_count": 16,
            "gate51_validation_success_count": 16,
            "gate51_validation_all_post_hold_success": True,
            "gate51_validation_start_shard_id": "05_of_20",
            "gate51_validation_end_shard_id": "20_of_20",
            "gate51_validation_observed_metric_min_A": 4.991,
            "gate51_validation_observed_metric_mean_A": 5.021,
            "gate51_validation_observed_metric_max_A": 5.054,
        }
    }
    payload = packet_mod.build_payload(
        _queue_payload(),
        bridge_payload,
        _hold_guard_payload(),
        _watch_action_payload(),
        exploratory_lane_payload,
        tuning_payload,
    )
    summary = payload["summary"]

    assert summary["packet_scope"] == "partner_operator_guarded_gate51_review"
    assert summary["branch_mode"] == "guarded_gate51_review"
    assert summary["review_unit_label"] == "guarded gate5.1 operator packet"
    assert summary["selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["selected_threshold_A"] == 5.1
    assert summary["decision_case"] == "tcruzi_krs1_guarded_gate51_review_candidate"
    assert summary["action"] == "pause_default_lane_and_review_gate51_retry"
    assert summary["gate51_validation_row_count"] == 16
    assert summary["gate51_validation_success_count"] == 16
    assert summary["gate51_validation_start_shard_id"] == "05_of_20"
    assert summary["gate51_validation_end_shard_id"] == "20_of_20"
    assert summary["gate51_validation_observed_metric_mean_A"] == 5.021


def test_build_tcruzi_krs1_guarded_branch_summary_switches_to_tuned_branch_when_tuned_bridge_is_selected() -> None:
    bridge_payload = {
        "summary": {
            "status": "wetlab_broad_screen_throughput_bridge_ready",
            "target_id": "T. cruzi KRS1",
            "preferred_command_kind": "throughput_preflight_tuned_gate45",
        },
        "rows": [
            {"command_kind": "throughput_preflight_tuned_gate45", "enabled": True},
            {"command_kind": "throughput_preflight", "enabled": True},
        ],
    }
    operator_packet = packet_mod.build_payload(
        _queue_payload(),
        bridge_payload,
        _hold_guard_payload(),
        _watch_action_payload(),
    )
    payload = branch_mod.build_payload(
        operator_packet,
        _queue_payload(),
        _hold_guard_payload(),
        _watch_action_payload(),
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_tcruzi_krs1_guarded_branch_summary_ready"
    assert summary["branch_label"] == "tcruzi_krs1_guarded_tuned_branch"
    assert summary["branch_state"] == "guarded_tuned_branch_review_default_lane_closed"
    assert summary["branch_to_rescue_only"] is False
    assert summary["branch_to_tuned_only"] is True
    assert summary["review_unit_label"] == "guarded tuned operator packet"
    assert summary["selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["selected_threshold_A"] == 4.5
    assert summary["operator_packet_scope"] == "partner_operator_guarded_tuned_branch_review"


def test_build_tcruzi_krs1_guarded_branch_summary_promotes_validated_gate51_branch_from_queue() -> None:
    operator_packet = {
        "summary": {
            "status": "wetlab_tcruzi_krs1_guarded_operator_packet_pending",
            "selected_command_kind": "throughput_preflight_tuned_gate51",
            "selected_threshold_A": 5.1,
            "review_unit_label": "guarded gate5.1 operator packet",
            "decision_case": "tcruzi_krs1_guarded_gate51_review_candidate",
            "action": "pause_default_lane_and_review_gate51_retry",
            "packet_scope": "partner_operator_guarded_gate51_review",
            "success_shard_count": 4,
            "hold_shard_count": 4,
            "queue_status_now": "ready_after_previous_shard",
        }
    }
    execution_queue = {
        "summary": {"status": "wetlab_broad_screen_execution_queue_ready"},
        "rows": [
            {"target_id": "T. cruzi KRS1", "shard_id": "01_of_20", "queue_status": "explicit_hold"},
            {"target_id": "T. cruzi KRS1", "shard_id": "02_of_20", "queue_status": "explicit_hold"},
            {"target_id": "T. cruzi KRS1", "shard_id": "03_of_20", "queue_status": "explicit_hold"},
            {"target_id": "T. cruzi KRS1", "shard_id": "04_of_20", "queue_status": "explicit_hold"},
            {"target_id": "T. cruzi KRS1", "shard_id": "05_of_20", "queue_status": "result_ready"},
            {"target_id": "T. cruzi KRS1", "shard_id": "06_of_20", "queue_status": "result_ready"},
        ],
    }

    payload = branch_mod.build_payload(
        operator_packet,
        execution_queue,
        _hold_guard_payload(),
        _watch_action_payload(),
        {
            "summary": {
                "gate51_validation_row_count": 16,
                "gate51_validation_success_count": 16,
                "gate51_validation_all_post_hold_success": True,
                "gate51_validation_start_shard_id": "05_of_20",
                "gate51_validation_end_shard_id": "20_of_20",
                "gate51_validation_observed_metric_min_A": 4.991,
                "gate51_validation_observed_metric_mean_A": 5.021,
                "gate51_validation_observed_metric_max_A": 5.054,
            }
        },
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_tcruzi_krs1_guarded_branch_summary_validated"
    assert summary["branch_state"] == "guarded_gate51_validated_default_lane_closed"
    assert summary["branch_validated"] is True
    assert summary["shard_id"] == "06_of_20"
    assert summary["queue_status_now"] == "result_ready"
    assert summary["success_shard_count"] == 2
    assert summary["hold_shard_count"] == 4
    assert summary["validated_start_shard_id"] == "05_of_20"
    assert summary["validated_end_shard_id"] == "06_of_20"
    assert summary["validated_success_streak_count"] == 2
    assert summary["gate51_validation_row_count"] == 16
    assert summary["gate51_validation_success_count"] == 16
    assert summary["gate51_validation_all_post_hold_success"] is True
    assert summary["gate51_validation_start_shard_id"] == "05_of_20"
    assert summary["gate51_validation_end_shard_id"] == "20_of_20"
    assert summary["gate51_validation_observed_metric_mean_A"] == 5.021
    assert "allow LRRK2 to continue" in summary["next_required_step"]
