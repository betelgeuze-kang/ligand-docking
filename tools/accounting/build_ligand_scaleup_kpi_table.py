#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DOMAIN_TARGETS = {
    "gpcr": {
        "target_100k_wall_min_upper": 25.0,
        "target_1m_wall_hr_upper": 3.0,
    },
    "ion_channel": {
        "target_100k_wall_min_upper": 50.0,
        "target_1m_wall_hr_upper": 10.0,
    },
    "kinase": {
        "target_100k_wall_min_upper": 15.0,
        "target_1m_wall_hr_upper": 2.0,
    },
    "protease": {
        "target_100k_wall_min_upper": 15.0,
        "target_1m_wall_hr_upper": 2.0,
    },
}


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_path(path_str: str) -> Path:
    path = Path(str(path_str))
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _resolve_packaged_copy(path_str: str, task: Dict[str, Any]) -> Optional[Path]:
    requested = _resolve_path(path_str)
    requested_name = requested.name
    for copied_file in task.get("copied_files", []):
        if not isinstance(copied_file, dict):
            continue
        src = _resolve_path(str(copied_file.get("src", "")))
        dst = _resolve_path(str(copied_file.get("dst", "")))
        if src == requested or src.name == requested_name:
            if dst.exists():
                return dst
    return None


def _resolve_task_artifact_path(path_str: str, task: Dict[str, Any]) -> tuple[Path, str]:
    path = _resolve_path(path_str)
    if path.exists():
        return path, "original_path"
    packaged_copy = _resolve_packaged_copy(path_str, task)
    if packaged_copy is not None:
        return packaged_copy, "packaged_copy"
    return path, "missing"


