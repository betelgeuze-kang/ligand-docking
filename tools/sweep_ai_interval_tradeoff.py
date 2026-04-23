#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import torch

from benchmark.performance_bench import benchmark_simulation
from core.definitions import ResearchConstants
from tools.pdb_loader import load_native_structure


def _parse_targets(spec: str) -> List[str]:
    s = str(spec).strip()
    if s.lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in s.split(",") if x.strip()]


def _parse_intervals(spec: str) -> List[int]:
    vals = [int(x.strip()) for x in str(spec).split(",") if x.strip()]
    vals = sorted(set(max(v, 1) for v in vals))
    if len(vals) == 0:
        raise ValueError("ai intervals must not be empty")
    return vals


def _parse_topk_values(spec: str) -> List[int]:
    vals = [int(x.strip()) for x in str(spec).split(",") if x.strip()]
    vals = sorted(set(max(v, 0) for v in vals))
    if len(vals) == 0:
        raise ValueError("top-k values must not be empty")
    return vals


@contextmanager
def _temporary_env_var(name: str, value: Optional[str]):
    prev = os.environ.get(name)
    try:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = str(value)
        yield
    finally:
        if prev is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = prev


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


def _raw_rmsd(a: torch.Tensor, b: torch.Tensor) -> float:
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch: {a.shape} vs {b.shape}")
    return float(torch.sqrt(((a - b) ** 2).sum(dim=-1).mean()).item())


