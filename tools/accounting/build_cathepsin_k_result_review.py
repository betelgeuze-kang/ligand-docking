#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, wetlab_run_record_state, write_artifact

DEFAULT_UPSTREAM_REVIEW_JSON = "runs/lbdhodh_result_review_current.json"
DEFAULT_LAUNCH_JSON = "runs/cathepsin_k_launch_packet_current.json"
DEFAULT_SUCCESSOR_LAUNCH_JSON = "runs/dengue_ns2b_ns3_protease_launch_packet_current.json"
DEFAULT_RUN_RECORD_JSON = "runs/cathepsin_k_run_record_current.json"
DEFAULT_OUT_MD = "runs/cathepsin_k_result_review_current.md"


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

    final2_gate_state = str(upstream_s.get("final_release_gate_status", "")).strip() or "wave1_tail_release_blocked"
    upstream_gate_open = not bool(upstream_s.get("final_release_blocked", True))
    content_ready = str(launch_s.get("launch_readiness", "")).strip() == "ready_for_serialized_execution"
    execution_gate_open = upstream_gate_open and content_ready

    if not upstream_gate_open:
        review_state = "blocked_on_final2_final_review"
        queue_status_now = "blocked_on_previous_review"
        successor_gate_state = "blocked_on_cathepsin_k_result_review"
        successor_gate_open = False
    elif not content_ready:
        review_state = "blocked_on_compound_fill"
        queue_status_now = "blocked_on_target_content"
        successor_gate_state = "blocked_on_cathepsin_k_result_review"
        successor_gate_open = False
    elif run_state["explicit_hold"]:
        review_state = "cathepsin_k_result_review_resolved"
        queue_status_now = "explicit_hold_ready_for_successor"
        successor_gate_state = "open_for_dengue_execution"
        successor_gate_open = True
    elif run_state["result_review_ready"]:
        review_state = "cathepsin_k_result_review_resolved"
        queue_status_now = "result_ready_for_successor"
        successor_gate_state = "open_for_dengue_execution"
        successor_gate_open = True
    elif run_state["run_started"]:
        review_state = "cathepsin_k_result_review_in_progress"
        queue_status_now = "running_after_previous_review"
        successor_gate_state = "blocked_on_cathepsin_k_result_review"
        successor_gate_open = False
    else:
        review_state = "ready_to_capture_cathepsin_k_result_review"
        queue_status_now = "ready_after_previous_review"
        successor_gate_state = "blocked_on_cathepsin_k_result_review"
        successor_gate_open = False

    rows = [
        {
            "review_item": "final2_release_gate",
            "source_artifact": "runs/lbdhodh_result_review_current.md",
            "queue_phrase": "LbDHODH must resolve before Cathepsin K may leave blocked_on_previous_review.",
            "gate_status": final2_gate_state,
        },
        {
            "review_item": "cathepsin_k_content_gate",
            "source_artifact": "runs/cathepsin_k_launch_packet_current.md",
            "queue_phrase": (
                "Cathepsin K launch packet is fill-ready; only the final2 release gate still blocks execution."
                if content_ready
                else "keep Cathepsin K blocked until the repurposing and novelty lanes are actually filled"
            ),
            "gate_status": str(launch_s.get("launch_readiness", "")).strip() or "missing_launch_packet",
        },
        {
            "review_item": "cathepsin_k_run_record",
            "source_artifact": "runs/cathepsin_k_run_record_current.md",
            "queue_phrase": "Live Cathepsin K run records advance this review from ready to running to resolved.",
            "gate_status": run_state["status"],
        },
        {
            "review_item": "successor_hold",
            "source_artifact": "runs/dengue_ns2b_ns3_protease_launch_packet_current.md",
            "queue_phrase": str(successor_s.get("blocking_rule", "")).strip() or "The next Wave 2 target stays closed until Cathepsin K resolves.",
            "gate_status": successor_gate_state,
        },
    ]

    return {
        "summary": {
            "status": "cathepsin_k_result_review_ready",
            "target_id": "Cathepsin K",
            "serialized_queue_rank": int(launch_s.get("serialized_queue_rank", 1) or 1),
            "serialized_run_order": str(launch_s.get("serialized_run_order", "1_of_5_after_final2")).strip() or "1_of_5_after_final2",
            "partner_track_id": str(launch_s.get("partner_track_id", "acidic_protease_wave2")).strip() or "acidic_protease_wave2",
            "final2_gate_state": final2_gate_state,
            "upstream_gate_open": upstream_gate_open,
            "content_ready": content_ready,
            "execution_gate_open": execution_gate_open,
            "cathepsin_k_review_state": review_state,
            "cathepsin_k_run_record_detected": run_state["detected"],
            "cathepsin_k_run_record_status": run_state["status"],
            "cathepsin_k_execution_state": run_state["execution_state"],
            "cathepsin_k_result_review_ready": run_state["result_review_ready"],
            "cathepsin_k_explicit_hold": run_state["explicit_hold"],
            "queue_status_now": queue_status_now,
            "successor_target": "Dengue NS2B-NS3 protease",
            "successor_gate_state": successor_gate_state,
            "successor_gate_open": successor_gate_open,
            "dengue_next_queue_state": "ready_after_previous_review" if successor_gate_open else "blocked_on_previous_review",
            "launch_packet_status": str(launch_s.get("status", "")).strip(),
            "next_required_step": (
                "Finish the missing Cathepsin K compound fill before allowing live execution."
                if upstream_gate_open and not content_ready
                else "Cathepsin K is resolved; the Dengue NS2B-NS3 slot may now move into ready_after_previous_review."
                if successor_gate_open
                else "Cathepsin K is running; keep the Dengue slot blocked until the live Cathepsin K run record reaches result-ready or explicit hold."
                if run_state["run_started"]
                else "Wait for LbDHODH to resolve before opening Cathepsin K."
                if not upstream_gate_open
                else "Cathepsin K may move from blocked_on_previous_review to ready_after_previous_review now; keep Dengue blocked until the live Cathepsin K run record resolves."
            ),
        },
        "structured": {
            "gate_policy": "open_cathepsin_k_only_after_final2_release_and_real_compound_fill",
            "downstream_policy": "dengue_stays_blocked_until_cathepsin_k_run_record_reaches_result_ready_or_explicit_hold",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Cathepsin K result-review surface as the first Wave 2 gate.")
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
    write_artifact(DEFAULT_OUT_MD, "Cathepsin K Result Review", payload)


if __name__ == "__main__":
    main()
