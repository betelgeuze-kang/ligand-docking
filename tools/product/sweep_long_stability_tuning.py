#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tempfile
from itertools import product
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from tools.report_sparse_checkpoints import run_sparse_checkpoint_report


def _parse_targets(spec: str) -> List[str]:
    out = [x.strip() for x in str(spec).split(",") if x.strip()]
    if not out:
        raise ValueError("targets must not be empty")
    seen = set()
    uniq: List[str] = []
    for t in out:
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return uniq


def _parse_float_grid(spec: str) -> List[float]:
    vals = [float(x.strip()) for x in str(spec).split(",") if x.strip()]
    if not vals:
        raise ValueError(f"invalid float grid: {spec}")
    return vals


def _build_sparse_args(
    targets: List[str],
    runs: int,
    steps: int,
    checkpoints: str,
    noise: float,
    seed: int,
    dt_val: float,
    restraint_k: float,
    force_clip: float,
    cutoff: float,
    skin: float,
    max_neighbors: int,
    max_atoms_per_cell: int,
    rebuild_stride: int,
    force_rust: bool,
    force_backend: str,
    clash_cutoff: float,
    aligned_rmsd_threshold: float,
    energy_drift_threshold: float,
    rg_delta_threshold: float,
    max_clash_pairs: int,
    out_csv: str,
    out_summary_csv: str,
    out_json: str,
) -> argparse.Namespace:
    return SimpleNamespace(
        targets=",".join(targets),
        runs=int(runs),
        steps=int(steps),
        checkpoints=str(checkpoints),
        noise=float(noise),
        seed=int(seed),
        dt=float(dt_val),
        restraint_k=float(restraint_k),
        force_clip=float(force_clip),
        cutoff=float(cutoff),
        skin=float(skin),
        max_neighbors=int(max_neighbors),
        max_atoms_per_cell=int(max_atoms_per_cell),
        rebuild_stride=int(rebuild_stride),
        force_rust=bool(force_rust),
        force_backend=str(force_backend),
        clash_cutoff=float(clash_cutoff),
        aligned_rmsd_threshold=float(aligned_rmsd_threshold),
        energy_drift_threshold=float(energy_drift_threshold),
        rg_delta_threshold=float(rg_delta_threshold),
        max_clash_pairs=int(max_clash_pairs),
        out_csv=str(out_csv),
        out_summary_csv=str(out_summary_csv),
        out_json=str(out_json),
        strict=False,
    )


def _score_sort_key(row: pd.Series) -> tuple:
    return (
        int(row.get("gate_pass_target", 0)),
        float(row.get("pass_rate", 0.0)),
        -float(row.get("energy_drift_ratio_mean", 0.0)),
        -float(row.get("rmsd_aligned_mean", 0.0)),
        -float(row.get("rg_delta_mean", 0.0)),
        -float(row.get("clash_pairs_mean", 0.0)),
    )


