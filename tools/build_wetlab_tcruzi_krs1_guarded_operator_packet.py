#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, queue_status_is_resolved, write_artifact

TARGET_ID = "T. cruzi KRS1"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_HOLD_GUARD_JSON = "runs/wetlab_primary_hold_guard_surface_current.json"
DEFAULT_WATCH_ACTION_JSON = "runs/wetlab_broad_screen_primary_watch_action_current.json"
DEFAULT_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_tcruzi_krs1_stage6_tuning_surface_current.json"
DEFAULT_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_tcruzi_krs1_exploratory_retry_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_krs1_guarded_operator_packet_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _selected_threshold_a(command_kind: str) -> float:
    kind = _text(command_kind)
    if "gate45" in kind:
        return 4.5
    if "gate51" in kind:
        return 5.1
    if "gate55" in kind:
        return 5.5
    return 0.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _is_tuned_command(command_kind: str) -> bool:
    return "tuned_gate" in _text(command_kind) or _text(command_kind) == "throughput_preflight_tuned"


def _queue_rows_for_target(payload: dict[str, Any] | None, target_id: str) -> list[dict[str, Any]]:
    return [
        dict(row or {})
        for row in ((payload or {}).get("rows", []) or [])
        if _text((row or {}).get("target_id")) == _text(target_id)
    ]


def _current_queue_row(payload: dict[str, Any] | None, target_id: str) -> dict[str, Any]:
    rows = _queue_rows_for_target(payload, target_id)
    for row in rows:
        if not queue_status_is_resolved(row.get("queue_status", "")):
            return row
    return rows[-1] if rows else {}


def _hold_guard_row(payload: dict[str, Any] | None, target_id: str) -> dict[str, Any]:
    for row in ((payload or {}).get("rows", []) or []):
        if _text((row or {}).get("target_id")) == _text(target_id):
            return dict(row or {})
    return {}


def _select_command_kind(
    throughput_bridge_payload: dict[str, Any] | None,
    exploratory_retry_lane_payload: dict[str, Any] | None,
    stage6_tuning_surface_payload: dict[str, Any] | None,
    target_id: str,
) -> str:
    exploratory_summary = _summary(exploratory_retry_lane_payload)
    if _text(exploratory_summary.get("target_id")) == _text(target_id):
        selected = _text(exploratory_summary.get("selected_command_kind"))
        if selected:
            return selected

    tuning_summary = _summary(stage6_tuning_surface_payload)
    if _text(tuning_summary.get("target_id")) == _text(target_id):
        selected = _text(tuning_summary.get("immediately_runnable_command_kind"))
        if selected:
            return selected

    summary = _summary(throughput_bridge_payload)
    if _text(summary.get("target_id")) != _text(target_id):
        return "throughput_preflight"
    preferred = _text(summary.get("preferred_command_kind"))
    if preferred:
        return preferred

    rows = [dict(row or {}) for row in ((throughput_bridge_payload or {}).get("rows", []) or [])]
    priority = [
        "throughput_preflight_tuned_gate51",
        "throughput_preflight_tuned_gate55",
        "throughput_preflight_tuned_gate45",
        "throughput_preflight_tuned",
        "throughput_preflight",
    ]
    for kind in priority:
        for row in rows:
            if _text(row.get("command_kind")) == kind and _text(row.get("command")):
                return kind
    return "throughput_preflight"


def _packet_scope_for_command(command_kind: str) -> str:
    if "gate51" in _text(command_kind):
        return "partner_operator_guarded_gate51_review"
    if _is_tuned_command(command_kind):
        return "partner_operator_guarded_tuned_branch_review"
    return "partner_operator_guarded_stage6_review"


def _branch_mode_for_command(command_kind: str) -> str:
    if "gate51" in _text(command_kind):
        return "guarded_gate51_review"
    if _is_tuned_command(command_kind):
        return "guarded_tuned_branch_review"
    return "guarded_operator_review"


def _decision_case_for_command(command_kind: str) -> str:
    if "gate51" in _text(command_kind):
        return "tcruzi_krs1_guarded_gate51_review_candidate"
    if _is_tuned_command(command_kind):
        return "tcruzi_krs1_guarded_tuned_review_candidate"
    return "tcruzi_krs1_guarded_review_required"


def _action_for_command(command_kind: str) -> str:
    if "gate51" in _text(command_kind):
        return "pause_default_lane_and_review_gate51_retry"
    if _is_tuned_command(command_kind):
        return "review_tuned_branch_before_reopen"
    return "pause_default_lane_and_select_tuned_retry"


