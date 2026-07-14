"""Strict opt-in mmCIF alternate-location selection envelope.

The base mmCIF parser deliberately requires an explicit alternate-location
identifier and the base writer deliberately rejects that selected state.  This
module leaves both contracts unchanged.  It preserves the exact values and row
order of the reviewed three-loop common-core21 source surface, materializes one
explicit conformer through the base parser, and emits every source atom row in
a deterministic category layout.

This is preservation evidence only.  Alternate populations, occupancy,
chemistry, preparation, parameterability, and execution authority are not
inferred.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import math
import re
import struct
from typing import Any, Mapping
import weakref

import torch

from .mmcif_syntax import CifBlock, CifLoop, CifSyntaxError, CifToken, parse_cif_block
from .mmcif_writer import MMCIF_WRITER_VERSION
from .models import canonical_element_symbol
from .pdb_mmcif import MMCIF_PARSER_VERSION, StructureParseError, parse_mmcif
from .serialization import deserialize_all_atom_system, serialize_all_atom_system
from .topology import CANONICAL_TOPOLOGY_SCHEMA_ID, canonical_topology_sha256


MMCIF_ALTLOC_SELECTION_ENVELOPE_VERSION = "1.0.0"
MMCIF_ALTLOC_SELECTION_PARSER_VERSION = "1.0.0"
MMCIF_ALTLOC_SELECTION_WRITER_VERSION = "1.0.0"
MMCIF_ALTLOC_SELECTION_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular.mmcif_altloc_selection.parse_mmcif_altloc_selection"
)
MMCIF_ALTLOC_SELECTION_PROFILE_ID = (
    "strict_mmcif_single_model_common_core21_explicit_altloc_selection_envelope/1.0.0"
)
MMCIF_ALTLOC_SELECTION_PROJECTION_SCOPE = (
    "source_reported_label_alt_id_rows_and_explicit_selected_coordinate_projection_only"
)

MMCIF_ALTLOC_SOURCE_PROJECTION_SCHEMA_ID = (
    "betelgeuze.mmcif_altloc_source_projection/1.0.0"
)
MMCIF_ALTLOC_SELECTED_STATE_SCHEMA_ID = "betelgeuze.mmcif_altloc_selected_state/1.0.0"
MMCIF_ALTLOC_RECORD_STATE_SCHEMA_ID = "betelgeuze.mmcif_altloc_record_state/1.0.0"
MMCIF_ALTLOC_SOURCE_BINDING_SCHEMA_ID = "betelgeuze.mmcif_altloc_source_binding/1.0.0"
MMCIF_ALTLOC_WRITE_RECEIPT_SCHEMA_ID = "betelgeuze.mmcif_altloc_write_receipt/1.0.0"
MMCIF_ALTLOC_ROUND_TRIP_REPORT_SCHEMA_ID = (
    "betelgeuze.mmcif_altloc_round_trip_report/1.0.0"
)

# Compatibility aliases make the selected-envelope prefix available without
# changing the shorter schema constants used by the corpus contract.
MMCIF_ALTLOC_SELECTION_SOURCE_PROJECTION_SCHEMA_ID = (
    MMCIF_ALTLOC_SOURCE_PROJECTION_SCHEMA_ID
)
MMCIF_ALTLOC_SELECTION_SELECTED_STATE_SCHEMA_ID = MMCIF_ALTLOC_SELECTED_STATE_SCHEMA_ID
MMCIF_ALTLOC_SELECTION_RECORD_STATE_SCHEMA_ID = MMCIF_ALTLOC_RECORD_STATE_SCHEMA_ID
MMCIF_ALTLOC_SELECTION_SOURCE_BINDING_SCHEMA_ID = MMCIF_ALTLOC_SOURCE_BINDING_SCHEMA_ID
MMCIF_ALTLOC_SELECTION_WRITE_RECEIPT_SCHEMA_ID = MMCIF_ALTLOC_WRITE_RECEIPT_SCHEMA_ID
MMCIF_ALTLOC_SELECTION_ROUND_TRIP_REPORT_SCHEMA_ID = (
    MMCIF_ALTLOC_ROUND_TRIP_REPORT_SCHEMA_ID
)

MAX_MMCIF_ALTLOC_SELECTION_INPUT_BYTES = 64 * 1024 * 1024
MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_MMCIF_ALTLOC_SELECTION_PROJECTION_BYTES = 64 * 1024 * 1024
MAX_MMCIF_ALTLOC_SELECTION_SOURCE_ID_BYTES = 4_096
MAX_MMCIF_ALTLOC_SELECTION_TOKEN_CHARS = 2_048
MAX_MMCIF_ALTLOC_SELECTION_ALTLOC_ID_CHARS = 256
MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_LINE_CHARS = 2_048
MAX_MMCIF_ALTLOC_SELECTION_ENTITY_ROWS = 4_096
MAX_MMCIF_ALTLOC_SELECTION_STRUCT_ASYM_ROWS = 16_384
MAX_MMCIF_ALTLOC_SELECTION_ATOM_ROWS = 80_000

MMCIF_ALTLOC_SELECTION_ENTITY_HEADERS = ("_entity.id", "_entity.type")
MMCIF_ALTLOC_SELECTION_STRUCT_ASYM_HEADERS = (
    "_struct_asym.id",
    "_struct_asym.entity_id",
)
MMCIF_ALTLOC_SELECTION_ATOM_SITE_HEADERS = (
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

_CATEGORY_ORDER = ("_entity", "_struct_asym", "_atom_site")
_HEADERS_BY_CATEGORY = {
    "_entity": MMCIF_ALTLOC_SELECTION_ENTITY_HEADERS,
    "_struct_asym": MMCIF_ALTLOC_SELECTION_STRUCT_ASYM_HEADERS,
    "_atom_site": MMCIF_ALTLOC_SELECTION_ATOM_SITE_HEADERS,
}
_SUPPORTED_ENTITY_TYPES = {
    "polymer": "polymer",
    "non-polymer": "non_polymer",
    "water": "water",
}
_BASE_PARSER_NAME = "betelgeuze_engine_v2.molecular.pdb_mmcif.parse_mmcif"
_BASE_OPERATIONS = (
    "parse_cif_1_1_block_structure",
    "parse_pdbx_atom_site_label_identity",
    "select_explicit_altloc_id/v1",
    "align_models_by_canonical_label_identity",
    "preserve_source_atom_order_from_first_model",
    "synthesize_canonical_atom_serials_from_first_model_order",
)
_FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "coordinate_observation_completeness_assessed",
    "altloc_population_interpreted",
    "occupancy_population_interpreted",
    "occupancy_weighting_applied",
    "refinement_validity_assessed",
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
_DATA_BLOCK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+\-]*$")
_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_NUMBER_RE = re.compile(
    r"^(?P<mantissa>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
    r"(?P<uncertainty>\(\d+\))?"
    r"(?P<exponent>[eE][+-]?\d+)?$"
)
_FACTORY_TOKEN = object()
_INGEST_STATE_ANCHORS: dict[int, tuple[weakref.ReferenceType[Any], Any]] = {}


class MmcifAltlocSelectionError(ValueError):
    """Stable fail-closed error for the alternate-location envelope."""

    def __init__(
        self, code: str, message: str, *, line_number: int | None = None
    ) -> None:
        self.code = str(code)
        self.detail = str(message)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"mmcif_altloc_selection:{self.code}{suffix}: {self.detail}")


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_document(value: Mapping[str, Any]) -> str:
    return _sha256_bytes(_canonical_json_bytes(value))


def _authority_false_document() -> dict[str, bool]:
    return {name: False for name in _FALSE_AUTHORITY_FIELDS}


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if value is None or type(value) in {str, bool, int, float}:
        if type(value) is float and not math.isfinite(value):
            raise MmcifAltlocSelectionError(
                "nonfinite_selected_state", "selected state is not finite"
            )
        return value
    raise MmcifAltlocSelectionError(
        "unsupported_selected_state", "selected state has an unsupported value type"
    )


def _source_id_sha256(source_id: str) -> str:
    if type(source_id) is not str:
        raise TypeError("source_id must be an exact string")
    try:
        encoded = source_id.encode("utf-8")
    except UnicodeEncodeError:
        raise MmcifAltlocSelectionError(
            "invalid_source_id", "source_id must be valid bounded UTF-8 text"
        ) from None
    if len(encoded) > MAX_MMCIF_ALTLOC_SELECTION_SOURCE_ID_BYTES:
        raise MmcifAltlocSelectionError(
            "source_id_limit_exceeded", "source_id exceeds the fixed UTF-8 byte limit"
        )
    return _sha256_bytes(encoded)


def _parse_block(data: bytes) -> CifBlock:
    if type(data) is not bytes:
        raise TypeError("mmCIF alternate-location input must be exact bytes")
    if not 1 <= len(data) <= MAX_MMCIF_ALTLOC_SELECTION_INPUT_BYTES:
        raise MmcifAltlocSelectionError(
            "input_limit_exceeded", "input is empty or exceeds the fixed byte limit"
        )
    try:
        return parse_cif_block(data.decode("ascii"))
    except UnicodeDecodeError:
        raise MmcifAltlocSelectionError(
            "invalid_cif_character_set", "input must be ASCII"
        ) from None
    except CifSyntaxError as exc:
        raise MmcifAltlocSelectionError(
            exc.code, "input is not valid strict CIF", line_number=exc.line_number
        ) from None


def _loop_for(block: CifBlock, category: str) -> CifLoop:
    loops = [loop for loop in block.loops if category in loop.categories]
    if len(loops) != 1 or loops[0].categories != (category,):
        raise MmcifAltlocSelectionError(
            "unsupported_category_surface",
            "each reviewed category must occupy one unmixed loop",
        )
    return loops[0]


def _token_text(token: CifToken) -> str:
    if token.quoted or token.multiline:
        raise MmcifAltlocSelectionError(
            "unsafe_cif_token",
            "the envelope accepts bare single-line CIF tokens only",
            line_number=token.line_number,
        )
    value = token.value
    lowered = value.lower()
    if (
        not value
        or len(value) > MAX_MMCIF_ALTLOC_SELECTION_TOKEN_CHARS
        or not value.isascii()
        or not value.isprintable()
        or any(character.isspace() for character in value)
        or value.startswith(("_", "#", ";", "$", "[", "]"))
        or lowered in {"loop_", "stop_", "global_"}
        or lowered.startswith(("data_", "save_"))
    ):
        raise MmcifAltlocSelectionError(
            "unsafe_cif_token",
            "a CIF token is outside the reviewed bare-token envelope",
        )
    return value


def _validate_requested_altloc(altloc_id: str) -> None:
    if type(altloc_id) is not str:
        raise TypeError("altloc_id must be an exact string")
    if altloc_id in {"", ".", "?"}:
        raise MmcifAltlocSelectionError(
            "invalid_altloc_id", "altloc_id must name one explicit alternate location"
        )
    synthetic = CifToken(
        value=altloc_id,
        quoted=False,
        multiline=False,
        line_number=1,
        column_number=1,
    )
    _token_text(synthetic)


def _validate_requested_altloc_bound(altloc_id: str) -> None:
    if len(altloc_id) > MAX_MMCIF_ALTLOC_SELECTION_ALTLOC_ID_CHARS:
        raise MmcifAltlocSelectionError(
            "invalid_altloc_id",
            "altloc_id exceeds the explicit-selection character limit",
        )


def _rows_for(block: CifBlock, category: str) -> tuple[tuple[str, ...], ...]:
    loop = _loop_for(block, category)
    if loop.tags != _HEADERS_BY_CATEGORY[category]:
        raise MmcifAltlocSelectionError(
            "unsupported_category_headers",
            "category headers differ from the exact reviewed order",
            line_number=loop.line_number,
        )
    return tuple(tuple(_token_text(token) for token in row) for row in loop.rows)


def _validate_numeric_uncertainty(
    loop: CifLoop, rows: tuple[tuple[str, ...], ...]
) -> None:
    numeric_columns = (10, 11, 12, 13, 14, 15)
    for row_index, row in enumerate(rows):
        for column in numeric_columns:
            token = row[column]
            if token in {".", "?"}:
                continue
            match = _NUMBER_RE.fullmatch(token)
            if match is not None and match.group("uncertainty") is not None:
                raise MmcifAltlocSelectionError(
                    "numeric_uncertainty_unsupported",
                    "numeric standard uncertainty is outside this envelope",
                    line_number=loop.rows[row_index][column].line_number,
                )


def _validated_surface(
    block: CifBlock,
) -> tuple[tuple[str, tuple[tuple[str, ...], ...]], ...]:
    if block.scalar_values or set(block.categories) != set(_CATEGORY_ORDER):
        raise MmcifAltlocSelectionError(
            "unsupported_category_surface",
            "the envelope requires exactly entity, struct_asym, and atom_site loops",
        )
    if len(block.categories) != 3 or len(block.loops) != 3:
        raise MmcifAltlocSelectionError(
            "unsupported_category_surface",
            "the envelope requires exactly three unmixed loops",
        )
    if _DATA_BLOCK_RE.fullmatch(block.name) is None:
        raise MmcifAltlocSelectionError(
            "unsafe_data_block", "the data block name is outside the envelope"
        )

    rows = {category: _rows_for(block, category) for category in _CATEGORY_ORDER}
    entity_rows = rows["_entity"]
    struct_rows = rows["_struct_asym"]
    atom_rows = rows["_atom_site"]
    if not 1 <= len(entity_rows) <= MAX_MMCIF_ALTLOC_SELECTION_ENTITY_ROWS:
        raise MmcifAltlocSelectionError(
            "entity_row_limit_exceeded",
            "entity rows are empty or exceed the fixed limit",
        )
    if not 1 <= len(struct_rows) <= MAX_MMCIF_ALTLOC_SELECTION_STRUCT_ASYM_ROWS:
        raise MmcifAltlocSelectionError(
            "struct_asym_row_limit_exceeded",
            "struct_asym rows are empty or exceed the fixed limit",
        )
    if not 1 <= len(atom_rows) <= MAX_MMCIF_ALTLOC_SELECTION_ATOM_ROWS:
        raise MmcifAltlocSelectionError(
            "atom_row_limit_exceeded", "atom rows are empty or exceed the fixed limit"
        )

    entity_map: dict[str, str] = {}
    for entity_id, entity_type in entity_rows:
        if (
            entity_id in {".", "?"}
            or entity_id in entity_map
            or entity_type not in _SUPPORTED_ENTITY_TYPES
        ):
            raise MmcifAltlocSelectionError(
                "unsupported_category_representation",
                "entity rows do not satisfy the exact identity surface",
            )
        entity_map[entity_id] = entity_type
    asym_map: dict[str, str] = {}
    for asym_id, entity_id in struct_rows:
        if asym_id in {".", "?"} or asym_id in asym_map or entity_id not in entity_map:
            raise MmcifAltlocSelectionError(
                "unsupported_category_representation",
                "struct_asym rows do not satisfy the exact identity surface",
            )
        asym_map[asym_id] = entity_id

    atom_loop = _loop_for(block, "_atom_site")
    _validate_numeric_uncertainty(atom_loop, atom_rows)
    source_ids: set[str] = set()
    for row_index, row in enumerate(atom_rows):
        source_id = row[1]
        if source_id in source_ids:
            raise MmcifAltlocSelectionError(
                "duplicate_atom_site_id", "atom_site identifiers must be unique"
            )
        source_ids.add(source_id)
        if (
            row[6] not in asym_map
            or row[7] != asym_map[row[6]]
            or any(row[column] in {".", "?"} for column in (16, 17, 18, 19))
        ):
            raise MmcifAltlocSelectionError(
                "unsupported_category_representation",
                "atom rows do not satisfy complete label/auth/entity identity",
                line_number=atom_loop.rows[row_index][0].line_number,
            )
        if _INTEGER_RE.fullmatch(row[20]) is None or int(row[20], 10) != 1:
            raise MmcifAltlocSelectionError(
                "unsupported_model_id", "every atom row must use model ID 1"
            )
    return tuple((category, rows[category]) for category in _CATEGORY_ORDER)


def _emit_categories(
    block_name: str,
    rows_by_category: Mapping[str, tuple[tuple[str, ...], ...]],
) -> bytes:
    lines = [f"data_{block_name}", "#"]
    for category in _CATEGORY_ORDER:
        lines.extend(("loop_", *_HEADERS_BY_CATEGORY[category]))
        for row in rows_by_category[category]:
            joined = " ".join(row)
            if len(joined) <= MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_LINE_CHARS:
                lines.append(joined)
            else:
                lines.extend(row)
        lines.append("#")
    if any(len(line) > MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_LINE_CHARS for line in lines):
        raise MmcifAltlocSelectionError(
            "output_line_limit_exceeded", "canonical output exceeds the line limit"
        )
    payload = ("\n".join(lines) + "\n").encode("ascii")
    if not 1 <= len(payload) <= MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_BYTES:
        raise MmcifAltlocSelectionError(
            "output_limit_exceeded", "canonical output exceeds the fixed byte limit"
        )
    return payload


def _blank(value: str) -> str:
    return "" if value in {".", "?"} else value


def _formal_charge_semantics(value: str) -> tuple[int, bool]:
    if value in {".", "?"}:
        return (0, False)
    if _INTEGER_RE.fullmatch(value) is None:
        return (0, False)
    return (int(value, 10), True)


def _residue_key(
    row: tuple[str, ...], entity_types: Mapping[str, str]
) -> tuple[Any, ...]:
    sequence = _blank(row[8])
    if not sequence:
        sequence = row[16]
    return (
        row[6],
        sequence,
        _blank(row[9]),
        row[5],
        row[0].upper(),
        row[7],
        _SUPPORTED_ENTITY_TYPES[entity_types[row[7]]],
    )


def _candidate_semantics(
    row: tuple[str, ...], entity_types: Mapping[str, str]
) -> tuple[Any, ...]:
    try:
        element = canonical_element_symbol(row[2])
    except (TypeError, ValueError):
        element = row[2].upper()
    return (
        row[0].upper(),
        row[3],
        element,
        *_formal_charge_semantics(row[15]),
        row[7],
        _SUPPORTED_ENTITY_TYPES[entity_types[row[7]]],
        (row[19], row[17], row[18], row[16]),
    )


def _independent_selection(
    rows_by_category: Mapping[str, tuple[tuple[str, ...], ...]],
    *,
    altloc_id: str,
) -> tuple[tuple[int, ...], tuple[int, ...], int]:
    entity_types = dict(rows_by_category["_entity"])
    atom_rows = rows_by_category["_atom_site"]
    alternates: dict[
        tuple[Any, ...], dict[str, dict[tuple[Any, ...], tuple[Any, ...]]]
    ] = {}
    blank_sites: dict[tuple[Any, ...], set[tuple[Any, ...]]] = {}
    for row in atom_rows:
        residue = _residue_key(row, entity_types)
        site = (*residue[:4], row[3])
        label = _blank(row[4])
        if not label:
            sites = blank_sites.setdefault(residue, set())
            if site in sites:
                raise MmcifAltlocSelectionError(
                    "duplicate_atom_identity", "blank atom identity is duplicated"
                )
            sites.add(site)
            continue
        labels = alternates.setdefault(residue, {})
        sites_by_label = labels.setdefault(label, {})
        if site in sites_by_label:
            raise MmcifAltlocSelectionError(
                "duplicate_altloc_atom_identity",
                "alternate-location atom identity is duplicated",
            )
        sites_by_label[site] = _candidate_semantics(row, entity_types)

    if not alternates:
        raise MmcifAltlocSelectionError(
            "requested_altloc_not_present", "the source has no explicit alternate rows"
        )
    for residue, labels in alternates.items():
        candidate_maps = list(labels.values())
        if any(candidate != candidate_maps[0] for candidate in candidate_maps[1:]):
            raise MmcifAltlocSelectionError(
                "inconsistent_altloc_atom_identity",
                "alternate labels describe unequal atom identities",
            )
        alternate_sites = set().union(*(set(candidate) for candidate in candidate_maps))
        if alternate_sites & blank_sites.get(residue, set()):
            raise MmcifAltlocSelectionError(
                "altloc_blank_collision",
                "blank and alternate rows collide at one atom identity",
            )
        if altloc_id not in labels:
            raise MmcifAltlocSelectionError(
                "requested_altloc_missing_for_residue",
                "the requested alternate is absent from an affected residue",
            )
    selected = tuple(
        index
        for index, row in enumerate(atom_rows)
        if _blank(row[4]) in {"", altloc_id}
    )
    discarded = tuple(
        index
        for index, row in enumerate(atom_rows)
        if _blank(row[4]) not in {"", altloc_id}
    )
    return selected, discarded, len(alternates)


def _binary64_hex(value: float) -> str:
    return struct.pack(">d", float(value)).hex()


def _stable_coverage(value: Mapping[str, Any]) -> dict[str, Any]:
    document = _plain(value)
    document.pop("source_missingness_evidence_sha256", None)
    return document


def _source_projection_document(
    rows_by_category: Mapping[str, tuple[tuple[str, ...], ...]],
    *,
    block_name: str,
) -> dict[str, Any]:
    atom_rows = rows_by_category["_atom_site"]
    return {
        "schema_id": MMCIF_ALTLOC_SOURCE_PROJECTION_SCHEMA_ID,
        "envelope_version": MMCIF_ALTLOC_SELECTION_ENVELOPE_VERSION,
        "profile_id": MMCIF_ALTLOC_SELECTION_PROFILE_ID,
        "projection_scope": MMCIF_ALTLOC_SELECTION_PROJECTION_SCOPE,
        "data_block": block_name,
        "categories": [
            {
                "category": category,
                "headers": list(_HEADERS_BY_CATEGORY[category]),
                "rows": [list(row) for row in rows_by_category[category]],
            }
            for category in _CATEGORY_ORDER
        ],
        "entity_row_count": len(rows_by_category["_entity"]),
        "struct_asym_row_count": len(rows_by_category["_struct_asym"]),
        "source_atom_row_count": len(atom_rows),
        "source_atom_site_ids": [row[1] for row in atom_rows],
        "source_altloc_tokens": [row[4] for row in atom_rows],
        "all_source_atom_rows_preserved": True,
        "parser_version": MMCIF_ALTLOC_SELECTION_PARSER_VERSION,
        "base_parser_version": MMCIF_PARSER_VERSION,
        "base_writer_version": MMCIF_WRITER_VERSION,
        "resource_limits": {
            "input_bytes": MAX_MMCIF_ALTLOC_SELECTION_INPUT_BYTES,
            "output_bytes": MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_BYTES,
            "projection_bytes": MAX_MMCIF_ALTLOC_SELECTION_PROJECTION_BYTES,
            "source_id_utf8_bytes": MAX_MMCIF_ALTLOC_SELECTION_SOURCE_ID_BYTES,
            "token_characters": MAX_MMCIF_ALTLOC_SELECTION_TOKEN_CHARS,
            "altloc_id_characters": MAX_MMCIF_ALTLOC_SELECTION_ALTLOC_ID_CHARS,
            "output_line_characters": MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_LINE_CHARS,
            "entity_rows": MAX_MMCIF_ALTLOC_SELECTION_ENTITY_ROWS,
            "struct_asym_rows": MAX_MMCIF_ALTLOC_SELECTION_STRUCT_ASYM_ROWS,
            "atom_rows": MAX_MMCIF_ALTLOC_SELECTION_ATOM_ROWS,
        },
        **_authority_false_document(),
    }


def _selected_state_document(
    ingest: Any,
    rows_by_category: Mapping[str, tuple[tuple[str, ...], ...]],
    *,
    altloc_id: str,
    selected_ordinals: tuple[int, ...],
    discarded_ordinals: tuple[int, ...],
    affected_residue_count: int,
) -> dict[str, Any]:
    system = ingest.system
    atom_rows = rows_by_category["_atom_site"]
    selected_rows = [atom_rows[index] for index in selected_ordinals]
    atoms: list[dict[str, Any]] = []
    for index, (atom, row) in enumerate(zip(system.atoms, selected_rows, strict=True)):
        residue = system.residues[atom.residue_index]
        chain = system.chains[residue.chain_index]
        atoms.append(
            {
                "index": index,
                "source_row_ordinal": selected_ordinals[index],
                "source_atom_site_id": row[1],
                "record": row[0],
                "name": atom.name,
                "element": atom.element,
                "formal_charge": atom.formal_charge,
                "formal_charge_known": atom.formal_charge_known,
                "serial": atom.serial,
                "altloc": atom.altloc,
                "residue_index": atom.residue_index,
                "residue_name": residue.name,
                "sequence_number": residue.sequence_number,
                "insertion_code": residue.insertion_code,
                "entity_type": residue.entity_type,
                "chain_index": residue.chain_index,
                "chain_id": chain.chain_id,
                "occupancy_ieee754_binary64_be": (
                    None if atom.occupancy is None else _binary64_hex(atom.occupancy)
                ),
                "b_factor_ieee754_binary64_be": (
                    None if atom.b_factor is None else _binary64_hex(atom.b_factor)
                ),
            }
        )
    coordinates = [
        [_binary64_hex(system.coordinates[0, index, axis]) for axis in range(3)]
        for index in range(system.atom_count)
    ]
    ledger = _plain(system.metadata["mmcif"]["altloc_selection"])
    return {
        "schema_id": MMCIF_ALTLOC_SELECTED_STATE_SCHEMA_ID,
        "envelope_version": MMCIF_ALTLOC_SELECTION_ENVELOPE_VERSION,
        "profile_id": MMCIF_ALTLOC_SELECTION_PROFILE_ID,
        "altloc_id": altloc_id,
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "canonical_topology_sha256": canonical_topology_sha256(system),
        "coordinate_unit": system.coordinate_unit,
        "model_count": system.model_count,
        "atom_count": system.atom_count,
        "residue_count": len(system.residues),
        "chain_count": len(system.chains),
        "affected_residue_count": affected_residue_count,
        "selected_source_row_ordinals": list(selected_ordinals),
        "discarded_source_row_ordinals": list(discarded_ordinals),
        "selected_source_atom_site_ids": [row[1] for row in selected_rows],
        "discarded_source_atom_site_ids": [
            atom_rows[index][1] for index in discarded_ordinals
        ],
        "atom_order": atoms,
        "coordinates_ieee754_binary64_be": coordinates,
        "altloc_selection_ledger": ledger,
        "base_coverage": _stable_coverage(ingest.coverage.to_dict()),
        "base_parser": {
            "name": system.provenance.parser_name,
            "version": system.provenance.parser_version,
            "operations": list(system.provenance.operations),
            "model_ids": _plain(system.provenance.metadata.get("model_ids")),
            "preparation_ready": system.provenance.preparation_ready,
            "claim_safe": system.provenance.claim_safe,
        },
        **_authority_false_document(),
    }


def _selected_atom_rows_match_source(
    system: Any,
    selected_rows: list[tuple[str, ...]],
) -> bool:
    if len(system.atoms) != len(selected_rows):
        return False
    for atom, source_row in zip(system.atoms, selected_rows, strict=True):
        metadata = atom.metadata
        if not isinstance(metadata, Mapping):
            return False
        mmcif = metadata.get("mmcif")
        if not isinstance(mmcif, Mapping):
            return False
        if (
            type(mmcif.get("source_atom_site_id")) is not str
            or mmcif["source_atom_site_id"] != source_row[1]
        ):
            return False
        atom_site = mmcif.get("atom_site")
        if not isinstance(atom_site, Mapping):
            return False
        for header, expected_token in zip(
            MMCIF_ALTLOC_SELECTION_ATOM_SITE_HEADERS,
            source_row,
            strict=True,
        ):
            token = atom_site.get(header)
            if (
                not isinstance(token, Mapping)
                or type(token.get("value")) is not str
                or token["value"] != expected_token
                or token.get("quoted") is not False
                or token.get("multiline") is not False
            ):
                return False
    return True


def _validate_base_result(
    ingest: Any,
    *,
    source: bytes,
    source_id: str,
    altloc_id: str,
    rows_by_category: Mapping[str, tuple[tuple[str, ...], ...]],
    selected_ordinals: tuple[int, ...],
    discarded_ordinals: tuple[int, ...],
    affected_residue_count: int,
) -> None:
    system = ingest.system
    coverage = ingest.coverage
    coverage_document = coverage.to_dict()
    atom_rows = rows_by_category["_atom_site"]
    ledger = _plain(system.metadata.get("mmcif", {}).get("altloc_selection"))
    selected_rows = [atom_rows[index] for index in selected_ordinals]
    expected_kept = [row[1] for row in selected_rows]
    expected_discarded = [atom_rows[index][1] for index in discarded_ordinals]
    ledger_models = ledger.get("models") if isinstance(ledger, dict) else None
    ledger_model = (
        ledger_models[0]
        if type(ledger_models) is list
        and len(ledger_models) == 1
        and type(ledger_models[0]) is dict
        else {}
    )
    ledger_kept = ledger_model.get("kept_source_atom_ids")
    ledger_discarded = ledger_model.get("discarded_source_atom_ids")
    coverage_counts_are_exact = all(
        type(value) is int
        for key, value in coverage_document.items()
        if key.endswith("_count")
    )
    model_ids = system.provenance.metadata.get("model_ids")
    semantic_match = (
        system.provenance.source_format == "mmcif"
        and system.provenance.source_id == source_id
        and system.provenance.source_sha256 == _sha256_bytes(source)
        and system.provenance.parser_name == _BASE_PARSER_NAME
        and system.provenance.parser_version == MMCIF_PARSER_VERSION
        and tuple(system.provenance.operations) == _BASE_OPERATIONS
        and tuple(system.provenance.parent_sha256) == ()
        and system.provenance.preparation_ready is False
        and system.provenance.claim_safe is False
        and system.coordinates.device.type == "cpu"
        and system.coordinates.dtype is torch.float64
        and not system.coordinates.requires_grad
        and system.model_count == 1
        and isinstance(model_ids, tuple)
        and len(model_ids) == 1
        and type(model_ids[0]) is int
        and model_ids[0] == 1
        and system.cell is None
        and system.coordinate_unit == "angstrom"
        and len(system.bonds) == 0
        and coverage_counts_are_exact
        and type(coverage.source_atom_row_count) is int
        and coverage.altloc_status == "explicit_id_selected"
        and coverage.requested_altloc_id == altloc_id
        and coverage.source_atom_row_count == len(atom_rows)
        and type(coverage.altloc_kept_row_count) is int
        and coverage.altloc_kept_row_count == len(selected_ordinals)
        and type(coverage.altloc_discarded_row_count) is int
        and coverage.altloc_discarded_row_count == len(discarded_ordinals)
        and type(coverage.altloc_affected_residue_count) is int
        and coverage.altloc_affected_residue_count == affected_residue_count
        and coverage.assembly_status == "not_present"
        and coverage.missingness_evidence_status == "not_present"
        and coverage.preparation_ready is False
        and coverage.claim_safe is False
        and type(ledger) is dict
        and type(ledger_models) is list
        and len(ledger_models) == 1
        and ledger.get("status") == "explicit_id_selected"
        and ledger.get("requested_altloc_id") == altloc_id
        and type(ledger_model.get("model_id")) is int
        and ledger_model.get("model_id") == 1
        and type(ledger_kept) is list
        and all(type(value) is str for value in ledger_kept)
        and ledger_kept == expected_kept
        and type(ledger_discarded) is list
        and all(type(value) is str for value in ledger_discarded)
        and ledger_discarded == expected_discarded
        and _selected_atom_rows_match_source(system, selected_rows)
        and system.atom_count == len(selected_ordinals)
    )
    if not semantic_match:
        raise MmcifAltlocSelectionError(
            "base_mmcif_semantic_mismatch",
            "the base parser result differs from independently derived selection evidence",
        )


@dataclass(frozen=True, slots=True)
class _ParsedState:
    full_source: bytes = field(repr=False)
    source_id: str = field(repr=False)
    altloc_id: str
    source_projection_bytes: bytes = field(repr=False)
    selected_state_bytes: bytes = field(repr=False)
    system_snapshot: bytes = field(repr=False)
    canonical_output: bytes = field(repr=False)
    record_state_bytes: bytes = field(repr=False)
    source_binding_bytes: bytes = field(repr=False)
    category_rows: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...] = field(
        repr=False
    )

    @property
    def rows_by_category(self) -> dict[str, tuple[tuple[str, ...], ...]]:
        return dict(self.category_rows)


def _nested_error(exc: Exception) -> MmcifAltlocSelectionError:
    code = getattr(exc, "code", "nested_mmcif_error")
    line_number = getattr(exc, "line_number", None)
    return MmcifAltlocSelectionError(
        str(code),
        "the base mmCIF parser rejected the reviewed source",
        line_number=line_number,
    )


def _parse_state(data: bytes, *, altloc_id: str, source_id: str) -> _ParsedState:
    _validate_requested_altloc(altloc_id)
    _source_id_sha256(source_id)
    block = _parse_block(data)
    category_rows = _validated_surface(block)
    _validate_requested_altloc_bound(altloc_id)
    rows = dict(category_rows)
    selected, discarded, affected = _independent_selection(rows, altloc_id=altloc_id)
    try:
        base_ingest = parse_mmcif(data, source_id=source_id, altloc_id=altloc_id)
        _validate_base_result(
            base_ingest,
            source=data,
            source_id=source_id,
            altloc_id=altloc_id,
            rows_by_category=rows,
            selected_ordinals=selected,
            discarded_ordinals=discarded,
            affected_residue_count=affected,
        )
        source_projection = _source_projection_document(rows, block_name=block.name)
        selected_state = _selected_state_document(
            base_ingest,
            rows,
            altloc_id=altloc_id,
            selected_ordinals=selected,
            discarded_ordinals=discarded,
            affected_residue_count=affected,
        )
        source_projection_bytes = _canonical_json_bytes(source_projection)
        selected_state_bytes = _canonical_json_bytes(selected_state)
        if (
            len(source_projection_bytes) > MAX_MMCIF_ALTLOC_SELECTION_PROJECTION_BYTES
            or len(selected_state_bytes) > MAX_MMCIF_ALTLOC_SELECTION_PROJECTION_BYTES
        ):
            raise MmcifAltlocSelectionError(
                "projection_limit_exceeded",
                "a canonical projection exceeds the byte limit",
            )
        state = _ParsedState(
            full_source=data,
            source_id=source_id,
            altloc_id=altloc_id,
            source_projection_bytes=source_projection_bytes,
            selected_state_bytes=selected_state_bytes,
            system_snapshot=serialize_all_atom_system(base_ingest.system),
            canonical_output=_emit_categories(block.name, rows),
            record_state_bytes=b"",
            source_binding_bytes=b"",
            category_rows=category_rows,
        )
        state = replace(
            state,
            record_state_bytes=_canonical_json_bytes(
                _compute_record_state_document(state)
            ),
        )
        return replace(
            state,
            source_binding_bytes=_canonical_json_bytes(
                _compute_source_binding_document(state)
            ),
        )
    except (StructureParseError, CifSyntaxError) as exc:
        raise _nested_error(exc) from None
    except MmcifAltlocSelectionError:
        raise
    except Exception:
        raise MmcifAltlocSelectionError(
            "base_mmcif_integration_failed",
            "the base mmCIF integration failed closed",
        ) from None


def _compute_record_state_document(state: _ParsedState) -> dict[str, Any]:
    selected = json.loads(state.selected_state_bytes.decode("ascii"))
    source = json.loads(state.source_projection_bytes.decode("ascii"))
    return {
        "schema_id": MMCIF_ALTLOC_RECORD_STATE_SCHEMA_ID,
        "envelope_version": MMCIF_ALTLOC_SELECTION_ENVELOPE_VERSION,
        "parser_version": MMCIF_ALTLOC_SELECTION_PARSER_VERSION,
        "writer_version": MMCIF_ALTLOC_SELECTION_WRITER_VERSION,
        "profile_id": MMCIF_ALTLOC_SELECTION_PROFILE_ID,
        "projection_scope": MMCIF_ALTLOC_SELECTION_PROJECTION_SCOPE,
        "base_parser_name": _BASE_PARSER_NAME,
        "base_parser_version": MMCIF_PARSER_VERSION,
        "base_parser_operations": list(_BASE_OPERATIONS),
        "base_writer_version": MMCIF_WRITER_VERSION,
        "source_id_sha256": _source_id_sha256(state.source_id),
        "altloc_id": state.altloc_id,
        "source_projection_sha256": _sha256_bytes(state.source_projection_bytes),
        "selected_state_sha256": _sha256_bytes(state.selected_state_bytes),
        "topology_sha256": selected["canonical_topology_sha256"],
        "entity_row_count": source["entity_row_count"],
        "struct_asym_row_count": source["struct_asym_row_count"],
        "source_atom_row_count": source["source_atom_row_count"],
        "selected_atom_row_count": selected["atom_count"],
        "discarded_atom_row_count": len(selected["discarded_source_row_ordinals"]),
        "affected_residue_count": selected["affected_residue_count"],
        **_authority_false_document(),
    }


def _record_state_document(state: _ParsedState) -> dict[str, Any]:
    return json.loads(state.record_state_bytes.decode("ascii"))


def _compute_source_binding_document(state: _ParsedState) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_ALTLOC_SOURCE_BINDING_SCHEMA_ID,
        "envelope_version": MMCIF_ALTLOC_SELECTION_ENVELOPE_VERSION,
        "parser_version": MMCIF_ALTLOC_SELECTION_PARSER_VERSION,
        "profile_id": MMCIF_ALTLOC_SELECTION_PROFILE_ID,
        "full_source_sha256": _sha256_bytes(state.full_source),
        "source_id_sha256": _source_id_sha256(state.source_id),
        "canonical_output_sha256": _sha256_bytes(state.canonical_output),
        "system_snapshot_sha256": _sha256_bytes(state.system_snapshot),
        "record_state_sha256": _sha256_bytes(state.record_state_bytes),
        **_authority_false_document(),
    }


def _source_binding_document(state: _ParsedState) -> dict[str, Any]:
    return json.loads(state.source_binding_bytes.decode("ascii"))


def _validate_bound_category_rows(
    value: Any,
) -> tuple[tuple[str, tuple[tuple[str, ...], ...]], ...]:
    if type(value) is not tuple or len(value) != len(_CATEGORY_ORDER):
        raise TypeError("category rows must be one exact immutable category tuple")
    for expected_category, item in zip(_CATEGORY_ORDER, value, strict=True):
        if type(item) is not tuple or len(item) != 2:
            raise TypeError("category rows contain an invalid category item")
        category, rows = item
        if category != expected_category or type(rows) is not tuple:
            raise TypeError("category rows differ from the exact category order")
        expected_width = len(_HEADERS_BY_CATEGORY[category])
        for row in rows:
            if (
                type(row) is not tuple
                or len(row) != expected_width
                or any(type(token) is not str for token in row)
            ):
                raise TypeError("category rows contain an invalid exact token row")
    return value


def _state_access_binding_document(state: _ParsedState) -> dict[str, Any]:
    byte_fields = {
        "full_source": state.full_source,
        "source_projection": state.source_projection_bytes,
        "selected_state": state.selected_state_bytes,
        "system_snapshot": state.system_snapshot,
        "canonical_output": state.canonical_output,
        "record_state": state.record_state_bytes,
        "source_binding": state.source_binding_bytes,
    }
    if any(type(value) is not bytes for value in byte_fields.values()):
        raise TypeError("bound ingest byte fields must remain exact bytes")
    _source_id_sha256(state.source_id)
    _validate_requested_altloc(state.altloc_id)
    _validate_requested_altloc_bound(state.altloc_id)
    rows = _validate_bound_category_rows(state.category_rows)
    return {
        "byte_objects": {
            name: {"object_id": id(value), "byte_count": len(value)}
            for name, value in byte_fields.items()
        },
        "source_id_object_id": id(state.source_id),
        "source_id_sha256": _source_id_sha256(state.source_id),
        "altloc_id_object_id": id(state.altloc_id),
        "altloc_id": state.altloc_id,
        "category_rows_object_id": id(rows),
    }


def _register_ingest_state_anchor(
    value: MmcifAltlocSelectionIngestResult,
    state: _ParsedState,
) -> None:
    key = id(value)

    def discard(reference: weakref.ReferenceType[Any]) -> None:
        current = _INGEST_STATE_ANCHORS.get(key)
        if current is not None and current[0] is reference:
            _INGEST_STATE_ANCHORS.pop(key, None)

    reference = weakref.ref(value, discard)
    _INGEST_STATE_ANCHORS[key] = (reference, state)


def _ingest_state_anchor(value: MmcifAltlocSelectionIngestResult) -> _ParsedState:
    current = _INGEST_STATE_ANCHORS.get(id(value))
    if (
        current is None
        or current[0]() is not value
        or type(current[1]) is not _ParsedState
    ):
        raise ValueError("ingest has no live factory state anchor")
    return current[1]


@dataclass(frozen=True, init=False)
class MmcifAltlocSelectionIngestResult:
    _full_source: bytes = field(repr=False)
    _source_id: str = field(repr=False)
    _altloc_id: str = field(repr=False)
    _source_projection_bytes: bytes = field(repr=False)
    _selected_state_bytes: bytes = field(repr=False)
    _system_snapshot: bytes = field(repr=False)
    _canonical_output: bytes = field(repr=False)
    _record_state_bytes: bytes = field(repr=False)
    _source_binding_bytes: bytes = field(repr=False)
    _category_rows: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...] = field(
        repr=False
    )
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self, state: _ParsedState, *, _factory_token: object | None = None
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifAltlocSelectionIngestResult is factory-only")
        if type(state) is not _ParsedState:
            raise TypeError("state must be exact parsed alternate-location state")
        for name in (
            "full_source",
            "source_id",
            "altloc_id",
            "source_projection_bytes",
            "selected_state_bytes",
            "system_snapshot",
            "canonical_output",
            "record_state_bytes",
            "source_binding_bytes",
            "category_rows",
        ):
            object.__setattr__(self, f"_{name}", getattr(state, name))
        object.__setattr__(
            self,
            "_access_binding_bytes",
            _canonical_json_bytes(_state_access_binding_document(state)),
        )
        _register_ingest_state_anchor(self, state)

    @property
    def altloc_id(self) -> str:
        return _validate_fresh_ingest(self).altloc_id

    @property
    def system(self) -> Any:
        return deserialize_all_atom_system(_validate_fresh_ingest(self).system_snapshot)

    @property
    def source_projection_document(self) -> dict[str, Any]:
        state = _validate_fresh_ingest(self)
        return json.loads(state.source_projection_bytes.decode("ascii"))

    @property
    def selected_state_document(self) -> dict[str, Any]:
        state = _validate_fresh_ingest(self)
        return json.loads(state.selected_state_bytes.decode("ascii"))

    @property
    def full_source_sha256(self) -> str:
        return str(
            _source_binding_document(_validate_fresh_ingest(self))["full_source_sha256"]
        )

    @property
    def source_id_sha256(self) -> str:
        return str(
            _record_state_document(_validate_fresh_ingest(self))["source_id_sha256"]
        )

    @property
    def source_projection_sha256(self) -> str:
        return str(
            _record_state_document(_validate_fresh_ingest(self))[
                "source_projection_sha256"
            ]
        )

    @property
    def selected_state_sha256(self) -> str:
        return str(
            _record_state_document(_validate_fresh_ingest(self))[
                "selected_state_sha256"
            ]
        )

    @property
    def system_snapshot_sha256(self) -> str:
        return str(
            _source_binding_document(_validate_fresh_ingest(self))[
                "system_snapshot_sha256"
            ]
        )

    @property
    def record_state_sha256(self) -> str:
        return _sha256_bytes(_validate_fresh_ingest(self).record_state_bytes)

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_bytes(_validate_fresh_ingest(self).source_binding_bytes)

    @property
    def topology_sha256(self) -> str:
        return str(
            _record_state_document(_validate_fresh_ingest(self))["topology_sha256"]
        )

    @property
    def entity_row_count(self) -> int:
        return int(
            _record_state_document(_validate_fresh_ingest(self))["entity_row_count"]
        )

    @property
    def struct_asym_row_count(self) -> int:
        return int(
            _record_state_document(_validate_fresh_ingest(self))[
                "struct_asym_row_count"
            ]
        )

    @property
    def source_atom_row_count(self) -> int:
        return int(
            _record_state_document(_validate_fresh_ingest(self))[
                "source_atom_row_count"
            ]
        )

    @property
    def selected_atom_row_count(self) -> int:
        return int(
            _record_state_document(_validate_fresh_ingest(self))[
                "selected_atom_row_count"
            ]
        )

    @property
    def discarded_atom_row_count(self) -> int:
        return int(
            _record_state_document(_validate_fresh_ingest(self))[
                "discarded_atom_row_count"
            ]
        )

    @property
    def affected_residue_count(self) -> int:
        return int(
            _record_state_document(_validate_fresh_ingest(self))[
                "affected_residue_count"
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        state = _validate_fresh_ingest(self)
        document = _record_state_document(state)
        return {
            **document,
            "full_source_sha256": _source_binding_document(state)["full_source_sha256"],
            "source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
            "record_state_sha256": _sha256_bytes(state.record_state_bytes),
            "system_snapshot_sha256": _source_binding_document(state)[
                "system_snapshot_sha256"
            ],
        }


def _state_from_ingest(value: MmcifAltlocSelectionIngestResult) -> _ParsedState:
    return _ParsedState(
        full_source=value._full_source,
        source_id=value._source_id,
        altloc_id=value._altloc_id,
        source_projection_bytes=value._source_projection_bytes,
        selected_state_bytes=value._selected_state_bytes,
        system_snapshot=value._system_snapshot,
        canonical_output=value._canonical_output,
        record_state_bytes=value._record_state_bytes,
        source_binding_bytes=value._source_binding_bytes,
        category_rows=value._category_rows,
    )


def _validate_fresh_ingest(value: MmcifAltlocSelectionIngestResult) -> _ParsedState:
    if type(value) is not MmcifAltlocSelectionIngestResult:
        raise TypeError("an exact alternate-location ingest result is required")
    try:
        stored = _state_from_ingest(value)
        anchor = _ingest_state_anchor(value)
        binding = _canonical_json_bytes(_state_access_binding_document(stored))
    except Exception:
        raise MmcifAltlocSelectionError(
            "stale_ingest_binding", "stored ingest evidence differs from a fresh parse"
        ) from None
    if (
        stored != anchor
        or type(value._access_binding_bytes) is not bytes
        or binding != value._access_binding_bytes
    ):
        raise MmcifAltlocSelectionError(
            "stale_ingest_binding", "stored ingest evidence differs from a fresh parse"
        )
    return stored


def parse_mmcif_altloc_selection(
    data: bytes, *, altloc_id: str, source_id: str = ""
) -> MmcifAltlocSelectionIngestResult:
    """Parse the exact three-loop envelope and select ``altloc_id``."""

    state = _parse_state(data, altloc_id=altloc_id, source_id=source_id)
    return MmcifAltlocSelectionIngestResult(state, _factory_token=_FACTORY_TOKEN)


def mmcif_altloc_source_projection_sha256(
    value: MmcifAltlocSelectionIngestResult,
) -> str:
    return str(
        _record_state_document(_validate_fresh_ingest(value))[
            "source_projection_sha256"
        ]
    )


def mmcif_altloc_selected_state_sha256(
    value: MmcifAltlocSelectionIngestResult,
) -> str:
    return str(
        _record_state_document(_validate_fresh_ingest(value))["selected_state_sha256"]
    )


def mmcif_altloc_record_state_sha256(
    value: MmcifAltlocSelectionIngestResult,
) -> str:
    return _sha256_bytes(_validate_fresh_ingest(value).record_state_bytes)


def _receipt_document(state: _ParsedState, payload: bytes) -> dict[str, Any]:
    record = _record_state_document(state)
    return {
        "schema_id": MMCIF_ALTLOC_WRITE_RECEIPT_SCHEMA_ID,
        "envelope_version": MMCIF_ALTLOC_SELECTION_ENVELOPE_VERSION,
        "parser_version": MMCIF_ALTLOC_SELECTION_PARSER_VERSION,
        "writer_version": MMCIF_ALTLOC_SELECTION_WRITER_VERSION,
        "profile_id": MMCIF_ALTLOC_SELECTION_PROFILE_ID,
        "input_source_binding_sha256": _sha256_document(
            _source_binding_document(state)
        ),
        "input_record_state_sha256": _sha256_document(record),
        "input_source_projection_sha256": record["source_projection_sha256"],
        "input_selected_state_sha256": record["selected_state_sha256"],
        "input_topology_sha256": record["topology_sha256"],
        "source_id_sha256": record["source_id_sha256"],
        "altloc_id": state.altloc_id,
        "output_source_sha256": _sha256_bytes(payload),
        "output_byte_count": len(payload),
        "preservation_scope": MMCIF_ALTLOC_SELECTION_PROJECTION_SCOPE,
        **_authority_false_document(),
    }


@dataclass(frozen=True, init=False)
class MmcifAltlocSelectionWriteReceipt:
    _ingest: MmcifAltlocSelectionIngestResult = field(repr=False)
    _payload: bytes = field(repr=False)
    _document_bytes: bytes = field(repr=False)

    def __init__(
        self,
        ingest: MmcifAltlocSelectionIngestResult,
        payload: bytes,
        document: Mapping[str, Any],
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifAltlocSelectionWriteReceipt is factory-only")
        state = _validate_fresh_ingest(ingest)
        expected = _receipt_document(state, payload)
        if _plain(document) != expected or payload != state.canonical_output:
            raise MmcifAltlocSelectionError(
                "invalid_write_receipt", "write receipt does not bind canonical output"
            )
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(expected))

    @property
    def output_source_sha256(self) -> str:
        return str(_validate_receipt(self)["output_source_sha256"])

    @property
    def output_byte_count(self) -> int:
        return int(_validate_receipt(self)["output_byte_count"])

    @property
    def receipt_sha256(self) -> str:
        _validate_receipt(self)
        return _sha256_bytes(self._document_bytes)

    def to_dict(self) -> dict[str, Any]:
        document = _validate_receipt(self)
        return {**document, "receipt_sha256": _sha256_bytes(self._document_bytes)}


def _validate_receipt(value: MmcifAltlocSelectionWriteReceipt) -> dict[str, Any]:
    if type(value) is not MmcifAltlocSelectionWriteReceipt:
        raise TypeError("an exact alternate-location write receipt is required")
    try:
        state = _validate_fresh_ingest(value._ingest)
        expected = _receipt_document(state, value._payload)
        expected_bytes = _canonical_json_bytes(expected)
    except Exception:
        raise MmcifAltlocSelectionError(
            "stale_write_receipt_binding", "write receipt artifacts are stale"
        ) from None
    if (
        value._payload != state.canonical_output
        or value._document_bytes != expected_bytes
    ):
        raise MmcifAltlocSelectionError(
            "stale_write_receipt_binding", "write receipt artifacts are stale"
        )
    return expected


def _write_binding_document(
    ingest: MmcifAltlocSelectionIngestResult,
    payload: bytes,
    receipt: MmcifAltlocSelectionWriteReceipt,
) -> dict[str, Any]:
    state = _validate_fresh_ingest(ingest)
    return {
        "ingest_object_id": id(ingest),
        "receipt_object_id": id(receipt),
        "receipt_ingest_object_id": id(receipt._ingest),
        "source_binding_sha256": _sha256_document(_source_binding_document(state)),
        "record_state_sha256": _sha256_document(_record_state_document(state)),
        "payload_sha256": _sha256_bytes(payload),
        "receipt_sha256": receipt.receipt_sha256,
    }


@dataclass(frozen=True, init=False)
class MmcifAltlocSelectionWriteResult:
    _ingest: MmcifAltlocSelectionIngestResult = field(repr=False)
    _payload: bytes = field(repr=False)
    _receipt: MmcifAltlocSelectionWriteReceipt = field(repr=False)
    _raw_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        ingest: MmcifAltlocSelectionIngestResult,
        payload: bytes,
        receipt: MmcifAltlocSelectionWriteReceipt,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifAltlocSelectionWriteResult is factory-only")
        if (
            type(payload) is not bytes
            or type(receipt) is not MmcifAltlocSelectionWriteReceipt
        ):
            raise TypeError("write result requires exact payload and receipt artifacts")
        binding = _write_binding_document(ingest, payload, receipt)
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_receipt", receipt)
        object.__setattr__(self, "_raw_binding_bytes", _canonical_json_bytes(binding))

    @property
    def payload(self) -> bytes:
        _validate_write_result(self)
        return self._payload

    @property
    def receipt(self) -> MmcifAltlocSelectionWriteReceipt:
        _validate_write_result(self)
        return self._receipt

    def to_dict(self) -> dict[str, Any]:
        _validate_write_result(self)
        return {
            "output_source_sha256": _sha256_bytes(self._payload),
            "output_byte_count": len(self._payload),
            "receipt": self._receipt.to_dict(),
            **_authority_false_document(),
        }


def _validate_write_result(value: MmcifAltlocSelectionWriteResult) -> None:
    if type(value) is not MmcifAltlocSelectionWriteResult:
        raise TypeError("an exact alternate-location write result is required")
    try:
        state = _validate_fresh_ingest(value._ingest)
        _validate_receipt(value._receipt)
        binding = _write_binding_document(value._ingest, value._payload, value._receipt)
    except Exception:
        raise MmcifAltlocSelectionError(
            "stale_write_result_binding", "write result artifacts are stale"
        ) from None
    if (
        value._payload != state.canonical_output
        or value._receipt._ingest is not value._ingest
        or value._receipt._payload != value._payload
        or value._raw_binding_bytes != _canonical_json_bytes(binding)
    ):
        raise MmcifAltlocSelectionError(
            "stale_write_result_binding", "write result artifacts are stale"
        )


def emit_mmcif_altloc_selection(
    value: MmcifAltlocSelectionIngestResult,
) -> MmcifAltlocSelectionWriteResult:
    """Emit all source rows in the canonical three-loop layout."""

    state = _validate_fresh_ingest(value)
    payload = state.canonical_output
    reparsed = _parse_state(
        payload, altloc_id=state.altloc_id, source_id=state.source_id
    )
    if _record_state_document(reparsed) != _record_state_document(state):
        raise MmcifAltlocSelectionError(
            "round_trip_mismatch", "canonical output does not recover selected state"
        )
    receipt = MmcifAltlocSelectionWriteReceipt(
        value,
        payload,
        _receipt_document(state, payload),
        _factory_token=_FACTORY_TOKEN,
    )
    return MmcifAltlocSelectionWriteResult(
        value, payload, receipt, _factory_token=_FACTORY_TOKEN
    )


def serialize_mmcif_altloc_selection(
    value: MmcifAltlocSelectionIngestResult,
) -> bytes:
    return emit_mmcif_altloc_selection(value).payload


def _report_document(
    source: MmcifAltlocSelectionIngestResult,
    write_result: MmcifAltlocSelectionWriteResult,
    reparsed: MmcifAltlocSelectionIngestResult,
    second: MmcifAltlocSelectionWriteResult,
) -> dict[str, Any]:
    source_state = _validate_fresh_ingest(source)
    reparsed_state = _validate_fresh_ingest(reparsed)
    _validate_write_result(write_result)
    _validate_write_result(second)
    source_record = _record_state_document(source_state)
    reparsed_record = _record_state_document(reparsed_state)
    source_projection_equal = (
        source_state.source_projection_bytes == reparsed_state.source_projection_bytes
    )
    selected_state_equal = (
        source_state.selected_state_bytes == reparsed_state.selected_state_bytes
    )
    topology_equal = (
        source_record["topology_sha256"] == reparsed_record["topology_sha256"]
    )
    emitted_source_reparsed_exact = (
        write_result._payload == reparsed_state.full_source
        and _sha256_bytes(write_result._payload)
        == _sha256_bytes(reparsed_state.full_source)
    )
    stable = write_result._payload == second._payload
    return {
        "schema_id": MMCIF_ALTLOC_ROUND_TRIP_REPORT_SCHEMA_ID,
        "envelope_version": MMCIF_ALTLOC_SELECTION_ENVELOPE_VERSION,
        "parser_version": MMCIF_ALTLOC_SELECTION_PARSER_VERSION,
        "writer_version": MMCIF_ALTLOC_SELECTION_WRITER_VERSION,
        "profile_id": MMCIF_ALTLOC_SELECTION_PROFILE_ID,
        "altloc_id": source_state.altloc_id,
        "source_id_sha256": _source_id_sha256(source_state.source_id),
        "input_source_binding_sha256": _sha256_document(
            _source_binding_document(source_state)
        ),
        "input_record_state_sha256": _sha256_bytes(source_state.record_state_bytes),
        "reparsed_source_binding_sha256": _sha256_document(
            _source_binding_document(reparsed_state)
        ),
        "reparsed_record_state_sha256": _sha256_bytes(
            reparsed_state.record_state_bytes
        ),
        "input_source_projection_sha256": _sha256_bytes(
            source_state.source_projection_bytes
        ),
        "reparsed_source_projection_sha256": _sha256_bytes(
            reparsed_state.source_projection_bytes
        ),
        "input_selected_state_sha256": _sha256_bytes(source_state.selected_state_bytes),
        "reparsed_selected_state_sha256": _sha256_bytes(
            reparsed_state.selected_state_bytes
        ),
        "write_receipt_sha256": write_result._receipt.receipt_sha256,
        "reemitted_write_receipt_sha256": second._receipt.receipt_sha256,
        "emitted_source_sha256": _sha256_bytes(write_result._payload),
        "reemitted_source_sha256": _sha256_bytes(second._payload),
        "source_projection_equal": source_projection_equal,
        "selected_state_equal": selected_state_equal,
        "topology_equal": topology_equal,
        "record_state_equal": source_record == reparsed_record,
        "source_id_equal": source_state.source_id == reparsed_state.source_id,
        "emitted_source_reparsed_exact": emitted_source_reparsed_exact,
        "second_emission_byte_stable": stable,
        "explicit_altloc_round_trip_preserved": all(
            (
                source_projection_equal,
                selected_state_equal,
                topology_equal,
                emitted_source_reparsed_exact,
                stable,
                source_record == reparsed_record,
                source_state.source_id == reparsed_state.source_id,
            )
        ),
        **_authority_false_document(),
    }


@dataclass(frozen=True, init=False)
class MmcifAltlocSelectionRoundTripReport:
    _source_ingest: MmcifAltlocSelectionIngestResult = field(repr=False)
    _write_result: MmcifAltlocSelectionWriteResult = field(repr=False)
    _reparsed_ingest: MmcifAltlocSelectionIngestResult = field(repr=False)
    _reemitted_write_result: MmcifAltlocSelectionWriteResult = field(repr=False)
    _document_bytes: bytes = field(repr=False)
    _raw_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        source: MmcifAltlocSelectionIngestResult,
        write_result: MmcifAltlocSelectionWriteResult,
        reparsed: MmcifAltlocSelectionIngestResult,
        second: MmcifAltlocSelectionWriteResult,
        document: Mapping[str, Any],
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifAltlocSelectionRoundTripReport is factory-only")
        expected = _report_document(source, write_result, reparsed, second)
        if (
            _plain(document) != expected
            or expected["explicit_altloc_round_trip_preserved"] is not True
        ):
            raise MmcifAltlocSelectionError(
                "crosswired_round_trip_artifacts",
                "round-trip report is not an exact chain",
            )
        object.__setattr__(self, "_source_ingest", source)
        object.__setattr__(self, "_write_result", write_result)
        object.__setattr__(self, "_reparsed_ingest", reparsed)
        object.__setattr__(self, "_reemitted_write_result", second)
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(expected))
        object.__setattr__(
            self,
            "_raw_binding_bytes",
            _canonical_json_bytes(_report_binding_document(self)),
        )

    def _document(self) -> dict[str, Any]:
        return _validate_report(self)

    @property
    def report_sha256(self) -> str:
        self._document()
        return _sha256_bytes(self._document_bytes)

    @property
    def round_trip_report_sha256(self) -> str:
        return self.report_sha256

    @property
    def source_projection_equal(self) -> bool:
        return self._document()["source_projection_equal"] is True

    @property
    def selected_state_equal(self) -> bool:
        return self._document()["selected_state_equal"] is True

    @property
    def topology_equal(self) -> bool:
        return self._document()["topology_equal"] is True

    @property
    def emitted_source_reparsed_exact(self) -> bool:
        return self._document()["emitted_source_reparsed_exact"] is True

    @property
    def second_emission_byte_stable(self) -> bool:
        return self._document()["second_emission_byte_stable"] is True

    def to_dict(self) -> dict[str, Any]:
        document = self._document()
        return {**document, "report_sha256": _sha256_bytes(self._document_bytes)}


def _report_binding_document(
    value: MmcifAltlocSelectionRoundTripReport,
) -> dict[str, Any]:
    _validate_write_result(value._write_result)
    _validate_write_result(value._reemitted_write_result)
    return {
        "source_object_id": id(value._source_ingest),
        "write_object_id": id(value._write_result),
        "reparsed_object_id": id(value._reparsed_ingest),
        "reemitted_write_object_id": id(value._reemitted_write_result),
        "document_object_id": id(value._document_bytes),
        "document_sha256": _sha256_bytes(value._document_bytes),
        "source_binding_sha256": value._source_ingest.source_binding_sha256,
        "write_binding_sha256": _sha256_bytes(value._write_result._raw_binding_bytes),
        "reparsed_source_binding_sha256": value._reparsed_ingest.source_binding_sha256,
        "reemitted_write_binding_sha256": _sha256_bytes(
            value._reemitted_write_result._raw_binding_bytes
        ),
    }


def _validate_report(value: MmcifAltlocSelectionRoundTripReport) -> dict[str, Any]:
    if type(value) is not MmcifAltlocSelectionRoundTripReport:
        raise TypeError("an exact alternate-location round-trip report is required")
    try:
        if (
            type(value._source_ingest) is not MmcifAltlocSelectionIngestResult
            or type(value._write_result) is not MmcifAltlocSelectionWriteResult
            or type(value._reparsed_ingest) is not MmcifAltlocSelectionIngestResult
            or type(value._reemitted_write_result)
            is not MmcifAltlocSelectionWriteResult
            or type(value._document_bytes) is not bytes
            or type(value._raw_binding_bytes) is not bytes
        ):
            raise TypeError("round-trip report contains an invalid artifact type")
        _validate_fresh_ingest(value._source_ingest)
        _validate_fresh_ingest(value._reparsed_ingest)
        binding = _report_binding_document(value)
        document = json.loads(value._document_bytes.decode("ascii"))
    except Exception:
        raise MmcifAltlocSelectionError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        ) from None
    if (
        value._document_bytes != _canonical_json_bytes(document)
        or value._raw_binding_bytes != _canonical_json_bytes(binding)
        or document.get("explicit_altloc_round_trip_preserved") is not True
    ):
        raise MmcifAltlocSelectionError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )
    return document


@dataclass(frozen=True, init=False)
class MmcifAltlocSelectionRoundTripResult:
    _source_ingest: MmcifAltlocSelectionIngestResult = field(repr=False)
    _write_result: MmcifAltlocSelectionWriteResult = field(repr=False)
    _reparsed_ingest: MmcifAltlocSelectionIngestResult = field(repr=False)
    _reemitted_write_result: MmcifAltlocSelectionWriteResult = field(repr=False)
    _report: MmcifAltlocSelectionRoundTripReport = field(repr=False)
    _raw_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        source: MmcifAltlocSelectionIngestResult,
        write_result: MmcifAltlocSelectionWriteResult,
        reparsed: MmcifAltlocSelectionIngestResult,
        second: MmcifAltlocSelectionWriteResult,
        report: MmcifAltlocSelectionRoundTripReport,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifAltlocSelectionRoundTripResult is factory-only")
        binding = _aggregate_binding_document(
            source, write_result, reparsed, second, report
        )
        object.__setattr__(self, "_source_ingest", source)
        object.__setattr__(self, "_write_result", write_result)
        object.__setattr__(self, "_reparsed_ingest", reparsed)
        object.__setattr__(self, "_reemitted_write_result", second)
        object.__setattr__(self, "_report", report)
        object.__setattr__(self, "_raw_binding_bytes", _canonical_json_bytes(binding))

    def _validate(self) -> None:
        _validate_aggregate(self)

    @property
    def source_ingest(self) -> MmcifAltlocSelectionIngestResult:
        self._validate()
        return self._source_ingest

    @property
    def write_result(self) -> MmcifAltlocSelectionWriteResult:
        self._validate()
        return self._write_result

    @property
    def reparsed_ingest(self) -> MmcifAltlocSelectionIngestResult:
        self._validate()
        return self._reparsed_ingest

    @property
    def reemitted_write_result(self) -> MmcifAltlocSelectionWriteResult:
        self._validate()
        return self._reemitted_write_result

    @property
    def report(self) -> MmcifAltlocSelectionRoundTripReport:
        self._validate()
        return self._report

    def to_dict(self) -> dict[str, Any]:
        self._validate()
        return {
            "source_ingest": self._source_ingest.to_dict(),
            "write_result": self._write_result.to_dict(),
            "reparsed_ingest": self._reparsed_ingest.to_dict(),
            "reemitted_write_result": self._reemitted_write_result.to_dict(),
            "report": self._report.to_dict(),
            **_authority_false_document(),
        }


def _aggregate_binding_document(
    source: MmcifAltlocSelectionIngestResult,
    write_result: MmcifAltlocSelectionWriteResult,
    reparsed: MmcifAltlocSelectionIngestResult,
    second: MmcifAltlocSelectionWriteResult,
    report: MmcifAltlocSelectionRoundTripReport,
) -> dict[str, Any]:
    _validate_report(report)
    if (
        report._source_ingest is not source
        or report._write_result is not write_result
        or report._reparsed_ingest is not reparsed
        or report._reemitted_write_result is not second
        or write_result._ingest is not source
        or second._ingest is not reparsed
    ):
        raise MmcifAltlocSelectionError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )
    return {
        "source_object_id": id(source),
        "write_object_id": id(write_result),
        "reparsed_object_id": id(reparsed),
        "reemitted_write_object_id": id(second),
        "report_object_id": id(report),
        "source_binding_sha256": source.source_binding_sha256,
        "write_binding_sha256": _sha256_bytes(write_result._raw_binding_bytes),
        "reparsed_source_binding_sha256": reparsed.source_binding_sha256,
        "reemitted_write_binding_sha256": _sha256_bytes(second._raw_binding_bytes),
        "report_sha256": report.report_sha256,
    }


def _validate_aggregate(value: MmcifAltlocSelectionRoundTripResult) -> None:
    if type(value) is not MmcifAltlocSelectionRoundTripResult:
        raise TypeError("an exact alternate-location round-trip result is required")
    try:
        binding = _aggregate_binding_document(
            value._source_ingest,
            value._write_result,
            value._reparsed_ingest,
            value._reemitted_write_result,
            value._report,
        )
    except Exception:
        raise MmcifAltlocSelectionError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        ) from None
    if value._raw_binding_bytes != _canonical_json_bytes(binding):
        raise MmcifAltlocSelectionError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )


def round_trip_mmcif_altloc_selection_source(
    data: bytes, *, altloc_id: str, source_id: str = ""
) -> MmcifAltlocSelectionRoundTripResult:
    source = parse_mmcif_altloc_selection(
        data, altloc_id=altloc_id, source_id=source_id
    )
    write_result = emit_mmcif_altloc_selection(source)
    reparsed = parse_mmcif_altloc_selection(
        write_result.payload, altloc_id=altloc_id, source_id=source_id
    )
    second = emit_mmcif_altloc_selection(reparsed)
    document = _report_document(source, write_result, reparsed, second)
    if document["explicit_altloc_round_trip_preserved"] is not True:
        raise MmcifAltlocSelectionError(
            "round_trip_mismatch", "alternate-location preservation did not round trip"
        )
    report = MmcifAltlocSelectionRoundTripReport(
        source,
        write_result,
        reparsed,
        second,
        document,
        _factory_token=_FACTORY_TOKEN,
    )
    return MmcifAltlocSelectionRoundTripResult(
        source,
        write_result,
        reparsed,
        second,
        report,
        _factory_token=_FACTORY_TOKEN,
    )


__all__ = [
    "MAX_MMCIF_ALTLOC_SELECTION_ALTLOC_ID_CHARS",
    "MAX_MMCIF_ALTLOC_SELECTION_ATOM_ROWS",
    "MAX_MMCIF_ALTLOC_SELECTION_ENTITY_ROWS",
    "MAX_MMCIF_ALTLOC_SELECTION_INPUT_BYTES",
    "MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_BYTES",
    "MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_LINE_CHARS",
    "MAX_MMCIF_ALTLOC_SELECTION_PROJECTION_BYTES",
    "MAX_MMCIF_ALTLOC_SELECTION_SOURCE_ID_BYTES",
    "MAX_MMCIF_ALTLOC_SELECTION_STRUCT_ASYM_ROWS",
    "MAX_MMCIF_ALTLOC_SELECTION_TOKEN_CHARS",
    "MMCIF_ALTLOC_RECORD_STATE_SCHEMA_ID",
    "MMCIF_ALTLOC_ROUND_TRIP_REPORT_SCHEMA_ID",
    "MMCIF_ALTLOC_SELECTED_STATE_SCHEMA_ID",
    "MMCIF_ALTLOC_SELECTION_ATOM_SITE_HEADERS",
    "MMCIF_ALTLOC_SELECTION_ENTITY_HEADERS",
    "MMCIF_ALTLOC_SELECTION_ENVELOPE_VERSION",
    "MMCIF_ALTLOC_SELECTION_PARSER_NAME",
    "MMCIF_ALTLOC_SELECTION_PARSER_VERSION",
    "MMCIF_ALTLOC_SELECTION_PROFILE_ID",
    "MMCIF_ALTLOC_SELECTION_PROJECTION_SCOPE",
    "MMCIF_ALTLOC_SELECTION_STRUCT_ASYM_HEADERS",
    "MMCIF_ALTLOC_SELECTION_WRITER_VERSION",
    "MMCIF_ALTLOC_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_ALTLOC_SOURCE_PROJECTION_SCHEMA_ID",
    "MMCIF_ALTLOC_WRITE_RECEIPT_SCHEMA_ID",
    "MmcifAltlocSelectionError",
    "MmcifAltlocSelectionIngestResult",
    "MmcifAltlocSelectionRoundTripReport",
    "MmcifAltlocSelectionRoundTripResult",
    "MmcifAltlocSelectionWriteReceipt",
    "MmcifAltlocSelectionWriteResult",
    "emit_mmcif_altloc_selection",
    "mmcif_altloc_record_state_sha256",
    "mmcif_altloc_selected_state_sha256",
    "mmcif_altloc_source_projection_sha256",
    "parse_mmcif_altloc_selection",
    "round_trip_mmcif_altloc_selection_source",
    "serialize_mmcif_altloc_selection",
]
