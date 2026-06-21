from __future__ import annotations

from typing import Any, Iterable

import numpy as np

CONFIDENCE_CALIBRATION_SCHEMA_VERSION = "confidence_calibration_v1"


def _finite_probability(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(out) or out < 0.0 or out > 1.0:
        return None
    return out


def build_confidence_calibration_report(
    rows: Iterable[dict[str, Any]],
    *,
    confidence_key: str = "hbond_confidence",
    outcome_key: str = "expected_claim_safe",
    bin_count: int = 5,
    max_expected_calibration_error: float = 0.2,
    max_brier_score: float = 0.2,
) -> dict[str, Any]:
    """Build a small reliability report for internal benchmark confidence scores."""
    row_list = [row for row in rows if isinstance(row, dict)]
    blocked_reasons: list[str] = []
    if int(bin_count) <= 0:
        raise ValueError("bin_count must be positive")

    samples: list[dict[str, Any]] = []
    for row in row_list:
        confidence = _finite_probability(row.get(confidence_key))
        outcome_raw = row.get(outcome_key)
        if confidence is None or not isinstance(outcome_raw, bool):
            continue
        outcome = 1.0 if outcome_raw else 0.0
        samples.append(
            {
                "pose_id": str(row.get("pose_id") or ""),
                "benchmark_role": str(row.get("benchmark_role") or ""),
                "confidence": float(confidence),
                "expected_claim_safe": bool(outcome_raw),
                "outcome": float(outcome),
                "prediction_error": float(abs(confidence - outcome)),
            }
        )

    if not samples:
        blocked_reasons.append("confidence_calibration_rows_missing")
    positive_count = sum(1 for sample in samples if sample["outcome"] == 1.0)
    negative_count = sum(1 for sample in samples if sample["outcome"] == 0.0)
    if positive_count <= 0:
        blocked_reasons.append("confidence_calibration_positive_rows_missing")
    if negative_count <= 0:
        blocked_reasons.append("confidence_calibration_negative_rows_missing")

    bins: list[dict[str, Any]] = []
    ece = 0.0
    for idx in range(int(bin_count)):
        low = float(idx / int(bin_count))
        high = float((idx + 1) / int(bin_count))
        bin_samples = [
            sample for sample in samples
            if min(int(sample["confidence"] * int(bin_count)), int(bin_count) - 1) == idx
        ]
        count = len(bin_samples)
        if count:
            mean_confidence = float(sum(sample["confidence"] for sample in bin_samples) / count)
            accuracy = float(sum(sample["outcome"] for sample in bin_samples) / count)
            calibration_gap = float(abs(mean_confidence - accuracy))
            ece += float(count / max(len(samples), 1)) * calibration_gap
        else:
            mean_confidence = 0.0
            accuracy = 0.0
            calibration_gap = 0.0
        bins.append(
            {
                "bin_index": idx,
                "confidence_low": low,
                "confidence_high": high,
                "row_count": count,
                "mean_confidence": mean_confidence,
                "accuracy": accuracy,
                "calibration_gap": calibration_gap,
            }
        )

    brier = (
        float(sum((sample["confidence"] - sample["outcome"]) ** 2 for sample in samples) / len(samples))
        if samples
        else 1.0
    )
    mean_confidence = (
        float(sum(sample["confidence"] for sample in samples) / len(samples))
        if samples
        else 0.0
    )
    mean_accuracy = (
        float(sum(sample["outcome"] for sample in samples) / len(samples))
        if samples
        else 0.0
    )
    if ece > float(max_expected_calibration_error):
        blocked_reasons.append("confidence_calibration_ece_exceeded")
    if brier > float(max_brier_score):
        blocked_reasons.append("confidence_calibration_brier_exceeded")
    if len(samples) != len(row_list):
        blocked_reasons.append("confidence_calibration_row_contract_incomplete")

    blocked_reasons = list(dict.fromkeys(blocked_reasons))
    ready = bool(not blocked_reasons)
    return {
        "schema_version": CONFIDENCE_CALIBRATION_SCHEMA_VERSION,
        "status": "confidence_calibration_report_ready" if ready else "blocked_confidence_calibration_report",
        "ready": ready,
        "confidence_calibration_ready": ready,
        "blocked_reasons": blocked_reasons,
        "row_count": len(samples),
        "source_row_count": len(row_list),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "bin_count": int(bin_count),
        "bins": bins,
        "expected_calibration_error": float(ece),
        "max_expected_calibration_error": float(max_expected_calibration_error),
        "brier_score": brier,
        "max_brier_score": float(max_brier_score),
        "mean_confidence": mean_confidence,
        "mean_accuracy": mean_accuracy,
        "rows": samples,
        "claim_boundary": (
            "Internal synthetic pose/H-bond benchmark confidence calibration only; "
            "not a public affinity or broad scientific claim."
        ),
    }
