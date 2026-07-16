"""Bounded source preservation for selected mmCIF ``_struct_conn`` rows.

The contract composes the accepted nonpoly identity and component-declaration
carriers.  It verifies that each selected connection partner resolves to one
source-reported nonpoly instance and one declared component atom, while
preserving the remaining source tokens without assigning scientific meaning.

It deliberately does not interpret connection type, symmetry, bond order,
covalence, coordination, chemistry, coordinates, topology, preparation,
parameterability, physics, or runtime eligibility.
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

from .mmcif_nonpoly_component_declarations import (
    MmcifNonpolyComponentDeclarationSnapshot,
    parse_mmcif_nonpoly_component_declarations,
)
from .mmcif_nonpoly_identity import (
    MmcifNonpolyIdentitySnapshot,
    MmcifNonpolyInstanceIdentity,
    parse_mmcif_nonpoly_identity,
)
from .mmcif_semantics import MmcifSemanticValue
from .mmcif_syntax import CifBlock, CifLoop, CifToken, parse_cif_block


STRUCT_CONN_CATEGORY = "_struct_conn"

MMCIF_STRUCT_CONN_DECLARATION_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_struct_conn_declaration_projection/1.0.0"
)
MMCIF_STRUCT_CONN_DECLARATION_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_struct_conn_declaration_source_binding/1.0.0"
)
MMCIF_STRUCT_CONN_DECLARATION_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_struct_conn_declaration_document/1.0.0"
)
MMCIF_STRUCT_CONN_DECLARATION_PROFILE_ID = (
    "bounded_mmcif_nonpoly_struct_conn_source_declarations/1.0.0"
)
MMCIF_STRUCT_CONN_DECLARATION_PARSER_VERSION = "1.0.0"

MAX_MMCIF_STRUCT_CONN_DECLARATION_ROWS = 120_000
MAX_MMCIF_STRUCT_CONN_DECLARATION_TOKEN_CHARS = 256

MMCIF_STRUCT_CONN_HEADERS = (
    "_struct_conn.id",
    "_struct_conn.conn_type_id",
    "_struct_conn.ptnr1_label_asym_id",
    "_struct_conn.ptnr1_label_comp_id",
    "_struct_conn.ptnr1_label_seq_id",
    "_struct_conn.ptnr1_label_atom_id",
    "_struct_conn.pdbx_ptnr1_label_alt_id",
    "_struct_conn.pdbx_ptnr1_pdb_ins_code",
    "_struct_conn.ptnr1_symmetry",
    "_struct_conn.ptnr2_label_asym_id",
    "_struct_conn.ptnr2_label_comp_id",
    "_struct_conn.ptnr2_label_seq_id",
    "_struct_conn.ptnr2_label_atom_id",
    "_struct_conn.pdbx_ptnr2_label_alt_id",
    "_struct_conn.pdbx_ptnr2_pdb_ins_code",
    "_struct_conn.ptnr1_auth_asym_id",
    "_struct_conn.ptnr1_auth_comp_id",
    "_struct_conn.ptnr1_auth_seq_id",
    "_struct_conn.ptnr2_auth_asym_id",
    "_struct_conn.ptnr2_auth_comp_id",
    "_struct_conn.ptnr2_auth_seq_id",
    "_struct_conn.ptnr2_symmetry",
    "_struct_conn.pdbx_value_order",
)

_INTERPRETED_IDENTITY_HEADERS = (
    "_struct_conn.id",
    "_struct_conn.ptnr1_label_asym_id",
    "_struct_conn.ptnr1_label_comp_id",
    "_struct_conn.ptnr1_label_seq_id",
    "_struct_conn.ptnr1_label_atom_id",
    "_struct_conn.pdbx_ptnr1_label_alt_id",
    "_struct_conn.pdbx_ptnr1_pdb_ins_code",
    "_struct_conn.ptnr2_label_asym_id",
    "_struct_conn.ptnr2_label_comp_id",
    "_struct_conn.ptnr2_label_seq_id",
    "_struct_conn.ptnr2_label_atom_id",
    "_struct_conn.pdbx_ptnr2_label_alt_id",
    "_struct_conn.pdbx_ptnr2_pdb_ins_code",
    "_struct_conn.ptnr1_auth_asym_id",
    "_struct_conn.ptnr1_auth_comp_id",
    "_struct_conn.ptnr1_auth_seq_id",
    "_struct_conn.ptnr2_auth_asym_id",
    "_struct_conn.ptnr2_auth_comp_id",
    "_struct_conn.ptnr2_auth_seq_id",
)
_SUPPORTED_CATEGORIES = frozenset(
    {
        "_entity",
        "_struct_asym",
        "_chem_comp",
        "_chem_comp_atom",
        "_chem_comp_bond",
        "_pdbx_entity_nonpoly",
        "_pdbx_nonpoly_scheme",
        STRUCT_CONN_CATEGORY,
    }
)
_BARE_IDENTITY_RE = re.compile(r"^[!-~]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifStructConnDeclarationError(ValueError):
    """Stable fail-closed error that does not echo source identity values."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"mmcif_struct_conn_declaration:{self.code}{suffix}: {self.detail}")


