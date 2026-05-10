#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tools.lib.artifacts import (
    ROOT,
    artifact as _artifact,
    read_csv as _read_csv,
    resolve as _resolve,
    short_error as _short_error,
    text as _text,
    truthy as _truthy,
    write_json as _write_json,
)

DEFAULT_INPUT_CSV = "runs/gpcr_drd2_pseudo_allatom_repair_rows_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_drd2_openmm_forcefield_parameterization_probe_current.json"
DEFAULT_OUT_MD = "runs/gpcr_drd2_openmm_forcefield_parameterization_probe_current.md"
DEFAULT_TARGET = "CHEMBL217_DRD2_HUMAN"
DEFAULT_POSITIVE_LIGAND = "CHEMBL301265"
DEFAULT_LIGAND_CHARGE = 1
DEFAULT_PREPARED_PROTEIN_PDB = "runs/gpcr_drd2_6cm4_chimerax_sidechain_rebuilt_split_oxt_current.pdb"
DEFAULT_INTEGRATED_COMPLEX_PDB = "runs/gpcr_drd2_integrated_openmm_complex_parameterization_probe_current.pdb"
DEFAULT_LIGAND_TEMPLATE_XML = "runs/gpcr_drd2_ligand_gaff_template_current.xml"

CHIMERAX_GAFF_XML = (
    "tools/bin/chimerax/local_unpack/usr/lib/ucsf-chimerax/lib/python3.11/"
    "site-packages/chimerax/minimize/gaff-2.2.20.xml"
)
CHIMERAX_AMBERTOOLS_HOME = "tools/bin/chimerax/local_unpack/usr/lib/ucsf-chimerax/bin/amber20"


def _find_positive(rows: list[dict[str, str]], target: str, ligand_id: str) -> dict[str, str] | None:
    for row in rows:
        if _text(row.get("target")) == target and _text(row.get("ligand_id")) == ligand_id:
            return row
    for row in rows:
        if _truthy(row.get("is_positive")) or _text(row.get("ligand_id")) == ligand_id:
            return row
    return None


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


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
    return atoms, bonds


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


def _write_pdb_with_conect(source_pdb: str | Path, out_pdb: str | Path, bonds: list[tuple[int, int]]) -> None:
    source_lines = [
        line for line in _resolve(source_pdb).read_text(encoding="utf-8", errors="replace").splitlines()
        if not line.startswith("END") and not line.startswith("CONECT")
    ]
    adjacency: dict[int, set[int]] = {}
    for atom_a, atom_b in bonds:
        adjacency.setdefault(atom_a, set()).add(atom_b)
        adjacency.setdefault(atom_b, set()).add(atom_a)
    conect = [
        "CONECT%5d%s" % (atom_id, "".join(f"{other:5d}" for other in sorted(others)))
        for atom_id, others in sorted(adjacency.items())
        if others
    ]
    _resolve(out_pdb).write_text("\n".join([*source_lines, *conect, "END", ""]), encoding="utf-8")


def _write_integrated_complex_pdb(protein_pdb: str | Path, ligand_pdb: str | Path, out_pdb: str | Path) -> dict[str, Any]:
    protein_path = _resolve(protein_pdb)
    ligand_path = _resolve(ligand_pdb)
    out_path = _resolve(out_pdb)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    protein_lines = [
        line
        for line in protein_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith(("ATOM", "TER"))
    ]
    ligand_atom_lines = [
        line
        for line in ligand_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith(("ATOM", "HETATM"))
    ]
    ligand_conect_lines = [
        line for line in ligand_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.startswith("CONECT")
    ]
    max_serial = max((int(line[6:11]) for line in protein_lines if line.startswith("ATOM")), default=0)
    serial_map: dict[int, int] = {}
    rewritten_ligand: list[str] = []
    for line in ligand_atom_lines:
        old_serial = int(line[6:11])
        new_serial = max_serial + len(serial_map) + 1
        serial_map[old_serial] = new_serial
        rewritten_ligand.append(f"HETATM{new_serial:5d} {line[12:16]} {'LIG':>3s} L   1    {line[30:66]}{line[66:]}")
    rewritten_conect: list[str] = []
    for line in ligand_conect_lines:
        ids: list[int] = []
        for idx in range(6, len(line), 5):
            token = line[idx : idx + 5].strip()
            if token:
                ids.append(int(token))
        if ids and ids[0] in serial_map:
            mapped_neighbors = [serial_map[item] for item in ids[1:] if item in serial_map]
            if mapped_neighbors:
                rewritten_conect.append(
                    "CONECT%5d%s" % (serial_map[ids[0]], "".join(f"{item:5d}" for item in mapped_neighbors))
                )
    out_path.write_text("\n".join([*protein_lines, *rewritten_ligand, *rewritten_conect, "END", ""]), encoding="utf-8")
    return {
        "path": _artifact(out_path),
        "protein_atom_line_count": sum(1 for line in protein_lines if line.startswith("ATOM")),
        "ligand_atom_line_count": len(rewritten_ligand),
        "ligand_conect_line_count": len(rewritten_conect),
    }


