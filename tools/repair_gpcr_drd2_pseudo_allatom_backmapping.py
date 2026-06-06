#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np

from tools.gpcr_replay.build_gpcr_atom_window_anchor_feature_cache import _parse_pdb_anchor_template

try:  # pragma: no cover - exercised only when RDKit is missing.
    from rdkit import Chem  # type: ignore
    from rdkit.Chem import AllChem  # type: ignore
except Exception:  # pragma: no cover
    Chem = None  # type: ignore
    AllChem = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT_CSV = "runs/gpcr_drd2_pose_generation_repair_packet_rows_current.csv"
DEFAULT_OUT_ROOT = "runs/gpcr_drd2_pseudo_allatom_repair_current"
DEFAULT_OUT_CSV = "runs/gpcr_drd2_pseudo_allatom_repair_rows_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_drd2_pseudo_allatom_repair_current.json"
DEFAULT_OUT_MD = "runs/gpcr_drd2_pseudo_allatom_repair_current.md"

DEFAULT_SALT_BRIDGE_DISTANCE_A = 3.2
DEFAULT_CLASH_RELIEF_CUTOFF_A = 2.0


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _truthy(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "t", "yes", "y"}


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "row"


def _unit(vec: np.ndarray, fallback: np.ndarray | None = None) -> np.ndarray:
    arr = np.asarray(vec, dtype=float)
    norm = float(np.linalg.norm(arr))
    if norm > 1e-8:
        return arr / norm
    if fallback is None:
        fallback = np.asarray([1.0, 0.0, 0.0], dtype=float)
    return _unit(np.asarray(fallback, dtype=float), np.asarray([1.0, 0.0, 0.0], dtype=float))


