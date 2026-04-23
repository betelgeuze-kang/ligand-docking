#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

try:
    from rdkit.ML.Scoring.Scoring import CalcBEDROC as _RDKIT_CALC_BEDROC  # type: ignore
except Exception:  # pragma: no cover
    _RDKIT_CALC_BEDROC = None


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _parse_topk_list(spec: str) -> List[int]:
    out: List[int] = []
    for tok in str(spec).split(","):
        s = str(tok).strip()
        if not s:
            continue
        try:
            k = int(float(s))
        except Exception:
            continue
        if k > 0:
            out.append(k)
    if not out:
        out = [10, 20, 50]
    return sorted(set(out))


def _parse_roles(spec: str) -> List[str]:
    return [tok.strip() for tok in str(spec or "").split(",") if tok.strip()]


def _score_resolution_metrics(scores: np.ndarray) -> Dict[str, Any]:
    s = np.asarray(scores, dtype=np.float64)
    n = int(s.size)
    finite = s[np.isfinite(s)]
    if n <= 0 or finite.size <= 0:
        return {
            "score_unique_count": 0,
            "score_unique_ratio": float("nan"),
            "score_tie_ratio": float("nan"),
            "score_mode_ratio": float("nan"),
        }
    rounded = np.round(finite, 12)
    uniq_vals, counts = np.unique(rounded, return_counts=True)
    uniq = int(uniq_vals.size)
    unique_ratio = float(uniq / max(n, 1))
    tie_ratio = float(1.0 - unique_ratio)
    mode_ratio = float(np.max(counts) / max(n, 1)) if counts.size > 0 else float("nan")
    return {
        "score_unique_count": uniq,
        "score_unique_ratio": unique_ratio,
        "score_tie_ratio": tie_ratio,
        "score_mode_ratio": mode_ratio,
    }


def _safe_auc_from_ranks(labels: np.ndarray, scores: np.ndarray, lower_better: bool) -> float:
    y = labels.astype(int)
    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))
    if n_pos <= 0 or n_neg <= 0:
        return float("nan")
    pos = scores[y == 1].reshape(-1, 1)
    neg = scores[y == 0].reshape(1, -1)
    better = (pos < neg).astype(np.float64) if bool(lower_better) else (pos > neg).astype(np.float64)
    ties = (pos == neg).astype(np.float64) * 0.5
    auc = float((better + ties).sum() / float(n_pos * n_neg))
    return auc


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    if a.size <= 1 or b.size <= 1:
        return float("nan")
    ar = pd.Series(a).rank(method="average").to_numpy(dtype=np.float64)
    br = pd.Series(b).rank(method="average").to_numpy(dtype=np.float64)
    av = ar - np.mean(ar)
    bv = br - np.mean(br)
    denom = float(np.sqrt(np.sum(av**2) * np.sum(bv**2)))
    if denom <= 1e-12:
        return float("nan")
    return float(np.sum(av * bv) / denom)


def _orient_scores(scores: np.ndarray, lower_better: bool) -> np.ndarray:
    return -scores if bool(lower_better) else scores


def _average_precision(labels: np.ndarray, scores: np.ndarray, lower_better: bool) -> float:
    y = labels.astype(int)
    n_pos = int(np.sum(y == 1))
    if n_pos <= 0:
        return float("nan")
    ord_idx = np.argsort(_orient_scores(scores, lower_better))[::-1]
    ys = y[ord_idx]
    tp = np.cumsum(ys == 1)
    fp = np.cumsum(ys == 0)
    prec = tp / np.maximum(tp + fp, 1)
    rec = tp / float(n_pos)
    ap = 0.0
    prev = 0.0
    for i in range(len(ys)):
        if ys[i] == 1:
            ap += float(prec[i]) * float(rec[i] - prev)
            prev = float(rec[i])
    return float(ap)


def _ef_at_fraction(labels: np.ndarray, scores: np.ndarray, lower_better: bool, frac: float = 0.01) -> float:
    y = labels.astype(int)
    n = int(len(y))
    if n <= 0:
        return float("nan")
    pos_rate = float(np.mean(y == 1))
    if pos_rate <= 1e-12:
        return float("nan")
    k = int(max(1, math.ceil(float(frac) * n)))
    ord_idx = np.argsort(_orient_scores(scores, lower_better))[::-1]
    ys = y[ord_idx]
    hit_rate = float(np.mean(ys[:k] == 1))
    return float(hit_rate / pos_rate)


def _bedroc(labels: np.ndarray, scores: np.ndarray, lower_better: bool, alpha: float = 20.0) -> float:
    y = labels.astype(int)
    n = int(len(y))
    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))
    if n <= 1 or n_pos <= 0 or n_neg <= 0:
        return float("nan")
    a = float(max(alpha, 1e-6))
    ord_idx = np.argsort(_orient_scores(scores, lower_better))[::-1]
    ys = y[ord_idx]

    # Use RDKit's production BEDROC implementation when available.
    if _RDKIT_CALC_BEDROC is not None:
        try:
            ranked = [(float(n - i), int(lbl)) for i, lbl in enumerate(ys.tolist())]
            # RDKit sorts by column 0 descending; with pre-sorted list and monotonic
            # first column this preserves ranking and yields canonical BEDROC in [0, 1].
            bed = float(_RDKIT_CALC_BEDROC(ranked, 0, a))
            return float(min(max(bed, 0.0), 1.0))
        except Exception:
            pass

    # Fallback: normalized exponential early-recognition score in [0, 1].
    rank_frac = (np.arange(n, dtype=np.float64) + 1.0) / float(n)
    w = np.exp(-a * rank_frac)
    weighted_hit = float(np.sum(w * ys.astype(np.float64)) / max(np.sum(w), 1e-12))
    rand = float(np.mean(y == 1))
    if rand >= 1.0:
        return 1.0
    bed = (weighted_hit - rand) / max(1.0 - rand, 1e-12)
    return float(min(max(bed, 0.0), 1.0))


