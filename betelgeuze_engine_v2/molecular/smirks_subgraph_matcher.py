"""Fail-closed SMIRKS subgraph matching over canonical all-atom systems.

The SMIRKS parser produces a typed query graph but never touches a molecule.
This module applies such a query to a canonical ``AllAtomSystem``: it evaluates
every reviewed atom primitive against observed molecular state, enumerates
bounded subgraph embeddings that respect the query's bond expressions, and
orders each match by the query's mapping indices so a caller receives atom
tuples in SMIRNOFF map order.

Ring primitives require ring perception.  Rather than guessing, this module
derives ring membership and the smallest ring size per atom from the bond graph
itself, and a query using a ring primitive on a system whose bond graph cannot
be perceived fails closed.

When several parameters match the same mapped atom tuple, SMIRNOFF resolves the
conflict by declaration order: the last matching parameter wins.  This module
implements exactly that rule and records every superseded candidate, so a
resolution is auditable rather than implicit.

Matching is chemistry-shaped bookkeeping, not validated typing: the reviewed
SMIRKS subset is narrow, no parameter value is applied to any energy term, and
no independent review exists, so every result stays claim-closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .models import AllAtomSystem
from .smirks_pattern_parser import (
    SmirksAtomExpression,
    SmirksPatternParserError,
    SmirksQuery,
    parse_smirks_pattern,
)


SMIRKS_MATCH_SCHEMA_ID = "betelgeuze.engine_v2_smirks_match/1.0.0"
SMIRKS_MATCH_SET_SCHEMA_ID = "betelgeuze.engine_v2_smirks_match_set/1.0.0"
SMIRKS_ASSIGNMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_smirks_last_match_assignment/1.0.0"
)
SMIRKS_SUBGRAPH_MATCHER_PROFILE_ID = "smirks_subgraph_matcher/1.0.0"
SMIRKS_SUBGRAPH_MATCHER_VERSION = "1.0.0"
SMIRKS_SUBGRAPH_MATCHER_MAX_ATOMS = 512
SMIRKS_SUBGRAPH_MATCHER_MAX_BONDS = 2048
SMIRKS_SUBGRAPH_MATCHER_MAX_MATCHES = 65536
SMIRKS_SUBGRAPH_MATCHER_MAX_RING_SIZE = 12

_AROMATIC_BOND_ORDER = "aromatic"
_SINGLE_ORDERS = frozenset({"1", "1.0", "single"})
_DOUBLE_ORDERS = frozenset({"2", "2.0", "double"})
_TRIPLE_ORDERS = frozenset({"3", "3.0", "triple"})

SMIRKS_SUBGRAPH_MATCHER_CONFIGURATION = {
    "schema_id": (
        "betelgeuze.engine_v2_smirks_subgraph_matcher_configuration/1.0.0"
    ),
    "atom_primitive_evaluation": "conjunction_of_every_reviewed_primitive",
    "connectivity_primitive_source": "explicit_bond_degree_including_hydrogens",
    "hydrogen_count_primitive_source": "explicit_bonded_hydrogen_atoms_only",
    "ring_primitive_source": "perceived_from_canonical_bond_graph",
    "max_perceived_ring_size": SMIRKS_SUBGRAPH_MATCHER_MAX_RING_SIZE,
    "match_ordering": "ascending_mapped_index_then_atom_index",
    "conflict_resolution": "last_declared_matching_parameter_wins",
    "superseded_candidates_retained": True,
    "implicit_hydrogens_inferred": False,
    "aromaticity_inferred": False,
    "parameter_values_applied_to_energy_terms": False,
    "max_atoms": SMIRKS_SUBGRAPH_MATCHER_MAX_ATOMS,
    "max_matches": SMIRKS_SUBGRAPH_MATCHER_MAX_MATCHES,
}
SMIRKS_SUBGRAPH_MATCHER_CONFIGURATION_SHA256 = hashlib.sha256(
    json.dumps(
        SMIRKS_SUBGRAPH_MATCHER_CONFIGURATION,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
).hexdigest()

SMIRKS_SUBGRAPH_MATCHER_BLOCKERS = (
    "reviewed_smirks_subset_is_narrower_than_full_smarts",
    "aromaticity_and_implicit_hydrogens_are_read_not_perceived",
    "ring_perception_is_bounded_smallest_ring_not_sssr_certified",
    "matched_parameters_not_applied_to_any_energy_term",
    "independent_scientific_review_missing",
    "validated_refinement_claim_not_authorized",
)

_CLAIM_FLAGS = {
    "atom_typing_implemented": True,
    "match_ordering_follows_mapped_indices": True,
    "last_declared_match_wins": True,
    "superseded_candidates_retained": True,
    "aromaticity_inferred": False,
    "implicit_hydrogens_inferred": False,
    "parameter_values_applied": False,
    "independent_external_review_present": False,
    "benchmark_validated": False,
    "scientifically_validated": False,
    "claim_safe": False,
}

_RING_PRIMITIVE_KINDS = frozenset({"ring_membership_count", "ring_size"})


class SmirksSubgraphMatcherError(ValueError):
    """A system, query, or match projection is invalid or unsupported."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _normalized_bond_order(bond: Any) -> str:
    if bool(bond.aromatic):
        return _AROMATIC_BOND_ORDER
    raw = str(bond.order).strip().lower()
    if raw in _SINGLE_ORDERS:
        return "single"
    if raw in _DOUBLE_ORDERS:
        return "double"
    if raw in _TRIPLE_ORDERS:
        return "triple"
    if raw in {"aromatic", "1.5"}:
        return _AROMATIC_BOND_ORDER
    raise SmirksSubgraphMatcherError(
        f"bond order {bond.order!r} is not in the reviewed subset"
    )