def _probe_protein_parameterization(protein_pdb: str, *, attempt_build: bool) -> dict[str, Any]:
    if not protein_pdb:
        return {"attempted": False, "ready": False, "error": "protein_structure_source_path_missing"}
    path = _resolve(protein_pdb)
    if not path.exists():
        return {"attempted": False, "ready": False, "path": _artifact(path), "error": "protein_pdb_not_found"}
    if not attempt_build:
        return {"attempted": False, "ready": False, "path": _artifact(path), "error": "build_attempt_disabled"}
    try:
        from openmm.app import ForceField, Modeller, NoCutoff, PDBFile  # type: ignore

        pdb = PDBFile(str(path))
        forcefield = ForceField("amber14-all.xml")
        raw_probe: dict[str, Any]
        try:
            system = forcefield.createSystem(pdb.topology, nonbondedMethod=NoCutoff, constraints=None)
            raw_probe = {"ready": True, "particle_count": system.getNumParticles()}
        except Exception as exc:
            raw_probe = {"ready": False, "error": _short_error(exc)}
        modeller = Modeller(pdb.topology, pdb.positions)
        try:
            modeller.addHydrogens(forcefield, pH=7.4)
            system = forcefield.createSystem(modeller.topology, nonbondedMethod=NoCutoff, constraints=None)
            return {
                "attempted": True,
                "ready": True,
                "path": _artifact(path),
                "raw_create_system": raw_probe,
                "repair_method": "openmm_modeller_addHydrogens",
                "particle_count": system.getNumParticles(),
                "force_count": system.getNumForces(),
            }
        except Exception as exc:
            return {
                "attempted": True,
                "ready": False,
                "path": _artifact(path),
                "raw_create_system": raw_probe,
                "repair_method": "openmm_modeller_addHydrogens",
                "error": _short_error(exc),
            }
    except Exception as exc:
        return {"attempted": True, "ready": False, "path": _artifact(path), "error": _short_error(exc)}


