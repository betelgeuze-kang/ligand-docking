"""Bounded source-preservation projection for mmCIF nonpoly identity.

This module interprets only the source identity carrier formed by ``_entity``,
``_struct_asym``, ``_chem_comp.id``, ``_pdbx_entity_nonpoly``, and
``_pdbx_nonpoly_scheme``. It preserves component identifiers, opaque names,
instance aliases, marker states, source row order, exact selected-category row
hashes, and their joins.

It deliberately does not inspect ``_atom_site``, interpret component type or
formal charge, infer author/label equivalence, construct chemistry or topology,
write mmCIF, prepare a system, or authorize runtime or product execution.
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

from .mmcif_semantics import MmcifSemanticValue
from .mmcif_syntax import CifBlock, CifLoop, CifToken, parse_cif_block


ENTITY_CATEGORY = "_entity"
STRUCT_ASYM_CATEGORY = "_struct_asym"
CHEM_COMP_CATEGORY = "_chem_comp"
ENTITY_NONPOLY_CATEGORY = "_pdbx_entity_nonpoly"
NONPOLY_SCHEME_CATEGORY = "_pdbx_nonpoly_scheme"

MMCIF_NONPOLY_IDENTITY_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_identity_projection/1.0.0"
)
MMCIF_NONPOLY_IDENTITY_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_identity_source_binding/1.0.0"
)
MMCIF_NONPOLY_IDENTITY_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_identity_document/1.0.0"
)
MMCIF_NONPOLY_IDENTITY_PROFILE_ID = (
    "bounded_mmcif_nonpoly_component_instance_identity/1.0.0"
)
MMCIF_NONPOLY_IDENTITY_PARSER_VERSION = "1.0.0"

MAX_MMCIF_NONPOLY_IDENTITY_INPUT_CHARS = 64 * 1024 * 1024
MAX_MMCIF_NONPOLY_IDENTITY_TOKEN_CHARS = 256
MAX_MMCIF_NONPOLY_ENTITY_ROWS = 4_096
MAX_MMCIF_NONPOLY_SCHEME_ROWS = 80_000
MAX_MMCIF_NONPOLY_SELECTED_ROWS = 100_000

MMCIF_NONPOLY_IDENTITY_ENTITY_HEADERS = (
    "_entity.id",
    "_entity.type",
)
MMCIF_NONPOLY_IDENTITY_STRUCT_ASYM_HEADERS = (
    "_struct_asym.id",
    "_struct_asym.entity_id",
)
MMCIF_NONPOLY_IDENTITY_CHEM_COMP_HEADERS = ("_chem_comp.id",)
MMCIF_NONPOLY_IDENTITY_ENTITY_NONPOLY_HEADERS = (
    "_pdbx_entity_nonpoly.entity_id",
    "_pdbx_entity_nonpoly.comp_id",
)
MMCIF_NONPOLY_IDENTITY_ENTITY_NONPOLY_NAME_HEADER = (
    "_pdbx_entity_nonpoly.name"
)
MMCIF_NONPOLY_IDENTITY_SCHEME_HEADERS = (
    "_pdbx_nonpoly_scheme.asym_id",
    "_pdbx_nonpoly_scheme.entity_id",
    "_pdbx_nonpoly_scheme.mon_id",
    "_pdbx_nonpoly_scheme.ndb_seq_num",
    "_pdbx_nonpoly_scheme.pdb_seq_num",
    "_pdbx_nonpoly_scheme.auth_seq_num",
    "_pdbx_nonpoly_scheme.pdb_mon_id",
    "_pdbx_nonpoly_scheme.auth_mon_id",
    "_pdbx_nonpoly_scheme.pdb_strand_id",
    "_pdbx_nonpoly_scheme.pdb_ins_code",
)

_SELECTED_ENTITY_TYPES = frozenset({"non-polymer", "water"})
_SELECTED_CATEGORIES = frozenset(
    {
        ENTITY_CATEGORY,
        STRUCT_ASYM_CATEGORY,
        CHEM_COMP_CATEGORY,
        ENTITY_NONPOLY_CATEGORY,
        NONPOLY_SCHEME_CATEGORY,
    }
)
_BARE_IDENTITY_RE = re.compile(r"^[!-~]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyIdentityError(ValueError):
    """Stable fail-closed error that does not echo opaque source values."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"mmcif_nonpoly_identity:{self.code}{suffix}: {self.detail}")


