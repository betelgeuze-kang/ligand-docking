"""Bounded preservation of source-reported mmCIF zero-occupancy atom declarations.

This module composes the accepted CIF syntax and semantic identity/sequence
projection with exactly one ``_pdbx_unobs_or_zero_occ_atoms`` loop.  It preserves
ordered source declarations and validates their label-side references against the
bounded entity/asym/polymer-sequence substrate.

It deliberately does **not** interpret ``_atom_site``, cross-check coordinate rows,
claim that an atom is absent, assign occupancy populations, infer auth/label
identity, select alternate locations, complete atoms, build topology, or authorize
runtime/product use.
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
from types import MappingProxyType
from typing import Any, Mapping

from .mmcif_semantics import MmcifSemanticSnapshot, parse_mmcif_semantics
from .mmcif_syntax import CifLoop, CifToken, parse_cif_block

MMCIF_ZERO_OCCUPANCY_ATOM_DECLARATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_zero_occupancy_atom_declarations/1.0.0"
)
MMCIF_ZERO_OCCUPANCY_ATOM_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_zero_occupancy_atom_document/1.0.0"
)
MMCIF_ZERO_OCCUPANCY_ATOM_PROFILE_ID = (
    "bounded_source_reported_zero_occupancy_atom_declarations/1.0.0"
)
MMCIF_ZERO_OCCUPANCY_ATOM_PARSER_VERSION = "1.0.0"
MAX_MMCIF_ZERO_OCCUPANCY_ATOM_ROWS = 10_000
MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS = 256

MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS = (
    "_pdbx_unobs_or_zero_occ_atoms.id",
    "_pdbx_unobs_or_zero_occ_atoms.polymer_flag",
    "_pdbx_unobs_or_zero_occ_atoms.occupancy_flag",
    "_pdbx_unobs_or_zero_occ_atoms.pdb_model_num",
    "_pdbx_unobs_or_zero_occ_atoms.auth_asym_id",
    "_pdbx_unobs_or_zero_occ_atoms.auth_comp_id",
    "_pdbx_unobs_or_zero_occ_atoms.auth_seq_id",
    "_pdbx_unobs_or_zero_occ_atoms.pdb_ins_code",
    "_pdbx_unobs_or_zero_occ_atoms.auth_atom_id",
    "_pdbx_unobs_or_zero_occ_atoms.label_alt_id",
    "_pdbx_unobs_or_zero_occ_atoms.label_asym_id",
    "_pdbx_unobs_or_zero_occ_atoms.label_comp_id",
    "_pdbx_unobs_or_zero_occ_atoms.label_seq_id",
    "_pdbx_unobs_or_zero_occ_atoms.label_atom_id",
)

_CATEGORY = "_pdbx_unobs_or_zero_occ_atoms"
_POSITIVE_INTEGER_RE = re.compile(r"^[1-9][0-9]*$")
_PRINTABLE_TOKEN_RE = re.compile(r"^[!-~]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MARKER_STATES = frozenset({"known", "not_applicable", "unknown"})


class MmcifZeroOccupancyAtomDeclarationError(ValueError):
    """Stable fail-closed declaration error without source identity disclosure."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"mmcif_zero_occupancy_atom:{self.code}{suffix}: {self.detail}")


@dataclass(frozen=True, slots=True)
class MmcifDeclarationMarker:
    state: str
    value: str
    quoted: bool

    def __post_init__(self) -> None:
        if self.state not in _MARKER_STATES:
            raise ValueError("unsupported declaration marker state")
        if type(self.value) is not str or not self.value:
            raise ValueError("declaration marker value must be non-empty text")
        if len(self.value) > MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS:
            raise ValueError("declaration marker exceeds the bounded token domain")
        expected = {"not_applicable": ".", "unknown": "?"}.get(self.state)
        if expected is not None and self.value != expected:
            raise ValueError("declaration marker state and value disagree")
        if type(self.quoted) is not bool:
            raise TypeError("quoted must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return {"state": self.state, "value": self.value, "quoted": self.quoted}


@dataclass(frozen=True, slots=True)
class MmcifZeroOccupancyAtomDeclaration:
    source_id: int
    model_number: int
    auth_asym_id: str
    auth_comp_id: str
    auth_seq_id: str
    insertion_code: MmcifDeclarationMarker
    auth_atom_id: str
    label_alt_id: MmcifDeclarationMarker
    label_asym_id: str
    label_comp_id: str
    label_seq_id: int
    label_atom_id: str
    entity_id: str
    source_ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "model_number": self.model_number,
            "auth_asym_id": self.auth_asym_id,
            "auth_comp_id": self.auth_comp_id,
            "auth_seq_id": self.auth_seq_id,
            "insertion_code": self.insertion_code.to_dict(),
            "auth_atom_id": self.auth_atom_id,
            "label_alt_id": self.label_alt_id.to_dict(),
            "label_asym_id": self.label_asym_id,
            "label_comp_id": self.label_comp_id,
            "label_seq_id": self.label_seq_id,
            "label_atom_id": self.label_atom_id,
            "entity_id": self.entity_id,
            "source_ordinal": self.source_ordinal,
            "polymer_flag": "Y",
            "occupancy_numeric_zero": True,
        }


