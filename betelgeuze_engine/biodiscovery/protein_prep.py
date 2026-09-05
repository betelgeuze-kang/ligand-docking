from __future__ import annotations

import math
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


def _parse_coordinates(x: str, y: str, z: str) -> list[float]:
    """Do not silently discard malformed atoms or overflow the float32 output."""
    try:
        coords = [float(x), float(y), float(z)]
    except ValueError as exc:
        raise ValueError("invalid_atom_coordinates") from exc
    if not all(math.isfinite(component) for component in coords):
        raise ValueError("nonfinite_atom_coordinates")
    if any(abs(component) > float(np.finfo(np.float32).max) for component in coords):
        raise ValueError("atom_coordinates_out_of_range")
    return coords


def parse_mmcif_text(text: str) -> tuple[np.ndarray, str] | None:
    """Read the supported atom-site loop as a single-model C-alpha projection.

    Alternate locations and multiple models/blocks require explicit preparation
    upstream; this coarse parser must not select or merge them implicitly.
    """
    lines = [line.strip() for line in str(text).splitlines()]
    if sum(line.startswith("data_") for line in lines) > 1:
        raise ValueError("unsupported_mmcif_multiple_data_blocks")
    coords_ca: list[list[float]] = []
    coords_all: list[list[float]] = []
    seq: list[str] = []
    seen_residues: set[tuple[str, str, str, str]] = set()
    model_ids: set[int] = set()
    identity_namespace: str | None = None

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
        if len(column) != len(headers) or not all(name in column for name in required):
            raise ValueError("invalid_mmcif_atom_site_columns")

        while i < len(lines):
            line = lines[i]
            if not line or line.startswith("#"):
                i += 1
                continue
            if line.startswith(("_", "data_", "save_")) or line in {"loop_", "stop_"}:
                break
            try:
                tokens = shlex.split(line, comments=True)
            except ValueError as exc:
                raise ValueError("invalid_mmcif_atom_site_row") from exc
            if len(tokens) != len(headers):
                raise ValueError("invalid_mmcif_atom_site_row")
            record = value(tokens, "group_PDB").upper()
            if record not in {"ATOM", "HETATM"}:
                raise ValueError("invalid_mmcif_atom_record")
            model_num = value(tokens, "pdbx_PDB_model_num") if "pdbx_PDB_model_num" in column else "1"
            try:
                model_id = int(model_num)
            except ValueError as exc:
                raise ValueError("invalid_model_records") from exc
            if model_id < 1:
                raise ValueError("invalid_model_records")
            model_ids.add(model_id)
            if len(model_ids) > 1:
                raise ValueError("unsupported_multiple_models")
            if value(tokens, "label_alt_id"):
                raise ValueError("unsupported_alternate_location")
            atom_name = value(tokens, "label_atom_id", "auth_atom_id")
            res_name = value(tokens, "label_comp_id", "auth_comp_id").upper()
            element = (value(tokens, "type_symbol") or atom_name[:2]).upper()
            if record == "HETATM" and res_name not in WATER_RESNAMES:
                if element in UNSUPPORTED_METAL_ELEMENTS:
                    raise ValueError(f"unsupported_metal:{element}")
                raise ValueError(f"unsupported_cofactor_or_bound_ligand:{res_name or element}")
            coords = _parse_coordinates(
                value(tokens, "Cartn_x"), value(tokens, "Cartn_y"), value(tokens, "Cartn_z")
            )
            coords_all.append(coords)
            if atom_name == "CA":
                # Use a complete namespace, never a label chain with an author ID.
                label_chain = value(tokens, "label_asym_id")
                label_seq = value(tokens, "label_seq_id")
                if label_chain and label_seq:
                    try:
                        label_seq_id = int(label_seq)
                    except ValueError as exc:
                        raise ValueError("invalid_residue_identity") from exc
                    if label_seq_id < 1:
                        raise ValueError("invalid_residue_identity")
                    residue_key = ("label", label_chain, str(label_seq_id), "")
                else:
                    auth_chain = value(tokens, "auth_asym_id")
                    auth_seq = value(tokens, "auth_seq_id")
                    if not auth_chain or not auth_seq:
                        raise ValueError("invalid_residue_identity")
                    residue_key = ("auth", auth_chain, auth_seq, value(tokens, "pdbx_PDB_ins_code"))
                if identity_namespace is not None and identity_namespace != residue_key[0]:
                    raise ValueError("inconsistent_residue_identity")
                identity_namespace = residue_key[0]
                if residue_key in seen_residues:
                    raise ValueError("duplicate_ca_residue")
                seen_residues.add(residue_key)
                coords_ca.append(coords)
                seq.append(aa3_to_aa1(res_name))
            i += 1

    coords_use = coords_ca if coords_ca else coords_all
    if not coords_use:
        return None
    return np.array(coords_use, dtype=np.float32), "".join(seq)


