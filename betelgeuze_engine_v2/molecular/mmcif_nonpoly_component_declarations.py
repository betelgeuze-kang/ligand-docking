"""Bounded source preservation for mmCIF nonpoly component declarations.

This module composes the accepted nonpoly identity carrier with selected
``_chem_comp_atom`` and optional ``_chem_comp_bond`` loops. It preserves source
tokens and verifies only component, atom-identity, ordinal, and bond-endpoint
relationships.

It deliberately does not interpret elements, charges, aromaticity, stereo,
bond order, chemistry, coordinates, molecular roles, topology readiness,
preparation, parameterability, physics, or runtime eligibility.
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

from .mmcif_nonpoly_identity import (
    MmcifNonpolyIdentitySnapshot,
    parse_mmcif_nonpoly_identity,
)
from .mmcif_semantics import MmcifSemanticValue
from .mmcif_syntax import CifBlock, CifLoop, CifToken, parse_cif_block


CHEM_COMP_ATOM_CATEGORY = "_chem_comp_atom"
CHEM_COMP_BOND_CATEGORY = "_chem_comp_bond"

MMCIF_NONPOLY_COMPONENT_DECLARATION_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_component_declaration_projection/1.0.0"
)
MMCIF_NONPOLY_COMPONENT_DECLARATION_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_component_declaration_source_binding/1.0.0"
)
MMCIF_NONPOLY_COMPONENT_DECLARATION_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_component_declaration_document/1.0.0"
)
MMCIF_NONPOLY_COMPONENT_DECLARATION_PROFILE_ID = (
    "bounded_mmcif_nonpoly_component_source_declarations/1.0.0"
)
MMCIF_NONPOLY_COMPONENT_DECLARATION_PARSER_VERSION = "1.0.0"

MAX_MMCIF_NONPOLY_COMPONENT_DECLARATION_ROWS = 120_000
MAX_MMCIF_NONPOLY_COMPONENT_DECLARATION_TOKEN_CHARS = 256
MAX_MMCIF_NONPOLY_COMPONENT_DECLARATION_INTEGER = (1 << 53) - 1

MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS = (
    "_chem_comp_atom.comp_id",
    "_chem_comp_atom.atom_id",
    "_chem_comp_atom.type_symbol",
    "_chem_comp_atom.charge",
    "_chem_comp_atom.pdbx_aromatic_flag",
    "_chem_comp_atom.pdbx_stereo_config",
    "_chem_comp_atom.pdbx_ordinal",
)
MMCIF_NONPOLY_COMPONENT_BOND_HEADERS = (
    "_chem_comp_bond.comp_id",
    "_chem_comp_bond.atom_id_1",
    "_chem_comp_bond.atom_id_2",
    "_chem_comp_bond.value_order",
    "_chem_comp_bond.pdbx_aromatic_flag",
    "_chem_comp_bond.pdbx_stereo_config",
    "_chem_comp_bond.pdbx_ordinal",
)

_ATOM_IDENTITY_HEADERS = (
    "_chem_comp_atom.comp_id",
    "_chem_comp_atom.atom_id",
    "_chem_comp_atom.pdbx_ordinal",
)
_BOND_IDENTITY_HEADERS = (
    "_chem_comp_bond.comp_id",
    "_chem_comp_bond.atom_id_1",
    "_chem_comp_bond.atom_id_2",
    "_chem_comp_bond.pdbx_ordinal",
)
_IDENTITY_CATEGORIES = frozenset(
    {
        "_entity",
        "_struct_asym",
        "_chem_comp",
        "_pdbx_entity_nonpoly",
        "_pdbx_nonpoly_scheme",
    }
)
_SUPPORTED_CATEGORIES = _IDENTITY_CATEGORIES | {
    CHEM_COMP_ATOM_CATEGORY,
    CHEM_COMP_BOND_CATEGORY,
}
_POSITIVE_INTEGER_RE = re.compile(r"^[1-9][0-9]*$")
_BARE_IDENTITY_RE = re.compile(r"^[!-~]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyComponentDeclarationError(ValueError):
    """Stable fail-closed error that does not echo source identity values."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            f"mmcif_nonpoly_component_declaration:{self.code}{suffix}: {self.detail}"
        )


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyComponentAtomDeclaration:
    comp_id: str
    atom_id: str
    type_symbol: MmcifSemanticValue
    charge: MmcifSemanticValue
    aromatic_flag: MmcifSemanticValue
    stereo_config: MmcifSemanticValue
    ordinal: int
    source_ordinal: int

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyComponentAtomDeclaration("
            f"ordinal={self.ordinal}, source_ordinal={self.source_ordinal})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "comp_id": self.comp_id,
            "atom_id": self.atom_id,
            "type_symbol": _semantic_projection(self.type_symbol),
            "charge": _semantic_projection(self.charge),
            "aromatic_flag": _semantic_projection(self.aromatic_flag),
            "stereo_config": _semantic_projection(self.stereo_config),
            "ordinal": self.ordinal,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyComponentBondDeclaration:
    comp_id: str
    atom_id_1: str
    atom_id_2: str
    value_order: MmcifSemanticValue
    aromatic_flag: MmcifSemanticValue
    stereo_config: MmcifSemanticValue
    ordinal: int
    source_ordinal: int

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyComponentBondDeclaration("
            f"ordinal={self.ordinal}, source_ordinal={self.source_ordinal})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "comp_id": self.comp_id,
            "atom_id_1": self.atom_id_1,
            "atom_id_2": self.atom_id_2,
            "value_order": _semantic_projection(self.value_order),
            "aromatic_flag": _semantic_projection(self.aromatic_flag),
            "stereo_config": _semantic_projection(self.stereo_config),
            "ordinal": self.ordinal,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class MmcifNonpolyComponentDeclarationCategoryBinding:
    category: str
    headers: tuple[str, ...]
    interpreted_headers: tuple[str, ...]
    uninterpreted_headers: tuple[str, ...]
    row_count: int
    selected_row_count: int
    source_ordinal: int
    row_sha256: tuple[str, ...]
    selected_row_sha256: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "representation": "loop",
            "headers": list(self.headers),
            "interpreted_headers": list(self.interpreted_headers),
            "uninterpreted_headers": list(self.uninterpreted_headers),
            "row_count": self.row_count,
            "selected_row_count": self.selected_row_count,
            "source_ordinal": self.source_ordinal,
            "row_sha256": list(self.row_sha256),
            "selected_row_sha256": list(self.selected_row_sha256),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyComponentDeclarationSnapshot:
    source_sha256: str
    block_name: str
    identity_snapshot_sha256: str
    identity_projection_sha256: str
    identity_source_binding_sha256: str
    component_ids: tuple[str, ...]
    atom_declarations: tuple[MmcifNonpolyComponentAtomDeclaration, ...]
    bond_declarations: tuple[MmcifNonpolyComponentBondDeclaration, ...]
    bond_category_present: bool
    source_category_order: tuple[str, ...]
    category_bindings: tuple[MmcifNonpolyComponentDeclarationCategoryBinding, ...]
    uninterpreted_categories: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyComponentDeclarationSnapshot("
            f"component_count={len(self.component_ids)}, "
            f"atom_count={len(self.atom_declarations)}, "
            f"bond_count={len(self.bond_declarations)})"
        )

    @property
    def declaration_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_component_declaration_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_component_declaration_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_COMPONENT_DECLARATION_DOCUMENT_SCHEMA_ID,
                "declaration_projection_sha256": self.declaration_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        atom_counts = {
            comp_id: sum(1 for row in self.atom_declarations if row.comp_id == comp_id)
            for comp_id in self.component_ids
        }
        bond_counts = {
            comp_id: sum(1 for row in self.bond_declarations if row.comp_id == comp_id)
            for comp_id in self.component_ids
        }
        return {
            "schema_id": MMCIF_NONPOLY_COMPONENT_DECLARATION_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_COMPONENT_DECLARATION_PROFILE_ID,
            "parser_version": MMCIF_NONPOLY_COMPONENT_DECLARATION_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "block_name": self.block_name,
            "identity_snapshot_sha256": self.identity_snapshot_sha256,
            "component_ids": list(self.component_ids),
            "component_count": len(self.component_ids),
            "atom_declaration_count": len(self.atom_declarations),
            "bond_declaration_count": len(self.bond_declarations),
            "bond_category_present": self.bond_category_present,
            "component_atom_counts": atom_counts,
            "component_bond_counts": bond_counts,
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
        "source_component_atom_declarations_preserved": True,
        "source_component_bond_declarations_preserved": True,
        "component_identity_references_verified": True,
        "bond_endpoint_identity_references_verified": True,
        "source_row_order_preserved": True,
        "source_category_headers_bound": True,
        "source_authenticated": False,
        "atom_site_identity_joined": False,
        "coordinates_interpreted": False,
        "type_symbol_interpreted": False,
        "atom_charge_interpreted": False,
        "aromaticity_interpreted": False,
        "stereo_interpreted": False,
        "bond_order_interpreted": False,
        "bond_topology_interpreted": False,
        "component_chemistry_interpreted": False,
        "role_assignment_interpreted": False,
        "coordination_interpreted": False,
        "charge_interpreted": False,
        "protonation_interpreted": False,
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
    if token.multiline or len(token.value) > MAX_MMCIF_NONPOLY_COMPONENT_DECLARATION_TOKEN_CHARS:
        raise MmcifNonpolyComponentDeclarationError(
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
        raise MmcifNonpolyComponentDeclarationError(
            "source_token_out_of_bounds",
            f"{field} exceeds the bounded semantic value domain",
            line_number=token.line_number,
        ) from exc


def _semantic_projection(value: MmcifSemanticValue) -> dict[str, Any]:
    return {"state": value.state, "value": value.value, "quoted": value.quoted}


def _known_identity(token: CifToken, *, field: str) -> str:
    value = _semantic(token, field=field)
    if value.state != "known":
        raise MmcifNonpolyComponentDeclarationError(
            "required_identity_marker",
            f"{field} must be a known source identity",
            line_number=token.line_number,
        )
    if value.quoted or _BARE_IDENTITY_RE.fullmatch(value.value) is None:
        raise MmcifNonpolyComponentDeclarationError(
            "invalid_identity_token",
            f"{field} must be a bounded bare printable token",
            line_number=token.line_number,
        )
    return value.value


def _positive_integer(token: CifToken, *, field: str) -> int:
    if token.quoted or token.multiline or _POSITIVE_INTEGER_RE.fullmatch(token.value) is None:
        raise MmcifNonpolyComponentDeclarationError(
            "invalid_positive_integer",
            f"{field} must be a canonical positive integer",
            line_number=token.line_number,
        )
    value = int(token.value)
    if value > MAX_MMCIF_NONPOLY_COMPONENT_DECLARATION_INTEGER:
        raise MmcifNonpolyComponentDeclarationError(
            "positive_integer_out_of_bounds",
            f"{field} exceeds the bounded integer domain",
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


def _category_loop(
    block: CifBlock,
    *,
    category: str,
    headers: tuple[str, ...],
    interpreted_headers: tuple[str, ...],
    required: bool,
) -> tuple[CifLoop, dict[str, int]] | None:
    scalar = tuple(
        tag for tag in block.scalar_values if tag.startswith(f"{category}.")
    )
    if scalar:
        token = block.scalar_values[scalar[0]]
        raise MmcifNonpolyComponentDeclarationError(
            "category_must_be_loop",
            f"{category} must use one category-local loop",
            line_number=token.line_number,
        )
    loops = [loop for loop in block.loops if category in loop.categories]
    if not loops:
        if required:
            raise MmcifNonpolyComponentDeclarationError(
                "required_category_missing",
                f"{category} is required by this bounded declaration profile",
            )
        return None
    if len(loops) != 1:
        raise MmcifNonpolyComponentDeclarationError(
            "multiple_category_loops",
            f"{category} must occur in exactly one loop",
            line_number=loops[1].line_number,
        )
    loop = loops[0]
    if loop.categories != (category,):
        raise MmcifNonpolyComponentDeclarationError(
            "mixed_category_loop",
            "cross-category declaration loops are outside this bounded profile",
            line_number=loop.line_number,
        )
    if not loop.rows:
        raise MmcifNonpolyComponentDeclarationError(
            "category_empty",
            f"{category} must contain at least one source row",
            line_number=loop.line_number,
        )
    if len(loop.rows) > MAX_MMCIF_NONPOLY_COMPONENT_DECLARATION_ROWS:
        raise MmcifNonpolyComponentDeclarationError(
            "too_many_declaration_rows",
            f"{category} exceeds the bounded row count",
            line_number=loop.line_number,
        )
    if len(loop.tags) != len(headers) or set(loop.tags) != set(headers):
        raise MmcifNonpolyComponentDeclarationError(
            "unsupported_headers",
            f"{category} must use the exact bounded source header set",
            line_number=loop.line_number,
        )
    for row in loop.rows:
        for token in row:
            if (
                token.multiline
                or len(token.value)
                > MAX_MMCIF_NONPOLY_COMPONENT_DECLARATION_TOKEN_CHARS
            ):
                raise MmcifNonpolyComponentDeclarationError(
                    "source_token_out_of_bounds",
                    f"{category} contains a source token outside the bounded domain",
                    line_number=token.line_number,
                )
    return loop, {tag: position for position, tag in enumerate(loop.tags)}


def _parse_atoms(
    parsed: tuple[CifLoop, dict[str, int]],
    *,
    selected_components: tuple[str, ...],
) -> tuple[
    tuple[MmcifNonpolyComponentAtomDeclaration, ...],
    tuple[str, ...],
]:
    loop, index = parsed
    selected = set(selected_components)
    rows: list[MmcifNonpolyComponentAtomDeclaration] = []
    selected_hashes: list[str] = []
    seen_atoms: set[tuple[str, str]] = set()
    seen_ordinals: set[tuple[str, int]] = set()
    covered: set[str] = set()

    for source_ordinal, row in enumerate(loop.rows):
        comp_id = _known_identity(
            row[index["_chem_comp_atom.comp_id"]],
            field="_chem_comp_atom.comp_id",
        )
        if comp_id not in selected:
            continue
        atom_token = row[index["_chem_comp_atom.atom_id"]]
        atom_id = _known_identity(atom_token, field="_chem_comp_atom.atom_id")
        ordinal = _positive_integer(
            row[index["_chem_comp_atom.pdbx_ordinal"]],
            field="_chem_comp_atom.pdbx_ordinal",
        )
        atom_key = (comp_id, atom_id)
        ordinal_key = (comp_id, ordinal)
        if atom_key in seen_atoms:
            raise MmcifNonpolyComponentDeclarationError(
                "duplicate_component_atom_id",
                "selected component atom identities must be unique",
                line_number=atom_token.line_number,
            )
        if ordinal_key in seen_ordinals:
            raise MmcifNonpolyComponentDeclarationError(
                "duplicate_component_atom_ordinal",
                "selected component atom ordinals must be unique",
                line_number=atom_token.line_number,
            )
        seen_atoms.add(atom_key)
        seen_ordinals.add(ordinal_key)
        covered.add(comp_id)
        rows.append(
            MmcifNonpolyComponentAtomDeclaration(
                comp_id=comp_id,
                atom_id=atom_id,
                type_symbol=_semantic(
                    row[index["_chem_comp_atom.type_symbol"]],
                    field="_chem_comp_atom.type_symbol",
                ),
                charge=_semantic(
                    row[index["_chem_comp_atom.charge"]],
                    field="_chem_comp_atom.charge",
                ),
                aromatic_flag=_semantic(
                    row[index["_chem_comp_atom.pdbx_aromatic_flag"]],
                    field="_chem_comp_atom.pdbx_aromatic_flag",
                ),
                stereo_config=_semantic(
                    row[index["_chem_comp_atom.pdbx_stereo_config"]],
                    field="_chem_comp_atom.pdbx_stereo_config",
                ),
                ordinal=ordinal,
                source_ordinal=source_ordinal,
            )
        )
        selected_hashes.append(_row_sha(loop, row))

    if covered != selected:
        raise MmcifNonpolyComponentDeclarationError(
            "component_atom_coverage_mismatch",
            "selected components must each have at least one atom declaration",
        )
    return tuple(rows), tuple(selected_hashes)


def _parse_bonds(
    parsed: tuple[CifLoop, dict[str, int]] | None,
    *,
    selected_components: tuple[str, ...],
    atom_declarations: tuple[MmcifNonpolyComponentAtomDeclaration, ...],
) -> tuple[
    tuple[MmcifNonpolyComponentBondDeclaration, ...],
    tuple[str, ...],
]:
    if parsed is None:
        return (), ()
    loop, index = parsed
    selected = set(selected_components)
    atom_ids = {(row.comp_id, row.atom_id) for row in atom_declarations}
    rows: list[MmcifNonpolyComponentBondDeclaration] = []
    selected_hashes: list[str] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    seen_ordinals: set[tuple[str, int]] = set()

    for source_ordinal, row in enumerate(loop.rows):
        comp_id = _known_identity(
            row[index["_chem_comp_bond.comp_id"]],
            field="_chem_comp_bond.comp_id",
        )
        if comp_id not in selected:
            continue
        atom_1_token = row[index["_chem_comp_bond.atom_id_1"]]
        atom_2_token = row[index["_chem_comp_bond.atom_id_2"]]
        atom_id_1 = _known_identity(
            atom_1_token,
            field="_chem_comp_bond.atom_id_1",
        )
        atom_id_2 = _known_identity(
            atom_2_token,
            field="_chem_comp_bond.atom_id_2",
        )
        if atom_id_1 == atom_id_2:
            raise MmcifNonpolyComponentDeclarationError(
                "self_component_bond_declaration",
                "selected bond declarations must reference two distinct atom identities",
                line_number=atom_1_token.line_number,
            )
        if (comp_id, atom_id_1) not in atom_ids or (comp_id, atom_id_2) not in atom_ids:
            raise MmcifNonpolyComponentDeclarationError(
                "bond_endpoint_identity_missing",
                "selected bond endpoints must reference declared atoms in the same component",
                line_number=atom_1_token.line_number,
            )
        ordinal = _positive_integer(
            row[index["_chem_comp_bond.pdbx_ordinal"]],
            field="_chem_comp_bond.pdbx_ordinal",
        )
        pair = (comp_id, *sorted((atom_id_1, atom_id_2)))
        ordinal_key = (comp_id, ordinal)
        if pair in seen_pairs:
            raise MmcifNonpolyComponentDeclarationError(
                "duplicate_component_bond_pair",
                "selected component bond endpoint pairs must be unique",
                line_number=atom_1_token.line_number,
            )
        if ordinal_key in seen_ordinals:
            raise MmcifNonpolyComponentDeclarationError(
                "duplicate_component_bond_ordinal",
                "selected component bond ordinals must be unique",
                line_number=atom_1_token.line_number,
            )
        seen_pairs.add(pair)
        seen_ordinals.add(ordinal_key)
        rows.append(
            MmcifNonpolyComponentBondDeclaration(
                comp_id=comp_id,
                atom_id_1=atom_id_1,
                atom_id_2=atom_id_2,
                value_order=_semantic(
                    row[index["_chem_comp_bond.value_order"]],
                    field="_chem_comp_bond.value_order",
                ),
                aromatic_flag=_semantic(
                    row[index["_chem_comp_bond.pdbx_aromatic_flag"]],
                    field="_chem_comp_bond.pdbx_aromatic_flag",
                ),
                stereo_config=_semantic(
                    row[index["_chem_comp_bond.pdbx_stereo_config"]],
                    field="_chem_comp_bond.pdbx_stereo_config",
                ),
                ordinal=ordinal,
                source_ordinal=source_ordinal,
            )
        )
        selected_hashes.append(_row_sha(loop, row))

    return tuple(rows), tuple(selected_hashes)


def _binding(
    block: CifBlock,
    *,
    parsed: tuple[CifLoop, dict[str, int]],
    interpreted_headers: tuple[str, ...],
    selected_hashes: tuple[str, ...],
) -> MmcifNonpolyComponentDeclarationCategoryBinding:
    loop, _index = parsed
    interpreted = frozenset(interpreted_headers)
    return MmcifNonpolyComponentDeclarationCategoryBinding(
        category=loop.categories[0],
        headers=tuple(loop.tags),
        interpreted_headers=tuple(tag for tag in loop.tags if tag in interpreted),
        uninterpreted_headers=tuple(tag for tag in loop.tags if tag not in interpreted),
        row_count=len(loop.rows),
        selected_row_count=len(selected_hashes),
        source_ordinal=block.category_order.index(loop.categories[0]),
        row_sha256=tuple(_row_sha(loop, row) for row in loop.rows),
        selected_row_sha256=selected_hashes,
    )


def parse_mmcif_nonpoly_component_declarations(
    text: str,
) -> MmcifNonpolyComponentDeclarationSnapshot:
    """Parse bounded nonpoly component atom and bond source declarations."""

    if type(text) is not str:
        raise TypeError("mmCIF nonpoly component declaration input must be a string")
    identity: MmcifNonpolyIdentitySnapshot = parse_mmcif_nonpoly_identity(text)
    block = parse_cif_block(text)
    selected_components = tuple(row.comp_id for row in identity.components)
    atom_parsed = _category_loop(
        block,
        category=CHEM_COMP_ATOM_CATEGORY,
        headers=MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS,
        interpreted_headers=_ATOM_IDENTITY_HEADERS,
        required=True,
    )
    assert atom_parsed is not None
    bond_parsed = _category_loop(
        block,
        category=CHEM_COMP_BOND_CATEGORY,
        headers=MMCIF_NONPOLY_COMPONENT_BOND_HEADERS,
        interpreted_headers=_BOND_IDENTITY_HEADERS,
        required=False,
    )
    atom_rows, atom_hashes = _parse_atoms(
        atom_parsed,
        selected_components=selected_components,
    )
    bond_rows, bond_hashes = _parse_bonds(
        bond_parsed,
        selected_components=selected_components,
        atom_declarations=atom_rows,
    )
    bindings = [
        _binding(
            block,
            parsed=atom_parsed,
            interpreted_headers=_ATOM_IDENTITY_HEADERS,
            selected_hashes=atom_hashes,
        )
    ]
    if bond_parsed is not None:
        bindings.append(
            _binding(
                block,
                parsed=bond_parsed,
                interpreted_headers=_BOND_IDENTITY_HEADERS,
                selected_hashes=bond_hashes,
            )
        )
    return MmcifNonpolyComponentDeclarationSnapshot(
        source_sha256=hashlib.sha256(text.encode("ascii")).hexdigest(),
        block_name=block.name,
        identity_snapshot_sha256=identity.snapshot_sha256,
        identity_projection_sha256=identity.identity_projection_sha256,
        identity_source_binding_sha256=identity.source_binding_sha256,
        component_ids=selected_components,
        atom_declarations=atom_rows,
        bond_declarations=bond_rows,
        bond_category_present=bond_parsed is not None,
        source_category_order=block.category_order,
        category_bindings=tuple(bindings),
        uninterpreted_categories=tuple(
            category
            for category in block.category_order
            if category not in _SUPPORTED_CATEGORIES
        ),
    )


def mmcif_nonpoly_component_declaration_projection(
    snapshot: MmcifNonpolyComponentDeclarationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_COMPONENT_DECLARATION_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_COMPONENT_DECLARATION_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_COMPONENT_DECLARATION_PARSER_VERSION,
        "identity_projection_sha256": snapshot.identity_projection_sha256,
        "component_ids": list(snapshot.component_ids),
        "atom_declarations": [row.to_dict() for row in snapshot.atom_declarations],
        "bond_declarations": [row.to_dict() for row in snapshot.bond_declarations],
        "bond_category_present": snapshot.bond_category_present,
        "row_order": "source_order_within_each_declaration_category",
        **_claim_policy(),
    }


def mmcif_nonpoly_component_declaration_source_binding(
    snapshot: MmcifNonpolyComponentDeclarationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_COMPONENT_DECLARATION_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "block_name": snapshot.block_name,
        "identity_snapshot_sha256": snapshot.identity_snapshot_sha256,
        "identity_source_binding_sha256": snapshot.identity_source_binding_sha256,
        "source_category_order": list(snapshot.source_category_order),
        "category_bindings": [row.to_dict() for row in snapshot.category_bindings],
        "uninterpreted_categories": list(snapshot.uninterpreted_categories),
    }


def mmcif_nonpoly_component_declaration_document(
    snapshot: MmcifNonpolyComponentDeclarationSnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_component_declaration_projection(snapshot)
    binding = mmcif_nonpoly_component_declaration_source_binding(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_COMPONENT_DECLARATION_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_COMPONENT_DECLARATION_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_COMPONENT_DECLARATION_PARSER_VERSION,
        "declaration_projection": projection,
        "source_binding": binding,
        "declaration_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def require_mmcif_nonpoly_component_declaration_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly component declaration document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_NONPOLY_COMPONENT_DECLARATION_DOCUMENT_SCHEMA_ID:
        raise ValueError("nonpoly component declaration document schema mismatch")
    if document.get("profile_id") != MMCIF_NONPOLY_COMPONENT_DECLARATION_PROFILE_ID:
        raise ValueError("nonpoly component declaration profile mismatch")
    if (
        document.get("parser_version")
        != MMCIF_NONPOLY_COMPONENT_DECLARATION_PARSER_VERSION
    ):
        raise ValueError("nonpoly component declaration parser version mismatch")
    projection = document.get("declaration_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("nonpoly component declaration sections must be mappings")
    if (
        projection.get("schema_id")
        != MMCIF_NONPOLY_COMPONENT_DECLARATION_PROJECTION_SCHEMA_ID
    ):
        raise ValueError("nonpoly component declaration projection schema mismatch")
    if (
        binding.get("schema_id")
        != MMCIF_NONPOLY_COMPONENT_DECLARATION_SOURCE_BINDING_SCHEMA_ID
    ):
        raise ValueError("nonpoly component declaration source binding schema mismatch")

    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("declaration_projection_sha256") != projection_digest:
        raise ValueError("nonpoly component declaration projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("nonpoly component declaration source binding digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_COMPONENT_DECLARATION_DOCUMENT_SCHEMA_ID,
            "declaration_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("nonpoly component declaration snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("nonpoly component declaration claim policy mismatch")

    component_ids = projection.get("component_ids")
    atom_rows = projection.get("atom_declarations")
    bond_rows = projection.get("bond_declarations")
    if not isinstance(component_ids, list) or not component_ids:
        raise ValueError("nonpoly component declaration component IDs must be non-empty")
    if not isinstance(atom_rows, list) or not atom_rows:
        raise ValueError("nonpoly component atom declarations must be non-empty")
    if not isinstance(bond_rows, list):
        raise ValueError("nonpoly component bond declarations must be a list")
    if document.get("component_ids") != component_ids:
        raise ValueError("nonpoly component declaration component binding mismatch")
    if document.get("component_count") != len(component_ids):
        raise ValueError("nonpoly component declaration component count mismatch")
    if document.get("atom_declaration_count") != len(atom_rows):
        raise ValueError("nonpoly component atom declaration count mismatch")
    if document.get("bond_declaration_count") != len(bond_rows):
        raise ValueError("nonpoly component bond declaration count mismatch")
    if document.get("bond_category_present") is not projection.get(
        "bond_category_present"
    ):
        raise ValueError("nonpoly component bond category binding mismatch")

    source_sha = binding.get("source_sha256")
    if _SHA256_RE.fullmatch(str(source_sha or "")) is None:
        raise ValueError("nonpoly component declaration source digest invalid")
    if document.get("source_sha256") != source_sha:
        raise ValueError("nonpoly component declaration source digest mismatch")
    for value, label in (
        (projection.get("identity_projection_sha256"), "identity projection"),
        (binding.get("identity_snapshot_sha256"), "identity snapshot"),
        (binding.get("identity_source_binding_sha256"), "identity source binding"),
    ):
        if _SHA256_RE.fullmatch(str(value or "")) is None:
            raise ValueError(
                f"nonpoly component declaration {label} digest invalid"
            )
    return payload


def mmcif_nonpoly_component_declaration_json_bytes(
    snapshot: MmcifNonpolyComponentDeclarationSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_component_declaration_document(snapshot))


def write_mmcif_nonpoly_component_declaration_json(
    path: str | Path,
    snapshot: MmcifNonpolyComponentDeclarationSnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_component_declaration_json_bytes(snapshot) + b"\n"
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
    "CHEM_COMP_ATOM_CATEGORY",
    "CHEM_COMP_BOND_CATEGORY",
    "MAX_MMCIF_NONPOLY_COMPONENT_DECLARATION_INTEGER",
    "MAX_MMCIF_NONPOLY_COMPONENT_DECLARATION_ROWS",
    "MAX_MMCIF_NONPOLY_COMPONENT_DECLARATION_TOKEN_CHARS",
    "MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS",
    "MMCIF_NONPOLY_COMPONENT_BOND_HEADERS",
    "MMCIF_NONPOLY_COMPONENT_DECLARATION_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_COMPONENT_DECLARATION_PARSER_VERSION",
    "MMCIF_NONPOLY_COMPONENT_DECLARATION_PROFILE_ID",
    "MMCIF_NONPOLY_COMPONENT_DECLARATION_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_COMPONENT_DECLARATION_SOURCE_BINDING_SCHEMA_ID",
    "MmcifNonpolyComponentAtomDeclaration",
    "MmcifNonpolyComponentBondDeclaration",
    "MmcifNonpolyComponentDeclarationCategoryBinding",
    "MmcifNonpolyComponentDeclarationError",
    "MmcifNonpolyComponentDeclarationSnapshot",
    "mmcif_nonpoly_component_declaration_document",
    "mmcif_nonpoly_component_declaration_json_bytes",
    "mmcif_nonpoly_component_declaration_projection",
    "mmcif_nonpoly_component_declaration_source_binding",
    "parse_mmcif_nonpoly_component_declarations",
    "require_mmcif_nonpoly_component_declaration_document",
    "write_mmcif_nonpoly_component_declaration_json",
]