def _safe_sec(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _has_positive_number(value: Any) -> bool:
    try:
        if value is None:
            return False
        return float(value) > 0.0
    except (TypeError, ValueError):
        return False


def _project_seconds(sec_at_10k: float, library_size: int) -> float:
    return float(sec_at_10k) * (float(library_size) / 10_000.0)


def _target_upper(domain: str, key: str) -> Optional[float]:
    value = DOMAIN_TARGETS.get(str(domain), {}).get(str(key))
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _gap_to_target(projected_value: float, target_upper: Optional[float]) -> Optional[float]:
    if target_upper is None:
        return None
    return float(projected_value) - float(target_upper)


def _required_speedup_to_target(projected_value: float, target_upper: Optional[float]) -> Optional[float]:
    if target_upper is None or float(projected_value) <= 0.0:
        return None
    return float(projected_value) / float(target_upper)


def _max_optional(values: List[Optional[float]]) -> Optional[float]:
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return float(max(present))


def _classify_priority(stage2_share: float, stage2_rows_per_sec: float) -> str:
    if stage2_share >= 0.88 or stage2_rows_per_sec < 30.0:
        return "P0"
    if stage2_share >= 0.80 or stage2_rows_per_sec < 80.0:
        return "P1"
    return "P2"


def _recommended_levers(stage2_share: float, domain: str) -> str:
    levers: List[str] = []
    if stage2_share >= 0.80:
        levers.extend(["adaptive_frame_budget", "target_specific_preset"])
    if domain in {"gpcr", "ion_channel"}:
        levers.append("artifact_light_prod_mode")
    if domain == "ion_channel":
        levers.append("persistent_stage2_worker")
    if domain == "kinase":
        levers.append("batch_autotune_expansion")
    if not levers:
        levers.append("stage3_slim_path")
    seen: List[str] = []
    for lever in levers:
        if lever not in seen:
            seen.append(lever)
    return ",".join(seen)


def _extract_stage_duration(stages: Dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = stages.get(key, {})
        if isinstance(value, dict):
            duration = value.get("duration_sec")
            if duration is not None:
                return _safe_sec(duration)
    return 0.0


def _missing_artifact_row(
    *,
    set_id: str,
    task: Dict[str, Any],
    missing_artifact_path: Path,
    missing_artifact_kind: str,
) -> Dict[str, Any]:
    domain = str(task.get("domain", ""))
    target_100k_wall_min_upper = _target_upper(domain, "target_100k_wall_min_upper")
    target_1m_wall_hr_upper = _target_upper(domain, "target_1m_wall_hr_upper")
    return {
        "set_id": set_id,
        "task_id": str(task.get("task_id", "")),
        "domain": domain,
        "profile_json": str(task.get("profile_json", "")),
        "pass": False,
        "raw_pass": False,
        "total_latency_sec_10k": 0.0,
        "stage2_trajectory_sec_10k": 0.0,
        "stage3_backmapping_sec_10k": 0.0,
        "stage4_calibration_sec_10k": 0.0,
        "stage45_integrity_sec_10k": 0.0,
        "stage5_ranking_sec_10k": 0.0,
        "stage2_share_pct": 0.0,
        "queue_rate_stage2_rows_per_sec": 0.0,
        "queue_rate_stage3_rows_per_sec": 0.0,
        "has_measured_total_latency": False,
        "has_stage2_queue_rate": False,
        "has_stage3_queue_rate": False,
        "total_latency_source": "missing_artifact",
        "timing_coverage_tier": "missing_artifact",
        "missing_artifact": True,
        "missing_artifact_kind": missing_artifact_kind,
        "missing_artifact_path": str(missing_artifact_path),
        "artifact_resolution_source": "missing",
        "wrapper_summary_resolution_source": "missing",
        "pipeline_summary_resolution_source": "missing",
        "projected_100k_wall_min": 0.0,
        "projected_1m_wall_hr": 0.0,
        "projected_100k_wall_min_at_2x": 0.0,
        "projected_1m_wall_hr_at_2x": 0.0,
        "projected_100k_wall_min_at_3x": 0.0,
        "projected_1m_wall_hr_at_3x": 0.0,
        "target_100k_wall_min_upper": target_100k_wall_min_upper,
        "target_1m_wall_hr_upper": target_1m_wall_hr_upper,
        "gap_to_target_100k_min": None,
        "gap_to_target_1m_hr": None,
        "required_speedup_to_target_100k": None,
        "required_speedup_to_target_1m": None,
        "max_required_speedup_to_target": None,
        "target_stage2_rows_per_sec_2x": 0.0,
        "target_stage2_rows_per_sec_3x": 0.0,
        "speedpack_priority": "blocked",
        "recommended_levers": f"refresh_missing_artifact:{missing_artifact_kind}",
    }


def _classify_timing_coverage(
    *,
    has_measured_total_latency: bool,
    has_stage2_queue_rate: bool,
    has_stage3_queue_rate: bool,
) -> str:
    if has_measured_total_latency and has_stage2_queue_rate and has_stage3_queue_rate:
        return "measured_full"
    if has_measured_total_latency and (has_stage2_queue_rate or has_stage3_queue_rate):
        return "measured_partial"
    if has_measured_total_latency:
        return "measured_latency_only"
    if has_stage2_queue_rate or has_stage3_queue_rate:
        return "derived_partial"
    return "derived_only"


def _annotate_pacing_ranks(rows: List[Dict[str, Any]]) -> None:
    ranked_rows = sorted(rows, key=lambda item: float(item["projected_1m_wall_hr"]), reverse=True)
    domain_counts: Dict[str, int] = {}
    for index, row in enumerate(ranked_rows, start=1):
        domain = str(row.get("domain", ""))
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        row["pacing_rank_1m"] = index
        row["domain_pacing_rank_1m"] = domain_counts[domain]
        row["is_global_pacing_item"] = index == 1
        row["is_domain_pacing_item"] = domain_counts[domain] == 1


def _build_rows(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for set_payload in summary.get("sets", []):
        set_id = str(set_payload.get("set_id", ""))
        if set_id == "set3_operational_smoke":
            continue
        for task in set_payload.get("tasks", []):
            if str(task.get("kind", "")) != "ligand_stress":
                continue
            wrapper_summary_path, wrapper_resolution_source = _resolve_task_artifact_path(
                str(task.get("summary_json", "")), task
            )
            if not wrapper_summary_path.exists():
                rows.append(
                    _missing_artifact_row(
                        set_id=set_id,
                        task=task,
                        missing_artifact_path=wrapper_summary_path,
                        missing_artifact_kind="wrapper_summary_json",
                    )
                )
                continue
            wrapper_summary = _load_json(wrapper_summary_path)
            run_records = wrapper_summary.get("runs", [])
            if not run_records:
                rows.append(
                    _missing_artifact_row(
                        set_id=set_id,
                        task=task,
                        missing_artifact_path=wrapper_summary_path,
                        missing_artifact_kind="wrapper_summary_runs",
                    )
                )
                continue
            run_record = dict(run_records[0])
            raw_summary_path, pipeline_resolution_source = _resolve_task_artifact_path(
                str(run_record.get("summary_json", "")), task
            )
            if not raw_summary_path.exists():
                rows.append(
                    _missing_artifact_row(
                        set_id=set_id,
                        task=task,
                        missing_artifact_path=raw_summary_path,
                        missing_artifact_kind="pipeline_summary_json",
                    )
                )
                continue
            raw_summary = _load_json(raw_summary_path)
            stages = raw_summary.get("stages", {})

            stage2_sec = _extract_stage_duration(stages, "stage2_trajectory_generation")
            stage3_sec = _extract_stage_duration(stages, "stage3_backmapping_scoring")
            stage4_sec = _extract_stage_duration(stages, "stage4_calibration")
            stage45_sec = _extract_stage_duration(stages, "stage45_eval_integrity", "stage45_integrity")
            stage5_sec = _extract_stage_duration(stages, "stage5_ranking_eval", "stage5_ranking")
            has_measured_total_latency = _has_positive_number(run_record.get("sla_total_latency_sec"))
            total_latency_sec = _safe_sec(run_record.get("sla_total_latency_sec"))
            if total_latency_sec <= 0.0:
                total_latency_sec = stage2_sec + stage3_sec + stage4_sec + stage45_sec + stage5_sec
            total_latency_source = "sla_total_latency_sec" if has_measured_total_latency else "recomputed_stage_sum"
            stage2_share = (stage2_sec / total_latency_sec) if total_latency_sec > 0.0 else 0.0
            has_stage2_queue_rate = _has_positive_number(run_record.get("sla_queue_rate_stage2_rows_per_sec"))
            has_stage3_queue_rate = _has_positive_number(run_record.get("sla_queue_rate_stage3_rows_per_sec"))
            stage2_rows_per_sec = _safe_sec(run_record.get("sla_queue_rate_stage2_rows_per_sec"))
            stage3_rows_per_sec = _safe_sec(run_record.get("sla_queue_rate_stage3_rows_per_sec"))
            priority = _classify_priority(stage2_share, stage2_rows_per_sec)
            domain = str(task.get("domain", ""))
            projected_100k_wall_min = _project_seconds(total_latency_sec, 100_000) / 60.0
            projected_1m_wall_hr = _project_seconds(total_latency_sec, 1_000_000) / 3600.0
            target_100k_wall_min_upper = _target_upper(domain, "target_100k_wall_min_upper")
            target_1m_wall_hr_upper = _target_upper(domain, "target_1m_wall_hr_upper")
            required_speedup_to_target_100k = _required_speedup_to_target(projected_100k_wall_min, target_100k_wall_min_upper)
            required_speedup_to_target_1m = _required_speedup_to_target(projected_1m_wall_hr, target_1m_wall_hr_upper)
            timing_coverage_tier = _classify_timing_coverage(
                has_measured_total_latency=has_measured_total_latency,
                has_stage2_queue_rate=has_stage2_queue_rate,
                has_stage3_queue_rate=has_stage3_queue_rate,
            )

            row = {
                "set_id": set_id,
                "task_id": str(task.get("task_id", "")),
                "domain": domain,
                "profile_json": str(task.get("profile_json", "")),
                "pass": bool(task.get("pass", False)),
                "raw_pass": bool(task.get("raw_pass", False)),
                "total_latency_sec_10k": total_latency_sec,
                "stage2_trajectory_sec_10k": stage2_sec,
                "stage3_backmapping_sec_10k": stage3_sec,
                "stage4_calibration_sec_10k": stage4_sec,
                "stage45_integrity_sec_10k": stage45_sec,
                "stage5_ranking_sec_10k": stage5_sec,
                "stage2_share_pct": stage2_share * 100.0,
                "queue_rate_stage2_rows_per_sec": stage2_rows_per_sec,
                "queue_rate_stage3_rows_per_sec": stage3_rows_per_sec,
                "has_measured_total_latency": has_measured_total_latency,
                "has_stage2_queue_rate": has_stage2_queue_rate,
                "has_stage3_queue_rate": has_stage3_queue_rate,
                "total_latency_source": total_latency_source,
                "timing_coverage_tier": timing_coverage_tier,
                "artifact_resolution_source": (
                    "packaged_copy"
                    if "packaged_copy" in {wrapper_resolution_source, pipeline_resolution_source}
                    else "original_path"
                ),
                "wrapper_summary_resolution_source": wrapper_resolution_source,
                "pipeline_summary_resolution_source": pipeline_resolution_source,
                "projected_100k_wall_min": projected_100k_wall_min,
                "projected_1m_wall_hr": projected_1m_wall_hr,
                "projected_100k_wall_min_at_2x": _project_seconds(total_latency_sec / 2.0, 100_000) / 60.0,
                "projected_1m_wall_hr_at_2x": _project_seconds(total_latency_sec / 2.0, 1_000_000) / 3600.0,
                "projected_100k_wall_min_at_3x": _project_seconds(total_latency_sec / 3.0, 100_000) / 60.0,
                "projected_1m_wall_hr_at_3x": _project_seconds(total_latency_sec / 3.0, 1_000_000) / 3600.0,
                "target_100k_wall_min_upper": target_100k_wall_min_upper,
                "target_1m_wall_hr_upper": target_1m_wall_hr_upper,
                "gap_to_target_100k_min": _gap_to_target(projected_100k_wall_min, target_100k_wall_min_upper),
                "gap_to_target_1m_hr": _gap_to_target(projected_1m_wall_hr, target_1m_wall_hr_upper),
                "required_speedup_to_target_100k": required_speedup_to_target_100k,
                "required_speedup_to_target_1m": required_speedup_to_target_1m,
                "max_required_speedup_to_target": _max_optional(
                    [required_speedup_to_target_100k, required_speedup_to_target_1m]
                ),
                "target_stage2_rows_per_sec_2x": stage2_rows_per_sec * 2.0,
                "target_stage2_rows_per_sec_3x": stage2_rows_per_sec * 3.0,
                "speedpack_priority": priority,
                "recommended_levers": _recommended_levers(stage2_share, domain),
            }
            rows.append(row)
    _annotate_pacing_ranks(rows)
    rows.sort(key=lambda item: (-float(item["stage2_share_pct"]), float(item["queue_rate_stage2_rows_per_sec"])))
    return rows


def _build_coverage_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    row_count = int(len(rows))
    if row_count <= 0:
        return {
            "measured_total_latency_count": 0,
            "measured_total_latency_pct": 0.0,
            "stage2_queue_rate_count": 0,
            "stage2_queue_rate_pct": 0.0,
            "stage3_queue_rate_count": 0,
            "stage3_queue_rate_pct": 0.0,
            "planning_ready_count": 0,
            "planning_ready_pct": 0.0,
            "missing_artifact_count": 0,
            "missing_artifact_pct": 0.0,
            "timing_source_counts": {},
            "timing_coverage_tier_counts": {},
        }
    measured_total_latency_count = sum(1 for row in rows if bool(row.get("has_measured_total_latency", False)))
    stage2_queue_rate_count = sum(1 for row in rows if bool(row.get("has_stage2_queue_rate", False)))
    stage3_queue_rate_count = sum(1 for row in rows if bool(row.get("has_stage3_queue_rate", False)))
    planning_ready_count = sum(
        1
        for row in rows
        if bool(row.get("has_measured_total_latency", False))
        and bool(row.get("has_stage2_queue_rate", False))
        and bool(row.get("has_stage3_queue_rate", False))
    )
    missing_artifact_count = sum(1 for row in rows if bool(row.get("missing_artifact", False)))
    timing_source_counts: Dict[str, int] = {}
    timing_coverage_tier_counts: Dict[str, int] = {}
    for row in rows:
        timing_source = str(row.get("total_latency_source", ""))
        timing_source_counts[timing_source] = timing_source_counts.get(timing_source, 0) + 1
        tier = str(row.get("timing_coverage_tier", ""))
        timing_coverage_tier_counts[tier] = timing_coverage_tier_counts.get(tier, 0) + 1
    return {
        "measured_total_latency_count": int(measured_total_latency_count),
        "measured_total_latency_pct": (float(measured_total_latency_count) / float(row_count)) * 100.0,
        "stage2_queue_rate_count": int(stage2_queue_rate_count),
        "stage2_queue_rate_pct": (float(stage2_queue_rate_count) / float(row_count)) * 100.0,
        "stage3_queue_rate_count": int(stage3_queue_rate_count),
        "stage3_queue_rate_pct": (float(stage3_queue_rate_count) / float(row_count)) * 100.0,
        "planning_ready_count": int(planning_ready_count),
        "planning_ready_pct": (float(planning_ready_count) / float(row_count)) * 100.0,
        "missing_artifact_count": int(missing_artifact_count),
        "missing_artifact_pct": (float(missing_artifact_count) / float(row_count)) * 100.0,
        "timing_source_counts": timing_source_counts,
        "timing_coverage_tier_counts": timing_coverage_tier_counts,
    }


def _build_domain_rollups(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        domain = str(row.get("domain", ""))
        grouped.setdefault(domain, []).append(row)

    rollups: List[Dict[str, Any]] = []
    for domain, domain_rows in grouped.items():
        df = pd.DataFrame(domain_rows)
        pacing_row = df.sort_values("projected_1m_wall_hr", ascending=False).iloc[0]
        priority_counts = {
            str(k): int(v)
            for k, v in df["speedpack_priority"].value_counts(dropna=False).sort_index().items()
        }
        coverage_tier_counts = {
            str(k): int(v)
            for k, v in df["timing_coverage_tier"].value_counts(dropna=False).sort_index().items()
        }
        target_band = DOMAIN_TARGETS.get(domain, {})
        target_100k_upper = target_band.get("target_100k_wall_min_upper")
        target_1m_upper = target_band.get("target_1m_wall_hr_upper")
        pacing_100k = float(pacing_row["projected_100k_wall_min"])
        pacing_1m = float(pacing_row["projected_1m_wall_hr"])
        rollups.append(
            {
                "domain": domain,
                "task_count": int(len(df)),
                "pass_count": int(df["pass"].astype(bool).sum()),
                "raw_pass_count": int(df["raw_pass"].astype(bool).sum()),
                "planning_ready_count": int(
                    (
                        df["has_measured_total_latency"].astype(bool)
                        & df["has_stage2_queue_rate"].astype(bool)
                        & df["has_stage3_queue_rate"].astype(bool)
                    ).sum()
                ),
                "measured_total_latency_pct": float(df["has_measured_total_latency"].astype(bool).mean() * 100.0),
                "stage2_queue_rate_pct": float(df["has_stage2_queue_rate"].astype(bool).mean() * 100.0),
                "stage3_queue_rate_pct": float(df["has_stage3_queue_rate"].astype(bool).mean() * 100.0),
                "mean_stage2_share_pct": float(df["stage2_share_pct"].mean()),
                "mean_stage2_rows_per_sec": float(df["queue_rate_stage2_rows_per_sec"].mean()),
                "min_stage2_rows_per_sec": float(df["queue_rate_stage2_rows_per_sec"].min()),
                "mean_projected_100k_wall_min": float(df["projected_100k_wall_min"].mean()),
                "mean_projected_1m_wall_hr": float(df["projected_1m_wall_hr"].mean()),
                "max_projected_100k_wall_min": float(df["projected_100k_wall_min"].max()),
                "max_projected_1m_wall_hr": float(df["projected_1m_wall_hr"].max()),
                "priority_counts": priority_counts,
                "coverage_tier_counts": coverage_tier_counts,
                "pacing_task_id": str(pacing_row["task_id"]),
                "pacing_set_id": str(pacing_row["set_id"]),
                "pacing_priority": str(pacing_row["speedpack_priority"]),
                "pacing_timing_coverage_tier": str(pacing_row["timing_coverage_tier"]),
                "target_100k_wall_min_upper": float(target_100k_upper) if isinstance(target_100k_upper, float) else None,
                "target_1m_wall_hr_upper": float(target_1m_upper) if isinstance(target_1m_upper, float) else None,
                "pacing_gap_to_target_100k_min": None
                if target_100k_upper is None
                else float(pacing_100k - float(target_100k_upper)),
                "pacing_gap_to_target_1m_hr": None
                if target_1m_upper is None
                else float(pacing_1m - float(target_1m_upper)),
                "pacing_required_speedup_to_target_100k": _required_speedup_to_target(pacing_100k, target_100k_upper),
                "pacing_required_speedup_to_target_1m": _required_speedup_to_target(pacing_1m, target_1m_upper),
                "pacing_max_required_speedup_to_target": _max_optional(
                    [
                        _required_speedup_to_target(pacing_100k, target_100k_upper),
                        _required_speedup_to_target(pacing_1m, target_1m_upper),
                    ]
                ),
            }
        )
    rollups.sort(key=lambda item: float(item["max_projected_1m_wall_hr"]), reverse=True)
    return rollups


def _build_pacing_items(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    pacing_rows = sorted(rows, key=lambda item: float(item["projected_1m_wall_hr"]), reverse=True)[:limit]
    return [
        {
            "pacing_rank_1m": int(row.get("pacing_rank_1m", 0)),
            "task_id": str(row.get("task_id", "")),
            "set_id": str(row.get("set_id", "")),
            "domain": str(row.get("domain", "")),
            "speedpack_priority": str(row.get("speedpack_priority", "")),
            "timing_coverage_tier": str(row.get("timing_coverage_tier", "")),
            "projected_100k_wall_min": float(row.get("projected_100k_wall_min", 0.0)),
            "projected_1m_wall_hr": float(row.get("projected_1m_wall_hr", 0.0)),
            "max_required_speedup_to_target": row.get("max_required_speedup_to_target"),
            "stage2_share_pct": float(row.get("stage2_share_pct", 0.0)),
            "queue_rate_stage2_rows_per_sec": float(row.get("queue_rate_stage2_rows_per_sec", 0.0)),
        }
        for row in pacing_rows
    ]


def _build_target_gap_items(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    ranked = [
        row for row in rows if isinstance(row.get("max_required_speedup_to_target"), (int, float))
    ]
    ranked.sort(key=lambda item: float(item["max_required_speedup_to_target"]), reverse=True)
    return [
        {
            "task_id": str(row.get("task_id", "")),
            "set_id": str(row.get("set_id", "")),
            "domain": str(row.get("domain", "")),
            "speedpack_priority": str(row.get("speedpack_priority", "")),
            "timing_coverage_tier": str(row.get("timing_coverage_tier", "")),
            "projected_100k_wall_min": float(row.get("projected_100k_wall_min", 0.0)),
            "projected_1m_wall_hr": float(row.get("projected_1m_wall_hr", 0.0)),
            "required_speedup_to_target_100k": row.get("required_speedup_to_target_100k"),
            "required_speedup_to_target_1m": row.get("required_speedup_to_target_1m"),
            "max_required_speedup_to_target": float(row.get("max_required_speedup_to_target", 0.0)),
        }
        for row in ranked[:limit]
    ]


def _build_summary(rows: List[Dict[str, Any]], freeze: Dict[str, Any]) -> Dict[str, Any]:
    df = pd.DataFrame(rows)
    if df.empty:
        return {
            "bundle_tag": str(freeze.get("bundle_tag", "")),
            "row_count": 0,
            "mean_stage2_share_pct": 0.0,
            "mean_total_latency_sec_10k": 0.0,
            "mean_projected_100k_wall_min": 0.0,
            "mean_projected_1m_wall_hr": 0.0,
            "mean_max_required_speedup_to_target": None,
            "priority_counts": {},
            "coverage_summary": _build_coverage_summary(rows),
            "domain_rollups": [],
            "pacing_items": [],
            "target_gap_items": [],
        }
    priority_counts = {
        str(k): int(v)
        for k, v in df["speedpack_priority"].value_counts(dropna=False).sort_index().items()
    }
    slowest = df.sort_values("projected_1m_wall_hr", ascending=False).iloc[0]
    coverage_summary = _build_coverage_summary(rows)
    domain_rollups = _build_domain_rollups(rows)
    speedup_series = pd.to_numeric(
        df.get("max_required_speedup_to_target", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()
    return {
        "bundle_tag": str(freeze.get("bundle_tag", "")),
        "run_root": str(freeze.get("run_root", "")),
        "row_count": int(len(df)),
        "mean_stage2_share_pct": float(df["stage2_share_pct"].mean()),
        "mean_total_latency_sec_10k": float(df["total_latency_sec_10k"].mean()),
        "mean_projected_100k_wall_min": float(df["projected_100k_wall_min"].mean()),
        "mean_projected_1m_wall_hr": float(df["projected_1m_wall_hr"].mean()),
        "mean_max_required_speedup_to_target": float(speedup_series.mean()) if not speedup_series.empty else None,
        "priority_counts": priority_counts,
        "coverage_summary": coverage_summary,
        "domain_rollups": domain_rollups,
        "pacing_items": _build_pacing_items(rows),
        "target_gap_items": _build_target_gap_items(rows),
        "slowest_task_at_1m": {
            "task_id": str(slowest["task_id"]),
            "domain": str(slowest["domain"]),
            "projected_1m_wall_hr": float(slowest["projected_1m_wall_hr"]),
            "stage2_share_pct": float(slowest["stage2_share_pct"]),
            "timing_coverage_tier": str(slowest["timing_coverage_tier"]),
        },
        "recommended_order": [
            "adaptive_frame_budget",
            "target_specific_preset",
            "artifact_light_prod_mode",
            "persistent_stage2_worker",
            "stage3_slim_path",
        ],
    }


def _write_md(path: Path, payload: Dict[str, Any]) -> None:
    summary = payload.get("summary", {})
    rows = payload.get("rows", [])
    coverage_summary = summary.get("coverage_summary", {})
    domain_rollups = summary.get("domain_rollups", [])
    pacing_items = summary.get("pacing_items", [])
    target_gap_items = summary.get("target_gap_items", [])
    lines: List[str] = []
    lines.append("# Ligand Scale-Up KPI Table")
    lines.append("")
    lines.append(f"- generated_at_local: `{payload.get('generated_at_local')}`")
    lines.append(f"- bundle_tag: `{summary.get('bundle_tag')}`")
    lines.append(f"- row_count: `{summary.get('row_count')}`")
    lines.append(f"- mean_stage2_share_pct: `{summary.get('mean_stage2_share_pct'):.2f}`")
    lines.append(f"- mean_projected_100k_wall_min: `{summary.get('mean_projected_100k_wall_min'):.2f}`")
    lines.append(f"- mean_projected_1m_wall_hr: `{summary.get('mean_projected_1m_wall_hr'):.2f}`")
    mean_speedup = summary.get("mean_max_required_speedup_to_target")
    lines.append(
        "- mean_max_required_speedup_to_target: `"
        + ("n/a" if mean_speedup is None else f"{float(mean_speedup):.2f}x")
        + "`"
    )
    lines.append(f"- priority_counts: `{summary.get('priority_counts')}`")
    lines.append(
        f"- planning_ready_count: `{coverage_summary.get('planning_ready_count', 0)}`"
        f" / `{summary.get('row_count', 0)}`"
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    slowest = summary.get("slowest_task_at_1m", {})
    lines.append(
        f"- slowest_task_at_1m: `{slowest.get('task_id')}` "
        f"(`{slowest.get('domain')}`, `{float(slowest.get('projected_1m_wall_hr', 0.0)):.2f}h`, "
        f"`{slowest.get('timing_coverage_tier', '')}`)"
    )
    lines.append(
        "- recommended_order: `"
        + " -> ".join(str(x) for x in summary.get("recommended_order", []))
        + "`"
    )
    lines.append("")
    lines.append("## Coverage")
    lines.append("")
    lines.append(
        f"- measured_total_latency: `{coverage_summary.get('measured_total_latency_count', 0)}`"
        f" / `{summary.get('row_count', 0)}`"
        f" (`{float(coverage_summary.get('measured_total_latency_pct', 0.0)):.2f}%`)"
    )
    lines.append(
        f"- stage2_queue_rate: `{coverage_summary.get('stage2_queue_rate_count', 0)}`"
        f" / `{summary.get('row_count', 0)}`"
        f" (`{float(coverage_summary.get('stage2_queue_rate_pct', 0.0)):.2f}%`)"
    )
    lines.append(
        f"- stage3_queue_rate: `{coverage_summary.get('stage3_queue_rate_count', 0)}`"
        f" / `{summary.get('row_count', 0)}`"
        f" (`{float(coverage_summary.get('stage3_queue_rate_pct', 0.0)):.2f}%`)"
    )
    lines.append(
        f"- planning_ready: `{coverage_summary.get('planning_ready_count', 0)}`"
        f" / `{summary.get('row_count', 0)}`"
        f" (`{float(coverage_summary.get('planning_ready_pct', 0.0)):.2f}%`)"
    )
    lines.append(
        f"- missing_artifact: `{coverage_summary.get('missing_artifact_count', 0)}`"
        f" / `{summary.get('row_count', 0)}`"
        f" (`{float(coverage_summary.get('missing_artifact_pct', 0.0)):.2f}%`)"
    )
    lines.append(f"- timing_source_counts: `{coverage_summary.get('timing_source_counts', {})}`")
    lines.append(f"- timing_coverage_tier_counts: `{coverage_summary.get('timing_coverage_tier_counts', {})}`")
    lines.append("")
    lines.append("## Domain Rollups")
    lines.append("")
    lines.append(
        "| domain | tasks | pacing task | pacing priority | pacing coverage | mean 100k(min) | max 100k(min) | mean 1M(hr) | max 1M(hr) | target gap 100k(min) | target gap 1M(hr) | planning ready |"
    )
    lines.append(
        "| --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    for rollup in domain_rollups:
        gap_100k = rollup.get("pacing_gap_to_target_100k_min")
        gap_1m = rollup.get("pacing_gap_to_target_1m_hr")
        lines.append(
            "| "
            + " | ".join(
                [
                    str(rollup.get("domain", "")),
                    str(int(rollup.get("task_count", 0))),
                    str(rollup.get("pacing_task_id", "")),
                    str(rollup.get("pacing_priority", "")),
                    str(rollup.get("pacing_timing_coverage_tier", "")),
                    f"{float(rollup.get('mean_projected_100k_wall_min', 0.0)):.2f}",
                    f"{float(rollup.get('max_projected_100k_wall_min', 0.0)):.2f}",
                    f"{float(rollup.get('mean_projected_1m_wall_hr', 0.0)):.2f}",
                    f"{float(rollup.get('max_projected_1m_wall_hr', 0.0)):.2f}",
                    "n/a" if gap_100k is None else f"{float(gap_100k):.2f}",
                    "n/a" if gap_1m is None else f"{float(gap_1m):.2f}",
                    str(int(rollup.get("planning_ready_count", 0))),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Pacing Items")
    lines.append("")
    lines.append(
        "| rank | task | set | domain | priority | coverage | stage2 share % | stage2 rows/s | 100k(min) | 1M(hr) | max req x |"
    )
    lines.append("| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for row in pacing_items:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(int(row.get("pacing_rank_1m", 0))),
                    str(row.get("task_id", "")),
                    str(row.get("set_id", "")),
                    str(row.get("domain", "")),
                    str(row.get("speedpack_priority", "")),
                    str(row.get("timing_coverage_tier", "")),
                    f"{float(row.get('stage2_share_pct', 0.0)):.2f}",
                    f"{float(row.get('queue_rate_stage2_rows_per_sec', 0.0)):.2f}",
                    f"{float(row.get('projected_100k_wall_min', 0.0)):.2f}",
                    f"{float(row.get('projected_1m_wall_hr', 0.0)):.2f}",
                    "n/a"
                    if row.get("max_required_speedup_to_target") is None
                    else f"{float(row.get('max_required_speedup_to_target', 0.0)):.2f}",
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Target Gap Items")
    lines.append("")
    lines.append(
        "| task | set | domain | priority | coverage | req x @100k | req x @1M | max req x | 100k(min) | 1M(hr) |"
    )
    lines.append("| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for row in target_gap_items:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("task_id", "")),
                    str(row.get("set_id", "")),
                    str(row.get("domain", "")),
                    str(row.get("speedpack_priority", "")),
                    str(row.get("timing_coverage_tier", "")),
                    "n/a"
                    if row.get("required_speedup_to_target_100k") is None
                    else f"{float(row.get('required_speedup_to_target_100k', 0.0)):.2f}",
                    "n/a"
                    if row.get("required_speedup_to_target_1m") is None
                    else f"{float(row.get('required_speedup_to_target_1m', 0.0)):.2f}",
                    f"{float(row.get('max_required_speedup_to_target', 0.0)):.2f}",
                    f"{float(row.get('projected_100k_wall_min', 0.0)):.2f}",
                    f"{float(row.get('projected_1m_wall_hr', 0.0)):.2f}",
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## 100k / 1M KPI Table")
    lines.append("")
    lines.append(
        "| set | task | domain | priority | coverage | total source | total@10k(s) | stage2 share % | stage2 rows/s | 100k(min) | 1M(hr) | req x @100k | req x @1M | max req x | 100k@2x(min) | 1M@2x(hr) | 100k@3x(min) | 1M@3x(hr) | levers |"
    )
    lines.append(
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["set_id"]),
                    str(row["task_id"]),
                    str(row["domain"]),
                    str(row["speedpack_priority"]),
                    str(row["timing_coverage_tier"]),
                    str(row["total_latency_source"]),
                    f"{float(row['total_latency_sec_10k']):.2f}",
                    f"{float(row['stage2_share_pct']):.2f}",
                    f"{float(row['queue_rate_stage2_rows_per_sec']):.2f}",
                    f"{float(row['projected_100k_wall_min']):.2f}",
                    f"{float(row['projected_1m_wall_hr']):.2f}",
                    "n/a"
                    if row.get("required_speedup_to_target_100k") is None
                    else f"{float(row['required_speedup_to_target_100k']):.2f}",
                    "n/a"
                    if row.get("required_speedup_to_target_1m") is None
                    else f"{float(row['required_speedup_to_target_1m']):.2f}",
                    "n/a"
                    if row.get("max_required_speedup_to_target") is None
                    else f"{float(row['max_required_speedup_to_target']):.2f}",
                    f"{float(row['projected_100k_wall_min_at_2x']):.2f}",
                    f"{float(row['projected_1m_wall_hr_at_2x']):.2f}",
                    f"{float(row['projected_100k_wall_min_at_3x']):.2f}",
                    f"{float(row['projected_1m_wall_hr_at_3x']):.2f}",
                    str(row["recommended_levers"]),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_payload(freeze_json_path: Path) -> Dict[str, Any]:
    freeze = _load_json(freeze_json_path)
    run_root = _resolve_path(str(freeze.get("run_root", "")))
    summary = _load_json(run_root / "summary.json")
    rows = _build_rows(summary)
    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "freeze_json": str(freeze_json_path.resolve()),
        "summary": _build_summary(rows, freeze),
        "rows": rows,
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a scale-up KPI table from the frozen accepted ligand validation run.")
    parser.add_argument(
        "--freeze-json",
        type=str,
        default="runs/biorxiv_submission_freeze_current.json",
    )
    parser.add_argument(
        "--out-json",
        type=str,
        default="runs/ligand_scaleup_kpi_current.json",
    )
    parser.add_argument(
        "--out-csv",
        type=str,
        default="runs/ligand_scaleup_kpi_current.csv",
    )
    parser.add_argument(
        "--out-md",
        type=str,
        default="runs/ligand_scaleup_kpi_current.md",
    )
    args = parser.parse_args()

    payload = build_payload(_resolve_path(str(args.freeze_json)))
    out_json = _resolve_path(str(args.out_json))
    out_csv = _resolve_path(str(args.out_csv))
    out_md = _resolve_path(str(args.out_md))
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    with out_json.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    pd.DataFrame(payload["rows"]).to_csv(out_csv, index=False)
    _write_md(out_md, payload)

    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    print(f"Wrote JSON: {out_json}")
    print(f"Wrote CSV: {out_csv}")
    print(f"Wrote MD: {out_md}")


if __name__ == "__main__":
    main()
