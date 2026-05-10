from __future__ import annotations

import json
from pathlib import Path

from tools import build_wetlab_selected_allatom_repair_packet as mod


def _strict_summary_payload(manifest: Path) -> dict:
    return {
        "summary": {"pass": True, "targets": 10},
        "gates": {
            "accuracy_gate": {
                "avg_neighbor_jaccard": 1.0,
                "avg_e2e_rmse_raw": 0.2,
                "avg_e2e_rel_rmse_mean_clipped": 1e-7,
            },
            "speed": {"avg_speedup_on_vs_off": 100.0},
            "long_stability": {"passed_targets": 10},
        },
        "source_manifest_csv": str(manifest),
    }


def _write_accuracy_external_csv(path: Path) -> None:
    path.write_text(
        "target,avg_rmsd_aligned,avg_rmsd_vs_native_aligned\n"
        "T. cruzi PDE,0.05,0.04\n",
        encoding="utf-8",
    )


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
    assert "runs/allatom_claim_readiness_" in summary["next_required_step"]
    assert "_summary.json" in summary["next_required_step"]
    assert "_gate.json" in summary["next_required_step"]
    assert "not pass" in summary["next_required_step"]

    command_plan = summary["command_plan"]
    phases = [item["phase"] for item in command_plan]
    assert phases == [
        "rescue_only_branch_build",
        "rescue_only_branch_summary",
        "allatom_rescue_lane_build",
        "hard_gate_repair",
        "replicate_evidence_refresh",
        "hard_gate_review_refresh",
        "claim_inputs_build_after_hard_gate",
        "claim_readiness_after_hard_gate",
        "claim_attached_review_refresh",
        "current_results_index_refresh",
        "partnering_stack_refresh",
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
    assert commands_by_phase["replicate_evidence_refresh"] == "python3 tools/build_wetlab_tcruzi_pde_replicate_evidence.py"
    assert commands_by_phase["hard_gate_review_refresh"] == "python3 tools/build_wetlab_tcruzi_pde_allatom_review_packet.py"
    assert "--manifest-csv <openmm_manifest.csv>" in commands_by_phase["claim_inputs_build_after_hard_gate"]
    assert "--out-json runs/allatom_claim_readiness_" in commands_by_phase["claim_readiness_after_hard_gate"]
    assert "--gate-out-json runs/allatom_claim_readiness_" in commands_by_phase["claim_readiness_after_hard_gate"]
    assert commands_by_phase["claim_attached_review_refresh"].startswith(
        "python3 tools/build_wetlab_tcruzi_pde_allatom_review_packet.py "
        "--claim-readiness-json runs/allatom_claim_readiness_"
    )
    assert commands_by_phase["current_results_index_refresh"] == "python3 tools/build_wetlab_current_results_index.py"
    assert commands_by_phase["partnering_stack_refresh"] == "python3 tools/build_wetlab_partnering_stack.py"
    assert commands_by_phase["final_campaign_refresh"] == "python3 tools/build_wetlab_final_campaign_summary.py"
    assert commands_by_phase["dashboard_refresh"] == "python3 tools/build_wetlab_master_handoff_dashboard.py"
    assert commands_by_phase["burndown_refresh"] == "python3 tools/build_wetlab_selected_allatom_gate_burndown_packet.py"
    assert commands_by_phase["commercialization_queue_refresh"] == "python3 tools/build_local_engine_commercialization_queue.py"
    assert commands_by_phase["commercialization_status_refresh"] == "python3 tools/build_commercialization_status_report.py"
    assert commands_by_phase["delivery_verdict_refresh"] == "python3 tools/build_local_delivery_verdict_gate.py"
    claim_step = next(item for item in command_plan if item["phase"] == "claim_attached_review_refresh")
    assert "runs/allatom_claim_readiness_" in claim_step["required_inputs"]
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


def test_repair_packet_reports_no_active_repair_when_current_chain_is_green() -> None:
    payload = mod.build_payload(
        burndown_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_focus_artifact": "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
                "selected_allatom_selected_threshold_A": "2.5",
                "selected_allatom_best_mean_min_distance_A": "2.120",
                "selected_allatom_wetlab_gate_pass": True,
                "selected_allatom_final_gate_pass": True,
                "selected_allatom_claim_gate_available": True,
                "selected_allatom_claim_ready_for_allatom": True,
                "hard_block_count": 0,
                "semi_hard_block_count": 0,
                "missing_metric_count": 0,
                "primary_burndown_code": "defer_expensive_lane",
                "primary_burndown_delta": "-",
            },
            "rows": [
                {
                    "severity": "soft",
                    "category": "next_expensive_lane",
                    "code": "defer_expensive_lane",
                    "action": "defer_expensive_lane",
                    "status": "deferred",
                    "reason": "Do not spend stronger-physics budget.",
                }
            ],
        },
        review_payload={
            "summary": {
                "target_id": "T. cruzi PDE",
                "wetlab_gate_pass": True,
                "wetlab_final_gate_pass": True,
                "claim_gate_available": True,
                "claim_gate_satisfied": True,
                "claim_ready_for_allatom": True,
                "allatom_claim_readiness_json": "runs/allatom_claim_readiness_2026-04-29_summary.json",
                "allatom_equivalence_gate_json": "runs/allatom_claim_readiness_2026-04-29_gate.json",
                "recommended_next_expensive_lane": "defer_expensive_lane",
            }
        },
        rescue_lane_payload={"summary": {}},
        allatom_runner_payload={
            "summary": {
                "raw_claim_gate_status": "claim_required_unavailable",
                "allatom_claim_readiness_json": "",
                "allatom_equivalence_gate_json": "",
            }
        },
    )

    summary = payload["summary"]
    assert summary["repair_ready"] is False
    assert summary["active_repair_required"] is False
    assert summary["supporting_packet_only"] is True
    assert summary["hard_block_count"] == 0
    assert summary["semi_hard_block_count"] == 0
    assert summary["missing_metric_count"] == 0
    assert summary["claim_equivalence_missing_inputs"] == []
    assert summary["claim_equivalence_missing_inputs_pass"] is True
    assert summary["claim_equivalence_available_inputs"]["claim_summary_json"] == (
        "runs/allatom_claim_readiness_2026-04-29_summary.json"
    )
    assert summary["claim_equivalence_available_inputs"]["gate_json"] == (
        "runs/allatom_claim_readiness_2026-04-29_gate.json"
    )
    assert summary["recommended_command"] == ""
    assert summary["command_plan"] == []
    assert summary["hard_gate_repair_codes"] == []
    assert summary["after_hard_gate_codes"] == []
    assert summary["deferred_codes"] == ["defer_expensive_lane"]
    assert "No active repair is required" in summary["next_required_step"]
    assert "regression/retry reference" in summary["next_required_step"]
    assert "claim_gate_required_unavailable" not in summary["next_required_step"]
    assert "strict_summary_json" not in summary["next_required_step"]
    assert "accuracy_external_csv" not in summary["next_required_step"]


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


