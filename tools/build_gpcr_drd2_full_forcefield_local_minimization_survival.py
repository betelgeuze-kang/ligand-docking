#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from tools.lib.artifacts import (
    ROOT,
    artifact as _artifact,
    read_json as _read_json,
    resolve as _resolve,
    short_error as _short_error,
    write_csv as _write_csv,
    write_json as _write_json,
)

DEFAULT_PARAMETERIZATION_PROBE_JSON = "runs/gpcr_drd2_openmm_forcefield_parameterization_probe_current.json"
DEFAULT_GAFF_XML = (
    "tools/bin/chimerax/local_unpack/usr/lib/ucsf-chimerax/lib/python3.11/"
    "site-packages/chimerax/minimize/gaff-2.2.20.xml"
)
DEFAULT_OUT_JSON = "runs/gpcr_drd2_local_minimization_survival_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_drd2_local_minimization_survival_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_drd2_local_minimization_survival_current.md"
DEFAULT_TARGET = "CHEMBL217_DRD2_HUMAN"
DEFAULT_LIGAND_ID = "CHEMBL301265"
DEFAULT_RMSD_THRESHOLD_A = 2.0


def _probe_paths(parameterization_probe: dict[str, Any]) -> dict[str, str]:
    probes = parameterization_probe.get("capability_probes", {})
    probes = probes if isinstance(probes, dict) else {}
    integrated = probes.get("integrated_protein_ligand_openmm", {})
    integrated = integrated if isinstance(integrated, dict) else {}
    return {
        "complex_pdb": str(integrated.get("complex_pdb") or ""),
        "ligand_template_xml": str(integrated.get("ligand_template_xml") or ""),
    }


def _rmsd_A(reference: np.ndarray, mobile: np.ndarray) -> float:
    ref = np.asarray(reference, dtype=float)
    mob = np.asarray(mobile, dtype=float)
    return float(math.sqrt(np.mean(np.sum((mob - ref) ** 2, axis=1))))


