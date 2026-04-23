from __future__ import annotations

from typing import Any

DEFAULT_LOCAL_ENGINE_COMMERCIALIZATION_QUEUE_JSON = "runs/local_engine_commercialization_queue_current.json"
DEFAULT_LOCAL_ENGINE_COMMERCIALIZATION_QUEUE_MD = "runs/local_engine_commercialization_queue_current.md"
DEFAULT_NIGHTLY_GATE_BURNDOWN_PACKET_MD = "runs/nightly_gate_burndown_packet_current.md"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_text(value: Any, digits: int = 3) -> str:
    try:
        if value in {None, ""}:
            return "-"
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def _rows_by_blocker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("blocker_id")): dict(row)
        for row in payload.get("rows", []) or []
        if _text(row.get("blocker_id"))
    }


def summarize_local_engine_commercialization_queue(
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(payload or {})
    summary = dict(payload.get("summary", {}) or {})
    rows_by_blocker = _rows_by_blocker(payload)

    row_count = _int(summary.get("row_count", len(rows_by_blocker)))
    top_priority_id = _text(summary.get("top_priority_id"))
    top_priority_status = _text(summary.get("top_priority_status"))
    top_row = dict(rows_by_blocker.get(top_priority_id, {}) or {})
    transporter_row = dict(rows_by_blocker.get("transporter_science_blocker", {}) or {})
    ready = bool(summary or rows_by_blocker)
    nightly_gate_ready = bool(summary.get("nightly_gate_burndown_ready", False))
    nightly_gate_artifact = _text(summary.get("nightly_gate_burndown_artifact")) or (
        DEFAULT_NIGHTLY_GATE_BURNDOWN_PACKET_MD if nightly_gate_ready else ""
    )
    nightly_gate_primary_metric = _text(summary.get("nightly_gate_primary_metric"))
    nightly_gate_primary_value = _text(summary.get("nightly_gate_primary_value"))
    nightly_gate_primary_threshold = _text(summary.get("nightly_gate_primary_threshold"))
    nightly_gate_primary_delta = _text(summary.get("nightly_gate_primary_delta"))
    nightly_gate_status_line = _text(summary.get("nightly_gate_status_line"))
    nightly_gate_recent_transition_line = _text(summary.get("nightly_gate_recent_transition_line"))
    nightly_gate_recent_stage6_fail_count = _int(summary.get("nightly_gate_recent_stage6_fail_count"))
    nightly_gate_next_required_step = _text(summary.get("nightly_gate_next_required_step"))

    blocker_signal_parts = [
        f"local_engine_row_count={row_count}" if row_count else "",
        (
            f"local_engine_blocked={_int(summary.get('blocked_count'))}; "
            f"local_engine_partial={_int(summary.get('partial_count'))}; "
            f"local_engine_keep_green={_int(summary.get('keep_green_count'))}; "
            f"local_engine_parked_science={_int(summary.get('parked_science_blocker_count'))}"
        )
        if ready
        else "",
        f"local_engine_top_priority={top_priority_id}" if top_priority_id else "",
        f"local_engine_top_status={top_priority_status}" if top_priority_status else "",
        f"local_engine_engine_blockers={_int(summary.get('engine_blocker_count'))}" if ready else "",
        f"local_engine_science_blockers={_int(summary.get('science_blocker_count'))}" if ready else "",
        (
            f"local_engine_transporter_status={_text(transporter_row.get('status'))}"
            if transporter_row
            else ""
        ),
        (
            f"local_engine_nightly_gate_metric={nightly_gate_primary_metric}; "
            f"local_engine_nightly_gate_delta={_float_text(nightly_gate_primary_delta)}; "
            f"local_engine_nightly_gate_artifact={nightly_gate_artifact}"
            if nightly_gate_ready and nightly_gate_primary_metric
            else ""
        ),
    ]
    blocker_signal = "; ".join(part for part in blocker_signal_parts if part)

    blocker_note = ""
    if ready:
        top_label = top_priority_id.replace("_", " ") if top_priority_id else "the local-engine commercialization queue"
        blocker_note = (
            f"Local-only commercialization is still queue-gated by {DEFAULT_LOCAL_ENGINE_COMMERCIALIZATION_QUEUE_MD}: "
            f"{top_label}"
            + (f" is {top_priority_status}" if top_priority_status else "")
            + ", and transporter science work stays parked behind nightly reliability, viewer usability, and wetlab execution readiness."
        )
        if top_priority_id == "nightly_reliability" and top_priority_status == "partial" and nightly_gate_ready:
            blocker_note += (
                " The nightly stage6 burndown packet at "
                f"{nightly_gate_artifact or DEFAULT_NIGHTLY_GATE_BURNDOWN_PACKET_MD} is tracking "
                f"{nightly_gate_primary_metric or 'mean_min_distance_A'}="
                f"{_float_text(nightly_gate_primary_value)} versus {_float_text(nightly_gate_primary_threshold)} "
                f"(+{_float_text(nightly_gate_primary_delta)} over threshold)."
            )

    next_required_step = _text(summary.get("next_required_step")) or _text(top_row.get("next_required_action"))

    return {
        "local_engine_commercialization_queue_ready": ready,
        "local_engine_commercialization_queue_artifact": (
            DEFAULT_LOCAL_ENGINE_COMMERCIALIZATION_QUEUE_MD if ready else ""
        ),
        "local_engine_commercialization_queue_row_count": row_count,
        "local_engine_commercialization_queue_blocked_count": _int(summary.get("blocked_count")),
        "local_engine_commercialization_queue_partial_count": _int(summary.get("partial_count")),
        "local_engine_commercialization_queue_keep_green_count": _int(summary.get("keep_green_count")),
        "local_engine_commercialization_queue_parked_science_blocker_count": _int(
            summary.get("parked_science_blocker_count")
        ),
        "local_engine_commercialization_queue_top_priority_id": top_priority_id,
        "local_engine_commercialization_queue_top_priority_status": top_priority_status,
        "local_engine_commercialization_queue_engine_blocker_count": _int(summary.get("engine_blocker_count")),
        "local_engine_commercialization_queue_science_blocker_count": _int(summary.get("science_blocker_count")),
        "local_engine_commercialization_queue_nightly_gate_burndown_ready": bool(
            summary.get("nightly_gate_burndown_ready", False)
        ),
        "local_engine_commercialization_queue_nightly_gate_burndown_artifact": _text(
            summary.get("nightly_gate_burndown_artifact")
        )
        or (DEFAULT_NIGHTLY_GATE_BURNDOWN_PACKET_MD if summary.get("nightly_gate_burndown_ready") else ""),
        "local_engine_commercialization_queue_nightly_gate_primary_metric": _text(
            summary.get("nightly_gate_primary_metric")
        ),
        "local_engine_commercialization_queue_nightly_gate_primary_value": _text(
            summary.get("nightly_gate_primary_value")
        ),
        "local_engine_commercialization_queue_nightly_gate_primary_threshold": _text(
            summary.get("nightly_gate_primary_threshold")
        ),
        "local_engine_commercialization_queue_nightly_gate_primary_delta": _text(
            summary.get("nightly_gate_primary_delta")
        ),
        "local_engine_commercialization_queue_nightly_gate_status_line": nightly_gate_status_line,
        "local_engine_commercialization_queue_nightly_gate_recent_transition_line": _text(
            summary.get("nightly_gate_recent_transition_line")
        ),
        "local_engine_commercialization_queue_nightly_gate_recent_stage6_fail_count": nightly_gate_recent_stage6_fail_count,
        "local_engine_commercialization_queue_nightly_gate_next_required_step": nightly_gate_next_required_step,
        "local_engine_commercialization_queue_top_priority_signal": _text(top_row.get("source_signal")),
        "local_engine_commercialization_queue_top_priority_next_required_action": _text(
            top_row.get("next_required_action")
        ),
        "local_engine_commercialization_queue_transporter_science_blocker_status": _text(
            transporter_row.get("status")
        ),
        "local_engine_commercialization_queue_transporter_science_blocker_signal": _text(
            transporter_row.get("source_signal")
        ),
        "local_engine_commercialization_queue_transporter_science_blocker_next_required_action": _text(
            transporter_row.get("next_required_action")
        ),
        "local_engine_commercialization_queue_blocker_signal": blocker_signal,
        "local_engine_commercialization_queue_blocker_note": blocker_note,
        "local_engine_commercialization_queue_next_required_step": next_required_step,
    }


def local_engine_summary_from_source(summary_source: dict[str, Any] | None = None) -> dict[str, Any]:
    summary_source = dict(summary_source or {})
    keys = [
        "local_engine_commercialization_queue_ready",
        "local_engine_commercialization_queue_artifact",
        "local_engine_commercialization_queue_row_count",
        "local_engine_commercialization_queue_blocked_count",
        "local_engine_commercialization_queue_partial_count",
        "local_engine_commercialization_queue_keep_green_count",
        "local_engine_commercialization_queue_parked_science_blocker_count",
        "local_engine_commercialization_queue_top_priority_id",
        "local_engine_commercialization_queue_top_priority_status",
        "local_engine_commercialization_queue_engine_blocker_count",
        "local_engine_commercialization_queue_science_blocker_count",
        "local_engine_commercialization_queue_nightly_gate_burndown_ready",
        "local_engine_commercialization_queue_nightly_gate_burndown_artifact",
        "local_engine_commercialization_queue_nightly_gate_primary_metric",
        "local_engine_commercialization_queue_nightly_gate_primary_value",
        "local_engine_commercialization_queue_nightly_gate_primary_threshold",
        "local_engine_commercialization_queue_nightly_gate_primary_delta",
        "local_engine_commercialization_queue_nightly_gate_status_line",
        "local_engine_commercialization_queue_nightly_gate_recent_transition_line",
        "local_engine_commercialization_queue_nightly_gate_recent_stage6_fail_count",
        "local_engine_commercialization_queue_nightly_gate_next_required_step",
        "local_engine_commercialization_queue_top_priority_signal",
        "local_engine_commercialization_queue_top_priority_next_required_action",
        "local_engine_commercialization_queue_transporter_science_blocker_status",
        "local_engine_commercialization_queue_transporter_science_blocker_signal",
        "local_engine_commercialization_queue_transporter_science_blocker_next_required_action",
        "local_engine_commercialization_queue_blocker_signal",
        "local_engine_commercialization_queue_blocker_note",
        "local_engine_commercialization_queue_next_required_step",
    ]
    hydrated = {key: summary_source.get(key, "") for key in keys}
    hydrated["local_engine_commercialization_queue_ready"] = bool(
        summary_source.get("local_engine_commercialization_queue_ready", False)
    )
    hydrated["local_engine_commercialization_queue_nightly_gate_burndown_ready"] = bool(
        summary_source.get("local_engine_commercialization_queue_nightly_gate_burndown_ready", False)
    )
    for key in (
        "local_engine_commercialization_queue_row_count",
        "local_engine_commercialization_queue_blocked_count",
        "local_engine_commercialization_queue_partial_count",
        "local_engine_commercialization_queue_keep_green_count",
        "local_engine_commercialization_queue_parked_science_blocker_count",
        "local_engine_commercialization_queue_engine_blocker_count",
        "local_engine_commercialization_queue_science_blocker_count",
        "local_engine_commercialization_queue_nightly_gate_recent_stage6_fail_count",
    ):
        hydrated[key] = _int(summary_source.get(key))
    return hydrated
