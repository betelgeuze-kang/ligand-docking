"""Bounded source-preservation projection for mmCIF alternate-location rows.

The projection composes the accepted entity/asym/polymer-sequence semantic carrier
with a bounded polymer ``_atom_site`` identity surface. It preserves alternate
location marker states and source order without selecting a conformer, weighting
occupancies, interpreting coordinates, or constructing topology.
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

from .mmcif_semantics import MmcifSemanticSnapshot, MmcifSemanticValue, parse_mmcif_semantics
from .mmcif_syntax import CifBlock, CifLoop, CifToken, parse_cif_block


MMCIF_ALTLOC_DECLARATION_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_altloc_declaration_projection/1.0.0"
)
MMCIF_ALTLOC_DECLARATION_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_altloc_declaration_source_binding/1.0.0"
)
MMCIF_ALTLOC_DECLARATION_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_altloc_declaration_document/1.0.0"
)
MMCIF_ALTLOC_DECLARATION_PROFILE_ID = (
    "bounded_mmcif_polymer_atom_site_altloc_declarations/1.0.0"
)
MMCIF_ALTLOC_DECLARATION_PARSER_VERSION = "1.0.0"
MAX_MMCIF_ALTLOC_DECLARATION_ROWS = 100_000
MAX_MMCIF_ALTLOC_DECLARATION_TOKEN_CHARS = 256
MAX_MMCIF_ALTLOC_DECLARATION_INTEGER = (1 << 53) - 1

ATOM_SITE_CATEGORY = "_atom_site"
MMCIF_ALTLOC_REQUIRED_HEADERS = (
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
    "_atom_site.pdbx_pdb_model_num",
)

_POSITIVE_INTEGER_RE = re.compile(r"^[1-9][0-9]*$")
_BARE_IDENTITY_RE = re.compile(r"^[!-~]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SEMANTIC_CATEGORIES = frozenset(
    {"_entry", "_entity", "_struct_asym", "_entity_poly", "_entity_poly_seq"}
)
_SUPPORTED_CATEGORIES = _SEMANTIC_CATEGORIES | {ATOM_SITE_CATEGORY}


class MmcifAltlocDeclarationError(ValueError):
    """Stable fail-closed error that does not echo source identities."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"mmcif_altloc_declaration:{self.code}{suffix}: {self.detail}")


