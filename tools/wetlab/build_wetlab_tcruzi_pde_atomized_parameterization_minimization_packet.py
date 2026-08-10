#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from benchmarks.oracles.openmm import load_openmm
from tools.lib.artifacts import (
    artifact as _artifact,
    read_json as _read_json,
    resolve as _resolve,
    short_error as _short_error,
    text as _text,
    write_csv as _write_csv,
    write_json as _write_json,
)

DEFAULT_DRAFT_JSON = "runs/wetlab_tcruzi_pde_atomized_ligand_draft_packet_current.json"
DEFAULT_NATIVE_PDB = "data/public_structures/selected_allatom_native_v1/t_cruzi_pde_pdb_3V94.pdb"
DEFAULT_OUT_DIR = "runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_current"
DEFAULT_OUT_JSON = "runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.md"
DEFAULT_GAFF_XML = (
    "tools/bin/chimerax/local_unpack/usr/lib/ucsf-chimerax/lib/python3.11/"
    "site-packages/chimerax/minimize/gaff-2.2.20.xml"
)
DEFAULT_AMBERTOOLS_HOME = "tools/bin/chimerax/local_unpack/usr/lib/ucsf-chimerax/bin/amber20"


def _formal_charge_from_sdf(path_like: str | Path, fallback_smiles: str = "") -> int:
    try:
        from rdkit import Chem  # type: ignore
    except Exception:
        return 0
    mol = None
    path = _resolve(path_like)
    if path.exists():
        try:
            supplier = Chem.SDMolSupplier(str(path), removeHs=False)
            mol = supplier[0] if supplier and len(supplier) else None
        except Exception:
            mol = None
    if mol is None and fallback_smiles:
        mol = Chem.MolFromSmiles(fallback_smiles)
    if mol is None:
        return 0
    return int(sum(atom.GetFormalCharge() for atom in mol.GetAtoms()))


def _extract_chain_pdb(native_pdb: str | Path, out_pdb: str | Path, *, chain_id: str) -> dict[str, Any]:
    source = _resolve(native_pdb)
    out = _resolve(out_pdb)
    out.parent.mkdir(parents=True, exist_ok=True)
    atom_lines: list[str] = []
    rendered: list[str] = []
    previous_resseq: int | None = None
    previous_residue_key = ""
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("ATOM") and line[21].strip() == chain_id:
            residue_key = line[22:27]
            try:
                resseq = int(line[22:26])
            except ValueError:
                resseq = None
            if (
                previous_resseq is not None
                and resseq is not None
                and residue_key != previous_residue_key
                and resseq > previous_resseq + 1
            ):
                rendered.append("TER")
            rendered.append(line)
            atom_lines.append(line)
            if resseq is not None:
                previous_resseq = resseq
            previous_residue_key = residue_key
    rendered.append("TER")
    rendered, oxt_added_count = _add_c_terminal_oxt_records(rendered)
    out.write_text("\n".join([*rendered, "END", ""]), encoding="utf-8")
    ca_count = sum(1 for line in atom_lines if line[12:16].strip() == "CA")
    return {
        "path": _artifact(out),
        "chain_id": chain_id,
        "atom_line_count": len(atom_lines),
        "ca_count": ca_count,
        "c_terminal_oxt_added_count": oxt_added_count,
        "ready": bool(atom_lines and ca_count >= 3),
    }


def _add_c_terminal_oxt_records(lines: list[str]) -> tuple[list[str], int]:
    max_serial = max((int(line[6:11]) for line in lines if line.startswith("ATOM")), default=0)
    rendered: list[str] = []
    segment: list[str] = []
    added = 0

    def flush_segment() -> None:
        nonlocal added, max_serial
        if not segment:
            return
        residue_lines = [line for line in segment if line.startswith("ATOM")]
        terminal_key = residue_lines[-1][17:27] if residue_lines else ""
        terminal = [line for line in residue_lines if line[17:27] == terminal_key]
        atom_names = {line[12:16].strip() for line in terminal}
        rendered.extend(segment)
        if {"CA", "C", "O"}.issubset(atom_names) and "OXT" not in atom_names:
            coords: dict[str, np.ndarray] = {}
            for line in terminal:
                name = line[12:16].strip()
                if name in {"CA", "C", "O"}:
                    coords[name] = np.asarray(
                        [float(line[30:38]), float(line[38:46]), float(line[46:54])],
                        dtype=float,
                    )
            try:
                carbonyl = coords["O"] - coords["C"]
                ca_axis = coords["CA"] - coords["C"]
                direction = -(carbonyl / np.linalg.norm(carbonyl) + ca_axis / np.linalg.norm(ca_axis))
                direction = direction / np.linalg.norm(direction)
                oxt = coords["C"] + 1.24 * direction
                max_serial += 1
                last = terminal[-1]
                rendered.append(
                    f"ATOM  {max_serial:5d}  OXT {last[17:20]} {last[21]}{last[22:27]}"
                    f"   {oxt[0]:8.3f}{oxt[1]:8.3f}{oxt[2]:8.3f}  1.00 20.00           O  "
                )
                added += 1
            except Exception:
                pass

    for line in lines:
        if line.startswith("TER"):
            flush_segment()
            segment = []
            rendered.append(line)
        else:
            segment.append(line)
    flush_segment()
    return rendered, added


