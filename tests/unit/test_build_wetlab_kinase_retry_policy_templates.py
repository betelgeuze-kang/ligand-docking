from __future__ import annotations

from tools import build_wetlab_kinase_retry_policy_templates as mod


def test_build_wetlab_kinase_retry_policy_templates_builds_expected_rows() -> None:
    primary_retry_preset = {
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "recommended_retry_mode": "tuned_gate_candidate",
                "representative_stage6_failure_shard_id": "17_of_20",
                "target_specific_next_step": "Fallback STK17B step.",
            },
            {
                "target_id": "ALK2",
                "recommended_retry_mode": "tuned_gate_candidate",
                "representative_stage6_failure_shard_id": "04_of_20",
            },
        ]
    }
    primary_hold_guard = {
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "recent_consecutive_auto_hold_streak": 11,
                "total_auto_hold_count": 11,
            },
            {
                "target_id": "ALK2",
                "recent_consecutive_auto_hold_streak": 4,
                "total_auto_hold_count": 20,
            },
        ]
    }
    execution_queue = {
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "shard_id": "18_of_20",
                "queue_rank": 1,
                "queue_status": "ready_after_previous_shard",
            },
            {
                "target_id": "ALK2",
                "shard_id": "04_of_20",
                "queue_rank": 1,
                "queue_status": "explicit_hold",
            },
            {
                "target_id": "ALK2",
                "shard_id": "05_of_20",
                "queue_rank": 2,
                "queue_status": "ready_after_previous_shard",
            },
            {
                "target_id": "LRRK2",
                "shard_id": "01_of_20",
                "queue_rank": 1,
                "queue_status": "blocked_on_previous_target",
            },
        ]
    }
    antitarget_queue = {
        "rows": [
            {
                "primary_target_id": "ALK2",
                "anti_target_id": "ALK2 wild-type comparator",
                "queue_rank": 1,
            }
        ]
    }
    stk17b_followup_review_surface = {
        "summary": {
            "target_id": "STK17B (DRAK2)",
            "decision": "branch_to_gate45_only_keep_default_closed",
            "decision_rationale": "17_of_20 succeeded under the exploratory gate4.5 branch.",
            "next_required_step": "Keep STK17B on gate4.5 only.",
            "exploratory_threshold_A": 4.5,
            "branch_to_gate45_only": True,
        }
    }

    payload = mod.build_payload(
        primary_retry_preset,
        primary_hold_guard,
        execution_queue,
        antitarget_queue,
        stk17b_followup_review_surface,
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_kinase_retry_policy_templates_ready"
    assert summary["template_target_count"] == 3
    assert summary["empirical_validated_target_count"] == 1
    assert summary["gate45_only_target_count"] == 1
    assert summary["guarded_gate55_candidate_target_count"] == 1
    assert summary["panel_first_template_target_count"] == 1
    assert summary["focus_target_id"] == "STK17B (DRAK2)"
    assert summary["focus_template_label"] == "gate45_branch_only_empirical"
    assert summary["focus_selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["focus_selected_threshold_A"] == 4.5
    assert summary["next_required_step"] == "Keep STK17B on gate4.5 only."

    rows_by_target = {row["target_id"]: row for row in payload["rows"]}

    stk17b = rows_by_target["STK17B (DRAK2)"]
    assert stk17b["template_label"] == "gate45_branch_only_empirical"
    assert stk17b["selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert stk17b["selected_threshold_A"] == 4.5
    assert stk17b["empirical_validated"] is True
    assert stk17b["decision"] == "branch_to_gate45_only_keep_default_closed"
    assert stk17b["decision_rationale"] == "17_of_20 succeeded under the exploratory gate4.5 branch."
    assert stk17b["evidence_source"] == "runs/wetlab_stk17b_followup_review_surface_current.md"
    assert stk17b["next_required_step"] == "Keep STK17B on gate4.5 only."

    alk2 = rows_by_target["ALK2"]
    assert alk2["template_label"] == "guarded_tuned_gate55_retry"
    assert alk2["selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert alk2["selected_threshold_A"] == 5.5
    assert alk2["companion_panel"] == "ALK2 wild-type comparator"
    assert alk2["recommended_retry_mode"] == "tuned_gate_candidate"
    assert alk2["next_required_step"].startswith("Keep ALK2 auto-start closed and reopen only through the tuned gate55 guarded retry path")

    lrrk2 = rows_by_target["LRRK2"]
    assert lrrk2["template_label"] == "panel_first_guarded_tuned_gate55_retry"
    assert lrrk2["selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert lrrk2["selected_threshold_A"] == 5.5
    assert lrrk2["recommended_retry_mode"] == "panel_first_preemptive_template"
    assert lrrk2["companion_panel"] == "kinase selectivity panel"
    assert lrrk2["next_required_step"].startswith("Keep LRRK2 on the panel-first kinase template")


def test_build_wetlab_kinase_retry_policy_templates_preserves_lrrk2_path_when_krs1_promoted() -> None:
    primary_retry_preset = {
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "recommended_retry_mode": "tuned_gate_candidate",
                "representative_stage6_failure_shard_id": "17_of_20",
                "target_specific_next_step": "Fallback STK17B step.",
            },
            {
                "target_id": "ALK2",
                "recommended_retry_mode": "tuned_gate_candidate",
                "representative_stage6_failure_shard_id": "04_of_20",
            },
        ]
    }
    primary_hold_guard = {
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "recent_consecutive_auto_hold_streak": 11,
                "total_auto_hold_count": 11,
            },
            {
                "target_id": "ALK2",
                "recent_consecutive_auto_hold_streak": 4,
                "total_auto_hold_count": 20,
            },
        ]
    }
    execution_queue = {
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "shard_id": "18_of_20",
                "queue_rank": 1,
                "queue_status": "ready_after_previous_shard",
            },
            {
                "target_id": "ALK2",
                "shard_id": "04_of_20",
                "queue_rank": 1,
                "queue_status": "explicit_hold",
            },
            {
                "target_id": "ALK2",
                "shard_id": "05_of_20",
                "queue_rank": 2,
                "queue_status": "ready_after_previous_shard",
            },
            {
                "target_id": "LRRK2",
                "shard_id": "01_of_20",
                "queue_rank": 1,
                "queue_status": "blocked_on_previous_target",
            },
        ]
    }
    antitarget_queue = {
        "rows": [
            {
                "primary_target_id": "ALK2",
                "anti_target_id": "ALK2 wild-type comparator",
                "queue_rank": 1,
            }
        ]
    }
    stk17b_followup_review_surface = {
        "summary": {
            "target_id": "STK17B (DRAK2)",
            "decision": "branch_to_gate45_only_keep_default_closed",
            "decision_rationale": "17_of_20 succeeded under the exploratory gate4.5 branch.",
            "next_required_step": "Keep STK17B on gate4.5 only.",
            "exploratory_threshold_A": 4.5,
            "branch_to_gate45_only": True,
        }
    }
    krs1_branch_review_surface = {
        "summary": {
            "status": "wetlab_tcruzi_krs1_branch_review_surface_ready",
            "target_id": "T. cruzi KRS1",
            "branch_state": "guarded_gate51_validated_default_lane_closed",
            "branch_validated": True,
            "exploratory_retry_selected_command_kind": "throughput_preflight_tuned_gate51",
            "exploratory_retry_selected_threshold_A": 5.1,
            "successor_target": "LRRK2",
            "next_required_step": "Promote T. cruzi KRS1 guarded gate5.1 as validated, keep the default lane closed, and allow LRRK2 to continue as the successor broad lane.",
        }
    }
    krs1_guarded_branch_summary = {
        "summary": {
            "status": "wetlab_tcruzi_krs1_guarded_branch_summary_validated",
            "target_id": "T. cruzi KRS1",
            "branch_state": "guarded_gate51_validated_default_lane_closed",
            "branch_validated": True,
            "selected_command_kind": "throughput_preflight_tuned_gate51",
            "selected_threshold_A": 5.1,
            "validated_end_shard_id": "20_of_20",
            "next_required_step": "Promote T. cruzi KRS1 guarded gate5.1 as validated, keep the default lane closed, and allow LRRK2 to continue as the successor broad lane.",
        }
    }

    payload = mod.build_payload(
        primary_retry_preset,
        primary_hold_guard,
        execution_queue,
        antitarget_queue,
        stk17b_followup_review_surface,
        krs1_branch_review_surface,
        krs1_guarded_branch_summary,
    )

    summary = payload["summary"]
    assert summary["template_target_count"] == 4
    assert summary["empirical_validated_target_count"] == 2
    assert summary["gate45_only_target_count"] == 1
    assert summary["guarded_gate55_candidate_target_count"] == 1
    assert summary["panel_first_template_target_count"] == 1
    assert summary["focus_target_id"] == "T. cruzi KRS1"
    assert summary["focus_template_label"] == "gate51_branch_only_empirical"
    assert summary["focus_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["focus_selected_threshold_A"] == 5.1
    assert summary["next_required_step"].startswith("Promote T. cruzi KRS1 guarded gate5.1 as validated")

    rows_by_target = {row["target_id"]: row for row in payload["rows"]}

    krs1 = rows_by_target["T. cruzi KRS1"]
    assert krs1["template_label"] == "gate51_branch_only_empirical"
    assert krs1["selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert krs1["selected_threshold_A"] == 5.1
    assert krs1["recommended_retry_mode"] == "gate51_validated_branch_only"
    assert krs1["empirical_validated"] is True
    assert krs1["evidence_source"] == "runs/wetlab_tcruzi_krs1_guarded_branch_summary_current.md"
    assert krs1["next_required_step"].startswith("Promote T. cruzi KRS1 guarded gate5.1 as validated")

    lrrk2 = rows_by_target["LRRK2"]
    assert lrrk2["template_label"] == "panel_first_guarded_tuned_gate55_retry"
    assert lrrk2["selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert lrrk2["selected_threshold_A"] == 5.5
    assert lrrk2["recommended_retry_mode"] == "panel_first_preemptive_template"
    assert lrrk2["next_required_step"].startswith("Keep LRRK2 on the panel-first kinase template")


def test_build_wetlab_kinase_retry_policy_templates_promotes_krs1_validated_gate51_family() -> None:
    payload = mod.build_payload(
        primary_retry_preset_payload={"rows": []},
        primary_hold_guard_payload={"rows": []},
        execution_queue_payload={"rows": []},
        antitarget_queue_payload={"rows": []},
        stk17b_followup_review_surface_payload={"summary": {}},
        tcruzi_krs1_branch_review_surface_payload={
            "summary": {
                "status": "wetlab_tcruzi_krs1_branch_review_surface_ready",
                "target_id": "T. cruzi KRS1",
                "branch_state": "guarded_gate51_validated_default_lane_closed",
                "branch_validated": True,
                "exploratory_retry_selected_command_kind": "throughput_preflight_tuned_gate51",
                "exploratory_retry_selected_threshold_A": 5.1,
                "successor_target": "LRRK2",
                "next_required_step": "Promote T. cruzi KRS1 guarded gate5.1 as validated, keep the default lane closed, and allow LRRK2 to continue as the successor broad lane.",
            }
        },
        tcruzi_krs1_guarded_branch_summary_payload={
            "summary": {
                "status": "wetlab_tcruzi_krs1_guarded_branch_summary_validated",
                "target_id": "T. cruzi KRS1",
                "branch_state": "guarded_gate51_validated_default_lane_closed",
                "branch_validated": True,
                "selected_command_kind": "throughput_preflight_tuned_gate51",
                "selected_threshold_A": 5.1,
                "validated_start_shard_id": "05_of_20",
                "validated_end_shard_id": "20_of_20",
                "next_required_step": "Promote T. cruzi KRS1 guarded gate5.1 as validated, keep the default lane closed, and allow LRRK2 to continue as the successor broad lane.",
            }
        },
    )

    summary = payload["summary"]
    assert summary["template_target_count"] == 4
    assert summary["empirical_validated_target_count"] == 1
    assert summary["focus_target_id"] == "T. cruzi KRS1"
    assert summary["focus_template_label"] == "gate51_branch_only_empirical"
    assert summary["focus_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["focus_selected_threshold_A"] == 5.1
    assert summary["next_required_step"].startswith("Promote T. cruzi KRS1 guarded gate5.1 as validated")

    rows_by_target = {row["target_id"]: row for row in payload["rows"]}
    krs1 = rows_by_target["T. cruzi KRS1"]
    assert krs1["template_label"] == "gate51_branch_only_empirical"
    assert krs1["template_scope"] == "empirical_validation_promoted"
    assert krs1["selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert krs1["selected_threshold_A"] == 5.1
    assert krs1["default_lane_policy"] == "keep_default_closed_branch_gate51_only"
    assert krs1["recommended_retry_mode"] == "gate51_validated_branch_only"
    assert krs1["empirical_validated"] is True
    assert krs1["evidence_source"] == "runs/wetlab_tcruzi_krs1_guarded_branch_summary_current.md"
