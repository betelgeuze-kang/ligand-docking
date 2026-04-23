from tools.build_idp_literature_anchor_feature_mask_comparison import build_payload


def test_build_idp_literature_anchor_feature_mask_comparison_prefers_narrow_safe_candidate() -> None:
    payload = build_payload(
        {"fold_count": 7, "corrected_pass_folds": 6, "combined_gate_pass": True},
        {"overall": {"would_have_changed_state_count": 11, "would_have_changed_gate_count": 0, "feature_state_shadow_row_count": 48}},
        {"fold_count": 7, "corrected_pass_folds": 6, "combined_gate_pass": True},
        {"overall": {"would_have_changed_state_count": 4, "would_have_changed_gate_count": 0, "feature_state_shadow_row_count": 48}},
    )
    assert payload["decision"] == "prefer_rg_sasa_only"
    assert payload["rows"][1]["feature_mask"] == "rg_sasa_only"
