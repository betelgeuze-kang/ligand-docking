#!/usr/bin/env python3

from __future__ import annotations

import argparse
import itertools
import json
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pandas as pd

from benchmark.performance_bench import benchmark_simulation
from core.definitions import ResearchConstants
from core.mts_policy import parse_target_drift_threshold_policy, parse_target_interval_policy
from tools.speed_profile import apply_speed_profile_env, resolve_speed_profile
from tools.stage2_full_report import estimate_force_rmse


def _parse_targets(spec: str) -> List[str]:
    s = str(spec).strip()
    if s.lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    out = [x.strip() for x in s.split(",") if x.strip()]
    if not out:
        raise ValueError(f"no targets parsed from spec: {spec}")
    unknown = [x for x in out if x not in ResearchConstants.CHALLENGES]
    if unknown:
        known = ", ".join(sorted(ResearchConstants.CHALLENGES.keys()))
        raise ValueError(f"unknown target(s): {unknown}. known: {known}")
    return out


def _parse_float_list(spec: str) -> List[float]:
    out = [float(x.strip()) for x in str(spec).split(",") if x.strip()]
    if not out:
        raise ValueError(f"empty float list: {spec}")
    return out


def _parse_int_list(spec: str) -> List[int]:
    out = [int(x.strip()) for x in str(spec).split(",") if x.strip()]
    if not out:
        raise ValueError(f"empty int list: {spec}")
    return out


def _mk_neighbor_settings(
    *,
    cutoff: float,
    skin: float,
    rebuild_stride: int,
    max_neighbors: int,
    max_atoms_per_cell: int,
    grid_spacing: Optional[float] = None,
) -> Dict[str, float]:
    gs = float(cutoff if grid_spacing is None else grid_spacing)
    return {
        "grid_spacing": float(gs),
        "cutoff": float(cutoff),
        "skin": float(skin),
        "max_neighbors": int(max_neighbors),
        "max_atoms_per_cell": int(max_atoms_per_cell),
        "rebuild_stride": int(rebuild_stride),
    }


def _evaluate_candidate(
    *,
    target: str,
    neighbor_settings: Mapping[str, float],
    steps: int,
    runs: int,
    warmup_steps: int,
    use_ai_router: bool,
    force_backend: str,
    benchmark_replicas: int,
    ai_interval: int,
    target_ai_interval_policy: Optional[Mapping[str, int]],
    target_ai_drift_threshold_policy: Optional[Mapping[str, float]],
    adaptive_ai_interval: bool,
    ai_interval_min: int,
    ai_interval_max: int,
    ai_downshift_factor: int,
    ai_drift_disp_threshold: float,
    ai_drift_check_stride: int,
    ai_stable_upshift_window: int,
    ai_interval_min_ratio: float,
    ai_runtime_mode: str,
    ai_disable_exploration: bool,
    ai_use_hip_graph: bool,
    ai_graph_warmup_iters: int,
    track_clip_hits: bool,
    profile_components: bool,
    sample_gpu_metrics: bool,
    eval_samples: int,
    eval_noise: float,
    eval_force_backend: str,
    reference_cutoff: float,
    reference_max_neighbors: int,
    benchmark_csv: Optional[str],
) -> Dict[str, Any]:
    perf = benchmark_simulation(
        target=target,
        steps=int(steps),
        use_ai_router=bool(use_ai_router),
        num_runs=int(runs),
        warmup_steps=int(warmup_steps),
        batch_replicas=int(benchmark_replicas),
        ai_interval=int(ai_interval),
        output_file=benchmark_csv,
        neighbor_settings=dict(neighbor_settings),
        force_backend=str(force_backend),
        target_ai_interval_policy=(target_ai_interval_policy or None),
        adaptive_ai_interval=bool(adaptive_ai_interval),
        ai_interval_min=int(ai_interval_min),
        ai_interval_max=int(ai_interval_max),
        ai_downshift_factor=int(ai_downshift_factor),
        ai_drift_disp_threshold=float(ai_drift_disp_threshold),
        ai_drift_check_stride=int(ai_drift_check_stride),
        ai_stable_upshift_window=int(ai_stable_upshift_window),
        ai_interval_min_ratio=float(ai_interval_min_ratio),
        target_ai_drift_threshold_policy=(target_ai_drift_threshold_policy or None),
        ai_runtime_mode=str(ai_runtime_mode),
        ai_disable_exploration=bool(ai_disable_exploration),
        ai_use_hip_graph=bool(ai_use_hip_graph),
        ai_graph_warmup_iters=int(ai_graph_warmup_iters),
        track_clip_hits=bool(track_clip_hits),
        profile_components=bool(profile_components),
        sample_gpu_metrics=bool(sample_gpu_metrics),
    )
    rmse = estimate_force_rmse(
        target=target,
        neighbor_settings=dict(neighbor_settings),
        samples=int(eval_samples),
        noise=float(eval_noise),
        reference_cutoff=float(reference_cutoff),
        reference_max_neighbors=int(reference_max_neighbors),
        force_backend=str(eval_force_backend),
    )
    return {
        "target": target,
        "throughput": float(perf["avg_throughput_steps_per_sec"]),
        "step_ms": float(perf["avg_time_per_step_ms"]),
        "cpu_util_percent": float(perf.get("avg_cpu_util_percent", 0.0)),
        "gpu_util_percent": float(perf.get("avg_gpu_util_percent", 0.0)),
        "force_rmse": float(rmse),
        "neighbor_settings": dict(neighbor_settings),
    }


