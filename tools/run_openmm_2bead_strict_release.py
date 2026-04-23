#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Set

import pandas as pd

from benchmark.accuracy_bench import run_accuracy_report
from core.definitions import ResearchConstants
from tools.build_external_eval_packet import build_packet
from tools.classify_runs_files import main as classify_runs_files_main
from tools.generate_openmm_ca_md_references import generate_openmm_ca_md_references
from tools.publish_openmm_2bead_release import publish_release
from tools.prune_runs_files import prune_runs_files
from tools.run_target_tuned_long_stability import run_target_tuned_validation
from tools.stage2_full_report import run_report as run_stage2_report
from tools.validate_accuracy_gate import run_accuracy_gate
from tools.validate_md_reference_set import validate_md_reference_set
from train.target_scheduler import FoldBalancedTargetScheduler


def _ns(**kwargs: Any) -> argparse.Namespace:
    return SimpleNamespace(**kwargs)


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
    seen: Set[str] = set()
    uniq: List[str] = []
    for t in out:
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return uniq


def _csv_targets(targets: List[str]) -> str:
    return ",".join(targets)


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    _ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _default_out_prefix(date_tag: str) -> str:
    return f"runs/openmm_2bead_strict_{date_tag}"


def _default_openmm_paths(date_tag: str) -> Dict[str, str]:
    return {
        "openmm_dir": f"runs/real_md_openmm_2bead_{date_tag}",
        "openmm_manifest": f"runs/real_md_source_manifest_openmm_2bead_{date_tag}.csv",
        "openmm_manifest_json": f"runs/real_md_source_manifest_openmm_2bead_{date_tag}_summary.json",
    }


def _build_paths(out_prefix: str, date_tag: str, packet_version: str) -> Dict[str, str]:
    openmm_paths = _default_openmm_paths(date_tag)
    packet_tag = str(packet_version).strip().lower()
    return {
        **openmm_paths,
        "profile_subset_json": f"{out_prefix}_profile_subset.json",
        "md_validation_csv": f"{out_prefix}_md_reference_validation.csv",
        "md_validation_json": f"{out_prefix}_md_reference_validation.json",
        "long_stability_csv": f"{out_prefix}_long_stability_validation.csv",
        "long_stability_json": f"{out_prefix}_long_stability_validation.json",
        "long_stability_out_prefix": f"{out_prefix}_long_stability_target_tuned",
        "accuracy_gate_json": f"{out_prefix}_accuracy_gate.json",
        "accuracy_gate_csv": f"{out_prefix}_accuracy_gate.csv",
        "accuracy_gate_parity_prefix": f"{out_prefix}_accuracy_gate_parity",
        "accuracy_gate_stage2_prefix": f"{out_prefix}_accuracy_gate_stage2",
        "speed_stage2_csv": f"{out_prefix}_stage2.csv",
        "speed_stage2_json": f"{out_prefix}_stage2.json",
        "speed_benchmark_csv": f"{out_prefix}_benchmark_raw.csv",
        "accuracy_external_csv": f"{out_prefix}_accuracy_external.csv",
        "accuracy_external_json": f"{out_prefix}_accuracy_external.json",
        "packet_json": f"{out_prefix}_external_eval_packet_{packet_tag}.json",
        "summary_json": f"{out_prefix}_summary.json",
        "summary_csv": f"{out_prefix}_summary.csv",
        "summary_md": f"{out_prefix}_summary.md",
    }


