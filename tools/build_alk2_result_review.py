#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, wetlab_run_record_state, write_artifact

DEFAULT_LAUNCH_JSON = "runs/alk2_launch_packet_current.json"
DEFAULT_PLPRO_REVIEW_JSON = "runs/sarscov2_plpro_result_review_current.json"
DEFAULT_RUN_RECORD_JSON = "runs/alk2_run_record_current.json"
DEFAULT_OUT_MD = "runs/alk2_result_review_current.md"


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def build_payload(plpro_review: dict[str, Any] | None, launch_payload: dict[str, Any], run_record: dict[str, Any] | None = None) -> dict[str, Any]:
    plpro_s = _summary(plpro_review or {})
    launch_s = _summary(launch_payload)
    run_state = wetlab_run_record_state(run_record)

    plpro_review_state = str(plpro_s.get("plpro_review_state", "")).strip() or "blocked_on_cruzain_result_review"
    upstream_transition_resolved = bool(plpro_s.get("successor_gate_open", plpro_s.get("alk2_execution_gate_open", False)))

    if not upstream_transition_resolved:
        queue_status_now = "blocked_on_previous_review"
        result_review_gate_status = "blocked_on_plpro_result_review"
        next_queue_release_gate_status = "next_queue_release_blocked"
        next_queue_release_blocked = True
    elif run_state["explicit_hold"]:
        queue_status_now = "explicit_hold_ready_for_next_release"
        result_review_gate_status = "explicit_hold"
        next_queue_release_gate_status = "open_after_alk2_explicit_hold"
        next_queue_release_blocked = False
    elif run_state["result_review_ready"]:
        queue_status_now = "result_ready_for_next_release"
        result_review_gate_status = "result_ready"
        next_queue_release_gate_status = "open_after_alk2_result_ready"
        next_queue_release_blocked = False
    elif run_state["run_started"]:
        queue_status_now = "running_after_previous_review"
        result_review_gate_status = "running"
        next_queue_release_gate_status = "next_queue_release_blocked"
        next_queue_release_blocked = True
    else:
        queue_status_now = "ready_after_previous_review"
        result_review_gate_status = "ready_for_final_result_review"
        next_queue_release_gate_status = "next_queue_release_blocked"
        next_queue_release_blocked = True

    rows = [
        {"review_item": "upstream_plpro_review", "source_artifact": "runs/sarscov2_plpro_result_review_current.md", "current_signal": plpro_review_state, "gate_status": "resolved" if upstream_transition_resolved else "pending_upstream_review", "release_effect": "unlock_alk2_execution" if upstream_transition_resolved else "keep_alk2_prep_only"},
        {"review_item": "alk2_run_record", "source_artifact": "runs/alk2_run_record_current.md", "current_signal": run_state["status"], "gate_status": run_state["execution_state"], "release_effect": "live_alk2_run_record_controls_next_release_gate"},
        {"review_item": "alk2_execution_gate", "source_artifact": "runs/alk2_launch_packet_current.md", "current_signal": result_review_gate_status, "gate_status": result_review_gate_status, "release_effect": "final_review_step_before_any_next_release"},
        {"review_item": "next_queue_release_gate", "source_artifact": "runs/alk2_go_no_go_card_current.md", "current_signal": next_queue_release_gate_status, "gate_status": next_queue_release_gate_status, "release_effect": "no_next_release_before_alk2_review_resolution"},
    ]

    return {
        "summary": {
            "status": "alk2_result_review_ready",
            "target_id": "ALK2",
            "serialized_queue_rank": 3,
            "serialized_run_order": str(launch_s.get("serialized_run_order", "3_of_3_after_priority3")).strip() or "3_of_3_after_priority3",
            "partner_track_id": str(launch_s.get("partner_track_id", "M4K_open_science")).strip() or "M4K_open_science",
            "launch_packet_status": str(launch_s.get("status", "")).strip(),
            "queue_status_now": queue_status_now,
            "result_review_gate_status": result_review_gate_status,
            "upstream_dependency_target": "SARS-CoV-2 PLpro",
            "upstream_dependency_status": str(plpro_s.get("status", "")).strip() or "plpro_result_review_missing_or_not_yet_built",
            "upstream_dependency_review_state": plpro_review_state,
            "upstream_transition_resolved": upstream_transition_resolved,
            "execution_gate_open": upstream_transition_resolved,
            "alk2_run_record_detected": run_state["detected"],
            "alk2_run_record_status": run_state["status"],
            "alk2_execution_state": run_state["execution_state"],
            "alk2_result_review_ready": run_state["result_review_ready"],
            "alk2_explicit_hold": run_state["explicit_hold"],
            "final_review_role": "final_review_step_before_any_next_release",
            "next_queue_release_gate_status": next_queue_release_gate_status,
            "next_queue_release_blocked": next_queue_release_blocked,
            "blocking_rule_echo": str(launch_s.get("blocking_rule", "")).strip(),
            "next_required_step": (
                "ALK2 is resolved by explicit hold; the next release gate may now open."
                if upstream_transition_resolved and run_state["explicit_hold"]
                else "ALK2 is result-ready; the next release gate may now open."
                if upstream_transition_resolved and run_state["result_review_ready"]
                else "ALK2 is running; keep later release blocked until the live run record reaches result-ready or explicit hold."
                if upstream_transition_resolved and run_state["run_started"]
                else "Run the ALK2 mutant-aware result review now; it is the final review gate before any later release opens."
                if upstream_transition_resolved
                else "Keep ALK2 prep-only until the PLpro live result review reaches result-ready or explicit hold, then use this packet as the final review step before any later release."
            ),
        },
        "structured": {
            "execution_policy": "serialized_by_target",
            "upstream_gate_rule": "PLpro live result review must resolve before ALK2 execution opens.",
            "next_release_rule": "No later release opens until the live ALK2 run record reaches result-ready or explicit hold.",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized result-review artifact for ALK2.")
    parser.add_argument("--plpro-review-json", default=DEFAULT_PLPRO_REVIEW_JSON)
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--run-record-json", default=DEFAULT_RUN_RECORD_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(maybe_load_json(args.plpro_review_json), load_json(args.launch_json), maybe_load_json(args.run_record_json))
    write_artifact(DEFAULT_OUT_MD, "ALK2 Result Review", payload)


if __name__ == "__main__":
    main()
