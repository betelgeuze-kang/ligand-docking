#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASE_PROFILE_JSON = "config/ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k.json"
DEFAULT_SPEC_JSON = "runs/gpcr_residual_prototype_spec_core_decoy_intrusion_v1_current.json"
DEFAULT_OUT_DIR = "runs/gpcr_scaleup_100k_core_decoy_intrusion_candidate_current"
DEFAULT_TAG_SUFFIX = "core-decoy-intrusion100k"
INTRUSION_VARIANT = "gpcr_core_decoy_intrusion_v1"
LINEAR_RESCORE_VARIANT = "gpcr_core_linear_rescore_v1"
MISMATCH_CONTACT_RESCORE_VARIANT = "gpcr_core_mismatch_contact_rescore_v1"
STRUCTURE_SUPPORT_RESCORE_VARIANT = "gpcr_core_structure_support_rescore_v1"
PHARMACOPHORE_VARIANT = "gpcr_adrb2_beta_blocker_pharmacophore_v1"
SUPPORTED_VARIANTS = {
    INTRUSION_VARIANT,
    LINEAR_RESCORE_VARIANT,
    MISMATCH_CONTACT_RESCORE_VARIANT,
    STRUCTURE_SUPPORT_RESCORE_VARIANT,
    PHARMACOPHORE_VARIANT,
}
SUPPORTED_MODES = {"shadow_only", "apply"}
SUPPORTED_SCORE_REFERENCE_SCALING_MODES = {"run_local", "fixed_family_reference"}
VARIANT_DEFAULT_SPEC_JSON = {
    INTRUSION_VARIANT: DEFAULT_SPEC_JSON,
    LINEAR_RESCORE_VARIANT: "runs/gpcr_residual_prototype_spec_core_linear_rescore_v1_current.json",
    MISMATCH_CONTACT_RESCORE_VARIANT: "runs/gpcr_residual_prototype_spec_core_mismatch_contact_rescore_v1_current.json",
    STRUCTURE_SUPPORT_RESCORE_VARIANT: "runs/gpcr_residual_prototype_spec_core_structure_support_rescore_v1_current.json",
    PHARMACOPHORE_VARIANT: "runs/gpcr_residual_prototype_spec_adrb2_beta_blocker_pharmacophore_v1_current.json",
}
VARIANT_CANDIDATE_KIND = {
    INTRUSION_VARIANT: "gpcr_core_decoy_intrusion_100k",
    LINEAR_RESCORE_VARIANT: "gpcr_core_linear_rescore_100k",
    MISMATCH_CONTACT_RESCORE_VARIANT: "gpcr_core_mismatch_contact_rescore_100k",
    STRUCTURE_SUPPORT_RESCORE_VARIANT: "gpcr_core_structure_support_rescore_100k",
    PHARMACOPHORE_VARIANT: "gpcr_adrb2_beta_blocker_pharmacophore_100k",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel_or_abs(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _default_spec_sidecar(path: Path, suffix: str) -> Path:
    if path.suffix == ".json":
        return path.with_suffix(suffix)
    return path.parent / f"{path.name}{suffix}"


def ensure_residual_spec(spec_json: Path, *, variant: str = INTRUSION_VARIANT) -> None:
    if spec_json.exists():
        return
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "build_gpcr_residual_prototype_spec.py"),
        "--variant",
        variant,
        "--out-json",
        str(spec_json),
        "--out-csv",
        str(_default_spec_sidecar(spec_json, ".csv")),
        "--out-md",
        str(_default_spec_sidecar(spec_json, ".md")),
    ]
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def _validate_residual_spec(spec: dict[str, Any], spec_json: Path, *, variant: str = INTRUSION_VARIANT) -> None:
    summary = spec.get("summary")
    prototype = spec.get("prototype")
    tuning = prototype.get("tuning") if isinstance(prototype, dict) else {}
    variants = {
        str(summary.get("prototype_variant", "")).strip() if isinstance(summary, dict) else "",
        str(tuning.get("variant", "")).strip() if isinstance(tuning, dict) else "",
    }
    if variant not in variants:
        raise ValueError(f"{spec_json} is not a {variant} residual prototype spec")


