"""Opt-in mmCIF polymer-sequence preservation envelope.

This module keeps the strict common-core21 parser/writer unchanged.  It removes
one exact ``_entity_poly_seq`` loop before delegating molecular state to that
base contract (or to the existing opt-in nonpoly-identity envelope), preserves
the ordered source-reported polymer sequence, and restores it around the
canonical carrier emission.

Sequence membership and coordinate observation are identity evidence only.
An unobserved sequence row is not a missing-residue claim, and no auth/label
equivalence, chemistry, preparation, parameterability, physics, runtime, or
scientific authority is inferred.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping

from .mmcif_nonpoly_identity import (
    MmcifNonpolyIdentityError,
    MmcifNonpolyIdentityIngestResult,
    MmcifNonpolyIdentityWriteResult,
    parse_mmcif_nonpoly_identity,
    write_mmcif_nonpoly_identity,
)
from .mmcif_syntax import CifBlock, CifLoop, CifSyntaxError, CifToken, parse_cif_block
from .mmcif_writer import (
    MMCIF_REPRESENTABLE_STATE_SCHEMA_ID,
    MMCIF_WRITER_VERSION,
    MmcifWriteError,
    mmcif_representable_state_sha256,
    write_mmcif,
)
from .models import AllAtomSystem
from .pdb_mmcif import (
    MMCIF_PARSER_VERSION,
    StructureIngestResult,
    StructureParseError,
    parse_mmcif,
)
from .serialization import (
    MolecularSerializationError,
    canonical_all_atom_snapshot_digest,
    deserialize_all_atom_system,
    serialize_all_atom_system,
)
from .topology import canonical_topology_sha256


MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION = "1.0.0"
MMCIF_POLYMER_SEQUENCE_PARSER_VERSION = "1.0.0"
MMCIF_POLYMER_SEQUENCE_WRITER_VERSION = "1.0.0"
MMCIF_POLYMER_SEQUENCE_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular.mmcif_polymer_sequence"
)
MMCIF_POLYMER_SEQUENCE_PROFILE_ID = (
    "strict_mmcif_source_reported_entity_poly_seq_envelope/1.0.0"
)
MMCIF_POLYMER_SEQUENCE_PROJECTION_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_sequence_projection/1.0.0"
)
MMCIF_POLYMER_SEQUENCE_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_sequence_source_binding/1.0.0"
)
MMCIF_POLYMER_SEQUENCE_RECORD_STATE_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_sequence_record_state/1.0.0"
)
MMCIF_POLYMER_SEQUENCE_WRITE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_sequence_write_receipt/1.0.0"
)
MMCIF_POLYMER_SEQUENCE_ROUND_TRIP_REPORT_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_sequence_round_trip_report/1.0.0"
)

MAX_MMCIF_POLYMER_SEQUENCE_INPUT_BYTES = 64 * 1024 * 1024
MAX_MMCIF_POLYMER_SEQUENCE_ROWS = 100_000
MAX_MMCIF_POLYMER_SEQUENCE_TOKEN_CHARS = 256

MMCIF_ENTITY_POLY_SEQ_HEADERS = (
    "_entity_poly_seq.entity_id",
    "_entity_poly_seq.num",
    "_entity_poly_seq.mon_id",
    "_entity_poly_seq.hetero",
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
_BASE_CATEGORIES = frozenset(
    {"_entity", "_struct_asym", "_entity_poly_seq", "_atom_site"}
)
_NONPOLY_CATEGORIES = frozenset(
    {
        "_entity",
        "_struct_asym",
        "_entity_poly_seq",
        "_pdbx_entity_nonpoly",
        "_pdbx_nonpoly_scheme",
        "_atom_site",
    }
)
_CANONICAL_BASE_ORDER = (
    "_entity",
    "_struct_asym",
    "_entity_poly_seq",
    "_atom_site",
)
_CANONICAL_NONPOLY_ORDER = (
    "_entity",
    "_struct_asym",
    "_entity_poly_seq",
    "_pdbx_entity_nonpoly",
    "_pdbx_nonpoly_scheme",
    "_atom_site",
)
_POSITIVE_INTEGER_RE = re.compile(r"^[1-9][0-9]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FACTORY_TOKEN = object()

_FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "reference_sequence_equivalence_assessed",
    "coordinate_observation_completeness_assessed",
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
    "missing_residue_fact_claimed",
    "sequence_completeness_claimed",
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


class MmcifPolymerSequenceError(ValueError):
    """Stable fail-closed error that never includes source identity values."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        line_number: int | None = None,
    ) -> None:
        self.code = str(code)
        self.detail = str(message)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"mmcif_polymer_sequence:{self.code}{suffix}: {self.detail}")


def _canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_document(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(document)).hexdigest()


def _require_sha256(value: Any, *, field_name: str) -> None:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256")


