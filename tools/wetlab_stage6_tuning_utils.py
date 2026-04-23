#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ""}:
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {None, ""}:
            return default
        return int(value)
    except Exception:
        return default


def shard_ordinal(shard_id: str) -> int:
    candidate = text(shard_id)
    if "_of_" not in candidate:
        return 0
    try:
        return int(candidate.split("_of_", 1)[0])
    except Exception:
        return 0


def shard_from_pathish(value: Any) -> str:
    candidate = text(value)
    if not candidate:
        return ""
    for part in Path(candidate).parts:
        if "_of_" in part and shard_ordinal(part) > 0:
            return part
    return candidate if shard_ordinal(candidate) > 0 else ""


def round_up(value: float, step: float = 0.05) -> float:
    if value <= 0:
        return 0.0
    return round(math.ceil(value / step) * step, 3)


def summary_paths(target_slug: str, shard_id: str) -> list[Path]:
    base = ROOT / "runs" / "wetlab_broad_screen_throughput" / target_slug / shard_id
    return [
        base / "throughput_run_summary.json",
        base / "throughput_run_gate45_summary.json",
        base / "throughput_run_gate51_summary.json",
        base / "throughput_run_gate55_summary.json",
    ]


def metric_fallback_paths(target_slug: str, shard_id: str) -> list[tuple[Path, str]]:
    base = ROOT / "runs" / "wetlab_broad_screen_throughput" / target_slug / shard_id
    return [
        (base / "throughput_run_gate45_stage4_calibration_scores.csv", "stage4_calibration_scores_mean(fallback)"),
        (base / "throughput_run_gate45_stage3_scores.csv", "stage3_scores_mean(fallback)"),
        (base / "throughput_run_gate51_stage4_calibration_scores.csv", "stage4_calibration_scores_mean(fallback)"),
        (base / "throughput_run_gate51_stage3_scores.csv", "stage3_scores_mean(fallback)"),
        (base / "throughput_run_gate55_stage4_calibration_scores.csv", "stage4_calibration_scores_mean(fallback)"),
        (base / "throughput_run_gate55_stage3_scores.csv", "stage3_scores_mean(fallback)"),
        (base / "throughput_run_stage4_calibration_scores.csv", "stage4_calibration_scores_mean(fallback)"),
        (base / "throughput_run_stage3_scores.csv", "stage3_scores_mean(fallback)"),
    ]


def load_summary(target_slug: str, shard_id: str, maybe_load_json) -> tuple[dict[str, Any], str]:
    for path in summary_paths(target_slug, shard_id):
        payload = maybe_load_json(str(path))
        if payload:
            return payload, str(path)
    return {}, str(summary_paths(target_slug, shard_id)[0])


def infer_gate_threshold(summary_path: str, stage6_payload: dict[str, Any]) -> float:
    direct = safe_float(stage6_payload.get("gate_threshold_A"))
    if direct > 0:
        return direct
    path = str(summary_path)
    if "gate45" in path:
        return 4.5
    if "gate51" in path:
        return 5.1
    if "gate55" in path:
        return 5.5
    return 2.5


def fallback_metric_from_csv(target_slug: str, shard_id: str) -> tuple[float, str]:
    for path, source in metric_fallback_paths(target_slug, shard_id):
        if not path.exists():
            continue
        values: list[float] = []
        try:
            with path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    value = safe_float((row or {}).get("mean_min_distance_A"))
                    if value > 0:
                        values.append(value)
        except Exception:
            continue
        if values:
            return round(sum(values) / len(values), 6), source
    return 0.0, ""


def find_bridge_row(throughput_bridge_payload: dict[str, Any], command_kind: str) -> dict[str, Any]:
    for row in throughput_bridge_payload.get("rows", []) or []:
        candidate = dict(row or {})
        if text(candidate.get("command_kind")) == command_kind and text(candidate.get("command")):
            return candidate
    return {}


def select_immediately_runnable_row(
    throughput_bridge_payload: dict[str, Any],
    recommended_threshold: float,
) -> tuple[dict[str, Any], float]:
    gate45_row = find_bridge_row(throughput_bridge_payload, "throughput_preflight_tuned_gate45")
    gate51_row = find_bridge_row(throughput_bridge_payload, "throughput_preflight_tuned_gate51")
    gate55_row = find_bridge_row(throughput_bridge_payload, "throughput_preflight_tuned_gate55")

    if recommended_threshold > 0 and recommended_threshold <= 4.5 and gate45_row:
        return gate45_row, 4.5
    if recommended_threshold > 0 and recommended_threshold <= 5.1 and gate51_row:
        return gate51_row, 5.1
    if recommended_threshold > 0 and recommended_threshold <= 5.5 and gate55_row:
        return gate55_row, 5.5
    if gate45_row:
        return gate45_row, 4.5
    if gate51_row:
        return gate51_row, 5.1
    if gate55_row:
        return gate55_row, 5.5
    return {}, 0.0


