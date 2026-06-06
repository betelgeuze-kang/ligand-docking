#!/usr/bin/env python3
from __future__ import annotations

import argparse
import statistics
from typing import Any

from tools.wetlab.wetlab_broad_screen_calibration_registry import (
    load_calibration_registry,
    summarize_calibration_registry,
)
from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

DEFAULT_SOURCE_JSON = "runs/wetlab_broad_screen_bulk_results_source_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_bulk_results_current.md"
DEFAULT_SCHEMA_ARTIFACT = "runs/wetlab_broad_screen_bulk_result_source_schema_current.md"
RECOMMENDED_FEEDBACK_FIELDS = (
    "seed_status",
    "first_contact_use_mode",
    "vendor_check_required",
    "cost_check_required",
    "selectivity_note",
    "usage_rationale",
    "must_not_do",
    "source_anchor",
    "source_url",
)
CALIBRATION_READINESS_ORDER = (
    "bootstrap_only",
    "advisory_ready",
    "calibration_candidate",
    "calibration_ready",
)
CALIBRATION_READINESS_RANKS = {state: index for index, state in enumerate(CALIBRATION_READINESS_ORDER)}
THRESHOLD_POSTURE_BY_READINESS = {
    "bootstrap_only": "bootstrap_hold",
    "advisory_ready": "advisory_hold",
    "calibration_candidate": "prepare_tighten",
    "calibration_ready": "tighten",
}
THRESHOLD_POSTURE_RANKS = {
    "bootstrap_hold": 0,
    "advisory_hold": 1,
    "prepare_tighten": 2,
    "tighten": 3,
}
DECISION_CLASS_UPDATE_BY_READINESS = {
    "bootstrap_only": "keep_bootstrap_class",
    "advisory_ready": "keep_advisory_class",
    "calibration_candidate": "promote_threshold_review_class",
    "calibration_ready": "promote_threshold_tighten_class",
}
DECISION_CLASS_UPDATE_RANKS = {
    "keep_bootstrap_class": 0,
    "keep_advisory_class": 1,
    "promote_threshold_review_class": 2,
    "promote_threshold_tighten_class": 3,
}
CALIBRATION_ACTION_BUCKET_BY_READINESS = {
    "bootstrap_only": "collect_more_actuals",
    "advisory_ready": "maintain_advisory_floor",
    "calibration_candidate": "prepare_threshold_update",
    "calibration_ready": "tighten_thresholds",
}
CALIBRATION_ACTION_BUCKET_RANKS = {
    "collect_more_actuals": 0,
    "maintain_advisory_floor": 1,
    "prepare_threshold_update": 2,
    "tighten_thresholds": 3,
}
CONFIDENCE_BUCKET_BY_READINESS = {
    "bootstrap_only": "bootstrap_only",
    "advisory_ready": "watchlist",
    "calibration_candidate": "moderate_confidence",
    "calibration_ready": "high_confidence",
}
CONFIDENCE_BUCKET_RANKS = {
    "bootstrap_only": 0,
    "watchlist": 1,
    "moderate_confidence": 2,
    "high_confidence": 3,
}
COMMERCIAL_WEIGHT_BY_READINESS = {
    "bootstrap_only": 0.75,
    "advisory_ready": 0.9,
    "calibration_candidate": 1.05,
    "calibration_ready": 1.2,
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _is_bootstrap(row: dict[str, Any]) -> bool:
    return str(row.get("seed_status", "")).strip().lower().startswith("bootstrap_")


def _row_sort_key(row: dict[str, Any]) -> tuple[int, float, str]:
    return (
        _safe_int(row.get("bulk_rank", 10**9), 10**9),
        -_safe_float(row.get("bulk_score", 0.0), 0.0),
        str(row.get("compound_name", "")).strip().lower(),
    )


def _commercial_weight_from_readiness(readiness: str) -> float:
    return COMMERCIAL_WEIGHT_BY_READINESS.get(readiness, 1.0)


def _count_by(rows: list[dict[str, Any]], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field_name, "")).strip()
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _field_presence_count(row: dict[str, Any], field_names: tuple[str, ...]) -> int:
    return sum(1 for field_name in field_names if _has_value(row.get(field_name)))