@dataclass(frozen=True, slots=True)
class MmcifZeroOccupancyAtomSnapshot:
    source_sha256: str
    semantic_projection_sha256: str
    source_category_order: tuple[str, ...]
    loop_headers: tuple[str, ...]
    declarations: tuple[MmcifZeroOccupancyAtomDeclaration, ...]

    @property
    def declaration_projection_sha256(self) -> str:
        return _sha256_document(zero_occupancy_atom_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_document(zero_occupancy_atom_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256_document(
            {
                "schema_id": MMCIF_ZERO_OCCUPANCY_ATOM_DOCUMENT_SCHEMA_ID,
                "declaration_projection_sha256": self.declaration_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_ZERO_OCCUPANCY_ATOM_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_ZERO_OCCUPANCY_ATOM_PROFILE_ID,
            "parser_version": MMCIF_ZERO_OCCUPANCY_ATOM_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "semantic_projection_sha256": self.semantic_projection_sha256,
            "declaration_count": len(self.declarations),
            "declaration_projection_sha256": self.declaration_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            "source_reported_zero_occupancy_atom_declarations_preserved": True,
            **_claim_policy(),
        }


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_document(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _claim_policy() -> dict[str, bool]:
    return {
        "atom_site_semantics_interpreted": False,
        "coordinate_row_crosscheck_performed": False,
        "coordinate_observation_completeness_assessed": False,
        "zero_occupancy_atom_fact_claimed": False,
        "missing_atom_fact_claimed": False,
        "occupancy_population_interpreted": False,
        "occupancy_weighting_applied": False,
        "refinement_validity_assessed": False,
        "auth_label_equivalence_inferred": False,
        "altloc_population_interpreted": False,
        "chemistry_interpreted": False,
        "topology_interpreted": False,
        "completion_attempted": False,
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


def _loop(block: Any) -> tuple[CifLoop, dict[str, int]]:
    scalar_tags = tuple(tag for tag in block.scalar_values if tag.startswith(f"{_CATEGORY}."))
    if scalar_tags:
        token = block.scalar_values[scalar_tags[0]]
        raise MmcifZeroOccupancyAtomDeclarationError(
            "category_must_be_loop",
            "zero-occupancy atom declarations must use one loop",
            line_number=token.line_number,
        )
    candidates = [loop for loop in block.loops if _CATEGORY in loop.categories]
    if not candidates:
        raise MmcifZeroOccupancyAtomDeclarationError(
            "declaration_loop_missing",
            "the zero-occupancy atom declaration loop is required",
        )
    if len(candidates) != 1:
        raise MmcifZeroOccupancyAtomDeclarationError(
            "multiple_declaration_loops",
            "the declaration category must occur in exactly one loop",
            line_number=candidates[1].line_number,
        )
    selected = candidates[0]
    if selected.categories != (_CATEGORY,):
        raise MmcifZeroOccupancyAtomDeclarationError(
            "mixed_category_loop",
            "cross-category declaration loops are outside this profile",
            line_number=selected.line_number,
        )
    if not selected.rows:
        raise MmcifZeroOccupancyAtomDeclarationError(
            "declaration_rows_missing",
            "at least one zero-occupancy atom declaration is required",
            line_number=selected.line_number,
        )
    if len(selected.rows) > MAX_MMCIF_ZERO_OCCUPANCY_ATOM_ROWS:
        raise MmcifZeroOccupancyAtomDeclarationError(
            "too_many_declaration_rows",
            "the zero-occupancy atom declaration row bound was exceeded",
            line_number=selected.line_number,
        )
    index = {tag: position for position, tag in enumerate(selected.tags)}
    missing = [header for header in MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS if header not in index]
    if missing:
        raise MmcifZeroOccupancyAtomDeclarationError(
            "required_header_missing",
            "one or more required zero-occupancy atom headers are missing",
            line_number=selected.line_number,
        )
    return selected, index


def _positive_integer(token: CifToken, *, field: str) -> int:
    if token.quoted or token.multiline or _POSITIVE_INTEGER_RE.fullmatch(token.value) is None:
        raise MmcifZeroOccupancyAtomDeclarationError(
            "invalid_positive_integer",
            f"{field} must be a canonical positive integer",
            line_number=token.line_number,
        )
    return int(token.value)


def _known_token(token: CifToken, *, field: str) -> str:
    value = token.value
    if (
        token.quoted
        or token.multiline
        or value in {"", ".", "?"}
        or len(value) > MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS
        or _PRINTABLE_TOKEN_RE.fullmatch(value) is None
    ):
        raise MmcifZeroOccupancyAtomDeclarationError(
            "invalid_identity_token",
            f"{field} must be a bounded bare printable identity token",
            line_number=token.line_number,
        )
    return value


def _marker(token: CifToken, *, field: str) -> MmcifDeclarationMarker:
    if token.multiline or len(token.value) > MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS:
        raise MmcifZeroOccupancyAtomDeclarationError(
            "invalid_marker_token",
            f"{field} exceeds the bounded marker domain",
            line_number=token.line_number,
        )
    if not token.quoted and token.value == ".":
        state = "not_applicable"
    elif not token.quoted and token.value == "?":
        state = "unknown"
    elif token.value and _PRINTABLE_TOKEN_RE.fullmatch(token.value) is not None:
        state = "known"
    else:
        raise MmcifZeroOccupancyAtomDeclarationError(
            "invalid_marker_token",
            f"{field} must be a marker or bounded printable token",
            line_number=token.line_number,
        )
    return MmcifDeclarationMarker(state=state, value=token.value, quoted=bool(token.quoted))


def _require_zero(token: CifToken) -> None:
    if token.quoted or token.multiline:
        raise MmcifZeroOccupancyAtomDeclarationError(
            "occupancy_flag_not_numeric_zero",
            "occupancy_flag must be an unquoted exact numeric zero",
            line_number=token.line_number,
        )
    try:
        value = Decimal(token.value)
    except InvalidOperation:
        value = None
    if value is None or not value.is_finite() or value != Decimal(0):
        raise MmcifZeroOccupancyAtomDeclarationError(
            "occupancy_flag_not_numeric_zero",
            "occupancy_flag must be an exact numeric zero",
            line_number=token.line_number,
        )


def _semantic_indices(
    semantics: MmcifSemanticSnapshot,
) -> tuple[dict[str, str], dict[tuple[str, int], str], set[str]]:
    asym_to_entity = {row.asym_id: row.entity_id for row in semantics.asym_units}
    sequence = {
        (row.entity_id, row.sequence_number): row.monomer_id
        for row in semantics.polymer_sequence
    }
    polymer_entities = {row.entity_id for row in semantics.polymer_definitions}
    return asym_to_entity, sequence, polymer_entities


def parse_mmcif_zero_occupancy_atom_declarations(
    text: str,
) -> MmcifZeroOccupancyAtomSnapshot:
    """Parse and bind source declarations without interpreting atom-site rows."""

    if type(text) is not str:
        raise TypeError("zero-occupancy atom declaration input must be a string")
    semantics = parse_mmcif_semantics(text)
    block = parse_cif_block(text)
    loop, index = _loop(block)
    asym_to_entity, sequence, polymer_entities = _semantic_indices(semantics)

    declarations: list[MmcifZeroOccupancyAtomDeclaration] = []
    source_ids: set[int] = set()
    for ordinal, row in enumerate(loop.rows):
        source_id_token = row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[0]]]
        source_id = _positive_integer(source_id_token, field="id")
        if source_id in source_ids:
            raise MmcifZeroOccupancyAtomDeclarationError(
                "duplicate_declaration_id",
                "declaration identifiers must be unique",
                line_number=source_id_token.line_number,
            )
        source_ids.add(source_id)

        polymer_flag = _known_token(
            row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[1]]], field="polymer_flag"
        ).upper()
        if polymer_flag != "Y":
            raise MmcifZeroOccupancyAtomDeclarationError(
                "nonpolymer_declaration_not_supported",
                "this profile accepts only polymer_flag Y declarations",
                line_number=row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[1]]].line_number,
            )
        _require_zero(row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[2]]])
        model_number = _positive_integer(
            row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[3]]], field="pdb_model_num"
        )

        auth_asym_id = _known_token(
            row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[4]]], field="auth_asym_id"
        )
        auth_comp_id = _known_token(
            row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[5]]], field="auth_comp_id"
        )
        auth_seq_id = _known_token(
            row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[6]]], field="auth_seq_id"
        )
        insertion_code = _marker(
            row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[7]]], field="pdb_ins_code"
        )
        auth_atom_id = _known_token(
            row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[8]]], field="auth_atom_id"
        )
        label_alt_id = _marker(
            row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[9]]], field="label_alt_id"
        )
        label_asym_token = row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[10]]]
        label_asym_id = _known_token(label_asym_token, field="label_asym_id")
        label_comp_token = row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[11]]]
        label_comp_id = _known_token(label_comp_token, field="label_comp_id")
        label_seq_token = row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[12]]]
        label_seq_id = _positive_integer(label_seq_token, field="label_seq_id")
        label_atom_id = _known_token(
            row[index[MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS[13]]], field="label_atom_id"
        )

        entity_id = asym_to_entity.get(label_asym_id)
        if entity_id is None:
            raise MmcifZeroOccupancyAtomDeclarationError(
                "label_asym_reference_missing",
                "one declaration references an unknown label asym identifier",
                line_number=label_asym_token.line_number,
            )
        if entity_id not in polymer_entities:
            raise MmcifZeroOccupancyAtomDeclarationError(
                "label_asym_not_polymer",
                "one declaration references a non-polymer asym unit",
                line_number=label_asym_token.line_number,
            )
        expected_comp = sequence.get((entity_id, label_seq_id))
        if expected_comp is None:
            raise MmcifZeroOccupancyAtomDeclarationError(
                "label_sequence_reference_missing",
                "one declaration references an unknown polymer sequence position",
                line_number=label_seq_token.line_number,
            )
        if expected_comp != label_comp_id:
            raise MmcifZeroOccupancyAtomDeclarationError(
                "label_component_sequence_mismatch",
                "one declaration component disagrees with the bounded polymer sequence",
                line_number=label_comp_token.line_number,
            )

        declarations.append(
            MmcifZeroOccupancyAtomDeclaration(
                source_id=source_id,
                model_number=model_number,
                auth_asym_id=auth_asym_id,
                auth_comp_id=auth_comp_id,
                auth_seq_id=auth_seq_id,
                insertion_code=insertion_code,
                auth_atom_id=auth_atom_id,
                label_alt_id=label_alt_id,
                label_asym_id=label_asym_id,
                label_comp_id=label_comp_id,
                label_seq_id=label_seq_id,
                label_atom_id=label_atom_id,
                entity_id=entity_id,
                source_ordinal=ordinal,
            )
        )

    return MmcifZeroOccupancyAtomSnapshot(
        source_sha256=hashlib.sha256(text.encode("ascii")).hexdigest(),
        semantic_projection_sha256=semantics.semantic_projection_sha256,
        source_category_order=tuple(block.category_order),
        loop_headers=tuple(loop.tags),
        declarations=tuple(declarations),
    )


