"""Preserve the canonical minimization class identity while enforcing round-1 caps.

The first round originally replaced the dataclass object. That made existing
constrained-minimization dataclass default factories instantiate the historical
class while their module globals referenced the replacement class. This
compatibility installer restores the original class object, hardens its
constructor defaults and caps, and rewires loaded modules without changing
``isinstance`` or dataclass default-factory semantics.
"""

from __future__ import annotations

import hashlib
import json
import sys

from betelgeuze_engine_v2.geometry import (
    MAX_COMPACT_ATOMS_PER_CELL,
    MAX_COMPACT_NEIGHBORS,
)


STACK_ROUND1_MINIMIZATION_COMPAT_SCHEMA_ID = (
    "betelgeuze.engine_v2_stack_round1_minimization_compat/1.0.0"
)


def _sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()


def install_stack_round1_minimization_compat() -> str:
    marker = "_betelgeuze_stack_round1_minimization_compat_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from betelgeuze_engine_v2 import physics as physics_package
    from betelgeuze_engine_v2.physics import reference_minimization as module

    replacement_class = module.ReferenceMinimizationConfig
    original_class = replacement_class
    constrained = sys.modules.get(
        "betelgeuze_engine_v2.physics.reference_constrained_minimization"
    )
    if constrained is not None:
        field = constrained.ReferenceConstrainedMinimizationConfig.__dataclass_fields__[
            "minimization"
        ]
        original_class = field.default_factory
    if not isinstance(original_class, type):
        raise RuntimeError("canonical minimization class identity is unavailable")

    if not getattr(original_class, "_betelgeuze_round1_constructor_hardened", False):
        original_init = original_class.__init__

        def hardened_init(
            self,
            max_iterations: int = 100,
            max_backtracks: int = 16,
            initial_step_size_angstrom2_mol_per_kcal: float = 1.0e-3,
            backtrack_factor: float = 0.5,
            armijo_constant: float = 1.0e-4,
            maximum_atom_displacement_angstrom: float = 0.05,
            force_tolerance_kcal_per_mol_angstrom: float = 1.0e-3,
            max_neighbors: int = MAX_COMPACT_NEIGHBORS,
            max_atoms_per_cell: int = MAX_COMPACT_ATOMS_PER_CELL,
            schema_id: str = module.REFERENCE_MINIMIZATION_CONFIG_SCHEMA_ID,
        ) -> None:
            if type(max_neighbors) is not int or type(max_atoms_per_cell) is not int:
                raise module.ReferenceMinimizationError(
                    "minimization capacities must be exact integers"
                )
            normalized_neighbors = max_neighbors
            normalized_cell_capacity = max_atoms_per_cell
            if normalized_neighbors > MAX_COMPACT_NEIGHBORS:
                raise module.ReferenceMinimizationError(
                    "max_neighbors exceeds the compact-neighbor hard cap"
                )
            if normalized_cell_capacity > MAX_COMPACT_ATOMS_PER_CELL:
                raise module.ReferenceMinimizationError(
                    "max_atoms_per_cell exceeds the compact-cell hard cap"
                )
            original_init(
                self,
                max_iterations=max_iterations,
                max_backtracks=max_backtracks,
                initial_step_size_angstrom2_mol_per_kcal=(
                    initial_step_size_angstrom2_mol_per_kcal
                ),
                backtrack_factor=backtrack_factor,
                armijo_constant=armijo_constant,
                maximum_atom_displacement_angstrom=(
                    maximum_atom_displacement_angstrom
                ),
                force_tolerance_kcal_per_mol_angstrom=(
                    force_tolerance_kcal_per_mol_angstrom
                ),
                max_neighbors=normalized_neighbors,
                max_atoms_per_cell=normalized_cell_capacity,
                schema_id=schema_id,
            )

        original_class.__init__ = hardened_init
        original_class._betelgeuze_round1_constructor_hardened = True
        original_class.__dataclass_fields__["max_neighbors"].default = (
            MAX_COMPACT_NEIGHBORS
        )
        original_class.__dataclass_fields__["max_atoms_per_cell"].default = (
            MAX_COMPACT_ATOMS_PER_CELL
        )
        original_class.max_neighbors = MAX_COMPACT_NEIGHBORS
        original_class.max_atoms_per_cell = MAX_COMPACT_ATOMS_PER_CELL

    module.ReferenceMinimizationConfig = original_class
    physics_package.ReferenceMinimizationConfig = original_class
    for loaded in tuple(sys.modules.values()):
        if loaded is not None and getattr(
            loaded, "ReferenceMinimizationConfig", None
        ) is replacement_class:
            setattr(loaded, "ReferenceMinimizationConfig", original_class)

    receipt = _sha256(
        {
            "schema_id": STACK_ROUND1_MINIMIZATION_COMPAT_SCHEMA_ID,
            "canonical_class_identity_preserved": True,
            "default_max_neighbors": MAX_COMPACT_NEIGHBORS,
            "default_max_atoms_per_cell": MAX_COMPACT_ATOMS_PER_CELL,
            "exact_integer_capacity_semantics": True,
            "constructor_caps_enforced": True,
            "scientifically_validated": False,
            "claim_safe": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "STACK_ROUND1_MINIMIZATION_COMPAT_SCHEMA_ID",
    "install_stack_round1_minimization_compat",
]
