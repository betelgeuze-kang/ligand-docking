from __future__ import annotations

import math
from typing import Any

import numpy as np

try:
    from rdkit import Chem
    from rdkit.Chem import rdDistGeom
except Exception:
    Chem = None
    rdDistGeom = None

_CG_BEAD_PER_RESIDUE = 4


def generate_conformers(smiles: str, num_poses: int, seed: int) -> np.ndarray | None:
    if Chem is None or rdDistGeom is None:
        return None
    mol = Chem.MolFromSmiles(str(smiles))
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    params = rdDistGeom.ETKDGv3()
    params.randomSeed = int(seed)
    params.pruneRmsThresh = 0.5
    params.numThreads = 0
    conf_ids = rdDistGeom.EmbedMultipleConfs(
        mol,
        numConfs=int(max(1, num_poses)),
        params=params,
    )
    if not conf_ids:
        return None
    result_ids = list(conf_ids)
    if len(result_ids) > int(num_poses):
        result_ids = result_ids[: int(num_poses)]
    mol = Chem.RemoveHs(mol)
    poses = []
    for cid in result_ids:
        conf = mol.GetConformer(cid)
        poses.append(conf.GetPositions())
    return np.array(poses, dtype=np.float32) if poses else None


def center_coordinates_around_origin(coords: np.ndarray) -> np.ndarray:
    center = coords.mean(axis=0)
    return coords - center


def place_pose_in_pocket(pose: np.ndarray, pocket_center: np.ndarray) -> np.ndarray:
    shifted = center_coordinates_around_origin(np.asarray(pose, dtype=np.float32))
    return shifted + np.asarray(pocket_center, dtype=np.float32).reshape(1, 3)


def pose_rmsd(a: np.ndarray, b: np.ndarray) -> float:
    left = np.asarray(a, dtype=np.float64)
    right = np.asarray(b, dtype=np.float64)
    n = min(int(left.shape[0]), int(right.shape[0]))
    if n <= 0:
        return float("inf")
    return float(np.sqrt(np.mean(np.sum((left[:n] - right[:n]) ** 2, axis=1))))


def clash_count(protein_beads: np.ndarray, ligand_coords: np.ndarray, *, clash_cutoff_a: float = 1.2) -> int:
    prot = np.asarray(protein_beads, dtype=np.float64)
    lig = np.asarray(ligand_coords, dtype=np.float64)
    if prot.size == 0 or lig.size == 0:
        return 0
    distances = np.linalg.norm(prot[:, None, :] - lig[None, :, :], axis=2)
    return int(np.sum(distances < float(clash_cutoff_a)))


def chemistry_validity_summary(ligand_valid: dict[str, Any], pose_coords: np.ndarray) -> dict[str, Any]:
    finite_coords = bool(np.isfinite(np.asarray(pose_coords, dtype=np.float64)).all())
    blockers = list(ligand_valid.get("blockers") or [])
    if not finite_coords:
        blockers.append("nonfinite_pose_coordinates")
    valid = bool(ligand_valid.get("valid") is True and finite_coords and not blockers)
    return {
        "status": "chemical_validity_pass" if valid else "blocked_chemical_validity",
        "valid": valid,
        "claim_blockers": blockers,
        "atom_count": int(ligand_valid.get("atom_count") or 0),
        "bond_count": int(ligand_valid.get("bond_count") or 0),
        "formal_charge_sum": int(sum(int(v) for v in ligand_valid.get("formal_charges", []) or [])),
        "chirality_status": str(ligand_valid.get("chirality_status") or "not_assessed"),
        "protonation_status": str(ligand_valid.get("protonation_status") or "not_assessed"),
        "tautomer_status": str(ligand_valid.get("tautomer_status") or "not_assessed"),
        "coordinate_finite": finite_coords,
    }


def random_rotation_matrix(seed: int) -> np.ndarray:
    rng = np.random.RandomState(int(seed))
    v = rng.randn(3)
    v /= np.linalg.norm(v)
    theta = rng.uniform(0, 2 * math.pi)
    c = math.cos(theta)
    s = math.sin(theta)
    t = 1 - c
    x, y, z = v
    return np.array(
        [
            [c + x * x * t, x * y * t - z * s, x * z * t + y * s],
            [y * x * t + z * s, c + y * y * t, y * z * t - x * s],
            [z * x * t - y * s, z * y * t + x * s, c + z * z * t],
        ],
        dtype=np.float64,
    )


def virtual_protein_coords(protein_ca: np.ndarray) -> np.ndarray:
    n_res = protein_ca.shape[0]
    beads = np.zeros((n_res * _CG_BEAD_PER_RESIDUE, 3), dtype=np.float32)
    for i in range(n_res):
        ca = protein_ca[i].astype(np.float64)
        base = i * _CG_BEAD_PER_RESIDUE
        beads[base + 0] = ca + np.array([0.0, 0.0, 0.0], dtype=np.float64)
        beads[base + 1] = ca + np.array([1.2, 0.0, 0.0], dtype=np.float64)
        beads[base + 2] = ca + np.array([-0.8, 0.9, 0.0], dtype=np.float64)
        beads[base + 3] = ca + np.array([-0.8, -0.9, 0.0], dtype=np.float64)
    return beads.astype(np.float32)


def resolve_pocket_indices(protein_ca: np.ndarray, ligand_center: np.ndarray | None, cutoff_a: float) -> list[int]:
    n_res = protein_ca.shape[0]
    if n_res == 0:
        return []
    if ligand_center is None:
        return list(range(n_res))
    distances = np.linalg.norm(protein_ca - np.array(ligand_center, dtype=np.float64), axis=1)
    return [int(i) for i in range(n_res) if distances[i] <= float(cutoff_a)]