def _run_full_forcefield_minimization(
    *,
    complex_pdb: str | Path,
    ligand_template_xml: str | Path,
    gaff_xml: str | Path,
    protein_restraint_k_kj_mol_nm2: float,
    max_iterations: int,
) -> dict[str, Any]:
    try:
        import openmm as mm  # type: ignore
        from openmm import unit  # type: ignore
        from openmm.app import ForceField, Modeller, NoCutoff, PDBFile, Simulation  # type: ignore
    except Exception as exc:
        return {"attempted": False, "ready": False, "error": _short_error(exc)}

    complex_path = _resolve(complex_pdb)
    template_path = _resolve(ligand_template_xml)
    gaff_path = _resolve(gaff_xml)
    if not complex_path.exists() or not template_path.exists() or not gaff_path.exists():
        return {
            "attempted": False,
            "ready": False,
            "complex_pdb": _artifact(complex_path),
            "ligand_template_xml": _artifact(template_path),
            "gaff_xml": _artifact(gaff_path),
            "error": "complex_or_forcefield_artifact_missing",
        }
    try:
        pdb = PDBFile(str(complex_path))
        forcefield = ForceField("amber14-all.xml", str(gaff_path), str(template_path))
        modeller = Modeller(pdb.topology, pdb.positions)
        modeller.addHydrogens(forcefield, pH=7.4)
        system = forcefield.createSystem(modeller.topology, nonbondedMethod=NoCutoff, constraints=None)
        positions = modeller.positions
        protein_heavy: list[int] = []
        ligand_heavy: list[int] = []
        for atom in modeller.topology.atoms():
            element = atom.element.symbol if atom.element else ""
            if atom.residue.name == "LIG" and element != "H":
                ligand_heavy.append(atom.index)
            elif atom.residue.name != "LIG" and element != "H":
                protein_heavy.append(atom.index)
        if not ligand_heavy:
            return {"attempted": True, "ready": False, "error": "ligand_heavy_atoms_missing"}

        restraint = mm.CustomExternalForce("0.5*k*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
        restraint.addGlobalParameter("k", float(protein_restraint_k_kj_mol_nm2))
        restraint.addPerParticleParameter("x0")
        restraint.addPerParticleParameter("y0")
        restraint.addPerParticleParameter("z0")
        for atom_index in protein_heavy:
            xyz = positions[atom_index].value_in_unit(unit.nanometer)
            restraint.addParticle(atom_index, xyz)
        system.addForce(restraint)

        integrator = mm.LangevinIntegrator(300 * unit.kelvin, 1 / unit.picosecond, 0.002 * unit.picoseconds)
        try:
            platform = mm.Platform.getPlatformByName("CPU")
            simulation = Simulation(modeller.topology, system, integrator, platform)
        except Exception:
            simulation = Simulation(modeller.topology, system, integrator)
        simulation.context.setPositions(positions)
        state0 = simulation.context.getState(getEnergy=True)
        initial_energy = state0.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
        mm.LocalEnergyMinimizer.minimize(
            simulation.context,
            tolerance=10.0 * unit.kilojoule_per_mole / unit.nanometer,
            maxIterations=int(max_iterations),
        )
        state1 = simulation.context.getState(getPositions=True, getEnergy=True)
        final_energy = state1.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
        final_positions = state1.getPositions()
        reference = np.asarray([positions[index].value_in_unit(unit.angstrom) for index in ligand_heavy], dtype=float)
        mobile = np.asarray([final_positions[index].value_in_unit(unit.angstrom) for index in ligand_heavy], dtype=float)
        rmsd = _rmsd_A(reference, mobile)
        return {
            "attempted": True,
            "ready": True,
            "complex_pdb": _artifact(complex_path),
            "ligand_template_xml": _artifact(template_path),
            "gaff_xml": _artifact(gaff_path),
            "particle_count": system.getNumParticles(),
            "force_count": system.getNumForces(),
            "protein_heavy_restraint_count": len(protein_heavy),
            "ligand_heavy_atom_count": len(ligand_heavy),
            "initial_energy_kj_mol": float(initial_energy),
            "final_energy_kj_mol": float(final_energy),
            "ligand_heavy_atom_rmsd_A": rmsd,
            "max_iterations": int(max_iterations),
        }
    except Exception as exc:
        return {
            "attempted": True,
            "ready": False,
            "complex_pdb": _artifact(complex_path),
            "ligand_template_xml": _artifact(template_path),
            "error": _short_error(exc),
        }


def build_survival_packet(
    *,
    parameterization_probe_json: str | Path = DEFAULT_PARAMETERIZATION_PROBE_JSON,
    gaff_xml: str | Path = DEFAULT_GAFF_XML,
    rmsd_threshold_A: float = DEFAULT_RMSD_THRESHOLD_A,
    protein_restraint_k_kj_mol_nm2: float = 1000.0,
    max_iterations: int = 100,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    parameterization_probe = _read_json(parameterization_probe_json)
    paths = _probe_paths(parameterization_probe)
    result = _run_full_forcefield_minimization(
        complex_pdb=paths["complex_pdb"],
        ligand_template_xml=paths["ligand_template_xml"],
        gaff_xml=gaff_xml,
        protein_restraint_k_kj_mol_nm2=protein_restraint_k_kj_mol_nm2,
        max_iterations=max_iterations,
    )
    rmsd = result.get("ligand_heavy_atom_rmsd_A")
    pass_gate = bool(result.get("ready") and isinstance(rmsd, (int, float)) and float(rmsd) <= float(rmsd_threshold_A))
    blockers: list[str] = []
    if not result.get("ready"):
        blockers.append("full_forcefield_local_minimization_failed")
    if isinstance(rmsd, (int, float)) and float(rmsd) > float(rmsd_threshold_A):
        blockers.append("ligand_pose_rmsd_above_threshold")
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "full_forcefield_local_minimization_survival_pass" if pass_gate else "blocked_full_forcefield_local_minimization_survival",
        "survival_fraction": 1.0 if pass_gate else 0.0,
        "hard_decoy_rebuild_evidence_allowed": pass_gate,
        "rmsd_threshold_A": float(rmsd_threshold_A),
        "ligand_heavy_atom_rmsd_A": rmsd,
        "engine_kind": "openmm_full_forcefield_restrained_receptor",
        "survival_claim_scope": "full_protein_ligand_forcefield_restrained_receptor",
        "blockers": blockers,
        "next_required_step": (
            "Use this claim-grade local-minimization survival evidence to reopen DRD2 hard-decoy rebuild diagnostics."
            if pass_gate
            else "Fix integrated parameterization/minimization before DRD2 hard-decoy rebuild."
        ),
    }
    row = {
        "target": DEFAULT_TARGET,
        "ligand_id": DEFAULT_LIGAND_ID,
        "survival_fraction": summary["survival_fraction"],
        "engine_kind": summary["engine_kind"],
        "survival_claim_scope": summary["survival_claim_scope"],
        "hard_decoy_rebuild_evidence_allowed": pass_gate,
        "ligand_heavy_atom_rmsd_A": rmsd,
        "blockers": blockers,
    }
    return {
        "packet_type": "gpcr_drd2_full_forcefield_local_minimization_survival",
        "summary": summary,
        "rows": [row],
        "parameterization_probe_json": _artifact(parameterization_probe_json),
        "minimization_probe": result,
        "claim_boundary": {
            "hard_decoy_rebuild_evidence_allowed": pass_gate,
            "claim_promotion_allowed": False,
            "guarded_100k_rerun_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = ["# GPCR DRD2 Full-Forcefield Local-Minimization Survival", "", "## Summary"]
    for key in (
        "status",
        "survival_fraction",
        "hard_decoy_rebuild_evidence_allowed",
        "ligand_heavy_atom_rmsd_A",
        "rmsd_threshold_A",
        "engine_kind",
        "survival_claim_scope",
        "blockers",
        "next_required_step",
    ):
        lines.append(f"- {key}: `{summary[key]}`")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DRD2 full-forcefield local-minimization survival smoke probe.")
    parser.add_argument("--parameterization-probe-json", default=DEFAULT_PARAMETERIZATION_PROBE_JSON)
    parser.add_argument("--gaff-xml", default=DEFAULT_GAFF_XML)
    parser.add_argument("--rmsd-threshold-A", type=float, default=DEFAULT_RMSD_THRESHOLD_A)
    parser.add_argument("--protein-restraint-k-kj-mol-nm2", type=float, default=1000.0)
    parser.add_argument("--max-iterations", type=int, default=100)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_survival_packet(
        parameterization_probe_json=args.parameterization_probe_json,
        gaff_xml=args.gaff_xml,
        rmsd_threshold_A=args.rmsd_threshold_A,
        protein_restraint_k_kj_mol_nm2=args.protein_restraint_k_kj_mol_nm2,
        max_iterations=args.max_iterations,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
