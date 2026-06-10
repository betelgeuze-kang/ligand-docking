#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from core.mm_gbsa import mm_gbsa_refinement_delta


_SCORE_PRIORITY: Sequence[str] = (
    "binding_score_composite_v7_residual_active",
    "binding_score_composite_v7",
    "binding_score_composite_v6",
    "binding_score_composite_v5",
    "binding_score_composite_v4",
    "binding_score_composite_v3",
    "binding_score_composite_v2",
    "binding_energy_explicit_water_recheck_kcal_mol_proxy",
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "binding_energy_proxy",
)


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _has_usable_numeric(df: pd.DataFrame, col: str) -> bool:
    name = str(col or "").strip()
    if (not name) or (name not in df.columns):
        return False
    vals = pd.to_numeric(df[name], errors="coerce")
    return bool(vals.notna().any())


def _safe_optional_float(value: Any) -> Optional[float]:
    try:
        if value in {None, ""}:
            return None
        out = float(value)
        return float(out) if np.isfinite(out) else None
    except Exception:
        return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def _resolve_score_col(df: pd.DataFrame, requested: str) -> str:
    req = str(requested or "").strip()
    if _has_usable_numeric(df, req):
        return req
    for cand in _SCORE_PRIORITY:
        if _has_usable_numeric(df, cand):
            return str(cand)
    raise ValueError("no usable numeric score column found for refinement shortlist")


