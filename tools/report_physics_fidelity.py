#!/usr/bin/env python3

import argparse
import json
import os
from typing import Dict, List

import pandas as pd

# Avoid ROCm unsupported hipBLASLt fallback warnings during torch matmul/cdist.
os.environ.setdefault("TORCH_BLAS_PREFER_HIPBLASLT", "0")

import torch

from core.definitions import ResearchConstants
from run_validation import calculate_rg, calculate_sasa_proxy, run_target
from tools.pdb_loader import load_native_structure


def _parse_targets(spec: str) -> List[str]:
    if spec.strip().lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in spec.split(",") if x.strip()]


def _rmsd(a: torch.Tensor, b: torch.Tensor) -> float:
    return float(torch.sqrt(((a - b).pow(2).sum(dim=-1)).mean()).item())


def _thresholds_for_target(target: str) -> Dict[str, float]:
    # Keep aligned with tests/validation/test_accuracy_vs_experimental.py
    table = {
        "Chignolin": (2.0, 1.0, 80.0, 0.30),
        "Trp_Cage": (2.0, 1.0, 120.0, 0.30),
        "Villin_HP35": (2.0, 1.0, 180.0, 0.30),
        "BBA5": (2.0, 1.0, 120.0, 0.30),
        "FSD_1": (2.0, 1.0, 140.0, 0.30),
        "WW_Domain_FiP35": (2.0, 1.0, 180.0, 0.30),
        "Crambin": (2.0, 1.0, 200.0, 0.30),
        "Protein_A_Bdomain": (2.0, 1.0, 260.0, 0.30),
        "GB1_Mini": (2.0, 1.0, 240.0, 0.30),
        "Ubiquitin_Mini": (2.0, 1.0, 300.0, 0.30),
        "T. cruzi PDE": (2.0, 1.0, 800.0, 0.30),
    }
    rmsd_t, rg_t, sasa_t, edrift_t = table[target]
    return {
        "rmsd_threshold": float(rmsd_t),
        "rg_delta_threshold": float(rg_t),
        "sasa_delta_threshold": float(sasa_t),
        "energy_drift_ratio_threshold": float(edrift_t),
    }


def _passes_standard(metrics: Dict[str, float], th: Dict[str, float]) -> bool:
    return (
        float(metrics["rmsd"]) < float(th["rmsd_threshold"])
        and float(metrics["rg_delta"]) < float(th["rg_delta_threshold"])
        and float(metrics["sasa_delta"]) < float(th["sasa_delta_threshold"])
        and float(metrics["energy_drift_ratio"]) < float(th["energy_drift_ratio_threshold"])
    )


def _passes_proxy_energy_standard(metrics: Dict[str, float], th: Dict[str, float]) -> bool:
    return (
        float(metrics["rmsd"]) < float(th["rmsd_threshold"])
        and float(metrics["rg_delta"]) < float(th["rg_delta_threshold"])
        and float(metrics["sasa_delta"]) < float(th["sasa_delta_threshold"])
        and float(metrics["proxy_energy_drift_ratio"]) < float(th["energy_drift_ratio_threshold"])
    )


def _run_one_mode(
    target: str,
    mode: str,
    steps: int,
    noise: float,
    seed: int,
    refinement_dt: float,
    restraint_k: float,
    force_clip: float,
) -> Dict[str, float]:
    native, _ = load_native_structure(target)
    if native is None:
        raise FileNotFoundError(f"Native structure for {target} not found")

    coords, m = run_target(
        target=target,
        steps=steps,
        noise_scale=noise,
        seed=seed,
        return_metrics=True,
        mode=mode,
        refinement_dt=refinement_dt,
        restraint_k=restraint_k,
        force_clip=force_clip,
    )
    rmsd = _rmsd(coords, native)
    rg_delta = abs(calculate_rg(coords) - calculate_rg(native))
    sasa_delta = abs(calculate_sasa_proxy(coords) - calculate_sasa_proxy(native))
    return {
        "rmsd": float(rmsd),
        "rg_delta": float(rg_delta),
        "sasa_delta": float(sasa_delta),
        "energy_drift_ratio": float(m["energy_drift_ratio"]),
        "proxy_energy_drift_ratio": float(m.get("proxy_energy_drift_ratio", 0.0)),
    }


