from __future__ import annotations

from tools import build_wetlab_selected_allatom_gate_burndown_packet as mod


def _dashboard_payload() -> dict:
    return {
        "summary": {
            "selected_allatom_target_id": "T. cruzi PDE",
            "selected_allatom_focus_artifact": "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
            "selected_allatom_selected_command_kind": "pseudo_allatom_backmapping_rescore",
            "selected_allatom_selected_threshold_A": 2.5,
            "selected_allatom_wetlab_gate_pass": False,
            "selected_allatom_final_gate_pass": False,
            "selected_allatom_claim_gate_available": False,
            "selected_allatom_claim_ready_for_allatom": False,
            "selected_allatom_action_recipe_rollup_text": (
                "hard:recompute_mean_min_distance_A -> repair geometry | "
                "semi_hard:produce_claim_equivalence_packet -> attach claim packet"
            ),
            "selected_allatom_action_recipe_rows": [
                {
                    "severity": "hard",
                    "category": "translation_commercial_hard_gate",
                    "action": "tighten_pose_geometry_under_strict_gate",
                    "calc_action": "recompute_mean_min_distance_A",
                    "status": "failed",
                    "metric": "mean_min_distance_A",
                    "value": "3.705",
                    "threshold": "2.500",
                    "code": "recompute_mean_min_distance_A",
                    "reason": "mean_min_distance_A=3.705 threshold=2.500",
                },
                {
                    "severity": "hard",
                    "category": "translation_commercial_hard_gate",
                    "action": "review_claim_gate_required_unavailable",
                    "calc_action": "recompute_claim_gate_required_unavailable",
                    "status": "missing",
                    "metric": "claim_gate_required_unavailable",
                    "value": "missing",
                    "threshold": "missing",
                    "code": "recompute_claim_gate_required_unavailable",
                    "reason": "claim_gate_required_unavailable=missing",
                },
                {
                    "severity": "semi_hard",
                    "category": "claim_equivalence",
                    "action": "produce_claim_equivalence_packet",
                    "status": "required",
                    "code": "produce_claim_equivalence_packet",
                    "reason": "claim/equivalence packet required",
                },
                {
                    "severity": "semi_hard",
                    "category": "claim_equivalence",
                    "action": "resolve_claim_equivalence_gate",
                    "status": "required",
                    "code": "resolve_claim_equivalence_gate",
                    "reason": "claim/equivalence packet required",
                },
                {
                    "severity": "soft",
                    "category": "next_expensive_lane",
                    "action": "defer_expensive_lane",
                    "status": "deferred",
                    "code": "defer_expensive_lane",
                    "reason": "do not spend stronger-physics budget yet",
                },
            ],
        }
    }


def _final_payload() -> dict:
    return {
        "summary": {
            "selected_allatom_target_id": "T. cruzi PDE",
            "selected_allatom_best_mean_min_distance_A": 3.705,
            "selected_allatom_promoted_candidate_count": 4,
            "selected_allatom_under_2p5_candidate_count": 0,
            "selected_allatom_near_candidate_count": 2,
            "selected_allatom_effective_actionability_status": "hard_blocked",
            "selected_allatom_effective_primary_blocking_domain": "translation_commercial_hard_gate",
            "selected_allatom_effective_actionability_claim_requirement_reason": (
                "claim/equivalence gate is deprioritized until the hard block clears"
            ),
        }
    }


def test_build_wetlab_selected_allatom_gate_burndown_packet() -> None:
    payload = mod.build_payload(
        wetlab_dashboard_payload=_dashboard_payload(),
        wetlab_final_payload=_final_payload(),
    )

    summary = payload["summary"]
    assert summary["packet_ready"] is True
    assert summary["selected_allatom_target_id"] == "T. cruzi PDE"
    assert summary["selected_allatom_focus_artifact"] == "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md"
    assert summary["row_count"] == 5
    assert summary["hard_block_count"] == 2
    assert summary["semi_hard_block_count"] == 2
    assert summary["soft_deferred_count"] == 1
    assert summary["missing_metric_count"] == 1
    assert summary["primary_burndown_code"] == "recompute_mean_min_distance_A"
    assert summary["primary_burndown_metric"] == "mean_min_distance_A"
    assert summary["primary_burndown_delta"] == "1.205"
    assert "claim/equivalence" in summary["next_required_step"]

    rows = {row["code"]: row for row in payload["rows"]}
    assert rows["recompute_mean_min_distance_A"]["operational_bucket"] == "geometry_hard_block"
    assert rows["recompute_claim_gate_required_unavailable"]["operational_bucket"] == "claim_gate_metric_missing"
    assert rows["produce_claim_equivalence_packet"]["operational_bucket"] == "claim_equivalence_block"
    assert rows["defer_expensive_lane"]["operational_bucket"] == "expensive_lane_hold"
    assert "Re-minimize the selected all-atom pose" in rows["recompute_mean_min_distance_A"]["next_required_action"]
    assert rows["produce_claim_equivalence_packet"]["gate_dependency"] == "blocked_until_translation_hard_gate_clears"


