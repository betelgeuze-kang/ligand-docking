#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from statistics import median
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

TARGET_ID = "Leishmania braziliensis DHODH"
TARGET_SLUG = "leishmania_braziliensis_dhodh"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_OUT_MD = "runs/wetlab_lbdhodh_stage6_tuning_surface_current.md"


def _text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ""}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {None, ""}:
            return default
        return int(value)
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


def _round_up(value: float, step: float = 0.05) -> float:
    if value <= 0:
        return 0.0
    return round(math.ceil(value / step) * step, 3)


def _summary_paths(shard_id: str) -> list[Path]:
    base = ROOT / "runs" / "wetlab_broad_screen_throughput" / TARGET_SLUG / shard_id
    return [
        base / "throughput_run_summary.json",
        base / "throughput_run_gate51_summary.json",
        base / "throughput_run_gate55_summary.json",
        base / "throughput_run_gate45_summary.json",
    ]


def _metric_fallback_paths(shard_id: str) -> list[tuple[Path, str]]:
    base = ROOT / "runs" / "wetlab_broad_screen_throughput" / TARGET_SLUG / shard_id
    return [
        (base / "throughput_run_gate51_stage4_calibration_scores.csv", "stage4_calibration_scores_mean(fallback)"),
        (base / "throughput_run_gate51_stage3_scores.csv", "stage3_scores_mean(fallback)"),
        (base / "throughput_run_gate55_stage4_calibration_scores.csv", "stage4_calibration_scores_mean(fallback)"),
        (base / "throughput_run_gate55_stage3_scores.csv", "stage3_scores_mean(fallback)"),
        (base / "throughput_run_stage4_calibration_scores.csv", "stage4_calibration_scores_mean(fallback)"),
        (base / "throughput_run_stage3_scores.csv", "stage3_scores_mean(fallback)"),
    ]


def _load_summary(shard_id: str) -> tuple[dict[str, Any], str]:
    for path in _summary_paths(shard_id):
        payload = maybe_load_json(str(path))
        if payload:
            return payload, str(path)
    return {}, str(_summary_paths(shard_id)[0])


def _infer_gate_threshold(summary_path: str, stage6_payload: dict[str, Any]) -> float:
    direct = _safe_float(stage6_payload.get("gate_threshold_A"))
    if direct > 0:
        return direct
    path = str(summary_path)
    if "gate51" in path:
        return 5.1
    if "gate55" in path:
        return 5.5
    if "gate45" in path:
        return 4.5
    return 2.5


def _fallback_metric_from_csv(shard_id: str) -> tuple[float, str]:
    for path, source in _metric_fallback_paths(shard_id):
        if not path.exists():
            continue
        values: list[float] = []
        try:
            with path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    value = _safe_float((row or {}).get("mean_min_distance_A"))
                    if value > 0:
                        values.append(value)
        except Exception:
            continue
        if values:
            return round(sum(values) / len(values), 6), source
    return 0.0, ""


def _find_bridge_row(throughput_bridge_payload: dict[str, Any], command_kind: str) -> dict[str, Any]:
    for row in throughput_bridge_payload.get("rows", []) or []:
        candidate = dict(row or {})
        if _text(candidate.get("command_kind")) == command_kind and _text(candidate.get("command")):
            return candidate
    return {}


