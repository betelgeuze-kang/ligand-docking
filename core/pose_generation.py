"""Multi-start ligand pose generation for independent docking pipeline."""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
except Exception:  # pragma: no cover
    Chem = None
    AllChem = None

POSE_CLAIM_BOUNDARY = (
    "Internal conformer embedding and pocket placement only. "
    "Cross-docking and induced-fit modes are bounded local sampling; "
    "not validated induced-fit or cross-target docking claims."
)

# χ1 rotamer wells (degrees) for common pocket residues — simplified library
_SIDECHAIN_ROTAMERS: dict[str, list[float]] = {
    "SER": [60.0, -60.0, 180.0],
    "THR": [60.0, -60.0, 180.0],
    "TYR": [60.0, -60.0, 180.0],
    "ASP": [0.0, 120.0, -120.0],
    "GLU": [0.0, 120.0, -120.0],
    "LYS": [60.0, 180.0, -60.0],
    "ARG": [60.0, 180.0, -60.0],
    "HIS": [60.0, -60.0, 180.0],
    "PHE": [60.0, -60.0, 180.0],
    "LEU": [60.0, -60.0, 180.0],
    "VAL": [60.0, -60.0],
    "ILE": [60.0, 180.0, -60.0],
    "MET": [60.0, -60.0, 180.0],
    "TRP": [60.0, -60.0, 180.0],
    "ASN": [60.0, -60.0, 180.0],
    "GLN": [60.0, -60.0, 180.0],
}


def _fallback_ligand_beads(n_starts: int) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    for i in range(max(int(n_starts), 1)):
        angle = 2.0 * np.pi * float(i) / max(float(n_starts), 1.0)
        b0 = np.asarray([-1.2 * np.cos(angle), -1.2 * np.sin(angle), 0.0], dtype=np.float32)
        b1 = np.asarray([1.2 * np.cos(angle), 1.2 * np.sin(angle), 0.0], dtype=np.float32)
        out.append(np.stack([b0, b1], axis=0))
    return out


def _embed_smiles_coords(smiles: str, seed: int = 0) -> np.ndarray | None:
    if Chem is None or AllChem is None:
        return None
    mol = Chem.MolFromSmiles(str(smiles or "").strip())
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = int(seed) & 0x7FFFFFFF
    if AllChem.EmbedMolecule(mol, params) != 0:
        return None
    conf = mol.GetConformer()
    coords = np.asarray(
        [[float(conf.GetAtomPosition(i).x), float(conf.GetAtomPosition(i).y), float(conf.GetAtomPosition(i).z)] for i in range(mol.GetNumAtoms())],
        dtype=np.float32,
    )
    return coords


