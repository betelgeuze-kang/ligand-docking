"""Authoritative construction for bounded known-pocket docking.

This module turns canonical receptor, ligand, and pocket objects into one
cross-wired docking contract.  It derives the torsion forest, exclusions,
reference geometry, receptor pocket subset, and bounded validity context rather
than accepting those values independently from a caller.

The current derivation is deliberately conservative:

* one float64 CPU model is selected from each molecular system;
* the ligand must be one connected component;
* ordinary ring systems are retained as rigid components;
* macrocycles remain outside the supported lane;
* rotor candidates are ring-external, non-terminal heavy-atom single bonds
  without declared stereo, restricted functional groups, or bounded
  conjugation markers;
* chirality covers only non-degenerate degree-four centers;
* the receptor subset is bounded to atoms near the supplied spherical pocket;
* the frozen public-redocking geometric validity policy is reused as an
  immutable baseline.

These are software authority and provenance contracts.  They are not general
ligand preparation, chemically validated rotor perception, pocket prediction,
pose-scoring calibration, benchmark validation, or product qualification.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import importlib
import json
import math
import re
from types import MappingProxyType
from typing import Any

import torch

from betelgeuze_engine_v2.ai import torsion_tree_forward_kinematics
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_coordinates_sha256,
    canonical_system_sha256,
    require_valid_all_atom_system,
)

from .identity import DockingProblemIdentity, coordinate_fingerprint
from .proposals import DockingBudget, TorsionSearchSpace
from .search import (
    DockingPoseRefiner,
    DockingPoseScorer,
    DockingSearchResult,
    run_bounded_docking_search,
)
from .validity import PoseValidityConfig, PoseValidityContext


AUTHENTICATED_DOCKING_INPUT_SCHEMA_ID = (
    "betelgeuze.engine_v2_authenticated_docking_input/1.0.0"
)
AUTHENTICATED_DOCKING_SEARCH_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_authenticated_docking_search_result/1.0.0"
)
POCKET_DEFINITION_SCHEMA_ID = "betelgeuze.engine_v2_pocket_definition/1.0.0"
TORSION_SEARCH_SPACE_DERIVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_torsion_search_space_derivation/3.0.0"
)
AUTHENTICATED_DOCKING_DERIVATION_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_authenticated_docking_derivation_policy/3.0.0"
)
AUTHENTICATED_DOCKING_DERIVATION_ID = (
    "betelgeuze.engine_v2_known_pocket_docking_derivation/3.0.0"
)
TORSION_FOREST_ALGORITHM_ID = (
    "betelgeuze.engine_v2_sorted_breadth_first_acyclic_forest/1.0.0"
)
ROTOR_SELECTION_POLICY_ID = (
    "betelgeuze.engine_v2_chemistry_aware_heavy_single_rotor/3.0.0"
)
RING_SYSTEM_POLICY_ID = (
    "betelgeuze.engine_v2_rigid_ring_system_bridge_analysis/1.0.0"
)
LOCAL_COORDINATE_POLICY_ID = (
    "betelgeuze.engine_v2_parent_frame_bond_offsets/1.0.0"
)
RECEPTOR_SUBSET_POLICY_ID = (
    "betelgeuze.engine_v2_spherical_pocket_plus_margin_subset/1.0.0"
)
AUTHENTICATED_DOCKING_MAX_LIGAND_ATOMS = 512
AUTHENTICATED_DOCKING_MAX_LIGAND_BONDS = 2_048
AUTHENTICATED_DOCKING_MAX_RECEPTOR_ATOMS = 200_000
AUTHENTICATED_DOCKING_MAX_POCKET_RADIUS_ANGSTROM = 100.0
AUTHENTICATED_DOCKING_MAX_RECEPTOR_MARGIN_ANGSTROM = 20.0
AUTHENTICATED_DOCKING_ZERO_TORSION_TOLERANCE_ANGSTROM = 1.0e-10
AUTHENTICATED_DOCKING_MACROCYCLE_MIN_RING_ATOMS = 12

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/+@-]{1,256}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UNDECLARED_BOND_STEREO = frozenset({"none", "unspecified"})
_ROTOR_BOND_DISPOSITIONS = frozenset(
    {
        "rotatable",
        "ring_bond",
        "aromatic_bond",
        "non_single_bond",
        "stereo_constrained_bond",
        "hydrogen_bond",
        "terminal_heavy_atom",
        "amide",
        "urea",
        "carbamate",
        "sulfonamide",
        "conjugated_bond",
    }
)


class DockingAuthorityError(ValueError):
    """Authoritative docking input construction failed closed."""


class DockingScope(str, Enum):
    KNOWN_POCKET = "known_pocket_docking"
    REDOCKING = "known_reference_pocket_redocking"


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise DockingAuthorityError(
            "authoritative docking state is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _safe_id(value: object, *, name: str) -> str:
    text = str(value or "").strip()
    if _SAFE_ID_RE.fullmatch(text) is None:
        raise DockingAuthorityError(f"{name} must be a safe identifier")
    return text


def _digest(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if _SHA256_RE.fullmatch(text) is None:
        raise DockingAuthorityError(f"{name} must be a lowercase SHA-256")
    return text


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise DockingAuthorityError(
            f"{name} must be an integer in [{minimum},{maximum}]"
        )
    return value


def _freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DockingAuthorityError("authority metadata floats must be finite")
        return float(value)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            text = str(key)
            if text in result:
                raise DockingAuthorityError("authority metadata keys are duplicated")
            result[text] = _freeze_json(item)
        return MappingProxyType(result)
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_json(item) for item in value)
    raise DockingAuthorityError(
        "authority metadata must contain canonical JSON-compatible values"
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _frozen_vector3(value: torch.Tensor, *, name: str) -> torch.Tensor:
    if not isinstance(value, torch.Tensor) or value.shape != (3,):
        raise DockingAuthorityError(f"{name} must be a tensor with shape [3]")
    if not value.is_floating_point() or value.device.type != "cpu":
        raise DockingAuthorityError(f"{name} must be a CPU floating tensor")
    result = value.detach().to(dtype=torch.float64, device="cpu").clone().contiguous()
    if not bool(torch.isfinite(result).all().item()):
        raise DockingAuthorityError(f"{name} must be finite")
    return result


def _frame(
    system: AllAtomSystem,
    *,
    model_index: int,
    name: str,
) -> torch.Tensor:
    if not isinstance(system, AllAtomSystem):
        raise TypeError(f"{name} must be AllAtomSystem")
    if hasattr(system, "assert_integrity"):
        system.assert_integrity()
    require_valid_all_atom_system(system)
    index = _exact_int(
        model_index,
        name=f"{name}_model_index",
        minimum=0,
        maximum=system.model_count - 1,
    )
    if system.coordinates.device.type != "cpu" or system.coordinates.dtype != torch.float64:
        raise DockingAuthorityError(
            f"{name} must use CPU float64 coordinates"
        )
    coordinates = system.coordinates[index].detach().clone().contiguous()
    if not bool(torch.isfinite(coordinates).all().item()):
        raise DockingAuthorityError(f"{name} coordinates must be finite")
    return coordinates


def _tensor_hex_rows(value: torch.Tensor) -> list[list[str]]:
    tensor = value.detach().to(dtype=torch.float64, device="cpu").contiguous()
    return [
        [float(component).hex() for component in row]
        for row in tensor.tolist()
    ]


def _molecular_identity_functions():
    molecular = importlib.import_module("betelgeuze_engine_v2.molecular")
    required = (
        "chemical_graph_sha256",
        "indexed_topology_sha256",
        "source_bound_topology_sha256",
    )
    if not all(hasattr(molecular, name) for name in required):
        raise DockingAuthorityError(
            "round-three molecular identity contracts are not installed"
        )
    return tuple(getattr(molecular, name) for name in required)


@dataclass(frozen=True, slots=True)
class PocketDefinition:
    scope: DockingScope | str
    method_id: str
    method_version: str
    coordinate_frame_id: str
    center: torch.Tensor
    radius_angstrom: float
    source_artifact_sha256: str
    implementation_source_sha256: str
    metadata: Mapping[str, object] = field(default_factory=dict)
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            scope = (
                self.scope
                if isinstance(self.scope, DockingScope)
                else DockingScope(str(self.scope))
            )
        except ValueError as exc:
            raise DockingAuthorityError("unsupported docking scope") from exc
        method = _safe_id(self.method_id, name="pocket method_id")
        version = _safe_id(self.method_version, name="pocket method_version")
        frame = _safe_id(
            self.coordinate_frame_id,
            name="pocket coordinate_frame_id",
        )
        center = _frozen_vector3(self.center, name="pocket center")
        radius = float(self.radius_angstrom)
        if (
            not math.isfinite(radius)
            or radius <= 0.0
            or radius > AUTHENTICATED_DOCKING_MAX_POCKET_RADIUS_ANGSTROM
        ):
            raise DockingAuthorityError(
                "pocket radius is outside the bounded positive range"
            )
        source = _digest(
            self.source_artifact_sha256,
            name="pocket source artifact",
        )
        implementation = _digest(
            self.implementation_source_sha256,
            name="pocket implementation source",
        )
        metadata = _freeze_json(dict(self.metadata))
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "method_id", method)
        object.__setattr__(self, "method_version", version)
        object.__setattr__(self, "coordinate_frame_id", frame)
        object.__setattr__(self, "center", center)
        object.__setattr__(self, "radius_angstrom", radius)
        object.__setattr__(self, "source_artifact_sha256", source)
        object.__setattr__(self, "implementation_source_sha256", implementation)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(
            self,
            "_fingerprint_sha256",
            _sha256(self._identity_projection()),
        )

    def _identity_projection(self) -> dict[str, object]:
        return {
            "schema_id": POCKET_DEFINITION_SCHEMA_ID,
            "scope": self.scope.value,
            "shape": "sphere",
            "method_id": self.method_id,
            "method_version": self.method_version,
            "coordinate_frame_id": self.coordinate_frame_id,
            "center_binary64_hex": [float(value).hex() for value in self.center.tolist()],
            "radius_angstrom_binary64_hex": self.radius_angstrom.hex(),
            "source_artifact_sha256": self.source_artifact_sha256,
            "implementation_source_sha256": self.implementation_source_sha256,
            "metadata": _thaw_json(self.metadata),
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._identity_projection())
        if observed != self._fingerprint_sha256:
            raise DockingAuthorityError("pocket definition changed after construction")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._identity_projection(),
            "center_angstrom": [float(value) for value in self.center.tolist()],
            "radius_angstrom": self.radius_angstrom,
            "fingerprint_sha256": self.fingerprint_sha256,
            "scientifically_validated": False,
            "claim_safe": False,
        }


@dataclass(frozen=True, slots=True)
class TorsionSearchSpaceDerivationReceipt:
    ligand_chemical_graph_sha256: str
    ligand_indexed_topology_sha256: str
    ligand_source_bound_topology_sha256: str
    ligand_coordinates_sha256: str
    selected_model_coordinate_sha256: str
    model_index: int
    atom_count: int
    bond_count: int
    root_atom_indices: tuple[int, ...]
    rotatable_child_atom_indices: tuple[int, ...]
    rotor_bond_dispositions: tuple[tuple[int, int, str], ...]
    ring_bond_pairs: tuple[tuple[int, int], ...]
    rigid_ring_system_atom_indices: tuple[tuple[int, ...], ...]
    maximum_ring_system_atom_count: int
    maximum_ring_cycle_size: int
    search_space_fingerprint_sha256: str
    zero_torsion_coordinate_sha256: str
    derivation_policy_sha256: str
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for field_name in (
            "ligand_chemical_graph_sha256",
            "ligand_indexed_topology_sha256",
            "ligand_source_bound_topology_sha256",
            "ligand_coordinates_sha256",
            "selected_model_coordinate_sha256",
            "search_space_fingerprint_sha256",
            "zero_torsion_coordinate_sha256",
            "derivation_policy_sha256",
        ):
            object.__setattr__(
                self,
                field_name,
                _digest(getattr(self, field_name), name=field_name),
            )
        model_index = _exact_int(
            self.model_index,
            name="model_index",
            minimum=0,
            maximum=AUTHENTICATED_DOCKING_MAX_LIGAND_ATOMS,
        )
        atom_count = _exact_int(
            self.atom_count,
            name="atom_count",
            minimum=1,
            maximum=AUTHENTICATED_DOCKING_MAX_LIGAND_ATOMS,
        )
        bond_count = _exact_int(
            self.bond_count,
            name="bond_count",
            minimum=0,
            maximum=AUTHENTICATED_DOCKING_MAX_LIGAND_BONDS,
        )
        roots = tuple(int(value) for value in self.root_atom_indices)
        rotors = tuple(int(value) for value in self.rotatable_child_atom_indices)
        dispositions: list[tuple[int, int, str]] = []
        for row in self.rotor_bond_dispositions:
            if not isinstance(row, (tuple, list)) or len(row) != 3:
                raise DockingAuthorityError(
                    "rotor bond dispositions must be three-field rows"
                )
            dispositions.append(
                (int(row[0]), int(row[1]), str(row[2]).strip())
            )
        rotor_bond_dispositions = tuple(dispositions)
        ring_bonds = tuple(
            tuple(int(value) for value in pair)
            for pair in self.ring_bond_pairs
        )
        ring_systems = tuple(
            tuple(int(value) for value in system)
            for system in self.rigid_ring_system_atom_indices
        )
        if roots != tuple(sorted(set(roots))) or any(
            not 0 <= value < atom_count for value in roots
        ):
            raise DockingAuthorityError("root atom indices are invalid")
        if rotors != tuple(sorted(set(rotors))) or any(
            not 0 <= value < atom_count for value in rotors
        ):
            raise DockingAuthorityError("rotatable child indices are invalid")
        if not roots:
            raise DockingAuthorityError("search-space receipt requires a root")
        disposition_pairs = tuple(
            (first, second)
            for first, second, _ in rotor_bond_dispositions
        )
        if (
            rotor_bond_dispositions != tuple(sorted(rotor_bond_dispositions))
            or len(disposition_pairs) != len(set(disposition_pairs))
            or len(rotor_bond_dispositions) != bond_count
            or any(
                first >= second
                or not 0 <= first < atom_count
                or not 0 <= second < atom_count
                or disposition not in _ROTOR_BOND_DISPOSITIONS
                for first, second, disposition in rotor_bond_dispositions
            )
        ):
            raise DockingAuthorityError("rotor bond dispositions are invalid")
        if sum(
            disposition == "rotatable"
            for _, _, disposition in rotor_bond_dispositions
        ) != len(rotors):
            raise DockingAuthorityError(
                "rotatable bond dispositions and child indices disagree"
            )
        if ring_bonds != tuple(sorted(set(ring_bonds))) or any(
            len(pair) != 2
            or pair[0] >= pair[1]
            or not 0 <= pair[0] < atom_count
            or not 0 <= pair[1] < atom_count
            for pair in ring_bonds
        ):
            raise DockingAuthorityError("ring bond pairs are invalid")
        if ring_systems != tuple(sorted(set(ring_systems))) or any(
            system != tuple(sorted(set(system)))
            or len(system) < 3
            or any(not 0 <= value < atom_count for value in system)
            for system in ring_systems
        ):
            raise DockingAuthorityError("rigid ring systems are invalid")
        flattened_ring_atoms = tuple(
            value for system in ring_systems for value in system
        )
        if len(flattened_ring_atoms) != len(set(flattened_ring_atoms)):
            raise DockingAuthorityError(
                "rigid ring systems must be atom-disjoint"
            )
        ring_atoms = set(flattened_ring_atoms)
        bonded_ring_atoms = {
            value for pair in ring_bonds for value in pair
        }
        if ring_atoms != bonded_ring_atoms:
            raise DockingAuthorityError(
                "ring bonds and rigid ring systems must cover the same atoms"
            )
        ring_system_by_atom = {
            value: system_index
            for system_index, system in enumerate(ring_systems)
            for value in system
        }
        if any(
            ring_system_by_atom[first] != ring_system_by_atom[second]
            for first, second in ring_bonds
        ):
            raise DockingAuthorityError(
                "ring bonds cannot cross rigid ring systems"
            )
        disposition_by_pair = {
            (first, second): disposition
            for first, second, disposition in rotor_bond_dispositions
        }
        if any(
            disposition_by_pair.get(pair) != "ring_bond"
            for pair in ring_bonds
        ) or any(
            disposition == "ring_bond" and (first, second) not in ring_bonds
            for first, second, disposition in rotor_bond_dispositions
        ):
            raise DockingAuthorityError(
                "ring topology and rotor dispositions are cross-wired"
            )
        maximum_ring_cycle_size = _exact_int(
            self.maximum_ring_cycle_size,
            name="maximum_ring_cycle_size",
            minimum=0,
            maximum=AUTHENTICATED_DOCKING_MACROCYCLE_MIN_RING_ATOMS - 1,
        )
        if bool(ring_bonds) != bool(maximum_ring_cycle_size):
            raise DockingAuthorityError(
                "ring cycle size must agree with retained ring bonds"
            )
        maximum_ring_system_atom_count = _exact_int(
            self.maximum_ring_system_atom_count,
            name="maximum_ring_system_atom_count",
            minimum=0,
            maximum=AUTHENTICATED_DOCKING_MACROCYCLE_MIN_RING_ATOMS - 1,
        )
        expected_maximum_ring_system_atom_count = (
            max(len(system) for system in ring_systems)
            if ring_systems
            else 0
        )
        if (
            maximum_ring_system_atom_count
            != expected_maximum_ring_system_atom_count
        ):
            raise DockingAuthorityError(
                "maximum ring-system atom count is cross-wired"
            )
        if ring_systems and maximum_ring_cycle_size > max(
            len(system) for system in ring_systems
        ):
            raise DockingAuthorityError(
                "ring cycle size exceeds its rigid ring system"
            )
        object.__setattr__(self, "model_index", model_index)
        object.__setattr__(self, "atom_count", atom_count)
        object.__setattr__(self, "bond_count", bond_count)
        object.__setattr__(self, "root_atom_indices", roots)
        object.__setattr__(self, "rotatable_child_atom_indices", rotors)
        object.__setattr__(
            self,
            "rotor_bond_dispositions",
            rotor_bond_dispositions,
        )
        object.__setattr__(self, "ring_bond_pairs", ring_bonds)
        object.__setattr__(
            self,
            "rigid_ring_system_atom_indices",
            ring_systems,
        )
        object.__setattr__(
            self,
            "maximum_ring_system_atom_count",
            maximum_ring_system_atom_count,
        )
        object.__setattr__(
            self,
            "maximum_ring_cycle_size",
            maximum_ring_cycle_size,
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": TORSION_SEARCH_SPACE_DERIVATION_SCHEMA_ID,
            "derivation_id": AUTHENTICATED_DOCKING_DERIVATION_ID,
            "forest_algorithm_id": TORSION_FOREST_ALGORITHM_ID,
            "rotor_selection_policy_id": ROTOR_SELECTION_POLICY_ID,
            "local_coordinate_policy_id": LOCAL_COORDINATE_POLICY_ID,
            "ligand_chemical_graph_sha256": self.ligand_chemical_graph_sha256,
            "ligand_indexed_topology_sha256": self.ligand_indexed_topology_sha256,
            "ligand_source_bound_topology_sha256": (
                self.ligand_source_bound_topology_sha256
            ),
            "ligand_coordinates_sha256": self.ligand_coordinates_sha256,
            "selected_model_coordinate_sha256": (
                self.selected_model_coordinate_sha256
            ),
            "model_index": self.model_index,
            "atom_count": self.atom_count,
            "bond_count": self.bond_count,
            "root_atom_indices": list(self.root_atom_indices),
            "rotatable_child_atom_indices": list(
                self.rotatable_child_atom_indices
            ),
            "rotor_bond_dispositions": [
                {
                    "atom_indices": [first, second],
                    "disposition": disposition,
                }
                for first, second, disposition in self.rotor_bond_dispositions
            ],
            "ring_bond_pairs": [
                list(pair) for pair in self.ring_bond_pairs
            ],
            "rigid_ring_system_atom_indices": [
                list(system)
                for system in self.rigid_ring_system_atom_indices
            ],
            "maximum_ring_system_atom_count": (
                self.maximum_ring_system_atom_count
            ),
            "maximum_ring_cycle_size": self.maximum_ring_cycle_size,
            "search_space_fingerprint_sha256": (
                self.search_space_fingerprint_sha256
            ),
            "zero_torsion_coordinate_sha256": (
                self.zero_torsion_coordinate_sha256
            ),
            "derivation_policy_sha256": self.derivation_policy_sha256,
            "connected_ligand_required": True,
            "acyclic_ligand_required": False,
            "ring_closure_supported": True,
            "ring_closure_sampling_supported": False,
            "ring_systems_retained_as_rigid_components": True,
            "macrocycle_min_ring_atoms": (
                AUTHENTICATED_DOCKING_MACROCYCLE_MIN_RING_ATOMS
            ),
            "macrocycle_supported": False,
            "chemistry_aware_rotor_rules_applied": True,
            "rotor_perception_chemically_validated": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingAuthorityError(
                "search-space derivation receipt changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class AuthenticatedDockingProblem:
    problem: DockingProblemIdentity
    pocket: PocketDefinition
    search_space: TorsionSearchSpace
    search_space_receipt: TorsionSearchSpaceDerivationReceipt
    validity_context: PoseValidityContext
    receptor_atom_indices: tuple[int, ...]
    receptor_model_index: int
    ligand_model_index: int
    authority_policy_sha256: str
    receptor_system_sha256: str
    ligand_system_sha256: str
    _input_receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.problem, DockingProblemIdentity):
            raise TypeError("problem must be DockingProblemIdentity")
        if not isinstance(self.pocket, PocketDefinition):
            raise TypeError("pocket must be PocketDefinition")
        if not isinstance(self.search_space, TorsionSearchSpace):
            raise TypeError("search_space must be TorsionSearchSpace")
        if not isinstance(
            self.search_space_receipt,
            TorsionSearchSpaceDerivationReceipt,
        ):
            raise TypeError(
                "search_space_receipt must be TorsionSearchSpaceDerivationReceipt"
            )
        if not isinstance(self.validity_context, PoseValidityContext):
            raise TypeError("validity_context must be PoseValidityContext")
        receptor_sha = _digest(
            self.receptor_system_sha256,
            name="receptor_system_sha256",
        )
        ligand_sha = _digest(
            self.ligand_system_sha256,
            name="ligand_system_sha256",
        )
        policy_sha = _digest(
            self.authority_policy_sha256,
            name="authority_policy_sha256",
        )
        receptor_model_index = _exact_int(
            self.receptor_model_index,
            name="receptor_model_index",
            minimum=0,
            maximum=AUTHENTICATED_DOCKING_MAX_RECEPTOR_ATOMS,
        )
        ligand_model_index = _exact_int(
            self.ligand_model_index,
            name="ligand_model_index",
            minimum=0,
            maximum=AUTHENTICATED_DOCKING_MAX_LIGAND_ATOMS,
        )
        if ligand_model_index != self.search_space_receipt.model_index:
            raise DockingAuthorityError(
                "ligand model index and search-space receipt are cross-wired"
            )
        if self.problem.receptor_system_sha256 != receptor_sha:
            raise DockingAuthorityError("problem receptor identity is cross-wired")
        if self.problem.ligand_system_sha256 != ligand_sha:
            raise DockingAuthorityError("problem ligand identity is cross-wired")
        if self.problem.pocket_definition_sha256 != self.pocket.fingerprint_sha256:
            raise DockingAuthorityError("problem pocket identity is cross-wired")
        if self.problem.coordinate_frame_id != self.pocket.coordinate_frame_id:
            raise DockingAuthorityError("problem coordinate frame is cross-wired")
        if (
            self.search_space.fingerprint_sha256
            != self.search_space_receipt.search_space_fingerprint_sha256
        ):
            raise DockingAuthorityError("search-space receipt is cross-wired")
        if (
            self.validity_context.problem_fingerprint_sha256
            != self.problem.fingerprint_sha256
        ):
            raise DockingAuthorityError("validity context is cross-wired")
        receptor_indices = tuple(int(value) for value in self.receptor_atom_indices)
        if receptor_indices != tuple(sorted(set(receptor_indices))) or not receptor_indices:
            raise DockingAuthorityError("receptor atom subset is invalid")
        object.__setattr__(self, "receptor_atom_indices", receptor_indices)
        object.__setattr__(self, "receptor_system_sha256", receptor_sha)
        object.__setattr__(self, "ligand_system_sha256", ligand_sha)
        object.__setattr__(self, "authority_policy_sha256", policy_sha)
        object.__setattr__(self, "receptor_model_index", receptor_model_index)
        object.__setattr__(self, "ligand_model_index", ligand_model_index)
        object.__setattr__(
            self,
            "_input_receipt_sha256",
            _sha256(self._projection()),
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": AUTHENTICATED_DOCKING_INPUT_SCHEMA_ID,
            "scope": self.pocket.scope.value,
            "problem_fingerprint_sha256": self.problem.fingerprint_sha256,
            "receptor_system_sha256": self.receptor_system_sha256,
            "ligand_system_sha256": self.ligand_system_sha256,
            "pocket_definition_sha256": self.pocket.fingerprint_sha256,
            "search_space_fingerprint_sha256": self.search_space.fingerprint_sha256,
            "search_space_derivation_receipt_sha256": (
                self.search_space_receipt.receipt_sha256
            ),
            "validity_context_fingerprint_sha256": (
                self.validity_context.fingerprint_sha256
            ),
            "validity_policy_sha256": self.validity_context.config.fingerprint_sha256,
            "receptor_atom_indices": list(self.receptor_atom_indices),
            "receptor_model_index": self.receptor_model_index,
            "ligand_model_index": self.ligand_model_index,
            "authority_policy_sha256": self.authority_policy_sha256,
            "caller_supplied_receptor_coordinates_allowed": False,
            "caller_supplied_ligand_reference_coordinates_allowed": False,
            "caller_supplied_exclusions_allowed": False,
            "caller_supplied_chirality_allowed": False,
            "caller_supplied_search_space_allowed": False,
            "caller_supplied_validity_context_allowed": False,
            "chemically_validated": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def input_receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._input_receipt_sha256:
            raise DockingAuthorityError(
                "authenticated docking input changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "input_receipt_sha256": self.input_receipt_sha256,
            "pocket": self.pocket.to_dict(),
            "search_space_derivation": self.search_space_receipt.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class AuthenticatedDockingSearchResult:
    authenticated_input_receipt_sha256: str
    search_result: DockingSearchResult
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        authority = _digest(
            self.authenticated_input_receipt_sha256,
            name="authenticated_input_receipt_sha256",
        )
        if not isinstance(self.search_result, DockingSearchResult):
            raise TypeError("search_result must be DockingSearchResult")
        object.__setattr__(self, "authenticated_input_receipt_sha256", authority)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": AUTHENTICATED_DOCKING_SEARCH_RESULT_SCHEMA_ID,
            "authenticated_input_receipt_sha256": (
                self.authenticated_input_receipt_sha256
            ),
            "search_fingerprint_sha256": (
                self.search_result.search_fingerprint_sha256
            ),
            "problem_fingerprint_sha256": (
                self.search_result.problem_fingerprint_sha256
            ),
            "search_space_fingerprint_sha256": (
                self.search_result.search_space_fingerprint_sha256
            ),
            "validity_context_fingerprint_sha256": (
                self.search_result.validity_context_fingerprint_sha256
            ),
            "candidate_count": len(self.search_result.rows),
            "success_count": self.search_result.success_count,
            "failure_count": self.search_result.failure_count,
            "valid_pose_count": self.search_result.valid_pose_count,
            "scientifically_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingAuthorityError(
                "authenticated docking search result changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
            "search_result": self.search_result.to_dict(),
        }


def authenticated_docking_derivation_policy_document() -> dict[str, object]:
    projection: dict[str, object] = {
        "schema_id": AUTHENTICATED_DOCKING_DERIVATION_POLICY_SCHEMA_ID,
        "derivation_id": AUTHENTICATED_DOCKING_DERIVATION_ID,
        "supported_scopes": [
            DockingScope.KNOWN_POCKET.value,
            DockingScope.REDOCKING.value,
        ],
        "coordinate_policy": "selected_cpu_float64_model",
        "ligand_component_policy": "exactly_one_connected_component",
        "ring_policy": (
            "rigid_ring_systems_with_macrocycles_rejected"
        ),
        "ring_system_policy_id": RING_SYSTEM_POLICY_ID,
        "macrocycle_min_ring_atoms": (
            AUTHENTICATED_DOCKING_MACROCYCLE_MIN_RING_ATOMS
        ),
        "macrocycle_supported": False,
        "ring_closure_sampling_supported": False,
        "forest_algorithm_id": TORSION_FOREST_ALGORITHM_ID,
        "rotor_selection_policy_id": ROTOR_SELECTION_POLICY_ID,
        "rotor_bond_dispositions": sorted(_ROTOR_BOND_DISPOSITIONS),
        "rotor_disposition_recorded_for_every_bond": True,
        "local_coordinate_policy_id": LOCAL_COORDINATE_POLICY_ID,
        "receptor_subset_policy_id": RECEPTOR_SUBSET_POLICY_ID,
        "nonbonded_exclusions": "ligand_graph_distance_at_most_two",
        "chirality": "degree_four_nondegenerate_reference_signed_volume_subset",
        "validity_policy": "immutable_public_redocking_geometric_baseline",
        "caller_supplied_search_space_allowed": False,
        "caller_supplied_validity_context_allowed": False,
        "rotor_perception_chemically_validated": False,
        "pocket_prediction_performed": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    projection["policy_sha256"] = _sha256(projection)
    return projection


def _bond_pairs(system: AllAtomSystem) -> tuple[tuple[int, int], ...]:
    return tuple(
        sorted(
            {
                tuple(sorted((int(bond.atom_i), int(bond.atom_j))))
                for bond in system.bonds
            }
        )
    )


def _adjacency(system: AllAtomSystem) -> tuple[tuple[int, ...], ...]:
    rows = [set() for _ in range(system.atom_count)]
    for first, second in _bond_pairs(system):
        rows[first].add(second)
        rows[second].add(first)
    return tuple(tuple(sorted(row)) for row in rows)


@dataclass(frozen=True, slots=True)
class _RingTopology:
    ring_bond_pairs: tuple[tuple[int, int], ...]
    rigid_ring_system_atom_indices: tuple[tuple[int, ...], ...]
    maximum_ring_system_atom_count: int
    maximum_ring_cycle_size: int


def _bridge_bond_pairs(
    adjacency: tuple[tuple[int, ...], ...],
) -> set[tuple[int, int]]:
    """Return graph bridges using deterministic linear-time DFS."""

    discovery = [-1] * len(adjacency)
    low = [-1] * len(adjacency)
    parent = [-1] * len(adjacency)
    bridges: set[tuple[int, int]] = set()
    clock = 0

    def visit(node: int) -> None:
        nonlocal clock
        discovery[node] = clock
        low[node] = clock
        clock += 1
        for neighbor in adjacency[node]:
            if discovery[neighbor] < 0:
                parent[neighbor] = node
                visit(neighbor)
                low[node] = min(low[node], low[neighbor])
                if low[neighbor] > discovery[node]:
                    bridges.add(tuple(sorted((node, neighbor))))
            elif neighbor != parent[node]:
                low[node] = min(low[node], discovery[neighbor])

    for root in range(len(adjacency)):
        if discovery[root] < 0:
            visit(root)
    return bridges


def _shortest_cycle_size_for_bond(
    adjacency: tuple[tuple[int, ...], ...],
    bond_pair: tuple[int, int],
) -> int:
    first, second = bond_pair
    queue: deque[tuple[int, int]] = deque([(first, 0)])
    visited = {first}
    while queue:
        node, distance = queue.popleft()
        for neighbor in adjacency[node]:
            if tuple(sorted((node, neighbor))) == bond_pair:
                continue
            if neighbor == second:
                return distance + 2
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, distance + 1))
    raise DockingAuthorityError(
        "ring bond does not retain an alternate graph path"
    )


def _derive_ring_topology(
    system: AllAtomSystem,
    adjacency: tuple[tuple[int, ...], ...],
) -> _RingTopology:
    all_bonds = set(_bond_pairs(system))
    ring_bonds = tuple(sorted(all_bonds - _bridge_bond_pairs(adjacency)))
    if not ring_bonds:
        return _RingTopology((), (), 0, 0)

    ring_adjacency: dict[int, set[int]] = {}
    for first, second in ring_bonds:
        ring_adjacency.setdefault(first, set()).add(second)
        ring_adjacency.setdefault(second, set()).add(first)
    remaining = set(ring_adjacency)
    systems: list[tuple[int, ...]] = []
    while remaining:
        root = min(remaining)
        component: set[int] = set()
        queue: deque[int] = deque([root])
        while queue:
            node = queue.popleft()
            if node in component:
                continue
            component.add(node)
            queue.extend(sorted(ring_adjacency[node] - component))
        remaining -= component
        systems.append(tuple(sorted(component)))

    maximum_ring_system_atom_count = max(len(system) for system in systems)
    if (
        maximum_ring_system_atom_count
        >= AUTHENTICATED_DOCKING_MACROCYCLE_MIN_RING_ATOMS
    ):
        raise DockingAuthorityError(
            "authoritative torsion derivation conservatively rejects ring "
            "systems with "
            f"{AUTHENTICATED_DOCKING_MACROCYCLE_MIN_RING_ATOMS} or more atoms"
        )
    maximum_cycle_size = max(
        _shortest_cycle_size_for_bond(adjacency, pair)
        for pair in ring_bonds
    )
    return _RingTopology(
        ring_bond_pairs=ring_bonds,
        rigid_ring_system_atom_indices=tuple(sorted(systems)),
        maximum_ring_system_atom_count=maximum_ring_system_atom_count,
        maximum_ring_cycle_size=maximum_cycle_size,
    )


@dataclass(frozen=True, slots=True)
class _RotorPerception:
    rotatable_mask: torch.Tensor
    bond_dispositions: tuple[tuple[int, int, str], ...]


def _derive_rotor_perception(
    ligand_system: AllAtomSystem,
    *,
    parent: Sequence[int],
    ring_bond_pairs: Sequence[tuple[int, int]],
) -> _RotorPerception:
    atom_count = ligand_system.atom_count
    pair_to_bond = {
        tuple(sorted((int(bond.atom_i), int(bond.atom_j)))): bond
        for bond in ligand_system.bonds
    }
    incident_bonds: list[list[tuple[int, object]]] = [
        [] for _ in range(atom_count)
    ]
    for pair, bond in pair_to_bond.items():
        first, second = pair
        incident_bonds[first].append((second, bond))
        incident_bonds[second].append((first, bond))
    for rows in incident_bonds:
        rows.sort(key=lambda row: row[0])

    def element(atom_index: int) -> str:
        return ligand_system.atoms[atom_index].element.upper()

    def is_order(bond: object, expected: float) -> bool:
        return math.isclose(
            float(getattr(bond, "order")),
            expected,
            rel_tol=0.0,
            abs_tol=1.0e-6,
        )

    def double_oxygen_count(atom_index: int) -> int:
        return sum(
            element(neighbor) == "O" and is_order(bond, 2.0)
            for neighbor, bond in incident_bonds[atom_index]
        )

    def single_neighbor_elements(atom_index: int) -> tuple[str, ...]:
        return tuple(
            element(neighbor)
            for neighbor, bond in incident_bonds[atom_index]
            if is_order(bond, 1.0) and not bool(getattr(bond, "aromatic"))
        )

    def pi_center(atom_index: int) -> bool:
        atom = ligand_system.atoms[atom_index]
        return bool(atom.aromatic) or any(
            bool(getattr(bond, "aromatic"))
            or float(getattr(bond, "order")) > 1.0 + 1.0e-6
            for _, bond in incident_bonds[atom_index]
        )

    def neutral_lone_pair_center(atom_index: int) -> bool:
        atom = ligand_system.atoms[atom_index]
        return (
            element(atom_index) in {"N", "O", "S"}
            and int(atom.formal_charge) <= 0
        )

    def functional_disposition(first: int, second: int) -> str | None:
        for center, partner in ((first, second), (second, first)):
            center_element = element(center)
            partner_element = element(partner)
            if (
                center_element == "C"
                and double_oxygen_count(center) >= 1
            ):
                neighbor_elements = single_neighbor_elements(center)
                nitrogen_count = neighbor_elements.count("N")
                oxygen_count = neighbor_elements.count("O")
                if partner_element == "N":
                    if nitrogen_count >= 2:
                        return "urea"
                    if oxygen_count >= 1:
                        return "carbamate"
                    return "amide"
                if partner_element == "O" and nitrogen_count >= 1:
                    return "carbamate"
            if (
                center_element == "S"
                and partner_element == "N"
                and double_oxygen_count(center) >= 2
            ):
                return "sulfonamide"
        return None

    ring_bonds = set(ring_bond_pairs)
    heavy_degrees = tuple(
        sum(element(neighbor) != "H" for neighbor, _ in rows)
        for rows in incident_bonds
    )
    dispositions: list[tuple[int, int, str]] = []
    disposition_by_pair: dict[tuple[int, int], str] = {}
    for pair, bond in sorted(pair_to_bond.items()):
        first, second = pair
        stereo = str(getattr(bond, "stereo") or "none").strip().lower()
        if pair in ring_bonds:
            disposition = "ring_bond"
        elif bool(getattr(bond, "aromatic")):
            disposition = "aromatic_bond"
        elif not is_order(bond, 1.0):
            disposition = "non_single_bond"
        elif stereo not in _UNDECLARED_BOND_STEREO:
            disposition = "stereo_constrained_bond"
        elif element(first) == "H" or element(second) == "H":
            disposition = "hydrogen_bond"
        else:
            disposition = functional_disposition(first, second) or ""
            if not disposition and (
                (
                    pi_center(first)
                    and (
                        pi_center(second)
                        or neutral_lone_pair_center(second)
                    )
                )
                or (
                    pi_center(second)
                    and (
                        pi_center(first)
                        or neutral_lone_pair_center(first)
                    )
                )
            ):
                disposition = "conjugated_bond"
            if not disposition and (
                heavy_degrees[first] <= 1 or heavy_degrees[second] <= 1
            ):
                disposition = "terminal_heavy_atom"
            if not disposition:
                disposition = "rotatable"
        dispositions.append((first, second, disposition))
        disposition_by_pair[pair] = disposition

    rotatable = torch.zeros(atom_count, dtype=torch.bool)
    for child, ancestor in enumerate(parent):
        if ancestor < 0:
            continue
        pair = tuple(sorted((child, ancestor)))
        rotatable[child] = disposition_by_pair[pair] == "rotatable"
    return _RotorPerception(
        rotatable_mask=rotatable,
        bond_dispositions=tuple(dispositions),
    )


def _derive_exclusions(system: AllAtomSystem) -> tuple[tuple[int, int], ...]:
    adjacency = _adjacency(system)
    exclusions: set[tuple[int, int]] = set()
    for source in range(system.atom_count):
        frontier = {source}
        visited = {source}
        for _ in range(2):
            next_frontier: set[int] = set()
            for node in frontier:
                next_frontier.update(adjacency[node])
            next_frontier -= visited
            for target in next_frontier:
                exclusions.add(tuple(sorted((source, target))))
            visited.update(next_frontier)
            frontier = next_frontier
    return tuple(sorted(exclusions))


def _signed_volume(
    coordinates: torch.Tensor,
    center: int,
    first: int,
    second: int,
    third: int,
) -> float:
    origin = coordinates[center]
    return float(
        torch.dot(
            torch.cross(
                coordinates[first] - origin,
                coordinates[second] - origin,
                dim=0,
            ),
            coordinates[third] - origin,
        ).item()
    )


def _derive_chirality(
    system: AllAtomSystem,
    coordinates: torch.Tensor,
) -> tuple[tuple[int, int, int, int], ...]:
    adjacency = _adjacency(system)
    rows: list[tuple[int, int, int, int]] = []
    for center, neighbors in enumerate(adjacency):
        if len(neighbors) != 4:
            continue
        first, second, third = neighbors[:3]
        if abs(_signed_volume(coordinates, center, first, second, third)) <= 1.0e-8:
            continue
        rows.append((center, first, second, third))
    return tuple(rows)


def derive_authoritative_torsion_search_space(
    ligand_system: AllAtomSystem,
    *,
    model_index: int = 0,
) -> tuple[TorsionSearchSpace, TorsionSearchSpaceDerivationReceipt]:
    coordinates = _frame(
        ligand_system,
        model_index=model_index,
        name="ligand_system",
    )
    atom_count = ligand_system.atom_count
    bond_count = len(ligand_system.bonds)
    if atom_count > AUTHENTICATED_DOCKING_MAX_LIGAND_ATOMS:
        raise DockingAuthorityError("ligand atom count exceeds the authority bound")
    if bond_count > AUTHENTICATED_DOCKING_MAX_LIGAND_BONDS:
        raise DockingAuthorityError("ligand bond count exceeds the authority bound")
    adjacency = _adjacency(ligand_system)
    parent = [-2] * atom_count
    parent[0] = -1
    order: list[int] = []
    queue: deque[int] = deque([0])
    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in adjacency[node]:
            if parent[neighbor] == -2:
                parent[neighbor] = node
                queue.append(neighbor)
    if len(order) != atom_count:
        raise DockingAuthorityError(
            "authoritative docking requires one connected ligand component"
        )
    ring_topology = _derive_ring_topology(ligand_system, adjacency)
    parent_tensor = torch.tensor(parent, dtype=torch.long)
    local_offsets = torch.zeros((atom_count, 3), dtype=torch.float64)
    local_axes = torch.zeros((atom_count, 3), dtype=torch.float64)
    local_axes[:, 2] = 1.0
    for child, ancestor in enumerate(parent):
        if ancestor < 0:
            continue
        offset = coordinates[child] - coordinates[ancestor]
        norm = float(torch.linalg.vector_norm(offset).item())
        if not math.isfinite(norm) or norm <= 1.0e-12:
            raise DockingAuthorityError(
                "ligand tree contains a degenerate parent-child bond"
            )
        local_offsets[child] = offset
        local_axes[child] = offset / norm
    rotor_perception = _derive_rotor_perception(
        ligand_system,
        parent=parent,
        ring_bond_pairs=ring_topology.ring_bond_pairs,
    )
    rotatable = rotor_perception.rotatable_mask
    root_positions = coordinates[[0]].clone().contiguous()
    search_space = TorsionSearchSpace(
        local_offsets=local_offsets,
        parent=parent_tensor,
        local_axes=local_axes,
        rotatable_mask=rotatable,
        root_positions=root_positions,
    )
    reconstructed = torsion_tree_forward_kinematics(
        search_space.local_offsets,
        search_space.parent,
        torch.zeros(atom_count, dtype=torch.float64),
        local_axes=search_space.local_axes,
        root_positions=search_space.root_positions,
    ).coordinates
    maximum_error = float((reconstructed - coordinates).abs().max().item())
    if maximum_error > AUTHENTICATED_DOCKING_ZERO_TORSION_TOLERANCE_ANGSTROM:
        raise DockingAuthorityError(
            "derived torsion search space does not reproduce the selected ligand model"
        )
    chemical_graph_sha256, indexed_topology_sha256, source_bound_topology_sha256 = (
        _molecular_identity_functions()
    )
    policy = authenticated_docking_derivation_policy_document()
    receipt = TorsionSearchSpaceDerivationReceipt(
        ligand_chemical_graph_sha256=chemical_graph_sha256(ligand_system),
        ligand_indexed_topology_sha256=indexed_topology_sha256(ligand_system),
        ligand_source_bound_topology_sha256=source_bound_topology_sha256(
            ligand_system
        ),
        ligand_coordinates_sha256=canonical_coordinates_sha256(ligand_system),
        selected_model_coordinate_sha256=coordinate_fingerprint(coordinates),
        model_index=model_index,
        atom_count=atom_count,
        bond_count=bond_count,
        root_atom_indices=(0,),
        rotatable_child_atom_indices=tuple(
            int(index)
            for index in torch.nonzero(rotatable, as_tuple=False).reshape(-1).tolist()
        ),
        rotor_bond_dispositions=rotor_perception.bond_dispositions,
        ring_bond_pairs=ring_topology.ring_bond_pairs,
        rigid_ring_system_atom_indices=(
            ring_topology.rigid_ring_system_atom_indices
        ),
        maximum_ring_system_atom_count=(
            ring_topology.maximum_ring_system_atom_count
        ),
        maximum_ring_cycle_size=ring_topology.maximum_ring_cycle_size,
        search_space_fingerprint_sha256=search_space.fingerprint_sha256,
        zero_torsion_coordinate_sha256=coordinate_fingerprint(reconstructed),
        derivation_policy_sha256=str(policy["policy_sha256"]),
    )
    return search_space, receipt


def _receptor_subset(
    receptor_coordinates: torch.Tensor,
    *,
    pocket: PocketDefinition,
    margin_angstrom: float,
    ligand_atom_count: int,
    max_cross_checks: int,
) -> tuple[torch.Tensor, tuple[int, ...]]:
    margin = float(margin_angstrom)
    if (
        not math.isfinite(margin)
        or margin < 0.0
        or margin > AUTHENTICATED_DOCKING_MAX_RECEPTOR_MARGIN_ANGSTROM
    ):
        raise DockingAuthorityError("receptor subset margin is outside its hard bound")
    distances = torch.linalg.vector_norm(
        receptor_coordinates - pocket.center,
        dim=-1,
    )
    indices = torch.nonzero(
        distances <= pocket.radius_angstrom + margin,
        as_tuple=False,
    ).reshape(-1)
    if int(indices.numel()) < 1:
        raise DockingAuthorityError(
            "pocket has no receptor atoms within the bounded support radius"
        )
    maximum_receptor_atoms = min(
        AUTHENTICATED_DOCKING_MAX_RECEPTOR_ATOMS,
        max_cross_checks // max(1, ligand_atom_count),
    )
    if int(indices.numel()) > maximum_receptor_atoms:
        raise DockingAuthorityError(
            "pocket-local receptor subset exceeds the cross-check capacity"
        )
    canonical_indices = tuple(int(value) for value in indices.tolist())
    return receptor_coordinates[indices].clone().contiguous(), canonical_indices


def build_authenticated_known_pocket_docking_problem(
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    pocket: PocketDefinition,
    *,
    receptor_model_index: int = 0,
    ligand_model_index: int = 0,
    receptor_margin_angstrom: float = 4.0,
) -> AuthenticatedDockingProblem:
    if not isinstance(pocket, PocketDefinition):
        raise TypeError("pocket must be PocketDefinition")
    if receptor_system.atom_count > AUTHENTICATED_DOCKING_MAX_RECEPTOR_ATOMS:
        raise DockingAuthorityError("receptor atom count exceeds the authority bound")
    receptor_coordinates = _frame(
        receptor_system,
        model_index=receptor_model_index,
        name="receptor_system",
    )
    ligand_coordinates = _frame(
        ligand_system,
        model_index=ligand_model_index,
        name="ligand_system",
    )
    search_space, search_receipt = derive_authoritative_torsion_search_space(
        ligand_system,
        model_index=ligand_model_index,
    )
    from betelgeuze_engine_v2.stack_round1_hardening import (
        PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID,
    )

    validity_config = PoseValidityConfig(
        pocket_radius_angstrom=pocket.radius_angstrom,
        policy_id=PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID,
    )
    receptor_subset, receptor_indices = _receptor_subset(
        receptor_coordinates,
        pocket=pocket,
        margin_angstrom=receptor_margin_angstrom,
        ligand_atom_count=ligand_system.atom_count,
        max_cross_checks=validity_config.max_cross_checks,
    )
    policy = authenticated_docking_derivation_policy_document()
    receptor_sha = canonical_system_sha256(receptor_system)
    ligand_sha = canonical_system_sha256(ligand_system)
    problem = DockingProblemIdentity(
        receptor_system_sha256=receptor_sha,
        ligand_system_sha256=ligand_sha,
        pocket_definition_sha256=pocket.fingerprint_sha256,
        coordinate_frame_id=pocket.coordinate_frame_id,
        metadata={
            "scope": pocket.scope.value,
            "pocket_method_id": pocket.method_id,
            "pocket_method_version": pocket.method_version,
            "authority_policy_sha256": policy["policy_sha256"],
        },
    )
    validity_context = PoseValidityContext(
        problem_fingerprint_sha256=problem.fingerprint_sha256,
        reference_coordinates=ligand_coordinates,
        bond_pairs=_bond_pairs(ligand_system),
        excluded_nonbonded_pairs=_derive_exclusions(ligand_system),
        receptor_coordinates=receptor_subset,
        pocket_center=pocket.center,
        chirality_centers=_derive_chirality(ligand_system, ligand_coordinates),
        config=validity_config,
    )
    return AuthenticatedDockingProblem(
        problem=problem,
        pocket=pocket,
        search_space=search_space,
        search_space_receipt=search_receipt,
        validity_context=validity_context,
        receptor_atom_indices=receptor_indices,
        receptor_model_index=receptor_model_index,
        ligand_model_index=ligand_model_index,
        authority_policy_sha256=str(policy["policy_sha256"]),
        receptor_system_sha256=receptor_sha,
        ligand_system_sha256=ligand_sha,
    )


def run_authenticated_bounded_docking_search(
    authenticated_problem: AuthenticatedDockingProblem,
    budget: DockingBudget,
    scorer: DockingPoseScorer,
    *,
    refiner: DockingPoseRefiner | None = None,
    diversity_rmsd_angstrom: float = 0.5,
    diversity_metric: str = "direct_rmsd",
    symmetry_permutations: Sequence[Sequence[int] | torch.Tensor] | None = None,
) -> AuthenticatedDockingSearchResult:
    if not isinstance(authenticated_problem, AuthenticatedDockingProblem):
        raise TypeError(
            "authenticated_problem must be AuthenticatedDockingProblem"
        )
    authenticated_problem.input_receipt_sha256
    result = run_bounded_docking_search(
        authenticated_problem.search_space,
        budget,
        scorer,
        refiner=refiner,
        validity_context=authenticated_problem.validity_context,
        diversity_rmsd_angstrom=diversity_rmsd_angstrom,
        diversity_metric=diversity_metric,
        symmetry_permutations=symmetry_permutations,
        problem=authenticated_problem.problem,
        placement_center=authenticated_problem.pocket.center,
    )
    if result.problem_fingerprint_sha256 != authenticated_problem.problem.fingerprint_sha256:
        raise DockingAuthorityError("search result problem identity is cross-wired")
    if result.search_space_fingerprint_sha256 != authenticated_problem.search_space.fingerprint_sha256:
        raise DockingAuthorityError("search result search-space identity is cross-wired")
    if (
        result.validity_context_fingerprint_sha256
        != authenticated_problem.validity_context.fingerprint_sha256
    ):
        raise DockingAuthorityError("search result validity identity is cross-wired")
    return AuthenticatedDockingSearchResult(
        authenticated_input_receipt_sha256=(
            authenticated_problem.input_receipt_sha256
        ),
        search_result=result,
    )


__all__ = [
    "AUTHENTICATED_DOCKING_DERIVATION_ID",
    "AUTHENTICATED_DOCKING_DERIVATION_POLICY_SCHEMA_ID",
    "AUTHENTICATED_DOCKING_INPUT_SCHEMA_ID",
    "AUTHENTICATED_DOCKING_SEARCH_RESULT_SCHEMA_ID",
    "AUTHENTICATED_DOCKING_MAX_LIGAND_ATOMS",
    "AUTHENTICATED_DOCKING_MAX_LIGAND_BONDS",
    "AUTHENTICATED_DOCKING_MACROCYCLE_MIN_RING_ATOMS",
    "AUTHENTICATED_DOCKING_MAX_POCKET_RADIUS_ANGSTROM",
    "AUTHENTICATED_DOCKING_MAX_RECEPTOR_ATOMS",
    "AUTHENTICATED_DOCKING_MAX_RECEPTOR_MARGIN_ANGSTROM",
    "AuthenticatedDockingProblem",
    "AuthenticatedDockingSearchResult",
    "DockingAuthorityError",
    "DockingScope",
    "PocketDefinition",
    "RING_SYSTEM_POLICY_ID",
    "TorsionSearchSpaceDerivationReceipt",
    "authenticated_docking_derivation_policy_document",
    "build_authenticated_known_pocket_docking_problem",
    "derive_authoritative_torsion_search_space",
    "run_authenticated_bounded_docking_search",
]
