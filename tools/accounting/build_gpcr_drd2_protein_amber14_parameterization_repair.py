#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import subprocess
from collections import Counter
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
DEFAULT_OUT_JSON = "runs/gpcr_drd2_protein_amber14_parameterization_repair_current.json"
DEFAULT_OUT_MD = "runs/gpcr_drd2_protein_amber14_parameterization_repair_current.md"
DEFAULT_TARGET = "CHEMBL217_DRD2_HUMAN"
DEFAULT_POSITIVE_LIGAND = "CHEMBL301265"
DEFAULT_CHIMERAX_EXE = "tools/bin/chimerax/local_unpack/usr/bin/chimerax"
DEFAULT_CONSERVATIVE_REPAIR_PDB = "runs/gpcr_drd2_6cm4_chimerax_sidechain_rebuilt_split_oxt_current.pdb"
DEFAULT_CHIMERAX_RAW_REPAIR_PDB = "runs/gpcr_drd2_6cm4_chimerax_sidechain_rebuilt_raw_current.pdb"

STANDARD_HEAVY_ATOMS: dict[str, set[str]] = {
    "ALA": {"N", "CA", "C", "O", "CB"},
    "ARG": {"N", "CA", "C", "O", "CB", "CG", "CD", "NE", "CZ", "NH1", "NH2"},
    "ASN": {"N", "CA", "C", "O", "CB", "CG", "OD1", "ND2"},
    "ASP": {"N", "CA", "C", "O", "CB", "CG", "OD1", "OD2"},
    "CYS": {"N", "CA", "C", "O", "CB", "SG"},
    "GLN": {"N", "CA", "C", "O", "CB", "CG", "CD", "OE1", "NE2"},
    "GLU": {"N", "CA", "C", "O", "CB", "CG", "CD", "OE1", "OE2"},
    "GLY": {"N", "CA", "C", "O"},
    "HIS": {"N", "CA", "C", "O", "CB", "CG", "ND1", "CD2", "CE1", "NE2"},
    "ILE": {"N", "CA", "C", "O", "CB", "CG1", "CG2", "CD1"},
    "LEU": {"N", "CA", "C", "O", "CB", "CG", "CD1", "CD2"},
    "LYS": {"N", "CA", "C", "O", "CB", "CG", "CD", "CE", "NZ"},
    "MET": {"N", "CA", "C", "O", "CB", "CG", "SD", "CE"},
    "PHE": {"N", "CA", "C", "O", "CB", "CG", "CD1", "CD2", "CE1", "CE2", "CZ"},
    "PRO": {"N", "CA", "C", "O", "CB", "CG", "CD"},
    "SER": {"N", "CA", "C", "O", "CB", "OG"},
    "THR": {"N", "CA", "C", "O", "CB", "OG1", "CG2"},
    "TRP": {"N", "CA", "C", "O", "CB", "CG", "CD1", "CD2", "NE1", "CE2", "CE3", "CZ2", "CZ3", "CH2"},
    "TYR": {"N", "CA", "C", "O", "CB", "CG", "CD1", "CD2", "CE1", "CE2", "CZ", "OH"},
    "VAL": {"N", "CA", "C", "O", "CB", "CG1", "CG2"},
}


def _find_positive(rows: list[dict[str, str]], target: str, ligand_id: str) -> dict[str, str] | None:
    for row in rows:
        if _text(row.get("target")) == target and _text(row.get("ligand_id")) == ligand_id:
            return row
    for row in rows:
        if _truthy(row.get("is_positive")) or _text(row.get("ligand_id")) == ligand_id:
            return row
    return None


def _atom_record(line: str) -> tuple[str, str, str, str, str] | None:
    if not line.startswith(("ATOM  ", "HETATM")):
        return None
    atom = line[12:16].strip()
    residue = line[17:20].strip()
    chain = line[21].strip()
    resid = line[22:26].strip()
    icode = line[26].strip()
    if atom and residue in STANDARD_HEAVY_ATOMS and resid:
        return atom, residue, chain, resid, icode
    parts = line.split()
    if len(parts) >= 6:
        return parts[2], parts[3], parts[4], parts[5], ""
    return None