@dataclass(frozen=True, slots=True)
class MmcifNonpolyCategoryBinding:
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
class MmcifNonpolyComponentIdentity:
    comp_id: str
    source_ordinal: int

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyComponentIdentity("
            f"source_ordinal={self.source_ordinal})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "comp_id": self.comp_id,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyEntityIdentity:
    entity_id: str
    entity_type: str
    comp_id: str
    name: MmcifSemanticValue | None
    source_ordinal: int

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyEntityIdentity("
            f"entity_type={self.entity_type!r}, source_ordinal={self.source_ordinal})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "comp_id": self.comp_id,
            "name": None if self.name is None else self.name.to_dict(),
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyInstanceIdentity:
    asym_id: str
    entity_id: str
    entity_type: str
    mon_id: str
    ndb_seq_num: str
    pdb_seq_num: str
    auth_seq_num: str
    pdb_mon_id: str
    auth_mon_id: str
    pdb_strand_id: str
    pdb_ins_code: MmcifSemanticValue
    instance_identity_sha256: str
    source_ordinal: int

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyInstanceIdentity("
            f"entity_type={self.entity_type!r}, source_ordinal={self.source_ordinal})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "asym_id": self.asym_id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "mon_id": self.mon_id,
            "ndb_seq_num": self.ndb_seq_num,
            "pdb_seq_num": self.pdb_seq_num,
            "auth_seq_num": self.auth_seq_num,
            "pdb_mon_id": self.pdb_mon_id,
            "auth_mon_id": self.auth_mon_id,
            "pdb_strand_id": self.pdb_strand_id,
            "pdb_ins_code": self.pdb_ins_code.to_dict(),
            "instance_identity_sha256": self.instance_identity_sha256,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyIdentitySnapshot:
    source_sha256: str
    block_name: str
    components: tuple[MmcifNonpolyComponentIdentity, ...]
    entities: tuple[MmcifNonpolyEntityIdentity, ...]
    instances: tuple[MmcifNonpolyInstanceIdentity, ...]
    source_category_order: tuple[str, ...]
    category_bindings: tuple[MmcifNonpolyCategoryBinding, ...]
    uninterpreted_categories: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyIdentitySnapshot("
            f"component_count={len(self.components)}, "
            f"entity_count={len(self.entities)}, "
            f"instance_count={len(self.instances)})"
        )

    @property
    def identity_projection_sha256(self) -> str:
        return _sha256_document(mmcif_nonpoly_identity_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_document(mmcif_nonpoly_identity_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256_document(
            {
                "schema_id": MMCIF_NONPOLY_IDENTITY_DOCUMENT_SCHEMA_ID,
                "identity_projection_sha256": self.identity_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_NONPOLY_IDENTITY_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
            "parser_version": MMCIF_NONPOLY_IDENTITY_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "block_name": self.block_name,
            "component_count": len(self.components),
            "entity_count": len(self.entities),
            "instance_count": len(self.instances),
            "entity_type_counts": {
                entity_type: sum(
                    1 for row in self.entities if row.entity_type == entity_type
                )
                for entity_type in sorted(_SELECTED_ENTITY_TYPES)
            },
            "uninterpreted_categories": list(self.uninterpreted_categories),
            "identity_projection_sha256": self.identity_projection_sha256,
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
        "source_component_ids_preserved": True,
        "source_nonpoly_entity_identity_preserved": True,
        "source_nonpoly_instance_aliases_preserved": True,
        "source_row_order_preserved": True,
        "entity_asym_component_joins_verified": True,
        "source_category_headers_bound": True,
        "source_authenticated": False,
        "atom_site_identity_joined": False,
        "atom_site_coordinates_interpreted": False,
        "chem_comp_type_interpreted": False,
        "formal_charge_interpreted": False,
        "auth_label_equivalence_inferred": False,
        "component_chemistry_interpreted": False,
        "role_assignment_interpreted": False,
        "bond_topology_interpreted": False,
        "bond_order_interpreted": False,
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


def _semantic_value(token: CifToken, *, field: str) -> MmcifSemanticValue:
    if token.multiline:
        raise MmcifNonpolyIdentityError(
            "multiline_value_not_supported",
            f"{field} must be a bounded single-line source value",
            line_number=token.line_number,
        )
    if len(token.value) > MAX_MMCIF_NONPOLY_IDENTITY_TOKEN_CHARS:
        raise MmcifNonpolyIdentityError(
            "source_token_out_of_bounds",
            f"{field} exceeds the bounded token domain",
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
        raise MmcifNonpolyIdentityError(
            "source_token_out_of_bounds",
            f"{field} exceeds the bounded semantic value domain",
            line_number=token.line_number,
        ) from exc


def _known_bare(token: CifToken, *, field: str) -> str:
    value = _semantic_value(token, field=field)
    if (
        value.state != "known"
        or value.quoted
        or _BARE_IDENTITY_RE.fullmatch(value.value) is None
    ):
        raise MmcifNonpolyIdentityError(
            "invalid_identity_token",
            f"{field} must be a nonmissing bare printable token",
            line_number=token.line_number,
        )
    return value.value


def _row_sha256(loop: CifLoop, row: tuple[CifToken, ...]) -> str:
    return _sha256_document(
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
    required_headers: tuple[str, ...],
    max_rows: int,
) -> tuple[CifLoop, dict[str, int], MmcifNonpolyCategoryBinding]:
    scalar_tags = tuple(
        tag for tag in block.scalar_values if tag.startswith(f"{category}.")
    )
    if scalar_tags:
        token = block.scalar_values[scalar_tags[0]]
        raise MmcifNonpolyIdentityError(
            "category_must_be_loop",
            "selected nonpoly identity categories must use category-local loops",
            line_number=token.line_number,
        )
    candidates = [loop for loop in block.loops if category in loop.categories]
    if not candidates:
        raise MmcifNonpolyIdentityError(
            "required_category_missing",
            "one selected nonpoly identity category is missing",
        )
    if len(candidates) != 1:
        raise MmcifNonpolyIdentityError(
            "multiple_category_loops",
            "selected nonpoly identity categories must occur exactly once",
            line_number=candidates[1].line_number,
        )
    loop = candidates[0]
    if loop.categories != (category,):
        raise MmcifNonpolyIdentityError(
            "mixed_category_loop",
            "cross-category loops are outside this bounded identity profile",
            line_number=loop.line_number,
        )
    if not loop.rows:
        raise MmcifNonpolyIdentityError(
            "category_rows_missing",
            "selected nonpoly identity categories must contain source rows",
            line_number=loop.line_number,
        )
    if len(loop.rows) > int(max_rows):
        raise MmcifNonpolyIdentityError(
            "too_many_category_rows",
            "one selected nonpoly identity category exceeds its row bound",
            line_number=loop.line_number,
        )
    index = {tag: position for position, tag in enumerate(loop.tags)}
    if any(header not in index for header in required_headers):
        raise MmcifNonpolyIdentityError(
            "required_header_missing",
            "one selected nonpoly identity category is missing reviewed headers",
            line_number=loop.line_number,
        )
    required_set = frozenset(required_headers)
    binding = MmcifNonpolyCategoryBinding(
        category=category,
        headers=tuple(loop.tags),
        interpreted_headers=tuple(
            header for header in loop.tags if header in required_set
        ),
        uninterpreted_headers=tuple(
            header for header in loop.tags if header not in required_set
        ),
        row_count=len(loop.rows),
        source_ordinal=block.category_order.index(category),
        row_sha256=tuple(_row_sha256(loop, row) for row in loop.rows),
    )
    return loop, index, binding


def _parse_entity_carrier(
    entity_loop: CifLoop,
    entity_index: Mapping[str, int],
    asym_loop: CifLoop,
    asym_index: Mapping[str, int],
) -> tuple[dict[str, str], dict[str, str]]:
    entity_types: dict[str, str] = {}
    for row in entity_loop.rows:
        entity_id_token = row[entity_index["_entity.id"]]
        entity_id = _known_bare(entity_id_token, field="_entity.id")
        entity_type = _known_bare(
            row[entity_index["_entity.type"]],
            field="_entity.type",
        ).lower()
        if entity_id in entity_types:
            raise MmcifNonpolyIdentityError(
                "duplicate_entity_id",
                "entity identifiers must be unique",
                line_number=entity_id_token.line_number,
            )
        entity_types[entity_id] = entity_type

    asym_to_entity: dict[str, str] = {}
    for row in asym_loop.rows:
        asym_token = row[asym_index["_struct_asym.id"]]
        asym_id = _known_bare(asym_token, field="_struct_asym.id")
        entity_id = _known_bare(
            row[asym_index["_struct_asym.entity_id"]],
            field="_struct_asym.entity_id",
        )
        if asym_id in asym_to_entity:
            raise MmcifNonpolyIdentityError(
                "duplicate_struct_asym_id",
                "struct_asym identifiers must be unique",
                line_number=asym_token.line_number,
            )
        if entity_id not in entity_types:
            raise MmcifNonpolyIdentityError(
                "struct_asym_entity_reference_missing",
                "one struct_asym row references an unknown entity",
                line_number=asym_token.line_number,
            )
        asym_to_entity[asym_id] = entity_id
    return entity_types, asym_to_entity


def _parse_components(
    loop: CifLoop,
    index: Mapping[str, int],
) -> tuple[MmcifNonpolyComponentIdentity, ...]:
    components: list[MmcifNonpolyComponentIdentity] = []
    seen: set[str] = set()
    for ordinal, row in enumerate(loop.rows):
        token = row[index["_chem_comp.id"]]
        comp_id = _known_bare(token, field="_chem_comp.id")
        if comp_id in seen:
            raise MmcifNonpolyIdentityError(
                "duplicate_component_id",
                "chemical component identifiers must be unique",
                line_number=token.line_number,
            )
        seen.add(comp_id)
        components.append(
            MmcifNonpolyComponentIdentity(
                comp_id=comp_id,
                source_ordinal=ordinal,
            )
        )
    return tuple(components)


def _parse_nonpoly_entities(
    loop: CifLoop,
    index: Mapping[str, int],
    *,
    entity_types: Mapping[str, str],
    component_ids: set[str],
) -> tuple[MmcifNonpolyEntityIdentity, ...]:
    required_entities = {
        entity_id
        for entity_id, entity_type in entity_types.items()
        if entity_type in _SELECTED_ENTITY_TYPES
    }
    if not required_entities:
        raise MmcifNonpolyIdentityError(
            "nonpoly_entity_missing",
            "at least one non-polymer or water entity is required",
        )

    entities: list[MmcifNonpolyEntityIdentity] = []
    seen: set[str] = set()
    has_name = MMCIF_NONPOLY_IDENTITY_ENTITY_NONPOLY_NAME_HEADER in index
    for ordinal, row in enumerate(loop.rows):
        entity_token = row[index["_pdbx_entity_nonpoly.entity_id"]]
        entity_id = _known_bare(
            entity_token,
            field="_pdbx_entity_nonpoly.entity_id",
        )
        if entity_id in seen:
            raise MmcifNonpolyIdentityError(
                "duplicate_nonpoly_entity_id",
                "entity_nonpoly identifiers must be unique",
                line_number=entity_token.line_number,
            )
        seen.add(entity_id)
        entity_type = entity_types.get(entity_id)
        if entity_type not in _SELECTED_ENTITY_TYPES:
            raise MmcifNonpolyIdentityError(
                "nonpoly_entity_type_mismatch",
                "one entity_nonpoly row does not reference a non-polymer or water entity",
                line_number=entity_token.line_number,
            )
        comp_token = row[index["_pdbx_entity_nonpoly.comp_id"]]
        comp_id = _known_bare(
            comp_token,
            field="_pdbx_entity_nonpoly.comp_id",
        )
        if comp_id not in component_ids:
            raise MmcifNonpolyIdentityError(
                "component_reference_missing",
                "one entity_nonpoly row references an unknown component",
                line_number=comp_token.line_number,
            )
        name = (
            _semantic_value(
                row[index[MMCIF_NONPOLY_IDENTITY_ENTITY_NONPOLY_NAME_HEADER]],
                field=MMCIF_NONPOLY_IDENTITY_ENTITY_NONPOLY_NAME_HEADER,
            )
            if has_name
            else None
        )
        entities.append(
            MmcifNonpolyEntityIdentity(
                entity_id=entity_id,
                entity_type=entity_type,
                comp_id=comp_id,
                name=name,
                source_ordinal=ordinal,
            )
        )
    if seen != required_entities:
        raise MmcifNonpolyIdentityError(
            "nonpoly_entity_coverage_mismatch",
            "entity_nonpoly rows must exactly cover non-polymer and water entities",
        )
    return tuple(entities)


def _instance_digest(
    *,
    asym_id: str,
    entity_id: str,
    mon_id: str,
    ndb_seq_num: str,
    pdb_ins_code: MmcifSemanticValue,
) -> str:
    return _sha256_document(
        {
            "asym_id": asym_id,
            "entity_id": entity_id,
            "mon_id": mon_id,
            "ndb_seq_num": ndb_seq_num,
            "pdb_ins_code": pdb_ins_code.to_dict(),
        }
    )


def _parse_instances(
    loop: CifLoop,
    index: Mapping[str, int],
    *,
    asym_to_entity: Mapping[str, str],
    entity_rows: tuple[MmcifNonpolyEntityIdentity, ...],
) -> tuple[MmcifNonpolyInstanceIdentity, ...]:
    selected = {row.entity_id: row for row in entity_rows}
    observed_selected_entities = {
        entity_id
        for entity_id in asym_to_entity.values()
        if entity_id in selected
    }
    if observed_selected_entities != set(selected):
        raise MmcifNonpolyIdentityError(
            "nonpoly_asym_coverage_mismatch",
            "every selected nonpoly entity must have at least one struct_asym carrier",
        )
    expected_asym = {
        asym_id
        for asym_id, entity_id in asym_to_entity.items()
        if entity_id in selected
    }

    instances: list[MmcifNonpolyInstanceIdentity] = []
    seen_keys: set[tuple[str, str]] = set()
    observed_asym: set[str] = set()
    for ordinal, row in enumerate(loop.rows):
        asym_token = row[index["_pdbx_nonpoly_scheme.asym_id"]]
        asym_id = _known_bare(
            asym_token,
            field="_pdbx_nonpoly_scheme.asym_id",
        )
        entity_id = _known_bare(
            row[index["_pdbx_nonpoly_scheme.entity_id"]],
            field="_pdbx_nonpoly_scheme.entity_id",
        )
        ndb_seq_num = _known_bare(
            row[index["_pdbx_nonpoly_scheme.ndb_seq_num"]],
            field="_pdbx_nonpoly_scheme.ndb_seq_num",
        )
        key = (asym_id, ndb_seq_num)
        if key in seen_keys:
            raise MmcifNonpolyIdentityError(
                "duplicate_nonpoly_scheme_key",
                "nonpoly scheme (asym_id, ndb_seq_num) keys must be unique",
                line_number=asym_token.line_number,
            )
        seen_keys.add(key)

        expected_entity = asym_to_entity.get(asym_id)
        selected_entity = selected.get(entity_id)
        if expected_entity != entity_id or selected_entity is None:
            raise MmcifNonpolyIdentityError(
                "nonpoly_scheme_join_mismatch",
                "one nonpoly scheme asym/entity join is inconsistent",
                line_number=asym_token.line_number,
            )
        mon_token = row[index["_pdbx_nonpoly_scheme.mon_id"]]
        mon_id = _known_bare(
            mon_token,
            field="_pdbx_nonpoly_scheme.mon_id",
        )
        if mon_id != selected_entity.comp_id:
            raise MmcifNonpolyIdentityError(
                "nonpoly_component_join_mismatch",
                "one nonpoly scheme component identity is inconsistent",
                line_number=mon_token.line_number,
            )
        pdb_ins_code = _semantic_value(
            row[index["_pdbx_nonpoly_scheme.pdb_ins_code"]],
            field="_pdbx_nonpoly_scheme.pdb_ins_code",
        )
        observed_asym.add(asym_id)
        instances.append(
            MmcifNonpolyInstanceIdentity(
                asym_id=asym_id,
                entity_id=entity_id,
                entity_type=selected_entity.entity_type,
                mon_id=mon_id,
                ndb_seq_num=ndb_seq_num,
                pdb_seq_num=_known_bare(
                    row[index["_pdbx_nonpoly_scheme.pdb_seq_num"]],
                    field="_pdbx_nonpoly_scheme.pdb_seq_num",
                ),
                auth_seq_num=_known_bare(
                    row[index["_pdbx_nonpoly_scheme.auth_seq_num"]],
                    field="_pdbx_nonpoly_scheme.auth_seq_num",
                ),
                pdb_mon_id=_known_bare(
                    row[index["_pdbx_nonpoly_scheme.pdb_mon_id"]],
                    field="_pdbx_nonpoly_scheme.pdb_mon_id",
                ),
                auth_mon_id=_known_bare(
                    row[index["_pdbx_nonpoly_scheme.auth_mon_id"]],
                    field="_pdbx_nonpoly_scheme.auth_mon_id",
                ),
                pdb_strand_id=_known_bare(
                    row[index["_pdbx_nonpoly_scheme.pdb_strand_id"]],
                    field="_pdbx_nonpoly_scheme.pdb_strand_id",
                ),
                pdb_ins_code=pdb_ins_code,
                instance_identity_sha256=_instance_digest(
                    asym_id=asym_id,
                    entity_id=entity_id,
                    mon_id=mon_id,
                    ndb_seq_num=ndb_seq_num,
                    pdb_ins_code=pdb_ins_code,
                ),
                source_ordinal=ordinal,
            )
        )
    if observed_asym != expected_asym:
        raise MmcifNonpolyIdentityError(
            "nonpoly_scheme_coverage_mismatch",
            "nonpoly scheme rows must cover every and only selected struct_asym carrier",
        )
    return tuple(instances)


def parse_mmcif_nonpoly_identity(text: str) -> MmcifNonpolyIdentitySnapshot:
    """Parse bounded source-reported nonpoly component and instance identity."""

    if type(text) is not str:
        raise TypeError("mmCIF nonpoly identity input must be a string")
    if len(text) > MAX_MMCIF_NONPOLY_IDENTITY_INPUT_CHARS:
        raise MmcifNonpolyIdentityError(
            "input_too_large",
            "mmCIF nonpoly identity input exceeds the bounded character limit",
        )
    block = parse_cif_block(text)
    source_sha256 = hashlib.sha256(text.encode("ascii")).hexdigest()

    selected: list[tuple[CifLoop, dict[str, int], MmcifNonpolyCategoryBinding]] = []
    selected.append(
        _category_loop(
            block,
            category=ENTITY_CATEGORY,
            required_headers=MMCIF_NONPOLY_IDENTITY_ENTITY_HEADERS,
            max_rows=MAX_MMCIF_NONPOLY_SELECTED_ROWS,
        )
    )
    selected.append(
        _category_loop(
            block,
            category=STRUCT_ASYM_CATEGORY,
            required_headers=MMCIF_NONPOLY_IDENTITY_STRUCT_ASYM_HEADERS,
            max_rows=MAX_MMCIF_NONPOLY_SELECTED_ROWS,
        )
    )
    selected.append(
        _category_loop(
            block,
            category=CHEM_COMP_CATEGORY,
            required_headers=MMCIF_NONPOLY_IDENTITY_CHEM_COMP_HEADERS,
            max_rows=MAX_MMCIF_NONPOLY_ENTITY_ROWS,
        )
    )
    selected.append(
        _category_loop(
            block,
            category=ENTITY_NONPOLY_CATEGORY,
            required_headers=MMCIF_NONPOLY_IDENTITY_ENTITY_NONPOLY_HEADERS,
            max_rows=MAX_MMCIF_NONPOLY_ENTITY_ROWS,
        )
    )
    selected.append(
        _category_loop(
            block,
            category=NONPOLY_SCHEME_CATEGORY,
            required_headers=MMCIF_NONPOLY_IDENTITY_SCHEME_HEADERS,
            max_rows=MAX_MMCIF_NONPOLY_SCHEME_ROWS,
        )
    )

    (
        (entity_loop, entity_index, _),
        (asym_loop, asym_index, _),
        (component_loop, component_index, _),
        (entity_nonpoly_loop, entity_nonpoly_index, _),
        (scheme_loop, scheme_index, _),
    ) = selected

    entity_types, asym_to_entity = _parse_entity_carrier(
        entity_loop,
        entity_index,
        asym_loop,
        asym_index,
    )
    components = _parse_components(component_loop, component_index)
    entities = _parse_nonpoly_entities(
        entity_nonpoly_loop,
        entity_nonpoly_index,
        entity_types=entity_types,
        component_ids={row.comp_id for row in components},
    )
    selected_component_ids = {row.comp_id for row in entities}
    components = tuple(
        row for row in components if row.comp_id in selected_component_ids
    )
    instances = _parse_instances(
        scheme_loop,
        scheme_index,
        asym_to_entity=asym_to_entity,
        entity_rows=entities,
    )
    return MmcifNonpolyIdentitySnapshot(
        source_sha256=source_sha256,
        block_name=block.name,
        components=components,
        entities=entities,
        instances=instances,
        source_category_order=tuple(block.category_order),
        category_bindings=tuple(item[2] for item in selected),
        uninterpreted_categories=tuple(
            category
            for category in block.category_order
            if category not in _SELECTED_CATEGORIES
        ),
    )


def mmcif_nonpoly_identity_projection(
    snapshot: MmcifNonpolyIdentitySnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_IDENTITY_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_IDENTITY_PARSER_VERSION,
        "components": [row.to_dict() for row in snapshot.components],
        "entities": [row.to_dict() for row in snapshot.entities],
        "instances": [row.to_dict() for row in snapshot.instances],
        "row_order": "source_order_within_each_selected_category",
        **_claim_policy(),
    }


def mmcif_nonpoly_identity_source_binding(
    snapshot: MmcifNonpolyIdentitySnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_IDENTITY_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "block_name": snapshot.block_name,
        "source_category_order": list(snapshot.source_category_order),
        "category_bindings": [
            binding.to_dict() for binding in snapshot.category_bindings
        ],
        "uninterpreted_categories": list(snapshot.uninterpreted_categories),
    }


def mmcif_nonpoly_identity_document(
    snapshot: MmcifNonpolyIdentitySnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_identity_projection(snapshot)
    source_binding = mmcif_nonpoly_identity_source_binding(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_IDENTITY_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_IDENTITY_PARSER_VERSION,
        "identity_projection": projection,
        "source_binding": source_binding,
        "identity_projection_sha256": _sha256_document(projection),
        "source_binding_sha256": _sha256_document(source_binding),
        **snapshot.to_dict(),
    }


def require_mmcif_nonpoly_identity_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly identity document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_NONPOLY_IDENTITY_DOCUMENT_SCHEMA_ID:
        raise ValueError("nonpoly identity document schema mismatch")
    if document.get("profile_id") != MMCIF_NONPOLY_IDENTITY_PROFILE_ID:
        raise ValueError("nonpoly identity profile mismatch")
    if document.get("parser_version") != MMCIF_NONPOLY_IDENTITY_PARSER_VERSION:
        raise ValueError("nonpoly identity parser version mismatch")

    projection = document.get("identity_projection")
    source_binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(source_binding, Mapping):
        raise ValueError("nonpoly identity document sections must be mappings")
    if projection.get("schema_id") != MMCIF_NONPOLY_IDENTITY_PROJECTION_SCHEMA_ID:
        raise ValueError("nonpoly identity projection schema mismatch")
    if (
        source_binding.get("schema_id")
        != MMCIF_NONPOLY_IDENTITY_SOURCE_BINDING_SCHEMA_ID
    ):
        raise ValueError("nonpoly identity source binding schema mismatch")

    projection_digest = _sha256_document(dict(projection))
    source_digest = _sha256_document(dict(source_binding))
    if document.get("identity_projection_sha256") != projection_digest:
        raise ValueError("nonpoly identity projection digest mismatch")
    if document.get("source_binding_sha256") != source_digest:
        raise ValueError("nonpoly identity source binding digest mismatch")
    expected_snapshot_digest = _sha256_document(
        {
            "schema_id": MMCIF_NONPOLY_IDENTITY_DOCUMENT_SCHEMA_ID,
            "identity_projection_sha256": projection_digest,
            "source_binding_sha256": source_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot_digest:
        raise ValueError("nonpoly identity snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("nonpoly identity claim policy mismatch")

    components = projection.get("components")
    entities = projection.get("entities")
    instances = projection.get("instances")
    if not isinstance(components, list) or not components:
        raise ValueError("nonpoly identity components must be a non-empty list")
    if not isinstance(entities, list) or not entities:
        raise ValueError("nonpoly identity entities must be a non-empty list")
    if not isinstance(instances, list) or not instances:
        raise ValueError("nonpoly identity instances must be a non-empty list")
    if document.get("component_count") != len(components):
        raise ValueError("nonpoly identity component count mismatch")
    if document.get("entity_count") != len(entities):
        raise ValueError("nonpoly identity entity count mismatch")
    if document.get("instance_count") != len(instances):
        raise ValueError("nonpoly identity instance count mismatch")

    source_sha = source_binding.get("source_sha256")
    if _SHA256_RE.fullmatch(str(source_sha or "")) is None:
        raise ValueError("nonpoly identity source digest invalid")
    if document.get("source_sha256") != source_sha:
        raise ValueError("nonpoly identity source digest binding mismatch")
    category_bindings = source_binding.get("category_bindings")
    if not isinstance(category_bindings, list) or len(category_bindings) != 5:
        raise ValueError("nonpoly identity category binding count mismatch")
    if {
        str(binding.get("category"))
        for binding in category_bindings
        if isinstance(binding, Mapping)
    } != _SELECTED_CATEGORIES:
        raise ValueError("nonpoly identity selected category binding mismatch")
    return payload


def mmcif_nonpoly_identity_json_bytes(
    snapshot: MmcifNonpolyIdentitySnapshot,
) -> bytes:
    return _canonical_json_bytes(mmcif_nonpoly_identity_document(snapshot))


def write_mmcif_nonpoly_identity_json(
    path: str | Path,
    snapshot: MmcifNonpolyIdentitySnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_identity_json_bytes(snapshot) + b"\n"
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
    "CHEM_COMP_CATEGORY",
    "ENTITY_CATEGORY",
    "ENTITY_NONPOLY_CATEGORY",
    "MAX_MMCIF_NONPOLY_ENTITY_ROWS",
    "MAX_MMCIF_NONPOLY_IDENTITY_INPUT_CHARS",
    "MAX_MMCIF_NONPOLY_IDENTITY_TOKEN_CHARS",
    "MAX_MMCIF_NONPOLY_SCHEME_ROWS",
    "MMCIF_NONPOLY_IDENTITY_CHEM_COMP_HEADERS",
    "MMCIF_NONPOLY_IDENTITY_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_IDENTITY_ENTITY_HEADERS",
    "MMCIF_NONPOLY_IDENTITY_ENTITY_NONPOLY_HEADERS",
    "MMCIF_NONPOLY_IDENTITY_ENTITY_NONPOLY_NAME_HEADER",
    "MMCIF_NONPOLY_IDENTITY_PARSER_VERSION",
    "MMCIF_NONPOLY_IDENTITY_PROFILE_ID",
    "MMCIF_NONPOLY_IDENTITY_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_IDENTITY_SCHEME_HEADERS",
    "MMCIF_NONPOLY_IDENTITY_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_NONPOLY_IDENTITY_STRUCT_ASYM_HEADERS",
    "MmcifNonpolyCategoryBinding",
    "MmcifNonpolyComponentIdentity",
    "MmcifNonpolyEntityIdentity",
    "MmcifNonpolyIdentityError",
    "MmcifNonpolyIdentitySnapshot",
    "MmcifNonpolyInstanceIdentity",
    "NONPOLY_SCHEME_CATEGORY",
    "STRUCT_ASYM_CATEGORY",
    "mmcif_nonpoly_identity_document",
    "mmcif_nonpoly_identity_json_bytes",
    "mmcif_nonpoly_identity_projection",
    "mmcif_nonpoly_identity_source_binding",
    "parse_mmcif_nonpoly_identity",
    "require_mmcif_nonpoly_identity_document",
    "write_mmcif_nonpoly_identity_json",
]
