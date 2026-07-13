"""Deterministic writer for the exactly representable strict PDB subset.

This is deliberately not a general PDB exporter.  It accepts the bondless,
no-altloc parser-owned state produced by the current strict PDB reader, with an
optional exactly representable parser-owned ``CRYST1`` record.  A narrow
single-model/model-ID-1 profile also normalizes typed source-reported REMARK
465/470 claims through a source-independent semantic projection.  The writer
fails closed whenever emitting fixed-column PDB would discard, round, or
reinterpret state inside that declared projection.

Round-trip equality is a versioned representable-state projection.  Dynamic
raw-source provenance, parser-observation digests, resource layout, source and
system identifiers, and the complete canonical snapshot are bound by receipts
but are not claimed to remain equal after emitted bytes are reparsed.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import math
import re
import struct
from typing import Any, Mapping

import torch

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID

from .missingness import (
    MAX_MISSING_ATOM_CLAIMS,
    MAX_MISSING_RESIDUE_CLAIMS,
    MAX_TOTAL_MISSINGNESS_CLAIMS,
    MISSINGNESS_PRESERVATION_POLICY_ID,
    MISSINGNESS_REPORT_SCHEMA_ID,
    SourceReportedMissingAtomClaim,
    SourceReportedMissingResidueClaim,
    SourceReportedMissingnessReport,
)
from .models import AllAtomSystem, UnitCell, atomic_number_for_element
from .observation import (
    PARSER_OBSERVATION_SCHEMA_ID,
    attached_parser_observation_sha256_matches,
)
from .pdb_mmcif import (
    PDB_PARSER_VERSION,
    STRUCTURE_INGEST_SUPPORT_SCOPE,
    StructureIngestCoverage,
    StructureIngestResult,
    parse_pdb,
)
from .serialization import (
    canonical_all_atom_snapshot_digest,
    deserialize_all_atom_system,
    serialize_all_atom_system,
)
from .topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    attached_canonical_topology_sha256_matches,
    canonical_topology_sha256,
)
from .validation import MolecularValidationError, require_valid_all_atom_system


PDB_WRITER_VERSION = "1.2.0"
PDB_REPRESENTABLE_STATE_SCHEMA_ID = "betelgeuze.pdb_representable_state/1.2.0"
PDB_WRITE_RECEIPT_SCHEMA_ID = "betelgeuze.pdb_write_receipt/1.2.0"
PDB_ROUND_TRIP_REPORT_SCHEMA_ID = "betelgeuze.pdb_round_trip_report/1.2.0"
PDB_MISSINGNESS_SEMANTIC_SCHEMA_ID = (
    "betelgeuze.pdb_source_reported_missingness_semantic_projection/1.0.0"
)
PDB_MISSINGNESS_PROFILE_ID = (
    "single_model_id1_source_reported_remark_465_470_semantic_roundtrip/1.0.0"
)

_PDB_PARSER_NAME = "betelgeuze_engine_v2.molecular.pdb_mmcif.parse_pdb"
_MAX_OUTPUT_BYTES = 64 * 1024 * 1024
_MAX_ATOM_ROWS = 80_000
_MAX_OUTPUT_LINES = 250_000
_MAX_MISSINGNESS_REMARK_LINES = 20_000
_MAX_MISSINGNESS_PROJECTED_CLAIMS = 25_000
_MAX_LINE_CHARS = 80
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_PARSER_OPERATIONS = (
    "parse_strict_fixed_column_pdb",
    "preserve_source_atom_order",
)
_PARSER_OPERATIONS_WITH_MISSINGNESS = (
    "parse_strict_fixed_column_pdb",
    "preserve_source_reported_missingness_without_completion/v1",
    "preserve_source_atom_order",
)
_COVERAGE_BASE_BLOCKERS = (
    "bond_topology_incomplete_or_unverified",
    "biological_assembly_not_applied",
    "missing_atom_and_residue_completion_not_assessed",
    "hydrogen_and_protonation_not_assessed",
    "stereochemistry_not_assessed",
    "modified_residue_cofactor_and_parameterability_not_assessed",
)
_ATOM_METADATA_KEYS = frozenset(
    {
        "source_record",
        "pdb_atom_name_field",
        "pdb_altloc",
        "pdb_segment_id",
        "formal_charge_known",
        "formal_charge_source",
        "formal_charge_interpretation",
        "hydrogen_origin",
    }
)
_RESIDUE_METADATA_KEYS = frozenset(
    {
        "source_record",
        "entity_id",
        "source_residue_namespace",
        "entity_type_basis",
        "pdb_segment_id",
    }
)
_CHAIN_METADATA_KEYS = frozenset({"source_format", "auth_asym_ids"})
_PROVENANCE_METADATA_KEYS = frozenset(
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
_PDB_METADATA_KEYS = frozenset(
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
_CRYST1_METADATA_KEYS = frozenset(
    {"lengths_angstrom", "angles_degrees", "space_group", "z"}
)
_TER_RECORD_KEYS = frozenset(
    {
        "serial",
        "residue_name",
        "chain_id",
        "residue_number",
        "insertion_code",
        "after_atom_index",
        "after_atom_serial",
        "line_number",
    }
)
_RESOURCE_USAGE_KEYS = frozenset(
    {
        "input_bytes",
        "atom_rows",
        "physical_line_upper_bound",
        "missingness_remark_lines",
        "missing_residue_claims",
        "missing_atom_claims",
        "total_missingness_claims",
    }
)
_SOURCE_MISSINGNESS_KEYS = frozenset(
    {
        "interpretation_policy",
        "remark_line_count",
        "remark_465_line_count",
        "remark_470_line_count",
        "raw_records",
    }
)
_RAW_MISSINGNESS_RECORD_KEYS = frozenset({"remark_number", "line_number", "raw_line"})
_MISSINGNESS_REPORT_KEYS = frozenset(
    {
        "schema_id",
        "policy_id",
        "source_format",
        "source_sha256",
        "canonical_topology_schema_id",
        "canonical_topology_sha256",
        "coordinate_scope",
        "altloc_status",
        "requested_altloc_id",
        "assembly_status",
        "requested_assembly_id",
        "missing_residue_claims",
        "missing_atom_claims",
        "source_reported_missing_residue_count",
        "source_reported_missing_atom_count",
        "blockers",
        "completion_attempted",
        "completion_applied",
        "preparation_ready",
        "claim_safe",
        "report_sha256",
    }
)
_MISSING_RESIDUE_CLAIM_KEYS = frozenset(
    {
        "source_ordinal",
        "source_category",
        "source_model_id",
        "source_chain_id",
        "source_residue_id",
        "source_residue_name",
        "source_insertion_code",
        "raw_payload",
    }
)
_MISSING_ATOM_CLAIM_KEYS = frozenset(
    {
        "source_ordinal",
        "source_category",
        "source_model_id",
        "source_chain_id",
        "source_residue_id",
        "source_residue_name",
        "source_insertion_code",
        "source_atom_name",
        "source_altloc_id",
        "raw_payload",
    }
)
_MISSING_RESIDUE_RAW_PAYLOAD_KEYS = frozenset(
    {"line_number", "raw_line", "model_field", "target_model_scope"}
)
_MISSING_ATOM_RAW_PAYLOAD_KEYS = frozenset(
    {
        "line_number",
        "raw_line",
        "atom_position_in_row",
        "model_field",
        "target_model_scope",
    }
)
_RESOURCE_LIMITS = {
    "input_bytes": _MAX_OUTPUT_BYTES,
    "atom_rows": _MAX_ATOM_ROWS,
    "physical_lines": _MAX_OUTPUT_LINES,
    "missingness_remark_lines": _MAX_MISSINGNESS_REMARK_LINES,
    "missing_residue_claims": MAX_MISSING_RESIDUE_CLAIMS,
    "missing_atom_claims": MAX_MISSING_ATOM_CLAIMS,
    "total_missingness_claims": MAX_TOTAL_MISSINGNESS_CLAIMS,
    "missingness_metadata_projected_claims": _MAX_MISSINGNESS_PROJECTED_CLAIMS,
}
_PRESERVATION_SCOPE = (
    "source_atom_and_residue_order",
    "pdb_atom_or_hetatm_record_class",
    "source_atom_serial_and_raw_four_column_name_field",
    "element_residue_chain_insertion_and_segment_identifiers",
    "blank_or_explicit_formal_charge_encoding",
    "exact_f8_3_model_coordinates_angstrom",
    "blank_or_exact_f6_2_occupancy_and_b_factor",
    "source_model_identifiers",
    "semantic_ter_layout_excluding_dynamic_line_number",
    "optional_parser_owned_cryst1_lengths_angles_space_group_z_and_cell_vectors",
    "single_model_id1_source_reported_remark_465_470_semantics_excluding_raw_layout",
)
_NON_PROMOTION_BLOCKERS = (
    "raw_source_bytes_and_layout_are_not_preserved",
    "system_id_source_id_parser_observation_and_resource_layout_are_outside_declared_projection",
    "full_canonical_snapshot_and_dynamic_source_provenance_equality_not_claimed",
    "sha256_receipts_are_tamper_evidence_not_source_authentication",
    "conect_bond_topology_altloc_and_general_missingness_unsupported",
    "remark_465_470_projection_preserves_source_reported_claims_not_actual_completeness",
    "seqres_reference_membership_and_missingness_modeling_are_not_assessed",
    "crystallographic_metadata_is_not_a_simulation_pbc_box_and_symmetry_or_assembly_is_not_expanded",
    "preparation_parameterability_simulation_and_claim_authority_not_granted",
)
_ARTIFACT_FACTORY_TOKEN = object()


class PdbWriteError(ValueError):
    """Stable fail-closed error for unrepresentable canonical PDB state."""

    def __init__(self, code: str, message: str, *, location: str | None = None):
        self.code = str(code)
        self.location = None if location is None else str(location)
        self.detail = str(message)
        suffix = "" if self.location is None else f" at {self.location}"
        super().__init__(f"{self.code}{suffix}: {self.detail}")


def _canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _plain_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _exact_typed_json_equal(actual: Any, expected: Any) -> bool:
    """Compare JSON-shaped values without Python's bool/int coercion."""

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
    if type(expected) is float:
        return struct.pack(">d", actual) == struct.pack(">d", expected)
    return bool(actual == expected)


def _sha256_document(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(document)).hexdigest()


def _require_sha256(value: str, *, field_name: str) -> None:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise TypeError(f"{field_name} must be a lowercase SHA-256")


