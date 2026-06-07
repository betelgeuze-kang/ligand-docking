from __future__ import annotations

from tools import build_tools_refactor_gap_closure as mod


def test_tools_refactor_gap_closure_complete() -> None:
    payload = mod.build_tools_refactor_gap_closure(
        other_review_plan_packet={"summary": {"plan_ready": True, "candidate_count": 2, "unclassified_count": 0}},
        batch3_plan_packet={"summary": {"plan_ready": True, "batch3_total_count": 1, "first_slice_candidate_count": 1}},
    )
    summary = payload["summary"]
    assert summary["status"] == "tools_refactor_gap_closure_complete"
    assert summary["all_gaps_closed"] is True
