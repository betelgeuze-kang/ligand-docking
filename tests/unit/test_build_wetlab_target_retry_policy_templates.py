from __future__ import annotations

from tools.wetlab import build_wetlab_target_retry_policy_templates as mod


def test_build_wetlab_target_retry_policy_templates_includes_dhodh_branch() -> None:
    kinase_templates = {
        "summary": {
            "status": "wetlab_kinase_retry_policy_templates_ready",
            "template_target_count": 3,
            "empirical_validated_target_count": 1,
            "focus_target_id": "STK17B (DRAK2)",
            "focus_template_label": "gate45_branch_only_empirical",
            "focus_selected_command_kind": "throughput_preflight_tuned_gate45",
            "focus_selected_threshold_A": 4.5,
            "next_required_step": "Keep STK17B on gate4.5 only.",
        },
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "template_label": "gate45_branch_only_empirical",
                "selected_command_kind": "throughput_preflight_tuned_gate45",
                "selected_threshold_A": 4.5,
                "empirical_validated": True,
                "next_required_step": "Keep STK17B on gate4.5 only.",
            }
        ],
    }
    lbdhodh_validation = {
        "summary": {
            "status": "wetlab_lbdhodh_gate51_validation_review_surface_ready",
            "target_id": "Leishmania braziliensis DHODH",
            "gate51_validated": True,
            "decision": "promote_gate51_validated_keep_default_closed",
            "decision_rationale": "Gate5.1 validated.",
            "validated_command_kind": "throughput_preflight_tuned_gate51",
            "validated_threshold_A": 5.1,
            "next_required_step": "Promote DHODH gate5.1 as validated, keep the default lane closed, and reserve any future DHODH reopen for an explicit new review.",
        }
    }
    lbdhodh_tuning = {"summary": {"recommended_observed_threshold_A": 5.1}}
    lbdhodh_lane = {"summary": {"selected_command_kind": "throughput_preflight_tuned_gate51"}}

    payload = mod.build_payload(
        kinase_templates,
        lbdhodh_validation,
        lbdhodh_tuning,
        lbdhodh_lane,
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_target_retry_policy_templates_ready"
    assert summary["template_target_count"] == 2
    assert summary["empirical_validated_target_count"] == 2
    assert summary["focus_target_id"] == "Leishmania braziliensis DHODH"
    assert summary["focus_template_label"] == "gate51_branch_only_empirical"
    assert summary["focus_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["focus_selected_threshold_A"] == 5.1
    assert summary["next_required_step"].startswith("Promote DHODH gate5.1 as validated")

    rows_by_target = {row["target_id"]: row for row in payload["rows"]}
    dhodh = rows_by_target["Leishmania braziliensis DHODH"]
    assert dhodh["template_label"] == "gate51_branch_only_empirical"
    assert dhodh["selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert dhodh["selected_threshold_A"] == 5.1
    assert dhodh["empirical_validated"] is True
    assert dhodh["default_lane_policy"] == "keep_default_closed_branch_gate51_only"
    assert dhodh["autostart_policy"] == "manual_review_before_any_reopen"
    assert dhodh["evidence_source"] == "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.md"


def test_build_wetlab_target_retry_policy_templates_includes_non_kinase_candidates() -> None:
    kinase_templates = {
        "summary": {"status": "wetlab_kinase_retry_policy_templates_ready"},
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "template_label": "gate45_branch_only_empirical",
                "selected_command_kind": "throughput_preflight_tuned_gate45",
                "selected_threshold_A": 4.5,
                "target_class": "kinase",
                "empirical_validated": True,
            }
        ],
    }
    lbdhodh_validation = {
        "summary": {
            "status": "wetlab_lbdhodh_gate51_validation_review_surface_ready",
            "target_id": "Leishmania braziliensis DHODH",
            "gate51_validated": True,
            "validated_command_kind": "throughput_preflight_tuned_gate51",
            "validated_threshold_A": 5.1,
            "decision": "promote_gate51_validated_keep_default_closed",
            "decision_rationale": "Validated at gate5.1.",
            "next_required_step": "Promote DHODH gate5.1 as validated.",
        }
    }
    plpro_lane = {
        "summary": {
            "status": "wetlab_plpro_manual_retry_lane_ready",
            "target_id": "SARS-CoV-2 PLpro",
            "ready_for_manual_retry": True,
            "selected_command_kind": "throughput_preflight_tuned_gate55",
            "recommended_retry_mode": "guarded_manual_preflight_retry",
            "retry_handoff_decision": "pause_auto_start",
            "next_required_step": "Run the PLpro manual retry runner.",
        }
    }
    primary_hold_guard = {
        "rows": [
            {
                "target_id": "Cathepsin K",
                "recommended_policy_action": "pause_target_autostart_and_review_retry_preset",
            }
        ]
    }
    cathepsin_k_stage6_tuning_surface = {
        "summary": {
            "status": "wetlab_cathepsin_k_stage6_tuning_surface_ready",
            "target_id": "Cathepsin K",
            "recommended_observed_threshold_A": 4.45,
            "immediately_runnable_command_kind": "throughput_preflight_tuned_gate45",
            "next_required_step": "Run the Cathepsin K exploratory gate4.5 retry for 05_of_20.",
        }
    }
    cathepsin_k_exploratory_retry_lane = {
        "summary": {
            "status": "wetlab_cathepsin_k_exploratory_retry_lane_ready",
            "target_id": "Cathepsin K",
            "selected_command_kind": "throughput_preflight_tuned_gate45",
            "selected_threshold_A": 4.5,
            "recommended_retry_mode": "guarded_tuned_gate45_candidate",
            "ready_for_manual_retry": True,
            "next_required_step": "Run the Cathepsin K exploratory gate4.5 retry for 05_of_20.",
        }
    }

    payload = mod.build_payload(
        kinase_templates,
        lbdhodh_validation,
        {"summary": {"recommended_observed_threshold_A": 5.1, "immediately_runnable_command_kind": "throughput_preflight_tuned_gate51"}},
        {"summary": {"selected_command_kind": "throughput_preflight_tuned_gate51"}},
        cathepsin_k_stage6_tuning_surface,
        cathepsin_k_exploratory_retry_lane,
        None,
        None,
        plpro_lane,
        primary_hold_guard,
        None,
    )
    summary = payload["summary"]
    assert summary["template_target_count"] == 4
    assert summary["non_kinase_template_target_count"] == 3
    assert summary["non_kinase_empirical_validated_target_count"] == 1
    assert summary["guarded_gate55_candidate_target_count"] == 1
    assert summary["guarded_gate45_candidate_target_count"] == 1

    rows_by_target = {row["target_id"]: row for row in payload["rows"]}
    assert rows_by_target["SARS-CoV-2 PLpro"]["template_label"] == "guarded_gate55_candidate"
    assert rows_by_target["SARS-CoV-2 PLpro"]["selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert rows_by_target["Cathepsin K"]["template_label"] == "guarded_gate45_candidate"
    assert rows_by_target["Cathepsin K"]["selected_threshold_A"] == 4.5


def test_build_wetlab_target_retry_policy_templates_includes_mpro_and_pde_stage6_candidates() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "wetlab_kinase_retry_policy_templates_ready"}, "rows": []},
        {
            "summary": {
                "status": "wetlab_lbdhodh_gate51_validation_review_surface_ready",
                "target_id": "Leishmania braziliensis DHODH",
                "gate51_validated": True,
                "validated_command_kind": "throughput_preflight_tuned_gate51",
                "validated_threshold_A": 5.1,
                "decision": "promote_gate51_validated_keep_default_closed",
                "decision_rationale": "Validated at gate5.1.",
                "next_required_step": "Promote DHODH gate5.1 as validated.",
            }
        },
        {"summary": {"status": "wetlab_lbdhodh_stage6_tuning_surface_ready", "recommended_observed_threshold_A": 5.1, "immediately_runnable_command_kind": "throughput_preflight_tuned_gate51"}},
        {"summary": {"selected_command_kind": "throughput_preflight_tuned_gate51"}},
        None,
        None,
        {"summary": {"status": "wetlab_sarscov2_mpro_stage6_tuning_surface_ready", "target_id": "SARS-CoV-2 Mpro", "immediately_runnable_command_kind": "throughput_preflight_tuned_gate45", "immediately_runnable_threshold_A": 4.5, "next_required_step": "Keep the SARS-CoV-2 Mpro default lane closed until a tuned stage6 retry family is selected."}},
        {"summary": {"status": "wetlab_tcruzi_pde_stage6_tuning_surface_ready", "target_id": "T. cruzi PDE", "immediately_runnable_command_kind": "throughput_preflight_tuned_gate51", "immediately_runnable_threshold_A": 5.1, "next_required_step": "Keep the T. cruzi PDE default lane closed until a tuned stage6 retry family is selected."}},
        None,
        None,
        None,
    )

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["SARS-CoV-2 Mpro"]["template_label"] == "guarded_gate45_candidate"
    assert rows["SARS-CoV-2 Mpro"]["selected_threshold_A"] == 4.5
    assert rows["T. cruzi PDE"]["template_label"] == "guarded_gate51_candidate"
    assert rows["T. cruzi PDE"]["selected_threshold_A"] == 5.1


