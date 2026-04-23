from __future__ import annotations

from tools import build_idp_page4_phosphorylation_fill_draft as mod


def test_build_idp_page4_phosphorylation_fill_draft() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "focus_conditions": "ph_low ; ph_high",
                "low_state_source_anchor": "PMID 26242913",
                "high_state_source_anchor": "PMID 28289210",
            }
        }
    )
    s = payload["summary"]
    assert s["status"] == "page4_phosphorylation_fill_draft_ready"
    assert s["focus_condition_count"] == 2
    assert s["focus_conditions"] == "ph_low ; ph_high"
    assert s["draft_fill_row_count"] == 4
    assert s["readiness_review_artifact"] == "runs/idp_page4_anchor_backed_candidate_readiness_current.md"
    assert s["state_mixing_allowed"] is False
    assert s["promotion_ready"] is False
    assert "readiness review" in s["next_required_step"]
    assert payload["rows"][0]["fill_target"] == "ph_low_candidate_state_note"
    assert payload["rows"][2]["fill_target"] == "ph_high_candidate_state_note"
