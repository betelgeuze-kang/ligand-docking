#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import torch

from benchmark.performance_bench import benchmark_simulation
from core.definitions import ResearchConstants
from core.mts_policy import parse_target_interval_policy, parse_target_drift_threshold_policy


def _parse_targets(spec: str) -> List[str]:
    s = str(spec).strip()
    if s.lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in s.split(",") if x.strip()]


def _parse_neighbor_settings(spec: str) -> Dict[str, float]:
    if not spec:
        return {}
    out: Dict[str, float] = {}
    for kv in spec.split(","):
        kv = kv.strip()
        if not kv:
            continue
        if "=" not in kv:
            raise ValueError(f"invalid neighbor setting entry: {kv}")
        k, v = kv.split("=", 1)
        k = k.strip()
        v = v.strip()
        if "." in v:
            out[k] = float(v)
        else:
            try:
                out[k] = int(v)
            except ValueError:
                out[k] = float(v)
    return out


def _to_xyz(coords: np.ndarray) -> torch.Tensor:
    arr = np.asarray(coords, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError(f"expected [N,3], got {arr.shape}")
    return torch.from_numpy(arr)


def _raw_rmsd(a: torch.Tensor, b: torch.Tensor) -> float:
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch: {a.shape} vs {b.shape}")
    return float(torch.sqrt(((a - b) ** 2).sum(dim=-1).mean()).item())


def _kabsch_aligned_rmsd(a: torch.Tensor, b: torch.Tensor) -> float:
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch: {a.shape} vs {b.shape}")
    x = a - a.mean(dim=0, keepdim=True)
    y = b - b.mean(dim=0, keepdim=True)
    cov = x.transpose(0, 1) @ y
    u, _s, vh = torch.linalg.svd(cov)
    v = vh.transpose(0, 1)
    d = torch.det(u @ v.transpose(0, 1))
    if float(d.item()) < 0.0:
        u = u.clone()
        u[:, -1] *= -1.0
    r = u @ v.transpose(0, 1)
    x_aligned = x @ r
    return float(torch.sqrt(((x_aligned - y) ** 2).sum(dim=-1).mean()).item())


def run_policy_eval(args: argparse.Namespace) -> Dict[str, Any]:
    if args.force_rust:
        os.environ["FORCE_RUST_HIP"] = "1"

    targets = _parse_targets(args.targets)
    policy_map = parse_target_interval_policy(args.target_ai_interval_policy)
    drift_policy_map = parse_target_drift_threshold_policy(args.target_ai_drift_threshold_policy)
    neighbor_settings = _parse_neighbor_settings(args.neighbor_settings)
    ai_ckpt = str(getattr(args, "ai_router_checkpoint", "")).strip() or None
    ai_runtime_mode = str(getattr(args, "ai_runtime_mode", "scripted")).strip().lower()
    if ai_runtime_mode not in ("eager", "scripted", "compiled", "onnx"):
        ai_runtime_mode = "scripted"
    common_kwargs = {
        "steps": int(args.steps),
        "use_ai_router": True,
        "num_runs": int(args.runs),
        "warmup_steps": int(args.warmup_steps),
        "batch_replicas": int(args.batch_replicas),
        "ai_interval": int(args.baseline_ai_interval),
        "output_file": args.benchmark_csv,
        "neighbor_settings": neighbor_settings,
        "force_backend": str(args.force_backend),
        "random_seed": int(args.seed),
        "ai_collect_aux": bool(args.ai_collect_aux),
        "capture_final_coords": True,
        "ai_router_checkpoint": ai_ckpt,
        "ai_router_checkpoint_strict": bool(getattr(args, "ai_router_checkpoint_strict", False)),
        "ai_runtime_mode": ai_runtime_mode,
        "ai_disable_exploration": bool(getattr(args, "ai_disable_exploration", True)),
        "ai_use_hip_graph": bool(getattr(args, "ai_use_hip_graph", False)),
        "ai_graph_warmup_iters": int(getattr(args, "ai_graph_warmup_iters", 2)),
        "profile_components": bool(getattr(args, "profile_components", True)),
        "sample_gpu_metrics": bool(getattr(args, "sample_gpu_metrics", True)),
    }

    rows: List[Dict[str, Any]] = []
    for idx, target in enumerate(targets, start=1):
        print(f"[{idx}/{len(targets)}] target={target}")
        baseline = benchmark_simulation(
            target=target,
            adaptive_ai_interval=False,
            **common_kwargs,
        )
        policy = benchmark_simulation(
            target=target,
            target_ai_interval_policy=policy_map,
            adaptive_ai_interval=bool(args.adaptive_ai_interval),
            ai_interval_min=int(args.ai_interval_min),
            ai_interval_max=int(args.ai_interval_max),
            ai_downshift_factor=int(args.ai_downshift_factor),
            ai_drift_disp_threshold=float(args.ai_drift_disp_threshold),
            ai_drift_check_stride=int(args.ai_drift_check_stride),
            ai_stable_upshift_window=int(args.ai_stable_upshift_window),
            ai_interval_min_ratio=float(args.ai_interval_min_ratio),
            target_ai_drift_threshold_policy=drift_policy_map,
            **common_kwargs,
        )

        b_coords = _to_xyz(np.asarray(baseline["final_coords"], dtype=np.float32)[0])
        p_coords = _to_xyz(np.asarray(policy["final_coords"], dtype=np.float32)[0])
        rmsd_raw = _raw_rmsd(p_coords, b_coords)
        rmsd_aligned = _kabsch_aligned_rmsd(p_coords, b_coords)
        rows.append(
            {
                "target": target,
                "baseline_interval": int(baseline.get("ai_interval", args.baseline_ai_interval)),
                "policy_interval_target": int(policy.get("ai_interval_target", policy.get("ai_interval", 1))),
                "policy_interval_active_mean": float(policy.get("avg_ai_interval_active_per_step", 1.0)),
                "policy_interval_final_mean": float(policy.get("avg_ai_interval_final_per_run", 1.0)),
                "baseline_throughput_steps_per_sec": float(baseline["avg_throughput_steps_per_sec"]),
                "policy_throughput_steps_per_sec": float(policy["avg_throughput_steps_per_sec"]),
                "speedup_policy_vs_baseline": float(
                    policy["avg_throughput_steps_per_sec"] / max(baseline["avg_throughput_steps_per_sec"], 1e-8)
                ),
                "baseline_step_ms": float(baseline["avg_time_per_step_ms"]),
                "policy_step_ms": float(policy["avg_time_per_step_ms"]),
                "rmsd_vs_baseline_raw": float(rmsd_raw),
                "rmsd_vs_baseline_aligned": float(rmsd_aligned),
                "policy_ai_calls_per_run": float(policy.get("avg_ai_inference_calls_per_run", 0.0)),
                "policy_ai_reuse_per_run": float(policy.get("avg_ai_reuse_steps_per_run", 0.0)),
                "policy_forced_eval_by_drift_per_run": float(policy.get("avg_ai_forced_eval_by_drift_per_run", 0.0)),
                "policy_downshifts_per_run": float(policy.get("avg_ai_interval_downshifts_per_run", 0.0)),
                "policy_upshifts_per_run": float(policy.get("avg_ai_interval_upshifts_per_run", 0.0)),
            }
        )

    df = pd.DataFrame(rows)
    summary = {
        "targets": int(len(df)),
        "avg_speedup_policy_vs_baseline": float(df["speedup_policy_vs_baseline"].mean()),
        "min_speedup_policy_vs_baseline": float(df["speedup_policy_vs_baseline"].min()),
        "avg_rmsd_vs_baseline_aligned": float(df["rmsd_vs_baseline_aligned"].mean()),
        "median_rmsd_vs_baseline_aligned": float(df["rmsd_vs_baseline_aligned"].median()),
        "p90_rmsd_vs_baseline_aligned": float(df["rmsd_vs_baseline_aligned"].quantile(0.90)),
        "avg_policy_forced_eval_by_drift_per_run": float(df["policy_forced_eval_by_drift_per_run"].mean()),
        "avg_policy_downshifts_per_run": float(df["policy_downshifts_per_run"].mean()),
    }
    return {
        "rows_df": df,
        "summary": summary,
        "policy_map": policy_map,
        "drift_policy_map": drift_policy_map,
        "targets": targets,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Evaluate target-level MTS policy vs interval=1 baseline.")
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--steps", type=int, default=80)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--warmup-steps", type=int, default=30)
    p.add_argument("--batch-replicas", type=int, default=1)
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--baseline-ai-interval", type=int, default=1)
    p.add_argument("--target-ai-interval-policy", type=str, default="speed_opt_v2")
    p.add_argument("--target-ai-drift-threshold-policy", type=str, default="balanced_v1")
    p.add_argument("--adaptive-ai-interval", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ai-interval-min", type=int, default=1)
    p.add_argument("--ai-interval-max", type=int, default=0, help="0 means target policy interval cap")
    p.add_argument("--ai-downshift-factor", type=int, default=2)
    p.add_argument("--ai-drift-disp-threshold", type=float, default=0.25)
    p.add_argument("--ai-drift-check-stride", type=int, default=1)
    p.add_argument("--ai-stable-upshift-window", type=int, default=0)
    p.add_argument("--ai-interval-min-ratio", type=float, default=0.0)
    p.add_argument("--force-backend", type=str, default="auto", choices=["auto", "pytorch"])
    p.add_argument("--force-rust", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ai-collect-aux", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ai-router-checkpoint", type=str, default="", help="Optional AIRouter checkpoint (.pth)")
    p.add_argument(
        "--ai-router-checkpoint-strict",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Use strict=True for load_state_dict when loading AIRouter checkpoint",
    )
    p.add_argument(
        "--ai-runtime-mode",
        type=str,
        default="scripted",
        choices=["eager", "scripted", "compiled", "onnx"],
        help="AIRouter runtime mode",
    )
    p.add_argument(
        "--ai-disable-exploration",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Disable router exploration during evaluation",
    )
    p.add_argument(
        "--ai-use-hip-graph",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable HIP graph replay for AIRouter inference",
    )
    p.add_argument("--ai-graph-warmup-iters", type=int, default=2)
    p.add_argument(
        "--profile-components",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Collect timing breakdown components",
    )
    p.add_argument(
        "--sample-gpu-metrics",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Sample GPU metrics during benchmark runs",
    )
    p.add_argument(
        "--neighbor-settings",
        type=str,
        default="grid_spacing=12,cutoff=12,skin=2,max_neighbors=100,rebuild_stride=4,max_atoms_per_cell=64",
    )
    p.add_argument("--benchmark-csv", type=str, default="")
    p.add_argument("--out-csv", type=str, default="runs/target_mts_policy_eval.csv")
    p.add_argument("--out-json", type=str, default="runs/target_mts_policy_eval.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    benchmark_csv = str(args.benchmark_csv).strip() or None
    args.benchmark_csv = benchmark_csv

    out = run_policy_eval(args)
    os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    out["rows_df"].to_csv(args.out_csv, index=False)
    payload = {
        "summary": out["summary"],
        "policy_map": out["policy_map"],
        "drift_policy_map": out["drift_policy_map"],
        "targets": out["targets"],
        "out_csv": args.out_csv,
    }
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(json.dumps({"out_csv": args.out_csv, "out_json": args.out_json, "summary": out["summary"]}, indent=2))


if __name__ == "__main__":
    main()
