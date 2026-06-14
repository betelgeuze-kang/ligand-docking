#!/usr/bin/env python3
"""Read-only R9 calibration cross-validation probe for public-benchmark scoring."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_fit_trained_calibration_probe import (
    DEFAULT_CANDIDATE_FILL_JSON,
    DEFAULT_EXISTING_MATERIALIZATION_CSV,
    MODEL_SPECS,
    ROOT,
    _evaluate_scores,
    _feature_count,
    _feature_matrix,
    _format_float,
    _model_sort_key,
    _safe_std,
)
from tools.product.build_refine_tier_public_benchmark_score_variant_probe import (
    _candidate_feature_rows,
    _display,
    _existing_feature_rows,
    _float,
    _rank_residual_rows,
    _read_json,
    _resolve,
)
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
)

DEFAULT_FIT_TRAINED_JSON = "config/refine_tier_public_benchmark_fit_trained_calibration_probe_current.json"
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_calibration_cross_validation_probe_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_calibration_cross_validation_probe_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_calibration_cross_validation_probe_current.md"

CLAIM_BOUNDARY = (
    "R9 calibration cross-validation probe only; it trains predeclared scoring hypotheses while leaving "
    "one target out at a time and reports out-of-fold diagnostics. It does not rewrite candidate-fill "
    "values, write reviewed metric payloads, approve operator receipts, promote canonical intake, change "
    "production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external "
    "state."
)


def _fit_predict_fold(
    rows: list[dict[str, Any]],
    *,
    features: tuple[str, ...],
    ridge_lambda: float,
    train_indexes: list[int],
    test_indexes: list[int],
) -> list[float]:
    x_raw = _feature_matrix(rows, features)
    x_train = x_raw[train_indexes]
    mean = np.mean(x_train, axis=0)
    std = _safe_std(x_train)
    design = np.column_stack([np.ones(len(rows), dtype=np.float64), (x_raw - mean) / std])
    design_train = design[train_indexes]
    y_train = np.asarray([float(rows[index]["reference"]) for index in train_indexes], dtype=np.float64)
    penalty = np.eye(design_train.shape[1], dtype=np.float64) * float(ridge_lambda)
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(
        design_train.T @ design_train + penalty,
        design_train.T @ y_train,
    )
    return [float(value) for value in design[test_indexes] @ coefficients]


def _target_folds(rows: list[dict[str, Any]]) -> list[tuple[str, list[int], list[int]]]:
    targets = sorted({str(row.get("target_id") or "") for row in rows if str(row.get("target_id") or "")})
    folds: list[tuple[str, list[int], list[int]]] = []
    for target in targets:
        test_indexes = [index for index, row in enumerate(rows) if row.get("target_id") == target]
        train_indexes = [index for index in range(len(rows)) if index not in set(test_indexes)]
        if train_indexes and test_indexes:
            folds.append((target, train_indexes, test_indexes))
    return folds


def _cross_validated_scores(
    rows: list[dict[str, Any]],
    *,
    features: tuple[str, ...],
    ridge_lambda: float,
) -> tuple[list[float], list[dict[str, Any]]]:
    scores: list[float | None] = [None] * len(rows)
    fold_rows: list[dict[str, Any]] = []
    for target, train_indexes, test_indexes in _target_folds(rows):
        predictions = _fit_predict_fold(
            rows,
            features=features,
            ridge_lambda=ridge_lambda,
            train_indexes=train_indexes,
            test_indexes=test_indexes,
        )
        for index, prediction in zip(test_indexes, predictions):
            scores[index] = float(prediction)
            fold_rows.append(
                {
                    "target_id": target,
                    "pose_id": rows[index].get("pose_id", ""),
                    "split": rows[index].get("split", ""),
                    "train_pair_count": len(train_indexes),
                    "test_pair_count": len(test_indexes),
                    "reference": _format_float(float(rows[index]["reference"])),
                    "cv_proxy": _format_float(float(prediction)),
                }
            )
    if any(score is None for score in scores):
        raise ValueError("cross-validation failed to score every row")
    return [float(score) for score in scores if score is not None], fold_rows


def _read_fit_trained_reference(path_like: str | Path, *, root: Path) -> tuple[dict[str, Any], bool]:
    payload, present = _read_json(path_like, root=root)
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    return summary if isinstance(summary, dict) else {}, present


def build_refine_tier_public_benchmark_calibration_cross_validation_probe(
    *,
    candidate_fill_json: str | Path = DEFAULT_CANDIDATE_FILL_JSON,
    existing_materialization_csv: str | Path = DEFAULT_EXISTING_MATERIALIZATION_CSV,
    fit_trained_json: str | Path = DEFAULT_FIT_TRAINED_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    candidate_payload, candidate_present = _read_json(candidate_fill_json, root=root_path)
    fit_reference, fit_reference_present = _read_fit_trained_reference(fit_trained_json, root=root_path)
    existing_rows = _existing_feature_rows(existing_materialization_csv, root=root_path)
    candidate_rows = _candidate_feature_rows(candidate_payload)
    rows = [*existing_rows, *candidate_rows]
    baseline_scores = [float(row["baseline_proxy"]) for row in rows]
    baseline_eval = _evaluate_scores(rows, baseline_scores) if rows else {}
    baseline_p05 = _float(baseline_eval.get("free_energy_spearman_bootstrap_p05"))
    baseline_holdout = _float(baseline_eval.get("holdout_spearman"))
    baseline_combined = _float(baseline_eval.get("combined_spearman"))

    model_rows: list[dict[str, Any]] = []
    residual_by_model: dict[str, list[dict[str, Any]]] = {}
    fold_rows_by_model: dict[str, list[dict[str, Any]]] = {}
    if len(rows) >= 3:
        for family, features, lambdas in MODEL_SPECS:
            for ridge_lambda in lambdas:
                model_id = f"{family}_ridge_l{ridge_lambda:g}"
                scores, fold_rows = _cross_validated_scores(rows, features=features, ridge_lambda=ridge_lambda)
                metrics = _evaluate_scores(rows, scores)
                p05 = _float(metrics.get("free_energy_spearman_bootstrap_p05"))
                holdout = _float(metrics.get("holdout_spearman"))
                combined = _float(metrics.get("combined_spearman"))
                model_row = {
                    "model_id": model_id,
                    "model_family": family,
                    "feature_names": ";".join(features),
                    "feature_count": len(features),
                    "ridge_lambda": _format_float(float(ridge_lambda)),
                    **metrics,
                    "bootstrap_p05_delta_from_baseline": (
                        None if baseline_p05 is None or p05 is None else p05 - baseline_p05
                    ),
                    "holdout_spearman_delta_from_baseline": (
                        None if baseline_holdout is None or holdout is None else holdout - baseline_holdout
                    ),
                    "combined_spearman_delta_from_baseline": (
                        None if baseline_combined is None or combined is None else combined - baseline_combined
                    ),
                    "holdout_guarded_eligible": bool(
                        p05 is not None
                        and holdout is not None
                        and combined is not None
                        and baseline_holdout is not None
                        and baseline_combined is not None
                        and holdout >= baseline_holdout
                        and combined >= baseline_combined
                    ),
                    "claim_grade_p05_ready": bool(
                        p05 is not None and p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW
                    ),
                    "cross_validation_mode": "leave_one_target_out",
                    "fold_count": len(fold_rows),
                    "diagnostic_only": True,
                }
                residual_rows = _rank_residual_rows(rows, scores)
                top_residual = residual_rows[0] if residual_rows else {}
                model_row.update(
                    {
                        "top_rank_residual_target_id": top_residual.get("target_id", ""),
                        "top_rank_residual_pose_id": top_residual.get("pose_id", ""),
                        "top_rank_residual_split": top_residual.get("split", ""),
                        "top_rank_residual_abs_error": int(top_residual.get("rank_abs_error") or 0),
                    }
                )
                model_rows.append(model_row)
                residual_by_model[model_id] = residual_rows
                fold_rows_by_model[model_id] = fold_rows

    sorted_models = sorted(model_rows, key=_model_sort_key, reverse=True)
    best_cv = sorted_models[0] if sorted_models else {}
    eligible_models = [row for row in sorted_models if bool(row.get("holdout_guarded_eligible"))]
    best_guarded = eligible_models[0] if eligible_models else {}
    locked_model_id = str(fit_reference.get("best_model_id") or "")
    locked_cv = next((row for row in sorted_models if row.get("model_id") == locked_model_id), {})
    if not locked_cv:
        locked_cv = best_cv
        locked_model_id = str(locked_cv.get("model_id") or "")
    locked_cv_p05 = _float(locked_cv.get("free_energy_spearman_bootstrap_p05"))
    fit_reference_p05 = _float(fit_reference.get("best_model_bootstrap_p05"))
    best_cv_p05 = _float(best_cv.get("free_energy_spearman_bootstrap_p05"))
    best_guarded_p05 = _float(best_guarded.get("free_energy_spearman_bootstrap_p05"))
    summary = {
        "packet_type": "refine_tier_public_benchmark_calibration_cross_validation_probe",
        "status": (
            "refine_tier_public_benchmark_calibration_cross_validation_probe_ready"
            if candidate_present and rows and model_rows
            else "blocked_refine_tier_public_benchmark_calibration_cross_validation_probe"
        ),
        "candidate_fill_json": _display(candidate_fill_json, root=root_path),
        "candidate_fill_present": candidate_present,
        "existing_materialization_csv": _display(existing_materialization_csv, root=root_path),
        "fit_trained_json": _display(fit_trained_json, root=root_path),
        "fit_trained_reference_present": fit_reference_present,
        "existing_pair_count": len(existing_rows),
        "candidate_pair_count": len(candidate_rows),
        "combined_pair_count": len(rows),
        "fit_pair_count": sum(1 for row in rows if row.get("split") == "fit"),
        "holdout_pair_count": sum(1 for row in rows if row.get("split") == "holdout"),
        "target_fold_count": len(_target_folds(rows)),
        "feature_complete_pair_count": _feature_count(rows, "feature_complete"),
        "candidate_detail_from_rows_pair_count": _feature_count(
            candidate_rows, "detail_source", "candidate_rows_internal_deltaG"
        ),
        "model_candidate_count": len(model_rows),
        "holdout_guarded_eligible_model_count": len(eligible_models),
        "bootstrap_iteration_count": BOOTSTRAP_ITERATIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "min_claim_grade_bootstrap_spearman_low_required": MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
        "baseline_holdout_spearman": baseline_eval.get("holdout_spearman"),
        "baseline_combined_spearman": baseline_eval.get("combined_spearman"),
        "baseline_bootstrap_p05": baseline_p05,
        "fit_trained_best_model_id": fit_reference.get("best_model_id", ""),
        "fit_trained_best_model_bootstrap_p05": fit_reference_p05,
        "locked_cv_model_id": locked_model_id,
        "locked_cv_holdout_spearman": locked_cv.get("holdout_spearman"),
        "locked_cv_combined_spearman": locked_cv.get("combined_spearman"),
        "locked_cv_bootstrap_p05": locked_cv_p05,
        "locked_cv_bootstrap_p05_drop_from_fit_trained": (
            None if fit_reference_p05 is None or locked_cv_p05 is None else fit_reference_p05 - locked_cv_p05
        ),
        "locked_cv_claim_grade_p05_ready": bool(
            locked_cv_p05 is not None and locked_cv_p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW
        ),
        "best_cv_model_id": best_cv.get("model_id", ""),
        "best_cv_model_feature_names": best_cv.get("feature_names", ""),
        "best_cv_holdout_spearman": best_cv.get("holdout_spearman"),
        "best_cv_combined_spearman": best_cv.get("combined_spearman"),
        "best_cv_bootstrap_p05": best_cv_p05,
        "best_cv_claim_grade_p05_ready": bool(
            best_cv_p05 is not None and best_cv_p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW
        ),
        "best_guarded_cv_model_id": best_guarded.get("model_id", ""),
        "best_guarded_cv_bootstrap_p05": best_guarded_p05,
        "cross_validation_generalization_ready": bool(
            best_guarded
            and best_guarded_p05 is not None
            and best_guarded_p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW
        ),
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "selection_policy": (
            "leave-one-target-out probes may diagnose generalization but may not promote scoring; claim-grade "
            "requires out-of-fold p05 >= threshold and holdout non-degradation, followed by reviewed payload evidence"
        ),
        "next_required_step": (
            "Do not use the near-threshold fit-trained model for production scoring. Add independent/operator-reviewed "
            "R9 evidence or reduce top residual targets, then rerun cross-validation and claim-grade bootstrap gates."
        ),
    }
    best_model_id = str(best_cv.get("model_id") or "")
    return {
        "summary": summary,
        "cv_model_rows": sorted_models,
        "best_cv_rank_residual_rows": residual_by_model.get(best_model_id, [])[:25],
        "locked_cv_rank_residual_rows": residual_by_model.get(locked_model_id, [])[:25],
        "locked_cv_fold_rows": fold_rows_by_model.get(locked_model_id, [])[:25],
        "baseline_rank_residual_rows": _rank_residual_rows(rows, baseline_scores)[:25] if rows else [],
    }


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Calibration Cross-Validation Probe",
        "",
        f"- status: `{s['status']}`",
        f"- cross_validation_mode: `leave_one_target_out`",
        f"- combined_pair_count: `{s['combined_pair_count']}`",
        f"- target_fold_count: `{s['target_fold_count']}`",
        f"- baseline_holdout/combined/p05: `{s['baseline_holdout_spearman']}/"
        f"{s['baseline_combined_spearman']}/{s['baseline_bootstrap_p05']}`",
        f"- fit_trained_best_model_id: `{s['fit_trained_best_model_id']}`",
        f"- fit_trained_best_model_bootstrap_p05: `{s['fit_trained_best_model_bootstrap_p05']}`",
        f"- locked_cv_model_id: `{s['locked_cv_model_id']}`",
        f"- locked_cv_holdout/combined/p05: `{s['locked_cv_holdout_spearman']}/"
        f"{s['locked_cv_combined_spearman']}/{s['locked_cv_bootstrap_p05']}`",
        f"- locked_cv_bootstrap_p05_drop_from_fit_trained: `{s['locked_cv_bootstrap_p05_drop_from_fit_trained']}`",
        f"- best_cv_model_id: `{s['best_cv_model_id']}`",
        f"- best_cv_holdout/combined/p05: `{s['best_cv_holdout_spearman']}/"
        f"{s['best_cv_combined_spearman']}/{s['best_cv_bootstrap_p05']}`",
        f"- holdout_guarded_eligible_model_count: `{s['holdout_guarded_eligible_model_count']}`",
        f"- cross_validation_generalization_ready: `{s['cross_validation_generalization_ready']}`",
        "",
        "## Top Cross-Validated Models",
        "",
        "| model | features | lambda | holdout | combined | p05 | p05 delta | holdout guarded | claim-grade p05 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["cv_model_rows"][:12]:
        lines.append(
            f"| `{row['model_id']}` | `{row['feature_names']}` | `{row['ridge_lambda']}` | "
            f"`{_format_float(_float(row.get('holdout_spearman')))}` | "
            f"`{_format_float(_float(row.get('combined_spearman')))}` | "
            f"`{_format_float(_float(row.get('free_energy_spearman_bootstrap_p05')))}` | "
            f"`{_format_float(_float(row.get('bootstrap_p05_delta_from_baseline')))}` | "
            f"`{row['holdout_guarded_eligible']}` | `{row['claim_grade_p05_ready']}` |"
        )
    lines.extend(
        [
            "",
            "## Locked Model Residuals",
            "",
            "| target | pose | source | split | variant rank | reference rank | rank abs error |",
            "| --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in payload["locked_cv_rank_residual_rows"][:10]:
        lines.append(
            f"| `{row['target_id']}` | `{row['pose_id']}` | `{row['source']}` | `{row['split']}` | "
            f"`{row['variant_rank']}` | `{row['reference_rank']}` | `{row['rank_abs_error']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 calibration cross-validation probe.")
    parser.add_argument("--candidate-fill-json", default=DEFAULT_CANDIDATE_FILL_JSON)
    parser.add_argument("--existing-materialization-csv", default=DEFAULT_EXISTING_MATERIALIZATION_CSV)
    parser.add_argument("--fit-trained-json", default=DEFAULT_FIT_TRAINED_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_calibration_cross_validation_probe(
        candidate_fill_json=args.candidate_fill_json,
        existing_materialization_csv=args.existing_materialization_csv,
        fit_trained_json=args.fit_trained_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["cv_model_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
