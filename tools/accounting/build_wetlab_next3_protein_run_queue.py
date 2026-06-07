#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_CRUZAIN_LAUNCH_JSON = "runs/cruzain_launch_packet_current.json"
DEFAULT_PLPRO_LAUNCH_JSON = "runs/sarscov2_plpro_launch_packet_current.json"
DEFAULT_ALK2_LAUNCH_JSON = "runs/alk2_launch_packet_current.json"
DEFAULT_PREP_LANE_JSON = "runs/wetlab_prep_artifact_lane_current.json"
DEFAULT_CRUZAIN_RUN_STATUS_JSON = "runs/cruzain_run_status_current.json"
DEFAULT_PLPRO_RESULT_REVIEW_JSON = "runs/sarscov2_plpro_result_review_current.json"
DEFAULT_ALK2_RESULT_REVIEW_JSON = "runs/alk2_result_review_current.json"
DEFAULT_OUT_MD = "runs/wetlab_next3_protein_run_queue_current.md"


def _first_text(mapping: dict, *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _queue_status_text(summary: dict, *keys: str) -> str:
    text = _first_text(summary, *keys)
    if text:
        return text
    return _first_text(summary, "execution_state", "result_review_gate_status", "queue_status")


def build_payload(cruzain_launch: dict, plpro_launch: dict, alk2_launch: dict, prep_lane: dict, cruzain_run_status: dict, plpro_result_review: dict, alk2_result_review: dict) -> dict:
    cruzain_s = dict(cruzain_launch.get("summary", {}) or {})
    plpro_s = dict(plpro_launch.get("summary", {}) or {})
    alk2_s = dict(alk2_launch.get("summary", {}) or {})
    prep_s = dict(prep_lane.get("summary", {}) or {})
    cruzain_run_s = dict(cruzain_run_status.get("summary", {}) or {})
    plpro_review_s = dict(plpro_result_review.get("summary", {}) or {})
    alk2_review_s = dict(alk2_result_review.get("summary", {}) or {})

    rows = [
        {"queue_order": 1, "target_id": "Cruzain", "launch_packet_artifact": "runs/cruzain_launch_packet_current.md", "transition_artifact": "runs/cruzain_run_status_current.md", "partner_track_id": str(cruzain_s.get("partner_track_id", "")).strip(), "transition_status": str(cruzain_run_s.get("status", "")).strip(), "queue_status": _queue_status_text(cruzain_run_s, "queue_status_now", "execution_state", "status") or "blocked_on_previous_review", "advance_gate": "Cruzain live run record must reach result-ready or explicit hold before PLpro starts", "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md"},
        {"queue_order": 2, "target_id": "SARS-CoV-2 PLpro", "launch_packet_artifact": "runs/sarscov2_plpro_launch_packet_current.md", "transition_artifact": "runs/sarscov2_plpro_result_review_current.md", "partner_track_id": str(plpro_s.get("partner_track_id", "")).strip(), "transition_status": str(plpro_review_s.get("status", "")).strip(), "queue_status": _queue_status_text(plpro_review_s, "queue_status_now", "result_review_gate_status", "execution_state", "status") or "blocked_on_previous_review", "advance_gate": "PLpro live run record must reach result-ready or explicit hold before ALK2 starts", "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md"},
        {"queue_order": 3, "target_id": "ALK2", "launch_packet_artifact": "runs/alk2_launch_packet_current.md", "transition_artifact": "runs/alk2_result_review_current.md", "partner_track_id": str(alk2_s.get("partner_track_id", "")).strip(), "transition_status": str(alk2_review_s.get("status", "")).strip(), "queue_status": _queue_status_text(alk2_review_s, "queue_status_now", "result_review_gate_status", "execution_state", "status") or "blocked_on_previous_review", "advance_gate": "ALK2 live run record must reach result-ready or explicit hold before any later release", "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md"},
    ]
    ready_now_target_count = sum(1 for row in rows if str(row.get("queue_status", "")).startswith("ready"))
    blocked_on_previous_review_count = sum(1 for row in rows if str(row.get("queue_status", "")) == "blocked_on_previous_review")
    running_target_count = sum(1 for row in rows if "running" in str(row.get("queue_status", "")))
    resolved_target_count = sum(1 for row in rows if "result_ready" in str(row.get("queue_status", "")) or "explicit_hold" in str(row.get("queue_status", "")))
    return {
        "summary": {
            "status": "wetlab_next3_protein_run_queue_ready",
            "queue_target_count": len(rows),
            "serialized_execution_slot_count": int(prep_s.get("serialized_execution_slot_count", 1) or 1),
            "prep_artifact_lane_status": str(prep_s.get("status", "")).strip(),
            "cruzain_run_status": str(cruzain_run_s.get("status", "")).strip(),
            "plpro_result_review_status": str(plpro_review_s.get("status", "")).strip(),
            "alk2_result_review_status": str(alk2_review_s.get("status", "")).strip(),
            "ready_now_target_count": ready_now_target_count,
            "blocked_on_previous_review_count": blocked_on_previous_review_count,
            "running_target_count": running_target_count,
            "resolved_target_count": resolved_target_count,
            "cruzain_queue_status": str(rows[0].get("queue_status", "")).strip(),
            "plpro_queue_status": str(rows[1].get("queue_status", "")).strip(),
            "alk2_queue_status": str(rows[2].get("queue_status", "")).strip(),
            "first_target": "Cruzain",
            "last_target": "ALK2",
            "next_required_step": "Use this serialized queue for the next3 wet-lab execution chain after priority3: refresh each live run-record-backed transition surface as the active target moves from Cruzain to PLpro to ALK2, while the prep/artifact lane stays parallel and partner mail packets remain frozen.",
        },
        "structured": {
            "execution_policy": "serialized_by_target_after_priority3",
            "parallel_prep_policy": "allowed_for_non_active_targets_only",
            "frozen_partner_export_policy": "do_not_mutate_partner_email_packets_during_active_execution",
            "transition_policy": "each queued target must point to one explicit transition artifact",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized protein run queue for the next3 wet-lab targets.")
    parser.add_argument("--cruzain-launch-json", default=DEFAULT_CRUZAIN_LAUNCH_JSON)
    parser.add_argument("--plpro-launch-json", default=DEFAULT_PLPRO_LAUNCH_JSON)
    parser.add_argument("--alk2-launch-json", default=DEFAULT_ALK2_LAUNCH_JSON)
    parser.add_argument("--prep-lane-json", default=DEFAULT_PREP_LANE_JSON)
    parser.add_argument("--cruzain-run-status-json", default=DEFAULT_CRUZAIN_RUN_STATUS_JSON)
    parser.add_argument("--plpro-result-review-json", default=DEFAULT_PLPRO_RESULT_REVIEW_JSON)
    parser.add_argument("--alk2-result-review-json", default=DEFAULT_ALK2_RESULT_REVIEW_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.cruzain_launch_json), load_json(args.plpro_launch_json), load_json(args.alk2_launch_json), load_json(args.prep_lane_json), load_json(args.cruzain_run_status_json), load_json(args.plpro_result_review_json), load_json(args.alk2_result_review_json))
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Next3 Protein Run Queue", payload)


if __name__ == "__main__":
    main()
