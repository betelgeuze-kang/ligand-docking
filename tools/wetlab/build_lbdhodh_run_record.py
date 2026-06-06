#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_LAUNCH_JSON = "runs/lbdhodh_launch_packet_current.json"
DEFAULT_RESULT_REVIEW_JSON = "runs/lbdhodh_result_review_current.json"
DEFAULT_PROGRESS_JSON = "runs/lbdhodh_live_progress_current.json"
DEFAULT_RESULT_JSON = "runs/lbdhodh_result_summary_current.json"
DEFAULT_OUT_MD = "runs/lbdhodh_run_record_current.md"

RUN_STATE_AUTO = "auto"
RUN_STATE_BLOCKED_PREVIOUS = "blocked_on_previous_review"
RUN_STATE_BLOCKED_CONTENT = "blocked_on_target_content"
RUN_STATE_READY = "ready_to_launch"
RUN_STATE_RUNNING = "running"
RUN_STATE_RESULT_READY = "result_ready"
RUN_STATE_EXPLICIT_HOLD = "explicit_hold"
TARGET_ID = "Leishmania braziliensis DHODH"
TRACK_ID = "DNDi_IPK"


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def _first_text(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _resolve_run_state(requested_state: str, upstream_gate_open: bool, content_ready: bool) -> str:
    if requested_state == RUN_STATE_AUTO:
        if not upstream_gate_open:
            return RUN_STATE_BLOCKED_PREVIOUS
        if not content_ready:
            return RUN_STATE_BLOCKED_CONTENT
        return RUN_STATE_READY
    if not upstream_gate_open and requested_state in {RUN_STATE_READY, RUN_STATE_RUNNING, RUN_STATE_RESULT_READY, RUN_STATE_EXPLICIT_HOLD}:
        raise ValueError("LbDHODH run state cannot advance past blocked_on_previous_review while the upstream STK17B gate is still closed.")
    if upstream_gate_open and not content_ready and requested_state in {RUN_STATE_READY, RUN_STATE_RUNNING, RUN_STATE_RESULT_READY, RUN_STATE_EXPLICIT_HOLD}:
        raise ValueError("LbDHODH run state cannot advance while the launch packet is still blocked on compound fill.")
    return requested_state


def _queue_status_for_run_state(run_state: str) -> str:
    if run_state == RUN_STATE_BLOCKED_PREVIOUS:
        return "blocked_on_previous_review"
    if run_state == RUN_STATE_BLOCKED_CONTENT:
        return "blocked_on_target_content"
    if run_state == RUN_STATE_READY:
        return "ready_after_previous_review"
    if run_state == RUN_STATE_RUNNING:
        return "running_active_slot"
    if run_state == RUN_STATE_RESULT_READY:
        return "result_ready_for_final_release"
    if run_state == RUN_STATE_EXPLICIT_HOLD:
        return "explicit_hold_ready_for_final_release"
    raise ValueError(f"Unsupported LbDHODH run state: {run_state}")


def build_payload(
    launch_payload: dict[str, Any],
    result_review_payload: dict[str, Any],
    live_progress: dict[str, Any] | None = None,
    result_summary: dict[str, Any] | None = None,
    run_state: str = RUN_STATE_AUTO,
) -> dict[str, Any]:
    launch_s = _summary(launch_payload)
    review_s = _summary(result_review_payload)
    progress_s = _summary(live_progress or {})
    result_s = _summary(result_summary or {})

    upstream_gate_open = bool(review_s.get("upstream_gate_open", review_s.get("lbdhodh_gate_open", False)))
    upstream_gate_state = str(review_s.get("lbdhodh_review_state", "")).strip() or RUN_STATE_BLOCKED_PREVIOUS
    content_ready = str(launch_s.get("launch_readiness", "")).strip() == "ready_for_serialized_execution"
    progress_status = _first_text(progress_s, "status")
    result_status = _first_text(result_s, "status")
    active_stage_label = _first_text(progress_s, "active_stage_label", "active_stage", "current_stage", "current_step", "step_label")
    started_at = _first_text(progress_s, "started_at", "started_at_local", "run_started_at", "launched_at") or _first_text(result_s, "started_at", "started_at_local", "run_started_at", "launched_at")
    last_update_at = _first_text(progress_s, "updated_at", "updated_at_local", "last_update_at", "last_update_at_local", "ended_at", "ended_at_local") or _first_text(result_s, "updated_at", "updated_at_local", "last_update_at", "last_update_at_local")
    completed_at = _first_text(result_s, "completed_at", "completed_at_local", "ended_at", "ended_at_local", "result_ready_at")

    artifact_explicit_hold = bool(result_s.get("explicit_hold", False)) or result_status == RUN_STATE_EXPLICIT_HOLD
    artifact_result_ready = bool(result_s.get("result_review_ready", False)) or result_status in {"completed", RUN_STATE_RESULT_READY, RUN_STATE_EXPLICIT_HOLD}
    artifact_run_started = bool(progress_s.get("run_started", False)) or bool(result_s.get("run_started", False)) or progress_status in {"running", "completed", RUN_STATE_RESULT_READY, RUN_STATE_EXPLICIT_HOLD} or artifact_result_ready

    if run_state == RUN_STATE_AUTO:
        if not upstream_gate_open:
            execution_state = RUN_STATE_BLOCKED_PREVIOUS
        elif not content_ready:
            execution_state = RUN_STATE_BLOCKED_CONTENT
        elif artifact_explicit_hold:
            execution_state = RUN_STATE_EXPLICIT_HOLD
        elif artifact_result_ready:
            execution_state = RUN_STATE_RESULT_READY
        elif artifact_run_started:
            execution_state = RUN_STATE_RUNNING
        else:
            execution_state = RUN_STATE_READY
    else:
        execution_state = _resolve_run_state(run_state, upstream_gate_open, content_ready)

    queue_status_now = _queue_status_for_run_state(execution_state)
    run_started = execution_state in {RUN_STATE_RUNNING, RUN_STATE_RESULT_READY, RUN_STATE_EXPLICIT_HOLD}
    result_review_ready = execution_state in {RUN_STATE_RESULT_READY, RUN_STATE_EXPLICIT_HOLD}
    explicit_hold = execution_state == RUN_STATE_EXPLICIT_HOLD

    rows = [
        {"record_item": "launch_packet", "artifact_path": "runs/lbdhodh_launch_packet_current.md", "current_signal": str(launch_s.get("status", "")).strip() or "missing_launch_packet", "detail": str(launch_s.get("launch_readiness", "")).strip() or "unknown", "record_role": "freeze_serialized_execution_contract"},
        {"record_item": "result_review_gate", "artifact_path": "runs/lbdhodh_result_review_current.md", "current_signal": str(review_s.get("status", "")).strip() or "missing_result_review", "detail": upstream_gate_state, "record_role": "inherit_upstream_release_gate"},
        {"record_item": "live_progress", "artifact_path": "runs/lbdhodh_live_progress_current.md", "current_signal": progress_status or "not_started", "detail": active_stage_label or execution_state, "record_role": "track_execution_progress"},
        {"record_item": "result_summary", "artifact_path": "runs/lbdhodh_result_summary_current.md", "current_signal": result_status or "not_ready", "detail": execution_state, "record_role": "freeze_result_handoff"},
    ]
    return {
        "summary": {
            "status": execution_state,
            "target_id": TARGET_ID,
            "artifact_kind": "run_record",
            "row_count": len(rows),
            "partner_track_id": str(launch_s.get("partner_track_id", TRACK_ID)).strip() or TRACK_ID,
            "upstream_gate_open": upstream_gate_open,
            "upstream_gate_state": upstream_gate_state,
            "launch_readiness": str(launch_s.get("launch_readiness", "")).strip(),
            "content_ready": content_ready,
            "run_started": run_started,
            "result_review_ready": result_review_ready,
            "explicit_hold": explicit_hold,
            "execution_state": execution_state,
            "queue_status_now": queue_status_now,
            "current_stage": active_stage_label or execution_state,
            "started_at": started_at,
            "updated_at": last_update_at,
            "completed_at": completed_at,
            "next_required_step": "Refresh the LbDHODH result review after every live or result update so the final2 tail gate stays honest.",
        },
        "structured": {
            "launch_artifact": "runs/lbdhodh_launch_packet_current.md",
            "execution_policy": "serialized_by_target",
            "result_handoff": "refresh_lbdhodh_result_review_after_every_live_or_result_update",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the LbDHODH run-record artifact from launch, live-progress, and result-review inputs.")
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--result-review-json", default=DEFAULT_RESULT_REVIEW_JSON)
    parser.add_argument("--progress-json", default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--result-json", default=DEFAULT_RESULT_JSON)
    parser.add_argument("--run-state", default=RUN_STATE_AUTO, choices=[RUN_STATE_AUTO, RUN_STATE_BLOCKED_PREVIOUS, RUN_STATE_BLOCKED_CONTENT, RUN_STATE_READY, RUN_STATE_RUNNING, RUN_STATE_RESULT_READY, RUN_STATE_EXPLICIT_HOLD])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.launch_json), load_json(args.result_review_json), maybe_load_json(args.progress_json), maybe_load_json(args.result_json), run_state=args.run_state)
    write_artifact(DEFAULT_OUT_MD, "LbDHODH Run Record", payload)


if __name__ == "__main__":
    main()
