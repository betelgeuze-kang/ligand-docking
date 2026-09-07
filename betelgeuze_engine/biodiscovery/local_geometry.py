"""Rigid-transform-covariant geometric proxies; not atom reconstruction.

The input is an ordered C-alpha point cloud, not a bonded/all-atom topology.
Geometry-derived axes avoid a preferred laboratory direction. Local contexts
are explicitly truncated diagnostics, never full-system energy equivalents.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

PROXY_REPRESENTATION = "ca_point_cloud_frame_v2"
BEADS_PER_RESIDUE = 4
# Fixed extents of the existing diagnostic search/minimizer and bead offsets.
SEARCH_TRANSLATION_BOUND_A = 1.5
LOCAL_TRANSLATION_BOUND_A = 6 * 0.25
BEAD_RADIUS_BOUND_A = 1.3


def _points(value: np.ndarray) -> np.ndarray:
    if np.ma.isMaskedArray(value):
        raise ValueError("masked_protein_geometry")
    points = np.asarray(value)
    if points.dtype.kind not in "iuf" or points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("protein_geometry_must_be_real_Nx3")
    if not len(points) or not np.isfinite(points).all():
        raise ValueError("protein_geometry_must_be_nonempty_and_finite")
    if (points > np.finfo(np.float32).max).any() or (points < -np.finfo(np.float32).max).any():
        raise ValueError("protein_geometry_out_of_range")
    return points.astype(np.float64)


def normalized_residue_indices(indices: list[int], count: int) -> list[int]:
    result = []
    for value in indices:
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
            raise ValueError("invalid_pocket_residue_indices")
        index = int(value)
        if index < 0 or index >= count:
            raise ValueError("invalid_pocket_residue_indices")
        result.append(index)
    if len(set(result)) != len(result):
        raise ValueError("duplicate_pocket_residue_indices")
    return result


def _nearest_index(squared: np.ndarray, eligible: np.ndarray) -> int | None:
    candidates = np.flatnonzero(eligible)
    if not len(candidates):
        return None
    minimum = float(squared[candidates].min())
    # Resolve geometric ties by input index, not rotation-sensitive roundoff.
    tolerance = 1e-8 * max(1.0, minimum)
    return int(candidates[np.flatnonzero(squared[candidates] <= minimum + tolerance)[0]])


def virtual_protein_coords(protein_ca: np.ndarray, *, residue_indices: list[int] | None = None) -> np.ndarray:
    """Four untyped geometric sites per selected residue, in input order.

    Axes use nearest distinct/noncollinear C-alpha directions. This infers no
    bonds or chemical atom types. A collinear/coincident cloud has no identifiable
    frame and is explicitly rejected, never given an arbitrary global-axis
    fallback or coincident artificial sites.
    Frame switches are possible as a point cloud deforms; this is not a learned
    potential or differentiable physical backmapping. Scores require rebaselining.
    """
    points = _points(protein_ca)
    indices = list(range(len(points))) if residue_indices is None else normalized_residue_indices(residue_indices, len(points))
    beads = np.empty((len(indices), BEADS_PER_RESIDUE, 3), dtype=np.float64)
    for out_index, residue_index in enumerate(indices):
        origin = points[residue_index]
        relative = points - origin
        squared = np.einsum("ij,ij->i", relative, relative)
        first = _nearest_index(squared, squared > 1e-16)
        tangent, radial = np.zeros(3), np.zeros(3)
        if first is not None:
            tangent = relative[first] / math.sqrt(float(squared[first]))
            orthogonal = relative - (relative @ tangent)[:, None] * tangent
            orthogonal_sq = np.einsum("ij,ij->i", orthogonal, orthogonal)
            second = _nearest_index(squared, orthogonal_sq > 1e-12 * np.maximum(squared, 1.0))
            if second is not None:
                radial = orthogonal[second] / math.sqrt(float(orthogonal_sq[second]))
        if first is None or not np.any(radial):
            raise ValueError("degenerate_protein_geometry_requires_noncollinear_ca")
        beads[out_index] = [origin, origin + 1.2 * tangent,
                            origin - 0.8 * tangent + 0.9 * radial,
                            origin - 0.8 * tangent - 0.9 * radial]
    if not np.isfinite(beads).all() or (np.abs(beads) > np.finfo(np.float32).max).any():
        raise ValueError("protein_proxy_coordinates_out_of_range")
    return beads.reshape(-1, 3).astype(np.float32)


def pocket_context(
    protein_ca: np.ndarray, pocket_indices: list[int], conformers: list[np.ndarray], *, cutoff_a: float,
) -> tuple[list[int], dict[str, Any]]:
    """Select a conservative geometric search neighborhood, not an energy cutoff.

    Dense/neighbor caps are checked separately and must never be bypassed by
    dropping nearest atoms. SA/GB and receptor self-energy change on truncation;
    neither whole-system equivalence nor a physically validated boundary is claimed.
    """
    points = _points(protein_ca)
    seeds = normalized_residue_indices(pocket_indices, len(points))
    if not seeds:
        raise ValueError("empty_pocket_resolution")
    if not math.isfinite(cutoff_a) or cutoff_a <= 0.0:
        raise ValueError("invalid_pocket_cutoff")
    center = points[seeds].mean(axis=0)
    seed_radius = float(np.linalg.norm(points[seeds] - center, axis=1).max())
    if not conformers:
        raise ValueError("missing_context_conformer_ensemble")
    ligand_radius = 0.0
    for value in conformers:
        ensemble = np.asarray(value)
        if (np.ma.isMaskedArray(value) or ensemble.dtype.kind not in "iuf" or ensemble.ndim != 3
                or ensemble.shape[2] != 3 or not ensemble.shape[0] or not ensemble.shape[1]):
            raise ValueError("invalid_context_conformer_ensemble")
        if not np.isfinite(ensemble).all():
            raise ValueError("nonfinite_context_conformer_ensemble")
        if (ensemble > np.finfo(np.float32).max).any() or (ensemble < -np.finfo(np.float32).max).any():
            raise ValueError("context_conformer_coordinates_out_of_range")
        ensemble = ensemble.astype(np.float64)
        centered = ensemble - ensemble.mean(axis=1, keepdims=True)
        ligand_radius = max(ligand_radius, float(np.linalg.norm(centered, axis=2).max()))
    radius = (seed_radius + max(8.0, float(cutoff_a)) + ligand_radius
              + SEARCH_TRANSLATION_BOUND_A + LOCAL_TRANSLATION_BOUND_A + BEAD_RADIUS_BOUND_A)
    selected = np.flatnonzero(np.linalg.norm(points - center, axis=1) <= radius + 1e-6).tolist()
    return selected, {
        "schema_version": "tier_beta_local_context_v1",
        "representation": PROXY_REPRESENTATION,
        "input_residue_count": int(len(points)),
        "context_residue_count": len(selected),
        "context_residue_indices": selected,
        "excluded_residue_count": int(len(points)) - len(selected),
        "pocket_seed_indices": seeds,
        "center_a": center.tolist(),
        "radius_a": radius,
        "ligand_radius_bound_a": ligand_radius,
        "search_translation_bound_a": SEARCH_TRANSLATION_BOUND_A,
        "local_translation_bound_a": LOCAL_TRANSLATION_BOUND_A,
        "bead_radius_bound_a": BEAD_RADIUS_BOUND_A,
        "full_system_energy_equivalent": False,
        "physical_boundary_validated": False,
        "scope": "restricted_local_geometric_proxy_not_allatom",
    }
