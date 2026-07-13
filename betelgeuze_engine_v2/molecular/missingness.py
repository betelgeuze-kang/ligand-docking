"""Immutable, preserve-only source-reported missingness evidence.

This module records only missing-residue and missing-atom claims that an input
source explicitly reported.  It does not compare those claims with a reference
sequence, residue template, chemical component dictionary, or the canonical
topology.  It never infers unreported missingness and never completes atoms or
residues.  The topology, coordinate-scope, alternate-location, and assembly
fields are evidence bindings, not assertions that the source claims are
chemically complete or correct.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Mapping

from .topology import CANONICAL_TOPOLOGY_SCHEMA_ID


MISSINGNESS_REPORT_SCHEMA_VERSION = "1.0.0"
MISSINGNESS_REPORT_SCHEMA_ID = (
    "betelgeuze.source_reported_missingness/"
    f"{MISSINGNESS_REPORT_SCHEMA_VERSION}"
)
MISSINGNESS_PRESERVATION_POLICY_ID = (
    "source_reported_missingness_preserve_only_v1"
)

MAX_MISSING_RESIDUE_CLAIMS = 20_000
MAX_MISSING_ATOM_CLAIMS = 100_000
MAX_TOTAL_MISSINGNESS_CLAIMS = 100_000
MAX_RAW_PAYLOAD_DEPTH = 16
MAX_RAW_PAYLOAD_NODES = 4_096
MAX_RAW_PAYLOAD_BYTES = 65_536
MAX_REPORT_CANONICAL_BYTES = 32 * 1024 * 1024

_MAX_CONTROL_STRING_CHARS = 4_096
_MAX_SOURCE_CATEGORY_CHARS = 256
_MAX_BINDING_ID_CHARS = 256
_MAX_JSON_INTEGER_MAGNITUDE = (1 << 63) - 1

_FIXED_BLOCKERS = (
    "source_reported_missingness_preserved_only",
    "source_reported_missingness_not_completeness_evidence",
    "reference_chemistry_not_consulted",
    "completion_not_attempted",
    "preparation_not_assessed",
)


class _FrozenJsonList(tuple):
    """Read-only JSON array retaining ordinary list/tuple equality."""

    __hash__ = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (list, tuple)):
            return tuple.__eq__(self, tuple(other))
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        equal = self.__eq__(other)
        return NotImplemented if equal is NotImplemented else not equal


def _strict_string(
    value: Any,
    *,
    field_name: str,
    allow_empty: bool,
    max_chars: int = _MAX_CONTROL_STRING_CHARS,
) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a string")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError(f"{field_name} must contain only Unicode scalar values")
    if not allow_empty and not value:
        raise ValueError(f"{field_name} must be nonempty")
    if len(value) > max_chars:
        raise ValueError(f"{field_name} exceeds the {max_chars}-character limit")
    return value


def _strict_positive_int(value: Any, *, field_name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    if value > _MAX_JSON_INTEGER_MAGNITUDE:
        raise ValueError(f"{field_name} integer exceeds signed 64-bit range")
    return value


def _strict_nonnegative_int(value: Any, *, field_name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    if value > _MAX_JSON_INTEGER_MAGNITUDE:
        raise ValueError(f"{field_name} integer exceeds signed 64-bit range")
    return value


def _validate_sha256(value: Any, *, field_name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field_name} must be a lowercase ASCII SHA-256")
    return value


def _freeze_json_value(
    value: Any,
    *,
    field_name: str,
    depth: int,
    active_container_ids: set[int],
    node_count: list[int],
) -> Any:
    node_count[0] += 1
    if node_count[0] > MAX_RAW_PAYLOAD_NODES:
        raise ValueError(
            f"{field_name} exceeds the {MAX_RAW_PAYLOAD_NODES}-node safety limit"
        )
    if depth > MAX_RAW_PAYLOAD_DEPTH:
        raise ValueError(
            f"{field_name} exceeds the {MAX_RAW_PAYLOAD_DEPTH}-level depth limit"
        )
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if abs(value) > _MAX_JSON_INTEGER_MAGNITUDE:
            raise ValueError(f"{field_name} integer exceeds signed 64-bit range")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{field_name} floats must be finite")
        return value
    if type(value) is str:
        return _strict_string(value, field_name=field_name, allow_empty=True)
    if isinstance(value, Mapping):
        container_id = id(value)
        if container_id in active_container_ids:
            raise ValueError(f"{field_name} must not contain a reference cycle")
        active_container_ids.add(container_id)
        try:
            frozen: dict[str, Any] = {}
            for key, item in value.items():
                normalized_key = _strict_string(
                    key,
                    field_name=f"{field_name} key",
                    allow_empty=False,
                )
                frozen[normalized_key] = _freeze_json_value(
                    item,
                    field_name=f"{field_name}.{normalized_key}",
                    depth=depth + 1,
                    active_container_ids=active_container_ids,
                    node_count=node_count,
                )
            return MappingProxyType(frozen)
        finally:
            active_container_ids.remove(container_id)
    if type(value) is list or isinstance(value, _FrozenJsonList):
        container_id = id(value)
        if container_id in active_container_ids:
            raise ValueError(f"{field_name} must not contain a reference cycle")
        active_container_ids.add(container_id)
        try:
            return _FrozenJsonList(
                _freeze_json_value(
                    item,
                    field_name=f"{field_name}[{index}]",
                    depth=depth + 1,
                    active_container_ids=active_container_ids,
                    node_count=node_count,
                )
                for index, item in enumerate(value)
            )
        finally:
            active_container_ids.remove(container_id)
    raise TypeError(
        f"{field_name} supports only JSON null, boolean, signed 64-bit integer, "
        "finite float, string, list, and mapping values"
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _freeze_raw_payload(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    if not value:
        raise ValueError(f"{field_name} must be nonempty")
    frozen = _freeze_json_value(
        value,
        field_name=field_name,
        depth=0,
        active_container_ids=set(),
        node_count=[0],
    )
    if not isinstance(frozen, Mapping):  # pragma: no cover - root check above
        raise TypeError(f"{field_name} must be a mapping")
    raw_bytes = _canonical_json_bytes(frozen)
    if len(raw_bytes) > MAX_RAW_PAYLOAD_BYTES:
        raise ValueError(
            f"{field_name} exceeds the {MAX_RAW_PAYLOAD_BYTES}-byte canonical limit"
        )
    return frozen


def _validate_claim_identity(
    *,
    source_ordinal: Any,
    source_category: Any,
    source_model_id: Any,
    source_chain_id: Any,
    source_residue_id: Any,
    source_residue_name: Any,
    source_insertion_code: Any,
    raw_payload: Any,
    field_prefix: str,
) -> Mapping[str, Any]:
    _strict_positive_int(source_ordinal, field_name=f"{field_prefix}.source_ordinal")
    _strict_string(
        source_category,
        field_name=f"{field_prefix}.source_category",
        allow_empty=False,
        max_chars=_MAX_SOURCE_CATEGORY_CHARS,
    )
    for name, value, allow_empty in (
        ("source_model_id", source_model_id, True),
        ("source_chain_id", source_chain_id, True),
        ("source_residue_id", source_residue_id, False),
        ("source_residue_name", source_residue_name, False),
        ("source_insertion_code", source_insertion_code, True),
    ):
        _strict_string(
            value,
            field_name=f"{field_prefix}.{name}",
            allow_empty=allow_empty,
        )
    return _freeze_raw_payload(
        raw_payload,
        field_name=f"{field_prefix}.raw_payload",
    )


@dataclass(frozen=True)
class SourceReportedMissingResidueClaim:
    """One source row explicitly reporting an unobserved residue."""

    source_ordinal: int
    source_category: str
    source_model_id: str
    source_chain_id: str
    source_residue_id: str
    source_residue_name: str
    source_insertion_code: str = ""
    raw_payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        frozen = _validate_claim_identity(
            source_ordinal=self.source_ordinal,
            source_category=self.source_category,
            source_model_id=self.source_model_id,
            source_chain_id=self.source_chain_id,
            source_residue_id=self.source_residue_id,
            source_residue_name=self.source_residue_name,
            source_insertion_code=self.source_insertion_code,
            raw_payload=self.raw_payload,
            field_prefix="missing_residue_claim",
        )
        object.__setattr__(self, "raw_payload", frozen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_ordinal": self.source_ordinal,
            "source_category": self.source_category,
            "source_model_id": self.source_model_id,
            "source_chain_id": self.source_chain_id,
            "source_residue_id": self.source_residue_id,
            "source_residue_name": self.source_residue_name,
            "source_insertion_code": self.source_insertion_code,
            "raw_payload": _json_safe(self.raw_payload),
        }


@dataclass(frozen=True)
class SourceReportedMissingAtomClaim:
    """One source row explicitly reporting an unobserved atom."""

    source_ordinal: int
    source_category: str
    source_model_id: str
    source_chain_id: str
    source_residue_id: str
    source_residue_name: str
    source_atom_name: str
    source_insertion_code: str = ""
    source_altloc_id: str = ""
    raw_payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        frozen = _validate_claim_identity(
            source_ordinal=self.source_ordinal,
            source_category=self.source_category,
            source_model_id=self.source_model_id,
            source_chain_id=self.source_chain_id,
            source_residue_id=self.source_residue_id,
            source_residue_name=self.source_residue_name,
            source_insertion_code=self.source_insertion_code,
            raw_payload=self.raw_payload,
            field_prefix="missing_atom_claim",
        )
        _strict_string(
            self.source_atom_name,
            field_name="missing_atom_claim.source_atom_name",
            allow_empty=False,
        )
        _strict_string(
            self.source_altloc_id,
            field_name="missing_atom_claim.source_altloc_id",
            allow_empty=True,
            max_chars=_MAX_BINDING_ID_CHARS,
        )
        object.__setattr__(self, "raw_payload", frozen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_ordinal": self.source_ordinal,
            "source_category": self.source_category,
            "source_model_id": self.source_model_id,
            "source_chain_id": self.source_chain_id,
            "source_residue_id": self.source_residue_id,
            "source_residue_name": self.source_residue_name,
            "source_insertion_code": self.source_insertion_code,
            "source_atom_name": self.source_atom_name,
            "source_altloc_id": self.source_altloc_id,
            "raw_payload": _json_safe(self.raw_payload),
        }


def _expected_blockers(
    missing_residue_count: int,
    missing_atom_count: int,
) -> tuple[str, ...]:
    blockers = list(_FIXED_BLOCKERS)
    if missing_residue_count:
        blockers.append("source_reports_missing_residues")
    if missing_atom_count:
        blockers.append("source_reports_missing_atoms")
    return tuple(blockers)


def _validate_ordered_claims(
    value: Any,
    *,
    field_name: str,
    claim_type: type,
    limit: int,
) -> None:
    if type(value) is not tuple:
        raise TypeError(f"{field_name} must be a tuple")
    if len(value) > limit:
        raise ValueError(f"{field_name} exceeds the {limit}-claim limit")
    previous_ordinal = 0
    for index, claim in enumerate(value):
        if type(claim) is not claim_type:
            raise TypeError(
                f"{field_name}[{index}] must be an exact {claim_type.__name__}"
            )
        if claim.source_ordinal <= previous_ordinal:
            raise ValueError(
                f"{field_name} source_ordinal values must be strictly increasing"
            )
        previous_ordinal = claim.source_ordinal


@dataclass(frozen=True)
class SourceReportedMissingnessReport:
    """Topology- and selection-bound source claims with no inferred completion."""

    policy_id: str
    source_format: str
    source_sha256: str
    canonical_topology_schema_id: str
    canonical_topology_sha256: str
    coordinate_scope: str
    altloc_status: str
    requested_altloc_id: str
    assembly_status: str
    requested_assembly_id: str
    missing_residue_claims: tuple[SourceReportedMissingResidueClaim, ...]
    missing_atom_claims: tuple[SourceReportedMissingAtomClaim, ...]
    source_reported_missing_residue_count: int
    source_reported_missing_atom_count: int
    blockers: tuple[str, ...]
    completion_attempted: bool = False
    completion_applied: bool = False
    preparation_ready: bool = False
    claim_safe: bool = False

    def __post_init__(self) -> None:
        if self.policy_id != MISSINGNESS_PRESERVATION_POLICY_ID:
            raise ValueError("missingness report v1 requires the fixed policy")
        if self.source_format not in {"pdb", "mmcif"}:
            raise ValueError("source_format must be 'pdb' or 'mmcif'")
        _validate_sha256(self.source_sha256, field_name="source_sha256")
        if self.canonical_topology_schema_id != CANONICAL_TOPOLOGY_SCHEMA_ID:
            raise ValueError(
                "missingness report v1 requires the fixed canonical topology schema"
            )
        _validate_sha256(
            self.canonical_topology_sha256,
            field_name="canonical_topology_sha256",
        )
        self._validate_selection_binding()
        _validate_ordered_claims(
            self.missing_residue_claims,
            field_name="missing_residue_claims",
            claim_type=SourceReportedMissingResidueClaim,
            limit=MAX_MISSING_RESIDUE_CLAIMS,
        )
        _validate_ordered_claims(
            self.missing_atom_claims,
            field_name="missing_atom_claims",
            claim_type=SourceReportedMissingAtomClaim,
            limit=MAX_MISSING_ATOM_CLAIMS,
        )
        total_claims = len(self.missing_residue_claims) + len(
            self.missing_atom_claims
        )
        if total_claims > MAX_TOTAL_MISSINGNESS_CLAIMS:
            raise ValueError(
                "combined missingness claims exceed the "
                f"{MAX_TOTAL_MISSINGNESS_CLAIMS}-claim limit"
            )
        _strict_nonnegative_int(
            self.source_reported_missing_residue_count,
            field_name="source_reported_missing_residue_count",
        )
        _strict_nonnegative_int(
            self.source_reported_missing_atom_count,
            field_name="source_reported_missing_atom_count",
        )
        if self.source_reported_missing_residue_count != len(
            self.missing_residue_claims
        ):
            raise ValueError(
                "source_reported_missing_residue_count must equal residue claim count"
            )
        if self.source_reported_missing_atom_count != len(
            self.missing_atom_claims
        ):
            raise ValueError(
                "source_reported_missing_atom_count must equal atom claim count"
            )
        if type(self.blockers) is not tuple or not all(
            type(blocker) is str and blocker for blocker in self.blockers
        ):
            raise TypeError("blockers must be a tuple of nonempty strings")
        expected_blockers = _expected_blockers(
            self.source_reported_missing_residue_count,
            self.source_reported_missing_atom_count,
        )
        if self.blockers != expected_blockers:
            raise ValueError(
                "blockers must exactly match the ordered preserve-only blocker set"
            )
        for name in (
            "completion_attempted",
            "completion_applied",
            "preparation_ready",
            "claim_safe",
        ):
            value = getattr(self, name)
            if type(value) is not bool:
                raise TypeError(f"{name} must be a boolean")
            if value:
                raise ValueError(f"{name} must remain false in preserve-only report v1")
        if self._canonical_size_bytes() > MAX_REPORT_CANONICAL_BYTES:
            raise ValueError(
                "missingness report exceeds the "
                f"{MAX_REPORT_CANONICAL_BYTES}-byte canonical limit"
            )

    def _validate_selection_binding(self) -> None:
        for name, value in (
            ("coordinate_scope", self.coordinate_scope),
            ("altloc_status", self.altloc_status),
            ("requested_altloc_id", self.requested_altloc_id),
            ("assembly_status", self.assembly_status),
            ("requested_assembly_id", self.requested_assembly_id),
        ):
            _strict_string(
                value,
                field_name=name,
                allow_empty=name.startswith("requested_"),
                max_chars=_MAX_BINDING_ID_CHARS,
            )
        if self.altloc_status == "not_present":
            if self.requested_altloc_id:
                raise ValueError(
                    "requested_altloc_id must be empty when altloc_status is not_present"
                )
        elif self.altloc_status == "explicit_id_selected":
            if not self.requested_altloc_id:
                raise ValueError(
                    "requested_altloc_id is required for explicit altloc selection"
                )
        else:
            raise ValueError("unsupported altloc_status for missingness report v1")

        if self.source_format == "pdb":
            expected = ("deposited_coordinates", "not_supported_for_pdb", "")
            actual = (
                self.coordinate_scope,
                self.assembly_status,
                self.requested_assembly_id,
            )
            if actual != expected:
                raise ValueError(
                    "PDB missingness reports require deposited coordinate scope and "
                    "the not_supported_for_pdb assembly binding"
                )
            return

        if self.coordinate_scope == "deposited_asymmetric_unit":
            if self.assembly_status not in {"not_present", "present_not_requested"}:
                raise ValueError(
                    "deposited mmCIF scope requires an unapplied assembly status"
                )
            if self.requested_assembly_id:
                raise ValueError(
                    "requested_assembly_id must be empty for deposited mmCIF scope"
                )
        elif self.coordinate_scope == "explicit_biological_assembly":
            if self.assembly_status != "explicit_id_applied":
                raise ValueError(
                    "explicit assembly scope requires explicit_id_applied status"
                )
            if not self.requested_assembly_id:
                raise ValueError(
                    "requested_assembly_id is required for explicit assembly scope"
                )
        else:
            raise ValueError("unsupported coordinate_scope for mmCIF missingness report v1")

    def _core_dict(self, *, include_claims: bool = True) -> dict[str, Any]:
        return {
            "schema_id": MISSINGNESS_REPORT_SCHEMA_ID,
            "policy_id": self.policy_id,
            "source_format": self.source_format,
            "source_sha256": self.source_sha256,
            "canonical_topology_schema_id": self.canonical_topology_schema_id,
            "canonical_topology_sha256": self.canonical_topology_sha256,
            "coordinate_scope": self.coordinate_scope,
            "altloc_status": self.altloc_status,
            "requested_altloc_id": self.requested_altloc_id,
            "assembly_status": self.assembly_status,
            "requested_assembly_id": self.requested_assembly_id,
            "missing_residue_claims": [
                claim.to_dict() for claim in self.missing_residue_claims
            ] if include_claims else [],
            "missing_atom_claims": [
                claim.to_dict() for claim in self.missing_atom_claims
            ] if include_claims else [],
            "source_reported_missing_residue_count": (
                self.source_reported_missing_residue_count
            ),
            "source_reported_missing_atom_count": (
                self.source_reported_missing_atom_count
            ),
            "blockers": list(self.blockers),
            "completion_attempted": self.completion_attempted,
            "completion_applied": self.completion_applied,
            "preparation_ready": self.preparation_ready,
            "claim_safe": self.claim_safe,
        }

    def _canonical_size_bytes(self) -> int:
        """Measure bounded output without first assembling an oversized blob."""

        skeleton = self._core_dict(include_claims=False)
        size = len(_canonical_json_bytes(skeleton))
        for claims in (self.missing_residue_claims, self.missing_atom_claims):
            for index, claim in enumerate(claims):
                size += len(_canonical_json_bytes(claim.to_dict()))
                if index:
                    size += 1  # canonical JSON list comma
                if size > MAX_REPORT_CANONICAL_BYTES:
                    return size
        return size

    @property
    def canonical_bytes(self) -> bytes:
        """Canonical UTF-8 JSON bytes, excluding the self-referential digest."""

        return _canonical_json_bytes(self._core_dict())

    @property
    def report_sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        payload = self._core_dict()
        payload["report_sha256"] = self.report_sha256
        return payload


def build_source_reported_missingness_report(
    *,
    source_format: str,
    source_sha256: str,
    canonical_topology_sha256: str,
    coordinate_scope: str,
    altloc_status: str,
    requested_altloc_id: str,
    assembly_status: str,
    requested_assembly_id: str,
    missing_residue_claims: tuple[SourceReportedMissingResidueClaim, ...] = (),
    missing_atom_claims: tuple[SourceReportedMissingAtomClaim, ...] = (),
) -> SourceReportedMissingnessReport:
    """Bind already-extracted source claims without deriving any new claim."""

    if type(missing_residue_claims) is not tuple:
        raise TypeError("missing_residue_claims must be a tuple")
    if type(missing_atom_claims) is not tuple:
        raise TypeError("missing_atom_claims must be a tuple")
    residue_count = len(missing_residue_claims)
    atom_count = len(missing_atom_claims)
    return SourceReportedMissingnessReport(
        policy_id=MISSINGNESS_PRESERVATION_POLICY_ID,
        source_format=source_format,
        source_sha256=source_sha256,
        canonical_topology_schema_id=CANONICAL_TOPOLOGY_SCHEMA_ID,
        canonical_topology_sha256=canonical_topology_sha256,
        coordinate_scope=coordinate_scope,
        altloc_status=altloc_status,
        requested_altloc_id=requested_altloc_id,
        assembly_status=assembly_status,
        requested_assembly_id=requested_assembly_id,
        missing_residue_claims=missing_residue_claims,
        missing_atom_claims=missing_atom_claims,
        source_reported_missing_residue_count=residue_count,
        source_reported_missing_atom_count=atom_count,
        blockers=_expected_blockers(residue_count, atom_count),
    )


__all__ = [
    "MAX_MISSING_ATOM_CLAIMS",
    "MAX_MISSING_RESIDUE_CLAIMS",
    "MAX_RAW_PAYLOAD_BYTES",
    "MAX_RAW_PAYLOAD_DEPTH",
    "MAX_RAW_PAYLOAD_NODES",
    "MAX_REPORT_CANONICAL_BYTES",
    "MAX_TOTAL_MISSINGNESS_CLAIMS",
    "MISSINGNESS_PRESERVATION_POLICY_ID",
    "MISSINGNESS_REPORT_SCHEMA_ID",
    "MISSINGNESS_REPORT_SCHEMA_VERSION",
    "SourceReportedMissingAtomClaim",
    "SourceReportedMissingResidueClaim",
    "SourceReportedMissingnessReport",
    "build_source_reported_missingness_report",
]
