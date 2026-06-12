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


def _refine_tier_physics_smoke_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    try:
        import numpy as np

        from core.allatom_forcefield import (
            allatom_energy,
            atom_typing_coverage_report,
            bonded_energy,
            dihedral_energy,
            equilibrium_bond_length,
            improper_energy,
            infer_atom_types,
            infer_bonds,
            infer_impropers,
            infer_torsions,
            nonbonded_energy,
            parameter_calibration_report,
            partial_charges_from_atom_types,
        )
        from core.mm_gbsa import compute_full_refine_stack

        compressed = np.asarray([[0.0, 0.0, 0.0], [1.20, 0.0, 0.0]], dtype=np.float64)
        stretched = np.asarray([[0.0, 0.0, 0.0], [1.85, 0.0, 0.0]], dtype=np.float64)
        elements = ["C", "O"]
        bonds = infer_bonds(stretched, elements)
        eq = equilibrium_bond_length("C", "O", 1.85)
        e_compressed = bonded_energy(compressed, [(0, 1)], elements=elements)
        e_stretched = bonded_energy(stretched, [(0, 1)], elements=elements)
        bonded_active = bool(
            bonds == [(0, 1)]
            and 1.40 <= float(eq) <= 1.65
            and float(e_stretched) > 0.0
            and abs(float(e_stretched) - float(e_compressed)) > 1e-3
        )
        checks.append(
            {
                "check_id": "refine_tier_allatom_bonded_energy_active",
                "status": "pass" if bonded_active else "blocked",
                "detail": "all-atom tier uses element-derived equilibrium bond lengths instead of current-distance zeroing",
            }
        )

        typed_coords = np.asarray(
            [[0.0, 0.0, 0.0], [1.25, 0.0, 0.0], [2.45, 0.0, 0.0], [3.75, 0.0, 0.0]],
            dtype=np.float64,
        )
        typed_elements = ["C", "O", "N", "H"]
        typed_bonds = infer_bonds(typed_coords, typed_elements)
        atom_types = infer_atom_types(typed_coords, typed_elements, bonds=typed_bonds)
        charges = partial_charges_from_atom_types(atom_types)
        nb_included = nonbonded_energy(typed_coords, typed_elements, atom_types=atom_types, charges=charges)
        nb_excluded = nonbonded_energy(
            typed_coords,
            typed_elements,
            atom_types=atom_types,
            charges=charges,
            exclude_pairs={(min(i, j), max(i, j)) for i, j in typed_bonds},
        )
        typed_ok = bool(
            atom_types[0] == "C_CARBONYL"
            and any(atom_type.startswith("O_") for atom_type in atom_types)
            and abs(float(np.sum(charges))) < 1e-8
            and float(charges[1]) < 0.0
            and nb_included["e_nonbonded"] != nb_excluded["e_nonbonded"]
        )
        checks.append(
            {
                "check_id": "refine_tier_atom_typing_charge_exclusion_active",
                "status": "pass" if typed_ok else "blocked",
                "detail": "internal all-atom tier infers atom types, neutralized partial charges, and bonded-pair nonbonded exclusions",
            }
        )

        coverage_coords = np.asarray(
            [
                [0.0, 0.0, 0.0],
                [1.5, 0.0, 0.0],
                [3.0, 0.0, 0.0],
                [4.5, 0.0, 0.0],
                [6.0, 0.0, 0.0],
                [7.5, 0.0, 0.0],
                [9.0, 0.0, 0.0],
                [10.5, 0.0, 0.0],
                [12.0, 0.0, 0.0],
                [13.5, 0.0, 0.0],
            ],
            dtype=np.float64,
        )
        coverage = atom_typing_coverage_report(
            coverage_coords,
            ["H", "C", "N", "O", "S", "P", "F", "Cl", "Br", "I"],
            bonds=[],
        )
        coverage_ok = bool(
            coverage.get("status") == "atom_typing_coverage_ready"
            and int(coverage.get("default_atom_count", -1)) == 0
            and abs(float(coverage.get("coverage_fraction", 0.0)) - 1.0) < 1e-12
            and "CL_HALOGEN" in coverage.get("atom_type_counts", {})
            and "BR_HALOGEN" in coverage.get("atom_type_counts", {})
            and coverage.get("charge_neutralization_ok") is True
        )
        checks.append(
            {
                "check_id": "refine_tier_atom_typing_coverage_surface",
                "status": "pass" if coverage_ok else "blocked",
                "detail": (
                    f"supported_elements={','.join(coverage.get('supported_elements', []))}; "
                    f"default_atom_count={coverage.get('default_atom_count')}; "
                    f"coverage_fraction={coverage.get('coverage_fraction')}"
                ),
            }
        )

        unsupported = atom_typing_coverage_report(
            np.asarray([[0.0, 0.0, 0.0], [2.2, 0.0, 0.0], [4.4, 0.0, 0.0]], dtype=np.float64),
            ["C", "Zn", "Mg"],
            bonds=[],
        )
        unsupported_energy = allatom_energy(
            np.asarray([[0.0, 0.0, 0.0], [2.2, 0.0, 0.0], [4.4, 0.0, 0.0]], dtype=np.float64),
            ["C", "Zn", "Mg"],
        )
        unsupported_fail_closed_ok = bool(
            unsupported.get("status") == "blocked_atom_typing_coverage"
            and unsupported.get("unsupported_metal_or_cofactor_elements") == ["MG", "ZN"]
            and int(unsupported.get("unsupported_metal_or_cofactor_count", 0)) == 2
            and unsupported_energy.get("atom_typing_coverage_status") == "blocked_atom_typing_coverage"
            and int(unsupported_energy.get("unsupported_metal_or_cofactor_count", 0)) == 2
        )
        checks.append(
            {
                "check_id": "refine_tier_unsupported_metal_fail_closed_surface",
                "status": "pass" if unsupported_fail_closed_ok else "blocked",
                "detail": (
                    "unsupported_metal_or_cofactor_elements="
                    f"{','.join(unsupported.get('unsupported_metal_or_cofactor_elements', []))}; "
                    f"energy_coverage_status={unsupported_energy.get('atom_typing_coverage_status')}"
                ),
            }
        )

        calibration = parameter_calibration_report(
            public_benchmark_pair_count=4,
            min_public_benchmark_pairs=5,
            public_benchmark_ready=False,
        )
        calibration_guard_ok = bool(
            calibration.get("status") == "blocked_parameter_calibration_claim"
            and calibration.get("claim_grade_parameterization_ready") is False
            and "insufficient_public_benchmark_pairs" in calibration.get("blockers", [])
            and "public_benchmark_gate_not_ready" in calibration.get("blockers", [])
        )
        checks.append(
            {
                "check_id": "refine_tier_parameter_calibration_claim_guard",
                "status": "pass" if calibration_guard_ok else "blocked",
                "detail": (
                    f"parameter_calibration_status={calibration.get('parameter_calibration_status')}; "
                    f"claim_grade_parameterization_ready={calibration.get('claim_grade_parameterization_ready')}; "
                    f"public_benchmark_pair_count={calibration.get('public_benchmark_pair_count')}/"
                    f"{calibration.get('min_public_benchmark_pairs')}"
                ),
            }
        )

        planar_chain = np.asarray(
            [[0.0, 0.0, 0.0], [1.54, 0.0, 0.0], [2.54, 1.0, 0.0], [3.54, 1.0, 0.0]],
            dtype=np.float64,
        )
        twisted_chain = np.asarray(
            [[0.0, 0.0, 0.0], [1.54, 0.0, 0.0], [2.54, 1.0, 0.0], [3.54, 1.0, 0.8]],
            dtype=np.float64,
        )
        torsions = infer_torsions(infer_bonds(planar_chain, ["C", "C", "C", "C"]))
        planar_center = np.asarray(
            [[0.0, 0.0, 0.0], [1.25, 0.0, 0.0], [0.0, 1.25, 0.0], [-1.0, -1.0, 0.0]],
            dtype=np.float64,
        )
        out_of_plane_center = planar_center.copy()
        out_of_plane_center[0, 2] = 0.4
        improper_elements = ["C", "O", "N", "H"]
        improper_bonds = infer_bonds(planar_center, improper_elements)
        improper_atom_types = infer_atom_types(planar_center, improper_elements, bonds=improper_bonds)
        impropers = infer_impropers(improper_bonds, improper_atom_types)
        bonded_shape_ok = bool(
            torsions == [(0, 1, 2, 3)]
            and dihedral_energy(planar_chain, torsions) != dihedral_energy(twisted_chain, torsions)
            and impropers == [(0, 1, 2, 3)]
            and improper_energy(out_of_plane_center, impropers) > improper_energy(planar_center, impropers)
        )
        checks.append(
            {
                "check_id": "refine_tier_dihedral_improper_terms_active",
                "status": "pass" if bonded_shape_ok else "blocked",
                "detail": "internal all-atom tier has periodic torsion and sp2-like improper planarity proxy terms",
            }
        )

        protein = np.asarray(
            [[0.0, 0.0, 0.0], [1.46, 0.0, 0.0], [2.02, 1.40, 0.0], [3.30, 1.55, 0.0]],
            dtype=np.float64,
        )
        ligand = np.asarray([[1.0, 2.3, 0.1], [2.2, 2.4, -0.1]], dtype=np.float64)
        stack = compute_full_refine_stack(protein, ligand, include_explicit=True, include_fep=True)
        aa = stack.get("allatom", {})
        gb = stack.get("gb_sa", {})
        explicit = stack.get("explicit", {})
        fep = stack.get("fep", {})
        stack_ok = bool(
            stack.get("refine_stack") == ["gb_sa", "allatom", "explicit_tip3p_shell", "fep"]
            and aa.get("parameterization_level") == "internal_united_atom_typed_v1"
            and aa.get("bond_model") == "covalent_radii_equilibrium_with_coarse_trace_fallback"
            and aa.get("charge_model") == "typed_partial_charge_neutralized_v1"
            and aa.get("nonbonded_exclusions") == "1-2_bonded_pairs"
            and aa.get("dihedral_model") == "periodic_torsion_proxy_n3"
            and aa.get("improper_model") == "planarity_proxy_for_sp2_like_centers"
            and gb.get("refine_tier") == "gb_sa_v1"
            and explicit.get("refine_tier") == "explicit_tip3p_shell_v1"
            and fep.get("status") == "fep_estimate_ready"
        )
        checks.append(
            {
                "check_id": "refine_tier_full_stack_internal_smoke",
                "status": "pass" if stack_ok else "blocked",
                "detail": "GB/SA, all-atom, explicit shell, and FEP scaffold run without external MD/docking engines",
            }
        )

        aa_energy = allatom_energy(protein, ["N", "C", "C", "O"])
        finite_energy = bool(np.isfinite(float(aa_energy.get("e_total", float("nan")))))
        checks.append(
            {
                "check_id": "refine_tier_allatom_energy_finite",
                "status": "pass" if finite_energy else "blocked",
                "detail": f"e_total={aa_energy.get('e_total')}",
            }
        )
    except Exception as exc:
        checks.append(
            {
                "check_id": "refine_tier_physics_smoke",
                "status": "blocked",
                "detail": f"{type(exc).__name__}: {exc}",
            }
        )
    return checks


