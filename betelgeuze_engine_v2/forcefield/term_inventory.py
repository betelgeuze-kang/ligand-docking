"""Bounded linear-alkane topological term and pair inventory.

This module is a topology-only V2-2 contract for source-bound, explicit-H,
neutral linear alkanes with one through four carbon atoms.  It enumerates
canonical bonded identities, topological environment match keys, and every
unordered atom pair's shortest-path class.  It intentionally does not assign
force-field atom types, partial charges, parameters, 1-4 scale factors,
energies, forces, virials, or runtime authority.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import hashlib
from itertools import combinations
import json
from typing import Any

from betelgeuze_engine_v2.molecular.alkane_forcefield_applicability import (
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_ID,
    LinearAlkaneC1C4ForceFieldApplicabilityReport,
    analyze_linear_alkane_c1_c4_force_field_applicability,
)
from betelgeuze_engine_v2.molecular.bonded_inventory import (
    CanonicalAngleIdentity,
    CanonicalBondIdentity,
)
from betelgeuze_engine_v2.molecular.models import AllAtomSystem
from betelgeuze_engine_v2.molecular.serialization import (
    deserialize_all_atom_system,
    serialize_all_atom_system,
)

from .typing import (
    LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_ID,
    LinearAlkaneTopologicalEnvironmentTypingReport,
    analyze_linear_alkane_topological_environment_typing,
)


_FROZEN_SCHEMA_VERSION = "1.0.0"
_FROZEN_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_term_pair_inventory/"
    f"{_FROZEN_SCHEMA_VERSION}"
)
_FROZEN_PROFILE_ID = (
    "source_explicit_h_sdf_v2000_linear_alkane_c1_c4_topology_v1"
)
_FROZEN_CLAIM_SCOPE = (
    "bounded_topological_term_and_pair_classification_only"
)
_FROZEN_ENVIRONMENT_MATCH_POLICY_ID = (
    "linear_alkane_c1_c4_topological_environment_match_v1"
)
_FROZEN_PAIR_CLASSIFICATION_POLICY_ID = (
    "covalent_shortest_graph_distance_1_2_excluded_1_3_excluded_"
    "1_4_separate_farther_full_v1"
)
_FROZEN_IMPROPER_SELECTION_POLICY_ID = (
    "linear_alkane_c1_c4_selected_improper_empty_v1"
)
_FROZEN_CONSTRAINT_SELECTION_POLICY_ID = (
    "linear_alkane_c1_c4_unconstrained_diagnostic_empty_v1"
)
_FROZEN_INVENTORY_STATUSES = frozenset(
    {"invalid", "unsupported", "available"}
)
_FROZEN_PAIR_INTERACTION_CLASSES = (
    "excluded_1_2",
    "excluded_1_3",
    "one_four_separate",
    "full_nonbonded",
)
_FROZEN_APPLICABILITY_SCHEMA_ID = (
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_ID
)
_FROZEN_TYPING_SCHEMA_ID = (
    LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_ID
)

# These public names are compatibility labels.  Report semantics use the
# private import-time constants above so monkeypatching an export cannot
# redefine an existing versioned artifact.
LINEAR_ALKANE_TERM_PAIR_INVENTORY_SCHEMA_VERSION = _FROZEN_SCHEMA_VERSION
LINEAR_ALKANE_TERM_PAIR_INVENTORY_SCHEMA_ID = _FROZEN_SCHEMA_ID
LINEAR_ALKANE_TERM_PAIR_INVENTORY_PROFILE_ID = _FROZEN_PROFILE_ID
LINEAR_ALKANE_TERM_PAIR_INVENTORY_CLAIM_SCOPE = _FROZEN_CLAIM_SCOPE
LINEAR_ALKANE_ENVIRONMENT_MATCH_POLICY_ID = (
    _FROZEN_ENVIRONMENT_MATCH_POLICY_ID
)
LINEAR_ALKANE_PAIR_CLASSIFICATION_POLICY_ID = (
    _FROZEN_PAIR_CLASSIFICATION_POLICY_ID
)
LINEAR_ALKANE_IMPROPER_SELECTION_POLICY_ID = (
    _FROZEN_IMPROPER_SELECTION_POLICY_ID
)
LINEAR_ALKANE_CONSTRAINT_SELECTION_POLICY_ID = (
    _FROZEN_CONSTRAINT_SELECTION_POLICY_ID
)
LINEAR_ALKANE_TERM_PAIR_INVENTORY_STATUSES = _FROZEN_INVENTORY_STATUSES
LINEAR_ALKANE_PAIR_INTERACTION_CLASSES = _FROZEN_PAIR_INTERACTION_CLASSES

_MAX_JSON_INTEGER = (1 << 53) - 1
_ENUMERATED = "enumerated_from_canonical_graph"
_ENUMERATED_EMPTY = "enumerated_empty_by_policy"
_NOT_ENUMERATED = "not_enumerated"


def _require_atom_index(name: str, value: Any) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0 or value > _MAX_JSON_INTEGER:
        raise ValueError(
            f"{name} must be a non-negative interoperable JSON integer"
        )
    return value


def _require_environment_id(name: str, value: Any) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be a string")
    if not value or value.strip() != value or any(character.isspace() for character in value):
        raise ValueError(f"{name} must be a non-empty whitespace-free identifier")
    return value


def _canonical_json_bytes(document: dict[str, Any]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_document(document: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(document)).hexdigest()


@dataclass(frozen=True, order=True, slots=True)
class CanonicalProperTorsionIdentity:
    """One undirected length-three simple path, normalized by reversal."""

    atom_i: int
    atom_j: int
    atom_k: int
    atom_l: int

    def __post_init__(self) -> None:
        values = (
            _require_atom_index("atom_i", self.atom_i),
            _require_atom_index("atom_j", self.atom_j),
            _require_atom_index("atom_k", self.atom_k),
            _require_atom_index("atom_l", self.atom_l),
        )
        if len(set(values)) != 4:
            raise ValueError("canonical proper torsion identity requires four atoms")
        if values > tuple(reversed(values)):
            raise ValueError(
                "canonical proper torsion identity must be lexicographically "
                "normalized against its reversal"
            )

    @classmethod
    def from_path(
        cls,
        atom_i: int,
        atom_j: int,
        atom_k: int,
        atom_l: int,
    ) -> "CanonicalProperTorsionIdentity":
        path = (atom_i, atom_j, atom_k, atom_l)
        canonical = min(path, tuple(reversed(path)))
        return cls(*canonical)

    def to_dict(self) -> dict[str, int]:
        return {
            "atom_i": self.atom_i,
            "atom_j": self.atom_j,
            "atom_k": self.atom_k,
            "atom_l": self.atom_l,
        }


@dataclass(frozen=True, order=True, slots=True)
class CanonicalPairIdentity:
    """One unordered atom pair."""

    atom_i: int
    atom_j: int

    def __post_init__(self) -> None:
        _require_atom_index("atom_i", self.atom_i)
        _require_atom_index("atom_j", self.atom_j)
        if self.atom_i >= self.atom_j:
            raise ValueError("canonical pair identity requires atom_i < atom_j")

    def to_dict(self) -> dict[str, int]:
        return {"atom_i": self.atom_i, "atom_j": self.atom_j}


@dataclass(frozen=True, order=True, slots=True)
class CanonicalBondEnvironmentMatchKey:
    """Environment-only bond key; this is not a parameter identifier."""

    environment_i: str
    environment_j: str

    def __post_init__(self) -> None:
        _require_environment_id("environment_i", self.environment_i)
        _require_environment_id("environment_j", self.environment_j)
        if self.environment_i > self.environment_j:
            raise ValueError("bond environment endpoints must be normalized")

    @classmethod
    def from_environments(
        cls,
        environment_i: str,
        environment_j: str,
    ) -> "CanonicalBondEnvironmentMatchKey":
        first, second = sorted((environment_i, environment_j))
        return cls(first, second)

    def to_dict(self) -> dict[str, str]:
        return {
            "environment_i": self.environment_i,
            "environment_j": self.environment_j,
        }


@dataclass(frozen=True, order=True, slots=True)
class CanonicalAngleEnvironmentMatchKey:
    """Environment-only outer-center-outer key."""

    outer_environment_i: str
    center_environment: str
    outer_environment_k: str

    def __post_init__(self) -> None:
        _require_environment_id("outer_environment_i", self.outer_environment_i)
        _require_environment_id("center_environment", self.center_environment)
        _require_environment_id("outer_environment_k", self.outer_environment_k)
        if self.outer_environment_i > self.outer_environment_k:
            raise ValueError("angle outer environments must be normalized")

    @classmethod
    def from_environments(
        cls,
        outer_environment_i: str,
        center_environment: str,
        outer_environment_k: str,
    ) -> "CanonicalAngleEnvironmentMatchKey":
        first, third = sorted((outer_environment_i, outer_environment_k))
        return cls(first, center_environment, third)

    def to_dict(self) -> dict[str, str]:
        return {
            "outer_environment_i": self.outer_environment_i,
            "center_environment": self.center_environment,
            "outer_environment_k": self.outer_environment_k,
        }


@dataclass(frozen=True, order=True, slots=True)
class CanonicalProperEnvironmentMatchKey:
    """Environment-only proper key, independently normalized by reversal."""

    environment_i: str
    environment_j: str
    environment_k: str
    environment_l: str

    def __post_init__(self) -> None:
        values = (
            _require_environment_id("environment_i", self.environment_i),
            _require_environment_id("environment_j", self.environment_j),
            _require_environment_id("environment_k", self.environment_k),
            _require_environment_id("environment_l", self.environment_l),
        )
        if values > tuple(reversed(values)):
            raise ValueError(
                "proper environment key must be normalized against its reversal"
            )

    @classmethod
    def from_environments(
        cls,
        environment_i: str,
        environment_j: str,
        environment_k: str,
        environment_l: str,
    ) -> "CanonicalProperEnvironmentMatchKey":
        values = (
            environment_i,
            environment_j,
            environment_k,
            environment_l,
        )
        canonical = min(values, tuple(reversed(values)))
        return cls(*canonical)

    def to_dict(self) -> dict[str, str]:
        return {
            "environment_i": self.environment_i,
            "environment_j": self.environment_j,
            "environment_k": self.environment_k,
            "environment_l": self.environment_l,
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneBondTopologyTerm:
    identity: CanonicalBondIdentity
    match_key: CanonicalBondEnvironmentMatchKey
    parameter_id: None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalBondIdentity:
            raise TypeError("identity must be a CanonicalBondIdentity")
        if type(self.match_key) is not CanonicalBondEnvironmentMatchKey:
            raise TypeError("match_key must be a CanonicalBondEnvironmentMatchKey")
        if self.parameter_id is not None:
            raise ValueError("parameter_id must remain None in the topology-only schema")

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "match_key": self.match_key.to_dict(),
            "parameter_id": None,
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneAngleTopologyTerm:
    identity: CanonicalAngleIdentity
    match_key: CanonicalAngleEnvironmentMatchKey
    parameter_id: None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalAngleIdentity:
            raise TypeError("identity must be a CanonicalAngleIdentity")
        if type(self.match_key) is not CanonicalAngleEnvironmentMatchKey:
            raise TypeError("match_key must be a CanonicalAngleEnvironmentMatchKey")
        if self.parameter_id is not None:
            raise ValueError("parameter_id must remain None in the topology-only schema")

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "match_key": self.match_key.to_dict(),
            "parameter_id": None,
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneProperTopologyTerm:
    identity: CanonicalProperTorsionIdentity
    match_key: CanonicalProperEnvironmentMatchKey
    parameter_id: None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalProperTorsionIdentity:
            raise TypeError("identity must be a CanonicalProperTorsionIdentity")
        if type(self.match_key) is not CanonicalProperEnvironmentMatchKey:
            raise TypeError("match_key must be a CanonicalProperEnvironmentMatchKey")
        if self.parameter_id is not None:
            raise ValueError("parameter_id must remain None in the topology-only schema")

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "match_key": self.match_key.to_dict(),
            "parameter_id": None,
        }


@dataclass(frozen=True, order=True, slots=True)
class CanonicalPairClassification:
    """Shortest-path classification without any interaction scale."""

    identity: CanonicalPairIdentity
    shortest_graph_distance: int | None
    interaction_class: str
    lj_scale: None = field(default=None, compare=False)
    coulomb_scale: None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalPairIdentity:
            raise TypeError("identity must be a CanonicalPairIdentity")
        if self.shortest_graph_distance is not None:
            distance = _require_atom_index(
                "shortest_graph_distance",
                self.shortest_graph_distance,
            )
            if distance < 1:
                raise ValueError("shortest_graph_distance must be positive")
        if type(self.interaction_class) is not str:
            raise TypeError("interaction_class must be an exact string")
        if self.interaction_class not in _FROZEN_PAIR_INTERACTION_CLASSES:
            raise ValueError("unknown pair interaction class")
        expected_class = _interaction_class(self.shortest_graph_distance)
        if self.interaction_class != expected_class:
            raise ValueError(
                "interaction_class must match the frozen shortest-path policy"
            )
        if self.lj_scale is not None or self.coulomb_scale is not None:
            raise ValueError("1-4 and full-pair scales remain unassigned")

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "shortest_graph_distance": self.shortest_graph_distance,
            "interaction_class": self.interaction_class,
            "lj_scale": None,
            "coulomb_scale": None,
        }


@dataclass(frozen=True, slots=True)
class _ComputedInventory:
    system: AllAtomSystem
    applicability: LinearAlkaneC1C4ForceFieldApplicabilityReport
    typing_report: LinearAlkaneTopologicalEnvironmentTypingReport
    inventory_status: str
    bond_terms: tuple[LinearAlkaneBondTopologyTerm, ...]
    angle_terms: tuple[LinearAlkaneAngleTopologyTerm, ...]
    proper_terms: tuple[LinearAlkaneProperTopologyTerm, ...]
    pair_classifications: tuple[CanonicalPairClassification, ...]


def _interaction_class(distance: int | None) -> str:
    if distance == 1:
        return "excluded_1_2"
    if distance == 2:
        return "excluded_1_3"
    if distance == 3:
        return "one_four_separate"
    return "full_nonbonded"


def _adjacency(system: AllAtomSystem) -> tuple[tuple[int, ...], ...]:
    atom_count = system.atom_count
    if tuple(sorted(atom.index for atom in system.atoms)) != tuple(range(atom_count)):
        raise ValueError("atom indices must be contiguous")
    neighbors: list[set[int]] = [set() for _ in range(atom_count)]
    for bond in system.bonds:
        atom_i, atom_j = sorted((bond.atom_i, bond.atom_j))
        if atom_i < 0 or atom_j >= atom_count or atom_i == atom_j:
            raise ValueError("bond endpoints must name two in-range atoms")
        if atom_j in neighbors[atom_i]:
            raise ValueError("covalent graph must not contain duplicate edges")
        neighbors[atom_i].add(atom_j)
        neighbors[atom_j].add(atom_i)
    return tuple(tuple(sorted(row)) for row in neighbors)


def _shortest_distance(
    adjacency: tuple[tuple[int, ...], ...],
    start: int,
    target: int,
) -> int | None:
    queue: deque[tuple[int, int]] = deque([(start, 0)])
    visited = {start}
    while queue:
        atom_index, distance = queue.popleft()
        if atom_index == target:
            return distance
        for neighbor in adjacency[atom_index]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, distance + 1))
    return None


def _environment_by_atom(
    typing_report: LinearAlkaneTopologicalEnvironmentTypingReport,
    atom_count: int,
) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for row in typing_report.environment_assignments:
        atom_index = row.atom_index
        environment_id = row.topological_environment_id
        if atom_index in mapping:
            raise ValueError("typing assignments must contain each atom exactly once")
        mapping[atom_index] = environment_id
    if tuple(sorted(mapping)) != tuple(range(atom_count)):
        raise ValueError("typing assignments must cover the exact atom set")
    return mapping


def _enumerate_available_inventory(
    system: AllAtomSystem,
    environment_by_atom: dict[int, str],
) -> tuple[
    tuple[LinearAlkaneBondTopologyTerm, ...],
    tuple[LinearAlkaneAngleTopologyTerm, ...],
    tuple[LinearAlkaneProperTopologyTerm, ...],
    tuple[CanonicalPairClassification, ...],
]:
    adjacency = _adjacency(system)
    bond_terms = tuple(
        LinearAlkaneBondTopologyTerm(
            identity=CanonicalBondIdentity(
                min(bond.atom_i, bond.atom_j),
                max(bond.atom_i, bond.atom_j),
            ),
            match_key=CanonicalBondEnvironmentMatchKey.from_environments(
                environment_by_atom[bond.atom_i],
                environment_by_atom[bond.atom_j],
            ),
        )
        for bond in sorted(
            system.bonds,
            key=lambda item: (
                min(item.atom_i, item.atom_j),
                max(item.atom_i, item.atom_j),
            ),
        )
    )

    angle_terms = tuple(
        sorted(
            LinearAlkaneAngleTopologyTerm(
                identity=CanonicalAngleIdentity(
                    outer_i,
                    center,
                    outer_k,
                ),
                match_key=CanonicalAngleEnvironmentMatchKey.from_environments(
                    environment_by_atom[outer_i],
                    environment_by_atom[center],
                    environment_by_atom[outer_k],
                ),
            )
            for center, neighbors in enumerate(adjacency)
            for outer_i, outer_k in combinations(neighbors, 2)
        )
    )

    proper_identities = {
        CanonicalProperTorsionIdentity.from_path(atom_i, atom_j, atom_k, atom_l)
        for atom_j, neighbors_j in enumerate(adjacency)
        for atom_k in neighbors_j
        if atom_j < atom_k
        for atom_i in neighbors_j
        if atom_i != atom_k
        for atom_l in adjacency[atom_k]
        if atom_l != atom_j and atom_l != atom_i
    }
    proper_terms = tuple(
        LinearAlkaneProperTopologyTerm(
            identity=identity,
            match_key=CanonicalProperEnvironmentMatchKey.from_environments(
                environment_by_atom[identity.atom_i],
                environment_by_atom[identity.atom_j],
                environment_by_atom[identity.atom_k],
                environment_by_atom[identity.atom_l],
            ),
        )
        for identity in sorted(proper_identities)
    )

    pair_classifications = tuple(
        CanonicalPairClassification(
            identity=CanonicalPairIdentity(atom_i, atom_j),
            shortest_graph_distance=distance,
            interaction_class=_interaction_class(distance),
        )
        for atom_i, atom_j in combinations(range(system.atom_count), 2)
        for distance in (_shortest_distance(adjacency, atom_i, atom_j),)
    )
    return bond_terms, angle_terms, proper_terms, pair_classifications


def _compute(snapshot: bytes) -> _ComputedInventory:
    system = deserialize_all_atom_system(snapshot)
    if serialize_all_atom_system(system) != snapshot:
        raise ValueError("stored canonical system snapshot is not canonical")
    applicability = analyze_linear_alkane_c1_c4_force_field_applicability(system)
    typing_report = analyze_linear_alkane_topological_environment_typing(system)
    if type(applicability) is not LinearAlkaneC1C4ForceFieldApplicabilityReport:
        raise TypeError("applicability dependency must be its exact report type")
    if type(typing_report) is not LinearAlkaneTopologicalEnvironmentTypingReport:
        raise TypeError("typing dependency must be its exact report type")
    snapshot_sha256 = hashlib.sha256(snapshot).hexdigest()
    if applicability.canonical_system_snapshot_sha256 != snapshot_sha256:
        raise ValueError("applicability report must bind the exact system snapshot")
    if typing_report.canonical_system_snapshot_sha256 != snapshot_sha256:
        raise ValueError("typing report must bind the exact system snapshot")
    if typing_report.applicability_report_sha256 != applicability.report_sha256:
        raise ValueError("typing report must bind the fresh applicability report")
    applicability_status = applicability.applicability_status
    typing_status = typing_report.typing_status
    expected_typing_status = {
        "invalid": "invalid_system",
        "unsupported": "unsupported_system",
        "available": "environments_available",
    }[applicability_status]
    if typing_status != expected_typing_status:
        raise ValueError(
            "typing status must agree with the bounded applicability status"
        )
    if applicability_status == "invalid":
        status = "invalid"
    elif applicability_status == "available":
        status = "available"
    else:
        status = "unsupported"
    if status == "available":
        environment_by_atom = _environment_by_atom(
            typing_report,
            system.atom_count,
        )
        bond_terms, angle_terms, proper_terms, pair_classifications = (
            _enumerate_available_inventory(system, environment_by_atom)
        )
    else:
        bond_terms = ()
        angle_terms = ()
        proper_terms = ()
        pair_classifications = ()
    return _ComputedInventory(
        system=system,
        applicability=applicability,
        typing_report=typing_report,
        inventory_status=status,
        bond_terms=bond_terms,
        angle_terms=angle_terms,
        proper_terms=proper_terms,
        pair_classifications=pair_classifications,
    )


def _report_sha256(
    report: LinearAlkaneC1C4ForceFieldApplicabilityReport
    | LinearAlkaneTopologicalEnvironmentTypingReport,
) -> str:
    value = report.report_sha256
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("dependency report must expose a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, init=False, slots=True)
class LinearAlkaneTermPairInventoryReport:
    """Factory-only, snapshot-bound bounded topology inventory."""

    _canonical_system_snapshot: bytes = field(repr=False)
    _canonical_system_snapshot_sha256: str = field(repr=False)

    def __init__(self, system: AllAtomSystem) -> None:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        snapshot = serialize_all_atom_system(system)
        object.__setattr__(self, "_canonical_system_snapshot", snapshot)
        object.__setattr__(
            self,
            "_canonical_system_snapshot_sha256",
            hashlib.sha256(snapshot).hexdigest(),
        )
        computed = _compute(snapshot)
        self._validate(computed)

    def _validated_snapshot_bytes(self) -> bytes:
        snapshot = self._canonical_system_snapshot
        if type(snapshot) is not bytes:
            raise TypeError("_canonical_system_snapshot must be canonical bytes")
        expected_snapshot_sha256 = self._canonical_system_snapshot_sha256
        if (
            type(expected_snapshot_sha256) is not str
            or len(expected_snapshot_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_snapshot_sha256
            )
            or hashlib.sha256(snapshot).hexdigest() != expected_snapshot_sha256
        ):
            raise ValueError("canonical system snapshot digest binding is inconsistent")
        return snapshot

    def _validate(self, computed: _ComputedInventory | None = None) -> None:
        snapshot = self._validated_snapshot_bytes()
        analysis = _compute(snapshot) if computed is None else computed
        if (
            type(analysis) is not _ComputedInventory
            or serialize_all_atom_system(analysis.system) != snapshot
        ):
            raise ValueError(
                "computed inventory must derive from the report's exact "
                "canonical system snapshot"
            )
        if analysis.inventory_status not in _FROZEN_INVENTORY_STATUSES:
            raise ValueError("unknown inventory status")
        if analysis.inventory_status != "available":
            if any(
                (
                    analysis.bond_terms,
                    analysis.angle_terms,
                    analysis.proper_terms,
                    analysis.pair_classifications,
                )
            ):
                raise ValueError("unavailable inventory cannot expose terms or pairs")
            return
        expected_terms = _enumerate_available_inventory(
            analysis.system,
            _environment_by_atom(
                analysis.typing_report,
                analysis.system.atom_count,
            ),
        )
        observed_terms = (
            analysis.bond_terms,
            analysis.angle_terms,
            analysis.proper_terms,
            analysis.pair_classifications,
        )
        if observed_terms != expected_terms:
            raise ValueError(
                "available inventory must exactly equal a fresh canonical "
                "term and pair enumeration"
            )
        atom_count = analysis.system.atom_count
        if len(analysis.pair_classifications) != atom_count * (atom_count - 1) // 2:
            raise ValueError("pair classifications must cover every unordered pair")
        expected_bonds = {
            CanonicalBondIdentity(
                min(bond.atom_i, bond.atom_j),
                max(bond.atom_i, bond.atom_j),
            )
            for bond in analysis.system.bonds
        }
        if {term.identity for term in analysis.bond_terms} != expected_bonds:
            raise ValueError("bond terms must cover the exact covalent edge set")
        distance_two_pairs = sum(
            pair.shortest_graph_distance == 2
            for pair in analysis.pair_classifications
        )
        distance_three_pairs = sum(
            pair.shortest_graph_distance == 3
            for pair in analysis.pair_classifications
        )
        if len(analysis.angle_terms) != distance_two_pairs:
            raise ValueError("tree angle count must equal distance-two pair count")
        if len(analysis.proper_terms) != distance_three_pairs:
            raise ValueError("tree proper count must equal distance-three pair count")

    def _analysis(self) -> _ComputedInventory:
        snapshot = self._validated_snapshot_bytes()
        analysis = _compute(snapshot)
        self._validate(analysis)
        return analysis

    @property
    def inventory_status(self) -> str:
        return self._analysis().inventory_status

    @property
    def bond_terms(self) -> tuple[LinearAlkaneBondTopologyTerm, ...]:
        return self._analysis().bond_terms

    @property
    def angle_terms(self) -> tuple[LinearAlkaneAngleTopologyTerm, ...]:
        return self._analysis().angle_terms

    @property
    def proper_terms(self) -> tuple[LinearAlkaneProperTopologyTerm, ...]:
        return self._analysis().proper_terms

    @property
    def pair_classifications(self) -> tuple[CanonicalPairClassification, ...]:
        return self._analysis().pair_classifications

    @property
    def bond_identities(self) -> tuple[CanonicalBondIdentity, ...]:
        return tuple(term.identity for term in self.bond_terms)

    @property
    def angle_identities(self) -> tuple[CanonicalAngleIdentity, ...]:
        return tuple(term.identity for term in self.angle_terms)

    @property
    def proper_identities(self) -> tuple[CanonicalProperTorsionIdentity, ...]:
        return tuple(term.identity for term in self.proper_terms)

    @property
    def improper_identities(self) -> tuple[()]:
        return ()

    @property
    def constraint_identities(self) -> tuple[()]:
        return ()

    @property
    def pair_class_counts(self) -> tuple[tuple[str, int], ...]:
        pairs = self.pair_classifications
        return tuple(
            (
                interaction_class,
                sum(
                    pair.interaction_class == interaction_class
                    for pair in pairs
                ),
            )
            for interaction_class in _FROZEN_PAIR_INTERACTION_CLASSES
        )

    @property
    def topological_term_and_pair_classification_complete(self) -> bool:
        return self.inventory_status == "available"

    @property
    def preparation_ready(self) -> bool:
        return False

    @property
    def parameter_assignment_complete(self) -> bool:
        return False

    @property
    def parameterability_assessed(self) -> bool:
        return False

    @property
    def global_parameter_coverage_complete(self) -> bool:
        return False

    @property
    def force_field_atom_typing_complete(self) -> bool:
        return False

    @property
    def partial_charge_assignment_complete(self) -> bool:
        return False

    @property
    def physics_supported(self) -> bool:
        return False

    @property
    def scientific_validity_green(self) -> bool:
        return False

    @property
    def energy_evaluation_authorized(self) -> bool:
        return False

    @property
    def force_evaluation_authorized(self) -> bool:
        return False

    @property
    def virial_evaluation_authorized(self) -> bool:
        return False

    @property
    def minimization_authorized(self) -> bool:
        return False

    @property
    def runtime_eligible(self) -> bool:
        return False

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def simulation_ready(self) -> bool:
        return False

    @property
    def claim_safe(self) -> bool:
        return False

    def _blockers(self, analysis: _ComputedInventory) -> tuple[str, ...]:
        blockers: list[str] = []
        if analysis.inventory_status != "available":
            blockers.append("bounded_linear_alkane_applicability_or_typing_unavailable")
        blockers.extend(
            (
                "source_digest_is_not_authentication",
                "force_field_atom_types_not_assigned",
                "partial_charges_not_assigned",
                "bonded_parameters_not_assigned",
                "nonbonded_parameters_not_assigned",
                "one_four_scales_not_assigned",
                "energy_force_virial_not_evaluated",
                "preparation_not_ready",
                "minimization_not_authorized",
                "simulation_not_authorized",
                "claim_not_authorized",
            )
        )
        return tuple(blockers)

    def _core_dict(self, analysis: _ComputedInventory) -> dict[str, Any]:
        applicability = analysis.applicability
        typing_report = analysis.typing_report
        source_sha256 = applicability.source_sha256
        topology_sha256 = applicability.canonical_topology_sha256
        pair_counts = {
            interaction_class: sum(
                pair.interaction_class == interaction_class
                for pair in analysis.pair_classifications
            )
            for interaction_class in _FROZEN_PAIR_INTERACTION_CLASSES
        }
        available = analysis.inventory_status == "available"
        return {
            "schema_id": _FROZEN_SCHEMA_ID,
            "schema_version": _FROZEN_SCHEMA_VERSION,
            "profile_id": _FROZEN_PROFILE_ID,
            "claim_scope": _FROZEN_CLAIM_SCOPE,
            "canonical_system_snapshot_sha256": (
                self._canonical_system_snapshot_sha256
            ),
            "canonical_topology_sha256": topology_sha256,
            "source_sha256": source_sha256,
            "source_authentication_status": "digest_bound_not_authenticated",
            "applicability_schema_id": (
                _FROZEN_APPLICABILITY_SCHEMA_ID
            ),
            "applicability_report_sha256": _report_sha256(applicability),
            "topological_environment_typing_schema_id": (
                _FROZEN_TYPING_SCHEMA_ID
            ),
            "topological_environment_typing_report_sha256": (
                _report_sha256(typing_report)
            ),
            "inventory_status": analysis.inventory_status,
            "atom_count": analysis.system.atom_count if available else None,
            "bond_identity_status": _ENUMERATED if available else _NOT_ENUMERATED,
            "bond_terms": [term.to_dict() for term in analysis.bond_terms],
            "angle_identity_status": _ENUMERATED if available else _NOT_ENUMERATED,
            "angle_terms": [term.to_dict() for term in analysis.angle_terms],
            "proper_torsion_identity_status": (
                _ENUMERATED if available else _NOT_ENUMERATED
            ),
            "proper_terms": [term.to_dict() for term in analysis.proper_terms],
            "improper_selection_policy_id": (
                _FROZEN_IMPROPER_SELECTION_POLICY_ID
            ),
            "improper_identity_status": (
                _ENUMERATED_EMPTY if available else _NOT_ENUMERATED
            ),
            "improper_identities": [],
            "constraint_selection_policy_id": (
                _FROZEN_CONSTRAINT_SELECTION_POLICY_ID
            ),
            "constraint_identity_status": (
                _ENUMERATED_EMPTY if available else _NOT_ENUMERATED
            ),
            "constraint_identities": [],
            "environment_match_policy_id": (
                _FROZEN_ENVIRONMENT_MATCH_POLICY_ID
            ),
            "pair_classification_policy_id": (
                _FROZEN_PAIR_CLASSIFICATION_POLICY_ID
            ),
            "pair_classification_status": (
                _ENUMERATED if available else _NOT_ENUMERATED
            ),
            "pair_classifications": [
                pair.to_dict() for pair in analysis.pair_classifications
            ],
            "pair_class_counts": pair_counts,
            "one_four_lj_scale": None,
            "one_four_coulomb_scale": None,
            "topological_term_and_pair_classification_complete": available,
            "preparation_ready": False,
            "parameter_assignment_complete": False,
            "parameterability_assessed": False,
            "global_parameter_coverage_complete": False,
            "force_field_atom_typing_complete": False,
            "partial_charge_assignment_complete": False,
            "physics_supported": False,
            "scientific_validity_green": False,
            "energy_evaluation_authorized": False,
            "force_evaluation_authorized": False,
            "virial_evaluation_authorized": False,
            "minimization_authorized": False,
            "runtime_eligible": False,
            "execution_authorized": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": list(self._blockers(analysis)),
        }

    @property
    def report_sha256(self) -> str:
        return _sha256_document(self._core_dict(self._analysis()))

    def to_dict(self) -> dict[str, Any]:
        analysis = self._analysis()
        payload = self._core_dict(analysis)
        payload["report_sha256"] = _sha256_document(payload)
        return payload

    def matches_system(self, system: AllAtomSystem) -> bool:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        self._analysis()
        return self._canonical_system_snapshot == serialize_all_atom_system(system)


def analyze_linear_alkane_term_pair_inventory(
    system: AllAtomSystem,
) -> LinearAlkaneTermPairInventoryReport:
    """Build the bounded topology-only term and pair inventory."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    return LinearAlkaneTermPairInventoryReport(system)


