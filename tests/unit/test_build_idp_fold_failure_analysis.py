from __future__ import annotations

from tools.build_idp_fold_failure_analysis import build_payload


def test_build_idp_fold_failure_analysis_detects_regressed_condition() -> None:
    current_gate = {
        "pass": False,
        "utility_gate_pass": False,
        "physics_gate_pass": True,
        "classification_metrics": {
            "dominant_state_accuracy": 2.0 / 3.0,
            "aggregation_flag_pr_auc": 0.25,
            "aggregation_relevant_pr_auc": 0.0,
            "branch_state_consistency": 0.5,
        },
        "anchor_diagnostics": {
            "rg_mean": {"median_normalized_error": 0.75},
            "ensemble_diversity": {"median_normalized_error": 0.31},
        },
        "gate_context": {"classification_thresholds": {"min_dominant_state_accuracy": 0.7}},
    }
    baseline_gate = {
        "pass": True,
        "utility_gate_pass": True,
        "physics_gate_pass": True,
        "classification_metrics": {
            "dominant_state_accuracy": 5.0 / 6.0,
            "aggregation_flag_pr_auc": 0.25,
            "aggregation_relevant_pr_auc": 0.0,
            "branch_state_consistency": 0.5,
        },
        "anchor_diagnostics": {
            "rg_mean": {"median_normalized_error": 0.75},
            "ensemble_diversity": {"median_normalized_error": 0.31},
        },
    }
    current_rows = [
        {
            "condition_group": "base",
            "true_dominant_state": "helix_enriched",
            "pred_state_prob_helix_enriched": 0.8,
            "pred_state_prob_sticky_condensed": 0.2,
            "kf_shadow_enabled": True,
            "would_have_changed_state": False,
            "would_have_changed_gate": False,
        },
        {
            "condition_group": "salt_high",
            "true_dominant_state": "helix_enriched",
            "pred_state_prob_helix_enriched": 0.2,
            "pred_state_prob_sticky_condensed": 0.8,
            "kf_shadow_enabled": True,
            "would_have_changed_state": False,
            "would_have_changed_gate": False,
        },
    ]
    baseline_rows = [
        {
            "condition_group": "base",
            "true_dominant_state": "helix_enriched",
            "pred_state_prob_helix_enriched": 0.8,
            "pred_state_prob_sticky_condensed": 0.2,
        },
        {
            "condition_group": "salt_high",
            "true_dominant_state": "helix_enriched",
            "pred_state_prob_helix_enriched": 0.8,
            "pred_state_prob_sticky_condensed": 0.2,
        },
    ]

    payload = build_payload(current_gate, baseline_gate, current_rows, baseline_rows)
    assert payload["summary"]["current_pass"] is False
    assert payload["summary"]["baseline_pass"] is True
    assert payload["summary"]["regressed_conditions"] == ["salt_high"]
    assert payload["summary"]["kalman_shadow_regression_signal"] is False
    assert len(payload["row_deltas"]) == 2
