"""Bounded source-preservation projection for mmCIF alternate locations.

This module composes the accepted mmCIF lexical and semantic projections with one
reviewed ``_atom_site`` common-core surface. It preserves every source row, token
state, header order, category order, and explicit ``label_alt_id`` declaration.

It deliberately does not select a conformer, materialize or numerically interpret
coordinates, weight occupancies, infer populations or missingness, equate author
and label identifiers, validate chemistry/topology, prepare a system, or authorize
runtime or product execution.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from .mmcif_zero_occupancy import (
    ATOM_CATEGORY as ZERO_OCCUPANCY_ATOM_CATEGORY,
    RESIDUE_CATEGORY as ZERO_OCCUPANCY_RESIDUE_CATEGORY,
    MmcifZeroOccupancySnapshot,
    parse_mmcif_zero_occupancy_declarations,
)


ATOM_SITE_CATEGORY = "_atom_site"
MMCIF_ALTLOC_SOURCE_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_altloc_source_projection/1.0.0"
)
MMCIF_ALTLOC_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_altloc_source_binding/1.0.0"
)
MMCIF_ALTLOC_SOURCE_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_altloc_source_document/1.0.0"
)
MMCIF_ALTLOC_SOURCE_PROFILE_ID = (
    "bounded_mmcif_atom_site_altloc_source_preservation/1.0.0"
)
MMCIF_ALTLOC_SOURCE_PARSER_VERSION = "1.0.0"
MAX_MMCIF_ALTLOC_SOURCE_ROWS = 100_000
MAX_MMCIF_ALTLOC_SOURCE_TOKEN_CHARS = 256
MAX_MMCIF_ALTLOC_SOURCE_INTEGER = (1 << 53) - 1

MMCIF_ALTLOC_SOURCE_ATOM_SITE_HEADERS = (
    "_atom_site.group_pdb",
    "_atom_site.id",
    "_atom_site.type_symbol",
    "_atom_site.label_atom_id",
    "_atom_site.label_alt_id",
    "_atom_site.label_comp_id",
    "_atom_site.label_asym_id",
    "_atom_site.label_entity_id",
    "_atom_site.label_seq_id",
    "_atom_site.pdbx_pdb_ins_code",
    "_atom_site.cartn_x",
    "_atom_site.cartn_y",
    "_atom_site.cartn_z",
    "_atom_site.occupancy",
    "_atom_site.b_iso_or_equiv",
    "_atom_site.pdbx_formal_charge",
    "_atom_site.auth_seq_id",
    "_atom_site.auth_comp_id",
    "_atom_site.auth_asym_id",
    "_atom_site.auth_atom_id",
    "_atom_site.pdbx_pdb_model_num",
)

_POSITIVE_INTEGER_RE = re.compile(r"^[1-9][0-9]*$")
_PRINTABLE_IDENTITY_RE = re.compile(r"^[!-~]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SEMANTIC_CATEGORIES = frozenset(
    {"_entry", "_entity", "_struct_asym", "_entity_poly", "_entity_poly_seq"}
)
_SUPPORTED_CATEGORIES = _SEMANTIC_CATEGORIES | {
    ATOM_SITE_CATEGORY,
    ZERO_OCCUPANCY_RESIDUE_CATEGORY,
    ZERO_OCCUPANCY_ATOM_CATEGORY,
}


class MmcifAltlocSourceError(ValueError):
    """Stable fail-closed error that does not echo molecular identity values."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"mmcif_altloc_source:{self.code}{suffix}: {self.detail}")


