#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, wetlab_run_record_state, write_artifact

DEFAULT_MPRO_RUN_STATUS_JSON = "runs/sarscov2_mpro_run_status_current.json"
DEFAULT_CAIX_LAUNCH_JSON = "runs/caix_launch_packet_current.json"
DEFAULT_TCRUZI_LAUNCH_JSON = "runs/tcruzi_pde_launch_packet_current.json"
DEFAULT_CAIX_RUN_RECORD_JSON = "runs/caix_run_record_current.json"
DEFAULT_OUT_MD = "runs/caix_result_review_current.md"


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def build_payload(
    mpro_run_status: dict[str, Any],
    caix_launch: dict[str, Any],
    tcruzi_launch: dict[str, Any],
    caix_run_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mpro_s = _summary(mpro_run_status)
    caix_s = _summary(caix_launch)
    tcruzi_s = _summary(tcruzi_launch)
    run_state = wetlab_run_record_state(caix_run_record)

    mpro_gate_state = str(mpro_s.get("execution_state", "")).strip() or "awaiting_result_context"
    mpro_gate_state_source = "upstream_run_status" if mpro_s else "missing_result_context"
    caix_gate_open = mpro_gate_state in {"result_ready", "explicit_hold"}
    caix_gate_decision = "open_for_caix_execution" if caix_gate_open else "hold_until_mpro_result_ready_or_explicit_hold"
    successor_gate_open = caix_gate_open and bool(run_state["result_review_ready"])

    if not caix_gate_open:
        caix_review_state = "blocked_on_mpro_result_review"
        queue_status_now = "blocked_on_previous_review"
    elif run_state["explicit_hold"]:
        caix_review_state = "caix_result_review_resolved"
        queue_status_now = "explicit_hold_ready_for_successor"
    elif run_state["result_review_ready"]:
        caix_review_state = "caix_result_review_resolved"
        queue_status_now = "result_ready_for_successor"
    elif run_state["run_started"]:
        caix_review_state = "caix_result_review_in_progress"
        queue_status_now = "running_after_previous_review"
    else:
        caix_review_state = "ready_to_capture_caix_result_review"
        queue_status_now = "ready_after_previous_review"

    successor_gate_state = "open_for_tcruzi_execution" if successor_gate_open else "blocked_on_caix_result_review"

    rows = [
        {
            "review_item": "mpro_gate_resolution",
            "source_artifact": "runs/sarscov2_mpro_run_status_current.md",
            "queue_phrase": "Mpro must reach result-ready or explicit hold before CA IX may start.",
            "gate_status": mpro_gate_state,
        },
        {
            "review_item": "caix_execution_gate",
            "source_artifact": "runs/caix_launch_packet_current.md",
            "queue_phrase": "capture CA IX condition-aware result review before T. cruzi PDE starts",
            "gate_status": caix_review_state,
        },
        {
            "review_item": "caix_run_record",
            "source_artifact": "runs/caix_run_record_current.md",
            "queue_phrase": "Live CA IX run records advance this review from ready to running to resolved.",
            "gate_status": run_state["status"],
        },
        {
            "review_item": "successor_hold",
            "source_artifact": "runs/tcruzi_pde_launch_packet_current.md",
            "queue_phrase": str(tcruzi_s.get("blocking_rule", "")).strip() or "This launch packet opens only after Mpro and CA IX both reach result-ready or explicit hold in the serialized queue.",
            "gate_status": successor_gate_state,
        },
    ]

    return {
        "summary": {
            "status": "caix_result_review_ready",
            "target_id": "CA IX",
            "serialized_queue_rank": 2,
            "serialized_run_order": str(caix_s.get("serialized_run_order", "2_of_3")).strip() or "2_of_3",
            "partner_track_id": str(caix_s.get("partner_track_id", "")).strip(),
            "mpro_gate_state": mpro_gate_state,
            "mpro_gate_state_source": mpro_gate_state_source,
            "caix_gate_open": caix_gate_open,
            "caix_gate_decision": caix_gate_decision,
            "caix_review_state": caix_review_state,
            "caix_run_record_detected": run_state["detected"],
            "caix_run_record_status": run_state["status"],
            "caix_execution_state": run_state["execution_state"],
            "caix_result_review_ready": run_state["result_review_ready"],
            "caix_explicit_hold": run_state["explicit_hold"],
            "queue_status_now": queue_status_now,
            "successor_target": "T. cruzi PDE",
            "successor_gate_state": successor_gate_state,
            "successor_gate_open": successor_gate_open,
            "tcruzi_next_queue_state": "ready_after_previous_review" if successor_gate_open else "blocked_on_previous_review",
            "queue_status_compatibility": queue_status_now,
            "launch_packet_artifact": "runs/caix_launch_packet_current.md",
            "successor_launch_artifact": "runs/tcruzi_pde_launch_packet_current.md",
            "execution_goal": str(caix_s.get("execution_goal", "")).strip(),
            "blocking_rule": str(caix_s.get("blocking_rule", "")).strip(),
            "next_required_step": (
                "CA IX is resolved by explicit hold; T. cruzi PDE may now move into the ready_after_previous_review slot."
                if caix_gate_open and run_state["explicit_hold"]
                else "CA IX is result-ready; T. cruzi PDE may now move into the ready_after_previous_review slot."
                if successor_gate_open
                else "CA IX is running; keep T. cruzi PDE blocked until the live CA IX run record reaches result-ready or explicit hold."
                if caix_gate_open and run_state["run_started"]
                else "CA IX may move from blocked_on_previous_review to ready_after_previous_review now; keep T. cruzi PDE blocked until the live CA IX run record reaches result-ready or explicit hold."
                if caix_gate_open
                else "Keep CA IX blocked until Mpro reaches result-ready or explicit hold, then treat the live CA IX run record as the gate before T. cruzi PDE starts."
            ),
        },
        "structured": {
            "gate_policy": "open_caix_only_after_mpro_result_ready_or_explicit_hold",
            "downstream_policy": "tcruzi_stays_blocked_until_caix_run_record_reaches_result_ready_or_explicit_hold",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the CA IX gate review surface driven by the upstream Mpro run status.")
    parser.add_argument("--mpro-run-status-json", default=DEFAULT_MPRO_RUN_STATUS_JSON)
    parser.add_argument("--caix-launch-json", default=DEFAULT_CAIX_LAUNCH_JSON)
    parser.add_argument("--tcruzi-launch-json", default=DEFAULT_TCRUZI_LAUNCH_JSON)
    parser.add_argument("--caix-run-record-json", default=DEFAULT_CAIX_RUN_RECORD_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.mpro_run_status_json),
        load_json(args.caix_launch_json),
        load_json(args.tcruzi_launch_json),
        maybe_load_json(args.caix_run_record_json),
    )
    write_artifact(DEFAULT_OUT_MD, "CA IX Result Review", payload)


if __name__ == "__main__":
    main()
