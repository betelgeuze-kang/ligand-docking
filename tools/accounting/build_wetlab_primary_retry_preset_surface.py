#!/usr/bin/env python3
from __future__ import annotations

import argparse
from statistics import median
from pathlib import Path
from typing import Any

from tools.wetlab_broad_screen_watch_utils import slug
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_primary_retry_preset_surface_current.md"
DEFAULT_TARGETS = ("SARS-CoV-2 Mpro", "T. cruzi PDE", "ALK2", "STK17B (DRAK2)")
DEFAULT_GUARD_LIMIT = 3


def _summary_path(target_id: str, shard_id: str, target_slug: str = "") -> Path:
    target_dir = target_slug or slug(target_id)
    return ROOT / "runs" / "wetlab_broad_screen_throughput" / target_dir / shard_id / "throughput_run_summary.json"


def _shard_sort_key(shard_id: str) -> tuple[int, str]:
    head = str(shard_id).split("_of_", 1)[0]
    try:
        return int(head), str(shard_id)
    except ValueError:
        return 0, str(shard_id)


def _failure_mode(payload: dict[str, Any]) -> str:
    service = dict(payload.get("service_result", {}) or {})
    failed_stage = str(payload.get("failed_stage", service.get("failed_stage", "")) or "").strip()
    if failed_stage == "stage1_ligand_mapping":
        return "stage1_mapping_failed"
    if failed_stage == "stage6_operational_gate":
        return "stage6_distance_gate_failed"
    return "other"


def _detail_row(row: dict[str, Any]) -> dict[str, Any]:
    target_id = str(row.get("target_id", "")).strip()
    shard_id = str(row.get("shard_id", "")).strip()
    target_slug = str(row.get("target_slug", "")).strip()
    summary_path = _summary_path(target_id, shard_id, target_slug)
    payload = maybe_load_json(str(summary_path))
    service = dict(payload.get("service_result", {}) or {})
    stage6 = dict((payload.get("stages", {}) or {}).get("stage6_operational_gate", {}) or {})
    failed_metrics = list(stage6.get("failed_metrics", []) or [])
    threshold = float((failed_metrics[0].get("threshold") if failed_metrics else stage6.get("gate_threshold_A", 0.0)) or 0.0)
    observed = float(stage6.get("mean_min_distance_A", 0.0) or 0.0)
    return {
        "target_id": target_id,
        "target_slug": target_slug or slug(target_id),
        "shard_id": shard_id,
        "summary_json": str(summary_path),
        "summary_detected": bool(payload),
        "error_code": str(service.get("error_code", "")).strip(),
        "failed_stage": str(payload.get("failed_stage", service.get("failed_stage", "")) or "").strip(),
        "failure_mode": _failure_mode(payload),
        "mean_min_distance_A": observed,
        "gate_threshold_A": threshold,
        "distance_over_threshold_A": round(observed - threshold, 3) if observed and threshold else 0.0,
    }


def _trailing_auto_hold_streak(target_rows: list[dict[str, Any]]) -> int:
    streak = 0
    for row in reversed(target_rows):
        notes = str(row.get("notes", "")).strip()
        status = str(row.get("queue_status", "")).strip()
        if status == "explicit_hold" and "auto_hold_from_primary_watcher" in notes:
            streak += 1
            continue
        break
    return streak


def _max_auto_hold_streak(target_rows: list[dict[str, Any]]) -> int:
    streak = 0
    best = 0
    for row in target_rows:
        notes = str(row.get("notes", "")).strip()
        status = str(row.get("queue_status", "")).strip()
        if status == "explicit_hold" and "auto_hold_from_primary_watcher" in notes:
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return best


def _recommended_retry_mode(stage1_count: int, stage6_count: int, trailing_streak: int, guard_limit: int) -> str:
    if stage1_count:
        return "mapping_fix_required"
    if stage6_count and trailing_streak >= guard_limit:
        return "do_not_autoadvance"
    if stage6_count:
        return "tuned_gate_candidate"
    return "manual_review"


def _guard_recommendation(trailing_streak: int, guard_limit: int) -> str:
    if trailing_streak >= guard_limit:
        return f"guard_stop_target_now_{trailing_streak}_ge_{guard_limit}"
    if trailing_streak == guard_limit - 1:
        return f"allow_one_manual_retry_then_stop_at_{guard_limit}"
    return "guard_can_remain_open_for_manual_retry"


def _target_specific_next_step(
    *,
    target_id: str,
    recommended_retry_mode: str,
    stage1_shard_id: str,
    stage6_shard_id: str,
    guard_limit: int,
) -> str:
    tuned_retry_label = "tuned gate55 manual retry lane" if target_id == "STK17B (DRAK2)" else "tuned gate preset"
    if recommended_retry_mode == "mapping_fix_required":
        shard_label = stage1_shard_id or stage6_shard_id or "representative shard"
        return (
            f"Repair stage1 ligand mapping for {target_id} and rerun {shard_label} with mapping diagnostics enabled "
            "before any further auto-start."
        )
    if recommended_retry_mode == "tuned_gate_candidate":
        shard_label = stage6_shard_id or "representative shard"
        return (
            f"Retry {target_id} on {shard_label} with the {tuned_retry_label} and keep the retry in manual-review mode "
            "until one stage6 pass is observed."
        )
    if recommended_retry_mode == "do_not_autoadvance":
        shard_label = stage6_shard_id or stage1_shard_id or "representative shard"
        return (
            f"Keep auto-advance disabled for {target_id}; review {shard_label} and only reopen the lane after a "
            f"{tuned_retry_label if stage6_shard_id else 'manual retry plan'} replaces the current {guard_limit}-hold guard."
        )
    return f"Manually inspect {target_id} retry eligibility before reopening auto-start."


