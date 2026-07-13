"""Opt-in preservation envelope for strict PDB ``CONECT`` declarations.

The strict PDB parser intentionally rejects ``CONECT`` because a bare PDB
serial pair cannot establish covalent, coordination, bond-order, or other
chemical semantics.  This module leaves that parser unchanged.  It removes one
final, contiguous ``CONECT`` suffix, parses the remaining carrier with
``parse_pdb``, and preserves the declaration rows as an ordered opaque
projection beside the bondless carrier system.

Direction, duplicate rows, duplicate target slots, and row grouping are
preserved exactly as ordered integer occurrences.  They are never normalized
into an unordered graph or interpreted as bond multiplicity.  All hashes are
tamper evidence only and grant no source or scientific authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Mapping

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID

from .missingness import (
    MISSINGNESS_PRESERVATION_POLICY_ID,
    MISSINGNESS_REPORT_SCHEMA_ID,
    SourceReportedMissingnessReport,
)
from .pdb_mmcif import (
    PDB_PARSER_VERSION,
    StructureIngestCoverage,
    StructureIngestResult,
    StructureParseError,
    parse_pdb,
)
from .pdb_writer import (
    PDB_REPRESENTABLE_STATE_SCHEMA_ID,
    PDB_WRITER_VERSION,
    PdbWriteError,
    pdb_representable_state_sha256,
    write_pdb,
)
from .serialization import (
    canonical_all_atom_snapshot_digest,
    deserialize_all_atom_system,
    serialize_all_atom_system,
)
from .topology import CANONICAL_TOPOLOGY_SCHEMA_ID, canonical_topology_sha256


PDB_CONECT_DECLARATION_ENVELOPE_VERSION = "1.0.0"
PDB_CONECT_DECLARATION_PARSER_VERSION = "1.0.0"
PDB_CONECT_DECLARATION_WRITER_VERSION = "1.0.0"
PDB_CONECT_DECLARATION_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular.pdb_conect_declaration"
)
PDB_CONECT_DECLARATION_PROFILE_ID = (
    "strict_pdb_single_model_id1_ordered_conect_declaration_envelope/1.0.0"
)
PDB_CONECT_DECLARATION_PROJECTION_SCOPE = (
    "ordered_source_directed_conect_rows_and_target_slot_occurrences_only"
)
PDB_CONECT_DECLARATION_PROJECTION_SCHEMA_ID = (
    "betelgeuze.pdb_conect_declaration_projection/1.0.0"
)
PDB_CONECT_DECLARATION_RECORD_STATE_SCHEMA_ID = (
    "betelgeuze.pdb_conect_declaration_record_state/1.0.0"
)
PDB_CONECT_DECLARATION_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.pdb_conect_declaration_source_binding/1.0.0"
)
PDB_CONECT_DECLARATION_WRITE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.pdb_conect_declaration_write_receipt/1.0.0"
)
PDB_CONECT_DECLARATION_ROUND_TRIP_REPORT_SCHEMA_ID = (
    "betelgeuze.pdb_conect_declaration_round_trip_report/1.0.0"
)

MAX_PDB_CONECT_DECLARATION_INPUT_BYTES = 64 * 1024 * 1024
MAX_PDB_CONECT_DECLARATION_SOURCE_ID_BYTES = 4_096
MAX_PDB_CONECT_DECLARATION_LINE_COUNT = 250_000
MAX_PDB_CONECT_DECLARATION_RECORDS = 20_000
MAX_PDB_CONECT_DECLARATION_TARGET_OCCURRENCES = 80_000
MAX_PDB_CONECT_DECLARATION_PROJECTION_BYTES = 16 * 1024 * 1024
MAX_PDB_CONECT_DECLARATION_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_PDB_CONECT_DECLARATION_OUTPUT_LINES = 250_000
MAX_PDB_CONECT_DECLARATION_OUTPUT_LINE_CHARS = 80

_FACTORY_TOKEN = object()
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BASE_PDB_PARSER_NAME = "betelgeuze_engine_v2.molecular.pdb_mmcif.parse_pdb"
_BASE_PDB_OPERATIONS = (
    "parse_strict_fixed_column_pdb",
    "preserve_source_atom_order",
)
_BASE_PDB_COVERAGE_BLOCKERS = (
    "bond_topology_incomplete_or_unverified",
    "biological_assembly_not_applied",
    "missing_atom_and_residue_completion_not_assessed",
    "hydrogen_and_protonation_not_assessed",
    "stereochemistry_not_assessed",
    "modified_residue_cofactor_and_parameterability_not_assessed",
)
_BASE_PDB_PROVENANCE_METADATA_KEYS = frozenset(
    {
        "coverage",
        "model_ids",
        "canonical_topology_schema_id",
        "canonical_topology_sha256",
        "source_missingness_evidence_schema_id",
        "source_missingness_evidence_sha256",
        "parser_observation_schema_id",
        "parser_observation_sha256",
    }
)
_BASE_PDB_SYSTEM_METADATA_KEYS = frozenset({"pdb"})
_BASE_PDB_FORMAT_METADATA_KEYS = frozenset(
    {
        "ter_count",
        "ter_records_by_model",
        "cryst1",
        "altloc_selection",
        "source_missingness",
        "resource_usage",
        "resource_limits",
        "source_reported_missingness",
    }
)

_FALSE_AUTHORITY_FIELDS = (
    "bare_system_preserves_declaration",
    "source_authenticated",
    "conect_declaration_authoritative",
    "declaration_authoritative",
    "bond_topology_established",
    "bond_topology_interpreted",
    "bond_kind_interpreted",
    "bond_order_assigned",
    "bond_order_interpreted",
    "covalent_bond_interpreted",
    "covalence_assessed",
    "coordination_bond_interpreted",
    "coordination_assessed",
    "chemistry_interpreted",
    "preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "runtime_eligible",
    "execution_authorized",
    "simulation_ready",
    "claim_safe",
    "general_pdb_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)
_NON_PROMOTION_BLOCKERS = (
    "conect_rows_are_preserved_as_ordered_opaque_declarations_only",
    "direction_duplicates_and_row_grouping_are_not_bond_semantics",
    "bond_topology_and_bond_order_are_not_established",
    "covalent_and_coordination_semantics_are_not_interpreted",
    "source_authentication_not_established",
    "chemistry_preparation_parameterability_and_physics_not_assessed",
    "runtime_execution_and_simulation_authority_not_granted",
    "general_pdb_round_trip_evidence_not_established",
    "all_format_round_trip_evidence_not_established",
)


class PdbConectDeclarationError(ValueError):
    """Stable fail-closed error for the opt-in declaration envelope."""

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
        super().__init__(f"pdb_conect_declaration:{self.code}{suffix}: {self.detail}")


def _canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_document(document: Mapping[str, Any]) -> str:
    return _sha256_bytes(_canonical_json_bytes(document))


def _require_sha256(value: str, *, field_name: str) -> None:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise TypeError(f"{field_name} must be a lowercase SHA-256")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if value is None or type(value) in {str, bool, int}:
        return value
    raise PdbConectDeclarationError(
        "unsupported_evidence_type",
        f"declaration evidence contains unsupported type {type(value).__name__}",
    )


def _exact_typed_json_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(
            _exact_typed_json_equal(actual[key], expected[key]) for key in expected
        )
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            _exact_typed_json_equal(left, right)
            for left, right in zip(actual, expected, strict=True)
        )
    return bool(actual == expected)


def _authority_false_document() -> dict[str, bool]:
    return {name: False for name in _FALSE_AUTHORITY_FIELDS}


def _source_id_sha256(source_id: str) -> str:
    if type(source_id) is not str:
        raise TypeError("source_id must be an exact string")
    try:
        encoded = source_id.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise PdbConectDeclarationError(
            "invalid_source_id", "source_id must be valid UTF-8 text"
        ) from exc
    if len(encoded) > MAX_PDB_CONECT_DECLARATION_SOURCE_ID_BYTES:
        raise PdbConectDeclarationError(
            "source_id_too_large", "source_id exceeds the fixed UTF-8 byte limit"
        )
    return _sha256_bytes(encoded)


@dataclass(frozen=True, slots=True, init=False)
class PdbConectDeclarationRow:
    """One ordered directed source row with ordered opaque target slots."""

    ordinal: int
    source_serial: int
    target_serials: tuple[int, ...]

    def __init__(
        self,
        *,
        ordinal: int,
        source_serial: int,
        target_serials: tuple[int, ...],
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("PdbConectDeclarationRow is factory-only")
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "source_serial", source_serial)
        object.__setattr__(self, "target_serials", target_serials)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self.ordinal) is not int or self.ordinal < 0:
            raise TypeError("CONECT row ordinal must be a nonnegative integer")
        if type(self.source_serial) is not int or not 1 <= self.source_serial <= 99_999:
            raise ValueError("CONECT source serial must be a positive I5 value")
        if (
            type(self.target_serials) is not tuple
            or not 1 <= len(self.target_serials) <= 4
        ):
            raise ValueError(
                "CONECT target_serials must be a tuple of one through four values"
            )
        for target in self.target_serials:
            if type(target) is not int or not 1 <= target <= 99_999:
                raise ValueError("CONECT target serial must be a positive I5 value")
            if target == self.source_serial:
                raise ValueError("CONECT target serial cannot equal its source")

    @property
    def target_occurrence_count(self) -> int:
        return len(self.target_serials)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "source_serial": self.source_serial,
            "target_serials": list(self.target_serials),
            "target_slot_occurrences": [
                {"slot_ordinal": slot, "target_serial": target}
                for slot, target in enumerate(self.target_serials)
            ],
        }


def _make_row(
    *, ordinal: int, source_serial: int, target_serials: list[int]
) -> PdbConectDeclarationRow:
    return PdbConectDeclarationRow(
        ordinal=ordinal,
        source_serial=source_serial,
        target_serials=tuple(target_serials),
        _factory_token=_FACTORY_TOKEN,
    )


def _projection_document(
    rows: tuple[PdbConectDeclarationRow, ...],
) -> dict[str, Any]:
    target_count = sum(len(row.target_serials) for row in rows)
    return {
        "schema_id": PDB_CONECT_DECLARATION_PROJECTION_SCHEMA_ID,
        "envelope_version": PDB_CONECT_DECLARATION_ENVELOPE_VERSION,
        "parser_version": PDB_CONECT_DECLARATION_PARSER_VERSION,
        "profile_id": PDB_CONECT_DECLARATION_PROFILE_ID,
        "projection_scope": PDB_CONECT_DECLARATION_PROJECTION_SCOPE,
        "conect_record_count": len(rows),
        "target_occurrence_count": target_count,
        "rows": [row.to_dict() for row in rows],
        "row_ordering": "exact_source_order",
        "target_ordering": "exact_left_to_right_occupied_slot_order",
        "direction_preserved": True,
        "duplicate_rows_preserved": True,
        "duplicate_target_occurrences_preserved": True,
        "row_grouping_preserved": True,
        "unordered_normalization_applied": False,
        "duplicate_occurrences_interpreted_as_bond_order": False,
        **_authority_false_document(),
    }


def _parse_i5(field_value: str, *, field_name: str, line_number: int) -> int:
    if len(field_value) != 5:
        raise PdbConectDeclarationError(
            "invalid_conect",
            f"{field_name} must occupy one I5 field",
            line_number=line_number,
        )
    token = field_value.strip()
    if not token or not token.isascii() or not token.isdecimal():
        raise PdbConectDeclarationError(
            "invalid_conect",
            f"{field_name} must be an unsigned decimal I5 value",
            line_number=line_number,
        )
    value = int(token, 10)
    if not 1 <= value <= 99_999:
        raise PdbConectDeclarationError(
            "invalid_conect",
            f"{field_name} must be strictly positive",
            line_number=line_number,
        )
    return value


def _parse_conect_line(
    line: str, *, ordinal: int, line_number: int
) -> PdbConectDeclarationRow:
    if len(line) < 16 or len(line) > MAX_PDB_CONECT_DECLARATION_OUTPUT_LINE_CHARS:
        raise PdbConectDeclarationError(
            "invalid_conect",
            "CONECT requires one source and one through four target I5 fields",
            line_number=line_number,
        )
    padded = line.ljust(MAX_PDB_CONECT_DECLARATION_OUTPUT_LINE_CHARS)
    if padded[0:6] != "CONECT":
        raise PdbConectDeclarationError(
            "invalid_conect",
            "CONECT record name must be exact uppercase fixed-column text",
            line_number=line_number,
        )
    if padded[31:80].strip():
        raise PdbConectDeclarationError(
            "invalid_conect",
            "CONECT reserved and trailing columns must be blank",
            line_number=line_number,
        )
    source = _parse_i5(padded[6:11], field_name="source", line_number=line_number)
    targets: list[int] = []
    blank_seen = False
    for slot_ordinal, start in enumerate((11, 16, 21, 26)):
        value = padded[start : start + 5]
        if not value.strip():
            blank_seen = True
            continue
        if blank_seen:
            raise PdbConectDeclarationError(
                "invalid_conect",
                "occupied CONECT target I5 fields must form a contiguous prefix",
                line_number=line_number,
            )
        targets.append(
            _parse_i5(
                value,
                field_name=f"target slot {slot_ordinal}",
                line_number=line_number,
            )
        )
    if not targets:
        raise PdbConectDeclarationError(
            "invalid_conect",
            "CONECT requires at least one target",
            line_number=line_number,
        )
    if source in targets:
        raise PdbConectDeclarationError(
            "self_reference",
            "CONECT source cannot occur in its own target slots",
            line_number=line_number,
        )
    return _make_row(ordinal=ordinal, source_serial=source, target_serials=targets)


def _decode_and_normalize_source(data: bytes) -> tuple[bytes, list[str], int]:
    if type(data) is not bytes:
        raise TypeError("PDB CONECT declaration input must be exact bytes")
    if not data:
        raise PdbConectDeclarationError("empty_input", "PDB input is empty")
    if len(data) > MAX_PDB_CONECT_DECLARATION_INPUT_BYTES:
        raise PdbConectDeclarationError(
            "input_too_large", "PDB input exceeds the fixed byte limit"
        )
    if any((byte < 0x20 and byte not in {0x0A, 0x0D}) or byte == 0x7F for byte in data):
        raise PdbConectDeclarationError(
            "invalid_ascii",
            "PDB input must contain printable ASCII plus CR/LF separators",
        )
    try:
        data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise PdbConectDeclarationError(
            "invalid_ascii", "fixed-column PDB input must be ASCII"
        ) from exc
    normalized = data.replace(b"\r\n", b"\n")
    if b"\r" in normalized:
        raise PdbConectDeclarationError(
            "invalid_line_endings", "bare carriage returns are not supported"
        )
    physical_line_upper_bound = normalized.count(b"\n") + 1
    if physical_line_upper_bound > MAX_PDB_CONECT_DECLARATION_LINE_COUNT:
        raise PdbConectDeclarationError(
            "too_many_lines", "PDB input exceeds the fixed physical-line limit"
        )
    text = normalized.decode("ascii")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return normalized, lines, physical_line_upper_bound


def _record_name(line: str) -> str:
    return line[0:6].strip().upper()


def _extract_components(
    data: bytes,
) -> tuple[bytes, bytes, tuple[PdbConectDeclarationRow, ...], int]:
    normalized, lines, physical_line_upper_bound = _decode_and_normalize_source(data)
    rows: list[PdbConectDeclarationRow] = []
    conect_indices: list[int] = []
    end_indices: list[int] = []
    inside_model = False
    target_count = 0

    for index, line in enumerate(lines):
        line_number = index + 1
        record = _record_name(line)
        if record == "CRYST1":
            raise PdbConectDeclarationError(
                "unsupported_cryst1",
                "this declaration profile excludes CRYST1",
                line_number=line_number,
            )
        if record == "REMARK":
            raise PdbConectDeclarationError(
                "unsupported_missingness",
                "this declaration profile excludes PDB REMARK records",
                line_number=line_number,
            )
        if record in {"ATOM", "HETATM"} and len(line) > 16 and line[16] != " ":
            raise PdbConectDeclarationError(
                "unsupported_altloc",
                "this declaration profile excludes alternate-location atom rows",
                line_number=line_number,
            )
        if record == "MODEL":
            inside_model = True
        elif record == "ENDMDL":
            inside_model = False
        elif record == "END":
            end_indices.append(index)
        elif record == "CONECT":
            if end_indices:
                raise PdbConectDeclarationError(
                    "conect_after_end",
                    "CONECT cannot occur after END",
                    line_number=line_number,
                )
            if inside_model:
                raise PdbConectDeclarationError(
                    "conect_inside_model",
                    "CONECT must be outside MODEL/ENDMDL",
                    line_number=line_number,
                )
            if len(rows) >= MAX_PDB_CONECT_DECLARATION_RECORDS:
                raise PdbConectDeclarationError(
                    "too_many_conect_records",
                    "CONECT rows exceed the fixed record limit",
                    line_number=line_number,
                )
            row = _parse_conect_line(line, ordinal=len(rows), line_number=line_number)
            target_count += len(row.target_serials)
            if target_count > MAX_PDB_CONECT_DECLARATION_TARGET_OCCURRENCES:
                raise PdbConectDeclarationError(
                    "too_many_target_occurrences",
                    "CONECT target slots exceed the fixed occurrence limit",
                    line_number=line_number,
                )
            rows.append(row)
            conect_indices.append(index)

    if not rows:
        raise PdbConectDeclarationError(
            "missing_conect_declaration",
            "at least one CONECT declaration row is required",
        )
    if len(end_indices) != 1:
        raise PdbConectDeclarationError(
            "invalid_end_layout",
            "the declaration profile requires exactly one END record",
        )
    expected_indices = list(range(conect_indices[0], conect_indices[-1] + 1))
    if conect_indices != expected_indices or end_indices[0] != conect_indices[-1] + 1:
        raise PdbConectDeclarationError(
            "noncontiguous_conect_suffix",
            "CONECT rows must be one contiguous suffix immediately before END",
        )
    if any(line.strip() for line in lines[end_indices[0] + 1 :]):
        raise PdbConectDeclarationError(
            "content_after_end", "nonblank content after END is not supported"
        )

    rows_tuple = tuple(rows)
    projection_bytes = _canonical_json_bytes(_projection_document(rows_tuple))
    if len(projection_bytes) > MAX_PDB_CONECT_DECLARATION_PROJECTION_BYTES:
        raise PdbConectDeclarationError(
            "projection_too_large", "ordered CONECT projection exceeds its byte limit"
        )
    carrier_lines = [
        *lines[: conect_indices[0]],
        *lines[conect_indices[-1] + 1 :],
    ]
    carrier_source = ("\n".join(carrier_lines) + "\n").encode("ascii")
    return normalized, carrier_source, rows_tuple, physical_line_upper_bound


def _nested_base_error(exc: Exception, *, action: str) -> PdbConectDeclarationError:
    code = getattr(exc, "code", type(exc).__name__)
    line_number = getattr(exc, "line_number", None)
    envelope_code = (
        "unsupported_base_pdb" if action == "parse" else "unwritable_base_pdb"
    )
    return PdbConectDeclarationError(
        envelope_code,
        f"strict base PDB {action} failed ({code})",
        line_number=line_number,
    )


def _validate_base_profile(base: StructureIngestResult) -> None:
    if type(base) is not StructureIngestResult:
        raise TypeError("base parse must produce an exact StructureIngestResult")
    system = base.system
    coverage = base.coverage
    missingness = base.missingness_evidence
    if type(coverage) is not StructureIngestCoverage:
        raise PdbConectDeclarationError(
            "stale_base_coverage",
            "detached carrier coverage must have the exact base-parser type",
        )
    if type(missingness) is not SourceReportedMissingnessReport:
        raise PdbConectDeclarationError(
            "stale_base_missingness",
            "detached carrier missingness must have the exact base-parser type",
        )
    try:
        missingness.__post_init__()
    except (TypeError, ValueError) as exc:
        raise PdbConectDeclarationError(
            "stale_base_missingness",
            "detached carrier missingness violates its preserve-only contract",
        ) from exc

    provenance = system.provenance
    metadata = provenance.metadata
    if frozenset(metadata) != _BASE_PDB_PROVENANCE_METADATA_KEYS:
        raise PdbConectDeclarationError(
            "base_parser_contract_drift",
            "carrier provenance metadata surface differs from the base parser contract",
        )
    if (
        frozenset(system.metadata) != _BASE_PDB_SYSTEM_METADATA_KEYS
        or not isinstance(system.metadata.get("pdb"), Mapping)
        or frozenset(system.metadata["pdb"]) != _BASE_PDB_FORMAT_METADATA_KEYS
    ):
        raise PdbConectDeclarationError(
            "base_parser_contract_drift",
            "carrier system metadata surface differs from the base PDB contract",
        )
    model_ids = metadata.get("model_ids")
    if (
        system.model_count != 1
        or coverage.model_count != 1
        or tuple(model_ids or ()) != (1,)
    ):
        raise PdbConectDeclarationError(
            "unsupported_model_profile",
            "CONECT declaration preservation requires only model ID 1",
        )
    if (
        provenance.source_format != "pdb"
        or provenance.parser_name != _BASE_PDB_PARSER_NAME
        or provenance.parser_version != PDB_PARSER_VERSION
        or provenance.parent_sha256 != ()
    ):
        raise PdbConectDeclarationError(
            "base_parser_contract_drift",
            "carrier does not have the current strict PDB parser pedigree",
        )
    if tuple(provenance.operations) != _BASE_PDB_OPERATIONS:
        raise PdbConectDeclarationError(
            "base_parser_contract_drift",
            "carrier parser operations differ from the declaration profile",
        )
    if (
        provenance.preparation_ready is not False
        or provenance.claim_safe is not False
        or coverage.supported is not True
        or coverage.syntax_ingest_supported is not True
        or coverage.preparation_ready is not False
        or coverage.claim_safe is not False
        or missingness.completion_attempted is not False
        or missingness.completion_applied is not False
        or missingness.preparation_ready is not False
        or missingness.claim_safe is not False
    ):
        raise PdbConectDeclarationError(
            "base_authority_drift",
            "carrier parser evidence must remain syntax-only and non-authoritative",
        )
    if system.cell is not None or coverage.cell_present:
        raise PdbConectDeclarationError(
            "unsupported_cryst1",
            "this declaration profile requires a nonperiodic carrier",
        )
    if system.bonds or coverage.bond_count != 0:
        raise PdbConectDeclarationError(
            "base_bond_state_not_empty",
            "CONECT declarations must not populate carrier bonds",
        )
    if coverage.altloc_status != "not_present" or coverage.requested_altloc_id:
        raise PdbConectDeclarationError(
            "unsupported_altloc",
            "this declaration profile excludes alternate locations",
        )
    if (
        coverage.missingness_evidence_status != "not_present"
        or coverage.source_reported_missing_residue_claim_count != 0
        or coverage.source_reported_missing_atom_claim_count != 0
    ):
        raise PdbConectDeclarationError(
            "unsupported_missingness",
            "this declaration profile excludes source missingness evidence",
        )
    if system.schema_id != ALL_ATOM_SCHEMA_ID or coverage.source_format != "pdb":
        raise PdbConectDeclarationError(
            "base_parser_contract_drift",
            "carrier is outside the strict all-atom PDB schema",
        )
    if system.coordinate_unit != "angstrom":
        raise PdbConectDeclarationError(
            "base_parser_contract_drift",
            "carrier coordinates must retain the base parser angstrom unit",
        )

    topology_sha256 = canonical_topology_sha256(system)
    missingness_document = missingness.to_dict()
    try:
        attached_missingness = _plain(
            system.metadata["pdb"]["source_reported_missingness"]
        )
    except (KeyError, TypeError, PdbConectDeclarationError) as exc:
        raise PdbConectDeclarationError(
            "stale_base_missingness",
            "carrier system metadata lacks exact PDB missingness evidence",
        ) from exc
    if (
        missingness.source_sha256 != provenance.source_sha256
        or missingness.canonical_topology_sha256 != topology_sha256
        or metadata.get("source_missingness_evidence_schema_id")
        != MISSINGNESS_REPORT_SCHEMA_ID
        or metadata.get("source_missingness_evidence_sha256")
        != missingness.report_sha256
        or not _exact_typed_json_equal(attached_missingness, missingness_document)
    ):
        raise PdbConectDeclarationError(
            "stale_base_missingness",
            "detached carrier missingness differs from live or attached evidence",
        )
    unknown_formal_charge_count = sum(
        atom.formal_charge_known is False for atom in system.atoms
    )
    unknown_entity_type_count = sum(
        residue.entity_type == "unknown" for residue in system.residues
    )
    expected_blockers = [*_BASE_PDB_COVERAGE_BLOCKERS]
    if unknown_formal_charge_count:
        expected_blockers.append("formal_charge_unknown_for_some_atoms")
    if unknown_entity_type_count:
        expected_blockers.append("entity_type_unknown_for_some_residues")
    expected_coverage = {
        "source_format": "pdb",
        "support_scope": "syntax_and_canonical_projection_only",
        "supported": True,
        "syntax_ingest_supported": True,
        "preparation_ready": False,
        "claim_safe": False,
        "atom_count": system.atom_count,
        "bond_count": len(system.bonds),
        "residue_count": len(system.residues),
        "chain_count": len(system.chains),
        "model_count": system.model_count,
        "explicit_hydrogen_count": sum(atom.element == "H" for atom in system.atoms),
        "hetero_residue_count": sum(residue.hetero for residue in system.residues),
        "cell_present": system.cell is not None,
        "unknown_formal_charge_count": unknown_formal_charge_count,
        "unknown_entity_type_count": unknown_entity_type_count,
        "uninterpreted_category_count": 0,
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "canonical_topology_sha256": topology_sha256,
        "source_atom_row_count": system.atom_count,
        "altloc_status": "not_present",
        "requested_altloc_id": "",
        "altloc_affected_residue_count": 0,
        "altloc_kept_row_count": system.atom_count,
        "altloc_discarded_row_count": 0,
        "coordinate_scope": "deposited_coordinates",
        "assembly_status": "not_supported_for_pdb",
        "requested_assembly_id": "",
        "assembly_operation_sequence_count": 0,
        "assembly_operation_application_count": 0,
        "assembly_chain_instance_count": 0,
        "assembly_output_atom_count": 0,
        "missingness_evidence_status": "not_present",
        "source_reported_missing_residue_claim_count": 0,
        "source_reported_missing_atom_claim_count": 0,
        "source_missingness_evidence_schema_id": MISSINGNESS_REPORT_SCHEMA_ID,
        "source_missingness_evidence_sha256": missingness.report_sha256,
        "missingness_completion_policy_id": MISSINGNESS_PRESERVATION_POLICY_ID,
        "missingness_completion_status": "not_assessed",
        "blockers": expected_blockers,
    }
    coverage_document = coverage.to_dict()
    if not _exact_typed_json_equal(coverage_document, expected_coverage):
        raise PdbConectDeclarationError(
            "stale_base_coverage",
            "detached carrier coverage does not exactly mirror live carrier state",
        )
    try:
        attached_coverage = _plain(metadata["coverage"])
    except (KeyError, PdbConectDeclarationError) as exc:
        raise PdbConectDeclarationError(
            "stale_base_coverage",
            "carrier provenance lacks exact attached coverage",
        ) from exc
    if not _exact_typed_json_equal(attached_coverage, coverage_document):
        raise PdbConectDeclarationError(
            "stale_base_coverage",
            "detached and provenance-attached carrier coverage differ",
        )
    if (
        metadata.get("canonical_topology_schema_id") != CANONICAL_TOPOLOGY_SCHEMA_ID
        or metadata.get("canonical_topology_sha256") != topology_sha256
    ):
        raise PdbConectDeclarationError(
            "stale_base_coverage",
            "carrier topology and provenance coverage bindings differ",
        )

    expected_missingness_fields = {
        "schema_id": MISSINGNESS_REPORT_SCHEMA_ID,
        "policy_id": MISSINGNESS_PRESERVATION_POLICY_ID,
        "source_format": "pdb",
        "source_sha256": provenance.source_sha256,
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "canonical_topology_sha256": topology_sha256,
        "coordinate_scope": "deposited_coordinates",
        "altloc_status": "not_present",
        "requested_altloc_id": "",
        "assembly_status": "not_supported_for_pdb",
        "requested_assembly_id": "",
        "missing_residue_claims": [],
        "missing_atom_claims": [],
        "source_reported_missing_residue_count": 0,
        "source_reported_missing_atom_count": 0,
        "completion_attempted": False,
        "completion_applied": False,
        "preparation_ready": False,
        "claim_safe": False,
    }
    if any(
        key not in missingness_document
        or not _exact_typed_json_equal(missingness_document[key], expected)
        for key, expected in expected_missingness_fields.items()
    ):
        raise PdbConectDeclarationError(
            "stale_base_missingness",
            "detached carrier missingness does not mirror live source and topology state",
        )
    if (
        metadata.get("source_missingness_evidence_schema_id")
        != MISSINGNESS_REPORT_SCHEMA_ID
        or metadata.get("source_missingness_evidence_sha256")
        != missingness.report_sha256
    ):
        raise PdbConectDeclarationError(
            "stale_base_missingness",
            "carrier provenance missingness digest differs from detached evidence",
        )
    try:
        pdb_metadata = system.metadata["pdb"]
        attached_missingness = _plain(pdb_metadata["source_reported_missingness"])
        raw_missingness = _plain(pdb_metadata["source_missingness"])
    except (KeyError, TypeError, PdbConectDeclarationError) as exc:
        raise PdbConectDeclarationError(
            "stale_base_missingness",
            "carrier system metadata lacks exact PDB missingness evidence",
        ) from exc
    if not _exact_typed_json_equal(attached_missingness, missingness_document):
        raise PdbConectDeclarationError(
            "stale_base_missingness",
            "detached and system-attached carrier missingness evidence differ",
        )
    expected_raw_missingness = {
        "interpretation_policy": "strict_remark_465_470_preserve_only/v1",
        "remark_line_count": 0,
        "remark_465_line_count": 0,
        "remark_470_line_count": 0,
        "raw_records": [],
    }
    if not _exact_typed_json_equal(raw_missingness, expected_raw_missingness):
        raise PdbConectDeclarationError(
            "stale_base_missingness",
            "PDB raw missingness ledger must be exactly empty in this profile",
        )


@dataclass(frozen=True, slots=True)
class _ParsedComponents:
    full_source: bytes = field(repr=False)
    normalized_source: bytes = field(repr=False)
    carrier_source: bytes = field(repr=False)
    canonical_carrier_source: bytes = field(repr=False)
    carrier_snapshot: bytes = field(repr=False)
    source_id: str = field(repr=False)
    source_id_sha256: str
    rows: tuple[PdbConectDeclarationRow, ...]
    coverage: StructureIngestCoverage
    missingness_report_sha256: str
    carrier_snapshot_sha256: str
    carrier_topology_sha256: str
    carrier_representable_state_sha256: str
    base_writer_receipt_sha256: str
    physical_line_upper_bound: int


def _parse_components(data: bytes, *, source_id: str) -> _ParsedComponents:
    source_id_digest = _source_id_sha256(source_id)
    normalized, carrier_source, rows, physical_lines = _extract_components(data)
    try:
        base = parse_pdb(carrier_source, source_id=source_id)
    except StructureParseError as exc:
        raise _nested_base_error(exc, action="parse") from exc
    _validate_base_profile(base)
    if (
        base.system.provenance.source_id != source_id
        or base.system.provenance.source_sha256 != _sha256_bytes(carrier_source)
    ):
        raise PdbConectDeclarationError(
            "base_parser_contract_drift",
            "carrier parser source identifier or source digest binding is stale",
        )

    atom_serials = {atom.serial: atom.index for atom in base.system.atoms}
    for row in rows:
        if row.source_serial not in atom_serials:
            raise PdbConectDeclarationError(
                "unknown_atom_reference",
                "CONECT source serial does not reference a carrier ATOM/HETATM",
            )
        if any(target not in atom_serials for target in row.target_serials):
            raise PdbConectDeclarationError(
                "unknown_atom_reference",
                "CONECT target serial does not reference a carrier ATOM/HETATM",
            )

    try:
        base_write = write_pdb(base.system)
        base_state_sha256 = pdb_representable_state_sha256(base.system)
    except PdbWriteError as exc:
        raise _nested_base_error(exc, action="write") from exc
    canonical_carrier = base_write.payload
    try:
        canonical_reparse = parse_pdb(canonical_carrier, source_id=source_id)
        canonical_rewrite = write_pdb(canonical_reparse.system)
    except (StructureParseError, PdbWriteError) as exc:
        raise PdbConectDeclarationError(
            "base_writer_contract_drift",
            f"canonical base PDB failed its inherited parser/writer contract ({getattr(exc, 'code', type(exc).__name__)})",
        ) from exc
    _validate_base_profile(canonical_reparse)
    if (
        canonical_reparse.system.provenance.source_id != source_id
        or canonical_reparse.system.provenance.source_sha256
        != _sha256_bytes(canonical_carrier)
    ):
        raise PdbConectDeclarationError(
            "base_parser_contract_drift",
            "canonical carrier parser source binding is stale",
        )
    if (
        canonical_rewrite.payload != canonical_carrier
        or canonical_topology_sha256(canonical_reparse.system)
        != canonical_topology_sha256(base.system)
        or pdb_representable_state_sha256(canonical_reparse.system) != base_state_sha256
    ):
        raise PdbConectDeclarationError(
            "base_writer_contract_drift",
            "canonical carrier is not stable under the inherited base contract",
        )

    components = _ParsedComponents(
        full_source=data,
        normalized_source=normalized,
        carrier_source=carrier_source,
        canonical_carrier_source=canonical_carrier,
        carrier_snapshot=serialize_all_atom_system(base.system),
        source_id=source_id,
        source_id_sha256=source_id_digest,
        rows=rows,
        coverage=base.coverage,
        missingness_report_sha256=base.missingness_evidence.report_sha256,
        carrier_snapshot_sha256=canonical_all_atom_snapshot_digest(base.system),
        carrier_topology_sha256=canonical_topology_sha256(base.system),
        carrier_representable_state_sha256=base_state_sha256,
        base_writer_receipt_sha256=base_write.receipt.receipt_sha256,
        physical_line_upper_bound=physical_lines,
    )
    _compose_output(components)
    return components


def _projection_sha256(components: _ParsedComponents) -> str:
    return _sha256_document(_projection_document(components.rows))


def _coverage_sha256(components: _ParsedComponents) -> str:
    return _sha256_document(components.coverage.to_dict())


def _record_state_document(components: _ParsedComponents) -> dict[str, Any]:
    return {
        "schema_id": PDB_CONECT_DECLARATION_RECORD_STATE_SCHEMA_ID,
        "envelope_version": PDB_CONECT_DECLARATION_ENVELOPE_VERSION,
        "parser_version": PDB_CONECT_DECLARATION_PARSER_VERSION,
        "writer_version": PDB_CONECT_DECLARATION_WRITER_VERSION,
        "profile_id": PDB_CONECT_DECLARATION_PROFILE_ID,
        "projection_scope": PDB_CONECT_DECLARATION_PROJECTION_SCOPE,
        "base_parser_name": _BASE_PDB_PARSER_NAME,
        "base_parser_version": PDB_PARSER_VERSION,
        "base_parser_operations": list(_BASE_PDB_OPERATIONS),
        "base_writer_version": PDB_WRITER_VERSION,
        "carrier_system_schema_id": ALL_ATOM_SCHEMA_ID,
        "carrier_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "carrier_topology_sha256": components.carrier_topology_sha256,
        "carrier_representable_state_schema_id": (PDB_REPRESENTABLE_STATE_SCHEMA_ID),
        "carrier_representable_state_sha256": (
            components.carrier_representable_state_sha256
        ),
        "canonical_carrier_source_sha256": _sha256_bytes(
            components.canonical_carrier_source
        ),
        "declaration_projection_schema_id": (
            PDB_CONECT_DECLARATION_PROJECTION_SCHEMA_ID
        ),
        "declaration_projection_sha256": _projection_sha256(components),
        "source_id_sha256": components.source_id_sha256,
        "conect_record_count": len(components.rows),
        "target_occurrence_count": sum(
            len(row.target_serials) for row in components.rows
        ),
        "carrier_bond_count": 0,
        "carrier_model_count": 1,
        "carrier_model_ids": [1],
        "ordered_declaration_projection_preserved": True,
        **_authority_false_document(),
    }


def _source_binding_document(components: _ParsedComponents) -> dict[str, Any]:
    projection_bytes = _canonical_json_bytes(_projection_document(components.rows))
    return {
        "schema_id": PDB_CONECT_DECLARATION_SOURCE_BINDING_SCHEMA_ID,
        "envelope_version": PDB_CONECT_DECLARATION_ENVELOPE_VERSION,
        "parser_version": PDB_CONECT_DECLARATION_PARSER_VERSION,
        "profile_id": PDB_CONECT_DECLARATION_PROFILE_ID,
        "projection_scope": PDB_CONECT_DECLARATION_PROJECTION_SCOPE,
        "source_id_sha256": components.source_id_sha256,
        "full_source_sha256": _sha256_bytes(components.full_source),
        "normalized_source_sha256": _sha256_bytes(components.normalized_source),
        "carrier_source_sha256": _sha256_bytes(components.carrier_source),
        "canonical_carrier_source_sha256": _sha256_bytes(
            components.canonical_carrier_source
        ),
        "carrier_snapshot_sha256": components.carrier_snapshot_sha256,
        "carrier_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "carrier_topology_sha256": components.carrier_topology_sha256,
        "carrier_representable_state_schema_id": (PDB_REPRESENTABLE_STATE_SCHEMA_ID),
        "carrier_representable_state_sha256": (
            components.carrier_representable_state_sha256
        ),
        "carrier_coverage_sha256": _coverage_sha256(components),
        "carrier_missingness_report_sha256": (components.missingness_report_sha256),
        "base_writer_receipt_sha256": components.base_writer_receipt_sha256,
        "declaration_projection_sha256": _projection_sha256(components),
        "record_state_sha256": _sha256_document(_record_state_document(components)),
        "full_source_byte_count": len(components.full_source),
        "normalized_source_byte_count": len(components.normalized_source),
        "carrier_source_byte_count": len(components.carrier_source),
        "canonical_carrier_source_byte_count": len(components.canonical_carrier_source),
        "physical_line_upper_bound": components.physical_line_upper_bound,
        "conect_record_count": len(components.rows),
        "target_occurrence_count": sum(
            len(row.target_serials) for row in components.rows
        ),
        "declaration_projection_byte_count": len(projection_bytes),
        "line_ending_policy": "CRLF_normalized_to_LF_while_exact_full_source_is_bound",
        **_authority_false_document(),
    }


@dataclass(frozen=True, slots=True, init=False)
class PdbConectDeclarationIngestResult:
    """Factory-owned immutable binding for carrier plus ordered declarations."""

    _components: _ParsedComponents = field(repr=False)

    def __init__(
        self,
        components: _ParsedComponents | None = None,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("PdbConectDeclarationIngestResult is factory-only")
        if type(components) is not _ParsedComponents:
            raise TypeError("ingest requires exact parsed declaration components")
        fresh = _parse_components(
            components.full_source, source_id=components.source_id
        )
        if fresh != components:
            raise PdbConectDeclarationError(
                "stale_or_crosswired_ingest",
                "supplied declaration components differ from a fresh parse",
            )
        object.__setattr__(self, "_components", fresh)

    @property
    def system(self):
        """Return a detached copy of the unchanged bondless carrier system."""

        return deserialize_all_atom_system(self._components.carrier_snapshot)

    @property
    def coverage(self) -> StructureIngestCoverage:
        return self._components.coverage

    @property
    def carrier_ingest(self) -> StructureIngestResult:
        try:
            value = parse_pdb(
                self._components.carrier_source,
                source_id=self._components.source_id,
            )
        except StructureParseError as exc:  # pragma: no cover - guarded at factory
            raise PdbConectDeclarationError(
                "stale_or_crosswired_ingest",
                "stored carrier source no longer parses under the base contract",
            ) from exc
        if (
            serialize_all_atom_system(value.system) != self._components.carrier_snapshot
            or value.coverage != self._components.coverage
            or value.missingness_evidence.report_sha256
            != self._components.missingness_report_sha256
        ):
            raise PdbConectDeclarationError(
                "stale_or_crosswired_ingest",
                "stored carrier artifacts are not cross-consistent",
            )
        return value

    @property
    def base_ingest(self) -> StructureIngestResult:
        return self.carrier_ingest

    @property
    def conect_rows(self) -> tuple[PdbConectDeclarationRow, ...]:
        return self._components.rows

    @property
    def rows(self) -> tuple[PdbConectDeclarationRow, ...]:
        return self.conect_rows

    @property
    def source_id_sha256(self) -> str:
        return self._components.source_id_sha256

    @property
    def full_source_sha256(self) -> str:
        return _sha256_bytes(self._components.full_source)

    @property
    def normalized_source_sha256(self) -> str:
        return _sha256_bytes(self._components.normalized_source)

    @property
    def carrier_source_sha256(self) -> str:
        return _sha256_bytes(self._components.carrier_source)

    @property
    def canonical_carrier_source_sha256(self) -> str:
        return _sha256_bytes(self._components.canonical_carrier_source)

    @property
    def carrier_snapshot_sha256(self) -> str:
        return self._components.carrier_snapshot_sha256

    @property
    def carrier_topology_sha256(self) -> str:
        return self._components.carrier_topology_sha256

    @property
    def carrier_representable_state_sha256(self) -> str:
        return self._components.carrier_representable_state_sha256

    @property
    def declaration_projection_sha256(self) -> str:
        return _projection_sha256(self._components)

    @property
    def ordered_projection_sha256(self) -> str:
        return self.declaration_projection_sha256

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_document(_source_binding_document(self._components))

    @property
    def record_state_sha256(self) -> str:
        return _sha256_document(_record_state_document(self._components))

    @property
    def conect_record_count(self) -> int:
        return len(self._components.rows)

    @property
    def target_occurrence_count(self) -> int:
        return sum(len(row.target_serials) for row in self._components.rows)

    @property
    def declaration_projection_byte_count(self) -> int:
        return len(_canonical_json_bytes(_projection_document(self._components.rows)))

    def to_dict(self) -> dict[str, Any]:
        system = self.system
        return {
            "schema_id": PDB_CONECT_DECLARATION_RECORD_STATE_SCHEMA_ID,
            "envelope_version": PDB_CONECT_DECLARATION_ENVELOPE_VERSION,
            "parser_version": PDB_CONECT_DECLARATION_PARSER_VERSION,
            "writer_version": PDB_CONECT_DECLARATION_WRITER_VERSION,
            "parser_name": PDB_CONECT_DECLARATION_PARSER_NAME,
            "profile_id": PDB_CONECT_DECLARATION_PROFILE_ID,
            "projection_scope": PDB_CONECT_DECLARATION_PROJECTION_SCOPE,
            "base_parser_name": _BASE_PDB_PARSER_NAME,
            "base_parser_version": PDB_PARSER_VERSION,
            "base_parser_operations": list(_BASE_PDB_OPERATIONS),
            "base_writer_version": PDB_WRITER_VERSION,
            "source_id_sha256": self.source_id_sha256,
            "full_source_sha256": self.full_source_sha256,
            "normalized_source_sha256": self.normalized_source_sha256,
            "carrier_source_sha256": self.carrier_source_sha256,
            "canonical_carrier_source_sha256": (self.canonical_carrier_source_sha256),
            "carrier_snapshot_sha256": self.carrier_snapshot_sha256,
            "carrier_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
            "carrier_topology_sha256": self.carrier_topology_sha256,
            "carrier_representable_state_schema_id": (
                PDB_REPRESENTABLE_STATE_SCHEMA_ID
            ),
            "carrier_representable_state_sha256": (
                self.carrier_representable_state_sha256
            ),
            "declaration_projection_schema_id": (
                PDB_CONECT_DECLARATION_PROJECTION_SCHEMA_ID
            ),
            "declaration_projection_sha256": self.declaration_projection_sha256,
            "source_binding_schema_id": (
                PDB_CONECT_DECLARATION_SOURCE_BINDING_SCHEMA_ID
            ),
            "source_binding_sha256": self.source_binding_sha256,
            "record_state_sha256": self.record_state_sha256,
            "base_writer_receipt_sha256": (self._components.base_writer_receipt_sha256),
            "carrier_atom_count": system.atom_count,
            "carrier_bond_count": len(system.bonds),
            "carrier_model_count": system.model_count,
            "carrier_model_ids": [1],
            "conect_record_count": self.conect_record_count,
            "target_occurrence_count": self.target_occurrence_count,
            "declaration_projection_byte_count": (
                self.declaration_projection_byte_count
            ),
            "ordered_declaration_projection_preserved": True,
            **_authority_false_document(),
            "blockers": list(_NON_PROMOTION_BLOCKERS),
        }


def _validate_fresh_ingest(
    value: PdbConectDeclarationIngestResult,
) -> _ParsedComponents:
    if type(value) is not PdbConectDeclarationIngestResult:
        raise TypeError("declaration emission requires an exact ingest result")
    stored = value._components
    fresh = _parse_components(stored.full_source, source_id=stored.source_id)
    if fresh != stored:
        raise PdbConectDeclarationError(
            "stale_or_crosswired_ingest",
            "stored declaration ingest evidence differs from a fresh parse",
        )
    return fresh


def parse_pdb_conect_declaration(
    data: bytes, *, source_id: str = ""
) -> PdbConectDeclarationIngestResult:
    """Parse a bondless strict-PDB carrier plus ordered ``CONECT`` rows."""

    components = _parse_components(data, source_id=source_id)
    return PdbConectDeclarationIngestResult(components, _factory_token=_FACTORY_TOKEN)


def pdb_conect_declaration_projection_sha256(
    value: PdbConectDeclarationIngestResult,
) -> str:
    return _projection_sha256(_validate_fresh_ingest(value))


def pdb_conect_declaration_source_binding_sha256(
    value: PdbConectDeclarationIngestResult,
) -> str:
    return _sha256_document(_source_binding_document(_validate_fresh_ingest(value)))


def pdb_conect_declaration_record_state_sha256(
    value: PdbConectDeclarationIngestResult,
) -> str:
    return _sha256_document(_record_state_document(_validate_fresh_ingest(value)))


def _conect_output_line(row: PdbConectDeclarationRow) -> bytes:
    line = (
        "CONECT"
        + f"{row.source_serial:5d}"
        + "".join(f"{target:5d}" for target in row.target_serials)
    )
    line = line.ljust(MAX_PDB_CONECT_DECLARATION_OUTPUT_LINE_CHARS)
    if len(line) != MAX_PDB_CONECT_DECLARATION_OUTPUT_LINE_CHARS:
        raise PdbConectDeclarationError(
            "base_writer_contract_drift",
            "validated declaration did not emit one 80-column row",
        )
    return line.encode("ascii")


def _compose_output(components: _ParsedComponents) -> bytes:
    base_lines = components.canonical_carrier_source.splitlines()
    canonical_end = b"END".ljust(MAX_PDB_CONECT_DECLARATION_OUTPUT_LINE_CHARS)
    if not base_lines or base_lines[-1] != canonical_end:
        raise PdbConectDeclarationError(
            "base_writer_contract_drift",
            "base writer no longer emits one canonical final END row",
        )
    if any(
        len(line) != MAX_PDB_CONECT_DECLARATION_OUTPUT_LINE_CHARS for line in base_lines
    ):
        raise PdbConectDeclarationError(
            "base_writer_contract_drift",
            "base writer emitted a non-80-column carrier row",
        )
    lines = [
        *base_lines[:-1],
        *(_conect_output_line(row) for row in components.rows),
        canonical_end,
    ]
    if len(lines) + 1 > MAX_PDB_CONECT_DECLARATION_OUTPUT_LINES:
        raise PdbConectDeclarationError(
            "output_too_many_lines",
            "canonical declaration output exceeds the inherited line limit",
        )
    payload = b"\n".join(lines) + b"\n"
    if len(payload) > MAX_PDB_CONECT_DECLARATION_OUTPUT_BYTES:
        raise PdbConectDeclarationError(
            "output_too_large",
            "canonical declaration output exceeds the inherited byte limit",
        )
    return payload


def _receipt_document(components: _ParsedComponents, payload: bytes) -> dict[str, Any]:
    record_state = _record_state_document(components)
    return {
        "schema_id": PDB_CONECT_DECLARATION_WRITE_RECEIPT_SCHEMA_ID,
        "envelope_version": PDB_CONECT_DECLARATION_ENVELOPE_VERSION,
        "parser_version": PDB_CONECT_DECLARATION_PARSER_VERSION,
        "writer_version": PDB_CONECT_DECLARATION_WRITER_VERSION,
        "parser_name": PDB_CONECT_DECLARATION_PARSER_NAME,
        "profile_id": PDB_CONECT_DECLARATION_PROFILE_ID,
        "projection_scope": PDB_CONECT_DECLARATION_PROJECTION_SCOPE,
        "base_parser_name": _BASE_PDB_PARSER_NAME,
        "base_parser_version": PDB_PARSER_VERSION,
        "base_parser_operations": list(_BASE_PDB_OPERATIONS),
        "base_writer_version": PDB_WRITER_VERSION,
        "input_source_binding_schema_id": (
            PDB_CONECT_DECLARATION_SOURCE_BINDING_SCHEMA_ID
        ),
        "input_source_binding_sha256": _sha256_document(
            _source_binding_document(components)
        ),
        "input_full_source_sha256": _sha256_bytes(components.full_source),
        "input_normalized_source_sha256": _sha256_bytes(components.normalized_source),
        "input_carrier_source_sha256": _sha256_bytes(components.carrier_source),
        "input_canonical_carrier_source_sha256": _sha256_bytes(
            components.canonical_carrier_source
        ),
        "input_carrier_snapshot_sha256": components.carrier_snapshot_sha256,
        "input_carrier_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "input_carrier_topology_sha256": components.carrier_topology_sha256,
        "input_carrier_representable_state_schema_id": (
            PDB_REPRESENTABLE_STATE_SCHEMA_ID
        ),
        "input_carrier_representable_state_sha256": (
            components.carrier_representable_state_sha256
        ),
        "input_declaration_projection_schema_id": (
            PDB_CONECT_DECLARATION_PROJECTION_SCHEMA_ID
        ),
        "input_declaration_projection_sha256": _projection_sha256(components),
        "input_record_state_schema_id": (PDB_CONECT_DECLARATION_RECORD_STATE_SCHEMA_ID),
        "input_record_state_sha256": _sha256_document(record_state),
        "base_writer_receipt_sha256": components.base_writer_receipt_sha256,
        "source_id_sha256": components.source_id_sha256,
        "output_source_sha256": _sha256_bytes(payload),
        "output_byte_count": len(payload),
        "carrier_atom_count": components.coverage.atom_count,
        "carrier_bond_count": 0,
        "carrier_model_count": 1,
        "carrier_model_ids": [1],
        "conect_record_count": len(components.rows),
        "target_occurrence_count": sum(
            len(row.target_serials) for row in components.rows
        ),
        "ordered_declaration_projection_preserved": True,
        **_authority_false_document(),
        "blockers": list(_NON_PROMOTION_BLOCKERS),
    }


@dataclass(frozen=True, slots=True, init=False)
class PdbConectDeclarationWriteReceipt:
    _document_bytes: bytes = field(repr=False)

    def __init__(
        self,
        document: Mapping[str, Any] | None = None,
        *,
        components: _ParsedComponents | None = None,
        payload: bytes | None = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("PdbConectDeclarationWriteReceipt is factory-only")
        if type(components) is not _ParsedComponents or type(payload) is not bytes:
            raise TypeError(
                "write receipt requires exact parsed components and payload"
            )
        fresh = _parse_components(
            components.full_source, source_id=components.source_id
        )
        if fresh != components:
            raise PdbConectDeclarationError(
                "stale_or_crosswired_receipt",
                "write receipt components differ from a fresh parse",
            )
        canonical_payload = _compose_output(fresh)
        if payload != canonical_payload:
            raise PdbConectDeclarationError(
                "invalid_write_payload",
                "write receipt payload differs from the canonical declaration emission",
            )
        reparsed = _parse_components(payload, source_id=fresh.source_id)
        if _record_state_document(reparsed) != _record_state_document(fresh):
            raise PdbConectDeclarationError(
                "round_trip_mismatch",
                "write receipt payload does not recover the input record state",
            )
        expected = _receipt_document(fresh, payload)
        if document is None or _plain(document) != expected:
            raise PdbConectDeclarationError(
                "invalid_write_receipt",
                "write receipt document differs from the exact artifact binding",
            )
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(expected))

    @property
    def receipt_sha256(self) -> str:
        return _sha256_bytes(self._document_bytes)

    def to_dict(self) -> dict[str, Any]:
        document = json.loads(self._document_bytes.decode("ascii"))
        document["receipt_sha256"] = self.receipt_sha256
        return document


@dataclass(frozen=True, slots=True, init=False)
class PdbConectDeclarationWriteResult:
    payload: bytes = field(repr=False)
    receipt: PdbConectDeclarationWriteReceipt

    def __init__(
        self,
        payload: bytes | None = None,
        receipt: PdbConectDeclarationWriteReceipt | None = None,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("PdbConectDeclarationWriteResult is factory-only")
        if (
            type(payload) is not bytes
            or type(receipt) is not PdbConectDeclarationWriteReceipt
        ):
            raise TypeError("invalid declaration write artifacts")
        receipt_document = receipt.to_dict()
        if receipt_document["output_byte_count"] != len(payload) or receipt_document[
            "output_source_sha256"
        ] != _sha256_bytes(payload):
            raise PdbConectDeclarationError(
                "invalid_write_artifacts", "write receipt does not bind its payload"
            )
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "receipt", receipt)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_source_sha256": _sha256_bytes(self.payload),
            "output_byte_count": len(self.payload),
            "receipt": self.receipt.to_dict(),
            **_authority_false_document(),
        }


def write_pdb_conect_declaration(
    value: PdbConectDeclarationIngestResult,
) -> PdbConectDeclarationWriteResult:
    """Emit canonical carrier bytes followed by exact ordered declarations."""

    components = _validate_fresh_ingest(value)
    payload = _compose_output(components)
    reparsed = _parse_components(payload, source_id=components.source_id)
    if _record_state_document(reparsed) != _record_state_document(components):
        raise PdbConectDeclarationError(
            "round_trip_mismatch",
            "emitted declaration does not recover the declared record state",
        )
    receipt = PdbConectDeclarationWriteReceipt(
        _receipt_document(components, payload),
        components=components,
        payload=payload,
        _factory_token=_FACTORY_TOKEN,
    )
    return PdbConectDeclarationWriteResult(
        payload, receipt, _factory_token=_FACTORY_TOKEN
    )


def serialize_pdb_conect_declaration(
    value: PdbConectDeclarationIngestResult,
) -> bytes:
    """Return deterministic bytes for the checked declaration envelope."""

    return write_pdb_conect_declaration(value).payload


def _receipt_exactly_binds(
    write_result: PdbConectDeclarationWriteResult,
    ingest: PdbConectDeclarationIngestResult,
) -> bool:
    receipt = write_result.receipt.to_dict()
    receipt.pop("receipt_sha256", None)
    return receipt == _receipt_document(ingest._components, write_result.payload)


def _report_document(
    source: PdbConectDeclarationIngestResult,
    reparsed: PdbConectDeclarationIngestResult,
    write_result: PdbConectDeclarationWriteResult,
    second: PdbConectDeclarationWriteResult,
) -> dict[str, Any]:
    projection_equal = (
        source.declaration_projection_sha256 == reparsed.declaration_projection_sha256
    )
    topology_equal = source.carrier_topology_sha256 == reparsed.carrier_topology_sha256
    carrier_state_equal = (
        source.carrier_representable_state_sha256
        == reparsed.carrier_representable_state_sha256
    )
    canonical_carrier_equal = (
        source.canonical_carrier_source_sha256
        == reparsed.canonical_carrier_source_sha256
    )
    record_state_equal = source.record_state_sha256 == reparsed.record_state_sha256
    source_id_equal = source.source_id_sha256 == reparsed.source_id_sha256
    emitted_source_reparsed_exact = (
        _sha256_bytes(write_result.payload) == reparsed.full_source_sha256
    )
    write_receipt_source_bound = _receipt_exactly_binds(write_result, source)
    reemitted_receipt_reparsed_bound = _receipt_exactly_binds(second, reparsed)
    second_emission_stable = write_result.payload == second.payload
    carrier_bond_count_zero = (
        len(source.system.bonds) == 0
        and source.coverage.bond_count == 0
        and len(reparsed.system.bonds) == 0
        and reparsed.coverage.bond_count == 0
    )
    preserved = all(
        (
            projection_equal,
            topology_equal,
            carrier_state_equal,
            canonical_carrier_equal,
            record_state_equal,
            source_id_equal,
            emitted_source_reparsed_exact,
            write_receipt_source_bound,
            reemitted_receipt_reparsed_bound,
            second_emission_stable,
            carrier_bond_count_zero,
        )
    )
    return {
        "schema_id": PDB_CONECT_DECLARATION_ROUND_TRIP_REPORT_SCHEMA_ID,
        "envelope_version": PDB_CONECT_DECLARATION_ENVELOPE_VERSION,
        "parser_version": PDB_CONECT_DECLARATION_PARSER_VERSION,
        "writer_version": PDB_CONECT_DECLARATION_WRITER_VERSION,
        "parser_name": PDB_CONECT_DECLARATION_PARSER_NAME,
        "profile_id": PDB_CONECT_DECLARATION_PROFILE_ID,
        "projection_scope": PDB_CONECT_DECLARATION_PROJECTION_SCOPE,
        "base_parser_name": _BASE_PDB_PARSER_NAME,
        "base_parser_version": PDB_PARSER_VERSION,
        "base_parser_operations": list(_BASE_PDB_OPERATIONS),
        "base_writer_version": PDB_WRITER_VERSION,
        "source_id_sha256": source.source_id_sha256,
        "input_source_binding_sha256": source.source_binding_sha256,
        "input_full_source_sha256": source.full_source_sha256,
        "input_carrier_source_sha256": source.carrier_source_sha256,
        "input_canonical_carrier_source_sha256": (
            source.canonical_carrier_source_sha256
        ),
        "input_carrier_snapshot_sha256": source.carrier_snapshot_sha256,
        "input_carrier_topology_sha256": source.carrier_topology_sha256,
        "input_carrier_representable_state_sha256": (
            source.carrier_representable_state_sha256
        ),
        "input_base_writer_receipt_sha256": (
            source._components.base_writer_receipt_sha256
        ),
        "input_declaration_projection_sha256": (source.declaration_projection_sha256),
        "input_record_state_sha256": source.record_state_sha256,
        "write_receipt_sha256": write_result.receipt.receipt_sha256,
        "emitted_source_sha256": _sha256_bytes(write_result.payload),
        "reparsed_source_binding_sha256": reparsed.source_binding_sha256,
        "reparsed_full_source_sha256": reparsed.full_source_sha256,
        "reparsed_carrier_source_sha256": reparsed.carrier_source_sha256,
        "reparsed_canonical_carrier_source_sha256": (
            reparsed.canonical_carrier_source_sha256
        ),
        "reparsed_carrier_snapshot_sha256": reparsed.carrier_snapshot_sha256,
        "reparsed_carrier_topology_sha256": reparsed.carrier_topology_sha256,
        "reparsed_carrier_representable_state_sha256": (
            reparsed.carrier_representable_state_sha256
        ),
        "reparsed_base_writer_receipt_sha256": (
            reparsed._components.base_writer_receipt_sha256
        ),
        "reparsed_declaration_projection_sha256": (
            reparsed.declaration_projection_sha256
        ),
        "reparsed_record_state_sha256": reparsed.record_state_sha256,
        "reemitted_write_receipt_sha256": second.receipt.receipt_sha256,
        "reemitted_source_sha256": _sha256_bytes(second.payload),
        "declaration_projection_equal": projection_equal,
        "carrier_topology_equal": topology_equal,
        "carrier_representable_state_equal": carrier_state_equal,
        "canonical_carrier_source_equal": canonical_carrier_equal,
        "record_state_equal": record_state_equal,
        "source_id_equal": source_id_equal,
        "emitted_source_reparsed_exact": emitted_source_reparsed_exact,
        "write_receipt_source_bound": write_receipt_source_bound,
        "reemitted_receipt_reparsed_bound": reemitted_receipt_reparsed_bound,
        "second_emission_byte_stable": second_emission_stable,
        "carrier_bond_count_zero": carrier_bond_count_zero,
        "ordered_conect_declaration_round_trip_preserved": preserved,
        **_authority_false_document(),
        "blockers": list(_NON_PROMOTION_BLOCKERS),
    }


@dataclass(frozen=True, slots=True, init=False)
class PdbConectDeclarationRoundTripReport:
    _document_bytes: bytes = field(repr=False)

    def __init__(
        self,
        document: Mapping[str, Any] | None = None,
        *,
        source: PdbConectDeclarationIngestResult | None = None,
        reparsed: PdbConectDeclarationIngestResult | None = None,
        write_result: PdbConectDeclarationWriteResult | None = None,
        reemitted_write_result: PdbConectDeclarationWriteResult | None = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("PdbConectDeclarationRoundTripReport is factory-only")
        if not all(
            (
                type(source) is PdbConectDeclarationIngestResult,
                type(reparsed) is PdbConectDeclarationIngestResult,
                type(write_result) is PdbConectDeclarationWriteResult,
                type(reemitted_write_result) is PdbConectDeclarationWriteResult,
            )
        ):
            raise TypeError("round-trip report requires exact bound artifacts")
        expected = _report_document(
            source, reparsed, write_result, reemitted_write_result
        )
        if (
            document is None
            or _plain(document) != expected
            or expected["ordered_conect_declaration_round_trip_preserved"] is not True
        ):
            raise PdbConectDeclarationError(
                "crosswired_round_trip_artifacts",
                "round-trip report does not prove the exact artifact chain",
            )
        object.__setattr__(self, "_document_bytes", _canonical_json_bytes(expected))

    @property
    def report_sha256(self) -> str:
        return _sha256_bytes(self._document_bytes)

    def to_dict(self) -> dict[str, Any]:
        document = json.loads(self._document_bytes.decode("ascii"))
        document["report_sha256"] = self.report_sha256
        return document


def _component_binding_document(components: _ParsedComponents) -> dict[str, Any]:
    return {
        "full_source_sha256": _sha256_bytes(components.full_source),
        "full_source_byte_count": len(components.full_source),
        "normalized_source_sha256": _sha256_bytes(components.normalized_source),
        "normalized_source_byte_count": len(components.normalized_source),
        "carrier_source_sha256": _sha256_bytes(components.carrier_source),
        "carrier_source_byte_count": len(components.carrier_source),
        "canonical_carrier_source_sha256": _sha256_bytes(
            components.canonical_carrier_source
        ),
        "canonical_carrier_source_byte_count": len(components.canonical_carrier_source),
        "carrier_snapshot_payload_sha256": _sha256_bytes(components.carrier_snapshot),
        "carrier_snapshot_byte_count": len(components.carrier_snapshot),
        "source_id_utf8_sha256": _sha256_bytes(components.source_id.encode("utf-8")),
        "source_id_sha256": components.source_id_sha256,
        "declaration_projection": _projection_document(components.rows),
        "coverage": components.coverage.to_dict(),
        "missingness_report_sha256": components.missingness_report_sha256,
        "carrier_snapshot_sha256": components.carrier_snapshot_sha256,
        "carrier_topology_sha256": components.carrier_topology_sha256,
        "carrier_representable_state_sha256": (
            components.carrier_representable_state_sha256
        ),
        "base_writer_receipt_sha256": components.base_writer_receipt_sha256,
        "physical_line_upper_bound": components.physical_line_upper_bound,
    }


def _aggregate_chain_binding_document(
    source_ingest: PdbConectDeclarationIngestResult,
    write_result: PdbConectDeclarationWriteResult,
    reparsed_ingest: PdbConectDeclarationIngestResult,
    reemitted_write_result: PdbConectDeclarationWriteResult,
    report: PdbConectDeclarationRoundTripReport,
) -> dict[str, Any]:
    return {
        "source_components": _component_binding_document(source_ingest._components),
        "write_payload_sha256": _sha256_bytes(write_result.payload),
        "write_payload_byte_count": len(write_result.payload),
        "write_receipt": write_result.receipt.to_dict(),
        "reparsed_components": _component_binding_document(reparsed_ingest._components),
        "reemitted_payload_sha256": _sha256_bytes(reemitted_write_result.payload),
        "reemitted_payload_byte_count": len(reemitted_write_result.payload),
        "reemitted_receipt": reemitted_write_result.receipt.to_dict(),
        "report": report.to_dict(),
    }


@dataclass(frozen=True, slots=True, init=False)
class PdbConectDeclarationRoundTripResult:
    _source_ingest: PdbConectDeclarationIngestResult = field(repr=False)
    _write_result: PdbConectDeclarationWriteResult = field(repr=False)
    _reparsed_ingest: PdbConectDeclarationIngestResult = field(repr=False)
    _reemitted_write_result: PdbConectDeclarationWriteResult = field(repr=False)
    _report: PdbConectDeclarationRoundTripReport = field(repr=False)
    _chain_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        source_ingest: PdbConectDeclarationIngestResult | None = None,
        write_result: PdbConectDeclarationWriteResult | None = None,
        reparsed_ingest: PdbConectDeclarationIngestResult | None = None,
        reemitted_write_result: PdbConectDeclarationWriteResult | None = None,
        report: PdbConectDeclarationRoundTripReport | None = None,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("PdbConectDeclarationRoundTripResult is factory-only")
        if not all(
            (
                type(source_ingest) is PdbConectDeclarationIngestResult,
                type(write_result) is PdbConectDeclarationWriteResult,
                type(reparsed_ingest) is PdbConectDeclarationIngestResult,
                type(reemitted_write_result) is PdbConectDeclarationWriteResult,
                type(report) is PdbConectDeclarationRoundTripReport,
            )
        ):
            raise TypeError("invalid declaration round-trip artifacts")
        _validate_fresh_ingest(source_ingest)
        _validate_fresh_ingest(reparsed_ingest)
        expected_source_write = write_pdb_conect_declaration(source_ingest)
        expected_reparsed_write = write_pdb_conect_declaration(reparsed_ingest)
        if (
            expected_source_write.payload != write_result.payload
            or expected_source_write.receipt.to_dict() != write_result.receipt.to_dict()
            or expected_reparsed_write.payload != reemitted_write_result.payload
            or expected_reparsed_write.receipt.to_dict()
            != reemitted_write_result.receipt.to_dict()
            or reparsed_ingest._components.full_source != write_result.payload
        ):
            raise PdbConectDeclarationError(
                "crosswired_round_trip_artifacts",
                "round-trip aggregate inputs do not match fresh source emissions",
            )
        expected = _report_document(
            source_ingest,
            reparsed_ingest,
            write_result,
            reemitted_write_result,
        )
        if report.to_dict() != {
            **expected,
            "report_sha256": _sha256_document(expected),
        }:
            raise PdbConectDeclarationError(
                "crosswired_round_trip_artifacts",
                "round-trip report does not bind the supplied artifacts",
            )
        if expected["ordered_conect_declaration_round_trip_preserved"] is not True:
            raise PdbConectDeclarationError(
                "crosswired_round_trip_artifacts",
                "round-trip artifacts do not form an exact preservation chain",
            )
        chain_binding_bytes = _canonical_json_bytes(
            _aggregate_chain_binding_document(
                source_ingest,
                write_result,
                reparsed_ingest,
                reemitted_write_result,
                report,
            )
        )
        object.__setattr__(self, "_source_ingest", source_ingest)
        object.__setattr__(self, "_write_result", write_result)
        object.__setattr__(self, "_reparsed_ingest", reparsed_ingest)
        object.__setattr__(self, "_reemitted_write_result", reemitted_write_result)
        object.__setattr__(self, "_report", report)
        object.__setattr__(self, "_chain_binding_bytes", chain_binding_bytes)

    def _validate_chain(self) -> None:
        try:
            if not all(
                (
                    type(self._source_ingest) is PdbConectDeclarationIngestResult,
                    type(self._write_result) is PdbConectDeclarationWriteResult,
                    type(self._reparsed_ingest) is PdbConectDeclarationIngestResult,
                    type(self._reemitted_write_result)
                    is PdbConectDeclarationWriteResult,
                    type(self._report) is PdbConectDeclarationRoundTripReport,
                    type(self._chain_binding_bytes) is bytes,
                )
            ):
                raise TypeError("aggregate contains invalid nested artifact types")
            current_binding = _canonical_json_bytes(
                _aggregate_chain_binding_document(
                    self._source_ingest,
                    self._write_result,
                    self._reparsed_ingest,
                    self._reemitted_write_result,
                    self._report,
                )
            )
            expected_report = _report_document(
                self._source_ingest,
                self._reparsed_ingest,
                self._write_result,
                self._reemitted_write_result,
            )
            report_matches = self._report.to_dict() == {
                **expected_report,
                "report_sha256": _sha256_document(expected_report),
            }
            if (
                current_binding != self._chain_binding_bytes
                or not report_matches
                or expected_report["ordered_conect_declaration_round_trip_preserved"]
                is not True
            ):
                raise ValueError("aggregate chain binding changed")
        except Exception as exc:
            raise PdbConectDeclarationError(
                "crosswired_round_trip_artifacts",
                "stored round-trip aggregate artifacts are stale or cross-wired",
            ) from exc

    @property
    def source_ingest(self) -> PdbConectDeclarationIngestResult:
        self._validate_chain()
        return self._source_ingest

    @property
    def write_result(self) -> PdbConectDeclarationWriteResult:
        self._validate_chain()
        return self._write_result

    @property
    def reparsed_ingest(self) -> PdbConectDeclarationIngestResult:
        self._validate_chain()
        return self._reparsed_ingest

    @property
    def reemitted_write_result(self) -> PdbConectDeclarationWriteResult:
        self._validate_chain()
        return self._reemitted_write_result

    @property
    def report(self) -> PdbConectDeclarationRoundTripReport:
        self._validate_chain()
        return self._report

    def to_dict(self) -> dict[str, Any]:
        self._validate_chain()
        return {
            "source_ingest": self._source_ingest.to_dict(),
            "write_result": self._write_result.to_dict(),
            "reparsed_ingest": self._reparsed_ingest.to_dict(),
            "reemitted_write_result": self._reemitted_write_result.to_dict(),
            "report": self._report.to_dict(),
            **_authority_false_document(),
        }


def round_trip_pdb_conect_declaration_source(
    data: bytes, *, source_id: str = ""
) -> PdbConectDeclarationRoundTripResult:
    """Verify ordered declaration and carrier-state deterministic re-emission."""

    source = parse_pdb_conect_declaration(data, source_id=source_id)
    write_result = write_pdb_conect_declaration(source)
    reparsed = parse_pdb_conect_declaration(write_result.payload, source_id=source_id)
    second = write_pdb_conect_declaration(reparsed)
    report_document = _report_document(source, reparsed, write_result, second)
    if not report_document["ordered_conect_declaration_round_trip_preserved"]:
        raise PdbConectDeclarationError(
            "round_trip_mismatch",
            "ordered CONECT declaration projection failed round-trip validation",
        )
    report = PdbConectDeclarationRoundTripReport(
        report_document,
        source=source,
        reparsed=reparsed,
        write_result=write_result,
        reemitted_write_result=second,
        _factory_token=_FACTORY_TOKEN,
    )
    return PdbConectDeclarationRoundTripResult(
        source,
        write_result,
        reparsed,
        second,
        report,
        _factory_token=_FACTORY_TOKEN,
    )


__all__ = [
    "MAX_PDB_CONECT_DECLARATION_INPUT_BYTES",
    "MAX_PDB_CONECT_DECLARATION_LINE_COUNT",
    "MAX_PDB_CONECT_DECLARATION_OUTPUT_BYTES",
    "MAX_PDB_CONECT_DECLARATION_OUTPUT_LINE_CHARS",
    "MAX_PDB_CONECT_DECLARATION_OUTPUT_LINES",
    "MAX_PDB_CONECT_DECLARATION_PROJECTION_BYTES",
    "MAX_PDB_CONECT_DECLARATION_RECORDS",
    "MAX_PDB_CONECT_DECLARATION_SOURCE_ID_BYTES",
    "MAX_PDB_CONECT_DECLARATION_TARGET_OCCURRENCES",
    "PDB_CONECT_DECLARATION_ENVELOPE_VERSION",
    "PDB_CONECT_DECLARATION_PARSER_NAME",
    "PDB_CONECT_DECLARATION_PARSER_VERSION",
    "PDB_CONECT_DECLARATION_PROFILE_ID",
    "PDB_CONECT_DECLARATION_PROJECTION_SCHEMA_ID",
    "PDB_CONECT_DECLARATION_PROJECTION_SCOPE",
    "PDB_CONECT_DECLARATION_RECORD_STATE_SCHEMA_ID",
    "PDB_CONECT_DECLARATION_ROUND_TRIP_REPORT_SCHEMA_ID",
    "PDB_CONECT_DECLARATION_SOURCE_BINDING_SCHEMA_ID",
    "PDB_CONECT_DECLARATION_WRITER_VERSION",
    "PDB_CONECT_DECLARATION_WRITE_RECEIPT_SCHEMA_ID",
    "PdbConectDeclarationError",
    "PdbConectDeclarationIngestResult",
    "PdbConectDeclarationRoundTripReport",
    "PdbConectDeclarationRoundTripResult",
    "PdbConectDeclarationRow",
    "PdbConectDeclarationWriteReceipt",
    "PdbConectDeclarationWriteResult",
    "parse_pdb_conect_declaration",
    "pdb_conect_declaration_projection_sha256",
    "pdb_conect_declaration_record_state_sha256",
    "pdb_conect_declaration_source_binding_sha256",
    "round_trip_pdb_conect_declaration_source",
    "serialize_pdb_conect_declaration",
    "write_pdb_conect_declaration",
]
