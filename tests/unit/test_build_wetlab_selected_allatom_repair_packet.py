from __future__ import annotations

from tools import build_wetlab_selected_allatom_repair_packet as mod


def test_build_wetlab_selected_allatom_repair_packet_is_repair_only() -> None:
    payload = mod.build_payload(
        burndown_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_focus_artifact": "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
                "selected_allatom_selected_threshold_A": "2.5",
                "selected_allatom_best_mean_min_distance_A": "3.705",
                "selected_allatom_wetlab_gate_pass": False,
                "selected_allatom_final_gate_pass": False,
                "hard_block_count": 2,
                "missing_metric_count": 1,
                "primary_burndown_code": "recompute_mean_min_distance_A",
                "primary_burndown_metric": "mean_min_distance_A",
                "primary_burndown_value": "3.705",
                "primary_burndown_threshold": "2.500",
                "primary_burndown_delta": "1.205",
            },
            "rows": [
                {
                    "severity": "hard",
                    "category": "translation_commercial_hard_gate",
                    "code": "recompute_mean_min_distance_A",
                    "action": "tighten_pose_geometry_under_strict_gate",
                    "status": "failed",
                    "metric": "mean_min_distance_A",
                    "value": "3.705",
                    "threshold": "2.500",
                    "delta": "1.205",
                    "reason": "mean_min_distance_A=3.705 threshold=2.500",
                },
                {
                    "severity": "hard",
                    "category": "translation_commercial_hard_gate",
                    "code": "recompute_claim_gate_required_unavailable",
                    "action": "review_claim_gate_required_unavailable",
                    "status": "missing",
                    "metric": "claim_gate_required_unavailable",
                    "value": "missing",
                    "threshold": "missing",
                    "delta": "-",
                    "reason": "claim_gate_required_unavailable=missing",
                },
                {
                    "severity": "semi_hard",
                    "category": "claim_equivalence",
                    "code": "produce_claim_equivalence_packet",
                    "action": "produce_claim_equivalence_packet",
                    "status": "required",
                },
                {
                    "severity": "semi_hard",
                    "category": "claim_equivalence",
                    "code": "resolve_claim_equivalence_gate",
                    "action": "resolve_claim_equivalence_gate",
                    "status": "required",
                },
                {
                    "severity": "soft",
                    "category": "next_expensive_lane",
                    "code": "defer_expensive_lane",
                    "action": "defer_expensive_lane",
                    "status": "deferred",
                },
            ],
        },
        review_payload={
            "summary": {
                "target_id": "T. cruzi PDE",
                "wetlab_gate_pass": False,
                "wetlab_final_gate_pass": False,
                "wetlab_gate_thresholds": {"selected_threshold_A": 2.5, "strict_threshold_A": 2.5},
                "wetlab_gate_failed_metrics": ["mean_min_distance_A"],
                "wetlab_final_gate_missing_metrics": ["claim_gate_required_unavailable"],
                "recommended_next_expensive_lane": "defer_expensive_lane",
                "recommended_next_expensive_lane_reason": "Do not spend stronger-physics budget yet.",
                "claim_gate_requirement_actions": [
                    "produce_claim_equivalence_packet",
                    "resolve_claim_equivalence_gate",
                ],
            },
            "rows": [{"ligand_id": "lig-1", "mean_min_distance_A": 3.705}],
        },
        rescue_lane_payload={
            "summary": {
                "rescue_only_branch_ready_for_final_wetlab": False,
                "recommended_next_expensive_lane": "defer_expensive_lane",
                "translation_gate_focus_action_codes": [
                    "tighten_pose_geometry_under_strict_gate",
                    "collect_replicate_translation_support",
                ],
            }
        },
    )

    summary = payload["summary"]
    assert summary["repair_ready"] is True
    assert summary["delivery_ready_override_allowed"] is False
    assert summary["selected_allatom_pass_override_allowed"] is False
    assert summary["selected_allatom_wetlab_gate_pass"] is False
    assert summary["selected_allatom_final_gate_pass"] is False
    assert summary["hard_block_count"] == 2
    assert summary["missing_metric_count"] == 1
    assert summary["primary_repair_code"] == "recompute_mean_min_distance_A"
    assert summary["primary_metric"] == "mean_min_distance_A"
    assert summary["primary_value"] == "3.705"
    assert summary["primary_threshold"] == "2.500"
    assert summary["primary_delta"] == "1.205"
    assert summary["recommended_command"] == (
        "python3 tools/run_wetlab_tcruzi_pde_allatom_rescue.py "
        "--top-k 8 --filter-mode strict_then_near_fill --execute"
    )
    assert summary["threshold_relaxation_allowed"] is False
    assert summary["manual_pass_promotion_allowed"] is False
    assert summary["claim_equivalence_required_inputs"] == ["<claim_summary.json>", "<gate.json>"]
    assert summary["claim_equivalence_missing_inputs_pass"] is False
    assert summary["claim_equivalence_plan_phases"] == [
        "claim_inputs_build_after_hard_gate",
        "claim_readiness_after_hard_gate",
        "claim_attached_review_refresh",
    ]
    assert summary["claim_equivalence_after_hard_gate"] is True
    assert summary["hard_gate_acceptance_metric"] == "mean_min_distance_A"
    assert summary["hard_gate_acceptance_operator"] == "<="
    assert summary["hard_gate_acceptance_threshold"] == "2.500"
    assert summary["hard_gate_acceptance_scope"] == "promoted selected all-atom review rows"
    assert summary["hard_gate_acceptance_manual_override_allowed"] is False
    assert summary["closure_acceptance_requires"] == [
        "selected_allatom_wetlab_gate_pass=true",
        "selected_allatom_final_gate_pass=true",
        "hard_block_count=0",
        "semi_hard_block_count=0",
        "missing_metric_count=0",
        "commercialization_queue_clear=true",
        "delivery_ready=true",
        "p0_blocker_count=0",
    ]
    assert "claim/equivalence" in summary["next_required_step"]
    assert "after hard gate" in summary["next_required_step"]
    assert "<claim_summary.json>" in summary["next_required_step"]
    assert "<gate.json>" in summary["next_required_step"]
    assert "not pass" in summary["next_required_step"]

    command_plan = summary["command_plan"]
    phases = [item["phase"] for item in command_plan]
    assert phases == [
        "rescue_only_branch_build",
        "rescue_only_branch_summary",
        "allatom_rescue_lane_build",
        "hard_gate_repair",
        "hard_gate_review_refresh",
        "claim_inputs_build_after_hard_gate",
        "claim_readiness_after_hard_gate",
        "claim_attached_review_refresh",
        "final_campaign_refresh",
        "dashboard_refresh",
        "burndown_refresh",
        "commercialization_queue_refresh",
        "commercialization_status_refresh",
        "delivery_verdict_refresh",
        "closure_acceptance_check",
    ]
    assert summary["closure_plan"] == command_plan
    commands_by_phase = {item["phase"]: item["command"] for item in command_plan}
    assert commands_by_phase["rescue_only_branch_build"] == "python3 tools/run_wetlab_tcruzi_pde_rescue_only_branch.py"
    assert commands_by_phase["rescue_only_branch_summary"] == "python3 tools/build_wetlab_tcruzi_pde_rescue_only_branch_summary.py"
    assert commands_by_phase["allatom_rescue_lane_build"] == "python3 tools/build_wetlab_tcruzi_pde_allatom_rescue_lane.py"
    assert commands_by_phase["hard_gate_repair"] == summary["recommended_command"]
    assert commands_by_phase["hard_gate_review_refresh"] == "python3 tools/build_wetlab_tcruzi_pde_allatom_review_packet.py"
    assert "--manifest-csv <openmm_manifest.csv>" in commands_by_phase["claim_inputs_build_after_hard_gate"]
    assert "--out-json <claim_summary.json>" in commands_by_phase["claim_readiness_after_hard_gate"]
    assert "--gate-out-json <gate.json>" in commands_by_phase["claim_readiness_after_hard_gate"]
    assert commands_by_phase["claim_attached_review_refresh"] == (
        "python3 tools/build_wetlab_tcruzi_pde_allatom_review_packet.py "
        "--claim-readiness-json <claim_summary.json> --equivalence-gate-json <gate.json>"
    )
    assert commands_by_phase["final_campaign_refresh"] == "python3 tools/build_wetlab_final_campaign_summary.py"
    assert commands_by_phase["dashboard_refresh"] == "python3 tools/build_wetlab_master_handoff_dashboard.py"
    assert commands_by_phase["burndown_refresh"] == "python3 tools/build_wetlab_selected_allatom_gate_burndown_packet.py"
    assert commands_by_phase["commercialization_queue_refresh"] == "python3 tools/build_local_engine_commercialization_queue.py"
    assert commands_by_phase["commercialization_status_refresh"] == "python3 tools/build_commercialization_status_report.py"
    assert commands_by_phase["delivery_verdict_refresh"] == "python3 tools/build_local_delivery_verdict_gate.py"
    claim_step = next(item for item in command_plan if item["phase"] == "claim_attached_review_refresh")
    assert claim_step["required_inputs"] == "<claim_summary.json>, <gate.json>"
    assert claim_step["blocked_if_missing"] == "true"
    assert command_plan[-1]["phase"] == "closure_acceptance_check"
    assert all(item["manual_pass_promotion_allowed"] == "false" for item in command_plan)

    rows = {row["repair_code"]: row for row in payload["rows"]}
    assert rows["recompute_mean_min_distance_A"]["operator_action"] == "repair_pose_geometry_and_recompute_gate"
    assert rows["recompute_mean_min_distance_A"]["threshold_change_allowed"] is False
    assert rows["recompute_mean_min_distance_A"]["manual_pass_promotion_allowed"] is False
    assert rows["recompute_claim_gate_required_unavailable"]["operator_action"] == "materialize_missing_claim_gate_metric"
    assert rows["produce_claim_equivalence_packet"]["execution_phase"] == "after_hard_gate"
    assert rows["resolve_claim_equivalence_gate"]["execution_phase"] == "after_hard_gate"
    assert rows["defer_expensive_lane"]["execution_phase"] == "deferred"


