#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from tools.report_sparse_checkpoints import run_sparse_checkpoint_report


def _load_profile(path: str) -> Dict[str, Dict[str, float]]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    targets = payload.get("targets", {})
    if not isinstance(targets, dict) or len(targets) == 0:
        raise ValueError(f"invalid profile targets in {path}")
    out: Dict[str, Dict[str, float]] = {}
    for t, cfg in targets.items():
        out[str(t)] = {
            "dt": float(cfg["dt"]),
            "restraint_k": float(cfg["restraint_k"]),
            "force_clip": float(cfg["force_clip"]),
        }
    return out


def _ns(**kwargs: Any) -> argparse.Namespace:
    return SimpleNamespace(**kwargs)


def run_target_tuned_validation(args: argparse.Namespace) -> Dict[str, Any]:
    profile = _load_profile(str(args.profile_json))
    stamp = str(args.date_tag).strip() or dt.date.today().isoformat()

    if bool(args.force_rust):
        os.environ["FORCE_RUST_HIP"] = "1"
        os.environ.setdefault("RUST_HIP_USE_GPU_NBLIST_BUILDER", "1")
        os.environ.setdefault("NBLIST_AUTOGROW", "1")
        os.environ.setdefault("RUST_HIP_NBLIST_AUTOGROW", "1")

    rows: List[Dict[str, Any]] = []
    for target, cfg in profile.items():
        stem = (
            f"{args.out_prefix}_{target.lower().replace(' ', '_').replace('/', '_')}_{stamp}"
            if str(args.out_prefix).strip()
            else f"runs/long_stability_target_tuned_{target.lower().replace(' ', '_').replace('/', '_')}_{stamp}"
        )
        ns = _ns(
            targets=str(target),
            runs=int(args.runs),
            steps=int(args.steps),
            checkpoints=str(args.checkpoints),
            noise=float(args.noise),
            seed=int(args.seed),
            dt=float(cfg["dt"]),
            restraint_k=float(cfg["restraint_k"]),
            force_clip=float(cfg["force_clip"]),
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
            out_csv=f"{stem}_metrics.csv",
            out_summary_csv=f"{stem}_summary.csv",
            out_json=f"{stem}_report.json",
            strict=False,
        )
        print(
            f"[target={target}] dt={cfg['dt']:g} restraint_k={cfg['restraint_k']:g} force_clip={cfg['force_clip']:g}",
            flush=True,
        )
        _ = run_sparse_checkpoint_report(ns)
        s = pd.read_csv(ns.out_summary_csv)
        final = s[s["checkpoint"] == s["checkpoint"].max()].iloc[0].to_dict()
        rows.append(
            {
                "target": target,
                "dt": float(cfg["dt"]),
                "restraint_k": float(cfg["restraint_k"]),
                "force_clip": float(cfg["force_clip"]),
                "pass_rate": float(final["pass_rate"]),
                "rmsd_aligned_mean": float(final["rmsd_aligned_mean"]),
                "energy_drift_ratio_mean": float(final["energy_drift_ratio_mean"]),
                "rg_delta_mean": float(final["rg_delta_mean"]),
                "overflow_events": int(final["overflow_events"]),
                "gate_pass": bool(float(final["pass_rate"]) >= 1.0),
            }
        )

    df = pd.DataFrame(rows).sort_values("target")
    os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    df.to_csv(args.out_csv, index=False)
    summary = {
        "profile_json": str(args.profile_json),
        "targets": int(len(df)),
        "passed_targets": int(df["gate_pass"].sum()) if len(df) else 0,
        "failed_targets": sorted(df.loc[df["gate_pass"] == False, "target"].astype(str).tolist()) if len(df) else [],
        "avg_rmsd_aligned_mean": float(df["rmsd_aligned_mean"].mean()) if len(df) else None,
        "avg_energy_drift_ratio_mean": float(df["energy_drift_ratio_mean"].mean()) if len(df) else None,
    }
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=2, ensure_ascii=False)
    return {"summary": summary}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run long-stability validation using per-target tuned parameters from a JSON profile."
    )
    p.add_argument("--profile-json", type=str, default="config/long_stability_target_tuned_2026-02-15.json")
    p.add_argument("--runs", type=int, default=2)
    p.add_argument("--steps", type=int, default=1200)
    p.add_argument("--checkpoints", type=str, default="0,100,300,600,900,1200")
    p.add_argument("--noise", type=float, default=0.08)
    p.add_argument("--seed", type=int, default=1234)
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
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--out-prefix", type=str, default="")
    p.add_argument("--out-csv", type=str, default="runs/long_stability_target_tuned_validation.csv")
    p.add_argument("--out-json", type=str, default="runs/long_stability_target_tuned_validation.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = run_target_tuned_validation(args)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
