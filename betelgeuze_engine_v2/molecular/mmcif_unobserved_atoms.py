"""Opt-in mmCIF source-reported unobserved-atom envelope.

The base mmCIF parser/writer and polymer-sequence envelope remain unchanged.
This module composes an existing polymer carrier with one exact
``_pdbx_unobs_or_zero_occ_atoms`` loop, reuses the base parser's preserve-only
atom-claim state, and emits the selected source claims deterministically.

The result proves only that selected source-reported atom claims survive a
semantic round trip.  It does not establish that an atom is actually missing,
that a residue template is complete, or that the system is prepared.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping

from .missingness import SourceReportedMissingnessReport
from .mmcif_polymer_sequence import (
    MAX_MMCIF_POLYMER_SEQUENCE_ROWS,
    MMCIF_ENTITY_POLY_SEQ_HEADERS,
    MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
    MmcifPolymerSequenceError,
    MmcifPolymerSequenceIngestResult,
    emit_mmcif_polymer_sequence,
    parse_mmcif_polymer_sequence,
)
from .mmcif_syntax import CifBlock, CifLoop, CifSyntaxError, CifToken, parse_cif_block
from .mmcif_writer import MMCIF_WRITER_VERSION
from .pdb_mmcif import MMCIF_PARSER_VERSION, StructureParseError, parse_mmcif
from .serialization import deserialize_all_atom_system, serialize_all_atom_system
from .topology import canonical_topology_sha256


MMCIF_UNOBSERVED_ATOM_ENVELOPE_VERSION = "1.0.0"
MMCIF_UNOBSERVED_ATOM_PARSER_VERSION = "1.0.0"
MMCIF_UNOBSERVED_ATOM_WRITER_VERSION = "1.0.0"
MMCIF_UNOBSERVED_ATOM_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular.mmcif_unobserved_atoms"
)
MMCIF_UNOBSERVED_ATOM_PROFILE_ID = (
    "strict_mmcif_source_reported_unobserved_atom_envelope/1.0.0"
)
MMCIF_UNOBSERVED_ATOM_PROJECTION_SCOPE = (
    "source_reported_unobserved_polymer_atom_claims_only"
)
MMCIF_UNOBSERVED_ATOM_PROJECTION_SCHEMA_ID = (
    "betelgeuze.mmcif_unobserved_atom_projection/1.0.0"
)
MMCIF_UNOBSERVED_ATOM_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.mmcif_unobserved_atom_source_binding/1.0.0"
)
MMCIF_UNOBSERVED_ATOM_RECORD_STATE_SCHEMA_ID = (
    "betelgeuze.mmcif_unobserved_atom_record_state/1.0.0"
)
MMCIF_UNOBSERVED_ATOM_WRITE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.mmcif_unobserved_atom_write_receipt/1.0.0"
)
MMCIF_UNOBSERVED_ATOM_ROUND_TRIP_REPORT_SCHEMA_ID = (
    "betelgeuze.mmcif_unobserved_atom_round_trip_report/1.0.0"
)

MAX_MMCIF_UNOBSERVED_ATOM_INPUT_BYTES = 64 * 1024 * 1024
# The unchanged base parser preserves at most 40,000 missingness items.  The
# exact atom loop has 14 tokens per row, so 2,857 is the largest admitted row
# count whose complete source payload can reach the base parser.
MAX_MMCIF_UNOBSERVED_ATOM_ROWS = 40_000 // 14
MAX_MMCIF_UNOBSERVED_ATOM_SOURCE_ID_BYTES = 4_096
MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS = 256

MMCIF_UNOBSERVED_ATOM_HEADERS = (
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

_ENTITY_HEADERS = ("_entity.id", "_entity.type")
_STRUCT_ASYM_HEADERS = ("_struct_asym.id", "_struct_asym.entity_id")
_COMMON_CORE21_ATOM_SITE_HEADERS = (
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
_UNOBSERVED_CATEGORY = "_pdbx_unobs_or_zero_occ_atoms"
_RESIDUE_UNOBSERVED_CATEGORY = "_pdbx_unobs_or_zero_occ_residues"
_POLYMER_CATEGORIES = frozenset(
    {"_entity", "_struct_asym", "_entity_poly_seq", _UNOBSERVED_CATEGORY, "_atom_site"}
)
_COMPOSED_CATEGORIES = frozenset(
    {
        "_entity",
        "_struct_asym",
        "_entity_poly_seq",
        "_pdbx_entity_nonpoly",
        "_pdbx_nonpoly_scheme",
        _UNOBSERVED_CATEGORY,
        "_atom_site",
    }
)
_CARRIER_DROP_FOR_MISSINGNESS = frozenset(
    {"_entity_poly_seq", "_pdbx_entity_nonpoly", "_pdbx_nonpoly_scheme"}
)
_CANONICAL_ORDER = (
    "_entity",
    "_struct_asym",
    "_entity_poly_seq",
    "_pdbx_entity_nonpoly",
    "_pdbx_nonpoly_scheme",
    _UNOBSERVED_CATEGORY,
    "_atom_site",
)
_POSITIVE_INTEGER_RE = re.compile(r"^[1-9][0-9]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FACTORY_TOKEN = object()
_MAX_SOURCE_ROW_ID = (1 << 53) - 1

_FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "reference_sequence_equivalence_assessed",
    "coordinate_observation_completeness_assessed",
    "missing_atom_fact_claimed",
    "sequence_completeness_claimed",
    "modeled_atom_presence_assessed",
    "residue_template_consulted",
    "atom_name_dictionary_validated",
    "completion_attempted",
    "completion_applied",
    "modified_residue_identity_assessed",
    "polymer_chemistry_interpreted",
    "microheterogeneity_interpreted",
    "chemistry_interpreted",
    "role_assignment_interpreted",
    "bond_topology_interpreted",
    "bond_order_interpreted",
    "coordination_interpreted",
    "charge_interpreted",
    "protonation_interpreted",
    "preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "runtime_eligible",
    "simulation_ready",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)


class MmcifUnobservedAtomError(ValueError):
    """Stable fail-closed error that does not include source identity values."""

    def __init__(
        self, code: str, message: str, *, line_number: int | None = None
    ) -> None:
        self.code = str(code)
        self.detail = str(message)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"mmcif_unobserved_atom:{self.code}{suffix}: {self.detail}")


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_document(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_canonical_json_document(
    payload: bytes,
    *,
    code: str,
    label: str,
) -> dict[str, Any]:
    if type(payload) is not bytes:
        raise MmcifUnobservedAtomError(
            code, f"{label} must be stored as canonical JSON bytes"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        document: dict[str, Any] = {}
        for key, value in pairs:
            if key in document:
                raise ValueError("duplicate JSON key")
            document[key] = value
        return document

    def reject_nonfinite_constant(_: str) -> None:
        raise ValueError("non-finite JSON constant")

    try:
        value = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite_constant,
        )
        if type(value) is not dict:
            raise TypeError("JSON evidence must be an object")
        canonical = _canonical_json_bytes(value)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
        OverflowError,
    ):
        raise MmcifUnobservedAtomError(
            code, f"{label} is not canonical JSON object evidence"
        ) from None
    if payload != canonical:
        raise MmcifUnobservedAtomError(code, f"{label} must use canonical JSON bytes")
    return value


def _authority_false_document() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _bounded_bare_token(token: CifToken, *, allow_missing: bool = False) -> str:
    value = token.value
    if (
        token.quoted
        or token.multiline
        or not value
        or (not allow_missing and value in {".", "?"})
        or len(value) > MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise MmcifUnobservedAtomError(
            "invalid_identity_token",
            "selected identity fields must be bounded bare ASCII tokens",
            line_number=token.line_number,
        )
    return value


def _validate_stored_token(value: Any, *, allow_missing: bool = False) -> str:
    if (
        type(value) is not str
        or not value
        or (not allow_missing and value in {".", "?"})
        or len(value) > MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise TypeError("unobserved-atom identity values must be bounded ASCII tokens")
    return value


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifUnobservedAtomRow:
    source_id: int
    auth_asym_id: str
    auth_comp_id: str
    auth_seq_id: str
    pdb_ins_code: str
    auth_atom_id: str
    label_alt_id: str
    label_asym_id: str
    label_comp_id: str
    label_seq_id: int
    label_atom_id: str
    entity_id: str

    def __init__(
        self,
        *,
        source_id: int | None = None,
        auth_asym_id: str | None = None,
        auth_comp_id: str | None = None,
        auth_seq_id: str | None = None,
        pdb_ins_code: str | None = None,
        auth_atom_id: str | None = None,
        label_alt_id: str | None = None,
        label_asym_id: str | None = None,
        label_comp_id: str | None = None,
        label_seq_id: int | None = None,
        label_atom_id: str | None = None,
        entity_id: str | None = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifUnobservedAtomRow is factory-only")
        for name, value in (
            ("source_id", source_id),
            ("auth_asym_id", auth_asym_id),
            ("auth_comp_id", auth_comp_id),
            ("auth_seq_id", auth_seq_id),
            ("pdb_ins_code", pdb_ins_code),
            ("auth_atom_id", auth_atom_id),
            ("label_alt_id", label_alt_id),
            ("label_asym_id", label_asym_id),
            ("label_comp_id", label_comp_id),
            ("label_seq_id", label_seq_id),
            ("label_atom_id", label_atom_id),
            ("entity_id", entity_id),
        ):
            object.__setattr__(self, name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        if (
            type(self.source_id) is not int
            or not 1 <= self.source_id <= _MAX_SOURCE_ROW_ID
        ):
            raise TypeError("source_id must be within the row domain")
        if (
            type(self.label_seq_id) is not int
            or not 1 <= self.label_seq_id <= MAX_MMCIF_POLYMER_SEQUENCE_ROWS
        ):
            raise TypeError("label_seq_id must be within the row domain")
        for name in (
            "auth_asym_id",
            "auth_comp_id",
            "auth_seq_id",
            "auth_atom_id",
            "label_asym_id",
            "label_comp_id",
            "label_atom_id",
            "entity_id",
        ):
            _validate_stored_token(getattr(self, name))
        _validate_stored_token(self.pdb_ins_code, allow_missing=True)
        _validate_stored_token(self.label_alt_id, allow_missing=True)
        if self.label_alt_id not in {".", "?"}:
            raise TypeError("label_alt_id must be an exact missing-value marker")

    def __repr__(self) -> str:
        return "MmcifUnobservedAtomRow(<source-reported-identity>)"


def _row_document(row: MmcifUnobservedAtomRow, *, ordinal: int) -> dict[str, Any]:
    return {
        "ordinal": ordinal,
        "source_id": row.source_id,
        "polymer_flag": "Y",
        "occupancy_flag": 1,
        "pdb_model_num": 1,
        "auth_asym_id": row.auth_asym_id,
        "auth_comp_id": row.auth_comp_id,
        "auth_seq_id": row.auth_seq_id,
        "pdb_ins_code": row.pdb_ins_code,
        "auth_atom_id": row.auth_atom_id,
        "label_alt_id": row.label_alt_id,
        "label_asym_id": row.label_asym_id,
        "label_comp_id": row.label_comp_id,
        "label_seq_id": row.label_seq_id,
        "label_atom_id": row.label_atom_id,
        "entity_id": row.entity_id,
    }


def _projection_document(rows: tuple[MmcifUnobservedAtomRow, ...]) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_UNOBSERVED_ATOM_PROJECTION_SCHEMA_ID,
        "envelope_version": MMCIF_UNOBSERVED_ATOM_ENVELOPE_VERSION,
        "parser_version": MMCIF_UNOBSERVED_ATOM_PARSER_VERSION,
        "profile_id": MMCIF_UNOBSERVED_ATOM_PROFILE_ID,
        "headers": list(MMCIF_UNOBSERVED_ATOM_HEADERS),
        "row_order": "source_order",
        "rows": [_row_document(row, ordinal=index) for index, row in enumerate(rows)],
        "semantics": MMCIF_UNOBSERVED_ATOM_PROJECTION_SCOPE,
        "actual_missing_atom_fact_established": False,
        "residue_template_consulted": False,
        "atom_name_dictionary_validated": False,
    }


def _projection_sha256(rows: tuple[MmcifUnobservedAtomRow, ...]) -> str:
    return _sha256_document(_projection_document(rows))


def _loop_for(block: CifBlock, category: str) -> CifLoop:
    scalar = [tag for tag in block.scalar_values if tag.split(".", 1)[0] == category]
    loops = [loop for loop in block.loops if category in loop.categories]
    if scalar or len(loops) != 1 or loops[0].categories != (category,):
        raise MmcifUnobservedAtomError(
            "unsupported_category_representation",
            "every selected category must be exactly one category-local loop",
        )
    return loops[0]


def _require_headers(loop: CifLoop, expected: tuple[str, ...]) -> None:
    if loop.tags != expected:
        raise MmcifUnobservedAtomError(
            "unsupported_category_headers",
            "selected category headers are outside the exact envelope",
            line_number=loop.line_number,
        )


def _token_text(token: CifToken) -> str:
    if token.multiline:
        raise MmcifUnobservedAtomError(
            "unsupported_multiline_token",
            "multiline carrier values are outside the exact envelope",
            line_number=token.line_number,
        )
    if not token.quoted:
        return token.value
    if "'" not in token.value:
        return f"'{token.value}'"
    if '"' not in token.value:
        return f'"{token.value}"'
    raise MmcifUnobservedAtomError(
        "unsupported_quoted_token",
        "quoted carrier value has no canonical single-line representation",
        line_number=token.line_number,
    )


def _emit_loop(loop: CifLoop) -> bytes:
    lines = ["loop_", *loop.tags]
    for row in loop.rows:
        tokens = [_token_text(token) for token in row]
        joined = " ".join(tokens)
        lines.extend((joined,) if len(joined) <= 2_048 else tokens)
    lines.append("#")
    return ("\n".join(lines) + "\n").encode("ascii")


def _emit_selected_categories(block: CifBlock, *, drop: frozenset[str]) -> bytes:
    parts = [f"data_{block.name}\n#\n".encode("ascii")]
    for category in block.categories:
        if category in drop:
            continue
        parts.append(_emit_loop(_loop_for(block, category)))
    payload = b"".join(parts)
    if len(payload) > MAX_MMCIF_UNOBSERVED_ATOM_INPUT_BYTES:
        raise MmcifUnobservedAtomError(
            "carrier_too_large", "normalized carrier exceeds the fixed byte cap"
        )
    return payload


def _parse_block(data: bytes) -> CifBlock:
    try:
        return parse_cif_block(data.decode("ascii"))
    except (UnicodeDecodeError, CifSyntaxError):
        raise MmcifUnobservedAtomError(
            "invalid_cif_syntax", "input failed exact ASCII CIF syntax validation"
        ) from None


@dataclass(frozen=True, slots=True)
class _ParsedEnvelope:
    full_source: bytes
    carrier_source: bytes
    canonical_carrier_source: bytes
    missingness_source: bytes
    source_id: str
    polymer_ingest: MmcifPolymerSequenceIngestResult
    missingness_ingest: Any
    rows: tuple[MmcifUnobservedAtomRow, ...]


def _parse_components(data: bytes, *, source_id: str) -> _ParsedEnvelope:
    if type(data) is not bytes:
        raise TypeError("mmCIF unobserved-atom input must be bytes")
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    try:
        encoded_source_id = source_id.encode("utf-8")
    except UnicodeEncodeError:
        raise MmcifUnobservedAtomError(
            "invalid_source_id", "source_id must contain only Unicode scalar values"
        ) from None
    if len(encoded_source_id) > MAX_MMCIF_UNOBSERVED_ATOM_SOURCE_ID_BYTES:
        raise MmcifUnobservedAtomError(
            "source_id_too_large", "source_id exceeds the fixed 4096-byte UTF-8 cap"
        )
    if not data:
        raise MmcifUnobservedAtomError("empty_input", "input is empty")
    if len(data) > MAX_MMCIF_UNOBSERVED_ATOM_INPUT_BYTES:
        raise MmcifUnobservedAtomError(
            "input_too_large", "input exceeds the fixed byte cap"
        )
    if not data.isascii():
        raise MmcifUnobservedAtomError(
            "non_ascii_input", "the exact envelope requires ASCII"
        )
    block = _parse_block(data)
    categories = frozenset(block.categories)
    if _RESIDUE_UNOBSERVED_CATEGORY in categories:
        raise MmcifUnobservedAtomError(
            "mixed_residue_missingness_unsupported",
            "v1 accepts an atom-claim loop without a residue-claim loop",
        )
    if categories == _POLYMER_CATEGORIES:
        expected_loop_count = 5
    elif categories == _COMPOSED_CATEGORIES:
        expected_loop_count = 7
    else:
        raise MmcifUnobservedAtomError(
            "unsupported_category_surface",
            "input categories are outside the exact polymer or composed envelope",
        )
    if block.scalar_values or len(block.loops) != expected_loop_count:
        raise MmcifUnobservedAtomError(
            "unsupported_category_representation",
            "the envelope requires one loop per category and no scalar items",
        )
    entity_loop = _loop_for(block, "_entity")
    asym_loop = _loop_for(block, "_struct_asym")
    sequence_loop = _loop_for(block, "_entity_poly_seq")
    unobserved_loop = _loop_for(block, _UNOBSERVED_CATEGORY)
    atom_loop = _loop_for(block, "_atom_site")
    _require_headers(entity_loop, _ENTITY_HEADERS)
    _require_headers(asym_loop, _STRUCT_ASYM_HEADERS)
    _require_headers(sequence_loop, MMCIF_ENTITY_POLY_SEQ_HEADERS)
    _require_headers(unobserved_loop, MMCIF_UNOBSERVED_ATOM_HEADERS)
    _require_headers(atom_loop, _COMMON_CORE21_ATOM_SITE_HEADERS)
    if not unobserved_loop.rows:
        raise MmcifUnobservedAtomError(
            "empty_unobserved_atom_loop",
            "the selected loop must contain at least one row",
        )
    if len(unobserved_loop.rows) > MAX_MMCIF_UNOBSERVED_ATOM_ROWS:
        raise MmcifUnobservedAtomError(
            "too_many_unobserved_atom_rows", "row count exceeds the fixed cap"
        )

    entity_types: dict[str, str] = {}
    for row in entity_loop.rows:
        entity_id = _bounded_bare_token(row[0])
        entity_type = _bounded_bare_token(row[1])
        if entity_id in entity_types:
            raise MmcifUnobservedAtomError(
                "duplicate_entity_id", "entity IDs must be unique"
            )
        entity_types[entity_id] = entity_type
    asym_to_entity: dict[str, str] = {}
    for row in asym_loop.rows:
        asym_id = _bounded_bare_token(row[0])
        entity_id = _bounded_bare_token(row[1])
        if asym_id in asym_to_entity or entity_id not in entity_types:
            raise MmcifUnobservedAtomError(
                "invalid_struct_asym_join",
                "struct-asym rows must uniquely join declared entities",
            )
        asym_to_entity[asym_id] = entity_id

    membership: set[tuple[str, int, str]] = set()
    for row in sequence_loop.rows:
        entity_id = _bounded_bare_token(row[0])
        if (
            not _POSITIVE_INTEGER_RE.fullmatch(row[1].value)
            or row[1].quoted
            or row[1].multiline
        ):
            raise MmcifUnobservedAtomError(
                "invalid_sequence_membership",
                "sequence positions must be canonical positive integers",
            )
        mon_id = _bounded_bare_token(row[2])
        membership.add((entity_id, int(row[1].value, 10), mon_id))

    def semantic_marker(token: CifToken) -> str:
        value = _bounded_bare_token(token, allow_missing=True)
        return "" if value in {".", "?"} else value

    coordinate_residues = {
        (
            1,
            _bounded_bare_token(row[6]),
            int(row[8].value, 10),
            _bounded_bare_token(row[5]),
            semantic_marker(row[9]),
        )
        for row in atom_loop.rows
        if _POSITIVE_INTEGER_RE.fullmatch(row[8].value)
        and not row[8].quoted
        and not row[8].multiline
        and row[20].value == "1"
        and not row[20].quoted
        and not row[20].multiline
    }
    coordinate_atoms = {
        (
            1,
            _bounded_bare_token(row[6]),
            int(row[8].value, 10),
            _bounded_bare_token(row[5]),
            semantic_marker(row[9]),
            _bounded_bare_token(row[3]),
            semantic_marker(row[4]),
        )
        for row in atom_loop.rows
        if _POSITIVE_INTEGER_RE.fullmatch(row[8].value)
        and not row[8].quoted
        and not row[8].multiline
        and row[20].value == "1"
        and not row[20].quoted
        and not row[20].multiline
    }
    seen_ids: set[int] = set()
    seen_semantic: set[tuple[int, str, int, str, str, str, str]] = set()
    parsed_rows: list[MmcifUnobservedAtomRow] = []
    for tokens in unobserved_loop.rows:
        if any(token.quoted or token.multiline for token in tokens):
            raise MmcifUnobservedAtomError(
                "invalid_unobserved_atom_token",
                "v1 requires bare source-reported atom tokens",
                line_number=tokens[0].line_number,
            )
        if not _POSITIVE_INTEGER_RE.fullmatch(tokens[0].value):
            raise MmcifUnobservedAtomError(
                "invalid_source_id",
                "source row IDs must be canonical positive integers",
            )
        row_id = int(tokens[0].value, 10)
        if row_id > _MAX_SOURCE_ROW_ID or row_id in seen_ids:
            raise MmcifUnobservedAtomError(
                "duplicate_or_invalid_unobserved_atom_id",
                "source row IDs must be bounded and unique",
            )
        seen_ids.add(row_id)
        if tokens[1].value != "Y":
            raise MmcifUnobservedAtomError(
                "unsupported_unobserved_atom_polymer_flag",
                "v1 accepts only exact polymer_flag Y",
            )
        if tokens[2].value != "1":
            raise MmcifUnobservedAtomError(
                "unsupported_unobserved_atom_occupancy_flag",
                "v1 accepts only exact unobserved occupancy_flag 1",
            )
        if tokens[3].value != "1":
            raise MmcifUnobservedAtomError(
                "unsupported_unobserved_atom_model", "v1 accepts only exact model 1"
            )
        auth_asym = _bounded_bare_token(tokens[4])
        auth_comp = _bounded_bare_token(tokens[5])
        auth_seq = _bounded_bare_token(tokens[6])
        ins_code = _bounded_bare_token(tokens[7], allow_missing=True)
        auth_atom = _bounded_bare_token(tokens[8])
        label_alt = _bounded_bare_token(tokens[9], allow_missing=True)
        if label_alt not in {".", "?"}:
            raise MmcifUnobservedAtomError(
                "unsupported_unobserved_atom_altloc",
                "v1 accepts only exact dot or question-mark label_alt_id markers",
            )
        label_asym = _bounded_bare_token(tokens[10])
        label_comp = _bounded_bare_token(tokens[11])
        if not _POSITIVE_INTEGER_RE.fullmatch(tokens[12].value):
            raise MmcifUnobservedAtomError(
                "invalid_label_seq_id",
                "label sequence IDs must be canonical positive integers",
            )
        label_seq = int(tokens[12].value, 10)
        if label_seq > MAX_MMCIF_POLYMER_SEQUENCE_ROWS:
            raise MmcifUnobservedAtomError(
                "invalid_label_seq_id", "label sequence ID exceeds the fixed row domain"
            )
        label_atom = _bounded_bare_token(tokens[13])
        entity_id = asym_to_entity.get(label_asym)
        if entity_id is None:
            raise MmcifUnobservedAtomError(
                "unknown_unobserved_atom_asym_id",
                "unobserved label asym does not join struct-asym",
            )
        if entity_types.get(entity_id) != "polymer":
            raise MmcifUnobservedAtomError(
                "unobserved_atom_nonpolymer_entity",
                "selected claims may reference only polymer entities",
            )
        if (entity_id, label_seq, label_comp) not in membership:
            raise MmcifUnobservedAtomError(
                "unobserved_atom_sequence_join_mismatch",
                "selected claim does not join the polymer sequence membership",
            )
        normalized_ins_code = "" if ins_code in {".", "?"} else ins_code
        normalized_label_alt = ""
        residue_key = (
            1,
            label_asym,
            label_seq,
            label_comp,
            normalized_ins_code,
        )
        if residue_key not in coordinate_residues:
            raise MmcifUnobservedAtomError(
                "unobserved_atom_residue_absent",
                "selected atom claims require their polymer residue in coordinates",
            )
        semantic_key = (*residue_key, label_atom, normalized_label_alt)
        if semantic_key in seen_semantic:
            raise MmcifUnobservedAtomError(
                "duplicate_unobserved_atom_identity",
                "semantic atom identities must be unique",
            )
        seen_semantic.add(semantic_key)
        if semantic_key in coordinate_atoms:
            raise MmcifUnobservedAtomError(
                "unobserved_atom_present_in_coordinates",
                "an unobserved-atom claim conflicts with a selected coordinate atom",
            )
        parsed_rows.append(
            MmcifUnobservedAtomRow(
                source_id=row_id,
                auth_asym_id=auth_asym,
                auth_comp_id=auth_comp,
                auth_seq_id=auth_seq,
                pdb_ins_code=ins_code,
                auth_atom_id=auth_atom,
                label_alt_id=label_alt,
                label_asym_id=label_asym,
                label_comp_id=label_comp,
                label_seq_id=label_seq,
                label_atom_id=label_atom,
                entity_id=entity_id,
                _factory_token=_FACTORY_TOKEN,
            )
        )

    carrier_source = _emit_selected_categories(
        block, drop=frozenset({_UNOBSERVED_CATEGORY})
    )
    missingness_source = _emit_selected_categories(
        block, drop=_CARRIER_DROP_FOR_MISSINGNESS
    )
    try:
        polymer_ingest = parse_mmcif_polymer_sequence(
            carrier_source, source_id=source_id
        )
        canonical_carrier_source = emit_mmcif_polymer_sequence(polymer_ingest).payload
    except (MmcifPolymerSequenceError, TypeError, ValueError, OverflowError):
        raise MmcifUnobservedAtomError(
            "invalid_polymer_carrier",
            "the selected polymer carrier failed its existing contract",
        ) from None
    try:
        missingness_ingest = parse_mmcif(missingness_source, source_id=source_id)
    except (StructureParseError, TypeError, ValueError, OverflowError):
        raise MmcifUnobservedAtomError(
            "invalid_missingness_carrier",
            "the selected source missingness failed its existing contract",
        ) from None
    if canonical_topology_sha256(polymer_ingest.system) != canonical_topology_sha256(
        missingness_ingest.system
    ):
        raise MmcifUnobservedAtomError(
            "carrier_topology_mismatch",
            "polymer and missingness carrier topologies differ",
        )
    report = missingness_ingest.missingness_evidence
    if (
        type(report) is not SourceReportedMissingnessReport
        or report.source_reported_missing_residue_count != 0
        or report.source_reported_missing_atom_count != len(parsed_rows)
    ):
        raise MmcifUnobservedAtomError(
            "missingness_report_mismatch",
            "existing preserve-only report does not match selected rows",
        )
    for ordinal, (row, claim) in enumerate(
        zip(parsed_rows, report.missing_atom_claims, strict=True), start=1
    ):
        expected_values = (
            str(row.source_id),
            "Y",
            "1",
            "1",
            row.auth_asym_id,
            row.auth_comp_id,
            row.auth_seq_id,
            row.pdb_ins_code,
            row.auth_atom_id,
            row.label_alt_id,
            row.label_asym_id,
            row.label_comp_id,
            str(row.label_seq_id),
            row.label_atom_id,
        )
        raw_payload = claim.raw_payload
        raw_tokens = raw_payload.get("tokens")
        expected_tokens = {
            header: {"value": value, "quoted": False, "multiline": False}
            for header, value in zip(
                MMCIF_UNOBSERVED_ATOM_HEADERS, expected_values, strict=True
            )
        }
        expected_insertion = "" if row.pdb_ins_code in {".", "?"} else row.pdb_ins_code
        expected_altloc = ""
        if not all(
            (
                claim.source_ordinal == ordinal,
                claim.source_category == _UNOBSERVED_CATEGORY,
                claim.source_model_id == "1",
                claim.source_chain_id == row.label_asym_id,
                claim.source_residue_id == str(row.label_seq_id),
                claim.source_residue_name == row.label_comp_id,
                claim.source_insertion_code == expected_insertion,
                claim.source_atom_name == row.label_atom_id,
                claim.source_altloc_id == expected_altloc,
                raw_payload.get("source_row_id") == row.source_id,
                type(raw_payload.get("source_line_number")) is int,
                raw_payload.get("polymer_flag") == "Y",
                raw_payload.get("occupancy_flag") == 1,
                raw_payload.get("identity_basis") == "label",
                raw_tokens == expected_tokens,
            )
        ):
            raise MmcifUnobservedAtomError(
                "missingness_report_mismatch",
                "existing preserve-only atom claims differ from selected rows",
            )
    return _ParsedEnvelope(
        full_source=data,
        carrier_source=carrier_source,
        canonical_carrier_source=canonical_carrier_source,
        missingness_source=missingness_source,
        source_id=source_id,
        polymer_ingest=polymer_ingest,
        missingness_ingest=missingness_ingest,
        rows=tuple(parsed_rows),
    )


def _record_state_document(
    *,
    polymer_record_state_sha256: str,
    polymer_projection_sha256: str,
    nonpoly_record_state_sha256: str | None,
    topology_sha256: str,
    projection_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_UNOBSERVED_ATOM_RECORD_STATE_SCHEMA_ID,
        "envelope_version": MMCIF_UNOBSERVED_ATOM_ENVELOPE_VERSION,
        "parser_version": MMCIF_UNOBSERVED_ATOM_PARSER_VERSION,
        "writer_version": MMCIF_UNOBSERVED_ATOM_WRITER_VERSION,
        "profile_id": MMCIF_UNOBSERVED_ATOM_PROFILE_ID,
        "base_parser_version": MMCIF_PARSER_VERSION,
        "base_writer_version": MMCIF_WRITER_VERSION,
        "polymer_envelope_version": MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
        "polymer_record_state_sha256": polymer_record_state_sha256,
        "polymer_projection_sha256": polymer_projection_sha256,
        "nonpoly_record_state_sha256": nonpoly_record_state_sha256,
        "canonical_topology_sha256": topology_sha256,
        "unobserved_atom_projection_sha256": projection_sha256,
        "missingness_semantics": MMCIF_UNOBSERVED_ATOM_PROJECTION_SCOPE,
    }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifUnobservedAtomIngestResult:
    full_source_sha256: str
    carrier_source_sha256: str
    canonical_carrier_source_sha256: str
    source_id_sha256: str
    unobserved_atom_projection_sha256: str
    record_state_sha256: str
    source_binding_sha256: str
    topology_sha256: str
    system_snapshot_sha256: str
    missingness_report_sha256: str
    polymer_record_state_sha256: str
    polymer_projection_sha256: str
    nonpoly_projection_sha256: str | None
    nonpoly_record_state_sha256: str | None
    unobserved_atom_rows: tuple[MmcifUnobservedAtomRow, ...]
    _full_source: bytes
    _source_id: str
    _carrier_source_bytes: bytes
    _missingness_source_bytes: bytes
    _system_snapshot_payload: bytes

    def __init__(
        self, components: _ParsedEnvelope, *, _factory_token: object | None = None
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifUnobservedAtomIngestResult is factory-only")
        system = components.missingness_ingest.system
        snapshot = serialize_all_atom_system(system)
        snapshot_sha = _sha256_bytes(snapshot)
        topology_sha = canonical_topology_sha256(system)
        projection_sha = _projection_sha256(components.rows)
        polymer = components.polymer_ingest
        nonpoly_state = polymer.nonpoly_identity_record_state_sha256
        report_sha = components.missingness_ingest.missingness_evidence.report_sha256
        record_document = _record_state_document(
            polymer_record_state_sha256=polymer.record_state_sha256,
            polymer_projection_sha256=polymer.polymer_sequence_projection_sha256,
            nonpoly_record_state_sha256=nonpoly_state,
            topology_sha256=topology_sha,
            projection_sha256=projection_sha,
        )
        record_sha = _sha256_document(record_document)
        full_sha = _sha256_bytes(components.full_source)
        carrier_sha = _sha256_bytes(components.carrier_source)
        canonical_carrier_sha = _sha256_bytes(components.canonical_carrier_source)
        source_id_sha = _sha256_bytes(components.source_id.encode("utf-8"))
        binding_sha = _sha256_document(
            {
                "schema_id": MMCIF_UNOBSERVED_ATOM_SOURCE_BINDING_SCHEMA_ID,
                "profile_id": MMCIF_UNOBSERVED_ATOM_PROFILE_ID,
                "full_source_sha256": full_sha,
                "carrier_source_sha256": carrier_sha,
                "canonical_carrier_source_sha256": canonical_carrier_sha,
                "source_id_sha256": source_id_sha,
                "record_state_sha256": record_sha,
                "source_missingness_report_sha256": report_sha,
                "system_snapshot_sha256": snapshot_sha,
            }
        )
        values = {
            "full_source_sha256": full_sha,
            "carrier_source_sha256": carrier_sha,
            "canonical_carrier_source_sha256": canonical_carrier_sha,
            "source_id_sha256": source_id_sha,
            "unobserved_atom_projection_sha256": projection_sha,
            "record_state_sha256": record_sha,
            "source_binding_sha256": binding_sha,
            "topology_sha256": topology_sha,
            "system_snapshot_sha256": snapshot_sha,
            "missingness_report_sha256": report_sha,
            "polymer_record_state_sha256": polymer.record_state_sha256,
            "polymer_projection_sha256": polymer.polymer_sequence_projection_sha256,
            "nonpoly_projection_sha256": (polymer.nonpoly_identity_projection_sha256),
            "nonpoly_record_state_sha256": nonpoly_state,
            "unobserved_atom_rows": components.rows,
            "_full_source": components.full_source,
            "_source_id": components.source_id,
            "_carrier_source_bytes": components.carrier_source,
            "_missingness_source_bytes": components.missingness_source,
            "_system_snapshot_payload": snapshot,
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def __repr__(self) -> str:
        return "MmcifUnobservedAtomIngestResult(<source-bound-evidence>)"

    @property
    def carrier_kind(self) -> str:
        return (
            "mmcif_polymer_sequence_nonpoly_identity"
            if self.has_nonpoly_identity
            else "mmcif_polymer_sequence"
        )

    @property
    def has_nonpoly_identity(self) -> bool:
        return self.nonpoly_record_state_sha256 is not None

    @property
    def system(self) -> Any:
        return deserialize_all_atom_system(self._system_snapshot_payload)

    @property
    def polymer_ingest(self) -> MmcifPolymerSequenceIngestResult:
        return parse_mmcif_polymer_sequence(
            self._carrier_source_bytes, source_id=self._source_id
        )

    @property
    def polymer_sequence_ingest(self) -> MmcifPolymerSequenceIngestResult:
        return self.polymer_ingest

    @property
    def base_ingest(self) -> Any:
        return parse_mmcif(self._missingness_source_bytes, source_id=self._source_id)

    @property
    def missingness_report(self) -> SourceReportedMissingnessReport:
        return self.base_ingest.missingness_evidence

    @property
    def nonpoly_identity_projection_sha256(self) -> str | None:
        return self.nonpoly_projection_sha256

    @property
    def nonpoly_identity_record_state_sha256(self) -> str | None:
        return self.nonpoly_record_state_sha256

    def to_dict(self) -> dict[str, Any]:
        fresh, _ = _validate_fresh_ingest(self)
        return _ingest_evidence_document(fresh)


def _ingest_evidence_document(
    ingest: MmcifUnobservedAtomIngestResult,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "envelope_version": MMCIF_UNOBSERVED_ATOM_ENVELOPE_VERSION,
        "parser_version": MMCIF_UNOBSERVED_ATOM_PARSER_VERSION,
        "profile_id": MMCIF_UNOBSERVED_ATOM_PROFILE_ID,
        "full_source_sha256": ingest.full_source_sha256,
        "carrier_source_sha256": ingest.carrier_source_sha256,
        "canonical_carrier_source_sha256": ingest.canonical_carrier_source_sha256,
        "source_id_sha256": ingest.source_id_sha256,
        "carrier_kind": ingest.carrier_kind,
        "has_nonpoly_identity": ingest.has_nonpoly_identity,
        "unobserved_atom_row_count": len(ingest.unobserved_atom_rows),
        "source_reported_missing_residue_claim_count": 0,
        "source_reported_missing_atom_claim_count": len(ingest.unobserved_atom_rows),
        "source_reported_unobserved_atom_claims_preserved": True,
        "unobserved_atom_projection_sha256": ingest.unobserved_atom_projection_sha256,
        "record_state_sha256": ingest.record_state_sha256,
        "source_binding_sha256": ingest.source_binding_sha256,
        "topology_sha256": ingest.topology_sha256,
        "system_snapshot_sha256": ingest.system_snapshot_sha256,
        "missingness_report_sha256": ingest.missingness_report_sha256,
        "polymer_record_state_sha256": ingest.polymer_record_state_sha256,
        "polymer_projection_sha256": ingest.polymer_projection_sha256,
        "nonpoly_record_state_sha256": ingest.nonpoly_record_state_sha256,
        "nonpoly_identity_projection_sha256": ingest.nonpoly_identity_projection_sha256,
        "nonpoly_identity_record_state_sha256": (
            ingest.nonpoly_identity_record_state_sha256
        ),
    }
    document.update(_authority_false_document())
    return document


def _same_ingest(
    left: MmcifUnobservedAtomIngestResult, right: MmcifUnobservedAtomIngestResult
) -> bool:
    scalar_fields = (
        "full_source_sha256",
        "carrier_source_sha256",
        "canonical_carrier_source_sha256",
        "source_id_sha256",
        "unobserved_atom_projection_sha256",
        "record_state_sha256",
        "source_binding_sha256",
        "topology_sha256",
        "system_snapshot_sha256",
        "missingness_report_sha256",
        "polymer_record_state_sha256",
        "polymer_projection_sha256",
        "nonpoly_projection_sha256",
        "nonpoly_record_state_sha256",
    )
    return (
        all(getattr(left, field) == getattr(right, field) for field in scalar_fields)
        and left.unobserved_atom_rows == right.unobserved_atom_rows
        and left._carrier_source_bytes == right._carrier_source_bytes
        and left._missingness_source_bytes == right._missingness_source_bytes
        and left._system_snapshot_payload == right._system_snapshot_payload
    )


def _validate_fresh_ingest(
    ingest: MmcifUnobservedAtomIngestResult,
) -> tuple[MmcifUnobservedAtomIngestResult, _ParsedEnvelope]:
    if type(ingest) is not MmcifUnobservedAtomIngestResult:
        raise TypeError("ingest must be a MmcifUnobservedAtomIngestResult")
    try:
        components = _parse_components(ingest._full_source, source_id=ingest._source_id)
        fresh = _ingest_from_components(components)
        if not _same_ingest(ingest, fresh):
            raise ValueError("stored evidence differs from fresh source")
        if serialize_all_atom_system(ingest.system) != ingest._system_snapshot_payload:
            raise ValueError("detached public system differs from bound snapshot")
        if ingest._system_snapshot_payload != fresh._system_snapshot_payload:
            raise ValueError("bound snapshot differs from fresh source")
    except (TypeError, ValueError, OverflowError, MmcifUnobservedAtomError):
        raise MmcifUnobservedAtomError(
            "stale_ingest_binding",
            "public ingest state no longer matches its source binding",
        ) from None
    return fresh, components


def _ingest_from_components(
    components: _ParsedEnvelope,
) -> MmcifUnobservedAtomIngestResult:
    return MmcifUnobservedAtomIngestResult(components, _factory_token=_FACTORY_TOKEN)


def parse_mmcif_unobserved_atoms(
    data: bytes, *, source_id: str = ""
) -> MmcifUnobservedAtomIngestResult:
    return _ingest_from_components(_parse_components(data, source_id=source_id))


def mmcif_unobserved_atom_projection_sha256(
    value: MmcifUnobservedAtomIngestResult,
) -> str:
    fresh, _ = _validate_fresh_ingest(value)
    return fresh.unobserved_atom_projection_sha256


def mmcif_unobserved_atom_record_state_sha256(
    value: MmcifUnobservedAtomIngestResult,
) -> str:
    fresh, _ = _validate_fresh_ingest(value)
    return fresh.record_state_sha256


def _emit_unobserved_loop(rows: tuple[MmcifUnobservedAtomRow, ...]) -> bytes:
    lines = ["loop_", *MMCIF_UNOBSERVED_ATOM_HEADERS]
    for row in rows:
        tokens = (
            str(row.source_id),
            "Y",
            "1",
            "1",
            row.auth_asym_id,
            row.auth_comp_id,
            row.auth_seq_id,
            row.pdb_ins_code,
            row.auth_atom_id,
            row.label_alt_id,
            row.label_asym_id,
            row.label_comp_id,
            str(row.label_seq_id),
            row.label_atom_id,
        )
        joined = " ".join(tokens)
        lines.extend((joined,) if len(joined) <= 2_048 else tokens)
    lines.append("#")
    return ("\n".join(lines) + "\n").encode("ascii")


def _compose_output(
    ingest: MmcifUnobservedAtomIngestResult,
    *,
    canonical_carrier_source: bytes | None = None,
) -> bytes:
    carrier_payload = (
        emit_mmcif_polymer_sequence(ingest.polymer_ingest).payload
        if canonical_carrier_source is None
        else canonical_carrier_source
    )
    carrier_block = _parse_block(carrier_payload)
    selected = {
        category: _loop_for(carrier_block, category)
        for category in carrier_block.categories
    }
    parts = [f"data_{carrier_block.name}\n#\n".encode("ascii")]
    for category in _CANONICAL_ORDER:
        if category == _UNOBSERVED_CATEGORY:
            parts.append(_emit_unobserved_loop(ingest.unobserved_atom_rows))
        elif category in selected:
            parts.append(_emit_loop(selected[category]))
    payload = b"".join(parts)
    if len(payload) > MAX_MMCIF_UNOBSERVED_ATOM_INPUT_BYTES:
        raise MmcifUnobservedAtomError(
            "output_too_large", "output exceeds the fixed byte cap"
        )
    return payload


def _receipt_document(
    ingest: MmcifUnobservedAtomIngestResult, payload: bytes
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_id": MMCIF_UNOBSERVED_ATOM_WRITE_RECEIPT_SCHEMA_ID,
        "envelope_version": MMCIF_UNOBSERVED_ATOM_ENVELOPE_VERSION,
        "writer_version": MMCIF_UNOBSERVED_ATOM_WRITER_VERSION,
        "profile_id": MMCIF_UNOBSERVED_ATOM_PROFILE_ID,
        "input_full_source_sha256": ingest.full_source_sha256,
        "input_source_id_sha256": ingest.source_id_sha256,
        "input_source_binding_sha256": ingest.source_binding_sha256,
        "input_record_state_sha256": ingest.record_state_sha256,
        "input_system_snapshot_sha256": ingest.system_snapshot_sha256,
        "input_topology_sha256": ingest.topology_sha256,
        "input_missingness_report_sha256": ingest.missingness_report_sha256,
        "unobserved_atom_projection_sha256": ingest.unobserved_atom_projection_sha256,
        "unobserved_atom_row_count": len(ingest.unobserved_atom_rows),
        "output_source_sha256": _sha256_bytes(payload),
        "output_byte_count": len(payload),
        "source_reported_unobserved_atom_claims_preserved": True,
    }
    document.update(_authority_false_document())
    document["receipt_sha256"] = _sha256_document(document)
    return document


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifUnobservedAtomWriteReceipt:
    _ingest: MmcifUnobservedAtomIngestResult
    _payload: bytes
    _document_bytes: bytes

    def __init__(
        self,
        ingest: MmcifUnobservedAtomIngestResult,
        payload: bytes,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifUnobservedAtomWriteReceipt is factory-only")
        document = _receipt_document(ingest, payload)
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_payload", bytes(payload))
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(document))

    def __repr__(self) -> str:
        return "MmcifUnobservedAtomWriteReceipt(<source-bound-evidence>)"

    def _stored_document(self) -> dict[str, Any]:
        return _load_canonical_json_document(
            self._document_bytes,
            code="invalid_write_receipt",
            label="write receipt",
        )

    @property
    def receipt_sha256(self) -> str:
        return str(self.to_dict()["receipt_sha256"])

    @property
    def output_source_sha256(self) -> str:
        return str(self.to_dict()["output_source_sha256"])

    def to_dict(self) -> dict[str, Any]:
        if (
            type(self._ingest) is not MmcifUnobservedAtomIngestResult
            or type(self._payload) is not bytes
            or type(self._document_bytes) is not bytes
        ):
            raise MmcifUnobservedAtomError(
                "stale_write_receipt",
                "write receipt contains an invalid nested artifact",
            )
        fresh, components = _validate_fresh_ingest(self._ingest)
        canonical_payload = _compose_output(
            fresh,
            canonical_carrier_source=components.canonical_carrier_source,
        )
        if self._payload != canonical_payload:
            raise MmcifUnobservedAtomError(
                "stale_write_receipt",
                "write receipt payload is not the canonical fresh emission",
            )
        expected = _receipt_document(fresh, canonical_payload)
        if self._stored_document() != expected:
            raise MmcifUnobservedAtomError(
                "stale_write_receipt", "write receipt no longer matches fresh evidence"
            )
        return expected


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifUnobservedAtomWriteResult:
    payload: bytes
    receipt: MmcifUnobservedAtomWriteReceipt
    _input_source_binding_sha256: str

    def __init__(
        self,
        payload: bytes,
        receipt: MmcifUnobservedAtomWriteReceipt,
        *,
        _validated_receipt_document: Mapping[str, Any] | None = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifUnobservedAtomWriteResult is factory-only")
        if _validated_receipt_document is None:
            receipt_document = receipt.to_dict()
        else:
            if (
                type(_validated_receipt_document) is not dict
                or receipt._stored_document() != _validated_receipt_document
                or receipt._payload != payload
                or _sha256_bytes(payload)
                != _validated_receipt_document.get("output_source_sha256")
                or len(payload) != _validated_receipt_document.get("output_byte_count")
            ):
                raise MmcifUnobservedAtomError(
                    "invalid_prevalidated_write_receipt",
                    "factory write receipt evidence is inconsistent",
                )
            receipt_document = _validated_receipt_document
        object.__setattr__(self, "payload", bytes(payload))
        object.__setattr__(self, "receipt", receipt)
        object.__setattr__(
            self,
            "_input_source_binding_sha256",
            receipt_document["input_source_binding_sha256"],
        )

    def __repr__(self) -> str:
        return "MmcifUnobservedAtomWriteResult(<canonical-payload>)"

    def to_dict(self) -> dict[str, Any]:
        if (
            type(self.payload) is not bytes
            or type(self.receipt) is not MmcifUnobservedAtomWriteReceipt
            or type(self._input_source_binding_sha256) is not str
        ):
            raise MmcifUnobservedAtomError(
                "stale_write_result",
                "write result contains an invalid nested artifact",
            )
        receipt = self.receipt.to_dict()
        if (
            self.payload != self.receipt._payload
            or len(self.payload) != receipt["output_byte_count"]
            or _sha256_bytes(self.payload) != receipt["output_source_sha256"]
            or receipt["input_source_binding_sha256"]
            != self._input_source_binding_sha256
        ):
            raise MmcifUnobservedAtomError(
                "stale_write_result", "write payload no longer matches its receipt"
            )
        return {
            "output_source_sha256": receipt["output_source_sha256"],
            "output_byte_count": len(self.payload),
            "receipt": receipt,
        }


def emit_mmcif_unobserved_atoms(
    ingest: MmcifUnobservedAtomIngestResult,
) -> MmcifUnobservedAtomWriteResult:
    fresh, components = _validate_fresh_ingest(ingest)
    payload = _compose_output(
        fresh,
        canonical_carrier_source=components.canonical_carrier_source,
    )
    receipt = MmcifUnobservedAtomWriteReceipt(
        fresh, payload, _factory_token=_FACTORY_TOKEN
    )
    return MmcifUnobservedAtomWriteResult(
        payload,
        receipt,
        _validated_receipt_document=receipt._stored_document(),
        _factory_token=_FACTORY_TOKEN,
    )


def serialize_mmcif_unobserved_atoms(
    ingest: MmcifUnobservedAtomIngestResult,
) -> bytes:
    return emit_mmcif_unobserved_atoms(ingest).payload


def _report_document(
    source: MmcifUnobservedAtomIngestResult,
    reparsed: MmcifUnobservedAtomIngestResult,
    write_result: MmcifUnobservedAtomWriteResult,
    reemitted_write_result: MmcifUnobservedAtomWriteResult,
    *,
    second_emission_byte_stable: bool,
    write_receipt_document: Mapping[str, Any] | None = None,
    reemitted_receipt_document: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    projection_equal = (
        source.unobserved_atom_projection_sha256
        == reparsed.unobserved_atom_projection_sha256
    )
    polymer_equal = (
        source.polymer_record_state_sha256 == reparsed.polymer_record_state_sha256
    )
    topology_equal = source.topology_sha256 == reparsed.topology_sha256
    record_equal = source.record_state_sha256 == reparsed.record_state_sha256
    source_id_equal = source.source_id_sha256 == reparsed.source_id_sha256
    carrier_kind_equal = source.carrier_kind == reparsed.carrier_kind
    nonpoly_projection_equal = (
        source.nonpoly_identity_projection_sha256
        == reparsed.nonpoly_identity_projection_sha256
    )
    nonpoly_state_equal = (
        source.nonpoly_identity_record_state_sha256
        == reparsed.nonpoly_identity_record_state_sha256
    )
    write_receipt = (
        write_result.to_dict()["receipt"]
        if write_receipt_document is None
        else write_receipt_document
    )
    reemitted_receipt = (
        reemitted_write_result.to_dict()["receipt"]
        if reemitted_receipt_document is None
        else reemitted_receipt_document
    )
    emitted_source_sha256 = _sha256_bytes(write_result.payload)
    reemitted_source_sha256 = _sha256_bytes(reemitted_write_result.payload)
    actual_second_emission_byte_stable = (
        write_result.payload == reemitted_write_result.payload
    )
    if (
        type(second_emission_byte_stable) is not bool
        or second_emission_byte_stable != actual_second_emission_byte_stable
    ):
        raise MmcifUnobservedAtomError(
            "inconsistent_round_trip_stability",
            "stored stability evidence differs from the two canonical payloads",
        )
    output_reparse_equal = emitted_source_sha256 == reparsed.full_source_sha256
    document: dict[str, Any] = {
        "schema_id": MMCIF_UNOBSERVED_ATOM_ROUND_TRIP_REPORT_SCHEMA_ID,
        "envelope_version": MMCIF_UNOBSERVED_ATOM_ENVELOPE_VERSION,
        "profile_id": MMCIF_UNOBSERVED_ATOM_PROFILE_ID,
        "source_full_source_sha256": source.full_source_sha256,
        "reparsed_full_source_sha256": reparsed.full_source_sha256,
        "source_source_id_sha256": source.source_id_sha256,
        "reparsed_source_id_sha256": reparsed.source_id_sha256,
        "source_source_binding_sha256": source.source_binding_sha256,
        "reparsed_source_binding_sha256": reparsed.source_binding_sha256,
        "source_carrier_kind": source.carrier_kind,
        "reparsed_carrier_kind": reparsed.carrier_kind,
        "output_source_sha256": emitted_source_sha256,
        "reemitted_source_sha256": reemitted_source_sha256,
        "write_receipt_sha256": write_receipt["receipt_sha256"],
        "reemitted_write_receipt_sha256": reemitted_receipt["receipt_sha256"],
        "write_input_source_binding_sha256": write_receipt[
            "input_source_binding_sha256"
        ],
        "reemitted_input_source_binding_sha256": reemitted_receipt[
            "input_source_binding_sha256"
        ],
        "source_projection_sha256": source.unobserved_atom_projection_sha256,
        "reparsed_projection_sha256": reparsed.unobserved_atom_projection_sha256,
        "source_record_state_sha256": source.record_state_sha256,
        "reparsed_record_state_sha256": reparsed.record_state_sha256,
        "source_polymer_record_state_sha256": source.polymer_record_state_sha256,
        "reparsed_polymer_record_state_sha256": (reparsed.polymer_record_state_sha256),
        "source_nonpoly_identity_projection_sha256": (
            source.nonpoly_identity_projection_sha256
        ),
        "reparsed_nonpoly_identity_projection_sha256": (
            reparsed.nonpoly_identity_projection_sha256
        ),
        "source_nonpoly_identity_record_state_sha256": (
            source.nonpoly_identity_record_state_sha256
        ),
        "reparsed_nonpoly_identity_record_state_sha256": (
            reparsed.nonpoly_identity_record_state_sha256
        ),
        "source_topology_sha256": source.topology_sha256,
        "reparsed_topology_sha256": reparsed.topology_sha256,
        "carrier_kind_equal": carrier_kind_equal,
        "source_id_sha256_equal": source_id_equal,
        "projection_sha256_equal": projection_equal,
        "unobserved_atom_projection_sha256_equal": projection_equal,
        "record_state_sha256_equal": record_equal,
        "polymer_record_state_sha256_equal": polymer_equal,
        "nonpoly_identity_projection_sha256_equal": nonpoly_projection_equal,
        "nonpoly_identity_record_state_sha256_equal": nonpoly_state_equal,
        "topology_sha256_equal": topology_equal,
        "source_missingness_report_sha256": source.missingness_report_sha256,
        "reparsed_missingness_report_sha256": reparsed.missingness_report_sha256,
        "missingness_report_sha256_equality_claimed": False,
        "output_reparsed_source_sha256_equal": output_reparse_equal,
        "second_emission_byte_stable": actual_second_emission_byte_stable,
        "source_reported_unobserved_atom_claims_preserved": (
            projection_equal
            and record_equal
            and polymer_equal
            and nonpoly_projection_equal
            and nonpoly_state_equal
            and topology_equal
            and carrier_kind_equal
            and source_id_equal
            and write_receipt["input_source_binding_sha256"]
            == source.source_binding_sha256
            and reemitted_receipt["input_source_binding_sha256"]
            == reparsed.source_binding_sha256
            and write_receipt["input_source_id_sha256"] == source.source_id_sha256
            and reemitted_receipt["input_source_id_sha256"] == reparsed.source_id_sha256
            and write_receipt["output_source_sha256"] == emitted_source_sha256
            and reemitted_receipt["output_source_sha256"] == reemitted_source_sha256
            and output_reparse_equal
            and actual_second_emission_byte_stable
        ),
    }
    document.update(_authority_false_document())
    document["round_trip_report_sha256"] = _sha256_document(document)
    return document


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifUnobservedAtomRoundTripReport:
    _source: MmcifUnobservedAtomIngestResult
    _reparsed: MmcifUnobservedAtomIngestResult
    _write_result: MmcifUnobservedAtomWriteResult
    _reemitted_write_result: MmcifUnobservedAtomWriteResult
    _second_emission_byte_stable: bool
    _document_bytes: bytes

    def __init__(
        self,
        source: MmcifUnobservedAtomIngestResult | None = None,
        reparsed: MmcifUnobservedAtomIngestResult | None = None,
        write_result: MmcifUnobservedAtomWriteResult | None = None,
        reemitted_write_result: MmcifUnobservedAtomWriteResult | None = None,
        second_emission_byte_stable: bool | None = None,
        *,
        _validated_write_receipt_document: Mapping[str, Any] | None = None,
        _validated_reemitted_receipt_document: Mapping[str, Any] | None = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifUnobservedAtomRoundTripReport is factory-only")
        if (
            source is None
            or reparsed is None
            or write_result is None
            or reemitted_write_result is None
            or type(second_emission_byte_stable) is not bool
        ):
            raise TypeError("round-trip report requires complete factory evidence")
        prevalidated = (
            _validated_write_receipt_document is not None
            and _validated_reemitted_receipt_document is not None
        )
        if prevalidated != (
            _validated_write_receipt_document is not None
            or _validated_reemitted_receipt_document is not None
        ):
            raise TypeError("prevalidated round-trip receipt evidence is incomplete")
        if prevalidated:
            if (
                type(_validated_write_receipt_document) is not dict
                or type(_validated_reemitted_receipt_document) is not dict
                or write_result.receipt._stored_document()
                != _validated_write_receipt_document
                or reemitted_write_result.receipt._stored_document()
                != _validated_reemitted_receipt_document
            ):
                raise MmcifUnobservedAtomError(
                    "invalid_prevalidated_round_trip_receipts",
                    "factory round-trip receipt evidence is inconsistent",
                )
        document = _report_document(
            source,
            reparsed,
            write_result,
            reemitted_write_result,
            second_emission_byte_stable=second_emission_byte_stable,
            write_receipt_document=_validated_write_receipt_document,
            reemitted_receipt_document=(_validated_reemitted_receipt_document),
        )
        object.__setattr__(self, "_source", source)
        object.__setattr__(self, "_reparsed", reparsed)
        object.__setattr__(self, "_write_result", write_result)
        object.__setattr__(self, "_reemitted_write_result", reemitted_write_result)
        object.__setattr__(
            self, "_second_emission_byte_stable", second_emission_byte_stable
        )
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(document))

    def __repr__(self) -> str:
        return "MmcifUnobservedAtomRoundTripReport(<semantic-evidence>)"

    def _stored_document(self) -> dict[str, Any]:
        return _load_canonical_json_document(
            self._document_bytes,
            code="invalid_round_trip_report",
            label="round-trip report",
        )

    @property
    def round_trip_report_sha256(self) -> str:
        return str(self.to_dict()["round_trip_report_sha256"])

    @property
    def projection_sha256_equal(self) -> bool:
        return bool(self.to_dict()["projection_sha256_equal"])

    @property
    def unobserved_atom_projection_sha256_equal(self) -> bool:
        return bool(self.to_dict()["unobserved_atom_projection_sha256_equal"])

    @property
    def record_state_sha256_equal(self) -> bool:
        return bool(self.to_dict()["record_state_sha256_equal"])

    @property
    def nonpoly_identity_projection_sha256_equal(self) -> bool:
        return bool(self.to_dict()["nonpoly_identity_projection_sha256_equal"])

    @property
    def nonpoly_identity_record_state_sha256_equal(self) -> bool:
        return bool(self.to_dict()["nonpoly_identity_record_state_sha256_equal"])

    @property
    def second_emission_byte_stable(self) -> bool:
        return bool(self.to_dict()["second_emission_byte_stable"])

    def to_dict(self) -> dict[str, Any]:
        if (
            type(self._source) is not MmcifUnobservedAtomIngestResult
            or type(self._reparsed) is not MmcifUnobservedAtomIngestResult
            or type(self._write_result) is not MmcifUnobservedAtomWriteResult
            or type(self._reemitted_write_result) is not MmcifUnobservedAtomWriteResult
            or type(self._second_emission_byte_stable) is not bool
            or type(self._document_bytes) is not bytes
        ):
            raise MmcifUnobservedAtomError(
                "stale_round_trip_report",
                "round-trip report contains an invalid nested artifact",
            )
        source, _ = _validate_fresh_ingest(self._source)
        reparsed, _ = _validate_fresh_ingest(self._reparsed)
        write_receipt = self._write_result.to_dict()["receipt"]
        reemitted_receipt = self._reemitted_write_result.to_dict()["receipt"]
        expected = _report_document(
            source,
            reparsed,
            self._write_result,
            self._reemitted_write_result,
            second_emission_byte_stable=self._second_emission_byte_stable,
            write_receipt_document=write_receipt,
            reemitted_receipt_document=reemitted_receipt,
        )
        if self._stored_document() != expected:
            raise MmcifUnobservedAtomError(
                "stale_round_trip_report",
                "round-trip report no longer matches fresh evidence",
            )
        return expected


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifUnobservedAtomRoundTripResult:
    source_ingest: MmcifUnobservedAtomIngestResult
    write_result: MmcifUnobservedAtomWriteResult
    reparsed_ingest: MmcifUnobservedAtomIngestResult
    reemitted_write_result: MmcifUnobservedAtomWriteResult
    report: MmcifUnobservedAtomRoundTripReport

    def __init__(
        self,
        source_ingest: MmcifUnobservedAtomIngestResult,
        write_result: MmcifUnobservedAtomWriteResult,
        reparsed_ingest: MmcifUnobservedAtomIngestResult,
        reemitted_write_result: MmcifUnobservedAtomWriteResult,
        report: MmcifUnobservedAtomRoundTripReport,
        *,
        _prevalidated: bool = False,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifUnobservedAtomRoundTripResult is factory-only")
        object.__setattr__(self, "source_ingest", source_ingest)
        object.__setattr__(self, "write_result", write_result)
        object.__setattr__(self, "reparsed_ingest", reparsed_ingest)
        object.__setattr__(self, "reemitted_write_result", reemitted_write_result)
        object.__setattr__(self, "report", report)
        if type(_prevalidated) is not bool:
            raise TypeError("prevalidated round-trip state must be boolean")
        if _prevalidated:
            self._validate_prevalidated_factory_artifacts()
        else:
            self.__post_init__()

    def __repr__(self) -> str:
        return "MmcifUnobservedAtomRoundTripResult(<bound-artifacts>)"

    def _validate_prevalidated_factory_artifacts(self) -> None:
        if (
            type(self.source_ingest) is not MmcifUnobservedAtomIngestResult
            or type(self.reparsed_ingest) is not MmcifUnobservedAtomIngestResult
            or type(self.write_result) is not MmcifUnobservedAtomWriteResult
            or type(self.reemitted_write_result) is not MmcifUnobservedAtomWriteResult
            or type(self.report) is not MmcifUnobservedAtomRoundTripReport
        ):
            raise MmcifUnobservedAtomError(
                "invalid_prevalidated_round_trip_artifacts",
                "factory aggregate contains an invalid artifact type",
            )
        write_document = self.write_result.receipt._stored_document()
        reemitted_document = self.reemitted_write_result.receipt._stored_document()
        report_document = self.report._stored_document()
        expected_report = _report_document(
            self.source_ingest,
            self.reparsed_ingest,
            self.write_result,
            self.reemitted_write_result,
            second_emission_byte_stable=(
                self.write_result.payload == self.reemitted_write_result.payload
            ),
            write_receipt_document=write_document,
            reemitted_receipt_document=reemitted_document,
        )
        if not all(
            (
                write_document
                == _receipt_document(self.source_ingest, self.write_result.payload),
                reemitted_document
                == _receipt_document(
                    self.reparsed_ingest, self.reemitted_write_result.payload
                ),
                self.write_result.payload == self.reparsed_ingest._full_source,
                self.write_result.payload == self.reemitted_write_result.payload,
                self.source_ingest.source_id_sha256
                == self.reparsed_ingest.source_id_sha256,
                self.report._source is self.source_ingest,
                self.report._reparsed is self.reparsed_ingest,
                self.report._write_result is self.write_result,
                self.report._reemitted_write_result is self.reemitted_write_result,
                report_document == expected_report,
                report_document["source_reported_unobserved_atom_claims_preserved"]
                is True,
            )
        ):
            raise MmcifUnobservedAtomError(
                "invalid_prevalidated_round_trip_artifacts",
                "factory aggregate evidence is inconsistent",
            )

    def _validated_artifacts(
        self,
    ) -> tuple[
        MmcifUnobservedAtomIngestResult,
        MmcifUnobservedAtomIngestResult,
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
    ]:
        if (
            type(self.source_ingest) is not MmcifUnobservedAtomIngestResult
            or type(self.reparsed_ingest) is not MmcifUnobservedAtomIngestResult
            or type(self.write_result) is not MmcifUnobservedAtomWriteResult
            or type(self.reemitted_write_result) is not MmcifUnobservedAtomWriteResult
            or type(self.report) is not MmcifUnobservedAtomRoundTripReport
        ):
            raise MmcifUnobservedAtomError(
                "crosswired_round_trip_artifacts",
                "round-trip aggregate contains an invalid artifact type",
            )
        try:
            source, _ = _validate_fresh_ingest(self.source_ingest)
            reparsed, _ = _validate_fresh_ingest(self.reparsed_ingest)
            write_result_document = self.write_result.to_dict()
            reemitted_result_document = self.reemitted_write_result.to_dict()
            write_document = write_result_document["receipt"]
            reemitted_document = reemitted_result_document["receipt"]
            report_document = self.report.to_dict()
            actual_stable = (
                self.write_result.payload == self.reemitted_write_result.payload
            )
            expected_report = _report_document(
                source,
                reparsed,
                self.write_result,
                self.reemitted_write_result,
                second_emission_byte_stable=actual_stable,
                write_receipt_document=write_document,
                reemitted_receipt_document=reemitted_document,
            )
            consistent = all(
                (
                    write_document["input_source_binding_sha256"]
                    == source.source_binding_sha256,
                    write_document["input_source_id_sha256"] == source.source_id_sha256,
                    reemitted_document["input_source_binding_sha256"]
                    == reparsed.source_binding_sha256,
                    reemitted_document["input_source_id_sha256"]
                    == reparsed.source_id_sha256,
                    source.source_id_sha256 == reparsed.source_id_sha256,
                    self.write_result.payload == reparsed._full_source,
                    self.write_result.payload == self.reemitted_write_result.payload,
                    write_document["output_source_sha256"]
                    == reparsed.full_source_sha256,
                    reemitted_document["output_source_sha256"]
                    == reparsed.full_source_sha256,
                    report_document == expected_report,
                    report_document["write_receipt_sha256"]
                    == write_document["receipt_sha256"],
                    report_document["reemitted_write_receipt_sha256"]
                    == reemitted_document["receipt_sha256"],
                    report_document["source_reported_unobserved_atom_claims_preserved"]
                    is True,
                    report_document["carrier_kind_equal"] is True,
                    report_document["source_id_sha256_equal"] is True,
                    report_document["projection_sha256_equal"] is True,
                    report_document["record_state_sha256_equal"] is True,
                    report_document["polymer_record_state_sha256_equal"] is True,
                    report_document["nonpoly_identity_projection_sha256_equal"] is True,
                    report_document["nonpoly_identity_record_state_sha256_equal"]
                    is True,
                    report_document["topology_sha256_equal"] is True,
                    report_document["output_reparsed_source_sha256_equal"] is True,
                    report_document["second_emission_byte_stable"] is True,
                )
            )
        except Exception:
            raise MmcifUnobservedAtomError(
                "crosswired_round_trip_artifacts",
                "round-trip artifacts failed nested validation",
            ) from None
        if not consistent:
            raise MmcifUnobservedAtomError(
                "crosswired_round_trip_artifacts",
                "round-trip artifacts are not cross-consistent",
            )
        return (
            source,
            reparsed,
            write_result_document,
            reemitted_result_document,
            report_document,
        )

    def __post_init__(self) -> None:
        self._validated_artifacts()

    def to_dict(self) -> dict[str, Any]:
        source, reparsed, write, reemitted, report = self._validated_artifacts()
        return {
            "source_ingest": _ingest_evidence_document(source),
            "write_result": write,
            "reparsed_ingest": _ingest_evidence_document(reparsed),
            "reemitted_write_result": reemitted,
            "report": report,
            "source_reported_unobserved_atom_claims_preserved": report[
                "source_reported_unobserved_atom_claims_preserved"
            ],
            **_authority_false_document(),
        }


def round_trip_mmcif_unobserved_atoms_source(
    data: bytes, *, source_id: str = ""
) -> MmcifUnobservedAtomRoundTripResult:
    source = parse_mmcif_unobserved_atoms(data, source_id=source_id)
    write_result = emit_mmcif_unobserved_atoms(source)
    reparsed = parse_mmcif_unobserved_atoms(write_result.payload, source_id=source_id)
    second = emit_mmcif_unobserved_atoms(reparsed)
    stable = second.payload == write_result.payload
    if (
        source.unobserved_atom_projection_sha256
        != reparsed.unobserved_atom_projection_sha256
        or source.record_state_sha256 != reparsed.record_state_sha256
        or source.polymer_record_state_sha256 != reparsed.polymer_record_state_sha256
        or source.nonpoly_identity_projection_sha256
        != reparsed.nonpoly_identity_projection_sha256
        or source.nonpoly_identity_record_state_sha256
        != reparsed.nonpoly_identity_record_state_sha256
        or source.topology_sha256 != reparsed.topology_sha256
        or source.source_id_sha256 != reparsed.source_id_sha256
        or source.carrier_kind != reparsed.carrier_kind
        or not stable
    ):
        raise MmcifUnobservedAtomError(
            "round_trip_mismatch",
            "declared semantic projection failed round-trip validation",
        )
    report = MmcifUnobservedAtomRoundTripReport(
        source,
        reparsed,
        write_result,
        second,
        stable,
        _validated_write_receipt_document=(write_result.receipt._stored_document()),
        _validated_reemitted_receipt_document=(second.receipt._stored_document()),
        _factory_token=_FACTORY_TOKEN,
    )
    return MmcifUnobservedAtomRoundTripResult(
        source,
        write_result,
        reparsed,
        second,
        report,
        _prevalidated=True,
        _factory_token=_FACTORY_TOKEN,
    )


__all__ = [
    "MAX_MMCIF_UNOBSERVED_ATOM_INPUT_BYTES",
    "MAX_MMCIF_UNOBSERVED_ATOM_ROWS",
    "MAX_MMCIF_UNOBSERVED_ATOM_SOURCE_ID_BYTES",
    "MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS",
    "MMCIF_UNOBSERVED_ATOM_ENVELOPE_VERSION",
    "MMCIF_UNOBSERVED_ATOM_HEADERS",
    "MMCIF_UNOBSERVED_ATOM_PARSER_NAME",
    "MMCIF_UNOBSERVED_ATOM_PARSER_VERSION",
    "MMCIF_UNOBSERVED_ATOM_PROFILE_ID",
    "MMCIF_UNOBSERVED_ATOM_PROJECTION_SCOPE",
    "MMCIF_UNOBSERVED_ATOM_PROJECTION_SCHEMA_ID",
    "MMCIF_UNOBSERVED_ATOM_RECORD_STATE_SCHEMA_ID",
    "MMCIF_UNOBSERVED_ATOM_ROUND_TRIP_REPORT_SCHEMA_ID",
    "MMCIF_UNOBSERVED_ATOM_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_UNOBSERVED_ATOM_WRITER_VERSION",
    "MMCIF_UNOBSERVED_ATOM_WRITE_RECEIPT_SCHEMA_ID",
    "MmcifUnobservedAtomError",
    "MmcifUnobservedAtomIngestResult",
    "MmcifUnobservedAtomRoundTripReport",
    "MmcifUnobservedAtomRoundTripResult",
    "MmcifUnobservedAtomRow",
    "MmcifUnobservedAtomWriteReceipt",
    "MmcifUnobservedAtomWriteResult",
    "emit_mmcif_unobserved_atoms",
    "mmcif_unobserved_atom_projection_sha256",
    "mmcif_unobserved_atom_record_state_sha256",
    "parse_mmcif_unobserved_atoms",
    "round_trip_mmcif_unobserved_atoms_source",
    "serialize_mmcif_unobserved_atoms",
]
