"""Opt-in preservation envelope for simple SDF V2000 SD data fields.

This module deliberately sits beside, rather than inside, the strict
``sdf_v2000`` parser.  The existing parser remains the sole owner of molecular
state.  Named SD data fields are preserved as ordered, opaque printable-ASCII
lines and are never copied into :class:`AllAtomSystem` metadata or interpreted
as chemistry, paths, commands, URLs, authentication, or scientific authority.

The envelope binds the complete input record, a normalized delimiter-terminated
base-molecule parser input, the canonical base-writer output, a detached
serialized base-system snapshot, parser coverage, and two versioned
projections.  Its hashes are tamper evidence only.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
import hashlib
import json
import re
from typing import Any, Mapping

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID

from .sdf_v2000 import (
    SDF_V2000_PARSER_VERSION,
    SdfV2000Coverage,
    SdfV2000IngestResult,
    SdfV2000ParseError,
    parse_sdf_v2000,
)
from .sdf_v2000_writer import (
    SDF_V2000_REPRESENTABLE_STATE_SCHEMA_ID,
    SDF_V2000_WRITER_VERSION,
    SdfV2000WriteError,
    sdf_v2000_representable_state_sha256,
    write_sdf_v2000,
)
from .serialization import (
    canonical_all_atom_snapshot_digest,
    deserialize_all_atom_system,
    serialize_all_atom_system,
)
from .topology import CANONICAL_TOPOLOGY_SCHEMA_ID, canonical_topology_sha256


SDF_V2000_DATA_FIELD_ENVELOPE_VERSION = "1.0.0"
SDF_V2000_DATA_FIELD_PARSER_VERSION = "1.0.0"
SDF_V2000_DATA_FIELD_WRITER_VERSION = "1.0.0"
SDF_V2000_DATA_FIELD_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular.sdf_v2000_data_fields"
)
SDF_V2000_DATA_FIELD_PROFILE_ID = (
    "strict_sdf_v2000_named_opaque_data_field_envelope/1.0.0"
)
SDF_V2000_DATA_FIELD_PROJECTION_SCHEMA_ID = (
    "betelgeuze.sdf_v2000_data_field_projection/1.0.0"
)
SDF_V2000_DATA_FIELD_RECORD_STATE_SCHEMA_ID = (
    "betelgeuze.sdf_v2000_data_field_record_representable_state/1.0.0"
)
SDF_V2000_DATA_FIELD_WRITE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.sdf_v2000_data_field_write_receipt/1.0.0"
)
SDF_V2000_DATA_FIELD_ROUND_TRIP_REPORT_SCHEMA_ID = (
    "betelgeuze.sdf_v2000_data_field_round_trip_report/1.0.0"
)

MAX_SDF_V2000_DATA_FIELDS = 256
MAX_SDF_V2000_DATA_FIELD_NAME_CHARS = 128
MAX_SDF_V2000_DATA_FIELD_VALUE_LINE_CHARS = 200
MAX_SDF_V2000_DATA_FIELD_VALUE_LINES = 64
MAX_SDF_V2000_DATA_FIELD_TOTAL_VALUE_LINES = 2_048
MAX_SDF_V2000_DATA_FIELD_PAYLOAD_BYTES = 384 * 1024

_MAX_SDF_INPUT_BYTES = 2 * 1024 * 1024
_MAX_SDF_LINE_COUNT = 4_096
_MAX_SDF_LINE_CHARS = 256
_FIELD_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
_FIELD_HEADER_RE = re.compile(r"^>  <([A-Za-z0-9_][A-Za-z0-9_.-]{0,127})>$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACT_FACTORY_TOKEN = object()

_NON_PROMOTION_BLOCKERS = (
    "opaque_data_field_values_are_not_interpreted",
    "data_field_names_grant_no_path_command_url_or_authority_semantics",
    "sha256_bindings_are_tamper_evidence_not_source_authentication",
    "only_simple_named_sdf_v2000_data_fields_are_preserved",
    "registry_qualified_and_noncanonical_data_headers_are_unsupported",
    "general_sdf_round_trip_evidence_not_established",
    "all_format_round_trip_evidence_not_established",
    "preparation_parameterability_simulation_runtime_and_claim_authority_not_granted",
)


class SdfV2000DataFieldError(ValueError):
    """Stable fail-closed error that never includes an opaque field value."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        line_number: int | None = None,
        location: str | None = None,
    ) -> None:
        self.code = str(code)
        self.line_number = None if line_number is None else int(line_number)
        self.location = None if location is None else str(location)
        self.detail = str(message)
        if self.line_number is not None:
            suffix = f" at line {self.line_number}"
        elif self.location is not None:
            suffix = f" at {self.location}"
        else:
            suffix = ""
        super().__init__(f"{self.code}{suffix}: {self.detail}")


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


def _require_sha256(value: str, *, field_name: str) -> None:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise TypeError(f"{field_name} must be a lowercase SHA-256")


def _require_nonnegative_int(value: int, *, field_name: str) -> None:
    if type(value) is not int or value < 0:
        raise TypeError(f"{field_name} must be a nonnegative integer")