def _rotation_matrix(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    a = np.asarray(axis, dtype=np.float64)
    norm = np.linalg.norm(a)
    if norm < 1e-8:
        return np.eye(3)
    a = a / norm
    x, y, z = a
    c = float(np.cos(angle_rad))
    s = float(np.sin(angle_rad))
    t = 1.0 - c
    return np.asarray(
        [
            [t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c],
        ],
        dtype=np.float64,
    )


def _to_two_bead(full_coords: np.ndarray) -> np.ndarray:
    pts = np.asarray(full_coords, dtype=np.float32)
    if pts.shape[0] < 2:
        return pts.reshape(-1, 3) if pts.size else np.zeros((0, 3), dtype=np.float32)
    center = pts.mean(axis=0, keepdims=True)
    rel = pts - center
    if rel.shape[0] >= 2:
        idx = np.argsort(np.linalg.norm(rel, axis=1))
        return np.stack([pts[idx[0]], pts[idx[-1]]], axis=0)
    return pts[:2]


def place_ligand_in_pocket(
    ligand_coords: np.ndarray,
    pocket_center: np.ndarray,
    *,
    rotation_axis: np.ndarray | None = None,
    rotation_angle_rad: float = 0.0,
) -> np.ndarray:
    """Translate ligand centroid to pocket center with optional rotation."""
    pts = np.asarray(ligand_coords, dtype=np.float64)
    if pts.size == 0:
        return np.zeros((0, 3), dtype=np.float32)
    center = pts.mean(axis=0)
    shifted = pts - center
    if rotation_angle_rad != 0.0:
        axis = rotation_axis if rotation_axis is not None else np.asarray([0.0, 0.0, 1.0])
        shifted = shifted @ _rotation_matrix(axis, float(rotation_angle_rad)).T
    placed = shifted + np.asarray(pocket_center, dtype=np.float64).reshape(1, 3)
    return placed.astype(np.float32)


def generate_pose_ensemble(
    smiles: str,
    pocket_center: np.ndarray | list[float],
    *,
    n_starts: int = 3,
    output_mode: str = "2bead",
    base_seed: int = 0x504F,
) -> dict[str, Any]:
    """Generate multi-start ligand poses placed in the binding pocket."""
    n = max(int(n_starts), 1)
    center = np.asarray(pocket_center, dtype=np.float64).reshape(3)
    poses: list[np.ndarray] = []
    meta_rows: list[dict[str, Any]] = []

    for i in range(n):
        seed = int(base_seed) + i * 17
        full = _embed_smiles_coords(smiles, seed=seed)
        if full is None:
            fb = _fallback_ligand_beads(1)[0]
            placed = place_ligand_in_pocket(fb, center, rotation_angle_rad=2.0 * np.pi * i / n)
        else:
            angle = 2.0 * np.pi * float(i) / float(n)
            placed = place_ligand_in_pocket(full, center, rotation_angle_rad=angle)
        if str(output_mode).lower() == "2bead":
            pose = _to_two_bead(placed)
        else:
            pose = placed
        poses.append(pose)
        meta_rows.append({"start_index": i, "seed": seed, "atom_count": int(pose.shape[0])})

    return {
        "status": "pose_ensemble_ready" if poses else "blocked_no_poses",
        "pose_count": len(poses),
        "poses": poses,
        "pocket_center": center.tolist(),
        "output_mode": str(output_mode),
        "rows": meta_rows,
        "claim_boundary": POSE_CLAIM_BOUNDARY,
    }


def cluster_poses_by_rmsd(
    poses: list[np.ndarray],
    *,
    rmsd_cutoff_a: float = 1.5,
    symmetry_mappings: list[tuple[int, ...]] | None = None,
    max_cluster_diameter_a: float | None = None,
) -> dict[str, Any]:
    """Order-independent RMSD clustering for pose diversity reporting.

    Uses connected components over the RMSD graph instead of the previous greedy
    first-match pass, whose output depended on the order the poses arrived in.
    """

    from betelgeuze_engine.chemistry.pose_clustering import cluster_poses as _cluster_poses_graph

    if not poses:
        return {"cluster_count": 0, "assignments": [], "representative_indices": []}

    usable: list[int] = []
    coords: list[np.ndarray] = []
    for idx, pose in enumerate(poses):
        candidate = np.asarray(pose, dtype=np.float64)
        if candidate.size == 0:
            continue
        usable.append(idx)
        coords.append(candidate)
    if not coords:
        return {
            "cluster_count": 0,
            "assignments": [-1 for _ in poses],
            "representative_indices": [],
        }

    result = _cluster_poses_graph(
        coords,
        scores=[float(position) for position in range(len(coords))],
        symmetry_mappings=symmetry_mappings,
        threshold_a=float(rmsd_cutoff_a),
        max_cluster_diameter_a=max_cluster_diameter_a,
    )
    assignments = [-1 for _ in poses]
    for position, cluster_id in result.assignments.items():
        assignments[usable[int(position)]] = int(cluster_id)
    representative_indices = [
        usable[int(cluster.representative_pose_index)] for cluster in result.clusters
    ]
    return {
        "cluster_count": int(result.cluster_count),
        "assignments": assignments,
        "representative_indices": representative_indices,
        "clustering_algorithm": result.method,
        "order_independent": True,
        "rmsd_cutoff_a": float(rmsd_cutoff_a),
    }


def sample_sidechain_rotamers(
    pocket_residue_atoms: list[dict[str, Any]],
    *,
    max_residues: int = 8,
) -> list[dict[str, Any]]:
    """Sample χ1 rotamer states for pocket residues (CA + SC virtual bead proxy)."""
    grouped: dict[tuple[str, str, str], list[np.ndarray]] = {}
    for atom in pocket_residue_atoms:
        key = (str(atom.get("chain_id", "_")), str(atom.get("resname", "UNK")), str(atom.get("residue_id", "0")))
        xyz = atom.get("xyz")
        if xyz is None:
            continue
        grouped.setdefault(key, []).append(np.asarray(xyz, dtype=np.float64))

    states: list[dict[str, Any]] = []
    for idx, (key, coords_list) in enumerate(sorted(grouped.items())[: int(max_residues)]):
        chain_id, resname, residue_id = key
        ca = coords_list[0]
        rotamers = _SIDECHAIN_ROTAMERS.get(resname.upper(), [60.0, -60.0, 180.0])
        for chi1_deg in rotamers:
            rad = np.deg2rad(float(chi1_deg))
            sc = ca + np.asarray([1.5 * np.cos(rad), 1.5 * np.sin(rad), 0.4], dtype=np.float64)
            states.append(
                {
                    "chain_id": chain_id,
                    "resname": resname,
                    "residue_id": residue_id,
                    "chi1_deg": float(chi1_deg),
                    "ca_xyz": ca.tolist(),
                    "sc_xyz": sc.tolist(),
                }
            )
    return states


def induced_fit_relax(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    sidechain_states: list[dict[str, Any]] | None = None,
    *,
    max_steps: int = 6,
    step_a: float = 0.15,
) -> dict[str, Any]:
    """Minor pocket atom displacement toward ligand (bounded induced-fit proxy)."""
    prot = np.asarray(protein_xyz, dtype=np.float32).copy()
    lig = np.asarray(ligand_xyz, dtype=np.float32)
    if prot.size == 0 or lig.size == 0:
        return {"status": "blocked", "protein_xyz": prot, "ligand_xyz": lig, "displacement_a": 0.0}
    lig_center = lig.mean(axis=0)
    total_disp = 0.0
    for _ in range(max(int(max_steps), 1)):
        dist = np.linalg.norm(prot - lig_center.reshape(1, 3), axis=1)
        near = dist < 6.0
        if not np.any(near):
            break
        direction = lig_center.reshape(1, 3) - prot[near]
        norms = np.linalg.norm(direction, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-6)
        delta = float(step_a) * direction / norms
        prot[near] += delta.astype(np.float32)
        total_disp += float(np.sum(np.linalg.norm(delta, axis=1)))
    sc_count = len(sidechain_states or [])
    return {
        "status": "induced_fit_relaxed",
        "protein_xyz": prot,
        "ligand_xyz": lig,
        "displacement_a": total_disp,
        "sidechain_states_applied": sc_count,
        "claim_boundary": POSE_CLAIM_BOUNDARY,
    }


def generate_cross_docking_poses(
    smiles: str,
    apo_protein_xyz: np.ndarray,
    *,
    holo_ligand_xyz: np.ndarray | None = None,
    n_starts: int = 4,
    induced_fit: bool = True,
    output_mode: str = "2bead",
) -> dict[str, Any]:
    """Cross-docking: apo pocket + ligand conformer; optional holo pocket hint."""
    from core.pocket_detection import detect_binding_pocket

    apo = np.asarray(apo_protein_xyz, dtype=np.float32)
    holo = np.asarray(holo_ligand_xyz, dtype=np.float32) if holo_ligand_xyz is not None else None
    pocket = detect_binding_pocket(apo, holo)
    center = np.asarray(pocket.get("pocket_center", [0.0, 0.0, 0.0]), dtype=np.float64)
    base = generate_pose_ensemble(smiles, center, n_starts=n_starts, output_mode=output_mode)
    relaxed_poses: list[np.ndarray] = []
    for pose in base.get("poses", []):
        lig = np.asarray(pose, dtype=np.float32)
        if induced_fit and apo.size and lig.size:
            fit = induced_fit_relax(apo, lig)
            relaxed_poses.append(np.asarray(fit["ligand_xyz"], dtype=np.float32))
        else:
            relaxed_poses.append(lig)
    base["poses"] = relaxed_poses
    base["mode"] = "cross_docking"
    base["pocket_method"] = pocket.get("method", "")
    base["induced_fit"] = bool(induced_fit)
    return base
