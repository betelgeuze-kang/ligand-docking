#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _fit_linear(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    if x.size <= 1:
        return 1.0, 0.0
    x_std = float(np.std(x))
    if x_std <= 1e-12:
        return 1.0, float(np.mean(y) - np.mean(x))
    a, b = np.polyfit(x, y, deg=1)
    return float(a), float(b)


def _fit_ridge(design: np.ndarray, y: np.ndarray, l2: float) -> np.ndarray:
    if design.ndim != 2 or design.shape[0] <= 0:
        return np.zeros((design.shape[1],), dtype=np.float64)
    reg = np.eye(design.shape[1], dtype=np.float64)
    reg[0, 0] = 0.0  # do not regularize intercept
    lam = float(max(l2, 0.0))
    xtx = design.T @ design
    xty = design.T @ y
    try:
        w = np.linalg.solve(xtx + lam * reg, xty)
    except np.linalg.LinAlgError:
        w = np.linalg.lstsq(design, y, rcond=None)[0]
    return w.astype(np.float64, copy=False)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    err = y_pred - y_true
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    var = float(np.var(y_true))
    r2 = 1.0 - float(np.mean(err**2) / var) if var > 1e-12 else float("nan")
    return {"mae": mae, "rmse": rmse, "r2": r2}


def run_calibration(args: argparse.Namespace) -> Dict[str, Any]:
    scores_csv = str(args.scores_csv).strip()
    if (not scores_csv) or (not os.path.exists(scores_csv)):
        raise FileNotFoundError(f"scores csv not found: {scores_csv}")
    df = pd.read_csv(scores_csv)
    if df.empty:
        raise ValueError(f"scores csv is empty: {scores_csv}")
    proxy_col = str(args.proxy_col).strip()
    if proxy_col not in df.columns:
        raise ValueError(f"proxy column not found in scores csv: {proxy_col}")

    ref_csv = str(args.reference_csv).strip()
    value_col = str(args.reference_value_col).strip()
    join_target = str(args.join_target_col).strip()
    join_ligand = str(args.join_ligand_col).strip()

    calib_mode = "identity"
    slope = float(args.default_slope)
    intercept = float(args.default_intercept)
    feature_cols_req = [c.strip() for c in str(getattr(args, "feature_cols", "") or "").split(",") if c.strip()]
    fit_feature_cols: List[str] = []
    model_coef: Dict[str, float] = {}
    feature_center: Dict[str, float] = {}
    feature_scale: Dict[str, float] = {}
    model_intercept = float(intercept)
    merged_n = 0
    fit_rows_total = 0
    fit_unique_keys = 0
    fit_stats: Dict[str, Any] = {}
    if ref_csv and os.path.exists(ref_csv):
        ref_df = pd.read_csv(ref_csv)
        required = {join_target, join_ligand, value_col}
        miss = [c for c in required if c not in ref_df.columns]
        if miss:
            raise ValueError(f"reference csv missing columns: {miss}")
        l_cols = [join_target, join_ligand, proxy_col]
        for c in feature_cols_req:
            if c in df.columns and c not in l_cols:
                l_cols.append(c)
        l_df = df[l_cols].copy()
        m = l_df.merge(
            ref_df[[join_target, join_ligand, value_col]].copy(),
            on=[join_target, join_ligand],
            how="inner",
        )
        split_csv = str(getattr(args, "split_csv", "") or "").strip()
        split_roles_raw = str(getattr(args, "fit_roles", "") or "").strip()
        split_roles = [r.strip() for r in split_roles_raw.split(",") if r.strip()]
        split_role_col = str(getattr(args, "split_role_col", "role") or "role").strip()
        split_target_col = str(getattr(args, "split_target_col", join_target) or join_target).strip()
        split_ligand_col = str(getattr(args, "split_ligand_col", join_ligand) or join_ligand).strip()
        split_required = bool(getattr(args, "require_split_for_fit", False))
        if split_csv:
            if not os.path.exists(split_csv):
                raise FileNotFoundError(f"split csv not found: {split_csv}")
            split_df = pd.read_csv(split_csv)
            split_req = {split_target_col, split_ligand_col, split_role_col}
            split_miss = [c for c in split_req if c not in split_df.columns]
            if split_miss:
                raise ValueError(f"split csv missing columns: {split_miss}")
            split_part = split_df[[split_target_col, split_ligand_col, split_role_col]].copy()
            split_part = split_part.rename(
                columns={
                    split_target_col: join_target,
                    split_ligand_col: join_ligand,
                }
            )
            m = m.merge(split_part, on=[join_target, join_ligand], how="left")
            if split_roles:
                m = m[m[split_role_col].astype(str).isin(split_roles)].copy()
            elif split_required:
                raise ValueError("--require-split-for-fit enabled but --fit-roles is empty")
        elif split_required:
            raise ValueError("--require-split-for-fit enabled but --split-csv is missing")
        m = m.dropna(subset=[proxy_col, value_col]).reset_index(drop=True)
        merged_n = int(len(m))
        fit_rows_total = int(merged_n)
        if merged_n > 0:
            fit_unique_keys = int(
                m[[join_target, join_ligand]].drop_duplicates().shape[0]
            )
        if merged_n >= int(args.min_pairs_to_fit):
            y = m[value_col].to_numpy(dtype=np.float64)
            fit_feature_cols = [proxy_col]
            for c in feature_cols_req:
                if c in m.columns:
                    fit_feature_cols.append(c)
            if len(fit_feature_cols) <= 1:
                x = m[proxy_col].to_numpy(dtype=np.float64)
                slope, intercept = _fit_linear(x, y)
                model_intercept = float(intercept)
                y_hat = slope * x + intercept
                model_coef = {proxy_col: float(slope)}
                fit_stats = _metrics(y_true=y, y_pred=y_hat)
                fit_stats["fit_rows"] = merged_n
                calib_mode = "linear_fit"
            else:
                x_raw = m[fit_feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=np.float64)
                mu = np.mean(x_raw, axis=0)
                sd = np.std(x_raw, axis=0)
                sd = np.where(sd <= 1e-8, 1.0, sd)
                x_norm = (x_raw - mu) / sd
                design = np.concatenate([np.ones((x_norm.shape[0], 1), dtype=np.float64), x_norm], axis=1)
                w = _fit_ridge(design, y, l2=float(getattr(args, "ridge_l2", 1e-2)))
                y_hat = design @ w
                fit_stats = _metrics(y_true=y, y_pred=y_hat)
                fit_stats["fit_rows"] = merged_n
                fit_stats["ridge_l2"] = float(getattr(args, "ridge_l2", 1e-2))
                calib_mode = "ridge_multifeature_fit"
                model_intercept = float(w[0])
                model_coef = {}
                for i, c in enumerate(fit_feature_cols):
                    model_coef[c] = float(w[i + 1])
                    feature_center[c] = float(mu[i])
                    feature_scale[c] = float(sd[i])
                slope = float(model_coef.get(proxy_col, slope))
                intercept = float(model_intercept)
        else:
            calib_mode = "identity_insufficient_pairs"

    out_col = str(args.out_col).strip()
    out = df.copy()
    if calib_mode == "ridge_multifeature_fit" and fit_feature_cols and model_coef:
        x_out = out[fit_feature_cols].apply(pd.to_numeric, errors="coerce").copy()
        for c in fit_feature_cols:
            center = float(feature_center.get(c, 0.0))
            x_out[c] = x_out[c].fillna(center)
            scale = float(feature_scale.get(c, 1.0))
            x_out[c] = (x_out[c].astype(float) - center) / max(scale, 1e-8)
        pred = np.full((len(out),), float(model_intercept), dtype=np.float64)
        for c in fit_feature_cols:
            pred += float(model_coef.get(c, 0.0)) * x_out[c].to_numpy(dtype=np.float64)
        out[out_col] = pred.astype(np.float64)
    else:
        out[out_col] = out[proxy_col].astype(float) * float(slope) + float(intercept)
    clip_abs = float(args.clip_abs)
    if clip_abs > 0.0:
        out[out_col] = out[out_col].clip(lower=-clip_abs, upper=clip_abs)

    out_csv = str(args.out_csv).strip() or scores_csv
    out_json = str(args.out_json).strip()
    out_md = str(args.out_md).strip()
    if not out_json:
        out_json = f"{os.path.splitext(out_csv)[0]}_calibration.json"
    if not out_md:
        out_md = f"{os.path.splitext(out_csv)[0]}_calibration.md"

    _ensure_parent(out_csv)
    out.to_csv(out_csv, index=False)

    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "pass": True,
        "calibration_mode": calib_mode,
        "scores_csv_in": scores_csv,
        "scores_csv_out": out_csv,
        "proxy_col": proxy_col,
        "calibrated_col": out_col,
        "reference_csv": ref_csv or "",
        "reference_pairs_used": int(merged_n),
        "fit_rows_total": int(fit_rows_total),
        "fit_unique_keys": int(fit_unique_keys),
        "fit_roles": [r.strip() for r in str(getattr(args, "fit_roles", "") or "").split(",") if r.strip()],
        "feature_cols_requested": feature_cols_req,
        "feature_cols_used": fit_feature_cols,
        "slope": float(slope),
        "intercept": float(intercept),
        "clip_abs": float(clip_abs),
        "fit_stats": fit_stats,
        "model_coef": model_coef,
        "feature_center": feature_center,
        "feature_scale": feature_scale,
        "artifacts": {
            "out_csv": out_csv,
            "out_json": out_json,
            "out_md": out_md,
        },
    }
    out_model_json = str(getattr(args, "out_model_json", "") or "").strip()
    if not out_model_json:
        out_model_json = f"{os.path.splitext(out_csv)[0]}_calibration_model.json"
    model_payload = {
        "generated_at_local": summary["generated_at_local"],
        "calibration_mode": summary["calibration_mode"],
        "proxy_col": proxy_col,
        "reference_value_col": value_col,
        "feature_cols_used": fit_feature_cols,
        "slope": float(slope),
        "intercept": float(intercept),
        "model_coef": model_coef,
        "feature_center": feature_center,
        "feature_scale": feature_scale,
        "fit_rows_total": int(fit_rows_total),
        "fit_unique_keys": int(fit_unique_keys),
        "fit_roles": summary["fit_roles"],
    }
    _ensure_parent(out_model_json)
    with open(out_model_json, "w", encoding="utf-8") as f:
        json.dump(model_payload, f, indent=2, ensure_ascii=False)
    summary["artifacts"]["out_model_json"] = out_model_json
    _ensure_parent(out_json)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    lines = [
        "# Ligand Proxy Calibration",
        "",
        f"- generated_at_local: {summary['generated_at_local']}",
        f"- pass: {summary['pass']}",
        f"- calibration_mode: {summary['calibration_mode']}",
        f"- scores_csv_in: `{scores_csv}`",
        f"- scores_csv_out: `{out_csv}`",
        f"- reference_pairs_used: {summary['reference_pairs_used']}",
        f"- slope: {summary['slope']}",
        f"- intercept: {summary['intercept']}",
        f"- fit_stats: {summary['fit_stats']}",
    ]
    _ensure_parent(out_md)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return summary


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description="Calibrate ligand MM/PBSA proxy score to reference binding values (linear fit)."
    )
    p.add_argument("--scores-csv", type=str, required=True)
    p.add_argument("--reference-csv", type=str, default="")
    p.add_argument("--proxy-col", type=str, default="binding_energy_mmpbsa_kcal_mol_proxy")
    p.add_argument("--reference-value-col", type=str, default="reference_binding_kcal_mol")
    p.add_argument("--join-target-col", type=str, default="target")
    p.add_argument("--join-ligand-col", type=str, default="ligand_id")
    p.add_argument("--split-csv", type=str, default="")
    p.add_argument("--fit-roles", type=str, default="")
    p.add_argument("--split-role-col", type=str, default="role")
    p.add_argument("--split-target-col", type=str, default="target")
    p.add_argument("--split-ligand-col", type=str, default="ligand_id")
    p.add_argument("--require-split-for-fit", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--min-pairs-to-fit", type=int, default=3)
    p.add_argument(
        "--feature-cols",
        type=str,
        default="ligand_affinity_hint,ligand_onsps_norm,mean_min_distance_A,contact_fraction,stability_score",
    )
    p.add_argument("--ridge-l2", type=float, default=1e-2)
    p.add_argument("--default-slope", type=float, default=1.0)
    p.add_argument("--default-intercept", type=float, default=0.0)
    p.add_argument("--clip-abs", type=float, default=200.0)
    p.add_argument("--out-col", type=str, default="binding_energy_mmpbsa_kcal_mol_calibrated")
    p.add_argument("--out-csv", type=str, default=f"runs/ligand_scores_calibrated_{stamp}.csv")
    p.add_argument("--out-json", type=str, default=f"runs/ligand_scores_calibrated_{stamp}.json")
    p.add_argument("--out-md", type=str, default=f"runs/ligand_scores_calibrated_{stamp}.md")
    p.add_argument("--out-model-json", type=str, default=f"runs/ligand_scores_calibrated_{stamp}_model.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_calibration(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