def _structure_support_gate_from_spec(spec: dict[str, Any]) -> dict[str, Any]:
    prototype = spec.get("prototype")
    constraints = prototype.get("constraints") if isinstance(prototype, dict) else {}
    raw_gate = constraints.get("structure_support_gate") if isinstance(constraints, dict) else {}
    if not isinstance(raw_gate, dict) or not raw_gate.get("enabled"):
        return {}
    return {
        "enabled": True,
        "required_before_claim": bool(raw_gate.get("required_before_claim", True)),
        "full_100k_gate_green": bool(raw_gate.get("full_100k_gate_green", False)),
    }


def _candidate_profile(
    base_profile: dict[str, Any],
    *,
    residual_spec_json: Path,
    residual_spec: dict[str, Any] | None = None,
    variant: str,
    mode: str,
    heavy_artifacts_root: str = "",
    traj_writer_mode: str = "",
    traj_writer_workers: int | None = None,
    traj_writer_max_pending: int | None = None,
    traj_job_batch_size: int | None = None,
    traj_job_batch_autotune_candidates: str = "",
    traj_job_batch_autotune_frames: int | None = None,
    traj_engine_cache_max_entries: int | None = None,
    traj_prod_early_stop_enabled: bool | None = None,
    score_reference_scaling_mode: str = "run_local",
    score_reference_stats_json: Path | None = None,
) -> dict[str, Any]:
    profile = dict(base_profile)
    target_specific = variant == PHARMACOPHORE_VARIANT
    candidate_label = variant.replace("gpcr_core_", "GPCR core ").replace("_", " ")
    mode_label = "guarded apply" if mode == "apply" else "shadow"
    profile["residual_prototype_enabled"] = True
    profile["residual_prototype_mode"] = mode
    profile["residual_prototype_family"] = "gpcr"
    profile["residual_prototype_apply_stage"] = "stage5_ranking"
    profile["residual_prototype_status"] = "shadow_runtime_ready"
    profile["residual_prototype_runtime_hook_ready"] = True
    profile["residual_prototype_spec_json"] = str(residual_spec_json.resolve())
    profile["residual_prototype_candidate"] = variant
    active_score = "binding_score_composite_v7_residual_active" if mode == "apply" else "binding_score_composite_v7"
    profile["ranking_score_col"] = active_score
    profile["ranking_probability_score_col"] = active_score
    profile["router_promotion_allowed"] = False
    profile["target_specific_candidate"] = bool(target_specific)
    profile["claim_safe_assertion_allowed"] = False
    profile["broad_gpcr_claim_allowed"] = False
    structure_support_gate = _structure_support_gate_from_spec(residual_spec or {})
    if structure_support_gate:
        profile["evidence_role"] = "reject_shadow_evidence"
        profile["structure_support_gate"] = structure_support_gate
        profile["claim_text_locked_until_full_100k_gate_green"] = not bool(
            structure_support_gate.get("full_100k_gate_green")
        )
    if str(heavy_artifacts_root).strip():
        profile["heavy_artifacts_root"] = str(heavy_artifacts_root).strip()
        profile["auto_heavy_artifacts_root"] = False
    if str(traj_writer_mode).strip():
        profile["traj_writer_mode"] = str(traj_writer_mode).strip()
    if traj_writer_workers is not None:
        profile["traj_writer_workers"] = int(traj_writer_workers)
    if traj_writer_max_pending is not None:
        profile["traj_writer_max_pending"] = int(traj_writer_max_pending)
    if traj_job_batch_size is not None:
        profile["traj_job_batch_size"] = int(traj_job_batch_size)
    if str(traj_job_batch_autotune_candidates).strip():
        profile["traj_job_batch_autotune_candidates"] = str(traj_job_batch_autotune_candidates).strip()
    if traj_job_batch_autotune_frames is not None:
        profile["traj_job_batch_autotune_frames"] = int(traj_job_batch_autotune_frames)
    if traj_engine_cache_max_entries is not None:
        profile["traj_engine_cache_max_entries"] = int(traj_engine_cache_max_entries)
    if traj_prod_early_stop_enabled is not None:
        profile["traj_prod_early_stop_enabled"] = bool(traj_prod_early_stop_enabled)
    score_reference_scaling_mode = str(score_reference_scaling_mode or "run_local").strip()
    if score_reference_scaling_mode != "run_local":
        profile["score_reference_scaling_mode"] = score_reference_scaling_mode
        profile["score_reference_stats_json"] = str(score_reference_stats_json.resolve()) if score_reference_stats_json else ""
        profile["score_reference_scaling_claim_allowed"] = False
    if target_specific:
        profile["residual_prototype_notes"] = (
            f"{mode} target-specific ADRB2 beta-blocker pharmacophore candidate. "
            "Residual telemetry must not be used for router promotion or general GPCR family claims."
        )
    else:
        profile["residual_prototype_notes"] = (
            f"{mode_label} {candidate_label} 100k comparison candidate. Residual telemetry is generated for guarded "
            "safety review only and is not a claim-safe assertion."
        )
    return profile


