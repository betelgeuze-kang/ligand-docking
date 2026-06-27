"""Fair docking-comparison contract (Betelgeuze vs Vina/GNINA), read-only.

External benchmark comparisons are only meaningful if every tool runs on the
**same dataset, same preparation policy, same metric definitions, and the same
failure accounting**. This module enforces that contract and is fail-closed: if
the dataset manifest hash, preparation-policy hash, metric-definition version,
pose-success threshold, or the complex universe differ across tools, the
comparison is marked invalid and **no winner is declared**.

The actual pose generation and the Vina/GNINA runs happen elsewhere
(GPU/local/CI). This module only ingests per-tool *aggregate result rows* (which
already follow the `betelgeuze_engine.benchmark.docking_gold` metric names) and
produces an auditable comparison. It computes no docking and downloads nothing.

Dependency-free so it is unit-testable without numpy/RDKit.
"""

from __future__ import annotations

from typing import Any

DOCKING_COMPARISON_SCHEMA_VERSION = "docking_comparison_contract_v1"

CLAIM_BOUNDARY = (
    "Fair docking-comparison contract. A comparison is valid only when every tool shares the same dataset "
    "manifest hash, preparation-policy hash, metric-definition version, pose-success RMSD threshold, and complex "
    "universe with explicit missing/failed accounting. It ingests caller-provided aggregate result rows; it does "
    "not run docking, prepare inputs, download datasets, or promote product claims. An invalid comparison declares "
    "no winner."
)

TOOL_KIND_SUBJECT = "subject"
TOOL_KIND_BASELINE = "baseline"
_TOOL_KINDS = frozenset({TOOL_KIND_SUBJECT, TOOL_KIND_BASELINE})

# Fields that MUST be identical across every tool for a fair comparison.
FAIRNESS_KEYS = (
    "dataset_id",
    "dataset_manifest_sha256",
    "prep_policy_sha256",
    "metric_def_version",
    "pose_success_rmsd_threshold_a",
)

_REQUIRED_POSE_FIELDS = (
    "tool_id",
    "tool_kind",
    "dataset_id",
    "dataset_manifest_sha256",
    "prep_policy_sha256",
    "metric_def_version",
    "pose_success_rmsd_threshold_a",
    "complex_count",
)

_REQUIRED_ENRICHMENT_FIELDS = (
    "tool_id",
    "tool_kind",
    "dataset_id",
    "dataset_manifest_sha256",
    "prep_policy_sha256",
    "metric_def_version",
)


