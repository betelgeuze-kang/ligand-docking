"""Bounded semantic projection for mmCIF identity and polymer sequence.

This module consumes :mod:`mmcif_syntax` output and interprets only a narrow,
dependency-free subset:

- ``_entry.id``;
- ``_entity.id`` and ``_entity.type``;
- ``_struct_asym.id`` and ``_struct_asym.entity_id``;
- ``_entity_poly.entity_id`` and ``_entity_poly.type``;
- ``_entity_poly_seq.entity_id/num/mon_id/hetero``.

It does not interpret ``_atom_site``, coordinates, author/label equivalence,
missingness, alternate locations, assemblies, chemistry, topology, preparation,
parameterability, physics, or execution readiness. Unknown markers are preserved
as markers rather than converted to empty strings or inferred facts.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from types import MappingProxyType
from typing import Any, Mapping

from .mmcif_syntax import CifBlock, CifLoop, CifToken, parse_cif_block

MMCIF_SEMANTIC_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_semantic_projection/1.0.0"
)
MMCIF_SEMANTIC_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_semantic_document/1.0.0"
)
MMCIF_SEMANTIC_PROFILE_ID = "bounded_mmcif_entity_asym_polymer_sequence/1.0.0"
MMCIF_SEMANTIC_PARSER_VERSION = "1.0.0"
MAX_MMCIF_SEMANTIC_ROWS = 100_000
MAX_MMCIF_SEMANTIC_TOKEN_CHARS = 256

_VALUE_STATES = frozenset({"known", "not_applicable", "unknown"})
_SUPPORTED_CATEGORIES = frozenset(
    {"_entry", "_entity", "_struct_asym", "_entity_poly", "_entity_poly_seq"}
)
_ENTITY_HEADERS = ("_entity.id", "_entity.type")
_STRUCT_ASYM_HEADERS = ("_struct_asym.id", "_struct_asym.entity_id")
_ENTITY_POLY_HEADERS = ("_entity_poly.entity_id", "_entity_poly.type")
_ENTITY_POLY_SEQ_HEADERS = (
    "_entity_poly_seq.entity_id",
    "_entity_poly_seq.num",
    "_entity_poly_seq.mon_id",
    "_entity_poly_seq.hetero",
)
_POSITIVE_INTEGER_RE = re.compile(r"^[1-9][0-9]*$")
_BARE_IDENTITY_RE = re.compile(r"^[!-~]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifSemanticError(ValueError):
    """Stable semantic error raised without inferring molecular authority."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"mmcif_semantics:{self.code}{suffix}: {self.detail}")


@dataclass(frozen=True, slots=True)
class MmcifSemanticValue:
    """One CIF value with an explicit known/unknown/not-applicable state."""

    state: str
    value: str
    quoted: bool
    line_number: int
    column_number: int

    def __post_init__(self) -> None:
        if self.state not in _VALUE_STATES:
            raise ValueError("unsupported semantic value state")
        if type(self.value) is not str or len(self.value) > MAX_MMCIF_SEMANTIC_TOKEN_CHARS:
            raise ValueError("semantic value exceeds the bounded token domain")
        if self.state == "known" and not self.value:
            raise ValueError("known semantic values may not be empty")
        expected_marker = {"not_applicable": ".", "unknown": "?"}.get(self.state)
        if expected_marker is not None and self.value != expected_marker:
            raise ValueError("semantic marker state and value disagree")
        if type(self.quoted) is not bool:
            raise TypeError("quoted must be boolean")
        if type(self.line_number) is not int or self.line_number <= 0:
            raise ValueError("line_number must be positive")
        if type(self.column_number) is not int or self.column_number <= 0:
            raise ValueError("column_number must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "value": self.value,
            "quoted": self.quoted,
        }