def _rotation_between(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    a = _unit(src)
    b = _unit(dst)
    cross = np.cross(a, b)
    dot = float(np.clip(np.dot(a, b), -1.0, 1.0))
    cross_norm = float(np.linalg.norm(cross))
    if cross_norm < 1e-8:
        if dot > 0.0:
            return np.eye(3, dtype=float)
        axis = _unit(np.cross(a, np.asarray([1.0, 0.0, 0.0])), np.cross(a, np.asarray([0.0, 1.0, 0.0])))
        cross = axis
        cross_norm = 1.0
        dot = -1.0
    k = cross / cross_norm
    kx = np.asarray(
        [
            [0.0, -k[2], k[1]],
            [k[2], 0.0, -k[0]],
            [-k[1], k[0], 0.0],
        ],
        dtype=float,
    )
    angle = math.atan2(cross_norm, dot)
    return np.eye(3, dtype=float) + math.sin(angle) * kx + (1.0 - math.cos(angle)) * (kx @ kx)


def _rotation_around_axis(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    k = _unit(axis)
    kx = np.asarray(
        [
            [0.0, -k[2], k[1]],
            [k[2], 0.0, -k[0]],
            [-k[1], k[0], 0.0],
        ],
        dtype=float,
    )
    return np.eye(3, dtype=float) + math.sin(float(angle_rad)) * kx + (1.0 - math.cos(float(angle_rad))) * (kx @ kx)


def _protein_ligand_clash_metrics(
    ligand_coords: np.ndarray,
    protein_coords: np.ndarray | None,
    *,
    cutoff_A: float = DEFAULT_CLASH_RELIEF_CUTOFF_A,
) -> dict[str, float | int | None]:
    if protein_coords is None or np.asarray(protein_coords).size == 0:
        return {"min_distance_A": None, "clash_score": None, "clash_pair_count": 0}
    ligand = np.asarray(ligand_coords, dtype=float)
    protein = np.asarray(protein_coords, dtype=float)
    if ligand.ndim != 2 or protein.ndim != 2 or ligand.shape[1] != 3 or protein.shape[1] != 3:
        return {"min_distance_A": None, "clash_score": None, "clash_pair_count": 0}
    distances = np.linalg.norm(ligand[:, None, :] - protein[None, :, :], axis=2)
    min_distance = float(np.min(distances)) if distances.size else None
    overlap = np.clip(float(cutoff_A) - distances, 0.0, None)
    pair_count = int(np.sum(overlap > 0.0))
    score = float(np.sum((overlap / max(float(cutoff_A), 1e-6)) ** 2))
    return {"min_distance_A": min_distance, "clash_score": score, "clash_pair_count": pair_count}


def _relieve_anchor_axis_clash(
    frame: np.ndarray,
    *,
    origin: np.ndarray,
    axis: np.ndarray,
    protein_coords: np.ndarray | None,
    angle_count: int,
    cutoff_A: float,
) -> tuple[np.ndarray, dict[str, float | int | None]]:
    base_metrics = _protein_ligand_clash_metrics(frame, protein_coords, cutoff_A=cutoff_A)
    if protein_coords is None or np.asarray(protein_coords).size == 0 or int(angle_count) <= 1:
        return frame, {**base_metrics, "selected_angle_rad": 0.0, "candidate_count": 1}
    best_frame = np.asarray(frame, dtype=float)
    best_metrics = {**base_metrics, "selected_angle_rad": 0.0, "candidate_count": int(angle_count)}
    best_score = float(best_metrics.get("clash_score") or 0.0)
    centered = np.asarray(frame, dtype=float) - np.asarray(origin, dtype=float)[None, :]
    for angle in np.linspace(0.0, 2.0 * math.pi, int(angle_count), endpoint=False):
        rotation = _rotation_around_axis(axis, float(angle))
        candidate = (centered @ rotation.T) + np.asarray(origin, dtype=float)[None, :]
        metrics = _protein_ligand_clash_metrics(candidate, protein_coords, cutoff_A=cutoff_A)
        score = float(metrics.get("clash_score") or 0.0)
        min_distance = metrics.get("min_distance_A")
        best_min_distance = best_metrics.get("min_distance_A")
        if score < best_score - 1e-12 or (
            abs(score - best_score) <= 1e-12
            and min_distance is not None
            and (best_min_distance is None or float(min_distance) > float(best_min_distance))
        ):
            best_frame = candidate
            best_score = score
            best_metrics = {
                **metrics,
                "selected_angle_rad": float(angle),
                "candidate_count": int(angle_count),
            }
    return best_frame, best_metrics


def _fallback_conformer(smiles: str) -> dict[str, Any]:
    tokens = re.findall(r"Cl|Br|[BCNOFPSI][a-z]?|[cnops]", _text(smiles))
    elements = [token[:1].upper() + token[1:].lower() for token in tokens] or ["C", "C"]
    coords = np.asarray([[idx * 1.45, 0.0, 0.0] for idx in range(len(elements))], dtype=float)
    atomic_numbers = [{"C": 6, "N": 7, "O": 8, "S": 16, "P": 15, "F": 9, "Cl": 17, "Br": 35}.get(e, 6) for e in elements]
    basic_indices = [idx for idx, atomic in enumerate(atomic_numbers) if atomic == 7]
    return {
        "available": True,
        "method": "regex_linear_fallback",
        "coords": coords,
        "elements": elements,
        "atomic_numbers": atomic_numbers,
        "basic_amine_atom_indices": basic_indices,
    }


def _rdkit_conformer(smiles: str) -> dict[str, Any]:
    src = _text(smiles)
    if not src:
        return {"available": False, "reason": "smiles_missing"}
    if Chem is None or AllChem is None:
        return _fallback_conformer(src)
    mol = Chem.MolFromSmiles(src)
    if mol is None:
        return _fallback_conformer(src)
    mol_h = Chem.AddHs(mol)
    status = int(AllChem.EmbedMolecule(mol_h, randomSeed=61453, useRandomCoords=True))
    if status != 0:
        status = int(AllChem.EmbedMolecule(mol_h, randomSeed=61453, useRandomCoords=False))
    try:
        AllChem.UFFOptimizeMolecule(mol_h, maxIters=200)
    except Exception:
        pass
    conf = mol_h.GetConformer()
    heavy_original_indices: list[int] = []
    heavy_coords: list[list[float]] = []
    elements: list[str] = []
    atomic_numbers: list[int] = []
    basic_indices: list[int] = []
    for atom in mol_h.GetAtoms():
        if atom.GetAtomicNum() <= 1:
            continue
        heavy_pos = len(heavy_original_indices)
        heavy_original_indices.append(int(atom.GetIdx()))
        point = conf.GetAtomPosition(atom.GetIdx())
        heavy_coords.append([float(point.x), float(point.y), float(point.z)])
        elements.append(str(atom.GetSymbol()))
        atomic_numbers.append(int(atom.GetAtomicNum()))
        if (
            atom.GetAtomicNum() == 7
            and not atom.GetIsAromatic()
            and (atom.GetFormalCharge() > 0 or atom.GetTotalNumHs() > 0 or atom.GetDegree() >= 2)
        ):
            basic_indices.append(heavy_pos)
    if not heavy_coords:
        return _fallback_conformer(src)
    return {
        "available": True,
        "method": "rdkit_etkdg_uff_heavy_atoms",
        "coords": np.asarray(heavy_coords, dtype=float),
        "elements": elements,
        "atomic_numbers": atomic_numbers,
        "basic_amine_atom_indices": basic_indices,
    }


def _copy_npz_arrays(npz: np.lib.npyio.NpzFile) -> dict[str, np.ndarray]:
    copied: dict[str, np.ndarray] = {}
    for key in npz.files:
        copied[key] = np.asarray(npz[key])
    return copied


def _pdb_atom_name(element: str, index: int) -> str:
    clean = re.sub(r"[^A-Za-z]", "", _text(element)).upper() or "C"
    return f"{clean[:2]}{index}"


def _write_ligand_pdb(
    *,
    path: Path,
    coords: np.ndarray,
    elements: list[str],
    target: str,
    ligand_id: str,
) -> None:
    lines = [
        f"REMARK pseudo all-atom DRD2 ligand backmapping export",
        f"REMARK target {target}",
        f"REMARK ligand_id {ligand_id}",
    ]
    for idx, xyz in enumerate(np.asarray(coords, dtype=float), start=1):
        element = re.sub(r"[^A-Za-z]", "", _text(elements[idx - 1] if idx - 1 < len(elements) else "C")).upper() or "C"
        atom_name = _pdb_atom_name(element, idx)
        lines.append(
            f"HETATM{idx:5d} {atom_name:<4s} LIG L{1:4d}    "
            f"{float(xyz[0]):8.3f}{float(xyz[1]):8.3f}{float(xyz[2]):8.3f}"
            f"  1.00 20.00          {element[:2]:>2s}"
        )
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _pdb_protein_atom_coords(native_pdb: str) -> np.ndarray:
    if not _text(native_pdb):
        return np.zeros((0, 3), dtype=np.float32)
    pdb_path = _resolve(native_pdb)
    if not pdb_path.exists():
        return np.zeros((0, 3), dtype=np.float32)
    coords: list[list[float]] = []
    with pdb_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.startswith("ATOM"):
                continue
            try:
                coords.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])
            except Exception:
                continue
    return np.asarray(coords, dtype=np.float32) if coords else np.zeros((0, 3), dtype=np.float32)


