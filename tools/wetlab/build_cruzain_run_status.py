#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, wetlab_run_record_state, write_artifact

DEFAULT_UPSTREAM_REVIEW_JSON = "runs/tcruzi_pde_result_review_current.json"
DEFAULT_LAUNCH_JSON = "runs/cruzain_launch_packet_current.json"
DEFAULT_RUN_RECORD_JSON = "runs/cruzain_run_record_current.json"
DEFAULT_OUT_MD = "runs/cruzain_run_status_current.md"


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def build_payload(upstream_review: dict[str, Any] | None, launch_packet: dict[str, Any], run_record: dict[str, Any] | None = None) -> dict[str, Any]:
    upstream_s = _summary(upstream_review or {})
    launch_s = _summary(launch_packet)
    run_state = wetlab_run_record_state(run_record)

    upstream_gate_open = not bool(upstream_s.get("wave2_release_blocked", True))
    upstream_gate_state = str(upstream_s.get("wave2_release_gate_status", "")).strip() or "blocked_on_priority3_final_review"

    if not upstream_gate_open:
        execution_state = "blocked_on_previous_review"
        queue_status_now = "blocked_on_previous_review"
        plpro_gate_state = "blocked_by_cruzain_first_slot"
    elif run_state["explicit_hold"]:
        execution_state = "explicit_hold"
        queue_status_now = "explicit_hold_ready_for_review"
        plpro_gate_state = "open_for_plpro_review"
    elif run_state["result_review_ready"]:
        execution_state = "result_ready"
        queue_status_now = "result_ready_for_review"
        plpro_gate_state = "open_for_plpro_review"
    elif run_state["run_started"]:
        execution_state = "running"
        queue_status_now = "running_first_in_next3"
        plpro_gate_state = "blocked_by_cruzain_first_slot"
    else:
        execution_state = "ready_to_launch"
        queue_status_now = "ready_after_previous_review"
        plpro_gate_state = "blocked_by_cruzain_first_slot"

    rows = [
        {"checkpoint_kind": "upstream_priority3_review", "artifact_path": "runs/tcruzi_pde_result_review_current.md", "checkpoint_state": upstream_gate_state, "queue_effect": "open_only_after_priority3_final_review_resolves"},
        {"checkpoint_kind": "launch_packet", "artifact_path": "runs/cruzain_launch_packet_current.md", "checkpoint_state": str(launch_s.get("status", "")).strip(), "queue_effect": "fix_first_next3_slot"},
        {"checkpoint_kind": "run_record", "artifact_path": "runs/cruzain_run_record_current.md", "checkpoint_state": run_state["status"], "queue_effect": "advance_from_ready_to_running_or_result_ready"},
        {"checkpoint_kind": "execution_state", "artifact_path": "runs/cruzain_run_status_current.md", "checkpoint_state": execution_state, "queue_effect": queue_status_now},
        {"checkpoint_kind": "plpro_gate", "artifact_path": "runs/sarscov2_plpro_result_review_current.md", "checkpoint_state": plpro_gate_state, "queue_effect": "open_only_after_result_ready_or_explicit_hold"},
    ]

    return {
        "summary": {
            "status": "cruzain_run_status_ready",
            "target_id": "Cruzain",
            "artifact_kind": "run_status",
            "row_count": len(rows),
            "serialized_queue_rank": 1,
            "serialized_run_order": "1_of_3_after_priority3",
            "launch_packet_status": str(launch_s.get("status", "")).strip(),
            "execution_state": execution_state,
            "queue_status_now": queue_status_now,
            "partner_track_id": str(launch_s.get("partner_track_id", "DNDi_IPK")).strip() or "DNDi_IPK",
            "upstream_gate_open": upstream_gate_open,
            "upstream_gate_state": upstream_gate_state,
            "run_record_detected": run_state["detected"],
            "run_record_status": run_state["status"],
            "result_review_ready": run_state["result_review_ready"],
            "explicit_hold": run_state["explicit_hold"],
            "plpro_gate_state": plpro_gate_state,
            "plpro_next_queue_state": "ready_after_previous_review" if plpro_gate_state == "open_for_plpro_review" else "blocked_on_previous_review",
            "plpro_gate_artifact": "runs/sarscov2_plpro_result_review_current.md",
            "next_required_step": (
                "Refresh the PLpro gate review now that the Cruzain slot is resolved."
                if plpro_gate_state == "open_for_plpro_review"
                else "Wait for the priority3 final review to resolve before launching Cruzain."
                if not upstream_gate_open
                else "Launch Cruzain from the first next3 serialized slot and keep PLpro blocked until Cruzain reaches result_ready or explicit hold."
            ),
        },
        "structured": {
            "execution_policy": "serialized_by_target",
            "gate_policy": "plpro_may_start_only_after_cruzain_result_ready_or_explicit_hold",
            "upstream_release_policy": "cruzain_may_start_only_after_priority3_final_review_resolves",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the first-target run-status surface for the serialized next3 Cruzain execution.")
    parser.add_argument("--upstream-review-json", default=DEFAULT_UPSTREAM_REVIEW_JSON)
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--run-record-json", default=DEFAULT_RUN_RECORD_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(maybe_load_json(args.upstream_review_json), load_json(args.launch_json), maybe_load_json(args.run_record_json))
    write_artifact(DEFAULT_OUT_MD, "Cruzain Run Status", payload)


if __name__ == "__main__":
    main()
