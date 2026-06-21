#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import torch

from core.config import config
from core.definitions import ResearchConstants
from core.forcefield import ForceField
from core.topology import TopologyFactory
from betelgeuze_engine.physics.neighbor import (
    CellListNeighborProvider,
    NeighborProviderConfig,
)
from run_validation import calculate_proxy_energy, calculate_rg, calculate_sasa_proxy
from tools.pdb_loader import load_native_structure

DEFAULT_CLASH_DIAGNOSTIC_MAX_NEIGHBORS = 128


def _parse_targets(spec: str) -> List[str]:
    if str(spec).strip().lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in str(spec).split(",") if x.strip()]


def _parse_checkpoints(spec: str, steps: int) -> List[int]:
    raw = [int(x.strip()) for x in str(spec).split(",") if x.strip()]
    if len(raw) == 0:
        raise ValueError("checkpoints must not be empty")
    if any(x < 0 for x in raw):
        raise ValueError("checkpoints must be >= 0")
    pts = sorted(set(raw + [0]))
    if max(pts) > int(steps):
        raise ValueError(f"max checkpoint {max(pts)} cannot exceed steps {int(steps)}")
    return pts


def _rmsd_raw(coords1: torch.Tensor, coords2: torch.Tensor) -> float:
    diff = coords1 - coords2
    return float(torch.sqrt(diff.pow(2).sum(dim=-1).mean()).item())


def _rmsd_aligned(coords1: torch.Tensor, coords2: torch.Tensor) -> float:
    if coords1.shape != coords2.shape:
        raise ValueError(f"shape mismatch: {coords1.shape} vs {coords2.shape}")
    x = coords1 - coords1.mean(dim=0, keepdim=True)
    y = coords2 - coords2.mean(dim=0, keepdim=True)
    cov = x.transpose(0, 1) @ y
    u, _s, vh = torch.linalg.svd(cov)
    v = vh.transpose(0, 1)
    d = torch.det(u @ v.transpose(0, 1))
    if float(d.item()) < 0.0:
        u = u.clone()
        u[:, -1] *= -1.0
    r = u @ v.transpose(0, 1)
    xa = x @ r
    diff = xa - y
    return float(torch.sqrt(diff.pow(2).sum(dim=-1).mean()).item())


def _clash_pairs(
    coords: torch.Tensor,
    clash_cutoff: float,
    *,
    max_dense_atoms: int = DEFAULT_CLASH_DIAGNOSTIC_MAX_NEIGHBORS,
    max_neighbors: int | None = None,
) -> int:
    n = int(coords.shape[0])
    if n < 2:
        return 0
    neighbor_cap = int(max_neighbors if max_neighbors is not None else max_dense_atoms)
    pairs = CellListNeighborProvider(
        NeighborProviderConfig(
            cutoff=float(clash_cutoff),
            max_neighbor_count=neighbor_cap,
            max_atoms_per_cell=max(8, neighbor_cap),
        )
    ).build(coords.reshape(1, n, 3))
    diagnostics = dict(pairs.diagnostics)
    if diagnostics.get("overflow") is True:
        raise ValueError(
            "sparse_checkpoint_clash_pairs neighbor provider overflow; "
            f"max_observed_neighbors={diagnostics.get('max_observed_neighbors')}"
        )
    idx_cpu = pairs.idx[0].detach().cpu()
    mask_cpu = pairs.mask[0].detach().cpu()
    clashes: set[tuple[int, int]] = set()
    for i in range(n):
        for j in idx_cpu[i][mask_cpu[i]].tolist():
            j = int(j)
            if abs(i - j) <= 1:
                continue
            a, b = (i, j) if i < j else (j, i)
            clashes.add((a, b))
    return int(len(clashes))


def _make_forcefield(target: str, force_backend: str, neighbor_settings: Dict[str, Any]) -> ForceField:
    t_conf = ResearchConstants.CHALLENGES[target]
    top = TopologyFactory(
        n_res=int(t_conf["n_res"]),
        t_type=str(t_conf["type"]),
        box_size=t_conf["box"],
        device=config.DEVICE,
        target_name=target,
    )
    ff = ForceField(
        top=top,
        params={"d_e": 20.0, "eps_solv": 25.0, "sigma": 3.8, "r0": 4.2},
        neighbor_settings=neighbor_settings,
        force_backend=force_backend,
    ).to(config.DEVICE)
    return ff


