#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import os
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from tools.monitor_ui import (
    BOLD,
    CYAN,
    DIM,
    GREEN,
    MAGENTA,
    RED,
    YELLOW,
    progress_bar as _ui_progress_bar,
    shorten as _ui_shorten,
    style as _ui_style,
)

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PRIMARY_MONITOR_JSON = ROOT / "runs/wetlab_broad_screen_precision_monitor_current.json"
DEFAULT_PRIMARY_QUEUE_JSON = ROOT / "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_PRIMARY_PROGRESS_JSON = ROOT / "runs/wetlab_broad_screen_progress_current.json"
DEFAULT_ANTITARGET_QUEUE_JSON = ROOT / "runs/wetlab_broad_screen_antitarget_execution_queue_current.json"
DEFAULT_ANTITARGET_PROGRESS_JSON = ROOT / "runs/wetlab_broad_screen_antitarget_progress_current.json"
DEFAULT_PRIMARY_WATCH_LOOP_PID = ROOT / "runs/wetlab_broad_screen_primary_watch_loop.pid"
DEFAULT_ANTITARGET_WATCHER_LOOP_PID = ROOT / "runs/wetlab_broad_screen_antitarget_watcher_loop.pid"
DEFAULT_ENGINEERING_JSON = ROOT / "runs/wetlab_engineering_progress_current.json"
DEFAULT_STACK_JSON = ROOT / "runs/wetlab_partnering_stack_current.json"
DEFAULT_HANDOFF_JSON = ROOT / "runs/wetlab_master_handoff_dashboard_current.json"
DEFAULT_CURRENT_RESULTS_INDEX_JSON = ROOT / "runs/wetlab_current_results_index_current.json"
DEFAULT_MONITOR_SEMANTICS_JSON = ROOT / "runs/wetlab_monitor_semantics_current.json"
DEFAULT_RERANK_JSON = ROOT / "runs/wetlab_broad_screen_target_rerank_current.json"
DEFAULT_STABILITY_JSON = ROOT / "runs/wetlab_broad_screen_stability_score_current.json"
DEFAULT_PRELAUNCH_JSON = ROOT / "runs/sarscov2_mpro_broad_screen_prelaunch_current.json"
DEFAULT_CATHEPSIN_EXPLORATORY_LANE_JSON = ROOT / "runs/wetlab_cathepsin_k_exploratory_retry_lane_current.json"
DEFAULT_MPRO_EXPLORATORY_LANE_JSON = ROOT / "runs/wetlab_sarscov2_mpro_exploratory_retry_lane_current.json"
DEFAULT_TCRUZI_PDE_EXPLORATORY_LANE_JSON = ROOT / "runs/wetlab_tcruzi_pde_exploratory_retry_lane_current.json"
DEFAULT_DENGUE_STAGE6_TUNING_SURFACE_JSON = ROOT / "runs/wetlab_dengue_ns2b_ns3_stage6_tuning_surface_current.json"
DEFAULT_DENGUE_EXPLORATORY_LANE_JSON = ROOT / "runs/wetlab_dengue_ns2b_ns3_exploratory_retry_lane_current.json"
DEFAULT_DENGUE_FOLLOWUP_LANE_JSON = ROOT / "runs/wetlab_dengue_ns2b_ns3_exploratory_followup_lane_current.json"
DEFAULT_DPRE1_RESULT_REVIEW_JSON = ROOT / "runs/dpre1_result_review_current.json"
DEFAULT_DPRE1_RUN_RECORD_JSON = ROOT / "runs/dpre1_run_record_current.json"
DEFAULT_DPRE1_RESULT_SUMMARY_JSON = ROOT / "runs/dpre1_result_summary_current.json"
DEFAULT_MPRO_STAGE1_MAPPING_FIX_LANE_JSON = ROOT / "runs/sarscov2_mpro_stage1_mapping_fix_lane_current.json"
DEFAULT_TCRUZI_PDE_STAGE1_MAPPING_FIX_LANE_JSON = ROOT / "runs/tcruzi_pde_stage1_mapping_fix_lane_current.json"
DEFAULT_MAPPING_FIX_RETRY_RUNNER_JSON = ROOT / "runs/wetlab_mapping_fix_retry_runner_current.json"
DEFAULT_MPRO_MAPPING_FIX_RETRY_RUNNER_JSON = ROOT / "runs/wetlab_mapping_fix_retry_runner_mpro_current.json"
DEFAULT_TCRUZI_PDE_MAPPING_FIX_RETRY_RUNNER_JSON = ROOT / "runs/wetlab_mapping_fix_retry_runner_tcruzi_current.json"
DEFAULT_PRIMARY_EVENT_LOG = ROOT / "runs/wetlab_broad_screen_runtime_event_log.jsonl"
DEFAULT_ANTITARGET_EVENT_LOG = ROOT / "runs/wetlab_broad_screen_antitarget_runtime_event_log.jsonl"

DEFAULT_LIGHT_REFRESH_SCRIPTS = [
    "tools/build_wetlab_broad_screen_precision_monitor.py",
]

DEFAULT_FULL_REFRESH_SCRIPTS = [
    "tools/build_wetlab_broad_screen_precision_monitor.py",
    "tools/build_wetlab_primary_stage6_failure_surface.py",
    "tools/build_wetlab_broad_screen_antitarget_execution_queue.py",
    "tools/build_wetlab_broad_screen_antitarget_runtime_runbook.py",
    "tools/build_wetlab_broad_screen_next_target_extension.py",
    "tools/build_wetlab_broad_screen_throughput_bridge.py",
    "tools/build_wetlab_mapping_fix_retry_policy_templates.py",
    "tools/build_wetlab_monitor_semantics.py",
    "tools/build_wetlab_current_results_index.py",
    "tools/build_wetlab_retry_handoff_summary.py",
    "tools/build_wetlab_stk17b_exploratory_followup_lane.py",
    "tools/build_wetlab_engineering_progress.py",
    "tools/build_wetlab_final_campaign_summary.py",
    "tools/build_wetlab_master_handoff_dashboard.py",
    "tools/build_wetlab_partnering_stack.py",
]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            rows.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    return rows


def _pid_snapshot(path: Path) -> dict[str, Any]:
    snapshot = {
        "pid_path": str(path),
        "pid": 0,
        "pid_alive": False,
        "pid_state": "missing",
    }
    if not path.exists():
        return snapshot
    try:
        text = path.read_text(encoding="utf-8").strip()
        pid = int(text or 0)
    except Exception:
        snapshot["pid_state"] = "invalid"
        return snapshot
    snapshot["pid"] = pid
    if pid <= 0:
        snapshot["pid_state"] = "invalid"
        return snapshot
    try:
        os.kill(pid, 0)
    except OSError:
        snapshot["pid_state"] = "stale"
        return snapshot
    snapshot["pid_alive"] = True
    snapshot["pid_state"] = "alive"
    return snapshot


def _parse_ts(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text)
    except Exception:
        return None


def _minutes_between(start: dt.datetime | None, end: dt.datetime | None) -> float:
    if start is None or end is None:
        return 0.0
    return max((end - start).total_seconds() / 60.0, 0.0)


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):.1f}%"
    except Exception:
        return "0.0%"


