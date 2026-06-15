#!/usr/bin/env python3
"""Read-only R9 CV feature-extrapolation probe for public-benchmark scoring."""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_score_variant_probe import (
    DEFAULT_CANDIDATE_FILL_JSON,
    DEFAULT_EXISTING_MATERIALIZATION_CSV,
    ROOT,
    _candidate_feature_rows,
    _display,
    _existing_feature_rows,
    _float,
    _format_float,
    _read_json,
    _resolve,
)
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
)

DEFAULT_CROSS_VALIDATION_JSON = "config/refine_tier_public_benchmark_calibration_cross_validation_probe_current.json"
DEFAULT_RESIDUAL_PRIORITY_JSON = (
    "config/refine_tier_public_benchmark_residual_metric_payload_priority_packet_current.json"
)
DEFAULT_SCORE_DECOMPOSITION_JSON = (
    "config/refine_tier_public_benchmark_score_variant_failure_decomposition_current.json"
)
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_cv_feature_extrapolation_probe_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_cv_feature_extrapolation_probe_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_cv_feature_extrapolation_probe_current.md"

HIGH_ERROR_THRESHOLD = 10
FEATURE_EXTRAPOLATION_Z_THRESHOLD = 2.0
FEATURE_SHIFT_WARNING_Z_THRESHOLD = 1.5

CLAIM_BOUNDARY = (
    "R9 CV feature-extrapolation probe only compares locked leave-one-target-out residual rows against "
    "the feature distribution available in each training fold. It does not train new production models, "
    "rewrite scores, write reviewed metric payloads, approve receipts, promote canonical intake, change "
    "production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external "
    "state."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return (_text(row.get("target_id")), _text(row.get("pose_id")))


def _index_rows(rows: Any) -> dict[tuple[str, str], dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = _key(row)
        if key[0] and key[1]:
            out[key] = row
    return out


def _group_rows(rows: Any) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = _key(row)
        if key[0] and key[1]:
            grouped[key].append(row)
    return dict(grouped)


def _metric_names(rows: list[dict[str, Any]]) -> str:
    return ";".join(_text(row.get("metric_name")) for row in rows if _text(row.get("metric_name")))


def _gap_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(_text(row.get("operator_gap_class")) or "unknown" for row in rows)


def _locked_model_features(cv_summary: dict[str, Any], cv_model_rows: Any) -> tuple[str, ...]:
    locked_model_id = _text(cv_summary.get("locked_cv_model_id"))
    if isinstance(cv_model_rows, list):
        for row in cv_model_rows:
            if not isinstance(row, dict):
                continue
            if _text(row.get("model_id")) == locked_model_id:
                features = [
                    feature.strip()
                    for feature in _text(row.get("feature_names")).split(";")
                    if feature.strip()
                ]
                if features:
                    return tuple(features)
    return ("contact_per_atom", "pose_atom_count")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if not values:
        return 1.0
    mean = _mean(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std = math.sqrt(max(0.0, variance))
    return std if std >= 1e-12 else 1.0


def _feature_value(row: dict[str, Any], feature: str) -> float | None:
    value = _float(row.get(feature))
    return None if value is None else float(value)


def _feature_diagnostics(
    *,
    row: dict[str, Any],
    train_rows: list[dict[str, Any]],
    features: tuple[str, ...],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for feature in features:
        value = _feature_value(row, feature)
        train_values = [
            feature_value
            for train_row in train_rows
            for feature_value in [_feature_value(train_row, feature)]
            if feature_value is not None
        ]
        if value is None or not train_values:
            diagnostics.append(
                {
                    "feature": feature,
                    "value": "",
                    "train_mean": "",
                    "train_std": "",
                    "train_min": "",
                    "train_max": "",
                    "z_score": "",
                    "abs_z_score": 0.0,
                    "outside_train_range": False,
                    "range_gap": "",
                }
            )
            continue
        train_min = min(train_values)
        train_max = max(train_values)
        train_mean = _mean(train_values)
        train_std = _std(train_values)
        z_score = (value - train_mean) / train_std
        outside = value < train_min or value > train_max
        range_gap = train_min - value if value < train_min else (value - train_max if value > train_max else 0.0)
        diagnostics.append(
            {
                "feature": feature,
                "value": _format_float(value),
                "train_mean": _format_float(train_mean),
                "train_std": _format_float(train_std),
                "train_min": _format_float(train_min),
                "train_max": _format_float(train_max),
                "z_score": _format_float(z_score),
                "abs_z_score": abs(z_score),
                "outside_train_range": outside,
                "range_gap": _format_float(range_gap),
            }
        )
    top = max(diagnostics, key=lambda item: float(item.get("abs_z_score") or 0.0), default={})
    outside_features = [item["feature"] for item in diagnostics if bool(item.get("outside_train_range"))]
    max_abs_z = float(top.get("abs_z_score") or 0.0)
    summary = {
        "feature_diagnostics_json": json.dumps(diagnostics, sort_keys=True, separators=(",", ":")),
        "top_feature_shift_name": _text(top.get("feature")),
        "top_feature_shift_abs_z": _format_float(max_abs_z),
        "top_feature_shift_z": _text(top.get("z_score")),
        "outside_train_range_feature_count": len(outside_features),
        "outside_train_range_features": ";".join(outside_features),
        "feature_extrapolation": bool(
            outside_features or max_abs_z >= FEATURE_EXTRAPOLATION_Z_THRESHOLD
        ),
        "feature_shift_warning": bool(max_abs_z >= FEATURE_SHIFT_WARNING_Z_THRESHOLD),
    }
    return diagnostics, summary


def _rank_direction(variant_rank: int, reference_rank: int) -> str:
    if not variant_rank or not reference_rank:
        return "unknown"
    if variant_rank < reference_rank:
        return "overranked_stronger_than_reference"
    if variant_rank > reference_rank:
        return "underranked_weaker_than_reference"
    return "rank_aligned"


def _residual_class(*, locked_error: int, error_delta: int, feature_extrapolation: bool, missing_payloads: int) -> str:
    if locked_error >= HIGH_ERROR_THRESHOLD and feature_extrapolation:
        return "high_error_feature_extrapolation"
    if locked_error >= HIGH_ERROR_THRESHOLD:
        return "high_error_in_distribution"
    if error_delta > 0 and feature_extrapolation:
        return "cv_regression_feature_extrapolation"
    if error_delta > 0:
        return "cv_regression_in_distribution"
    if missing_payloads > 0:
        return "payload_receipt_gap_monitor"
    return "monitor"


def _next_step(row: dict[str, Any]) -> str:
    residual_class = _text(row.get("feature_extrapolation_residual_class"))
    gaps = _text(row.get("operator_gap_classes"))
    if "existing_metric_payload_present_without_operator_receipt" in gaps:
        return "Add operator receipt coverage for existing metric-source JSON before using this row as reviewed evidence."
    if residual_class == "high_error_feature_extrapolation":
        return "Add/review target-held-out evidence near this feature range before adding stronger calibration terms."
    if residual_class == "high_error_in_distribution":
        return "Prioritize metric payload, pose assignment, and model-form review; fold feature range alone does not explain the residual."
    if residual_class == "cv_regression_feature_extrapolation":
        return "Guard calibration against this fold feature shift before considering descriptor promotion."
    if "operator_receipt_blocked_placeholders" in gaps:
        return "Fill and review blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose."
    return "Monitor after higher-priority residual and payload rows are closed."


def _priority_sort_key(row: dict[str, Any]) -> tuple[int, int, float, int, str]:
    class_weight = {
        "high_error_in_distribution": 5,
        "high_error_feature_extrapolation": 5,
        "cv_regression_feature_extrapolation": 4,
        "cv_regression_in_distribution": 3,
        "payload_receipt_gap_monitor": 2,
        "monitor": 1,
    }.get(_text(row.get("feature_extrapolation_residual_class")), 0)
    return (
        class_weight,
        _int(row.get("locked_cv_rank_abs_error")),
        _float(row.get("top_feature_shift_abs_z")) or 0.0,
        _int(row.get("operator_receipt_blocked_payload_count")) + _int(row.get("operator_receipt_missing_payload_count")),
        _text(row.get("target_id")),
    )


def build_refine_tier_public_benchmark_cv_feature_extrapolation_probe(
    *,
    cross_validation_json: str | Path = DEFAULT_CROSS_VALIDATION_JSON,
    candidate_fill_json: str | Path = DEFAULT_CANDIDATE_FILL_JSON,
    existing_materialization_csv: str | Path = DEFAULT_EXISTING_MATERIALIZATION_CSV,
    residual_priority_json: str | Path = DEFAULT_RESIDUAL_PRIORITY_JSON,
    score_decomposition_json: str | Path = DEFAULT_SCORE_DECOMPOSITION_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    cv_payload, cv_present = _read_json(cross_validation_json, root=root_path)
    candidate_payload, candidate_present = _read_json(candidate_fill_json, root=root_path)
    priority_payload, priority_present = _read_json(residual_priority_json, root=root_path)
    decomposition_payload, decomposition_present = _read_json(score_decomposition_json, root=root_path)
    cv_summary = cv_payload.get("summary") if isinstance(cv_payload.get("summary"), dict) else {}
    features = _locked_model_features(cv_summary, cv_payload.get("cv_model_rows"))
    feature_rows = [
        *_existing_feature_rows(existing_materialization_csv, root=root_path),
        *_candidate_feature_rows(candidate_payload),
    ]
    feature_by_key = _index_rows(feature_rows)
    locked_rows = [row for row in cv_payload.get("locked_cv_rank_residual_rows", []) if isinstance(row, dict)]
    baseline_rows = _index_rows(cv_payload.get("baseline_rank_residual_rows"))
    priority_rows = _group_rows(priority_payload.get("priority_rows"))
    decomposition_rows = _index_rows(decomposition_payload.get("decomposition_rows"))

    rows: list[dict[str, Any]] = []
    for locked in locked_rows:
        key = _key(locked)
        feature_row = feature_by_key.get(key)
        if not feature_row:
            continue
        train_rows = [row for row in feature_rows if _text(row.get("target_id")) != key[0]]
        _diagnostics, feature_summary = _feature_diagnostics(
            row=feature_row,
            train_rows=train_rows,
            features=features,
        )
        baseline = baseline_rows.get(key, {})
        priority = priority_rows.get(key, [])
        gaps = _gap_counts(priority)
        decomposition = decomposition_rows.get(key, {})
        locked_error = _int(locked.get("rank_abs_error"))
        baseline_error = _int(baseline.get("rank_abs_error"))
        error_delta = locked_error - baseline_error
        missing_payloads = sum(
            count for gap, count in gaps.items() if "missing" in gap or "without_operator_receipt" in gap
        )
        row = {
            "feature_extrapolation_priority_rank": 0,
            "target_id": key[0],
            "pose_id": key[1],
            "work_order_id": _text(feature_row.get("work_order_id")),
            "source": _text(locked.get("source")) or _text(feature_row.get("source")),
            "split": _text(locked.get("split")) or _text(feature_row.get("split")),
            "locked_cv_model_id": _text(cv_summary.get("locked_cv_model_id")),
            "locked_cv_feature_names": ";".join(features),
            "baseline_proxy": _text(locked.get("baseline_proxy")),
            "locked_cv_proxy": _text(locked.get("variant_proxy")),
            "reference_deltaG": _text(locked.get("reference")),
            "locked_cv_rank": _int(locked.get("variant_rank")),
            "reference_rank": _int(locked.get("reference_rank")),
            "locked_cv_rank_abs_error": locked_error,
            "baseline_rank_abs_error": baseline_error,
            "rank_abs_error_delta_from_baseline": error_delta,
            "cv_rank_error_vs_baseline": "worse" if error_delta > 0 else ("better" if error_delta < 0 else "same"),
            "rank_direction": _rank_direction(_int(locked.get("variant_rank")), _int(locked.get("reference_rank"))),
            **feature_summary,
            "feature_extrapolation_residual_class": _residual_class(
                locked_error=locked_error,
                error_delta=error_delta,
                feature_extrapolation=bool(feature_summary.get("feature_extrapolation")),
                missing_payloads=missing_payloads,
            ),
            "decomposition_class": _text(decomposition.get("decomposition_class")),
            "metric_payload_priority_row_count": len(priority),
            "required_metric_names": _metric_names(priority),
            "operator_receipt_blocked_payload_count": gaps.get("operator_receipt_blocked_placeholders", 0),
            "operator_receipt_missing_payload_count": missing_payloads,
            "existing_metric_source_artifact_present_without_receipt_count": gaps.get(
                "existing_metric_payload_present_without_operator_receipt", 0
            ),
            "operator_gap_classes": ";".join(f"{gap}:{count}" for gap, count in sorted(gaps.items())),
            "payload_write_allowed": False,
            "canonical_intake_promotion_allowed": False,
            "claim_promotion_allowed": False,
            "production_score_mutation_allowed": False,
            "external_state_mutated": False,
        }
        row["next_science_step"] = _next_step(row)
        rows.append(row)

    sorted_rows = sorted(rows, key=_priority_sort_key, reverse=True)
    for index, row in enumerate(sorted_rows, start=1):
        row["feature_extrapolation_priority_rank"] = index

    locked_p05 = _float(cv_summary.get("locked_cv_bootstrap_p05"))
    high_error_rows = [row for row in sorted_rows if _int(row.get("locked_cv_rank_abs_error")) >= HIGH_ERROR_THRESHOLD]
    feature_extrapolation_rows = [row for row in sorted_rows if bool(row.get("feature_extrapolation"))]
    feature_warning_rows = [row for row in sorted_rows if bool(row.get("feature_shift_warning"))]
    top_shift = max(
        sorted_rows,
        key=lambda row: _float(row.get("top_feature_shift_abs_z")) or 0.0,
        default={},
    )
    top_in_distribution_high_error = next(
        (
            row
            for row in sorted_rows
            if row.get("feature_extrapolation_residual_class") == "high_error_in_distribution"
        ),
        {},
    )
    summary = {
        "packet_type": "refine_tier_public_benchmark_cv_feature_extrapolation_probe",
        "status": (
            "refine_tier_public_benchmark_cv_feature_extrapolation_probe_ready"
            if cv_present and candidate_present and sorted_rows
            else "blocked_refine_tier_public_benchmark_cv_feature_extrapolation_probe"
        ),
        "cross_validation_json": _display(cross_validation_json, root=root_path),
        "cross_validation_present": cv_present,
        "candidate_fill_json": _display(candidate_fill_json, root=root_path),
        "candidate_fill_present": candidate_present,
        "existing_materialization_csv": _display(existing_materialization_csv, root=root_path),
        "residual_priority_json": _display(residual_priority_json, root=root_path),
        "residual_priority_json_present": priority_present,
        "score_decomposition_json": _display(score_decomposition_json, root=root_path),
        "score_decomposition_json_present": decomposition_present,
        "locked_cv_model_id": cv_summary.get("locked_cv_model_id", ""),
        "locked_cv_feature_names": ";".join(features),
        "locked_cv_bootstrap_p05": locked_p05,
        "locked_cv_bootstrap_p05_gap_to_claim_grade": (
            None if locked_p05 is None else MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW - locked_p05
        ),
        "residual_input_row_count": len(locked_rows),
        "feature_row_count": len(feature_rows),
        "feature_extrapolation_probe_row_count": len(sorted_rows),
        "feature_extrapolation_row_count": len(feature_extrapolation_rows),
        "feature_shift_warning_row_count": len(feature_warning_rows),
        "high_error_row_count": len(high_error_rows),
        "high_error_feature_extrapolation_count": sum(
            1 for row in sorted_rows if row.get("feature_extrapolation_residual_class") == "high_error_feature_extrapolation"
        ),
        "high_error_in_distribution_count": sum(
            1 for row in sorted_rows if row.get("feature_extrapolation_residual_class") == "high_error_in_distribution"
        ),
        "cv_regression_row_count": sum(1 for row in sorted_rows if row.get("cv_rank_error_vs_baseline") == "worse"),
        "cv_regression_feature_extrapolation_count": sum(
            1 for row in sorted_rows if row.get("feature_extrapolation_residual_class") == "cv_regression_feature_extrapolation"
        ),
        "operator_receipt_blocked_payload_count": sum(
            _int(row.get("operator_receipt_blocked_payload_count")) for row in sorted_rows
        ),
        "operator_receipt_missing_payload_count": sum(
            _int(row.get("operator_receipt_missing_payload_count")) for row in sorted_rows
        ),
        "existing_metric_source_artifact_present_without_receipt_count": sum(
            _int(row.get("existing_metric_source_artifact_present_without_receipt_count")) for row in sorted_rows
        ),
        "top_feature_shift_target_id": top_shift.get("target_id", ""),
        "top_feature_shift_pose_id": top_shift.get("pose_id", ""),
        "top_feature_shift_name": top_shift.get("top_feature_shift_name", ""),
        "top_feature_shift_abs_z": top_shift.get("top_feature_shift_abs_z", ""),
        "top_in_distribution_high_error_target_id": top_in_distribution_high_error.get("target_id", ""),
        "top_in_distribution_high_error_pose_id": top_in_distribution_high_error.get("pose_id", ""),
        "top_priority_target_id": sorted_rows[0].get("target_id", "") if sorted_rows else "",
        "top_priority_pose_id": sorted_rows[0].get("pose_id", "") if sorted_rows else "",
        "top_priority_residual_class": sorted_rows[0].get("feature_extrapolation_residual_class", "") if sorted_rows else "",
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use feature-extrapolation rows to separate descriptor coverage gaps from in-distribution residuals; "
            "review top metric payloads and add independent/operator-reviewed evidence before rerunning CV and "
            "bootstrap gates. Do not promote scoring while p05 remains below 0.5 or payload receipts remain blocked."
        ),
    }
    return {"summary": summary, "feature_extrapolation_rows": sorted_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 CV Feature-Extrapolation Probe",
        "",
        f"- status: `{s['status']}`",
        f"- locked_cv_model_id: `{s['locked_cv_model_id']}`",
        f"- locked_cv_feature_names: `{s['locked_cv_feature_names']}`",
        f"- locked_cv_bootstrap_p05: `{s['locked_cv_bootstrap_p05']}`",
        f"- locked_cv_bootstrap_p05_gap_to_claim_grade: `{s['locked_cv_bootstrap_p05_gap_to_claim_grade']}`",
        f"- feature_extrapolation_probe_row_count: `{s['feature_extrapolation_probe_row_count']}`",
        f"- high_error_row_count: `{s['high_error_row_count']}`",
        f"- high_error_feature_extrapolation_count: `{s['high_error_feature_extrapolation_count']}`",
        f"- high_error_in_distribution_count: `{s['high_error_in_distribution_count']}`",
        f"- feature_extrapolation_row_count: `{s['feature_extrapolation_row_count']}`",
        f"- feature_shift_warning_row_count: `{s['feature_shift_warning_row_count']}`",
        f"- operator_receipt_blocked_payload_count: `{s['operator_receipt_blocked_payload_count']}`",
        f"- operator_receipt_missing_payload_count: `{s['operator_receipt_missing_payload_count']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Top Rows",
        "",
        "| rank | target | pose | split | class | cv err | delta | top feature | abs z | outside | gaps | next |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["feature_extrapolation_rows"][:12]:
        lines.append(
            f"| `{row['feature_extrapolation_priority_rank']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['split']}` | `{row['feature_extrapolation_residual_class']}` | "
            f"`{row['locked_cv_rank_abs_error']}` | `{row['rank_abs_error_delta_from_baseline']}` | "
            f"`{row['top_feature_shift_name']}` | `{row['top_feature_shift_abs_z']}` | "
            f"`{row['outside_train_range_features']}` | `{row['operator_gap_classes']}` | {row['next_science_step']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 CV feature-extrapolation probe.")
    parser.add_argument("--cross-validation-json", default=DEFAULT_CROSS_VALIDATION_JSON)
    parser.add_argument("--candidate-fill-json", default=DEFAULT_CANDIDATE_FILL_JSON)
    parser.add_argument("--existing-materialization-csv", default=DEFAULT_EXISTING_MATERIALIZATION_CSV)
    parser.add_argument("--residual-priority-json", default=DEFAULT_RESIDUAL_PRIORITY_JSON)
    parser.add_argument("--score-decomposition-json", default=DEFAULT_SCORE_DECOMPOSITION_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_cv_feature_extrapolation_probe(
        cross_validation_json=args.cross_validation_json,
        candidate_fill_json=args.candidate_fill_json,
        existing_materialization_csv=args.existing_materialization_csv,
        residual_priority_json=args.residual_priority_json,
        score_decomposition_json=args.score_decomposition_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["feature_extrapolation_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