def test_repair_packet_uses_clash_relief_command_for_binding_proxy_blocker() -> None:
    payload = mod.build_payload(
        burndown_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_focus_artifact": "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
                "selected_allatom_selected_threshold_A": "2.5",
                "selected_allatom_best_mean_min_distance_A": "0.672",
                "selected_allatom_wetlab_gate_pass": True,
                "selected_allatom_final_gate_pass": False,
                "hard_block_count": 2,
                "missing_metric_count": 1,
                "primary_burndown_code": "recompute_binding_energy_proxy",
                "primary_burndown_metric": "binding_energy_proxy",
                "primary_burndown_value": "0.113",
                "primary_burndown_threshold": "-0.050",
                "primary_burndown_delta": "0.163",
            },
            "rows": [
                {
                    "severity": "hard",
                    "category": "translation_commercial_hard_gate",
                    "code": "recompute_binding_energy_proxy",
                    "action": "strengthen_binding_energy_proxy",
                    "status": "failed",
                    "metric": "binding_energy_proxy",
                    "value": "0.113",
                    "threshold": "-0.050",
                    "delta": "0.163",
                    "reason": "binding_energy_proxy=0.113 threshold=-0.050",
                }
            ],
        },
        review_payload={
            "summary": {
                "target_id": "T. cruzi PDE",
                "wetlab_gate_pass": True,
                "wetlab_final_gate_pass": False,
                "recommended_next_expensive_lane": "defer_expensive_lane",
            }
        },
        rescue_lane_payload={"summary": {}},
    )

    summary = payload["summary"]
    assert summary["primary_repair_code"] == "recompute_binding_energy_proxy"
    assert summary["hard_gate_acceptance_metric"] == "binding_energy_proxy"
    assert summary["hard_gate_acceptance_threshold"] == "-0.050"
    assert "--clash-relief-mode translate" in summary["recommended_command"]
    assert "--clash-relief-target-min-distance-A 2.12" in summary["recommended_command"]
    rows = {row["repair_code"]: row for row in payload["rows"]}
    assert rows["recompute_binding_energy_proxy"]["operator_action"] == (
        "relieve_pose_clash_and_recompute_binding_proxy"
    )
    assert "binding_energy_proxy <= -0.050" in rows["recompute_binding_energy_proxy"]["operator_instruction"]