@dataclass(frozen=True, slots=True, init=False)
class SdfV2000DataField:
    """One ordered opaque SD data item; values are intentionally repr-hidden."""

    name: str
    value_lines: tuple[str, ...] = dataclass_field(repr=False)

    def __init__(
        self,
        *,
        name: str,
        value_lines: tuple[str, ...],
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SdfV2000DataField is factory-only")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "value_lines", value_lines)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self.name) is not str or _FIELD_NAME_RE.fullmatch(self.name) is None:
            raise ValueError(
                "data field name is outside the canonical named-field subset"
            )
        if type(self.value_lines) is not tuple:
            raise TypeError("data field value_lines must be a tuple")
        if len(self.value_lines) > MAX_SDF_V2000_DATA_FIELD_VALUE_LINES:
            raise ValueError("data field exceeds the per-field value-line limit")
        for value in self.value_lines:
            if type(value) is not str:
                raise TypeError("data field value lines must be strings")
            if len(value) > MAX_SDF_V2000_DATA_FIELD_VALUE_LINE_CHARS:
                raise ValueError("data field value line exceeds the character limit")
            if not all(" " <= char <= "~" for char in value):
                raise ValueError("data field values must be printable ASCII")


def _field_projection_document(
    fields: tuple[SdfV2000DataField, ...],
) -> dict[str, Any]:
    return {
        "schema_id": SDF_V2000_DATA_FIELD_PROJECTION_SCHEMA_ID,
        "envelope_version": SDF_V2000_DATA_FIELD_ENVELOPE_VERSION,
        "parser_version": SDF_V2000_DATA_FIELD_PARSER_VERSION,
        "profile_id": SDF_V2000_DATA_FIELD_PROFILE_ID,
        "parser_name": SDF_V2000_DATA_FIELD_PARSER_NAME,
        "field_count": len(fields),
        "fields": [
            {
                "ordinal": ordinal,
                "name": item.name,
                "value_lines": list(item.value_lines),
            }
            for ordinal, item in enumerate(fields)
        ],
        "ordering": "source_order_with_duplicate_names_preserved",
        "value_semantics": "opaque_printable_ascii_lines",
        "name_semantics": "opaque_case_preserved_identifier",
    }


def _projection_sha256(fields: tuple[SdfV2000DataField, ...]) -> str:
    return _sha256_document(_field_projection_document(fields))


def _record_state_document(
    *,
    base_representable_state_sha256: str,
    data_field_projection_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_id": SDF_V2000_DATA_FIELD_RECORD_STATE_SCHEMA_ID,
        "envelope_version": SDF_V2000_DATA_FIELD_ENVELOPE_VERSION,
        "parser_version": SDF_V2000_DATA_FIELD_PARSER_VERSION,
        "writer_version": SDF_V2000_DATA_FIELD_WRITER_VERSION,
        "profile_id": SDF_V2000_DATA_FIELD_PROFILE_ID,
        "base_parser_version": SDF_V2000_PARSER_VERSION,
        "base_writer_version": SDF_V2000_WRITER_VERSION,
        "base_representable_state_schema_id": (SDF_V2000_REPRESENTABLE_STATE_SCHEMA_ID),
        "base_representable_state_sha256": base_representable_state_sha256,
        "data_field_projection_schema_id": (SDF_V2000_DATA_FIELD_PROJECTION_SCHEMA_ID),
        "data_field_projection_sha256": data_field_projection_sha256,
    }


def _record_state_sha256(
    *,
    base_representable_state_sha256: str,
    data_field_projection_sha256: str,
) -> str:
    return _sha256_document(
        _record_state_document(
            base_representable_state_sha256=base_representable_state_sha256,
            data_field_projection_sha256=data_field_projection_sha256,
        )
    )


def _canonical_data_payload(fields: tuple[SdfV2000DataField, ...]) -> bytes:
    if not fields:
        return b""
    lines: list[str] = []
    for item in fields:
        lines.append(f">  <{item.name}>")
        lines.extend(item.value_lines)
        lines.append("")
    return ("\n".join(lines) + "\n").encode("ascii")


def _field_counts(
    fields: tuple[SdfV2000DataField, ...],
) -> tuple[int, int, int]:
    value_line_count = sum(len(item.value_lines) for item in fields)
    return (
        len(fields),
        value_line_count,
        len(_canonical_data_payload(fields)),
    )


def _make_field(name: str, value_lines: list[str]) -> SdfV2000DataField:
    return SdfV2000DataField(
        name=name,
        value_lines=tuple(value_lines),
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )


def _decode_source_lines(data: bytes) -> list[str]:
    if type(data) is not bytes:
        raise TypeError("SDF V2000 data-field input must be bytes")
    if not data:
        raise SdfV2000DataFieldError("empty_input", "SDF input is empty")
    if len(data) > _MAX_SDF_INPUT_BYTES:
        raise SdfV2000DataFieldError(
            "input_too_large", "SDF input exceeds the inherited byte safety limit"
        )
    if not data.isascii():
        raise SdfV2000DataFieldError("invalid_ascii", "SDF input must be ASCII")
    text = data.decode("ascii")
    if "\x00" in text:
        raise SdfV2000DataFieldError(
            "invalid_data_field_text", "NUL bytes are not allowed"
        )
    if any(char not in "\r\n" and not (" " <= char <= "~") for char in text):
        raise SdfV2000DataFieldError(
            "invalid_data_field_text",
            "SDF input may contain only printable ASCII and line endings",
        )
    normalized = text.replace("\r\n", "\n")
    if "\r" in normalized:
        raise SdfV2000DataFieldError(
            "invalid_data_field_text", "bare carriage returns are not supported"
        )
    lines = normalized.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) > _MAX_SDF_LINE_COUNT:
        raise SdfV2000DataFieldError(
            "too_many_lines", "SDF input exceeds the inherited line safety limit"
        )
    for line_number, line in enumerate(lines, start=1):
        if len(line) > _MAX_SDF_LINE_CHARS:
            raise SdfV2000DataFieldError(
                "line_too_long",
                "SDF line exceeds the inherited character limit",
                line_number=line_number,
            )
    return lines


def _find_m_end(lines: list[str]) -> int:
    if len(lines) < 5:
        raise SdfV2000DataFieldError(
            "truncated_record", "SDF base molecule block is truncated"
        )
    for index in range(4, len(lines)):
        if lines[index] == "M  END":
            return index
    raise SdfV2000DataFieldError(
        "missing_m_end", "SDF base molecule block requires M  END"
    )


def _header_name(line: str, *, line_number: int) -> str:
    match = _FIELD_HEADER_RE.fullmatch(line)
    if match is not None:
        return match.group(1)
    if line.startswith(">  <") and line.endswith(">"):
        candidate = line[4:-1]
        if len(candidate) > MAX_SDF_V2000_DATA_FIELD_NAME_CHARS:
            raise SdfV2000DataFieldError(
                "data_field_name_too_long",
                "data-field name exceeds the character limit",
                line_number=line_number,
            )
    raise SdfV2000DataFieldError(
        "invalid_data_field_header",
        "expected the canonical >  <FIELD_NAME> header form",
        line_number=line_number,
    )