def build_payload(
    execution_queue_payload: dict[str, Any],
    *,
    targets: list[str] | None = None,
    guard_limit: int = DEFAULT_GUARD_LIMIT,
) -> dict[str, Any]:
    target_set = {str(target).strip() for target in (targets or list(DEFAULT_TARGETS)) if str(target).strip()}
    queue_rows = [
        dict(row)
        for row in (execution_queue_payload.get("rows", []) or [])
        if str(row.get("target_id", "")).strip() in target_set
    ]
    grouped: dict[str, list[dict[str, Any]]] = {target_id: [] for target_id in sorted(target_set)}
    for row in queue_rows:
        grouped.setdefault(str(row.get("target_id", "")).strip(), []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: _shard_sort_key(str(row.get("shard_id", ""))))

    rollup_rows: list[dict[str, Any]] = []
    total_stage1 = 0
    total_stage6 = 0
    total_auto_hold = 0
    blocked_targets = 0

    for target_id in sorted(target_set):
        target_rows = grouped.get(target_id, [])
        auto_hold_rows = [
            row
            for row in target_rows
            if str(row.get("queue_status", "")).strip() == "explicit_hold"
            and "auto_hold_from_primary_watcher" in str(row.get("notes", "")).strip()
        ]
        detail_rows = [_detail_row(row) for row in auto_hold_rows]
        stage1_rows = [row for row in detail_rows if row["failure_mode"] == "stage1_mapping_failed"]
        stage6_rows = [row for row in detail_rows if row["failure_mode"] == "stage6_distance_gate_failed"]
        trailing_streak = _trailing_auto_hold_streak(target_rows)
        max_streak = _max_auto_hold_streak(target_rows)
        recommended_retry_mode = _recommended_retry_mode(len(stage1_rows), len(stage6_rows), trailing_streak, guard_limit)
        stage1_shard_id = stage1_rows[0]["shard_id"] if stage1_rows else ""
        stage6_shard_id = ""
        if stage6_rows:
            stage6_shard_id = max(
                stage6_rows,
                key=lambda row: (float(row.get("distance_over_threshold_A", 0.0) or 0.0), _shard_sort_key(str(row.get("shard_id", "")))),
            )["shard_id"]
        if trailing_streak >= guard_limit:
            blocked_targets += 1

        total_auto_hold += len(auto_hold_rows)
        total_stage1 += len(stage1_rows)
        total_stage6 += len(stage6_rows)

        rollup_rows.append(
            {
                "target_id": target_id,
                "auto_hold_row_count": len(auto_hold_rows),
                "stage1_mapping_failed_count": len(stage1_rows),
                "stage6_distance_gate_failed_count": len(stage6_rows),
                "trailing_auto_hold_streak_count": trailing_streak,
                "max_auto_hold_streak_count": max_streak,
                "recommended_retry_mode": recommended_retry_mode,
                "consecutive_auto_hold_guard_recommendation": _guard_recommendation(trailing_streak, guard_limit),
                "representative_stage1_mapping_failure_shard_id": stage1_shard_id,
                "representative_stage6_failure_shard_id": stage6_shard_id,
                "median_stage6_distance_over_threshold_A": round(
                    float(median(float(row.get("distance_over_threshold_A", 0.0) or 0.0) for row in stage6_rows)),
                    3,
                ) if stage6_rows else 0.0,
                "max_stage6_distance_over_threshold_A": round(
                    max((float(row.get("distance_over_threshold_A", 0.0) or 0.0) for row in stage6_rows), default=0.0),
                    3,
                ),
                "target_specific_next_step": _target_specific_next_step(
                    target_id=target_id,
                    recommended_retry_mode=recommended_retry_mode,
                    stage1_shard_id=stage1_shard_id,
                    stage6_shard_id=stage6_shard_id,
                    guard_limit=guard_limit,
                ),
            }
        )

    return {
        "summary": {
            "status": "wetlab_primary_retry_preset_surface_ready",
            "target_count": len(target_set),
            "auto_hold_row_count": total_auto_hold,
            "stage1_mapping_failed_count": total_stage1,
            "stage6_distance_gate_failed_count": total_stage6,
            "guard_limit": guard_limit,
            "guard_blocked_target_count": blocked_targets,
            "next_required_step": "Use this retry preset surface to decide whether a target should stay stopped, take a mapping fix retry, or take a tuned gate retry before reopening auto-advance.",
        },
        "structured": {
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "stage6_failure_surface_artifact": "runs/wetlab_primary_stage6_failure_surface_current.md",
        },
        "rows": rollup_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a target-level retry preset surface for repeated primary broad-screen failures.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--guard-limit", type=int, default=DEFAULT_GUARD_LIMIT)
    parser.add_argument("--target", action="append", dest="targets", default=[])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    targets = args.targets or list(DEFAULT_TARGETS)
    payload = build_payload(
        load_json(args.execution_queue_json),
        targets=targets,
        guard_limit=max(1, int(args.guard_limit)),
    )
    write_artifact(args.out_md, "Wet-Lab Primary Retry Preset Surface", payload)


if __name__ == "__main__":
    main()
