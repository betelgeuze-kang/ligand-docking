#!/usr/bin/env python3
from __future__ import annotations

import argparse
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_PROGRESS_JSON = "runs/wetlab_broad_screen_progress_current.json"
DEFAULT_EVENT_LOG_JSONL = "runs/wetlab_broad_screen_runtime_event_log.jsonl"
DEFAULT_THROUGHPUT_SUMMARY_07_JSON = "runs/wetlab_broad_screen_throughput/ca_ix/07_of_20/throughput_run_summary.json"
DEFAULT_THROUGHPUT_SUMMARY_08_JSON = "runs/wetlab_broad_screen_throughput/ca_ix/08_of_20/throughput_run_summary.json"
DEFAULT_RESULT_ROWS_07_JSON = "runs/caix_broad_screen_shard_07_result_rows_current.json"
DEFAULT_RESULT_ROWS_08_JSON = "runs/caix_broad_screen_shard_08_result_rows_current.json"
DEFAULT_OUT_MD = "runs/caix_broad_screen_runtime_profile_current.md"


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
    return max((end - start).total_seconds() / 60.0, 0.0)


def _round1(value: float) -> float:
    return round(value, 1)


def _load_jsonl(path_like: str) -> list[dict[str, Any]]:
    import json
    from pathlib import Path

    path = Path(path_like)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            rows.append(json.loads(text))
        except Exception:
            continue
    return rows


def _duration_minutes(row: dict[str, Any]) -> float:
    started_at = _parse_ts(row.get("started_at"))
    completed_at = _parse_ts(row.get("completed_at") or row.get("updated_at"))
    return _minutes_between(started_at, completed_at)


def _classify_cause(
    *,
    throughput_summary_present: bool,
    reset_count: int,
    heartbeat_count: int,
    failed_stage: str,
    notes: str,
    distance_gate_failed: bool,
) -> str:
    if distance_gate_failed:
        return "speedpack_preflight_stage6_gate_failure"
    if reset_count > 0:
        return "runtime_reset_restart_churn"
    if not throughput_summary_present and "bootstrap_execution" in notes:
        return "bootstrap_only_uninstrumented_long_shard"
    if heartbeat_count == 0:
        return "low_visibility_runtime_without_heartbeat"
    return "serialized_runtime_slow_path"


