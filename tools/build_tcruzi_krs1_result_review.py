#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, wetlab_run_record_state, write_artifact

DEFAULT_UPSTREAM_REVIEW_JSON = "runs/dpre1_result_review_current.json"
DEFAULT_LAUNCH_JSON = "runs/tcruzi_krs1_launch_packet_current.json"
DEFAULT_SUCCESSOR_LAUNCH_JSON = "runs/lrrk2_launch_packet_current.json"
DEFAULT_RUN_RECORD_JSON = "runs/tcruzi_krs1_run_record_current.json"
DEFAULT_OUT_MD = "runs/tcruzi_krs1_result_review_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def build_payload(upstream_review: dict[str, Any] | None, launch_payload: dict[str, Any], successor_launch: dict[str, Any] | None, run_record: dict[str, Any] | None = None) -> dict:
    upstream_s = _summary(upstream_review)
    launch_s = _summary(launch_payload)
    successor_s = _summary(successor_launch)
    run_state = wetlab_run_record_state(run_record)

    upstream_gate_state = str(upstream_s.get("successor_gate_state", "")).strip() or "blocked_on_dpre1_result_review"
    upstream_gate_open = bool(upstream_s.get("successor_gate_open", False))
    content_ready = str(launch_s.get("launch_readiness", "")).strip() == "ready_for_serialized_execution"
    execution_gate_open = upstream_gate_open and content_ready

    if not upstream_gate_open:
        review_state = "blocked_on_dpre1_result_review"
        queue_status_now = "blocked_on_previous_review"
        successor_gate_state = "blocked_on_tcruzi_krs1_result_review"
        successor_gate_open = False
    elif not content_ready:
        review_state = "blocked_on_target_content"
        queue_status_now = "blocked_on_target_content"
        successor_gate_state = "blocked_on_tcruzi_krs1_result_review"
        successor_gate_open = False
    elif run_state["explicit_hold"]:
        review_state = "tcruzi_krs1_result_review_resolved"
        queue_status_now = "explicit_hold_ready_for_successor"
        successor_gate_state = "open_for_lrrk2_execution"
        successor_gate_open = True
    elif run_state["result_review_ready"]:
        review_state = "tcruzi_krs1_result_review_resolved"
        queue_status_now = "result_ready_for_successor"
        successor_gate_state = "open_for_lrrk2_execution"
        successor_gate_open = True
    elif run_state["run_started"]:
        review_state = "tcruzi_krs1_result_review_in_progress"
        queue_status_now = "running_after_previous_review"
        successor_gate_state = "blocked_on_tcruzi_krs1_result_review"
        successor_gate_open = False
    else:
        review_state = "ready_to_capture_tcruzi_krs1_result_review"
        queue_status_now = "ready_after_previous_review"
        successor_gate_state = "blocked_on_tcruzi_krs1_result_review"
        successor_gate_open = False

    rows = [
        {"review_item": "dpre1_release_gate", "source_artifact": "runs/dpre1_result_review_current.md", "queue_phrase": "DprE1 must resolve before T. cruzi KRS1 may leave blocked_on_previous_review.", "gate_status": upstream_gate_state},
        {"review_item": "tcruzi_krs1_content_gate", "source_artifact": "runs/tcruzi_krs1_launch_packet_current.md", "queue_phrase": "T. cruzi KRS1 launch packet is fill-ready; only the DprE1 predecessor gate still blocks execution." if content_ready else "keep T. cruzi KRS1 blocked until the repurposing and novelty lanes are actually filled", "gate_status": str(launch_s.get("launch_readiness", "")).strip() or "missing_launch_packet"},
        {"review_item": "tcruzi_krs1_run_record", "source_artifact": "runs/tcruzi_krs1_run_record_current.md", "queue_phrase": "Live T. cruzi KRS1 run records advance this review from ready to running to resolved.", "gate_status": run_state["status"]},
        {"review_item": "successor_hold", "source_artifact": "runs/lrrk2_launch_packet_current.md", "queue_phrase": str(successor_s.get("blocking_rule", "")).strip() or "LRRK2 stays closed until T. cruzi KRS1 resolves.", "gate_status": successor_gate_state},
    ]

    return {"summary": {
        "status": "tcruzi_krs1_result_review_ready",
        "target_id": "T. cruzi KRS1",
        "serialized_queue_rank": int(launch_s.get("serialized_queue_rank", 4) or 4),
        "serialized_run_order": str(launch_s.get("serialized_run_order", "4_of_5_in_wave2")).strip() or "4_of_5_in_wave2",
        "partner_track_id": str(launch_s.get("partner_track_id", "DNDi_Chagas_backup")).strip() or "DNDi_Chagas_backup",
        "upstream_gate_state": upstream_gate_state,
        "upstream_gate_open": upstream_gate_open,
        "content_ready": content_ready,
        "tcruzi_krs1_gate_open": execution_gate_open,
        "tcruzi_krs1_review_state": review_state,
        "tcruzi_krs1_run_record_detected": run_state["detected"],
        "tcruzi_krs1_run_record_status": run_state["status"],
        "tcruzi_krs1_execution_state": run_state["execution_state"],
        "tcruzi_krs1_result_review_ready": run_state["result_review_ready"],
        "tcruzi_krs1_explicit_hold": run_state["explicit_hold"],
        "queue_status_now": queue_status_now,
        "successor_target": "LRRK2",
        "successor_gate_state": successor_gate_state,
        "successor_gate_open": successor_gate_open,
        "lrrk2_next_queue_state": "ready_after_previous_review" if successor_gate_open else "blocked_on_previous_review",
        "launch_packet_status": str(launch_s.get("status", "")).strip(),
        "next_required_step": "T. cruzi KRS1 is resolved; LRRK2 may now move into ready_after_previous_review." if successor_gate_open else "T. cruzi KRS1 is running; keep LRRK2 blocked until the live run record reaches result-ready or explicit hold." if run_state["run_started"] else "Wait for DprE1 to resolve before opening T. cruzi KRS1." if not upstream_gate_open else "T. cruzi KRS1 may move into ready_after_previous_review now; keep LRRK2 blocked until the live run record resolves.",
    }, "structured": {
        "gate_policy": "open_tcruzi_krs1_only_after_dpre1_resolution_and_real_compound_fill",
        "downstream_policy": "lrrk2_stays_blocked_until_tcruzi_krs1_run_record_reaches_result_ready_or_explicit_hold",
    }, "rows": rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the T. cruzi KRS1 result-review surface as the fourth Wave 2 gate.")
    parser.add_argument("--upstream-review-json", default=DEFAULT_UPSTREAM_REVIEW_JSON)
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--successor-launch-json", default=DEFAULT_SUCCESSOR_LAUNCH_JSON)
    parser.add_argument("--run-record-json", default=DEFAULT_RUN_RECORD_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(maybe_load_json(args.upstream_review_json), load_json(args.launch_json), maybe_load_json(args.successor_launch_json), maybe_load_json(args.run_record_json))
    write_artifact(DEFAULT_OUT_MD, "T. cruzi KRS1 Result Review", payload)


if __name__ == "__main__":
    main()
