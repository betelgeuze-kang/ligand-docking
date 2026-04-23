#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _default_md_path(out_json: str) -> str:
    if out_json.endswith(".json"):
        return out_json[:-5] + ".md"
    return out_json + ".md"


def _default_predictions_path(out_json: str) -> str:
    if out_json.endswith(".json"):
        return out_json[:-5] + "_predictions.csv"
    return out_json + "_predictions.csv"


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40.0, 40.0)))


def _average_precision(y_true: Sequence[int], y_score: Sequence[float]) -> Optional[float]:
    y = np.asarray(list(y_true), dtype=int)
    s = np.asarray(list(y_score), dtype=float)
    pos = int(y.sum())
    if pos <= 0:
        return None
    order = np.argsort(-s, kind="mergesort")
    y = y[order]
    tp = np.cumsum(y)
    k = np.arange(1, len(y) + 1)
    precision = tp / k
    return float((precision * y).sum() / pos)


def _parse_holdout_from_path(path: str) -> str:
    name = os.path.basename(path)
    match = re.search(r"_fold\d+_(.+?)_eval_corrected_targets\.csv$", name)
    if not match:
        raise ValueError(f"could not infer holdout target from csv path: {path}")
    return str(match.group(1))


def _load_rows(manifest_json: str) -> pd.DataFrame:
    manifest = _load_json(manifest_json)
    frames: List[pd.DataFrame] = []
    for idx, art in enumerate(manifest.get("fold_artifacts", []), start=1):
        csv_path = str(art.get("eval_corrected_csv", "")).strip()
        if not csv_path:
            continue
        fold_index = int(art.get("fold_index") or idx)
        holdout = str(art.get("holdout") or "").strip() or _parse_holdout_from_path(csv_path)
        df = pd.read_csv(csv_path)
        df["__fold_index"] = fold_index
        df["__holdout"] = holdout
        df["__source_csv"] = csv_path
        frames.append(df)
    if not frames:
        raise ValueError("no eval_corrected_csv entries found in manifest")
    rows = pd.concat(frames, ignore_index=True)
    if "true_aggregation_flag" not in rows.columns:
        raise ValueError("eval_corrected csv rows are missing true_aggregation_flag")
    return rows


