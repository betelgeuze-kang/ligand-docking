from __future__ import annotations

from typing import Any

DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_JSON = "runs/wetlab_execution_readiness_queue_current.json"
DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_CSV = "runs/wetlab_execution_readiness_queue_current.csv"
DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_MD = "runs/wetlab_execution_readiness_queue_current.md"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _rows_by_lane(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("lane_id")): dict(row)
        for row in payload.get("rows", []) or []
        if _text(row.get("lane_id"))
    }


def _top_priority_row(payload: dict[str, Any]) -> dict[str, Any]:
    rows = [dict(row) for row in payload.get("rows", []) or [] if isinstance(row, dict)]
    if not rows:
        return {}
    rows.sort(key=lambda row: (_int(row.get("queue_rank")) or 10**9, _text(row.get("lane_id"))))
    return rows[0]


def summarize_wetlab_execution_readiness_queue(
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(payload or {})
    summary = dict(payload.get("summary", {}) or {})
    rows_by_lane = _rows_by_lane(payload)
    top_row = _top_priority_row(payload)

    ready = bool(summary or rows_by_lane)
    row_count = _int(summary.get("row_count", len(rows_by_lane)))
    artifact = _text(summary.get("queue_artifact")) or (DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_MD if ready else "")
    top_priority_lane_id = _text(summary.get("top_priority_lane_id")) or _text(top_row.get("lane_id"))
    top_priority_status = _text(summary.get("top_priority_status")) or _text(top_row.get("status"))
    top_priority_signal = _text(summary.get("top_priority_signal")) or _text(top_row.get("signal"))
    top_priority_next_required_action = _text(summary.get("top_priority_next_required_action")) or _text(
        top_row.get("next_required_action")
    )
    primary_watch_liveness = _text(summary.get("primary_watch_liveness"))
    antitarget_watch_liveness = _text(summary.get("antitarget_watch_liveness"))
    watch_gap_count = _int(summary.get("watch_gap_count"))
    execution_ready_now_row_count = _int(summary.get("execution_ready_now_row_count"))
    antitarget_ready_now_row_count = _int(summary.get("antitarget_ready_now_row_count"))
    ready_to_send_track_count = _int(summary.get("ready_to_send_track_count"))
    selected_allatom_wetlab_gate_pass = bool(summary.get("selected_allatom_wetlab_gate_pass", False))
    selected_allatom_focus_label = _text(summary.get("selected_allatom_focus_label"))
    selected_allatom_block_reason = _text(summary.get("selected_allatom_block_reason"))
    status_line = _text(summary.get("status_line"))

    blocker_signal_parts = [
        f"wetlab_queue_rows={row_count}" if row_count else "",
        (
            f"wetlab_blocked={_int(summary.get('blocked_count'))}; "
            f"wetlab_partial={_int(summary.get('partial_count'))}; "
            f"wetlab_ready={_int(summary.get('ready_count'))}"
        )
        if ready
        else "",
        f"wetlab_top_priority={top_priority_lane_id}" if top_priority_lane_id else "",
        f"wetlab_top_status={top_priority_status}" if top_priority_status else "",
        f"wetlab_primary_watch={primary_watch_liveness}" if primary_watch_liveness else "",
        f"wetlab_antitarget_watch={antitarget_watch_liveness}" if antitarget_watch_liveness else "",
        f"wetlab_watch_gap_count={watch_gap_count}" if watch_gap_count else "",
        f"wetlab_primary_ready_now={execution_ready_now_row_count}",
        f"wetlab_antitarget_ready_now={antitarget_ready_now_row_count}",
        f"wetlab_ready_to_send_tracks={ready_to_send_track_count}" if ready_to_send_track_count else "",
        f"wetlab_selected_allatom_gate_pass={selected_allatom_wetlab_gate_pass}",
        f"wetlab_queue_artifact={artifact}" if artifact else "",
    ]
    blocker_signal = "; ".join(part for part in blocker_signal_parts if part)

    blocker_note = ""
    if ready:
        top_label = top_priority_lane_id.replace("_", " ") if top_priority_lane_id else "wetlab execution readiness"
        blocker_note = (
            f"Wetlab execution readiness is still queue-gated by {artifact or DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_MD}: "
            f"{top_label}"
            + (f" is {top_priority_status}" if top_priority_status else "")
            + (
                f", primary watch is {primary_watch_liveness} and antitarget watch is {antitarget_watch_liveness}"
                if primary_watch_liveness or antitarget_watch_liveness
                else ""
            )
            + (
                f", and the selected all-atom gate is {'passing' if selected_allatom_wetlab_gate_pass else 'failing'}"
                if summary.get("selected_allatom_wetlab_gate_pass") is not None or selected_allatom_wetlab_gate_pass
                else ""
            )
            + "."
        )

    next_required_step = _text(summary.get("next_required_step")) or top_priority_next_required_action

    return {
        "wetlab_execution_readiness_queue_ready": ready,
        "wetlab_execution_readiness_queue_json": (
            DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_JSON if ready else ""
        ),
        "wetlab_execution_readiness_queue_csv": (
            DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_CSV if ready else ""
        ),
        "wetlab_execution_readiness_queue_artifact": artifact,
        "wetlab_execution_readiness_queue_row_count": row_count,
        "wetlab_execution_readiness_queue_blocked_count": _int(summary.get("blocked_count")),
        "wetlab_execution_readiness_queue_partial_count": _int(summary.get("partial_count")),
        "wetlab_execution_readiness_queue_ready_count": _int(summary.get("ready_count")),
        "wetlab_execution_readiness_queue_top_priority_lane_id": top_priority_lane_id,
        "wetlab_execution_readiness_queue_top_priority_status": top_priority_status,
        "wetlab_execution_readiness_queue_top_priority_signal": top_priority_signal,
        "wetlab_execution_readiness_queue_top_priority_next_required_action": top_priority_next_required_action,
        "wetlab_execution_readiness_queue_primary_watch_liveness": primary_watch_liveness,
        "wetlab_execution_readiness_queue_antitarget_watch_liveness": antitarget_watch_liveness,
        "wetlab_execution_readiness_queue_watch_gap_count": watch_gap_count,
        "wetlab_execution_readiness_queue_execution_ready_now_row_count": execution_ready_now_row_count,
        "wetlab_execution_readiness_queue_antitarget_ready_now_row_count": antitarget_ready_now_row_count,
        "wetlab_execution_readiness_queue_ready_to_send_track_count": ready_to_send_track_count,
        "wetlab_execution_readiness_queue_selected_allatom_wetlab_gate_pass": selected_allatom_wetlab_gate_pass,
        "wetlab_execution_readiness_queue_selected_allatom_focus_label": selected_allatom_focus_label,
        "wetlab_execution_readiness_queue_selected_allatom_block_reason": selected_allatom_block_reason,
        "wetlab_execution_readiness_queue_status_line": status_line,
        "wetlab_execution_readiness_queue_blocker_signal": blocker_signal,
        "wetlab_execution_readiness_queue_blocker_note": blocker_note,
        "wetlab_execution_readiness_queue_next_required_step": next_required_step,
    }


def wetlab_summary_from_source(summary_source: dict[str, Any] | None = None) -> dict[str, Any]:
    summary_source = dict(summary_source or {})
    keys = [
        "wetlab_execution_readiness_queue_ready",
        "wetlab_execution_readiness_queue_json",
        "wetlab_execution_readiness_queue_csv",
        "wetlab_execution_readiness_queue_artifact",
        "wetlab_execution_readiness_queue_row_count",
        "wetlab_execution_readiness_queue_blocked_count",
        "wetlab_execution_readiness_queue_partial_count",
        "wetlab_execution_readiness_queue_ready_count",
        "wetlab_execution_readiness_queue_top_priority_lane_id",
        "wetlab_execution_readiness_queue_top_priority_status",
        "wetlab_execution_readiness_queue_top_priority_signal",
        "wetlab_execution_readiness_queue_top_priority_next_required_action",
        "wetlab_execution_readiness_queue_primary_watch_liveness",
        "wetlab_execution_readiness_queue_antitarget_watch_liveness",
        "wetlab_execution_readiness_queue_watch_gap_count",
        "wetlab_execution_readiness_queue_execution_ready_now_row_count",
        "wetlab_execution_readiness_queue_antitarget_ready_now_row_count",
        "wetlab_execution_readiness_queue_ready_to_send_track_count",
        "wetlab_execution_readiness_queue_selected_allatom_wetlab_gate_pass",
        "wetlab_execution_readiness_queue_selected_allatom_focus_label",
        "wetlab_execution_readiness_queue_selected_allatom_block_reason",
        "wetlab_execution_readiness_queue_status_line",
        "wetlab_execution_readiness_queue_blocker_signal",
        "wetlab_execution_readiness_queue_blocker_note",
        "wetlab_execution_readiness_queue_next_required_step",
    ]
    hydrated = {key: summary_source.get(key, "") for key in keys}
    hydrated["wetlab_execution_readiness_queue_ready"] = bool(
        summary_source.get("wetlab_execution_readiness_queue_ready", False)
    )
    hydrated["wetlab_execution_readiness_queue_selected_allatom_wetlab_gate_pass"] = bool(
        summary_source.get("wetlab_execution_readiness_queue_selected_allatom_wetlab_gate_pass", False)
    )
    for key in (
        "wetlab_execution_readiness_queue_row_count",
        "wetlab_execution_readiness_queue_blocked_count",
        "wetlab_execution_readiness_queue_partial_count",
        "wetlab_execution_readiness_queue_ready_count",
        "wetlab_execution_readiness_queue_watch_gap_count",
        "wetlab_execution_readiness_queue_execution_ready_now_row_count",
        "wetlab_execution_readiness_queue_antitarget_ready_now_row_count",
        "wetlab_execution_readiness_queue_ready_to_send_track_count",
    ):
        hydrated[key] = _int(summary_source.get(key))
    return hydrated