@dataclass(frozen=True, slots=True)
class _MolecularView:
    atom_count: int
    atomic_numbers: tuple[int, ...]
    aromatic: tuple[bool, ...]
    formal_charges: tuple[int, ...]
    degrees: tuple[int, ...]
    hydrogen_counts: tuple[int, ...]
    ring_membership: tuple[int, ...]
    smallest_ring_size: tuple[int, ...]
    ring_perception_complete: bool
    neighbors: tuple[tuple[int, ...], ...]
    bond_orders: Mapping[tuple[int, int], str]


def _perceive_rings(
    atom_count: int,
    neighbors: Sequence[Sequence[int]],
) -> tuple[tuple[int, ...], tuple[int, ...], bool]:
    """Return per-atom ring membership counts and smallest ring size."""

    membership = [0] * atom_count
    smallest = [0] * atom_count
    complete = True
    for start in range(atom_count):
        best: int | None = None
        # Bounded breadth-first search for the shortest cycle through `start`.
        for first in neighbors[start]:
            queue: list[tuple[int, int, int]] = [(first, start, 1)]
            seen = {start, first}
            while queue:
                current, parent, depth = queue.pop(0)
                if depth >= SMIRKS_SUBGRAPH_MATCHER_MAX_RING_SIZE:
                    complete = False
                    continue
                for neighbor in neighbors[current]:
                    if neighbor == parent:
                        continue
                    if neighbor == start:
                        length = depth + 1
                        if length >= 3 and (best is None or length < best):
                            best = length
                        continue
                    if neighbor in seen:
                        continue
                    seen.add(neighbor)
                    queue.append((neighbor, current, depth + 1))
        if best is not None:
            membership[start] = 1
            smallest[start] = best
    return tuple(membership), tuple(smallest), complete


