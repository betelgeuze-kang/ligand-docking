#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from tools.wetlab import build_wetlab_prediction_result_comparison as comparison_mod
from tools.builder_table_utils import write_csv_rows
from tools.wetlab.wetlab_broad_screen_calibration_registry import (
    load_calibration_registry,
    resolve_target_calibration_registry,
    summarize_calibration_registry,
)
from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

DEFAULT_SCHEMA_JSON = "runs/wetlab_broad_screen_bulk_result_source_schema_current.json"
DEFAULT_SOURCE_JSON = "runs/wetlab_broad_screen_bulk_results_source_current.json"
DEFAULT_EXAMPLE_ROWS_JSON = "runs/wetlab_broad_screen_bulk_result_row_examples_current.json"
DEFAULT_OUT_MD = "runs/caix_broad_screen_shard_04_intake_packet_current.md"
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
FEEDBACK_GROUPS = {
    "provenance": ("shard_id", "seed_status", "source_anchor", "source_url"),
    "operational_flags": ("first_contact_use_mode", "vendor_check_required", "cost_check_required"),
    "interpretation": ("selectivity_note", "usage_rationale", "must_not_do"),
}
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
ROOT = Path(__file__).resolve().parents[1]


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


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


def _span(values: list[Any], *, formatter: str = "int") -> str:
    cleaned: list[float] = []
    for value in values:
        if formatter == "float":
            cleaned.append(_safe_float(value, 0.0))
        else:
            cleaned.append(float(_safe_int(value, 0)))
    if not cleaned:
        return ""
    if formatter == "float":
        return f"{min(cleaned):.1f}..{max(cleaned):.1f}"
    return f"{int(min(cleaned))}..{int(max(cleaned))}"


def _field_presence_count(row: dict[str, Any], field_names: tuple[str, ...]) -> int:
    return sum(1 for field_name in field_names if _has_value(row.get(field_name)))


def _field_presence_rate(row: dict[str, Any], field_names: tuple[str, ...]) -> float:
    if not field_names:
        return 0.0
    return round(_field_presence_count(row, field_names) / len(field_names), 3)


def _join_fields(field_names: tuple[str, ...]) -> str:
    return " ; ".join(field_names)


def _build_feedback_field_order(schema_rows: list[dict[str, Any]]) -> list[str]:
    schema_optional_fields = [
        str(row.get("field_name", "")).strip()
        for row in schema_rows
        if not bool(row.get("required", False)) and str(row.get("field_name", "")).strip()
    ]
    ordered = [field_name for field_name in FEEDBACK_FIELDS if field_name in schema_optional_fields]
    ordered.extend(field_name for field_name in schema_optional_fields if field_name not in ordered)
    return ordered


def _source_calibration_readiness(source_actual_row_count: int, source_actual_top3_count: int) -> str:
    if source_actual_row_count <= 0:
        return "bootstrap_only"
    if source_actual_top3_count >= 3:
        return "calibration_ready"
    if source_actual_top3_count > 0:
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


def _commercial_weight_from_readiness(readiness: str) -> float:
    return COMMERCIAL_WEIGHT_BY_READINESS.get(readiness, 1.0)


def _derive_comparison_paths(out_md: str) -> tuple[Path, Path, Path]:
    out_path = _resolve(out_md)
    stem = out_path.stem.replace("_intake_packet_current", "_prediction_result_comparison_current")
    base = out_path.with_name(stem)
    return base.with_suffix(".json"), base.with_suffix(".csv"), base.with_suffix(".md")