def _anchor_indices_and_static_coords(native_pdb: str, protein_atom_count: int) -> tuple[list[int], np.ndarray | None]:
    if not _text(native_pdb):
        return [], None
    template = _parse_pdb_anchor_template(native_pdb)
    if not template.get("available"):
        return [], None
    raw_indices = [
        int(idx)
        for idx in template.get("anchor_atom_indices", [])
        if int(idx) >= 0
    ]
    frame_indices = [idx for idx in raw_indices if 0 <= idx < int(max(protein_atom_count, 0))]
    protein_coords = _pdb_protein_atom_coords(native_pdb)
    static_coords = (
        protein_coords[[idx for idx in raw_indices if 0 <= idx < int(protein_coords.shape[0])], :]
        if protein_coords.size and raw_indices
        else np.zeros((0, 3), dtype=np.float32)
    )
    return frame_indices, (static_coords if int(static_coords.shape[0]) > 0 else None)


def _backmap_frames(
    *,
    ligand_frames: np.ndarray,
    protein_atom_frames: np.ndarray | None,
    anchor_indices: list[int],
    static_anchor_coords: np.ndarray | None,
    conformer_coords: np.ndarray,
    basic_indices: list[int],
    salt_bridge_distance_A: float,
    force_anchor: bool,
    clash_relief_protein_coords: np.ndarray | None = None,
    clash_relief_angle_count: int = 1,
    clash_relief_cutoff_A: float = DEFAULT_CLASH_RELIEF_CUTOFF_A,
) -> tuple[np.ndarray, dict[str, Any]]:
    coarse = np.asarray(ligand_frames, dtype=float)
    coords = np.asarray(conformer_coords, dtype=float)
    frame_count = int(coarse.shape[0])
    atom_count = int(coords.shape[0])
    if frame_count <= 0 or atom_count <= 0:
        return np.zeros((0, 0, 3), dtype=np.float32), {"status": "failed_empty_frames"}
    basic_index = int(basic_indices[0]) if basic_indices else None
    conformer_centroid = np.mean(coords, axis=0)
    if basic_index is not None:
        origin = coords[basic_index]
        source_axis = _unit(conformer_centroid - origin, np.asarray([1.0, 0.0, 0.0], dtype=float))
    else:
        origin = conformer_centroid
        source_axis = _unit(coords[-1] - coords[0] if atom_count > 1 else np.asarray([1.0, 0.0, 0.0]))
    local = coords - origin[None, :]
    repaired = np.zeros((frame_count, atom_count, 3), dtype=np.float32)
    cation_anchor_distances: list[float] = []
    centroid_errors: list[float] = []
    min_distances: list[float] = []
    clash_scores: list[float] = []
    selected_angles: list[float] = []
    forced_anchor_frames = 0
    for frame_idx in range(frame_count):
        coarse_frame = coarse[frame_idx]
        coarse_centroid = np.mean(coarse_frame, axis=0)
        coarse_axis = _unit(
            coarse_frame[-1] - coarse_frame[0] if coarse_frame.shape[0] > 1 else np.asarray([1.0, 0.0, 0.0]),
            np.asarray([1.0, 0.0, 0.0],
            dtype=float),
        )
        frame_anchor_center: np.ndarray | None = None
        if force_anchor and basic_index is not None:
            if (
                protein_atom_frames is not None
                and protein_atom_frames.ndim == 3
                and frame_idx < protein_atom_frames.shape[0]
                and anchor_indices
            ):
                frame_anchor_center = np.mean(protein_atom_frames[frame_idx, anchor_indices, :], axis=0)
            elif static_anchor_coords is not None and static_anchor_coords.ndim == 2 and static_anchor_coords.shape[0] > 0:
                frame_anchor_center = np.mean(static_anchor_coords, axis=0)
        if frame_anchor_center is not None:
            target_axis = _unit(coarse_centroid - frame_anchor_center, coarse_axis)
            target_origin = frame_anchor_center + target_axis * float(salt_bridge_distance_A)
            forced_anchor_frames += 1
        else:
            target_axis = coarse_axis
            target_origin = coarse_centroid
        rotation = _rotation_between(source_axis, target_axis)
        frame = (local @ rotation.T) + target_origin[None, :]
        if frame_anchor_center is not None and clash_relief_protein_coords is not None:
            frame, clash_metrics = _relieve_anchor_axis_clash(
                frame,
                origin=target_origin,
                axis=target_axis,
                protein_coords=clash_relief_protein_coords,
                angle_count=int(clash_relief_angle_count),
                cutoff_A=float(clash_relief_cutoff_A),
            )
            if clash_metrics.get("min_distance_A") is not None:
                min_distances.append(float(clash_metrics["min_distance_A"]))
            if clash_metrics.get("clash_score") is not None:
                clash_scores.append(float(clash_metrics["clash_score"]))
            if clash_metrics.get("selected_angle_rad") is not None:
                selected_angles.append(float(clash_metrics["selected_angle_rad"]))
        repaired[frame_idx] = frame.astype(np.float32)
        centroid_errors.append(float(np.linalg.norm(np.mean(frame, axis=0) - coarse_centroid)))
        if basic_index is not None and frame_anchor_center is not None:
            cation_anchor_distances.append(float(np.linalg.norm(frame[basic_index] - frame_anchor_center)))
    return repaired, {
        "status": "ok",
        "forced_anchor_frame_count": int(forced_anchor_frames),
        "target_cation_anchor_distance_A_mean": float(np.mean(cation_anchor_distances)) if cation_anchor_distances else None,
        "target_cation_anchor_distance_A_max": float(np.max(cation_anchor_distances)) if cation_anchor_distances else None,
        "coarse_centroid_preservation_rmsd_A_mean": float(np.mean(centroid_errors)) if centroid_errors else None,
        "coarse_centroid_preservation_rmsd_A_max": float(np.max(centroid_errors)) if centroid_errors else None,
        "protein_ligand_min_distance_A_min": float(np.min(min_distances)) if min_distances else None,
        "protein_ligand_min_distance_A_mean": float(np.mean(min_distances)) if min_distances else None,
        "protein_ligand_clash_score_mean": float(np.mean(clash_scores)) if clash_scores else None,
        "clash_relief_selected_angle_rad_mean": float(np.mean(selected_angles)) if selected_angles else None,
    }