def _molecular_view(system: AllAtomSystem) -> _MolecularView:
    atoms = list(system.atoms)
    if not atoms:
        raise SmirksSubgraphMatcherError("canonical system declares no atoms")
    if len(atoms) > SMIRKS_SUBGRAPH_MATCHER_MAX_ATOMS:
        raise SmirksSubgraphMatcherError("canonical system exceeds its atom bound")
    bonds = list(system.bonds)
    if len(bonds) > SMIRKS_SUBGRAPH_MATCHER_MAX_BONDS:
        raise SmirksSubgraphMatcherError("canonical system exceeds its bond bound")
    if tuple(atom.index for atom in atoms) != tuple(range(len(atoms))):
        raise SmirksSubgraphMatcherError(
            "canonical system atom indices are not contiguous"
        )
    neighbor_sets: list[set[int]] = [set() for _ in atoms]
    orders: dict[tuple[int, int], str] = {}
    for bond in bonds:
        i = int(bond.atom_i)
        j = int(bond.atom_j)
        if not 0 <= i < len(atoms) or not 0 <= j < len(atoms) or i == j:
            raise SmirksSubgraphMatcherError("canonical bond references bad atoms")
        order = _normalized_bond_order(bond)
        key = (min(i, j), max(i, j))
        if key in orders and orders[key] != order:
            raise SmirksSubgraphMatcherError(
                "canonical system declares conflicting bond orders"
            )
        orders[key] = order
        neighbor_sets[i].add(j)
        neighbor_sets[j].add(i)
    neighbors = tuple(tuple(sorted(row)) for row in neighbor_sets)
    membership, smallest, complete = _perceive_rings(len(atoms), neighbors)
    hydrogen_counts = tuple(
        sum(1 for neighbor in neighbors[index] if atoms[neighbor].atomic_number == 1)
        for index in range(len(atoms))
    )
    return _MolecularView(
        atom_count=len(atoms),
        atomic_numbers=tuple(int(atom.atomic_number) for atom in atoms),
        aromatic=tuple(bool(atom.aromatic) for atom in atoms),
        formal_charges=tuple(int(atom.formal_charge) for atom in atoms),
        degrees=tuple(len(row) for row in neighbors),
        hydrogen_counts=hydrogen_counts,
        ring_membership=membership,
        smallest_ring_size=smallest,
        ring_perception_complete=complete,
        neighbors=neighbors,
        bond_orders=orders,
    )


def _atom_matches(
    expression: SmirksAtomExpression,
    atom_index: int,
    view: _MolecularView,
) -> bool:
    for primitive in expression.primitives:
        kind = str(primitive["kind"])
        value = primitive["value"]
        if kind == "any_atom":
            continue
        if kind == "atomic_number":
            if view.atomic_numbers[atom_index] != value:
                return False
        elif kind == "aromatic":
            if not view.aromatic[atom_index]:
                return False
        elif kind == "aliphatic":
            if view.aromatic[atom_index]:
                return False
        elif kind in {"connectivity", "explicit_degree"}:
            if view.degrees[atom_index] != value:
                return False
        elif kind == "total_hydrogen_count":
            if view.hydrogen_counts[atom_index] != value:
                return False
        elif kind == "ring_membership_count":
            if view.ring_membership[atom_index] != value:
                return False
        elif kind == "ring_size":
            if view.smallest_ring_size[atom_index] != value:
                return False
        elif kind == "formal_charge":
            if view.formal_charges[atom_index] != value:
                return False
        else:  # pragma: no cover - parser restricts the primitive set
            raise SmirksSubgraphMatcherError(
                f"primitive kind {kind!r} is not supported by the matcher"
            )
    return True


def _bond_matches(primitive: str, observed: str) -> bool:
    if primitive == "any":
        return True
    if primitive == "single_or_aromatic":
        return observed in {"single", _AROMATIC_BOND_ORDER}
    return primitive == observed


def _require_ring_support(query: SmirksQuery, view: _MolecularView) -> bool:
    uses_rings = any(
        str(primitive["kind"]) in _RING_PRIMITIVE_KINDS
        for atom in query.atoms
        for primitive in atom.primitives
    )
    if uses_rings and not view.ring_perception_complete:
        raise SmirksSubgraphMatcherError(
            "query uses a ring primitive but ring perception is incomplete"
        )
    return uses_rings


def _enumerate_matches(
    query: SmirksQuery,
    view: _MolecularView,
) -> tuple[tuple[int, ...], ...]:
    adjacency: dict[int, list[tuple[int, str]]] = {
        atom.ordinal: [] for atom in query.atoms
    }
    for bond in query.bonds:
        adjacency[bond.atom_i].append((bond.atom_j, bond.primitive))
        adjacency[bond.atom_j].append((bond.atom_i, bond.primitive))

    order = [atom.ordinal for atom in query.atoms]
    candidates = {
        atom.ordinal: [
            index
            for index in range(view.atom_count)
            if _atom_matches(atom, index, view)
        ]
        for atom in query.atoms
    }
    matches: list[tuple[int, ...]] = []
    assignment: dict[int, int] = {}

    def extend(position: int) -> None:
        if len(matches) > SMIRKS_SUBGRAPH_MATCHER_MAX_MATCHES:
            raise SmirksSubgraphMatcherError(
                "SMIRKS match count exceeds its bound"
            )
        if position == len(order):
            matches.append(tuple(assignment[ordinal] for ordinal in order))
            return
        ordinal = order[position]
        for index in candidates[ordinal]:
            if index in assignment.values():
                continue
            compatible = True
            for neighbor_ordinal, primitive in adjacency[ordinal]:
                if neighbor_ordinal not in assignment:
                    continue
                other = assignment[neighbor_ordinal]
                key = (min(index, other), max(index, other))
                observed = view.bond_orders.get(key)
                if observed is None or not _bond_matches(primitive, observed):
                    compatible = False
                    break
            if not compatible:
                continue
            assignment[ordinal] = index
            extend(position + 1)
            del assignment[ordinal]

    extend(0)
    return tuple(matches)


