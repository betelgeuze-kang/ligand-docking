from __future__ import annotations

from tools import build_idp_broader_shadow_review_resolution as mod


def test_build_idp_broader_shadow_review_resolution_no_additional_anchor() -> None:
    payload = mod.build_payload(
        {"summary": {"operator_scope_now": "controlled_shadow_only_commercial_pretest"}},
        {"summary": {"corrected_pass_folds": 7, "fold_count": 7}},
        {"summary": {"default_feature_mask": "rg_sasa_only"}, "rows": [{"target_name": "alpha_synuclein_full"}, {"target_name": "amyloid_beta_40"}]},
        {"targets": [{"name": "alpha_synuclein_full"}, {"name": "amyloid_beta_40"}]},
        {
            "targets": {
                "alpha_synuclein_full": {"source": "literature_curated_partial"},
                "amyloid_beta_40": {"source": "branch_family_provisional"},
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "broader_shadow_review_resolved_no_additional_anchor_backed_targets"
    assert s["recommended_launch_scope"] == "same_scope_process_check_only"
    assert s["true_broader_rerun_ready"] is False
    assert s["same_scope_process_check_ready"] is True


def test_build_idp_broader_shadow_review_resolution_true_broader_ready_with_page4() -> None:
    payload = mod.build_payload(
        {"summary": {"operator_scope_now": "controlled_shadow_only_commercial_pretest"}},
        {"summary": {"corrected_pass_folds": 7, "fold_count": 7}},
        {"summary": {"default_feature_mask": "rg_sasa_only"}, "rows": [{"target_name": "alpha_synuclein_full"}]},
        {"targets": [{"name": "alpha_synuclein_full"}, {"name": "page4"}, {"name": "amyloid_beta_40"}]},
        {
            "targets": {
                "alpha_synuclein_full": {"source": "literature_curated_partial"},
                "page4": {"source": "literature_curated_partial"},
                "amyloid_beta_40": {"source": "branch_family_provisional"},
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "broader_shadow_review_resolved_true_broader_roster_available"
    assert s["recommended_launch_scope"] == "first_true_broader_shadow_only_not_promotion"
    assert s["true_broader_rerun_ready"] is True
    assert s["same_scope_process_check_ready"] is False
    assert s["additional_anchor_backed_target_count"] == 1
    assert s["config_json"].endswith("config/idp_3bead_benchmark_v7_anchor_plus_page4.json")
    assert "page4" in s["next_required_step"].lower()
