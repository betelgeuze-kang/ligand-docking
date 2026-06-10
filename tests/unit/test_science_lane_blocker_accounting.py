from tools.accounting.science_lane_blocker_accounting import (
    dual_count_ca2_direct_conflicts,
    dual_count_pxr_must_defer,
    science_lane_dual_counts,
)


def test_dual_count_ca2_without_workbench_defaults_active() -> None:
    counts = dual_count_ca2_direct_conflicts(conflict_row_count=5)
    assert counts == {
        "ca2_direct_conflict_row_count": 5,
        "ca2_direct_conflict_parked_review_only_count": 0,
        "ca2_direct_conflict_active_blocker_count": 5,
    }


def test_dual_count_ca2_shortlist_marks_active() -> None:
    counts = dual_count_ca2_direct_conflicts(
        conflict_row_count=2,
        workbench_rows=[
            {"operator_review_bucket": "conflict_review", "packet_step": "core_non_binder_01"},
            {"operator_review_bucket": "conflict_review", "packet_step": "core_non_binder_03"},
        ],
        shortlist_rows=[
            {"packet_step": "core_non_binder_01", "replacement_status": "proposed_pending_verification"},
            {"packet_step": "core_non_binder_03", "replacement_status": "proposed_pending_verification"},
        ],
    )
    assert counts["ca2_direct_conflict_active_blocker_count"] == 2
    assert counts["ca2_direct_conflict_parked_review_only_count"] == 0


def test_dual_count_ca2_parked_when_documented_only() -> None:
    counts = dual_count_ca2_direct_conflicts(
        conflict_row_count=1,
        workbench_rows=[
            {
                "operator_review_bucket": "conflict_review",
                "packet_step": "core_non_binder_01",
                "next_required_action": "keep_review_only_conflict_documented",
            }
        ],
        shortlist_rows=[],
    )
    assert counts["ca2_direct_conflict_parked_review_only_count"] == 1
    assert counts["ca2_direct_conflict_active_blocker_count"] == 0


def test_dual_count_ca2_verified_replacement_is_parked() -> None:
    counts = dual_count_ca2_direct_conflicts(
        conflict_row_count=1,
        workbench_rows=[{"operator_review_bucket": "conflict_review", "packet_step": "core_non_binder_01"}],
        shortlist_rows=[
            {"packet_step": "core_non_binder_01", "replacement_status": "verified_direct_negative_review_only"}
        ],
    )
    assert counts["ca2_direct_conflict_parked_review_only_count"] == 1
    assert counts["ca2_direct_conflict_active_blocker_count"] == 0


def test_dual_count_pxr_defer_intake_parked() -> None:
    counts = dual_count_pxr_must_defer(
        must_defer_count=3,
        commit_rows=[
            {"manual_commit_class": "must_remain_deferred", "packet_step": "core_eval_non_binder_01"},
            {"manual_commit_class": "must_remain_deferred", "packet_step": "core_eval_non_binder_02"},
            {"manual_commit_class": "must_remain_deferred", "packet_step": "ood_fit_binder_01"},
        ],
        intake_rows=[
            {
                "packet_step": "core_eval_non_binder_01",
                "conflict_resolution_decision": "KEEP_DEFERRED",
                "review_decision": "KEEP_BLOCKED",
            },
            {
                "packet_step": "core_eval_non_binder_02",
                "conflict_resolution_decision": "KEEP_DEFERRED",
                "review_decision": "KEEP_BLOCKED",
            },
            {
                "packet_step": "ood_fit_binder_01",
                "conflict_resolution_decision": "KEEP_DEFERRED",
                "review_decision": "KEEP_BLOCKED",
            },
        ],
    )
    assert counts == {
        "pxr_must_defer_count": 3,
        "pxr_must_defer_parked_review_only_count": 3,
        "pxr_must_defer_active_blocker_count": 0,
    }


def test_science_lane_dual_counts_merge() -> None:
    counts = science_lane_dual_counts(
        ca2_direct_conflict_row_count=1,
        ca2_workbench_rows=[{"operator_review_bucket": "conflict_review", "packet_step": "a"}],
        ca2_shortlist_rows=[{"packet_step": "a", "replacement_status": "proposed_pending_verification"}],
        pxr_must_defer_count=1,
        pxr_commit_rows=[{"manual_commit_class": "must_remain_deferred", "packet_step": "x"}],
        pxr_defer_intake_rows=[
            {"packet_step": "x", "conflict_resolution_decision": "KEEP_DEFERRED", "review_decision": "KEEP_BLOCKED"}
        ],
    )
    assert counts["science_lane_active_blocker_count"] == 1
    assert counts["science_lane_parked_review_only_count"] == 1
