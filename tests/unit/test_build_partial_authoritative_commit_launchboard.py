from __future__ import annotations

from tools import build_partial_authoritative_commit_launchboard as mod


def test_build_partial_authoritative_commit_launchboard_sets_strict_order() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "commit_row_count": 3,
                "confirm_now_row_count": 3,
            },
            "rows": [
                {"ligand": "acetaminophen"},
                {"ligand": "metformin"},
                {"ligand": "caffeine"},
            ],
        },
        {
            "summary": {
                "commit_row_count": 4,
                "confirm_now_count": 1,
                "must_remain_deferred_count": 3,
                "supportive_binder_review_count": 0,
                "confirmed_binder_quantitative_gap_count": 1,
            },
            "rows": [
                {"ligand": "ibuprofen"},
                {"ligand": "acetaminophen"},
                {"ligand": "caffeine"},
                {"ligand": "bexarotene"},
            ],
        },
    )

    assert payload["summary"]["family_count"] == 2
    assert payload["summary"]["launch_stage_count"] == 2
    assert payload["summary"]["today_open_now"] == "runs/ca2_evidence_closure_commit_packet_current.md"
    assert payload["summary"]["today_open_now_label"] == "acetaminophen"
    assert payload["summary"]["next_open_after_current"] == "runs/pxr_pending_resolution_commit_packet_current.md"
    assert payload["summary"]["total_commit_row_count"] == 7
    assert payload["summary"]["total_confirm_now_count"] == 4
    assert payload["summary"]["total_must_remain_deferred_count"] == 3
    assert payload["rows"][0]["family"] == "ca2"
    assert payload["rows"][1]["family"] == "pxr"
    assert payload["rows"][0]["open_after_exhausted"] == "runs/pxr_pending_resolution_commit_packet_current.md"
    assert "quantitative-provenance gap lane" in payload["rows"][1]["finish_line"]
    assert "quantitative provenance" in payload["summary"]["next_required_step"]


def test_build_partial_authoritative_commit_launchboard_checklist_mentions_no_quant_fill() -> None:
    payload = mod.build_payload(
        {"summary": {}, "rows": []},
        {"summary": {}, "rows": []},
    )
    assert any("Do not fill quantitative binding fields" in item for item in payload["checklist"])