def build_payload(execution_queue_payload: dict[str, Any], throughput_bridge_payload: dict[str, Any]) -> dict[str, Any]:
    target_rows = [
        dict(row)
        for row in (execution_queue_payload.get("rows", []) or [])
        if _text((row or {}).get("target_id")) == TARGET_ID
    ]
    target_rows.sort(key=lambda row: _shard_ordinal(_text(row.get("shard_id"))))

    observed_rows: list[dict[str, Any]] = []
    for row in target_rows:
        shard_id = _text(row.get("shard_id"))
        queue_status = _text(row.get("queue_status"))
        if queue_status != "explicit_hold":
            continue
        payload, summary_path = _load_summary(shard_id)
        service = dict(payload.get("service_result", {}) or {})
        stage6 = dict((payload.get("stages", {}) or {}).get("stage6_operational_gate", {}) or {})
        failed_stage = _text(service.get("failed_stage")) or _text(payload.get("failed_stage"))
        if failed_stage != "stage6_operational_gate":
            continue
        observed = _safe_float(stage6.get("mean_min_distance_A"))
        metric_source = _text(stage6.get("mean_min_distance_A_source"))
        if observed <= 0:
            observed, metric_source = _fallback_metric_from_csv(shard_id)
        if observed <= 0:
            continue
        threshold = _infer_gate_threshold(summary_path, stage6)
        observed_rows.append(
            {
                "row_kind": "stage6_retry_observation",
                "target_id": TARGET_ID,
                "shard_id": shard_id,
                "queue_status": queue_status,
                "service_status": _text(service.get("status")),
                "error_code": _text(service.get("error_code")),
                "failed_stage": failed_stage,
                "mean_min_distance_A": observed,
                "stage6_failed_metric": "mean_min_distance_A",
                "stage6_failed_metric_value": observed,
                "stage6_failed_metric_threshold": threshold,
                "stage6_failed_metric_delta": round(observed - threshold, 3),
                "mean_min_distance_A_source": metric_source,
                "min_frames_observed": _safe_int(stage6.get("min_frames_observed"), 0),
                "summary_json": summary_path,
            }
        )

    observed_rows.sort(key=lambda row: _shard_ordinal(_text(row.get("shard_id"))))
    values = [_safe_float(row.get("mean_min_distance_A")) for row in observed_rows if _safe_float(row.get("mean_min_distance_A")) > 0]
    current_threshold = _safe_float(observed_rows[-1].get("stage6_failed_metric_threshold"), 2.5) if observed_rows else 2.5
    min_obs = min(values) if values else 0.0
    max_obs = max(values) if values else 0.0
    median_obs = float(median(values)) if values else 0.0
    mean_obs = round(sum(values) / len(values), 3) if values else 0.0
    recommended_threshold = _round_up(max_obs, 0.05) if values else 0.0

    candidate_rows: list[dict[str, Any]] = []
    for label, threshold in [
        ("current_gate", current_threshold),
        ("candidate_5.0", 5.0),
        ("candidate_5.05", 5.05),
        ("candidate_5.1", 5.1),
        ("candidate_5.5", 5.5),
    ]:
        if threshold <= 0:
            continue
        pass_count = sum(1 for value in values if value <= threshold)
        candidate_rows.append(
            {
                "row_kind": "threshold_candidate",
                "target_id": TARGET_ID,
                "candidate_label": label,
                "candidate_threshold_A": threshold,
                "pass_count": pass_count,
                "total_count": len(values),
                "pass_pct": round((pass_count / len(values)) * 100.0, 1) if values else 0.0,
                "notes": (
                    "current stage6 gate"
                    if label == "current_gate"
                    else "observed band threshold candidate"
                    if label == "candidate_5.05"
                    else "recommended observed-band command family"
                    if label == "candidate_5.1"
                    else "immediately runnable gate55 fallback"
                    if label == "candidate_5.5"
                    else "round-number comparison"
                ),
            }
        )

    next_row = next(
        (
            row
            for row in target_rows
            if _text(row.get("queue_status")) in {"ready_after_previous_shard", "running", "ready_first"}
        ),
        {},
    )
    next_shard_id = _text(next_row.get("shard_id"))
    gate51_row = _find_bridge_row(throughput_bridge_payload, "throughput_preflight_tuned_gate51")
    gate55_row = _find_bridge_row(throughput_bridge_payload, "throughput_preflight_tuned_gate55")
    immediately_runnable_row = gate51_row or gate55_row
    gate51_ready = bool(gate51_row)
    gate55_ready = bool(gate55_row)
    immediately_runnable_kind = _text(immediately_runnable_row.get("command_kind"))
    immediately_runnable_threshold = 5.1 if gate51_ready else 5.5 if gate55_ready else 0.0

    next_step = (
        f"Run the {TARGET_ID} exploratory gate5.1 retry for {next_shard_id}; use gate5.1 as the immediately runnable family for the observed {recommended_threshold:.2f}A band and keep the default lane closed until the result is reviewed."
        if next_shard_id and gate51_ready
        else
        f"Run the {TARGET_ID} exploratory gate55 retry for {next_shard_id}; use gate55 as the immediately runnable proxy for the observed {recommended_threshold:.2f}A band and keep the default lane closed until the result is reviewed."
        if next_shard_id and gate55_ready
        else f"Review the {TARGET_ID} stage6 band and refresh the throughput bridge before retrying the next shard."
    )

    return {
        "summary": {
            "status": "wetlab_lbdhodh_stage6_tuning_surface_ready",
            "target_id": TARGET_ID,
            "campaign_start_shard_id": _text(observed_rows[0].get("shard_id")) if observed_rows else "",
            "next_retry_shard_id": next_shard_id,
            "observed_row_count": len(observed_rows),
            "current_gate_threshold_A": current_threshold,
            "observed_metric_name": "mean_min_distance_A",
            "observed_metric_min_A": round(min_obs, 3) if values else 0.0,
            "observed_metric_median_A": round(median_obs, 3) if values else 0.0,
            "observed_metric_mean_A": mean_obs,
            "observed_metric_max_A": round(max_obs, 3) if values else 0.0,
            "recommended_observed_threshold_A": recommended_threshold,
            "immediately_runnable_threshold_A": immediately_runnable_threshold,
            "immediately_runnable_command_kind": immediately_runnable_kind,
            "gate51_ready_now": gate51_ready,
            "gate55_ready_now": gate55_ready,
            "telemetry_fallback_applied_count": sum(
                1 for row in observed_rows if "fallback" in _text(row.get("mean_min_distance_A_source"))
            ),
            "candidate_5_0_pass_count": sum(1 for value in values if value <= 5.0),
            "candidate_5_05_pass_count": sum(1 for value in values if value <= 5.05),
            "candidate_5_1_pass_count": sum(1 for value in values if value <= 5.1),
            "candidate_5_5_pass_count": sum(1 for value in values if value <= 5.5),
            "next_required_step": next_step,
        },
        "structured": {
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "throughput_bridge_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
            "selected_gate_summary_json": _text((throughput_bridge_payload.get("structured", {}) or {}).get("preferred_summary_json")),
            "selected_gate55_summary_json": _text((throughput_bridge_payload.get("structured", {}) or {}).get("preferred_summary_json")),
        },
        "rows": candidate_rows + observed_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a DHODH-specific stage6 tuning surface from broad-screen hold rows.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--throughput-bridge-json", default=DEFAULT_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab DHODH Stage6 Tuning Surface",
        build_payload(load_json(args.execution_queue_json), load_json(args.throughput_bridge_json)),
    )


if __name__ == "__main__":
    main()
