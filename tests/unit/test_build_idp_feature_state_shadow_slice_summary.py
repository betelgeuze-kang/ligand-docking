from __future__ import annotations

from tools.build_idp_feature_state_shadow_slice_summary import build_payload


def test_build_idp_feature_state_shadow_slice_summary_counts_anchor_policy() -> None:
    payload = build_payload(
        {
            "targets": [
                {
                    "condition_group": "base",
                    "kf_shadow_anchor_policy": "abstain_provisional_anchor",
                    "would_have_changed_state": False,
                    "would_have_changed_llps_flag": False,
                    "would_have_changed_aggregation_flag": False,
                    "would_have_changed_gate": False,
                    "kf_shadow_mean_abs_delta": 0.0,
                    "kf_shadow_max_abs_delta": 0.0,
                },
                {
                    "condition_group": "salt_high",
                    "kf_shadow_anchor_policy": "anchor_backed",
                    "would_have_changed_state": True,
                    "would_have_changed_llps_flag": False,
                    "would_have_changed_aggregation_flag": False,
                    "would_have_changed_gate": False,
                    "kf_shadow_mean_abs_delta": 0.1,
                    "kf_shadow_max_abs_delta": 0.25,
                },
            ],
            "kalman_shadow": {
                "status": "feature_state_v1_shadow",
                "mode": "feature_state_v1",
                "provisional_anchor_row_count": 1,
                "anchor_feature_count": 5,
                "smoothed_feature_count": 5,
                "would_change_state_count": 1,
                "would_change_gate_count": 0,
            },
        }
    )
    assert payload["summary"]["target_count"] == 2
    assert payload["summary"]["changed_row_count"] == 1
    assert payload["summary"]["anchor_policy_counts"]["abstain_provisional_anchor"] == 1
    assert payload["summary"]["anchor_policy_counts"]["anchor_backed"] == 1
