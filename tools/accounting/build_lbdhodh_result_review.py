#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, wetlab_run_record_state, write_artifact

DEFAULT_STK17B_RUN_STATUS_JSON = "runs/stk17b_run_status_current.json"
DEFAULT_LBDHODH_LAUNCH_JSON = "runs/lbdhodh_launch_packet_current.json"
DEFAULT_LBDHODH_RUN_RECORD_JSON = "runs/lbdhodh_run_record_current.json"
DEFAULT_OUT_MD = "runs/lbdhodh_result_review_current.md"
TARGET_ID = "Leishmania braziliensis DHODH"


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def build_payload(stk17b_run_status: dict[str, Any], lbdhodh_launch: dict[str, Any], lbdhodh_run_record: dict[str, Any] | None = None) -> dict[str, Any]:
    stk_s = _summary(stk17b_run_status)
    launch_s = _summary(lbdhodh_launch)
    run_state = wetlab_run_record_state(lbdhodh_run_record)

    stk_gate_state = str(stk_s.get("execution_state", "")).strip() or "awaiting_result_context"
    upstream_gate_open = stk_gate_state in {"result_ready", "explicit_hold"}
    content_ready = str(launch_s.get("launch_readiness", "")).strip() == "ready_for_serialized_execution"
    execution_gate_open = upstream_gate_open and content_ready

    if not upstream_gate_open:
        lbdhodh_review_state = "blocked_on_stk17b_result_review"
        queue_status_now = "blocked_on_previous_review"
        final_release_gate_status = "wave1_tail_release_blocked"
        final_release_blocked = True
    elif not content_ready:
        lbdhodh_review_state = "blocked_on_compound_fill"
        queue_status_now = "blocked_on_target_content"
        final_release_gate_status = "wave1_tail_release_blocked"
        final_release_blocked = True
    elif run_state["explicit_hold"]:
        lbdhodh_review_state = "lbdhodh_result_review_resolved"
        queue_status_now = "explicit_hold_ready_for_final_release"
        final_release_gate_status = "open_after_lbdhodh_explicit_hold"
        final_release_blocked = False
    elif run_state["result_review_ready"]:
        lbdhodh_review_state = "lbdhodh_result_review_resolved"
        queue_status_now = "result_ready_for_final_release"
        final_release_gate_status = "open_after_lbdhodh_result_ready"
        final_release_blocked = False
    elif run_state["run_started"]:
        lbdhodh_review_state = "lbdhodh_result_review_in_progress"
        queue_status_now = "running_after_previous_review"
        final_release_gate_status = "wave1_tail_release_blocked"
        final_release_blocked = True
    else:
        lbdhodh_review_state = "ready_to_capture_lbdhodh_result_review"
        queue_status_now = "ready_after_previous_review"
        final_release_gate_status = "wave1_tail_release_blocked"
        final_release_blocked = True

    rows = [
        {"review_item": "stk17b_gate_resolution", "source_artifact": "runs/stk17b_run_status_current.md", "queue_phrase": "STK17B must reach result-ready or explicit hold before LbDHODH may start.", "gate_status": stk_gate_state},
        {"review_item": "lbdhodh_launch_content_gate", "source_artifact": "runs/lbdhodh_launch_packet_current.md", "queue_phrase": "keep LbDHODH blocked until compound lanes are actually filled", "gate_status": str(launch_s.get("launch_readiness", "")).strip() or "missing_launch_packet"},
        {"review_item": "lbdhodh_run_record", "source_artifact": "runs/lbdhodh_run_record_current.md", "queue_phrase": "Live LbDHODH run records advance this review from ready to running to resolved.", "gate_status": run_state["status"]},
        {"review_item": "final_release_gate", "source_artifact": "runs/lbdhodh_go_no_go_card_current.md", "queue_phrase": "This is the final Wave 1 tail release gate.", "gate_status": final_release_gate_status},
    ]
    return {
        "summary": {
            "status": "lbdhodh_result_review_ready",
            "target_id": TARGET_ID,
            "serialized_queue_rank": 2,
            "serialized_run_order": str(launch_s.get("serialized_run_order", "2_of_2_after_next3")).strip() or "2_of_2_after_next3",
            "partner_track_id": str(launch_s.get("partner_track_id", "DNDi_IPK")).strip() or "DNDi_IPK",
            "stk17b_gate_state": stk_gate_state,
            "upstream_gate_open": upstream_gate_open,
            "lbdhodh_gate_open": execution_gate_open,
            "lbdhodh_review_state": lbdhodh_review_state,
            "lbdhodh_run_record_detected": run_state["detected"],
            "lbdhodh_run_record_status": run_state["status"],
            "lbdhodh_execution_state": run_state["execution_state"],
            "lbdhodh_result_review_ready": run_state["result_review_ready"],
            "lbdhodh_explicit_hold": run_state["explicit_hold"],
            "launch_packet_status": str(launch_s.get("status", "")).strip(),
            "launch_readiness": str(launch_s.get("launch_readiness", "")).strip(),
            "content_ready": content_ready,
            "queue_status_now": queue_status_now,
            "final_release_gate_status": final_release_gate_status,
            "final_release_blocked": final_release_blocked,
            "next_required_step": (
                "Finish the missing LbDHODH compound fill before allowing live execution."
                if upstream_gate_open and not content_ready
                else "Refresh the final Wave 1 tail release note now that LbDHODH is resolved."
                if not final_release_blocked
                else "Wait for STK17B to resolve before opening LbDHODH."
            ),
        },
        "structured": {
            "execution_policy": "serialized_by_target",
            "gate_policy": "lbdhodh_may_start_only_after_stk17b_resolution_and_compound_fill",
            "final_release_policy": "no_wave1_tail_release_before_lbdhodh_review_resolution",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the second-target result-review surface for the serialized wet-lab LbDHODH execution.")
    parser.add_argument("--stk17b-run-status-json", default=DEFAULT_STK17B_RUN_STATUS_JSON)
    parser.add_argument("--launch-json", default=DEFAULT_LBDHODH_LAUNCH_JSON)
    parser.add_argument("--run-record-json", default=DEFAULT_LBDHODH_RUN_RECORD_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.stk17b_run_status_json), load_json(args.launch_json), maybe_load_json(args.run_record_json))
    write_artifact(DEFAULT_OUT_MD, "LbDHODH Result Review", payload)


if __name__ == "__main__":
    main()
