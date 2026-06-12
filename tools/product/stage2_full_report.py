#!/usr/bin/env python3

import argparse
import json
import os
from typing import Dict, List

import pandas as pd
import torch

from benchmark.performance_bench import benchmark_simulation
from core.config import config
from core.definitions import ResearchConstants
from core.forcefield import ForceField
from core.mts_policy import parse_target_drift_threshold_policy, parse_target_interval_policy
from core.topology import TopologyFactory
from tools.speed_profile import apply_speed_profile_env, resolve_speed_profile
from tools.pdb_loader import load_native_structure


def _parse_targets(spec: str) -> List[str]:
    if spec.strip().lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in spec.split(",") if x.strip()]


def _load_native(target: str, n_res: int) -> torch.Tensor:
    native_coords, _ = load_native_structure(target)
    if native_coords is None:
        native_coords = (
            torch.linspace(0, n_res - 1, n_res, device=config.DEVICE)
            .view(1, n_res, 1)
            .repeat(1, 1, 3)
        )
    elif native_coords.dim() == 2:
        native_coords = native_coords.unsqueeze(0)
    return native_coords.to(config.DEVICE)


def estimate_force_rmse(
    target: str,
    neighbor_settings: Dict[str, float],
    samples: int,
    noise: float,
    reference_cutoff: float,
    reference_max_neighbors: int,
    force_backend: str,
) -> float:
    t_conf = ResearchConstants.CHALLENGES[target]
    n_res = t_conf["n_res"]
    box = torch.as_tensor(t_conf["box"], dtype=torch.float32, device=config.DEVICE)
    top = TopologyFactory(n_res, t_conf["type"], t_conf["box"], config.DEVICE, target_name=target)
    ff = ForceField(
        top,
        params={"d_e": 20.0, "eps_solv": 25.0, "sigma": 3.8, "r0": 4.2},
        neighbor_settings=neighbor_settings,
        force_backend=force_backend,
    ).to(config.DEVICE)
    native = _load_native(target, n_res)

    vals: List[float] = []
    with torch.no_grad():
        for _ in range(samples):
            c = native + torch.randn_like(native) * noise
            c = torch.remainder(c, box.view(1, 1, 3))
            f_pred, _ = ff.compute(c, None)
            f_ref, _ = ff.compute_reference_pytorch(
                c, cutoff=reference_cutoff, max_neighbors=reference_max_neighbors, skin=0.0
            )
            rmse = torch.sqrt(torch.mean((f_pred - f_ref) ** 2)).item()
            vals.append(rmse)
    return float(sum(vals) / max(len(vals), 1))


def _component_breakdown_needs_probe(perf: Dict[str, object]) -> bool:
    keys = (
        "neighbor_time_per_step_ms",
        "force_time_per_step_ms",
        "ai_time_per_step_ms",
        "integrator_time_per_step_ms",
    )
    for key in keys:
        try:
            if float(perf.get(key, 0.0) or 0.0) > 0.0:
                return False
        except Exception:
            continue
    return True


def _pick_breakdown_value(perf_primary: Dict[str, object], perf_probe: Dict[str, object], key: str) -> float:
    try:
        v = float(perf_primary.get(key, 0.0) or 0.0)
    except Exception:
        v = 0.0
    if v > 0.0:
        return v
    try:
        return float(perf_probe.get(key, 0.0) or 0.0)
    except Exception:
        return 0.0


