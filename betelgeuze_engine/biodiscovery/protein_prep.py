from __future__ import annotations

import os
import shlex

import numpy as np

UNSUPPORTED_METAL_ELEMENTS = {
    "FE", "ZN", "MG", "MN", "CU", "CO", "NI", "CA", "NA", "K", "CD", "HG",
}
WATER_RESNAMES = {"HOH", "WAT", "H2O"}

AA3_TO_AA1: dict[str, str] = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def aa3_to_aa1(code: str) -> str:
    return AA3_TO_AA1.get(str(code).strip().upper(), "X")


def looks_like_mmcif_text(text: str) -> bool:
    body = str(text or "")
    return "_atom_site." in body or body.lstrip().startswith("data_")


def parse_mmcif_text(text: str) -> tuple[np.ndarray, str] | None:
    lines = [line.strip() for line in str(text).splitlines()]
    coords_ca: list[list[float]] = []
    coords_all: list[list[float]] = []
    seq: list[str] = []
    seen_residues: set[tuple[str, str]] = set()

    i = 0
    while i < len(lines):
        if lines[i] != "loop_":
            i += 1
            continue
        i += 1
        headers: list[str] = []
        while i < len(lines) and lines[i].startswith("_"):
            headers.append(lines[i])
            i += 1
        if not headers or not any(header.startswith("_atom_site.") for header in headers):
            continue

        column = {header.replace("_atom_site.", ""): idx for idx, header in enumerate(headers)}

        def value(tokens: list[str], *names: str) -> str:
            for name in names:
                idx = column.get(name)
                if idx is not None and idx < len(tokens):
                    item = str(tokens[idx]).strip()
                    if item not in {"", ".", "?"}:
                        return item
            return ""

        required = ("group_PDB", "label_atom_id", "label_comp_id", "Cartn_x", "Cartn_y", "Cartn_z")
        if not all(name in column for name in required):
            while i < len(lines) and lines[i] != "#":
                i += 1
            continue

        while i < len(lines):
            line = lines[i]
            if not line or line == "#":
                i += 1
                break
            if line.startswith("_") or line == "loop_":
                break
            try:
                tokens = shlex.split(line)
            except ValueError:
                tokens = line.split()
            if len(tokens) < len(headers):
                i += 1
                continue
            model_num = value(tokens, "pdbx_PDB_model_num")
            if model_num and model_num != "1":
                i += 1
                continue
            record = value(tokens, "group_PDB").upper()
            atom_name = value(tokens, "label_atom_id", "auth_atom_id")
            res_name = value(tokens, "label_comp_id", "auth_comp_id").upper()
            chain_id = value(tokens, "label_asym_id", "auth_asym_id")
            res_num = value(tokens, "label_seq_id", "auth_seq_id")
            element = (value(tokens, "type_symbol") or atom_name[:2]).upper()
            if record == "HETATM" and res_name not in WATER_RESNAMES:
                if element in UNSUPPORTED_METAL_ELEMENTS:
                    raise ValueError(f"unsupported_metal:{element}")
                raise ValueError(f"unsupported_cofactor_or_bound_ligand:{res_name or element}")
            try:
                x = float(value(tokens, "Cartn_x"))
                y = float(value(tokens, "Cartn_y"))
                z = float(value(tokens, "Cartn_z"))
            except ValueError:
                i += 1
                continue
            coords_all.append([x, y, z])
            if atom_name == "CA":
                coords_ca.append([x, y, z])
                residue_key = (chain_id, res_num or str(len(seq)))
                if residue_key not in seen_residues:
                    seq.append(aa3_to_aa1(res_name))
                    seen_residues.add(residue_key)
            i += 1

    coords_use = coords_ca if coords_ca else coords_all
    if not coords_use:
        return None
    return np.array(coords_use, dtype=np.float32), "".join(seq) if seq else ""