def _score_to_probability(
    scores: np.ndarray,
    lower_better: bool,
    logit_scale: float = 1.35,
    binder_threshold: Optional[float] = None,
    target_prevalence: Optional[float] = None,
) -> np.ndarray:
    s = scores.astype(np.float64)
    if binder_threshold is not None and np.isfinite(float(binder_threshold)):
        thr = float(binder_threshold)
        q1, q3 = np.percentile(s, [25.0, 75.0])
        spread = float((q3 - q1) / 1.349) if np.isfinite(q3 - q1) else float("nan")
        if (not np.isfinite(spread)) or spread <= 1e-8:
            spread = float(np.std(s))
        temp = max(spread / max(float(logit_scale), 1e-6), 1e-6)
        if bool(lower_better):
            z = (thr - s) / temp
        else:
            z = (s - thr) / temp
        if target_prevalence is not None and np.isfinite(float(target_prevalence)):
            p_target = float(min(max(float(target_prevalence), 1e-6), 1.0 - 1e-6))
            lo, hi = -40.0, 40.0
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                p_mid = float(np.mean(1.0 / (1.0 + np.exp(-np.clip(z + mid, -40.0, 40.0)))))
                if p_mid > p_target:
                    hi = mid
                else:
                    lo = mid
            z = z + 0.5 * (lo + hi)
        z = np.clip(z, -40.0, 40.0)
        p = 1.0 / (1.0 + np.exp(-z))
        return np.clip(p, 1e-6, 1.0 - 1e-6)

    o = _orient_scores(s, lower_better)
    med = float(np.median(o))
    mad = float(np.median(np.abs(o - med)))
    scale = 1.4826 * mad if mad > 1e-12 else float(np.std(o) + 1e-8)
    z = (o - med) / max(scale, 1e-8)
    z = float(max(logit_scale, 1e-6)) * z
    z = np.clip(z, -40.0, 40.0)
    p = 1.0 / (1.0 + np.exp(-z))
    return np.clip(p, 1e-6, 1.0 - 1e-6)


def _brier_score(labels: np.ndarray, probs: np.ndarray) -> float:
    y = labels.astype(np.float64)
    p = np.clip(probs.astype(np.float64), 1e-6, 1.0 - 1e-6)
    return float(np.mean((p - y) ** 2))


def _ece(labels: np.ndarray, probs: np.ndarray, n_bins: int = 10) -> float:
    y = labels.astype(np.float64)
    p = np.clip(probs.astype(np.float64), 1e-6, 1.0 - 1e-6)
    bins = np.linspace(0.0, 1.0, int(max(n_bins, 2)) + 1)
    ece = 0.0
    n = float(len(p))
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        if i < len(bins) - 2:
            m = (p >= lo) & (p < hi)
        else:
            m = (p >= lo) & (p <= hi)
        c = int(np.sum(m))
        if c <= 0:
            continue
        conf = float(np.mean(p[m]))
        acc = float(np.mean(y[m]))
        ece += float((c / n) * abs(acc - conf))
    return float(ece)


def _bootstrap_ci(
    labels: np.ndarray,
    scores: np.ndarray,
    prob_scores: Optional[np.ndarray],
    lower_better: bool,
    n_boot: int,
    seed: int,
    alpha_bedroc: float,
    ece_bins: int,
    prob_logit_scale: float,
    binder_threshold: float,
) -> Dict[str, Dict[str, float]]:
    if int(n_boot) <= 0:
        return {}
    y = labels.astype(int)
    s = scores.astype(np.float64)
    n = len(y)
    if n <= 1:
        return {}
    rng = np.random.default_rng(int(seed))
    store: Dict[str, List[float]] = {
        "roc_auc": [],
        "pr_auc": [],
        "ef1": [],
        "bedroc_alpha20": [],
        "brier": [],
        "ece_10bin": [],
    }
    for _ in range(int(n_boot)):
        idx = rng.integers(0, n, size=n)
        yb = y[idx]
        sb = s[idx]
        if np.sum(yb == 1) <= 0 or np.sum(yb == 0) <= 0:
            continue
        sb_prob = sb
        if prob_scores is not None:
            sb_prob = prob_scores[idx]
        pb = _score_to_probability(
            sb_prob,
            lower_better,
            logit_scale=float(prob_logit_scale),
            binder_threshold=float(binder_threshold),
            target_prevalence=float(np.mean(yb == 1)),
        )
        store["roc_auc"].append(_safe_auc_from_ranks(yb, sb, lower_better))
        store["pr_auc"].append(_average_precision(yb, sb, lower_better))
        store["ef1"].append(_ef_at_fraction(yb, sb, lower_better, frac=0.01))
        store["bedroc_alpha20"].append(_bedroc(yb, sb, lower_better, alpha=alpha_bedroc))
        store["brier"].append(_brier_score(yb, pb))
        store["ece_10bin"].append(_ece(yb, pb, n_bins=ece_bins))

    out: Dict[str, Dict[str, float]] = {}
    for k, vals in store.items():
        vv = [float(x) for x in vals if not np.isnan(float(x))]
        if len(vv) <= 0:
            continue
        arr = np.asarray(vv, dtype=np.float64)
        lo = float(np.percentile(arr, 2.5))
        hi = float(np.percentile(arr, 97.5))
        out[k] = {
            "low": lo,
            "high": hi,
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr, ddof=0)),
            "n": int(len(arr)),
        }
    return out


