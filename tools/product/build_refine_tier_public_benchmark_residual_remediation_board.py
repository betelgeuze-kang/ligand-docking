#!/usr/bin/env python3
"""Read-only R9 residual remediation board for public-benchmark calibration."""
from __future__ import annotations

import argparse
import csv
import json
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
DEFAULT_LEAVE_ONE_OUT_CSV = "runs/refine_tier_public_benchmark_candidate_support_leave_one_out_current.csv"
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_residual_remediation_board_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_residual_remediation_board_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_residual_remediation_board_current.md"

CLAIM_BOUNDARY = (
    "R9 residual remediation board only ranks target/pose residuals from existing read-only diagnostics and "
    "lists evidence needed before another calibration probe. It does not rewrite candidate-fill values, write "
    "reviewed metric payloads, approve operator receipts, promote canonical intake, change production scoring, "
    "run docking/MD, download, upload, email, delete, commit, push, or mutate external state."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int | None:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return None


def _read_csv_rows(path_like: str | Path, *, root: Path) -> list[dict[str, str]]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{str(k): str(v) for k, v in row.items()} for row in csv.DictReader(handle)]


def _residual_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (_text(row.get("target_id")), _text(row.get("pose_id")), _text(row.get("split")))


def _removed_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (_text(row.get("removed_target_id")), _text(row.get("removed_pose_id")), _text(row.get("removed_split")))


def _feature_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (_text(row.get("target_id")), _text(row.get("pose_id")), _text(row.get("split")))


def _rank_direction(variant_rank: int | None, reference_rank: int | None) -> str:
    if variant_rank is None or reference_rank is None:
        return "unknown"
    if variant_rank < reference_rank:
        return "overranked_stronger_than_reference"
    if variant_rank > reference_rank:
        return "underranked_weaker_than_reference"
    return "rank_aligned"


def _primary_action(*, direction: str, p05_delta: float | None, cv_worsened: bool, split: str) -> str:
    if p05_delta is not None and p05_delta >= 0.10:
        return "priority_metric_payload_and_pose_assignment_review"
    if cv_worsened:
        return "target_heldout_generalization_regression_review"
    if direction == "overranked_stronger_than_reference":
        return "overbinding_contact_density_inflation_review"
    if direction == "underranked_weaker_than_reference":
        return "underbinding_pose_contact_coverage_review"
    if split == "holdout":
        return "holdout_metric_payload_confirmation"
    return "metric_payload_confirmation"


def _remediation_note(direction: str) -> str:
    if direction == "overranked_stronger_than_reference":
        return "Audit possible overbinding from contact-density inflation; require reviewed DockQ/lDDT-PLI/internal_deltaG evidence before tuning."
    if direction == "underranked_weaker_than_reference":
        return "Audit possible underbinding or pose/contact coverage loss; verify receptor assembly, pose atom count, contacts, and internal_deltaG source."
    if direction == "rank_aligned":
        return "Rank is aligned; keep as lower priority unless leave-one-out leverage is high."
    return "Residual direction unavailable; verify metric payload schema and source artifacts first."


def _payload_paths(work_order_id: str) -> str:
    if not work_order_id:
        return ""
    metrics = ("dockq", "lddt_pli", "internal_deltaG")
    return ";".join(f"runs/refine_tier_public_benchmark_metric_sources/{work_order_id}_{metric}.json" for metric in metrics)


def _priority_score(row: dict[str, Any]) -> tuple[float, int, int, str]:
    p05_delta = _float(row.get("leave_one_out_bootstrap_p05_delta")) or 0.0
    cv_worsened = 1 if row.get("cv_rank_error_vs_baseline") == "worse" else 0
    rank_abs_error = _int(row.get("locked_cv_rank_abs_error")) or 0
    return (float(rank_abs_error), int(round(p05_delta * 1000)), cv_worsened, _text(row.get("target_id")))


