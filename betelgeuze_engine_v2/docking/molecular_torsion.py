"""Bounded molecular-graph to docking torsion-tree materialization.

Only non-ring, non-terminal heavy-atom single-bond bridges are admitted as
torsion variables.  A narrow amide/sulfonamide/phosphoramidate exclusion avoids
the most obvious partial-double-bond rotations.  This is deterministic graph
bookkeeping, not full chemical perception, conformer generation, or a torsion
energy model.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Integral, Real

import torch

from betelgeuze_engine_v2.ai import torsion_tree_forward_kinematics
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Bond,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
)

from .identity import coordinate_fingerprint
from .proposals import MAX_DOCKING_TORSIONS, TorsionSearchSpace


MOLECULAR_TORSION_SEARCH_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_molecular_torsion_search_config/1.0.0"
)
MOLECULAR_TORSION_SEARCH_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_molecular_torsion_search_receipt/1.0.0"
)
MOLECULAR_TORSION_SEARCH_BLOCKERS = (
    "rotatable_bond_perception_is_a_bounded_graph_heuristic",
    "amide_like_exclusion_is_not_full_resonance_perception",
    "ring_and_macrocycle_closure_sampling_missing",
    "torsion_energy_profile_missing",
    "seed_bond_lengths_and_angles_are_retained",
    "conformer_generation_not_scientifically_validated",
    "public_flexible_docking_evidence_missing",
)


class MolecularTorsionSearchError(ValueError):
    """A molecular topology is outside the bounded torsion-search contract."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise MolecularTorsionSearchError(
            "molecular torsion value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise MolecularTorsionSearchError(f"{name} must be a lowercase SHA-256")
    return value