def _audit_missing_heavy_atoms(protein_pdb: str | Path) -> dict[str, Any]:
    path = _resolve(protein_pdb)
    residue_atoms: dict[tuple[str, str, str, str], set[str]] = {}
    atom_count = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parsed = _atom_record(line)
        if parsed is None or not line.startswith("ATOM"):
            continue
        atom, residue, chain, resid, icode = parsed
        if atom.startswith("H"):
            continue
        residue_atoms.setdefault((residue, chain, resid, icode), set()).add(atom)
        atom_count += 1
    missing_rows: list[dict[str, Any]] = []
    for (residue, chain, resid, icode), atoms in residue_atoms.items():
        expected = STANDARD_HEAVY_ATOMS.get(residue)
        if not expected:
            continue
        missing = sorted(expected - atoms)
        if missing:
            missing_rows.append(
                {
                    "residue_name": residue,
                    "chain_id": chain,
                    "residue_id": resid,
                    "insertion_code": icode,
                    "present_heavy_atom_count": len(atoms),
                    "expected_heavy_atom_count": len(expected),
                    "missing_heavy_atoms": missing,
                }
            )
    by_residue = Counter(row["residue_name"] for row in missing_rows)
    return {
        "protein_atom_count": atom_count,
        "protein_residue_count": len(residue_atoms),
        "missing_heavy_atom_residue_count": len(missing_rows),
        "incomplete_histidine_count": int(by_residue.get("HIS", 0)),
        "missing_heavy_atom_residue_histogram": dict(sorted(by_residue.items())),
        "missing_rows": missing_rows,
        "examples": missing_rows[:20],
    }


def _openmm_probe(protein_pdb: str | Path, *, attempt_build: bool = True) -> dict[str, Any]:
    path = _resolve(protein_pdb)
    if not path.exists():
        return {"attempted": False, "raw_ready": False, "add_hydrogens_ready": False, "error": "protein_pdb_missing"}
    if not attempt_build:
        return {"attempted": False, "raw_ready": False, "add_hydrogens_ready": False, "error": "build_attempt_disabled"}
    try:
        from openmm.app import ForceField, Modeller, NoCutoff, PDBFile  # type: ignore

        pdb = PDBFile(str(path))
        forcefield = ForceField("amber14-all.xml")
        raw: dict[str, Any]
        try:
            system = forcefield.createSystem(pdb.topology, nonbondedMethod=NoCutoff, constraints=None)
            raw = {"ready": True, "particle_count": system.getNumParticles(), "force_count": system.getNumForces()}
        except Exception as exc:
            raw = {"ready": False, "error": _short_error(exc)}
        try:
            modeller = Modeller(pdb.topology, pdb.positions)
            modeller.addHydrogens(forcefield, pH=7.4)
            system = forcefield.createSystem(modeller.topology, nonbondedMethod=NoCutoff, constraints=None)
            hyd = {"ready": True, "particle_count": system.getNumParticles(), "force_count": system.getNumForces()}
        except Exception as exc:
            hyd = {"ready": False, "error": _short_error(exc)}
        return {"attempted": True, "raw_create_system": raw, "add_hydrogens": hyd}
    except Exception as exc:
        return {"attempted": True, "raw_create_system": {"ready": False}, "add_hydrogens": {"ready": False}, "error": _short_error(exc)}


def _coord(line: str) -> tuple[float, float, float]:
    return (float(line[30:38]), float(line[38:46]), float(line[46:54]))