def run_report(
    targets: List[str],
    steps: int,
    noise: float,
    seed: int,
    restrained_dt: float,
    restrained_k: float,
    unrestrained_dt: float,
    force_clip: float,
    out_csv: str,
    out_json: str,
):
    rows = []
    for target in targets:
        th = _thresholds_for_target(target)
        restrained = _run_one_mode(
            target=target,
            mode="physics",
            steps=steps,
            noise=noise,
            seed=seed,
            refinement_dt=restrained_dt,
            restraint_k=restrained_k,
            force_clip=force_clip,
        )
        unrestrained = _run_one_mode(
            target=target,
            mode="physics_unrestrained",
            steps=steps,
            noise=noise,
            seed=seed,
            refinement_dt=unrestrained_dt,
            restraint_k=0.0,
            force_clip=force_clip,
        )

        pass_restrained = _passes_standard(restrained, th)
        pass_unrestrained = _passes_standard(unrestrained, th)
        pass_restrained_proxy = _passes_proxy_energy_standard(restrained, th)
        pass_unrestrained_proxy = _passes_proxy_energy_standard(unrestrained, th)
        rows.append(
            {
                "target": target,
                **th,
                "restrained_rmsd": restrained["rmsd"],
                "restrained_rg_delta": restrained["rg_delta"],
                "restrained_sasa_delta": restrained["sasa_delta"],
                "restrained_energy_drift_ratio": restrained["energy_drift_ratio"],
                "restrained_proxy_energy_drift_ratio": restrained["proxy_energy_drift_ratio"],
                "restrained_pass_standard": bool(pass_restrained),
                "restrained_pass_proxy_energy_standard": bool(pass_restrained_proxy),
                "unrestrained_rmsd": unrestrained["rmsd"],
                "unrestrained_rg_delta": unrestrained["rg_delta"],
                "unrestrained_sasa_delta": unrestrained["sasa_delta"],
                "unrestrained_energy_drift_ratio": unrestrained["energy_drift_ratio"],
                "unrestrained_proxy_energy_drift_ratio": unrestrained["proxy_energy_drift_ratio"],
                "unrestrained_pass_standard": bool(pass_unrestrained),
                "unrestrained_pass_proxy_energy_standard": bool(pass_unrestrained_proxy),
                "rmsd_gap_unrestrained_minus_restrained": float(unrestrained["rmsd"] - restrained["rmsd"]),
                "proxy_edrift_gap_unrestrained_minus_restrained": float(
                    unrestrained["proxy_energy_drift_ratio"] - restrained["proxy_energy_drift_ratio"]
                ),
            }
        )

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    df.to_csv(out_csv, index=False)

    summary = {
        "targets": int(len(df)),
        "restrained_pass_count": int(df["restrained_pass_standard"].sum()) if len(df) else 0,
        "unrestrained_pass_count": int(df["unrestrained_pass_standard"].sum()) if len(df) else 0,
        "restrained_proxy_pass_count": int(df["restrained_pass_proxy_energy_standard"].sum()) if len(df) else 0,
        "unrestrained_proxy_pass_count": int(df["unrestrained_pass_proxy_energy_standard"].sum()) if len(df) else 0,
        "avg_restrained_rmsd": float(df["restrained_rmsd"].mean()) if len(df) else 0.0,
        "avg_unrestrained_rmsd": float(df["unrestrained_rmsd"].mean()) if len(df) else 0.0,
        "avg_rmsd_gap_unrestrained_minus_restrained": float(df["rmsd_gap_unrestrained_minus_restrained"].mean())
        if len(df)
        else 0.0,
        "avg_restrained_proxy_energy_drift_ratio": float(df["restrained_proxy_energy_drift_ratio"].mean())
        if len(df)
        else 0.0,
        "avg_unrestrained_proxy_energy_drift_ratio": float(df["unrestrained_proxy_energy_drift_ratio"].mean())
        if len(df)
        else 0.0,
    }
    problematic = df[(df["restrained_pass_standard"] == True) & (df["unrestrained_pass_standard"] == False)]  # noqa: E712
    payload = {
        "summary": summary,
        "problematic_targets": problematic["target"].tolist(),
        "rows": rows,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Compare restrained vs unrestrained physical refinement fidelity.")
    parser.add_argument("--targets", type=str, default="all")
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--noise", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--restrained-dt", type=float, default=3e-5)
    parser.add_argument("--restrained-k", type=float, default=3.0)
    parser.add_argument("--unrestrained-dt", type=float, default=1e-5)
    parser.add_argument("--force-clip", type=float, default=200.0)
    parser.add_argument("--out-csv", type=str, default="runs/physics_fidelity_report.csv")
    parser.add_argument("--out-json", type=str, default="runs/physics_fidelity_report.json")
    args = parser.parse_args()

    run_report(
        targets=_parse_targets(args.targets),
        steps=args.steps,
        noise=args.noise,
        seed=args.seed,
        restrained_dt=args.restrained_dt,
        restrained_k=args.restrained_k,
        unrestrained_dt=args.unrestrained_dt,
        force_clip=args.force_clip,
        out_csv=args.out_csv,
        out_json=args.out_json,
    )


if __name__ == "__main__":
    main()
