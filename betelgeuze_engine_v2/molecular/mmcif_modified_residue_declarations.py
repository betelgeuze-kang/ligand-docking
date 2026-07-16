"""Bounded source declarations for modified polymer residues in mmCIF.

The ``_pdbx_struct_mod_residue`` category explicitly lists modified polymer
components.  This carrier joins its label identity to the existing bounded
entity/asym/polymer-sequence projection and preserves the declared parent
component, model number, and insertion-code token.  It does not infer the
chemical nature of a modification, auth/label equivalence, atom-site
observation, preparation, parameterability, or biological function.
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

from .mmcif_semantics import (
    MmcifSemanticValue,
    parse_mmcif_semantics,
)
from .mmcif_syntax import CifLoop, CifToken, parse_cif_block


PDBX_STRUCT_MOD_RESIDUE_CATEGORY = "_pdbx_struct_mod_residue"
MMCIF_MODIFIED_RESIDUE_DECLARATION_HEADERS = (
    "_pdbx_struct_mod_residue.id",
    "_pdbx_struct_mod_residue.label_asym_id",
    "_pdbx_struct_mod_residue.label_seq_id",
    "_pdbx_struct_mod_residue.label_comp_id",
    "_pdbx_struct_mod_residue.parent_comp_id",
    "_pdbx_struct_mod_residue.pdb_model_num",
    "_pdbx_struct_mod_residue.pdb_ins_code",
)
MMCIF_MODIFIED_RESIDUE_DECLARATION_DICTIONARY_ITEMS: Mapping[str, str] = (
    MappingProxyType(
        {
            "_pdbx_struct_mod_residue.id": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Items/_pdbx_struct_mod_residue.id.html"
            ),
            "_pdbx_struct_mod_residue.label_asym_id": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Items/_pdbx_struct_mod_residue.label_asym_id.html"
            ),
            "_pdbx_struct_mod_residue.label_seq_id": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Items/_pdbx_struct_mod_residue.label_seq_id.html"
            ),
            "_pdbx_struct_mod_residue.label_comp_id": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Items/_pdbx_struct_mod_residue.label_comp_id.html"
            ),
            "_pdbx_struct_mod_residue.parent_comp_id": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Items/_pdbx_struct_mod_residue.parent_comp_id.html"
            ),
            "_pdbx_struct_mod_residue.PDB_model_num": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Items/_pdbx_struct_mod_residue.PDB_model_num.html"
            ),
            "_pdbx_struct_mod_residue.PDB_ins_code": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Items/_pdbx_struct_mod_residue.PDB_ins_code.html"
            ),
        }
    )
)

MMCIF_MODIFIED_RESIDUE_DECLARATION_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_modified_residue_declaration_projection/1.0.0"
)
MMCIF_MODIFIED_RESIDUE_DECLARATION_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_modified_residue_declaration_source_binding/1.0.0"
)
MMCIF_MODIFIED_RESIDUE_DECLARATION_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_modified_residue_declaration_document/1.0.0"
)
MMCIF_MODIFIED_RESIDUE_DECLARATION_PROFILE_ID = (
    "bounded_mmcif_modified_polymer_residue_source_declarations/1.0.0"
)
MMCIF_MODIFIED_RESIDUE_DECLARATION_PARSER_VERSION = "1.0.0"

MAX_MMCIF_MODIFIED_RESIDUE_DECLARATION_ROWS = 100_000
MAX_MMCIF_MODIFIED_RESIDUE_DECLARATION_TOKEN_CHARS = 256
MAX_MMCIF_MODIFIED_RESIDUE_DECLARATION_INTEGER = (1 << 53) - 1

_INTEGER_RE = re.compile(r"^[+]?[0-9]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_NO_WHITESPACE_RE = re.compile(r"^\S+$")
_ROLE = "source_declared_modified_polymer_component"
_ROLE_STATUS = "interpreted_source_declaration"
_PREPARATION_DISPOSITION = "explicitly_unsupported"
_ROLE_BLOCKERS = (
    "atom_site_label_identity_not_crosschecked",
    "parent_component_chemistry_not_interpreted",
    "modification_nature_not_interpreted",
    "model_insertion_and_auth_semantics_not_interpreted",
    "modified_residue_preparation_not_supported",
)


class MmcifModifiedResidueDeclarationError(ValueError):
    """Stable fail-closed error without opaque source-value echo."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            f"mmcif_modified_residue_declaration:{self.code}{suffix}: {self.detail}"
        )


