#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from statistics import mean, median
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
TARGET_ID = "Leishmania braziliensis DHODH"
TARGET_SLUG = "leishmania_braziliensis_dhodh"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_lbdhodh_stage6_tuning_surface_current.json"
DEFAULT_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_lbdhodh_exploratory_retry_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ""}:
            return default
        return float(value)
    except Exception:
        return default


def _queue_rows(execution_queue_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(row or {})
        for row in (execution_queue_payload.get("rows", []) or [])
        if _text((row or {}).get("target_id")) == TARGET_ID
    ]


def _summary_path(shard_id: str) -> Path:
    base = ROOT / "runs" / "wetlab_broad_screen_throughput" / TARGET_SLUG / shard_id
    return base / "throughput_run_gate51_summary.json"


def _load_service_payload(shard_id: str) -> tuple[dict[str, Any], str]:
    summary_path = _summary_path(shard_id)
    return maybe_load_json(str(summary_path)) or {}, str(summary_path)


def _gate51_row(row: dict[str, Any]) -> dict[str, Any] | None:
    shard_id = _text(row.get("shard_id"))
    if not shard_id:
        return None
    payload, summary_path = _load_service_payload(shard_id)
    if not payload:
        return None
    service = dict(payload.get("service_result", {}) or {})
    stage6 = dict((payload.get("stages", {}) or {}).get("stage6_operational_gate", {}) or {})
    observed = _safe_float(stage6.get("mean_min_distance_A"))
    if observed <= 0:
        return None
    return {
        "row_kind": "gate51_validation_row",
        "target_id": TARGET_ID,
        "shard_id": shard_id,
        "queue_status": _text(row.get("queue_status")),
        "execution_state": _text(row.get("execution_state")),
        "notes": _text(row.get("notes")),
        "service_status": _text(service.get("status")),
        "error_code": _text(service.get("error_code")),
        "failed_stage": _text(service.get("failed_stage")),
        "stage6_pass": bool(stage6.get("pass", False)),
        "mean_min_distance_A": observed,
        "observed_threshold_A": 5.1,
        "mean_min_distance_A_source": _text(stage6.get("mean_min_distance_A_source")),
        "min_frames_observed": int(_safe_float(stage6.get("min_frames_observed"), 0)),
        "summary_json": str(summary_path),
        "promotion_state": "validated",
    }


def build_payload(
    execution_queue_payload: dict[str, Any],
    stage6_tuning_surface_payload: dict[str, Any],
    exploratory_retry_lane_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tuning = _summary(stage6_tuning_surface_payload)
    exploratory = _summary(exploratory_retry_lane_payload)
    rows = _queue_rows(execution_queue_payload)
    hold_rows = [dict(row) for row in rows if _text(row.get("queue_status")) == "explicit_hold"]
    validation_rows = [
        row
        for row in (_gate51_row(row) for row in rows if _text(row.get("queue_status")) == "result_ready")
        if row is not None
    ]
    validation_rows.sort(key=lambda row: row["shard_id"])
    validation_values = [_safe_float(row.get("mean_min_distance_A")) for row in validation_rows if _safe_float(row.get("mean_min_distance_A")) > 0]

    success_mean = round(mean(validation_values), 3) if validation_values else 0.0
    success_median = round(median(validation_values), 3) if validation_values else 0.0
    success_min = round(min(validation_values), 3) if validation_values else 0.0
    success_max = round(max(validation_values), 3) if validation_values else 0.0
    next_required_step = (
        "Promote DHODH gate5.1 as validated, keep the default lane closed, and reserve any future DHODH reopen for an explicit new review."
        if validation_rows
        else "Wait for DHODH gate5.1 validation rows before promoting the target in the top-level handoff."
    )

    return {
        "summary": {
            "status": "wetlab_lbdhodh_gate51_validation_review_surface_ready",
            "target_id": TARGET_ID,
            "promotion_label": "gate5.1_validated",
            "validated": bool(validation_rows),
            "gate51_validated": bool(validation_rows),
            "default_lane_reopen_allowed": False,
            "branch_to_gate51_only": True,
            "decision": "promote_gate51_validated_keep_default_closed" if validation_rows else "review_pending",
            "decision_rationale": (
                "Default-lane shards 01_of_20-08_of_20 held, while gate5.1 validation shards starting at 09_of_20 all reached result_ready with HTVS_OK summaries, so DHODH should be promoted as validated and the default lane should remain closed."
                if validation_rows
                else "Validation rows are missing, so the promotion decision remains pending."
            ),
            "campaign_start_shard_id": "01_of_20",
            "default_lane_campaign_start_shard_id": "01_of_20",
            "default_lane_campaign_end_shard_id": "08_of_20",
            "validated_shard_ids": ";".join(row["shard_id"] for row in validation_rows),
            "validated_shard_count": len(validation_rows),
            "gate51_validation_row_count": len(validation_rows),
            "gate51_validation_success_count": len(validation_rows),
            "gate51_validation_success_pct": 100.0 if validation_rows else 0.0,
            "gate51_validation_start_shard_id": validation_rows[0]["shard_id"] if validation_rows else "",
            "gate51_validation_end_shard_id": validation_rows[-1]["shard_id"] if validation_rows else "",
            "default_lane_hold_count": len(hold_rows),
            "observed_metric_name": "mean_min_distance_A",
            "observed_metric_min_A": success_min,
            "observed_metric_median_A": success_median,
            "observed_metric_mean_A": success_mean,
            "observed_metric_max_A": success_max,
            "recommended_observed_threshold_A": _safe_float(tuning.get("recommended_observed_threshold_A"), 5.1),
            "selected_command_kind": _text(exploratory.get("selected_command_kind")) or "throughput_preflight_tuned_gate51",
            "selected_threshold_A": _safe_float(exploratory.get("selected_threshold_A"), 5.1),
            "validated_command_kind": _text(exploratory.get("selected_command_kind")) or "throughput_preflight_tuned_gate51",
            "validated_threshold_A": _safe_float(exploratory.get("selected_threshold_A"), 5.1),
            "validated_metric_name": "mean_min_distance_A",
            "validated_metric_min_A": success_min,
            "validated_metric_median_A": success_median,
            "validated_metric_mean_A": success_mean,
            "validated_metric_max_A": success_max,
            "exploratory_lane_label": _text(exploratory.get("lane_label")) or "exploratory_gate5.1_candidate",
            "exploratory_retry_shard_id": _text(exploratory.get("shard_id")) or "20_of_20",
            "next_required_step": next_required_step,
        },
        "structured": {
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "stage6_tuning_surface_artifact": "runs/wetlab_lbdhodh_stage6_tuning_surface_current.md",
            "exploratory_retry_lane_artifact": "runs/wetlab_lbdhodh_exploratory_retry_lane_current.md",
        },
        "rows": validation_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the DHODH gate5.1 validation review surface.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--stage6-tuning-surface-json", default=DEFAULT_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--exploratory-retry-lane-json", default=DEFAULT_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.execution_queue_json),
        load_json(args.stage6_tuning_surface_json),
        maybe_load_json(args.exploratory_retry_lane_json),
    )
    write_artifact(args.out_md, "Wet-Lab DHODH Gate5.1 Validation Review Surface", payload)


if __name__ == "__main__":
    main()
