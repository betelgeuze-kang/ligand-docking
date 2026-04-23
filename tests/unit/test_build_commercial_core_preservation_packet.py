from __future__ import annotations

from tools import build_commercial_core_preservation_packet as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_commercial_core_preservation_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "strongest_ready_families": ["kinase", "ion_channel", "gpcr"],
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
            },
            "rows": [
                {"family": "gpcr", "score": 82, "source_artifact": "gpcr.md"},
                {"family": "ion_channel", "score": 88, "source_artifact": "ion.md"},
                {"family": "kinase", "score": 90, "source_artifact": "kinase.md"},
                {"family": "idp", "score": 70, "source_artifact": "idp.md"},
            ],
        },
        {
            "summary": {"run_now_count": 4, "prepare_next_count": 2, "manual_review_only_count": 1},
            "rows": [],
        },
        {"summary": {"router_status": "blocked"}},
        {"summary": {"default_feature_mask": "rg_sasa_only", "blocked_now": "broader_full_idp_promotion"}},
        {"summary": {"cross_family_shadow_status": "completed"}, "rows": []},
    )

    assert payload["summary"]["preservation_family_count"] == 4
    assert payload["summary"]["gpcr_router_status"] == "blocked"
    assert payload["summary"]["idp_blocked_now"] == "broader_full_idp_promotion"
    assert payload["summary"]["cross_family_shadow_status"] == "completed"
    rows = {row["family"]: row for row in payload["rows"]}
    assert rows["gpcr"]["must_preserve"] == "chembl50_v4 locked-decoy apply-safe endpoint parity and no new router promotion"
    _contains_tokens(rows["idp"]["must_preserve"], "legacy", "subset", "basis", "commercial-pretest")
    _contains_tokens(rows["idp"]["safe_scope"], "controlled", "commercial-pretest", "subset", "basis")
    assert "rg_sasa_only" in rows["idp"]["protection_rule"]
    assert rows["idp"]["source_artifact"] == "runs/idp_commercial_pretest_packet_current.md"
