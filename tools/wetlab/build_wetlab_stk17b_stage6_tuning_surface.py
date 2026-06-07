#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

TARGET_ID = "STK17B (DRAK2)"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE6_SURFACE_JSON = "runs/wetlab_primary_stage6_failure_surface_current.json"
DEFAULT_RETRY_LANE_JSON = "runs/wetlab_stk17b_manual_retry_lane_current.json"
DEFAULT_TRACE_JSON = "runs/wetlab_stk17b_exploratory_trace_current.json"
DEFAULT_FOLLOWUP_LANE_JSON = "runs/wetlab_stk17b_exploratory_followup_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_stk17b_stage6_tuning_surface_current.md"


def _text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ""}:
            return default
        return float(value)
    except Exception:
        return default


def _shard_ordinal(shard_id: str) -> int:
    text = _text(shard_id)
    if "_of_" not in text:
        return 0
    try:
        return int(text.split("_of_", 1)[0])
    except Exception:
        return 0


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def _round_up(value: float, step: float = 0.05) -> float:
    if value <= 0:
        return 0.0
    return round(math.ceil(value / step) * step, 3)


def _summary_path(shard_id: str) -> Path:
    base = ROOT / "runs" / "wetlab_broad_screen_throughput" / "stk17b_drak2" / shard_id
    gate45_path = base / "throughput_run_gate45_summary.json"
    default_path = base / "throughput_run_summary.json"
    if gate45_path.exists():
        return gate45_path
    return default_path


def _comparison_row(shard_id: str, expected_threshold: float) -> dict[str, Any]:
    summary_path = _summary_path(shard_id)
    payload = maybe_load_json(str(summary_path))
    service = dict(payload.get("service_result", {}) or {})
    stage6 = dict((payload.get("stages", {}) or {}).get("stage6_operational_gate", {}) or {})
    observed = _safe_float(stage6.get("mean_min_distance_A"))
    threshold = _safe_float(stage6.get("gate_threshold_A"), expected_threshold)
    return {
        "row_kind": "exploratory_success_hold_comparison",
        "target_id": TARGET_ID,
        "shard_id": shard_id,
        "service_status": _text(service.get("status")),
        "error_code": _text(service.get("error_code")),
        "failed_stage": _text(service.get("failed_stage")),
        "stage6_pass": bool(stage6.get("pass", False)),
        "mean_min_distance_A": observed,
        "gate_threshold_A": threshold,
        "distance_vs_threshold_A": round(observed - threshold, 3) if observed and threshold else 0.0,
        "min_frames_observed": int(_safe_float(stage6.get("min_frames_observed"), 0)),
        "mean_min_distance_A_source": _text(stage6.get("mean_min_distance_A_source")),
        "summary_json": str(summary_path),
    }


def _first_followup_shard_id(followup_summary: dict[str, Any]) -> str:
    direct = _text(followup_summary.get("followup_start_shard_id")) or _text(followup_summary.get("shard_id"))
    if direct:
        return direct
    shard_ids_text = _text(followup_summary.get("followup_shard_ids"))
    if not shard_ids_text:
        return ""
    return _text(shard_ids_text.split(";", 1)[0])