@dataclass(frozen=True, slots=True, repr=False)
class SmirksMatch:
    """One embedding of a query into the system, in mapped-index order."""

    ordinal: int
    query_ordinals: tuple[int, ...]
    atom_indices: tuple[int, ...]
    mapped_indices: tuple[int, ...]
    mapped_atom_indices: tuple[int, ...]

    def __repr__(self) -> str:
        return (
            "SmirksMatch("
            f"ordinal={self.ordinal}, "
            f"mapped_atom_indices={self.mapped_atom_indices!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        projection = {
            "schema_id": SMIRKS_MATCH_SCHEMA_ID,
            "ordinal": self.ordinal,
            "query_ordinals": list(self.query_ordinals),
            "atom_indices": list(self.atom_indices),
            "mapped_indices": list(self.mapped_indices),
            "mapped_atom_indices": list(self.mapped_atom_indices),
            "mapped_atom_count": len(self.mapped_atom_indices),
        }
        return {**projection, "match_sha256": _sha256(projection)}


@dataclass(frozen=True, slots=True, repr=False)
class SmirksMatchSet:
    """Every match of one SMIRKS pattern against one canonical system."""

    smirks: str
    query_sha256: str
    system_atom_count: int
    ring_primitives_used: bool
    matches: tuple[SmirksMatch, ...]

    def __repr__(self) -> str:
        return f"SmirksMatchSet(smirks={self.smirks!r}, matches={len(self.matches)})"

    def _payload(self) -> dict[str, Any]:
        rows = [row.to_dict() for row in self.matches]
        return {
            "schema_id": SMIRKS_MATCH_SET_SCHEMA_ID,
            "profile_id": SMIRKS_SUBGRAPH_MATCHER_PROFILE_ID,
            "matcher_version": SMIRKS_SUBGRAPH_MATCHER_VERSION,
            "smirks": self.smirks,
            "query_sha256": self.query_sha256,
            "system_atom_count": self.system_atom_count,
            "ring_primitives_used": self.ring_primitives_used,
            "match_count": len(rows),
            "matches": rows,
            "matched_atom_indices": sorted(
                {index for row in rows for index in row["mapped_atom_indices"]}
            ),
            "configuration": dict(SMIRKS_SUBGRAPH_MATCHER_CONFIGURATION),
            "configuration_sha256": SMIRKS_SUBGRAPH_MATCHER_CONFIGURATION_SHA256,
            "scientific_blockers": list(SMIRKS_SUBGRAPH_MATCHER_BLOCKERS),
            **_CLAIM_FLAGS,
        }

    @property
    def match_set_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "match_set_sha256": self.match_set_sha256}


def match_smirks_query(
    query: SmirksQuery,
    system: AllAtomSystem,
) -> SmirksMatchSet:
    """Match one parsed query against one canonical system."""

    if not isinstance(query, SmirksQuery):
        raise SmirksSubgraphMatcherError("query must be a parsed SMIRKS query")
    view = _molecular_view(system)
    ring_primitives_used = _require_ring_support(query, view)
    mapped_pairs = sorted(
        (
            (atom.map_index, atom.ordinal)
            for atom in query.atoms
            if atom.map_index is not None
        )
    )
    mapped_indices = tuple(index for index, _ordinal in mapped_pairs)
    mapped_ordinals = tuple(ordinal for _index, ordinal in mapped_pairs)
    query_ordinals = tuple(atom.ordinal for atom in query.atoms)
    embeddings = _enumerate_matches(query, view)
    rows: list[SmirksMatch] = []
    for ordinal, embedding in enumerate(
        sorted(
            embeddings,
            key=lambda row: tuple(
                row[query_ordinals.index(mapped)] for mapped in mapped_ordinals
            )
            + row,
        )
    ):
        position = {value: slot for slot, value in enumerate(query_ordinals)}
        rows.append(
            SmirksMatch(
                ordinal=ordinal,
                query_ordinals=query_ordinals,
                atom_indices=embedding,
                mapped_indices=mapped_indices,
                mapped_atom_indices=tuple(
                    embedding[position[mapped]] for mapped in mapped_ordinals
                ),
            )
        )
    return SmirksMatchSet(
        smirks=query.smirks,
        query_sha256=query.query_sha256,
        system_atom_count=view.atom_count,
        ring_primitives_used=ring_primitives_used,
        matches=tuple(rows),
    )


