from __future__ import annotations

from tools.product import build_transporter_wave_verdict_notes as mod


def test_build_transporter_wave_verdict_notes() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {"target_id": "AQP1", "wave_label": "first_wave_low_risk"},
                {"target_id": "GLUT1", "wave_label": "second_wave_higher_upside"},
            ]
        },
        {
            "summary": {"next_required_step": "finish aqp1"},
            "rows": [
                {"suggested_external_candidate": "bacopaside II"},
                {"suggested_external_candidate": "AqB013"},
                {"suggested_external_candidate": "AqB011"},
            ],
        },
        {"summary": {"keep_review_only_count": 3, "caution_only_count": 1, "defer_count": 1}},
        {
            "summary": {"next_required_step": "finish glut1"},
            "rows": [
                {"suggested_external_candidate": "cytochalasin B"},
                {"suggested_external_candidate": "WZB117"},
                {"suggested_external_candidate": "STF-31"},
            ],
        },
        {"summary": {"keep_review_only_count": 3, "caution_only_count": 1, "defer_count": 1}},
    )

    assert payload["summary"]["first_wave_target"] == "AQP1"
    assert payload["summary"]["policy_status"] == "reviewer_state_only_blocker_closure"
    assert "blocker-closure target" in payload["summary"]["next_required_step"]
    assert payload["rows"][0]["wave_label"] == "first_wave_low_risk"
    assert payload["rows"][0]["top_candidates"] == "bacopaside II, AqB013, AqB011"
    assert payload["rows"][1]["wave_label"] == "second_wave_higher_upside"
    assert payload["rows"][1]["keep_review_only_count"] == 3
