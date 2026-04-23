from __future__ import annotations

from tools import build_tau_k18_config_only_tuning_decision as mod


def test_build_tau_k18_config_only_tuning_decision() -> None:
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
            "pass": False,
            "classification_metrics": {
                "dominant_state_accuracy": 0.5,
                "aggregation_flag_pr_auc": 0.68,
                "llps_flag_pr_auc": 0.0,
            },
            "physics_summary": {
                "hotspots": [{"metrics": ["anti_collapse_force_mean"], "failed_row_count": 8}],
            },
        },
        {
            "pass": False,
            "classification_metrics": {
                "dominant_state_accuracy": 0.5,
                "aggregation_flag_pr_auc": 0.72,
                "llps_flag_pr_auc": 0.0,
            },
            "physics_summary": {
                "hotspots": [{"metrics": ["anti_collapse_force_mean"], "failed_row_count": 8}],
            },
        },
        {
            "pass": False,
            "classification_metrics": {
                "dominant_state_accuracy": 0.5,
                "aggregation_flag_pr_auc": 0.68,
                "llps_flag_pr_auc": 0.0,
            },
            "physics_summary": {
                "hotspots": [{"metrics": ["anti_collapse_force_mean"], "failed_row_count": 8}],
            },
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "config_only_force_policy_tuning_exhausted"
    assert summary["shadow_safe_retained"] is True
    assert summary["config_only_force_policy_tuning_exhausted"] is True
    assert summary["best_aggregation_variant"] == "rg_target_multiplier"
    assert summary["attempted_tweak_count"] == 2
    assert "Stop config-only force-policy tuning" in summary["next_required_step"]