def match_smirks_pattern(
    smirks: object,
    system: AllAtomSystem,
) -> SmirksMatchSet:
    """Parse one SMIRKS pattern and match it against one canonical system."""

    try:
        query = parse_smirks_pattern(smirks)
    except SmirksPatternParserError as exc:
        raise SmirksSubgraphMatcherError(
            "SMIRKS pattern is not in the reviewed subset"
        ) from exc
    return match_smirks_query(query, system)


@dataclass(frozen=True, slots=True, repr=False)
class SmirksLastMatchAssignment:
    """Last-declared-wins resolution over an ordered parameter list."""

    system_atom_count: int
    parameter_ids: tuple[str, ...]
    resolved: tuple[dict[str, Any], ...]

    def __repr__(self) -> str:
        return (
            "SmirksLastMatchAssignment("
            f"parameters={len(self.parameter_ids)}, "
            f"resolved={len(self.resolved)})"
        )

    def _payload(self) -> dict[str, Any]:
        rows = [dict(row) for row in self.resolved]
        return {
            "schema_id": SMIRKS_ASSIGNMENT_SCHEMA_ID,
            "profile_id": SMIRKS_SUBGRAPH_MATCHER_PROFILE_ID,
            "matcher_version": SMIRKS_SUBGRAPH_MATCHER_VERSION,
            "system_atom_count": self.system_atom_count,
            "parameter_ids": list(self.parameter_ids),
            "parameter_count": len(self.parameter_ids),
            "resolved_tuple_count": len(rows),
            "resolved": rows,
            "superseded_candidate_count": sum(
                len(row["superseded_parameter_ids"]) for row in rows
            ),
            "conflict_resolution": "last_declared_matching_parameter_wins",
            "configuration": dict(SMIRKS_SUBGRAPH_MATCHER_CONFIGURATION),
            "configuration_sha256": SMIRKS_SUBGRAPH_MATCHER_CONFIGURATION_SHA256,
            "scientific_blockers": list(SMIRKS_SUBGRAPH_MATCHER_BLOCKERS),
            **_CLAIM_FLAGS,
        }

    @property
    def assignment_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "assignment_sha256": self.assignment_sha256}


def resolve_last_match_assignment(
    parameters: Sequence[Mapping[str, Any]],
    system: AllAtomSystem,
) -> SmirksLastMatchAssignment:
    """Resolve an ordered ``(parameter_id, smirks)`` list by last-match-wins."""

    if not parameters:
        raise SmirksSubgraphMatcherError("assignment requires at least one parameter")
    view = _molecular_view(system)
    parameter_ids: list[str] = []
    winners: dict[tuple[int, ...], dict[str, Any]] = {}
    for declaration_order, entry in enumerate(parameters):
        row = dict(entry)
        parameter_id = row.get("parameter_id")
        smirks = row.get("smirks")
        if not isinstance(parameter_id, str) or not parameter_id:
            raise SmirksSubgraphMatcherError(
                "parameter entry must carry a non-empty parameter_id"
            )
        if parameter_id in parameter_ids:
            raise SmirksSubgraphMatcherError(
                "parameter ids must be unique within one handler"
            )
        parameter_ids.append(parameter_id)
        match_set = match_smirks_pattern(smirks, system)
        for match in match_set.matches:
            key = match.mapped_atom_indices
            existing = winners.get(key)
            superseded = list(existing["superseded_parameter_ids"]) if existing else []
            if existing is not None:
                superseded.append(str(existing["parameter_id"]))
            winners[key] = {
                "mapped_atom_indices": list(key),
                "parameter_id": parameter_id,
                "declaration_order": declaration_order,
                "smirks": match_set.smirks,
                "superseded_parameter_ids": superseded,
                "superseded_count": len(superseded),
            }
    resolved = tuple(
        {**winners[key], "mapped_atom_indices": list(key)}
        for key in sorted(winners)
    )
    if view.atom_count != len(system.atoms):  # pragma: no cover - defensive
        raise SmirksSubgraphMatcherError("system atom count changed during matching")
    return SmirksLastMatchAssignment(
        system_atom_count=view.atom_count,
        parameter_ids=tuple(parameter_ids),
        resolved=resolved,
    )


