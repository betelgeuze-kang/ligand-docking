#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_LAUNCH_JSON = "runs/tcruzi_pde_launch_packet_current.json"
DEFAULT_CAIX_REVIEW_JSON = "runs/caix_result_review_current.json"
DEFAULT_GO_NO_GO_JSON = "runs/tcruzi_pde_go_no_go_card_current.json"
DEFAULT_PROGRESS_JSON = "runs/tcruzi_pde_live_progress_current.json"
DEFAULT_RESULT_JSON = "runs/tcruzi_pde_result_summary_current.json"
DEFAULT_OUT_MD = "runs/tcruzi_pde_run_record_current.md"

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
            "T. cruzi PDE run state cannot advance past blocked_on_previous_review "
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
        return "result_ready_for_wave2_release"
    if run_state == RUN_STATE_EXPLICIT_HOLD:
        return "explicit_hold_ready_for_wave2_release"
    raise ValueError(f"Unsupported T. cruzi PDE run state: {run_state}")


def build_payload(
    launch_payload: dict[str, Any],
    caix_review_payload: dict[str, Any] | None,
    go_no_go_payload: dict[str, Any],
    live_progress: dict[str, Any] | None = None,
    result_summary: dict[str, Any] | None = None,
    run_state: str = RUN_STATE_AUTO,
) -> dict[str, Any]:
    launch_s = _summary(launch_payload)
    caix_s = _summary(caix_review_payload or {})
    go_s = _summary(go_no_go_payload)
    progress_s = _summary(live_progress or {})
    result_s = _summary(result_summary or {})

    upstream_gate_open = bool(caix_s.get("successor_gate_open", caix_s.get("tcruzi_execution_gate_open", False)))
    upstream_gate_state = str(caix_s.get("caix_review_state", "")).strip() or RUN_STATE_BLOCKED
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
    run_started = execution_state in {RUN_STATE_RUNNING, RUN_STATE_RESULT_READY, RUN_STATE_EXPLICIT_HOLD}
    result_review_ready = execution_state in {RUN_STATE_RESULT_READY, RUN_STATE_EXPLICIT_HOLD}
    explicit_hold = execution_state == RUN_STATE_EXPLICIT_HOLD

    if explicit_hold:
        next_required_step = "T. cruzi PDE is explicitly held; keep wave-2 release blocked until the hold is frozen into the final review artifact."
    elif result_review_ready:
        next_required_step = "T. cruzi PDE now satisfies the wave-2 release-open rule; refresh the final result review to propagate the resolved gate."
    elif execution_state == RUN_STATE_RUNNING:
        next_required_step = "Keep T. cruzi PDE as the active serialized slot and leave wave-2 release blocked until the result summary lands."
    elif execution_state == RUN_STATE_READY:
        next_required_step = "Launch T. cruzi PDE from the third serialized slot now, then use the resulting outcome to decide any wave-2 release."
    else:
        next_required_step = "Keep T. cruzi PDE blocked until the upstream CA IX live result review resolves."

    rows = [
        {
            "checkpoint_kind": "launch_packet",
            "artifact_path": "runs/tcruzi_pde_launch_packet_current.md",
            "checkpoint_state": str(launch_s.get("status", "")).strip(),
            "queue_effect": "fix_third_serialized_slot",
        },
        {
            "checkpoint_kind": "upstream_caix_review",
            "artifact_path": "runs/caix_result_review_current.md",
            "checkpoint_state": upstream_gate_state,
            "queue_effect": "open_only_after_caix_result_ready_or_explicit_hold",
        },
        {
            "checkpoint_kind": "live_progress",
            "artifact_path": "runs/tcruzi_pde_live_progress_current.md",
            "checkpoint_state": progress_status or "not_detected",
            "queue_effect": active_stage_label or "no_live_progress_artifact",
        },
        {
            "checkpoint_kind": "result_summary",
            "artifact_path": "runs/tcruzi_pde_result_summary_current.md",
            "checkpoint_state": result_status or "not_detected",
            "queue_effect": "capture_result_ready_or_explicit_hold",
        },
        {
            "checkpoint_kind": "go_no_go_card",
            "artifact_path": "runs/tcruzi_pde_go_no_go_card_current.md",
            "checkpoint_state": str(go_s.get("status", "")).strip(),
            "queue_effect": "wave2_release_rule_frozen",
        },
        {
            "checkpoint_kind": "run_execution",
            "artifact_path": "runs/tcruzi_pde_run_record_current.md",
            "checkpoint_state": execution_state,
            "queue_effect": queue_status_now,
        },
    ]

    return {
        "summary": {
            "status": "tcruzi_pde_run_record_ready",
            "target_id": "T. cruzi PDE",
            "artifact_kind": "run_record",
            "row_count": len(rows),
            "serialized_queue_rank": int(launch_s.get("serialized_queue_rank", 3) or 3),
            "serialized_run_order": str(launch_s.get("serialized_run_order", "3_of_3")).strip() or "3_of_3",
            "partner_track_id": str(launch_s.get("partner_track_id", "DNDi_IPK")).strip() or "DNDi_IPK",
            "launch_packet_status": str(launch_s.get("status", "")).strip(),
            "caix_review_status": str(caix_s.get("status", "")).strip(),
            "go_no_go_card_status": str(go_s.get("status", "")).strip(),
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
            "launch_packet_artifact": "runs/tcruzi_pde_launch_packet_current.md",
            "caix_review_artifact": "runs/caix_result_review_current.md",
            "progress_artifact_optional": "runs/tcruzi_pde_live_progress_current.md",
            "result_artifact_optional": "runs/tcruzi_pde_result_summary_current.md",
            "go_no_go_artifact": "runs/tcruzi_pde_go_no_go_card_current.md",
            "next_required_step": next_required_step,
        },
        "structured": {
            "execution_policy": "serialized_by_target",
            "gate_policy": "open_tcruzi_only_after_caix_result_ready_or_explicit_hold",
            "wave2_release_policy": "keep wave-2 closed until the live T. cruzi run record reaches result_ready or explicit_hold",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the T. cruzi PDE serialized run-record artifact.")
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--caix-review-json", default=DEFAULT_CAIX_REVIEW_JSON)
    parser.add_argument("--go-no-go-json", default=DEFAULT_GO_NO_GO_JSON)
    parser.add_argument("--progress-json", default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--result-json", default=DEFAULT_RESULT_JSON)
    parser.add_argument("--run-state", choices=VALID_RUN_STATES, default=RUN_STATE_AUTO)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.launch_json),
        maybe_load_json(args.caix_review_json),
        load_json(args.go_no_go_json),
        maybe_load_json(args.progress_json),
        maybe_load_json(args.result_json),
        run_state=args.run_state,
    )
    write_artifact(DEFAULT_OUT_MD, "T. cruzi PDE Run Record", payload)


if __name__ == "__main__":
    main()