def _parse_mol2(path: str | Path) -> tuple[list[dict[str, Any]], list[tuple[int, int]]]:
    atoms: list[dict[str, Any]] = []
    bonds: list[tuple[int, int]] = []
    mode = ""
    for line in _resolve(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("@<TRIPOS>ATOM"):
            mode = "atom"
            continue
        if line.startswith("@<TRIPOS>BOND"):
            mode = "bond"
            continue
        if line.startswith("@<TRIPOS>"):
            mode = ""
            continue
        if not line.strip():
            continue
        if mode == "atom":
            parts = line.split()
            if len(parts) >= 9:
                atoms.append(
                    {
                        "index": int(parts[0]),
                        "name": parts[1],
                        "type": parts[5],
                        "charge": float(parts[8]),
                    }
                )
        elif mode == "bond":
            parts = line.split()
            if len(parts) >= 4:
                bonds.append((int(parts[1]), int(parts[2])))
    deduped_bonds: list[tuple[int, int]] = []
    seen_bonds: set[tuple[int, int]] = set()
    for atom_a, atom_b in bonds:
        key = tuple(sorted((atom_a, atom_b)))
        if atom_a == atom_b or key in seen_bonds:
            continue
        seen_bonds.add(key)
        deduped_bonds.append((atom_a, atom_b))
    return atoms, deduped_bonds


def _write_ligand_template_xml(path: str | Path, atoms: list[dict[str, Any]], bonds: list[tuple[int, int]]) -> None:
    lines = ["<ForceField>", "  <Residues>", '    <Residue name="LIG">']
    for atom in atoms:
        lines.append(
            f'      <Atom name="{atom["name"]}" type="{atom["type"]}" charge="{atom["charge"]}"/>'
        )
    for atom_a, atom_b in bonds:
        lines.append(f'      <Bond from="{atom_a - 1}" to="{atom_b - 1}"/>')
    lines.extend(["    </Residue>", "  </Residues>", "</ForceField>", ""])
    _resolve(path).write_text("\n".join(lines), encoding="utf-8")


def _rewrite_ligand_pdb_with_conect(source_pdb: str | Path, out_pdb: str | Path, bonds: list[tuple[int, int]]) -> None:
    source_lines = [
        line
        for line in _resolve(source_pdb).read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith(("ATOM", "HETATM"))
    ]
    rewritten: list[str] = []
    serial_map: dict[int, int] = {}
    for new_serial, line in enumerate(source_lines, start=1):
        old_serial = int(line[6:11])
        serial_map[old_serial] = new_serial
        atom_name = line[12:16]
        coords_tail = line[30:66]
        element_tail = line[66:] if len(line) > 66 else ""
        rewritten.append(f"HETATM{new_serial:5d} {atom_name} {'LIG':>3s} L   1    {coords_tail}{element_tail}")
    adjacency: dict[int, set[int]] = {}
    for atom_a, atom_b in bonds:
        if atom_a in serial_map and atom_b in serial_map:
            adjacency.setdefault(serial_map[atom_a], set()).add(serial_map[atom_b])
            adjacency.setdefault(serial_map[atom_b], set()).add(serial_map[atom_a])
    conect = [
        "CONECT%5d%s" % (atom_id, "".join(f"{other:5d}" for other in sorted(others)))
        for atom_id, others in sorted(adjacency.items())
        if others
    ]
    _resolve(out_pdb).write_text("\n".join([*rewritten, *conect, "END", ""]), encoding="utf-8")


def _write_integrated_complex_pdb(protein_pdb: str | Path, ligand_pdb: str | Path, out_pdb: str | Path) -> dict[str, Any]:
    protein_lines = [
        line
        for line in _resolve(protein_pdb).read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith(("ATOM", "TER"))
    ]
    ligand_lines = [
        line
        for line in _resolve(ligand_pdb).read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith(("HETATM", "CONECT"))
    ]
    max_serial = max((int(line[6:11]) for line in protein_lines if line.startswith("ATOM")), default=0)
    rewritten_ligand: list[str] = []
    serial_map: dict[int, int] = {}
    for line in ligand_lines:
        if not line.startswith("HETATM"):
            continue
        old_serial = int(line[6:11])
        new_serial = max_serial + len(serial_map) + 1
        serial_map[old_serial] = new_serial
        rewritten_ligand.append(f"HETATM{new_serial:5d} {line[12:16]} {'LIG':>3s} L   1    {line[30:66]}{line[66:]}")
    rewritten_conect: list[str] = []
    for line in ligand_lines:
        if not line.startswith("CONECT"):
            continue
        ids = [int(line[idx : idx + 5]) for idx in range(6, len(line), 5) if line[idx : idx + 5].strip()]
        if ids and ids[0] in serial_map:
            mapped = [serial_map[item] for item in ids[1:] if item in serial_map]
            if mapped:
                rewritten_conect.append("CONECT%5d%s" % (serial_map[ids[0]], "".join(f"{item:5d}" for item in mapped)))
    out = _resolve(out_pdb)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join([*protein_lines, *rewritten_ligand, *rewritten_conect, "END", ""]), encoding="utf-8")
    return {
        "complex_pdb": _artifact(out),
        "protein_atom_line_count": sum(1 for line in protein_lines if line.startswith("ATOM")),
        "ligand_atom_line_count": len(rewritten_ligand),
        "ligand_conect_line_count": len(rewritten_conect),
    }