def candidate_rows(values: list[float], candidates: list[tuple[str, float]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, threshold in candidates:
        if threshold <= 0:
            continue
        pass_count = sum(1 for value in values if value <= threshold)
        rows.append(
            {
                "row_kind": "threshold_candidate",
                "candidate_label": label,
                "candidate_threshold_A": threshold,
                "pass_count": pass_count,
                "total_count": len(values),
                "pass_pct": round((pass_count / len(values)) * 100.0, 1) if values else 0.0,
            }
        )
    return rows


def median_float(values: list[float]) -> float:
    return float(median(values)) if values else 0.0


def build_stage6_tuning_payload(
    *,
    target_id: str,
    target_slug: str,
    status: str,
    execution_queue_payload: dict[str, Any],
    throughput_bridge_payload: dict[str, Any],
    maybe_load_json,
    candidate_thresholds: list[tuple[str, float]],
    next_step_template: str,
) -> dict[str, Any]:
    target_rows = [
        dict(row or {})
        for row in (execution_queue_payload.get("rows", []) or [])
        if text((row or {}).get("target_id")) == target_id
    ]
    target_rows.sort(key=lambda row: shard_ordinal(text(row.get("shard_id"))))

    observed_rows: list[dict[str, Any]] = []
    telemetry_fallback_applied_count = 0
    for row in target_rows:
        shard_id = text(row.get("shard_id"))
        if text(row.get("queue_status")) != "explicit_hold":
            continue
        payload, summary_path = load_summary(target_slug, shard_id, maybe_load_json)
        service = dict(payload.get("service_result", {}) or {})
        stage6 = dict((payload.get("stages", {}) or {}).get("stage6_operational_gate", {}) or {})
        failed_stage = text(service.get("failed_stage")) or text(payload.get("failed_stage"))
        if failed_stage != "stage6_operational_gate":
            continue
        observed = safe_float(stage6.get("mean_min_distance_A"))
        metric_source = text(stage6.get("mean_min_distance_A_source"))
        if observed <= 0:
            observed, metric_source = fallback_metric_from_csv(target_slug, shard_id)
            if observed > 0:
                telemetry_fallback_applied_count += 1
        if observed <= 0:
            continue
        threshold = infer_gate_threshold(summary_path, stage6)
        observed_rows.append(
            {
                "row_kind": "stage6_retry_observation",
                "target_id": target_id,
                "shard_id": shard_id,
                "queue_status": text(row.get("queue_status")),
                "service_status": text(service.get("status")),
                "error_code": text(service.get("error_code")),
                "failed_stage": failed_stage,
                "mean_min_distance_A": observed,
                "stage6_failed_metric": "mean_min_distance_A",
                "stage6_failed_metric_value": observed,
                "stage6_failed_metric_threshold": threshold,
                "stage6_failed_metric_delta": round(observed - threshold, 3),
                "mean_min_distance_A_source": metric_source,
                "min_frames_observed": safe_int(stage6.get("min_frames_observed"), 0),
                "summary_json": summary_path,
            }
        )

    observed_rows.sort(key=lambda row: shard_ordinal(text(row.get("shard_id"))))
    values = [safe_float(row.get("mean_min_distance_A")) for row in observed_rows if safe_float(row.get("mean_min_distance_A")) > 0]
    current_threshold = safe_float(observed_rows[-1].get("stage6_failed_metric_threshold"), 2.5) if observed_rows else 2.5
    min_obs = min(values) if values else 0.0
    max_obs = max(values) if values else 0.0
    median_obs = median_float(values)
    mean_obs = round(sum(values) / len(values), 3) if values else 0.0
    recommended_threshold = round_up(max_obs, 0.05) if values else 0.0

    next_row = next(
        (
            row
            for row in target_rows
            if text(row.get("queue_status")) in {"ready_after_previous_shard", "running", "ready_first"}
        ),
        {},
    )
    next_shard_id = text(next_row.get("shard_id"))
    if not next_shard_id:
        bridge_summary = dict(throughput_bridge_payload.get("summary", {}) or {})
        bridge_structured = dict(throughput_bridge_payload.get("structured", {}) or {})
        bridge_target_id = text(bridge_summary.get("target_id"))
        if bridge_target_id == target_id:
            next_shard_id = (
                shard_from_pathish(bridge_summary.get("shard_id"))
                or shard_from_pathish(bridge_structured.get("preferred_summary_json"))
                or shard_from_pathish(bridge_structured.get("preferred_summary_path"))
            )
    immediately_runnable_row, immediately_runnable_threshold = select_immediately_runnable_row(
        throughput_bridge_payload,
        recommended_threshold,
    )
    immediately_runnable_kind = text(immediately_runnable_row.get("command_kind"))

    candidate_rows_out = []
    seen_labels = set()
    all_candidates = [("current_gate", current_threshold), *candidate_thresholds]
    for row in candidate_rows(values, all_candidates):
        label = text(row.get("candidate_label"))
        if label in seen_labels:
            continue
        seen_labels.add(label)
        row["target_id"] = target_id
        candidate_rows_out.append(row)

    next_required_step = (
        next_step_template.format(
            target_id=target_id,
            shard_id=next_shard_id,
            recommended_threshold=f"{recommended_threshold:.2f}",
            immediately_runnable_threshold=f"{immediately_runnable_threshold:.1f}" if immediately_runnable_threshold else "0.0",
            command_kind=immediately_runnable_kind,
        )
        if next_shard_id and immediately_runnable_kind
        else f"Keep the {target_id} default lane closed until a tuned stage6 retry family is selected."
    )

    return {
        "summary": {
            "status": status,
            "target_id": target_id,
            "campaign_start_shard_id": text(observed_rows[0].get("shard_id")) if observed_rows else "",
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
            "gate45_ready_now": bool(find_bridge_row(throughput_bridge_payload, "throughput_preflight_tuned_gate45")),
            "gate51_ready_now": bool(find_bridge_row(throughput_bridge_payload, "throughput_preflight_tuned_gate51")),
            "gate55_ready_now": bool(find_bridge_row(throughput_bridge_payload, "throughput_preflight_tuned_gate55")),
            "telemetry_fallback_applied_count": telemetry_fallback_applied_count,
            **{
                f"{label.replace('.', '_')}_pass_count": sum(1 for value in values if value <= threshold)
                for label, threshold in candidate_thresholds
            },
            "next_required_step": next_required_step,
        },
        "rows": observed_rows + candidate_rows_out,
    }
