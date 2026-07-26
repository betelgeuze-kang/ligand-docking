"""Fail-closed valence and vdW parameter assignment over canonical systems.

Three pieces already exist: the OFFXML semantic parser reads a typed parameter
table, the SMIRKS parser turns each pattern into a query, and the subgraph
matcher applies a query to a molecule.  Nothing joined them, so no atom, bond,
angle, or torsion had an actual assigned parameter.

This module closes that join.  For one canonical ``AllAtomSystem`` it enumerates
the topology each handler is responsible for -- vdW atoms, bonded pairs, angle
triples, proper-torsion quadruples, and improper-torsion centres -- then resolves
every one of those tuples against the handler's ordered parameter list using the
SMIRNOFF rule that the last declared match wins.

Coverage is a gate, not a statistic.  A handler that leaves any of its own
topology tuples unassigned fails closed, because silently skipping a term would
let an incomplete force field look complete.  Superseded candidates are retained
per tuple so each choice is auditable.

Assignment attaches reviewed parameter values to topology; it does not evaluate
an energy or force, does not assign partial charges or masses, and carries no
calibration review, so every result stays claim-closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .models import AllAtomSystem
from .offxml_semantic_parser import (
    OffxmlSemanticDocument,
    OffxmlSemanticParameter,
)
from .smirks_pattern_parser import (
    SmirksPatternParserError,
    parse_smirks_pattern,
)
from .smirks_subgraph_matcher import (
    SmirksSubgraphMatcherError,
    match_smirks_query,
)


OFFXML_VALENCE_TERM_SCHEMA_ID = (
    "betelgeuze.engine_v2_offxml_valence_term/1.0.0"
)
OFFXML_VALENCE_HANDLER_SCHEMA_ID = (
    "betelgeuze.engine_v2_offxml_valence_handler_assignment/1.0.0"
)
OFFXML_VALENCE_ASSIGNMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_offxml_valence_assignment/1.0.0"
)
OFFXML_VALENCE_ASSIGNMENT_PROFILE_ID = "offxml_valence_assignment/1.0.0"
OFFXML_VALENCE_ASSIGNMENT_VERSION = "1.0.0"
OFFXML_VALENCE_ASSIGNMENT_MAX_TERMS = 65536

# Handler -> the topology it is responsible for covering.
OFFXML_VALENCE_HANDLER_TOPOLOGY = {
    "vdW": "atom",
    "Bonds": "bond",
    "Angles": "angle",
    "ProperTorsions": "proper_torsion",
    "ImproperTorsions": "improper_torsion",
}

# Handlers whose topology must be fully covered for an assignment to succeed.
OFFXML_VALENCE_REQUIRED_COVERAGE_HANDLERS = (
    "vdW",
    "Bonds",
    "Angles",
    "ProperTorsions",
)

OFFXML_VALENCE_ASSIGNMENT_CONFIGURATION = {
    "schema_id": (
        "betelgeuze.engine_v2_offxml_valence_assignment_configuration/1.0.0"
    ),
    "handler_topology": dict(OFFXML_VALENCE_HANDLER_TOPOLOGY),
    "required_coverage_handlers": list(
        OFFXML_VALENCE_REQUIRED_COVERAGE_HANDLERS
    ),
    "conflict_resolution": "last_declared_matching_parameter_wins",
    "superseded_candidates_retained": True,
    "incomplete_required_coverage_fails_closed": True,
    "improper_coverage_is_optional_by_smirnoff_convention": True,
    "topology_source": "canonical_all_atom_system_bond_graph",
    "angle_and_torsion_enumeration": "canonical_ascending_endpoint_order",
    "energies_or_forces_evaluated": False,
    "partial_charges_assigned": False,
    "atom_masses_assigned": False,
    "parameter_values_calibration_reviewed": False,
}
OFFXML_VALENCE_ASSIGNMENT_CONFIGURATION_SHA256 = hashlib.sha256(
    json.dumps(
        OFFXML_VALENCE_ASSIGNMENT_CONFIGURATION,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
).hexdigest()

OFFXML_VALENCE_ASSIGNMENT_BLOCKERS = (
    "reviewed_smirks_subset_is_narrower_than_full_smarts",
    "assigned_values_not_evaluated_in_any_energy_or_force_term",
    "partial_charge_and_atom_mass_assignment_not_implemented",
    "exclusions_and_one_four_scaling_not_applied",
    "parameter_value_calibration_not_reviewed",
    "independent_force_and_energy_validation_missing",
    "independent_scientific_review_missing",
    "validated_refinement_claim_not_authorized",
)

_CLAIM_FLAGS = {
    "parameter_assignment_implemented": True,
    "required_handler_coverage_complete": True,
    "last_declared_match_wins": True,
    "superseded_candidates_retained": True,
    "energies_or_forces_evaluated": False,
    "partial_charges_assigned": False,
    "atom_masses_assigned": False,
    "exclusions_and_one_four_scaling_applied": False,
    "independent_external_review_present": False,
    "benchmark_validated": False,
    "scientifically_validated": False,
    "claim_safe": False,
}


class OffxmlValenceAssignmentError(ValueError):
    """A topology, handler, coverage, or assignment projection is invalid."""


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


def _neighbors(system: AllAtomSystem) -> tuple[tuple[int, ...], ...]:
    atom_count = len(system.atoms)
    sets: list[set[int]] = [set() for _ in range(atom_count)]
    for bond in system.bonds:
        i = int(bond.atom_i)
        j = int(bond.atom_j)
        if not 0 <= i < atom_count or not 0 <= j < atom_count or i == j:
            raise OffxmlValenceAssignmentError(
                "canonical bond references an invalid atom index"
            )
        sets[i].add(j)
        sets[j].add(i)
    return tuple(tuple(sorted(row)) for row in sets)


def _atom_topology(system: AllAtomSystem) -> tuple[tuple[int, ...], ...]:
    return tuple((int(atom.index),) for atom in system.atoms)


def _bond_topology(system: AllAtomSystem) -> tuple[tuple[int, ...], ...]:
    pairs = {
        (min(int(bond.atom_i), int(bond.atom_j)), max(int(bond.atom_i), int(bond.atom_j)))
        for bond in system.bonds
    }
    return tuple(sorted(pairs))


def _angle_topology(
    neighbors: Sequence[Sequence[int]],
) -> tuple[tuple[int, ...], ...]:
    angles: set[tuple[int, int, int]] = set()
    for centre, bonded in enumerate(neighbors):
        ordered = sorted(bonded)
        for position, first in enumerate(ordered):
            for last in ordered[position + 1 :]:
                angles.add((min(first, last), centre, max(first, last)))
    return tuple(sorted(angles))


def _proper_torsion_topology(
    system: AllAtomSystem,
    neighbors: Sequence[Sequence[int]],
) -> tuple[tuple[int, ...], ...]:
    torsions: set[tuple[int, int, int, int]] = set()
    for bond in system.bonds:
        j = int(bond.atom_i)
        k = int(bond.atom_j)
        for i in neighbors[j]:
            if i == k:
                continue
            for last in neighbors[k]:
                if last in {i, j}:
                    continue
                candidate = (i, j, k, last)
                reverse = (last, k, j, i)
                torsions.add(min(candidate, reverse))
    return tuple(sorted(torsions))


def _improper_torsion_topology(
    neighbors: Sequence[Sequence[int]],
) -> tuple[tuple[int, ...], ...]:
    impropers: set[tuple[int, int, int, int]] = set()
    for centre, bonded in enumerate(neighbors):
        if len(bonded) != 3:
            continue
        first, second, third = sorted(bonded)
        impropers.add((first, centre, second, third))
    return tuple(sorted(impropers))


def _handler_topology(
    handler: str,
    system: AllAtomSystem,
    neighbors: Sequence[Sequence[int]],
) -> tuple[tuple[int, ...], ...]:
    topology = OFFXML_VALENCE_HANDLER_TOPOLOGY.get(handler)
    if topology == "atom":
        return _atom_topology(system)
    if topology == "bond":
        return _bond_topology(system)
    if topology == "angle":
        return _angle_topology(neighbors)
    if topology == "proper_torsion":
        return _proper_torsion_topology(system, neighbors)
    if topology == "improper_torsion":
        return _improper_torsion_topology(neighbors)
    raise OffxmlValenceAssignmentError(
        f"handler {handler!r} has no reviewed topology mapping"
    )


def _canonical_tuple(handler: str, indices: Sequence[int]) -> tuple[int, ...]:
    values = tuple(int(value) for value in indices)
    topology = OFFXML_VALENCE_HANDLER_TOPOLOGY.get(handler)
    if topology in {"atom", "improper_torsion"}:
        return values
    if topology == "bond":
        if len(values) != 2:
            raise OffxmlValenceAssignmentError("bond match must map two atoms")
        return (min(values), max(values))
    if topology == "angle":
        if len(values) != 3:
            raise OffxmlValenceAssignmentError("angle match must map three atoms")
        return (min(values[0], values[2]), values[1], max(values[0], values[2]))
    if topology == "proper_torsion":
        if len(values) != 4:
            raise OffxmlValenceAssignmentError(
                "proper torsion match must map four atoms"
            )
        return min(values, tuple(reversed(values)))
    raise OffxmlValenceAssignmentError(
        f"handler {handler!r} has no reviewed tuple canonicalization"
    )


def _parameter_values(parameter: OffxmlSemanticParameter) -> dict[str, Any]:
    return {
        str(row["attribute"]): {
            "value_binary64_hex": str(row["value_binary64_hex"]),
            "unit": str(row["unit"]),
        }
        for row in parameter.quantities
    }


@dataclass(frozen=True, slots=True, repr=False)
class OffxmlValenceTerm:
    """One topology tuple with its winning parameter and superseded history."""

    handler: str
    topology: str
    atom_indices: tuple[int, ...]
    parameter_id: str
    declaration_order: int
    smirks: str
    values: Mapping[str, Any]
    superseded_parameter_ids: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            "OffxmlValenceTerm("
            f"handler={self.handler!r}, atoms={self.atom_indices!r}, "
            f"parameter_id={self.parameter_id!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        projection = {
            "schema_id": OFFXML_VALENCE_TERM_SCHEMA_ID,
            "handler": self.handler,
            "topology": self.topology,
            "atom_indices": list(self.atom_indices),
            "parameter_id": self.parameter_id,
            "declaration_order": self.declaration_order,
            "smirks": self.smirks,
            "values": {key: dict(value) for key, value in dict(self.values).items()},
            "value_attribute_ids": sorted(dict(self.values)),
            "superseded_parameter_ids": list(self.superseded_parameter_ids),
            "superseded_count": len(self.superseded_parameter_ids),
            "values_evaluated_in_energy_term": False,
        }
        return {**projection, "term_sha256": _sha256(projection)}


@dataclass(frozen=True, slots=True, repr=False)
class OffxmlValenceHandlerAssignment:
    """One handler's coverage of its own topology."""

    handler: str
    topology: str
    parameter_count: int
    topology_tuple_count: int
    coverage_required: bool
    terms: tuple[OffxmlValenceTerm, ...]
    unassigned_atom_tuples: tuple[tuple[int, ...], ...]

    def __repr__(self) -> str:
        return (
            "OffxmlValenceHandlerAssignment("
            f"handler={self.handler!r}, terms={len(self.terms)})"
        )

    @property
    def coverage_complete(self) -> bool:
        return not self.unassigned_atom_tuples

    def to_dict(self) -> dict[str, Any]:
        rows = [row.to_dict() for row in self.terms]
        projection = {
            "schema_id": OFFXML_VALENCE_HANDLER_SCHEMA_ID,
            "handler": self.handler,
            "topology": self.topology,
            "parameter_count": self.parameter_count,
            "topology_tuple_count": self.topology_tuple_count,
            "assigned_tuple_count": len(rows),
            "unassigned_tuple_count": len(self.unassigned_atom_tuples),
            "unassigned_atom_tuples": [
                list(row) for row in self.unassigned_atom_tuples
            ],
            "coverage_required": self.coverage_required,
            "coverage_complete": self.coverage_complete,
            "superseded_candidate_count": sum(
                row["superseded_count"] for row in rows
            ),
            "terms": rows,
        }
        return {
            **projection,
            "handler_assignment_sha256": _sha256(projection),
        }


