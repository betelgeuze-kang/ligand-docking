from __future__ import annotations

from tools import build_idp_broader_shadow_result as mod


def test_build_idp_broader_shadow_result_clean_pass() -> None:
    payload = mod.build_payload(
        {"fold_count": 8, "corrected_pass_folds": 8, "pass": True},
        {
            "pass": True,
            "utility_gate_pass": True,
            "physics_gate_pass": True,
            "target_count": 62,
            "classification_metrics": {
                "branch_macro_f1": 1.0,
                "dominant_state_accuracy": 0.95,
                "llps_flag_pr_auc": 0.84,
                "aggregation_relevant_pr_auc": 0.90,
            },
            "ranking_metrics": {
                "compactness_rank_auc": 0.97,
                "helicity_rank_auc": 0.87,
                "condensation_rank_auc": 0.97,
            },
        },
        {
            "target_count": 62,
            "kalman_shadow": {
                "would_change_state_count": 0,
                "would_change_gate_count": 0,
                "would_change_llps_flag_count": 0,
                "would_change_aggregation_flag_count": 0,
            },
        },
        {"summary": {"validated_current_target_count": 7, "additional_anchor_backed_target_count": 1, "provisional_expansion_target_count": 13}},
        {"summary": {"config_json": "config/idp_3bead_benchmark_v7_anchor_plus_page4.json", "out_prefix": "runs/idp_3bead_holdout_v7_broader_shadow_full_r1_debug"}},
        [
            {"target_name": "page4", "pass": True, "dominant_state_accuracy": 1.0, "branch_macro_f1": 1.0, "llps_flag_pr_auc": 0.7, "aggregation_relevant_pr_auc": 0.8, "source_json": "page4.json"},
            {"target_name": "tau_k18", "pass": True, "dominant_state_accuracy": 1.0, "branch_macro_f1": 1.0, "llps_flag_pr_auc": 0.8, "aggregation_relevant_pr_auc": 0.9, "source_json": "tau.json"},
        ],
    )
    summary = payload["summary"]
    assert summary["true_broader_shadow_passed"] is True
    assert summary["page4_fold_pass"] is True
    assert summary["tau_k18_fold_pass"] is True
    assert summary["corrected_pass_folds"] == summary["fold_count"] == 8