def zero_occupancy_atom_projection(
    snapshot: MmcifZeroOccupancyAtomSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ZERO_OCCUPANCY_ATOM_DECLARATION_SCHEMA_ID,
        "profile_id": MMCIF_ZERO_OCCUPANCY_ATOM_PROFILE_ID,
        "parser_version": MMCIF_ZERO_OCCUPANCY_ATOM_PARSER_VERSION,
        "semantic_projection_sha256": snapshot.semantic_projection_sha256,
        "declarations": [row.to_dict() for row in snapshot.declarations],
        "declaration_order": "source_order",
        "source_reported_zero_occupancy_atom_declarations_preserved": True,
        **_claim_policy(),
    }


def zero_occupancy_atom_source_binding(
    snapshot: MmcifZeroOccupancyAtomSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": "betelgeuze.engine_v2_mmcif_zero_occupancy_atom_source_binding/1.0.0",
        "source_sha256": snapshot.source_sha256,
        "source_category_order": list(snapshot.source_category_order),
        "loop_headers": list(snapshot.loop_headers),
        "row_count": len(snapshot.declarations),
    }


def zero_occupancy_atom_document(
    snapshot: MmcifZeroOccupancyAtomSnapshot,
) -> dict[str, Any]:
    projection = zero_occupancy_atom_projection(snapshot)
    source_binding = zero_occupancy_atom_source_binding(snapshot)
    return {
        "schema_id": MMCIF_ZERO_OCCUPANCY_ATOM_DOCUMENT_SCHEMA_ID,
        "declaration_projection_sha256": _sha256_document(projection),
        "source_binding_sha256": _sha256_document(source_binding),
        "snapshot_sha256": snapshot.snapshot_sha256,
        "declaration_projection": projection,
        "source_binding": source_binding,
        "claim_policy": _claim_policy(),
    }