def _parse_data_fields(
    lines: list[str],
    *,
    start_index: int,
) -> tuple[SdfV2000DataField, ...]:
    cursor = start_index
    while cursor < len(lines) and lines[cursor] == "":
        cursor += 1
    if cursor == len(lines):
        return ()
    if lines[cursor] == "$$$$":
        if any(line != "" for line in lines[cursor + 1 :]):
            raise SdfV2000DataFieldError(
                "multiple_records",
                "content after the first SDF delimiter is not allowed",
                line_number=cursor + 2,
            )
        return ()
    if cursor != start_index:
        raise SdfV2000DataFieldError(
            "blank_before_data_field",
            "blank lines may not precede a data-field header",
            line_number=start_index + 1,
        )

    fields: list[SdfV2000DataField] = []
    total_value_lines = 0
    while True:
        line_number = cursor + 1
        name = _header_name(lines[cursor], line_number=line_number)
        if len(fields) >= MAX_SDF_V2000_DATA_FIELDS:
            raise SdfV2000DataFieldError(
                "too_many_data_fields",
                "record exceeds the data-field count limit",
                line_number=line_number,
            )
        cursor += 1
        value_lines: list[str] = []
        while cursor < len(lines) and lines[cursor] != "":
            value_line_number = cursor + 1
            if lines[cursor] == "$$$$":
                raise SdfV2000DataFieldError(
                    "missing_data_field_terminator",
                    "data field requires a blank terminator before the delimiter",
                    line_number=value_line_number,
                )
            if _FIELD_HEADER_RE.fullmatch(lines[cursor]) is not None:
                raise SdfV2000DataFieldError(
                    "nested_data_field_header",
                    "data-field header encountered before the prior blank terminator",
                    line_number=value_line_number,
                )
            if len(lines[cursor]) > MAX_SDF_V2000_DATA_FIELD_VALUE_LINE_CHARS:
                raise SdfV2000DataFieldError(
                    "data_field_value_line_too_long",
                    "opaque value line exceeds the data-field character limit",
                    line_number=value_line_number,
                )
            if len(value_lines) >= MAX_SDF_V2000_DATA_FIELD_VALUE_LINES:
                raise SdfV2000DataFieldError(
                    "too_many_data_field_value_lines",
                    "data field exceeds the per-field value-line limit",
                    line_number=value_line_number,
                )
            if total_value_lines >= MAX_SDF_V2000_DATA_FIELD_TOTAL_VALUE_LINES:
                raise SdfV2000DataFieldError(
                    "too_many_total_data_field_value_lines",
                    "record exceeds the total data-field value-line limit",
                    line_number=value_line_number,
                )
            value_lines.append(lines[cursor])
            total_value_lines += 1
            cursor += 1
        if cursor == len(lines):
            raise SdfV2000DataFieldError(
                "missing_data_field_terminator",
                "data field requires a blank terminator",
                line_number=len(lines),
            )
        fields.append(_make_field(name, value_lines))
        cursor += 1
        if len(_canonical_data_payload(tuple(fields))) > (
            MAX_SDF_V2000_DATA_FIELD_PAYLOAD_BYTES
        ):
            raise SdfV2000DataFieldError(
                "data_field_payload_too_large",
                "data-field payload exceeds its byte safety limit",
            )
        if cursor == len(lines):
            raise SdfV2000DataFieldError(
                "missing_data_field_delimiter",
                "records with data fields require an SDF delimiter",
            )
        if lines[cursor] == "$$$$":
            if any(line != "" for line in lines[cursor + 1 :]):
                next_content = next(
                    index
                    for index in range(cursor + 1, len(lines))
                    if lines[index] != ""
                )
                raise SdfV2000DataFieldError(
                    "multiple_records",
                    "content after the first SDF delimiter is not allowed",
                    line_number=next_content + 1,
                )
            return tuple(fields)
        if lines[cursor] == "":
            raise SdfV2000DataFieldError(
                "extra_blank_between_data_fields",
                "exactly one blank terminator is required between data fields",
                line_number=cursor + 1,
            )
        if _FIELD_HEADER_RE.fullmatch(lines[cursor]) is None:
            raise SdfV2000DataFieldError(
                "invalid_data_field_header",
                "expected another canonical data-field header or the delimiter",
                line_number=cursor + 1,
            )


def _parse_source_components(
    data: bytes,
    *,
    source_id: str,
) -> tuple[bytes, SdfV2000IngestResult, tuple[SdfV2000DataField, ...]]:
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    lines = _decode_source_lines(data)
    m_end_index = _find_m_end(lines)
    fields = _parse_data_fields(lines, start_index=m_end_index + 1)
    base_source = ("\n".join([*lines[: m_end_index + 1], "$$$$"]) + "\n").encode(
        "ascii"
    )
    try:
        base_ingest = parse_sdf_v2000(base_source, source_id=source_id)
    except SdfV2000ParseError as exc:
        raise SdfV2000DataFieldError(
            "unsupported_base_mol_block",
            f"strict base SDF parser rejected the molecule block ({exc.code})",
            line_number=exc.line_number,
        ) from exc
    try:
        write_sdf_v2000(base_ingest.system)
    except SdfV2000WriteError as exc:
        raise SdfV2000DataFieldError(
            "unwritable_base_mol_block",
            f"strict base SDF writer rejected parser-owned state ({exc.code})",
        ) from exc
    return base_source, base_ingest, fields