def _candidate_set_spec(
    *,
    profile_json: Path,
    residual_spec_json: Path,
    residual_spec: dict[str, Any] | None = None,
    tag_suffix: str,
    variant: str,
    mode: str,
    set_id: str,
    set_title: str,
    task_id: str,
    score_reference_scaling_mode: str = "run_local",
    score_reference_stats_json: Path | None = None,
) -> dict[str, Any]:
    candidate_kind = VARIANT_CANDIDATE_KIND[variant]
    comparison_candidate_role = "guarded_apply_candidate" if mode == "apply" else "shadow_candidate"
    governance = {
        "comparison_kind": f"{candidate_kind}_candidate",
        "prototype_spec_json": str(residual_spec_json.resolve()),
        "prototype_variant": variant,
        "prototype_mode": mode,
        "family_scope": ["gpcr"],
        "router_promotion_allowed": False,
        "target_specific_candidate": variant == PHARMACOPHORE_VARIANT,
        "apply_mode_claim_allowed": False,
        "claim_safe_assertion_allowed": False,
        "broad_gpcr_claim_allowed": False,
        "comparison_candidate_role": comparison_candidate_role,
    }
    structure_support_gate = _structure_support_gate_from_spec(residual_spec or {})
    if structure_support_gate:
        governance["evidence_role"] = "reject_shadow_evidence"
        governance["structure_support_gate"] = structure_support_gate
        governance["claim_text_locked_until_full_100k_gate_green"] = not bool(
            structure_support_gate.get("full_100k_gate_green")
        )
    score_reference_scaling_mode = str(score_reference_scaling_mode or "run_local").strip()
    if score_reference_scaling_mode != "run_local":
        governance["score_reference_scaling"] = {
            "mode": score_reference_scaling_mode,
            "stats_json": str(score_reference_stats_json.resolve()) if score_reference_stats_json else "",
            "claim_safe_assertion_allowed": False,
            "comparison_only": True,
            "eval_role_non_use_required": True,
        }
    return {
        "protocol_id": f"{candidate_kind}_{tag_suffix}",
        "protocol_title": "GPCR 100k Residual Candidate",
        "protocol_version": "v1",
        "global_governance": governance,
        "sets": [
            {
                "set_id": set_id,
                "title": set_title,
                "purpose": f"GPCR core full 100k {mode} residual candidate review.",
                "claim_role": "comparison_candidate",
                "preregistered_claim": (
                    "Not a claim: operational 100k comparison candidate for GPCR residual analysis; "
                    "not a router-promotion or delivery claim."
                ),
                "tasks": [
                    {
                        "task_id": task_id,
                        "domain": "gpcr",
                        "kind": "ligand_stress",
                        "profile_json": str(profile_json.resolve()),
                        "ligand_sizes": "100000",
                        "date_tag_suffix": f"{task_id.replace('_', '-')}-{tag_suffix}",
                    }
                ],
            }
        ],
    }