def _unit(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    norm = math.sqrt(sum(component * component for component in vector))
    if norm <= 1e-12:
        return (1.0, 0.0, 0.0)
    return tuple(component / norm for component in vector)  # type: ignore[return-value]


def _atom_name(line: str) -> str:
    return line[12:16].strip()


def _residue_key(line: str) -> tuple[str, str, str]:
    return (line[21].strip(), line[22:26].strip(), line[26].strip())


def _residue_int(line: str) -> int | None:
    try:
        return int(line[22:26])
    except ValueError:
        return None


def _format_atom_line(
    *,
    serial: int,
    atom_name: str,
    residue_name: str,
    chain_id: str,
    residue_id: int,
    insertion_code: str,
    x: float,
    y: float,
    z: float,
    element: str,
) -> str:
    return (
        f"ATOM  {serial:5d} {atom_name:>4s} {residue_name:>3s} {chain_id[:1] or ' '}{residue_id:4d}"
        f"{insertion_code[:1] or ' '}   {x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {element:>2s}"
    )


def _terminal_oxt_line(residue_lines: list[str], serial: int, chain_id: str) -> str | None:
    atoms = {_atom_name(line): line for line in residue_lines}
    if "OXT" in atoms or not {"CA", "C", "O"} <= set(atoms):
        return None
    cx, cy, cz = _coord(atoms["C"])
    ox, oy, oz = _coord(atoms["O"])
    direction = _unit((cx - ox, cy - oy, cz - oz))
    x = cx + direction[0] * 1.25
    y = cy + direction[1] * 1.25
    z = cz + direction[2] * 1.25
    base = atoms["C"]
    residue_id = _residue_int(base)
    if residue_id is None:
        return None
    return _format_atom_line(
        serial=serial,
        atom_name="OXT",
        residue_name=base[17:20].strip(),
        chain_id=chain_id,
        residue_id=residue_id,
        insertion_code=base[26].strip(),
        x=x,
        y=y,
        z=z,
        element="O",
    )


def _write_fragment_split_oxt_pdb(source_pdb: str | Path, out_pdb: str | Path) -> dict[str, Any]:
    source = _resolve(source_pdb)
    out = _resolve(out_pdb)
    out.parent.mkdir(parents=True, exist_ok=True)
    chain_ids = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    lines: list[str] = []
    current_residue_lines: list[str] = []
    previous_residue_id: int | None = None
    previous_residue_name = ""
    fragment_index = 0
    serial = 1
    ter_serial = 90000

    def flush_ter() -> None:
        nonlocal serial, ter_serial
        if not current_residue_lines or previous_residue_id is None:
            return
        chain_id = chain_ids[min(fragment_index, len(chain_ids) - 1)]
        oxt = _terminal_oxt_line(current_residue_lines, serial, chain_id)
        if oxt is not None:
            lines.append(oxt)
            serial += 1
        lines.append(f"TER   {ter_serial:5d}      {previous_residue_name:>3s} {chain_id}{previous_residue_id:4d}")
        ter_serial += 1

    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("ATOM"):
            continue
        residue_id = _residue_int(line)
        if residue_id is None:
            continue
        if current_residue_lines and _residue_key(line) != _residue_key(current_residue_lines[-1]):
            if previous_residue_id is not None and residue_id != previous_residue_id + 1:
                flush_ter()
                fragment_index += 1
            current_residue_lines = []
        chain_id = chain_ids[min(fragment_index, len(chain_ids) - 1)]
        lines.append(f"{line[:6]}{serial:5d}{line[11:21]}{chain_id}{line[22:]}")
        serial += 1
        current_residue_lines.append(line)
        previous_residue_id = residue_id
        previous_residue_name = line[17:20].strip()

    flush_ter()
    lines.append("END")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"path": _artifact(out), "fragment_count": fragment_index + 1, "atom_count": serial - 1}


