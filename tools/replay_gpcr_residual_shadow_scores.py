#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tools import run_ligand_backmapping_scoring as scoring

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT_SCORES_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_SPEC_JSON = "runs/gpcr_residual_prototype_spec_class_a_motif_shadow_v6.json"
DEFAULT_OUT_SCORES_CSV = "runs/gpcr_class_a_motif_v6_shadow_replay_scores_current.csv"
DEFAULT_OUT_SUMMARY_JSON = "runs/gpcr_class_a_motif_v6_shadow_replay_summary_current.json"
DEFAULT_OUT_SUMMARY_MD = "runs/gpcr_class_a_motif_v6_shadow_replay_summary_current.md"

NUMERIC_COLUMNS = [
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "mean_min_distance_A",
    "stability_score",
    "contact_fraction",
    "binding_energy_mmpbsa_std",
    "ligand_affinity_hint",
    "ligand_onsps_norm",
    "ligand_mw",
    "ligand_logp",
    "ligand_rot_bonds",
    "ligand_h_donors",
    "ligand_h_acceptors",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _z(df: pd.DataFrame, col: str, scaling: dict[str, Any]) -> pd.Series:
    if col not in df.columns:
        df[col] = 0.0
    return scoring._zscore_with_reference(df, col, scaling)


def _ensure_base_scores(df: pd.DataFrame, scaling: dict[str, Any]) -> dict[str, Any]:
    for col in NUMERIC_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce")

    z_e = _z(df, "binding_energy_mmpbsa_kcal_mol_proxy", scaling)
    z_d = _z(df, "mean_min_distance_A", scaling)
    z_s = _z(df, "stability_score", scaling)
    z_c = _z(df, "contact_fraction", scaling)
    z_std = _z(df, "binding_energy_mmpbsa_std", scaling)
    z_mw = _z(df, "ligand_mw", scaling)
    z_logp = _z(df, "ligand_logp", scaling)
    z_rot = _z(df, "ligand_rot_bonds", scaling)
    z_hd = _z(df, "ligand_h_donors", scaling)
    z_ha = _z(df, "ligand_h_acceptors", scaling)
    z_aff = _z(df, "ligand_affinity_hint", scaling)
    z_onsps = _z(df, "ligand_onsps_norm", scaling)

    dist = pd.to_numeric(df["mean_min_distance_A"], errors="coerce")
    clash_thr = 2.22
    clash_scale = 0.25
    clash_penalty = np.where(
        np.isfinite(dist.to_numpy()) & (dist.to_numpy() < clash_thr),
        np.square((clash_thr - dist.to_numpy()) / clash_scale),
        0.0,
    )

    df["binding_score_composite_v2"] = z_e + 0.75 * z_d - 0.05 * z_s - 0.85 * z_c + 0.15 * z_std
    df["binding_score_composite_v3"] = (
        0.95 * z_e + 0.30 * z_d - 0.05 * z_s - 1.40 * z_c + 0.02 * z_std + 0.05 * clash_penalty
    )
    df["binding_score_composite_v4"] = (
        0.95 * z_e
        + 0.30 * z_d
        - 0.05 * z_s
        - 0.80 * z_c
        + 0.02 * z_std
        - 2.00 * z_aff
        - 1.00 * z_onsps
        + 0.05 * clash_penalty
    )
    df["binding_score_composite_v6"] = (
        0.95 * z_e
        + 0.30 * z_d
        - 0.05 * z_s
        - 0.80 * z_c
        + 0.02 * z_std
        - 2.20 * z_aff
        - 1.00 * z_onsps
        - 0.18 * z_mw
        - 0.22 * z_hd
        - 0.14 * z_ha
        - 0.10 * z_rot
        + 0.05 * clash_penalty
    )
    df["binding_score_composite_v7"] = (
        0.95 * z_e
        + 0.00 * z_d
        - 0.05 * z_s
        - 0.15 * z_c
        + 0.02 * z_std
        - 1.20 * z_aff
        - 1.00 * z_onsps
        - 0.00 * z_mw
        - 1.20 * z_hd
        - 1.00 * z_ha
        - 0.40 * z_rot
        + 0.24 * z_logp
        + 0.05 * clash_penalty
    )
    return {
        "z_e": z_e,
        "z_d": z_d,
        "z_s": z_s,
        "z_c": z_c,
        "z_aff": z_aff,
        "z_logp": z_logp,
        "z_rot": z_rot,
        "z_hd": z_hd,
        "z_ha": z_ha,
        "z_std": z_std,
    }


def _merge_feature_cache(df: pd.DataFrame, feature_cache_csv: str | Path = "") -> tuple[pd.DataFrame, dict[str, Any]]:
    cache_src = str(feature_cache_csv or "").strip()
    if not cache_src:
        return df, {
            "enabled": False,
            "feature_cache_csv": "",
            "matched_row_count": 0,
            "merged_feature_columns": [],
        }
    cache_path = _resolve(cache_src)
    if not cache_path.exists():
        raise FileNotFoundError(f"feature cache CSV not found: {cache_path}")
    cache_df = pd.read_csv(cache_path)
    required = {"target", "ligand_id"}
    if not required.issubset(set(cache_df.columns)):
        raise ValueError("feature cache CSV must include target and ligand_id columns")
    feature_cols = [col for col in cache_df.columns if col not in required]
    before_cols = set(df.columns)
    merged = df.merge(cache_df[["target", "ligand_id", *feature_cols]], on=["target", "ligand_id"], how="left")
    matched = int(merged[feature_cols].notna().any(axis=1).sum()) if feature_cols else 0
    return merged, {
        "enabled": True,
        "feature_cache_csv": str(cache_path),
        "cache_row_count": int(len(cache_df)),
        "matched_row_count": matched,
        "merged_feature_columns": [col for col in feature_cols if col not in before_cols or col in merged.columns],
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    residual = payload["residual_prototype"]
    return "\n".join(
        [
            "# GPCR Residual Shadow Replay",
            "",
            "## Summary",
            "",
            f"- status: `{summary['status']}`",
            f"- input_rows: `{summary['input_rows']}`",
            f"- prototype_variant: `{residual.get('tuning_variant', '')}`",
            f"- shadow_only_active_locked: `{str(residual.get('shadow_only_active_locked', False)).lower()}`",
            f"- active_score_locked_to_base: `{str(summary['active_score_locked_to_base']).lower()}`",
            f"- active_delta_max_abs: `{summary['active_delta_max_abs']}`",
            f"- reset_prior_active_to_base: `{str(summary.get('reset_prior_active_to_base', False)).lower()}`",
            f"- shadow_score_col: `{summary['shadow_score_col']}`",
            "",
            "## Claim Boundary",
            "",
            "- claim_promotion_allowed: `false`",
            "- scorer_apply_allowed: `false`",
            "- router_platform_or_broad_gpcr_claim_allowed: `false`",
            "- next_step: evaluate this score-only replay against the v2 donor/baseline before any guarded apply.",
            "",
        ]
    )


def build_replay(
    *,
    input_scores_csv: str | Path,
    residual_prototype_spec_json: str | Path,
    residual_prototype_mode: str = "shadow_only",
    score_reference_scaling_mode: str = "run_local",
    score_reference_stats_json: str | Path = "",
    feature_cache_csv: str | Path = "",
    reset_prior_active_to_base: bool = True,
    active_lock_required: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    input_path = _resolve(input_scores_csv)
    spec_path = _resolve(residual_prototype_spec_json)
    if not input_path.exists():
        raise FileNotFoundError(f"input scores CSV not found: {input_path}")
    if not spec_path.exists():
        raise FileNotFoundError(f"residual prototype spec JSON not found: {spec_path}")

    df = pd.read_csv(input_path)
    if df.empty:
        raise ValueError(f"input scores CSV is empty: {input_path}")
    df, feature_cache_summary = _merge_feature_cache(df, feature_cache_csv)
    scaling = scoring._load_score_reference_scaling(
        mode=str(score_reference_scaling_mode),
        stats_json=str(score_reference_stats_json),
    )
    z = _ensure_base_scores(df, scaling)
    if reset_prior_active_to_base:
        # Keep score-only replays independent: do not stack a fresh candidate on
        # stale residual-active columns that may be present in reused stage3 CSVs.
        df["binding_score_composite_v7_residual_active"] = df["binding_score_composite_v7"]
    args = argparse.Namespace(
        residual_prototype_enabled=True,
        residual_prototype_mode=str(residual_prototype_mode),
        residual_prototype_family="gpcr",
        residual_prototype_spec_json=str(spec_path),
        residual_prototype_runtime_hook_ready=True,
        residual_prototype_max_abs_delta_score=None,
        residual_prototype_yellow_band_abs_delta_score=None,
        score_reference_scaling_mode=str(score_reference_scaling_mode),
        score_reference_stats_json=str(score_reference_stats_json or ""),
    )
    replay_df, residual_meta = scoring._apply_residual_prototype_shadow(
        df,
        args,
        z_e=z["z_e"],
        z_d=z["z_d"],
        z_s=z["z_s"],
        z_c=z["z_c"],
        z_aff=z["z_aff"],
        z_logp=z["z_logp"],
        z_rot=z["z_rot"],
        z_hd=z["z_hd"],
        z_ha=z["z_ha"],
        z_std=z["z_std"],
    )
    base = pd.to_numeric(replay_df["binding_score_composite_v7"], errors="coerce")
    active = pd.to_numeric(replay_df["binding_score_composite_v7_residual_active"], errors="coerce")
    active_delta = (active - base).abs()
    active_delta_max_abs = float(active_delta.max()) if len(active_delta) else 0.0
    active_locked = bool(active_delta_max_abs <= 1e-12)
    if active_lock_required and not active_locked:
        raise ValueError("active score lock check failed: residual_active differs from binding_score_composite_v7")
    status = "ready_for_evaluation"
    if active_lock_required and not bool(residual_meta.get("shadow_only_active_locked")):
        status = "blocked_active_lock_missing"
    if active_lock_required and not active_locked:
        status = "blocked_active_score_changed"
    summary = {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "input_scores_csv": str(input_path),
        "residual_prototype_spec_json": str(spec_path),
        "input_rows": int(len(replay_df)),
        "shadow_score_col": "binding_score_composite_v7_residual_shadow",
        "active_score_locked_to_base": active_locked,
        "active_delta_max_abs": active_delta_max_abs,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "broad_gpcr_claim_allowed": False,
        "feature_cache_enabled": bool(feature_cache_summary.get("enabled", False)),
        "feature_cache_matched_row_count": int(feature_cache_summary.get("matched_row_count", 0) or 0),
        "reset_prior_active_to_base": bool(reset_prior_active_to_base),
    }
    payload = {
        "packet_type": "gpcr_residual_shadow_score_only_replay",
        "summary": summary,
        "residual_prototype": residual_meta,
        "score_reference_scaling": {
            "mode": scaling.get("mode", "run_local"),
            "stats_hash": scaling.get("stats_hash", ""),
            "applied_columns": scaling.get("applied_columns", []),
            "fallback_columns": scaling.get("fallback_columns", []),
            "missing_columns": scaling.get("missing_columns", []),
            "invalid_columns": scaling.get("invalid_columns", []),
        },
        "feature_cache": feature_cache_summary,
    }
    return replay_df, payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a GPCR residual shadow scorer on existing stage3 score rows.")
    parser.add_argument("--input-scores-csv", default=DEFAULT_INPUT_SCORES_CSV)
    parser.add_argument("--residual-prototype-spec-json", default=DEFAULT_SPEC_JSON)
    parser.add_argument("--residual-prototype-mode", default="shadow_only")
    parser.add_argument("--score-reference-scaling-mode", default="run_local")
    parser.add_argument("--score-reference-stats-json", default="")
    parser.add_argument("--feature-cache-csv", default="")
    parser.add_argument("--reset-prior-active-to-base", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--active-lock-required", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-scores-csv", default=DEFAULT_OUT_SCORES_CSV)
    parser.add_argument("--out-summary-json", default=DEFAULT_OUT_SUMMARY_JSON)
    parser.add_argument("--out-summary-md", default=DEFAULT_OUT_SUMMARY_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    replay_df, payload = build_replay(
        input_scores_csv=args.input_scores_csv,
        residual_prototype_spec_json=args.residual_prototype_spec_json,
        residual_prototype_mode=args.residual_prototype_mode,
        score_reference_scaling_mode=args.score_reference_scaling_mode,
        score_reference_stats_json=args.score_reference_stats_json,
        feature_cache_csv=args.feature_cache_csv,
        reset_prior_active_to_base=bool(args.reset_prior_active_to_base),
        active_lock_required=bool(args.active_lock_required),
    )
    scores_path = _resolve(args.out_scores_csv)
    summary_path = _resolve(args.out_summary_json)
    md_path = _resolve(args.out_summary_md)
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    replay_df.to_csv(scores_path, index=False)
    payload["summary"]["out_scores_csv"] = str(scores_path)
    _write_json(summary_path, payload)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