@dataclass(frozen=True, slots=True, repr=False)
class MmcifStructConnPartnerIdentity:
    label_asym_id: str
    label_comp_id: str
    label_seq_id: MmcifSemanticValue
    label_atom_id: str
    label_alt_id: MmcifSemanticValue
    pdb_ins_code: MmcifSemanticValue
    symmetry: MmcifSemanticValue
    auth_asym_id: str
    auth_comp_id: str
    auth_seq_id: str
    instance_identity_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifStructConnPartnerIdentity("
            f"instance_identity_sha256={self.instance_identity_sha256!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "label_asym_id": self.label_asym_id,
            "label_comp_id": self.label_comp_id,
            "label_seq_id": _semantic_projection(self.label_seq_id),
            "label_atom_id": self.label_atom_id,
            "label_alt_id": _semantic_projection(self.label_alt_id),
            "pdb_ins_code": _semantic_projection(self.pdb_ins_code),
            "symmetry": _semantic_projection(self.symmetry),
            "auth_asym_id": self.auth_asym_id,
            "auth_comp_id": self.auth_comp_id,
            "auth_seq_id": self.auth_seq_id,
            "instance_identity_sha256": self.instance_identity_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifStructConnDeclaration:
    connection_id: str
    connection_type: MmcifSemanticValue
    partner_1: MmcifStructConnPartnerIdentity
    partner_2: MmcifStructConnPartnerIdentity
    value_order: MmcifSemanticValue
    source_ordinal: int

    def __repr__(self) -> str:
        return (
            "MmcifStructConnDeclaration("
            f"source_ordinal={self.source_ordinal})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "connection_type": _semantic_projection(self.connection_type),
            "partner_1": self.partner_1.to_dict(),
            "partner_2": self.partner_2.to_dict(),
            "value_order": _semantic_projection(self.value_order),
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class MmcifStructConnDeclarationCategoryBinding:
    category: str
    headers: tuple[str, ...]
    interpreted_headers: tuple[str, ...]
    uninterpreted_headers: tuple[str, ...]
    row_count: int
    source_ordinal: int
    row_sha256: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "representation": "loop",
            "headers": list(self.headers),
            "interpreted_headers": list(self.interpreted_headers),
            "uninterpreted_headers": list(self.uninterpreted_headers),
            "row_count": self.row_count,
            "source_ordinal": self.source_ordinal,
            "row_sha256": list(self.row_sha256),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifStructConnDeclarationSnapshot:
    source_sha256: str
    block_name: str
    identity_snapshot_sha256: str
    identity_projection_sha256: str
    identity_source_binding_sha256: str
    component_snapshot_sha256: str
    component_projection_sha256: str
    component_source_binding_sha256: str
    declarations: tuple[MmcifStructConnDeclaration, ...]
    source_category_order: tuple[str, ...]
    category_binding: MmcifStructConnDeclarationCategoryBinding
    uninterpreted_categories: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            "MmcifStructConnDeclarationSnapshot("
            f"declaration_count={len(self.declarations)})"
        )

    @property
    def declaration_projection_sha256(self) -> str:
        return _sha256(mmcif_struct_conn_declaration_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_struct_conn_declaration_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_STRUCT_CONN_DECLARATION_DOCUMENT_SCHEMA_ID,
                "declaration_projection_sha256": self.declaration_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_STRUCT_CONN_DECLARATION_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_STRUCT_CONN_DECLARATION_PROFILE_ID,
            "parser_version": MMCIF_STRUCT_CONN_DECLARATION_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "block_name": self.block_name,
            "identity_snapshot_sha256": self.identity_snapshot_sha256,
            "component_snapshot_sha256": self.component_snapshot_sha256,
            "connection_ids": [row.connection_id for row in self.declarations],
            "declaration_count": len(self.declarations),
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
        "source_struct_conn_declarations_preserved": True,
        "connection_identity_references_verified": True,
        "partner_nonpoly_instance_references_verified": True,
        "partner_component_atom_references_verified": True,
        "source_row_order_preserved": True,
        "source_category_headers_bound": True,
        "source_authenticated": False,
        "atom_site_identity_joined": False,
        "coordinates_interpreted": False,
        "label_auth_semantic_equivalence_interpreted": False,
        "connection_type_interpreted": False,
        "symmetry_interpreted": False,
        "bond_order_interpreted": False,
        "covalence_interpreted": False,
        "coordination_interpreted": False,
        "bond_topology_interpreted": False,
        "component_chemistry_interpreted": False,
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


def _semantic(token: CifToken, *, field: str) -> MmcifSemanticValue:
    if token.multiline or len(token.value) > MAX_MMCIF_STRUCT_CONN_DECLARATION_TOKEN_CHARS:
        raise MmcifStructConnDeclarationError(
            "source_token_out_of_bounds",
            f"{field} exceeds the bounded source token domain",
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
        raise MmcifStructConnDeclarationError(
            "source_token_out_of_bounds",
            f"{field} exceeds the bounded semantic value domain",
            line_number=token.line_number,
        ) from exc


def _semantic_projection(value: MmcifSemanticValue) -> dict[str, Any]:
    return {"state": value.state, "value": value.value, "quoted": value.quoted}


def _semantic_key(value: MmcifSemanticValue) -> tuple[str, str, bool]:
    return value.state, value.value, value.quoted


def _known_identity(token: CifToken, *, field: str) -> str:
    value = _semantic(token, field=field)
    if value.state != "known":
        raise MmcifStructConnDeclarationError(
            "required_identity_marker",
            f"{field} must be a known source identity",
            line_number=token.line_number,
        )
    if value.quoted or _BARE_IDENTITY_RE.fullmatch(value.value) is None:
        raise MmcifStructConnDeclarationError(
            "invalid_identity_token",
            f"{field} must be a bounded bare printable token",
            line_number=token.line_number,
        )
    return value.value


def _blank_identity_marker(token: CifToken, *, field: str) -> MmcifSemanticValue:
    value = _semantic(token, field=field)
    if value.state == "known":
        raise MmcifStructConnDeclarationError(
            "nonblank_partner_marker_not_supported",
            f"{field} must be an explicit dot or question marker in this profile",
            line_number=token.line_number,
        )
    return value


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


def _category_loop(block: CifBlock) -> tuple[CifLoop, dict[str, int]]:
    scalar = tuple(
        tag
        for tag in block.scalar_values
        if tag.startswith(f"{STRUCT_CONN_CATEGORY}.")
    )
    if scalar:
        token = block.scalar_values[scalar[0]]
        raise MmcifStructConnDeclarationError(
            "category_must_be_loop",
            "_struct_conn must use one category-local loop",
            line_number=token.line_number,
        )
    loops = [loop for loop in block.loops if STRUCT_CONN_CATEGORY in loop.categories]
    if not loops:
        raise MmcifStructConnDeclarationError(
            "required_category_missing",
            "_struct_conn is required by this bounded declaration profile",
        )
    if len(loops) != 1:
        raise MmcifStructConnDeclarationError(
            "multiple_category_loops",
            "_struct_conn must occur in exactly one loop",
            line_number=loops[1].line_number,
        )
    loop = loops[0]
    if loop.categories != (STRUCT_CONN_CATEGORY,):
        raise MmcifStructConnDeclarationError(
            "mixed_category_loop",
            "cross-category declaration loops are outside this bounded profile",
            line_number=loop.line_number,
        )
    if not loop.rows:
        raise MmcifStructConnDeclarationError(
            "category_empty",
            "_struct_conn must contain at least one source row",
            line_number=loop.line_number,
        )
    if len(loop.rows) > MAX_MMCIF_STRUCT_CONN_DECLARATION_ROWS:
        raise MmcifStructConnDeclarationError(
            "too_many_declaration_rows",
            "_struct_conn exceeds the bounded row count",
            line_number=loop.line_number,
        )
    if len(loop.tags) != len(MMCIF_STRUCT_CONN_HEADERS) or set(loop.tags) != set(
        MMCIF_STRUCT_CONN_HEADERS
    ):
        raise MmcifStructConnDeclarationError(
            "unsupported_headers",
            "_struct_conn must use the exact bounded source header set",
            line_number=loop.line_number,
        )
    for row in loop.rows:
        for token in row:
            if token.multiline or len(token.value) > MAX_MMCIF_STRUCT_CONN_DECLARATION_TOKEN_CHARS:
                raise MmcifStructConnDeclarationError(
                    "source_token_out_of_bounds",
                    "_struct_conn contains a source token outside the bounded domain",
                    line_number=token.line_number,
                )
    return loop, {tag: position for position, tag in enumerate(loop.tags)}


def _join_partner_instance(
    *,
    instances: tuple[MmcifNonpolyInstanceIdentity, ...],
    label_asym_id: str,
    label_comp_id: str,
    auth_asym_id: str,
    auth_comp_id: str,
    auth_seq_id: str,
    pdb_ins_code: MmcifSemanticValue,
    line_number: int,
) -> MmcifNonpolyInstanceIdentity:
    matches = tuple(
        row
        for row in instances
        if row.asym_id == label_asym_id
        and row.mon_id == label_comp_id
        and row.pdb_strand_id == auth_asym_id
        and row.auth_mon_id == auth_comp_id
        and row.auth_seq_num == auth_seq_id
        and _semantic_key(row.pdb_ins_code) == _semantic_key(pdb_ins_code)
    )
    if len(matches) != 1:
        raise MmcifStructConnDeclarationError(
            "partner_instance_identity_join_failed",
            "each connection partner must resolve to exactly one nonpoly source instance",
            line_number=line_number,
        )
    return matches[0]


def _parse_partner(
    row: tuple[CifToken, ...],
    index: Mapping[str, int],
    *,
    partner: int,
    identity: MmcifNonpolyIdentitySnapshot,
    component_atoms: frozenset[tuple[str, str]],
) -> MmcifStructConnPartnerIdentity:
    prefix = f"_struct_conn.ptnr{partner}"
    alt_field = f"_struct_conn.pdbx_ptnr{partner}_label_alt_id"
    ins_field = f"_struct_conn.pdbx_ptnr{partner}_pdb_ins_code"
    label_asym_token = row[index[f"{prefix}_label_asym_id"]]
    label_asym_id = _known_identity(label_asym_token, field=f"{prefix}_label_asym_id")
    label_comp_id = _known_identity(
        row[index[f"{prefix}_label_comp_id"]],
        field=f"{prefix}_label_comp_id",
    )
    label_seq_id = _blank_identity_marker(
        row[index[f"{prefix}_label_seq_id"]],
        field=f"{prefix}_label_seq_id",
    )
    label_atom_id = _known_identity(
        row[index[f"{prefix}_label_atom_id"]],
        field=f"{prefix}_label_atom_id",
    )
    label_alt_id = _blank_identity_marker(row[index[alt_field]], field=alt_field)
    pdb_ins_code = _semantic(row[index[ins_field]], field=ins_field)
    symmetry = _semantic(
        row[index[f"{prefix}_symmetry"]],
        field=f"{prefix}_symmetry",
    )
    auth_asym_id = _known_identity(
        row[index[f"{prefix}_auth_asym_id"]],
        field=f"{prefix}_auth_asym_id",
    )
    auth_comp_id = _known_identity(
        row[index[f"{prefix}_auth_comp_id"]],
        field=f"{prefix}_auth_comp_id",
    )
    auth_seq_id = _known_identity(
        row[index[f"{prefix}_auth_seq_id"]],
        field=f"{prefix}_auth_seq_id",
    )

    if (label_comp_id, label_atom_id) not in component_atoms:
        raise MmcifStructConnDeclarationError(
            "partner_component_atom_identity_missing",
            "each connection partner must reference one declared component atom",
            line_number=label_asym_token.line_number,
        )
    instance = _join_partner_instance(
        instances=identity.instances,
        label_asym_id=label_asym_id,
        label_comp_id=label_comp_id,
        auth_asym_id=auth_asym_id,
        auth_comp_id=auth_comp_id,
        auth_seq_id=auth_seq_id,
        pdb_ins_code=pdb_ins_code,
        line_number=label_asym_token.line_number,
    )
    return MmcifStructConnPartnerIdentity(
        label_asym_id=label_asym_id,
        label_comp_id=label_comp_id,
        label_seq_id=label_seq_id,
        label_atom_id=label_atom_id,
        label_alt_id=label_alt_id,
        pdb_ins_code=pdb_ins_code,
        symmetry=symmetry,
        auth_asym_id=auth_asym_id,
        auth_comp_id=auth_comp_id,
        auth_seq_id=auth_seq_id,
        instance_identity_sha256=instance.instance_identity_sha256,
    )


def _parse_declarations(
    parsed: tuple[CifLoop, dict[str, int]],
    *,
    identity: MmcifNonpolyIdentitySnapshot,
    components: MmcifNonpolyComponentDeclarationSnapshot,
) -> tuple[MmcifStructConnDeclaration, ...]:
    loop, index = parsed
    component_atoms = frozenset(
        (row.comp_id, row.atom_id) for row in components.atom_declarations
    )
    declarations: list[MmcifStructConnDeclaration] = []
    seen_ids: set[str] = set()
    for source_ordinal, row in enumerate(loop.rows):
        id_token = row[index["_struct_conn.id"]]
        connection_id = _known_identity(id_token, field="_struct_conn.id")
        if connection_id in seen_ids:
            raise MmcifStructConnDeclarationError(
                "duplicate_connection_id",
                "connection source identities must be unique",
                line_number=id_token.line_number,
            )
        seen_ids.add(connection_id)
        declarations.append(
            MmcifStructConnDeclaration(
                connection_id=connection_id,
                connection_type=_semantic(
                    row[index["_struct_conn.conn_type_id"]],
                    field="_struct_conn.conn_type_id",
                ),
                partner_1=_parse_partner(
                    row,
                    index,
                    partner=1,
                    identity=identity,
                    component_atoms=component_atoms,
                ),
                partner_2=_parse_partner(
                    row,
                    index,
                    partner=2,
                    identity=identity,
                    component_atoms=component_atoms,
                ),
                value_order=_semantic(
                    row[index["_struct_conn.pdbx_value_order"]],
                    field="_struct_conn.pdbx_value_order",
                ),
                source_ordinal=source_ordinal,
            )
        )
    return tuple(declarations)


def parse_mmcif_struct_conn_declarations(
    text: str,
) -> MmcifStructConnDeclarationSnapshot:
    """Parse bounded nonpoly ``_struct_conn`` identity declarations."""

    if type(text) is not str:
        raise TypeError("mmCIF struct_conn declaration input must be a string")
    identity = parse_mmcif_nonpoly_identity(text)
    components = parse_mmcif_nonpoly_component_declarations(text)
    block = parse_cif_block(text)
    parsed = _category_loop(block)
    loop, _index = parsed
    declarations = _parse_declarations(
        parsed,
        identity=identity,
        components=components,
    )
    interpreted = frozenset(_INTERPRETED_IDENTITY_HEADERS)
    binding = MmcifStructConnDeclarationCategoryBinding(
        category=STRUCT_CONN_CATEGORY,
        headers=tuple(loop.tags),
        interpreted_headers=tuple(tag for tag in loop.tags if tag in interpreted),
        uninterpreted_headers=tuple(tag for tag in loop.tags if tag not in interpreted),
        row_count=len(loop.rows),
        source_ordinal=block.category_order.index(STRUCT_CONN_CATEGORY),
        row_sha256=tuple(_row_sha(loop, row) for row in loop.rows),
    )
    return MmcifStructConnDeclarationSnapshot(
        source_sha256=hashlib.sha256(text.encode("ascii")).hexdigest(),
        block_name=block.name,
        identity_snapshot_sha256=identity.snapshot_sha256,
        identity_projection_sha256=identity.identity_projection_sha256,
        identity_source_binding_sha256=identity.source_binding_sha256,
        component_snapshot_sha256=components.snapshot_sha256,
        component_projection_sha256=components.declaration_projection_sha256,
        component_source_binding_sha256=components.source_binding_sha256,
        declarations=declarations,
        source_category_order=block.category_order,
        category_binding=binding,
        uninterpreted_categories=tuple(
            category
            for category in block.category_order
            if category not in _SUPPORTED_CATEGORIES
        ),
    )


def mmcif_struct_conn_declaration_projection(
    snapshot: MmcifStructConnDeclarationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_STRUCT_CONN_DECLARATION_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_STRUCT_CONN_DECLARATION_PROFILE_ID,
        "parser_version": MMCIF_STRUCT_CONN_DECLARATION_PARSER_VERSION,
        "identity_projection_sha256": snapshot.identity_projection_sha256,
        "component_projection_sha256": snapshot.component_projection_sha256,
        "declarations": [row.to_dict() for row in snapshot.declarations],
        "row_order": "source_order",
        **_claim_policy(),
    }


def mmcif_struct_conn_declaration_source_binding(
    snapshot: MmcifStructConnDeclarationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_STRUCT_CONN_DECLARATION_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "block_name": snapshot.block_name,
        "identity_snapshot_sha256": snapshot.identity_snapshot_sha256,
        "identity_source_binding_sha256": snapshot.identity_source_binding_sha256,
        "component_snapshot_sha256": snapshot.component_snapshot_sha256,
        "component_source_binding_sha256": snapshot.component_source_binding_sha256,
        "source_category_order": list(snapshot.source_category_order),
        "category_binding": snapshot.category_binding.to_dict(),
        "uninterpreted_categories": list(snapshot.uninterpreted_categories),
    }


def mmcif_struct_conn_declaration_document(
    snapshot: MmcifStructConnDeclarationSnapshot,
) -> dict[str, Any]:
    projection = mmcif_struct_conn_declaration_projection(snapshot)
    binding = mmcif_struct_conn_declaration_source_binding(snapshot)
    return {
        "schema_id": MMCIF_STRUCT_CONN_DECLARATION_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_STRUCT_CONN_DECLARATION_PROFILE_ID,
        "parser_version": MMCIF_STRUCT_CONN_DECLARATION_PARSER_VERSION,
        "declaration_projection": projection,
        "source_binding": binding,
        "declaration_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def require_mmcif_struct_conn_declaration_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("struct_conn declaration document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_STRUCT_CONN_DECLARATION_DOCUMENT_SCHEMA_ID:
        raise ValueError("struct_conn declaration document schema mismatch")
    if document.get("profile_id") != MMCIF_STRUCT_CONN_DECLARATION_PROFILE_ID:
        raise ValueError("struct_conn declaration profile mismatch")
    if document.get("parser_version") != MMCIF_STRUCT_CONN_DECLARATION_PARSER_VERSION:
        raise ValueError("struct_conn declaration parser version mismatch")
    projection = document.get("declaration_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("struct_conn declaration sections must be mappings")
    if projection.get("schema_id") != MMCIF_STRUCT_CONN_DECLARATION_PROJECTION_SCHEMA_ID:
        raise ValueError("struct_conn declaration projection schema mismatch")
    if binding.get("schema_id") != MMCIF_STRUCT_CONN_DECLARATION_SOURCE_BINDING_SCHEMA_ID:
        raise ValueError("struct_conn declaration source binding schema mismatch")

    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("declaration_projection_sha256") != projection_digest:
        raise ValueError("struct_conn declaration projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("struct_conn declaration source binding digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_STRUCT_CONN_DECLARATION_DOCUMENT_SCHEMA_ID,
            "declaration_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("struct_conn declaration snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("struct_conn declaration claim policy mismatch")

    rows = projection.get("declarations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("struct_conn declarations must be a non-empty list")
    connection_ids = [
        row.get("connection_id") if isinstance(row, Mapping) else None for row in rows
    ]
    if any(not isinstance(value, str) or not value for value in connection_ids):
        raise ValueError("struct_conn declaration connection IDs invalid")
    if len(set(connection_ids)) != len(connection_ids):
        raise ValueError("struct_conn declaration connection IDs not unique")
    if document.get("connection_ids") != connection_ids:
        raise ValueError("struct_conn declaration connection ID binding mismatch")
    if document.get("declaration_count") != len(rows):
        raise ValueError("struct_conn declaration count mismatch")

    source_sha = binding.get("source_sha256")
    if _SHA256_RE.fullmatch(str(source_sha or "")) is None:
        raise ValueError("struct_conn declaration source digest invalid")
    if document.get("source_sha256") != source_sha:
        raise ValueError("struct_conn declaration source digest mismatch")
    for value, label in (
        (projection.get("identity_projection_sha256"), "identity projection"),
        (projection.get("component_projection_sha256"), "component projection"),
        (binding.get("identity_snapshot_sha256"), "identity snapshot"),
        (binding.get("identity_source_binding_sha256"), "identity source binding"),
        (binding.get("component_snapshot_sha256"), "component snapshot"),
        (binding.get("component_source_binding_sha256"), "component source binding"),
    ):
        if _SHA256_RE.fullmatch(str(value or "")) is None:
            raise ValueError(f"struct_conn declaration {label} digest invalid")
    return payload


def mmcif_struct_conn_declaration_json_bytes(
    snapshot: MmcifStructConnDeclarationSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_struct_conn_declaration_document(snapshot))


def write_mmcif_struct_conn_declaration_json(
    path: str | Path,
    snapshot: MmcifStructConnDeclarationSnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_struct_conn_declaration_json_bytes(snapshot) + b"\n"
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
    "MAX_MMCIF_STRUCT_CONN_DECLARATION_ROWS",
    "MAX_MMCIF_STRUCT_CONN_DECLARATION_TOKEN_CHARS",
    "MMCIF_STRUCT_CONN_DECLARATION_DOCUMENT_SCHEMA_ID",
    "MMCIF_STRUCT_CONN_DECLARATION_PARSER_VERSION",
    "MMCIF_STRUCT_CONN_DECLARATION_PROFILE_ID",
    "MMCIF_STRUCT_CONN_DECLARATION_PROJECTION_SCHEMA_ID",
    "MMCIF_STRUCT_CONN_DECLARATION_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_STRUCT_CONN_HEADERS",
    "MmcifStructConnDeclaration",
    "MmcifStructConnDeclarationCategoryBinding",
    "MmcifStructConnDeclarationError",
    "MmcifStructConnDeclarationSnapshot",
    "MmcifStructConnPartnerIdentity",
    "STRUCT_CONN_CATEGORY",
    "mmcif_struct_conn_declaration_document",
    "mmcif_struct_conn_declaration_json_bytes",
    "mmcif_struct_conn_declaration_projection",
    "mmcif_struct_conn_declaration_source_binding",
    "parse_mmcif_struct_conn_declarations",
    "require_mmcif_struct_conn_declaration_document",
    "write_mmcif_struct_conn_declaration_json",
]
