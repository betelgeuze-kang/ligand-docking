from __future__ import annotations

from tools import build_tau_k18_corrected_path_diagnostic_result as mod


def test_build_tau_k18_corrected_path_diagnostic_result() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "blocking_target": "tau_k18",
                "blocking_class": "corrected_path_fragility",
                "diagnostic_rule_name": "short_tau_base_phlow_gate_trace_v1",
                "diagnostic_rule_scope": "corrected_path_observability_only",
            },
            "rows": [
                {"condition_group": "base", "true_state": "helix_enriched", "reference_pred_state": "expanded_disordered"},
                {"condition_group": "ph_low", "true_state": "compact_disordered", "reference_pred_state": "expanded_disordered"},
            ],
        },
        {"corrected_gate_pass": False, "corrected_dominant_state_accuracy": 0.5},
        {"classification_metrics": {"aggregation_flag_pr_auc": 0.68}},
        {"corrected_gate_pass": False, "corrected_dominant_state_accuracy": 0.5, "kalman_shadow": {"would_change_state_count": 0, "would_change_gate_count": 0}},
        {"classification_metrics": {"aggregation_flag_pr_auc": 0.68}},
        {
            "base": {
                "pred_state": "expanded_disordered",
                "tau_k18_diag_state_assignment": "expanded_disordered",
                "tau_k18_diag_tau_helix_gate": False,
                "tau_k18_diag_expanded_gate": True,
                "tau_k18_diag_sticky_gate": False,
                "tau_k18_diag_agg_cal_pre_gate": 0.11,
                "tau_k18_diag_agg_cal_post_gate": 0.11,
            },
            "ph_low": {
                "pred_state": "expanded_disordered",
                "tau_k18_diag_state_assignment": "expanded_disordered",
                "tau_k18_diag_tau_helix_gate": False,
                "tau_k18_diag_expanded_gate": True,
                "tau_k18_diag_sticky_gate": False,
                "tau_k18_diag_agg_cal_pre_gate": 0.10,
                "tau_k18_diag_agg_cal_post_gate": 0.10,
            },
        },
    )
    summary = payload["summary"]
    assert summary["status"] == "single_slice_diagnostic_completed_blocker_persists"
    assert summary["shadow_safe_retained"] is True
    assert summary["broader_promotion_blocked"] is True
    assert summary["behavior_change_detected"] is False
    assert summary["debug_columns_present_count"] == 2
    assert summary["expanded_gate_count"] == 2
    assert summary["primary_observation"] == "expanded_gate_dominates_remaining_base_phlow_gap"


def test_build_tau_k18_corrected_path_diagnostic_result_detects_inactive_short_tau_path() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "blocking_target": "tau_k18",
                "blocking_class": "corrected_path_fragility",
                "diagnostic_rule_name": "short_tau_base_phlow_gate_trace_v1",
                "diagnostic_rule_scope": "corrected_path_observability_only",
            },
            "rows": [
                {"condition_group": "base", "true_state": "helix_enriched", "reference_pred_state": "expanded_disordered"},
                {"condition_group": "ph_low", "true_state": "compact_disordered", "reference_pred_state": "expanded_disordered"},
            ],
        },
        {"corrected_gate_pass": False, "corrected_dominant_state_accuracy": 0.5},
        {"classification_metrics": {"aggregation_flag_pr_auc": 0.68}},
        {"corrected_gate_pass": False, "corrected_dominant_state_accuracy": 0.5, "kalman_shadow": {"would_change_state_count": 0, "would_change_gate_count": 0}},
        {"classification_metrics": {"aggregation_flag_pr_auc": 0.68}},
        {
            "base": {
                "pred_state": "expanded_disordered",
                "tau_k18_diag_enabled": False,
                "tau_k18_diag_focus_condition": False,
                "tau_k18_diag_state_assignment": "",
                "tau_k18_diag_tau_helix_gate": False,
                "tau_k18_diag_expanded_gate": False,
                "tau_k18_diag_sticky_gate": False,
                "tau_k18_diag_agg_cal_pre_gate": 0.0,
                "tau_k18_diag_agg_cal_post_gate": 0.0,
            },
            "ph_low": {
                "pred_state": "expanded_disordered",
                "tau_k18_diag_enabled": False,
                "tau_k18_diag_focus_condition": False,
                "tau_k18_diag_state_assignment": "",
                "tau_k18_diag_tau_helix_gate": False,
                "tau_k18_diag_expanded_gate": False,
                "tau_k18_diag_sticky_gate": False,
                "tau_k18_diag_agg_cal_pre_gate": 0.0,
                "tau_k18_diag_agg_cal_post_gate": 0.0,
            },
        },
    )
    summary = payload["summary"]
    assert summary["inactive_short_tau_diag_count"] == 2
    assert summary["expanded_gate_count"] == 0
    assert summary["primary_observation"] == "short_tau_diagnostic_path_inactive_on_current_corrected_slice"
    assert "inactive on base/ph_low" in summary["next_required_step"]
