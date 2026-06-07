#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd


def build_stats(
    manifest_csv: str,
    out_csv: str,
    out_json: str,
    max_samples_per_file: Optional[int] = None,
    min_global_mean_abs_force: Optional[float] = None,
    max_global_zero_like_ratio_1e6: Optional[float] = None,
) -> Dict[str, Any]:
    if not os.path.exists(manifest_csv):
        raise FileNotFoundError(f"manifest not found: {manifest_csv}")
    df = pd.read_csv(manifest_csv)
    required = {"target", "split", "output_npz"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"manifest missing required columns: {required}")
    if "error" in df.columns:
        df = df[df["error"].isna()]

    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        p = str(row["output_npz"])
        if not os.path.exists(p):
            continue
        z = np.load(p, mmap_mode="r")
        f = np.asarray(z["residual_forces"], dtype=np.float32)
        if max_samples_per_file is not None and int(max_samples_per_file) > 0 and f.shape[0] > int(max_samples_per_file):
            f = f[: int(max_samples_per_file)]
        absf = np.abs(f)
        l2 = np.linalg.norm(f, axis=-1)
        rows.append(
            {
                "target": str(row["target"]),
                "split": str(row["split"]),
                "file": p,
                "samples": int(f.shape[0]),
                "n_atoms": int(f.shape[1]),
                "mean_abs_force": float(absf.mean()),
                "std_abs_force": float(absf.std()),
                "p50_abs_force": float(np.percentile(absf, 50)),
                "p95_abs_force": float(np.percentile(absf, 95)),
                "p99_abs_force": float(np.percentile(absf, 99)),
                "max_abs_force": float(absf.max()),
                "mean_l2_force": float(l2.mean()),
                "p95_l2_force": float(np.percentile(l2, 95)),
                "max_l2_force": float(l2.max()),
                "zero_like_ratio_1e6": float((absf < 1e-6).mean()),
                "zero_like_ratio_1e5": float((absf < 1e-5).mean()),
            }
        )

    out_df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    out_df.to_csv(out_csv, index=False)

    agg = (
        out_df.groupby("target", as_index=False)
        .agg(
            files=("file", "count"),
            samples=("samples", "sum"),
            mean_abs_force=("mean_abs_force", "mean"),
            p95_abs_force=("p95_abs_force", "mean"),
            max_abs_force=("max_abs_force", "max"),
            mean_zero_like_ratio_1e6=("zero_like_ratio_1e6", "mean"),
        )
        .sort_values("mean_abs_force")
    )
    total_samples = int(out_df["samples"].sum()) if len(out_df) else 0
    if total_samples > 0:
        global_mean_abs_force = float(
            (out_df["mean_abs_force"] * out_df["samples"]).sum() / total_samples
        )
        global_zero_like_ratio_1e6 = float(
            (out_df["zero_like_ratio_1e6"] * out_df["samples"]).sum() / total_samples
        )
    else:
        global_mean_abs_force = 0.0
        global_zero_like_ratio_1e6 = 1.0

    failed_reasons: List[Dict[str, Any]] = []
    if min_global_mean_abs_force is not None and global_mean_abs_force < float(min_global_mean_abs_force):
        failed_reasons.append(
            {
                "metric": "global_mean_abs_force",
                "value": float(global_mean_abs_force),
                "threshold": float(min_global_mean_abs_force),
                "condition": "value >= threshold",
            }
        )
    if (
        max_global_zero_like_ratio_1e6 is not None
        and global_zero_like_ratio_1e6 > float(max_global_zero_like_ratio_1e6)
    ):
        failed_reasons.append(
            {
                "metric": "global_zero_like_ratio_1e6",
                "value": float(global_zero_like_ratio_1e6),
                "threshold": float(max_global_zero_like_ratio_1e6),
                "condition": "value <= threshold",
            }
        )

    summary = {
        "manifest_csv": manifest_csv,
        "files": int(len(out_df)),
        "targets": int(out_df["target"].nunique()) if len(out_df) else 0,
        "global_mean_abs_force": float(global_mean_abs_force),
        "global_zero_like_ratio_1e6": float(global_zero_like_ratio_1e6),
        "out_csv": out_csv,
        "per_target_sorted_by_mean_abs_force": agg.to_dict(orient="records"),
        "gate": {
            "pass": len(failed_reasons) == 0,
            "failed_reasons": failed_reasons,
            "min_global_mean_abs_force": (
                None if min_global_mean_abs_force is None else float(min_global_mean_abs_force)
            ),
            "max_global_zero_like_ratio_1e6": (
                None
                if max_global_zero_like_ratio_1e6 is None
                else float(max_global_zero_like_ratio_1e6)
            ),
        },
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report residual-force magnitude distribution stats for distilled NPZ shards."
    )
    parser.add_argument("--manifest-csv", type=str, default="runs/distilled_residual_manifest.csv")
    parser.add_argument("--out-csv", type=str, default="runs/distilled_residual_stats.csv")
    parser.add_argument("--out-json", type=str, default="runs/distilled_residual_stats.json")
    parser.add_argument("--max-samples-per-file", type=int, default=None)
    parser.add_argument("--min-global-mean-abs-force", type=float, default=None)
    parser.add_argument("--max-global-zero-like-ratio-1e6", type=float, default=None)
    parser.add_argument("--fail-on-threshold", action=argparse.BooleanOptionalAction, default=False)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = build_stats(
        manifest_csv=str(args.manifest_csv),
        out_csv=str(args.out_csv),
        out_json=str(args.out_json),
        max_samples_per_file=args.max_samples_per_file,
        min_global_mean_abs_force=args.min_global_mean_abs_force,
        max_global_zero_like_ratio_1e6=args.max_global_zero_like_ratio_1e6,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if bool(args.fail_on_threshold) and not bool(summary.get("gate", {}).get("pass", True)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