def build_payload(
    progress_payload: dict[str, Any],
    event_rows: list[dict[str, Any]],
    throughput_07_payload: dict[str, Any] | None,
    throughput_08_payload: dict[str, Any] | None,
    result_rows_07_payload: dict[str, Any] | None,
    result_rows_08_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    progress_rows = [
        dict(row)
        for row in (progress_payload.get("rows", []) or [])
        if str(row.get("target_id", "")).strip() == "CA IX"
    ]
    completed_rows = [row for row in progress_rows if _duration_minutes(row) > 0]
    completed_minutes = [_duration_minutes(row) for row in completed_rows]
    overall_median_minutes = _round1(float(statistics.median(completed_minutes))) if completed_minutes else 0.0

    focus_shards = {"07_of_20", "08_of_20"}
    runtime_events = [
        dict(row)
        for row in event_rows
        if str(row.get("target_id", "")).strip() == "CA IX"
        and str(row.get("shard_id", "")).strip() in focus_shards
    ]

    throughput_by_shard = {
        "07_of_20": dict(throughput_07_payload or {}),
        "08_of_20": dict(throughput_08_payload or {}),
    }
    result_rows_by_shard = {
        "07_of_20": dict(result_rows_07_payload or {}),
        "08_of_20": dict(result_rows_08_payload or {}),
    }

    rows: list[dict[str, Any]] = []
    for shard_id in ("07_of_20", "08_of_20"):
        row = next((candidate for candidate in completed_rows if str(candidate.get("shard_id", "")).strip() == shard_id), {})
        shard_events = [candidate for candidate in runtime_events if str(candidate.get("shard_id", "")).strip() == shard_id]
        heartbeat_count = sum(1 for candidate in shard_events if str(candidate.get("event", "")).strip() == "heartbeat")
        reset_count = sum(1 for candidate in shard_events if str(candidate.get("event", "")).strip() == "reset")
        start_count = sum(1 for candidate in shard_events if str(candidate.get("event", "")).strip() == "start")
        complete_count = sum(1 for candidate in shard_events if str(candidate.get("event", "")).strip() == "complete")
        duration_minutes = _round1(_duration_minutes(row))
        slowdown_vs_median_minutes = _round1(duration_minutes - overall_median_minutes) if overall_median_minutes > 0 else 0.0
        slowdown_multiplier = round((duration_minutes / overall_median_minutes), 2) if overall_median_minutes > 0 else 0.0
        throughput_summary = throughput_by_shard.get(shard_id, {})
        result_rows = result_rows_by_shard.get(shard_id, {})
        stage6 = dict((throughput_summary.get("stages", {}) or {}).get("stage6_operational_gate", {}) or {})
        failed_stage = str(throughput_summary.get("failed_stage", "")).strip()
        mean_min_distance_a = float(stage6.get("mean_min_distance_A", 0.0) or 0.0)
        gate_threshold_a = float(stage6.get("gate_threshold_A", 2.5) or 2.5)
        distance_gate_failed = bool(failed_stage == "stage6_operational_gate" and mean_min_distance_a > 0)
        notes = str(row.get("notes", "")).strip()
        source_row_count = int((result_rows.get("summary", {}) or {}).get("row_count", 0) or 0)
        suspected_cause = _classify_cause(
            throughput_summary_present=bool(throughput_summary),
            reset_count=reset_count,
            heartbeat_count=heartbeat_count,
            failed_stage=failed_stage,
            notes=notes,
            distance_gate_failed=distance_gate_failed,
        )
        rows.append(
            {
                "target_id": "CA IX",
                "shard_id": shard_id,
                "duration_minutes": duration_minutes,
                "overall_median_minutes": overall_median_minutes,
                "slowdown_vs_median_minutes": slowdown_vs_median_minutes,
                "slowdown_multiplier": slowdown_multiplier,
                "start_count": start_count,
                "heartbeat_count": heartbeat_count,
                "reset_count": reset_count,
                "complete_count": complete_count,
                "event_count": len(shard_events),
                "notes": notes,
                "throughput_summary_present": bool(throughput_summary),
                "failed_stage": failed_stage,
                "mean_min_distance_A": mean_min_distance_a if distance_gate_failed else 0.0,
                "gate_threshold_A": gate_threshold_a if distance_gate_failed else 0.0,
                "result_row_count": source_row_count,
                "suspected_cause": suspected_cause,
                "profiling_note": (
                    "Speedpack preflight reached stage6 and failed the operational distance gate."
                    if distance_gate_failed
                    else "Bootstrap-only shard with shallow instrumentation; runtime is observed but internal stage attribution is not available."
                    if not throughput_summary
                    else "Runtime event pattern suggests serialized slow path without a distinct gate failure."
                ),
            }
        )

    worst_row = max(rows, key=lambda item: float(item.get("duration_minutes", 0.0) or 0.0)) if rows else {}
    gate_fail_row = next((item for item in rows if item.get("failed_stage")), {})
    summary = {
        "status": "caix_broad_screen_runtime_profile_ready",
        "target_id": "CA IX",
        "overall_completed_shard_count": len(completed_rows),
        "overall_median_completed_shard_minutes": overall_median_minutes,
        "profiled_shard_count": len(rows),
        "worst_profiled_shard_id": str(worst_row.get("shard_id", "")).strip(),
        "worst_profiled_duration_minutes": float(worst_row.get("duration_minutes", 0.0) or 0.0),
        "slowdown_flagged_shard_count": sum(1 for item in rows if float(item.get("duration_minutes", 0.0) or 0.0) > overall_median_minutes),
        "gate_failed_shard_count": sum(1 for item in rows if str(item.get("failed_stage", "")).strip()),
        "gate_failed_focus_shard_id": str(gate_fail_row.get("shard_id", "")).strip(),
        "next_required_step": "Use this profile to separate monitor-rate distortion from real shard-runtime slowdowns before tuning presets or thresholds.",
    }
    structured = {
        "progress_artifact": "runs/wetlab_broad_screen_progress_current.md",
        "event_log_artifact": "runs/wetlab_broad_screen_runtime_event_log.jsonl",
        "throughput_summary_08_artifact": DEFAULT_THROUGHPUT_SUMMARY_08_JSON,
        "result_rows_07_artifact": DEFAULT_RESULT_ROWS_07_JSON,
        "result_rows_08_artifact": DEFAULT_RESULT_ROWS_08_JSON,
    }
    return {"summary": summary, "structured": structured, "rows": rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile CA IX slow shards against the current broad-screen runtime median.")
    parser.add_argument("--progress-json", default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--event-log-jsonl", default=DEFAULT_EVENT_LOG_JSONL)
    parser.add_argument("--throughput-summary-07-json", default=DEFAULT_THROUGHPUT_SUMMARY_07_JSON)
    parser.add_argument("--throughput-summary-08-json", default=DEFAULT_THROUGHPUT_SUMMARY_08_JSON)
    parser.add_argument("--result-rows-07-json", default=DEFAULT_RESULT_ROWS_07_JSON)
    parser.add_argument("--result-rows-08-json", default=DEFAULT_RESULT_ROWS_08_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        progress_payload=load_json(args.progress_json),
        event_rows=_load_jsonl(args.event_log_jsonl),
        throughput_07_payload=load_json(args.throughput_summary_07_json) if Path(args.throughput_summary_07_json).exists() else {},
        throughput_08_payload=load_json(args.throughput_summary_08_json) if Path(args.throughput_summary_08_json).exists() else {},
        result_rows_07_payload=load_json(args.result_rows_07_json) if Path(args.result_rows_07_json).exists() else {},
        result_rows_08_payload=load_json(args.result_rows_08_json) if Path(args.result_rows_08_json).exists() else {},
    )
    write_artifact(args.out_md, "CA IX Broad Screen Runtime Profile", payload)


if __name__ == "__main__":
    main()
