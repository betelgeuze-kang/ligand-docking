#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from tools.wetlab_target_render_utils import load_json, resolve, wetlab_run_record_state, write_artifact

DEFAULT_UPSTREAM_REVIEW_JSON = "runs/alk2_result_review_current.json"
DEFAULT_LAUNCH_JSON = "runs/stk17b_launch_packet_current.json"
DEFAULT_RUN_RECORD_JSON = "runs/stk17b_run_record_current.json"
DEFAULT_OUT_MD = "runs/stk17b_run_status_current.md"
TARGET_ID = "STK17B (DRAK2)"


def _load_json_if_exists(path_like: str) -> dict:
    path = resolve(path_like)
    if not path.exists():
        return {}
    return load_json(path_like)


def _summary(payload: dict) -> dict:
    return dict(payload.get("summary", {}) or {})


def build_payload(upstream_review: dict | None, launch_packet: dict, run_record: dict | None = None) -> dict:
    upstream_s = _summary(upstream_review or {})
    launch_s = _summary(launch_packet)
    run_state = wetlab_run_record_state(run_record)

    upstream_gate_open = not bool(upstream_s.get("next_queue_release_blocked", True))
    upstream_gate_state = str(upstream_s.get("next_queue_release_gate_status", "")).strip() or "blocked_on_next3_final_review"

    if not upstream_gate_open:
        execution_state = "blocked_on_previous_review"
        queue_status_now = "blocked_on_previous_review"
        lbdhodh_gate_state = "blocked_by_stk17b_first_slot"
    elif run_state["explicit_hold"]:
        execution_state = "explicit_hold"
        queue_status_now = "explicit_hold_ready_for_review"
        lbdhodh_gate_state = "open_for_lbdhodh_review"
    elif run_state["result_review_ready"]:
        execution_state = "result_ready"
        queue_status_now = "result_ready_for_review"
        lbdhodh_gate_state = "open_for_lbdhodh_review"
    elif run_state["run_started"]:
        execution_state = "running"
        queue_status_now = "running_first_in_final2"
        lbdhodh_gate_state = "blocked_by_stk17b_first_slot"
    else:
        execution_state = "ready_to_launch"
        queue_status_now = "ready_after_previous_review"
        lbdhodh_gate_state = "blocked_by_stk17b_first_slot"

    rows = [
        {"checkpoint_kind": "upstream_next3_review", "artifact_path": "runs/alk2_result_review_current.md", "checkpoint_state": upstream_gate_state, "queue_effect": "open_only_after_next3_final_review_resolves"},
        {"checkpoint_kind": "launch_packet", "artifact_path": "runs/stk17b_launch_packet_current.md", "checkpoint_state": str(launch_s.get("status", "")).strip(), "queue_effect": "fix_first_final2_slot"},
        {"checkpoint_kind": "run_record", "artifact_path": "runs/stk17b_run_record_current.md", "checkpoint_state": run_state["status"], "queue_effect": "advance_from_ready_to_running_or_result_ready"},
        {"checkpoint_kind": "execution_state", "artifact_path": "runs/stk17b_run_status_current.md", "checkpoint_state": execution_state, "queue_effect": queue_status_now},
        {"checkpoint_kind": "lbdhodh_gate", "artifact_path": "runs/lbdhodh_result_review_current.md", "checkpoint_state": lbdhodh_gate_state, "queue_effect": "open_only_after_result_ready_or_explicit_hold"},
    ]

    return {
        "summary": {
            "status": "stk17b_run_status_ready",
            "target_id": TARGET_ID,
            "artifact_kind": "run_status",
            "row_count": len(rows),
            "serialized_queue_rank": 1,
            "serialized_run_order": "1_of_2_after_next3",
            "launch_packet_status": str(launch_s.get("status", "")).strip(),
            "execution_state": execution_state,
            "queue_status_now": queue_status_now,
            "partner_track_id": str(launch_s.get("partner_track_id", "SGC_dark_kinase")).strip() or "SGC_dark_kinase",
            "upstream_gate_open": upstream_gate_open,
            "upstream_gate_state": upstream_gate_state,
            "run_record_detected": run_state["detected"],
            "run_record_status": run_state["status"],
            "result_review_ready": run_state["result_review_ready"],
            "explicit_hold": run_state["explicit_hold"],
            "lbdhodh_gate_state": lbdhodh_gate_state,
            "lbdhodh_next_queue_state": "ready_after_previous_review" if lbdhodh_gate_state == "open_for_lbdhodh_review" else "blocked_on_previous_review",
            "lbdhodh_gate_artifact": "runs/lbdhodh_result_review_current.md",
            "next_required_step": (
                "Refresh the LbDHODH gate review now that the STK17B slot is resolved."
                if lbdhodh_gate_state == "open_for_lbdhodh_review"
                else "Wait for the next3 final review to resolve before launching STK17B."
                if not upstream_gate_open
                else "Launch STK17B from the first final2 serialized slot and keep LbDHODH blocked until STK17B reaches result_ready or explicit hold."
            ),
        },
        "structured": {
            "execution_policy": "serialized_by_target",
            "gate_policy": "lbdhodh_may_start_only_after_stk17b_result_ready_or_explicit_hold",
            "upstream_release_policy": "stk17b_may_start_only_after_next3_final_review_resolution",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the first-target run-status surface for the serialized wet-lab STK17B execution.")
    parser.add_argument("--upstream-review-json", default=DEFAULT_UPSTREAM_REVIEW_JSON)
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--run-record-json", default=DEFAULT_RUN_RECORD_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json_if_exists(args.upstream_review_json),
        load_json(args.launch_json),
        _load_json_if_exists(args.run_record_json),
    )
    write_artifact(DEFAULT_OUT_MD, "STK17B Run Status", payload)


if __name__ == "__main__":
    main()