@dataclass(frozen=True, slots=True, repr=False)
class OffxmlValenceAssignment:
    """Canonical, claim-closed valence and vdW assignment for one system."""

    offxml_document_sha256: str
    system_sha256: str
    system_atom_count: int
    handlers: tuple[OffxmlValenceHandlerAssignment, ...]

    def __repr__(self) -> str:
        return (
            "OffxmlValenceAssignment("
            f"handlers={len(self.handlers)}, terms={self.term_count})"
        )

    @property
    def term_count(self) -> int:
        return sum(len(row.terms) for row in self.handlers)

    def _payload(self) -> dict[str, Any]:
        handler_rows = [row.to_dict() for row in self.handlers]
        return {
            "schema_id": OFFXML_VALENCE_ASSIGNMENT_SCHEMA_ID,
            "profile_id": OFFXML_VALENCE_ASSIGNMENT_PROFILE_ID,
            "assigner_version": OFFXML_VALENCE_ASSIGNMENT_VERSION,
            "offxml_document_sha256": self.offxml_document_sha256,
            "system_sha256": self.system_sha256,
            "system_atom_count": self.system_atom_count,
            "handler_count": len(handler_rows),
            "handler_ids": [row["handler"] for row in handler_rows],
            "term_count": sum(row["assigned_tuple_count"] for row in handler_rows),
            "handlers": handler_rows,
            "required_coverage_handler_ids": list(
                OFFXML_VALENCE_REQUIRED_COVERAGE_HANDLERS
            ),
            "superseded_candidate_count": sum(
                row["superseded_candidate_count"] for row in handler_rows
            ),
            "configuration": dict(OFFXML_VALENCE_ASSIGNMENT_CONFIGURATION),
            "configuration_sha256": (
                OFFXML_VALENCE_ASSIGNMENT_CONFIGURATION_SHA256
            ),
            "scientific_blockers": list(OFFXML_VALENCE_ASSIGNMENT_BLOCKERS),
            **_CLAIM_FLAGS,
        }

    @property
    def assignment_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "assignment_sha256": self.assignment_sha256}