def build_payload(
    stage6_surface_payload: dict[str, Any],
    retry_lane_payload: dict[str, Any],
    trace_payload: dict[str, Any] | None = None,
    followup_lane_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    retry_summary = dict(retry_lane_payload.get("summary", {}) or {})
    trace_summary = dict((trace_payload or {}).get("summary", {}) or {})
    followup_summary = dict((followup_lane_payload or {}).get("summary", {}) or {})
    campaign_start = _text(retry_summary.get("campaign_start_shard_id")) or _text(retry_summary.get("shard_id"))
    start_ordinal = _shard_ordinal(campaign_start)
    detail_rows = []
    for row in stage6_surface_payload.get("rows", []) or []:
        candidate = dict(row or {})
        if _text(candidate.get("target_id")) != TARGET_ID:
            continue
        shard_id = _text(candidate.get("shard_id"))
        if not shard_id:
            continue
        if _shard_ordinal(shard_id) < start_ordinal:
            continue
        if _text(candidate.get("failed_stage")) != "stage6_operational_gate":
            continue
        detail_rows.append(candidate)
    detail_rows.sort(key=lambda row: _shard_ordinal(_text(row.get("shard_id"))))

    observed = [_safe_float(row.get("mean_min_distance_A")) for row in detail_rows]
    deltas = [_safe_float(row.get("stage6_failed_metric_delta")) for row in detail_rows]
    threshold = _safe_float(detail_rows[-1].get("stage6_failed_metric_threshold")) if detail_rows else 0.0
    latest = detail_rows[-1] if detail_rows else {}
    min_obs = min(observed) if observed else 0.0
    max_obs = max(observed) if observed else 0.0
    med_obs = _median(observed)
    med_delta = _median(deltas)
    recommended_threshold = _round_up(max_obs + 0.05, 0.05) if observed else 0.0
    exploratory_threshold = _round_up(med_obs, 0.05) if observed else 0.0
    comparison_threshold = _safe_float(
        followup_summary.get("selected_threshold_A"),
        _safe_float(trace_summary.get("exploratory_success_threshold_A"), exploratory_threshold),
    )
    exploratory_success_shard_id = _text(trace_summary.get("exploratory_success_shard_id"))
    followup_start_shard_id = _first_followup_shard_id(followup_summary)
    comparison_rows = [
        _comparison_row(shard_id, comparison_threshold)
        for shard_id in [exploratory_success_shard_id, followup_start_shard_id]
        if shard_id
    ]
    success_row = next((row for row in comparison_rows if row["shard_id"] == exploratory_success_shard_id), {})
    hold_row = next((row for row in comparison_rows if row["shard_id"] == followup_start_shard_id), {})
    comparison_gap = round(
        _safe_float(hold_row.get("mean_min_distance_A")) - _safe_float(success_row.get("mean_min_distance_A")),
        3,
    ) if success_row and hold_row else 0.0

    candidate_thresholds = []
    for label, candidate_threshold in [
        ("current_gate", threshold),
        ("median_align", exploratory_threshold),
        ("max_plus_margin", recommended_threshold),
    ]:
        if candidate_threshold <= 0:
            continue
        pass_count = sum(1 for value in observed if value <= candidate_threshold)
        candidate_thresholds.append(
            {
                "row_kind": "threshold_candidate",
                "target_id": TARGET_ID,
                "candidate_label": label,
                "candidate_threshold_A": candidate_threshold,
                "campaign_stage6_pass_count": pass_count,
                "campaign_stage6_total_count": len(observed),
                "campaign_stage6_pass_pct": round((pass_count / len(observed)) * 100.0, 1) if observed else 0.0,
                "notes": (
                    "baseline current gate"
                    if label == "current_gate"
                    else "aligns to current retry median"
                    if label == "median_align"
                    else "clears current retry band with a small margin"
                ),
            }
        )

    detail_out = [
        {
            "row_kind": "stage6_retry_observation",
            "target_id": TARGET_ID,
            "shard_id": _text(row.get("shard_id")),
            "queue_status": _text(row.get("queue_status")),
            "failed_stage": _text(row.get("failed_stage")),
            "mean_min_distance_A": _safe_float(row.get("mean_min_distance_A")),
            "gate_threshold_A": _safe_float(row.get("stage6_failed_metric_threshold")),
            "distance_over_threshold_A": _safe_float(row.get("distance_over_threshold_A")),
            "min_frames_observed": int(_safe_float(row.get("min_frames_observed"), 0)),
            "mean_min_distance_A_source": _text(row.get("mean_min_distance_A_source")),
            "summary_json": _text(row.get("summary_json")),
        }
        for row in detail_rows
    ]

    next_step = (
        f"Use the STK17B tuned retry lane with threshold candidates anchored on {campaign_start}; current data suggests trying a threshold near {recommended_threshold:.2f}A before spending another guarded retry slot."
        if detail_rows
        else "No STK17B retry observations were found yet; run a guarded tuned retry first."
    )
    return {
        "summary": {
            "status": "wetlab_stk17b_stage6_tuning_surface_ready",
            "target_id": TARGET_ID,
            "campaign_start_shard_id": campaign_start,
            "campaign_stage6_row_count": len(detail_rows),
            "current_gate_threshold_A": threshold,
            "exploratory_success_threshold_A": comparison_threshold,
            "exploratory_success_shard_id": exploratory_success_shard_id,
            "exploratory_followup_hold_shard_id": followup_start_shard_id,
            "exploratory_success_mean_min_distance_A": round(_safe_float(success_row.get("mean_min_distance_A")), 3) if success_row else 0.0,
            "exploratory_followup_hold_mean_min_distance_A": round(_safe_float(hold_row.get("mean_min_distance_A")), 3) if hold_row else 0.0,
            "exploratory_success_vs_hold_gap_A": comparison_gap,
            "median_mean_min_distance_A": round(med_obs, 3) if observed else 0.0,
            "min_mean_min_distance_A": round(min_obs, 3) if observed else 0.0,
            "max_mean_min_distance_A": round(max_obs, 3) if observed else 0.0,
            "median_distance_over_threshold_A": round(med_delta, 3) if deltas else 0.0,
            "latest_observed_shard_id": _text(latest.get("shard_id")),
            "latest_mean_min_distance_A": round(_safe_float(latest.get("mean_min_distance_A")), 3) if latest else 0.0,
            "recommended_relaxed_threshold_A": recommended_threshold,
            "exploratory_median_threshold_A": exploratory_threshold,
            "next_required_step": next_step,
        },
        "structured": {
            "stage6_failure_surface_artifact": "runs/wetlab_primary_stage6_failure_surface_current.md",
            "manual_retry_lane_artifact": "runs/wetlab_stk17b_manual_retry_lane_current.md",
            "exploratory_trace_artifact": "runs/wetlab_stk17b_exploratory_trace_current.md",
            "exploratory_followup_lane_artifact": "runs/wetlab_stk17b_exploratory_followup_lane_current.md",
        },
        "rows": comparison_rows + candidate_thresholds + detail_out,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a STK17B-specific stage6 tuning surface from guarded retry failures.")
    parser.add_argument("--stage6-surface-json", default=DEFAULT_STAGE6_SURFACE_JSON)
    parser.add_argument("--retry-lane-json", default=DEFAULT_RETRY_LANE_JSON)
    parser.add_argument("--trace-json", default=DEFAULT_TRACE_JSON)
    parser.add_argument("--followup-lane-json", default=DEFAULT_FOLLOWUP_LANE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab STK17B Stage6 Tuning Surface",
        build_payload(
            load_json(args.stage6_surface_json),
            load_json(args.retry_lane_json),
            maybe_load_json(args.trace_json),
            maybe_load_json(args.followup_lane_json),
        ),
    )


if __name__ == "__main__":
    main()