def run_sweep(args: argparse.Namespace) -> Dict[str, Any]:
    targets = _parse_targets(args.targets)
    dt_grid = _parse_float_grid(args.dt_grid)
    restraint_grid = _parse_float_grid(args.restraint_grid)
    force_clip_grid = _parse_float_grid(args.force_clip_grid)
    combos = list(product(dt_grid, restraint_grid, force_clip_grid))
    if len(combos) == 0:
        raise RuntimeError("no parameter combinations generated")

    records: List[Dict[str, Any]] = []
    combo_records: List[Dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="stability_sweep_") as tdir:
        for idx, (dt_val, r_k, f_clip) in enumerate(combos, start=1):
            out_csv = os.path.join(tdir, f"metrics_{idx}.csv")
            out_summary_csv = os.path.join(tdir, f"summary_{idx}.csv")
            out_json = os.path.join(tdir, f"report_{idx}.json")

            print(
                f"[{idx}/{len(combos)}] dt={dt_val:g} restraint_k={r_k:g} force_clip={f_clip:g}",
                flush=True,
            )
            ns = _build_sparse_args(
                targets=targets,
                runs=int(args.runs),
                steps=int(args.steps),
                checkpoints=str(args.checkpoints),
                noise=float(args.noise),
                seed=int(args.seed),
                dt_val=float(dt_val),
                restraint_k=float(r_k),
                force_clip=float(f_clip),
                cutoff=float(args.cutoff),
                skin=float(args.skin),
                max_neighbors=int(args.max_neighbors),
                max_atoms_per_cell=int(args.max_atoms_per_cell),
                rebuild_stride=int(args.rebuild_stride),
                force_rust=bool(args.force_rust),
                force_backend=str(args.force_backend),
                clash_cutoff=float(args.clash_cutoff),
                aligned_rmsd_threshold=float(args.aligned_rmsd_threshold),
                energy_drift_threshold=float(args.energy_drift_threshold),
                rg_delta_threshold=float(args.rg_delta_threshold),
                max_clash_pairs=int(args.max_clash_pairs),
                out_csv=out_csv,
                out_summary_csv=out_summary_csv,
                out_json=out_json,
            )
            payload = run_sparse_checkpoint_report(ns)
            summary_df = pd.read_csv(out_summary_csv)
            final_ckpt = int(summary_df["checkpoint"].max())
            final_df = summary_df[summary_df["checkpoint"] == final_ckpt].copy()
            if final_df.empty:
                continue
            final_df["dt"] = float(dt_val)
            final_df["restraint_k"] = float(r_k)
            final_df["force_clip"] = float(f_clip)
            final_df["runs"] = int(args.runs)
            final_df["steps"] = int(args.steps)
            final_df["final_checkpoint"] = int(final_ckpt)
            final_df["gate_pass_target"] = (final_df["pass_rate"] >= 1.0).astype(int)
            final_df["combo_idx"] = int(idx)
            records.extend(final_df.to_dict(orient="records"))

            combo_records.append(
                {
                    "combo_idx": int(idx),
                    "dt": float(dt_val),
                    "restraint_k": float(r_k),
                    "force_clip": float(f_clip),
                    "targets": int(len(final_df)),
                    "pass_targets": int((final_df["pass_rate"] >= 1.0).sum()),
                    "avg_pass_rate": float(final_df["pass_rate"].mean()),
                    "avg_rmsd_aligned_mean": float(final_df["rmsd_aligned_mean"].mean()),
                    "avg_energy_drift_ratio_mean": float(final_df["energy_drift_ratio_mean"].mean()),
                    "avg_rg_delta_mean": float(final_df["rg_delta_mean"].mean()),
                    "overflow_events_sum": int(final_df["overflow_events"].sum()),
                    "payload_gate_pass": bool(payload.get("summary", {}).get("gate_pass", False)),
                }
            )

    detail_df = pd.DataFrame(records)
    if detail_df.empty:
        raise RuntimeError("sweep produced no records")
    combo_df = pd.DataFrame(combo_records).sort_values(
        ["pass_targets", "avg_pass_rate", "avg_energy_drift_ratio_mean"],
        ascending=[False, False, True],
    )
    best_global = combo_df.iloc[0].to_dict()

    best_rows: List[Dict[str, Any]] = []
    for target, g in detail_df.groupby("target", as_index=False):
        g2 = g.copy()
        g2["_sort"] = g2.apply(_score_sort_key, axis=1)
        g2 = g2.sort_values("_sort", ascending=False).drop(columns=["_sort"])
        best_rows.append(g2.iloc[0].to_dict())
    best_df = pd.DataFrame(best_rows).sort_values("target")

    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "targets": targets,
        "target_count": int(len(targets)),
        "runs": int(args.runs),
        "steps": int(args.steps),
        "checkpoints": str(args.checkpoints),
        "grid": {
            "dt_grid": dt_grid,
            "restraint_grid": restraint_grid,
            "force_clip_grid": force_clip_grid,
        },
        "combo_count": int(len(combos)),
        "best_global": {
            "dt": float(best_global["dt"]),
            "restraint_k": float(best_global["restraint_k"]),
            "force_clip": float(best_global["force_clip"]),
            "pass_targets": int(best_global["pass_targets"]),
            "avg_pass_rate": float(best_global["avg_pass_rate"]),
            "avg_energy_drift_ratio_mean": float(best_global["avg_energy_drift_ratio_mean"]),
            "avg_rmsd_aligned_mean": float(best_global["avg_rmsd_aligned_mean"]),
        },
    }

    os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_best_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_combo_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    detail_df.to_csv(args.out_csv, index=False)
    best_df.to_csv(args.out_best_csv, index=False)
    combo_df.to_csv(args.out_combo_csv, index=False)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "summary": summary,
                "files": {
                    "detail_csv": str(args.out_csv),
                    "best_csv": str(args.out_best_csv),
                    "combo_csv": str(args.out_combo_csv),
                },
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    return {"summary": summary}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Sweep long-horizon stability parameters (dt/restraint_k/force_clip) and rank best settings."
    )
    p.add_argument(
        "--targets",
        type=str,
        default="BBA5,Chignolin,FSD_1,GB1_Mini,Trp_Cage,WW_Domain_FiP35",
    )
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--steps", type=int, default=1200)
    p.add_argument("--checkpoints", type=str, default="0,100,300,600,900,1200")
    p.add_argument("--noise", type=float, default=0.08)
    p.add_argument("--seed", type=int, default=1234)

    p.add_argument("--dt-grid", type=str, default="4e-6,5e-6,6e-6,8e-6,1e-5")
    p.add_argument("--restraint-grid", type=str, default="3,5,7,9")
    p.add_argument("--force-clip-grid", type=str, default="120,160,200")

    p.add_argument("--cutoff", type=float, default=12.0)
    p.add_argument("--skin", type=float, default=2.0)
    p.add_argument("--max-neighbors", type=int, default=100)
    p.add_argument("--max-atoms-per-cell", type=int, default=64)
    p.add_argument("--rebuild-stride", type=int, default=4)
    p.add_argument("--force-rust", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--force-backend", type=str, default="auto", choices=["auto", "pytorch"])
    p.add_argument("--clash-cutoff", type=float, default=2.0)
    p.add_argument("--aligned-rmsd-threshold", type=float, default=2.0)
    p.add_argument("--energy-drift-threshold", type=float, default=0.30)
    p.add_argument("--rg-delta-threshold", type=float, default=1.0)
    p.add_argument("--max-clash-pairs", type=int, default=2)

    stamp = dt.date.today().isoformat()
    p.add_argument("--out-csv", type=str, default=f"runs/long_stability_sweep_detail_{stamp}.csv")
    p.add_argument("--out-best-csv", type=str, default=f"runs/long_stability_sweep_best_{stamp}.csv")
    p.add_argument("--out-combo-csv", type=str, default=f"runs/long_stability_sweep_combo_{stamp}.csv")
    p.add_argument("--out-json", type=str, default=f"runs/long_stability_sweep_summary_{stamp}.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = run_sweep(args)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