def _exact_int(value: object, *, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise MolecularTorsionSearchError(f"{name} must be an integer")
    result = int(value)
    if result < minimum:
        raise MolecularTorsionSearchError(f"{name} must be at least {minimum}")
    return result


def _finite(value: object, *, name: str, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise MolecularTorsionSearchError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result) or (nonnegative and result < 0.0):
        condition = "finite and non-negative" if nonnegative else "finite"
        raise MolecularTorsionSearchError(f"{name} must be {condition}")
    return result


@dataclass(frozen=True, slots=True)
class MolecularTorsionSearchConfig:
    max_atoms: int = 256
    max_bonds: int = 1_024
    max_rotatable_bonds: int = 32
    reconstruction_tolerance_angstrom: float = 1.0e-10

    def __post_init__(self) -> None:
        max_atoms = _exact_int(self.max_atoms, name="max_atoms", minimum=1)
        if max_atoms > 4_096:
            raise MolecularTorsionSearchError("max_atoms must not exceed 4096")
        max_bonds = _exact_int(self.max_bonds, name="max_bonds", minimum=0)
        if max_bonds > 16_384:
            raise MolecularTorsionSearchError("max_bonds must not exceed 16384")
        max_rotatable = _exact_int(
            self.max_rotatable_bonds,
            name="max_rotatable_bonds",
            minimum=0,
        )
        if max_rotatable > MAX_DOCKING_TORSIONS:
            raise MolecularTorsionSearchError(
                f"max_rotatable_bonds must not exceed {MAX_DOCKING_TORSIONS}"
            )
        tolerance = _finite(
            self.reconstruction_tolerance_angstrom,
            name="reconstruction_tolerance_angstrom",
            nonnegative=True,
        )
        object.__setattr__(self, "max_atoms", max_atoms)
        object.__setattr__(self, "max_bonds", max_bonds)
        object.__setattr__(self, "max_rotatable_bonds", max_rotatable)
        object.__setattr__(self, "reconstruction_tolerance_angstrom", tolerance)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": MOLECULAR_TORSION_SEARCH_CONFIG_SCHEMA_ID,
            "max_atoms": self.max_atoms,
            "max_bonds": self.max_bonds,
            "max_rotatable_bonds": self.max_rotatable_bonds,
            "reconstruction_tolerance_angstrom": (
                self.reconstruction_tolerance_angstrom
            ),
            "root_policy": "lowest_index_heavy_atom_else_lowest_index_atom",
            "tree_policy": "deterministic_breadth_first_sorted_neighbor_order",
            "rotatable_policy": (
                "heavy_single_graph_bridge_with_two_heavy_atoms_on_each_side_"
                "excluding_narrow_amide_sulfonamide_phosphoramidate_patterns"
            ),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class MolecularTorsionBondRow:
    bond_index: int
    atom_i: int
    atom_j: int
    bond_order: float
    aromatic: bool
    status: str
    reason: str
    parent_atom_index: int
    child_atom_index: int
    side_heavy_atom_counts: tuple[int, int]

    def __post_init__(self) -> None:
        for name in ("bond_index", "atom_i", "atom_j"):
            _exact_int(getattr(self, name), name=name)
        order = _finite(self.bond_order, name="bond_order", nonnegative=True)
        if not isinstance(self.aromatic, bool):
            raise MolecularTorsionSearchError("aromatic must be boolean")
        if self.status not in {"selected", "excluded"} or not self.reason:
            raise MolecularTorsionSearchError(
                "molecular torsion bond status or reason is invalid"
            )
        for name in ("parent_atom_index", "child_atom_index"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral) or int(value) < -1:
                raise MolecularTorsionSearchError(f"{name} must be an integer >= -1")
        counts = tuple(
            _exact_int(value, name="side_heavy_atom_count")
            for value in self.side_heavy_atom_counts
        )
        if len(counts) != 2:
            raise MolecularTorsionSearchError(
                "side_heavy_atom_counts must contain two values"
            )
        if self.status == "selected" and (
            self.parent_atom_index < 0
            or self.child_atom_index < 0
            or min(counts) < 2
        ):
            raise MolecularTorsionSearchError(
                "selected molecular torsion bond row is incomplete"
            )
        object.__setattr__(self, "bond_order", order)
        object.__setattr__(self, "parent_atom_index", int(self.parent_atom_index))
        object.__setattr__(self, "child_atom_index", int(self.child_atom_index))
        object.__setattr__(self, "side_heavy_atom_counts", counts)

    def to_dict(self) -> dict[str, object]:
        return {
            "bond_index": self.bond_index,
            "atom_i": self.atom_i,
            "atom_j": self.atom_j,
            "bond_order": self.bond_order,
            "aromatic": self.aromatic,
            "status": self.status,
            "reason": self.reason,
            "parent_atom_index": self.parent_atom_index,
            "child_atom_index": self.child_atom_index,
            "side_heavy_atom_counts": list(self.side_heavy_atom_counts),
        }


@dataclass(frozen=True, slots=True)
class MolecularTorsionSearchReceipt:
    system_sha256: str
    topology_sha256: str
    input_coordinate_sha256: str
    search_space_sha256: str
    config_sha256: str
    atom_count: int
    bond_count: int
    root_atom_index: int
    component_count: int
    reconstruction_max_abs_error_angstrom: float
    bond_rows: tuple[MolecularTorsionBondRow, ...]
    blockers: tuple[str, ...] = MOLECULAR_TORSION_SEARCH_BLOCKERS
    schema_id: str = MOLECULAR_TORSION_SEARCH_RECEIPT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != MOLECULAR_TORSION_SEARCH_RECEIPT_SCHEMA_ID:
            raise MolecularTorsionSearchError(
                "unsupported molecular torsion search receipt schema"
            )
        for name in (
            "system_sha256",
            "topology_sha256",
            "input_coordinate_sha256",
            "search_space_sha256",
            "config_sha256",
        ):
            _digest(getattr(self, name), name=name)
        atom_count = _exact_int(self.atom_count, name="atom_count", minimum=1)
        bond_count = _exact_int(self.bond_count, name="bond_count")
        root = _exact_int(self.root_atom_index, name="root_atom_index")
        if root >= atom_count:
            raise MolecularTorsionSearchError("root_atom_index is out of bounds")
        components = _exact_int(
            self.component_count,
            name="component_count",
            minimum=1,
        )
        rows = tuple(self.bond_rows)
        if len(rows) != bond_count or tuple(row.bond_index for row in rows) != tuple(
            range(bond_count)
        ):
            raise MolecularTorsionSearchError(
                "molecular torsion receipt must retain every bond in index order"
            )
        error = _finite(
            self.reconstruction_max_abs_error_angstrom,
            name="reconstruction_max_abs_error_angstrom",
            nonnegative=True,
        )
        if tuple(self.blockers) != MOLECULAR_TORSION_SEARCH_BLOCKERS:
            raise MolecularTorsionSearchError(
                "molecular torsion search blockers cannot be promoted"
            )
        object.__setattr__(self, "atom_count", atom_count)
        object.__setattr__(self, "bond_count", bond_count)
        object.__setattr__(self, "root_atom_index", root)
        object.__setattr__(self, "component_count", components)
        object.__setattr__(self, "reconstruction_max_abs_error_angstrom", error)
        object.__setattr__(self, "bond_rows", rows)

    @property
    def rotatable_bond_count(self) -> int:
        return sum(row.status == "selected" for row in self.bond_rows)

    @property
    def excluded_bond_count(self) -> int:
        return self.bond_count - self.rotatable_bond_count

    def _payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "system_sha256": self.system_sha256,
            "topology_sha256": self.topology_sha256,
            "input_coordinate_sha256": self.input_coordinate_sha256,
            "search_space_sha256": self.search_space_sha256,
            "config_sha256": self.config_sha256,
            "atom_count": self.atom_count,
            "bond_count": self.bond_count,
            "root_atom_index": self.root_atom_index,
            "component_count": self.component_count,
            "reconstruction_max_abs_error_angstrom": (
                self.reconstruction_max_abs_error_angstrom
            ),
            "rotatable_bond_count": self.rotatable_bond_count,
            "excluded_bond_count": self.excluded_bond_count,
            "bond_rows": [row.to_dict() for row in self.bond_rows],
            "blockers": list(self.blockers),
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}


