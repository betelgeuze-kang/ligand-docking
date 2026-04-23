#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd
import torch

from benchmark.performance_bench import benchmark_simulation
from core.definitions import ResearchConstants
from core.mts_policy import parse_target_drift_threshold_policy, parse_target_interval_policy
from tools.speed_profile import apply_speed_profile_env, resolve_speed_profile


def _detect_hip_graph_capability() -> Tuple[bool, str, Dict[str, Any]]:
    details: Dict[str, Any] = {
        "torch_cuda_available": bool(torch.cuda.is_available()),
    }
    if not torch.cuda.is_available():
        return False, "cuda_unavailable", details
    try:
        props = torch.cuda.get_device_properties(0)
        name = str(getattr(props, "name", "unknown"))
        gcn = str(getattr(props, "gcnArchName", "") or "").strip().lower()
        details["device_name"] = name
        details["gcn_arch_name"] = gcn or "unknown"
        # Conservative allow-list for known stable datacenter-like ROCm targets.
        allow_prefixes = ("gfx90a", "gfx94", "gfx110")
        if gcn and any(gcn.startswith(pref) for pref in allow_prefixes):
            return True, "ok", details
        return False, f"unsupported_gpu_arch:{gcn or 'unknown'}", details
    except Exception as exc:
        details["exception"] = f"{type(exc).__name__}: {exc}"
        return False, "capability_probe_failed", details


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