def test_build_wetlab_target_retry_policy_templates_promotes_krs1_validated_gate51_family() -> None:
    kinase_templates = {
        "summary": {
            "status": "wetlab_kinase_retry_policy_templates_ready",
            "template_target_count": 3,
            "empirical_validated_target_count": 1,
            "focus_target_id": "STK17B (DRAK2)",
            "focus_template_label": "gate45_branch_only_empirical",
            "focus_selected_command_kind": "throughput_preflight_tuned_gate45",
            "focus_selected_threshold_A": 4.5,
            "next_required_step": "Keep STK17B on gate4.5 only.",
        },
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "template_label": "gate45_branch_only_empirical",
                "selected_command_kind": "throughput_preflight_tuned_gate45",
                "selected_threshold_A": 4.5,
                "target_class": "kinase",
                "empirical_validated": True,
                "next_required_step": "Keep STK17B on gate4.5 only.",
            }
        ],
    }
    lbdhodh_validation = {
        "summary": {
            "status": "wetlab_lbdhodh_gate51_validation_review_surface_ready",
            "target_id": "Leishmania braziliensis DHODH",
            "gate51_validated": True,
            "validated_command_kind": "throughput_preflight_tuned_gate51",
            "validated_threshold_A": 5.1,
            "decision": "promote_gate51_validated_keep_default_closed",
            "decision_rationale": "Gate5.1 validated.",
            "next_required_step": "Promote DHODH gate5.1 as validated, keep the default lane closed, and reserve any future DHODH reopen for an explicit new review.",
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
            "validated_start_shard_id": "05_of_20",
            "validated_end_shard_id": "20_of_20",
            "validated_success_streak_count": 16,
            "next_required_step": "Promote T. cruzi KRS1 guarded gate5.1 as validated, keep the default lane closed, and allow LRRK2 to continue as the successor broad lane.",
        }
    }

    payload = mod.build_payload(
        kinase_templates,
        lbdhodh_validation,
        {"summary": {"recommended_observed_threshold_A": 5.1, "immediately_runnable_command_kind": "throughput_preflight_tuned_gate51"}},
        {"summary": {"selected_command_kind": "throughput_preflight_tuned_gate51"}},
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        krs1_branch_review_surface,
        krs1_guarded_branch_summary,
    )

    summary = payload["summary"]
    assert summary["template_target_count"] == 3
    assert summary["empirical_validated_target_count"] == 3
    assert summary["validated_branch_only_target_count"] == 3
    assert summary["non_kinase_template_target_count"] == 2
    assert summary["non_kinase_empirical_validated_target_count"] == 2
    assert summary["focus_target_id"] == "T. cruzi KRS1"
    assert summary["focus_template_label"] == "gate51_branch_only_empirical"
    assert summary["focus_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["focus_selected_threshold_A"] == 5.1
    assert summary["next_required_step"].startswith("Promote T. cruzi KRS1 guarded gate5.1 as validated")

    rows_by_target = {row["target_id"]: row for row in payload["rows"]}
    krs1 = rows_by_target["T. cruzi KRS1"]
    assert krs1["template_label"] == "gate51_branch_only_empirical"
    assert krs1["template_scope"] == "empirical_validation_promoted"
    assert krs1["target_class"] == "pathogen_trna_synthetase"
    assert krs1["selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert krs1["selected_threshold_A"] == 5.1
    assert krs1["default_lane_policy"] == "keep_default_closed_branch_gate51_only"
    assert krs1["recommended_retry_mode"] == "gate51_validated_branch_only"
    assert krs1["empirical_validated"] is True
    assert krs1["evidence_source"] == "runs/wetlab_tcruzi_krs1_guarded_branch_summary_current.md"
    assert krs1["next_required_step"].startswith("Promote T. cruzi KRS1 guarded gate5.1 as validated")
    assert payload["structured"]["tcruzi_krs1_guarded_branch_summary_artifact"] == "runs/wetlab_tcruzi_krs1_guarded_branch_summary_current.md"