def test_repair_packet_starts_from_claim_inputs_when_claim_gate_is_primary() -> None:
    payload = mod.build_payload(
        burndown_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_focus_artifact": "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
                "selected_allatom_wetlab_gate_pass": True,
                "selected_allatom_final_gate_pass": False,
                "hard_block_count": 1,
                "missing_metric_count": 1,
                "primary_burndown_code": "recompute_claim_gate_required_unavailable",
                "primary_burndown_metric": "claim_gate_required_unavailable",
                "primary_burndown_value": "missing",
                "primary_burndown_threshold": "missing",
                "primary_burndown_delta": "-",
            },
            "rows": [
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
                }
            ],
        },
        review_payload={"summary": {"target_id": "T. cruzi PDE", "wetlab_gate_pass": True}},
        rescue_lane_payload={"summary": {}},
    )

    summary = payload["summary"]
    assert summary["primary_repair_code"] == "recompute_claim_gate_required_unavailable"
    assert summary["recommended_command"].startswith("python3 tools/build_claim_inputs_from_openmm_manifest.py")
    phases = [item["phase"] for item in summary["command_plan"]]
    assert phases[:3] == [
        "claim_inputs_build_after_hard_gate",
        "claim_readiness_after_hard_gate",
        "claim_attached_review_refresh",
    ]
    assert "hard_gate_repair" not in phases
    rows = {row["repair_code"]: row for row in payload["rows"]}
    assert rows["recompute_claim_gate_required_unavailable"]["operator_action"] == (
        "materialize_missing_claim_gate_metric"
    )
    assert "Build the claim/equivalence inputs" in rows["recompute_claim_gate_required_unavailable"]["operator_instruction"]


def test_repair_packet_materializes_claim_handoff_from_existing_artifacts() -> None:
    stage2_manifest = (
        "runs/wetlab_tcruzi_pde_allatom_rescue/t_cruzi_pde/20_of_20/top_8_strict_then_near_fill/"
        "allatom_rescue_stage2_manifest.csv"
    )
    payload = mod.build_payload(
        burndown_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_focus_artifact": "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
                "selected_allatom_wetlab_gate_pass": True,
                "selected_allatom_final_gate_pass": False,
                "hard_block_count": 1,
                "missing_metric_count": 1,
                "primary_burndown_code": "recompute_claim_gate_required_unavailable",
                "primary_burndown_metric": "claim_gate_required_unavailable",
                "primary_burndown_value": "missing",
                "primary_burndown_threshold": "missing",
                "primary_burndown_delta": "-",
            },
            "rows": [
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
                }
            ],
        },
        review_payload={"summary": {"target_id": "T. cruzi PDE", "wetlab_gate_pass": True}},
        rescue_lane_payload={
            "summary": {
                "base_stage2_manifest_csv": stage2_manifest,
            }
        },
        allatom_runner_payload={
            "summary": {
                "allatom_stage2_manifest_csv": stage2_manifest,
            }
        },
    )

    summary = payload["summary"]
    assert summary["claim_equivalence_input_status"] == "ready_to_build_claim_inputs"
    assert summary["claim_equivalence_missing_inputs"] == [
        "strict_summary_json",
        "accuracy_external_csv",
    ]
    assert summary["claim_equivalence_available_inputs"]["openmm_manifest_csv"] == stage2_manifest
    assert "accuracy_external_csv" not in summary["claim_equivalence_available_inputs"]
    assert summary["claim_equivalence_accuracy_external_candidate_paths"] == [
        "runs/accuracy_gate_local_delivery_preflight_current.csv"
    ]
    assert summary["claim_equivalence_accuracy_external_rejected_candidates"] == [
        {
            "path": "runs/accuracy_gate_local_delivery_preflight_current.csv",
            "reason": (
                "missing_accuracy_external_columns:"
                "avg_rmsd_aligned,avg_rmsd_vs_native_aligned"
            ),
        }
    ]

    commands_by_phase = {item["phase"]: item["command"] for item in summary["command_plan"]}
    assert f"--manifest-csv {stage2_manifest}" in commands_by_phase[
        "claim_inputs_build_after_hard_gate"
    ]
    assert "--kinetics-input-csv runs/kinetics_equivalence_input_real_openmm_" in commands_by_phase[
        "claim_readiness_after_hard_gate"
    ]
    assert "--accuracy-external-csv <accuracy_external.csv>" in commands_by_phase[
        "claim_readiness_after_hard_gate"
    ]
    assert "--strict-summary-json <strict_summary.json>" in commands_by_phase["claim_readiness_after_hard_gate"]
    assert "strict_summary_json" in summary["next_required_step"]
    assert "accuracy_external_csv" in summary["next_required_step"]


