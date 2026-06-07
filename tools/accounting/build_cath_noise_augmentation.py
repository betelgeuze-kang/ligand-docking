#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd


def _read_ca_coords(path: str) -> np.ndarray:
    coords: List[List[float]] = []
    model_seen = False
    in_first_model = True
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            rec = line[0:6].strip().upper()
            if rec == "MODEL":
                if not model_seen:
                    model_seen = True
                    in_first_model = True
                else:
                    in_first_model = False
                continue
            if rec == "ENDMDL" and model_seen:
                break
            if model_seen and (not in_first_model):
                continue
            if not line.startswith("ATOM"):
                continue
            atom_name = line[12:16].strip()
            if atom_name != "CA":
                continue
            try:
                x = float(line[30:38].strip())
                y = float(line[38:46].strip())
                z = float(line[46:54].strip())
            except Exception:
                continue
            coords.append([x, y, z])
    if len(coords) == 0:
        return np.zeros((0, 3), dtype=np.float64)
    return np.asarray(coords, dtype=np.float64)


def _kabsch_rmsd(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape or a.size == 0:
        return float("nan")
    xa = np.asarray(a, dtype=np.float64)
    xb = np.asarray(b, dtype=np.float64)
    xa = xa - xa.mean(axis=0, keepdims=True)
    xb = xb - xb.mean(axis=0, keepdims=True)
    cov = xa.T @ xb
    u, _s, vh = np.linalg.svd(cov, full_matrices=False)
    d = np.linalg.det(u @ vh)
    if d < 0.0:
        u[:, -1] *= -1.0
    rot = u @ vh
    xr = xa @ rot
    diff = xr - xb
    return float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))


def _radius_of_gyration(coords: np.ndarray) -> float:
    if coords.size == 0:
        return float("nan")
    c = coords - coords.mean(axis=0, keepdims=True)
    return float(np.sqrt(np.mean(np.sum(c * c, axis=1))))


def _min_pair_distance(coords: np.ndarray) -> float:
    n = int(coords.shape[0]) if coords.ndim == 2 else 0
    if n < 2:
        return float("nan")
    diff = coords[:, None, :] - coords[None, :, :]
    d2 = np.sum(diff * diff, axis=-1)
    np.fill_diagonal(d2, np.inf)
    return float(np.sqrt(np.min(d2)))


def _parse_sigma_list(raw: str) -> List[float]:
    vals: List[float] = []
    for tok in str(raw).split(","):
        t = tok.strip()
        if not t:
            continue
        vals.append(float(t))
    if len(vals) == 0:
        vals = [0.25, 0.5, 1.0]
    return vals