def test_review_packet_metric_refreshes_primary_blocker_without_gate_promotion() -> None:
    payload = mod.build_payload(
        wetlab_dashboard_payload=_dashboard_payload(),
        wetlab_final_payload=_final_payload(),
        selected_allatom_review_payload={
            "summary": {
                "target_id": "T. cruzi PDE",
                "best_mean_min_distance_A": 3.375,
                "selected_threshold_A": 2.5,
                "wetlab_gate_pass": False,
                "wetlab_final_gate_pass": False,
                "claim_gate_available": False,
            }
        },
    )

    summary = payload["summary"]
    assert summary["selected_allatom_best_mean_min_distance_A"] == "3.375"
    assert summary["primary_burndown_value"] == "3.375"
    assert summary["primary_burndown_threshold"] == "2.500"
    assert summary["primary_burndown_delta"] == "0.875"
    assert summary["selected_allatom_geometry_wetlab_gate_pass"] is False
    assert summary["selected_allatom_effective_execution_gate_pass"] is False
    assert summary["selected_allatom_wetlab_gate_pass"] is False
    assert summary["selected_allatom_final_gate_pass"] is False
    assert summary["hard_block_count"] == 2
    assert summary["missing_metric_count"] == 1
    assert summary["selected_allatom_metric_source_kind"] == "selected_allatom_review_packet_summary"

    rows = {row["code"]: row for row in payload["rows"]}
    assert rows["recompute_mean_min_distance_A"]["value"] == "3.375"
    assert rows["recompute_mean_min_distance_A"]["threshold"] == "2.500"
    assert rows["recompute_mean_min_distance_A"]["delta"] == "0.875"


def test_review_packet_strict_metric_clears_stale_geometry_hard_blocker() -> None:
    payload = mod.build_payload(
        wetlab_dashboard_payload=_dashboard_payload(),
        wetlab_final_payload=_final_payload(),
        selected_allatom_review_payload={
            "summary": {
                "target_id": "T. cruzi PDE",
                "best_ligand_id": "t_cruzi_pde_20_of_20_095609",
                "best_mean_min_distance_A": 0.672,
                "selected_threshold_A": 2.5,
                "under_2p5_candidate_count": 1,
                "wetlab_gate_pass": True,
                "wetlab_final_gate_pass": False,
                "claim_gate_available": False,
            }
        },
    )

    summary = payload["summary"]
    assert summary["selected_allatom_best_mean_min_distance_A"] == "0.672"
    assert summary["primary_burndown_code"] == "recompute_claim_gate_required_unavailable"
    assert summary["hard_block_count"] == 1
    assert summary["missing_metric_count"] == 1
    assert summary["selected_allatom_metric_source_kind"] == "selected_allatom_review_packet_summary"

    rows = {row["code"]: row for row in payload["rows"]}
    assert "recompute_mean_min_distance_A" not in rows
    assert rows["recompute_claim_gate_required_unavailable"]["burndown_rank"] == 1


