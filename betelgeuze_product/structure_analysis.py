from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from core.structure_metrics import parse_pdb_atoms_with_coords
from core.structure_metrics_external import evaluate_structure_quality_with_external
from betelgeuze_product.legacy_input_contract import (
    LegacyInputContractError,
    LegacyInputPolicy,
    resolve_legacy_input_policy,
    strict_coordinate,
)

CLAIM_BOUNDARY = (
    "Local molecular-structure analysis only; it parses supplied PDB/mmCIF content or local files to summarize "
    "atoms, chains, residues, waters, and ligand-like HETATM residues. It does not fetch PDB entries, run docking, "
    "predict structures, emit benchmark claims, upload data, or mutate external state."
)

WATER_RESNAMES = {"HOH", "WAT", "H2O", "DOD"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _source(payload: dict[str, Any]) -> tuple[str, str]:
    for key in ("pdb_content", "pdb_path", "mmcif_content", "mmcif_path", "pdb_id"):
        value = _text(payload.get(key))
        if value:
            return key, value
    return "", ""


def _read_source_text(kind: str, value: str, root: str | Path) -> tuple[str, bool, list[dict[str, str]]]:
    if kind in {"pdb_content", "mmcif_content"}:
        return value, True, []
    if kind in {"pdb_path", "mmcif_path"}:
        path = Path(value)
        if not path.is_absolute():
            path = Path(root) / path
        if not path.is_file():
            return "", False, [_blocker("structure_file_missing", f"Structure file is missing: {path}")]
        try:
            return path.read_text(encoding="utf-8", errors="ignore"), True, []
        except OSError as exc:
            return "", False, [_blocker("structure_file_unreadable", f"Structure file could not be read: {exc}")]
    if kind == "pdb_id":
        return "", False, []
    return "", False, [_blocker("structure_source_missing", "Provide pdb_content, pdb_path, mmcif_content, mmcif_path, or pdb_id.")]


def _element_from_atom_name(atom_name: str) -> str:
    letters = "".join(ch for ch in atom_name if ch.isalpha())
    return letters[:1].upper()


def _parse_pdb(text: str) -> list[dict[str, str]]:
    atoms: list[dict[str, str]] = []
    for line in text.splitlines():
        record = line[:6].strip().upper()
        if record not in {"ATOM", "HETATM"}:
            continue
        atom_name = line[12:16].strip() if len(line) >= 16 else ""
        resname = (line[17:20].strip() if len(line) >= 20 else "") or "UNK"
        chain_id = (line[21:22].strip() if len(line) >= 22 else "") or "_"
        resseq = (line[22:26].strip() if len(line) >= 26 else "") or "0"
        icode = line[26:27].strip() if len(line) >= 27 else ""
        element = (line[76:78].strip() if len(line) >= 78 else "") or _element_from_atom_name(atom_name)
        atoms.append(
            {
                "record": record,
                "atom_name": atom_name,
                "resname": resname.upper(),
                "chain_id": chain_id,
                "residue_id": f"{resseq}{icode}",
                "element": element.upper(),
            }
        )
    return atoms


def _split_mmcif_line(line: str) -> list[str]:
    try:
        return shlex.split(line)
    except ValueError:
        return line.split()


def _parse_mmcif(text: str) -> list[dict[str, Any]]:
    return _parse_mmcif_with_policy(text, policy=LegacyInputPolicy(compatibility_mode=True))


def _parse_mmcif_with_policy(text: str, *, policy: LegacyInputPolicy) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = []
    headers: list[str] = []
    in_atom_loop = False
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            if in_atom_loop and headers:
                in_atom_loop = False
                headers = []
            continue
        if line == "loop_":
            in_atom_loop = False
            headers = []
            continue
        if line.startswith("_atom_site."):
            in_atom_loop = True
            headers.append(line)
            continue
        if not in_atom_loop or not headers:
            continue
        fields = _split_mmcif_line(line)
        if len(fields) < len(headers):
            continue
        values = dict(zip(headers, fields))
        record = _text(values.get("_atom_site.group_PDB")).upper()
        if record not in {"ATOM", "HETATM"}:
            continue
        resname = _text(values.get("_atom_site.auth_comp_id") or values.get("_atom_site.label_comp_id") or "UNK").upper()
        chain_id = _text(values.get("_atom_site.auth_asym_id") or values.get("_atom_site.label_asym_id") or "_")
        residue_id = _text(values.get("_atom_site.auth_seq_id") or values.get("_atom_site.label_seq_id") or "0")
        atom: dict[str, Any] = {
            "record": record,
            "atom_name": _text(values.get("_atom_site.auth_atom_id") or values.get("_atom_site.label_atom_id")),
            "resname": resname,
            "chain_id": chain_id,
            "residue_id": residue_id,
            "element": _text(values.get("_atom_site.type_symbol")).upper(),
        }
        columns = [
            _text(values.get("_atom_site.Cartn_x")),
            _text(values.get("_atom_site.Cartn_y")),
            _text(values.get("_atom_site.Cartn_z")),
        ]
        coordinates_declared = all(
            f"_atom_site.Cartn_{axis}" in headers for axis in ("x", "y", "z")
        )
        # A file that never declares Cartn_* columns is a coordinate-free
        # mmCIF, not a malformed coordinate. Only a declared-but-unparseable
        # coordinate is the fail-closed case.
        if coordinates_declared:
            coordinate = strict_coordinate(
                columns,
                field=f"mmcif_atom_xyz(line={line_number})",
                policy=policy,
            )
            if coordinate is not None:
                atom["xyz"] = [coordinate[0], coordinate[1], coordinate[2]]
        atoms.append(atom)
    return atoms


def _summarize_atoms(atoms: list[dict[str, Any]]) -> dict[str, Any]:
    residue_keys = {(atom["chain_id"], atom["resname"], atom["residue_id"]) for atom in atoms}
    polymer_residues = {
        (atom["chain_id"], atom["resname"], atom["residue_id"])
        for atom in atoms
        if atom["record"] == "ATOM"
    }
    hetatm_residues = {
        (atom["chain_id"], atom["resname"], atom["residue_id"])
        for atom in atoms
        if atom["record"] == "HETATM"
    }
    water_residues = {key for key in hetatm_residues if key[1] in WATER_RESNAMES}
    ligand_like = sorted(hetatm_residues - water_residues)
    chains = sorted({atom["chain_id"] for atom in atoms})
    elements = sorted({atom["element"] for atom in atoms if atom["element"]})
    return {
        "atom_count": len(atoms),
        "polymer_atom_count": sum(1 for atom in atoms if atom["record"] == "ATOM"),
        "hetatm_count": sum(1 for atom in atoms if atom["record"] == "HETATM"),
        "chain_count": len(chains),
        "chains": chains,
        "residue_count": len(residue_keys),
        "polymer_residue_count": len(polymer_residues),
        "hetatm_residue_count": len(hetatm_residues),
        "water_residue_count": len(water_residues),
        "ligand_like_residue_count": len(ligand_like),
        "ligand_like_residues": [
            {"chain_id": chain_id, "resname": resname, "residue_id": residue_id}
            for chain_id, resname, residue_id in ligand_like[:50]
        ],
        "element_count": len(elements),
        "elements": elements,
    }


def analyze_structure_source(
    payload: dict[str, Any],
    *,
    root: str | Path = ".",
    legacy_input_compatibility_mode: bool | None = None,
) -> dict[str, Any]:
    policy = resolve_legacy_input_policy(compatibility_mode=legacy_input_compatibility_mode)
    source_kind, source_value = _source(payload)
    source_text, source_available, blockers = _read_source_text(source_kind, source_value, root)
    parser = ""
    atoms: list[dict[str, Any]] = []
    if source_text:
        parser = "mmcif" if source_kind.startswith("mmcif") else "pdb"
        try:
            if parser == "pdb":
                atoms = parse_pdb_atoms_with_coords(source_text, policy=policy)
            else:
                atoms = _parse_mmcif_with_policy(source_text, policy=policy)
        except LegacyInputContractError as exc:
            atoms = []
            blockers.append(_blocker(exc.reason_code, exc.reason))
        if not atoms and not blockers:
            blockers.append(_blocker("structure_atoms_not_found", "No ATOM/HETATM rows were parsed from the supplied structure source."))

    summary = _summarize_atoms(atoms)
    quality_metrics: dict[str, Any] = {}
    coordinates_present = bool(atoms) and all("xyz" in atom for atom in atoms)
    if coordinates_present:
        quality_metrics = evaluate_structure_quality_with_external(
            atoms,
            pdb_text=source_text if parser == "pdb" else "",
        )
    status = "structure_analysis_ready" if source_available and atoms and not blockers else "blocked_structure_analysis"
    if source_kind == "pdb_id" and source_value:
        status = "structure_reference_recorded"
    return {
        "status": status,
        "source_kind": source_kind,
        "source_available": source_available,
        "source_reference": source_value if source_kind == "pdb_id" else "",
        "parser": parser,
        **summary,
        **policy.receipt(),
        "structure_coordinates_present": coordinates_present,
        "quality_metrics": quality_metrics,
        "molprobity_clashscore": quality_metrics.get("molprobity_clashscore"),
        "molprobity_clashscore_source": quality_metrics.get("molprobity_clashscore_source", "internal_proxy"),
        "ramachandran_outlier_fraction": quality_metrics.get("ramachandran_outlier_fraction"),
        "lddt_pli_source": quality_metrics.get("lddt_pli_source"),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