def test_repair_packet_does_not_relax_threshold_when_input_distance_fails() -> None:
    payload = mod.build_payload(
        burndown_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_selected_threshold_A": "99.0",
                "selected_allatom_best_mean_min_distance_A": "3.705",
                "hard_block_count": 1,
                "missing_metric_count": 0,
                "primary_burndown_code": "recompute_mean_min_distance_A",
                "primary_burndown_metric": "mean_min_distance_A",
                "primary_burndown_value": "3.705",
                "primary_burndown_threshold": "2.500",
                "primary_burndown_delta": "1.205",
            },
            "rows": [
                {
                    "severity": "hard",
                    "code": "recompute_mean_min_distance_A",
                    "metric": "mean_min_distance_A",
                    "value": "3.705",
                    "threshold": "2.500",
                    "delta": "1.205",
                }
            ],
        },
        review_payload={"summary": {"wetlab_gate_thresholds": {"selected_threshold_A": 2.5}}},
        rescue_lane_payload={"summary": {}},
    )

    summary = payload["summary"]
    assert summary["primary_threshold"] == "2.500"
    assert summary["threshold_relaxation_allowed"] is False
    assert summary["manual_pass_promotion_allowed"] is False
    assert summary["selected_allatom_pass_override_allowed"] is False
    assert summary["next_required_step"].startswith("Execute repair")