def _gate_pass(row: Dict[str, Any], th: Dict[str, float]) -> bool:
    return bool(
        float(row["rmsd_aligned"]) <= float(th["aligned_rmsd_threshold"])
        and float(row["energy_drift_ratio"]) <= float(th["energy_drift_threshold"])
        and float(row["rg_delta"]) <= float(th["rg_delta_threshold"])
        and int(row["clash_pairs"]) <= int(th["max_clash_pairs"])
        and int(row["overflow_flag"]) <= 0
    )


def run_sparse_checkpoint_report(args: argparse.Namespace) -> Dict[str, Any]:
    targets = _parse_targets(args.targets)
    checkpoints = _parse_checkpoints(args.checkpoints, steps=int(args.steps))
    max_step = int(max(checkpoints))
    if bool(args.force_rust):
        os.environ["FORCE_RUST_HIP"] = "1"
        os.environ.setdefault("RUST_HIP_USE_GPU_NBLIST_BUILDER", "1")
    os.environ.setdefault("NBLIST_AUTOGROW", "1")
    os.environ.setdefault("RUST_HIP_NBLIST_AUTOGROW", "1")

    thresholds = {
        "aligned_rmsd_threshold": float(args.aligned_rmsd_threshold),
        "energy_drift_threshold": float(args.energy_drift_threshold),
        "rg_delta_threshold": float(args.rg_delta_threshold),
        "max_clash_pairs": int(args.max_clash_pairs),
    }

    neighbor_settings = {
        "grid_spacing": float(args.cutoff),
        "cutoff": float(args.cutoff),
        "skin": float(args.skin),
        "max_neighbors": int(args.max_neighbors),
        "max_atoms_per_cell": int(args.max_atoms_per_cell),
        "rebuild_stride": int(args.rebuild_stride),
    }

    rows: List[Dict[str, Any]] = []
    for t_idx, target in enumerate(targets):
        native, _ = load_native_structure(target)
        if native is None:
            raise FileNotFoundError(f"native structure not found for {target}")
        native = native.to(config.DEVICE, dtype=torch.float32)
        native_batch = native.unsqueeze(0)
        t_conf = ResearchConstants.CHALLENGES[target]
        ff = _make_forcefield(target=target, force_backend=str(args.force_backend), neighbor_settings=neighbor_settings)

        native_rg = float(calculate_rg(native))
        native_sasa = float(calculate_sasa_proxy(native))
        native_proxy_e = float(calculate_proxy_energy(native))

        for run_idx in range(int(args.runs)):
            seed_i = int(args.seed) + (t_idx * 1000) + run_idx
            gen = torch.Generator(device=config.DEVICE)
            gen.manual_seed(int(seed_i))
            c = native_batch + torch.randn((1, native.shape[0], 3), generator=gen, device=config.DEVICE) * float(
                args.noise
            )

            start_energy: Optional[float] = None
            for step in range(max_step + 1):
                with torch.no_grad():
                    f_core, pe = ff.compute(c, None)
                    energy = float(pe.squeeze().item()) if pe.numel() > 0 else 0.0

                if start_energy is None:
                    start_energy = energy

                if step in checkpoints:
                    coords = c.squeeze(0).detach()
                    rg = float(calculate_rg(coords))
                    sasa = float(calculate_sasa_proxy(coords))
                    proxy_e = float(calculate_proxy_energy(coords))
                    row = {
                        "target": target,
                        "run_idx": int(run_idx),
                        "seed": int(seed_i),
                        "checkpoint": int(step),
                        "rmsd_raw": float(_rmsd_raw(coords, native)),
                        "rmsd_aligned": float(_rmsd_aligned(coords, native)),
                        "rg": float(rg),
                        "rg_delta": float(abs(rg - native_rg)),
                        "sasa": float(sasa),
                        "sasa_delta": float(abs(sasa - native_sasa)),
                        "energy": float(energy),
                        "energy_drift_ratio": float(abs(energy - start_energy) / (abs(start_energy) + 1e-8)),
                        "proxy_energy": float(proxy_e),
                        "proxy_energy_drift_ratio": float(abs(proxy_e - native_proxy_e) / (abs(native_proxy_e) + 1e-8)),
                        "clash_pairs": int(
                            _clash_pairs(
                                coords,
                                clash_cutoff=float(args.clash_cutoff),
                                max_neighbors=int(args.clash_diagnostic_max_neighbors),
                            )
                        ),
                        "overflow_flag": int(
                            int(getattr(ff.sh, "_last_neighbor_saturated_atoms", 0)) > 0
                            or bool((getattr(ff.rust_backend, "last_neighbor_build_stats", {}) or {}).get("cell_overflow", False))
                            or bool((getattr(ff.rust_backend, "last_neighbor_build_stats", {}) or {}).get("neighbor_saturated", False))
                        ),
                    }
                    row["pass_gate"] = bool(_gate_pass(row, thresholds))
                    rows.append(row)

                if step < max_step:
                    with torch.no_grad():
                        f_total = f_core - float(args.restraint_k) * (c - native_batch)
                        if float(args.force_clip) > 0.0:
                            f_total = torch.clamp(f_total, min=-float(args.force_clip), max=float(args.force_clip))
                        c = c + float(args.dt) * f_total

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("no rows generated in sparse checkpoint report")

    group_cols = ["target", "checkpoint"]
    summary_df = (
        df.groupby(group_cols, as_index=False)
        .agg(
            rows=("pass_gate", "count"),
            pass_rate=("pass_gate", "mean"),
            rmsd_aligned_mean=("rmsd_aligned", "mean"),
            rmsd_aligned_std=("rmsd_aligned", "std"),
            energy_drift_ratio_mean=("energy_drift_ratio", "mean"),
            rg_delta_mean=("rg_delta", "mean"),
            clash_pairs_mean=("clash_pairs", "mean"),
            overflow_events=("overflow_flag", "sum"),
        )
        .sort_values(["target", "checkpoint"])
    )
    summary_df["pass_rate"] = summary_df["pass_rate"].fillna(0.0)
    summary_df["rmsd_aligned_std"] = summary_df["rmsd_aligned_std"].fillna(0.0)

    final_ckpt = int(max(checkpoints))
    final_df = summary_df[summary_df["checkpoint"] == final_ckpt].copy()
    final_pass_targets = sorted(final_df[final_df["pass_rate"] >= 1.0]["target"].astype(str).tolist())
    failed_targets = sorted(set(targets) - set(final_pass_targets))

    payload = {
        "summary": {
            "targets": int(len(targets)),
            "runs_per_target": int(args.runs),
            "checkpoints": checkpoints,
            "final_checkpoint": final_ckpt,
            "final_pass_targets": final_pass_targets,
            "failed_targets": failed_targets,
            "gate_pass": bool(len(failed_targets) == 0),
            "thresholds": thresholds,
        },
        "files": {
            "metrics_csv": str(args.out_csv),
            "summary_csv": str(args.out_summary_csv),
        },
    }

    os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_summary_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    df.to_csv(str(args.out_csv), index=False)
    summary_df.to_csv(str(args.out_summary_csv), index=False)
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run sparse-checkpoint physics/structure validation without storing full trajectories."
    )
    parser.add_argument("--targets", type=str, default="all")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--checkpoints", type=str, default="0,10,30,60")
    parser.add_argument("--noise", type=float, default=0.08)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--dt", type=float, default=1e-5)
    parser.add_argument("--restraint-k", type=float, default=3.0)
    parser.add_argument("--force-clip", type=float, default=200.0)
    parser.add_argument("--cutoff", type=float, default=12.0)
    parser.add_argument("--skin", type=float, default=2.0)
    parser.add_argument("--max-neighbors", type=int, default=100)
    parser.add_argument("--max-atoms-per-cell", type=int, default=64)
    parser.add_argument("--rebuild-stride", type=int, default=4)
    parser.add_argument("--force-rust", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--force-backend", type=str, default="auto", choices=["auto", "pytorch"])
    parser.add_argument("--clash-cutoff", type=float, default=2.0)
    parser.add_argument(
        "--clash-diagnostic-max-neighbors",
        type=int,
        default=DEFAULT_CLASH_DIAGNOSTIC_MAX_NEIGHBORS,
    )
    parser.add_argument(
        "--max-dense-diagnostic-atoms",
        type=int,
        default=DEFAULT_CLASH_DIAGNOSTIC_MAX_NEIGHBORS,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--aligned-rmsd-threshold", type=float, default=2.0)
    parser.add_argument("--energy-drift-threshold", type=float, default=0.30)
    parser.add_argument("--rg-delta-threshold", type=float, default=1.0)
    parser.add_argument("--max-clash-pairs", type=int, default=2)
    parser.add_argument("--out-csv", type=str, default="runs/sparse_checkpoint_metrics.csv")
    parser.add_argument("--out-summary-csv", type=str, default="runs/sparse_checkpoint_summary.csv")
    parser.add_argument("--out-json", type=str, default="runs/sparse_checkpoint_report.json")
    parser.add_argument("--strict", action=argparse.BooleanOptionalAction, default=False)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = run_sparse_checkpoint_report(args)
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(2)
    print(json.dumps(payload["summary"], indent=2))
    if bool(args.strict) and not bool(payload["summary"]["gate_pass"]):
        sys.exit(2)


if __name__ == "__main__":
    main()