def _review_unit_label(command_kind: str) -> str:
    if "gate51" in _text(command_kind):
        return "guarded gate5.1 operator packet"
    if _is_tuned_command(command_kind):
        return "guarded tuned operator packet"
    return "guarded stage6 operator packet"


def _next_required_step(command_kind: str, shard_id: str) -> str:
    if "gate51" in _text(command_kind):
        return (
            f"Use the T. cruzi KRS1 guarded gate5.1 operator packet as the review unit for {shard_id}, keep the default lane closed, and review the gate5.1 exploratory retry before any reopen decision."
            if shard_id
            else "Use the T. cruzi KRS1 guarded gate5.1 operator packet, keep the default lane closed, and review the gate5.1 exploratory retry before any reopen decision."
        )
    if _is_tuned_command(command_kind):
        return (
            f"Use the T. cruzi KRS1 guarded tuned operator packet as the review unit for {shard_id}, keep the default lane closed, and review the tuned branch before any reopen decision."
            if shard_id
            else "Use the T. cruzi KRS1 guarded tuned operator packet, keep the default lane closed, and review the tuned branch before any reopen decision."
        )
    return (
        f"Use the T. cruzi KRS1 guarded operator packet as the stage6 review unit for {shard_id}, keep the default lane closed, and select a tuned retry preset before any reopen decision."
        if shard_id
        else "Use the T. cruzi KRS1 guarded operator packet as the stage6 review unit, keep the default lane closed, and select a tuned retry preset before any reopen decision."
    )


def _validated_next_required_step() -> str:
    return (
        "Promote T. cruzi KRS1 guarded gate5.1 as validated, keep the default lane closed, "
        "and allow LRRK2 to continue as the successor broad lane."
    )


