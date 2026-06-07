#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tools.wetlab_broad_screen_watch_utils import slug
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_primary_stage6_failure_surface_current.md"
DEFAULT_TARGETS = ("SARS-CoV-2 Mpro", "T. cruzi PDE", "ALK2", "STK17B (DRAK2)")


def _summary_path(target_id: str, shard_id: str, target_slug: str = "") -> Path:
    base = ROOT / "runs" / "wetlab_broad_screen_throughput" / (target_slug or slug(target_id)) / shard_id
    default_path = base / "throughput_run_summary.json"
    gate55_path = base / "throughput_run_gate55_summary.json"
    if default_path.exists():
        return default_path
    if gate55_path.exists():
        return gate55_path
    return default_path


def _summary_text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def _normalized_failed_stage(payload: dict[str, Any], service: dict[str, Any]) -> str:
    return _summary_text(payload.get("failed_stage") or service.get("failed_stage"))


def _queue_status_kind(queue_status: str) -> str:
    status = str(queue_status or "").strip()
    if status == "explicit_hold":
        return "hold"
    if "running" in status:
        return "running"
    if status.startswith("ready"):
        return "ready"
    return "other"


def _failed_metric(stage6: dict[str, Any]) -> tuple[str, float, float]:
    failed_metrics = list(stage6.get("failed_metrics", []) or [])
    if failed_metrics:
        first = dict(failed_metrics[0] or {})
        metric = _summary_text(first.get("metric")) or "mean_min_distance_A"
        value = float(first.get("value", stage6.get("mean_min_distance_A", 0.0)) or 0.0)
        threshold = float(first.get("threshold", stage6.get("gate_threshold_A", 0.0)) or 0.0)
        return metric, value, threshold
    return (
        "mean_min_distance_A",
        float(stage6.get("mean_min_distance_A", 0.0) or 0.0),
        float(stage6.get("gate_threshold_A", 0.0) or 0.0),
    )


