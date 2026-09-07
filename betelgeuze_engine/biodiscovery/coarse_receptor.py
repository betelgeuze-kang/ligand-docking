"""Coordinate-covariant, explicitly approximate receptor preparation.

The four sites are geometric proxies, not reconstructed atoms or a calibrated
coarse-grained force field. No all-atom chemistry is inferred from a CA trace.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from betelgeuze_engine.biodiscovery.stability_observations import _coords
from betelgeuze_engine.physics.dense_guard import DEFAULT_DENSE_DIAGNOSTIC_MAX_ATOMS

PROXY_SCHEMA = "ca_local_frame_four_site_proxy_v2"


def covariant_protein_coords(protein_ca: np.ndarray) -> np.ndarray:
    ca = _coords(protein_ca, "protein_ca")
    result = np.empty((len(ca), 4, 3), dtype=np.float64)
    for i, origin in enumerate(ca):
        # Index order is intentional: distance ties must not switch an axis
        # after a rigid rotation. This does not infer chain/peptide topology.
        order = [*range(i + 1, len(ca)), *range(i - 1, -1, -1)]
        vectors = ca[order] - origin
        lengths = np.linalg.norm(vectors, axis=1)
        usable = np.flatnonzero(lengths > 1e-7)
        if not len(usable):
            raise ValueError("protein_proxy_requires_distinct_ca_sites")
        tangent = vectors[usable[0]] / lengths[usable[0]]
        normal = None
        for index in usable[1:]:
            direction = vectors[index] / lengths[index]
            perpendicular = direction - np.dot(direction, tangent) * tangent
            magnitude = float(np.linalg.norm(perpendicular))
            if magnitude > 1e-6:
                normal = perpendicular / magnitude
                break
        result[i, 0] = origin
        result[i, 1] = origin + 1.2 * tangent
        if normal is None:
            # A line has no rotation-covariant transverse direction. Use a
            # documented collinear proxy, never an arbitrary world-axis fallback.
            result[i, 2] = origin - 0.73 * tangent
            result[i, 3] = origin - 1.61 * tangent
        else:
            result[i, 2] = origin - 0.8 * tangent + 0.9 * normal
            result[i, 3] = origin - 0.8 * tangent - 0.9 * normal
    with np.errstate(over="ignore", invalid="ignore"):
        output = result.reshape(-1, 3).astype(np.float32)
    if not np.isfinite(output).all():
        raise ValueError("protein_proxy_coordinates_not_float32_representable")
    return output


def prepare_receptor_proxy(
    protein_ca: np.ndarray, pocket_indices: list[int], *, ligand_atom_count: int,
    buffer_a: float, explicit_pocket: bool,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Build one fixed pocket+buffer domain for all candidates and observations.

    There is no adaptive truncation to fit the cap. This local proxy is not an
    electrostatically complete subsystem or a physically capped all-atom model.
    """
    ca = _coords(protein_ca, "protein_ca")
    if not math.isfinite(buffer_a) or buffer_a <= 0.:
        raise ValueError("pocket_cutoff_a must be finite and positive")
    if not pocket_indices:
        raise ValueError("empty_pocket_resolution")
    if any(isinstance(i, (bool, np.bool_)) or not isinstance(i, (int, np.integer))
           or i < 0 or i >= len(ca) for i in pocket_indices):
        raise ValueError("invalid_pocket_residue_indices")
    if len(set(pocket_indices)) != len(pocket_indices):
        raise ValueError("invalid_pocket_residue_indices:duplicates")
    if isinstance(ligand_atom_count, (bool, np.bool_)) or not isinstance(ligand_atom_count, (int, np.integer)) or ligand_atom_count < 1:
        raise ValueError("invalid_ligand_atom_count")
    seeds = [int(i) for i in pocket_indices]
    included = np.ones(len(ca), dtype=bool) if not explicit_pocket else np.zeros(len(ca), dtype=bool)
    if explicit_pocket:
        # O(N) working memory; no N x N protein allocation.
        for index in seeds:
            included |= np.linalg.norm(ca - ca[index], axis=1) <= buffer_a
    indices = np.flatnonzero(included).tolist()
    total = 4 * len(indices) + int(ligand_atom_count)
    if total > DEFAULT_DENSE_DIAGNOSTIC_MAX_ATOMS:
        raise ValueError(f"dense_diagnostic_blocked:pocket_domain_has_{total}_sites_cap_{DEFAULT_DENSE_DIAGNOSTIC_MAX_ATOMS}")
    beads = covariant_protein_coords(ca[indices])
    center = ca[seeds].mean(axis=0).astype(np.float32)
    details = {
        "schema_version": PROXY_SCHEMA,
        "representation": "geometric_ca_proxy_not_all_atom",
        "frame_policy": "ordered_ca_directions_with_collinear_degenerate_fallback",
        "scope": "fixed_explicit_pocket_plus_buffer" if explicit_pocket else "full_receptor",
        "input_residue_count": len(ca), "scoring_residue_count": len(indices),
        "scoring_residue_indices": indices, "pocket_residue_indices": seeds,
        "buffer_a": float(buffer_a) if explicit_pocket else None,
        "protein_site_count": len(beads), "reserved_ligand_atom_count": int(ligand_atom_count),
        "dense_diagnostic_cap": DEFAULT_DENSE_DIAGNOSTIC_MAX_ATOMS,
        "physical_subsystem_validated": False, "distant_environment_included": not explicit_pocket,
        "scope_boundary": "local geometric proxy; not a capped forcefield subsystem or long-range solvation model",
    }
    return beads, center, details