@dataclass(frozen=True, slots=True, init=False)
class SdfV2000DataFieldIngestResult:
    """Factory-owned immutable binding for a base molecule and opaque fields."""

    _source_bytes: bytes = dataclass_field(repr=False)
    _base_source_bytes: bytes = dataclass_field(repr=False)
    _base_system_snapshot: bytes = dataclass_field(repr=False)
    _coverage: SdfV2000Coverage = dataclass_field(repr=False)
    _data_fields: tuple[SdfV2000DataField, ...] = dataclass_field(repr=False)
    full_source_sha256: str
    base_mol_block_source_sha256: str
    canonical_base_mol_block_sha256: str
    base_system_snapshot_sha256: str
    base_topology_sha256: str
    base_representable_state_sha256: str
    data_field_projection_sha256: str
    record_representable_state_sha256: str
    full_source_byte_count: int
    data_field_count: int
    data_field_value_line_count: int
    data_field_payload_byte_count: int

    def __init__(
        self,
        *,
        source_bytes: bytes,
        base_source_bytes: bytes,
        base_ingest: SdfV2000IngestResult,
        data_fields: tuple[SdfV2000DataField, ...],
        full_source_sha256: str,
        base_mol_block_source_sha256: str,
        canonical_base_mol_block_sha256: str,
        base_system_snapshot_sha256: str,
        base_topology_sha256: str,
        base_representable_state_sha256: str,
        data_field_projection_sha256: str,
        record_representable_state_sha256: str,
        full_source_byte_count: int,
        data_field_count: int,
        data_field_value_line_count: int,
        data_field_payload_byte_count: int,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SdfV2000DataFieldIngestResult is factory-only")
        if type(base_ingest) is not SdfV2000IngestResult:
            raise TypeError("base_ingest must be an SdfV2000IngestResult")
        values = {
            "_source_bytes": source_bytes,
            "_base_source_bytes": base_source_bytes,
            "_base_system_snapshot": serialize_all_atom_system(base_ingest.system),
            "_coverage": base_ingest.coverage,
            "_data_fields": data_fields,
            "full_source_sha256": full_source_sha256,
            "base_mol_block_source_sha256": base_mol_block_source_sha256,
            "canonical_base_mol_block_sha256": canonical_base_mol_block_sha256,
            "base_system_snapshot_sha256": base_system_snapshot_sha256,
            "base_topology_sha256": base_topology_sha256,
            "base_representable_state_sha256": base_representable_state_sha256,
            "data_field_projection_sha256": data_field_projection_sha256,
            "record_representable_state_sha256": record_representable_state_sha256,
            "full_source_byte_count": full_source_byte_count,
            "data_field_count": data_field_count,
            "data_field_value_line_count": data_field_value_line_count,
            "data_field_payload_byte_count": data_field_payload_byte_count,
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)
        self.__post_init__()

    @property
    def system(self):
        """Return a detached copy of the base parser-owned molecular system."""

        return deserialize_all_atom_system(self._base_system_snapshot)

    @property
    def coverage(self) -> SdfV2000Coverage:
        return self._coverage

    @property
    def data_fields(self) -> tuple[SdfV2000DataField, ...]:
        return self._data_fields

    @property
    def base_ingest(self) -> SdfV2000IngestResult:
        return SdfV2000IngestResult(system=self.system, coverage=self.coverage)

    def __post_init__(self) -> None:
        if type(self._source_bytes) is not bytes:
            raise TypeError("source snapshot must be exact bytes")
        if type(self._base_source_bytes) is not bytes:
            raise TypeError("base source snapshot must be exact bytes")
        if type(self._base_system_snapshot) is not bytes:
            raise TypeError("base system snapshot must be exact bytes")
        if type(self._coverage) is not SdfV2000Coverage:
            raise TypeError("coverage must be SdfV2000Coverage")
        if type(self._data_fields) is not tuple or any(
            type(item) is not SdfV2000DataField for item in self._data_fields
        ):
            raise TypeError("data_fields must be a tuple of SdfV2000DataField")
        for field_name in (
            "full_source_sha256",
            "base_mol_block_source_sha256",
            "canonical_base_mol_block_sha256",
            "base_system_snapshot_sha256",
            "base_topology_sha256",
            "base_representable_state_sha256",
            "data_field_projection_sha256",
            "record_representable_state_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        for field_name in (
            "full_source_byte_count",
            "data_field_count",
            "data_field_value_line_count",
            "data_field_payload_byte_count",
        ):
            _require_nonnegative_int(getattr(self, field_name), field_name=field_name)
        if len(self._source_bytes) != self.full_source_byte_count:
            raise ValueError("full source byte count binding is stale")
        if hashlib.sha256(self._source_bytes).hexdigest() != self.full_source_sha256:
            raise ValueError("full source SHA-256 binding is stale")
        if hashlib.sha256(self._base_source_bytes).hexdigest() != (
            self.base_mol_block_source_sha256
        ):
            raise ValueError("base molecule source SHA-256 binding is stale")
        counts = _field_counts(self._data_fields)
        if counts != (
            self.data_field_count,
            self.data_field_value_line_count,
            self.data_field_payload_byte_count,
        ):
            raise ValueError("data field count binding is stale")

    def to_dict(self) -> dict[str, Any]:
        """Return a value-free audit summary of the envelope."""

        return {
            "profile_id": SDF_V2000_DATA_FIELD_PROFILE_ID,
            "parser_name": SDF_V2000_DATA_FIELD_PARSER_NAME,
            "envelope_version": SDF_V2000_DATA_FIELD_ENVELOPE_VERSION,
            "parser_version": SDF_V2000_DATA_FIELD_PARSER_VERSION,
            "writer_version": SDF_V2000_DATA_FIELD_WRITER_VERSION,
            "base_parser_version": SDF_V2000_PARSER_VERSION,
            "base_writer_version": SDF_V2000_WRITER_VERSION,
            "full_source_sha256": self.full_source_sha256,
            "base_mol_block_source_sha256": self.base_mol_block_source_sha256,
            "canonical_base_mol_block_sha256": self.canonical_base_mol_block_sha256,
            "base_system_snapshot_sha256": self.base_system_snapshot_sha256,
            "base_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
            "base_topology_sha256": self.base_topology_sha256,
            "data_field_projection_schema_id": (
                SDF_V2000_DATA_FIELD_PROJECTION_SCHEMA_ID
            ),
            "data_field_projection_sha256": self.data_field_projection_sha256,
            "record_representable_state_schema_id": (
                SDF_V2000_DATA_FIELD_RECORD_STATE_SCHEMA_ID
            ),
            "record_representable_state_sha256": (
                self.record_representable_state_sha256
            ),
            "full_source_byte_count": self.full_source_byte_count,
            "data_field_count": self.data_field_count,
            "data_field_value_line_count": self.data_field_value_line_count,
            "data_field_payload_byte_count": self.data_field_payload_byte_count,
            "named_field_opaque_projection_preserved": True,
            "data_field_semantics_interpreted": False,
            "chemistry_interpreted": False,
            "path_command_url_or_authority_semantics_granted": False,
            "source_authentication_status": "not_authenticated",
            "source_authenticated": False,
            "preparation_ready": False,
            "parameterability_assessed": False,
            "simulation_ready": False,
            "runtime_eligible": False,
            "claim_safe": False,
            "general_sdf_round_trip_evidence_ready": False,
            "all_format_round_trip_evidence_ready": False,
            "blockers": list(_NON_PROMOTION_BLOCKERS),
        }


def _build_ingest(
    *,
    source_bytes: bytes,
    base_source: bytes,
    base_ingest: SdfV2000IngestResult,
    fields: tuple[SdfV2000DataField, ...],
) -> SdfV2000DataFieldIngestResult:
    base_write = write_sdf_v2000(base_ingest.system)
    base_snapshot_sha256 = canonical_all_atom_snapshot_digest(base_ingest.system)
    base_topology_sha256 = canonical_topology_sha256(base_ingest.system)
    base_state_sha256 = sdf_v2000_representable_state_sha256(base_ingest.system)
    projection_sha256 = _projection_sha256(fields)
    record_state_sha256 = _record_state_sha256(
        base_representable_state_sha256=base_state_sha256,
        data_field_projection_sha256=projection_sha256,
    )
    field_count, value_line_count, data_payload_bytes = _field_counts(fields)
    return SdfV2000DataFieldIngestResult(
        source_bytes=source_bytes,
        base_source_bytes=base_source,
        base_ingest=base_ingest,
        data_fields=fields,
        full_source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        base_mol_block_source_sha256=hashlib.sha256(base_source).hexdigest(),
        canonical_base_mol_block_sha256=hashlib.sha256(base_write.payload).hexdigest(),
        base_system_snapshot_sha256=base_snapshot_sha256,
        base_topology_sha256=base_topology_sha256,
        base_representable_state_sha256=base_state_sha256,
        data_field_projection_sha256=projection_sha256,
        record_representable_state_sha256=record_state_sha256,
        full_source_byte_count=len(source_bytes),
        data_field_count=field_count,
        data_field_value_line_count=value_line_count,
        data_field_payload_byte_count=data_payload_bytes,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )


def parse_sdf_v2000_data_fields(
    data: bytes,
    *,
    source_id: str = "",
) -> SdfV2000DataFieldIngestResult:
    """Parse a base molecule plus the opt-in simple named-field envelope."""

    base_source, base_ingest, fields = _parse_source_components(
        data, source_id=source_id
    )
    return _build_ingest(
        source_bytes=data,
        base_source=base_source,
        base_ingest=base_ingest,
        fields=fields,
    )


def _validate_ingest(
    ingest: SdfV2000DataFieldIngestResult,
) -> tuple[SdfV2000IngestResult, bytes]:
    if type(ingest) is not SdfV2000DataFieldIngestResult:
        raise TypeError("ingest must be an SdfV2000DataFieldIngestResult")
    try:
        ingest.__post_init__()
        system = ingest.system
    except Exception as exc:
        if isinstance(exc, SdfV2000DataFieldError):
            raise
        raise SdfV2000DataFieldError(
            "stale_envelope", "envelope primitive bindings are not self-consistent"
        ) from exc
    if system.schema_id != ALL_ATOM_SCHEMA_ID:
        raise SdfV2000DataFieldError(
            "stale_base_snapshot", "base system schema binding is stale"
        )
    if canonical_all_atom_snapshot_digest(system) != ingest.base_system_snapshot_sha256:
        raise SdfV2000DataFieldError(
            "stale_base_snapshot", "base system snapshot binding is stale"
        )
    if canonical_topology_sha256(system) != ingest.base_topology_sha256:
        raise SdfV2000DataFieldError(
            "stale_base_topology", "base topology binding is stale"
        )
    if ingest.coverage.to_dict() != system.provenance.metadata.get("coverage"):
        raise SdfV2000DataFieldError(
            "stale_coverage", "base parser coverage binding is stale"
        )
    if system.provenance.source_sha256 != ingest.base_mol_block_source_sha256:
        raise SdfV2000DataFieldError(
            "stale_base_source", "base parser source binding is stale"
        )
    try:
        base_write = write_sdf_v2000(system)
        base_state_sha256 = sdf_v2000_representable_state_sha256(system)
    except SdfV2000WriteError as exc:
        raise SdfV2000DataFieldError(
            "unwritable_base_snapshot",
            f"strict base writer rejected the stored parser state ({exc.code})",
        ) from exc
    if base_state_sha256 != ingest.base_representable_state_sha256:
        raise SdfV2000DataFieldError(
            "stale_base_projection", "base representable-state binding is stale"
        )
    if hashlib.sha256(base_write.payload).hexdigest() != (
        ingest.canonical_base_mol_block_sha256
    ):
        raise SdfV2000DataFieldError(
            "stale_canonical_base_source",
            "canonical base molecule source binding is stale",
        )
    projection_sha256 = _projection_sha256(ingest.data_fields)
    if projection_sha256 != ingest.data_field_projection_sha256:
        raise SdfV2000DataFieldError(
            "stale_data_field_projection", "data-field projection binding is stale"
        )
    record_state_sha256 = _record_state_sha256(
        base_representable_state_sha256=base_state_sha256,
        data_field_projection_sha256=projection_sha256,
    )
    if record_state_sha256 != ingest.record_representable_state_sha256:
        raise SdfV2000DataFieldError(
            "stale_record_state", "record representable-state binding is stale"
        )

    reparsed_base_source, reparsed_base, reparsed_fields = _parse_source_components(
        ingest._source_bytes,
        source_id=system.provenance.source_id,
    )
    if reparsed_base_source != ingest._base_source_bytes:
        raise SdfV2000DataFieldError(
            "crosswired_base_source", "full source and base source are cross-wired"
        )
    if reparsed_fields != ingest.data_fields:
        raise SdfV2000DataFieldError(
            "crosswired_data_fields",
            "full source and data-field projection are cross-wired",
        )
    if serialize_all_atom_system(reparsed_base.system) != ingest._base_system_snapshot:
        raise SdfV2000DataFieldError(
            "crosswired_base_snapshot", "full source and base system are cross-wired"
        )
    if reparsed_base.coverage != ingest.coverage:
        raise SdfV2000DataFieldError(
            "crosswired_coverage", "full source and parser coverage are cross-wired"
        )
    return SdfV2000IngestResult(
        system=system, coverage=ingest.coverage
    ), base_write.payload


def sdf_v2000_data_field_projection_sha256(
    ingest: SdfV2000DataFieldIngestResult,
) -> str:
    """Return the checked ordered opaque-field projection digest."""

    _validate_ingest(ingest)
    return ingest.data_field_projection_sha256


def sdf_v2000_data_field_record_state_sha256(
    ingest: SdfV2000DataFieldIngestResult,
) -> str:
    """Return the checked base-molecule plus data-field projection digest."""

    _validate_ingest(ingest)
    return ingest.record_representable_state_sha256


@dataclass(frozen=True, slots=True, init=False)
class SdfV2000DataFieldWriteReceipt:
    input_full_source_sha256: str
    input_base_mol_block_source_sha256: str
    input_canonical_base_mol_block_sha256: str
    input_base_system_snapshot_sha256: str
    input_base_topology_sha256: str
    input_base_representable_state_sha256: str
    input_data_field_projection_sha256: str
    input_record_representable_state_sha256: str
    base_writer_receipt_sha256: str
    output_source_sha256: str
    output_byte_count: int
    data_field_count: int
    data_field_value_line_count: int
    data_field_payload_byte_count: int

    def __init__(self, *, _factory_token: object | None = None, **values: Any) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SdfV2000DataFieldWriteReceipt is factory-only")
        expected = tuple(self.__annotations__)
        if frozenset(values) != frozenset(expected):
            raise TypeError("write receipt fields do not match the schema")
        for name in expected:
            object.__setattr__(self, name, values[name])
        self.__post_init__()

    def __post_init__(self) -> None:
        for field_name in (
            "input_full_source_sha256",
            "input_base_mol_block_source_sha256",
            "input_canonical_base_mol_block_sha256",
            "input_base_system_snapshot_sha256",
            "input_base_topology_sha256",
            "input_base_representable_state_sha256",
            "input_data_field_projection_sha256",
            "input_record_representable_state_sha256",
            "base_writer_receipt_sha256",
            "output_source_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        for field_name in (
            "output_byte_count",
            "data_field_count",
            "data_field_value_line_count",
            "data_field_payload_byte_count",
        ):
            _require_nonnegative_int(getattr(self, field_name), field_name=field_name)

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": SDF_V2000_DATA_FIELD_WRITE_RECEIPT_SCHEMA_ID,
            "envelope_version": SDF_V2000_DATA_FIELD_ENVELOPE_VERSION,
            "parser_version": SDF_V2000_DATA_FIELD_PARSER_VERSION,
            "writer_version": SDF_V2000_DATA_FIELD_WRITER_VERSION,
            "profile_id": SDF_V2000_DATA_FIELD_PROFILE_ID,
            "parser_name": SDF_V2000_DATA_FIELD_PARSER_NAME,
            "base_parser_version": SDF_V2000_PARSER_VERSION,
            "base_writer_version": SDF_V2000_WRITER_VERSION,
            "input_system_schema_id": ALL_ATOM_SCHEMA_ID,
            "input_full_source_sha256": self.input_full_source_sha256,
            "input_base_mol_block_source_sha256": (
                self.input_base_mol_block_source_sha256
            ),
            "input_canonical_base_mol_block_sha256": (
                self.input_canonical_base_mol_block_sha256
            ),
            "input_base_system_snapshot_sha256": (
                self.input_base_system_snapshot_sha256
            ),
            "input_base_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
            "input_base_topology_sha256": self.input_base_topology_sha256,
            "input_base_representable_state_schema_id": (
                SDF_V2000_REPRESENTABLE_STATE_SCHEMA_ID
            ),
            "input_base_representable_state_sha256": (
                self.input_base_representable_state_sha256
            ),
            "input_data_field_projection_schema_id": (
                SDF_V2000_DATA_FIELD_PROJECTION_SCHEMA_ID
            ),
            "input_data_field_projection_sha256": (
                self.input_data_field_projection_sha256
            ),
            "input_record_representable_state_schema_id": (
                SDF_V2000_DATA_FIELD_RECORD_STATE_SCHEMA_ID
            ),
            "input_record_representable_state_sha256": (
                self.input_record_representable_state_sha256
            ),
            "base_writer_receipt_sha256": self.base_writer_receipt_sha256,
            "output_source_sha256": self.output_source_sha256,
            "output_byte_count": self.output_byte_count,
            "data_field_count": self.data_field_count,
            "data_field_value_line_count": self.data_field_value_line_count,
            "data_field_payload_byte_count": self.data_field_payload_byte_count,
            "named_field_opaque_projection_preserved": True,
            "data_field_semantics_interpreted": False,
            "chemistry_interpreted": False,
            "path_command_url_or_authority_semantics_granted": False,
            "source_authentication_status": "not_authenticated",
            "source_authenticated": False,
            "preparation_ready": False,
            "parameterability_assessed": False,
            "simulation_ready": False,
            "runtime_eligible": False,
            "claim_safe": False,
            "general_sdf_round_trip_evidence_ready": False,
            "all_format_round_trip_evidence_ready": False,
            "blockers": list(_NON_PROMOTION_BLOCKERS),
        }

    @property
    def receipt_sha256(self) -> str:
        return _sha256_document(self._core_dict())

    def to_dict(self) -> dict[str, Any]:
        result = self._core_dict()
        result["receipt_sha256"] = self.receipt_sha256
        return result


