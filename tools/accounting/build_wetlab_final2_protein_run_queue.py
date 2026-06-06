#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_STK17B_LAUNCH_JSON = "runs/stk17b_launch_packet_current.json"
DEFAULT_LBDHODH_LAUNCH_JSON = "runs/lbdhodh_launch_packet_current.json"
DEFAULT_PREP_LANE_JSON = "runs/wetlab_prep_artifact_lane_current.json"
DEFAULT_STK17B_RUN_STATUS_JSON = "runs/stk17b_run_status_current.json"
DEFAULT_LBDHODH_RESULT_REVIEW_JSON = "runs/lbdhodh_result_review_current.json"
DEFAULT_OUT_MD = "runs/wetlab_final2_protein_run_queue_current.md"


def build_payload(stk17b_launch: dict, lbdhodh_launch: dict, prep_lane: dict, stk17b_run_status: dict, lbdhodh_result_review: dict) -> dict:
    stk_l = dict(stk17b_launch.get("summary", {}) or {})
    lb_l = dict(lbdhodh_launch.get("summary", {}) or {})
    prep_s = dict(prep_lane.get("summary", {}) or {})
    stk_s = dict(stk17b_run_status.get("summary", {}) or {})
    lb_s = dict(lbdhodh_result_review.get("summary", {}) or {})
    rows = [
        {"queue_order": 1, "target_id": "STK17B (DRAK2)", "launch_packet_artifact": "runs/stk17b_launch_packet_current.md", "transition_artifact": "runs/stk17b_run_status_current.md", "partner_track_id": str(stk_l.get("partner_track_id", "")).strip(), "transition_status": str(stk_s.get("status", "")).strip(), "queue_status": str(stk_s.get("queue_status_now", "")).strip() or "blocked_on_previous_review", "advance_gate": "STK17B live run record must reach result-ready or explicit hold before LbDHODH starts", "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md"},
        {"queue_order": 2, "target_id": "Leishmania braziliensis DHODH", "launch_packet_artifact": "runs/lbdhodh_launch_packet_current.md", "transition_artifact": "runs/lbdhodh_result_review_current.md", "partner_track_id": str(lb_l.get("partner_track_id", "")).strip(), "transition_status": str(lb_s.get("status", "")).strip(), "queue_status": str(lb_s.get("queue_status_now", "")).strip() or "blocked_on_previous_review", "advance_gate": "LbDHODH is the final Wave 1 tail slot and must also satisfy compound-fill readiness", "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md"},
    ]
    ready_now_target_count = sum(1 for row in rows if str(row.get("queue_status", "")).startswith("ready"))
    blocked_on_previous_review_count = sum(1 for row in rows if str(row.get("queue_status", "")) == "blocked_on_previous_review")
    blocked_on_target_content_count = sum(1 for row in rows if str(row.get("queue_status", "")) == "blocked_on_target_content")
    running_target_count = sum(1 for row in rows if "running" in str(row.get("queue_status", "")))
    resolved_target_count = sum(1 for row in rows if "result_ready" in str(row.get("queue_status", "")) or "explicit_hold" in str(row.get("queue_status", "")))
    return {
        "summary": {
            "status": "wetlab_final2_protein_run_queue_ready",
            "queue_target_count": len(rows),
            "serialized_execution_slot_count": int(prep_s.get("serialized_execution_slot_count", 1) or 1),
            "prep_artifact_lane_status": str(prep_s.get("status", "")).strip(),
            "ready_now_target_count": ready_now_target_count,
            "blocked_on_previous_review_count": blocked_on_previous_review_count,
            "blocked_on_target_content_count": blocked_on_target_content_count,
            "running_target_count": running_target_count,
            "resolved_target_count": resolved_target_count,
            "stk17b_queue_status": rows[0]["queue_status"],
            "lbdhodh_queue_status": rows[1]["queue_status"],
            "lbdhodh_launch_readiness": str(lb_l.get("launch_readiness", "")).strip(),
            "lbdhodh_content_ready": str(lb_l.get("launch_readiness", "")).strip() == "ready_for_serialized_execution",
            "next_required_step": "Keep STK17B as the first final2 live slot; LbDHODH stays behind both the STK17B gate and its own content-fill gate.",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized final2 wet-lab protein run queue.")
    parser.add_argument("--stk17b-launch-json", default=DEFAULT_STK17B_LAUNCH_JSON)
    parser.add_argument("--lbdhodh-launch-json", default=DEFAULT_LBDHODH_LAUNCH_JSON)
    parser.add_argument("--prep-lane-json", default=DEFAULT_PREP_LANE_JSON)
    parser.add_argument("--stk17b-run-status-json", default=DEFAULT_STK17B_RUN_STATUS_JSON)
    parser.add_argument("--lbdhodh-result-review-json", default=DEFAULT_LBDHODH_RESULT_REVIEW_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.stk17b_launch_json), load_json(args.lbdhodh_launch_json), load_json(args.prep_lane_json), load_json(args.stk17b_run_status_json), load_json(args.lbdhodh_result_review_json))
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Final2 Protein Run Queue", payload)


if __name__ == "__main__":
    main()
