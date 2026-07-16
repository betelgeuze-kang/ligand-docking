"""Bounded source-declaration projection for mmCIF zero-occupancy records.

This module composes the existing entity/asym/polymer-sequence semantic snapshot
with source-reported ``_pdbx_unobs_or_zero_occ_residues`` and
``_pdbx_unobs_or_zero_occ_atoms`` loops. It validates only bounded source-internal
identity relationships and that ``occupancy_flag`` is an exact numeric zero.

It deliberately does not interpret ``_atom_site`` coordinates or populations,
infer missingness, equate author and label identifiers, select alternate
locations, validate chemistry/topology, prepare a system, or authorize execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from .mmcif_semantics import (
    MmcifSemanticSnapshot,
    MmcifSemanticValue,
    parse_mmcif_semantics,
)
from .mmcif_syntax import CifBlock, CifLoop, CifToken, parse_cif_block


MMCIF_ZERO_OCCUPANCY_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_zero_occupancy_projection/1.0.0"
)
MMCIF_ZERO_OCCUPANCY_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_zero_occupancy_source_binding/1.0.0"
)
MMCIF_ZERO_OCCUPANCY_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_zero_occupancy_document/1.0.0"
)
MMCIF_ZERO_OCCUPANCY_PROFILE_ID = (
    "bounded_mmcif_source_reported_zero_occupancy_declarations/1.0.0"
)
MMCIF_ZERO_OCCUPANCY_PARSER_VERSION = "1.0.0"
MAX_MMCIF_ZERO_OCCUPANCY_ROWS = 100_000
MAX_MMCIF_ZERO_OCCUPANCY_TOKEN_CHARS = 256
MAX_MMCIF_ZERO_OCCUPANCY_INTEGER = (1 << 53) - 1

RESIDUE_CATEGORY = "_pdbx_unobs_or_zero_occ_residues"
ATOM_CATEGORY = "_pdbx_unobs_or_zero_occ_atoms"

MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS = (
    f"{RESIDUE_CATEGORY}.id",
    f"{RESIDUE_CATEGORY}.polymer_flag",
    f"{RESIDUE_CATEGORY}.occupancy_flag",
    f"{RESIDUE_CATEGORY}.pdb_model_num",
    f"{RESIDUE_CATEGORY}.auth_asym_id",
    f"{RESIDUE_CATEGORY}.auth_comp_id",
    f"{RESIDUE_CATEGORY}.auth_seq_id",
    f"{RESIDUE_CATEGORY}.pdb_ins_code",
    f"{RESIDUE_CATEGORY}.label_asym_id",
    f"{RESIDUE_CATEGORY}.label_comp_id",
    f"{RESIDUE_CATEGORY}.label_seq_id",
)
MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS = (
    f"{ATOM_CATEGORY}.id",
    f"{ATOM_CATEGORY}.polymer_flag",
    f"{ATOM_CATEGORY}.occupancy_flag",
    f"{ATOM_CATEGORY}.pdb_model_num",
    f"{ATOM_CATEGORY}.auth_asym_id",
    f"{ATOM_CATEGORY}.auth_comp_id",
    f"{ATOM_CATEGORY}.auth_seq_id",
    f"{ATOM_CATEGORY}.pdb_ins_code",
    f"{ATOM_CATEGORY}.auth_atom_id",
    f"{ATOM_CATEGORY}.label_alt_id",
    f"{ATOM_CATEGORY}.label_asym_id",
    f"{ATOM_CATEGORY}.label_comp_id",
    f"{ATOM_CATEGORY}.label_seq_id",
    f"{ATOM_CATEGORY}.label_atom_id",
)

_POSITIVE_INTEGER_RE = re.compile(r"^[1-9][0-9]*$")
_EXACT_NUMERIC_RE = re.compile(
    r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?$"
)
_BARE_IDENTITY_RE = re.compile(r"^[!-~]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SEMANTIC_CATEGORIES = frozenset(
    {"_entry", "_entity", "_struct_asym", "_entity_poly", "_entity_poly_seq"}
)
_SUPPORTED_CATEGORIES = _SEMANTIC_CATEGORIES | {RESIDUE_CATEGORY, ATOM_CATEGORY}


class MmcifZeroOccupancyError(ValueError):
    """Stable fail-closed error that does not echo source identity values."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"mmcif_zero_occupancy:{self.code}{suffix}: {self.detail}")


