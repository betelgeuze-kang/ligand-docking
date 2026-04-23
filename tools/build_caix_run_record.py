#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_LAUNCH_JSON = "runs/caix_launch_packet_current.json"
DEFAULT_RESULT_REVIEW_JSON = "runs/caix_result_review_current.json"
DEFAULT_TCRUZI_LAUNCH_JSON = "runs/tcruzi_pde_launch_packet_current.json"
DEFAULT_PROGRESS_JSON = "runs/caix_live_progress_current.json"
DEFAULT_RESULT_JSON = "runs/caix_result_summary_current.json"
DEFAULT_OUT_MD = "runs/caix_run_record_current.md"

RUN_STATE_AUTO = "auto"
RUN_STATE_BLOCKED = "blocked_on_previous_review"
RUN_STATE_READY = "ready_to_launch"
RUN_STATE_RUNNING = "running"
RUN_STATE_RESULT_READY = "result_ready"
RUN_STATE_EXPLICIT_HOLD = "explicit_hold"

VALID_RUN_STATES = [
    RUN_STATE_AUTO,
    RUN_STATE_BLOCKED,
    RUN_STATE_READY,
    RUN_STATE_RUNNING,
    RUN_STATE_RESULT_READY,
    RUN_STATE_EXPLICIT_HOLD,
]


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


def _resolve_run_state(requested_state: str, upstream_gate_open: bool) -> str:
    if requested_state == RUN_STATE_AUTO:
        return RUN_STATE_READY if upstream_gate_open else RUN_STATE_BLOCKED

    if not upstream_gate_open and requested_state in {
        RUN_STATE_READY,
        RUN_STATE_RUNNING,
        RUN_STATE_RESULT_READY,
        RUN_STATE_EXPLICIT_HOLD,
    }:
        raise ValueError(
            "CA IX run state cannot advance past blocked_on_previous_review "
            "while the upstream CA IX gate is still closed."
        )
    return requested_state


def _queue_status_for_run_state(run_state: str) -> str:
    if run_state == RUN_STATE_BLOCKED:
        return "blocked_on_previous_review"
    if run_state == RUN_STATE_READY:
        return "ready_after_previous_review"
    if run_state == RUN_STATE_RUNNING:
        return "running_active_slot"
    if run_state == RUN_STATE_RESULT_READY:
        return "result_ready_for_review"
    if run_state == RUN_STATE_EXPLICIT_HOLD:
        return "explicit_hold_ready_for_review"
    raise ValueError(f"Unsupported CA IX run state: {run_state}")