__all__ = [
    "CanonicalAngleEnvironmentMatchKey",
    "CanonicalBondEnvironmentMatchKey",
    "CanonicalPairClassification",
    "CanonicalPairIdentity",
    "CanonicalProperEnvironmentMatchKey",
    "CanonicalProperTorsionIdentity",
    "LINEAR_ALKANE_CONSTRAINT_SELECTION_POLICY_ID",
    "LINEAR_ALKANE_ENVIRONMENT_MATCH_POLICY_ID",
    "LINEAR_ALKANE_IMPROPER_SELECTION_POLICY_ID",
    "LINEAR_ALKANE_PAIR_CLASSIFICATION_POLICY_ID",
    "LINEAR_ALKANE_PAIR_INTERACTION_CLASSES",
    "LINEAR_ALKANE_TERM_PAIR_INVENTORY_CLAIM_SCOPE",
    "LINEAR_ALKANE_TERM_PAIR_INVENTORY_PROFILE_ID",
    "LINEAR_ALKANE_TERM_PAIR_INVENTORY_SCHEMA_ID",
    "LINEAR_ALKANE_TERM_PAIR_INVENTORY_SCHEMA_VERSION",
    "LINEAR_ALKANE_TERM_PAIR_INVENTORY_STATUSES",
    "LinearAlkaneAngleTopologyTerm",
    "LinearAlkaneBondTopologyTerm",
    "LinearAlkaneProperTopologyTerm",
    "LinearAlkaneTermPairInventoryReport",
    "analyze_linear_alkane_term_pair_inventory",
]