def _fit_logistic_regression(
    X: np.ndarray,
    y: np.ndarray,
    *,
    l2: float,
    iters: int,
    lr: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    n, d = X.shape
    mu = X.mean(axis=0)
    sigma = X.std(axis=0)
    sigma[sigma < 1e-8] = 1.0
    Xs = (X - mu) / sigma
    w = np.zeros(d, dtype=float)
    p0 = min(max(float(y.mean()), 1e-4), 1.0 - 1e-4)
    b = float(math.log(p0 / (1.0 - p0)))
    mw = np.zeros(d, dtype=float)
    vw = np.zeros(d, dtype=float)
    mb = 0.0
    vb = 0.0
    beta1 = 0.9
    beta2 = 0.999
    eps = 1e-8
    for t in range(1, iters + 1):
        z = Xs @ w + b
        p = _sigmoid(z)
        err = p - y
        grad_w = (Xs.T @ err) / n + l2 * w
        grad_b = float(err.mean())
        mw = beta1 * mw + (1.0 - beta1) * grad_w
        vw = beta2 * vw + (1.0 - beta2) * (grad_w * grad_w)
        mb = beta1 * mb + (1.0 - beta1) * grad_b
        vb = beta2 * vb + (1.0 - beta2) * (grad_b * grad_b)
        mw_hat = mw / (1.0 - beta1**t)
        vw_hat = vw / (1.0 - beta2**t)
        mb_hat = mb / (1.0 - beta1**t)
        vb_hat = vb / (1.0 - beta2**t)
        w -= lr * mw_hat / (np.sqrt(vw_hat) + eps)
        b -= lr * mb_hat / (math.sqrt(vb_hat) + eps)
    return mu, sigma, w, b


def _predict(model: Tuple[np.ndarray, np.ndarray, np.ndarray, float], X: np.ndarray) -> np.ndarray:
    mu, sigma, w, b = model
    return _sigmoid(((X - mu) / sigma) @ w + b)


def _feature_table(rows: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    base_features = [
        "pred_aggregation_prob",
        "pred_llps_prob",
        "branch_weight_aggregation_prone",
        "branch_weight_llps_lcd",
        "branch_weight_helix_tad",
        "pred_state_prob_expanded_disordered",
        "pred_state_prob_compact_disordered",
        "pred_state_prob_helix_enriched",
        "pred_state_prob_sticky_condensed",
        "pred_rank_compactness",
        "pred_rank_helicity",
        "pred_rank_condensation",
    ]
    missing = [c for c in base_features if c not in rows.columns]
    if missing:
        raise ValueError(f"missing required feature columns: {', '.join(missing)}")
    X_base = rows[base_features].astype(float).to_numpy()
    bagg = rows["branch_weight_aggregation_prone"].astype(float).to_numpy()
    bllps = rows["branch_weight_llps_lcd"].astype(float).to_numpy()
    bhel = rows["branch_weight_helix_tad"].astype(float).to_numpy()
    pred_agg = rows["pred_aggregation_prob"].astype(float).to_numpy()
    rank_comp = rows["pred_rank_compactness"].astype(float).to_numpy()
    rank_hel = rows["pred_rank_helicity"].astype(float).to_numpy()
    rank_cond = rows["pred_rank_condensation"].astype(float).to_numpy()
    interactions = np.column_stack(
        [
            pred_agg * bagg,
            rank_comp * bagg,
            rank_cond * bagg,
            rank_comp * bllps,
            rank_cond * bllps,
            rank_hel * bhel,
        ]
    )
    interaction_names = [
        "pred_aggregation_prob_x_branch_weight_aggregation_prone",
        "pred_rank_compactness_x_branch_weight_aggregation_prone",
        "pred_rank_condensation_x_branch_weight_aggregation_prone",
        "pred_rank_compactness_x_branch_weight_llps_lcd",
        "pred_rank_condensation_x_branch_weight_llps_lcd",
        "pred_rank_helicity_x_branch_weight_helix_tad",
    ]
    return np.concatenate([X_base, interactions], axis=1), base_features + interaction_names


def _branch_ap(rows: pd.DataFrame, score_col: str) -> Dict[str, Optional[float]]:
    payload: Dict[str, Optional[float]] = {}
    for branch in ("aggregation_prone", "llps_lcd", "helix_tad"):
        subset = rows.loc[rows["branch_label"] == branch]
        payload[branch] = _average_precision(
            subset["true_aggregation_flag"].astype(int).tolist(),
            subset[score_col].astype(float).tolist(),
        )
    return payload


def _top_weights(
    names: Sequence[str],
    mu: np.ndarray,
    sigma: np.ndarray,
    w: np.ndarray,
    top_k: int,
) -> List[Dict[str, Any]]:
    order = np.argsort(-np.abs(w))[:top_k]
    items: List[Dict[str, Any]] = []
    for idx in order:
        items.append(
            {
                "feature": str(names[int(idx)]),
                "weight_standardized": float(w[int(idx)]),
                "mean_train": float(mu[int(idx)]),
                "std_train": float(sigma[int(idx)]),
            }
        )
    return items


def evaluate(args: argparse.Namespace) -> Dict[str, Any]:
    rows = _load_rows(str(args.manifest_json))
    rows = rows.loc[rows["true_aggregation_flag"].notna()].copy()
    rows["true_aggregation_flag"] = rows["true_aggregation_flag"].astype(int)
    X, feature_names = _feature_table(rows)
    y = rows["true_aggregation_flag"].to_numpy(dtype=int)
    folds = rows["__fold_index"].to_numpy(dtype=int)

    raw_score = rows["pred_aggregation_prob"].astype(float).to_numpy()
    oof_score = np.zeros(len(rows), dtype=float)

    unique_folds = sorted(int(x) for x in np.unique(folds))
    for fold in unique_folds:
        train_mask = folds != fold
        valid_mask = folds == fold
        model = _fit_logistic_regression(
            X[train_mask],
            y[train_mask],
            l2=float(args.l2),
            iters=int(args.iters),
            lr=float(args.lr),
        )
        oof_score[valid_mask] = _predict(model, X[valid_mask])

    rows["pred_aggregation_risk_global"] = oof_score

    raw_global_ap = _average_precision(y, raw_score)
    calibrated_global_ap = _average_precision(y, oof_score)
    raw_branch_ap = _branch_ap(rows, "pred_aggregation_prob")
    calibrated_branch_ap = _branch_ap(rows, "pred_aggregation_risk_global")

    final_model = _fit_logistic_regression(
        X,
        y,
        l2=float(args.l2),
        iters=int(args.iters),
        lr=float(args.lr),
    )
    final_mu, final_sigma, final_w, final_b = final_model

    manifest = _load_json(str(args.manifest_json))
    combined_metrics = dict(manifest.get("combined_gate_metrics", {}) or {})
    raw_branch_macro = np.nanmean([v for v in raw_branch_ap.values() if v is not None])
    calibrated_branch_macro = np.nanmean([v for v in calibrated_branch_ap.values() if v is not None])

    payload: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "manifest_json": str(args.manifest_json),
        },
        "dataset": {
            "row_count": int(len(rows)),
            "fold_count": int(len(unique_folds)),
            "positive_count": int(y.sum()),
            "negative_count": int(len(y) - int(y.sum())),
            "frozen_label_applied_count": int(pd.to_numeric(rows.get("frozen_label_applied"), errors="coerce").fillna(0).astype(int).sum())
            if "frozen_label_applied" in rows.columns
            else None,
        },
        "baseline_metrics": {
            "aggregation_flag_pr_auc": combined_metrics.get("aggregation_flag_pr_auc"),
            "aggregation_relevant_pr_auc": combined_metrics.get("aggregation_relevant_pr_auc"),
            "raw_global_aggregation_pr_auc": raw_global_ap,
            "raw_branch_aggregation_pr_auc": raw_branch_ap,
            "raw_branch_macro_aggregation_pr_auc": None if math.isnan(raw_branch_macro) else float(raw_branch_macro),
        },
        "calibrated_metrics": {
            "oof_global_aggregation_pr_auc": calibrated_global_ap,
            "oof_branch_aggregation_pr_auc": calibrated_branch_ap,
            "oof_branch_macro_aggregation_pr_auc": None if math.isnan(calibrated_branch_macro) else float(calibrated_branch_macro),
            "improvement_vs_raw_global_pr_auc": None
            if raw_global_ap is None or calibrated_global_ap is None
            else float(calibrated_global_ap - raw_global_ap),
        },
        "model": {
            "type": "logistic_regression_oof_diagnostic",
            "feature_count": int(len(feature_names)),
            "features": list(feature_names),
            "hyperparameters": {
                "l2": float(args.l2),
                "iters": int(args.iters),
                "lr": float(args.lr),
            },
            "final_bias": float(final_b),
            "top_weights": _top_weights(feature_names, final_mu, final_sigma, final_w, int(args.top_k)),
        },
        "recommendation": {
            "use_for_release_gate": False,
            "use_for_diagnostic_reporting": bool(
                calibrated_global_ap is not None
                and raw_global_ap is not None
                and calibrated_global_ap > raw_global_ap + float(args.min_improvement)
            ),
            "note": "keep branch-conditioned aggregation_relevant_pr_auc as the release metric; use calibrated global aggregation risk as an additional diagnostic only",
        },
    }

    out_json = str(args.out_json)
    out_md = str(args.out_md).strip() or _default_md_path(out_json)
    out_predictions_csv = str(args.out_predictions_csv).strip() or _default_predictions_path(out_json)
    _ensure_parent(out_json)
    _ensure_parent(out_md)
    _ensure_parent(out_predictions_csv)

    rows_to_write = rows[
        [
            "__fold_index",
            "__holdout",
            "target",
            "condition_group",
            "branch_label",
            "pred_state",
            "true_aggregation_flag",
            "pred_aggregation_prob",
            "pred_aggregation_risk_global",
            "pred_rank_compactness",
            "pred_rank_helicity",
            "pred_rank_condensation",
            "branch_weight_aggregation_prone",
            "branch_weight_llps_lcd",
            "branch_weight_helix_tad",
        ]
    ].copy()
    rows_to_write.to_csv(out_predictions_csv, index=False)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    def _fmt(x: Optional[float]) -> str:
        if x is None:
            return "n/a"
        return f"{float(x):.4f}"

    with open(out_md, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "# IDP Global Aggregation Calibrator",
                    "",
                    f"- rows: {payload['dataset']['row_count']}",
                    f"- folds: {payload['dataset']['fold_count']}",
                    f"- positives: {payload['dataset']['positive_count']}",
                    f"- raw_global_aggregation_pr_auc: {_fmt(payload['baseline_metrics']['raw_global_aggregation_pr_auc'])}",
                    f"- baseline_aggregation_relevant_pr_auc: {_fmt(payload['baseline_metrics']['aggregation_relevant_pr_auc'])}",
                    f"- oof_global_aggregation_pr_auc: {_fmt(payload['calibrated_metrics']['oof_global_aggregation_pr_auc'])}",
                    f"- improvement_vs_raw_global_pr_auc: {_fmt(payload['calibrated_metrics']['improvement_vs_raw_global_pr_auc'])}",
                    f"- diagnostic_recommendation: {payload['recommendation']['use_for_diagnostic_reporting']}",
                    "",
                    "## Branch AP",
                    "",
                    f"- aggregation_prone raw/oof: {_fmt(raw_branch_ap.get('aggregation_prone'))} / {_fmt(calibrated_branch_ap.get('aggregation_prone'))}",
                    f"- llps_lcd raw/oof: {_fmt(raw_branch_ap.get('llps_lcd'))} / {_fmt(calibrated_branch_ap.get('llps_lcd'))}",
                    f"- helix_tad raw/oof: {_fmt(raw_branch_ap.get('helix_tad'))} / {_fmt(calibrated_branch_ap.get('helix_tad'))}",
                    "",
                    "## Top Weights",
                    "",
                ]
            )
            + "\n"
        )
        for item in payload["model"]["top_weights"]:
            f.write(
                f"- `{item['feature']}`: weight={item['weight_standardized']:.4f}, mean={item['mean_train']:.4f}, std={item['std_train']:.4f}\n"
            )
        f.write(f"\n## Predictions CSV\n\n- `{out_predictions_csv}`\n")
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Evaluate a diagnostic global aggregation calibrator from a release manifest.")
    p.add_argument("--manifest-json", required=True, type=str)
    p.add_argument("--out-json", required=True, type=str)
    p.add_argument("--out-md", default="", type=str)
    p.add_argument("--out-predictions-csv", default="", type=str)
    p.add_argument("--l2", type=float, default=0.05)
    p.add_argument("--iters", type=int, default=4000)
    p.add_argument("--lr", type=float, default=0.03)
    p.add_argument("--top-k", type=int, default=8)
    p.add_argument("--min-improvement", type=float, default=0.05)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = evaluate(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
