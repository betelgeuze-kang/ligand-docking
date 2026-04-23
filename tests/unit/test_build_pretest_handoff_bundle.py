from __future__ import annotations

from tools import build_pretest_handoff_bundle as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_pretest_handoff_bundle() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "pretest_ready_count": 4,
                "partial_pretest_ready_count": 2,
                "blocked_pretest_count": 1,
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
            },
            "rows": [],
        },
        {
            "summary": {
                "safe_now": "chembl50_v4_locked_decoy_apply_safe_endpoint",
                "blocked_now": "100k_router_promotion",
            }
        },
        {
            "summary": {
                "allowed_now": "literature_anchor_subset_only",
                "blocked_now": "broader_full_idp_promotion",
                "next_safe_experiment": "expand to next anchor-backed slice",
            }
        },
        {
            "summary": {
                "blocker_reason": "corrected-path fragility remains",
            }
        },
        {
            "summary": {
                "next_required_step": "run the controlled idp commercial pretest",
            }
        },
        {},
        {
            "summary": {
                "ready_row_count": 6,
                "next_required_step": "fill CA2 remaining rows",
            }
        },
        {
            "summary": {
                "review_only_rows": ["ibuprofen"],
                "next_required_step": "keep unresolved PXR rows deferred",
                "policy_line": "keep ibuprofen review-only",
            }
        },
        {
            "summary": {
                "binder_pending_manual_verdict_count": 0,
                "binder_seed_row_count": 6,
                "next_required_step": "keep transporter in manual-review mode",
            }
        },
    )

    assert payload["summary"]["bundle_family_count"] == 5
    assert payload["summary"]["pretest_ready_count"] == 4
    assert payload["summary"]["gpcr_ready_endpoint_only"] is True
    assert payload["summary"]["idp_subset_only"] is True
    assert payload["summary"]["idp_commercial_pretest_ready"] is True
    assert payload["summary"]["idp_broader_shadow_passed"] is False
    assert payload["summary"]["ca2_ready_rows"] == 6
    assert payload["summary"]["pxr_review_only_rows"] == 1
    assert payload["summary"]["transporter_binder_pending_manual_verdict_count"] == 0
    assert payload["summary"]["transporter_seed_row_count"] == 6
    assert payload["rows"][0]["family"] == "gpcr"
    assert payload["rows"][1]["family"] == "idp"
    assert payload["rows"][1]["source_artifact"] == "runs/idp_commercial_pretest_packet_current.md"
    assert payload["rows"][1]["operator_status"] == "subset_safe_controlled_pretest_ready"
    transporter_row = next(row for row in payload["rows"] if row["family"] == "transporter")
    assert transporter_row["source_artifact"] == "runs/transporter_operator_console_current.md"
    assert transporter_row["safe_scope_now"] == "blocker_closure_seed_row_promotion_only"
    assert transporter_row["operator_status"] == "seed_row_blocker_closure_only"
    _contains_tokens(transporter_row["next_safe_experiment"], "aqp1", "seed-row", "promotion")
    _contains_tokens(transporter_row["primary_handoff_note"], "seed-row", "blocker-closure")


def test_build_pretest_handoff_bundle_prefers_idp_commercial_decision() -> None:
    payload = mod.build_payload(
        {"summary": {"pretest_ready_count": 4, "partial_pretest_ready_count": 2, "blocked_pretest_count": 1, "core_commercial_lane_score": 82.5, "all_category_expansion_score": 68.9}, "rows": []},
        {"summary": {"safe_now": "chembl50_v4_locked_decoy_apply_safe_endpoint", "blocked_now": "100k_router_promotion"}},
        {"summary": {"allowed_now": "literature_anchor_subset_only", "blocked_now": "broader_full_idp_promotion", "next_safe_experiment": "expand to next anchor-backed slice"}},
        {"summary": {"blocker_reason": "legacy blocker"}},
        {"summary": {"next_required_step": "run the controlled idp commercial pretest"}},
        {
            "summary": {
                "broader_shadow_passed": True,
                "blocker_reason": "broader shadow passed cleanly; reopen promotion review",
                "next_required_step": "reopen explicit promotion review using the completed broader-shadow result",
            }
        },
        {"summary": {"ready_row_count": 6, "next_required_step": "fill CA2 remaining rows"}},
        {"summary": {"review_only_rows": ["ibuprofen"], "next_required_step": "keep unresolved PXR rows deferred", "policy_line": "keep ibuprofen review-only"}},
        {"summary": {"binder_pending_manual_verdict_count": 0, "binder_seed_row_count": 6}},
        {
            "summary": {
                "blocker_reason": "tau_k18 corrected-path fragility remains the blocker",
                "next_required_step": "keep the current lane and route follow-up through tau_k18 stabilization",
            }
        },
    )
    row = next(r for r in payload["rows"] if r["family"] == "idp")
    assert payload["summary"]["idp_broader_shadow_passed"] is True
    assert row["source_artifact"] == "runs/idp_broader_shadow_decision_current.md"
    assert "broader shadow passed" in row["primary_handoff_note"]
    assert "promotion review" in row["next_safe_experiment"]


def test_build_pretest_handoff_bundle_prefers_broader_promotion_resolution() -> None:
    payload = mod.build_payload(
        {"summary": {"pretest_ready_count": 4, "partial_pretest_ready_count": 2, "blocked_pretest_count": 1, "core_commercial_lane_score": 82.5, "all_category_expansion_score": 68.9}, "rows": []},
        {"summary": {"safe_now": "chembl50_v4_locked_decoy_apply_safe_endpoint", "blocked_now": "100k_router_promotion"}},
        {"summary": {"allowed_now": "literature_anchor_subset_only", "blocked_now": "broader_full_idp_promotion", "next_safe_experiment": "expand to next anchor-backed slice"}},
        {"summary": {"blocker_reason": "legacy blocker"}},
        {"summary": {"next_required_step": "run the controlled idp commercial pretest"}},
        {"summary": {"broader_shadow_passed": True, "blocker_reason": "broader shadow passed cleanly; reopen promotion review", "next_required_step": "reopen explicit promotion review using the completed broader-shadow result"}},
        {"summary": {"ready_row_count": 6, "next_required_step": "fill CA2 remaining rows"}},
        {"summary": {"review_only_rows": ["ibuprofen"], "next_required_step": "keep unresolved PXR rows deferred", "policy_line": "keep ibuprofen review-only"}},
        {"summary": {"binder_pending_manual_verdict_count": 0, "binder_seed_row_count": 6}},
        {"summary": {"blocker_reason": "tau_k18 corrected-path fragility remains the blocker", "next_required_step": "keep the current lane and route follow-up through tau_k18 stabilization"}},
        {"summary": {"wider_shadow_safe_lane_admitted": True, "blocker_reason": "admit one wider shadow-safe lane but keep commercialization blocked", "next_required_step": "run only the admitted one-wider shadow-safe lane", "status": "one_wider_shadow_safe_lane_admitted_not_commercialized"}},
    )
    row = next(r for r in payload["rows"] if r["family"] == "idp")
    assert payload["summary"]["idp_wider_shadow_safe_lane_admitted"] is True
    assert row["source_artifact"] == "runs/idp_broader_promotion_resolution_current.md"
    assert row["safe_scope_now"] == "one_wider_shadow_safe_lane_only"
    assert row["operator_status"] == "one_wider_shadow_safe_lane_only"
    assert "commercialization blocked" in row["primary_handoff_note"]
