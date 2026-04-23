from __future__ import annotations

from tools import build_idp_broader_promotion_resolution as mod


def test_build_idp_broader_promotion_resolution_admits_bounded_wider_lane() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "wider_lane_candidate_ready": True,
                "frozen_total_target_count": 8,
            }
        },
        {
            "summary": {
                "shadow_safe_retained": True,
                "validated_current_target_count": 7,
                "additional_anchor_backed_target_count": 1,
                "page4_fold_pass": True,
                "tau_k18_fold_pass": True,
            }
        },
    )
    summary = payload["summary"]
    assert summary["decision"] == "one_wider_shadow_safe_lane_admitted"
    assert summary["status"] == "one_wider_shadow_safe_lane_admitted_not_commercialized"
    assert summary["operator_scope_now"] == "one_wider_shadow_safe_lane_only"
    assert summary["blocking_class"] == "bounded_wider_lane_only"
    assert summary["wider_shadow_safe_lane_admitted"] is True
