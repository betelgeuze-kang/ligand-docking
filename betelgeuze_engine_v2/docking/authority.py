"""Authoritative construction for bounded known-pocket docking.

This module turns canonical receptor, ligand, and pocket objects into one
cross-wired docking contract.  It derives the torsion forest, exclusions,
reference geometry, receptor pocket subset, and bounded validity context rather
than accepting those values independently from a caller.

The current derivation is deliberately conservative:

* one float64 CPU model is selected from each molecular system;
* the ligand must be one connected acyclic component;
* rotors are topology-only single, non-aromatic, non-terminal heavy-atom edges;
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
    "betelgeuze.engine_v2_torsion_search_space_derivation/1.0.0"
)
AUTHENTICATED_DOCKING_DERIVATION_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_authenticated_docking_derivation_policy/1.0.0"
)
AUTHENTICATED_DOCKING_DERIVATION_ID = (
    "betelgeuze.engine_v2_known_pocket_docking_derivation/1.0.0"
)
TORSION_FOREST_ALGORITHM_ID = (
    "betelgeuze.engine_v2_sorted_breadth_first_acyclic_forest/1.0.0"
)
ROTOR_SELECTION_POLICY_ID = (
    "betelgeuze.engine_v2_topology_only_nonterminal_heavy_single_rotor/1.0.0"
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

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/+@-]{1,256}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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
        object.__setattr__(self, "model_index", model_index)
        object.__setattr__(self, "atom_count", atom_count)
        object.__setattr__(self, "bond_count", bond_count)
        object.__setattr__(self, "root_atom_indices", roots)
        object.__setattr__(self, "rotatable_child_atom_indices", rotors)
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
            "search_space_fingerprint_sha256": (
                self.search_space_fingerprint_sha256
            ),
            "zero_torsion_coordinate_sha256": (
                self.zero_torsion_coordinate_sha256
            ),
            "derivation_policy_sha256": self.derivation_policy_sha256,
            "connected_ligand_required": True,
            "acyclic_ligand_required": True,
            "ring_closure_supported": False,
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
        "ring_policy": "reject_graph_cycles",
        "forest_algorithm_id": TORSION_FOREST_ALGORITHM_ID,
        "rotor_selection_policy_id": ROTOR_SELECTION_POLICY_ID,
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
    if bond_count != atom_count - 1:
        raise DockingAuthorityError(
            "authoritative torsion derivation does not support ring closure"
        )
    pair_to_bond = {
        tuple(sorted((int(bond.atom_i), int(bond.atom_j)))): bond
        for bond in ligand_system.bonds
    }
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
    subtree_size = [1] * atom_count
    for node in reversed(order):
        ancestor = parent[node]
        if ancestor >= 0:
            subtree_size[ancestor] += subtree_size[node]
    rotatable = torch.zeros(atom_count, dtype=torch.bool)
    for child, ancestor in enumerate(parent):
        if ancestor < 0:
            continue
        bond = pair_to_bond[tuple(sorted((child, ancestor)))]
        child_atom = ligand_system.atoms[child]
        parent_atom = ligand_system.atoms[ancestor]
        child_side = subtree_size[child]
        parent_side = atom_count - child_side
        rotatable[child] = bool(
            float(bond.order) == 1.0
            and not bool(bond.aromatic)
            and not str(bond.stereo or "")
            and child_atom.element.upper() != "H"
            and parent_atom.element.upper() != "H"
            and child_side > 1
            and parent_side > 1
        )
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
    "AUTHENTICATED_DOCKING_MAX_POCKET_RADIUS_ANGSTROM",
    "AUTHENTICATED_DOCKING_MAX_RECEPTOR_ATOMS",
    "AUTHENTICATED_DOCKING_MAX_RECEPTOR_MARGIN_ANGSTROM",
    "AuthenticatedDockingProblem",
    "AuthenticatedDockingSearchResult",
    "DockingAuthorityError",
    "DockingScope",
    "PocketDefinition",
    "TorsionSearchSpaceDerivationReceipt",
    "authenticated_docking_derivation_policy_document",
    "build_authenticated_known_pocket_docking_problem",
    "derive_authoritative_torsion_search_space",
    "run_authenticated_bounded_docking_search",
]
