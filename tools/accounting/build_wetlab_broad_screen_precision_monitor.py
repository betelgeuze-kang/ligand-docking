#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import statistics
from typing import Any

from tools.wetlab_broad_screen_watch_utils import slug
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_PROGRESS_JSON = "runs/wetlab_broad_screen_progress_current.json"
DEFAULT_RERANK_JSON = "runs/wetlab_broad_screen_target_rerank_current.json"
DEFAULT_SOURCE_JSON = "runs/wetlab_broad_screen_bulk_results_source_current.json"
DEFAULT_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_STK17B_MANUAL_RETRY_LANE_JSON = "runs/wetlab_stk17b_manual_retry_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_precision_monitor_current.md"


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _minutes_between(start: datetime | None, end: datetime | None) -> float:
    if start is None or end is None:
        return 0.0
    delta = end - start
    return max(delta.total_seconds() / 60.0, 0.0)


def _round1(value: float) -> float:
    return round(value, 1)


def _median_or_zero(values: list[float]) -> float:
    filtered = [float(value) for value in values if float(value) > 0]
    if not filtered:
        return 0.0
    return _round1(float(statistics.median(filtered)))


def _runtime_baseline_minutes(
    values: list[float],
    *,
    windows: tuple[int, ...] = (3, 5, 7),
    floor: float = 5.0,
) -> float:
    filtered = [float(value) for value in values if float(value) > 0]
    if not filtered:
        return 0.0
    candidate_medians: list[float] = []
    seen_lengths: set[int] = set()
    for window in windows:
        sample_size = min(len(filtered), int(window))
        if sample_size <= 0 or sample_size in seen_lengths:
            continue
        seen_lengths.add(sample_size)
        candidate_medians.append(float(statistics.median(filtered[-sample_size:])))
    if len(filtered) not in seen_lengths:
        candidate_medians.append(float(statistics.median(filtered)))
    baseline = float(statistics.median(candidate_medians)) if candidate_medians else 0.0
    if floor > 0.0:
        baseline = max(baseline, float(floor))
    return _round1(baseline)


