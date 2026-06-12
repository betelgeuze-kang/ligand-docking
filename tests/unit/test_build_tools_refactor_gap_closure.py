from __future__ import annotations

from tools import build_tools_refactor_gap_closure as mod


def test_tools_refactor_gap_closure_complete() -> None:
    payload = mod.build_tools_refactor_gap_closure(
        other_review_plan_packet={"summary": {"plan_ready": True, "candidate_count": 2, "unclassified_count": 0}},
        batch3_plan_packet={"summary": {"plan_ready": True, "batch3_total_count": 1, "first_slice_candidate_count": 1}},
        batch3_other_review_plan_packet={
            "summary": {"plan_ready": True, "candidate_count": 3, "unclassified_count": 0}
        },
        batch3_lane_decomposition_plan_packet={
            "summary": {"plan_ready": True, "candidate_count": 4, "selected_for_next_slice_count": 1}
        },
        batch3_package_classification_plan_packet={
            "summary": {"plan_ready": True, "candidate_count": 5, "unclassified_count": 0}
        },
    )
    summary = payload["summary"]
    assert summary["status"] == "tools_refactor_gap_closure_complete"
    assert summary["all_gaps_closed"] is True
    assert summary["gap_count"] == 5
    assert "TOOLS-BATCH3-LANES" in summary["closed_gap_ids"]
    assert "TOOLS-BATCH3-PACKAGE-CLASSIFICATION" in summary["closed_gap_ids"]