def _stage6_row(row: dict[str, Any]) -> dict[str, Any]:
    target_id = str(row.get("target_id", "")).strip()
    shard_id = str(row.get("shard_id", "")).strip()
    target_slug = str(row.get("target_slug", "")).strip()
    summary_path = _summary_path(target_id, shard_id, target_slug)
    payload = maybe_load_json(str(summary_path))
    service = dict(payload.get("service_result", {}) or {})
    stage6 = dict((payload.get("stages", {}) or {}).get("stage6_operational_gate", {}) or {})
    stage1 = dict((payload.get("stages", {}) or {}).get("stage1_ligand_mapping", {}) or {})
    stage2 = dict((payload.get("stages", {}) or {}).get("stage2_trajectory_generation", {}) or {})
    stage3 = dict((payload.get("stages", {}) or {}).get("stage3_score_delivery", {}) or {})
    stage4 = dict((payload.get("stages", {}) or {}).get("stage4_calibration", {}) or {})
    top_level_status = _summary_text(payload.get("status"))
    top_level_error_code = _summary_text(payload.get("error_code"))
    top_level_failed_stage = _summary_text(payload.get("failed_stage"))
    service_status = _summary_text(service.get("status"))
    service_error_code = _summary_text(service.get("error_code"))
    service_failed_stage = _summary_text(service.get("failed_stage"))
    failed_stage = _normalized_failed_stage(payload, service)
    failed_metric, failed_metric_value, threshold = _failed_metric(stage6)
    observed = float(stage6.get("mean_min_distance_A", failed_metric_value) or 0.0)
    queue_status = _summary_text(row.get("queue_status"))
    queue_status_kind = _queue_status_kind(queue_status)
    summary_top_level_sparse = bool((not top_level_status and service_status) or (not top_level_error_code and service_error_code))
    watcher_consumption_state = (
        "consumed_auto_hold"
        if queue_status == "explicit_hold" and "auto_hold_from_primary_watcher" in _summary_text(row.get("notes"))
        else "summary_failed_but_queue_running"
        if queue_status_kind == "running" and failed_stage
        else "other"
    )
    return {
        "target_id": target_id,
        "shard_id": shard_id,
        "queue_status": queue_status,
        "queue_status_kind": queue_status_kind,
        "notes": _summary_text(row.get("notes")),
        "error_code": service_error_code,
        "failed_stage": failed_stage,
        "summary_detected": bool(payload),
        "summary_json": str(summary_path),
        "summary_top_level_status": top_level_status,
        "summary_top_level_error_code": top_level_error_code,
        "summary_top_level_failed_stage": top_level_failed_stage,
        "summary_service_status": service_status,
        "summary_service_error_code": service_error_code,
        "summary_service_failed_stage": service_failed_stage,
        "summary_top_level_sparse": summary_top_level_sparse,
        "service_result_present": bool(service),
        "stage1_mapping_pass": stage1.get("pass"),
        "stage6_pass": stage6.get("pass"),
        "stage6_failed_metric": failed_metric,
        "stage6_failed_metric_value": failed_metric_value,
        "stage6_failed_metric_threshold": threshold,
        "stage6_failed_metric_delta": round(failed_metric_value - threshold, 3) if failed_metric_value and threshold else 0.0,
        "mean_min_distance_A": observed,
        "mean_min_distance_A_all": float(stage6.get("mean_min_distance_A_all", observed) or observed),
        "mean_min_distance_A_source": _summary_text(stage6.get("mean_min_distance_A_source")),
        "gate_threshold_A": threshold,
        "distance_over_threshold_A": round(observed - threshold, 3) if observed and threshold else 0.0,
        "min_frames_observed": int(stage6.get("min_frames_observed", 0) or 0),
        "stage1_duration_sec": float(stage1.get("duration_sec", 0.0) or 0.0),
        "stage2_duration_sec": float(stage2.get("duration_sec", 0.0) or 0.0),
        "stage3_duration_sec": float(stage3.get("duration_sec", 0.0) or 0.0),
        "stage4_duration_sec": float(stage4.get("duration_sec", 0.0) or 0.0),
        "pipeline_runtime_sec": round(
            float(stage1.get("duration_sec", 0.0) or 0.0)
            + float(stage2.get("duration_sec", 0.0) or 0.0)
            + float(stage3.get("duration_sec", 0.0) or 0.0)
            + float(stage4.get("duration_sec", 0.0) or 0.0),
            3,
        ),
        "watcher_consumption_state": watcher_consumption_state,
        "failure_mode": (
            "stage1_mapping_failed"
            if failed_stage == "stage1_ligand_mapping"
            else "stage6_distance_gate_failed"
            if failed_stage == "stage6_operational_gate"
            else "other"
        ),
    }