def parse_pdb_text(text: str) -> tuple[np.ndarray, str]:
    if not str(text).strip():
        raise ValueError("empty PDB/mmCIF input")
    if looks_like_mmcif_text(text):
        parsed_cif = parse_mmcif_text(text)
        if parsed_cif is not None:
            return parsed_cif
    coords_ca: list[list[float]] = []
    coords_all: list[list[float]] = []
    seq: list[str] = []
    current_residue = -1
    lines = text.splitlines()
    for line in lines:
        if line.startswith("ATOM") or line.startswith("HETATM"):
            record = line[:6].strip()
            atom_name = line[12:16].strip()
            res_name = line[17:20].strip().upper()
            element = (line[76:78].strip() or atom_name[:2]).upper()
            if record == "HETATM" and res_name not in WATER_RESNAMES:
                if element in UNSUPPORTED_METAL_ELEMENTS:
                    raise ValueError(f"unsupported_metal:{element}")
                raise ValueError(f"unsupported_cofactor_or_bound_ligand:{res_name or element}")
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except (ValueError, IndexError):
                continue
            coords_all.append([x, y, z])
            if atom_name == "CA":
                coords_ca.append([x, y, z])
                try:
                    res_num = int(line[22:26].strip())
                except ValueError:
                    res_num = current_residue + 1
                if res_num != current_residue:
                    seq.append(aa3_to_aa1(res_name))
                    current_residue = res_num
        elif line.startswith("SEQRES"):
            seq_part = line[19:].strip().split()
            for aa3 in seq_part:
                if aa3 in AA3_TO_AA1 and (not seq or aa3_to_aa1(aa3) != seq[-1]):
                    pass
    coords_use = coords_ca if coords_ca else coords_all
    if not coords_use:
        raise ValueError("no ATOM/HETATM CA records found in PDB/mmCIF input")
    return np.array(coords_use, dtype=np.float32), "".join(seq) if seq else ""


def validate_protein(protein_coords: np.ndarray, sequence: str) -> dict[str, object]:
    coords = np.asarray(protein_coords, dtype=np.float64)
    if coords.ndim != 2 or coords.shape[1] != 3:
        return {"valid": False, "reason": "invalid_coordinate_shape", "blocked": True, "blocker": "invalid_coordinate_shape"}
    n_res = coords.shape[0]
    if n_res == 0:
        return {"valid": False, "reason": "empty_protein_coords", "blocked": True, "blocker": "empty_protein_coords"}
    if not np.isfinite(coords).all():
        return {"valid": False, "reason": "nonfinite_coordinates", "blocked": True, "blocker": "nonfinite_coordinates"}
    if float(np.max(np.ptp(coords, axis=0))) > 5000.0:
        return {"valid": False, "reason": "coordinate_span_too_large", "blocked": True, "blocker": "coordinate_span_too_large"}
    if n_res < 10:
        return {"valid": False, "reason": "too_few_residues", "blocked": True, "blocker": "too_few_residues"}
    if n_res > 5000:
        return {"valid": False, "reason": "too_many_residues", "blocked": True, "blocker": "too_many_residues"}
    if str(sequence).strip():
        fidelity = "sequence_mapped"
    else:
        return {
            "valid": False,
            "reason": "placeholder_or_missing_sequence",
            "blocked": True,
            "blocker": "placeholder_topology",
        }
    if "X" in str(sequence).upper():
        return {
            "valid": False,
            "reason": "unknown_residue_in_sequence",
            "blocked": True,
            "blocker": "placeholder_topology",
        }
    return {"valid": True, "blocked": False, "fidelity": fidelity, "residue_count": n_res}


def resolve_protein_input(protein_input: str) -> tuple[np.ndarray, str]:
    if not protein_input.strip():
        raise ValueError("empty protein input")
    if os.path.isfile(protein_input.strip()):
        with open(protein_input.strip(), "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        if not text.strip():
            raise ValueError(f"empty protein file: {protein_input}")
        return parse_pdb_text(text)
    if (
        "ATOM  " in protein_input
        or "HETATM" in protein_input
        or "SEQRES" in protein_input
        or looks_like_mmcif_text(protein_input)
    ):
        return parse_pdb_text(protein_input)
    raise ValueError("protein input must be a PDB/mmCIF file path or PDB/mmCIF text with atom records")
