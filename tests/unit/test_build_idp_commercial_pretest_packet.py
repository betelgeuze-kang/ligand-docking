from __future__ import annotations

from tools import build_idp_commercial_pretest_packet as mod


def test_build_idp_commercial_pretest_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "broader_promotion_blocked": True,
                "default_feature_mask": "rg_sasa_only",
                "blocker_reason": "tau_k18 corrected-path fragility remains",
            },
            "rows": [
                {
                    "target_name": "alpha_synuclein_full",
                    "lane": "commercial_pretest_core",
                    "risk_class": "stable_anchor_backed_core",
                    "condition_row_count": 8,
                    "recommended_mask": "rg_sasa_only",
                    "success_criteria": "would_have_changed_state=0; would_have_changed_gate=0; no_corrected_pass_regression",
                    "stop_condition": "stop on any regression",
                    "selection_reason": "stable core",
                },
                {
                    "target_name": "tau_k18",
                    "lane": "commercial_pretest_watchlist",
                    "risk_class": "corrected_path_fragility_anchor",
                    "condition_row_count": 8,
                    "recommended_mask": "rg_sasa_only",
                    "success_criteria": "would_have_changed_state=0; would_have_changed_gate=0; no_corrected_pass_regression",
                    "stop_condition": "stop on any regression",
                    "selection_reason": "watchlist blocker",
                },
            ],
            "suggested_command": [
                "python3",
                "tools/run_idp_3bead_holdout_pipeline.py",
                "--kalman-shadow-feature-mask",
                "rg_sasa_only",
            ],
        }
    )

    summary = payload["summary"]
    assert summary["status"] == "operator_packet_ready"
    assert summary["packet_scope"] == "idp_anchor_backed_shadow_only_commercial_pretest"
    assert summary["broader_promotion_blocked"] is True
    assert summary["core_target_count"] == 1
    assert summary["watchlist_target_count"] == 1
    assert "rg_sasa_only" in summary["recommended_command"]

    rows = {row["target_name"]: row for row in payload["rows"]}
    assert rows["alpha_synuclein_full"]["watchlist_interpretation"] == "Treat as steady anchor-backed comparator only."
    assert rows["tau_k18"]["watchlist_interpretation"] == "Do not use as promotion evidence; use only to detect corrected-path regression."
    assert any("corrected-pass regression" in item for item in payload["failure_gates"])
