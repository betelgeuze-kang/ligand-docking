"""Fail-closed parser for the reviewed SMIRKS subset.

The OFFXML semantic parser reads each parameter's SMIRKS pattern as opaque text.
Nothing decomposed that text, so no downstream stage could reason about which
atoms a parameter is even shaped to match.

This module parses a bounded SMIRKS subset into a typed query graph: bracketed
atom expressions with element, connectivity, ring, aromaticity, charge and
hydrogen-count primitives, explicit bond expressions between them, mapping
indices, and parenthesised branches.  Every supported primitive is enumerated;
any token outside the reviewed subset fails closed instead of being ignored,
because a silently dropped primitive would widen a parameter's match set.

Parsing is structural only.  It builds a query, not a match: no molecule is
traversed and no parameter is assigned, so every result stays claim-closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any


SMIRKS_ATOM_EXPRESSION_SCHEMA_ID = (
    "betelgeuze.engine_v2_smirks_atom_expression/1.0.0"
)
SMIRKS_BOND_EXPRESSION_SCHEMA_ID = (
    "betelgeuze.engine_v2_smirks_bond_expression/1.0.0"
)
SMIRKS_QUERY_SCHEMA_ID = "betelgeuze.engine_v2_smirks_query/1.0.0"
SMIRKS_PATTERN_PARSER_PROFILE_ID = "smirks_pattern_parser/1.0.0"
SMIRKS_PATTERN_PARSER_VERSION = "1.0.0"
SMIRKS_PATTERN_MAX_BYTES = 512
SMIRKS_PATTERN_MAX_ATOMS = 32
SMIRKS_PATTERN_MAX_BONDS = 64
SMIRKS_PATTERN_MAX_MAP_INDEX = 8

# Bond primitives the reviewed subset understands, in canonical order.
SMIRKS_SUPPORTED_BOND_PRIMITIVES = {
    "-": "single",
    "=": "double",
    "#": "triple",
    ":": "aromatic",
    "~": "any",
}

# Atom primitive kinds the reviewed subset understands.
SMIRKS_SUPPORTED_ATOM_PRIMITIVE_KINDS = (
    "any_atom",
    "atomic_number",
    "aromatic",
    "aliphatic",
    "connectivity",
    "explicit_degree",
    "total_hydrogen_count",
    "ring_membership_count",
    "ring_size",
    "formal_charge",
)

SMIRKS_PATTERN_PARSER_CONFIGURATION = {
    "schema_id": (
        "betelgeuze.engine_v2_smirks_pattern_parser_configuration/1.0.0"
    ),
    "supported_bond_primitives": sorted(SMIRKS_SUPPORTED_BOND_PRIMITIVES),
    "supported_atom_primitive_kinds": list(
        SMIRKS_SUPPORTED_ATOM_PRIMITIVE_KINDS
    ),
    "bracketed_atom_expressions_required": True,
    "implicit_bond_between_adjacent_atoms": "single_or_aromatic",
    "atom_primitive_combination": "conjunction_only_high_precedence_and",
    "disjunction_supported": False,
    "negation_supported": False,
    "recursive_smarts_supported": False,
    "ring_closure_bonds_supported": False,
    "unknown_token_fails_closed": True,
    "max_atoms": SMIRKS_PATTERN_MAX_ATOMS,
    "max_bonds": SMIRKS_PATTERN_MAX_BONDS,
    "max_map_index": SMIRKS_PATTERN_MAX_MAP_INDEX,
    "molecules_traversed": False,
    "parameters_assigned": False,
}
SMIRKS_PATTERN_PARSER_CONFIGURATION_SHA256 = hashlib.sha256(
    json.dumps(
        SMIRKS_PATTERN_PARSER_CONFIGURATION,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
).hexdigest()

SMIRKS_PATTERN_PARSER_BLOCKERS = (
    "reviewed_subset_excludes_disjunction_negation_and_recursive_smarts",
    "ring_closure_bonds_not_supported",
    "query_is_structural_and_not_matched_against_molecules",
    "atom_typing_and_parameter_assignment_not_implemented",
    "independent_scientific_review_missing",
    "validated_refinement_claim_not_authorized",
)

_CLAIM_FLAGS = {
    "pattern_parsed": True,
    "every_primitive_recognized": True,
    "molecules_traversed": False,
    "atom_typing_implemented": False,
    "parameters_assigned": False,
    "scientifically_validated": False,
    "claim_safe": False,
}

_PRIMITIVE_RE = re.compile(
    r"""
    (?P<any_atom>\*)
  | \#(?P<atomic_number>[1-9][0-9]{0,2})
  | (?P<aromatic>a)
  | (?P<aliphatic>A)
  | X(?P<connectivity>[0-9])
  | D(?P<explicit_degree>[0-9])
  | H(?P<total_hydrogen_count>[0-9])
  | R(?P<ring_membership_count>[0-9])
  | r(?P<ring_size>[3-9]|1[0-9])
  | (?P<formal_charge>[+-](?:[0-9]|[+-]*))
    """,
    re.VERBOSE,
)


class SmirksPatternParserError(ValueError):
    """A SMIRKS pattern uses an unsupported token or malformed structure."""


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


def _parse_formal_charge(token: str) -> int:
    sign = 1 if token[0] == "+" else -1
    remainder = token[1:]
    if not remainder:
        return sign
    if remainder.isdigit():
        return sign * int(remainder)
    if set(remainder) == {token[0]}:
        return sign * (len(remainder) + 1)
    raise SmirksPatternParserError(
        f"formal-charge primitive {token!r} is not in the reviewed subset"
    )


def _parse_atom_primitives(body: str) -> tuple[dict[str, Any], ...]:
    if not body:
        raise SmirksPatternParserError("atom expression is empty")
    primitives: list[dict[str, Any]] = []
    position = 0
    while position < len(body):
        match = _PRIMITIVE_RE.match(body, position)
        if match is None:
            raise SmirksPatternParserError(
                f"atom primitive at {body[position:position + 4]!r} is not in "
                "the reviewed subset"
            )
        kind = match.lastgroup
        raw = match.group(0)
        if kind is None:  # pragma: no cover - regex always names a group
            raise SmirksPatternParserError("atom primitive is unnamed")
        if kind in {"any_atom", "aromatic", "aliphatic"}:
            value: int | None = None
        elif kind == "formal_charge":
            value = _parse_formal_charge(raw)
        else:
            value = int(match.group(kind))
        primitives.append({"kind": kind, "raw": raw, "value": value})
        position = match.end()
    return tuple(primitives)


@dataclass(frozen=True, slots=True, repr=False)
class SmirksAtomExpression:
    """One bracketed atom expression with its conjunctive primitives."""

    ordinal: int
    raw: str
    map_index: int | None
    primitives: tuple[dict[str, Any], ...]

    def __repr__(self) -> str:
        return (
            "SmirksAtomExpression("
            f"ordinal={self.ordinal}, map_index={self.map_index!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        projection = {
            "schema_id": SMIRKS_ATOM_EXPRESSION_SCHEMA_ID,
            "ordinal": self.ordinal,
            "raw": self.raw,
            "map_index": self.map_index,
            "mapped": self.map_index is not None,
            "primitive_count": len(self.primitives),
            "primitives": [dict(row) for row in self.primitives],
            "primitive_kinds": sorted({str(row["kind"]) for row in self.primitives}),
            "matches_any_atom": any(
                row["kind"] == "any_atom" for row in self.primitives
            ),
        }
        return {**projection, "atom_expression_sha256": _sha256(projection)}


@dataclass(frozen=True, slots=True, repr=False)
class SmirksBondExpression:
    """One bond between two parsed atom expressions."""

    ordinal: int
    atom_i: int
    atom_j: int
    raw: str
    primitive: str
    explicit: bool

    def __repr__(self) -> str:
        return (
            "SmirksBondExpression("
            f"ordinal={self.ordinal}, primitive={self.primitive!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        projection = {
            "schema_id": SMIRKS_BOND_EXPRESSION_SCHEMA_ID,
            "ordinal": self.ordinal,
            "atom_i": self.atom_i,
            "atom_j": self.atom_j,
            "raw": self.raw,
            "primitive": self.primitive,
            "explicit_in_pattern": self.explicit,
        }
        return {**projection, "bond_expression_sha256": _sha256(projection)}


@dataclass(frozen=True, slots=True, repr=False)
class SmirksQuery:
    """Canonical, claim-closed structural projection of one SMIRKS pattern."""

    smirks: str
    atoms: tuple[SmirksAtomExpression, ...]
    bonds: tuple[SmirksBondExpression, ...]

    def __repr__(self) -> str:
        return (
            f"SmirksQuery(atoms={len(self.atoms)}, bonds={len(self.bonds)})"
        )

    @property
    def mapped_indices(self) -> tuple[int, ...]:
        return tuple(
            sorted(row.map_index for row in self.atoms if row.map_index is not None)
        )

    def _payload(self) -> dict[str, Any]:
        atom_rows = [row.to_dict() for row in self.atoms]
        bond_rows = [row.to_dict() for row in self.bonds]
        return {
            "schema_id": SMIRKS_QUERY_SCHEMA_ID,
            "profile_id": SMIRKS_PATTERN_PARSER_PROFILE_ID,
            "parser_version": SMIRKS_PATTERN_PARSER_VERSION,
            "smirks": self.smirks,
            "atom_count": len(atom_rows),
            "bond_count": len(bond_rows),
            "atoms": atom_rows,
            "bonds": bond_rows,
            "mapped_atom_count": len(self.mapped_indices),
            "mapped_indices": list(self.mapped_indices),
            "every_atom_mapped": len(self.mapped_indices) == len(atom_rows),
            "primitive_kinds": sorted(
                {kind for row in atom_rows for kind in row["primitive_kinds"]}
            ),
            "bond_primitives": sorted({row["primitive"] for row in bond_rows}),
            "configuration": dict(SMIRKS_PATTERN_PARSER_CONFIGURATION),
            "configuration_sha256": SMIRKS_PATTERN_PARSER_CONFIGURATION_SHA256,
            "scientific_blockers": list(SMIRKS_PATTERN_PARSER_BLOCKERS),
            **_CLAIM_FLAGS,
        }

    @property
    def query_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "query_sha256": self.query_sha256}


def _require_pattern(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > SMIRKS_PATTERN_MAX_BYTES
        or any(character in "\r\n\x00\t " for character in value)
    ):
        raise SmirksPatternParserError(
            "SMIRKS pattern must be bounded whitespace-free text"
        )
    return value


def parse_smirks_pattern(smirks: object) -> SmirksQuery:
    """Parse one SMIRKS pattern from the reviewed subset into a typed query."""

    pattern = _require_pattern(smirks)
    atoms: list[SmirksAtomExpression] = []
    bonds: list[SmirksBondExpression] = []
    branch_stack: list[int] = []
    previous: int | None = None
    pending_bond: tuple[str, str] | None = None
    position = 0

    while position < len(pattern):
        character = pattern[position]
        if character == "[":
            end = pattern.find("]", position)
            if end < 0:
                raise SmirksPatternParserError(
                    "atom expression is not closed with ]"
                )
            body = pattern[position + 1 : end]
            map_index: int | None = None
            if ":" in body:
                body, _, raw_index = body.rpartition(":")
                if not raw_index.isdigit():
                    raise SmirksPatternParserError(
                        "atom map index must be a decimal integer"
                    )
                map_index = int(raw_index)
                if not 1 <= map_index <= SMIRKS_PATTERN_MAX_MAP_INDEX:
                    raise SmirksPatternParserError(
                        "atom map index is outside the reviewed bound"
                    )
            ordinal = len(atoms)
            atoms.append(
                SmirksAtomExpression(
                    ordinal=ordinal,
                    raw=pattern[position : end + 1],
                    map_index=map_index,
                    primitives=_parse_atom_primitives(body),
                )
            )
            if len(atoms) > SMIRKS_PATTERN_MAX_ATOMS:
                raise SmirksPatternParserError(
                    "SMIRKS pattern exceeds its atom bound"
                )
            if previous is not None:
                raw, primitive = pending_bond or ("", "single_or_aromatic")
                bonds.append(
                    SmirksBondExpression(
                        ordinal=len(bonds),
                        atom_i=previous,
                        atom_j=ordinal,
                        raw=raw,
                        primitive=primitive,
                        explicit=pending_bond is not None,
                    )
                )
                if len(bonds) > SMIRKS_PATTERN_MAX_BONDS:
                    raise SmirksPatternParserError(
                        "SMIRKS pattern exceeds its bond bound"
                    )
            elif pending_bond is not None:
                raise SmirksPatternParserError(
                    "bond primitive precedes its first atom"
                )
            pending_bond = None
            previous = ordinal
            position = end + 1
            continue
        if character in SMIRKS_SUPPORTED_BOND_PRIMITIVES:
            if pending_bond is not None:
                raise SmirksPatternParserError(
                    "two bond primitives appear in sequence"
                )
            pending_bond = (character, SMIRKS_SUPPORTED_BOND_PRIMITIVES[character])
            position += 1
            continue
        if character == "(":
            if previous is None:
                raise SmirksPatternParserError("branch opens before its first atom")
            if pending_bond is not None:
                raise SmirksPatternParserError(
                    "branch opens after a dangling bond primitive"
                )
            branch_stack.append(previous)
            position += 1
            continue
        if character == ")":
            if not branch_stack:
                raise SmirksPatternParserError("branch closes without opening")
            if pending_bond is not None:
                raise SmirksPatternParserError(
                    "branch closes after a dangling bond primitive"
                )
            previous = branch_stack.pop()
            position += 1
            continue
        raise SmirksPatternParserError(
            f"token {character!r} is not in the reviewed SMIRKS subset"
        )

    if branch_stack:
        raise SmirksPatternParserError("branch is not closed")
    if pending_bond is not None:
        raise SmirksPatternParserError("pattern ends with a dangling bond primitive")
    if not atoms:
        raise SmirksPatternParserError("pattern declares no atom expression")
    mapped = [row.map_index for row in atoms if row.map_index is not None]
    if len(set(mapped)) != len(mapped):
        raise SmirksPatternParserError("atom map indices must be unique")
    return SmirksQuery(
        smirks=pattern,
        atoms=tuple(atoms),
        bonds=tuple(bonds),
    )


def parse_smirks_patterns(
    patterns: Sequence[object],
) -> tuple[SmirksQuery, ...]:
    """Parse an ordered sequence of SMIRKS patterns, failing closed on any one."""

    return tuple(parse_smirks_pattern(pattern) for pattern in patterns)


def smirks_query_document(query: SmirksQuery) -> dict[str, Any]:
    return query.to_dict()


def require_smirks_query_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a canonical SMIRKS query document without re-parsing it."""

    if not isinstance(payload, Mapping):
        raise SmirksPatternParserError("SMIRKS query document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != SMIRKS_QUERY_SCHEMA_ID:
        raise SmirksPatternParserError("unsupported SMIRKS query schema")
    declared = document.pop("query_sha256", None)
    if _sha256(document) != declared:
        raise SmirksPatternParserError("SMIRKS query document digest is invalid")
    for field in (
        "molecules_traversed",
        "atom_typing_implemented",
        "parameters_assigned",
        "scientifically_validated",
        "claim_safe",
    ):
        if document.get(field) is not False:
            raise SmirksPatternParserError(
                f"SMIRKS query document must keep {field}=false"
            )
    atoms = document.get("atoms")
    if not isinstance(atoms, list) or not atoms:
        raise SmirksPatternParserError(
            "SMIRKS query document must retain atom expressions"
        )
    for item in atoms:
        if not isinstance(item, Mapping):
            raise SmirksPatternParserError("atom expression must be a mapping")
        atom = dict(item)
        atom_digest = atom.pop("atom_expression_sha256", None)
        if _sha256(atom) != atom_digest:
            raise SmirksPatternParserError("atom expression digest is invalid")
        for primitive in atom.get("primitives", []):
            kind = dict(primitive).get("kind")
            if kind not in SMIRKS_SUPPORTED_ATOM_PRIMITIVE_KINDS:
                raise SmirksPatternParserError(
                    "atom expression declares an unsupported primitive kind"
                )
    for item in document.get("bonds", []):
        if not isinstance(item, Mapping):
            raise SmirksPatternParserError("bond expression must be a mapping")
        bond = dict(item)
        bond_digest = bond.pop("bond_expression_sha256", None)
        if _sha256(bond) != bond_digest:
            raise SmirksPatternParserError("bond expression digest is invalid")
    return {**document, "query_sha256": declared}


def smirks_supported_bond_primitives() -> Mapping[str, str]:
    return dict(SMIRKS_SUPPORTED_BOND_PRIMITIVES)


__all__ = [
    "SMIRKS_ATOM_EXPRESSION_SCHEMA_ID",
    "SMIRKS_BOND_EXPRESSION_SCHEMA_ID",
    "SMIRKS_PATTERN_MAX_ATOMS",
    "SMIRKS_PATTERN_MAX_BONDS",
    "SMIRKS_PATTERN_MAX_BYTES",
    "SMIRKS_PATTERN_MAX_MAP_INDEX",
    "SMIRKS_PATTERN_PARSER_BLOCKERS",
    "SMIRKS_PATTERN_PARSER_CONFIGURATION",
    "SMIRKS_PATTERN_PARSER_CONFIGURATION_SHA256",
    "SMIRKS_PATTERN_PARSER_PROFILE_ID",
    "SMIRKS_PATTERN_PARSER_VERSION",
    "SMIRKS_QUERY_SCHEMA_ID",
    "SMIRKS_SUPPORTED_ATOM_PRIMITIVE_KINDS",
    "SMIRKS_SUPPORTED_BOND_PRIMITIVES",
    "SmirksAtomExpression",
    "SmirksBondExpression",
    "SmirksPatternParserError",
    "SmirksQuery",
    "parse_smirks_pattern",
    "parse_smirks_patterns",
    "require_smirks_query_document",
    "smirks_query_document",
    "smirks_supported_bond_primitives",
]