def build_payload(
    *,
    out_dir: str | Path,
    spec_json: str | Path,
    base_profile_json: str | Path,
    tag_suffix: str = DEFAULT_TAG_SUFFIX,
    variant: str = INTRUSION_VARIANT,
    mode: str = "shadow_only",
    set_id: str = "set1_core_blind",
    set_title: str = "Core Blind Set",
    task_id: str = "gpcr_core_full",
    generate_missing_spec: bool = True,
    heavy_artifacts_root: str = "",
    traj_writer_mode: str = "",
    traj_writer_workers: int | None = None,
    traj_writer_max_pending: int | None = None,
    traj_job_batch_size: int | None = None,
    traj_job_batch_autotune_candidates: str = "",
    traj_job_batch_autotune_frames: int | None = None,
    traj_engine_cache_max_entries: int | None = None,
    traj_prod_early_stop_enabled: bool | None = None,
    score_reference_scaling_mode: str = "run_local",
    score_reference_stats_json: str | Path = "",
) -> dict[str, Any]:
    variant = str(variant or INTRUSION_VARIANT).strip()
    if variant not in SUPPORTED_VARIANTS:
        raise ValueError(f"unsupported GPCR scale-up residual candidate variant: {variant}")
    mode = str(mode or "shadow_only").strip().lower()
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"unsupported GPCR scale-up residual candidate mode: {mode}")
    score_reference_scaling_mode = str(score_reference_scaling_mode or "run_local").strip()
    if score_reference_scaling_mode not in SUPPORTED_SCORE_REFERENCE_SCALING_MODES:
        raise ValueError(f"unsupported score reference scaling mode: {score_reference_scaling_mode}")
    out_root = _resolve(out_dir)
    residual_spec_path = _resolve(spec_json or VARIANT_DEFAULT_SPEC_JSON[variant])
    base_profile_path = _resolve(base_profile_json)
    score_reference_stats_path = _resolve(score_reference_stats_json) if str(score_reference_stats_json).strip() else None
    if score_reference_scaling_mode != "run_local" and score_reference_stats_path is None:
        raise ValueError("score_reference_stats_json is required for fixed score reference scaling candidates")
    if generate_missing_spec:
        ensure_residual_spec(residual_spec_path, variant=variant)

    residual_spec = _read_json(residual_spec_path)
    _validate_residual_spec(residual_spec, residual_spec_path, variant=variant)
    base_profile = _read_json(base_profile_path)

    profile_path = out_root / "profiles" / f"{base_profile_path.stem}_{tag_suffix}.json"
    set_spec_path = out_root / "specs" / f"{VARIANT_CANDIDATE_KIND[variant]}_{tag_suffix}.json"
    profile = _candidate_profile(
        base_profile,
        residual_spec_json=residual_spec_path,
        residual_spec=residual_spec,
        variant=variant,
        mode=mode,
        heavy_artifacts_root=heavy_artifacts_root,
        traj_writer_mode=traj_writer_mode,
        traj_writer_workers=traj_writer_workers,
        traj_writer_max_pending=traj_writer_max_pending,
        traj_job_batch_size=traj_job_batch_size,
        traj_job_batch_autotune_candidates=traj_job_batch_autotune_candidates,
        traj_job_batch_autotune_frames=traj_job_batch_autotune_frames,
        traj_engine_cache_max_entries=traj_engine_cache_max_entries,
        traj_prod_early_stop_enabled=traj_prod_early_stop_enabled,
        score_reference_scaling_mode=score_reference_scaling_mode,
        score_reference_stats_json=score_reference_stats_path,
    )
    set_spec = _candidate_set_spec(
        profile_json=profile_path,
        residual_spec_json=residual_spec_path,
        residual_spec=residual_spec,
        tag_suffix=tag_suffix,
        variant=variant,
        mode=mode,
        set_id=str(set_id or "set1_core_blind"),
        set_title=str(set_title or "Core Blind Set"),
        task_id=str(task_id or "gpcr_core_full"),
        score_reference_scaling_mode=score_reference_scaling_mode,
        score_reference_stats_json=score_reference_stats_path,
    )
    _write_json(profile_path, profile)
    _write_json(set_spec_path, set_spec)

    return {
        "candidate_kind": VARIANT_CANDIDATE_KIND[variant],
        "residual_prototype_mode": mode,
        "residual_prototype_variant": variant,
        "router_promotion_allowed": False,
        "base_profile_json": str(base_profile_path.resolve()),
        "residual_prototype_spec_json": str(residual_spec_path.resolve()),
        "profile_json": str(profile_path.resolve()),
        "set_spec_json": str(set_spec_path.resolve()),
        "score_reference_scaling_mode": score_reference_scaling_mode,
        "score_reference_stats_json": str(score_reference_stats_path.resolve()) if score_reference_stats_path else "",
        "run_command": (
            "python3 tools/run_external_validation_blind_sets.py "
            f"--set-spec-json {_rel_or_abs(set_spec_path)} --sets {str(set_id or 'set1_core_blind')}"
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR residual 100k comparison candidate profile and set-spec JSON.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--spec-json", default="")
    parser.add_argument("--base-profile-json", default=DEFAULT_BASE_PROFILE_JSON)
    parser.add_argument("--tag-suffix", default=DEFAULT_TAG_SUFFIX)
    parser.add_argument("--variant", choices=sorted(SUPPORTED_VARIANTS), default=INTRUSION_VARIANT)
    parser.add_argument("--mode", choices=sorted(SUPPORTED_MODES), default="shadow_only")
    parser.add_argument("--set-id", default="set1_core_blind")
    parser.add_argument("--set-title", default="Core Blind Set")
    parser.add_argument("--task-id", default="gpcr_core_full")
    parser.add_argument(
        "--heavy-artifacts-root",
        default="",
        help="Optional per-candidate heavy artifact root override for local 100k reruns.",
    )
    parser.add_argument(
        "--traj-writer-mode",
        default="",
        help="Optional trajectory writer mode override, e.g. thread for safer local reruns.",
    )
    parser.add_argument("--traj-writer-workers", type=int, default=None)
    parser.add_argument("--traj-writer-max-pending", type=int, default=None)
    parser.add_argument("--traj-job-batch-size", type=int, default=None)
    parser.add_argument("--traj-job-batch-autotune-candidates", default="")
    parser.add_argument("--traj-job-batch-autotune-frames", type=int, default=None)
    parser.add_argument("--traj-engine-cache-max-entries", type=int, default=None)
    parser.add_argument("--traj-prod-early-stop-enabled", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument(
        "--score-reference-scaling-mode",
        choices=sorted(SUPPORTED_SCORE_REFERENCE_SCALING_MODES),
        default="run_local",
    )
    parser.add_argument("--score-reference-stats-json", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        out_dir=args.out_dir,
        spec_json=args.spec_json,
        base_profile_json=args.base_profile_json,
        tag_suffix=args.tag_suffix,
        variant=args.variant,
        mode=args.mode,
        set_id=args.set_id,
        set_title=args.set_title,
        task_id=args.task_id,
        heavy_artifacts_root=args.heavy_artifacts_root,
        traj_writer_mode=args.traj_writer_mode,
        traj_writer_workers=args.traj_writer_workers,
        traj_writer_max_pending=args.traj_writer_max_pending,
        traj_job_batch_size=args.traj_job_batch_size,
        traj_job_batch_autotune_candidates=args.traj_job_batch_autotune_candidates,
        traj_job_batch_autotune_frames=args.traj_job_batch_autotune_frames,
        traj_engine_cache_max_entries=args.traj_engine_cache_max_entries,
        traj_prod_early_stop_enabled=args.traj_prod_early_stop_enabled,
        score_reference_scaling_mode=args.score_reference_scaling_mode,
        score_reference_stats_json=args.score_reference_stats_json,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