def test_satisfied_claim_actions_do_not_remain_as_semi_hard_blockers() -> None:
    dashboard = _dashboard_payload()
    dashboard["summary"].update(
        {
            "selected_allatom_wetlab_gate_pass": True,
            "selected_allatom_final_gate_pass": False,
            "selected_allatom_claim_gate_available": True,
            "selected_allatom_claim_ready_for_allatom": True,
            "selected_allatom_actionability_status": "ready",
            "selected_allatom_action_recipe_rows": [
                {
                    "severity": "semi_hard",
                    "category": "claim_equivalence",
                    "action": "produce_claim_equivalence_packet",
                    "status": "satisfied",
                    "code": "produce_claim_equivalence_packet",
                    "reason": "claim/equivalence evidence is available and passes.",
                },
                {
                    "severity": "semi_hard",
                    "category": "claim_equivalence",
                    "action": "resolve_claim_equivalence_gate",
                    "status": "satisfied",
                    "code": "resolve_claim_equivalence_gate",
                    "reason": "claim/equivalence evidence is available and passes.",
                },
                {
                    "severity": "soft",
                    "category": "next_expensive_lane",
                    "action": "defer_expensive_lane",
                    "status": "deferred",
                    "code": "defer_expensive_lane",
                    "reason": "stronger-physics lane remains optional.",
                },
            ],
        }
    )

    payload = mod.build_payload(
        wetlab_dashboard_payload=dashboard,
        wetlab_final_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_best_mean_min_distance_A": 2.12,
                "selected_allatom_effective_actionability_status": "ready",
            }
        },
        selected_allatom_review_payload={
            "summary": {
                "target_id": "T. cruzi PDE",
                "best_ligand_id": "t_cruzi_pde_20_of_20_095609",
                "best_mean_min_distance_A": 2.12,
                "selected_threshold_A": 2.5,
                "wetlab_gate_pass": True,
                "wetlab_final_gate_pass": True,
                "claim_gate_available": True,
                "claim_ready_for_allatom": True,
            }
        },
    )

    summary = payload["summary"]
    assert summary["selected_allatom_geometry_wetlab_gate_pass"] is True
    assert summary["selected_allatom_effective_execution_gate_pass"] is True
    assert summary["selected_allatom_final_gate_pass"] is True
    assert summary["hard_block_count"] == 0
    assert summary["semi_hard_block_count"] == 0
    assert summary["missing_metric_count"] == 0
    assert summary["primary_burndown_code"] == "defer_expensive_lane"
    assert "Selected all-atom wetlab gate is green" in summary["next_required_step"]
    assert "recompute the missing claim-gate field" not in summary["next_required_step"]
    assert {row["code"] for row in payload["rows"]} == {"defer_expensive_lane"}


def test_review_claim_gap_overrides_stale_satisfied_dashboard_actions() -> None:
    dashboard = _dashboard_payload()
    dashboard["summary"].update(
        {
            "selected_allatom_wetlab_gate_pass": True,
            "selected_allatom_final_gate_pass": True,
            "selected_allatom_claim_gate_available": True,
            "selected_allatom_claim_ready_for_allatom": True,
            "selected_allatom_action_recipe_rows": [
                {
                    "severity": "semi_hard",
                    "category": "claim_equivalence",
                    "action": "produce_claim_equivalence_packet",
                    "status": "satisfied",
                    "code": "produce_claim_equivalence_packet",
                    "reason": "stale claim/equivalence evidence looked available.",
                },
                {
                    "severity": "soft",
                    "category": "next_expensive_lane",
                    "action": "defer_expensive_lane",
                    "status": "deferred",
                    "code": "defer_expensive_lane",
                    "reason": "stronger-physics lane remains optional.",
                },
            ],
        }
    )

    payload = mod.build_payload(
        wetlab_dashboard_payload=dashboard,
        wetlab_final_payload=_final_payload(),
        selected_allatom_review_payload={
            "summary": {
                "target_id": "T. cruzi PDE",
                "best_mean_min_distance_A": 2.12,
                "selected_threshold_A": 2.5,
                "wetlab_gate_pass": True,
                "wetlab_final_gate_pass": False,
                "claim_gate_available": False,
                "claim_gate_satisfied": False,
                "wetlab_final_gate_missing_metrics": ["claim_gate_required_unavailable"],
                "claim_gate_status_reason": "No claim/equivalence artifact is attached yet.",
            }
        },
    )

    summary = payload["summary"]
    assert summary["selected_allatom_geometry_wetlab_gate_pass"] is True
    assert summary["selected_allatom_effective_execution_gate_pass"] is False
    assert summary["selected_allatom_wetlab_gate_pass"] is True
    assert summary["selected_allatom_final_gate_pass"] is False
    assert summary["selected_allatom_claim_gate_available"] is False
    assert summary["selected_allatom_claim_ready_for_allatom"] is False
    assert summary["primary_burndown_code"] == "recompute_claim_gate_required_unavailable"
    assert summary["hard_block_count"] == 1
    assert summary["missing_metric_count"] == 1
    rows = {row["code"]: row for row in payload["rows"]}
    assert rows["recompute_claim_gate_required_unavailable"]["burndown_rank"] == 1
    assert rows["defer_expensive_lane"]["burndown_rank"] == 2