def _adjacency(system: AllAtomSystem) -> tuple[tuple[tuple[int, int], ...], ...]:
    rows: list[list[tuple[int, int]]] = [[] for _ in range(system.atom_count)]
    for bond in system.bonds:
        rows[bond.atom_i].append((bond.atom_j, bond.index))
        rows[bond.atom_j].append((bond.atom_i, bond.index))
    return tuple(tuple(sorted(row)) for row in rows)


def _breadth_first_parent(
    adjacency: tuple[tuple[tuple[int, int], ...], ...],
    root: int,
) -> tuple[tuple[int, ...], int]:
    parent = [-2] * len(adjacency)
    parent[root] = -1
    queue = [root]
    offset = 0
    while offset < len(queue):
        atom_index = queue[offset]
        offset += 1
        for neighbor, _bond_index in adjacency[atom_index]:
            if parent[neighbor] != -2:
                continue
            parent[neighbor] = atom_index
            queue.append(neighbor)
    component_count = 1
    for atom_index in range(len(adjacency)):
        if parent[atom_index] != -2:
            continue
        component_count += 1
        parent[atom_index] = -1
        queue = [atom_index]
        offset = 0
        while offset < len(queue):
            current = queue[offset]
            offset += 1
            for neighbor, _bond_index in adjacency[current]:
                if parent[neighbor] != -2:
                    continue
                parent[neighbor] = current
                queue.append(neighbor)
    return tuple(parent), component_count


def _bridge_indices(
    adjacency: tuple[tuple[tuple[int, int], ...], ...],
) -> frozenset[int]:
    discovered = [-1] * len(adjacency)
    low = [-1] * len(adjacency)
    bridge_indices: set[int] = set()
    clock = 0

    def visit(atom_index: int, parent_bond_index: int) -> None:
        nonlocal clock
        discovered[atom_index] = clock
        low[atom_index] = clock
        clock += 1
        for neighbor, bond_index in adjacency[atom_index]:
            if discovered[neighbor] == -1:
                visit(neighbor, bond_index)
                low[atom_index] = min(low[atom_index], low[neighbor])
                if low[neighbor] > discovered[atom_index]:
                    bridge_indices.add(bond_index)
            elif bond_index != parent_bond_index:
                low[atom_index] = min(low[atom_index], discovered[neighbor])

    for atom_index in range(len(adjacency)):
        if discovered[atom_index] == -1:
            visit(atom_index, -1)
    return frozenset(bridge_indices)


