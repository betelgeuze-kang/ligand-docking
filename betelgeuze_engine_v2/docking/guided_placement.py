"""Deterministic interaction-guided docking proposal placement.

The guided layer consumes authenticated receptor/ligand systems, derives a
bounded set of chemistry and shape anchors, and replaces part of the existing
uniform pocket-placement batch.  Uniform Haar/spherical proposals remain in
every multi-candidate guided batch and become the complete fallback when no
guided interaction mode is available.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any

import torch

from betelgeuze_engine_v2.ai import torsion_tree_forward_kinematics
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    require_valid_all_atom_system,
)

from .authority import (
    AuthenticatedDockingProblem,
    AuthenticatedDockingSearchResult,
    DockingAuthorityError,
)
from .identity import coordinate_fingerprint
from .placement import (
    _PROPOSAL_OVERRIDE,
    _ProposalOverride,
    _budget_sha256,
    _counter_uniform,
    _stable_candidate_id,
    generate_pocket_centered_docking_proposals,
)
from .proposals import DockingBudget, DockingProposal


GUIDED_PLACEMENT_CONTEXT_SCHEMA_ID = (
    "betelgeuze.engine_v2_guided_placement_context/1.0.0"
)
GUIDED_PLACEMENT_POLICY_SCHEMA_ID = "betelgeuze.engine_v2_guided_placement_policy/1.1.0"
GUIDED_PLACEMENT_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_guided_placement_receipt/1.0.0"
)
GUIDED_PLACEMENT_SEARCH_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_guided_placement_search_result/1.0.0"
)
GUIDED_PLACEMENT_POLICY_ID = (
    "betelgeuze.engine_v2_interaction_guided_with_uniform_fallback/1.1.0"
)
GUIDED_FEATURE_POLICY_ID = "betelgeuze.engine_v2_bounded_graph_guidance_features/1.0.0"
GUIDED_MODES = (
    "donor_acceptor_hotspot",
    "charge_anchor",
    "hydrophobic_patch",
    "aromatic_plane",
    "shape_complementarity",
)
UNIFORM_FALLBACK_MODE = "uniform_fallback"
MAX_GUIDED_FEATURE_ATOMS = 2_048
MAX_GUIDED_AROMATIC_SYSTEMS = 128
MAX_GUIDED_RECEPTOR_BONDS_SCANNED = 1_000_000
_CENTROID_TOLERANCE_ANGSTROM = 1.0e-10
_FEATURE_KINDS = (
    "donor",
    "acceptor",
    "positive",
    "negative",
    "hydrophobic",
    "aromatic",
)


class _GuidanceUnavailable(RuntimeError):
    """One guided mode is unavailable for one sampled conformer."""


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
        raise DockingAuthorityError(
            "guided placement state is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise DockingAuthorityError(f"{name} must be a lowercase SHA-256")
    return text


def _freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DockingAuthorityError(
                "guided placement metadata floats must be finite"
            )
        return float(value)
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_json(item) for item in value)
    raise DockingAuthorityError("guided placement metadata is not JSON-compatible")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _tuple3(value: Sequence[float], *, name: str) -> tuple[float, float, float]:
    if len(value) != 3:
        raise DockingAuthorityError(f"{name} must have three components")
    result = tuple(float(component) for component in value)
    if any(not math.isfinite(component) for component in result):
        raise DockingAuthorityError(f"{name} must be finite")
    return result  # type: ignore[return-value]


def _coordinates_tuple(value: torch.Tensor) -> tuple[float, float, float]:
    return _tuple3(value.detach().to(dtype=torch.float64).tolist(), name="coordinate")


def _adjacency(
    system: AllAtomSystem,
    *,
    allowed_indices: set[int] | None = None,
) -> dict[int, tuple[int, ...]]:
    if allowed_indices is None:
        retained = set(range(system.atom_count))
    else:
        retained = set(allowed_indices)
        first_hop = set(retained)
        for bond in system.bonds:
            first, second = int(bond.atom_i), int(bond.atom_j)
            if first in retained or second in retained:
                first_hop.update((first, second))
        retained = set(first_hop)
        for bond in system.bonds:
            first, second = int(bond.atom_i), int(bond.atom_j)
            if first in first_hop or second in first_hop:
                retained.update((first, second))
    rows = {index: set() for index in retained}
    for bond in system.bonds:
        first, second = int(bond.atom_i), int(bond.atom_j)
        if first in retained and second in retained:
            rows[first].add(second)
            rows[second].add(first)
    return {index: tuple(sorted(row)) for index, row in rows.items()}


def _bond_by_pair(
    system: AllAtomSystem,
    *,
    retained_indices: set[int] | None = None,
) -> dict[tuple[int, int], Any]:
    return {
        tuple(sorted((int(bond.atom_i), int(bond.atom_j)))): bond
        for bond in system.bonds
        if retained_indices is None
        or (
            int(bond.atom_i) in retained_indices
            and int(bond.atom_j) in retained_indices
        )
    }


def _is_amide_or_sulfonamide_nitrogen(
    system: AllAtomSystem,
    atom_index: int,
    adjacency: Mapping[int, tuple[int, ...]],
    bonds: Mapping[tuple[int, int], Any],
) -> bool:
    if system.atoms[atom_index].element.upper() != "N":
        return False
    for neighbor in adjacency[atom_index]:
        center_element = system.atoms[neighbor].element.upper()
        oxygen_equivalents = sum(
            system.atoms[other].element.upper() == "O"
            and (
                math.isclose(
                    float(bonds[tuple(sorted((neighbor, other)))].order),
                    2.0,
                    abs_tol=1.0e-6,
                )
                or (
                    center_element == "S"
                    and int(system.atoms[neighbor].formal_charge) > 0
                    and int(system.atoms[other].formal_charge) < 0
                )
            )
            for other in adjacency[neighbor]
            if other != atom_index
        )
        if center_element == "C" and oxygen_equivalents >= 1:
            return True
        if center_element == "S" and oxygen_equivalents >= 2:
            return True
    return False


def _feature_indices(
    system: AllAtomSystem,
    *,
    allowed_indices: set[int] | None = None,
) -> dict[str, tuple[int, ...]]:
    adjacency = _adjacency(system, allowed_indices=allowed_indices)
    bonds = _bond_by_pair(
        system,
        retained_indices=set(adjacency),
    )
    donors: list[int] = []
    acceptors: list[int] = []
    positive: list[int] = []
    negative: list[int] = []
    hydrophobic: list[int] = []
    aromatic: list[int] = []
    for atom in system.atoms:
        index = int(atom.index)
        if allowed_indices is not None and index not in allowed_indices:
            continue
        element = atom.element.upper()
        charge = int(atom.formal_charge)
        attached_hydrogen = any(
            system.atoms[neighbor].element.upper() == "H"
            for neighbor in adjacency[index]
        )
        if element in {"N", "O", "S"} and attached_hydrogen:
            donors.append(index)
        if (
            element in {"N", "O", "S"}
            and charge <= 0
            and not (element == "N" and bool(atom.aromatic) and attached_hydrogen)
            and not _is_amide_or_sulfonamide_nitrogen(
                system,
                index,
                adjacency,
                bonds,
            )
        ):
            acceptors.append(index)
        if charge > 0:
            positive.append(index)
        elif charge < 0:
            negative.append(index)
        if charge == 0 and element in {"C", "S", "F", "CL", "BR", "I"}:
            hydrophobic.append(index)
        if bool(atom.aromatic):
            aromatic.append(index)
    result = {
        "donor": tuple(donors),
        "acceptor": tuple(acceptors),
        "positive": tuple(positive),
        "negative": tuple(negative),
        "hydrophobic": tuple(hydrophobic),
        "aromatic": tuple(aromatic),
    }
    if any(len(indices) > MAX_GUIDED_FEATURE_ATOMS for indices in result.values()):
        raise DockingAuthorityError("guided feature atom count exceeds its hard bound")
    return result


def _aromatic_systems(
    system: AllAtomSystem,
    *,
    allowed_indices: set[int] | None = None,
) -> tuple[tuple[int, ...], ...]:
    aromatic_atoms = {int(atom.index) for atom in system.atoms if bool(atom.aromatic)}
    if allowed_indices is not None:
        aromatic_atoms &= allowed_indices
    rows: dict[int, set[int]] = {index: set() for index in aromatic_atoms}
    for bond in system.bonds:
        first, second = int(bond.atom_i), int(bond.atom_j)
        if first in aromatic_atoms and second in aromatic_atoms and bool(bond.aromatic):
            rows[first].add(second)
            rows[second].add(first)
    remaining = set(aromatic_atoms)
    systems: list[tuple[int, ...]] = []
    while remaining:
        root = min(remaining)
        component = {root}
        frontier = [root]
        while frontier:
            node = frontier.pop()
            for neighbor in sorted(rows[node]):
                if neighbor not in component:
                    component.add(neighbor)
                    frontier.append(neighbor)
        remaining -= component
        if len(component) >= 3:
            systems.append(tuple(sorted(component)))
    if len(systems) > MAX_GUIDED_AROMATIC_SYSTEMS:
        raise DockingAuthorityError(
            "guided aromatic system count exceeds its hard bound"
        )
    return tuple(systems)


def _hydrophobic_patches(
    system: AllAtomSystem,
    hydrophobic_indices: Sequence[int],
    *,
    allowed_indices: set[int] | None = None,
) -> tuple[tuple[int, ...], ...]:
    allowed = set(int(index) for index in hydrophobic_indices)
    if allowed_indices is not None:
        allowed &= allowed_indices
    adjacency = _adjacency(system, allowed_indices=allowed_indices)
    remaining = set(allowed)
    patches: list[tuple[int, ...]] = []
    while remaining:
        root = min(remaining)
        component = {root}
        frontier = [root]
        while frontier:
            node = frontier.pop()
            for neighbor in adjacency[node]:
                if neighbor in allowed and neighbor not in component:
                    component.add(neighbor)
                    frontier.append(neighbor)
        remaining -= component
        patches.append(tuple(sorted(component)))
    return tuple(patches)


def _plane(
    coordinates: torch.Tensor,
    atom_indices: Sequence[int],
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    points = coordinates[list(atom_indices)].to(dtype=torch.float64)
    center = points.mean(dim=0)
    centered = points - center
    _, singular_values, vh = torch.linalg.svd(centered, full_matrices=False)
    if len(singular_values) < 2 or float(singular_values[1].item()) <= 1.0e-8:
        return None
    normal = vh[-1]
    largest = int(torch.argmax(normal.abs()).item())
    if float(normal[largest].item()) < 0.0:
        normal = -normal
    normal = normal / torch.linalg.vector_norm(normal)
    return _coordinates_tuple(center), _coordinates_tuple(normal)


def _principal_axes(
    coordinates: torch.Tensor,
) -> tuple[tuple[float, ...], ...] | None:
    points = coordinates.to(dtype=torch.float64)
    if points.ndim != 2 or points.shape[1] != 3 or points.shape[0] < 3:
        return None
    centered = points - points.mean(dim=0)
    _, singular_values, vh = torch.linalg.svd(centered, full_matrices=False)
    if (
        vh.shape != (3, 3)
        or len(singular_values) != 3
        or float(singular_values[1].item()) <= 1.0e-8
    ):
        return None
    values = tuple(float(value.item()) for value in singular_values)
    if math.isclose(
        values[0], values[1], rel_tol=1.0e-8, abs_tol=1.0e-10
    ) or math.isclose(values[1], values[2], rel_tol=1.0e-8, abs_tol=1.0e-10):
        return None
    axes = vh.T
    for column in range(3):
        largest = int(torch.argmax(axes[:, column].abs()).item())
        if float(axes[largest, column].item()) < 0.0:
            axes[:, column] = -axes[:, column]
    if float(torch.linalg.det(axes).item()) < 0.0:
        axes[:, -1] = -axes[:, -1]
    return tuple(tuple(float(value) for value in row) for row in axes.tolist())


@dataclass(frozen=True, slots=True)
class GuidedPlacementContext:
    authority_input_receipt_sha256: str
    receptor_system_sha256: str
    ligand_system_sha256: str
    ligand_features: Mapping[str, tuple[int, ...]]
    receptor_feature_rows: Mapping[
        str,
        tuple[tuple[int, tuple[float, float, float], int], ...],
    ]
    receptor_atom_indices: tuple[int, ...]
    ligand_hydrophobic_patches: tuple[tuple[int, ...], ...]
    receptor_hydrophobic_patches: tuple[
        tuple[tuple[int, ...], tuple[float, float, float]],
        ...,
    ]
    ligand_aromatic_systems: tuple[tuple[int, ...], ...]
    receptor_aromatic_planes: tuple[
        tuple[tuple[int, ...], tuple[float, float, float], tuple[float, float, float]],
        ...,
    ]
    receptor_shape_axes: tuple[tuple[float, ...], ...]
    ligand_shape_frame_available: bool
    ligand_shape_atom_count: int
    receptor_shape_atom_count: int
    feature_policy_id: str = GUIDED_FEATURE_POLICY_ID
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "authority_input_receipt_sha256",
            "receptor_system_sha256",
            "ligand_system_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if self.feature_policy_id != GUIDED_FEATURE_POLICY_ID:
            raise DockingAuthorityError("unsupported guided feature policy")
        ligand_features = {
            str(name): tuple(int(value) for value in values)
            for name, values in self.ligand_features.items()
        }
        if set(ligand_features) != set(_FEATURE_KINDS) or any(
            values != tuple(sorted(set(values))) for values in ligand_features.values()
        ):
            raise DockingAuthorityError("guided ligand features are invalid")
        receptor_atom_indices = tuple(
            int(value) for value in self.receptor_atom_indices
        )
        if receptor_atom_indices != tuple(sorted(set(receptor_atom_indices))) or any(
            value < 0 for value in receptor_atom_indices
        ):
            raise DockingAuthorityError("guided receptor atom indices are invalid")
        allowed_receptor = set(receptor_atom_indices)
        receptor_rows: dict[
            str,
            tuple[tuple[int, tuple[float, float, float], int], ...],
        ] = {}
        for name, rows in self.receptor_feature_rows.items():
            normalized = tuple(
                (
                    int(index),
                    _tuple3(coordinate, name="receptor feature coordinate"),
                    int(charge),
                )
                for index, coordinate, charge in rows
            )
            if tuple(index for index, _, _ in normalized) != tuple(
                sorted({index for index, _, _ in normalized})
            ) or any(index not in allowed_receptor for index, _, _ in normalized):
                raise DockingAuthorityError("guided receptor features are invalid")
            receptor_rows[str(name)] = normalized
        if set(receptor_rows) != set(ligand_features):
            raise DockingAuthorityError("guided receptor feature kinds are incomplete")
        ligand_hydrophobic_patches = tuple(
            tuple(int(value) for value in patch)
            for patch in self.ligand_hydrophobic_patches
        )
        receptor_hydrophobic_patches = tuple(
            (
                tuple(int(value) for value in patch),
                _tuple3(center, name="receptor hydrophobic patch center"),
            )
            for patch, center in self.receptor_hydrophobic_patches
        )
        if any(
            not patch
            or patch != tuple(sorted(set(patch)))
            or not set(patch).issubset(set(ligand_features["hydrophobic"]))
            for patch in ligand_hydrophobic_patches
        ) or any(
            not patch
            or patch != tuple(sorted(set(patch)))
            or not set(patch).issubset(allowed_receptor)
            or not set(patch).issubset(
                {index for index, _, _ in receptor_rows["hydrophobic"]}
            )
            for patch, _ in receptor_hydrophobic_patches
        ):
            raise DockingAuthorityError("guided hydrophobic patches are invalid")
        ligand_aromatic = tuple(
            tuple(int(value) for value in system)
            for system in self.ligand_aromatic_systems
        )
        if any(
            len(system) < 3 or system != tuple(sorted(set(system)))
            for system in ligand_aromatic
        ):
            raise DockingAuthorityError("guided ligand aromatic systems are invalid")
        receptor_planes = tuple(
            (
                tuple(int(value) for value in atom_indices),
                _tuple3(center, name="aromatic plane center"),
                _tuple3(normal, name="aromatic plane normal"),
            )
            for atom_indices, center, normal in self.receptor_aromatic_planes
        )
        if any(
            len(atom_indices) < 3
            or atom_indices != tuple(sorted(set(atom_indices)))
            or not set(atom_indices).issubset(allowed_receptor)
            or not math.isclose(
                math.sqrt(sum(value * value for value in normal)),
                1.0,
                abs_tol=1.0e-10,
            )
            for atom_indices, _, normal in receptor_planes
        ):
            raise DockingAuthorityError("guided receptor aromatic planes are invalid")
        axes = tuple(
            _tuple3(row, name="receptor shape axis row")
            for row in self.receptor_shape_axes
        )
        if axes and len(axes) != 3:
            raise DockingAuthorityError("receptor shape axes must be empty or 3x3")
        if type(self.ligand_shape_frame_available) is not bool:
            raise DockingAuthorityError(
                "ligand shape frame availability must be boolean"
            )
        ligand_shape_atom_count = int(self.ligand_shape_atom_count)
        receptor_shape_atom_count = int(self.receptor_shape_atom_count)
        if ligand_shape_atom_count < 1 or receptor_shape_atom_count < 1:
            raise DockingAuthorityError("guided shape atom counts must be positive")
        if receptor_shape_atom_count != len(receptor_atom_indices):
            raise DockingAuthorityError(
                "guided receptor shape atom count is cross-wired"
            )
        if any(
            index < 0 or index >= ligand_shape_atom_count
            for values in ligand_features.values()
            for index in values
        ) or any(
            index < 0 or index >= ligand_shape_atom_count
            for system in ligand_aromatic
            for index in system
        ):
            raise DockingAuthorityError("guided ligand feature index is out of bounds")
        if axes:
            axes_tensor = torch.tensor(axes, dtype=torch.float64)
            identity = torch.eye(3, dtype=torch.float64)
            if not torch.allclose(
                axes_tensor.T @ axes_tensor,
                identity,
                atol=1.0e-10,
                rtol=0.0,
            ) or not math.isclose(
                float(torch.linalg.det(axes_tensor).item()),
                1.0,
                abs_tol=1.0e-10,
            ):
                raise DockingAuthorityError(
                    "receptor shape axes are not a proper frame"
                )
        object.__setattr__(self, "ligand_features", MappingProxyType(ligand_features))
        object.__setattr__(
            self, "receptor_feature_rows", MappingProxyType(receptor_rows)
        )
        object.__setattr__(self, "receptor_atom_indices", receptor_atom_indices)
        object.__setattr__(
            self,
            "ligand_hydrophobic_patches",
            ligand_hydrophobic_patches,
        )
        object.__setattr__(
            self,
            "receptor_hydrophobic_patches",
            receptor_hydrophobic_patches,
        )
        object.__setattr__(self, "ligand_aromatic_systems", ligand_aromatic)
        object.__setattr__(self, "receptor_aromatic_planes", receptor_planes)
        object.__setattr__(self, "receptor_shape_axes", axes)
        object.__setattr__(self, "ligand_shape_atom_count", ligand_shape_atom_count)
        object.__setattr__(self, "receptor_shape_atom_count", receptor_shape_atom_count)
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": GUIDED_PLACEMENT_CONTEXT_SCHEMA_ID,
            "feature_policy_id": self.feature_policy_id,
            "authority_input_receipt_sha256": self.authority_input_receipt_sha256,
            "receptor_system_sha256": self.receptor_system_sha256,
            "ligand_system_sha256": self.ligand_system_sha256,
            "ligand_features": {
                name: list(values) for name, values in self.ligand_features.items()
            },
            "receptor_feature_rows": {
                name: [
                    {
                        "atom_index": index,
                        "coordinate_binary64_hex": [
                            value.hex() for value in coordinate
                        ],
                        "formal_charge": charge,
                    }
                    for index, coordinate, charge in rows
                ]
                for name, rows in self.receptor_feature_rows.items()
            },
            "receptor_atom_indices": list(self.receptor_atom_indices),
            "ligand_hydrophobic_patches": [
                list(patch) for patch in self.ligand_hydrophobic_patches
            ],
            "receptor_hydrophobic_patches": [
                {
                    "atom_indices": list(patch),
                    "center_binary64_hex": [value.hex() for value in center],
                }
                for patch, center in self.receptor_hydrophobic_patches
            ],
            "ligand_aromatic_systems": [
                list(row) for row in self.ligand_aromatic_systems
            ],
            "receptor_aromatic_planes": [
                {
                    "atom_indices": list(indices),
                    "center_binary64_hex": [value.hex() for value in center],
                    "normal_binary64_hex": [value.hex() for value in normal],
                }
                for indices, center, normal in self.receptor_aromatic_planes
            ],
            "receptor_shape_axes_binary64_hex": [
                [value.hex() for value in row] for row in self.receptor_shape_axes
            ],
            "ligand_shape_atom_count": self.ligand_shape_atom_count,
            "receptor_shape_atom_count": self.receptor_shape_atom_count,
            "shape_frame_available": bool(self.receptor_shape_axes),
            "ligand_shape_frame_available": self.ligand_shape_frame_available,
            "max_receptor_bonds_scanned": MAX_GUIDED_RECEPTOR_BONDS_SCANNED,
            "chemistry_feature_perception_scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise DockingAuthorityError("guided placement context changed")
        return observed

    def feature_counts(self) -> dict[str, int]:
        return (
            {
                f"ligand_{name}": len(values)
                for name, values in self.ligand_features.items()
            }
            | {
                f"receptor_{name}": len(values)
                for name, values in self.receptor_feature_rows.items()
            }
            | {
                "ligand_aromatic_system": len(self.ligand_aromatic_systems),
                "receptor_aromatic_plane": len(self.receptor_aromatic_planes),
                "ligand_hydrophobic_patch": len(self.ligand_hydrophobic_patches),
                "receptor_hydrophobic_patch": len(self.receptor_hydrophobic_patches),
                "ligand_shape_atom": self.ligand_shape_atom_count,
                "receptor_shape_atom": self.receptor_shape_atom_count,
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


@dataclass(frozen=True, slots=True)
class GuidedPlacementPolicy:
    guided_fraction: float = 0.75
    minimum_uniform_fraction: float = 0.375
    maximum_guided_candidates_per_mode: int = 8
    donor_acceptor_distance_angstrom: float = 2.9
    charge_anchor_distance_angstrom: float = 3.5
    hydrophobic_distance_angstrom: float = 3.8
    aromatic_plane_distance_angstrom: float = 3.6
    policy_id: str = GUIDED_PLACEMENT_POLICY_ID
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.policy_id != GUIDED_PLACEMENT_POLICY_ID:
            raise DockingAuthorityError("unsupported guided placement policy")
        fraction = float(self.guided_fraction)
        if not math.isfinite(fraction) or not 0.0 < fraction <= 1.0:
            raise DockingAuthorityError("guided_fraction must be in (0,1]")
        object.__setattr__(self, "guided_fraction", fraction)
        minimum_uniform_fraction = float(self.minimum_uniform_fraction)
        if (
            not math.isfinite(minimum_uniform_fraction)
            or not 0.0 < minimum_uniform_fraction < 1.0
        ):
            raise DockingAuthorityError(
                "minimum_uniform_fraction must be in (0,1)"
            )
        if (
            type(self.maximum_guided_candidates_per_mode) is not int
            or not 1 <= self.maximum_guided_candidates_per_mode <= 64
        ):
            raise DockingAuthorityError(
                "maximum_guided_candidates_per_mode must be in [1,64]"
            )
        object.__setattr__(
            self, "minimum_uniform_fraction", minimum_uniform_fraction
        )
        for name in (
            "donor_acceptor_distance_angstrom",
            "charge_anchor_distance_angstrom",
            "hydrophobic_distance_angstrom",
            "aromatic_plane_distance_angstrom",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 1.0 <= value <= 8.0:
                raise DockingAuthorityError(f"{name} is outside its hard bound")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": GUIDED_PLACEMENT_POLICY_SCHEMA_ID,
            "policy_id": self.policy_id,
            "guided_modes": list(GUIDED_MODES),
            "guided_fraction_binary64_hex": self.guided_fraction.hex(),
            "allocation_strategy": "available_mode_capped_with_uniform_floor",
            "minimum_uniform_fraction_binary64_hex": (
                self.minimum_uniform_fraction.hex()
            ),
            "maximum_guided_candidates_per_mode": (
                self.maximum_guided_candidates_per_mode
            ),
            "donor_acceptor_distance_angstrom_binary64_hex": self.donor_acceptor_distance_angstrom.hex(),
            "charge_anchor_distance_angstrom_binary64_hex": self.charge_anchor_distance_angstrom.hex(),
            "hydrophobic_distance_angstrom_binary64_hex": self.hydrophobic_distance_angstrom.hex(),
            "aromatic_plane_distance_angstrom_binary64_hex": self.aromatic_plane_distance_angstrom.hex(),
            "uniform_random_placement_retained_as_fallback": True,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise DockingAuthorityError("guided placement policy changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


def build_guided_placement_context(
    authenticated_problem: AuthenticatedDockingProblem,
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
) -> GuidedPlacementContext:
    if not isinstance(authenticated_problem, AuthenticatedDockingProblem):
        raise TypeError("authenticated_problem must be AuthenticatedDockingProblem")
    for name, system in (
        ("receptor_system", receptor_system),
        ("ligand_system", ligand_system),
    ):
        if not isinstance(system, AllAtomSystem):
            raise TypeError(f"{name} must be AllAtomSystem")
        require_valid_all_atom_system(system)
    authenticated_problem.input_receipt_sha256
    receptor_sha256 = canonical_system_sha256(receptor_system)
    ligand_sha256 = canonical_system_sha256(ligand_system)
    if receptor_sha256 != authenticated_problem.receptor_system_sha256:
        raise DockingAuthorityError("guided receptor system is cross-wired")
    if ligand_sha256 != authenticated_problem.ligand_system_sha256:
        raise DockingAuthorityError("guided ligand system is cross-wired")
    if len(receptor_system.bonds) > MAX_GUIDED_RECEPTOR_BONDS_SCANNED:
        raise DockingAuthorityError(
            "guided receptor bond count exceeds its hard scan bound"
        )
    receptor_coordinates = (
        receptor_system.coordinates[authenticated_problem.receptor_model_index]
        .detach()
        .to(dtype=torch.float64, device="cpu")
    )
    ligand_coordinates = (
        ligand_system.coordinates[authenticated_problem.ligand_model_index]
        .detach()
        .to(dtype=torch.float64, device="cpu")
    )
    allowed_receptor = set(authenticated_problem.receptor_atom_indices)
    receptor_features_full = _feature_indices(
        receptor_system,
        allowed_indices=allowed_receptor,
    )
    ligand_features = _feature_indices(ligand_system)
    receptor_rows = {
        name: tuple(
            (
                index,
                _coordinates_tuple(receptor_coordinates[index]),
                int(receptor_system.atoms[index].formal_charge),
            )
            for index in values
            if index in allowed_receptor
        )
        for name, values in receptor_features_full.items()
    }
    receptor_aromatic_planes = []
    for system in _aromatic_systems(
        receptor_system,
        allowed_indices=allowed_receptor,
    ):
        observed = _plane(receptor_coordinates, system)
        if observed is not None:
            center, normal = observed
            receptor_aromatic_planes.append((system, center, normal))
    receptor_subset_coordinates = receptor_coordinates[
        list(authenticated_problem.receptor_atom_indices)
    ]
    ligand_hydrophobic_patches = _hydrophobic_patches(
        ligand_system,
        ligand_features["hydrophobic"],
    )
    receptor_hydrophobic_patch_indices = _hydrophobic_patches(
        receptor_system,
        receptor_features_full["hydrophobic"],
        allowed_indices=allowed_receptor,
    )
    return GuidedPlacementContext(
        authority_input_receipt_sha256=authenticated_problem.input_receipt_sha256,
        receptor_system_sha256=receptor_sha256,
        ligand_system_sha256=ligand_sha256,
        ligand_features=ligand_features,
        receptor_feature_rows=receptor_rows,
        receptor_atom_indices=authenticated_problem.receptor_atom_indices,
        ligand_hydrophobic_patches=ligand_hydrophobic_patches,
        receptor_hydrophobic_patches=tuple(
            (
                patch,
                _coordinates_tuple(receptor_coordinates[list(patch)].mean(dim=0)),
            )
            for patch in receptor_hydrophobic_patch_indices
        ),
        ligand_aromatic_systems=tuple(
            system
            for system in _aromatic_systems(ligand_system)
            if _plane(ligand_coordinates, system) is not None
        ),
        receptor_aromatic_planes=tuple(receptor_aromatic_planes),
        receptor_shape_axes=(_principal_axes(receptor_subset_coordinates) or ()),
        ligand_shape_frame_available=(_principal_axes(ligand_coordinates) is not None),
        ligand_shape_atom_count=ligand_system.atom_count,
        receptor_shape_atom_count=len(authenticated_problem.receptor_atom_indices),
    )


def _available_modes(context: GuidedPlacementContext) -> tuple[str, ...]:
    ligand = context.ligand_features
    receptor = context.receptor_feature_rows
    modes = []
    if (ligand["donor"] and receptor["acceptor"]) or (
        ligand["acceptor"] and receptor["donor"]
    ):
        modes.append("donor_acceptor_hotspot")
    if (ligand["positive"] and receptor["negative"]) or (
        ligand["negative"] and receptor["positive"]
    ):
        modes.append("charge_anchor")
    if context.ligand_hydrophobic_patches and context.receptor_hydrophobic_patches:
        modes.append("hydrophobic_patch")
    if context.ligand_aromatic_systems and context.receptor_aromatic_planes:
        modes.append("aromatic_plane")
    if context.ligand_shape_frame_available and context.receptor_shape_axes:
        modes.append("shape_complementarity")
    return tuple(modes)


def _pick_index(length: int, *, seed: int, proposal_index: int, domain: str) -> int:
    if length < 1:
        raise DockingAuthorityError("guided anchor collection is empty")
    value = _counter_uniform(
        seed=seed,
        proposal_index=proposal_index,
        domain=domain,
        counter=0,
    )
    return min(length - 1, int(value * length))


def _unit_toward_pocket(
    receptor_coordinate: torch.Tensor,
    pocket_center: torch.Tensor,
    *,
    seed: int,
    proposal_index: int,
) -> torch.Tensor:
    direction = pocket_center - receptor_coordinate
    norm = float(torch.linalg.vector_norm(direction).item())
    if norm > 1.0e-12:
        return direction / norm
    values = torch.tensor(
        [
            2.0
            * _counter_uniform(
                seed=seed,
                proposal_index=proposal_index,
                domain="guided-degenerate-direction",
                counter=counter,
            )
            - 1.0
            for counter in range(3)
        ],
        dtype=receptor_coordinate.dtype,
    )
    return values / torch.linalg.vector_norm(values)


def _rotation_between(first: torch.Tensor, second: torch.Tensor) -> torch.Tensor:
    source = first / torch.linalg.vector_norm(first)
    target = second / torch.linalg.vector_norm(second)
    cross = torch.cross(source, target, dim=0)
    sine = float(torch.linalg.vector_norm(cross).item())
    cosine = float(torch.dot(source, target).item())
    identity = torch.eye(3, dtype=source.dtype)
    if sine <= 1.0e-12:
        if cosine > 0.0:
            return identity
        basis = torch.tensor([1.0, 0.0, 0.0], dtype=source.dtype)
        if abs(float(source[0].item())) > 0.8:
            basis = torch.tensor([0.0, 1.0, 0.0], dtype=source.dtype)
        axis = torch.cross(source, basis, dim=0)
        axis = axis / torch.linalg.vector_norm(axis)
        return 2.0 * torch.outer(axis, axis) - identity
    axis = cross / sine
    zero = torch.zeros((), dtype=source.dtype)
    skew = torch.stack(
        (
            torch.stack((zero, -axis[2], axis[1])),
            torch.stack((axis[2], zero, -axis[0])),
            torch.stack((-axis[1], axis[0], zero)),
        )
    )
    return identity + sine * skew + (1.0 - cosine) * (skew @ skew)


def _principal_rotation(
    ligand_coordinates: torch.Tensor,
    receptor_axes: tuple[tuple[float, ...], ...],
) -> torch.Tensor:
    ligand_frame = _principal_axes(ligand_coordinates)
    if ligand_frame is None:
        raise _GuidanceUnavailable("guided ligand shape frame is degenerate")
    ligand_axes = torch.tensor(ligand_frame, dtype=ligand_coordinates.dtype)
    target_axes = torch.tensor(receptor_axes, dtype=ligand_coordinates.dtype)
    rotation = target_axes @ ligand_axes.T
    if float(torch.linalg.det(rotation).item()) < 0.0:
        target_axes[:, -1] = -target_axes[:, -1]
        rotation = target_axes @ ligand_axes.T
    identity = torch.eye(3, dtype=rotation.dtype)
    if not torch.allclose(
        rotation.T @ rotation,
        identity,
        atol=1.0e-10,
        rtol=0.0,
    ) or not math.isclose(
        float(torch.linalg.det(rotation).item()),
        1.0,
        abs_tol=1.0e-10,
    ):
        raise DockingAuthorityError("guided shape rotation is not proper")
    return rotation


def _anchor_coordinates(
    coordinates: torch.Tensor,
    atom_indices: Sequence[int],
) -> torch.Tensor:
    return coordinates[list(atom_indices)].mean(dim=0)


def _guided_transform(
    *,
    mode: str,
    context: GuidedPlacementContext,
    policy: GuidedPlacementPolicy,
    conformer: torch.Tensor,
    base_rotation: torch.Tensor,
    pocket_center: torch.Tensor,
    translation_radius_angstrom: float,
    seed: int,
    proposal_index: int,
) -> tuple[
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
    tuple[int, ...],
    tuple[int, ...],
    float,
    float,
]:
    ligand = context.ligand_features
    receptor = context.receptor_feature_rows
    rotation = base_rotation
    ligand_anchor_indices: tuple[int, ...]
    receptor_coordinate: torch.Tensor
    receptor_anchor_indices: tuple[int, ...]
    anchor_direction: torch.Tensor | None = None
    distance: float
    if mode == "donor_acceptor_hotspot":
        choices = []
        if ligand["donor"] and receptor["acceptor"]:
            choices.append((ligand["donor"], receptor["acceptor"]))
        if ligand["acceptor"] and receptor["donor"]:
            choices.append((ligand["acceptor"], receptor["donor"]))
        ligand_rows, receptor_rows = choices[
            _pick_index(
                len(choices),
                seed=seed,
                proposal_index=proposal_index,
                domain="donor-acceptor-direction",
            )
        ]
        ligand_anchor_indices = (
            ligand_rows[
                _pick_index(
                    len(ligand_rows),
                    seed=seed,
                    proposal_index=proposal_index,
                    domain="donor-acceptor-ligand",
                )
            ],
        )
        receptor_row = receptor_rows[
            _pick_index(
                len(receptor_rows),
                seed=seed,
                proposal_index=proposal_index,
                domain="donor-acceptor-receptor",
            )
        ]
        receptor_coordinate = torch.tensor(receptor_row[1], dtype=conformer.dtype)
        receptor_anchor_indices = (receptor_row[0],)
        distance = policy.donor_acceptor_distance_angstrom
    elif mode == "charge_anchor":
        choices = []
        if ligand["positive"] and receptor["negative"]:
            choices.append((ligand["positive"], receptor["negative"]))
        if ligand["negative"] and receptor["positive"]:
            choices.append((ligand["negative"], receptor["positive"]))
        ligand_rows, receptor_rows = choices[
            _pick_index(
                len(choices),
                seed=seed,
                proposal_index=proposal_index,
                domain="charge-direction",
            )
        ]
        ligand_anchor_indices = (
            ligand_rows[
                _pick_index(
                    len(ligand_rows),
                    seed=seed,
                    proposal_index=proposal_index,
                    domain="charge-ligand",
                )
            ],
        )
        receptor_row = receptor_rows[
            _pick_index(
                len(receptor_rows),
                seed=seed,
                proposal_index=proposal_index,
                domain="charge-receptor",
            )
        ]
        receptor_coordinate = torch.tensor(receptor_row[1], dtype=conformer.dtype)
        receptor_anchor_indices = (receptor_row[0],)
        distance = policy.charge_anchor_distance_angstrom
    elif mode == "hydrophobic_patch":
        ligand_anchor_indices = context.ligand_hydrophobic_patches[
            _pick_index(
                len(context.ligand_hydrophobic_patches),
                seed=seed,
                proposal_index=proposal_index,
                domain="hydrophobic-ligand-patch",
            )
        ]
        receptor_patch, receptor_center = context.receptor_hydrophobic_patches[
            _pick_index(
                len(context.receptor_hydrophobic_patches),
                seed=seed,
                proposal_index=proposal_index,
                domain="hydrophobic-receptor-patch",
            )
        ]
        receptor_coordinate = torch.tensor(
            receptor_center,
            dtype=conformer.dtype,
        )
        receptor_anchor_indices = receptor_patch
        distance = policy.hydrophobic_distance_angstrom
    elif mode == "aromatic_plane":
        ligand_system = context.ligand_aromatic_systems[
            _pick_index(
                len(context.ligand_aromatic_systems),
                seed=seed,
                proposal_index=proposal_index,
                domain="aromatic-ligand",
            )
        ]
        receptor_plane = context.receptor_aromatic_planes[
            _pick_index(
                len(context.receptor_aromatic_planes),
                seed=seed,
                proposal_index=proposal_index,
                domain="aromatic-receptor",
            )
        ]
        ligand_plane = _plane(conformer, ligand_system)
        if ligand_plane is None:
            raise _GuidanceUnavailable("guided ligand aromatic plane is degenerate")
        ligand_normal = torch.tensor(ligand_plane[1], dtype=conformer.dtype)
        receptor_normal = torch.tensor(receptor_plane[2], dtype=conformer.dtype)
        rotation = _rotation_between(ligand_normal, receptor_normal)
        ligand_anchor_indices = ligand_system
        receptor_anchor_indices = receptor_plane[0]
        receptor_coordinate = torch.tensor(receptor_plane[1], dtype=conformer.dtype)
        anchor_direction = receptor_normal
        if (
            float(
                torch.dot(anchor_direction, pocket_center - receptor_coordinate).item()
            )
            < 0.0
        ):
            anchor_direction = -anchor_direction
        distance = policy.aromatic_plane_distance_angstrom
    elif mode == "shape_complementarity":
        rotation = _principal_rotation(conformer, context.receptor_shape_axes)
        ligand_anchor_indices = tuple(range(len(conformer)))
        receptor_anchor_indices = ()
        receptor_coordinate = pocket_center
        distance = 0.0
    else:
        raise DockingAuthorityError("unsupported guided placement mode")

    rotated = conformer @ rotation.T
    ligand_anchor = _anchor_coordinates(rotated, ligand_anchor_indices)
    direction = anchor_direction
    if direction is None:
        direction = _unit_toward_pocket(
            receptor_coordinate,
            pocket_center,
            seed=seed,
            proposal_index=proposal_index,
        )
    target_anchor = receptor_coordinate + distance * direction
    translation = target_anchor - ligand_anchor
    coordinates = rotated + translation
    centroid = coordinates.mean(dim=0)
    centroid_delta = centroid - pocket_center
    centroid_distance = float(torch.linalg.vector_norm(centroid_delta).item())
    if centroid_distance > translation_radius_angstrom:
        bounded_centroid = pocket_center + centroid_delta * (
            translation_radius_angstrom / centroid_distance
        )
        correction = bounded_centroid - centroid
        coordinates = coordinates + correction
        translation = translation + correction
    observed_ligand_anchor = _anchor_coordinates(
        coordinates,
        ligand_anchor_indices,
    )
    observed_distance = float(
        torch.linalg.vector_norm(observed_ligand_anchor - receptor_coordinate).item()
    )
    return (
        coordinates.contiguous(),
        rotation.contiguous(),
        translation.contiguous(),
        tuple(ligand_anchor_indices),
        tuple(receptor_anchor_indices),
        float(distance),
        observed_distance,
    )


@dataclass(frozen=True, slots=True)
class GuidedPlacementReceipt:
    authenticated_input_receipt_sha256: str
    guidance_context_sha256: str
    guided_policy_sha256: str
    budget_sha256: str
    proposal_fingerprint_sha256s: tuple[str, ...]
    proposal_modes: tuple[str, ...]
    ligand_anchor_atom_indices: tuple[tuple[int, ...], ...]
    receptor_anchor_atom_indices: tuple[tuple[int, ...], ...]
    requested_anchor_distance_angstroms: tuple[float | None, ...]
    observed_anchor_distance_angstroms: tuple[float | None, ...]
    feature_counts: Mapping[str, int]
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "authenticated_input_receipt_sha256",
            "guidance_context_sha256",
            "guided_policy_sha256",
            "budget_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        fingerprints = tuple(
            _digest(value, name="proposal fingerprint")
            for value in self.proposal_fingerprint_sha256s
        )
        modes = tuple(str(value) for value in self.proposal_modes)
        allowed = set(GUIDED_MODES) | {UNIFORM_FALLBACK_MODE}
        if (
            not fingerprints
            or len(fingerprints) != len(modes)
            or any(mode not in allowed for mode in modes)
        ):
            raise DockingAuthorityError("guided proposal rows are invalid")
        ligand_anchors = tuple(
            tuple(int(index) for index in row)
            for row in self.ligand_anchor_atom_indices
        )
        receptor_anchors = tuple(
            tuple(int(index) for index in row)
            for row in self.receptor_anchor_atom_indices
        )
        requested_distances = tuple(
            None if value is None else float(value)
            for value in self.requested_anchor_distance_angstroms
        )
        observed_distances = tuple(
            None if value is None else float(value)
            for value in self.observed_anchor_distance_angstroms
        )
        row_count = len(fingerprints)
        if any(
            len(rows) != row_count
            for rows in (
                ligand_anchors,
                receptor_anchors,
                requested_distances,
                observed_distances,
            )
        ):
            raise DockingAuthorityError("guided anchor rows are incomplete")
        for mode, ligand_row, receptor_row, requested, observed in zip(
            modes,
            ligand_anchors,
            receptor_anchors,
            requested_distances,
            observed_distances,
        ):
            if (
                ligand_row != tuple(sorted(set(ligand_row)))
                or receptor_row != tuple(sorted(set(receptor_row)))
                or any(index < 0 for index in (*ligand_row, *receptor_row))
            ):
                raise DockingAuthorityError("guided anchor atom indices are invalid")
            if mode == UNIFORM_FALLBACK_MODE:
                if (
                    ligand_row
                    or receptor_row
                    or requested is not None
                    or observed is not None
                ):
                    raise DockingAuthorityError(
                        "uniform fallback cannot declare guided anchors"
                    )
            elif (
                not ligand_row
                or requested is None
                or observed is None
                or not math.isfinite(requested)
                or not math.isfinite(observed)
                or requested < 0.0
                or observed < 0.0
            ):
                raise DockingAuthorityError("guided anchor distances are invalid")
        counts = {str(name): int(value) for name, value in self.feature_counts.items()}
        if any(value < 0 for value in counts.values()):
            raise DockingAuthorityError("guided feature counts are invalid")
        object.__setattr__(self, "proposal_fingerprint_sha256s", fingerprints)
        object.__setattr__(self, "proposal_modes", modes)
        object.__setattr__(self, "ligand_anchor_atom_indices", ligand_anchors)
        object.__setattr__(self, "receptor_anchor_atom_indices", receptor_anchors)
        object.__setattr__(
            self, "requested_anchor_distance_angstroms", requested_distances
        )
        object.__setattr__(
            self, "observed_anchor_distance_angstroms", observed_distances
        )
        object.__setattr__(self, "feature_counts", MappingProxyType(counts))
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": GUIDED_PLACEMENT_RECEIPT_SCHEMA_ID,
            "authenticated_input_receipt_sha256": self.authenticated_input_receipt_sha256,
            "guidance_context_sha256": self.guidance_context_sha256,
            "guided_policy_sha256": self.guided_policy_sha256,
            "budget_sha256": self.budget_sha256,
            "proposal_count": len(self.proposal_modes),
            "proposal_fingerprint_sha256s": list(self.proposal_fingerprint_sha256s),
            "proposal_modes": list(self.proposal_modes),
            "proposal_guidance_rows": [
                {
                    "proposal_index": index,
                    "mode": mode,
                    "ligand_anchor_atom_indices": list(ligand_atoms),
                    "receptor_anchor_atom_indices": list(receptor_atoms),
                    "requested_anchor_distance_angstrom_binary64_hex": (
                        None if requested is None else requested.hex()
                    ),
                    "observed_anchor_distance_angstrom_binary64_hex": (
                        None if observed is None else observed.hex()
                    ),
                }
                for index, (
                    mode,
                    ligand_atoms,
                    receptor_atoms,
                    requested,
                    observed,
                ) in enumerate(
                    zip(
                        self.proposal_modes,
                        self.ligand_anchor_atom_indices,
                        self.receptor_anchor_atom_indices,
                        self.requested_anchor_distance_angstroms,
                        self.observed_anchor_distance_angstroms,
                    )
                )
            ],
            "guided_proposal_count": sum(
                mode != UNIFORM_FALLBACK_MODE for mode in self.proposal_modes
            ),
            "uniform_fallback_count": sum(
                mode == UNIFORM_FALLBACK_MODE for mode in self.proposal_modes
            ),
            "uniform_random_placement_retained_as_fallback": True,
            "feature_counts": dict(self.feature_counts),
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingAuthorityError("guided placement receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def generate_guided_docking_proposals(
    authenticated_problem: AuthenticatedDockingProblem,
    budget: DockingBudget,
    context: GuidedPlacementContext,
    *,
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    policy: GuidedPlacementPolicy | None = None,
) -> tuple[tuple[DockingProposal, ...], GuidedPlacementReceipt]:
    if not isinstance(authenticated_problem, AuthenticatedDockingProblem):
        raise TypeError("authenticated_problem must be AuthenticatedDockingProblem")
    if not isinstance(budget, DockingBudget):
        raise TypeError("budget must be DockingBudget")
    if not isinstance(context, GuidedPlacementContext):
        raise TypeError("context must be GuidedPlacementContext")
    selected_policy = GuidedPlacementPolicy() if policy is None else policy
    if not isinstance(selected_policy, GuidedPlacementPolicy):
        raise TypeError("policy must be GuidedPlacementPolicy")
    authenticated_problem.input_receipt_sha256
    if (
        context.authority_input_receipt_sha256
        != authenticated_problem.input_receipt_sha256
    ):
        raise DockingAuthorityError(
            "guided context is cross-wired to another authority"
        )
    if (
        context.receptor_system_sha256 != authenticated_problem.receptor_system_sha256
        or context.ligand_system_sha256 != authenticated_problem.ligand_system_sha256
        or context.receptor_atom_indices != authenticated_problem.receptor_atom_indices
    ):
        raise DockingAuthorityError("guided context system identity is cross-wired")
    context.fingerprint_sha256
    derived_context = build_guided_placement_context(
        authenticated_problem,
        receptor_system,
        ligand_system,
    )
    if derived_context.fingerprint_sha256 != context.fingerprint_sha256:
        raise DockingAuthorityError(
            "guided context does not match its authenticated derivation"
        )
    selected_policy.fingerprint_sha256
    baseline, _ = generate_pocket_centered_docking_proposals(
        authenticated_problem,
        budget,
    )
    modes = _available_modes(context)
    if modes:
        fraction_cap = int(
            math.floor(
                budget.candidate_count * selected_policy.guided_fraction
            )
        )
        mode_cap = (
            len(modes) * selected_policy.maximum_guided_candidates_per_mode
        )
        uniform_floor = int(
            math.ceil(
                budget.candidate_count
                * selected_policy.minimum_uniform_fraction
            )
        )
        guided_count = min(
            fraction_cap,
            mode_cap,
            budget.candidate_count - uniform_floor,
        )
        guided_count = max(1, guided_count)
        if budget.candidate_count >= 2:
            guided_count = min(budget.candidate_count - 1, guided_count)
    else:
        guided_count = 0
    from . import proposals as proposal_module

    proposals = list(baseline)
    proposal_modes = [UNIFORM_FALLBACK_MODE] * len(proposals)
    ligand_anchor_rows: list[tuple[int, ...]] = [()] * len(proposals)
    receptor_anchor_rows: list[tuple[int, ...]] = [()] * len(proposals)
    requested_anchor_distances: list[float | None] = [None] * len(proposals)
    observed_anchor_distances: list[float | None] = [None] * len(proposals)
    search_space = authenticated_problem.search_space
    pocket_center = authenticated_problem.pocket.center.to(
        dtype=search_space.local_offsets.dtype
    )
    for proposal_index in range(guided_count):
        mode = modes[proposal_index % len(modes)]
        base = baseline[proposal_index]
        conformer = torsion_tree_forward_kinematics(
            search_space.local_offsets,
            search_space.parent,
            base.torsion_angles,
            local_axes=search_space.local_axes,
            root_positions=search_space.root_positions,
        ).coordinates
        try:
            (
                coordinates,
                rotation,
                translation,
                ligand_anchor_indices,
                receptor_anchor_indices,
                requested_anchor_distance,
                observed_anchor_distance,
            ) = _guided_transform(
                mode=mode,
                context=context,
                policy=selected_policy,
                conformer=conformer,
                base_rotation=base.rotation,
                pocket_center=pocket_center,
                translation_radius_angstrom=budget.translation_radius_angstrom,
                seed=budget.seed,
                proposal_index=proposal_index,
            )
        except _GuidanceUnavailable:
            continue
        centroid_offset = float(
            torch.linalg.vector_norm(coordinates.mean(dim=0) - pocket_center).item()
        )
        if (
            centroid_offset
            > budget.translation_radius_angstrom + _CENTROID_TOLERANCE_ANGSTROM
        ):
            raise DockingAuthorityError("guided proposal exceeds the translation bound")
        coordinate_digest = coordinate_fingerprint(coordinates)
        fingerprint = proposal_module._proposal_fingerprint(
            proposal_index=proposal_index,
            seed=budget.seed,
            torsion_angles=base.torsion_angles,
            rotation=rotation,
            translation=translation,
            problem_fingerprint_sha256=authenticated_problem.problem.fingerprint_sha256,
            search_space_fingerprint_sha256=search_space.fingerprint_sha256,
            coordinate_fingerprint_sha256=coordinate_digest,
        )
        proposal = DockingProposal(
            candidate_id=_stable_candidate_id(
                proposal_index=proposal_index,
                seed=budget.seed,
                problem_fingerprint_sha256=authenticated_problem.problem.fingerprint_sha256,
                search_space_fingerprint_sha256=search_space.fingerprint_sha256,
            ),
            coordinates=coordinates,
            torsion_angles=base.torsion_angles,
            rotation=rotation,
            translation=translation,
            proposal_index=proposal_index,
            seed=budget.seed,
            fingerprint_sha256=fingerprint,
            problem_fingerprint_sha256=authenticated_problem.problem.fingerprint_sha256,
            search_space_fingerprint_sha256=search_space.fingerprint_sha256,
            coordinate_fingerprint_sha256=coordinate_digest,
        )
        proposal.assert_integrity()
        proposals[proposal_index] = proposal
        proposal_modes[proposal_index] = mode
        ligand_anchor_rows[proposal_index] = ligand_anchor_indices
        receptor_anchor_rows[proposal_index] = receptor_anchor_indices
        requested_anchor_distances[proposal_index] = requested_anchor_distance
        observed_anchor_distances[proposal_index] = observed_anchor_distance
    result = tuple(proposals)
    receipt = GuidedPlacementReceipt(
        authenticated_input_receipt_sha256=authenticated_problem.input_receipt_sha256,
        guidance_context_sha256=context.fingerprint_sha256,
        guided_policy_sha256=selected_policy.fingerprint_sha256,
        budget_sha256=_budget_sha256(budget),
        proposal_fingerprint_sha256s=tuple(row.fingerprint_sha256 for row in result),
        proposal_modes=tuple(proposal_modes),
        ligand_anchor_atom_indices=tuple(ligand_anchor_rows),
        receptor_anchor_atom_indices=tuple(receptor_anchor_rows),
        requested_anchor_distance_angstroms=tuple(requested_anchor_distances),
        observed_anchor_distance_angstroms=tuple(observed_anchor_distances),
        feature_counts=context.feature_counts(),
    )
    return result, receipt


@dataclass(frozen=True, slots=True)
class GuidedPlacementSearchResult:
    guided_receipt: GuidedPlacementReceipt
    authenticated_search_result: AuthenticatedDockingSearchResult
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.guided_receipt, GuidedPlacementReceipt):
            raise TypeError("guided_receipt must be GuidedPlacementReceipt")
        if not isinstance(
            self.authenticated_search_result, AuthenticatedDockingSearchResult
        ):
            raise TypeError(
                "authenticated_search_result must be AuthenticatedDockingSearchResult"
            )
        observed = tuple(
            row.proposal_fingerprint_sha256
            for row in self.authenticated_search_result.search_result.rows
        )
        if observed != self.guided_receipt.proposal_fingerprint_sha256s:
            raise DockingAuthorityError("guided search proposals are cross-wired")
        if (
            _budget_sha256(self.authenticated_search_result.search_result.budget)
            != self.guided_receipt.budget_sha256
        ):
            raise DockingAuthorityError("guided search budget is cross-wired")
        if (
            self.authenticated_search_result.authenticated_input_receipt_sha256
            != self.guided_receipt.authenticated_input_receipt_sha256
        ):
            raise DockingAuthorityError("guided search authority is cross-wired")
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": GUIDED_PLACEMENT_SEARCH_RESULT_SCHEMA_ID,
            "guided_receipt_sha256": self.guided_receipt.receipt_sha256,
            "authenticated_search_receipt_sha256": self.authenticated_search_result.receipt_sha256,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingAuthorityError("guided placement search result changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
            "guided_placement": self.guided_receipt.to_dict(),
            "search": self.authenticated_search_result.to_dict(),
        }


def run_authenticated_guided_placement_search(
    authenticated_problem: AuthenticatedDockingProblem,
    budget: DockingBudget,
    scorer,
    context: GuidedPlacementContext,
    *,
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    refiner=None,
    policy: GuidedPlacementPolicy | None = None,
    diversity_rmsd_angstrom: float = 0.5,
    diversity_metric: str = "direct_rmsd",
    symmetry_permutations: Sequence[Sequence[int] | torch.Tensor] | None = None,
) -> GuidedPlacementSearchResult:
    proposals, receipt = generate_guided_docking_proposals(
        authenticated_problem,
        budget,
        context,
        receptor_system=receptor_system,
        ligand_system=ligand_system,
        policy=policy,
    )
    override = _ProposalOverride(
        search_space_fingerprint_sha256=authenticated_problem.search_space.fingerprint_sha256,
        budget_sha256=_budget_sha256(budget),
        problem_fingerprint_sha256=authenticated_problem.problem.fingerprint_sha256,
        proposals=proposals,
    )
    token = _PROPOSAL_OVERRIDE.set(override)
    try:
        from . import authority as authority_module

        search = authority_module.run_authenticated_bounded_docking_search(
            authenticated_problem,
            budget,
            scorer,
            refiner=refiner,
            diversity_rmsd_angstrom=diversity_rmsd_angstrom,
            diversity_metric=diversity_metric,
            symmetry_permutations=symmetry_permutations,
        )
    finally:
        _PROPOSAL_OVERRIDE.reset(token)
    return GuidedPlacementSearchResult(
        guided_receipt=receipt,
        authenticated_search_result=search,
    )


__all__ = [
    "GUIDED_FEATURE_POLICY_ID",
    "GUIDED_MODES",
    "GUIDED_PLACEMENT_CONTEXT_SCHEMA_ID",
    "GUIDED_PLACEMENT_POLICY_ID",
    "GUIDED_PLACEMENT_POLICY_SCHEMA_ID",
    "GUIDED_PLACEMENT_RECEIPT_SCHEMA_ID",
    "GUIDED_PLACEMENT_SEARCH_RESULT_SCHEMA_ID",
    "MAX_GUIDED_AROMATIC_SYSTEMS",
    "MAX_GUIDED_FEATURE_ATOMS",
    "MAX_GUIDED_RECEPTOR_BONDS_SCANNED",
    "UNIFORM_FALLBACK_MODE",
    "GuidedPlacementContext",
    "GuidedPlacementPolicy",
    "GuidedPlacementReceipt",
    "GuidedPlacementSearchResult",
    "build_guided_placement_context",
    "generate_guided_docking_proposals",
    "run_authenticated_guided_placement_search",
]
