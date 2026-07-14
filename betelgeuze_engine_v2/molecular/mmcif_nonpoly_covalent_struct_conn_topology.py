"""Strict opt-in covalent ``_struct_conn`` topology envelope.

This module extends the exact eight-category non-polymer component-topology
envelope with one narrowly constrained ``_struct_conn`` loop.  Only explicit
identity-symmetry ``covale`` rows with explicit single, double, or triple bond
order are accepted.  Both partners must join, in the combined label and auth
namespaces, to different non-polymer or water residue instances already
materialized by the component-topology carrier.

The result is bounded source-reported inter-residue topology evidence.  It is
not general ``_struct_conn`` support, source authentication, independent
chemistry or valence evidence, molecular preparation, parameterability,
runtime authority, or claim authority.  Digests are deterministic tamper
evidence only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import hashlib
import json
from typing import Any
import weakref

from .mmcif_nonpoly_component_topology import (
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
    MmcifNonpolyComponentTopologyError,
    MmcifNonpolyComponentTopologyIngestResult,
    parse_mmcif_nonpoly_component_topology,
    write_mmcif_nonpoly_component_topology,
)
from .mmcif_syntax import CifBlock, CifLoop, CifSyntaxError, CifToken, parse_cif_block
from .models import AllAtomSystem, Bond
from .observation import (
    PARSER_OBSERVATION_SCHEMA_ID,
    attach_parser_observation_digest,
    attached_parser_observation_sha256_matches,
)
from .serialization import deserialize_all_atom_system, serialize_all_atom_system
from .topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    attached_canonical_topology_sha256_matches,
    canonical_topology_sha256,
)


MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ENVELOPE_VERSION = "1.0.0"
MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_VERSION = "1.0.0"
MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_WRITER_VERSION = "1.0.0"
MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular."
    "mmcif_nonpoly_covalent_struct_conn_topology."
    "parse_mmcif_nonpoly_covalent_struct_conn_topology"
)
MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID = (
    "betelgeuze.mmcif_nonpoly_covalent_struct_conn_topology_parser/1.0.0"
)
MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROFILE_ID = (
    "strict_mmcif_nonpoly_covalent_struct_conn_topology_envelope/1.0.0"
)
MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROJECTION_SCHEMA_ID = (
    "betelgeuze.mmcif_nonpoly_covalent_struct_conn_topology_projection/1.0.0"
)
MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_STATE_SCHEMA_ID = (
    "betelgeuze.mmcif_nonpoly_covalent_struct_conn_topology_state/1.0.0"
)
MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.mmcif_nonpoly_covalent_struct_conn_topology_source_binding/1.0.0"
)
MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.mmcif_nonpoly_covalent_struct_conn_topology_write_receipt/1.0.0"
)
MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID = (
    "betelgeuze.mmcif_nonpoly_covalent_struct_conn_topology_round_trip_report/1.0.0"
)

MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_INPUT_BYTES = 64 * 1024 * 1024
MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROJECTION_BYTES = 64 * 1024 * 1024
MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_SOURCE_ID_BYTES = 4_096
MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_TOKEN_CHARS = 2_048
MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_OUTPUT_LINE_CHARS = 2_048
MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_ROWS = 120_000
MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_MATERIALIZED_BONDS = 120_000

MMCIF_NONPOLY_COVALENT_STRUCT_CONN_HEADERS = (
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

_COMPONENT_CATEGORY_ORDER = (
    "_entity",
    "_struct_asym",
    "_chem_comp",
    "_chem_comp_atom",
    "_chem_comp_bond",
    "_pdbx_entity_nonpoly",
    "_pdbx_nonpoly_scheme",
    "_atom_site",
)
_CATEGORY_ORDER = (*_COMPONENT_CATEGORY_ORDER[:-1], "_struct_conn", "_atom_site")
_EXPECTED_CATEGORIES = frozenset(_CATEGORY_ORDER)
_ORDER_BY_VALUE = {"sing": 1.0, "doub": 2.0, "trip": 3.0}
_FACTORY_TOKEN = object()
_INGEST_STATE_ANCHORS: dict[int, tuple[weakref.ReferenceType[Any], "_ParsedState"]] = {}
_FACTORY_ARTIFACT_ANCHORS: dict[int, tuple[weakref.ReferenceType[Any], bytes]] = {}

_FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
    "independent_chemistry_established",
    "independent_valence_established",
    "independent_aromaticity_established",
    "independent_stereo_established",
    "chemistry_inferred",
    "generic_chemistry_supported",
    "struct_conn_interpreted",
    "inter_residue_bonds_interpreted",
    "inter_residue_bonds_supported",
    "general_struct_conn_supported",
    "general_struct_conn_interpreted",
    "general_inter_residue_topology_supported",
    "role_assignment_interpreted",
    "coordination_interpreted",
    "protonation_interpreted",
    "preparation_ready",
    "generic_preparation_ready",
    "generic_molecular_preparation_ready",
    "global_preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "simulation_ready",
    "runtime_eligible",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_topology_complete",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)

_BOUNDED_TRUE_FIELDS = {
    "bounded_source_reported_struct_conn_materialized": True,
    "bounded_inter_residue_topology_interpreted": True,
    "source_reported_covalent_struct_conn_materialized": True,
}

_STRUCT_CONN_MARKER_KEY = "mmcif_nonpoly_covalent_struct_conn_topology"
_STRUCT_CONN_MARKER_FIELDS = frozenset(
    {
        "connection_id",
        "row_ordinal",
        "conn_type_id",
        "value_order",
        "ptnr1_atom_site_id",
        "ptnr2_atom_site_id",
        "ptnr1_atom_index",
        "ptnr2_atom_index",
        "ptnr1_residue_index",
        "ptnr2_residue_index",
        "ptnr1_symmetry",
        "ptnr2_symmetry",
    }
)


class MmcifNonpolyCovalentStructConnTopologyError(ValueError):
    """Privacy-safe fail-closed error for the exact nine-category profile."""

    def __init__(
        self, code: str, message: str, *, line_number: int | None = None
    ) -> None:
        self.code = str(code)
        self.detail = str(message)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            "mmcif_nonpoly_covalent_struct_conn_topology:"
            f"{self.code}{suffix}: {self.detail}"
        )


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


def _authority_false_document() -> dict[str, bool]:
    return {name: False for name in _FALSE_AUTHORITY_FIELDS}


def _source_id_sha256(source_id: str) -> str:
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    try:
        encoded = source_id.encode("utf-8")
    except UnicodeError:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "invalid_source_id",
            "source identifier must contain Unicode scalar values",
        ) from None
    if len(encoded) > MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_SOURCE_ID_BYTES:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "source_id_too_long", "source identifier exceeds the UTF-8 byte limit"
        )
    return _sha256_bytes(encoded)


def _parse_block(data: bytes) -> CifBlock:
    if type(data) is not bytes:
        raise TypeError("mmCIF covalent struct_conn topology input must be bytes")
    if not data:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "empty_input", "input is empty"
        )
    if len(data) > MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_INPUT_BYTES:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "input_too_large", "input exceeds the envelope byte limit"
        )
    try:
        decoded = data.decode("ascii")
    except UnicodeDecodeError:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "non_ascii_input", "input must use the CIF 1.1 ASCII character set"
        ) from None
    try:
        return parse_cif_block(decoded)
    except CifSyntaxError as exc:
        code = (
            "unsupported_category_representation"
            if exc.code == "duplicate_data_name"
            else exc.code
        )
        raise MmcifNonpolyCovalentStructConnTopologyError(
            code,
            "input is outside the exact single-block CIF envelope grammar",
            line_number=exc.line_number,
        ) from None


def _loop_for(block: CifBlock, category: str) -> CifLoop:
    scalar = [name for name in block.scalar_values if name.split(".", 1)[0] == category]
    loops = [loop for loop in block.loops if category in loop.categories]
    if scalar or len(loops) != 1 or loops[0].categories != (category,):
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "unsupported_category_representation",
            "each selected category must occur in one category-local loop",
        )
    return loops[0]


def _validate_surface(block: CifBlock) -> dict[str, CifLoop]:
    if (
        len(block.name) > MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_TOKEN_CHARS
        or len("data_") + len(block.name)
        > MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_OUTPUT_LINE_CHARS
    ):
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "block_name_too_long",
            "data-block name exceeds the canonical line character limit",
        )
    if set(block.categories) != _EXPECTED_CATEGORIES:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "unsupported_category_surface",
            "input categories must exactly match the nine-category envelope",
        )
    loops = {category: _loop_for(block, category) for category in _CATEGORY_ORDER}
    struct_conn = loops["_struct_conn"]
    if struct_conn.tags != MMCIF_NONPOLY_COVALENT_STRUCT_CONN_HEADERS:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "unsupported_struct_conn_headers",
            "_struct_conn headers are outside the exact 23-field profile",
            line_number=struct_conn.line_number,
        )
    if not struct_conn.rows:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "missing_struct_conn_rows", "the strict profile requires at least one row"
        )
    if len(struct_conn.rows) > MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_ROWS:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "too_many_struct_conn_rows", "_struct_conn row count exceeds the limit"
        )
    for row in struct_conn.rows:
        for token in row:
            if (
                len(token.value)
                > MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_TOKEN_CHARS
            ):
                raise MmcifNonpolyCovalentStructConnTopologyError(
                    "token_too_long",
                    "selected source token exceeds the character limit",
                    line_number=token.line_number,
                )
    return loops


def _bare_value(token: CifToken, *, allow_missing: bool = False) -> str:
    if token.quoted or token.multiline or "\n" in token.value or "\r" in token.value:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "invalid_struct_conn_token",
            "_struct_conn values must be bare single-line tokens",
            line_number=token.line_number,
        )
    if not allow_missing and token.value in {".", "?"}:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "invalid_struct_conn_token",
            "the selected _struct_conn field must be nonmissing",
            line_number=token.line_number,
        )
    if len(token.value) > MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_TOKEN_CHARS:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "token_too_long",
            "_struct_conn token exceeds the character limit",
            line_number=token.line_number,
        )
    return token.value


def _token_text(token: CifToken) -> str:
    if token.multiline:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "unsupported_multiline_token", "multiline tokens are outside the profile"
        )
    if not token.quoted:
        rendered = token.value
    elif "'" not in token.value:
        rendered = f"'{token.value}'"
    elif '"' not in token.value:
        rendered = f'"{token.value}"'
    else:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "unsupported_quoted_token", "a quoted token cannot be emitted canonically"
        )
    if (
        len(rendered)
        > MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_OUTPUT_LINE_CHARS
    ):
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "output_token_too_long", "canonical token exceeds the line limit"
        )
    return rendered


def _emit_rows(headers: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> bytes:
    lines = ["loop_", *headers]
    for row in rows:
        joined = " ".join(row)
        lines.extend(
            (joined,)
            if len(joined)
            <= MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_OUTPUT_LINE_CHARS
            else row
        )
    lines.append("#")
    return ("\n".join(lines) + "\n").encode("ascii")


def _emit_loop(loop: CifLoop) -> bytes:
    rows = tuple(tuple(_token_text(token) for token in row) for row in loop.rows)
    return _emit_rows(loop.tags, rows)


def _component_carrier_source(block: CifBlock, loops: Mapping[str, CifLoop]) -> bytes:
    return b"".join(
        (
            f"data_{block.name}\n#\n".encode("ascii"),
            *(_emit_loop(loops[category]) for category in _COMPONENT_CATEGORY_ORDER),
        )
    )


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MmcifNonpolyCovalentStructConnRow:
    connection_id: str
    conn_type_id: str
    ptnr1_label_asym_id: str
    ptnr1_label_comp_id: str
    ptnr1_label_seq_id: str
    ptnr1_label_atom_id: str
    ptnr1_label_alt_id: str
    ptnr1_pdb_ins_code: str
    ptnr1_symmetry: str
    ptnr2_label_asym_id: str
    ptnr2_label_comp_id: str
    ptnr2_label_seq_id: str
    ptnr2_label_atom_id: str
    ptnr2_label_alt_id: str
    ptnr2_pdb_ins_code: str
    ptnr1_auth_asym_id: str
    ptnr1_auth_comp_id: str
    ptnr1_auth_seq_id: str
    ptnr2_auth_asym_id: str
    ptnr2_auth_comp_id: str
    ptnr2_auth_seq_id: str
    ptnr2_symmetry: str
    value_order: str
    order: float
    row_ordinal: int

    def __init__(
        self,
        *,
        values: tuple[str, ...],
        order: float,
        row_ordinal: int,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("MmcifNonpolyCovalentStructConnRow is factory-only")
        if len(values) != len(MMCIF_NONPOLY_COVALENT_STRUCT_CONN_HEADERS):
            raise TypeError("struct_conn row requires exactly 23 values")
        names = (
            "connection_id",
            "conn_type_id",
            "ptnr1_label_asym_id",
            "ptnr1_label_comp_id",
            "ptnr1_label_seq_id",
            "ptnr1_label_atom_id",
            "ptnr1_label_alt_id",
            "ptnr1_pdb_ins_code",
            "ptnr1_symmetry",
            "ptnr2_label_asym_id",
            "ptnr2_label_comp_id",
            "ptnr2_label_seq_id",
            "ptnr2_label_atom_id",
            "ptnr2_label_alt_id",
            "ptnr2_pdb_ins_code",
            "ptnr1_auth_asym_id",
            "ptnr1_auth_comp_id",
            "ptnr1_auth_seq_id",
            "ptnr2_auth_asym_id",
            "ptnr2_auth_comp_id",
            "ptnr2_auth_seq_id",
            "ptnr2_symmetry",
            "value_order",
        )
        for name, value in zip(names, values, strict=True):
            if type(value) is not str:
                raise TypeError("struct_conn values must be exact strings")
            object.__setattr__(self, name, value)
        if type(order) is not float or type(row_ordinal) is not int:
            raise TypeError("struct_conn order and row ordinal have invalid types")
        object.__setattr__(self, "order", order)
        object.__setattr__(self, "row_ordinal", row_ordinal)

    def values(self) -> tuple[str, ...]:
        return (
            self.connection_id,
            self.conn_type_id,
            self.ptnr1_label_asym_id,
            self.ptnr1_label_comp_id,
            self.ptnr1_label_seq_id,
            self.ptnr1_label_atom_id,
            self.ptnr1_label_alt_id,
            self.ptnr1_pdb_ins_code,
            self.ptnr1_symmetry,
            self.ptnr2_label_asym_id,
            self.ptnr2_label_comp_id,
            self.ptnr2_label_seq_id,
            self.ptnr2_label_atom_id,
            self.ptnr2_label_alt_id,
            self.ptnr2_pdb_ins_code,
            self.ptnr1_auth_asym_id,
            self.ptnr1_auth_comp_id,
            self.ptnr1_auth_seq_id,
            self.ptnr2_auth_asym_id,
            self.ptnr2_auth_comp_id,
            self.ptnr2_auth_seq_id,
            self.ptnr2_symmetry,
            self.value_order,
        )


def _parse_struct_conn_rows(
    loop: CifLoop,
) -> tuple[MmcifNonpolyCovalentStructConnRow, ...]:
    rows: list[MmcifNonpolyCovalentStructConnRow] = []
    seen_ids: set[str] = set()
    for ordinal, tokens in enumerate(loop.rows, 1):
        values = tuple(_bare_value(token, allow_missing=True) for token in tokens)
        for index in (
            0,
            1,
            2,
            3,
            5,
            8,
            9,
            10,
            12,
            15,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
        ):
            if values[index] in {".", "?"}:
                raise MmcifNonpolyCovalentStructConnTopologyError(
                    "missing_required_struct_conn_value",
                    "a required _struct_conn value is missing",
                    line_number=tokens[index].line_number,
                )
        connection_id = values[0]
        if connection_id in seen_ids:
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "duplicate_struct_conn_id", "_struct_conn ids must be unique"
            )
        seen_ids.add(connection_id)
        if values[1] != "covale":
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "unsupported_struct_conn_type",
                "conn_type_id must be the exact bare token covale",
            )
        if values[4] != "." or values[11] != ".":
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "unsupported_partner_label_seq_id",
                "both non-polymer partner label_seq_id values must be .",
            )
        if values[6] != "." or values[13] != ".":
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "unsupported_partner_alt_id",
                "both partner label_alt_id values must be .",
            )
        if values[7] != "?" or values[14] != "?":
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "unsupported_partner_insertion_code",
                "both partner PDB insertion-code values must be ?",
            )
        if values[8] != "1_555" or values[21] != "1_555":
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "unsupported_partner_symmetry",
                "both partner symmetry values must be exact identity 1_555",
            )
        if values[22] not in _ORDER_BY_VALUE:
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "unsupported_struct_conn_bond_order",
                "pdbx_value_order must be explicit lowercase sing, doub, or trip",
            )
        rows.append(
            MmcifNonpolyCovalentStructConnRow(
                values=values,
                order=_ORDER_BY_VALUE[values[22]],
                row_ordinal=ordinal,
                _factory_token=_FACTORY_TOKEN,
            )
        )
    return tuple(rows)


def _atom_site_value(atom: Any, tag: str) -> str:
    mmcif = atom.metadata.get("mmcif")
    atom_site = mmcif.get("atom_site") if isinstance(mmcif, Mapping) else None
    payload = atom_site.get(tag) if isinstance(atom_site, Mapping) else None
    value = payload.get("value") if isinstance(payload, Mapping) else None
    if type(value) is not str:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "carrier_atom_identity_missing",
            "component carrier atom lacks an exact atom-site identity token",
        )
    return value


def _atom_identity(atom: Any) -> tuple[str, ...]:
    return tuple(
        _atom_site_value(atom, tag)
        for tag in (
            "_atom_site.label_asym_id",
            "_atom_site.label_comp_id",
            "_atom_site.label_seq_id",
            "_atom_site.label_atom_id",
            "_atom_site.label_alt_id",
            "_atom_site.pdbx_pdb_ins_code",
            "_atom_site.auth_asym_id",
            "_atom_site.auth_comp_id",
            "_atom_site.auth_seq_id",
        )
    )


def _partner_identity(
    row: MmcifNonpolyCovalentStructConnRow, partner: int
) -> tuple[str, ...]:
    if partner == 1:
        return (
            row.ptnr1_label_asym_id,
            row.ptnr1_label_comp_id,
            row.ptnr1_label_seq_id,
            row.ptnr1_label_atom_id,
            row.ptnr1_label_alt_id,
            row.ptnr1_pdb_ins_code,
            row.ptnr1_auth_asym_id,
            row.ptnr1_auth_comp_id,
            row.ptnr1_auth_seq_id,
        )
    return (
        row.ptnr2_label_asym_id,
        row.ptnr2_label_comp_id,
        row.ptnr2_label_seq_id,
        row.ptnr2_label_atom_id,
        row.ptnr2_label_alt_id,
        row.ptnr2_pdb_ins_code,
        row.ptnr2_auth_asym_id,
        row.ptnr2_auth_comp_id,
        row.ptnr2_auth_seq_id,
    )


def _source_atom_site_id(atom: Any) -> str:
    mmcif = atom.metadata.get("mmcif")
    value = mmcif.get("source_atom_site_id") if isinstance(mmcif, Mapping) else None
    if type(value) is not str or value in {"", ".", "?"}:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "carrier_atom_site_id_missing",
            "component carrier atom lacks a source atom-site id",
        )
    return value


def _resolve_rows(
    carrier: MmcifNonpolyComponentTopologyIngestResult,
    rows: tuple[MmcifNonpolyCovalentStructConnRow, ...],
) -> tuple[tuple[MmcifNonpolyCovalentStructConnRow, int, int], ...]:
    system = carrier.system
    exact: dict[tuple[str, ...], int] = {}
    labels: dict[tuple[str, ...], set[int]] = {}
    auth: dict[tuple[str, ...], set[int]] = {}
    for atom in system.atoms:
        identity = _atom_identity(atom)
        if identity in exact:
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "ambiguous_carrier_atom_identity",
                "combined label and auth atom identity is not unique",
            )
        exact[identity] = atom.index
        labels.setdefault(identity[:6], set()).add(atom.index)
        auth.setdefault(identity[6:], set()).add(atom.index)

    existing_pairs = {(bond.atom_i, bond.atom_j) for bond in system.bonds}
    seen_pairs: set[tuple[int, int]] = set()
    resolved: list[tuple[MmcifNonpolyCovalentStructConnRow, int, int]] = []
    for row in rows:
        endpoint_indices: list[int] = []
        for partner in (1, 2):
            identity = _partner_identity(row, partner)
            atom_index = exact.get(identity)
            if atom_index is None:
                if identity[:6] in labels or identity[6:] in auth:
                    raise MmcifNonpolyCovalentStructConnTopologyError(
                        "crosswired_struct_conn_partner",
                        "partner label and auth namespaces do not identify one atom",
                    )
                raise MmcifNonpolyCovalentStructConnTopologyError(
                    "unknown_struct_conn_partner",
                    "a partner does not join to a component-materialized atom",
                )
            atom = system.atoms[atom_index]
            residue = system.residues[atom.residue_index]
            if residue.entity_type not in {"non_polymer", "water"} or not isinstance(
                atom.metadata.get("mmcif_nonpoly_component_topology"), Mapping
            ):
                raise MmcifNonpolyCovalentStructConnTopologyError(
                    "unsupported_struct_conn_partner_scope",
                    "partners must be component-materialized nonpoly or water atoms",
                )
            endpoint_indices.append(atom_index)
        ptnr1, ptnr2 = endpoint_indices
        if ptnr1 == ptnr2:
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "self_struct_conn_bond", "_struct_conn must not describe a self bond"
            )
        pair = (min(ptnr1, ptnr2), max(ptnr1, ptnr2))
        if pair in existing_pairs:
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "already_materialized_bond",
                "_struct_conn must not repeat a component-materialized bond",
            )
        residue_1 = system.atoms[ptnr1].residue_index
        residue_2 = system.atoms[ptnr2].residue_index
        if residue_1 == residue_2:
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "same_residue_struct_conn_bond",
                "the strict profile accepts only inter-residue bonds",
            )
        if pair in seen_pairs:
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "duplicate_struct_conn_bond",
                "duplicate or reversed _struct_conn endpoint pairs are forbidden",
            )
        seen_pairs.add(pair)
        resolved.append((row, ptnr1, ptnr2))
    return tuple(resolved)


def _projection_document(
    carrier: MmcifNonpolyComponentTopologyIngestResult,
    rows: tuple[MmcifNonpolyCovalentStructConnRow, ...],
) -> dict[str, Any]:
    carrier_document = carrier.to_dict()
    return {
        "schema_id": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROJECTION_SCHEMA_ID,
        "envelope_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ENVELOPE_VERSION,
        "profile_id": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROFILE_ID,
        "carrier_profile_id": MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
        "carrier_component_projection_sha256": carrier_document[
            "component_projection_sha256"
        ],
        "struct_conn_headers": list(MMCIF_NONPOLY_COVALENT_STRUCT_CONN_HEADERS),
        "struct_conn_rows": [list(row.values()) for row in rows],
        "struct_conn_row_count": len(rows),
        **_BOUNDED_TRUE_FIELDS,
        **_authority_false_document(),
    }


def _canonical_output(
    carrier: MmcifNonpolyComponentTopologyIngestResult,
    rows: tuple[MmcifNonpolyCovalentStructConnRow, ...],
) -> bytes:
    carrier_output = write_mmcif_nonpoly_component_topology(carrier).payload
    try:
        block = parse_cif_block(carrier_output.decode("ascii"))
    except (UnicodeDecodeError, CifSyntaxError):
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "carrier_emission_invalid",
            "the bound component carrier emitted invalid CIF",
        ) from None
    carrier_loops = {
        category: _loop_for(block, category) for category in _COMPONENT_CATEGORY_ORDER
    }
    pieces: list[bytes] = [f"data_{block.name}\n#\n".encode("ascii")]
    for category in _CATEGORY_ORDER:
        if category == "_struct_conn":
            pieces.append(
                _emit_rows(
                    MMCIF_NONPOLY_COVALENT_STRUCT_CONN_HEADERS,
                    tuple(row.values() for row in rows),
                )
            )
        else:
            pieces.append(_emit_loop(carrier_loops[category]))
    payload = b"".join(pieces)
    if len(payload) > MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_OUTPUT_BYTES:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "output_too_large", "canonical output exceeds the envelope byte limit"
        )
    _validate_surface(_parse_block(payload))
    return payload


def _materialize_system(
    carrier: MmcifNonpolyComponentTopologyIngestResult,
    resolved: tuple[tuple[MmcifNonpolyCovalentStructConnRow, int, int], ...],
    *,
    full_source: bytes,
    canonical_output: bytes,
) -> AllAtomSystem:
    carrier_system = carrier.system
    carrier_document = carrier.to_dict()
    if (
        len(carrier_system.bonds) + len(resolved)
        > MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_MATERIALIZED_BONDS
    ):
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "too_many_materialized_bonds",
            "merged component and struct_conn bonds exceed the profile limit",
        )
    pending: list[tuple[int, int, Bond]] = [
        (bond.atom_i, bond.atom_j, bond) for bond in carrier_system.bonds
    ]
    for row, ptnr1, ptnr2 in resolved:
        residue_1 = carrier_system.atoms[ptnr1].residue_index
        residue_2 = carrier_system.atoms[ptnr2].residue_index
        marker = {
            "connection_id": row.connection_id,
            "row_ordinal": row.row_ordinal,
            "conn_type_id": row.conn_type_id,
            "value_order": row.value_order,
            "ptnr1_atom_site_id": _source_atom_site_id(carrier_system.atoms[ptnr1]),
            "ptnr2_atom_site_id": _source_atom_site_id(carrier_system.atoms[ptnr2]),
            "ptnr1_atom_index": ptnr1,
            "ptnr2_atom_index": ptnr2,
            "ptnr1_residue_index": residue_1,
            "ptnr2_residue_index": residue_2,
            "ptnr1_symmetry": row.ptnr1_symmetry,
            "ptnr2_symmetry": row.ptnr2_symmetry,
        }
        pending.append(
            (
                min(ptnr1, ptnr2),
                max(ptnr1, ptnr2),
                Bond(
                    index=-1,
                    atom_i=min(ptnr1, ptnr2),
                    atom_j=max(ptnr1, ptnr2),
                    order=row.order,
                    aromatic=False,
                    stereo="none",
                    source="mmcif_struct_conn_covale",
                    metadata={_STRUCT_CONN_MARKER_KEY: marker},
                ),
            )
        )
    pending.sort(key=lambda item: (item[0], item[1]))
    bonds = tuple(
        replace(bond, index=index) for index, (*_, bond) in enumerate(pending)
    )

    provenance_metadata = dict(carrier_system.provenance.metadata)
    inherited_component_marker = provenance_metadata.pop(
        "mmcif_nonpoly_component_topology", None
    )
    provenance_metadata.pop("canonical_topology_schema_id", None)
    provenance_metadata.pop("canonical_topology_sha256", None)
    provenance_metadata.pop("parser_observation_schema_id", None)
    provenance_metadata.pop("parser_observation_sha256", None)
    provenance_metadata["carrier_mmcif_nonpoly_component_topology"] = (
        inherited_component_marker
    )
    provenance_metadata[_STRUCT_CONN_MARKER_KEY] = {
        "canonical_output_sha256": _sha256_bytes(canonical_output),
        "source_sha256_semantics": "raw_full_source_bytes",
        "carrier_evidence_semantics": (
            "preserved_component_topology_carrier_only_not_struct_conn_evidence"
        ),
    }
    provenance = replace(
        carrier_system.provenance,
        source_sha256=_sha256_bytes(full_source),
        parser_name=MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_NAME,
        parser_version=MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_VERSION,
        operations=(
            *carrier_system.provenance.operations,
            "join_exact_struct_conn_label_auth_partners/v1",
            "materialize_explicit_identity_symmetry_covale_bonds/v1",
        ),
        parent_sha256=(carrier_document["augmented_system_snapshot_sha256"],),
        preparation_ready=False,
        claim_safe=False,
        metadata=provenance_metadata,
    )
    metadata = dict(carrier_system.metadata)
    inherited_system_component_marker = metadata.pop(
        "mmcif_nonpoly_component_topology", None
    )
    metadata["carrier_mmcif_nonpoly_component_topology"] = (
        inherited_system_component_marker
    )
    mmcif_metadata = dict(metadata.get("mmcif", {}))
    mmcif_metadata["component_topology_carrier_evidence_semantics"] = (
        "preserved_component_topology_carrier_only_not_struct_conn_evidence"
    )
    metadata["mmcif"] = mmcif_metadata
    metadata[_STRUCT_CONN_MARKER_KEY] = {
        "profile_id": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROFILE_ID,
        "struct_conn_row_count": len(resolved),
        "materialized_inter_residue_bond_count": len(resolved),
        **_BOUNDED_TRUE_FIELDS,
        **_authority_false_document(),
    }
    system = replace(
        carrier_system,
        bonds=bonds,
        provenance=provenance,
        metadata=metadata,
    )
    topology_sha256 = canonical_topology_sha256(system)
    refreshed_metadata = dict(system.provenance.metadata)
    refreshed_metadata["canonical_topology_schema_id"] = CANONICAL_TOPOLOGY_SCHEMA_ID
    refreshed_metadata["canonical_topology_sha256"] = topology_sha256
    system = replace(
        system,
        provenance=replace(system.provenance, metadata=refreshed_metadata),
    )
    return attach_parser_observation_digest(system)


@dataclass(frozen=True, slots=True)
class _ParsedState:
    full_source: bytes = field(repr=False)
    source_id: str = field(repr=False)
    carrier_source: bytes = field(repr=False)
    carrier_ingest: MmcifNonpolyComponentTopologyIngestResult = field(repr=False)
    carrier_object_id: int
    struct_conn_rows: tuple[MmcifNonpolyCovalentStructConnRow, ...] = field(repr=False)
    projection_bytes: bytes = field(repr=False)
    system_snapshot: bytes = field(repr=False)
    canonical_output: bytes = field(repr=False)
    topology_state_bytes: bytes = field(repr=False)
    source_binding_bytes: bytes = field(repr=False)


def _compute_topology_state_document(state: _ParsedState) -> dict[str, Any]:
    system = deserialize_all_atom_system(state.system_snapshot)
    carrier_system = state.carrier_ingest.system
    carrier_document = state.carrier_ingest.to_dict()
    return {
        "schema_id": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_STATE_SCHEMA_ID,
        "envelope_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ENVELOPE_VERSION,
        "parser_name": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_NAME,
        "parser_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_VERSION,
        "parser_pedigree_id": (
            MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID
        ),
        "writer_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_WRITER_VERSION,
        "profile_id": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROFILE_ID,
        "carrier_profile_id": MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "parser_observation_schema_id": PARSER_OBSERVATION_SCHEMA_ID,
        "attached_canonical_topology_digest_self_consistent": (
            attached_canonical_topology_sha256_matches(system)
        ),
        "attached_parser_observation_digest_self_consistent": (
            attached_parser_observation_sha256_matches(system)
        ),
        "source_id_sha256": _source_id_sha256(state.source_id),
        "carrier_component_projection_sha256": (
            carrier_document["component_projection_sha256"]
        ),
        "carrier_topology_state_sha256": carrier_document["topology_state_sha256"],
        "carrier_augmented_topology_sha256": (
            carrier_document["augmented_topology_sha256"]
        ),
        "carrier_augmented_system_snapshot_sha256": (
            carrier_document["augmented_system_snapshot_sha256"]
        ),
        "struct_conn_projection_sha256": _sha256_bytes(state.projection_bytes),
        "augmented_topology_sha256": canonical_topology_sha256(system),
        "struct_conn_row_count": len(state.struct_conn_rows),
        "carrier_bond_count": len(carrier_system.bonds),
        "materialized_inter_residue_bond_count": len(state.struct_conn_rows),
        "materialized_bond_count": len(system.bonds),
        "materialized_atom_count": system.atom_count,
        "topology_state_scope": (
            "normalized_component_carrier_struct_conn_projection_and_canonical_topology"
        ),
        "source_specific_augmented_snapshot_bound_in": (
            "source_binding_and_write_receipt"
        ),
        "combined_label_auth_partner_join_required": True,
        "identity_symmetry_only": True,
        "explicit_covale_order_only": True,
        **_BOUNDED_TRUE_FIELDS,
        **_authority_false_document(),
    }


def _topology_state_document(state: _ParsedState) -> dict[str, Any]:
    return json.loads(state.topology_state_bytes.decode("ascii"))


def _compute_source_binding_document(state: _ParsedState) -> dict[str, Any]:
    system = deserialize_all_atom_system(state.system_snapshot)
    carrier_document = state.carrier_ingest.to_dict()
    return {
        "schema_id": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID,
        "envelope_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ENVELOPE_VERSION,
        "parser_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_VERSION,
        "parser_pedigree_id": (
            MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID
        ),
        "profile_id": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROFILE_ID,
        "full_source_sha256": _sha256_bytes(state.full_source),
        "source_id_sha256": _source_id_sha256(state.source_id),
        "carrier_source_sha256": _sha256_bytes(state.carrier_source),
        "carrier_full_source_sha256": carrier_document["full_source_sha256"],
        "carrier_source_binding_sha256": carrier_document["source_binding_sha256"],
        "struct_conn_projection_sha256": _sha256_bytes(state.projection_bytes),
        "augmented_system_snapshot_sha256": _sha256_bytes(state.system_snapshot),
        "augmented_system_provenance_source_sha256": system.provenance.source_sha256,
        "augmented_system_parser_observation_sha256": (
            system.provenance.metadata.get("parser_observation_sha256")
        ),
        "canonical_output_sha256": _sha256_bytes(state.canonical_output),
        "topology_state_sha256": _sha256_bytes(state.topology_state_bytes),
        "provenance_source_sha256_semantics": "raw_full_source_bytes",
        **_BOUNDED_TRUE_FIELDS,
        **_authority_false_document(),
    }


def _source_binding_document(state: _ParsedState) -> dict[str, Any]:
    return json.loads(state.source_binding_bytes.decode("ascii"))


def _parse_state(data: bytes, *, source_id: str) -> _ParsedState:
    _source_id_sha256(source_id)
    block = _parse_block(data)
    loops = _validate_surface(block)
    rows = _parse_struct_conn_rows(loops["_struct_conn"])
    raw_carrier_source = _component_carrier_source(block, loops)
    try:
        carrier = parse_mmcif_nonpoly_component_topology(
            raw_carrier_source, source_id=source_id
        )
        carrier_source = write_mmcif_nonpoly_component_topology(carrier).payload
        carrier = parse_mmcif_nonpoly_component_topology(
            carrier_source, source_id=source_id
        )
    except MmcifNonpolyComponentTopologyError as exc:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "carrier_component_topology_rejected",
            "the exact component-topology carrier rejected its projection",
            line_number=exc.line_number,
        ) from None
    try:
        resolved = _resolve_rows(carrier, rows)
        canonical_output = _canonical_output(carrier, rows)
        system = _materialize_system(
            carrier,
            resolved,
            full_source=data,
            canonical_output=canonical_output,
        )
        projection_bytes = _canonical_json_bytes(_projection_document(carrier, rows))
        if (
            len(projection_bytes)
            > MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROJECTION_BYTES
        ):
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "projection_too_large", "struct_conn projection exceeds the byte limit"
            )
        state = _ParsedState(
            full_source=data,
            source_id=source_id,
            carrier_source=carrier_source,
            carrier_ingest=carrier,
            carrier_object_id=id(carrier),
            struct_conn_rows=rows,
            projection_bytes=projection_bytes,
            system_snapshot=serialize_all_atom_system(system),
            canonical_output=canonical_output,
            topology_state_bytes=b"",
            source_binding_bytes=b"",
        )
        state = replace(
            state,
            topology_state_bytes=_canonical_json_bytes(
                _compute_topology_state_document(state)
            ),
        )
        return replace(
            state,
            source_binding_bytes=_canonical_json_bytes(
                _compute_source_binding_document(state)
            ),
        )
    except MmcifNonpolyCovalentStructConnTopologyError:
        raise
    except Exception:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "struct_conn_topology_integration_failed",
            "covalent struct_conn topology integration failed closed",
        ) from None


def _state_access_binding_document(state: _ParsedState) -> dict[str, Any]:
    byte_fields = {
        "full_source": state.full_source,
        "carrier_source": state.carrier_source,
        "projection": state.projection_bytes,
        "system_snapshot": state.system_snapshot,
        "canonical_output": state.canonical_output,
        "topology_state": state.topology_state_bytes,
        "source_binding": state.source_binding_bytes,
    }
    if any(type(value) is not bytes for value in byte_fields.values()):
        raise TypeError("bound ingest byte fields must remain exact bytes")
    if (
        type(state.carrier_ingest) is not MmcifNonpolyComponentTopologyIngestResult
        or id(state.carrier_ingest) != state.carrier_object_id
    ):
        raise TypeError("bound component carrier object is inconsistent")
    if type(state.struct_conn_rows) is not tuple:
        raise TypeError("bound struct_conn rows must remain an exact tuple")
    row_content: list[dict[str, Any]] = []
    for row in state.struct_conn_rows:
        if (
            type(row) is not MmcifNonpolyCovalentStructConnRow
            or type(row.order) is not float
            or type(row.row_ordinal) is not int
        ):
            raise TypeError("bound struct_conn row fields are not exact")
        values = row.values()
        if len(values) != len(MMCIF_NONPOLY_COVALENT_STRUCT_CONN_HEADERS) or any(
            type(value) is not str for value in values
        ):
            raise TypeError("bound struct_conn row values are not exact strings")
        row_content.append(
            {
                "values": list(values),
                "order_hex": row.order.hex(),
                "row_ordinal": row.row_ordinal,
            }
        )
    row_content_bytes = _canonical_json_bytes({"rows": row_content})
    _source_id_sha256(state.source_id)
    return {
        "byte_objects": {
            name: {"object_id": id(value), "byte_count": len(value)}
            for name, value in byte_fields.items()
        },
        "source_id_object_id": id(state.source_id),
        "source_id_sha256": _source_id_sha256(state.source_id),
        "carrier_object_id": id(state.carrier_ingest),
        "struct_conn_rows": {
            "object_id": id(state.struct_conn_rows),
            "row_count": len(state.struct_conn_rows),
            "content_sha256": _sha256_bytes(row_content_bytes),
        },
    }


def _register_ingest_state_anchor(
    value: "MmcifNonpolyCovalentStructConnTopologyIngestResult", state: _ParsedState
) -> None:
    key = id(value)

    def discard(reference: weakref.ReferenceType[Any]) -> None:
        current = _INGEST_STATE_ANCHORS.get(key)
        if current is not None and current[0] is reference:
            _INGEST_STATE_ANCHORS.pop(key, None)

    reference = weakref.ref(value, discard)
    _INGEST_STATE_ANCHORS[key] = (reference, state)


def _ingest_state_anchor(
    value: "MmcifNonpolyCovalentStructConnTopologyIngestResult",
) -> _ParsedState:
    current = _INGEST_STATE_ANCHORS.get(id(value))
    if (
        current is None
        or current[0]() is not value
        or type(current[1]) is not _ParsedState
    ):
        raise ValueError("ingest has no live factory state anchor")
    return current[1]


def _register_factory_artifact_anchor(value: Any, access_binding: bytes) -> None:
    if type(access_binding) is not bytes:
        raise TypeError("factory artifact access binding must be exact bytes")
    key = id(value)

    def discard(reference: weakref.ReferenceType[Any]) -> None:
        current = _FACTORY_ARTIFACT_ANCHORS.get(key)
        if current is not None and current[0] is reference:
            _FACTORY_ARTIFACT_ANCHORS.pop(key, None)

    reference = weakref.ref(value, discard)
    _FACTORY_ARTIFACT_ANCHORS[key] = (reference, access_binding)


def _validate_factory_artifact_anchor(
    value: Any, current_access_binding: bytes
) -> None:
    current = _FACTORY_ARTIFACT_ANCHORS.get(id(value))
    stored_access_binding = getattr(value, "_access_binding_bytes")
    if (
        type(current_access_binding) is not bytes
        or current is None
        or current[0]() is not value
        or type(current[1]) is not bytes
        or type(stored_access_binding) is not bytes
        or stored_access_binding is not current[1]
        or stored_access_binding != current_access_binding
    ):
        raise ValueError("artifact has no live factory access anchor")


@dataclass(frozen=True, init=False)
class MmcifNonpolyCovalentStructConnTopologyIngestResult:
    _full_source: bytes = field(repr=False)
    _source_id: str = field(repr=False)
    _carrier_source: bytes = field(repr=False)
    _carrier_ingest: MmcifNonpolyComponentTopologyIngestResult = field(repr=False)
    _carrier_object_id: int = field(repr=False)
    _struct_conn_rows: tuple[MmcifNonpolyCovalentStructConnRow, ...] = field(repr=False)
    _projection_bytes: bytes = field(repr=False)
    _system_snapshot: bytes = field(repr=False)
    _canonical_output: bytes = field(repr=False)
    _topology_state_bytes: bytes = field(repr=False)
    _source_binding_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self, state: _ParsedState, *, _factory_token: object | None = None
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifNonpolyCovalentStructConnTopologyIngestResult is factory-only"
            )
        if type(state) is not _ParsedState:
            raise TypeError("ingest construction requires exact private parsed state")
        for name in (
            "full_source",
            "source_id",
            "carrier_source",
            "carrier_ingest",
            "carrier_object_id",
            "struct_conn_rows",
            "projection_bytes",
            "system_snapshot",
            "canonical_output",
            "topology_state_bytes",
            "source_binding_bytes",
        ):
            object.__setattr__(self, f"_{name}", getattr(state, name))
        object.__setattr__(
            self,
            "_access_binding_bytes",
            _canonical_json_bytes(_state_access_binding_document(state)),
        )
        _register_factory_artifact_anchor(self, self._access_binding_bytes)
        _register_ingest_state_anchor(self, state)

    @property
    def system(self) -> AllAtomSystem:
        return deserialize_all_atom_system(_validate_fresh_ingest(self).system_snapshot)

    @property
    def carrier_ingest(self) -> MmcifNonpolyComponentTopologyIngestResult:
        return _validate_fresh_ingest(self).carrier_ingest

    @property
    def struct_conn_rows(self) -> tuple[MmcifNonpolyCovalentStructConnRow, ...]:
        rows = _validate_fresh_ingest(self).struct_conn_rows
        return tuple(
            MmcifNonpolyCovalentStructConnRow(
                values=row.values(),
                order=row.order,
                row_ordinal=row.row_ordinal,
                _factory_token=_FACTORY_TOKEN,
            )
            for row in rows
        )

    @property
    def full_source_sha256(self) -> str:
        return str(
            _source_binding_document(_validate_fresh_ingest(self))["full_source_sha256"]
        )

    @property
    def source_id_sha256(self) -> str:
        return str(
            _topology_state_document(_validate_fresh_ingest(self))["source_id_sha256"]
        )

    @property
    def struct_conn_projection_sha256(self) -> str:
        return _sha256_bytes(_validate_fresh_ingest(self).projection_bytes)

    @property
    def topology_state_sha256(self) -> str:
        return _sha256_bytes(_validate_fresh_ingest(self).topology_state_bytes)

    @property
    def record_state_sha256(self) -> str:
        return self.topology_state_sha256

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_bytes(_validate_fresh_ingest(self).source_binding_bytes)

    @property
    def augmented_system_snapshot_sha256(self) -> str:
        return str(
            _source_binding_document(_validate_fresh_ingest(self))[
                "augmented_system_snapshot_sha256"
            ]
        )

    @property
    def system_snapshot_sha256(self) -> str:
        return self.augmented_system_snapshot_sha256

    @property
    def augmented_topology_sha256(self) -> str:
        return str(
            _topology_state_document(_validate_fresh_ingest(self))[
                "augmented_topology_sha256"
            ]
        )

    @property
    def topology_sha256(self) -> str:
        return self.augmented_topology_sha256

    def to_dict(self) -> dict[str, Any]:
        state = _validate_fresh_ingest(self)
        source_binding = _source_binding_document(state)
        return {
            **_topology_state_document(state),
            "full_source_sha256": source_binding["full_source_sha256"],
            "augmented_system_snapshot_sha256": source_binding[
                "augmented_system_snapshot_sha256"
            ],
            "augmented_system_provenance_source_sha256": source_binding[
                "augmented_system_provenance_source_sha256"
            ],
            "augmented_system_parser_observation_sha256": source_binding[
                "augmented_system_parser_observation_sha256"
            ],
            "canonical_output_sha256": source_binding["canonical_output_sha256"],
            "source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
            "topology_state_sha256": _sha256_bytes(state.topology_state_bytes),
        }


def _state_from_ingest(
    value: MmcifNonpolyCovalentStructConnTopologyIngestResult,
) -> _ParsedState:
    return _ParsedState(
        full_source=value._full_source,
        source_id=value._source_id,
        carrier_source=value._carrier_source,
        carrier_ingest=value._carrier_ingest,
        carrier_object_id=value._carrier_object_id,
        struct_conn_rows=value._struct_conn_rows,
        projection_bytes=value._projection_bytes,
        system_snapshot=value._system_snapshot,
        canonical_output=value._canonical_output,
        topology_state_bytes=value._topology_state_bytes,
        source_binding_bytes=value._source_binding_bytes,
    )


def _validate_fresh_ingest(
    value: MmcifNonpolyCovalentStructConnTopologyIngestResult,
) -> _ParsedState:
    if type(value) is not MmcifNonpolyCovalentStructConnTopologyIngestResult:
        raise TypeError("an exact covalent struct_conn topology ingest is required")
    try:
        stored = _state_from_ingest(value)
        anchor = _ingest_state_anchor(value)
        stored_access = _canonical_json_bytes(_state_access_binding_document(stored))
        anchor_access = _canonical_json_bytes(_state_access_binding_document(anchor))
        _validate_factory_artifact_anchor(value, stored_access)
        carrier_document = stored.carrier_ingest.to_dict()
        system = deserialize_all_atom_system(stored.system_snapshot)
        topology_state = _topology_state_document(stored)
        source_binding = _source_binding_document(stored)
        profile_metadata = system.metadata.get(_STRUCT_CONN_MARKER_KEY)
        carrier_profile_metadata = system.metadata.get(
            "carrier_mmcif_nonpoly_component_topology"
        )
        provenance_metadata = system.provenance.metadata
        struct_conn_bonds = [
            bond for bond in system.bonds if bond.source == "mmcif_struct_conn_covale"
        ]
    except Exception:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "stale_ingest_binding", "stored ingest evidence differs from factory state"
        ) from None
    marker_valid = all(
        set(bond.metadata) == {_STRUCT_CONN_MARKER_KEY}
        and isinstance(bond.metadata.get(_STRUCT_CONN_MARKER_KEY), Mapping)
        and set(bond.metadata[_STRUCT_CONN_MARKER_KEY]) == _STRUCT_CONN_MARKER_FIELDS
        and bond.aromatic is False
        and bond.stereo == "none"
        for bond in struct_conn_bonds
    )
    if (
        stored != anchor
        or stored_access != anchor_access
        or type(value._access_binding_bytes) is not bytes
        or value._access_binding_bytes != anchor_access
        or stored.carrier_object_id != id(stored.carrier_ingest)
        or _sha256_bytes(stored.system_snapshot)
        != source_binding["augmented_system_snapshot_sha256"]
        or _sha256_bytes(stored.full_source) != source_binding["full_source_sha256"]
        or _sha256_bytes(stored.carrier_source)
        != source_binding["carrier_source_sha256"]
        or _sha256_bytes(stored.projection_bytes)
        != source_binding["struct_conn_projection_sha256"]
        or _sha256_bytes(stored.canonical_output)
        != source_binding["canonical_output_sha256"]
        or _sha256_bytes(stored.topology_state_bytes)
        != source_binding["topology_state_sha256"]
        or carrier_document["full_source_sha256"]
        != source_binding["carrier_full_source_sha256"]
        or carrier_document["source_binding_sha256"]
        != source_binding["carrier_source_binding_sha256"]
        or carrier_document["component_projection_sha256"]
        != topology_state["carrier_component_projection_sha256"]
        or carrier_document["topology_state_sha256"]
        != topology_state["carrier_topology_state_sha256"]
        or system.provenance.source_sha256 != source_binding["full_source_sha256"]
        or system.provenance.source_format != "mmcif"
        or system.provenance.parser_name
        != MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_NAME
        or system.provenance.parser_version
        != MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_VERSION
        or system.provenance.preparation_ready is not False
        or system.provenance.claim_safe is not False
        or not attached_canonical_topology_sha256_matches(system)
        or not attached_parser_observation_sha256_matches(system)
        or provenance_metadata.get("canonical_topology_schema_id")
        != CANONICAL_TOPOLOGY_SCHEMA_ID
        or provenance_metadata.get("parser_observation_schema_id")
        != PARSER_OBSERVATION_SCHEMA_ID
        or "mmcif_nonpoly_component_topology" in provenance_metadata
        or "mmcif_nonpoly_component_topology" in system.metadata
        or not isinstance(
            provenance_metadata.get("carrier_mmcif_nonpoly_component_topology"),
            Mapping,
        )
        or not isinstance(carrier_profile_metadata, Mapping)
        or not isinstance(profile_metadata, Mapping)
        or profile_metadata.get("profile_id")
        != MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROFILE_ID
        or any(
            profile_metadata.get(name) is not False for name in _FALSE_AUTHORITY_FIELDS
        )
        or any(profile_metadata.get(name) is not True for name in _BOUNDED_TRUE_FIELDS)
        or len(struct_conn_bonds) != len(stored.struct_conn_rows)
        or not marker_valid
        or canonical_topology_sha256(system)
        != topology_state["augmented_topology_sha256"]
    ):
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "stale_ingest_binding", "stored ingest evidence differs from factory state"
        )
    return stored


def parse_mmcif_nonpoly_covalent_struct_conn_topology(
    data: bytes, *, source_id: str = ""
) -> MmcifNonpolyCovalentStructConnTopologyIngestResult:
    """Parse the exact nine-category covalent struct_conn envelope."""

    state = _parse_state(data, source_id=source_id)
    return MmcifNonpolyCovalentStructConnTopologyIngestResult(
        state, _factory_token=_FACTORY_TOKEN
    )


def mmcif_nonpoly_covalent_struct_conn_topology_projection_sha256(
    value: MmcifNonpolyCovalentStructConnTopologyIngestResult,
) -> str:
    return _sha256_bytes(_validate_fresh_ingest(value).projection_bytes)


def mmcif_nonpoly_covalent_struct_conn_topology_state_sha256(
    value: MmcifNonpolyCovalentStructConnTopologyIngestResult,
) -> str:
    return _sha256_bytes(_validate_fresh_ingest(value).topology_state_bytes)


def mmcif_nonpoly_covalent_struct_conn_topology_record_state_sha256(
    value: MmcifNonpolyCovalentStructConnTopologyIngestResult,
) -> str:
    return mmcif_nonpoly_covalent_struct_conn_topology_state_sha256(value)


def _receipt_document(state: _ParsedState, payload: bytes) -> dict[str, Any]:
    topology = _topology_state_document(state)
    source_binding = _source_binding_document(state)
    return {
        "schema_id": (
            MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID
        ),
        "envelope_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ENVELOPE_VERSION,
        "parser_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_VERSION,
        "writer_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_WRITER_VERSION,
        "profile_id": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROFILE_ID,
        "input_source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
        "input_topology_state_sha256": _sha256_bytes(state.topology_state_bytes),
        "input_struct_conn_projection_sha256": _sha256_bytes(state.projection_bytes),
        "input_augmented_system_snapshot_sha256": source_binding[
            "augmented_system_snapshot_sha256"
        ],
        "input_augmented_topology_sha256": topology["augmented_topology_sha256"],
        "carrier_topology_state_sha256": topology["carrier_topology_state_sha256"],
        "output_source_sha256": _sha256_bytes(payload),
        "output_byte_count": len(payload),
        "struct_conn_row_count": len(state.struct_conn_rows),
        "materialized_inter_residue_bond_count": topology[
            "materialized_inter_residue_bond_count"
        ],
        **_BOUNDED_TRUE_FIELDS,
        **_authority_false_document(),
    }


def _receipt_access_document(
    value: "MmcifNonpolyCovalentStructConnTopologyWriteReceipt",
) -> dict[str, Any]:
    if (
        type(value) is not MmcifNonpolyCovalentStructConnTopologyWriteReceipt
        or type(value._ingest) is not MmcifNonpolyCovalentStructConnTopologyIngestResult
        or type(value._payload) is not bytes
        or type(value._document_bytes) is not bytes
    ):
        raise TypeError("write receipt access fields are not exact")
    return {
        "artifact_type": "MmcifNonpolyCovalentStructConnTopologyWriteReceipt",
        "self_object_id": id(value),
        "ingest_object_id": id(value._ingest),
        "payload_object_id": id(value._payload),
        "payload_sha256": _sha256_bytes(value._payload),
        "document_object_id": id(value._document_bytes),
        "document_sha256": _sha256_bytes(value._document_bytes),
    }


@dataclass(frozen=True, init=False)
class MmcifNonpolyCovalentStructConnTopologyWriteReceipt:
    _ingest: MmcifNonpolyCovalentStructConnTopologyIngestResult = field(repr=False)
    _payload: bytes = field(repr=False)
    _document_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        ingest: MmcifNonpolyCovalentStructConnTopologyIngestResult,
        payload: bytes,
        document: Mapping[str, Any],
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifNonpolyCovalentStructConnTopologyWriteReceipt is factory-only"
            )
        state = _validate_fresh_ingest(ingest)
        expected = _receipt_document(state, payload)
        if dict(document) != expected or payload != state.canonical_output:
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "invalid_write_receipt", "receipt does not bind canonical output"
            )
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(expected))
        access = _canonical_json_bytes(_receipt_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", access)
        _register_factory_artifact_anchor(self, access)

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


def _validate_receipt(
    value: MmcifNonpolyCovalentStructConnTopologyWriteReceipt,
    *,
    _validated_state: _ParsedState | None = None,
) -> dict[str, Any]:
    if type(value) is not MmcifNonpolyCovalentStructConnTopologyWriteReceipt:
        raise TypeError("an exact covalent struct_conn receipt is required")
    try:
        _validate_factory_artifact_anchor(
            value, _canonical_json_bytes(_receipt_access_document(value))
        )
        state = (
            _validate_fresh_ingest(value._ingest)
            if _validated_state is None
            else _validated_state
        )
        if value._ingest is not None and state != _state_from_ingest(value._ingest):
            raise ValueError("validated receipt state does not match its ingest")
        expected = _receipt_document(state, value._payload)
    except Exception:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "stale_write_receipt_binding", "write receipt artifacts are stale"
        ) from None
    if (
        value._payload != state.canonical_output
        or value._document_bytes != _canonical_json_bytes(expected)
    ):
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "stale_write_receipt_binding", "write receipt artifacts are stale"
        )
    return expected


def _write_binding_document(
    ingest: MmcifNonpolyCovalentStructConnTopologyIngestResult,
    payload: bytes,
    receipt: MmcifNonpolyCovalentStructConnTopologyWriteReceipt,
) -> dict[str, Any]:
    state = _state_from_ingest(ingest)
    return {
        "ingest_object_id": id(ingest),
        "receipt_object_id": id(receipt),
        "receipt_ingest_object_id": id(receipt._ingest),
        "source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
        "topology_state_sha256": _sha256_bytes(state.topology_state_bytes),
        "payload_sha256": _sha256_bytes(payload),
        "receipt_sha256": _sha256_bytes(receipt._document_bytes),
    }


def _write_result_access_document(
    value: "MmcifNonpolyCovalentStructConnTopologyWriteResult",
) -> dict[str, Any]:
    if (
        type(value) is not MmcifNonpolyCovalentStructConnTopologyWriteResult
        or type(value._ingest) is not MmcifNonpolyCovalentStructConnTopologyIngestResult
        or type(value._payload) is not bytes
        or type(value._receipt)
        is not MmcifNonpolyCovalentStructConnTopologyWriteReceipt
        or type(value._raw_binding_bytes) is not bytes
    ):
        raise TypeError("write result access fields are not exact")
    return {
        "artifact_type": "MmcifNonpolyCovalentStructConnTopologyWriteResult",
        "self_object_id": id(value),
        "ingest_object_id": id(value._ingest),
        "payload_object_id": id(value._payload),
        "payload_sha256": _sha256_bytes(value._payload),
        "receipt_object_id": id(value._receipt),
        "raw_binding_object_id": id(value._raw_binding_bytes),
        "raw_binding_sha256": _sha256_bytes(value._raw_binding_bytes),
    }


@dataclass(frozen=True, init=False)
class MmcifNonpolyCovalentStructConnTopologyWriteResult:
    _ingest: MmcifNonpolyCovalentStructConnTopologyIngestResult = field(repr=False)
    _payload: bytes = field(repr=False)
    _receipt: MmcifNonpolyCovalentStructConnTopologyWriteReceipt = field(repr=False)
    _raw_binding_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        ingest: MmcifNonpolyCovalentStructConnTopologyIngestResult,
        payload: bytes,
        receipt: MmcifNonpolyCovalentStructConnTopologyWriteReceipt,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifNonpolyCovalentStructConnTopologyWriteResult is factory-only"
            )
        if (
            type(payload) is not bytes
            or type(receipt) is not MmcifNonpolyCovalentStructConnTopologyWriteReceipt
        ):
            raise TypeError("write result requires exact payload and receipt artifacts")
        state = _validate_fresh_ingest(ingest)
        _validate_receipt(receipt, _validated_state=state)
        if receipt._ingest is not ingest or receipt._payload is not payload:
            raise MmcifNonpolyCovalentStructConnTopologyError(
                "stale_write_result_binding", "write result artifacts are crosswired"
            )
        binding = _write_binding_document(ingest, payload, receipt)
        object.__setattr__(self, "_ingest", ingest)
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_receipt", receipt)
        object.__setattr__(self, "_raw_binding_bytes", _canonical_json_bytes(binding))
        access = _canonical_json_bytes(_write_result_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", access)
        _register_factory_artifact_anchor(self, access)

    @property
    def payload(self) -> bytes:
        _validate_write_result(self)
        return self._payload

    @property
    def receipt(self) -> MmcifNonpolyCovalentStructConnTopologyWriteReceipt:
        _validate_write_result(self)
        return self._receipt

    def to_dict(self) -> dict[str, Any]:
        _validate_write_result(self)
        return {
            "output_source_sha256": _sha256_bytes(self._payload),
            "output_byte_count": len(self._payload),
            "receipt": self._receipt.to_dict(),
            **_BOUNDED_TRUE_FIELDS,
            **_authority_false_document(),
        }


def _validate_write_result(
    value: MmcifNonpolyCovalentStructConnTopologyWriteResult,
) -> _ParsedState:
    if type(value) is not MmcifNonpolyCovalentStructConnTopologyWriteResult:
        raise TypeError("an exact covalent struct_conn write result is required")
    try:
        _validate_factory_artifact_anchor(
            value, _canonical_json_bytes(_write_result_access_document(value))
        )
        state = _validate_fresh_ingest(value._ingest)
        _validate_receipt(value._receipt, _validated_state=state)
        binding = _write_binding_document(value._ingest, value._payload, value._receipt)
    except Exception:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "stale_write_result_binding", "write result artifacts are stale"
        ) from None
    if (
        value._payload != state.canonical_output
        or value._receipt._ingest is not value._ingest
        or value._receipt._payload is not value._payload
        or value._raw_binding_bytes != _canonical_json_bytes(binding)
    ):
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "stale_write_result_binding", "write result artifacts are stale"
        )
    return state


def write_mmcif_nonpoly_covalent_struct_conn_topology(
    value: MmcifNonpolyCovalentStructConnTopologyIngestResult,
) -> MmcifNonpolyCovalentStructConnTopologyWriteResult:
    """Emit the deterministic nine-category canonical representation."""

    state = _validate_fresh_ingest(value)
    payload = state.canonical_output
    reparsed = _parse_state(payload, source_id=state.source_id)
    if (
        reparsed.projection_bytes != state.projection_bytes
        or reparsed.topology_state_bytes != state.topology_state_bytes
        or reparsed.canonical_output != payload
    ):
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "round_trip_mismatch",
            "canonical output does not recover the bound topology state",
        )
    receipt = MmcifNonpolyCovalentStructConnTopologyWriteReceipt(
        value,
        payload,
        _receipt_document(state, payload),
        _factory_token=_FACTORY_TOKEN,
    )
    return MmcifNonpolyCovalentStructConnTopologyWriteResult(
        value, payload, receipt, _factory_token=_FACTORY_TOKEN
    )


def emit_mmcif_nonpoly_covalent_struct_conn_topology(
    value: MmcifNonpolyCovalentStructConnTopologyIngestResult,
) -> MmcifNonpolyCovalentStructConnTopologyWriteResult:
    return write_mmcif_nonpoly_covalent_struct_conn_topology(value)


def serialize_mmcif_nonpoly_covalent_struct_conn_topology(
    value: MmcifNonpolyCovalentStructConnTopologyIngestResult,
) -> bytes:
    return write_mmcif_nonpoly_covalent_struct_conn_topology(value).payload


def _report_document(
    source: MmcifNonpolyCovalentStructConnTopologyIngestResult,
    write_result: MmcifNonpolyCovalentStructConnTopologyWriteResult,
    reparsed: MmcifNonpolyCovalentStructConnTopologyIngestResult,
    second: MmcifNonpolyCovalentStructConnTopologyWriteResult,
) -> dict[str, Any]:
    source_state = _validate_write_result(write_result)
    reparsed_state = _validate_write_result(second)
    if write_result._ingest is not source or second._ingest is not reparsed:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )
    projection_equal = source_state.projection_bytes == reparsed_state.projection_bytes
    topology_state_equal = (
        source_state.topology_state_bytes == reparsed_state.topology_state_bytes
    )
    topology_equal = (
        _topology_state_document(source_state)["augmented_topology_sha256"]
        == _topology_state_document(reparsed_state)["augmented_topology_sha256"]
    )
    carrier_state_equal = (
        _topology_state_document(source_state)["carrier_topology_state_sha256"]
        == _topology_state_document(reparsed_state)["carrier_topology_state_sha256"]
    )
    exact_reparse = (
        write_result._payload == reparsed_state.full_source
        and _sha256_bytes(write_result._payload)
        == _source_binding_document(reparsed_state)["full_source_sha256"]
    )
    stable = write_result._payload == second._payload
    preserved = all(
        (
            projection_equal,
            topology_state_equal,
            topology_equal,
            carrier_state_equal,
            exact_reparse,
            stable,
            source_state.source_id == reparsed_state.source_id,
        )
    )
    return {
        "schema_id": (
            MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID
        ),
        "envelope_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ENVELOPE_VERSION,
        "parser_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_VERSION,
        "writer_version": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_WRITER_VERSION,
        "profile_id": MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROFILE_ID,
        "source_id_sha256": _source_id_sha256(source_state.source_id),
        "input_source_binding_sha256": _sha256_bytes(source_state.source_binding_bytes),
        "reparsed_source_binding_sha256": _sha256_bytes(
            reparsed_state.source_binding_bytes
        ),
        "input_struct_conn_projection_sha256": _sha256_bytes(
            source_state.projection_bytes
        ),
        "reparsed_struct_conn_projection_sha256": _sha256_bytes(
            reparsed_state.projection_bytes
        ),
        "input_topology_state_sha256": _sha256_bytes(source_state.topology_state_bytes),
        "reparsed_topology_state_sha256": _sha256_bytes(
            reparsed_state.topology_state_bytes
        ),
        "input_augmented_topology_sha256": _topology_state_document(source_state)[
            "augmented_topology_sha256"
        ],
        "reparsed_augmented_topology_sha256": _topology_state_document(reparsed_state)[
            "augmented_topology_sha256"
        ],
        "write_receipt_sha256": write_result._receipt.receipt_sha256,
        "reemitted_write_receipt_sha256": second._receipt.receipt_sha256,
        "emitted_source_sha256": _sha256_bytes(write_result._payload),
        "reemitted_source_sha256": _sha256_bytes(second._payload),
        "struct_conn_projection_equal": projection_equal,
        "topology_state_equal": topology_state_equal,
        "topology_equal": topology_equal,
        "carrier_state_equal": carrier_state_equal,
        "emitted_source_reparsed_exact": exact_reparse,
        "second_emission_byte_stable": stable,
        "source_reported_covalent_struct_conn_round_trip_preserved": preserved,
        **_BOUNDED_TRUE_FIELDS,
        **_authority_false_document(),
    }


def _report_access_document(
    value: "MmcifNonpolyCovalentStructConnTopologyRoundTripReport",
) -> dict[str, Any]:
    if (
        type(value) is not MmcifNonpolyCovalentStructConnTopologyRoundTripReport
        or type(value._source_ingest)
        is not MmcifNonpolyCovalentStructConnTopologyIngestResult
        or type(value._write_result)
        is not MmcifNonpolyCovalentStructConnTopologyWriteResult
        or type(value._reparsed_ingest)
        is not MmcifNonpolyCovalentStructConnTopologyIngestResult
        or type(value._reemitted_write_result)
        is not MmcifNonpolyCovalentStructConnTopologyWriteResult
        or type(value._document_bytes) is not bytes
        or type(value._raw_binding_bytes) is not bytes
    ):
        raise TypeError("round-trip report access fields are not exact")
    return {
        "artifact_type": "MmcifNonpolyCovalentStructConnTopologyRoundTripReport",
        "self_object_id": id(value),
        "source_object_id": id(value._source_ingest),
        "write_object_id": id(value._write_result),
        "reparsed_object_id": id(value._reparsed_ingest),
        "reemitted_write_object_id": id(value._reemitted_write_result),
        "document_object_id": id(value._document_bytes),
        "document_sha256": _sha256_bytes(value._document_bytes),
        "raw_binding_object_id": id(value._raw_binding_bytes),
        "raw_binding_sha256": _sha256_bytes(value._raw_binding_bytes),
    }


def _report_binding_document(
    value: "MmcifNonpolyCovalentStructConnTopologyRoundTripReport",
) -> dict[str, Any]:
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


@dataclass(frozen=True, init=False)
class MmcifNonpolyCovalentStructConnTopologyRoundTripReport:
    _source_ingest: MmcifNonpolyCovalentStructConnTopologyIngestResult = field(
        repr=False
    )
    _write_result: MmcifNonpolyCovalentStructConnTopologyWriteResult = field(repr=False)
    _reparsed_ingest: MmcifNonpolyCovalentStructConnTopologyIngestResult = field(
        repr=False
    )
    _reemitted_write_result: MmcifNonpolyCovalentStructConnTopologyWriteResult = field(
        repr=False
    )
    _document_bytes: bytes = field(repr=False)
    _raw_binding_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        source: MmcifNonpolyCovalentStructConnTopologyIngestResult,
        write_result: MmcifNonpolyCovalentStructConnTopologyWriteResult,
        reparsed: MmcifNonpolyCovalentStructConnTopologyIngestResult,
        second: MmcifNonpolyCovalentStructConnTopologyWriteResult,
        document: Mapping[str, Any],
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifNonpolyCovalentStructConnTopologyRoundTripReport is factory-only"
            )
        expected = _report_document(source, write_result, reparsed, second)
        if (
            dict(document) != expected
            or expected["source_reported_covalent_struct_conn_round_trip_preserved"]
            is not True
        ):
            raise MmcifNonpolyCovalentStructConnTopologyError(
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
        access = _canonical_json_bytes(_report_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", access)
        _register_factory_artifact_anchor(self, access)

    @property
    def report_sha256(self) -> str:
        _validate_report(self)
        return _sha256_bytes(self._document_bytes)

    @property
    def round_trip_report_sha256(self) -> str:
        return self.report_sha256

    @property
    def struct_conn_projection_equal(self) -> bool:
        return _validate_report(self)["struct_conn_projection_equal"] is True

    @property
    def topology_state_equal(self) -> bool:
        return _validate_report(self)["topology_state_equal"] is True

    @property
    def topology_equal(self) -> bool:
        return _validate_report(self)["topology_equal"] is True

    @property
    def emitted_source_reparsed_exact(self) -> bool:
        return _validate_report(self)["emitted_source_reparsed_exact"] is True

    @property
    def second_emission_byte_stable(self) -> bool:
        return _validate_report(self)["second_emission_byte_stable"] is True

    def to_dict(self) -> dict[str, Any]:
        document = _validate_report(self)
        return {**document, "report_sha256": _sha256_bytes(self._document_bytes)}


def _validate_report(
    value: MmcifNonpolyCovalentStructConnTopologyRoundTripReport,
) -> dict[str, Any]:
    if type(value) is not MmcifNonpolyCovalentStructConnTopologyRoundTripReport:
        raise TypeError("an exact covalent struct_conn report is required")
    try:
        _validate_factory_artifact_anchor(
            value, _canonical_json_bytes(_report_access_document(value))
        )
        binding = _report_binding_document(value)
        expected = _report_document(
            value._source_ingest,
            value._write_result,
            value._reparsed_ingest,
            value._reemitted_write_result,
        )
    except Exception:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        ) from None
    if (
        value._document_bytes != _canonical_json_bytes(expected)
        or value._raw_binding_bytes != _canonical_json_bytes(binding)
        or expected.get("source_reported_covalent_struct_conn_round_trip_preserved")
        is not True
    ):
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )
    return expected


def _aggregate_binding_document(
    source: MmcifNonpolyCovalentStructConnTopologyIngestResult,
    write_result: MmcifNonpolyCovalentStructConnTopologyWriteResult,
    reparsed: MmcifNonpolyCovalentStructConnTopologyIngestResult,
    second: MmcifNonpolyCovalentStructConnTopologyWriteResult,
    report: MmcifNonpolyCovalentStructConnTopologyRoundTripReport,
) -> dict[str, Any]:
    if (
        report._source_ingest is not source
        or report._write_result is not write_result
        or report._reparsed_ingest is not reparsed
        or report._reemitted_write_result is not second
        or write_result._ingest is not source
        or second._ingest is not reparsed
    ):
        raise MmcifNonpolyCovalentStructConnTopologyError(
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
        "report_sha256": _sha256_bytes(report._document_bytes),
    }


def _aggregate_access_document(
    value: "MmcifNonpolyCovalentStructConnTopologyRoundTripResult",
) -> dict[str, Any]:
    if (
        type(value) is not MmcifNonpolyCovalentStructConnTopologyRoundTripResult
        or type(value._source_ingest)
        is not MmcifNonpolyCovalentStructConnTopologyIngestResult
        or type(value._write_result)
        is not MmcifNonpolyCovalentStructConnTopologyWriteResult
        or type(value._reparsed_ingest)
        is not MmcifNonpolyCovalentStructConnTopologyIngestResult
        or type(value._reemitted_write_result)
        is not MmcifNonpolyCovalentStructConnTopologyWriteResult
        or type(value._report)
        is not MmcifNonpolyCovalentStructConnTopologyRoundTripReport
        or type(value._raw_binding_bytes) is not bytes
    ):
        raise TypeError("round-trip result access fields are not exact")
    return {
        "artifact_type": "MmcifNonpolyCovalentStructConnTopologyRoundTripResult",
        "self_object_id": id(value),
        "source_object_id": id(value._source_ingest),
        "write_object_id": id(value._write_result),
        "reparsed_object_id": id(value._reparsed_ingest),
        "reemitted_write_object_id": id(value._reemitted_write_result),
        "report_object_id": id(value._report),
        "raw_binding_object_id": id(value._raw_binding_bytes),
        "raw_binding_sha256": _sha256_bytes(value._raw_binding_bytes),
    }


@dataclass(frozen=True, init=False)
class MmcifNonpolyCovalentStructConnTopologyRoundTripResult:
    _source_ingest: MmcifNonpolyCovalentStructConnTopologyIngestResult = field(
        repr=False
    )
    _write_result: MmcifNonpolyCovalentStructConnTopologyWriteResult = field(repr=False)
    _reparsed_ingest: MmcifNonpolyCovalentStructConnTopologyIngestResult = field(
        repr=False
    )
    _reemitted_write_result: MmcifNonpolyCovalentStructConnTopologyWriteResult = field(
        repr=False
    )
    _report: MmcifNonpolyCovalentStructConnTopologyRoundTripReport = field(repr=False)
    _raw_binding_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        source: MmcifNonpolyCovalentStructConnTopologyIngestResult,
        write_result: MmcifNonpolyCovalentStructConnTopologyWriteResult,
        reparsed: MmcifNonpolyCovalentStructConnTopologyIngestResult,
        second: MmcifNonpolyCovalentStructConnTopologyWriteResult,
        report: MmcifNonpolyCovalentStructConnTopologyRoundTripReport,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "MmcifNonpolyCovalentStructConnTopologyRoundTripResult is factory-only"
            )
        _validate_report(report)
        binding = _aggregate_binding_document(
            source, write_result, reparsed, second, report
        )
        object.__setattr__(self, "_source_ingest", source)
        object.__setattr__(self, "_write_result", write_result)
        object.__setattr__(self, "_reparsed_ingest", reparsed)
        object.__setattr__(self, "_reemitted_write_result", second)
        object.__setattr__(self, "_report", report)
        object.__setattr__(self, "_raw_binding_bytes", _canonical_json_bytes(binding))
        access = _canonical_json_bytes(_aggregate_access_document(self))
        object.__setattr__(self, "_access_binding_bytes", access)
        _register_factory_artifact_anchor(self, access)

    @property
    def source_ingest(self) -> MmcifNonpolyCovalentStructConnTopologyIngestResult:
        _validate_aggregate(self)
        return self._source_ingest

    @property
    def write_result(self) -> MmcifNonpolyCovalentStructConnTopologyWriteResult:
        _validate_aggregate(self)
        return self._write_result

    @property
    def reparsed_ingest(
        self,
    ) -> MmcifNonpolyCovalentStructConnTopologyIngestResult:
        _validate_aggregate(self)
        return self._reparsed_ingest

    @property
    def reemitted_write_result(
        self,
    ) -> MmcifNonpolyCovalentStructConnTopologyWriteResult:
        _validate_aggregate(self)
        return self._reemitted_write_result

    @property
    def report(self) -> MmcifNonpolyCovalentStructConnTopologyRoundTripReport:
        _validate_aggregate(self)
        return self._report

    def to_dict(self) -> dict[str, Any]:
        _validate_aggregate(self)
        return {
            "source_ingest": self._source_ingest.to_dict(),
            "write_result": self._write_result.to_dict(),
            "reparsed_ingest": self._reparsed_ingest.to_dict(),
            "reemitted_write_result": self._reemitted_write_result.to_dict(),
            "report": self._report.to_dict(),
            **_BOUNDED_TRUE_FIELDS,
            **_authority_false_document(),
        }


def _validate_aggregate(
    value: MmcifNonpolyCovalentStructConnTopologyRoundTripResult,
) -> None:
    if type(value) is not MmcifNonpolyCovalentStructConnTopologyRoundTripResult:
        raise TypeError("an exact covalent struct_conn round-trip result is required")
    try:
        _validate_factory_artifact_anchor(
            value, _canonical_json_bytes(_aggregate_access_document(value))
        )
        _validate_report(value._report)
        binding = _aggregate_binding_document(
            value._source_ingest,
            value._write_result,
            value._reparsed_ingest,
            value._reemitted_write_result,
            value._report,
        )
    except Exception:
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        ) from None
    if value._raw_binding_bytes != _canonical_json_bytes(binding):
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "crosswired_round_trip_artifacts", "round-trip artifacts are crosswired"
        )


def round_trip_mmcif_nonpoly_covalent_struct_conn_topology_source(
    data: bytes, *, source_id: str = ""
) -> MmcifNonpolyCovalentStructConnTopologyRoundTripResult:
    source = parse_mmcif_nonpoly_covalent_struct_conn_topology(
        data, source_id=source_id
    )
    write_result = write_mmcif_nonpoly_covalent_struct_conn_topology(source)
    reparsed = parse_mmcif_nonpoly_covalent_struct_conn_topology(
        write_result.payload, source_id=source_id
    )
    second = write_mmcif_nonpoly_covalent_struct_conn_topology(reparsed)
    document = _report_document(source, write_result, reparsed, second)
    if (
        document["source_reported_covalent_struct_conn_round_trip_preserved"]
        is not True
    ):
        raise MmcifNonpolyCovalentStructConnTopologyError(
            "round_trip_mismatch", "covalent struct_conn topology did not round trip"
        )
    report = MmcifNonpolyCovalentStructConnTopologyRoundTripReport(
        source,
        write_result,
        reparsed,
        second,
        document,
        _factory_token=_FACTORY_TOKEN,
    )
    return MmcifNonpolyCovalentStructConnTopologyRoundTripResult(
        source,
        write_result,
        reparsed,
        second,
        report,
        _factory_token=_FACTORY_TOKEN,
    )


__all__ = [
    "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_MATERIALIZED_BONDS",
    "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_ROWS",
    "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_INPUT_BYTES",
    "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_OUTPUT_BYTES",
    "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_OUTPUT_LINE_CHARS",
    "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROJECTION_BYTES",
    "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_SOURCE_ID_BYTES",
    "MAX_MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_TOKEN_CHARS",
    "MMCIF_NONPOLY_COVALENT_STRUCT_CONN_HEADERS",
    "MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ENVELOPE_VERSION",
    "MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_NAME",
    "MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_PEDIGREE_ID",
    "MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PARSER_VERSION",
    "MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROFILE_ID",
    "MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_ROUND_TRIP_REPORT_SCHEMA_ID",
    "MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_STATE_SCHEMA_ID",
    "MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_WRITER_VERSION",
    "MMCIF_NONPOLY_COVALENT_STRUCT_CONN_TOPOLOGY_WRITE_RECEIPT_SCHEMA_ID",
    "MmcifNonpolyCovalentStructConnRow",
    "MmcifNonpolyCovalentStructConnTopologyError",
    "MmcifNonpolyCovalentStructConnTopologyIngestResult",
    "MmcifNonpolyCovalentStructConnTopologyRoundTripReport",
    "MmcifNonpolyCovalentStructConnTopologyRoundTripResult",
    "MmcifNonpolyCovalentStructConnTopologyWriteReceipt",
    "MmcifNonpolyCovalentStructConnTopologyWriteResult",
    "emit_mmcif_nonpoly_covalent_struct_conn_topology",
    "mmcif_nonpoly_covalent_struct_conn_topology_projection_sha256",
    "mmcif_nonpoly_covalent_struct_conn_topology_record_state_sha256",
    "mmcif_nonpoly_covalent_struct_conn_topology_state_sha256",
    "parse_mmcif_nonpoly_covalent_struct_conn_topology",
    "round_trip_mmcif_nonpoly_covalent_struct_conn_topology_source",
    "serialize_mmcif_nonpoly_covalent_struct_conn_topology",
    "write_mmcif_nonpoly_covalent_struct_conn_topology",
]