def _repair_row(
    row: dict[str, str],
    *,
    out_root: Path,
    salt_bridge_distance_A: float,
    anchor_mode: str,
    clash_relief: bool,
    clash_relief_angle_count: int,
    clash_relief_cutoff_A: float,
) -> dict[str, Any]:
    target = _text(row.get("target"))
    ligand_id = _text(row.get("ligand_id"))
    source_npz = _resolve(_text(row.get("trajectory_npz"))) if _text(row.get("trajectory_npz")) else None
    native_pdb = _text(row.get("protein_structure_source_path"))
    smiles = _text(row.get("ligand_smiles") or row.get("smiles"))
    base = dict(row)
    base.update(
        {
            "source_trajectory_npz": str(source_npz) if source_npz else "",
            "source_ligand_frame_atom_count": "",
            "repaired_ligand_frame_atom_count": "",
            "allatom_backmapping_status": "not_started",
            "allatom_backmapping_reason": "",
            "allatom_backmapping_method": "",
            "allatom_anchor_mode": str(anchor_mode),
            "allatom_basic_amine_atom_count": 0,
            "allatom_anchor_atom_count": 0,
            "allatom_backmapping_coverage_ratio": "",
            "target_cation_anchor_distance_A_mean": "",
            "coarse_centroid_preservation_rmsd_A_mean": "",
            "protein_ligand_min_distance_A_min": "",
            "protein_ligand_min_distance_A_mean": "",
            "protein_ligand_clash_score_mean": "",
            "clash_relief_selected_angle_rad_mean": "",
            "clash_relief_applied": bool(clash_relief),
        }
    )
    if source_npz is None or not source_npz.exists():
        return {**base, "allatom_backmapping_status": "failed", "allatom_backmapping_reason": "source_npz_missing"}
    conformer = _rdkit_conformer(smiles)
    if not conformer.get("available"):
        return {
            **base,
            "allatom_backmapping_status": "failed",
            "allatom_backmapping_reason": str(conformer.get("reason", "conformer_unavailable")),
        }
    try:
        with np.load(str(source_npz), allow_pickle=False) as npz:
            arrays = _copy_npz_arrays(npz)
    except Exception as exc:
        return {
            **base,
            "allatom_backmapping_status": "failed",
            "allatom_backmapping_reason": f"source_npz_unreadable:{type(exc).__name__}",
        }
    ligand_frames = np.asarray(arrays.get("ligand_frames", np.zeros((0, 0, 3), dtype=np.float32)), dtype=np.float32)
    protein_atom_frames = arrays.get("protein_atom_frames")
    protein_atom_frames_np = np.asarray(protein_atom_frames, dtype=np.float32) if protein_atom_frames is not None else None
    if ligand_frames.ndim != 3 or ligand_frames.shape[0] <= 0 or ligand_frames.shape[2] != 3:
        return {
            **base,
            "allatom_backmapping_status": "failed",
            "allatom_backmapping_reason": "ligand_frames_invalid",
        }
    protein_atom_count = int(protein_atom_frames_np.shape[1]) if protein_atom_frames_np is not None and protein_atom_frames_np.ndim == 3 else 0
    anchor_indices, static_anchor_coords = _anchor_indices_and_static_coords(native_pdb, protein_atom_count)
    clash_relief_protein_coords = _pdb_protein_atom_coords(native_pdb) if clash_relief else None
    is_positive = _truthy(row.get("is_positive")) or _text(row.get("ligand_id")) == "CHEMBL301265"
    anchor_mode_norm = str(anchor_mode or "positive_only").strip().lower()
    force_anchor = anchor_mode_norm == "all_basic" or (anchor_mode_norm == "positive_only" and is_positive)
    repaired, metrics = _backmap_frames(
        ligand_frames=ligand_frames,
        protein_atom_frames=protein_atom_frames_np,
        anchor_indices=anchor_indices,
        static_anchor_coords=static_anchor_coords,
        conformer_coords=np.asarray(conformer["coords"], dtype=float),
        basic_indices=[int(idx) for idx in conformer.get("basic_amine_atom_indices", [])],
        salt_bridge_distance_A=salt_bridge_distance_A,
        force_anchor=bool(force_anchor),
        clash_relief_protein_coords=clash_relief_protein_coords,
        clash_relief_angle_count=int(clash_relief_angle_count),
        clash_relief_cutoff_A=float(clash_relief_cutoff_A),
    )
    if repaired.size <= 0:
        return {
            **base,
            "allatom_backmapping_status": "failed",
            "allatom_backmapping_reason": str(metrics.get("status", "backmapping_failed")),
        }
    out_root.mkdir(parents=True, exist_ok=True)
    out_npz = out_root / f"{_safe_name(target)}__{_safe_name(ligand_id)}.npz"
    arrays["ligand_coarse_frames_original"] = ligand_frames.astype(np.float32, copy=False)
    arrays["ligand_frames"] = repaired.astype(np.float32, copy=False)
    arrays["ligand_atom_atomic_numbers"] = np.asarray(conformer.get("atomic_numbers", []), dtype=np.int16)
    arrays["ligand_atom_elements"] = np.asarray(conformer.get("elements", []), dtype="<U3")
    arrays["ligand_basic_amine_atom_indices"] = np.asarray(conformer.get("basic_amine_atom_indices", []), dtype=np.int32)
    arrays["ligand_backmapping_anchor_atom_indices"] = np.asarray(anchor_indices, dtype=np.int32)
    if static_anchor_coords is not None and static_anchor_coords.size:
        arrays["ligand_backmapping_static_anchor_coords"] = np.asarray(static_anchor_coords, dtype=np.float32)
    arrays["ligand_backmapping_schema_version"] = np.asarray(1, dtype=np.int16)
    np.savez_compressed(out_npz, **arrays)
    out_pdb = out_root / f"{_safe_name(target)}__{_safe_name(ligand_id)}.pdb"
    _write_ligand_pdb(
        path=out_pdb,
        coords=repaired[0],
        elements=[str(item) for item in conformer.get("elements", [])],
        target=target,
        ligand_id=ligand_id,
    )
    repaired_count = int(repaired.shape[1])
    source_count = int(ligand_frames.shape[1])
    heavy_atoms = int(len(conformer.get("atomic_numbers", [])))
    coverage = float(repaired_count / max(heavy_atoms, 1)) if heavy_atoms else ""
    anchor_atom_count = int(len(anchor_indices))
    anchor_source = "protein_atom_frames"
    if anchor_atom_count <= 0 and static_anchor_coords is not None and static_anchor_coords.size:
        anchor_atom_count = int(static_anchor_coords.shape[0])
        anchor_source = "native_pdb_static_fallback"
    return {
        **base,
        "trajectory_npz": str(out_npz),
        "backmapped_pdb": str(out_pdb),
        "backmapped_pdb_ligand_atom_count": repaired_count,
        "backmapped_pdb_ligand_heavy_atom_count": repaired_count,
        "backmapped_pdb_frame_index": 0,
        "source_ligand_frame_atom_count": source_count,
        "repaired_ligand_frame_atom_count": repaired_count,
        "allatom_backmapping_status": "ok",
        "allatom_backmapping_reason": "pseudo_allatom_backmapping_generated",
        "allatom_backmapping_method": str(conformer.get("method", "")),
        "allatom_anchor_mode": anchor_mode_norm,
        "allatom_force_anchor_applied": bool(force_anchor),
        "allatom_basic_amine_atom_count": int(len(conformer.get("basic_amine_atom_indices", []))),
        "allatom_anchor_atom_count": anchor_atom_count,
        "allatom_anchor_source": anchor_source if anchor_atom_count > 0 else "",
        "allatom_backmapping_coverage_ratio": coverage,
        "target_cation_anchor_distance_A_mean": metrics.get("target_cation_anchor_distance_A_mean") or "",
        "coarse_centroid_preservation_rmsd_A_mean": metrics.get("coarse_centroid_preservation_rmsd_A_mean") or "",
        "protein_ligand_min_distance_A_min": metrics.get("protein_ligand_min_distance_A_min") or "",
        "protein_ligand_min_distance_A_mean": metrics.get("protein_ligand_min_distance_A_mean") or "",
        "protein_ligand_clash_score_mean": metrics.get("protein_ligand_clash_score_mean") or "",
        "clash_relief_selected_angle_rad_mean": metrics.get("clash_relief_selected_angle_rad_mean") or "",
        "clash_relief_applied": bool(clash_relief),
    }


