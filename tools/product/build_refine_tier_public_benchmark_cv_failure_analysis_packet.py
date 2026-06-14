#!/usr/bin/env python3
"""Read-only R9 cross-validation failure analysis packet."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CV_JSON = "config/refine_tier_public_benchmark_calibration_cross_validation_probe_current.json"
DEFAULT_RESIDUAL_PRIORITY_JSON = "config/refine_tier_public_benchmark_residual_metric_payload_priority_packet_current.json"
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_cv_failure_analysis_packet_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_cv_failure_analysis_packet_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_cv_failure_analysis_packet_current.md"

CLAIM_BOUNDARY = (
    "R9 CV failure analysis packet only joins existing cross-validation residual diagnostics with "
    "metric-payload priority/receipt status to rank science follow-up work. It does not train models, "
    "rewrite scores, compute DockQ/lDDT/internal DeltaG, write reviewed metric payloads, approve receipts, "
    "promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, "
    "commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path, *, root: Path) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return payload if isinstance(payload, dict) else {}, True


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _format_float(value: Any) -> str:
    numeric = _float(value)
    if numeric is None:
        return ""
    return f"{numeric:.12g}"


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (_text(row.get("target_id")), _text(row.get("pose_id")), _text(row.get("split")))


def _payload_key(row: dict[str, Any]) -> tuple[str, str]:
    return (_text(row.get("target_id")), _text(row.get("pose_id")))


def _group_payload_priority(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if isinstance(row, dict):
            grouped[_payload_key(row)].append(row)
    return grouped


def _baseline_by_key(rows: list[Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict):
            result[_key(row)] = row
    return result


def _fold_proxy_by_key(rows: list[Any]) -> dict[tuple[str, str, str], str]:
    result: dict[tuple[str, str, str], str] = {}
    for row in rows:
        if isinstance(row, dict):
            result[_key(row)] = _text(row.get("cv_proxy"))
    return result


def _gap_counts(payload_rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(_text(row.get("operator_gap_class")) or "unknown" for row in payload_rows)


def _metric_names(payload_rows: list[dict[str, Any]]) -> str:
    return ";".join(_text(row.get("metric_name")) for row in payload_rows if _text(row.get("metric_name")))


def _first_priority(payload_rows: list[dict[str, Any]]) -> str:
    ranks = [_int(row.get("payload_priority_rank")) for row in payload_rows if _int(row.get("payload_priority_rank"))]
    return str(min(ranks)) if ranks else ""


def _failure_class(*, rank_error: int, delta: int, split: str, payload_rows: list[dict[str, Any]]) -> str:
    gap_counter = _gap_counts(payload_rows)
    if rank_error >= 10 and delta > 0:
        return "high_error_cv_regression_with_payload_review"
    if rank_error >= 10 and gap_counter:
        return "high_error_payload_review"
    if split == "holdout" and rank_error >= 8:
        return "holdout_high_error_generalization_failure"
    if delta > 0:
        return "cv_regression"
    if rank_error >= 8:
        return "high_error_monitor"
    return "monitor_after_payload_review"


def _next_science_step(*, failure_class: str, payload_rows: list[dict[str, Any]]) -> str:
    gap_counter = _gap_counts(payload_rows)
    if gap_counter.get("existing_metric_payload_present_without_operator_receipt"):
        return "Add operator receipt coverage for existing seeded metric JSON before treating it as reviewed evidence."
    if gap_counter.get("operator_receipt_blocked_placeholders"):
        return "Fill and review the blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose."
    if "holdout" in failure_class:
        return "Add independent reviewed holdout evidence or adjust descriptor hypothesis before any score promotion."
    if "cv_regression" in failure_class:
        return "Audit target-held-out generalization: compare receptor assembly, pose contacts, and descriptor scaling."
    return "Keep as lower-priority residual until high-error payload gaps are closed."


def _priority_score(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    return (
        _int(row.get("locked_cv_rank_abs_error")),
        max(0, _int(row.get("rank_abs_error_delta_from_baseline"))),
        _int(row.get("operator_receipt_blocked_payload_count"))
        + _int(row.get("operator_receipt_missing_payload_count")),
        1 if row.get("split") == "holdout" else 0,
        _text(row.get("target_id")),
    )


def build_refine_tier_public_benchmark_cv_failure_analysis_packet(
    *,
    cv_json: str | Path = DEFAULT_CV_JSON,
    residual_priority_json: str | Path = DEFAULT_RESIDUAL_PRIORITY_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    cv_payload, cv_present = _read_json(cv_json, root=root_path)
    priority_payload, priority_present = _read_json(residual_priority_json, root=root_path)
    cv_summary = cv_payload.get("summary") if isinstance(cv_payload.get("summary"), dict) else {}
    priority_summary = (
        priority_payload.get("summary") if isinstance(priority_payload.get("summary"), dict) else {}
    )
    locked_rows = [row for row in cv_payload.get("locked_cv_rank_residual_rows", []) if isinstance(row, dict)]
    baseline_rows = _baseline_by_key(cv_payload.get("baseline_rank_residual_rows", []))
    fold_proxy = _fold_proxy_by_key(cv_payload.get("locked_cv_fold_rows", []))
    priority_rows = [
        row for row in priority_payload.get("priority_rows", []) if isinstance(row, dict)
    ]
    payload_by_target_pose = _group_payload_priority(priority_rows)

    failure_rows: list[dict[str, Any]] = []
    for residual in locked_rows:
        key = _key(residual)
        baseline = baseline_rows.get(key, {})
        payload_rows = payload_by_target_pose.get((_text(residual.get("target_id")), _text(residual.get("pose_id"))), [])
        locked_error = _int(residual.get("rank_abs_error"))
        baseline_error = _int(baseline.get("rank_abs_error"))
        delta = locked_error - baseline_error
        gaps = _gap_counts(payload_rows)
        failure_class = _failure_class(
            rank_error=locked_error,
            delta=delta,
            split=_text(residual.get("split")),
            payload_rows=payload_rows,
        )
        row = {
            "failure_priority_rank": 0,
            "target_id": _text(residual.get("target_id")),
            "pose_id": _text(residual.get("pose_id")),
            "split": _text(residual.get("split")),
            "source": _text(residual.get("source")),
            "reference_deltaG": _text(residual.get("reference")),
            "baseline_proxy": _text(residual.get("baseline_proxy")),
            "locked_cv_proxy": fold_proxy.get(key, _text(residual.get("variant_proxy"))),
            "reference_rank": _int(residual.get("reference_rank")),
            "locked_cv_rank": _int(residual.get("variant_rank")),
            "baseline_rank": _int(baseline.get("variant_rank")),
            "locked_cv_rank_abs_error": locked_error,
            "baseline_rank_abs_error": baseline_error,
            "rank_abs_error_delta_from_baseline": delta,
            "contact_per_atom": _text(residual.get("contact_per_atom")),
            "pose_atom_count": _text(residual.get("pose_atom_count")),
            "failure_class": failure_class,
            "metric_payload_priority_row_count": len(payload_rows),
            "first_payload_priority_rank": _first_priority(payload_rows),
            "required_metric_names": _metric_names(payload_rows),
            "operator_receipt_blocked_payload_count": gaps.get("operator_receipt_blocked_placeholders", 0),
            "operator_receipt_missing_payload_count": sum(
                count for gap, count in gaps.items() if "missing" in gap or "without_operator_receipt" in gap
            ),
            "existing_metric_source_artifact_present_without_receipt_count": gaps.get(
                "existing_metric_payload_present_without_operator_receipt", 0
            ),
            "operator_gap_classes": ";".join(f"{gap}:{count}" for gap, count in sorted(gaps.items())),
            "next_science_step": _next_science_step(failure_class=failure_class, payload_rows=payload_rows),
            "payload_write_allowed": False,
            "canonical_intake_promotion_allowed": False,
            "claim_promotion_allowed": False,
            "production_score_mutation_allowed": False,
            "external_state_mutated": False,
        }
        failure_rows.append(row)

    sorted_rows = sorted(failure_rows, key=_priority_score, reverse=True)
    for index, row in enumerate(sorted_rows, start=1):
        row["failure_priority_rank"] = index

    locked_p05 = _float(cv_summary.get("locked_cv_bootstrap_p05"))
    fit_p05 = _float(cv_summary.get("fit_trained_best_model_bootstrap_p05"))
    baseline_holdout = _float(cv_summary.get("baseline_holdout_spearman"))
    locked_holdout = _float(cv_summary.get("locked_cv_holdout_spearman"))
    p05_gap = None if locked_p05 is None else max(0.0, MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW - locked_p05)
    holdout_delta = (
        None if baseline_holdout is None or locked_holdout is None else locked_holdout - baseline_holdout
    )
    top_row = sorted_rows[0] if sorted_rows else {}
    high_error_rows = [row for row in sorted_rows if _int(row.get("locked_cv_rank_abs_error")) >= 10]
    cv_regression_rows = [row for row in sorted_rows if _int(row.get("rank_abs_error_delta_from_baseline")) > 0]
    holdout_high_error_rows = [
        row for row in sorted_rows if row.get("split") == "holdout" and _int(row.get("locked_cv_rank_abs_error")) >= 8
    ]
    summary = {
        "packet_type": "refine_tier_public_benchmark_cv_failure_analysis_packet",
        "status": (
            "refine_tier_public_benchmark_cv_failure_analysis_packet_ready"
            if cv_present and locked_rows
            else "blocked_refine_tier_public_benchmark_cv_failure_analysis_packet"
        ),
        "cv_json": _display(cv_json, root=root_path),
        "cv_json_present": cv_present,
        "residual_priority_json": _display(residual_priority_json, root=root_path),
        "residual_priority_json_present": priority_present,
        "locked_cv_model_id": cv_summary.get("locked_cv_model_id", ""),
        "locked_cv_bootstrap_p05": locked_p05,
        "locked_cv_bootstrap_p05_gap_to_claim_grade": p05_gap,
        "fit_trained_best_model_bootstrap_p05": fit_p05,
        "locked_cv_bootstrap_p05_drop_from_fit_trained": (
            None if locked_p05 is None or fit_p05 is None else fit_p05 - locked_p05
        ),
        "baseline_holdout_spearman": baseline_holdout,
        "locked_cv_holdout_spearman": locked_holdout,
        "locked_cv_holdout_spearman_delta_from_baseline": holdout_delta,
        "cross_validation_generalization_ready": bool(
            cv_summary.get("cross_validation_generalization_ready", False)
        ),
        "failure_row_count": len(sorted_rows),
        "high_error_failure_row_count": len(high_error_rows),
        "cv_regression_row_count": len(cv_regression_rows),
        "holdout_high_error_row_count": len(holdout_high_error_rows),
        "payload_priority_matched_failure_row_count": sum(
            1 for row in sorted_rows if _int(row.get("metric_payload_priority_row_count"))
        ),
        "operator_receipt_blocked_payload_count": sum(
            _int(row.get("operator_receipt_blocked_payload_count")) for row in sorted_rows
        ),
        "operator_receipt_missing_payload_count": sum(
            _int(row.get("operator_receipt_missing_payload_count")) for row in sorted_rows
        ),
        "existing_metric_source_artifact_present_without_receipt_count": sum(
            _int(row.get("existing_metric_source_artifact_present_without_receipt_count"))
            for row in sorted_rows
        ),
        "priority_packet_metric_payload_priority_row_count": priority_summary.get(
            "metric_payload_priority_row_count", 0
        ),
        "top_failure_target_id": top_row.get("target_id", ""),
        "top_failure_pose_id": top_row.get("pose_id", ""),
        "top_failure_class": top_row.get("failure_class", ""),
        "top_failure_next_science_step": top_row.get("next_science_step", ""),
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Resolve the top CV failure rows by reviewing their metric payloads/receipts and receptor-pose "
            "descriptor assignments, then rerun calibration cross-validation and bootstrap gates."
        ),
    }
    return {"summary": summary, "failure_rows": sorted_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 CV Failure Analysis Packet",
        "",
        f"- status: `{s['status']}`",
        f"- locked_cv_model_id: `{s['locked_cv_model_id']}`",
        f"- locked_cv_bootstrap_p05: `{s['locked_cv_bootstrap_p05']}`",
        f"- locked_cv_bootstrap_p05_gap_to_claim_grade: `{s['locked_cv_bootstrap_p05_gap_to_claim_grade']}`",
        f"- locked_cv_bootstrap_p05_drop_from_fit_trained: `{s['locked_cv_bootstrap_p05_drop_from_fit_trained']}`",
        f"- locked_cv_holdout_spearman_delta_from_baseline: `{s['locked_cv_holdout_spearman_delta_from_baseline']}`",
        f"- failure_row_count: `{s['failure_row_count']}`",
        f"- high_error_failure_row_count: `{s['high_error_failure_row_count']}`",
        f"- cv_regression_row_count: `{s['cv_regression_row_count']}`",
        f"- holdout_high_error_row_count: `{s['holdout_high_error_row_count']}`",
        f"- payload_priority_matched_failure_row_count: `{s['payload_priority_matched_failure_row_count']}`",
        f"- operator_receipt_blocked_payload_count: `{s['operator_receipt_blocked_payload_count']}`",
        f"- operator_receipt_missing_payload_count: `{s['operator_receipt_missing_payload_count']}`",
        f"- existing_metric_source_artifact_present_without_receipt_count: `{s['existing_metric_source_artifact_present_without_receipt_count']}`",
        f"- top_failure_target_id: `{s['top_failure_target_id']}`",
        f"- top_failure_pose_id: `{s['top_failure_pose_id']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Top Failure Rows",
        "",
        "| rank | target | pose | split | class | locked err | baseline err | delta | payloads | gaps | next step |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["failure_rows"][:12]:
        lines.append(
            f"| `{row['failure_priority_rank']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['split']}` | `{row['failure_class']}` | `{row['locked_cv_rank_abs_error']}` | "
            f"`{row['baseline_rank_abs_error']}` | `{row['rank_abs_error_delta_from_baseline']}` | "
            f"`{row['metric_payload_priority_row_count']}` | `{row['operator_gap_classes']}` | "
            f"`{row['next_science_step']}` |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            s["claim_boundary"],
            "",
            "## Next Step",
            "",
            f"- {s['next_required_step']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an R9 CV failure analysis packet.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--cv-json", default=DEFAULT_CV_JSON)
    parser.add_argument("--residual-priority-json", default=DEFAULT_RESIDUAL_PRIORITY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_cv_failure_analysis_packet(
        cv_json=args.cv_json,
        residual_priority_json=args.residual_priority_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(
        _resolve(args.out_csv, root=root),
        payload["failure_rows"],
    )
    _write_markdown(args.out_md, payload, root=root)


if __name__ == "__main__":
    main()
