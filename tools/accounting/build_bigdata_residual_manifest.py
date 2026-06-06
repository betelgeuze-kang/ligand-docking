#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from core.definitions import ResearchConstants
from tools.build_distilled_residual_dataset import build_distilled_residual_dataset


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _parse_targets(spec: str) -> List[str]:
    s = str(spec).strip().lower()
    if s == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    out = [x.strip() for x in str(spec).split(",") if x.strip()]
    if not out:
        raise ValueError(f"no targets parsed from: {spec}")
    return out


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _load_manifest_rows(
    manifest_csv: str,
    source_tag: str,
    base_weight: float,
    selected_targets: List[str],
    skip_missing_output_npz: bool,
) -> pd.DataFrame:
    if not os.path.exists(manifest_csv):
        raise FileNotFoundError(f"manifest not found: {manifest_csv}")
    try:
        df = pd.read_csv(manifest_csv)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    required = {"target", "split", "output_npz"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"manifest missing required columns {required}: {manifest_csv}")
    if "error" in df.columns:
        df = df[df["error"].isna()].copy()

    allowed = {_normalize_target_key(t) for t in selected_targets}
    df = df[df["target"].astype(str).map(_normalize_target_key).isin(allowed)].copy()
    if df.empty:
        return df

    if skip_missing_output_npz:
        exists_mask = df["output_npz"].astype(str).map(os.path.exists)
        df = df[exists_mask].copy()

    if df.empty:
        return df

    df["source_tag"] = str(source_tag)
    df["sampling_weight"] = float(base_weight)
    return df


def _target_multiplier_map(path: Optional[str]) -> Dict[str, float]:
    if not path:
        return {}
    if not os.path.exists(path):
        raise FileNotFoundError(f"target weights csv not found: {path}")
    df = pd.read_csv(path)
    if "target" not in df.columns:
        raise ValueError("target weights csv must include column: target")
    weight_col = None
    for cand in ("multiplier", "sampling_weight", "weight"):
        if cand in df.columns:
            weight_col = cand
            break
    if weight_col is None:
        raise ValueError("target weights csv must include one of: multiplier, sampling_weight, weight")

    out: Dict[str, float] = {}
    for _, row in df.iterrows():
        key = _normalize_target_key(str(row.get("target", "")).strip())
        if not key:
            continue
        try:
            v = float(row.get(weight_col, 1.0))
        except Exception:
            v = 1.0
        out[key] = v
    return out


def _apply_target_multipliers(df: pd.DataFrame, target_map: Dict[str, float]) -> pd.DataFrame:
    if not target_map or df.empty:
        return df
    out = df.copy()
    mult = out["target"].astype(str).map(lambda x: target_map.get(_normalize_target_key(x), 1.0))
    out["sampling_weight"] = out["sampling_weight"].astype(float) * mult.astype(float)
    return out


