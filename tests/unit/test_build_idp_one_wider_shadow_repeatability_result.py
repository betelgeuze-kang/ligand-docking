from __future__ import annotations

from tools import build_idp_one_wider_shadow_repeatability_result as mod


def test_build_idp_one_wider_shadow_repeatability_result_running() -> None:
    payload = mod.build_payload(
        {"summary": {"operator_scope_now": "one_wider_shadow_safe_lane_only", "out_prefix": "runs/idp_3bead_holdout_v7_onewider_repeatability_r1"}},
        {"summary": {"corrected_pass_folds": 8}},
        {},
        {},
        {},
        [],
    )
    summary = payload["summary"]
    assert summary["status"] == "one_wider_shadow_repeatability_running_or_not_yet_summarized"
    assert summary["summary_exists"] is False
    assert summary["broader_promotion_blocked"] is True


def test_build_idp_one_wider_shadow_repeatability_result_confirmed() -> None:
    payload = mod.build_payload(
        {"summary": {"operator_scope_now": "one_wider_shadow_safe_lane_only", "out_prefix": "runs/idp_3bead_holdout_v7_onewider_repeatability_r1"}},
        {"summary": {"corrected_pass_folds": 8}},
        {"fold_count": 8, "corrected_pass_folds": 8, "pass": True},
        {"pass": True, "classification_metrics": {"dominant_state_accuracy": 0.95}},
        {
            "kalman_shadow": {
                "would_change_state_count": 0,
                "would_change_gate_count": 0,
                "would_change_llps_flag_count": 0,
                "would_change_aggregation_flag_count": 0,
            }
        },
        [
            {"target_name": "tau_k18", "pass": True},
            {"target_name": "page4", "pass": True},
        ],
    )
    summary = payload["summary"]
    assert summary["status"] == "one_wider_shadow_repeatability_confirmed"
    assert summary["shadow_safe_retained"] is True
    assert summary["no_corrected_pass_regression_vs_reference"] is True
    assert summary["page4_fold_pass"] is True
    assert summary["tau_k18_fold_pass"] is True