def build_repair(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    out_root: str | Path = DEFAULT_OUT_ROOT,
    salt_bridge_distance_A: float = DEFAULT_SALT_BRIDGE_DISTANCE_A,
    anchor_mode: str = "positive_only",
    clash_relief: bool = False,
    clash_relief_angle_count: int = 24,
    clash_relief_cutoff_A: float = DEFAULT_CLASH_RELIEF_CUTOFF_A,
    generated_at_local: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = _read_csv(input_csv)
    root = _resolve(out_root)
    repaired_rows = [
        _repair_row(
            row,
            out_root=root,
            salt_bridge_distance_A=float(salt_bridge_distance_A),
            anchor_mode=str(anchor_mode),
            clash_relief=bool(clash_relief),
            clash_relief_angle_count=int(clash_relief_angle_count),
            clash_relief_cutoff_A=float(clash_relief_cutoff_A),
        )
        for row in rows
    ]
    ok_rows = [row for row in repaired_rows if row.get("allatom_backmapping_status") == "ok"]
    positive_ok = [
        row for row in ok_rows if _truthy(row.get("is_positive")) or _text(row.get("ligand_id")) == "CHEMBL301265"
    ]
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "pseudo_allatom_repair_ready" if len(ok_rows) == len(repaired_rows) and repaired_rows else "pseudo_allatom_repair_partial",
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": False,
        "input_row_count": len(rows),
        "repaired_row_count": len(ok_rows),
        "failed_row_count": len(repaired_rows) - len(ok_rows),
        "positive_repaired_count": len(positive_ok),
        "min_repaired_atom_count": min((int(row.get("repaired_ligand_frame_atom_count") or 0) for row in ok_rows), default=0),
        "max_repaired_atom_count": max((int(row.get("repaired_ligand_frame_atom_count") or 0) for row in ok_rows), default=0),
        "salt_bridge_distance_A": float(salt_bridge_distance_A),
        "anchor_mode": str(anchor_mode),
        "clash_relief": bool(clash_relief),
        "clash_relief_angle_count": int(clash_relief_angle_count),
        "clash_relief_cutoff_A": float(clash_relief_cutoff_A),
        "out_root": str(root),
        "next_action": "rebuild_atom_window_cache_on_repaired_rows_then_rescore_shadow_only",
        "next_required_step": (
            "Use the repaired selected-row CSV only for shadow diagnostics. Rebuild the atom-window cache on these "
            "pseudo-allatom trajectories, verify cationic-center anchor geometry and pose-survival metrics, then decide "
            "whether a new label-free scorer candidate is justified. Do not promote claims from this repair alone."
        ),
    }
    payload = {
        "packet_type": "gpcr_drd2_pseudo_allatom_backmapping_repair",
        "summary": summary,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "full_100k_claim_review_allowed": False,
            "threshold_relaxation_allowed": False,
        },
        "input_artifacts": {"input_csv": str(_resolve(input_csv))},
        "rows": repaired_rows,
    }
    return payload, repaired_rows


