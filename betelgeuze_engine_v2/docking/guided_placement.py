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
    canonical_topology_sha256,
    require_valid_all_atom_system,
)

from .authority import (
    AuthenticatedDockingProblem,
    AuthenticatedDockingSearchResult,
    DockingAuthorityError,
)
from .conformers import (
    SOURCE_BOUND_CONFORMER_ENSEMBLE_SCHEMA_ID,
    ConformerPreparationError,
    SourceBoundPreparedConformerEnsemble,
)
from .identity import coordinate_fingerprint
from .placement import (
    _PROPOSAL_OVERRIDE,
    _ProposalOverride,
    _budget_sha256,
    _centered_candidate_count,
    _counter_uniform,
    _stable_candidate_id,
    PocketPlacementPolicy,
    generate_pocket_centered_docking_proposals,
)
from .proposals import DockingBudget, DockingProposal


GUIDED_PLACEMENT_CONTEXT_SCHEMA_ID = (
    "betelgeuze.engine_v2_guided_placement_context/1.0.0"
)
GUIDED_PLACEMENT_POLICY_SCHEMA_ID = "betelgeuze.engine_v2_guided_placement_policy/1.4.0"
GUIDED_PLACEMENT_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_guided_placement_receipt/1.3.0"
)
SOURCE_PAIRED_TORSION_RESCUE_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_torsion_rescue_policy/1.0.0"
)
SOURCE_PAIRED_TORSION_RESCUE_ALLOCATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_torsion_rescue_allocation/1.0.0"
)
SOURCE_PAIRED_TORSION_RESCUE_GUIDED_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_guided_placement_receipt/1.4.0"
)
SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_torsion_rescue_proposal_receipt/1.0.0"
)
GUIDED_PLACEMENT_SEARCH_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_guided_placement_search_result/1.0.0"
)
GUIDED_PLACEMENT_POLICY_ID = (
    "betelgeuze.engine_v2_interaction_guided_with_uniform_fallback/1.4.0"
)
SOURCE_PAIRED_TORSION_RESCUE_POLICY_ID = (
    "betelgeuze.engine_v2_historical_development_source_paired_torsion_rescue/1.0.0"
)
GUIDED_FEATURE_POLICY_ID = "betelgeuze.engine_v2_bounded_graph_guidance_features/1.0.0"
GUIDED_MODES = (
    "donor_acceptor_hotspot",
    "charge_anchor",
    "hydrophobic_patch",
    "aromatic_plane",
    "shape_complementarity",
)
MULTI_ANCHOR_MODE = "multi_anchor_hotspot"
POCKET_CENTER_BASELINE_MODE = "pocket_center_baseline"
UNIFORM_FALLBACK_MODE = "uniform_fallback"
UNIFORM_V3_ENSEMBLE_MODE = "uniform_v3_rigid_ensemble"
UNIFORM_TORSION_RESCUE_VARIANT_MODE = "uniform_torsion_rescue_variant"
MAX_UNIFORM_TORSION_RESCUE_VARIANTS = 4
SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT = 64
FIXED_SOURCE_BOUND_CONFORMER_PROFILE_SCHEMA_ID = (
    "betelgeuze.engine_v2_fixed_source_bound_conformer_profile/1.0.0"
)
FIXED_SOURCE_BOUND_CONFORMER_PROFILE_ID = "betelgeuze.engine_v2_historical_development_fixed64_source_paired_true_conformer/1.0.0"
FIXED_SOURCE_BOUND_CONFORMER_LINEAGE_SCHEMA_ID = (
    "betelgeuze.engine_v2_fixed_source_bound_conformer_lineage/1.0.0"
)
FIXED_SOURCE_BOUND_CONFORMER_TORSION_METADATA_SCHEMA_ID = (
    "betelgeuze.engine_v2_fixed_source_bound_conformer_torsion_metadata/1.0.0"
)
FIXED_SOURCE_BOUND_CONFORMER_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_fixed_source_bound_conformer_proposal_receipt/1.0.0"
)
FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT = 64
FIXED_SOURCE_BOUND_CONFORMER_CENTERED_COUNT = 8
FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT = 28
FIXED_SOURCE_BOUND_CONFORMER_VARIANT_START = 8
FIXED_SOURCE_BOUND_CONFORMER_SOURCE_START = 36
MAX_GUIDED_FEATURE_ATOMS = 2_048
MAX_GUIDED_AROMATIC_SYSTEMS = 128
MAX_GUIDED_RECEPTOR_BONDS_SCANNED = 1_000_000
MAX_MULTI_ANCHOR_MATCHES_PER_LANE = 64
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


def fixed_source_bound_conformer_profile_document() -> dict[str, object]:
    projection = {
        "schema_id": FIXED_SOURCE_BOUND_CONFORMER_PROFILE_SCHEMA_ID,
        "profile_id": FIXED_SOURCE_BOUND_CONFORMER_PROFILE_ID,
        "candidate_count": FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT,
        "centered_source_slots": [0, 8],
        "true_conformer_variant_slots": [8, 36],
        "retained_uniform_source_slots": [36, 64],
        "variant_count": FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT,
        "variant_source_pairing": "variant_8_plus_j_to_source_36_plus_j",
        "conformer_assignment": "energy_rank_j_mod_selected_conformer_count",
        "minimum_selected_conformer_count": 2,
        "maximum_selected_conformer_count": 8,
        "variant_rigid_frame": (
            "centered_conformer_times_paired_source_rotation_transpose_plus_paired_source_centroid"
        ),
        "retained_source_proposal_objects_bit_identical": True,
        "variant_coordinate_geometry_authoritative": True,
        "variant_torsion_metadata": (
            "source_relative_heavy_first_rotor_dihedral_delta_non_reconstructive"
        ),
        "public_proposal_mode": UNIFORM_V3_ENSEMBLE_MODE,
        "public_candidate_schema_changed": False,
        "development_only": True,
        "stage0_eligible": False,
        "fresh_execution_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return {
        **projection,
        "fingerprint_sha256": _sha256(projection),
    }