def _run_breakdown_probe(
    *,
    target: str,
    steps: int,
    warmup_steps: int,
    runs: int,
    use_ai_router: bool,
    benchmark_replicas: int,
    ai_interval: int,
    target_ai_interval_policy,
    adaptive_ai_interval: bool,
    ai_interval_min: int,
    ai_interval_max: int,
    ai_downshift_factor: int,
    ai_drift_disp_threshold: float,
    ai_drift_check_stride: int,
    ai_stable_upshift_window: int,
    ai_interval_min_ratio: float,
    target_ai_drift_threshold_policy,
    enable_physics_filter: bool,
    physics_filter_mode: str,
    physics_filter_max_energy_drift: float,
    physics_filter_max_momentum_drift: float,
    physics_filter_min_interatomic_distance: float,
    output_file: str,
    neighbor_settings: Dict[str, float],
    force_backend: str,
    ai_router_checkpoint: str | None,
    ai_router_checkpoint_strict: bool,
    ai_runtime_mode: str,
    ai_disable_exploration: bool,
    ai_use_hip_graph: bool,
    ai_graph_warmup_iters: int,
    disable_stochastic_noise: bool,
    precompute_stochastic_noise: bool,
    precompute_stochastic_noise_block_steps: int,
    track_clip_hits: bool,
    sample_gpu_metrics: bool,
) -> Dict[str, object]:
    return benchmark_simulation(
        target=target,
        steps=int(max(steps, 4)),
        use_ai_router=bool(use_ai_router),
        num_runs=int(max(runs, 1)),
        warmup_steps=int(max(warmup_steps, 0)),
        batch_replicas=int(max(benchmark_replicas, 1)),
        ai_interval=int(max(ai_interval, 1)),
        target_ai_interval_policy=(target_ai_interval_policy or None),
        adaptive_ai_interval=bool(adaptive_ai_interval),
        ai_interval_min=int(max(ai_interval_min, 1)),
        ai_interval_max=int(ai_interval_max),
        ai_downshift_factor=int(max(ai_downshift_factor, 2)),
        ai_drift_disp_threshold=float(max(ai_drift_disp_threshold, 0.0)),
        ai_drift_check_stride=int(max(ai_drift_check_stride, 1)),
        ai_stable_upshift_window=int(max(ai_stable_upshift_window, 0)),
        ai_interval_min_ratio=float(max(ai_interval_min_ratio, 0.0)),
        target_ai_drift_threshold_policy=(target_ai_drift_threshold_policy or None),
        enable_physics_filter=bool(enable_physics_filter),
        physics_filter_mode=str(physics_filter_mode),
        physics_filter_max_energy_drift=float(physics_filter_max_energy_drift),
        physics_filter_max_momentum_drift=float(physics_filter_max_momentum_drift),
        physics_filter_min_interatomic_distance=float(physics_filter_min_interatomic_distance),
        output_file=str(output_file),
        neighbor_settings=neighbor_settings,
        force_backend=str(force_backend),
        ai_router_checkpoint=ai_router_checkpoint,
        ai_router_checkpoint_strict=bool(ai_router_checkpoint_strict),
        ai_runtime_mode=str(ai_runtime_mode),
        ai_disable_exploration=bool(ai_disable_exploration),
        ai_use_hip_graph=bool(ai_use_hip_graph),
        ai_graph_warmup_iters=int(max(ai_graph_warmup_iters, 1)),
        disable_stochastic_noise=bool(disable_stochastic_noise),
        precompute_stochastic_noise=bool(precompute_stochastic_noise),
        precompute_stochastic_noise_block_steps=int(max(precompute_stochastic_noise_block_steps, 0)),
        track_clip_hits=bool(track_clip_hits),
        profile_components=True,
        sample_gpu_metrics=bool(sample_gpu_metrics),
    )


