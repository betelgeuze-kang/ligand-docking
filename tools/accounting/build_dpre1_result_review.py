#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, wetlab_run_record_state, write_artifact

DEFAULT_UPSTREAM_REVIEW_JSON = "runs/dengue_ns2b_ns3_protease_result_review_current.json"
DEFAULT_LAUNCH_JSON = "runs/dpre1_launch_packet_current.json"
DEFAULT_SUCCESSOR_LAUNCH_JSON = "runs/tcruzi_krs1_launch_packet_current.json"
DEFAULT_RUN_RECORD_JSON = "runs/dpre1_run_record_current.json"
DEFAULT_GUARDED_BRANCH_SUMMARY_JSON = "runs/wetlab_dpre1_guarded_branch_summary_current.json"
DEFAULT_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_dpre1_exploratory_retry_lane_current.json"
DEFAULT_OUT_MD = "runs/dpre1_result_review_current.md"


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def build_payload(
    upstream_review: dict[str, Any] | None,
    launch_payload: dict[str, Any],
    successor_launch: dict[str, Any] | None,
    run_record: dict[str, Any] | None = None,
    guarded_branch_summary: dict[str, Any] | None = None,
    exploratory_retry_lane: dict[str, Any] | None = None,
) -> dict:
    upstream_s = _summary(upstream_review or {})
    launch_s = _summary(launch_payload)
    successor_s = _summary(successor_launch or {})
    run_state = wetlab_run_record_state(run_record)
    guarded_s = _summary(guarded_branch_summary or {})
    lane_s = _summary(exploratory_retry_lane or {})

    upstream_gate_state = str(upstream_s.get("successor_gate_state", "")).strip() or "blocked_on_dengue_result_review"
    upstream_gate_open = bool(upstream_s.get("successor_gate_open", False))
    content_ready = str(launch_s.get("launch_readiness", "")).strip() == "ready_for_serialized_execution"
    execution_gate_open = upstream_gate_open and content_ready
    guarded_active = bool(str(guarded_s.get("status", "")).startswith("wetlab_dpre1_guarded_branch_summary_")) or bool(
        str(lane_s.get("status", "")).startswith("wetlab_dpre1_exploratory_retry_lane_")
    )
    guarded_next_step = str(guarded_s.get("next_required_step") or lane_s.get("next_required_step") or "").strip()
    guarded_selected_command = str(guarded_s.get("selected_command_kind") or lane_s.get("selected_command_kind") or "").strip()
    try:
        guarded_selected_threshold = float(guarded_s.get("selected_threshold_A") or lane_s.get("selected_threshold_A") or 0.0)
    except Exception:
        guarded_selected_threshold = 0.0

    if not upstream_gate_open:
        review_state = "blocked_on_dengue_result_review"
        queue_status_now = "blocked_on_previous_review"
        successor_gate_state = "blocked_on_dpre1_result_review"
        successor_gate_open = False
    elif guarded_active:
        review_state = "dpre1_guarded_review_pending"
        queue_status_now = "blocked_pending_guarded_stage6_review"
        successor_gate_state = "blocked_pending_dpre1_guarded_review"
        successor_gate_open = False
        execution_gate_open = False
    elif not content_ready:
        review_state = "blocked_on_target_content"
        queue_status_now = "blocked_on_target_content"
        successor_gate_state = "blocked_on_dpre1_result_review"
        successor_gate_open = False
    elif run_state["explicit_hold"]:
        review_state = "dpre1_result_review_resolved"
        queue_status_now = "explicit_hold_ready_for_successor"
        successor_gate_state = "open_for_tcruzi_krs1_execution"
        successor_gate_open = True
    elif run_state["result_review_ready"]:
        review_state = "dpre1_result_review_resolved"
        queue_status_now = "result_ready_for_successor"
        successor_gate_state = "open_for_tcruzi_krs1_execution"
        successor_gate_open = True
    elif run_state["run_started"]:
        review_state = "dpre1_result_review_in_progress"
        queue_status_now = "running_after_previous_review"
        successor_gate_state = "blocked_on_dpre1_result_review"
        successor_gate_open = False
    else:
        review_state = "ready_to_capture_dpre1_result_review"
        queue_status_now = "ready_after_previous_review"
        successor_gate_state = "blocked_on_dpre1_result_review"
        successor_gate_open = False

    rows = [
        {"review_item": "dengue_release_gate", "source_artifact": "runs/dengue_ns2b_ns3_protease_result_review_current.md", "queue_phrase": "Dengue must resolve before DprE1 may leave blocked_on_previous_review.", "gate_status": upstream_gate_state},
        {"review_item": "dpre1_content_gate", "source_artifact": "runs/dpre1_launch_packet_current.md", "queue_phrase": "DprE1 launch packet is fill-ready; only the Dengue predecessor gate still blocks execution." if content_ready else "keep DprE1 blocked until the repurposing and novelty lanes are actually filled", "gate_status": str(launch_s.get("launch_readiness", "")).strip() or "missing_launch_packet"},
        {"review_item": "dpre1_run_record", "source_artifact": "runs/dpre1_run_record_current.md", "queue_phrase": "Live DprE1 run records should remain subordinate to the guarded gate5.1 review until that branch is explicitly resolved." if guarded_active else "Live DprE1 run records advance this review from ready to running to resolved.", "gate_status": run_state["status"]},
        {"review_item": "successor_hold", "source_artifact": "runs/tcruzi_krs1_launch_packet_current.md", "queue_phrase": str(successor_s.get("blocking_rule", "")).strip() or "T. cruzi KRS1 stays closed until DprE1 resolves.", "gate_status": successor_gate_state},
    ]

    return {"summary": {
        "status": "dpre1_result_review_ready",
        "target_id": "DprE1",
        "serialized_queue_rank": int(launch_s.get("serialized_queue_rank", 3) or 3),
        "serialized_run_order": str(launch_s.get("serialized_run_order", "3_of_5_in_wave2")).strip() or "3_of_5_in_wave2",
        "partner_track_id": str(launch_s.get("partner_track_id", "TB_Alliance")).strip() or "TB_Alliance",
        "upstream_gate_state": upstream_gate_state,
        "upstream_gate_open": upstream_gate_open,
        "content_ready": content_ready,
        "dpre1_gate_open": execution_gate_open,
        "dpre1_review_state": review_state,
        "dpre1_run_record_detected": run_state["detected"],
        "dpre1_run_record_status": run_state["status"],
        "dpre1_execution_state": run_state["execution_state"],
        "dpre1_result_review_ready": run_state["result_review_ready"],
        "dpre1_explicit_hold": run_state["explicit_hold"],
        "guarded_review_active": guarded_active,
        "guarded_selected_command_kind": guarded_selected_command,
        "guarded_selected_threshold_A": guarded_selected_threshold,
        "queue_status_now": queue_status_now,
        "successor_target": "T. cruzi KRS1",
        "successor_gate_state": successor_gate_state,
        "successor_gate_open": successor_gate_open,
        "tcruzi_krs1_next_queue_state": "ready_after_previous_review" if successor_gate_open else "blocked_on_previous_review",
        "launch_packet_status": str(launch_s.get("status", "")).strip(),
        "next_required_step": guarded_next_step if guarded_active and guarded_next_step else "DprE1 is resolved; T. cruzi KRS1 may now move into ready_after_previous_review." if successor_gate_open else "DprE1 is running; keep T. cruzi KRS1 blocked until the live run record reaches result-ready or explicit hold." if run_state["run_started"] else "Wait for Dengue to resolve before opening DprE1." if not upstream_gate_open else "DprE1 may move into ready_after_previous_review now; keep T. cruzi KRS1 blocked until the live run record resolves.",
    }, "structured": {
        "gate_policy": "open_dpre1_only_after_dengue_resolution_and_real_compound_fill",
        "downstream_policy": "tcruzi_krs1_stays_blocked_until_dpre1_guarded_gate51_review_is_explicitly_resolved" if guarded_active else "tcruzi_krs1_stays_blocked_until_dpre1_run_record_reaches_result_ready_or_explicit_hold",
    }, "rows": rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the DprE1 result-review surface as the third Wave 2 gate.")
    parser.add_argument("--upstream-review-json", default=DEFAULT_UPSTREAM_REVIEW_JSON)
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--successor-launch-json", default=DEFAULT_SUCCESSOR_LAUNCH_JSON)
    parser.add_argument("--run-record-json", default=DEFAULT_RUN_RECORD_JSON)
    parser.add_argument("--guarded-branch-summary-json", default=DEFAULT_GUARDED_BRANCH_SUMMARY_JSON)
    parser.add_argument("--exploratory-retry-lane-json", default=DEFAULT_EXPLORATORY_RETRY_LANE_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.upstream_review_json),
        load_json(args.launch_json),
        maybe_load_json(args.successor_launch_json),
        maybe_load_json(args.run_record_json),
        maybe_load_json(args.guarded_branch_summary_json),
        maybe_load_json(args.exploratory_retry_lane_json),
    )
    write_artifact(DEFAULT_OUT_MD, "DprE1 Result Review", payload)


if __name__ == "__main__":
    main()
