#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_MPRO_LAUNCH_JSON = "runs/sarscov2_mpro_launch_packet_current.json"
DEFAULT_CAIX_LAUNCH_JSON = "runs/caix_launch_packet_current.json"
DEFAULT_TCRUZI_LAUNCH_JSON = "runs/tcruzi_pde_launch_packet_current.json"
DEFAULT_PREP_LANE_JSON = "runs/wetlab_prep_artifact_lane_current.json"
DEFAULT_MPRO_RUN_STATUS_JSON = "runs/sarscov2_mpro_run_status_current.json"
DEFAULT_CAIX_RESULT_REVIEW_JSON = "runs/caix_result_review_current.json"
DEFAULT_TCRUZI_PDE_RESULT_REVIEW_JSON = "runs/tcruzi_pde_result_review_current.json"
DEFAULT_OUT_MD = "runs/wetlab_priority3_protein_run_queue_current.md"


def build_payload(
    mpro_launch: dict,
    caix_launch: dict,
    tcruzi_launch: dict,
    prep_lane: dict,
    mpro_run_status: dict,
    caix_result_review: dict,
    tcruzi_pde_result_review: dict,
) -> dict:
    mpro_s = dict(mpro_launch.get("summary", {}) or {})
    caix_s = dict(caix_launch.get("summary", {}) or {})
    tcruzi_s = dict(tcruzi_launch.get("summary", {}) or {})
    prep_s = dict(prep_lane.get("summary", {}) or {})
    mpro_run_s = dict(mpro_run_status.get("summary", {}) or {})
    caix_review_s = dict(caix_result_review.get("summary", {}) or {})
    tcruzi_review_s = dict(tcruzi_pde_result_review.get("summary", {}) or {})

    rows = [
        {
            "queue_order": 1,
            "target_id": "SARS-CoV-2 Mpro",
            "launch_packet_artifact": "runs/sarscov2_mpro_launch_packet_current.md",
            "transition_artifact": "runs/sarscov2_mpro_run_status_current.md",
            "partner_track_id": str(mpro_s.get("partner_track_id", "")).strip(),
            "transition_status": str(mpro_run_s.get("status", "")).strip(),
            "queue_status": str(mpro_run_s.get("queue_status_now", "")).strip() or "ready_first",
            "advance_gate": "Mpro live run record must reach result-ready or explicit hold before CA IX starts",
            "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md",
        },
        {
            "queue_order": 2,
            "target_id": "CA IX",
            "launch_packet_artifact": "runs/caix_launch_packet_current.md",
            "transition_artifact": "runs/caix_result_review_current.md",
            "partner_track_id": str(caix_s.get("partner_track_id", "")).strip(),
            "transition_status": str(caix_review_s.get("status", "")).strip(),
            "queue_status": str(caix_review_s.get("queue_status_now", "")).strip() or "blocked_on_previous_review",
            "advance_gate": "CA IX live run record must reach result-ready or explicit hold before T. cruzi PDE starts",
            "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md",
        },
        {
            "queue_order": 3,
            "target_id": "T. cruzi PDE",
            "launch_packet_artifact": "runs/tcruzi_pde_launch_packet_current.md",
            "transition_artifact": "runs/tcruzi_pde_result_review_current.md",
            "partner_track_id": str(tcruzi_s.get("partner_track_id", "")).strip(),
            "transition_status": str(tcruzi_review_s.get("status", "")).strip(),
            "queue_status": str(tcruzi_review_s.get("queue_status_now", "")).strip() or "blocked_on_previous_review",
            "advance_gate": "T. cruzi PDE live run record must reach result-ready or explicit hold before any wave-2 release",
            "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md",
        },
    ]
    ready_now_target_count = sum(1 for row in rows if str(row.get("queue_status", "")).startswith("ready"))
    blocked_on_previous_review_count = sum(1 for row in rows if str(row.get("queue_status", "")) == "blocked_on_previous_review")
    running_target_count = sum(1 for row in rows if "running" in str(row.get("queue_status", "")))
    resolved_target_count = sum(1 for row in rows if "result_ready" in str(row.get("queue_status", "")) or "explicit_hold" in str(row.get("queue_status", "")))

    return {
        "summary": {
            "status": "wetlab_priority3_protein_run_queue_ready",
            "queue_target_count": len(rows),
            "serialized_execution_slot_count": int(prep_s.get("serialized_execution_slot_count", 1) or 1),
            "prep_artifact_lane_status": str(prep_s.get("status", "")).strip(),
            "mpro_run_status": str(mpro_run_s.get("status", "")).strip(),
            "caix_result_review_status": str(caix_review_s.get("status", "")).strip(),
            "tcruzi_pde_result_review_status": str(tcruzi_review_s.get("status", "")).strip(),
            "ready_now_target_count": ready_now_target_count,
            "blocked_on_previous_review_count": blocked_on_previous_review_count,
            "running_target_count": running_target_count,
            "resolved_target_count": resolved_target_count,
            "mpro_queue_status": str(rows[0].get("queue_status", "")).strip(),
            "caix_queue_status": str(rows[1].get("queue_status", "")).strip(),
            "tcruzi_queue_status": str(rows[2].get("queue_status", "")).strip(),
            "first_target": "SARS-CoV-2 Mpro",
            "last_target": "T. cruzi PDE",
            "next_required_step": "Use this serialized queue for wet-lab execution: refresh each live run-record-backed transition surface as the active target moves from Mpro to CA IX to T. cruzi PDE, while the prep/artifact lane stays parallel and partner mail packets remain frozen.",
        },
        "structured": {
            "execution_policy": "serialized_by_target",
            "parallel_prep_policy": "allowed_for_non_active_targets_only",
            "frozen_partner_export_policy": "do_not_mutate_partner_email_packets_during_active_execution",
            "transition_policy": "each queued target must point to one explicit transition artifact",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized protein run queue for the first three wet-lab priority targets.")
    parser.add_argument("--mpro-launch-json", default=DEFAULT_MPRO_LAUNCH_JSON)
    parser.add_argument("--caix-launch-json", default=DEFAULT_CAIX_LAUNCH_JSON)
    parser.add_argument("--tcruzi-launch-json", default=DEFAULT_TCRUZI_LAUNCH_JSON)
    parser.add_argument("--prep-lane-json", default=DEFAULT_PREP_LANE_JSON)
    parser.add_argument("--mpro-run-status-json", default=DEFAULT_MPRO_RUN_STATUS_JSON)
    parser.add_argument("--caix-result-review-json", default=DEFAULT_CAIX_RESULT_REVIEW_JSON)
    parser.add_argument("--tcruzi-pde-result-review-json", default=DEFAULT_TCRUZI_PDE_RESULT_REVIEW_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.mpro_launch_json),
        load_json(args.caix_launch_json),
        load_json(args.tcruzi_launch_json),
        load_json(args.prep_lane_json),
        load_json(args.mpro_run_status_json),
        load_json(args.caix_result_review_json),
        load_json(args.tcruzi_pde_result_review_json),
    )
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Priority-3 Protein Run Queue", payload)


if __name__ == "__main__":
    main()
