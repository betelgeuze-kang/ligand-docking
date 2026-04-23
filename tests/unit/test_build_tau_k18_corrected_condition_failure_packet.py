from __future__ import annotations

from tools import build_tau_k18_corrected_condition_failure_packet as mod


def test_build_tau_k18_corrected_condition_failure_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "shadow_safe_retained": True,
                "broader_promotion_blocked": True,
                "blocking_target": "tau_k18",
            }
        },
        {
            "classification_metrics": {
                "branch_macro_f1": 0.3333333333333333,
                "dominant_state_accuracy": 0.5,
                "aggregation_flag_pr_auc": 0.68,
                "llps_flag_pr_auc": 0.0,
            },
            "failed_targets": [
                {"condition_group": "base"},
                {"condition_group": "salt_high"},
            ],
            "physics_summary": {
                "hotspots": [
                    {
                        "metrics": ["anti_collapse_force_mean"],
                        "condition_groups": ["base", "salt_high"],
                    }
                ]
            },
        },
        {
            "targets": [
                {
                    "condition_group": "base",
                    "true_dominant_state": "compact_disordered",
                    "pred_state": "helix_enriched",
                    "dominant_state_label": "helix_enriched",
                    "pred_llps_prob": 0.1,
                    "pred_aggregation_prob": 0.25,
                    "pred_rank_compactness": -100.0,
                    "pred_rank_helicity": -1.0,
                    "pred_rank_condensation": -50.0,
                    "on_anti_collapse_force_mean": 2.5,
                    "on_anti_collapse_rg_target_A": 48.9,
                    "conditional_anti_collapse_scale": 1.0,
                    "target_pass": False,
                    "residual_target_pass": True,
                    "would_have_changed_state": False,
                    "would_have_changed_gate": False,
                },
                {
                    "condition_group": "salt_high",
                    "true_dominant_state": "compact_disordered",
                    "pred_state": "helix_enriched",
                    "dominant_state_label": "helix_enriched",
                    "pred_llps_prob": 0.1,
                    "pred_aggregation_prob": 0.24,
                    "pred_rank_compactness": -101.0,
                    "pred_rank_helicity": -1.1,
                    "pred_rank_condensation": -51.0,
                    "on_anti_collapse_force_mean": 2.6,
                    "on_anti_collapse_rg_target_A": 48.9,
                    "conditional_anti_collapse_scale": 1.0,
                    "target_pass": False,
                    "residual_target_pass": True,
                    "would_have_changed_state": False,
                    "would_have_changed_gate": False,
                },
            ]
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "diagnostic_packet_ready"
    assert summary["failed_condition_count"] == 2
    assert summary["primary_hotspot_metric"] == "anti_collapse_force_mean"
    assert summary["shadow_safe_retained"] is True
    assert payload["rows"][0]["condition_group"] == "base"
    assert payload["rows"][0]["pred_state"] == "helix_enriched"
    assert payload["rows"][0]["primary_hotspot_metric"] == "anti_collapse_force_mean"
