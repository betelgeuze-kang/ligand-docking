#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

_COMMON_NON_LIGAND_HET = {
    "HOH",
    "WAT",
    "DOD",
    "SO4",
    "PO4",
    "GOL",
    "EDO",
    "DMS",
    "PEG",
    "PGE",
    "MPD",
    "ACT",
    "ACY",
    "FMT",
    "EOH",
    "IPA",
    "MES",
    "TRS",
    "CL",
    "NA",
    "K",
    "CA",
    "MG",
    "ZN",
    "MN",
    "FE",
    "CU",
    "NI",
}


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _safe_optional_float(value: Any) -> float | None:
    try:
        if value in {"", None}:
            return None
        return float(value)
    except Exception:
        return None


def _is_ligand_atom(record: str, residue_name: str, chain_id: str) -> bool:
    residue = str(residue_name or "").strip().upper()
    chain = str(chain_id or "").strip().upper()
    if residue == "LIG" or chain == "L":
        return True
    return str(record or "").strip().upper() == "HETATM" and residue not in _COMMON_NON_LIGAND_HET


def _parse_pdb_atoms(path: Path) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not (line.startswith("ATOM") or line.startswith("HETATM")):
            continue
        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except Exception:
            continue
        record = "HETATM" if line.startswith("HETATM") else "ATOM"
        atoms.append(
            {
                "record": record,
                "atom_name": str(line[12:16].strip() or "C"),
                "residue_name": str(line[17:20].strip() or "UNK"),
                "chain_id": str(line[21:22].strip() or "A"),
                "residue_seq": _safe_int(line[22:26].strip(), 1),
                "insertion_code": str(line[26:27].strip()),
                "element": str(line[76:78].strip() or line[12:14].strip() or "C")[:2],
                "x": x,
                "y": y,
                "z": z,
            }
        )
    return atoms


def _parse_mmcif_atoms(path: Path) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = []
    headers: list[str] = []
    row_tokens: list[str] = []
    in_atom_site_loop = False
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped == "loop_":
            headers = []
            row_tokens = []
            in_atom_site_loop = False
            continue
        if stripped.startswith("_atom_site."):
            headers.append(stripped)
            in_atom_site_loop = True
            continue
        if headers and stripped.startswith("_") and not stripped.startswith("_atom_site."):
            headers = []
            row_tokens = []
            in_atom_site_loop = False
            continue
        if not in_atom_site_loop or not headers:
            continue
        if stripped == "#":
            break
        row_tokens.extend(shlex.split(stripped, posix=True))
        if len(row_tokens) < len(headers):
            continue
        row = {headers[idx]: row_tokens[idx] for idx in range(len(headers))}
        row_tokens = row_tokens[len(headers) :]
        try:
            x = float(row.get("_atom_site.Cartn_x", "nan"))
            y = float(row.get("_atom_site.Cartn_y", "nan"))
            z = float(row.get("_atom_site.Cartn_z", "nan"))
        except Exception:
            continue
        if not (np.isfinite(x) and np.isfinite(y) and np.isfinite(z)):
            continue
        record = str(row.get("_atom_site.group_PDB") or "ATOM").strip().upper()
        atoms.append(
            {
                "record": "HETATM" if record == "HETATM" else "ATOM",
                "atom_name": str(
                    row.get("_atom_site.label_atom_id")
                    or row.get("_atom_site.auth_atom_id")
                    or "C"
                ).strip(),
                "residue_name": str(
                    row.get("_atom_site.label_comp_id")
                    or row.get("_atom_site.auth_comp_id")
                    or "UNK"
                ).strip(),
                "chain_id": str(
                    row.get("_atom_site.auth_asym_id")
                    or row.get("_atom_site.label_asym_id")
                    or "A"
                ).strip(),
                "residue_seq": _safe_int(
                    row.get("_atom_site.auth_seq_id") or row.get("_atom_site.label_seq_id"),
                    1,
                ),
                "insertion_code": str(row.get("_atom_site.pdbx_PDB_ins_code") or "").strip(),
                "element": str(row.get("_atom_site.type_symbol") or "C").strip()[:2],
                "x": x,
                "y": y,
                "z": z,
            }
        )
    return atoms


