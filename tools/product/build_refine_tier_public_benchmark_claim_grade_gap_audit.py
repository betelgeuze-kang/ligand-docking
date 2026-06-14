#!/usr/bin/env python3
"""Read-only audit for R9 public-benchmark claim-grade statistical gaps."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
    MIN_CLAIM_GRADE_HOLDOUT_PAIRS,
    MIN_CLAIM_GRADE_PUBLIC_BENCHMARK_PAIRS,
)

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MATERIALIZATION_JSON = "runs/refine_tier_public_benchmark_metric_source_materialization_current.json"
DEFAULT_STATISTICAL_SUPPORT_WORK_ORDER_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_work_order_current.json"
)
DEFAULT_METRIC_MATERIALIZATION_READINESS_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json"
)
DEFAULT_METRIC_SOURCE_TEMPLATES_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json"
)
DEFAULT_COORDINATE_FETCH_R4_PREFLIGHT_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.json"
)
DEFAULT_OUT_JSON = "runs/refine_tier_public_benchmark_claim_grade_gap_audit_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_claim_grade_gap_audit_current.csv"
DEFAULT_OUT_MD = "runs/refine_tier_public_benchmark_claim_grade_gap_audit_current.md"

CLAIM_BOUNDARY = (
    "R9 public-benchmark claim-grade gap audit only; it reads local current artifacts and explains why "
    "the current materialized public benchmark evidence cannot be promoted to claim-grade commercial "
    "accuracy. It does not download coordinates, run docking/MD, fill metric source payloads, promote "
    "canonical intake, approve receipts, upload, email, delete, commit, push, or mutate external state."
)

NEXT_REQUIRED_STEP = (
    "Keep R9 claim-grade promotion blocked; fetch and validate any remaining public coordinate candidates, "
    "replace reviewed DockQ/lDDT-PLI/internal DeltaG metric source payload placeholders, then rebuild "
    "materialization and require bootstrap Spearman p05 >= 0.5 with at least 25 public benchmark pairs and "
    "8 holdout pairs."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    path = _resolve(path_like)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        out = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _bool_int(value: Any) -> int:
    return 1 if value is True else 0


def _deficit(observed: int, required: int) -> int:
    return max(0, int(required) - int(observed))


def _float_deficit(observed: float | None, required: float) -> float:
    if observed is None:
        return float(required)
    return max(0.0, float(required) - observed)


def _gap_status(deficit: int | float) -> str:
    return "pass" if float(deficit) <= 0.0 else "blocked"


def build_refine_tier_public_benchmark_claim_grade_gap_audit(
    *,
    materialization_json: str | Path = DEFAULT_MATERIALIZATION_JSON,
    statistical_support_work_order_json: str | Path = DEFAULT_STATISTICAL_SUPPORT_WORK_ORDER_JSON,
    metric_materialization_readiness_json: str | Path = DEFAULT_METRIC_MATERIALIZATION_READINESS_JSON,
    metric_source_templates_json: str | Path = DEFAULT_METRIC_SOURCE_TEMPLATES_JSON,
    coordinate_fetch_r4_preflight_json: str | Path = DEFAULT_COORDINATE_FETCH_R4_PREFLIGHT_JSON,
) -> dict[str, Any]:
    materialization_payload, materialization_present = _read_json(materialization_json)
    work_order_payload, work_order_present = _read_json(statistical_support_work_order_json)
    metric_readiness_payload, metric_readiness_present = _read_json(metric_materialization_readiness_json)
    templates_payload, templates_present = _read_json(metric_source_templates_json)
    r4_payload, r4_present = _read_json(coordinate_fetch_r4_preflight_json)

    materialization = _summary(materialization_payload)
    work_order = _summary(work_order_payload)
    metric_readiness = _summary(metric_readiness_payload)
    templates = _summary(templates_payload)
    r4 = _summary(r4_payload)

    observed_pair_count = _int(materialization.get("free_energy_pair_count"))
    observed_holdout_count = _int(materialization.get("free_energy_holdout_pair_count"))
    observed_bootstrap_p05 = _float(materialization.get("free_energy_spearman_bootstrap_p05"))
    pair_deficit = _deficit(observed_pair_count, MIN_CLAIM_GRADE_PUBLIC_BENCHMARK_PAIRS)
    holdout_deficit = _deficit(observed_holdout_count, MIN_CLAIM_GRADE_HOLDOUT_PAIRS)
    bootstrap_deficit = _float_deficit(
        observed_bootstrap_p05,
        MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
    )

    coordinate_validation_pass_count = _int(metric_readiness.get("coordinate_validation_pass_row_count"))
    coordinate_validation_blocked_count = _int(metric_readiness.get("coordinate_validation_blocked_row_count"))
    coordinate_candidate_count = _int(metric_readiness.get("metric_materialization_row_count"))
    coordinate_validation_deficit = _deficit(coordinate_validation_pass_count, coordinate_candidate_count)

    planned_payload_count = _int(templates.get("planned_metric_source_payload_count")) or _int(
        metric_readiness.get("planned_metric_source_payload_count")
    )
    payload_fill_ready_count = _int(templates.get("metric_source_payload_fill_ready_row_count"))
    payload_fill_blocked_count = _int(templates.get("metric_source_payload_fill_blocked_row_count"))
    payload_fill_deficit = _deficit(payload_fill_ready_count, planned_payload_count)

    blocker_ids: list[str] = []
    if not materialization_present:
        blocker_ids.append("materialization_artifact_missing")
    if not work_order_present:
        blocker_ids.append("statistical_support_work_order_missing")
    if not metric_readiness_present:
        blocker_ids.append("metric_materialization_readiness_missing")
    if not templates_present:
        blocker_ids.append("metric_source_templates_missing")
    if not r4_present:
        blocker_ids.append("coordinate_fetch_r4_preflight_missing")
    if pair_deficit:
        blocker_ids.append("claim_grade_public_benchmark_pair_count_below_minimum")
    if holdout_deficit:
        blocker_ids.append("claim_grade_public_benchmark_holdout_pair_count_below_minimum")
    if bootstrap_deficit > 0.0:
        blocker_ids.append("claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum")
    if coordinate_validation_deficit:
        blocker_ids.append("claim_grade_coordinate_validation_not_complete")
    if payload_fill_deficit:
        blocker_ids.append("claim_grade_metric_source_payloads_not_materialized")

    claim_grade_ready = bool(
        materialization.get("claim_grade_public_benchmark_statistical_support_ready") is True
    )
    canonical_intake_promotion_allowed = bool(
        claim_grade_ready
        and not blocker_ids
        and work_order.get("canonical_intake_promotion_allowed") is True
    )
    audit_ready = bool(
        materialization_present
        and work_order_present
        and metric_readiness_present
        and templates_present
        and r4_present
    )

    rows = [
        {
            "gap_id": "claim_grade_public_benchmark_pair_count",
            "observed": observed_pair_count,
            "required": MIN_CLAIM_GRADE_PUBLIC_BENCHMARK_PAIRS,
            "deficit": pair_deficit,
            "status": _gap_status(pair_deficit),
            "next_action": "add_reviewed_public_benchmark_pairs",
        },
        {
            "gap_id": "claim_grade_public_benchmark_holdout_pair_count",
            "observed": observed_holdout_count,
            "required": MIN_CLAIM_GRADE_HOLDOUT_PAIRS,
            "deficit": holdout_deficit,
            "status": _gap_status(holdout_deficit),
            "next_action": "add_reviewed_holdout_pairs",
        },
        {
            "gap_id": "claim_grade_public_benchmark_bootstrap_spearman_p05",
            "observed": observed_bootstrap_p05,
            "required": MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
            "deficit": bootstrap_deficit,
            "status": _gap_status(bootstrap_deficit),
            "next_action": "rerun_bootstrap_after_metric_source_materialization",
        },
        {
            "gap_id": "claim_grade_coordinate_validation",
            "observed": coordinate_validation_pass_count,
            "required": coordinate_candidate_count,
            "deficit": coordinate_validation_deficit,
            "status": _gap_status(coordinate_validation_deficit),
            "next_action": "run_r4_approved_coordinate_fetch_and_validation",
        },
        {
            "gap_id": "claim_grade_metric_source_payloads",
            "observed": payload_fill_ready_count,
            "required": planned_payload_count,
            "deficit": payload_fill_deficit,
            "status": _gap_status(payload_fill_deficit),
            "next_action": "replace_operator_metric_source_placeholders",
        },
    ]
    blocked_row_count = sum(1 for row in rows if row["status"] != "pass")
    if coordinate_validation_deficit:
        next_required_step = NEXT_REQUIRED_STEP
    else:
        next_required_step = (
            "Coordinate fetch and validation are complete for the 17 R9 statistical-support candidates; "
            "fill/review the 51 DockQ/lDDT-PLI/internal DeltaG metric source payload values, materialize "
            "the 17 candidates, and rerun bootstrap Spearman p05 with at least 25 public benchmark pairs "
            "and 8 holdout pairs before any claim-grade promotion."
        )

    summary = {
        "packet_type": "refine_tier_public_benchmark_claim_grade_gap_audit",
        "status": (
            "refine_tier_public_benchmark_claim_grade_gap_audit_ready"
            if audit_ready
            else "blocked_refine_tier_public_benchmark_claim_grade_gap_audit"
        ),
        "claim_grade_gap_audit_ready": audit_ready,
        "claim_grade_statistical_support_ready": claim_grade_ready,
        "canonical_intake_promotion_allowed": canonical_intake_promotion_allowed,
        "materialization_artifact": _display(materialization_json),
        "materialization_artifact_present": materialization_present,
        "statistical_support_work_order_artifact": _display(statistical_support_work_order_json),
        "statistical_support_work_order_present": work_order_present,
        "metric_materialization_readiness_artifact": _display(metric_materialization_readiness_json),
        "metric_materialization_readiness_present": metric_readiness_present,
        "metric_source_templates_artifact": _display(metric_source_templates_json),
        "metric_source_templates_present": templates_present,
        "coordinate_fetch_r4_preflight_artifact": _display(coordinate_fetch_r4_preflight_json),
        "coordinate_fetch_r4_preflight_present": r4_present,
        "observed_public_benchmark_pair_count": observed_pair_count,
        "observed_holdout_pair_count": observed_holdout_count,
        "observed_bootstrap_spearman_p05": observed_bootstrap_p05,
        "observed_bootstrap_spearman_p50": _float(materialization.get("free_energy_spearman_bootstrap_p50")),
        "observed_bootstrap_spearman_p95": _float(materialization.get("free_energy_spearman_bootstrap_p95")),
        "min_claim_grade_public_benchmark_pairs_required": MIN_CLAIM_GRADE_PUBLIC_BENCHMARK_PAIRS,
        "min_claim_grade_holdout_pairs_required": MIN_CLAIM_GRADE_HOLDOUT_PAIRS,
        "min_claim_grade_bootstrap_spearman_low_required": MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
        "minimum_new_pair_count": pair_deficit,
        "minimum_new_holdout_pair_count": holdout_deficit,
        "bootstrap_spearman_p05_deficit": bootstrap_deficit,
        "bootstrap_retest_required": not claim_grade_ready,
        "statistical_support_work_order_expansion_slot_count": _int(work_order.get("expansion_slot_count")),
        "statistical_support_work_order_holdout_expansion_slot_count": _int(
            work_order.get("holdout_expansion_slot_count")
        ),
        "statistical_support_work_order_fit_or_holdout_expansion_slot_count": _int(
            work_order.get("fit_or_holdout_expansion_slot_count")
        ),
        "coordinate_fetch_r4_preflight_ready": bool(r4.get("r4_preflight_ready") is True),
        "coordinate_fetch_r4_fetch_required_row_count": _int(r4.get("fetch_required_row_count")),
        "coordinate_fetch_r4_ready_for_review_row_count": _int(r4.get("ready_for_r4_review_row_count")),
        "coordinate_fetch_r4_blocked_row_count": _int(r4.get("blocked_r4_row_count")),
        "coordinate_fetch_r4_authorized_for_external_download": bool(
            r4.get("authorized_for_external_download") is True
        ),
        "coordinate_fetch_r4_download_executed": bool(r4.get("download_executed") is True),
        "coordinate_fetch_r4_external_state_mutated": bool(r4.get("external_state_mutated") is True),
        "coordinate_fetch_r4_approval_token_required": str(r4.get("approval_token_required", "")),
        "coordinate_validation_candidate_row_count": coordinate_candidate_count,
        "coordinate_validation_pass_row_count": coordinate_validation_pass_count,
        "coordinate_validation_blocked_row_count": coordinate_validation_blocked_count,
        "coordinate_validation_deficit": coordinate_validation_deficit,
        "planned_metric_source_payload_count": planned_payload_count,
        "metric_source_payload_fill_ready_row_count": payload_fill_ready_count,
        "metric_source_payload_fill_blocked_row_count": payload_fill_blocked_count,
        "metric_source_payload_fill_deficit": payload_fill_deficit,
        "required_metric_source_payloads": str(
            templates.get("required_metric_source_payloads")
            or metric_readiness.get("required_metric_source_payloads")
            or ""
        ),
        "required_metric_source_payload_fields": str(
            templates.get("required_metric_source_payload_fields")
            or metric_readiness.get("required_metric_source_payload_fields")
            or ""
        ),
        "gap_row_count": len(rows),
        "blocked_gap_row_count": blocked_row_count,
        "pass_gap_row_count": len(rows) - blocked_row_count,
        "blocker_count": len(blocker_ids),
        "blockers": blocker_ids,
        "top_science_gap_id": (
            "coordinate_fetch_r4_approval_required"
            if _int(r4.get("fetch_required_row_count")) > 0 and r4.get("download_executed") is not True
            else (blocker_ids[0] if blocker_ids else "")
        ),
        "top_statistical_gap_id": (
            "claim_grade_public_benchmark_pair_count_below_minimum"
            if pair_deficit
            else (blocker_ids[0] if blocker_ids else "")
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_step,
        "execution_enabled": False,
        "external_state_mutated": False,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Refine Tier Public Benchmark Claim Grade Gap Audit",
        "",
        f"- status: `{s['status']}`",
        f"- audit_ready: `{s['claim_grade_gap_audit_ready']}`",
        f"- claim_grade_statistical_support_ready: `{s['claim_grade_statistical_support_ready']}`",
        f"- observed_pair_count: `{s['observed_public_benchmark_pair_count']}`",
        f"- observed_holdout_pair_count: `{s['observed_holdout_pair_count']}`",
        f"- observed_bootstrap_p05: `{s['observed_bootstrap_spearman_p05']}`",
        f"- minimum_new_pair_count: `{s['minimum_new_pair_count']}`",
        f"- minimum_new_holdout_pair_count: `{s['minimum_new_holdout_pair_count']}`",
        f"- bootstrap_spearman_p05_deficit: `{s['bootstrap_spearman_p05_deficit']}`",
        f"- coordinate_validation_pass/block: `{s['coordinate_validation_pass_row_count']}/{s['coordinate_validation_blocked_row_count']}`",
        f"- metric_source_payload_fill_ready/block: `{s['metric_source_payload_fill_ready_row_count']}/{s['metric_source_payload_fill_blocked_row_count']}`",
        f"- blocked_gap_row_count: `{s['blocked_gap_row_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        "",
        "## Gap Rows",
        "",
    ]
    for row in payload["rows"]:
        lines.append(
            f"- `{row['gap_id']}` status=`{row['status']}` observed=`{row['observed']}` "
            f"required=`{row['required']}` deficit=`{row['deficit']}`"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the R9 public-benchmark claim-grade gap audit."
    )
    parser.add_argument("--materialization-json", default=DEFAULT_MATERIALIZATION_JSON)
    parser.add_argument("--statistical-support-work-order-json", default=DEFAULT_STATISTICAL_SUPPORT_WORK_ORDER_JSON)
    parser.add_argument("--metric-materialization-readiness-json", default=DEFAULT_METRIC_MATERIALIZATION_READINESS_JSON)
    parser.add_argument("--metric-source-templates-json", default=DEFAULT_METRIC_SOURCE_TEMPLATES_JSON)
    parser.add_argument("--coordinate-fetch-r4-preflight-json", default=DEFAULT_COORDINATE_FETCH_R4_PREFLIGHT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    payload = build_refine_tier_public_benchmark_claim_grade_gap_audit(
        materialization_json=args.materialization_json,
        statistical_support_work_order_json=args.statistical_support_work_order_json,
        metric_materialization_readiness_json=args.metric_materialization_readiness_json,
        metric_source_templates_json=args.metric_source_templates_json,
        coordinate_fetch_r4_preflight_json=args.coordinate_fetch_r4_preflight_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
