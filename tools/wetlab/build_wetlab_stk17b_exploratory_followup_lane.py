#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

TARGET_ID = "STK17B (DRAK2)"
FOLLOWUP_LANE_LABEL = "exploratory_gate4.5_followup"
FOLLOWUP_COMMAND_KIND = "throughput_preflight_tuned_gate45"
FOLLOWUP_THRESHOLD_A = 4.5
DEFAULT_TRACE_JSON = "runs/wetlab_stk17b_exploratory_trace_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_FOLLOWUP_REVIEW_SURFACE_JSON = "runs/wetlab_stk17b_followup_review_surface_current.json"
DEFAULT_OUT_MD = "runs/wetlab_stk17b_exploratory_followup_lane_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _shard_number(shard_id: str) -> int:
    text = str(shard_id or "").strip()
    if not text:
        return 0
    try:
        return int(text.split("_of_", 1)[0])
    except Exception:
        return 0


def _make_followup_step(target_id: str, start_shard_id: str, followup_shard_ids: list[str]) -> str:
    followup_text = ";".join(followup_shard_ids)
    if target_id and start_shard_id:
        return (
            f"Run the {target_id} exploratory gate4.5 follow-up runner for {start_shard_id}; "
            + (
                f"keep auto-start hard-frozen after the gate4.5 success and review follow-up shards {followup_text} separately before reopening."
                if followup_text
                else "keep auto-start hard-frozen after the gate4.5 success and review the follow-up shards separately before reopening."
            )
        )
    if target_id:
        return (
            f"Run the {target_id} exploratory gate4.5 follow-up runner; "
            + (
                f"keep auto-start hard-frozen after the gate4.5 success and review follow-up shards {followup_text} separately before reopening."
                if followup_text
                else "keep auto-start hard-frozen after the gate4.5 success and review the follow-up shards separately before reopening."
            )
        )
    return (
        f"Keep auto-start hard-frozen after the exploratory gate4.5 success and review follow-up shards {followup_text} separately before reopening."
        if followup_text
        else "Keep auto-start hard-frozen after the exploratory gate4.5 success and review the follow-up shards separately before reopening."
    )


def _queue_status_map(execution_queue_payload: dict[str, Any] | None, target_id: str) -> dict[str, str]:
    rows = (execution_queue_payload or {}).get("rows", []) or []
    status_map: dict[str, str] = {}
    for row in rows:
        if _text(row.get("target_id")) != target_id:
            continue
        shard_id = _text(row.get("shard_id"))
        if not shard_id:
            continue
        status_map[shard_id] = _text(row.get("queue_status"))
    return status_map


def _followup_review_next_step(review_surface_payload: dict[str, Any] | None) -> str:
    summary = _summary(review_surface_payload)
    if _text(summary.get("target_id")) != TARGET_ID:
        return ""
    if not _text(summary.get("decision")):
        return ""
    return _text(summary.get("next_required_step"))


