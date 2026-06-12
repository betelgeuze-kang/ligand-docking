#!/usr/bin/env python3
"""Audit refine-tier physics wiring readiness (WS5 partial, Tier α science)."""
from __future__ import annotations

import argparse
import ast
import importlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ENGINE_CONFIG = "config/ligand_engine_production.json"
DEFAULT_OUT_JSON = "runs/engine_refinement_tier_readiness_current.json"

CLAIM_BOUNDARY = (
    "Engine refinement tier readiness only; it verifies internal refine-tier modules and HTVS stage3b "
    "policy wiring. It is not an OpenMM/Schrödinger-grade accuracy claim."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _module_importable(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def _trajectory_engine_param_surface_check() -> dict[str, Any]:
    required_params = {
        "electrostatic_scale",
        "debye_kappa",
        "backbone_bond_k",
        "backbone_bond_r0",
        "backbone_angle_k",
        "backbone_angle_theta0_rad",
    }
    required_flags = {
        "--electrostatic-scale",
        "--debye-kappa",
        "--backbone-bond-k",
        "--backbone-bond-r0",
        "--backbone-angle-k",
        "--backbone-angle-theta0-rad",
    }
    source_path = ROOT / "tools" / "generate_ligand_trajectory_engine.py"
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    except Exception as exc:
        return {
            "check_id": "trajectory_engine_coarse_forcefield_param_surface",
            "status": "blocked",
            "detail": f"trajectory engine source parse failed: {type(exc).__name__}: {exc}",
        }

    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    signature_ok = True
    for name in ("_engine_cache_key", "_get_engine_resources", "_simulate_with_engine_batch"):
        fn = functions.get(name)
        kwonly = {arg.arg for arg in fn.args.kwonlyargs} if fn is not None else set()
        signature_ok = signature_ok and required_params.issubset(kwonly)

    flags_seen: set[str] = set()
    for node in ast.walk(functions.get("build_parser", ast.Module(body=[], type_ignores=[]))):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("--"):
                    flags_seen.add(arg.value)
    cli_ok = required_flags.issubset(flags_seen)

    cache_fn = functions.get("_engine_cache_key")
    cache_names: set[str] = set()
    if cache_fn is not None:
        for node in ast.walk(cache_fn):
            if isinstance(node, ast.Name):
                cache_names.add(node.id)
    cache_ok = required_params.issubset(cache_names)

    ok = bool(signature_ok and cli_ok and cache_ok)
    return {
        "check_id": "trajectory_engine_coarse_forcefield_param_surface",
        "status": "pass" if ok else "blocked",
        "detail": "trajectory engine exposes coarse forcefield params via signatures, CLI flags, and cache key",
    }


def _residue_aware_fast_tier_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    try:
        import contextlib
        import io
        import torch

        from core.forcefield import ForceField
        from core.sequence_topology import (
            residue_coarse_charges_from_indices,
            residue_nonbonded_params_from_indices,
        )
        from core.topology import TopologyFactory

        with contextlib.redirect_stdout(io.StringIO()):
            top = TopologyFactory(
                n_res=5,
                t_type="protein",
                box_size=[40.0, 40.0, 40.0],
                device="cpu",
            )
        top.set_residue_types_from_sequence_string("GDEKR")
        expanded = top.residue_types_for_coordinate_count(10)
        block_layout_ok = (
            expanded is not None
            and int(expanded.numel()) == 10
            and torch.equal(expanded[:5], top.residue_types)
            and torch.equal(expanded[5:], top.residue_types)
        )
        checks.append(
            {
                "check_id": "fast_tier_ca_sc_residue_block_layout",
                "status": "pass" if block_layout_ok else "blocked",
                "detail": "CA/SC residue types align to [CA..., SC...] coordinate layout",
            }
        )

        sigma, epsilon = residue_nonbonded_params_from_indices(
            top.residue_types,
            base_sigma=3.8,
            base_epsilon=25.0,
        )
        residue_params_vary = bool(
            int(sigma.numel()) == 5
            and int(epsilon.numel()) == 5
            and (float(sigma.max().item()) != float(sigma.min().item()))
            and (float(epsilon.max().item()) != float(epsilon.min().item()))
        )
        checks.append(
            {
                "check_id": "fast_tier_residue_class_nonbonded_params",
                "status": "pass" if residue_params_vary else "blocked",
                "detail": "sequence-mapped residue classes produce non-uniform coarse sigma/epsilon",
            }
        )

        charges = residue_coarse_charges_from_indices(top.residue_types)
        has_acidic_and_basic_charge = bool(float(charges.min().item()) < 0.0 and float(charges.max().item()) > 0.0)
        checks.append(
            {
                "check_id": "fast_tier_residue_class_screened_charges",
                "status": "pass" if has_acidic_and_basic_charge else "blocked",
                "detail": "sequence-mapped acidic/basic residues produce coarse screened electrostatic charges",
            }
        )

        ff = ForceField.__new__(ForceField)
        ff.top = top
        ff.params = {
            "d_e": 0.0,
            "eps_solv": 0.0,
            "sigma": 3.8,
            "r0": 4.2,
            "electrostatic_scale": 0.0,
            "backbone_bond_k": 2.0,
            "backbone_bond_r0": 4.0,
            "backbone_angle_k": 1.0,
            "backbone_angle_theta0_rad": 2.0,
        }
        coords = torch.tensor(
            [[[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [9.0, 0.0, 0.0], [13.0, 0.0, 0.0], [17.0, 0.0, 0.0]]],
            dtype=torch.float32,
        )
        f_bond, pe_bond = ff._compute_coarse_backbone_bonds(coords)
        bonded_ok = bool(
            float(pe_bond.item()) > 0.0
            and float(f_bond[0, 0, 0].item()) > 0.0
            and float(f_bond[0, 1, 0].item()) < 0.0
        )
        checks.append(
            {
                "check_id": "fast_tier_coarse_backbone_bonded_term",
                "status": "pass" if bonded_ok else "blocked",
                "detail": "consecutive CA residues have a restricted harmonic backbone bond term",
            }
        )

        angle_coords = torch.tensor(
            [[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [4.0, 4.0, 0.0], [8.0, 4.0, 0.0], [12.0, 4.0, 0.0]]],
            dtype=torch.float32,
        )
        f_angle, pe_angle = ff._compute_coarse_backbone_angles(angle_coords)
        angle_ok = bool(float(pe_angle.item()) > 0.0 and float(f_angle.abs().sum().item()) > 0.0)
        checks.append(
            {
                "check_id": "fast_tier_coarse_backbone_angle_term",
                "status": "pass" if angle_ok else "blocked",
                "detail": "consecutive CA triplets have a restricted harmonic angle term",
            }
        )

        from tools.product.generate_perturbed_data import DataGenerator

        gen = DataGenerator.__new__(DataGenerator)
        gen.runtime_profile = {
            "hydro_strength": 1.0,
            "ionic_strength": 0.15,
            "force_scale": 1.0,
            "backbone_bond_k": 3.0,
            "backbone_bond_r0": 4.1,
            "k_angle": 50.0,
            "theta0": 120.0,
        }
        ff_params = gen._build_forcefield_params()
        runtime_plumbing_ok = bool(
            float(ff_params.get("backbone_bond_k", 0.0)) == 3.0
            and float(ff_params.get("backbone_bond_r0", 0.0)) == 4.1
            and float(ff_params.get("backbone_angle_k", 0.0)) == 2.0
            and float(ff_params.get("backbone_angle_theta0_rad", 0.0)) > 2.0
        )
        checks.append(
            {
                "check_id": "fast_tier_runtime_profile_forcefield_params",
                "status": "pass" if runtime_plumbing_ok else "blocked",
                "detail": "runtime profile maps coarse backbone bond/angle settings into ForceField params",
            }
        )

        checks.append(_trajectory_engine_param_surface_check())
    except Exception as exc:
        checks.append(
            {
                "check_id": "fast_tier_residue_aware_runtime",
                "status": "blocked",
                "detail": f"{type(exc).__name__}: {exc}",
            }
        )
    return checks


def build_engine_refinement_tier_readiness(*, engine_config: str = DEFAULT_ENGINE_CONFIG) -> dict[str, Any]:
    from tools.product.engine_refinement_config import load_engine_refinement_config

    cfg = load_engine_refinement_config(_resolve(engine_config))
    stage3 = cfg.get("stage3") if isinstance(cfg.get("stage3"), dict) else {}
    stage3b = cfg.get("stage3b") if isinstance(cfg.get("stage3b"), dict) else {}

    checks: list[dict[str, Any]] = []
    checks.append(
        {
            "check_id": "refine_tier_cascade_enabled",
            "status": "pass" if stage3.get("refine_tier_cascade") is True else "blocked",
            "detail": f"refine_tier_cascade={stage3.get('refine_tier_cascade')}",
        }
    )
    checks.append(
        {
            "check_id": "stage3b_physics_refinement_enabled",
            "status": "pass" if stage3b.get("run_physics_refinement") is True else "blocked",
            "detail": f"run_physics_refinement={stage3b.get('run_physics_refinement')}",
        }
    )
    checks.append(
        {
            "check_id": "stage3b_refined_energy_col",
            "status": "pass" if stage3b.get("physics_refinement_refined_energy_col") == "deltaG_mm_gbsa_kcal_mol" else "blocked",
            "detail": str(stage3b.get("physics_refinement_refined_energy_col")),
        }
    )
    for module_name in (
        "core.refine_physics",
        "core.mm_gbsa",
        "core.allatom_forcefield",
        "core.pocket_detection",
        "core.pose_generation",
    ):
        ok = _module_importable(module_name)
        checks.append({"check_id": f"module_{module_name}", "status": "pass" if ok else "blocked", "detail": module_name})

    script_checks = (
        "tools/run_ligand_physics_refinement.py",
        "tools/run_ligand_backmapping_scoring.py",
        "tools/product/engine_refinement_config.py",
    )
    for rel in script_checks:
        ok = _resolve(rel).is_file()
        checks.append({"check_id": f"script_{Path(rel).name}", "status": "pass" if ok else "blocked", "detail": rel})

    checks.extend(_residue_aware_fast_tier_checks())

    blocked = [item for item in checks if item["status"] != "pass"]
    ready = not blocked
    return {
        "summary": {
            "packet_type": "engine_refinement_tier_readiness",
            "status": "engine_refinement_tier_ready" if ready else "blocked_engine_refinement_tier_readiness",
            "engine_refinement_tier_ready": ready,
            "refine_tier": stage3b.get("physics_refinement_mode", "implicit_gb_sa_v1"),
            "refined_energy_col": stage3b.get("physics_refinement_refined_energy_col"),
            "check_count": len(checks),
            "pass_count": len(checks) - len(blocked),
            "blocked_count": len(blocked),
            "claim_boundary": CLAIM_BOUNDARY,
        },
        "checks": checks,
        "engine_config_path": engine_config,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build engine refinement tier readiness gate.")
    parser.add_argument("--engine-config", default=DEFAULT_ENGINE_CONFIG)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    args = parser.parse_args(argv)
    payload = build_engine_refinement_tier_readiness(engine_config=args.engine_config)
    out = _resolve(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