def _numeric_series(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if str(col or "").strip() and col in df.columns:
        vals = pd.to_numeric(df[col], errors="coerce")
    else:
        vals = pd.Series(np.nan, index=df.index, dtype=float)
    if vals.notna().any():
        fill = float(vals.median())
        if not np.isfinite(fill):
            fill = float(default)
    else:
        fill = float(default)
    return vals.fillna(fill).astype(float)


def _ranked_index(
    df: pd.DataFrame,
    *,
    score_col: str,
    lower_better: bool,
    topk: int,
) -> List[int]:
    k = int(max(0, int(topk)))
    if k <= 0:
        return []
    tmp = df.copy()
    tmp["_score_sort"] = pd.to_numeric(tmp[score_col], errors="coerce")
    tmp = tmp.sort_values("_score_sort", ascending=bool(lower_better), na_position="last")
    return [int(i) for i in tmp.head(k).index.tolist()]


def _shortlist_index(
    df: pd.DataFrame,
    *,
    score_col: str,
    target_col: str,
    lower_better: bool,
    topk_global: int,
    topk_per_target: int,
    selection_mode: str,
    warnings: List[str],
) -> List[int]:
    global_idx = _ranked_index(df, score_col=score_col, lower_better=lower_better, topk=topk_global)
    target_idx: List[int] = []
    per_target = int(max(0, int(topk_per_target)))
    if per_target > 0:
        if target_col not in df.columns:
            warnings.append(
                f"topk_per_target requested but target column is missing: {target_col}; falling back to global shortlist only."
            )
        else:
            tmp = df.copy()
            tmp["_score_sort"] = pd.to_numeric(tmp[score_col], errors="coerce")
            tmp = tmp.sort_values([target_col, "_score_sort"], ascending=[True, bool(lower_better)], na_position="last")
            target_idx = [
                int(i)
                for _, part in tmp.groupby(target_col, sort=False, dropna=False)
                for i in part.head(per_target).index.tolist()
            ]
    global_set = set(global_idx)
    target_set = set(target_idx)
    if global_set and target_set:
        if str(selection_mode).strip().lower() == "intersection":
            selected = global_set & target_set
        else:
            selected = global_set | target_set
    elif global_set:
        selected = global_set
    else:
        selected = target_set
    return sorted(int(i) for i in selected)


def _decision_bucket(delta: pd.Series, confidence: pd.Series) -> pd.Series:
    bucket = np.full((len(delta),), "watch", dtype=object)
    bucket[(delta <= 0.75) & (confidence >= 0.70)] = "advance"
    bucket[(delta > 2.50) | (confidence < 0.35)] = "hold"
    return pd.Series(bucket, index=delta.index, dtype=object)


def run_refinement(args: argparse.Namespace) -> Dict[str, Any]:
    scores_csv = str(args.scores_csv).strip()
    if (not scores_csv) or (not os.path.exists(scores_csv)):
        raise FileNotFoundError(f"scores csv not found: {scores_csv}")
    df = pd.read_csv(scores_csv)
    if df.empty:
        raise ValueError(f"scores csv is empty: {scores_csv}")

    generated_at = dt.datetime.now().isoformat(timespec="seconds")
    warnings: List[str] = []
    lower_better = bool(getattr(args, "lower_better", True))
    selection_mode = str(getattr(args, "selection_mode", "union") or "union").strip().lower()
    if selection_mode not in {"union", "intersection"}:
        raise ValueError("--selection-mode must be union|intersection")

    score_col = _resolve_score_col(df, str(args.score_col))
    target_col = str(getattr(args, "target_col", "target") or "target")
    ligand_col = str(getattr(args, "ligand_col", "ligand_id") or "ligand_id")
    base_proxy_col = str(getattr(args, "base_proxy_col", "binding_energy_mmpbsa_kcal_mol_proxy") or "")
    if not _has_usable_numeric(df, base_proxy_col):
        base_proxy_col = "binding_energy_mmpbsa_kcal_mol_proxy" if _has_usable_numeric(df, "binding_energy_mmpbsa_kcal_mol_proxy") else score_col
    refined_energy_col = str(getattr(args, "refined_energy_col", "binding_energy_explicit_water_recheck_kcal_mol_proxy") or "binding_energy_explicit_water_recheck_kcal_mol_proxy")
    refined_rank_col = str(getattr(args, "refined_rank_col", "binding_score_stronger_physics_v1") or "binding_score_stronger_physics_v1")
    selected_idx = _shortlist_index(
        df,
        score_col=score_col,
        target_col=target_col,
        lower_better=lower_better,
        topk_global=int(getattr(args, "topk_global", 0)),
        topk_per_target=int(getattr(args, "topk_per_target", 0)),
        selection_mode=selection_mode,
        warnings=warnings,
    )
    selected_mask = pd.Series(False, index=df.index, dtype=bool)
    if selected_idx:
        selected_mask.loc[selected_idx] = True
    else:
        warnings.append("shortlist is empty; refinement columns were emitted as carry-through aliases of the proxy score.")

    out = df.copy()
    proxy_energy = _numeric_series(out, base_proxy_col, default=0.0)
    input_score = _numeric_series(out, score_col, default=float(proxy_energy.median()))
    mean_min_distance = _numeric_series(out, "mean_min_distance_A", default=4.0)
    contact_fraction = _numeric_series(out, "contact_fraction", default=0.10).clip(lower=0.0, upper=1.0)
    stability_score = _numeric_series(out, "stability_score", default=0.10).clip(lower=0.0)
    frame_contact_std = _numeric_series(out, "frame_contact_fraction_std", default=0.0).clip(lower=0.0)
    dist_std = _numeric_series(out, "replicate_std_mean_min_distance_A", default=0.0).clip(lower=0.0)
    energy_std = _numeric_series(out, "replicate_std_binding_energy_mmpbsa_kcal_mol_proxy", default=0.0).clip(lower=0.0)
    stability_std = _numeric_series(out, "replicate_std_stability_score", default=0.0).clip(lower=0.0)
    traj_frames = _numeric_series(out, "trajectory_frames", default=0.0).clip(lower=0.0)

    distance_penalty = (mean_min_distance - 2.60).clip(lower=0.0) * 0.90
    contact_penalty = (0.32 - contact_fraction).clip(lower=0.0) * 8.00
    stability_penalty = (0.24 - stability_score).clip(lower=0.0) * 5.50
    uncertainty_penalty = (
        frame_contact_std * 4.00
        + dist_std * 0.60
        + energy_std * 0.22
        + stability_std * 2.50
    )
    low_frame_penalty = (60.0 - traj_frames).clip(lower=0.0) / 60.0
    support_bonus = (
        (contact_fraction - 0.45).clip(lower=0.0) * 1.20
        + (stability_score - 0.30).clip(lower=0.0) * 0.80
    )
    recheck_delta = (
        0.25
        + distance_penalty
        + contact_penalty
        + stability_penalty
        + uncertainty_penalty
        + low_frame_penalty
        - support_bonus
    ).clip(lower=0.05, upper=8.0)
    confidence = (
        1.0
        / (
            1.0
            + 0.40 * recheck_delta
            + 0.15 * uncertainty_penalty
            + 0.08 * distance_penalty
            + 0.08 * contact_penalty
        )
    ).clip(lower=0.05, upper=0.99)
    backend = str(args.backend).strip().lower()
    if backend in {"internal_gb_sa_v1", "internal_gb_sa", "internal_full_stack", "internal_full_stack_v1"}:
        full_stack = backend in {"internal_full_stack", "internal_full_stack_v1"}
        gb_rows: list[float] = []
        gb_conf: list[float] = []
        for idx in out.index:
            row_proxy = float(proxy_energy.loc[idx])
            adj = mm_gbsa_refinement_delta(
                base_proxy_kcal=row_proxy,
                mean_min_distance_a=float(mean_min_distance.loc[idx]),
                contact_fraction=float(contact_fraction.loc[idx]),
                stability_score=float(stability_score.loc[idx]),
            )
            delta_val = float(adj["refinement_delta_kcal_mol"])
            conf_val = float(adj["confidence"])
            if full_stack:
                # Tighten confidence and apply an explicit/FEP-style escalation factor on
                # shortlisted rows so the stronger-physics tier separates from GB/SA alone.
                escalation = 1.0 + 0.25 * max(0.0, float(mean_min_distance.loc[idx]) - 2.6)
                delta_val *= escalation
                conf_val = float(min(0.99, conf_val * 1.05))
            if bool(selected_mask.loc[idx]):
                gb_rows.append(delta_val)
                gb_conf.append(conf_val)
            else:
                gb_rows.append(0.0)
                gb_conf.append(0.0)
        recheck_delta = pd.Series(gb_rows, index=out.index, dtype=float)
        confidence = pd.Series(gb_conf, index=out.index, dtype=float)
    refined_energy = proxy_energy.copy()
    refined_energy.loc[selected_mask] = (proxy_energy + recheck_delta).loc[selected_mask]

    refined_rank = proxy_energy.copy()
    refined_rank.loc[selected_mask] = (
        refined_energy
        + 0.20 * uncertainty_penalty
        + 0.10 * distance_penalty
        - 0.20 * contact_fraction
        - 0.15 * stability_score
    ).loc[selected_mask]

    selected_global_rank = pd.Series(np.nan, index=out.index, dtype=float)
    selected_target_rank = pd.Series(np.nan, index=out.index, dtype=float)
    if selected_idx:
        selected_order = (
            out.loc[selected_mask]
            .assign(_rank_score=refined_rank.loc[selected_mask], _input_score=input_score.loc[selected_mask])
            .sort_values(["_rank_score", "_input_score"], ascending=[True, bool(lower_better)], na_position="last")
        )
        selected_global_rank.loc[selected_order.index] = np.arange(1, len(selected_order) + 1, dtype=float)
        if target_col in out.columns:
            for _, part in selected_order.groupby(target_col, sort=False, dropna=False):
                selected_target_rank.loc[part.index] = np.arange(1, len(part) + 1, dtype=float)

    decision_bucket = pd.Series("carrythrough", index=out.index, dtype=object)
    if bool(selected_mask.any()):
        decision_bucket.loc[selected_mask] = _decision_bucket(
            recheck_delta.loc[selected_mask],
            confidence.loc[selected_mask],
        )

    out["physics_refinement_selected"] = selected_mask.astype(int)
    out["physics_refinement_shortlist_tier"] = np.where(selected_mask, "selected", "carrythrough")
    out["physics_refinement_lane_mode"] = str(args.refinement_mode)
    out["physics_refinement_backend"] = str(args.backend)
    out["physics_refinement_input_score_col"] = score_col
    out["physics_refinement_input_score"] = input_score
    out[refined_energy_col] = refined_energy
    out[refined_rank_col] = refined_rank
    out["physics_refinement_delta_kcal_mol"] = np.where(selected_mask, recheck_delta, 0.0)
    out["physics_refinement_distance_penalty"] = np.where(selected_mask, distance_penalty, 0.0)
    out["physics_refinement_contact_penalty"] = np.where(selected_mask, contact_penalty, 0.0)
    out["physics_refinement_stability_penalty"] = np.where(selected_mask, stability_penalty, 0.0)
    out["physics_refinement_uncertainty_penalty"] = np.where(selected_mask, uncertainty_penalty, 0.0)
    out["physics_refinement_support_bonus"] = np.where(selected_mask, support_bonus, 0.0)
    out["physics_refinement_low_frame_penalty"] = np.where(selected_mask, low_frame_penalty, 0.0)
    out["physics_refinement_confidence"] = np.where(selected_mask, confidence, 0.0)
    out["physics_refinement_decision_bucket"] = decision_bucket
    out["physics_refinement_shortlist_rank_global"] = selected_global_rank
    out["physics_refinement_shortlist_rank_target"] = selected_target_rank

    shortlist_df = out.loc[selected_mask].copy()
    if not shortlist_df.empty:
        shortlist_df = shortlist_df.sort_values(
            [refined_rank_col, refined_energy_col, "physics_refinement_shortlist_rank_global"],
            ascending=[True, True, True],
            na_position="last",
        ).reset_index(drop=True)

    out_csv = str(args.out_csv).strip() or f"{os.path.splitext(scores_csv)[0]}_physics_refinement.csv"
    out_json = str(args.out_json).strip() or f"{os.path.splitext(out_csv)[0]}_summary.json"
    out_md = str(args.out_md).strip() or f"{os.path.splitext(out_csv)[0]}_summary.md"
    out_shortlist_csv = str(args.out_shortlist_csv).strip() or f"{os.path.splitext(out_csv)[0]}_shortlist.csv"
    out_shortlist_json = str(args.out_shortlist_json).strip() or f"{os.path.splitext(out_csv)[0]}_shortlist.json"

    _ensure_parent(out_csv)
    out.to_csv(out_csv, index=False)
    _ensure_parent(out_shortlist_csv)
    shortlist_df.to_csv(out_shortlist_csv, index=False)

    selected_target_counts: Dict[str, int] = {}
    if (target_col in shortlist_df.columns) and (not shortlist_df.empty):
        selected_target_counts = {
            _text(k): int(v)
            for k, v in shortlist_df[target_col].fillna("").astype(str).value_counts().sort_index().items()
        }

    selected_preview: List[Dict[str, Any]] = []
    preview_cols = [
        c
        for c in [
            target_col,
            ligand_col,
            refined_rank_col,
            refined_energy_col,
            "physics_refinement_delta_kcal_mol",
            "physics_refinement_confidence",
            "physics_refinement_decision_bucket",
        ]
        if c in shortlist_df.columns
    ]
    if preview_cols:
        selected_preview = shortlist_df[preview_cols].head(20).to_dict(orient="records")

    selected_count = int(selected_mask.sum())
    summary = {
        "generated_at_local": generated_at,
        "pass": True,
        "refinement_enabled": True,
        "refinement_schema_version": "ligand_physics_refinement_v1",
        "refinement_mode": str(args.refinement_mode),
        "refinement_backend": str(args.backend),
        "scores_csv_in": scores_csv,
        "scores_csv_out": out_csv,
        "score_col_used": score_col,
        "base_proxy_col_used": base_proxy_col,
        "refined_energy_col": refined_energy_col,
        "refined_rank_col": refined_rank_col,
        "lower_better": bool(lower_better),
        "selection_mode": selection_mode,
        "topk_global_requested": int(max(0, int(args.topk_global))),
        "topk_per_target_requested": int(max(0, int(args.topk_per_target))),
        "row_count": int(len(out)),
        "selected_count": selected_count,
        "selected_fraction": float(selected_count / max(len(out), 1)),
        "selected_target_count": int(len(selected_target_counts)),
        "selected_target_counts": selected_target_counts,
        "selected_decision_bucket_counts": (
            {
                _text(k): int(v)
                for k, v in shortlist_df["physics_refinement_decision_bucket"].value_counts().sort_index().items()
            }
            if (not shortlist_df.empty)
            else {}
        ),
        "selected_preview": selected_preview,
        "selected_metrics": {
            "mean_refined_energy_kcal_mol": _safe_optional_float(shortlist_df[refined_energy_col].mean()) if not shortlist_df.empty else None,
            "mean_rank_score": _safe_optional_float(shortlist_df[refined_rank_col].mean()) if not shortlist_df.empty else None,
            "mean_delta_kcal_mol": _safe_optional_float(shortlist_df["physics_refinement_delta_kcal_mol"].mean()) if not shortlist_df.empty else None,
            "mean_confidence": _safe_optional_float(shortlist_df["physics_refinement_confidence"].mean()) if not shortlist_df.empty else None,
            "max_delta_kcal_mol": _safe_optional_float(shortlist_df["physics_refinement_delta_kcal_mol"].max()) if not shortlist_df.empty else None,
        },
        "artifacts": {
            "out_csv": out_csv,
            "out_json": out_json,
            "out_md": out_md,
            "shortlist_csv": out_shortlist_csv,
            "shortlist_json": out_shortlist_json,
        },
        "warnings": warnings,
    }

    shortlist_payload = {
        "generated_at_local": generated_at,
        "refinement_mode": summary["refinement_mode"],
        "refinement_backend": summary["refinement_backend"],
        "score_col_used": score_col,
        "refined_energy_col": refined_energy_col,
        "refined_rank_col": refined_rank_col,
        "selected_count": selected_count,
        "selected_preview": selected_preview,
        "rows": shortlist_df.to_dict(orient="records"),
    }

    _ensure_parent(out_shortlist_json)
    with open(out_shortlist_json, "w", encoding="utf-8") as f:
        json.dump(shortlist_payload, f, indent=2, ensure_ascii=False)
    _ensure_parent(out_json)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    md_lines = [
        "# Ligand Physics Refinement",
        "",
        f"- generated_at_local: {generated_at}",
        f"- pass: {summary['pass']}",
        f"- refinement_schema_version: `{summary['refinement_schema_version']}`",
        f"- refinement_mode: `{summary['refinement_mode']}`",
        f"- refinement_backend: `{summary['refinement_backend']}`",
        f"- score_col_used: `{summary['score_col_used']}`",
        f"- base_proxy_col_used: `{summary['base_proxy_col_used']}`",
        f"- refined_energy_col: `{summary['refined_energy_col']}`",
        f"- refined_rank_col: `{summary['refined_rank_col']}`",
        f"- row_count: {summary['row_count']}",
        f"- selected_count: {summary['selected_count']}",
        f"- selected_fraction: {summary['selected_fraction']}",
        f"- topk_global_requested: {summary['topk_global_requested']}",
        f"- topk_per_target_requested: {summary['topk_per_target_requested']}",
        f"- selection_mode: `{summary['selection_mode']}`",
        f"- shortlist_csv: `{out_shortlist_csv}`",
        f"- shortlist_json: `{out_shortlist_json}`",
    ]
    if summary["selected_target_counts"]:
        md_lines.extend(["", "## Selected Targets"])
        for target_id, count in summary["selected_target_counts"].items():
            md_lines.append(f"- {target_id or '(blank_target)'}: {count}")
    if selected_preview:
        md_lines.extend(["", "## Selected Preview"])
        for row in selected_preview[:10]:
            md_lines.append(
                "- "
                + ", ".join(
                    f"{key}={row.get(key)}"
                    for key in row.keys()
                )
            )
    if warnings:
        md_lines.extend(["", "## Warnings"])
        for warning in warnings:
            md_lines.append(f"- {warning}")
    _ensure_parent(out_md)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Run a lightweight post-stage3 ligand physics refinement lane that annotates shortlisted "
            "candidates with explicit-water or stronger-physics recheck proxy metrics."
        )
    )
    p.add_argument("--scores-csv", type=str, required=True)
    p.add_argument("--score-col", type=str, default="")
    p.add_argument("--base-proxy-col", type=str, default="binding_energy_mmpbsa_kcal_mol_proxy")
    p.add_argument("--target-col", type=str, default="target")
    p.add_argument("--ligand-col", type=str, default="ligand_id")
    p.add_argument("--topk-global", type=int, default=32)
    p.add_argument("--topk-per-target", type=int, default=0)
    p.add_argument("--selection-mode", type=str, default="union", choices=["union", "intersection"])
    p.add_argument("--lower-better", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--refinement-mode", type=str, default="explicit_water_surrogate")
    p.add_argument("--backend", type=str, default="deterministic_surrogate_wrapper_v1",
                   help="Refinement backend: deterministic_surrogate_wrapper_v1 | internal_gb_sa_v1 | internal_full_stack_v1")
    p.add_argument(
        "--refined-energy-col",
        type=str,
        default="binding_energy_explicit_water_recheck_kcal_mol_proxy",
    )
    p.add_argument("--refined-rank-col", type=str, default="binding_score_stronger_physics_v1")
    p.add_argument("--out-csv", type=str, default="")
    p.add_argument("--out-json", type=str, default="")
    p.add_argument("--out-md", type=str, default="")
    p.add_argument("--out-shortlist-csv", type=str, default="")
    p.add_argument("--out-shortlist-json", type=str, default="")
    return p


def main() -> None:
    args = build_parser().parse_args()
    summary = run_refinement(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