def test_repair_packet_uses_valid_accuracy_external_when_present(tmp_path: Path) -> None:
    manifest = tmp_path / "allatom_rescue_stage2_manifest.csv"
    accuracy_external = tmp_path / "accuracy_external.csv"
    manifest.write_text("target,trajectory_npz\nT. cruzi PDE,traj.npz\n", encoding="utf-8")
    _write_accuracy_external_csv(accuracy_external)

    payload = mod.build_payload(
        burndown_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_wetlab_gate_pass": True,
                "selected_allatom_final_gate_pass": False,
                "hard_block_count": 1,
                "missing_metric_count": 1,
                "primary_burndown_code": "recompute_claim_gate_required_unavailable",
                "primary_burndown_metric": "claim_gate_required_unavailable",
                "primary_burndown_value": "missing",
                "primary_burndown_threshold": "missing",
                "primary_burndown_delta": "-",
            },
            "rows": [
                {
                    "severity": "hard",
                    "category": "translation_commercial_hard_gate",
                    "code": "recompute_claim_gate_required_unavailable",
                    "status": "missing",
                }
            ],
        },
        review_payload={"summary": {"target_id": "T. cruzi PDE", "wetlab_gate_pass": True}},
        rescue_lane_payload={"summary": {}},
        allatom_runner_payload={
            "summary": {
                "allatom_stage2_manifest_csv": str(manifest),
                "accuracy_external_csv": str(accuracy_external),
            }
        },
    )

    summary = payload["summary"]
    assert summary["claim_equivalence_missing_inputs"] == ["strict_summary_json"]
    assert summary["claim_equivalence_available_inputs"]["accuracy_external_csv"] == str(accuracy_external)
    assert summary["claim_equivalence_accuracy_external_candidate_paths"] == [
        str(accuracy_external),
        "runs/accuracy_gate_local_delivery_preflight_current.csv",
    ]
    assert summary["claim_equivalence_accuracy_external_rejected_candidates"] == []
    command = {item["phase"]: item["command"] for item in summary["command_plan"]}[
        "claim_readiness_after_hard_gate"
    ]
    assert f"--accuracy-external-csv {accuracy_external}" in command


def test_repair_packet_uses_current_strict_summary_when_present(tmp_path: Path) -> None:
    manifest = tmp_path / "allatom_rescue_stage2_manifest.csv"
    strict_summary = tmp_path / "strict_summary_current.json"
    manifest.write_text("target,trajectory_npz\nT. cruzi PDE,traj.npz\n", encoding="utf-8")
    strict_summary.write_text(
        json.dumps(_strict_summary_payload(manifest)),
        encoding="utf-8",
    )

    payload = mod.build_payload(
        burndown_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_wetlab_gate_pass": True,
                "selected_allatom_final_gate_pass": False,
                "hard_block_count": 1,
                "missing_metric_count": 1,
                "primary_burndown_code": "recompute_claim_gate_required_unavailable",
                "primary_burndown_metric": "claim_gate_required_unavailable",
                "primary_burndown_value": "missing",
                "primary_burndown_threshold": "missing",
                "primary_burndown_delta": "-",
            },
            "rows": [
                {
                    "severity": "hard",
                    "category": "translation_commercial_hard_gate",
                    "code": "recompute_claim_gate_required_unavailable",
                    "status": "missing",
                }
            ],
        },
        review_payload={"summary": {"target_id": "T. cruzi PDE", "wetlab_gate_pass": True}},
        rescue_lane_payload={"summary": {}},
        allatom_runner_payload={
            "summary": {
                "allatom_stage2_manifest_csv": str(manifest),
                "strict_summary_json": str(strict_summary),
            }
        },
    )

    summary = payload["summary"]
    assert "strict_summary_json" not in summary["claim_equivalence_missing_inputs"]
    assert summary["claim_equivalence_available_inputs"]["strict_summary_json"] == str(strict_summary)
    assert summary["claim_equivalence_strict_summary_candidate_paths"] == [str(strict_summary)]
    assert summary["claim_equivalence_rejected_candidates"] == []
    command = {item["phase"]: item["command"] for item in summary["command_plan"]}[
        "claim_readiness_after_hard_gate"
    ]
    assert f"--strict-summary-json {strict_summary}" in command