def _available_platform(preferred: str) -> str:
    try:
        mm = load_openmm().mm

        names = [mm.Platform.getPlatform(i).getName() for i in range(mm.Platform.getNumPlatforms())]
        if preferred and preferred in names:
            return preferred
        if "CUDA" in names:
            return "CUDA"
        if "CPU" in names:
            return "CPU"
        return names[0] if names else ""
    except Exception:
        return ""


def _run_antechamber(
    *,
    ligand_pdb: str | Path,
    mol2_path: str | Path,
    ambertools_home: str | Path,
    ligand_charge: int,
    charge_method: str,
    timeout_sec: int,
) -> dict[str, Any]:
    amber_home = _resolve(ambertools_home)
    antechamber = amber_home / "bin" / "antechamber"
    if not antechamber.exists():
        return {"ready": False, "error": "antechamber_not_found", "antechamber": _artifact(antechamber)}
    env = os.environ.copy()
    env["AMBERHOME"] = str(amber_home)
    command = [
        str(antechamber),
        "-i",
        str(_resolve(ligand_pdb)),
        "-fi",
        "pdb",
        "-o",
        str(_resolve(mol2_path)),
        "-fo",
        "mol2",
        "-c",
        str(charge_method),
        "-s",
        "0",
        "-nc",
        str(int(ligand_charge)),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(_resolve(mol2_path).parent),
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ready": False,
            "antechamber": _artifact(antechamber),
            "antechamber_charge_method": str(charge_method),
            "antechamber_returncode": None,
            "error": _short_error(exc),
        }
    if result.returncode != 0 or not _resolve(mol2_path).exists():
        return {
            "ready": False,
            "antechamber": _artifact(antechamber),
            "antechamber_charge_method": str(charge_method),
            "antechamber_returncode": result.returncode,
            "error": _short_error((result.stderr or result.stdout or "antechamber_failed").strip()),
        }
    return {
        "ready": True,
        "antechamber": _artifact(antechamber),
        "antechamber_charge_method": str(charge_method),
        "antechamber_returncode": result.returncode,
    }


def _pairwise_min_distances_A(ligand: np.ndarray, protein: np.ndarray) -> np.ndarray:
    if ligand.size == 0 or protein.size == 0:
        return np.asarray([], dtype=float)
    diff = ligand[:, None, :] - protein[None, :, :]
    return np.min(np.linalg.norm(diff, axis=-1), axis=1)