@dataclass(frozen=True, slots=True)
class MmcifEntityIdentity:
    entity_id: str
    entity_type: str
    source_ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class MmcifAsymIdentity:
    asym_id: str
    entity_id: str
    source_ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "asym_id": self.asym_id,
            "entity_id": self.entity_id,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class MmcifPolymerDefinition:
    entity_id: str
    polymer_type: MmcifSemanticValue
    source_ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "polymer_type": self.polymer_type.to_dict(),
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class MmcifPolymerSequenceRow:
    entity_id: str
    sequence_number: int
    monomer_id: str
    heterogeneity: MmcifSemanticValue
    source_ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "sequence_number": self.sequence_number,
            "monomer_id": self.monomer_id,
            "heterogeneity": self.heterogeneity.to_dict(),
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class MmcifCategoryBinding:
    category: str
    representation: str
    headers: tuple[str, ...]
    row_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "representation": self.representation,
            "headers": list(self.headers),
            "row_count": self.row_count,
        }


@dataclass(frozen=True, slots=True)
class MmcifSemanticSnapshot:
    source_sha256: str
    block_name: str
    entry_id: MmcifSemanticValue | None
    entities: tuple[MmcifEntityIdentity, ...]
    asym_units: tuple[MmcifAsymIdentity, ...]
    polymer_definitions: tuple[MmcifPolymerDefinition, ...]
    polymer_sequence: tuple[MmcifPolymerSequenceRow, ...]
    source_category_order: tuple[str, ...]
    category_bindings: tuple[MmcifCategoryBinding, ...]
    uninterpreted_categories: tuple[str, ...]

    @property
    def semantic_projection_sha256(self) -> str:
        return _sha256_document(mmcif_semantic_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_document(mmcif_semantic_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256_document(
            {
                "schema_id": MMCIF_SEMANTIC_DOCUMENT_SCHEMA_ID,
                "semantic_projection_sha256": self.semantic_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_SEMANTIC_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_SEMANTIC_PROFILE_ID,
            "parser_version": MMCIF_SEMANTIC_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "block_name": self.block_name,
            "entity_count": len(self.entities),
            "asym_count": len(self.asym_units),
            "polymer_entity_count": len(self.polymer_definitions),
            "polymer_sequence_row_count": len(self.polymer_sequence),
            "uninterpreted_categories": list(self.uninterpreted_categories),
            "semantic_projection_sha256": self.semantic_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def _canonical_json_bytes(document: Any) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256_document(document: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(document)).hexdigest()


def _claim_policy() -> dict[str, bool]:
    return {
        "dictionary_conformance_assessed": False,
        "atom_site_semantics_interpreted": False,
        "coordinate_observation_assessed": False,
        "missingness_interpreted": False,
        "auth_label_equivalence_inferred": False,
        "chemistry_interpreted": False,
        "topology_interpreted": False,
        "preparation_ready": False,
        "parameterability_assessed": False,
        "physics_supported": False,
        "runtime_eligible": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _semantic_value(token: CifToken) -> MmcifSemanticValue:
    if not token.quoted and token.value == ".":
        state = "not_applicable"
    elif not token.quoted and token.value == "?":
        state = "unknown"
    else:
        state = "known"
    try:
        return MmcifSemanticValue(
            state=state,
            value=token.value,
            quoted=bool(token.quoted),
            line_number=int(token.line_number),
            column_number=int(token.column_number),
        )
    except (TypeError, ValueError) as exc:
        raise MmcifSemanticError(
            "semantic_value_out_of_bounds",
            "one supported semantic value is outside the bounded token domain",
            line_number=token.line_number,
        ) from exc


def _known_identity(token: CifToken, *, field: str) -> str:
    semantic = _semantic_value(token)
    if semantic.state != "known":
        raise MmcifSemanticError(
            "required_identity_marker",
            f"{field} must be a known identity value",
            line_number=token.line_number,
        )
    if (
        len(semantic.value) > MAX_MMCIF_SEMANTIC_TOKEN_CHARS
        or _BARE_IDENTITY_RE.fullmatch(semantic.value) is None
    ):
        raise MmcifSemanticError(
            "invalid_identity_token",
            f"{field} must be a bounded printable token without whitespace",
            line_number=token.line_number,
        )
    return semantic.value


def _loop_for_category(
    block: CifBlock,
    category: str,
    required_headers: tuple[str, ...],
) -> tuple[CifLoop, dict[str, int], MmcifCategoryBinding]:
    scalar_tags = tuple(tag for tag in block.scalar_values if tag.startswith(f"{category}."))
    if scalar_tags:
        token = block.scalar_values[scalar_tags[0]]
        raise MmcifSemanticError(
            "category_must_be_loop",
            f"{category} must use one loop in this bounded profile",
            line_number=token.line_number,
        )
    candidates = [loop for loop in block.loops if category in loop.categories]
    if not candidates:
        raise MmcifSemanticError(
            "required_category_missing",
            f"required category {category} is missing",
        )
    if len(candidates) != 1:
        raise MmcifSemanticError(
            "multiple_category_loops",
            f"category {category} must occur in exactly one loop",
            line_number=candidates[1].line_number,
        )
    loop = candidates[0]
    if loop.categories != (category,):
        raise MmcifSemanticError(
            "mixed_category_loop",
            "cross-category loops are outside this bounded semantic profile",
            line_number=loop.line_number,
        )
    if len(loop.rows) > MAX_MMCIF_SEMANTIC_ROWS:
        raise MmcifSemanticError(
            "too_many_semantic_rows",
            f"category {category} exceeds the semantic row bound",
            line_number=loop.line_number,
        )
    index = {tag: position for position, tag in enumerate(loop.tags)}
    missing = [header for header in required_headers if header not in index]
    if missing:
        raise MmcifSemanticError(
            "required_header_missing",
            f"category {category} is missing one or more required headers",
            line_number=loop.line_number,
        )
    return (
        loop,
        index,
        MmcifCategoryBinding(
            category=category,
            representation="loop",
            headers=tuple(loop.tags),
            row_count=len(loop.rows),
        ),
    )


def _entry_value(block: CifBlock) -> tuple[MmcifSemanticValue | None, MmcifCategoryBinding | None]:
    entry_loops = [loop for loop in block.loops if "_entry" in loop.categories]
    if entry_loops:
        raise MmcifSemanticError(
            "entry_must_be_scalar",
            "_entry.id must be scalar in this bounded profile",
            line_number=entry_loops[0].line_number,
        )
    entry_tags = tuple(tag for tag in block.scalar_values if tag.startswith("_entry."))
    if not entry_tags:
        return None, None
    if entry_tags != ("_entry.id",):
        token = block.scalar_values[entry_tags[0]]
        raise MmcifSemanticError(
            "unsupported_entry_headers",
            "only scalar _entry.id is interpreted",
            line_number=token.line_number,
        )
    token = block.scalar_values["_entry.id"]
    value = _semantic_value(token)
    if value.state == "known":
        _known_identity(token, field="_entry.id")
    return (
        value,
        MmcifCategoryBinding(
            category="_entry",
            representation="scalar",
            headers=("_entry.id",),
            row_count=1,
        ),
    )


def parse_mmcif_semantics(text: str) -> MmcifSemanticSnapshot:
    """Parse the bounded entity/asym/polymer-sequence semantic projection."""

    if type(text) is not str:
        raise TypeError("mmCIF semantic input must be a string")
    block = parse_cif_block(text)
    source_sha256 = hashlib.sha256(text.encode("ascii")).hexdigest()

    entry_id, entry_binding = _entry_value(block)
    entity_loop, entity_index, entity_binding = _loop_for_category(
        block, "_entity", _ENTITY_HEADERS
    )
    asym_loop, asym_index, asym_binding = _loop_for_category(
        block, "_struct_asym", _STRUCT_ASYM_HEADERS
    )
    poly_loop, poly_index, poly_binding = _loop_for_category(
        block, "_entity_poly", _ENTITY_POLY_HEADERS
    )
    seq_loop, seq_index, seq_binding = _loop_for_category(
        block, "_entity_poly_seq", _ENTITY_POLY_SEQ_HEADERS
    )

    entities: list[MmcifEntityIdentity] = []
    entity_types: dict[str, str] = {}
    for ordinal, row in enumerate(entity_loop.rows):
        entity_id = _known_identity(row[entity_index["_entity.id"]], field="_entity.id")
        entity_type_token = row[entity_index["_entity.type"]]
        entity_type = _known_identity(entity_type_token, field="_entity.type").lower()
        if entity_id in entity_types:
            raise MmcifSemanticError(
                "duplicate_entity_id",
                "entity identifiers must be unique",
                line_number=row[entity_index["_entity.id"]].line_number,
            )
        entity_types[entity_id] = entity_type
        entities.append(MmcifEntityIdentity(entity_id, entity_type, ordinal))
    if not entities:
        raise MmcifSemanticError("entity_rows_missing", "at least one entity row is required")

    asym_units: list[MmcifAsymIdentity] = []
    asym_ids: set[str] = set()
    entities_with_asym: set[str] = set()
    for ordinal, row in enumerate(asym_loop.rows):
        asym_id = _known_identity(row[asym_index["_struct_asym.id"]], field="_struct_asym.id")
        entity_id = _known_identity(
            row[asym_index["_struct_asym.entity_id"]],
            field="_struct_asym.entity_id",
        )
        if asym_id in asym_ids:
            raise MmcifSemanticError(
                "duplicate_asym_id",
                "asym identifiers must be unique",
                line_number=row[asym_index["_struct_asym.id"]].line_number,
            )
        if entity_id not in entity_types:
            raise MmcifSemanticError(
                "asym_entity_reference_missing",
                "one struct_asym row references an unknown entity",
                line_number=row[asym_index["_struct_asym.entity_id"]].line_number,
            )
        asym_ids.add(asym_id)
        entities_with_asym.add(entity_id)
        asym_units.append(MmcifAsymIdentity(asym_id, entity_id, ordinal))

    polymer_entities = {
        entity_id for entity_id, entity_type in entity_types.items() if entity_type == "polymer"
    }
    if not polymer_entities:
        raise MmcifSemanticError(
            "polymer_entity_missing",
            "this profile requires at least one entity with type polymer",
        )
    missing_asym = sorted(polymer_entities - entities_with_asym)
    if missing_asym:
        raise MmcifSemanticError(
            "polymer_asym_coverage_missing",
            "every polymer entity must be instantiated by at least one struct_asym row",
        )

    polymer_definitions: list[MmcifPolymerDefinition] = []
    poly_ids: set[str] = set()
    for ordinal, row in enumerate(poly_loop.rows):
        entity_id = _known_identity(
            row[poly_index["_entity_poly.entity_id"]], field="_entity_poly.entity_id"
        )
        if entity_id in poly_ids:
            raise MmcifSemanticError(
                "duplicate_polymer_definition",
                "polymer entities must have exactly one entity_poly row",
                line_number=row[poly_index["_entity_poly.entity_id"]].line_number,
            )
        if entity_id not in polymer_entities:
            raise MmcifSemanticError(
                "entity_poly_nonpolymer_reference",
                "entity_poly may reference only an entity declared as polymer",
                line_number=row[poly_index["_entity_poly.entity_id"]].line_number,
            )
        poly_ids.add(entity_id)
        polymer_definitions.append(
            MmcifPolymerDefinition(
                entity_id=entity_id,
                polymer_type=_semantic_value(row[poly_index["_entity_poly.type"]]),
                source_ordinal=ordinal,
            )
        )
    if poly_ids != polymer_entities:
        raise MmcifSemanticError(
            "polymer_definition_coverage_mismatch",
            "entity_poly rows must cover every and only polymer entity",
        )

    sequence_rows: list[MmcifPolymerSequenceRow] = []
    sequence_entities: set[str] = set()
    expected_next = {entity_id: 1 for entity_id in polymer_entities}
    seen_positions: set[tuple[str, int]] = set()
    for ordinal, row in enumerate(seq_loop.rows):
        entity_id = _known_identity(
            row[seq_index["_entity_poly_seq.entity_id"]],
            field="_entity_poly_seq.entity_id",
        )
        if entity_id not in polymer_entities:
            raise MmcifSemanticError(
                "sequence_nonpolymer_reference",
                "entity_poly_seq may reference only a polymer entity",
                line_number=row[seq_index["_entity_poly_seq.entity_id"]].line_number,
            )
        num_token = row[seq_index["_entity_poly_seq.num"]]
        if _POSITIVE_INTEGER_RE.fullmatch(num_token.value) is None or num_token.quoted:
            raise MmcifSemanticError(
                "invalid_sequence_number",
                "polymer sequence numbers must be canonical positive integers",
                line_number=num_token.line_number,
            )
        sequence_number = int(num_token.value)
        key = (entity_id, sequence_number)
        if key in seen_positions:
            raise MmcifSemanticError(
                "duplicate_sequence_position",
                "polymer sequence positions must be unique per entity",
                line_number=num_token.line_number,
            )
        expected = expected_next[entity_id]
        if sequence_number != expected:
            raise MmcifSemanticError(
                "noncontiguous_sequence_positions",
                "each entity sequence must appear in source order as positions 1..N",
                line_number=num_token.line_number,
            )
        expected_next[entity_id] = expected + 1
        seen_positions.add(key)
        sequence_entities.add(entity_id)

        monomer_id = _known_identity(
            row[seq_index["_entity_poly_seq.mon_id"]],
            field="_entity_poly_seq.mon_id",
        )
        heterogeneity = _semantic_value(row[seq_index["_entity_poly_seq.hetero"]])
        if heterogeneity.state == "known":
            normalized = heterogeneity.value.lower()
            if normalized in {"y", "yes"}:
                raise MmcifSemanticError(
                    "microheterogeneity_not_supported",
                    "positive entity_poly_seq heterogeneity is outside this profile",
                    line_number=heterogeneity.line_number,
                )
            if normalized not in {"n", "no"}:
                raise MmcifSemanticError(
                    "invalid_sequence_heterogeneity",
                    "known heterogeneity values must be n or no",
                    line_number=heterogeneity.line_number,
                )
            heterogeneity = MmcifSemanticValue(
                state="known",
                value="n",
                quoted=heterogeneity.quoted,
                line_number=heterogeneity.line_number,
                column_number=heterogeneity.column_number,
            )
        sequence_rows.append(
            MmcifPolymerSequenceRow(
                entity_id=entity_id,
                sequence_number=sequence_number,
                monomer_id=monomer_id,
                heterogeneity=heterogeneity,
                source_ordinal=ordinal,
            )
        )
    if sequence_entities != polymer_entities:
        raise MmcifSemanticError(
            "polymer_sequence_coverage_mismatch",
            "entity_poly_seq rows must cover every and only polymer entity",
        )

    bindings = tuple(
        binding
        for binding in (
            entry_binding,
            entity_binding,
            asym_binding,
            poly_binding,
            seq_binding,
        )
        if binding is not None
    )
    uninterpreted = tuple(
        category for category in block.category_order if category not in _SUPPORTED_CATEGORIES
    )
    return MmcifSemanticSnapshot(
        source_sha256=source_sha256,
        block_name=block.name,
        entry_id=entry_id,
        entities=tuple(entities),
        asym_units=tuple(asym_units),
        polymer_definitions=tuple(polymer_definitions),
        polymer_sequence=tuple(sequence_rows),
        source_category_order=tuple(block.category_order),
        category_bindings=bindings,
        uninterpreted_categories=uninterpreted,
    )


def mmcif_semantic_projection(snapshot: MmcifSemanticSnapshot) -> dict[str, Any]:
    """Return a category-order-independent semantic identity projection."""

    return {
        "schema_id": MMCIF_SEMANTIC_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_SEMANTIC_PROFILE_ID,
        "parser_version": MMCIF_SEMANTIC_PARSER_VERSION,
        "block_name": snapshot.block_name,
        "entry_id": None if snapshot.entry_id is None else snapshot.entry_id.to_dict(),
        "entities": [
            row.to_dict() for row in sorted(snapshot.entities, key=lambda item: item.entity_id)
        ],
        "asym_units": [
            row.to_dict() for row in sorted(snapshot.asym_units, key=lambda item: item.asym_id)
        ],
        "polymer_definitions": [
            row.to_dict()
            for row in sorted(snapshot.polymer_definitions, key=lambda item: item.entity_id)
        ],
        # Global source row order is preserved intentionally. Entities may be interleaved.
        "polymer_sequence": [row.to_dict() for row in snapshot.polymer_sequence],
        "sequence_row_order": "source_order_with_per_entity_contiguous_positions",
        "unknown_marker_semantics": "unquoted_dot_not_applicable_unquoted_question_unknown",
        **_claim_policy(),
    }


def mmcif_semantic_source_binding(snapshot: MmcifSemanticSnapshot) -> dict[str, Any]:
    """Return exact source/category/header binding separate from semantics."""

    return {
        "schema_id": "betelgeuze.engine_v2_mmcif_semantic_source_binding/1.0.0",
        "source_sha256": snapshot.source_sha256,
        "block_name": snapshot.block_name,
        "source_category_order": list(snapshot.source_category_order),
        "category_bindings": [binding.to_dict() for binding in snapshot.category_bindings],
        "uninterpreted_categories": list(snapshot.uninterpreted_categories),
    }


def mmcif_semantic_document(snapshot: MmcifSemanticSnapshot) -> dict[str, Any]:
    projection = mmcif_semantic_projection(snapshot)
    source_binding = mmcif_semantic_source_binding(snapshot)
    return {
        "schema_id": MMCIF_SEMANTIC_DOCUMENT_SCHEMA_ID,
        "semantic_projection_sha256": _sha256_document(projection),
        "source_binding_sha256": _sha256_document(source_binding),
        "snapshot_sha256": snapshot.snapshot_sha256,
        "semantic_projection": projection,
        "source_binding": source_binding,
        "claim_policy": _claim_policy(),
    }


def require_mmcif_semantic_document(document: Any) -> Mapping[str, Any]:
    """Require an internally consistent canonical semantic JSON document."""

    if not isinstance(document, Mapping):
        raise ValueError("mmCIF semantic document must be a mapping")
    payload = dict(document)
    if payload.get("schema_id") != MMCIF_SEMANTIC_DOCUMENT_SCHEMA_ID:
        raise ValueError("mmCIF semantic document schema mismatch")
    projection = payload.get("semantic_projection")
    source_binding = payload.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(source_binding, Mapping):
        raise ValueError("mmCIF semantic document payloads must be mappings")
    projection_sha = _sha256_document(dict(projection))
    source_sha = _sha256_document(dict(source_binding))
    if payload.get("semantic_projection_sha256") != projection_sha:
        raise ValueError("mmCIF semantic projection digest mismatch")
    if payload.get("source_binding_sha256") != source_sha:
        raise ValueError("mmCIF semantic source binding digest mismatch")
    expected_snapshot_sha = _sha256_document(
        {
            "schema_id": MMCIF_SEMANTIC_DOCUMENT_SCHEMA_ID,
            "semantic_projection_sha256": projection_sha,
            "source_binding_sha256": source_sha,
            "claim_policy": _claim_policy(),
        }
    )
    if payload.get("snapshot_sha256") != expected_snapshot_sha:
        raise ValueError("mmCIF semantic snapshot digest mismatch")
    if payload.get("claim_policy") != _claim_policy():
        raise ValueError("mmCIF semantic claim policy mismatch")
    return MappingProxyType(payload)


def mmcif_semantic_json_bytes(snapshot: MmcifSemanticSnapshot) -> bytes:
    return _canonical_json_bytes(mmcif_semantic_document(snapshot))


def write_mmcif_semantic_json(
    path: str | Path,
    snapshot: MmcifSemanticSnapshot,
) -> Path:
    """Atomically write a self-verifying canonical JSON projection."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_semantic_json_bytes(snapshot) + b"\n"
    file_fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(file_fd, 0o600)
        with os.fdopen(file_fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        directory_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(
            os, "O_DIRECTORY", 0
        )
        directory_fd = os.open(destination.parent, directory_flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
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
    "MAX_MMCIF_SEMANTIC_ROWS",
    "MAX_MMCIF_SEMANTIC_TOKEN_CHARS",
    "MMCIF_SEMANTIC_DOCUMENT_SCHEMA_ID",
    "MMCIF_SEMANTIC_PARSER_VERSION",
    "MMCIF_SEMANTIC_PROFILE_ID",
    "MMCIF_SEMANTIC_PROJECTION_SCHEMA_ID",
    "MmcifAsymIdentity",
    "MmcifCategoryBinding",
    "MmcifEntityIdentity",
    "MmcifPolymerDefinition",
    "MmcifPolymerSequenceRow",
    "MmcifSemanticError",
    "MmcifSemanticSnapshot",
    "MmcifSemanticValue",
    "mmcif_semantic_document",
    "mmcif_semantic_json_bytes",
    "mmcif_semantic_projection",
    "mmcif_semantic_source_binding",
    "parse_mmcif_semantics",
    "require_mmcif_semantic_document",
    "write_mmcif_semantic_json",
]