def build_payload(
    launch_payload: dict[str, Any],
    result_review_payload: dict[str, Any],
    tcruzi_launch_payload: dict[str, Any],
    live_progress: dict[str, Any] | None = None,
    result_summary: dict[str, Any] | None = None,
    run_state: str = RUN_STATE_AUTO,
) -> dict[str, Any]:
    launch_s = _summary(launch_payload)
    review_s = _summary(result_review_payload)
    tcruzi_s = _summary(tcruzi_launch_payload)
    progress_s = _summary(live_progress or {})
    result_s = _summary(result_summary or {})

    upstream_gate_open = bool(review_s.get("caix_gate_open", review_s.get("execution_gate_open", False)))
    upstream_gate_state = (
        str(review_s.get("caix_review_state", "")).strip()
        or RUN_STATE_BLOCKED
    )
    progress_status = _first_text(progress_s, "status")
    result_status = _first_text(result_s, "status")
    active_stage_label = _first_text(
        progress_s,
        "active_stage_label",
        "active_stage",
        "current_stage",
        "current_step",
        "step_label",
    )
    started_at = _first_text(
        progress_s,
        "started_at",
        "started_at_local",
        "run_started_at",
        "launched_at",
    ) or _first_text(
        result_s,
        "started_at",
        "started_at_local",
        "run_started_at",
        "launched_at",
    )
    last_update_at = _first_text(
        progress_s,
        "updated_at",
        "updated_at_local",
        "last_update_at",
        "last_update_at_local",
        "ended_at",
        "ended_at_local",
    ) or _first_text(
        result_s,
        "updated_at",
        "updated_at_local",
        "last_update_at",
        "last_update_at_local",
    )
    completed_at = _first_text(
        result_s,
        "completed_at",
        "completed_at_local",
        "ended_at",
        "ended_at_local",
        "result_ready_at",
    )

    progress_detected = bool(progress_s)
    result_detected = bool(result_s)
    artifact_explicit_hold = bool(result_s.get("explicit_hold", False)) or result_status == RUN_STATE_EXPLICIT_HOLD
    artifact_result_ready = bool(result_s.get("result_review_ready", False)) or result_status in {
        "completed",
        RUN_STATE_RESULT_READY,
        RUN_STATE_EXPLICIT_HOLD,
    }
    artifact_run_started = (
        bool(progress_s.get("run_started", False))
        or bool(result_s.get("run_started", False))
        or progress_status in {"running", "completed", RUN_STATE_RESULT_READY, RUN_STATE_EXPLICIT_HOLD}
        or artifact_result_ready
    )

    if run_state == RUN_STATE_AUTO:
        if not upstream_gate_open:
            execution_state = RUN_STATE_BLOCKED
        elif artifact_explicit_hold:
            execution_state = RUN_STATE_EXPLICIT_HOLD
        elif artifact_result_ready:
            execution_state = RUN_STATE_RESULT_READY
        elif artifact_run_started:
            execution_state = RUN_STATE_RUNNING
        else:
            execution_state = RUN_STATE_READY
    else:
        execution_state = _resolve_run_state(run_state, upstream_gate_open)

    queue_status_now = _queue_status_for_run_state(execution_state)

    run_started = execution_state in {
        RUN_STATE_RUNNING,
        RUN_STATE_RESULT_READY,
        RUN_STATE_EXPLICIT_HOLD,
    }
    result_review_ready = execution_state in {
        RUN_STATE_RESULT_READY,
        RUN_STATE_EXPLICIT_HOLD,
    }
    explicit_hold = execution_state == RUN_STATE_EXPLICIT_HOLD
    successor_gate_open = result_review_ready
    successor_gate_state = (
        "open_for_tcruzi_execution"
        if successor_gate_open
        else "blocked_until_caix_result_ready_or_explicit_hold"
    )
    successor_next_queue_state = (
        "ready_after_previous_review"
        if successor_gate_open
        else "blocked_on_previous_review"
    )

    rows = [
        {
            "checkpoint_kind": "launch_packet",
            "artifact_path": "runs/caix_launch_packet_current.md",
            "checkpoint_state": str(launch_s.get("status", "")).strip(),
            "queue_effect": "fix_second_serialized_slot",
        },
        {
            "checkpoint_kind": "upstream_gate_review",
            "artifact_path": "runs/caix_result_review_current.md",
            "checkpoint_state": upstream_gate_state,
            "queue_effect": "open_only_after_mpro_result_ready_or_explicit_hold",
        },
        {
            "checkpoint_kind": "live_progress",
            "artifact_path": "runs/caix_live_progress_current.md",
            "checkpoint_state": progress_status or "not_detected",
            "queue_effect": active_stage_label or "no_live_progress_artifact",
        },
        {
            "checkpoint_kind": "result_summary",
            "artifact_path": "runs/caix_result_summary_current.md",
            "checkpoint_state": result_status or "not_detected",
            "queue_effect": "capture_result_ready_or_explicit_hold",
        },
        {
            "checkpoint_kind": "run_execution",
            "artifact_path": "runs/caix_run_record_current.md",
            "checkpoint_state": execution_state,
            "queue_effect": queue_status_now,
        },
        {
            "checkpoint_kind": "successor_gate",
            "artifact_path": "runs/tcruzi_pde_launch_packet_current.md",
            "checkpoint_state": successor_gate_state,
            "queue_effect": "open_only_after_caix_result_ready_or_explicit_hold",
        },
    ]

    if successor_gate_open:
        next_required_step = (
            "CA IX now satisfies the serialized successor-open rule. "
            "A later T. cruzi PDE gate refresh can advance to ready_after_previous_review."
        )
    elif execution_state == RUN_STATE_RUNNING:
        next_required_step = (
            "Keep CA IX as the active serialized slot and leave T. cruzi PDE prep-only "
            "until CA IX reaches result_ready or explicit_hold."
        )
    elif execution_state == RUN_STATE_READY:
        next_required_step = (
            "Launch CA IX from the second serialized slot now, then use the resulting "
            "CA IX outcome to open the later T. cruzi PDE gate."
        )
    else:
        next_required_step = (
            "Keep CA IX blocked until the upstream Mpro-backed gate opens, and keep "
            "T. cruzi PDE prep-only until CA IX later reaches result_ready or explicit_hold."
        )

    return {
        "summary": {
            "status": "caix_run_record_ready",
            "target_id": "CA IX",
            "artifact_kind": "run_record",
            "row_count": len(rows),
            "serialized_queue_rank": int(launch_s.get("serialized_queue_rank", 2) or 2),
            "serialized_run_order": str(
                launch_s.get("serialized_run_order", "2_of_3")
            ).strip()
            or "2_of_3",
            "partner_track_id": str(launch_s.get("partner_track_id", "")).strip(),
            "launch_packet_status": str(launch_s.get("status", "")).strip(),
            "review_status": str(review_s.get("status", "")).strip(),
            "live_progress_detected": progress_detected,
            "result_summary_detected": result_detected,
            "progress_status": progress_status or "not_detected",
            "result_status": result_status or "not_detected",
            "upstream_gate_open": upstream_gate_open,
            "upstream_gate_state": upstream_gate_state,
            "execution_state": execution_state,
            "queue_status_now": queue_status_now,
            "run_started": run_started,
            "result_review_ready": result_review_ready,
            "explicit_hold": explicit_hold,
            "current_stage": (
                "manual_review_hold"
                if explicit_hold
                else "result_review_complete"
                if result_review_ready
                else active_stage_label
                if run_started
                else "launch_packet_frozen_pending_execution"
                if upstream_gate_open
                else "awaiting_upstream_gate"
            ),
            "active_stage_label": active_stage_label,
            "started_at": started_at,
            "last_update_at": last_update_at,
            "completed_at": completed_at,
            "successor_target": "T. cruzi PDE",
            "successor_launch_status": str(tcruzi_s.get("status", "")).strip(),
            "successor_gate_open": successor_gate_open,
            "successor_gate_state": successor_gate_state,
            "successor_next_queue_state": successor_next_queue_state,
            "launch_packet_artifact": "runs/caix_launch_packet_current.md",
            "review_artifact": "runs/caix_result_review_current.md",
            "successor_launch_artifact": "runs/tcruzi_pde_launch_packet_current.md",
            "next_required_step": next_required_step,
        },
        "structured": {
            "execution_policy": "serialized_by_target",
            "gate_policy": "open_tcruzi_only_after_caix_result_ready_or_explicit_hold",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the CA IX serialized run-record artifact."
    )
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--result-review-json", default=DEFAULT_RESULT_REVIEW_JSON)
    parser.add_argument("--tcruzi-launch-json", default=DEFAULT_TCRUZI_LAUNCH_JSON)
    parser.add_argument("--progress-json", default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--result-json", default=DEFAULT_RESULT_JSON)
    parser.add_argument("--run-state", choices=VALID_RUN_STATES, default=RUN_STATE_AUTO)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.launch_json),
        load_json(args.result_review_json),
        load_json(args.tcruzi_launch_json),
        maybe_load_json(args.progress_json),
        maybe_load_json(args.result_json),
        run_state=args.run_state,
    )
    write_artifact(DEFAULT_OUT_MD, "CA IX Run Record", payload)


if __name__ == "__main__":
    main()
