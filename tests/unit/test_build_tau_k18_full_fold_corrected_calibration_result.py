from __future__ import annotations

from tools import build_tau_k18_full_fold_corrected_calibration_result as mod


def test_build_tau_k18_full_fold_corrected_calibration_result() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "blocking_target": "tau_k18",
                "blocking_class": "corrected_path_fragility",
                "candidate_rule_name": "short_tau_ph_shift_helix_recovery_v1",
                "candidate_rule_scope": "corrected_path_interpretation_only",
            },
            "rows": [
                {
                    "condition_group": "base",
                    "true_state": "compact_disordered",
                    "reference_pred_state": "helix_enriched",
                },
                {
                    "condition_group": "ph_low",
                    "true_state": "helix_enriched",
                    "reference_pred_state": "compact_disordered",
                },
            ],
        },
        {
            "pass": False,
            "classification_metrics": {
                "dominant_state_accuracy": 0.375,
                "aggregation_flag_pr_auc": 1.0,
            },
        },
        {
            "corrected_gate_pass": True,
            "kalman_shadow_feature_mask": "rg_sasa_only",
            "idp_r16_ml_patch": 1,
            "idp_r17_tau_ph_split_patch": 1,
            "idp_r18_tau_ph_helix_recovery_patch": 1,
            "kalman_shadow": {
                "would_change_state_count": 0,
                "would_change_gate_count": 0,
                "would_change_llps_flag_count": 0,
                "would_change_aggregation_flag_count": 0,
            },
        },
        {
            "pass": True,
            "classification_metrics": {
                "dominant_state_accuracy": 0.75,
                "aggregation_flag_pr_auc": 0.9,
            },
        },
        {
            "base": {
                "pred_state": "compact_disordered",
                "pred_aggregation_positive": 0,
                "true_aggregation_flag": 0,
                "tau_k18_diag_tau_helix_gate": False,
                "tau_k18_diag_state_assignment": "compact_disordered",
            },
            "ph_low": {
                "pred_state": "helix_enriched",
                "pred_aggregation_positive": 0,
                "true_aggregation_flag": 0,
                "tau_k18_diag_tau_helix_gate": True,
                "tau_k18_diag_state_assignment": "helix_enriched",
            },
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "full_fold_calibration_completed_local_pass_broader_blocked"
    assert summary["shadow_safe_retained"] is True
    assert summary["candidate_rule_name"] == "short_tau_ph_shift_helix_recovery_v1"
    assert summary["recovered_condition_count"] == 2
    assert summary["idp_r17_tau_ph_split_patch"] == 1
    assert summary["idp_r18_tau_ph_helix_recovery_patch"] == 1