def test_review_commercial_hard_gate_failure_overrides_claim_and_geometry_green() -> None:
    dashboard = _dashboard_payload()
    dashboard["summary"].update(
        {
            "selected_allatom_wetlab_gate_pass": True,
            "selected_allatom_final_gate_pass": True,
            "selected_allatom_claim_gate_available": True,
            "selected_allatom_claim_ready_for_allatom": True,
            "selected_allatom_actionability_status": "ready",
            "selected_allatom_action_recipe_rows": [
                {
                    "severity": "soft",
                    "category": "next_expensive_lane",
                    "action": "defer_expensive_lane",
                    "status": "deferred",
                    "code": "defer_expensive_lane",
                    "reason": "stronger-physics lane remains optional.",
                }
            ],
        }
    )

    payload = mod.build_payload(
        wetlab_dashboard_payload=dashboard,
        wetlab_final_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_best_mean_min_distance_A": 2.12,
                "selected_allatom_effective_actionability_status": "ready",
            }
        },
        selected_allatom_review_payload={
            "summary": {
                "target_id": "T. cruzi PDE",
                "best_ligand_id": "t_cruzi_pde_20_of_20_095609",
                "best_mean_min_distance_A": 2.12,
                "selected_threshold_A": 2.5,
                "wetlab_gate_pass": True,
                "wetlab_final_gate_pass": True,
                "claim_gate_available": True,
                "claim_ready_for_allatom": True,
                "commercial_hard_gate_pass_v2": False,
                "commercial_hard_gate_failed_metrics_v2": [
                    "translation_gate_focus_status",
                    "focus_shortlist_tier",
                    "recommended_next_expensive_lane",
                ],
                "commercial_primary_upgrade_actions_v2": [
                    "clear_translation_hard_gate",
                    "promote_stronger_physics_shortlist",
                    "replace_deferred_expensive_lane_with_validated_repair",
                ],
                "translation_commercial_fail_closed": True,
                "translation_commercial_failed_metrics": [
                    "translation_gate_focus_status",
                    "focus_shortlist_tier",
                    "recommended_next_expensive_lane",
                ],
                "translation_gate_focus_status": "fail",
                "focus_shortlist_tier": "defer",
                "recommended_next_expensive_lane": "defer_expensive_lane",
            }
        },
    )

    summary = payload["summary"]
    assert summary["selected_allatom_geometry_wetlab_gate_pass"] is True
    assert summary["selected_allatom_final_gate_pass"] is True
    assert summary["selected_allatom_claim_ready_for_allatom"] is True
    assert summary["selected_allatom_commercial_hard_gate_pass_v2"] is False
    assert summary["selected_allatom_effective_execution_gate_pass"] is False
    assert summary["hard_block_count"] == 3
    assert summary["semi_hard_block_count"] == 0
    assert summary["missing_metric_count"] == 0
    assert summary["primary_burndown_code"] == "clear_translation_hard_gate"
    assert "Selected all-atom wetlab gate is green" not in summary["next_required_step"]

    rows = {row["code"]: row for row in payload["rows"]}
    assert rows["clear_translation_hard_gate"]["operational_bucket"] == "translation_hard_gate_block"
    assert rows["clear_translation_hard_gate"]["metric"] == "translation_gate_focus_status"
    assert rows["promote_stronger_physics_shortlist"]["metric"] == "focus_shortlist_tier"
    assert rows["replace_deferred_expensive_lane_with_validated_repair"]["metric"] == "recommended_next_expensive_lane"