def _build_comparison_artifacts(
    *,
    target_id: str,
    source_rows: list[dict[str, Any]],
    actual_results_table: str,
    prediction_table: str = "",
    comparison_score_col: str = "",
    comparison_actual_col: str = "",
    comparison_out_json: str = "",
    comparison_out_csv: str = "",
    comparison_out_md: str = "",
    intake_out_md: str = DEFAULT_OUT_MD,
) -> dict[str, Any]:
    if not actual_results_table:
        return {}
    if prediction_table:
        prediction_frame = comparison_mod._load_frame(prediction_table)
    else:
        prediction_frame = pd.DataFrame(source_rows)
    if prediction_frame.empty:
        return {}
    actual_frame = comparison_mod._load_frame(actual_results_table)
    comparison_payload = comparison_mod.build_payload(
        prediction_frame,
        actual_frame,
        score_col=comparison_score_col,
        actual_col=comparison_actual_col,
    )
    target_rows = [row for row in comparison_payload.get("targets", []) if str(row.get("target_id", "")).strip() == target_id]
    target_summary = target_rows[0] if target_rows else {}
    if not comparison_out_json or not comparison_out_csv or not comparison_out_md:
        derived_json, derived_csv, derived_md = _derive_comparison_paths(intake_out_md)
        comparison_out_json = comparison_out_json or str(derived_json)
        comparison_out_csv = comparison_out_csv or str(derived_csv)
        comparison_out_md = comparison_out_md or str(derived_md)
    out_json = _resolve(comparison_out_json)
    out_csv = _resolve(comparison_out_csv)
    out_md = _resolve(comparison_out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(comparison_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, comparison_payload.get("rows", []) or [])
    comparison_mod._write_markdown(out_md, comparison_payload)
    return {
        "status": str(comparison_payload.get("summary", {}).get("status", "")).strip() or "comparison_not_built",
        "artifact_json": str(out_json),
        "artifact_csv": str(out_csv),
        "artifact_md": str(out_md),
        "merged_row_count": comparison_payload.get("summary", {}).get("merged_row_count", 0),
        "actual_value_kind": comparison_payload.get("summary", {}).get("actual_value_kind", ""),
        "prediction_score_col": comparison_payload.get("summary", {}).get("prediction_score_col", ""),
        "spearman_prediction_vs_activity": target_summary.get("spearman_prediction_vs_activity", ""),
        "pearson_prediction_vs_activity": target_summary.get("pearson_prediction_vs_activity", ""),
        "kendall_prediction_vs_activity": target_summary.get("kendall_prediction_vs_activity", ""),
        "top1_rank_match": target_summary.get("top1_rank_match", ""),
        "top3_overlap_count": target_summary.get("top3_overlap_count", ""),
        "top3_hit_count": target_summary.get("top3_hit_count", ""),
    }


def build_payload(
    *,
    target_id: str,
    shard_id: str,
    schema_payload: dict[str, Any] | None = None,
    source_payload: dict[str, Any] | None = None,
    example_payload: dict[str, Any] | None = None,
    actual_results_table: str = "",
    prediction_table: str = "",
    comparison_score_col: str = "",
    comparison_actual_col: str = "",
    comparison_out_json: str = "",
    comparison_out_csv: str = "",
    comparison_out_md: str = "",
    intake_out_md: str = DEFAULT_OUT_MD,
) -> dict[str, Any]:
    schema_rows = [dict(row) for row in ((schema_payload or {}).get("rows", []) or [])]
    example_rows = [
        dict(row)
        for row in ((example_payload or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip() == target_id and str(row.get("shard_id", "")).strip() == shard_id
    ]
    source_rows = sorted(
        [
            dict(row)
            for row in ((source_payload or {}).get("rows", []) or [])
            if str(row.get("target_id", "")).strip() == target_id
        ],
        key=_row_sort_key,
    )
    source_actual_rows = [dict(row) for row in source_rows if not _is_bootstrap(row)]
    source_bootstrap_rows = [dict(row) for row in source_rows if _is_bootstrap(row)]
    source_top3_rows = source_rows[:3]
    source_actual_top3_count = sum(1 for row in source_top3_rows if not _is_bootstrap(row))
    source_bulk_rank_span = _span([row.get("bulk_rank", "") for row in source_rows], formatter="int")
    source_bulk_score_span = _span([row.get("bulk_score", "") for row in source_rows], formatter="float")
    source_actual_row_fraction = round(len(source_actual_rows) / len(source_rows), 3) if source_rows else 0.0
    source_actual_feedback_completion_rate = (
        round(sum(_field_presence_rate(row, FEEDBACK_FIELDS) for row in source_actual_rows) / len(source_actual_rows), 3)
        if source_actual_rows
        else 0.0
    )
    source_actual_provenance_completion_rate = (
        round(
            sum(1 for row in source_actual_rows if _has_value(row.get("source_anchor")) and _has_value(row.get("source_url"))) / len(source_actual_rows),
            3,
        )
        if source_actual_rows
        else 0.0
    )
    source_actual_complete_row_count = sum(1 for row in source_actual_rows if _field_presence_count(row, FEEDBACK_FIELDS) == len(FEEDBACK_FIELDS))
    source_actual_feedback_bucket_counts: dict[str, int] = {}
    for row in source_actual_rows:
        fill_rate = _field_presence_rate(row, FEEDBACK_FIELDS)
        bucket = "complete" if fill_rate >= 0.9 else "strong" if fill_rate >= 0.75 else "partial" if fill_rate >= 0.5 else "sparse"
        source_actual_feedback_bucket_counts[bucket] = source_actual_feedback_bucket_counts.get(bucket, 0) + 1
    source_calibration_state = "full_actual_support" if source_actual_top3_count >= 3 else "partial_actual_support" if source_actual_top3_count > 0 else "actual_present_but_off_top3" if source_actual_rows else "bootstrap_only"
    source_calibration_readiness = _source_calibration_readiness(len(source_actual_rows), source_actual_top3_count)
    source_policy = _readiness_policy(source_calibration_readiness)
    registry_info = load_calibration_registry(source_payload)
    registry_summary = summarize_calibration_registry(registry_info)
    commercial_weight_default = _commercial_weight_from_readiness(source_calibration_readiness)
    registry_resolution = resolve_target_calibration_registry(
        target_id,
        registry_info=registry_info,
        defaults={
            "selected_threshold_A": None,
            "decision_class_update_hint": source_policy["decision_class_update_hint"],
            "commercial_weight": commercial_weight_default,
            "score_posture": source_policy["threshold_posture"],
            "threshold_posture": source_policy["threshold_posture"],
        },
        fallback_reason=(
            f"Default policy follows calibration_readiness={source_calibration_readiness}; "
            f"threshold_posture={source_policy['threshold_posture']}; "
            f"decision_class_update_hint={source_policy['decision_class_update_hint']}; "
            f"commercial_weight={commercial_weight_default:.2f}."
        ),
    )
    source_threshold_posture_effective = str(registry_resolution["threshold_posture"]).strip()
    source_decision_class_effective = str(registry_resolution["decision_class_update_hint"]).strip()
    source_commercial_weight_effective = _safe_float(registry_resolution["commercial_weight"], commercial_weight_default) or commercial_weight_default
    comparison_artifacts = _build_comparison_artifacts(
        target_id=target_id,
        source_rows=source_rows,
        actual_results_table=actual_results_table,
        prediction_table=prediction_table,
        comparison_score_col=comparison_score_col,
        comparison_actual_col=comparison_actual_col,
        comparison_out_json=comparison_out_json,
        comparison_out_csv=comparison_out_csv,
        comparison_out_md=comparison_out_md,
        intake_out_md=intake_out_md,
    )

    required_fields = [str(row.get("field_name", "")).strip() for row in schema_rows if bool(row.get("required", False))]
    optional_fields = [str(row.get("field_name", "")).strip() for row in schema_rows if not bool(row.get("required", False))]
    feedback_fields_requested = _build_feedback_field_order(schema_rows)

    rows = [
        {
            "target_id": target_id,
            "shard_id": shard_id,
            "required_fields": " ; ".join(required_fields),
            "optional_fields": " ; ".join(optional_fields),
            "feedback_fields_requested": _join_fields(tuple(feedback_fields_requested)),
            "feedback_field_groups": " | ".join(
                f"{group_name}: {_join_fields(field_names)}" for group_name, field_names in FEEDBACK_GROUPS.items()
            ),
            "existing_target_rows_in_source": len(source_rows),
            "source_actual_row_count": len(source_actual_rows),
            "source_bootstrap_row_count": len(source_bootstrap_rows),
            "source_actual_top3_count": source_actual_top3_count,
            "source_actual_row_fraction": source_actual_row_fraction,
            "source_actual_feedback_completion_rate": source_actual_feedback_completion_rate,
            "source_actual_provenance_completion_rate": source_actual_provenance_completion_rate,
            "source_actual_feedback_quality_bucket": (
                "complete"
                if source_actual_feedback_completion_rate >= 0.9
                else "strong"
                if source_actual_feedback_completion_rate >= 0.75
                else "partial"
                if source_actual_feedback_completion_rate >= 0.5
                else "sparse"
            ),
            "source_rank_span": source_bulk_rank_span,
            "source_score_span": source_bulk_score_span,
            "calibration_hint": "Capture the actual shard rows with stable bulk_rank and bulk_score provenance so target rerank can keep bootstrap-heavy targets conservative.",
            "feedback_request_note": "Ask for provenance first, then operational flags, then interpretation notes so rerank can trust actual rows without a schema migration.",
            "source_actual_complete_row_count": source_actual_complete_row_count,
            "source_calibration_readiness": source_calibration_readiness,
            "source_calibration_readiness_rank": source_policy["calibration_readiness_rank"],
            "source_threshold_posture": source_threshold_posture_effective,
            "source_threshold_posture_default": source_policy["threshold_posture"],
            "source_threshold_posture_source": registry_resolution["threshold_posture_source"],
            "source_threshold_posture_override_applied": bool(registry_resolution["threshold_posture_override_applied"]),
            "source_threshold_posture_rank": source_policy["threshold_posture_rank"],
            "source_decision_class_update_hint": source_decision_class_effective,
            "source_decision_class_update_hint_default": source_policy["decision_class_update_hint"],
            "source_decision_class_update_hint_source": registry_resolution["decision_class_update_hint_source"],
            "source_decision_class_update_hint_override_applied": bool(registry_resolution["decision_class_update_hint_override_applied"]),
            "source_decision_class_update_rank": source_policy["decision_class_update_rank"],
            "source_calibration_action_bucket": source_policy["calibration_action_bucket"],
            "source_calibration_action_bucket_rank": source_policy["calibration_action_bucket_rank"],
            "source_confidence_bucket": source_policy["confidence_bucket"],
            "source_confidence_bucket_rank": source_policy["confidence_bucket_rank"],
            "source_commercial_weight": round(source_commercial_weight_effective, 3),
            "source_commercial_weight_default": round(commercial_weight_default, 3),
            "source_commercial_weight_source": registry_resolution["commercial_weight_source"],
            "source_commercial_weight_override_applied": bool(registry_resolution["commercial_weight_override_applied"]),
            "source_score_posture": registry_resolution["score_posture"],
            "source_score_posture_default": source_policy["threshold_posture"],
            "source_score_posture_source": registry_resolution["score_posture_source"],
            "source_score_posture_override_applied": bool(registry_resolution["score_posture_override_applied"]),
            "source_selected_threshold_A": registry_resolution["selected_threshold_A"],
            "source_selected_threshold_A_default": registry_resolution["selected_threshold_A_default"],
            "source_selected_threshold_A_source": registry_resolution["selected_threshold_A_source"],
            "source_selected_threshold_A_override_applied": bool(registry_resolution["selected_threshold_A_override_applied"]),
            "source_calibration_registry_presence": registry_resolution["calibration_registry_presence"],
            "source_calibration_registry_match": bool(registry_resolution["calibration_registry_match"]),
            "source_calibration_registry_state": registry_resolution["calibration_registry_state"],
            "source_calibration_registry_source": registry_resolution["calibration_registry_source"],
            "source_calibration_registry_reason": registry_resolution["calibration_registry_reason"],
            "source_calibration_registry_reason_source": registry_resolution["calibration_registry_reason_source"],
            "source_calibration_registry_override_fields": registry_resolution["calibration_registry_override_fields"],
            "source_calibration_registry_entry_count": registry_resolution["calibration_registry_entry_count"],
            "source_calibration_registry_target_count": registry_resolution["calibration_registry_target_count"],
            "source_calibration_registry_override_target_count": registry_resolution["calibration_registry_override_target_count"],
            "source_calibration_registry_default_target_count": registry_resolution["calibration_registry_default_target_count"],
            "example_row_count_for_shard": len(example_rows),
            "example_feedback_completion_rate": (
                round(sum(_field_presence_rate(row, FEEDBACK_FIELDS) for row in example_rows) / len(example_rows), 3)
                if example_rows
                else 0.0
            ),
            "comparison_summary_status": comparison_artifacts.get("status", "not_requested"),
            "comparison_artifact_md": comparison_artifacts.get("artifact_md", ""),
            "comparison_merged_row_count": comparison_artifacts.get("merged_row_count", 0),
            "comparison_actual_value_kind": comparison_artifacts.get("actual_value_kind", ""),
            "comparison_prediction_score_col": comparison_artifacts.get("prediction_score_col", ""),
            "comparison_spearman_prediction_vs_activity": comparison_artifacts.get("spearman_prediction_vs_activity", ""),
            "comparison_top1_rank_match": comparison_artifacts.get("top1_rank_match", ""),
            "comparison_top3_overlap_count": comparison_artifacts.get("top3_overlap_count", ""),
            "comparison_top3_hit_count": comparison_artifacts.get("top3_hit_count", ""),
            "merge_command": "python3 tools/build_wetlab_broad_screen_bulk_results_source_merge.py --rows-json runs/wetlab_broad_screen_bulk_result_row_examples_current.json",
        }
    ]

    return {
        "summary": {
            "status": "wetlab_broad_screen_actual_result_intake_packet_ready",
            "target_id": target_id,
            "shard_id": shard_id,
            "required_field_count": len(required_fields),
            "optional_field_count": len(optional_fields),
            "feedback_field_count": len(feedback_fields_requested),
            "existing_target_rows_in_source": len(source_rows),
            "source_actual_row_count": len(source_actual_rows),
            "source_bootstrap_row_count": len(source_bootstrap_rows),
            "source_actual_top3_count": source_actual_top3_count,
            "source_actual_row_fraction": source_actual_row_fraction,
            "source_calibration_state": source_calibration_state,
            "source_actual_feedback_completion_rate": source_actual_feedback_completion_rate,
            "source_actual_provenance_completion_rate": source_actual_provenance_completion_rate,
            "source_actual_feedback_quality_bucket": (
                "complete"
                if source_actual_feedback_completion_rate >= 0.9
                else "strong"
                if source_actual_feedback_completion_rate >= 0.75
                else "partial"
                if source_actual_feedback_completion_rate >= 0.5
                else "sparse"
            ),
            "source_actual_complete_row_count": source_actual_complete_row_count,
            "source_calibration_readiness": source_calibration_readiness,
            "source_calibration_readiness_rank": source_policy["calibration_readiness_rank"],
            "source_threshold_posture": source_threshold_posture_effective,
            "source_threshold_posture_default": source_policy["threshold_posture"],
            "source_threshold_posture_source": registry_resolution["threshold_posture_source"],
            "source_threshold_posture_override_applied": bool(registry_resolution["threshold_posture_override_applied"]),
            "source_threshold_posture_rank": source_policy["threshold_posture_rank"],
            "source_decision_class_update_hint": source_decision_class_effective,
            "source_decision_class_update_hint_default": source_policy["decision_class_update_hint"],
            "source_decision_class_update_hint_source": registry_resolution["decision_class_update_hint_source"],
            "source_decision_class_update_hint_override_applied": bool(registry_resolution["decision_class_update_hint_override_applied"]),
            "source_decision_class_update_rank": source_policy["decision_class_update_rank"],
            "source_calibration_action_bucket": source_policy["calibration_action_bucket"],
            "source_calibration_action_bucket_rank": source_policy["calibration_action_bucket_rank"],
            "source_confidence_bucket": source_policy["confidence_bucket"],
            "source_confidence_bucket_rank": source_policy["confidence_bucket_rank"],
            "source_commercial_weight": round(source_commercial_weight_effective, 3),
            "source_commercial_weight_default": round(commercial_weight_default, 3),
            "source_commercial_weight_source": registry_resolution["commercial_weight_source"],
            "source_commercial_weight_override_applied": bool(registry_resolution["commercial_weight_override_applied"]),
            "source_score_posture": registry_resolution["score_posture"],
            "source_score_posture_default": source_policy["threshold_posture"],
            "source_score_posture_source": registry_resolution["score_posture_source"],
            "source_score_posture_override_applied": bool(registry_resolution["score_posture_override_applied"]),
            "source_selected_threshold_A": registry_resolution["selected_threshold_A"],
            "source_selected_threshold_A_default": registry_resolution["selected_threshold_A_default"],
            "source_selected_threshold_A_source": registry_resolution["selected_threshold_A_source"],
            "source_selected_threshold_A_override_applied": bool(registry_resolution["selected_threshold_A_override_applied"]),
            "source_calibration_registry_presence": registry_resolution["calibration_registry_presence"],
            "source_calibration_registry_match": bool(registry_resolution["calibration_registry_match"]),
            "source_calibration_registry_state": registry_resolution["calibration_registry_state"],
            "source_calibration_registry_source": registry_resolution["calibration_registry_source"],
            "source_calibration_registry_reason": registry_resolution["calibration_registry_reason"],
            "source_calibration_registry_reason_source": registry_resolution["calibration_registry_reason_source"],
            "source_calibration_registry_override_fields": registry_resolution["calibration_registry_override_fields"],
            "source_calibration_registry_entry_count": registry_resolution["calibration_registry_entry_count"],
            "source_calibration_registry_target_count": registry_resolution["calibration_registry_target_count"],
            "source_calibration_registry_override_target_count": registry_resolution["calibration_registry_override_target_count"],
            "source_calibration_registry_default_target_count": registry_resolution["calibration_registry_default_target_count"],
            "example_row_count_for_shard": len(example_rows),
            "comparison_summary_status": comparison_artifacts.get("status", "not_requested"),
            "comparison_artifact_json": comparison_artifacts.get("artifact_json", ""),
            "comparison_artifact_csv": comparison_artifacts.get("artifact_csv", ""),
            "comparison_artifact_md": comparison_artifacts.get("artifact_md", ""),
            "comparison_merged_row_count": comparison_artifacts.get("merged_row_count", 0),
            "comparison_actual_value_kind": comparison_artifacts.get("actual_value_kind", ""),
            "comparison_prediction_score_col": comparison_artifacts.get("prediction_score_col", ""),
            "comparison_spearman_prediction_vs_activity": comparison_artifacts.get("spearman_prediction_vs_activity", ""),
            "comparison_pearson_prediction_vs_activity": comparison_artifacts.get("pearson_prediction_vs_activity", ""),
            "comparison_kendall_prediction_vs_activity": comparison_artifacts.get("kendall_prediction_vs_activity", ""),
            "comparison_top1_rank_match": comparison_artifacts.get("top1_rank_match", ""),
            "comparison_top3_overlap_count": comparison_artifacts.get("top3_overlap_count", ""),
            "comparison_top3_hit_count": comparison_artifacts.get("top3_hit_count", ""),
            "next_required_step": "Fill a real shard-result JSON that matches the schema, including seed_status, first_contact_use_mode, provenance, and selectivity notes, then run the merge builder and rerank refresh chain with the calibration readiness, threshold posture, decision-class hints, commercial weights, and calibration registry overrides preserved.",
        },
        "structured": {
            "schema_artifact": "runs/wetlab_broad_screen_bulk_result_source_schema_current.md",
            "source_artifact": "runs/wetlab_broad_screen_bulk_results_source_current.md",
            "example_rows_artifact": "runs/wetlab_broad_screen_bulk_result_row_examples_current.md",
            "calibration_fields": "bulk_rank ; bulk_score ; seed_status ; first_contact_use_mode ; source_anchor ; source_url",
            "feedback_fields_requested": "shard_id ; seed_status ; first_contact_use_mode ; vendor_check_required ; cost_check_required ; selectivity_note ; usage_rationale ; must_not_do ; source_anchor ; source_url",
            "feedback_field_groups": "provenance: shard_id ; seed_status ; source_anchor ; source_url | operational_flags: first_contact_use_mode ; vendor_check_required ; cost_check_required | interpretation: selectivity_note ; usage_rationale ; must_not_do",
            "feedback_loop_note": "The merged source rows should keep actual-versus-bootstrap provenance, calibration readiness, threshold posture, decision-class hints, commercial weights, and calibration registry overrides so rerank can calibrate thresholds later without a separate schema migration.",
            "comparison_note": "If --actual-results-table is provided, this intake builder also emits a wet-lab-vs-prediction comparison summary beside the intake artifact.",
        },
        "calibration": {
            "target_id": target_id,
            "source_actual_row_count": len(source_actual_rows),
            "source_bootstrap_row_count": len(source_bootstrap_rows),
            "source_actual_top3_count": source_actual_top3_count,
            "source_actual_row_fraction": source_actual_row_fraction,
            "source_bulk_rank_span": source_bulk_rank_span,
            "source_bulk_score_span": source_bulk_score_span,
            "source_calibration_state": source_calibration_state,
            "source_actual_feedback_completion_rate": source_actual_feedback_completion_rate,
            "source_actual_provenance_completion_rate": source_actual_provenance_completion_rate,
            "source_actual_complete_row_count": source_actual_complete_row_count,
            "source_actual_feedback_bucket_counts": source_actual_feedback_bucket_counts,
            "source_calibration_readiness": source_calibration_readiness,
            "source_calibration_readiness_rank": source_policy["calibration_readiness_rank"],
            "source_threshold_posture": source_threshold_posture_effective,
            "source_threshold_posture_default": source_policy["threshold_posture"],
            "source_threshold_posture_source": registry_resolution["threshold_posture_source"],
            "source_threshold_posture_override_applied": bool(registry_resolution["threshold_posture_override_applied"]),
            "source_threshold_posture_rank": source_policy["threshold_posture_rank"],
            "source_decision_class_update_hint": source_decision_class_effective,
            "source_decision_class_update_hint_default": source_policy["decision_class_update_hint"],
            "source_decision_class_update_hint_source": registry_resolution["decision_class_update_hint_source"],
            "source_decision_class_update_hint_override_applied": bool(registry_resolution["decision_class_update_hint_override_applied"]),
            "source_decision_class_update_rank": source_policy["decision_class_update_rank"],
            "source_calibration_action_bucket": source_policy["calibration_action_bucket"],
            "source_calibration_action_bucket_rank": source_policy["calibration_action_bucket_rank"],
            "source_confidence_bucket": source_policy["confidence_bucket"],
            "source_confidence_bucket_rank": source_policy["confidence_bucket_rank"],
            "source_commercial_weight": round(source_commercial_weight_effective, 3),
            "source_commercial_weight_default": round(commercial_weight_default, 3),
            "source_commercial_weight_source": registry_resolution["commercial_weight_source"],
            "source_commercial_weight_override_applied": bool(registry_resolution["commercial_weight_override_applied"]),
            "source_score_posture": registry_resolution["score_posture"],
            "source_score_posture_default": source_policy["threshold_posture"],
            "source_score_posture_source": registry_resolution["score_posture_source"],
            "source_score_posture_override_applied": bool(registry_resolution["score_posture_override_applied"]),
            "source_selected_threshold_A": registry_resolution["selected_threshold_A"],
            "source_selected_threshold_A_default": registry_resolution["selected_threshold_A_default"],
            "source_selected_threshold_A_source": registry_resolution["selected_threshold_A_source"],
            "source_selected_threshold_A_override_applied": bool(registry_resolution["selected_threshold_A_override_applied"]),
            "source_calibration_registry_presence": registry_resolution["calibration_registry_presence"],
            "source_calibration_registry_match": bool(registry_resolution["calibration_registry_match"]),
            "source_calibration_registry_state": registry_resolution["calibration_registry_state"],
            "source_calibration_registry_source": registry_resolution["calibration_registry_source"],
            "source_calibration_registry_reason": registry_resolution["calibration_registry_reason"],
            "source_calibration_registry_reason_source": registry_resolution["calibration_registry_reason_source"],
            "source_calibration_registry_override_fields": registry_resolution["calibration_registry_override_fields"],
            "source_calibration_registry_entry_count": registry_resolution["calibration_registry_entry_count"],
            "source_calibration_registry_target_count": registry_resolution["calibration_registry_target_count"],
            "source_calibration_registry_override_target_count": registry_resolution["calibration_registry_override_target_count"],
            "source_calibration_registry_default_target_count": registry_resolution["calibration_registry_default_target_count"],
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an intake packet for a real broad-screen shard result row set.")
    parser.add_argument("--target-id", default="CA IX")
    parser.add_argument("--shard-id", default="04_of_20")
    parser.add_argument("--schema-json", default=DEFAULT_SCHEMA_JSON)
    parser.add_argument("--source-json", default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--example-rows-json", default=DEFAULT_EXAMPLE_ROWS_JSON)
    parser.add_argument("--actual-results-table", default="")
    parser.add_argument("--prediction-table", default="")
    parser.add_argument("--comparison-score-col", default="")
    parser.add_argument("--comparison-actual-col", default="")
    parser.add_argument("--comparison-out-json", default="")
    parser.add_argument("--comparison-out-csv", default="")
    parser.add_argument("--comparison-out-md", default="")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Actual Result Intake Packet",
        build_payload(
            target_id=args.target_id,
            shard_id=args.shard_id,
            schema_payload=maybe_load_json(args.schema_json),
            source_payload=maybe_load_json(args.source_json),
            example_payload=maybe_load_json(args.example_rows_json),
            actual_results_table=args.actual_results_table,
            prediction_table=args.prediction_table,
            comparison_score_col=args.comparison_score_col,
            comparison_actual_col=args.comparison_actual_col,
            comparison_out_json=args.comparison_out_json,
            comparison_out_csv=args.comparison_out_csv,
            comparison_out_md=args.comparison_out_md,
            intake_out_md=args.out_md,
        ),
    )