def _bridge_heavy_counts(
    system: AllAtomSystem,
    adjacency: tuple[tuple[tuple[int, int], ...], ...],
    bond: Bond,
) -> tuple[int, int]:
    visited = {bond.atom_i}
    stack = [bond.atom_i]
    while stack:
        atom_index = stack.pop()
        for neighbor, bond_index in adjacency[atom_index]:
            if bond_index == bond.index or neighbor in visited:
                continue
            visited.add(neighbor)
            stack.append(neighbor)
    first = sum(system.atoms[index].atomic_number != 1 for index in visited)
    heavy_total = sum(atom.atomic_number != 1 for atom in system.atoms)
    return (first, heavy_total - first)


def _partial_double_bond_reason(
    system: AllAtomSystem,
    adjacency: tuple[tuple[tuple[int, int], ...], ...],
    bond: Bond,
) -> str:
    atomic_numbers = {
        system.atoms[bond.atom_i].atomic_number,
        system.atoms[bond.atom_j].atomic_number,
    }
    patterns = (
        ({6, 7}, 6, {8, 16}, "amide_like_c_n_partial_double_bond"),
        ({7, 16}, 16, {8}, "sulfonamide_like_s_n_partial_double_bond"),
        ({7, 15}, 15, {8}, "phosphoramidate_like_p_n_partial_double_bond"),
    )
    for endpoint_pattern, center_number, double_neighbor_numbers, reason in patterns:
        if atomic_numbers != endpoint_pattern:
            continue
        center = (
            bond.atom_i
            if system.atoms[bond.atom_i].atomic_number == center_number
            else bond.atom_j
        )
        for neighbor, neighbor_bond_index in adjacency[center]:
            if neighbor_bond_index == bond.index:
                continue
            neighbor_bond = system.bonds[neighbor_bond_index]
            if (
                neighbor_bond.order >= 1.9
                and system.atoms[neighbor].atomic_number in double_neighbor_numbers
            ):
                return reason
    return ""


