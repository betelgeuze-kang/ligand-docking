"""Fail-closed 1-2/1-3/1-4/1-5 exclusion and scaling derivation.

The valence assigner reads the ``vdW`` and ``Electrostatics`` section attributes
but never applies them: ``scale12``, ``scale13``, ``scale14`` and ``scale15``
sat in the parsed document while every nonbonded pair remained unscaled.

This module derives the topological separation of every atom pair from the
canonical bond graph -- shortest bonded path length 2, 3, 4, or 5-and-beyond --
and attaches the declared scale factor for that separation, once for vdW and
once for electrostatics.  A pair whose factor is exactly zero is recorded as
excluded; a nonzero factor below one is recorded as scaled.

Every scale attribute a handler is required to declare must be present and must
parse as a finite factor in [0, 1]; a missing or out-of-range attribute fails
closed rather than defaulting, because a silently assumed 1.0 would turn an
intended exclusion into a full interaction.

Derivation attaches declared factors to pairs.  It evaluates no energy, applies
no partial charge, and carries no calibration review, so results stay
claim-closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .models import AllAtomSystem
from .offxml_semantic_parser import OffxmlSemanticDocument


OFFXML_NONBONDED_PAIR_SCHEMA_ID = (
    "betelgeuze.engine_v2_offxml_nonbonded_pair/1.0.0"
)
OFFXML_NONBONDED_HANDLER_SCHEMA_ID = (
    "betelgeuze.engine_v2_offxml_nonbonded_handler_policy/1.0.0"
)
OFFXML_NONBONDED_EXCLUSIONS_SCHEMA_ID = (
    "betelgeuze.engine_v2_offxml_nonbonded_exclusions/1.0.0"
)
OFFXML_NONBONDED_EXCLUSIONS_PROFILE_ID = "offxml_nonbonded_exclusions/1.0.0"
OFFXML_NONBONDED_EXCLUSIONS_VERSION = "1.0.0"
OFFXML_NONBONDED_EXCLUSIONS_MAX_PAIRS = 131072

OFFXML_NONBONDED_SCALED_HANDLERS = ("vdW", "Electrostatics")
OFFXML_NONBONDED_SCALE_ATTRIBUTES = (
    "scale12",
    "scale13",
    "scale14",
    "scale15",
)
OFFXML_NONBONDED_SEPARATIONS = (
    "one_two",
    "one_three",
    "one_four",
    "one_five_or_greater",
)

_SEPARATION_BY_PATH_LENGTH = {
    1: "one_two",
    2: "one_three",
    3: "one_four",
}
_SCALE_ATTRIBUTE_BY_SEPARATION = {
    "one_two": "scale12",
    "one_three": "scale13",
    "one_four": "scale14",
    "one_five_or_greater": "scale15",
}

OFFXML_NONBONDED_EXCLUSIONS_CONFIGURATION = {
    "schema_id": (
        "betelgeuze.engine_v2_offxml_nonbonded_exclusions_configuration/1.0.0"
    ),
    "scaled_handlers": list(OFFXML_NONBONDED_SCALED_HANDLERS),
    "required_scale_attributes": list(OFFXML_NONBONDED_SCALE_ATTRIBUTES),
    "separations": list(OFFXML_NONBONDED_SEPARATIONS),
    "separation_source": "shortest_bonded_path_length_in_canonical_bond_graph",
    "missing_scale_attribute_fails_closed": True,
    "scale_factor_domain": "closed_unit_interval",
    "zero_factor_recorded_as_exclusion": True,
    "default_scale_assumed_when_absent": False,
    "intramolecular_pairs_only": True,
    "energies_evaluated": False,
    "partial_charges_assigned": False,
    "max_pairs": OFFXML_NONBONDED_EXCLUSIONS_MAX_PAIRS,
}
OFFXML_NONBONDED_EXCLUSIONS_CONFIGURATION_SHA256 = hashlib.sha256(
    json.dumps(
        OFFXML_NONBONDED_EXCLUSIONS_CONFIGURATION,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
).hexdigest()

OFFXML_NONBONDED_EXCLUSIONS_BLOCKERS = (
    "declared_scale_factors_not_evaluated_in_any_energy_term",
    "partial_charge_and_atom_mass_assignment_not_implemented",
    "intermolecular_and_periodic_exclusion_policy_not_derived",
    "parameter_value_calibration_not_reviewed",
    "independent_force_and_energy_validation_missing",
    "independent_scientific_review_missing",
    "validated_refinement_claim_not_authorized",
)

_CLAIM_FLAGS = {
    "exclusions_and_one_four_scaling_derived": True,
    "every_intramolecular_pair_classified": True,
    "declared_scale_factors_read_not_assumed": True,
    "energies_evaluated": False,
    "partial_charges_assigned": False,
    "periodic_exclusion_policy_derived": False,
    "independent_external_review_present": False,
    "benchmark_validated": False,
    "scientifically_validated": False,
    "claim_safe": False,
}


class OffxmlNonbondedExclusionsError(ValueError):
    """A scale attribute, topology, or pair projection is invalid."""


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


def _scale_factor(handler: str, attribute: str, raw: object) -> float:
    if not isinstance(raw, str) or not raw.strip():
        raise OffxmlNonbondedExclusionsError(
            f"{handler}.{attribute} is missing from the parsed document"
        )
    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise OffxmlNonbondedExclusionsError(
            f"{handler}.{attribute} is not a finite decimal factor"
        ) from exc
    if value != value or value in {float("inf"), float("-inf")}:
        raise OffxmlNonbondedExclusionsError(
            f"{handler}.{attribute} is not a finite decimal factor"
        )
    if not 0.0 <= value <= 1.0:
        raise OffxmlNonbondedExclusionsError(
            f"{handler}.{attribute} factor {value!r} is outside [0, 1]"
        )
    return value


def _handler_policy(
    handler: str,
    section_attributes: Mapping[str, str],
) -> dict[str, Any]:
    factors: dict[str, float] = {}
    for separation in OFFXML_NONBONDED_SEPARATIONS:
        attribute = _SCALE_ATTRIBUTE_BY_SEPARATION[separation]
        factors[separation] = _scale_factor(
            handler,
            attribute,
            section_attributes.get(attribute),
        )
    return {
        "handler": handler,
        "factors": factors,
    }


def _neighbors(system: AllAtomSystem) -> tuple[tuple[int, ...], ...]:
    atom_count = len(system.atoms)
    sets: list[set[int]] = [set() for _ in range(atom_count)]
    for bond in system.bonds:
        i = int(bond.atom_i)
        j = int(bond.atom_j)
        if not 0 <= i < atom_count or not 0 <= j < atom_count or i == j:
            raise OffxmlNonbondedExclusionsError(
                "canonical bond references an invalid atom index"
            )
        sets[i].add(j)
        sets[j].add(i)
    return tuple(tuple(sorted(row)) for row in sets)


def _shortest_path_lengths(
    start: int,
    neighbors: Sequence[Sequence[int]],
) -> dict[int, int]:
    distances = {start: 0}
    frontier = [start]
    depth = 0
    while frontier and depth < 4:
        depth += 1
        following: list[int] = []
        for current in frontier:
            for neighbor in neighbors[current]:
                if neighbor in distances:
                    continue
                distances[neighbor] = depth
                following.append(neighbor)
        frontier = following
    return distances


@dataclass(frozen=True, slots=True, repr=False)
class OffxmlNonbondedPair:
    """One intramolecular atom pair with its separation and scale factors."""

    atom_i: int
    atom_j: int
    separation: str
    bonded_path_length: int | None
    factors: Mapping[str, float]

    def __repr__(self) -> str:
        return (
            "OffxmlNonbondedPair("
            f"atoms=({self.atom_i}, {self.atom_j}), "
            f"separation={self.separation!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        factors = dict(self.factors)
        projection = {
            "schema_id": OFFXML_NONBONDED_PAIR_SCHEMA_ID,
            "atom_i": self.atom_i,
            "atom_j": self.atom_j,
            "separation": self.separation,
            "bonded_path_length": self.bonded_path_length,
            "scale_attribute": _SCALE_ATTRIBUTE_BY_SEPARATION[self.separation],
            "factors": {
                handler: float(factors[handler]).hex()
                for handler in sorted(factors)
            },
            "excluded_handler_ids": sorted(
                handler for handler in factors if factors[handler] == 0.0
            ),
            "scaled_handler_ids": sorted(
                handler
                for handler in factors
                if 0.0 < factors[handler] < 1.0
            ),
            "full_strength_handler_ids": sorted(
                handler for handler in factors if factors[handler] == 1.0
            ),
            "factors_evaluated_in_energy_term": False,
        }
        return {**projection, "pair_sha256": _sha256(projection)}


@dataclass(frozen=True, slots=True, repr=False)
class OffxmlNonbondedExclusions:
    """Canonical, claim-closed exclusion and scaling projection."""

    offxml_document_sha256: str
    system_sha256: str
    system_atom_count: int
    handler_policies: tuple[dict[str, Any], ...]
    pairs: tuple[OffxmlNonbondedPair, ...]

    def __repr__(self) -> str:
        return f"OffxmlNonbondedExclusions(pairs={len(self.pairs)})"

    def _handler_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for policy in self.handler_policies:
            factors = dict(policy["factors"])
            projection = {
                "schema_id": OFFXML_NONBONDED_HANDLER_SCHEMA_ID,
                "handler": str(policy["handler"]),
                "factors": {
                    separation: float(factors[separation]).hex()
                    for separation in OFFXML_NONBONDED_SEPARATIONS
                },
                "scale_attributes": {
                    separation: _SCALE_ATTRIBUTE_BY_SEPARATION[separation]
                    for separation in OFFXML_NONBONDED_SEPARATIONS
                },
                "excluded_separations": [
                    separation
                    for separation in OFFXML_NONBONDED_SEPARATIONS
                    if factors[separation] == 0.0
                ],
                "scaled_separations": [
                    separation
                    for separation in OFFXML_NONBONDED_SEPARATIONS
                    if 0.0 < factors[separation] < 1.0
                ],
                "declared_scale_attributes_complete": True,
            }
            rows.append(
                {**projection, "handler_policy_sha256": _sha256(projection)}
            )
        return rows

    def _payload(self) -> dict[str, Any]:
        handler_rows = self._handler_rows()
        pair_rows = [row.to_dict() for row in self.pairs]
        separation_counts = {
            separation: sum(
                1 for row in pair_rows if row["separation"] == separation
            )
            for separation in OFFXML_NONBONDED_SEPARATIONS
        }
        return {
            "schema_id": OFFXML_NONBONDED_EXCLUSIONS_SCHEMA_ID,
            "profile_id": OFFXML_NONBONDED_EXCLUSIONS_PROFILE_ID,
            "deriver_version": OFFXML_NONBONDED_EXCLUSIONS_VERSION,
            "offxml_document_sha256": self.offxml_document_sha256,
            "system_sha256": self.system_sha256,
            "system_atom_count": self.system_atom_count,
            "handler_ids": [row["handler"] for row in handler_rows],
            "handler_policies": handler_rows,
            "pair_count": len(pair_rows),
            "expected_pair_count": (
                self.system_atom_count * (self.system_atom_count - 1) // 2
            ),
            "separation_counts": separation_counts,
            "excluded_pair_counts": {
                handler: sum(
                    1
                    for row in pair_rows
                    if handler in row["excluded_handler_ids"]
                )
                for handler in OFFXML_NONBONDED_SCALED_HANDLERS
            },
            "scaled_pair_counts": {
                handler: sum(
                    1 for row in pair_rows if handler in row["scaled_handler_ids"]
                )
                for handler in OFFXML_NONBONDED_SCALED_HANDLERS
            },
            "pairs": pair_rows,
            "configuration": dict(OFFXML_NONBONDED_EXCLUSIONS_CONFIGURATION),
            "configuration_sha256": (
                OFFXML_NONBONDED_EXCLUSIONS_CONFIGURATION_SHA256
            ),
            "scientific_blockers": list(OFFXML_NONBONDED_EXCLUSIONS_BLOCKERS),
            **_CLAIM_FLAGS,
        }

    @property
    def exclusions_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "exclusions_sha256": self.exclusions_sha256}


def derive_offxml_nonbonded_exclusions(
    document: OffxmlSemanticDocument,
    system: AllAtomSystem,
) -> OffxmlNonbondedExclusions:
    """Derive every intramolecular pair's separation and declared scale factors."""

    if not isinstance(document, OffxmlSemanticDocument):
        raise OffxmlNonbondedExclusionsError(
            "derivation requires a parsed OFFXML semantic document"
        )
    atoms = list(system.atoms)
    if not atoms:
        raise OffxmlNonbondedExclusionsError("canonical system declares no atoms")
    pair_total = len(atoms) * (len(atoms) - 1) // 2
    if pair_total > OFFXML_NONBONDED_EXCLUSIONS_MAX_PAIRS:
        raise OffxmlNonbondedExclusionsError(
            "canonical system exceeds its nonbonded pair bound"
        )
    sections = {row.handler: dict(row.section_attributes) for row in document.handlers}
    policies: list[dict[str, Any]] = []
    for handler in OFFXML_NONBONDED_SCALED_HANDLERS:
        if handler not in sections:
            raise OffxmlNonbondedExclusionsError(
                f"OFFXML document omits the {handler} section"
            )
        policies.append(_handler_policy(handler, sections[handler]))
    neighbors = _neighbors(system)
    pairs: list[OffxmlNonbondedPair] = []
    for first in range(len(atoms)):
        distances = _shortest_path_lengths(first, neighbors)
        for second in range(first + 1, len(atoms)):
            path_length = distances.get(second)
            separation = (
                _SEPARATION_BY_PATH_LENGTH.get(path_length)
                if path_length is not None
                else None
            ) or "one_five_or_greater"
            pairs.append(
                OffxmlNonbondedPair(
                    atom_i=first,
                    atom_j=second,
                    separation=separation,
                    bonded_path_length=path_length,
                    factors={
                        str(policy["handler"]): float(
                            dict(policy["factors"])[separation]
                        )
                        for policy in policies
                    },
                )
            )
    if len(pairs) != pair_total:  # pragma: no cover - defensive
        raise OffxmlNonbondedExclusionsError(
            "pair enumeration did not cover every intramolecular pair"
        )
    from .serialization import canonical_system_sha256

    return OffxmlNonbondedExclusions(
        offxml_document_sha256=document.document_sha256,
        system_sha256=canonical_system_sha256(system),
        system_atom_count=len(atoms),
        handler_policies=tuple(policies),
        pairs=tuple(pairs),
    )


