from __future__ import annotations

import pytest

from tools import build_tau_k18_stabilization_result as mod


def test_build_tau_k18_stabilization_result() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "shadow_safe_retained": True,
                "broader_promotion_blocked": True,
                "blocking_target": "tau_k18",
                "blocking_class": "corrected_path_fragility",
            }
        },
        {
            "seed": 77,
            "corrected_gate_pass": False,
            "corrected_dominant_state_accuracy": 0.375,
            "gate_metrics": {
                "aggregation_flag_pr_auc": 0.62,
            },
        },
        {
            "seed": 123,
            "corrected_gate_pass": False,
            "corrected_dominant_state_accuracy": 0.5,
            "kalman_shadow_feature_mask": "rg_sasa_only",
            "kalman_shadow": {
                "feature_mask_name": "rg_sasa_only",
                "would_change_state_count": 0,
                "would_change_gate_count": 0,
            },
        },
        {
            "classification_metrics": {
                "branch_macro_f1": 0.3333333333333333,
                "aggregation_flag_pr_auc": 0.68,
                "llps_flag_pr_auc": 0.0,
            },
            "ranking_metrics": {
                "compactness_rank_auc": 0.57,
                "helicity_rank_auc": 0.44,
                "condensation_rank_auc": 0.53,
            },
            "physics_summary": {
                "failed_row_count": 8,
                "hotspots": [
                    {
                        "metrics": ["anti_collapse_force_mean"],
                        "failed_row_count": 8,
                        "condition_groups": ["base", "salt_high"],
                    }
                ],
            },
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "fallback_trial_completed_blocker_persists"
    assert summary["shadow_safe_retained"] is True
    assert summary["broader_promotion_blocked"] is True
    assert summary["fallback_feature_mask_name"] == "rg_sasa_only"
    assert summary["dominant_state_accuracy_delta_vs_reference"] == 0.125
    assert summary["reference_aggregation_flag_pr_auc"] == 0.62
    assert summary["aggregation_flag_pr_auc_delta_vs_reference"] == pytest.approx(0.06)
    assert summary["primary_hotspot_metric"] == "anti_collapse_force_mean"
    assert summary["primary_hotspot_condition_count"] == 2
    assert "anti_collapse_force_mean" in summary["next_required_step"]
    assert payload["hotspot_conditions"][0]["condition_group"] == "base"
