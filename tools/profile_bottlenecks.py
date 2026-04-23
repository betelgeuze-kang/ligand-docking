#!/usr/bin/env python3

import argparse
import json
import os

from benchmark.performance_bench import benchmark_simulation
from core.config import config
from core.rust_hip_backend import probe_rust_hip_backend


def _parse_neighbor_settings(spec: str):
    if not spec:
        return {}
    out = {}
    for kv in spec.split(","):
        kv = kv.strip()
        if not kv:
            continue
        if "=" not in kv:
            raise ValueError(f"Invalid neighbor setting '{kv}', expected key=value")
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


def run_profile(
    target: str,
    steps: int,
    runs: int,
    warmup_steps: int,
    batch_replicas: int,
    ai_interval: int,
    use_ai_router: bool,
    enable_physics_filter: bool,
    physics_filter_mode: str,
    physics_filter_max_energy_drift: float,
    physics_filter_max_momentum_drift: float,
    physics_filter_min_interatomic_distance: float,
    force_rust: bool,
    neighbor_settings: dict,
    ai_router_checkpoint: str,
    ai_router_checkpoint_strict: bool,
):
    if force_rust:
        os.environ["FORCE_RUST_HIP"] = "1"

    status = probe_rust_hip_backend(device=config.DEVICE)
    result = benchmark_simulation(
        target=target,
        steps=steps,
        use_ai_router=use_ai_router,
        num_runs=runs,
        warmup_steps=warmup_steps,
        batch_replicas=batch_replicas,
        ai_interval=ai_interval,
        enable_physics_filter=enable_physics_filter,
        physics_filter_mode=physics_filter_mode,
        physics_filter_max_energy_drift=physics_filter_max_energy_drift,
        physics_filter_max_momentum_drift=physics_filter_max_momentum_drift,
        physics_filter_min_interatomic_distance=physics_filter_min_interatomic_distance,
        output_file="benchmark_results.csv",
        neighbor_settings=neighbor_settings,
        ai_router_checkpoint=(str(ai_router_checkpoint).strip() or None),
        ai_router_checkpoint_strict=bool(ai_router_checkpoint_strict),
    )

    report = {
        "target": target,
        "steps": steps,
        "runs": runs,
        "warmup_steps": int(warmup_steps),
        "batch_replicas": int(batch_replicas),
        "ai_interval": int(ai_interval),
        "use_ai_router": use_ai_router,
        "enable_physics_filter": bool(enable_physics_filter),
        "physics_filter_mode": str(physics_filter_mode),
        "force_rust": force_rust,
        "ai_router_checkpoint": (str(ai_router_checkpoint).strip() or None),
        "ai_router_checkpoint_strict": bool(ai_router_checkpoint_strict),
        "rust_hip": {
            "enabled": status.enabled,
            "reason": status.reason,
            "kernel_name": status.kernel_name,
            "module_path": status.module_path,
            "torch_cuda_available": status.torch_cuda_available,
            "kfd_accessible": status.kfd_accessible,
        },
        "performance": result,
        "neighbor_settings": neighbor_settings,
    }
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Profile simulation bottlenecks and Rust HIP status.")
    parser.add_argument("--target", type=str, default="Chignolin")
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--warmup-steps", type=int, default=40)
    parser.add_argument("--batch-replicas", type=int, default=1)
    parser.add_argument("--ai-interval", type=int, default=1, help="AI correction interval (MTS)")
    parser.add_argument("--use-ai-router", action="store_true")
    parser.add_argument("--enable-physics-filter", action="store_true")
    parser.add_argument("--physics-filter-mode", type=str, default="rollback", choices=["rollback", "hard_fail"])
    parser.add_argument("--physics-filter-max-energy-drift", type=float, default=0.015)
    parser.add_argument("--physics-filter-max-momentum-drift", type=float, default=0.015)
    parser.add_argument("--physics-filter-min-interatomic-distance", type=float, default=0.0)
    parser.add_argument("--force-rust", action="store_true")
    parser.add_argument("--ai-router-checkpoint", type=str, default="", help="Optional AIRouter checkpoint (.pth)")
    parser.add_argument("--ai-router-checkpoint-strict", action="store_true")
    parser.add_argument(
        "--neighbor-settings",
        type=str,
        default="",
        help="Comma separated key=value, e.g. grid_spacing=12,cutoff=12,skin=2,max_neighbors=100,rebuild_stride=4,max_atoms_per_cell=64",
    )
    args = parser.parse_args()
    neighbor_settings = _parse_neighbor_settings(args.neighbor_settings)
    run_profile(
        target=args.target,
        steps=args.steps,
        runs=args.runs,
        warmup_steps=args.warmup_steps,
        batch_replicas=args.batch_replicas,
        ai_interval=args.ai_interval,
        use_ai_router=args.use_ai_router,
        enable_physics_filter=args.enable_physics_filter,
        physics_filter_mode=args.physics_filter_mode,
        physics_filter_max_energy_drift=args.physics_filter_max_energy_drift,
        physics_filter_max_momentum_drift=args.physics_filter_max_momentum_drift,
        physics_filter_min_interatomic_distance=args.physics_filter_min_interatomic_distance,
        force_rust=args.force_rust,
        neighbor_settings=neighbor_settings,
        ai_router_checkpoint=args.ai_router_checkpoint,
        ai_router_checkpoint_strict=args.ai_router_checkpoint_strict,
    )


if __name__ == "__main__":
    main()
