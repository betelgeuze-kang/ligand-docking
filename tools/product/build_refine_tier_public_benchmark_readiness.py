#!/usr/bin/env python3
"""Fail-closed readiness gate for curated refine-tier public benchmarks."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from core.score_calibration import calibration_quality_gate, fit_linear_calibration
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_CSV = "config/refine_tier_public_benchmark_intake_current.csv"
DEFAULT_OUT_JSON = "runs/refine_tier_public_benchmark_readiness_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_readiness_current.csv"
DEFAULT_OUT_MD = "runs/refine_tier_public_benchmark_readiness_current.md"
DEFAULT_OUT_WORK_ORDER_CSV = "runs/refine_tier_public_benchmark_work_order_current.csv"
REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN = "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE"
DEFAULT_WORK_ORDER_APPLY_COMMAND = "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py"
DEFAULT_WORK_ORDER_APPLY_WRITE_INTAKE_COMMAND = (
    "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py "
    f"--write-intake --approval-token {REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN}"
)

REQUIRED_COLUMNS = [
    "benchmark_id",
    "target_id",
    "benchmark_family",
    "split",
    "provenance_kind",
    "provenance_id",
    "license_ok",
    "external_engine_calls",
    "pose_rmsd_A",
    "dockq",
    "lddt_pli",
    "deltaG_mm_gbsa_kcal_mol",
    "deltaG_experimental_kcal_mol",
]
ALLOWED_PROVENANCE_KINDS = {"pdbbind", "casf", "bm5", "public_pdb", "operator_curated_public"}
ALLOWED_SPLITS = {"fit", "holdout", "test"}
CLAIM_BOUNDARY = (
    "Refine-tier public benchmark readiness only; verifies operator-curated public pose/free-energy rows, "
    "provenance, licensing flags, and no external engine calls. It does not download data, run docking/MD, "
    "contact providers, or open an OpenMM/Schrödinger-grade claim."
)

WORK_ORDER_COLUMNS = [
    "work_order_id",
    "target_input_csv",
    "template_row_index",
    "benchmark_id",
    "target_id",
    "benchmark_family",
    "split",
    "provenance_kind",
    "provenance_id",
    "license_ok",
    "external_engine_calls",
    "pose_rmsd_A",
    "dockq",
    "lddt_pli",
    "deltaG_mm_gbsa_kcal_mol",
    "deltaG_experimental_kcal_mol",
    "operator_action",
    "acceptance_rule",
    "external_state_mutated",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return default


def _float(value: Any) -> float | None:
    try:
        out = float(_text(value))
    except (TypeError, ValueError):
        return None
    return out if np.isfinite(out) else None


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, Any]], list[str], bool]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [], False
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader], list(reader.fieldnames or []), True


def _row_status(row: dict[str, Any], *, max_pose_rmsd_a: float, min_dockq: float, min_lddt_pli: float) -> dict[str, Any]:
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in row]
    provenance_ok = _text(row.get("provenance_kind")) in ALLOWED_PROVENANCE_KINDS and bool(_text(row.get("provenance_id")))
    split_ok = _text(row.get("split")).lower() in ALLOWED_SPLITS
    license_ok = _bool(row.get("license_ok"))
    external_engine_calls = _int(row.get("external_engine_calls"), default=999999)
    external_engine_ok = external_engine_calls == 0
    pose_rmsd = _float(row.get("pose_rmsd_A"))
    dockq = _float(row.get("dockq"))
    lddt = _float(row.get("lddt_pli"))
    dg_refine = _float(row.get("deltaG_mm_gbsa_kcal_mol"))
    dg_exp = _float(row.get("deltaG_experimental_kcal_mol"))
    pose_metrics_present = pose_rmsd is not None and dockq is not None and lddt is not None
    pose_metrics_pass = bool(
        pose_metrics_present
        and pose_rmsd <= float(max_pose_rmsd_a)
        and dockq >= float(min_dockq)
        and lddt >= float(min_lddt_pli)
    )
    free_energy_pair_present = dg_refine is not None and dg_exp is not None
    blockers: list[str] = []
    if missing_columns:
        blockers.append("missing_columns:" + ",".join(missing_columns))
    if not provenance_ok:
        blockers.append("provenance_missing_or_unaccepted")
    if not split_ok:
        blockers.append("split_missing_or_unaccepted")
    if not license_ok:
        blockers.append("license_not_ok")
    if not external_engine_ok:
        blockers.append("external_engine_calls_present")
    if not pose_metrics_present:
        blockers.append("pose_metrics_missing")
    elif not pose_metrics_pass:
        blockers.append("pose_metrics_threshold_failed")
    if not free_energy_pair_present:
        blockers.append("free_energy_pair_missing")
    return {
        **row,
        "row_status": "pass" if not blockers else "blocked",
        "blockers": ";".join(blockers),
        "provenance_ok": provenance_ok,
        "split_ok": split_ok,
        "license_ok_bool": license_ok,
        "external_engine_ok": external_engine_ok,
        "pose_metrics_present": pose_metrics_present,
        "pose_metrics_pass": pose_metrics_pass,
        "free_energy_pair_present": free_energy_pair_present,
    }


def _build_operator_work_order_rows(
    *,
    input_csv: str | Path,
    existing_row_count: int,
    valid_row_count: int,
    pose_pass_count: int,
    free_energy_pair_count: int,
    fit_split_present: bool,
    holdout_or_test_split_present: bool,
    min_total_rows: int,
    min_pose_rows: int,
    min_free_energy_pairs: int,
) -> list[dict[str, Any]]:
    needed = max(
        int(min_total_rows) - int(existing_row_count),
        int(min_total_rows) - int(valid_row_count),
        int(min_pose_rows) - int(pose_pass_count),
        int(min_free_energy_pairs) - int(free_energy_pair_count),
        0,
    )
    if needed <= 0 and fit_split_present and holdout_or_test_split_present:
        return []
    if needed <= 0:
        needed = 2

    rows: list[dict[str, Any]] = []
    for idx in range(needed):
        split = "fit" if idx < max(1, min(5, needed - 1)) else "holdout"
        if not fit_split_present and holdout_or_test_split_present and idx == 0:
            split = "fit"
        if fit_split_present and not holdout_or_test_split_present and idx == needed - 1:
            split = "holdout"
        row = {
            "work_order_id": f"refine_tier_public_benchmark_fill_{idx + 1:03d}",
            "target_input_csv": str(input_csv),
            "template_row_index": idx + 1,
            "benchmark_id": f"OPERATOR_FILL_PUBLIC_BENCHMARK_{idx + 1:03d}",
            "target_id": "OPERATOR_FILL_TARGET_OR_COMPLEX_ID",
            "benchmark_family": "pdbbind_or_casf_refine_tier_public",
            "split": split,
            "provenance_kind": "operator_curated_public",
            "provenance_id": "OPERATOR_FILL_PUBLIC_SOURCE_ID",
            "license_ok": "OPERATOR_CONFIRM_TRUE",
            "external_engine_calls": 0,
            "pose_rmsd_A": "OPERATOR_FILL_POSE_RMSD_A",
            "dockq": "OPERATOR_FILL_DOCKQ",
            "lddt_pli": "OPERATOR_FILL_LDDT_PLI",
            "deltaG_mm_gbsa_kcal_mol": "OPERATOR_FILL_INTERNAL_REFINE_DG",
            "deltaG_experimental_kcal_mol": "OPERATOR_FILL_PUBLIC_EXPERIMENTAL_DG",
            "operator_action": "append_validated_public_benchmark_row",
            "acceptance_rule": (
                "Fill all required columns from public provenance, set external_engine_calls=0, "
                "include at least one fit and one holdout/test split, and rerun this readiness gate."
            ),
            "external_state_mutated": False,
        }
        rows.append(row)
    return rows


def build_refine_tier_public_benchmark_readiness(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    min_total_rows: int = 8,
    min_pose_rows: int = 5,
    min_free_energy_pairs: int = 5,
    min_spearman: float = 0.5,
    max_pose_rmsd_a: float = 2.5,
    min_dockq: float = 0.23,
    min_lddt_pli: float = 0.5,
) -> dict[str, Any]:
    raw_rows, columns, input_present = _read_csv(input_csv)
    row_missing_columns = [col for col in REQUIRED_COLUMNS if col not in columns] if input_present else list(REQUIRED_COLUMNS)
    rows = [
        _row_status(row, max_pose_rmsd_a=max_pose_rmsd_a, min_dockq=min_dockq, min_lddt_pli=min_lddt_pli)
        for row in raw_rows
    ]
    valid_rows = [row for row in rows if not row["blockers"]]
    pose_rows = [row for row in rows if row["pose_metrics_present"]]
    pose_pass_rows = [row for row in rows if row["pose_metrics_pass"]]
    free_energy_rows = [row for row in rows if row["free_energy_pair_present"]]
    splits = sorted({_text(row.get("split")).lower() for row in rows if _text(row.get("split")).lower() in ALLOWED_SPLITS})
    fit_ready = "fit" in splits
    holdout_ready = bool({"holdout", "test"} & set(splits))
    spearman: float | None = None
    calibration_ready = False
    if free_energy_rows:
        fit = fit_linear_calibration(
            [_float(row.get("deltaG_mm_gbsa_kcal_mol")) for row in free_energy_rows],
            [_float(row.get("deltaG_experimental_kcal_mol")) for row in free_energy_rows],
        )
        gate = calibration_quality_gate(fit, min_pairs=min_free_energy_pairs, min_spearman=min_spearman)
        spearman = gate.get("spearman")
        calibration_ready = bool(gate.get("calibration_promotion_ready"))
    else:
        gate = {
            "calibration_promotion_ready": False,
            "pair_count": 0,
            "spearman": None,
            "min_pairs_required": min_free_energy_pairs,
            "min_spearman_required": min_spearman,
        }

    blockers: list[str] = []
    if not input_present:
        blockers.append("input_csv_missing")
    if row_missing_columns:
        blockers.append("required_columns_missing:" + ",".join(row_missing_columns))
    if len(rows) < int(min_total_rows):
        blockers.append("insufficient_total_rows")
    if len(valid_rows) < int(min_total_rows):
        blockers.append("insufficient_valid_rows")
    if len(pose_pass_rows) < int(min_pose_rows):
        blockers.append("insufficient_pose_metric_pass_rows")
    if len(free_energy_rows) < int(min_free_energy_pairs):
        blockers.append("insufficient_free_energy_pairs")
    if not calibration_ready:
        blockers.append("free_energy_spearman_or_pair_gate_not_ready")
    if not fit_ready or not holdout_ready:
        blockers.append("fit_and_holdout_splits_required")

    ready = not blockers
    summary = {
        "packet_type": "refine_tier_public_benchmark_readiness",
        "status": "refine_tier_public_benchmark_ready" if ready else "blocked_refine_tier_public_benchmark_readiness",
        "claim_grade_public_benchmark_ready": ready,
        "benchmark_metric_surface_ready": len(pose_rows) > 0 and len(free_energy_rows) > 0,
        "input_csv": str(input_csv),
        "input_csv_present": input_present,
        "row_count": len(rows),
        "valid_row_count": len(valid_rows),
        "pose_metric_row_count": len(pose_rows),
        "pose_metric_pass_count": len(pose_pass_rows),
        "free_energy_pair_count": len(free_energy_rows),
        "fit_split_present": fit_ready,
        "holdout_or_test_split_present": holdout_ready,
        "free_energy_spearman": spearman,
        "min_total_rows_required": int(min_total_rows),
        "min_pose_rows_required": int(min_pose_rows),
        "min_free_energy_pairs_required": int(min_free_energy_pairs),
        "min_spearman_required": float(min_spearman),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    work_order_rows = _build_operator_work_order_rows(
        input_csv=input_csv,
        existing_row_count=len(rows),
        valid_row_count=len(valid_rows),
        pose_pass_count=len(pose_pass_rows),
        free_energy_pair_count=len(free_energy_rows),
        fit_split_present=fit_ready,
        holdout_or_test_split_present=holdout_ready,
        min_total_rows=min_total_rows,
        min_pose_rows=min_pose_rows,
        min_free_energy_pairs=min_free_energy_pairs,
    )
    summary["work_order_row_count"] = len(work_order_rows)
    summary["operator_work_order_ready"] = bool(work_order_rows and not ready)
    summary["work_order_columns"] = WORK_ORDER_COLUMNS
    summary["work_order_csv"] = DEFAULT_OUT_WORK_ORDER_CSV
    summary["work_order_apply_command"] = DEFAULT_WORK_ORDER_APPLY_COMMAND
    summary["work_order_apply_write_intake_command"] = DEFAULT_WORK_ORDER_APPLY_WRITE_INTAKE_COMMAND
    summary["write_intake_approval_token_required"] = REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN
    summary["next_required_step"] = (
        "Fill the work-order CSV from reviewed public provenance, run the apply command to validate row and aggregate readiness, "
        "then rerun with --write-intake only after the apply gate is ready."
        if work_order_rows and not ready
        else "Public benchmark readiness is ready; no work-order apply step is required."
    )
    return {
        "summary": summary,
        "rows": rows,
        "work_order_rows": work_order_rows,
        "required_columns": REQUIRED_COLUMNS,
        "work_order_columns": WORK_ORDER_COLUMNS,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Refine Tier Public Benchmark Readiness",
        "",
        f"- status: `{summary['status']}`",
        f"- claim_grade_public_benchmark_ready: `{summary['claim_grade_public_benchmark_ready']}`",
        f"- rows valid/total: `{summary['valid_row_count']}/{summary['row_count']}`",
        f"- pose pass rows: `{summary['pose_metric_pass_count']}`",
        f"- free-energy pairs: `{summary['free_energy_pair_count']}`",
        f"- free-energy Spearman: `{summary['free_energy_spearman']}`",
        f"- blockers: `{summary['blocker_count']}`",
        f"- work-order rows: `{summary.get('work_order_row_count', 0)}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if not summary["blockers"]:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Operator Work Order",
            "",
            f"- operator_work_order_ready: `{summary.get('operator_work_order_ready', False)}`",
            f"- target input CSV: `{summary['input_csv']}`",
            f"- work-order CSV: `{summary.get('work_order_csv')}`",
            f"- validate command: `{summary.get('work_order_apply_command')}`",
            f"- write-intake command: `{summary.get('work_order_apply_write_intake_command')}`",
            f"- write-intake approval token: `{summary.get('write_intake_approval_token_required')}`",
            "- fill the work-order CSV after operator/public-source review, validate it with the apply command, then use the write-intake command only after the apply gate is ready.",
            "- rerun this builder after intake rows are applied; this builder does not download data or run docking/MD.",
        ]
    )
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build refine-tier public benchmark readiness gate.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-work-order-csv", default=DEFAULT_OUT_WORK_ORDER_CSV)
    args = parser.parse_args(argv)
    payload = build_refine_tier_public_benchmark_readiness(input_csv=args.input_csv)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    write_csv_rows(_resolve(args.out_work_order_csv), payload["work_order_rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
