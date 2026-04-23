#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, wetlab_run_record_state, write_artifact

DEFAULT_CRUZAIN_RUN_STATUS_JSON = "runs/cruzain_run_status_current.json"
DEFAULT_PLPRO_LAUNCH_JSON = "runs/sarscov2_plpro_launch_packet_current.json"
DEFAULT_ALK2_LAUNCH_JSON = "runs/alk2_launch_packet_current.json"
DEFAULT_PLPRO_RUN_RECORD_JSON = "runs/sarscov2_plpro_run_record_current.json"
DEFAULT_OUT_MD = "runs/sarscov2_plpro_result_review_current.md"


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def build_payload(cruzain_run_status: dict[str, Any], plpro_launch: dict[str, Any], alk2_launch: dict[str, Any], plpro_run_record: dict[str, Any] | None = None) -> dict[str, Any]:
    cruzain_s = _summary(cruzain_run_status)
    plpro_s = _summary(plpro_launch)
    alk2_s = _summary(alk2_launch)
    run_state = wetlab_run_record_state(plpro_run_record)

    cruzain_gate_state = str(cruzain_s.get("execution_state", "")).strip() or "awaiting_result_context"
    plpro_gate_open = cruzain_gate_state in {"result_ready", "explicit_hold"}
    plpro_gate_decision = "open_for_plpro_execution" if plpro_gate_open else "hold_until_cruzain_result_ready_or_explicit_hold"
    successor_gate_open = plpro_gate_open and bool(run_state["result_review_ready"])

    if not plpro_gate_open:
        plpro_review_state = "blocked_on_cruzain_result_review"
        queue_status_now = "blocked_on_previous_review"
    elif run_state["explicit_hold"]:
        plpro_review_state = "plpro_result_review_resolved"
        queue_status_now = "explicit_hold_ready_for_successor"
    elif run_state["result_review_ready"]:
        plpro_review_state = "plpro_result_review_resolved"
        queue_status_now = "result_ready_for_successor"
    elif run_state["run_started"]:
        plpro_review_state = "plpro_result_review_in_progress"
        queue_status_now = "running_after_previous_review"
    else:
        plpro_review_state = "ready_to_capture_plpro_result_review"
        queue_status_now = "ready_after_previous_review"

    successor_gate_state = "open_for_alk2_execution" if successor_gate_open else "blocked_on_plpro_result_review"
    rows = [
        {"review_item": "cruzain_gate_resolution", "source_artifact": "runs/cruzain_run_status_current.md", "queue_phrase": "Cruzain must reach result-ready or explicit hold before PLpro may start.", "gate_status": cruzain_gate_state},
        {"review_item": "plpro_execution_gate", "source_artifact": "runs/sarscov2_plpro_launch_packet_current.md", "queue_phrase": "capture PLpro result review before ALK2 starts", "gate_status": plpro_review_state},
        {"review_item": "plpro_run_record", "source_artifact": "runs/sarscov2_plpro_run_record_current.md", "queue_phrase": "Live PLpro run records advance this review from ready to running to resolved.", "gate_status": run_state["status"]},
        {"review_item": "successor_hold", "source_artifact": "runs/alk2_launch_packet_current.md", "queue_phrase": str(alk2_s.get("blocking_rule", "")).strip() or "This launch packet opens only after Cruzain and PLpro both reach result-ready or explicit hold in the serialized next3 queue.", "gate_status": successor_gate_state},
    ]
    return {
        "summary": {
            "status": "sarscov2_plpro_result_review_ready",
            "target_id": "SARS-CoV-2 PLpro",
            "serialized_queue_rank": 2,
            "serialized_run_order": str(plpro_s.get("serialized_run_order", "2_of_3_after_priority3")).strip() or "2_of_3_after_priority3",
            "partner_track_id": str(plpro_s.get("partner_track_id", "READDI_Korea")).strip() or "READDI_Korea",
            "cruzain_gate_state": cruzain_gate_state,
            "plpro_gate_open": plpro_gate_open,
            "plpro_gate_decision": plpro_gate_decision,
            "plpro_review_state": plpro_review_state,
            "plpro_run_record_detected": run_state["detected"],
            "plpro_run_record_status": run_state["status"],
            "plpro_execution_state": run_state["execution_state"],
            "plpro_result_review_ready": run_state["result_review_ready"],
            "plpro_explicit_hold": run_state["explicit_hold"],
            "queue_status_now": queue_status_now,
            "successor_target": "ALK2",
            "successor_gate_state": successor_gate_state,
            "successor_gate_open": successor_gate_open,
            "alk2_next_queue_state": "ready_after_previous_review" if successor_gate_open else "blocked_on_previous_review",
            "queue_status_compatibility": queue_status_now,
            "launch_packet_artifact": "runs/sarscov2_plpro_launch_packet_current.md",
            "successor_launch_artifact": "runs/alk2_launch_packet_current.md",
            "execution_goal": str(plpro_s.get("execution_goal", "")).strip(),
            "blocking_rule": str(plpro_s.get("blocking_rule", "")).strip(),
            "next_required_step": (
                "PLpro is resolved by explicit hold; ALK2 may now move into the ready_after_previous_review slot."
                if plpro_gate_open and run_state["explicit_hold"]
                else "PLpro is result-ready; ALK2 may now move into the ready_after_previous_review slot."
                if successor_gate_open
                else "PLpro is running; keep ALK2 blocked until the live PLpro run record reaches result-ready or explicit hold."
                if plpro_gate_open and run_state["run_started"]
                else "PLpro may move from blocked_on_previous_review to ready_after_previous_review now; keep ALK2 blocked until the live PLpro run record reaches result-ready or explicit hold."
                if plpro_gate_open
                else "Keep PLpro blocked until Cruzain reaches result-ready or explicit hold, then treat the live PLpro run record as the gate before ALK2 starts."
            ),
        },
        "structured": {
            "gate_policy": "open_plpro_only_after_cruzain_result_ready_or_explicit_hold",
            "downstream_policy": "alk2_stays_blocked_until_plpro_run_record_reaches_result_ready_or_explicit_hold",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the PLpro gate review surface driven by the upstream Cruzain run status.")
    parser.add_argument("--cruzain-run-status-json", default=DEFAULT_CRUZAIN_RUN_STATUS_JSON)
    parser.add_argument("--plpro-launch-json", default=DEFAULT_PLPRO_LAUNCH_JSON)
    parser.add_argument("--alk2-launch-json", default=DEFAULT_ALK2_LAUNCH_JSON)
    parser.add_argument("--plpro-run-record-json", default=DEFAULT_PLPRO_RUN_RECORD_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.cruzain_run_status_json), load_json(args.plpro_launch_json), load_json(args.alk2_launch_json), maybe_load_json(args.plpro_run_record_json))
    write_artifact(DEFAULT_OUT_MD, "SARS-CoV-2 PLpro Result Review", payload)


if __name__ == "__main__":
    main()
