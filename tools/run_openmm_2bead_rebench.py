#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from benchmark.accuracy_bench import run_accuracy_report
from core.definitions import ResearchConstants
from tools.generate_openmm_ca_md_references import generate_openmm_ca_md_references
from tools.report_sparse_checkpoints import run_sparse_checkpoint_report
from tools.run_target_tuned_long_stability import run_target_tuned_validation
from tools.stage2_full_report import run_report as run_stage2_full_report
from train.target_scheduler import FoldBalancedTargetScheduler


def _parse_targets(spec: str, seed: int) -> List[str]:
    s = str(spec).strip().lower()
    if s in ("noncyclic", "non_cyclic", "fold_balanced_noncyclic"):
        scheduler = FoldBalancedTargetScheduler()
        return scheduler.build_unique_fold_balanced_targets(seed=int(seed), shuffle=True)
    if s == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    out = [x.strip() for x in str(spec).split(",") if x.strip()]
    if not out:
        raise ValueError(f"no targets parsed from spec: {spec}")
    # Keep input order while dropping accidental duplicates.
    seen = set()
    uniq: List[str] = []
    for t in out:
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return uniq


def _csv_targets(targets: List[str]) -> str:
    return ",".join(targets)


def _default_paths(date_tag: str) -> Dict[str, str]:
    base = "runs"
    return {
        "openmm_dir": os.path.join(base, f"real_md_openmm_2bead_{date_tag}"),
        "openmm_manifest": os.path.join(base, f"real_md_source_manifest_openmm_2bead_{date_tag}.csv"),
        "openmm_json": os.path.join(base, f"real_md_source_manifest_openmm_2bead_{date_tag}_summary.json"),
        "stability_csv": os.path.join(base, f"long_stability_metrics_{date_tag}.csv"),
        "stability_summary_csv": os.path.join(base, f"long_stability_summary_{date_tag}.csv"),
        "stability_json": os.path.join(base, f"long_stability_report_{date_tag}.json"),
        "stage2_csv": os.path.join(base, f"noncyclic_stage2_rebench_{date_tag}.csv"),
        "stage2_json": os.path.join(base, f"noncyclic_stage2_rebench_{date_tag}.json"),
        "accuracy_csv": os.path.join(base, f"noncyclic_accuracy_external_openmm2b_{date_tag}.csv"),
        "accuracy_json": os.path.join(base, f"noncyclic_accuracy_external_openmm2b_{date_tag}.json"),
        "combined_csv": os.path.join(base, f"noncyclic_speed_accuracy_rebench_{date_tag}.csv"),
        "combined_json": os.path.join(base, f"noncyclic_speed_accuracy_rebench_{date_tag}.json"),
        "benchmark_csv": os.path.join(base, f"noncyclic_stage2_benchmark_raw_{date_tag}.csv"),
    }


def _to_namespace(**kwargs: Any) -> argparse.Namespace:
    return SimpleNamespace(**kwargs)


