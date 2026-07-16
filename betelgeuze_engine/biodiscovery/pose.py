from __future__ import annotations

import math
from typing import Any

import numpy as np

from betelgeuze_engine.chemistry.ligand_states import ligand_chemistry_state_from_smiles

try:
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem import rdDistGeom
except Exception:
    Chem = None
    rdMolDescriptors = None
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


def _validated_pose_coordinates(value: np.ndarray, *, label: str) -> np.ndarray:
    coords = np.asarray(value, dtype=np.float64)
    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError(f"{label} must have shape [N, 3]")
    if int(coords.shape[0]) <= 0:
        raise ValueError(f"{label} must contain at least one atom")
    if not np.isfinite(coords).all():
        raise ValueError(f"{label} contains non-finite coordinates")
    return coords


def _validated_pose_pair(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    left = _validated_pose_coordinates(a, label="left pose")
    right = _validated_pose_coordinates(b, label="right pose")
    if left.shape != right.shape:
        raise ValueError(
            "pose coordinate shapes must match exactly; "
            f"left={tuple(left.shape)} right={tuple(right.shape)}"
        )
    return left, right


def _strict_symmetry_mappings(
    symmetry_mappings: list[tuple[int, ...]] | None,
    *,
    atom_count: int,
) -> list[tuple[int, ...]]:
    identity = tuple(range(int(atom_count)))
    if not symmetry_mappings:
        return [identity]
    mappings: list[tuple[int, ...]] = [identity]
    seen = {identity}
    expected = set(identity)
    for mapping_index, mapping in enumerate(symmetry_mappings):
        values: list[int] = []
        for value in mapping:
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
                raise ValueError(
                    f"symmetry mapping {mapping_index} must contain integer atom indices"
                )
            values.append(int(value))
        normalized = tuple(values)
        if len(normalized) != int(atom_count):
            raise ValueError(
                f"symmetry mapping {mapping_index} must contain exactly {atom_count} indices"
            )
        if set(normalized) != expected:
            raise ValueError(
                f"symmetry mapping {mapping_index} must be a full atom-index bijection"
            )
        if normalized not in seen:
            seen.add(normalized)
            mappings.append(normalized)
    return mappings


def pose_rmsd(a: np.ndarray, b: np.ndarray) -> float:
    """Return direct receptor-frame RMSD for exactly matching atom coordinates."""

    left, right = _validated_pose_pair(a, b)
    return float(np.sqrt(np.mean(np.sum((left - right) ** 2, axis=1))))


def _kabsch_align(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    left, right = _validated_pose_pair(reference, candidate)
    left_centered = left - left.mean(axis=0, keepdims=True)
    right_centered = right - right.mean(axis=0, keepdims=True)
    covariance = right_centered.T @ left_centered
    u, _singular_values, vt = np.linalg.svd(covariance)
    rotation = u @ vt
    if float(np.linalg.det(rotation)) < 0.0:
        u = u.copy()
        u[:, -1] *= -1.0
        rotation = u @ vt
    return right_centered @ rotation


def aligned_pose_rmsd(a: np.ndarray, b: np.ndarray) -> float:
    """Return Kabsch-aligned RMSD for exactly matching atom coordinates."""

    left, right = _validated_pose_pair(a, b)
    left_centered = left - left.mean(axis=0, keepdims=True)
    right_aligned = _kabsch_align(left, right)
    return float(np.sqrt(np.mean(np.sum((left_centered - right_aligned) ** 2, axis=1))))


def best_symmetry_mapped_pose(
    reference: np.ndarray,
    candidate: np.ndarray,
    symmetry_mappings: list[tuple[int, ...]] | None = None,
    *,
    align: bool = False,
) -> tuple[np.ndarray, float, tuple[int, ...]]:
    """Return the candidate atom ordering with the lowest strict RMSD."""

    left, right = _validated_pose_pair(reference, candidate)
    mappings = _strict_symmetry_mappings(
        symmetry_mappings,
        atom_count=int(left.shape[0]),
    )
    best_coords = right
    best_mapping = mappings[0]
    best = float("inf")
    for mapping in mappings:
        mapped = right[np.asarray(mapping, dtype=np.int64)]
        value = aligned_pose_rmsd(left, mapped) if align else pose_rmsd(left, mapped)
        if value < best:
            best = float(value)
            best_coords = mapped
            best_mapping = mapping
    return np.asarray(best_coords, dtype=np.float64).copy(), float(best), best_mapping

def rotatable_bond_count(smiles: str) -> int:
    if Chem is None or rdMolDescriptors is None:
        return 0
    mol = Chem.MolFromSmiles(str(smiles or ""))
    if mol is None:
        return 0
    return int(rdMolDescriptors.CalcNumRotatableBonds(mol))


def conformer_diversity_diagnostics(
    poses: np.ndarray,
    *,
    smiles: str = "",
    diversity_threshold_a: float = 0.5,
) -> dict[str, Any]:
    conformers = np.asarray(poses, dtype=np.float64)
    if conformers.ndim != 3 or conformers.shape[-1] != 3:
        raise ValueError("conformer ensemble must have shape [C, N, 3]")
    if int(conformers.shape[0]) <= 0 or int(conformers.shape[1]) <= 0:
        raise ValueError("conformer ensemble must contain at least one conformer and atom")
    if not np.isfinite(conformers).all():
        raise ValueError("conformer ensemble contains non-finite coordinates")
    count = int(conformers.shape[0])
    symmetry_mappings = ligand_symmetry_mappings(smiles) if smiles else []
    rmsd_values: list[float] = []
    for i in range(count):
        for j in range(i + 1, count):
            rmsd_values.append(
                aligned_symmetry_aware_pose_rmsd(
                    conformers[i],
                    conformers[j],
                    symmetry_mappings,
                )
            )
    finite = [float(value) for value in rmsd_values if math.isfinite(float(value))]
    if count <= 1:
        status = "single_conformer_no_pairwise_diversity"
    elif finite and max(finite) >= float(diversity_threshold_a):
        status = "rotatable_conformer_diversity_measured"
    else:
        status = "low_conformer_diversity_measured"
    return {
        "schema_version": "tier_beta_conformer_diversity_v1",
        "status": status,
        "method": (
            "kabsch_aligned_rdkit_automorphism_min_heavy_atom_rmsd"
            if symmetry_mappings
            else "kabsch_aligned_identity_heavy_atom_rmsd"
        ),
        "alignment": "kabsch",
        "coordinate_frame_invariant": True,
        "atom_mapping_contract": "strict_full_atom_bijection",
        "symmetry_mapping_count": int(len(symmetry_mappings) if symmetry_mappings else 1),
        "atom_count": int(conformers.shape[1]),
        "rotatable_bond_count": rotatable_bond_count(smiles) if smiles else 0,
        "conformer_count": count,
        "pairwise_rmsd_count": int(len(finite)),
        "pairwise_rmsd_min_a": min(finite) if finite else 0.0,
        "pairwise_rmsd_mean_a": float(sum(finite) / len(finite)) if finite else 0.0,
        "pairwise_rmsd_max_a": max(finite) if finite else 0.0,
        "diversity_threshold_a": float(diversity_threshold_a),
        "diverse_pair_count": int(sum(1 for value in finite if value >= float(diversity_threshold_a))),
        "claim_boundary": (
            "Kabsch-aligned, symmetry-aware generated-conformer spread only; not an exhaustive rotamer search or "
            "benchmarked pose-diversity guarantee."
        ),
    }

def ligand_symmetry_mappings(smiles: str, *, max_mappings: int = 256) -> list[tuple[int, ...]]:
    if Chem is None:
        return []
    mol = Chem.MolFromSmiles(str(smiles or ""))
    if mol is None:
        return []
    atom_count = int(mol.GetNumAtoms())
    identity = tuple(range(atom_count))
    try:
        matches = mol.GetSubstructMatches(mol, uniquify=False, maxMatches=int(max_mappings))
    except Exception:
        matches = ()
    mappings: list[tuple[int, ...]] = [identity]
    seen = {identity}
    expected = set(identity)
    for match in matches:
        mapping = tuple(int(idx) for idx in match)
        if len(mapping) != atom_count or set(mapping) != expected or mapping in seen:
            continue
        seen.add(mapping)
        mappings.append(mapping)
    return mappings


def symmetry_aware_pose_rmsd(
    a: np.ndarray,
    b: np.ndarray,
    symmetry_mappings: list[tuple[int, ...]] | None = None,
) -> float:
    """Return strict direct RMSD minimized over full atom-index automorphisms."""

    _mapped, best, _mapping = best_symmetry_mapped_pose(
        a,
        b,
        symmetry_mappings,
        align=False,
    )
    return float(best)


def aligned_symmetry_aware_pose_rmsd(
    a: np.ndarray,
    b: np.ndarray,
    symmetry_mappings: list[tuple[int, ...]] | None = None,
) -> float:
    """Return Kabsch-aligned RMSD minimized over full atom-index automorphisms."""

    _mapped, best, _mapping = best_symmetry_mapped_pose(
        a,
        b,
        symmetry_mappings,
        align=True,
    )
    return float(best)

def cluster_poses_by_symmetry(
    pose_scores: list[dict[str, Any]],
    placed_pose_coords: dict[int, np.ndarray],
    symmetry_mappings: list[tuple[int, ...]],
    *,
    threshold_a: float = 2.0,
) -> dict[str, Any]:
    clusters: list[dict[str, Any]] = []
    for row in pose_scores:
        pose_index = int(row["pose_index"])
        coords = placed_pose_coords[pose_index]
        assigned_cluster = -1
        assigned_rmsd = float("inf")
        for cluster_idx, cluster in enumerate(clusters):
            representative = placed_pose_coords[int(cluster["representative_pose_index"])]
            rmsd = symmetry_aware_pose_rmsd(coords, representative, symmetry_mappings)
            if rmsd <= float(threshold_a):
                assigned_cluster = cluster_idx
                assigned_rmsd = rmsd
                break
        if assigned_cluster < 0:
            assigned_cluster = len(clusters)
            assigned_rmsd = 0.0
            clusters.append(
                {
                    "cluster_id": int(assigned_cluster),
                    "representative_pose_index": pose_index,
                    "member_pose_indices": [],
                    "best_composite_score": float(row.get("composite_score", float("inf"))),
                }
            )
        clusters[assigned_cluster]["member_pose_indices"].append(pose_index)
        row["pose_cluster_id"] = int(assigned_cluster)
        row["symmetry_aware_pose_rmsd_to_cluster_representative_a"] = float(assigned_rmsd)
        row["pose_rmsd_clustering"] = {
            "schema_version": "tier_beta_pose_rmsd_clustering_v1",
            "method": "rdkit_automorphism_min_rmsd" if symmetry_mappings else "identity_atom_order_rmsd",
            "threshold_a": float(threshold_a),
            "symmetry_mapping_count": int(len(symmetry_mappings) if symmetry_mappings else 1),
            "atom_mapping_contract": "strict_full_atom_bijection",
            "coordinate_frame": "receptor_frame_no_alignment",
            "cluster_id": int(assigned_cluster),
            "cluster_representative_pose_index": int(clusters[assigned_cluster]["representative_pose_index"]),
        }
    for cluster in clusters:
        cluster["member_count"] = int(len(cluster["member_pose_indices"]))
    return {
        "status": "symmetry_aware_rmsd_clustered",
        "method": "rdkit_automorphism_min_rmsd" if symmetry_mappings else "identity_atom_order_rmsd",
        "threshold_a": float(threshold_a),
        "symmetry_mapping_count": int(len(symmetry_mappings) if symmetry_mappings else 1),
        "atom_mapping_contract": "strict_full_atom_bijection",
        "coordinate_frame": "receptor_frame_no_alignment",
        "cluster_count": int(len(clusters)),
        "clusters": clusters,
    }


def chemical_anchor_mapping(smiles: str, ligand_valid: dict[str, Any]) -> dict[str, Any]:
    if Chem is None:
        atom_elements = list(ligand_valid.get("atom_elements") or [])
        atom_count = int(ligand_valid.get("atom_count") or len(atom_elements))
        fallback_indices = list(range(min(4, atom_count)))
        return {
            "schema_version": "tier_beta_ligand_anchor_mapping_v1",
            "status": "fallback_atom_order_anchor_mapping",
            "method": "fallback_atom_order",
            "claim_safe": False,
            "blocked_reason": "rdkit_unavailable",
            "atom_count": atom_count,
            "two_bead_anchor_atom_indices": fallback_indices[:2],
            "four_bead_anchor_atom_indices": fallback_indices,
            "anchor_rows": [
                {
                    "atom_idx": int(idx),
                    "element": str(atom_elements[idx]) if idx < len(atom_elements) else "",
                    "roles": [],
                    "formal_charge": 0,
                    "ring": False,
                    "aromatic": False,
                    "selection_reason": "fallback_atom_order",
                }
                for idx in fallback_indices
            ],
        }
    mol = Chem.MolFromSmiles(str(smiles or ""))
    if mol is None or mol.GetNumAtoms() <= 0:
        return {
            "schema_version": "tier_beta_ligand_anchor_mapping_v1",
            "status": "blocked_invalid_ligand_anchor_mapping",
            "method": "rdkit_feature_charge_ring_graph",
            "claim_safe": False,
            "blocked_reason": "invalid_smiles",
            "atom_count": 0,
            "two_bead_anchor_atom_indices": [],
            "four_bead_anchor_atom_indices": [],
            "anchor_rows": [],
        }
    chemistry = ligand_chemistry_state_from_smiles(str(smiles or ""))
    roles_by_atom: dict[int, list[str]] = {}
    for site in chemistry.feature_sites:
        roles_by_atom.setdefault(int(site.atom_idx), []).append(str(site.role))
    atom_count = int(mol.GetNumAtoms())
    distance_matrix = Chem.GetDistanceMatrix(mol)

    def atom_priority(idx: int) -> tuple[int, int, int, int]:
        atom = mol.GetAtomWithIdx(int(idx))
        roles = roles_by_atom.get(int(idx), [])
        has_feature = bool(roles)
        charged = int(atom.GetFormalCharge()) != 0
        hetero = int(atom.GetAtomicNum()) not in {1, 6}
        ring = bool(atom.IsInRing())
        return (
            0 if charged else 1,
            0 if has_feature else 1,
            0 if hetero else 1,
            0 if ring else 1,
        )

    ordered = sorted(range(atom_count), key=lambda idx: (*atom_priority(idx), int(idx)))
    selected: list[int] = []
    for idx in ordered:
        if not selected:
            selected.append(int(idx))
            continue
        candidate_dist = min(float(distance_matrix[int(idx), chosen]) for chosen in selected)
        best_existing = max(
            (
                min(float(distance_matrix[other, chosen]) for chosen in selected)
                for other in range(atom_count)
                if other not in selected
            ),
            default=0.0,
        )
        if candidate_dist + 1e-8 >= best_existing or len(selected) >= atom_count - 1:
            selected.append(int(idx))
        if len(selected) >= min(4, atom_count):
            break
    for idx in ordered:
        if len(selected) >= min(4, atom_count):
            break
        if idx not in selected:
            selected.append(int(idx))
    primary = selected[0] if selected else 0
    if atom_count <= 1:
        two_bead = [primary]
    else:
        secondary = max(
            (idx for idx in range(atom_count) if idx != primary),
            key=lambda idx: (float(distance_matrix[primary, idx]), -atom_priority(idx)[0], -atom_priority(idx)[1]),
        )
        two_bead = [int(primary), int(secondary)]

    four_set = [int(idx) for idx in selected[: min(4, atom_count)]]

    def row_for(idx: int, reason: str) -> dict[str, Any]:
        atom = mol.GetAtomWithIdx(int(idx))
        roles = sorted(set(roles_by_atom.get(int(idx), [])))
        if int(atom.GetFormalCharge()) != 0:
            reason = "formal_charge_anchor"
        elif roles:
            reason = "chemical_feature_anchor"
        elif atom.IsInRing():
            reason = "ring_graph_diversity_anchor"
        return {
            "atom_idx": int(idx),
            "element": str(atom.GetSymbol()),
            "roles": roles,
            "formal_charge": int(atom.GetFormalCharge()),
            "ring": bool(atom.IsInRing()),
            "aromatic": bool(atom.GetIsAromatic()),
            "selection_reason": reason,
        }

    anchor_rows = [
        row_for(idx, "graph_diversity_anchor")
        for idx in dict.fromkeys([*two_bead, *four_set])
    ]
    return {
        "schema_version": "tier_beta_ligand_anchor_mapping_v1",
        "status": "rdkit_feature_charge_ring_graph_anchor_mapping",
        "method": "rdkit_feature_charge_ring_graph",
        "claim_safe": True,
        "blocked_reason": "",
        "atom_count": atom_count,
        "two_bead_anchor_atom_indices": two_bead,
        "four_bead_anchor_atom_indices": four_set,
        "anchor_rows": anchor_rows,
        "feature_source": chemistry.feature_source,
        "graph_distance_source": "rdkit_topological_distance_matrix",
    }


def clash_count(protein_beads: np.ndarray, ligand_coords: np.ndarray, *, clash_cutoff_a: float = 1.2) -> int:
    prot = np.asarray(protein_beads, dtype=np.float64)
    lig = np.asarray(ligand_coords, dtype=np.float64)
    if prot.size == 0 or lig.size == 0:
        return 0
    distances = np.linalg.norm(prot[:, None, :] - lig[None, :, :], axis=2)
    return int(np.sum(distances < float(clash_cutoff_a)))


def coarse_pose_score(
    protein_beads: np.ndarray,
    ligand_coords: np.ndarray,
    *,
    clash_cutoff_a: float = 1.2,
    contact_cutoff_a: float = 8.0,
) -> dict[str, Any]:
    prot = np.asarray(protein_beads, dtype=np.float64)
    lig = np.asarray(ligand_coords, dtype=np.float64)
    if prot.size == 0 or lig.size == 0:
        return {
            "score": float("inf"),
            "min_distance_a": float("inf"),
            "contact_count": 0,
            "clash_count": 0,
            "clash_penalty": float("inf"),
            "contact_reward": 0.0,
        }
    distances = np.linalg.norm(prot[:, None, :] - lig[None, :, :], axis=2)
    min_distance = float(np.min(distances))
    clash_depth = np.maximum(0.0, float(clash_cutoff_a) - distances)
    clash_penalty = float(np.sum(clash_depth * clash_depth) * 100.0)
    contacts = distances <= float(contact_cutoff_a)
    contact_count = int(np.sum(contacts))
    contact_reward = float(np.sum(np.exp(-distances[contacts] / max(float(contact_cutoff_a), 1e-6)))) if contact_count else 0.0
    ligand_min_distances = np.min(distances, axis=0)
    pocket_fit_penalty = float(np.mean(np.maximum(0.0, ligand_min_distances - float(contact_cutoff_a))))
    score = float(clash_penalty + pocket_fit_penalty - 0.05 * contact_reward)
    return {
        "score": score,
        "min_distance_a": min_distance,
        "contact_count": contact_count,
        "clash_count": int(np.sum(distances < float(clash_cutoff_a))),
        "clash_penalty": clash_penalty,
        "contact_reward": contact_reward,
        "pocket_fit_penalty": pocket_fit_penalty,
    }


def _rotation_matrix_from_vector(rotation_rad: np.ndarray) -> np.ndarray:
    vector = np.asarray(rotation_rad, dtype=np.float64).reshape(3)
    theta = float(np.linalg.norm(vector))
    if theta < 1e-12:
        return np.eye(3, dtype=np.float64)
    axis = vector / theta
    x, y, z = axis
    c = math.cos(theta)
    s = math.sin(theta)
    t = 1.0 - c
    return np.array(
        [
            [c + x * x * t, x * y * t - z * s, x * z * t + y * s],
            [y * x * t + z * s, c + y * y * t, y * z * t - x * s],
            [z * x * t - y * s, z * y * t + x * s, c + z * z * t],
        ],
        dtype=np.float64,
    )


def _apply_rigid_body_delta(
    ligand_coords: np.ndarray,
    translation_a: np.ndarray,
    rotation_rad: np.ndarray,
) -> np.ndarray:
    coords = np.asarray(ligand_coords, dtype=np.float64)
    center = coords.mean(axis=0)
    rotation = _rotation_matrix_from_vector(rotation_rad)
    shifted = coords - center.reshape(1, 3)
    rotated = shifted @ rotation.T
    return (rotated + center.reshape(1, 3) + np.asarray(translation_a, dtype=np.float64).reshape(1, 3)).astype(
        np.float32
    )


def local_rigid_body_minimize_pose(
    protein_beads: np.ndarray,
    ligand_coords: np.ndarray,
    *,
    max_steps: int = 6,
    initial_step_a: float = 0.25,
    initial_rotation_step_rad: float = 0.08,
    clash_cutoff_a: float = 1.2,
) -> tuple[np.ndarray, dict[str, Any]]:
    coords = np.asarray(ligand_coords, dtype=np.float32).copy()
    current = coarse_pose_score(protein_beads, coords, clash_cutoff_a=clash_cutoff_a)
    initial_score = float(current["score"])
    total_delta = np.zeros(3, dtype=np.float32)
    total_rotation = np.zeros(3, dtype=np.float32)
    translation_probe_a = max(float(initial_step_a) * 0.25, 1e-3)
    rotation_probe_rad = max(float(initial_rotation_step_rad) * 0.25, 1e-4)
    parameter_probe = np.asarray(
        [
            translation_probe_a,
            translation_probe_a,
            translation_probe_a,
            rotation_probe_rad,
            rotation_probe_rad,
            rotation_probe_rad,
        ],
        dtype=np.float64,
    )
    parameter_step = np.asarray(
        [
            max(float(initial_step_a), 1e-6),
            max(float(initial_step_a), 1e-6),
            max(float(initial_step_a), 1e-6),
            max(float(initial_rotation_step_rad), 1e-6),
            max(float(initial_rotation_step_rad), 1e-6),
            max(float(initial_rotation_step_rad), 1e-6),
        ],
        dtype=np.float64,
    )
    steps_taken = 0
    line_search_backtracks = 0
    initial_gradient_norm = 0.0
    final_gradient_norm = 0.0
    for _idx in range(int(max(0, max_steps))):
        gradient = np.zeros(6, dtype=np.float64)
        for axis in range(6):
            plus = np.zeros(6, dtype=np.float64)
            minus = np.zeros(6, dtype=np.float64)
            plus[axis] = parameter_probe[axis]
            minus[axis] = -parameter_probe[axis]
            plus_coords = _apply_rigid_body_delta(coords, plus[:3], plus[3:])
            minus_coords = _apply_rigid_body_delta(coords, minus[:3], minus[3:])
            plus_score = coarse_pose_score(protein_beads, plus_coords, clash_cutoff_a=clash_cutoff_a)
            minus_score = coarse_pose_score(protein_beads, minus_coords, clash_cutoff_a=clash_cutoff_a)
            derivative = (float(plus_score["score"]) - float(minus_score["score"])) / (2.0 * parameter_probe[axis])
            gradient[axis] = derivative * parameter_step[axis]
        gradient_norm = float(np.linalg.norm(gradient))
        if steps_taken == 0:
            initial_gradient_norm = gradient_norm
        final_gradient_norm = gradient_norm
        if not math.isfinite(gradient_norm) or gradient_norm < 1e-10:
            break

        direction = -gradient / gradient_norm
        accepted = False
        line_scale = 1.0
        for _backtrack_idx in range(8):
            parameter_delta = direction * parameter_step * line_scale
            candidate_coords = _apply_rigid_body_delta(coords, parameter_delta[:3], parameter_delta[3:])
            candidate_score = coarse_pose_score(protein_beads, candidate_coords, clash_cutoff_a=clash_cutoff_a)
            if float(candidate_score["score"]) + 1e-8 < float(current["score"]):
                coords = candidate_coords.astype(np.float32)
                current = candidate_score
                total_delta += parameter_delta[:3].astype(np.float32)
                total_rotation += parameter_delta[3:].astype(np.float32)
                steps_taken += 1
                accepted = True
                break
            line_scale *= 0.5
            line_search_backtracks += 1
        if not accepted:
            break
    final_score = float(current["score"])
    improved = bool(final_score + 1e-8 < initial_score)
    return coords.astype(np.float32), {
        "status": (
            "finite_difference_rigid_body_gradient_minimized"
            if improved
            else "finite_difference_rigid_body_gradient_no_improvement"
        ),
        "method": "finite_difference_gradient_descent_translation_rotation",
        "degrees_of_freedom": ["translation", "rotation"],
        "gradient_parameter_count": 6,
        "steps_taken": int(steps_taken),
        "line_search_backtracks": int(line_search_backtracks),
        "initial_coarse_score": initial_score,
        "final_coarse_score": final_score,
        "improved": improved,
        "translation_delta_a": [float(v) for v in total_delta.tolist()],
        "rotation_delta_rad": [float(v) for v in total_rotation.tolist()],
        "initial_gradient_norm": float(initial_gradient_norm),
        "final_gradient_norm": float(final_gradient_norm),
    }


def local_translation_minimize_pose(
    protein_beads: np.ndarray,
    ligand_coords: np.ndarray,
    *,
    max_steps: int = 6,
    initial_step_a: float = 0.25,
    clash_cutoff_a: float = 1.2,
) -> tuple[np.ndarray, dict[str, Any]]:
    coords = np.asarray(ligand_coords, dtype=np.float32).copy()
    directions = [
        np.asarray([1.0, 0.0, 0.0], dtype=np.float32),
        np.asarray([-1.0, 0.0, 0.0], dtype=np.float32),
        np.asarray([0.0, 1.0, 0.0], dtype=np.float32),
        np.asarray([0.0, -1.0, 0.0], dtype=np.float32),
        np.asarray([0.0, 0.0, 1.0], dtype=np.float32),
        np.asarray([0.0, 0.0, -1.0], dtype=np.float32),
    ]
    current = coarse_pose_score(protein_beads, coords, clash_cutoff_a=clash_cutoff_a)
    initial_score = float(current["score"])
    total_delta = np.zeros(3, dtype=np.float32)
    step = float(initial_step_a)
    steps_taken = 0
    for _idx in range(int(max(0, max_steps))):
        best_coords = coords
        best_delta = np.zeros(3, dtype=np.float32)
        best_score = current
        for direction in directions:
            candidate_delta = direction * step
            candidate_coords = coords + candidate_delta.reshape(1, 3)
            candidate_score = coarse_pose_score(
                protein_beads,
                candidate_coords,
                clash_cutoff_a=clash_cutoff_a,
            )
            if float(candidate_score["score"]) + 1e-8 < float(best_score["score"]):
                best_coords = candidate_coords.astype(np.float32)
                best_delta = candidate_delta.astype(np.float32)
                best_score = candidate_score
        if best_coords is coords:
            step *= 0.5
            if step < 0.025:
                break
            continue
        coords = best_coords
        current = best_score
        total_delta += best_delta
        steps_taken += 1
    final_score = float(current["score"])
    improved = bool(final_score + 1e-8 < initial_score)
    return coords.astype(np.float32), {
        "status": (
            "finite_difference_rigid_translation_score_minimized"
            if improved
            else "finite_difference_rigid_translation_no_improvement"
        ),
        "steps_taken": int(steps_taken),
        "initial_coarse_score": initial_score,
        "final_coarse_score": final_score,
        "improved": improved,
        "translation_delta_a": [float(v) for v in total_delta.tolist()],
    }


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


def so3_rotation_matrices(count: int, seed: int) -> list[np.ndarray]:
    """Deterministic uniform-quaternion SO(3) samples with identity first."""
    total = int(max(1, count))
    rotations = [np.eye(3, dtype=np.float64)]
    if total == 1:
        return rotations
    rng = np.random.RandomState(int(seed))
    for _idx in range(total - 1):
        u1, u2, u3 = rng.uniform(0.0, 1.0, size=3)
        q1 = math.sqrt(1.0 - u1) * math.sin(2.0 * math.pi * u2)
        q2 = math.sqrt(1.0 - u1) * math.cos(2.0 * math.pi * u2)
        q3 = math.sqrt(u1) * math.sin(2.0 * math.pi * u3)
        q4 = math.sqrt(u1) * math.cos(2.0 * math.pi * u3)
        x, y, z, w = q1, q2, q3, q4
        rotations.append(
            np.array(
                [
                    [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                    [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                    [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
                ],
                dtype=np.float64,
            )
        )
    return rotations


def pocket_translation_grid(spacing_a: float = 1.5) -> list[np.ndarray]:
    spacing = float(spacing_a)
    offsets = [
        (0.0, 0.0, 0.0),
        (spacing, 0.0, 0.0),
        (-spacing, 0.0, 0.0),
        (0.0, spacing, 0.0),
        (0.0, -spacing, 0.0),
        (0.0, 0.0, spacing),
        (0.0, 0.0, -spacing),
    ]
    return [np.asarray(offset, dtype=np.float32) for offset in offsets]


def transform_pose_to_pocket(
    pose: np.ndarray,
    pocket_center: np.ndarray,
    rotation: np.ndarray,
    translation: np.ndarray,
) -> np.ndarray:
    centered = center_coordinates_around_origin(np.asarray(pose, dtype=np.float32)).astype(np.float64)
    rotated = centered @ np.asarray(rotation, dtype=np.float64).T
    placed = rotated + np.asarray(pocket_center, dtype=np.float64).reshape(1, 3)
    placed += np.asarray(translation, dtype=np.float64).reshape(1, 3)
    return placed.astype(np.float32)


def pose_search_candidates(
    poses: np.ndarray,
    pocket_center: np.ndarray,
    protein_beads: np.ndarray,
    *,
    seed: int,
    max_candidates: int,
    ligand_smiles: str = "",
    rotations_per_conformer: int = 4,
    translation_spacing_a: float = 1.5,
    clash_cutoff_a: float = 1.2,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    conformers = np.asarray(poses, dtype=np.float32)
    diversity = conformer_diversity_diagnostics(conformers, smiles=ligand_smiles)
    rotations = so3_rotation_matrices(rotations_per_conformer, seed)
    translations = pocket_translation_grid(translation_spacing_a)
    raw: list[dict[str, Any]] = []
    for conformer_index, pose in enumerate(conformers):
        for rotation_index, rotation in enumerate(rotations):
            for translation_index, translation in enumerate(translations):
                coords = transform_pose_to_pocket(pose, pocket_center, rotation, translation)
                coarse = coarse_pose_score(protein_beads, coords, clash_cutoff_a=clash_cutoff_a)
                raw.append(
                    {
                        "coords": coords,
                        "conformer_index": int(conformer_index),
                        "rotation_index": int(rotation_index),
                        "translation_index": int(translation_index),
                        "translation_vector_a": [float(v) for v in translation.tolist()],
                        "clash_count": int(coarse["clash_count"]),
                        "coarse_score": float(coarse["score"]),
                        "coarse_score_components": coarse,
                    }
                )
    raw.sort(
        key=lambda row: (
            int(row["clash_count"]),
            float(row["coarse_score"]),
            int(row["conformer_index"]),
            int(row["rotation_index"]),
            int(row["translation_index"]),
        )
    )
    coarse_beam_size = int(max(1, max_candidates) * 2)
    coarse_beam = raw[:coarse_beam_size]
    minimized: list[dict[str, Any]] = []
    for row in coarse_beam:
        coords, minimization = local_rigid_body_minimize_pose(
            protein_beads,
            np.asarray(row["coords"], dtype=np.float32),
            clash_cutoff_a=clash_cutoff_a,
        )
        final_coarse = coarse_pose_score(protein_beads, coords, clash_cutoff_a=clash_cutoff_a)
        updated = dict(row)
        updated["coords"] = coords
        updated["coarse_score_before_local"] = float(row["coarse_score"])
        updated["coarse_score"] = float(final_coarse["score"])
        updated["coarse_score_components"] = final_coarse
        updated["clash_count"] = int(final_coarse["clash_count"])
        updated["local_minimization"] = minimization
        minimized.append(updated)
    minimized.sort(
        key=lambda row: (
            int(row["clash_count"]),
            float(row["coarse_score"]),
            int(row["conformer_index"]),
            int(row["rotation_index"]),
            int(row["translation_index"]),
        )
    )
    retained = minimized[: int(max(1, max_candidates))]
    if retained and all(int(row["clash_count"]) > 0 for row in retained):
        prefilter_status = "retained_lowest_clash_candidates"
    else:
        prefilter_status = "pass"
    minimized_count = int(sum(1 for row in minimized if row.get("local_minimization", {}).get("improved") is True))
    if minimized_count > 0:
        local_minimization_status = "finite_difference_rigid_body_gradient_minimized"
    elif minimized:
        local_minimization_status = "finite_difference_rigid_body_gradient_no_improvement"
    else:
        local_minimization_status = "finite_difference_rigid_body_gradient_not_attempted"
    retained_conformer_indices = sorted({int(row["conformer_index"]) for row in retained})
    diagnostics = {
        "search_strategy": "etkdg_conformer_so3_translation_grid_coarse_score_local_min_beam_v1",
        "conformer_count": int(conformers.shape[0]),
        "conformer_diversity": diversity,
        "rotatable_bond_count": int(diversity["rotatable_bond_count"]),
        "retained_conformer_count": int(len(retained_conformer_indices)),
        "retained_conformer_indices": retained_conformer_indices,
        "retained_conformer_fraction": (
            float(len(retained_conformer_indices) / int(conformers.shape[0]))
            if int(conformers.shape[0]) > 0
            else 0.0
        ),
        "rotations_per_conformer": int(len(rotations)),
        "translation_grid_point_count": int(len(translations)),
        "translation_spacing_a": float(translation_spacing_a),
        "raw_candidate_count": int(len(raw)),
        "coarse_beam_candidate_count": int(len(coarse_beam)),
        "retained_candidate_count": int(len(retained)),
        "beam_size": int(max(1, max_candidates)),
        "clash_cutoff_a": float(clash_cutoff_a),
        "clash_prefilter_status": prefilter_status,
        "clash_prefiltered_candidate_count": int(sum(1 for row in raw if int(row["clash_count"]) == 0)),
        "coarse_score_beam_status": "pass",
        "local_minimization_status": local_minimization_status,
        "local_minimization_method": "finite_difference_gradient_descent_translation_rotation",
        "local_minimization_degrees_of_freedom": ["translation", "rotation"],
        "local_minimization_candidate_count": int(len(minimized)),
        "local_minimization_improved_count": minimized_count,
        "symmetry_rmsd_clustering_status": "not_run_restricted_vertical_slice",
        "chemical_anchor_mapping_status": "not_run_restricted_vertical_slice",
    }
    return retained, diagnostics


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