def _render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# GPCR DRD2 Pseudo-Allatom Backmapping Repair",
        "",
        f"- status: `{s['status']}`",
        f"- claim_promotion_allowed: `{str(s['claim_promotion_allowed']).lower()}`",
        f"- repaired_row_count: `{s['repaired_row_count']}`",
        f"- failed_row_count: `{s['failed_row_count']}`",
        f"- positive_repaired_count: `{s['positive_repaired_count']}`",
        f"- min_repaired_atom_count: `{s['min_repaired_atom_count']}`",
        f"- max_repaired_atom_count: `{s['max_repaired_atom_count']}`",
        f"- anchor_mode: `{s.get('anchor_mode', '')}`",
        f"- next_action: `{s['next_action']}`",
        "",
        "## Next Required Step",
        "",
        s["next_required_step"],
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair DRD2 selected rows with pseudo-allatom ligand backmapping.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--out-root", default=DEFAULT_OUT_ROOT)
    parser.add_argument("--salt-bridge-distance-A", type=float, default=DEFAULT_SALT_BRIDGE_DISTANCE_A)
    parser.add_argument(
        "--anchor-mode",
        choices=["positive_only", "all_basic", "none"],
        default="positive_only",
        help="Which rows receive forced cationic-center-to-anchor placement.",
    )
    parser.add_argument(
        "--clash-relief",
        action="store_true",
        help="Sample rotations around the cation-anchor axis to reduce static protein-ligand steric clashes.",
    )
    parser.add_argument("--clash-relief-angle-count", type=int, default=24)
    parser.add_argument("--clash-relief-cutoff-A", type=float, default=DEFAULT_CLASH_RELIEF_CUTOFF_A)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload, rows = build_repair(
        input_csv=args.input_csv,
        out_root=args.out_root,
        salt_bridge_distance_A=float(args.salt_bridge_distance_A),
        anchor_mode=str(args.anchor_mode),
        clash_relief=bool(args.clash_relief),
        clash_relief_angle_count=int(args.clash_relief_angle_count),
        clash_relief_cutoff_A=float(args.clash_relief_cutoff_A),
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, rows)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