def _parse_checkpoint_list(spec: str) -> List[int]:
    raw = [x.strip() for x in str(spec).split(",") if x.strip()]
    out: List[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except Exception:
            continue
    if not out:
        out = [0]
    return sorted(set(out))


def _run_openmm_generation(
    targets: List[str],
    paths: Dict[str, str],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    gen_args = _to_namespace(
        targets=_csv_targets(targets),
        out_dir=paths["openmm_dir"],
        out_manifest=paths["openmm_manifest"],
        out_json=paths["openmm_json"],
        representation="ca_sc_2bead",
        steps=int(args.openmm_steps),
        save_stride=int(args.openmm_save_stride),
        temperature_k=float(args.temperature_k),
        friction_ps=float(args.friction_ps),
        dt_ps=float(args.dt_ps),
        sigma_nm=float(args.sigma_nm),
        epsilon_kj=float(args.epsilon_kj),
        bond_k_kj_nm2=float(args.bond_k_kj_nm2),
        angle_k_kj_rad2=float(args.angle_k_kj_rad2),
        sidechain_bond_k_kj_nm2=float(args.sidechain_bond_k_kj_nm2),
        sidechain_angle_k_kj_rad2=float(args.sidechain_angle_k_kj_rad2),
        sc_distance_nm=float(args.sc_distance_nm),
        ca_mass_amu=float(args.ca_mass_amu),
        sc_mass_amu=float(args.sc_mass_amu),
        sc_sigma_scale=float(args.sc_sigma_scale),
        sc_epsilon_scale=float(args.sc_epsilon_scale),
        exclude_local_sc_neighbors=bool(args.exclude_local_sc_neighbors),
        save_ca_projection=bool(args.save_ca_projection),
        cutoff_nm=float(args.cutoff_nm),
        platform=str(args.openmm_platform),
        seed_base=int(args.seed_base),
        minimize_iters=int(args.minimize_iters),
    )
    payload = generate_openmm_ca_md_references(gen_args)
    return payload


def _run_long_stability(
    targets: List[str],
    paths: Dict[str, str],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    st_args = _to_namespace(
        targets=_csv_targets(targets),
        runs=int(args.stability_runs),
        steps=int(args.stability_steps),
        checkpoints=str(args.stability_checkpoints),
        noise=float(args.stability_noise),
        seed=int(args.seed_base),
        dt=float(args.stability_dt),
        restraint_k=float(args.stability_restraint_k),
        force_clip=float(args.stability_force_clip),
        cutoff=float(args.cutoff_A),
        skin=float(args.skin_A),
        max_neighbors=int(args.max_neighbors),
        max_atoms_per_cell=int(args.max_atoms_per_cell),
        rebuild_stride=int(args.rebuild_stride),
        force_rust=bool(args.force_rust),
        force_backend=str(args.force_backend),
        clash_cutoff=float(args.clash_cutoff_A),
        aligned_rmsd_threshold=float(args.stability_aligned_rmsd_threshold),
        energy_drift_threshold=float(args.stability_energy_drift_threshold),
        rg_delta_threshold=float(args.stability_rg_delta_threshold),
        max_clash_pairs=int(args.stability_max_clash_pairs),
        out_csv=paths["stability_csv"],
        out_summary_csv=paths["stability_summary_csv"],
        out_json=paths["stability_json"],
        strict=False,
    )
    return run_sparse_checkpoint_report(st_args)


def _run_long_stability_tuned(
    targets: List[str],
    paths: Dict[str, str],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    profile_json = str(args.stability_profile_json).strip()
    if not profile_json:
        raise ValueError("stability_profile_json is required for tuned long-stability mode")
    if not os.path.exists(profile_json):
        raise FileNotFoundError(f"stability profile not found: {profile_json}")

    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    tuned_prefix = f"{os.path.splitext(paths['stability_json'])[0]}_tuned"
    tuned_args = _to_namespace(
        profile_json=profile_json,
        runs=int(args.stability_runs),
        steps=int(args.stability_steps),
        checkpoints=str(args.stability_checkpoints),
        noise=float(args.stability_noise),
        seed=int(args.seed_base),
        cutoff=float(args.cutoff_A),
        skin=float(args.skin_A),
        max_neighbors=int(args.max_neighbors),
        max_atoms_per_cell=int(args.max_atoms_per_cell),
        rebuild_stride=int(args.rebuild_stride),
        force_rust=bool(args.force_rust),
        force_backend=str(args.force_backend),
        clash_cutoff=float(args.clash_cutoff_A),
        aligned_rmsd_threshold=float(args.stability_aligned_rmsd_threshold),
        energy_drift_threshold=float(args.stability_energy_drift_threshold),
        rg_delta_threshold=float(args.stability_rg_delta_threshold),
        max_clash_pairs=int(args.stability_max_clash_pairs),
        date_tag=date_tag,
        out_prefix=tuned_prefix,
        out_csv=paths["stability_summary_csv"],
        out_json=paths["stability_json"],
    )
    tuned_payload = run_target_tuned_validation(tuned_args)
    tuned_summary = tuned_payload.get("summary", {}) if isinstance(tuned_payload, dict) else {}

    requested = list(targets)
    failed_targets = [str(x) for x in tuned_summary.get("failed_targets", [])] if isinstance(
        tuned_summary.get("failed_targets", []), list
    ) else []
    target_set = set(requested)
    failed_targets = [t for t in failed_targets if t in target_set]
    final_pass_targets = [t for t in requested if t not in set(failed_targets)]
    passed_targets = int(len(final_pass_targets))
    checkpoints = _parse_checkpoint_list(str(args.stability_checkpoints))
    gate_pass = bool((len(failed_targets) == 0) and (passed_targets == len(requested)))

    summary = {
        "targets": int(len(requested)),
        "runs_per_target": int(args.stability_runs),
        "checkpoints": checkpoints,
        "final_checkpoint": int(max(checkpoints)),
        "final_pass_targets": final_pass_targets,
        "failed_targets": failed_targets,
        "gate_pass": gate_pass,
        "thresholds": {
            "aligned_rmsd_threshold": float(args.stability_aligned_rmsd_threshold),
            "energy_drift_threshold": float(args.stability_energy_drift_threshold),
            "rg_delta_threshold": float(args.stability_rg_delta_threshold),
            "max_clash_pairs": int(args.stability_max_clash_pairs),
        },
        "profile_json": profile_json,
        "mode": "target_tuned_profile",
        "avg_rmsd_aligned_mean": (
            float(tuned_summary["avg_rmsd_aligned_mean"])
            if "avg_rmsd_aligned_mean" in tuned_summary
            else None
        ),
        "avg_energy_drift_ratio_mean": (
            float(tuned_summary["avg_energy_drift_ratio_mean"])
            if "avg_energy_drift_ratio_mean" in tuned_summary
            else None
        ),
    }
    return {"summary": summary}


def _run_speed_rebench(
    targets: List[str],
    paths: Dict[str, str],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    stage2_args = _to_namespace(
        steps=int(args.speed_steps),
        runs=int(args.speed_runs),
        use_ai_router=bool(args.use_ai_router),
        ai_router_checkpoint=str(getattr(args, "ai_router_checkpoint", "")).strip(),
        ai_router_checkpoint_strict=bool(getattr(args, "ai_router_checkpoint_strict", False)),
        ai_runtime_mode=str(getattr(args, "ai_runtime_mode", "scripted")).strip().lower(),
        speed_profile_preserve_runtime_mode=bool(
            getattr(args, "speed_profile_preserve_runtime_mode", True)
        ),
        ai_disable_exploration=bool(getattr(args, "ai_disable_exploration", True)),
        ai_use_hip_graph=bool(getattr(args, "ai_use_hip_graph", False)),
        ai_graph_warmup_iters=int(getattr(args, "ai_graph_warmup_iters", 2)),
        warmup_steps=int(args.speed_warmup_steps),
        benchmark_replicas=int(args.speed_benchmark_replicas),
        speed_mode=str(getattr(args, "speed_mode", "balanced")).strip().lower(),
        speed_mode_replicas=int(getattr(args, "speed_mode_replicas", 0)),
        speed_profile_max_replicas=int(getattr(args, "speed_profile_max_replicas", 0)) or None,
        ai_interval=int(args.ai_interval),
        target_ai_interval_policy=str(args.target_ai_interval_policy),
        target_ai_drift_threshold_policy=str(args.target_ai_drift_threshold_policy),
        adaptive_ai_interval=bool(args.adaptive_ai_interval),
        ai_interval_min=int(args.ai_interval_min),
        ai_interval_max=int(args.ai_interval_max),
        ai_downshift_factor=int(args.ai_downshift_factor),
        ai_drift_disp_threshold=float(args.ai_drift_disp_threshold),
        ai_drift_check_stride=int(args.ai_drift_check_stride),
        ai_stable_upshift_window=int(args.ai_stable_upshift_window),
        ai_interval_min_ratio=float(args.ai_interval_min_ratio),
        enable_physics_filter=bool(args.enable_physics_filter),
        physics_filter_mode=str(args.physics_filter_mode),
        physics_filter_max_energy_drift=float(args.physics_filter_max_energy_drift),
        physics_filter_max_momentum_drift=float(args.physics_filter_max_momentum_drift),
        physics_filter_min_interatomic_distance=float(args.physics_filter_min_interatomic_distance),
        eval_samples=int(args.speed_eval_samples),
        eval_noise=float(args.speed_eval_noise),
        reference_cutoff=float(args.reference_cutoff_A),
        reference_max_neighbors=int(args.reference_max_neighbors),
        cutoff=float(args.cutoff_A),
        skin=float(args.skin_A),
        max_neighbors=int(args.max_neighbors),
        max_atoms_per_cell=int(args.max_atoms_per_cell),
        rebuild_stride=int(args.rebuild_stride),
        disable_stochastic_noise=getattr(args, "disable_stochastic_noise", None),
        precompute_stochastic_noise=getattr(args, "precompute_stochastic_noise", None),
        precompute_stochastic_noise_block_steps=getattr(args, "precompute_stochastic_noise_block_steps", None),
        sample_gpu_metrics=getattr(args, "sample_gpu_metrics", None),
        with_fallback=bool(args.with_fallback),
        force_rust=bool(args.force_rust),
        targets=_csv_targets(targets),
        report_csv=paths["stage2_csv"],
        report_json=paths["stage2_json"],
        benchmark_csv=paths["benchmark_csv"],
    )
    return run_stage2_full_report(stage2_args)


def _run_accuracy_rebench(
    targets: List[str],
    external_manifest_csv: str,
    paths: Dict[str, str],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    if not os.path.exists(external_manifest_csv):
        raise FileNotFoundError(f"external manifest not found: {external_manifest_csv}")
    target_profile_json = str(getattr(args, "accuracy_target_profile_json", "")).strip()
    if not target_profile_json:
        target_profile_json = str(getattr(args, "stability_profile_json", "")).strip()
    acc_args = _to_namespace(
        targets=_csv_targets(targets),
        steps=int(args.accuracy_steps),
        runs=int(args.accuracy_runs),
        noise=float(args.accuracy_noise),
        seed_base=int(args.seed_base),
        reference_source="external",
        external_manifest=external_manifest_csv,
        external_key=None,
        external_frame=-1,
        external_summary_csv=None,
        compare_bead=str(args.compare_bead),
        target_profile_json=(target_profile_json or None),
        out_csv=paths["accuracy_csv"],
        out_json=paths["accuracy_json"],
    )
    return run_accuracy_report(acc_args)


def _merge_speed_accuracy(paths: Dict[str, str]) -> Dict[str, Any]:
    has_speed = os.path.exists(paths["stage2_csv"])
    acc_df = pd.read_csv(paths["accuracy_csv"])
    if not has_speed:
        merged = acc_df.copy()
        for col in [
            "throughput_on",
            "throughput_off",
            "speedup_on_vs_off",
            "step_ms_on",
            "step_ms_off",
            "force_rmse_on",
            "force_rmse_off",
        ]:
            if col not in merged.columns:
                merged[col] = float("nan")
        merged["speed_accuracy_score"] = float("nan")
        os.makedirs(os.path.dirname(paths["combined_csv"]) or ".", exist_ok=True)
        merged.to_csv(paths["combined_csv"], index=False)
        summary = {
            "targets": int(merged["target"].nunique()) if "target" in merged.columns else 0,
            "speed_rebench_skipped": True,
            "avg_throughput_on": None,
            "avg_speedup_on_vs_off": None,
            "avg_rmsd_aligned_vs_external": (
                float(merged["avg_rmsd_aligned"].mean()) if "avg_rmsd_aligned" in merged.columns else None
            ),
            "avg_rmsd_vs_native_aligned": (
                float(merged["avg_rmsd_vs_native_aligned"].mean())
                if "avg_rmsd_vs_native_aligned" in merged.columns
                else None
            ),
        }
        return {"summary": summary}

    speed_df = pd.read_csv(paths["stage2_csv"])
    cols = [
        "target",
        "avg_rmsd",
        "avg_rmsd_aligned",
        "avg_rmsd_vs_native_aligned",
        "comparison_projection",
        "reference_representation",
        "reference_path",
    ]
    use_cols = [c for c in cols if c in acc_df.columns]
    merged = speed_df.merge(acc_df[use_cols], on="target", how="left")
    if "throughput_on" in merged.columns and "avg_rmsd_aligned" in merged.columns:
        merged["speed_accuracy_score"] = merged["throughput_on"] / merged["avg_rmsd_aligned"].clip(lower=1e-6)
    os.makedirs(os.path.dirname(paths["combined_csv"]) or ".", exist_ok=True)
    merged.to_csv(paths["combined_csv"], index=False)

    summary = {
        "targets": int(merged["target"].nunique()) if "target" in merged.columns else 0,
        "speed_rebench_skipped": False,
        "avg_throughput_on": float(merged["throughput_on"].mean()) if "throughput_on" in merged.columns else None,
        "avg_speedup_on_vs_off": (
            float(merged["speedup_on_vs_off"].mean()) if "speedup_on_vs_off" in merged.columns else None
        ),
        "avg_rmsd_aligned_vs_external": (
            float(merged["avg_rmsd_aligned"].mean()) if "avg_rmsd_aligned" in merged.columns else None
        ),
        "avg_rmsd_vs_native_aligned": (
            float(merged["avg_rmsd_vs_native_aligned"].mean())
            if "avg_rmsd_vs_native_aligned" in merged.columns
            else None
        ),
    }
    return {"summary": summary}


def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    targets = _parse_targets(args.targets, seed=int(args.target_seed))
    paths = _default_paths(date_tag)

    if str(args.openmm_out_dir).strip():
        paths["openmm_dir"] = str(args.openmm_out_dir)
    if str(args.openmm_manifest).strip():
        paths["openmm_manifest"] = str(args.openmm_manifest)
    if str(args.openmm_json).strip():
        paths["openmm_json"] = str(args.openmm_json)
    if str(args.out_prefix).strip():
        prefix = str(args.out_prefix).strip()
        paths["stability_csv"] = f"{prefix}_long_stability_metrics.csv"
        paths["stability_summary_csv"] = f"{prefix}_long_stability_summary.csv"
        paths["stability_json"] = f"{prefix}_long_stability_report.json"
        paths["stage2_csv"] = f"{prefix}_stage2.csv"
        paths["stage2_json"] = f"{prefix}_stage2.json"
        paths["accuracy_csv"] = f"{prefix}_accuracy.csv"
        paths["accuracy_json"] = f"{prefix}_accuracy.json"
        paths["combined_csv"] = f"{prefix}_speed_accuracy.csv"
        paths["combined_json"] = f"{prefix}_speed_accuracy.json"
        paths["benchmark_csv"] = f"{prefix}_benchmark_raw.csv"

    if bool(args.force_rust):
        os.environ["FORCE_RUST_HIP"] = "1"
        os.environ.setdefault("RUST_HIP_USE_GPU_NBLIST_BUILDER", "1")
        os.environ.setdefault("NBLIST_AUTOGROW", "1")
        os.environ.setdefault("RUST_HIP_NBLIST_AUTOGROW", "1")

    openmm_payload: Optional[Dict[str, Any]] = None
    if not bool(args.skip_openmm_generate):
        openmm_payload = _run_openmm_generation(targets=targets, paths=paths, args=args)

    external_manifest_csv = str(args.external_manifest).strip() or paths["openmm_manifest"]
    use_tuned_stability = bool(str(getattr(args, "stability_profile_json", "")).strip())
    if use_tuned_stability:
        stability_payload = _run_long_stability_tuned(targets=targets, paths=paths, args=args)
    else:
        stability_payload = _run_long_stability(targets=targets, paths=paths, args=args)

    stability_summary = stability_payload.get("summary", {}) if isinstance(stability_payload, dict) else {}
    if bool(getattr(args, "enforce_long_stability_gate", False)):
        if not bool(stability_summary.get("gate_pass", False)):
            failed_targets = stability_summary.get("failed_targets", [])
            raise RuntimeError(f"long stability gate failed: failed_targets={failed_targets}")

    if bool(getattr(args, "skip_speed_rebench", False)):
        speed_payload = {
            "summary": {
                "skipped": True,
                "reason": "skip_speed_rebench_flag",
            }
        }
    else:
        speed_payload = _run_speed_rebench(targets=targets, paths=paths, args=args)
    accuracy_payload = _run_accuracy_rebench(
        targets=targets,
        external_manifest_csv=external_manifest_csv,
        paths=paths,
        args=args,
    )
    merged = _merge_speed_accuracy(paths=paths)

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "date_tag": date_tag,
        "targets_mode": str(args.targets),
        "targets": targets,
        "openmm_generated": bool(not args.skip_openmm_generate),
        "openmm_summary": (openmm_payload or {}).get("summary", {}),
        "long_stability_summary": stability_summary,
        "speed_summary": speed_payload.get("summary", {}),
        "accuracy_summary": accuracy_payload.get("summary", {}),
        "merged_summary": merged["summary"],
        "speed_runtime_config": {
            "use_ai_router": bool(getattr(args, "use_ai_router", True)),
            "ai_router_checkpoint": str(getattr(args, "ai_router_checkpoint", "")).strip() or None,
            "ai_router_checkpoint_strict": bool(getattr(args, "ai_router_checkpoint_strict", False)),
            "ai_runtime_mode": str(getattr(args, "ai_runtime_mode", "scripted")).strip().lower(),
            "speed_profile_preserve_runtime_mode": bool(
                getattr(args, "speed_profile_preserve_runtime_mode", True)
            ),
            "ai_disable_exploration": bool(getattr(args, "ai_disable_exploration", True)),
            "ai_use_hip_graph": bool(getattr(args, "ai_use_hip_graph", False)),
            "ai_graph_warmup_iters": int(getattr(args, "ai_graph_warmup_iters", 2)),
        },
        "files": paths,
        "external_manifest_csv": external_manifest_csv,
    }
    os.makedirs(os.path.dirname(paths["combined_json"]) or ".", exist_ok=True)
    with open(paths["combined_json"], "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "OpenMM CA-SC 2-bead generation + long-stability validation + non-cyclic speed-accuracy re-benchmark."
        )
    )
    p.add_argument("--targets", type=str, default="noncyclic", help="noncyclic|all|csv")
    p.add_argument("--target-seed", type=int, default=42)
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--out-prefix", type=str, default="")

    p.add_argument("--skip-openmm-generate", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--openmm-out-dir", type=str, default="")
    p.add_argument("--openmm-manifest", type=str, default="")
    p.add_argument("--openmm-json", type=str, default="")
    p.add_argument("--external-manifest", type=str, default="")
    p.add_argument("--openmm-platform", type=str, default="")
    p.add_argument("--openmm-steps", type=int, default=20000)
    p.add_argument("--openmm-save-stride", type=int, default=200)
    p.add_argument("--temperature-k", type=float, default=300.0)
    p.add_argument("--friction-ps", type=float, default=1.0)
    p.add_argument("--dt-ps", type=float, default=0.004)
    p.add_argument("--sigma-nm", type=float, default=0.38)
    p.add_argument("--epsilon-kj", type=float, default=0.50)
    p.add_argument("--bond-k-kj-nm2", type=float, default=2500.0)
    p.add_argument("--angle-k-kj-rad2", type=float, default=40.0)
    p.add_argument("--sidechain-bond-k-kj-nm2", type=float, default=2500.0)
    p.add_argument("--sidechain-angle-k-kj-rad2", type=float, default=35.0)
    p.add_argument("--sc-distance-nm", type=float, default=0.15)
    p.add_argument("--ca-mass-amu", type=float, default=100.0)
    p.add_argument("--sc-mass-amu", type=float, default=45.0)
    p.add_argument("--sc-sigma-scale", type=float, default=0.95)
    p.add_argument("--sc-epsilon-scale", type=float, default=0.90)
    p.add_argument("--exclude-local-sc-neighbors", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--save-ca-projection", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--cutoff-nm", type=float, default=1.2)
    p.add_argument("--minimize-iters", type=int, default=200)
    p.add_argument("--seed-base", type=int, default=1234)

    p.add_argument("--stability-runs", type=int, default=2)
    p.add_argument("--stability-steps", type=int, default=1000)
    p.add_argument("--stability-checkpoints", type=str, default="0,100,250,500,750,1000")
    p.add_argument("--stability-profile-json", type=str, default="")
    p.add_argument("--enforce-long-stability-gate", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--stability-noise", type=float, default=0.08)
    p.add_argument("--stability-dt", type=float, default=1e-5)
    p.add_argument("--stability-restraint-k", type=float, default=3.0)
    p.add_argument("--stability-force-clip", type=float, default=200.0)
    p.add_argument("--stability-aligned-rmsd-threshold", type=float, default=2.0)
    p.add_argument("--stability-energy-drift-threshold", type=float, default=0.30)
    p.add_argument("--stability-rg-delta-threshold", type=float, default=1.0)
    p.add_argument("--stability-max-clash-pairs", type=int, default=2)
    p.add_argument("--clash-cutoff-A", type=float, default=2.0)

    p.add_argument("--speed-steps", type=int, default=160)
    p.add_argument("--speed-runs", type=int, default=1)
    p.add_argument("--speed-warmup-steps", type=int, default=40)
    p.add_argument("--speed-benchmark-replicas", type=int, default=1)
    p.add_argument("--speed-eval-samples", type=int, default=2)
    p.add_argument("--speed-eval-noise", type=float, default=0.12)
    p.add_argument(
        "--speed-mode",
        type=str,
        default="balanced",
        choices=["balanced", "fast", "ultra", "turbo", "extreme", "warp", "titan", "max"],
    )
    p.add_argument("--speed-mode-replicas", type=int, default=0)
    p.add_argument("--speed-profile-max-replicas", type=int, default=0)
    p.add_argument(
        "--sample-gpu-metrics",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable per-run GPU metric sampling in speed benchmarking.",
    )
    p.add_argument(
        "--disable-stochastic-noise",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Force Langevin stochastic term off during benchmark.",
    )
    p.add_argument(
        "--precompute-stochastic-noise",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Precompute Langevin noise in fixed-size blocks.",
    )
    p.add_argument(
        "--precompute-stochastic-noise-block-steps",
        type=int,
        default=None,
        help="Noise precompute block size (steps).",
    )
    p.add_argument("--use-ai-router", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ai-router-checkpoint", type=str, default="")
    p.add_argument("--ai-router-checkpoint-strict", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument(
        "--ai-runtime-mode",
        type=str,
        default="eager",
        choices=["eager", "scripted", "compiled", "onnx"],
    )
    p.add_argument(
        "--speed-profile-preserve-runtime-mode",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Preserve requested --ai-runtime-mode even when speed profile preset has its own runtime mode.",
    )
    p.add_argument("--ai-disable-exploration", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ai-use-hip-graph", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ai-graph-warmup-iters", type=int, default=2)
    p.add_argument("--ai-interval", type=int, default=1)
    p.add_argument("--target-ai-interval-policy", type=str, default="speed_opt_v2")
    p.add_argument("--target-ai-drift-threshold-policy", type=str, default="")
    p.add_argument("--adaptive-ai-interval", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ai-interval-min", type=int, default=1)
    p.add_argument("--ai-interval-max", type=int, default=0)
    p.add_argument("--ai-downshift-factor", type=int, default=2)
    p.add_argument("--ai-drift-disp-threshold", type=float, default=0.25)
    p.add_argument("--ai-drift-check-stride", type=int, default=1)
    p.add_argument("--ai-stable-upshift-window", type=int, default=0)
    p.add_argument("--ai-interval-min-ratio", type=float, default=0.0)
    p.add_argument("--enable-physics-filter", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--physics-filter-mode", type=str, default="rollback", choices=["rollback", "hard_fail"])
    p.add_argument("--physics-filter-max-energy-drift", type=float, default=0.015)
    p.add_argument("--physics-filter-max-momentum-drift", type=float, default=0.015)
    p.add_argument("--physics-filter-min-interatomic-distance", type=float, default=0.0)
    p.add_argument("--with-fallback", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--force-rust", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--force-backend", type=str, default="auto", choices=["auto", "pytorch"])
    p.add_argument("--cutoff-A", type=float, default=12.0)
    p.add_argument("--skin-A", type=float, default=2.0)
    p.add_argument("--max-neighbors", type=int, default=100)
    p.add_argument("--max-atoms-per-cell", type=int, default=64)
    p.add_argument("--rebuild-stride", type=int, default=4)
    p.add_argument("--reference-cutoff-A", type=float, default=14.0)
    p.add_argument("--reference-max-neighbors", type=int, default=160)

    p.add_argument("--accuracy-steps", type=int, default=60)
    p.add_argument("--accuracy-runs", type=int, default=3)
    p.add_argument("--accuracy-noise", type=float, default=0.02)
    p.add_argument("--compare-bead", type=str, default="auto", choices=["auto", "ca", "all"])
    p.add_argument(
        "--accuracy-target-profile-json",
        type=str,
        default="",
        help=(
            "Optional per-target refinement profile JSON for accuracy rebench. "
            "When empty, reuses --stability-profile-json."
        ),
    )
    p.add_argument(
        "--skip-speed-rebench",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Skip stage2 speed re-benchmark and generate accuracy-only merged outputs.",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = run_pipeline(args)
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(2)
    print(json.dumps(payload["merged_summary"], indent=2, ensure_ascii=False))
    print(f"Wrote: {payload['files']['combined_json']}")
    print(f"Wrote: {payload['files']['combined_csv']}")


if __name__ == "__main__":
    main()
