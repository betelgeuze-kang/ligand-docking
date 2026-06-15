#!/usr/bin/env python3
"""Read-only R9 CV model-extension probe for public-benchmark scoring."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_fit_trained_calibration_probe import (
    _evaluate_scores,
    _safe_std,
)
from tools.product.build_refine_tier_public_benchmark_score_variant_probe import (
    DEFAULT_CANDIDATE_FILL_JSON,
    DEFAULT_EXISTING_MATERIALIZATION_CSV,
    ROOT,
    _candidate_feature_rows,
    _display,
    _existing_feature_rows,
    _float,
    _format_float,
    _rank_residual_rows,
    _read_json,
    _resolve,
)
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
)

DEFAULT_CROSS_VALIDATION_JSON = "config/refine_tier_public_benchmark_calibration_cross_validation_probe_current.json"
DEFAULT_FEATURE_EXTRAPOLATION_JSON = (
    "config/refine_tier_public_benchmark_cv_feature_extrapolation_probe_current.json"
)
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_cv_model_extension_probe_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_cv_model_extension_probe_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_cv_model_extension_probe_current.md"

MATERIAL_P05_DELTA_THRESHOLD = 0.02

MODEL_EXTENSION_SPECS: tuple[tuple[str, tuple[str, ...], tuple[float, ...]], ...] = (
    ("density_size", ("contact_per_atom", "pose_atom_count"), (0.1, 0.3, 1.0, 3.0, 10.0)),
    (
        "density_size_quadratic",
        ("contact_per_atom", "pose_atom_count", "contact_per_atom_sq", "pose_atom_count_sq"),
        (0.1, 0.3, 1.0, 3.0, 10.0),
    ),
    (
        "density_size_interaction",
        ("contact_per_atom", "pose_atom_count", "contact_x_pose_atom_count"),
        (0.1, 0.3, 1.0, 3.0, 10.0),
    ),
    (
        "density_size_contact_over_size",
        ("contact_per_atom", "pose_atom_count", "contact_per_atom_over_pose_atom_count"),
        (0.1, 0.3, 1.0, 3.0, 10.0),
    ),
    (
        "density_size_min_distance",
        ("contact_per_atom", "pose_atom_count", "min_distance_a"),
        (0.1, 0.3, 1.0, 3.0, 10.0),
    ),
    (
        "density_size_log",
        ("contact_per_atom", "pose_atom_count", "log_contact_per_atom"),
        (0.1, 0.3, 1.0, 3.0, 10.0),
    ),
    (
        "baseline_density_size_interaction",
        ("baseline_proxy", "contact_per_atom", "pose_atom_count", "baseline_x_contact_per_atom", "baseline_x_pose_atom_count"),
        (0.1, 0.3, 1.0, 3.0, 10.0),
    ),
)

CLAIM_BOUNDARY = (
    "R9 CV model-extension probe only evaluates predeclared interaction/nonlinear descriptor hypotheses "
    "with leave-one-target-out diagnostics. It does not rewrite scores, write reviewed metric payloads, "
    "approve receipts, promote canonical intake, change production scoring, run docking/MD, download, "
    "upload, email, delete, commit, push, or mutate external state."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _feature_value(row: dict[str, Any], feature: str) -> float:
    baseline = float(row["baseline_proxy"])
    contact = float(row["contact_per_atom"])
    pose_atoms = float(row["pose_atom_count"])
    if feature == "baseline_proxy":
        return baseline
    if feature == "contact_per_atom":
        return contact
    if feature == "pose_atom_count":
        return pose_atoms
    if feature == "contact_sqrt_norm":
        return float(row.get("contact_sqrt_norm") or 0.0)
    if feature == "min_distance_a":
        return float(row.get("min_distance_a") or 0.0)
    if feature == "log_contact_per_atom":
        return float(row.get("log_contact_per_atom") or math.log1p(max(contact, 0.0)))
    if feature == "contact_per_atom_sq":
        return contact * contact
    if feature == "pose_atom_count_sq":
        return pose_atoms * pose_atoms
    if feature == "contact_x_pose_atom_count":
        return contact * pose_atoms
    if feature == "contact_per_atom_over_pose_atom_count":
        return contact / max(pose_atoms, 1e-9)
    if feature == "baseline_x_contact_per_atom":
        return baseline * contact
    if feature == "baseline_x_pose_atom_count":
        return baseline * pose_atoms
    return 0.0


def _target_folds(rows: list[dict[str, Any]]) -> list[tuple[str, list[int], list[int]]]:
    targets = sorted({_text(row.get("target_id")) for row in rows if _text(row.get("target_id"))})
    folds: list[tuple[str, list[int], list[int]]] = []
    for target in targets:
        test_indexes = [index for index, row in enumerate(rows) if row.get("target_id") == target]
        train_indexes = [index for index in range(len(rows)) if index not in set(test_indexes)]
        if train_indexes and test_indexes:
            folds.append((target, train_indexes, test_indexes))
    return folds


def _feature_matrix(rows: list[dict[str, Any]], features: tuple[str, ...]) -> np.ndarray:
    return np.asarray(
        [[_feature_value(row, feature) for feature in features] for row in rows],
        dtype=np.float64,
    )


def _cross_validated_scores(
    rows: list[dict[str, Any]],
    *,
    features: tuple[str, ...],
    ridge_lambda: float,
) -> list[float]:
    scores: list[float | None] = [None] * len(rows)
    x_raw = _feature_matrix(rows, features)
    for _target, train_indexes, test_indexes in _target_folds(rows):
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
        for index, prediction in zip(test_indexes, design[test_indexes] @ coefficients):
            scores[index] = float(prediction)
    if any(score is None for score in scores):
        raise ValueError("cross-validation failed to score every row")
    return [float(score) for score in scores if score is not None]


def _model_sort_key(row: dict[str, Any]) -> tuple[float, float, float, str]:
    p05 = _float(row.get("free_energy_spearman_bootstrap_p05"))
    holdout = _float(row.get("holdout_spearman"))
    combined = _float(row.get("combined_spearman"))
    return (
        float("-inf") if p05 is None else p05,
        float("-inf") if holdout is None else holdout,
        float("-inf") if combined is None else combined,
        _text(row.get("model_id")),
    )


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _build_model_row(
    *,
    rows: list[dict[str, Any]],
    family: str,
    features: tuple[str, ...],
    ridge_lambda: float,
    locked_cv_p05: float | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scores = _cross_validated_scores(rows, features=features, ridge_lambda=ridge_lambda)
    metrics = _evaluate_scores(rows, scores)
    p05 = _float(metrics.get("free_energy_spearman_bootstrap_p05"))
    residual_rows = _rank_residual_rows(rows, scores)
    top_residual = residual_rows[0] if residual_rows else {}
    delta = None if locked_cv_p05 is None or p05 is None else p05 - locked_cv_p05
    return (
        {
            "model_id": f"{family}_ridge_l{ridge_lambda:g}",
            "model_family": family,
            "feature_names": ";".join(features),
            "feature_count": len(features),
            "ridge_lambda": _format_float(float(ridge_lambda)),
            **metrics,
            "bootstrap_p05_delta_from_locked_cv": delta,
            "material_p05_delta_from_locked_cv": bool(delta is not None and delta >= MATERIAL_P05_DELTA_THRESHOLD),
            "claim_grade_p05_ready": bool(p05 is not None and p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW),
            "top_rank_residual_target_id": top_residual.get("target_id", ""),
            "top_rank_residual_pose_id": top_residual.get("pose_id", ""),
            "top_rank_residual_split": top_residual.get("split", ""),
            "top_rank_residual_abs_error": _int(top_residual.get("rank_abs_error")),
            "diagnostic_only": True,
        },
        residual_rows,
    )


def build_refine_tier_public_benchmark_cv_model_extension_probe(
    *,
    candidate_fill_json: str | Path = DEFAULT_CANDIDATE_FILL_JSON,
    existing_materialization_csv: str | Path = DEFAULT_EXISTING_MATERIALIZATION_CSV,
    cross_validation_json: str | Path = DEFAULT_CROSS_VALIDATION_JSON,
    feature_extrapolation_json: str | Path = DEFAULT_FEATURE_EXTRAPOLATION_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    candidate_payload, candidate_present = _read_json(candidate_fill_json, root=root_path)
    cv_payload, cv_present = _read_json(cross_validation_json, root=root_path)
    feature_payload, feature_present = _read_json(feature_extrapolation_json, root=root_path)
    cv_summary = cv_payload.get("summary") if isinstance(cv_payload.get("summary"), dict) else {}
    feature_summary = feature_payload.get("summary") if isinstance(feature_payload.get("summary"), dict) else {}
    existing_rows = _existing_feature_rows(existing_materialization_csv, root=root_path)
    candidate_rows = _candidate_feature_rows(candidate_payload)
    rows = [*existing_rows, *candidate_rows]
    locked_cv_p05 = _float(cv_summary.get("locked_cv_bootstrap_p05"))
    locked_holdout = _float(cv_summary.get("locked_cv_holdout_spearman"))
    locked_combined = _float(cv_summary.get("locked_cv_combined_spearman"))

    model_rows: list[dict[str, Any]] = []
    residuals_by_model: dict[str, list[dict[str, Any]]] = {}
    if rows:
        for family, features, lambdas in MODEL_EXTENSION_SPECS:
            for ridge_lambda in lambdas:
                model_row, residual_rows = _build_model_row(
                    rows=rows,
                    family=family,
                    features=features,
                    ridge_lambda=ridge_lambda,
                    locked_cv_p05=locked_cv_p05,
                )
                model_rows.append(model_row)
                residuals_by_model[str(model_row["model_id"])] = residual_rows

    sorted_models = sorted(model_rows, key=_model_sort_key, reverse=True)
    best = sorted_models[0] if sorted_models else {}
    best_id = _text(best.get("model_id"))
    best_p05 = _float(best.get("free_energy_spearman_bootstrap_p05"))
    best_delta = _float(best.get("bootstrap_p05_delta_from_locked_cv"))
    material_rows = [row for row in sorted_models if bool(row.get("material_p05_delta_from_locked_cv"))]
    claim_grade_rows = [row for row in sorted_models if bool(row.get("claim_grade_p05_ready"))]
    top_residual_rows = residuals_by_model.get(best_id, [])[:25]
    top_residual = top_residual_rows[0] if top_residual_rows else {}
    summary = {
        "packet_type": "refine_tier_public_benchmark_cv_model_extension_probe",
        "status": (
            "refine_tier_public_benchmark_cv_model_extension_probe_ready"
            if candidate_present and cv_present and rows and sorted_models
            else "blocked_refine_tier_public_benchmark_cv_model_extension_probe"
        ),
        "candidate_fill_json": _display(candidate_fill_json, root=root_path),
        "candidate_fill_present": candidate_present,
        "existing_materialization_csv": _display(existing_materialization_csv, root=root_path),
        "cross_validation_json": _display(cross_validation_json, root=root_path),
        "cross_validation_present": cv_present,
        "feature_extrapolation_json": _display(feature_extrapolation_json, root=root_path),
        "feature_extrapolation_present": feature_present,
        "locked_cv_model_id": cv_summary.get("locked_cv_model_id", ""),
        "locked_cv_bootstrap_p05": locked_cv_p05,
        "locked_cv_holdout_spearman": locked_holdout,
        "locked_cv_combined_spearman": locked_combined,
        "locked_cv_bootstrap_p05_gap_to_claim_grade": (
            None if locked_cv_p05 is None else MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW - locked_cv_p05
        ),
        "combined_pair_count": len(rows),
        "existing_pair_count": len(existing_rows),
        "candidate_pair_count": len(candidate_rows),
        "bootstrap_iteration_count": BOOTSTRAP_ITERATIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "extension_model_candidate_count": len(sorted_models),
        "material_p05_delta_threshold": MATERIAL_P05_DELTA_THRESHOLD,
        "material_extension_improvement_count": len(material_rows),
        "claim_grade_extension_model_count": len(claim_grade_rows),
        "feature_extrapolation_high_error_count": feature_summary.get("high_error_feature_extrapolation_count"),
        "in_distribution_high_error_count": feature_summary.get("high_error_in_distribution_count"),
        "best_extension_model_id": best_id,
        "best_extension_feature_names": best.get("feature_names", ""),
        "best_extension_bootstrap_p05": best_p05,
        "best_extension_bootstrap_p05_delta_from_locked_cv": best_delta,
        "best_extension_bootstrap_p05_gap_to_claim_grade": (
            None if best_p05 is None else MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW - best_p05
        ),
        "best_extension_holdout_spearman": best.get("holdout_spearman"),
        "best_extension_combined_spearman": best.get("combined_spearman"),
        "best_extension_material_p05_delta_ready": bool(best.get("material_p05_delta_from_locked_cv")),
        "best_extension_claim_grade_p05_ready": bool(best.get("claim_grade_p05_ready")),
        "best_extension_top_residual_target_id": top_residual.get("target_id", ""),
        "best_extension_top_residual_pose_id": top_residual.get("pose_id", ""),
        "best_extension_top_residual_abs_error": _int(top_residual.get("rank_abs_error")),
        "model_extension_generalization_ready": bool(
            best.get("claim_grade_p05_ready") and best.get("material_p05_delta_from_locked_cv")
        ),
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Do not promote nonlinear/interaction extensions unless an extension clears claim-grade p05 and "
            "materially improves locked CV. Current failures should continue through reviewed metric payload, "
            "pose assignment, descriptor coverage, and independent holdout evidence before another calibration gate."
        ),
    }
    return {"summary": summary, "extension_model_rows": sorted_models, "best_extension_rank_residual_rows": top_residual_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 CV Model-Extension Probe",
        "",
        f"- status: `{s['status']}`",
        f"- locked_cv_model_id: `{s['locked_cv_model_id']}`",
        f"- locked_cv_bootstrap_p05: `{s['locked_cv_bootstrap_p05']}`",
        f"- locked_cv_bootstrap_p05_gap_to_claim_grade: `{s['locked_cv_bootstrap_p05_gap_to_claim_grade']}`",
        f"- extension_model_candidate_count: `{s['extension_model_candidate_count']}`",
        f"- material_extension_improvement_count: `{s['material_extension_improvement_count']}`",
        f"- claim_grade_extension_model_count: `{s['claim_grade_extension_model_count']}`",
        f"- best_extension_model_id: `{s['best_extension_model_id']}`",
        f"- best_extension_features: `{s['best_extension_feature_names']}`",
        f"- best_extension_bootstrap_p05: `{s['best_extension_bootstrap_p05']}`",
        f"- best_extension_bootstrap_p05_delta_from_locked_cv: `{s['best_extension_bootstrap_p05_delta_from_locked_cv']}`",
        f"- best_extension_bootstrap_p05_gap_to_claim_grade: `{s['best_extension_bootstrap_p05_gap_to_claim_grade']}`",
        f"- best_extension_material_p05_delta_ready: `{s['best_extension_material_p05_delta_ready']}`",
        f"- best_extension_claim_grade_p05_ready: `{s['best_extension_claim_grade_p05_ready']}`",
        f"- model_extension_generalization_ready: `{s['model_extension_generalization_ready']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Top Extension Models",
        "",
        "| model | features | lambda | holdout | combined | p05 | delta vs locked | material delta | claim-grade p05 | top residual |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["extension_model_rows"][:12]:
        lines.append(
            f"| `{row['model_id']}` | `{row['feature_names']}` | `{row['ridge_lambda']}` | "
            f"`{_format_float(_float(row.get('holdout_spearman')))}` | "
            f"`{_format_float(_float(row.get('combined_spearman')))}` | "
            f"`{_format_float(_float(row.get('free_energy_spearman_bootstrap_p05')))}` | "
            f"`{_format_float(_float(row.get('bootstrap_p05_delta_from_locked_cv')))}` | "
            f"`{row['material_p05_delta_from_locked_cv']}` | `{row['claim_grade_p05_ready']}` | "
            f"`{row['top_rank_residual_target_id']}/{row['top_rank_residual_abs_error']}` |"
        )
    lines.extend(
        [
            "",
            "## Best Extension Residuals",
            "",
            "| target | pose | source | split | variant rank | reference rank | rank abs error |",
            "| --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in payload["best_extension_rank_residual_rows"][:12]:
        lines.append(
            f"| `{row['target_id']}` | `{row['pose_id']}` | `{row['source']}` | `{row['split']}` | "
            f"`{row['variant_rank']}` | `{row['reference_rank']}` | `{row['rank_abs_error']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 CV model-extension probe.")
    parser.add_argument("--candidate-fill-json", default=DEFAULT_CANDIDATE_FILL_JSON)
    parser.add_argument("--existing-materialization-csv", default=DEFAULT_EXISTING_MATERIALIZATION_CSV)
    parser.add_argument("--cross-validation-json", default=DEFAULT_CROSS_VALIDATION_JSON)
    parser.add_argument("--feature-extrapolation-json", default=DEFAULT_FEATURE_EXTRAPOLATION_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_cv_model_extension_probe(
        candidate_fill_json=args.candidate_fill_json,
        existing_materialization_csv=args.existing_materialization_csv,
        cross_validation_json=args.cross_validation_json,
        feature_extrapolation_json=args.feature_extrapolation_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["extension_model_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