@dataclass(frozen=True, slots=True)
class MmcifZeroOccupancyResidueDeclaration:
    source_id: int
    model_number: int
    entity_id: str
    label_asym_id: str
    label_comp_id: str
    label_seq_id: int
    auth_asym_id: MmcifSemanticValue
    auth_comp_id: MmcifSemanticValue
    auth_seq_id: MmcifSemanticValue
    insertion_code: MmcifSemanticValue
    occupancy_token: str
    source_ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "model_number": self.model_number,
            "entity_id": self.entity_id,
            "label_asym_id": self.label_asym_id,
            "label_comp_id": self.label_comp_id,
            "label_seq_id": self.label_seq_id,
            "auth_asym_id": self.auth_asym_id.to_dict(),
            "auth_comp_id": self.auth_comp_id.to_dict(),
            "auth_seq_id": self.auth_seq_id.to_dict(),
            "insertion_code": self.insertion_code.to_dict(),
            "occupancy_token": self.occupancy_token,
            "numeric_zero_verified": True,
            "polymer_flag": "Y",
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class MmcifZeroOccupancyAtomDeclaration:
    source_id: int
    model_number: int
    entity_id: str
    label_asym_id: str
    label_comp_id: str
    label_seq_id: int
    label_atom_id: str
    label_alt_id: MmcifSemanticValue
    auth_asym_id: MmcifSemanticValue
    auth_comp_id: MmcifSemanticValue
    auth_seq_id: MmcifSemanticValue
    insertion_code: MmcifSemanticValue
    auth_atom_id: MmcifSemanticValue
    occupancy_token: str
    source_ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "model_number": self.model_number,
            "entity_id": self.entity_id,
            "label_asym_id": self.label_asym_id,
            "label_comp_id": self.label_comp_id,
            "label_seq_id": self.label_seq_id,
            "label_atom_id": self.label_atom_id,
            "label_alt_id": self.label_alt_id.to_dict(),
            "auth_asym_id": self.auth_asym_id.to_dict(),
            "auth_comp_id": self.auth_comp_id.to_dict(),
            "auth_seq_id": self.auth_seq_id.to_dict(),
            "insertion_code": self.insertion_code.to_dict(),
            "auth_atom_id": self.auth_atom_id.to_dict(),
            "occupancy_token": self.occupancy_token,
            "numeric_zero_verified": True,
            "polymer_flag": "Y",
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class MmcifZeroOccupancyCategoryBinding:
    category: str
    headers: tuple[str, ...]
    row_count: int
    source_ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "representation": "loop",
            "headers": list(self.headers),
            "row_count": self.row_count,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class MmcifZeroOccupancySnapshot:
    source_sha256: str
    block_name: str
    semantic_snapshot_sha256: str
    semantic_projection_sha256: str
    semantic_source_binding_sha256: str
    residue_declarations: tuple[MmcifZeroOccupancyResidueDeclaration, ...]
    atom_declarations: tuple[MmcifZeroOccupancyAtomDeclaration, ...]
    source_category_order: tuple[str, ...]
    category_bindings: tuple[MmcifZeroOccupancyCategoryBinding, ...]
    uninterpreted_categories: tuple[str, ...]

    @property
    def declaration_projection_sha256(self) -> str:
        return _sha256_document(mmcif_zero_occupancy_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_document(mmcif_zero_occupancy_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256_document(
            {
                "schema_id": MMCIF_ZERO_OCCUPANCY_DOCUMENT_SCHEMA_ID,
                "declaration_projection_sha256": self.declaration_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_ZERO_OCCUPANCY_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_ZERO_OCCUPANCY_PROFILE_ID,
            "parser_version": MMCIF_ZERO_OCCUPANCY_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "block_name": self.block_name,
            "semantic_snapshot_sha256": self.semantic_snapshot_sha256,
            "residue_declaration_count": len(self.residue_declarations),
            "atom_declaration_count": len(self.atom_declarations),
            "uninterpreted_categories": list(self.uninterpreted_categories),
            "declaration_projection_sha256": self.declaration_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256_document(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _claim_policy() -> dict[str, bool]:
    return {
        "source_declarations_preserved": True,
        "exact_zero_tokens_verified": True,
        "semantic_sequence_references_verified": True,
        "atom_site_semantics_interpreted": False,
        "atom_site_occupancy_crosschecked": False,
        "coordinate_observation_assessed": False,
        "missingness_inferred": False,
        "auth_label_equivalence_inferred": False,
        "altloc_population_interpreted": False,
        "occupancy_population_interpreted": False,
        "refinement_validity_assessed": False,
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
        raise MmcifZeroOccupancyError(
            "semantic_value_out_of_bounds",
            "one selected declaration value is outside the bounded token domain",
            line_number=token.line_number,
        ) from exc


def _known_identity(token: CifToken, *, field: str) -> str:
    semantic = _semantic_value(token)
    if semantic.state != "known":
        raise MmcifZeroOccupancyError(
            "required_identity_marker",
            f"{field} must be a known identity value",
            line_number=token.line_number,
        )
    if (
        semantic.quoted
        or token.multiline
        or len(semantic.value) > MAX_MMCIF_ZERO_OCCUPANCY_TOKEN_CHARS
        or _BARE_IDENTITY_RE.fullmatch(semantic.value) is None
    ):
        raise MmcifZeroOccupancyError(
            "invalid_identity_token",
            f"{field} must be a bounded bare printable token",
            line_number=token.line_number,
        )
    return semantic.value


def _positive_integer(token: CifToken, *, field: str) -> int:
    if token.quoted or token.multiline or _POSITIVE_INTEGER_RE.fullmatch(token.value) is None:
        raise MmcifZeroOccupancyError(
            "invalid_positive_integer",
            f"{field} must be a canonical positive integer",
            line_number=token.line_number,
        )
    value = int(token.value)
    if value > MAX_MMCIF_ZERO_OCCUPANCY_INTEGER:
        raise MmcifZeroOccupancyError(
            "positive_integer_out_of_bounds",
            f"{field} exceeds the bounded integer domain",
            line_number=token.line_number,
        )
    return value


def _polymer_yes(token: CifToken) -> None:
    if token.quoted or token.multiline or token.value.upper() != "Y":
        raise MmcifZeroOccupancyError(
            "polymer_flag_not_supported",
            "this bounded profile accepts only polymer_flag Y declarations",
            line_number=token.line_number,
        )


def _exact_zero(token: CifToken) -> str:
    if (
        token.quoted
        or token.multiline
        or _EXACT_NUMERIC_RE.fullmatch(token.value) is None
    ):
        raise MmcifZeroOccupancyError(
            "invalid_occupancy_flag",
            "occupancy_flag must be an unquoted exact numeric token",
            line_number=token.line_number,
        )
    try:
        value = Decimal(token.value)
    except InvalidOperation as exc:
        raise MmcifZeroOccupancyError(
            "invalid_occupancy_flag",
            "occupancy_flag must be an exact numeric token",
            line_number=token.line_number,
        ) from exc
    if not value.is_finite() or value != Decimal(0):
        raise MmcifZeroOccupancyError(
            "nonzero_occupancy_flag",
            "selected declarations must report exact numeric zero occupancy",
            line_number=token.line_number,
        )
    return token.value


def _optional_pure_loop(
    block: CifBlock,
    *,
    category: str,
    required_headers: tuple[str, ...],
) -> tuple[CifLoop, dict[str, int], MmcifZeroOccupancyCategoryBinding] | None:
    scalar_tags = tuple(tag for tag in block.scalar_values if tag.startswith(f"{category}."))
    if scalar_tags:
        token = block.scalar_values[scalar_tags[0]]
        raise MmcifZeroOccupancyError(
            "category_must_be_loop",
            f"{category} must use one loop in this bounded profile",
            line_number=token.line_number,
        )
    candidates = [loop for loop in block.loops if category in loop.categories]
    if not candidates:
        return None
    if len(candidates) != 1:
        raise MmcifZeroOccupancyError(
            "multiple_category_loops",
            f"{category} must occur in exactly one loop",
            line_number=candidates[1].line_number,
        )
    loop = candidates[0]
    if loop.categories != (category,):
        raise MmcifZeroOccupancyError(
            "mixed_category_loop",
            "cross-category loops are outside this bounded declaration profile",
            line_number=loop.line_number,
        )
    if len(loop.rows) > MAX_MMCIF_ZERO_OCCUPANCY_ROWS:
        raise MmcifZeroOccupancyError(
            "too_many_declaration_rows",
            f"{category} exceeds the declaration row bound",
            line_number=loop.line_number,
        )
    if set(loop.tags) != set(required_headers) or len(loop.tags) != len(required_headers):
        raise MmcifZeroOccupancyError(
            "unsupported_headers",
            f"{category} must use the exact bounded declaration header set",
            line_number=loop.line_number,
        )
    index = {tag: position for position, tag in enumerate(loop.tags)}
    return (
        loop,
        index,
        MmcifZeroOccupancyCategoryBinding(
            category=category,
            headers=tuple(loop.tags),
            row_count=len(loop.rows),
            source_ordinal=block.category_order.index(category),
        ),
    )


def _semantic_maps(
    semantic: MmcifSemanticSnapshot,
) -> tuple[dict[str, str], dict[tuple[str, int], str]]:
    asym_to_entity = {row.asym_id: row.entity_id for row in semantic.asym_units}
    sequence = {
        (row.entity_id, row.sequence_number): row.monomer_id
        for row in semantic.polymer_sequence
    }
    return asym_to_entity, sequence


def _resolve_polymer_member(
    *,
    label_asym_id: str,
    label_seq_id: int,
    label_comp_id: str,
    asym_to_entity: Mapping[str, str],
    sequence: Mapping[tuple[str, int], str],
    line_number: int,
) -> str:
    entity_id = asym_to_entity.get(label_asym_id)
    if entity_id is None:
        raise MmcifZeroOccupancyError(
            "label_asym_reference_missing",
            "one declaration references an unknown label asym identity",
            line_number=line_number,
        )
    expected_comp = sequence.get((entity_id, label_seq_id))
    if expected_comp is None:
        raise MmcifZeroOccupancyError(
            "label_sequence_reference_missing",
            "one declaration references a sequence position outside the semantic carrier",
            line_number=line_number,
        )
    if expected_comp != label_comp_id:
        raise MmcifZeroOccupancyError(
            "label_component_mismatch",
            "one declaration component does not match the semantic polymer sequence",
            line_number=line_number,
        )
    return entity_id


def _parse_residues(
    parsed: tuple[CifLoop, dict[str, int], MmcifZeroOccupancyCategoryBinding] | None,
    *,
    asym_to_entity: Mapping[str, str],
    sequence: Mapping[tuple[str, int], str],
) -> tuple[MmcifZeroOccupancyResidueDeclaration, ...]:
    if parsed is None:
        return ()
    loop, index, _binding = parsed
    rows: list[MmcifZeroOccupancyResidueDeclaration] = []
    source_ids: set[int] = set()
    logical_keys: set[tuple[int, str, int]] = set()
    for ordinal, row in enumerate(loop.rows):
        source_token = row[index[f"{RESIDUE_CATEGORY}.id"]]
        source_id = _positive_integer(source_token, field=f"{RESIDUE_CATEGORY}.id")
        if source_id in source_ids:
            raise MmcifZeroOccupancyError(
                "duplicate_residue_source_id",
                "zero-occupancy residue source identifiers must be unique",
                line_number=source_token.line_number,
            )
        source_ids.add(source_id)
        _polymer_yes(row[index[f"{RESIDUE_CATEGORY}.polymer_flag"]])
        occupancy_token = _exact_zero(row[index[f"{RESIDUE_CATEGORY}.occupancy_flag"]])
        model_number = _positive_integer(
            row[index[f"{RESIDUE_CATEGORY}.pdb_model_num"]],
            field=f"{RESIDUE_CATEGORY}.pdb_model_num",
        )
        label_asym_token = row[index[f"{RESIDUE_CATEGORY}.label_asym_id"]]
        label_asym_id = _known_identity(
            label_asym_token,
            field=f"{RESIDUE_CATEGORY}.label_asym_id",
        )
        label_comp_id = _known_identity(
            row[index[f"{RESIDUE_CATEGORY}.label_comp_id"]],
            field=f"{RESIDUE_CATEGORY}.label_comp_id",
        )
        label_seq_id = _positive_integer(
            row[index[f"{RESIDUE_CATEGORY}.label_seq_id"]],
            field=f"{RESIDUE_CATEGORY}.label_seq_id",
        )
        entity_id = _resolve_polymer_member(
            label_asym_id=label_asym_id,
            label_seq_id=label_seq_id,
            label_comp_id=label_comp_id,
            asym_to_entity=asym_to_entity,
            sequence=sequence,
            line_number=label_asym_token.line_number,
        )
        logical_key = (model_number, label_asym_id, label_seq_id)
        if logical_key in logical_keys:
            raise MmcifZeroOccupancyError(
                "duplicate_residue_declaration",
                "one model/asym/sequence residue declaration occurs more than once",
                line_number=source_token.line_number,
            )
        logical_keys.add(logical_key)
        rows.append(
            MmcifZeroOccupancyResidueDeclaration(
                source_id=source_id,
                model_number=model_number,
                entity_id=entity_id,
                label_asym_id=label_asym_id,
                label_comp_id=label_comp_id,
                label_seq_id=label_seq_id,
                auth_asym_id=_semantic_value(
                    row[index[f"{RESIDUE_CATEGORY}.auth_asym_id"]]
                ),
                auth_comp_id=_semantic_value(
                    row[index[f"{RESIDUE_CATEGORY}.auth_comp_id"]]
                ),
                auth_seq_id=_semantic_value(
                    row[index[f"{RESIDUE_CATEGORY}.auth_seq_id"]]
                ),
                insertion_code=_semantic_value(
                    row[index[f"{RESIDUE_CATEGORY}.pdb_ins_code"]]
                ),
                occupancy_token=occupancy_token,
                source_ordinal=ordinal,
            )
        )
    return tuple(rows)


def _parse_atoms(
    parsed: tuple[CifLoop, dict[str, int], MmcifZeroOccupancyCategoryBinding] | None,
    *,
    asym_to_entity: Mapping[str, str],
    sequence: Mapping[tuple[str, int], str],
) -> tuple[MmcifZeroOccupancyAtomDeclaration, ...]:
    if parsed is None:
        return ()
    loop, index, _binding = parsed
    rows: list[MmcifZeroOccupancyAtomDeclaration] = []
    source_ids: set[int] = set()
    logical_keys: set[tuple[int, str, int, str, str, str]] = set()
    for ordinal, row in enumerate(loop.rows):
        source_token = row[index[f"{ATOM_CATEGORY}.id"]]
        source_id = _positive_integer(source_token, field=f"{ATOM_CATEGORY}.id")
        if source_id in source_ids:
            raise MmcifZeroOccupancyError(
                "duplicate_atom_source_id",
                "zero-occupancy atom source identifiers must be unique",
                line_number=source_token.line_number,
            )
        source_ids.add(source_id)
        _polymer_yes(row[index[f"{ATOM_CATEGORY}.polymer_flag"]])
        occupancy_token = _exact_zero(row[index[f"{ATOM_CATEGORY}.occupancy_flag"]])
        model_number = _positive_integer(
            row[index[f"{ATOM_CATEGORY}.pdb_model_num"]],
            field=f"{ATOM_CATEGORY}.pdb_model_num",
        )
        label_asym_token = row[index[f"{ATOM_CATEGORY}.label_asym_id"]]
        label_asym_id = _known_identity(
            label_asym_token,
            field=f"{ATOM_CATEGORY}.label_asym_id",
        )
        label_comp_id = _known_identity(
            row[index[f"{ATOM_CATEGORY}.label_comp_id"]],
            field=f"{ATOM_CATEGORY}.label_comp_id",
        )
        label_seq_id = _positive_integer(
            row[index[f"{ATOM_CATEGORY}.label_seq_id"]],
            field=f"{ATOM_CATEGORY}.label_seq_id",
        )
        label_atom_id = _known_identity(
            row[index[f"{ATOM_CATEGORY}.label_atom_id"]],
            field=f"{ATOM_CATEGORY}.label_atom_id",
        )
        label_alt_id = _semantic_value(row[index[f"{ATOM_CATEGORY}.label_alt_id"]])
        entity_id = _resolve_polymer_member(
            label_asym_id=label_asym_id,
            label_seq_id=label_seq_id,
            label_comp_id=label_comp_id,
            asym_to_entity=asym_to_entity,
            sequence=sequence,
            line_number=label_asym_token.line_number,
        )
        logical_key = (
            model_number,
            label_asym_id,
            label_seq_id,
            label_atom_id,
            label_alt_id.state,
            label_alt_id.value,
        )
        if logical_key in logical_keys:
            raise MmcifZeroOccupancyError(
                "duplicate_atom_declaration",
                "one model/asym/sequence/atom/alt declaration occurs more than once",
                line_number=source_token.line_number,
            )
        logical_keys.add(logical_key)
        rows.append(
            MmcifZeroOccupancyAtomDeclaration(
                source_id=source_id,
                model_number=model_number,
                entity_id=entity_id,
                label_asym_id=label_asym_id,
                label_comp_id=label_comp_id,
                label_seq_id=label_seq_id,
                label_atom_id=label_atom_id,
                label_alt_id=label_alt_id,
                auth_asym_id=_semantic_value(
                    row[index[f"{ATOM_CATEGORY}.auth_asym_id"]]
                ),
                auth_comp_id=_semantic_value(
                    row[index[f"{ATOM_CATEGORY}.auth_comp_id"]]
                ),
                auth_seq_id=_semantic_value(
                    row[index[f"{ATOM_CATEGORY}.auth_seq_id"]]
                ),
                insertion_code=_semantic_value(
                    row[index[f"{ATOM_CATEGORY}.pdb_ins_code"]]
                ),
                auth_atom_id=_semantic_value(
                    row[index[f"{ATOM_CATEGORY}.auth_atom_id"]]
                ),
                occupancy_token=occupancy_token,
                source_ordinal=ordinal,
            )
        )
    return tuple(rows)


def parse_mmcif_zero_occupancy_declarations(text: str) -> MmcifZeroOccupancySnapshot:
    """Parse bounded source-reported zero-occupancy declaration loops."""

    if type(text) is not str:
        raise TypeError("mmCIF zero-occupancy input must be a string")
    semantic = parse_mmcif_semantics(text)
    block = parse_cif_block(text)
    source_sha256 = hashlib.sha256(text.encode("ascii")).hexdigest()
    residue_parsed = _optional_pure_loop(
        block,
        category=RESIDUE_CATEGORY,
        required_headers=MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS,
    )
    atom_parsed = _optional_pure_loop(
        block,
        category=ATOM_CATEGORY,
        required_headers=MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS,
    )
    if residue_parsed is None and atom_parsed is None:
        raise MmcifZeroOccupancyError(
            "declaration_category_missing",
            "at least one bounded zero-occupancy declaration loop is required",
        )
    asym_to_entity, sequence = _semantic_maps(semantic)
    residues = _parse_residues(
        residue_parsed,
        asym_to_entity=asym_to_entity,
        sequence=sequence,
    )
    atoms = _parse_atoms(
        atom_parsed,
        asym_to_entity=asym_to_entity,
        sequence=sequence,
    )
    bindings = tuple(
        parsed[2] for parsed in (residue_parsed, atom_parsed) if parsed is not None
    )
    return MmcifZeroOccupancySnapshot(
        source_sha256=source_sha256,
        block_name=block.name,
        semantic_snapshot_sha256=semantic.snapshot_sha256,
        semantic_projection_sha256=semantic.semantic_projection_sha256,
        semantic_source_binding_sha256=semantic.source_binding_sha256,
        residue_declarations=residues,
        atom_declarations=atoms,
        source_category_order=block.category_order,
        category_bindings=bindings,
        uninterpreted_categories=tuple(
            category
            for category in block.category_order
            if category not in _SUPPORTED_CATEGORIES
        ),
    )


def mmcif_zero_occupancy_projection(
    snapshot: MmcifZeroOccupancySnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ZERO_OCCUPANCY_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_ZERO_OCCUPANCY_PROFILE_ID,
        "parser_version": MMCIF_ZERO_OCCUPANCY_PARSER_VERSION,
        "semantic_projection_sha256": snapshot.semantic_projection_sha256,
        "residue_declarations": [
            row.to_dict() for row in snapshot.residue_declarations
        ],
        "atom_declarations": [row.to_dict() for row in snapshot.atom_declarations],
        "row_order": "source_order_within_each_declaration_category",
        **_claim_policy(),
    }


def mmcif_zero_occupancy_source_binding(
    snapshot: MmcifZeroOccupancySnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ZERO_OCCUPANCY_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "block_name": snapshot.block_name,
        "semantic_snapshot_sha256": snapshot.semantic_snapshot_sha256,
        "semantic_source_binding_sha256": snapshot.semantic_source_binding_sha256,
        "source_category_order": list(snapshot.source_category_order),
        "category_bindings": [
            binding.to_dict() for binding in snapshot.category_bindings
        ],
        "uninterpreted_categories": list(snapshot.uninterpreted_categories),
    }


def mmcif_zero_occupancy_document(
    snapshot: MmcifZeroOccupancySnapshot,
) -> dict[str, Any]:
    projection = mmcif_zero_occupancy_projection(snapshot)
    source_binding = mmcif_zero_occupancy_source_binding(snapshot)
    return {
        "schema_id": MMCIF_ZERO_OCCUPANCY_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_ZERO_OCCUPANCY_PROFILE_ID,
        "parser_version": MMCIF_ZERO_OCCUPANCY_PARSER_VERSION,
        "declaration_projection": projection,
        "source_binding": source_binding,
        "declaration_projection_sha256": _sha256_document(projection),
        "source_binding_sha256": _sha256_document(source_binding),
        **snapshot.to_dict(),
    }


def require_mmcif_zero_occupancy_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("zero-occupancy document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_ZERO_OCCUPANCY_DOCUMENT_SCHEMA_ID:
        raise ValueError("zero-occupancy document schema mismatch")
    if document.get("profile_id") != MMCIF_ZERO_OCCUPANCY_PROFILE_ID:
        raise ValueError("zero-occupancy profile mismatch")
    if document.get("parser_version") != MMCIF_ZERO_OCCUPANCY_PARSER_VERSION:
        raise ValueError("zero-occupancy parser version mismatch")
    projection = document.get("declaration_projection")
    source_binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(source_binding, Mapping):
        raise ValueError("zero-occupancy document sections must be mappings")
    if projection.get("schema_id") != MMCIF_ZERO_OCCUPANCY_PROJECTION_SCHEMA_ID:
        raise ValueError("zero-occupancy projection schema mismatch")
    if source_binding.get("schema_id") != MMCIF_ZERO_OCCUPANCY_SOURCE_BINDING_SCHEMA_ID:
        raise ValueError("zero-occupancy source binding schema mismatch")
    projection_digest = _sha256_document(dict(projection))
    source_digest = _sha256_document(dict(source_binding))
    if document.get("declaration_projection_sha256") != projection_digest:
        raise ValueError("zero-occupancy projection digest mismatch")
    if document.get("source_binding_sha256") != source_digest:
        raise ValueError("zero-occupancy source binding digest mismatch")
    expected_snapshot_digest = _sha256_document(
        {
            "schema_id": MMCIF_ZERO_OCCUPANCY_DOCUMENT_SCHEMA_ID,
            "declaration_projection_sha256": projection_digest,
            "source_binding_sha256": source_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot_digest:
        raise ValueError("zero-occupancy snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("zero-occupancy claim policy mismatch")
    residue_rows = projection.get("residue_declarations")
    atom_rows = projection.get("atom_declarations")
    if not isinstance(residue_rows, list) or not isinstance(atom_rows, list):
        raise ValueError("zero-occupancy declaration rows must be lists")
    if not residue_rows and not atom_rows:
        raise ValueError("zero-occupancy document must contain declaration rows")
    if document.get("residue_declaration_count") != len(residue_rows):
        raise ValueError("zero-occupancy residue count mismatch")
    if document.get("atom_declaration_count") != len(atom_rows):
        raise ValueError("zero-occupancy atom count mismatch")
    source_sha = source_binding.get("source_sha256")
    if _SHA256_RE.fullmatch(str(source_sha or "")) is None:
        raise ValueError("zero-occupancy source digest invalid")
    if document.get("source_sha256") != source_sha:
        raise ValueError("zero-occupancy source digest binding mismatch")
    semantic_projection_sha = projection.get("semantic_projection_sha256")
    if _SHA256_RE.fullmatch(str(semantic_projection_sha or "")) is None:
        raise ValueError("zero-occupancy semantic projection digest invalid")
    semantic_snapshot_sha = source_binding.get("semantic_snapshot_sha256")
    semantic_binding_sha = source_binding.get("semantic_source_binding_sha256")
    if _SHA256_RE.fullmatch(str(semantic_snapshot_sha or "")) is None:
        raise ValueError("zero-occupancy semantic snapshot digest invalid")
    if _SHA256_RE.fullmatch(str(semantic_binding_sha or "")) is None:
        raise ValueError("zero-occupancy semantic source binding digest invalid")
    return payload


def mmcif_zero_occupancy_json_bytes(
    snapshot: MmcifZeroOccupancySnapshot,
) -> bytes:
    return _canonical_json_bytes(mmcif_zero_occupancy_document(snapshot))


def write_mmcif_zero_occupancy_json(
    path: str | Path,
    snapshot: MmcifZeroOccupancySnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_zero_occupancy_json_bytes(snapshot) + b"\n"
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
        file_fd = -1
        os.replace(temporary_path, destination)
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
        )
        directory_fd = os.open(destination.parent, directory_flags)
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
    "ATOM_CATEGORY",
    "MAX_MMCIF_ZERO_OCCUPANCY_INTEGER",
    "MAX_MMCIF_ZERO_OCCUPANCY_ROWS",
    "MAX_MMCIF_ZERO_OCCUPANCY_TOKEN_CHARS",
    "MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS",
    "MMCIF_ZERO_OCCUPANCY_DOCUMENT_SCHEMA_ID",
    "MMCIF_ZERO_OCCUPANCY_PARSER_VERSION",
    "MMCIF_ZERO_OCCUPANCY_PROFILE_ID",
    "MMCIF_ZERO_OCCUPANCY_PROJECTION_SCHEMA_ID",
    "MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS",
    "MMCIF_ZERO_OCCUPANCY_SOURCE_BINDING_SCHEMA_ID",
    "MmcifZeroOccupancyAtomDeclaration",
    "MmcifZeroOccupancyCategoryBinding",
    "MmcifZeroOccupancyError",
    "MmcifZeroOccupancyResidueDeclaration",
    "MmcifZeroOccupancySnapshot",
    "RESIDUE_CATEGORY",
    "mmcif_zero_occupancy_document",
    "mmcif_zero_occupancy_json_bytes",
    "mmcif_zero_occupancy_projection",
    "mmcif_zero_occupancy_source_binding",
    "parse_mmcif_zero_occupancy_declarations",
    "require_mmcif_zero_occupancy_document",
    "write_mmcif_zero_occupancy_json",
]
