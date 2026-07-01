#!/usr/bin/env python3
"""Build a claim-locked current-fit GPCR hard-decoy closure probe.

This probe trains a diagnostic logistic scorer on the current actual GPCR
hard-decoy rows after excluding identifier, label, reference, rank, target, and
previous supervised-output columns. It is intentionally claim-locked: fitting on
the evaluated rows can prove feature separability, not external beta readiness.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
except Exception:  # pragma: no cover - dependency availability is reported in output.
    LogisticRegression = None  # type: ignore[assignment]
    StandardScaler = None  # type: ignore[assignment]
    make_pipeline = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SCORES_CSV = "runs/gpcr_coverage_v2_supervised_logreg_l2_c10_shadow_replay_scores_current.csv"
DEFAULT_LABELS_CSV = (
    "runs/external_validation_2026-05-17_gpcr_a1_coverage_v2_beta_rescue_fast_r1_set1_core_blind_"
    "gpcr_core_full_hard_decoy_labels_balanced.csv"
)
DEFAULT_SPLIT_CSV = (
    "runs/external_validation_2026-05-17_gpcr_a1_coverage_v2_beta_rescue_fast_r1_set1_core_blind_"
    "gpcr_core_full_hard_decoy_split.csv"
)
DEFAULT_OUT_SCORES_CSV = "runs/gpcr_hard_decoy_current_fit_closure_probe_scores_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_current_fit_closure_probe_current.json"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_current_fit_closure_probe_current.md"

SCORE_COL = "binding_score_composite_v7_current_fit_closure_probe"
TARGET_HELDOUT_SCORE_COL = "binding_score_composite_v7_target_heldout_closure_probe"
TARGETS = {
    "CHEMBL217_DRD2_HUMAN": "DRD2",
    "CHEMBL224_HTR2A_HUMAN": "HTR2A",
    "CHEMBL233_OPRM1_HUMAN": "OPRM1",
}
FORBIDDEN_PATTERNS = (
    "ligand_id",
    "queue_id",
    "target",
    "source",
    "path",
    "json",
    "pdb",
    "npz",
    "mode",
    "family",
    "band",
    "kind",
    "format",
    "reason",
    "status",
    "hash",
    "role",
    "reference",
    "is_binder",
    "rank",
    "replica",
    "export",
    "split",
    "score_reference",
    "coverage_v2_adaptive_rank_rescue_shadow",
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_csv(path_like: str | Path) -> pd.DataFrame:
    path = _resolve(path_like)
    if not path.exists():
        raise FileNotFoundError(str(path))
    return pd.read_csv(path)


def _finite_float_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _feature_columns(df: pd.DataFrame, *, min_finite_ratio: float) -> list[str]:
    out: list[str] = []
    for col in df.columns:
        low = str(col).lower()
        if any(pattern in low for pattern in FORBIDDEN_PATTERNS):
            continue
        series = _finite_float_series(df[col])
        finite = series.dropna()
        if len(finite) < len(df) * float(min_finite_ratio):
            continue
        if finite.nunique(dropna=True) < 5:
            continue
        out.append(str(col))
    return out


def _average_precision(labels: np.ndarray, score_lower_better: np.ndarray) -> float:
    y = np.asarray(labels, dtype=np.int64)
    score = np.asarray(score_lower_better, dtype=np.float64)
    order = np.argsort(score, kind="mergesort")
    ranked = y[order]
    positives = int(np.sum(ranked == 1))
    if positives <= 0:
        return float("nan")
    tp = np.cumsum(ranked == 1)
    precision = tp / np.arange(1, len(ranked) + 1, dtype=np.float64)
    return float(np.sum(precision * (ranked == 1)) / float(positives))


def _topk_hit_rate(labels: np.ndarray, score_lower_better: np.ndarray, *, k: int = 20) -> float:
    y = np.asarray(labels, dtype=np.int64)
    score = np.asarray(score_lower_better, dtype=np.float64)
    order = np.argsort(score, kind="mergesort")[: min(int(k), len(score))]
    if len(order) <= 0:
        return float("nan")
    return float(np.mean(y[order] == 1))


def _bootstrap_pr_auc_ci(
    labels: np.ndarray,
    score_lower_better: np.ndarray,
    *,
    n: int,
    seed: int,
) -> dict[str, Any]:
    if int(n) <= 0:
        return {}
    y = np.asarray(labels, dtype=np.int64)
    score = np.asarray(score_lower_better, dtype=np.float64)
    rng = np.random.default_rng(int(seed))
    vals: list[float] = []
    for _ in range(int(n)):
        idx = rng.integers(0, len(y), size=len(y))
        yy = y[idx]
        if int(np.sum(yy == 1)) <= 0 or int(np.sum(yy == 0)) <= 0:
            continue
        vals.append(_average_precision(yy, score[idx]))
    if not vals:
        return {}
    arr = np.asarray(vals, dtype=np.float64)
    return {
        "low": float(np.percentile(arr, 2.5)),
        "high": float(np.percentile(arr, 97.5)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "n": int(len(arr)),
    }


def _target_separation(df: pd.DataFrame, score_lower_better: np.ndarray) -> dict[str, dict[str, Any]]:
    tmp = df[["target", "ligand_id", "is_binder", "mean_min_distance_A"]].copy()
    tmp["_score"] = np.asarray(score_lower_better, dtype=np.float64)
    tmp["is_binder"] = pd.to_numeric(tmp["is_binder"], errors="coerce").fillna(0).astype(int)
    out: dict[str, dict[str, Any]] = {}
    for target, target_id in TARGETS.items():
        sub = tmp[tmp["target"].astype(str).eq(target)].sort_values("_score", kind="mergesort").reset_index(drop=True)
        positives = sub[sub["is_binder"].eq(1)]
        if positives.empty:
            out[target_id] = {
                "decoys_above_positive_count": None,
                "positive_target_rank": None,
                "positive_anchor_distance_a": None,
                "top_decoy_anchor_distance_a": None,
                "anchor_margin_a": None,
                "positive_ligand_id": "",
                "top_decoy_ligand_id": "",
            }
            continue
        pos_index = int(positives.index[0])
        decoys_above = int((sub.iloc[:pos_index]["is_binder"] == 0).sum())
        positive_distance = float(sub.loc[pos_index, "mean_min_distance_A"])
        top_decoy = sub[sub["is_binder"].eq(0)].head(1)
        top_decoy_distance = None if top_decoy.empty else float(top_decoy.iloc[0]["mean_min_distance_A"])
        out[target_id] = {
            "decoys_above_positive_count": decoys_above,
            "positive_target_rank": int(pos_index + 1),
            "positive_anchor_distance_a": positive_distance,
            "top_decoy_anchor_distance_a": top_decoy_distance,
            "anchor_margin_a": None if top_decoy_distance is None else float(top_decoy_distance - positive_distance),
            "positive_ligand_id": str(sub.loc[pos_index, "ligand_id"]),
            "top_decoy_ligand_id": "" if top_decoy.empty else str(top_decoy.iloc[0]["ligand_id"]),
        }
    return out


def _metrics(
    df: pd.DataFrame,
    score_lower_better: np.ndarray,
    *,
    bootstrap_n: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    labels = pd.to_numeric(df["is_binder"], errors="coerce").fillna(0).astype(int).to_numpy()
    target_rows = _target_separation(df, score_lower_better)
    pr_ci = _bootstrap_pr_auc_ci(labels, score_lower_better, n=bootstrap_n, seed=bootstrap_seed)
    return {
        "ranking_pr_auc": _average_precision(labels, score_lower_better),
        "ranking_pr_auc_ci": pr_ci,
        "ranking_pr_auc_ci_low": pr_ci.get("low"),
        "top20_hit_rate": _topk_hit_rate(labels, score_lower_better, k=20),
        "target_rows": target_rows,
        "target_decoys_above_positive_total": int(
            sum(
                int(row.get("decoys_above_positive_count") or 0)
                for row in target_rows.values()
                if row.get("decoys_above_positive_count") is not None
            )
        ),
        "all_required_targets_decoy_clear": all(
            row.get("decoys_above_positive_count") == 0 for row in target_rows.values()
        ),
        "all_required_targets_anchor_margin_nonnegative": all(
            row.get("anchor_margin_a") is not None and float(row["anchor_margin_a"]) >= 0.0
            for row in target_rows.values()
        ),
    }


def _positive_rank_rows(df: pd.DataFrame, score_lower_better: np.ndarray) -> list[dict[str, Any]]:
    tmp = df[["target", "ligand_id", "is_binder", "mean_min_distance_A"]].copy()
    tmp["_score"] = np.asarray(score_lower_better, dtype=np.float64)
    tmp["is_binder"] = pd.to_numeric(tmp["is_binder"], errors="coerce").fillna(0).astype(int)
    rows: list[dict[str, Any]] = []
    for target, sub in tmp.groupby("target", sort=True):
        ranked = sub.sort_values("_score", kind="mergesort").reset_index(drop=True)
        target_id = TARGETS.get(str(target), str(target))
        for index, row in ranked[ranked["is_binder"].eq(1)].iterrows():
            rank = int(index + 1)
            rows.append(
                {
                    "target_id": target_id,
                    "target_source_id": str(target),
                    "ligand_id": str(row["ligand_id"]),
                    "positive_target_rank": rank,
                    "decoys_above_positive_count": int((ranked.iloc[:index]["is_binder"] == 0).sum()),
                    "positive_anchor_distance_a": float(row["mean_min_distance_A"]),
                    "score_lower_better": float(row["_score"]),
                    "in_top20": bool(rank <= 20),
                }
            )
    return sorted(rows, key=lambda row: (int(row["positive_target_rank"]), row["target_id"], row["ligand_id"]))


def _target_metric_rows(df: pd.DataFrame, score_lower_better: np.ndarray) -> list[dict[str, Any]]:
    labels = pd.to_numeric(df["is_binder"], errors="coerce").fillna(0).astype(int).to_numpy()
    score = np.asarray(score_lower_better, dtype=np.float64)
    rows: list[dict[str, Any]] = []
    for target in sorted(df["target"].astype(str).unique()):
        mask = df["target"].astype(str).eq(target).to_numpy()
        target_labels = labels[mask]
        target_score = score[mask]
        positive_ranks = [
            row["positive_target_rank"]
            for row in _positive_rank_rows(df.loc[mask].reset_index(drop=True), target_score)
        ]
        rows.append(
            {
                "target_id": TARGETS.get(target, target),
                "target_source_id": target,
                "row_count": int(np.sum(mask)),
                "positive_count": int(np.sum(target_labels == 1)),
                "ranking_pr_auc": _average_precision(target_labels, target_score),
                "top20_hit_rate": _topk_hit_rate(target_labels, target_score, k=20),
                "best_positive_rank": min(positive_ranks) if positive_ranks else None,
                "worst_positive_rank": max(positive_ranks) if positive_ranks else None,
                "positive_ranks": positive_ranks,
            }
        )
    return rows


def _merged_input(scores_csv: str | Path, labels_csv: str | Path, split_csv: str | Path, eval_roles: Iterable[str]) -> pd.DataFrame:
    scores = _read_csv(scores_csv)
    labels = _read_csv(labels_csv)[["target", "ligand_id", "is_binder", "reference_binding_kcal_mol"]]
    split = _read_csv(split_csv)
    role_set = {str(role).strip() for role in eval_roles if str(role).strip()}
    split_use = split[split["role"].astype(str).isin(role_set)][["target", "ligand_id", "role"]].drop_duplicates()
    merged = (
        scores.merge(labels.drop_duplicates(["target", "ligand_id"]), on=["target", "ligand_id"], how="left")
        .merge(split_use, on=["target", "ligand_id"], how="inner")
        .reset_index(drop=True)
    )
    if merged.empty:
        raise ValueError("no rows available after score/label/split merge")
    merged["is_binder"] = pd.to_numeric(merged["is_binder"], errors="coerce").fillna(0).astype(int)
    return merged


def _fit_probability(X: np.ndarray, y: np.ndarray, *, C: float) -> tuple[np.ndarray, Any]:
    if LogisticRegression is None or StandardScaler is None or make_pipeline is None:
        raise RuntimeError("scikit-learn is required for this probe")
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=float(C),
            solver="liblinear",
            class_weight="balanced",
            max_iter=2000,
            random_state=13,
        ),
    )
    model.fit(X, y)
    return model.predict_proba(X)[:, 1], model


def _target_heldout_probability(df: pd.DataFrame, X: np.ndarray, y: np.ndarray, *, C: float) -> np.ndarray:
    if LogisticRegression is None or StandardScaler is None or make_pipeline is None:
        raise RuntimeError("scikit-learn is required for this probe")
    out = np.zeros(len(df), dtype=np.float64)
    for target in sorted(df["target"].astype(str).unique()):
        test_mask = df["target"].astype(str).eq(target).to_numpy()
        train_mask = ~test_mask
        if int(np.sum(y[train_mask] == 1)) <= 0 or int(np.sum(y[train_mask] == 0)) <= 0:
            continue
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=float(C),
                solver="liblinear",
                class_weight="balanced",
                max_iter=2000,
                random_state=13,
            ),
        )
        model.fit(X[train_mask], y[train_mask])
        out[test_mask] = model.predict_proba(X[test_mask])[:, 1]
    return out


def _standardized_coefficients(model: Any, feature_columns: list[str]) -> list[dict[str, Any]]:
    try:
        weights = model.named_steps["logisticregression"].coef_[0]
    except Exception:
        return []
    rows = [
        {"feature": feature, "standardized_weight": float(weight)}
        for feature, weight in zip(feature_columns, weights)
    ]
    return sorted(rows, key=lambda row: abs(float(row["standardized_weight"])), reverse=True)


def _closure_gate(metrics: dict[str, Any]) -> bool:
    ci_low = metrics.get("ranking_pr_auc_ci_low")
    return bool(
        ci_low is not None
        and float(ci_low) >= 0.45
        and float(metrics.get("top20_hit_rate") or 0.0) >= 0.20
        and metrics.get("all_required_targets_decoy_clear") is True
        and metrics.get("all_required_targets_anchor_margin_nonnegative") is True
    )


def build_probe(
    *,
    scores_csv: str | Path = DEFAULT_SCORES_CSV,
    labels_csv: str | Path = DEFAULT_LABELS_CSV,
    split_csv: str | Path = DEFAULT_SPLIT_CSV,
    c_grid: Iterable[float] = (0.003, 0.01, 0.03, 0.1, 0.3, 1.0),
    min_finite_ratio: float = 0.95,
    bootstrap_n: int = 400,
    bootstrap_seed: int = 7,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if LogisticRegression is None:
        payload = {
            "status": "blocked_gpcr_hard_decoy_current_fit_closure_probe_sklearn_missing",
            "claim_promotion_allowed": False,
            "diagnostic_current_fit_used_labels": True,
        }
        return pd.DataFrame(), payload

    df = _merged_input(scores_csv, labels_csv, split_csv, eval_roles=("far_ood_eval",))
    feature_columns = _feature_columns(df, min_finite_ratio=min_finite_ratio)
    if not feature_columns:
        raise ValueError("no eligible feature columns found")
    X = (
        df[feature_columns]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .to_numpy(dtype=np.float64)
    )
    y = df["is_binder"].to_numpy(dtype=np.int64)

    candidates: list[dict[str, Any]] = []
    models: dict[float, Any] = {}
    current_scores: dict[float, np.ndarray] = {}
    target_heldout_scores: dict[float, np.ndarray] = {}
    for C in [float(value) for value in c_grid]:
        prob, model = _fit_probability(X, y, C=C)
        score = -prob
        current_metrics = _metrics(df, score, bootstrap_n=bootstrap_n, bootstrap_seed=bootstrap_seed)
        heldout_prob = _target_heldout_probability(df, X, y, C=C)
        heldout_score = -heldout_prob
        heldout_metrics = _metrics(df, heldout_score, bootstrap_n=bootstrap_n, bootstrap_seed=bootstrap_seed)
        candidate = {
            "C": float(C),
            "current_fit": current_metrics,
            "target_heldout": heldout_metrics,
            "current_fit_closure_gate_pass": _closure_gate(current_metrics),
            "target_heldout_closure_gate_pass": _closure_gate(heldout_metrics),
        }
        candidates.append(candidate)
        models[float(C)] = model
        current_scores[float(C)] = score
        target_heldout_scores[float(C)] = heldout_score

    def _selection_key(candidate: dict[str, Any]) -> tuple[int, float, float, float]:
        heldout = candidate["target_heldout"]
        return (
            1 if candidate["current_fit_closure_gate_pass"] else 0,
            float(heldout.get("ranking_pr_auc_ci_low") or -1.0),
            float(heldout.get("ranking_pr_auc") or -1.0),
            -float(candidate["C"]),
        )

    selected = max(candidates, key=_selection_key)
    selected_c = float(selected["C"])
    selected_score = current_scores[selected_c]
    selected_heldout_score = target_heldout_scores[selected_c]
    output_scores = df[["target", "ligand_id", "mean_min_distance_A"]].copy()
    output_scores[SCORE_COL] = selected_score
    output_scores[TARGET_HELDOUT_SCORE_COL] = selected_heldout_score
    heldout_positive_rank_rows = _positive_rank_rows(df, selected_heldout_score)
    heldout_target_metric_rows = _target_metric_rows(df, selected_heldout_score)

    current_pass = bool(selected["current_fit_closure_gate_pass"])
    heldout_pass = bool(selected["target_heldout_closure_gate_pass"])
    status = (
        "gpcr_hard_decoy_current_fit_closure_probe_ready_claim_locked"
        if current_pass
        else "blocked_gpcr_hard_decoy_current_fit_closure_probe_no_current_fit_closure"
    )
    payload = {
        "packet_type": "gpcr_hard_decoy_current_fit_closure_probe",
        "schema_version": "gpcr_hard_decoy_current_fit_closure_probe_v1",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "scores_csv": str(_resolve(scores_csv)),
        "labels_csv": str(_resolve(labels_csv)),
        "split_csv": str(_resolve(split_csv)),
        "score_col": SCORE_COL,
        "target_heldout_score_col": TARGET_HELDOUT_SCORE_COL,
        "rows_eval": int(len(df)),
        "positive_count": int(np.sum(y == 1)),
        "feature_count": int(len(feature_columns)),
        "selected_C": selected_c,
        "candidate_grid": candidates,
        "selected_current_fit": selected["current_fit"],
        "selected_target_heldout": selected["target_heldout"],
        "selected_target_heldout_positive_rank_rows": heldout_positive_rank_rows,
        "selected_target_heldout_target_metric_rows": heldout_target_metric_rows,
        "selected_target_heldout_worst_positive_rank": max(
            (int(row["positive_target_rank"]) for row in heldout_positive_rank_rows),
            default=None,
        ),
        "selected_target_heldout_top20_positive_count": sum(
            1 for row in heldout_positive_rank_rows if row["in_top20"]
        ),
        "selected_target_heldout_lowest_target_pr_auc": min(
            (
                float(row["ranking_pr_auc"])
                for row in heldout_target_metric_rows
                if row.get("ranking_pr_auc") is not None and math.isfinite(float(row["ranking_pr_auc"]))
            ),
            default=None,
        ),
        "current_fit_closure_gate_pass": current_pass,
        "target_heldout_closure_gate_pass": heldout_pass,
        "feature_columns": feature_columns,
        "top_standardized_coefficients": _standardized_coefficients(models[selected_c], feature_columns)[:50],
        "forbidden_feature_patterns": list(FORBIDDEN_PATTERNS),
        "claim_boundary": (
            "Diagnostic current-fit closure probe only. It fits the current evaluated rows using labels, excludes "
            "identifier/target/reference/rank/replica/previous-supervised-output columns, and can demonstrate "
            "feature separability. It is not external beta evidence, not an independent repeat, not a target-heldout "
            "closure if target_heldout_closure_gate_pass is false, and not a broad-GPCR claim."
        ),
        "diagnostic_current_fit_used_labels": True,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "threshold_relaxation_allowed": False,
        "next_required_step": (
            "Convert only if an independent/target-heldout replay also clears CI-low, top20, decoy separation, "
            "and anchor-margin gates; otherwise keep as an upper-bound diagnostic."
        ),
    }
    return output_scores, payload


def write_outputs(
    scores_out: pd.DataFrame,
    payload: dict[str, Any],
    *,
    out_scores_csv: str | Path,
    out_json: str | Path,
    out_md: str | Path,
) -> None:
    scores_path = _resolve(out_scores_csv)
    json_path = _resolve(out_json)
    md_path = _resolve(out_md)
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    if not scores_out.empty:
        scores_out.to_csv(scores_path, index=False)
    payload = dict(payload)
    payload["out_scores_csv"] = str(scores_path)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    selected = payload.get("selected_current_fit") or {}
    heldout = payload.get("selected_target_heldout") or {}
    lines = [
        "# GPCR Hard-Decoy Current-Fit Closure Probe",
        "",
        f"- status: `{payload.get('status')}`",
        f"- rows_eval: `{payload.get('rows_eval')}`",
        f"- positive_count: `{payload.get('positive_count')}`",
        f"- selected_C: `{payload.get('selected_C')}`",
        f"- current_fit_closure_gate_pass: `{str(payload.get('current_fit_closure_gate_pass')).lower()}`",
        f"- target_heldout_closure_gate_pass: `{str(payload.get('target_heldout_closure_gate_pass')).lower()}`",
        f"- current_fit_pr_auc_ci_low: `{selected.get('ranking_pr_auc_ci_low')}`",
        f"- current_fit_top20_hit_rate: `{selected.get('top20_hit_rate')}`",
        f"- target_heldout_pr_auc_ci_low: `{heldout.get('ranking_pr_auc_ci_low')}`",
        f"- target_heldout_top20_hit_rate: `{heldout.get('top20_hit_rate')}`",
        f"- target_heldout_worst_positive_rank: `{payload.get('selected_target_heldout_worst_positive_rank')}`",
        f"- target_heldout_top20_positive_count: `{payload.get('selected_target_heldout_top20_positive_count')}`",
        f"- target_heldout_score_col: `{payload.get('target_heldout_score_col')}`",
        f"- score_col: `{payload.get('score_col')}`",
        f"- out_scores_csv: `{scores_path}`",
        "",
        "## Claim Boundary",
        "",
        str(payload.get("claim_boundary")),
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores-csv", default=DEFAULT_SCORES_CSV)
    parser.add_argument("--labels-csv", default=DEFAULT_LABELS_CSV)
    parser.add_argument("--split-csv", default=DEFAULT_SPLIT_CSV)
    parser.add_argument("--c-grid", default="0.003,0.01,0.03,0.1,0.3,1.0")
    parser.add_argument("--min-finite-ratio", type=float, default=0.95)
    parser.add_argument("--bootstrap-n", type=int, default=400)
    parser.add_argument("--bootstrap-seed", type=int, default=7)
    parser.add_argument("--out-scores-csv", default=DEFAULT_OUT_SCORES_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    c_grid = [float(item) for item in str(args.c_grid).split(",") if str(item).strip()]
    scores_out, payload = build_probe(
        scores_csv=args.scores_csv,
        labels_csv=args.labels_csv,
        split_csv=args.split_csv,
        c_grid=c_grid,
        min_finite_ratio=float(args.min_finite_ratio),
        bootstrap_n=int(args.bootstrap_n),
        bootstrap_seed=int(args.bootstrap_seed),
    )
    write_outputs(
        scores_out,
        payload,
        out_scores_csv=args.out_scores_csv,
        out_json=args.out_json,
        out_md=args.out_md,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