def _require_exact_keys(
    value: Any,
    expected: frozenset[str],
    *,
    code: str,
    location: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PdbWriteError(code, "value must be a mapping", location=location)
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise PdbWriteError(
            code,
            f"mapping keys do not match parser-owned state; missing={missing}, unknown={unknown}",
            location=location,
        )
    return value


def _binary64_hex(value: float) -> str:
    return struct.pack(">d", float(value)).hex()


@dataclass(frozen=True, slots=True, init=False)
class PdbWriteReceipt:
    """Hash binding for one deterministic strict-PDB emission."""

    input_system_schema_id: str
    parent_source_sha256: str
    input_snapshot_sha256: str
    input_topology_sha256: str
    input_representable_state_sha256: str
    input_parser_observation_sha256: str
    output_source_sha256: str
    output_byte_count: int
    atom_count: int
    bond_count: int
    model_count: int
    ter_count: int
    cell_present: bool
    cryst1_count: int
    input_missingness_report_sha256: str
    input_missingness_semantic_sha256: str
    missingness_evidence_present: bool
    input_missingness_remark_line_count: int
    emitted_missingness_remark_line_count: int
    missing_residue_claim_count: int
    missing_atom_claim_count: int

    def __init__(
        self,
        *,
        input_system_schema_id: str,
        parent_source_sha256: str,
        input_snapshot_sha256: str,
        input_topology_sha256: str,
        input_representable_state_sha256: str,
        input_parser_observation_sha256: str,
        output_source_sha256: str,
        output_byte_count: int,
        atom_count: int,
        bond_count: int,
        model_count: int,
        ter_count: int,
        cell_present: bool,
        cryst1_count: int,
        input_missingness_report_sha256: str,
        input_missingness_semantic_sha256: str,
        missingness_evidence_present: bool,
        input_missingness_remark_line_count: int,
        emitted_missingness_remark_line_count: int,
        missing_residue_claim_count: int,
        missing_atom_claim_count: int,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("PdbWriteReceipt is factory-only")
        for field_name, value in (
            ("input_system_schema_id", input_system_schema_id),
            ("parent_source_sha256", parent_source_sha256),
            ("input_snapshot_sha256", input_snapshot_sha256),
            ("input_topology_sha256", input_topology_sha256),
            ("input_representable_state_sha256", input_representable_state_sha256),
            ("input_parser_observation_sha256", input_parser_observation_sha256),
            ("output_source_sha256", output_source_sha256),
            ("output_byte_count", output_byte_count),
            ("atom_count", atom_count),
            ("bond_count", bond_count),
            ("model_count", model_count),
            ("ter_count", ter_count),
            ("cell_present", cell_present),
            ("cryst1_count", cryst1_count),
            ("input_missingness_report_sha256", input_missingness_report_sha256),
            (
                "input_missingness_semantic_sha256",
                input_missingness_semantic_sha256,
            ),
            ("missingness_evidence_present", missingness_evidence_present),
            (
                "input_missingness_remark_line_count",
                input_missingness_remark_line_count,
            ),
            (
                "emitted_missingness_remark_line_count",
                emitted_missingness_remark_line_count,
            ),
            ("missing_residue_claim_count", missing_residue_claim_count),
            ("missing_atom_claim_count", missing_atom_claim_count),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.input_system_schema_id != ALL_ATOM_SCHEMA_ID:
            raise ValueError("write receipt must bind the current all-atom schema")
        for field_name in (
            "parent_source_sha256",
            "input_snapshot_sha256",
            "input_topology_sha256",
            "input_representable_state_sha256",
            "input_parser_observation_sha256",
            "output_source_sha256",
            "input_missingness_report_sha256",
            "input_missingness_semantic_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        for field_name in (
            "output_byte_count",
            "atom_count",
            "bond_count",
            "model_count",
            "ter_count",
            "cryst1_count",
            "input_missingness_remark_line_count",
            "emitted_missingness_remark_line_count",
            "missing_residue_claim_count",
            "missing_atom_claim_count",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise TypeError(f"{field_name} must be a nonnegative integer")
        if self.atom_count < 1:
            raise ValueError("write receipt atom_count must be positive")
        if self.bond_count != 0:
            raise ValueError("strict PDB write receipt bond_count must be zero")
        if self.model_count < 1 or self.model_count * self.atom_count > _MAX_ATOM_ROWS:
            raise ValueError("write receipt model/atom rows exceed the PDB limit")
        if self.ter_count > self.model_count * self.atom_count:
            raise ValueError("write receipt ter_count cannot exceed emitted atom rows")
        if type(self.cell_present) is not bool:
            raise TypeError("cell_present must be an exact boolean")
        if self.cryst1_count not in {0, 1}:
            raise ValueError("write receipt cryst1_count must be zero or one")
        if self.cryst1_count != int(self.cell_present):
            raise ValueError("write receipt CRYST1 count must agree with cell presence")
        if type(self.missingness_evidence_present) is not bool:
            raise TypeError("missingness_evidence_present must be an exact boolean")
        total_claims = self.missing_residue_claim_count + self.missing_atom_claim_count
        if (
            self.missing_residue_claim_count > MAX_MISSING_RESIDUE_CLAIMS
            or self.missing_atom_claim_count > MAX_MISSING_ATOM_CLAIMS
            or total_claims > MAX_TOTAL_MISSINGNESS_CLAIMS
        ):
            raise ValueError(
                "write receipt missingness claim counts exceed fixed limits"
            )
        if self.missingness_evidence_present != (total_claims > 0):
            raise ValueError(
                "missingness evidence presence must agree with the exact claim counts"
            )
        if self.missingness_evidence_present and self.model_count != 1:
            raise ValueError(
                "missingness evidence receipt requires exactly one coordinate model"
            )
        expected_emitted_lines = (
            (2 + self.missing_residue_claim_count)
            if self.missing_residue_claim_count
            else 0
        ) + (
            (2 + self.missing_atom_claim_count) if self.missing_atom_claim_count else 0
        )
        if self.emitted_missingness_remark_line_count != expected_emitted_lines:
            raise ValueError(
                "emitted missingness line count does not match canonical section shape"
            )
        if self.emitted_missingness_remark_line_count > _MAX_MISSINGNESS_REMARK_LINES:
            raise ValueError("canonical missingness lines exceed the writer limit")
        if self.missingness_evidence_present:
            if (
                not 1
                <= self.input_missingness_remark_line_count
                <= (_MAX_MISSINGNESS_REMARK_LINES)
            ):
                raise ValueError("input missingness lines are outside the writer limit")
        elif self.input_missingness_remark_line_count != 0:
            raise ValueError(
                "empty missingness evidence cannot bind source remark lines"
            )
        if self.output_byte_count < 1 or self.output_byte_count > _MAX_OUTPUT_BYTES:
            raise ValueError(
                "write receipt output_byte_count is outside the writer limit"
            )

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": PDB_WRITE_RECEIPT_SCHEMA_ID,
            "writer_version": PDB_WRITER_VERSION,
            "parser_version": PDB_PARSER_VERSION,
            "input_system_schema_id": self.input_system_schema_id,
            "parent_source_sha256": self.parent_source_sha256,
            "input_snapshot_sha256": self.input_snapshot_sha256,
            "input_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
            "input_topology_sha256": self.input_topology_sha256,
            "representable_state_schema_id": PDB_REPRESENTABLE_STATE_SCHEMA_ID,
            "input_representable_state_sha256": self.input_representable_state_sha256,
            "parser_observation_schema_id": PARSER_OBSERVATION_SCHEMA_ID,
            "input_parser_observation_sha256": self.input_parser_observation_sha256,
            "output_source_sha256": self.output_source_sha256,
            "output_byte_count": self.output_byte_count,
            "atom_count": self.atom_count,
            "bond_count": self.bond_count,
            "model_count": self.model_count,
            "ter_count": self.ter_count,
            "cell_present": self.cell_present,
            "cryst1_count": self.cryst1_count,
            "missingness_semantic_schema_id": PDB_MISSINGNESS_SEMANTIC_SCHEMA_ID,
            "missingness_profile_id": PDB_MISSINGNESS_PROFILE_ID,
            "input_missingness_report_sha256": self.input_missingness_report_sha256,
            "input_missingness_semantic_sha256": (
                self.input_missingness_semantic_sha256
            ),
            "missingness_evidence_present": self.missingness_evidence_present,
            "input_missingness_remark_line_count": (
                self.input_missingness_remark_line_count
            ),
            "emitted_missingness_remark_line_count": (
                self.emitted_missingness_remark_line_count
            ),
            "missing_residue_claim_count": self.missing_residue_claim_count,
            "missing_atom_claim_count": self.missing_atom_claim_count,
            "coordinate_unit": "angstrom",
            "coordinate_format": "fixed_width_f8_3_exact_binary64_round_trip",
            "occupancy_b_factor_format": "blank_or_fixed_width_f6_2_exact_binary64_round_trip",
            "cryst1_format": "optional_fixed_width_f9_3_lengths_f7_2_angles_ascii_space_group_and_blank_or_i4_z_exact_binary64_round_trip",
            "preservation_scope": list(_PRESERVATION_SCOPE),
            "source_authentication_status": "not_authenticated",
            "preparation_ready": False,
            "parameterability_assessed": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": list(_NON_PROMOTION_BLOCKERS),
        }

    @property
    def receipt_sha256(self) -> str:
        return _sha256_document(self._core_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = self._core_dict()
        payload["receipt_sha256"] = self.receipt_sha256
        return payload


@dataclass(frozen=True, slots=True, init=False)
class PdbWriteResult:
    payload: bytes = field(repr=False)
    receipt: PdbWriteReceipt
    _input_snapshot: bytes = field(repr=False)

    def __init__(
        self,
        *,
        payload: bytes,
        receipt: PdbWriteReceipt,
        input_snapshot: bytes,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("PdbWriteResult is factory-only")
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "receipt", receipt)
        object.__setattr__(self, "_input_snapshot", input_snapshot)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self.payload) is not bytes:
            raise TypeError("PDB write payload must be exact bytes")
        if type(self.receipt) is not PdbWriteReceipt:
            raise TypeError("receipt must be a PdbWriteReceipt")
        if type(self._input_snapshot) is not bytes:
            raise TypeError("PDB write input snapshot must be exact bytes")
        if len(self.payload) != self.receipt.output_byte_count:
            raise ValueError("write payload length does not match receipt")
        if (
            hashlib.sha256(self.payload).hexdigest()
            != self.receipt.output_source_sha256
        ):
            raise ValueError("write payload SHA-256 does not match receipt")
        cryst1_count = sum(
            line.startswith(b"CRYST1") for line in self.payload.splitlines()
        )
        if cryst1_count != self.receipt.cryst1_count:
            raise ValueError("write payload CRYST1 count does not match receipt")
        if bool(cryst1_count) is not self.receipt.cell_present:
            raise ValueError("write payload CRYST1 state does not match receipt")
        try:
            snapshot_system = deserialize_all_atom_system(self._input_snapshot)
            state = _validate_write_state(snapshot_system)
            expected_payload = _emit_payload(state)
        except (PdbWriteError, TypeError, ValueError, RuntimeError) as exc:
            raise ValueError(
                "write input snapshot is not valid strict-PDB state"
            ) from exc
        expected_pairs = (
            ("payload bytes", expected_payload, self.payload),
            (
                "input system schema",
                state.system.schema_id,
                self.receipt.input_system_schema_id,
            ),
            (
                "parent source",
                state.system.provenance.source_sha256,
                self.receipt.parent_source_sha256,
            ),
            (
                "input snapshot",
                canonical_all_atom_snapshot_digest(state.system),
                self.receipt.input_snapshot_sha256,
            ),
            (
                "input topology",
                canonical_topology_sha256(state.system),
                self.receipt.input_topology_sha256,
            ),
            (
                "representable state",
                _sha256_document(state.representable_state_document),
                self.receipt.input_representable_state_sha256,
            ),
            (
                "parser observation",
                state.system.provenance.metadata.get("parser_observation_sha256"),
                self.receipt.input_parser_observation_sha256,
            ),
            (
                "raw missingness report",
                state.missingness_report.report_sha256,
                self.receipt.input_missingness_report_sha256,
            ),
            (
                "missingness semantics",
                state.missingness_semantic_sha256,
                self.receipt.input_missingness_semantic_sha256,
            ),
            (
                "missingness evidence presence",
                state.missingness_evidence_present,
                self.receipt.missingness_evidence_present,
            ),
            (
                "input missingness lines",
                state.input_missingness_remark_line_count,
                self.receipt.input_missingness_remark_line_count,
            ),
            (
                "emitted missingness lines",
                len(state.missingness_lines),
                self.receipt.emitted_missingness_remark_line_count,
            ),
            (
                "missing residue count",
                len(state.missingness_report.missing_residue_claims),
                self.receipt.missing_residue_claim_count,
            ),
            (
                "missing atom count",
                len(state.missingness_report.missing_atom_claims),
                self.receipt.missing_atom_claim_count,
            ),
            ("atom count", state.system.atom_count, self.receipt.atom_count),
            ("bond count", len(state.system.bonds), self.receipt.bond_count),
            ("model count", state.system.model_count, self.receipt.model_count),
            (
                "TER count",
                sum(len(records) for records in state.ter_records_by_model),
                self.receipt.ter_count,
            ),
            ("cell presence", state.cryst1 is not None, self.receipt.cell_present),
            ("CRYST1 count", int(state.cryst1 is not None), self.receipt.cryst1_count),
        )
        mismatches = [
            label
            for label, expected, observed in expected_pairs
            if expected != observed
        ]
        if mismatches:
            raise ValueError(
                f"PDB write result artifacts are not cross-consistent: {mismatches}"
            )


@dataclass(frozen=True, slots=True, init=False)
class PdbRoundTripReport:
    """Evidence for the declared source-independent PDB projection."""

    input_source_sha256: str
    input_snapshot_sha256: str
    input_topology_sha256: str
    input_representable_state_sha256: str
    input_parser_observation_sha256: str
    writer_receipt_sha256: str
    emitted_source_sha256: str
    reparsed_snapshot_sha256: str
    reparsed_topology_sha256: str
    reparsed_representable_state_sha256: str
    reparsed_parser_observation_sha256: str
    reemitted_source_sha256: str
    input_missingness_report_sha256: str
    reparsed_missingness_report_sha256: str
    input_missingness_semantic_sha256: str
    reparsed_missingness_semantic_sha256: str
    missingness_evidence_present: bool
    missing_residue_claim_count: int
    missing_atom_claim_count: int

    def __init__(
        self,
        *,
        input_source_sha256: str,
        input_snapshot_sha256: str,
        input_topology_sha256: str,
        input_representable_state_sha256: str,
        input_parser_observation_sha256: str,
        writer_receipt_sha256: str,
        emitted_source_sha256: str,
        reparsed_snapshot_sha256: str,
        reparsed_topology_sha256: str,
        reparsed_representable_state_sha256: str,
        reparsed_parser_observation_sha256: str,
        reemitted_source_sha256: str,
        input_missingness_report_sha256: str,
        reparsed_missingness_report_sha256: str,
        input_missingness_semantic_sha256: str,
        reparsed_missingness_semantic_sha256: str,
        missingness_evidence_present: bool,
        missing_residue_claim_count: int,
        missing_atom_claim_count: int,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("PdbRoundTripReport is factory-only")
        for field_name, value in (
            ("input_source_sha256", input_source_sha256),
            ("input_snapshot_sha256", input_snapshot_sha256),
            ("input_topology_sha256", input_topology_sha256),
            ("input_representable_state_sha256", input_representable_state_sha256),
            ("input_parser_observation_sha256", input_parser_observation_sha256),
            ("writer_receipt_sha256", writer_receipt_sha256),
            ("emitted_source_sha256", emitted_source_sha256),
            ("reparsed_snapshot_sha256", reparsed_snapshot_sha256),
            ("reparsed_topology_sha256", reparsed_topology_sha256),
            (
                "reparsed_representable_state_sha256",
                reparsed_representable_state_sha256,
            ),
            ("reparsed_parser_observation_sha256", reparsed_parser_observation_sha256),
            ("reemitted_source_sha256", reemitted_source_sha256),
            ("input_missingness_report_sha256", input_missingness_report_sha256),
            (
                "reparsed_missingness_report_sha256",
                reparsed_missingness_report_sha256,
            ),
            (
                "input_missingness_semantic_sha256",
                input_missingness_semantic_sha256,
            ),
            (
                "reparsed_missingness_semantic_sha256",
                reparsed_missingness_semantic_sha256,
            ),
            ("missingness_evidence_present", missingness_evidence_present),
            ("missing_residue_claim_count", missing_residue_claim_count),
            ("missing_atom_claim_count", missing_atom_claim_count),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        for field_name in (
            "input_source_sha256",
            "input_snapshot_sha256",
            "input_topology_sha256",
            "input_representable_state_sha256",
            "input_parser_observation_sha256",
            "writer_receipt_sha256",
            "emitted_source_sha256",
            "reparsed_snapshot_sha256",
            "reparsed_topology_sha256",
            "reparsed_representable_state_sha256",
            "reparsed_parser_observation_sha256",
            "reemitted_source_sha256",
            "input_missingness_report_sha256",
            "reparsed_missingness_report_sha256",
            "input_missingness_semantic_sha256",
            "reparsed_missingness_semantic_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        if self.input_topology_sha256 != self.reparsed_topology_sha256:
            raise ValueError("round-trip topology hashes must match")
        if (
            self.input_representable_state_sha256
            != self.reparsed_representable_state_sha256
        ):
            raise ValueError("round-trip representable-state hashes must match")
        if self.emitted_source_sha256 != self.reemitted_source_sha256:
            raise ValueError("round-trip emitted bytes must be stable")
        if (
            self.input_missingness_semantic_sha256
            != self.reparsed_missingness_semantic_sha256
        ):
            raise ValueError("round-trip missingness semantic hashes must match")
        if type(self.missingness_evidence_present) is not bool:
            raise TypeError("missingness_evidence_present must be an exact boolean")
        for field_name in ("missing_residue_claim_count", "missing_atom_claim_count"):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise TypeError(f"{field_name} must be a nonnegative integer")
        if self.missingness_evidence_present != (
            self.missing_residue_claim_count + self.missing_atom_claim_count > 0
        ):
            raise ValueError("missingness presence must agree with report claim counts")
        total_claims = self.missing_residue_claim_count + self.missing_atom_claim_count
        if (
            self.missing_residue_claim_count > MAX_MISSING_RESIDUE_CLAIMS
            or self.missing_atom_claim_count > MAX_MISSING_ATOM_CLAIMS
            or total_claims > MAX_TOTAL_MISSINGNESS_CLAIMS
        ):
            raise ValueError("round-trip report missingness counts exceed fixed limits")

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": PDB_ROUND_TRIP_REPORT_SCHEMA_ID,
            "writer_version": PDB_WRITER_VERSION,
            "parser_version": PDB_PARSER_VERSION,
            "representable_state_schema_id": PDB_REPRESENTABLE_STATE_SCHEMA_ID,
            "input_source_sha256": self.input_source_sha256,
            "input_snapshot_sha256": self.input_snapshot_sha256,
            "input_topology_sha256": self.input_topology_sha256,
            "input_representable_state_sha256": self.input_representable_state_sha256,
            "input_parser_observation_sha256": self.input_parser_observation_sha256,
            "writer_receipt_sha256": self.writer_receipt_sha256,
            "emitted_source_sha256": self.emitted_source_sha256,
            "reparsed_snapshot_sha256": self.reparsed_snapshot_sha256,
            "reparsed_topology_sha256": self.reparsed_topology_sha256,
            "reparsed_representable_state_sha256": self.reparsed_representable_state_sha256,
            "reparsed_parser_observation_sha256": self.reparsed_parser_observation_sha256,
            "reemitted_source_sha256": self.reemitted_source_sha256,
            "missingness_semantic_schema_id": PDB_MISSINGNESS_SEMANTIC_SCHEMA_ID,
            "missingness_profile_id": PDB_MISSINGNESS_PROFILE_ID,
            "input_missingness_report_sha256": self.input_missingness_report_sha256,
            "reparsed_missingness_report_sha256": (
                self.reparsed_missingness_report_sha256
            ),
            "input_missingness_semantic_sha256": (
                self.input_missingness_semantic_sha256
            ),
            "reparsed_missingness_semantic_sha256": (
                self.reparsed_missingness_semantic_sha256
            ),
            "missingness_evidence_present": self.missingness_evidence_present,
            "missing_residue_claim_count": self.missing_residue_claim_count,
            "missing_atom_claim_count": self.missing_atom_claim_count,
            "missingness_semantic_sha256_equal": True,
            "missingness_raw_report_sha256_equal_claimed": False,
            "missingness_raw_source_layout_equal_claimed": False,
            "declared_projection_sha256_equal": True,
            "canonical_topology_sha256_equal": True,
            "coordinate_binary64_projection_equal": True,
            "cryst1_cell_binary64_projection_equal": True,
            "declared_parser_marker_projection_equal": True,
            "emitted_source_sha256_and_bytes_stable": True,
            "full_canonical_snapshot_equality_claimed": False,
            "dynamic_source_provenance_equality_claimed": False,
            "source_authentication_status": "not_authenticated",
            "preparation_ready": False,
            "parameterability_assessed": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": list(_NON_PROMOTION_BLOCKERS),
        }

    @property
    def report_sha256(self) -> str:
        return _sha256_document(self._core_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = self._core_dict()
        payload["report_sha256"] = self.report_sha256
        return payload


@dataclass(frozen=True, slots=True, init=False)
class PdbRoundTripResult:
    """Snapshot-backed aggregate for one verified PDB source round trip."""

    _source_snapshot: bytes = field(repr=False)
    _source_coverage: StructureIngestCoverage
    _source_missingness: SourceReportedMissingnessReport = field(repr=False)
    _write_result: PdbWriteResult = field(repr=False)
    _reparsed_snapshot: bytes = field(repr=False)
    _reparsed_coverage: StructureIngestCoverage
    _reparsed_missingness: SourceReportedMissingnessReport = field(repr=False)
    _report: PdbRoundTripReport = field(repr=False)

    def __init__(
        self,
        *,
        source_ingest: StructureIngestResult,
        write_result: PdbWriteResult,
        reparsed_ingest: StructureIngestResult,
        report: PdbRoundTripReport,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("PdbRoundTripResult is factory-only")
        if type(source_ingest) is not StructureIngestResult:
            raise TypeError("source_ingest must be a StructureIngestResult")
        if type(source_ingest.coverage) is not StructureIngestCoverage:
            raise TypeError("source_ingest.coverage must be a StructureIngestCoverage")
        if (
            type(source_ingest.missingness_evidence)
            is not SourceReportedMissingnessReport
        ):
            raise TypeError(
                "source_ingest.missingness_evidence must be a SourceReportedMissingnessReport"
            )
        if type(write_result) is not PdbWriteResult:
            raise TypeError("write_result must be a PdbWriteResult")
        if type(reparsed_ingest) is not StructureIngestResult:
            raise TypeError("reparsed_ingest must be a StructureIngestResult")
        if type(reparsed_ingest.coverage) is not StructureIngestCoverage:
            raise TypeError(
                "reparsed_ingest.coverage must be a StructureIngestCoverage"
            )
        if (
            type(reparsed_ingest.missingness_evidence)
            is not SourceReportedMissingnessReport
        ):
            raise TypeError(
                "reparsed_ingest.missingness_evidence must be a SourceReportedMissingnessReport"
            )
        if type(report) is not PdbRoundTripReport:
            raise TypeError("report must be a PdbRoundTripReport")
        object.__setattr__(
            self,
            "_source_snapshot",
            serialize_all_atom_system(source_ingest.system),
        )
        object.__setattr__(self, "_source_coverage", source_ingest.coverage)
        object.__setattr__(
            self,
            "_source_missingness",
            source_ingest.missingness_evidence,
        )
        object.__setattr__(self, "_write_result", write_result)
        object.__setattr__(
            self,
            "_reparsed_snapshot",
            serialize_all_atom_system(reparsed_ingest.system),
        )
        object.__setattr__(self, "_reparsed_coverage", reparsed_ingest.coverage)
        object.__setattr__(
            self,
            "_reparsed_missingness",
            reparsed_ingest.missingness_evidence,
        )
        object.__setattr__(self, "_report", report)
        self.__post_init__()

    @property
    def source_ingest(self) -> StructureIngestResult:
        """Return a fresh detached copy of the source canonical snapshot."""

        return StructureIngestResult(
            system=deserialize_all_atom_system(self._source_snapshot),
            coverage=self._source_coverage,
            missingness_evidence=self._source_missingness,
        )

    @property
    def write_result(self) -> PdbWriteResult:
        return self._write_result

    @property
    def reparsed_ingest(self) -> StructureIngestResult:
        """Return a fresh detached copy of the reparsed canonical snapshot."""

        return StructureIngestResult(
            system=deserialize_all_atom_system(self._reparsed_snapshot),
            coverage=self._reparsed_coverage,
            missingness_evidence=self._reparsed_missingness,
        )

    @property
    def report(self) -> PdbRoundTripReport:
        return self._report

    def __post_init__(self) -> None:
        if type(self._source_snapshot) is not bytes:
            raise TypeError("source snapshot must be exact bytes")
        if type(self._source_coverage) is not StructureIngestCoverage:
            raise TypeError("source coverage must be a StructureIngestCoverage")
        if type(self._source_missingness) is not SourceReportedMissingnessReport:
            raise TypeError(
                "source missingness must be a SourceReportedMissingnessReport"
            )
        if type(self._write_result) is not PdbWriteResult:
            raise TypeError("write result must be a PdbWriteResult")
        if type(self._reparsed_snapshot) is not bytes:
            raise TypeError("reparsed snapshot must be exact bytes")
        if type(self._reparsed_coverage) is not StructureIngestCoverage:
            raise TypeError("reparsed coverage must be a StructureIngestCoverage")
        if type(self._reparsed_missingness) is not SourceReportedMissingnessReport:
            raise TypeError(
                "reparsed missingness must be a SourceReportedMissingnessReport"
            )
        if type(self._report) is not PdbRoundTripReport:
            raise TypeError("report must be a PdbRoundTripReport")

        source_ingest = self.source_ingest
        reparsed_ingest = self.reparsed_ingest
        source_system = source_ingest.system
        reparsed_system = reparsed_ingest.system
        source_snapshot_sha256 = canonical_all_atom_snapshot_digest(source_system)
        source_topology_sha256 = canonical_topology_sha256(source_system)
        source_state_sha256 = pdb_representable_state_sha256(source_system)
        reparsed_snapshot_sha256 = canonical_all_atom_snapshot_digest(reparsed_system)
        reparsed_topology_sha256 = canonical_topology_sha256(reparsed_system)
        reparsed_state_sha256 = pdb_representable_state_sha256(reparsed_system)
        output_source_sha256 = hashlib.sha256(self.write_result.payload).hexdigest()
        reemitted = write_pdb(reparsed_system)
        source_observation = source_system.provenance.metadata.get(
            "parser_observation_sha256"
        )
        reparsed_observation = reparsed_system.provenance.metadata.get(
            "parser_observation_sha256"
        )
        source_pdb_metadata = source_system.metadata.get("pdb")
        source_ter_count = (
            sum(
                len(entry.get("records", ()))
                for entry in source_pdb_metadata.get("ter_records_by_model", ())
                if isinstance(entry, Mapping)
            )
            if isinstance(source_pdb_metadata, Mapping)
            else -1
        )
        reparsed_pdb_metadata = reparsed_system.metadata.get("pdb")
        source_cryst1_count = int(
            isinstance(source_pdb_metadata, Mapping)
            and source_pdb_metadata.get("cryst1") is not None
        )
        reparsed_cryst1_count = int(
            isinstance(reparsed_pdb_metadata, Mapping)
            and reparsed_pdb_metadata.get("cryst1") is not None
        )
        source_cell_present = source_system.cell is not None
        reparsed_cell_present = reparsed_system.cell is not None
        expected_pairs = (
            (
                "source system schema to receipt",
                source_system.schema_id,
                self.write_result.receipt.input_system_schema_id,
            ),
            (
                "source atom count to receipt",
                source_system.atom_count,
                self.write_result.receipt.atom_count,
            ),
            (
                "source bond count to receipt",
                len(source_system.bonds),
                self.write_result.receipt.bond_count,
            ),
            (
                "source model count to receipt",
                source_system.model_count,
                self.write_result.receipt.model_count,
            ),
            (
                "source semantic TER count to receipt",
                source_ter_count,
                self.write_result.receipt.ter_count,
            ),
            (
                "source cell presence to receipt",
                source_cell_present,
                self.write_result.receipt.cell_present,
            ),
            (
                "source CRYST1 count to receipt",
                source_cryst1_count,
                self.write_result.receipt.cryst1_count,
            ),
            (
                "source snapshot to hidden write snapshot",
                self._source_snapshot,
                self.write_result._input_snapshot,
            ),
            (
                "source raw missingness report to receipt",
                self._source_missingness.report_sha256,
                self.write_result.receipt.input_missingness_report_sha256,
            ),
            (
                "source raw missingness report to report",
                self._source_missingness.report_sha256,
                self.report.input_missingness_report_sha256,
            ),
            (
                "source missingness semantics to report",
                self.write_result.receipt.input_missingness_semantic_sha256,
                self.report.input_missingness_semantic_sha256,
            ),
            (
                "source missingness presence to report",
                self.write_result.receipt.missingness_evidence_present,
                self.report.missingness_evidence_present,
            ),
            (
                "source missing residue count to report",
                len(self._source_missingness.missing_residue_claims),
                self.report.missing_residue_claim_count,
            ),
            (
                "source missing atom count to report",
                len(self._source_missingness.missing_atom_claims),
                self.report.missing_atom_claim_count,
            ),
            (
                "source to reparsed cell presence",
                source_cell_present,
                reparsed_cell_present,
            ),
            (
                "source to reparsed CRYST1 count",
                source_cryst1_count,
                reparsed_cryst1_count,
            ),
            (
                "reparsed cell presence to reemitted receipt",
                reparsed_cell_present,
                reemitted.receipt.cell_present,
            ),
            (
                "reparsed CRYST1 count to reemitted receipt",
                reparsed_cryst1_count,
                reemitted.receipt.cryst1_count,
            ),
            (
                "reparsed raw missingness report to report",
                self._reparsed_missingness.report_sha256,
                self.report.reparsed_missingness_report_sha256,
            ),
            (
                "reparsed raw missingness report to reemitted receipt",
                self._reparsed_missingness.report_sha256,
                reemitted.receipt.input_missingness_report_sha256,
            ),
            (
                "reparsed missingness semantics to report",
                reemitted.receipt.input_missingness_semantic_sha256,
                self.report.reparsed_missingness_semantic_sha256,
            ),
            (
                "source to reparsed missingness semantics",
                self.write_result.receipt.input_missingness_semantic_sha256,
                reemitted.receipt.input_missingness_semantic_sha256,
            ),
            (
                "source to reparsed missing residue count",
                len(self._source_missingness.missing_residue_claims),
                len(self._reparsed_missingness.missing_residue_claims),
            ),
            (
                "source to reparsed missing atom count",
                len(self._source_missingness.missing_atom_claims),
                len(self._reparsed_missingness.missing_atom_claims),
            ),
            (
                "source provenance to report input source",
                source_system.provenance.source_sha256,
                self.report.input_source_sha256,
            ),
            (
                "source provenance to receipt parent source",
                source_system.provenance.source_sha256,
                self.write_result.receipt.parent_source_sha256,
            ),
            (
                "source snapshot to receipt",
                source_snapshot_sha256,
                self.write_result.receipt.input_snapshot_sha256,
            ),
            (
                "source snapshot to report",
                source_snapshot_sha256,
                self.report.input_snapshot_sha256,
            ),
            (
                "source topology to receipt",
                source_topology_sha256,
                self.write_result.receipt.input_topology_sha256,
            ),
            (
                "source topology to report",
                source_topology_sha256,
                self.report.input_topology_sha256,
            ),
            (
                "source representable state to receipt",
                source_state_sha256,
                self.write_result.receipt.input_representable_state_sha256,
            ),
            (
                "source representable state to report",
                source_state_sha256,
                self.report.input_representable_state_sha256,
            ),
            (
                "source parser observation to receipt",
                source_observation,
                self.write_result.receipt.input_parser_observation_sha256,
            ),
            (
                "source parser observation to report",
                source_observation,
                self.report.input_parser_observation_sha256,
            ),
            (
                "write receipt to report",
                self.write_result.receipt.receipt_sha256,
                self.report.writer_receipt_sha256,
            ),
            (
                "payload to receipt output source",
                output_source_sha256,
                self.write_result.receipt.output_source_sha256,
            ),
            (
                "payload to report emitted source",
                output_source_sha256,
                self.report.emitted_source_sha256,
            ),
            (
                "payload to reparsed source provenance",
                output_source_sha256,
                reparsed_system.provenance.source_sha256,
            ),
            (
                "reparsed snapshot to report",
                reparsed_snapshot_sha256,
                self.report.reparsed_snapshot_sha256,
            ),
            (
                "reparsed topology to report",
                reparsed_topology_sha256,
                self.report.reparsed_topology_sha256,
            ),
            (
                "reparsed representable state to report",
                reparsed_state_sha256,
                self.report.reparsed_representable_state_sha256,
            ),
            (
                "reparsed parser observation to report",
                reparsed_observation,
                self.report.reparsed_parser_observation_sha256,
            ),
            (
                "reemitted payload to report",
                hashlib.sha256(reemitted.payload).hexdigest(),
                self.report.reemitted_source_sha256,
            ),
        )
        mismatches = [
            label
            for label, expected, observed in expected_pairs
            if expected != observed
        ]
        if source_system.cell is not None and reparsed_system.cell is not None:
            source_cell_hex = tuple(
                _binary64_hex(value)
                for row in source_system.cell.vectors.tolist()
                for value in row
            )
            reparsed_cell_hex = tuple(
                _binary64_hex(value)
                for row in reparsed_system.cell.vectors.tolist()
                for value in row
            )
            if source_cell_hex != reparsed_cell_hex:
                mismatches.append("source to reparsed CRYST1 cell vectors")
            if source_system.cell.periodic != reparsed_system.cell.periodic:
                mismatches.append("source to reparsed CRYST1 periodic flags")
        for label, ingest in (
            ("source", source_ingest),
            ("reparsed", reparsed_ingest),
        ):
            if ingest.coverage.to_dict() != ingest.system.provenance.metadata.get(
                "coverage"
            ):
                mismatches.append(f"{label} ingest coverage")
            if ingest.missingness_evidence.to_dict() != ingest.system.metadata.get(
                "pdb", {}
            ).get("source_reported_missingness"):
                mismatches.append(f"{label} ingest missingness")
        if reemitted.payload != self.write_result.payload:
            mismatches.append("reemitted payload bytes")
        if mismatches:
            raise ValueError(
                "PDB round-trip result artifacts are not cross-consistent: "
                f"{mismatches}"
            )


@dataclass(frozen=True, slots=True)
class _ValidatedCryst1State:
    line: str
    document: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _ValidatedWriteState:
    system: AllAtomSystem
    model_ids: tuple[int, ...]
    coordinate_tokens: tuple[tuple[tuple[str, str, str], ...], ...]
    occupancy_tokens: tuple[str, ...]
    b_factor_tokens: tuple[str, ...]
    charge_tokens: tuple[str, ...]
    ter_records_by_model: tuple[tuple[Mapping[str, Any], ...], ...]
    cryst1: _ValidatedCryst1State | None
    missingness_report: SourceReportedMissingnessReport
    missingness_semantic_document: Mapping[str, Any]
    missingness_semantic_sha256: str
    missingness_evidence_present: bool
    input_missingness_remark_line_count: int
    missingness_lines: tuple[str, ...]
    representable_state_document: Mapping[str, Any]


def _snapshot_parser_system(system: AllAtomSystem) -> AllAtomSystem:
    if type(system) is not AllAtomSystem:
        raise TypeError("PDB writer input must be an exact AllAtomSystem")
    raw_pdb_metadata = (
        system.metadata.get("pdb") if isinstance(system.metadata, Mapping) else None
    )
    raw_cryst1 = (
        raw_pdb_metadata.get("cryst1")
        if isinstance(raw_pdb_metadata, Mapping)
        else None
    )
    if (system.cell is None) != (raw_cryst1 is None):
        raise PdbWriteError(
            "cryst1_state_mismatch",
            "canonical cell and parser-owned CRYST1 metadata must be present together",
            location="cell",
        )

    coordinates = system.coordinates
    if coordinates.device.type != "cpu":
        raise PdbWriteError(
            "unsupported_coordinate_device",
            "parser-owned PDB coordinates must be on CPU",
            location="coordinates",
        )
    if coordinates.dtype is not torch.float64:
        raise PdbWriteError(
            "unsupported_coordinate_dtype",
            "parser-owned PDB coordinates must use float64",
            location="coordinates",
        )
    if coordinates.requires_grad:
        raise PdbWriteError(
            "coordinate_gradient_state_unsupported",
            "PDB writing does not accept coordinates requiring gradients",
            location="coordinates",
        )
    snapshot_cell: UnitCell | None = None
    if system.cell is not None:
        if type(system.cell) is not UnitCell:
            raise PdbWriteError(
                "unsupported_unit_cell_type",
                "parser-owned PDB cell must be an exact UnitCell",
                location="cell",
            )
        vectors = system.cell.vectors
        if type(vectors) is not torch.Tensor:
            raise PdbWriteError(
                "unsupported_unit_cell_type",
                "unit-cell vectors must be an exact tensor",
                location="cell.vectors",
            )
        if vectors.layout is not torch.strided:
            raise PdbWriteError(
                "unsupported_unit_cell_layout",
                "parser-owned unit-cell vectors must use strided layout",
                location="cell.vectors",
            )
        if vectors.device.type != "cpu":
            raise PdbWriteError(
                "unsupported_unit_cell_device",
                "parser-owned unit-cell vectors must be on CPU",
                location="cell.vectors",
            )
        if vectors.dtype is not torch.float64:
            raise PdbWriteError(
                "unsupported_unit_cell_dtype",
                "parser-owned unit-cell vectors must use float64",
                location="cell.vectors",
            )
        if vectors.shape != (3, 3):
            raise PdbWriteError(
                "unsupported_unit_cell_shape",
                "parser-owned unit-cell vectors must have shape [3, 3]",
                location="cell.vectors",
            )
        if vectors.requires_grad:
            raise PdbWriteError(
                "unit_cell_gradient_state_unsupported",
                "PDB writing does not accept unit-cell vectors requiring gradients",
                location="cell.vectors",
            )
        if system.cell.periodic != (False, False, False):
            raise PdbWriteError(
                "unsupported_unit_cell_periodic_state",
                "CRYST1 is crystallographic metadata and must not be promoted to periodic simulation state",
                location="cell.periodic",
            )
        snapshot_cell = UnitCell(
            vectors=vectors.detach().clone(),
            periodic=(False, False, False),
        )
    try:
        snapshot = replace(
            system,
            coordinates=coordinates.detach().clone(),
            cell=snapshot_cell,
        )
        require_valid_all_atom_system(snapshot)
    except (MolecularValidationError, TypeError, ValueError, RuntimeError) as exc:
        raise PdbWriteError(
            "canonical_validation_failed",
            str(exc),
            location="system",
        ) from exc
    return snapshot


def _fixed_decimal_token(
    value: float,
    *,
    width: int,
    precision: int,
    kind: str,
    location: str,
) -> str:
    if not math.isfinite(value):
        raise PdbWriteError(
            f"nonfinite_{kind}",
            f"{kind.replace('_', ' ')} must be finite",
            location=location,
        )
    token = f"{value:{width}.{precision}f}"
    if len(token) != width or "e" in token.lower():
        raise PdbWriteError(
            f"{kind}_field_overflow",
            f"value does not fit fixed-width F{width}.{precision}",
            location=location,
        )
    reparsed = float(token)
    if _binary64_hex(reparsed) != _binary64_hex(value):
        raise PdbWriteError(
            f"{kind}_rounding_required",
            f"value is not exactly representable by F{width}.{precision}",
            location=location,
        )
    return token


def _optional_f6_2_token(
    value: float | None,
    *,
    kind: str,
    location: str,
) -> str:
    if value is None:
        return " " * 6
    return _fixed_decimal_token(
        value,
        width=6,
        precision=2,
        kind=kind,
        location=location,
    )


def _integer_token(value: Any, *, width: int, code: str, location: str) -> str:
    if type(value) is not int:
        raise PdbWriteError(code, "value must be an integer", location=location)
    token = f"{value:{width}d}"
    if len(token) != width:
        raise PdbWriteError(
            code,
            f"integer does not fit the I{width} field",
            location=location,
        )
    return token


def _ascii_text(
    value: Any,
    *,
    max_chars: int,
    code: str,
    location: str,
    allow_empty: bool = False,
) -> str:
    if type(value) is not str:
        raise PdbWriteError(code, "value must be a string", location=location)
    if (not value and not allow_empty) or len(value) > max_chars:
        raise PdbWriteError(
            code,
            f"value must contain {'zero to ' if allow_empty else 'one to '}{max_chars} characters",
            location=location,
        )
    if not value.isascii() or any(
        ord(character) < 0x20 or ord(character) > 0x7E for character in value
    ):
        raise PdbWriteError(
            code,
            "value must contain only printable ASCII",
            location=location,
        )
    return value


def _cryst1_float_triplet(
    value: Any,
    *,
    field_name: str,
) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise PdbWriteError(
            "unsupported_cryst1_metadata",
            f"{field_name} must be a three-value parser-owned sequence",
            location=f"metadata.pdb.cryst1.{field_name}",
        )
    result: list[float] = []
    for index, item in enumerate(value):
        if type(item) is not float or not math.isfinite(item):
            raise PdbWriteError(
                "unsupported_cryst1_metadata",
                f"{field_name} values must be exact finite floats",
                location=f"metadata.pdb.cryst1.{field_name}[{index}]",
            )
        result.append(item)
    return result[0], result[1], result[2]


def _validate_cryst1_state(
    system: AllAtomSystem,
) -> _ValidatedCryst1State | None:
    pdb_metadata = system.metadata.get("pdb")
    raw_cryst1 = (
        pdb_metadata.get("cryst1") if isinstance(pdb_metadata, Mapping) else None
    )
    if system.cell is None:
        if raw_cryst1 is not None:
            raise PdbWriteError(
                "cryst1_state_mismatch",
                "CRYST1 metadata cannot exist without a canonical cell",
                location="metadata.pdb.cryst1",
            )
        return None
    if raw_cryst1 is None:
        raise PdbWriteError(
            "cryst1_state_mismatch",
            "canonical cell requires parser-owned CRYST1 metadata",
            location="metadata.pdb.cryst1",
        )

    cryst1 = _require_exact_keys(
        raw_cryst1,
        _CRYST1_METADATA_KEYS,
        code="unsupported_cryst1_metadata",
        location="metadata.pdb.cryst1",
    )
    lengths = _cryst1_float_triplet(
        cryst1.get("lengths_angstrom"),
        field_name="lengths_angstrom",
    )
    angles = _cryst1_float_triplet(
        cryst1.get("angles_degrees"),
        field_name="angles_degrees",
    )
    if min(lengths) <= 0.0:
        raise PdbWriteError(
            "unsupported_cryst1_metadata",
            "CRYST1 lengths must be positive",
            location="metadata.pdb.cryst1.lengths_angstrom",
        )
    if not all(0.0 < angle < 180.0 for angle in angles):
        raise PdbWriteError(
            "unsupported_cryst1_metadata",
            "CRYST1 angles must lie strictly between zero and 180 degrees",
            location="metadata.pdb.cryst1.angles_degrees",
        )

    space_group = _ascii_text(
        cryst1.get("space_group"),
        max_chars=11,
        code="unsupported_cryst1_space_group",
        location="metadata.pdb.cryst1.space_group",
        allow_empty=True,
    )
    if space_group != space_group.strip():
        raise PdbWriteError(
            "unsupported_cryst1_space_group",
            "parser-owned space group must not carry outer whitespace",
            location="metadata.pdb.cryst1.space_group",
        )
    normalized_space_group = " ".join(space_group.upper().split())
    if (
        all(
            math.isclose(length, 1.0, rel_tol=0.0, abs_tol=1.0e-6) for length in lengths
        )
        and all(
            math.isclose(angle, 90.0, rel_tol=0.0, abs_tol=1.0e-6) for angle in angles
        )
        and normalized_space_group == "P 1"
    ):
        raise PdbWriteError(
            "dummy_cryst1",
            "1x1x1 A, 90-degree P 1 CRYST1 placeholder is not a physical crystallographic cell",
            location="metadata.pdb.cryst1",
        )

    z_value = cryst1.get("z")
    if z_value is None:
        z_token = " " * 4
    else:
        if type(z_value) is not int or z_value < 1:
            raise PdbWriteError(
                "unsupported_cryst1_z",
                "CRYST1 Z must be None or an exact positive integer",
                location="metadata.pdb.cryst1.z",
            )
        z_token = _integer_token(
            z_value,
            width=4,
            code="unsupported_cryst1_z",
            location="metadata.pdb.cryst1.z",
        )

    length_tokens = tuple(
        _fixed_decimal_token(
            value,
            width=9,
            precision=3,
            kind="cryst1_length",
            location=f"metadata.pdb.cryst1.lengths_angstrom[{index}]",
        )
        for index, value in enumerate(lengths)
    )
    angle_tokens = tuple(
        _fixed_decimal_token(
            value,
            width=7,
            precision=2,
            kind="cryst1_angle",
            location=f"metadata.pdb.cryst1.angles_degrees[{index}]",
        )
        for index, value in enumerate(angles)
    )

    a, b, c = lengths
    alpha_r, beta_r, gamma_r = map(math.radians, angles)
    sin_gamma = math.sin(gamma_r)
    if abs(sin_gamma) <= 1.0e-12:
        raise PdbWriteError(
            "unsupported_cryst1_metadata",
            "CRYST1 gamma produces a singular cell",
            location="metadata.pdb.cryst1.angles_degrees[2]",
        )
    vector_a = (a, 0.0, 0.0)
    vector_b = (b * math.cos(gamma_r), b * sin_gamma, 0.0)
    c_x = c * math.cos(beta_r)
    c_y = c * (math.cos(alpha_r) - math.cos(beta_r) * math.cos(gamma_r)) / sin_gamma
    c_z_squared = c * c - c_x * c_x - c_y * c_y
    if c_z_squared <= 1.0e-12:
        raise PdbWriteError(
            "unsupported_cryst1_metadata",
            "CRYST1 values do not form a positive cell volume",
            location="metadata.pdb.cryst1",
        )
    expected_vectors = torch.tensor(
        [vector_a, vector_b, (c_x, c_y, math.sqrt(c_z_squared))],
        dtype=torch.float64,
    )
    expected_hex = tuple(
        tuple(_binary64_hex(value) for value in row)
        for row in expected_vectors.tolist()
    )
    observed_hex = tuple(
        tuple(_binary64_hex(value) for value in row)
        for row in system.cell.vectors.tolist()
    )
    if observed_hex != expected_hex:
        raise PdbWriteError(
            "cryst1_cell_mismatch",
            "canonical cell vectors do not match parser-owned CRYST1 values bit-for-bit",
            location="cell.vectors",
        )

    line = (
        "CRYST1"
        + "".join(length_tokens)
        + "".join(angle_tokens)
        + " "
        + f"{space_group:<11}"
        + z_token
    ).ljust(_MAX_LINE_CHARS)
    if len(line) != _MAX_LINE_CHARS or any(
        ord(character) < 0x20 or ord(character) > 0x7E for character in line
    ):
        raise PdbWriteError(
            "internal_fixed_column_error",
            "validated CRYST1 state did not produce one printable 80-column line",
            location="metadata.pdb.cryst1",
        )

    document: Mapping[str, Any] = {
        "vectors_ieee754_binary64_be": [list(row) for row in observed_hex],
        "periodic": [False, False, False],
        "lengths_angstrom": list(lengths),
        "lengths_ieee754_binary64_be": [_binary64_hex(value) for value in lengths],
        "length_tokens_f9_3": list(length_tokens),
        "angles_degrees": list(angles),
        "angles_ieee754_binary64_be": [_binary64_hex(value) for value in angles],
        "angle_tokens_f7_2": list(angle_tokens),
        "space_group": space_group,
        "z": z_value,
        "z_token_blank_or_i4": z_token,
        "canonical_line_80": line,
    }
    return _ValidatedCryst1State(line=line, document=document)


def _reconstruct_attached_missingness_report(
    system: AllAtomSystem,
    *,
    topology_sha256: str,
    pdb_metadata: Mapping[str, Any],
) -> SourceReportedMissingnessReport:
    attached = _require_exact_keys(
        pdb_metadata.get("source_reported_missingness"),
        _MISSINGNESS_REPORT_KEYS,
        code="stale_missingness_digest",
        location="metadata.pdb.source_reported_missingness",
    )
    raw_residue_claims = attached.get("missing_residue_claims")
    raw_atom_claims = attached.get("missing_atom_claims")
    if not isinstance(raw_residue_claims, (list, tuple)) or not isinstance(
        raw_atom_claims, (list, tuple)
    ):
        raise PdbWriteError(
            "invalid_missingness_claim",
            "attached missingness claims must be parser-owned sequences",
            location="metadata.pdb.source_reported_missingness",
        )
    try:
        residue_claims: list[SourceReportedMissingResidueClaim] = []
        for index, raw_claim in enumerate(raw_residue_claims):
            claim = _require_exact_keys(
                raw_claim,
                _MISSING_RESIDUE_CLAIM_KEYS,
                code="invalid_missingness_claim",
                location=(
                    "metadata.pdb.source_reported_missingness."
                    f"missing_residue_claims[{index}]"
                ),
            )
            _require_exact_keys(
                claim.get("raw_payload"),
                _MISSING_RESIDUE_RAW_PAYLOAD_KEYS,
                code="invalid_missingness_claim",
                location=(
                    "metadata.pdb.source_reported_missingness."
                    f"missing_residue_claims[{index}].raw_payload"
                ),
            )
            residue_claims.append(
                SourceReportedMissingResidueClaim(
                    source_ordinal=claim["source_ordinal"],
                    source_category=claim["source_category"],
                    source_model_id=claim["source_model_id"],
                    source_chain_id=claim["source_chain_id"],
                    source_residue_id=claim["source_residue_id"],
                    source_residue_name=claim["source_residue_name"],
                    source_insertion_code=claim["source_insertion_code"],
                    raw_payload=_plain_json(claim["raw_payload"]),
                )
            )
        atom_claims: list[SourceReportedMissingAtomClaim] = []
        for index, raw_claim in enumerate(raw_atom_claims):
            claim = _require_exact_keys(
                raw_claim,
                _MISSING_ATOM_CLAIM_KEYS,
                code="invalid_missingness_claim",
                location=(
                    "metadata.pdb.source_reported_missingness."
                    f"missing_atom_claims[{index}]"
                ),
            )
            _require_exact_keys(
                claim.get("raw_payload"),
                _MISSING_ATOM_RAW_PAYLOAD_KEYS,
                code="invalid_missingness_claim",
                location=(
                    "metadata.pdb.source_reported_missingness."
                    f"missing_atom_claims[{index}].raw_payload"
                ),
            )
            atom_claims.append(
                SourceReportedMissingAtomClaim(
                    source_ordinal=claim["source_ordinal"],
                    source_category=claim["source_category"],
                    source_model_id=claim["source_model_id"],
                    source_chain_id=claim["source_chain_id"],
                    source_residue_id=claim["source_residue_id"],
                    source_residue_name=claim["source_residue_name"],
                    source_insertion_code=claim["source_insertion_code"],
                    source_atom_name=claim["source_atom_name"],
                    source_altloc_id=claim["source_altloc_id"],
                    raw_payload=_plain_json(claim["raw_payload"]),
                )
            )
        blockers = attached.get("blockers")
        if not isinstance(blockers, (list, tuple)):
            raise TypeError("missingness blockers must be a sequence")
        report = SourceReportedMissingnessReport(
            policy_id=attached["policy_id"],
            source_format=attached["source_format"],
            source_sha256=attached["source_sha256"],
            canonical_topology_schema_id=attached["canonical_topology_schema_id"],
            canonical_topology_sha256=attached["canonical_topology_sha256"],
            coordinate_scope=attached["coordinate_scope"],
            altloc_status=attached["altloc_status"],
            requested_altloc_id=attached["requested_altloc_id"],
            assembly_status=attached["assembly_status"],
            requested_assembly_id=attached["requested_assembly_id"],
            missing_residue_claims=tuple(residue_claims),
            missing_atom_claims=tuple(atom_claims),
            source_reported_missing_residue_count=attached[
                "source_reported_missing_residue_count"
            ],
            source_reported_missing_atom_count=attached[
                "source_reported_missing_atom_count"
            ],
            blockers=tuple(blockers),
            completion_attempted=attached["completion_attempted"],
            completion_applied=attached["completion_applied"],
            preparation_ready=attached["preparation_ready"],
            claim_safe=attached["claim_safe"],
        )
    except PdbWriteError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise PdbWriteError(
            "invalid_missingness_claim",
            "attached source-reported missingness report is not reconstructable",
            location="metadata.pdb.source_reported_missingness",
        ) from exc
    if (
        attached.get("schema_id") != MISSINGNESS_REPORT_SCHEMA_ID
        or attached.get("report_sha256") != report.report_sha256
        or not _exact_typed_json_equal(_plain_json(attached), report.to_dict())
        or report.source_sha256 != system.provenance.source_sha256
        or report.canonical_topology_sha256 != topology_sha256
    ):
        raise PdbWriteError(
            "stale_missingness_digest",
            "attached source-reported missingness report is stale",
            location="metadata.pdb.source_reported_missingness",
        )
    expected_binding = (
        "pdb",
        "deposited_coordinates",
        "not_present",
        "",
        "not_supported_for_pdb",
        "",
    )
    observed_binding = (
        report.source_format,
        report.coordinate_scope,
        report.altloc_status,
        report.requested_altloc_id,
        report.assembly_status,
        report.requested_assembly_id,
    )
    if observed_binding != expected_binding:
        raise PdbWriteError(
            "unsupported_missingness_evidence_binding",
            "source-reported missingness must retain the exact unselected PDB coordinate binding",
            location="metadata.pdb.source_reported_missingness",
        )
    return report


def _printable_nonspace_ascii(
    value: Any,
    *,
    max_chars: int,
    code: str,
    location: str,
    uppercase: bool = False,
    allow_empty: bool = False,
) -> str:
    text = _ascii_text(
        value,
        max_chars=max_chars,
        code=code,
        location=location,
        allow_empty=allow_empty,
    )
    if text and (
        any(character.isspace() for character in text)
        or (uppercase and text != text.upper())
    ):
        raise PdbWriteError(
            code,
            "value must contain uppercase printable non-whitespace ASCII"
            if uppercase
            else "value must contain printable non-whitespace ASCII",
            location=location,
        )
    return text


def _canonical_residue_number(
    value: Any,
    *,
    width: int,
    location: str,
) -> tuple[int, str]:
    if type(value) is not str or not value:
        raise PdbWriteError(
            "invalid_missingness_identity",
            "residue number must be a canonical decimal string",
            location=location,
        )
    try:
        integer = int(value, 10)
    except ValueError as exc:
        raise PdbWriteError(
            "invalid_missingness_identity",
            "residue number must be a canonical decimal integer",
            location=location,
        ) from exc
    if str(integer) != value:
        raise PdbWriteError(
            "invalid_missingness_identity",
            "residue number must not carry plus signs or leading zeroes",
            location=location,
        )
    return integer, _integer_token(
        integer,
        width=width,
        code="missingness_residue_number_overflow",
        location=location,
    )


def _fixed_integer_field_matches(field: str, value: int) -> bool:
    token = field.strip()
    return (
        bool(token)
        and re.fullmatch(r"[+-]?\d+", token) is not None
        and int(token, 10) == value
    )


def _model_field_matches(source_model_id: str, model_field: Any) -> bool:
    if type(model_field) is not str or len(model_field) != 3:
        return False
    if source_model_id == "":
        return model_field == "   "
    return source_model_id == "1" and _fixed_integer_field_matches(model_field, 1)


def _raw_missingness_records(
    pdb_metadata: Mapping[str, Any],
    *,
    physical_line_upper_bound: int,
) -> tuple[Mapping[str, Any], ...]:
    source = _require_exact_keys(
        pdb_metadata.get("source_missingness"),
        _SOURCE_MISSINGNESS_KEYS,
        code="unsupported_missingness_evidence",
        location="metadata.pdb.source_missingness",
    )
    if source.get("interpretation_policy") != "strict_remark_465_470_preserve_only/v1":
        raise PdbWriteError(
            "unsupported_missingness_evidence",
            "source missingness policy is not the strict preserve-only parser policy",
            location="metadata.pdb.source_missingness.interpretation_policy",
        )
    raw_records = source.get("raw_records")
    if not isinstance(raw_records, (list, tuple)):
        raise PdbWriteError(
            "invalid_missingness_raw_ledger",
            "source missingness raw records must be a parser-owned sequence",
            location="metadata.pdb.source_missingness.raw_records",
        )
    if len(raw_records) > _MAX_MISSINGNESS_REMARK_LINES:
        raise PdbWriteError(
            "missingness_line_limit_exceeded",
            "source missingness remarks exceed the writer line cap",
            location="metadata.pdb.source_missingness.raw_records",
        )
    normalized: list[Mapping[str, Any]] = []
    previous_line_number = 0
    counts = {465: 0, 470: 0}
    for index, raw_record in enumerate(raw_records):
        location = f"metadata.pdb.source_missingness.raw_records[{index}]"
        record = _require_exact_keys(
            raw_record,
            _RAW_MISSINGNESS_RECORD_KEYS,
            code="invalid_missingness_raw_ledger",
            location=location,
        )
        remark_number = record.get("remark_number")
        line_number = record.get("line_number")
        raw_line = record.get("raw_line")
        if type(remark_number) is not int or remark_number not in {465, 470}:
            raise PdbWriteError(
                "invalid_missingness_raw_ledger",
                "raw record remark_number must be exact integer 465 or 470",
                location=f"{location}.remark_number",
            )
        if (
            type(line_number) is not int
            or not previous_line_number < line_number <= physical_line_upper_bound
        ):
            raise PdbWriteError(
                "invalid_missingness_raw_ledger",
                "raw record line numbers must be unique, increasing, and in range",
                location=f"{location}.line_number",
            )
        previous_line_number = line_number
        if (
            type(raw_line) is not str
            or not 10 <= len(raw_line) <= _MAX_LINE_CHARS
            or not raw_line.isascii()
            or any(
                ord(character) < 0x20 or ord(character) > 0x7E for character in raw_line
            )
        ):
            raise PdbWriteError(
                "invalid_missingness_raw_ledger",
                "raw REMARK lines must be one to 80 printable ASCII columns",
                location=f"{location}.raw_line",
            )
        padded = raw_line.ljust(_MAX_LINE_CHARS)
        if (
            padded[:6] != "REMARK"
            or padded[6] != " "
            or padded[7:10] != str(remark_number)
            or padded[10] != " "
        ):
            raise PdbWriteError(
                "invalid_missingness_raw_ledger",
                "raw line does not match its REMARK number",
                location=f"{location}.raw_line",
            )
        counts[remark_number] += 1
        normalized.append(
            {
                "remark_number": remark_number,
                "line_number": line_number,
                "raw_line": raw_line,
            }
        )
    for field_name, expected in (
        ("remark_line_count", len(normalized)),
        ("remark_465_line_count", counts[465]),
        ("remark_470_line_count", counts[470]),
    ):
        if (
            type(source.get(field_name)) is not int
            or source.get(field_name) != expected
        ):
            raise PdbWriteError(
                "invalid_missingness_raw_ledger",
                f"{field_name} does not match the raw record ledger",
                location=f"metadata.pdb.source_missingness.{field_name}",
            )
    return tuple(normalized)


def _is_missingness_table_header(remark_number: int, padded: str) -> bool:
    if remark_number == 465:
        return (
            padded[11:14] == "  M"
            and padded[15:18] == "RES"
            and padded[19] == "C"
            and padded[21:26] == "SSSEQ"
            and padded[26] == "I"
            and not padded[27:].strip()
        )
    return (
        padded[11:14] == "  M"
        and padded[15:18] == "RES"
        and padded[20] == "C"
        and padded[21:25] == "SSEQ"
        and padded[25] == "I"
        and padded[28:33] == "ATOMS"
        and not padded[33:].strip()
    )


def _is_missingness_boilerplate(padded: str) -> bool:
    content = padded[11:].strip().upper()
    return not content or content.startswith(
        (
            "MISSING ",
            "THE FOLLOWING ",
            "EXPERIMENT.",
            "IDENTIFIER;",
            "RES=RESIDUE NAME;",
            "C=CHAIN IDENTIFIER;",
            "I=INSERTION CODE",
            "SSSEQ=SEQUENCE NUMBER;",
        )
    )


def _validate_missingness_claims_and_build_semantics(
    system: AllAtomSystem,
    *,
    report: SourceReportedMissingnessReport,
    raw_records: tuple[Mapping[str, Any], ...],
    model_ids: tuple[int, ...],
) -> tuple[Mapping[str, Any], tuple[str, ...]]:
    residue_claims = report.missing_residue_claims
    atom_claims = report.missing_atom_claims
    evidence_present = bool(residue_claims or atom_claims)
    if bool(raw_records) != evidence_present:
        raise PdbWriteError(
            "header_only_missingness_evidence",
            "REMARK 465/470 evidence requires at least one typed claim",
            location="metadata.pdb.source_missingness",
        )
    if evidence_present and (
        system.model_count != 1 or model_ids != (1,) or system.bonds
    ):
        raise PdbWriteError(
            "unsupported_missingness_model_scope",
            "missingness emission requires exactly one bondless coordinate model with ID 1",
            location="provenance.metadata.model_ids",
        )
    record_by_line = {int(record["line_number"]): record for record in raw_records}
    residue_claim_lines: set[int] = set()
    atom_claim_lines: dict[int, set[int]] = {}
    residue_documents: list[Mapping[str, Any]] = []
    atom_documents: list[Mapping[str, Any]] = []
    residue_keys: set[tuple[str, int, str, str]] = set()
    residue_name_by_locator: dict[tuple[str, int, str], str] = {}
    atom_keys: set[tuple[str, int, str, str, str]] = set()
    previous_residue_line_number = 0
    previous_atom_source_position = (0, 0)

    present_residues = {
        (
            system.chains[residue.chain_index].chain_id,
            residue.sequence_number,
            residue.name,
            residue.insertion_code,
        )
        for residue in system.residues
    }
    present_residue_locators = {
        (chain_id, residue_number, insertion_code)
        for chain_id, residue_number, _residue_name, insertion_code in present_residues
    }
    present_atoms = {
        (
            system.chains[system.residues[atom.residue_index].chain_index].chain_id,
            system.residues[atom.residue_index].sequence_number,
            system.residues[atom.residue_index].name,
            system.residues[atom.residue_index].insertion_code,
            atom.name,
        )
        for atom in system.atoms
    }

    for index, claim in enumerate(residue_claims):
        location = f"missing_residue_claims[{index}]"
        if (
            claim.source_ordinal != index + 1
            or claim.source_category != "PDB_REMARK_465"
        ):
            raise PdbWriteError(
                "invalid_missingness_claim_order",
                "REMARK 465 claims require sequential ordinals and the exact source category",
                location=location,
            )
        if claim.source_model_id not in {"", "1"}:
            raise PdbWriteError(
                "unsupported_missingness_model_scope",
                "REMARK 465 model scope must normalize to model 1",
                location=f"{location}.source_model_id",
            )
        residue_name = _printable_nonspace_ascii(
            claim.source_residue_name,
            max_chars=3,
            uppercase=True,
            code="invalid_missingness_identity",
            location=f"{location}.source_residue_name",
        )
        chain_id = _printable_nonspace_ascii(
            claim.source_chain_id,
            max_chars=1,
            allow_empty=True,
            code="invalid_missingness_identity",
            location=f"{location}.source_chain_id",
        )
        insertion_code = _printable_nonspace_ascii(
            claim.source_insertion_code,
            max_chars=1,
            allow_empty=True,
            code="invalid_missingness_identity",
            location=f"{location}.source_insertion_code",
        )
        residue_number, _ = _canonical_residue_number(
            claim.source_residue_id,
            width=5,
            location=f"{location}.source_residue_id",
        )
        raw_payload = claim.raw_payload
        line_number = raw_payload.get("line_number")
        raw_line = raw_payload.get("raw_line")
        model_field = raw_payload.get("model_field")
        if (
            type(line_number) is not int
            or line_number in residue_claim_lines
            or record_by_line.get(line_number)
            != {"remark_number": 465, "line_number": line_number, "raw_line": raw_line}
        ):
            raise PdbWriteError(
                "missingness_raw_claim_mismatch",
                "REMARK 465 claim is not bound to exactly one raw ledger row",
                location=f"{location}.raw_payload",
            )
        if line_number <= previous_residue_line_number:
            raise PdbWriteError(
                "invalid_missingness_claim_order",
                "REMARK 465 raw line numbers must follow typed claim order",
                location=f"{location}.raw_payload.line_number",
            )
        previous_residue_line_number = line_number
        if not _model_field_matches(claim.source_model_id, model_field):
            raise PdbWriteError(
                "unsupported_missingness_model_scope",
                "REMARK 465 raw model field does not match the typed claim",
                location=f"{location}.raw_payload.model_field",
            )
        scope = raw_payload.get("target_model_scope")
        if not isinstance(scope, Mapping) or not _exact_typed_json_equal(
            _plain_json(scope),
            {
                "kind": "explicit_model_ids",
                "model_ids": [1],
                "count": 1,
            },
        ):
            raise PdbWriteError(
                "unsupported_missingness_model_scope",
                "NMR ranges and non-ID1 missingness scopes are unsupported",
                location=f"{location}.raw_payload.target_model_scope",
            )
        if type(raw_line) is not str:
            raise PdbWriteError(
                "missingness_raw_claim_mismatch",
                "REMARK 465 raw line must be exact text",
                location=f"{location}.raw_payload.raw_line",
            )
        padded = raw_line.ljust(_MAX_LINE_CHARS)
        if (
            padded[11:14] != model_field
            or padded[14] != " "
            or padded[15:18].strip() != residue_name
            or padded[18] != " "
            or padded[19].strip() != chain_id
            or padded[20] != " "
            or not _fixed_integer_field_matches(padded[21:26], residue_number)
            or padded[26].strip() != insertion_code
            or padded[27:].strip()
        ):
            raise PdbWriteError(
                "missingness_raw_claim_mismatch",
                "typed REMARK 465 claim does not match its fixed-column raw row",
                location=f"{location}.raw_payload.raw_line",
            )
        key = (chain_id, residue_number, residue_name, insertion_code)
        locator = (chain_id, residue_number, insertion_code)
        if key in residue_keys:
            raise PdbWriteError(
                "duplicate_missingness_claim",
                "duplicate normalized REMARK 465 claim",
                location=location,
            )
        prior_name = residue_name_by_locator.get(locator)
        if prior_name is not None and prior_name != residue_name:
            raise PdbWriteError(
                "ambiguous_missing_residue_identity",
                "one REMARK 465 residue locator cannot carry multiple residue names",
                location=location,
            )
        if locator in present_residue_locators:
            raise PdbWriteError(
                "missing_residue_present_in_coordinates",
                "REMARK 465 locator is present in coordinates regardless of residue-name spelling",
                location=location,
            )
        residue_keys.add(key)
        residue_name_by_locator[locator] = residue_name
        residue_claim_lines.add(line_number)
        residue_documents.append(
            {
                "order": index + 1,
                "model_id": 1,
                "chain_id": chain_id,
                "residue_number": residue_number,
                "residue_name": residue_name,
                "insertion_code": insertion_code,
            }
        )

    for index, claim in enumerate(atom_claims):
        location = f"missing_atom_claims[{index}]"
        if (
            claim.source_ordinal != index + 1
            or claim.source_category != "PDB_REMARK_470"
        ):
            raise PdbWriteError(
                "invalid_missingness_claim_order",
                "REMARK 470 claims require sequential ordinals and the exact source category",
                location=location,
            )
        if claim.source_model_id not in {"", "1"} or claim.source_altloc_id != "":
            raise PdbWriteError(
                "unsupported_missingness_model_scope",
                "REMARK 470 claims require model 1 and blank atom altloc",
                location=location,
            )
        residue_name = _printable_nonspace_ascii(
            claim.source_residue_name,
            max_chars=3,
            uppercase=True,
            code="invalid_missingness_identity",
            location=f"{location}.source_residue_name",
        )
        chain_id = _printable_nonspace_ascii(
            claim.source_chain_id,
            max_chars=1,
            allow_empty=True,
            code="invalid_missingness_identity",
            location=f"{location}.source_chain_id",
        )
        insertion_code = _printable_nonspace_ascii(
            claim.source_insertion_code,
            max_chars=1,
            allow_empty=True,
            code="invalid_missingness_identity",
            location=f"{location}.source_insertion_code",
        )
        atom_name = _printable_nonspace_ascii(
            claim.source_atom_name,
            max_chars=4,
            code="invalid_missingness_identity",
            location=f"{location}.source_atom_name",
        )
        residue_number, _ = _canonical_residue_number(
            claim.source_residue_id,
            width=4,
            location=f"{location}.source_residue_id",
        )
        raw_payload = claim.raw_payload
        line_number = raw_payload.get("line_number")
        raw_line = raw_payload.get("raw_line")
        atom_position = raw_payload.get("atom_position_in_row")
        model_field = raw_payload.get("model_field")
        if (
            type(line_number) is not int
            or record_by_line.get(line_number)
            != {"remark_number": 470, "line_number": line_number, "raw_line": raw_line}
            or type(atom_position) is not int
            or atom_position < 1
        ):
            raise PdbWriteError(
                "missingness_raw_claim_mismatch",
                "REMARK 470 claim is not bound to one exact raw ledger atom position",
                location=f"{location}.raw_payload",
            )
        source_position = (line_number, atom_position)
        if source_position <= previous_atom_source_position:
            raise PdbWriteError(
                "invalid_missingness_claim_order",
                "REMARK 470 claims must follow raw line and atom-position order",
                location=f"{location}.raw_payload",
            )
        previous_atom_source_position = source_position
        if not _model_field_matches(claim.source_model_id, model_field):
            raise PdbWriteError(
                "unsupported_missingness_model_scope",
                "REMARK 470 raw model field does not match the typed claim",
                location=f"{location}.raw_payload.model_field",
            )
        scope = raw_payload.get("target_model_scope")
        if not isinstance(scope, Mapping) or not _exact_typed_json_equal(
            _plain_json(scope),
            {
                "kind": "explicit_model_ids",
                "model_ids": [1],
                "count": 1,
            },
        ):
            raise PdbWriteError(
                "unsupported_missingness_model_scope",
                "NMR ranges and non-ID1 missingness scopes are unsupported",
                location=f"{location}.raw_payload.target_model_scope",
            )
        if type(raw_line) is not str:
            raise PdbWriteError(
                "missingness_raw_claim_mismatch",
                "REMARK 470 raw line must be exact text",
                location=f"{location}.raw_payload.raw_line",
            )
        padded = raw_line.ljust(_MAX_LINE_CHARS)
        atom_names = padded[28:].split()
        if (
            padded[11:14] != model_field
            or padded[14] != " "
            or padded[15:18].strip() != residue_name
            or padded[18:20] != "  "
            or padded[20].strip() != chain_id
            or not _fixed_integer_field_matches(padded[21:25], residue_number)
            or padded[25].strip() != insertion_code
            or padded[26:28] != "  "
            or atom_position > len(atom_names)
            or atom_names[atom_position - 1] != atom_name
        ):
            raise PdbWriteError(
                "missingness_raw_claim_mismatch",
                "typed REMARK 470 claim does not match its fixed-column raw row",
                location=f"{location}.raw_payload.raw_line",
            )
        positions = atom_claim_lines.setdefault(line_number, set())
        if atom_position in positions:
            raise PdbWriteError(
                "duplicate_missingness_claim",
                "duplicate REMARK 470 atom position",
                location=location,
            )
        positions.add(atom_position)
        residue_key = (chain_id, residue_number, residue_name, insertion_code)
        key = (*residue_key, atom_name)
        if key in atom_keys:
            raise PdbWriteError(
                "duplicate_missingness_claim",
                "duplicate normalized REMARK 470 claim",
                location=location,
            )
        if residue_key not in present_residues:
            raise PdbWriteError(
                "missing_atom_residue_absent",
                "REMARK 470 references a residue absent from coordinates",
                location=location,
            )
        if key in present_atoms:
            raise PdbWriteError(
                "declared_missing_atom_present",
                "REMARK 470 declares an atom present in coordinates",
                location=location,
            )
        atom_keys.add(key)
        atom_documents.append(
            {
                "order": index + 1,
                "model_id": 1,
                "chain_id": chain_id,
                "residue_number": residue_number,
                "residue_name": residue_name,
                "insertion_code": insertion_code,
                "atom_name": atom_name,
                "atom_altloc_id": "",
            }
        )

    for line_number, positions in atom_claim_lines.items():
        raw_line = str(record_by_line[line_number]["raw_line"])
        expected_positions = set(range(1, len(raw_line.ljust(80)[28:].split()) + 1))
        if positions != expected_positions:
            raise PdbWriteError(
                "missingness_raw_claim_mismatch",
                "REMARK 470 typed claims do not cover every atom in the raw row",
                location=f"metadata.pdb.source_missingness.raw_records.line[{line_number}]",
            )

    claimed_lines = residue_claim_lines | set(atom_claim_lines)
    for record in raw_records:
        line_number = int(record["line_number"])
        padded = str(record["raw_line"]).ljust(_MAX_LINE_CHARS)
        if padded[11:].lstrip().upper().startswith("MODELS"):
            raise PdbWriteError(
                "unsupported_missingness_model_scope",
                "NMR REMARK model ranges are outside the writer profile",
                location=f"metadata.pdb.source_missingness.raw_records.line[{line_number}]",
            )
        if line_number in claimed_lines:
            continue
        if not (
            _is_missingness_table_header(int(record["remark_number"]), padded)
            or _is_missingness_boilerplate(padded)
        ):
            raise PdbWriteError(
                "missingness_raw_claim_mismatch",
                "raw missingness data row has no matching typed claim",
                location=f"metadata.pdb.source_missingness.raw_records.line[{line_number}]",
            )

    semantic_document: Mapping[str, Any] = {
        "schema_id": PDB_MISSINGNESS_SEMANTIC_SCHEMA_ID,
        "profile_id": PDB_MISSINGNESS_PROFILE_ID,
        "preservation_policy_id": MISSINGNESS_PRESERVATION_POLICY_ID,
        "evidence_present": evidence_present,
        "evidence_status": (
            "present_fully_preserved" if evidence_present else "not_present"
        ),
        "coordinate_scope": "deposited_coordinates",
        "normalized_model_ids": [1] if evidence_present else [],
        "ordered_missing_residue_claims": residue_documents,
        "ordered_missing_atom_claims": atom_documents,
        "missing_residue_claim_count": len(residue_documents),
        "missing_atom_claim_count": len(atom_documents),
        "total_claim_count": len(residue_documents) + len(atom_documents),
        "source_reported_claims_only": True,
        "actual_completeness_assessed": False,
        "seqres_or_reference_membership_assessed": False,
        "completion_attempted": False,
        "completion_applied": False,
        "preparation_ready": False,
        "claim_safe": False,
    }

    lines: list[str] = []
    if residue_documents:
        lines.append("REMARK 465 MISSING RESIDUES".ljust(80))
        header = [" "] * 80
        header[0:6] = "REMARK"
        header[7:10] = "465"
        header[11:14] = "  M"
        header[15:18] = "RES"
        header[19] = "C"
        header[21:26] = "SSSEQ"
        header[26] = "I"
        lines.append("".join(header))
        for document in residue_documents:
            line = [" "] * 80
            line[0:6] = "REMARK"
            line[7:10] = "465"
            line[15:18] = f"{document['residue_name']:>3}"
            line[19] = str(document["chain_id"] or " ")
            line[21:26] = f"{document['residue_number']:5d}"
            line[26] = str(document["insertion_code"] or " ")
            lines.append("".join(line))
    if atom_documents:
        lines.append("REMARK 470 MISSING ATOM".ljust(80))
        header = [" "] * 80
        header[0:6] = "REMARK"
        header[7:10] = "470"
        header[11:14] = "  M"
        header[15:18] = "RES"
        header[20] = "C"
        header[21:25] = "SSEQ"
        header[25] = "I"
        header[28:33] = "ATOMS"
        lines.append("".join(header))
        for document in atom_documents:
            line = [" "] * 80
            line[0:6] = "REMARK"
            line[7:10] = "470"
            line[15:18] = f"{document['residue_name']:>3}"
            line[20] = str(document["chain_id"] or " ")
            line[21:25] = f"{document['residue_number']:4d}"
            line[25] = str(document["insertion_code"] or " ")
            atom_name = str(document["atom_name"])
            line[28 : 28 + len(atom_name)] = atom_name
            lines.append("".join(line))
    if len(lines) > _MAX_MISSINGNESS_REMARK_LINES:
        raise PdbWriteError(
            "missingness_line_limit_exceeded",
            "canonical REMARK 465/470 output exceeds the 20,000-line cap",
        )
    if any(
        len(line) != 80
        or not line.isascii()
        or any(ord(character) < 0x20 or ord(character) > 0x7E for character in line)
        for line in lines
    ):
        raise PdbWriteError(
            "internal_fixed_column_error",
            "validated missingness state did not produce printable 80-column lines",
        )
    return semantic_document, tuple(lines)


def _expected_coverage_document(
    system: AllAtomSystem,
    *,
    topology_sha256: str,
    missingness_report: SourceReportedMissingnessReport,
    evidence_present: bool,
    cryst1: _ValidatedCryst1State | None,
) -> dict[str, Any]:
    atom_count = system.atom_count
    model_count = system.model_count
    unknown_formal_charge_count = sum(
        not atom.formal_charge_known for atom in system.atoms
    )
    unknown_entity_type_count = sum(
        residue.entity_type == "unknown" for residue in system.residues
    )
    blockers = list(_COVERAGE_BASE_BLOCKERS)
    if unknown_formal_charge_count:
        blockers.append("formal_charge_unknown_for_some_atoms")
    if unknown_entity_type_count:
        blockers.append("entity_type_unknown_for_some_residues")
    if missingness_report.missing_residue_claims:
        blockers.append("source_reports_missing_residues")
    if missingness_report.missing_atom_claims:
        blockers.append("source_reports_missing_atoms")
    if evidence_present:
        blockers.append("source_missingness_seqres_membership_not_assessed")
    if cryst1 is not None:
        blockers.append("crystallographic_cell_not_simulation_box")
        space_group = str(cryst1.document["space_group"])
        if space_group.replace(" ", "").upper() != "P1":
            blockers.append("crystallographic_symmetry_not_expanded")
    return {
        "source_format": "pdb",
        "support_scope": STRUCTURE_INGEST_SUPPORT_SCOPE,
        "supported": True,
        "syntax_ingest_supported": True,
        "preparation_ready": False,
        "claim_safe": False,
        "atom_count": atom_count,
        "bond_count": 0,
        "residue_count": len(system.residues),
        "chain_count": len(system.chains),
        "model_count": model_count,
        "explicit_hydrogen_count": sum(atom.element == "H" for atom in system.atoms),
        "hetero_residue_count": sum(residue.hetero for residue in system.residues),
        "cell_present": cryst1 is not None,
        "unknown_formal_charge_count": unknown_formal_charge_count,
        "unknown_entity_type_count": unknown_entity_type_count,
        "uninterpreted_category_count": 0,
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "canonical_topology_sha256": topology_sha256,
        "source_atom_row_count": atom_count * model_count,
        "altloc_status": "not_present",
        "requested_altloc_id": "",
        "altloc_affected_residue_count": 0,
        "altloc_kept_row_count": atom_count * model_count,
        "altloc_discarded_row_count": 0,
        "coordinate_scope": "deposited_coordinates",
        "assembly_status": "not_supported_for_pdb",
        "requested_assembly_id": "",
        "assembly_operation_sequence_count": 0,
        "assembly_operation_application_count": 0,
        "assembly_chain_instance_count": 0,
        "assembly_output_atom_count": 0,
        "missingness_evidence_status": (
            "present_fully_preserved" if evidence_present else "not_present"
        ),
        "source_reported_missing_residue_claim_count": len(
            missingness_report.missing_residue_claims
        ),
        "source_reported_missing_atom_claim_count": len(
            missingness_report.missing_atom_claims
        ),
        "source_missingness_evidence_schema_id": MISSINGNESS_REPORT_SCHEMA_ID,
        "source_missingness_evidence_sha256": missingness_report.report_sha256,
        "missingness_completion_policy_id": MISSINGNESS_PRESERVATION_POLICY_ID,
        "missingness_completion_status": "not_assessed",
        "blockers": blockers,
    }


def _validate_provenance_and_metadata(
    system: AllAtomSystem,
    *,
    cryst1: _ValidatedCryst1State | None,
) -> tuple[
    tuple[int, ...],
    Mapping[str, Any],
    SourceReportedMissingnessReport,
    tuple[Mapping[str, Any], ...],
]:
    provenance = system.provenance
    if provenance.source_format != "pdb":
        raise PdbWriteError(
            "unsupported_source_format",
            "writer accepts only strict PDB parser output",
            location="provenance.source_format",
        )
    if (
        provenance.parser_name != _PDB_PARSER_NAME
        or provenance.parser_version != PDB_PARSER_VERSION
    ):
        raise PdbWriteError(
            "unsupported_parser_pedigree",
            "writer requires the current strict PDB parser pedigree",
            location="provenance",
        )
    if "select_explicit_altloc_id/v1" in provenance.operations:
        raise PdbWriteError(
            "unsupported_altloc_selection",
            "strict PDB writer v1 does not emit selected alternate locations",
            location="provenance.operations",
        )
    if provenance.operations not in {
        _PARSER_OPERATIONS,
        _PARSER_OPERATIONS_WITH_MISSINGNESS,
    }:
        raise PdbWriteError(
            "unsupported_provenance_operations",
            "provenance operations are not a supported no-altloc parser ledger",
            location="provenance.operations",
        )
    if provenance.parent_sha256:
        raise PdbWriteError(
            "unsupported_parent_provenance",
            "parser-owned PDB state must not carry parent source hashes",
            location="provenance.parent_sha256",
        )
    if provenance.preparation_ready or provenance.claim_safe:
        raise PdbWriteError(
            "unsupported_authority_state",
            "PDB source writing cannot preserve preparation or claim authority",
            location="provenance",
        )
    if _SHA256_RE.fullmatch(provenance.source_sha256) is None:
        raise PdbWriteError(
            "unsupported_source_provenance",
            "parser source SHA-256 is missing or malformed",
            location="provenance.source_sha256",
        )

    provenance_metadata = _require_exact_keys(
        provenance.metadata,
        _PROVENANCE_METADATA_KEYS,
        code="unsupported_provenance_metadata",
        location="provenance.metadata",
    )
    topology_sha256 = canonical_topology_sha256(system)
    if (
        provenance_metadata.get("canonical_topology_schema_id")
        != CANONICAL_TOPOLOGY_SCHEMA_ID
        or provenance_metadata.get("canonical_topology_sha256") != topology_sha256
        or not attached_canonical_topology_sha256_matches(system)
    ):
        raise PdbWriteError(
            "stale_canonical_topology_digest",
            "attached canonical topology digest does not match current state",
            location="provenance.metadata.canonical_topology_sha256",
        )
    if provenance_metadata.get(
        "parser_observation_schema_id"
    ) != PARSER_OBSERVATION_SCHEMA_ID or not attached_parser_observation_sha256_matches(
        system
    ):
        raise PdbWriteError(
            "stale_parser_observation_digest",
            "attached parser-observation digest does not match current state",
            location="provenance.metadata.parser_observation_sha256",
        )

    raw_model_ids = provenance_metadata.get("model_ids")
    if not isinstance(raw_model_ids, (list, tuple)):
        raise PdbWriteError(
            "unsupported_model_id",
            "model_ids must be a parser-owned sequence",
            location="provenance.metadata.model_ids",
        )
    model_ids = tuple(raw_model_ids)
    if (
        len(model_ids) != system.model_count
        or len(model_ids) < 1
        or any(type(value) is not int or not 1 <= value <= 9_999 for value in model_ids)
        or len(set(model_ids)) != len(model_ids)
    ):
        raise PdbWriteError(
            "unsupported_model_id",
            "model IDs must be unique I4-positive values matching coordinate models",
            location="provenance.metadata.model_ids",
        )

    system_metadata = _require_exact_keys(
        system.metadata,
        frozenset({"pdb"}),
        code="unsupported_system_metadata",
        location="metadata",
    )
    pdb_metadata = _require_exact_keys(
        system_metadata["pdb"],
        _PDB_METADATA_KEYS,
        code="unsupported_pdb_metadata",
        location="metadata.pdb",
    )
    if (pdb_metadata.get("cryst1") is None) != (cryst1 is None):
        raise PdbWriteError(
            "cryst1_state_mismatch",
            "canonical cell and parser-owned CRYST1 metadata must be present together",
            location="metadata.pdb.cryst1",
        )
    expected_altloc = {
        "status": "not_present",
        "requested_altloc_id": "",
        "models": [],
    }
    altloc_selection = pdb_metadata.get("altloc_selection")
    if not isinstance(altloc_selection, Mapping) or not _exact_typed_json_equal(
        _plain_json(altloc_selection), expected_altloc
    ):
        raise PdbWriteError(
            "unsupported_altloc_selection",
            "strict PDB writer v1 requires parser-owned no-altloc state",
            location="metadata.pdb.altloc_selection",
        )
    resource_limits = pdb_metadata.get("resource_limits")
    if not isinstance(resource_limits, Mapping) or not _exact_typed_json_equal(
        _plain_json(resource_limits), _RESOURCE_LIMITS
    ):
        raise PdbWriteError(
            "unsupported_resource_metadata",
            "PDB parser resource limits are missing or stale",
            location="metadata.pdb.resource_limits",
        )
    resource_usage = _require_exact_keys(
        pdb_metadata.get("resource_usage"),
        _RESOURCE_USAGE_KEYS,
        code="unsupported_resource_metadata",
        location="metadata.pdb.resource_usage",
    )
    for field_name, upper_bound in (
        ("input_bytes", _RESOURCE_LIMITS["input_bytes"]),
        ("physical_line_upper_bound", _RESOURCE_LIMITS["physical_lines"]),
    ):
        value = resource_usage.get(field_name)
        if type(value) is not int or not 1 <= value <= upper_bound:
            raise PdbWriteError(
                "unsupported_resource_metadata",
                f"{field_name} is outside the parser limit",
                location=f"metadata.pdb.resource_usage.{field_name}",
            )
    expected_atom_rows = system.atom_count * system.model_count
    if (
        type(resource_usage.get("atom_rows")) is not int
        or resource_usage.get("atom_rows") != expected_atom_rows
    ):
        raise PdbWriteError(
            "unsupported_resource_metadata",
            "source atom-row usage does not match the no-altloc model state",
            location="metadata.pdb.resource_usage.atom_rows",
        )
    physical_line_upper_bound = resource_usage.get("physical_line_upper_bound")
    if type(physical_line_upper_bound) is not int:  # guarded above
        raise PdbWriteError(
            "unsupported_resource_metadata",
            "physical line bound must be an exact integer",
            location="metadata.pdb.resource_usage.physical_line_upper_bound",
        )
    expected_missingness = _reconstruct_attached_missingness_report(
        system,
        topology_sha256=topology_sha256,
        pdb_metadata=pdb_metadata,
    )
    raw_records = _raw_missingness_records(
        pdb_metadata,
        physical_line_upper_bound=physical_line_upper_bound,
    )
    expected_resource_missingness = {
        "missingness_remark_lines": len(raw_records),
        "missing_residue_claims": len(expected_missingness.missing_residue_claims),
        "missing_atom_claims": len(expected_missingness.missing_atom_claims),
        "total_missingness_claims": (
            len(expected_missingness.missing_residue_claims)
            + len(expected_missingness.missing_atom_claims)
        ),
    }
    for field_name, expected in expected_resource_missingness.items():
        if (
            type(resource_usage.get(field_name)) is not int
            or resource_usage.get(field_name) != expected
        ):
            raise PdbWriteError(
                "unsupported_resource_metadata",
                "missingness resource usage does not match the typed/raw ledger",
                location=f"metadata.pdb.resource_usage.{field_name}",
            )
    evidence_present = bool(raw_records)
    expected_operations = (
        _PARSER_OPERATIONS_WITH_MISSINGNESS if evidence_present else _PARSER_OPERATIONS
    )
    if provenance.operations != expected_operations:
        raise PdbWriteError(
            "unsupported_provenance_operations",
            "missingness operation ledger does not match typed evidence presence",
            location="provenance.operations",
        )
    if (
        provenance_metadata.get("source_missingness_evidence_schema_id")
        != MISSINGNESS_REPORT_SCHEMA_ID
        or provenance_metadata.get("source_missingness_evidence_sha256")
        != expected_missingness.report_sha256
    ):
        raise PdbWriteError(
            "stale_missingness_digest",
            "attached missingness digest does not match the reconstructed report",
            location="provenance.metadata.source_missingness_evidence_sha256",
        )
    expected_coverage = _expected_coverage_document(
        system,
        topology_sha256=topology_sha256,
        missingness_report=expected_missingness,
        evidence_present=evidence_present,
        cryst1=cryst1,
    )
    coverage = provenance_metadata.get("coverage")
    if not isinstance(coverage, Mapping) or not _exact_typed_json_equal(
        _plain_json(coverage), expected_coverage
    ):
        raise PdbWriteError(
            "stale_pdb_coverage",
            "attached PDB coverage does not match current parser-owned state",
            location="provenance.metadata.coverage",
        )
    return model_ids, pdb_metadata, expected_missingness, raw_records


def _validate_atoms_residues_chains(
    system: AllAtomSystem,
) -> tuple[
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    seen_serials: set[int] = set()
    seen_atom_sites: set[tuple[str, int, str, str, str]] = set()
    atom_indices_by_residue: list[list[int]] = [[] for _ in system.residues]
    residue_indices_by_chain: list[list[int]] = [[] for _ in system.chains]
    seen_residue_indices: set[int] = set()
    seen_chain_indices: set[int] = set()
    chain_indices_in_atom_order: list[int] = []
    atom_documents: list[Mapping[str, Any]] = []
    occupancy_tokens: list[str] = []
    b_factor_tokens: list[str] = []
    charge_tokens: list[str] = []

    for atom in system.atoms:
        location = f"atoms[{atom.index}]"
        metadata = _require_exact_keys(
            atom.metadata,
            _ATOM_METADATA_KEYS,
            code="unsupported_atom_metadata",
            location=f"{location}.metadata",
        )
        if atom.serial is None or not 1 <= atom.serial <= 99_999:
            raise PdbWriteError(
                "unsupported_atom_serial",
                "PDB atom serial must be an I5-positive value",
                location=f"{location}.serial",
            )
        if atom.serial in seen_serials:
            raise PdbWriteError(
                "unsupported_atom_serial",
                "PDB atom serials must be unique within each model",
                location=f"{location}.serial",
            )
        seen_serials.add(atom.serial)
        _integer_token(
            atom.serial,
            width=5,
            code="unsupported_atom_serial",
            location=f"{location}.serial",
        )

        record = metadata.get("source_record")
        if record not in {"ATOM", "HETATM"}:
            raise PdbWriteError(
                "unsupported_record_class",
                "source_record must be ATOM or HETATM",
                location=f"{location}.metadata.source_record",
            )
        raw_name = metadata.get("pdb_atom_name_field")
        if type(raw_name) is not str or len(raw_name) != 4:
            raise PdbWriteError(
                "unsupported_atom_name_field",
                "pdb_atom_name_field must preserve exactly four columns",
                location=f"{location}.metadata.pdb_atom_name_field",
            )
        _ascii_text(
            raw_name,
            max_chars=4,
            code="unsupported_atom_name_field",
            location=f"{location}.metadata.pdb_atom_name_field",
        )
        if not raw_name.strip() or raw_name.strip() != atom.name:
            raise PdbWriteError(
                "unsupported_atom_name_field",
                "raw PDB atom-name field does not match the canonical atom name",
                location=f"{location}.metadata.pdb_atom_name_field",
            )
        residue = system.residues[atom.residue_index]
        chain = system.chains[residue.chain_index]
        atom_site = (
            chain.chain_id,
            residue.sequence_number,
            residue.insertion_code,
            residue.name,
            atom.name,
        )
        if atom_site in seen_atom_sites:
            raise PdbWriteError(
                "duplicate_atom_identity",
                "PDB atom-site identity must be unique before emission",
                location=location,
            )
        seen_atom_sites.add(atom_site)
        atom_indices_by_residue[residue.index].append(atom.index)
        if chain.index not in seen_chain_indices:
            seen_chain_indices.add(chain.index)
            chain_indices_in_atom_order.append(chain.index)
        if residue.index not in seen_residue_indices:
            seen_residue_indices.add(residue.index)
            residue_indices_by_chain[chain.index].append(residue.index)
        if atom.altloc or metadata.get("pdb_altloc") != "":
            raise PdbWriteError(
                "unsupported_altloc_selection",
                "strict PDB writer v1 requires blank atom altloc state",
                location=f"{location}.altloc",
            )
        segment_id = _ascii_text(
            metadata.get("pdb_segment_id"),
            max_chars=4,
            code="unsupported_atom_metadata",
            location=f"{location}.metadata.pdb_segment_id",
            allow_empty=True,
        )
        if segment_id != segment_id.strip():
            raise PdbWriteError(
                "unsupported_atom_metadata",
                "parser-owned segment ID must already be stripped",
                location=f"{location}.metadata.pdb_segment_id",
            )

        expected_hydrogen_origin = "source" if atom.element == "H" else "not_hydrogen"
        if metadata.get("hydrogen_origin") != expected_hydrogen_origin:
            raise PdbWriteError(
                "unsupported_atom_metadata",
                "hydrogen origin marker does not match the element",
                location=f"{location}.metadata.hydrogen_origin",
            )
        if atomic_number_for_element(atom.element) != atom.atomic_number:
            raise PdbWriteError(
                "unsupported_element",
                "element and atomic number do not match",
                location=f"{location}.element",
            )
        element = _ascii_text(
            atom.element,
            max_chars=2,
            code="unsupported_element",
            location=f"{location}.element",
        )
        if atom.partial_charge_e is not None:
            raise PdbWriteError(
                "unsupported_partial_charge",
                "PDB writer cannot preserve partial charge",
                location=f"{location}.partial_charge_e",
            )
        if atom.mass_da is not None:
            raise PdbWriteError(
                "unsupported_atom_mass",
                "PDB writer cannot preserve atom mass",
                location=f"{location}.mass_da",
            )
        if atom.isotope_mass_number is not None:
            raise PdbWriteError(
                "unsupported_isotope",
                "PDB writer cannot preserve isotope mass number",
                location=f"{location}.isotope_mass_number",
            )
        if atom.atom_map is not None:
            raise PdbWriteError(
                "unsupported_atom_map",
                "PDB writer cannot preserve atom-map state",
                location=f"{location}.atom_map",
            )
        if atom.aromatic:
            raise PdbWriteError(
                "unsupported_aromatic_atom",
                "strict PDB parser does not produce aromatic atom state",
                location=f"{location}.aromatic",
            )
        if atom.stereo != "unspecified":
            raise PdbWriteError(
                "unsupported_atom_stereo",
                "strict PDB parser does not produce atom stereochemistry",
                location=f"{location}.stereo",
            )

        metadata_charge_known = metadata.get("formal_charge_known")
        if metadata_charge_known is not atom.formal_charge_known:
            raise PdbWriteError(
                "unsupported_formal_charge",
                "formal-charge known marker disagrees with canonical state",
                location=f"{location}.formal_charge_known",
            )
        if atom.formal_charge_known:
            if atom.formal_charge == 0:
                raise PdbWriteError(
                    "known_neutral_charge",
                    "PDB columns 79-80 cannot encode known neutral charge",
                    location=f"{location}.formal_charge",
                )
            if not 1 <= abs(atom.formal_charge) <= 9:
                raise PdbWriteError(
                    "unsupported_formal_charge",
                    "explicit PDB formal charge must have magnitude 1 through 9",
                    location=f"{location}.formal_charge",
                )
            if (
                metadata.get("formal_charge_source") != "pdb_columns_79_80"
                or metadata.get("formal_charge_interpretation") != "explicit"
            ):
                raise PdbWriteError(
                    "unsupported_formal_charge",
                    "explicit formal-charge source markers are stale",
                    location=f"{location}.metadata",
                )
            charge_token = (
                f"{abs(atom.formal_charge)}{'+' if atom.formal_charge > 0 else '-'}"
            )
        else:
            if atom.formal_charge != 0:
                raise PdbWriteError(
                    "unknown_nonzero_formal_charge",
                    "unknown PDB formal charge must retain placeholder zero",
                    location=f"{location}.formal_charge",
                )
            if (
                metadata.get("formal_charge_source") != "missing_in_pdb"
                or metadata.get("formal_charge_interpretation")
                != "placeholder_zero_unknown"
            ):
                raise PdbWriteError(
                    "unsupported_formal_charge",
                    "unknown formal-charge source markers are stale",
                    location=f"{location}.metadata",
                )
            charge_token = "  "

        if atom.occupancy is not None and not 0.0 <= atom.occupancy <= 1.0:
            raise PdbWriteError(
                "invalid_occupancy",
                "occupancy must remain in [0, 1]",
                location=f"{location}.occupancy",
            )
        occupancy_token = _optional_f6_2_token(
            atom.occupancy,
            kind="occupancy",
            location=f"{location}.occupancy",
        )
        b_factor_token = _optional_f6_2_token(
            atom.b_factor,
            kind="b_factor",
            location=f"{location}.b_factor",
        )
        occupancy_tokens.append(occupancy_token)
        b_factor_tokens.append(b_factor_token)
        charge_tokens.append(charge_token)
        atom_documents.append(
            {
                "index": atom.index,
                "record": record,
                "serial": atom.serial,
                "name": atom.name,
                "pdb_atom_name_field": raw_name,
                "element": element,
                "atomic_number": atom.atomic_number,
                "residue_index": atom.residue_index,
                "formal_charge": atom.formal_charge,
                "formal_charge_known": atom.formal_charge_known,
                "formal_charge_token": charge_token,
                "altloc": "",
                "occupancy_ieee754_binary64_be": (
                    None if atom.occupancy is None else _binary64_hex(atom.occupancy)
                ),
                "occupancy_token": occupancy_token,
                "b_factor_ieee754_binary64_be": (
                    None if atom.b_factor is None else _binary64_hex(atom.b_factor)
                ),
                "b_factor_token": b_factor_token,
                "segment_id": segment_id,
                "metadata": dict(metadata),
            }
        )

    residue_documents: list[Mapping[str, Any]] = []
    seen_residue_bases: set[tuple[int, int, str]] = set()
    for residue in system.residues:
        location = f"residues[{residue.index}]"
        metadata = _require_exact_keys(
            residue.metadata,
            _RESIDUE_METADATA_KEYS,
            code="unsupported_residue_metadata",
            location=f"{location}.metadata",
        )
        _ascii_text(
            residue.name,
            max_chars=3,
            code="unsupported_residue_name",
            location=f"{location}.name",
        )
        if residue.name != residue.name.upper():
            raise PdbWriteError(
                "unsupported_residue_name",
                "parser-owned PDB residue names must be uppercase",
                location=f"{location}.name",
            )
        _integer_token(
            residue.sequence_number,
            width=4,
            code="unsupported_residue_number",
            location=f"{location}.sequence_number",
        )
        insertion_code = _ascii_text(
            residue.insertion_code,
            max_chars=1,
            code="unsupported_insertion_code",
            location=f"{location}.insertion_code",
            allow_empty=True,
        )
        if insertion_code and insertion_code.isspace():
            raise PdbWriteError(
                "unsupported_insertion_code",
                "insertion code must be blank or non-whitespace",
                location=f"{location}.insertion_code",
            )
        expected_atom_indices = tuple(atom_indices_by_residue[residue.index])
        if residue.atom_indices != expected_atom_indices or not expected_atom_indices:
            raise PdbWriteError(
                "unsupported_residue_topology",
                "residue atom_indices do not match ordered canonical atoms",
                location=f"{location}.atom_indices",
            )
        source_record = "HETATM" if residue.hetero else "ATOM"
        expected_entity_type = "unknown" if residue.hetero else "polymer"
        expected_basis = (
            "unresolved_from_hetero_record" if residue.hetero else "atom_record"
        )
        segment_ids = {
            str(system.atoms[index].metadata.get("pdb_segment_id"))
            for index in expected_atom_indices
        }
        if len(segment_ids) != 1:
            raise PdbWriteError(
                "unsupported_residue_metadata",
                "all atoms in one PDB residue must share a segment ID",
                location=location,
            )
        segment_id = next(iter(segment_ids))
        if (
            residue.entity_type != expected_entity_type
            or metadata.get("source_record") != source_record
            or metadata.get("entity_id") != ""
            or metadata.get("source_residue_namespace") != segment_id
            or metadata.get("entity_type_basis") != expected_basis
            or metadata.get("pdb_segment_id") != segment_id
            or any(
                system.atoms[index].metadata.get("source_record") != source_record
                for index in expected_atom_indices
            )
        ):
            raise PdbWriteError(
                "unsupported_residue_metadata",
                "residue metadata does not match parser-owned ATOM/HETATM state",
                location=location,
            )
        base = (residue.chain_index, residue.sequence_number, insertion_code)
        if base in seen_residue_bases:
            raise PdbWriteError(
                "unsupported_residue_topology",
                "PDB residue base identity must be unique within a chain",
                location=location,
            )
        seen_residue_bases.add(base)
        residue_documents.append(
            {
                "index": residue.index,
                "name": residue.name,
                "chain_index": residue.chain_index,
                "sequence_number": residue.sequence_number,
                "atom_indices": list(residue.atom_indices),
                "insertion_code": insertion_code,
                "entity_type": residue.entity_type,
                "hetero": residue.hetero,
                "metadata": dict(metadata),
            }
        )

    chain_documents: list[Mapping[str, Any]] = []
    seen_chain_ids: set[str] = set()
    canonical_chain_indices = tuple(chain.index for chain in system.chains)
    if tuple(chain_indices_in_atom_order) != canonical_chain_indices:
        raise PdbWriteError(
            "unsupported_chain_topology",
            "canonical chain indices must follow first occurrence in PDB atom order",
            location="chains",
        )
    parser_residue_order = tuple(
        residue_index
        for chain_index in chain_indices_in_atom_order
        for residue_index in residue_indices_by_chain[chain_index]
    )
    canonical_residue_indices = tuple(residue.index for residue in system.residues)
    if parser_residue_order != canonical_residue_indices:
        raise PdbWriteError(
            "unsupported_residue_topology",
            "canonical residue indices must match parser first-occurrence order",
            location="residues",
        )
    for chain in system.chains:
        location = f"chains[{chain.index}]"
        metadata = _require_exact_keys(
            chain.metadata,
            _CHAIN_METADATA_KEYS,
            code="unsupported_chain_metadata",
            location=f"{location}.metadata",
        )
        chain_id = _ascii_text(
            chain.chain_id,
            max_chars=1,
            code="unsupported_chain_id",
            location=f"{location}.chain_id",
            allow_empty=True,
        )
        if chain_id and chain_id.isspace():
            raise PdbWriteError(
                "unsupported_chain_id",
                "chain ID must be blank or non-whitespace",
                location=f"{location}.chain_id",
            )
        if chain_id in seen_chain_ids:
            raise PdbWriteError(
                "unsupported_chain_topology",
                "PDB chain IDs must be unique",
                location=f"{location}.chain_id",
            )
        seen_chain_ids.add(chain_id)
        expected_residue_indices = tuple(residue_indices_by_chain[chain.index])
        if (
            chain.residue_indices != expected_residue_indices
            or not expected_residue_indices
        ):
            raise PdbWriteError(
                "unsupported_chain_topology",
                "chain residue_indices do not match ordered residues",
                location=f"{location}.residue_indices",
            )
        auth_asym_ids = metadata.get("auth_asym_ids")
        if (
            chain.entity_id != ""
            or metadata.get("source_format") != "pdb"
            or not isinstance(auth_asym_ids, (list, tuple))
            or tuple(auth_asym_ids)
        ):
            raise PdbWriteError(
                "unsupported_chain_metadata",
                "chain metadata does not match parser-owned PDB state",
                location=location,
            )
        chain_documents.append(
            {
                "index": chain.index,
                "chain_id": chain_id,
                "residue_indices": list(chain.residue_indices),
                "entity_id": "",
                "metadata": {
                    "source_format": "pdb",
                    "auth_asym_ids": [],
                },
            }
        )

    return (
        tuple(atom_documents),
        tuple(residue_documents),
        tuple(chain_documents),
        tuple(occupancy_tokens),
        tuple(b_factor_tokens),
        tuple(charge_tokens),
    )


def _validate_ter_records(
    system: AllAtomSystem,
    *,
    model_ids: tuple[int, ...],
    pdb_metadata: Mapping[str, Any],
    cryst1_present: bool,
    missingness_line_count: int,
) -> tuple[tuple[Mapping[str, Any], ...], ...]:
    last_atom_index_by_chain: dict[int, int] = {}
    for atom in system.atoms:
        residue = system.residues[atom.residue_index]
        last_atom_index_by_chain[residue.chain_index] = atom.index
    raw_models = pdb_metadata.get("ter_records_by_model")
    if not isinstance(raw_models, (list, tuple)) or len(raw_models) != len(model_ids):
        raise PdbWriteError(
            "unsupported_ter_metadata",
            "TER metadata must provide one entry per coordinate model",
            location="metadata.pdb.ter_records_by_model",
        )
    resource_usage = pdb_metadata.get("resource_usage")
    physical_line_upper_bound = (
        resource_usage.get("physical_line_upper_bound")
        if isinstance(resource_usage, Mapping)
        else None
    )
    normalized_models: list[tuple[Mapping[str, Any], ...]] = []
    total_ter_count = 0
    reference_layout: tuple[Mapping[str, Any], ...] | None = None
    for model_index, (model_id, raw_model) in enumerate(
        zip(model_ids, raw_models, strict=True)
    ):
        location = f"metadata.pdb.ter_records_by_model[{model_index}]"
        model_mapping = _require_exact_keys(
            raw_model,
            frozenset({"model_id", "records"}),
            code="unsupported_ter_metadata",
            location=location,
        )
        if (
            type(model_mapping.get("model_id")) is not int
            or model_mapping.get("model_id") != model_id
        ):
            raise PdbWriteError(
                "unsupported_ter_metadata",
                "TER model identifier does not match provenance model_ids",
                location=f"{location}.model_id",
            )
        raw_records = model_mapping.get("records")
        if not isinstance(raw_records, (list, tuple)):
            raise PdbWriteError(
                "unsupported_ter_metadata",
                "TER records must be a parser-owned sequence",
                location=f"{location}.records",
            )
        normalized: list[Mapping[str, Any]] = []
        previous_after_index = -1
        terminated_chain_indices: set[int] = set()
        for record_index, raw_record in enumerate(raw_records):
            record_location = f"{location}.records[{record_index}]"
            record = _require_exact_keys(
                raw_record,
                _TER_RECORD_KEYS,
                code="unsupported_ter_metadata",
                location=record_location,
            )
            after_atom_index = record.get("after_atom_index")
            if (
                type(after_atom_index) is not int
                or not 0 <= after_atom_index < system.atom_count
                or after_atom_index <= previous_after_index
            ):
                raise PdbWriteError(
                    "unsupported_ter_metadata",
                    "TER after_atom_index values must be unique, increasing, and in range",
                    location=f"{record_location}.after_atom_index",
                )
            previous_after_index = after_atom_index
            atom = system.atoms[after_atom_index]
            residue = system.residues[atom.residue_index]
            chain = system.chains[residue.chain_index]
            expected_serial = atom.serial + 1 if atom.serial is not None else None
            if (
                type(record.get("serial")) is not int
                or record.get("serial") != expected_serial
                or not 1 <= record.get("serial") <= 99_999
            ):
                raise PdbWriteError(
                    "unsupported_ter_serial",
                    "TER serial must fit I5 and immediately follow the preceding atom",
                    location=f"{record_location}.serial",
                )
            if (
                type(record.get("after_atom_serial")) is not int
                or record.get("after_atom_serial") != atom.serial
            ):
                raise PdbWriteError(
                    "unsupported_ter_metadata",
                    "TER after_atom_serial does not match the preceding atom",
                    location=f"{record_location}.after_atom_serial",
                )
            expected_identity = (
                residue.name,
                chain.chain_id,
                residue.sequence_number,
                residue.insertion_code,
            )
            observed_identity = (
                record.get("residue_name"),
                record.get("chain_id"),
                record.get("residue_number"),
                record.get("insertion_code"),
            )
            if not _exact_typed_json_equal(
                _plain_json(list(observed_identity)),
                _plain_json(list(expected_identity)),
            ):
                raise PdbWriteError(
                    "unsupported_ter_metadata",
                    "TER residue identity does not match its preceding atom",
                    location=record_location,
                )
            line_number = record.get("line_number")
            if (
                type(line_number) is not int
                or line_number < 1
                or type(physical_line_upper_bound) is not int
                or line_number > physical_line_upper_bound
            ):
                raise PdbWriteError(
                    "unsupported_ter_metadata",
                    "TER source line number is outside parser resource usage",
                    location=f"{record_location}.line_number",
                )
            if (
                chain.index in terminated_chain_indices
                or last_atom_index_by_chain.get(chain.index) != after_atom_index
            ):
                raise PdbWriteError(
                    "unsupported_ter_metadata",
                    "a PDB chain cannot reappear after TER",
                    location=record_location,
                )
            terminated_chain_indices.add(chain.index)
            normalized.append(
                {
                    "serial": record["serial"],
                    "residue_name": record["residue_name"],
                    "chain_id": record["chain_id"],
                    "residue_number": record["residue_number"],
                    "insertion_code": record["insertion_code"],
                    "after_atom_index": record["after_atom_index"],
                    "after_atom_serial": record["after_atom_serial"],
                }
            )
        normalized_tuple = tuple(normalized)
        if reference_layout is None:
            reference_layout = normalized_tuple
        elif normalized_tuple != reference_layout:
            raise PdbWriteError(
                "unsupported_ter_metadata",
                "all models must carry identical semantic TER layout",
                location=location,
            )
        normalized_models.append(normalized_tuple)
        total_ter_count += len(normalized_tuple)

    if (
        type(pdb_metadata.get("ter_count")) is not int
        or pdb_metadata.get("ter_count") != total_ter_count
    ):
        raise PdbWriteError(
            "unsupported_ter_metadata",
            "TER count does not match records_by_model",
            location="metadata.pdb.ter_count",
        )
    if total_ter_count > system.model_count * system.atom_count:
        raise PdbWriteError(
            "unsupported_ter_metadata",
            "TER count cannot exceed one record per emitted atom row",
            location="metadata.pdb.ter_count",
        )
    explicit_models = not (system.model_count == 1 and model_ids == (1,))
    output_record_lines = (
        system.model_count * system.atom_count
        + total_ter_count
        + (2 * system.model_count if explicit_models else 0)
        + int(cryst1_present)
        + missingness_line_count
        + 1
    )
    if output_record_lines + 1 > _MAX_OUTPUT_LINES:
        raise PdbWriteError(
            "output_line_limit_exceeded",
            "emitted PDB would exceed the parser physical-line safety limit",
        )
    return tuple(normalized_models)


def _validate_coordinate_tokens(
    system: AllAtomSystem,
) -> tuple[tuple[tuple[str, str, str], ...], ...]:
    models: list[tuple[tuple[str, str, str], ...]] = []
    for model_index in range(system.model_count):
        atoms: list[tuple[str, str, str]] = []
        for atom_index in range(system.atom_count):
            tokens: list[str] = []
            for axis_index, axis in enumerate(("x", "y", "z")):
                value = float(
                    system.coordinates[model_index, atom_index, axis_index].item()
                )
                tokens.append(
                    _fixed_decimal_token(
                        value,
                        width=8,
                        precision=3,
                        kind="coordinate",
                        location=(f"coordinates[{model_index},{atom_index},{axis}]"),
                    )
                )
            atoms.append((tokens[0], tokens[1], tokens[2]))
        models.append(tuple(atoms))
    return tuple(models)


def _validate_write_state(system: AllAtomSystem) -> _ValidatedWriteState:
    snapshot = _snapshot_parser_system(system)
    if snapshot.schema_id != ALL_ATOM_SCHEMA_ID:
        raise PdbWriteError(
            "unsupported_system_schema",
            "writer requires the current all-atom schema",
            location="schema_id",
        )
    if snapshot.atom_count < 1:
        raise PdbWriteError(
            "unsupported_atom_count",
            "strict PDB writer requires at least one atom",
            location="atoms",
        )
    if snapshot.bonds:
        raise PdbWriteError(
            "unsupported_bonds",
            "strict PDB parser rejects contextual CONECT semantics",
            location="bonds",
        )
    if snapshot.coordinate_unit != "angstrom":
        raise PdbWriteError(
            "unsupported_coordinate_unit",
            "PDB coordinates must be in angstrom",
            location="coordinate_unit",
        )
    if snapshot.model_count < 1:
        raise PdbWriteError(
            "unsupported_model_count",
            "strict PDB writer requires at least one coordinate model",
            location="coordinates",
        )
    atom_rows = snapshot.model_count * snapshot.atom_count
    if atom_rows > _MAX_ATOM_ROWS:
        raise PdbWriteError(
            "too_many_atom_rows",
            "emitted PDB atom rows exceed the parser safety limit",
            location="coordinates",
        )

    cryst1 = _validate_cryst1_state(snapshot)

    (
        atom_documents,
        residue_documents,
        chain_documents,
        occupancy_tokens,
        b_factor_tokens,
        charge_tokens,
    ) = _validate_atoms_residues_chains(snapshot)
    model_ids, pdb_metadata, missingness_report, raw_missingness_records = (
        _validate_provenance_and_metadata(
            snapshot,
            cryst1=cryst1,
        )
    )
    missingness_semantic_document, missingness_lines = (
        _validate_missingness_claims_and_build_semantics(
            snapshot,
            report=missingness_report,
            raw_records=raw_missingness_records,
            model_ids=model_ids,
        )
    )
    missingness_semantic_sha256 = _sha256_document(missingness_semantic_document)
    missingness_evidence_present = bool(
        missingness_report.missing_residue_claims
        or missingness_report.missing_atom_claims
    )
    ter_records_by_model = _validate_ter_records(
        snapshot,
        model_ids=model_ids,
        pdb_metadata=pdb_metadata,
        cryst1_present=cryst1 is not None,
        missingness_line_count=len(missingness_lines),
    )
    coordinate_tokens = _validate_coordinate_tokens(snapshot)
    coordinate_document = [
        [
            [
                _binary64_hex(
                    float(snapshot.coordinates[model_index, atom_index, axis].item())
                )
                for axis in range(3)
            ]
            for atom_index in range(snapshot.atom_count)
        ]
        for model_index in range(snapshot.model_count)
    ]
    representable_state_document: Mapping[str, Any] = {
        "schema_id": PDB_REPRESENTABLE_STATE_SCHEMA_ID,
        "system_schema_id": snapshot.schema_id,
        "parser_name": snapshot.provenance.parser_name,
        "parser_version": snapshot.provenance.parser_version,
        "parser_operations": list(snapshot.provenance.operations),
        "canonical_topology_sha256": canonical_topology_sha256(snapshot),
        "atom_count": snapshot.atom_count,
        "bond_count": 0,
        "residue_count": len(snapshot.residues),
        "chain_count": len(snapshot.chains),
        "model_count": snapshot.model_count,
        "model_ids": list(model_ids),
        "implicit_single_model_one": (snapshot.model_count == 1 and model_ids == (1,)),
        "coordinate_unit": "angstrom",
        "coordinates_ieee754_binary64_be": coordinate_document,
        "coordinate_tokens_f8_3": [
            [list(tokens) for tokens in model] for model in coordinate_tokens
        ],
        "atoms": list(atom_documents),
        "residues": list(residue_documents),
        "chains": list(chain_documents),
        "ter_records_by_model": [
            {
                "model_id": model_id,
                "records": [dict(record) for record in records],
            }
            for model_id, records in zip(
                model_ids,
                ter_records_by_model,
                strict=True,
            )
        ],
        "cell": None if cryst1 is None else dict(cryst1.document),
        "altloc_status": "not_present",
        "missingness_semantic_projection": dict(missingness_semantic_document),
        "missingness_semantic_sha256": missingness_semantic_sha256,
        "missingness_evidence_status": (
            "present_fully_preserved" if missingness_evidence_present else "not_present"
        ),
        "preservation_scope": list(_PRESERVATION_SCOPE),
    }
    return _ValidatedWriteState(
        system=snapshot,
        model_ids=model_ids,
        coordinate_tokens=coordinate_tokens,
        occupancy_tokens=occupancy_tokens,
        b_factor_tokens=b_factor_tokens,
        charge_tokens=charge_tokens,
        ter_records_by_model=ter_records_by_model,
        cryst1=cryst1,
        missingness_report=missingness_report,
        missingness_semantic_document=missingness_semantic_document,
        missingness_semantic_sha256=missingness_semantic_sha256,
        missingness_evidence_present=missingness_evidence_present,
        input_missingness_remark_line_count=len(raw_missingness_records),
        missingness_lines=missingness_lines,
        representable_state_document=representable_state_document,
    )


def _atom_line(
    state: _ValidatedWriteState,
    *,
    model_index: int,
    atom_index: int,
) -> str:
    system = state.system
    atom = system.atoms[atom_index]
    residue = system.residues[atom.residue_index]
    chain = system.chains[residue.chain_index]
    metadata = atom.metadata
    record_field = "ATOM  " if metadata["source_record"] == "ATOM" else "HETATM"
    coordinate_tokens = state.coordinate_tokens[model_index][atom_index]
    line = (
        record_field
        + f"{atom.serial:5d}"
        + " "
        + str(metadata["pdb_atom_name_field"])
        + " "
        + f"{residue.name:>3}"
        + " "
        + (chain.chain_id or " ")
        + f"{residue.sequence_number:4d}"
        + (residue.insertion_code or " ")
        + "   "
        + coordinate_tokens[0]
        + coordinate_tokens[1]
        + coordinate_tokens[2]
        + state.occupancy_tokens[atom_index]
        + state.b_factor_tokens[atom_index]
        + "      "
        + f"{metadata['pdb_segment_id']:<4}"
        + f"{atom.element:>2}"
        + state.charge_tokens[atom_index]
    )
    if len(line) != _MAX_LINE_CHARS or any(
        ord(character) < 0x20 or ord(character) > 0x7E for character in line
    ):
        raise PdbWriteError(
            "internal_fixed_column_error",
            "validated atom state did not produce one printable 80-column line",
            location=f"coordinates[{model_index},{atom_index}]",
        )
    return line


def _ter_line(record: Mapping[str, Any]) -> str:
    line = (
        "TER   "
        + f"{record['serial']:5d}"
        + "      "
        + f"{record['residue_name']:>3}"
        + " "
        + (record["chain_id"] or " ")
        + f"{record['residue_number']:4d}"
        + (record["insertion_code"] or " ")
    ).ljust(_MAX_LINE_CHARS)
    if len(line) != _MAX_LINE_CHARS or any(
        ord(character) < 0x20 or ord(character) > 0x7E for character in line
    ):
        raise PdbWriteError(
            "internal_fixed_column_error",
            "validated TER state did not produce one printable 80-column line",
        )
    return line


def _emit_payload(state: _ValidatedWriteState) -> bytes:
    lines: list[str] = []
    if state.cryst1 is not None:
        lines.append(state.cryst1.line)
    lines.extend(state.missingness_lines)
    explicit_models = not (state.system.model_count == 1 and state.model_ids == (1,))
    for model_index, model_id in enumerate(state.model_ids):
        if explicit_models:
            lines.append(("MODEL " + " " * 4 + f"{model_id:4d}").ljust(80))
        records_by_index = {
            int(record["after_atom_index"]): record
            for record in state.ter_records_by_model[model_index]
        }
        for atom_index in range(state.system.atom_count):
            lines.append(
                _atom_line(
                    state,
                    model_index=model_index,
                    atom_index=atom_index,
                )
            )
            ter_record = records_by_index.get(atom_index)
            if ter_record is not None:
                lines.append(_ter_line(ter_record))
        if explicit_models:
            lines.append("ENDMDL".ljust(80))
    lines.append("END".ljust(80))
    if len(lines) + 1 > _MAX_OUTPUT_LINES:
        raise PdbWriteError(
            "output_line_limit_exceeded",
            "emitted PDB exceeds the parser physical-line safety limit",
        )
    if any(len(line) != _MAX_LINE_CHARS for line in lines):
        raise PdbWriteError(
            "internal_fixed_column_error",
            "emitted PDB contains a non-80-column line",
        )
    payload = ("\n".join(lines) + "\n").encode("ascii")
    if len(payload) > _MAX_OUTPUT_BYTES:
        raise PdbWriteError(
            "output_too_large",
            "emitted PDB exceeds the parser byte safety limit",
        )
    return payload


def pdb_representable_state_sha256(system: AllAtomSystem) -> str:
    """Hash the exact parser-owned PDB state that this writer reproduces."""

    state = _validate_write_state(system)
    return _sha256_document(state.representable_state_document)


def write_pdb(system: AllAtomSystem) -> PdbWriteResult:
    """Emit deterministic strict PDB bytes and a non-authoritative receipt."""

    state = _validate_write_state(system)
    payload = _emit_payload(state)
    output_source_sha256 = hashlib.sha256(payload).hexdigest()
    parser_observation_sha256 = state.system.provenance.metadata.get(
        "parser_observation_sha256"
    )
    if type(parser_observation_sha256) is not str:
        raise PdbWriteError(
            "stale_parser_observation_digest",
            "validated parser observation digest is missing",
            location="provenance.metadata.parser_observation_sha256",
        )
    receipt = PdbWriteReceipt(
        input_system_schema_id=state.system.schema_id,
        parent_source_sha256=state.system.provenance.source_sha256,
        input_snapshot_sha256=canonical_all_atom_snapshot_digest(state.system),
        input_topology_sha256=canonical_topology_sha256(state.system),
        input_representable_state_sha256=_sha256_document(
            state.representable_state_document
        ),
        input_parser_observation_sha256=parser_observation_sha256,
        output_source_sha256=output_source_sha256,
        output_byte_count=len(payload),
        atom_count=state.system.atom_count,
        bond_count=0,
        model_count=state.system.model_count,
        ter_count=sum(len(records) for records in state.ter_records_by_model),
        cell_present=state.cryst1 is not None,
        cryst1_count=int(state.cryst1 is not None),
        input_missingness_report_sha256=state.missingness_report.report_sha256,
        input_missingness_semantic_sha256=state.missingness_semantic_sha256,
        missingness_evidence_present=state.missingness_evidence_present,
        input_missingness_remark_line_count=(state.input_missingness_remark_line_count),
        emitted_missingness_remark_line_count=len(state.missingness_lines),
        missing_residue_claim_count=len(
            state.missingness_report.missing_residue_claims
        ),
        missing_atom_claim_count=len(state.missingness_report.missing_atom_claims),
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )
    return PdbWriteResult(
        payload=payload,
        receipt=receipt,
        input_snapshot=serialize_all_atom_system(state.system),
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )


def serialize_pdb(system: AllAtomSystem) -> bytes:
    """Return deterministic PDB bytes for exactly representable state."""

    return write_pdb(system).payload


def round_trip_pdb_source(
    data: bytes,
    *,
    source_id: str = "",
) -> PdbRoundTripResult:
    """Execute and verify ``source -> canonical -> PDB -> canonical``.

    Equality covers only :data:`PDB_REPRESENTABLE_STATE_SCHEMA_ID`.  Dynamic
    raw-source provenance and the complete canonical snapshot are bound in the
    report but intentionally are not equality or authentication claims.
    """

    source_ingest = parse_pdb(data, source_id=source_id)
    write_result = write_pdb(source_ingest.system)
    reparsed_ingest = parse_pdb(write_result.payload, source_id=source_id)
    reemitted = write_pdb(reparsed_ingest.system)

    input_topology_sha256 = canonical_topology_sha256(source_ingest.system)
    reparsed_topology_sha256 = canonical_topology_sha256(reparsed_ingest.system)
    input_state_sha256 = write_result.receipt.input_representable_state_sha256
    reparsed_state_sha256 = reemitted.receipt.input_representable_state_sha256
    input_source_sha256 = hashlib.sha256(data).hexdigest()
    mismatches: list[str] = []
    if source_ingest.system.provenance.source_sha256 != input_source_sha256:
        mismatches.append("input_source_sha256")
    if write_result.receipt.parent_source_sha256 != input_source_sha256:
        mismatches.append("writer_parent_source_sha256")
    if input_topology_sha256 != reparsed_topology_sha256:
        mismatches.append("canonical_topology")
    if input_state_sha256 != reparsed_state_sha256:
        mismatches.append("representable_state")
    if (
        write_result.receipt.input_missingness_semantic_sha256
        != reemitted.receipt.input_missingness_semantic_sha256
    ):
        mismatches.append("missingness_semantic_projection")
    if (
        write_result.receipt.missingness_evidence_present
        != reemitted.receipt.missingness_evidence_present
    ):
        mismatches.append("missingness_evidence_presence")
    if (
        write_result.receipt.missing_residue_claim_count
        != reemitted.receipt.missing_residue_claim_count
        or write_result.receipt.missing_atom_claim_count
        != reemitted.receipt.missing_atom_claim_count
    ):
        mismatches.append("missingness_claim_counts")
    if (
        source_ingest.missingness_evidence.report_sha256
        != write_result.receipt.input_missingness_report_sha256
    ):
        mismatches.append("source_missingness_raw_report")
    if (
        reparsed_ingest.missingness_evidence.report_sha256
        != reemitted.receipt.input_missingness_report_sha256
    ):
        mismatches.append("reparsed_missingness_raw_report")
    input_cell = source_ingest.system.cell
    reparsed_cell = reparsed_ingest.system.cell
    if (input_cell is None) != (reparsed_cell is None):
        mismatches.append("cryst1_cell_presence")
    elif input_cell is not None and reparsed_cell is not None:
        input_cell_hex = tuple(
            _binary64_hex(value) for row in input_cell.vectors.tolist() for value in row
        )
        reparsed_cell_hex = tuple(
            _binary64_hex(value)
            for row in reparsed_cell.vectors.tolist()
            for value in row
        )
        if input_cell_hex != reparsed_cell_hex:
            mismatches.append("cryst1_cell_vectors")
        if input_cell.periodic != reparsed_cell.periodic:
            mismatches.append("cryst1_cell_periodic_flags")
    if write_result.receipt.cell_present != reemitted.receipt.cell_present:
        mismatches.append("cryst1_receipt_cell_presence")
    if write_result.receipt.cryst1_count != reemitted.receipt.cryst1_count:
        mismatches.append("cryst1_receipt_count")
    if (
        reparsed_ingest.system.provenance.source_sha256
        != write_result.receipt.output_source_sha256
    ):
        mismatches.append("reparsed_source_sha256")
    if reemitted.payload != write_result.payload:
        mismatches.append("reemitted_bytes")
    if mismatches:
        raise PdbWriteError(
            "round_trip_mismatch",
            f"declared PDB round-trip projection failed: {mismatches}",
        )

    input_observation_sha256 = source_ingest.system.provenance.metadata.get(
        "parser_observation_sha256"
    )
    reparsed_observation_sha256 = reparsed_ingest.system.provenance.metadata.get(
        "parser_observation_sha256"
    )
    if (
        type(input_observation_sha256) is not str
        or type(reparsed_observation_sha256) is not str
    ):
        raise PdbWriteError(
            "stale_parser_observation_digest",
            "round-trip parser observation digests are missing",
        )
    report = PdbRoundTripReport(
        input_source_sha256=input_source_sha256,
        input_snapshot_sha256=write_result.receipt.input_snapshot_sha256,
        input_topology_sha256=input_topology_sha256,
        input_representable_state_sha256=input_state_sha256,
        input_parser_observation_sha256=input_observation_sha256,
        writer_receipt_sha256=write_result.receipt.receipt_sha256,
        emitted_source_sha256=write_result.receipt.output_source_sha256,
        reparsed_snapshot_sha256=canonical_all_atom_snapshot_digest(
            reparsed_ingest.system
        ),
        reparsed_topology_sha256=reparsed_topology_sha256,
        reparsed_representable_state_sha256=reparsed_state_sha256,
        reparsed_parser_observation_sha256=reparsed_observation_sha256,
        reemitted_source_sha256=hashlib.sha256(reemitted.payload).hexdigest(),
        input_missingness_report_sha256=(
            source_ingest.missingness_evidence.report_sha256
        ),
        reparsed_missingness_report_sha256=(
            reparsed_ingest.missingness_evidence.report_sha256
        ),
        input_missingness_semantic_sha256=(
            write_result.receipt.input_missingness_semantic_sha256
        ),
        reparsed_missingness_semantic_sha256=(
            reemitted.receipt.input_missingness_semantic_sha256
        ),
        missingness_evidence_present=(
            write_result.receipt.missingness_evidence_present
        ),
        missing_residue_claim_count=(write_result.receipt.missing_residue_claim_count),
        missing_atom_claim_count=write_result.receipt.missing_atom_claim_count,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )
    return PdbRoundTripResult(
        source_ingest=source_ingest,
        write_result=write_result,
        reparsed_ingest=reparsed_ingest,
        report=report,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )


__all__ = [
    "PDB_MISSINGNESS_PROFILE_ID",
    "PDB_MISSINGNESS_SEMANTIC_SCHEMA_ID",
    "PDB_REPRESENTABLE_STATE_SCHEMA_ID",
    "PDB_ROUND_TRIP_REPORT_SCHEMA_ID",
    "PDB_WRITER_VERSION",
    "PDB_WRITE_RECEIPT_SCHEMA_ID",
    "PdbRoundTripReport",
    "PdbRoundTripResult",
    "PdbWriteError",
    "PdbWriteReceipt",
    "PdbWriteResult",
    "pdb_representable_state_sha256",
    "round_trip_pdb_source",
    "serialize_pdb",
    "write_pdb",
]