def _load_structure_atoms(path_like: str) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    suffix = path.suffix.lower()
    if suffix in {".cif", ".mmcif"}:
        return _parse_mmcif_atoms(path)
    return _parse_pdb_atoms(path)


def _partition_atoms(atoms: list[dict[str, Any]]) -> dict[str, Any]:
    protein_atoms: list[dict[str, Any]] = []
    protein_ca: list[list[float]] = []
    ligand_atoms: list[dict[str, Any]] = []
    ligand_groups: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for atom in atoms:
        is_ligand = _is_ligand_atom(atom.get("record"), atom.get("residue_name"), atom.get("chain_id"))
        xyz = [float(atom["x"]), float(atom["y"]), float(atom["z"])]
        if is_ligand:
            ligand_atoms.append(atom)
            group_key = (
                str(atom.get("residue_name") or "").upper(),
                str(atom.get("chain_id") or "").upper(),
                int(atom.get("residue_seq") or 0),
            )
            ligand_groups.setdefault(group_key, []).append(atom)
            continue
        protein_atoms.append(atom)
        if str(atom.get("atom_name") or "").strip().upper() == "CA":
            protein_ca.append(xyz)
    native_anchor_atoms: list[dict[str, Any]] = []
    if ligand_groups:
        native_anchor_atoms = max(ligand_groups.values(), key=len)
    return {
        "protein_atoms": protein_atoms,
        "protein_ca": np.asarray(protein_ca, dtype=np.float32) if protein_ca else np.zeros((0, 3), dtype=np.float32),
        "ligand_atoms": ligand_atoms,
        "native_anchor_atoms": native_anchor_atoms,
    }


def _centroid_from_atoms(atoms: list[dict[str, Any]]) -> np.ndarray:
    coords = np.asarray([[atom["x"], atom["y"], atom["z"]] for atom in atoms], dtype=np.float32)
    if coords.size <= 0:
        return np.zeros(3, dtype=np.float32)
    return np.mean(coords, axis=0).astype(np.float32, copy=False)


def _centroid_from_pocket(pocket_center: tuple[float, float, float] | None) -> np.ndarray | None:
    if pocket_center is None:
        return None
    return np.asarray([float(pocket_center[0]), float(pocket_center[1]), float(pocket_center[2])], dtype=np.float32)


def _coords_from_atoms(atoms: list[dict[str, Any]]) -> np.ndarray:
    if not atoms:
        return np.zeros((0, 3), dtype=np.float32)
    return np.asarray([[atom["x"], atom["y"], atom["z"]] for atom in atoms], dtype=np.float32)


def _apply_transform(atoms: list[dict[str, Any]], rotation: np.ndarray, translation: np.ndarray) -> list[dict[str, Any]]:
    transformed: list[dict[str, Any]] = []
    for atom in atoms:
        xyz = np.asarray([atom["x"], atom["y"], atom["z"]], dtype=np.float32)
        moved = (xyz @ rotation.T) + translation
        transformed.append(
            {
                **atom,
                "x": float(moved[0]),
                "y": float(moved[1]),
                "z": float(moved[2]),
            }
        )
    return transformed