def _compute_metrics_block(
    df: pd.DataFrame,
    score_col: str,
    probability_score_col: Optional[str],
    binder_col: str,
    ref_energy_col: str,
    lower_better: bool,
    binder_threshold_kcal_mol: float,
    topk_list: List[int],
    bootstrap_n: int,
    bootstrap_seed: int,
    bootstrap_bedroc_alpha: float,
    ece_bins: int,
    prob_logit_scale: float,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"metrics": {}, "topk": [], "metrics_ci": {}}
    if df.empty:
        return out
    y: Optional[np.ndarray] = None
    if binder_col in df.columns:
        y = df[binder_col].astype(int).to_numpy(dtype=np.int64)
    elif ref_energy_col in df.columns:
        thr = float(binder_threshold_kcal_mol)
        y = (df[ref_energy_col].astype(float).to_numpy(dtype=np.float64) <= thr).astype(np.int64)
    if y is not None:
        scores = df[score_col].astype(float).to_numpy(dtype=np.float64)
        prob_source_col = str(probability_score_col or score_col).strip() or score_col
        if prob_source_col not in df.columns:
            prob_source_col = score_col
        prob_scores = df[prob_source_col].astype(float).to_numpy(dtype=np.float64)
        pos_count = int(np.sum(y == 1))
        auc = _safe_auc_from_ranks(y, scores, lower_better=bool(lower_better))
        auc_flip = _safe_auc_from_ranks(y, scores, lower_better=(not bool(lower_better)))
        pr_auc = _average_precision(y, scores, lower_better=bool(lower_better))
        pr_auc_flip = _average_precision(y, scores, lower_better=(not bool(lower_better)))
        ef1 = _ef_at_fraction(y, scores, lower_better=bool(lower_better), frac=0.01)
        bedroc = _bedroc(y, scores, lower_better=bool(lower_better), alpha=float(bootstrap_bedroc_alpha))
        probs = _score_to_probability(
            prob_scores,
            lower_better=bool(lower_better),
            logit_scale=float(prob_logit_scale),
            binder_threshold=float(binder_threshold_kcal_mol),
            target_prevalence=float(np.mean(y == 1)),
        )
        brier = _brier_score(y, probs)
        ece = _ece(y, probs, n_bins=int(ece_bins))
        pos_rate = float(np.mean(y == 1))

        out["metrics"]["roc_auc"] = float(auc)
        out["metrics"]["roc_auc_if_flipped"] = float(auc_flip)
        out["metrics"]["pr_auc"] = float(pr_auc)
        out["metrics"]["pr_auc_if_flipped"] = float(pr_auc_flip)
        out["metrics"]["ef1"] = float(ef1)
        out["metrics"]["bedroc_alpha20"] = float(bedroc)
        out["metrics"]["brier"] = float(brier)
        out["metrics"]["ece_10bin"] = float(ece)
        out["metrics"]["positive_rate"] = float(pos_rate)
        out["metrics"]["positive_count"] = int(max(0, pos_count))
        out["metrics"]["probability_score_col_used"] = str(prob_source_col)
        out["metrics"].update(_score_resolution_metrics(scores))
        if np.isfinite(auc) and np.isfinite(auc_flip):
            delta = float(auc_flip - auc)
            out["metrics"]["score_orientation_auc_delta"] = delta
            out["metrics"]["score_orientation_suspect"] = bool(delta > 0.05)

        # top-k from sorted df ordering
        for k in topk_list:
            kk = int(min(max(k, 1), len(df)))
            yk = y[:kk]
            hit_rate = float(np.mean(yk == 1))
            ef = float(hit_rate / pos_rate) if pos_rate > 1e-12 else float("nan")
            out["topk"].append(
                {
                    "k": int(kk),
                    "hit_rate": hit_rate,
                    "enrichment_factor": ef,
                    "hits": int(np.sum(yk == 1)),
                }
            )

        out["metrics_ci"] = _bootstrap_ci(
            labels=y,
            scores=scores,
            prob_scores=prob_scores,
            lower_better=bool(lower_better),
            n_boot=int(bootstrap_n),
            seed=int(bootstrap_seed),
            alpha_bedroc=float(bootstrap_bedroc_alpha),
            ece_bins=int(ece_bins),
            prob_logit_scale=float(prob_logit_scale),
            binder_threshold=float(binder_threshold_kcal_mol),
        )

    if ref_energy_col in df.columns:
        ref = df[ref_energy_col].astype(float).to_numpy(dtype=np.float64)
        pred = df[score_col].astype(float).to_numpy(dtype=np.float64)
        sp = _spearman(-pred, -ref)
        out["metrics"]["spearman_ref_vs_score"] = float(sp)
    return out


def _resolve_worst_score_value(
    finite_scores: np.ndarray,
    *,
    lower_better: bool,
    explicit_value: Optional[float],
    margin: float,
) -> float:
    if explicit_value is not None and np.isfinite(float(explicit_value)):
        return float(explicit_value)
    m = float(abs(margin))
    if finite_scores.size > 0:
        if bool(lower_better):
            return float(np.max(finite_scores) + m)
        return float(np.min(finite_scores) - m)
    return float(9999.0 if bool(lower_better) else -9999.0)


