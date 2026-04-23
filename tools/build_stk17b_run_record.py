#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, resolve, write_artifact

DEFAULT_LAUNCH_JSON = "runs/stk17b_launch_packet_current.json"
DEFAULT_ASSAY_JSON = "runs/stk17b_assay_packet_current.json"
DEFAULT_GO_NO_GO_JSON = "runs/stk17b_go_no_go_card_current.json"
DEFAULT_PROGRESS_JSON = "runs/stk17b_live_progress_current.json"
DEFAULT_RESULT_JSON = "runs/stk17b_result_summary_current.json"
DEFAULT_OUT_MD = "runs/stk17b_run_record_current.md"
TARGET_ID = "STK17B (DRAK2)"
TRACK_ID = "SGC_dark_kinase"


def _load_json_if_exists(path_like: str) -> dict[str, Any]:
    path = resolve(path_like)
    if not path.exists():
        return {}
    return load_json(path_like)


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


def _result_class(result_summary: dict[str, Any], result_review_ready: bool, explicit_hold: bool) -> str:
    status = _first_text(result_summary, "status").lower()
    decision_case = _first_text(result_summary, "decision_case", "result_class", "review_decision", "go_no_go_decision", "decision")
    action = _first_text(result_summary, "action", "recommended_action").lower()
    details = " ".join(part for part in (decision_case.lower(), action, status) if part)
    if explicit_hold:
        return "hold_partial_cleanliness"
    if "reject" in details:
        return decision_case or "reject"
    if "hold" in details:
        return decision_case or "hold"
    if "promote" in details:
        return decision_case or "promote"
    if decision_case:
        return decision_case
    if result_review_ready:
        return "result_ready_pending_classification"
    return "awaiting_result"


def build_payload(
    launch_packet: dict[str, Any],
    assay_packet: dict[str, Any],
    go_no_go_card: dict[str, Any],
    live_progress: dict[str, Any] | None = None,
    result_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    launch_s = _summary(launch_packet)
    assay_s = _summary(assay_packet)
    go_s = _summary(go_no_go_card)
    progress_s = _summary(live_progress or {})
    result_s = _summary(result_summary or {})

    launch_status = _first_text(launch_s, "status")
    assay_status = _first_text(assay_s, "status")
    go_status = _first_text(go_s, "status")
    progress_status = _first_text(progress_s, "status")
    result_status = _first_text(result_s, "status")

    explicit_hold = bool(result_s.get("explicit_hold", False)) or result_status == "explicit_hold"
    result_review_ready = bool(result_s.get("result_review_ready", False)) or result_status in {"completed", "result_ready", "explicit_hold"}
    run_started = (
        bool(progress_s.get("run_started", False))
        or bool(result_s.get("run_started", False))
        or progress_status in {"running", "completed", "result_ready", "explicit_hold"}
        or result_review_ready
    )

    active_stage_label = _first_text(progress_s, "active_stage_label", "active_stage", "current_stage", "current_step", "step_label")
    started_at = _first_text(progress_s, "started_at", "started_at_local", "run_started_at", "launched_at") or _first_text(result_s, "started_at", "started_at_local", "run_started_at", "launched_at")
    last_update_at = _first_text(progress_s, "updated_at", "updated_at_local", "last_update_at", "last_update_at_local", "ended_at", "ended_at_local") or _first_text(result_s, "updated_at", "updated_at_local", "last_update_at", "last_update_at_local")
    completed_at = _first_text(result_s, "completed_at", "completed_at_local", "ended_at", "ended_at_local", "result_ready_at")

    if explicit_hold:
        status = "explicit_hold"
        current_stage = "manual_review_hold"
    elif result_review_ready:
        status = "completed"
        current_stage = "result_review_complete"
    elif run_started:
        status = "running"
        current_stage = active_stage_label or "execution_in_progress"
    else:
        status = "ready_to_launch"
        current_stage = "launch_packet_frozen_pending_execution"

    result_class = _result_class(result_s, result_review_ready, explicit_hold)
    rows = [
        {"record_item": "launch_packet", "artifact_path": "runs/stk17b_launch_packet_current.md", "current_signal": launch_status or "missing_launch_packet", "detail": "serialized_first_slot_in_final2", "record_role": "freeze_serialized_execution_contract"},
        {"record_item": "assay_packet", "artifact_path": "runs/stk17b_assay_packet_current.md", "current_signal": assay_status or "missing_assay_packet", "detail": "benchmark_first_dark_kinase_stack", "record_role": "anchor_execution_context"},
        {"record_item": "go_no_go_card", "artifact_path": "runs/stk17b_go_no_go_card_current.md", "current_signal": go_status or "missing_go_no_go_card", "detail": result_class, "record_role": "classify_result_review"},
        {"record_item": "live_progress", "artifact_path": "runs/stk17b_live_progress_current.md", "current_signal": progress_status or "not_started", "detail": current_stage, "record_role": "track_execution_progress"},
        {"record_item": "result_summary", "artifact_path": "runs/stk17b_result_summary_current.md", "current_signal": result_status or "not_ready", "detail": result_class, "record_role": "freeze_result_handoff"},
    ]

    return {
        "summary": {
            "status": status,
            "target_id": TARGET_ID,
            "artifact_kind": "run_record",
            "row_count": len(rows),
            "partner_track_id": str(launch_s.get("partner_track_id", TRACK_ID)).strip() or TRACK_ID,
            "launch_packet_status": launch_status,
            "assay_packet_status": assay_status,
            "go_no_go_status": go_status,
            "run_started": run_started,
            "result_review_ready": result_review_ready,
            "explicit_hold": explicit_hold,
            "execution_state": "blocked_on_previous_review" if status == "blocked_on_previous_review" else ("explicit_hold" if explicit_hold else "result_ready" if result_review_ready else "running" if run_started else "ready_to_launch"),
            "current_stage": current_stage,
            "active_stage_label": active_stage_label,
            "started_at": started_at,
            "updated_at": last_update_at,
            "completed_at": completed_at,
            "result_class": result_class,
            "next_required_step": "Refresh the STK17B run-status gate so the final2 successor review can open when this record resolves.",
        },
        "structured": {
            "launch_artifact": "runs/stk17b_launch_packet_current.md",
            "execution_policy": "serialized_by_target",
            "result_handoff": "refresh_stk17b_run_status_after_every_live_or_result_update",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the STK17B run-record artifact from launch, live-progress, and result-summary inputs.")
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--assay-json", default=DEFAULT_ASSAY_JSON)
    parser.add_argument("--go-no-go-json", default=DEFAULT_GO_NO_GO_JSON)
    parser.add_argument("--progress-json", default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--result-json", default=DEFAULT_RESULT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.launch_json),
        load_json(args.assay_json),
        load_json(args.go_no_go_json),
        _load_json_if_exists(args.progress_json),
        _load_json_if_exists(args.result_json),
    )
    write_artifact(DEFAULT_OUT_MD, "STK17B Run Record", payload)


if __name__ == "__main__":
    main()
