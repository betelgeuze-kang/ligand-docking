from __future__ import annotations

from tools import build_transporter_verdict_summary as mod


def test_build_transporter_verdict_summary() -> None:
    payload = mod.build_payload(
        {"summary": {"candidate_count": 5, "keep_review_only_count": 3, "caution_only_count": 1, "defer_count": 1}},
        {"summary": {"candidate_count": 5, "keep_review_only_count": 3, "caution_only_count": 1, "defer_count": 1}},
    )

    assert payload["summary"]["family_count"] == 2
    assert payload["summary"]["candidate_count"] == 10
    assert payload["summary"]["keep_review_only_count"] == 6
    assert payload["summary"]["caution_only_count"] == 2
    assert payload["summary"]["defer_count"] == 2
    assert payload["summary"]["policy_status"] == "reviewer_state_only_blocker_closure"
    assert "reviewer-state only" in payload["summary"]["next_required_step"]
    assert payload["rows"][0]["family"] == "aqp1"
    assert payload["rows"][1]["family"] == "glut1"