@dataclass(frozen=True, slots=True, init=False)
class SdfV2000DataFieldWriteResult:
    payload: bytes = dataclass_field(repr=False)
    receipt: SdfV2000DataFieldWriteReceipt

    def __init__(
        self,
        *,
        payload: bytes,
        receipt: SdfV2000DataFieldWriteReceipt,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SdfV2000DataFieldWriteResult is factory-only")
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "receipt", receipt)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self.payload) is not bytes:
            raise TypeError("write payload must be exact bytes")
        if type(self.receipt) is not SdfV2000DataFieldWriteReceipt:
            raise TypeError("receipt must be SdfV2000DataFieldWriteReceipt")
        if len(self.payload) != self.receipt.output_byte_count:
            raise ValueError("write payload byte count does not match receipt")
        if (
            hashlib.sha256(self.payload).hexdigest()
            != self.receipt.output_source_sha256
        ):
            raise ValueError("write payload SHA-256 does not match receipt")


def _compose_output(
    base_payload: bytes,
    fields: tuple[SdfV2000DataField, ...],
) -> bytes:
    delimiter = b"$$$$\n"
    if not base_payload.endswith(delimiter):
        raise SdfV2000DataFieldError(
            "base_writer_contract_drift",
            "strict base writer no longer emits the expected delimiter",
        )
    if not fields:
        payload = base_payload
    else:
        payload = (
            base_payload[: -len(delimiter)]
            + _canonical_data_payload(fields)
            + delimiter
        )
    if len(payload) > _MAX_SDF_INPUT_BYTES:
        raise SdfV2000DataFieldError(
            "output_too_large", "output exceeds the inherited byte safety limit"
        )
    lines = payload.decode("ascii").splitlines()
    if len(lines) > _MAX_SDF_LINE_COUNT:
        raise SdfV2000DataFieldError(
            "output_too_many_lines", "output exceeds the inherited line safety limit"
        )
    if any(len(line) > _MAX_SDF_LINE_CHARS for line in lines):
        raise SdfV2000DataFieldError(
            "output_line_too_long", "output exceeds the inherited line-width limit"
        )
    return payload