def build_refine_tier_public_benchmark_residual_remediation_board(
    *,
    cross_validation_json: str | Path = DEFAULT_CROSS_VALIDATION_JSON,
    leave_one_out_csv: str | Path = DEFAULT_LEAVE_ONE_OUT_CSV,
    candidate_fill_json: str | Path = DEFAULT_CANDIDATE_FILL_JSON,
    existing_materialization_csv: str | Path = DEFAULT_EXISTING_MATERIALIZATION_CSV,
    root: str | Path = ROOT,
    top_n: int = 12,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    cv_payload, cv_present = _read_json(cross_validation_json, root=root_path)
    cv_summary = cv_payload.get("summary") if isinstance(cv_payload.get("summary"), dict) else {}
    locked_residuals = cv_payload.get("locked_cv_rank_residual_rows", [])
    baseline_residuals = cv_payload.get("baseline_rank_residual_rows", [])
    locked_rows = [row for row in locked_residuals if isinstance(row, dict)]
    baseline_by_key = {_residual_key(row): row for row in baseline_residuals if isinstance(row, dict)}
    leave_one_out_rows = _read_csv_rows(leave_one_out_csv, root=root_path)
    leave_one_out_by_key = {_removed_key(row): row for row in leave_one_out_rows}
    candidate_payload, candidate_present = _read_json(candidate_fill_json, root=root_path)
    feature_rows = [
        *_existing_feature_rows(existing_materialization_csv, root=root_path),
        *_candidate_feature_rows(candidate_payload),
    ]
    feature_by_key = {_feature_key(row): row for row in feature_rows}

    action_rows: list[dict[str, Any]] = []
    for residual in locked_rows:
        key = _residual_key(residual)
        baseline = baseline_by_key.get(key, {})
        loo = leave_one_out_by_key.get(key, {})
        feature = feature_by_key.get(key, {})
        variant_rank = _int(residual.get("variant_rank"))
        reference_rank = _int(residual.get("reference_rank"))
        locked_abs_error = _int(residual.get("rank_abs_error")) or 0
        baseline_abs_error = _int(baseline.get("rank_abs_error")) or 0
        delta = locked_abs_error - baseline_abs_error
        direction = _rank_direction(variant_rank, reference_rank)
        p05_delta = _float(loo.get("bootstrap_p05_delta"))
        primary_action = _primary_action(
            direction=direction,
            p05_delta=p05_delta,
            cv_worsened=delta > 0,
            split=_text(residual.get("split")),
        )
        work_order_id = _text(feature.get("work_order_id")) or _text(loo.get("removed_work_order_id"))
        row = {
            "priority_rank": 0,
            "target_id": _text(residual.get("target_id")),
            "pose_id": _text(residual.get("pose_id")),
            "work_order_id": work_order_id,
            "source": _text(residual.get("source")),
            "split": _text(residual.get("split")),
            "locked_cv_model_id": _text(cv_summary.get("locked_cv_model_id")),
            "locked_cv_proxy": _text(residual.get("variant_proxy")),
            "baseline_proxy": _text(residual.get("baseline_proxy")),
            "reference_deltaG": _text(residual.get("reference")),
            "locked_cv_rank": variant_rank if variant_rank is not None else "",
            "reference_rank": reference_rank if reference_rank is not None else "",
            "locked_cv_rank_abs_error": locked_abs_error,
            "baseline_rank_abs_error": baseline_abs_error,
            "rank_abs_error_delta_from_baseline": delta,
            "cv_rank_error_vs_baseline": "worse" if delta > 0 else ("better" if delta < 0 else "same"),
            "rank_direction": direction,
            "leave_one_out_bootstrap_p05_without_pair": _text(loo.get("bootstrap_p05_without_pair")),
            "leave_one_out_bootstrap_p05_delta": _format_float(p05_delta),
            "leave_one_out_leverage": bool(p05_delta is not None and p05_delta >= 0.05),
            "contact_per_atom": _text(residual.get("contact_per_atom")),
            "pose_atom_count": _text(residual.get("pose_atom_count")),
            "feature_detail_source": _text(feature.get("detail_source")),
            "feature_complete": bool(feature.get("feature_complete", False)),
            "primary_action": primary_action,
            "remediation_note": _remediation_note(direction),
            "required_reviewed_metric_payloads": _payload_paths(work_order_id),
            "payload_write_allowed": False,
            "canonical_intake_promotion_allowed": False,
            "claim_promotion_allowed": False,
            "production_score_mutation_allowed": False,
            "external_state_mutated": False,
        }
        action_rows.append(row)

    sorted_rows = sorted(action_rows, key=_priority_score, reverse=True)
    for index, row in enumerate(sorted_rows, start=1):
        row["priority_rank"] = index
    if top_n > 0:
        sorted_rows = sorted_rows[:top_n]

    locked_p05 = _float(cv_summary.get("locked_cv_bootstrap_p05"))
    p05_gap = (
        None
        if locked_p05 is None
        else max(0.0, MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW - locked_p05)
    )
    high_priority_rows = [
        row
        for row in sorted_rows
        if (_int(row.get("locked_cv_rank_abs_error")) or 0) >= 10
        or bool(row.get("leave_one_out_leverage"))
        or row.get("cv_rank_error_vs_baseline") == "worse"
    ]
    top_row = sorted_rows[0] if sorted_rows else {}
    summary = {
        "packet_type": "refine_tier_public_benchmark_residual_remediation_board",
        "status": (
            "refine_tier_public_benchmark_residual_remediation_board_ready"
            if cv_present and sorted_rows
            else "blocked_refine_tier_public_benchmark_residual_remediation_board"
        ),
        "cross_validation_json": _display(cross_validation_json, root=root_path),
        "cross_validation_present": cv_present,
        "leave_one_out_csv": _display(leave_one_out_csv, root=root_path),
        "leave_one_out_row_count": len(leave_one_out_rows),
        "candidate_fill_json": _display(candidate_fill_json, root=root_path),
        "candidate_fill_present": candidate_present,
        "existing_materialization_csv": _display(existing_materialization_csv, root=root_path),
        "locked_cv_model_id": cv_summary.get("locked_cv_model_id", ""),
        "locked_cv_bootstrap_p05": locked_p05,
        "locked_cv_bootstrap_p05_gap_to_claim_grade": p05_gap,
        "locked_cv_holdout_spearman": cv_summary.get("locked_cv_holdout_spearman"),
        "baseline_holdout_spearman": cv_summary.get("baseline_holdout_spearman"),
        "locked_cv_holdout_non_degradation_ready": bool(
            _float(cv_summary.get("locked_cv_holdout_spearman")) is not None
            and _float(cv_summary.get("baseline_holdout_spearman")) is not None
            and float(cv_summary.get("locked_cv_holdout_spearman")) >= float(cv_summary.get("baseline_holdout_spearman"))
        ),
        "residual_input_row_count": len(locked_rows),
        "remediation_action_row_count": len(sorted_rows),
        "high_priority_action_row_count": len(high_priority_rows),
        "leave_one_out_leverage_row_count": sum(1 for row in sorted_rows if row.get("leave_one_out_leverage")),
        "cv_worse_than_baseline_row_count": sum(1 for row in sorted_rows if row.get("cv_rank_error_vs_baseline") == "worse"),
        "top_priority_target_id": top_row.get("target_id", ""),
        "top_priority_pose_id": top_row.get("pose_id", ""),
        "top_priority_action": top_row.get("primary_action", ""),
        "required_reviewed_metric_payload_count_for_listed_rows": sum(
            3 for row in sorted_rows if row.get("required_reviewed_metric_payloads")
        ),
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Review the listed residual targets with DockQ/lDDT-PLI/internal_deltaG payload evidence, then rerun "
            "candidate fill, cross-validation, and bootstrap gates. Do not promote the locked CV model while p05 "
            "and holdout non-degradation remain below claim-grade requirements."
        ),
    }
    return {"summary": summary, "remediation_rows": sorted_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Residual Remediation Board",
        "",
        f"- status: `{s['status']}`",
        f"- locked_cv_model_id: `{s['locked_cv_model_id']}`",
        f"- locked_cv_bootstrap_p05: `{s['locked_cv_bootstrap_p05']}`",
        f"- locked_cv_bootstrap_p05_gap_to_claim_grade: `{s['locked_cv_bootstrap_p05_gap_to_claim_grade']}`",
        f"- locked_cv_holdout_non_degradation_ready: `{s['locked_cv_holdout_non_degradation_ready']}`",
        f"- remediation_action_row_count: `{s['remediation_action_row_count']}`",
        f"- high_priority_action_row_count: `{s['high_priority_action_row_count']}`",
        f"- leave_one_out_leverage_row_count: `{s['leave_one_out_leverage_row_count']}`",
        f"- cv_worse_than_baseline_row_count: `{s['cv_worse_than_baseline_row_count']}`",
        f"- required_reviewed_metric_payload_count_for_listed_rows: `{s['required_reviewed_metric_payload_count_for_listed_rows']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Top Actions",
        "",
        "| rank | target | pose | split | direction | cv err | baseline err | p05 delta if removed | action |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["remediation_rows"]:
        lines.append(
            f"| `{row['priority_rank']}` | `{row['target_id']}` | `{row['pose_id']}` | `{row['split']}` | "
            f"`{row['rank_direction']}` | `{row['locked_cv_rank_abs_error']}` | "
            f"`{row['baseline_rank_abs_error']}` | `{row['leave_one_out_bootstrap_p05_delta']}` | "
            f"`{row['primary_action']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 residual remediation board.")
    parser.add_argument("--cross-validation-json", default=DEFAULT_CROSS_VALIDATION_JSON)
    parser.add_argument("--leave-one-out-csv", default=DEFAULT_LEAVE_ONE_OUT_CSV)
    parser.add_argument("--candidate-fill-json", default=DEFAULT_CANDIDATE_FILL_JSON)
    parser.add_argument("--existing-materialization-csv", default=DEFAULT_EXISTING_MATERIALIZATION_CSV)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--top-n", type=int, default=12)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_residual_remediation_board(
        cross_validation_json=args.cross_validation_json,
        leave_one_out_csv=args.leave_one_out_csv,
        candidate_fill_json=args.candidate_fill_json,
        existing_materialization_csv=args.existing_materialization_csv,
        root=root,
        top_n=args.top_n,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["remediation_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
