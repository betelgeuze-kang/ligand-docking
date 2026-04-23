#!/usr/bin/env python3

import argparse
import json
import os
import sys
from types import SimpleNamespace
from typing import Dict, List, Set, Tuple

import pandas as pd
import torch

from core.definitions import ResearchConstants
from tools.report_neighbor_force_parity import run_parity
from tools.stage2_full_report import run_report as run_stage2_report


def _parse_targets(spec: str) -> List[str]:
    if spec.strip().lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in spec.split(",") if x.strip()]


def _safe_int(raw, default: int = 0) -> int:
    try:
        return int(raw)
    except Exception:
        return int(default)


def _optional_positive_int(raw) -> int | None:
    v = _safe_int(raw, default=0)
    return int(v) if int(v) > 0 else None


def _mk_fail(scope: str, metric: str, value: float, threshold: float, op: str, target: str = "") -> Dict[str, object]:
    return {
        "scope": scope,
        "target": target,
        "metric": metric,
        "value": float(value),
        "threshold": float(threshold),
        "operator": op,
    }


def evaluate_parity_gate(
    parity_df: pd.DataFrame,
    jaccard_threshold: float,
    e2e_rmse_threshold: float,
    rel_rmse_threshold: float,
    strict_mode: bool,
    strict_kernel_rmse_threshold: float,
    strict_nblist_effect_threshold: float,
    strict_nblist_effect_rs_threshold: float,
) -> Tuple[pd.DataFrame, List[Dict[str, object]], List[Dict[str, object]], Set[str]]:
    failed_metrics: List[Dict[str, object]] = []
    failed_targets: Set[str] = set()
    overflow_events: List[Dict[str, object]] = []
    out_rows: List[Dict[str, object]] = []

    for _, row in parity_df.iterrows():
        target = str(row["target"])
        reasons: List[str] = []
        target_failed = False

        jaccard = float(row.get("neighbor_jaccard_mean", 0.0))
        e2e_rmse = float(row.get("e2e_rmse_mean_raw", row.get("force_rmse_mean_raw", 1e30)))
        e2e_rel = float(
            row.get(
                "e2e_rel_rmse_mean_clipped",
                row.get("force_rel_rmse_mean_clipped200", 1e30),
            )
        )
        kernel_shared_rs_rmse = float(row.get("kernel_shared_rs_rmse_mean_raw", 0.0))
        nblist_effect_py_rmse = float(row.get("nblist_effect_py_rmse_mean_raw", 0.0))
        nblist_effect_rs_rmse = float(row.get("nblist_effect_rs_rmse_mean_raw", 0.0))

        rs_neighbor_saturated_samples = int(row.get("rs_neighbor_saturated_samples", 0))
        rs_cell_overflow_samples = int(row.get("rs_cell_overflow_samples", 0))
        py_saturated_atoms_max = int(row.get("py_saturated_atoms_max", 0))
        rs_max_cell_count_max = int(row.get("rs_max_cell_count_max", 0))
        rs_builder_max_atoms_per_cell_max = int(row.get("rs_builder_max_atoms_per_cell_max", 0))
        rs_builder_max_neighbors_max = int(row.get("rs_builder_max_neighbors_max", 0))
        py_max_required_neighbors_max = int(row.get("py_max_required_neighbors_max", 0))
        py_effective_max_neighbors_max = int(row.get("py_effective_max_neighbors_max", 0))

        overflow_flag = (
            rs_neighbor_saturated_samples > 0
            or rs_cell_overflow_samples > 0
            or py_saturated_atoms_max > 0
        )
        if overflow_flag:
            overflow_events.append(
                {
                    "target": target,
                    "rs_neighbor_saturated_samples": rs_neighbor_saturated_samples,
                    "rs_cell_overflow_samples": rs_cell_overflow_samples,
                    "py_saturated_atoms_max": py_saturated_atoms_max,
                    "rs_max_cell_count_max": rs_max_cell_count_max,
                    "rs_builder_max_atoms_per_cell_max": rs_builder_max_atoms_per_cell_max,
                    "rs_builder_max_neighbors_max": rs_builder_max_neighbors_max,
                    "py_max_required_neighbors_max": py_max_required_neighbors_max,
                    "py_effective_max_neighbors_max": py_effective_max_neighbors_max,
                }
            )
            target_failed = True
            failed_targets.add(target)
            reasons.append("overflow_or_saturation_detected")
            failed_metrics.append(
                _mk_fail(
                    scope="parity_overflow",
                    target=target,
                    metric="overflow_or_saturation",
                    value=1.0,
                    threshold=0.0,
                    op="==",
                )
            )

        if jaccard < jaccard_threshold:
            target_failed = True
            failed_targets.add(target)
            reasons.append("neighbor_jaccard")
            failed_metrics.append(
                _mk_fail(
                    scope="parity",
                    target=target,
                    metric="neighbor_jaccard_mean",
                    value=jaccard,
                    threshold=jaccard_threshold,
                    op=">=",
                )
            )
        if e2e_rmse > e2e_rmse_threshold:
            target_failed = True
            failed_targets.add(target)
            reasons.append("e2e_rmse_raw")
            failed_metrics.append(
                _mk_fail(
                    scope="parity",
                    target=target,
                    metric="e2e_rmse_mean_raw",
                    value=e2e_rmse,
                    threshold=e2e_rmse_threshold,
                    op="<=",
                )
            )
        if e2e_rel > rel_rmse_threshold:
            target_failed = True
            failed_targets.add(target)
            reasons.append("e2e_rel_rmse_clipped")
            failed_metrics.append(
                _mk_fail(
                    scope="parity",
                    target=target,
                    metric="e2e_rel_rmse_mean_clipped",
                    value=e2e_rel,
                    threshold=rel_rmse_threshold,
                    op="<=",
                )
            )

        if strict_mode:
            if kernel_shared_rs_rmse > strict_kernel_rmse_threshold:
                target_failed = True
                failed_targets.add(target)
                reasons.append("strict_kernel_shared_rs_rmse")
                failed_metrics.append(
                    _mk_fail(
                        scope="strict_parity",
                        target=target,
                        metric="kernel_shared_rs_rmse_mean_raw",
                        value=kernel_shared_rs_rmse,
                        threshold=strict_kernel_rmse_threshold,
                        op="<=",
                    )
                )
            if nblist_effect_py_rmse > strict_nblist_effect_threshold:
                target_failed = True
                failed_targets.add(target)
                reasons.append("strict_nblist_effect_py_rmse")
                failed_metrics.append(
                    _mk_fail(
                        scope="strict_parity",
                        target=target,
                        metric="nblist_effect_py_rmse_mean_raw",
                        value=nblist_effect_py_rmse,
                        threshold=strict_nblist_effect_threshold,
                        op="<=",
                    )
                )
            if nblist_effect_rs_rmse > strict_nblist_effect_rs_threshold:
                target_failed = True
                failed_targets.add(target)
                reasons.append("strict_nblist_effect_rs_rmse")
                failed_metrics.append(
                    _mk_fail(
                        scope="strict_parity",
                        target=target,
                        metric="nblist_effect_rs_rmse_mean_raw",
                        value=nblist_effect_rs_rmse,
                        threshold=strict_nblist_effect_rs_threshold,
                        op="<=",
                    )
                )

        out_rows.append(
            {
                "target": target,
                "pass": (not target_failed),
                "neighbor_jaccard_mean": jaccard,
                "e2e_rmse_mean_raw": e2e_rmse,
                "e2e_rel_rmse_mean_clipped": e2e_rel,
                "kernel_shared_rs_rmse_mean_raw": kernel_shared_rs_rmse,
                "nblist_effect_py_rmse_mean_raw": nblist_effect_py_rmse,
                "nblist_effect_rs_rmse_mean_raw": nblist_effect_rs_rmse,
                "rs_neighbor_saturated_samples": rs_neighbor_saturated_samples,
                "rs_cell_overflow_samples": rs_cell_overflow_samples,
                "py_saturated_atoms_max": py_saturated_atoms_max,
                "reasons": ",".join(reasons),
            }
        )

    return pd.DataFrame(out_rows), failed_metrics, overflow_events, failed_targets


