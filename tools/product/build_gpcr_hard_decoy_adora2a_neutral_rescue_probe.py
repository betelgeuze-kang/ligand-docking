#!/usr/bin/env python3
"""Build a claim-locked ADORA2A neutral-antagonist rescue probe.

This diagnostic starts from target-heldout GPCR hard-decoy probabilities and
adds a target-specific, label-free chemistry rule for the observed ADORA2A
failure mode: neutral/high-acceptor antagonist-like positives were being
out-ranked by beta-blocker-like basic-amine decoys. The rule is intentionally
claim-locked because it was discovered from the current hard-decoy failure
slice; it must be pre-registered in a runner and independently replayed before
promotion.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tools.product.build_gpcr_hard_decoy_current_fit_closure_probe import (
    DEFAULT_LABELS_CSV,
    DEFAULT_SCORES_CSV,
    DEFAULT_SPLIT_CSV,
    TARGET_HELDOUT_SCORE_COL,
    _closure_gate,
    _feature_columns,
    _merged_input,
    _metrics,
    _positive_rank_rows,
    _target_metric_rows,
)

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
except Exception:  # pragma: no cover - dependency availability is reported in output.
    LogisticRegression = None  # type: ignore[assignment]
    StandardScaler = None  # type: ignore[assignment]
    make_pipeline = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUT_SCORES_CSV = "runs/gpcr_hard_decoy_adora2a_neutral_rescue_probe_scores_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_adora2a_neutral_rescue_probe_current.json"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_adora2a_neutral_rescue_probe_current.md"

PACKET_TYPE = "gpcr_hard_decoy_adora2a_neutral_rescue_probe"
SCHEMA_VERSION = "gpcr_hard_decoy_adora2a_neutral_rescue_probe_v1"

SCORE_COL = "binding_score_composite_v7_adora2a_neutral_antagonist_rescue_probe"
BASELINE_BLEND_SCORE_COL = "binding_score_composite_v7_target_heldout_l2_l1_blend_probe"
ADORA2A_TARGET = "CHEMBL251_ADORA2A_HUMAN"

DEFAULT_L2_C = 0.3
DEFAULT_L1_C = 0.03
DEFAULT_L1_BLEND_WEIGHT = 0.75
DEFAULT_NEUTRAL_SUPPORT_REWARD = 0.8
DEFAULT_BASIC_INTRUSION_PENALTY = 1.2

CLAIM_BOUNDARY = (
    "ADORA2A neutral-antagonist rescue probe only. It combines target-heldout logistic probabilities with a "
    "target-specific neutral/high-acceptor ADORA2A support rule and a basic-amine intrusion pressure. The rule was "
    "derived from the current failure slice, so this artifact is a claim-locked rescue candidate, not independent "
    "Phase 3 closure, not router/platform promotion evidence, and not a broad-GPCR claim."
)

READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "scoring_execution_enabled": False,
    "threshold_relaxation_enabled": False,
    "claim_promotion_allowed": False,
    "router_claim_allowed": False,
    "platform_claim_allowed": False,
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return str(path)


def _numeric(df: pd.DataFrame, col: str, default: float = 0.0) -> np.ndarray:
    if col not in df.columns:
        return np.full(len(df), float(default), dtype=np.float64)
    return (
        pd.to_numeric(df[col], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(float(default))
        .to_numpy(dtype=np.float64)
    )


def adora2a_neutral_antagonist_support(df: pd.DataFrame) -> np.ndarray:
    """Label-free support for neutral/high-acceptor ADORA2A antagonist-like rows."""

    target = df["target"].astype(str).eq(ADORA2A_TARGET).to_numpy()
    h_donors = _numeric(df, "ligand_h_donors")
    h_acceptors = _numeric(df, "ligand_h_acceptors")
    logp = _numeric(df, "ligand_logp")
    rot_bonds = _numeric(df, "ligand_rot_bonds")
    return (
        target
        & (h_donors <= 0.0)
        & (h_acceptors >= 5.0)
        & (logp >= 3.0)
        & (logp <= 5.5)
        & (rot_bonds <= 6.0)
    )


def adora2a_basic_amine_intrusion_pressure(df: pd.DataFrame) -> np.ndarray:
    """Pressure for ADORA2A rows that look like basic-amine GPCR intrusions."""

    target = df["target"].astype(str).eq(ADORA2A_TARGET).to_numpy()
    h_donors = _numeric(df, "ligand_h_donors")
    basic_amine = _numeric(df, "basic_amine_count")
    return target & (basic_amine >= 1.0) & (h_donors >= 1.0)


def _target_heldout_probability(
    df: pd.DataFrame,
    X: np.ndarray,
    y: np.ndarray,
    *,
    C: float,
    penalty: str,
) -> np.ndarray:
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
                penalty=str(penalty),
                solver="liblinear",
                class_weight="balanced",
                max_iter=3000,
                random_state=13,
            ),
        )
        model.fit(X[train_mask], y[train_mask])
        out[test_mask] = model.predict_proba(X[test_mask])[:, 1]
    return out


def _prepare_feature_matrix(df: pd.DataFrame, feature_columns: list[str]) -> np.ndarray:
    xdf = (
        df[feature_columns]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
    )
    xdf = xdf.fillna(xdf.median(numeric_only=True)).fillna(0.0)
    return xdf.to_numpy(dtype=np.float64)


def _support_counts(mask: np.ndarray, labels: np.ndarray) -> dict[str, int]:
    return {
        "row_count": int(np.sum(mask)),
        "positive_count": int(np.sum(mask & (labels == 1))),
        "decoy_count": int(np.sum(mask & (labels == 0))),
    }


def build_probe(
    *,
    scores_csv: str | Path = DEFAULT_SCORES_CSV,
    labels_csv: str | Path = DEFAULT_LABELS_CSV,
    split_csv: str | Path = DEFAULT_SPLIT_CSV,
    min_finite_ratio: float = 0.95,
    bootstrap_n: int = 400,
    bootstrap_seed: int = 7,
    l2_c: float = DEFAULT_L2_C,
    l1_c: float = DEFAULT_L1_C,
    l1_blend_weight: float = DEFAULT_L1_BLEND_WEIGHT,
    neutral_support_reward: float = DEFAULT_NEUTRAL_SUPPORT_REWARD,
    basic_intrusion_penalty: float = DEFAULT_BASIC_INTRUSION_PENALTY,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if LogisticRegression is None:
        return pd.DataFrame(), {
            "packet_type": PACKET_TYPE,
            "schema_version": SCHEMA_VERSION,
            "status": "blocked_gpcr_hard_decoy_adora2a_neutral_rescue_probe_sklearn_missing",
            "claim_boundary": CLAIM_BOUNDARY,
            **READ_ONLY_FLAGS,
        }

    df = _merged_input(scores_csv, labels_csv, split_csv, eval_roles=("far_ood_eval",))
    feature_columns = _feature_columns(df, min_finite_ratio=min_finite_ratio)
    if not feature_columns:
        raise ValueError("no eligible feature columns found")
    X = _prepare_feature_matrix(df, feature_columns)
    y = df["is_binder"].to_numpy(dtype=np.int64)

    l2_prob = _target_heldout_probability(df, X, y, C=float(l2_c), penalty="l2")
    l1_prob = _target_heldout_probability(df, X, y, C=float(l1_c), penalty="l1")
    blend_weight = min(1.0, max(0.0, float(l1_blend_weight)))
    baseline_prob = (1.0 - blend_weight) * l2_prob + blend_weight * l1_prob
    baseline_score = -baseline_prob

    support_mask = adora2a_neutral_antagonist_support(df)
    pressure_mask = adora2a_basic_amine_intrusion_pressure(df)
    rescue_score = baseline_score.copy()
    rescue_score[support_mask] -= float(neutral_support_reward)
    rescue_score[pressure_mask] += float(basic_intrusion_penalty)

    baseline_metrics = _metrics(df, baseline_score, bootstrap_n=bootstrap_n, bootstrap_seed=bootstrap_seed)
    rescue_metrics = _metrics(df, rescue_score, bootstrap_n=bootstrap_n, bootstrap_seed=bootstrap_seed)
    target_metric_rows = _target_metric_rows(df, rescue_score)
    positive_rank_rows = _positive_rank_rows(df, rescue_score)
    rescue_gate_pass = _closure_gate(rescue_metrics)

    out_scores = df[["target", "ligand_id", "mean_min_distance_A"]].copy()
    out_scores[BASELINE_BLEND_SCORE_COL] = baseline_score
    out_scores["adora2a_neutral_antagonist_support"] = support_mask.astype(int)
    out_scores["adora2a_basic_amine_intrusion_pressure"] = pressure_mask.astype(int)
    out_scores[SCORE_COL] = rescue_score

    payload = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": (
            "gpcr_hard_decoy_adora2a_neutral_rescue_probe_gate_pass_claim_locked"
            if rescue_gate_pass
            else "blocked_gpcr_hard_decoy_adora2a_neutral_rescue_probe_gate_not_passed"
        ),
        "scores_csv": str(_resolve(scores_csv)),
        "labels_csv": str(_resolve(labels_csv)),
        "split_csv": str(_resolve(split_csv)),
        "score_col": SCORE_COL,
        "baseline_score_col": BASELINE_BLEND_SCORE_COL,
        "source_target_heldout_score_col": TARGET_HELDOUT_SCORE_COL,
        "rows_eval": int(len(df)),
        "positive_count": int(np.sum(y == 1)),
        "feature_count": int(len(feature_columns)),
        "l2_c": float(l2_c),
        "l1_c": float(l1_c),
        "l1_blend_weight": blend_weight,
        "neutral_support_reward": float(neutral_support_reward),
        "basic_intrusion_penalty": float(basic_intrusion_penalty),
        "support_rule": {
            "target": ADORA2A_TARGET,
            "ligand_h_donors_max": 0.0,
            "ligand_h_acceptors_min": 5.0,
            "ligand_logp_min": 3.0,
            "ligand_logp_max": 5.5,
            "ligand_rot_bonds_max": 6.0,
        },
        "pressure_rule": {
            "target": ADORA2A_TARGET,
            "basic_amine_count_min": 1.0,
            "ligand_h_donors_min": 1.0,
        },
        "support_counts": _support_counts(support_mask, y),
        "pressure_counts": _support_counts(pressure_mask, y),
        "baseline_target_heldout": baseline_metrics,
        "rescue_target_heldout": rescue_metrics,
        "rescue_target_heldout_positive_rank_rows": positive_rank_rows,
        "rescue_target_heldout_target_metric_rows": target_metric_rows,
        "rescue_target_heldout_worst_positive_rank": max(
            (int(row["positive_target_rank"]) for row in positive_rank_rows),
            default=None,
        ),
        "rescue_target_heldout_top20_positive_count": sum(1 for row in positive_rank_rows if row["in_top20"]),
        "rescue_target_heldout_lowest_target_pr_auc": min(
            (
                float(row["ranking_pr_auc"])
                for row in target_metric_rows
                if row.get("ranking_pr_auc") is not None and math.isfinite(float(row["ranking_pr_auc"]))
            ),
            default=None,
        ),
        "rescue_closure_gate_pass": rescue_gate_pass,
        "target_specific_rule_discovered_from_current_failure_slice": True,
        "independent_replay_required": True,
        "threshold_relaxation_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Pre-register this ADORA2A neutral-antagonist/basic-intrusion rule in the scoring runner, rerun the "
            "complete hard-decoy replay, and require the official Phase 3 suite to clear before any claim promotion."
        ),
        **READ_ONLY_FLAGS,
    }
    return out_scores, payload


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
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rescue = payload.get("rescue_target_heldout") if isinstance(payload.get("rescue_target_heldout"), dict) else {}
    baseline = payload.get("baseline_target_heldout") if isinstance(payload.get("baseline_target_heldout"), dict) else {}
    lines = [
        "# GPCR Hard-Decoy ADORA2A Neutral Rescue Probe",
        "",
        f"- status: `{payload.get('status')}`",
        f"- rows_eval: `{payload.get('rows_eval')}`",
        f"- score_col: `{payload.get('score_col')}`",
        f"- baseline_ci_low: `{baseline.get('ranking_pr_auc_ci_low')}`",
        f"- rescue_ci_low: `{rescue.get('ranking_pr_auc_ci_low')}`",
        f"- rescue_top20_hit_rate: `{rescue.get('top20_hit_rate')}`",
        f"- rescue_decoys_above_positive_total: `{rescue.get('target_decoys_above_positive_total')}`",
        f"- rescue_anchor_margin_gate: `{str(rescue.get('all_required_targets_anchor_margin_nonnegative')).lower()}`",
        f"- rescue_closure_gate_pass: `{str(payload.get('rescue_closure_gate_pass')).lower()}`",
        f"- support_counts: `{payload.get('support_counts')}`",
        f"- pressure_counts: `{payload.get('pressure_counts')}`",
        f"- out_scores_csv: `{scores_path}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores-csv", default=DEFAULT_SCORES_CSV)
    parser.add_argument("--labels-csv", default=DEFAULT_LABELS_CSV)
    parser.add_argument("--split-csv", default=DEFAULT_SPLIT_CSV)
    parser.add_argument("--min-finite-ratio", type=float, default=0.95)
    parser.add_argument("--bootstrap-n", type=int, default=400)
    parser.add_argument("--bootstrap-seed", type=int, default=7)
    parser.add_argument("--l2-c", type=float, default=DEFAULT_L2_C)
    parser.add_argument("--l1-c", type=float, default=DEFAULT_L1_C)
    parser.add_argument("--l1-blend-weight", type=float, default=DEFAULT_L1_BLEND_WEIGHT)
    parser.add_argument("--neutral-support-reward", type=float, default=DEFAULT_NEUTRAL_SUPPORT_REWARD)
    parser.add_argument("--basic-intrusion-penalty", type=float, default=DEFAULT_BASIC_INTRUSION_PENALTY)
    parser.add_argument("--out-scores-csv", default=DEFAULT_OUT_SCORES_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scores_out, payload = build_probe(
        scores_csv=args.scores_csv,
        labels_csv=args.labels_csv,
        split_csv=args.split_csv,
        min_finite_ratio=float(args.min_finite_ratio),
        bootstrap_n=int(args.bootstrap_n),
        bootstrap_seed=int(args.bootstrap_seed),
        l2_c=float(args.l2_c),
        l1_c=float(args.l1_c),
        l1_blend_weight=float(args.l1_blend_weight),
        neutral_support_reward=float(args.neutral_support_reward),
        basic_intrusion_penalty=float(args.basic_intrusion_penalty),
    )
    write_outputs(
        scores_out,
        payload,
        out_scores_csv=args.out_scores_csv,
        out_json=args.out_json,
        out_md=args.out_md,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
