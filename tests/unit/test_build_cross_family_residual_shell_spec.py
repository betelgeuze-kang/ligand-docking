from __future__ import annotations

from tools.product.build_cross_family_residual_shell_spec import build_payload


def test_build_cross_family_residual_shell_spec() -> None:
    layer = {
        "rows": [
            {"family": "gpcr", "current_state": "measured_shadow_and_apply_complete", "shadow_policy": "shadow/apply", "routing_policy": "no_go", "readiness_signal": "no_go"},
            {"family": "ion_channel", "current_state": "locked_decoy_shadow_running", "shadow_policy": "family_noop_shadow_equal_size_locked_decoy", "routing_policy": "baseline", "readiness_signal": "running"},
            {"family": "kinase", "current_state": "locked_decoy_shadow_running", "shadow_policy": "family_noop_shadow_equal_size_locked_decoy", "routing_policy": "baseline", "readiness_signal": "running"},
            {"family": "idp", "current_state": "telemetry_identity_shadow_ready", "shadow_policy": "feature_state_smoothing_only_identity_shadow", "routing_policy": "no coordinate correction", "readiness_signal": "identity_shadow_wired_no_rank_override"},
            {"family": "non_kinase_enzyme_ca2", "current_state": "binding_verification_in_progress", "shadow_policy": "future family token with abstention", "routing_policy": "blocked", "readiness_signal": "ready_rows=3; blocked_rows=9"},
            {"family": "nuclear_receptor_pxr", "current_state": "binding_verification_in_progress", "shadow_policy": "future family token with abstention", "routing_policy": "blocked", "readiness_signal": "ready_rows=4; blocked_rows=10"},
            {"family": "transporter", "current_state": "scaffold_only", "shadow_policy": "strongest abstention defaults", "routing_policy": "unsupported", "readiness_signal": "scaffold_only"},
        ]
    }
    plan = {
        "family_rows": [
            {"family": "gpcr", "shadow_status": "locked_decoy_shadow_validated", "residual_mode": "shadow_then_apply_equal_size_only", "readiness_signal": "locked_decoy_shadow_validated", "next_runnable_step": "anchor"},
            {"family": "idp", "shadow_status": "design_only_feature_state_path", "residual_mode": "shadow_only_no_rank_override", "readiness_signal": "design_only_feature_state_path", "next_runnable_step": "kalman"},
        ]
    }
    payload = build_payload(layer, plan)
    rows = {row["family"]: row for row in payload["family_rows"]}
    assert payload["summary"]["family_token_col"] == "residual_shadow_family"
    assert rows["gpcr"]["token_state"] == "active_measured_family"
    assert rows["gpcr"]["abstain_default"] == "no"
    assert rows["gpcr"]["gpcr_anchor_policy"] == "locked_decoy_equal_size_anchor_required"
    assert rows["idp"]["token_state"] == "placeholder_feature_state_family"
    assert rows["idp"]["idp_kalman_policy"] == "feature_state_smoothing_only_identity_shadow_ready"
    assert rows["non_kinase_enzyme_ca2"]["abstain_default"] == "yes"