@dataclass(frozen=True, slots=True)
class MmcifAltlocCategoryBinding:
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
class MmcifAltlocAtomSiteRow:
    source_id: str
    group_pdb: str
    type_symbol: str
    label_atom_id: str
    label_alt_id: MmcifSemanticValue
    label_comp_id: str
    label_asym_id: str
    label_entity_id: str
    label_seq_id: MmcifSemanticValue
    label_seq_number: int | None
    insertion_code: MmcifSemanticValue
    cartn_x: MmcifSemanticValue
    cartn_y: MmcifSemanticValue
    cartn_z: MmcifSemanticValue
    occupancy: MmcifSemanticValue
    b_iso_or_equiv: MmcifSemanticValue
    formal_charge: MmcifSemanticValue
    auth_seq_id: MmcifSemanticValue
    auth_comp_id: MmcifSemanticValue
    auth_asym_id: MmcifSemanticValue
    auth_atom_id: MmcifSemanticValue
    model_number: int
    entity_type: str
    source_ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "group_pdb": self.group_pdb,
            "type_symbol": self.type_symbol,
            "label_atom_id": self.label_atom_id,
            "label_alt_id": self.label_alt_id.to_dict(),
            "label_comp_id": self.label_comp_id,
            "label_asym_id": self.label_asym_id,
            "label_entity_id": self.label_entity_id,
            "label_seq_id": self.label_seq_id.to_dict(),
            "label_seq_number": self.label_seq_number,
            "insertion_code": self.insertion_code.to_dict(),
            "cartn_x": self.cartn_x.to_dict(),
            "cartn_y": self.cartn_y.to_dict(),
            "cartn_z": self.cartn_z.to_dict(),
            "occupancy": self.occupancy.to_dict(),
            "b_iso_or_equiv": self.b_iso_or_equiv.to_dict(),
            "formal_charge": self.formal_charge.to_dict(),
            "auth_seq_id": self.auth_seq_id.to_dict(),
            "auth_comp_id": self.auth_comp_id.to_dict(),
            "auth_asym_id": self.auth_asym_id.to_dict(),
            "auth_atom_id": self.auth_atom_id.to_dict(),
            "model_number": self.model_number,
            "entity_type": self.entity_type,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class MmcifAltlocAffectedSite:
    model_number: int
    label_entity_id: str
    label_asym_id: str
    label_comp_id: str
    label_seq_id: MmcifSemanticValue
    label_seq_number: int | None
    label_atom_id: str
    source_row_ordinals: tuple[int, ...]
    explicit_altloc_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_number": self.model_number,
            "label_entity_id": self.label_entity_id,
            "label_asym_id": self.label_asym_id,
            "label_comp_id": self.label_comp_id,
            "label_seq_id": self.label_seq_id.to_dict(),
            "label_seq_number": self.label_seq_number,
            "label_atom_id": self.label_atom_id,
            "source_row_ordinals": list(self.source_row_ordinals),
            "source_row_count": len(self.source_row_ordinals),
            "explicit_altloc_ids": list(self.explicit_altloc_ids),
            "explicit_altloc_count": len(self.explicit_altloc_ids),
        }