def _probe_ligand_template(
    ligand_pdb: str,
    *,
    gaff_xml: str | Path,
    ambertools_home: str | Path,
    ligand_charge: int,
    attempt_build: bool,
    timeout_sec: int,
) -> dict[str, Any]:
    if not ligand_pdb:
        return {"attempted": False, "ready": False, "error": "backmapped_pdb_missing"}
    ligand_path = _resolve(ligand_pdb)
    gaff_path = _resolve(gaff_xml)
    amber_home = _resolve(ambertools_home)
    antechamber = amber_home / "bin" / "antechamber"
    if not ligand_path.exists():
        return {"attempted": False, "ready": False, "path": _artifact(ligand_path), "error": "ligand_pdb_not_found"}
    if not gaff_path.exists():
        return {"attempted": False, "ready": False, "gaff_xml": _artifact(gaff_path), "error": "gaff_xml_not_found"}
    if not antechamber.exists():
        return {"attempted": False, "ready": False, "antechamber": _artifact(antechamber), "error": "antechamber_not_found"}
    if not attempt_build:
        return {"attempted": False, "ready": False, "path": _artifact(ligand_path), "error": "build_attempt_disabled"}
    try:
        from openmm.app import ForceField, NoCutoff, PDBFile  # type: ignore

        with tempfile.TemporaryDirectory(prefix="drd2_ligand_ff_") as tmp:
            tmp_path = Path(tmp)
            mol2_path = tmp_path / "ligand.mol2"
            template_xml = tmp_path / "ligand_residue_template.xml"
            conect_pdb = tmp_path / "ligand_conect.pdb"
            env = os.environ.copy()
            env["AMBERHOME"] = str(amber_home)
            command = [
                str(antechamber),
                "-i",
                str(ligand_path),
                "-fi",
                "pdb",
                "-o",
                str(mol2_path),
                "-fo",
                "mol2",
                "-c",
                "bcc",
                "-s",
                "0",
                "-nc",
                str(int(ligand_charge)),
            ]
            result = subprocess.run(
                command,
                cwd=str(tmp_path),
                env=env,
                text=True,
                capture_output=True,
                timeout=timeout_sec,
                check=False,
            )
            if result.returncode != 0 or not mol2_path.exists():
                return {
                    "attempted": True,
                    "ready": False,
                    "path": _artifact(ligand_path),
                    "antechamber": _artifact(antechamber),
                    "antechamber_returncode": result.returncode,
                    "error": _short_error((result.stderr or result.stdout or "antechamber_failed").strip()),
                }
            atoms, bonds = _parse_mol2(mol2_path)
            if not atoms or not bonds:
                return {
                    "attempted": True,
                    "ready": False,
                    "path": _artifact(ligand_path),
                    "antechamber_returncode": result.returncode,
                    "error": "mol2_atoms_or_bonds_missing",
                }
            _write_ligand_template_xml(template_xml, atoms, bonds)
            _write_pdb_with_conect(ligand_path, conect_pdb, bonds)
            pdb = PDBFile(str(conect_pdb))
            forcefield = ForceField(str(gaff_path), str(template_xml))
            system = forcefield.createSystem(pdb.topology, nonbondedMethod=NoCutoff, constraints=None)
            return {
                "attempted": True,
                "ready": True,
                "claim_grade": False,
                "claim_scope": "ligand_only_gaff_template_probe_not_full_protein_ligand_forcefield",
                "path": _artifact(ligand_path),
                "gaff_xml": _artifact(gaff_path),
                "antechamber": _artifact(antechamber),
                "antechamber_returncode": result.returncode,
                "ligand_charge": int(ligand_charge),
                "mol2_atom_count": len(atoms),
                "mol2_bond_count": len(bonds),
                "openmm_bond_count": sum(1 for _ in pdb.topology.bonds()),
                "particle_count": system.getNumParticles(),
                "force_count": system.getNumForces(),
            }
    except Exception as exc:
        return {"attempted": True, "ready": False, "path": _artifact(ligand_path), "error": _short_error(exc)}