def test_repair_packet_exposes_archived_strict_summary_without_adopting(tmp_path: Path) -> None:
    manifest = tmp_path / "allatom_rescue_stage2_manifest.csv"
    archived = tmp_path / "archived" / "strict_summary.json"
    manifest.write_text("target,trajectory_npz\nT. cruzi PDE,traj.npz\n", encoding="utf-8")
    archived.parent.mkdir()
    archived.write_text(
        json.dumps(_strict_summary_payload(manifest)),
        encoding="utf-8",
    )

    payload = mod.build_payload(
        burndown_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_wetlab_gate_pass": True,
                "selected_allatom_final_gate_pass": False,
                "hard_block_count": 1,
                "missing_metric_count": 1,
                "primary_burndown_code": "recompute_claim_gate_required_unavailable",
                "primary_burndown_metric": "claim_gate_required_unavailable",
                "primary_burndown_value": "missing",
                "primary_burndown_threshold": "missing",
                "primary_burndown_delta": "-",
            },
            "rows": [
                {
                    "severity": "hard",
                    "category": "translation_commercial_hard_gate",
                    "code": "recompute_claim_gate_required_unavailable",
                    "status": "missing",
                }
            ],
        },
        review_payload={"summary": {"target_id": "T. cruzi PDE", "wetlab_gate_pass": True}},
        rescue_lane_payload={"summary": {}},
        allatom_runner_payload={
            "summary": {
                "allatom_stage2_manifest_csv": str(manifest),
                "strict_summary_json": str(archived),
            }
        },
    )

    summary = payload["summary"]
    assert summary["claim_equivalence_missing_inputs"] == [
        "strict_summary_json",
        "accuracy_external_csv",
    ]
    assert "strict_summary_json" not in summary["claim_equivalence_available_inputs"]
    assert summary["claim_equivalence_strict_summary_candidate_paths"] == [str(archived)]
    assert summary["claim_equivalence_rejected_candidates"] == [
        {"path": str(archived), "reason": "archived_candidate_not_auto_adopted"}
    ]
    command = {item["phase"]: item["command"] for item in summary["command_plan"]}[
        "claim_readiness_after_hard_gate"
    ]
    assert "--strict-summary-json <strict_summary.json>" in command


def test_repair_packet_rejects_rescue_state_json_as_strict_summary(tmp_path: Path) -> None:
    manifest = tmp_path / "allatom_rescue_stage2_manifest.csv"
    rescue_dir = tmp_path / "top_8_strict_then_near_fill"
    rescue_state = rescue_dir / "allatom_rescue_state.json"
    manifest.write_text("target,trajectory_npz\nT. cruzi PDE,traj.npz\n", encoding="utf-8")
    rescue_dir.mkdir()
    rescue_state.write_text(
        json.dumps(
            {
                "summary": {
                    "allatom_stage2_manifest_csv": str(manifest),
                    "source_manifest_csv": str(manifest),
                },
                "rows": [],
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(
        burndown_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_wetlab_gate_pass": True,
                "selected_allatom_final_gate_pass": False,
                "hard_block_count": 1,
                "missing_metric_count": 1,
                "primary_burndown_code": "recompute_claim_gate_required_unavailable",
                "primary_burndown_metric": "claim_gate_required_unavailable",
                "primary_burndown_value": "missing",
                "primary_burndown_threshold": "missing",
                "primary_burndown_delta": "-",
            },
            "rows": [
                {
                    "severity": "hard",
                    "category": "translation_commercial_hard_gate",
                    "code": "recompute_claim_gate_required_unavailable",
                    "status": "missing",
                }
            ],
        },
        review_payload={"summary": {"target_id": "T. cruzi PDE", "wetlab_gate_pass": True}},
        rescue_lane_payload={"summary": {}},
        allatom_runner_payload={
            "summary": {
                "allatom_stage2_manifest_csv": str(manifest),
                "allatom_state_json": str(rescue_state),
            }
        },
    )

    summary = payload["summary"]
    assert summary["claim_equivalence_missing_inputs"] == [
        "strict_summary_json",
        "accuracy_external_csv",
    ]
    assert "strict_summary_json" not in summary["claim_equivalence_available_inputs"]
    assert summary["claim_equivalence_strict_summary_candidate_paths"] == [str(rescue_state)]
    assert summary["claim_equivalence_rejected_candidates"] == [
        {"path": str(rescue_state), "reason": "missing_strict_release_target_count"}
    ]
    command = {item["phase"]: item["command"] for item in summary["command_plan"]}[
        "claim_readiness_after_hard_gate"
    ]
    assert "--strict-summary-json <strict_summary.json>" in command