@dataclass(frozen=True, slots=True)
class MmcifAltlocSourceSnapshot:
    source_sha256: str
    block_name: str
    semantic_snapshot_sha256: str
    semantic_projection_sha256: str
    semantic_source_binding_sha256: str
    zero_occupancy_snapshot_sha256: str
    zero_occupancy_projection_sha256: str
    zero_occupancy_source_binding_sha256: str
    atom_site_rows: tuple[MmcifAltlocAtomSiteRow, ...]
    affected_sites: tuple[MmcifAltlocAffectedSite, ...]
    explicit_altloc_ids: tuple[str, ...]
    source_category_order: tuple[str, ...]
    atom_site_binding: MmcifAltlocCategoryBinding
    uninterpreted_categories: tuple[str, ...]

    @property
    def altloc_projection_sha256(self) -> str:
        return _sha256_document(mmcif_altloc_source_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_document(mmcif_altloc_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256_document(
            {
                "schema_id": MMCIF_ALTLOC_SOURCE_DOCUMENT_SCHEMA_ID,
                "altloc_projection_sha256": self.altloc_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_ALTLOC_SOURCE_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_ALTLOC_SOURCE_PROFILE_ID,
            "parser_version": MMCIF_ALTLOC_SOURCE_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "block_name": self.block_name,
            "semantic_snapshot_sha256": self.semantic_snapshot_sha256,
            "zero_occupancy_declarations_present": bool(
                self.zero_occupancy_snapshot_sha256
            ),
            "atom_site_row_count": len(self.atom_site_rows),
            "explicit_altloc_row_count": sum(
                1 for row in self.atom_site_rows if row.label_alt_id.state == "known"
            ),
            "explicit_altloc_id_count": len(self.explicit_altloc_ids),
            "affected_site_count": len(self.affected_sites),
            "uninterpreted_categories": list(self.uninterpreted_categories),
            "altloc_projection_sha256": self.altloc_projection_sha256,
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
        "source_atom_site_rows_preserved": True,
        "source_row_order_preserved": True,
        "label_alt_id_tokens_preserved": True,
        "semantic_identity_references_verified": True,
        "altloc_selected": False,
        "coordinates_materialized": False,
        "coordinate_values_interpreted": False,
        "coordinate_observation_assessed": False,
        "missingness_inferred": False,
        "auth_label_equivalence_inferred": False,
        "altloc_population_interpreted": False,
        "occupancy_population_interpreted": False,
        "occupancy_weighting_applied": False,
        "zero_occupancy_atom_site_crosschecked": False,
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
    if token.multiline:
        raise MmcifAltlocSourceError(
            "multiline_atom_site_value_not_supported",
            "atom_site values must be bounded single-line tokens",
            line_number=token.line_number,
        )
    if len(token.value) > MAX_MMCIF_ALTLOC_SOURCE_TOKEN_CHARS:
        raise MmcifAltlocSourceError(
            "atom_site_token_out_of_bounds",
            "one atom_site value exceeds the bounded token domain",
            line_number=token.line_number,
        )
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
        raise MmcifAltlocSourceError(
            "atom_site_token_out_of_bounds",
            "one atom_site value exceeds the bounded token domain",
            line_number=token.line_number,
        ) from exc


def _known_identity(token: CifToken, *, field: str) -> str:
    value = _semantic_value(token)
    if value.state != "known":
        raise MmcifAltlocSourceError(
            "required_identity_marker",
            f"{field} must be a known source identity",
            line_number=token.line_number,
        )
    if _PRINTABLE_IDENTITY_RE.fullmatch(value.value) is None:
        raise MmcifAltlocSourceError(
            "invalid_identity_token",
            f"{field} must be a bounded printable token without whitespace",
            line_number=token.line_number,
        )
    return value.value


def _positive_integer(token: CifToken, *, field: str) -> int:
    if (
        token.quoted
        or token.multiline
        or _POSITIVE_INTEGER_RE.fullmatch(token.value) is None
    ):
        raise MmcifAltlocSourceError(
            "invalid_positive_integer",
            f"{field} must be a canonical positive integer",
            line_number=token.line_number,
        )
    value = int(token.value)
    if value > MAX_MMCIF_ALTLOC_SOURCE_INTEGER:
        raise MmcifAltlocSourceError(
            "positive_integer_out_of_bounds",
            f"{field} exceeds the bounded integer domain",
            line_number=token.line_number,
        )
    return value


def _atom_site_loop(
    block: CifBlock,
) -> tuple[CifLoop, dict[str, int], MmcifAltlocCategoryBinding]:
    scalar_tags = tuple(
        tag for tag in block.scalar_values if tag.startswith(f"{ATOM_SITE_CATEGORY}.")
    )
    if scalar_tags:
        token = block.scalar_values[scalar_tags[0]]
        raise MmcifAltlocSourceError(
            "atom_site_must_be_loop",
            "_atom_site must use one loop in this bounded profile",
            line_number=token.line_number,
        )
    candidates = [loop for loop in block.loops if ATOM_SITE_CATEGORY in loop.categories]
    if not candidates:
        raise MmcifAltlocSourceError(
            "atom_site_category_missing",
            "one reviewed _atom_site loop is required",
        )
    if len(candidates) != 1:
        raise MmcifAltlocSourceError(
            "multiple_atom_site_loops",
            "_atom_site must occur in exactly one loop",
            line_number=candidates[1].line_number,
        )
    loop = candidates[0]
    if loop.categories != (ATOM_SITE_CATEGORY,):
        raise MmcifAltlocSourceError(
            "mixed_atom_site_loop",
            "cross-category atom_site loops are outside this bounded profile",
            line_number=loop.line_number,
        )
    if len(loop.rows) > MAX_MMCIF_ALTLOC_SOURCE_ROWS:
        raise MmcifAltlocSourceError(
            "too_many_atom_site_rows",
            "_atom_site exceeds the bounded row limit",
            line_number=loop.line_number,
        )
    if (
        set(loop.tags) != set(MMCIF_ALTLOC_SOURCE_ATOM_SITE_HEADERS)
        or len(loop.tags) != len(MMCIF_ALTLOC_SOURCE_ATOM_SITE_HEADERS)
    ):
        raise MmcifAltlocSourceError(
            "unsupported_atom_site_headers",
            "_atom_site must use the exact reviewed common-core header set",
            line_number=loop.line_number,
        )
    return (
        loop,
        {tag: position for position, tag in enumerate(loop.tags)},
        MmcifAltlocCategoryBinding(
            category=ATOM_SITE_CATEGORY,
            headers=tuple(loop.tags),
            row_count=len(loop.rows),
            source_ordinal=block.category_order.index(ATOM_SITE_CATEGORY),
        ),
    )


def _semantic_maps(
    semantic: MmcifSemanticSnapshot,
) -> tuple[dict[str, str], dict[str, str], dict[tuple[str, int], str]]:
    entity_types = {row.entity_id: row.entity_type for row in semantic.entities}
    asym_to_entity = {row.asym_id: row.entity_id for row in semantic.asym_units}
    sequence = {
        (row.entity_id, row.sequence_number): row.monomer_id
        for row in semantic.polymer_sequence
    }
    return entity_types, asym_to_entity, sequence


def _parse_rows(
    loop: CifLoop,
    index: Mapping[str, int],
    *,
    semantic: MmcifSemanticSnapshot,
) -> tuple[MmcifAltlocAtomSiteRow, ...]:
    entity_types, asym_to_entity, sequence = _semantic_maps(semantic)
    rows: list[MmcifAltlocAtomSiteRow] = []
    source_ids: set[str] = set()
    logical_rows: set[tuple[Any, ...]] = set()

    for ordinal, source_row in enumerate(loop.rows):
        source_id_token = source_row[index["_atom_site.id"]]
        source_id = _known_identity(source_id_token, field="_atom_site.id")
        if source_id in source_ids:
            raise MmcifAltlocSourceError(
                "duplicate_atom_site_id",
                "atom_site source identifiers must be unique",
                line_number=source_id_token.line_number,
            )
        source_ids.add(source_id)

        group_token = source_row[index["_atom_site.group_pdb"]]
        group_pdb = _known_identity(group_token, field="_atom_site.group_pdb")
        if group_pdb.upper() not in {"ATOM", "HETATM"}:
            raise MmcifAltlocSourceError(
                "unsupported_group_pdb",
                "group_PDB must be ATOM or HETATM in this bounded profile",
                line_number=group_token.line_number,
            )

        type_symbol = _known_identity(
            source_row[index["_atom_site.type_symbol"]],
            field="_atom_site.type_symbol",
        )
        label_atom_id = _known_identity(
            source_row[index["_atom_site.label_atom_id"]],
            field="_atom_site.label_atom_id",
        )
        label_alt_token = source_row[index["_atom_site.label_alt_id"]]
        label_alt_id = _semantic_value(label_alt_token)
        if label_alt_id.state == "known":
            _known_identity(label_alt_token, field="_atom_site.label_alt_id")
        label_comp_id = _known_identity(
            source_row[index["_atom_site.label_comp_id"]],
            field="_atom_site.label_comp_id",
        )
        label_asym_token = source_row[index["_atom_site.label_asym_id"]]
        label_asym_id = _known_identity(
            label_asym_token,
            field="_atom_site.label_asym_id",
        )
        label_entity_id = _known_identity(
            source_row[index["_atom_site.label_entity_id"]],
            field="_atom_site.label_entity_id",
        )
        expected_entity = asym_to_entity.get(label_asym_id)
        if expected_entity is None:
            raise MmcifAltlocSourceError(
                "label_asym_reference_missing",
                "one atom_site row references an unknown label asym identity",
                line_number=label_asym_token.line_number,
            )
        if expected_entity != label_entity_id:
            raise MmcifAltlocSourceError(
                "label_entity_reference_mismatch",
                "one atom_site label entity disagrees with the semantic asym carrier",
                line_number=label_asym_token.line_number,
            )
        entity_type = entity_types[label_entity_id]

        label_seq_token = source_row[index["_atom_site.label_seq_id"]]
        label_seq_id = _semantic_value(label_seq_token)
        label_seq_number: int | None = None
        if entity_type == "polymer":
            label_seq_number = _positive_integer(
                label_seq_token,
                field="_atom_site.label_seq_id",
            )
            expected_comp = sequence.get((label_entity_id, label_seq_number))
            if expected_comp is None:
                raise MmcifAltlocSourceError(
                    "label_sequence_reference_missing",
                    "one polymer atom_site row references a sequence position outside the semantic carrier",
                    line_number=label_seq_token.line_number,
                )
            if expected_comp != label_comp_id:
                raise MmcifAltlocSourceError(
                    "label_component_mismatch",
                    "one polymer atom_site component disagrees with the semantic sequence",
                    line_number=label_seq_token.line_number,
                )

        model_number = _positive_integer(
            source_row[index["_atom_site.pdbx_pdb_model_num"]],
            field="_atom_site.pdbx_pdb_model_num",
        )
        logical_key = (
            model_number,
            label_entity_id,
            label_asym_id,
            label_seq_id.state,
            label_seq_id.value,
            label_comp_id,
            label_atom_id,
            label_alt_id.state,
            label_alt_id.value,
        )
        if logical_key in logical_rows:
            raise MmcifAltlocSourceError(
                "duplicate_atom_site_logical_row",
                "one model/site/alternate-location declaration occurs more than once",
                line_number=source_id_token.line_number,
            )
        logical_rows.add(logical_key)

        rows.append(
            MmcifAltlocAtomSiteRow(
                source_id=source_id,
                group_pdb=group_pdb,
                type_symbol=type_symbol,
                label_atom_id=label_atom_id,
                label_alt_id=label_alt_id,
                label_comp_id=label_comp_id,
                label_asym_id=label_asym_id,
                label_entity_id=label_entity_id,
                label_seq_id=label_seq_id,
                label_seq_number=label_seq_number,
                insertion_code=_semantic_value(
                    source_row[index["_atom_site.pdbx_pdb_ins_code"]]
                ),
                cartn_x=_semantic_value(source_row[index["_atom_site.cartn_x"]]),
                cartn_y=_semantic_value(source_row[index["_atom_site.cartn_y"]]),
                cartn_z=_semantic_value(source_row[index["_atom_site.cartn_z"]]),
                occupancy=_semantic_value(source_row[index["_atom_site.occupancy"]]),
                b_iso_or_equiv=_semantic_value(
                    source_row[index["_atom_site.b_iso_or_equiv"]]
                ),
                formal_charge=_semantic_value(
                    source_row[index["_atom_site.pdbx_formal_charge"]]
                ),
                auth_seq_id=_semantic_value(source_row[index["_atom_site.auth_seq_id"]]),
                auth_comp_id=_semantic_value(
                    source_row[index["_atom_site.auth_comp_id"]]
                ),
                auth_asym_id=_semantic_value(
                    source_row[index["_atom_site.auth_asym_id"]]
                ),
                auth_atom_id=_semantic_value(
                    source_row[index["_atom_site.auth_atom_id"]]
                ),
                model_number=model_number,
                entity_type=entity_type,
                source_ordinal=ordinal,
            )
        )
    return tuple(rows)


def _affected_sites(
    rows: tuple[MmcifAltlocAtomSiteRow, ...],
) -> tuple[tuple[MmcifAltlocAffectedSite, ...], tuple[str, ...]]:
    site_rows: dict[tuple[Any, ...], list[MmcifAltlocAtomSiteRow]] = {}
    explicit_global: dict[str, None] = {}
    affected_keys: set[tuple[Any, ...]] = set()
    for row in rows:
        key = (
            row.model_number,
            row.label_entity_id,
            row.label_asym_id,
            row.label_comp_id,
            row.label_seq_id.state,
            row.label_seq_id.value,
            row.label_atom_id,
        )
        site_rows.setdefault(key, []).append(row)
        if row.label_alt_id.state == "known":
            affected_keys.add(key)
            explicit_global.setdefault(row.label_alt_id.value, None)
    if not explicit_global:
        raise MmcifAltlocSourceError(
            "explicit_altloc_missing",
            "at least one known label_alt_id declaration is required",
        )

    result: list[MmcifAltlocAffectedSite] = []
    for key, grouped in site_rows.items():
        if key not in affected_keys:
            continue
        first = grouped[0]
        explicit: dict[str, None] = {}
        for row in grouped:
            if row.label_alt_id.state == "known":
                explicit.setdefault(row.label_alt_id.value, None)
        result.append(
            MmcifAltlocAffectedSite(
                model_number=first.model_number,
                label_entity_id=first.label_entity_id,
                label_asym_id=first.label_asym_id,
                label_comp_id=first.label_comp_id,
                label_seq_id=first.label_seq_id,
                label_seq_number=first.label_seq_number,
                label_atom_id=first.label_atom_id,
                source_row_ordinals=tuple(row.source_ordinal for row in grouped),
                explicit_altloc_ids=tuple(explicit),
            )
        )
    return tuple(result), tuple(explicit_global)


def _optional_zero_occupancy(
    text: str,
    block: CifBlock,
) -> MmcifZeroOccupancySnapshot | None:
    if not {
        ZERO_OCCUPANCY_RESIDUE_CATEGORY,
        ZERO_OCCUPANCY_ATOM_CATEGORY,
    }.intersection(block.category_order):
        return None
    return parse_mmcif_zero_occupancy_declarations(text)


def parse_mmcif_altloc_source(text: str) -> MmcifAltlocSourceSnapshot:
    """Preserve a bounded alternate-location-bearing ``_atom_site`` source loop."""

    if type(text) is not str:
        raise TypeError("mmCIF alternate-location source input must be a string")
    semantic = parse_mmcif_semantics(text)
    block = parse_cif_block(text)
    loop, index, binding = _atom_site_loop(block)
    rows = _parse_rows(loop, index, semantic=semantic)
    sites, explicit_altloc_ids = _affected_sites(rows)
    zero = _optional_zero_occupancy(text, block)
    return MmcifAltlocSourceSnapshot(
        source_sha256=hashlib.sha256(text.encode("ascii")).hexdigest(),
        block_name=block.name,
        semantic_snapshot_sha256=semantic.snapshot_sha256,
        semantic_projection_sha256=semantic.semantic_projection_sha256,
        semantic_source_binding_sha256=semantic.source_binding_sha256,
        zero_occupancy_snapshot_sha256="" if zero is None else zero.snapshot_sha256,
        zero_occupancy_projection_sha256=(
            "" if zero is None else zero.declaration_projection_sha256
        ),
        zero_occupancy_source_binding_sha256=(
            "" if zero is None else zero.source_binding_sha256
        ),
        atom_site_rows=rows,
        affected_sites=sites,
        explicit_altloc_ids=explicit_altloc_ids,
        source_category_order=tuple(block.category_order),
        atom_site_binding=binding,
        uninterpreted_categories=tuple(
            category
            for category in block.category_order
            if category not in _SUPPORTED_CATEGORIES
        ),
    )


def mmcif_altloc_source_projection(
    snapshot: MmcifAltlocSourceSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ALTLOC_SOURCE_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_ALTLOC_SOURCE_PROFILE_ID,
        "parser_version": MMCIF_ALTLOC_SOURCE_PARSER_VERSION,
        "semantic_projection_sha256": snapshot.semantic_projection_sha256,
        "zero_occupancy_projection_sha256": snapshot.zero_occupancy_projection_sha256,
        "atom_site_rows": [row.to_dict() for row in snapshot.atom_site_rows],
        "affected_sites": [site.to_dict() for site in snapshot.affected_sites],
        "explicit_altloc_ids": list(snapshot.explicit_altloc_ids),
        "row_order": "source_order_within_atom_site",
        **_claim_policy(),
    }


def mmcif_altloc_source_binding(
    snapshot: MmcifAltlocSourceSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ALTLOC_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "block_name": snapshot.block_name,
        "semantic_snapshot_sha256": snapshot.semantic_snapshot_sha256,
        "semantic_source_binding_sha256": snapshot.semantic_source_binding_sha256,
        "zero_occupancy_snapshot_sha256": snapshot.zero_occupancy_snapshot_sha256,
        "zero_occupancy_source_binding_sha256": (
            snapshot.zero_occupancy_source_binding_sha256
        ),
        "source_category_order": list(snapshot.source_category_order),
        "atom_site_binding": snapshot.atom_site_binding.to_dict(),
        "uninterpreted_categories": list(snapshot.uninterpreted_categories),
    }


def mmcif_altloc_source_document(
    snapshot: MmcifAltlocSourceSnapshot,
) -> dict[str, Any]:
    projection = mmcif_altloc_source_projection(snapshot)
    source_binding = mmcif_altloc_source_binding(snapshot)
    return {
        "schema_id": MMCIF_ALTLOC_SOURCE_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_ALTLOC_SOURCE_PROFILE_ID,
        "parser_version": MMCIF_ALTLOC_SOURCE_PARSER_VERSION,
        "altloc_projection": projection,
        "source_binding": source_binding,
        "altloc_projection_sha256": _sha256_document(projection),
        "source_binding_sha256": _sha256_document(source_binding),
        **snapshot.to_dict(),
    }


def require_mmcif_altloc_source_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("alternate-location source document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_ALTLOC_SOURCE_DOCUMENT_SCHEMA_ID:
        raise ValueError("alternate-location source document schema mismatch")
    if document.get("profile_id") != MMCIF_ALTLOC_SOURCE_PROFILE_ID:
        raise ValueError("alternate-location source profile mismatch")
    if document.get("parser_version") != MMCIF_ALTLOC_SOURCE_PARSER_VERSION:
        raise ValueError("alternate-location source parser version mismatch")
    projection = document.get("altloc_projection")
    source_binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(source_binding, Mapping):
        raise ValueError("alternate-location source document sections must be mappings")
    if projection.get("schema_id") != MMCIF_ALTLOC_SOURCE_PROJECTION_SCHEMA_ID:
        raise ValueError("alternate-location source projection schema mismatch")
    if source_binding.get("schema_id") != MMCIF_ALTLOC_SOURCE_BINDING_SCHEMA_ID:
        raise ValueError("alternate-location source binding schema mismatch")
    projection_digest = _sha256_document(dict(projection))
    source_digest = _sha256_document(dict(source_binding))
    if document.get("altloc_projection_sha256") != projection_digest:
        raise ValueError("alternate-location source projection digest mismatch")
    if document.get("source_binding_sha256") != source_digest:
        raise ValueError("alternate-location source binding digest mismatch")
    expected_snapshot_digest = _sha256_document(
        {
            "schema_id": MMCIF_ALTLOC_SOURCE_DOCUMENT_SCHEMA_ID,
            "altloc_projection_sha256": projection_digest,
            "source_binding_sha256": source_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot_digest:
        raise ValueError("alternate-location source snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("alternate-location source claim policy mismatch")

    rows = projection.get("atom_site_rows")
    affected = projection.get("affected_sites")
    explicit_ids = projection.get("explicit_altloc_ids")
    if not isinstance(rows, list) or not rows:
        raise ValueError("alternate-location source rows must be a non-empty list")
    if not isinstance(affected, list) or not affected:
        raise ValueError("alternate-location affected sites must be a non-empty list")
    if not isinstance(explicit_ids, list) or not explicit_ids:
        raise ValueError("alternate-location explicit identifiers must be a non-empty list")
    if document.get("atom_site_row_count") != len(rows):
        raise ValueError("alternate-location source row count mismatch")
    if document.get("affected_site_count") != len(affected):
        raise ValueError("alternate-location affected-site count mismatch")
    if document.get("explicit_altloc_id_count") != len(explicit_ids):
        raise ValueError("alternate-location identifier count mismatch")

    source_sha = source_binding.get("source_sha256")
    semantic_projection_sha = projection.get("semantic_projection_sha256")
    semantic_snapshot_sha = source_binding.get("semantic_snapshot_sha256")
    semantic_binding_sha = source_binding.get("semantic_source_binding_sha256")
    for label, value in (
        ("source", source_sha),
        ("semantic projection", semantic_projection_sha),
        ("semantic snapshot", semantic_snapshot_sha),
        ("semantic source binding", semantic_binding_sha),
    ):
        if _SHA256_RE.fullmatch(str(value or "")) is None:
            raise ValueError(f"alternate-location {label} digest invalid")
    if document.get("source_sha256") != source_sha:
        raise ValueError("alternate-location source digest binding mismatch")

    zero_present = document.get("zero_occupancy_declarations_present") is True
    zero_values = (
        projection.get("zero_occupancy_projection_sha256"),
        source_binding.get("zero_occupancy_snapshot_sha256"),
        source_binding.get("zero_occupancy_source_binding_sha256"),
    )
    if zero_present:
        if any(_SHA256_RE.fullmatch(str(value or "")) is None for value in zero_values):
            raise ValueError("alternate-location zero-occupancy digest invalid")
    elif any(value not in {"", None} for value in zero_values):
        raise ValueError("alternate-location zero-occupancy presence mismatch")
    return payload


def mmcif_altloc_source_json_bytes(
    snapshot: MmcifAltlocSourceSnapshot,
) -> bytes:
    return _canonical_json_bytes(mmcif_altloc_source_document(snapshot))


def write_mmcif_altloc_source_json(
    path: str | Path,
    snapshot: MmcifAltlocSourceSnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_altloc_source_json_bytes(snapshot) + b"\n"
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
    "ATOM_SITE_CATEGORY",
    "MAX_MMCIF_ALTLOC_SOURCE_INTEGER",
    "MAX_MMCIF_ALTLOC_SOURCE_ROWS",
    "MAX_MMCIF_ALTLOC_SOURCE_TOKEN_CHARS",
    "MMCIF_ALTLOC_SOURCE_ATOM_SITE_HEADERS",
    "MMCIF_ALTLOC_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_ALTLOC_SOURCE_DOCUMENT_SCHEMA_ID",
    "MMCIF_ALTLOC_SOURCE_PARSER_VERSION",
    "MMCIF_ALTLOC_SOURCE_PROFILE_ID",
    "MMCIF_ALTLOC_SOURCE_PROJECTION_SCHEMA_ID",
    "MmcifAltlocAffectedSite",
    "MmcifAltlocAtomSiteRow",
    "MmcifAltlocCategoryBinding",
    "MmcifAltlocSourceError",
    "MmcifAltlocSourceSnapshot",
    "mmcif_altloc_source_binding",
    "mmcif_altloc_source_document",
    "mmcif_altloc_source_json_bytes",
    "mmcif_altloc_source_projection",
    "parse_mmcif_altloc_source",
    "require_mmcif_altloc_source_document",
    "write_mmcif_altloc_source_json",
]
