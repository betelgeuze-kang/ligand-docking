#!/usr/bin/env python3

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Mapping, Optional


_SPEED_PROFILE_SPECS: Dict[str, Dict[str, Any]] = {
    "balanced": {
        "description": "throughput-safe defaults",
        "ai_interval_scale": 1,
        "ai_runtime_mode": None,
        "ai_disable_exploration": None,
        "ai_use_hip_graph": None,
        "ai_graph_warmup_iters": None,
        "ai_topk_active": None,
        "ai_mask_threshold": None,
        "track_clip_hits": None,
        "profile_components": None,
        "disable_stochastic_noise": False,
        "precompute_stochastic_noise": False,
        "precompute_stochastic_noise_block_steps": 0,
        "replica_min": None,
        "env": {},
    },
    "fast": {
        "description": "high-throughput preset with scripted router + graph",
        "ai_interval_scale": 2,
        "ai_runtime_mode": "scripted",
        "ai_disable_exploration": True,
        "ai_use_hip_graph": True,
        "ai_graph_warmup_iters": 2,
        "ai_topk_active": 4,
        "ai_mask_threshold": 0.72,
        "track_clip_hits": False,
        "profile_components": False,
        "disable_stochastic_noise": False,
        "precompute_stochastic_noise": False,
        "precompute_stochastic_noise_block_steps": 0,
        "replica_min": 96,
        "env": {
            "RUST_HIP_USE_GPU_NBLIST_BUILDER": "1",
            "RUST_HIP_USE_FUSED_CELL": "1",
            "NBLIST_AUTOGROW": "1",
            "RUST_HIP_NBLIST_AUTOGROW": "1",
        },
    },
    "ultra": {
        "description": "maximum throughput profile (aggressive)",
        "ai_interval_scale": 4,
        "ai_runtime_mode": "scripted",
        "ai_disable_exploration": True,
        "ai_use_hip_graph": True,
        "ai_graph_warmup_iters": 3,
        "ai_topk_active": 2,
        "ai_mask_threshold": 0.88,
        "track_clip_hits": False,
        "profile_components": False,
        "disable_stochastic_noise": False,
        "precompute_stochastic_noise": True,
        "precompute_stochastic_noise_block_steps": 256,
        "replica_min": 64,
        "env": {
            "RUST_HIP_USE_GPU_NBLIST_BUILDER": "1",
            "RUST_HIP_USE_FUSED_CELL": "1",
            "NBLIST_AUTOGROW": "1",
            "RUST_HIP_NBLIST_AUTOGROW": "1",
        },
    },
    "turbo": {
        "description": "ultra throughput profile for maximum hardware occupancy testing",
        "ai_interval_scale": 6,
        "ai_runtime_mode": "scripted",
        "ai_disable_exploration": True,
        "ai_use_hip_graph": True,
        "ai_graph_warmup_iters": 4,
        "ai_topk_active": 1,
        "ai_mask_threshold": 0.95,
        "track_clip_hits": False,
        "profile_components": False,
        "disable_stochastic_noise": False,
        "precompute_stochastic_noise": True,
        "precompute_stochastic_noise_block_steps": 256,
        "replica_min": 128,
        "env": {
            "RUST_HIP_USE_GPU_NBLIST_BUILDER": "1",
            "RUST_HIP_USE_FUSED_CELL": "1",
            "NBLIST_AUTOGROW": "1",
            "RUST_HIP_NBLIST_AUTOGROW": "1",
            "RUST_HIP_NBLIST_AUTOGROW_ROUNDS": "2",
        },
    },
    "extreme": {
        "description": "maximum throughput profile for sustained occupancy stress tests",
        "ai_interval_scale": 10,
        "ai_runtime_mode": "scripted",
        "ai_disable_exploration": True,
        "ai_use_hip_graph": True,
        "ai_graph_warmup_iters": 6,
        "ai_topk_active": 1,
        "ai_mask_threshold": 0.98,
        "track_clip_hits": False,
        "profile_components": False,
        "disable_stochastic_noise": False,
        "precompute_stochastic_noise": True,
        "precompute_stochastic_noise_block_steps": 256,
        "replica_min": 256,
        "env": {
            "RUST_HIP_USE_GPU_NBLIST_BUILDER": "1",
            "RUST_HIP_USE_FUSED_CELL": "1",
            "NBLIST_AUTOGROW": "1",
            "RUST_HIP_NBLIST_AUTOGROW": "1",
            "RUST_HIP_NBLIST_AUTOGROW_ROUNDS": "3",
        },
    },
    "warp": {
        "description": "high-pressure profile prioritizing sustained kernel occupancy",
        "ai_interval_scale": 20,
        "ai_runtime_mode": "scripted",
        "ai_disable_exploration": True,
        "ai_use_hip_graph": True,
        "ai_graph_warmup_iters": 8,
        "ai_topk_active": 1,
        "ai_mask_threshold": 0.995,
        "track_clip_hits": False,
        "profile_components": False,
        "disable_stochastic_noise": False,
        "precompute_stochastic_noise": True,
        "precompute_stochastic_noise_block_steps": 256,
        "replica_min": 512,
        "sample_gpu_metrics": False,
        "env": {
            "RUST_HIP_USE_GPU_NBLIST_BUILDER": "1",
            "RUST_HIP_USE_FUSED_CELL": "1",
            "NBLIST_AUTOGROW": "1",
            "RUST_HIP_NBLIST_AUTOGROW": "1",
            "RUST_HIP_NBLIST_AUTOGROW_ROUNDS": "4",
        },
    },
    "titan": {
        "description": "maximum-throughput experimental profile for aggressive throughput sweeps",
        "ai_interval_scale": 30,
        "ai_runtime_mode": "scripted",
        "ai_disable_exploration": True,
        "ai_use_hip_graph": True,
        "ai_graph_warmup_iters": 10,
        "ai_topk_active": 1,
        "ai_mask_threshold": 0.999,
        "track_clip_hits": False,
        "profile_components": False,
        "disable_stochastic_noise": False,
        "precompute_stochastic_noise": True,
        "precompute_stochastic_noise_block_steps": 256,
        "replica_min": 768,
        "sample_gpu_metrics": False,
        "env": {
            "RUST_HIP_USE_GPU_NBLIST_BUILDER": "1",
            "RUST_HIP_USE_FUSED_CELL": "1",
            "NBLIST_AUTOGROW": "1",
            "RUST_HIP_NBLIST_AUTOGROW": "1",
            "RUST_HIP_NBLIST_AUTOGROW_ROUNDS": "4",
        },
    },
    "max": {
        "description": "maximum sustained profile for extreme throughput experiments",
        "ai_interval_scale": 40,
        "ai_runtime_mode": "scripted",
        "ai_disable_exploration": True,
        "ai_use_hip_graph": True,
        "ai_graph_warmup_iters": 12,
        "ai_topk_active": 1,
        "ai_mask_threshold": 0.999,
        "track_clip_hits": False,
        "profile_components": False,
        "disable_stochastic_noise": False,
        "precompute_stochastic_noise": True,
        "precompute_stochastic_noise_block_steps": 512,
        "replica_min": 1024,
        "sample_gpu_metrics": False,
        "env": {
            "RUST_HIP_USE_GPU_NBLIST_BUILDER": "1",
            "RUST_HIP_USE_FUSED_CELL": "1",
            "NBLIST_AUTOGROW": "1",
            "RUST_HIP_NBLIST_AUTOGROW": "1",
            "RUST_HIP_NBLIST_AUTOGROW_ROUNDS": "5",
        },
    },
}


