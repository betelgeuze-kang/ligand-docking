from __future__ import annotations

from tools import build_tau_k18_full_fold_corrected_failure_slice_packet as mod


def test_build_tau_k18_full_fold_corrected_failure_slice_packet() -> None:
    payload = mod.build_payload(
        {"summary": {"operator_scope_now": "controlled_shadow_only_commercial_pretest", "shadow_safe_retained": True, "broader_promotion_blocked": True}},
        {"summary": {"status": "bounded_commercial_pretest_completed_blocker_persists_activation_retained", "operator_scope_now": "controlled_shadow_only_commercial_pretest", "shadow_safe_retained": True, "broader_promotion_blocked": True, "activation_observation": "short_tau_diagnostic_path_activated_on_focus_rows", "tau_k18_corrected_gate_pass": False}},
        {
            "targets": [
                {"condition_group": "base", "true_dominant_state": "compact_disordered", "pred_state": "helix_enriched", "true_aggregation_flag": 0, "pred_aggregation_prob": 0.72, "true_llps_flag": 0, "pred_llps_prob": 0.08, "tau_k18_diag_enabled": True, "tau_k18_diag_focus_condition": True, "tau_k18_diag_state_assignment": "helix_enriched", "tau_k18_diag_tau_helix_gate": True, "tau_k18_diag_expanded_gate": False, "tau_k18_diag_sticky_gate": False, "on_anti_collapse_force_mean": 8.5, "compactness_score": -2852.0, "helicity_score": -1.28, "condensation_score": -2055.4},
                {"condition_group": "salt_low", "true_dominant_state": "expanded_disordered", "pred_state": "expanded_disordered", "true_aggregation_flag": 0, "pred_aggregation_prob": 0.21, "true_llps_flag": 0, "pred_llps_prob": 0.08, "tau_k18_diag_enabled": True, "tau_k18_diag_focus_condition": False, "tau_k18_diag_state_assignment": "", "tau_k18_diag_tau_helix_gate": False, "tau_k18_diag_expanded_gate": False, "tau_k18_diag_sticky_gate": False, "on_anti_collapse_force_mean": 8.8, "compactness_score": -2858.9, "helicity_score": -1.30, "condensation_score": -2060.3},
            ]
        },
        {"pass": False, "classification_metrics": {"dominant_state_accuracy": 0.375, "aggregation_flag_pr_auc": 1.0}},
    )
    s = payload["summary"]
    assert s["status"] == "full_fold_failure_slice_packet_ready"
    assert s["mismatch_row_count"] == 1
    assert s["focus_row_count"] == 1
    row = payload["rows"][0]
    assert row["condition_group"] == "base"
    assert row["state_mismatch"] is True
    assert row["aggregation_mismatch"] is True
