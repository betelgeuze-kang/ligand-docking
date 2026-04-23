from __future__ import annotations

from tools import build_family_policy_freeze_notes as mod


def test_build_family_policy_freeze_notes() -> None:
    payload = mod.build_payload(
        {"summary": {"review_only_rows": 6, "defer_rows": 0}},
        {"summary": {"review_only_rows": 1, "defer_rows": 5}},
    )
    assert payload["summary"]["family_count"] == 2
    assert "review-only" in payload["rows"][0]["decision"]
    assert "ibuprofen" in payload["rows"][1]["decision"]
    assert "manual-confirmation lane" in payload["rows"][1]["decision"]