def _probe_integrated_complex_parameterization(
    protein_pdb: str,
    ligand_pdb: str,
    *,
    gaff_xml: str | Path,
    ambertools_home: str | Path,
    ligand_charge: int,
    attempt_build: bool,
    timeout_sec: int,
    out_complex_pdb: str | Path,
    out_template_xml: str | Path,
) -> dict[str, Any]:
    if not protein_pdb or not ligand_pdb:
        return {"attempted": False, "ready": False, "error": "protein_or_ligand_path_missing"}
    protein_path = _resolve(protein_pdb)
    ligand_path = _resolve(ligand_pdb)
    gaff_path = _resolve(gaff_xml)
    amber_home = _resolve(ambertools_home)
    antechamber = amber_home / "bin" / "antechamber"
    template_xml = _resolve(out_template_xml)
    complex_pdb = _resolve(out_complex_pdb)
    if not protein_path.exists():
        return {"attempted": False, "ready": False, "protein_pdb": _artifact(protein_path), "error": "protein_pdb_not_found"}
    if not ligand_path.exists():
        return {"attempted": False, "ready": False, "ligand_pdb": _artifact(ligand_path), "error": "ligand_pdb_not_found"}
    if not gaff_path.exists() or not antechamber.exists():
        return {
            "attempted": False,
            "ready": False,
            "gaff_xml": _artifact(gaff_path),
            "antechamber": _artifact(antechamber),
            "error": "gaff_or_antechamber_not_found",
        }
    if not attempt_build:
        return {"attempted": False, "ready": False, "error": "build_attempt_disabled"}
    try:
        from openmm.app import ForceField, Modeller, NoCutoff, PDBFile  # type: ignore

        with tempfile.TemporaryDirectory(prefix="drd2_integrated_ff_") as tmp:
            tmp_path = Path(tmp)
            mol2_path = tmp_path / "ligand.mol2"
            ligand_conect_pdb = tmp_path / "ligand_conect.pdb"
            env = os.environ.copy()
            env["AMBERHOME"] = str(amber_home)
            result = subprocess.run(
                [
                    str(antechamber),
                    "-i",
                    str(ligand_path),
                    "-fi",
                    "pdb",
                    "-o",
                    str(mol2_path),
                    "-fo",
                    "mol2",
                    "-c",
                    "bcc",
                    "-s",
                    "0",
                    "-nc",
                    str(int(ligand_charge)),
                ],
                cwd=str(tmp_path),
                env=env,
                text=True,
                capture_output=True,
                timeout=timeout_sec,
                check=False,
            )
            if result.returncode != 0 or not mol2_path.exists():
                return {
                    "attempted": True,
                    "ready": False,
                    "antechamber_returncode": result.returncode,
                    "error": _short_error((result.stderr or result.stdout or "antechamber_failed").strip()),
                }
            atoms, bonds = _parse_mol2(mol2_path)
            if not atoms or not bonds:
                return {"attempted": True, "ready": False, "error": "mol2_atoms_or_bonds_missing"}
            template_xml.parent.mkdir(parents=True, exist_ok=True)
            _write_ligand_template_xml(template_xml, atoms, bonds)
            _write_pdb_with_conect(ligand_path, ligand_conect_pdb, bonds)
            complex_info = _write_integrated_complex_pdb(protein_path, ligand_conect_pdb, complex_pdb)
            pdb = PDBFile(str(complex_pdb))
            forcefield = ForceField("amber14-all.xml", str(gaff_path), str(template_xml))
            modeller = Modeller(pdb.topology, pdb.positions)
            modeller.addHydrogens(forcefield, pH=7.4)
            system = forcefield.createSystem(modeller.topology, nonbondedMethod=NoCutoff, constraints=None)
            return {
                "attempted": True,
                "ready": True,
                "claim_scope": "integrated_protein_ligand_openmm_system_parameterized_not_minimized",
                "protein_pdb": _artifact(protein_path),
                "ligand_pdb": _artifact(ligand_path),
                "complex_pdb": _artifact(complex_pdb),
                "ligand_template_xml": _artifact(template_xml),
                "gaff_xml": _artifact(gaff_path),
                "antechamber": _artifact(antechamber),
                "antechamber_returncode": result.returncode,
                "ligand_charge": int(ligand_charge),
                "mol2_atom_count": len(atoms),
                "mol2_bond_count": len(bonds),
                "input_atom_count": sum(1 for _ in pdb.topology.atoms()),
                "input_residue_count": sum(1 for _ in pdb.topology.residues()),
                "hydrogenated_atom_count": sum(1 for _ in modeller.topology.atoms()),
                "particle_count": system.getNumParticles(),
                "force_count": system.getNumForces(),
                **complex_info,
            }
    except Exception as exc:
        return {
            "attempted": True,
            "ready": False,
            "protein_pdb": _artifact(protein_path),
            "ligand_pdb": _artifact(ligand_path),
            "error": _short_error(exc),
        }