def _review_rows_by_shard(review_surface_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = (review_surface_payload or {}).get("rows", []) or []
    mapped: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate = dict(row or {})
        if _text(candidate.get("target_id")) != TARGET_ID:
            continue
        shard_id = _text(candidate.get("shard_id"))
        if not shard_id:
            continue
        mapped[shard_id] = candidate
    return mapped


def build_payload(
    trace_payload: dict[str, Any],
    execution_queue_payload: dict[str, Any] | None = None,
    followup_review_surface_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trace_summary = _summary(trace_payload)
    target_id = _text(trace_summary.get("target_id"), TARGET_ID)
    success_shard_id = _text(trace_summary.get("exploratory_success_shard_id"))
    success_number = _shard_number(success_shard_id)
    followup_numbers = [number for number in range(success_number + 1, success_number + 4) if number > 0]
    followup_shard_ids = [f"{number:02d}_of_20" for number in followup_numbers]
    followup_start_shard_id = followup_shard_ids[0] if followup_shard_ids else ""
    followup_end_shard_id = followup_shard_ids[-1] if followup_shard_ids else ""
    queue_status_map = _queue_status_map(execution_queue_payload, target_id)
    review_summary = _summary(followup_review_surface_payload)
    review_rows_by_shard = _review_rows_by_shard(followup_review_surface_payload)
    preserve_gate45_followup = bool(review_summary)
    resolved_statuses = {"result_ready", "explicit_hold"}
    unresolved_followup_shard_ids: list[str] = []
    for shard_id in followup_shard_ids:
        queue_status = queue_status_map.get(shard_id, "")
        if preserve_gate45_followup:
            review_row = review_rows_by_shard.get(shard_id, {})
            command_family = _text(review_row.get("command_family"))
            summary_json = _text(review_row.get("summary_json"))
            consumed_by_gate45 = "gate45" in command_family or "gate45" in summary_json
            if not consumed_by_gate45:
                unresolved_followup_shard_ids.append(shard_id)
            continue
        if queue_status not in resolved_statuses:
            unresolved_followup_shard_ids.append(shard_id)
    if queue_status_map and not unresolved_followup_shard_ids:
        followup_start_shard_id = ""
    elif unresolved_followup_shard_ids:
        followup_start_shard_id = unresolved_followup_shard_ids[0]
    followup_ready = bool(target_id) and bool(success_shard_id) and len(followup_shard_ids) == 3 and bool(followup_start_shard_id)
    followup_text = ";".join(followup_shard_ids)
    followup_review_next_step = _followup_review_next_step(followup_review_surface_payload)
    freeze_note = (
        f"Auto-start remains hard-frozen after the gate4.5 success; follow-up shards {followup_text} are routed to the exploratory gate4.5 follow-up lane and should be reviewed separately before reopening."
        if followup_text
        else "Auto-start remains hard-frozen after the gate4.5 success; the follow-up shards are routed to the exploratory gate4.5 follow-up lane and should be reviewed separately before reopening."
    )
    next_required_step = (
        _make_followup_step(target_id, followup_start_shard_id, followup_shard_ids)
        if followup_ready
        else (
            followup_review_next_step
            if followup_review_next_step
            else
            f"Keep auto-start hard-frozen and review completed follow-up shards {followup_text} before reopening the STK17B (DRAK2) default lane."
            if followup_text
            else "Keep auto-start hard-frozen and review the exploratory follow-up lane before reopening the STK17B (DRAK2) default lane."
        )
    )

    rows = [
        {
            "row_kind": "exploratory_followup_lane",
            "target_id": target_id,
            "shard_id": shard_id,
            "queue_status": (
                queue_status_map.get(shard_id, "ready_for_followup_review")
                if followup_ready
                else queue_status_map.get(shard_id, "blocked")
            ),
            "selected_command_kind": FOLLOWUP_COMMAND_KIND,
            "selected_threshold_A": FOLLOWUP_THRESHOLD_A,
            "command_family": "gate45_exploratory_followup",
            "launch_basis": "hard_freeze_after_exploratory_success",
            "followup_lane_label": FOLLOWUP_LANE_LABEL,
            "followup_shard_ids": ";".join(followup_shard_ids),
            "freeze_state": "hard_freeze_after_exploratory_success",
            "freeze_note": freeze_note,
            "ready_for_manual_retry": followup_ready,
            "next_required_step": next_required_step,
        }
        for shard_id in followup_shard_ids
    ]

    return {
        "summary": {
            "status": "wetlab_stk17b_exploratory_followup_lane_ready" if followup_ready else "wetlab_stk17b_exploratory_followup_lane_blocked",
            "target_id": target_id,
            "campaign_start_shard_id": _text(trace_summary.get("campaign_start_shard_id")),
            "exploratory_success_shard_id": success_shard_id,
            "exploratory_success_command_family": _text(trace_summary.get("exploratory_success_command_family"), "gate45_exploratory"),
            "exploratory_success_threshold_A": float(trace_summary.get("exploratory_success_threshold_A", FOLLOWUP_THRESHOLD_A) or FOLLOWUP_THRESHOLD_A),
            "followup_lane_label": FOLLOWUP_LANE_LABEL,
            "lane_label": FOLLOWUP_LANE_LABEL,
            "shard_id": followup_start_shard_id,
            "followup_start_shard_id": followup_start_shard_id,
            "followup_end_shard_id": followup_end_shard_id,
            "followup_shard_count": len(followup_shard_ids),
            "followup_shard_ids": ";".join(followup_shard_ids),
            "remaining_followup_shard_count": len(unresolved_followup_shard_ids) if queue_status_map else len(followup_shard_ids),
            "completed_followup_shard_count": (
                sum(1 for shard_id in followup_shard_ids if queue_status_map.get(shard_id, "") in resolved_statuses)
                if queue_status_map
                else 0
            ),
            "selected_command_kind": FOLLOWUP_COMMAND_KIND,
            "selected_threshold_A": FOLLOWUP_THRESHOLD_A,
            "hard_freeze_state": "hard_freeze_after_exploratory_success" if followup_shard_ids else "",
            "freeze_note": freeze_note if followup_shard_ids else "",
            "ready_for_manual_retry": followup_ready,
            "next_required_step": next_required_step,
        },
        "structured": {
            "exploratory_trace_artifact": "runs/wetlab_stk17b_exploratory_trace_current.md",
            "success_summary_artifact": "runs/wetlab_broad_screen_throughput/stk17b_drak2/17_of_20/throughput_run_gate45_summary.json",
            "followup_review_surface_artifact": "runs/wetlab_stk17b_followup_review_surface_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the STK17B exploratory gate4.5 follow-up lane.")
    parser.add_argument("--trace-json", default=DEFAULT_TRACE_JSON)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--followup-review-surface-json", default=DEFAULT_FOLLOWUP_REVIEW_SURFACE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab STK17B Exploratory Follow-Up Lane",
        build_payload(
            load_json(args.trace_json),
            load_json(args.execution_queue_json),
            load_json(args.followup_review_surface_json),
        ),
    )


if __name__ == "__main__":
    main()
