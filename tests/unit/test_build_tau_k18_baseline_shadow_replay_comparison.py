from tools.build_tau_k18_baseline_shadow_replay_comparison import build_payload


def test_build_tau_k18_baseline_shadow_replay_comparison_prefers_narrower_safe_mode() -> None:
    payload = build_payload(
        {"pass": True, "baseline_gate_pass": True, "replay_gate_pass": True, "kalman_shadow": {"would_change_state_count": 0, "would_change_gate_count": 0}},
        {"summary": {"anchor_feature_count": 40, "smoothed_feature_count": 40, "changed_row_count": 0}},
        {"pass": True, "baseline_gate_pass": True, "replay_gate_pass": True, "kalman_shadow": {"would_change_state_count": 0, "would_change_gate_count": 0}},
        {"summary": {"anchor_feature_count": 16, "smoothed_feature_count": 16, "changed_row_count": 0}},
    )
    assert payload["recommended_mode"] == "rg_sasa_only"
    assert payload["rows"][0]["mode"] == "ensemble_only"
    assert payload["rows"][1]["smoothed_feature_count"] == 16
