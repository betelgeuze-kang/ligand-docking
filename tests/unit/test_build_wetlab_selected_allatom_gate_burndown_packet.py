from __future__ import annotations

from tools import build_wetlab_selected_allatom_gate_burndown_packet as mod


def test_build_wetlab_selected_allatom_gate_burndown_packet() -> None:
    payload = mod.build_payload(
        wetlab_dashboard_payload={
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
        },
        wetlab_final_payload={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_best_mean_min_distance_A": 3.705,
                "selected_allatom_promoted_candidate_count": 4,
                "selected_allatom_under_2p5_candidate_count": 0,
                "selected_allatom_near_candidate_count": 2,
                "selected_allatom_effective_actionability_status": "hard_blocked",
                "selected_allatom_effective_primary_blocking_domain": "translation_commercial_hard_gate",
                "selected_allatom_effective_actionability_claim_requirement_reason": "claim/equivalence gate is deprioritized until the hard block clears",
            }
        },
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