def require_smirks_match_set_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a canonical match-set document without rematching."""

    if not isinstance(payload, Mapping):
        raise SmirksSubgraphMatcherError("match-set document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != SMIRKS_MATCH_SET_SCHEMA_ID:
        raise SmirksSubgraphMatcherError("unsupported match-set schema")
    declared = document.pop("match_set_sha256", None)
    if _sha256(document) != declared:
        raise SmirksSubgraphMatcherError("match-set document digest is invalid")
    for field in (
        "aromaticity_inferred",
        "implicit_hydrogens_inferred",
        "parameter_values_applied",
        "scientifically_validated",
        "claim_safe",
    ):
        if document.get(field) is not False:
            raise SmirksSubgraphMatcherError(
                f"match-set document must keep {field}=false"
            )
    matches = document.get("matches")
    if not isinstance(matches, list):
        raise SmirksSubgraphMatcherError("match-set document must retain matches")
    for item in matches:
        if not isinstance(item, Mapping):
            raise SmirksSubgraphMatcherError("match row must be a mapping")
        match = dict(item)
        match_digest = match.pop("match_sha256", None)
        if _sha256(match) != match_digest:
            raise SmirksSubgraphMatcherError("match row digest is invalid")
    return {**document, "match_set_sha256": declared}


def require_smirks_assignment_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a canonical last-match assignment document."""

    if not isinstance(payload, Mapping):
        raise SmirksSubgraphMatcherError("assignment document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != SMIRKS_ASSIGNMENT_SCHEMA_ID:
        raise SmirksSubgraphMatcherError("unsupported assignment schema")
    declared = document.pop("assignment_sha256", None)
    if _sha256(document) != declared:
        raise SmirksSubgraphMatcherError("assignment document digest is invalid")
    if document.get("conflict_resolution") != (
        "last_declared_matching_parameter_wins"
    ):
        raise SmirksSubgraphMatcherError(
            "assignment document declares a different conflict rule"
        )
    for field in ("parameter_values_applied", "scientifically_validated", "claim_safe"):
        if document.get(field) is not False:
            raise SmirksSubgraphMatcherError(
                f"assignment document must keep {field}=false"
            )
    return {**document, "assignment_sha256": declared}


__all__ = [
    "SMIRKS_ASSIGNMENT_SCHEMA_ID",
    "SMIRKS_MATCH_SCHEMA_ID",
    "SMIRKS_MATCH_SET_SCHEMA_ID",
    "SMIRKS_SUBGRAPH_MATCHER_BLOCKERS",
    "SMIRKS_SUBGRAPH_MATCHER_CONFIGURATION",
    "SMIRKS_SUBGRAPH_MATCHER_CONFIGURATION_SHA256",
    "SMIRKS_SUBGRAPH_MATCHER_MAX_ATOMS",
    "SMIRKS_SUBGRAPH_MATCHER_MAX_BONDS",
    "SMIRKS_SUBGRAPH_MATCHER_MAX_MATCHES",
    "SMIRKS_SUBGRAPH_MATCHER_MAX_RING_SIZE",
    "SMIRKS_SUBGRAPH_MATCHER_PROFILE_ID",
    "SMIRKS_SUBGRAPH_MATCHER_VERSION",
    "SmirksLastMatchAssignment",
    "SmirksMatch",
    "SmirksMatchSet",
    "SmirksSubgraphMatcherError",
    "match_smirks_pattern",
    "match_smirks_query",
    "require_smirks_assignment_document",
    "require_smirks_match_set_document",
    "resolve_last_match_assignment",
]