def build_payload(execution_queue_payload: dict[str, Any], targets: list[str] | None = None) -> dict[str, Any]:
    target_set = {str(target).strip() for target in (targets or list(DEFAULT_TARGETS)) if str(target).strip()}
    detailed_rows: list[dict[str, Any]] = []
    for queue_row in (execution_queue_payload.get("rows", []) or []):
        target_id = str(queue_row.get("target_id", "")).strip()
        if target_id not in target_set:
            continue
        candidate = _stage6_row(dict(queue_row))
        queue_status = str(candidate.get("queue_status", "")).strip()
        notes = str(candidate.get("notes", "")).strip()
        watcher_consumed_hold = queue_status == "explicit_hold" and "auto_hold_from_primary_watcher" in notes
        pending_running_failure = str(candidate.get("queue_status_kind", "")).strip() == "running" and candidate.get("failure_mode") in {
            "stage1_mapping_failed",
            "stage6_distance_gate_failed",
        }
        if watcher_consumed_hold or pending_running_failure:
            detailed_rows.append(candidate)
    detailed_rows.sort(key=lambda row: (row["target_id"], row["shard_id"]))

    surface_row_count = len(detailed_rows)
    auto_hold_row_count = sum(1 for row in detailed_rows if row.get("watcher_consumption_state") == "consumed_auto_hold")
    watcher_pending_failure_row_count = sum(1 for row in detailed_rows if row.get("watcher_consumption_state") == "summary_failed_but_queue_running")
    sparse_top_level_row_count = sum(1 for row in detailed_rows if bool(row.get("summary_top_level_sparse")))
    stage1_mapping_failed = sum(1 for row in detailed_rows if row["failure_mode"] == "stage1_mapping_failed")
    stage6_failed = sum(1 for row in detailed_rows if row["failure_mode"] == "stage6_distance_gate_failed")
    max_stage6_delta = max((float(row.get("distance_over_threshold_A", 0.0) or 0.0) for row in detailed_rows if row["failure_mode"] == "stage6_distance_gate_failed"), default=0.0)

    rollup_rows: list[dict[str, Any]] = []
    for target_id in sorted(target_set):
        target_rows = [row for row in detailed_rows if row["target_id"] == target_id]
        stage1_rows = [row for row in target_rows if row["failure_mode"] == "stage1_mapping_failed"]
        stage6_rows = [row for row in target_rows if row["failure_mode"] == "stage6_distance_gate_failed"]
        pending_rows = [row for row in target_rows if row.get("watcher_consumption_state") == "summary_failed_but_queue_running"]
        sparse_rows = [row for row in target_rows if bool(row.get("summary_top_level_sparse"))]
        rollup_rows.append(
            {
                "target_id": target_id,
                "surface_row_count": len(target_rows),
                "auto_hold_row_count": len([row for row in target_rows if row.get("watcher_consumption_state") == "consumed_auto_hold"]),
                "watcher_pending_failure_row_count": len(pending_rows),
                "sparse_top_level_row_count": len(sparse_rows),
                "stage1_mapping_failed_count": len(stage1_rows),
                "stage6_failed_count": len(stage6_rows),
                "max_distance_over_threshold_A": round(max((float(row.get("distance_over_threshold_A", 0.0) or 0.0) for row in stage6_rows), default=0.0), 3),
                "median_stage6_metric_delta_A": round(
                    sorted(float(row.get("stage6_failed_metric_delta", 0.0) or 0.0) for row in stage6_rows)[len(stage6_rows) // 2], 3
                ) if stage6_rows else 0.0,
                "median_observed_mean_min_distance_A": round(
                    sorted(float(row.get("mean_min_distance_A", 0.0) or 0.0) for row in stage6_rows)[len(stage6_rows) // 2], 3
                ) if stage6_rows else 0.0,
                "representative_failed_metric_names": ", ".join(
                    sorted(
                        {
                            str(row.get("stage6_failed_metric", "")).strip()
                            for row in stage6_rows
                            if str(row.get("stage6_failed_metric", "")).strip()
                        }
                    )
                ),
                "representative_mean_min_distance_source": next(
                    (
                        str(row.get("mean_min_distance_A_source", "")).strip()
                        for row in stage6_rows
                        if str(row.get("mean_min_distance_A_source", "")).strip()
                    ),
                    "",
                ),
                "median_pipeline_runtime_sec": round(
                    sorted(float(row.get("pipeline_runtime_sec", 0.0) or 0.0) for row in stage6_rows)[len(stage6_rows) // 2], 3
                ) if stage6_rows else 0.0,
                "recommended_action": (
                    "watcher reconciliation required before continuing"
                    if pending_rows
                    else
                    "fix stage1 mapping contract before further auto-start"
                    if stage1_rows
                    else "split or relax stage6 gate policy before continuing"
                    if stage6_rows
                    else "manual review"
                ),
            }
        )

    return {
        "summary": {
            "status": "wetlab_primary_stage6_failure_surface_ready",
            "target_count": len(target_set),
            "surface_row_count": surface_row_count,
            "auto_hold_row_count": auto_hold_row_count,
            "watcher_pending_failure_row_count": watcher_pending_failure_row_count,
            "sparse_top_level_row_count": sparse_top_level_row_count,
            "stage1_mapping_failed_count": stage1_mapping_failed,
            "stage6_failed_count": stage6_failed,
            "max_stage6_distance_over_threshold_A": round(max_stage6_delta, 3),
            "next_required_step": "Use this surface to separate consumed auto-holds from watcher-pending failures, and decide whether stage1 mapping or stage6 gate needs a target-specific preset before resuming.",
        },
        "structured": {
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
        },
        "rows": rollup_rows + detailed_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a target-level surface for repeated primary stage6 gate failures.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--target", action="append", dest="targets", default=[])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    targets = args.targets or list(DEFAULT_TARGETS)
    write_artifact(
        args.out_md,
        "Wet-Lab Primary Stage6 Failure Surface",
        build_payload(load_json(args.execution_queue_json), targets=targets),
    )


if __name__ == "__main__":
    main()
