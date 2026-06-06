#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, resolve, write_artifact

DEFAULT_LAUNCH_JSON = "runs/sarscov2_mpro_launch_packet_current.json"
DEFAULT_ASSAY_JSON = "runs/sarscov2_mpro_assay_packet_current.json"
DEFAULT_GO_NO_GO_JSON = "runs/sarscov2_mpro_go_no_go_card_current.json"
DEFAULT_PROGRESS_JSON = "runs/sarscov2_mpro_live_progress_current.json"
DEFAULT_RESULT_JSON = "runs/sarscov2_mpro_result_summary_current.json"
DEFAULT_OUT_MD = "runs/sarscov2_mpro_run_record_current.md"


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
    decision_case = _first_text(
        result_summary,
        "decision_case",
        "result_class",
        "review_decision",
        "go_no_go_decision",
        "decision",
    )
    action = _first_text(result_summary, "action", "recommended_action").lower()
    details = " ".join(part for part in (decision_case.lower(), action, status) if part)

    if explicit_hold:
        return "hold_partial_cleanliness"
    if "reject_host_like" in details or ("reject" in details and "host" in details):
        return "reject_host_like"
    if "reject_reactive_or_sticky" in details or ("reject" in details and any(token in details for token in ("reactive", "sticky", "aggregation"))):
        return "reject_reactive_or_sticky"
    if "hold_partial_cleanliness" in details or "hold" in details:
        return "hold_partial_cleanliness"
    if "promote_clean_mpro_favored" in details or "promote" in details:
        return "promote_clean_mpro_favored"
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
    go_no_go_s = _summary(go_no_go_card)
    progress_s = _summary(live_progress or {})
    result_s = _summary(result_summary or {})

    launch_status = _first_text(launch_s, "status")
    assay_status = _first_text(assay_s, "status")
    go_no_go_status = _first_text(go_no_go_s, "status")
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
    progress_detected = bool(progress_s)
    result_detected = bool(result_s)

    rows = [
        {
            "record_item": "launch_packet",
            "artifact_path": "runs/sarscov2_mpro_launch_packet_current.md",
            "current_signal": launch_status or "missing_launch_packet",
            "detail": "serialized_first_slot_frozen",
            "record_role": "freeze_first_serialized_execution_contract",
        },
        {
            "record_item": "assay_packet",
            "artifact_path": "runs/sarscov2_mpro_assay_packet_current.md",
            "current_signal": assay_status or "missing_assay_packet",
            "detail": "first_pass_stack_ready",
            "record_role": "define_bounded_primary_assay_stack",
        },
        {
            "record_item": "live_progress",
            "artifact_path": "runs/sarscov2_mpro_live_progress_current.md",
            "current_signal": progress_status or "not_detected",
            "detail": active_stage_label or "no_live_progress_artifact",
            "record_role": "track_active_execution_until_result_summary_lands",
        },
        {
            "record_item": "result_summary",
            "artifact_path": "runs/sarscov2_mpro_result_summary_current.md",
            "current_signal": result_status or "not_detected",
            "detail": result_class,
            "record_role": "capture_result_ready_or_explicit_hold",
        },
        {
            "record_item": "go_no_go_card",
            "artifact_path": "runs/sarscov2_mpro_go_no_go_card_current.md",
            "current_signal": go_no_go_status or "missing_go_no_go_card",
            "detail": result_class if result_review_ready or explicit_hold else "classification_rules_ready",
            "record_role": "classify_clean_vs_host_like_vs_reactive_outcomes",
        },
    ]

    if explicit_hold:
        next_required_step = "Review the explicit Mpro hold against the go/no-go card, record the blocking reason in the result summary, and keep CA IX blocked until the hold resolves."
    elif result_review_ready:
        next_required_step = "Use the go/no-go card to classify the completed Mpro outcome, freeze the result summary, and then refresh the CA IX gate review."
    elif run_started:
        next_required_step = "Keep the live progress artifact current until the Mpro result summary lands; CA IX stays blocked while execution is active."
    else:
        next_required_step = "Launch SARS-CoV-2 Mpro from the frozen first slot, then start recording live progress once the biochemical stack is running."

    return {
        "summary": {
            "status": status,
            "target_id": "SARS-CoV-2 Mpro",
            "artifact_kind": "run_record",
            "row_count": len(rows),
            "serialized_queue_rank": int(launch_s.get("execution_rank", 1) or 1),
            "partner_track_id": _first_text(launch_s, "partner_track_id"),
            "launch_packet_status": launch_status,
            "assay_packet_status": assay_status,
            "go_no_go_card_status": go_no_go_status,
            "live_progress_detected": progress_detected,
            "result_summary_detected": result_detected,
            "progress_status": progress_status or "not_detected",
            "result_status": result_status or "not_detected",
            "run_started": run_started,
            "result_review_ready": result_review_ready,
            "explicit_hold": explicit_hold,
            "current_stage": current_stage,
            "active_stage_label": active_stage_label,
            "result_class": result_class,
            "started_at": started_at,
            "last_update_at": last_update_at,
            "completed_at": completed_at,
            "next_required_step": next_required_step,
        },
        "structured": {
            "execution_policy": "serialized_by_target",
            "progress_artifact_optional": "runs/sarscov2_mpro_live_progress_current.md",
            "result_artifact_optional": "runs/sarscov2_mpro_result_summary_current.md",
            "classification_policy": "interpret_completed_results_with_the_go_no_go_card_before_opening_caix",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the SARS-CoV-2 Mpro run-record slice from launch, progress, and result-facing artifacts.")
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--assay-json", default=DEFAULT_ASSAY_JSON)
    parser.add_argument("--go-no-go-json", default=DEFAULT_GO_NO_GO_JSON)
    parser.add_argument("--progress-json", default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--result-json", default=DEFAULT_RESULT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
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
    write_artifact(args.out_md, "SARS-CoV-2 Mpro Run Record", payload)


if __name__ == "__main__":
    main()
