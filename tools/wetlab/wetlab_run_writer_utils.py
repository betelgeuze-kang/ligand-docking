#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

LIVE_PROGRESS_NOT_STARTED = "not_started"
LIVE_PROGRESS_RUNNING = "running"
LIVE_PROGRESS_COMPLETED = "completed"
LIVE_PROGRESS_EXPLICIT_HOLD = "explicit_hold"

RESULT_SUMMARY_NOT_READY = "not_ready"
RESULT_SUMMARY_COMPLETED = "completed"
RESULT_SUMMARY_READY = "result_ready"
RESULT_SUMMARY_EXPLICIT_HOLD = "explicit_hold"

LIVE_PROGRESS_STATUSES = [
    LIVE_PROGRESS_NOT_STARTED,
    LIVE_PROGRESS_RUNNING,
    LIVE_PROGRESS_COMPLETED,
    LIVE_PROGRESS_EXPLICIT_HOLD,
]

RESULT_SUMMARY_STATUSES = [
    RESULT_SUMMARY_NOT_READY,
    RESULT_SUMMARY_COMPLETED,
    RESULT_SUMMARY_READY,
    RESULT_SUMMARY_EXPLICIT_HOLD,
]


def build_live_progress_payload(
    *,
    target_id: str,
    partner_track_id: str,
    launch_artifact: str,
    launch_status: str,
    status: str,
    active_stage_label: str = "",
    started_at: str = "",
    updated_at: str = "",
    notes: str = "",
) -> dict[str, Any]:
    run_started = status in {
        LIVE_PROGRESS_RUNNING,
        LIVE_PROGRESS_COMPLETED,
        LIVE_PROGRESS_EXPLICIT_HOLD,
    }
    current_stage = (
        active_stage_label
        if active_stage_label
        else "execution_in_progress"
        if run_started
        else "launch_packet_frozen_pending_execution"
    )
    next_required_step = (
        "Keep the live progress artifact current until a result summary lands."
        if run_started
        else "Launch the serialized slot and start updating this live progress artifact once execution begins."
    )
    rows = [
        {
            "record_item": "launch_packet",
            "artifact_path": launch_artifact,
            "current_signal": launch_status or "missing_launch_packet",
            "detail": "serialized_slot_frozen",
            "record_role": "freeze_serialized_execution_contract",
        },
        {
            "record_item": "live_progress",
            "artifact_path": "self",
            "current_signal": status,
            "detail": current_stage,
            "record_role": "track_active_execution_before_result_summary",
        },
    ]
    return {
        "summary": {
            "status": status,
            "target_id": target_id,
            "artifact_kind": "live_progress",
            "row_count": len(rows),
            "partner_track_id": partner_track_id,
            "launch_packet_status": launch_status,
            "run_started": run_started,
            "active_stage_label": active_stage_label,
            "current_stage": current_stage,
            "started_at": started_at,
            "updated_at": updated_at,
            "notes": notes,
            "next_required_step": next_required_step,
        },
        "structured": {
            "writer_role": "execution_progress_writer",
            "result_handoff": "refresh_the_matching_result_summary_when_execution_finishes",
        },
        "rows": rows,
    }



def build_result_summary_payload(
    *,
    target_id: str,
    partner_track_id: str,
    launch_artifact: str,
    launch_status: str,
    go_no_go_artifact: str,
    go_no_go_status: str,
    status: str,
    decision_case: str = "",
    action: str = "",
    started_at: str = "",
    updated_at: str = "",
    completed_at: str = "",
    notes: str = "",
) -> dict[str, Any]:
    result_review_ready = status in {
        RESULT_SUMMARY_COMPLETED,
        RESULT_SUMMARY_READY,
        RESULT_SUMMARY_EXPLICIT_HOLD,
    }
    explicit_hold = status == RESULT_SUMMARY_EXPLICIT_HOLD
    next_required_step = (
        "Result review is explicitly held; refresh downstream gates only after the hold decision is frozen."
        if explicit_hold
        else "Result review is ready; refresh downstream gates now."
        if result_review_ready
        else "Keep this result summary pending until the live execution completes or an explicit hold is recorded."
    )
    rows = [
        {
            "record_item": "launch_packet",
            "artifact_path": launch_artifact,
            "current_signal": launch_status or "missing_launch_packet",
            "detail": "serialized_slot_frozen",
            "record_role": "keep_result_summary_bound_to_one_launch_contract",
        },
        {
            "record_item": "go_no_go_card",
            "artifact_path": go_no_go_artifact,
            "current_signal": go_no_go_status or "missing_go_no_go_card",
            "detail": decision_case or action or "classification_rules_ready",
            "record_role": "record_the_decision_context_used_by_downstream_gates",
        },
        {
            "record_item": "result_summary",
            "artifact_path": "self",
            "current_signal": status,
            "detail": decision_case or action or "awaiting_result",
            "record_role": "feed_run_record_and_downstream_gate_refresh",
        },
    ]
    return {
        "summary": {
            "status": status,
            "target_id": target_id,
            "artifact_kind": "result_summary",
            "row_count": len(rows),
            "partner_track_id": partner_track_id,
            "launch_packet_status": launch_status,
            "go_no_go_card_status": go_no_go_status,
            "run_started": bool(started_at or updated_at or completed_at or result_review_ready),
            "result_review_ready": result_review_ready,
            "explicit_hold": explicit_hold,
            "decision_case": decision_case,
            "action": action,
            "started_at": started_at,
            "updated_at": updated_at,
            "completed_at": completed_at,
            "notes": notes,
            "next_required_step": next_required_step,
        },
        "structured": {
            "writer_role": "result_summary_writer",
            "downstream_policy": "run_record_and_gate_refresh_builders_consume_this_artifact",
        },
        "rows": rows,
    }
