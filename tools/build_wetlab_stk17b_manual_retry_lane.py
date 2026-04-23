#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

TARGET_ID = "STK17B (DRAK2)"
DEFAULT_HOLD_GUARD_JSON = "runs/wetlab_primary_hold_guard_surface_current.json"
DEFAULT_RETRY_HANDOFF_JSON = "runs/wetlab_retry_handoff_summary_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_PREVIOUS_LANE_JSON = "runs/wetlab_stk17b_manual_retry_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_stk17b_manual_retry_lane_current.md"
COMMAND_PREFERENCE = [
    "throughput_preflight_tuned_gate55",
    "throughput_execute_tuned_gate55",
    "throughput_preflight_tuned",
    "throughput_execute_tuned",
    "throughput_preflight",
    "throughput_execute",
]


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _shard_ordinal(value: Any) -> int:
    text = _text(value)
    if not text or "_of_" not in text:
        return 0
    try:
        return int(text.split("_of_", 1)[0])
    except Exception:
        return 0


def _shard_id_from_ordinal(ordinal: int, template: str) -> str:
    text = _text(template)
    if ordinal <= 0 or "_of_" not in text:
        return ""
    suffix = text.split("_of_", 1)[1]
    return f"{ordinal:02d}_of_{suffix}"


def _find_guard_row(hold_guard_payload: dict[str, Any]) -> dict[str, Any]:
    for row in hold_guard_payload.get("rows", []) or []:
        candidate = dict(row)
        if _text(candidate.get("target_id")) == TARGET_ID:
            return candidate
    return {}


def _find_retry_handoff_row(retry_handoff_payload: dict[str, Any]) -> dict[str, Any]:
    for row in retry_handoff_payload.get("rows", []) or []:
        candidate = dict(row)
        if _text(candidate.get("target_id")) == TARGET_ID:
            return candidate
    return {}


def _find_queue_row(execution_queue_payload: dict[str, Any]) -> dict[str, Any]:
    rows = [dict(row) for row in (execution_queue_payload.get("rows", []) or [])]
    preferred_statuses = {"ready_after_previous_shard", "running", "ready_first"}
    for row in rows:
        if _text(row.get("target_id")) == TARGET_ID and _text(row.get("queue_status")) in preferred_statuses:
            return row
    for row in rows:
        if _text(row.get("target_id")) == TARGET_ID:
            return row
    return {}


def _infer_campaign_start_shard_id(
    previous_lane_payload: dict[str, Any] | None,
    execution_queue_payload: dict[str, Any],
    current_shard_id: str,
) -> str:
    previous_summary = _summary(previous_lane_payload)
    preserved = _text(previous_summary.get("campaign_start_shard_id")) or _text(previous_summary.get("shard_id"))
    current_ordinal = _shard_ordinal(current_shard_id)
    predecessor_id = _shard_id_from_ordinal(current_ordinal - 1, current_shard_id) if current_ordinal > 1 else ""
    predecessor_resolved = False
    if predecessor_id:
        for row in execution_queue_payload.get("rows", []) or []:
            candidate = dict(row)
            if _text(candidate.get("target_id")) != TARGET_ID:
                continue
            if _text(candidate.get("shard_id")) != predecessor_id:
                continue
            if _text(candidate.get("queue_status")) in {"explicit_hold", "result_ready"}:
                predecessor_resolved = True
                break
    if preserved:
        if preserved == current_shard_id and predecessor_resolved:
            return predecessor_id
        return preserved
    if predecessor_resolved:
        return predecessor_id
    return current_shard_id


