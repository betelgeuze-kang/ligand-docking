from __future__ import annotations

from tools import build_tau_k18_corrected_path_calibration_packet as mod


def test_build_tau_k18_corrected_path_calibration_packet() -> None:
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
                "failure_anchor_target": "tau_k18",
            },
            "row_deltas": [
                {
                    "condition_group": "salt_high",
                    "true_state": "helix_enriched",
                    "baseline_pred_state": "expanded_disordered",
                    "corrected_pred_state": "expanded_disordered",
                },
                {
                    "condition_group": "cooling",
                    "true_state": "helix_enriched",
                    "baseline_pred_state": "expanded_disordered",
                    "corrected_pred_state": "expanded_disordered",
                },
                {
                    "condition_group": "base",
                    "true_state": "helix_enriched",
                    "baseline_pred_state": "expanded_disordered",
                    "corrected_pred_state": "expanded_disordered",
                },
                {
                    "condition_group": "ph_low",
                    "true_state": "compact_disordered",
                    "baseline_pred_state": "expanded_disordered",
                    "corrected_pred_state": "expanded_disordered",
                },
            ],
        },
        {
            "corrected_gate_pass": False,
            "corrected_dominant_state_accuracy": 0.5,
        },
        out_prefix="runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_shorttau_helixgate_r1",
    )

    summary = payload["summary"]
    assert summary["packet_scope"] == "tau_k18_corrected_path_single_slice_calibration"
    assert summary["operator_scope_now"] == "controlled_shadow_only_commercial_pretest"
    assert summary["blocking_target"] == "tau_k18"
    assert summary["blocking_class"] == "corrected_path_fragility"
    assert summary["broader_promotion_blocked"] is True
    assert summary["calibration_slice_id"] == "fold6_tau_k18_seed123"
    assert summary["candidate_rule_name"] == "short_tau_helix_anchor_bypass_v1"
    assert summary["candidate_rule_scope"] == "corrected_path_interpretation_only"
    assert "shorttau_helixgate_r1" in summary["exact_command"]
    assert payload["rows"][0]["condition_group"] == "salt_high"