def _field_presence_rate(row: dict[str, Any], field_names: tuple[str, ...]) -> float:
    if not field_names:
        return 0.0
    return round(_field_presence_count(row, field_names) / len(field_names), 3)


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * percentile / 100.0
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def _series_stats(values: list[Any]) -> dict[str, float]:
    cleaned = sorted(_safe_float(value, 0.0) for value in values if _has_value(value))
    if not cleaned:
        return {
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "p25": 0.0,
            "p75": 0.0,
            "std": 0.0,
        }
    mean = sum(cleaned) / len(cleaned)
    std = statistics.pstdev(cleaned) if len(cleaned) > 1 else 0.0
    return {
        "min": cleaned[0],
        "max": cleaned[-1],
        "mean": round(mean, 4),
        "median": round(statistics.median(cleaned), 4),
        "p25": round(_percentile(cleaned, 25.0), 4),
        "p75": round(_percentile(cleaned, 75.0), 4),
        "std": round(std, 4),
    }


def _feedback_quality_bucket(fill_rate: float) -> str:
    if fill_rate >= 0.9:
        return "complete"
    if fill_rate >= 0.75:
        return "strong"
    if fill_rate >= 0.5:
        return "partial"
    return "sparse"


def _rows_by_target(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        grouped.setdefault(target_id, []).append(dict(row))
    for target_id, target_rows in grouped.items():
        grouped[target_id] = sorted(target_rows, key=_row_sort_key)
    return grouped


def _source_calibration_readiness(actual_row_count: int, actual_top3_row_count: int) -> str:
    if actual_row_count <= 0:
        return "bootstrap_only"
    if actual_top3_row_count >= 3:
        return "calibration_ready"
    if actual_top3_row_count > 0:
        return "calibration_candidate"
    return "advisory_ready"


def _readiness_policy(readiness: str) -> dict[str, Any]:
    threshold_posture = THRESHOLD_POSTURE_BY_READINESS.get(readiness, "advisory_hold")
    decision_class_update_hint = DECISION_CLASS_UPDATE_BY_READINESS.get(readiness, "keep_advisory_class")
    calibration_action_bucket = CALIBRATION_ACTION_BUCKET_BY_READINESS.get(readiness, "maintain_advisory_floor")
    confidence_bucket = CONFIDENCE_BUCKET_BY_READINESS.get(readiness, "watchlist")
    return {
        "calibration_readiness": readiness,
        "calibration_readiness_rank": CALIBRATION_READINESS_RANKS.get(readiness, 1),
        "threshold_posture": threshold_posture,
        "threshold_posture_rank": THRESHOLD_POSTURE_RANKS.get(threshold_posture, 1),
        "decision_class_update_hint": decision_class_update_hint,
        "decision_class_update_rank": DECISION_CLASS_UPDATE_RANKS.get(decision_class_update_hint, 1),
        "calibration_action_bucket": calibration_action_bucket,
        "calibration_action_bucket_rank": CALIBRATION_ACTION_BUCKET_RANKS.get(calibration_action_bucket, 1),
        "confidence_bucket": confidence_bucket,
        "confidence_bucket_rank": CONFIDENCE_BUCKET_RANKS.get(confidence_bucket, 0),
    }


def _calibration_summary(
    rows: list[dict[str, Any]],
    *,
    registry_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actual_rows = [dict(row) for row in rows if not _is_bootstrap(row)]
    bootstrap_rows = [dict(row) for row in rows if _is_bootstrap(row)]
    rows_by_target = _rows_by_target(rows)
    actual_scores = [_safe_float(row.get("bulk_score", 0.0), 0.0) for row in actual_rows]
    bootstrap_scores = [_safe_float(row.get("bulk_score", 0.0), 0.0) for row in bootstrap_rows]
    actual_target_ids: list[str] = []
    actual_top3_target_count = 0
    actual_top3_row_count = 0
    actual_rank1_row_count = 0
    actual_rank2_3_row_count = 0
    actual_rank_gt3_row_count = 0
    actual_full_feedback_row_count = 0
    actual_provenance_complete_row_count = 0
    actual_feedback_completion_rates: list[float] = []
    actual_quality_bucket_counts: dict[str, int] = {}
    actual_recommended_field_fill_counts = {field_name: 0 for field_name in RECOMMENDED_FEEDBACK_FIELDS}

    for target_id, target_rows in rows_by_target.items():
        top3 = target_rows[:3]
        if any(not _is_bootstrap(row) for row in target_rows):
            actual_target_ids.append(target_id)
        if any(not _is_bootstrap(row) for row in top3):
            actual_top3_target_count += 1
        for row in target_rows:
            if _is_bootstrap(row):
                continue
            rank = _safe_int(row.get("bulk_rank", 10**9), 10**9)
            actual_top3_row_count += 1 if rank <= 3 else 0
            actual_rank1_row_count += 1 if rank == 1 else 0
            actual_rank2_3_row_count += 1 if rank in {2, 3} else 0
            actual_rank_gt3_row_count += 1 if rank > 3 else 0
            feedback_rate = _field_presence_rate(row, RECOMMENDED_FEEDBACK_FIELDS)
            actual_feedback_completion_rates.append(feedback_rate)
            quality_bucket = _feedback_quality_bucket(feedback_rate)
            actual_quality_bucket_counts[quality_bucket] = actual_quality_bucket_counts.get(quality_bucket, 0) + 1
            if feedback_rate >= 1.0:
                actual_full_feedback_row_count += 1
            if _has_value(row.get("source_anchor")) and _has_value(row.get("source_url")):
                actual_provenance_complete_row_count += 1
            for field_name in RECOMMENDED_FEEDBACK_FIELDS:
                if _has_value(row.get(field_name)):
                    actual_recommended_field_fill_counts[field_name] += 1

    actual_target_ids = sorted(set(actual_target_ids))
    actual_score_stats = _series_stats(actual_scores)
    bootstrap_score_stats = _series_stats(bootstrap_scores)
    actual_feedback_completion_rate = round(sum(actual_feedback_completion_rates) / len(actual_feedback_completion_rates), 3) if actual_feedback_completion_rates else 0.0
    actual_provenance_completion_rate = round(actual_provenance_complete_row_count / len(actual_rows), 3) if actual_rows else 0.0
    actual_target_fraction = round(len(actual_target_ids) / len({str(row.get("target_id", "")).strip() for row in rows if str(row.get("target_id", "")).strip()}), 3) if rows else 0.0
    actual_row_fraction = round(len(actual_rows) / len(rows), 3) if rows else 0.0
    actual_top3_row_fraction = round(actual_top3_row_count / len(actual_rows), 3) if actual_rows else 0.0
    actual_top3_target_fraction = round(actual_top3_target_count / len(actual_target_ids), 3) if actual_target_ids else 0.0
    actual_score_gap_vs_bootstrap_mean = round(actual_score_stats["mean"] - bootstrap_score_stats["mean"], 4) if actual_scores and bootstrap_scores else 0.0
    calibration_strength_bucket = (
        "strong_actual"
        if actual_rows and actual_top3_row_count >= 3 and actual_feedback_completion_rate >= 0.9
        else "partial_actual"
        if actual_rows
        else "bootstrap_only"
    )
    calibration_readiness = _source_calibration_readiness(len(actual_rows), actual_top3_row_count)
    policy = _readiness_policy(calibration_readiness)
    registry_summary = summarize_calibration_registry(registry_info)

    return {
        "actual_row_count": len(actual_rows),
        "bootstrap_row_count": len(bootstrap_rows),
        "actual_target_count": len(actual_target_ids),
        "actual_target_ids": actual_target_ids,
        "actual_row_fraction": actual_row_fraction,
        "actual_target_fraction": actual_target_fraction,
        "actual_top3_row_count": actual_top3_row_count,
        "actual_top3_row_fraction": actual_top3_row_fraction,
        "actual_top3_target_count": actual_top3_target_count,
        "actual_top3_target_fraction": actual_top3_target_fraction,
        "actual_rank1_row_count": actual_rank1_row_count,
        "actual_rank2_3_row_count": actual_rank2_3_row_count,
        "actual_rank_gt3_row_count": actual_rank_gt3_row_count,
        "actual_seed_status_counts": _count_by(actual_rows, "seed_status"),
        "actual_first_contact_use_mode_counts": _count_by(actual_rows, "first_contact_use_mode"),
        "actual_feedback_completion_rate": actual_feedback_completion_rate,
        "actual_provenance_completion_rate": actual_provenance_completion_rate,
        "actual_full_feedback_row_count": actual_full_feedback_row_count,
        "actual_provenance_complete_row_count": actual_provenance_complete_row_count,
        "actual_feedback_quality_bucket_counts": dict(sorted(actual_quality_bucket_counts.items(), key=lambda item: (-item[1], item[0]))),
        "actual_recommended_field_fill_counts": dict(sorted(actual_recommended_field_fill_counts.items(), key=lambda item: item[0])),
        "actual_bulk_score_min": actual_score_stats["min"],
        "actual_bulk_score_max": actual_score_stats["max"],
        "actual_bulk_score_mean": actual_score_stats["mean"],
        "actual_bulk_score_median": actual_score_stats["median"],
        "actual_bulk_score_p25": actual_score_stats["p25"],
        "actual_bulk_score_p75": actual_score_stats["p75"],
        "actual_bulk_score_std": actual_score_stats["std"],
        "bootstrap_bulk_score_min": bootstrap_score_stats["min"],
        "bootstrap_bulk_score_max": bootstrap_score_stats["max"],
        "bootstrap_bulk_score_mean": bootstrap_score_stats["mean"],
        "bootstrap_bulk_score_median": bootstrap_score_stats["median"],
        "bootstrap_bulk_score_p25": bootstrap_score_stats["p25"],
        "bootstrap_bulk_score_p75": bootstrap_score_stats["p75"],
        "bootstrap_bulk_score_std": bootstrap_score_stats["std"],
        "actual_bulk_score_mean_minus_bootstrap_mean": actual_score_gap_vs_bootstrap_mean,
        "calibration_state": "actual_rows_present" if actual_rows else "bootstrap_only",
        "calibration_strength_bucket": calibration_strength_bucket,
        "calibration_readiness": calibration_readiness,
        "calibration_readiness_rank": policy["calibration_readiness_rank"],
        "threshold_posture": policy["threshold_posture"],
        "threshold_posture_rank": policy["threshold_posture_rank"],
        "decision_class_update_hint": policy["decision_class_update_hint"],
        "decision_class_update_rank": policy["decision_class_update_rank"],
        "calibration_action_bucket": policy["calibration_action_bucket"],
        "calibration_action_bucket_rank": policy["calibration_action_bucket_rank"],
        "confidence_bucket": policy["confidence_bucket"],
        "confidence_bucket_rank": policy["confidence_bucket_rank"],
        "commercial_weight": _commercial_weight_from_readiness(calibration_readiness),
        "commercial_weight_source": "default_from_readiness",
        "score_posture": policy["threshold_posture"],
        "score_posture_source": "default_from_policy",
        "calibration_registry_presence": registry_summary["calibration_registry_presence"],
        "calibration_registry_entry_count": registry_summary["calibration_registry_entry_count"],
        "calibration_registry_target_count": registry_summary["calibration_registry_target_count"],
        "calibration_registry_override_target_count": registry_summary["calibration_registry_override_target_count"],
        "calibration_registry_default_target_count": registry_summary["calibration_registry_default_target_count"],
        "calibration_registry_target_ids": registry_summary["calibration_registry_target_ids"],
        "calibration_registry_source_counts": registry_summary["calibration_registry_source_counts"],
        "calibration_registry_field_override_counts": registry_summary["calibration_registry_field_override_counts"],
    }


def build_payload(source_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = [dict(row) for row in ((source_payload or {}).get("rows", []) or [])]
    summary = dict((source_payload or {}).get("summary", {}) or {})
    registry_info = load_calibration_registry(source_payload)
    calibration = _calibration_summary(rows, registry_info=registry_info)
    if rows:
        return {
            "summary": {
                "status": "wetlab_broad_screen_bulk_results_ready",
                "row_count": len(rows),
                "target_count": len({str(row.get("target_id", "")).strip() for row in rows if str(row.get("target_id", "")).strip()}),
                "actual_row_count": calibration["actual_row_count"],
                "bootstrap_row_count": calibration["bootstrap_row_count"],
                "actual_target_count": calibration["actual_target_count"],
                "actual_target_fraction": calibration["actual_target_fraction"],
                "actual_top3_row_count": calibration["actual_top3_row_count"],
                "actual_top3_row_fraction": calibration["actual_top3_row_fraction"],
                "actual_top3_target_count": calibration["actual_top3_target_count"],
                "actual_top3_target_fraction": calibration["actual_top3_target_fraction"],
                "actual_feedback_completion_rate": calibration["actual_feedback_completion_rate"],
                "actual_provenance_completion_rate": calibration["actual_provenance_completion_rate"],
                "actual_full_feedback_row_count": calibration["actual_full_feedback_row_count"],
                "actual_provenance_complete_row_count": calibration["actual_provenance_complete_row_count"],
                "actual_bulk_score_min": calibration["actual_bulk_score_min"],
                "actual_bulk_score_max": calibration["actual_bulk_score_max"],
                "actual_bulk_score_mean": calibration["actual_bulk_score_mean"],
                "actual_bulk_score_median": calibration["actual_bulk_score_median"],
                "actual_bulk_score_p25": calibration["actual_bulk_score_p25"],
                "actual_bulk_score_p75": calibration["actual_bulk_score_p75"],
                "actual_bulk_score_std": calibration["actual_bulk_score_std"],
                "bootstrap_bulk_score_mean": calibration["bootstrap_bulk_score_mean"],
                "actual_bulk_score_mean_minus_bootstrap_mean": calibration["actual_bulk_score_mean_minus_bootstrap_mean"],
                "calibration_state": calibration["calibration_state"],
                "calibration_strength_bucket": calibration["calibration_strength_bucket"],
                "calibration_readiness": calibration["calibration_readiness"],
                "calibration_readiness_rank": calibration["calibration_readiness_rank"],
                "threshold_posture": calibration["threshold_posture"],
                "threshold_posture_rank": calibration["threshold_posture_rank"],
                "decision_class_update_hint": calibration["decision_class_update_hint"],
                "decision_class_update_rank": calibration["decision_class_update_rank"],
                "calibration_action_bucket": calibration["calibration_action_bucket"],
                "calibration_action_bucket_rank": calibration["calibration_action_bucket_rank"],
                "confidence_bucket": calibration["confidence_bucket"],
                "confidence_bucket_rank": calibration["confidence_bucket_rank"],
                "commercial_weight": calibration["commercial_weight"],
                "commercial_weight_source": calibration["commercial_weight_source"],
                "score_posture": calibration["score_posture"],
                "score_posture_source": calibration["score_posture_source"],
                "calibration_registry_presence": calibration["calibration_registry_presence"],
                "calibration_registry_entry_count": calibration["calibration_registry_entry_count"],
                "calibration_registry_target_count": calibration["calibration_registry_target_count"],
                "calibration_registry_override_target_count": calibration["calibration_registry_override_target_count"],
                "calibration_registry_default_target_count": calibration["calibration_registry_default_target_count"],
                "calibration_registry_target_ids": calibration["calibration_registry_target_ids"],
                "calibration_registry_source_counts": calibration["calibration_registry_source_counts"],
                "calibration_registry_field_override_counts": calibration["calibration_registry_field_override_counts"],
                "actual_feedback_quality_bucket_counts": calibration["actual_feedback_quality_bucket_counts"],
                "actual_recommended_field_fill_counts": calibration["actual_recommended_field_fill_counts"],
                "next_required_step": "Use these bulk rows to regenerate the broad-screen repurposing autofill, then keep calibration_ready targets on a tightening track, calibration_candidate targets on a review track, and bootstrap_only targets conservative.",
            },
            "structured": {
                "source_json": DEFAULT_SOURCE_JSON,
                "schema_artifact": DEFAULT_SCHEMA_ARTIFACT,
                "feedback_fields_requested": "seed_status ; first_contact_use_mode ; vendor_check_required ; cost_check_required ; selectivity_note ; usage_rationale ; must_not_do ; source_anchor ; source_url",
                "calibration_hint": "Actual rows are preserved alongside bootstrap rows so rerank can use provenance-complete actual rows, score spread, feedback completeness, calibration readiness, decision-class hints, commercial weights, and calibration registry overrides as calibration inputs.",
            },
            "calibration": calibration,
            "rows": rows,
        }
    return {
        "summary": {
            "status": "wetlab_broad_screen_bulk_results_not_started",
            "row_count": 0,
            "target_count": 0,
            "actual_row_count": 0,
            "bootstrap_row_count": 0,
            "actual_target_count": 0,
            "actual_target_fraction": 0.0,
            "actual_top3_row_count": 0,
            "actual_top3_row_fraction": 0.0,
            "actual_top3_target_count": 0,
            "actual_top3_target_fraction": 0.0,
            "actual_feedback_completion_rate": 0.0,
            "actual_provenance_completion_rate": 0.0,
            "actual_full_feedback_row_count": 0,
            "actual_provenance_complete_row_count": 0,
            "actual_bulk_score_min": 0.0,
            "actual_bulk_score_max": 0.0,
            "actual_bulk_score_mean": 0.0,
            "actual_bulk_score_median": 0.0,
            "actual_bulk_score_p25": 0.0,
            "actual_bulk_score_p75": 0.0,
            "actual_bulk_score_std": 0.0,
            "bootstrap_bulk_score_mean": 0.0,
            "actual_bulk_score_mean_minus_bootstrap_mean": 0.0,
            "calibration_state": calibration["calibration_state"],
            "calibration_strength_bucket": calibration["calibration_strength_bucket"],
            "calibration_readiness": calibration["calibration_readiness"],
            "calibration_readiness_rank": calibration["calibration_readiness_rank"],
            "threshold_posture": calibration["threshold_posture"],
            "threshold_posture_rank": calibration["threshold_posture_rank"],
            "decision_class_update_hint": calibration["decision_class_update_hint"],
            "decision_class_update_rank": calibration["decision_class_update_rank"],
            "calibration_action_bucket": calibration["calibration_action_bucket"],
            "calibration_action_bucket_rank": calibration["calibration_action_bucket_rank"],
            "confidence_bucket": calibration["confidence_bucket"],
            "confidence_bucket_rank": calibration["confidence_bucket_rank"],
            "commercial_weight": calibration["commercial_weight"],
            "commercial_weight_source": calibration["commercial_weight_source"],
            "score_posture": calibration["score_posture"],
            "score_posture_source": calibration["score_posture_source"],
            "calibration_registry_presence": calibration["calibration_registry_presence"],
            "calibration_registry_entry_count": calibration["calibration_registry_entry_count"],
            "calibration_registry_target_count": calibration["calibration_registry_target_count"],
            "calibration_registry_override_target_count": calibration["calibration_registry_override_target_count"],
            "calibration_registry_default_target_count": calibration["calibration_registry_default_target_count"],
            "calibration_registry_target_ids": calibration["calibration_registry_target_ids"],
            "calibration_registry_source_counts": calibration["calibration_registry_source_counts"],
            "calibration_registry_field_override_counts": calibration["calibration_registry_field_override_counts"],
            "actual_feedback_quality_bucket_counts": calibration["actual_feedback_quality_bucket_counts"],
            "actual_recommended_field_fill_counts": calibration["actual_recommended_field_fill_counts"],
            "next_required_step": "Attach or generate target-level broad-screen result rows, then rerun the repurposing autofill builder and keep the calibration_ready / calibration_candidate / advisory_ready split intact.",
        },
        "structured": {
            "source_json": DEFAULT_SOURCE_JSON,
            "schema_artifact": DEFAULT_SCHEMA_ARTIFACT,
            "source_present": bool(summary or rows),
            "feedback_fields_requested": "seed_status ; first_contact_use_mode ; vendor_check_required ; cost_check_required ; selectivity_note ; usage_rationale ; must_not_do ; source_anchor ; source_url",
            "calibration_hint": "No actual rows are present yet, so downstream rerank should remain bootstrap-only and conservative; once actual rows arrive, threshold posture, decision-class hints, commercial weights, and calibration registry overrides should be keyed off calibration readiness.",
        },
        "calibration": calibration,
        "rows": [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize broad-screen bulk result rows if a source file is present.")
    parser.add_argument("--source-json", default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Bulk Results",
        build_payload(maybe_load_json(args.source_json)),
    )