def _kabsch_transform(mobile: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mobile = np.asarray(mobile, dtype=np.float64)
    reference = np.asarray(reference, dtype=np.float64)
    mobile_center = np.mean(mobile, axis=0)
    reference_center = np.mean(reference, axis=0)
    mobile_centered = mobile - mobile_center
    reference_centered = reference - reference_center
    covariance = mobile_centered.T @ reference_centered
    u, _s, vh = np.linalg.svd(covariance, full_matrices=False)
    rotation = vh.T @ u.T
    if np.linalg.det(rotation) < 0:
        vh[-1, :] *= -1.0
        rotation = vh.T @ u.T
    translation = reference_center - (mobile_center @ rotation.T)
    return rotation.astype(np.float32), translation.astype(np.float32)


def _format_pdb_atom_line(atom: dict[str, Any], serial: int, *, hetatm: bool | None = None) -> str:
    record = "HETATM" if (hetatm if hetatm is not None else str(atom.get("record")).upper() == "HETATM") else "ATOM  "
    return (
        f"{record}{int(serial):5d} {str(atom.get('atom_name') or 'C')[:4]:<4s}"
        f"{str(atom.get('residue_name') or 'UNK')[:3]:>3s} "
        f"{str(atom.get('chain_id') or 'A')[:1]}{int(atom.get('residue_seq') or 1):4d}"
        f"{str(atom.get('insertion_code') or '')[:1]}   "
        f"{float(atom.get('x') or 0.0):8.3f}{float(atom.get('y') or 0.0):8.3f}{float(atom.get('z') or 0.0):8.3f}"
        f"{1.00:6.2f}{30.0:6.2f}          {str(atom.get('element') or 'C')[:2]:>2s}"
    )


def _write_reference_pdb(
    out_path: Path,
    *,
    protein_atoms: list[dict[str, Any]],
    ligand_atoms: list[dict[str, Any]],
    alignment_mode: str,
    alignment_note: str,
) -> None:
    lines = [
        f"REMARK SELECTED_ALLATOM_ALIGNMENT_MODE {alignment_mode}",
        f"REMARK SELECTED_ALLATOM_ALIGNMENT_NOTE {alignment_note}",
    ]
    serial = 1
    for atom in protein_atoms:
        lines.append(_format_pdb_atom_line(atom, serial, hetatm=False))
        serial += 1
    if protein_atoms:
        lines.append("TER")
    for atom in ligand_atoms:
        lines.append(_format_pdb_atom_line(atom, serial, hetatm=True))
        serial += 1
    lines.append("END")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_aligned_reference(
    *,
    native_structure_path: str,
    ligand_pose_pdb: str,
    out_pdb: str,
    viewer_reference_pdb: str = "",
    pocket_center: tuple[float, float, float] | None = None,
) -> dict[str, Any]:
    native_path = _resolve(native_structure_path)
    pose_path = _resolve(ligand_pose_pdb)
    viewer_path = (
        _resolve(viewer_reference_pdb)
        if str(viewer_reference_pdb or "").strip()
        else None
    )
    out_path = _resolve(out_pdb)

    if not native_path.exists():
        return {
            "ready": False,
            "aligned_reference_pdb": "",
            "alignment_mode": "missing_native_structure",
            "alignment_note": f"native structure is missing: {native_path}",
        }
    if not pose_path.exists():
        return {
            "ready": False,
            "aligned_reference_pdb": "",
            "alignment_mode": "missing_ligand_pose",
            "alignment_note": f"ligand pose PDB is missing: {pose_path}",
        }

    native = _partition_atoms(_load_structure_atoms(str(native_path)))
    pose = _partition_atoms(_load_structure_atoms(str(pose_path)))
    if not native["protein_atoms"]:
        return {
            "ready": False,
            "aligned_reference_pdb": "",
            "alignment_mode": "missing_native_protein_atoms",
            "alignment_note": f"native structure has no protein atoms: {native_path}",
        }
    if not pose["ligand_atoms"]:
        return {
            "ready": False,
            "aligned_reference_pdb": "",
            "alignment_mode": "missing_pose_ligand_atoms",
            "alignment_note": f"ligand pose has no ligand atoms: {pose_path}",
        }

    transformed_protein_atoms: list[dict[str, Any]] = []
    alignment_mode = ""
    alignment_note = ""

    if viewer_path is not None and viewer_path.is_file():
        viewer = _partition_atoms(_load_structure_atoms(str(viewer_path)))
        native_ca = np.asarray(native["protein_ca"], dtype=np.float32)
        viewer_ca = np.asarray(viewer["protein_ca"], dtype=np.float32)
        if native_ca.shape[0] >= 3 and viewer_ca.shape[0] >= 3:
            n_anchor = min(int(native_ca.shape[0]), int(viewer_ca.shape[0]))
            rotation, translation = _kabsch_transform(native_ca[:n_anchor], viewer_ca[:n_anchor])
            transformed_protein_atoms = _apply_transform(native["protein_atoms"], rotation, translation)
            alignment_mode = "viewer_reference_kabsch"
            alignment_note = (
                f"Aligned native protein to viewer reference using {n_anchor} CA anchors."
            )

    if not transformed_protein_atoms:
        anchor_centroid = None
        anchor_mode = ""
        if native["native_anchor_atoms"]:
            anchor_centroid = _centroid_from_atoms(native["native_anchor_atoms"])
            anchor_mode = "native_ligand_centroid_translation"
        else:
            anchor_centroid = _centroid_from_pocket(pocket_center)
            anchor_mode = "pocket_center_translation" if anchor_centroid is not None else ""
        if anchor_centroid is None:
            return {
                "ready": False,
                "aligned_reference_pdb": "",
                "alignment_mode": "missing_anchor_for_translation",
                "alignment_note": (
                    "Native structure has no usable ligand anchor and no pocket center was provided for translation fallback."
                ),
            }
        pose_centroid = _centroid_from_atoms(pose["ligand_atoms"])
        translation = pose_centroid - anchor_centroid
        transformed_protein_atoms = _apply_transform(
            native["protein_atoms"],
            np.eye(3, dtype=np.float32),
            translation.astype(np.float32),
        )
        alignment_mode = anchor_mode
        alignment_note = (
            "Translated native protein into the ligand pose frame using the native ligand/pocket centroid."
        )

    _write_reference_pdb(
        out_path,
        protein_atoms=transformed_protein_atoms,
        ligand_atoms=pose["ligand_atoms"],
        alignment_mode=alignment_mode,
        alignment_note=alignment_note,
    )
    return {
        "ready": True,
        "aligned_reference_pdb": str(out_path),
        "alignment_mode": alignment_mode,
        "alignment_note": alignment_note,
        "native_protein_atom_count": int(len(native["protein_atoms"])),
        "native_protein_ca_count": int(native["protein_ca"].shape[0]),
        "native_anchor_atom_count": int(len(native["native_anchor_atoms"])),
        "pose_ligand_atom_count": int(len(pose["ligand_atoms"])),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a selected-allatom native protein reference aligned for viewer use.")
    parser.add_argument("--native-structure", required=True)
    parser.add_argument("--ligand-pose-pdb", required=True)
    parser.add_argument("--viewer-reference-pdb", default="")
    parser.add_argument("--out-pdb", required=True)
    parser.add_argument("--pocket-x", default="")
    parser.add_argument("--pocket-y", default="")
    parser.add_argument("--pocket-z", default="")
    parser.add_argument("--out-json", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pocket_x = _safe_optional_float(args.pocket_x)
    pocket_y = _safe_optional_float(args.pocket_y)
    pocket_z = _safe_optional_float(args.pocket_z)
    pocket_center = None
    if pocket_x is not None and pocket_y is not None and pocket_z is not None:
        pocket_center = (pocket_x, pocket_y, pocket_z)
    payload = build_aligned_reference(
        native_structure_path=str(args.native_structure),
        ligand_pose_pdb=str(args.ligand_pose_pdb),
        viewer_reference_pdb=str(args.viewer_reference_pdb),
        out_pdb=str(args.out_pdb),
        pocket_center=pocket_center,
    )
    if str(args.out_json or "").strip():
        out_json = _resolve(str(args.out_json))
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not payload.get("ready"):
        raise SystemExit(str(payload.get("alignment_note") or "failed to build aligned reference"))


if __name__ == "__main__":
    main()