def evaluate_speed_gate(
    perf_summary: Dict[str, float],
    perf_rows: List[Dict[str, object]],
    speedup_threshold: float,
    speedup_per_target_threshold: float,
) -> List[Dict[str, object]]:
    failed_metrics: List[Dict[str, object]] = []
    speedup = float(perf_summary.get("avg_speedup_on_vs_off", 0.0))
    if speedup < speedup_threshold:
        failed_metrics.append(
            _mk_fail(
                scope="performance",
                target="all",
                metric="avg_speedup_on_vs_off",
                value=speedup,
                threshold=speedup_threshold,
                op=">=",
            )
        )
    if float(speedup_per_target_threshold) > 0.0:
        for row in perf_rows:
            target = str(row.get("target", "unknown"))
            per_target_speedup = float(row.get("speedup_on_vs_off", 0.0))
            if per_target_speedup < speedup_per_target_threshold:
                failed_metrics.append(
                    _mk_fail(
                        scope="performance_per_target",
                        target=target,
                        metric="speedup_on_vs_off",
                        value=per_target_speedup,
                        threshold=speedup_per_target_threshold,
                        op=">=",
                    )
                )
    return failed_metrics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate strict accuracy gate for Rust HIP + auto-grow.")
    parser.add_argument("--targets", type=str, default="all")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--noise", type=float, default=0.08)
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--warmup-steps", type=int, default=40)
    parser.add_argument("--benchmark-replicas", type=int, default=1)
    parser.add_argument("--use-ai-router", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--ai-router-checkpoint", type=str, default="")
    parser.add_argument("--ai-router-checkpoint-strict", action=argparse.BooleanOptionalAction, default=False)
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
    parser.add_argument("--cutoff", type=float, default=12.0)
    parser.add_argument("--skin", type=float, default=2.0)
    parser.add_argument("--max-neighbors", type=int, default=100)
    parser.add_argument("--max-atoms-per-cell", type=int, default=64)
    parser.add_argument("--rebuild-stride", type=int, default=4)
    parser.add_argument("--reference-cutoff", type=float, default=14.0)
    parser.add_argument("--reference-max-neighbors", type=int, default=160)
    parser.add_argument("--jaccard-threshold", type=float, default=1.0)
    parser.add_argument("--e2e-rmse-threshold", type=float, default=0.35)
    parser.add_argument("--rel-rmse-threshold", type=float, default=1e-5)
    parser.add_argument("--speedup-threshold", type=float, default=12.0)
    parser.add_argument("--speedup-per-target-threshold", type=float, default=0.0)
    parser.add_argument("--strict-kernel-rmse-threshold", type=float, default=0.45)
    parser.add_argument("--strict-nblist-effect-threshold", type=float, default=0.12)
    parser.add_argument("--strict-nblist-effect-rs-threshold", type=float, default=1e-8)
    parser.add_argument("--strict-mode", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--speed-mode",
        type=str,
        default="balanced",
        choices=["balanced", "fast", "ultra", "turbo", "extreme", "warp", "titan", "max"],
        help="Speed preset for internal stage-2 benchmark in accuracy gate",
    )
    parser.add_argument(
        "--disable-stochastic-noise",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Force Langevin stochastic term off during internal stage-2 benchmark.",
    )
    parser.add_argument(
        "--precompute-stochastic-noise",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Precompute Langevin noise in fixed-size blocks during internal stage-2 benchmark.",
    )
    parser.add_argument(
        "--precompute-stochastic-noise-block-steps",
        type=int,
        default=None,
        help="Noise precompute block size (steps) for internal stage-2 benchmark.",
    )
    parser.add_argument(
        "--sample-gpu-metrics",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable per-run GPU metric sampling in internal stage-2 benchmark.",
    )
    parser.add_argument(
        "--speed-mode-replicas",
        type=int,
        default=0,
        help="Minimum replicas enforced by speed-mode profile",
    )
    parser.add_argument(
        "--speed-profile-max-replicas",
        type=int,
        default=0,
        help="Optional max replicas cap applied to speed profile.",
    )
    parser.add_argument("--enforce-speed-gate", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--outlier-mode", type=str, default="shared_rs_nblist")
    parser.add_argument("--out-json", type=str, default="runs/accuracy_gate.json")
    parser.add_argument("--out-csv", type=str, default="runs/accuracy_gate.csv")
    parser.add_argument("--parity-prefix", type=str, default="runs/accuracy_gate_parity")
    parser.add_argument("--stage2-prefix", type=str, default="runs/accuracy_gate_stage2")
    parser.add_argument("--benchmark-csv", type=str, default="benchmark_results.csv")
    return parser


def run_accuracy_gate(args) -> Dict[str, object]:
    targets = _parse_targets(args.targets)
    neighbor_settings = {
        "grid_spacing": float(args.cutoff),
        "cutoff": float(args.cutoff),
        "skin": float(args.skin),
        "max_neighbors": int(args.max_neighbors),
        "max_atoms_per_cell": int(args.max_atoms_per_cell),
        "rebuild_stride": int(args.rebuild_stride),
    }

    os.environ.setdefault("FORCE_RUST_HIP", "1")
    os.environ.setdefault("RUST_HIP_USE_GPU_NBLIST_BUILDER", "1")
    os.environ.setdefault("NBLIST_AUTOGROW", "1")
    os.environ.setdefault("RUST_HIP_NBLIST_AUTOGROW", "1")

    seed = int(getattr(args, "seed", 1234))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    parity_target_csv = f"{args.parity_prefix}_target.csv"
    parity_sample_csv = f"{args.parity_prefix}_sample.csv"
    parity_atom_csv = f"{args.parity_prefix}_atom.csv"
    parity_pair_csv = f"{args.parity_prefix}_pair.csv"
    parity_json = f"{args.parity_prefix}.json"
    parity_payload = run_parity(
        targets=targets,
        samples=int(args.samples),
        noise=float(args.noise),
        neighbor_settings=neighbor_settings,
        out_target_csv=parity_target_csv,
        out_sample_csv=parity_sample_csv,
        out_atom_csv=parity_atom_csv,
        out_pair_csv=parity_pair_csv,
        out_json=parity_json,
        clip=200.0,
        topk_atoms=16,
        topk_pairs_per_atom=4,
        outlier_mode=args.outlier_mode,
    )

    stage2_args = SimpleNamespace(
        steps=int(args.steps),
        runs=int(args.runs),
        warmup_steps=int(getattr(args, "warmup_steps", 40)),
        benchmark_replicas=int(getattr(args, "benchmark_replicas", 1)),
        speed_mode=str(getattr(args, "speed_mode", "balanced")).strip().lower(),
        speed_mode_replicas=int(getattr(args, "speed_mode_replicas", 0)),
        use_ai_router=bool(getattr(args, "use_ai_router", False)),
        ai_router_checkpoint=str(getattr(args, "ai_router_checkpoint", "")).strip(),
        ai_router_checkpoint_strict=bool(getattr(args, "ai_router_checkpoint_strict", False)),
        ai_interval=int(getattr(args, "ai_interval", 1)),
        target_ai_interval_policy=str(getattr(args, "target_ai_interval_policy", "")),
        target_ai_drift_threshold_policy=str(
            getattr(args, "target_ai_drift_threshold_policy", "")
        ),
        adaptive_ai_interval=bool(getattr(args, "adaptive_ai_interval", False)),
        ai_interval_min=int(getattr(args, "ai_interval_min", 1)),
        ai_interval_max=int(getattr(args, "ai_interval_max", 0)),
        ai_downshift_factor=int(getattr(args, "ai_downshift_factor", 2)),
        ai_drift_disp_threshold=float(getattr(args, "ai_drift_disp_threshold", 0.25)),
        ai_drift_check_stride=int(getattr(args, "ai_drift_check_stride", 1)),
        ai_stable_upshift_window=int(getattr(args, "ai_stable_upshift_window", 0)),
        ai_interval_min_ratio=float(getattr(args, "ai_interval_min_ratio", 0.0)),
        enable_physics_filter=bool(getattr(args, "enable_physics_filter", False)),
        physics_filter_mode=str(getattr(args, "physics_filter_mode", "rollback")),
        physics_filter_max_energy_drift=float(getattr(args, "physics_filter_max_energy_drift", 0.015)),
        physics_filter_max_momentum_drift=float(getattr(args, "physics_filter_max_momentum_drift", 0.015)),
        physics_filter_min_interatomic_distance=float(
            getattr(args, "physics_filter_min_interatomic_distance", 0.0)
        ),
        eval_samples=int(args.samples),
        eval_noise=float(args.noise),
        reference_cutoff=float(args.reference_cutoff),
        reference_max_neighbors=int(args.reference_max_neighbors),
        cutoff=float(args.cutoff),
        skin=float(args.skin),
        max_neighbors=int(args.max_neighbors),
        max_atoms_per_cell=int(args.max_atoms_per_cell),
        rebuild_stride=int(args.rebuild_stride),
        with_fallback=True,
        force_rust=True,
        targets=args.targets,
        report_csv=f"{args.stage2_prefix}.csv",
        report_json=f"{args.stage2_prefix}.json",
        disable_stochastic_noise=getattr(args, "disable_stochastic_noise", None),
        precompute_stochastic_noise=getattr(args, "precompute_stochastic_noise", None),
        precompute_stochastic_noise_block_steps=getattr(
            args,
            "precompute_stochastic_noise_block_steps",
            None,
        ),
        sample_gpu_metrics=getattr(args, "sample_gpu_metrics", None),
        benchmark_csv=args.benchmark_csv,
        speed_profile_max_replicas=_optional_positive_int(
            getattr(args, "speed_profile_max_replicas", 0)
        ),
    )
    perf_payload = run_stage2_report(stage2_args)

    parity_df = pd.read_csv(parity_target_csv)
    gate_df, failed_metrics, overflow_events, failed_targets = evaluate_parity_gate(
        parity_df=parity_df,
        jaccard_threshold=float(args.jaccard_threshold),
        e2e_rmse_threshold=float(args.e2e_rmse_threshold),
        rel_rmse_threshold=float(args.rel_rmse_threshold),
        strict_mode=bool(args.strict_mode),
        strict_kernel_rmse_threshold=float(args.strict_kernel_rmse_threshold),
        strict_nblist_effect_threshold=float(args.strict_nblist_effect_threshold),
        strict_nblist_effect_rs_threshold=float(args.strict_nblist_effect_rs_threshold),
    )
    enforce_speed_gate = (
        bool(args.enforce_speed_gate)
        if getattr(args, "enforce_speed_gate", None) is not None
        else (len(targets) > 1)
    )
    if enforce_speed_gate:
        speed_failures = evaluate_speed_gate(
            perf_summary=perf_payload.get("summary", {}),
            perf_rows=list(perf_payload.get("rows", [])),
            speedup_threshold=float(args.speedup_threshold),
            speedup_per_target_threshold=float(args.speedup_per_target_threshold),
        )
        failed_metrics.extend(speed_failures)
        for item in speed_failures:
            if item.get("target") and item.get("target") != "all":
                failed_targets.add(str(item["target"]))

    gate_pass = len(failed_metrics) == 0
    out_dir = os.path.dirname(args.out_json) or "."
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
    gate_df.to_csv(args.out_csv, index=False)

    payload = {
        "summary": {
            "pass": bool(gate_pass),
            "targets": int(len(targets)),
            "seed": seed,
            "samples": int(args.samples),
            "noise": float(args.noise),
            "strict_mode": bool(args.strict_mode),
            "enforce_speed_gate": bool(enforce_speed_gate),
            "failed_targets": sorted(failed_targets),
            "failed_metrics": failed_metrics,
            "thresholds": {
                "neighbor_jaccard_mean": float(args.jaccard_threshold),
                "e2e_rmse_mean_raw": float(args.e2e_rmse_threshold),
                "e2e_rel_rmse_mean_clipped": float(args.rel_rmse_threshold),
                "avg_speedup_on_vs_off": float(args.speedup_threshold),
                "speedup_on_vs_off_per_target": float(args.speedup_per_target_threshold),
                "strict_kernel_shared_rs_rmse_mean_raw": float(args.strict_kernel_rmse_threshold),
                "strict_nblist_effect_py_rmse_mean_raw": float(args.strict_nblist_effect_threshold),
                "strict_nblist_effect_rs_rmse_mean_raw": float(args.strict_nblist_effect_rs_threshold),
            },
            "runtime_options": {
                "use_ai_router": bool(getattr(args, "use_ai_router", False)),
                "ai_router_checkpoint": str(getattr(args, "ai_router_checkpoint", "")).strip() or None,
                "ai_router_checkpoint_strict": bool(getattr(args, "ai_router_checkpoint_strict", False)),
                "ai_interval": int(getattr(args, "ai_interval", 1)),
                "target_ai_interval_policy": str(getattr(args, "target_ai_interval_policy", "")),
                "target_ai_drift_threshold_policy": str(
                    getattr(args, "target_ai_drift_threshold_policy", "")
                ),
                "adaptive_ai_interval": bool(getattr(args, "adaptive_ai_interval", False)),
                "ai_interval_min": int(getattr(args, "ai_interval_min", 1)),
                "ai_interval_max": int(getattr(args, "ai_interval_max", 0)),
                "ai_downshift_factor": int(getattr(args, "ai_downshift_factor", 2)),
                "ai_drift_disp_threshold": float(getattr(args, "ai_drift_disp_threshold", 0.25)),
                "ai_drift_check_stride": int(getattr(args, "ai_drift_check_stride", 1)),
                "ai_stable_upshift_window": int(getattr(args, "ai_stable_upshift_window", 0)),
                "ai_interval_min_ratio": float(getattr(args, "ai_interval_min_ratio", 0.0)),
                "enable_physics_filter": bool(getattr(args, "enable_physics_filter", False)),
                "physics_filter_mode": str(getattr(args, "physics_filter_mode", "rollback")),
                "physics_filter_max_energy_drift": float(
                    getattr(args, "physics_filter_max_energy_drift", 0.015)
                ),
                "physics_filter_max_momentum_drift": float(
                    getattr(args, "physics_filter_max_momentum_drift", 0.015)
                ),
                "physics_filter_min_interatomic_distance": float(
                    getattr(args, "physics_filter_min_interatomic_distance", 0.0)
                ),
                "speed_mode": str(getattr(args, "speed_mode", "balanced")),
                "speed_mode_replicas": _safe_int(getattr(args, "speed_mode_replicas", 0), 0),
                "speed_profile_max_replicas": _safe_int(
                    getattr(args, "speed_profile_max_replicas", 0),
                    0,
                ),
                "disable_stochastic_noise": getattr(args, "disable_stochastic_noise", None),
                "precompute_stochastic_noise": getattr(args, "precompute_stochastic_noise", None),
                "precompute_stochastic_noise_block_steps": getattr(
                    args,
                    "precompute_stochastic_noise_block_steps",
                    None,
                ),
                "sample_gpu_metrics": getattr(args, "sample_gpu_metrics", None),
            },
        },
        "parity_summary": parity_payload.get("summary", {}),
        "performance_summary": perf_payload.get("summary", {}),
        "overflow_events": overflow_events,
        "files": {
            "gate_csv": args.out_csv,
            "parity_target_csv": parity_target_csv,
            "parity_sample_csv": parity_sample_csv,
            "parity_atom_csv": parity_atom_csv,
            "parity_pair_csv": parity_pair_csv,
            "parity_json": parity_json,
            "stage2_csv": stage2_args.report_csv,
            "stage2_json": stage2_args.report_json,
        },
    }
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = run_accuracy_gate(args)
    summary = payload["summary"]
    print(json.dumps(summary, indent=2))
    if not summary["pass"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
