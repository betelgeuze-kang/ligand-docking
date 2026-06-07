#!/usr/bin/env python3
from __future__ import annotations

import argparse
import statistics
from typing import Any

from tools.wetlab.wetlab_broad_screen_calibration_registry import (
    load_calibration_registry,
    resolve_target_calibration_registry,
    summarize_calibration_registry,
)
from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

DEFAULT_SOURCE_JSON = "runs/wetlab_broad_screen_bulk_results_source_current.json"
DEFAULT_PROGRESS_JSON = "runs/wetlab_broad_screen_progress_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_target_rerank_current.md"
FEEDBACK_FIELDS = (
    "shard_id",
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
    std = statistics.pstdev(cleaned) if len(cleaned) > 1 else 0.0
    return {
        "min": cleaned[0],
        "max": cleaned[-1],
        "mean": round(sum(cleaned) / len(cleaned), 4),
        "median": round(statistics.median(cleaned), 4),
        "p25": round(_percentile(cleaned, 25.0), 4),
        "p75": round(_percentile(cleaned, 75.0), 4),
        "std": round(std, 4),
    }


def _top_score_stats(rows: list[dict[str, Any]], top_n: int = 3) -> dict[str, float]:
    ranked = sorted(rows, key=_row_sort_key)[:top_n]
    return _series_stats([row.get("bulk_score", 0.0) for row in ranked])


def _confidence_bucket(confidence_score: float, actual_row_count: int, actual_top3_count: int) -> str:
    if actual_row_count <= 0:
        return "bootstrap_only"
    if actual_top3_count >= 3 and confidence_score >= 80:
        return "high_confidence"
    if actual_top3_count > 0 and confidence_score >= 60:
        return "moderate_confidence"
    return "watchlist"


def _calibration_readiness(actual_row_count: int, actual_top3_count: int) -> str:
    if actual_row_count <= 0:
        return "bootstrap_only"
    if actual_top3_count >= 3:
        return "calibration_ready"
    if actual_top3_count > 0:
        return "calibration_candidate"
    return "advisory_ready"


def _threshold_posture(bucket: str) -> str:
    if bucket == "high_confidence":
        return "tighten"
    if bucket == "moderate_confidence":
        return "hold"
    if bucket == "watchlist":
        return "defer"
    return "bootstrap_only"


def _threshold_posture_from_readiness(readiness: str) -> str:
    return THRESHOLD_POSTURE_BY_READINESS.get(readiness, "advisory_hold")


def _decision_class_update_hint(readiness: str) -> str:
    return DECISION_CLASS_UPDATE_BY_READINESS.get(readiness, "keep_advisory_class")


def _calibration_action_bucket(readiness: str) -> str:
    return CALIBRATION_ACTION_BUCKET_BY_READINESS.get(readiness, "maintain_advisory_floor")


def _confidence_bucket_from_readiness(readiness: str) -> str:
    return CONFIDENCE_BUCKET_BY_READINESS.get(readiness, "watchlist")


def _commercial_weight_from_readiness(readiness: str) -> float:
    return COMMERCIAL_WEIGHT_BY_READINESS.get(readiness, 1.0)


def _readiness_policy(readiness: str, confidence_bucket: str) -> dict[str, Any]:
    threshold_posture = _threshold_posture_from_readiness(readiness)
    decision_class_update_hint = _decision_class_update_hint(readiness)
    calibration_action_bucket = _calibration_action_bucket(readiness)
    return {
        "calibration_readiness": readiness,
        "calibration_readiness_rank": CALIBRATION_READINESS_RANKS.get(readiness, 1),
        "threshold_posture": threshold_posture,
        "threshold_posture_rank": THRESHOLD_POSTURE_RANKS.get(threshold_posture, 1),
        "decision_class_update_hint": decision_class_update_hint,
        "decision_class_update_rank": DECISION_CLASS_UPDATE_RANKS.get(decision_class_update_hint, 1),
        "calibration_action_bucket": calibration_action_bucket,
        "calibration_action_bucket_rank": CALIBRATION_ACTION_BUCKET_RANKS.get(calibration_action_bucket, 1),
        "confidence_bucket_rank": CONFIDENCE_BUCKET_RANKS.get(confidence_bucket, 0),
    }


def _threshold_guidance(
    *,
    calibration_readiness: str,
    threshold_posture: str,
    decision_class_update_hint: str,
    bucket: str,
    actual_top3_floor: float,
    bootstrap_top3_floor: float,
    actual_mean: float,
    bootstrap_mean: float,
    actual_row_count: int,
    actual_top3_count: int,
    feedback_rate: float,
    provenance_rate: float,
    completed_shard_count: int,
    has_bootstrap_rows: bool,
) -> str:
    mean_delta = actual_mean - bootstrap_mean
    confidence_clause = f"confidence_bucket={bucket}"
    readiness_clause = f"calibration_readiness={calibration_readiness}"
    posture_clause = f"threshold_posture={threshold_posture}"
    decision_clause = f"decision_class_update_hint={decision_class_update_hint}"
    bootstrap_clause = (
        f"mean_delta_vs_bootstrap={mean_delta:+.2f}"
        if has_bootstrap_rows
        else "no bootstrap baseline in this target"
    )
    if calibration_readiness == "calibration_ready":
        return (
            f"Tighten the bulk_score floor to about {actual_top3_floor:.1f}; "
            f"actual top-3 support is complete and the calibration rows are provenance-complete "
            f"(feedback_rate={feedback_rate:.2f}, provenance_rate={provenance_rate:.2f}, completed_shards={completed_shard_count}, "
            f"{bootstrap_clause}, {confidence_clause}, {readiness_clause}, {posture_clause}, {decision_clause})."
        )
    if calibration_readiness == "calibration_candidate":
        return (
            f"Prepare to tighten the bulk_score floor around {actual_top3_floor:.1f}; "
            f"the actual rows are informative but should stay on review until the next pass "
            f"(actual_rows={actual_row_count}, actual_top3={actual_top3_count}, feedback_rate={feedback_rate:.2f}, "
            f"provenance_rate={provenance_rate:.2f}, {bootstrap_clause}, {confidence_clause}, {readiness_clause}, "
            f"{posture_clause}, {decision_clause})."
        )
    if calibration_readiness == "advisory_ready":
        return (
            f"Hold the current bootstrap floor near {bootstrap_top3_floor:.1f}; "
            f"actual rows are present but should stay advisory until the target reaches top-3 support "
            f"(actual_rows={actual_row_count}, actual_top3={actual_top3_count}, feedback_rate={feedback_rate:.2f}, "
            f"provenance_rate={provenance_rate:.2f}, {bootstrap_clause}, {confidence_clause}, {readiness_clause}, "
            f"{posture_clause}, {decision_clause})."
        )
    return (
        f"Stay bootstrap-only and keep the conservative floor near {bootstrap_top3_floor:.1f}; "
        f"no actual rows are available yet, so do not tighten thresholds on this target "
        f"({confidence_clause}, {readiness_clause}, {posture_clause}, {decision_clause})."
    )


def _confidence_score(
    *,
    actual_row_count: int,
    actual_top3_count: int,
    actual_row_fraction: float,
    actual_feedback_rate: float,
    actual_provenance_rate: float,
    completed_shard_count: int,
    actual_top3_span: float,
    actual_mean: float,
    bootstrap_mean: float,
) -> float:
    if actual_row_count <= 0:
        score = 10.0 + min(completed_shard_count, 8) * 1.5
        return round(min(35.0, score), 1)

    score = 28.0
    score += 28.0 * min(actual_top3_count, 3) / 3.0
    score += 14.0 * min(actual_row_count, 6) / 6.0
    score += 14.0 * actual_feedback_rate
    score += 10.0 * actual_provenance_rate
    score += 8.0 * min(completed_shard_count, 8) / 8.0
    score += 4.0 if actual_row_fraction >= 0.75 else 2.0 if actual_row_fraction >= 0.5 else 0.0
    score += 2.0 if actual_top3_span <= 5.0 else 0.0
    score += 2.0 if actual_mean >= bootstrap_mean else 0.0
    return round(min(100.0, score), 1)


def _target_rows(source_payload: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in ((source_payload or {}).get("rows", []) or []):
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        grouped.setdefault(target_id, []).append(dict(row))
    for target_id, rows in grouped.items():
        grouped[target_id] = sorted(rows, key=_row_sort_key)
    return grouped


def _completed_shards(progress_payload: dict[str, Any] | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in ((progress_payload or {}).get("rows", []) or []):
        if str(row.get("queue_status", "")).strip() != "result_ready":
            continue
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        counts[target_id] = counts.get(target_id, 0) + 1
    return counts


def _target_calibration_hint(actual_row_count: int, actual_top3_count: int) -> tuple[str, str]:
    if actual_top3_count >= 3:
        return "full_actual_support", "Actual rows are strong enough to treat the target as higher-confidence for threshold tightening."
    if actual_top3_count > 0:
        return "partial_actual_support", "Use the actual rows as advisory calibration only and keep the current thresholds conservative."
    if actual_row_count > 0:
        return "actual_present_but_off_top3", "Actual rows exist but are not shaping the top-3 yet, so rerank should stay bootstrap-aware."
    return "bootstrap_only", "No actual rows are present for this target yet, so keep rerank in bootstrap-only mode."


def _source_calibration_readiness(actual_row_count: int, actual_top3_count: int) -> str:
    if actual_row_count <= 0:
        return "bootstrap_only"
    if actual_top3_count >= 3:
        return "calibration_ready"
    if actual_top3_count > 0:
        return "calibration_candidate"
    return "advisory_ready"


def _source_calibration(
    source_payload: dict[str, Any] | None,
    *,
    registry_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [dict(row) for row in ((source_payload or {}).get("rows", []) or [])]
    rows_by_target = _target_rows(source_payload)
    actual_rows = [dict(row) for row in rows if not _is_bootstrap(row)]
    bootstrap_rows = [dict(row) for row in rows if _is_bootstrap(row)]
    actual_scores = [_safe_float(row.get("bulk_score", 0.0), 0.0) for row in actual_rows]
    bootstrap_scores = [_safe_float(row.get("bulk_score", 0.0), 0.0) for row in bootstrap_rows]
    actual_feedback_completion_rate = (
        round(sum(_field_presence_rate(row, FEEDBACK_FIELDS) for row in actual_rows) / len(actual_rows), 3)
        if actual_rows
        else 0.0
    )
    actual_provenance_completion_rate = (
        round(
            sum(1 for row in actual_rows if _has_value(row.get("source_anchor")) and _has_value(row.get("source_url"))) / len(actual_rows),
            3,
        )
        if actual_rows
        else 0.0
    )
    actual_target_ids: list[str] = []
    actual_top3_target_count = 0
    actual_top3_row_count = 0
    actual_rank1_row_count = 0
    actual_rank2_3_row_count = 0
    actual_rank_gt3_row_count = 0

    for target_id, ranked_rows in rows_by_target.items():
        top3 = ranked_rows[:3]
        if any(not _is_bootstrap(row) for row in ranked_rows):
            actual_target_ids.append(target_id)
        if any(not _is_bootstrap(row) for row in top3):
            actual_top3_target_count += 1
        for row in ranked_rows:
            if _is_bootstrap(row):
                continue
            rank = _safe_int(row.get("bulk_rank", 10**9), 10**9)
            actual_top3_row_count += 1 if rank <= 3 else 0
            actual_rank1_row_count += 1 if rank == 1 else 0
            actual_rank2_3_row_count += 1 if rank in {2, 3} else 0
            actual_rank_gt3_row_count += 1 if rank > 3 else 0

    actual_target_ids = sorted(set(actual_target_ids))
    calibration_state = "actual_supported" if actual_top3_row_count else "actual_rows_present" if actual_rows else "bootstrap_only"
    calibration_readiness = _source_calibration_readiness(len(actual_rows), actual_top3_row_count)
    confidence_bucket = _confidence_bucket_from_readiness(calibration_readiness)
    policy = _readiness_policy(calibration_readiness, confidence_bucket)
    source_summary = dict((source_payload or {}).get("summary", {}) or {})
    raw_calibration = dict((source_payload or {}).get("calibration", {}) or {})
    registry_summary = summarize_calibration_registry(registry_info)
    actual_score_stats = _series_stats(actual_scores)
    bootstrap_score_stats = _series_stats(bootstrap_scores)
    actual_score_mean_minus_bootstrap_mean = (
        round(actual_score_stats["mean"] - bootstrap_score_stats["mean"], 4) if actual_scores and bootstrap_scores else 0.0
    )
    actual_row_fraction = round(len(actual_rows) / len(rows), 3) if rows else 0.0
    actual_top3_row_fraction = round(actual_top3_row_count / len(actual_rows), 3) if actual_rows else 0.0

    calibration = {
        "source_row_count": len(rows),
        "actual_row_count": len(actual_rows),
        "bootstrap_row_count": len(bootstrap_rows),
        "actual_row_fraction": actual_row_fraction,
        "actual_top3_row_fraction": actual_top3_row_fraction,
        "actual_target_count": len(actual_target_ids),
        "actual_target_ids": actual_target_ids,
        "actual_top3_row_count": actual_top3_row_count,
        "actual_top3_target_count": actual_top3_target_count,
        "actual_rank1_row_count": actual_rank1_row_count,
        "actual_rank2_3_row_count": actual_rank2_3_row_count,
        "actual_rank_gt3_row_count": actual_rank_gt3_row_count,
        "actual_seed_status_counts": _count_by(actual_rows, "seed_status"),
        "actual_first_contact_use_mode_counts": _count_by(actual_rows, "first_contact_use_mode"),
        "actual_feedback_completion_rate": actual_feedback_completion_rate,
        "actual_provenance_completion_rate": actual_provenance_completion_rate,
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
        "actual_bulk_score_mean_minus_bootstrap_mean": actual_score_mean_minus_bootstrap_mean,
        "calibration_state": calibration_state,
        "calibration_readiness": calibration_readiness,
        "calibration_readiness_rank": policy["calibration_readiness_rank"],
        "threshold_posture": policy["threshold_posture"],
        "threshold_posture_rank": policy["threshold_posture_rank"],
        "decision_class_update_hint": policy["decision_class_update_hint"],
        "decision_class_update_rank": policy["decision_class_update_rank"],
        "calibration_action_bucket": policy["calibration_action_bucket"],
        "calibration_action_bucket_rank": policy["calibration_action_bucket_rank"],
        "confidence_bucket": confidence_bucket,
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
    calibration.update({key: value for key, value in raw_calibration.items() if key not in calibration})
    calibration["source_summary"] = source_summary
    return calibration


def build_payload(
    source_payload: dict[str, Any] | None = None,
    progress_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows_by_target = _target_rows(source_payload)
    completed_shards = _completed_shards(progress_payload)
    registry_info = load_calibration_registry(source_payload)
    source_calibration = _source_calibration(source_payload, registry_info=registry_info)

    rows: list[dict[str, Any]] = []
    full_bulk_ready_target_count = 0
    partial_actual_target_count = 0
    confidence_bucket_counts: dict[str, int] = {}
    threshold_posture_counts: dict[str, int] = {}
    threshold_posture_v2_counts: dict[str, int] = {}
    calibration_readiness_counts: dict[str, int] = {}
    decision_class_update_counts: dict[str, int] = {}
    calibration_action_bucket_counts: dict[str, int] = {}
    calibration_registry_state_counts: dict[str, int] = {}
    selected_threshold_override_target_count = 0
    decision_class_override_target_count = 0
    commercial_weight_override_target_count = 0
    score_posture_override_target_count = 0
    for target_id in sorted(rows_by_target):
        ranked = rows_by_target[target_id]
        actual_rows = [row for row in ranked if not _is_bootstrap(row)]
        bootstrap_rows = [row for row in ranked if _is_bootstrap(row)]
        top3 = ranked[:3]
        actual_top3_count = sum(1 for row in top3 if not _is_bootstrap(row))
        calibration_hint, calibration_advice = _target_calibration_hint(len(actual_rows), actual_top3_count)
        actual_score_stats = _series_stats([row.get("bulk_score", 0.0) for row in actual_rows])
        bootstrap_score_stats = _series_stats([row.get("bulk_score", 0.0) for row in bootstrap_rows])
        actual_top3_score_stats = _top_score_stats(actual_rows, 3)
        bootstrap_top3_score_stats = _top_score_stats(bootstrap_rows, 3)
        actual_feedback_completion_rate = (
            round(sum(_field_presence_rate(row, FEEDBACK_FIELDS) for row in actual_rows) / len(actual_rows), 3)
            if actual_rows
            else 0.0
        )
        actual_provenance_completion_rate = (
            round(
                sum(1 for row in actual_rows if _has_value(row.get("source_anchor")) and _has_value(row.get("source_url"))) / len(actual_rows),
                3,
            )
            if actual_rows
            else 0.0
        )
        actual_row_fraction = round(len(actual_rows) / len(ranked), 3) if ranked else 0.0
        confidence_score = _confidence_score(
            actual_row_count=len(actual_rows),
            actual_top3_count=actual_top3_count,
            actual_row_fraction=actual_row_fraction,
            actual_feedback_rate=actual_feedback_completion_rate,
            actual_provenance_rate=actual_provenance_completion_rate,
            completed_shard_count=completed_shards.get(target_id, 0),
            actual_top3_span=actual_top3_score_stats["max"] - actual_top3_score_stats["min"] if actual_rows else 0.0,
            actual_mean=actual_score_stats["mean"],
            bootstrap_mean=bootstrap_score_stats["mean"],
        )
        confidence_bucket = _confidence_bucket(confidence_score, len(actual_rows), actual_top3_count)
        calibration_readiness = _calibration_readiness(len(actual_rows), actual_top3_count)
        policy = _readiness_policy(calibration_readiness, confidence_bucket)
        threshold_posture = _threshold_posture(confidence_bucket)
        commercial_weight_default = _commercial_weight_from_readiness(calibration_readiness)
        registry_resolution = resolve_target_calibration_registry(
            target_id,
            registry_info=registry_info,
            defaults={
                "selected_threshold_A": None,
                "decision_class_update_hint": policy["decision_class_update_hint"],
                "commercial_weight": commercial_weight_default,
                "score_posture": policy["threshold_posture"],
                "threshold_posture": policy["threshold_posture"],
            },
            fallback_reason=(
                f"Default policy follows calibration_readiness={calibration_readiness}; "
                f"threshold_posture={policy['threshold_posture']}; "
                f"decision_class_update_hint={policy['decision_class_update_hint']}; "
                f"commercial_weight={commercial_weight_default:.2f}."
            ),
        )
        effective_threshold_posture = str(registry_resolution["threshold_posture"]).strip()
        effective_decision_class = str(registry_resolution["decision_class_update_hint"]).strip()
        effective_commercial_weight = _safe_float(registry_resolution["commercial_weight"], commercial_weight_default) or commercial_weight_default
        registry_state = str(registry_resolution["calibration_registry_state"]).strip()
        actual_top3_floor = actual_top3_score_stats["min"] if actual_rows else 0.0
        bootstrap_top3_floor = bootstrap_top3_score_stats["min"] if bootstrap_rows else actual_top3_floor
        threshold_guidance = _threshold_guidance(
            calibration_readiness=calibration_readiness,
            threshold_posture=effective_threshold_posture,
            decision_class_update_hint=effective_decision_class,
            bucket=confidence_bucket,
            actual_top3_floor=actual_top3_floor if actual_top3_floor else bootstrap_top3_floor,
            bootstrap_top3_floor=bootstrap_top3_floor,
            actual_mean=actual_score_stats["mean"],
            bootstrap_mean=bootstrap_score_stats["mean"],
            actual_row_count=len(actual_rows),
            actual_top3_count=actual_top3_count,
            feedback_rate=actual_feedback_completion_rate,
            provenance_rate=actual_provenance_completion_rate,
            completed_shard_count=completed_shards.get(target_id, 0),
            has_bootstrap_rows=bool(bootstrap_rows),
        )
        confidence_bucket_counts[confidence_bucket] = confidence_bucket_counts.get(confidence_bucket, 0) + 1
        threshold_posture_counts[effective_threshold_posture] = threshold_posture_counts.get(effective_threshold_posture, 0) + 1
        threshold_posture_v2_counts[effective_threshold_posture] = threshold_posture_v2_counts.get(effective_threshold_posture, 0) + 1
        calibration_readiness_counts[calibration_readiness] = calibration_readiness_counts.get(calibration_readiness, 0) + 1
        decision_class_update_counts[effective_decision_class] = decision_class_update_counts.get(effective_decision_class, 0) + 1
        calibration_action_bucket_counts[policy["calibration_action_bucket"]] = calibration_action_bucket_counts.get(policy["calibration_action_bucket"], 0) + 1
        calibration_registry_state_counts[registry_state] = calibration_registry_state_counts.get(registry_state, 0) + 1
        if bool(registry_resolution["selected_threshold_A_override_applied"]):
            selected_threshold_override_target_count += 1
        if bool(registry_resolution["decision_class_update_hint_override_applied"]):
            decision_class_override_target_count += 1
        if bool(registry_resolution["commercial_weight_override_applied"]):
            commercial_weight_override_target_count += 1
        if bool(registry_resolution["score_posture_override_applied"]):
            score_posture_override_target_count += 1

        if actual_top3_count >= 3:
            rerank_status = "full_bulk_top3_ready"
            full_bulk_ready_target_count += 1
        elif actual_top3_count > 0:
            rerank_status = "partial_actual_top3_not_full_bulk_ready"
            partial_actual_target_count += 1
        else:
            rerank_status = "bootstrap_only"

        rows.append(
            {
                "target_id": target_id,
                "completed_shard_count": completed_shards.get(target_id, 0),
                "source_row_count": len(ranked),
                "actual_row_count": len(actual_rows),
                "bootstrap_row_count": len(bootstrap_rows),
                "actual_row_fraction": actual_row_fraction,
                "actual_top3_count": actual_top3_count,
                "actual_feedback_completion_rate": actual_feedback_completion_rate,
                "actual_provenance_completion_rate": actual_provenance_completion_rate,
                "actual_bulk_score_min": actual_score_stats["min"],
                "actual_bulk_score_max": actual_score_stats["max"],
                "actual_bulk_score_mean": actual_score_stats["mean"],
                "actual_bulk_score_median": actual_score_stats["median"],
                "actual_top3_bulk_score_floor": actual_top3_floor,
                "bootstrap_bulk_score_min": bootstrap_score_stats["min"],
                "bootstrap_bulk_score_max": bootstrap_score_stats["max"],
                "bootstrap_bulk_score_mean": bootstrap_score_stats["mean"],
                "bootstrap_bulk_score_median": bootstrap_score_stats["median"],
                "bootstrap_top3_bulk_score_floor": bootstrap_top3_floor,
                "actual_bulk_score_mean_minus_bootstrap_mean": round(actual_score_stats["mean"] - bootstrap_score_stats["mean"], 4)
                if actual_rows and bootstrap_rows
                else 0.0,
                "rerank_status": rerank_status,
                "calibration_hint": calibration_hint,
                "calibration_advice": calibration_advice,
                "confidence_bucket": confidence_bucket,
                "confidence_score": confidence_score,
                "confidence_bucket_rank": CONFIDENCE_BUCKET_RANKS[confidence_bucket],
                "calibration_readiness": calibration_readiness,
                "calibration_readiness_rank": policy["calibration_readiness_rank"],
                "threshold_posture": effective_threshold_posture,
                "threshold_posture_default": policy["threshold_posture"],
                "threshold_posture_source": registry_resolution["threshold_posture_source"],
                "threshold_posture_override_applied": bool(registry_resolution["threshold_posture_override_applied"]),
                "threshold_posture_rank": policy["threshold_posture_rank"],
                "decision_class_update_hint": effective_decision_class,
                "decision_class_update_hint_default": policy["decision_class_update_hint"],
                "decision_class_update_hint_source": registry_resolution["decision_class_update_hint_source"],
                "decision_class_update_hint_override_applied": bool(registry_resolution["decision_class_update_hint_override_applied"]),
                "decision_class_update_rank": policy["decision_class_update_rank"],
                "calibration_action_bucket": policy["calibration_action_bucket"],
                "calibration_action_bucket_rank": policy["calibration_action_bucket_rank"],
                "recommended_threshold_action": effective_threshold_posture,
                "recommended_threshold_band": (
                    "tighten_ready"
                    if effective_threshold_posture == "tighten"
                    else "stable_hold"
                    if effective_threshold_posture == "hold"
                    else "watchlist"
                    if effective_threshold_posture == "defer"
                    else "bootstrap_only"
                ),
                "recommended_bulk_score_floor": round(actual_top3_floor if actual_rows else bootstrap_top3_floor, 1),
                "recommended_bulk_score_ceiling": round(actual_score_stats["max"] if actual_rows else bootstrap_score_stats["max"], 1),
                "commercial_weight": round(effective_commercial_weight, 3),
                "commercial_weight_default": round(commercial_weight_default, 3),
                "commercial_weight_source": registry_resolution["commercial_weight_source"],
                "commercial_weight_override_applied": bool(registry_resolution["commercial_weight_override_applied"]),
                "score_posture": registry_resolution["score_posture"],
                "score_posture_default": policy["threshold_posture"],
                "score_posture_source": registry_resolution["score_posture_source"],
                "score_posture_override_applied": bool(registry_resolution["score_posture_override_applied"]),
                "selected_threshold_A": registry_resolution["selected_threshold_A"],
                "selected_threshold_A_default": registry_resolution["selected_threshold_A_default"],
                "selected_threshold_A_source": registry_resolution["selected_threshold_A_source"],
                "selected_threshold_A_override_applied": bool(registry_resolution["selected_threshold_A_override_applied"]),
                "calibration_registry_presence": registry_resolution["calibration_registry_presence"],
                "calibration_registry_match": bool(registry_resolution["calibration_registry_match"]),
                "calibration_registry_state": registry_state,
                "calibration_registry_source": registry_resolution["calibration_registry_source"],
                "calibration_registry_reason": registry_resolution["calibration_registry_reason"],
                "calibration_registry_reason_source": registry_resolution["calibration_registry_reason_source"],
                "calibration_registry_override_fields": registry_resolution["calibration_registry_override_fields"],
                "calibration_registry_entry_count": registry_resolution["calibration_registry_entry_count"],
                "calibration_registry_target_count": registry_resolution["calibration_registry_target_count"],
                "calibration_registry_override_target_count": registry_resolution["calibration_registry_override_target_count"],
                "calibration_registry_default_target_count": registry_resolution["calibration_registry_default_target_count"],
                "threshold_guidance": threshold_guidance,
                "threshold_delta_hint": (
                    f"mean_delta_vs_bootstrap={round(actual_score_stats['mean'] - bootstrap_score_stats['mean'], 2):+.2f}; "
                    f"top3_floor_gap={round(actual_top3_floor - bootstrap_top3_floor, 2):+.2f}"
                    if actual_rows and bootstrap_rows
                    else "actual_only_no_bootstrap_baseline"
                    if actual_rows
                    else "bootstrap_only"
                ),
                "calibration_basis": (
                    f"actual_rows={len(actual_rows)}; actual_top3={actual_top3_count}; "
                    f"feedback_rate={actual_feedback_completion_rate:.2f}; provenance_rate={actual_provenance_completion_rate:.2f}; "
                    f"completed_shards={completed_shards.get(target_id, 0)}; "
                    f"calibration_readiness={calibration_readiness}; threshold_posture={effective_threshold_posture}; "
                    f"decision_class_update_hint={effective_decision_class}; "
                    f"commercial_weight={round(effective_commercial_weight, 3):.3f}; "
                    f"calibration_action_bucket={policy['calibration_action_bucket']}"
                ),
                "top1_compound": str(top3[0].get("compound_name", "")).strip() if len(top3) >= 1 else "",
                "top2_compound": str(top3[1].get("compound_name", "")).strip() if len(top3) >= 2 else "",
                "top3_compound": str(top3[2].get("compound_name", "")).strip() if len(top3) >= 3 else "",
            }
        )

    return {
        "summary": {
            "status": "wetlab_broad_screen_target_rerank_ready",
            "target_count": len(rows),
            "full_bulk_ready_target_count": full_bulk_ready_target_count,
            "partial_actual_target_count": partial_actual_target_count,
            "source_row_count": source_calibration["source_row_count"],
            "source_actual_row_count": source_calibration["actual_row_count"],
            "source_bootstrap_row_count": source_calibration["bootstrap_row_count"],
            "source_actual_row_fraction": source_calibration["actual_row_fraction"],
            "source_actual_target_count": source_calibration["actual_target_count"],
            "source_actual_top3_row_count": source_calibration["actual_top3_row_count"],
            "source_actual_top3_row_fraction": source_calibration["actual_top3_row_fraction"],
            "source_actual_top3_target_count": source_calibration["actual_top3_target_count"],
            "source_actual_feedback_completion_rate": source_calibration["actual_feedback_completion_rate"],
            "source_actual_provenance_completion_rate": source_calibration["actual_provenance_completion_rate"],
            "source_actual_bulk_score_mean": source_calibration["actual_bulk_score_mean"],
            "source_bootstrap_bulk_score_mean": source_calibration["bootstrap_bulk_score_mean"],
            "source_actual_bulk_score_mean_minus_bootstrap_mean": source_calibration["actual_bulk_score_mean_minus_bootstrap_mean"],
            "calibration_state": source_calibration["calibration_state"],
            "source_calibration_readiness": source_calibration["calibration_readiness"],
            "source_threshold_posture": source_calibration["threshold_posture"],
            "source_decision_class_update_hint": source_calibration["decision_class_update_hint"],
            "source_calibration_action_bucket": source_calibration["calibration_action_bucket"],
            "source_confidence_bucket": source_calibration["confidence_bucket"],
            "source_calibration_readiness_rank": source_calibration["calibration_readiness_rank"],
            "source_threshold_posture_rank": source_calibration["threshold_posture_rank"],
            "source_decision_class_update_rank": source_calibration["decision_class_update_rank"],
            "source_calibration_action_bucket_rank": source_calibration["calibration_action_bucket_rank"],
            "source_confidence_bucket_rank": source_calibration["confidence_bucket_rank"],
            "source_commercial_weight": source_calibration["commercial_weight"],
            "source_commercial_weight_source": source_calibration["commercial_weight_source"],
            "source_score_posture": source_calibration["score_posture"],
            "source_score_posture_source": source_calibration["score_posture_source"],
            "calibration_registry_presence": source_calibration["calibration_registry_presence"],
            "calibration_registry_entry_count": source_calibration["calibration_registry_entry_count"],
            "calibration_registry_target_count": source_calibration["calibration_registry_target_count"],
            "calibration_registry_override_target_count": source_calibration["calibration_registry_override_target_count"],
            "calibration_registry_default_target_count": source_calibration["calibration_registry_default_target_count"],
            "calibration_registry_target_ids": source_calibration["calibration_registry_target_ids"],
            "calibration_registry_source_counts": source_calibration["calibration_registry_source_counts"],
            "calibration_registry_field_override_counts": source_calibration["calibration_registry_field_override_counts"],
            "confidence_bucket_counts": confidence_bucket_counts,
            "threshold_posture_counts": threshold_posture_counts,
            "threshold_posture_v2_counts": threshold_posture_v2_counts,
            "calibration_readiness_counts": calibration_readiness_counts,
            "decision_class_update_counts": decision_class_update_counts,
            "calibration_action_bucket_counts": calibration_action_bucket_counts,
            "calibration_registry_state_counts": calibration_registry_state_counts,
            "selected_threshold_A_override_target_count": selected_threshold_override_target_count,
            "decision_class_update_hint_override_target_count": decision_class_override_target_count,
            "commercial_weight_override_target_count": commercial_weight_override_target_count,
            "score_posture_override_target_count": score_posture_override_target_count,
            "next_required_step": "Keep merging real shard rows until targets reach full_bulk_top3_ready, then tighten thresholds only for high-confidence targets, promote calibration_candidate targets for review, and keep bootstrap-only targets conservative.",
        },
        "structured": {
            "source_artifact": "runs/wetlab_broad_screen_bulk_results_source_current.md",
            "progress_artifact": "runs/wetlab_broad_screen_progress_current.md",
            "source_calibration_artifact": "runs/wetlab_broad_screen_bulk_results_current.md",
            "calibration_hint": "Actual-result counts, confidence buckets, calibration readiness, action buckets, commercial weights, and calibration registry overrides are threaded into each target row as advisory inputs; preserve them as explicit machine-readable calibration signals rather than hidden prose.",
        },
        "calibration": source_calibration,
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build target-level rerank readiness from the broad-screen bulk-result source.")
    parser.add_argument("--source-json", default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--progress-json", default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Target Rerank",
        build_payload(
            source_payload=maybe_load_json(args.source_json),
            progress_payload=maybe_load_json(args.progress_json),
        ),
    )