def _assign_handler(
    handler: str,
    parameters: Sequence[OffxmlSemanticParameter],
    system: AllAtomSystem,
    neighbors: Sequence[Sequence[int]],
) -> OffxmlValenceHandlerAssignment:
    topology_name = OFFXML_VALENCE_HANDLER_TOPOLOGY[handler]
    expected = set(_handler_topology(handler, system, neighbors))
    if len(expected) > OFFXML_VALENCE_ASSIGNMENT_MAX_TERMS:
        raise OffxmlValenceAssignmentError(
            f"{handler} topology exceeds its term bound"
        )
    winners: dict[tuple[int, ...], dict[str, Any]] = {}
    seen_ids: set[str] = set()
    for declaration_order, parameter in enumerate(parameters):
        if parameter.parameter_id in seen_ids:
            raise OffxmlValenceAssignmentError(
                f"{handler} declares duplicate parameter id "
                f"{parameter.parameter_id!r}"
            )
        seen_ids.add(parameter.parameter_id)
        try:
            query = parse_smirks_pattern(parameter.smirks)
            match_set = match_smirks_query(query, system)
        except (SmirksPatternParserError, SmirksSubgraphMatcherError) as exc:
            raise OffxmlValenceAssignmentError(
                f"{handler} parameter {parameter.parameter_id!r} could not be "
                "matched within the reviewed subset"
            ) from exc
        # One parameter can match the same canonical tuple through several
        # symmetric embeddings; collapse them so a single parameter never
        # supersedes itself.
        canonical_keys: list[tuple[int, ...]] = []
        for match in match_set.matches:
            key = _canonical_tuple(handler, match.mapped_atom_indices)
            if key in expected and key not in canonical_keys:
                canonical_keys.append(key)
        for key in canonical_keys:
            existing = winners.get(key)
            superseded = list(existing["superseded_parameter_ids"]) if existing else []
            if existing is not None:
                superseded.append(str(existing["parameter_id"]))
            winners[key] = {
                "parameter_id": parameter.parameter_id,
                "declaration_order": declaration_order,
                "smirks": parameter.smirks,
                "values": _parameter_values(parameter),
                "superseded_parameter_ids": superseded,
            }
    terms = tuple(
        OffxmlValenceTerm(
            handler=handler,
            topology=topology_name,
            atom_indices=key,
            parameter_id=str(winners[key]["parameter_id"]),
            declaration_order=int(winners[key]["declaration_order"]),
            smirks=str(winners[key]["smirks"]),
            values=dict(winners[key]["values"]),
            superseded_parameter_ids=tuple(
                str(value) for value in winners[key]["superseded_parameter_ids"]
            ),
        )
        for key in sorted(winners)
    )
    unassigned = tuple(sorted(expected - set(winners)))
    return OffxmlValenceHandlerAssignment(
        handler=handler,
        topology=topology_name,
        parameter_count=len(parameters),
        topology_tuple_count=len(expected),
        coverage_required=handler in OFFXML_VALENCE_REQUIRED_COVERAGE_HANDLERS,
        terms=terms,
        unassigned_atom_tuples=unassigned,
    )


