from __future__ import annotations

from tools import build_tau_k18_corrected_path_calibration_result as mod


def test_build_tau_k18_corrected_path_calibration_result() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "blocking_target": "tau_k18",
                "blocking_class": "corrected_path_fragility",
                "candidate_rule_name": "short_tau_helix_anchor_bypass_v1",
                "candidate_rule_scope": "corrected_path_interpretation_only",
            },
            "rows": [
                {
                    "condition_group": "salt_high",
                    "true_state": "helix_enriched",
                    "corrected_pred_state": "expanded_disordered",
                },
                {
                    "condition_group": "cooling",
                    "true_state": "helix_enriched",
                    "corrected_pred_state": "expanded_disordered",
                },
            ],
        },
        {
            "corrected_gate_pass": False,
        },
        {
            "classification_metrics": {
                "dominant_state_accuracy": 0.5,
                "aggregation_flag_pr_auc": 0.68,
                "llps_flag_pr_auc": 0.0,
                "branch_macro_f1": 0.3333,
            },
            "ranking_metrics": {"compactness_rank_auc": 0.9},
        },
        {
            "corrected_gate_pass": True,
            "kalman_shadow_feature_mask": "rg_sasa_only",
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
                "aggregation_flag_pr_auc": 0.72,
                "llps_flag_pr_auc": 0.0,
                "branch_macro_f1": 0.3333,
            },
            "ranking_metrics": {"compactness_rank_auc": 0.9},
        },
        {
            "salt_high": {"pred_state": "helix_enriched", "pred_aggregation_prob": 0.31, "pred_llps_prob": 0.13},
            "cooling": {"pred_state": "helix_enriched", "pred_aggregation_prob": 0.30, "pred_llps_prob": 0.13},
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "single_slice_calibration_completed_local_pass_broader_blocked"
    assert summary["shadow_safe_retained"] is True
    assert summary["broader_promotion_blocked"] is True
    assert summary["candidate_rule_name"] == "short_tau_helix_anchor_bypass_v1"
    assert summary["candidate_rule_scope"] == "corrected_path_interpretation_only"
    assert summary["calibration_corrected_gate_pass"] is True
    assert summary["dominant_state_accuracy_delta"] == 0.25
    assert summary["recovered_condition_count"] == 2