def require_zero_occupancy_atom_document(document: Any) -> Mapping[str, Any]:
    if not isinstance(document, Mapping):
        raise ValueError("zero-occupancy atom document must be a mapping")
    payload = dict(document)
    if payload.get("schema_id") != MMCIF_ZERO_OCCUPANCY_ATOM_DOCUMENT_SCHEMA_ID:
        raise ValueError("zero-occupancy atom document schema mismatch")
    projection = payload.get("declaration_projection")
    source_binding = payload.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(source_binding, Mapping):
        raise ValueError("zero-occupancy atom document payloads must be mappings")
    projection_sha = _sha256_document(dict(projection))
    source_sha = _sha256_document(dict(source_binding))
    if payload.get("declaration_projection_sha256") != projection_sha:
        raise ValueError("zero-occupancy atom projection digest mismatch")
    if payload.get("source_binding_sha256") != source_sha:
        raise ValueError("zero-occupancy atom source binding digest mismatch")
    expected_snapshot_sha = _sha256_document(
        {
            "schema_id": MMCIF_ZERO_OCCUPANCY_ATOM_DOCUMENT_SCHEMA_ID,
            "declaration_projection_sha256": projection_sha,
            "source_binding_sha256": source_sha,
            "claim_policy": _claim_policy(),
        }
    )
    if payload.get("snapshot_sha256") != expected_snapshot_sha:
        raise ValueError("zero-occupancy atom snapshot digest mismatch")
    if payload.get("claim_policy") != _claim_policy():
        raise ValueError("zero-occupancy atom claim policy mismatch")
    return MappingProxyType(payload)