def assign_offxml_valence_parameters(
    document: OffxmlSemanticDocument,
    system: AllAtomSystem,
) -> OffxmlValenceAssignment:
    """Assign every reviewed handler's parameters to one canonical system."""

    if not isinstance(document, OffxmlSemanticDocument):
        raise OffxmlValenceAssignmentError(
            "assignment requires a parsed OFFXML semantic document"
        )
    atoms = list(system.atoms)
    if not atoms:
        raise OffxmlValenceAssignmentError("canonical system declares no atoms")
    neighbors = _neighbors(system)
    handlers: list[OffxmlValenceHandlerAssignment] = []
    observed: set[str] = set()
    for section in document.handlers:
        if section.handler not in OFFXML_VALENCE_HANDLER_TOPOLOGY:
            continue
        observed.add(section.handler)
        handlers.append(
            _assign_handler(section.handler, section.parameters, system, neighbors)
        )
    missing = [
        handler
        for handler in OFFXML_VALENCE_REQUIRED_COVERAGE_HANDLERS
        if handler not in observed
    ]
    if missing:
        raise OffxmlValenceAssignmentError(
            f"OFFXML document omits required handler {missing[0]}"
        )
    incomplete = [
        row.handler
        for row in handlers
        if row.coverage_required and not row.coverage_complete
    ]
    if incomplete:
        raise OffxmlValenceAssignmentError(
            f"handler {incomplete[0]} leaves its topology partially assigned"
        )
    handlers.sort(key=lambda row: row.handler)
    from .serialization import canonical_system_sha256

    return OffxmlValenceAssignment(
        offxml_document_sha256=document.document_sha256,
        system_sha256=canonical_system_sha256(system),
        system_atom_count=len(atoms),
        handlers=tuple(handlers),
    )