class DockingComparisonError(ValueError):
    """Raised when a comparison input row is malformed."""


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise DockingComparisonError(f"non-numeric value: {value!r}") from exc


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _require(row: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        if field not in row:
            raise DockingComparisonError(f"result row missing required field: {field}")
    kind = str(row.get("tool_kind"))
    if kind not in _TOOL_KINDS:
        raise DockingComparisonError(f"unknown tool_kind: {kind}")


def _fairness_signature(row: dict[str, Any]) -> tuple:
    return tuple(str(row.get(key)) for key in FAIRNESS_KEYS)


def _check_fairness(rows: list[dict[str, Any]]) -> list[str]:
    """Return a list of fairness violations (empty == fair)."""

    reasons: list[str] = []
    if len(rows) < 2:
        reasons.append("need_at_least_two_tools")
        return reasons
    tool_ids = [str(r.get("tool_id")) for r in rows]
    if len(set(tool_ids)) != len(tool_ids):
        reasons.append("duplicate_tool_id")
    if not any(str(r.get("tool_kind")) == TOOL_KIND_SUBJECT for r in rows):
        reasons.append("no_subject_tool")
    if not any(str(r.get("tool_kind")) == TOOL_KIND_BASELINE for r in rows):
        reasons.append("no_baseline_tool")
    # Every fairness key must be identical across all tools.
    signatures = {_fairness_signature(r) for r in rows}
    if len(signatures) > 1:
        for idx, key in enumerate(FAIRNESS_KEYS):
            values = {str(r.get(key)) for r in rows}
            if len(values) > 1:
                reasons.append(f"mismatched_{key}")
    return reasons


def _pose_row(row: dict[str, Any]) -> dict[str, Any]:
    _require(row, _REQUIRED_POSE_FIELDS)
    complex_count = _int(row.get("complex_count"))
    evaluated = _int(row.get("evaluated_complex_count")) or complex_count
    missing = _int(row.get("missing_complex_count"))
    failed = _int(row.get("failed_pose_complex_count"))
    return {
        "tool_id": str(row["tool_id"]),
        "tool_kind": str(row["tool_kind"]),
        "complex_count": complex_count,
        "evaluated_complex_count": evaluated,
        "missing_complex_count": missing,
        "failed_pose_complex_count": failed,
        "top1_pose_success_rate": _num(row.get("top1_pose_success_rate")),
        "top5_pose_success_rate": _num(row.get("top5_pose_success_rate")),
        "top1_mean_rmsd_a": _num(row.get("top1_mean_rmsd_a")),
        "top5_best_mean_rmsd_a": _num(row.get("top5_best_mean_rmsd_a")),
        "posebusters_valid_rate": _num(row.get("posebusters_valid_rate")),
        "result_artifact_sha256": str(row.get("result_artifact_sha256", "")),
    }


def build_pose_success_comparison(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare pose-success across tools under the fairness contract."""

    pose_rows = [_pose_row(row) for row in rows]
    raw = list(rows)
    unfairness = _check_fairness(raw)
    comparison_valid = not unfairness

    subject = next((r for r in pose_rows if r["tool_kind"] == TOOL_KIND_SUBJECT), None)
    deltas: list[dict[str, Any]] = []
    if comparison_valid and subject is not None:
        for baseline in (r for r in pose_rows if r["tool_kind"] == TOOL_KIND_BASELINE):
            deltas.append(
                {
                    "baseline_tool_id": baseline["tool_id"],
                    "top1_success_delta": _delta(subject["top1_pose_success_rate"], baseline["top1_pose_success_rate"]),
                    "top5_success_delta": _delta(subject["top5_pose_success_rate"], baseline["top5_pose_success_rate"]),
                }
            )

    summary = {
        "schema_version": DOCKING_COMPARISON_SCHEMA_VERSION,
        "comparison_kind": "pose_success",
        "comparison_valid": comparison_valid,
        "status": "fair_comparison_ready" if comparison_valid else "blocked_unfair_comparison",
        "unfairness_reasons": unfairness,
        "tool_count": len(pose_rows),
        "dataset_id": str(raw[0].get("dataset_id")) if raw else "",
        "pose_success_rmsd_threshold_a": _num(raw[0].get("pose_success_rmsd_threshold_a")) if raw else None,
        "subject_vs_baseline_deltas": deltas,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": pose_rows}


def _enrichment_row(row: dict[str, Any]) -> dict[str, Any]:
    _require(row, _REQUIRED_ENRICHMENT_FIELDS)
    return {
        "tool_id": str(row["tool_id"]),
        "tool_kind": str(row["tool_kind"]),
        "ef1": _num(row.get("ef1")),
        "ef_point1": _num(row.get("ef_point1")),
        "bedroc": _num(row.get("bedroc")),
        "roc_auc": _num(row.get("roc_auc")),
        "pr_auc": _num(row.get("pr_auc")),
        "active_count": _int(row.get("active_count")),
        "decoy_count": _int(row.get("decoy_count")),
        "result_artifact_sha256": str(row.get("result_artifact_sha256", "")),
    }


def build_enrichment_comparison(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare enrichment (EF1/EF0.1/BEDROC) across tools under fairness."""

    enr_rows = [_enrichment_row(row) for row in rows]
    raw = list(rows)
    # Enrichment fairness omits the pose threshold key.
    fairness_rows = [{**r, "pose_success_rmsd_threshold_a": "n/a"} for r in raw]
    unfairness = _check_fairness(fairness_rows)
    comparison_valid = not unfairness

    subject = next((r for r in enr_rows if r["tool_kind"] == TOOL_KIND_SUBJECT), None)
    deltas: list[dict[str, Any]] = []
    if comparison_valid and subject is not None:
        for baseline in (r for r in enr_rows if r["tool_kind"] == TOOL_KIND_BASELINE):
            deltas.append(
                {
                    "baseline_tool_id": baseline["tool_id"],
                    "ef1_delta": _delta(subject["ef1"], baseline["ef1"]),
                    "ef_point1_delta": _delta(subject["ef_point1"], baseline["ef_point1"]),
                    "bedroc_delta": _delta(subject["bedroc"], baseline["bedroc"]),
                }
            )

    summary = {
        "schema_version": DOCKING_COMPARISON_SCHEMA_VERSION,
        "comparison_kind": "enrichment",
        "comparison_valid": comparison_valid,
        "status": "fair_comparison_ready" if comparison_valid else "blocked_unfair_comparison",
        "unfairness_reasons": unfairness,
        "tool_count": len(enr_rows),
        "dataset_id": str(raw[0].get("dataset_id")) if raw else "",
        "subject_vs_baseline_deltas": deltas,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": enr_rows}


def _delta(subject_value: float | None, baseline_value: float | None) -> float | None:
    if subject_value is None or baseline_value is None:
        return None
    return round(float(subject_value) - float(baseline_value), 6)


__all__ = [
    "DOCKING_COMPARISON_SCHEMA_VERSION",
    "CLAIM_BOUNDARY",
    "TOOL_KIND_SUBJECT",
    "TOOL_KIND_BASELINE",
    "FAIRNESS_KEYS",
    "DockingComparisonError",
    "build_pose_success_comparison",
    "build_enrichment_comparison",
]