def fixed_source_bound_conformer_proposal_indices() -> tuple[int, ...]:
    return tuple(
        range(
            FIXED_SOURCE_BOUND_CONFORMER_VARIANT_START,
            FIXED_SOURCE_BOUND_CONFORMER_SOURCE_START,
        )
    )


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
    centered_candidate_count: int = 8
    maximum_guided_candidates_per_mode: int = 8
    donor_acceptor_distance_angstrom: float = 2.9
    charge_anchor_distance_angstrom: float = 3.5
    hydrophobic_distance_angstrom: float = 3.8
    aromatic_plane_distance_angstrom: float = 3.6
    multi_anchor_max_points: int = 3
    multi_anchor_min_separation_angstrom: float = 1.0
    multi_anchor_max_distance_mismatch_angstrom: float = 2.5
    uniform_v3_ensemble_enabled: bool = False
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
        if (
            type(self.centered_candidate_count) is not int
            or not 1 <= self.centered_candidate_count <= 64
        ):
            raise DockingAuthorityError(
                "centered_candidate_count must be in [1,64]"
            )
        if (
            type(self.multi_anchor_max_points) is not int
            or not 2 <= self.multi_anchor_max_points <= 3
        ):
            raise DockingAuthorityError("multi_anchor_max_points must be in [2,3]")
        if type(self.uniform_v3_ensemble_enabled) is not bool:
            raise DockingAuthorityError(
                "uniform_v3_ensemble_enabled must be boolean"
            )
        object.__setattr__(
            self, "minimum_uniform_fraction", minimum_uniform_fraction
        )
        for name in (
            "donor_acceptor_distance_angstrom",
            "charge_anchor_distance_angstrom",
            "hydrophobic_distance_angstrom",
            "aromatic_plane_distance_angstrom",
            "multi_anchor_min_separation_angstrom",
            "multi_anchor_max_distance_mismatch_angstrom",
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
            "allocation_strategy": (
                "centered_quota_within_guided_cap_and_uniform_floor"
            ),
            "minimum_uniform_fraction_binary64_hex": (
                self.minimum_uniform_fraction.hex()
            ),
            "centered_candidate_count": self.centered_candidate_count,
            "centered_candidate_policy": (
                "preserve_before_guided_replacement"
            ),
            "maximum_guided_candidates_per_mode": (
                self.maximum_guided_candidates_per_mode
            ),
            "donor_acceptor_distance_angstrom_binary64_hex": self.donor_acceptor_distance_angstrom.hex(),
            "charge_anchor_distance_angstrom_binary64_hex": self.charge_anchor_distance_angstrom.hex(),
            "hydrophobic_distance_angstrom_binary64_hex": self.hydrophobic_distance_angstrom.hex(),
            "aromatic_plane_distance_angstrom_binary64_hex": self.aromatic_plane_distance_angstrom.hex(),
            "multi_anchor_mode": MULTI_ANCHOR_MODE,
            "multi_anchor_max_points": self.multi_anchor_max_points,
            "multi_anchor_min_separation_angstrom_binary64_hex": (
                self.multi_anchor_min_separation_angstrom.hex()
            ),
            "multi_anchor_max_distance_mismatch_angstrom_binary64_hex": (
                self.multi_anchor_max_distance_mismatch_angstrom.hex()
            ),
            "multi_anchor_allocation": (
                "odd_repeated_donor_or_charge_cycles_capped_at_eight"
            ),
            "uniform_v3_ensemble_enabled": self.uniform_v3_ensemble_enabled,
            "uniform_v3_ensemble_mode": UNIFORM_V3_ENSEMBLE_MODE,
            "uniform_v3_ensemble_source_selection": (
                "rounded_even_spacing_across_retained_uniform_indices"
            ),
            "uniform_v3_ensemble_originals_retained": True,
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


@dataclass(frozen=True, slots=True)
class SourcePairedTorsionRescuePolicy:
    """Frozen development wrapper over the ordinary source-paired V3 batch."""

    maximum_variant_count: int = MAX_UNIFORM_TORSION_RESCUE_VARIANTS
    candidate_count: int = SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT
    policy_id: str = SOURCE_PAIRED_TORSION_RESCUE_POLICY_ID
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.policy_id != SOURCE_PAIRED_TORSION_RESCUE_POLICY_ID:
            raise DockingAuthorityError(
                "unsupported source-paired torsion-rescue policy"
            )
        if self.maximum_variant_count != MAX_UNIFORM_TORSION_RESCUE_VARIANTS:
            raise DockingAuthorityError(
                "source-paired torsion rescue requires the fixed cap of four"
            )
        if self.candidate_count != SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT:
            raise DockingAuthorityError(
                "source-paired torsion rescue requires exactly 64 candidates"
            )
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    @property
    def base_guided_policy(self) -> GuidedPlacementPolicy:
        return GuidedPlacementPolicy(uniform_v3_ensemble_enabled=True)

    def _projection(self) -> dict[str, object]:
        base_policy = self.base_guided_policy
        return {
            "schema_id": SOURCE_PAIRED_TORSION_RESCUE_POLICY_SCHEMA_ID,
            "policy_id": self.policy_id,
            "base_guided_policy_sha256": base_policy.fingerprint_sha256,
            "candidate_count": self.candidate_count,
            "maximum_variant_count": self.maximum_variant_count,
            "source_pair_authority": "base_uniform_v3_ensemble_receipt",
            "variant_target_selection": (
                "rounded_even_spacing_across_ordered_v3_target_indices"
            ),
            "authority_rotor_required": True,
            "proposal_objects_and_coordinates_unchanged": True,
            "selected_parent_proposal_objects_retained": True,
            "ordinary_v3_and_rescue_target_parent_unions_disjoint": True,
            "candidate_denominator_changed": False,
            "rmsd_posebusters_native_rank_or_score_used_for_allocation": False,
            "development_only": True,
            "stage0_eligible": False,
            "fresh_execution_authorized": False,
            "product_promotion_eligible": False,
            "public_claim_eligible": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise DockingAuthorityError("source-paired torsion-rescue policy changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


@dataclass(frozen=True, slots=True)
class SourcePairedTorsionRescueAllocation:
    """Authenticated ordered V3 and rescue child-to-parent allocation."""

    authenticated_input_receipt_sha256: str
    guidance_context_sha256: str
    budget_sha256: str
    rescue_policy_sha256: str
    base_guided_policy_sha256: str
    candidate_count: int
    authority_rotor_count: int
    v3_target_parent_pairs: tuple[tuple[int, int], ...]
    rescue_target_parent_pairs: tuple[tuple[int, int], ...]
    _allocation_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "authenticated_input_receipt_sha256",
            "guidance_context_sha256",
            "budget_sha256",
            "rescue_policy_sha256",
            "base_guided_policy_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if self.candidate_count != SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT:
            raise DockingAuthorityError(
                "source-paired torsion-rescue allocation requires 64 candidates"
            )
        if (
            type(self.authority_rotor_count) is not int
            or self.authority_rotor_count < 0
        ):
            raise DockingAuthorityError(
                "source-paired torsion-rescue rotor count is invalid"
            )

        def normalize_pairs(
            values: Sequence[Sequence[int]], *, name: str
        ) -> tuple[tuple[int, int], ...]:
            rows: list[tuple[int, int]] = []
            for value in values:
                if (
                    not isinstance(value, (tuple, list))
                    or len(value) != 2
                    or any(type(index) is not int for index in value)
                ):
                    raise DockingAuthorityError(f"{name} rows are invalid")
                target, parent = int(value[0]), int(value[1])
                if (
                    not 0 <= target < self.candidate_count
                    or not 0 <= parent < self.candidate_count
                    or target == parent
                ):
                    raise DockingAuthorityError(f"{name} indices are invalid")
                rows.append((target, parent))
            normalized = tuple(rows)
            if tuple(sorted(normalized)) != normalized:
                raise DockingAuthorityError(f"{name} rows must be target-sorted")
            return normalized

        v3_pairs = normalize_pairs(
            self.v3_target_parent_pairs,
            name="ordinary V3 target-parent",
        )
        rescue_pairs = normalize_pairs(
            self.rescue_target_parent_pairs,
            name="torsion-rescue target-parent",
        )
        if len(rescue_pairs) > MAX_UNIFORM_TORSION_RESCUE_VARIANTS:
            raise DockingAuthorityError(
                "source-paired torsion-rescue allocation exceeds its hard cap"
            )
        if rescue_pairs and self.authority_rotor_count == 0:
            raise DockingAuthorityError(
                "torsion-rescue variants require an authority-proven rotor"
            )
        ordered_all_pairs = tuple(sorted((*v3_pairs, *rescue_pairs)))
        expected_rescue_count = (
            min(MAX_UNIFORM_TORSION_RESCUE_VARIANTS, len(ordered_all_pairs))
            if self.authority_rotor_count
            else 0
        )
        expected_rescue_targets = frozenset(
            _evenly_spaced_uniform_sources(
                tuple(target for target, _ in ordered_all_pairs),
                expected_rescue_count,
            )
        )
        expected_rescue_pairs = tuple(
            pair for pair in ordered_all_pairs if pair[0] in expected_rescue_targets
        )
        expected_v3_pairs = tuple(
            pair for pair in ordered_all_pairs if pair[0] not in expected_rescue_targets
        )
        if rescue_pairs != expected_rescue_pairs or v3_pairs != expected_v3_pairs:
            raise DockingAuthorityError(
                "source-paired torsion-rescue allocation is not the fixed even split"
            )
        all_pairs = (*v3_pairs, *rescue_pairs)
        targets = tuple(row[0] for row in all_pairs)
        parents = tuple(row[1] for row in all_pairs)
        v3_union = {index for row in v3_pairs for index in row}
        rescue_union = {index for row in rescue_pairs for index in row}
        if (
            len(targets) != len(set(targets))
            or len(parents) != len(set(parents))
            or set(targets) & set(parents)
            or v3_union & rescue_union
        ):
            raise DockingAuthorityError(
                "source-paired torsion-rescue lanes overlap or reuse parents"
            )
        object.__setattr__(self, "v3_target_parent_pairs", v3_pairs)
        object.__setattr__(self, "rescue_target_parent_pairs", rescue_pairs)
        object.__setattr__(self, "_allocation_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": SOURCE_PAIRED_TORSION_RESCUE_ALLOCATION_SCHEMA_ID,
            "authenticated_input_receipt_sha256": (
                self.authenticated_input_receipt_sha256
            ),
            "guidance_context_sha256": self.guidance_context_sha256,
            "budget_sha256": self.budget_sha256,
            "rescue_policy_sha256": self.rescue_policy_sha256,
            "base_guided_policy_sha256": self.base_guided_policy_sha256,
            "candidate_count": self.candidate_count,
            "authority_rotor_count": self.authority_rotor_count,
            "v3_target_parent_pairs": [
                {"target_proposal_index": target, "parent_proposal_index": parent}
                for target, parent in self.v3_target_parent_pairs
            ],
            "rescue_target_parent_pairs": [
                {"target_proposal_index": target, "parent_proposal_index": parent}
                for target, parent in self.rescue_target_parent_pairs
            ],
            "rescue_variant_count": len(self.rescue_target_parent_pairs),
            "rescue_variant_cap": MAX_UNIFORM_TORSION_RESCUE_VARIANTS,
            "selected_parent_proposal_objects_retained": True,
            "candidate_denominator_changed": False,
            "result_dependent_allocation": False,
            "development_only": True,
            "stage0_eligible": False,
            "fresh_execution_authorized": False,
            "claim_safe": False,
        }

    @property
    def allocation_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._allocation_sha256:
            raise DockingAuthorityError(
                "source-paired torsion-rescue allocation changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "allocation_sha256": self.allocation_sha256}

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


def _multi_anchor_available(context: GuidedPlacementContext) -> bool:
    ligand = context.ligand_features
    receptor = context.receptor_feature_rows
    ligand_indices: set[int] = set()
    receptor_indices: set[int] = set()
    for ligand_kind, receptor_kind in (
        ("donor", "acceptor"),
        ("acceptor", "donor"),
        ("positive", "negative"),
        ("negative", "positive"),
        ("hydrophobic", "hydrophobic"),
    ):
        if ligand[ligand_kind] and receptor[receptor_kind]:
            ligand_indices.update(ligand[ligand_kind])
            receptor_indices.update(row[0] for row in receptor[receptor_kind])
    return len(ligand_indices) >= 2 and len(receptor_indices) >= 2


def _guided_allocation(
    context: GuidedPlacementContext,
    budget: DockingBudget,
    policy: GuidedPlacementPolicy,
) -> tuple[int, int, tuple[str, ...]]:
    centered_count = _centered_candidate_count(
        budget.candidate_count,
        policy.centered_candidate_count,
    )
    modes = _available_modes(context)
    if not modes:
        return centered_count, 0, modes
    fraction_cap = int(math.floor(budget.candidate_count * policy.guided_fraction))
    mode_cap = len(modes) * policy.maximum_guided_candidates_per_mode
    uniform_floor = int(
        math.ceil(budget.candidate_count * policy.minimum_uniform_fraction)
    )
    structured_count = min(
        fraction_cap,
        mode_cap,
        max(0, budget.candidate_count - uniform_floor),
    )
    guided_count = max(0, structured_count - centered_count)
    if policy.uniform_v3_ensemble_enabled:
        # Each V3 variant retains one distinct uniform V2 source in the same
        # denominator.  This cap proves that source selection cannot consume
        # or duplicate the source lane.
        guided_count = min(
            guided_count,
            max(0, (budget.candidate_count - centered_count) // 2),
        )
    return centered_count, guided_count, modes


def uniform_v3_ensemble_proposal_indices(
    context: GuidedPlacementContext,
    budget: DockingBudget,
    policy: GuidedPlacementPolicy,
) -> tuple[int, ...]:
    """Return the receipt-bound proposal indices assigned to the V3 lane."""

    if not isinstance(context, GuidedPlacementContext):
        raise TypeError("context must be GuidedPlacementContext")
    if not isinstance(budget, DockingBudget):
        raise TypeError("budget must be DockingBudget")
    if not isinstance(policy, GuidedPlacementPolicy):
        raise TypeError("policy must be GuidedPlacementPolicy")
    policy.fingerprint_sha256
    if not policy.uniform_v3_ensemble_enabled:
        return ()
    centered_count, guided_count, _ = _guided_allocation(context, budget, policy)
    return tuple(range(centered_count, centered_count + guided_count))


def _evenly_spaced_uniform_sources(
    source_indices: Sequence[int],
    target_count: int,
) -> tuple[int, ...]:
    sources = tuple(int(value) for value in source_indices)
    if target_count == 0:
        return ()
    if target_count < 0 or len(sources) < target_count:
        raise DockingAuthorityError(
            "uniform V3 ensemble lacks distinct retained source proposals"
        )
    if target_count == 1:
        return (sources[0],)
    positions = tuple(
        round(index * (len(sources) - 1) / (target_count - 1))
        for index in range(target_count)
    )
    selected = tuple(sources[position] for position in positions)
    if len(set(selected)) != len(selected):
        raise DockingAuthorityError(
            "uniform V3 ensemble source spacing is not one-to-one"
        )
    return selected


def source_paired_torsion_rescue_allocation(
    authenticated_problem: AuthenticatedDockingProblem,
    context: GuidedPlacementContext,
    budget: DockingBudget,
    policy: SourcePairedTorsionRescuePolicy,
) -> SourcePairedTorsionRescueAllocation:
    """Split the ordinary V3 pairs into disjoint V3 and rescue lanes."""

    if not isinstance(authenticated_problem, AuthenticatedDockingProblem):
        raise TypeError("authenticated_problem must be AuthenticatedDockingProblem")
    if not isinstance(context, GuidedPlacementContext):
        raise TypeError("context must be GuidedPlacementContext")
    if not isinstance(budget, DockingBudget):
        raise TypeError("budget must be DockingBudget")
    if not isinstance(policy, SourcePairedTorsionRescuePolicy):
        raise TypeError("policy must be SourcePairedTorsionRescuePolicy")
    authenticated_problem.input_receipt_sha256
    context.fingerprint_sha256
    policy.fingerprint_sha256
    if (
        context.authority_input_receipt_sha256
        != authenticated_problem.input_receipt_sha256
    ):
        raise DockingAuthorityError("torsion-rescue allocation context is cross-wired")
    if budget.candidate_count != policy.candidate_count:
        raise DockingAuthorityError(
            "torsion-rescue allocation candidate denominator is invalid"
        )
    base_policy = policy.base_guided_policy
    centered_count, guided_count, _ = _guided_allocation(
        context,
        budget,
        base_policy,
    )
    target_indices = tuple(range(centered_count, centered_count + guided_count))
    source_indices = tuple(range(centered_count + guided_count, budget.candidate_count))
    selected_sources = _evenly_spaced_uniform_sources(
        source_indices,
        guided_count,
    )
    all_pairs = tuple(zip(target_indices, selected_sources, strict=True))
    rotor_count = int(
        torch.count_nonzero(authenticated_problem.search_space.rotatable_mask).item()
    )
    rescue_count = (
        min(policy.maximum_variant_count, len(target_indices)) if rotor_count else 0
    )
    rescue_targets = frozenset(
        _evenly_spaced_uniform_sources(target_indices, rescue_count)
    )
    rescue_pairs = tuple(pair for pair in all_pairs if pair[0] in rescue_targets)
    v3_pairs = tuple(pair for pair in all_pairs if pair[0] not in rescue_targets)
    return SourcePairedTorsionRescueAllocation(
        authenticated_input_receipt_sha256=(authenticated_problem.input_receipt_sha256),
        guidance_context_sha256=context.fingerprint_sha256,
        budget_sha256=_budget_sha256(budget),
        rescue_policy_sha256=policy.fingerprint_sha256,
        base_guided_policy_sha256=base_policy.fingerprint_sha256,
        candidate_count=budget.candidate_count,
        authority_rotor_count=rotor_count,
        v3_target_parent_pairs=v3_pairs,
        rescue_target_parent_pairs=rescue_pairs,
    )

def _rotor_dihedral_angle(
    coordinates: torch.Tensor,
    atoms: tuple[int, int, int, int],
) -> float:
    first, second, third, fourth = (coordinates[index] for index in atoms)
    middle = third - second
    middle_norm = float(torch.linalg.vector_norm(middle).item())
    if middle_norm <= 1.0e-12:
        raise DockingAuthorityError(
            "true-conformer rotor geometry contains a degenerate central bond"
        )
    axis = middle / middle_norm
    left = first - second
    right = fourth - third
    left = left - torch.dot(left, axis) * axis
    right = right - torch.dot(right, axis) * axis
    left_norm = float(torch.linalg.vector_norm(left).item())
    right_norm = float(torch.linalg.vector_norm(right).item())
    if min(left_norm, right_norm) <= 1.0e-12:
        raise DockingAuthorityError(
            "true-conformer rotor geometry lacks a stable dihedral anchor"
        )
    left = left / left_norm
    right = right / right_norm
    sine = float(torch.dot(torch.cross(left, right, dim=0), axis).item())
    cosine = float(torch.dot(left, right).item())
    return math.atan2(sine, cosine)


def _source_relative_rotor_torsion_metadata(
    authenticated_problem: AuthenticatedDockingProblem,
    source_system: AllAtomSystem,
    conformer_coordinates: torch.Tensor,
) -> torch.Tensor:
    if not isinstance(authenticated_problem, AuthenticatedDockingProblem):
        raise TypeError("authenticated_problem must be AuthenticatedDockingProblem")
    if not isinstance(source_system, AllAtomSystem):
        raise TypeError("source_system must be AllAtomSystem")
    require_valid_all_atom_system(source_system)
    if source_system.model_count != 1:
        raise DockingAuthorityError(
            "true-conformer torsion metadata requires one source model"
        )
    if (
        not isinstance(conformer_coordinates, torch.Tensor)
        or conformer_coordinates.device.type != "cpu"
        or not conformer_coordinates.is_floating_point()
        or conformer_coordinates.shape != (source_system.atom_count, 3)
        or not bool(torch.isfinite(conformer_coordinates).all().item())
    ):
        raise DockingAuthorityError(
            "true-conformer coordinates must be finite CPU [N,3] floating data"
        )
    source_coordinates = source_system.coordinates[0].to(
        dtype=conformer_coordinates.dtype,
        device="cpu",
    )
    search_space = authenticated_problem.search_space
    if int(search_space.local_offsets.shape[0]) != source_system.atom_count:
        raise DockingAuthorityError(
            "true-conformer source and torsion search space are cross-wired"
        )
    adjacency = _adjacency(source_system)

    def anchor(index: int, excluded: int) -> int:
        candidates = [neighbor for neighbor in adjacency[index] if neighbor != excluded]
        if not candidates:
            raise DockingAuthorityError(
                "true-conformer rotatable bond lacks a dihedral anchor"
            )
        return min(
            candidates,
            key=lambda value: (
                source_system.atoms[value].element == "H",
                value,
            ),
        )

    result = torch.zeros(
        source_system.atom_count,
        dtype=conformer_coordinates.dtype,
        device="cpu",
    )
    for child_value in (
        torch.nonzero(search_space.rotatable_mask, as_tuple=False).reshape(-1).tolist()
    ):
        child = int(child_value)
        parent = int(search_space.parent[child].item())
        if not 0 <= parent < source_system.atom_count:
            raise DockingAuthorityError(
                "true-conformer rotatable bond parent is invalid"
            )
        atoms = (
            anchor(parent, child),
            parent,
            child,
            anchor(child, parent),
        )
        reference_angle = _rotor_dihedral_angle(source_coordinates, atoms)
        conformer_angle = _rotor_dihedral_angle(conformer_coordinates, atoms)
        result[child] = math.atan2(
            math.sin(conformer_angle - reference_angle),
            math.cos(conformer_angle - reference_angle),
        )
    return result.contiguous()


def _torsion_metadata_sha256(torsion_angles: torch.Tensor) -> str:
    if (
        not isinstance(torsion_angles, torch.Tensor)
        or torsion_angles.device.type != "cpu"
        or not torsion_angles.is_floating_point()
        or torsion_angles.ndim != 1
        or not bool(torch.isfinite(torsion_angles).all().item())
    ):
        raise DockingAuthorityError(
            "true-conformer torsion metadata must be a finite CPU vector"
        )
    return _sha256(
        {
            "schema_id": FIXED_SOURCE_BOUND_CONFORMER_TORSION_METADATA_SCHEMA_ID,
            "shape": [int(torsion_angles.shape[0])],
            "values_binary64_hex": [
                float(value).hex()
                for value in torsion_angles.detach()
                .to(dtype=torch.float64, device="cpu")
                .tolist()
            ],
            "semantics": (
                "source_relative_heavy_first_rotor_dihedral_delta_non_reconstructive"
            ),
        }
    )


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


@dataclass(frozen=True, slots=True)
class _MultiAnchorMatch:
    ligand_index: int
    receptor_index: int
    receptor_coordinate: torch.Tensor
    target_coordinate: torch.Tensor
    requested_distance_angstrom: float
    lane_index: int


def _bounded_flat_indices(
    length: int,
    *,
    seed: int,
    proposal_index: int,
    domain: str,
) -> tuple[int, ...]:
    if length <= MAX_MULTI_ANCHOR_MATCHES_PER_LANE:
        return tuple(range(length))
    selected: set[int] = set()
    target = MAX_MULTI_ANCHOR_MATCHES_PER_LANE
    for counter in range(target * 4):
        value = _counter_uniform(
            seed=seed,
            proposal_index=proposal_index,
            domain=domain,
            counter=counter,
        )
        selected.add(min(length - 1, int(value * length)))
        if len(selected) == target:
            break
    if len(selected) < target:
        for index in range(length):
            selected.add(index)
            if len(selected) == target:
                break
    return tuple(sorted(selected))


def _multi_anchor_matches(
    *,
    context: GuidedPlacementContext,
    policy: GuidedPlacementPolicy,
    pocket_center: torch.Tensor,
    seed: int,
    proposal_index: int,
) -> tuple[_MultiAnchorMatch, ...]:
    ligand = context.ligand_features
    receptor = context.receptor_feature_rows
    lanes = (
        ("donor", "acceptor", policy.donor_acceptor_distance_angstrom),
        ("acceptor", "donor", policy.donor_acceptor_distance_angstrom),
        ("positive", "negative", policy.charge_anchor_distance_angstrom),
        ("negative", "positive", policy.charge_anchor_distance_angstrom),
        ("hydrophobic", "hydrophobic", policy.hydrophobic_distance_angstrom),
    )
    matches: list[_MultiAnchorMatch] = []
    retained: set[tuple[int, int, float]] = set()
    for lane_index, (ligand_kind, receptor_kind, distance) in enumerate(lanes):
        ligand_rows = ligand[ligand_kind]
        receptor_rows = receptor[receptor_kind]
        if not ligand_rows or not receptor_rows:
            continue
        flat_count = len(ligand_rows) * len(receptor_rows)
        for flat_index in _bounded_flat_indices(
            flat_count,
            seed=seed,
            proposal_index=proposal_index,
            domain=f"multi-anchor-lane-{lane_index}",
        ):
            ligand_index = ligand_rows[flat_index // len(receptor_rows)]
            receptor_row = receptor_rows[flat_index % len(receptor_rows)]
            identity = (ligand_index, receptor_row[0], float(distance))
            if identity in retained:
                continue
            retained.add(identity)
            receptor_coordinate = torch.tensor(
                receptor_row[1],
                dtype=pocket_center.dtype,
            )
            direction = _unit_toward_pocket(
                receptor_coordinate,
                pocket_center,
                seed=seed,
                proposal_index=proposal_index,
            )
            matches.append(
                _MultiAnchorMatch(
                    ligand_index=ligand_index,
                    receptor_index=receptor_row[0],
                    receptor_coordinate=receptor_coordinate,
                    target_coordinate=(receptor_coordinate + distance * direction),
                    requested_distance_angstrom=float(distance),
                    lane_index=lane_index,
                )
            )
    return tuple(matches)


def _multi_anchor_rotation(
    source: torch.Tensor,
    target: torch.Tensor,
    base_rotation: torch.Tensor,
) -> torch.Tensor:
    if len(source) >= 3:
        source_centered = source - source.mean(dim=0)
        target_centered = target - target.mean(dim=0)
        covariance = source_centered.T @ target_centered
        u, singular_values, vh = torch.linalg.svd(covariance)
        if float(singular_values[1].item()) > 1.0e-10:
            rotation = vh.T @ u.T
            if float(torch.linalg.det(rotation).item()) < 0.0:
                vh = vh.clone()
                vh[-1] = -vh[-1]
                rotation = vh.T @ u.T
            return rotation
    base_source = source @ base_rotation.T
    source_vector = base_source[1] - base_source[0]
    target_vector = target[1] - target[0]
    if (
        float(torch.linalg.vector_norm(source_vector).item()) <= 1.0e-10
        or float(torch.linalg.vector_norm(target_vector).item()) <= 1.0e-10
    ):
        raise _GuidanceUnavailable("multi-anchor pair is geometrically degenerate")
    return _rotation_between(source_vector, target_vector) @ base_rotation


def _multi_anchor_transform(
    *,
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
    matches = _multi_anchor_matches(
        context=context,
        policy=policy,
        pocket_center=pocket_center,
        seed=seed,
        proposal_index=proposal_index,
    )
    if len(matches) < 2:
        raise _GuidanceUnavailable("multi-anchor chemistry is unavailable")
    pair_candidates: list[
        tuple[
            tuple[float, int, int, int, int, int],
            _MultiAnchorMatch,
            _MultiAnchorMatch,
        ]
    ] = []
    for first_index, first in enumerate(matches):
        for second in matches[first_index + 1 :]:
            if (
                first.ligand_index == second.ligand_index
                or first.receptor_index == second.receptor_index
            ):
                continue
            source_distance = float(
                torch.linalg.vector_norm(
                    conformer[first.ligand_index]
                    - conformer[second.ligand_index]
                ).item()
            )
            target_distance = float(
                torch.linalg.vector_norm(
                    first.target_coordinate - second.target_coordinate
                ).item()
            )
            if (
                source_distance < policy.multi_anchor_min_separation_angstrom
                or target_distance < policy.multi_anchor_min_separation_angstrom
            ):
                continue
            mismatch = abs(source_distance - target_distance)
            if mismatch > policy.multi_anchor_max_distance_mismatch_angstrom:
                continue
            pair_candidates.append(
                (
                    (
                        mismatch,
                        int(first.lane_index == second.lane_index),
                        min(first.ligand_index, second.ligand_index),
                        max(first.ligand_index, second.ligand_index),
                        min(first.receptor_index, second.receptor_index),
                        max(first.receptor_index, second.receptor_index),
                    ),
                    first,
                    second,
                )
            )
    if not pair_candidates:
        raise _GuidanceUnavailable("multi-anchor geometry is incompatible")
    pair_candidates.sort(key=lambda item: item[0])
    pair_choice_count = min(8, len(pair_candidates))
    pair_choice = pair_candidates[
        _pick_index(
            pair_choice_count,
            seed=seed,
            proposal_index=proposal_index,
            domain="multi-anchor-primary-pair",
        )
    ]
    selected = [pair_choice[1], pair_choice[2]]
    while len(selected) < policy.multi_anchor_max_points:
        candidates: list[tuple[float, int, int, int, _MultiAnchorMatch]] = []
        selected_ligand = {row.ligand_index for row in selected}
        selected_receptor = {row.receptor_index for row in selected}
        selected_lanes = {row.lane_index for row in selected}
        for row in matches:
            if (
                row.ligand_index in selected_ligand
                or row.receptor_index in selected_receptor
            ):
                continue
            mismatches: list[float] = []
            compatible = True
            for retained in selected:
                source_distance = float(
                    torch.linalg.vector_norm(
                        conformer[row.ligand_index]
                        - conformer[retained.ligand_index]
                    ).item()
                )
                target_distance = float(
                    torch.linalg.vector_norm(
                        row.target_coordinate - retained.target_coordinate
                    ).item()
                )
                if (
                    source_distance < policy.multi_anchor_min_separation_angstrom
                    or target_distance < policy.multi_anchor_min_separation_angstrom
                ):
                    compatible = False
                    break
                mismatches.append(abs(source_distance - target_distance))
            if not compatible:
                continue
            mismatch = max(mismatches)
            if mismatch > policy.multi_anchor_max_distance_mismatch_angstrom:
                continue
            candidates.append(
                (
                    mismatch,
                    int(row.lane_index in selected_lanes),
                    row.ligand_index,
                    row.receptor_index,
                    row,
                )
            )
        if not candidates:
            break
        candidates.sort(key=lambda item: item[:4])
        choice_count = min(4, len(candidates))
        selected.append(
            candidates[
                _pick_index(
                    choice_count,
                    seed=seed,
                    proposal_index=proposal_index,
                    domain=f"multi-anchor-choice-{len(selected)}",
                )
            ][4]
        )
    if len(selected) < 2:
        raise _GuidanceUnavailable("multi-anchor geometry is incompatible")

    # Keep the two index vectors positionally aligned.  The ligand index is the
    # stable ordering key; the receptor row deliberately remains in matching
    # order instead of being sorted independently.
    selected.sort(
        key=lambda row: (row.ligand_index, row.receptor_index, row.lane_index)
    )
    ligand_indices = tuple(row.ligand_index for row in selected)
    source = conformer[list(ligand_indices)]
    target = torch.stack(tuple(row.target_coordinate for row in selected))
    rotation = _multi_anchor_rotation(source, target, base_rotation)
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
        raise DockingAuthorityError("multi-anchor rotation is not proper")
    rotated = conformer @ rotation.T
    translation = target.mean(dim=0) - rotated[list(ligand_indices)].mean(dim=0)
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
    observed_distances = tuple(
        float(
            torch.linalg.vector_norm(
                coordinates[row.ligand_index] - row.receptor_coordinate
            ).item()
        )
        for row in selected
    )
    return (
        coordinates.contiguous(),
        rotation.contiguous(),
        translation.contiguous(),
        ligand_indices,
        tuple(row.receptor_index for row in selected),
        sum(row.requested_distance_angstrom for row in selected) / len(selected),
        sum(observed_distances) / len(observed_distances),
    )


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
    if mode == MULTI_ANCHOR_MODE:
        return _multi_anchor_transform(
            context=context,
            policy=policy,
            conformer=conformer,
            base_rotation=base_rotation,
            pocket_center=pocket_center,
            translation_radius_angstrom=translation_radius_angstrom,
            seed=seed,
            proposal_index=proposal_index,
        )
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
    ensemble_source_proposal_indices: tuple[int | None, ...] = ()
    torsion_rescue_parent_proposal_indices: tuple[int | None, ...] = ()
    source_paired_torsion_rescue_profile: bool = False
    baseline_guided_receipt_sha256: str = ""
    torsion_rescue_allocation_sha256: str = ""
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
        allowed = set(GUIDED_MODES) | {
            MULTI_ANCHOR_MODE,
            POCKET_CENTER_BASELINE_MODE,
            UNIFORM_FALLBACK_MODE,
            UNIFORM_V3_ENSEMBLE_MODE,
            UNIFORM_TORSION_RESCUE_VARIANT_MODE,
        }
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
        ensemble_sources = (
            tuple(None for _ in range(row_count))
            if not self.ensemble_source_proposal_indices
            else tuple(self.ensemble_source_proposal_indices)
        )
        rescue_parents = (
            tuple(None for _ in range(row_count))
            if not self.torsion_rescue_parent_proposal_indices
            else tuple(self.torsion_rescue_parent_proposal_indices)
        )
        if any(
            value is not None and type(value) is not int
            for value in ensemble_sources
        ):
            raise DockingAuthorityError(
                "uniform V3 ensemble source indices must be exact integers"
            )
        if any(
            value is not None and type(value) is not int
            for value in rescue_parents
        ):
            raise DockingAuthorityError(
                "torsion-rescue parent indices must be exact integers"
            )
        if any(
            len(rows) != row_count
            for rows in (
                ligand_anchors,
                receptor_anchors,
                requested_distances,
                observed_distances,
                ensemble_sources,
                rescue_parents,
            )
        ):
            raise DockingAuthorityError("guided anchor rows are incomplete")
        for index, (
            mode,
            ligand_row,
            receptor_row,
            requested,
            observed,
            ensemble_source,
            rescue_parent,
        ) in enumerate(
            zip(
                modes,
                ligand_anchors,
                receptor_anchors,
                requested_distances,
                observed_distances,
                ensemble_sources,
                rescue_parents,
                strict=True,
            )
        ):
            if any(index < 0 for index in (*ligand_row, *receptor_row)):
                raise DockingAuthorityError("guided anchor atom indices are invalid")
            if mode == MULTI_ANCHOR_MODE:
                if (
                    not 2 <= len(ligand_row) <= 3
                    or len(ligand_row) != len(receptor_row)
                    or ligand_row != tuple(sorted(set(ligand_row)))
                    or len(set(receptor_row)) != len(receptor_row)
                ):
                    raise DockingAuthorityError(
                        "multi-anchor atom pairs are invalid"
                    )
            elif (
                ligand_row != tuple(sorted(set(ligand_row)))
                or receptor_row != tuple(sorted(set(receptor_row)))
            ):
                raise DockingAuthorityError("guided anchor atom indices are invalid")
            if mode in {
                POCKET_CENTER_BASELINE_MODE,
                UNIFORM_FALLBACK_MODE,
                UNIFORM_V3_ENSEMBLE_MODE,
                UNIFORM_TORSION_RESCUE_VARIANT_MODE,
            }:
                if (
                    ligand_row
                    or receptor_row
                    or requested is not None
                    or observed is not None
                ):
                    raise DockingAuthorityError(
                        "baseline placement cannot declare guided anchors"
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
            if mode == UNIFORM_V3_ENSEMBLE_MODE:
                if (
                    ensemble_source is None
                    or not 0 <= ensemble_source < row_count
                    or ensemble_source == index
                    or modes[ensemble_source] != UNIFORM_FALLBACK_MODE
                    or rescue_parent is not None
                ):
                    raise DockingAuthorityError(
                        "uniform V3 ensemble source index is invalid"
                    )
            elif ensemble_source is not None:
                raise DockingAuthorityError(
                    "non-ensemble proposal cannot declare an ensemble source"
                )
            if mode == UNIFORM_TORSION_RESCUE_VARIANT_MODE:
                if (
                    rescue_parent is None
                    or not 0 <= rescue_parent < row_count
                    or rescue_parent == index
                    or modes[rescue_parent] != UNIFORM_FALLBACK_MODE
                    or ensemble_source is not None
                ):
                    raise DockingAuthorityError(
                        "torsion-rescue parent proposal index is invalid"
                    )
            elif rescue_parent is not None:
                raise DockingAuthorityError(
                    "non-rescue proposal cannot declare a torsion-rescue parent"
                )
        retained_sources = tuple(
            value for value in ensemble_sources if value is not None
        )
        if len(retained_sources) != len(set(retained_sources)):
            raise DockingAuthorityError(
                "uniform V3 ensemble sources must be one-to-one"
            )
        retained_rescue_parents = tuple(
            value for value in rescue_parents if value is not None
        )
        v3_targets = frozenset(
            index
            for index, mode in enumerate(modes)
            if mode == UNIFORM_V3_ENSEMBLE_MODE
        )
        rescue_targets = frozenset(
            index
            for index, mode in enumerate(modes)
            if mode == UNIFORM_TORSION_RESCUE_VARIANT_MODE
        )
        if (
            len(retained_rescue_parents) != len(set(retained_rescue_parents))
            or (v3_targets | set(retained_sources))
            & (rescue_targets | set(retained_rescue_parents))
        ):
            raise DockingAuthorityError(
                "guided source-paired proposal lanes overlap or reuse parents"
            )
        rescue_profile = self.source_paired_torsion_rescue_profile
        if type(rescue_profile) is not bool:
            raise DockingAuthorityError(
                "source-paired torsion-rescue profile flag must be boolean"
            )
        baseline_receipt_sha256 = str(
            self.baseline_guided_receipt_sha256 or ""
        ).strip().lower()
        allocation_sha256 = str(
            self.torsion_rescue_allocation_sha256 or ""
        ).strip().lower()
        if rescue_profile:
            if (
                row_count != SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT
                or len(rescue_targets) > MAX_UNIFORM_TORSION_RESCUE_VARIANTS
            ):
                raise DockingAuthorityError(
                    "source-paired torsion-rescue receipt violates its hard bounds"
                )
            baseline_receipt_sha256 = _digest(
                baseline_receipt_sha256,
                name="baseline_guided_receipt_sha256",
            )
            allocation_sha256 = _digest(
                allocation_sha256,
                name="torsion_rescue_allocation_sha256",
            )
        elif (
            rescue_targets
            or retained_rescue_parents
            or baseline_receipt_sha256
            or allocation_sha256
        ):
            raise DockingAuthorityError(
                "torsion-rescue lineage requires the development profile"
            )
        counts = {str(name): int(value) for name, value in self.feature_counts.items()}
        if any(value < 0 for value in counts.values()):
            raise DockingAuthorityError("guided feature counts are invalid")
        object.__setattr__(self, "proposal_fingerprint_sha256s", fingerprints)
        object.__setattr__(self, "proposal_modes", modes)
        object.__setattr__(self, "torsion_rescue_parent_proposal_indices", rescue_parents)
        object.__setattr__(self, "source_paired_torsion_rescue_profile", rescue_profile)
        object.__setattr__(self, "baseline_guided_receipt_sha256", baseline_receipt_sha256)
        object.__setattr__(self, "torsion_rescue_allocation_sha256", allocation_sha256)
        object.__setattr__(self, "ligand_anchor_atom_indices", ligand_anchors)
        object.__setattr__(self, "receptor_anchor_atom_indices", receptor_anchors)
        object.__setattr__(
            self, "requested_anchor_distance_angstroms", requested_distances
        )
        object.__setattr__(
            self, "observed_anchor_distance_angstroms", observed_distances
        )
        object.__setattr__(
            self,
            "ensemble_source_proposal_indices",
            ensemble_sources,
        )
        object.__setattr__(self, "feature_counts", MappingProxyType(counts))
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        rescue_profile = self.source_paired_torsion_rescue_profile
        guidance_rows: list[dict[str, object]] = []
        for index, (
            mode,
            ligand_atoms,
            receptor_atoms,
            requested,
            observed,
            ensemble_source,
            rescue_parent,
        ) in enumerate(
            zip(
                self.proposal_modes,
                self.ligand_anchor_atom_indices,
                self.receptor_anchor_atom_indices,
                self.requested_anchor_distance_angstroms,
                self.observed_anchor_distance_angstroms,
                self.ensemble_source_proposal_indices,
                self.torsion_rescue_parent_proposal_indices,
                strict=True,
            )
        ):
            row: dict[str, object] = {
                "proposal_index": index,
                "mode": mode,
                "ligand_anchor_atom_indices": list(ligand_atoms),
                "receptor_anchor_atom_indices": list(receptor_atoms),
                "anchor_pairs": (
                    [
                        {"ligand_atom_index": ligand_index, "receptor_atom_index": receptor_index}
                        for ligand_index, receptor_index in zip(ligand_atoms, receptor_atoms)
                    ]
                    if mode == MULTI_ANCHOR_MODE
                    else []
                ),
                "anchor_pairing": "positionally_aligned" if mode == MULTI_ANCHOR_MODE else None,
                "anchor_distance_aggregation": (
                    "per_pair_arithmetic_mean" if mode == MULTI_ANCHOR_MODE else None
                ),
                "requested_anchor_distance_angstrom_binary64_hex": (
                    None if requested is None else requested.hex()
                ),
                "observed_anchor_distance_angstrom_binary64_hex": (
                    None if observed is None else observed.hex()
                ),
                "ensemble_source_proposal_index": ensemble_source,
            }
            if rescue_profile:
                row["torsion_rescue_parent_proposal_index"] = rescue_parent
            guidance_rows.append(row)
        projection: dict[str, object] = {
            "schema_id": (
                SOURCE_PAIRED_TORSION_RESCUE_GUIDED_RECEIPT_SCHEMA_ID
                if rescue_profile
                else GUIDED_PLACEMENT_RECEIPT_SCHEMA_ID
            ),
            "authenticated_input_receipt_sha256": self.authenticated_input_receipt_sha256,
            "guidance_context_sha256": self.guidance_context_sha256,
            "guided_policy_sha256": self.guided_policy_sha256,
            "budget_sha256": self.budget_sha256,
            "proposal_count": len(self.proposal_modes),
            "proposal_fingerprint_sha256s": list(self.proposal_fingerprint_sha256s),
            "proposal_modes": list(self.proposal_modes),
            "proposal_guidance_rows": guidance_rows,
            "guided_proposal_count": sum(
                mode not in {POCKET_CENTER_BASELINE_MODE, UNIFORM_FALLBACK_MODE}
                for mode in self.proposal_modes
            ),
            "pocket_center_baseline_count": sum(
                mode == POCKET_CENTER_BASELINE_MODE for mode in self.proposal_modes
            ),
            "uniform_fallback_count": sum(
                mode == UNIFORM_FALLBACK_MODE for mode in self.proposal_modes
            ),
            "uniform_v3_ensemble_count": sum(
                mode == UNIFORM_V3_ENSEMBLE_MODE for mode in self.proposal_modes
            ),
            "uniform_random_placement_retained_as_fallback": True,
            "feature_counts": dict(self.feature_counts),
            "scientifically_validated": False,
            "claim_safe": False,
        }
        if rescue_profile:
            projection.update(
                {
                    "source_paired_torsion_rescue_profile": True,
                    "baseline_guided_receipt_sha256": self.baseline_guided_receipt_sha256,
                    "torsion_rescue_allocation_sha256": self.torsion_rescue_allocation_sha256,
                    "uniform_torsion_rescue_variant_count": sum(
                        mode == UNIFORM_TORSION_RESCUE_VARIANT_MODE
                        for mode in self.proposal_modes
                    ),
                    "uniform_torsion_rescue_variant_cap": MAX_UNIFORM_TORSION_RESCUE_VARIANTS,
                    "proposal_objects_and_coordinates_unchanged": True,
                    "selected_parent_proposal_objects_retained": True,
                    "development_only": True,
                    "stage0_eligible": False,
                    "fresh_execution_authorized": False,
                }
            )
        return projection

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingAuthorityError("guided placement receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class SourcePairedTorsionRescueProposalReceipt:
    """End-to-end evidence for a source-paired rescue proposal batch."""

    authenticated_input_receipt_sha256: str
    budget_sha256: str
    source_ligand_system_sha256: str
    source_ligand_topology_sha256: str
    rescue_policy_sha256: str
    allocation: SourcePairedTorsionRescueAllocation
    baseline_guided_receipt: GuidedPlacementReceipt
    guided_receipt: GuidedPlacementReceipt
    candidate_ids: tuple[str, ...]
    proposal_fingerprint_sha256s: tuple[str, ...]
    proposal_coordinate_fingerprint_sha256s: tuple[str, ...]
    proposal_torsion_metadata_sha256s: tuple[str, ...]
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "authenticated_input_receipt_sha256",
            "budget_sha256",
            "source_ligand_system_sha256",
            "source_ligand_topology_sha256",
            "rescue_policy_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if not isinstance(self.allocation, SourcePairedTorsionRescueAllocation):
            raise TypeError("allocation must be SourcePairedTorsionRescueAllocation")
        if not isinstance(self.baseline_guided_receipt, GuidedPlacementReceipt):
            raise TypeError("baseline_guided_receipt must be GuidedPlacementReceipt")
        if not isinstance(self.guided_receipt, GuidedPlacementReceipt):
            raise TypeError("guided_receipt must be GuidedPlacementReceipt")
        allocation = self.allocation
        baseline = self.baseline_guided_receipt
        guided = self.guided_receipt
        allocation.allocation_sha256
        baseline.receipt_sha256
        guided.receipt_sha256

        policy = SourcePairedTorsionRescuePolicy()
        base_policy = policy.base_guided_policy
        if (
            self.rescue_policy_sha256 != policy.fingerprint_sha256
            or allocation.rescue_policy_sha256 != policy.fingerprint_sha256
            or allocation.base_guided_policy_sha256 != base_policy.fingerprint_sha256
            or allocation.authenticated_input_receipt_sha256
            != self.authenticated_input_receipt_sha256
            or allocation.guidance_context_sha256 != baseline.guidance_context_sha256
            or allocation.budget_sha256 != self.budget_sha256
            or baseline.authenticated_input_receipt_sha256
            != self.authenticated_input_receipt_sha256
            or guided.authenticated_input_receipt_sha256
            != self.authenticated_input_receipt_sha256
            or baseline.budget_sha256 != self.budget_sha256
            or guided.budget_sha256 != self.budget_sha256
            or baseline.guided_policy_sha256 != base_policy.fingerprint_sha256
            or guided.guided_policy_sha256 != policy.fingerprint_sha256
            or guided.baseline_guided_receipt_sha256 != baseline.receipt_sha256
            or guided.torsion_rescue_allocation_sha256 != allocation.allocation_sha256
            or baseline.source_paired_torsion_rescue_profile
            or not guided.source_paired_torsion_rescue_profile
        ):
            raise DockingAuthorityError(
                "source-paired torsion-rescue proposal authority is cross-wired"
            )

        candidate_ids = tuple(str(value or "").strip() for value in self.candidate_ids)
        if (
            len(candidate_ids) != SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT
            or any(not value for value in candidate_ids)
            or len(set(candidate_ids)) != len(candidate_ids)
        ):
            raise DockingAuthorityError(
                "source-paired torsion-rescue candidate IDs are invalid"
            )

        def digest_rows(values: Sequence[str], *, name: str) -> tuple[str, ...]:
            rows = tuple(_digest(value, name=name) for value in values)
            if len(rows) != SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT:
                raise DockingAuthorityError(
                    f"source-paired torsion-rescue {name} rows must contain 64 values"
                )
            return rows

        fingerprints = digest_rows(
            self.proposal_fingerprint_sha256s,
            name="proposal fingerprint",
        )
        coordinate_fingerprints = digest_rows(
            self.proposal_coordinate_fingerprint_sha256s,
            name="coordinate fingerprint",
        )
        torsion_fingerprints = digest_rows(
            self.proposal_torsion_metadata_sha256s,
            name="torsion metadata fingerprint",
        )
        expected_pairs = tuple(
            sorted(
                (
                    *allocation.v3_target_parent_pairs,
                    *allocation.rescue_target_parent_pairs,
                )
            )
        )
        baseline_pairs = tuple(
            (index, parent)
            for index, (mode, parent) in enumerate(
                zip(
                    baseline.proposal_modes,
                    baseline.ensemble_source_proposal_indices,
                    strict=True,
                )
            )
            if mode == UNIFORM_V3_ENSEMBLE_MODE and parent is not None
        )
        guided_v3_pairs = tuple(
            (index, parent)
            for index, (mode, parent) in enumerate(
                zip(
                    guided.proposal_modes,
                    guided.ensemble_source_proposal_indices,
                    strict=True,
                )
            )
            if mode == UNIFORM_V3_ENSEMBLE_MODE and parent is not None
        )
        guided_rescue_pairs = tuple(
            (index, parent)
            for index, (mode, parent) in enumerate(
                zip(
                    guided.proposal_modes,
                    guided.torsion_rescue_parent_proposal_indices,
                    strict=True,
                )
            )
            if mode == UNIFORM_TORSION_RESCUE_VARIANT_MODE and parent is not None
        )
        rescue_target_set = {
            target for target, _ in allocation.rescue_target_parent_pairs
        }
        unchanged_row_evidence = all(
            (
                guided.proposal_modes[index]
                == (
                    UNIFORM_TORSION_RESCUE_VARIANT_MODE
                    if index in rescue_target_set
                    else baseline.proposal_modes[index]
                )
                and guided.ensemble_source_proposal_indices[index]
                == (
                    None
                    if index in rescue_target_set
                    else baseline.ensemble_source_proposal_indices[index]
                )
            )
            for index in range(SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT)
        )
        if (
            allocation.candidate_count != SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT
            or baseline_pairs != expected_pairs
            or guided_v3_pairs != allocation.v3_target_parent_pairs
            or guided_rescue_pairs != allocation.rescue_target_parent_pairs
            or not unchanged_row_evidence
            or baseline.proposal_fingerprint_sha256s != fingerprints
            or guided.proposal_fingerprint_sha256s != fingerprints
            or baseline.guidance_context_sha256 != guided.guidance_context_sha256
            or baseline.ligand_anchor_atom_indices != guided.ligand_anchor_atom_indices
            or baseline.receptor_anchor_atom_indices
            != guided.receptor_anchor_atom_indices
            or baseline.requested_anchor_distance_angstroms
            != guided.requested_anchor_distance_angstroms
            or baseline.observed_anchor_distance_angstroms
            != guided.observed_anchor_distance_angstroms
            or dict(baseline.feature_counts) != dict(guided.feature_counts)
        ):
            raise DockingAuthorityError(
                "source-paired torsion-rescue proposal lineage is cross-wired"
            )
        object.__setattr__(self, "candidate_ids", candidate_ids)
        object.__setattr__(self, "proposal_fingerprint_sha256s", fingerprints)
        object.__setattr__(
            self,
            "proposal_coordinate_fingerprint_sha256s",
            coordinate_fingerprints,
        )
        object.__setattr__(
            self,
            "proposal_torsion_metadata_sha256s",
            torsion_fingerprints,
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        policy = SourcePairedTorsionRescuePolicy()
        return {
            "schema_id": SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_RECEIPT_SCHEMA_ID,
            "authenticated_input_receipt_sha256": (
                self.authenticated_input_receipt_sha256
            ),
            "budget_sha256": self.budget_sha256,
            "source_ligand_system_sha256": self.source_ligand_system_sha256,
            "source_ligand_topology_sha256": self.source_ligand_topology_sha256,
            "rescue_policy_sha256": self.rescue_policy_sha256,
            "rescue_policy": policy.to_dict(),
            "allocation": self.allocation.to_dict(),
            "baseline_guided_placement": self.baseline_guided_receipt.to_dict(),
            "guided_placement": self.guided_receipt.to_dict(),
            "candidate_count": SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT,
            "candidate_slots": [
                {
                    "proposal_index": index,
                    "candidate_id": self.candidate_ids[index],
                    "proposal_fingerprint_sha256": (
                        self.proposal_fingerprint_sha256s[index]
                    ),
                    "coordinate_fingerprint_sha256": (
                        self.proposal_coordinate_fingerprint_sha256s[index]
                    ),
                    "torsion_metadata_sha256": (
                        self.proposal_torsion_metadata_sha256s[index]
                    ),
                }
                for index in range(SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT)
            ],
            "proposal_objects_and_coordinates_unchanged": True,
            "selected_parent_proposal_objects_retained": True,
            "result_dependent_allocation": False,
            "development_only": True,
            "stage0_eligible": False,
            "fresh_execution_authorized": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingAuthorityError(
                "source-paired torsion-rescue proposal receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}

@dataclass(frozen=True, slots=True)
class FixedSourceBoundConformerLineageRow:
    proposal_index: int
    source_proposal_index: int
    candidate_id: str
    conformer_rank: int
    source_conformer_index: int
    conformer_id: str
    conformer_energy_kcal_mol: float
    conformer_coordinates_sha256: str
    source_proposal_fingerprint_sha256: str
    source_coordinate_fingerprint_sha256: str
    variant_proposal_fingerprint_sha256: str
    variant_coordinate_fingerprint_sha256: str
    torsion_metadata_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "proposal_index",
            "source_proposal_index",
            "conformer_rank",
            "source_conformer_index",
        ):
            value = getattr(self, name)
            if type(value) is not int:
                raise DockingAuthorityError(
                    f"fixed true-conformer {name} must be an exact integer"
                )
        if not (
            FIXED_SOURCE_BOUND_CONFORMER_VARIANT_START
            <= self.proposal_index
            < FIXED_SOURCE_BOUND_CONFORMER_SOURCE_START
        ):
            raise DockingAuthorityError(
                "fixed true-conformer proposal index is outside the variant lane"
            )
        expected_source = (
            FIXED_SOURCE_BOUND_CONFORMER_SOURCE_START
            + self.proposal_index
            - FIXED_SOURCE_BOUND_CONFORMER_VARIANT_START
        )
        if self.source_proposal_index != expected_source:
            raise DockingAuthorityError(
                "fixed true-conformer source pairing is invalid"
            )
        if self.conformer_rank < 0 or self.source_conformer_index < 0:
            raise DockingAuthorityError(
                "fixed true-conformer conformer indices must be nonnegative"
            )
        candidate_id = str(self.candidate_id or "").strip()
        if not candidate_id:
            raise DockingAuthorityError(
                "fixed true-conformer candidate ID must be non-empty"
            )
        energy = float(self.conformer_energy_kcal_mol)
        if not math.isfinite(energy):
            raise DockingAuthorityError("fixed true-conformer energy must be finite")
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "conformer_energy_kcal_mol", energy)
        for name in (
            "conformer_id",
            "conformer_coordinates_sha256",
            "source_proposal_fingerprint_sha256",
            "source_coordinate_fingerprint_sha256",
            "variant_proposal_fingerprint_sha256",
            "variant_coordinate_fingerprint_sha256",
            "torsion_metadata_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": FIXED_SOURCE_BOUND_CONFORMER_LINEAGE_SCHEMA_ID,
            "proposal_index": self.proposal_index,
            "source_proposal_index": self.source_proposal_index,
            "candidate_id": self.candidate_id,
            "conformer_rank": self.conformer_rank,
            "source_conformer_index": self.source_conformer_index,
            "conformer_id": self.conformer_id,
            "conformer_energy_kcal_mol_binary64_hex": (
                self.conformer_energy_kcal_mol.hex()
            ),
            "conformer_coordinates_sha256": self.conformer_coordinates_sha256,
            "source_proposal_fingerprint_sha256": (
                self.source_proposal_fingerprint_sha256
            ),
            "source_coordinate_fingerprint_sha256": (
                self.source_coordinate_fingerprint_sha256
            ),
            "variant_proposal_fingerprint_sha256": (
                self.variant_proposal_fingerprint_sha256
            ),
            "variant_coordinate_fingerprint_sha256": (
                self.variant_coordinate_fingerprint_sha256
            ),
            "torsion_metadata_sha256": self.torsion_metadata_sha256,
        }


@dataclass(frozen=True, slots=True)
class FixedSourceBoundConformerProposalReceipt:
    authenticated_input_receipt_sha256: str
    budget_sha256: str
    source_ligand_system_sha256: str
    source_ligand_topology_sha256: str
    source_conformer_ensemble_receipt_sha256: str
    source_conformer_ensemble_document: Mapping[str, Any]
    baseline_placement_receipt_sha256: str
    profile_fingerprint_sha256: str
    guided_receipt: GuidedPlacementReceipt
    baseline_candidate_ids: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    baseline_proposal_fingerprint_sha256s: tuple[str, ...]
    proposal_fingerprint_sha256s: tuple[str, ...]
    baseline_coordinate_fingerprint_sha256s: tuple[str, ...]
    proposal_coordinate_fingerprint_sha256s: tuple[str, ...]
    proposal_torsion_metadata_sha256s: tuple[str, ...]
    lineage_rows: tuple[FixedSourceBoundConformerLineageRow, ...]
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "authenticated_input_receipt_sha256",
            "budget_sha256",
            "source_ligand_system_sha256",
            "source_ligand_topology_sha256",
            "source_conformer_ensemble_receipt_sha256",
            "baseline_placement_receipt_sha256",
            "profile_fingerprint_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        profile = fixed_source_bound_conformer_profile_document()
        if self.profile_fingerprint_sha256 != profile["fingerprint_sha256"]:
            raise DockingAuthorityError(
                "fixed true-conformer profile fingerprint is cross-wired"
            )
        if not isinstance(self.guided_receipt, GuidedPlacementReceipt):
            raise TypeError("guided_receipt must be GuidedPlacementReceipt")
        self.guided_receipt.receipt_sha256

        baseline_candidate_ids = tuple(
            str(value or "").strip() for value in self.baseline_candidate_ids
        )
        candidate_ids = tuple(str(value or "").strip() for value in self.candidate_ids)
        if (
            len(baseline_candidate_ids) != FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT
            or len(candidate_ids) != FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT
            or any(not value for value in (*baseline_candidate_ids, *candidate_ids))
            or len(set(baseline_candidate_ids))
            != FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT
            or len(set(candidate_ids)) != FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT
            or baseline_candidate_ids != candidate_ids
        ):
            raise DockingAuthorityError(
                "fixed true-conformer candidate IDs are invalid"
            )

        def digest_rows(values: Sequence[str], *, name: str) -> tuple[str, ...]:
            rows = tuple(_digest(value, name=name) for value in values)
            if len(rows) != FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT:
                raise DockingAuthorityError(
                    f"fixed true-conformer {name} rows must contain 64 values"
                )
            return rows

        baseline_fingerprints = digest_rows(
            self.baseline_proposal_fingerprint_sha256s,
            name="baseline proposal fingerprint",
        )
        fingerprints = digest_rows(
            self.proposal_fingerprint_sha256s,
            name="proposal fingerprint",
        )
        baseline_coordinate_fingerprints = digest_rows(
            self.baseline_coordinate_fingerprint_sha256s,
            name="baseline coordinate fingerprint",
        )
        coordinate_fingerprints = digest_rows(
            self.proposal_coordinate_fingerprint_sha256s,
            name="proposal coordinate fingerprint",
        )
        torsion_metadata_fingerprints = digest_rows(
            self.proposal_torsion_metadata_sha256s,
            name="proposal torsion metadata fingerprint",
        )
        lineages = tuple(self.lineage_rows)
        if any(
            not isinstance(row, FixedSourceBoundConformerLineageRow) for row in lineages
        ):
            raise TypeError(
                "lineage_rows must contain FixedSourceBoundConformerLineageRow values"
            )
        expected_variant_indices = fixed_source_bound_conformer_proposal_indices()
        if tuple(row.proposal_index for row in lineages) != expected_variant_indices:
            raise DockingAuthorityError(
                "fixed true-conformer lineage must cover the ordered 28-slot lane"
            )

        guided = self.guided_receipt
        expected_modes = (
            (POCKET_CENTER_BASELINE_MODE,) * FIXED_SOURCE_BOUND_CONFORMER_CENTERED_COUNT
            + (UNIFORM_V3_ENSEMBLE_MODE,) * FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT
            + (UNIFORM_FALLBACK_MODE,) * FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT
        )
        expected_sources: tuple[int | None, ...] = (
            (None,) * FIXED_SOURCE_BOUND_CONFORMER_CENTERED_COUNT
            + tuple(
                range(
                    FIXED_SOURCE_BOUND_CONFORMER_SOURCE_START,
                    FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT,
                )
            )
            + (None,) * FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT
        )
        if (
            guided.authenticated_input_receipt_sha256
            != self.authenticated_input_receipt_sha256
            or guided.budget_sha256 != self.budget_sha256
            or guided.guided_policy_sha256 != self.profile_fingerprint_sha256
            or guided.proposal_fingerprint_sha256s != fingerprints
            or guided.proposal_modes != expected_modes
            or guided.ensemble_source_proposal_indices != expected_sources
            or any(guided.ligand_anchor_atom_indices)
            or any(guided.receptor_anchor_atom_indices)
            or any(
                value is not None
                for value in guided.requested_anchor_distance_angstroms
            )
            or any(
                value is not None for value in guided.observed_anchor_distance_angstroms
            )
        ):
            raise DockingAuthorityError(
                "fixed true-conformer guided receipt is cross-wired"
            )

        ensemble_document = _thaw_json(self.source_conformer_ensemble_document)
        if not isinstance(ensemble_document, dict):
            raise DockingAuthorityError(
                "fixed true-conformer ensemble document must be a mapping"
            )
        ensemble_receipt = dict(ensemble_document)
        observed_ensemble_digest = ensemble_receipt.pop("receipt_sha256", None)
        conformer_rows = ensemble_receipt.pop("conformers", None)
        derivation = ensemble_receipt.get("derivation_evidence")
        if (
            observed_ensemble_digest != self.source_conformer_ensemble_receipt_sha256
            or _sha256(ensemble_receipt)
            != self.source_conformer_ensemble_receipt_sha256
            or ensemble_receipt.get("schema_id")
            != SOURCE_BOUND_CONFORMER_ENSEMBLE_SCHEMA_ID
            or not isinstance(derivation, dict)
            or derivation.get("source_system_sha256")
            != self.source_ligand_system_sha256
            or derivation.get("source_topology_sha256")
            != self.source_ligand_topology_sha256
            or ensemble_receipt.get("prepared_topology_sha256")
            != self.source_ligand_topology_sha256
            or any(
                ensemble_receipt.get(name) is not expected
                for name, expected in (
                    ("development_only", True),
                    ("stage0_eligible", False),
                    ("fresh_execution_authorized", False),
                    ("scientifically_validated", False),
                    ("claim_safe", False),
                )
            )
        ):
            raise DockingAuthorityError(
                "fixed true-conformer ensemble evidence is cross-wired"
            )
        selected_count = derivation.get("selected_conformer_count")
        if (
            type(selected_count) is not int
            or not 2 <= selected_count <= 8
            or not isinstance(conformer_rows, list)
            or len(conformer_rows) != selected_count
        ):
            raise DockingAuthorityError(
                "fixed true-conformer ensemble must contain two to eight records"
            )
        if conformer_rows != derivation.get("selected_conformer_records"):
            raise DockingAuthorityError(
                "fixed true-conformer rows are not bound to ensemble evidence"
            )
        try:
            energies = tuple(
                float.fromhex(str(row["energy_kcal_mol_binary64_hex"]))
                for row in conformer_rows
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DockingAuthorityError(
                "fixed true-conformer ensemble records are incomplete"
            ) from exc
        if any(not math.isfinite(value) for value in energies) or any(
            energies[index] > energies[index + 1] for index in range(len(energies) - 1)
        ):
            raise DockingAuthorityError(
                "fixed true-conformer records must remain energy-ranked"
            )

        retained_indices = (
            *range(FIXED_SOURCE_BOUND_CONFORMER_CENTERED_COUNT),
            *range(
                FIXED_SOURCE_BOUND_CONFORMER_SOURCE_START,
                FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT,
            ),
        )
        if any(
            baseline_fingerprints[index] != fingerprints[index]
            or baseline_coordinate_fingerprints[index] != coordinate_fingerprints[index]
            for index in retained_indices
        ):
            raise DockingAuthorityError(
                "fixed true-conformer retained source proposals changed"
            )
        for offset, row in enumerate(lineages):
            expected_rank = offset % selected_count
            record = conformer_rows[expected_rank]
            if not isinstance(record, dict):
                raise DockingAuthorityError(
                    "fixed true-conformer ensemble record is invalid"
                )
            if (
                row.conformer_rank != expected_rank
                or row.source_proposal_index
                != FIXED_SOURCE_BOUND_CONFORMER_SOURCE_START + offset
                or row.candidate_id != candidate_ids[row.proposal_index]
                or row.conformer_id != record.get("conformer_id")
                or row.source_conformer_index != record.get("source_conformer_index")
                or row.conformer_energy_kcal_mol != energies[expected_rank]
                or row.conformer_coordinates_sha256 != record.get("coordinates_sha256")
                or row.source_proposal_fingerprint_sha256
                != baseline_fingerprints[row.source_proposal_index]
                or row.source_coordinate_fingerprint_sha256
                != baseline_coordinate_fingerprints[row.source_proposal_index]
                or row.variant_proposal_fingerprint_sha256
                != fingerprints[row.proposal_index]
                or row.variant_coordinate_fingerprint_sha256
                != coordinate_fingerprints[row.proposal_index]
                or row.torsion_metadata_sha256
                != torsion_metadata_fingerprints[row.proposal_index]
                or fingerprints[row.proposal_index]
                == baseline_fingerprints[row.proposal_index]
            ):
                raise DockingAuthorityError(
                    "fixed true-conformer lineage is cross-wired"
                )

        object.__setattr__(self, "baseline_candidate_ids", baseline_candidate_ids)
        object.__setattr__(self, "candidate_ids", candidate_ids)
        object.__setattr__(
            self,
            "baseline_proposal_fingerprint_sha256s",
            baseline_fingerprints,
        )
        object.__setattr__(self, "proposal_fingerprint_sha256s", fingerprints)
        object.__setattr__(
            self,
            "baseline_coordinate_fingerprint_sha256s",
            baseline_coordinate_fingerprints,
        )
        object.__setattr__(
            self,
            "proposal_coordinate_fingerprint_sha256s",
            coordinate_fingerprints,
        )
        object.__setattr__(
            self,
            "proposal_torsion_metadata_sha256s",
            torsion_metadata_fingerprints,
        )
        object.__setattr__(self, "lineage_rows", lineages)
        object.__setattr__(
            self,
            "source_conformer_ensemble_document",
            _freeze_json(ensemble_document),
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        profile = fixed_source_bound_conformer_profile_document()
        retained = set(range(FIXED_SOURCE_BOUND_CONFORMER_CENTERED_COUNT)) | set(
            range(
                FIXED_SOURCE_BOUND_CONFORMER_SOURCE_START,
                FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT,
            )
        )
        return {
            "schema_id": FIXED_SOURCE_BOUND_CONFORMER_RECEIPT_SCHEMA_ID,
            "profile": profile,
            "profile_fingerprint_sha256": self.profile_fingerprint_sha256,
            "authenticated_input_receipt_sha256": (
                self.authenticated_input_receipt_sha256
            ),
            "budget_sha256": self.budget_sha256,
            "source_ligand_system_sha256": self.source_ligand_system_sha256,
            "source_ligand_topology_sha256": self.source_ligand_topology_sha256,
            "source_conformer_ensemble_receipt_sha256": (
                self.source_conformer_ensemble_receipt_sha256
            ),
            "source_conformer_ensemble": _thaw_json(
                self.source_conformer_ensemble_document
            ),
            "baseline_placement_receipt_sha256": (
                self.baseline_placement_receipt_sha256
            ),
            "guided_placement_receipt_sha256": self.guided_receipt.receipt_sha256,
            "candidate_count": FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT,
            "candidate_slots": [
                {
                    "proposal_index": index,
                    "candidate_id": self.candidate_ids[index],
                    "baseline_candidate_id": self.baseline_candidate_ids[index],
                    "baseline_proposal_fingerprint_sha256": (
                        self.baseline_proposal_fingerprint_sha256s[index]
                    ),
                    "proposal_fingerprint_sha256": (
                        self.proposal_fingerprint_sha256s[index]
                    ),
                    "baseline_coordinate_fingerprint_sha256": (
                        self.baseline_coordinate_fingerprint_sha256s[index]
                    ),
                    "coordinate_fingerprint_sha256": (
                        self.proposal_coordinate_fingerprint_sha256s[index]
                    ),
                    "torsion_metadata_sha256": (
                        self.proposal_torsion_metadata_sha256s[index]
                    ),
                    "baseline_object_retained": index in retained,
                }
                for index in range(FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT)
            ],
            "lineage_rows": [row.to_dict() for row in self.lineage_rows],
            "coordinate_geometry_authoritative": True,
            "torsion_metadata_non_reconstructive": True,
            "development_only": True,
            "stage0_eligible": False,
            "fresh_execution_authorized": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingAuthorityError("fixed true-conformer proposal receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def _generate_source_paired_torsion_rescue_docking_proposals(
    authenticated_problem: AuthenticatedDockingProblem,
    budget: DockingBudget,
    context: GuidedPlacementContext,
    *,
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    policy: SourcePairedTorsionRescuePolicy,
) -> tuple[
    tuple[DockingProposal, ...],
    GuidedPlacementReceipt,
    SourcePairedTorsionRescueProposalReceipt,
]:
    """Reclassify bounded existing V3 pairs without changing proposals."""

    allocation = source_paired_torsion_rescue_allocation(
        authenticated_problem,
        context,
        budget,
        policy,
    )
    proposals, baseline_receipt = generate_guided_docking_proposals(
        authenticated_problem,
        budget,
        context,
        receptor_system=receptor_system,
        ligand_system=ligand_system,
        policy=policy.base_guided_policy,
    )
    baseline_pairs = tuple(
        (proposal_index, source_index)
        for proposal_index, (mode, source_index) in enumerate(
            zip(
                baseline_receipt.proposal_modes,
                baseline_receipt.ensemble_source_proposal_indices,
                strict=True,
            )
        )
        if mode == UNIFORM_V3_ENSEMBLE_MODE and source_index is not None
    )
    expected_pairs = tuple(
        sorted(
            (
                *allocation.v3_target_parent_pairs,
                *allocation.rescue_target_parent_pairs,
            )
        )
    )
    if baseline_pairs != expected_pairs:
        raise DockingAuthorityError(
            "torsion-rescue allocation disagrees with the baseline V3 receipt"
        )
    modes = list(baseline_receipt.proposal_modes)
    ensemble_sources = list(baseline_receipt.ensemble_source_proposal_indices)
    rescue_parents: list[int | None] = [None] * len(proposals)
    for target_index, parent_index in allocation.rescue_target_parent_pairs:
        if (
            modes[target_index] != UNIFORM_V3_ENSEMBLE_MODE
            or ensemble_sources[target_index] != parent_index
            or modes[parent_index] != UNIFORM_FALLBACK_MODE
        ):
            raise DockingAuthorityError(
                "torsion-rescue target-parent lineage is cross-wired"
            )
        modes[target_index] = UNIFORM_TORSION_RESCUE_VARIANT_MODE
        ensemble_sources[target_index] = None
        rescue_parents[target_index] = parent_index
    receipt = GuidedPlacementReceipt(
        authenticated_input_receipt_sha256=(
            baseline_receipt.authenticated_input_receipt_sha256
        ),
        guidance_context_sha256=baseline_receipt.guidance_context_sha256,
        guided_policy_sha256=policy.fingerprint_sha256,
        budget_sha256=baseline_receipt.budget_sha256,
        proposal_fingerprint_sha256s=(baseline_receipt.proposal_fingerprint_sha256s),
        proposal_modes=tuple(modes),
        ligand_anchor_atom_indices=(baseline_receipt.ligand_anchor_atom_indices),
        receptor_anchor_atom_indices=(baseline_receipt.receptor_anchor_atom_indices),
        requested_anchor_distance_angstroms=(
            baseline_receipt.requested_anchor_distance_angstroms
        ),
        observed_anchor_distance_angstroms=(
            baseline_receipt.observed_anchor_distance_angstroms
        ),
        feature_counts=baseline_receipt.feature_counts,
        ensemble_source_proposal_indices=tuple(ensemble_sources),
        torsion_rescue_parent_proposal_indices=tuple(rescue_parents),
        source_paired_torsion_rescue_profile=True,
        baseline_guided_receipt_sha256=baseline_receipt.receipt_sha256,
        torsion_rescue_allocation_sha256=allocation.allocation_sha256,
    )
    if receipt.proposal_fingerprint_sha256s != tuple(
        proposal.fingerprint_sha256 for proposal in proposals
    ):
        raise DockingAuthorityError(
            "torsion-rescue receipt changed the baseline proposal objects"
        )
    provenance = SourcePairedTorsionRescueProposalReceipt(
        authenticated_input_receipt_sha256=(authenticated_problem.input_receipt_sha256),
        budget_sha256=_budget_sha256(budget),
        source_ligand_system_sha256=canonical_system_sha256(ligand_system),
        source_ligand_topology_sha256=canonical_topology_sha256(ligand_system),
        rescue_policy_sha256=policy.fingerprint_sha256,
        allocation=allocation,
        baseline_guided_receipt=baseline_receipt,
        guided_receipt=receipt,
        candidate_ids=tuple(proposal.candidate_id for proposal in proposals),
        proposal_fingerprint_sha256s=tuple(
            proposal.fingerprint_sha256 for proposal in proposals
        ),
        proposal_coordinate_fingerprint_sha256s=tuple(
            proposal.coordinate_fingerprint_sha256 for proposal in proposals
        ),
        proposal_torsion_metadata_sha256s=tuple(
            _torsion_metadata_sha256(proposal.torsion_angles) for proposal in proposals
        ),
    )
    return proposals, receipt, provenance


def generate_source_paired_torsion_rescue_docking_proposals(
    authenticated_problem: AuthenticatedDockingProblem,
    budget: DockingBudget,
    context: GuidedPlacementContext,
    *,
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    policy: SourcePairedTorsionRescuePolicy | None = None,
) -> tuple[
    tuple[DockingProposal, ...],
    GuidedPlacementReceipt,
    SourcePairedTorsionRescueProposalReceipt,
]:
    """Build the fixed rescue batch and its complete development evidence."""

    selected_policy = policy or SourcePairedTorsionRescuePolicy()
    if not isinstance(selected_policy, SourcePairedTorsionRescuePolicy):
        raise TypeError("policy must be SourcePairedTorsionRescuePolicy")
    return _generate_source_paired_torsion_rescue_docking_proposals(
        authenticated_problem,
        budget,
        context,
        receptor_system=receptor_system,
        ligand_system=ligand_system,
        policy=selected_policy,
    )

def generate_guided_docking_proposals(
    authenticated_problem: AuthenticatedDockingProblem,
    budget: DockingBudget,
    context: GuidedPlacementContext,
    *,
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    policy: GuidedPlacementPolicy | SourcePairedTorsionRescuePolicy | None = None,
) -> tuple[tuple[DockingProposal, ...], GuidedPlacementReceipt]:
    if not isinstance(authenticated_problem, AuthenticatedDockingProblem):
        raise TypeError("authenticated_problem must be AuthenticatedDockingProblem")
    if not isinstance(budget, DockingBudget):
        raise TypeError("budget must be DockingBudget")
    if not isinstance(context, GuidedPlacementContext):
        raise TypeError("context must be GuidedPlacementContext")
    selected_policy = GuidedPlacementPolicy() if policy is None else policy
    if isinstance(selected_policy, SourcePairedTorsionRescuePolicy):
        proposals, receipt, _ = _generate_source_paired_torsion_rescue_docking_proposals(
            authenticated_problem,
            budget,
            context,
            receptor_system=receptor_system,
            ligand_system=ligand_system,
            policy=selected_policy,
        )
        return proposals, receipt
    if not isinstance(selected_policy, GuidedPlacementPolicy):
        raise TypeError(
            "policy must be GuidedPlacementPolicy or SourcePairedTorsionRescuePolicy"
        )
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
    placement_policy = PocketPlacementPolicy(
        centered_candidate_count=selected_policy.centered_candidate_count
    )
    baseline, _ = generate_pocket_centered_docking_proposals(
        authenticated_problem,
        budget,
        policy=placement_policy,
    )
    centered_count, guided_count, modes = _guided_allocation(
        context,
        budget,
        selected_policy,
    )
    from . import proposals as proposal_module

    proposals = list(baseline)
    proposal_modes = [UNIFORM_FALLBACK_MODE] * len(proposals)
    proposal_modes[:centered_count] = [POCKET_CENTER_BASELINE_MODE] * centered_count
    ligand_anchor_rows: list[tuple[int, ...]] = [()] * len(proposals)
    receptor_anchor_rows: list[tuple[int, ...]] = [()] * len(proposals)
    requested_anchor_distances: list[float | None] = [None] * len(proposals)
    observed_anchor_distances: list[float | None] = [None] * len(proposals)
    ensemble_source_indices: list[int | None] = [None] * len(proposals)
    search_space = authenticated_problem.search_space
    pocket_center = authenticated_problem.pocket.center.to(
        dtype=search_space.local_offsets.dtype
    )
    multi_anchor_count = 0
    guided_transform_count = guided_count
    if selected_policy.uniform_v3_ensemble_enabled and guided_count:
        target_indices = tuple(
            range(centered_count, centered_count + guided_count)
        )
        uniform_source_indices = tuple(
            range(centered_count + guided_count, len(baseline))
        )
        selected_sources = _evenly_spaced_uniform_sources(
            uniform_source_indices,
            guided_count,
        )
        for proposal_index, source_index in zip(
            target_indices,
            selected_sources,
            strict=True,
        ):
            target = baseline[proposal_index]
            source = baseline[source_index]
            fingerprint = proposal_module._proposal_fingerprint(
                proposal_index=proposal_index,
                seed=budget.seed,
                torsion_angles=source.torsion_angles,
                rotation=source.rotation,
                translation=source.translation,
                problem_fingerprint_sha256=(
                    authenticated_problem.problem.fingerprint_sha256
                ),
                search_space_fingerprint_sha256=(
                    search_space.fingerprint_sha256
                ),
                coordinate_fingerprint_sha256=(
                    source.coordinate_fingerprint_sha256
                ),
            )
            variant = DockingProposal(
                candidate_id=target.candidate_id,
                coordinates=source.coordinates,
                torsion_angles=source.torsion_angles,
                rotation=source.rotation,
                translation=source.translation,
                proposal_index=proposal_index,
                seed=budget.seed,
                fingerprint_sha256=fingerprint,
                problem_fingerprint_sha256=(
                    authenticated_problem.problem.fingerprint_sha256
                ),
                search_space_fingerprint_sha256=(
                    search_space.fingerprint_sha256
                ),
                coordinate_fingerprint_sha256=(
                    source.coordinate_fingerprint_sha256
                ),
            )
            variant.assert_integrity()
            proposals[proposal_index] = variant
            proposal_modes[proposal_index] = UNIFORM_V3_ENSEMBLE_MODE
            ensemble_source_indices[proposal_index] = source_index
        guided_transform_count = 0
    for guided_slot_index in range(guided_transform_count):
        proposal_index = centered_count + guided_slot_index
        base_mode = modes[proposal_index % len(modes)]
        cycle_index = proposal_index // len(modes)
        mode = base_mode
        if (
            base_mode in {"donor_acceptor_hotspot", "charge_anchor"}
            and cycle_index >= 1
            and cycle_index % 2 == 1
            and multi_anchor_count
            < selected_policy.maximum_guided_candidates_per_mode
            and _multi_anchor_available(context)
        ):
            mode = MULTI_ANCHOR_MODE
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
            if mode != MULTI_ANCHOR_MODE:
                continue
            mode = base_mode
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
        multi_anchor_count += int(mode == MULTI_ANCHOR_MODE)
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
        ensemble_source_proposal_indices=tuple(ensemble_source_indices),
    )
    return result, receipt


def generate_fixed_source_bound_conformer_docking_proposals(
    authenticated_problem: AuthenticatedDockingProblem,
    budget: DockingBudget,
    context: GuidedPlacementContext,
    *,
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    source_conformer_ensemble: SourceBoundPreparedConformerEnsemble,
) -> tuple[
    tuple[DockingProposal, ...],
    GuidedPlacementReceipt,
    FixedSourceBoundConformerProposalReceipt,
]:
    """Build the historical-development fixed 64-slot true-conformer lane."""

    if not isinstance(authenticated_problem, AuthenticatedDockingProblem):
        raise TypeError("authenticated_problem must be AuthenticatedDockingProblem")
    if not isinstance(budget, DockingBudget):
        raise TypeError("budget must be DockingBudget")
    if not isinstance(context, GuidedPlacementContext):
        raise TypeError("context must be GuidedPlacementContext")
    if not isinstance(source_conformer_ensemble, SourceBoundPreparedConformerEnsemble):
        raise TypeError(
            "source_conformer_ensemble must be SourceBoundPreparedConformerEnsemble"
        )
    if budget.candidate_count != FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT:
        raise DockingAuthorityError(
            "fixed true-conformer profile requires exactly 64 candidates"
        )
    authenticated_problem.input_receipt_sha256
    if (
        context.authority_input_receipt_sha256
        != authenticated_problem.input_receipt_sha256
        or context.receptor_system_sha256
        != authenticated_problem.receptor_system_sha256
        or context.ligand_system_sha256 != authenticated_problem.ligand_system_sha256
        or context.receptor_atom_indices != authenticated_problem.receptor_atom_indices
    ):
        raise DockingAuthorityError(
            "fixed true-conformer guided context is cross-wired"
        )
    context.fingerprint_sha256
    derived_context = build_guided_placement_context(
        authenticated_problem,
        receptor_system,
        ligand_system,
    )
    if derived_context.fingerprint_sha256 != context.fingerprint_sha256:
        raise DockingAuthorityError(
            "fixed true-conformer context does not match its derivation"
        )
    try:
        ensemble_document = source_conformer_ensemble.to_dict()
    except ConformerPreparationError as exc:
        raise DockingAuthorityError(
            "fixed true-conformer prepared ensemble is invalid"
        ) from exc
    source_ligand_system_sha256 = canonical_system_sha256(
        source_conformer_ensemble.source_system
    )
    active_ligand_system_sha256 = canonical_system_sha256(ligand_system)
    source_ligand_topology_sha256 = canonical_topology_sha256(
        source_conformer_ensemble.source_system
    )
    prepared_topology_sha256 = canonical_topology_sha256(
        source_conformer_ensemble.system
    )
    if (
        source_ligand_system_sha256 != active_ligand_system_sha256
        or source_ligand_system_sha256 != authenticated_problem.ligand_system_sha256
        or source_ligand_topology_sha256 != prepared_topology_sha256
    ):
        raise DockingAuthorityError(
            "fixed true-conformer ensemble is cross-wired to another ligand"
        )
    conformer_count = len(source_conformer_ensemble.records)
    search_space = authenticated_problem.search_space
    ensemble_coordinates = source_conformer_ensemble.system.coordinates
    if (
        not 2 <= conformer_count <= 8
        or ensemble_coordinates.shape != (conformer_count, ligand_system.atom_count, 3)
        or ensemble_coordinates.device.type != "cpu"
        or ensemble_coordinates.dtype != search_space.local_offsets.dtype
        or ligand_system.coordinates.dtype != search_space.local_offsets.dtype
        or ligand_system.coordinates.device.type != "cpu"
    ):
        raise DockingAuthorityError(
            "fixed true-conformer ensemble is outside the fixed profile contract"
        )

    placement_policy = PocketPlacementPolicy(
        centered_candidate_count=FIXED_SOURCE_BOUND_CONFORMER_CENTERED_COUNT
    )
    baseline, placement_receipt = generate_pocket_centered_docking_proposals(
        authenticated_problem,
        budget,
        policy=placement_policy,
    )
    if len(baseline) != FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT:
        raise DockingAuthorityError(
            "fixed true-conformer baseline does not contain 64 proposals"
        )
    for proposal_index, proposal in enumerate(baseline):
        proposal.assert_integrity()
        expected_candidate_id = _stable_candidate_id(
            proposal_index=proposal_index,
            seed=budget.seed,
            problem_fingerprint_sha256=(
                authenticated_problem.problem.fingerprint_sha256
            ),
            search_space_fingerprint_sha256=search_space.fingerprint_sha256,
        )
        if (
            proposal.proposal_index != proposal_index
            or proposal.seed != budget.seed
            or proposal.candidate_id != expected_candidate_id
        ):
            raise DockingAuthorityError(
                "fixed true-conformer baseline candidate identity is invalid"
            )

    torsion_metadata_by_rank = tuple(
        _source_relative_rotor_torsion_metadata(
            authenticated_problem,
            source_conformer_ensemble.source_system,
            ensemble_coordinates[rank],
        )
        for rank in range(conformer_count)
    )
    proposals = list(baseline)
    torsion_metadata_fingerprints = [
        _torsion_metadata_sha256(proposal.torsion_angles) for proposal in baseline
    ]
    lineages: list[FixedSourceBoundConformerLineageRow] = []
    from . import proposals as proposal_module

    pocket_center = authenticated_problem.pocket.center.to(
        dtype=search_space.local_offsets.dtype,
        device="cpu",
    )
    for offset in range(FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT):
        proposal_index = FIXED_SOURCE_BOUND_CONFORMER_VARIANT_START + offset
        source_index = FIXED_SOURCE_BOUND_CONFORMER_SOURCE_START + offset
        conformer_rank = offset % conformer_count
        target = baseline[proposal_index]
        source = baseline[source_index]
        record = source_conformer_ensemble.records[conformer_rank]
        conformer = ensemble_coordinates[conformer_rank]
        conformer_centroid = conformer.mean(dim=0)
        source_centroid = source.coordinates.mean(dim=0)
        rotation = source.rotation
        coordinates = (
            (conformer - conformer_centroid) @ rotation.T + source_centroid
        ).contiguous()
        translation = (source_centroid - conformer_centroid @ rotation.T).contiguous()
        reconstructed = conformer @ rotation.T + translation
        if not bool(
            torch.allclose(
                reconstructed,
                coordinates,
                atol=1.0e-12,
                rtol=0.0,
            )
        ):
            raise DockingAuthorityError(
                "fixed true-conformer rigid frame is numerically inconsistent"
            )
        centroid_error = float(
            torch.linalg.vector_norm(coordinates.mean(dim=0) - source_centroid).item()
        )
        centroid_offset = float(
            torch.linalg.vector_norm(coordinates.mean(dim=0) - pocket_center).item()
        )
        if (
            centroid_error > _CENTROID_TOLERANCE_ANGSTROM
            or centroid_offset
            > budget.translation_radius_angstrom + _CENTROID_TOLERANCE_ANGSTROM
        ):
            raise DockingAuthorityError(
                "fixed true-conformer proposal exceeds its paired source frame"
            )
        torsion_metadata = torsion_metadata_by_rank[conformer_rank]
        coordinate_digest = coordinate_fingerprint(coordinates)
        torsion_metadata_digest = _torsion_metadata_sha256(torsion_metadata)
        fingerprint = proposal_module._proposal_fingerprint(
            proposal_index=proposal_index,
            seed=budget.seed,
            torsion_angles=torsion_metadata,
            rotation=rotation,
            translation=translation,
            problem_fingerprint_sha256=(
                authenticated_problem.problem.fingerprint_sha256
            ),
            search_space_fingerprint_sha256=search_space.fingerprint_sha256,
            coordinate_fingerprint_sha256=coordinate_digest,
        )
        variant = DockingProposal(
            candidate_id=target.candidate_id,
            coordinates=coordinates,
            torsion_angles=torsion_metadata,
            rotation=rotation,
            translation=translation,
            proposal_index=proposal_index,
            seed=budget.seed,
            fingerprint_sha256=fingerprint,
            problem_fingerprint_sha256=(
                authenticated_problem.problem.fingerprint_sha256
            ),
            search_space_fingerprint_sha256=search_space.fingerprint_sha256,
            coordinate_fingerprint_sha256=coordinate_digest,
        )
        variant.assert_integrity()
        proposals[proposal_index] = variant
        torsion_metadata_fingerprints[proposal_index] = torsion_metadata_digest
        lineages.append(
            FixedSourceBoundConformerLineageRow(
                proposal_index=proposal_index,
                source_proposal_index=source_index,
                candidate_id=target.candidate_id,
                conformer_rank=conformer_rank,
                source_conformer_index=record.source_conformer_index,
                conformer_id=record.conformer_id,
                conformer_energy_kcal_mol=record.energy_kcal_mol,
                conformer_coordinates_sha256=record.coordinates_sha256,
                source_proposal_fingerprint_sha256=source.fingerprint_sha256,
                source_coordinate_fingerprint_sha256=(
                    source.coordinate_fingerprint_sha256
                ),
                variant_proposal_fingerprint_sha256=variant.fingerprint_sha256,
                variant_coordinate_fingerprint_sha256=(
                    variant.coordinate_fingerprint_sha256
                ),
                torsion_metadata_sha256=torsion_metadata_digest,
            )
        )

    result = tuple(proposals)
    profile = fixed_source_bound_conformer_profile_document()
    profile_fingerprint_sha256 = str(profile["fingerprint_sha256"])
    proposal_modes = (
        (POCKET_CENTER_BASELINE_MODE,) * FIXED_SOURCE_BOUND_CONFORMER_CENTERED_COUNT
        + (UNIFORM_V3_ENSEMBLE_MODE,) * FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT
        + (UNIFORM_FALLBACK_MODE,) * FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT
    )
    ensemble_source_indices: tuple[int | None, ...] = (
        (None,) * FIXED_SOURCE_BOUND_CONFORMER_CENTERED_COUNT
        + tuple(
            range(
                FIXED_SOURCE_BOUND_CONFORMER_SOURCE_START,
                FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT,
            )
        )
        + (None,) * FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT
    )
    guided_receipt = GuidedPlacementReceipt(
        authenticated_input_receipt_sha256=(authenticated_problem.input_receipt_sha256),
        guidance_context_sha256=context.fingerprint_sha256,
        guided_policy_sha256=profile_fingerprint_sha256,
        budget_sha256=_budget_sha256(budget),
        proposal_fingerprint_sha256s=tuple(
            proposal.fingerprint_sha256 for proposal in result
        ),
        proposal_modes=proposal_modes,
        ligand_anchor_atom_indices=((),) * len(result),
        receptor_anchor_atom_indices=((),) * len(result),
        requested_anchor_distance_angstroms=(None,) * len(result),
        observed_anchor_distance_angstroms=(None,) * len(result),
        feature_counts=context.feature_counts(),
        ensemble_source_proposal_indices=ensemble_source_indices,
    )
    development_receipt = FixedSourceBoundConformerProposalReceipt(
        authenticated_input_receipt_sha256=(authenticated_problem.input_receipt_sha256),
        budget_sha256=_budget_sha256(budget),
        source_ligand_system_sha256=source_ligand_system_sha256,
        source_ligand_topology_sha256=source_ligand_topology_sha256,
        source_conformer_ensemble_receipt_sha256=(
            source_conformer_ensemble.receipt_sha256
        ),
        source_conformer_ensemble_document=ensemble_document,
        baseline_placement_receipt_sha256=placement_receipt.receipt_sha256,
        profile_fingerprint_sha256=profile_fingerprint_sha256,
        guided_receipt=guided_receipt,
        baseline_candidate_ids=tuple(row.candidate_id for row in baseline),
        candidate_ids=tuple(row.candidate_id for row in result),
        baseline_proposal_fingerprint_sha256s=tuple(
            row.fingerprint_sha256 for row in baseline
        ),
        proposal_fingerprint_sha256s=tuple(row.fingerprint_sha256 for row in result),
        baseline_coordinate_fingerprint_sha256s=tuple(
            row.coordinate_fingerprint_sha256 for row in baseline
        ),
        proposal_coordinate_fingerprint_sha256s=tuple(
            row.coordinate_fingerprint_sha256 for row in result
        ),
        proposal_torsion_metadata_sha256s=tuple(torsion_metadata_fingerprints),
        lineage_rows=tuple(lineages),
    )
    return result, guided_receipt, development_receipt


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
    policy: GuidedPlacementPolicy | SourcePairedTorsionRescuePolicy | None = None,
    diversity_rmsd_angstrom: float = 0.5,
    diversity_metric: str = "direct_rmsd",
    symmetry_permutations: Sequence[Sequence[int] | torch.Tensor] | None = None,
    precomputed_proposals: Sequence[DockingProposal] | None = None,
    precomputed_guided_receipt: GuidedPlacementReceipt | None = None,
    precomputed_provenance_receipt: (
        FixedSourceBoundConformerProposalReceipt
        | SourcePairedTorsionRescueProposalReceipt
        | None
    ) = None,
) -> GuidedPlacementSearchResult:
    supplied_precomputed_values = (
        precomputed_proposals is not None,
        precomputed_guided_receipt is not None,
        precomputed_provenance_receipt is not None,
    )
    if any(supplied_precomputed_values) and not all(supplied_precomputed_values):
        raise DockingAuthorityError(
            "precomputed guided proposals, receipt, and provenance must be "
            "supplied together"
        )
    if precomputed_proposals is None:
        proposals, receipt = generate_guided_docking_proposals(
            authenticated_problem,
            budget,
            context,
            receptor_system=receptor_system,
            ligand_system=ligand_system,
            policy=policy,
        )
    else:
        if policy is not None:
            raise DockingAuthorityError(
                "precomputed guided proposals reject a second policy"
            )
        if not isinstance(authenticated_problem, AuthenticatedDockingProblem):
            raise TypeError(
                "authenticated_problem must be AuthenticatedDockingProblem"
            )
        if not isinstance(budget, DockingBudget):
            raise TypeError("budget must be DockingBudget")
        if not isinstance(context, GuidedPlacementContext):
            raise TypeError("context must be GuidedPlacementContext")
        if not isinstance(precomputed_guided_receipt, GuidedPlacementReceipt):
            raise TypeError(
                "precomputed_guided_receipt must be GuidedPlacementReceipt"
            )
        if not isinstance(
            precomputed_provenance_receipt,
            (
                FixedSourceBoundConformerProposalReceipt,
                SourcePairedTorsionRescueProposalReceipt,
            ),
        ):
            raise TypeError(
                "precomputed_provenance_receipt must be "
                "FixedSourceBoundConformerProposalReceipt or "
                "SourcePairedTorsionRescueProposalReceipt"
            )
        authenticated_problem.input_receipt_sha256
        context.fingerprint_sha256
        receipt = precomputed_guided_receipt
        receipt.receipt_sha256
        provenance = precomputed_provenance_receipt
        provenance.receipt_sha256
        derived_context = build_guided_placement_context(
            authenticated_problem,
            receptor_system,
            ligand_system,
        )
        if (
            derived_context.fingerprint_sha256 != context.fingerprint_sha256
            or context.authority_input_receipt_sha256
            != authenticated_problem.input_receipt_sha256
            or receipt.authenticated_input_receipt_sha256
            != authenticated_problem.input_receipt_sha256
            or receipt.guidance_context_sha256 != context.fingerprint_sha256
            or receipt.budget_sha256 != _budget_sha256(budget)
            or dict(receipt.feature_counts) != context.feature_counts()
        ):
            raise DockingAuthorityError(
                "precomputed guided proposal authority is cross-wired"
            )
        proposals = tuple(precomputed_proposals)
        if len(proposals) != budget.candidate_count or any(
            not isinstance(proposal, DockingProposal) for proposal in proposals
        ):
            raise DockingAuthorityError(
                "precomputed guided proposal denominator is invalid"
            )
        for proposal_index, proposal in enumerate(proposals):
            proposal.assert_integrity()
            expected_candidate_id = _stable_candidate_id(
                proposal_index=proposal_index,
                seed=budget.seed,
                problem_fingerprint_sha256=(
                    authenticated_problem.problem.fingerprint_sha256
                ),
                search_space_fingerprint_sha256=(
                    authenticated_problem.search_space.fingerprint_sha256
                ),
            )
            if (
                proposal.proposal_index != proposal_index
                or proposal.seed != budget.seed
                or proposal.candidate_id != expected_candidate_id
                or proposal.problem_fingerprint_sha256
                != authenticated_problem.problem.fingerprint_sha256
                or proposal.search_space_fingerprint_sha256
                != authenticated_problem.search_space.fingerprint_sha256
                or proposal.refined
            ):
                raise DockingAuthorityError(
                    "precomputed guided proposal identity is invalid"
                )
        if tuple(
            proposal.fingerprint_sha256 for proposal in proposals
        ) != receipt.proposal_fingerprint_sha256s:
            raise DockingAuthorityError(
                "precomputed guided proposal fingerprints are cross-wired"
            )
        if isinstance(provenance, SourcePairedTorsionRescueProposalReceipt):
            expected_allocation = source_paired_torsion_rescue_allocation(
                authenticated_problem,
                context,
                budget,
                SourcePairedTorsionRescuePolicy(),
            )
            if provenance.allocation.allocation_sha256 != expected_allocation.allocation_sha256:
                raise DockingAuthorityError(
                    "precomputed torsion-rescue allocation is not its "
                    "authenticated deterministic derivation"
                )
        if (
            provenance.authenticated_input_receipt_sha256
            != authenticated_problem.input_receipt_sha256
            or provenance.budget_sha256 != _budget_sha256(budget)
            or provenance.source_ligand_system_sha256
            != canonical_system_sha256(ligand_system)
            or provenance.source_ligand_topology_sha256
            != canonical_topology_sha256(ligand_system)
            or provenance.guided_receipt.receipt_sha256
            != receipt.receipt_sha256
            or provenance.candidate_ids
            != tuple(proposal.candidate_id for proposal in proposals)
            or provenance.proposal_fingerprint_sha256s
            != tuple(proposal.fingerprint_sha256 for proposal in proposals)
            or provenance.proposal_coordinate_fingerprint_sha256s
            != tuple(
                proposal.coordinate_fingerprint_sha256
                for proposal in proposals
            )
            or provenance.proposal_torsion_metadata_sha256s
            != tuple(
                _torsion_metadata_sha256(proposal.torsion_angles)
                for proposal in proposals
            )
        ):
            raise DockingAuthorityError(
                "precomputed guided proposal provenance is cross-wired"
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
    "FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT",
    "FIXED_SOURCE_BOUND_CONFORMER_CENTERED_COUNT",
    "FIXED_SOURCE_BOUND_CONFORMER_LINEAGE_SCHEMA_ID",
    "FIXED_SOURCE_BOUND_CONFORMER_PROFILE_ID",
    "FIXED_SOURCE_BOUND_CONFORMER_PROFILE_SCHEMA_ID",
    "FIXED_SOURCE_BOUND_CONFORMER_RECEIPT_SCHEMA_ID",
    "FIXED_SOURCE_BOUND_CONFORMER_SOURCE_START",
    "FIXED_SOURCE_BOUND_CONFORMER_TORSION_METADATA_SCHEMA_ID",
    "FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT",
    "FIXED_SOURCE_BOUND_CONFORMER_VARIANT_START",
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
    "MAX_MULTI_ANCHOR_MATCHES_PER_LANE",
    "MAX_UNIFORM_TORSION_RESCUE_VARIANTS",
    "MULTI_ANCHOR_MODE",
    "POCKET_CENTER_BASELINE_MODE",
    "SOURCE_PAIRED_TORSION_RESCUE_ALLOCATION_SCHEMA_ID",
    "SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT",
    "SOURCE_PAIRED_TORSION_RESCUE_GUIDED_RECEIPT_SCHEMA_ID",
    "SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_RECEIPT_SCHEMA_ID",
    "SOURCE_PAIRED_TORSION_RESCUE_POLICY_ID",
    "SOURCE_PAIRED_TORSION_RESCUE_POLICY_SCHEMA_ID",
    "UNIFORM_FALLBACK_MODE",
    "UNIFORM_V3_ENSEMBLE_MODE",
    "UNIFORM_TORSION_RESCUE_VARIANT_MODE",
    "FixedSourceBoundConformerLineageRow",
    "FixedSourceBoundConformerProposalReceipt",
    "GuidedPlacementContext",
    "GuidedPlacementPolicy",
    "GuidedPlacementReceipt",
    "GuidedPlacementSearchResult",
    "SourcePairedTorsionRescueAllocation",
    "SourcePairedTorsionRescuePolicy",
    "SourcePairedTorsionRescueProposalReceipt",
    "build_guided_placement_context",
    "fixed_source_bound_conformer_profile_document",
    "fixed_source_bound_conformer_proposal_indices",
    "generate_fixed_source_bound_conformer_docking_proposals",
    "generate_guided_docking_proposals",
    "generate_source_paired_torsion_rescue_docking_proposals",
    "run_authenticated_guided_placement_search",
    "source_paired_torsion_rescue_allocation",
    "uniform_v3_ensemble_proposal_indices",
]