def build_payload(
    execution_queue_payload: dict[str, Any] | None,
    throughput_bridge_payload: dict[str, Any] | None,
    hold_guard_payload: dict[str, Any] | None,
    watch_action_payload: dict[str, Any] | None,
    exploratory_retry_lane_payload: dict[str, Any] | None = None,
    stage6_tuning_surface_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    queue_summary = _summary(execution_queue_payload)
    watch_action = _summary(watch_action_payload)
    exploratory_summary = _summary(exploratory_retry_lane_payload)
    tuning_summary = _summary(stage6_tuning_surface_payload)
    current_row = _current_queue_row(execution_queue_payload, TARGET_ID)
    guard_row = _hold_guard_row(hold_guard_payload, TARGET_ID)
    command_kind = _select_command_kind(
        throughput_bridge_payload,
        exploratory_retry_lane_payload,
        stage6_tuning_surface_payload,
        TARGET_ID,
    )
    selected_threshold_a = _safe_float(
        exploratory_summary.get("selected_threshold_A"),
        _safe_float(
            tuning_summary.get("immediately_runnable_threshold_A"),
            _selected_threshold_a(command_kind),
        ),
    )
    packet_scope = _packet_scope_for_command(command_kind)
    branch_mode = _branch_mode_for_command(command_kind)
    queue_rows = _queue_rows_for_target(execution_queue_payload, TARGET_ID)
    success_count = sum(1 for row in queue_rows if "result_ready" in _text(row.get("queue_status")))
    hold_count = sum(1 for row in queue_rows if "explicit_hold" in _text(row.get("queue_status")))
    unresolved_count = sum(1 for row in queue_rows if not queue_status_is_resolved(row.get("queue_status", "")))
    shard_id = _text(current_row.get("shard_id"), queue_summary.get("first_actionable_shard_id"))
    queue_status_now = _text(current_row.get("queue_status"), default="blocked_on_target_review")
    guard_triggered = bool(guard_row.get("guard_triggered_now", False))
    packet_ready = bool(current_row) and guard_triggered
    branch_validated = unresolved_count == 0 and success_count > hold_count and "gate51" in _text(command_kind)
    gate51_validation_row_count = _safe_int(tuning_summary.get("gate51_validation_row_count"))
    gate51_validation_success_count = _safe_int(tuning_summary.get("gate51_validation_success_count"))
    gate51_validation_all_post_hold_success = bool(tuning_summary.get("gate51_validation_all_post_hold_success", False))
    gate51_validation_start_shard_id = _text(tuning_summary.get("gate51_validation_start_shard_id"))
    gate51_validation_end_shard_id = _text(tuning_summary.get("gate51_validation_end_shard_id"))
    gate51_validation_observed_metric_min_A = _safe_float(tuning_summary.get("gate51_validation_observed_metric_min_A"))
    gate51_validation_observed_metric_mean_A = _safe_float(tuning_summary.get("gate51_validation_observed_metric_mean_A"))
    gate51_validation_observed_metric_max_A = _safe_float(tuning_summary.get("gate51_validation_observed_metric_max_A"))
    status = (
        "wetlab_tcruzi_krs1_guarded_operator_packet_validated"
        if branch_validated
        else "wetlab_tcruzi_krs1_guarded_operator_packet_ready"
        if packet_ready
        else "wetlab_tcruzi_krs1_guarded_operator_packet_pending"
    )
    if branch_validated and "gate51" in _text(command_kind):
        packet_scope = "partner_operator_guarded_gate51_validated"
        branch_mode = "guarded_gate51_validated"

    return {
        "summary": {
            "status": status,
            "target_id": TARGET_ID,
            "shard_id": shard_id,
            "surface_label": "tcruzi_krs1_guarded_operator_packet",
            "packet_scope": packet_scope,
            "packet_ready": packet_ready or branch_validated,
            "packet_ready_for_operator_review": packet_ready or branch_validated,
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": False,
            "branch_mode": branch_mode,
            "review_unit_label": _review_unit_label(command_kind),
            "selected_command_kind": command_kind,
            "selected_threshold_A": round(selected_threshold_a, 3),
            "decision_case": _decision_case_for_command(command_kind),
            "action": _action_for_command(command_kind),
            "queue_status_now": queue_status_now,
            "success_shard_count": success_count,
            "hold_shard_count": hold_count,
            "unresolved_shard_count": unresolved_count,
            "branch_validated": branch_validated,
            "gate51_validation_row_count": gate51_validation_row_count,
            "gate51_validation_success_count": gate51_validation_success_count,
            "gate51_validation_all_post_hold_success": gate51_validation_all_post_hold_success,
            "gate51_validation_start_shard_id": gate51_validation_start_shard_id,
            "gate51_validation_end_shard_id": gate51_validation_end_shard_id,
            "gate51_validation_observed_metric_min_A": round(gate51_validation_observed_metric_min_A, 3),
            "gate51_validation_observed_metric_mean_A": round(gate51_validation_observed_metric_mean_A, 3),
            "gate51_validation_observed_metric_max_A": round(gate51_validation_observed_metric_max_A, 3),
            "guard_hold_streak": _safe_int(guard_row.get("recent_consecutive_auto_hold_streak")),
            "guard_hold_limit": _safe_int(guard_row.get("guard_limit")),
            "watch_action": _text(watch_action.get("action_taken")),
            "next_required_step": _validated_next_required_step() if branch_validated else _next_required_step(command_kind, shard_id),
        },
        "structured": {},
        "rows": [
            {
                "row_kind": "tcruzi_krs1_guarded_operator_packet_row",
                "target_id": TARGET_ID,
                "shard_id": shard_id,
                "packet_scope": packet_scope,
                "selected_command_kind": command_kind,
                "selected_threshold_A": round(selected_threshold_a, 3),
                "queue_status_now": queue_status_now,
                "success_shard_count": success_count,
                "hold_shard_count": hold_count,
                "gate51_validation_row_count": gate51_validation_row_count,
                "gate51_validation_success_count": gate51_validation_success_count,
                "gate51_validation_start_shard_id": gate51_validation_start_shard_id,
                "gate51_validation_end_shard_id": gate51_validation_end_shard_id,
                "guard_hold_streak": _safe_int(guard_row.get("recent_consecutive_auto_hold_streak")),
                "guard_hold_limit": _safe_int(guard_row.get("guard_limit")),
                "default_lane_reopen_allowed": False,
                "branch_mode": branch_mode,
            }
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the T. cruzi KRS1 guarded operator packet.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--throughput-bridge-json", default=DEFAULT_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--hold-guard-json", default=DEFAULT_HOLD_GUARD_JSON)
    parser.add_argument("--watch-action-json", default=DEFAULT_WATCH_ACTION_JSON)
    parser.add_argument("--exploratory-retry-lane-json", default=DEFAULT_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--stage6-tuning-surface-json", default=DEFAULT_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.execution_queue_json),
        maybe_load_json(args.throughput_bridge_json),
        maybe_load_json(args.hold_guard_json),
        maybe_load_json(args.watch_action_json),
        maybe_load_json(args.exploratory_retry_lane_json),
        maybe_load_json(args.stage6_tuning_surface_json),
    )
    write_artifact(args.out_md, "Wet-Lab T. cruzi KRS1 Guarded Operator Packet", payload)


if __name__ == "__main__":
    main()