def _refine_tier_benchmark_readiness_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    try:
        import numpy as np

        from core.score_calibration import calibration_quality_gate, fit_linear_calibration
        from core.structure_metrics import dockq_proxy, kabsch_rmsd, lddt_pli_proxy

        reference = np.asarray(
            [[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [2.0, 1.2, 0.0], [3.2, 1.3, 0.2]],
            dtype=np.float64,
        )
        model = reference + np.asarray(
            [[0.05, -0.03, 0.02], [0.00, 0.04, -0.01], [-0.04, 0.00, 0.03], [0.02, -0.02, 0.00]],
            dtype=np.float64,
        )
        pose_rmsd = kabsch_rmsd(model, reference)
        lddt = lddt_pli_proxy(model, reference)
        dockq = dockq_proxy(model, reference)
        pose_metrics_ready = bool(
            pose_rmsd is not None
            and float(pose_rmsd) < 0.20
            and lddt is not None
            and 0.0 <= float(lddt) <= 1.0
            and dockq is not None
        )
        checks.append(
            {
                "check_id": "refine_tier_pose_metric_surface_ready",
                "status": "pass" if pose_metrics_ready else "blocked",
                "detail": f"pose_rmsd_A={pose_rmsd}; lddt_pli_proxy={lddt}; dockq_proxy={dockq}",
            }
        )

        fit = fit_linear_calibration(
            proxy_values=np.asarray([-8.0, -7.0, -6.0, -5.0], dtype=np.float64),
            reference_dg=np.asarray([-9.1, -8.0, -6.8, -5.9], dtype=np.float64),
        )
        gate = calibration_quality_gate(fit, min_pairs=5, min_spearman=0.5)
        claim_guard_ok = bool(
            fit.get("status") == "calibration_ready"
            and int(gate.get("pair_count", 0)) == 4
            and gate.get("calibration_promotion_ready") is False
        )
        checks.append(
            {
                "check_id": "refine_tier_free_energy_calibration_claim_guard",
                "status": "pass" if claim_guard_ok else "blocked",
                "detail": (
                    "MM-GBSA calibration surface computes locally but remains claim-blocked until "
                    f"pair_count={gate.get('pair_count')} reaches min_pairs={gate.get('min_pairs_required')}"
                ),
            }
        )
    except Exception as exc:
        checks.append(
            {
                "check_id": "refine_tier_benchmark_readiness",
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
        "core.explicit_solvent",
        "core.fep",
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
    checks.extend(_refine_tier_physics_smoke_checks())
    checks.extend(_refine_tier_benchmark_readiness_checks())

    blocked = [item for item in checks if item["status"] != "pass"]
    ready = not blocked
    by_id = {item["check_id"]: item for item in checks}
    return {
        "summary": {
            "packet_type": "engine_refinement_tier_readiness",
            "status": "engine_refinement_tier_ready" if ready else "blocked_engine_refinement_tier_readiness",
            "engine_refinement_tier_ready": ready,
            "atom_typing_coverage_surface_ready": by_id.get(
                "refine_tier_atom_typing_coverage_surface",
                {},
            ).get("status")
            == "pass",
            "unsupported_metal_fail_closed_surface_ready": by_id.get(
                "refine_tier_unsupported_metal_fail_closed_surface",
                {},
            ).get("status")
            == "pass",
            "parameter_calibration_claim_guard_ready": by_id.get(
                "refine_tier_parameter_calibration_claim_guard",
                {},
            ).get("status")
            == "pass",
            "benchmark_metric_surface_ready": by_id.get("refine_tier_pose_metric_surface_ready", {}).get("status") == "pass",
            "free_energy_calibration_claim_guard_ready": by_id.get(
                "refine_tier_free_energy_calibration_claim_guard",
                {},
            ).get("status")
            == "pass",
            "claim_grade_public_benchmark_ready": False,
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