def write_sdf_v2000_data_fields(
    ingest: SdfV2000DataFieldIngestResult,
) -> SdfV2000DataFieldWriteResult:
    """Emit a checked canonical base record plus ordered opaque data fields."""

    base_ingest, base_payload = _validate_ingest(ingest)
    base_write = write_sdf_v2000(base_ingest.system)
    if base_write.payload != base_payload:
        raise SdfV2000DataFieldError(
            "unstable_base_emission", "strict base writer emission is not stable"
        )
    payload = _compose_output(base_payload, ingest.data_fields)
    receipt = SdfV2000DataFieldWriteReceipt(
        input_full_source_sha256=ingest.full_source_sha256,
        input_base_mol_block_source_sha256=ingest.base_mol_block_source_sha256,
        input_canonical_base_mol_block_sha256=(ingest.canonical_base_mol_block_sha256),
        input_base_system_snapshot_sha256=ingest.base_system_snapshot_sha256,
        input_base_topology_sha256=ingest.base_topology_sha256,
        input_base_representable_state_sha256=(ingest.base_representable_state_sha256),
        input_data_field_projection_sha256=ingest.data_field_projection_sha256,
        input_record_representable_state_sha256=(
            ingest.record_representable_state_sha256
        ),
        base_writer_receipt_sha256=base_write.receipt.receipt_sha256,
        output_source_sha256=hashlib.sha256(payload).hexdigest(),
        output_byte_count=len(payload),
        data_field_count=ingest.data_field_count,
        data_field_value_line_count=ingest.data_field_value_line_count,
        data_field_payload_byte_count=ingest.data_field_payload_byte_count,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )
    return SdfV2000DataFieldWriteResult(
        payload=payload,
        receipt=receipt,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )


def serialize_sdf_v2000_data_fields(
    ingest: SdfV2000DataFieldIngestResult,
) -> bytes:
    """Return deterministic bytes for the checked data-field envelope."""

    return write_sdf_v2000_data_fields(ingest).payload


@dataclass(frozen=True, slots=True, init=False)
class SdfV2000DataFieldRoundTripReport:
    input_full_source_sha256: str
    input_base_system_snapshot_sha256: str
    input_base_topology_sha256: str
    input_data_field_projection_sha256: str
    input_record_representable_state_sha256: str
    writer_receipt_sha256: str
    emitted_source_sha256: str
    reparsed_base_system_snapshot_sha256: str
    reparsed_base_topology_sha256: str
    reparsed_data_field_projection_sha256: str
    reparsed_record_representable_state_sha256: str
    reemitted_source_sha256: str

    def __init__(self, *, _factory_token: object | None = None, **values: Any) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SdfV2000DataFieldRoundTripReport is factory-only")
        expected = tuple(self.__annotations__)
        if frozenset(values) != frozenset(expected):
            raise TypeError("round-trip report fields do not match the schema")
        for name in expected:
            object.__setattr__(self, name, values[name])
        self.__post_init__()

    def __post_init__(self) -> None:
        for field_name in self.__annotations__:
            _require_sha256(getattr(self, field_name), field_name=field_name)
        if self.input_base_topology_sha256 != self.reparsed_base_topology_sha256:
            raise ValueError("round-trip base topology hashes must match")
        if self.input_data_field_projection_sha256 != (
            self.reparsed_data_field_projection_sha256
        ):
            raise ValueError("round-trip data-field projection hashes must match")
        if self.input_record_representable_state_sha256 != (
            self.reparsed_record_representable_state_sha256
        ):
            raise ValueError("round-trip record-state hashes must match")
        if self.emitted_source_sha256 != self.reemitted_source_sha256:
            raise ValueError("round-trip emitted source hashes must match")

    def _core_dict(self) -> dict[str, Any]:
        values = {name: getattr(self, name) for name in self.__annotations__}
        return {
            "schema_id": SDF_V2000_DATA_FIELD_ROUND_TRIP_REPORT_SCHEMA_ID,
            "envelope_version": SDF_V2000_DATA_FIELD_ENVELOPE_VERSION,
            "parser_version": SDF_V2000_DATA_FIELD_PARSER_VERSION,
            "writer_version": SDF_V2000_DATA_FIELD_WRITER_VERSION,
            "profile_id": SDF_V2000_DATA_FIELD_PROFILE_ID,
            "parser_name": SDF_V2000_DATA_FIELD_PARSER_NAME,
            "base_parser_version": SDF_V2000_PARSER_VERSION,
            "base_writer_version": SDF_V2000_WRITER_VERSION,
            **values,
            "named_field_opaque_projection_preserved": True,
            "named_field_opaque_projection_sha256_equal": True,
            "base_canonical_topology_sha256_equal": True,
            "record_representable_state_sha256_equal": True,
            "emitted_source_sha256_and_bytes_stable": True,
            "data_field_semantics_interpreted": False,
            "chemistry_interpreted": False,
            "path_command_url_or_authority_semantics_granted": False,
            "source_authentication_status": "not_authenticated",
            "source_authenticated": False,
            "preparation_ready": False,
            "parameterability_assessed": False,
            "simulation_ready": False,
            "runtime_eligible": False,
            "claim_safe": False,
            "general_sdf_round_trip_evidence_ready": False,
            "all_format_round_trip_evidence_ready": False,
            "blockers": list(_NON_PROMOTION_BLOCKERS),
        }

    @property
    def report_sha256(self) -> str:
        return _sha256_document(self._core_dict())

    def to_dict(self) -> dict[str, Any]:
        result = self._core_dict()
        result["report_sha256"] = self.report_sha256
        return result


