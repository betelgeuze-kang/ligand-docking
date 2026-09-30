"""Fair docking-comparison contract (Betelgeuze vs Vina/GNINA), read-only.

External benchmark comparisons are only meaningful with explicit scope and
failure accounting. The v1 contract requires the same preparation policy. V2
separates controlled-core from full-workflow comparisons. V1 is fail-closed: if
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
SCOPED_POSE_SCHEMA_VERSION = "docking_comparison_contract_v2"
CONTROLLED_CORE = "controlled_core"
FULL_WORKFLOW = "full_workflow"

CLAIM_BOUNDARY = (
    "Fair docking-comparison contract. A comparison is valid only when every tool shares the same dataset "
    "manifest hash, preparation-policy hash, metric-definition version, pose-success RMSD threshold, and complex "
    "universe with explicit missing/failed accounting. It ingests caller-provided aggregate result rows; it does "
    "not run docking, prepare inputs, download datasets, or promote product claims. An invalid comparison declares "
    "no winner."
)

SCOPED_CLAIM_BOUNDARY = (
    "V2 checks only the internal consistency of caller-declared aggregate rows within one explicit scope. "
    "Controlled core requires one canonical prepared input; full workflow permits documented tool-specific "
    "preparation. This function neither authenticates input/result artifacts nor independently recalculates "
    "pose metrics, runs docking, or authorizes a scientific, product, or customer claim."
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


def _required_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DockingComparisonError(f"missing or empty {key}")
    return value


def _count(row: dict[str, Any], key: str) -> int:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DockingComparisonError(f"{key} must be a nonnegative integer")
    return value


def _wall_seconds(row: dict[str, Any], key: str) -> float:
    if isinstance(row.get(key), bool):
        raise DockingComparisonError(f"{key} must be finite and nonnegative")
    value = _num(row.get(key))
    if value is None or not 0 <= value < float("inf"):
        raise DockingComparisonError(f"{key} must be finite and nonnegative")
    return value


def build_scoped_pose_success_comparison(rows: list[dict[str, Any]], *, scope: str) -> dict[str, Any]:
    """Build a v2, failure-inclusive pose comparison for exactly one scope.

    The caller supplies counts and provenance, never precomputed rates. This is
    an aggregate receipt validator; it cannot authenticate input artifacts or
    establish that the recorded tool runs actually happened.
    """

    if scope not in (CONTROLLED_CORE, FULL_WORKFLOW):
        raise DockingComparisonError(f"unknown comparison scope: {scope}")
    shared = (
        "dataset_id", "dataset_manifest_sha256", "candidate_manifest_sha256",
        "metric_def_version", "pose_success_rmsd_threshold_a",
    )
    if scope == CONTROLLED_CORE:
        shared += (
            "chemical_state_sha256", "receptor_state_sha256",
            "pocket_definition_sha256", "shared_preparation_sha256",
            "canonical_prepared_input_sha256",
        )
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if row.get("schema_version") != SCOPED_POSE_SCHEMA_VERSION:
            raise DockingComparisonError("invalid_scoped_comparison_schema_version")
        if row.get("comparison_scope") != scope:
            raise DockingComparisonError("mixed_or_missing_comparison_scope")
        if "top1_pose_success_rate" in row or "top5_pose_success_rate" in row:
            raise DockingComparisonError("caller_supplied_pose_success_rate")
        _require(row, ("tool_id", "tool_kind"))
        _required_text(row, "tool_id")
        _required_text(row, "tool_version")
        for key in shared:
            if key == "pose_success_rmsd_threshold_a":
                if isinstance(row.get(key), bool):
                    raise DockingComparisonError("invalid pose_success_rmsd_threshold_a")
                threshold = _num(row.get(key))
                if threshold is None or not 0 < threshold < float("inf"):
                    raise DockingComparisonError("invalid pose_success_rmsd_threshold_a")
            else:
                _required_text(row, key)
        total = _count(row, "complex_count")
        completed = _count(row, "completed_complex_count")
        failed = _count(row, "failed_complex_count")
        unprocessed = _count(row, "unprocessed_complex_count")
        top1 = _count(row, "top1_success_count")
        top5 = _count(row, "top5_success_count")
        if total == 0 or completed + failed + unprocessed != total:
            raise DockingComparisonError("complex_denominator_mismatch")
        if top1 > top5 or top5 > completed:
            raise DockingComparisonError("pose_success_count_exceeds_completed")
        normalized_row = {
            **{key: row[key] for key in shared},
            "schema_version": SCOPED_POSE_SCHEMA_VERSION,
            "tool_id": row["tool_id"], "tool_kind": row["tool_kind"],
            "tool_version": row["tool_version"], "comparison_scope": scope,
            "complex_count": total, "completed_complex_count": completed,
            "failed_complex_count": failed, "unprocessed_complex_count": unprocessed,
            "top1_success_count": top1, "top5_success_count": top5,
            "top1_pose_success_rate": top1 / total,
            "top5_pose_success_rate": top5 / total,
            "result_artifact_sha256": _required_text(row, "result_artifact_sha256"),
        }
        if scope == CONTROLLED_CORE:
            conversion = row.get("input_conversion")
            if not isinstance(conversion, dict):
                raise DockingComparisonError("missing input_conversion")
            normalized_row["input_conversion"] = {
                key: _required_text(conversion, key)
                for key in ("method", "version", "source_sha256", "output_sha256")
            }
            if normalized_row["input_conversion"]["source_sha256"] != row["canonical_prepared_input_sha256"]:
                raise DockingComparisonError("conversion_source_mismatch")
        else:
            normalized_row["preparation_policy_sha256"] = _required_text(row, "preparation_policy_sha256")
            normalized_row["preparation_recommendation_ref"] = _required_text(row, "preparation_recommendation_ref")
            prep_failed = _count(row, "preparation_failed_complex_count")
            if prep_failed > failed:
                raise DockingComparisonError("preparation_failures_exceed_failed_complexes")
            normalized_row["preparation_failed_complex_count"] = prep_failed
            normalized_row["peak_rss_kib"] = _count(row, "peak_rss_kib")
            if normalized_row["peak_rss_kib"] == 0:
                raise DockingComparisonError("peak_rss_kib_must_be_measured")
            intervention_count = _count(row, "expert_intervention_count")
            intervention_wall = _wall_seconds(row, "expert_intervention_wall_seconds")
            if (intervention_count == 0) != (intervention_wall == 0):
                raise DockingComparisonError("expert_intervention_count_time_mismatch")
            normalized_row["expert_intervention_count"] = intervention_count
            normalized_row["expert_intervention_wall_seconds"] = intervention_wall
            normalized_row["expert_intervention_log_sha256"] = _required_text(
                row, "expert_intervention_log_sha256"
            )
            normalized_row["cost_wall_seconds"] = {
                phase: _wall_seconds(row, f"{phase}_wall_seconds")
                for phase in ("preparation", "compute", "validation", "recovery")
            }
            normalized_row["elapsed_wall_seconds"] = _wall_seconds(row, "elapsed_wall_seconds")
            accounted = sum(normalized_row["cost_wall_seconds"].values()) + intervention_wall
            if accounted > normalized_row["elapsed_wall_seconds"] + 1e-9:
                raise DockingComparisonError("phase_cost_exceeds_elapsed_wall_seconds")
            normalized_row["other_wall_seconds"] = max(
                0.0, normalized_row["elapsed_wall_seconds"] - accounted
            )
        normalized.append(normalized_row)

    unfairness = _check_fairness([
        {**r, "prep_policy_sha256": r.get("shared_preparation_sha256", "scope_specific")}
        for r in rows
    ])
    # v1's fairness keys do not include the v2 candidate/state keys. Check
    # those independently. The full-workflow policy is tool-specific, and the
    # synthetic v1 prep key above is constant for that scope.
    for key in shared:
        if len({str(r[key]) for r in rows}) > 1:
            reason = f"mismatched_{key}"
            if reason not in unfairness:
                unfairness.append(reason)
    if len({r["complex_count"] for r in normalized}) > 1:
        unfairness.append("mismatched_complex_count")

    valid = not unfairness
    subject = next((r for r in normalized if r["tool_kind"] == TOOL_KIND_SUBJECT), None)
    deltas = []
    if valid and subject is not None:
        for baseline in (r for r in normalized if r["tool_kind"] == TOOL_KIND_BASELINE):
            deltas.append({
                "baseline_tool_id": baseline["tool_id"],
                "top1_success_delta": _delta(subject["top1_pose_success_rate"], baseline["top1_pose_success_rate"]),
                "top5_success_delta": _delta(subject["top5_pose_success_rate"], baseline["top5_pose_success_rate"]),
            })
    return {
        "summary": {
            "schema_version": SCOPED_POSE_SCHEMA_VERSION,
            "comparison_kind": "pose_success",
            "comparison_scope": scope,
            "comparison_valid": valid,
            "status": "declared_comparison_consistent_unverified" if valid else "blocked_unfair_comparison",
            "unfairness_reasons": unfairness,
            "tool_count": len(normalized),
            "dataset_id": rows[0]["dataset_id"] if rows else "",
            "subject_vs_baseline_deltas": deltas,
            "claim_boundary": SCOPED_CLAIM_BOUNDARY,
            "source_artifacts_verified": False,
            "metrics_independently_recomputed": False,
        },
        "rows": normalized,
    }


__all__ = [
    "DOCKING_COMPARISON_SCHEMA_VERSION",
    "CLAIM_BOUNDARY",
    "SCOPED_CLAIM_BOUNDARY",
    "TOOL_KIND_SUBJECT",
    "TOOL_KIND_BASELINE",
    "FAIRNESS_KEYS",
    "DockingComparisonError",
    "build_pose_success_comparison",
    "build_enrichment_comparison",
    "SCOPED_POSE_SCHEMA_VERSION",
    "CONTROLLED_CORE",
    "FULL_WORKFLOW",
    "build_scoped_pose_success_comparison",
]