def offxml_nonbonded_exclusions_document(
    exclusions: OffxmlNonbondedExclusions,
) -> dict[str, Any]:
    return exclusions.to_dict()


def require_offxml_nonbonded_exclusions_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a canonical exclusion document without rederiving it."""

    if not isinstance(payload, Mapping):
        raise OffxmlNonbondedExclusionsError(
            "nonbonded exclusion document must be a mapping"
        )
    document = dict(payload)
    if document.get("schema_id") != OFFXML_NONBONDED_EXCLUSIONS_SCHEMA_ID:
        raise OffxmlNonbondedExclusionsError(
            "unsupported nonbonded exclusion schema"
        )
    declared = document.pop("exclusions_sha256", None)
    if _sha256(document) != declared:
        raise OffxmlNonbondedExclusionsError(
            "nonbonded exclusion document digest is invalid"
        )
    for field in (
        "energies_evaluated",
        "partial_charges_assigned",
        "periodic_exclusion_policy_derived",
        "scientifically_validated",
        "claim_safe",
    ):
        if document.get(field) is not False:
            raise OffxmlNonbondedExclusionsError(
                f"nonbonded exclusion document must keep {field}=false"
            )
    if document.get("pair_count") != document.get("expected_pair_count"):
        raise OffxmlNonbondedExclusionsError(
            "nonbonded exclusion document omits intramolecular pairs"
        )
    handlers = document.get("handler_policies")
    if not isinstance(handlers, list) or len(handlers) != len(
        OFFXML_NONBONDED_SCALED_HANDLERS
    ):
        raise OffxmlNonbondedExclusionsError(
            "nonbonded exclusion document must retain every handler policy"
        )
    for item in handlers:
        if not isinstance(item, Mapping):
            raise OffxmlNonbondedExclusionsError(
                "handler policy must be a mapping"
            )
        handler = dict(item)
        handler_digest = handler.pop("handler_policy_sha256", None)
        if _sha256(handler) != handler_digest:
            raise OffxmlNonbondedExclusionsError(
                "handler policy digest is invalid"
            )
    pairs = document.get("pairs")
    if not isinstance(pairs, list):
        raise OffxmlNonbondedExclusionsError(
            "nonbonded exclusion document must retain pair rows"
        )
    for item in pairs:
        if not isinstance(item, Mapping):
            raise OffxmlNonbondedExclusionsError("pair row must be a mapping")
        pair = dict(item)
        pair_digest = pair.pop("pair_sha256", None)
        if _sha256(pair) != pair_digest:
            raise OffxmlNonbondedExclusionsError("pair row digest is invalid")
        if pair.get("separation") not in OFFXML_NONBONDED_SEPARATIONS:
            raise OffxmlNonbondedExclusionsError(
                "pair row declares an unreviewed separation"
            )
    return {**document, "exclusions_sha256": declared}


def offxml_nonbonded_scale_attributes() -> Mapping[str, str]:
    return dict(_SCALE_ATTRIBUTE_BY_SEPARATION)


__all__ = [
    "OFFXML_NONBONDED_EXCLUSIONS_BLOCKERS",
    "OFFXML_NONBONDED_EXCLUSIONS_CONFIGURATION",
    "OFFXML_NONBONDED_EXCLUSIONS_CONFIGURATION_SHA256",
    "OFFXML_NONBONDED_EXCLUSIONS_MAX_PAIRS",
    "OFFXML_NONBONDED_EXCLUSIONS_PROFILE_ID",
    "OFFXML_NONBONDED_EXCLUSIONS_SCHEMA_ID",
    "OFFXML_NONBONDED_EXCLUSIONS_VERSION",
    "OFFXML_NONBONDED_HANDLER_SCHEMA_ID",
    "OFFXML_NONBONDED_PAIR_SCHEMA_ID",
    "OFFXML_NONBONDED_SCALED_HANDLERS",
    "OFFXML_NONBONDED_SCALE_ATTRIBUTES",
    "OFFXML_NONBONDED_SEPARATIONS",
    "OffxmlNonbondedExclusions",
    "OffxmlNonbondedExclusionsError",
    "OffxmlNonbondedPair",
    "derive_offxml_nonbonded_exclusions",
    "offxml_nonbonded_exclusions_document",
    "offxml_nonbonded_scale_attributes",
    "require_offxml_nonbonded_exclusions_document",
]