def build_molecular_torsion_search_space(
    system: AllAtomSystem,
    *,
    config: MolecularTorsionSearchConfig | None = None,
) -> tuple[TorsionSearchSpace, MolecularTorsionSearchReceipt]:
    """Materialize one deterministic bridge-only torsion tree and receipt."""

    if not isinstance(system, AllAtomSystem):
        raise MolecularTorsionSearchError("system must be AllAtomSystem")
    require_valid_all_atom_system(system)
    active = MolecularTorsionSearchConfig() if config is None else config
    if not isinstance(active, MolecularTorsionSearchConfig):
        raise MolecularTorsionSearchError(
            "config must be MolecularTorsionSearchConfig"
        )
    if system.model_count != 1:
        raise MolecularTorsionSearchError(
            "molecular torsion search requires exactly one coordinate model"
        )
    if system.coordinates.device.type != "cpu" or system.coordinates.dtype not in {
        torch.float32,
        torch.float64,
    }:
        raise MolecularTorsionSearchError(
            "molecular torsion search requires CPU float32 or float64 coordinates"
        )
    if system.atom_count > active.max_atoms or len(system.bonds) > active.max_bonds:
        raise MolecularTorsionSearchError(
            "molecular torsion topology exceeds the configured capacity"
        )

    coordinates = system.coordinates[0]
    adjacency = _adjacency(system)
    heavy_indices = [
        atom.index for atom in system.atoms if atom.atomic_number != 1
    ]
    root = min(heavy_indices) if heavy_indices else 0
    parent_values, component_count = _breadth_first_parent(adjacency, root)
    if component_count != 1:
        raise MolecularTorsionSearchError(
            "molecular torsion search requires one connected covalent component"
        )
    bridges = _bridge_indices(adjacency)
    bond_rows: list[MolecularTorsionBondRow] = []
    selected_children: list[int] = []
    for bond in system.bonds:
        counts = (
            _bridge_heavy_counts(system, adjacency, bond)
            if bond.index in bridges
            else (0, 0)
        )
        if parent_values[bond.atom_j] == bond.atom_i:
            parent_atom, child_atom = bond.atom_i, bond.atom_j
        elif parent_values[bond.atom_i] == bond.atom_j:
            parent_atom, child_atom = bond.atom_j, bond.atom_i
        else:
            parent_atom, child_atom = -1, -1
        endpoint_numbers = (
            system.atoms[bond.atom_i].atomic_number,
            system.atoms[bond.atom_j].atomic_number,
        )
        reason = ""
        if bond.aromatic or bond.order != 1.0:
            reason = "not_nonaromatic_single_bond"
        elif 1 in endpoint_numbers:
            reason = "hydrogen_endpoint"
        elif bond.index not in bridges:
            reason = "ring_or_redundant_cycle_bond"
        elif min(counts) < 2:
            reason = "terminal_heavy_side"
        else:
            reason = _partial_double_bond_reason(system, adjacency, bond)
        selected = not reason
        if selected:
            if parent_atom < 0 or child_atom < 0:
                raise MolecularTorsionSearchError(
                    "selected bridge bond is missing a tree orientation"
                )
            reason = "selected_bridge_single_heavy_nonterminal"
            selected_children.append(child_atom)
        bond_rows.append(
            MolecularTorsionBondRow(
                bond_index=bond.index,
                atom_i=bond.atom_i,
                atom_j=bond.atom_j,
                bond_order=bond.order,
                aromatic=bond.aromatic,
                status="selected" if selected else "excluded",
                reason=reason,
                parent_atom_index=parent_atom,
                child_atom_index=child_atom,
                side_heavy_atom_counts=counts,
            )
        )
    if len(selected_children) > active.max_rotatable_bonds:
        raise MolecularTorsionSearchError(
            "perceived rotatable-bond count exceeds the configured capacity"
        )

    parent = torch.tensor(parent_values, dtype=torch.long)
    local_offsets = torch.zeros_like(coordinates)
    local_axes = torch.zeros_like(coordinates)
    local_axes[:, 2] = 1.0
    for atom_index, parent_index in enumerate(parent_values):
        if parent_index < 0:
            continue
        offset = coordinates[atom_index] - coordinates[parent_index]
        norm = torch.linalg.vector_norm(offset)
        if float(norm.item()) <= 1.0e-12:
            raise MolecularTorsionSearchError(
                "molecular torsion tree contains a zero-length covalent edge"
            )
        local_offsets[atom_index] = offset
        local_axes[atom_index] = offset / norm
    rotatable_mask = torch.zeros(system.atom_count, dtype=torch.bool)
    if selected_children:
        rotatable_mask[torch.tensor(selected_children, dtype=torch.long)] = True
    search_space = TorsionSearchSpace(
        local_offsets=local_offsets,
        parent=parent,
        local_axes=local_axes,
        rotatable_mask=rotatable_mask,
        root_positions=coordinates[root].reshape(1, 3),
    )
    reconstructed = torsion_tree_forward_kinematics(
        search_space.local_offsets,
        search_space.parent,
        torch.zeros(system.atom_count, dtype=coordinates.dtype),
        local_axes=search_space.local_axes,
        root_positions=search_space.root_positions,
    ).coordinates
    reconstruction_error = float((reconstructed - coordinates).abs().max().item())
    if reconstruction_error > active.reconstruction_tolerance_angstrom:
        raise MolecularTorsionSearchError(
            "zero-angle torsion tree does not reconstruct the source coordinates"
        )
    receipt = MolecularTorsionSearchReceipt(
        system_sha256=canonical_system_sha256(system),
        topology_sha256=canonical_topology_sha256(system),
        input_coordinate_sha256=coordinate_fingerprint(coordinates),
        search_space_sha256=search_space.fingerprint_sha256,
        config_sha256=active.fingerprint_sha256,
        atom_count=system.atom_count,
        bond_count=len(system.bonds),
        root_atom_index=root,
        component_count=component_count,
        reconstruction_max_abs_error_angstrom=reconstruction_error,
        bond_rows=tuple(bond_rows),
    )
    return search_space, receipt


__all__ = [
    "MOLECULAR_TORSION_SEARCH_BLOCKERS",
    "MOLECULAR_TORSION_SEARCH_CONFIG_SCHEMA_ID",
    "MOLECULAR_TORSION_SEARCH_RECEIPT_SCHEMA_ID",
    "MolecularTorsionBondRow",
    "MolecularTorsionSearchConfig",
    "MolecularTorsionSearchError",
    "MolecularTorsionSearchReceipt",
    "build_molecular_torsion_search_space",
]
