from __future__ import annotations

from tools import build_tau_k18_stabilization_packet as mod


def test_build_tau_k18_stabilization_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "shadow_safe_retained": True,
                "failure_anchor_target": "tau_k18",
                "dominant_state_accuracy": 0.375,
                "dominant_state_threshold": 0.7,
                "branch_macro_f1": 0.3333333333333333,
                "kalman_state_change_count": 0,
                "kalman_gate_change_count": 0,
                "blocker_reason": "tau_k18 corrected-path fragility remains the blocker",
            },
            "row_deltas": [
                {
                    "condition_group": "base",
                    "true_state": "compact_disordered",
                    "baseline_state": "compact_disordered",
                    "corrected_state": "compact_disordered",
                    "corrected_pred_state": "helix_enriched",
                    "baseline_target_pass": 1,
                    "corrected_target_pass": 1,
                    "would_have_changed_state": 0,
                    "would_have_changed_gate": 0,
                    "kf_shadow_state": "compact_disordered",
                }
            ],
        },
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "shadow_safe_retained": True,
                "broader_promotion_blocked": True,
                "blocking_target": "tau_k18",
                "blocking_class": "corrected_path_fragility",
                "decision_reason": "shadow-safe retained but broader promotion blocked",
                "next_required_step": "route follow-up through tau_k18 corrected-path stabilization",
            }
        },
        {
            "summary": {
                "next_trial": {
                    "label": "commercial_pretest_fold6_seed123_fallback",
                    "seed": 123,
                    "epochs": 120,
                    "patience": 24,
                    "lr": 7.5e-4,
                    "weight_decay": 1e-5,
                    "train_npz": "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold6_tau_k18_train_branch_dataset.npz",
                    "eval_config_json": "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold_inputs/fold6_tau_k18_eval.json",
                    "baseline_gate_json": "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold6_tau_k18_gate_baseline_summary.json",
                    "out_prefix": "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_r1",
                    "fixed_feature_mask": "rg_sasa_only",
                    "fixed_kalman_mode": "feature_state_v1",
                    "exact_command": "python3 tools/run_idp_tau_k18_stabilization_trial.py --seed 123",
                },
                "completed_reference_trial": {"seed": 77},
            }
        },
        {
            "seed": 77,
            "pass": False,
            "corrected_gate_pass": False,
            "corrected_dominant_state_accuracy": 0.375,
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "operator_packet_ready"
    assert summary["packet_scope"] == "tau_k18_corrected_path_single_fold_stabilization_fallback"
    assert summary["operator_scope_now"] == "controlled_shadow_only_commercial_pretest"
    assert summary["shadow_safe_retained"] is True
    assert summary["broader_promotion_blocked"] is True
    assert summary["blocking_target"] == "tau_k18"
    assert summary["reference_fail_seed"] == 77
    assert summary["next_trial_seed"] == 123
    assert "run_idp_tau_k18_stabilization_trial.py" in summary["exact_command"]
    assert summary["condition_row_count"] == 1
    assert payload["conditions"][0]["prediction_matches_true_state"] is False