def _select_bridge_rows(throughput_bridge_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = [dict(row) for row in (throughput_bridge_payload.get("rows", []) or [])]

    def _find_row(kind: str, *, allow_disabled: bool = True) -> dict[str, Any]:
        for row in rows:
            if _text(row.get("command_kind")) != kind:
                continue
            if _text(row.get("command")) == "":
                continue
            if allow_disabled or bool(row.get("enabled", False)):
                return row
        return {}

    selected: dict[str, Any] = {}
    for kind in COMMAND_PREFERENCE:
        selected = _find_row(kind, allow_disabled=True)
        if selected:
            break
    follow_on_execute: dict[str, Any] = {}
    if selected:
        selected_kind = _text(selected.get("command_kind"))
        if "preflight" in selected_kind:
            follow_on_execute = _find_row(selected_kind.replace("preflight", "execute", 1), allow_disabled=True)
    return selected, follow_on_execute


def build_payload(
    hold_guard_payload: dict[str, Any],
    retry_handoff_payload: dict[str, Any],
    execution_queue_payload: dict[str, Any],
    throughput_bridge_payload: dict[str, Any],
    previous_lane_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hold_summary = _summary(hold_guard_payload)
    bridge_summary = _summary(throughput_bridge_payload)
    guard_row = _find_guard_row(hold_guard_payload)
    retry_row = _find_retry_handoff_row(retry_handoff_payload)
    queue_row = _find_queue_row(execution_queue_payload)
    selected_command_row, follow_on_execute_row = _select_bridge_rows(throughput_bridge_payload)

    shard_id = _text(queue_row.get("shard_id")) or _text(bridge_summary.get("shard_id"))
    selected_kind = _text(selected_command_row.get("command_kind"))
    selected_command = _text(selected_command_row.get("command"))
    follow_on_execute_kind = _text(follow_on_execute_row.get("command_kind"))
    follow_on_execute_command = _text(follow_on_execute_row.get("command"))
    campaign_start_shard_id = _infer_campaign_start_shard_id(previous_lane_payload, execution_queue_payload, shard_id)
    guard_active = bool(
        guard_row.get("guard_triggered_now", False)
        or _safe_int(guard_row.get("recent_consecutive_auto_hold_streak", 0)) >= _safe_int(hold_summary.get("guard_limit", 0))
    )
    ready_for_manual_retry = bool(
        guard_active
        and _text(queue_row.get("queue_status")) in {"ready_after_previous_shard", "ready_first"}
        and bool(selected_command)
    )
    recommended_retry_mode = (
        "guarded_tuned_gate55_manual_retry"
        if "gate55" in selected_kind
        else "guarded_manual_retry"
        if selected_kind
        else "blocked_no_enabled_retry_command"
    )
    runner_command = (
        f'python3 tools/run_wetlab_stk17b_manual_retry.py --shard-id "{shard_id}" --replace-heartbeat'
        if ready_for_manual_retry
        else ""
    )
    next_step = (
        f"Run the STK17B tuned gate55 manual retry runner for {shard_id}; keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        if ready_for_manual_retry and "gate55" in selected_kind
        else f"Run the STK17B manual retry runner for {shard_id}; keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        if ready_for_manual_retry
        else "Keep STK17B auto-start paused; no enabled guarded retry command is available yet."
    )
    return {
        "summary": {
            "status": "wetlab_stk17b_manual_retry_lane_ready",
            "target_id": TARGET_ID,
            "shard_id": shard_id,
            "campaign_start_shard_id": campaign_start_shard_id,
            "guard_active": guard_active,
            "guard_limit": _safe_int(hold_summary.get("guard_limit", 0)),
            "guard_hold_streak": _safe_int(guard_row.get("recent_consecutive_auto_hold_streak", 0)),
            "total_auto_hold_count": _safe_int(guard_row.get("total_auto_hold_count", 0)),
            "retry_handoff_decision": _text(retry_row.get("decision")) or "pause_auto_start",
            "recommended_retry_mode": recommended_retry_mode,
            "selected_command_kind": selected_kind,
            "throughput_execute_ready": bool(bridge_summary.get("throughput_execute_ready", False)),
            "ready_for_manual_retry": ready_for_manual_retry,
            "next_required_step": next_step,
        },
        "structured": {
            "hold_guard_artifact": "runs/wetlab_primary_hold_guard_surface_current.md",
            "retry_handoff_artifact": "runs/wetlab_retry_handoff_summary_current.md",
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "throughput_bridge_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
            "selected_bridge_summary_json": _text((throughput_bridge_payload.get("structured", {}) or {}).get("preferred_summary_json")),
        },
        "rows": [
            {
                "row_kind": "manual_retry_selection",
                "target_id": TARGET_ID,
                "shard_id": shard_id,
                "recommended_retry_mode": recommended_retry_mode,
                "selected_command_kind": selected_kind,
                "guard_active": guard_active,
                "guard_hold_streak": _safe_int(guard_row.get("recent_consecutive_auto_hold_streak", 0)),
                "ready_for_manual_retry": ready_for_manual_retry,
                "one_line_summary": next_step,
            },
            {
                "row_kind": "runner_command",
                "target_id": TARGET_ID,
                "shard_id": shard_id,
                "command_kind": "stk17b_manual_retry_runner",
                "command": runner_command,
            },
            {
                "row_kind": "selected_bridge_command",
                "target_id": TARGET_ID,
                "shard_id": shard_id,
                "command_kind": selected_kind,
                "command": selected_command,
            },
            {
                "row_kind": "follow_on_execute_command",
                "target_id": TARGET_ID,
                "shard_id": shard_id,
                "command_kind": follow_on_execute_kind,
                "command": follow_on_execute_command,
            },
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the guarded manual retry lane for STK17B (DRAK2).")
    parser.add_argument("--hold-guard-json", default=DEFAULT_HOLD_GUARD_JSON)
    parser.add_argument("--retry-handoff-json", default=DEFAULT_RETRY_HANDOFF_JSON)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--throughput-bridge-json", default=DEFAULT_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--previous-lane-json", default=DEFAULT_PREVIOUS_LANE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.hold_guard_json),
        load_json(args.retry_handoff_json),
        load_json(args.execution_queue_json),
        load_json(args.throughput_bridge_json),
        maybe_load_json(args.previous_lane_json),
    )
    write_artifact(args.out_md, "STK17B (DRAK2) Manual Retry Lane", payload)


if __name__ == "__main__":
    main()
