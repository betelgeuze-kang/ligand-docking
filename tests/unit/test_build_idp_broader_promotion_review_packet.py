from __future__ import annotations

from tools import build_idp_broader_promotion_review_packet as mod


def test_build_idp_broader_promotion_review_packet_marks_wider_lane_candidate_ready() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "true_broader_shadow_passed": True,
                "shadow_safe_retained": True,
                "combined_gate_pass": True,
                "fold_count": 8,
                "corrected_pass_folds": 8,
                "validated_current_target_count": 7,
                "additional_anchor_backed_target_count": 1,
                "page4_fold_pass": True,
                "tau_k18_fold_pass": True,
            }
        },
        {"summary": {"operator_scope_now": "controlled_shadow_only_commercial_pretest"}},
    )
    summary = payload["summary"]
    assert summary["status"] == "broader_promotion_review_packet_ready_wider_lane_candidate"
    assert summary["wider_lane_candidate_ready"] is True
    assert summary["candidate_scope_next"] == "one_wider_shadow_safe_lane_only"
    assert summary["recommended_accept_with_guardrails_count"] == 2