@dataclass(frozen=True, slots=True, init=False)
class SdfV2000DataFieldRoundTripResult:
    source_ingest: SdfV2000DataFieldIngestResult = dataclass_field(repr=False)
    write_result: SdfV2000DataFieldWriteResult = dataclass_field(repr=False)
    reparsed_ingest: SdfV2000DataFieldIngestResult = dataclass_field(repr=False)
    report: SdfV2000DataFieldRoundTripReport

    def __init__(
        self,
        *,
        source_ingest: SdfV2000DataFieldIngestResult,
        write_result: SdfV2000DataFieldWriteResult,
        reparsed_ingest: SdfV2000DataFieldIngestResult,
        report: SdfV2000DataFieldRoundTripReport,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SdfV2000DataFieldRoundTripResult is factory-only")
        for name, value in (
            ("source_ingest", source_ingest),
            ("write_result", write_result),
            ("reparsed_ingest", reparsed_ingest),
            ("report", report),
        ):
            object.__setattr__(self, name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self.source_ingest) is not SdfV2000DataFieldIngestResult:
            raise TypeError("source_ingest has the wrong type")
        if type(self.write_result) is not SdfV2000DataFieldWriteResult:
            raise TypeError("write_result has the wrong type")
        if type(self.reparsed_ingest) is not SdfV2000DataFieldIngestResult:
            raise TypeError("reparsed_ingest has the wrong type")
        if type(self.report) is not SdfV2000DataFieldRoundTripReport:
            raise TypeError("report has the wrong type")
        source_write = write_sdf_v2000_data_fields(self.source_ingest)
        reparsed_write = write_sdf_v2000_data_fields(self.reparsed_ingest)
        expected = (
            (source_write.payload, self.write_result.payload),
            (
                source_write.receipt.receipt_sha256,
                self.write_result.receipt.receipt_sha256,
            ),
            (
                self.write_result.receipt.receipt_sha256,
                self.report.writer_receipt_sha256,
            ),
            (
                self.source_ingest.full_source_sha256,
                self.report.input_full_source_sha256,
            ),
            (
                self.source_ingest.base_system_snapshot_sha256,
                self.report.input_base_system_snapshot_sha256,
            ),
            (
                self.source_ingest.base_topology_sha256,
                self.report.input_base_topology_sha256,
            ),
            (
                self.source_ingest.data_field_projection_sha256,
                self.report.input_data_field_projection_sha256,
            ),
            (
                self.source_ingest.record_representable_state_sha256,
                self.report.input_record_representable_state_sha256,
            ),
            (
                self.write_result.receipt.output_source_sha256,
                self.report.emitted_source_sha256,
            ),
            (
                self.reparsed_ingest.base_system_snapshot_sha256,
                self.report.reparsed_base_system_snapshot_sha256,
            ),
            (
                self.reparsed_ingest.base_topology_sha256,
                self.report.reparsed_base_topology_sha256,
            ),
            (
                self.reparsed_ingest.data_field_projection_sha256,
                self.report.reparsed_data_field_projection_sha256,
            ),
            (
                self.reparsed_ingest.record_representable_state_sha256,
                self.report.reparsed_record_representable_state_sha256,
            ),
            (
                reparsed_write.receipt.output_source_sha256,
                self.report.reemitted_source_sha256,
            ),
        )
        if any(left != right for left, right in expected):
            raise ValueError("round-trip artifacts are not cross-consistent")


def round_trip_sdf_v2000_data_fields_source(
    data: bytes,
    *,
    source_id: str = "",
) -> SdfV2000DataFieldRoundTripResult:
    """Verify base-molecule plus ordered named-field deterministic re-emission."""

    source = parse_sdf_v2000_data_fields(data, source_id=source_id)
    write_result = write_sdf_v2000_data_fields(source)
    reparsed = parse_sdf_v2000_data_fields(write_result.payload, source_id=source_id)
    reemitted = write_sdf_v2000_data_fields(reparsed)
    mismatches: list[str] = []
    if source.base_topology_sha256 != reparsed.base_topology_sha256:
        mismatches.append("base_topology")
    if source.data_field_projection_sha256 != reparsed.data_field_projection_sha256:
        mismatches.append("data_field_projection")
    if source.record_representable_state_sha256 != (
        reparsed.record_representable_state_sha256
    ):
        mismatches.append("record_representable_state")
    if write_result.payload != reemitted.payload:
        mismatches.append("reemitted_bytes")
    if mismatches:
        raise SdfV2000DataFieldError(
            "round_trip_mismatch",
            f"declared data-field envelope projection failed: {mismatches}",
        )
    report = SdfV2000DataFieldRoundTripReport(
        input_full_source_sha256=source.full_source_sha256,
        input_base_system_snapshot_sha256=source.base_system_snapshot_sha256,
        input_base_topology_sha256=source.base_topology_sha256,
        input_data_field_projection_sha256=source.data_field_projection_sha256,
        input_record_representable_state_sha256=(
            source.record_representable_state_sha256
        ),
        writer_receipt_sha256=write_result.receipt.receipt_sha256,
        emitted_source_sha256=write_result.receipt.output_source_sha256,
        reparsed_base_system_snapshot_sha256=(reparsed.base_system_snapshot_sha256),
        reparsed_base_topology_sha256=reparsed.base_topology_sha256,
        reparsed_data_field_projection_sha256=(reparsed.data_field_projection_sha256),
        reparsed_record_representable_state_sha256=(
            reparsed.record_representable_state_sha256
        ),
        reemitted_source_sha256=reemitted.receipt.output_source_sha256,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )
    return SdfV2000DataFieldRoundTripResult(
        source_ingest=source,
        write_result=write_result,
        reparsed_ingest=reparsed,
        report=report,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )
