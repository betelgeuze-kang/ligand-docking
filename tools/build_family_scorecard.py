#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


METRIC_NAMES = [
    "row_count",
    "positive_count",
    "negative_count",
    "score_coverage",
    "auroc",
    "average_precision",
    "top_k_hit_rate",
    "enrichment_at_k",
    "score_min",
    "score_max",
    "score_mean",
    "score_unique_count",
    "score_unique_ratio",
    "score_tie_ratio",
    "score_mode_ratio",
]

BASELINE_METRIC_NAMES = [
    "auroc",
    "average_precision",
    "top_k_hit_rate",
    "enrichment_at_k",
    "score_coverage",
]

ROW_IDENTITY_SCHEMA_VERSION = "family-scorecard-row-identity-v1"

BASELINE_BLOCKING_REASONS = {
    "baseline_identity_columns_mismatch",
    "baseline_row_identity_schema_version_mismatch",
    "invalid_baseline_comparison_metric",
    "missing_baseline_identity_columns",
    "missing_baseline_lower_better",
    "missing_baseline_families",
    "missing_baseline_family",
    "missing_baseline_metric",
    "missing_baseline_row_identity_sha256",
    "missing_baseline_row_identity_schema_version",
    "missing_baseline_summary",
    "missing_baseline_top_k",
    "null_baseline_comparison_metric",
    "baseline_row_identity_mismatch",
}

SCORECARD_BLOCKING_REASONS = {
    "duplicate_row_identity",
    "missing_required_family",
}


def _parse_label(value: object) -> int:
    text = str(value).strip()
    if text not in {"0", "1"}:
        raise ValueError(f"label must be 0 or 1, got {value!r}")
    return int(text)


def _parse_score(value: object) -> float | None:
    text = str(value).strip()
    if not text:
        return None
    score = float(text)
    return score if math.isfinite(score) else None


def _read_rows(
    predictions_csv: Path,
    *,
    family_col: str,
    label_col: str,
    score_col: str,
    identity_cols: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with predictions_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {family_col, label_col, score_col}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing required CSV columns: {', '.join(sorted(missing))}")
        missing_identity = set(identity_cols).difference(reader.fieldnames or [])
        if missing_identity:
            raise ValueError(
                f"missing identity CSV columns: {', '.join(sorted(missing_identity))}"
            )
        for line_number, row in enumerate(reader, start=2):
            family = str(row[family_col]).strip()
            if not family:
                raise ValueError(
                    f"blank family value in row {line_number}, column {family_col}"
                )
            if family.lower() == "overall":
                raise ValueError(
                    f"reserved family value in row {line_number}, column {family_col}: {family}"
                )
            identity: dict[str, str] = {}
            for identity_col in identity_cols:
                value = str(row[identity_col]).strip()
                if not value:
                    raise ValueError(
                        f"blank identity value in row {line_number}, column {identity_col}"
                    )
                identity[identity_col] = value
            rows.append(
                {
                    "family": family,
                    "label": _parse_label(row[label_col]),
                    "score": _parse_score(row[score_col]),
                    "identity": identity,
                }
            )
    return rows


def _is_positive_better(positive: float, negative: float, *, lower_better: bool) -> float:
    if positive == negative:
        return 0.5
    if lower_better:
        return 1.0 if positive < negative else 0.0
    return 1.0 if positive > negative else 0.0


def _auroc(scored_rows: list[dict[str, Any]], *, lower_better: bool) -> float | None:
    positives = [row["score"] for row in scored_rows if row["label"] == 1]
    negatives = [row["score"] for row in scored_rows if row["label"] == 0]
    if not positives or not negatives:
        return None

    wins = 0.0
    for positive in positives:
        for negative in negatives:
            wins += _is_positive_better(positive, negative, lower_better=lower_better)
    return wins / (len(positives) * len(negatives))


def _average_precision(scored_rows: list[dict[str, Any]], *, lower_better: bool) -> float | None:
    positive_count = sum(1 for row in scored_rows if row["label"] == 1)
    negative_count = sum(1 for row in scored_rows if row["label"] == 0)
    if positive_count == 0 or negative_count == 0:
        return None

    sorted_rows = sorted(scored_rows, key=lambda row: row["score"], reverse=not lower_better)
    precision_sum = 0.0
    positives_seen = 0
    for rank, row in enumerate(sorted_rows, start=1):
        if row["label"] == 1:
            positives_seen += 1
            precision_sum += positives_seen / rank
    return precision_sum / positive_count


def _score_stats(scores: list[float]) -> tuple[float | None, float | None, float | None]:
    if not scores:
        return None, None, None
    return min(scores), max(scores), sum(scores) / len(scores)


def _score_resolution_metrics(scores: list[float], row_count: int) -> dict[str, Any]:
    if row_count <= 0 or not scores:
        return {
            "score_unique_count": 0,
            "score_unique_ratio": None,
            "score_tie_ratio": None,
            "score_mode_ratio": None,
        }
    rounded_counts: dict[float, int] = {}
    for score in scores:
        rounded = round(score, 12)
        rounded_counts[rounded] = rounded_counts.get(rounded, 0) + 1
    unique_count = len(rounded_counts)
    unique_ratio = unique_count / row_count
    return {
        "score_unique_count": unique_count,
        "score_unique_ratio": unique_ratio,
        "score_tie_ratio": 1.0 - unique_ratio,
        "score_mode_ratio": max(rounded_counts.values()) / row_count,
    }


def _family_metrics(
    family: str,
    rows: list[dict[str, Any]],
    *,
    top_k: int,
    lower_better: bool,
    warnings: list[dict[str, str]],
) -> dict[str, Any]:
    row_count = len(rows)
    positive_count = sum(1 for row in rows if row["label"] == 1)
    negative_count = sum(1 for row in rows if row["label"] == 0)
    scored_rows = [row for row in rows if row["score"] is not None]
    scores = [row["score"] for row in scored_rows]
    scored_positive_count = sum(1 for row in scored_rows if row["label"] == 1)
    scored_negative_count = sum(1 for row in scored_rows if row["label"] == 0)

    auroc = _auroc(scored_rows, lower_better=lower_better)
    average_precision = _average_precision(scored_rows, lower_better=lower_better)
    if scored_positive_count == 0 or scored_negative_count == 0:
        warnings.append(
            {
                "family": family,
                "metric": "auroc,average_precision",
                "reason": "single_class_labels",
            }
        )
    if len(scored_rows) < row_count:
        warnings.append(
            {
                "family": family,
                "metric": "score_coverage",
                "reason": "missing_or_non_finite_scores",
            }
        )

    sorted_rows = sorted(scored_rows, key=lambda row: row["score"], reverse=not lower_better)
    k = min(top_k, len(sorted_rows))
    top_rows = sorted_rows[:k]
    top_k_hit_rate = None
    enrichment_at_k = None
    if k > 0:
        top_positive_rate = sum(1 for row in top_rows if row["label"] == 1) / k
        base_positive_rate = scored_positive_count / len(scored_rows)
        top_k_hit_rate = top_positive_rate
        enrichment_at_k = top_positive_rate / base_positive_rate if base_positive_rate > 0 else None

    score_min, score_max, score_mean = _score_stats(scores)
    score_resolution = _score_resolution_metrics(scores, row_count)
    return {
        "row_count": row_count,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "score_coverage": (len(scored_rows) / row_count) if row_count else None,
        "auroc": auroc,
        "average_precision": average_precision,
        "top_k_hit_rate": top_k_hit_rate,
        "enrichment_at_k": enrichment_at_k,
        "score_min": score_min,
        "score_max": score_max,
        "score_mean": score_mean,
        **score_resolution,
    }


def _group_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["family"], []).append(row)
    return grouped


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _resolve_optional_payload(
    *,
    payload: dict[str, Any] | None,
    json_path: str | Path | None,
    name: str,
) -> dict[str, Any] | None:
    if payload is not None and json_path is not None:
        raise ValueError(f"pass either {name} or {name}_json, not both")
    if payload is not None:
        return payload
    if json_path is not None:
        return _load_json(json_path)
    return None


def _finite_float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_identity_columns(
    identity_cols: list[str] | None,
    *,
    score_col: str,
) -> list[str]:
    normalized: list[str] = []
    for identity_col in identity_cols or []:
        column = str(identity_col).strip()
        if not column:
            continue
        if column == score_col:
            raise ValueError("score column cannot be used as an identity column")
        if column not in normalized:
            normalized.append(column)
    return normalized


def _summary_identity_columns(identity_cols: list[str]) -> list[str]:
    columns = ["family", "label"]
    for identity_col in identity_cols:
        if identity_col not in columns:
            columns.append(identity_col)
    return columns


def _row_identity_sha256(rows: list[dict[str, Any]], identity_cols: list[str]) -> str:
    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            {"row_identity_schema_version": ROW_IDENTITY_SCHEMA_VERSION},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    digest.update(b"\n")
    for row in rows:
        row_identity = {"family": row["family"], "label": row["label"]}
        for identity_col in identity_cols:
            if identity_col not in row_identity:
                row_identity[identity_col] = row.get("identity", {}).get(identity_col, "")
        digest.update(
            json.dumps(
                row_identity,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _add_duplicate_row_identity_warnings(
    *,
    rows: list[dict[str, Any]],
    identity_cols: list[str],
    warnings: list[dict[str, str]],
) -> None:
    if not identity_cols:
        return

    identity_columns = _summary_identity_columns(identity_cols)
    seen: set[tuple[Any, ...]] = set()
    warned_families: set[str] = set()
    for row in rows:
        family = str(row["family"])
        row_identity = {"family": family, "label": row["label"]}
        for identity_col in identity_cols:
            if identity_col not in row_identity:
                row_identity[identity_col] = row.get("identity", {}).get(identity_col, "")
        row_identity_key = tuple(row_identity[column] for column in identity_columns)
        if row_identity_key in seen and family not in warned_families:
            warnings.append(
                {
                    "family": family,
                    "metric": "row_identity",
                    "reason": "duplicate_row_identity",
                }
            )
            warned_families.add(family)
        seen.add(row_identity_key)


def _add_baseline_summary_warnings(
    *,
    baseline_scorecard: dict[str, Any],
    top_k: int,
    lower_better: bool,
    row_identity_sha256: str,
    identity_columns: list[str],
    row_identity_schema_version: str,
    warnings: list[dict[str, str]],
) -> None:
    summary = baseline_scorecard.get("summary")
    if not isinstance(summary, dict):
        warnings.append(
            {
                "family": "overall",
                "metric": "baseline",
                "reason": "missing_baseline_summary",
            }
        )
        return

    baseline_top_k = summary.get("top_k")
    if baseline_top_k is None:
        warnings.append(
            {
                "family": "overall",
                "metric": "baseline.top_k",
                "reason": "missing_baseline_top_k",
            }
        )
    else:
        try:
            baseline_top_k_int = int(baseline_top_k)
        except (TypeError, ValueError):
            baseline_top_k_int = None
        if baseline_top_k_int != int(top_k):
            warnings.append(
                {
                    "family": "overall",
                    "metric": "baseline.top_k",
                    "reason": "baseline_top_k_mismatch",
                }
            )

    baseline_lower_better = summary.get("lower_better")
    if baseline_lower_better is None:
        warnings.append(
            {
                "family": "overall",
                "metric": "baseline.lower_better",
                "reason": "missing_baseline_lower_better",
            }
        )
    elif bool(baseline_lower_better) != bool(lower_better):
        warnings.append(
            {
                "family": "overall",
                "metric": "baseline.lower_better",
                "reason": "baseline_lower_better_mismatch",
            }
        )

    baseline_row_identity_sha256 = summary.get("row_identity_sha256")
    if baseline_row_identity_sha256 is None:
        warnings.append(
            {
                "family": "overall",
                "metric": "baseline.row_identity_sha256",
                "reason": "missing_baseline_row_identity_sha256",
            }
        )
    elif str(baseline_row_identity_sha256) != row_identity_sha256:
        warnings.append(
            {
                "family": "overall",
                "metric": "baseline.row_identity_sha256",
                "reason": "baseline_row_identity_mismatch",
            }
        )

    baseline_row_identity_schema_version = summary.get("row_identity_schema_version")
    if baseline_row_identity_schema_version is None:
        warnings.append(
            {
                "family": "overall",
                "metric": "baseline.row_identity_schema_version",
                "reason": "missing_baseline_row_identity_schema_version",
            }
        )
    elif str(baseline_row_identity_schema_version) != row_identity_schema_version:
        warnings.append(
            {
                "family": "overall",
                "metric": "baseline.row_identity_schema_version",
                "reason": "baseline_row_identity_schema_version_mismatch",
            }
        )

    if "identity_columns" not in summary:
        warnings.append(
            {
                "family": "overall",
                "metric": "baseline.identity_columns",
                "reason": "missing_baseline_identity_columns",
            }
        )
    else:
        baseline_identity_columns = summary.get("identity_columns")
        if not isinstance(baseline_identity_columns, list):
            warnings.append(
                {
                    "family": "overall",
                    "metric": "baseline.identity_columns",
                    "reason": "baseline_identity_columns_mismatch",
                }
            )
        elif baseline_identity_columns != identity_columns:
            warnings.append(
                {
                    "family": "overall",
                    "metric": "baseline.identity_columns",
                    "reason": "baseline_identity_columns_mismatch",
                }
            )


def _add_baseline_deltas(
    families: dict[str, dict[str, Any]],
    baseline_scorecard: dict[str, Any],
    warnings: list[dict[str, str]],
    *,
    top_k: int,
    lower_better: bool,
    row_identity_sha256: str,
    identity_columns: list[str],
    row_identity_schema_version: str,
) -> None:
    _add_baseline_summary_warnings(
        baseline_scorecard=baseline_scorecard,
        top_k=top_k,
        lower_better=lower_better,
        row_identity_sha256=row_identity_sha256,
        identity_columns=identity_columns,
        row_identity_schema_version=row_identity_schema_version,
        warnings=warnings,
    )
    baseline_families = baseline_scorecard.get("families")
    if not isinstance(baseline_families, dict):
        for family in families:
            warnings.append(
                {
                    "family": family,
                    "metric": "baseline",
                    "reason": "missing_baseline_families",
                }
            )
        return

    for family, metrics in families.items():
        baseline_metrics = baseline_families.get(family)
        if not isinstance(baseline_metrics, dict):
            warnings.append(
                {
                    "family": family,
                    "metric": "baseline",
                    "reason": "missing_baseline_family",
                }
            )
            metrics["deltas"] = {}
            continue

        deltas: dict[str, float] = {}
        for metric_name in BASELINE_METRIC_NAMES:
            current_value = metrics.get(metric_name)
            baseline_value = baseline_metrics.get(metric_name)
            if metric_name not in baseline_metrics:
                warnings.append(
                    {
                        "family": family,
                        "metric": metric_name,
                        "reason": "missing_baseline_metric",
                    }
                )
                continue
            if current_value is None or baseline_value is None:
                warnings.append(
                    {
                        "family": family,
                        "metric": metric_name,
                        "reason": "null_baseline_comparison_metric",
                    }
                )
                continue
            current_number = _finite_float_or_none(current_value)
            baseline_number = _finite_float_or_none(baseline_value)
            if current_number is None or baseline_number is None:
                warnings.append(
                    {
                        "family": family,
                        "metric": metric_name,
                        "reason": "invalid_baseline_comparison_metric",
                    }
                )
                continue
            deltas[metric_name] = round(current_number - baseline_number, 12)
        metrics["deltas"] = deltas


def _threshold_metric_name(threshold_name: str) -> str:
    if threshold_name.startswith("min_"):
        return threshold_name.removeprefix("min_")
    if threshold_name.startswith("max_"):
        return threshold_name.removeprefix("max_")
    return threshold_name


def _thresholds_for_family(acceptance_profile: dict[str, Any], family: str) -> dict[str, Any]:
    default_thresholds = acceptance_profile.get("default", {})
    family_thresholds = acceptance_profile.get("families", {}).get(family, {})
    if not isinstance(default_thresholds, dict):
        default_thresholds = {}
    if not isinstance(family_thresholds, dict):
        family_thresholds = {}
    return {**default_thresholds, **family_thresholds}


def _warnings_by_family(warnings: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for warning in warnings:
        grouped.setdefault(str(warning.get("family", "")), []).append(warning)
    return grouped


def _metric_for_threshold(
    metrics: dict[str, Any],
    threshold_name: str,
) -> tuple[str, Any]:
    if threshold_name.startswith("min_delta_"):
        metric_name = threshold_name.removeprefix("min_delta_")
        return f"delta_{metric_name}", metrics.get("deltas", {}).get(metric_name)
    if threshold_name.startswith("max_delta_"):
        metric_name = threshold_name.removeprefix("max_delta_")
        return f"delta_{metric_name}", metrics.get("deltas", {}).get(metric_name)
    return _threshold_metric_name(threshold_name), metrics.get(_threshold_metric_name(threshold_name))


def _evaluate_acceptance(
    families: dict[str, dict[str, Any]],
    acceptance_profile: dict[str, Any],
    warnings: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    family_acceptance: dict[str, dict[str, Any]] = {}
    grouped_warnings = _warnings_by_family(warnings)
    for family, metrics in families.items():
        reasons: list[str] = []
        family_warnings = grouped_warnings.get(family, [])
        if family != "overall":
            family_warnings.extend(grouped_warnings.get("overall", []))
        for warning in family_warnings:
            reason = str(warning.get("reason", ""))
            if (
                reason in BASELINE_BLOCKING_REASONS
                or reason in SCORECARD_BLOCKING_REASONS
                or reason.startswith("baseline_")
            ):
                reasons.append(
                    f"{warning.get('metric', 'scorecard')} blocked because {reason}"
                )
        thresholds = _thresholds_for_family(acceptance_profile, family)
        for threshold_name, threshold_value in thresholds.items():
            if threshold_value is None:
                continue
            threshold_key = str(threshold_name)
            metric_name, metric_value = _metric_for_threshold(metrics, threshold_key)
            metric_number = _finite_float_or_none(metric_value)
            threshold_number = _finite_float_or_none(threshold_value)
            if metric_number is None:
                reasons.append(f"{metric_name} is null for {threshold_name}")
                continue
            if threshold_number is None:
                reasons.append(f"{threshold_name} threshold is invalid")
                continue
            if threshold_key.startswith("min_") and metric_number < threshold_number:
                reasons.append(
                    f"{metric_name} {_format_cell(metric_number)} < {threshold_name} {_format_cell(threshold_number)}"
                )
            if threshold_key.startswith("max_") and metric_number > threshold_number:
                reasons.append(
                    f"{metric_name} {_format_cell(metric_number)} > {threshold_name} {_format_cell(threshold_number)}"
                )
        family_acceptance[family] = {
            "status": "blocked" if reasons else "pass",
            "reasons": reasons,
            "thresholds": thresholds,
        }
    return family_acceptance


def _add_required_family_warnings(
    *,
    required_families: list[str],
    candidate_families: set[str],
    warnings: list[dict[str, str]],
) -> None:
    for family in required_families:
        if family not in candidate_families:
            warnings.append(
                {
                    "family": family,
                    "metric": "required_family",
                    "reason": "missing_required_family",
                }
            )


def _add_required_family_acceptance(
    *,
    family_acceptance: dict[str, dict[str, Any]],
    required_families: list[str],
    candidate_families: set[str],
    acceptance_profile: dict[str, Any],
) -> None:
    for family in required_families:
        if family in candidate_families:
            continue
        family_acceptance[family] = {
            "status": "blocked",
            "reasons": ["required_family blocked because missing_required_family"],
            "thresholds": _thresholds_for_family(acceptance_profile, family),
        }


def _scorecard_level_status(
    warnings: list[dict[str, str]],
    *,
    required_families: list[str],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    for warning in warnings:
        reason = str(warning.get("reason", ""))
        if (
            reason in BASELINE_BLOCKING_REASONS
            or reason.startswith("baseline_")
            or reason in SCORECARD_BLOCKING_REASONS
        ):
            reasons.append(f"{warning.get('metric', 'scorecard')} blocked because {reason}")
    if required_families and any(
        str(warning.get("reason", "")) == "missing_required_family" for warning in warnings
    ):
        return "blocked", reasons
    if reasons:
        return "blocked", reasons
    return "pass", []


def build_scorecard(
    *,
    predictions_csv: str | Path,
    family_col: str,
    label_col: str,
    score_col: str,
    top_k: int = 10,
    lower_better: bool = False,
    baseline_scorecard_json: str | Path | None = None,
    baseline_scorecard: dict[str, Any] | None = None,
    acceptance_profile_json: str | Path | None = None,
    acceptance_profile: dict[str, Any] | None = None,
    required_families: list[str] | None = None,
    identity_cols: list[str] | None = None,
    packet_id: str | None = None,
) -> dict[str, Any]:
    if top_k < 1:
        raise ValueError("--top-k must be >= 1")

    predictions_path = Path(predictions_csv)
    normalized_identity_cols = _normalize_identity_columns(
        identity_cols,
        score_col=score_col,
    )
    identity_columns = _summary_identity_columns(normalized_identity_cols)
    rows = _read_rows(
        predictions_path,
        family_col=family_col,
        label_col=label_col,
        score_col=score_col,
        identity_cols=normalized_identity_cols,
    )
    grouped = _group_rows(rows)
    warnings: list[dict[str, str]] = []
    required_family_list = list(
        dict.fromkeys(
            str(family).strip()
            for family in (required_families or [])
            if str(family).strip()
        )
    )
    _add_required_family_warnings(
        required_families=required_family_list,
        candidate_families=set(grouped),
        warnings=warnings,
    )
    _add_duplicate_row_identity_warnings(
        rows=rows,
        identity_cols=normalized_identity_cols,
        warnings=warnings,
    )
    families = {
        family: _family_metrics(
            family,
            family_rows,
            top_k=top_k,
            lower_better=lower_better,
            warnings=warnings,
        )
        for family, family_rows in grouped.items()
    }
    families["overall"] = _family_metrics(
        "overall",
        rows,
        top_k=top_k,
        lower_better=lower_better,
        warnings=warnings,
    )

    resolved_baseline_scorecard = _resolve_optional_payload(
        payload=baseline_scorecard,
        json_path=baseline_scorecard_json,
        name="baseline_scorecard",
    )
    row_identity_sha256 = _row_identity_sha256(rows, normalized_identity_cols)
    if resolved_baseline_scorecard is not None:
        _add_baseline_deltas(
            families,
            resolved_baseline_scorecard,
            warnings,
            top_k=top_k,
            lower_better=lower_better,
            row_identity_sha256=row_identity_sha256,
            identity_columns=identity_columns,
            row_identity_schema_version=ROW_IDENTITY_SCHEMA_VERSION,
        )

    resolved_acceptance_profile = _resolve_optional_payload(
        payload=acceptance_profile,
        json_path=acceptance_profile_json,
        name="acceptance_profile",
    )
    family_acceptance: dict[str, dict[str, Any]] = {}
    acceptance_overall_pass = False
    if resolved_acceptance_profile is not None:
        family_acceptance = _evaluate_acceptance(
            families,
            resolved_acceptance_profile,
            warnings,
        )
        _add_required_family_acceptance(
            family_acceptance=family_acceptance,
            required_families=required_family_list,
            candidate_families=set(grouped),
            acceptance_profile=resolved_acceptance_profile,
        )
        acceptance_overall_pass = all(
            result["status"] == "pass" for result in family_acceptance.values()
        )

    scorecard_level_status, scorecard_level_reasons = _scorecard_level_status(
        warnings,
        required_families=required_family_list,
    )
    supported_families = list(grouped.keys())
    summary = {
        "family_count": len(supported_families),
        "overall_row_count": len(rows),
        "supported_families": supported_families,
        "required_families": required_family_list,
        "warnings": warnings,
        "metric_names": METRIC_NAMES,
        "baseline_metric_names": BASELINE_METRIC_NAMES,
        "top_k": top_k,
        "lower_better": bool(lower_better),
        "predictions_csv_sha256": _sha256_file(predictions_path),
        "row_identity_schema_version": ROW_IDENTITY_SCHEMA_VERSION,
        "row_identity_sha256": row_identity_sha256,
        "identity_columns": identity_columns,
        "packet_id": packet_id,
        "scorecard_level_status": scorecard_level_status,
        "scorecard_level_reasons": scorecard_level_reasons,
        "acceptance_overall_pass": acceptance_overall_pass,
    }
    return {
        "summary": summary,
        "families": families,
        "family_acceptance": family_acceptance,
        "warnings": warnings,
    }


def build_family_scorecard(**kwargs: Any) -> dict[str, Any]:
    return build_scorecard(**kwargs)


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _format_cell(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def render_markdown(payload: dict[str, Any]) -> str:
    header = ["family", *METRIC_NAMES]
    identity_columns = ", ".join(payload["summary"].get("identity_columns", [])) or "none"
    packet_id = payload["summary"].get("packet_id")
    lines = [
        "# Family Scorecard",
        "",
        f"- family_count: {payload['summary']['family_count']}",
        f"- overall_row_count: {payload['summary']['overall_row_count']}",
        f"- top_k: {payload['summary']['top_k']}",
        f"- lower_better: {payload['summary']['lower_better']}",
        f"- identity_columns: {identity_columns}",
        f"- row_identity_schema_version: {payload['summary']['row_identity_schema_version']}",
        f"- packet_id: {packet_id if packet_id is not None else 'null'}",
        f"- required_families: {', '.join(payload['summary'].get('required_families', [])) or 'none'}",
        f"- predictions_csv_sha256: {payload['summary']['predictions_csv_sha256']}",
        f"- row_identity_sha256: {payload['summary']['row_identity_sha256']}",
        f"- scorecard_level_status: {payload['summary']['scorecard_level_status']}",
        "",
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for family, metrics in payload["families"].items():
        row = [family, *[_format_cell(metrics[name]) for name in METRIC_NAMES]]
        lines.append("| " + " | ".join(row) + " |")

    if payload["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for warning in payload["warnings"]:
            reason = str(warning["reason"])
            verb = "flagged" if warning["metric"] == "score_coverage" else "skipped"
            if (
                reason in BASELINE_BLOCKING_REASONS
                or reason in SCORECARD_BLOCKING_REASONS
                or reason.startswith("baseline_")
            ):
                verb = "blocked"
            lines.append(
                f"- {warning['family']}: {warning['metric']} {verb} because {reason}"
            )
    return "\n".join(lines) + "\n"


def write_markdown(path: str | Path, payload: dict[str, Any]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(payload), encoding="utf-8")


def write_csv(path: str | Path, payload: dict[str, Any]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    delta_columns = [f"delta_{metric_name}" for metric_name in BASELINE_METRIC_NAMES]
    fieldnames = [
        "predictions_csv_sha256",
        "row_identity_schema_version",
        "row_identity_sha256",
        "identity_columns",
        "packet_id",
        "required_families",
        "family",
        *METRIC_NAMES,
        *delta_columns,
        "acceptance_status",
        "acceptance_reasons",
    ]
    family_acceptance = payload.get("family_acceptance", {})
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        family_names = list(payload["families"].keys())
        for family in payload.get("family_acceptance", {}):
            if family not in payload["families"]:
                family_names.append(family)
        for family in family_names:
            metrics = payload["families"].get(family, {})
            acceptance = family_acceptance.get(family, {})
            row = {
                "predictions_csv_sha256": payload["summary"]["predictions_csv_sha256"],
                "row_identity_schema_version": payload["summary"][
                    "row_identity_schema_version"
                ],
                "row_identity_sha256": payload["summary"]["row_identity_sha256"],
                "identity_columns": ",".join(
                    payload["summary"].get("identity_columns", [])
                ),
                "packet_id": _format_cell(payload["summary"].get("packet_id")),
                "required_families": ",".join(
                    payload["summary"].get("required_families", [])
                ),
                "family": family,
                **{
                    metric_name: _format_cell(metrics.get(metric_name))
                    for metric_name in METRIC_NAMES
                },
                **{
                    f"delta_{metric_name}": _format_cell(
                        metrics.get("deltas", {}).get(metric_name)
                    )
                    for metric_name in BASELINE_METRIC_NAMES
                },
                "acceptance_status": acceptance.get("status", ""),
                "acceptance_reasons": "; ".join(acceptance.get("reasons", [])),
            }
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build family-level scoring scorecards.")
    parser.add_argument("--predictions-csv", required=True)
    parser.add_argument("--family-col", required=True)
    parser.add_argument("--label-col", required=True)
    parser.add_argument("--score-col", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-csv")
    parser.add_argument("--baseline-scorecard-json")
    parser.add_argument("--acceptance-profile-json")
    parser.add_argument(
        "--identity-col",
        action="append",
        default=[],
        help="CSV column to include in row identity after family and label. Repeatable.",
    )
    parser.add_argument(
        "--packet-id",
        help="Optional human-readable packet alias. Not used for blocking comparisons.",
    )
    parser.add_argument(
        "--required-family",
        action="append",
        default=[],
        help="Family that must be present in the prediction CSV. Repeatable.",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--lower-better",
        action="store_true",
        help="Treat lower scores as better when computing ranking metrics and top-k rows.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_scorecard(
        predictions_csv=args.predictions_csv,
        family_col=args.family_col,
        label_col=args.label_col,
        score_col=args.score_col,
        top_k=args.top_k,
        lower_better=args.lower_better,
        baseline_scorecard_json=args.baseline_scorecard_json,
        acceptance_profile_json=args.acceptance_profile_json,
        required_families=args.required_family,
        identity_cols=args.identity_col,
        packet_id=args.packet_id,
    )
    write_json(args.out_json, payload)
    write_markdown(args.out_md, payload)
    if args.out_csv:
        write_csv(args.out_csv, payload)


if __name__ == "__main__":
    main()
