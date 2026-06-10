#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    return str(value or "").strip()


def dual_count_ca2_direct_conflicts(
    *,
    conflict_row_count: int,
    workbench_rows: list[dict[str, Any]] | None = None,
    shortlist_rows: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Split CA2 direct-conflict rows into parked review-only vs active blocker work."""
    total = max(0, _int(conflict_row_count))
    shortlist_by_step = {
        _text(row.get("packet_step")): dict(row)
        for row in shortlist_rows or []
        if _text(row.get("packet_step"))
    }
    parked = 0
    active = 0
    for row in workbench_rows or []:
        if _text(row.get("operator_review_bucket")) != "conflict_review":
            continue
        packet_step = _text(row.get("packet_step"))
        shortlist = shortlist_by_step.get(packet_step, {})
        replacement_status = _text(shortlist.get("replacement_status"))
        if replacement_status in {"verified_direct_negative_review_only"}:
            parked += 1
        elif replacement_status in {"proposed_pending_verification", "alternate_pending_verification"}:
            active += 1
        elif replacement_status.startswith("blocked_"):
            active += 1
        elif _text(row.get("next_required_action")) == "keep_review_only_conflict_documented":
            parked += 1
        else:
            active += 1
    if not workbench_rows:
        active = total
        parked = 0
    elif parked + active != total:
        active = max(0, total - parked)
    return {
        "ca2_direct_conflict_row_count": total,
        "ca2_direct_conflict_parked_review_only_count": parked,
        "ca2_direct_conflict_active_blocker_count": active,
    }


def dual_count_pxr_must_defer(
    *,
    must_defer_count: int,
    commit_rows: list[dict[str, Any]] | None = None,
    intake_rows: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Split PXR must-defer rows into parked defer vs active exact-evidence work."""
    total = max(0, _int(must_defer_count))
    intake_by_step = {
        _text(row.get("packet_step")): dict(row)
        for row in intake_rows or []
        if _text(row.get("packet_step"))
    }
    parked = 0
    active = 0
    for row in commit_rows or []:
        if _text(row.get("manual_commit_class")) != "must_remain_deferred":
            continue
        packet_step = _text(row.get("packet_step"))
        intake = intake_by_step.get(packet_step, {})
        conflict_decision = _text(intake.get("conflict_resolution_decision"))
        review_decision = _text(intake.get("review_decision"))
        if conflict_decision in {"KEEP_DEFERRED", "KEEP_BLOCKED"} and review_decision in {
            "KEEP_BLOCKED",
            "KEEP_DEFERRED",
        }:
            parked += 1
        else:
            active += 1
    if not commit_rows:
        active = total
        parked = 0
    elif parked + active != total:
        active = max(0, total - parked)
    return {
        "pxr_must_defer_count": total,
        "pxr_must_defer_parked_review_only_count": parked,
        "pxr_must_defer_active_blocker_count": active,
    }


def science_lane_dual_counts(
    *,
    ca2_direct_conflict_row_count: int,
    ca2_workbench_rows: list[dict[str, Any]] | None = None,
    ca2_shortlist_rows: list[dict[str, Any]] | None = None,
    pxr_must_defer_count: int,
    pxr_commit_rows: list[dict[str, Any]] | None = None,
    pxr_defer_intake_rows: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Merge CA2/PXR science-lane dual counts plus rollup convenience totals."""
    ca2 = dual_count_ca2_direct_conflicts(
        conflict_row_count=ca2_direct_conflict_row_count,
        workbench_rows=ca2_workbench_rows,
        shortlist_rows=ca2_shortlist_rows,
    )
    pxr = dual_count_pxr_must_defer(
        must_defer_count=pxr_must_defer_count,
        commit_rows=pxr_commit_rows,
        intake_rows=pxr_defer_intake_rows,
    )
    return {
        **ca2,
        **pxr,
        "science_lane_parked_review_only_count": ca2["ca2_direct_conflict_parked_review_only_count"]
        + pxr["pxr_must_defer_parked_review_only_count"],
        "science_lane_active_blocker_count": ca2["ca2_direct_conflict_active_blocker_count"]
        + pxr["pxr_must_defer_active_blocker_count"],
    }
