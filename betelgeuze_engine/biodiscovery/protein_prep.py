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


def _coordinates(x: str, y: str, z: str) -> list[float]:
    """Reject bad rows instead of silently dropping atoms; output is float32."""
    try:
        xyz = [float(x), float(y), float(z)]
    except ValueError as exc:
        raise ValueError("invalid_protein_coordinates") from exc
    if not all(math.isfinite(v) for v in xyz):
        raise ValueError("nonfinite_protein_coordinates")
    if any(abs(v) > float(np.finfo(np.float32).max) for v in xyz):
        raise ValueError("protein_coordinates_out_of_range")
    return xyz


def _append_ca(
    coords: list[list[float]], seq: list[str], seen: set[tuple[str, str, str]],
    key: tuple[str, str, str], res_name: str, xyz: list[float],
) -> None:
    if not key[1]:
        raise ValueError("missing_protein_residue_identity")
    if key in seen:
        raise ValueError("duplicate_protein_ca_residue")
    seen.add(key)
    coords.append(xyz)
    seq.append(aa3_to_aa1(res_name))


def parse_mmcif_text(text: str) -> tuple[np.ndarray, str] | None:
    """Read the existing row-per-line atom_site subset, not a general CIF parser.

    Multiple models/atom_site loops/data blocks and explicit alternate locations
    must be resolved by the caller. No model or conformer is silently selected.
    """
    lines = [line.strip() for line in str(text).splitlines()]
    coords_ca: list[list[float]] = []
    coords_all: list[list[float]] = []
    seq: list[str] = []
    seen_residues: set[tuple[str, str, str]] = set()
    models: set[int] = set()
    atom_loop_seen = False
    if sum(line.startswith("data_") for line in lines) > 1:
        raise ValueError("unsupported_multiple_mmcif_data_blocks")

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
        if not any(header.startswith("_atom_site.") for header in headers):
            continue
        if atom_loop_seen:
            raise ValueError("unsupported_multiple_atom_site_loops")
        atom_loop_seen = True
        if len(set(headers)) != len(headers) or any(
            not header.startswith("_atom_site.") for header in headers
        ):
            raise ValueError("invalid_mmcif_atom_site_columns")
        column = {header.removeprefix("_atom_site."): idx for idx, header in enumerate(headers)}

        def value(tokens: list[str], *names: str) -> str:
            for name in names:
                idx = column.get(name)
                if idx is not None:
                    item = tokens[idx].strip()
                    if item not in {"", ".", "?"}:
                        return item
            return ""

        required = ("group_PDB", "Cartn_x", "Cartn_y", "Cartn_z")
        if not all(name in column for name in required) or not all(
            label in column or auth in column
            for label, auth in (("label_atom_id", "auth_atom_id"), ("label_comp_id", "auth_comp_id"))
        ):
            raise ValueError("missing_mmcif_atom_site_columns")

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
            model_text = value(tokens, "pdbx_PDB_model_num")
            if "pdbx_PDB_model_num" in column and not model_text:
                raise ValueError("invalid_protein_model_number")
            try:
                model_num = int(model_text or "1")
            except ValueError as exc:
                raise ValueError("invalid_protein_model_number") from exc
            if model_num < 1:
                raise ValueError("invalid_protein_model_number")
            models.add(model_num)
            if len(models) > 1:
                raise ValueError("unsupported_multiple_protein_models")
            if value(tokens, "label_alt_id", "auth_alt_id"):
                raise ValueError("unsupported_protein_altloc")
            record = value(tokens, "group_PDB").upper()
            if record not in {"ATOM", "HETATM"}:
                raise ValueError("invalid_mmcif_atom_record")
            atom_name = value(tokens, "label_atom_id", "auth_atom_id")
            res_name = value(tokens, "label_comp_id", "auth_comp_id").upper()
            if not atom_name or not res_name:
                raise ValueError("missing_protein_atom_identity")
            element = (value(tokens, "type_symbol") or atom_name[:2]).upper()
            if record == "HETATM" and res_name not in WATER_RESNAMES:
                if element in UNSUPPORTED_METAL_ELEMENTS:
                    raise ValueError(f"unsupported_metal:{element}")
                raise ValueError(f"unsupported_cofactor_or_bound_ligand:{res_name or element}")
            xyz = _coordinates(value(tokens, "Cartn_x"), value(tokens, "Cartn_y"), value(tokens, "Cartn_z"))
            coords_all.append(xyz)
            if record == "ATOM" and atom_name == "CA":
                # Do not combine a label chain with an author residue number.
                chain_id, res_num = value(tokens, "label_asym_id"), value(tokens, "label_seq_id")
                if not chain_id or not res_num:
                    chain_id, res_num = value(tokens, "auth_asym_id"), value(tokens, "auth_seq_id")
                if not chain_id or not res_num:
                    raise ValueError("missing_protein_residue_identity")
                key = (chain_id, res_num, value(tokens, "pdbx_PDB_ins_code"))
                _append_ca(coords_ca, seq, seen_residues, key, res_name, xyz)
            i += 1

    coords_use = coords_ca if coords_ca else coords_all
    if not coords_use:
        return None
    return np.array(coords_use, dtype=np.float32), "".join(seq)


