from __future__ import annotations

from tools import build_idp_page4_anchor_backed_promotion_review as mod


def test_build_idp_page4_anchor_backed_promotion_review() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "page4_anchor_backed_candidate_decision_pending_manual_confirmation"}},
        {"summary": {"pending_manual_confirmation_count": 2}},
        {
            "summary": {"recommended_accept_with_guardrails_count": 2},
            "rows": [
                {"confirmation_item": "ph_low_freeze_confirmation", "suggested_manual_confirmation_decision": "accept_with_guardrails"},
                {"confirmation_item": "ph_high_freeze_confirmation", "suggested_manual_confirmation_decision": "accept_with_guardrails"},
            ],
        },
    )
    s = payload["summary"]
    assert s["status"] == "page4_anchor_backed_promotion_review_pending_manual_confirmation"
    assert s["confirmation_sheet_ready"] is True
    assert s["recommendation_ready"] is True
    assert s["recommended_accept_with_guardrails_count"] == 2
    assert s["pending_manual_confirmation_count"] == 2
    assert s["promotion_review_ready"] is True
    assert payload["rows"][1]["recommended_manual_confirmation"] == "accept_with_guardrails"
