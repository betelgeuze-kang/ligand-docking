from __future__ import annotations

from tools import build_idp_broader_anchor_shadow_scaffold as mod


def test_build_idp_broader_anchor_shadow_scaffold() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "default_feature_mask": "rg_sasa_only",
                "fold_count": 7,
                "corrected_pass_folds": 7,
                "would_have_changed_state_count": 0,
                "would_have_changed_gate_count": 0,
                "blocking_reason": "tau_k18 corrected-path fragility",
            }
        },
        {
            "summary": {
                "allowed_now": "literature_anchor_subset_only",
                "default_feature_mask": "rg_sasa_only",
            }
        },
        {
            "summary": {
                "broader_promotion_blocked": True,
                "subset_safe_scope": "literature_anchor_subset_rg_sasa_only",
                "blocker_reason": "tau_k18 corrected-path fragility",
            }
        },
        {
            "summary": {
                "literature_anchor_slice_count": 3,
            },
            "rows": [
                {
                    "target_name": "hnrnpa1_lcd",
                    "is_literature_anchor": 1,
                    "anchor_source": "literature_curated_partial",
                    "would_change_state_count": 3,
                    "would_change_gate_count": 0,
                },
                {
                    "target_name": "tau_k18",
                    "is_literature_anchor": 1,
                    "anchor_source": "literature_curated_partial",
                    "would_change_state_count": 0,
                    "would_change_gate_count": 0,
                },
                {
                    "target_name": "tp53_tad",
                    "is_literature_anchor": 1,
                    "anchor_source": "literature_curated_partial",
                    "would_change_state_count": 3,
                    "would_change_gate_count": 0,
                },
            ],
        },
        {
            "summary": {
                "subset_targets": [
                    "alpha_synuclein_full",
                    "fus_lcd",
                    "hnrnpa1_lcd",
                    "sic1_ntd",
                    "tardbp_ctd",
                    "tau_k18",
                    "tp53_tad",
                ],
                "subset_condition_counts": {
                    "alpha_synuclein_full": 8,
                    "fus_lcd": 8,
                    "hnrnpa1_lcd": 8,
                    "sic1_ntd": 8,
                    "tardbp_ctd": 8,
                    "tau_k18": 8,
                    "tp53_tad": 8,
                },
            }
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "broader_anchor_shadow_scaffold_ready"
    assert summary["default_feature_mask"] == "rg_sasa_only"
    assert summary["controlled_target_count"] == 7
    assert summary["commercial_pretest_core_count"] == 4
    assert summary["commercial_pretest_watchlist_count"] == 3
    assert summary["broader_promotion_blocked"] is True

    rows = {row["target_name"]: row for row in payload["rows"]}
    assert rows["alpha_synuclein_full"]["lane"] == "commercial_pretest_core"
    assert rows["tau_k18"]["lane"] == "commercial_pretest_watchlist"
    assert rows["tau_k18"]["risk_class"] == "corrected_path_fragility_anchor"
    assert rows["hnrnpa1_lcd"]["state_change_count"] == 3
    assert "require_zero_gate_changes" in payload["guardrails"]
    assert any(m["milestone"] == "run_shadow_only_pretest" for m in payload["milestones"])