def _run_one(
    *,
    target: str,
    graph_on: bool,
    steps: int,
    runs: int,
    warmup_steps: int,
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
    ai_graph_warmup_iters: int,
    track_clip_hits: bool,
    profile_components: bool,
    sample_gpu_metrics: bool,
    benchmark_csv: Optional[str],
) -> Dict[str, Any]:
    perf = benchmark_simulation(
        target=target,
        steps=int(steps),
        use_ai_router=True,
        num_runs=int(runs),
        warmup_steps=int(warmup_steps),
        batch_replicas=int(benchmark_replicas),
        ai_interval=int(ai_interval),
        output_file=benchmark_csv,
        neighbor_settings={
            "grid_spacing": 12.0,
            "cutoff": 12.0,
            "skin": 2.0,
            "max_neighbors": 100,
            "max_atoms_per_cell": 64,
            "rebuild_stride": 4,
        },
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
        ai_use_hip_graph=bool(graph_on),
        ai_graph_warmup_iters=int(ai_graph_warmup_iters),
        track_clip_hits=bool(track_clip_hits),
        profile_components=bool(profile_components),
        sample_gpu_metrics=bool(sample_gpu_metrics),
    )
    return {
        "target": target,
        "hip_graph_requested": bool(graph_on),
        "run_status": "ok",
        "run_error": "",
        "throughput": float(perf["avg_throughput_steps_per_sec"]),
        "step_ms": float(perf["avg_time_per_step_ms"]),
        "ai_infer_ms": float(perf.get("ai_inference_time_per_step_ms", 0.0) or 0.0),
        "cpu_util_percent": float(perf.get("avg_cpu_util_percent", 0.0)),
        "gpu_util_percent": float(perf.get("avg_gpu_util_percent", 0.0)),
        "ai_graph_enabled_flag": float(perf.get("avg_ai_graph_enabled_flag", 0.0) or 0.0),
        "ai_graph_last_reason": str(perf.get("ai_graph_last_reason", "unknown")),
        "ai_calls": float(perf.get("avg_ai_inference_calls_per_run", 0.0) or 0.0),
        "ai_reuse": float(perf.get("avg_ai_reuse_steps_per_run", 0.0) or 0.0),
        "ai_interval_target": int(perf.get("ai_interval_target", perf.get("ai_interval", 1))),
        "ai_interval_active": float(perf.get("avg_ai_interval_active_per_step", 1.0) or 1.0),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="A/B test HIP graph replay on selected targets.")
    p.add_argument("--targets", type=str, default="Protein_A_Bdomain,WW_Domain_FiP35")
    p.add_argument("--steps", type=int, default=60)
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--warmup-steps", type=int, default=30)
    p.add_argument("--force-backend", type=str, default="auto", choices=["auto", "pytorch"])
    p.add_argument("--force-rust", action=argparse.BooleanOptionalAction, default=True)
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
    p.add_argument("--ai-graph-warmup-iters", type=int, default=2)
    p.add_argument("--allow-unsafe-graph", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--track-clip-hits", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--profile-components", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--sample-gpu-metrics", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--out-csv", type=str, default="runs/ai_hip_graph_ab_2026-02-18.csv")
    p.add_argument("--out-json", type=str, default="runs/ai_hip_graph_ab_2026-02-18.json")
    p.add_argument("--benchmark-csv", type=str, default="runs/ai_hip_graph_ab_2026-02-18_bench.csv")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)

    if args.force_rust:
        os.environ["FORCE_RUST_HIP"] = "1"
        os.environ.setdefault("RUST_HIP_USE_GPU_NBLIST_BUILDER", "1")
        os.environ.setdefault("NBLIST_AUTOGROW", "1")
        os.environ.setdefault("RUST_HIP_NBLIST_AUTOGROW", "1")

    targets = _parse_targets(args.targets)
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
        ai_use_hip_graph=False,
        ai_graph_warmup_iters=int(args.ai_graph_warmup_iters),
        track_clip_hits=bool(args.track_clip_hits),
        profile_components=bool(args.profile_components),
        sample_gpu_metrics=bool(args.sample_gpu_metrics),
        speed_mode_replicas=int(args.speed_mode_replicas),
        speed_profile_max_replicas=(
            int(speed_profile_max_replicas) if speed_profile_max_replicas > 0 else None
        ),
    )

    rows: List[Dict[str, Any]] = []
    graph_capable, graph_reason, graph_details = _detect_hip_graph_capability()
    if bool(args.allow_unsafe_graph):
        graph_capable = True
        graph_reason = "force_enabled_by_flag"
    with apply_speed_profile_env(resolved_speed_profile.get("env")):
        for idx, target in enumerate(targets, start=1):
            print(f"[{idx}/{len(targets)}] target={target} graph=off")
            off = _run_one(
                target=target,
                graph_on=False,
                steps=int(args.steps),
                runs=int(args.runs),
                warmup_steps=int(args.warmup_steps),
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
                ai_graph_warmup_iters=int(resolved_speed_profile["ai_graph_warmup_iters"]),
                track_clip_hits=bool(resolved_speed_profile["track_clip_hits"]),
                profile_components=bool(resolved_speed_profile["profile_components"]),
                sample_gpu_metrics=bool(resolved_speed_profile["sample_gpu_metrics"]),
                benchmark_csv=(str(args.benchmark_csv).strip() or None),
            )
            print(f"[{idx}/{len(targets)}] target={target} graph=on")
            if graph_capable:
                on = _run_one(
                    target=target,
                    graph_on=True,
                    steps=int(args.steps),
                    runs=int(args.runs),
                    warmup_steps=int(args.warmup_steps),
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
                    ai_graph_warmup_iters=int(resolved_speed_profile["ai_graph_warmup_iters"]),
                    track_clip_hits=bool(resolved_speed_profile["track_clip_hits"]),
                    profile_components=bool(resolved_speed_profile["profile_components"]),
                    sample_gpu_metrics=bool(resolved_speed_profile["sample_gpu_metrics"]),
                    benchmark_csv=(str(args.benchmark_csv).strip() or None),
                )
            else:
                on = {
                    "target": target,
                    "hip_graph_requested": True,
                    "run_status": "skipped",
                    "run_error": graph_reason,
                    "throughput": float("nan"),
                    "step_ms": float("nan"),
                    "ai_infer_ms": float("nan"),
                    "cpu_util_percent": float("nan"),
                    "gpu_util_percent": float("nan"),
                    "ai_graph_enabled_flag": 0.0,
                    "ai_graph_last_reason": graph_reason,
                    "ai_calls": float("nan"),
                    "ai_reuse": float("nan"),
                    "ai_interval_target": int(off.get("ai_interval_target", 1)),
                    "ai_interval_active": float("nan"),
                }
            rows.extend([off, on])

    df = pd.DataFrame(rows).sort_values(["target", "hip_graph_requested"]).reset_index(drop=True)
    comp_rows: List[Dict[str, Any]] = []
    for target in targets:
        sub = df[df["target"] == target]
        row_off = sub[sub["hip_graph_requested"] == False].iloc[0]  # noqa: E712
        row_on = sub[sub["hip_graph_requested"] == True].iloc[0]  # noqa: E712
        off_tp = float(row_off["throughput"])
        on_tp = float(row_on["throughput"])
        gain = float("nan")
        if pd.notna(off_tp) and pd.notna(on_tp):
            gain = (on_tp - off_tp) / max(off_tp, 1e-12) * 100.0
        comp_rows.append(
            {
                "target": target,
                "throughput_off": off_tp,
                "throughput_on": on_tp,
                "throughput_gain_pct": gain,
                "step_ms_off": float(row_off["step_ms"]),
                "step_ms_on": float(row_on["step_ms"]),
                "ai_graph_enabled_flag_off": float(row_off["ai_graph_enabled_flag"]),
                "ai_graph_enabled_flag_on": float(row_on["ai_graph_enabled_flag"]),
                "ai_graph_last_reason_off": str(row_off["ai_graph_last_reason"]),
                "ai_graph_last_reason_on": str(row_on["ai_graph_last_reason"]),
                "graph_on_status": str(row_on.get("run_status", "ok")),
                "graph_on_error": str(row_on.get("run_error", "")),
            }
        )
    comp_df = pd.DataFrame(comp_rows).sort_values("throughput_gain_pct", ascending=False).reset_index(drop=True)

    os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    df.to_csv(args.out_csv, index=False)
    summary = {
        "targets": targets,
        "speed_mode": str(args.speed_mode),
        "resolved_speed_profile": resolved_speed_profile,
        "hip_graph_capability": {
            "capable": bool(graph_capable),
            "reason": graph_reason,
            "details": graph_details,
            "allow_unsafe_graph": bool(args.allow_unsafe_graph),
        },
        "avg_throughput_gain_pct": float(comp_df["throughput_gain_pct"].dropna().mean())
        if not comp_df["throughput_gain_pct"].dropna().empty
        else float("nan"),
        "max_throughput_gain_pct": float(comp_df["throughput_gain_pct"].dropna().max())
        if not comp_df["throughput_gain_pct"].dropna().empty
        else float("nan"),
        "min_throughput_gain_pct": float(comp_df["throughput_gain_pct"].dropna().min())
        if not comp_df["throughput_gain_pct"].dropna().empty
        else float("nan"),
        "rows": comp_rows,
        "files": {
            "out_csv": os.path.abspath(args.out_csv),
            "benchmark_csv": os.path.abspath(args.benchmark_csv) if str(args.benchmark_csv).strip() else None,
        },
    }
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(
        json.dumps(
            {
                "out_csv": args.out_csv,
                "out_json": args.out_json,
                "avg_throughput_gain_pct": summary["avg_throughput_gain_pct"],
                "rows": comp_rows,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