def parse_pdb_text(text: str) -> tuple[np.ndarray, str]:
    """Keep one C-alpha coordinate per identified residue in input order.

    This remains the coarse BioDiscovery path, not all-atom preparation.
    Multi-model structures and nonblank altLoc records are explicitly unsupported.
    """
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
    seen_residues: set[tuple[str, str, str]] = set()
    model_seen = False
    in_model = False
    for line in text.splitlines():
        record = line[:6].strip()
        if record == "MODEL":
            if model_seen:
                raise ValueError("unsupported_multiple_protein_models")
            if coords_all:
                raise ValueError("invalid_pdb_model_records")
            try:
                model_number = int(line[10:14].strip())
            except ValueError as exc:
                raise ValueError("invalid_protein_model_number") from exc
            if model_number < 1:
                raise ValueError("invalid_protein_model_number")
            model_seen = in_model = True
        elif record == "ENDMDL":
            if not in_model:
                raise ValueError("invalid_pdb_model_records")
            in_model = False
        elif record in {"ATOM", "HETATM"}:
            if model_seen and not in_model:
                raise ValueError("invalid_pdb_model_records")
            if line[16:17].strip():
                raise ValueError("unsupported_protein_altloc")
            atom_name = line[12:16].strip()
            res_name = line[17:20].strip().upper()
            element = (line[76:78].strip() or atom_name[:2]).upper()
            if not atom_name or not res_name:
                raise ValueError("missing_protein_atom_identity")
            if record == "HETATM" and res_name not in WATER_RESNAMES:
                if element in UNSUPPORTED_METAL_ELEMENTS:
                    raise ValueError(f"unsupported_metal:{element}")
                raise ValueError(f"unsupported_cofactor_or_bound_ligand:{res_name or element}")
            xyz = _coordinates(line[30:38], line[38:46], line[46:54])
            coords_all.append(xyz)
            if record == "ATOM" and atom_name == "CA":
                try:
                    res_num = str(int(line[22:26].strip()))
                except ValueError as exc:
                    raise ValueError("invalid_protein_residue_number") from exc
                key = (line[21:22], res_num, line[26:27].strip())
                _append_ca(coords_ca, seq, seen_residues, key, res_name, xyz)
    if in_model:
        raise ValueError("invalid_pdb_model_records")
    coords_use = coords_ca if coords_ca else coords_all
    if not coords_use:
        raise ValueError("no ATOM/HETATM CA records found in PDB/mmCIF input")
    return np.array(coords_use, dtype=np.float32), "".join(seq)


def _blocked(reason: str, blocker: str | None = None) -> dict[str, object]:
    return {"valid": False, "reason": reason, "blocked": True, "blocker": blocker or reason}


def validate_protein(protein_coords: np.ndarray, sequence: str) -> dict[str, object]:
    """Validate the C-alpha/sequence contract before coarse-grained computation."""
    try:
        coords = np.asarray(protein_coords)
    except (ValueError, TypeError):
        return _blocked("invalid_protein_coords")
    if coords.ndim != 2 or coords.shape[1] != 3:
        return _blocked("invalid_protein_coords_shape")
    if coords.dtype.kind not in "iuf":
        return _blocked("invalid_protein_coords_dtype")
    if not np.isfinite(coords).all():
        return _blocked("nonfinite_protein_coordinates")
    limit = float(np.finfo(np.float32).max)
    if (coords > limit).any() or (coords < -limit).any():
        return _blocked("protein_coordinates_out_of_range")
    n_res = coords.shape[0]
    if n_res == 0:
        return _blocked("empty_protein_coords")
    if n_res < 10:
        return _blocked("too_few_residues")
    if n_res > 5000:
        return _blocked("too_many_residues")
    if not isinstance(sequence, str) or not sequence.strip():
        return _blocked("placeholder_or_missing_sequence", "placeholder_topology")
    if any(aa not in AA3_TO_AA1.values() for aa in sequence.upper()):
        return _blocked("unknown_residue_in_sequence", "placeholder_topology")
    if len(sequence) != n_res:
        return _blocked("protein_coordinate_sequence_length_mismatch", "placeholder_topology")
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