def build_cath_noise_augmentation(
    manifest_csv: str,
    out_csv: str,
    out_json: str,
    seed: int = 20260219,
    variants_per_target: int = 24,
    noise_sigmas: str = "0.25,0.5,1.0",
    min_ca_residues: int = 20,
    unstable_min_distance_threshold: float = 2.8,
    unstable_rmsd_threshold: float = 3.0,
    unstable_rg_ratio_threshold: float = 0.25,
) -> Dict[str, Any]:
    df = pd.read_csv(manifest_csv)
    if "target" not in df.columns or "path" not in df.columns:
        raise ValueError(f"manifest missing required columns target/path: {manifest_csv}")
    if "status" in df.columns:
        ok_status = {"downloaded", "exists"}
        df = df[df["status"].astype(str).isin(ok_status)].copy()

    rng = np.random.default_rng(int(seed))
    sigmas = _parse_sigma_list(noise_sigmas)
    rows: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for rec in df.to_dict(orient="records"):
        target = str(rec.get("target", "")).strip()
        path = str(rec.get("path", "")).strip()
        if not target or not path or (not os.path.exists(path)):
            continue
        native = _read_ca_coords(path)
        n_ca = int(native.shape[0]) if native.ndim == 2 else 0
        if n_ca < int(min_ca_residues):
            skipped.append({"target": target, "path": path, "reason": "low_ca_residue_count", "ca_residues": n_ca})
            continue

        rg_native = _radius_of_gyration(native)
        for i in range(int(variants_per_target)):
            sigma = float(sigmas[i % len(sigmas)])
            noise = rng.normal(loc=0.0, scale=sigma, size=native.shape)
            perturbed = native + noise
            rmsd = _kabsch_rmsd(native, perturbed)
            min_dist = _min_pair_distance(perturbed)
            rg_pert = _radius_of_gyration(perturbed)
            rg_ratio = float(abs(rg_pert - rg_native) / rg_native) if (np.isfinite(rg_native) and rg_native > 0.0) else float("nan")
            unstable = bool(
                (np.isfinite(min_dist) and min_dist < float(unstable_min_distance_threshold))
                or (np.isfinite(rmsd) and rmsd > float(unstable_rmsd_threshold))
                or (np.isfinite(rg_ratio) and rg_ratio > float(unstable_rg_ratio_threshold))
            )
            rows.append(
                {
                    "target": target,
                    "source_file": os.path.abspath(path),
                    "variant_id": int(i),
                    "noise_sigma_A": sigma,
                    "ca_residues": n_ca,
                    "rmsd_aligned_A": float(rmsd),
                    "min_ca_distance_A": float(min_dist),
                    "rg_native_A": float(rg_native),
                    "rg_perturbed_A": float(rg_pert),
                    "rg_delta_ratio": float(rg_ratio),
                    "stable_label": int(0 if unstable else 1),
                    "unstable_label": int(1 if unstable else 0),
                }
            )

    out_df = pd.DataFrame(rows)
    if len(out_df) == 0:
        raise RuntimeError("no augmentation rows were generated")

    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    out_df.to_csv(out_csv, index=False)

    per_target = (
        out_df.groupby("target")
        .agg(
            variants=("variant_id", "count"),
            unstable=("unstable_label", "sum"),
            stable=("stable_label", "sum"),
            mean_rmsd=("rmsd_aligned_A", "mean"),
            min_distance_min=("min_ca_distance_A", "min"),
        )
        .reset_index()
        .to_dict(orient="records")
    )
    summary = {
        "seed": int(seed),
        "manifest_csv": manifest_csv,
        "rows_total": int(len(out_df)),
        "targets": int(out_df["target"].nunique()),
        "variants_per_target": int(variants_per_target),
        "noise_sigmas": [float(x) for x in sigmas],
        "unstable_count": int(out_df["unstable_label"].sum()),
        "stable_count": int(out_df["stable_label"].sum()),
        "unstable_ratio": float(out_df["unstable_label"].mean()),
        "skipped_targets_count": int(len(skipped)),
        "skipped_targets": skipped,
        "thresholds": {
            "unstable_min_distance_threshold_A": float(unstable_min_distance_threshold),
            "unstable_rmsd_threshold_A": float(unstable_rmsd_threshold),
            "unstable_rg_ratio_threshold": float(unstable_rg_ratio_threshold),
            "min_ca_residues": int(min_ca_residues),
        },
        "per_target": per_target,
        "out_csv": out_csv,
        "out_json": out_json,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary}, f, indent=2, ensure_ascii=False)
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Build CATH structure noise-augmentation manifest with "
            "stable/unstable labels for robustness training."
        )
    )
    p.add_argument("--manifest-csv", type=str, required=True)
    p.add_argument("--out-csv", type=str, default="runs/cath_noise_augmentation.csv")
    p.add_argument("--out-json", type=str, default="runs/cath_noise_augmentation_summary.json")
    p.add_argument("--seed", type=int, default=20260219)
    p.add_argument("--variants-per-target", type=int, default=24)
    p.add_argument("--noise-sigmas", type=str, default="0.25,0.5,1.0")
    p.add_argument("--min-ca-residues", type=int, default=20)
    p.add_argument("--unstable-min-distance-threshold", type=float, default=2.8)
    p.add_argument("--unstable-rmsd-threshold", type=float, default=3.0)
    p.add_argument("--unstable-rg-ratio-threshold", type=float, default=0.25)
    return p


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    summary = build_cath_noise_augmentation(
        manifest_csv=str(args.manifest_csv),
        out_csv=str(args.out_csv),
        out_json=str(args.out_json),
        seed=int(args.seed),
        variants_per_target=int(args.variants_per_target),
        noise_sigmas=str(args.noise_sigmas),
        min_ca_residues=int(args.min_ca_residues),
        unstable_min_distance_threshold=float(args.unstable_min_distance_threshold),
        unstable_rmsd_threshold=float(args.unstable_rmsd_threshold),
        unstable_rg_ratio_threshold=float(args.unstable_rg_ratio_threshold),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
