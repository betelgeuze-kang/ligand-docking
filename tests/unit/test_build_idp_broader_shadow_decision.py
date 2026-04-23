from __future__ import annotations

from tools import build_idp_broader_shadow_decision as mod


def test_build_idp_broader_shadow_decision_reopens_promotion_review() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "true_broader_shadow_completed": True,
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
        {"summary": {"operator_scope_now": "controlled_shadow_only_commercial_pretest", "default_feature_mask": "rg_sasa_only"}},
    )
    summary = payload["summary"]
    assert summary["decision"] == "broader_shadow_passed_promotion_review_reopen"
    assert summary["blocking_class"] == "explicit_promotion_decision_required"
    assert summary["broader_promotion_blocked"] is True