def _chimerax_sidechain_rebuild_probe(
    protein_pdb: str | Path,
    audit: dict[str, Any],
    *,
    chimerax_exe: str | Path = DEFAULT_CHIMERAX_EXE,
    raw_out_pdb: str | Path = DEFAULT_CHIMERAX_RAW_REPAIR_PDB,
    out_pdb: str | Path = DEFAULT_CONSERVATIVE_REPAIR_PDB,
    timeout_sec: int = 240,
) -> dict[str, Any]:
    source = _resolve(protein_pdb)
    chimerax = _resolve(chimerax_exe)
    raw_out = _resolve(raw_out_pdb)
    final_out = _resolve(out_pdb)
    if not source.exists():
        return {"attempted": False, "ready": False, "error": "protein_pdb_missing"}
    if not chimerax.exists():
        return {"attempted": False, "ready": False, "error": "chimerax_executable_missing", "chimerax_exe": _artifact(chimerax)}
    missing_rows = audit.get("missing_rows", [])
    if not isinstance(missing_rows, list):
        missing_rows = []
    raw_out.parent.mkdir(parents=True, exist_ok=True)
    command = [str(chimerax), "--nogui", "--exit", "--cmd", f"open {source}"]
    for row in missing_rows:
        if not isinstance(row, dict):
            continue
        chain = _text(row.get("chain_id"))
        resid = _text(row.get("residue_id"))
        if not resid:
            continue
        selector = f"/{chain}:{resid}" if chain else f":{resid}"
        command.extend(["--cmd", f"swapaa {selector} same rotLib Dunbrack"])
    command.extend(["--cmd", "select protein", "--cmd", f"save {raw_out} models #1 selectedOnly true"])
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout_sec, check=False)
    if result.returncode != 0 or not raw_out.exists():
        return {
            "attempted": True,
            "ready": False,
            "chimerax_exe": _artifact(chimerax),
            "returncode": result.returncode,
            "error": _short_error((result.stderr or result.stdout or "chimerax_rebuild_failed").strip()),
        }
    split = _write_fragment_split_oxt_pdb(raw_out, final_out)
    repaired_audit = _audit_missing_heavy_atoms(final_out)
    openmm_probe = _openmm_probe(final_out, attempt_build=True)
    ready = bool((openmm_probe.get("add_hydrogens") or {}).get("ready")) and int(
        repaired_audit.get("missing_heavy_atom_residue_count") or 0
    ) == 0
    return {
        "attempted": True,
        "ready": ready,
        "method": "chimerax_swapaa_same_rotamer_fragment_split_oxt",
        "chimerax_exe": _artifact(chimerax),
        "raw_repair_pdb": _artifact(raw_out),
        "repaired_protein_pdb": _artifact(final_out),
        "repaired_fragment_count": split["fragment_count"],
        "repaired_atom_count": split["atom_count"],
        "raw_missing_heavy_atom_residue_count": int(audit.get("missing_heavy_atom_residue_count") or 0),
        "repaired_missing_heavy_atom_residue_count": int(repaired_audit.get("missing_heavy_atom_residue_count") or 0),
        "repaired_incomplete_histidine_count": int(repaired_audit.get("incomplete_histidine_count") or 0),
        "openmm_probe": openmm_probe,
    }


