#!/usr/bin/env python3
"""Read-only R9 fit-trained calibration probe for public-benchmark scoring."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

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
    _rank_residual_rows,
    _read_json,
    _resolve,
)
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
    _bootstrap_spearman_interval,
    _spearman_values,
)

DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_fit_trained_calibration_probe_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_fit_trained_calibration_probe_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_fit_trained_calibration_probe_current.md"

CLAIM_BOUNDARY = (
    "R9 fit-trained calibration probe only; it trains predeclared linear/ridge scoring hypotheses on "
    "the current fit split and reports holdout/public-benchmark diagnostics. It does not rewrite "
    "candidate-fill values, write reviewed metric payloads, approve operator receipts, promote canonical "
    "intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or "
    "mutate external state."
)

MODEL_SPECS: tuple[tuple[str, tuple[str, ...], tuple[float, ...]], ...] = (
    ("density_size", ("contact_per_atom", "pose_atom_count"), (0.1, 1.0, 10.0)),
    (
        "descriptor_only",
        ("contact_per_atom", "contact_sqrt_norm", "pose_atom_count", "min_distance_a"),
        (0.1, 1.0, 10.0),
    ),
    ("baseline_density_size", ("baseline_proxy", "contact_per_atom", "pose_atom_count"), (0.1, 1.0, 10.0)),
    (
        "baseline_density_sqrt_size",
        ("baseline_proxy", "contact_per_atom", "contact_sqrt_norm", "pose_atom_count"),
        (0.1, 1.0, 10.0),
    ),
    (
        "baseline_contact_min_distance",
        ("baseline_proxy", "contact_per_atom", "contact_sqrt_norm", "min_distance_a"),
        (0.1, 1.0, 10.0),
    ),
)


def _feature_value(row: dict[str, Any], feature: str) -> float:
    value = _float(row.get(feature))
    return 0.0 if value is None else float(value)


def _feature_matrix(rows: list[dict[str, Any]], features: tuple[str, ...]) -> np.ndarray:
    return np.asarray(
        [[_feature_value(row, feature) for feature in features] for row in rows],
        dtype=np.float64,
    )


def _safe_std(values: np.ndarray) -> np.ndarray:
    std = np.std(values, axis=0)
    std[~np.isfinite(std)] = 1.0
    std[std < 1e-12] = 1.0
    return std


def _split_spearman(rows: list[dict[str, Any]], scores: list[float], split: str) -> float | None:
    indexes = [index for index, row in enumerate(rows) if row.get("split") == split]
    if len(indexes) < 2:
        return None
    return _spearman_values(
        [float(scores[index]) for index in indexes],
        [float(rows[index]["reference"]) for index in indexes],
    )


def _evaluate_scores(rows: list[dict[str, Any]], scores: list[float]) -> dict[str, Any]:
    pairs = [
        {"proxy": float(score), "reference": float(row["reference"])}
        for row, score in zip(rows, scores)
        if math.isfinite(float(score))
    ]
    return {
        "fit_spearman": _split_spearman(rows, scores, "fit"),
        "holdout_spearman": _split_spearman(rows, scores, "holdout"),
        "combined_spearman": _spearman_values(scores, [float(row["reference"]) for row in rows]),
        **_bootstrap_spearman_interval(pairs),
    }


def _fit_model(
    rows: list[dict[str, Any]],
    *,
    features: tuple[str, ...],
    ridge_lambda: float,
) -> tuple[list[float], dict[str, float], dict[str, float]]:
    fit_indexes = [index for index, row in enumerate(rows) if row.get("split") == "fit"]
    x_raw = _feature_matrix(rows, features)
    x_fit = x_raw[fit_indexes]
    mean = np.mean(x_fit, axis=0)
    std = _safe_std(x_fit)
    x_scaled = (x_raw - mean) / std
    design = np.column_stack([np.ones(len(rows), dtype=np.float64), x_scaled])
    design_fit = design[fit_indexes]
    y_fit = np.asarray([float(rows[index]["reference"]) for index in fit_indexes], dtype=np.float64)
    penalty = np.eye(design_fit.shape[1], dtype=np.float64) * float(ridge_lambda)
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(design_fit.T @ design_fit + penalty, design_fit.T @ y_fit)
    scores = [float(value) for value in design @ coefficients]
    coef_map = {"intercept": float(coefficients[0])}
    coef_map.update({feature: float(coefficients[index + 1]) for index, feature in enumerate(features)})
    scale_map = {f"{feature}_mean": float(mean[index]) for index, feature in enumerate(features)}
    scale_map.update({f"{feature}_std": float(std[index]) for index, feature in enumerate(features)})
    return scores, coef_map, scale_map


def _format_map(payload: dict[str, float]) -> str:
    return ";".join(f"{key}={_format_float(value)}" for key, value in payload.items())


def _model_sort_key(row: dict[str, Any]) -> tuple[float, float, float, float, str]:
    p05 = _float(row.get("free_energy_spearman_bootstrap_p05"))
    holdout = _float(row.get("holdout_spearman"))
    combined = _float(row.get("combined_spearman"))
    fit = _float(row.get("fit_spearman"))
    return (
        float("-inf") if p05 is None else p05,
        float("-inf") if holdout is None else holdout,
        float("-inf") if combined is None else combined,
        float("-inf") if fit is None else fit,
        str(row.get("model_id") or ""),
    )


def _feature_count(rows: list[dict[str, Any]], key: str, value: Any = True) -> int:
    return sum(1 for row in rows if row.get(key) == value)


def build_refine_tier_public_benchmark_fit_trained_calibration_probe(
    *,
    candidate_fill_json: str | Path = DEFAULT_CANDIDATE_FILL_JSON,
    existing_materialization_csv: str | Path = DEFAULT_EXISTING_MATERIALIZATION_CSV,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    candidate_payload, candidate_present = _read_json(candidate_fill_json, root=root_path)
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
    fit_rows = [row for row in rows if row.get("split") == "fit"]
    if len(fit_rows) >= 2:
        for family, features, lambdas in MODEL_SPECS:
            for ridge_lambda in lambdas:
                model_id = f"{family}_ridge_l{ridge_lambda:g}"
                scores, coefficients, scales = _fit_model(rows, features=features, ridge_lambda=ridge_lambda)
                metrics = _evaluate_scores(rows, scores)
                p05 = _float(metrics.get("free_energy_spearman_bootstrap_p05"))
                holdout = _float(metrics.get("holdout_spearman"))
                combined = _float(metrics.get("combined_spearman"))
                row = {
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
                    "coefficients": _format_map(coefficients),
                    "fit_standardization": _format_map(scales),
                    "diagnostic_only": True,
                }
                residual_rows = _rank_residual_rows(rows, scores)
                top_residual = residual_rows[0] if residual_rows else {}
                row.update(
                    {
                        "top_rank_residual_target_id": top_residual.get("target_id", ""),
                        "top_rank_residual_pose_id": top_residual.get("pose_id", ""),
                        "top_rank_residual_split": top_residual.get("split", ""),
                        "top_rank_residual_abs_error": int(top_residual.get("rank_abs_error") or 0),
                    }
                )
                model_rows.append(row)
                residual_by_model[model_id] = residual_rows

    sorted_models = sorted(model_rows, key=_model_sort_key, reverse=True)
    eligible_models = [row for row in sorted_models if bool(row.get("holdout_guarded_eligible"))]
    best = eligible_models[0] if eligible_models else (sorted_models[0] if sorted_models else {})
    best_id = str(best.get("model_id") or "")
    best_p05 = _float(best.get("free_energy_spearman_bootstrap_p05"))
    p05_gap = (
        None
        if best_p05 is None
        else MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW - best_p05
    )
    summary = {
        "packet_type": "refine_tier_public_benchmark_fit_trained_calibration_probe",
        "status": (
            "refine_tier_public_benchmark_fit_trained_calibration_probe_ready"
            if candidate_present and rows and model_rows
            else "blocked_refine_tier_public_benchmark_fit_trained_calibration_probe"
        ),
        "candidate_fill_json": _display(candidate_fill_json, root=root_path),
        "candidate_fill_present": candidate_present,
        "existing_materialization_csv": _display(existing_materialization_csv, root=root_path),
        "existing_pair_count": len(existing_rows),
        "candidate_pair_count": len(candidate_rows),
        "combined_pair_count": len(rows),
        "fit_pair_count": sum(1 for row in rows if row.get("split") == "fit"),
        "holdout_pair_count": sum(1 for row in rows if row.get("split") == "holdout"),
        "feature_complete_pair_count": _feature_count(rows, "feature_complete"),
        "candidate_detail_from_rows_pair_count": _feature_count(
            candidate_rows, "detail_source", "candidate_rows_internal_deltaG"
        ),
        "model_candidate_count": len(model_rows),
        "holdout_guarded_eligible_model_count": len(eligible_models),
        "bootstrap_iteration_count": BOOTSTRAP_ITERATIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "min_claim_grade_bootstrap_spearman_low_required": MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
        "baseline_fit_spearman": baseline_eval.get("fit_spearman"),
        "baseline_holdout_spearman": baseline_eval.get("holdout_spearman"),
        "baseline_combined_spearman": baseline_eval.get("combined_spearman"),
        "baseline_bootstrap_p05": baseline_p05,
        "best_model_id": best_id,
        "best_model_family": best.get("model_family", ""),
        "best_model_feature_names": best.get("feature_names", ""),
        "best_model_ridge_lambda": best.get("ridge_lambda", ""),
        "best_model_fit_spearman": best.get("fit_spearman"),
        "best_model_holdout_spearman": best.get("holdout_spearman"),
        "best_model_combined_spearman": best.get("combined_spearman"),
        "best_model_bootstrap_p05": best_p05,
        "best_model_bootstrap_p05_delta": best.get("bootstrap_p05_delta_from_baseline"),
        "best_model_bootstrap_p05_gap_to_claim_grade": p05_gap,
        "best_model_holdout_guarded_eligible": bool(best.get("holdout_guarded_eligible")),
        "best_model_claim_grade_p05_ready": bool(best.get("claim_grade_p05_ready")),
        "calibration_generalization_ready": bool(
            best.get("holdout_guarded_eligible") and best.get("claim_grade_p05_ready")
        ),
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "selection_policy": (
            "select highest bootstrap p05 among fit-trained models that do not degrade holdout or combined "
            "Spearman versus baseline; still requires independent/operator-reviewed R9 payload validation"
        ),
        "next_required_step": (
            "Treat the best fit-trained model as a near-threshold descriptor hypothesis only. Verify it on "
            "operator-reviewed metric-source payloads or an independent R9 holdout, then reduce remaining top "
            "rank residuals before any score mutation, payload write, canonical intake, or claim promotion."
        ),
    }
    return {
        "summary": summary,
        "model_rows": sorted_models,
        "best_model_rank_residual_rows": residual_by_model.get(best_id, [])[:25],
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
        "# R9 Fit-Trained Calibration Probe",
        "",
        f"- status: `{s['status']}`",
        f"- combined_pair_count: `{s['combined_pair_count']}`",
        f"- fit_pair_count: `{s['fit_pair_count']}`",
        f"- holdout_pair_count: `{s['holdout_pair_count']}`",
        f"- feature_complete_pair_count: `{s['feature_complete_pair_count']}`",
        f"- baseline_fit/holdout/combined: `{s['baseline_fit_spearman']}/"
        f"{s['baseline_holdout_spearman']}/{s['baseline_combined_spearman']}`",
        f"- baseline_bootstrap_p05: `{s['baseline_bootstrap_p05']}`",
        f"- best_model_id: `{s['best_model_id']}`",
        f"- best_model_features: `{s['best_model_feature_names']}`",
        f"- best_model_fit/holdout/combined: `{s['best_model_fit_spearman']}/"
        f"{s['best_model_holdout_spearman']}/{s['best_model_combined_spearman']}`",
        f"- best_model_bootstrap_p05: `{s['best_model_bootstrap_p05']}`",
        f"- best_model_bootstrap_p05_gap_to_claim_grade: `{s['best_model_bootstrap_p05_gap_to_claim_grade']}`",
        f"- best_model_claim_grade_p05_ready: `{s['best_model_claim_grade_p05_ready']}`",
        f"- calibration_generalization_ready: `{s['calibration_generalization_ready']}`",
        "",
        "## Top Fit-Trained Models",
        "",
        "| model | features | lambda | fit | holdout | combined | p05 | p05 delta | holdout guarded | claim-grade p05 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["model_rows"][:12]:
        lines.append(
            f"| `{row['model_id']}` | `{row['feature_names']}` | `{row['ridge_lambda']}` | "
            f"`{_format_float(_float(row.get('fit_spearman')))}` | "
            f"`{_format_float(_float(row.get('holdout_spearman')))}` | "
            f"`{_format_float(_float(row.get('combined_spearman')))}` | "
            f"`{_format_float(_float(row.get('free_energy_spearman_bootstrap_p05')))}` | "
            f"`{_format_float(_float(row.get('bootstrap_p05_delta_from_baseline')))}` | "
            f"`{row['holdout_guarded_eligible']}` | `{row['claim_grade_p05_ready']}` |"
        )
    lines.extend(
        [
            "",
            "## Best Model Residuals",
            "",
            "| target | pose | source | split | variant rank | reference rank | rank abs error |",
            "| --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in payload["best_model_rank_residual_rows"][:10]:
        lines.append(
            f"| `{row['target_id']}` | `{row['pose_id']}` | `{row['source']}` | `{row['split']}` | "
            f"`{row['variant_rank']}` | `{row['reference_rank']}` | `{row['rank_abs_error']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 fit-trained calibration probe.")
    parser.add_argument("--candidate-fill-json", default=DEFAULT_CANDIDATE_FILL_JSON)
    parser.add_argument("--existing-materialization-csv", default=DEFAULT_EXISTING_MATERIALIZATION_CSV)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_fit_trained_calibration_probe(
        candidate_fill_json=args.candidate_fill_json,
        existing_materialization_csv=args.existing_materialization_csv,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["model_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
