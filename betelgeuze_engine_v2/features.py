"""Deterministic topology features for the engine-v2 CPU reference path."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    require_molecular_preparation_ready,
    require_valid_all_atom_system,
)


ATOM_FEATURE_SCHEMA_VERSION = "betelgeuze.atom_features.reference/1.0.0"

ATOM_FEATURE_NAMES = (
    "atomic_number_scaled",
    "formal_charge_squashed",
    "partial_charge_squashed",
    "partial_charge_present",
    "mass_squashed",
    "mass_present",
    "isotope_mass_number_scaled",
    "isotope_mass_number_present",
    "aromatic",
    "bond_degree_squashed",
    "bond_order_sum_squashed",
    "stereo_e_bond_count_squashed",
    "stereo_z_bond_count_squashed",
    "aromatic_bond_degree_squashed",
    "is_hydrogen",
    "hetero_residue",
    "polymer_residue",
    "stereo_r",
    "stereo_s",
    "occupancy_or_one",
    "b_factor_squashed",
)


@dataclass(frozen=True)
class AtomFeatureBatch:
    """One feature row per explicit atom and coordinate model."""

    values: torch.Tensor
    names: tuple[str, ...]
    schema_version: str
    diagnostics: dict[str, Any]

    def __post_init__(self) -> None:
        if self.values.ndim != 3:
            raise ValueError("atom features must have shape [B, N, F]")
        if self.values.shape[-1] != len(self.names):
            raise ValueError("feature names must match the final tensor dimension")
        if not self.values.is_floating_point():
            raise TypeError("atom features must use a floating dtype")

    @property
    def width(self) -> int:
        return int(self.values.shape[-1])


def _squash(value: float, scale: float) -> float:
    return math.tanh(float(value) / float(scale))


def build_deterministic_atom_features(
    system: AllAtomSystem,
    *,
    dtype: torch.dtype | None = None,
    device: torch.device | str | None = None,
) -> AtomFeatureBatch:
    """Build fixed-width, coordinate-independent atom descriptors.

    The operation traverses atoms and bonds once.  Missing optional chemistry
    fields are represented by a zero value plus an explicit presence bit; no
    parameterization or chemical identity is guessed.
    """

    if not isinstance(system, AllAtomSystem):
        raise TypeError("system must be an AllAtomSystem")
    require_valid_all_atom_system(system)
    require_molecular_preparation_ready(system)
    target_dtype = system.coordinates.dtype if dtype is None else dtype
    target_device = system.coordinates.device if device is None else torch.device(device)
    if target_dtype not in (torch.float32, torch.float64):
        raise TypeError("reference atom features support torch.float32 or torch.float64")

    atom_count = system.atom_count
    degree = [0] * atom_count
    order_sum = [0.0] * atom_count
    stereo_e_count = [0] * atom_count
    stereo_z_count = [0] * atom_count
    aromatic_bond_degree = [0] * atom_count
    for bond in system.bonds:
        first = int(bond.atom_i)
        second = int(bond.atom_j)
        if first < 0 or first >= atom_count or second < 0 or second >= atom_count:
            raise ValueError("bond endpoint is outside the canonical atom table")
        if first >= second:
            raise ValueError("bond endpoints are not in canonical increasing order")
        if not math.isfinite(float(bond.order)) or float(bond.order) <= 0.0:
            raise ValueError("bond order must be finite and positive")
        degree[first] += 1
        degree[second] += 1
        order_sum[first] += float(bond.order)
        order_sum[second] += float(bond.order)
        stereo = str(bond.stereo or "").strip().upper()
        if stereo == "E":
            stereo_e_count[first] += 1
            stereo_e_count[second] += 1
        elif stereo == "Z":
            stereo_z_count[first] += 1
            stereo_z_count[second] += 1
        if bond.aromatic:
            aromatic_bond_degree[first] += 1
            aromatic_bond_degree[second] += 1

    rows: list[list[float]] = []
    for atom in system.atoms:
        residue_index = int(atom.residue_index)
        if residue_index < 0 or residue_index >= len(system.residues):
            raise ValueError("atom residue index is outside the canonical residue table")
        residue = system.residues[residue_index]
        partial_charge = 0.0 if atom.partial_charge_e is None else float(atom.partial_charge_e)
        mass = 0.0 if atom.mass_da is None else float(atom.mass_da)
        isotope_mass_number = (
            0.0 if atom.isotope_mass_number is None else float(atom.isotope_mass_number)
        )
        occupancy = 1.0 if atom.occupancy is None else float(atom.occupancy)
        b_factor = 0.0 if atom.b_factor is None else float(atom.b_factor)
        optional_values = (partial_charge, mass, occupancy, b_factor)
        if not all(math.isfinite(value) for value in optional_values):
            raise ValueError("optional atom fields used by the feature builder must be finite")
        stereo = str(atom.stereo or "").strip().upper()
        rows.append(
            [
                float(atom.atomic_number) / 118.0,
                _squash(float(atom.formal_charge), 4.0),
                _squash(partial_charge, 2.0),
                float(atom.partial_charge_e is not None),
                _squash(mass, 100.0),
                float(atom.mass_da is not None),
                isotope_mass_number / 350.0,
                float(atom.isotope_mass_number is not None),
                float(bool(atom.aromatic)),
                _squash(float(degree[atom.index]), 4.0),
                _squash(order_sum[atom.index], 6.0),
                _squash(float(stereo_e_count[atom.index]), 2.0),
                _squash(float(stereo_z_count[atom.index]), 2.0),
                _squash(float(aromatic_bond_degree[atom.index]), 4.0),
                float(int(atom.atomic_number) == 1),
                float(bool(residue.hetero)),
                float(str(residue.entity_type).strip().lower() == "polymer"),
                float(stereo == "R"),
                float(stereo == "S"),
                occupancy,
                _squash(b_factor, 100.0),
            ]
        )

    values = torch.tensor(rows, dtype=target_dtype, device=target_device)
    values = values.unsqueeze(0).expand(system.model_count, atom_count, len(ATOM_FEATURE_NAMES))
    diagnostics: dict[str, Any] = {
        "schema_version": ATOM_FEATURE_SCHEMA_VERSION,
        "status": "deterministic_reference_features",
        "batch_size": system.model_count,
        "atom_count": atom_count,
        "feature_count": len(ATOM_FEATURE_NAMES),
        "coordinate_dependent": False,
        "parameterization_inferred": False,
        "isotope_identity_encoded": True,
        "atom_rs_stereochemistry_encoded": True,
        "bond_ez_stereochemistry_encoded": True,
        "constructs_pair_matrix": False,
        "expected_complexity": "O(N + E_bond)",
    }
    return AtomFeatureBatch(
        values=values,
        names=ATOM_FEATURE_NAMES,
        schema_version=ATOM_FEATURE_SCHEMA_VERSION,
        diagnostics=diagnostics,
    )


__all__ = [
    "ATOM_FEATURE_NAMES",
    "ATOM_FEATURE_SCHEMA_VERSION",
    "AtomFeatureBatch",
    "build_deterministic_atom_features",
]
