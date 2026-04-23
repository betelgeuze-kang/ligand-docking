from __future__ import annotations

from tools import build_idp_commercial_pretest_validation_result as mod


def test_build_idp_commercial_pretest_validation_result_blocker_persists_activation_retained() -> None:
    payload = mod.build_payload(
        {"fold_count": 7, "corrected_pass_folds": 6, "combined_gate_pass": True},
        {"pass": True},
        {"kalman_shadow": {"feature_mask_name": "rg_sasa_only", "would_change_state_count": 0, "would_change_gate_count": 0, "would_change_llps_flag_count": 0, "would_change_aggregation_flag_count": 0}},
        {"pass": False, "classification_metrics": {"dominant_state_accuracy": 0.375, "aggregation_flag_pr_auc": 1.0}},
        {"summary": {"activation_rule_name": "short_tau_diag_r16_activation_v1", "status": "activation_slice_completed_path_active", "primary_observation": "short_tau_diagnostic_path_activated_on_focus_rows"}},
    )
    s = payload["summary"]
    assert s["status"] == "bounded_commercial_pretest_completed_blocker_persists_activation_retained"
    assert s["shadow_safe_retained"] is True
    assert s["tau_k18_corrected_gate_pass"] is False
    assert "full-fold corrected failure slice" in s["next_required_step"]
