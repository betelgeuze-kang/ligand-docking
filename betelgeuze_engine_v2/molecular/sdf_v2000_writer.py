"""Deterministic writer for the exactly representable strict SDF V2000 subset.

This module is deliberately not a general ``AllAtomSystem`` exporter.  It
accepts only the parser-shaped, single-ligand state produced by the current
strict SDF V2000 reader and fails closed whenever state inside the declared
representable-state projection would be discarded, rounded, or reinterpreted
by the source format.

Source-format round-trip equality is defined by a versioned representable-state
projection.  Raw-source SHA-256, parser-observation SHA-256, and the full
canonical snapshot are excluded because reparsing emitted bytes correctly
creates new source provenance.  The receipt binds those hashes separately; it
is tamper evidence, not authentication or scientific authority.
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

from .models import AllAtomSystem
from .observation import (
    PARSER_OBSERVATION_SCHEMA_ID,
    attached_parser_observation_sha256_matches,
)
from .sdf_v2000 import (
    SDF_V2000_PARSER_VERSION,
    SdfV2000Coverage,
    SdfV2000IngestResult,
    parse_sdf_v2000,
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


SDF_V2000_WRITER_VERSION = "1.0.0"
SDF_V2000_REPRESENTABLE_STATE_SCHEMA_ID = (
    "betelgeuze.sdf_v2000_representable_state/1.0.0"
)
SDF_V2000_WRITE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.sdf_v2000_write_receipt/1.0.0"
)
SDF_V2000_ROUND_TRIP_REPORT_SCHEMA_ID = (
    "betelgeuze.sdf_v2000_round_trip_report/1.0.0"
)

_SDF_PARSER_NAME = "betelgeuze_engine_v2.molecular.sdf_v2000"
_MAX_OUTPUT_BYTES = 2 * 1024 * 1024
_MAX_OUTPUT_LINES = 4_096
_MAX_LINE_CHARS = 256
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_FORMAL_CHARGE_TO_ATOM_BLOCK_CODE = {
    0: 0,
    3: 1,
    2: 2,
    1: 3,
    -1: 5,
    -2: 6,
    -3: 7,
}
_BOND_STATE_TO_TYPE = {
    (1.0, False): 1,
    (2.0, False): 2,
    (3.0, False): 3,
    (1.5, True): 4,
}
_ATOM_METADATA_KEYS = frozenset(
    {
        "sdf_source_atom_index",
        "sdf_atom_map",
        "hydrogen_origin",
        "formal_charge_source",
    }
)
_BOND_METADATA_KEYS = frozenset(
    {
        "sdf_source_bond_index",
        "sdf_source_atom_i",
        "sdf_source_atom_j",
        "sdf_bond_type",
    }
)
_PROVENANCE_METADATA_KEYS = frozenset(
    {
        "coverage",
        "canonical_topology_schema_id",
        "canonical_topology_sha256",
        "parser_observation_schema_id",
        "parser_observation_sha256",
    }
)
_PARSER_OPERATIONS = (
    "parse_strict_sdf_v2000_single_record",
    "preserve_source_atom_order",
    "synthesize_atom_names",
    "synthesize_single_ligand_residue_and_chain",
)
_PRESERVATION_SCOPE = (
    "safe_sdf_header_text",
    "source_atom_order",
    "element_and_atomic_number",
    "known_formal_charge_and_source_encoding_class",
    "isotope_mass_number",
    "atom_map",
    "supported_bond_order_and_aromatic_marker",
    "source_bond_row_order_and_endpoint_orientation",
    "exact_f10_4_single_model_coordinates_angstrom",
    "strict_parser_synthesized_single_ligand_context",
)
_NON_PROMOTION_BLOCKERS = (
    "raw_source_bytes_and_delimiter_presence_are_not_preserved",
    "system_id_and_source_id_are_outside_declared_projection",
    "full_canonical_snapshot_and_dynamic_source_provenance_equality_not_claimed",
    "sha256_receipts_are_tamper_evidence_not_source_authentication",
    "sdf_atom_and_bond_stereochemistry_unsupported",
    "sdf_property_data_fields_and_arbitrary_context_unsupported",
    "preparation_parameterability_simulation_and_claim_authority_not_granted",
)
_ARTIFACT_FACTORY_TOKEN = object()


class SdfV2000WriteError(ValueError):
    """Stable fail-closed error for an unrepresentable canonical SDF state."""

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
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


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
        raise SdfV2000WriteError(code, "value must be a mapping", location=location)
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise SdfV2000WriteError(
            code,
            f"mapping keys do not match parser-owned state; missing={missing}, unknown={unknown}",
            location=location,
        )
    return value


def _binary64_hex(value: float) -> str:
    return struct.pack(">d", float(value)).hex()


@dataclass(frozen=True, slots=True, init=False)
class SdfV2000WriteReceipt:
    """Hash binding for one deterministic SDF emission."""

    input_system_schema_id: str
    parent_source_sha256: str
    input_snapshot_sha256: str
    input_topology_sha256: str
    input_representable_state_sha256: str
    output_source_sha256: str
    output_byte_count: int
    atom_count: int
    bond_count: int

    def __init__(
        self,
        *,
        input_system_schema_id: str,
        parent_source_sha256: str,
        input_snapshot_sha256: str,
        input_topology_sha256: str,
        input_representable_state_sha256: str,
        output_source_sha256: str,
        output_byte_count: int,
        atom_count: int,
        bond_count: int,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SdfV2000WriteReceipt is factory-only")
        for field_name, value in (
            ("input_system_schema_id", input_system_schema_id),
            ("parent_source_sha256", parent_source_sha256),
            ("input_snapshot_sha256", input_snapshot_sha256),
            ("input_topology_sha256", input_topology_sha256),
            ("input_representable_state_sha256", input_representable_state_sha256),
            ("output_source_sha256", output_source_sha256),
            ("output_byte_count", output_byte_count),
            ("atom_count", atom_count),
            ("bond_count", bond_count),
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
            "output_source_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        for field_name in ("output_byte_count", "atom_count", "bond_count"):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise TypeError(f"{field_name} must be a nonnegative integer")
        if not 1 <= self.atom_count <= 999:
            raise ValueError("write receipt atom_count must be in [1, 999]")
        if self.bond_count > 999:
            raise ValueError("write receipt bond_count must be at most 999")
        if self.output_byte_count < 1 or self.output_byte_count > _MAX_OUTPUT_BYTES:
            raise ValueError("write receipt output_byte_count is outside the writer limit")

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": SDF_V2000_WRITE_RECEIPT_SCHEMA_ID,
            "writer_version": SDF_V2000_WRITER_VERSION,
            "parser_version": SDF_V2000_PARSER_VERSION,
            "input_system_schema_id": self.input_system_schema_id,
            "parent_source_sha256": self.parent_source_sha256,
            "input_snapshot_sha256": self.input_snapshot_sha256,
            "input_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
            "input_topology_sha256": self.input_topology_sha256,
            "representable_state_schema_id": (
                SDF_V2000_REPRESENTABLE_STATE_SCHEMA_ID
            ),
            "input_representable_state_sha256": (
                self.input_representable_state_sha256
            ),
            "output_source_sha256": self.output_source_sha256,
            "output_byte_count": self.output_byte_count,
            "atom_count": self.atom_count,
            "bond_count": self.bond_count,
            "model_count": 1,
            "coordinate_unit": "angstrom",
            "coordinate_format": "fixed_width_f10_4_exact_binary64_round_trip",
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
class SdfV2000WriteResult:
    payload: bytes = field(repr=False)
    receipt: SdfV2000WriteReceipt

    def __init__(
        self,
        *,
        payload: bytes,
        receipt: SdfV2000WriteReceipt,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SdfV2000WriteResult is factory-only")
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "receipt", receipt)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self.payload) is not bytes:
            raise TypeError("SDF write payload must be exact bytes")
        if type(self.receipt) is not SdfV2000WriteReceipt:
            raise TypeError("receipt must be an SdfV2000WriteReceipt")
        if len(self.payload) != self.receipt.output_byte_count:
            raise ValueError("write payload length does not match receipt")
        if hashlib.sha256(self.payload).hexdigest() != self.receipt.output_source_sha256:
            raise ValueError("write payload SHA-256 does not match receipt")


@dataclass(frozen=True, slots=True, init=False)
class SdfV2000RoundTripReport:
    """Evidence for the declared source-independent round-trip projection."""

    input_source_sha256: str
    input_snapshot_sha256: str
    input_topology_sha256: str
    input_representable_state_sha256: str
    writer_receipt_sha256: str
    emitted_source_sha256: str
    reparsed_snapshot_sha256: str
    reparsed_topology_sha256: str
    reparsed_representable_state_sha256: str
    reemitted_source_sha256: str

    def __init__(
        self,
        *,
        input_source_sha256: str,
        input_snapshot_sha256: str,
        input_topology_sha256: str,
        input_representable_state_sha256: str,
        writer_receipt_sha256: str,
        emitted_source_sha256: str,
        reparsed_snapshot_sha256: str,
        reparsed_topology_sha256: str,
        reparsed_representable_state_sha256: str,
        reemitted_source_sha256: str,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SdfV2000RoundTripReport is factory-only")
        for field_name, value in (
            ("input_source_sha256", input_source_sha256),
            ("input_snapshot_sha256", input_snapshot_sha256),
            ("input_topology_sha256", input_topology_sha256),
            ("input_representable_state_sha256", input_representable_state_sha256),
            ("writer_receipt_sha256", writer_receipt_sha256),
            ("emitted_source_sha256", emitted_source_sha256),
            ("reparsed_snapshot_sha256", reparsed_snapshot_sha256),
            ("reparsed_topology_sha256", reparsed_topology_sha256),
            (
                "reparsed_representable_state_sha256",
                reparsed_representable_state_sha256,
            ),
            ("reemitted_source_sha256", reemitted_source_sha256),
        ):
            object.__setattr__(self, field_name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        for field_name in (
            "input_source_sha256",
            "input_snapshot_sha256",
            "input_topology_sha256",
            "input_representable_state_sha256",
            "writer_receipt_sha256",
            "emitted_source_sha256",
            "reparsed_snapshot_sha256",
            "reparsed_topology_sha256",
            "reparsed_representable_state_sha256",
            "reemitted_source_sha256",
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

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": SDF_V2000_ROUND_TRIP_REPORT_SCHEMA_ID,
            "writer_version": SDF_V2000_WRITER_VERSION,
            "parser_version": SDF_V2000_PARSER_VERSION,
            "representable_state_schema_id": (
                SDF_V2000_REPRESENTABLE_STATE_SCHEMA_ID
            ),
            "input_source_sha256": self.input_source_sha256,
            "input_snapshot_sha256": self.input_snapshot_sha256,
            "input_topology_sha256": self.input_topology_sha256,
            "input_representable_state_sha256": (
                self.input_representable_state_sha256
            ),
            "writer_receipt_sha256": self.writer_receipt_sha256,
            "emitted_source_sha256": self.emitted_source_sha256,
            "reparsed_snapshot_sha256": self.reparsed_snapshot_sha256,
            "reparsed_topology_sha256": self.reparsed_topology_sha256,
            "reparsed_representable_state_sha256": (
                self.reparsed_representable_state_sha256
            ),
            "reemitted_source_sha256": self.reemitted_source_sha256,
            "declared_projection_sha256_equal": True,
            "canonical_topology_sha256_equal": True,
            "coordinate_binary64_projection_equal": True,
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
class SdfV2000RoundTripResult:
    _source_snapshot: bytes = field(repr=False)
    _source_coverage: SdfV2000Coverage
    _write_result: SdfV2000WriteResult = field(repr=False)
    _reparsed_snapshot: bytes = field(repr=False)
    _reparsed_coverage: SdfV2000Coverage
    _report: SdfV2000RoundTripReport

    def __init__(
        self,
        *,
        source_ingest: SdfV2000IngestResult,
        write_result: SdfV2000WriteResult,
        reparsed_ingest: SdfV2000IngestResult,
        report: SdfV2000RoundTripReport,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SdfV2000RoundTripResult is factory-only")
        if type(source_ingest) is not SdfV2000IngestResult:
            raise TypeError("source_ingest must be an SdfV2000IngestResult")
        if type(source_ingest.coverage) is not SdfV2000Coverage:
            raise TypeError("source_ingest.coverage must be an SdfV2000Coverage")
        if type(write_result) is not SdfV2000WriteResult:
            raise TypeError("write_result must be an SdfV2000WriteResult")
        if type(reparsed_ingest) is not SdfV2000IngestResult:
            raise TypeError("reparsed_ingest must be an SdfV2000IngestResult")
        if type(reparsed_ingest.coverage) is not SdfV2000Coverage:
            raise TypeError("reparsed_ingest.coverage must be an SdfV2000Coverage")
        if type(report) is not SdfV2000RoundTripReport:
            raise TypeError("report must be an SdfV2000RoundTripReport")
        object.__setattr__(
            self,
            "_source_snapshot",
            serialize_all_atom_system(source_ingest.system),
        )
        object.__setattr__(self, "_source_coverage", source_ingest.coverage)
        object.__setattr__(self, "_write_result", write_result)
        object.__setattr__(
            self,
            "_reparsed_snapshot",
            serialize_all_atom_system(reparsed_ingest.system),
        )
        object.__setattr__(self, "_reparsed_coverage", reparsed_ingest.coverage)
        object.__setattr__(self, "_report", report)
        self.__post_init__()

    @property
    def source_ingest(self) -> SdfV2000IngestResult:
        """Return a fresh detached copy of the source canonical snapshot."""

        return SdfV2000IngestResult(
            system=deserialize_all_atom_system(self._source_snapshot),
            coverage=self._source_coverage,
        )

    @property
    def write_result(self) -> SdfV2000WriteResult:
        return self._write_result

    @property
    def reparsed_ingest(self) -> SdfV2000IngestResult:
        """Return a fresh detached copy of the reparsed canonical snapshot."""

        return SdfV2000IngestResult(
            system=deserialize_all_atom_system(self._reparsed_snapshot),
            coverage=self._reparsed_coverage,
        )

    @property
    def report(self) -> SdfV2000RoundTripReport:
        return self._report

    def __post_init__(self) -> None:
        if type(self._source_snapshot) is not bytes:
            raise TypeError("source snapshot must be exact bytes")
        if type(self._source_coverage) is not SdfV2000Coverage:
            raise TypeError("source coverage must be an SdfV2000Coverage")
        if type(self._write_result) is not SdfV2000WriteResult:
            raise TypeError("write result must be an SdfV2000WriteResult")
        if type(self._reparsed_snapshot) is not bytes:
            raise TypeError("reparsed snapshot must be exact bytes")
        if type(self._reparsed_coverage) is not SdfV2000Coverage:
            raise TypeError("reparsed coverage must be an SdfV2000Coverage")
        if type(self._report) is not SdfV2000RoundTripReport:
            raise TypeError("report must be an SdfV2000RoundTripReport")
        source_ingest = self.source_ingest
        reparsed_ingest = self.reparsed_ingest
        source_system = source_ingest.system
        reparsed_system = reparsed_ingest.system
        source_snapshot_sha256 = canonical_all_atom_snapshot_digest(source_system)
        source_topology_sha256 = canonical_topology_sha256(source_system)
        source_state_sha256 = sdf_v2000_representable_state_sha256(source_system)
        reparsed_snapshot_sha256 = canonical_all_atom_snapshot_digest(
            reparsed_system
        )
        reparsed_topology_sha256 = canonical_topology_sha256(reparsed_system)
        reparsed_state_sha256 = sdf_v2000_representable_state_sha256(
            reparsed_system
        )
        output_source_sha256 = hashlib.sha256(self.write_result.payload).hexdigest()
        reemitted = write_sdf_v2000(reparsed_system)
        expected_pairs = (
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
                "reemitted payload to report",
                hashlib.sha256(reemitted.payload).hexdigest(),
                self.report.reemitted_source_sha256,
            ),
        )
        mismatches = [
            label for label, expected, observed in expected_pairs if expected != observed
        ]
        if source_ingest.coverage.to_dict() != source_system.provenance.metadata.get(
            "coverage"
        ):
            mismatches.append("source ingest coverage")
        if reparsed_ingest.coverage.to_dict() != (
            reparsed_system.provenance.metadata.get("coverage")
        ):
            mismatches.append("reparsed ingest coverage")
        if reemitted.payload != self.write_result.payload:
            mismatches.append("reemitted payload bytes")
        if mismatches:
            raise ValueError(
                "SDF round-trip result artifacts are not cross-consistent: "
                f"{mismatches}"
            )


@dataclass(frozen=True, slots=True)
class _ValidatedWriteState:
    system: AllAtomSystem
    header: tuple[str, str, str]
    coordinate_tokens: tuple[tuple[str, str, str], ...]
    atom_charge_codes: tuple[int, ...]
    charge_pairs: tuple[tuple[int, int], ...]
    isotope_pairs: tuple[tuple[int, int], ...]
    bond_rows: tuple[tuple[int, int, int], ...]
    representable_state_document: Mapping[str, Any]


def _snapshot_parser_system(system: AllAtomSystem) -> AllAtomSystem:
    if type(system) is not AllAtomSystem:
        raise TypeError("SDF V2000 writer input must be an exact AllAtomSystem")
    coordinates = system.coordinates
    if coordinates.device.type != "cpu":
        raise SdfV2000WriteError(
            "unsupported_coordinate_device",
            "parser-owned SDF coordinates must be on CPU",
            location="coordinates",
        )
    if coordinates.dtype is not torch.float64:
        raise SdfV2000WriteError(
            "unsupported_coordinate_dtype",
            "parser-owned SDF coordinates must use float64",
            location="coordinates",
        )
    if coordinates.requires_grad:
        raise SdfV2000WriteError(
            "coordinate_gradient_state_unsupported",
            "SDF writing does not accept coordinates requiring gradients",
            location="coordinates",
        )
    try:
        snapshot = replace(system, coordinates=coordinates.detach().clone())
        require_valid_all_atom_system(snapshot)
    except (MolecularValidationError, TypeError, ValueError, RuntimeError) as exc:
        raise SdfV2000WriteError(
            "canonical_validation_failed",
            str(exc),
            location="system",
        ) from exc
    return snapshot


def _safe_header(system: AllAtomSystem) -> tuple[str, str, str]:
    metadata = _require_exact_keys(
        system.metadata,
        frozenset({"sdf_v2000_header"}),
        code="unsupported_system_metadata",
        location="metadata",
    )
    header = _require_exact_keys(
        metadata["sdf_v2000_header"],
        frozenset({"title", "program", "comment"}),
        code="unsupported_sdf_header",
        location="metadata.sdf_v2000_header",
    )
    values: list[str] = []
    for key in ("title", "program", "comment"):
        value = header[key]
        if type(value) is not str:
            raise SdfV2000WriteError(
                "unsupported_sdf_header",
                "header values must be strings",
                location=f"metadata.sdf_v2000_header.{key}",
            )
        if len(value) > _MAX_LINE_CHARS or any(
            ord(character) < 0x20 or ord(character) > 0x7E
            for character in value
        ):
            raise SdfV2000WriteError(
                "unsupported_sdf_header",
                "header text must contain at most 256 printable ASCII characters",
                location=f"metadata.sdf_v2000_header.{key}",
            )
        values.append(value)
    return values[0], values[1], values[2]


def _require_parser_context(system: AllAtomSystem) -> None:
    if len(system.residues) != 1:
        raise SdfV2000WriteError(
            "unsupported_residue_context",
            "strict SDF output requires exactly one parser-synthesized residue",
            location="residues",
        )
    residue = system.residues[0]
    expected_residue = (
        residue.index == 0
        and residue.name == "LIG"
        and residue.chain_index == 0
        and residue.sequence_number == 1
        and residue.atom_indices == tuple(range(system.atom_count))
        and residue.insertion_code == ""
        and residue.entity_type == "non_polymer"
        and residue.hetero is True
        and dict(residue.metadata) == {"source": "sdf_v2000_single_record"}
    )
    if not expected_residue:
        raise SdfV2000WriteError(
            "unsupported_residue_context",
            "residue does not match the exact parser-synthesized LIG context",
            location="residues[0]",
        )
    if len(system.chains) != 1:
        raise SdfV2000WriteError(
            "unsupported_chain_context",
            "strict SDF output requires exactly one parser-synthesized chain",
            location="chains",
        )
    chain = system.chains[0]
    expected_chain = (
        chain.index == 0
        and chain.chain_id == "L"
        and chain.residue_indices == (0,)
        and chain.entity_id == "ligand"
        and dict(chain.metadata) == {"source": "sdf_v2000_single_record"}
    )
    if not expected_chain:
        raise SdfV2000WriteError(
            "unsupported_chain_context",
            "chain does not match the exact parser-synthesized L context",
            location="chains[0]",
        )


def _coordinate_token(value: float, *, location: str) -> str:
    if not math.isfinite(value):
        raise SdfV2000WriteError(
            "nonfinite_coordinate",
            "coordinate must be finite",
            location=location,
        )
    token = f"{value:10.4f}"
    if len(token) != 10 or "e" in token.lower():
        raise SdfV2000WriteError(
            "coordinate_field_overflow",
            "coordinate does not fit the fixed-width F10.4 field",
            location=location,
        )
    reparsed = float(token)
    if _binary64_hex(reparsed) != _binary64_hex(value):
        raise SdfV2000WriteError(
            "coordinate_rounding_required",
            "coordinate is not exactly representable by fixed-width F10.4",
            location=location,
        )
    return token


def _validate_provenance_and_coverage(
    system: AllAtomSystem,
    *,
    normalized_bond_endpoints: bool,
) -> None:
    provenance = system.provenance
    if provenance.source_format != "sdf_v2000":
        raise SdfV2000WriteError(
            "unsupported_source_format",
            "writer accepts only strict SDF V2000 parser output",
            location="provenance.source_format",
        )
    if (
        provenance.parser_name != _SDF_PARSER_NAME
        or provenance.parser_version != SDF_V2000_PARSER_VERSION
    ):
        raise SdfV2000WriteError(
            "unsupported_parser_pedigree",
            "writer requires the current strict SDF V2000 parser pedigree",
            location="provenance",
        )
    expected_operations = _PARSER_OPERATIONS + (
        (("canonicalize_bond_endpoint_order",) if normalized_bond_endpoints else ())
    )
    if provenance.operations != expected_operations:
        raise SdfV2000WriteError(
            "unsupported_provenance_operations",
            "provenance operations are not the exact parser-owned transform ledger",
            location="provenance.operations",
        )
    if provenance.parent_sha256:
        raise SdfV2000WriteError(
            "unsupported_parent_provenance",
            "parser-owned SDF state must not carry parent source hashes",
            location="provenance.parent_sha256",
        )
    if provenance.preparation_ready or provenance.claim_safe:
        raise SdfV2000WriteError(
            "unsupported_authority_state",
            "SDF source writing cannot preserve preparation or claim authority",
            location="provenance",
        )
    if _SHA256_RE.fullmatch(provenance.source_sha256) is None:
        raise SdfV2000WriteError(
            "invalid_source_sha256",
            "parser-owned source SHA-256 is missing or malformed",
            location="provenance.source_sha256",
        )

    metadata = _require_exact_keys(
        provenance.metadata,
        _PROVENANCE_METADATA_KEYS,
        code="unsupported_provenance_metadata",
        location="provenance.metadata",
    )
    topology_sha256 = canonical_topology_sha256(system)
    expected_coverage = SdfV2000Coverage(
        atom_count=system.atom_count,
        bond_count=len(system.bonds),
        explicit_hydrogen_count=sum(atom.element == "H" for atom in system.atoms),
        formal_charge_count=sum(atom.formal_charge != 0 for atom in system.atoms),
        isotope_count=sum(
            atom.isotope_mass_number is not None for atom in system.atoms
        ),
        aromatic_bond_count=sum(bond.aromatic for bond in system.bonds),
        atom_map_count=sum(atom.atom_map is not None for atom in system.atoms),
        canonical_topology_sha256=topology_sha256,
    ).to_dict()
    if metadata["coverage"] != expected_coverage:
        raise SdfV2000WriteError(
            "stale_sdf_coverage",
            "attached SDF coverage does not match current canonical state",
            location="provenance.metadata.coverage",
        )
    if (
        metadata["canonical_topology_schema_id"]
        != CANONICAL_TOPOLOGY_SCHEMA_ID
        or metadata["canonical_topology_sha256"] != topology_sha256
        or not attached_canonical_topology_sha256_matches(system)
    ):
        raise SdfV2000WriteError(
            "stale_canonical_topology_digest",
            "attached canonical topology digest is missing or stale",
            location="provenance.metadata",
        )
    if (
        metadata["parser_observation_schema_id"] != PARSER_OBSERVATION_SCHEMA_ID
        or type(metadata["parser_observation_sha256"]) is not str
        or _SHA256_RE.fullmatch(metadata["parser_observation_sha256"]) is None
        or not attached_parser_observation_sha256_matches(system)
    ):
        raise SdfV2000WriteError(
            "stale_parser_observation_digest",
            "attached parser-observation digest is missing or stale",
            location="provenance.metadata",
        )


def _validate_write_state(system: AllAtomSystem) -> _ValidatedWriteState:
    snapshot = _snapshot_parser_system(system)
    if snapshot.schema_id != ALL_ATOM_SCHEMA_ID:
        raise SdfV2000WriteError(
            "unsupported_system_schema",
            "writer requires the current all-atom schema",
            location="schema_id",
        )
    if not 1 <= snapshot.atom_count <= 999:
        raise SdfV2000WriteError(
            "unsupported_atom_count",
            "SDF V2000 atom count must be in [1, 999]",
            location="atoms",
        )
    if len(snapshot.bonds) > 999:
        raise SdfV2000WriteError(
            "unsupported_bond_count",
            "SDF V2000 bond count must be in [0, 999]",
            location="bonds",
        )
    if snapshot.model_count != 1:
        raise SdfV2000WriteError(
            "unsupported_coordinate_model_count",
            "strict SDF output requires exactly one coordinate model",
            location="coordinates",
        )
    if snapshot.coordinate_unit != "angstrom":
        raise SdfV2000WriteError(
            "unsupported_coordinate_unit",
            "strict SDF output requires Angstrom coordinates",
            location="coordinate_unit",
        )
    if snapshot.cell is not None:
        raise SdfV2000WriteError(
            "unsupported_unit_cell",
            "the strict SDF subset cannot preserve unit-cell state",
            location="cell",
        )

    header = _safe_header(snapshot)
    _require_parser_context(snapshot)

    atom_documents: list[dict[str, Any]] = []
    formal_charge_sources: list[str] = []
    isotope_pairs: list[tuple[int, int]] = []
    for index, atom in enumerate(snapshot.atoms):
        location = f"atoms[{index}]"
        metadata = _require_exact_keys(
            atom.metadata,
            _ATOM_METADATA_KEYS,
            code="unsupported_atom_metadata",
            location=f"{location}.metadata",
        )
        expected_marker_values = {
            "sdf_source_atom_index": index + 1,
            "sdf_atom_map": 0 if atom.atom_map is None else atom.atom_map,
            "hydrogen_origin": "source" if atom.element == "H" else "not_hydrogen",
        }
        for key, expected in expected_marker_values.items():
            if type(metadata[key]) is not type(expected) or metadata[key] != expected:
                raise SdfV2000WriteError(
                    "inconsistent_atom_metadata",
                    f"{key} does not match parser-owned atom state",
                    location=f"{location}.metadata.{key}",
                )
        formal_charge_source = metadata["formal_charge_source"]
        if formal_charge_source not in {
            "sdf_v2000_atom_block",
            "sdf_v2000_m_chg",
        }:
            raise SdfV2000WriteError(
                "inconsistent_formal_charge_source",
                "formal-charge source marker is unsupported",
                location=f"{location}.metadata.formal_charge_source",
            )
        formal_charge_sources.append(formal_charge_source)
        if atom.name != f"{atom.element}{index + 1}":
            raise SdfV2000WriteError(
                "unsupported_atom_name",
                "atom name is not the parser-synthesized element/index name",
                location=f"{location}.name",
            )
        if atom.residue_index != 0 or atom.serial != index + 1:
            raise SdfV2000WriteError(
                "unsupported_atom_identity_context",
                "atom residue or serial identity is not parser-shaped",
                location=location,
            )
        if not atom.formal_charge_known:
            raise SdfV2000WriteError(
                "unknown_formal_charge",
                "SDF output requires a known formal charge for every atom",
                location=f"{location}.formal_charge_known",
            )
        if atom.formal_charge < -15 or atom.formal_charge > 15:
            raise SdfV2000WriteError(
                "unsupported_formal_charge",
                "formal charge must be in [-15, 15]",
                location=f"{location}.formal_charge",
            )
        if atom.partial_charge_e is not None:
            raise SdfV2000WriteError(
                "unsupported_partial_charge",
                "partial charge cannot be represented by the strict SDF subset",
                location=f"{location}.partial_charge_e",
            )
        if atom.mass_da is not None:
            raise SdfV2000WriteError(
                "unsupported_atom_mass",
                "free-form atom mass cannot be represented; use an isotope mass number",
                location=f"{location}.mass_da",
            )
        if atom.altloc or atom.occupancy is not None or atom.b_factor is not None:
            raise SdfV2000WriteError(
                "unsupported_atom_coordinate_context",
                "altloc, occupancy, and B-factor state cannot be represented",
                location=location,
            )
        if atom.stereo != "unspecified":
            raise SdfV2000WriteError(
                "unsupported_atom_stereo",
                "the strict SDF parser/writer subset supports only unspecified atom stereo",
                location=f"{location}.stereo",
            )
        if atom.atom_map is not None and not 1 <= atom.atom_map <= 999:
            raise SdfV2000WriteError(
                "unsupported_atom_map",
                "atom map must be in [1, 999]",
                location=f"{location}.atom_map",
            )
        if atom.isotope_mass_number is not None:
            isotope_pairs.append((index + 1, atom.isotope_mass_number))
        atom_documents.append(
            {
                "index": atom.index,
                "name": atom.name,
                "element": atom.element,
                "atomic_number": atom.atomic_number,
                "formal_charge": atom.formal_charge,
                "formal_charge_known": atom.formal_charge_known,
                "isotope_mass_number": atom.isotope_mass_number,
                "serial": atom.serial,
                "atom_map": atom.atom_map,
                "aromatic": atom.aromatic,
                "stereo": atom.stereo,
                "parser_markers": dict(metadata),
            }
        )

    use_m_chg = any(
        source == "sdf_v2000_m_chg" for source in formal_charge_sources
    )
    atom_charge_codes: list[int] = []
    charge_pairs: list[tuple[int, int]] = []
    for index, (atom, source) in enumerate(
        zip(snapshot.atoms, formal_charge_sources, strict=True)
    ):
        expected_source = (
            "sdf_v2000_m_chg"
            if use_m_chg and atom.formal_charge != 0
            else "sdf_v2000_atom_block"
        )
        if source != expected_source:
            raise SdfV2000WriteError(
                "inconsistent_formal_charge_source",
                "formal-charge source markers cannot be emitted without changing meaning",
                location=f"atoms[{index}].metadata.formal_charge_source",
            )
        if use_m_chg:
            atom_charge_codes.append(0)
            if atom.formal_charge != 0:
                charge_pairs.append((index + 1, atom.formal_charge))
        else:
            code = _FORMAL_CHARGE_TO_ATOM_BLOCK_CODE.get(atom.formal_charge)
            if code is None:
                raise SdfV2000WriteError(
                    "unsupported_atom_block_formal_charge",
                    "atom-block charge origin supports only formal charges in [-3, 3]",
                    location=f"atoms[{index}].formal_charge",
                )
            atom_charge_codes.append(code)

    aromatic_atom_indices: set[int] = set()
    bond_rows: list[tuple[int, int, int]] = []
    bond_documents: list[dict[str, Any]] = []
    normalized_bond_endpoints = False
    for index, bond in enumerate(snapshot.bonds):
        location = f"bonds[{index}]"
        metadata = _require_exact_keys(
            bond.metadata,
            _BOND_METADATA_KEYS,
            code="unsupported_bond_metadata",
            location=f"{location}.metadata",
        )
        if bond.source != "sdf_v2000":
            raise SdfV2000WriteError(
                "unsupported_bond_source",
                "bond source is not the strict SDF parser",
                location=f"{location}.source",
            )
        if bond.stereo != "none":
            raise SdfV2000WriteError(
                "unsupported_bond_stereo",
                "the strict SDF parser/writer subset supports only no bond stereo",
                location=f"{location}.stereo",
            )
        bond_type = _BOND_STATE_TO_TYPE.get((bond.order, bond.aromatic))
        if bond_type is None:
            raise SdfV2000WriteError(
                "unsupported_bond_state",
                "bond order/aromatic state is not one of V2000 types 1-4",
                location=location,
            )
        source_i = metadata["sdf_source_atom_i"]
        source_j = metadata["sdf_source_atom_j"]
        expected_metadata = {
            "sdf_source_bond_index": index + 1,
            "sdf_bond_type": bond_type,
        }
        for key, expected in expected_metadata.items():
            if type(metadata[key]) is not int or metadata[key] != expected:
                raise SdfV2000WriteError(
                    "inconsistent_bond_metadata",
                    f"{key} does not match canonical bond state",
                    location=f"{location}.metadata.{key}",
                )
        if type(source_i) is not int or type(source_j) is not int:
            raise SdfV2000WriteError(
                "inconsistent_bond_metadata",
                "source bond endpoints must be integers",
                location=f"{location}.metadata",
            )
        if {source_i - 1, source_j - 1} != {bond.atom_i, bond.atom_j}:
            raise SdfV2000WriteError(
                "inconsistent_bond_metadata",
                "source bond endpoints do not match canonical endpoints",
                location=f"{location}.metadata",
            )
        normalized_bond_endpoints = normalized_bond_endpoints or (
            source_i - 1 != bond.atom_i
        )
        if bond.aromatic:
            aromatic_atom_indices.update((bond.atom_i, bond.atom_j))
        bond_rows.append((source_i, source_j, bond_type))
        bond_documents.append(
            {
                "index": bond.index,
                "atom_i": bond.atom_i,
                "atom_j": bond.atom_j,
                "order_ieee754_binary64_be": _binary64_hex(bond.order),
                "aromatic": bond.aromatic,
                "stereo": bond.stereo,
                "source": bond.source,
                "parser_markers": dict(metadata),
            }
        )

    observed_aromatic_atoms = {
        atom.index for atom in snapshot.atoms if atom.aromatic
    }
    if observed_aromatic_atoms != aromatic_atom_indices:
        raise SdfV2000WriteError(
            "inconsistent_aromatic_atom_flags",
            "aromatic atom flags must equal the endpoints of type-4 aromatic bonds",
            location="atoms",
        )

    _validate_provenance_and_coverage(
        snapshot,
        normalized_bond_endpoints=normalized_bond_endpoints,
    )

    coordinate_tokens: list[tuple[str, str, str]] = []
    coordinate_document: list[list[str]] = []
    for atom_index in range(snapshot.atom_count):
        tokens: list[str] = []
        binary64_values: list[str] = []
        for axis_index, axis in enumerate(("x", "y", "z")):
            value = float(snapshot.coordinates[0, atom_index, axis_index].item())
            tokens.append(
                _coordinate_token(
                    value,
                    location=f"coordinates[0,{atom_index},{axis}]",
                )
            )
            binary64_values.append(_binary64_hex(value))
        coordinate_tokens.append((tokens[0], tokens[1], tokens[2]))
        coordinate_document.append(binary64_values)

    residue = snapshot.residues[0]
    chain = snapshot.chains[0]
    representable_state_document = {
        "schema_id": SDF_V2000_REPRESENTABLE_STATE_SCHEMA_ID,
        "system_schema_id": snapshot.schema_id,
        "parser_name": snapshot.provenance.parser_name,
        "parser_version": snapshot.provenance.parser_version,
        "parser_operations": list(snapshot.provenance.operations),
        "header": {
            "title": header[0],
            "program": header[1],
            "comment": header[2],
        },
        "atom_count": snapshot.atom_count,
        "bond_count": len(snapshot.bonds),
        "model_count": 1,
        "coordinate_unit": "angstrom",
        "coordinates_ieee754_binary64_be": coordinate_document,
        "formal_charge_encoding": "m_chg" if use_m_chg else "atom_block",
        "atoms": atom_documents,
        "bonds": bond_documents,
        "residue": {
            "index": residue.index,
            "name": residue.name,
            "chain_index": residue.chain_index,
            "sequence_number": residue.sequence_number,
            "atom_indices": list(residue.atom_indices),
            "insertion_code": residue.insertion_code,
            "entity_type": residue.entity_type,
            "hetero": residue.hetero,
            "metadata": dict(residue.metadata),
        },
        "chain": {
            "index": chain.index,
            "chain_id": chain.chain_id,
            "residue_indices": list(chain.residue_indices),
            "entity_id": chain.entity_id,
            "metadata": dict(chain.metadata),
        },
        "cell": None,
        "preservation_scope": list(_PRESERVATION_SCOPE),
    }
    return _ValidatedWriteState(
        system=snapshot,
        header=header,
        coordinate_tokens=tuple(coordinate_tokens),
        atom_charge_codes=tuple(atom_charge_codes),
        charge_pairs=tuple(charge_pairs),
        isotope_pairs=tuple(isotope_pairs),
        bond_rows=tuple(bond_rows),
        representable_state_document=representable_state_document,
    )


def _property_lines(
    property_name: str,
    pairs: tuple[tuple[int, int], ...],
) -> list[str]:
    lines: list[str] = []
    for start in range(0, len(pairs), 8):
        chunk = pairs[start : start + 8]
        line = f"M  {property_name}{len(chunk):3d}" + "".join(
            f"{atom_index:4d}{value:4d}" for atom_index, value in chunk
        )
        lines.append(line)
    return lines


def _emit_payload(state: _ValidatedWriteState) -> bytes:
    system = state.system
    counts_line = (
        f"{system.atom_count:3d}{len(system.bonds):3d}"
        "  0  0  0  0  0  0  0  0999 V2000"
    )
    if len(counts_line) != 39:  # pragma: no cover - fixed contract invariant
        raise RuntimeError("internal SDF counts line width drifted")
    lines = [*state.header, counts_line]
    for index, atom in enumerate(system.atoms):
        x, y, z = state.coordinate_tokens[index]
        atom_map = 0 if atom.atom_map is None else atom.atom_map
        line = (
            f"{x}{y}{z} {atom.element:<3}{0:2d}"
            f"{state.atom_charge_codes[index]:3d}"
            f"{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}"
            f"{atom_map:3d}{0:3d}{0:3d}"
        )
        if len(line) != 69:  # pragma: no cover - validated widths above
            raise RuntimeError("internal SDF atom line width drifted")
        lines.append(line)
    lines.extend(
        f"{atom_i:3d}{atom_j:3d}{bond_type:3d}{0:3d}"
        for atom_i, atom_j, bond_type in state.bond_rows
    )
    lines.extend(_property_lines("CHG", state.charge_pairs))
    lines.extend(_property_lines("ISO", state.isotope_pairs))
    lines.extend(("M  END", "$$$$"))
    if len(lines) > _MAX_OUTPUT_LINES:
        raise SdfV2000WriteError(
            "output_too_many_lines",
            "emitted SDF exceeds the parser line safety limit",
        )
    if any(len(line) > _MAX_LINE_CHARS for line in lines):
        raise SdfV2000WriteError(
            "output_line_too_long",
            "emitted SDF exceeds the parser line-width safety limit",
        )
    try:
        payload = ("\n".join(lines) + "\n").encode("ascii")
    except UnicodeEncodeError as exc:  # pragma: no cover - header preflight
        raise RuntimeError("validated SDF output was not ASCII") from exc
    if len(payload) > _MAX_OUTPUT_BYTES:
        raise SdfV2000WriteError(
            "output_too_large",
            "emitted SDF exceeds the parser byte safety limit",
        )
    return payload


def sdf_v2000_representable_state_sha256(system: AllAtomSystem) -> str:
    """Hash the exact parser-owned state that this writer can reproduce."""

    state = _validate_write_state(system)
    return _sha256_document(state.representable_state_document)


def write_sdf_v2000(system: AllAtomSystem) -> SdfV2000WriteResult:
    """Emit deterministic SDF V2000 bytes and a non-authoritative receipt."""

    state = _validate_write_state(system)
    payload = _emit_payload(state)
    output_source_sha256 = hashlib.sha256(payload).hexdigest()
    receipt = SdfV2000WriteReceipt(
        input_system_schema_id=state.system.schema_id,
        parent_source_sha256=state.system.provenance.source_sha256,
        input_snapshot_sha256=canonical_all_atom_snapshot_digest(state.system),
        input_topology_sha256=canonical_topology_sha256(state.system),
        input_representable_state_sha256=_sha256_document(
            state.representable_state_document
        ),
        output_source_sha256=output_source_sha256,
        output_byte_count=len(payload),
        atom_count=state.system.atom_count,
        bond_count=len(state.system.bonds),
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )
    return SdfV2000WriteResult(
        payload=payload,
        receipt=receipt,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )


def serialize_sdf_v2000(system: AllAtomSystem) -> bytes:
    """Return deterministic SDF V2000 bytes for exactly representable state."""

    return write_sdf_v2000(system).payload


def round_trip_sdf_v2000_source(
    data: bytes,
    *,
    source_id: str = "",
) -> SdfV2000RoundTripResult:
    """Execute and verify ``source -> canonical -> source -> canonical``.

    Equality covers only :data:`SDF_V2000_REPRESENTABLE_STATE_SCHEMA_ID`.
    Dynamic raw-source provenance and the complete canonical snapshot are bound
    in the report but are intentionally not equality or authentication claims.
    """

    source_ingest = parse_sdf_v2000(data, source_id=source_id)
    write_result = write_sdf_v2000(source_ingest.system)
    reparsed_ingest = parse_sdf_v2000(
        write_result.payload,
        source_id=source_id,
    )
    reemitted = write_sdf_v2000(reparsed_ingest.system)

    input_topology_sha256 = canonical_topology_sha256(source_ingest.system)
    reparsed_topology_sha256 = canonical_topology_sha256(reparsed_ingest.system)
    input_state_sha256 = write_result.receipt.input_representable_state_sha256
    reparsed_state_sha256 = reemitted.receipt.input_representable_state_sha256
    mismatches: list[str] = []
    input_source_sha256 = hashlib.sha256(data).hexdigest()
    if source_ingest.system.provenance.source_sha256 != input_source_sha256:
        mismatches.append("input_source_sha256")
    if write_result.receipt.parent_source_sha256 != input_source_sha256:
        mismatches.append("writer_parent_source_sha256")
    if input_topology_sha256 != reparsed_topology_sha256:
        mismatches.append("canonical_topology")
    if input_state_sha256 != reparsed_state_sha256:
        mismatches.append("representable_state")
    if (
        reparsed_ingest.system.provenance.source_sha256
        != write_result.receipt.output_source_sha256
    ):
        mismatches.append("reparsed_source_sha256")
    if reemitted.payload != write_result.payload:
        mismatches.append("reemitted_bytes")
    if mismatches:
        raise SdfV2000WriteError(
            "round_trip_mismatch",
            f"declared SDF round-trip projection failed: {mismatches}",
        )

    report = SdfV2000RoundTripReport(
        input_source_sha256=input_source_sha256,
        input_snapshot_sha256=write_result.receipt.input_snapshot_sha256,
        input_topology_sha256=input_topology_sha256,
        input_representable_state_sha256=input_state_sha256,
        writer_receipt_sha256=write_result.receipt.receipt_sha256,
        emitted_source_sha256=write_result.receipt.output_source_sha256,
        reparsed_snapshot_sha256=canonical_all_atom_snapshot_digest(
            reparsed_ingest.system
        ),
        reparsed_topology_sha256=reparsed_topology_sha256,
        reparsed_representable_state_sha256=reparsed_state_sha256,
        reemitted_source_sha256=hashlib.sha256(reemitted.payload).hexdigest(),
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )
    return SdfV2000RoundTripResult(
        source_ingest=source_ingest,
        write_result=write_result,
        reparsed_ingest=reparsed_ingest,
        report=report,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )


__all__ = [
    "SDF_V2000_REPRESENTABLE_STATE_SCHEMA_ID",
    "SDF_V2000_ROUND_TRIP_REPORT_SCHEMA_ID",
    "SDF_V2000_WRITER_VERSION",
    "SDF_V2000_WRITE_RECEIPT_SCHEMA_ID",
    "SdfV2000RoundTripReport",
    "SdfV2000RoundTripResult",
    "SdfV2000WriteError",
    "SdfV2000WriteReceipt",
    "SdfV2000WriteResult",
    "round_trip_sdf_v2000_source",
    "sdf_v2000_representable_state_sha256",
    "serialize_sdf_v2000",
    "write_sdf_v2000",
]