def test_review_commercial_hard_gate_pass_clears_stale_translation_rows() -> None:
    dashboard = _dashboard_payload()
    dashboard["summary"].update(
        {
            "selected_allatom_wetlab_gate_pass": True,
            "selected_allatom_final_gate_pass": True,
            "selected_allatom_claim_gate_available": True,
            "selected_allatom_claim_ready_for_allatom": True,
            "selected_allatom_action_recipe_rows": [
                {
                    "severity": "hard",
                    "category": "translation_commercial_hard_gate",
                    "action": "review_translation_gate_focus_status",
                    "calc_action": "recompute_translation_gate_focus_status",
                    "status": "failed",
                    "metric": "translation_gate_focus_status",
                    "value": "missing",
                    "threshold": "missing",
                    "code": "recompute_translation_gate_focus_status",
                },
                {
                    "severity": "hard",
                    "category": "translation_commercial_hard_gate",
                    "action": "review_focus_shortlist_tier",
                    "calc_action": "recompute_focus_shortlist_tier",
                    "status": "failed",
                    "metric": "focus_shortlist_tier",
                    "value": "missing",
                    "threshold": "missing",
                    "code": "recompute_focus_shortlist_tier",
                },
                {
                    "severity": "hard",
                    "category": "translation_commercial_hard_gate",
                    "action": "review_recommended_next_expensive_lane",
                    "calc_action": "recompute_recommended_next_expensive_lane",
                    "status": "failed",
                    "metric": "recommended_next_expensive_lane",
                    "value": "missing",
                    "threshold": "missing",
                    "code": "recompute_recommended_next_expensive_lane",
                },
                {
                    "severity": "soft",
                    "category": "next_expensive_lane",
                    "action": "defer_expensive_lane",
                    "status": "deferred",
                    "code": "defer_expensive_lane",
                    "reason": "stale stronger-physics hold",
                },
            ],
        }
    )

    payload = mod.build_payload(
        wetlab_dashboard_payload=dashboard,
        wetlab_final_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_best_mean_min_distance_A": 2.12,
            }
        },
        selected_allatom_review_payload={
            "summary": {
                "target_id": "T. cruzi PDE",
                "best_mean_min_distance_A": 2.12,
                "selected_threshold_A": 2.5,
                "wetlab_gate_pass": True,
                "wetlab_final_gate_pass": True,
                "claim_gate_available": True,
                "claim_ready_for_allatom": True,
                "commercial_hard_gate_pass_v2": True,
                "commercial_hard_gate_failed_metrics_v2": [],
                "commercial_hard_gate_missing_metrics_v2": [],
                "translation_gate_focus_status": "pass",
                "focus_shortlist_tier": "tier2_silver",
                "recommended_next_expensive_lane": "atomized_openmm_local_min_validated_repair",
                "atomized_local_min_evidence_ready": True,
            }
        },
    )

    summary = payload["summary"]
    assert summary["hard_block_count"] == 0
    assert summary["soft_deferred_count"] == 0
    assert summary["selected_allatom_effective_execution_gate_pass"] is True
    assert summary["selected_allatom_translation_gate_focus_status"] == "pass"
    assert summary["selected_allatom_focus_shortlist_tier"] == "tier2_silver"
    assert summary["selected_allatom_recommended_next_expensive_lane"] == "atomized_openmm_local_min_validated_repair"
    assert payload["rows"] == []


