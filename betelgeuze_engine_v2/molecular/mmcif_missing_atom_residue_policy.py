"""Bounded preparation admission for source-declared observation gaps.

The PDBx/mmCIF ``_pdbx_unobs_or_zero_occ_residues`` and
``_pdbx_unobs_or_zero_occ_atoms`` categories report residues or atoms that are
unobserved (``occupancy_flag = 1``) or have zero occupancy
(``occupancy_flag = 0``).  This module binds the complete selected declaration
rows and interprets only that controlled flag for a fail-closed preparation
admission decision.

The absence of either optional declaration category is not evidence that a
structure is complete.  It only means that this source-declaration gate has no
row to block.  When either category is present, bounded preparation remains
disabled; this policy does not repair atoms or residues, infer coordinates,
select conformers, or assess scientific missingness.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from types import MappingProxyType
from typing import Any, Mapping

from .mmcif_syntax import CifLoop, CifToken, parse_cif_block
from .mmcif_zero_occupancy import (
    ATOM_CATEGORY,
    MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS,
    RESIDUE_CATEGORY,
)


MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_missing_atom_residue_policy_projection/1.0.0"
)
MMCIF_MISSING_ATOM_RESIDUE_POLICY_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_missing_atom_residue_policy_source_binding/1.0.0"
)
MMCIF_MISSING_ATOM_RESIDUE_POLICY_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_missing_atom_residue_policy_document/1.0.0"
)
MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROFILE_ID = (
    "bounded_mmcif_source_declared_observation_gap_preparation_admission/1.0.0"
)
MMCIF_MISSING_ATOM_RESIDUE_POLICY_PARSER_VERSION = "1.0.0"

MAX_MMCIF_MISSING_ATOM_RESIDUE_POLICY_ROWS = 100_000
MAX_MMCIF_MISSING_ATOM_RESIDUE_POLICY_TOKEN_CHARS = 256

MMCIF_MISSING_ATOM_RESIDUE_POLICY_CATEGORIES = (
    RESIDUE_CATEGORY,
    ATOM_CATEGORY,
)
MMCIF_MISSING_ATOM_RESIDUE_POLICY_DICTIONARY_CATEGORIES: Mapping[str, str] = (
    MappingProxyType(
        {
            RESIDUE_CATEGORY: (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Categories/pdbx_unobs_or_zero_occ_residues.html"
            ),
            ATOM_CATEGORY: (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Categories/pdbx_unobs_or_zero_occ_atoms.html"
            ),
        }
    )
)
MMCIF_MISSING_ATOM_RESIDUE_POLICY_DICTIONARY_ITEMS: Mapping[str, str] = (
    MappingProxyType(
        {
            f"{RESIDUE_CATEGORY}.occupancy_flag": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Items/_pdbx_unobs_or_zero_occ_residues.occupancy_flag.html"
            ),
            f"{ATOM_CATEGORY}.occupancy_flag": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Items/_pdbx_unobs_or_zero_occ_atoms.occupancy_flag.html"
            ),
        }
    )
)

_REQUIRED_HEADERS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        RESIDUE_CATEGORY: MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS,
        ATOM_CATEGORY: MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS,
    }
)
_DECLARATION_KIND = {RESIDUE_CATEGORY: "residue", ATOM_CATEGORY: "atom"}
_FLAG_HEADER = {
    RESIDUE_CATEGORY: f"{RESIDUE_CATEGORY}.occupancy_flag",
    ATOM_CATEGORY: f"{ATOM_CATEGORY}.occupancy_flag",
}
_INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_STATUS = "allowed_no_source_observation_gap_declarations"
_BLOCKED_STATUS = "explicitly_unsupported_source_declared_observation_gaps"
_STATUS_BY_FLAG = {0: "zero_occupancy", 1: "unobserved"}
_BLOCKER_ORDER = (
    (
        "residue",
        "zero_occupancy",
        "source_declared_zero_occupancy_residue_preparation_not_supported",
    ),
    (
        "atom",
        "zero_occupancy",
        "source_declared_zero_occupancy_atom_preparation_not_supported",
    ),
    (
        "residue",
        "unobserved",
        "source_declared_unobserved_residue_preparation_not_supported",
    ),
    (
        "atom",
        "unobserved",
        "source_declared_unobserved_atom_preparation_not_supported",
    ),
)


class MmcifMissingAtomResiduePolicyError(ValueError):
    """Stable fail-closed policy error without source identity echo."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            f"mmcif_missing_atom_residue_policy:{self.code}{suffix}: {self.detail}"
        )