def run_report(args):
    if args.force_rust:
        os.environ["FORCE_RUST_HIP"] = "1"
        # Keep stage2 benchmark runtime consistent with accuracy gate defaults.
        os.environ.setdefault("RUST_HIP_USE_GPU_NBLIST_BUILDER", "1")
        os.environ.setdefault("NBLIST_AUTOGROW", "1")
        os.environ.setdefault("RUST_HIP_NBLIST_AUTOGROW", "1")

    targets = _parse_targets(getattr(args, "targets", "all"))
    target_ai_interval_policy = parse_target_interval_policy(
        getattr(args, "target_ai_interval_policy", "")
    )
    target_ai_drift_threshold_policy = parse_target_drift_threshold_policy(
        getattr(args, "target_ai_drift_threshold_policy", "")
    )
    adaptive_ai_interval = bool(getattr(args, "adaptive_ai_interval", False))
    ai_interval_min = int(getattr(args, "ai_interval_min", 1))
    ai_interval_max = int(getattr(args, "ai_interval_max", 0))
    ai_downshift_factor = int(getattr(args, "ai_downshift_factor", 2))
    ai_drift_disp_threshold = float(getattr(args, "ai_drift_disp_threshold", 0.25))
    ai_drift_check_stride = int(getattr(args, "ai_drift_check_stride", 1))
    ai_stable_upshift_window = int(getattr(args, "ai_stable_upshift_window", 0))
    ai_interval_min_ratio = float(getattr(args, "ai_interval_min_ratio", 0.0))
    requested_ai_runtime_mode = str(getattr(args, "ai_runtime_mode", "eager")).strip().lower()
    speed_profile_max_replicas = getattr(args, "speed_profile_max_replicas", None)
    if isinstance(speed_profile_max_replicas, str):
        try:
            speed_profile_max_replicas = int(speed_profile_max_replicas)
        except ValueError:
            speed_profile_max_replicas = None
    env_speed_profile_max_replicas = int(os.environ.get("SPEED_PROFILE_MAX_REPLICAS", "0")) or None
    if speed_profile_max_replicas is not None and int(speed_profile_max_replicas) > 0:
        env_speed_profile_max_replicas = int(speed_profile_max_replicas)

    resolved_speed_profile = resolve_speed_profile(
        mode=str(getattr(args, "speed_mode", "balanced")),
        ai_interval=int(getattr(args, "ai_interval", 1)),
        benchmark_replicas=int(getattr(args, "benchmark_replicas", 1)),
        ai_runtime_mode=requested_ai_runtime_mode,
        ai_disable_exploration=bool(getattr(args, "ai_disable_exploration", False)),
        ai_use_hip_graph=bool(getattr(args, "ai_use_hip_graph", False)),
        ai_graph_warmup_iters=int(getattr(args, "ai_graph_warmup_iters", 2)),
        track_clip_hits=bool(getattr(args, "track_clip_hits", False)),
        profile_components=bool(getattr(args, "profile_components", False)),
        disable_stochastic_noise=getattr(args, "disable_stochastic_noise", None),
        precompute_stochastic_noise=getattr(args, "precompute_stochastic_noise", None),
        precompute_stochastic_noise_block_steps=getattr(
            args,
            "precompute_stochastic_noise_block_steps",
            None,
        ),
        sample_gpu_metrics=getattr(args, "sample_gpu_metrics", None),
        speed_mode_replicas=int(getattr(args, "speed_mode_replicas", 0)),
        speed_profile_max_replicas=env_speed_profile_max_replicas,
        preserve_ai_runtime_mode=bool(getattr(args, "speed_profile_preserve_runtime_mode", False)),
    )
    ai_interval = int(resolved_speed_profile["ai_interval"])
    track_clip_hits = bool(resolved_speed_profile["track_clip_hits"])
    profile_components = bool(resolved_speed_profile["profile_components"])
    benchmark_replicas = int(resolved_speed_profile["benchmark_replicas"])
    ai_runtime_mode_i = str(resolved_speed_profile["ai_runtime_mode"]).strip().lower()
    ai_disable_exploration_b = bool(resolved_speed_profile["ai_disable_exploration"])
    ai_use_hip_graph_b = bool(resolved_speed_profile["ai_use_hip_graph"])
    ai_graph_warmup_iters = int(resolved_speed_profile["ai_graph_warmup_iters"])
    sample_gpu_metrics = bool(resolved_speed_profile.get("sample_gpu_metrics", True))
    breakdown_probe_enabled = bool(getattr(args, "breakdown_probe_enabled", True))
    breakdown_probe_steps = int(getattr(args, "breakdown_probe_steps", 24))
    breakdown_probe_runs = int(getattr(args, "breakdown_probe_runs", 1))
    breakdown_probe_warmup_steps = int(getattr(args, "breakdown_probe_warmup_steps", 8))
    rows = []
    for target in targets:
        neighbor_settings = {
            "grid_spacing": float(args.cutoff),
            "cutoff": float(args.cutoff),
            "skin": float(args.skin),
            "max_neighbors": int(args.max_neighbors),
            "max_atoms_per_cell": int(args.max_atoms_per_cell),
            "rebuild_stride": int(args.rebuild_stride),
        }
        enable_physics_filter = bool(getattr(args, "enable_physics_filter", False))
        physics_filter_mode = str(getattr(args, "physics_filter_mode", "rollback"))
        physics_filter_max_energy_drift = float(
            getattr(args, "physics_filter_max_energy_drift", 0.015)
        )
        physics_filter_max_momentum_drift = float(
            getattr(args, "physics_filter_max_momentum_drift", 0.015)
        )
        physics_filter_min_interatomic_distance = float(
            getattr(args, "physics_filter_min_interatomic_distance", 0.0)
        )
        with apply_speed_profile_env(overrides=resolved_speed_profile.get("env")):
            perf_on = benchmark_simulation(
                target=target,
                steps=args.steps,
                use_ai_router=bool(getattr(args, "use_ai_router", False)),
                num_runs=args.runs,
                warmup_steps=int(getattr(args, "warmup_steps", 40)),
                batch_replicas=benchmark_replicas,
                ai_interval=ai_interval,
                target_ai_interval_policy=(target_ai_interval_policy or None),
                adaptive_ai_interval=adaptive_ai_interval,
                ai_interval_min=ai_interval_min,
                ai_interval_max=ai_interval_max,
                ai_downshift_factor=ai_downshift_factor,
                ai_drift_disp_threshold=ai_drift_disp_threshold,
                ai_drift_check_stride=ai_drift_check_stride,
                ai_stable_upshift_window=ai_stable_upshift_window,
                ai_interval_min_ratio=ai_interval_min_ratio,
                target_ai_drift_threshold_policy=(target_ai_drift_threshold_policy or None),
                enable_physics_filter=enable_physics_filter,
                physics_filter_mode=physics_filter_mode,
                physics_filter_max_energy_drift=physics_filter_max_energy_drift,
                physics_filter_max_momentum_drift=physics_filter_max_momentum_drift,
                physics_filter_min_interatomic_distance=physics_filter_min_interatomic_distance,
                output_file=args.benchmark_csv,
                neighbor_settings=neighbor_settings,
                force_backend="auto",
                ai_router_checkpoint=str(getattr(args, "ai_router_checkpoint", "")).strip() or None,
                ai_router_checkpoint_strict=bool(getattr(args, "ai_router_checkpoint_strict", False)),
        ai_runtime_mode=ai_runtime_mode_i,
        ai_disable_exploration=ai_disable_exploration_b,
        ai_use_hip_graph=ai_use_hip_graph_b,
        ai_graph_warmup_iters=ai_graph_warmup_iters,
        disable_stochastic_noise=bool(resolved_speed_profile.get("disable_stochastic_noise", False)),
        precompute_stochastic_noise=bool(resolved_speed_profile.get("precompute_stochastic_noise", False)),
        precompute_stochastic_noise_block_steps=int(
            resolved_speed_profile.get("precompute_stochastic_noise_block_steps", 0)
        ),
        track_clip_hits=track_clip_hits,
        profile_components=profile_components,
        sample_gpu_metrics=sample_gpu_metrics,
    )
        rmse_on = estimate_force_rmse(
            target=target,
            neighbor_settings=neighbor_settings,
            samples=args.eval_samples,
            noise=args.eval_noise,
            reference_cutoff=args.reference_cutoff,
            reference_max_neighbors=args.reference_max_neighbors,
            force_backend=str(getattr(args, "eval_force_backend", "pytorch")).strip().lower(),
        )
        perf_on_probe: Dict[str, object] = {}
        if breakdown_probe_enabled and _component_breakdown_needs_probe(perf_on):
            with apply_speed_profile_env(overrides=resolved_speed_profile.get("env")):
                perf_on_probe = _run_breakdown_probe(
                    target=target,
                    steps=breakdown_probe_steps,
                    warmup_steps=breakdown_probe_warmup_steps,
                    runs=breakdown_probe_runs,
                    use_ai_router=bool(getattr(args, "use_ai_router", False)),
                    benchmark_replicas=benchmark_replicas,
                    ai_interval=ai_interval,
                    target_ai_interval_policy=(target_ai_interval_policy or None),
                    adaptive_ai_interval=adaptive_ai_interval,
                    ai_interval_min=ai_interval_min,
                    ai_interval_max=ai_interval_max,
                    ai_downshift_factor=ai_downshift_factor,
                    ai_drift_disp_threshold=ai_drift_disp_threshold,
                    ai_drift_check_stride=ai_drift_check_stride,
                    ai_stable_upshift_window=ai_stable_upshift_window,
                    ai_interval_min_ratio=ai_interval_min_ratio,
                    target_ai_drift_threshold_policy=(target_ai_drift_threshold_policy or None),
                    enable_physics_filter=enable_physics_filter,
                    physics_filter_mode=physics_filter_mode,
                    physics_filter_max_energy_drift=physics_filter_max_energy_drift,
                    physics_filter_max_momentum_drift=physics_filter_max_momentum_drift,
                    physics_filter_min_interatomic_distance=physics_filter_min_interatomic_distance,
                    output_file=args.benchmark_csv,
                    neighbor_settings=neighbor_settings,
                    force_backend="auto",
                    ai_router_checkpoint=str(getattr(args, "ai_router_checkpoint", "")).strip() or None,
                    ai_router_checkpoint_strict=bool(getattr(args, "ai_router_checkpoint_strict", False)),
                    ai_runtime_mode=ai_runtime_mode_i,
                    ai_disable_exploration=ai_disable_exploration_b,
                    ai_use_hip_graph=ai_use_hip_graph_b,
                    ai_graph_warmup_iters=ai_graph_warmup_iters,
                    disable_stochastic_noise=bool(
                        resolved_speed_profile.get("disable_stochastic_noise", False)
                    ),
                    precompute_stochastic_noise=bool(
                        resolved_speed_profile.get("precompute_stochastic_noise", False)
                    ),
                    precompute_stochastic_noise_block_steps=int(
                        resolved_speed_profile.get("precompute_stochastic_noise_block_steps", 0)
                    ),
                    track_clip_hits=track_clip_hits,
                    sample_gpu_metrics=sample_gpu_metrics,
                )

        row = {
            "target": target,
            "throughput_on": perf_on["avg_throughput_steps_per_sec"],
            "step_ms_on": perf_on["avg_time_per_step_ms"],
            "force_rmse_on": rmse_on,
            "neighbor_ms_on": _pick_breakdown_value(
                perf_on, perf_on_probe, "neighbor_time_per_step_ms"
            ),
            "force_ms_on": _pick_breakdown_value(
                perf_on, perf_on_probe, "force_time_per_step_ms"
            ),
            "ai_ms_on": _pick_breakdown_value(perf_on, perf_on_probe, "ai_time_per_step_ms"),
            "ai_infer_ms_on": _pick_breakdown_value(
                perf_on, perf_on_probe, "ai_inference_time_per_step_ms"
            ),
            "integrator_ms_on": _pick_breakdown_value(
                perf_on, perf_on_probe, "integrator_time_per_step_ms"
            ),
            "breakdown_source_on": (
                "probe"
                if (perf_on_probe and _component_breakdown_needs_probe(perf_on))
                else "direct"
            ),
            "ai_active_modules_on": perf_on.get("avg_ai_active_modules_per_eval"),
            "ai_active_module_ratio_on": perf_on.get("avg_ai_active_module_ratio_per_eval"),
            "ai_uncertainty_fallback_steps_on": perf_on.get(
                "avg_ai_uncertainty_fallback_steps_per_run"
            ),
            "ai_uncertainty_fallback_ratio_on": perf_on.get(
                "avg_ai_uncertainty_fallback_ratio_per_eval"
            ),
            "ai_uncertainty_score_on": perf_on.get("avg_ai_uncertainty_score_per_eval"),
            "ai_interval_on": perf_on.get("ai_interval"),
            "ai_interval_target_on": perf_on.get("ai_interval_target", perf_on.get("ai_interval")),
            "ai_interval_active_on": perf_on.get("avg_ai_interval_active_per_step"),
            "ai_drift_disp_threshold_on": perf_on.get("ai_drift_disp_threshold"),
            "ai_forced_eval_by_drift_on": perf_on.get("avg_ai_forced_eval_by_drift_per_run"),
            "ai_interval_downshifts_on": perf_on.get("avg_ai_interval_downshifts_per_run"),
            "ai_interval_upshifts_on": perf_on.get("avg_ai_interval_upshifts_per_run"),
            "ai_calls_on": perf_on.get("avg_ai_inference_calls_per_run"),
            "ai_reuse_on": perf_on.get("avg_ai_reuse_steps_per_run"),
            "ai_router_checkpoint_loaded_on": perf_on.get("ai_router_checkpoint_loaded"),
            "ai_runtime_mode_on": perf_on.get("ai_runtime_mode"),
            "ai_graph_enabled_on": perf_on.get("avg_ai_graph_enabled_flag"),
            "ai_graph_reason_on": perf_on.get("ai_graph_last_reason"),
            "ai_router_script_error_on": perf_on.get("ai_router_script_error"),
            "physics_violations_on": perf_on.get("avg_physics_violations_per_run"),
            "physics_recoveries_on": perf_on.get("avg_physics_recoveries_per_run"),
            "neighbor_settings": json.dumps(neighbor_settings),
        }

        if args.with_fallback:
            with apply_speed_profile_env(overrides=resolved_speed_profile.get("env")):
                perf_off = benchmark_simulation(
                    target=target,
                    steps=args.steps,
                    # OFF baseline must disable AIRouter to measure true fallback speed.
                    use_ai_router=False,
                    num_runs=args.runs,
                    warmup_steps=int(getattr(args, "warmup_steps", 40)),
                    batch_replicas=benchmark_replicas,
                    ai_interval=ai_interval,
                    target_ai_interval_policy=(target_ai_interval_policy or None),
                    adaptive_ai_interval=adaptive_ai_interval,
                    ai_interval_min=ai_interval_min,
                    ai_interval_max=ai_interval_max,
                    ai_downshift_factor=ai_downshift_factor,
                    ai_drift_disp_threshold=ai_drift_disp_threshold,
                    ai_drift_check_stride=ai_drift_check_stride,
                    ai_stable_upshift_window=ai_stable_upshift_window,
                    ai_interval_min_ratio=ai_interval_min_ratio,
                    target_ai_drift_threshold_policy=(target_ai_drift_threshold_policy or None),
                    enable_physics_filter=enable_physics_filter,
                    physics_filter_mode=physics_filter_mode,
                    physics_filter_max_energy_drift=physics_filter_max_energy_drift,
                    physics_filter_max_momentum_drift=physics_filter_max_momentum_drift,
                    physics_filter_min_interatomic_distance=physics_filter_min_interatomic_distance,
                    output_file=args.benchmark_csv,
                    neighbor_settings=neighbor_settings,
                    force_backend="pytorch",
                    ai_router_checkpoint=str(getattr(args, "ai_router_checkpoint", "")).strip() or None,
                    ai_router_checkpoint_strict=bool(getattr(args, "ai_router_checkpoint_strict", False)),
                    ai_runtime_mode=ai_runtime_mode_i,
                    ai_disable_exploration=ai_disable_exploration_b,
                    ai_use_hip_graph=ai_use_hip_graph_b,
                ai_graph_warmup_iters=ai_graph_warmup_iters,
                disable_stochastic_noise=bool(resolved_speed_profile.get("disable_stochastic_noise", False)),
                precompute_stochastic_noise=bool(resolved_speed_profile.get("precompute_stochastic_noise", False)),
                precompute_stochastic_noise_block_steps=int(
                    resolved_speed_profile.get("precompute_stochastic_noise_block_steps", 0)
                ),
                track_clip_hits=track_clip_hits,
                profile_components=profile_components,
                sample_gpu_metrics=sample_gpu_metrics,
            )
            rmse_off = estimate_force_rmse(
                target=target,
                neighbor_settings=neighbor_settings,
                samples=args.eval_samples,
                noise=args.eval_noise,
                reference_cutoff=args.reference_cutoff,
                reference_max_neighbors=args.reference_max_neighbors,
                force_backend=str(getattr(args, "eval_force_backend", "pytorch")).strip().lower(),
            )
            perf_off_probe: Dict[str, object] = {}
            if breakdown_probe_enabled and _component_breakdown_needs_probe(perf_off):
                with apply_speed_profile_env(overrides=resolved_speed_profile.get("env")):
                    perf_off_probe = _run_breakdown_probe(
                        target=target,
                        steps=breakdown_probe_steps,
                        warmup_steps=breakdown_probe_warmup_steps,
                        runs=breakdown_probe_runs,
                        # Keep probe consistent with OFF baseline path.
                        use_ai_router=False,
                        benchmark_replicas=benchmark_replicas,
                        ai_interval=ai_interval,
                        target_ai_interval_policy=(target_ai_interval_policy or None),
                        adaptive_ai_interval=adaptive_ai_interval,
                        ai_interval_min=ai_interval_min,
                        ai_interval_max=ai_interval_max,
                        ai_downshift_factor=ai_downshift_factor,
                        ai_drift_disp_threshold=ai_drift_disp_threshold,
                        ai_drift_check_stride=ai_drift_check_stride,
                        ai_stable_upshift_window=ai_stable_upshift_window,
                        ai_interval_min_ratio=ai_interval_min_ratio,
                        target_ai_drift_threshold_policy=(target_ai_drift_threshold_policy or None),
                        enable_physics_filter=enable_physics_filter,
                        physics_filter_mode=physics_filter_mode,
                        physics_filter_max_energy_drift=physics_filter_max_energy_drift,
                        physics_filter_max_momentum_drift=physics_filter_max_momentum_drift,
                        physics_filter_min_interatomic_distance=physics_filter_min_interatomic_distance,
                        output_file=args.benchmark_csv,
                        neighbor_settings=neighbor_settings,
                        force_backend="pytorch",
                        ai_router_checkpoint=str(getattr(args, "ai_router_checkpoint", "")).strip() or None,
                        ai_router_checkpoint_strict=bool(getattr(args, "ai_router_checkpoint_strict", False)),
                        ai_runtime_mode=ai_runtime_mode_i,
                        ai_disable_exploration=ai_disable_exploration_b,
                        ai_use_hip_graph=ai_use_hip_graph_b,
                        ai_graph_warmup_iters=ai_graph_warmup_iters,
                        disable_stochastic_noise=bool(
                            resolved_speed_profile.get("disable_stochastic_noise", False)
                        ),
                        precompute_stochastic_noise=bool(
                            resolved_speed_profile.get("precompute_stochastic_noise", False)
                        ),
                        precompute_stochastic_noise_block_steps=int(
                            resolved_speed_profile.get("precompute_stochastic_noise_block_steps", 0)
                        ),
                        track_clip_hits=track_clip_hits,
                        sample_gpu_metrics=sample_gpu_metrics,
                    )
            row.update(
                {
                    "throughput_off": perf_off["avg_throughput_steps_per_sec"],
                    "step_ms_off": perf_off["avg_time_per_step_ms"],
                    "force_rmse_off": rmse_off,
                    "speedup_on_vs_off": perf_on["avg_throughput_steps_per_sec"]
                    / max(perf_off["avg_throughput_steps_per_sec"], 1e-8),
                    "neighbor_ms_off": _pick_breakdown_value(
                        perf_off, perf_off_probe, "neighbor_time_per_step_ms"
                    ),
                    "force_ms_off": _pick_breakdown_value(
                        perf_off, perf_off_probe, "force_time_per_step_ms"
                    ),
                    "ai_ms_off": _pick_breakdown_value(
                        perf_off, perf_off_probe, "ai_time_per_step_ms"
                    ),
                    "ai_infer_ms_off": _pick_breakdown_value(
                        perf_off, perf_off_probe, "ai_inference_time_per_step_ms"
                    ),
                    "integrator_ms_off": _pick_breakdown_value(
                        perf_off, perf_off_probe, "integrator_time_per_step_ms"
                    ),
                    "breakdown_source_off": (
                        "probe"
                        if (perf_off_probe and _component_breakdown_needs_probe(perf_off))
                        else "direct"
                    ),
                    "ai_active_modules_off": perf_off.get("avg_ai_active_modules_per_eval"),
                    "ai_active_module_ratio_off": perf_off.get("avg_ai_active_module_ratio_per_eval"),
                    "ai_uncertainty_fallback_steps_off": perf_off.get(
                        "avg_ai_uncertainty_fallback_steps_per_run"
                    ),
                    "ai_uncertainty_fallback_ratio_off": perf_off.get(
                        "avg_ai_uncertainty_fallback_ratio_per_eval"
                    ),
                    "ai_uncertainty_score_off": perf_off.get("avg_ai_uncertainty_score_per_eval"),
                    "ai_interval_off": perf_off.get("ai_interval"),
                    "ai_interval_target_off": perf_off.get(
                        "ai_interval_target", perf_off.get("ai_interval")
                    ),
                    "ai_interval_active_off": perf_off.get("avg_ai_interval_active_per_step"),
                    "ai_drift_disp_threshold_off": perf_off.get("ai_drift_disp_threshold"),
                    "ai_forced_eval_by_drift_off": perf_off.get("avg_ai_forced_eval_by_drift_per_run"),
                    "ai_interval_downshifts_off": perf_off.get("avg_ai_interval_downshifts_per_run"),
                    "ai_interval_upshifts_off": perf_off.get("avg_ai_interval_upshifts_per_run"),
                    "ai_calls_off": perf_off.get("avg_ai_inference_calls_per_run"),
                    "ai_reuse_off": perf_off.get("avg_ai_reuse_steps_per_run"),
                    "ai_router_checkpoint_loaded_off": perf_off.get("ai_router_checkpoint_loaded"),
                    "ai_runtime_mode_off": perf_off.get("ai_runtime_mode"),
                    "ai_graph_enabled_off": perf_off.get("avg_ai_graph_enabled_flag"),
                    "ai_graph_reason_off": perf_off.get("ai_graph_last_reason"),
                    "ai_router_script_error_off": perf_off.get("ai_router_script_error"),
                    "physics_violations_off": perf_off.get("avg_physics_violations_per_run"),
                    "physics_recoveries_off": perf_off.get("avg_physics_recoveries_per_run"),
                }
            )
        rows.append(row)

    os.makedirs(os.path.dirname(args.report_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.report_json) or ".", exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(args.report_csv, index=False)

    summary = {
        "speed_mode": str(resolved_speed_profile.get("mode", "balanced")),
        "targets": len(rows),
        "use_ai_router": bool(getattr(args, "use_ai_router", False)),
        "ai_router_checkpoint": str(getattr(args, "ai_router_checkpoint", "")).strip() or None,
        "batch_replicas_profile": int(benchmark_replicas),
        "avg_throughput_on": float(df["throughput_on"].mean()),
        "avg_step_ms_on": float(df["step_ms_on"].mean()),
        "avg_force_rmse_on": float(df["force_rmse_on"].mean()),
        "adaptive_ai_interval": bool(adaptive_ai_interval),
        "target_ai_interval_policy_count": int(len(target_ai_interval_policy)),
        "target_ai_drift_threshold_policy_count": int(len(target_ai_drift_threshold_policy)),
        "ai_interval": int(ai_interval),
        "ai_runtime_mode_requested": requested_ai_runtime_mode,
        "ai_runtime_mode": ai_runtime_mode_i,
        "ai_runtime_mode_profile": resolved_speed_profile.get("ai_runtime_mode_profile"),
        "ai_runtime_mode_preserved": bool(resolved_speed_profile.get("ai_runtime_mode_preserved", False)),
        "ai_runtime_mode_overridden_by_profile": bool(ai_runtime_mode_i != requested_ai_runtime_mode),
        "ai_disable_exploration": bool(ai_disable_exploration_b),
        "ai_use_hip_graph": bool(ai_use_hip_graph_b),
        "ai_graph_warmup_iters": int(ai_graph_warmup_iters),
        "disable_stochastic_noise": bool(resolved_speed_profile.get("disable_stochastic_noise", False)),
        "precompute_stochastic_noise": bool(
            resolved_speed_profile.get("precompute_stochastic_noise", False)
        ),
        "precompute_stochastic_noise_block_steps": int(
            resolved_speed_profile.get("precompute_stochastic_noise_block_steps", 0)
        ),
        "track_clip_hits": bool(track_clip_hits),
        "profile_components": bool(profile_components),
        "breakdown_probe_enabled": bool(breakdown_probe_enabled),
        "breakdown_probe_steps": int(breakdown_probe_steps),
        "breakdown_probe_runs": int(breakdown_probe_runs),
        "breakdown_probe_warmup_steps": int(breakdown_probe_warmup_steps),
    }
    if args.with_fallback:
        summary.update(
            {
                "avg_throughput_off": float(df["throughput_off"].mean()),
                "avg_step_ms_off": float(df["step_ms_off"].mean()),
                "avg_speedup_on_vs_off": float(df["speedup_on_vs_off"].mean()),
                "avg_force_rmse_off": float(df["force_rmse_off"].mean()),
            }
        )

    payload = {"summary": summary, "rows": rows}
    with open(args.report_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(summary, indent=2))
    return payload


def main():
    parser = argparse.ArgumentParser(description="Run stage-2 full report across all 10 protein targets.")
    parser.add_argument("--steps", type=int, default=160)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--use-ai-router", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--ai-router-checkpoint", type=str, default="")
    parser.add_argument("--ai-router-checkpoint-strict", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument(
        "--ai-runtime-mode",
        type=str,
        default="eager",
        choices=["eager", "scripted", "compiled", "onnx"],
        help="AIRouter inference runtime mode",
    )
    parser.add_argument(
        "--speed-profile-preserve-runtime-mode",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Keep --ai-runtime-mode even when speed profile preset has its own runtime mode.",
    )
    parser.add_argument(
        "--ai-disable-exploration",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Disable AIRouter exploration noise for deterministic high-throughput runs",
    )
    parser.add_argument(
        "--ai-use-hip-graph",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Attempt CUDA/HIP graph replay for AI inference path",
    )
    parser.add_argument(
        "--speed-mode",
        type=str,
        default="balanced",
        choices=["balanced", "fast", "ultra", "turbo", "extreme", "warp", "titan", "max"],
        help="Speed preset for this benchmark run",
    )
    parser.add_argument(
        "--sample-gpu-metrics",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable per-run GPU metric sampling.",
    )
    parser.add_argument(
        "--speed-mode-replicas",
        type=int,
        default=0,
        help="Minimum replicas enforced by the selected speed preset",
    )
    parser.add_argument(
        "--speed-profile-max-replicas",
        type=int,
        default=0,
        help="Optional max replicas cap applied to speed profile.",
    )
    parser.add_argument(
        "--ai-graph-warmup-iters",
        type=int,
        default=2,
        help="Warmup iterations before graph capture",
    )
    parser.add_argument(
        "--disable-stochastic-noise",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Force Langevin stochastic term off (throughput-focused).",
    )
    parser.add_argument(
        "--precompute-stochastic-noise",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Precompute Langevin noise in fixed-size blocks.",
    )
    parser.add_argument(
        "--precompute-stochastic-noise-block-steps",
        type=int,
        default=None,
        help="Noise precompute block size (steps).",
    )
    parser.add_argument("--warmup-steps", type=int, default=40)
    parser.add_argument("--benchmark-replicas", type=int, default=1)
    parser.add_argument("--ai-interval", type=int, default=1)
    parser.add_argument("--target-ai-interval-policy", type=str, default="speed_opt_v2")
    parser.add_argument("--target-ai-drift-threshold-policy", type=str, default="")
    parser.add_argument("--adaptive-ai-interval", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--ai-interval-min", type=int, default=1)
    parser.add_argument("--ai-interval-max", type=int, default=0)
    parser.add_argument("--ai-downshift-factor", type=int, default=2)
    parser.add_argument("--ai-drift-disp-threshold", type=float, default=0.25)
    parser.add_argument("--ai-drift-check-stride", type=int, default=1)
    parser.add_argument("--ai-stable-upshift-window", type=int, default=0)
    parser.add_argument("--ai-interval-min-ratio", type=float, default=0.0)
    parser.add_argument("--enable-physics-filter", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--physics-filter-mode", type=str, default="rollback", choices=["rollback", "hard_fail"])
    parser.add_argument("--physics-filter-max-energy-drift", type=float, default=0.015)
    parser.add_argument("--physics-filter-max-momentum-drift", type=float, default=0.015)
    parser.add_argument("--physics-filter-min-interatomic-distance", type=float, default=0.0)
    parser.add_argument("--eval-samples", type=int, default=2)
    parser.add_argument("--eval-noise", type=float, default=0.12)
    parser.add_argument(
        "--eval-force-backend",
        type=str,
        default="pytorch",
        choices=["auto", "pytorch"],
        help="Backend used by force RMSE probe path (default pytorch for stability).",
    )
    parser.add_argument("--reference-cutoff", type=float, default=14.0)
    parser.add_argument("--reference-max-neighbors", type=int, default=160)
    parser.add_argument("--cutoff", type=float, default=12.0)
    parser.add_argument("--skin", type=float, default=2.0)
    parser.add_argument("--max-neighbors", type=int, default=100)
    parser.add_argument("--max-atoms-per-cell", type=int, default=64)
    parser.add_argument("--rebuild-stride", type=int, default=4)
    parser.add_argument("--with-fallback", action="store_true")
    parser.add_argument("--force-rust", action="store_true")
    parser.add_argument("--track-clip-hits", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--profile-components", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument(
        "--breakdown-probe-enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When true, run short profile_components probes if breakdown metrics are all zero.",
    )
    parser.add_argument(
        "--breakdown-probe-steps",
        type=int,
        default=24,
        help="Probe benchmark steps for component breakdown backfill.",
    )
    parser.add_argument(
        "--breakdown-probe-runs",
        type=int,
        default=1,
        help="Probe benchmark runs for component breakdown backfill.",
    )
    parser.add_argument(
        "--breakdown-probe-warmup-steps",
        type=int,
        default=8,
        help="Probe warmup steps for component breakdown backfill.",
    )
    parser.add_argument("--targets", type=str, default="all")
    parser.add_argument("--report-csv", type=str, default="runs/stage2_full_report.csv")
    parser.add_argument("--report-json", type=str, default="runs/stage2_full_report.json")
    parser.add_argument("--benchmark-csv", type=str, default="benchmark_results.csv")
    args = parser.parse_args()
    run_report(args)


if __name__ == "__main__":
    main()
