from __future__ import annotations

from tools import build_family_manual_review_burndown as mod


def test_build_family_manual_review_burndown() -> None:
    payload = mod.build_payload(
        {"summary": {"ready_row_count": 6, "next_required_step": "fill ca2"}},
        {"summary": {"review_only_negative_count": 6, "defer_binder_count": 0, "policy_fixed_pending_count": 6, "next_required_step": "keep ca2 manual-only"}},
        {"summary": {"ready_for_apply_row_count": 8, "next_required_step": "fill pxr"}},
        {"summary": {"review_only_negative_count": 1, "defer_binder_count": 5, "policy_fixed_pending_count": 6, "next_required_step": "keep pxr manual-only"}},
        {"summary": {"keep_review_only_count": 3, "defer_count": 1, "next_required_step": "aqp1 review"}},
        {"summary": {"pending_manual_verdict_count": 0, "next_required_step": "aqp1 verdicts"}},
        {"summary": {"keep_review_only_count": 3, "defer_count": 1, "next_required_step": "glut1 review"}},
        {"summary": {"pending_manual_verdict_count": 0, "next_required_step": "glut1 verdicts"}},
    )

    assert payload["summary"]["family_count"] == 4
    assert payload["summary"]["ready_count_total"] == 14
    assert payload["summary"]["review_only_count_total"] == 13
    assert payload["summary"]["defer_count_total"] == 7
    assert payload["summary"]["pending_manual_count_total"] == 12
    rows = {row["family"]: row for row in payload["rows"]}
    assert rows["ca2"]["ready_count"] == 6
    assert rows["pxr"]["defer_count"] == 5
    assert rows["aqp1"]["pending_manual_count"] == 0
    assert rows["aqp1"]["current_stage"] == "first_wave_seed_row_promotion"
    assert rows["glut1"]["current_stage"] == "second_wave_seed_row_hold"