def _to_xyz(coords: np.ndarray) -> torch.Tensor:
    arr = np.asarray(coords, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError(f"expected [N,3], got {arr.shape}")
    return torch.from_numpy(arr)


def _load_native(target: str) -> torch.Tensor:
    native_coords, _ = load_native_structure(target)
    if native_coords is None:
        conf = ResearchConstants.CHALLENGES[target]
        n_res = int(conf["n_res"])
        native_coords = (
            torch.linspace(0, n_res - 1, n_res, dtype=torch.float32).view(1, n_res, 1).repeat(1, 1, 3)
        )
    if native_coords.ndim == 3:
        native_coords = native_coords[0]
    return native_coords.detach().cpu().float()


def run_sweep(
    targets: List[str],
    ai_intervals: List[int],
    topk_values: List[int],
    steps: int,
    runs: int,
    warmup_steps: int,
    batch_replicas: int,
    seed: int,
    benchmark_csv: Optional[str],
    neighbor_settings: Dict[str, float],
    force_backend: str,
    force_rust: bool,
    ai_collect_aux: bool,
    ai_router_checkpoint: Optional[str],
    ai_router_checkpoint_strict: bool,
    ai_runtime_mode: str,
    ai_disable_exploration: bool,
    ai_use_hip_graph: bool,
    ai_graph_warmup_iters: int,
) -> Dict[str, Any]:
    if force_rust:
        os.environ["FORCE_RUST_HIP"] = "1"

    rows: List[Dict[str, Any]] = []
    baseline_interval = int(ai_intervals[0])
    baseline_topk = int(topk_values[0])
    for t_idx, target in enumerate(targets, start=1):
        print(f"[{t_idx}/{len(targets)}] target={target}")
        native = _load_native(target)
        baseline_coords: Optional[torch.Tensor] = None
        baseline_throughput: Optional[float] = None

        for topk in topk_values:
            topk_env = None if int(topk) <= 0 else str(int(topk))
            with _temporary_env_var("AI_ROUTER_TOPK_ACTIVE", topk_env):
                for interval in ai_intervals:
                    result = benchmark_simulation(
                        target=target,
                        steps=int(steps),
                        use_ai_router=True,
                        num_runs=int(runs),
                        warmup_steps=int(warmup_steps),
                        batch_replicas=int(batch_replicas),
                        ai_interval=int(interval),
                        output_file=benchmark_csv,
                        neighbor_settings=neighbor_settings,
                        force_backend=str(force_backend),
                        random_seed=int(seed),
                        ai_collect_aux=bool(ai_collect_aux),
                        capture_final_coords=True,
                        ai_router_checkpoint=(str(ai_router_checkpoint).strip() or None),
                        ai_router_checkpoint_strict=bool(ai_router_checkpoint_strict),
                        ai_runtime_mode=str(ai_runtime_mode).strip().lower(),
                        ai_disable_exploration=bool(ai_disable_exploration),
                        ai_use_hip_graph=bool(ai_use_hip_graph),
                        ai_graph_warmup_iters=int(ai_graph_warmup_iters),
                    )
                    final_coords_all = np.asarray(result["final_coords"], dtype=np.float32)
                    final_coords = _to_xyz(final_coords_all[0])

                    if int(interval) == baseline_interval and int(topk) == baseline_topk:
                        baseline_coords = final_coords
                        baseline_throughput = float(result["avg_throughput_steps_per_sec"])

                    if baseline_coords is None or baseline_throughput is None:
                        raise RuntimeError("baseline (interval/topk) must be evaluated before other points")

                    rmsd_vs_baseline_raw = _raw_rmsd(final_coords, baseline_coords)
                    rmsd_vs_baseline_aligned = _kabsch_aligned_rmsd(final_coords, baseline_coords)
                    rmsd_vs_native_raw = _raw_rmsd(final_coords, native)
                    rmsd_vs_native_aligned = _kabsch_aligned_rmsd(final_coords, native)
                    throughput = float(result["avg_throughput_steps_per_sec"])

                    rows.append(
                        {
                            "target": target,
                            "ai_interval": int(interval),
                            "topk_active": int(topk),
                            "throughput_steps_per_sec": throughput,
                            "step_ms": float(result["avg_time_per_step_ms"]),
                            "ai_calls_per_run": float(result.get("avg_ai_inference_calls_per_run", 0.0)),
                            "ai_reuse_steps_per_run": float(result.get("avg_ai_reuse_steps_per_run", 0.0)),
                            "speedup_vs_baseline": float(throughput / max(baseline_throughput, 1e-8)),
                            "rmsd_vs_baseline_raw": float(rmsd_vs_baseline_raw),
                            "rmsd_vs_baseline_aligned": float(rmsd_vs_baseline_aligned),
                            "rmsd_vs_native_raw": float(rmsd_vs_native_raw),
                            "rmsd_vs_native_aligned": float(rmsd_vs_native_aligned),
                            "ai_runtime_mode": str(ai_runtime_mode).strip().lower(),
                            "ai_graph_enabled_flag": float(result.get("avg_ai_graph_enabled_flag", 0.0)),
                        }
                    )

    df = pd.DataFrame(rows)
    curve_df = (
        df.groupby(["ai_interval", "topk_active"], as_index=False)
        .agg(
            targets=("target", "nunique"),
            throughput_mean=("throughput_steps_per_sec", "mean"),
            throughput_std=("throughput_steps_per_sec", "std"),
            step_ms_mean=("step_ms", "mean"),
            speedup_vs_baseline_mean=("speedup_vs_baseline", "mean"),
            ai_calls_mean=("ai_calls_per_run", "mean"),
            ai_reuse_mean=("ai_reuse_steps_per_run", "mean"),
            rmsd_loss_raw_mean=("rmsd_vs_baseline_raw", "mean"),
            rmsd_loss_raw_std=("rmsd_vs_baseline_raw", "std"),
            rmsd_loss_aligned_mean=("rmsd_vs_baseline_aligned", "mean"),
            rmsd_loss_aligned_std=("rmsd_vs_baseline_aligned", "std"),
            rmsd_native_aligned_mean=("rmsd_vs_native_aligned", "mean"),
            ai_graph_enabled_mean=("ai_graph_enabled_flag", "mean"),
        )
        .sort_values(["ai_interval", "topk_active"])
    )

    payload = {
        "targets": targets,
        "ai_intervals": ai_intervals,
        "topk_values": topk_values,
        "baseline": {"ai_interval": baseline_interval, "topk_active": baseline_topk},
        "steps": int(steps),
        "runs": int(runs),
        "warmup_steps": int(warmup_steps),
        "batch_replicas": int(batch_replicas),
        "seed": int(seed),
        "force_backend": str(force_backend),
        "force_rust": bool(force_rust),
        "ai_collect_aux": bool(ai_collect_aux),
        "ai_router_checkpoint": (str(ai_router_checkpoint).strip() or None),
        "ai_router_checkpoint_strict": bool(ai_router_checkpoint_strict),
        "ai_runtime_mode": str(ai_runtime_mode).strip().lower(),
        "ai_disable_exploration": bool(ai_disable_exploration),
        "ai_use_hip_graph": bool(ai_use_hip_graph),
        "ai_graph_warmup_iters": int(ai_graph_warmup_iters),
        "neighbor_settings": neighbor_settings,
        "curve": curve_df.to_dict(orient="records"),
    }
    return {"target_df": df, "curve_df": curve_df, "payload": payload}


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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sweep AI MTS interval + top-k and build throughput-accuracy loss curve.")
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--ai-intervals", type=str, default="1,2,4,6,8,10")
    p.add_argument("--topk-values", type=str, default="0,4,8")
    p.add_argument("--steps", type=int, default=80)
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--warmup-steps", type=int, default=30)
    p.add_argument("--batch-replicas", type=int, default=1)
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--benchmark-csv", type=str, default="")
    p.add_argument("--force-backend", type=str, default="auto", choices=["auto", "pytorch"])
    p.add_argument("--force-rust", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ai-collect-aux", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument(
        "--ai-runtime-mode",
        type=str,
        default="eager",
        choices=["eager", "scripted", "compiled", "onnx"],
    )
    p.add_argument("--ai-disable-exploration", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ai-use-hip-graph", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ai-graph-warmup-iters", type=int, default=2)
    p.add_argument("--ai-router-checkpoint", type=str, default="", help="Optional AIRouter checkpoint (.pth)")
    p.add_argument(
        "--ai-router-checkpoint-strict",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Use strict=True for load_state_dict when loading AIRouter checkpoint",
    )
    p.add_argument(
        "--neighbor-settings",
        type=str,
        default="grid_spacing=12,cutoff=12,skin=2,max_neighbors=100,rebuild_stride=4,max_atoms_per_cell=64",
    )
    p.add_argument("--out-csv", type=str, default="runs/ai_interval_sweep_target.csv")
    p.add_argument("--out-curve-csv", type=str, default="runs/ai_interval_sweep_curve.csv")
    p.add_argument("--out-json", type=str, default="runs/ai_interval_sweep.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    targets = _parse_targets(args.targets)
    ai_intervals = _parse_intervals(args.ai_intervals)
    topk_values = _parse_topk_values(args.topk_values)
    neighbor_settings = _parse_neighbor_settings(args.neighbor_settings)
    benchmark_csv = str(args.benchmark_csv).strip() or None

    out = run_sweep(
        targets=targets,
        ai_intervals=ai_intervals,
        topk_values=topk_values,
        steps=args.steps,
        runs=args.runs,
        warmup_steps=args.warmup_steps,
        batch_replicas=args.batch_replicas,
        seed=args.seed,
        benchmark_csv=benchmark_csv,
        neighbor_settings=neighbor_settings,
        force_backend=args.force_backend,
        force_rust=bool(args.force_rust),
        ai_collect_aux=bool(args.ai_collect_aux),
        ai_router_checkpoint=(str(args.ai_router_checkpoint).strip() or None),
        ai_router_checkpoint_strict=bool(args.ai_router_checkpoint_strict),
        ai_runtime_mode=str(args.ai_runtime_mode).strip().lower(),
        ai_disable_exploration=bool(args.ai_disable_exploration),
        ai_use_hip_graph=bool(args.ai_use_hip_graph),
        ai_graph_warmup_iters=int(args.ai_graph_warmup_iters),
    )

    os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_curve_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    out["target_df"].to_csv(args.out_csv, index=False)
    out["curve_df"].to_csv(args.out_curve_csv, index=False)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(out["payload"], f, indent=2, ensure_ascii=False)

    print(json.dumps({"out_csv": args.out_csv, "out_curve_csv": args.out_curve_csv, "out_json": args.out_json}, indent=2))


if __name__ == "__main__":
    main()