def _resolve_n_res_for_weight(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series([], dtype="float64")
    target_to_n_res = {
        str(t): int(cfg.get("n_res", 0))
        for t, cfg in ResearchConstants.CHALLENGES.items()
    }

    vals: List[float] = []
    has_n_res_expected = "n_res_expected" in df.columns
    has_n_atoms = "n_atoms" in df.columns
    for _, row in df.iterrows():
        v = 0.0
        if has_n_res_expected:
            raw = row.get("n_res_expected", 0.0)
            try:
                v = float(raw)
            except Exception:
                v = 0.0
        if v <= 0.0:
            t = str(row.get("target", ""))
            v = float(target_to_n_res.get(t, 0))
        if v <= 0.0 and has_n_atoms:
            raw_atoms = row.get("n_atoms", 0.0)
            try:
                n_atoms = float(raw_atoms)
            except Exception:
                n_atoms = 0.0
            if n_atoms > 0.0:
                # Fallback heuristic when only atom count exists.
                v = n_atoms
        vals.append(max(float(v), 1.0))
    return pd.Series(vals, index=df.index, dtype="float64")


def _apply_length_weight(
    df: pd.DataFrame,
    length_weight_beta: float,
    length_reference_n_res: float,
) -> pd.DataFrame:
    out = df.copy()
    n_res = _resolve_n_res_for_weight(out)
    ref = max(float(length_reference_n_res), 1.0)
    beta = float(length_weight_beta)
    if beta == 0.0:
        mult = pd.Series([1.0] * len(out), index=out.index, dtype="float64")
    else:
        mult = (n_res / ref).astype("float64").pow(beta)
        mult = mult.clip(lower=1e-6)
    out["n_res_for_weight"] = n_res.astype("float64")
    out["length_weight_multiplier"] = mult.astype("float64")
    out["sampling_weight"] = out["sampling_weight"].astype(float) * out["length_weight_multiplier"].astype(float)
    return out


def _apply_n_atoms_consistency(df: pd.DataFrame, policy: str) -> tuple[pd.DataFrame, Dict[str, Any]]:
    p = str(policy).strip().lower()
    if p in ("none", "off", ""):
        return df, {"policy": "none", "rows_removed": 0, "targets_affected": []}
    if "n_atoms" not in df.columns:
        return df, {"policy": p, "rows_removed": 0, "targets_affected": []}

    keep = pd.Series([True] * len(df), index=df.index)
    affected: List[Dict[str, Any]] = []
    for target, sub in df.groupby("target"):
        atoms = sorted({int(x) for x in sub["n_atoms"].dropna().astype(int).tolist()})
        if len(atoms) <= 1:
            continue
        if p in ("max_atoms", "prefer_2bead", "max"):
            chosen = int(max(atoms))
        elif p in ("min_atoms", "prefer_ca", "min"):
            chosen = int(min(atoms))
        else:
            raise ValueError(f"unsupported bead consistency policy: {policy}")
        bad_idx = sub[sub["n_atoms"].astype(int) != chosen].index
        keep.loc[bad_idx] = False
        affected.append({"target": str(target), "atoms": atoms, "chosen_n_atoms": chosen})
    out = df[keep].copy()
    rows_removed = int(len(df) - len(out))
    return out, {"policy": p, "rows_removed": rows_removed, "targets_affected": affected}


def build_bigdata_residual_manifest(
    base_manifest_csv: str,
    out_manifest_csv: str,
    out_summary_json: str,
    targets: str = "all",
    hardcase_manifest_csv: Optional[str] = None,
    hardcase_h5_glob: str = "data/residual_hardcases_2026-02-15/*_airouter_*_data.h5",
    hardcase_out_dir: str = "data/distilled_residual_hardcases",
    hardcase_out_manifest_csv: str = "runs/distilled_residual_manifest_hardcases.csv",
    hardcase_out_summary_json: str = "runs/distilled_residual_summary_hardcases.json",
    hardcase_float_dtype: str = "float32",
    hardcase_keep_coords: bool = True,
    hardcase_min_quality: Optional[float] = None,
    hardcase_max_samples_per_file: Optional[int] = None,
    hardcase_repair_zero_residual: bool = True,
    hardcase_zero_residual_atol: float = 1e-8,
    hardcase_repair_device: str = "cpu",
    hardcase_reference_cutoff: float = 14.0,
    hardcase_reference_max_neighbors: int = 160,
    hardcase_reference_force_cap: Optional[float] = 100.0,
    base_weight: float = 1.0,
    hardcase_weight: float = 3.0,
    length_weight_beta: float = 0.0,
    length_reference_n_res: float = 40.0,
    target_weights_csv: Optional[str] = None,
    bead_consistency_policy: str = "max_atoms",
    min_sampling_weight: float = 1e-6,
    skip_missing_output_npz: bool = True,
) -> Dict[str, Any]:
    selected_targets = _parse_targets(targets)
    hardcase_distill_summary: Optional[Dict[str, Any]] = None
    hardcase_manifest = hardcase_manifest_csv

    if not hardcase_manifest:
        hardcase_distill_summary = build_distilled_residual_dataset(
            input_glob=str(hardcase_h5_glob),
            targets=str(targets),
            out_dir=str(hardcase_out_dir),
            out_manifest_csv=str(hardcase_out_manifest_csv),
            out_summary_json=str(hardcase_out_summary_json),
            float_dtype=str(hardcase_float_dtype),
            keep_coords=bool(hardcase_keep_coords),
            max_samples_per_file=hardcase_max_samples_per_file,
            min_quality=hardcase_min_quality,
            skip_if_exists=False,
            repair_zero_residual=bool(hardcase_repair_zero_residual),
            zero_residual_atol=float(hardcase_zero_residual_atol),
            repair_device=str(hardcase_repair_device),
            repair_reference_cutoff=float(hardcase_reference_cutoff),
            repair_reference_max_neighbors=int(hardcase_reference_max_neighbors),
            repair_reference_force_cap=hardcase_reference_force_cap,
        )
        hardcase_manifest = str(hardcase_out_manifest_csv)

    base_df = _load_manifest_rows(
        manifest_csv=str(base_manifest_csv),
        source_tag="base",
        base_weight=float(base_weight),
        selected_targets=selected_targets,
        skip_missing_output_npz=bool(skip_missing_output_npz),
    )
    hard_df = _load_manifest_rows(
        manifest_csv=str(hardcase_manifest),
        source_tag="hardcase",
        base_weight=float(hardcase_weight),
        selected_targets=selected_targets,
        skip_missing_output_npz=bool(skip_missing_output_npz),
    )

    merged = pd.concat([base_df, hard_df], ignore_index=True) if (not base_df.empty or not hard_df.empty) else pd.DataFrame()
    if merged.empty:
        raise ValueError("merged manifest is empty after filtering")

    target_map = _target_multiplier_map(target_weights_csv)
    merged = _apply_target_multipliers(merged, target_map)
    merged = _apply_length_weight(
        merged,
        length_weight_beta=float(length_weight_beta),
        length_reference_n_res=float(length_reference_n_res),
    )
    merged["sampling_weight"] = merged["sampling_weight"].astype(float).clip(lower=float(min_sampling_weight))
    merged, consistency_info = _apply_n_atoms_consistency(merged, policy=bead_consistency_policy)

    # If duplicate shard path appears, keep the row with larger sampling weight.
    merged = merged.sort_values(["output_npz", "sampling_weight"], ascending=[True, False])
    merged = merged.drop_duplicates(subset=["output_npz"], keep="first").reset_index(drop=True)

    _ensure_parent(out_manifest_csv)
    merged.to_csv(out_manifest_csv, index=False)

    by_source = (
        merged.groupby("source_tag")["output_npz"]
        .count()
        .reset_index(name="rows")
        .to_dict(orient="records")
    )
    by_split = (
        merged.groupby("split")["output_npz"]
        .count()
        .reset_index(name="rows")
        .to_dict(orient="records")
    )
    by_target = (
        merged.groupby("target")["output_npz"]
        .count()
        .reset_index(name="rows")
        .sort_values("rows", ascending=False)
        .to_dict(orient="records")
    )
    sampling_stats = {
        "min": float(merged["sampling_weight"].min()),
        "max": float(merged["sampling_weight"].max()),
        "mean": float(merged["sampling_weight"].mean()),
        "median": float(merged["sampling_weight"].median()),
    }
    length_mult_stats = {
        "min": float(merged["length_weight_multiplier"].min()),
        "max": float(merged["length_weight_multiplier"].max()),
        "mean": float(merged["length_weight_multiplier"].mean()),
        "median": float(merged["length_weight_multiplier"].median()),
    }

    summary = {
        "targets": selected_targets,
        "base_manifest_csv": str(base_manifest_csv),
        "hardcase_manifest_csv": str(hardcase_manifest),
        "out_manifest_csv": str(out_manifest_csv),
        "rows_total": int(len(merged)),
        "rows_by_source": by_source,
        "rows_by_split": by_split,
        "rows_by_target": by_target,
        "sampling_weight_stats": sampling_stats,
        "base_weight": float(base_weight),
        "hardcase_weight": float(hardcase_weight),
        "length_weight_beta": float(length_weight_beta),
        "length_reference_n_res": float(length_reference_n_res),
        "length_weight_multiplier_stats": length_mult_stats,
        "target_weights_csv": str(target_weights_csv) if target_weights_csv else None,
        "bead_consistency": consistency_info,
        "skip_missing_output_npz": bool(skip_missing_output_npz),
        "hardcase_distill_summary": hardcase_distill_summary,
    }
    _ensure_parent(out_summary_json)
    with open(out_summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Build merged residual-learning manifest for bigdata training "
            "(base distilled + hardcase distilled) with sampling weights."
        )
    )
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--base-manifest-csv", type=str, default="runs/distilled_residual_manifest_repaired_fp32_cap100.csv")
    p.add_argument("--hardcase-manifest-csv", type=str, default="")
    p.add_argument("--hardcase-h5-glob", type=str, default="data/residual_hardcases_2026-02-15/*_airouter_*_data.h5")
    p.add_argument("--hardcase-out-dir", type=str, default="data/distilled_residual_hardcases")
    p.add_argument("--hardcase-out-manifest-csv", type=str, default="runs/distilled_residual_manifest_hardcases.csv")
    p.add_argument("--hardcase-out-summary-json", type=str, default="runs/distilled_residual_summary_hardcases.json")
    p.add_argument("--hardcase-float-dtype", type=str, default="float32", choices=["float16", "float32"])
    p.add_argument("--hardcase-keep-coords", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--hardcase-min-quality", type=float, default=None)
    p.add_argument("--hardcase-max-samples-per-file", type=int, default=None)
    p.add_argument("--hardcase-repair-zero-residual", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--hardcase-zero-residual-atol", type=float, default=1e-8)
    p.add_argument("--hardcase-repair-device", type=str, default="cpu")
    p.add_argument("--hardcase-reference-cutoff", type=float, default=14.0)
    p.add_argument("--hardcase-reference-max-neighbors", type=int, default=160)
    p.add_argument("--hardcase-reference-force-cap", type=float, default=100.0)
    p.add_argument("--base-weight", type=float, default=1.0)
    p.add_argument("--hardcase-weight", type=float, default=3.0)
    p.add_argument("--length-weight-beta", type=float, default=0.0)
    p.add_argument("--length-reference-n-res", type=float, default=40.0)
    p.add_argument("--target-weights-csv", type=str, default="")
    p.add_argument(
        "--bead-consistency-policy",
        type=str,
        default="max_atoms",
        choices=["none", "max_atoms", "min_atoms"],
        help="When n_atoms are mixed per target, keep one representation only.",
    )
    p.add_argument("--min-sampling-weight", type=float, default=1e-6)
    p.add_argument("--skip-missing-output-npz", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--out-manifest-csv", type=str, default="runs/distilled_residual_manifest_bigdata.csv")
    p.add_argument("--out-summary-json", type=str, default="runs/distilled_residual_bigdata_summary.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = build_parser()
    args = p.parse_args(argv)
    summary = build_bigdata_residual_manifest(
        targets=str(args.targets),
        base_manifest_csv=str(args.base_manifest_csv),
        hardcase_manifest_csv=(str(args.hardcase_manifest_csv).strip() or None),
        hardcase_h5_glob=str(args.hardcase_h5_glob),
        hardcase_out_dir=str(args.hardcase_out_dir),
        hardcase_out_manifest_csv=str(args.hardcase_out_manifest_csv),
        hardcase_out_summary_json=str(args.hardcase_out_summary_json),
        hardcase_float_dtype=str(args.hardcase_float_dtype),
        hardcase_keep_coords=bool(args.hardcase_keep_coords),
        hardcase_min_quality=args.hardcase_min_quality,
        hardcase_max_samples_per_file=args.hardcase_max_samples_per_file,
        hardcase_repair_zero_residual=bool(args.hardcase_repair_zero_residual),
        hardcase_zero_residual_atol=float(args.hardcase_zero_residual_atol),
        hardcase_repair_device=str(args.hardcase_repair_device),
        hardcase_reference_cutoff=float(args.hardcase_reference_cutoff),
        hardcase_reference_max_neighbors=int(args.hardcase_reference_max_neighbors),
        hardcase_reference_force_cap=(
            None
            if float(args.hardcase_reference_force_cap) <= 0.0
            else float(args.hardcase_reference_force_cap)
        ),
        base_weight=float(args.base_weight),
        hardcase_weight=float(args.hardcase_weight),
        length_weight_beta=float(args.length_weight_beta),
        length_reference_n_res=float(args.length_reference_n_res),
        target_weights_csv=(str(args.target_weights_csv).strip() or None),
        bead_consistency_policy=str(args.bead_consistency_policy),
        min_sampling_weight=float(args.min_sampling_weight),
        skip_missing_output_npz=bool(args.skip_missing_output_npz),
        out_manifest_csv=str(args.out_manifest_csv),
        out_summary_json=str(args.out_summary_json),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
