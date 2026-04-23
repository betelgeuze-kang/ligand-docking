#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, wetlab_run_record_state, write_artifact

DEFAULT_UPSTREAM_REVIEW_JSON = "runs/cathepsin_k_result_review_current.json"
DEFAULT_LAUNCH_JSON = "runs/dengue_ns2b_ns3_protease_launch_packet_current.json"
DEFAULT_SUCCESSOR_LAUNCH_JSON = "runs/dpre1_launch_packet_current.json"
DEFAULT_RUN_RECORD_JSON = "runs/dengue_ns2b_ns3_protease_run_record_current.json"
DEFAULT_OUT_MD = "runs/dengue_ns2b_ns3_protease_result_review_current.md"


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def build_payload(
    upstream_review: dict[str, Any] | None,
    launch_payload: dict[str, Any],
    successor_launch: dict[str, Any] | None,
    run_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    upstream_s = _summary(upstream_review or {})
    launch_s = _summary(launch_payload)
    successor_s = _summary(successor_launch or {})
    run_state = wetlab_run_record_state(run_record)

    upstream_gate_state = str(upstream_s.get("successor_gate_state", "")).strip() or "blocked_on_cathepsin_k_result_review"
    upstream_gate_open = bool(upstream_s.get("successor_gate_open", False))
    content_ready = str(launch_s.get("launch_readiness", "")).strip() == "ready_for_serialized_execution"
    execution_gate_open = upstream_gate_open and content_ready

    if not upstream_gate_open:
        review_state = "blocked_on_cathepsin_k_result_review"
        queue_status_now = "blocked_on_previous_review"
        successor_gate_state = "blocked_on_dengue_ns2b_ns3_result_review"
        successor_gate_open = False
    elif not content_ready:
        review_state = "blocked_on_target_content"
        queue_status_now = "blocked_on_target_content"
        successor_gate_state = "blocked_on_dengue_ns2b_ns3_result_review"
        successor_gate_open = False
    elif run_state["explicit_hold"]:
        review_state = "dengue_result_review_resolved"
        queue_status_now = "explicit_hold_ready_for_successor"
        successor_gate_state = "open_for_dpre1_execution"
        successor_gate_open = True
    elif run_state["result_review_ready"]:
        review_state = "dengue_result_review_resolved"
        queue_status_now = "result_ready_for_successor"
        successor_gate_state = "open_for_dpre1_execution"
        successor_gate_open = True
    elif run_state["run_started"]:
        review_state = "dengue_result_review_in_progress"
        queue_status_now = "running_after_previous_review"
        successor_gate_state = "blocked_on_dengue_ns2b_ns3_result_review"
        successor_gate_open = False
    else:
        review_state = "ready_to_capture_dengue_result_review"
        queue_status_now = "ready_after_previous_review"
        successor_gate_state = "blocked_on_dengue_ns2b_ns3_result_review"
        successor_gate_open = False

    rows = [
        {
            "review_item": "cathepsin_k_release_gate",
            "source_artifact": "runs/cathepsin_k_result_review_current.md",
            "queue_phrase": "Cathepsin K must resolve before Dengue NS2B-NS3 protease may leave blocked_on_previous_review.",
            "gate_status": upstream_gate_state,
        },
        {
            "review_item": "dengue_ns2b_ns3_content_gate",
            "source_artifact": "runs/dengue_ns2b_ns3_protease_launch_packet_current.md",
            "queue_phrase": (
                "Dengue NS2B-NS3 protease launch packet is fill-ready; only the Cathepsin K predecessor gate still blocks execution."
                if content_ready
                else "keep Dengue NS2B-NS3 protease blocked until the repurposing and novelty lanes are actually filled"
            ),
            "gate_status": str(launch_s.get("launch_readiness", "")).strip() or "missing_launch_packet",
        },
        {
            "review_item": "dengue_ns2b_ns3_run_record",
            "source_artifact": "runs/dengue_ns2b_ns3_protease_run_record_current.md",
            "queue_phrase": "Live Dengue NS2B-NS3 protease run records advance this review from ready to running to resolved.",
            "gate_status": run_state["status"],
        },
        {
            "review_item": "successor_hold",
            "source_artifact": "runs/dpre1_launch_packet_current.md",
            "queue_phrase": str(successor_s.get("blocking_rule", "")).strip() or "DprE1 stays closed until Dengue NS2B-NS3 protease resolves.",
            "gate_status": successor_gate_state,
        },
    ]

    return {
        "summary": {
            "status": "dengue_ns2b_ns3_protease_result_review_ready",
            "target_id": "Dengue NS2B-NS3 protease",
            "serialized_queue_rank": int(launch_s.get("serialized_queue_rank", 2) or 2),
            "serialized_run_order": str(launch_s.get("serialized_run_order", "2_of_5_in_wave2")).strip() or "2_of_5_in_wave2",
            "partner_track_id": str(launch_s.get("partner_track_id", "IPK_dengue")).strip() or "IPK_dengue",
            "upstream_gate_state": upstream_gate_state,
            "upstream_gate_open": upstream_gate_open,
            "predecessor_gate_state": upstream_gate_state,
            "predecessor_gate_open": upstream_gate_open,
            "content_ready": content_ready,
            "execution_gate_open": execution_gate_open,
            "dengue_gate_open": execution_gate_open,
            "dengue_ns2b_ns3_gate_open": execution_gate_open,
            "dengue_review_state": review_state,
            "dengue_ns2b_ns3_review_state": review_state,
            "dengue_run_record_detected": run_state["detected"],
            "dengue_ns2b_ns3_run_record_detected": run_state["detected"],
            "dengue_run_record_status": run_state["status"],
            "dengue_ns2b_ns3_run_record_status": run_state["status"],
            "dengue_execution_state": run_state["execution_state"],
            "dengue_ns2b_ns3_execution_state": run_state["execution_state"],
            "dengue_result_review_ready": run_state["result_review_ready"],
            "dengue_ns2b_ns3_result_review_ready": run_state["result_review_ready"],
            "dengue_explicit_hold": run_state["explicit_hold"],
            "dengue_ns2b_ns3_explicit_hold": run_state["explicit_hold"],
            "queue_status_now": queue_status_now,
            "successor_target": "DprE1",
            "successor_gate_state": successor_gate_state,
            "successor_gate_open": successor_gate_open,
            "dpre1_next_queue_state": "ready_after_previous_review" if successor_gate_open else "blocked_on_previous_review",
            "launch_packet_status": str(launch_s.get("status", "")).strip(),
            "next_required_step": (
                "Finish the missing Dengue compound fill before allowing live execution."
                if upstream_gate_open and not content_ready
                else "Dengue NS2B-NS3 protease is resolved; DprE1 may now move into ready_after_previous_review."
                if successor_gate_open
                else "Dengue NS2B-NS3 protease is running; keep DprE1 blocked until the live run record reaches result-ready or explicit hold."
                if run_state["run_started"]
                else "Wait for Cathepsin K to resolve before opening Dengue NS2B-NS3 protease."
                if not upstream_gate_open
                else "Dengue NS2B-NS3 protease may move into ready_after_previous_review now; keep DprE1 blocked until the live run record resolves."
            ),
        },
        "structured": {
            "gate_policy": "open_dengue_ns2b_ns3_only_after_cathepsin_k_resolution_and_real_compound_fill",
            "downstream_policy": "dpre1_stays_blocked_until_dengue_ns2b_ns3_run_record_reaches_result_ready_or_explicit_hold",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Dengue NS2B-NS3 protease result-review surface as the second Wave 2 gate.")
    parser.add_argument("--upstream-review-json", default=DEFAULT_UPSTREAM_REVIEW_JSON)
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--successor-launch-json", default=DEFAULT_SUCCESSOR_LAUNCH_JSON)
    parser.add_argument("--run-record-json", default=DEFAULT_RUN_RECORD_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.upstream_review_json),
        load_json(args.launch_json),
        maybe_load_json(args.successor_launch_json),
        maybe_load_json(args.run_record_json),
    )
    write_artifact(DEFAULT_OUT_MD, "Dengue NS2B-NS3 Protease Result Review", payload)


if __name__ == "__main__":
    main()