def _load_profile(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid profile json: {path}")
    targets = payload.get("targets", {})
    if not isinstance(targets, dict) or len(targets) == 0:
        raise ValueError(f"invalid profile targets in: {path}")
    return payload


def _prepare_profile_for_targets(profile_json: str, targets: List[str], out_json: str) -> str:
    payload = _load_profile(profile_json)
    prof_targets = payload.get("targets", {})
    missing = [t for t in targets if t not in prof_targets]
    if missing:
        raise ValueError(f"profile missing targets: {missing}")

    if set(targets) == set(prof_targets.keys()) and len(targets) == len(prof_targets):
        return profile_json

    subset_targets = {t: prof_targets[t] for t in targets}
    subset_payload = {
        "meta": {
            "source_profile": os.path.abspath(profile_json),
            "created_at": dt.date.today().isoformat(),
            "description": "subset profile auto-generated for requested target scope",
        },
        "targets": subset_targets,
    }
    _write_json(out_json, subset_payload)
    return out_json


def _normalize_checkpoints(spec: str, steps: int) -> str:
    vals: List[int] = []
    for tok in str(spec).split(","):
        tok = tok.strip()
        if not tok:
            continue
        vals.append(int(tok))
    if not vals:
        vals = [0, int(steps)]
    vals = sorted(set(v for v in vals if v >= 0 and v <= int(steps)))
    if 0 not in vals:
        vals.insert(0, 0)
    if int(steps) not in vals:
        vals.append(int(steps))
    vals = sorted(set(vals))
    return ",".join(str(v) for v in vals)


def _copy_if_exists(src: str, dst_dir: str) -> None:
    if not src:
        return
    if not os.path.exists(src):
        return
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copy2(src, os.path.join(dst_dir, os.path.basename(src)))


def _move_to_archive_if_exists(src: str, archive_dir: str) -> Optional[str]:
    if not src:
        return None
    if not os.path.exists(src):
        return None
    os.makedirs(archive_dir, exist_ok=True)
    base = os.path.basename(src)
    dst = os.path.join(archive_dir, base)
    if os.path.abspath(src) == os.path.abspath(dst):
        return dst
    if os.path.exists(dst):
        stem, ext = os.path.splitext(base)
        idx = 2
        while os.path.exists(dst):
            dst = os.path.join(archive_dir, f"{stem}__{idx}{ext}")
            idx += 1
    shutil.move(src, dst)
    return dst


def _build_artifact_lists(paths: Dict[str, str], external_manifest: str) -> Dict[str, List[str]]:
    core = [
        paths["summary_json"],
        paths["summary_csv"],
        paths["summary_md"],
        paths["packet_json"],
        paths["accuracy_external_csv"],
        paths["accuracy_external_json"],
        paths["accuracy_gate_json"],
        paths["accuracy_gate_csv"],
        f"{paths['accuracy_gate_parity_prefix']}_target.csv",
        paths["speed_stage2_csv"],
        paths["speed_stage2_json"],
        paths["md_validation_csv"],
        paths["md_validation_json"],
        paths["long_stability_csv"],
        paths["long_stability_json"],
        external_manifest,
    ]
    intermediate = [
        paths["profile_subset_json"],
        paths["speed_benchmark_csv"],
        f"{paths['accuracy_gate_parity_prefix']}_sample.csv",
        f"{paths['accuracy_gate_parity_prefix']}_atom.csv",
        f"{paths['accuracy_gate_parity_prefix']}_pair.csv",
        f"{paths['accuracy_gate_parity_prefix']}.json",
        f"{paths['accuracy_gate_stage2_prefix']}.csv",
        f"{paths['accuracy_gate_stage2_prefix']}.json",
    ]
    return {"core": core, "intermediate": intermediate}


def _gate_check(
    gate_name: str,
    passed: bool,
    details: Dict[str, Any],
    failed_gates: List[str],
    failed_targets: Set[str],
    strict_fail_fast: bool,
) -> None:
    if passed:
        return

    failed_gates.append(gate_name)
    for t in details.get("failed_targets", []) or []:
        if str(t).strip():
            failed_targets.add(str(t).strip())

    if strict_fail_fast:
        reason = details.get("reason", "gate check failed")
        raise RuntimeError(f"{gate_name} failed: {reason}")


def _write_summary_md(path: str, payload: Dict[str, Any]) -> None:
    _ensure_parent(path)
    summary = payload.get("summary", {})
    gates = payload.get("gates", {})
    artifacts = payload.get("artifacts", {})
    artifact_policy = payload.get("artifact_policy", {})
    runtime_policy = payload.get("runtime_policy", {})
    prune_policy = payload.get("prune_policy", {})
    prune_summary = prune_policy.get("summary", {})
    publish_policy = payload.get("publish_policy", {})
    publish_summary = publish_policy.get("summary", {})
    published_files = publish_summary.get("copied_files", [])
    published_files_count = len(published_files) if isinstance(published_files, list) else 0

    lines: List[str] = []
    lines.append("# OpenMM 2-Bead Strict Release Summary")
    lines.append("")
    lines.append(f"- generated_at_local: `{payload.get('generated_at_local')}`")
    lines.append(f"- date_tag: `{payload.get('date_tag')}`")
    lines.append(f"- targets: `{summary.get('targets')}`")
    lines.append(f"- pass: `{summary.get('pass')}`")
    lines.append(f"- failed_gates: `{summary.get('failed_gates')}`")
    lines.append(f"- failed_targets: `{summary.get('failed_targets')}`")
    lines.append(f"- artifact_level: `{artifact_policy.get('level')}`")
    lines.append(f"- archived_intermediate_files: `{artifact_policy.get('archived_files_count')}`")
    lines.append(f"- prune_runs: `{prune_policy.get('enabled')}`")
    lines.append(f"- prune_keep_per_role: `{prune_policy.get('keep_per_role')}`")
    lines.append(f"- pruned_files: `{prune_summary.get('moved_files')}`")
    lines.append(f"- publish_release: `{publish_policy.get('enabled')}`")
    lines.append(f"- published_files: `{published_files_count}`")
    lines.append(f"- publish_release_tag: `{publish_summary.get('release_tag')}`")
    lines.append(f"- target_ai_interval_policy: `{runtime_policy.get('target_ai_interval_policy')}`")
    lines.append("")
    lines.append("## Gate Status")
    lines.append("")
    for gate_name in ["md_reference_validation", "long_stability", "accuracy_gate", "speed"]:
        info = gates.get(gate_name, {})
        lines.append(f"- `{gate_name}`: pass=`{info.get('pass')}`")
    lines.append("")
    lines.append("## Key Metrics")
    lines.append("")
    speed = gates.get("speed", {})
    accuracy_gate = gates.get("accuracy_gate", {})
    long_stability = gates.get("long_stability", {})
    lines.append(f"- avg_speedup_on_vs_off: `{speed.get('avg_speedup_on_vs_off')}`")
    lines.append(f"- avg_neighbor_jaccard: `{accuracy_gate.get('avg_neighbor_jaccard')}`")
    lines.append(f"- avg_e2e_rmse_raw: `{accuracy_gate.get('avg_e2e_rmse_raw')}`")
    lines.append(f"- long_stability_passed_targets: `{long_stability.get('passed_targets')}`")
    lines.append("")
    lines.append("## Artifacts")
    lines.append("")
    for k in sorted(artifacts.keys()):
        lines.append(f"- `{k}`: `{artifacts[k]}`")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- 신규 실행/제출 흐름은 `OpenMM CA-SC 2-bead` 기준으로 단일화됨.")
    lines.append("- 기존 `openmm_ca` 계열 산출물은 legacy 용도로만 보존됨.")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")


def run_release(args: argparse.Namespace) -> Dict[str, Any]:
    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    targets = _parse_targets(args.targets, seed=int(args.target_seed))
    if len(targets) == 0:
        raise ValueError("no targets selected")

    expected_target_count = int(args.expected_target_count)
    if expected_target_count <= 0:
        expected_target_count = len(targets)

    out_prefix = str(args.out_prefix).strip() or _default_out_prefix(date_tag)
    paths = _build_paths(
        out_prefix=out_prefix,
        date_tag=date_tag,
        packet_version=str(args.packet_version),
    )
    if str(args.openmm_out_dir).strip():
        paths["openmm_dir"] = str(args.openmm_out_dir)
    if str(args.openmm_manifest).strip():
        paths["openmm_manifest"] = str(args.openmm_manifest)
    if str(args.openmm_json).strip():
        paths["openmm_manifest_json"] = str(args.openmm_json)

    if bool(args.force_rust):
        os.environ["FORCE_RUST_HIP"] = "1"
        os.environ.setdefault("RUST_HIP_USE_GPU_NBLIST_BUILDER", "1")
        os.environ.setdefault("NBLIST_AUTOGROW", "1")
        os.environ.setdefault("RUST_HIP_NBLIST_AUTOGROW", "1")

    failed_gates: List[str] = []
    failed_targets: Set[str] = set()
    gates: Dict[str, Dict[str, Any]] = {}

    # 1) OpenMM 2-bead generation (or manifest reuse)
    openmm_payload: Dict[str, Any] = {}
    if not bool(args.skip_openmm_generate):
        gen_args = _ns(
            targets=_csv_targets(targets),
            out_dir=paths["openmm_dir"],
            out_manifest=paths["openmm_manifest"],
            out_json=paths["openmm_manifest_json"],
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
        openmm_payload = generate_openmm_ca_md_references(gen_args)
    else:
        openmm_payload = {"summary": {"skipped": True}}

    external_manifest = str(args.external_manifest).strip() or paths["openmm_manifest"]
    if not os.path.exists(external_manifest):
        raise FileNotFoundError(f"external manifest not found: {external_manifest}")

    # 2) MD reference validation gate
    md_validation_payload = validate_md_reference_set(
        manifest_csv=external_manifest,
        out_json=paths["md_validation_json"],
        out_csv=paths["md_validation_csv"],
        md_engine_regex=str(args.md_engine_regex),
        expected_target_count=int(expected_target_count),
        strict=False,
    )
    md_summary = md_validation_payload.get("summary", {})
    md_ready = bool(md_summary.get("ready", False))
    gates["md_reference_validation"] = {
        "pass": md_ready,
        "ready": md_ready,
        "failed_targets": md_summary.get("failed_targets", []),
        "reason": (
            None
            if md_ready
            else (
                f"md_ok_targets={md_summary.get('md_ok_targets')} expected={md_summary.get('expected_target_count')}"
            )
        ),
        "summary": md_summary,
    }
    _gate_check(
        gate_name="md_reference_validation",
        passed=md_ready,
        details=gates["md_reference_validation"],
        failed_gates=failed_gates,
        failed_targets=failed_targets,
        strict_fail_fast=bool(args.strict_fail_fast),
    )

    # 3) Target-tuned long-stability gate
    profile_to_use = _prepare_profile_for_targets(
        profile_json=str(args.profile_json),
        targets=targets,
        out_json=paths["profile_subset_json"],
    )
    long_stability_payload = run_target_tuned_validation(
        _ns(
            profile_json=profile_to_use,
            runs=int(args.stability_runs),
            steps=int(args.stability_steps),
            checkpoints=_normalize_checkpoints(
                spec=str(args.stability_checkpoints),
                steps=int(args.stability_steps),
            ),
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
            out_prefix=paths["long_stability_out_prefix"],
            out_csv=paths["long_stability_csv"],
            out_json=paths["long_stability_json"],
        )
    )
    ls_summary = long_stability_payload.get("summary", {})
    ls_failed = [str(x) for x in ls_summary.get("failed_targets", [])]
    ls_pass = bool(int(ls_summary.get("passed_targets", 0)) >= int(expected_target_count) and len(ls_failed) == 0)
    gates["long_stability"] = {
        "pass": ls_pass,
        "passed_targets": int(ls_summary.get("passed_targets", 0)),
        "targets": int(ls_summary.get("targets", 0)),
        "failed_targets": ls_failed,
        "avg_rmsd_aligned_mean": ls_summary.get("avg_rmsd_aligned_mean"),
        "avg_energy_drift_ratio_mean": ls_summary.get("avg_energy_drift_ratio_mean"),
        "reason": (
            None
            if ls_pass
            else f"passed_targets={ls_summary.get('passed_targets')} expected={expected_target_count}"
        ),
        "summary": ls_summary,
    }
    _gate_check(
        gate_name="long_stability",
        passed=ls_pass,
        details=gates["long_stability"],
        failed_gates=failed_gates,
        failed_targets=failed_targets,
        strict_fail_fast=bool(args.strict_fail_fast),
    )

    # 4) Accuracy gate (strict parity + overflow checks)
    accuracy_gate_payload = run_accuracy_gate(
        _ns(
            targets=_csv_targets(targets),
            seed=int(args.seed_base),
            samples=int(args.gate_samples),
            noise=float(args.gate_noise),
            steps=int(args.gate_steps),
            runs=int(args.gate_runs),
            warmup_steps=int(args.gate_warmup_steps),
            benchmark_replicas=int(args.gate_benchmark_replicas),
            speed_mode=str(getattr(args, "speed_mode", "balanced")).strip().lower(),
            speed_mode_replicas=int(getattr(args, "speed_mode_replicas", 0)),
            use_ai_router=bool(args.use_ai_router),
            ai_router_checkpoint=str(args.ai_router_checkpoint),
            ai_router_checkpoint_strict=bool(args.ai_router_checkpoint_strict),
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
            cutoff=float(args.cutoff_A),
            skin=float(args.skin_A),
            max_neighbors=int(args.max_neighbors),
            max_atoms_per_cell=int(args.max_atoms_per_cell),
            rebuild_stride=int(args.rebuild_stride),
            reference_cutoff=float(args.reference_cutoff_A),
            reference_max_neighbors=int(args.reference_max_neighbors),
            jaccard_threshold=float(args.gate_jaccard_threshold),
            e2e_rmse_threshold=float(args.gate_e2e_rmse_threshold),
            rel_rmse_threshold=float(args.gate_rel_rmse_threshold),
            speedup_threshold=float(args.gate_speedup_threshold),
            speedup_per_target_threshold=float(args.gate_speedup_per_target_threshold),
            strict_kernel_rmse_threshold=float(args.gate_strict_kernel_rmse_threshold),
            strict_nblist_effect_threshold=float(args.gate_strict_nblist_effect_threshold),
            strict_nblist_effect_rs_threshold=float(args.gate_strict_nblist_effect_rs_threshold),
            strict_mode=True,
            enforce_speed_gate=False,
            outlier_mode=str(args.outlier_mode),
            out_json=paths["accuracy_gate_json"],
            out_csv=paths["accuracy_gate_csv"],
            parity_prefix=paths["accuracy_gate_parity_prefix"],
            stage2_prefix=paths["accuracy_gate_stage2_prefix"],
            benchmark_csv=paths["speed_benchmark_csv"],
            disable_stochastic_noise=getattr(args, "disable_stochastic_noise", None),
            precompute_stochastic_noise=getattr(args, "precompute_stochastic_noise", None),
            precompute_stochastic_noise_block_steps=getattr(
                args,
                "precompute_stochastic_noise_block_steps",
                None,
            ),
            speed_profile_max_replicas=(
                int(getattr(args, "speed_profile_max_replicas", 0))
                if int(getattr(args, "speed_profile_max_replicas", 0)) > 0
                else None
            ),
            sample_gpu_metrics=getattr(args, "sample_gpu_metrics", None),
        )
    )
    ag_summary = accuracy_gate_payload.get("summary", {})
    ag_pass = bool(ag_summary.get("pass", False))
    parity_summary = accuracy_gate_payload.get("parity_summary", {})
    gates["accuracy_gate"] = {
        "pass": ag_pass,
        "failed_targets": ag_summary.get("failed_targets", []),
        "failed_metrics": ag_summary.get("failed_metrics", []),
        "avg_neighbor_jaccard": parity_summary.get("avg_neighbor_jaccard"),
        "avg_e2e_rmse_raw": parity_summary.get(
            "avg_e2e_rmse_raw",
            parity_summary.get("avg_force_rmse_raw"),
        ),
        "avg_e2e_rel_rmse_mean_clipped": parity_summary.get(
            "avg_e2e_rel_rmse_mean_clipped",
            parity_summary.get("avg_force_rel_rmse_clipped200"),
        ),
        "overflow_events_count": len(accuracy_gate_payload.get("overflow_events", [])),
        "reason": None if ag_pass else "accuracy gate summary.pass=false",
        "summary": ag_summary,
    }
    _gate_check(
        gate_name="accuracy_gate",
        passed=ag_pass,
        details=gates["accuracy_gate"],
        failed_gates=failed_gates,
        failed_targets=failed_targets,
        strict_fail_fast=bool(args.strict_fail_fast),
    )

    # 5) Speed gate (stage2)
    speed_payload = run_stage2_report(
        _ns(
            steps=int(args.speed_steps),
            runs=int(args.speed_runs),
            warmup_steps=int(args.speed_warmup_steps),
            benchmark_replicas=int(args.speed_benchmark_replicas),
            speed_mode=str(getattr(args, "speed_mode", "balanced")).strip().lower(),
            speed_mode_replicas=int(getattr(args, "speed_mode_replicas", 0)),
            disable_stochastic_noise=getattr(args, "disable_stochastic_noise", None),
            precompute_stochastic_noise=getattr(args, "precompute_stochastic_noise", None),
            precompute_stochastic_noise_block_steps=getattr(
                args,
                "precompute_stochastic_noise_block_steps",
                None,
            ),
            speed_profile_max_replicas=(
                int(getattr(args, "speed_profile_max_replicas", 0))
                if int(getattr(args, "speed_profile_max_replicas", 0)) > 0
                else None
            ),
            sample_gpu_metrics=getattr(args, "sample_gpu_metrics", None),
            use_ai_router=bool(args.use_ai_router),
            ai_router_checkpoint=str(args.ai_router_checkpoint),
            ai_router_checkpoint_strict=bool(args.ai_router_checkpoint_strict),
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
            track_clip_hits=bool(args.speed_track_clip_hits),
            profile_components=bool(args.speed_profile_components),
            reference_cutoff=float(args.reference_cutoff_A),
            reference_max_neighbors=int(args.reference_max_neighbors),
            cutoff=float(args.cutoff_A),
            skin=float(args.skin_A),
            max_neighbors=int(args.max_neighbors),
            max_atoms_per_cell=int(args.max_atoms_per_cell),
            rebuild_stride=int(args.rebuild_stride),
            with_fallback=bool(args.with_fallback),
            force_rust=bool(args.force_rust),
            targets=_csv_targets(targets),
            report_csv=paths["speed_stage2_csv"],
            report_json=paths["speed_stage2_json"],
            benchmark_csv=paths["speed_benchmark_csv"],
        )
    )
    speed_summary = speed_payload.get("summary", {})
    speed_rows = speed_payload.get("rows", []) or []
    avg_speedup = float(speed_summary.get("avg_speedup_on_vs_off", 0.0))
    speed_gate_enforced = bool(int(expected_target_count) > 1)
    speed_pass = True
    if speed_gate_enforced:
        speed_pass = bool(avg_speedup >= float(args.gate_speedup_threshold))
    speed_failed_targets = []
    if speed_gate_enforced and float(args.gate_speedup_per_target_threshold) > 0.0:
        for row in speed_rows:
            t = str(row.get("target", "")).strip()
            val = float(row.get("speedup_on_vs_off", 0.0))
            if t and val < float(args.gate_speedup_per_target_threshold):
                speed_failed_targets.append(t)
                speed_pass = False
    gates["speed"] = {
        "pass": speed_pass,
        "enforced": speed_gate_enforced,
        "avg_speedup_on_vs_off": avg_speedup,
        "threshold": float(args.gate_speedup_threshold),
        "failed_targets": sorted(set(speed_failed_targets)),
        "reason": (
            None
            if speed_pass
            else f"avg_speedup_on_vs_off={avg_speedup}"
        )
        if speed_gate_enforced
        else "skipped_for_single_target_scope",
        "summary": speed_summary,
    }
    _gate_check(
        gate_name="speed",
        passed=speed_pass,
        details=gates["speed"],
        failed_gates=failed_gates,
        failed_targets=failed_targets,
        strict_fail_fast=bool(args.strict_fail_fast),
    )

    # 6) External accuracy report on OpenMM 2-bead references
    accuracy_use_ai_router = bool(args.accuracy_use_ai_router or args.use_ai_router)
    accuracy_external_payload = run_accuracy_report(
        _ns(
            targets=_csv_targets(targets),
            steps=int(args.accuracy_steps),
            runs=int(args.accuracy_runs),
            noise=float(args.accuracy_noise),
            seed_base=int(args.seed_base),
            reference_source="external",
            external_manifest=external_manifest,
            external_key=None,
            external_frame=-1,
            external_summary_csv=None,
            compare_bead=str(args.compare_bead),
            simulation_engine=str(args.accuracy_simulation_engine),
            use_ai_router=bool(accuracy_use_ai_router),
            ai_interval=int(args.accuracy_ai_interval),
            benchmark_warmup_steps=int(args.accuracy_benchmark_warmup_steps),
            benchmark_replicas=int(args.accuracy_benchmark_replicas),
            benchmark_force_backend=str(args.accuracy_benchmark_force_backend),
            benchmark_neighbor_settings=str(args.accuracy_benchmark_neighbor_settings),
            benchmark_force_clip=float(args.accuracy_benchmark_force_clip),
            benchmark_ai_correction_clip=float(args.accuracy_benchmark_ai_correction_clip),
            ai_router_checkpoint=str(args.ai_router_checkpoint),
            ai_router_checkpoint_strict=bool(args.ai_router_checkpoint_strict),
            ai_collect_aux=bool(args.accuracy_ai_collect_aux),
            target_profile_json=profile_to_use,
            out_csv=paths["accuracy_external_csv"],
            out_json=paths["accuracy_external_json"],
        )
    )

    # 7) External packet build (JSON)
    packet_args = _ns(
        packet_version=str(args.packet_version),
        gate_json=paths["accuracy_gate_json"],
        parity_target_csv=f"{paths['accuracy_gate_parity_prefix']}_target.csv",
        stage2_csv=paths["speed_stage2_csv"],
        fidelity_csv=str(args.fidelity_csv),
        feature_csv=str(args.feature_csv),
        q_low=float(args.q_low),
        q_high=float(args.q_high),
        min_obs=int(args.min_obs),
        out_json=paths["packet_json"],
        accuracy_external_csv=paths["accuracy_external_csv"],
        quality_curation_csv=str(args.quality_curation_csv),
        strict_optional_sources=False,
    )
    packet_payload = build_packet(packet_args)
    _write_json(paths["packet_json"], packet_payload)

    # 8) Unified summary (JSON/CSV/MD)
    overall_pass = len(failed_gates) == 0
    submission_dir = os.path.join(str(args.submission_dir), f"openmm_2bead_strict_{date_tag}")
    summary_payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "date_tag": date_tag,
        "targets_mode": str(args.targets),
        "targets": targets,
        "runtime_policy": {
            "target_ai_interval_policy": str(args.target_ai_interval_policy),
            "target_ai_drift_threshold_policy": str(args.target_ai_drift_threshold_policy),
            "adaptive_ai_interval": bool(args.adaptive_ai_interval),
            "ai_interval": int(args.ai_interval),
            "speed_mode": str(getattr(args, "speed_mode", "balanced")).strip().lower(),
            "speed_mode_replicas": int(getattr(args, "speed_mode_replicas", 0)),
            "speed_profile_max_replicas": int(getattr(args, "speed_profile_max_replicas", 0)),
            "speed_benchmark_replicas": int(getattr(args, "speed_benchmark_replicas", 0)),
            "disable_stochastic_noise": getattr(args, "disable_stochastic_noise", None),
            "precompute_stochastic_noise": getattr(args, "precompute_stochastic_noise", None),
            "sample_gpu_metrics": getattr(args, "sample_gpu_metrics", None),
            "precompute_stochastic_noise_block_steps": getattr(
                args,
                "precompute_stochastic_noise_block_steps",
                None,
            ),
        },
        "summary": {
            "pass": bool(overall_pass),
            "targets": int(len(targets)),
            "failed_gates": failed_gates,
            "failed_targets": sorted(failed_targets),
        },
        "gates": {
            "md_reference_validation": gates.get("md_reference_validation", {}),
            "long_stability": gates.get("long_stability", {}),
            "accuracy_gate": gates.get("accuracy_gate", {}),
            "speed": gates.get("speed", {}),
        },
        "openmm_summary": openmm_payload.get("summary", {}),
        "accuracy_external_summary": accuracy_external_payload.get("summary", {}),
        "packet_summary": {
            "packet_version": packet_payload.get("meta", {}).get("packet_version"),
            "gate_pass": packet_payload.get("global_summary", {}).get("gate_pass"),
            "avg_speedup_on_vs_off": packet_payload.get("global_summary", {})
            .get("speed", {})
            .get("avg_speedup_on_vs_off"),
        },
        "artifact_policy": {
            "level": str(args.artifact_level),
            "archive_intermediate": bool(args.archive_intermediate),
            "archived_files_count": 0,
            "archive_dir": "",
            "archived_files": [],
        },
        "prune_policy": {
            "enabled": bool(args.prune_runs),
            "keep_per_role": int(args.prune_keep_per_role),
            "summary": {},
        },
        "publish_policy": {
            "enabled": bool(args.publish_release),
            "summary": {},
        },
        "artifacts": {
            "external_manifest_csv": external_manifest,
            "submission_dir": submission_dir,
            **paths,
        },
    }

    _write_json(paths["summary_json"], summary_payload)
    summary_row = {
        "date_tag": date_tag,
        "targets": len(targets),
        "pass": bool(overall_pass),
        "failed_gates": "|".join(failed_gates),
        "failed_targets": "|".join(sorted(failed_targets)),
        "artifact_level": str(args.artifact_level),
        "avg_neighbor_jaccard": gates.get("accuracy_gate", {}).get("avg_neighbor_jaccard"),
        "avg_e2e_rmse_raw": gates.get("accuracy_gate", {}).get("avg_e2e_rmse_raw"),
        "avg_speedup_on_vs_off": gates.get("speed", {}).get("avg_speedup_on_vs_off"),
        "avg_rmsd_aligned_vs_external": accuracy_external_payload.get("summary", {}).get("avg_rmsd_aligned"),
    }
    _ensure_parent(paths["summary_csv"])
    pd.DataFrame([summary_row]).to_csv(paths["summary_csv"], index=False)
    _write_summary_md(paths["summary_md"], summary_payload)

    # 9) External submission folder copy
    artifact_groups = _build_artifact_lists(paths=paths, external_manifest=external_manifest)
    artifact_groups["intermediate"].extend(
        sorted(glob.glob(f"{paths['long_stability_out_prefix']}_*"))
    )
    artifact_level = str(args.artifact_level).strip().lower()
    artifacts_to_copy = list(artifact_groups["core"])
    if artifact_level == "full":
        artifacts_to_copy.extend(artifact_groups["intermediate"])
    for fp in artifacts_to_copy:
        _copy_if_exists(fp, submission_dir)

    archived_files: List[str] = []
    if artifact_level == "minimal" and bool(args.archive_intermediate):
        archive_dir = os.path.join(
            "runs",
            "_archive_intermediate",
            date_tag,
            os.path.basename(out_prefix),
        )
        for fp in artifact_groups["intermediate"]:
            moved = _move_to_archive_if_exists(fp, archive_dir)
            if moved:
                archived_files.append(moved)
        summary_payload["artifact_policy"]["archive_dir"] = archive_dir
    summary_payload["artifact_policy"]["archived_files_count"] = int(len(archived_files))
    summary_payload["artifact_policy"]["archived_files"] = archived_files

    # Rewrite summary after archive step so policy counters are accurate.
    _write_json(paths["summary_json"], summary_payload)
    _write_summary_md(paths["summary_md"], summary_payload)

    # 10) Refresh run index/category snapshots
    classify_runs_files_main()
    if bool(args.prune_runs):
        prune_summary = prune_runs_files(
            runs_dir="runs",
            keep_per_role=int(args.prune_keep_per_role),
            protect_prefixes=[os.path.basename(out_prefix), "LATEST", "INDEX"],
            dry_run=False,
        )
        summary_payload["prune_policy"]["summary"] = prune_summary
        _write_json(paths["summary_json"], summary_payload)
        _write_summary_md(paths["summary_md"], summary_payload)
        classify_runs_files_main()

    if bool(args.publish_release):
        publish_summary = publish_release(
            summary_json=paths["summary_json"],
            submission_root=str(args.submission_dir),
            release_tag=(str(args.publish_release_tag).strip() or os.path.basename(out_prefix)),
            clean_target_dir=bool(args.publish_clean_target_dir),
            archive_date_dir_files=bool(args.publish_archive_date_dir_files),
            archive_root=str(args.publish_archive_root),
            dry_run=False,
        )
        summary_payload["publish_policy"]["summary"] = publish_summary
        _write_json(paths["summary_json"], summary_payload)
        _write_summary_md(paths["summary_md"], summary_payload)

    if not overall_pass and bool(args.strict_fail_fast):
        raise RuntimeError(f"strict release failed: gates={failed_gates}, targets={sorted(failed_targets)}")
    return summary_payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "OpenMM CA-SC 2-bead strict unified re-benchmark: generation -> md validation -> "
            "target-tuned long-stability -> strict accuracy gate -> speed gate -> external packet -> summary."
        )
    )

    # Requested public interface
    p.add_argument("--targets", type=str, default="noncyclic")
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument(
        "--profile-json",
        type=str,
        default="config/long_stability_target_tuned_all10_2026-02-15.json",
    )
    p.add_argument("--skip-openmm-generate", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--external-manifest", type=str, default="")
    p.add_argument("--strict-fail-fast", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--gate-speedup-threshold", type=float, default=12.0)
    p.add_argument("--gate-jaccard-threshold", type=float, default=1.0)
    p.add_argument("--gate-e2e-rmse-threshold", type=float, default=0.35)
    p.add_argument("--gate-rel-rmse-threshold", type=float, default=1e-5)
    p.add_argument("--submission-dir", type=str, default="runs/external_eval_submission")
    p.add_argument("--artifact-level", type=str, default="minimal", choices=["minimal", "full"])
    p.add_argument("--archive-intermediate", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--prune-runs", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--prune-keep-per-role", type=int, default=2)
    p.add_argument("--publish-release", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--publish-release-tag", type=str, default="")
    p.add_argument("--publish-clean-target-dir", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--publish-archive-date-dir-files", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--publish-archive-root", type=str, default="runs/external_eval_submission/_archive")
    p.add_argument("--out-prefix", type=str, default="")

    # General runtime options
    p.add_argument("--target-seed", type=int, default=42)
    p.add_argument("--seed-base", type=int, default=1234)
    p.add_argument("--expected-target-count", type=int, default=0)
    p.add_argument("--force-rust", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--force-backend", type=str, default="auto", choices=["auto", "pytorch"])
    p.add_argument("--md-engine-regex", type=str, default=r"(openmm|amber|gromacs)")

    # OpenMM generation
    p.add_argument("--openmm-out-dir", type=str, default="")
    p.add_argument("--openmm-manifest", type=str, default="")
    p.add_argument("--openmm-json", type=str, default="")
    p.add_argument("--openmm-platform", type=str, default="")
    p.add_argument("--openmm-steps", type=int, default=10000)
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

    # Shared neighbor settings
    p.add_argument("--cutoff-A", type=float, default=12.0)
    p.add_argument("--skin-A", type=float, default=2.0)
    p.add_argument("--max-neighbors", type=int, default=100)
    p.add_argument("--max-atoms-per-cell", type=int, default=64)
    p.add_argument("--rebuild-stride", type=int, default=4)
    p.add_argument("--reference-cutoff-A", type=float, default=14.0)
    p.add_argument("--reference-max-neighbors", type=int, default=160)

    # Long stability
    p.add_argument("--stability-runs", type=int, default=2)
    p.add_argument("--stability-steps", type=int, default=1200)
    p.add_argument("--stability-checkpoints", type=str, default="0,100,300,600,900,1200")
    p.add_argument("--stability-noise", type=float, default=0.08)
    p.add_argument("--stability-aligned-rmsd-threshold", type=float, default=2.0)
    p.add_argument("--stability-energy-drift-threshold", type=float, default=0.30)
    p.add_argument("--stability-rg-delta-threshold", type=float, default=1.0)
    p.add_argument("--stability-max-clash-pairs", type=int, default=2)
    p.add_argument("--clash-cutoff-A", type=float, default=2.0)

    # Accuracy gate
    p.add_argument("--gate-samples", type=int, default=8)
    p.add_argument("--gate-noise", type=float, default=0.08)
    p.add_argument("--gate-steps", type=int, default=60)
    p.add_argument("--gate-runs", type=int, default=1)
    p.add_argument("--gate-warmup-steps", type=int, default=40)
    p.add_argument("--gate-benchmark-replicas", type=int, default=1)
    p.add_argument("--gate-speedup-per-target-threshold", type=float, default=0.0)
    p.add_argument("--gate-strict-kernel-rmse-threshold", type=float, default=0.45)
    p.add_argument("--gate-strict-nblist-effect-threshold", type=float, default=0.12)
    p.add_argument("--gate-strict-nblist-effect-rs-threshold", type=float, default=1e-8)
    p.add_argument("--outlier-mode", type=str, default="shared_rs_nblist")

    # Stage2 speed gate
    p.add_argument("--speed-steps", type=int, default=160)
    p.add_argument("--speed-runs", type=int, default=1)
    p.add_argument("--speed-warmup-steps", type=int, default=40)
    p.add_argument("--speed-benchmark-replicas", type=int, default=8)
    p.add_argument(
        "--speed-mode",
        type=str,
        default="balanced",
        choices=["balanced", "fast", "ultra", "turbo", "extreme", "warp", "titan", "max"],
    )
    p.add_argument("--speed-mode-replicas", type=int, default=0)
    p.add_argument(
        "--speed-profile-max-replicas",
        type=int,
        default=0,
        help="Optional max replicas cap applied to speed profile.",
    )
    p.add_argument("--speed-eval-samples", type=int, default=2)
    p.add_argument("--speed-eval-noise", type=float, default=0.08)
    p.add_argument("--speed-track-clip-hits", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--speed-profile-components", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument(
        "--sample-gpu-metrics",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable per-run GPU metric sampling in speed benchmarking.",
    )
    p.add_argument("--with-fallback", action=argparse.BooleanOptionalAction, default=True)

    # Shared AI/runtime knobs
    p.add_argument("--use-ai-router", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ai-router-checkpoint", type=str, default="")
    p.add_argument("--ai-router-checkpoint-strict", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--ai-interval", type=int, default=1)
    p.add_argument(
        "--target-ai-interval-policy",
        type=str,
        default="speed_opt_v2",
    )
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
    p.add_argument(
        "--disable-stochastic-noise",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Force Langevin stochastic term off during internal benchmarks.",
    )
    p.add_argument(
        "--precompute-stochastic-noise",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Precompute Langevin noise in fixed-size blocks during internal benchmarks.",
    )
    p.add_argument(
        "--precompute-stochastic-noise-block-steps",
        type=int,
        default=None,
        help="Noise precompute block size (steps) for internal benchmarks.",
    )

    # External accuracy report
    p.add_argument("--accuracy-steps", type=int, default=60)
    p.add_argument("--accuracy-runs", type=int, default=3)
    p.add_argument("--accuracy-noise", type=float, default=0.02)
    p.add_argument("--compare-bead", type=str, default="auto", choices=["auto", "ca", "all"])
    p.add_argument(
        "--accuracy-simulation-engine",
        type=str,
        default="refinement",
        choices=["refinement", "benchmark"],
    )
    p.add_argument("--accuracy-use-ai-router", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--accuracy-ai-interval", type=int, default=1)
    p.add_argument("--accuracy-benchmark-warmup-steps", type=int, default=40)
    p.add_argument("--accuracy-benchmark-replicas", type=int, default=1)
    p.add_argument(
        "--accuracy-benchmark-force-backend",
        type=str,
        default="auto",
        choices=["auto", "pytorch"],
    )
    p.add_argument(
        "--accuracy-benchmark-neighbor-settings",
        type=str,
        default="grid_spacing=12,cutoff=12,skin=2,max_neighbors=100,rebuild_stride=4,max_atoms_per_cell=64",
    )
    p.add_argument("--accuracy-benchmark-force-clip", type=float, default=200.0)
    p.add_argument("--accuracy-benchmark-ai-correction-clip", type=float, default=100.0)
    p.add_argument("--accuracy-ai-collect-aux", action=argparse.BooleanOptionalAction, default=False)

    # Packet options
    p.add_argument("--packet-version", type=str, default="v2", choices=["v1", "v2", "v3"])
    p.add_argument("--fidelity-csv", type=str, default="runs/physics_fidelity_report.csv")
    p.add_argument("--feature-csv", type=str, default="runs/feature_matrix_per_target.csv")
    p.add_argument("--quality-curation-csv", type=str, default="runs/structure_quality_curated.csv")
    p.add_argument("--q-low", type=float, default=0.10)
    p.add_argument("--q-high", type=float, default=0.90)
    p.add_argument("--min-obs", type=int, default=64)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = run_release(args)
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(2)

    print(json.dumps(payload.get("summary", {}), indent=2, ensure_ascii=False))
    print(f"Wrote: {payload['artifacts']['summary_json']}")
    print(f"Wrote: {payload['artifacts']['summary_csv']}")
    print(f"Wrote: {payload['artifacts']['summary_md']}")


if __name__ == "__main__":
    main()