def _choose_best(
    baseline: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    *,
    rmse_rel_tol: float,
    rmse_abs_tol: float,
    min_throughput_gain_pct: float,
) -> Dict[str, Any]:
    base_thr = float(baseline["throughput"])
    base_rmse = float(baseline["force_rmse"])
    rmse_limit = max(base_rmse * (1.0 + float(rmse_rel_tol)), base_rmse + float(rmse_abs_tol))
    thr_limit = base_thr * (1.0 + float(min_throughput_gain_pct) / 100.0)

    feasible = []
    for row in candidates:
        thr = float(row["throughput"])
        rmse = float(row["force_rmse"])
        if rmse <= rmse_limit and thr >= thr_limit:
            feasible.append(row)
    if feasible:
        best = max(feasible, key=lambda x: (float(x["throughput"]), -float(x["force_rmse"])))
        reason = "feasible_best"
    else:
        best = max(candidates, key=lambda x: (float(x["throughput"]), -float(x["force_rmse"])))
        reason = "fallback_max_throughput"

    out = dict(best)
    out["selection_reason"] = reason
    out["rmse_limit"] = rmse_limit
    out["throughput_limit"] = thr_limit
    out["throughput_gain_pct_vs_baseline"] = (
        (float(out["throughput"]) - base_thr) / max(base_thr, 1e-12) * 100.0
    )
    out["rmse_delta_vs_baseline"] = float(out["force_rmse"]) - base_rmse
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Target-level neighbor/rebuild tuning loop for AI-router throughput with RMSE guard."
    )
    p.add_argument("--targets", type=str, default="Protein_A_Bdomain,WW_Domain_FiP35")
    p.add_argument("--steps", type=int, default=60)
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--warmup-steps", type=int, default=30)
    p.add_argument("--force-backend", type=str, default="auto", choices=["auto", "pytorch"])
    p.add_argument("--force-rust", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--use-ai-router", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--speed-mode",
        type=str,
        default="fast",
        choices=["balanced", "fast", "ultra", "turbo", "extreme", "warp", "titan", "max"],
    )
    p.add_argument("--speed-mode-replicas", type=int, default=0)
    p.add_argument("--speed-profile-max-replicas", type=int, default=0)
    p.add_argument("--benchmark-replicas", type=int, default=1)
    p.add_argument("--ai-interval", type=int, default=1)
    p.add_argument("--target-ai-interval-policy", type=str, default="speed_opt_v2")
    p.add_argument("--target-ai-drift-threshold-policy", type=str, default="balanced_v1")
    p.add_argument("--adaptive-ai-interval", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ai-interval-min", type=int, default=1)
    p.add_argument("--ai-interval-max", type=int, default=0)
    p.add_argument("--ai-downshift-factor", type=int, default=2)
    p.add_argument("--ai-drift-disp-threshold", type=float, default=0.25)
    p.add_argument("--ai-drift-check-stride", type=int, default=1)
    p.add_argument("--ai-stable-upshift-window", type=int, default=0)
    p.add_argument("--ai-interval-min-ratio", type=float, default=0.0)
    p.add_argument(
        "--ai-runtime-mode",
        type=str,
        default="scripted",
        choices=["eager", "scripted", "compiled", "onnx"],
    )
    p.add_argument("--ai-disable-exploration", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ai-use-hip-graph", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ai-graph-warmup-iters", type=int, default=2)
    p.add_argument("--track-clip-hits", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--profile-components", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--sample-gpu-metrics", action=argparse.BooleanOptionalAction, default=True)

    p.add_argument("--baseline-cutoff", type=float, default=12.0)
    p.add_argument("--baseline-skin", type=float, default=2.0)
    p.add_argument("--baseline-rebuild-stride", type=int, default=4)
    p.add_argument("--baseline-max-neighbors", type=int, default=100)
    p.add_argument("--baseline-max-atoms-per-cell", type=int, default=64)
    p.add_argument("--cutoffs", type=str, default="11.5,12.0")
    p.add_argument("--skins", type=str, default="1.5,2.0")
    p.add_argument("--rebuild-strides", type=str, default="3,4")
    p.add_argument("--max-neighbors-values", type=str, default="96,100")
    p.add_argument("--max-atoms-per-cell-values", type=str, default="64")

    p.add_argument("--eval-samples", type=int, default=4)
    p.add_argument("--eval-noise", type=float, default=0.08)
    p.add_argument("--eval-force-backend", type=str, default="pytorch", choices=["auto", "pytorch"])
    p.add_argument("--reference-cutoff", type=float, default=14.0)
    p.add_argument("--reference-max-neighbors", type=int, default=160)
    p.add_argument("--rmse-rel-tol", type=float, default=0.10)
    p.add_argument("--rmse-abs-tol", type=float, default=0.005)
    p.add_argument("--min-throughput-gain-pct", type=float, default=0.0)

    p.add_argument("--out-csv", type=str, default="runs/target_neighbor_tune_2026-02-18.csv")
    p.add_argument("--out-json", type=str, default="runs/target_neighbor_tune_2026-02-18.json")
    p.add_argument("--out-policy-json", type=str, default="config/target_neighbor_policy_2026-02-18.json")
    p.add_argument("--benchmark-csv", type=str, default="runs/target_neighbor_tune_2026-02-18_bench.csv")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)

    if args.force_rust:
        os.environ["FORCE_RUST_HIP"] = "1"
        os.environ.setdefault("RUST_HIP_USE_GPU_NBLIST_BUILDER", "1")
        os.environ.setdefault("NBLIST_AUTOGROW", "1")
        os.environ.setdefault("RUST_HIP_NBLIST_AUTOGROW", "1")

    targets = _parse_targets(args.targets)
    cutoffs = _parse_float_list(args.cutoffs)
    skins = _parse_float_list(args.skins)
    rebuild_strides = _parse_int_list(args.rebuild_strides)
    max_neighbors_values = _parse_int_list(args.max_neighbors_values)
    max_atoms_per_cell_values = _parse_int_list(args.max_atoms_per_cell_values)
    target_ai_interval_policy = parse_target_interval_policy(args.target_ai_interval_policy)
    target_ai_drift_threshold_policy = parse_target_drift_threshold_policy(
        args.target_ai_drift_threshold_policy
    )

    speed_profile_max_replicas = int(getattr(args, "speed_profile_max_replicas", 0))
    resolved_speed_profile = resolve_speed_profile(
        mode=str(args.speed_mode),
        ai_interval=int(args.ai_interval),
        benchmark_replicas=int(args.benchmark_replicas),
        ai_runtime_mode=str(args.ai_runtime_mode),
        ai_disable_exploration=bool(args.ai_disable_exploration),
        ai_use_hip_graph=bool(args.ai_use_hip_graph),
        ai_graph_warmup_iters=int(args.ai_graph_warmup_iters),
        track_clip_hits=bool(args.track_clip_hits),
        profile_components=bool(args.profile_components),
        sample_gpu_metrics=bool(args.sample_gpu_metrics),
        speed_mode_replicas=int(args.speed_mode_replicas),
        speed_profile_max_replicas=(
            int(speed_profile_max_replicas) if speed_profile_max_replicas > 0 else None
        ),
    )

    base_neighbor = _mk_neighbor_settings(
        cutoff=float(args.baseline_cutoff),
        skin=float(args.baseline_skin),
        rebuild_stride=int(args.baseline_rebuild_stride),
        max_neighbors=int(args.baseline_max_neighbors),
        max_atoms_per_cell=int(args.baseline_max_atoms_per_cell),
    )

    all_rows: List[Dict[str, Any]] = []
    best_by_target: Dict[str, Dict[str, Any]] = {}
    neighbor_policy: Dict[str, Dict[str, Any]] = {}

    eval_kwargs = dict(
        steps=int(args.steps),
        runs=int(args.runs),
        warmup_steps=int(args.warmup_steps),
        use_ai_router=bool(args.use_ai_router),
        force_backend=str(args.force_backend),
        benchmark_replicas=int(resolved_speed_profile["benchmark_replicas"]),
        ai_interval=int(resolved_speed_profile["ai_interval"]),
        target_ai_interval_policy=target_ai_interval_policy,
        target_ai_drift_threshold_policy=target_ai_drift_threshold_policy,
        adaptive_ai_interval=bool(args.adaptive_ai_interval),
        ai_interval_min=int(args.ai_interval_min),
        ai_interval_max=int(args.ai_interval_max),
        ai_downshift_factor=int(args.ai_downshift_factor),
        ai_drift_disp_threshold=float(args.ai_drift_disp_threshold),
        ai_drift_check_stride=int(args.ai_drift_check_stride),
        ai_stable_upshift_window=int(args.ai_stable_upshift_window),
        ai_interval_min_ratio=float(args.ai_interval_min_ratio),
        ai_runtime_mode=str(resolved_speed_profile["ai_runtime_mode"]),
        ai_disable_exploration=bool(resolved_speed_profile["ai_disable_exploration"]),
        ai_use_hip_graph=bool(resolved_speed_profile["ai_use_hip_graph"]),
        ai_graph_warmup_iters=int(resolved_speed_profile["ai_graph_warmup_iters"]),
        track_clip_hits=bool(resolved_speed_profile["track_clip_hits"]),
        profile_components=bool(resolved_speed_profile["profile_components"]),
        sample_gpu_metrics=bool(resolved_speed_profile["sample_gpu_metrics"]),
        eval_samples=int(args.eval_samples),
        eval_noise=float(args.eval_noise),
        eval_force_backend=str(args.eval_force_backend),
        reference_cutoff=float(args.reference_cutoff),
        reference_max_neighbors=int(args.reference_max_neighbors),
        benchmark_csv=(str(args.benchmark_csv).strip() or None),
    )

    with apply_speed_profile_env(resolved_speed_profile.get("env")):
        for idx, target in enumerate(targets, start=1):
            print(f"[{idx}/{len(targets)}] target={target} baseline eval...")
            baseline = _evaluate_candidate(
                target=target,
                neighbor_settings=base_neighbor,
                **eval_kwargs,
            )
            baseline_row = {
                "target": target,
                "is_baseline": True,
                "cutoff": float(base_neighbor["cutoff"]),
                "skin": float(base_neighbor["skin"]),
                "rebuild_stride": int(base_neighbor["rebuild_stride"]),
                "max_neighbors": int(base_neighbor["max_neighbors"]),
                "max_atoms_per_cell": int(base_neighbor["max_atoms_per_cell"]),
                "throughput": float(baseline["throughput"]),
                "step_ms": float(baseline["step_ms"]),
                "force_rmse": float(baseline["force_rmse"]),
                "cpu_util_percent": float(baseline["cpu_util_percent"]),
                "gpu_util_percent": float(baseline["gpu_util_percent"]),
                "throughput_gain_pct_vs_baseline": 0.0,
                "rmse_delta_vs_baseline": 0.0,
                "selection_reason": "baseline",
            }
            all_rows.append(baseline_row)

            candidates: List[Dict[str, Any]] = []
            combo_iter = list(
                itertools.product(
                    cutoffs,
                    skins,
                    rebuild_strides,
                    max_neighbors_values,
                    max_atoms_per_cell_values,
                )
            )
            for jdx, (cutoff, skin, rebuild_stride, max_neighbors, max_atoms_per_cell) in enumerate(
                combo_iter, start=1
            ):
                print(
                    f"  - candidate {jdx}/{len(combo_iter)} "
                    f"(cutoff={cutoff}, skin={skin}, rebuild={rebuild_stride}, "
                    f"max_n={max_neighbors}, max_cell={max_atoms_per_cell})"
                )
                nset = _mk_neighbor_settings(
                    cutoff=float(cutoff),
                    skin=float(skin),
                    rebuild_stride=int(rebuild_stride),
                    max_neighbors=int(max_neighbors),
                    max_atoms_per_cell=int(max_atoms_per_cell),
                )
                row = _evaluate_candidate(
                    target=target,
                    neighbor_settings=nset,
                    **eval_kwargs,
                )
                row["cutoff"] = float(cutoff)
                row["skin"] = float(skin)
                row["rebuild_stride"] = int(rebuild_stride)
                row["max_neighbors"] = int(max_neighbors)
                row["max_atoms_per_cell"] = int(max_atoms_per_cell)
                candidates.append(row)

            best = _choose_best(
                baseline=baseline,
                candidates=candidates,
                rmse_rel_tol=float(args.rmse_rel_tol),
                rmse_abs_tol=float(args.rmse_abs_tol),
                min_throughput_gain_pct=float(args.min_throughput_gain_pct),
            )
            best_by_target[target] = best
            neighbor_policy[target] = dict(best["neighbor_settings"])

            for row in candidates:
                all_rows.append(
                    {
                        "target": target,
                        "is_baseline": False,
                        "cutoff": float(row["cutoff"]),
                        "skin": float(row["skin"]),
                        "rebuild_stride": int(row["rebuild_stride"]),
                        "max_neighbors": int(row["max_neighbors"]),
                        "max_atoms_per_cell": int(row["max_atoms_per_cell"]),
                        "throughput": float(row["throughput"]),
                        "step_ms": float(row["step_ms"]),
                        "force_rmse": float(row["force_rmse"]),
                        "cpu_util_percent": float(row["cpu_util_percent"]),
                        "gpu_util_percent": float(row["gpu_util_percent"]),
                        "throughput_gain_pct_vs_baseline": (
                            (float(row["throughput"]) - float(baseline["throughput"]))
                            / max(float(baseline["throughput"]), 1e-12)
                            * 100.0
                        ),
                        "rmse_delta_vs_baseline": float(row["force_rmse"]) - float(baseline["force_rmse"]),
                        "selection_reason": (
                            best["selection_reason"]
                            if row["neighbor_settings"] == best["neighbor_settings"]
                            else "candidate"
                        ),
                    }
                )

    df = pd.DataFrame(all_rows)
    os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_policy_json) or ".", exist_ok=True)
    df.to_csv(args.out_csv, index=False)

    summary = {
        "targets": targets,
        "speed_mode": str(args.speed_mode),
        "resolved_speed_profile": resolved_speed_profile,
        "baseline_neighbor_settings": base_neighbor,
        "best_by_target": best_by_target,
        "neighbor_policy": neighbor_policy,
        "files": {
            "out_csv": os.path.abspath(args.out_csv),
            "out_policy_json": os.path.abspath(args.out_policy_json),
        },
    }
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with open(args.out_policy_json, "w", encoding="utf-8") as f:
        json.dump(neighbor_policy, f, indent=2, ensure_ascii=False)

    print(
        json.dumps(
            {
                "targets": targets,
                "out_csv": args.out_csv,
                "out_json": args.out_json,
                "out_policy_json": args.out_policy_json,
                "best_by_target": {
                    k: {
                        "throughput_gain_pct_vs_baseline": v["throughput_gain_pct_vs_baseline"],
                        "rmse_delta_vs_baseline": v["rmse_delta_vs_baseline"],
                        "selection_reason": v["selection_reason"],
                        "neighbor_settings": v["neighbor_settings"],
                    }
                    for k, v in best_by_target.items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