def zero_occupancy_atom_json_bytes(snapshot: MmcifZeroOccupancyAtomSnapshot) -> bytes:
    return _canonical_json_bytes(zero_occupancy_atom_document(snapshot))


def write_zero_occupancy_atom_json(
    path: str | Path,
    snapshot: MmcifZeroOccupancyAtomSnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = zero_occupancy_atom_json_bytes(snapshot) + b"\n"
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
    "MAX_MMCIF_ZERO_OCCUPANCY_ATOM_ROWS",
    "MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS",
    "MMCIF_ZERO_OCCUPANCY_ATOM_DECLARATION_SCHEMA_ID",
    "MMCIF_ZERO_OCCUPANCY_ATOM_DOCUMENT_SCHEMA_ID",
    "MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS",
    "MMCIF_ZERO_OCCUPANCY_ATOM_PARSER_VERSION",
    "MMCIF_ZERO_OCCUPANCY_ATOM_PROFILE_ID",
    "MmcifDeclarationMarker",
    "MmcifZeroOccupancyAtomDeclaration",
    "MmcifZeroOccupancyAtomDeclarationError",
    "MmcifZeroOccupancyAtomSnapshot",
    "parse_mmcif_zero_occupancy_atom_declarations",
    "require_zero_occupancy_atom_document",
    "write_zero_occupancy_atom_json",
    "zero_occupancy_atom_document",
    "zero_occupancy_atom_json_bytes",
    "zero_occupancy_atom_projection",
    "zero_occupancy_atom_source_binding",
]
