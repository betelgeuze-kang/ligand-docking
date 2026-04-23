#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, resolve, wetlab_run_record_state, write_artifact

DEFAULT_LAUNCH_JSON = "runs/sarscov2_mpro_launch_packet_current.json"
DEFAULT_RUN_RECORD_JSON = "runs/sarscov2_mpro_run_record_current.json"
DEFAULT_OUT_MD = "runs/sarscov2_mpro_run_status_current.md"


def _load_json_if_exists(path_like: str) -> dict[str, Any]:
    path = resolve(path_like)
    if not path.exists():
        return {}
    return load_json(path_like)


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def build_payload(launch_packet: dict[str, Any], run_record: dict[str, Any] | None = None) -> dict[str, Any]:
    launch_s = _summary(launch_packet)
    run_state = wetlab_run_record_state(run_record)

    if run_state["explicit_hold"]:
        execution_state = "explicit_hold"
        queue_status_now = "explicit_hold_ready_for_review"
        caix_gate_state = "open_for_caix_review"
    elif run_state["result_review_ready"]:
        execution_state = "result_ready"
        queue_status_now = "result_ready_for_review"
        caix_gate_state = "open_for_caix_review"
    elif run_state["run_started"]:
        execution_state = "running"
        queue_status_now = "running_first"
        caix_gate_state = "blocked_by_mpro_first_slot"
    else:
        execution_state = "ready_to_launch"
        queue_status_now = "ready_first"
        caix_gate_state = "blocked_by_mpro_first_slot"

    rows = [
        {
            "checkpoint_kind": "launch_packet",
            "artifact_path": "runs/sarscov2_mpro_launch_packet_current.md",
            "checkpoint_state": str(launch_s.get("status", "")).strip(),
            "queue_effect": "fix_first_serialized_slot",
        },
        {
            "checkpoint_kind": "run_record",
            "artifact_path": "runs/sarscov2_mpro_run_record_current.md",
            "checkpoint_state": run_state["status"],
            "queue_effect": "advance_from_ready_to_running_or_result_ready",
        },
        {
            "checkpoint_kind": "execution_state",
            "artifact_path": "runs/sarscov2_mpro_run_status_current.md",
            "checkpoint_state": execution_state,
            "queue_effect": queue_status_now,
        },
        {
            "checkpoint_kind": "caix_gate",
            "artifact_path": "runs/caix_result_review_current.md",
            "checkpoint_state": caix_gate_state,
            "queue_effect": "open_only_after_result_ready_or_explicit_hold",
        },
    ]

    return {
        "summary": {
            "status": "sarscov2_mpro_run_status_ready",
            "target_id": "SARS-CoV-2 Mpro",
            "artifact_kind": "run_status",
            "row_count": len(rows),
            "serialized_queue_rank": 1,
            "launch_packet_status": str(launch_s.get("status", "")).strip(),
            "execution_state": execution_state,
            "queue_status_now": queue_status_now,
            "partner_track_id": str(launch_s.get("partner_track_id", "")).strip(),
            "run_record_detected": run_state["detected"],
            "run_record_status": run_state["status"],
            "result_review_ready": run_state["result_review_ready"],
            "explicit_hold": run_state["explicit_hold"],
            "caix_gate_state": caix_gate_state,
            "caix_next_queue_state": "ready_after_previous_review" if caix_gate_state == "open_for_caix_review" else "blocked_on_previous_review",
            "caix_gate_artifact": "runs/caix_result_review_current.md",
            "next_required_step": (
                "Refresh the CA IX gate review now that the Mpro slot is resolved."
                if caix_gate_state == "open_for_caix_review"
                else "Launch SARS-CoV-2 Mpro from the first serialized slot and keep CA IX blocked until Mpro reaches result_ready or explicit hold."
            ),
        },
        "structured": {
            "execution_policy": "serialized_by_target",
            "gate_policy": "caix_may_start_only_after_mpro_result_ready_or_explicit_hold",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the first-target run-status surface for the serialized wet-lab Mpro execution.")
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--run-record-json", default=DEFAULT_RUN_RECORD_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.launch_json),
        _load_json_if_exists(args.run_record_json),
    )
    write_artifact(DEFAULT_OUT_MD, "SARS-CoV-2 Mpro Run Status", payload)


if __name__ == "__main__":
    main()
