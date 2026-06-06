#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_STK17B_LAUNCH_JSON = "runs/stk17b_launch_packet_current.json"
DEFAULT_LBDHODH_LAUNCH_JSON = "runs/lbdhodh_launch_packet_current.json"
DEFAULT_PREP_LANE_JSON = "runs/wetlab_prep_artifact_lane_current.json"
DEFAULT_STK17B_RUN_STATUS_JSON = "runs/stk17b_run_status_current.json"
DEFAULT_LBDHODH_RESULT_REVIEW_JSON = "runs/lbdhodh_result_review_current.json"
DEFAULT_OUT_MD = "runs/wetlab_wave1_tail_protein_run_queue_current.md"


def build_payload(
    stk17b_launch: dict,
    lbdhodh_launch: dict,
    prep_lane: dict,
    stk17b_run_status: dict,
    lbdhodh_result_review: dict,
) -> dict:
    stk17b_launch_s = dict(stk17b_launch.get("summary", {}) or {})
    lbdhodh_launch_s = dict(lbdhodh_launch.get("summary", {}) or {})
    prep_s = dict(prep_lane.get("summary", {}) or {})
    stk17b_status_s = dict(stk17b_run_status.get("summary", {}) or {})
    lbdhodh_review_s = dict(lbdhodh_result_review.get("summary", {}) or {})

    rows = [
        {
            "queue_order": 1,
            "target_id": "STK17B (DRAK2)",
            "launch_packet_artifact": "runs/stk17b_launch_packet_current.md",
            "transition_artifact": "runs/stk17b_run_status_current.md",
            "partner_track_id": str(stk17b_launch_s.get("partner_track_id", "")).strip(),
            "transition_status": str(stk17b_status_s.get("status", "")).strip(),
            "queue_status": str(stk17b_status_s.get("queue_status_now", "")).strip() or "blocked_on_previous_review",
            "advance_gate": "STK17B live run record must reach result-ready or explicit hold before LbDHODH starts",
            "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md",
        },
        {
            "queue_order": 2,
            "target_id": "Leishmania braziliensis DHODH",
            "launch_packet_artifact": "runs/lbdhodh_launch_packet_current.md",
            "transition_artifact": "runs/lbdhodh_result_review_current.md",
            "partner_track_id": str(lbdhodh_launch_s.get("partner_track_id", "")).strip(),
            "transition_status": str(lbdhodh_review_s.get("status", "")).strip(),
            "queue_status": str(lbdhodh_review_s.get("queue_status_now", "")).strip() or "blocked_on_previous_review",
            "advance_gate": "LbDHODH live run record must reach result-ready or explicit hold before the Wave 1 tail closes",
            "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md",
        },
    ]
    ready_now_target_count = sum(1 for row in rows if str(row.get("queue_status", "")).startswith("ready"))
    blocked_on_previous_review_count = sum(1 for row in rows if str(row.get("queue_status", "")) == "blocked_on_previous_review")
    running_target_count = sum(1 for row in rows if "running" in str(row.get("queue_status", "")))
    resolved_target_count = sum(
        1
        for row in rows
        if "result_ready" in str(row.get("queue_status", "")) or "explicit_hold" in str(row.get("queue_status", ""))
    )

    return {
        "summary": {
            "status": "wetlab_wave1_tail_protein_run_queue_ready",
            "queue_target_count": len(rows),
            "serialized_execution_slot_count": int(prep_s.get("serialized_execution_slot_count", 1) or 1),
            "prep_artifact_lane_status": str(prep_s.get("status", "")).strip(),
            "stk17b_run_status": str(stk17b_status_s.get("status", "")).strip(),
            "lbdhodh_result_review_status": str(lbdhodh_review_s.get("status", "")).strip(),
            "ready_now_target_count": ready_now_target_count,
            "blocked_on_previous_review_count": blocked_on_previous_review_count,
            "running_target_count": running_target_count,
            "resolved_target_count": resolved_target_count,
            "stk17b_queue_status": str(rows[0].get("queue_status", "")).strip(),
            "lbdhodh_queue_status": str(rows[1].get("queue_status", "")).strip(),
            "first_target": "STK17B (DRAK2)",
            "last_target": "Leishmania braziliensis DHODH",
            "next_required_step": "Use this serialized Wave 1 tail queue after next3 resolves: refresh each live run-record-backed transition surface as the active target moves from STK17B to LbDHODH, while the prep/artifact lane stays parallel and partner mail packets remain frozen.",
        },
        "structured": {
            "execution_policy": "serialized_by_target_after_next3",
            "parallel_prep_policy": "allowed_for_non_active_targets_only",
            "frozen_partner_export_policy": "do_not_mutate_partner_email_packets_during_active_execution",
            "transition_policy": "each queued target must point to one explicit transition artifact",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized protein run queue for the Wave 1 tail wet-lab targets.")
    parser.add_argument("--stk17b-launch-json", default=DEFAULT_STK17B_LAUNCH_JSON)
    parser.add_argument("--lbdhodh-launch-json", default=DEFAULT_LBDHODH_LAUNCH_JSON)
    parser.add_argument("--prep-lane-json", default=DEFAULT_PREP_LANE_JSON)
    parser.add_argument("--stk17b-run-status-json", default=DEFAULT_STK17B_RUN_STATUS_JSON)
    parser.add_argument("--lbdhodh-result-review-json", default=DEFAULT_LBDHODH_RESULT_REVIEW_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.stk17b_launch_json),
        load_json(args.lbdhodh_launch_json),
        load_json(args.prep_lane_json),
        load_json(args.stk17b_run_status_json),
        load_json(args.lbdhodh_result_review_json),
    )
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Wave1 Tail Protein Run Queue", payload)


if __name__ == "__main__":
    main()
