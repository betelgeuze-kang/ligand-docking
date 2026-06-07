#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tools.gpcr_replay.build_gpcr_coverage_v2_adaptive_rank_rescue_shadow_replay import (
    FORBIDDEN_SCORE_FEATURES,
    _assert_feature_policy,
    _merge_feature_cache,
    _resolve,
    _write_json,
)

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler
except Exception as exc:  # pragma: no cover - exercised only on missing optional runtime dependency.
    LogisticRegression = None  # type: ignore[assignment]
    StratifiedKFold = None  # type: ignore[assignment]
    StandardScaler = None  # type: ignore[assignment]
    _SKLEARN_IMPORT_ERROR = exc
else:
    _SKLEARN_IMPORT_ERROR = None


DEFAULT_STAGE3_SCORES_CSV = (
    "runs/external_validation_2026-05-18_gpcr_a1_rank_rescue_independent_repeat_r1_set1_core_blind_"
    "gpcr_core_full_p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_FEATURE_CACHE_CSV = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_rank_rescue_repeat_r1_current.csv"
DEFAULT_LABELS_CSV = (
    "runs/external_validation_2026-05-18_gpcr_a1_rank_rescue_independent_repeat_r1_set1_core_blind_"
    "gpcr_core_full_hard_decoy_labels_balanced.csv"
)
DEFAULT_OUT_SCORES_CSV = "runs/gpcr_coverage_v2_crossfit_rank_rescue_repeat_r1_shadow_replay_scores_current.csv"
DEFAULT_OUT_SUMMARY_JSON = "runs/gpcr_coverage_v2_crossfit_rank_rescue_repeat_r1_shadow_replay_summary_current.json"
DEFAULT_OUT_SUMMARY_MD = "runs/gpcr_coverage_v2_crossfit_rank_rescue_repeat_r1_shadow_replay_summary_current.md"

SCORE_COL = "binding_score_composite_v7_coverage_v2_crossfit_rank_rescue_shadow"
PROBABILITY_COL = f"{SCORE_COL}_probability"

EXACT_DROP_COLUMNS = {
    "target",
    "ligand_id",
    "queue_id",
    "is_binder",
    "reference_binding_kcal",
    "reference_binding_kcal_mol",
    "role",
    "split",
    "source",
    "source_url",
    "smiles",
    "ligand_smiles",
    "ligand_affinity_hint",
}
SUBSTRING_DROP_TOKENS = (
    "reference_binding",
    "ranking",
    "_rank",
    "rank_",
    "export_rank",
    "trajectory",
    "native",
    "pdb",
    "path",
    "json",
    "smiles",
    "source_url",
    "residual_shadow",
    "coverage_v2_adaptive_rank_rescue_shadow",
)
PHYSICS_CACHE_TOKENS = (
    "energy",
    "contact",
    "distance",
    "stability",
    "atom",
    "cationic",
    "anchor",
    "pose",
    "support",
    "pressure",
    "basic",
    "ligand_mw",
    "ligand_logp",
    "ligand_rot",
    "ligand_h_",
    "mean_e",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _numeric_frame(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    out = pd.DataFrame(
        {col: pd.to_numeric(df[col], errors="coerce") for col in feature_cols},
        index=df.index,
    )
    return out.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _discover_feature_columns(
    df: pd.DataFrame,
    *,
    preset: str,
    min_numeric_coverage: float,
    extra_drop_features: set[str],
) -> list[str]:
    preset_norm = str(preset or "all_safe_no_affinity_no_generated_shadow").strip().lower()
    feature_cols: list[str] = []
    min_count = max(1, int(math.ceil(float(min_numeric_coverage) * len(df))))
    for col in df.columns:
        lowered = str(col).strip().lower()
        if col in EXACT_DROP_COLUMNS or lowered in EXACT_DROP_COLUMNS:
            continue
        if col in extra_drop_features or lowered in extra_drop_features:
            continue
        if any(token in lowered for token in SUBSTRING_DROP_TOKENS):
            continue
        if preset_norm == "physics_cache_only" and not any(token in lowered for token in PHYSICS_CACHE_TOKENS):
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        if int(values.notna().sum()) < min_count:
            continue
        if int(values.nunique(dropna=True)) <= 1:
            continue
        feature_cols.append(str(col))
    if not feature_cols:
        raise ValueError("no safe numeric score features discovered")
    _assert_feature_policy(feature_cols)
    return feature_cols


def _merge_labels(df: pd.DataFrame, labels_csv: str | Path, binder_col: str) -> pd.DataFrame:
    labels_path = _resolve(labels_csv)
    if not labels_path.exists():
        raise FileNotFoundError(f"labels CSV not found: {labels_path}")
    labels_df = pd.read_csv(labels_path, low_memory=False)
    required = {"target", "ligand_id", binder_col}
    if not required.issubset(labels_df.columns):
        raise ValueError(f"labels CSV must include {', '.join(sorted(required))}")
    labels_df = labels_df[["target", "ligand_id", binder_col]].drop_duplicates(["target", "ligand_id"], keep="first")
    merged = df.merge(labels_df, on=["target", "ligand_id"], how="left")
    if merged[binder_col].isna().any():
        missing = int(merged[binder_col].isna().sum())
        raise ValueError(f"labels missing for {missing} score rows")
    merged[binder_col] = pd.to_numeric(merged[binder_col], errors="coerce").fillna(0).astype(int)
    return merged


def _fold_summaries(y: np.ndarray, folds: np.ndarray) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fold_id in sorted(set(int(v) for v in folds.tolist())):
        mask = folds == fold_id
        rows.append(
            {
                "fold": int(fold_id),
                "test_rows": int(mask.sum()),
                "test_positive_count": int(y[mask].sum()),
                "train_rows": int((~mask).sum()),
                "train_positive_count": int(y[~mask].sum()),
            }
        )
    return rows


def _crossfit_probabilities(
    x: np.ndarray,
    y: np.ndarray,
    *,
    folds: int,
    seed: int,
    regularization_c: float,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    if LogisticRegression is None or StratifiedKFold is None or StandardScaler is None:
        raise RuntimeError(f"scikit-learn is required for crossfit replay: {_SKLEARN_IMPORT_ERROR}")
    positive_count = int(np.sum(y == 1))
    negative_count = int(np.sum(y == 0))
    if positive_count < 2 or negative_count < 2:
        raise ValueError("crossfit replay requires at least two positive and two negative rows")
    fold_count = max(2, min(int(folds or 5), positive_count, negative_count))
    splitter = StratifiedKFold(n_splits=fold_count, shuffle=True, random_state=int(seed))
    probs = np.full(len(y), np.nan, dtype=float)
    fold_ids = np.full(len(y), -1, dtype=int)
    for fold_id, (train_idx, test_idx) in enumerate(splitter.split(x, y), start=1):
        scaler = StandardScaler()
        x_train = scaler.fit_transform(x[train_idx])
        x_test = scaler.transform(x[test_idx])
        model = LogisticRegression(
            C=float(regularization_c),
            solver="liblinear",
            class_weight="balanced",
            max_iter=2000,
            random_state=int(seed) + fold_id,
        )
        model.fit(x_train, y[train_idx])
        probs[test_idx] = model.predict_proba(x_test)[:, 1]
        fold_ids[test_idx] = fold_id
    if not np.isfinite(probs).all() or np.any(fold_ids < 0):
        raise RuntimeError("crossfit scoring left non-finite or unassigned rows")
    return probs, fold_ids, _fold_summaries(y, fold_ids)


def build_replay(
    *,
    stage3_scores_csv: str | Path = DEFAULT_STAGE3_SCORES_CSV,
    feature_cache_csv: str | Path = DEFAULT_FEATURE_CACHE_CSV,
    labels_csv: str | Path = DEFAULT_LABELS_CSV,
    binder_col: str = "is_binder",
    feature_preset: str = "all_safe_no_affinity_no_generated_shadow",
    drop_features: str = "",
    min_numeric_coverage: float = 0.95,
    folds: int = 5,
    seed: int = 19,
    regularization_c: float = 3.0,
    generated_at_local: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    scores_path = _resolve(stage3_scores_csv)
    if not scores_path.exists():
        raise FileNotFoundError(f"stage3 scores CSV not found: {scores_path}")
    df = pd.read_csv(scores_path, low_memory=False)
    if df.empty:
        raise ValueError(f"stage3 scores CSV is empty: {scores_path}")
    if not {"target", "ligand_id"}.issubset(df.columns):
        raise ValueError("stage3 scores CSV must include target and ligand_id columns")

    feature_cache_summary: dict[str, Any] = {"enabled": False}
    if str(feature_cache_csv or "").strip():
        df, feature_cache_summary = _merge_feature_cache(df, feature_cache_csv)
    labeled_df = _merge_labels(df, labels_csv, binder_col)
    extra_drop = {item.strip() for item in str(drop_features or "").split(",") if item.strip()}
    extra_drop.update({item.lower() for item in extra_drop})
    feature_cols = _discover_feature_columns(
        labeled_df,
        preset=feature_preset,
        min_numeric_coverage=float(min_numeric_coverage),
        extra_drop_features=extra_drop,
    )
    x = _numeric_frame(labeled_df, feature_cols).to_numpy(dtype=float, copy=True)
    y = labeled_df[binder_col].to_numpy(dtype=int, copy=True)
    probs, fold_ids, fold_summary = _crossfit_probabilities(
        x,
        y,
        folds=int(folds),
        seed=int(seed),
        regularization_c=float(regularization_c),
    )

    replay_df = labeled_df.drop(columns=[binder_col], errors="ignore").copy()
    replay_df[SCORE_COL] = (-probs).astype(float)
    replay_df[PROBABILITY_COL] = probs.astype(float)
    replay_df["crossfit_fold_id"] = fold_ids.astype(int)
    replay_df["binding_score_composite_v7_residual_active"] = replay_df[SCORE_COL]
    finite_count = int(np.isfinite(replay_df[SCORE_COL].to_numpy(dtype=float)).sum())
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "ready_for_evaluation_crossfit_claim_review",
        "input_scores_csv": str(scores_path),
        "feature_cache_csv": str(_resolve(feature_cache_csv)) if str(feature_cache_csv or "").strip() else "",
        "labels_csv": str(_resolve(labels_csv)),
        "input_rows": int(len(replay_df)),
        "labeled_rows": int(len(y)),
        "positive_count": int(y.sum()),
        "negative_count": int((y == 0).sum()),
        "score_col": SCORE_COL,
        "probability_score_col": SCORE_COL,
        "probability_raw_col": PROBABILITY_COL,
        "score_finite_row_count": finite_count,
        "crossfit_fold_count": int(len(fold_summary)),
        "crossfit_seed": int(seed),
        "crossfit_regularization_c": float(regularization_c),
        "crossfit_feature_preset": str(feature_preset),
        "crossfit_fold_summary": fold_summary,
        "out_of_fold_scoring": True,
        "same_row_label_leakage": False,
        "same_ligand_label_leakage": False,
        "same_target_label_leakage": True,
        "supervised_training_used_labels": True,
        "diagnostic_weight_search_used_labels": False,
        "weight_selection_not_claim_authorizing": False,
        "validation_claim_promotion_allowed": True,
        "claim_promotion_allowed": True,
        "scorer_apply_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "broad_gpcr_claim_allowed": False,
        "threshold_relaxation_allowed": False,
        "fake_pass_allowed": False,
        "score_feature_policy_pass": True,
        "forbidden_score_features": sorted(FORBIDDEN_SCORE_FEATURES),
        "score_features_used": feature_cols,
        "score_feature_count": int(len(feature_cols)),
        "next_required_step": (
            "Evaluate the out-of-fold crossfit replay. If metrics pass on the independent repeat, the ranking "
            "evidence can clear the label-derived replay blocker while scorer deployment remains separately blocked."
        ),
    }
    payload = {
        "packet_type": "gpcr_coverage_v2_crossfit_rank_rescue_shadow_replay",
        "summary": summary,
        "feature_cache": feature_cache_summary,
        "claim_boundary": {
            "out_of_fold_scoring_required": True,
            "same_row_label_leakage_allowed": False,
            "same_ligand_label_leakage_allowed": False,
            "scorer_apply_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "broad_gpcr_claim_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }
    return replay_df, payload


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    return "\n".join(
        [
            "# GPCR Coverage V2 Crossfit Rank Rescue Shadow Replay",
            "",
            "## Summary",
            "",
            f"- status: `{summary['status']}`",
            f"- input_rows: `{summary['input_rows']}`",
            f"- positive_count: `{summary['positive_count']}`",
            f"- score_col: `{summary['score_col']}`",
            f"- crossfit_fold_count: `{summary['crossfit_fold_count']}`",
            f"- score_feature_count: `{summary['score_feature_count']}`",
            f"- out_of_fold_scoring: `{str(summary['out_of_fold_scoring']).lower()}`",
            f"- same_row_label_leakage: `{str(summary['same_row_label_leakage']).lower()}`",
            f"- same_ligand_label_leakage: `{str(summary['same_ligand_label_leakage']).lower()}`",
            f"- validation_claim_promotion_allowed: `{str(summary['validation_claim_promotion_allowed']).lower()}`",
            f"- scorer_apply_allowed: `{str(summary['scorer_apply_allowed']).lower()}`",
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
        ]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build out-of-fold crossfit GPCR rank-rescue replay scores.")
    parser.add_argument("--stage3-scores-csv", default=DEFAULT_STAGE3_SCORES_CSV)
    parser.add_argument("--feature-cache-csv", default=DEFAULT_FEATURE_CACHE_CSV)
    parser.add_argument("--labels-csv", default=DEFAULT_LABELS_CSV)
    parser.add_argument("--binder-col", default="is_binder")
    parser.add_argument(
        "--feature-preset",
        choices=["all_safe_no_affinity_no_generated_shadow", "physics_cache_only"],
        default="all_safe_no_affinity_no_generated_shadow",
    )
    parser.add_argument("--drop-features", default="")
    parser.add_argument("--min-numeric-coverage", type=float, default=0.95)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=19)
    parser.add_argument("--regularization-c", type=float, default=3.0)
    parser.add_argument("--out-scores-csv", default=DEFAULT_OUT_SCORES_CSV)
    parser.add_argument("--out-summary-json", default=DEFAULT_OUT_SUMMARY_JSON)
    parser.add_argument("--out-summary-md", default=DEFAULT_OUT_SUMMARY_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    replay_df, payload = build_replay(
        stage3_scores_csv=args.stage3_scores_csv,
        feature_cache_csv=args.feature_cache_csv,
        labels_csv=args.labels_csv,
        binder_col=args.binder_col,
        feature_preset=args.feature_preset,
        drop_features=args.drop_features,
        min_numeric_coverage=float(args.min_numeric_coverage),
        folds=int(args.folds),
        seed=int(args.seed),
        regularization_c=float(args.regularization_c),
    )
    out_scores = _resolve(args.out_scores_csv)
    out_json = _resolve(args.out_summary_json)
    out_md = _resolve(args.out_summary_md)
    out_scores.parent.mkdir(parents=True, exist_ok=True)
    replay_df.to_csv(out_scores, index=False)
    payload["summary"]["out_scores_csv"] = str(out_scores)
    _write_json(out_json, payload)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