def offxml_valence_assignment_document(
    assignment: OffxmlValenceAssignment,
) -> dict[str, Any]:
    return assignment.to_dict()


def require_offxml_valence_assignment_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a canonical assignment document without reassigning."""

    if not isinstance(payload, Mapping):
        raise OffxmlValenceAssignmentError(
            "valence assignment document must be a mapping"
        )
    document = dict(payload)
    if document.get("schema_id") != OFFXML_VALENCE_ASSIGNMENT_SCHEMA_ID:
        raise OffxmlValenceAssignmentError("unsupported valence assignment schema")
    declared = document.pop("assignment_sha256", None)
    if _sha256(document) != declared:
        raise OffxmlValenceAssignmentError(
            "valence assignment document digest is invalid"
        )
    for field in (
        "energies_or_forces_evaluated",
        "partial_charges_assigned",
        "atom_masses_assigned",
        "exclusions_and_one_four_scaling_applied",
        "scientifically_validated",
        "claim_safe",
    ):
        if document.get(field) is not False:
            raise OffxmlValenceAssignmentError(
                f"valence assignment document must keep {field}=false"
            )
    handlers = document.get("handlers")
    if not isinstance(handlers, list) or not handlers:
        raise OffxmlValenceAssignmentError(
            "valence assignment document must retain handler assignments"
        )
    for item in handlers:
        if not isinstance(item, Mapping):
            raise OffxmlValenceAssignmentError(
                "handler assignment must be a mapping"
            )
        handler = dict(item)
        handler_digest = handler.pop("handler_assignment_sha256", None)
        if _sha256(handler) != handler_digest:
            raise OffxmlValenceAssignmentError(
                "handler assignment digest is invalid"
            )
        if handler.get("coverage_required") is True and (
            handler.get("coverage_complete") is not True
        ):
            raise OffxmlValenceAssignmentError(
                "handler assignment publishes incomplete required coverage"
            )
        for entry in handler.get("terms", []):
            if not isinstance(entry, Mapping):
                raise OffxmlValenceAssignmentError("term row must be a mapping")
            term = dict(entry)
            term_digest = term.pop("term_sha256", None)
            if _sha256(term) != term_digest:
                raise OffxmlValenceAssignmentError("term row digest is invalid")
    return {**document, "assignment_sha256": declared}


def offxml_valence_handler_topology() -> Mapping[str, str]:
    return dict(OFFXML_VALENCE_HANDLER_TOPOLOGY)


__all__ = [
    "OFFXML_VALENCE_ASSIGNMENT_BLOCKERS",
    "OFFXML_VALENCE_ASSIGNMENT_CONFIGURATION",
    "OFFXML_VALENCE_ASSIGNMENT_CONFIGURATION_SHA256",
    "OFFXML_VALENCE_ASSIGNMENT_MAX_TERMS",
    "OFFXML_VALENCE_ASSIGNMENT_PROFILE_ID",
    "OFFXML_VALENCE_ASSIGNMENT_SCHEMA_ID",
    "OFFXML_VALENCE_ASSIGNMENT_VERSION",
    "OFFXML_VALENCE_HANDLER_SCHEMA_ID",
    "OFFXML_VALENCE_HANDLER_TOPOLOGY",
    "OFFXML_VALENCE_REQUIRED_COVERAGE_HANDLERS",
    "OFFXML_VALENCE_TERM_SCHEMA_ID",
    "OffxmlValenceAssignment",
    "OffxmlValenceAssignmentError",
    "OffxmlValenceHandlerAssignment",
    "OffxmlValenceTerm",
    "assign_offxml_valence_parameters",
    "offxml_valence_assignment_document",
    "offxml_valence_handler_topology",
    "require_offxml_valence_assignment_document",
]
