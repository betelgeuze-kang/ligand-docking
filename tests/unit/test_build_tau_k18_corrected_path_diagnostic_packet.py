from __future__ import annotations

from tools import build_tau_k18_corrected_path_diagnostic_packet as mod


def test_build_tau_k18_corrected_path_diagnostic_packet() -> None:
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
        {"summary": {"dominant_state_accuracy": 0.5, "broader_promotion_blocked": True}},
        {
            "targets": [
                {"condition_group": "base", "true_dominant_state": "helix_enriched", "pred_state": "expanded_disordered", "dominant_state_label": "helix_enriched"},
                {"condition_group": "ph_low", "true_dominant_state": "compact_disordered", "pred_state": "expanded_disordered", "dominant_state_label": "compact_disordered"},
            ]
        },
        out_prefix="runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_basephlow_diag_r1",
    )
    summary = payload["summary"]
    assert summary["packet_scope"] == "tau_k18_corrected_path_single_slice_diagnostic"
    assert summary["operator_scope_now"] == "controlled_shadow_only_commercial_pretest"
    assert summary["shadow_safe_retained"] is True
    assert summary["broader_promotion_blocked"] is True
    assert summary["diagnostic_slice_id"] == "fold6_tau_k18_seed123_base_phlow"
    assert summary["diagnostic_rule_name"] == "short_tau_base_phlow_gate_trace_v1"
    assert summary["diagnostic_rule_scope"] == "corrected_path_observability_only"
    assert summary["focus_condition_count"] == 2