def build_repair_packet(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    target: str = DEFAULT_TARGET,
    ligand_id: str = DEFAULT_POSITIVE_LIGAND,
    attempt_build: bool = True,
    attempt_conservative_repair: bool = True,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    positive = _find_positive(_read_csv(input_csv), target, ligand_id)
    protein_pdb = _text(positive.get("protein_structure_source_path")) if positive else ""
    audit = _audit_missing_heavy_atoms(protein_pdb) if protein_pdb and _resolve(protein_pdb).exists() else {}
    probe = _openmm_probe(protein_pdb, attempt_build=attempt_build) if protein_pdb else {
        "attempted": False,
        "raw_create_system": {"ready": False, "error": "protein_path_missing"},
        "add_hydrogens": {"ready": False, "error": "protein_path_missing"},
    }
    raw_ready = bool((probe.get("raw_create_system") or {}).get("ready"))
    hyd_ready = bool((probe.get("add_hydrogens") or {}).get("ready"))
    missing_count = int(audit.get("missing_heavy_atom_residue_count") or 0)
    conservative = (
        _chimerax_sidechain_rebuild_probe(protein_pdb, audit)
        if protein_pdb and attempt_build and attempt_conservative_repair and _resolve(protein_pdb).exists()
        else {"attempted": False, "ready": False, "error": "conservative_repair_disabled"}
    )
    conservative_ready = bool(conservative.get("ready"))
    active_missing_count = (
        int(conservative.get("repaired_missing_heavy_atom_residue_count") or 0) if conservative_ready else missing_count
    )
    protein_ready = (hyd_ready and missing_count == 0) or conservative_ready
    claim_allowed = bool(protein_ready)
    blockers: list[str] = []
    if not positive:
        blockers.append("drd2_positive_row_missing")
    if not protein_pdb:
        blockers.append("protein_structure_source_path_missing")
    if missing_count > 0 and not conservative_ready:
        blockers.append("missing_heavy_atom_residues_present")
    if int(audit.get("incomplete_histidine_count") or 0) > 0 and not conservative_ready:
        blockers.append("incomplete_histidine_residues_present")
    if not raw_ready and not conservative_ready:
        blockers.append("raw_openmm_create_system_failed")
    if not hyd_ready and not conservative_ready:
        blockers.append("openmm_add_hydrogens_or_create_system_failed")
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "protein_amber14_parameterization_ready" if protein_ready else "blocked_protein_amber14_parameterization",
        "protein_parameterization_ready": protein_ready,
        "claim_grade_repair_allowed": claim_allowed,
        "protein_pdb": _artifact(protein_pdb),
        "raw_missing_heavy_atom_residue_count": missing_count,
        "missing_heavy_atom_residue_count": active_missing_count,
        "incomplete_histidine_count": int(audit.get("incomplete_histidine_count") or 0),
        "raw_openmm_create_system_ready": raw_ready,
        "add_hydrogens_ready": hyd_ready,
        "conservative_repair_attempted": bool(conservative.get("attempted")),
        "conservative_repair_ready": conservative_ready,
        "conservative_repair_pdb": _text(conservative.get("repaired_protein_pdb")),
        "conservative_repair_fragment_count": conservative.get("repaired_fragment_count"),
        "conservative_repair_add_hydrogens_ready": bool(
            ((conservative.get("openmm_probe") or {}).get("add_hydrogens") or {}).get("ready")
        ),
        "blockers": blockers,
        "next_required_step": (
            "Use the conservative repaired DRD2 receptor artifact for the next integrated protein-ligand OpenMM "
            "parameterization probe. This still does not authorize commercial claims until full-forcefield "
            "local-minimization survival and hard-decoy separation pass."
            if protein_ready
            else "Use an authoritative prepared DRD2 receptor or a chemistry-preserving missing-heavy-atom rebuild "
            "pipeline before full-forcefield local minimization. Deleting or mutating incomplete residues may be "
            "useful as a non-claim diagnostic, but it must not open commercial/OpenMM-class claims."
        ),
    }
    return {
        "packet_type": "gpcr_drd2_protein_amber14_parameterization_repair",
        "summary": summary,
        "target_probe": {
            "target": _text(positive.get("target")) if positive else target,
            "ligand_id": _text(positive.get("ligand_id")) if positive else ligand_id,
            "row_found": positive is not None,
        },
        "missing_heavy_atom_audit": audit,
        "openmm_probe": probe,
        "conservative_repair_probe": conservative,
        "claim_boundary": {
            "claim_promotion_allowed": claim_allowed,
            "deletion_or_mutation_repair_claim_grade_allowed": False,
            "commercial_claim_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    audit = payload.get("missing_heavy_atom_audit", {})
    lines = [
        "# GPCR DRD2 Protein Amber14 Parameterization Repair",
        "",
        "## Summary",
    ]
    for key in (
        "status",
        "protein_parameterization_ready",
        "claim_grade_repair_allowed",
        "missing_heavy_atom_residue_count",
        "incomplete_histidine_count",
        "raw_openmm_create_system_ready",
        "add_hydrogens_ready",
        "conservative_repair_attempted",
        "conservative_repair_ready",
        "conservative_repair_pdb",
        "conservative_repair_fragment_count",
        "conservative_repair_add_hydrogens_ready",
        "blockers",
        "next_required_step",
    ):
        lines.append(f"- {key}: `{summary[key]}`")
    lines.extend(["", "## Missing Heavy Atom Examples", ""])
    for row in audit.get("examples", [])[:10]:
        lines.append(
            f"- `{row['residue_name']} {row['chain_id']}{row['residue_id']}` missing `{','.join(row['missing_heavy_atoms'])}`"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "- This packet does not authorize DRD2 hard-decoy rebuild or OpenMM-class claims unless claim-grade repair is true.",
            "- Residue deletion, mutation, or pocket chemistry loss is non-claim diagnostic evidence only.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit DRD2 protein Amber14/OpenMM parameterization blockers.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--ligand-id", default=DEFAULT_POSITIVE_LIGAND)
    parser.add_argument("--no-attempt-build", action="store_true")
    parser.add_argument("--no-conservative-repair", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_repair_packet(
        input_csv=args.input_csv,
        target=args.target,
        ligand_id=args.ligand_id,
        attempt_build=not args.no_attempt_build,
        attempt_conservative_repair=not args.no_conservative_repair,
    )
    _write_json(args.out_json, payload)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