@dataclass(frozen=True, slots=True)
class MmcifModifiedResidueDeclarationCategoryBinding:
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
class MmcifModifiedResidueDeclaration:
    ordinal: int
    declaration_id: int
    label_asym_id: str
    label_entity_id: str
    label_seq_id: int
    label_comp_id: str
    parent_comp_id: str
    model_number: int
    pdb_ins_code: MmcifSemanticValue
    row_sha256: str
    declaration_identity_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifModifiedResidueDeclaration("
            f"ordinal={self.ordinal}, model_number={self.model_number})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "declaration_id": self.declaration_id,
            "label_asym_id": self.label_asym_id,
            "label_entity_id": self.label_entity_id,
            "label_seq_id": self.label_seq_id,
            "label_comp_id": self.label_comp_id,
            "parent_comp_id": self.parent_comp_id,
            "model_number": self.model_number,
            "pdb_ins_code": self.pdb_ins_code.to_dict(),
            "row_sha256": self.row_sha256,
            "modified_residue_role": _ROLE,
            "role_status": _ROLE_STATUS,
            "preparation_disposition": _PREPARATION_DISPOSITION,
            "role_blockers": list(_ROLE_BLOCKERS),
            "declaration_identity_sha256": self.declaration_identity_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifModifiedResidueDeclarationSnapshot:
    source_sha256: str
    semantic_snapshot_sha256: str
    semantic_projection_sha256: str
    semantic_source_binding_sha256: str
    declarations: tuple[MmcifModifiedResidueDeclaration, ...]
    category_binding: MmcifModifiedResidueDeclarationCategoryBinding

    def __repr__(self) -> str:
        return (
            "MmcifModifiedResidueDeclarationSnapshot("
            f"declaration_count={len(self.declarations)})"
        )

    @property
    def declaration_projection_sha256(self) -> str:
        return _sha256(mmcif_modified_residue_declaration_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_modified_residue_declaration_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_MODIFIED_RESIDUE_DECLARATION_DOCUMENT_SCHEMA_ID,
                "declaration_projection_sha256": self.declaration_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_MODIFIED_RESIDUE_DECLARATION_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_MODIFIED_RESIDUE_DECLARATION_PROFILE_ID,
            "parser_version": MMCIF_MODIFIED_RESIDUE_DECLARATION_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "declaration_count": len(self.declarations),
            "model_numbers": sorted({row.model_number for row in self.declarations}),
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
        "source_modified_residue_declaration_interpreted": True,
        "polymer_label_identity_joined": True,
        "modified_residue_role_source_declared": True,
        "parent_component_id_preserved": True,
        "model_number_value_interpreted": True,
        "insertion_code_marker_interpreted": True,
        "dictionary_conformance_assessed": False,
        "atom_site_observation_joined": False,
        "parent_component_chemistry_interpreted": False,
        "modification_nature_interpreted": False,
        "auth_label_equivalence_inferred": False,
        "model_and_insertion_semantics_interpreted": False,
        "modified_residue_preparation_supported": False,
        "parameterable": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _semantic_value(token: CifToken) -> MmcifSemanticValue:
    if token.multiline:
        raise MmcifModifiedResidueDeclarationError(
            "multiline_value_not_supported",
            "reviewed modified-residue values must be bounded single tokens",
            line_number=token.line_number,
        )
    if not token.quoted and token.value == ".":
        state = "not_applicable"
    elif not token.quoted and token.value == "?":
        state = "unknown"
    else:
        state = "known"
    if len(token.value) > MAX_MMCIF_MODIFIED_RESIDUE_DECLARATION_TOKEN_CHARS:
        raise MmcifModifiedResidueDeclarationError(
            "token_too_long",
            "one modified-residue source token exceeds the bounded profile",
            line_number=token.line_number,
        )
    return MmcifSemanticValue(
        state=state,
        value=token.value,
        quoted=bool(token.quoted),
        line_number=int(token.line_number),
        column_number=int(token.column_number),
    )


def _known_identity(token: CifToken) -> str:
    value = _semantic_value(token)
    if (
        value.state != "known"
        or not value.value
        or _NO_WHITESPACE_RE.fullmatch(value.value) is None
    ):
        raise MmcifModifiedResidueDeclarationError(
            "required_identity_value_invalid",
            "one required modified-residue identity is unavailable or invalid",
            line_number=token.line_number,
        )
    return value.value


def _positive_integer(token: CifToken, *, code: str) -> int:
    value = _known_identity(token)
    if _INTEGER_RE.fullmatch(value) is None:
        raise MmcifModifiedResidueDeclarationError(
            code,
            "one modified-residue integer does not use the reviewed grammar",
            line_number=token.line_number,
        )
    number = int(value)
    if not 1 <= number <= MAX_MMCIF_MODIFIED_RESIDUE_DECLARATION_INTEGER:
        raise MmcifModifiedResidueDeclarationError(
            f"{code}_out_of_bounds",
            "one modified-residue integer is outside the bounded profile",
            line_number=token.line_number,
        )
    return number


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
    text: str,
) -> tuple[CifLoop, dict[str, int], MmcifModifiedResidueDeclarationCategoryBinding]:
    block = parse_cif_block(text)
    scalar_tags = tuple(
        tag
        for tag in block.scalar_values
        if tag.startswith(f"{PDBX_STRUCT_MOD_RESIDUE_CATEGORY}.")
    )
    if scalar_tags:
        raise MmcifModifiedResidueDeclarationError(
            "category_must_be_loop",
            "_pdbx_struct_mod_residue must use one category-local loop",
            line_number=block.scalar_values[scalar_tags[0]].line_number,
        )
    loops = [
        loop
        for loop in block.loops
        if PDBX_STRUCT_MOD_RESIDUE_CATEGORY in loop.categories
    ]
    if len(loops) != 1:
        raise MmcifModifiedResidueDeclarationError(
            "category_loop_count_mismatch",
            "_pdbx_struct_mod_residue must occur in exactly one loop",
        )
    loop = loops[0]
    if loop.categories != (PDBX_STRUCT_MOD_RESIDUE_CATEGORY,):
        raise MmcifModifiedResidueDeclarationError(
            "mixed_category_loop",
            "cross-category loops are outside this bounded declaration profile",
            line_number=loop.line_number,
        )
    if not loop.rows:
        raise MmcifModifiedResidueDeclarationError(
            "declaration_rows_missing",
            "at least one modified-residue source declaration is required",
            line_number=loop.line_number,
        )
    if len(loop.rows) > MAX_MMCIF_MODIFIED_RESIDUE_DECLARATION_ROWS:
        raise MmcifModifiedResidueDeclarationError(
            "too_many_declaration_rows",
            "modified-residue declarations exceed the bounded row count",
            line_number=loop.line_number,
        )
    index = {tag: position for position, tag in enumerate(loop.tags)}
    if any(
        header not in index for header in MMCIF_MODIFIED_RESIDUE_DECLARATION_HEADERS
    ):
        raise MmcifModifiedResidueDeclarationError(
            "required_declaration_header_missing",
            "_pdbx_struct_mod_residue is missing a reviewed identity header",
            line_number=loop.line_number,
        )
    interpreted = frozenset(MMCIF_MODIFIED_RESIDUE_DECLARATION_HEADERS)
    binding = MmcifModifiedResidueDeclarationCategoryBinding(
        category=PDBX_STRUCT_MOD_RESIDUE_CATEGORY,
        headers=tuple(loop.tags),
        interpreted_headers=tuple(tag for tag in loop.tags if tag in interpreted),
        uninterpreted_headers=tuple(tag for tag in loop.tags if tag not in interpreted),
        row_count=len(loop.rows),
        source_ordinal=block.category_order.index(PDBX_STRUCT_MOD_RESIDUE_CATEGORY),
        row_sha256=tuple(_row_sha(loop, row) for row in loop.rows),
    )
    return loop, index, binding


def _identity_payload(
    *,
    ordinal: int,
    declaration_id: int,
    label_asym_id: str,
    label_entity_id: str,
    label_seq_id: int,
    label_comp_id: str,
    parent_comp_id: str,
    model_number: int,
    pdb_ins_code: Mapping[str, Any],
    row_sha256: str,
) -> dict[str, Any]:
    return {
        "ordinal": ordinal,
        "declaration_id": declaration_id,
        "label_asym_id": label_asym_id,
        "label_entity_id": label_entity_id,
        "label_seq_id": label_seq_id,
        "label_comp_id": label_comp_id,
        "parent_comp_id": parent_comp_id,
        "model_number": model_number,
        "pdb_ins_code": dict(pdb_ins_code),
        "row_sha256": row_sha256,
        "modified_residue_role": _ROLE,
        "role_status": _ROLE_STATUS,
        "preparation_disposition": _PREPARATION_DISPOSITION,
        "role_blockers": list(_ROLE_BLOCKERS),
    }


def parse_mmcif_modified_residue_declarations(
    text: str,
) -> MmcifModifiedResidueDeclarationSnapshot:
    """Parse source-declared modified polymer residues and join label identity."""

    if type(text) is not str:
        raise TypeError("mmCIF modified-residue declaration input must be a string")
    semantic = parse_mmcif_semantics(text)
    loop, index, binding = _category_loop(text)
    source_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if semantic.source_sha256 != source_sha256:
        raise MmcifModifiedResidueDeclarationError(
            "source_carrier_mismatch",
            "semantic and modified-residue carriers must bind identical source bytes",
        )

    entities = {row.entity_id: row for row in semantic.entities}
    asym_units = {row.asym_id: row for row in semantic.asym_units}
    sequence = {
        (row.entity_id, row.sequence_number): row for row in semantic.polymer_sequence
    }
    seen_ids: set[int] = set()
    declarations: list[MmcifModifiedResidueDeclaration] = []
    for ordinal, row in enumerate(loop.rows):
        declaration_id = _positive_integer(
            row[index["_pdbx_struct_mod_residue.id"]],
            code="invalid_declaration_id",
        )
        if declaration_id in seen_ids:
            raise MmcifModifiedResidueDeclarationError(
                "duplicate_declaration_id",
                "modified-residue declaration ids must be unique",
                line_number=row[index["_pdbx_struct_mod_residue.id"]].line_number,
            )
        seen_ids.add(declaration_id)
        label_asym_id = _known_identity(
            row[index["_pdbx_struct_mod_residue.label_asym_id"]]
        )
        label_seq_id = _positive_integer(
            row[index["_pdbx_struct_mod_residue.label_seq_id"]],
            code="invalid_label_seq_id",
        )
        label_comp_id = _known_identity(
            row[index["_pdbx_struct_mod_residue.label_comp_id"]]
        )
        parent_comp_id = _known_identity(
            row[index["_pdbx_struct_mod_residue.parent_comp_id"]]
        )
        model_number = _positive_integer(
            row[index["_pdbx_struct_mod_residue.pdb_model_num"]],
            code="invalid_model_number",
        )
        pdb_ins_code = _semantic_value(
            row[index["_pdbx_struct_mod_residue.pdb_ins_code"]]
        )

        asym = asym_units.get(label_asym_id)
        if asym is None:
            raise MmcifModifiedResidueDeclarationError(
                "label_asym_reference_missing",
                "one modified-residue label asym does not exist in _struct_asym",
                line_number=row[
                    index["_pdbx_struct_mod_residue.label_asym_id"]
                ].line_number,
            )
        entity = entities.get(asym.entity_id)
        if entity is None or entity.entity_type != "polymer":
            raise MmcifModifiedResidueDeclarationError(
                "label_asym_not_polymer",
                "modified-residue label identity must reference a polymer entity",
                line_number=row[
                    index["_pdbx_struct_mod_residue.label_asym_id"]
                ].line_number,
            )
        sequence_row = sequence.get((asym.entity_id, label_seq_id))
        if sequence_row is None:
            raise MmcifModifiedResidueDeclarationError(
                "label_sequence_reference_missing",
                "one modified-residue label sequence position does not exist",
                line_number=row[
                    index["_pdbx_struct_mod_residue.label_seq_id"]
                ].line_number,
            )
        if sequence_row.monomer_id != label_comp_id:
            raise MmcifModifiedResidueDeclarationError(
                "label_component_reference_mismatch",
                "modified-residue label component must match polymer sequence identity",
                line_number=row[
                    index["_pdbx_struct_mod_residue.label_comp_id"]
                ].line_number,
            )
        row_sha256 = binding.row_sha256[ordinal]
        identity = _identity_payload(
            ordinal=ordinal,
            declaration_id=declaration_id,
            label_asym_id=label_asym_id,
            label_entity_id=asym.entity_id,
            label_seq_id=label_seq_id,
            label_comp_id=label_comp_id,
            parent_comp_id=parent_comp_id,
            model_number=model_number,
            pdb_ins_code=pdb_ins_code.to_dict(),
            row_sha256=row_sha256,
        )
        declarations.append(
            MmcifModifiedResidueDeclaration(
                ordinal=ordinal,
                declaration_id=declaration_id,
                label_asym_id=label_asym_id,
                label_entity_id=asym.entity_id,
                label_seq_id=label_seq_id,
                label_comp_id=label_comp_id,
                parent_comp_id=parent_comp_id,
                model_number=model_number,
                pdb_ins_code=pdb_ins_code,
                row_sha256=row_sha256,
                declaration_identity_sha256=_sha256(identity),
            )
        )

    return MmcifModifiedResidueDeclarationSnapshot(
        source_sha256=source_sha256,
        semantic_snapshot_sha256=semantic.snapshot_sha256,
        semantic_projection_sha256=semantic.semantic_projection_sha256,
        semantic_source_binding_sha256=semantic.source_binding_sha256,
        declarations=tuple(declarations),
        category_binding=binding,
    )


def mmcif_modified_residue_declaration_projection(
    snapshot: MmcifModifiedResidueDeclarationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_MODIFIED_RESIDUE_DECLARATION_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_MODIFIED_RESIDUE_DECLARATION_PROFILE_ID,
        "parser_version": MMCIF_MODIFIED_RESIDUE_DECLARATION_PARSER_VERSION,
        "semantic_projection_sha256": snapshot.semantic_projection_sha256,
        "declarations": [row.to_dict() for row in snapshot.declarations],
        "declaration_order": "pdbx_struct_mod_residue_source_order",
        **_claim_policy(),
    }


def mmcif_modified_residue_declaration_source_binding(
    snapshot: MmcifModifiedResidueDeclarationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_MODIFIED_RESIDUE_DECLARATION_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "semantic_snapshot_sha256": snapshot.semantic_snapshot_sha256,
        "semantic_source_binding_sha256": snapshot.semantic_source_binding_sha256,
        "dictionary_items": dict(MMCIF_MODIFIED_RESIDUE_DECLARATION_DICTIONARY_ITEMS),
        "category_binding": snapshot.category_binding.to_dict(),
    }


def mmcif_modified_residue_declaration_document(
    snapshot: MmcifModifiedResidueDeclarationSnapshot,
) -> dict[str, Any]:
    projection = mmcif_modified_residue_declaration_projection(snapshot)
    binding = mmcif_modified_residue_declaration_source_binding(snapshot)
    return {
        "schema_id": MMCIF_MODIFIED_RESIDUE_DECLARATION_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_MODIFIED_RESIDUE_DECLARATION_PROFILE_ID,
        "parser_version": MMCIF_MODIFIED_RESIDUE_DECLARATION_PARSER_VERSION,
        "declaration_projection": projection,
        "source_binding": binding,
        "declaration_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str) -> str:
    candidate = str(value or "")
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"modified-residue {label} digest invalid")
    return candidate


def _require_semantic_value(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("modified-residue insertion code must be a mapping")
    item = dict(value)
    state = item.get("state")
    token = item.get("value")
    quoted = item.get("quoted")
    if (
        state not in {"known", "unknown", "not_applicable"}
        or type(token) is not str
        or len(token) > MAX_MMCIF_MODIFIED_RESIDUE_DECLARATION_TOKEN_CHARS
        or type(quoted) is not bool
        or set(item) != {"state", "value", "quoted"}
    ):
        raise ValueError("modified-residue insertion code invalid")
    if state == "unknown" and (quoted or token != "?"):
        raise ValueError("modified-residue unknown insertion code invalid")
    if state == "not_applicable" and (quoted or token != "."):
        raise ValueError("modified-residue inapplicable insertion code invalid")
    return item


def _require_declaration(value: object, expected_ordinal: int) -> tuple[int, int]:
    if not isinstance(value, Mapping):
        raise ValueError("modified-residue declaration must be a mapping")
    row = dict(value)
    ordinal = row.get("ordinal")
    declaration_id = row.get("declaration_id")
    label_seq_id = row.get("label_seq_id")
    model_number = row.get("model_number")
    if ordinal != expected_ordinal:
        raise ValueError("modified-residue declaration order mismatch")
    for item in (declaration_id, label_seq_id, model_number):
        if (
            type(item) is not int
            or not 1 <= item <= MAX_MMCIF_MODIFIED_RESIDUE_DECLARATION_INTEGER
        ):
            raise ValueError("modified-residue declaration integer invalid")
    for key in (
        "label_asym_id",
        "label_entity_id",
        "label_comp_id",
        "parent_comp_id",
    ):
        item = row.get(key)
        if (
            type(item) is not str
            or not item
            or len(item) > MAX_MMCIF_MODIFIED_RESIDUE_DECLARATION_TOKEN_CHARS
            or _NO_WHITESPACE_RE.fullmatch(item) is None
        ):
            raise ValueError("modified-residue declaration identity invalid")
    insertion = _require_semantic_value(row.get("pdb_ins_code"))
    row_sha256 = _require_digest(row.get("row_sha256"), "row")
    if (
        row.get("modified_residue_role") != _ROLE
        or row.get("role_status") != _ROLE_STATUS
        or row.get("preparation_disposition") != _PREPARATION_DISPOSITION
        or row.get("role_blockers") != list(_ROLE_BLOCKERS)
    ):
        raise ValueError("modified-residue role boundary mismatch")
    identity = _identity_payload(
        ordinal=ordinal,
        declaration_id=declaration_id,
        label_asym_id=row["label_asym_id"],
        label_entity_id=row["label_entity_id"],
        label_seq_id=label_seq_id,
        label_comp_id=row["label_comp_id"],
        parent_comp_id=row["parent_comp_id"],
        model_number=model_number,
        pdb_ins_code=insertion,
        row_sha256=row_sha256,
    )
    if row.get("declaration_identity_sha256") != _sha256(identity):
        raise ValueError("modified-residue declaration identity digest mismatch")
    return declaration_id, model_number


def require_mmcif_modified_residue_declaration_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("modified-residue declaration document must be a mapping")
    document = dict(payload)
    if (
        document.get("schema_id")
        != MMCIF_MODIFIED_RESIDUE_DECLARATION_DOCUMENT_SCHEMA_ID
    ):
        raise ValueError("modified-residue declaration document schema mismatch")
    if document.get("profile_id") != MMCIF_MODIFIED_RESIDUE_DECLARATION_PROFILE_ID:
        raise ValueError("modified-residue declaration profile mismatch")
    if (
        document.get("parser_version")
        != MMCIF_MODIFIED_RESIDUE_DECLARATION_PARSER_VERSION
    ):
        raise ValueError("modified-residue declaration parser version mismatch")
    projection = document.get("declaration_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("modified-residue document sections must be mappings")
    if (
        projection.get("schema_id")
        != MMCIF_MODIFIED_RESIDUE_DECLARATION_PROJECTION_SCHEMA_ID
        or projection.get("profile_id") != MMCIF_MODIFIED_RESIDUE_DECLARATION_PROFILE_ID
        or projection.get("parser_version")
        != MMCIF_MODIFIED_RESIDUE_DECLARATION_PARSER_VERSION
        or projection.get("declaration_order") != "pdbx_struct_mod_residue_source_order"
    ):
        raise ValueError("modified-residue declaration projection policy mismatch")
    if (
        binding.get("schema_id")
        != MMCIF_MODIFIED_RESIDUE_DECLARATION_SOURCE_BINDING_SCHEMA_ID
    ):
        raise ValueError("modified-residue declaration source binding mismatch")
    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("declaration_projection_sha256") != projection_digest:
        raise ValueError("modified-residue declaration projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("modified-residue declaration binding digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_MODIFIED_RESIDUE_DECLARATION_DOCUMENT_SCHEMA_ID,
            "declaration_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("modified-residue declaration snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("modified-residue declaration claim policy mismatch")

    declarations = projection.get("declarations")
    if not isinstance(declarations, list) or not declarations:
        raise ValueError("modified-residue declarations must be non-empty")
    ids: list[int] = []
    models: list[int] = []
    for ordinal, declaration in enumerate(declarations):
        declaration_id, model_number = _require_declaration(declaration, ordinal)
        ids.append(declaration_id)
        models.append(model_number)
    if len(set(ids)) != len(ids):
        raise ValueError("modified-residue declaration ids must be unique")
    if document.get("declaration_count") != len(declarations):
        raise ValueError("modified-residue declaration count mismatch")
    if document.get("model_numbers") != sorted(set(models)):
        raise ValueError("modified-residue model summary mismatch")
    source_sha = _require_digest(binding.get("source_sha256"), "source")
    if document.get("source_sha256") != source_sha:
        raise ValueError("modified-residue source digest mismatch")
    _require_digest(projection.get("semantic_projection_sha256"), "semantic projection")
    _require_digest(binding.get("semantic_snapshot_sha256"), "semantic snapshot")
    _require_digest(
        binding.get("semantic_source_binding_sha256"), "semantic source binding"
    )
    if (
        binding.get("dictionary_items")
        != MMCIF_MODIFIED_RESIDUE_DECLARATION_DICTIONARY_ITEMS
    ):
        raise ValueError("modified-residue dictionary binding mismatch")
    category = binding.get("category_binding")
    if not isinstance(category, Mapping):
        raise ValueError("modified-residue category binding missing")
    headers = category.get("headers")
    interpreted = category.get("interpreted_headers")
    row_hashes = category.get("row_sha256")
    if (
        category.get("category") != PDBX_STRUCT_MOD_RESIDUE_CATEGORY
        or category.get("representation") != "loop"
        or not isinstance(headers, list)
        or not all(type(value) is str and value for value in headers)
        or len(set(headers)) != len(headers)
        or not isinstance(interpreted, list)
        or set(interpreted) != set(MMCIF_MODIFIED_RESIDUE_DECLARATION_HEADERS)
        or interpreted
        != [
            value
            for value in headers
            if value in MMCIF_MODIFIED_RESIDUE_DECLARATION_HEADERS
        ]
        or category.get("uninterpreted_headers")
        != [
            value
            for value in headers
            if value not in MMCIF_MODIFIED_RESIDUE_DECLARATION_HEADERS
        ]
        or category.get("row_count") != len(declarations)
        or type(category.get("source_ordinal")) is not int
        or category.get("source_ordinal") < 0
        or not isinstance(row_hashes, list)
        or len(row_hashes) != len(declarations)
        or not all(_SHA256_RE.fullmatch(str(value or "")) for value in row_hashes)
        or [row["row_sha256"] for row in declarations] != row_hashes
    ):
        raise ValueError("modified-residue category binding invalid")
    return payload


def mmcif_modified_residue_declaration_json_bytes(
    snapshot: MmcifModifiedResidueDeclarationSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_modified_residue_declaration_document(snapshot))


def write_mmcif_modified_residue_declaration_json(
    path: str | Path,
    snapshot: MmcifModifiedResidueDeclarationSnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_modified_residue_declaration_json_bytes(snapshot) + b"\n"
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
    "MAX_MMCIF_MODIFIED_RESIDUE_DECLARATION_INTEGER",
    "MAX_MMCIF_MODIFIED_RESIDUE_DECLARATION_ROWS",
    "MAX_MMCIF_MODIFIED_RESIDUE_DECLARATION_TOKEN_CHARS",
    "MMCIF_MODIFIED_RESIDUE_DECLARATION_DICTIONARY_ITEMS",
    "MMCIF_MODIFIED_RESIDUE_DECLARATION_DOCUMENT_SCHEMA_ID",
    "MMCIF_MODIFIED_RESIDUE_DECLARATION_HEADERS",
    "MMCIF_MODIFIED_RESIDUE_DECLARATION_PARSER_VERSION",
    "MMCIF_MODIFIED_RESIDUE_DECLARATION_PROFILE_ID",
    "MMCIF_MODIFIED_RESIDUE_DECLARATION_PROJECTION_SCHEMA_ID",
    "MMCIF_MODIFIED_RESIDUE_DECLARATION_SOURCE_BINDING_SCHEMA_ID",
    "MmcifModifiedResidueDeclaration",
    "MmcifModifiedResidueDeclarationCategoryBinding",
    "MmcifModifiedResidueDeclarationError",
    "MmcifModifiedResidueDeclarationSnapshot",
    "PDBX_STRUCT_MOD_RESIDUE_CATEGORY",
    "mmcif_modified_residue_declaration_document",
    "mmcif_modified_residue_declaration_json_bytes",
    "mmcif_modified_residue_declaration_projection",
    "mmcif_modified_residue_declaration_source_binding",
    "parse_mmcif_modified_residue_declarations",
    "require_mmcif_modified_residue_declaration_document",
    "write_mmcif_modified_residue_declaration_json",
]
