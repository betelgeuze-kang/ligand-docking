from __future__ import annotations

from tools import build_idp_commercial_pretest_validation_packet as mod


def test_build_idp_commercial_pretest_validation_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_target_count": 4,
                "watchlist_target_count": 3,
                "default_feature_mask": "rg_sasa_only",
            },
            "rows": [
                {"target_name": "alpha_synuclein_full", "lane": "commercial_pretest_core", "risk_class": "stable_anchor_backed_core", "recommended_mask": "rg_sasa_only"},
                {"target_name": "tau_k18", "lane": "commercial_pretest_watchlist", "risk_class": "corrected_path_fragility_anchor", "recommended_mask": "rg_sasa_only"},
            ],
        },
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "broader_promotion_blocked": True,
                "shadow_safe_retained": True,
                "default_feature_mask": "rg_sasa_only",
            }
        },
        {
            "summary": {
                "activation_rule_name": "short_tau_diag_r16_activation_v1",
                "status": "activation_slice_completed_path_active",
                "primary_observation": "short_tau_diagnostic_path_activated_on_focus_rows",
            }
        },
        out_prefix="runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r16validation_r1",
    )
    s = payload["summary"]
    assert s["status"] == "operator_validation_packet_ready"
    assert s["validation_scope"] == "bounded_idp_commercial_pretest_rerun"
    assert s["focus_validation_target"] == "tau_k18"
    assert s["activation_status"] == "activation_slice_completed_path_active"
    assert "--resume-existing 0" in s["exact_command"]
    row_map = {row["target_name"]: row for row in payload["rows"]}
    assert row_map["tau_k18"]["validation_priority"] == "focus_blocker_target"
