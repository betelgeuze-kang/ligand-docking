#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, wetlab_run_record_state, write_artifact

DEFAULT_LAUNCH_JSON = "runs/tcruzi_pde_launch_packet_current.json"
DEFAULT_CAIX_REVIEW_JSON = "runs/caix_result_review_current.json"
DEFAULT_RUN_RECORD_JSON = "runs/tcruzi_pde_run_record_current.json"
DEFAULT_OUT_MD = "runs/tcruzi_pde_result_review_current.md"


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def build_payload(
    caix_review: dict[str, Any] | None,
    launch_payload: dict[str, Any],
    run_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    caix_s = _summary(caix_review or {})
    launch_s = _summary(launch_payload)
    run_state = wetlab_run_record_state(run_record)

    caix_review_state = str(caix_s.get("caix_review_state", "")).strip() or "blocked_on_mpro_result_review"
    upstream_transition_resolved = bool(caix_s.get("successor_gate_open", caix_s.get("tcruzi_execution_gate_open", False)))

    if not upstream_transition_resolved:
        queue_status_now = "blocked_on_previous_review"
        result_review_gate_status = "blocked_on_caix_result_review"
        wave2_release_gate_status = "wave2_release_blocked"
        wave2_release_blocked = True
    elif run_state["explicit_hold"]:
        queue_status_now = "explicit_hold_ready_for_wave2_release"
        result_review_gate_status = "explicit_hold"
        wave2_release_gate_status = "open_after_tcruzi_explicit_hold"
        wave2_release_blocked = False
    elif run_state["result_review_ready"]:
        queue_status_now = "result_ready_for_wave2_release"
        result_review_gate_status = "result_ready"
        wave2_release_gate_status = "open_after_tcruzi_result_ready"
        wave2_release_blocked = False
    elif run_state["run_started"]:
        queue_status_now = "running_after_previous_review"
        result_review_gate_status = "running"
        wave2_release_gate_status = "wave2_release_blocked"
        wave2_release_blocked = True
    else:
        queue_status_now = "ready_after_previous_review"
        result_review_gate_status = "ready_for_final_result_review"
        wave2_release_gate_status = "wave2_release_blocked"
        wave2_release_blocked = True

    rows = [
        {
            "review_item": "upstream_caix_review",
            "source_artifact": "runs/caix_result_review_current.md",
            "current_signal": caix_review_state,
            "gate_status": "resolved" if upstream_transition_resolved else "pending_upstream_review",
            "release_effect": "unlock_tcruzi_execution" if upstream_transition_resolved else "keep_tcruzi_prep_only",
        },
        {
            "review_item": "tcruzi_run_record",
            "source_artifact": "runs/tcruzi_pde_run_record_current.md",
            "current_signal": run_state["status"],
            "gate_status": run_state["execution_state"],
            "release_effect": "live_tcruzi_run_record_controls_wave2_release_gate",
        },
        {
            "review_item": "tcruzi_execution_gate",
            "source_artifact": "runs/tcruzi_pde_launch_packet_current.md",
            "current_signal": result_review_gate_status,
            "gate_status": result_review_gate_status,
            "release_effect": "final_review_step_before_any_wave2_release",
        },
        {
            "review_item": "wave2_release_gate",
            "source_artifact": "runs/tcruzi_pde_go_no_go_card_current.md",
            "current_signal": wave2_release_gate_status,
            "gate_status": wave2_release_gate_status,
            "release_effect": "no_wave2_release_before_tcruzi_review_resolution",
        },
    ]

    return {
        "summary": {
            "status": "tcruzi_pde_result_review_ready",
            "target_id": "T. cruzi PDE",
            "serialized_queue_rank": int(launch_s.get("serialized_queue_rank", 3) or 3),
            "serialized_run_order": str(launch_s.get("serialized_run_order", "3_of_3")).strip() or "3_of_3",
            "partner_track_id": str(launch_s.get("partner_track_id", "DNDi_IPK")).strip() or "DNDi_IPK",
            "launch_packet_status": str(launch_s.get("status", "")).strip(),
            "queue_status_now": queue_status_now,
            "result_review_gate_status": result_review_gate_status,
            "upstream_dependency_target": "CA IX",
            "upstream_dependency_status": str(caix_s.get("status", "")).strip() or "caix_result_review_missing_or_not_yet_built",
            "upstream_dependency_review_state": caix_review_state,
            "upstream_transition_resolved": upstream_transition_resolved,
            "execution_gate_open": upstream_transition_resolved,
            "tcruzi_run_record_detected": run_state["detected"],
            "tcruzi_run_record_status": run_state["status"],
            "tcruzi_execution_state": run_state["execution_state"],
            "tcruzi_result_review_ready": run_state["result_review_ready"],
            "tcruzi_explicit_hold": run_state["explicit_hold"],
            "final_review_role": "final_review_step_before_any_wave2_release",
            "wave2_release_gate_status": wave2_release_gate_status,
            "wave2_release_blocked": wave2_release_blocked,
            "blocking_rule_echo": str(launch_s.get("blocking_rule", "")).strip(),
            "next_required_step": (
                "T. cruzi PDE is resolved by explicit hold; the wave-2 release gate may now open."
                if upstream_transition_resolved and run_state["explicit_hold"]
                else "T. cruzi PDE is result-ready; the wave-2 release gate may now open."
                if upstream_transition_resolved and run_state["result_review_ready"]
                else "T. cruzi PDE is running; keep wave-2 release blocked until the live run record reaches result-ready or explicit hold."
                if upstream_transition_resolved and run_state["run_started"]
                else "Run the T. cruzi PDE parasite-versus-human result review now; it is the final review gate before any wave-2 release opens."
                if upstream_transition_resolved
                else "Keep T. cruzi PDE prep-only until the CA IX live result review reaches result-ready or explicit hold, then use this packet as the final review step before any wave-2 release."
            ),
        },
        "structured": {
            "execution_policy": "serialized_by_target",
            "upstream_gate_rule": "CA IX live result review must resolve before T. cruzi PDE execution opens.",
            "wave2_release_rule": "No wave-2 release opens until the live T. cruzi run record reaches result-ready or explicit hold.",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized result-review artifact for T. cruzi PDE.")
    parser.add_argument("--caix-review-json", default=DEFAULT_CAIX_REVIEW_JSON)
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--run-record-json", default=DEFAULT_RUN_RECORD_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.caix_review_json),
        load_json(args.launch_json),
        maybe_load_json(args.run_record_json),
    )
    write_artifact(DEFAULT_OUT_MD, "T. cruzi PDE Result Review", payload)


if __name__ == "__main__":
    main()
