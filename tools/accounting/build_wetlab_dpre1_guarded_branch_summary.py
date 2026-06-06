#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab.build_wetlab_dpre1_guarded_operator_packet import (
    DEFAULT_EXECUTION_QUEUE_JSON,
    DEFAULT_EXPLORATORY_RETRY_LANE_JSON,
    DEFAULT_HOLD_GUARD_JSON,
    DEFAULT_STAGE6_TUNING_SURFACE_JSON,
    DEFAULT_THROUGHPUT_BRIDGE_JSON,
    DEFAULT_WATCH_ACTION_JSON,
    TARGET_ID,
    _is_tuned_command,
    _safe_int,
    _summary,
    _text,
    build_payload as build_operator_packet_payload,
)
from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

DEFAULT_OPERATOR_PACKET_JSON = "runs/wetlab_dpre1_guarded_operator_packet_current.json"
DEFAULT_OUT_MD = "runs/wetlab_dpre1_guarded_branch_summary_current.md"


def _branch_label(command_kind: str) -> str:
    if "gate51" in _text(command_kind):
        return "dpre1_guarded_gate51_branch"
    if _is_tuned_command(command_kind):
        return "dpre1_guarded_tuned_branch"
    return "dpre1_guarded_review_branch"


def _branch_state(command_kind: str) -> str:
    if "gate51" in _text(command_kind):
        return "guarded_gate51_review_default_lane_closed"
    if _is_tuned_command(command_kind):
        return "guarded_tuned_branch_review_default_lane_closed"
    return "operator_review_ready_default_lane_closed"


def _next_required_step(command_kind: str, shard_id: str) -> str:
    if "gate51" in _text(command_kind):
        return (
            f"Review DprE1 through the guarded gate5.1 branch for {shard_id}, keep the default lane closed, and do not reopen auto-start until the gate5.1 exploratory retry is explicitly resolved."
            if shard_id
            else "Review DprE1 through the guarded gate5.1 branch, keep the default lane closed, and do not reopen auto-start until the gate5.1 exploratory retry is explicitly resolved."
        )
    if _is_tuned_command(command_kind):
        return (
            f"Review DprE1 through the guarded tuned branch for {shard_id}, keep the default lane closed, and do not reopen auto-start until the tuned review is explicitly resolved."
            if shard_id
            else "Review DprE1 through the guarded tuned branch, keep the default lane closed, and do not reopen auto-start until the tuned review is explicitly resolved."
        )
    return (
        f"Review DprE1 through the guarded stage6 branch for {shard_id}, keep the default lane closed, and do not reopen auto-start until a tuned retry preset is selected."
        if shard_id
        else "Review DprE1 through the guarded stage6 branch, keep the default lane closed, and do not reopen auto-start until a tuned retry preset is selected."
    )


def build_payload(
    operator_packet_payload: dict[str, Any] | None,
    execution_queue_payload: dict[str, Any] | None,
    hold_guard_payload: dict[str, Any] | None,
    watch_action_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    operator_packet = _summary(operator_packet_payload)
    watch_action = _summary(watch_action_payload)
    command_kind = _text(operator_packet.get("selected_command_kind"), default="throughput_preflight")
    shard_id = _text(operator_packet.get("shard_id"))
    queue_status_now = _text(operator_packet.get("queue_status_now"))
    branch_label = _branch_label(command_kind)
    branch_state = _branch_state(command_kind)
    operator_packet_ready = bool(operator_packet.get("packet_ready", False))

    return {
        "summary": {
            "status": "wetlab_dpre1_guarded_branch_summary_ready" if operator_packet_ready else "wetlab_dpre1_guarded_branch_summary_pending",
            "target_id": TARGET_ID,
            "shard_id": shard_id,
            "branch_label": branch_label,
            "branch_state": branch_state,
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": False,
            "branch_to_tuned_only": _is_tuned_command(command_kind),
            "review_unit_label": _text(operator_packet.get("review_unit_label")),
            "selected_command_kind": command_kind,
            "selected_threshold_A": operator_packet.get("selected_threshold_A", 0.0),
            "decision_case": _text(operator_packet.get("decision_case")),
            "action": _text(operator_packet.get("action")),
            "operator_packet_ready": operator_packet_ready,
            "operator_packet_scope": _text(operator_packet.get("packet_scope")),
            "success_shard_count": _safe_int(operator_packet.get("success_shard_count")),
            "hold_shard_count": _safe_int(operator_packet.get("hold_shard_count")),
            "guard_hold_streak": _safe_int(operator_packet.get("guard_hold_streak")),
            "guard_hold_limit": _safe_int(operator_packet.get("guard_hold_limit")),
            "queue_status_now": queue_status_now,
            "watch_action": _text(watch_action.get("action_taken")),
            "next_required_step": _next_required_step(command_kind, shard_id),
        },
        "structured": {},
        "rows": [
            {
                "row_kind": "dpre1_guarded_branch_step",
                "step_id": "operator_packet",
                "status": _text(operator_packet.get("status")),
                "signal": _text(operator_packet.get("packet_scope"), f"{_safe_int(operator_packet.get('hold_shard_count'))} hold"),
            },
            {
                "row_kind": "dpre1_guarded_branch_step",
                "step_id": "watch_action",
                "status": _text(watch_action.get("status")),
                "signal": _text(watch_action.get("action_taken"), watch_action.get("next_required_step")),
            },
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the DprE1 guarded branch summary.")
    parser.add_argument("--operator-packet-json", default=DEFAULT_OPERATOR_PACKET_JSON)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--hold-guard-json", default=DEFAULT_HOLD_GUARD_JSON)
    parser.add_argument("--watch-action-json", default=DEFAULT_WATCH_ACTION_JSON)
    parser.add_argument("--exploratory-retry-lane-json", default=DEFAULT_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--stage6-tuning-surface-json", default=DEFAULT_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    operator_packet_payload = maybe_load_json(args.operator_packet_json)
    if not operator_packet_payload:
        operator_packet_payload = build_operator_packet_payload(
            maybe_load_json(args.execution_queue_json),
            maybe_load_json(DEFAULT_THROUGHPUT_BRIDGE_JSON),
            maybe_load_json(args.hold_guard_json),
            maybe_load_json(args.watch_action_json),
            maybe_load_json(args.exploratory_retry_lane_json),
            maybe_load_json(args.stage6_tuning_surface_json),
        )
    payload = build_payload(
        operator_packet_payload,
        maybe_load_json(args.execution_queue_json),
        maybe_load_json(args.hold_guard_json),
        maybe_load_json(args.watch_action_json),
    )
    write_artifact(args.out_md, "Wet-Lab DprE1 Guarded Branch Summary", payload)


if __name__ == "__main__":
    main()