def test_binding_proxy_burndown_exposes_repair_provenance_from_review_row() -> None:
    dashboard = _dashboard_payload()
    dashboard["summary"]["selected_allatom_action_recipe_rows"] = [
        {
            "severity": "hard",
            "category": "translation_commercial_hard_gate",
            "action": "strengthen_binding_energy_proxy",
            "calc_action": "recompute_binding_energy_proxy",
            "status": "failed",
            "metric": "binding_energy_proxy",
            "value": "0.113",
            "threshold": "-0.050",
            "code": "recompute_binding_energy_proxy",
            "reason": "binding_energy_proxy=0.113 threshold=-0.050",
        },
        {
            "severity": "semi_hard",
            "category": "claim_equivalence",
            "action": "produce_claim_equivalence_packet",
            "status": "required",
            "code": "produce_claim_equivalence_packet",
            "reason": "claim/equivalence packet required after hard blockers clear",
        },
    ]

    payload = mod.build_payload(
        wetlab_dashboard_payload=dashboard,
        wetlab_final_payload=_final_payload(),
        selected_allatom_review_payload={
            "summary": {
                "target_id": "T. cruzi PDE",
                "best_ligand_id": "t_cruzi_pde_20_of_20_095609",
                "best_mean_min_distance_A": 0.672,
                "selected_threshold_A": 2.5,
                "wetlab_gate_pass": True,
                "wetlab_final_gate_pass": False,
                "claim_gate_available": False,
                "allatom_summary_json": "runs/wetlab_tcruzi_pde_allatom_rescue_summary.json",
            },
            "rows": [
                {
                    "packet_rank": 4,
                    "ligand_id": "t_cruzi_pde_20_of_20_095609",
                    "score_json": "runs/wetlab_tcruzi_pde_allatom_rescue_score.json",
                    "binding_energy_proxy": 0.113,
                }
            ],
        },
    )

    summary = payload["summary"]
    assert summary["primary_burndown_code"] == "recompute_binding_energy_proxy"
    assert summary["primary_burndown_metric"] == "binding_energy_proxy"
    assert summary["primary_repair_lane"] == "tcruzi_pde_allatom_rescue"
    assert (
        summary["primary_repair_action"]
        == "run_clash_relief_allatom_rescue_then_build_review_packet"
    )
    assert summary["primary_repair_source_artifact"] == "runs/wetlab_tcruzi_pde_allatom_rescue_score.json"
    assert summary["primary_repair_source_ligand_id"] == "t_cruzi_pde_20_of_20_095609"
    assert "all hard blocks clear" in summary["next_required_step"]

    rows = {row["code"]: row for row in payload["rows"]}
    assert rows["recompute_binding_energy_proxy"]["operational_bucket"] == "binding_proxy_hard_block"
    assert rows["recompute_binding_energy_proxy"]["repair_lane"] == "tcruzi_pde_allatom_rescue"
    assert rows["produce_claim_equivalence_packet"]["gate_dependency"] == "blocked_until_translation_hard_gate_clears"


def test_binding_proxy_blocker_emits_repair_lane_provenance() -> None:
    dashboard = _dashboard_payload()
    dashboard["summary"]["selected_allatom_action_recipe_rows"][0] = {
        "severity": "hard",
        "category": "translation_commercial_hard_gate",
        "action": "strengthen_binding_energy_proxy",
        "calc_action": "recompute_binding_energy_proxy",
        "status": "failed",
        "metric": "binding_energy_proxy",
        "value": "0.113",
        "threshold": "-0.050",
        "code": "recompute_binding_energy_proxy",
        "reason": "binding_energy_proxy=0.113 threshold=-0.050",
    }
    payload = mod.build_payload(
        wetlab_dashboard_payload=dashboard,
        wetlab_final_payload=_final_payload(),
        selected_allatom_review_payload={
            "summary": {
                "target_id": "T. cruzi PDE",
                "best_ligand_id": "t_cruzi_pde_20_of_20_095609",
                "best_mean_min_distance_A": 0.672,
                "best_binding_energy_proxy": 0.1134023467,
                "selected_threshold_A": 2.5,
                "wetlab_gate_pass": True,
                "wetlab_final_gate_pass": False,
                "claim_gate_available": False,
                "allatom_summary_json": "runs/pde_allatom_summary.json",
            },
            "rows": [
                {
                    "ligand_id": "t_cruzi_pde_20_of_20_095609",
                    "score_json": "runs/pde_ligand_score.json",
                }
            ],
        },
    )

    summary = payload["summary"]
    assert summary["primary_burndown_code"] == "recompute_binding_energy_proxy"
    assert summary["primary_repair_lane"] == "tcruzi_pde_allatom_rescue"
    assert summary["primary_repair_action"] == "run_clash_relief_allatom_rescue_then_build_review_packet"
    assert summary["primary_repair_source_artifact"] == "runs/pde_ligand_score.json"
    assert summary["primary_repair_source_ligand_id"] == "t_cruzi_pde_20_of_20_095609"
    assert "repair_lane=`tcruzi_pde_allatom_rescue`" in summary["next_required_step"]
    rows = {row["code"]: row for row in payload["rows"]}
    assert rows["recompute_binding_energy_proxy"]["operational_bucket"] == "binding_proxy_hard_block"
    assert rows["recompute_binding_energy_proxy"]["repair_source_kind"] == (
        "selected_allatom_review_packet_best_row_binding_energy_proxy"
    )
    assert "binding_energy_proxy is <= -0.050" in rows["recompute_binding_energy_proxy"]["next_required_action"]
