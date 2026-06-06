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

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_STAGE3_SCORES_CSV = (
    "runs/external_validation_2026-05-17_gpcr_a1_coverage_v2_beta_rescue_fast_r1_"
    "set1_core_blind_gpcr_core_full_p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_FEATURE_CACHE_CSV = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_coverage_v2_adaptive_current.csv"
DEFAULT_OUT_SCORES_CSV = "runs/gpcr_coverage_v2_adaptive_rank_rescue_shadow_replay_scores_current.csv"
DEFAULT_OUT_SUMMARY_JSON = "runs/gpcr_coverage_v2_adaptive_rank_rescue_shadow_replay_summary_current.json"
DEFAULT_OUT_SUMMARY_MD = "runs/gpcr_coverage_v2_adaptive_rank_rescue_shadow_replay_summary_current.md"
DEFAULT_WEIGHT_SPEC_JSON = ""

SCORE_COL = "binding_score_composite_v7_coverage_v2_adaptive_rank_rescue_shadow"
BASE_SCORE_CANDIDATES = (
    "binding_score_composite_v7_residual_active",
    "binding_score_composite_v7",
    "base_score",
)

FORBIDDEN_SCORE_FEATURES = {
    "target",
    "ligand_id",
    "is_binder",
    "reference_binding_kcal_mol",
    "reference_binding_kcal",
    "rank",
    "export_rank",
    "role",
    "split",
    "source",
}

REWARD_WEIGHTS = {
    "ligand_affinity_hint": 6.274560058825278,
    "ligand_h_acceptors": 2.22495505069016,
    "pose_preservation_support": 0.9326420224168248,
    "contact_fraction": 0.9912018289438151,
    "stability_score": 1.946460605087315,
    "v14_cationic_anchor_occupancy_support": 0.30892732048150673,
    "multipolar_basic_pressure": 0.43522840629393444,
    "mw_300_550_gate": 0.9772214161390386,
    "mw_high_gate": 1.1602925789980918,
    "support_high_gate": 0.48032681064274296,
    "cationic_high_gate": 1.0650353664888512,
    "rot_mid_gate": 0.5567597042529604,
}

PENALTY_WEIGHTS = {
    "ligand_rot_bonds": 0.7392613348767578,
    "pose_distortion_pressure": 0.9631738967934546,
}

ACTIVE_SCORE_WEIGHT = 0.2


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _numeric(df: pd.DataFrame, col: str, fill: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.full(len(df), float(fill)), index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce").fillna(float(fill)).astype(float)


def _zscore(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0.0).astype(float)
    std = float(values.std(ddof=0))
    if not math.isfinite(std) or std <= 1e-12:
        std = 1.0
    return (values - float(values.mean())) / std


def _merge_feature_cache(df: pd.DataFrame, feature_cache_csv: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    cache_path = _resolve(feature_cache_csv)
    if not cache_path.exists():
        raise FileNotFoundError(f"feature cache CSV not found: {cache_path}")
    cache_df = pd.read_csv(cache_path)
    required = {"target", "ligand_id"}
    if not required.issubset(cache_df.columns):
        raise ValueError("feature cache CSV must include target and ligand_id columns")
    feature_cols = [col for col in cache_df.columns if col not in required]
    overlay_cols = [col for col in feature_cols if col in df.columns]
    merge_base = df.drop(columns=overlay_cols) if overlay_cols else df
    merged = merge_base.merge(cache_df[["target", "ligand_id", *feature_cols]], on=["target", "ligand_id"], how="left")
    matched = int(merged[feature_cols].notna().any(axis=1).sum()) if feature_cols else 0
    status_counts = {}
    if "feature_cache_status" in merged.columns:
        status_counts = {
            str(key): int(value)
            for key, value in merged["feature_cache_status"].fillna("missing").value_counts().sort_index().items()
        }
    return merged, {
        "enabled": True,
        "feature_cache_csv": str(cache_path),
        "cache_row_count": int(len(cache_df)),
        "matched_row_count": matched,
        "overlay_replaced_column_count": int(len(overlay_cols)),
        "overlay_replaced_columns": overlay_cols,
        "feature_cache_status_counts": status_counts,
    }


def _base_score_col(df: pd.DataFrame) -> str:
    for col in BASE_SCORE_CANDIDATES:
        if col in df.columns:
            return col
    raise ValueError(f"no base score column found; tried {', '.join(BASE_SCORE_CANDIDATES)}")


def _feature_series(df: pd.DataFrame, feature: str) -> pd.Series:
    ligand_mw = _numeric(df, "ligand_mw")
    rot = _numeric(df, "ligand_rot_bonds")
    hba = _numeric(df, "ligand_h_acceptors")
    basic = _numeric(df, "basic_amine_count")
    affinity = _numeric(df, "ligand_affinity_hint")
    pose = _numeric(df, "pose_preservation_support")
    support = _numeric(df, "label_free_support_pressure")
    cationic = _numeric(df, "v14_cationic_anchor_occupancy_support")
    dist = _numeric(df, "mean_min_distance_A")
    logp = _numeric(df, "ligand_logp")
    if feature == "mw_300_550_gate":
        return ((ligand_mw - 300.0) / 220.0).clip(lower=0.0, upper=1.0)
    if feature == "mw_high_gate":
        return (ligand_mw >= 300.0).astype(float)
    if feature == "hba_ge4_gate":
        return (hba >= 4.0).astype(float)
    if feature == "hba_ge5_gate":
        return (hba >= 5.0).astype(float)
    if feature == "basic_ge1_gate":
        return (basic >= 1.0).astype(float)
    if feature == "basic_ge2_gate":
        return (basic >= 2.0).astype(float)
    if feature == "aff_high_gate":
        return (affinity >= 0.55).astype(float)
    if feature == "pose_any_gate":
        return (pose > 0.0).astype(float)
    if feature == "pose_high_gate":
        return (pose >= 0.6).astype(float)
    if feature == "support_high_gate":
        return (support >= 0.5).astype(float)
    if feature == "cationic_high_gate":
        return (cationic >= 0.5).astype(float)
    if feature == "dist_3p5_5p5_gate":
        return ((dist >= 3.5) & (dist <= 5.5)).astype(float)
    if feature == "logp_mid_gate":
        return ((logp >= 1.5) & (logp <= 4.5)).astype(float)
    if feature == "rot_mid_gate":
        return ((rot >= 2.0) & (rot <= 10.0)).astype(float)
    return _numeric(df, feature)


def _default_weight_spec(base_score_col: str) -> dict[str, Any]:
    return {
        "preset": "coverage_v2_adaptive_rank_rescue_search_v1",
        "mode": "reward_penalty_zscore",
        "active_score_weight": ACTIVE_SCORE_WEIGHT,
        "base_score_col": base_score_col,
        "reward_weights": dict(REWARD_WEIGHTS),
        "penalty_weights": dict(PENALTY_WEIGHTS),
        "diagnostic_weight_search_used_labels": True,
        "weight_selection_not_claim_authorizing": True,
    }


def _load_weight_spec(weight_spec_json: str | Path, base_score_col: str) -> tuple[dict[str, Any], str]:
    spec_src = str(weight_spec_json or "").strip()
    if not spec_src:
        return _default_weight_spec(base_score_col), ""
    spec_path = _resolve(spec_src)
    if not spec_path.exists():
        raise FileNotFoundError(f"weight spec JSON not found: {spec_path}")
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"weight spec JSON must contain an object: {spec_path}")
    return payload, str(spec_path)


def _score_features_used(weight_spec: dict[str, Any], base_score_col: str) -> list[str]:
    if isinstance(weight_spec.get("linear_weights"), dict):
        return list(weight_spec["linear_weights"].keys())
    features = [str(weight_spec.get("base_score_col") or base_score_col)]
    features.extend((weight_spec.get("reward_weights") or {}).keys())
    features.extend((weight_spec.get("penalty_weights") or {}).keys())
    return features


def _assert_feature_policy(features: list[str]) -> None:
    forbidden = []
    for feature in features:
        lowered = str(feature).strip().lower()
        if lowered in FORBIDDEN_SCORE_FEATURES:
            forbidden.append(feature)
            continue
        if "reference_binding" in lowered or lowered.endswith("_rank") or "_rank_" in lowered:
            forbidden.append(feature)
            continue
        if lowered in {"target", "ligand_id", "is_binder"}:
            forbidden.append(feature)
    if forbidden:
        raise ValueError(f"forbidden score feature(s) used: {', '.join(sorted(set(forbidden)))}")


def _apply_weight_spec(
    replay_df: pd.DataFrame,
    *,
    weight_spec: dict[str, Any],
    base_score_col: str,
) -> tuple[pd.Series, list[dict[str, Any]]]:
    mode = str(weight_spec.get("mode") or "").strip()
    terms: list[dict[str, Any]] = []
    if isinstance(weight_spec.get("linear_weights"), dict):
        score = pd.Series(np.zeros(len(replay_df)), index=replay_df.index, dtype=float)
        for feature, coefficient in weight_spec["linear_weights"].items():
            coef = float(coefficient)
            score = score - coef * _zscore(_feature_series(replay_df, str(feature)))
            terms.append(
                {
                    "feature": str(feature),
                    "binder_coefficient": coef,
                    "score_contribution": "negative_coefficient_times_zscore",
                }
            )
        return score, terms

    reward_weights = {
        str(feature): float(weight)
        for feature, weight in (weight_spec.get("reward_weights") or {}).items()
    }
    penalty_weights = {
        str(feature): float(weight)
        for feature, weight in (weight_spec.get("penalty_weights") or {}).items()
    }
    active_weight = float(weight_spec.get("active_score_weight", ACTIVE_SCORE_WEIGHT) or 0.0)
    base_col = str(weight_spec.get("base_score_col") or base_score_col)
    score = active_weight * _zscore(_numeric(replay_df, base_col))
    terms.append({"feature": base_col, "weight": active_weight, "direction": "base_score_prior"})
    for feature, weight in reward_weights.items():
        score = score - weight * _zscore(_feature_series(replay_df, feature))
        terms.append({"feature": feature, "weight": weight, "direction": "reward_lower_score"})
    for feature, weight in penalty_weights.items():
        score = score + weight * _zscore(_feature_series(replay_df, feature))
        terms.append({"feature": feature, "weight": weight, "direction": "penalty_raise_score"})
    if mode and mode != "reward_penalty_zscore":
        terms.append({"feature": "__weight_spec_mode__", "value": mode, "direction": "metadata"})
    return score, terms


def build_replay(
    *,
    stage3_scores_csv: str | Path = DEFAULT_STAGE3_SCORES_CSV,
    feature_cache_csv: str | Path = DEFAULT_FEATURE_CACHE_CSV,
    weight_spec_json: str | Path = DEFAULT_WEIGHT_SPEC_JSON,
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

    replay_df, feature_cache_summary = _merge_feature_cache(df, feature_cache_csv)
    base_col = _base_score_col(replay_df)
    weight_spec, weight_spec_path = _load_weight_spec(weight_spec_json, base_col)
    used_features = _score_features_used(weight_spec, base_col)
    _assert_feature_policy(used_features)

    score, term_summaries = _apply_weight_spec(replay_df, weight_spec=weight_spec, base_score_col=base_col)

    replay_df[SCORE_COL] = score.astype(float)
    replay_df["binding_score_composite_v7_residual_active"] = replay_df[SCORE_COL]
    finite = pd.to_numeric(replay_df[SCORE_COL], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "ready_for_evaluation_claim_locked",
        "input_scores_csv": str(scores_path),
        "feature_cache_csv": str(_resolve(feature_cache_csv)),
        "weight_spec_json": weight_spec_path,
        "weight_spec_preset": weight_spec.get("preset", "coverage_v2_adaptive_rank_rescue_search_v1"),
        "weight_spec_mode": weight_spec.get("mode", "reward_penalty_zscore"),
        "input_rows": int(len(replay_df)),
        "score_col": SCORE_COL,
        "probability_score_col": SCORE_COL,
        "base_score_col": base_col,
        "score_finite_row_count": int(len(finite)),
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "broad_gpcr_claim_allowed": False,
        "threshold_relaxation_allowed": False,
        "fake_pass_allowed": False,
        "score_feature_policy_pass": True,
        "forbidden_score_features": sorted(FORBIDDEN_SCORE_FEATURES),
        "score_features_used": used_features,
        "diagnostic_weight_search_used_labels": bool(weight_spec.get("diagnostic_weight_search_used_labels", True)),
        "weight_selection_not_claim_authorizing": bool(weight_spec.get("weight_selection_not_claim_authorizing", True)),
        "next_required_step": (
            "Evaluate this shadow score, then rerun a new independent GPCR A1 repeat before any claim promotion. "
            "Current artifact is a claim-locked rescue candidate, not a delivery or broad GPCR parity claim."
        ),
    }
    payload = {
        "packet_type": "gpcr_coverage_v2_adaptive_rank_rescue_shadow_replay",
        "summary": summary,
        "feature_cache": feature_cache_summary,
        "linear_score_terms": term_summaries,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "broad_gpcr_claim_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "requires_independent_repeat_before_scorecard_claim": True,
        },
    }
    return replay_df, payload


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    cache = payload["feature_cache"]
    return "\n".join(
        [
            "# GPCR Coverage V2 Adaptive Rank Rescue Shadow Replay",
            "",
            "## Summary",
            "",
            f"- status: `{summary['status']}`",
            f"- input_rows: `{summary['input_rows']}`",
            f"- score_col: `{summary['score_col']}`",
            f"- base_score_col: `{summary['base_score_col']}`",
            f"- feature_cache_matched_row_count: `{cache['matched_row_count']}`",
            f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
            f"- scorer_apply_allowed: `{str(summary['scorer_apply_allowed']).lower()}`",
            f"- diagnostic_weight_search_used_labels: `{str(summary['diagnostic_weight_search_used_labels']).lower()}`",
            "",
            "## Claim Boundary",
            "",
            "- This is a claim-locked shadow candidate.",
            "- It must not be used as a delivery verdict, router promotion, or broad GPCR parity claim.",
            "- A fresh independent repeat is required before any scorecard claim promotion.",
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
        ]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a claim-locked GPCR coverage-v2 adaptive rank rescue score replay.")
    parser.add_argument("--stage3-scores-csv", default=DEFAULT_STAGE3_SCORES_CSV)
    parser.add_argument("--feature-cache-csv", default=DEFAULT_FEATURE_CACHE_CSV)
    parser.add_argument("--weight-spec-json", default=DEFAULT_WEIGHT_SPEC_JSON)
    parser.add_argument("--out-scores-csv", default=DEFAULT_OUT_SCORES_CSV)
    parser.add_argument("--out-summary-json", default=DEFAULT_OUT_SUMMARY_JSON)
    parser.add_argument("--out-summary-md", default=DEFAULT_OUT_SUMMARY_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    replay_df, payload = build_replay(
        stage3_scores_csv=args.stage3_scores_csv,
        feature_cache_csv=args.feature_cache_csv,
        weight_spec_json=args.weight_spec_json,
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