def _apply_missing_score_policy(
    df: pd.DataFrame,
    *,
    score_col: str,
    lower_better: bool,
    policy: str,
    worst_value: Optional[float],
    worst_margin: float,
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    out_df = df.copy()
    arr = pd.to_numeric(out_df[score_col], errors="coerce").to_numpy(dtype=np.float64)
    missing = np.isnan(arr)
    nonfinite = np.isinf(arr)
    invalid = ~np.isfinite(arr)
    stats: Dict[str, Any] = {
        "rows": int(len(out_df)),
        "missing_score_rows": int(np.sum(missing)),
        "nonfinite_score_rows": int(np.sum(nonfinite)),
        "invalid_score_rows": int(np.sum(invalid)),
        "repaired_worst_rows": 0,
        "dropped_invalid_rows": 0,
        "worst_score_value": None,
        "policy": str(policy),
    }

    if int(np.sum(invalid)) <= 0:
        out_df[score_col] = arr
        return out_df, stats

    mode = str(policy).strip().lower()
    if mode == "drop":
        keep = np.isfinite(arr)
        stats["dropped_invalid_rows"] = int(np.sum(~keep))
        out_df = out_df.loc[keep].copy()
        out_df[score_col] = pd.to_numeric(out_df[score_col], errors="coerce")
        return out_df, stats

    finite = arr[np.isfinite(arr)]
    worst = _resolve_worst_score_value(
        finite,
        lower_better=bool(lower_better),
        explicit_value=worst_value,
        margin=float(worst_margin),
    )
    arr_fixed = arr.copy()
    arr_fixed[invalid] = float(worst)
    out_df[score_col] = arr_fixed
    stats["repaired_worst_rows"] = int(np.sum(invalid))
    stats["worst_score_value"] = float(worst)
    return out_df, stats


def run_eval(args: argparse.Namespace) -> Dict[str, Any]:
    scores_csv = str(args.scores_csv).strip()
    if (not scores_csv) or (not os.path.exists(scores_csv)):
        raise FileNotFoundError(f"scores csv not found: {scores_csv}")
    sdf = pd.read_csv(scores_csv)
    if sdf.empty:
        raise ValueError(f"scores csv is empty: {scores_csv}")

    score_col = str(args.score_col).strip()
    if score_col not in sdf.columns:
        raise ValueError(f"score column not found in scores csv: {score_col}")
    probability_score_col = str(getattr(args, "probability_score_col", "") or "").strip()
    if probability_score_col and (probability_score_col not in sdf.columns):
        raise ValueError(f"probability score column not found in scores csv: {probability_score_col}")

    labels_csv = str(args.labels_csv).strip()
    join_target = str(args.join_target_col).strip()
    join_ligand = str(args.join_ligand_col).strip()
    binder_col = str(args.binder_col).strip()
    ref_energy_col = str(args.ref_energy_col).strip()

    score_cols = [join_target, join_ligand, score_col]
    if probability_score_col and (probability_score_col not in score_cols):
        score_cols.append(probability_score_col)
    # Preserve distance column for downstream gate/source selection.
    if "mean_min_distance_A" in sdf.columns and ("mean_min_distance_A" not in score_cols):
        score_cols.append("mean_min_distance_A")
    score_part = sdf[score_cols].copy()
    score_part[score_col] = pd.to_numeric(score_part[score_col], errors="coerce")
    if probability_score_col and (probability_score_col in score_part.columns):
        score_part[probability_score_col] = pd.to_numeric(score_part[probability_score_col], errors="coerce")
    if "mean_min_distance_A" in score_part.columns:
        score_part["mean_min_distance_A"] = pd.to_numeric(score_part["mean_min_distance_A"], errors="coerce")
    agg_map: Dict[str, str] = {score_col: "mean"}
    if probability_score_col and (probability_score_col in score_part.columns):
        agg_map[probability_score_col] = "mean"
    if "mean_min_distance_A" in score_part.columns:
        agg_map["mean_min_distance_A"] = "mean"
    score_part = score_part.groupby([join_target, join_ligand], as_index=False).agg(agg_map).reset_index(drop=True)

    merged = score_part.copy()
    has_labels = False
    rows_label_keys = 0
    if labels_csv and os.path.exists(labels_csv):
        ldf = pd.read_csv(labels_csv)
        miss = [c for c in (join_target, join_ligand) if c not in ldf.columns]
        if miss:
            raise ValueError(f"labels csv missing key columns: {miss}")
        use_cols = [join_target, join_ligand]
        for c in (binder_col, ref_energy_col):
            if c in ldf.columns:
                use_cols.append(c)
        label_part = ldf[use_cols].copy().drop_duplicates([join_target, join_ligand], keep="first")
        rows_label_keys = int(len(label_part))
        if bool(getattr(args, "labels_driven_eval", True)):
            merged = label_part.merge(score_part, on=[join_target, join_ligand], how="left")
        else:
            merged = score_part.merge(label_part, on=[join_target, join_ligand], how="inner")
        has_labels = True

    if merged.empty:
        raise ValueError("no rows available after score/label merge")

    split_csv = str(getattr(args, "split_csv", "") or "").strip()
    split_role_col = str(getattr(args, "split_role_col", "role") or "role").strip()
    split_target_col = str(getattr(args, "split_target_col", join_target) or join_target).strip()
    split_ligand_col = str(getattr(args, "split_ligand_col", join_ligand) or join_ligand).strip()
    eval_roles = _parse_roles(str(getattr(args, "eval_roles", "") or ""))
    ood_eval_roles = _parse_roles(str(getattr(args, "ood_eval_roles", "ood_eval") or "ood_eval"))
    require_split_eval = bool(getattr(args, "require_split_for_eval", False))
    require_ood_eval = bool(getattr(args, "require_ood_eval", False))
    expected_keys_csv = str(getattr(args, "expected_keys_csv", "") or "").strip()
    expected_target_col = str(getattr(args, "expected_target_col", join_target) or join_target).strip()
    expected_ligand_col = str(getattr(args, "expected_ligand_col", join_ligand) or join_ligand).strip()
    min_expected_score_coverage = float(getattr(args, "min_expected_score_coverage", 0.0) or 0.0)
    rows_expected_keys = 0
    rows_expected_keys_with_score = 0
    if split_csv:
        if not os.path.exists(split_csv):
            raise FileNotFoundError(f"split csv not found: {split_csv}")
        split_df = pd.read_csv(split_csv)
        req = {split_target_col, split_ligand_col, split_role_col}
        miss = [c for c in req if c not in split_df.columns]
        if miss:
            raise ValueError(f"split csv missing columns: {miss}")
        split_part = split_df[[split_target_col, split_ligand_col, split_role_col]].copy()
        split_part = split_part.rename(columns={split_target_col: join_target, split_ligand_col: join_ligand})
        merged = merged.merge(split_part, on=[join_target, join_ligand], how="left")
    elif require_split_eval:
        raise ValueError("--require-split-for-eval enabled but --split-csv is missing")

    if expected_keys_csv:
        if not os.path.exists(expected_keys_csv):
            raise FileNotFoundError(f"expected keys csv not found: {expected_keys_csv}")
        ek = pd.read_csv(expected_keys_csv)
        req = {expected_target_col, expected_ligand_col}
        miss = [c for c in req if c not in ek.columns]
        if miss:
            raise ValueError(f"expected keys csv missing columns: {miss}")
        expected_keys = (
            ek[[expected_target_col, expected_ligand_col]]
            .rename(columns={expected_target_col: join_target, expected_ligand_col: join_ligand})
            .drop_duplicates([join_target, join_ligand], keep="first")
            .reset_index(drop=True)
        )
        rows_expected_keys = int(len(expected_keys))
        rows_expected_keys_with_score = int(
            len(expected_keys.merge(score_part[[join_target, join_ligand]], on=[join_target, join_ligand], how="inner"))
        )
        if rows_expected_keys > 0 and min_expected_score_coverage > 0:
            cov = float(rows_expected_keys_with_score / rows_expected_keys)
            if cov + 1e-12 < min_expected_score_coverage:
                raise ValueError(
                    f"expected score coverage too low: {cov:.6f} < {min_expected_score_coverage:.6f}"
                )
        merged = merged.merge(expected_keys, on=[join_target, join_ligand], how="inner")

    out = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "pass": True,
        "has_labels": bool(has_labels),
        "rows_scores": int(len(sdf)),
        "rows_score_unique_keys": int(len(score_part)),
        "rows_label_keys": int(rows_label_keys),
        "rows_eval": int(len(merged)),
        "rows_eval_after_role_filter": int(len(merged)),
        "rows_eval_role_filtered_out": 0,
        "rows_eval_after_score_policy": int(len(merged)),
        "rows_eval_filtered": int(len(merged)),
        "rows_eval_ood": 0,
        "rows_eval_missing_score": 0,
        "rows_eval_nonfinite_score": 0,
        "rows_eval_invalid_score": 0,
        "rows_eval_repaired_worst_score": 0,
        "rows_eval_dropped_invalid_score": 0,
        "eval_unique_keys": 0,
        "ood_unique_keys": 0,
        "score_col": score_col,
        "probability_score_col": probability_score_col if probability_score_col else score_col,
        "lower_better": bool(args.lower_better),
        "labels_driven_eval": bool(getattr(args, "labels_driven_eval", True)),
        "missing_score_policy": str(getattr(args, "missing_score_policy", "worst")),
        "missing_score_worst_margin": float(getattr(args, "missing_score_worst_margin", 1000.0)),
        "missing_score_worst_value": (
            float(getattr(args, "missing_score_worst_value"))
            if getattr(args, "missing_score_worst_value", None) is not None
            else None
        ),
        "split_csv": split_csv,
        "expected_keys_csv": expected_keys_csv,
        "rows_expected_keys": int(rows_expected_keys),
        "rows_expected_keys_with_score": int(rows_expected_keys_with_score),
        "observed_expected_score_coverage_ratio": (
            float(rows_expected_keys_with_score / rows_expected_keys) if rows_expected_keys > 0 else None
        ),
        "eval_roles": eval_roles,
        "ood_eval_roles": ood_eval_roles,
        "metrics": {},
        "metrics_ci": {},
        "metrics_unique": {},
        "metrics_ci_unique": {},
        "metrics_ood": {},
        "metrics_ci_ood": {},
        "metrics_ood_unique": {},
        "metrics_ci_ood_unique": {},
        "topk": [],
        "topk_unique": [],
        "topk_ood": [],
        "topk_ood_unique": [],
        "mean_min_distance_A_unique": None,
        "mean_min_distance_A_topk_unique": None,
        "distance_topk_k": int(getattr(args, "distance_topk_k", 200) or 200),
        "artifacts": {},
    }

    topk_list = _parse_topk_list(args.topk_list)
    eval_df = merged.copy()
    if split_role_col in eval_df.columns and eval_roles:
        eval_df = eval_df[eval_df[split_role_col].astype(str).isin(eval_roles)].copy()
    out["rows_eval_after_role_filter"] = int(len(eval_df))
    out["rows_eval_role_filtered_out"] = int(max(0, int(out["rows_eval"]) - int(out["rows_eval_after_role_filter"])))
    if eval_df.empty:
        raise ValueError("no rows available after eval role filtering")

    eval_df, eval_score_stats = _apply_missing_score_policy(
        eval_df,
        score_col=score_col,
        lower_better=bool(args.lower_better),
        policy=str(getattr(args, "missing_score_policy", "worst")),
        worst_value=getattr(args, "missing_score_worst_value", None),
        worst_margin=float(getattr(args, "missing_score_worst_margin", 1000.0)),
    )
    if eval_df.empty:
        raise ValueError("no rows left after missing-score policy applied")

    out["rows_eval_after_score_policy"] = int(len(eval_df))
    out["rows_eval_filtered"] = int(len(eval_df))
    out["rows_eval_missing_score"] = int(eval_score_stats.get("missing_score_rows", 0))
    out["rows_eval_nonfinite_score"] = int(eval_score_stats.get("nonfinite_score_rows", 0))
    out["rows_eval_invalid_score"] = int(eval_score_stats.get("invalid_score_rows", 0))
    out["rows_eval_repaired_worst_score"] = int(eval_score_stats.get("repaired_worst_rows", 0))
    out["rows_eval_dropped_invalid_score"] = int(eval_score_stats.get("dropped_invalid_rows", 0))
    if eval_score_stats.get("worst_score_value") is not None:
        out["missing_score_worst_value_effective"] = float(eval_score_stats["worst_score_value"])

    if has_labels:
        sorted_eval = eval_df.sort_values(score_col, ascending=bool(args.lower_better)).reset_index(drop=True)
        blk = _compute_metrics_block(
            df=sorted_eval,
            score_col=score_col,
            probability_score_col=probability_score_col,
            binder_col=binder_col,
            ref_energy_col=ref_energy_col,
            lower_better=bool(args.lower_better),
            binder_threshold_kcal_mol=float(args.binder_threshold_kcal_mol),
            topk_list=topk_list,
            bootstrap_n=int(args.bootstrap_n),
            bootstrap_seed=int(args.bootstrap_seed),
            bootstrap_bedroc_alpha=float(args.bootstrap_bedroc_alpha),
            ece_bins=int(args.ece_bins),
            prob_logit_scale=float(args.probability_logit_scale),
        )
        out["metrics"] = dict(blk.get("metrics", {}))
        out["metrics_ci"] = dict(blk.get("metrics_ci", {}))
        out["topk"] = list(blk.get("topk", []))

        uniq_agg: Dict[str, str] = {score_col: "mean"}
        if probability_score_col and (probability_score_col in eval_df.columns) and (probability_score_col != score_col):
            uniq_agg[probability_score_col] = "mean"
        if binder_col in eval_df.columns:
            uniq_agg[binder_col] = "first"
        if "mean_min_distance_A" in eval_df.columns:
            uniq_agg["mean_min_distance_A"] = "mean"
        uniq_eval = eval_df.groupby([join_target, join_ligand], as_index=False).agg(uniq_agg)
        if ref_energy_col in eval_df.columns:
            uniq_eval = uniq_eval.merge(
                eval_df[[join_target, join_ligand, ref_energy_col]].drop_duplicates(),
                on=[join_target, join_ligand],
                how="left",
            )
        out["eval_unique_keys"] = int(len(uniq_eval))
        sorted_uniq = uniq_eval.sort_values(score_col, ascending=bool(args.lower_better)).reset_index(drop=True)
        uniq_blk = _compute_metrics_block(
            df=sorted_uniq,
            score_col=score_col,
            probability_score_col=probability_score_col,
            binder_col=binder_col,
            ref_energy_col=ref_energy_col,
            lower_better=bool(args.lower_better),
            binder_threshold_kcal_mol=float(args.binder_threshold_kcal_mol),
            topk_list=topk_list,
            bootstrap_n=int(args.bootstrap_n),
            bootstrap_seed=int(args.bootstrap_seed) + 17,
            bootstrap_bedroc_alpha=float(args.bootstrap_bedroc_alpha),
            ece_bins=int(args.ece_bins),
            prob_logit_scale=float(args.probability_logit_scale),
        )
        out["metrics_unique"] = dict(uniq_blk.get("metrics", {}))
        out["metrics_ci_unique"] = dict(uniq_blk.get("metrics_ci", {}))
        out["topk_unique"] = list(uniq_blk.get("topk", []))
        if "mean_min_distance_A" in sorted_uniq.columns:
            try:
                out["mean_min_distance_A_unique"] = float(pd.to_numeric(sorted_uniq["mean_min_distance_A"], errors="coerce").mean())
                d_topk = int(max(1, int(getattr(args, "distance_topk_k", 200) or 200)))
                d_topk = int(min(d_topk, len(sorted_uniq)))
                out["distance_topk_k"] = int(d_topk)
                if d_topk > 0:
                    out["mean_min_distance_A_topk_unique"] = float(
                        pd.to_numeric(sorted_uniq.head(d_topk)["mean_min_distance_A"], errors="coerce").mean()
                    )
            except Exception:
                out["mean_min_distance_A_unique"] = None
                out["mean_min_distance_A_topk_unique"] = None

        # Backward-compatible + gate-primary aliases.
        m_u = out["metrics_unique"]
        ci_u = out["metrics_ci_unique"]
        alias_map = {
            "roc_auc": "roc_auc_unique_key",
            "pr_auc": "pr_auc_unique_key",
            "ef1": "ef1_unique_key",
            "bedroc_alpha20": "bedroc_unique_key",
            "brier": "brier_unique_key",
            "ece_10bin": "ece_unique_key",
            "positive_rate": "positive_rate_unique_key",
            "positive_count": "positive_count_unique_key",
        }
        for src, dst in alias_map.items():
            if src in m_u:
                out["metrics"][dst] = float(m_u[src])
        for src, dst in alias_map.items():
            if src in ci_u:
                out["metrics_ci"][dst] = dict(ci_u[src])

        if split_role_col in merged.columns and ood_eval_roles:
            ood_df = merged[merged[split_role_col].astype(str).isin(ood_eval_roles)].copy()
            if not ood_df.empty:
                ood_df, _ood_score_stats = _apply_missing_score_policy(
                    ood_df,
                    score_col=score_col,
                    lower_better=bool(args.lower_better),
                    policy=str(getattr(args, "missing_score_policy", "worst")),
                    worst_value=getattr(args, "missing_score_worst_value", None),
                    worst_margin=float(getattr(args, "missing_score_worst_margin", 1000.0)),
                )
            out["rows_eval_ood"] = int(len(ood_df))
            if (not ood_df.empty) and has_labels:
                sorted_ood = ood_df.sort_values(score_col, ascending=bool(args.lower_better)).reset_index(drop=True)
                ood_blk = _compute_metrics_block(
                    df=sorted_ood,
                    score_col=score_col,
                    probability_score_col=probability_score_col,
                    binder_col=binder_col,
                    ref_energy_col=ref_energy_col,
                    lower_better=bool(args.lower_better),
                    binder_threshold_kcal_mol=float(args.binder_threshold_kcal_mol),
                    topk_list=topk_list,
                    bootstrap_n=int(args.bootstrap_n),
                    bootstrap_seed=int(args.bootstrap_seed) + 31,
                    bootstrap_bedroc_alpha=float(args.bootstrap_bedroc_alpha),
                    ece_bins=int(args.ece_bins),
                    prob_logit_scale=float(args.probability_logit_scale),
                )
                out["metrics_ood"] = dict(ood_blk.get("metrics", {}))
                out["metrics_ci_ood"] = dict(ood_blk.get("metrics_ci", {}))
                out["topk_ood"] = list(ood_blk.get("topk", []))

                ood_agg: Dict[str, str] = {score_col: "mean"}
                if probability_score_col and (probability_score_col in ood_df.columns) and (probability_score_col != score_col):
                    ood_agg[probability_score_col] = "mean"
                if binder_col in ood_df.columns:
                    ood_agg[binder_col] = "first"
                uniq_ood = ood_df.groupby([join_target, join_ligand], as_index=False).agg(ood_agg)
                if ref_energy_col in ood_df.columns:
                    uniq_ood = uniq_ood.merge(
                        ood_df[[join_target, join_ligand, ref_energy_col]].drop_duplicates(),
                        on=[join_target, join_ligand],
                        how="left",
                    )
                out["ood_unique_keys"] = int(len(uniq_ood))
                sorted_ood_uniq = uniq_ood.sort_values(score_col, ascending=bool(args.lower_better)).reset_index(drop=True)
                ood_uniq_blk = _compute_metrics_block(
                    df=sorted_ood_uniq,
                    score_col=score_col,
                    probability_score_col=probability_score_col,
                    binder_col=binder_col,
                    ref_energy_col=ref_energy_col,
                    lower_better=bool(args.lower_better),
                    binder_threshold_kcal_mol=float(args.binder_threshold_kcal_mol),
                    topk_list=topk_list,
                    bootstrap_n=int(args.bootstrap_n),
                    bootstrap_seed=int(args.bootstrap_seed) + 47,
                    bootstrap_bedroc_alpha=float(args.bootstrap_bedroc_alpha),
                    ece_bins=int(args.ece_bins),
                    prob_logit_scale=float(args.probability_logit_scale),
                )
                out["metrics_ood_unique"] = dict(ood_uniq_blk.get("metrics", {}))
                out["metrics_ci_ood_unique"] = dict(ood_uniq_blk.get("metrics_ci", {}))
                out["topk_ood_unique"] = list(ood_uniq_blk.get("topk", []))

                m_ou = out["metrics_ood_unique"]
                ci_ou = out["metrics_ci_ood_unique"]
                ood_alias_map = {
                    "roc_auc": "roc_auc_ood_unique_key",
                    "pr_auc": "pr_auc_ood_unique_key",
                    "ef1": "ef1_ood_unique_key",
                    "bedroc_alpha20": "bedroc_ood_unique_key",
                    "brier": "brier_ood_unique_key",
                    "ece_10bin": "ece_ood_unique_key",
                    "positive_count": "positive_count_ood_unique_key",
                }
                for src, dst in ood_alias_map.items():
                    if src in m_ou:
                        out["metrics"][dst] = float(m_ou[src])
                for src, dst in ood_alias_map.items():
                    if src in ci_ou:
                        out["metrics_ci"][dst] = dict(ci_ou[src])

            elif require_ood_eval:
                raise ValueError("require_ood_eval is enabled but no OOD eval rows found")
        elif require_ood_eval:
            raise ValueError("require_ood_eval is enabled but split role column is unavailable")

    detail_csv = str(args.out_detail_csv).strip() or f"{os.path.splitext(scores_csv)[0]}_ranking_eval_rows.csv"
    _ensure_parent(detail_csv)
    eval_df.sort_values(score_col, ascending=bool(args.lower_better)).reset_index(drop=True).to_csv(detail_csv, index=False)
    out["artifacts"]["detail_csv"] = detail_csv

    topk_csv = str(args.out_topk_csv).strip() or f"{os.path.splitext(scores_csv)[0]}_ranking_eval_topk.csv"
    _ensure_parent(topk_csv)
    pd.DataFrame(out["topk"]).to_csv(topk_csv, index=False)
    out["artifacts"]["topk_csv"] = topk_csv

    unique_csv = str(getattr(args, "out_unique_csv", "") or "").strip() or f"{os.path.splitext(scores_csv)[0]}_ranking_eval_unique.csv"
    _ensure_parent(unique_csv)
    unique_out_agg: Dict[str, str] = {score_col: "mean"}
    if probability_score_col and (probability_score_col in eval_df.columns) and (probability_score_col != score_col):
        unique_out_agg[probability_score_col] = "mean"
    if binder_col in eval_df.columns:
        unique_out_agg[binder_col] = "first"
    if "mean_min_distance_A" in eval_df.columns:
        unique_out_agg["mean_min_distance_A"] = "mean"
    unique_out = eval_df.groupby([join_target, join_ligand], as_index=False).agg(unique_out_agg)
    if ref_energy_col in eval_df.columns:
        unique_out = unique_out.merge(
            eval_df[[join_target, join_ligand, ref_energy_col]].drop_duplicates(),
            on=[join_target, join_ligand],
            how="left",
        )
    unique_out.sort_values(score_col, ascending=bool(args.lower_better)).to_csv(unique_csv, index=False)
    out["artifacts"]["unique_csv"] = unique_csv

    out_json = str(args.out_json).strip() or f"{os.path.splitext(scores_csv)[0]}_ranking_eval.json"
    out_md = str(args.out_md).strip() or f"{os.path.splitext(scores_csv)[0]}_ranking_eval.md"
    _ensure_parent(out_json)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    lines = [
        "# Ligand Ranking Evaluation",
        "",
        f"- generated_at_local: {out['generated_at_local']}",
        f"- pass: {out['pass']}",
        f"- has_labels: {out['has_labels']}",
        f"- rows_scores: {out['rows_scores']}",
        f"- rows_eval: {out['rows_eval']}",
        f"- rows_eval_after_role_filter: {out['rows_eval_after_role_filter']}",
        f"- rows_eval_role_filtered_out: {out['rows_eval_role_filtered_out']}",
        f"- rows_eval_after_score_policy: {out['rows_eval_after_score_policy']}",
        f"- rows_eval_filtered: {out['rows_eval_filtered']}",
        f"- rows_eval_ood: {out['rows_eval_ood']}",
        f"- rows_expected_keys: {out['rows_expected_keys']}",
        f"- rows_expected_keys_with_score: {out['rows_expected_keys_with_score']}",
        f"- observed_expected_score_coverage_ratio: {out['observed_expected_score_coverage_ratio']}",
        f"- eval_unique_keys: {out['eval_unique_keys']}",
        f"- ood_unique_keys: {out['ood_unique_keys']}",
        f"- score_col: `{out['score_col']}`",
        f"- probability_score_col: `{out['probability_score_col']}`",
        f"- metrics: {out['metrics']}",
        f"- metrics_ci: {out['metrics_ci']}",
        f"- metrics_unique: {out['metrics_unique']}",
        f"- metrics_ood_unique: {out['metrics_ood_unique']}",
        f"- mean_min_distance_A_unique: {out['mean_min_distance_A_unique']}",
        f"- mean_min_distance_A_topk_unique({out['distance_topk_k']}): {out['mean_min_distance_A_topk_unique']}",
        f"- detail_csv: `{detail_csv}`",
        f"- topk_csv: `{topk_csv}`",
        f"- unique_csv: `{unique_csv}`",
    ]
    _ensure_parent(out_md)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    out["artifacts"]["summary_json"] = out_json
    out["artifacts"]["summary_md"] = out_md
    return out


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(description="Evaluate ligand ranking quality with robust metrics and CI.")
    p.add_argument("--scores-csv", type=str, required=True)
    p.add_argument("--labels-csv", type=str, default="")
    p.add_argument("--score-col", type=str, default="binding_energy_mmpbsa_kcal_mol_calibrated")
    p.add_argument("--probability-score-col", type=str, default="")
    p.add_argument("--join-target-col", type=str, default="target")
    p.add_argument("--join-ligand-col", type=str, default="ligand_id")
    p.add_argument("--binder-col", type=str, default="is_binder")
    p.add_argument("--ref-energy-col", type=str, default="reference_binding_kcal_mol")
    p.add_argument("--binder-threshold-kcal-mol", type=float, default=-3.0)
    p.add_argument("--lower-better", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--split-csv", type=str, default="")
    p.add_argument("--split-role-col", type=str, default="role")
    p.add_argument("--split-target-col", type=str, default="target")
    p.add_argument("--split-ligand-col", type=str, default="ligand_id")
    p.add_argument("--eval-roles", type=str, default="")
    p.add_argument("--ood-eval-roles", type=str, default="ood_eval")
    p.add_argument("--require-split-for-eval", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--require-ood-eval", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--expected-keys-csv", type=str, default="")
    p.add_argument("--expected-target-col", type=str, default="target")
    p.add_argument("--expected-ligand-col", type=str, default="ligand_id")
    p.add_argument("--min-expected-score-coverage", type=float, default=0.0)
    p.add_argument("--topk-list", type=str, default="10,20,50")

    p.add_argument("--bootstrap-n", type=int, default=400)
    p.add_argument("--bootstrap-seed", type=int, default=7)
    p.add_argument("--bootstrap-bedroc-alpha", type=float, default=20.0)
    p.add_argument("--ece-bins", type=int, default=10)
    p.add_argument("--probability-logit-scale", type=float, default=1.35)
    p.add_argument("--distance-topk-k", type=int, default=200)
    p.add_argument("--labels-driven-eval", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--missing-score-policy", type=str, default="worst", choices=["worst", "drop"])
    p.add_argument("--missing-score-worst-margin", type=float, default=1000.0)
    p.add_argument("--missing-score-worst-value", type=float, default=None)

    p.add_argument("--out-detail-csv", type=str, default=f"runs/ligand_ranking_eval_rows_{stamp}.csv")
    p.add_argument("--out-topk-csv", type=str, default=f"runs/ligand_ranking_eval_topk_{stamp}.csv")
    p.add_argument("--out-unique-csv", type=str, default=f"runs/ligand_ranking_eval_unique_{stamp}.csv")
    p.add_argument("--out-json", type=str, default=f"runs/ligand_ranking_eval_{stamp}.json")
    p.add_argument("--out-md", type=str, default=f"runs/ligand_ranking_eval_{stamp}.md")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_eval(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
