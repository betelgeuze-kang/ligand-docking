from __future__ import annotations

from tools import build_tau_k18_corrected_path_activation_result as mod


def test_build_tau_k18_corrected_path_activation_result_detects_activation() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "blocking_target": "tau_k18",
                "blocking_class": "corrected_path_fragility",
                "activation_rule_name": "short_tau_diag_r16_activation_v1",
                "activation_rule_scope": "corrected_path_observability_only_env_gate",
            },
            "rows": [
                {"condition_group": "base", "true_state": "helix_enriched"},
                {"condition_group": "ph_low", "true_state": "compact_disordered"},
            ],
        },
        {"summary": {"primary_observation": "short_tau_diagnostic_path_inactive_on_current_corrected_slice"}},
        {"corrected_gate_pass": False, "corrected_dominant_state_accuracy": 0.5, "kalman_shadow": {"would_change_state_count": 0, "would_change_gate_count": 0}},
        {"classification_metrics": {"aggregation_flag_pr_auc": 0.68}},
        {
            "base": {"pred_state": "expanded_disordered", "tau_k18_diag_enabled": True, "tau_k18_diag_focus_condition": True, "tau_k18_diag_state_assignment": "expanded_disordered", "tau_k18_diag_tau_helix_gate": False, "tau_k18_diag_expanded_gate": True, "tau_k18_diag_sticky_gate": False},
            "ph_low": {"pred_state": "expanded_disordered", "tau_k18_diag_enabled": True, "tau_k18_diag_focus_condition": True, "tau_k18_diag_state_assignment": "compact_disordered", "tau_k18_diag_tau_helix_gate": False, "tau_k18_diag_expanded_gate": False, "tau_k18_diag_sticky_gate": False},
        },
    )
    s = payload["summary"]
    assert s["status"] == "activation_slice_completed_path_active"
    assert s["focus_condition_enabled_count"] == 2
    assert s["focus_condition_active_count"] == 2
    assert s["primary_observation"] == "short_tau_diagnostic_path_activated_on_focus_rows"
    assert "bounded commercial-pretest rerun" in s["next_required_step"]
