from __future__ import annotations

from tools import build_gpcr_conditional_prior_promotion_gate as mod


def test_gpcr_conditional_prior_promotion_gate_ready() -> None:
    payload = mod.build_gpcr_conditional_prior_promotion_gate(
        breadth_packet={"summary": {"gpcr_residual_proof_breadth_gate_ready": True, "status": "gpcr_residual_proof_breadth_gate_ready"}},
        ci_low_packet={"summary": {"ranking_pr_auc_ci_low": 0.21, "threshold": 0.45, "ci_low_blocker": True}},
        oprm1_packet={"summary": {"pose_collapse_blocker": True, "blocked_positive_count": 3}},
    )
    summary = payload["summary"]
    assert summary["status"] == "gpcr_conditional_prior_promotion_gate_ready"
    assert summary["claim_promotion_allowed"] is False
    assert summary["promotion_boundary_ready"] is True
