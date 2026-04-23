from __future__ import annotations

from tools import build_tau_k18_full_fold_corrected_calibration_packet as mod


def test_build_tau_k18_full_fold_corrected_calibration_packet() -> None:
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
            "summary": {
                "tau_k18_corrected_gate_pass": False,
                "dominant_state_accuracy": 0.375,
            },
            "rows": [
                {
                    "condition_group": "base",
                    "true_state": "compact_disordered",
                    "pred_state": "helix_enriched",
                    "state_mismatch": True,
                    "aggregation_mismatch": True,
                    "diag_enabled": True,
                    "diag_focus_condition": True,
                    "diag_state_assignment": "helix_enriched",
                },
                {
                    "condition_group": "ph_low",
                    "true_state": "helix_enriched",
                    "pred_state": "compact_disordered",
                    "state_mismatch": True,
                    "aggregation_mismatch": True,
                    "diag_enabled": True,
                    "diag_focus_condition": True,
                    "diag_state_assignment": "compact_disordered",
                },
            ],
        },
        out_prefix="runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_phhelixrecover_r1",
    )

    summary = payload["summary"]
    assert summary["packet_scope"] == "tau_k18_full_fold_corrected_calibration"
    assert summary["candidate_rule_name"] == "short_tau_ph_shift_helix_recovery_v1"
    assert summary["focus_condition_count"] == 2
    assert "idp-r18-tau-ph-helix-recovery-patch" in summary["exact_command"]
    assert payload["rows"][0]["condition_group"] == "base"