def _fmt_float(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return f"{0.0:.{digits}f}"


def _fmt_duration_minutes(value: float) -> str:
    minutes = max(int(round(value)), 0)
    hours, rem = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{rem}m")
    return " ".join(parts)


def _fmt_rate(value: float) -> str:
    if value <= 0:
        return "n/a"
    return f"{value:.2f}/h"


def _style(enabled: bool, text: str, *codes: str) -> str:
    return _ui_style(enabled, text, *codes)


def _shorten(text: Any, limit: int = 80) -> str:
    return _ui_shorten(str(text or ""), limit=limit)


def _progress_bar(done: int, total: int, *, width: int = 20, color: bool = False, bar_color: str = CYAN) -> str:
    return _ui_progress_bar(done, total, width=width, color=color, bar_color=bar_color)


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def _first_value_from_sources(sources: list[dict[str, Any]], *keys: str) -> Any:
    for source in sources:
        for key in keys:
            if key not in source:
                continue
            value = source.get(key)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
    return None


def _first_text_from_sources(sources: list[dict[str, Any]], *keys: str, default: str = "") -> str:
    value = _first_value_from_sources(sources, *keys)
    if value in {None, ""}:
        return default
    return str(value).strip()


def _first_float_from_sources(sources: list[dict[str, Any]], *keys: str) -> float:
    value = _first_value_from_sources(sources, *keys)
    if value is None:
        return 0.0
    try:
        return float(value)
    except Exception:
        return 0.0


def _first_int_from_sources(sources: list[dict[str, Any]], *keys: str) -> int:
    value = _first_value_from_sources(sources, *keys)
    if value is None:
        return 0
    try:
        return int(value)
    except Exception:
        return 0


def _completed_rows(rows: list[dict[str, Any]], status_key: str, completed_at_key: str = "completed_at") -> list[dict[str, Any]]:
    out = []
    for row in rows:
        status = str(row.get(status_key, "")).strip()
        if "result_ready" in status or "explicit_hold" in status:
            out.append(dict(row))
    return out


def _status_kind(status: Any) -> str:
    text = str(status or "").strip()
    if "result_ready" in text:
        return "success"
    if "explicit_hold" in text:
        return "hold"
    return ""


def _completed_runtime_minutes(row: dict[str, Any]) -> float:
    started_at = _parse_ts(row.get("started_at"))
    completed_at = _parse_ts(row.get("completed_at") or row.get("updated_at"))
    if started_at is None or completed_at is None:
        return 0.0
    return _minutes_between(started_at, completed_at)


def _completed_runtime_series(completed_rows: list[dict[str, Any]], *, sample_size: int | None = None) -> list[float]:
    if sample_size is not None and sample_size > 0:
        completed_rows = sorted(
            completed_rows,
            key=lambda row: _parse_ts(row.get("completed_at") or row.get("updated_at")) or dt.datetime.min,
        )[-sample_size:]
    return [minutes for minutes in (_completed_runtime_minutes(row) for row in completed_rows) if minutes > 0]


def _rate_per_hour(completed_rows: list[dict[str, Any]], *, sample_size: int | None = None) -> float:
    durations = _completed_runtime_series(completed_rows, sample_size=sample_size)
    if not durations:
        return 0.0
    total_hours = sum(durations) / 60.0
    if total_hours <= 0:
        return 0.0
    return len(durations) / total_hours


def _median_runtime_minutes(completed_rows: list[dict[str, Any]], *, sample_size: int | None = None) -> float:
    durations = _completed_runtime_series(completed_rows, sample_size=sample_size)
    if not durations:
        return 0.0
    return float(statistics.median(durations))


def _runtime_baseline_minutes(values: list[float], *, windows: tuple[int, ...] = (3, 5, 7), minimum_floor: float = 5.0) -> float:
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
    return max(baseline, float(minimum_floor))


def _active_row(rows: list[dict[str, Any]], status_key: str) -> dict[str, Any]:
    for row in rows:
        if "running" in str(row.get(status_key, "")).strip():
            return dict(row)
    return {}


def _find_primary_queue_row(rows: list[dict[str, Any]], target_id: str, shard_id: str) -> dict[str, Any]:
    for row in rows:
        if (
            str(row.get("target_id", "")).strip() == target_id
            and str(row.get("shard_id", "")).strip() == shard_id
        ):
            return dict(row)
    return {}


def _find_primary_progress_row(rows: list[dict[str, Any]], target_id: str, shard_id: str) -> dict[str, Any]:
    for row in rows:
        if (
            str(row.get("target_id", "")).strip() == target_id
            and str(row.get("shard_id", "")).strip() == shard_id
        ):
            return dict(row)
    return {}


def _mapping_fix_lane_snapshot(
    lane_summary: dict[str, Any],
    primary_queue_rows: list[dict[str, Any]],
    primary_progress_rows: list[dict[str, Any]],
    *runner_summaries: dict[str, Any],
) -> dict[str, Any]:
    target_id = str(lane_summary.get("target_id", "")).strip()
    shard_id = str(lane_summary.get("shard_id", "")).strip()
    queue_row = _find_primary_queue_row(primary_queue_rows, target_id, shard_id)
    progress_row = _find_primary_progress_row(primary_progress_rows, target_id, shard_id)
    queue_status = str(queue_row.get("queue_status", "")).strip()
    progress_status = str(progress_row.get("queue_status", "")).strip()
    status = queue_status or progress_status or ("ready_for_mapping_fix_retry" if bool(lane_summary.get("ready_for_mapping_fix_retry", False)) else "not_ready")
    hb = int(progress_row.get("heartbeat_count", 0) or 0)
    ev = int(progress_row.get("event_count", 0) or 0)
    runner_match = any(
        str(summary.get("target_id", "")).strip() == target_id
        and str(summary.get("shard_id", "")).strip() == shard_id
        and bool(summary.get("mapping_fix_launch_completed", False))
        for summary in runner_summaries
    )
    return {
        "target_id": target_id,
        "shard_id": shard_id,
        "status": status,
        "selected_command_kind": str(lane_summary.get("selected_command_kind", "")).strip(),
        "ready_for_retry": bool(lane_summary.get("ready_for_mapping_fix_retry", False)),
        "heartbeat_count": hb,
        "event_count": ev,
        "runner_match": runner_match,
    }


def _compact_mapping_fix_status(status: Any) -> str:
    text = str(status or "").strip()
    if text == "ready_for_mapping_fix_retry":
        return "ready"
    return text or "-"


def _short_mapping_fix_targets(text: Any) -> str:
    value = str(text or "").strip()
    if not value:
        return "-"
    replacements = {
        "SARS-CoV-2 Mpro": "Mpro",
        "T. cruzi PDE": "PDE",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def _mapping_fix_lane_progress_text(lane: dict[str, Any]) -> str:
    shard_id = str(lane.get("shard_id", "")).strip()
    status = _compact_mapping_fix_status(lane.get("status"))
    if not shard_id:
        return ""
    part = f"{shard_id} {status}"
    hb = int(lane.get("heartbeat_count", 0) or 0)
    ev = int(lane.get("event_count", 0) or 0)
    if "running" in status:
        part += f" | hb {hb} ev {ev}"
    elif bool(lane.get("runner_match", False)):
        part += " | runner-launched"
    return part


def _dengue_stage6_line(snapshot: dict[str, Any]) -> str:
    current_results_index = _summary(snapshot.get("current_results_index", {}))
    monitor_semantics = _summary(snapshot.get("monitor_semantics", {}))
    handoff = _summary(snapshot.get("handoff", {}))
    branch_lanes = dict(snapshot.get("branch_lane_summaries", {}) or {})
    dengue_tuning = _summary(snapshot.get("dengue_stage6_tuning_surface", {}))
    if not dengue_tuning:
        dengue_tuning = _summary(branch_lanes.get("dengue_stage6_tuning_surface", {}))
    dengue_exploratory = _summary(snapshot.get("dengue_exploratory_lane", {}))
    if not dengue_exploratory:
        dengue_exploratory = _summary(branch_lanes.get("dengue_exploratory", {}))
    dengue_followup = _summary(snapshot.get("dengue_followup_lane", {}))
    if not dengue_followup:
        dengue_followup = _summary(branch_lanes.get("dengue_followup", {}))

    prefix_sources = [current_results_index, monitor_semantics, handoff]
    payload_sources = [dengue_followup, dengue_exploratory, dengue_tuning]
    sources = prefix_sources + payload_sources

    target = _first_text_from_sources(
        prefix_sources,
        "dengue_stage6_retry_target_id",
        "dengue_stage6_target_id",
        "dengue_followup_target_id",
        "dengue_target_id",
    )
    if not target:
        target = _first_text_from_sources(payload_sources, "target_id", "focus_target_id")

    lane_label = _first_text_from_sources(
        prefix_sources,
        "dengue_stage6_retry_lane_label",
        "dengue_stage6_lane_label",
        "dengue_followup_lane_label",
    )
    if not lane_label:
        lane_label = _first_text_from_sources(payload_sources, "lane_label", "followup_lane_label", "stage6_lane_label")

    command_kind = _first_text_from_sources(
        prefix_sources,
        "dengue_stage6_retry_selected_command_kind",
        "dengue_stage6_selected_command_kind",
        "dengue_followup_selected_command_kind",
    )
    if not command_kind:
        command_kind = _first_text_from_sources(
            payload_sources,
            "selected_command_kind",
            "command_kind",
            "immediately_runnable_command_kind",
        )

    threshold = _first_float_from_sources(
        prefix_sources,
        "dengue_stage6_retry_selected_threshold_A",
        "dengue_stage6_selected_threshold_A",
        "dengue_followup_selected_threshold_A",
        "dengue_stage6_retry_recommended_threshold_A",
        "dengue_stage6_recommended_threshold_A",
    )
    if threshold <= 0:
        threshold = _first_float_from_sources(
            payload_sources,
            "selected_threshold_A",
            "recommended_observed_threshold_A",
            "immediately_runnable_threshold_A",
        )

    status = _first_text_from_sources(
        prefix_sources,
        "dengue_stage6_retry_status",
        "dengue_stage6_status",
        "dengue_followup_status",
    )
    if not status:
        status = _first_text_from_sources(payload_sources, "status", "queue_status")
    if not status and any(bool(source.get("ready_for_manual_retry", False)) for source in payload_sources):
        status = "ready"
    if not status and any(bool(source.get("ready", False)) for source in prefix_sources):
        status = "ready"
    if not status and any(bool(source.get("validated", False)) for source in prefix_sources):
        status = "validated"
    if not status and any([target, lane_label, command_kind, threshold > 0]):
        status = "ready"

    heartbeat_count = _first_int_from_sources(
        prefix_sources,
        "dengue_stage6_retry_heartbeat_count",
        "dengue_stage6_heartbeat_count",
        "dengue_followup_heartbeat_count",
        "heartbeat_count",
    )
    event_count = _first_int_from_sources(
        prefix_sources,
        "dengue_stage6_retry_event_count",
        "dengue_stage6_event_count",
        "dengue_followup_event_count",
        "event_count",
    )

    if not any([target, lane_label, command_kind, threshold > 0, status, heartbeat_count, event_count]):
        return ""

    parts: list[str] = []
    if status:
        parts.append(status)
    if target:
        parts.append(target)
    if lane_label:
        parts.append(lane_label)
    if command_kind:
        parts.append(f"cmd {command_kind}")
    if threshold > 0:
        parts.append(f"{threshold:.1f}A")
    if "running" in status:
        parts.append(f"hb {heartbeat_count} ev {event_count}")
    return " | ".join(parts)


def _dpre1_guarded_review_line(snapshot: dict[str, Any], *, compact: bool = False, success_only: bool = False) -> str:
    current_results_index = _summary(snapshot.get("current_results_index", {}))
    monitor_semantics = _summary(snapshot.get("monitor_semantics", {}))
    handoff = _summary(snapshot.get("handoff", {}))
    dpre1_result_review = _summary(snapshot.get("dpre1_result_review", {}))
    dpre1_run_record = _summary(snapshot.get("dpre1_run_record", {}))
    dpre1_result_summary = _summary(snapshot.get("dpre1_result_summary", {}))

    prefix_sources = [current_results_index, monitor_semantics, handoff]
    payload_sources = [dpre1_result_review, dpre1_run_record, dpre1_result_summary]

    target = _first_text_from_sources(
        prefix_sources,
        "dpre1_wave2_target_id",
        "dpre1_result_review_target_id",
        "dpre1_target_id",
    )
    if not target:
        target = _first_text_from_sources(payload_sources, "target_id", default="DprE1")

    run_order = _first_text_from_sources(
        prefix_sources,
        "dpre1_wave2_serialized_run_order",
        "dpre1_result_review_serialized_run_order",
    )
    if not run_order:
        run_order = _first_text_from_sources(payload_sources, "serialized_run_order")
    run_order = str(run_order or "").strip()
    if run_order:
        run_order = run_order.replace("_in_wave2", "").replace("wave2", "").strip("_ ")

    status_raw = _first_text_from_sources(
        prefix_sources,
        "dpre1_wave2_execution_state",
        "dpre1_run_record_execution_state",
        "dpre1_wave2_queue_status_now",
    )
    if not status_raw:
        status_raw = _first_text_from_sources(
            payload_sources,
            "execution_state",
            "queue_status_now",
            "status",
        )
    status_text = str(status_raw or "").strip()
    if "hold" in status_text:
        status = "guarded_review_hold"
    elif "running" in status_text:
        status = "guarded_review_running"
    else:
        status = "guarded_review"

    successor = _first_text_from_sources(
        prefix_sources,
        "dpre1_wave2_successor_target",
    )
    if not successor:
        successor = _first_text_from_sources(payload_sources, "successor_target", default="T. cruzi KRS1")
    successor = str(successor or "").strip()

    if not any([target, run_order, status, successor]):
        return ""

    if compact or success_only:
        short_status = "guarded gate5.1"
        if "hold" in status:
            short_status = f"{short_status} hold"
        elif "running" in status:
            short_status = f"{short_status} running"
        parts = [short_status]
        if run_order:
            parts.append(run_order)
        if successor:
            parts.append("KRS1" if successor == "T. cruzi KRS1" else successor)
        return " | ".join(parts)

    parts = [status or "guarded_review", target or "DprE1"]
    if run_order:
        parts.append(run_order)
    parts.append("gate5.1 exploratory branch")
    if successor:
        parts.append(successor)
    return " | ".join(parts)


def _target_queue_stats(rows: list[dict[str, Any]], target_id: str) -> dict[str, Any]:
    target_rows = [dict(row) for row in rows if str(row.get("target_id", "")).strip() == target_id]
    if not target_rows:
        return {
            "total": 0,
            "resolved": 0,
            "running": 0,
            "remaining": 0,
            "completion_pct": 0.0,
        }
    total = len(target_rows)
    resolved = sum(1 for row in target_rows if _is_resolved_status(row.get("queue_status", "")))
    running = sum(1 for row in target_rows if "running" in str(row.get("queue_status", "")).strip())
    remaining = max(total - resolved - running, 0)
    completion_pct = (100.0 * resolved / total) if total else 0.0
    return {
        "total": total,
        "resolved": resolved,
        "running": running,
        "remaining": remaining,
        "completion_pct": completion_pct,
    }


def _is_resolved_status(status: Any) -> bool:
    text = str(status or "").strip()
    return "result_ready" in text or "explicit_hold" in text


def _age_text(ts: dt.datetime | None, now: dt.datetime) -> str:
    if ts is None:
        return "-"
    return _fmt_duration_minutes(_minutes_between(ts, now))


def _line(label: str, value: str, width: int = 18) -> str:
    return f"{label:<{width}} {value}"


def _status_color(status: str) -> str:
    text = str(status or "").strip().lower()
    if "stale" in text:
        return RED
    if "running" in text:
        return YELLOW
    if "ready" in text or "complete" in text or "resolved" in text:
        return GREEN
    if "hold" in text or "blocked" in text:
        return MAGENTA
    return DIM


def _freshness_color(age_minutes: float) -> str:
    if age_minutes <= 10:
        return GREEN
    if age_minutes <= 30:
        return YELLOW
    return RED


def _render_recent_events(title: str, events: list[dict[str, Any]], formatter) -> list[str]:
    lines = [title]
    if not events:
        lines.append("  (no recent events)")
        return lines
    for row in events[-4:]:
        lines.append(f"  {formatter(row)}")
    return lines


def _format_primary_event(row: dict[str, Any]) -> str:
    stamp = str(row.get("event_timestamp", "")).replace("T", " ")
    target = str(row.get("target_id", "")).strip()
    shard = str(row.get("shard_id", "")).strip()
    event = str(row.get("event", "")).strip()
    return f"{stamp} | {event:<8} | {target} {shard}".strip()


def _format_antitarget_event(row: dict[str, Any]) -> str:
    stamp = str(row.get("event_timestamp", "")).replace("T", " ")
    primary = str(row.get("primary_target_id", "")).strip()
    anti = str(row.get("anti_target_id", "")).strip()
    shard = str(row.get("primary_shard_id", "")).strip()
    event = str(row.get("event", "")).strip()
    return f"{stamp} | {event:<8} | {primary} -> {anti} {shard}".strip()


def _top_target_rows(
    precision_rows: list[dict[str, Any]],
    stability_rows_by_target: dict[str, dict[str, Any]],
    limit: int,
    target_filter: str = "",
    *,
    success_only: bool = False,
) -> list[dict[str, Any]]:
    normalized_filter = str(target_filter or "").strip().lower()

    def sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        target_id = str(row.get("target_id", "")).strip()
        stability = stability_rows_by_target.get(target_id, {})
        return (
            -int(bool(str(row.get("current_running_shard", "")).strip())),
            -float(row.get("completion_pct", 0.0) or 0.0),
            -float(stability.get("stability_score", 0.0) or 0.0),
            target_id.lower(),
        )

    filtered = [
        row
        for row in precision_rows
        if not normalized_filter or normalized_filter in str(row.get("target_id", "")).strip().lower()
    ]
    if success_only:
        filtered = [
            row
            for row in filtered
            if int(row.get("completed_shards", 0) or 0) > 0
            or str(row.get("current_running_shard", "")).strip()
        ]
    return sorted(filtered, key=sort_key)[:limit]


def _matching_primary_events(events: list[dict[str, Any]], target_filter: str) -> list[dict[str, Any]]:
    normalized_filter = str(target_filter or "").strip().lower()
    if not normalized_filter:
        return list(events)
    return [row for row in events if normalized_filter in str(row.get("target_id", "")).strip().lower()]


def _matching_antitarget_events(events: list[dict[str, Any]], target_filter: str) -> list[dict[str, Any]]:
    normalized_filter = str(target_filter or "").strip().lower()
    if not normalized_filter:
        return list(events)
    return [
        row
        for row in events
        if normalized_filter in str(row.get("primary_target_id", "")).strip().lower()
        or normalized_filter in str(row.get("anti_target_id", "")).strip().lower()
    ]


def _last_event_for_primary(events: list[dict[str, Any]], target_id: str, shard_id: str) -> dict[str, Any]:
    matches = [
        row
        for row in events
        if str(row.get("target_id", "")).strip() == target_id and str(row.get("shard_id", "")).strip() == shard_id
    ]
    if not matches:
        return {}
    return max(matches, key=lambda row: _parse_ts(row.get("event_timestamp")) or dt.datetime.min)


def _last_event_for_antitarget(events: list[dict[str, Any]], primary_target_id: str, anti_target_id: str, shard_id: str) -> dict[str, Any]:
    matches = [
        row
        for row in events
        if str(row.get("primary_target_id", "")).strip() == primary_target_id
        and str(row.get("anti_target_id", "")).strip() == anti_target_id
        and str(row.get("primary_shard_id", "")).strip() == shard_id
    ]
    if not matches:
        return {}
    return max(matches, key=lambda row: _parse_ts(row.get("event_timestamp")) or dt.datetime.min)


def _find_antitarget_progress_row(
    rows: list[dict[str, Any]],
    primary_target_id: str,
    anti_target_id: str,
    shard_id: str,
) -> dict[str, Any]:
    for row in rows:
        if (
            str(row.get("primary_target_id", "")).strip() == primary_target_id
            and str(row.get("anti_target_id", "")).strip() == anti_target_id
            and str(row.get("primary_shard_id", "")).strip() == shard_id
        ):
            return dict(row)
    return {}


def _recent_signal_gap_minutes(events: list[dict[str, Any]]) -> float:
    stamps = sorted(_parse_ts(row.get("event_timestamp")) for row in events)
    valid = [stamp for stamp in stamps if stamp is not None]
    if len(valid) < 2:
        return 0.0
    return _minutes_between(valid[-2], valid[-1])


def _build_snapshot(target_filter: str = "", *, success_only: bool = False) -> dict[str, Any]:
    primary_monitor = _load_json(DEFAULT_PRIMARY_MONITOR_JSON)
    primary_queue = _load_json(DEFAULT_PRIMARY_QUEUE_JSON)
    primary_progress = _load_json(DEFAULT_PRIMARY_PROGRESS_JSON)
    antitarget_queue = _load_json(DEFAULT_ANTITARGET_QUEUE_JSON)
    antitarget_progress = _load_json(DEFAULT_ANTITARGET_PROGRESS_JSON)
    engineering = _load_json(DEFAULT_ENGINEERING_JSON)
    stack = _load_json(DEFAULT_STACK_JSON)
    handoff = _load_json(DEFAULT_HANDOFF_JSON)
    current_results_index = _load_json(DEFAULT_CURRENT_RESULTS_INDEX_JSON)
    monitor_semantics = _load_json(DEFAULT_MONITOR_SEMANTICS_JSON)
    rerank = _load_json(DEFAULT_RERANK_JSON)
    stability = _load_json(DEFAULT_STABILITY_JSON)
    prelaunch = _load_json(DEFAULT_PRELAUNCH_JSON)
    cathepsin_exploratory_lane = _load_json(DEFAULT_CATHEPSIN_EXPLORATORY_LANE_JSON)
    mpro_exploratory_lane = _load_json(DEFAULT_MPRO_EXPLORATORY_LANE_JSON)
    tcruzi_pde_exploratory_lane = _load_json(DEFAULT_TCRUZI_PDE_EXPLORATORY_LANE_JSON)
    dengue_stage6_tuning_surface = _load_json(DEFAULT_DENGUE_STAGE6_TUNING_SURFACE_JSON)
    dengue_exploratory_lane = _load_json(DEFAULT_DENGUE_EXPLORATORY_LANE_JSON)
    dengue_followup_lane = _load_json(DEFAULT_DENGUE_FOLLOWUP_LANE_JSON)
    dpre1_result_review = _load_json(DEFAULT_DPRE1_RESULT_REVIEW_JSON)
    dpre1_run_record = _load_json(DEFAULT_DPRE1_RUN_RECORD_JSON)
    dpre1_result_summary = _load_json(DEFAULT_DPRE1_RESULT_SUMMARY_JSON)
    mpro_mapping_fix_lane = _load_json(DEFAULT_MPRO_STAGE1_MAPPING_FIX_LANE_JSON)
    tcruzi_mapping_fix_lane = _load_json(DEFAULT_TCRUZI_PDE_STAGE1_MAPPING_FIX_LANE_JSON)
    mapping_fix_retry_runner = _load_json(DEFAULT_MAPPING_FIX_RETRY_RUNNER_JSON)
    mpro_mapping_fix_retry_runner = _load_json(DEFAULT_MPRO_MAPPING_FIX_RETRY_RUNNER_JSON)
    tcruzi_mapping_fix_retry_runner = _load_json(DEFAULT_TCRUZI_PDE_MAPPING_FIX_RETRY_RUNNER_JSON)
    primary_events = _load_jsonl(DEFAULT_PRIMARY_EVENT_LOG)
    antitarget_events = _load_jsonl(DEFAULT_ANTITARGET_EVENT_LOG)
    primary_watch_loop = _pid_snapshot(DEFAULT_PRIMARY_WATCH_LOOP_PID)
    antitarget_watch_loop = _pid_snapshot(DEFAULT_ANTITARGET_WATCHER_LOOP_PID)

    now = dt.datetime.now()
    pmon = _summary(primary_monitor)
    peqq = _summary(primary_queue)
    pp = _summary(primary_progress)
    aq = _summary(antitarget_queue)
    ap = _summary(antitarget_progress)
    eng = _summary(engineering)
    stk = _summary(stack)
    hnd = _summary(handoff)
    idx = _summary(current_results_index)
    msem = _summary(monitor_semantics)
    rr = _summary(rerank)
    st = _summary(stability)
    pre = _summary(prelaunch)
    cathepsin_exploratory_lane_summary = _summary(cathepsin_exploratory_lane)
    mpro_exploratory_lane_summary = _summary(mpro_exploratory_lane)
    tcruzi_pde_exploratory_lane_summary = _summary(tcruzi_pde_exploratory_lane)
    dengue_stage6_tuning_surface_summary = _summary(dengue_stage6_tuning_surface)
    dengue_exploratory_lane_summary = _summary(dengue_exploratory_lane)
    dengue_followup_lane_summary = _summary(dengue_followup_lane)
    dpre1_result_review_summary = _summary(dpre1_result_review)
    dpre1_run_record_summary = _summary(dpre1_run_record)
    dpre1_result_summary_summary = _summary(dpre1_result_summary)
    mpro_mapping_fix_lane_summary = _summary(mpro_mapping_fix_lane)
    tcruzi_mapping_fix_lane_summary = _summary(tcruzi_mapping_fix_lane)
    mapping_fix_retry_runner_summary = _summary(mapping_fix_retry_runner)
    mpro_mapping_fix_retry_runner_summary = _summary(mpro_mapping_fix_retry_runner)
    tcruzi_mapping_fix_retry_runner_summary = _summary(tcruzi_mapping_fix_retry_runner)

    primary_progress_rows = list(primary_progress.get("rows", []) or [])
    antitarget_progress_rows = list(antitarget_progress.get("rows", []) or [])
    primary_completed = _completed_rows(primary_progress_rows, "queue_status")
    primary_success_completed = [row for row in primary_completed if _status_kind(row.get("queue_status", "")) == "success"]
    primary_hold_completed = [row for row in primary_completed if _status_kind(row.get("queue_status", "")) == "hold"]
    antitarget_completed = _completed_rows(antitarget_progress_rows, "queue_status")
    antitarget_success_completed = [row for row in antitarget_completed if _status_kind(row.get("queue_status", "")) == "success"]
    antitarget_hold_completed = [row for row in antitarget_completed if _status_kind(row.get("queue_status", "")) == "hold"]
    primary_queue_rows = list(primary_queue.get("rows", []) or [])
    mpro_mapping_fix_snapshot = _mapping_fix_lane_snapshot(
        mpro_mapping_fix_lane_summary,
        primary_queue_rows,
        primary_progress_rows,
        mpro_mapping_fix_retry_runner_summary,
        mapping_fix_retry_runner_summary,
    )
    tcruzi_mapping_fix_snapshot = _mapping_fix_lane_snapshot(
        tcruzi_mapping_fix_lane_summary,
        primary_queue_rows,
        primary_progress_rows,
        tcruzi_mapping_fix_retry_runner_summary,
        mapping_fix_retry_runner_summary,
    )
    active_primary = _active_row(primary_progress_rows, "queue_status")
    active_antitarget = _active_row(antitarget_progress_rows, "queue_status")

    primary_overall_rate = _rate_per_hour(primary_completed)
    primary_recent_rate = _rate_per_hour(primary_completed, sample_size=3)
    primary_success_overall_rate = _rate_per_hour(primary_success_completed)
    primary_success_recent_rate = _rate_per_hour(primary_success_completed, sample_size=3)
    primary_hold_overall_rate = _rate_per_hour(primary_hold_completed)
    primary_hold_recent_rate = _rate_per_hour(primary_hold_completed, sample_size=3)
    antitarget_overall_rate = _rate_per_hour(antitarget_completed)
    antitarget_recent_rate = _rate_per_hour(antitarget_completed, sample_size=3)
    antitarget_success_overall_rate = _rate_per_hour(antitarget_success_completed)
    antitarget_success_recent_rate = _rate_per_hour(antitarget_success_completed, sample_size=3)
    antitarget_hold_overall_rate = _rate_per_hour(antitarget_hold_completed)
    antitarget_hold_recent_rate = _rate_per_hour(antitarget_hold_completed, sample_size=3)
    primary_runtime_median_minutes = _median_runtime_minutes(primary_completed)
    primary_recent_runtime_median_minutes = _median_runtime_minutes(primary_completed, sample_size=3)
    primary_success_runtime_median_minutes = _median_runtime_minutes(primary_success_completed)
    primary_success_recent_runtime_median_minutes = _median_runtime_minutes(primary_success_completed, sample_size=3)
    primary_hold_runtime_median_minutes = _median_runtime_minutes(primary_hold_completed)
    primary_hold_recent_runtime_median_minutes = _median_runtime_minutes(primary_hold_completed, sample_size=3)
    primary_progress_baseline_minutes = _runtime_baseline_minutes(_completed_runtime_series(primary_success_completed))
    antitarget_runtime_median_minutes = _median_runtime_minutes(antitarget_completed)
    antitarget_recent_runtime_median_minutes = _median_runtime_minutes(antitarget_completed, sample_size=3)
    antitarget_success_runtime_median_minutes = _median_runtime_minutes(antitarget_success_completed)
    antitarget_success_recent_runtime_median_minutes = _median_runtime_minutes(antitarget_success_completed, sample_size=3)
    antitarget_hold_runtime_median_minutes = _median_runtime_minutes(antitarget_hold_completed)
    antitarget_hold_recent_runtime_median_minutes = _median_runtime_minutes(antitarget_hold_completed, sample_size=3)

    primary_running_started = _parse_ts(active_primary.get("started_at"))
    primary_running_updated = _parse_ts(active_primary.get("updated_at"))
    active_primary_target = str(active_primary.get("target_id", "")).strip()
    active_primary_shard = str(active_primary.get("shard_id", "")).strip()
    if active_primary_target and active_primary_shard:
        focus_primary_target = active_primary_target
        focus_primary_shard = active_primary_shard
        focus_primary_status = str(active_primary.get("queue_status", "")).strip() or "running"
        focus_primary_mode = "running"
    else:
        focus_primary_target = str(peqq.get("first_actionable_target_id", "")).strip() or str(pmon.get("focus_target_id", "")).strip()
        focus_primary_shard = str(peqq.get("first_actionable_shard_id", "")).strip() or str(pmon.get("focus_shard_id", "")).strip()
        focus_primary_status = str(peqq.get("first_actionable_queue_status", "")).strip() or str(pmon.get("focus_queue_status", "")).strip()
        focus_primary_mode = (
            "stale"
            if "stale_running" in focus_primary_status
            else "dispatch_ready"
            if focus_primary_target and focus_primary_shard
            else "idle"
        )
    focus_primary_queue_row = _find_primary_queue_row(primary_queue_rows, focus_primary_target, focus_primary_shard)
    focus_primary_stats = _target_queue_stats(primary_queue_rows, focus_primary_target)
    focus_primary_target_completion_pct = float(focus_primary_stats.get("completion_pct", 0.0) or 0.0)
    focus_primary_target_remaining_shards = int(focus_primary_stats.get("remaining", 0) or 0)
    if int(focus_primary_stats.get("total", 0) or 0) == 0:
        focus_primary_target_completion_pct = float(
            pmon.get("focus_target_completion_pct", pmon.get("active_target_completion_pct", 0.0)) or 0.0
        )
        focus_primary_target_remaining_shards = int(pmon.get("focus_target_remaining_shards", 0) or 0)
    focus_primary_completed_rows = [
        row for row in primary_completed if str(row.get("target_id", "")).strip() == focus_primary_target
    ]
    focus_primary_runtime_median = _median_runtime_minutes(focus_primary_completed_rows)
    focus_primary_recent_runtime_median = _median_runtime_minutes(focus_primary_completed_rows, sample_size=3)
    focus_primary_runtime_baseline = _runtime_baseline_minutes(_completed_runtime_series(focus_primary_completed_rows))
    focus_primary_elapsed_minutes = _minutes_between(primary_running_started, now) if primary_running_started else 0.0
    focus_primary_stage = str(active_primary.get("active_stage_label", "")).strip() or str(
        focus_primary_queue_row.get("active_stage_label", "")
    ).strip() or "-"
    focus_primary_heartbeat_count = int(active_primary.get("heartbeat_count", 0) or 0)
    focus_primary_event_count = int(active_primary.get("event_count", 0) or 0)
    focus_primary_estimated_pct = (
        (focus_primary_elapsed_minutes / focus_primary_runtime_baseline) * 100.0
        if focus_primary_mode == "running" and focus_primary_runtime_baseline > 0
        else 0.0
    )
    active_antitarget_primary = str(aq.get("first_actionable_primary_target_id", "")).strip()
    active_antitarget_target = str(aq.get("first_actionable_anti_target_id", "")).strip()
    active_antitarget_shard = str(aq.get("first_actionable_shard_id", "")).strip()
    if (not active_antitarget_primary) and active_antitarget:
        active_antitarget_primary = str(active_antitarget.get("primary_target_id", "")).strip()
    if (not active_antitarget_target) and active_antitarget:
        active_antitarget_target = str(active_antitarget.get("anti_target_id", "")).strip()
    if (not active_antitarget_shard) and active_antitarget:
        active_antitarget_shard = str(active_antitarget.get("primary_shard_id", "")).strip()
    antitarget_progress_row = _find_antitarget_progress_row(
        antitarget_progress_rows,
        active_antitarget_primary,
        active_antitarget_target,
        active_antitarget_shard,
    )
    antitarget_running_started = _parse_ts(
        antitarget_progress_row.get("started_at") or active_antitarget.get("started_at")
    )
    antitarget_running_updated = _parse_ts(
        antitarget_progress_row.get("updated_at") or active_antitarget.get("updated_at")
    )

    antitarget_queue_rows = list(antitarget_queue.get("rows", []) or [])
    antitarget_panel_rows = [
        row
        for row in antitarget_queue_rows
        if str(row.get("primary_target_id", "")).strip() == active_antitarget_primary
        and str(row.get("anti_target_id", "")).strip() == active_antitarget_target
    ]
    antitarget_panel_total = len(antitarget_panel_rows)
    antitarget_panel_resolved = sum(1 for row in antitarget_panel_rows if _is_resolved_status(row.get("queue_status", "")))
    antitarget_panel_running = sum(1 for row in antitarget_panel_rows if "running" in str(row.get("queue_status", "")).strip())
    antitarget_panel_remaining = max(antitarget_panel_total - antitarget_panel_resolved - antitarget_panel_running, 0)
    antitarget_panel_completion_pct = (
        (100.0 * antitarget_panel_resolved / antitarget_panel_total) if antitarget_panel_total > 0 else 0.0
    )
    antitarget_panel_progress_rows = [
        row
        for row in antitarget_progress_rows
        if str(row.get("primary_target_id", "")).strip() == active_antitarget_primary
        and str(row.get("anti_target_id", "")).strip() == active_antitarget_target
    ]
    antitarget_panel_completed_rows = [
        row
        for row in antitarget_panel_progress_rows
        if str(row.get("queue_status", "")).strip() == "result_ready"
    ]
    antitarget_panel_completed_minutes = [
        _minutes_between(_parse_ts(row.get("started_at")), _parse_ts(row.get("completed_at") or row.get("updated_at")))
        for row in antitarget_panel_completed_rows
        if _minutes_between(_parse_ts(row.get("started_at")), _parse_ts(row.get("completed_at") or row.get("updated_at"))) > 0
    ]
    antitarget_panel_avg_completed_minutes = (
        sum(antitarget_panel_completed_minutes) / len(antitarget_panel_completed_minutes)
        if antitarget_panel_completed_minutes
        else 0.0
    )
    antitarget_panel_median_completed_minutes = (
        float(statistics.median(antitarget_panel_completed_minutes)) if antitarget_panel_completed_minutes else 0.0
    )
    antitarget_panel_runtime_baseline = _runtime_baseline_minutes(
        antitarget_panel_completed_minutes,
        minimum_floor=10.0,
    )
    antitarget_stage_label = str(
        antitarget_progress_row.get("active_stage_label") or active_antitarget.get("active_stage_label", "")
    ).strip() or "-"
    antitarget_heartbeat_count = int(
        antitarget_progress_row.get("heartbeat_count", active_antitarget.get("heartbeat_count", 0)) or 0
    )
    antitarget_event_count = int(
        antitarget_progress_row.get("event_count", active_antitarget.get("event_count", 0)) or 0
    )
    antitarget_estimated_running_pct = (
        _minutes_between(antitarget_running_started, now) / antitarget_panel_runtime_baseline * 100.0
        if antitarget_panel_runtime_baseline > 0 and antitarget_running_started is not None
        else 0.0
    )

    primary_signal_events = [
        row
        for row in primary_events
        if str(row.get("target_id", "")).strip() == focus_primary_target
        and str(row.get("shard_id", "")).strip() == focus_primary_shard
    ]
    antitarget_signal_events = [
        row
        for row in antitarget_events
        if str(row.get("primary_target_id", "")).strip() == active_antitarget_primary
        and str(row.get("anti_target_id", "")).strip() == active_antitarget_target
        and str(row.get("primary_shard_id", "")).strip() == active_antitarget_shard
    ]
    last_primary_signal = _last_event_for_primary(primary_events, focus_primary_target, focus_primary_shard)
    last_antitarget_signal = _last_event_for_antitarget(
        antitarget_events,
        active_antitarget_primary,
        active_antitarget_target,
        active_antitarget_shard,
    )
    primary_signal_age_minutes = _minutes_between(_parse_ts(last_primary_signal.get("event_timestamp")), now)
    antitarget_signal_age_minutes = _minutes_between(_parse_ts(last_antitarget_signal.get("event_timestamp")), now)
    primary_signal_gap_minutes = _recent_signal_gap_minutes(primary_signal_events)
    antitarget_signal_gap_minutes = _recent_signal_gap_minutes(antitarget_signal_events)
    primary_watch_loop_liveness = (
        "attached"
        if bool(primary_watch_loop.get("pid_alive", False))
        else "stale"
        if str(primary_watch_loop.get("pid_state", "")).strip() == "stale"
        else "detached"
    )
    antitarget_watch_loop_liveness = (
        "attached"
        if bool(antitarget_watch_loop.get("pid_alive", False))
        else "stale"
        if str(antitarget_watch_loop.get("pid_state", "")).strip() == "stale"
        else "detached"
    )
    primary_watch_loop_fallback_mode = (
        "compute-attached"
        if primary_watch_loop_liveness == "attached"
        else "stale-recovery"
        if primary_watch_loop_liveness == "stale"
        else "manual-restart"
    )
    antitarget_watch_loop_fallback_mode = (
        "compute-attached"
        if antitarget_watch_loop_liveness == "attached"
        else "stale-recovery"
        if antitarget_watch_loop_liveness == "stale"
        else "manual-restart"
    )

    stability_rows_by_target = {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in (stability.get("rows", []) or [])
        if str(row.get("target_id", "")).strip()
    }

    total_actual_rows = sum(int(row.get("actual_row_count", 0) or 0) for row in (rerank.get("rows", []) or []))
    primary_pending = max(
        int(pmon.get("total_shards", 0) or 0) - int(pmon.get("resolved_shards", 0) or 0) - int(pmon.get("running_shards", 0) or 0),
        0,
    )
    antitarget_pending = max(
        int(aq.get("queue_row_count", 0) or 0) - int(aq.get("resolved_row_count", 0) or 0) - int(aq.get("running_row_count", 0) or 0),
        0,
    )
    stable_target_count = int(st.get("stable_high_confidence_target_count", 0) or 0) + int(
        st.get("stable_provisional_target_count", 0) or 0
    )
    stk17b_retry_target_id = str(pmon.get("stk17b_retry_target_id", "")).strip()
    stk17b_retry_start_shard_id = str(pmon.get("stk17b_retry_start_shard_id", "")).strip()
    stk17b_retry_total_seen_shards = int(pmon.get("stk17b_retry_total_seen_shards", 0) or 0)
    stk17b_retry_resolved_shards = int(pmon.get("stk17b_retry_resolved_shards", 0) or 0)
    stk17b_retry_success_shards = int(pmon.get("stk17b_retry_success_shards", 0) or 0)
    stk17b_retry_hold_shards = int(pmon.get("stk17b_retry_hold_shards", 0) or 0)
    stk17b_retry_running_shards = int(pmon.get("stk17b_retry_running_shards", 0) or 0)
    stk17b_retry_success_pct = float(pmon.get("stk17b_retry_success_pct", 0.0) or 0.0)
    stk17b_retry_hold_pct = float(pmon.get("stk17b_retry_hold_pct", 0.0) or 0.0)
    stk17b_retry_last_outcome = str(pmon.get("stk17b_retry_last_outcome", "")).strip()
    stk17b_retry_last_outcome_shard_id = str(pmon.get("stk17b_retry_last_outcome_shard_id", "")).strip()
    stk17b_retry_ready = bool(pmon.get("stk17b_retry_ready_for_manual_retry", False))
    primary_eta_hours = (primary_pending / primary_recent_rate) if primary_recent_rate > 0 else 0.0
    antitarget_eta_hours = (antitarget_pending / antitarget_recent_rate) if antitarget_recent_rate > 0 else 0.0

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "primary_monitor": primary_monitor,
        "primary_queue": primary_queue,
        "primary_progress": primary_progress,
        "antitarget_queue": antitarget_queue,
        "antitarget_progress": antitarget_progress,
        "engineering": engineering,
        "stack": stack,
        "handoff": handoff,
        "current_results_index": current_results_index,
        "monitor_semantics": monitor_semantics,
        "rerank": rerank,
        "stability": stability,
        "prelaunch": prelaunch,
        "primary_events": primary_events,
        "antitarget_events": antitarget_events,
        "dpre1_result_review": dpre1_result_review,
        "dpre1_run_record": dpre1_run_record,
        "dpre1_result_summary": dpre1_result_summary,
        "target_filter": target_filter,
        "computed": {
            "primary_overall_rate": primary_overall_rate,
            "primary_recent_rate": primary_recent_rate,
            "primary_success_overall_rate": primary_success_overall_rate,
            "primary_success_recent_rate": primary_success_recent_rate,
            "primary_hold_overall_rate": primary_hold_overall_rate,
            "primary_hold_recent_rate": primary_hold_recent_rate,
            "antitarget_overall_rate": antitarget_overall_rate,
            "antitarget_recent_rate": antitarget_recent_rate,
            "antitarget_success_overall_rate": antitarget_success_overall_rate,
            "antitarget_success_recent_rate": antitarget_success_recent_rate,
            "antitarget_hold_overall_rate": antitarget_hold_overall_rate,
            "antitarget_hold_recent_rate": antitarget_hold_recent_rate,
            "primary_runtime_median_minutes": primary_runtime_median_minutes,
            "primary_recent_runtime_median_minutes": primary_recent_runtime_median_minutes,
            "primary_success_runtime_median_minutes": primary_success_runtime_median_minutes,
            "primary_success_recent_runtime_median_minutes": primary_success_recent_runtime_median_minutes,
            "primary_hold_runtime_median_minutes": primary_hold_runtime_median_minutes,
            "primary_hold_recent_runtime_median_minutes": primary_hold_recent_runtime_median_minutes,
            "primary_success_completed_count": len(primary_success_completed),
            "primary_hold_completed_count": len(primary_hold_completed),
            "primary_progress_baseline_minutes": primary_progress_baseline_minutes,
            "antitarget_runtime_median_minutes": antitarget_runtime_median_minutes,
            "antitarget_recent_runtime_median_minutes": antitarget_recent_runtime_median_minutes,
            "antitarget_success_runtime_median_minutes": antitarget_success_runtime_median_minutes,
            "antitarget_success_recent_runtime_median_minutes": antitarget_success_recent_runtime_median_minutes,
            "antitarget_hold_runtime_median_minutes": antitarget_hold_runtime_median_minutes,
            "antitarget_hold_recent_runtime_median_minutes": antitarget_hold_recent_runtime_median_minutes,
            "antitarget_success_completed_count": len(antitarget_success_completed),
            "antitarget_hold_completed_count": len(antitarget_hold_completed),
            "primary_pending": primary_pending,
            "antitarget_pending": antitarget_pending,
            "stable_target_count": stable_target_count,
            "total_actual_rows": total_actual_rows,
            "stk17b_retry_target_id": stk17b_retry_target_id,
            "stk17b_retry_start_shard_id": stk17b_retry_start_shard_id,
            "stk17b_retry_total_seen_shards": stk17b_retry_total_seen_shards,
            "stk17b_retry_resolved_shards": stk17b_retry_resolved_shards,
            "stk17b_retry_success_shards": stk17b_retry_success_shards,
            "stk17b_retry_hold_shards": stk17b_retry_hold_shards,
            "stk17b_retry_running_shards": stk17b_retry_running_shards,
            "stk17b_retry_success_pct": stk17b_retry_success_pct,
            "stk17b_retry_hold_pct": stk17b_retry_hold_pct,
            "stk17b_retry_last_outcome": stk17b_retry_last_outcome,
            "stk17b_retry_last_outcome_shard_id": stk17b_retry_last_outcome_shard_id,
            "stk17b_retry_ready": stk17b_retry_ready,
            "primary_running_tracked_minutes": _minutes_between(primary_running_started, primary_running_updated),
            "primary_running_update_age_minutes": _minutes_between(primary_running_updated, now),
            "primary_signal_age_minutes": primary_signal_age_minutes,
            "primary_last_signal_event": str(last_primary_signal.get("event", "")).strip(),
            "primary_signal_gap_minutes": primary_signal_gap_minutes,
            "focus_primary_target": focus_primary_target,
            "focus_primary_shard": focus_primary_shard,
            "focus_primary_status": focus_primary_status,
            "focus_primary_mode": focus_primary_mode,
            "focus_primary_target_completion_pct": focus_primary_target_completion_pct,
            "focus_primary_target_remaining_shards": focus_primary_target_remaining_shards,
            "focus_primary_stage": focus_primary_stage,
            "focus_primary_heartbeat_count": focus_primary_heartbeat_count,
            "focus_primary_event_count": focus_primary_event_count,
            "focus_primary_runtime_baseline_minutes": focus_primary_runtime_baseline,
            "focus_primary_estimated_pct": focus_primary_estimated_pct,
            "antitarget_running_tracked_minutes": _minutes_between(antitarget_running_started, antitarget_running_updated),
            "antitarget_running_update_age_minutes": _minutes_between(antitarget_running_updated, now),
            "antitarget_signal_age_minutes": antitarget_signal_age_minutes,
            "antitarget_last_signal_event": str(last_antitarget_signal.get("event", "")).strip(),
            "antitarget_signal_gap_minutes": antitarget_signal_gap_minutes,
            "primary_watch_loop_pid": int(primary_watch_loop.get("pid", 0) or 0),
            "primary_watch_loop_pid_path": str(primary_watch_loop.get("pid_path", "")),
            "primary_watch_loop_attached": bool(primary_watch_loop.get("pid_alive", False)),
            "primary_watch_loop_liveness": primary_watch_loop_liveness,
            "primary_watch_loop_fallback_mode": primary_watch_loop_fallback_mode,
            "antitarget_watch_loop_pid": int(antitarget_watch_loop.get("pid", 0) or 0),
            "antitarget_watch_loop_pid_path": str(antitarget_watch_loop.get("pid_path", "")),
            "antitarget_watch_loop_attached": bool(antitarget_watch_loop.get("pid_alive", False)),
            "antitarget_watch_loop_liveness": antitarget_watch_loop_liveness,
            "antitarget_watch_loop_fallback_mode": antitarget_watch_loop_fallback_mode,
            "primary_eta_hours": primary_eta_hours,
            "antitarget_eta_hours": antitarget_eta_hours,
            "dpre1_wave2_target_id": _first_text_from_sources(
                [dpre1_result_review_summary, dpre1_run_record_summary, dpre1_result_summary_summary],
                "target_id",
                default="DprE1",
            ),
            "dpre1_wave2_serialized_run_order": _first_text_from_sources(
                [dpre1_result_review_summary, dpre1_run_record_summary, dpre1_result_summary_summary],
                "serialized_run_order",
            ),
            "dpre1_wave2_queue_status_now": _first_text_from_sources(
                [dpre1_result_review_summary, dpre1_run_record_summary, dpre1_result_summary_summary],
                "queue_status_now",
            ),
            "dpre1_wave2_execution_state": _first_text_from_sources(
                [dpre1_run_record_summary, dpre1_result_review_summary, dpre1_result_summary_summary],
                "execution_state",
            ),
            "dpre1_wave2_selected_command_kind": _first_text_from_sources(
                [dpre1_result_summary_summary, dpre1_result_review_summary, dpre1_run_record_summary],
                "action",
                "selected_command_kind",
                default="advance_to_successor_gate",
            ),
            "dpre1_wave2_successor_target": _first_text_from_sources(
                [dpre1_run_record_summary, dpre1_result_review_summary, dpre1_result_summary_summary],
                "successor_target",
                default="T. cruzi KRS1",
            ),
            "dpre1_wave2_next_required_step": _first_text_from_sources(
                [dpre1_run_record_summary, dpre1_result_review_summary, dpre1_result_summary_summary],
                "next_required_step",
            ),
            "antitarget_panel_total": antitarget_panel_total,
            "antitarget_panel_resolved": antitarget_panel_resolved,
            "antitarget_panel_running": antitarget_panel_running,
            "antitarget_panel_remaining": antitarget_panel_remaining,
            "antitarget_panel_completion_pct": antitarget_panel_completion_pct,
            "antitarget_panel_avg_completed_minutes": antitarget_panel_avg_completed_minutes,
            "antitarget_panel_median_completed_minutes": antitarget_panel_median_completed_minutes,
            "antitarget_panel_runtime_baseline_minutes": antitarget_panel_runtime_baseline,
            "antitarget_stage_label": antitarget_stage_label,
            "antitarget_heartbeat_count": antitarget_heartbeat_count,
            "antitarget_event_count": antitarget_event_count,
            "antitarget_estimated_running_pct": antitarget_estimated_running_pct,
        },
        "top_target_rows": _top_target_rows(
            list(primary_monitor.get("rows", []) or []),
            stability_rows_by_target,
            limit=6,
            target_filter=target_filter,
            success_only=success_only,
        ),
        "branch_lane_summaries": {
            "cathepsin_followup": cathepsin_exploratory_lane,
            "mpro_exploratory": mpro_exploratory_lane,
            "tcruzi_pde_exploratory": tcruzi_pde_exploratory_lane,
            "dengue_stage6_tuning_surface": dengue_stage6_tuning_surface,
            "dengue_exploratory": dengue_exploratory_lane,
            "dengue_followup": dengue_followup_lane,
        },
        "mapping_fix_lanes": {
            "mpro": mpro_mapping_fix_snapshot,
            "tcruzi_pde": tcruzi_mapping_fix_snapshot,
        },
    }


def render_snapshot(
    snapshot: dict[str, Any],
    *,
    color: bool = False,
    compact: bool = False,
    success_only: bool = False,
) -> str:
    if success_only:
        compact = True
    pmon = _summary(snapshot["primary_monitor"])
    peqq = _summary(snapshot["primary_queue"])
    aq = _summary(snapshot["antitarget_queue"])
    eng = _summary(snapshot["engineering"])
    stk = _summary(snapshot["stack"])
    hnd = _summary(snapshot["handoff"])
    msem = _summary(snapshot["monitor_semantics"])
    pre = _summary(snapshot["prelaunch"])
    branch_lanes = dict(snapshot.get("branch_lane_summaries", {}) or {})
    cathepsin_exploratory_lane_summary = _summary(branch_lanes.get("cathepsin_followup", {}))
    mpro_exploratory_lane_summary = _summary(branch_lanes.get("mpro_exploratory", {}))
    tcruzi_pde_exploratory_lane_summary = _summary(branch_lanes.get("tcruzi_pde_exploratory", {}))
    dengue_stage6_tuning_surface_summary = _summary(branch_lanes.get("dengue_stage6_tuning_surface", {}))
    dengue_exploratory_lane_summary = _summary(branch_lanes.get("dengue_exploratory", {}))
    dengue_followup_lane_summary = _summary(branch_lanes.get("dengue_followup", {}))
    computed = dict(snapshot["computed"])
    target_filter = str(snapshot.get("target_filter", "") or "").strip()
    primary_events = _matching_primary_events(snapshot["primary_events"], target_filter)
    antitarget_events = _matching_antitarget_events(snapshot["antitarget_events"], target_filter)
    primary_total_rows = int(peqq.get("queue_row_count", 0) or pmon.get("total_shards", 0) or 0)
    primary_resolved_rows = int(peqq.get("resolved_row_count", 0) or pmon.get("resolved_shards", 0) or 0)
    primary_success_rows = int(pmon.get("successful_resolved_shards", 0) or 0)
    primary_mapping_failed_rows = int(pmon.get("mapping_failed_resolved_shards", 0) or 0)
    primary_gate_failed_rows = int(pmon.get("gate_failed_resolved_shards", 0) or 0)
    primary_hold_other_rows = int(pmon.get("hold_other_resolved_shards", 0) or 0)
    primary_hold_rows = int(pmon.get("held_resolved_shards", 0) or 0)
    primary_running_rows = int(peqq.get("running_row_count", 0) or pmon.get("running_shards", 0) or 0)
    primary_completion_pct = (
        (100.0 * primary_resolved_rows / primary_total_rows) if primary_total_rows > 0 else float(pmon.get("completion_pct", 0.0) or 0.0)
    )
    antitarget_success_rows = int(computed.get("antitarget_success_completed_count", 0) or 0)
    antitarget_hold_rows = int(computed.get("antitarget_hold_completed_count", 0) or 0)

    primary_bar = _progress_bar(
        int(pmon.get("resolved_shards", 0) or 0),
        int(pmon.get("total_shards", 0) or 0),
        width=22,
        color=color,
        bar_color=CYAN,
    )
    counter_bar = _progress_bar(
        int(aq.get("resolved_row_count", 0) or 0),
        int(aq.get("queue_row_count", 0) or 0),
        width=22,
        color=color,
        bar_color=MAGENTA,
    )
    counter_status = str(aq.get("first_actionable_queue_status", "-") or "-")
    counter_primary = str(aq.get("first_actionable_primary_target_id", "-") or "-")
    counter_target = str(aq.get("first_actionable_anti_target_id", "-") or "-")
    counter_shard = str(aq.get("first_actionable_shard_id", "-") or "-")
    counter_stage = str(computed.get("antitarget_stage_label", "-") or "-")
    counter_hb = int(computed.get("antitarget_heartbeat_count", 0) or 0)
    counter_ev = int(computed.get("antitarget_event_count", 0) or 0)
    counter_estimated_pct = float(computed.get("antitarget_estimated_running_pct", 0.0) or 0.0)
    counter_panel_pct = float(computed.get("antitarget_panel_completion_pct", 0.0) or 0.0)
    counter_mode = (
        "heartbeat-only"
        if "supervision_only" in counter_status
        else "compute-attached"
        if "running" in counter_status
        else "dispatch-ready"
        if counter_status.startswith("ready")
        else "-"
    )
    focus_primary_target = str(computed.get("focus_primary_target", "")).strip() or str(pmon.get("focus_target_id", "")).strip()
    focus_primary_shard = str(computed.get("focus_primary_shard", "")).strip() or str(pmon.get("focus_shard_id", "")).strip()
    focus_primary_status = str(computed.get("focus_primary_status", "")).strip() or str(pmon.get("focus_queue_status", "")).strip()
    focus_primary_mode = str(computed.get("focus_primary_mode", "")).strip() or str(pmon.get("focus_mode", "")).strip() or "idle"
    focus_primary_stage = str(computed.get("focus_primary_stage", "")).strip() or str(pmon.get("focus_active_stage_label", "")).strip() or "-"
    focus_primary_heartbeat_count = int(computed.get("focus_primary_heartbeat_count", 0) or pmon.get("focus_heartbeat_count", 0) or 0)
    focus_primary_event_count = int(computed.get("focus_primary_event_count", 0) or pmon.get("focus_event_count", 0) or 0)
    focus_primary_estimated_pct = float(computed.get("focus_primary_estimated_pct", 0.0) or pmon.get("focus_estimated_running_shard_pct", 0.0) or 0.0)
    primary_lane_label = (
        f"{focus_primary_target} {focus_primary_shard}"
        if focus_primary_target and focus_primary_shard
        else "-"
    )
    primary_signal_text = (
        f"{computed['primary_last_signal_event'] or 'n/a'} | age {_fmt_duration_minutes(computed['primary_signal_age_minutes'])} | "
        f"gap {_fmt_duration_minutes(computed['primary_signal_gap_minutes']) if computed['primary_signal_gap_minutes'] > 0 else 'n/a'}"
    )
    primary_lane_detail = (
        f"running | target {_fmt_pct(computed.get('focus_primary_target_completion_pct', pmon.get('focus_target_completion_pct', pmon.get('active_target_completion_pct', 0))))} | "
        f"shard~{_fmt_pct(focus_primary_estimated_pct)} | "
        f"stage {focus_primary_stage} | hb {focus_primary_heartbeat_count} | ev {focus_primary_event_count} | "
        f"tracked {_fmt_duration_minutes(computed['primary_running_tracked_minutes'])} | "
        f"signal {_style(color, primary_signal_text, _freshness_color(computed['primary_signal_age_minutes']))}"
        if focus_primary_mode == "running"
        else f"dispatch-ready | target {_fmt_pct(computed.get('focus_primary_target_completion_pct', pmon.get('focus_target_completion_pct', 0)))} | "
        f"remaining {computed.get('focus_primary_target_remaining_shards', pmon.get('focus_target_remaining_shards', 0))} | "
        f"last signal {_style(color, primary_signal_text, _freshness_color(computed['primary_signal_age_minutes']))}"
        if focus_primary_mode == "dispatch_ready"
        else f"stale-needs-recovery | target {_fmt_pct(computed.get('focus_primary_target_completion_pct', pmon.get('focus_target_completion_pct', 0)))} | "
        f"last signal {_style(color, primary_signal_text, _freshness_color(computed['primary_signal_age_minutes']))}"
        if focus_primary_mode == "stale"
        else "idle"
    )
    primary_watch_text = (
        f"watch loop attached {'yes' if bool(computed.get('primary_watch_loop_attached', False)) else 'no'} | "
        f"liveness {computed.get('primary_watch_loop_liveness', 'detached')} | "
        f"fallback {computed.get('primary_watch_loop_fallback_mode', 'manual-restart')}"
    )
    antitarget_signal_text = (
        f"{computed['antitarget_last_signal_event'] or 'n/a'} | age {_fmt_duration_minutes(computed['antitarget_signal_age_minutes'])} | "
        f"gap {_fmt_duration_minutes(computed['antitarget_signal_gap_minutes']) if computed['antitarget_signal_gap_minutes'] > 0 else 'n/a'}"
    )
    antitarget_watch_text = (
        f"watch loop attached {'yes' if bool(computed.get('antitarget_watch_loop_attached', False)) else 'no'} | "
        f"liveness {computed.get('antitarget_watch_loop_liveness', 'detached')} | "
        f"fallback {computed.get('antitarget_watch_loop_fallback_mode', 'manual-restart')}"
    )
    stk17b_retry_text = (
        f"{computed.get('stk17b_retry_target_id', 'STK17B (DRAK2)')} retry from {computed.get('stk17b_retry_start_shard_id', '-')} | "
        f"success {computed.get('stk17b_retry_success_shards', 0)} ({_fmt_pct(computed.get('stk17b_retry_success_pct', 0.0))}) | "
        f"hold {computed.get('stk17b_retry_hold_shards', 0)} ({_fmt_pct(computed.get('stk17b_retry_hold_pct', 0.0))}) | "
        f"running {computed.get('stk17b_retry_running_shards', 0)} | "
        f"last {computed.get('stk17b_retry_last_outcome', '') or '-'} {computed.get('stk17b_retry_last_outcome_shard_id', '') or '-'}"
        if (
            bool(computed.get("stk17b_retry_ready", False))
            or int(computed.get("stk17b_retry_total_seen_shards", 0) or 0) > 0
            or target_filter == "STK17B (DRAK2)"
        )
        else ""
    )
    stk17b_followup_label = (
        str(
            msem.get("stk17b_followup_lane_label")
            or msem.get("selected_manual_retry_lane_label")
            or msem.get("stk17b_exploratory_followup_lane_label")
            or ""
        ).strip()
    )
    stk17b_followup_freeze_state = str(
        msem.get("stk17b_followup_freeze_state")
        or msem.get("selected_manual_retry_freeze_state")
        or msem.get("stk17b_exploratory_followup_freeze_state")
        or ""
    ).strip()
    stk17b_followup_freeze_note = str(
        msem.get("stk17b_followup_freeze_note")
        or msem.get("selected_manual_retry_freeze_note")
        or msem.get("stk17b_exploratory_followup_freeze_note")
        or ""
    ).strip()
    stk17b_followup_next_required_step = str(
        msem.get("next_required_step")
        or hnd.get("next_required_step")
        or ""
    ).strip()
    stk17b_followup_text = (
        f"{msem.get('selected_manual_retry_target_id', 'STK17B (DRAK2)')} follow-up | "
        f"lane {stk17b_followup_label or '-'} | freeze {stk17b_followup_freeze_state or '-'} | "
        f"note {_shorten(stk17b_followup_freeze_note, 74) if stk17b_followup_freeze_note else '-'} | "
        f"next {_shorten(stk17b_followup_next_required_step, 92) if stk17b_followup_next_required_step else '-'}"
        if stk17b_followup_label or stk17b_followup_freeze_state or stk17b_followup_freeze_note
        else ""
    )
    generic_retry_focus_target = str(
        msem.get("target_retry_focus_target_id")
        or hnd.get("broad_screen_target_retry_focus_target_id")
        or "-"
    ).strip()
    generic_retry_label = str(
        msem.get("target_retry_focus_template_label")
        or hnd.get("broad_screen_target_retry_focus_template_label")
        or "-"
    ).strip()
    generic_retry_command = str(
        msem.get("target_retry_focus_selected_command_kind")
        or hnd.get("broad_screen_target_retry_focus_selected_command_kind")
        or "-"
    ).strip()
    generic_retry_template_count = int(
        msem.get("target_retry_template_target_count")
        or hnd.get("broad_screen_target_retry_template_target_count")
        or 0
    )
    generic_retry_empirical_count = int(
        msem.get("target_retry_empirical_validated_target_count")
        or hnd.get("broad_screen_target_retry_empirical_validated_target_count")
        or 0
    )
    generic_retry_threshold = float(
        msem.get("target_retry_focus_selected_threshold_A")
        or hnd.get("broad_screen_target_retry_focus_selected_threshold_A")
        or 0.0
    )
    generic_retry_text = (
        f"{generic_retry_focus_target} | {generic_retry_label or '-'} | "
        f"cmd {generic_retry_command or '-'} | templates {generic_retry_template_count} | "
        f"empirical {generic_retry_empirical_count}"
        f"{f' | thr {generic_retry_threshold:.1f}A' if generic_retry_threshold > 0 else ''}"
        if generic_retry_label not in {'', '-'} or generic_retry_template_count > 0
        else ""
    )
    generic_retry_short_text = (
        f"{generic_retry_label or '-'} | {generic_retry_template_count} tpl | {generic_retry_empirical_count} emp"
        f"{f' | {generic_retry_threshold:.1f}A' if generic_retry_threshold > 0 else ''}"
        if generic_retry_label not in {'', '-'} or generic_retry_template_count > 0
        else ""
    )
    mapping_fix_focus_target = str(
        msem.get("mapping_fix_retry_focus_target_id")
        or hnd.get("broad_screen_mapping_fix_retry_focus_target_id")
        or "-"
    ).strip()
    mapping_fix_label = str(
        msem.get("mapping_fix_retry_focus_template_label")
        or hnd.get("broad_screen_mapping_fix_retry_focus_template_label")
        or "-"
    ).strip()
    mapping_fix_command = str(
        msem.get("mapping_fix_retry_focus_selected_command_kind")
        or hnd.get("broad_screen_mapping_fix_retry_focus_selected_command_kind")
        or "-"
    ).strip()
    mapping_fix_template_count = int(
        msem.get("mapping_fix_retry_template_target_count")
        or hnd.get("broad_screen_mapping_fix_retry_template_target_count")
        or 0
    )
    mapping_fix_ready_count = int(
        msem.get("mapping_fix_retry_ready_target_count")
        or hnd.get("broad_screen_mapping_fix_retry_ready_target_count")
        or 0
    )
    mapping_fix_ready_targets = str(
        msem.get("mapping_fix_retry_ready_targets")
        or hnd.get("broad_screen_mapping_fix_retry_ready_targets")
        or "-"
    ).strip()
    mapping_fix_text = (
        f"{mapping_fix_focus_target} | {mapping_fix_label or '-'} | "
        f"cmd {mapping_fix_command or '-'} | ready {mapping_fix_ready_count}/{mapping_fix_template_count or mapping_fix_ready_count} | "
        f"targets {_shorten(mapping_fix_ready_targets, 56)}"
        if mapping_fix_label not in {'', '-'} or mapping_fix_template_count > 0 or mapping_fix_ready_count > 0
        else ""
    )
    mapping_fix_short_text = (
        f"{mapping_fix_label or '-'} | {mapping_fix_ready_count}/{mapping_fix_template_count or mapping_fix_ready_count} ready | "
        f"{_shorten(_short_mapping_fix_targets(mapping_fix_ready_targets), 24)}"
        if mapping_fix_label not in {'', '-'} or mapping_fix_template_count > 0 or mapping_fix_ready_count > 0
        else ""
    )
    cathepsin_followup_status = "ready" if bool(cathepsin_exploratory_lane_summary.get("ready_for_manual_retry", False)) else "paused"
    cathepsin_followup_shard_id = str(cathepsin_exploratory_lane_summary.get("shard_id", "")).strip() or "-"
    cathepsin_followup_threshold = float(
        cathepsin_exploratory_lane_summary.get("selected_threshold_A")
        or cathepsin_exploratory_lane_summary.get("recommended_observed_threshold_A")
        or 0.0
    )
    cathepsin_followup_text = (
        f"{cathepsin_followup_status} | {cathepsin_followup_shard_id} | succ {int(cathepsin_exploratory_lane_summary.get('prior_tuned_success_count', 0) or 0)} "
        f"hold {int(cathepsin_exploratory_lane_summary.get('prior_tuned_hold_count', 0) or 0)}"
        f"{f' | {cathepsin_followup_threshold:.1f}A' if cathepsin_followup_threshold > 0 else ''}"
        if cathepsin_exploratory_lane_summary
        else ""
    )
    mpro_exploratory_status = "ready" if bool(mpro_exploratory_lane_summary.get("ready_for_manual_retry", False)) else "paused"
    tcruzi_pde_exploratory_status = "ready" if bool(tcruzi_pde_exploratory_lane_summary.get("ready_for_manual_retry", False)) else "paused"
    mpro_exploratory_threshold = float(
        mpro_exploratory_lane_summary.get("selected_threshold_A")
        or mpro_exploratory_lane_summary.get("recommended_observed_threshold_A")
        or 0.0
    )
    tcruzi_pde_exploratory_threshold = float(
        tcruzi_pde_exploratory_lane_summary.get("selected_threshold_A")
        or tcruzi_pde_exploratory_lane_summary.get("recommended_observed_threshold_A")
        or 0.0
    )
    mpro_exploratory_text = (
        f"{mpro_exploratory_status} | {str(mpro_exploratory_lane_summary.get('shard_id', '')).strip() or '-'} | "
        f"{mpro_exploratory_threshold:.1f}A"
        if mpro_exploratory_lane_summary
        else ""
    )
    tcruzi_pde_exploratory_text = (
        f"{tcruzi_pde_exploratory_status} | {str(tcruzi_pde_exploratory_lane_summary.get('shard_id', '')).strip() or '-'} | "
        f"{tcruzi_pde_exploratory_threshold:.1f}A"
        if tcruzi_pde_exploratory_lane_summary
        else ""
    )
    dpre1_guarded_review_text = _dpre1_guarded_review_line(snapshot, compact=compact)
    dpre1_guarded_review_short_text = _dpre1_guarded_review_line(snapshot, compact=True, success_only=True)
    dengue_stage6_text = _dengue_stage6_line(snapshot)
    mapping_fix_lanes = snapshot.get("mapping_fix_lanes", {}) or {}
    mpro_fix = dict(mapping_fix_lanes.get("mpro", {}) or {})
    tcruzi_fix = dict(mapping_fix_lanes.get("tcruzi_pde", {}) or {})
    mpro_mapping_fix_progress_text = _mapping_fix_lane_progress_text(mpro_fix)
    tcruzi_mapping_fix_progress_text = _mapping_fix_lane_progress_text(tcruzi_fix)

    lines = [
        _style(color, "Wet-Lab Campaign Monitor", BOLD),
        f"refreshed: {snapshot['generated_at'].replace('T', ' ')}",
    ]
    if target_filter:
        lines.append(f"focus: {target_filter}")
    if success_only:
        lines.append("mode: success-only compact")
    lines.append("")

    if compact:
        if success_only:
            lines.extend(
                [
                    f"{primary_bar} primary success {primary_success_rows}/{primary_total_rows} "
                    f"({_fmt_pct(pmon.get('successful_completion_pct', 0))}) | run {primary_running_rows} | success-rate {_fmt_rate(computed['primary_success_recent_rate'])}",
                    f"{counter_bar} counter success {antitarget_success_rows}/{aq.get('queue_row_count', 0)} "
                    f"| run {aq.get('running_row_count', 0)} | success-rate {_fmt_rate(computed['antitarget_success_recent_rate'])}",
                    _line(
                        "primary",
                        f"{primary_lane_label} | "
                        f"{_style(color, focus_primary_status or focus_primary_mode, _status_color(focus_primary_status or focus_primary_mode))} | "
                        f"stage {focus_primary_stage} | hb {focus_primary_heartbeat_count} | ev {focus_primary_event_count} | "
                        f"shard~{_fmt_pct(focus_primary_estimated_pct)} | "
                        f"signal {_style(color, _fmt_duration_minutes(computed['primary_signal_age_minutes']), _freshness_color(computed['primary_signal_age_minutes']))}",
                    ),
                    _line("primary watch", primary_watch_text),
                    _line(
                        "counter",
                        f"{counter_primary} -> {counter_target} {counter_shard} | "
                        f"{_style(color, counter_status, _status_color(counter_status))} | "
                        f"mode {counter_mode} | target {_fmt_pct(counter_panel_pct)} | stage {counter_stage} | hb {counter_hb} | ev {counter_ev} | "
                        f"shard~{_fmt_pct(counter_estimated_pct)} | "
                        f"signal {_style(color, _fmt_duration_minutes(computed['antitarget_signal_age_minutes']), _freshness_color(computed['antitarget_signal_age_minutes']))}",
                    ),
                    _line("counter watch", antitarget_watch_text),
                    _line("stk17b retry", stk17b_retry_text) if stk17b_retry_text else "",
                    _line("stk17b follow-up", stk17b_followup_text) if stk17b_followup_text else "",
                    _line("cathepsin follow-up", cathepsin_followup_text) if cathepsin_followup_text else "",
                    _line("dengue stage6", dengue_stage6_text) if dengue_stage6_text else "",
                    _line("retry family", generic_retry_short_text) if generic_retry_short_text else "",
                    _line("map-fix family", mapping_fix_short_text) if mapping_fix_short_text else "",
                    _line("mpro gate4.5", mpro_exploratory_text) if mpro_exploratory_text else "",
                    _line("pde gate5.1", tcruzi_pde_exploratory_text) if tcruzi_pde_exploratory_text else "",
                    _line("dpre1 guard", dpre1_guarded_review_short_text) if dpre1_guarded_review_short_text else "",
                    _line("next", f"{hnd.get('next_required_step', '-') }"),
                    _line("quality", f"success-only | full-ready {pmon.get('full_bulk_ready_target_count', 0)} | stable {computed['stable_target_count']} | actual rows {computed['total_actual_rows']}"),
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    f"{primary_bar} primary ok {primary_success_rows}/{primary_total_rows} "
                    f"({_fmt_pct(pmon.get('successful_completion_pct', 0))}) | map {primary_mapping_failed_rows} | gate {primary_gate_failed_rows} | other {primary_hold_other_rows} | run {primary_running_rows} | ok-rate {_fmt_rate(computed['primary_success_recent_rate'])} | hold-rate {_fmt_rate(computed['primary_hold_recent_rate'])}",
                    f"{counter_bar} counter ok {aq.get('resolved_row_count', 0)}/{aq.get('queue_row_count', 0)} "
                    f"| panel {_fmt_pct(counter_panel_pct)} | run {aq.get('running_row_count', 0)} | ok-rate {_fmt_rate(computed['antitarget_success_recent_rate'])} | hold-rate {_fmt_rate(computed['antitarget_hold_recent_rate'])}",
                    _line(
                        "primary",
                        f"{primary_lane_label} | "
                        f"{_style(color, focus_primary_status or focus_primary_mode, _status_color(focus_primary_status or focus_primary_mode))} | "
                        f"stage {focus_primary_stage} | hb {focus_primary_heartbeat_count} | ev {focus_primary_event_count} | "
                        f"shard~{_fmt_pct(focus_primary_estimated_pct)} | "
                        f"signal {_style(color, _fmt_duration_minutes(computed['primary_signal_age_minutes']), _freshness_color(computed['primary_signal_age_minutes']))}",
                    ),
                    _line("primary watch", primary_watch_text),
                    _line(
                        "counter",
                        f"{counter_primary} -> {counter_target} {counter_shard} | "
                        f"{_style(color, counter_status, _status_color(counter_status))} | "
                        f"mode {counter_mode} | target {_fmt_pct(counter_panel_pct)} | stage {counter_stage} | hb {counter_hb} | ev {counter_ev} | "
                        f"shard~{_fmt_pct(counter_estimated_pct)} | "
                        f"signal {_style(color, _fmt_duration_minutes(computed['antitarget_signal_age_minutes']), _freshness_color(computed['antitarget_signal_age_minutes']))}",
                    ),
                    _line("counter watch", antitarget_watch_text),
                    _line("stk17b retry", stk17b_retry_text) if stk17b_retry_text else "",
                    _line("stk17b follow-up", stk17b_followup_text) if stk17b_followup_text else "",
                    _line("cathepsin follow-up", cathepsin_followup_text) if cathepsin_followup_text else "",
                    _line("dengue stage6", dengue_stage6_text) if dengue_stage6_text else "",
                    _line("generic retry", generic_retry_text) if generic_retry_text else "",
                    _line("mapping-fix", mapping_fix_text) if mapping_fix_text else "",
                    _line("mpro gate4.5", mpro_exploratory_text) if mpro_exploratory_text else "",
                    _line("pde gate5.1", tcruzi_pde_exploratory_text) if tcruzi_pde_exploratory_text else "",
                    _line("dpre1 guard", dpre1_guarded_review_text) if dpre1_guarded_review_text else "",
                    _line("next", f"{pre.get('target_id', '-') } {pre.get('primary_shard_id', '-') } | {pre.get('primary_queue_status', '-') }"),
                    _line("quality", f"full-ready {pmon.get('full_bulk_ready_target_count', 0)} | stable {computed['stable_target_count']} | actual rows {computed['total_actual_rows']}"),
                    "",
                ]
            )
    else:
        if success_only:
            lines.extend(
                [
                    "SUCCESS ONLY",
                    _line(
                        "primary",
                        f"{primary_bar} {primary_success_rows}/{primary_total_rows} success "
                        f"({_fmt_pct(pmon.get('successful_completion_pct', 0))}) | running {primary_running_rows} | success pending {computed['primary_pending']}",
                    ),
                    _line(
                        "throughput",
                        f"success overall {_fmt_rate(computed['primary_success_overall_rate'])} | success recent {_fmt_rate(computed['primary_success_recent_rate'])}",
                    ),
                    _line(
                        "runtime split",
                        f"success med {_fmt_float(computed['primary_success_runtime_median_minutes'])}m | success recent-med {_fmt_float(computed['primary_success_recent_runtime_median_minutes'])}m | "
                        f"baseline {_fmt_float(computed['primary_progress_baseline_minutes'])}m | eta {_fmt_duration_minutes(computed['primary_eta_hours'] * 60) if computed['primary_eta_hours'] > 0 else 'n/a'}",
                    ),
                    _line(
                        "counter",
                        f"{counter_bar} {antitarget_success_rows}/{aq.get('queue_row_count', 0)} success | running {aq.get('running_row_count', 0)} | success pending {computed['antitarget_pending']}",
                    ),
                    _line(
                        "counter rate",
                        f"success overall {_fmt_rate(computed['antitarget_success_overall_rate'])} | success recent {_fmt_rate(computed['antitarget_success_recent_rate'])}",
                    ),
                    _line(
                        "counter split",
                        f"success med {_fmt_float(computed['antitarget_success_runtime_median_minutes'])}m | success recent-med {_fmt_float(computed['antitarget_success_recent_runtime_median_minutes'])}m | "
                        f"eta {_fmt_duration_minutes(computed['antitarget_eta_hours'] * 60) if computed['antitarget_eta_hours'] > 0 else 'n/a'}",
                    ),
                    _line(
                        "quality",
                        f"full-ready {pmon.get('full_bulk_ready_target_count', 0)} | stable {computed['stable_target_count']} | actual rows {computed['total_actual_rows']}",
                    ),
                    _line(
                        "lane",
                        f"primary {primary_lane_label} | status {_style(color, focus_primary_status or focus_primary_mode, _status_color(focus_primary_status or focus_primary_mode))} | "
                        f"counter {counter_primary} -> {counter_target} {counter_shard} | mode {counter_mode}",
                    ),
                    _line("watch", f"primary {primary_watch_text} | counter {antitarget_watch_text}"),
                    _line("stk17b retry", stk17b_retry_text) if stk17b_retry_text else "",
                    _line("stk17b follow-up", stk17b_followup_text) if stk17b_followup_text else "",
                    _line("cathepsin follow-up", cathepsin_followup_text) if cathepsin_followup_text else "",
                    _line("dengue stage6", dengue_stage6_text) if dengue_stage6_text else "",
                    _line("retry family", generic_retry_short_text) if generic_retry_short_text else "",
                    _line("map-fix family", mapping_fix_short_text) if mapping_fix_short_text else "",
                    _line("mpro gate4.5", mpro_exploratory_text) if mpro_exploratory_text else "",
                    _line("pde gate5.1", tcruzi_pde_exploratory_text) if tcruzi_pde_exploratory_text else "",
                    _line("dpre1 guard", dpre1_guarded_review_short_text) if dpre1_guarded_review_short_text else "",
                    _line(
                        "next",
                        f"{hnd.get('next_required_step', '-')}",
                    ),
                    "",
                    "TOP SUCCESS TARGETS",
                    "  target                          success       running          actual top3   stability           rerank",
                ]
            )
        else:
            lines.extend(
                [
                    "OVERALL",
                    _line(
                        "primary",
                        f"{primary_bar} {primary_resolved_rows}/{primary_total_rows} resolved "
                        f"({_fmt_pct(primary_completion_pct)}) | running {primary_running_rows} | pending {computed['primary_pending']}",
                    ),
                    _line(
                        "throughput",
                        f"success overall {_fmt_rate(computed['primary_success_overall_rate'])} | success recent {_fmt_rate(computed['primary_success_recent_rate'])} | "
                        f"hold overall {_fmt_rate(computed['primary_hold_overall_rate'])} | hold recent {_fmt_rate(computed['primary_hold_recent_rate'])}",
                    ),
                    _line(
                        "resolved split",
                        f"success {primary_success_rows} | mapping {primary_mapping_failed_rows} | gate {primary_gate_failed_rows} | other {primary_hold_other_rows}",
                    ),
                    _line(
                        "runtime split",
                        f"success med {_fmt_float(computed['primary_success_runtime_median_minutes'])}m | success recent-med {_fmt_float(computed['primary_success_recent_runtime_median_minutes'])}m | "
                        f"hold med {_fmt_float(computed['primary_hold_runtime_median_minutes'])}m | hold recent-med {_fmt_float(computed['primary_hold_recent_runtime_median_minutes'])}m | "
                        f"progress-base {_fmt_float(computed['primary_progress_baseline_minutes'])}m | "
                        f"eta {_fmt_duration_minutes(computed['primary_eta_hours'] * 60) if computed['primary_eta_hours'] > 0 else 'n/a'}",
                    ),
                    _line(
                        "counterscreen",
                        f"{counter_bar} {aq.get('resolved_row_count', 0)}/{aq.get('queue_row_count', 0)} resolved | running {aq.get('running_row_count', 0)} | pending {computed['antitarget_pending']}",
                    ),
                    _line(
                        "counter rate",
                        f"success overall {_fmt_rate(computed['antitarget_success_overall_rate'])} | success recent {_fmt_rate(computed['antitarget_success_recent_rate'])} | "
                        f"hold overall {_fmt_rate(computed['antitarget_hold_overall_rate'])} | hold recent {_fmt_rate(computed['antitarget_hold_recent_rate'])}",
                    ),
                    _line(
                        "counter split",
                        f"success med {_fmt_float(computed['antitarget_success_runtime_median_minutes'])}m | success recent-med {_fmt_float(computed['antitarget_success_recent_runtime_median_minutes'])}m | "
                        f"hold med {_fmt_float(computed['antitarget_hold_runtime_median_minutes'])}m | hold recent-med {_fmt_float(computed['antitarget_hold_recent_runtime_median_minutes'])}m | "
                        f"eta {_fmt_duration_minutes(computed['antitarget_eta_hours'] * 60) if computed['antitarget_eta_hours'] > 0 else 'n/a'}",
                    ),
                    _line(
                        "counter panel",
                        f"{counter_primary} -> {counter_target} {counter_shard} | "
                        f"{computed['antitarget_panel_resolved']}/{computed['antitarget_panel_total']} resolved "
                        f"({_fmt_pct(counter_panel_pct)}) | remaining {computed['antitarget_panel_remaining']}",
                    ),
                    "",
                    "QUALITY",
                    _line(
                        "bulk/stable",
                        f"full-ready {pmon.get('full_bulk_ready_target_count', 0)} | stable {computed['stable_target_count']} | partial-actual {pmon.get('partial_actual_target_count', 0)}",
                    ),
                    _line(
                        "data layer",
                        f"actual rows {computed['total_actual_rows']} | override targets {stk.get('broad_screen_override_target_count', 0)} | library {stk.get('broad_screen_ingested_compound_count', 0)}",
                    ),
                    _line(
                        "engineering",
                        f"progress {eng.get('overall_progress_band', '-') } | auto-append {eng.get('auto_append_ready', False)} | anti-target queue {eng.get('anti_target_execution_queue_ready', False)}",
                    ),
                    "",
                    "ACTIVE LANES",
                    _line(
                        "primary lane",
                        f"{primary_lane_label} | "
                        f"status {_style(color, focus_primary_status or focus_primary_mode, _status_color(focus_primary_status or focus_primary_mode))} | "
                        f"{primary_lane_detail}",
                    ),
                    _line("primary watch", primary_watch_text),
                    _line(
                        "counter lane",
                        f"{counter_primary} -> {counter_target} {counter_shard} | "
                        f"status {_style(color, counter_status, _status_color(counter_status))} | "
                        f"mode {counter_mode} | target {_fmt_pct(counter_panel_pct)} | shard~{_fmt_pct(counter_estimated_pct)} | "
                        f"stage {counter_stage} | hb {counter_hb} | ev {counter_ev} | "
                        f"tracked {_fmt_duration_minutes(computed['antitarget_running_tracked_minutes'])} | "
                        f"signal {_style(color, antitarget_signal_text, _freshness_color(computed['antitarget_signal_age_minutes']))}",
                    ),
                    _line("counter watch", antitarget_watch_text),
                    _line("stk17b retry", stk17b_retry_text) if stk17b_retry_text else "",
                    _line("stk17b follow-up", stk17b_followup_text) if stk17b_followup_text else "",
                    _line("generic retry", generic_retry_text) if generic_retry_text else "",
                    _line("mapping-fix", mapping_fix_text) if mapping_fix_text else "",
                    _line("mpro fix lane", mpro_mapping_fix_progress_text) if mpro_mapping_fix_progress_text else "",
                    _line("tcruzi fix lane", tcruzi_mapping_fix_progress_text) if tcruzi_mapping_fix_progress_text else "",
                    _line("dpre1 guard", dpre1_guarded_review_text) if dpre1_guarded_review_text else "",
                    _line(
                        "next target",
                        f"{pre.get('target_id', '-') } {pre.get('primary_shard_id', '-') } | "
                        f"primary {pre.get('primary_queue_status', '-') } | anti {pre.get('anti_target_id', '-') }",
                    ),
                    "",
                    "TOP TARGETS",
                    "  target                          ok/map/gate/oth        running          actual top3   stability           rerank",
                ]
            )

    stability_rows_by_target = {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in (snapshot["stability"].get("rows", []) or [])
        if str(row.get("target_id", "")).strip()
    }
    if not compact:
        for row in snapshot["top_target_rows"]:
            target_id = str(row.get("target_id", "")).strip()
            stability = stability_rows_by_target.get(target_id, {})
            split_text = (
                f"{row.get('completed_shards', 0)}/"
                f"{row.get('mapping_failed_shards', 0)}/"
                f"{row.get('gate_failed_shards', 0)}/"
                f"{row.get('hold_other_shards', 0)}"
            )
            lines.append(
                "  "
                f"{_shorten(target_id, 30):<30} "
                f"{split_text[:22]:<22} "
                f"{str(row.get('current_running_shard', '-') or '-')[:15]:<15} "
                f"{str(row.get('actual_top3_count', 0))[:12]:<12} "
                f"{str(stability.get('stability_band', '-'))[:18]:<18} "
                f"{str(row.get('rerank_status', '-'))[:24]:<24}"
            )

    if not success_only:
        lines.extend(
            [
                "",
                * _render_recent_events("RECENT PRIMARY EVENTS", primary_events, _format_primary_event),
                "",
                * _render_recent_events("RECENT COUNTERSCREEN EVENTS", antitarget_events, _format_antitarget_event),
                "",
                "NEXT",
                f"  primary: {pmon.get('next_required_step', '-')}",
                f"  counter: {aq.get('next_required_step', '-')}",
                f"  handoff: {hnd.get('next_required_step', '-')}",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "NEXT",
                f"  primary: {pmon.get('next_required_step', '-')}",
                f"  counter: {aq.get('next_required_step', '-')}",
                f"  handoff: {hnd.get('next_required_step', '-')}",
            ]
        )
    return "\n".join(lines)


def _refresh(mode: str = "light") -> None:
    normalized = str(mode or "light").strip().lower()
    if normalized == "none":
        return
    scripts = DEFAULT_FULL_REFRESH_SCRIPTS if normalized == "full" else DEFAULT_LIGHT_REFRESH_SCRIPTS
    for script in scripts:
        subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified CLI monitor for wet-lab broad screen, counterscreen, and next-target preparation.")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--refresh-mode", choices=("light", "full", "none"), default="light")
    parser.add_argument(
        "--full-refresh-every",
        type=int,
        default=0,
        help="When looping in light refresh mode, run a full refresh every N iterations. 0 disables periodic full refresh.",
    )
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=5.0)
    parser.add_argument("--clear-screen", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--success-only", action="store_true")
    parser.add_argument("--target", default="")
    parser.add_argument("--color", choices=("auto", "always", "never"), default="auto")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    color_enabled = sys.stdout.isatty() if args.color == "auto" else args.color == "always"
    iteration = 0
    while True:
        if args.refresh:
            iteration += 1
            refresh_mode = args.refresh_mode
            if (
                args.loop
                and args.refresh_mode == "light"
                and int(args.full_refresh_every or 0) > 0
                and iteration % int(args.full_refresh_every) == 0
            ):
                refresh_mode = "full"
            _refresh(refresh_mode)
        text = render_snapshot(
            _build_snapshot(target_filter=args.target),
            color=color_enabled,
            compact=args.compact or args.success_only,
            success_only=args.success_only,
        )
        if args.clear_screen:
            print("\033[2J\033[H", end="")
        print(text)
        if not args.loop:
            break
        time.sleep(max(args.interval_sec, 0.5))