@dataclass(frozen=True, slots=True)
class MmcifAltlocAtomDeclaration:
    source_atom_id: int
    model_number: int
    entity_id: str
    label_asym_id: str
    label_comp_id: str
    label_seq_id: int
    label_atom_id: str
    type_symbol: str
    label_alt_id: MmcifSemanticValue
    insertion_code: MmcifSemanticValue
    site_identity_sha256: str
    source_ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_atom_id": self.source_atom_id,
            "model_number": self.model_number,
            "entity_id": self.entity_id,
            "label_asym_id": self.label_asym_id,
            "label_comp_id": self.label_comp_id,
            "label_seq_id": self.label_seq_id,
            "label_atom_id": self.label_atom_id,
            "type_symbol": self.type_symbol,
            "label_alt_id": _marker_projection(self.label_alt_id),
            "insertion_code": _marker_projection(self.insertion_code),
            "site_identity_sha256": self.site_identity_sha256,
            "explicit_altloc": self.label_alt_id.state == "known",
            "group_pdb": "ATOM",
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class MmcifAltlocDeclarationSnapshot:
    source_sha256: str
    block_name: str
    semantic_snapshot_sha256: str
    semantic_projection_sha256: str
    semantic_source_binding_sha256: str
    declarations: tuple[MmcifAltlocAtomDeclaration, ...]
    explicit_altloc_ids: tuple[str, ...]
    site_identity_count: int
    source_category_order: tuple[str, ...]
    atom_site_headers: tuple[str, ...]
    atom_site_source_ordinal: int
    atom_site_row_sha256: tuple[str, ...]
    uninterpreted_atom_site_headers: tuple[str, ...]
    uninterpreted_categories: tuple[str, ...]

    @property
    def declaration_projection_sha256(self) -> str:
        return _sha256(mmcif_altloc_declaration_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_altloc_declaration_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_ALTLOC_DECLARATION_DOCUMENT_SCHEMA_ID,
                "declaration_projection_sha256": self.declaration_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_ALTLOC_DECLARATION_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_ALTLOC_DECLARATION_PROFILE_ID,
            "parser_version": MMCIF_ALTLOC_DECLARATION_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "block_name": self.block_name,
            "semantic_snapshot_sha256": self.semantic_snapshot_sha256,
            "declaration_count": len(self.declarations),
            "explicit_altloc_ids": list(self.explicit_altloc_ids),
            "explicit_altloc_id_count": len(self.explicit_altloc_ids),
            "site_identity_count": self.site_identity_count,
            "uninterpreted_categories": list(self.uninterpreted_categories),
            "declaration_projection_sha256": self.declaration_projection_sha256,
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
        "source_altloc_markers_preserved": True,
        "polymer_label_identity_references_verified": True,
        "source_atom_order_preserved": True,
        "conformer_selected": False,
        "coordinate_values_interpreted": False,
        "coordinate_observation_assessed": False,
        "occupancy_values_interpreted": False,
        "occupancy_weighting_applied": False,
        "altloc_population_interpreted": False,
        "missingness_inferred": False,
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


def _marker(token: CifToken, *, field: str) -> MmcifSemanticValue:
    if token.multiline or len(token.value) > MAX_MMCIF_ALTLOC_DECLARATION_TOKEN_CHARS:
        raise MmcifAltlocDeclarationError(
            "marker_token_out_of_bounds",
            f"{field} must be a bounded single-line value",
            line_number=token.line_number,
        )
    state = (
        "not_applicable"
        if not token.quoted and token.value == "."
        else "unknown"
        if not token.quoted and token.value == "?"
        else "known"
    )
    try:
        return MmcifSemanticValue(
            state=state,
            value=token.value,
            quoted=bool(token.quoted),
            line_number=int(token.line_number),
            column_number=int(token.column_number),
        )
    except (TypeError, ValueError) as exc:
        raise MmcifAltlocDeclarationError(
            "semantic_value_out_of_bounds",
            f"{field} is outside the bounded semantic value domain",
            line_number=token.line_number,
        ) from exc


def _marker_projection(value: MmcifSemanticValue) -> dict[str, Any]:
    return {"state": value.state, "value": value.value, "quoted": value.quoted}


def _known(token: CifToken, *, field: str) -> str:
    value = _marker(token, field=field)
    if value.state != "known":
        raise MmcifAltlocDeclarationError(
            "required_identity_marker",
            f"{field} must be a known identity value",
            line_number=token.line_number,
        )
    if (
        value.quoted
        or _BARE_IDENTITY_RE.fullmatch(value.value) is None
        or len(value.value) > MAX_MMCIF_ALTLOC_DECLARATION_TOKEN_CHARS
    ):
        raise MmcifAltlocDeclarationError(
            "invalid_identity_token",
            f"{field} must be a bounded bare printable token",
            line_number=token.line_number,
        )
    return value.value


def _positive_integer(token: CifToken, *, field: str) -> int:
    if token.quoted or token.multiline or _POSITIVE_INTEGER_RE.fullmatch(token.value) is None:
        raise MmcifAltlocDeclarationError(
            "invalid_positive_integer",
            f"{field} must be a canonical positive integer",
            line_number=token.line_number,
        )
    value = int(token.value)
    if value > MAX_MMCIF_ALTLOC_DECLARATION_INTEGER:
        raise MmcifAltlocDeclarationError(
            "positive_integer_out_of_bounds",
            f"{field} exceeds the bounded integer domain",
            line_number=token.line_number,
        )
    return value


def _atom_site_loop(block: CifBlock) -> tuple[CifLoop, dict[str, int]]:
    scalar_tags = tuple(
        tag for tag in block.scalar_values if tag.startswith(f"{ATOM_SITE_CATEGORY}.")
    )
    if scalar_tags:
        token = block.scalar_values[scalar_tags[0]]
        raise MmcifAltlocDeclarationError(
            "atom_site_must_be_loop",
            "_atom_site must use one loop in this bounded profile",
            line_number=token.line_number,
        )
    loops = [loop for loop in block.loops if ATOM_SITE_CATEGORY in loop.categories]
    if not loops:
        raise MmcifAltlocDeclarationError(
            "atom_site_missing",
            "one bounded _atom_site loop is required",
        )
    if len(loops) != 1:
        raise MmcifAltlocDeclarationError(
            "multiple_atom_site_loops",
            "_atom_site must occur in exactly one loop",
            line_number=loops[1].line_number,
        )
    loop = loops[0]
    if loop.categories != (ATOM_SITE_CATEGORY,):
        raise MmcifAltlocDeclarationError(
            "mixed_atom_site_loop",
            "cross-category atom_site loops are outside this bounded profile",
            line_number=loop.line_number,
        )
    if not loop.rows:
        raise MmcifAltlocDeclarationError(
            "atom_site_empty",
            "_atom_site must contain at least one source row",
            line_number=loop.line_number,
        )
    if len(loop.rows) > MAX_MMCIF_ALTLOC_DECLARATION_ROWS:
        raise MmcifAltlocDeclarationError(
            "too_many_atom_site_rows",
            "_atom_site exceeds the bounded row count",
            line_number=loop.line_number,
        )
    if any(tag not in loop.tags for tag in MMCIF_ALTLOC_REQUIRED_HEADERS):
        raise MmcifAltlocDeclarationError(
            "required_atom_site_headers_missing",
            "the bounded alternate-location identity header set is incomplete",
            line_number=loop.line_number,
        )
    return loop, {tag: position for position, tag in enumerate(loop.tags)}


def _semantic_maps(
    semantic: MmcifSemanticSnapshot,
) -> tuple[dict[str, str], dict[tuple[str, int], str]]:
    return (
        {row.asym_id: row.entity_id for row in semantic.asym_units},
        {
            (row.entity_id, row.sequence_number): row.monomer_id
            for row in semantic.polymer_sequence
        },
    )


def _site_sha(
    *,
    model_number: int,
    entity_id: str,
    label_asym_id: str,
    label_comp_id: str,
    label_seq_id: int,
    label_atom_id: str,
    insertion_code: MmcifSemanticValue,
) -> str:
    return _sha256(
        {
            "model_number": model_number,
            "entity_id": entity_id,
            "label_asym_id": label_asym_id,
            "label_comp_id": label_comp_id,
            "label_seq_id": label_seq_id,
            "label_atom_id": label_atom_id,
            "insertion_code": _marker_projection(insertion_code),
        }
    )


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


def parse_mmcif_altloc_declarations(text: str) -> MmcifAltlocDeclarationSnapshot:
    """Parse bounded polymer atom-site alternate-location source declarations."""

    if type(text) is not str:
        raise TypeError("mmCIF alternate-location input must be a string")
    semantic = parse_mmcif_semantics(text)
    block = parse_cif_block(text)
    loop, index = _atom_site_loop(block)
    asym_to_entity, sequence = _semantic_maps(semantic)

    rows: list[MmcifAltlocAtomDeclaration] = []
    source_ids: set[int] = set()
    logical_keys: set[tuple[Any, ...]] = set()
    explicit_ids: list[str] = []
    explicit_seen: set[str] = set()
    site_ids: set[str] = set()

    for ordinal, source_row in enumerate(loop.rows):
        source_token = source_row[index["_atom_site.id"]]
        source_atom_id = _positive_integer(source_token, field="_atom_site.id")
        if source_atom_id in source_ids:
            raise MmcifAltlocDeclarationError(
                "duplicate_source_atom_id",
                "_atom_site source identifiers must be unique",
                line_number=source_token.line_number,
            )
        source_ids.add(source_atom_id)

        group_token = source_row[index["_atom_site.group_pdb"]]
        if _known(group_token, field="_atom_site.group_pdb") != "ATOM":
            raise MmcifAltlocDeclarationError(
                "nonpoly_atom_site_row_not_supported",
                "this bounded profile accepts only polymer ATOM rows",
                line_number=group_token.line_number,
            )
        model_number = _positive_integer(
            source_row[index["_atom_site.pdbx_pdb_model_num"]],
            field="_atom_site.pdbx_pdb_model_num",
        )
        asym_token = source_row[index["_atom_site.label_asym_id"]]
        label_asym_id = _known(asym_token, field="_atom_site.label_asym_id")
        label_entity_id = _known(
            source_row[index["_atom_site.label_entity_id"]],
            field="_atom_site.label_entity_id",
        )
        entity_id = asym_to_entity.get(label_asym_id)
        if entity_id is None:
            raise MmcifAltlocDeclarationError(
                "label_asym_reference_missing",
                "one atom row references an unknown label asym identity",
                line_number=asym_token.line_number,
            )
        if label_entity_id != entity_id:
            raise MmcifAltlocDeclarationError(
                "label_entity_reference_mismatch",
                "one atom row label entity does not match the semantic asym carrier",
                line_number=asym_token.line_number,
            )
        label_seq_id = _positive_integer(
            source_row[index["_atom_site.label_seq_id"]],
            field="_atom_site.label_seq_id",
        )
        label_comp_id = _known(
            source_row[index["_atom_site.label_comp_id"]],
            field="_atom_site.label_comp_id",
        )
        expected_comp = sequence.get((entity_id, label_seq_id))
        if expected_comp is None:
            raise MmcifAltlocDeclarationError(
                "label_sequence_reference_missing",
                "one atom row references a sequence position outside the semantic carrier",
                line_number=asym_token.line_number,
            )
        if expected_comp != label_comp_id:
            raise MmcifAltlocDeclarationError(
                "label_component_mismatch",
                "one atom row component does not match the semantic polymer sequence",
                line_number=asym_token.line_number,
            )

        label_atom_id = _known(
            source_row[index["_atom_site.label_atom_id"]],
            field="_atom_site.label_atom_id",
        )
        type_symbol = _known(
            source_row[index["_atom_site.type_symbol"]],
            field="_atom_site.type_symbol",
        )
        label_alt_id = _marker(
            source_row[index["_atom_site.label_alt_id"]],
            field="_atom_site.label_alt_id",
        )
        insertion_code = _marker(
            source_row[index["_atom_site.pdbx_pdb_ins_code"]],
            field="_atom_site.pdbx_pdb_ins_code",
        )
        site_identity_sha256 = _site_sha(
            model_number=model_number,
            entity_id=entity_id,
            label_asym_id=label_asym_id,
            label_comp_id=label_comp_id,
            label_seq_id=label_seq_id,
            label_atom_id=label_atom_id,
            insertion_code=insertion_code,
        )
        logical_key = (
            site_identity_sha256,
            label_alt_id.state,
            label_alt_id.value,
            label_alt_id.quoted,
        )
        if logical_key in logical_keys:
            raise MmcifAltlocDeclarationError(
                "duplicate_altloc_declaration",
                "one model/site/alternate-location declaration occurs more than once",
                line_number=source_token.line_number,
            )
        logical_keys.add(logical_key)
        site_ids.add(site_identity_sha256)
        if label_alt_id.state == "known" and label_alt_id.value not in explicit_seen:
            explicit_seen.add(label_alt_id.value)
            explicit_ids.append(label_alt_id.value)

        rows.append(
            MmcifAltlocAtomDeclaration(
                source_atom_id=source_atom_id,
                model_number=model_number,
                entity_id=entity_id,
                label_asym_id=label_asym_id,
                label_comp_id=label_comp_id,
                label_seq_id=label_seq_id,
                label_atom_id=label_atom_id,
                type_symbol=type_symbol,
                label_alt_id=label_alt_id,
                insertion_code=insertion_code,
                site_identity_sha256=site_identity_sha256,
                source_ordinal=ordinal,
            )
        )

    if not explicit_ids:
        raise MmcifAltlocDeclarationError(
            "explicit_altloc_declaration_missing",
            "at least one explicit label alternate-location identifier is required",
            line_number=loop.line_number,
        )

    required = frozenset(MMCIF_ALTLOC_REQUIRED_HEADERS)
    return MmcifAltlocDeclarationSnapshot(
        source_sha256=hashlib.sha256(text.encode("ascii")).hexdigest(),
        block_name=block.name,
        semantic_snapshot_sha256=semantic.snapshot_sha256,
        semantic_projection_sha256=semantic.semantic_projection_sha256,
        semantic_source_binding_sha256=semantic.source_binding_sha256,
        declarations=tuple(rows),
        explicit_altloc_ids=tuple(explicit_ids),
        site_identity_count=len(site_ids),
        source_category_order=block.category_order,
        atom_site_headers=tuple(loop.tags),
        atom_site_source_ordinal=block.category_order.index(ATOM_SITE_CATEGORY),
        atom_site_row_sha256=tuple(_row_sha(loop, row) for row in loop.rows),
        uninterpreted_atom_site_headers=tuple(
            tag for tag in loop.tags if tag not in required
        ),
        uninterpreted_categories=tuple(
            category
            for category in block.category_order
            if category not in _SUPPORTED_CATEGORIES
        ),
    )


def mmcif_altloc_declaration_projection(
    snapshot: MmcifAltlocDeclarationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ALTLOC_DECLARATION_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_ALTLOC_DECLARATION_PROFILE_ID,
        "parser_version": MMCIF_ALTLOC_DECLARATION_PARSER_VERSION,
        "semantic_projection_sha256": snapshot.semantic_projection_sha256,
        "declarations": [row.to_dict() for row in snapshot.declarations],
        "explicit_altloc_ids": list(snapshot.explicit_altloc_ids),
        "site_identity_count": snapshot.site_identity_count,
        "row_order": "source_atom_site_order",
        **_claim_policy(),
    }


def mmcif_altloc_declaration_source_binding(
    snapshot: MmcifAltlocDeclarationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ALTLOC_DECLARATION_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "block_name": snapshot.block_name,
        "semantic_snapshot_sha256": snapshot.semantic_snapshot_sha256,
        "semantic_source_binding_sha256": snapshot.semantic_source_binding_sha256,
        "source_category_order": list(snapshot.source_category_order),
        "atom_site_binding": {
            "category": ATOM_SITE_CATEGORY,
            "representation": "loop",
            "headers": list(snapshot.atom_site_headers),
            "row_count": len(snapshot.declarations),
            "source_ordinal": snapshot.atom_site_source_ordinal,
            "row_sha256": list(snapshot.atom_site_row_sha256),
            "uninterpreted_headers": list(
                snapshot.uninterpreted_atom_site_headers
            ),
        },
        "uninterpreted_categories": list(snapshot.uninterpreted_categories),
    }


def mmcif_altloc_declaration_document(
    snapshot: MmcifAltlocDeclarationSnapshot,
) -> dict[str, Any]:
    projection = mmcif_altloc_declaration_projection(snapshot)
    binding = mmcif_altloc_declaration_source_binding(snapshot)
    return {
        "schema_id": MMCIF_ALTLOC_DECLARATION_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_ALTLOC_DECLARATION_PROFILE_ID,
        "parser_version": MMCIF_ALTLOC_DECLARATION_PARSER_VERSION,
        "declaration_projection": projection,
        "source_binding": binding,
        "declaration_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def require_mmcif_altloc_declaration_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("altloc declaration document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_ALTLOC_DECLARATION_DOCUMENT_SCHEMA_ID:
        raise ValueError("altloc declaration document schema mismatch")
    if document.get("profile_id") != MMCIF_ALTLOC_DECLARATION_PROFILE_ID:
        raise ValueError("altloc declaration profile mismatch")
    if document.get("parser_version") != MMCIF_ALTLOC_DECLARATION_PARSER_VERSION:
        raise ValueError("altloc declaration parser version mismatch")
    projection = document.get("declaration_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("altloc declaration document sections must be mappings")
    if projection.get("schema_id") != MMCIF_ALTLOC_DECLARATION_PROJECTION_SCHEMA_ID:
        raise ValueError("altloc declaration projection schema mismatch")
    if binding.get("schema_id") != MMCIF_ALTLOC_DECLARATION_SOURCE_BINDING_SCHEMA_ID:
        raise ValueError("altloc declaration source binding schema mismatch")

    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("declaration_projection_sha256") != projection_digest:
        raise ValueError("altloc declaration projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("altloc declaration source binding digest mismatch")
    if document.get("snapshot_sha256") != _sha256(
        {
            "schema_id": MMCIF_ALTLOC_DECLARATION_DOCUMENT_SCHEMA_ID,
            "declaration_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    ):
        raise ValueError("altloc declaration snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("altloc declaration claim policy mismatch")

    rows = projection.get("declarations")
    explicit_ids = projection.get("explicit_altloc_ids")
    if not isinstance(rows, list) or not rows:
        raise ValueError("altloc declaration rows must be a non-empty list")
    if not isinstance(explicit_ids, list) or not explicit_ids:
        raise ValueError("altloc declaration explicit identifiers must be non-empty")
    if document.get("declaration_count") != len(rows):
        raise ValueError("altloc declaration count mismatch")
    if document.get("explicit_altloc_ids") != explicit_ids:
        raise ValueError("altloc declaration identifier binding mismatch")
    if document.get("explicit_altloc_id_count") != len(explicit_ids):
        raise ValueError("altloc declaration identifier count mismatch")

    source_sha = binding.get("source_sha256")
    if _SHA256_RE.fullmatch(str(source_sha or "")) is None:
        raise ValueError("altloc declaration source digest invalid")
    if document.get("source_sha256") != source_sha:
        raise ValueError("altloc declaration source digest binding mismatch")
    for value, label in (
        (projection.get("semantic_projection_sha256"), "semantic projection"),
        (binding.get("semantic_snapshot_sha256"), "semantic snapshot"),
        (binding.get("semantic_source_binding_sha256"), "semantic source binding"),
    ):
        if _SHA256_RE.fullmatch(str(value or "")) is None:
            raise ValueError(f"altloc declaration {label} digest invalid")
    return payload


def mmcif_altloc_declaration_json_bytes(
    snapshot: MmcifAltlocDeclarationSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_altloc_declaration_document(snapshot))


def write_mmcif_altloc_declaration_json(
    path: str | Path,
    snapshot: MmcifAltlocDeclarationSnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_altloc_declaration_json_bytes(snapshot) + b"\n"
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
        directory_fd = os.open(
            destination.parent,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0),
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
    "ATOM_SITE_CATEGORY",
    "MAX_MMCIF_ALTLOC_DECLARATION_INTEGER",
    "MAX_MMCIF_ALTLOC_DECLARATION_ROWS",
    "MAX_MMCIF_ALTLOC_DECLARATION_TOKEN_CHARS",
    "MMCIF_ALTLOC_DECLARATION_DOCUMENT_SCHEMA_ID",
    "MMCIF_ALTLOC_DECLARATION_PARSER_VERSION",
    "MMCIF_ALTLOC_DECLARATION_PROFILE_ID",
    "MMCIF_ALTLOC_DECLARATION_PROJECTION_SCHEMA_ID",
    "MMCIF_ALTLOC_DECLARATION_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_ALTLOC_REQUIRED_HEADERS",
    "MmcifAltlocAtomDeclaration",
    "MmcifAltlocDeclarationError",
    "MmcifAltlocDeclarationSnapshot",
    "mmcif_altloc_declaration_document",
    "mmcif_altloc_declaration_json_bytes",
    "mmcif_altloc_declaration_projection",
    "mmcif_altloc_declaration_source_binding",
    "parse_mmcif_altloc_declarations",
    "require_mmcif_altloc_declaration_document",
    "write_mmcif_altloc_declaration_json",
]