@dataclass(frozen=True, slots=True)
class MmcifMissingAtomResiduePolicyCategoryBinding:
    category: str
    headers: tuple[str, ...]
    row_count: int
    source_ordinal: int
    row_sha256: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "representation": "loop",
            "headers": list(self.headers),
            "row_count": self.row_count,
            "source_ordinal": self.source_ordinal,
            "row_sha256": list(self.row_sha256),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifMissingAtomResiduePolicyObservation:
    category: str
    declaration_kind: str
    source_ordinal: int
    occupancy_flag_token: str
    occupancy_flag: int
    declaration_status: str
    row_sha256: str
    observation_identity_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifMissingAtomResiduePolicyObservation("
            f"declaration_kind={self.declaration_kind!r}, "
            f"source_ordinal={self.source_ordinal}, "
            f"declaration_status={self.declaration_status!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "declaration_kind": self.declaration_kind,
            "source_ordinal": self.source_ordinal,
            "occupancy_flag_token": self.occupancy_flag_token,
            "occupancy_flag": self.occupancy_flag,
            "declaration_status": self.declaration_status,
            "row_sha256": self.row_sha256,
            "observation_identity_sha256": self.observation_identity_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifMissingAtomResiduePolicySnapshot:
    source_sha256: str
    observations: tuple[MmcifMissingAtomResiduePolicyObservation, ...]
    category_bindings: tuple[MmcifMissingAtomResiduePolicyCategoryBinding, ...]

    def __repr__(self) -> str:
        return (
            "MmcifMissingAtomResiduePolicySnapshot("
            f"declaration_count={len(self.observations)}, "
            f"execution_allowed={self.execution_allowed})"
        )

    @property
    def residue_declaration_count(self) -> int:
        return sum(row.declaration_kind == "residue" for row in self.observations)

    @property
    def atom_declaration_count(self) -> int:
        return sum(row.declaration_kind == "atom" for row in self.observations)

    @property
    def zero_occupancy_declaration_count(self) -> int:
        return sum(
            row.declaration_status == "zero_occupancy" for row in self.observations
        )

    @property
    def unobserved_declaration_count(self) -> int:
        return sum(row.declaration_status == "unobserved" for row in self.observations)

    @property
    def declaration_status_counts(self) -> tuple[tuple[str, str, int], ...]:
        return tuple(
            (
                declaration_kind,
                declaration_status,
                sum(
                    row.declaration_kind == declaration_kind
                    and row.declaration_status == declaration_status
                    for row in self.observations
                ),
            )
            for declaration_kind, declaration_status, _blocker in _BLOCKER_ORDER
        )

    @property
    def execution_policy_status(self) -> str:
        return _ALLOWED_STATUS if not self.observations else _BLOCKED_STATUS

    @property
    def execution_allowed(self) -> bool:
        return not self.observations

    @property
    def execution_blockers(self) -> tuple[str, ...]:
        counts = {
            (kind, status): count
            for kind, status, count in self.declaration_status_counts
        }
        return tuple(
            blocker
            for kind, status, blocker in _BLOCKER_ORDER
            if counts[(kind, status)]
        )

    @property
    def policy_projection_sha256(self) -> str:
        return _sha256(mmcif_missing_atom_residue_policy_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_missing_atom_residue_policy_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_MISSING_ATOM_RESIDUE_POLICY_DOCUMENT_SCHEMA_ID,
                "policy_projection_sha256": self.policy_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_MISSING_ATOM_RESIDUE_POLICY_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROFILE_ID,
            "parser_version": MMCIF_MISSING_ATOM_RESIDUE_POLICY_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "declaration_category_count": len(self.category_bindings),
            "declaration_count": len(self.observations),
            "residue_declaration_count": self.residue_declaration_count,
            "atom_declaration_count": self.atom_declaration_count,
            "zero_occupancy_declaration_count": (
                self.zero_occupancy_declaration_count
            ),
            "unobserved_declaration_count": self.unobserved_declaration_count,
            "declaration_status_counts": [
                {
                    "declaration_kind": kind,
                    "declaration_status": status,
                    "row_count": count,
                }
                for kind, status, count in self.declaration_status_counts
            ],
            "source_declared_observation_gap_input": bool(self.observations),
            "execution_policy_status": self.execution_policy_status,
            "execution_allowed": self.execution_allowed,
            "execution_blockers": list(self.execution_blockers),
            "policy_projection_sha256": self.policy_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _claim_policy() -> dict[str, bool]:
    return {
        "source_declaration_presence_classified": True,
        "complete_selected_declaration_rows_bound": True,
        "occupancy_flag_values_interpreted": True,
        "unobserved_and_zero_occupancy_status_classified": True,
        "preparation_admission_policy_interpreted": True,
        "absence_proves_structure_complete": False,
        "declaration_identity_interpreted": False,
        "atom_site_coordinates_interpreted": False,
        "atom_site_occupancy_crosschecked": False,
        "missingness_inferred": False,
        "missing_atom_or_residue_repaired": False,
        "coordinates_generated": False,
        "alternate_location_selected": False,
        "chemistry_interpreted": False,
        "topology_interpreted": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _row_sha(loop: CifLoop, row: tuple[CifToken, ...]) -> str:
    return _sha256(
        [
            {
                "tag": tag,
                "value": token.value,
                "quoted": bool(token.quoted),
                "multiline": bool(token.multiline),
            }
            for tag, token in zip(loop.tags, row, strict=True)
        ]
    )


def _occupancy_flag(token: CifToken) -> tuple[int, str]:
    if (
        token.quoted
        or token.multiline
        or len(token.value) > MAX_MMCIF_MISSING_ATOM_RESIDUE_POLICY_TOKEN_CHARS
        or _INTEGER_RE.fullmatch(token.value) is None
    ):
        raise MmcifMissingAtomResiduePolicyError(
            "invalid_occupancy_flag",
            "occupancy_flag must be an unquoted bounded PDBx/mmCIF integer",
            line_number=token.line_number,
        )
    value = int(token.value)
    if value not in _STATUS_BY_FLAG:
        raise MmcifMissingAtomResiduePolicyError(
            "occupancy_flag_outside_controlled_vocabulary",
            "occupancy_flag must be controlled value 0 or 1",
            line_number=token.line_number,
        )
    return value, _STATUS_BY_FLAG[value]


def _observation_payload(
    *,
    category: str,
    declaration_kind: str,
    source_ordinal: int,
    occupancy_flag_token: str,
    occupancy_flag: int,
    declaration_status: str,
    row_sha256: str,
) -> dict[str, Any]:
    return {
        "category": category,
        "declaration_kind": declaration_kind,
        "source_ordinal": source_ordinal,
        "occupancy_flag_token": occupancy_flag_token,
        "occupancy_flag": occupancy_flag,
        "declaration_status": declaration_status,
        "row_sha256": row_sha256,
    }


def parse_mmcif_missing_atom_residue_policy(
    text: str,
) -> MmcifMissingAtomResiduePolicySnapshot:
    """Classify source-declared observation gaps for preparation admission."""

    if type(text) is not str:
        raise TypeError("mmCIF missing atom/residue policy input must be a string")
    block = parse_cif_block(text)
    observations: list[MmcifMissingAtomResiduePolicyObservation] = []
    bindings: list[MmcifMissingAtomResiduePolicyCategoryBinding] = []

    for category in MMCIF_MISSING_ATOM_RESIDUE_POLICY_CATEGORIES:
        scalar_tags = tuple(
            tag for tag in block.scalar_values if tag.startswith(f"{category}.")
        )
        if scalar_tags:
            raise MmcifMissingAtomResiduePolicyError(
                "declaration_category_must_be_loop",
                "selected observation-gap categories must use one pure loop",
                line_number=block.scalar_values[scalar_tags[0]].line_number,
            )
        loops = [loop for loop in block.loops if category in loop.categories]
        if not loops:
            continue
        if len(loops) != 1:
            raise MmcifMissingAtomResiduePolicyError(
                "declaration_loop_count_mismatch",
                "each selected observation-gap category must occur in one loop",
                line_number=loops[1].line_number,
            )
        loop = loops[0]
        if loop.categories != (category,):
            raise MmcifMissingAtomResiduePolicyError(
                "mixed_declaration_loop",
                "cross-category observation-gap loops are outside this policy",
                line_number=loop.line_number,
            )
        if not loop.rows:
            raise MmcifMissingAtomResiduePolicyError(
                "declaration_rows_missing",
                "selected observation-gap loops must contain source rows",
                line_number=loop.line_number,
            )
        if len(loop.rows) > MAX_MMCIF_MISSING_ATOM_RESIDUE_POLICY_ROWS:
            raise MmcifMissingAtomResiduePolicyError(
                "too_many_declaration_rows",
                "observation-gap declarations exceed the bounded policy",
                line_number=loop.line_number,
            )
        required_headers = _REQUIRED_HEADERS[category]
        if (
            set(loop.tags) != set(required_headers)
            or len(loop.tags) != len(required_headers)
        ):
            raise MmcifMissingAtomResiduePolicyError(
                "unsupported_declaration_headers",
                "selected observation-gap loops require the exact bounded headers",
                line_number=loop.line_number,
            )
        index = {tag: position for position, tag in enumerate(loop.tags)}
        row_hashes: list[str] = []
        for source_ordinal, row in enumerate(loop.rows):
            for token in row:
                if (
                    token.multiline
                    or len(token.value)
                    > MAX_MMCIF_MISSING_ATOM_RESIDUE_POLICY_TOKEN_CHARS
                ):
                    raise MmcifMissingAtomResiduePolicyError(
                        "declaration_token_out_of_bounds",
                        "one observation-gap token is outside the bounded policy",
                        line_number=token.line_number,
                    )
            row_sha256 = _row_sha(loop, row)
            row_hashes.append(row_sha256)
            token = row[index[_FLAG_HEADER[category]]]
            flag, status = _occupancy_flag(token)
            payload = _observation_payload(
                category=category,
                declaration_kind=_DECLARATION_KIND[category],
                source_ordinal=source_ordinal,
                occupancy_flag_token=token.value,
                occupancy_flag=flag,
                declaration_status=status,
                row_sha256=row_sha256,
            )
            observations.append(
                MmcifMissingAtomResiduePolicyObservation(
                    **payload,
                    observation_identity_sha256=_sha256(payload),
                )
            )
        bindings.append(
            MmcifMissingAtomResiduePolicyCategoryBinding(
                category=category,
                headers=tuple(loop.tags),
                row_count=len(loop.rows),
                source_ordinal=block.category_order.index(category),
                row_sha256=tuple(row_hashes),
            )
        )

    return MmcifMissingAtomResiduePolicySnapshot(
        source_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observations=tuple(observations),
        category_bindings=tuple(bindings),
    )


def mmcif_missing_atom_residue_policy_projection(
    snapshot: MmcifMissingAtomResiduePolicySnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROFILE_ID,
        "parser_version": MMCIF_MISSING_ATOM_RESIDUE_POLICY_PARSER_VERSION,
        "observations": [row.to_dict() for row in snapshot.observations],
        "observation_order": "category_then_source_order",
        "declaration_status_counts": [
            {
                "declaration_kind": kind,
                "declaration_status": status,
                "row_count": count,
            }
            for kind, status, count in snapshot.declaration_status_counts
        ],
        "execution_policy_status": snapshot.execution_policy_status,
        "execution_allowed": snapshot.execution_allowed,
        "execution_blockers": list(snapshot.execution_blockers),
        **_claim_policy(),
    }


def mmcif_missing_atom_residue_policy_source_binding(
    snapshot: MmcifMissingAtomResiduePolicySnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_MISSING_ATOM_RESIDUE_POLICY_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "dictionary_categories": dict(
            MMCIF_MISSING_ATOM_RESIDUE_POLICY_DICTIONARY_CATEGORIES
        ),
        "dictionary_items": dict(
            MMCIF_MISSING_ATOM_RESIDUE_POLICY_DICTIONARY_ITEMS
        ),
        "category_bindings": [
            binding.to_dict() for binding in snapshot.category_bindings
        ],
    }


def mmcif_missing_atom_residue_policy_document(
    snapshot: MmcifMissingAtomResiduePolicySnapshot,
) -> dict[str, Any]:
    projection = mmcif_missing_atom_residue_policy_projection(snapshot)
    binding = mmcif_missing_atom_residue_policy_source_binding(snapshot)
    return {
        "schema_id": MMCIF_MISSING_ATOM_RESIDUE_POLICY_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROFILE_ID,
        "parser_version": MMCIF_MISSING_ATOM_RESIDUE_POLICY_PARSER_VERSION,
        "policy_projection": projection,
        "source_binding": binding,
        "policy_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str) -> str:
    candidate = str(value or "")
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"missing atom/residue policy {label} digest invalid")
    return candidate


def require_mmcif_missing_atom_residue_policy_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("missing atom/residue policy document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_MISSING_ATOM_RESIDUE_POLICY_DOCUMENT_SCHEMA_ID:
        raise ValueError("missing atom/residue policy document schema mismatch")
    if document.get("profile_id") != MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROFILE_ID:
        raise ValueError("missing atom/residue policy profile mismatch")
    if (
        document.get("parser_version")
        != MMCIF_MISSING_ATOM_RESIDUE_POLICY_PARSER_VERSION
    ):
        raise ValueError("missing atom/residue policy parser version mismatch")
    projection = document.get("policy_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("missing atom/residue policy sections must be mappings")
    if (
        projection.get("schema_id")
        != MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROJECTION_SCHEMA_ID
        or projection.get("profile_id")
        != MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROFILE_ID
        or projection.get("parser_version")
        != MMCIF_MISSING_ATOM_RESIDUE_POLICY_PARSER_VERSION
        or projection.get("observation_order") != "category_then_source_order"
    ):
        raise ValueError("missing atom/residue policy projection mismatch")
    if (
        binding.get("schema_id")
        != MMCIF_MISSING_ATOM_RESIDUE_POLICY_SOURCE_BINDING_SCHEMA_ID
    ):
        raise ValueError("missing atom/residue policy source binding mismatch")
    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("policy_projection_sha256") != projection_digest:
        raise ValueError("missing atom/residue policy projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("missing atom/residue policy source binding digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_MISSING_ATOM_RESIDUE_POLICY_DOCUMENT_SCHEMA_ID,
            "policy_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("missing atom/residue policy snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("missing atom/residue policy claim boundary mismatch")

    observations = projection.get("observations")
    if not isinstance(observations, list):
        raise ValueError("missing atom/residue policy observations must be a list")
    expected_ordinals = {RESIDUE_CATEGORY: 0, ATOM_CATEGORY: 0}
    row_hashes_by_category: dict[str, list[str]] = {
        RESIDUE_CATEGORY: [],
        ATOM_CATEGORY: [],
    }
    counts = {(kind, status): 0 for kind, status, _blocker in _BLOCKER_ORDER}
    for item in observations:
        if not isinstance(item, Mapping):
            raise ValueError("missing atom/residue policy observation invalid")
        row = dict(item)
        category = row.get("category")
        if category not in MMCIF_MISSING_ATOM_RESIDUE_POLICY_CATEGORIES:
            raise ValueError("missing atom/residue policy category invalid")
        kind = _DECLARATION_KIND[category]
        ordinal = row.get("source_ordinal")
        token = row.get("occupancy_flag_token")
        flag = row.get("occupancy_flag")
        status = row.get("declaration_status")
        if (
            row.get("declaration_kind") != kind
            or ordinal != expected_ordinals[category]
            or type(token) is not str
            or not token
            or len(token) > MAX_MMCIF_MISSING_ATOM_RESIDUE_POLICY_TOKEN_CHARS
            or _INTEGER_RE.fullmatch(token) is None
            or type(flag) is not int
            or flag not in _STATUS_BY_FLAG
            or int(token) != flag
            or status != _STATUS_BY_FLAG[flag]
        ):
            raise ValueError("missing atom/residue policy observation value invalid")
        row_sha256 = _require_digest(row.get("row_sha256"), "row")
        observation_payload = _observation_payload(
            category=category,
            declaration_kind=kind,
            source_ordinal=ordinal,
            occupancy_flag_token=token,
            occupancy_flag=flag,
            declaration_status=status,
            row_sha256=row_sha256,
        )
        if row.get("observation_identity_sha256") != _sha256(observation_payload):
            raise ValueError("missing atom/residue policy observation identity mismatch")
        expected_ordinals[category] += 1
        row_hashes_by_category[category].append(row_sha256)
        counts[(kind, status)] += 1

    expected_count_rows = [
        {
            "declaration_kind": kind,
            "declaration_status": status,
            "row_count": counts[(kind, status)],
        }
        for kind, status, _blocker in _BLOCKER_ORDER
    ]
    expected_blockers = [
        blocker
        for kind, status, blocker in _BLOCKER_ORDER
        if counts[(kind, status)]
    ]
    execution_allowed = not observations
    expected_status = _ALLOWED_STATUS if execution_allowed else _BLOCKED_STATUS
    if (
        projection.get("declaration_status_counts") != expected_count_rows
        or document.get("declaration_status_counts") != expected_count_rows
        or projection.get("execution_policy_status") != expected_status
        or document.get("execution_policy_status") != expected_status
        or projection.get("execution_allowed") is not execution_allowed
        or document.get("execution_allowed") is not execution_allowed
        or projection.get("execution_blockers") != expected_blockers
        or document.get("execution_blockers") != expected_blockers
        or document.get("source_declared_observation_gap_input")
        is not bool(observations)
        or document.get("declaration_count") != len(observations)
        or document.get("residue_declaration_count")
        != expected_ordinals[RESIDUE_CATEGORY]
        or document.get("atom_declaration_count") != expected_ordinals[ATOM_CATEGORY]
        or document.get("zero_occupancy_declaration_count")
        != sum(count for (kind, status), count in counts.items() if status == "zero_occupancy")
        or document.get("unobserved_declaration_count")
        != sum(count for (kind, status), count in counts.items() if status == "unobserved")
    ):
        raise ValueError("missing atom/residue policy classification mismatch")

    source_sha256 = _require_digest(binding.get("source_sha256"), "source")
    if document.get("source_sha256") != source_sha256:
        raise ValueError("missing atom/residue policy source digest mismatch")
    if (
        binding.get("dictionary_categories")
        != MMCIF_MISSING_ATOM_RESIDUE_POLICY_DICTIONARY_CATEGORIES
        or binding.get("dictionary_items")
        != MMCIF_MISSING_ATOM_RESIDUE_POLICY_DICTIONARY_ITEMS
    ):
        raise ValueError("missing atom/residue policy dictionary binding mismatch")
    category_bindings = binding.get("category_bindings")
    if not isinstance(category_bindings, list):
        raise ValueError("missing atom/residue policy category bindings invalid")
    expected_present = [
        category
        for category in MMCIF_MISSING_ATOM_RESIDUE_POLICY_CATEGORIES
        if row_hashes_by_category[category]
    ]
    if len(category_bindings) != len(expected_present):
        raise ValueError("missing atom/residue policy category count mismatch")
    for item, category in zip(category_bindings, expected_present, strict=True):
        if not isinstance(item, Mapping):
            raise ValueError("missing atom/residue policy category binding invalid")
        row = dict(item)
        headers = row.get("headers")
        row_hashes = row.get("row_sha256")
        if (
            row.get("category") != category
            or row.get("representation") != "loop"
            or not isinstance(headers, list)
            or set(headers) != set(_REQUIRED_HEADERS[category])
            or len(headers) != len(_REQUIRED_HEADERS[category])
            or row.get("row_count") != len(row_hashes_by_category[category])
            or type(row.get("source_ordinal")) is not int
            or row.get("source_ordinal") < 0
            or row_hashes != row_hashes_by_category[category]
        ):
            raise ValueError("missing atom/residue policy category binding mismatch")
    if document.get("declaration_category_count") != len(category_bindings):
        raise ValueError("missing atom/residue policy declaration category mismatch")
    return payload


def mmcif_missing_atom_residue_policy_json_bytes(
    snapshot: MmcifMissingAtomResiduePolicySnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_missing_atom_residue_policy_document(snapshot))


def write_mmcif_missing_atom_residue_policy_json(
    path: str | Path,
    snapshot: MmcifMissingAtomResiduePolicySnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_missing_atom_residue_policy_json_bytes(snapshot) + b"\n"
    file_fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(file_fd, 0o600)
        with os.fdopen(file_fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        file_fd = -1
        os.replace(temporary_path, destination)
        directory_fd = os.open(
            destination.parent,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        if file_fd >= 0:
            try:
                os.close(file_fd)
            except OSError:
                pass
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise
    return destination


__all__ = [
    "MAX_MMCIF_MISSING_ATOM_RESIDUE_POLICY_ROWS",
    "MAX_MMCIF_MISSING_ATOM_RESIDUE_POLICY_TOKEN_CHARS",
    "MMCIF_MISSING_ATOM_RESIDUE_POLICY_CATEGORIES",
    "MMCIF_MISSING_ATOM_RESIDUE_POLICY_DICTIONARY_CATEGORIES",
    "MMCIF_MISSING_ATOM_RESIDUE_POLICY_DICTIONARY_ITEMS",
    "MMCIF_MISSING_ATOM_RESIDUE_POLICY_DOCUMENT_SCHEMA_ID",
    "MMCIF_MISSING_ATOM_RESIDUE_POLICY_PARSER_VERSION",
    "MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROFILE_ID",
    "MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROJECTION_SCHEMA_ID",
    "MMCIF_MISSING_ATOM_RESIDUE_POLICY_SOURCE_BINDING_SCHEMA_ID",
    "MmcifMissingAtomResiduePolicyCategoryBinding",
    "MmcifMissingAtomResiduePolicyError",
    "MmcifMissingAtomResiduePolicyObservation",
    "MmcifMissingAtomResiduePolicySnapshot",
    "mmcif_missing_atom_residue_policy_document",
    "mmcif_missing_atom_residue_policy_json_bytes",
    "mmcif_missing_atom_residue_policy_projection",
    "mmcif_missing_atom_residue_policy_source_binding",
    "parse_mmcif_missing_atom_residue_policy",
    "require_mmcif_missing_atom_residue_policy_document",
    "write_mmcif_missing_atom_residue_policy_json",
]
