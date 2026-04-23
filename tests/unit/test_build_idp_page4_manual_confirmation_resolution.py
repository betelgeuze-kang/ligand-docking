from __future__ import annotations

from tools import build_idp_page4_manual_confirmation_resolution as mod


def test_build_idp_page4_manual_confirmation_resolution() -> None:
    payload = mod.build_payload({"summary": {"status": "page4_anchor_backed_confirmation_recommendation_ready"}})
    s = payload["summary"]
    assert s["status"] == "page4_manual_confirmation_resolution_ready"
    assert s["accept_with_guardrails_count"] == 2
    assert s["pending_manual_confirmation_count"] == 0
    assert payload["rows"][0]["manual_confirmation_decision"] == "accept_with_guardrails"