def build_probe(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    target: str = DEFAULT_TARGET,
    ligand_id: str = DEFAULT_POSITIVE_LIGAND,
    ligand_charge: int = DEFAULT_LIGAND_CHARGE,
    attempt_build: bool = True,
    gaff_xml: str | Path = CHIMERAX_GAFF_XML,
    ambertools_home: str | Path = CHIMERAX_AMBERTOOLS_HOME,
    prepared_protein_pdb: str | Path | None = None,
    out_complex_pdb: str | Path = DEFAULT_INTEGRATED_COMPLEX_PDB,
    out_template_xml: str | Path = DEFAULT_LIGAND_TEMPLATE_XML,
    timeout_sec: int = 60,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    rows = _read_csv(input_csv)
    positive = _find_positive(rows, target, ligand_id)
    openmm_available = _module_available("openmm")
    rdkit_available = _module_available("rdkit")
    raw_protein_pdb = _text(positive.get("protein_structure_source_path")) if positive else ""
    prepared_path = _resolve(prepared_protein_pdb) if prepared_protein_pdb else None
    active_protein_pdb = str(prepared_path) if prepared_path is not None and prepared_path.exists() else raw_protein_pdb
    target_probe = {
        "target": _text(positive.get("target")) if positive else target,
        "ligand_id": _text(positive.get("ligand_id")) if positive else ligand_id,
        "row_found": positive is not None,
        "protein_structure_source_path": _artifact(raw_protein_pdb) if raw_protein_pdb else "",
        "active_protein_pdb": _artifact(active_protein_pdb) if active_protein_pdb else "",
        "prepared_protein_pdb": _artifact(prepared_path) if prepared_path is not None and prepared_path.exists() else "",
        "backmapped_pdb": _artifact(positive.get("backmapped_pdb", "")) if positive else "",
        "ligand_smiles": _text(positive.get("ligand_smiles")) if positive else "",
    }
    if positive and openmm_available:
        protein_probe = _probe_protein_parameterization(
            active_protein_pdb,
            attempt_build=attempt_build,
        )
        ligand_probe = _probe_ligand_template(
            _text(positive.get("backmapped_pdb")),
            gaff_xml=gaff_xml,
            ambertools_home=ambertools_home,
            ligand_charge=ligand_charge,
            attempt_build=attempt_build,
            timeout_sec=timeout_sec,
        )
        integrated_probe = _probe_integrated_complex_parameterization(
            active_protein_pdb,
            _text(positive.get("backmapped_pdb")),
            gaff_xml=gaff_xml,
            ambertools_home=ambertools_home,
            ligand_charge=ligand_charge,
            attempt_build=attempt_build,
            timeout_sec=timeout_sec,
            out_complex_pdb=out_complex_pdb,
            out_template_xml=out_template_xml,
        )
    else:
        reason = "openmm_missing" if not openmm_available else "positive_row_missing"
        protein_probe = {"attempted": False, "ready": False, "error": reason}
        ligand_probe = {"attempted": False, "ready": False, "error": reason}
        integrated_probe = {"attempted": False, "ready": False, "error": reason}

    protein_ready = bool(protein_probe.get("ready"))
    ligand_ready = bool(ligand_probe.get("ready"))
    integrated_ready = bool(integrated_probe.get("ready"))
    claim_ready = integrated_ready
    blockers: list[str] = []
    if positive is None:
        blockers.append("drd2_positive_repair_row_missing")
    if not openmm_available:
        blockers.append("openmm_missing")
    if not protein_ready:
        blockers.append("protein_amber14_parameterization_unavailable")
    if not ligand_ready:
        blockers.append("ligand_gaff_template_parameterization_unavailable")
    if ligand_ready and not integrated_ready:
        blockers.append("ligand_probe_is_ligand_only_not_full_complex")
    if protein_ready and ligand_ready and not integrated_ready:
        blockers.append("integrated_protein_ligand_system_not_parameterized")
    if not integrated_ready and not (_resolve(ambertools_home) / "bin" / "tleap").exists():
        blockers.append("ambertools_tleap_missing")
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "integrated_protein_ligand_parameterization_ready" if claim_ready else "blocked_full_protein_ligand_parameterization",
        "claim_grade_parameterization_ready": claim_ready,
        "local_probe_partial": bool((ligand_ready or protein_ready) and not integrated_ready),
        "openmm_available": openmm_available,
        "rdkit_available": rdkit_available,
        "protein_parameterization_available": protein_ready,
        "ligand_template_parameterization_available": ligand_ready,
        "integrated_system_parameterization_available": integrated_ready,
        "blockers": blockers,
        "claim_scope": (
            "integrated_protein_ligand_openmm_system_parameterized_not_minimized"
            if claim_ready
            else "blocked_probe_ligand_template_may_be_available_but_full_complex_is_not_claim_grade"
        ),
        "next_required_step": (
            "Run full-forcefield DRD2 local-minimization survival using the integrated OpenMM parameterization "
            "artifact before promoting hard-decoy rebuild evidence."
            if claim_ready
            else "Keep the ligand GAFF/template probe as partial evidence only. Repair/protonate the DRD2 protein so "
            "OpenMM amber14 can parameterize it, then build one integrated protein-ligand OpenMM System before "
            "promoting local-min survival or hard-decoy rebuild evidence."
        ),
    }
    return {
        "packet_type": "gpcr_drd2_openmm_forcefield_parameterization_probe",
        "summary": summary,
        "target_probe": target_probe,
        "capability_probes": {
            "protein_amber14_openmm": protein_probe,
            "ligand_gaff_template_openmm": ligand_probe,
            "integrated_protein_ligand_openmm": integrated_probe,
        },
        "claim_boundary": {
            "claim_promotion_allowed": claim_ready,
            "hard_decoy_rebuild_allowed": False,
            "guarded_100k_rerun_allowed": False,
            "ligand_only_probe_is_not_claim_grade": True,
            "integrated_parameterization_is_not_minimization_survival": True,
            "fake_pass_allowed": False,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    probes = payload["capability_probes"]
    lines = [
        "# GPCR DRD2 OpenMM Forcefield Parameterization Probe",
        "",
        "## Summary",
    ]
    for key in (
        "status",
        "claim_grade_parameterization_ready",
        "local_probe_partial",
        "protein_parameterization_available",
        "ligand_template_parameterization_available",
        "integrated_system_parameterization_available",
        "blockers",
        "claim_scope",
        "next_required_step",
    ):
        lines.append(f"- {key}: `{summary[key]}`")
    lines.extend(
        [
            "",
            "## Target Probe",
            f"- target: `{payload['target_probe']['target']}`",
            f"- ligand_id: `{payload['target_probe']['ligand_id']}`",
            f"- protein_structure_source_path: `{payload['target_probe']['protein_structure_source_path']}`",
            f"- active_protein_pdb: `{payload['target_probe']['active_protein_pdb']}`",
            f"- prepared_protein_pdb: `{payload['target_probe']['prepared_protein_pdb']}`",
            f"- backmapped_pdb: `{payload['target_probe']['backmapped_pdb']}`",
            "",
            "## Capability Probes",
            f"- protein_amber14_openmm: `{probes['protein_amber14_openmm']}`",
            f"- ligand_gaff_template_openmm: `{probes['ligand_gaff_template_openmm']}`",
            f"- integrated_protein_ligand_openmm: `{probes['integrated_protein_ligand_openmm']}`",
            "",
            "## Claim Boundary",
            "- Ligand-only GAFF/OpenMM template success is partial diagnostic evidence only.",
            "- A commercial/OpenMM-class local-min claim requires an integrated protein-ligand OpenMM System.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(payload: dict[str, Any], out_json: str | Path, out_md: str | Path) -> None:
    _write_json(out_json, payload)
    path = _resolve(out_md)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(payload), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe DRD2 OpenMM protein-ligand forcefield parameterization.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--ligand-id", default=DEFAULT_POSITIVE_LIGAND)
    parser.add_argument("--ligand-charge", type=int, default=DEFAULT_LIGAND_CHARGE)
    parser.add_argument("--gaff-xml", default=CHIMERAX_GAFF_XML)
    parser.add_argument("--ambertools-home", default=CHIMERAX_AMBERTOOLS_HOME)
    parser.add_argument("--prepared-protein-pdb", default=DEFAULT_PREPARED_PROTEIN_PDB)
    parser.add_argument("--out-complex-pdb", default=DEFAULT_INTEGRATED_COMPLEX_PDB)
    parser.add_argument("--out-template-xml", default=DEFAULT_LIGAND_TEMPLATE_XML)
    parser.add_argument("--timeout-sec", type=int, default=60)
    parser.add_argument("--no-attempt-build", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_probe(
        input_csv=args.input_csv,
        target=args.target,
        ligand_id=args.ligand_id,
        ligand_charge=args.ligand_charge,
        gaff_xml=args.gaff_xml,
        ambertools_home=args.ambertools_home,
        prepared_protein_pdb=args.prepared_protein_pdb,
        out_complex_pdb=args.out_complex_pdb,
        out_template_xml=args.out_template_xml,
        timeout_sec=args.timeout_sec,
        attempt_build=not args.no_attempt_build,
    )
    write_outputs(payload, args.out_json, args.out_md)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