def _parameterize_and_minimize(
    *,
    row: dict[str, Any],
    rank: int,
    protein_pdb: str | Path,
    out_dir: str | Path,
    gaff_xml: str | Path,
    ambertools_home: str | Path,
    timeout_sec: int,
    charge_method: str,
    max_iterations: int,
    rmsd_threshold_A: float,
    contact_cutoff_A: float,
    preferred_platform: str,
) -> dict[str, Any]:
    ligand_pdb = _resolve(_text(row.get("atomized_ligand_pdb")))
    ligand_sdf = _resolve(_text(row.get("atomized_ligand_sdf")))
    ligand_id = _text(row.get("ligand_id")) or f"ligand_{rank:02d}"
    safe_ligand = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in ligand_id)[:120]
    row_dir = _resolve(out_dir) / f"{rank:02d}_{safe_ligand}"
    row_dir.mkdir(parents=True, exist_ok=True)
    blockers: list[str] = []
    if not ligand_pdb.exists():
        return {**row, "blockers": ["atomized_ligand_pdb_missing"], "parameterization_status": "blocked"}
    if not _resolve(gaff_xml).exists():
        return {**row, "blockers": ["gaff_xml_missing"], "parameterization_status": "blocked"}

    ligand_charge = _formal_charge_from_sdf(ligand_sdf, _text(row.get("ligand_smiles")))
    mol2_path = row_dir / "ligand.mol2"
    ligand_conect_pdb = row_dir / "ligand_LIG_conect.pdb"
    template_xml = row_dir / "ligand_template.xml"
    complex_pdb = row_dir / "protein_ligand_complex.pdb"
    minimized_pdb = row_dir / "protein_ligand_complex_minimized.pdb"
    antechamber = _run_antechamber(
        ligand_pdb=ligand_pdb,
        mol2_path=mol2_path,
        ambertools_home=ambertools_home,
        ligand_charge=ligand_charge,
        charge_method=charge_method,
        timeout_sec=timeout_sec,
    )
    if not antechamber.get("ready"):
        return {
            **row,
            "ligand_formal_charge": ligand_charge,
            "parameterization_status": "antechamber_failed",
            "protein_local_minimization_status": "blocked_parameterization_failed",
            "parameterization_ready": False,
            "protein_local_minimization_ready": False,
            "blockers": ["antechamber_failed"],
            "parameterization_error": antechamber.get("error", ""),
            "antechamber_charge_method": antechamber.get("antechamber_charge_method", ""),
        }
    try:
        atoms, bonds = _parse_mol2(mol2_path)
        if not atoms or not bonds:
            raise RuntimeError("mol2_atoms_or_bonds_missing")
        _write_ligand_template_xml(template_xml, atoms, bonds)
        _rewrite_ligand_pdb_with_conect(ligand_pdb, ligand_conect_pdb, bonds)
        complex_info = _write_integrated_complex_pdb(protein_pdb, ligand_conect_pdb, complex_pdb)
    except Exception as exc:
        return {
            **row,
            "ligand_formal_charge": ligand_charge,
            "parameterization_status": "template_or_complex_build_failed",
            "protein_local_minimization_status": "blocked_parameterization_failed",
            "parameterization_ready": False,
            "protein_local_minimization_ready": False,
            "blockers": ["template_or_complex_build_failed"],
            "parameterization_error": _short_error(exc),
        }

    try:
        openmm = load_openmm()
        mm = openmm.mm
        unit = openmm.unit
        ForceField = openmm.app.ForceField
        Modeller = openmm.app.Modeller
        NoCutoff = openmm.app.NoCutoff
        PDBFile = openmm.app.PDBFile
        Simulation = openmm.app.Simulation
    except Exception as exc:
        return {
            **row,
            "ligand_formal_charge": ligand_charge,
            "parameterization_status": "openmm_missing",
            "protein_local_minimization_status": "blocked_openmm_missing",
            "parameterization_ready": False,
            "protein_local_minimization_ready": False,
            "blockers": ["openmm_missing"],
            "parameterization_error": _short_error(exc),
        }

    try:
        forcefield = ForceField("amber14-all.xml", str(_resolve(gaff_xml)), str(template_xml))
        protein = PDBFile(str(_resolve(protein_pdb)))
        protein_forcefield = ForceField("amber14-all.xml")
        modeller = Modeller(protein.topology, protein.positions)
        modeller.addHydrogens(protein_forcefield, pH=7.4)
        ligand = PDBFile(str(ligand_conect_pdb))
        modeller.add(ligand.topology, ligand.positions)
        try:
            system = forcefield.createSystem(
                modeller.topology,
                nonbondedMethod=NoCutoff,
                constraints=None,
                ignoreExternalBonds=True,
            )
        except TypeError:
            system = forcefield.createSystem(modeller.topology, nonbondedMethod=NoCutoff, constraints=None)
        positions = modeller.positions
        protein_heavy: list[int] = []
        ligand_heavy: list[int] = []
        for atom in modeller.topology.atoms():
            element = atom.element.symbol if atom.element else ""
            if element == "H":
                continue
            if atom.residue.name == "LIG":
                ligand_heavy.append(atom.index)
            else:
                protein_heavy.append(atom.index)
        if not protein_heavy or not ligand_heavy:
            raise RuntimeError("protein_or_ligand_heavy_atoms_missing")

        restraint = mm.CustomExternalForce("0.5*k*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
        restraint.addGlobalParameter("k", 1000.0)
        restraint.addPerParticleParameter("x0")
        restraint.addPerParticleParameter("y0")
        restraint.addPerParticleParameter("z0")
        for atom_index in protein_heavy:
            xyz = positions[atom_index].value_in_unit(unit.nanometer)
            restraint.addParticle(atom_index, xyz)
        system.addForce(restraint)

        integrator = mm.LangevinIntegrator(300 * unit.kelvin, 1 / unit.picosecond, 0.002 * unit.picoseconds)
        platform_name = _available_platform(preferred_platform)
        if platform_name:
            simulation = Simulation(modeller.topology, system, integrator, mm.Platform.getPlatformByName(platform_name))
        else:
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
        initial_ligand = np.asarray([positions[index].value_in_unit(unit.angstrom) for index in ligand_heavy], dtype=float)
        final_ligand = np.asarray([final_positions[index].value_in_unit(unit.angstrom) for index in ligand_heavy], dtype=float)
        final_protein = np.asarray([final_positions[index].value_in_unit(unit.angstrom) for index in protein_heavy], dtype=float)
        ligand_rmsd = float(math.sqrt(np.mean(np.sum((final_ligand - initial_ligand) ** 2, axis=1))))
        min_distances = _pairwise_min_distances_A(final_ligand, final_protein)
        mean_min_distance = float(np.mean(min_distances)) if min_distances.size else None
        contact_fraction = float(np.mean(min_distances <= float(contact_cutoff_A))) if min_distances.size else None
        survival_pass = bool(ligand_rmsd <= float(rmsd_threshold_A))
        if not survival_pass:
            blockers.append("ligand_heavy_atom_rmsd_above_threshold")
        with minimized_pdb.open("w", encoding="utf-8") as fh:
            PDBFile.writeFile(modeller.topology, final_positions, fh)
        return {
            **row,
            "ligand_formal_charge": ligand_charge,
            "parameterization_status": "integrated_openmm_system_ready",
            "protein_local_minimization_status": "pass" if survival_pass else "fail_pose_rmsd_above_threshold",
            "parameterization_ready": True,
            "protein_local_minimization_ready": survival_pass,
            "local_minimization_survival_fraction": 1.0 if survival_pass else 0.0,
            "ligand_heavy_atom_rmsd_A": ligand_rmsd,
            "rmsd_threshold_A": float(rmsd_threshold_A),
            "mean_min_distance_A": mean_min_distance,
            "contact_fraction": contact_fraction,
            "contact_cutoff_A": float(contact_cutoff_A),
            "initial_energy_kj_mol": float(initial_energy),
            "final_energy_kj_mol": float(final_energy),
            "energy_delta_kj_mol": float(final_energy - initial_energy),
            "ligand_heavy_atom_count": len(ligand_heavy),
            "protein_heavy_atom_count": len(protein_heavy),
            "hydrogenated_complex_atom_count": modeller.topology.getNumAtoms(),
            "particle_count": system.getNumParticles(),
            "force_count": system.getNumForces(),
            "openmm_platform": platform_name,
            "gaff_xml": _artifact(gaff_xml),
            "ambertools_antechamber": antechamber.get("antechamber", ""),
            "antechamber_charge_method": antechamber.get("antechamber_charge_method", ""),
            "mol2_atom_count": len(atoms),
            "mol2_bond_count": len(bonds),
            "ligand_template_xml": _artifact(template_xml),
            "ligand_conect_pdb": _artifact(ligand_conect_pdb),
            "integrated_complex_pdb": _artifact(complex_pdb),
            "minimized_complex_pdb": _artifact(minimized_pdb),
            "blockers": blockers,
            **complex_info,
        }
    except Exception as exc:
        return {
            **row,
            "ligand_formal_charge": ligand_charge,
            "parameterization_status": "integrated_openmm_system_failed",
            "protein_local_minimization_status": "blocked_parameterization_failed",
            "parameterization_ready": False,
            "protein_local_minimization_ready": False,
            "ligand_template_xml": _artifact(template_xml),
            "integrated_complex_pdb": _artifact(complex_pdb),
            "blockers": ["integrated_openmm_system_failed"],
            "parameterization_error": _short_error(exc),
        }


def build_payload(
    *,
    draft_json: str | Path = DEFAULT_DRAFT_JSON,
    native_pdb: str | Path = DEFAULT_NATIVE_PDB,
    native_chain_id: str = "B",
    out_dir: str | Path = DEFAULT_OUT_DIR,
    gaff_xml: str | Path = DEFAULT_GAFF_XML,
    ambertools_home: str | Path = DEFAULT_AMBERTOOLS_HOME,
    timeout_sec: int = 120,
    charge_method: str = "gas",
    max_iterations: int = 100,
    rmsd_threshold_A: float = 2.5,
    contact_cutoff_A: float = 4.5,
    openmm_platform: str = "",
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    draft = _read_json(draft_json)
    draft_rows = [dict(row or {}) for row in (draft.get("rows", []) or [])]
    out_root = _resolve(out_dir)
    protein_pdb = out_root / "tcruzi_pde_chain_B_protein_only.pdb"
    protein_info = _extract_chain_pdb(native_pdb, protein_pdb, chain_id=native_chain_id)
    rows: list[dict[str, Any]] = []
    if not protein_info.get("ready"):
        rows = [
            {
                **row,
                "parameterization_status": "blocked_protein_chain_missing",
                "protein_local_minimization_status": "blocked_protein_chain_missing",
                "parameterization_ready": False,
                "protein_local_minimization_ready": False,
                "blockers": ["protein_chain_missing"],
            }
            for row in draft_rows
        ]
    else:
        for rank, row in enumerate(draft_rows, start=1):
            rows.append(
                _parameterize_and_minimize(
                    row=row,
                    rank=rank,
                    protein_pdb=protein_pdb,
                    out_dir=out_root,
                    gaff_xml=gaff_xml,
                    ambertools_home=ambertools_home,
                    timeout_sec=timeout_sec,
                    charge_method=charge_method,
                    max_iterations=max_iterations,
                    rmsd_threshold_A=rmsd_threshold_A,
                    contact_cutoff_A=contact_cutoff_A,
                    preferred_platform=openmm_platform,
                )
            )
    parameterized = [row for row in rows if bool(row.get("parameterization_ready"))]
    minimized = [row for row in rows if bool(row.get("protein_local_minimization_ready"))]
    validated = [
        row
        for row in minimized
        if row.get("local_minimization_survival_fraction") == 1.0
        and row.get("mean_min_distance_A") is not None
    ]
    best = min(
        validated,
        key=lambda row: (
            float(row.get("mean_min_distance_A") or 999.0),
            float(row.get("ligand_heavy_atom_rmsd_A") or 999.0),
        ),
        default={},
    )
    hard_block_count = sum(1 for row in rows if row.get("blockers"))
    status = (
        "wetlab_tcruzi_pde_atomized_parameterization_minimization_pass"
        if len(parameterized) == len(rows) and len(minimized) == len(rows) and rows
        else "blocked_wetlab_tcruzi_pde_atomized_parameterization_minimization"
    )
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "target_id": "T. cruzi PDE",
        "draft_json": _artifact(draft_json),
        "native_pdb": _artifact(native_pdb),
        "native_chain_id": native_chain_id,
        "protein_pdb": protein_info.get("path", ""),
        "protein_ca_count": protein_info.get("ca_count", 0),
        "out_dir": _artifact(out_root),
        "row_count": len(rows),
        "parameterization_ready_count": len(parameterized),
        "protein_local_minimization_ready_count": len(minimized),
        "validated_repair_count": len(validated),
        "hard_block_count": hard_block_count,
        "rmsd_threshold_A": float(rmsd_threshold_A),
        "contact_cutoff_A": float(contact_cutoff_A),
        "antechamber_charge_method": charge_method,
        "openmm_platform": _available_platform(openmm_platform),
        "gaff_xml": _artifact(gaff_xml),
        "ambertools_home": _artifact(ambertools_home),
        "best_validated_ligand_id": _text(best.get("ligand_id")),
        "best_validated_mean_min_distance_A": best.get("mean_min_distance_A"),
        "best_validated_ligand_heavy_atom_rmsd_A": best.get("ligand_heavy_atom_rmsd_A"),
        "best_validated_contact_fraction": best.get("contact_fraction"),
        "claim_promotion_allowed": False,
        "commercial_repair_evidence_allowed": bool(validated),
        "next_required_step": (
            "Feed this atomized parameterization/local-min evidence into the PDE all-atom review overlay and "
            "rebuild the selected-allatom burndown."
            if validated
            else "Fix row-level parameterization/local-min blockers before using atomized PDE ligands as repair evidence."
        ),
    }
    return {
        "packet_type": "wetlab_tcruzi_pde_atomized_parameterization_minimization_packet",
        "summary": summary,
        "protein_preparation": protein_info,
        "rows": rows,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "commercial_repair_evidence_allowed": bool(validated),
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# T. cruzi PDE Atomized Parameterization/Local-Min Packet",
        "",
        "## Summary",
        "",
    ]
    for key in (
        "status",
        "row_count",
        "parameterization_ready_count",
        "protein_local_minimization_ready_count",
        "validated_repair_count",
        "hard_block_count",
        "best_validated_ligand_id",
        "best_validated_mean_min_distance_A",
        "best_validated_ligand_heavy_atom_rmsd_A",
        "commercial_repair_evidence_allowed",
        "claim_promotion_allowed",
        "next_required_step",
    ):
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| rank | ligand_id | parameterization | local_min | rmsd_A | mean_min_distance_A | contact_fraction | blockers |",
            "|---:|---|---|---|---:|---:|---:|---|",
        ]
    )
    for idx, row in enumerate(payload.get("rows", []) or [], start=1):
        blockers = ",".join(str(item) for item in (row.get("blockers") or [])) or "-"
        lines.append(
            f"| {idx} | `{row.get('ligand_id','')}` | `{row.get('parameterization_status','')}` | "
            f"`{row.get('protein_local_minimization_status','')}` | `{row.get('ligand_heavy_atom_rmsd_A','')}` | "
            f"`{row.get('mean_min_distance_A','')}` | `{row.get('contact_fraction','')}` | `{blockers}` |"
        )
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parameterize and locally minimize T. cruzi PDE atomized ligands.")
    parser.add_argument("--draft-json", default=DEFAULT_DRAFT_JSON)
    parser.add_argument("--native-pdb", default=DEFAULT_NATIVE_PDB)
    parser.add_argument("--native-chain-id", default="B")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--gaff-xml", default=DEFAULT_GAFF_XML)
    parser.add_argument("--ambertools-home", default=DEFAULT_AMBERTOOLS_HOME)
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument("--charge-method", default="gas")
    parser.add_argument("--max-iterations", type=int, default=100)
    parser.add_argument("--rmsd-threshold-A", type=float, default=2.5)
    parser.add_argument("--contact-cutoff-A", type=float, default=4.5)
    parser.add_argument("--openmm-platform", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        draft_json=args.draft_json,
        native_pdb=args.native_pdb,
        native_chain_id=args.native_chain_id,
        out_dir=args.out_dir,
        gaff_xml=args.gaff_xml,
        ambertools_home=args.ambertools_home,
        timeout_sec=args.timeout_sec,
        charge_method=args.charge_method,
        max_iterations=args.max_iterations,
        rmsd_threshold_A=args.rmsd_threshold_A,
        contact_cutoff_A=args.contact_cutoff_A,
        openmm_platform=args.openmm_platform,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    md_path = _resolve(args.out_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(payload["summary"])


if __name__ == "__main__":
    main()