def parse_pdb_text(text: str) -> tuple[np.ndarray, str]:
    """Return the legacy C-alpha representation, never an implicit model mixture."""
    if not str(text).strip():
        raise ValueError("empty PDB/mmCIF input")
    if looks_like_mmcif_text(text):
        parsed_cif = parse_mmcif_text(text)
        if parsed_cif is None:
            raise ValueError("no ATOM/HETATM CA records found in PDB/mmCIF input")
        return parsed_cif
    coords_ca: list[list[float]] = []
    coords_all: list[list[float]] = []
    seq: list[str] = []
    seen_residues: set[tuple[str, int, str]] = set()
    saw_model = False
    in_model = False
    for line in text.splitlines():
        record = line[:6].strip()
        if record == "MODEL":
            if saw_model:
                raise ValueError("unsupported_multiple_models")
            if coords_all:
                raise ValueError("invalid_model_records")
            try:
                model_id = int(line[10:14].strip())
            except ValueError as exc:
                raise ValueError("invalid_model_records") from exc
            if model_id < 1:
                raise ValueError("invalid_model_records")
            saw_model = True
            in_model = True
        elif record == "ENDMDL":
            if not in_model:
                raise ValueError("invalid_model_records")
            in_model = False
        elif record in {"ATOM", "HETATM"}:
            if saw_model and not in_model:
                raise ValueError("invalid_model_records")
            if line[16:17].strip():
                raise ValueError("unsupported_alternate_location")
            atom_name = line[12:16].strip()
            res_name = line[17:20].strip().upper()
            element = (line[76:78].strip() or atom_name[:2]).upper()
            if record == "HETATM" and res_name not in WATER_RESNAMES:
                if element in UNSUPPORTED_METAL_ELEMENTS:
                    raise ValueError(f"unsupported_metal:{element}")
                raise ValueError(f"unsupported_cofactor_or_bound_ligand:{res_name or element}")
            coords = _parse_coordinates(line[30:38], line[38:46], line[46:54])
            coords_all.append(coords)
            if atom_name == "CA":
                try:
                    res_num = int(line[22:26].strip())
                except ValueError as exc:
                    raise ValueError("invalid_residue_identity") from exc
                residue_key = (line[21:22], res_num, line[26:27].strip())
                if residue_key in seen_residues:
                    raise ValueError("duplicate_ca_residue")
                seen_residues.add(residue_key)
                coords_ca.append(coords)
                seq.append(aa3_to_aa1(res_name))
    if in_model:
        raise ValueError("invalid_model_records")
    coords_use = coords_ca if coords_ca else coords_all
    if not coords_use:
        raise ValueError("no ATOM/HETATM CA records found in PDB/mmCIF input")
    return np.array(coords_use, dtype=np.float32), "".join(seq)


def _blocked_protein(reason: str, blocker: str | None = None) -> dict[str, object]:
    return {"valid": False, "reason": reason, "blocked": True, "blocker": blocker or reason}


def validate_protein(protein_coords: np.ndarray, sequence: str) -> dict[str, object]:
    """Validate one coordinate per residue in the legacy C-alpha projection."""
    if not isinstance(protein_coords, np.ndarray) or protein_coords.ndim != 2 or protein_coords.shape[1] != 3:
        return _blocked_protein("invalid_protein_coordinate_shape")
    if protein_coords.dtype.kind not in "fiu":
        return _blocked_protein("invalid_protein_coordinate_dtype")
    n_res = protein_coords.shape[0]
    if n_res == 0:
        return _blocked_protein("empty_protein_coords")
    if n_res < 10:
        return _blocked_protein("too_few_residues")
    if n_res > 5000:
        return _blocked_protein("too_many_residues")
    if not np.isfinite(protein_coords).all():
        return _blocked_protein("nonfinite_protein_coordinates")
    if not isinstance(sequence, str) or not sequence.strip():
        return _blocked_protein("placeholder_or_missing_sequence", "placeholder_topology")
    normalized_sequence = sequence.strip().upper()
    if "X" in normalized_sequence:
        return _blocked_protein("unknown_residue_in_sequence", "placeholder_topology")
    if any(residue not in AA3_TO_AA1.values() for residue in normalized_sequence):
        return _blocked_protein("invalid_protein_sequence", "placeholder_topology")
    if len(normalized_sequence) != n_res:
        return _blocked_protein("protein_coordinate_sequence_length_mismatch", "placeholder_topology")
    return {"valid": True, "blocked": False, "fidelity": "sequence_mapped", "residue_count": n_res}


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
