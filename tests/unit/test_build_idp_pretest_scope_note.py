from __future__ import annotations

from tools import build_idp_pretest_scope_note as mod


def test_build_idp_pretest_scope_note() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "default_feature_mask": "rg_sasa_only",
                "literature_anchor_default_promotion": True,
            }
        }
    )
    assert payload["summary"]["allowed_now"] == "literature_anchor_subset_only"
    assert payload["summary"]["default_feature_mask"] == "rg_sasa_only"
    assert payload["summary"]["blocked_now"] == "broader_full_idp_promotion"
    assert payload["summary"]["subset_safe"] is True