def _authority_false_document() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _is_bounded_identity_token(value: Any) -> bool:
    return (
        type(value) is str
        and bool(value)
        and value not in {".", "?"}
        and len(value) <= MAX_MMCIF_POLYMER_SEQUENCE_TOKEN_CHARS
        and all(0x21 <= ord(character) <= 0x7E for character in value)
    )


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifPolymerSequenceRow:
    """One ordered source sequence row with derived coordinate observation."""

    entity_id: str
    num: int
    mon_id: str
    hetero: str
    coordinate_observed: bool
    observed_asym_ids: tuple[str, ...]

    def __init__(
        self,
        *,
        entity_id: str,
        num: int,
        mon_id: str,
        hetero: str,
        coordinate_observed: bool,
        observed_asym_ids: tuple[str, ...],
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifPolymerSequenceRow is factory-only")
        for field_name, value in (
            ("entity_id", entity_id),
            ("num", num),
            ("mon_id", mon_id),
            ("hetero", hetero),
            ("coordinate_observed", coordinate_observed),
            ("observed_asym_ids", observed_asym_ids),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        if not _is_bounded_identity_token(
            self.entity_id
        ) or not _is_bounded_identity_token(self.mon_id):
            raise TypeError(
                "polymer sequence identifiers must be bounded bare ASCII tokens"
            )
        if (
            type(self.num) is not int
            or not 1 <= self.num <= MAX_MMCIF_POLYMER_SEQUENCE_ROWS
        ):
            raise TypeError("polymer sequence num must be within the row domain")
        if self.hetero != "n":
            raise ValueError("polymer sequence hetero must be canonical n")
        if type(self.coordinate_observed) is not bool:
            raise TypeError("coordinate_observed must be boolean")
        if (
            type(self.observed_asym_ids) is not tuple
            or not all(
                _is_bounded_identity_token(value) for value in self.observed_asym_ids
            )
            or tuple(dict.fromkeys(self.observed_asym_ids)) != self.observed_asym_ids
        ):
            raise TypeError("observed_asym_ids must be an ordered unique string tuple")
        if self.coordinate_observed != bool(self.observed_asym_ids):
            raise ValueError("coordinate observation fields are inconsistent")


def _projection_document(
    rows: tuple[MmcifPolymerSequenceRow, ...],
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_POLYMER_SEQUENCE_PROJECTION_SCHEMA_ID,
        "envelope_version": MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
        "parser_version": MMCIF_POLYMER_SEQUENCE_PARSER_VERSION,
        "profile_id": MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
        "headers": list(MMCIF_ENTITY_POLY_SEQ_HEADERS),
        "rows": [
            {
                "ordinal": ordinal,
                "entity_id": row.entity_id,
                "num": row.num,
                "mon_id": row.mon_id,
                "hetero": "n",
                "coordinate_observed": row.coordinate_observed,
                "observed_asym_ids": list(row.observed_asym_ids),
                "missing_residue_fact_claimed": False,
            }
            for ordinal, row in enumerate(rows)
        ],
        "row_order": "source_order",
        "coordinate_observation_semantics": (
            "atom_site_label_identity_presence_only_not_missingness"
        ),
    }


def _projection_sha256(rows: tuple[MmcifPolymerSequenceRow, ...]) -> str:
    return _sha256_document(_projection_document(rows))


def _record_state_document(
    *,
    base_representable_state_sha256: str,
    polymer_sequence_projection_sha256: str,
    nonpoly_identity_record_state_sha256: str | None,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_POLYMER_SEQUENCE_RECORD_STATE_SCHEMA_ID,
        "envelope_version": MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
        "parser_version": MMCIF_POLYMER_SEQUENCE_PARSER_VERSION,
        "writer_version": MMCIF_POLYMER_SEQUENCE_WRITER_VERSION,
        "profile_id": MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
        "base_parser_version": MMCIF_PARSER_VERSION,
        "base_writer_version": MMCIF_WRITER_VERSION,
        "base_representable_state_schema_id": MMCIF_REPRESENTABLE_STATE_SCHEMA_ID,
        "base_representable_state_sha256": base_representable_state_sha256,
        "polymer_sequence_projection_schema_id": (
            MMCIF_POLYMER_SEQUENCE_PROJECTION_SCHEMA_ID
        ),
        "polymer_sequence_projection_sha256": (polymer_sequence_projection_sha256),
        "nonpoly_identity_record_state_sha256": (nonpoly_identity_record_state_sha256),
        "nonpoly_identity_combined": nonpoly_identity_record_state_sha256 is not None,
    }


def _record_state_sha256(
    *,
    base_representable_state_sha256: str,
    polymer_sequence_projection_sha256: str,
    nonpoly_identity_record_state_sha256: str | None,
) -> str:
    return _sha256_document(
        _record_state_document(
            base_representable_state_sha256=base_representable_state_sha256,
            polymer_sequence_projection_sha256=(polymer_sequence_projection_sha256),
            nonpoly_identity_record_state_sha256=(nonpoly_identity_record_state_sha256),
        )
    )


def _source_binding_document(
    *,
    full_source_sha256: str,
    normalized_carrier_source_sha256: str,
    canonical_carrier_source_sha256: str,
    source_id_sha256: str,
    polymer_sequence_projection_sha256: str,
    nonpoly_identity_record_state_sha256: str | None,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_POLYMER_SEQUENCE_SOURCE_BINDING_SCHEMA_ID,
        "envelope_version": MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
        "parser_version": MMCIF_POLYMER_SEQUENCE_PARSER_VERSION,
        "profile_id": MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
        "full_source_sha256": full_source_sha256,
        "normalized_carrier_source_sha256": normalized_carrier_source_sha256,
        "canonical_carrier_source_sha256": canonical_carrier_source_sha256,
        "source_id_sha256": source_id_sha256,
        "polymer_sequence_projection_sha256": (polymer_sequence_projection_sha256),
        "nonpoly_identity_record_state_sha256": (nonpoly_identity_record_state_sha256),
    }


def _source_binding_sha256(
    *,
    full_source_sha256: str,
    normalized_carrier_source_sha256: str,
    canonical_carrier_source_sha256: str,
    source_id_sha256: str,
    polymer_sequence_projection_sha256: str,
    nonpoly_identity_record_state_sha256: str | None,
) -> str:
    return _sha256_document(
        _source_binding_document(
            full_source_sha256=full_source_sha256,
            normalized_carrier_source_sha256=(normalized_carrier_source_sha256),
            canonical_carrier_source_sha256=(canonical_carrier_source_sha256),
            source_id_sha256=source_id_sha256,
            polymer_sequence_projection_sha256=(polymer_sequence_projection_sha256),
            nonpoly_identity_record_state_sha256=(nonpoly_identity_record_state_sha256),
        )
    )


def _try_parse_block(text: str) -> tuple[CifBlock | None, str, int | None]:
    try:
        return parse_cif_block(text), "", None
    except CifSyntaxError as exc:
        return None, exc.code, exc.line_number


def _loop_for(block: CifBlock, category: str) -> CifLoop:
    scalar = [tag for tag in block.scalar_values if tag.split(".", 1)[0] == category]
    loops = [loop for loop in block.loops if category in loop.categories]
    if scalar or len(loops) != 1 or loops[0].categories != (category,):
        raise MmcifPolymerSequenceError(
            "unsupported_category_representation",
            "each selected category must be exactly one category-local loop",
        )
    return loops[0]


def _require_headers(loop: CifLoop, expected: tuple[str, ...]) -> None:
    if loop.tags != expected:
        raise MmcifPolymerSequenceError(
            "unsupported_category_headers",
            "selected category headers are outside the exact envelope profile",
            line_number=loop.line_number,
        )


def _identity_value(token: CifToken) -> str:
    value = token.value
    if (
        token.quoted
        or token.multiline
        or not value
        or value in {".", "?"}
        or len(value) > MAX_MMCIF_POLYMER_SEQUENCE_TOKEN_CHARS
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise MmcifPolymerSequenceError(
            "invalid_sequence_identity_token",
            "sequence identity fields must be bounded bare nonmissing ASCII tokens",
            line_number=token.line_number,
        )
    return value


def _token_text(token: CifToken) -> str:
    if token.multiline:
        raise MmcifPolymerSequenceError(
            "unsupported_multiline_token",
            "multiline values are outside the carrier profile",
            line_number=token.line_number,
        )
    if not token.quoted:
        return token.value
    if "'" not in token.value:
        return f"'{token.value}'"
    if '"' not in token.value:
        return f'"{token.value}"'
    raise MmcifPolymerSequenceError(
        "unsupported_quoted_token",
        "quoted carrier token has no canonical single-line representation",
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


def _emit_without_polymer_sequence(block: CifBlock) -> bytes:
    parts = [f"data_{block.name}\n#\n".encode("ascii")]
    for category in block.categories:
        if category == "_entity_poly_seq":
            continue
        parts.append(_emit_loop(_loop_for(block, category)))
    payload = b"".join(parts)
    if len(payload) > MAX_MMCIF_POLYMER_SEQUENCE_INPUT_BYTES:
        raise MmcifPolymerSequenceError(
            "carrier_source_too_large", "normalized carrier exceeds the byte cap"
        )
    return payload


@dataclass(frozen=True, slots=True)
class _ParsedComponents:
    block_name: str
    full_source_bytes: bytes
    carrier_source_bytes: bytes
    canonical_carrier_source_bytes: bytes
    base_ingest: StructureIngestResult
    sequence_rows: tuple[MmcifPolymerSequenceRow, ...]
    nonpoly_ingest: MmcifNonpolyIdentityIngestResult | None
    nonpoly_write: MmcifNonpolyIdentityWriteResult | None


def _try_parse_base(
    data: bytes, source_id: str
) -> tuple[StructureIngestResult | None, str]:
    try:
        return parse_mmcif(data, source_id=source_id), ""
    except StructureParseError as exc:
        return None, exc.code


def _try_parse_nonpoly(
    data: bytes, source_id: str
) -> tuple[MmcifNonpolyIdentityIngestResult | None, str]:
    try:
        return parse_mmcif_nonpoly_identity(data, source_id=source_id), ""
    except MmcifNonpolyIdentityError as exc:
        return None, exc.code


def _try_write_base(system: AllAtomSystem):
    try:
        return write_mmcif(system), ""
    except MmcifWriteError as exc:
        return None, exc.code


def _try_write_nonpoly(
    ingest: MmcifNonpolyIdentityIngestResult,
) -> tuple[MmcifNonpolyIdentityWriteResult | None, str]:
    try:
        return write_mmcif_nonpoly_identity(ingest), ""
    except MmcifNonpolyIdentityError as exc:
        return None, exc.code


def _parse_components(data: bytes, *, source_id: str) -> _ParsedComponents:
    if type(data) is not bytes:
        raise TypeError("mmCIF polymer sequence input must be bytes")
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    if not data:
        raise MmcifPolymerSequenceError("empty_input", "input is empty")
    if len(data) > MAX_MMCIF_POLYMER_SEQUENCE_INPUT_BYTES:
        raise MmcifPolymerSequenceError(
            "input_too_large", "input exceeds the fixed polymer-sequence byte cap"
        )
    if not data.isascii():
        raise MmcifPolymerSequenceError(
            "non_ascii_input", "the exact CIF 1.1 envelope requires ASCII"
        )
    block, syntax_code, syntax_line = _try_parse_block(data.decode("ascii"))
    if block is None:
        raise MmcifPolymerSequenceError(
            "invalid_cif_syntax",
            f"input failed CIF syntax validation ({syntax_code})",
            line_number=syntax_line,
        )
    category_set = frozenset(block.categories)
    if category_set == _BASE_CATEGORIES:
        has_nonpoly = False
    elif category_set == _NONPOLY_CATEGORIES:
        has_nonpoly = True
    else:
        raise MmcifPolymerSequenceError(
            "unsupported_category_surface",
            "input categories are outside the base or composed exact envelope",
        )
    expected_loop_count = 6 if has_nonpoly else 4
    if block.scalar_values or len(block.loops) != expected_loop_count:
        raise MmcifPolymerSequenceError(
            "unsupported_category_representation",
            "the envelope requires one loop for every selected category and no scalars",
        )

    entity_loop = _loop_for(block, "_entity")
    struct_asym_loop = _loop_for(block, "_struct_asym")
    sequence_loop = _loop_for(block, "_entity_poly_seq")
    atom_loop = _loop_for(block, "_atom_site")
    _require_headers(entity_loop, _ENTITY_HEADERS)
    _require_headers(struct_asym_loop, _STRUCT_ASYM_HEADERS)
    _require_headers(sequence_loop, MMCIF_ENTITY_POLY_SEQ_HEADERS)
    _require_headers(atom_loop, _COMMON_CORE21_ATOM_SITE_HEADERS)
    if len(sequence_loop.rows) > MAX_MMCIF_POLYMER_SEQUENCE_ROWS:
        raise MmcifPolymerSequenceError(
            "too_many_sequence_rows", "polymer sequence row count exceeds the cap"
        )

    entity_types: dict[str, str] = {}
    for tokens in entity_loop.rows:
        entity_id = _identity_value(tokens[0])
        entity_type = _identity_value(tokens[1])
        if entity_id in entity_types:
            raise MmcifPolymerSequenceError(
                "duplicate_entity_id", "base entity IDs must be unique"
            )
        entity_types[entity_id] = entity_type

    raw_sequence: list[tuple[str, int, str]] = []
    by_entity_positions: dict[str, list[int]] = {}
    seen_positions: set[tuple[str, int]] = set()
    for tokens in sequence_loop.rows:
        entity_id = _identity_value(tokens[0])
        if entity_types.get(entity_id) != "polymer":
            raise MmcifPolymerSequenceError(
                "nonpolymer_sequence_entity",
                "entity-poly-seq rows may reference only polymer entities",
                line_number=tokens[0].line_number,
            )
        num_token = tokens[1]
        if (
            num_token.quoted
            or num_token.multiline
            or not _POSITIVE_INTEGER_RE.fullmatch(num_token.value)
        ):
            raise MmcifPolymerSequenceError(
                "invalid_sequence_num",
                "sequence num must be a canonical positive decimal integer",
                line_number=num_token.line_number,
            )
        num = int(num_token.value, 10)
        if num > MAX_MMCIF_POLYMER_SEQUENCE_ROWS:
            raise MmcifPolymerSequenceError(
                "sequence_num_too_large", "sequence num exceeds the row-domain cap"
            )
        key = (entity_id, num)
        if key in seen_positions:
            raise MmcifPolymerSequenceError(
                "duplicate_sequence_position",
                "sequence positions must be unique within each entity",
            )
        seen_positions.add(key)
        mon_id = _identity_value(tokens[2])
        hetero_token = tokens[3]
        if hetero_token.quoted or hetero_token.multiline:
            raise MmcifPolymerSequenceError(
                "invalid_sequence_hetero",
                "sequence hetero must be a bare token",
                line_number=hetero_token.line_number,
            )
        if hetero_token.value in {"y", "yes"}:
            raise MmcifPolymerSequenceError(
                "microheterogeneity_not_supported",
                "v1 does not preserve microheterogeneous sequence positions",
                line_number=hetero_token.line_number,
            )
        if hetero_token.value not in {"n", "no"}:
            raise MmcifPolymerSequenceError(
                "invalid_sequence_hetero",
                "v1 accepts only n or no and emits canonical n",
                line_number=hetero_token.line_number,
            )
        raw_sequence.append((entity_id, num, mon_id))
        by_entity_positions.setdefault(entity_id, []).append(num)
    polymer_entity_ids = {
        entity_id
        for entity_id, entity_type in entity_types.items()
        if entity_type == "polymer"
    }
    if set(by_entity_positions) != polymer_entity_ids:
        raise MmcifPolymerSequenceError(
            "polymer_entity_sequence_coverage_mismatch",
            "every polymer entity must have sequence rows and only polymer entities may have them",
        )
    for positions in by_entity_positions.values():
        if positions != list(range(1, len(positions) + 1)):
            raise MmcifPolymerSequenceError(
                "noncontiguous_sequence_positions",
                "source-filtered sequence positions must be ordered contiguously from one per entity",
            )

    asym_entities: dict[str, str] = {}
    for tokens in struct_asym_loop.rows:
        asym_id = _identity_value(tokens[0])
        entity_id = _identity_value(tokens[1])
        if asym_id in asym_entities:
            raise MmcifPolymerSequenceError(
                "duplicate_struct_asym_id", "struct-asym IDs must be unique"
            )
        asym_entities[asym_id] = entity_id
    sequence_components = {
        (entity_id, num): mon_id for entity_id, num, mon_id in raw_sequence
    }
    observed_asym_ids: dict[tuple[str, int], list[str]] = {}
    atom_indexes = {tag: index for index, tag in enumerate(atom_loop.tags)}
    for atom_tokens in atom_loop.rows:
        entity_id = _identity_value(
            atom_tokens[atom_indexes["_atom_site.label_entity_id"]]
        )
        if entity_types.get(entity_id) != "polymer":
            continue
        asym_id = _identity_value(atom_tokens[atom_indexes["_atom_site.label_asym_id"]])
        if asym_entities.get(asym_id) != entity_id:
            raise MmcifPolymerSequenceError(
                "polymer_atom_asym_join_mismatch",
                "polymer atom label asym and entity IDs do not join",
            )
        seq_token = atom_tokens[atom_indexes["_atom_site.label_seq_id"]]
        if (
            seq_token.quoted
            or seq_token.multiline
            or not _POSITIVE_INTEGER_RE.fullmatch(seq_token.value)
        ):
            raise MmcifPolymerSequenceError(
                "invalid_polymer_atom_sequence_num",
                "polymer atom label_seq_id must be a canonical positive integer",
                line_number=seq_token.line_number,
            )
        num = int(seq_token.value, 10)
        mon_id = _identity_value(atom_tokens[atom_indexes["_atom_site.label_comp_id"]])
        key = (entity_id, num)
        if sequence_components.get(key) != mon_id:
            raise MmcifPolymerSequenceError(
                "polymer_atom_sequence_join_mismatch",
                "polymer atom label identity is absent or differs from the sequence row",
            )
        asym_values = observed_asym_ids.setdefault(key, [])
        if asym_id not in asym_values:
            asym_values.append(asym_id)

    sequence_rows = tuple(
        MmcifPolymerSequenceRow(
            entity_id=entity_id,
            num=num,
            mon_id=mon_id,
            hetero="n",
            coordinate_observed=bool(observed_asym_ids.get((entity_id, num))),
            observed_asym_ids=tuple(observed_asym_ids.get((entity_id, num), ())),
            _factory_token=_FACTORY_TOKEN,
        )
        for entity_id, num, mon_id in raw_sequence
    )

    carrier_source = _emit_without_polymer_sequence(block)
    nonpoly_ingest: MmcifNonpolyIdentityIngestResult | None = None
    nonpoly_write: MmcifNonpolyIdentityWriteResult | None = None
    if has_nonpoly:
        nonpoly_ingest, carrier_code = _try_parse_nonpoly(carrier_source, source_id)
        if nonpoly_ingest is None:
            raise MmcifPolymerSequenceError(
                "nonpoly_carrier_rejected",
                f"existing nonpoly identity contract rejected the carrier ({carrier_code})",
            )
        nonpoly_write, writer_code = _try_write_nonpoly(nonpoly_ingest)
        if nonpoly_write is None:
            raise MmcifPolymerSequenceError(
                "nonpoly_carrier_unwritable",
                f"existing nonpoly identity writer rejected the carrier ({writer_code})",
            )
        base_ingest = nonpoly_ingest.base_ingest
        canonical_carrier = nonpoly_write.payload
    else:
        base_ingest, carrier_code = _try_parse_base(carrier_source, source_id)
        if base_ingest is None:
            raise MmcifPolymerSequenceError(
                "base_carrier_rejected",
                f"common-core21 parser rejected the carrier ({carrier_code})",
            )
        base_write, writer_code = _try_write_base(base_ingest.system)
        if base_write is None:
            raise MmcifPolymerSequenceError(
                "base_carrier_unwritable",
                f"common-core21 writer rejected the carrier ({writer_code})",
            )
        canonical_carrier = base_write.payload
    return _ParsedComponents(
        block_name=block.name,
        full_source_bytes=data,
        carrier_source_bytes=carrier_source,
        canonical_carrier_source_bytes=canonical_carrier,
        base_ingest=base_ingest,
        sequence_rows=sequence_rows,
        nonpoly_ingest=nonpoly_ingest,
        nonpoly_write=nonpoly_write,
    )


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifPolymerSequenceIngestResult:
    """Detached, digest-bound result for the exact polymer-sequence envelope."""

    _system_snapshot_payload: bytes
    _base_coverage: Any
    _base_missingness_evidence: Any
    _full_source_bytes: bytes
    _carrier_source_bytes: bytes
    _canonical_carrier_source_bytes: bytes
    _nonpoly_ingest: MmcifNonpolyIdentityIngestResult | None
    sequence_rows: tuple[MmcifPolymerSequenceRow, ...]
    data_block_name: str
    carrier_kind: str
    full_source_sha256: str
    carrier_source_sha256: str
    canonical_carrier_source_sha256: str
    base_system_snapshot_sha256: str
    base_topology_sha256: str
    base_representable_state_sha256: str
    polymer_sequence_projection_sha256: str
    nonpoly_identity_projection_sha256: str | None
    nonpoly_identity_record_state_sha256: str | None
    record_state_sha256: str
    source_id_sha256: str
    source_binding_sha256: str

    def __init__(
        self,
        *,
        system: AllAtomSystem,
        base_ingest: StructureIngestResult,
        nonpoly_ingest: MmcifNonpolyIdentityIngestResult | None,
        sequence_rows: tuple[MmcifPolymerSequenceRow, ...],
        data_block_name: str,
        carrier_kind: str,
        full_source_bytes: bytes,
        carrier_source_bytes: bytes,
        canonical_carrier_source_bytes: bytes,
        full_source_sha256: str,
        carrier_source_sha256: str,
        canonical_carrier_source_sha256: str,
        base_system_snapshot_sha256: str,
        base_topology_sha256: str,
        base_representable_state_sha256: str,
        polymer_sequence_projection_sha256: str,
        nonpoly_identity_projection_sha256: str | None,
        nonpoly_identity_record_state_sha256: str | None,
        record_state_sha256: str,
        source_id_sha256: str,
        source_binding_sha256: str,
        _validated_components: _ParsedComponents | None = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifPolymerSequenceIngestResult is factory-only")
        if (
            _validated_components is not None
            and type(_validated_components) is not _ParsedComponents
        ):
            raise TypeError("validated components must use the internal exact type")
        if base_ingest.system is not system:
            raise ValueError("polymer ingest base/system binding is inconsistent")
        for field_name, value in (
            ("_system_snapshot_payload", serialize_all_atom_system(system)),
            ("_base_coverage", deepcopy(base_ingest.coverage)),
            (
                "_base_missingness_evidence",
                deepcopy(base_ingest.missingness_evidence),
            ),
            ("_full_source_bytes", full_source_bytes),
            ("_carrier_source_bytes", carrier_source_bytes),
            ("_canonical_carrier_source_bytes", canonical_carrier_source_bytes),
            ("_nonpoly_ingest", deepcopy(nonpoly_ingest)),
            ("sequence_rows", sequence_rows),
            ("data_block_name", data_block_name),
            ("carrier_kind", carrier_kind),
            ("full_source_sha256", full_source_sha256),
            ("carrier_source_sha256", carrier_source_sha256),
            (
                "canonical_carrier_source_sha256",
                canonical_carrier_source_sha256,
            ),
            ("base_system_snapshot_sha256", base_system_snapshot_sha256),
            ("base_topology_sha256", base_topology_sha256),
            (
                "base_representable_state_sha256",
                base_representable_state_sha256,
            ),
            (
                "polymer_sequence_projection_sha256",
                polymer_sequence_projection_sha256,
            ),
            (
                "nonpoly_identity_projection_sha256",
                nonpoly_identity_projection_sha256,
            ),
            (
                "nonpoly_identity_record_state_sha256",
                nonpoly_identity_record_state_sha256,
            ),
            ("record_state_sha256", record_state_sha256),
            ("source_id_sha256", source_id_sha256),
            ("source_binding_sha256", source_binding_sha256),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__(_validated_components=_validated_components)

    @property
    def system(self) -> AllAtomSystem:
        """Return a detached system reconstructed from the bound snapshot."""

        return deserialize_all_atom_system(self._system_snapshot_payload)

    @property
    def base_ingest(self) -> StructureIngestResult:
        """Return a detached common-core21 ingest view."""

        return StructureIngestResult(
            system=self.system,
            coverage=deepcopy(self._base_coverage),
            missingness_evidence=deepcopy(self._base_missingness_evidence),
        )

    @property
    def has_nonpoly_identity(self) -> bool:
        return self._nonpoly_ingest is not None

    @property
    def nonpoly_ingest(self) -> MmcifNonpolyIdentityIngestResult | None:
        """Return a detached composed carrier ingest, when present."""

        return deepcopy(self._nonpoly_ingest)

    def __post_init__(
        self,
        *,
        _validated_components: _ParsedComponents | None = None,
    ) -> None:
        for field_name in (
            "_system_snapshot_payload",
            "_full_source_bytes",
            "_carrier_source_bytes",
            "_canonical_carrier_source_bytes",
        ):
            if type(getattr(self, field_name)) is not bytes:
                raise TypeError("polymer ingest bound payloads must be bytes")
        if type(self.sequence_rows) is not tuple or not self.sequence_rows:
            raise TypeError("sequence_rows must be a nonempty tuple")
        for row in self.sequence_rows:
            if type(row) is not MmcifPolymerSequenceRow:
                raise TypeError("sequence_rows contain an invalid row artifact")
            row.__post_init__()
        if type(self.data_block_name) is not str or not self.data_block_name.isascii():
            raise TypeError("data_block_name must be an ASCII string")
        if self.carrier_kind not in {"common_core21", "mmcif_nonpoly_identity"}:
            raise ValueError("carrier_kind is outside the exact envelope")
        for field_name in (
            "full_source_sha256",
            "carrier_source_sha256",
            "canonical_carrier_source_sha256",
            "base_system_snapshot_sha256",
            "base_topology_sha256",
            "base_representable_state_sha256",
            "polymer_sequence_projection_sha256",
            "record_state_sha256",
            "source_id_sha256",
            "source_binding_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        for field_name in (
            "nonpoly_identity_projection_sha256",
            "nonpoly_identity_record_state_sha256",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _require_sha256(value, field_name=field_name)
        composed = self.carrier_kind == "mmcif_nonpoly_identity"
        if composed != (self._nonpoly_ingest is not None) or composed != (
            self.nonpoly_identity_projection_sha256 is not None
            and self.nonpoly_identity_record_state_sha256 is not None
        ):
            raise ValueError("polymer ingest carrier composition is inconsistent")
        if hashlib.sha256(self._full_source_bytes).hexdigest() != (
            self.full_source_sha256
        ):
            raise ValueError("polymer ingest full-source digest is inconsistent")
        if hashlib.sha256(self._carrier_source_bytes).hexdigest() != (
            self.carrier_source_sha256
        ):
            raise ValueError("polymer ingest carrier-source digest is inconsistent")
        if hashlib.sha256(self._canonical_carrier_source_bytes).hexdigest() != (
            self.canonical_carrier_source_sha256
        ):
            raise ValueError("polymer ingest canonical-carrier digest is inconsistent")
        header_end = self._carrier_source_bytes.find(b"\n")
        if header_end < 0 or self._carrier_source_bytes[
            :header_end
        ] != b"data_" + self.data_block_name.encode("ascii"):
            raise ValueError("polymer ingest data-block binding is inconsistent")
        system = None
        try:
            system = self.system
        except (MolecularSerializationError, ValueError, TypeError):
            pass
        if system is None:
            raise ValueError("polymer ingest snapshot cannot be reconstructed")
        if canonical_all_atom_snapshot_digest(system) != (
            self.base_system_snapshot_sha256
        ):
            raise ValueError("polymer ingest snapshot digest is inconsistent")
        if canonical_topology_sha256(system) != self.base_topology_sha256:
            raise ValueError("polymer ingest topology digest is inconsistent")
        if mmcif_representable_state_sha256(system) != (
            self.base_representable_state_sha256
        ):
            raise ValueError("polymer ingest representable state is inconsistent")
        if _projection_sha256(self.sequence_rows) != (
            self.polymer_sequence_projection_sha256
        ):
            raise ValueError("polymer ingest sequence projection is inconsistent")
        if self._nonpoly_ingest is not None:
            self._nonpoly_ingest.__post_init__()
            if self._nonpoly_ingest.identity_projection_sha256 != (
                self.nonpoly_identity_projection_sha256
            ) or self._nonpoly_ingest.record_state_sha256 != (
                self.nonpoly_identity_record_state_sha256
            ):
                raise ValueError("polymer ingest nonpoly binding is inconsistent")
        expected_state = _record_state_sha256(
            base_representable_state_sha256=(self.base_representable_state_sha256),
            polymer_sequence_projection_sha256=(
                self.polymer_sequence_projection_sha256
            ),
            nonpoly_identity_record_state_sha256=(
                self.nonpoly_identity_record_state_sha256
            ),
        )
        if self.record_state_sha256 != expected_state:
            raise ValueError("polymer ingest record-state digest is inconsistent")
        expected_source_id_sha = hashlib.sha256(
            system.provenance.source_id.encode("utf-8")
        ).hexdigest()
        if self.source_id_sha256 != expected_source_id_sha:
            raise ValueError("polymer ingest source-ID digest is inconsistent")
        expected_binding = _source_binding_sha256(
            full_source_sha256=self.full_source_sha256,
            normalized_carrier_source_sha256=self.carrier_source_sha256,
            canonical_carrier_source_sha256=(self.canonical_carrier_source_sha256),
            source_id_sha256=self.source_id_sha256,
            polymer_sequence_projection_sha256=(
                self.polymer_sequence_projection_sha256
            ),
            nonpoly_identity_record_state_sha256=(
                self.nonpoly_identity_record_state_sha256
            ),
        )
        if self.source_binding_sha256 != expected_binding:
            raise ValueError("polymer ingest source binding is inconsistent")

        fresh = _validated_components
        fresh_system_payload = None
        if fresh is None:
            try:
                fresh = _parse_components(
                    self._full_source_bytes,
                    source_id=system.provenance.source_id,
                )
                fresh_system_payload = serialize_all_atom_system(
                    fresh.base_ingest.system
                )
            except Exception:
                pass
        else:
            try:
                fresh_system_payload = serialize_all_atom_system(
                    fresh.base_ingest.system
                )
            except Exception:
                pass
        if fresh is None or fresh_system_payload is None:
            raise ValueError("polymer ingest source cannot be reconstructed")
        if not all(
            (
                fresh.block_name == self.data_block_name,
                fresh.full_source_bytes == self._full_source_bytes,
                fresh.carrier_source_bytes == self._carrier_source_bytes,
                fresh.canonical_carrier_source_bytes
                == self._canonical_carrier_source_bytes,
                fresh_system_payload == self._system_snapshot_payload,
                fresh.sequence_rows == self.sequence_rows,
                fresh.base_ingest.coverage == self._base_coverage,
                fresh.base_ingest.missingness_evidence
                == self._base_missingness_evidence,
                fresh.nonpoly_ingest == self._nonpoly_ingest,
            )
        ):
            raise ValueError("polymer ingest source artifacts are inconsistent")

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        observed_count = sum(row.coordinate_observed for row in self.sequence_rows)
        document: dict[str, Any] = {
            "schema_id": MMCIF_POLYMER_SEQUENCE_RECORD_STATE_SCHEMA_ID,
            "profile_id": MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
            "envelope_version": MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
            "parser_version": MMCIF_POLYMER_SEQUENCE_PARSER_VERSION,
            "carrier_kind": self.carrier_kind,
            "full_source_sha256": self.full_source_sha256,
            "carrier_source_sha256": self.carrier_source_sha256,
            "canonical_carrier_source_sha256": (self.canonical_carrier_source_sha256),
            "base_system_snapshot_sha256": self.base_system_snapshot_sha256,
            "base_topology_sha256": self.base_topology_sha256,
            "base_representable_state_sha256": (self.base_representable_state_sha256),
            "polymer_sequence_projection_sha256": (
                self.polymer_sequence_projection_sha256
            ),
            "nonpoly_identity_projection_sha256": (
                self.nonpoly_identity_projection_sha256
            ),
            "nonpoly_identity_record_state_sha256": (
                self.nonpoly_identity_record_state_sha256
            ),
            "record_state_sha256": self.record_state_sha256,
            "source_id_sha256": self.source_id_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "polymer_sequence_row_count": len(self.sequence_rows),
            "coordinate_observed_sequence_row_count": observed_count,
            "coordinate_unobserved_sequence_row_count": (
                len(self.sequence_rows) - observed_count
            ),
            "source_reported_sequence_preserved": True,
            "coordinate_absent_rows_preserved_without_missingness_claim": True,
        }
        document.update(_authority_false_document())
        return document


def _ingest_from_components(
    components: _ParsedComponents,
) -> MmcifPolymerSequenceIngestResult:
    system = components.base_ingest.system
    projection_sha = _projection_sha256(components.sequence_rows)
    nonpoly_projection_sha = (
        None
        if components.nonpoly_ingest is None
        else components.nonpoly_ingest.identity_projection_sha256
    )
    nonpoly_state_sha = (
        None
        if components.nonpoly_ingest is None
        else components.nonpoly_ingest.record_state_sha256
    )
    representable_sha = mmcif_representable_state_sha256(system)
    full_source_sha = hashlib.sha256(components.full_source_bytes).hexdigest()
    carrier_source_sha = hashlib.sha256(components.carrier_source_bytes).hexdigest()
    canonical_carrier_sha = hashlib.sha256(
        components.canonical_carrier_source_bytes
    ).hexdigest()
    source_id_sha = hashlib.sha256(
        system.provenance.source_id.encode("utf-8")
    ).hexdigest()
    return MmcifPolymerSequenceIngestResult(
        system=system,
        base_ingest=components.base_ingest,
        nonpoly_ingest=components.nonpoly_ingest,
        sequence_rows=components.sequence_rows,
        data_block_name=components.block_name,
        carrier_kind=(
            "common_core21"
            if components.nonpoly_ingest is None
            else "mmcif_nonpoly_identity"
        ),
        full_source_bytes=components.full_source_bytes,
        carrier_source_bytes=components.carrier_source_bytes,
        canonical_carrier_source_bytes=(components.canonical_carrier_source_bytes),
        full_source_sha256=full_source_sha,
        carrier_source_sha256=carrier_source_sha,
        canonical_carrier_source_sha256=canonical_carrier_sha,
        base_system_snapshot_sha256=canonical_all_atom_snapshot_digest(system),
        base_topology_sha256=canonical_topology_sha256(system),
        base_representable_state_sha256=representable_sha,
        polymer_sequence_projection_sha256=projection_sha,
        nonpoly_identity_projection_sha256=nonpoly_projection_sha,
        nonpoly_identity_record_state_sha256=nonpoly_state_sha,
        record_state_sha256=_record_state_sha256(
            base_representable_state_sha256=representable_sha,
            polymer_sequence_projection_sha256=projection_sha,
            nonpoly_identity_record_state_sha256=nonpoly_state_sha,
        ),
        source_id_sha256=source_id_sha,
        source_binding_sha256=_source_binding_sha256(
            full_source_sha256=full_source_sha,
            normalized_carrier_source_sha256=carrier_source_sha,
            canonical_carrier_source_sha256=canonical_carrier_sha,
            source_id_sha256=source_id_sha,
            polymer_sequence_projection_sha256=projection_sha,
            nonpoly_identity_record_state_sha256=nonpoly_state_sha,
        ),
        _validated_components=components,
        _factory_token=_FACTORY_TOKEN,
    )


def parse_mmcif_polymer_sequence(
    data: bytes,
    *,
    source_id: str = "",
) -> MmcifPolymerSequenceIngestResult:
    """Parse the exact common-core21 plus entity-poly-seq envelope."""

    return _ingest_from_components(_parse_components(data, source_id=source_id))


def _validate_fresh_ingest(
    ingest: MmcifPolymerSequenceIngestResult,
) -> tuple[AllAtomSystem, Any]:
    if type(ingest) is not MmcifPolymerSequenceIngestResult:
        raise TypeError("ingest must be an MmcifPolymerSequenceIngestResult")
    system = None
    try:
        ingest.__post_init__()
        system = ingest.system
    except Exception:
        pass
    if system is None:
        raise MmcifPolymerSequenceError(
            "stale_ingest_binding",
            "the bound ingest artifact no longer validates",
        )

    if ingest._nonpoly_ingest is None:
        carrier_write, writer_code = _try_write_base(system)
    else:
        try:
            nonpoly_system_payload = serialize_all_atom_system(
                ingest._nonpoly_ingest.system
            )
        except Exception:
            nonpoly_system_payload = None
        if nonpoly_system_payload != ingest._system_snapshot_payload:
            raise MmcifPolymerSequenceError(
                "stale_composed_carrier",
                "the nonpoly carrier no longer binds the base molecular snapshot",
            )
        carrier_write, writer_code = _try_write_nonpoly(ingest._nonpoly_ingest)
    if carrier_write is None:
        raise MmcifPolymerSequenceError(
            "stale_carrier_state",
            f"the exact carrier writer rejected the bound state ({writer_code})",
        )
    if carrier_write.payload != ingest._canonical_carrier_source_bytes:
        raise MmcifPolymerSequenceError(
            "stale_carrier_state",
            "the current carrier emission differs from the bound canonical carrier",
        )

    return system, carrier_write


def mmcif_polymer_sequence_projection_sha256(
    ingest: MmcifPolymerSequenceIngestResult,
) -> str:
    """Revalidate and return the source-reported sequence projection digest."""

    _validate_fresh_ingest(ingest)
    return _projection_sha256(ingest.sequence_rows)


def mmcif_polymer_sequence_record_state_sha256(
    ingest: MmcifPolymerSequenceIngestResult,
) -> str:
    """Revalidate and return the combined base/sequence/nonpoly state digest."""

    system, _ = _validate_fresh_ingest(ingest)
    return _record_state_sha256(
        base_representable_state_sha256=mmcif_representable_state_sha256(system),
        polymer_sequence_projection_sha256=_projection_sha256(ingest.sequence_rows),
        nonpoly_identity_record_state_sha256=(
            ingest.nonpoly_identity_record_state_sha256
        ),
    )


def _emit_sequence_loop(
    rows: tuple[MmcifPolymerSequenceRow, ...],
) -> bytes:
    lines = ["loop_", *MMCIF_ENTITY_POLY_SEQ_HEADERS]
    for row in rows:
        values = [row.entity_id, str(row.num), row.mon_id, "n"]
        joined = " ".join(values)
        lines.extend((joined,) if len(joined) <= 2_048 else values)
    lines.append("#")
    return ("\n".join(lines) + "\n").encode("ascii")


def _compose_output(
    *,
    data_block_name: str,
    carrier_kind: str,
    sequence_rows: tuple[MmcifPolymerSequenceRow, ...],
    canonical_carrier_source: bytes,
) -> bytes:
    carrier_block, syntax_code, _ = _try_parse_block(
        canonical_carrier_source.decode("ascii")
    )
    if carrier_block is None:
        raise MmcifPolymerSequenceError(
            "invalid_canonical_carrier",
            f"canonical carrier failed CIF syntax validation ({syntax_code})",
        )
    if carrier_block.name != data_block_name:
        raise MmcifPolymerSequenceError(
            "invalid_canonical_carrier",
            "canonical carrier data-block binding differs from the ingest",
        )
    expected_carrier_categories = (
        ("_entity", "_struct_asym", "_atom_site")
        if carrier_kind == "common_core21"
        else (
            "_entity",
            "_struct_asym",
            "_pdbx_entity_nonpoly",
            "_pdbx_nonpoly_scheme",
            "_atom_site",
        )
    )
    if (
        carrier_block.categories != expected_carrier_categories
        or carrier_block.scalar_values
    ):
        raise MmcifPolymerSequenceError(
            "invalid_canonical_carrier",
            "canonical carrier category order is outside the exact profile",
        )
    loops = {
        category: _loop_for(carrier_block, category)
        for category in carrier_block.categories
    }
    order = (
        _CANONICAL_BASE_ORDER
        if carrier_kind == "common_core21"
        else _CANONICAL_NONPOLY_ORDER
    )
    parts = [f"data_{carrier_block.name}\n#\n".encode("ascii")]
    for category in order:
        if category == "_entity_poly_seq":
            parts.append(_emit_sequence_loop(sequence_rows))
        else:
            parts.append(_emit_loop(loops[category]))
    payload = b"".join(parts)
    if len(payload) > MAX_MMCIF_POLYMER_SEQUENCE_INPUT_BYTES:
        raise MmcifPolymerSequenceError(
            "output_too_large", "canonical output exceeds the fixed byte cap"
        )
    block, syntax_code, _ = _try_parse_block(payload.decode("ascii"))
    expected_order = (
        _CANONICAL_BASE_ORDER
        if carrier_kind == "common_core21"
        else _CANONICAL_NONPOLY_ORDER
    )
    if (
        block is None
        or block.categories != expected_order
        or block.scalar_values
        or len(block.loops) != len(expected_order)
    ):
        raise MmcifPolymerSequenceError(
            "invalid_canonical_output",
            f"canonical output failed exact-surface validation ({syntax_code})",
        )
    _require_headers(
        _loop_for(block, "_entity_poly_seq"), MMCIF_ENTITY_POLY_SEQ_HEADERS
    )
    return payload


def _receipt_payload(
    receipt: "MmcifPolymerSequenceWriteReceipt",
) -> dict[str, Any]:
    return {
        "schema_id": receipt.schema_id,
        "envelope_version": receipt.envelope_version,
        "writer_version": receipt.writer_version,
        "profile_id": receipt.profile_id,
        "carrier_kind": receipt.carrier_kind,
        "input_full_source_sha256": receipt.input_full_source_sha256,
        "input_carrier_source_sha256": receipt.input_carrier_source_sha256,
        "input_canonical_carrier_source_sha256": (
            receipt.input_canonical_carrier_source_sha256
        ),
        "input_base_system_snapshot_sha256": (
            receipt.input_base_system_snapshot_sha256
        ),
        "input_base_topology_sha256": receipt.input_base_topology_sha256,
        "input_base_representable_state_sha256": (
            receipt.input_base_representable_state_sha256
        ),
        "input_polymer_sequence_projection_sha256": (
            receipt.input_polymer_sequence_projection_sha256
        ),
        "input_nonpoly_identity_projection_sha256": (
            receipt.input_nonpoly_identity_projection_sha256
        ),
        "input_nonpoly_identity_record_state_sha256": (
            receipt.input_nonpoly_identity_record_state_sha256
        ),
        "input_record_state_sha256": receipt.input_record_state_sha256,
        "input_source_id_sha256": receipt.input_source_id_sha256,
        "input_source_binding_sha256": receipt.input_source_binding_sha256,
        "carrier_writer_receipt_sha256": receipt.carrier_writer_receipt_sha256,
        "output_source_sha256": receipt.output_source_sha256,
        "output_byte_count": receipt.output_byte_count,
        "polymer_sequence_row_count": receipt.polymer_sequence_row_count,
        "coordinate_observed_sequence_row_count": (
            receipt.coordinate_observed_sequence_row_count
        ),
        "coordinate_unobserved_sequence_row_count": (
            receipt.coordinate_unobserved_sequence_row_count
        ),
    }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifPolymerSequenceWriteReceipt:
    """Factory-only binding for one canonical polymer-sequence emission."""

    schema_id: str
    envelope_version: str
    writer_version: str
    profile_id: str
    carrier_kind: str
    input_full_source_sha256: str
    input_carrier_source_sha256: str
    input_canonical_carrier_source_sha256: str
    input_base_system_snapshot_sha256: str
    input_base_topology_sha256: str
    input_base_representable_state_sha256: str
    input_polymer_sequence_projection_sha256: str
    input_nonpoly_identity_projection_sha256: str | None
    input_nonpoly_identity_record_state_sha256: str | None
    input_record_state_sha256: str
    input_source_id_sha256: str
    input_source_binding_sha256: str
    carrier_writer_receipt_sha256: str
    output_source_sha256: str
    output_byte_count: int
    polymer_sequence_row_count: int
    coordinate_observed_sequence_row_count: int
    coordinate_unobserved_sequence_row_count: int
    receipt_sha256: str

    def __init__(
        self,
        *,
        schema_id: Any = None,
        envelope_version: Any = None,
        writer_version: Any = None,
        profile_id: Any = None,
        carrier_kind: Any = None,
        input_full_source_sha256: Any = None,
        input_carrier_source_sha256: Any = None,
        input_canonical_carrier_source_sha256: Any = None,
        input_base_system_snapshot_sha256: Any = None,
        input_base_topology_sha256: Any = None,
        input_base_representable_state_sha256: Any = None,
        input_polymer_sequence_projection_sha256: Any = None,
        input_nonpoly_identity_projection_sha256: Any = None,
        input_nonpoly_identity_record_state_sha256: Any = None,
        input_record_state_sha256: Any = None,
        input_source_id_sha256: Any = None,
        input_source_binding_sha256: Any = None,
        carrier_writer_receipt_sha256: Any = None,
        output_source_sha256: Any = None,
        output_byte_count: Any = None,
        polymer_sequence_row_count: Any = None,
        coordinate_observed_sequence_row_count: Any = None,
        coordinate_unobserved_sequence_row_count: Any = None,
        receipt_sha256: Any = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifPolymerSequenceWriteReceipt is factory-only")
        for field_name, value in (
            ("schema_id", schema_id),
            ("envelope_version", envelope_version),
            ("writer_version", writer_version),
            ("profile_id", profile_id),
            ("carrier_kind", carrier_kind),
            ("input_full_source_sha256", input_full_source_sha256),
            ("input_carrier_source_sha256", input_carrier_source_sha256),
            (
                "input_canonical_carrier_source_sha256",
                input_canonical_carrier_source_sha256,
            ),
            (
                "input_base_system_snapshot_sha256",
                input_base_system_snapshot_sha256,
            ),
            ("input_base_topology_sha256", input_base_topology_sha256),
            (
                "input_base_representable_state_sha256",
                input_base_representable_state_sha256,
            ),
            (
                "input_polymer_sequence_projection_sha256",
                input_polymer_sequence_projection_sha256,
            ),
            (
                "input_nonpoly_identity_projection_sha256",
                input_nonpoly_identity_projection_sha256,
            ),
            (
                "input_nonpoly_identity_record_state_sha256",
                input_nonpoly_identity_record_state_sha256,
            ),
            ("input_record_state_sha256", input_record_state_sha256),
            ("input_source_id_sha256", input_source_id_sha256),
            ("input_source_binding_sha256", input_source_binding_sha256),
            ("carrier_writer_receipt_sha256", carrier_writer_receipt_sha256),
            ("output_source_sha256", output_source_sha256),
            ("output_byte_count", output_byte_count),
            ("polymer_sequence_row_count", polymer_sequence_row_count),
            (
                "coordinate_observed_sequence_row_count",
                coordinate_observed_sequence_row_count,
            ),
            (
                "coordinate_unobserved_sequence_row_count",
                coordinate_unobserved_sequence_row_count,
            ),
            ("receipt_sha256", receipt_sha256),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.schema_id != MMCIF_POLYMER_SEQUENCE_WRITE_RECEIPT_SCHEMA_ID:
            raise ValueError("polymer write receipt schema is inconsistent")
        if self.envelope_version != MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION:
            raise ValueError("polymer write receipt envelope is inconsistent")
        if self.writer_version != MMCIF_POLYMER_SEQUENCE_WRITER_VERSION:
            raise ValueError("polymer write receipt writer is inconsistent")
        if self.profile_id != MMCIF_POLYMER_SEQUENCE_PROFILE_ID:
            raise ValueError("polymer write receipt profile is inconsistent")
        if self.carrier_kind not in {"common_core21", "mmcif_nonpoly_identity"}:
            raise ValueError("polymer write receipt carrier kind is inconsistent")
        for field_name in (
            "input_full_source_sha256",
            "input_carrier_source_sha256",
            "input_canonical_carrier_source_sha256",
            "input_base_system_snapshot_sha256",
            "input_base_topology_sha256",
            "input_base_representable_state_sha256",
            "input_polymer_sequence_projection_sha256",
            "input_record_state_sha256",
            "input_source_id_sha256",
            "input_source_binding_sha256",
            "carrier_writer_receipt_sha256",
            "output_source_sha256",
            "receipt_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        for field_name in (
            "input_nonpoly_identity_projection_sha256",
            "input_nonpoly_identity_record_state_sha256",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _require_sha256(value, field_name=field_name)
        composed = self.carrier_kind == "mmcif_nonpoly_identity"
        if composed != (
            self.input_nonpoly_identity_projection_sha256 is not None
            and self.input_nonpoly_identity_record_state_sha256 is not None
        ):
            raise ValueError("polymer write receipt composition is inconsistent")
        expected_record_state = _record_state_sha256(
            base_representable_state_sha256=(
                self.input_base_representable_state_sha256
            ),
            polymer_sequence_projection_sha256=(
                self.input_polymer_sequence_projection_sha256
            ),
            nonpoly_identity_record_state_sha256=(
                self.input_nonpoly_identity_record_state_sha256
            ),
        )
        if self.input_record_state_sha256 != expected_record_state:
            raise ValueError("polymer write receipt record state is inconsistent")
        expected_source_binding = _source_binding_sha256(
            full_source_sha256=self.input_full_source_sha256,
            normalized_carrier_source_sha256=(self.input_carrier_source_sha256),
            canonical_carrier_source_sha256=(
                self.input_canonical_carrier_source_sha256
            ),
            source_id_sha256=self.input_source_id_sha256,
            polymer_sequence_projection_sha256=(
                self.input_polymer_sequence_projection_sha256
            ),
            nonpoly_identity_record_state_sha256=(
                self.input_nonpoly_identity_record_state_sha256
            ),
        )
        if self.input_source_binding_sha256 != expected_source_binding:
            raise ValueError("polymer write receipt source binding is inconsistent")
        for field_name in (
            "output_byte_count",
            "polymer_sequence_row_count",
            "coordinate_observed_sequence_row_count",
            "coordinate_unobserved_sequence_row_count",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise TypeError(f"{field_name} must be a nonnegative integer")
        if not 1 <= self.output_byte_count <= MAX_MMCIF_POLYMER_SEQUENCE_INPUT_BYTES:
            raise ValueError("polymer write receipt output size is outside the cap")
        if (
            not 1
            <= self.polymer_sequence_row_count
            <= (MAX_MMCIF_POLYMER_SEQUENCE_ROWS)
        ):
            raise ValueError("polymer write receipt sequence count is outside the cap")
        if self.polymer_sequence_row_count != (
            self.coordinate_observed_sequence_row_count
            + self.coordinate_unobserved_sequence_row_count
        ):
            raise ValueError("polymer write receipt sequence counts are inconsistent")
        if self.receipt_sha256 != _sha256_document(_receipt_payload(self)):
            raise ValueError("polymer write receipt digest is inconsistent")

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        document = _receipt_payload(self)
        document["receipt_sha256"] = self.receipt_sha256
        document["source_reported_sequence_preserved"] = True
        document["coordinate_absent_rows_preserved_without_missingness_claim"] = True
        document.update(_authority_false_document())
        return document


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifPolymerSequenceWriteResult:
    """Canonical bytes paired with their factory-only write receipt."""

    payload: bytes
    receipt: MmcifPolymerSequenceWriteReceipt

    def __init__(
        self,
        *,
        payload: bytes,
        receipt: MmcifPolymerSequenceWriteReceipt,
        _validated_components: _ParsedComponents | None = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifPolymerSequenceWriteResult is factory-only")
        if (
            _validated_components is not None
            and type(_validated_components) is not _ParsedComponents
        ):
            raise TypeError("validated components must use the internal exact type")
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "receipt", receipt)
        self.__post_init__(_validated_components=_validated_components)

    def __post_init__(
        self,
        *,
        _validated_components: _ParsedComponents | None = None,
    ) -> None:
        if type(self.payload) is not bytes:
            raise TypeError("polymer write payload must be bytes")
        if type(self.receipt) is not MmcifPolymerSequenceWriteReceipt:
            raise TypeError("polymer write result must contain its typed receipt")
        self.receipt.__post_init__()
        if len(self.payload) != self.receipt.output_byte_count:
            raise ValueError("polymer write payload byte count is inconsistent")
        if hashlib.sha256(self.payload).hexdigest() != (
            self.receipt.output_source_sha256
        ):
            raise ValueError("polymer write payload digest is inconsistent")
        components = _validated_components
        if components is None:
            try:
                components = _parse_components(self.payload, source_id="")
            except Exception:
                pass
        if components is None:
            raise ValueError(
                "polymer write payload is outside the exact parseable envelope"
            )
        observed_count = sum(
            row.coordinate_observed for row in components.sequence_rows
        )
        carrier_kind = (
            "common_core21"
            if components.nonpoly_ingest is None
            else "mmcif_nonpoly_identity"
        )
        base_system = components.base_ingest.system
        output_projection_sha256 = _projection_sha256(components.sequence_rows)
        output_nonpoly_projection_sha256 = (
            None
            if components.nonpoly_ingest is None
            else components.nonpoly_ingest.identity_projection_sha256
        )
        output_nonpoly_record_state_sha256 = (
            None
            if components.nonpoly_ingest is None
            else components.nonpoly_ingest.record_state_sha256
        )
        output_record_state_sha256 = _record_state_sha256(
            base_representable_state_sha256=mmcif_representable_state_sha256(
                base_system
            ),
            polymer_sequence_projection_sha256=output_projection_sha256,
            nonpoly_identity_record_state_sha256=(output_nonpoly_record_state_sha256),
        )
        canonical_payload = _compose_output(
            data_block_name=components.block_name,
            carrier_kind=carrier_kind,
            sequence_rows=components.sequence_rows,
            canonical_carrier_source=components.canonical_carrier_source_bytes,
        )
        if (
            carrier_kind != self.receipt.carrier_kind
            or len(components.sequence_rows) != self.receipt.polymer_sequence_row_count
            or observed_count != self.receipt.coordinate_observed_sequence_row_count
            or self.payload != canonical_payload
            or hashlib.sha256(components.canonical_carrier_source_bytes).hexdigest()
            != self.receipt.input_canonical_carrier_source_sha256
            or canonical_topology_sha256(base_system)
            != self.receipt.input_base_topology_sha256
            or mmcif_representable_state_sha256(base_system)
            != self.receipt.input_base_representable_state_sha256
            or output_projection_sha256
            != self.receipt.input_polymer_sequence_projection_sha256
            or output_nonpoly_projection_sha256
            != self.receipt.input_nonpoly_identity_projection_sha256
            or output_nonpoly_record_state_sha256
            != self.receipt.input_nonpoly_identity_record_state_sha256
            or output_record_state_sha256 != self.receipt.input_record_state_sha256
        ):
            raise ValueError("polymer write payload state binding is inconsistent")


def _make_write_receipt(
    *,
    ingest: MmcifPolymerSequenceIngestResult,
    carrier_writer_receipt_sha256: str,
    payload: bytes,
) -> MmcifPolymerSequenceWriteReceipt:
    observed_count = sum(row.coordinate_observed for row in ingest.sequence_rows)
    values: dict[str, Any] = {
        "schema_id": MMCIF_POLYMER_SEQUENCE_WRITE_RECEIPT_SCHEMA_ID,
        "envelope_version": MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
        "writer_version": MMCIF_POLYMER_SEQUENCE_WRITER_VERSION,
        "profile_id": MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
        "carrier_kind": ingest.carrier_kind,
        "input_full_source_sha256": ingest.full_source_sha256,
        "input_carrier_source_sha256": ingest.carrier_source_sha256,
        "input_canonical_carrier_source_sha256": (
            ingest.canonical_carrier_source_sha256
        ),
        "input_base_system_snapshot_sha256": (ingest.base_system_snapshot_sha256),
        "input_base_topology_sha256": ingest.base_topology_sha256,
        "input_base_representable_state_sha256": (
            ingest.base_representable_state_sha256
        ),
        "input_polymer_sequence_projection_sha256": (
            ingest.polymer_sequence_projection_sha256
        ),
        "input_nonpoly_identity_projection_sha256": (
            ingest.nonpoly_identity_projection_sha256
        ),
        "input_nonpoly_identity_record_state_sha256": (
            ingest.nonpoly_identity_record_state_sha256
        ),
        "input_record_state_sha256": ingest.record_state_sha256,
        "input_source_id_sha256": ingest.source_id_sha256,
        "input_source_binding_sha256": ingest.source_binding_sha256,
        "carrier_writer_receipt_sha256": carrier_writer_receipt_sha256,
        "output_source_sha256": hashlib.sha256(payload).hexdigest(),
        "output_byte_count": len(payload),
        "polymer_sequence_row_count": len(ingest.sequence_rows),
        "coordinate_observed_sequence_row_count": observed_count,
        "coordinate_unobserved_sequence_row_count": (
            len(ingest.sequence_rows) - observed_count
        ),
    }
    provisional = type("_PolymerSequenceReceiptDocument", (), values)()
    values["receipt_sha256"] = _sha256_document(_receipt_payload(provisional))
    return MmcifPolymerSequenceWriteReceipt(
        **values,
        _factory_token=_FACTORY_TOKEN,
    )


def emit_mmcif_polymer_sequence(
    ingest: MmcifPolymerSequenceIngestResult,
) -> MmcifPolymerSequenceWriteResult:
    """Emit the canonical exact envelope after revalidating every binding."""

    system, carrier_write = _validate_fresh_ingest(ingest)
    payload = _compose_output(
        data_block_name=ingest.data_block_name,
        carrier_kind=ingest.carrier_kind,
        sequence_rows=ingest.sequence_rows,
        canonical_carrier_source=carrier_write.payload,
    )
    output_components = None
    try:
        output_components = _parse_components(
            payload,
            source_id=system.provenance.source_id,
        )
    except Exception:
        pass
    if output_components is None:
        raise MmcifPolymerSequenceError(
            "invalid_canonical_output",
            "canonical output failed exact-envelope revalidation",
        )
    output_nonpoly_state = (
        None
        if output_components.nonpoly_ingest is None
        else output_components.nonpoly_ingest.record_state_sha256
    )
    output_projection_sha = _projection_sha256(output_components.sequence_rows)
    output_state_sha = _record_state_sha256(
        base_representable_state_sha256=mmcif_representable_state_sha256(
            output_components.base_ingest.system
        ),
        polymer_sequence_projection_sha256=output_projection_sha,
        nonpoly_identity_record_state_sha256=output_nonpoly_state,
    )
    if not all(
        (
            output_components.sequence_rows == ingest.sequence_rows,
            output_projection_sha == ingest.polymer_sequence_projection_sha256,
            output_nonpoly_state == ingest.nonpoly_identity_record_state_sha256,
            output_state_sha == ingest.record_state_sha256,
            output_components.canonical_carrier_source_bytes == carrier_write.payload,
        )
    ):
        raise MmcifPolymerSequenceError(
            "canonical_output_state_mismatch",
            "canonical output did not preserve the bound combined record state",
        )
    receipt = _make_write_receipt(
        ingest=ingest,
        carrier_writer_receipt_sha256=carrier_write.receipt.receipt_sha256,
        payload=payload,
    )
    return MmcifPolymerSequenceWriteResult(
        payload=payload,
        receipt=receipt,
        _validated_components=output_components,
        _factory_token=_FACTORY_TOKEN,
    )


def serialize_mmcif_polymer_sequence(
    ingest: MmcifPolymerSequenceIngestResult,
) -> bytes:
    """Return only canonical bytes while retaining emit-time validation."""

    return emit_mmcif_polymer_sequence(ingest).payload


def _report_payload(
    report: "MmcifPolymerSequenceRoundTripReport",
) -> dict[str, Any]:
    return {
        "schema_id": report.schema_id,
        "envelope_version": report.envelope_version,
        "profile_id": report.profile_id,
        "input_full_source_sha256": report.input_full_source_sha256,
        "reparsed_full_source_sha256": report.reparsed_full_source_sha256,
        "input_source_binding_sha256": report.input_source_binding_sha256,
        "reparsed_source_binding_sha256": report.reparsed_source_binding_sha256,
        "writer_receipt_sha256": report.writer_receipt_sha256,
        "reemitted_writer_receipt_sha256": (report.reemitted_writer_receipt_sha256),
        "input_carrier_kind": report.input_carrier_kind,
        "reparsed_carrier_kind": report.reparsed_carrier_kind,
        "input_source_id_sha256": report.input_source_id_sha256,
        "reparsed_source_id_sha256": report.reparsed_source_id_sha256,
        "input_polymer_sequence_projection_sha256": (
            report.input_polymer_sequence_projection_sha256
        ),
        "reparsed_polymer_sequence_projection_sha256": (
            report.reparsed_polymer_sequence_projection_sha256
        ),
        "input_nonpoly_identity_projection_sha256": (
            report.input_nonpoly_identity_projection_sha256
        ),
        "reparsed_nonpoly_identity_projection_sha256": (
            report.reparsed_nonpoly_identity_projection_sha256
        ),
        "input_nonpoly_identity_record_state_sha256": (
            report.input_nonpoly_identity_record_state_sha256
        ),
        "reparsed_nonpoly_identity_record_state_sha256": (
            report.reparsed_nonpoly_identity_record_state_sha256
        ),
        "input_record_state_sha256": report.input_record_state_sha256,
        "reparsed_record_state_sha256": report.reparsed_record_state_sha256,
        "emitted_source_sha256": report.emitted_source_sha256,
        "reemitted_source_sha256": report.reemitted_source_sha256,
        "carrier_kind_equal": report.carrier_kind_equal,
        "source_id_sha256_equal": report.source_id_sha256_equal,
        "polymer_sequence_projection_sha256_equal": (
            report.polymer_sequence_projection_sha256_equal
        ),
        "nonpoly_identity_projection_sha256_equal": (
            report.nonpoly_identity_projection_sha256_equal
        ),
        "nonpoly_identity_record_state_sha256_equal": (
            report.nonpoly_identity_record_state_sha256_equal
        ),
        "record_state_sha256_equal": report.record_state_sha256_equal,
        "second_emission_byte_stable": report.second_emission_byte_stable,
    }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifPolymerSequenceRoundTripReport:
    """Value-free evidence for one stable parse/emit/reparse/emit cycle."""

    schema_id: str
    envelope_version: str
    profile_id: str
    input_full_source_sha256: str
    reparsed_full_source_sha256: str
    input_source_binding_sha256: str
    reparsed_source_binding_sha256: str
    writer_receipt_sha256: str
    reemitted_writer_receipt_sha256: str
    input_carrier_kind: str
    reparsed_carrier_kind: str
    input_source_id_sha256: str
    reparsed_source_id_sha256: str
    input_polymer_sequence_projection_sha256: str
    reparsed_polymer_sequence_projection_sha256: str
    input_nonpoly_identity_projection_sha256: str | None
    reparsed_nonpoly_identity_projection_sha256: str | None
    input_nonpoly_identity_record_state_sha256: str | None
    reparsed_nonpoly_identity_record_state_sha256: str | None
    input_record_state_sha256: str
    reparsed_record_state_sha256: str
    emitted_source_sha256: str
    reemitted_source_sha256: str
    carrier_kind_equal: bool
    source_id_sha256_equal: bool
    polymer_sequence_projection_sha256_equal: bool
    nonpoly_identity_projection_sha256_equal: bool
    nonpoly_identity_record_state_sha256_equal: bool
    record_state_sha256_equal: bool
    second_emission_byte_stable: bool
    report_sha256: str

    def __init__(
        self,
        *,
        schema_id: Any = None,
        envelope_version: Any = None,
        profile_id: Any = None,
        input_full_source_sha256: Any = None,
        reparsed_full_source_sha256: Any = None,
        input_source_binding_sha256: Any = None,
        reparsed_source_binding_sha256: Any = None,
        writer_receipt_sha256: Any = None,
        reemitted_writer_receipt_sha256: Any = None,
        input_carrier_kind: Any = None,
        reparsed_carrier_kind: Any = None,
        input_source_id_sha256: Any = None,
        reparsed_source_id_sha256: Any = None,
        input_polymer_sequence_projection_sha256: Any = None,
        reparsed_polymer_sequence_projection_sha256: Any = None,
        input_nonpoly_identity_projection_sha256: Any = None,
        reparsed_nonpoly_identity_projection_sha256: Any = None,
        input_nonpoly_identity_record_state_sha256: Any = None,
        reparsed_nonpoly_identity_record_state_sha256: Any = None,
        input_record_state_sha256: Any = None,
        reparsed_record_state_sha256: Any = None,
        emitted_source_sha256: Any = None,
        reemitted_source_sha256: Any = None,
        carrier_kind_equal: Any = None,
        source_id_sha256_equal: Any = None,
        polymer_sequence_projection_sha256_equal: Any = None,
        nonpoly_identity_projection_sha256_equal: Any = None,
        nonpoly_identity_record_state_sha256_equal: Any = None,
        record_state_sha256_equal: Any = None,
        second_emission_byte_stable: Any = None,
        report_sha256: Any = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifPolymerSequenceRoundTripReport is factory-only")
        for field_name, value in (
            ("schema_id", schema_id),
            ("envelope_version", envelope_version),
            ("profile_id", profile_id),
            ("input_full_source_sha256", input_full_source_sha256),
            ("reparsed_full_source_sha256", reparsed_full_source_sha256),
            ("input_source_binding_sha256", input_source_binding_sha256),
            ("reparsed_source_binding_sha256", reparsed_source_binding_sha256),
            ("writer_receipt_sha256", writer_receipt_sha256),
            ("reemitted_writer_receipt_sha256", reemitted_writer_receipt_sha256),
            ("input_carrier_kind", input_carrier_kind),
            ("reparsed_carrier_kind", reparsed_carrier_kind),
            ("input_source_id_sha256", input_source_id_sha256),
            ("reparsed_source_id_sha256", reparsed_source_id_sha256),
            (
                "input_polymer_sequence_projection_sha256",
                input_polymer_sequence_projection_sha256,
            ),
            (
                "reparsed_polymer_sequence_projection_sha256",
                reparsed_polymer_sequence_projection_sha256,
            ),
            (
                "input_nonpoly_identity_projection_sha256",
                input_nonpoly_identity_projection_sha256,
            ),
            (
                "reparsed_nonpoly_identity_projection_sha256",
                reparsed_nonpoly_identity_projection_sha256,
            ),
            (
                "input_nonpoly_identity_record_state_sha256",
                input_nonpoly_identity_record_state_sha256,
            ),
            (
                "reparsed_nonpoly_identity_record_state_sha256",
                reparsed_nonpoly_identity_record_state_sha256,
            ),
            ("input_record_state_sha256", input_record_state_sha256),
            ("reparsed_record_state_sha256", reparsed_record_state_sha256),
            ("emitted_source_sha256", emitted_source_sha256),
            ("reemitted_source_sha256", reemitted_source_sha256),
            ("carrier_kind_equal", carrier_kind_equal),
            ("source_id_sha256_equal", source_id_sha256_equal),
            (
                "polymer_sequence_projection_sha256_equal",
                polymer_sequence_projection_sha256_equal,
            ),
            (
                "nonpoly_identity_projection_sha256_equal",
                nonpoly_identity_projection_sha256_equal,
            ),
            (
                "nonpoly_identity_record_state_sha256_equal",
                nonpoly_identity_record_state_sha256_equal,
            ),
            ("record_state_sha256_equal", record_state_sha256_equal),
            ("second_emission_byte_stable", second_emission_byte_stable),
            ("report_sha256", report_sha256),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.schema_id != MMCIF_POLYMER_SEQUENCE_ROUND_TRIP_REPORT_SCHEMA_ID:
            raise ValueError("polymer round-trip report schema is inconsistent")
        if self.envelope_version != MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION:
            raise ValueError("polymer round-trip report envelope is inconsistent")
        if self.profile_id != MMCIF_POLYMER_SEQUENCE_PROFILE_ID:
            raise ValueError("polymer round-trip report profile is inconsistent")
        for field_name in (
            "input_full_source_sha256",
            "reparsed_full_source_sha256",
            "input_source_binding_sha256",
            "reparsed_source_binding_sha256",
            "writer_receipt_sha256",
            "reemitted_writer_receipt_sha256",
            "input_source_id_sha256",
            "reparsed_source_id_sha256",
            "input_polymer_sequence_projection_sha256",
            "reparsed_polymer_sequence_projection_sha256",
            "input_record_state_sha256",
            "reparsed_record_state_sha256",
            "emitted_source_sha256",
            "reemitted_source_sha256",
            "report_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        for field_name in (
            "input_nonpoly_identity_projection_sha256",
            "reparsed_nonpoly_identity_projection_sha256",
            "input_nonpoly_identity_record_state_sha256",
            "reparsed_nonpoly_identity_record_state_sha256",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _require_sha256(value, field_name=field_name)
        for field_name in ("input_carrier_kind", "reparsed_carrier_kind"):
            if getattr(self, field_name) not in {
                "common_core21",
                "mmcif_nonpoly_identity",
            }:
                raise ValueError("polymer round-trip carrier kind is inconsistent")
        for prefix in ("input", "reparsed"):
            composed = getattr(self, f"{prefix}_carrier_kind") == (
                "mmcif_nonpoly_identity"
            )
            if composed != (
                getattr(self, f"{prefix}_nonpoly_identity_projection_sha256")
                is not None
                and getattr(self, f"{prefix}_nonpoly_identity_record_state_sha256")
                is not None
            ):
                raise ValueError(
                    "polymer round-trip nonpoly composition is inconsistent"
                )
        equality_fields = {
            "carrier_kind_equal": (
                self.input_carrier_kind == self.reparsed_carrier_kind
            ),
            "source_id_sha256_equal": (
                self.input_source_id_sha256 == self.reparsed_source_id_sha256
            ),
            "polymer_sequence_projection_sha256_equal": (
                self.input_polymer_sequence_projection_sha256
                == self.reparsed_polymer_sequence_projection_sha256
            ),
            "nonpoly_identity_projection_sha256_equal": (
                self.input_nonpoly_identity_projection_sha256
                == self.reparsed_nonpoly_identity_projection_sha256
            ),
            "nonpoly_identity_record_state_sha256_equal": (
                self.input_nonpoly_identity_record_state_sha256
                == self.reparsed_nonpoly_identity_record_state_sha256
            ),
            "record_state_sha256_equal": (
                self.input_record_state_sha256 == self.reparsed_record_state_sha256
            ),
            "second_emission_byte_stable": (
                self.emitted_source_sha256 == self.reemitted_source_sha256
            ),
        }
        for field_name, expected in equality_fields.items():
            value = getattr(self, field_name)
            if type(value) is not bool or value != expected:
                raise ValueError("polymer round-trip equality evidence is inconsistent")
        if not all(equality_fields.values()):
            raise ValueError("polymer round-trip report cannot attest failure")
        if self.report_sha256 != _sha256_document(_report_payload(self)):
            raise ValueError("polymer round-trip report digest is inconsistent")

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        document = _report_payload(self)
        document["report_sha256"] = self.report_sha256
        document["source_reported_sequence_preserved"] = True
        document["coordinate_absent_rows_preserved_without_missingness_claim"] = True
        document.update(_authority_false_document())
        return document


def _make_round_trip_report(
    *,
    source_ingest: MmcifPolymerSequenceIngestResult,
    write_result: MmcifPolymerSequenceWriteResult,
    reparsed_ingest: MmcifPolymerSequenceIngestResult,
    reemitted_write_result: MmcifPolymerSequenceWriteResult,
) -> MmcifPolymerSequenceRoundTripReport:
    values: dict[str, Any] = {
        "schema_id": MMCIF_POLYMER_SEQUENCE_ROUND_TRIP_REPORT_SCHEMA_ID,
        "envelope_version": MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
        "profile_id": MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
        "input_full_source_sha256": source_ingest.full_source_sha256,
        "reparsed_full_source_sha256": reparsed_ingest.full_source_sha256,
        "input_source_binding_sha256": source_ingest.source_binding_sha256,
        "reparsed_source_binding_sha256": reparsed_ingest.source_binding_sha256,
        "writer_receipt_sha256": write_result.receipt.receipt_sha256,
        "reemitted_writer_receipt_sha256": (
            reemitted_write_result.receipt.receipt_sha256
        ),
        "input_carrier_kind": source_ingest.carrier_kind,
        "reparsed_carrier_kind": reparsed_ingest.carrier_kind,
        "input_source_id_sha256": source_ingest.source_id_sha256,
        "reparsed_source_id_sha256": reparsed_ingest.source_id_sha256,
        "input_polymer_sequence_projection_sha256": (
            source_ingest.polymer_sequence_projection_sha256
        ),
        "reparsed_polymer_sequence_projection_sha256": (
            reparsed_ingest.polymer_sequence_projection_sha256
        ),
        "input_nonpoly_identity_projection_sha256": (
            source_ingest.nonpoly_identity_projection_sha256
        ),
        "reparsed_nonpoly_identity_projection_sha256": (
            reparsed_ingest.nonpoly_identity_projection_sha256
        ),
        "input_nonpoly_identity_record_state_sha256": (
            source_ingest.nonpoly_identity_record_state_sha256
        ),
        "reparsed_nonpoly_identity_record_state_sha256": (
            reparsed_ingest.nonpoly_identity_record_state_sha256
        ),
        "input_record_state_sha256": source_ingest.record_state_sha256,
        "reparsed_record_state_sha256": reparsed_ingest.record_state_sha256,
        "emitted_source_sha256": write_result.receipt.output_source_sha256,
        "reemitted_source_sha256": (
            reemitted_write_result.receipt.output_source_sha256
        ),
        "carrier_kind_equal": (
            source_ingest.carrier_kind == reparsed_ingest.carrier_kind
        ),
        "source_id_sha256_equal": (
            source_ingest.source_id_sha256 == reparsed_ingest.source_id_sha256
        ),
        "polymer_sequence_projection_sha256_equal": (
            source_ingest.polymer_sequence_projection_sha256
            == reparsed_ingest.polymer_sequence_projection_sha256
        ),
        "nonpoly_identity_projection_sha256_equal": (
            source_ingest.nonpoly_identity_projection_sha256
            == reparsed_ingest.nonpoly_identity_projection_sha256
        ),
        "nonpoly_identity_record_state_sha256_equal": (
            source_ingest.nonpoly_identity_record_state_sha256
            == reparsed_ingest.nonpoly_identity_record_state_sha256
        ),
        "record_state_sha256_equal": (
            source_ingest.record_state_sha256 == reparsed_ingest.record_state_sha256
        ),
        "second_emission_byte_stable": (
            write_result.payload == reemitted_write_result.payload
        ),
    }
    provisional = type("_PolymerSequenceReportDocument", (), values)()
    values["report_sha256"] = _sha256_document(_report_payload(provisional))
    return MmcifPolymerSequenceRoundTripReport(
        **values,
        _factory_token=_FACTORY_TOKEN,
    )


def _receipt_matches_ingest(
    receipt: MmcifPolymerSequenceWriteReceipt,
    ingest: MmcifPolymerSequenceIngestResult,
    *,
    carrier_writer_receipt_sha256: str,
) -> bool:
    observed_count = sum(row.coordinate_observed for row in ingest.sequence_rows)
    return all(
        (
            receipt.carrier_kind == ingest.carrier_kind,
            receipt.input_full_source_sha256 == ingest.full_source_sha256,
            receipt.input_carrier_source_sha256 == ingest.carrier_source_sha256,
            receipt.input_canonical_carrier_source_sha256
            == ingest.canonical_carrier_source_sha256,
            receipt.input_base_system_snapshot_sha256
            == ingest.base_system_snapshot_sha256,
            receipt.input_base_topology_sha256 == ingest.base_topology_sha256,
            receipt.input_base_representable_state_sha256
            == ingest.base_representable_state_sha256,
            receipt.input_polymer_sequence_projection_sha256
            == ingest.polymer_sequence_projection_sha256,
            receipt.input_nonpoly_identity_projection_sha256
            == ingest.nonpoly_identity_projection_sha256,
            receipt.input_nonpoly_identity_record_state_sha256
            == ingest.nonpoly_identity_record_state_sha256,
            receipt.input_record_state_sha256 == ingest.record_state_sha256,
            receipt.input_source_id_sha256 == ingest.source_id_sha256,
            receipt.input_source_binding_sha256 == ingest.source_binding_sha256,
            receipt.carrier_writer_receipt_sha256 == carrier_writer_receipt_sha256,
            receipt.polymer_sequence_row_count == len(ingest.sequence_rows),
            receipt.coordinate_observed_sequence_row_count == observed_count,
            receipt.coordinate_unobserved_sequence_row_count
            == len(ingest.sequence_rows) - observed_count,
        )
    )


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifPolymerSequenceRoundTripResult:
    """Cross-validated aggregate containing every round-trip artifact."""

    source_ingest: MmcifPolymerSequenceIngestResult
    write_result: MmcifPolymerSequenceWriteResult
    reparsed_ingest: MmcifPolymerSequenceIngestResult
    reemitted_write_result: MmcifPolymerSequenceWriteResult
    report: MmcifPolymerSequenceRoundTripReport

    def __init__(
        self,
        *,
        source_ingest: MmcifPolymerSequenceIngestResult,
        write_result: MmcifPolymerSequenceWriteResult,
        reparsed_ingest: MmcifPolymerSequenceIngestResult,
        reemitted_write_result: MmcifPolymerSequenceWriteResult,
        report: MmcifPolymerSequenceRoundTripReport,
        _source_carrier_writer_receipt_sha256: str | None = None,
        _reparsed_carrier_writer_receipt_sha256: str | None = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifPolymerSequenceRoundTripResult is factory-only")
        for field_name, value in (
            ("source_ingest", source_ingest),
            ("write_result", write_result),
            ("reparsed_ingest", reparsed_ingest),
            ("reemitted_write_result", reemitted_write_result),
            ("report", report),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__(
            _source_carrier_writer_receipt_sha256=(
                _source_carrier_writer_receipt_sha256
            ),
            _reparsed_carrier_writer_receipt_sha256=(
                _reparsed_carrier_writer_receipt_sha256
            ),
        )

    def __post_init__(
        self,
        *,
        _source_carrier_writer_receipt_sha256: str | None = None,
        _reparsed_carrier_writer_receipt_sha256: str | None = None,
    ) -> None:
        if (
            type(self.source_ingest) is not MmcifPolymerSequenceIngestResult
            or type(self.reparsed_ingest) is not MmcifPolymerSequenceIngestResult
        ):
            raise TypeError("round-trip aggregate contains an invalid ingest")
        if (
            type(self.write_result) is not MmcifPolymerSequenceWriteResult
            or type(self.reemitted_write_result) is not MmcifPolymerSequenceWriteResult
        ):
            raise TypeError("round-trip aggregate contains an invalid write result")
        if type(self.report) is not MmcifPolymerSequenceRoundTripReport:
            raise TypeError("round-trip aggregate contains an invalid report")
        prevalidated = (
            _source_carrier_writer_receipt_sha256 is not None
            and _reparsed_carrier_writer_receipt_sha256 is not None
        )
        if prevalidated != (
            _source_carrier_writer_receipt_sha256 is not None
            or _reparsed_carrier_writer_receipt_sha256 is not None
        ):
            raise ValueError("prevalidated carrier receipt bindings are incomplete")
        if prevalidated:
            self.write_result.receipt.__post_init__()
            self.reemitted_write_result.receipt.__post_init__()
            self.report.__post_init__()
            _require_sha256(
                _source_carrier_writer_receipt_sha256,
                field_name="source_carrier_writer_receipt_sha256",
            )
            _require_sha256(
                _reparsed_carrier_writer_receipt_sha256,
                field_name="reparsed_carrier_writer_receipt_sha256",
            )
            source_carrier_receipt_sha256 = _source_carrier_writer_receipt_sha256
            reparsed_carrier_receipt_sha256 = _reparsed_carrier_writer_receipt_sha256
        else:
            nested_artifacts_valid = True
            try:
                _, source_carrier_write = _validate_fresh_ingest(self.source_ingest)
                self.write_result.receipt.__post_init__()
                self.write_result.__post_init__()
                _, reparsed_carrier_write = _validate_fresh_ingest(self.reparsed_ingest)
                self.reemitted_write_result.receipt.__post_init__()
                self.reemitted_write_result.__post_init__()
                self.report.__post_init__()
            except Exception:
                nested_artifacts_valid = False
            if not nested_artifacts_valid:
                raise ValueError(
                    "round-trip aggregate contains a stale nested artifact"
                )
            source_carrier_receipt_sha256 = source_carrier_write.receipt.receipt_sha256
            reparsed_carrier_receipt_sha256 = (
                reparsed_carrier_write.receipt.receipt_sha256
            )
        source_receipt_matches = _receipt_matches_ingest(
            self.write_result.receipt,
            self.source_ingest,
            carrier_writer_receipt_sha256=source_carrier_receipt_sha256,
        )
        reparsed_receipt_matches = _receipt_matches_ingest(
            self.reemitted_write_result.receipt,
            self.reparsed_ingest,
            carrier_writer_receipt_sha256=reparsed_carrier_receipt_sha256,
        )
        consistent = all(
            (
                source_receipt_matches,
                reparsed_receipt_matches,
                self.write_result.payload == self.reparsed_ingest._full_source_bytes,
                self.write_result.receipt.output_source_sha256
                == self.reparsed_ingest.full_source_sha256,
                self.write_result.payload == self.reemitted_write_result.payload,
                self.report.input_full_source_sha256
                == self.source_ingest.full_source_sha256,
                self.report.reparsed_full_source_sha256
                == self.reparsed_ingest.full_source_sha256,
                self.report.input_source_binding_sha256
                == self.source_ingest.source_binding_sha256,
                self.report.reparsed_source_binding_sha256
                == self.reparsed_ingest.source_binding_sha256,
                self.report.writer_receipt_sha256
                == self.write_result.receipt.receipt_sha256,
                self.report.reemitted_writer_receipt_sha256
                == self.reemitted_write_result.receipt.receipt_sha256,
                self.report.input_carrier_kind == self.source_ingest.carrier_kind,
                self.report.reparsed_carrier_kind == self.reparsed_ingest.carrier_kind,
                self.report.input_source_id_sha256
                == self.source_ingest.source_id_sha256,
                self.report.reparsed_source_id_sha256
                == self.reparsed_ingest.source_id_sha256,
                self.report.input_polymer_sequence_projection_sha256
                == self.source_ingest.polymer_sequence_projection_sha256,
                self.report.reparsed_polymer_sequence_projection_sha256
                == self.reparsed_ingest.polymer_sequence_projection_sha256,
                self.report.input_nonpoly_identity_projection_sha256
                == self.source_ingest.nonpoly_identity_projection_sha256,
                self.report.reparsed_nonpoly_identity_projection_sha256
                == self.reparsed_ingest.nonpoly_identity_projection_sha256,
                self.report.input_nonpoly_identity_record_state_sha256
                == self.source_ingest.nonpoly_identity_record_state_sha256,
                self.report.reparsed_nonpoly_identity_record_state_sha256
                == self.reparsed_ingest.nonpoly_identity_record_state_sha256,
                self.report.input_record_state_sha256
                == self.source_ingest.record_state_sha256,
                self.report.reparsed_record_state_sha256
                == self.reparsed_ingest.record_state_sha256,
                self.report.emitted_source_sha256
                == self.write_result.receipt.output_source_sha256,
                self.report.reemitted_source_sha256
                == self.reemitted_write_result.receipt.output_source_sha256,
                self.report.carrier_kind_equal,
                self.report.source_id_sha256_equal,
                self.report.polymer_sequence_projection_sha256_equal,
                self.report.nonpoly_identity_projection_sha256_equal,
                self.report.nonpoly_identity_record_state_sha256_equal,
                self.report.record_state_sha256_equal,
                self.report.second_emission_byte_stable,
            )
        )
        if not consistent:
            raise ValueError("round-trip artifacts are not cross-consistent")

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        document: dict[str, Any] = {
            "schema_id": MMCIF_POLYMER_SEQUENCE_ROUND_TRIP_REPORT_SCHEMA_ID,
            "profile_id": MMCIF_POLYMER_SEQUENCE_PROFILE_ID,
            "report_sha256": self.report.report_sha256,
            "input_source_binding_sha256": (self.source_ingest.source_binding_sha256),
            "reparsed_source_binding_sha256": (
                self.reparsed_ingest.source_binding_sha256
            ),
            "writer_receipt_sha256": self.write_result.receipt.receipt_sha256,
            "reemitted_writer_receipt_sha256": (
                self.reemitted_write_result.receipt.receipt_sha256
            ),
            "source_reported_sequence_preserved": True,
            "coordinate_absent_rows_preserved_without_missingness_claim": True,
        }
        document.update(_authority_false_document())
        return document


def round_trip_mmcif_polymer_sequence_source(
    data: bytes,
    *,
    source_id: str = "",
) -> MmcifPolymerSequenceRoundTripResult:
    """Run and attest one deterministic polymer-sequence round trip."""

    source_ingest = parse_mmcif_polymer_sequence(data, source_id=source_id)
    write_result = emit_mmcif_polymer_sequence(source_ingest)
    reparsed_ingest = parse_mmcif_polymer_sequence(
        write_result.payload,
        source_id=source_id,
    )
    reemitted_write_result = emit_mmcif_polymer_sequence(reparsed_ingest)
    report = _make_round_trip_report(
        source_ingest=source_ingest,
        write_result=write_result,
        reparsed_ingest=reparsed_ingest,
        reemitted_write_result=reemitted_write_result,
    )
    return MmcifPolymerSequenceRoundTripResult(
        source_ingest=source_ingest,
        write_result=write_result,
        reparsed_ingest=reparsed_ingest,
        reemitted_write_result=reemitted_write_result,
        report=report,
        _source_carrier_writer_receipt_sha256=(
            write_result.receipt.carrier_writer_receipt_sha256
        ),
        _reparsed_carrier_writer_receipt_sha256=(
            reemitted_write_result.receipt.carrier_writer_receipt_sha256
        ),
        _factory_token=_FACTORY_TOKEN,
    )


__all__ = [
    "MAX_MMCIF_POLYMER_SEQUENCE_INPUT_BYTES",
    "MAX_MMCIF_POLYMER_SEQUENCE_ROWS",
    "MAX_MMCIF_POLYMER_SEQUENCE_TOKEN_CHARS",
    "MMCIF_ENTITY_POLY_SEQ_HEADERS",
    "MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION",
    "MMCIF_POLYMER_SEQUENCE_PARSER_NAME",
    "MMCIF_POLYMER_SEQUENCE_PARSER_VERSION",
    "MMCIF_POLYMER_SEQUENCE_PROFILE_ID",
    "MMCIF_POLYMER_SEQUENCE_PROJECTION_SCHEMA_ID",
    "MMCIF_POLYMER_SEQUENCE_RECORD_STATE_SCHEMA_ID",
    "MMCIF_POLYMER_SEQUENCE_ROUND_TRIP_REPORT_SCHEMA_ID",
    "MMCIF_POLYMER_SEQUENCE_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_POLYMER_SEQUENCE_WRITER_VERSION",
    "MMCIF_POLYMER_SEQUENCE_WRITE_RECEIPT_SCHEMA_ID",
    "MmcifPolymerSequenceError",
    "MmcifPolymerSequenceIngestResult",
    "MmcifPolymerSequenceRoundTripReport",
    "MmcifPolymerSequenceRoundTripResult",
    "MmcifPolymerSequenceRow",
    "MmcifPolymerSequenceWriteReceipt",
    "MmcifPolymerSequenceWriteResult",
    "emit_mmcif_polymer_sequence",
    "mmcif_polymer_sequence_projection_sha256",
    "mmcif_polymer_sequence_record_state_sha256",
    "parse_mmcif_polymer_sequence",
    "round_trip_mmcif_polymer_sequence_source",
    "serialize_mmcif_polymer_sequence",
]
