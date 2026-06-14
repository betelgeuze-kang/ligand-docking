from __future__ import annotations

from tools import build_gpcr_conditional_prior_promotion_gate as mod


def test_gpcr_conditional_prior_promotion_gate_blocks_oprm1_even_when_scaffold_ready() -> None:
    payload = mod.build_gpcr_conditional_prior_promotion_gate(
        breadth_packet={"summary": {"gpcr_residual_proof_breadth_gate_ready": True, "status": "gpcr_residual_proof_breadth_gate_ready"}},
        ci_low_packet={"summary": {"ranking_pr_auc_ci_low": 0.7611678630724843, "threshold": 0.45, "ci_low_blocker": False}},
        oprm1_packet={"summary": {"pose_collapse_blocker": True, "blocked_positive_count": 3}},
        oprm1_topology_replay_packet={"summary": {}},
    )
    summary = payload["summary"]
    assert summary["status"] == "blocked_gpcr_conditional_prior_promotion_gate"
    assert summary["claim_promotion_allowed"] is False
    assert summary["promotion_boundary_ready"] is False
    assert summary["ci_low_blocker"] is False
    assert summary["oprm1_collapse_blocker"] is True
    assert summary["blockers"] == ["oprm1_pose_collapse_unresolved"]


def test_gpcr_conditional_prior_promotion_gate_ready_after_ci_and_oprm1_clear() -> None:
    payload = mod.build_gpcr_conditional_prior_promotion_gate(
        breadth_packet={"summary": {"gpcr_residual_proof_breadth_gate_ready": True, "status": "gpcr_residual_proof_breadth_gate_ready"}},
        ci_low_packet={"summary": {"ranking_pr_auc_ci_low": 0.7611678630724843, "threshold": 0.45, "ci_low_blocker": False}},
        oprm1_packet={"summary": {"pose_collapse_blocker": False, "blocked_positive_count": 0}},
    )
    summary = payload["summary"]
    assert summary["status"] == "gpcr_conditional_prior_promotion_gate_ready"
    assert summary["claim_promotion_allowed"] is False
    assert summary["promotion_boundary_ready"] is True
    assert summary["blockers"] == []


def test_gpcr_conditional_prior_promotion_gate_uses_claim_locked_oprm1_replay_repair() -> None:
    payload = mod.build_gpcr_conditional_prior_promotion_gate(
        breadth_packet={"summary": {"gpcr_residual_proof_breadth_gate_ready": True, "status": "gpcr_residual_proof_breadth_gate_ready"}},
        ci_low_packet={"summary": {"ranking_pr_auc_ci_low": 0.7611678630724843}},
        oprm1_packet={"summary": {"pose_collapse_blocker": True, "blocked_positive_count": 3}},
        oprm1_topology_replay_packet={
            "summary": {
                "status": "oprm1_topology_pose_shadow_replay_selected_slice_green_claim_locked",
                "selected_oprm1_target_rank": 1,
                "selected_oprm1_decoys_above_positive": 0,
                "selected_non_oprm1_regression_count": 0,
                "selected_top20_positive_count": 3,
                "claim_promotion_allowed": False,
                "scorer_apply_allowed": False,
                "active_score_locked_to_base": True,
            }
        },
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "gpcr_conditional_prior_promotion_gate_ready"
    assert summary["oprm1_collapse_blocker"] is False
    assert summary["oprm1_pose_repair_evidence_ready"] is True
    assert summary["claim_promotion_allowed"] is False
    assert row["oprm1_topology_replay_selected_target_rank"] == 1
    assert row["oprm1_topology_replay_selected_decoys_above_positive"] == 0
    assert row["blockers"] == ""
