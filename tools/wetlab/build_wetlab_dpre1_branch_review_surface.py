#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

TARGET_ID = "DprE1"
DEFAULT_RESULT_REVIEW_JSON = "runs/dpre1_result_review_current.json"
DEFAULT_RESULT_SUMMARY_JSON = "runs/dpre1_result_summary_current.json"
DEFAULT_LAUNCH_PACKET_JSON = "runs/dpre1_launch_packet_current.json"
DEFAULT_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_dpre1_stage6_tuning_surface_current.json"
DEFAULT_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_dpre1_exploratory_retry_lane_current.json"
DEFAULT_GUARDED_OPERATOR_PACKET_JSON = "runs/wetlab_dpre1_guarded_operator_packet_current.json"
DEFAULT_GUARDED_BRANCH_SUMMARY_JSON = "runs/wetlab_dpre1_guarded_branch_summary_current.json"
DEFAULT_RUN_RECORD_JSON = "runs/dpre1_run_record_current.json"
DEFAULT_OUT_MD = "runs/wetlab_dpre1_branch_review_surface_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def build_payload(
    result_review_payload: dict[str, Any],
    result_summary_payload: dict[str, Any],
    launch_packet_payload: dict[str, Any],
    stage6_tuning_surface_payload: dict[str, Any] | None = None,
    exploratory_retry_lane_payload: dict[str, Any] | None = None,
    guarded_operator_packet_payload: dict[str, Any] | None = None,
    guarded_branch_summary_payload: dict[str, Any] | None = None,
    run_record_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review_s = _summary(result_review_payload)
    result_s = _summary(result_summary_payload)
    launch_s = _summary(launch_packet_payload)
    tuning_s = _summary(stage6_tuning_surface_payload)
    lane_s = _summary(exploratory_retry_lane_payload)
    guarded_packet_s = _summary(guarded_operator_packet_payload)
    guarded_branch_s = _summary(guarded_branch_summary_payload)
    run_s = _summary(run_record_payload)

    review_ready = _text(review_s.get("status")) == "dpre1_result_review_ready"
    result_ready = _text(result_s.get("status")) == "completed"
    launch_ready = _text(launch_s.get("status")) == "dpre1_launch_packet_ready"
    tuning_ready = _text(tuning_s.get("status")) == "wetlab_dpre1_stage6_tuning_surface_ready"
    lane_ready = _text(lane_s.get("status")) == "wetlab_dpre1_exploratory_retry_lane_ready"
    guarded_packet_ready = _text(guarded_packet_s.get("status")).startswith("wetlab_dpre1_guarded_operator_packet_")
    guarded_branch_ready = _text(guarded_branch_s.get("status")).startswith("wetlab_dpre1_guarded_branch_summary_")
    run_ready = _text(run_s.get("status")) == "dpre1_run_record_ready"
    source_priority = "guarded_branch_summary" if guarded_branch_ready else "result_review"
    decision_source_priority = "guarded_operator_packet" if guarded_packet_ready else "result_summary"

    successor_target = _text(review_s.get("successor_target"), run_s.get("successor_target"), "T. cruzi KRS1")
    successor_gate_state = _text(
        "blocked_pending_dpre1_guarded_review" if guarded_branch_ready or guarded_packet_ready else "",
        review_s.get("successor_gate_state"),
        run_s.get("successor_gate_state"),
        "open_for_tcruzi_krs1_execution",
    )
    next_required_step = _text(
        lane_s.get("next_required_step"),
        guarded_branch_s.get("next_required_step"),
        guarded_packet_s.get("next_required_step"),
        review_s.get("next_required_step"),
        run_s.get("next_required_step"),
        result_s.get("next_required_step"),
    )
    if not next_required_step:
        next_required_step = (
            f"Run the DprE1 exploratory gate5.1 retry for {_text(lane_s.get('shard_id'), tuning_s.get('next_retry_shard_id'))}; "
            "keep the default lane closed and leave the successor gate blocked until the guarded review is resolved."
        )

    branch_review_artifact = (
        "runs/wetlab_dpre1_guarded_branch_summary_current.md"
        if guarded_branch_ready
        else "runs/dpre1_result_review_current.md"
    )
    decision_artifact = (
        "runs/wetlab_dpre1_guarded_operator_packet_current.md"
        if guarded_packet_ready
        else "runs/dpre1_result_summary_current.md"
    )
    guarded_review_active = guarded_branch_ready or guarded_packet_ready

    rows = [
        {
            "row_kind": "branch_review_source",
            "target_id": TARGET_ID,
            "source_priority": source_priority,
            "source_artifact": branch_review_artifact,
            "queue_phrase": _text(
                guarded_branch_s.get("next_required_step"),
                guarded_packet_s.get("next_required_step"),
                review_s.get("next_required_step"),
                "DprE1 stays in a guarded review branch until the gate5.1 exploratory retry is reviewed.",
            ),
            "gate_status": _text(
                guarded_branch_s.get("status"),
                guarded_packet_s.get("status"),
                review_s.get("status"),
                default="missing",
            ),
        },
        {
            "row_kind": "result_summary_source",
            "target_id": TARGET_ID,
            "source_priority": decision_source_priority,
            "source_artifact": decision_artifact,
            "queue_phrase": _text(
                guarded_packet_s.get("next_required_step"),
                result_s.get("next_required_step"),
                "DprE1 guarded review keeps the default lane closed until a tuned retry decision is reviewed.",
            ),
            "gate_status": _text(guarded_packet_s.get("status"), result_s.get("status"), default="missing"),
        },
        {
            "row_kind": "launch_packet_source",
            "target_id": TARGET_ID,
            "source_priority": "launch_packet",
            "source_artifact": "runs/dpre1_launch_packet_current.md",
            "queue_phrase": _text(
                "Keep the DprE1 default lane closed and leave launch sequencing paused while the guarded review branch is active."
                if guarded_review_active
                else "",
                launch_s.get("next_required_step"),
                "DprE1 launch packet remains paused while the guarded review branch is active.",
            ),
            "gate_status": _text(launch_s.get("status"), default="missing"),
        },
        {
            "row_kind": "stage6_tuning_source",
            "target_id": TARGET_ID,
            "source_priority": "stage6_tuning_surface",
            "source_artifact": "runs/wetlab_dpre1_stage6_tuning_surface_current.md",
            "queue_phrase": _text(
                tuning_s.get("next_required_step"),
                "Use the observed 5.05A band as the immediately runnable family for DprE1 stage6 tuning.",
            ),
            "gate_status": _text(tuning_s.get("status"), default="missing"),
        },
        {
            "row_kind": "exploratory_retry_lane",
            "target_id": TARGET_ID,
            "source_priority": "exploratory_lane",
            "source_artifact": "runs/wetlab_dpre1_exploratory_retry_lane_current.md",
            "queue_phrase": _text(
                lane_s.get("next_required_step"),
                "Use the DprE1 exploratory gate5.1 candidate lane as the active guarded review path while the successor gate stays blocked.",
            ),
            "gate_status": _text(lane_s.get("status"), default="missing"),
        },
        {
            "row_kind": "successor_gate",
            "target_id": TARGET_ID,
            "source_priority": "result_review",
            "source_artifact": "runs/tcruzi_krs1_launch_packet_current.md",
            "queue_phrase": _text(
                "T. cruzi KRS1 stays blocked behind DprE1 until the guarded review branch is cleared."
                if guarded_review_active
                else "",
                successor_gate_state,
                "T. cruzi KRS1 stays blocked behind the active DprE1 guarded review branch.",
            ),
            "gate_status": successor_gate_state,
        },
    ]

    return {
        "summary": {
            "status": "wetlab_dpre1_branch_review_surface_ready",
            "target_id": TARGET_ID,
            "branch_label": _text(guarded_branch_s.get("branch_label"), "dpre1_guarded_review_branch"),
            "branch_state": _text(
                guarded_branch_s.get("branch_state"),
                review_s.get("dpre1_review_state"),
                "guarded_stage6_review_default_lane_closed",
            ),
            "source_priority": source_priority,
            "decision_source_priority": decision_source_priority,
            "serialized_queue_rank": _safe_int(review_s.get("serialized_queue_rank", launch_s.get("serialized_queue_rank", 3)), 3),
            "serialized_run_order": (
                "guarded_review_hold"
                if guarded_review_active
                else _text(review_s.get("serialized_run_order"), launch_s.get("serialized_run_order"), "guarded_review_hold")
            ),
            "partner_track_id": _text(review_s.get("partner_track_id"), result_s.get("partner_track_id"), launch_s.get("partner_track_id"), "TB_Alliance"),
            "result_review_status": _text(guarded_branch_s.get("status"), guarded_packet_s.get("status"), review_s.get("status"), "dpre1_result_review_ready"),
            "result_summary_status": _text(guarded_packet_s.get("status"), result_s.get("status"), "completed"),
            "launch_packet_status": _text(launch_s.get("status"), "dpre1_launch_packet_ready"),
            "run_record_status": _text(run_s.get("status"), "dpre1_run_record_ready"),
            "successor_target": successor_target,
            "successor_gate_state": successor_gate_state,
            "successor_gate_open": False if guarded_branch_ready or guarded_packet_ready else bool(review_s.get("successor_gate_open", run_s.get("successor_gate_open", True))),
            "stage6_tuning_surface_ready": tuning_ready,
            "stage6_tuning_source_priority": "stage6_tuning_surface",
            "stage6_tuning_recommended_threshold_A": _safe_float(
                tuning_s.get("recommended_observed_threshold_A"), 0.0
            ),
            "stage6_tuning_immediately_runnable_command_kind": _text(
                tuning_s.get("immediately_runnable_command_kind")
            ),
            "stage6_tuning_next_required_step": _text(tuning_s.get("next_required_step")),
            "exploratory_retry_lane_ready": lane_ready,
            "exploratory_source_priority": "exploratory_lane",
            "exploratory_retry_lane_label": _text(lane_s.get("lane_label"), "exploratory_gate5.1_candidate"),
            "exploratory_retry_selected_command_kind": _text(lane_s.get("selected_command_kind")),
            "exploratory_retry_selected_threshold_A": _safe_float(lane_s.get("selected_threshold_A"), 0.0),
            "exploratory_retry_next_required_step": _text(lane_s.get("next_required_step")),
            "branch_review_ready": guarded_branch_ready or guarded_packet_ready or (review_ready and result_ready and launch_ready and tuning_ready and lane_ready and run_ready),
            "next_required_step": next_required_step,
        },
        "structured": {
            "result_review_artifact": "runs/dpre1_result_review_current.md",
            "result_summary_artifact": "runs/dpre1_result_summary_current.md",
            "launch_packet_artifact": "runs/dpre1_launch_packet_current.md",
            "stage6_tuning_surface_artifact": "runs/wetlab_dpre1_stage6_tuning_surface_current.md",
            "exploratory_retry_lane_artifact": "runs/wetlab_dpre1_exploratory_retry_lane_current.md",
            "guarded_operator_packet_artifact": "runs/wetlab_dpre1_guarded_operator_packet_current.md",
            "guarded_branch_summary_artifact": "runs/wetlab_dpre1_guarded_branch_summary_current.md",
            "run_record_artifact": "runs/dpre1_run_record_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the DprE1 branch review surface.")
    parser.add_argument("--result-review-json", default=DEFAULT_RESULT_REVIEW_JSON)
    parser.add_argument("--result-summary-json", default=DEFAULT_RESULT_SUMMARY_JSON)
    parser.add_argument("--launch-packet-json", default=DEFAULT_LAUNCH_PACKET_JSON)
    parser.add_argument("--stage6-tuning-surface-json", default=DEFAULT_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--exploratory-retry-lane-json", default=DEFAULT_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--guarded-operator-packet-json", default=DEFAULT_GUARDED_OPERATOR_PACKET_JSON)
    parser.add_argument("--guarded-branch-summary-json", default=DEFAULT_GUARDED_BRANCH_SUMMARY_JSON)
    parser.add_argument("--run-record-json", default=DEFAULT_RUN_RECORD_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.result_review_json),
        load_json(args.result_summary_json),
        load_json(args.launch_packet_json),
        maybe_load_json(args.stage6_tuning_surface_json),
        maybe_load_json(args.exploratory_retry_lane_json),
        maybe_load_json(args.guarded_operator_packet_json),
        maybe_load_json(args.guarded_branch_summary_json),
        maybe_load_json(args.run_record_json),
    )
    write_artifact(args.out_md, "Wet-Lab DprE1 Branch Review Surface", payload)


if __name__ == "__main__":
    main()
