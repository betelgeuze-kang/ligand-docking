from __future__ import annotations

from tools import build_tau_k18_corrected_path_activation_packet as mod


def test_build_tau_k18_corrected_path_activation_packet() -> None:
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
                "primary_observation": "short_tau_diagnostic_path_inactive_on_current_corrected_slice",
                "inactive_short_tau_diag_count": 2,
            }
        },
        {
            "targets": [
                {"condition_group": "base", "dominant_state_label": "helix_enriched", "pred_state": "expanded_disordered", "tau_k18_diag_enabled": False},
                {"condition_group": "ph_low", "dominant_state_label": "compact_disordered", "pred_state": "expanded_disordered", "tau_k18_diag_enabled": False},
            ]
        },
        out_prefix="runs/idp_tau_k18_activation_trial_commercial_pretest_seed123_r16patch_r1",
    )
    s = payload["summary"]
    assert s["packet_scope"] == "tau_k18_corrected_path_single_slice_activation_check"
    assert s["activation_rule_name"] == "short_tau_diag_r16_activation_v1"
    assert s["activation_rule_scope"] == "corrected_path_observability_only_env_gate"
    assert "--idp-r16-ml-patch 1" in s["exact_command"]
    assert s["reference_primary_observation"] == "short_tau_diagnostic_path_inactive_on_current_corrected_slice"
    assert payload["rows"][0]["condition_group"] == "base"