def resolve_speed_profile(
    mode: str,
    *,
    ai_interval: int,
    benchmark_replicas: int,
    ai_runtime_mode: str = "eager",
    ai_disable_exploration: bool = False,
    ai_use_hip_graph: bool = False,
    ai_graph_warmup_iters: int = 2,
    track_clip_hits: bool = True,
    profile_components: bool = True,
    disable_stochastic_noise: bool = False,
    precompute_stochastic_noise: bool = False,
    precompute_stochastic_noise_block_steps: int = 0,
    sample_gpu_metrics: Optional[bool] = None,
    speed_mode_replicas: int = 0,
    speed_profile_max_replicas: Optional[int] = None,
    preserve_ai_runtime_mode: bool = False,
) -> Dict[str, Any]:
    mode_i = str(mode).strip().lower()
    if mode_i not in _SPEED_PROFILE_SPECS:
        mode_i = "balanced"
    spec = _SPEED_PROFILE_SPECS[mode_i]

    base_interval = max(int(ai_interval), 1)
    base_replicas = max(int(benchmark_replicas), 1)
    scale = max(int(spec.get("ai_interval_scale", 1)), 1)

    resolved_replicas = base_replicas
    replica_min = spec.get("replica_min")
    if isinstance(replica_min, int) and replica_min > resolved_replicas:
        resolved_replicas = replica_min

    override_replicas = int(speed_mode_replicas)
    if override_replicas > 0:
        resolved_replicas = max(resolved_replicas, override_replicas)

    if speed_profile_max_replicas is not None:
        resolved_replicas = min(resolved_replicas, int(max(speed_profile_max_replicas, 1)))

    def _resolve_val(key: str, default: Any) -> Any:
        raw = spec.get(key)
        return default if raw is None else raw

    requested_ai_runtime_mode = str(ai_runtime_mode).strip().lower()
    profile_ai_runtime_mode = spec.get("ai_runtime_mode")
    if not preserve_ai_runtime_mode and profile_ai_runtime_mode is not None:
        resolved_ai_runtime_mode = str(profile_ai_runtime_mode).strip().lower()
    else:
        resolved_ai_runtime_mode = requested_ai_runtime_mode

    resolved: Dict[str, Any] = {
        "mode": mode_i,
        "description": spec.get("description", "").strip(),
        "ai_interval": base_interval * scale,
        "benchmark_replicas": resolved_replicas,
        "ai_runtime_mode": resolved_ai_runtime_mode,
        "ai_runtime_mode_requested": requested_ai_runtime_mode,
        "ai_runtime_mode_profile": (
            str(profile_ai_runtime_mode).strip().lower()
            if profile_ai_runtime_mode is not None
            else None
        ),
        "ai_runtime_mode_preserved": bool(preserve_ai_runtime_mode),
        "ai_disable_exploration": bool(_resolve_val("ai_disable_exploration", ai_disable_exploration)),
        "ai_use_hip_graph": bool(_resolve_val("ai_use_hip_graph", ai_use_hip_graph)),
        "ai_graph_warmup_iters": int(_resolve_val("ai_graph_warmup_iters", ai_graph_warmup_iters)),
        "track_clip_hits": bool(_resolve_val("track_clip_hits", track_clip_hits)),
        "profile_components": bool(_resolve_val("profile_components", profile_components)),
        "disable_stochastic_noise": bool(_resolve_val("disable_stochastic_noise", disable_stochastic_noise)),
        "precompute_stochastic_noise": bool(_resolve_val("precompute_stochastic_noise", precompute_stochastic_noise)),
        "precompute_stochastic_noise_block_steps": max(
            int(_resolve_val("precompute_stochastic_noise_block_steps", precompute_stochastic_noise_block_steps)),
            0,
        ),
        "sample_gpu_metrics": bool(_resolve_val("sample_gpu_metrics", sample_gpu_metrics if sample_gpu_metrics is not None else True)),
    }
    hip_graph_experimental = str(
        os.getenv("AI_ROUTER_ENABLE_HIP_GRAPH_EXPERIMENTAL", "0")
    ).strip().lower() in ("1", "true", "yes", "on")
    if not hip_graph_experimental:
        resolved["ai_use_hip_graph"] = False

    env = dict(spec.get("env", {}))
    topk_active = spec.get("ai_topk_active")
    if topk_active is not None:
        env["AI_ROUTER_TOPK_ACTIVE"] = str(int(topk_active))

    mask_threshold = spec.get("ai_mask_threshold")
    if mask_threshold is not None:
        env["AI_ROUTER_MASK_THRESHOLD"] = str(float(mask_threshold))

    env["AI_ROUTER_RUNTIME_MODE"] = resolved["ai_runtime_mode"]
    env["AI_ROUTER_DISABLE_EXPLORATION"] = "1" if resolved["ai_disable_exploration"] else "0"
    env.setdefault("AI_ROUTER_SKIP_ZERO_SPECIALISTS", "1")
    env.setdefault("AI_ROUTER_ASSUME_BRANCH_ZERO", "1")
    fused_cell_experimental = str(
        os.getenv("RUST_HIP_ENABLE_FUSED_CELL_EXPERIMENTAL", "0")
    ).strip().lower() in ("1", "true", "yes", "on")
    env["RUST_HIP_USE_FUSED_CELL"] = "1" if fused_cell_experimental else "0"

    resolved["env"] = env
    return resolved


@contextmanager
def apply_speed_profile_env(overrides: Optional[Mapping[str, str]]) -> Iterator[None]:
    if not overrides:
        yield
        return

    prev: Dict[str, Optional[str]] = {}
    touched: list = []
    for key, raw_value in overrides.items():
        val = str(raw_value)
        prev[key] = os.environ.get(key)
        os.environ[key] = val
        touched.append(key)

    try:
        yield
    finally:
        for key in touched:
            old = prev.get(key)
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