def _queue_rows_by_target(payload: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in ((payload or {}).get("rows", []) or []):
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        grouped.setdefault(target_id, []).append(dict(row))
    return grouped


def _progress_rows_by_target(payload: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in ((payload or {}).get("rows", []) or []):
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        grouped.setdefault(target_id, []).append(dict(row))
    return grouped


def _progress_row_by_key(
    grouped: dict[str, list[dict[str, Any]]],
    target_id: str,
    shard_id: str,
) -> dict[str, Any]:
    rows = grouped.get(target_id, [])
    for row in rows:
        if str(row.get("shard_id", "")).strip() == shard_id:
            return dict(row)
    return {}


def _rerank_rows_by_target(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in ((payload or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip()
    }


def _source_rows_by_target(payload: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in ((payload or {}).get("rows", []) or []):
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        grouped.setdefault(target_id, []).append(dict(row))
    return grouped


def _resolved_status_kind(status: Any) -> str:
    text = str(status or "").strip()
    if "result_ready" in text:
        return "success"
    if "explicit_hold" in text:
        return "hold"
    return ""


def _shard_ordinal(shard_id: Any) -> int:
    text = str(shard_id or "").strip()
    if not text or "_of_" not in text:
        return 0
    try:
        return int(text.split("_of_", 1)[0])
    except Exception:
        return 0


def _load_hold_summary(row: dict[str, Any]) -> dict[str, Any]:
    target_id = str(row.get("target_id", "")).strip()
    shard_id = str(row.get("shard_id", "")).strip()
    target_slug = str(row.get("target_slug", "")).strip() or slug(target_id)
    if not target_id or not shard_id:
        return {}
    base = ROOT / "runs" / "wetlab_broad_screen_throughput" / target_slug / shard_id
    candidates = [
        base / "throughput_run_gate55_summary.json",
        base / "throughput_run_summary.json",
        *sorted(base.glob("*_summary.json")),
    ]
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        payload = maybe_load_json(str(path))
        if payload and (
            payload.get("service_result")
            or payload.get("stages")
            or str(payload.get("run_scope", "")).strip() == "full"
        ):
            return payload
    return {}


def _hold_failure_mode(row: dict[str, Any]) -> str:
    payload = _load_hold_summary(row)
    service = dict(payload.get("service_result", {}) or {})
    failed_stage = str(payload.get("failed_stage", service.get("failed_stage", "")) or "").strip()
    if failed_stage == "stage1_ligand_mapping":
        return "mapping_failed"
    if failed_stage == "stage6_operational_gate":
        return "gate_failed"
    return "other_hold"


def _target_slug(target_id: str, row: dict[str, Any]) -> str:
    existing = str(row.get("target_slug", "")).strip()
    if existing:
        return existing
    slug = target_id.strip().lower()
    for src, dst in (
        ("sars-cov-2", "sars_cov_2"),
        ("t. cruzi", "t_cruzi"),
        ("l. braziliensis", "leishmania_braziliensis"),
        (" ", "_"),
        (".", ""),
        ("-", "_"),
        ("/", "_"),
        ("(", ""),
        (")", ""),
    ):
        slug = slug.replace(src, dst)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


def _throughput_summary_path(target_id: str, row: dict[str, Any]) -> Path:
    target_slug = _target_slug(target_id, row)
    shard_id = str(row.get("shard_id", "")).strip()
    gate55 = "gate55" in str(row.get("notes", "")).lower()
    name = "throughput_run_gate55_summary.json" if gate55 else "throughput_run_summary.json"
    return ROOT / "runs" / "wetlab_broad_screen_throughput" / target_slug / shard_id / name


def _load_summary_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return maybe_load_json(str(path)) or {}


def _resolved_failure_class(target_id: str, row: dict[str, Any]) -> str:
    status_kind = _resolved_status_kind(row.get("queue_status", ""))
    if status_kind == "success":
        return "success"
    if status_kind != "hold":
        return ""
    payload = _load_summary_json(_throughput_summary_path(target_id, row))
    service = dict(payload.get("service_result", {}) or {})
    failed_stage = str(payload.get("failed_stage", service.get("failed_stage", "")) or "").strip()
    if failed_stage == "stage1_ligand_mapping":
        return "mapping_failed"
    if failed_stage == "stage6_operational_gate":
        return "gate_failed"
    return "hold_other"


def build_payload(
    execution_queue: dict[str, Any],
    progress_payload: dict[str, Any] | None = None,
    rerank_payload: dict[str, Any] | None = None,
    source_payload: dict[str, Any] | None = None,
    compound_universe: dict[str, Any] | None = None,
    stk17b_manual_retry_lane: dict[str, Any] | None = None,
) -> dict[str, Any]:
    queue_summary = dict((execution_queue or {}).get("summary", {}) or {})
    progress_summary = dict((progress_payload or {}).get("summary", {}) or {})
    rerank_summary = dict((rerank_payload or {}).get("summary", {}) or {})
    universe_summary = dict((compound_universe or {}).get("summary", {}) or {})
    stk17b_manual_retry_summary = dict((stk17b_manual_retry_lane or {}).get("summary", {}) or {})

    queue_rows_by_target = _queue_rows_by_target(execution_queue)
    progress_rows_by_target = _progress_rows_by_target(progress_payload)
    rerank_rows_by_target = _rerank_rows_by_target(rerank_payload)
    source_rows_by_target = _source_rows_by_target(source_payload)

    all_completed_minutes: list[float] = []
    rows: list[dict[str, Any]] = []
    now = datetime.now()
    resolved_class_counts = {
        "success": 0,
        "mapping_failed": 0,
        "gate_failed": 0,
        "hold_other": 0,
    }

    for target_id in sorted(queue_rows_by_target):
        target_queue_rows = queue_rows_by_target[target_id]
        target_progress_rows = progress_rows_by_target.get(target_id, [])
        target_rerank = rerank_rows_by_target.get(target_id, {})
        target_source_rows = source_rows_by_target.get(target_id, [])

        total_shards = len(target_queue_rows)
        target_resolved_class_counts = {
            "success": 0,
            "mapping_failed": 0,
            "gate_failed": 0,
            "hold_other": 0,
        }
        for resolved_row in target_queue_rows:
            failure_class = _resolved_failure_class(target_id, resolved_row)
            if failure_class:
                target_resolved_class_counts[failure_class] += 1
                resolved_class_counts[failure_class] += 1
        completed_shards = target_resolved_class_counts["success"]
        mapping_failed_shards = target_resolved_class_counts["mapping_failed"]
        gate_failed_shards = target_resolved_class_counts["gate_failed"]
        hold_other_shards = target_resolved_class_counts["hold_other"]
        held_shards = mapping_failed_shards + gate_failed_shards + hold_other_shards
        running_rows = [row for row in target_queue_rows if "running" in str(row.get("queue_status", ""))]
        running_shards = len(running_rows)
        remaining_shards = max(total_shards - completed_shards - held_shards - running_shards, 0)
        completion_pct = _round1(((completed_shards + held_shards) / total_shards) * 100.0) if total_shards else 0.0
        successful_completion_pct = _round1((completed_shards / total_shards) * 100.0) if total_shards else 0.0
        held_completion_pct = _round1((held_shards / total_shards) * 100.0) if total_shards else 0.0
        mapping_failed_completion_pct = _round1((mapping_failed_shards / total_shards) * 100.0) if total_shards else 0.0
        gate_failed_completion_pct = _round1((gate_failed_shards / total_shards) * 100.0) if total_shards else 0.0
        hold_other_completion_pct = _round1((hold_other_shards / total_shards) * 100.0) if total_shards else 0.0

        completed_progress_rows = [row for row in target_progress_rows if _resolved_status_kind(row.get("queue_status", "")) == "success"]
        held_progress_rows = [row for row in target_progress_rows if _resolved_status_kind(row.get("queue_status", "")) == "hold"]
        completed_minutes = [
            _minutes_between(_parse_ts(row.get("started_at")), _parse_ts(row.get("completed_at") or row.get("updated_at")))
            for row in completed_progress_rows
            if _minutes_between(_parse_ts(row.get("started_at")), _parse_ts(row.get("completed_at") or row.get("updated_at"))) > 0
        ]
        held_minutes = [
            _minutes_between(_parse_ts(row.get("started_at")), _parse_ts(row.get("completed_at") or row.get("updated_at")))
            for row in held_progress_rows
            if _minutes_between(_parse_ts(row.get("started_at")), _parse_ts(row.get("completed_at") or row.get("updated_at"))) > 0
        ]
        all_completed_minutes.extend(completed_minutes)
        avg_completed_minutes = _round1(sum(completed_minutes) / len(completed_minutes)) if completed_minutes else 0.0
        median_completed_minutes = _median_or_zero(completed_minutes)
        recent_completed_minutes = completed_minutes[-3:] if completed_minutes else []
        recent_median_completed_minutes = _median_or_zero(recent_completed_minutes)
        hold_median_minutes = _median_or_zero(held_minutes)

        running_row = running_rows[0] if running_rows else {}
        running_shard_id = str(running_row.get("shard_id", "")).strip()
        running_progress_row = _progress_row_by_key(progress_rows_by_target, target_id, running_shard_id) if running_shard_id else {}
        running_started_at = _parse_ts(
            running_progress_row.get("started_at")
            or running_row.get("progress_started_at")
            or running_row.get("started_at")
        )
        running_updated_at = _parse_ts(
            running_progress_row.get("updated_at")
            or running_row.get("progress_updated_at")
            or running_row.get("updated_at")
        )
        current_elapsed_minutes = _round1(_minutes_between(running_started_at, now)) if running_started_at else 0.0
        signal_age_minutes = _round1(_minutes_between(running_updated_at, now)) if running_updated_at else 0.0
        heartbeat_count = int(running_progress_row.get("heartbeat_count", running_row.get("heartbeat_count", 0)) or 0)
        event_count = int(running_progress_row.get("event_count", running_row.get("event_count", 0)) or 0)
        last_event = str(running_progress_row.get("last_event", running_row.get("last_event", ""))).strip()
        active_stage_label = str(
            running_progress_row.get("active_stage_label", running_row.get("active_stage_label", ""))
        ).strip()
        runtime_baseline_minutes = _runtime_baseline_minutes(completed_minutes)
        estimated_running_shard_pct = (
            _round1((current_elapsed_minutes / runtime_baseline_minutes) * 100.0)
            if runtime_baseline_minutes > 0 and current_elapsed_minutes > 0
            else 0.0
        )

        last_completed_at = ""
        if completed_progress_rows:
            latest = max(
                (
                    _parse_ts(row.get("completed_at") or row.get("updated_at"))
                    for row in completed_progress_rows
                ),
                key=lambda x: x or datetime.min,
            )
            last_completed_at = latest.isoformat(timespec="seconds") if latest else ""

        row = {
            "target_id": target_id,
            "total_shards": total_shards,
            "completed_shards": completed_shards,
            "held_shards": held_shards,
            "mapping_failed_shards": mapping_failed_shards,
            "gate_failed_shards": gate_failed_shards,
            "hold_other_shards": hold_other_shards,
            "running_shards": running_shards,
            "remaining_shards": remaining_shards,
            "completion_pct": completion_pct,
            "successful_completion_pct": successful_completion_pct,
            "held_completion_pct": held_completion_pct,
            "mapping_failed_completion_pct": mapping_failed_completion_pct,
            "gate_failed_completion_pct": gate_failed_completion_pct,
            "hold_other_completion_pct": hold_other_completion_pct,
            "current_running_shard": running_shard_id,
            "current_elapsed_minutes": current_elapsed_minutes,
            "signal_age_minutes": signal_age_minutes,
            "heartbeat_count": heartbeat_count,
            "event_count": event_count,
            "last_event": last_event,
            "active_stage_label": active_stage_label,
            "estimated_running_shard_pct": estimated_running_shard_pct,
            "avg_completed_shard_minutes": avg_completed_minutes,
            "median_completed_shard_minutes": median_completed_minutes,
            "recent_median_completed_shard_minutes": recent_median_completed_minutes,
            "hold_median_completed_shard_minutes": hold_median_minutes,
            "runtime_baseline_minutes": runtime_baseline_minutes,
            "last_completed_at": last_completed_at,
            "source_row_count": len(target_source_rows),
            "actual_row_count": int(target_rerank.get("actual_row_count", 0) or 0),
            "bootstrap_row_count": int(target_rerank.get("bootstrap_row_count", 0) or 0),
            "actual_top3_count": int(target_rerank.get("actual_top3_count", 0) or 0),
            "rerank_status": str(target_rerank.get("rerank_status", "")).strip(),
            "top1_compound": str(target_rerank.get("top1_compound", "")).strip(),
            "top2_compound": str(target_rerank.get("top2_compound", "")).strip(),
            "top3_compound": str(target_rerank.get("top3_compound", "")).strip(),
        }
        rows.append(row)

    total_shards = int(queue_summary.get("queue_row_count", len((execution_queue or {}).get("rows", []) or [])) or 0)
    resolved_shards = int(queue_summary.get("resolved_row_count", 0) or 0)
    successful_resolved_shards = resolved_class_counts["success"]
    mapping_failed_resolved_shards = resolved_class_counts["mapping_failed"]
    gate_failed_resolved_shards = resolved_class_counts["gate_failed"]
    hold_other_resolved_shards = resolved_class_counts["hold_other"]
    held_resolved_shards = mapping_failed_resolved_shards + gate_failed_resolved_shards + hold_other_resolved_shards
    running_shards = int(queue_summary.get("running_row_count", 0) or 0)
    pending_shards = max(total_shards - resolved_shards - running_shards, 0)
    completion_pct = _round1((resolved_shards / total_shards) * 100.0) if total_shards else 0.0
    successful_completion_pct = _round1((successful_resolved_shards / total_shards) * 100.0) if total_shards else 0.0
    held_completion_pct = _round1((held_resolved_shards / total_shards) * 100.0) if total_shards else 0.0
    mapping_failed_completion_pct = _round1((mapping_failed_resolved_shards / total_shards) * 100.0) if total_shards else 0.0
    gate_failed_completion_pct = _round1((gate_failed_resolved_shards / total_shards) * 100.0) if total_shards else 0.0
    hold_other_completion_pct = _round1((hold_other_resolved_shards / total_shards) * 100.0) if total_shards else 0.0
    avg_completed_shard_minutes = _round1(sum(all_completed_minutes) / len(all_completed_minutes)) if all_completed_minutes else 0.0
    median_completed_shard_minutes = _median_or_zero(all_completed_minutes)
    recent_all_completed_minutes = all_completed_minutes[-3:] if all_completed_minutes else []
    recent_median_completed_shard_minutes = _median_or_zero(recent_all_completed_minutes)
    runtime_baseline_minutes = _runtime_baseline_minutes(all_completed_minutes)
    estimated_remaining_minutes = _round1((pending_shards + running_shards) * avg_completed_shard_minutes) if avg_completed_shard_minutes else 0.0

    focus_target_id = str(queue_summary.get("first_actionable_target_id", "")).strip()
    focus_shard_id = str(queue_summary.get("first_actionable_shard_id", "")).strip()
    focus_target_row = next((row for row in rows if row["target_id"] == focus_target_id), {})
    current_target_completion_pct = float(focus_target_row.get("completion_pct", 0.0) or 0.0)
    current_target_remaining_shards = int(focus_target_row.get("remaining_shards", 0) or 0)
    first_actionable_queue_status = str(queue_summary.get("first_actionable_queue_status", "")).strip()
    focus_mode = (
        "stale"
        if focus_target_id and "stale_running" in first_actionable_queue_status
        else "running"
        if focus_target_id and ("running" in first_actionable_queue_status or (running_shards > 0 and not first_actionable_queue_status))
        else "dispatch_ready"
        if focus_target_id
        else "idle"
    )
    focus_elapsed_minutes = (
        float(focus_target_row.get("current_elapsed_minutes", 0.0) or 0.0)
        if focus_mode == "running"
        else 0.0
    )
    focus_signal_age_minutes = float(focus_target_row.get("signal_age_minutes", 0.0) or 0.0) if focus_target_row else 0.0
    focus_heartbeat_count = int(focus_target_row.get("heartbeat_count", 0) or 0) if focus_target_row else 0
    focus_event_count = int(focus_target_row.get("event_count", 0) or 0) if focus_target_row else 0
    focus_last_event = str(focus_target_row.get("last_event", "")).strip() if focus_target_row else ""
    focus_active_stage_label = str(focus_target_row.get("active_stage_label", "")).strip() if focus_target_row else ""
    focus_estimated_running_shard_pct = (
        float(focus_target_row.get("estimated_running_shard_pct", 0.0) or 0.0) if focus_target_row else 0.0
    )
    focus_runtime_baseline_minutes = (
        float(focus_target_row.get("runtime_baseline_minutes", 0.0) or 0.0) if focus_target_row else 0.0
    )
    active_target_id = focus_target_id if focus_mode == "running" else ""
    active_shard_id = focus_shard_id if focus_mode == "running" else ""

    stk17b_retry_target_id = str(stk17b_manual_retry_summary.get("target_id", "")).strip()
    stk17b_retry_start_shard_id = str(
        stk17b_manual_retry_summary.get("campaign_start_shard_id", stk17b_manual_retry_summary.get("shard_id", ""))
    ).strip()
    stk17b_retry_start_ordinal = _shard_ordinal(stk17b_retry_start_shard_id)
    stk17b_retry_rows = []
    if stk17b_retry_target_id and stk17b_retry_start_ordinal > 0:
        for row in queue_rows_by_target.get(stk17b_retry_target_id, []):
            row_ordinal = _shard_ordinal(row.get("shard_id"))
            if row_ordinal >= stk17b_retry_start_ordinal:
                stk17b_retry_rows.append(dict(row))
    stk17b_retry_success_rows = [
        row for row in stk17b_retry_rows if _resolved_status_kind(row.get("queue_status", "")) == "success"
    ]
    stk17b_retry_hold_rows = [
        row for row in stk17b_retry_rows if _resolved_status_kind(row.get("queue_status", "")) == "hold"
    ]
    stk17b_retry_running_rows = [
        row for row in stk17b_retry_rows if "running" in str(row.get("queue_status", "")).strip()
    ]
    stk17b_retry_resolved_rows = len(stk17b_retry_success_rows) + len(stk17b_retry_hold_rows)
    stk17b_retry_total_seen = len(stk17b_retry_rows)
    stk17b_retry_success_pct = _round1((len(stk17b_retry_success_rows) / stk17b_retry_resolved_rows) * 100.0) if stk17b_retry_resolved_rows else 0.0
    stk17b_retry_hold_pct = _round1((len(stk17b_retry_hold_rows) / stk17b_retry_resolved_rows) * 100.0) if stk17b_retry_resolved_rows else 0.0
    stk17b_retry_last_resolved = {}
    if stk17b_retry_resolved_rows:
        stk17b_retry_last_resolved = max(
            stk17b_retry_success_rows + stk17b_retry_hold_rows,
            key=lambda row: _shard_ordinal(row.get("shard_id")),
        )
    stk17b_retry_last_outcome = _resolved_status_kind(stk17b_retry_last_resolved.get("queue_status", ""))
    stk17b_retry_last_outcome_shard_id = str(stk17b_retry_last_resolved.get("shard_id", "")).strip()

    next_required_step = (
        f"Continue monitoring {focus_target_id} shard {focus_shard_id}; merge the next actual row when this shard completes."
        if focus_target_id and focus_shard_id and running_shards > 0
        else f"Recover stale {focus_target_id} shard {focus_shard_id}, then relaunch it and resume result-row merges."
        if focus_target_id and focus_shard_id and "stale_running" in first_actionable_queue_status
        else f"Dispatch {focus_target_id} shard {focus_shard_id} and keep the shard-level result intake packet ready."
        if focus_target_id and focus_shard_id
        else "Broad-screen queue is resolved; aggregate target-level actual rows and refresh autofill outputs."
    )

    return {
        "summary": {
            "status": "wetlab_broad_screen_precision_monitor_ready",
            "target_count": len(rows),
            "library_size": int(universe_summary.get("target_library_size", queue_summary.get("target_library_size", 0)) or 0),
            "ingested_compound_count": int(universe_summary.get("deduped_compound_count", queue_summary.get("ingested_compound_count", 0)) or 0),
            "total_shards": total_shards,
            "resolved_shards": resolved_shards,
            "successful_resolved_shards": successful_resolved_shards,
            "mapping_failed_resolved_shards": mapping_failed_resolved_shards,
            "gate_failed_resolved_shards": gate_failed_resolved_shards,
            "hold_other_resolved_shards": hold_other_resolved_shards,
            "held_resolved_shards": held_resolved_shards,
            "running_shards": running_shards,
            "pending_shards": pending_shards,
            "completion_pct": completion_pct,
            "successful_completion_pct": successful_completion_pct,
            "held_completion_pct": held_completion_pct,
            "mapping_failed_completion_pct": mapping_failed_completion_pct,
            "gate_failed_completion_pct": gate_failed_completion_pct,
            "hold_other_completion_pct": hold_other_completion_pct,
            "full_bulk_ready_target_count": int(rerank_summary.get("full_bulk_ready_target_count", 0) or 0),
            "partial_actual_target_count": int(rerank_summary.get("partial_actual_target_count", 0) or 0),
            "focus_mode": focus_mode,
            "focus_target_id": focus_target_id,
            "focus_shard_id": focus_shard_id,
            "focus_queue_status": first_actionable_queue_status,
            "focus_target_completion_pct": current_target_completion_pct,
            "focus_target_remaining_shards": current_target_remaining_shards,
            "focus_elapsed_minutes": focus_elapsed_minutes,
            "focus_signal_age_minutes": focus_signal_age_minutes,
            "focus_heartbeat_count": focus_heartbeat_count,
            "focus_event_count": focus_event_count,
            "focus_last_event": focus_last_event,
            "focus_active_stage_label": focus_active_stage_label,
            "focus_estimated_running_shard_pct": focus_estimated_running_shard_pct,
            "focus_runtime_baseline_minutes": focus_runtime_baseline_minutes,
            "active_target_id": active_target_id,
            "active_shard_id": active_shard_id,
            "active_target_completion_pct": current_target_completion_pct,
            "active_target_remaining_shards": current_target_remaining_shards,
            "active_elapsed_minutes": focus_elapsed_minutes,
            "average_completed_shard_minutes": avg_completed_shard_minutes,
            "median_completed_shard_minutes": median_completed_shard_minutes,
            "recent_median_completed_shard_minutes": recent_median_completed_shard_minutes,
            "runtime_baseline_minutes": runtime_baseline_minutes,
            "estimated_remaining_minutes": estimated_remaining_minutes,
            "progress_row_count": int(progress_summary.get("row_count", 0) or 0),
            "stk17b_retry_ready_for_manual_retry": bool(stk17b_manual_retry_summary.get("ready_for_manual_retry", False)),
            "stk17b_retry_target_id": stk17b_retry_target_id,
            "stk17b_retry_start_shard_id": stk17b_retry_start_shard_id,
            "stk17b_retry_total_seen_shards": stk17b_retry_total_seen,
            "stk17b_retry_resolved_shards": stk17b_retry_resolved_rows,
            "stk17b_retry_success_shards": len(stk17b_retry_success_rows),
            "stk17b_retry_hold_shards": len(stk17b_retry_hold_rows),
            "stk17b_retry_running_shards": len(stk17b_retry_running_rows),
            "stk17b_retry_success_pct": stk17b_retry_success_pct,
            "stk17b_retry_hold_pct": stk17b_retry_hold_pct,
            "stk17b_retry_last_outcome": stk17b_retry_last_outcome,
            "stk17b_retry_last_outcome_shard_id": stk17b_retry_last_outcome_shard_id,
            "next_required_step": next_required_step,
        },
        "structured": {
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "progress_artifact": "runs/wetlab_broad_screen_progress_current.md",
            "target_rerank_artifact": "runs/wetlab_broad_screen_target_rerank_current.md",
            "bulk_source_artifact": "runs/wetlab_broad_screen_bulk_results_source_current.md",
            "monitor_command": "python3 tools/wetlab/monitor_wetlab_broad_screen.py --refresh --loop",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a precision monitor for the wet-lab broad-screen campaign.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--progress-json", default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--rerank-json", default=DEFAULT_RERANK_JSON)
    parser.add_argument("--source-json", default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--compound-universe-json", default=DEFAULT_UNIVERSE_JSON)
    parser.add_argument("--stk17b-manual-retry-lane-json", default=DEFAULT_STK17B_MANUAL_RETRY_LANE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Precision Monitor",
        build_payload(
            execution_queue=load_json(args.execution_queue_json),
            progress_payload=maybe_load_json(args.progress_json),
            rerank_payload=maybe_load_json(args.rerank_json),
            source_payload=maybe_load_json(args.source_json),
            compound_universe=maybe_load_json(args.compound_universe_json),
            stk17b_manual_retry_lane=maybe_load_json(args.stk17b_manual_retry_lane_json),
        ),
    )
