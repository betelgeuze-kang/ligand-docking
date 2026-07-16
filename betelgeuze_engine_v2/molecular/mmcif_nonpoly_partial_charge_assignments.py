"""Apply explicit, provenance-bound partial-charge vectors to bounded systems.

This module validates and applies caller-supplied charge values.  It does not
generate, calibrate, or scientifically validate charges.  Every vector is bound
to one exact parameter-source-bound system hash, atom order, and method
provenance digest before values are written to ``Atom.partial_charge_e``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import tempfile
from typing import Any, Mapping, Sequence

from .mmcif_nonpoly_parameter_source_binding import (
    MMCIF_NONPOLY_PARAMETER_SOURCE_BINDER_VERSION,
    MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROFILE_ID,
    MmcifNonpolyParameterSourceBindingSnapshot,
    mmcif_nonpoly_parameter_source_binding_document,
    require_mmcif_nonpoly_parameter_source_binding_document,
)
from .models import AllAtomSystem
from .serialization import (
    all_atom_system_from_canonical_json,
    canonical_system_json_bytes,
    canonical_system_sha256,
)
from .validation import require_valid_all_atom_system


MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_partial_charge_assignment_projection/1.0.0"
)
MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_partial_charge_assignment_document/1.0.0"
)
MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROFILE_ID = (
    "bounded_explicit_binary64_partial_charge_vector_application/1.0.0"
)
MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNER_VERSION = "1.0.0"
MMCIF_NONPOLY_PARTIAL_CHARGE_TOTAL_TOLERANCE_E = 1.0e-12

MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_LIMITATIONS = (
    "explicit_charge_values_required_from_caller",
    "charge_generation_not_implemented",
    "charge_method_not_scientifically_validated",
    "charge_values_not_calibrated",
    "parameter_coverage_and_applicability_not_validated",
    "force_field_parameter_assignment_not_implemented",
    "atom_masses_not_assigned",
    "fixed_parent_offset_geometry_not_validated",
    "force_energy_and_scientific_validation_missing",
)

_ASSIGNED_STATUS = "explicit_partial_charge_vector_assigned"
_MISSING_STATUS = "not_assigned_explicit_charge_record_missing"
_UNAVAILABLE_STATUS = "not_assigned_parameter_bound_system_unavailable"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyPartialChargeAssignmentError(ValueError):
    """Stable fail-closed charge-assignment error without value disclosure."""

    def __init__(self, code: str, detail: str):
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(f"mmcif_nonpoly_partial_charge_assignment:{self.code}: {self.detail}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _binary64_bits_hex(value: float) -> str:
    return struct.pack(">d", float(value)).hex()


def _canonical_system_document(system: AllAtomSystem) -> dict[str, Any]:
    return json.loads(canonical_system_json_bytes(system).decode("ascii"))


def _system_from_document(payload: Mapping[str, object]) -> AllAtomSystem:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return all_atom_system_from_canonical_json(encoded)


def _claim_policy() -> dict[str, bool]:
    return {
        "explicit_partial_charge_records_bound": True,
        "partial_charge_values_assigned": True,
        "finite_binary64_charge_values_bound": True,
        "charge_vector_atom_order_bound": True,
        "formal_total_charge_conservation_checked": True,
        "method_provenance_digest_bound": True,
        "parameter_source_binding_preserved": True,
        "failure_complete_instance_reports": True,
        "charge_generation_implemented": False,
        "charge_method_scientifically_validated": False,
        "charge_values_calibrated": False,
        "parameter_coverage_validated": False,
        "applicability_domain_validated": False,
        "force_field_parameter_assignment_implemented": False,
        "atom_masses_assigned": False,
        "parameterable": False,
        "coordinate_geometry_validated": False,
        "force_or_energy_validated": False,
        "chemistry_validated": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyPartialChargeAssignmentInput:
    """One explicit charge vector and its non-scientific method identity."""

    instance_identity_sha256: str
    source_system_sha256: str
    method_id: str
    method_version: str
    method_provenance_sha256: str
    charges_e: tuple[float, ...]
    expected_total_charge_e: float

    def __post_init__(self) -> None:
        for name, value in (
            ("instance_identity_sha256", self.instance_identity_sha256),
            ("source_system_sha256", self.source_system_sha256),
            ("method_provenance_sha256", self.method_provenance_sha256),
        ):
            if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
                raise MmcifNonpolyPartialChargeAssignmentError(
                    "invalid_digest", f"{name} must be a lowercase SHA-256 digest"
                )
        if (
            not isinstance(self.method_id, str)
            or not self.method_id.strip()
            or not isinstance(self.method_version, str)
            or not self.method_version.strip()
        ):
            raise MmcifNonpolyPartialChargeAssignmentError(
                "invalid_method_identity", "method ID and version must be non-empty"
            )
        values = tuple(self.charges_e)
        if not values:
            raise MmcifNonpolyPartialChargeAssignmentError(
                "empty_charge_vector", "charge vector must not be empty"
            )
        charges: list[float] = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise MmcifNonpolyPartialChargeAssignmentError(
                    "invalid_charge_value", "charge values must be finite real numbers"
                )
            charge = float(value)
            if not math.isfinite(charge):
                raise MmcifNonpolyPartialChargeAssignmentError(
                    "nonfinite_charge_value", "charge values must be finite"
                )
            charges.append(charge)
        if (
            isinstance(self.expected_total_charge_e, bool)
            or not isinstance(self.expected_total_charge_e, (int, float))
            or not math.isfinite(float(self.expected_total_charge_e))
        ):
            raise MmcifNonpolyPartialChargeAssignmentError(
                "invalid_expected_total", "expected total charge must be finite"
            )
        object.__setattr__(self, "method_id", self.method_id.strip())
        object.__setattr__(self, "method_version", self.method_version.strip())
        object.__setattr__(self, "charges_e", tuple(charges))
        object.__setattr__(
            self, "expected_total_charge_e", float(self.expected_total_charge_e)
        )

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyPartialChargeAssignmentInput("
            f"method_id={self.method_id!r}, atom_count={len(self.charges_e)})"
        )

    @property
    def charge_binary64_bits_hex(self) -> tuple[str, ...]:
        return tuple(_binary64_bits_hex(value) for value in self.charges_e)

    @property
    def observed_total_charge_e(self) -> float:
        return math.fsum(self.charges_e)

    @property
    def assignment_input_sha256(self) -> str:
        return _sha256(self.identity_dict())

    def identity_dict(self) -> dict[str, Any]:
        return {
            "profile_id": MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROFILE_ID,
            "assigner_version": MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNER_VERSION,
            "instance_identity_sha256": self.instance_identity_sha256,
            "source_system_sha256": self.source_system_sha256,
            "method_id": self.method_id,
            "method_version": self.method_version,
            "method_provenance_sha256": self.method_provenance_sha256,
            "method_claim_status": "unvalidated_explicit_values_only",
            "charge_unit": "elementary_charge",
            "charge_binary64_bits_hex": list(self.charge_binary64_bits_hex),
            "expected_total_charge_e_binary64_bits_hex": _binary64_bits_hex(
                self.expected_total_charge_e
            ),
            "total_charge_tolerance_e_binary64_bits_hex": _binary64_bits_hex(
                MMCIF_NONPOLY_PARTIAL_CHARGE_TOTAL_TOLERANCE_E
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_dict(),
            "charges_e": list(self.charges_e),
            "expected_total_charge_e": self.expected_total_charge_e,
            "observed_total_charge_e": self.observed_total_charge_e,
            "assignment_input_sha256": self.assignment_input_sha256,
            "charge_generation_implemented": False,
            "charge_method_scientifically_validated": False,
            "charge_values_calibrated": False,
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, object]
    ) -> "MmcifNonpolyPartialChargeAssignmentInput":
        charges = payload.get("charges_e")
        if not isinstance(charges, list):
            raise ValueError("partial charge assignment input vector missing")
        record = cls(
            instance_identity_sha256=str(payload.get("instance_identity_sha256") or ""),
            source_system_sha256=str(payload.get("source_system_sha256") or ""),
            method_id=str(payload.get("method_id") or ""),
            method_version=str(payload.get("method_version") or ""),
            method_provenance_sha256=str(
                payload.get("method_provenance_sha256") or ""
            ),
            charges_e=tuple(charges),
            expected_total_charge_e=payload.get("expected_total_charge_e"),
        )
        if dict(payload) != record.to_dict():
            raise ValueError("partial charge assignment input identity mismatch")
        return record


def _apply_assignment(
    system: AllAtomSystem,
    record: MmcifNonpolyPartialChargeAssignmentInput,
) -> AllAtomSystem:
    source_system_sha256 = canonical_system_sha256(system)
    if record.source_system_sha256 != source_system_sha256:
        raise MmcifNonpolyPartialChargeAssignmentError(
            "source_system_crosswire", "charge vector targets a different system hash"
        )
    instance = str(system.metadata.get("instance_identity_sha256") or "")
    if record.instance_identity_sha256 != instance:
        raise MmcifNonpolyPartialChargeAssignmentError(
            "instance_crosswire", "charge vector targets a different source instance"
        )
    if len(record.charges_e) != system.atom_count:
        raise MmcifNonpolyPartialChargeAssignmentError(
            "charge_vector_length_mismatch",
            "charge vector must cover every atom in canonical order",
        )
    formal_total = float(sum(atom.formal_charge for atom in system.atoms))
    if not math.isclose(
        record.expected_total_charge_e,
        formal_total,
        rel_tol=0.0,
        abs_tol=MMCIF_NONPOLY_PARTIAL_CHARGE_TOTAL_TOLERANCE_E,
    ):
        raise MmcifNonpolyPartialChargeAssignmentError(
            "expected_total_formal_charge_mismatch",
            "expected charge total must match the canonical formal-charge total",
        )
    if not math.isclose(
        record.observed_total_charge_e,
        record.expected_total_charge_e,
        rel_tol=0.0,
        abs_tol=MMCIF_NONPOLY_PARTIAL_CHARGE_TOTAL_TOLERANCE_E,
    ):
        raise MmcifNonpolyPartialChargeAssignmentError(
            "partial_charge_total_mismatch",
            "partial charge vector does not conserve the expected total charge",
        )

    assignment_sha256 = record.assignment_input_sha256
    atoms = tuple(
        replace(
            atom,
            partial_charge_e=charge,
            metadata={
                **dict(atom.metadata),
                "partial_charge_assignment_status": _ASSIGNED_STATUS,
                "partial_charge_binary64_bits_hex": _binary64_bits_hex(charge),
                "partial_charge_assignment_input_sha256": assignment_sha256,
                "partial_charge_method_id": record.method_id,
                "partial_charge_method_version": record.method_version,
                "partial_charge_method_provenance_sha256": (
                    record.method_provenance_sha256
                ),
                "partial_charge_scientifically_validated": False,
            },
        )
        for atom, charge in zip(system.atoms, record.charges_e, strict=True)
    )
    metadata = dict(system.metadata)
    metadata.update(
        {
            "partial_charge_assignment_status": _ASSIGNED_STATUS,
            "partial_charge_assignment_input_sha256": assignment_sha256,
            "partial_charge_method_id": record.method_id,
            "partial_charge_method_version": record.method_version,
            "partial_charge_method_provenance_sha256": (
                record.method_provenance_sha256
            ),
            "partial_charge_total_e": record.observed_total_charge_e,
            "partial_charge_scientifically_validated": False,
            "partial_charge_values_calibrated": False,
            "parameterable": False,
        }
    )
    provenance_metadata = dict(system.provenance.metadata)
    provenance_metadata.update(
        {
            "partial_charge_assigned": True,
            "partial_charge_assignment_input_sha256": assignment_sha256,
            "partial_charge_method_provenance_sha256": (
                record.method_provenance_sha256
            ),
            "partial_charge_scientifically_validated": False,
            "partial_charge_values_calibrated": False,
            "parameter_assignment_implemented": False,
            "atom_masses_assigned": False,
            "claim_safe": False,
        }
    )
    assigned = replace(
        system,
        atoms=atoms,
        metadata=metadata,
        provenance=replace(system.provenance, metadata=provenance_metadata),
    )
    validation = require_valid_all_atom_system(assigned)
    if validation.claim_stage.name.lower() != "contract_valid" or validation.claim_safe:
        raise MmcifNonpolyPartialChargeAssignmentError(
            "unexpected_claim_promotion",
            "charge assignment must preserve contract-valid claim-blocked state",
        )
    return assigned


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyPartialChargeAssignmentInstanceReport:
    instance_identity_sha256: str
    component_id: str
    assignment_status: str
    assignment_blockers: tuple[str, ...]
    limitations: tuple[str, ...]
    source_system_sha256: str
    assignment_input: MmcifNonpolyPartialChargeAssignmentInput | None
    assigned_system: AllAtomSystem | None

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyPartialChargeAssignmentInstanceReport("
            f"component_id={self.component_id!r}, assignment_status={self.assignment_status!r})"
        )

    @property
    def charge_assigned(self) -> bool:
        return self.assigned_system is not None

    @property
    def assignment_input_sha256(self) -> str:
        return (
            "" if self.assignment_input is None else self.assignment_input.assignment_input_sha256
        )

    @property
    def assigned_system_sha256(self) -> str:
        return (
            "" if self.assigned_system is None else canonical_system_sha256(self.assigned_system)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_identity_sha256": self.instance_identity_sha256,
            "component_id": self.component_id,
            "assignment_status": self.assignment_status,
            "assignment_blockers": list(self.assignment_blockers),
            "limitations": list(self.limitations),
            "source_system_sha256": self.source_system_sha256,
            "charge_assigned": self.charge_assigned,
            "assignment_input_sha256": self.assignment_input_sha256,
            "assigned_system_sha256": self.assigned_system_sha256,
            "assignment_input": (
                None if self.assignment_input is None else self.assignment_input.to_dict()
            ),
            "canonical_assigned_system_document": (
                None
                if self.assigned_system is None
                else _canonical_system_document(self.assigned_system)
            ),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyPartialChargeAssignmentSnapshot:
    parameter_source_binding_snapshot: MmcifNonpolyParameterSourceBindingSnapshot
    instance_reports: tuple[MmcifNonpolyPartialChargeAssignmentInstanceReport, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyPartialChargeAssignmentSnapshot("
            f"instance_count={len(self.instance_reports)}, "
            f"assigned_system_count={self.assigned_system_count})"
        )

    @property
    def assigned_system_count(self) -> int:
        return sum(report.charge_assigned for report in self.instance_reports)

    @property
    def unassigned_system_count(self) -> int:
        return len(self.instance_reports) - self.assigned_system_count

    @property
    def assignment_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_partial_charge_assignment_projection(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_DOCUMENT_SCHEMA_ID,
                "parameter_source_binding_snapshot_sha256": (
                    self.parameter_source_binding_snapshot.snapshot_sha256
                ),
                "assignment_projection_sha256": self.assignment_projection_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_sha256": (
                self.parameter_source_binding_snapshot.all_atom_snapshot.source_sha256
            ),
            "parameter_source_binding_snapshot_sha256": (
                self.parameter_source_binding_snapshot.snapshot_sha256
            ),
            "instance_count": len(self.instance_reports),
            "assigned_system_count": self.assigned_system_count,
            "unassigned_system_count": self.unassigned_system_count,
            "assignment_projection_sha256": self.assignment_projection_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def apply_explicit_mmcif_nonpoly_partial_charge_assignments(
    parameter_source_binding_snapshot: MmcifNonpolyParameterSourceBindingSnapshot,
    assignments: Sequence[MmcifNonpolyPartialChargeAssignmentInput],
) -> MmcifNonpolyPartialChargeAssignmentSnapshot:
    """Apply exact explicit vectors; missing records remain visible failures."""

    require_mmcif_nonpoly_parameter_source_binding_document(
        mmcif_nonpoly_parameter_source_binding_document(
            parameter_source_binding_snapshot
        )
    )
    records = tuple(assignments)
    if not all(
        isinstance(record, MmcifNonpolyPartialChargeAssignmentInput)
        for record in records
    ):
        raise MmcifNonpolyPartialChargeAssignmentError(
            "invalid_assignment_record", "assignments must contain typed records"
        )
    by_instance = {record.instance_identity_sha256: record for record in records}
    if len(by_instance) != len(records):
        raise MmcifNonpolyPartialChargeAssignmentError(
            "duplicate_assignment_record", "each instance may have at most one charge vector"
        )
    parent_instances = {
        report.instance_identity_sha256
        for report in parameter_source_binding_snapshot.instance_reports
    }
    unknown = set(by_instance) - parent_instances
    if unknown:
        raise MmcifNonpolyPartialChargeAssignmentError(
            "unknown_assignment_instance", "charge vector targets an unknown instance"
        )

    reports: list[MmcifNonpolyPartialChargeAssignmentInstanceReport] = []
    for parent in parameter_source_binding_snapshot.instance_reports:
        record = by_instance.get(parent.instance_identity_sha256)
        if parent.bound_system is None:
            if record is not None:
                raise MmcifNonpolyPartialChargeAssignmentError(
                    "assignment_for_unavailable_system",
                    "charge vector cannot target an unavailable parameter-bound system",
                )
            reports.append(
                MmcifNonpolyPartialChargeAssignmentInstanceReport(
                    instance_identity_sha256=parent.instance_identity_sha256,
                    component_id=parent.component_id,
                    assignment_status=_UNAVAILABLE_STATUS,
                    assignment_blockers=parent.binding_blockers,
                    limitations=(),
                    source_system_sha256="",
                    assignment_input=None,
                    assigned_system=None,
                )
            )
            continue
        source_system_sha256 = canonical_system_sha256(parent.bound_system)
        if record is None:
            reports.append(
                MmcifNonpolyPartialChargeAssignmentInstanceReport(
                    instance_identity_sha256=parent.instance_identity_sha256,
                    component_id=parent.component_id,
                    assignment_status=_MISSING_STATUS,
                    assignment_blockers=("explicit_partial_charge_record_missing",),
                    limitations=(),
                    source_system_sha256=source_system_sha256,
                    assignment_input=None,
                    assigned_system=None,
                )
            )
            continue
        assigned = _apply_assignment(parent.bound_system, record)
        reports.append(
            MmcifNonpolyPartialChargeAssignmentInstanceReport(
                instance_identity_sha256=parent.instance_identity_sha256,
                component_id=parent.component_id,
                assignment_status=_ASSIGNED_STATUS,
                assignment_blockers=(),
                limitations=MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_LIMITATIONS,
                source_system_sha256=source_system_sha256,
                assignment_input=record,
                assigned_system=assigned,
            )
        )
    return MmcifNonpolyPartialChargeAssignmentSnapshot(
        parameter_source_binding_snapshot=parameter_source_binding_snapshot,
        instance_reports=tuple(reports),
    )


def mmcif_nonpoly_partial_charge_assignment_projection(
    snapshot: MmcifNonpolyPartialChargeAssignmentSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROFILE_ID,
        "assigner_version": MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNER_VERSION,
        "instance_order": "bounded_nonpoly_identity_source_order",
        "instance_reports": [report.to_dict() for report in snapshot.instance_reports],
        **_claim_policy(),
    }


def mmcif_nonpoly_partial_charge_assignment_document(
    snapshot: MmcifNonpolyPartialChargeAssignmentSnapshot,
) -> dict[str, Any]:
    parent = mmcif_nonpoly_parameter_source_binding_document(
        snapshot.parameter_source_binding_snapshot
    )
    projection = mmcif_nonpoly_partial_charge_assignment_projection(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROFILE_ID,
        "assigner_version": MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNER_VERSION,
        "parameter_source_binding_document": parent,
        "parameter_source_binding_document_sha256": _sha256(parent),
        "assignment_projection": projection,
        "assignment_projection_sha256": _sha256(projection),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str, *, allow_empty: bool = False) -> str:
    candidate = str(value or "")
    if allow_empty and not candidate:
        return ""
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"partial charge assignment {label} digest invalid")
    return candidate


def require_mmcif_nonpoly_partial_charge_assignment_document(
    payload: object,
) -> Mapping[str, object]:
    """Verify parent binding, charge vectors, assigned systems, and non-claims."""

    if not isinstance(payload, Mapping):
        raise ValueError("partial charge assignment document must be a mapping")
    document = dict(payload)
    if (
        document.get("schema_id")
        != MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_DOCUMENT_SCHEMA_ID
        or document.get("profile_id")
        != MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROFILE_ID
        or document.get("assigner_version")
        != MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNER_VERSION
    ):
        raise ValueError("partial charge assignment document envelope mismatch")
    parent = document.get("parameter_source_binding_document")
    projection = document.get("assignment_projection")
    if not isinstance(parent, Mapping) or not isinstance(projection, Mapping):
        raise ValueError("partial charge assignment evidence missing")
    require_mmcif_nonpoly_parameter_source_binding_document(parent)
    parent_dict = dict(parent)
    projection_dict = dict(projection)
    if (
        document.get("parameter_source_binding_document_sha256")
        != _sha256(parent_dict)
        or document.get("assignment_projection_sha256") != _sha256(projection_dict)
        or projection_dict.get("schema_id")
        != MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROJECTION_SCHEMA_ID
        or projection_dict.get("profile_id")
        != MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROFILE_ID
        or projection_dict.get("assigner_version")
        != MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNER_VERSION
        or projection_dict.get("instance_order")
        != "bounded_nonpoly_identity_source_order"
        or parent_dict.get("profile_id")
        != MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROFILE_ID
        or parent_dict.get("binder_version")
        != MMCIF_NONPOLY_PARAMETER_SOURCE_BINDER_VERSION
    ):
        raise ValueError("partial charge assignment evidence identity mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection_dict.get(key) is not expected:
            raise ValueError("partial charge assignment claim boundary mismatch")

    parent_projection = parent_dict.get("binding_projection")
    if not isinstance(parent_projection, Mapping):
        raise ValueError("partial charge assignment parent projection missing")
    parent_reports_raw = parent_projection.get("instance_reports")
    reports_raw = projection_dict.get("instance_reports")
    if not isinstance(parent_reports_raw, list) or not isinstance(reports_raw, list):
        raise ValueError("partial charge assignment reports missing")
    parent_reports = {
        str(row["instance_identity_sha256"]): dict(row)
        for row in parent_reports_raw
        if isinstance(row, Mapping)
    }
    if len(parent_reports) != len(parent_reports_raw):
        raise ValueError("partial charge assignment parent instances invalid")

    assigned_count = 0
    seen: set[str] = set()
    for raw in reports_raw:
        if not isinstance(raw, Mapping):
            raise ValueError("partial charge assignment instance report invalid")
        report = dict(raw)
        instance = _require_digest(report.get("instance_identity_sha256"), "instance")
        if instance in seen or instance not in parent_reports:
            raise ValueError("partial charge assignment instance crosswire")
        seen.add(instance)
        parent_report = parent_reports[instance]
        blockers = report.get("assignment_blockers")
        limitations = report.get("limitations")
        if not isinstance(blockers, list) or not isinstance(limitations, list):
            raise ValueError("partial charge assignment report lists invalid")
        input_payload = report.get("assignment_input")
        assigned_payload = report.get("canonical_assigned_system_document")
        parent_payload = parent_report.get("canonical_bound_system_document")

        if parent_report.get("source_bound") is True:
            if not isinstance(parent_payload, Mapping):
                raise ValueError("partial charge assignment parent system missing")
            parent_system = _system_from_document(parent_payload)
            source_system_sha256 = canonical_system_sha256(parent_system)
            if report.get("source_system_sha256") != source_system_sha256:
                raise ValueError("partial charge assignment source system mismatch")
            if report.get("assignment_status") == _ASSIGNED_STATUS:
                assigned_count += 1
                if blockers or limitations != list(
                    MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_LIMITATIONS
                ):
                    raise ValueError("partial charge assignment success boundary invalid")
                if not isinstance(input_payload, Mapping) or not isinstance(
                    assigned_payload, Mapping
                ):
                    raise ValueError("partial charge assignment payload missing")
                record = MmcifNonpolyPartialChargeAssignmentInput.from_dict(input_payload)
                expected_system = _apply_assignment(parent_system, record)
                expected_document = _canonical_system_document(expected_system)
                if (
                    dict(assigned_payload) != expected_document
                    or report.get("charge_assigned") is not True
                    or report.get("assignment_input_sha256")
                    != record.assignment_input_sha256
                    or report.get("assigned_system_sha256")
                    != canonical_system_sha256(expected_system)
                    or any(atom.partial_charge_e is None for atom in expected_system.atoms)
                    or any(atom.mass_da is not None for atom in expected_system.atoms)
                    or expected_system.provenance.metadata.get("partial_charge_assigned")
                    is not True
                    or expected_system.provenance.chemistry_validated
                    or expected_system.provenance.scientifically_validated
                    or expected_system.provenance.product_qualified
                ):
                    raise ValueError("partial charge assigned system identity mismatch")
            elif report.get("assignment_status") == _MISSING_STATUS:
                if (
                    blockers != ["explicit_partial_charge_record_missing"]
                    or limitations
                    or input_payload is not None
                    or assigned_payload is not None
                    or report.get("charge_assigned") is not False
                    or report.get("assignment_input_sha256") != ""
                    or report.get("assigned_system_sha256") != ""
                ):
                    raise ValueError("missing partial charge assignment report invalid")
            else:
                raise ValueError("partial charge assignment status invalid")
        else:
            if (
                report.get("assignment_status") != _UNAVAILABLE_STATUS
                or not blockers
                or limitations
                or input_payload is not None
                or assigned_payload is not None
                or report.get("charge_assigned") is not False
                or any(
                    report.get(key) != ""
                    for key in (
                        "source_system_sha256",
                        "assignment_input_sha256",
                        "assigned_system_sha256",
                    )
                )
            ):
                raise ValueError("unavailable partial charge assignment report invalid")
    if seen != set(parent_reports):
        raise ValueError("partial charge assignment report coverage incomplete")
    parent_snapshot_sha256 = _require_digest(
        parent_dict.get("snapshot_sha256"), "parent binding snapshot"
    )
    if (
        document.get("source_sha256") != parent_dict.get("source_sha256")
        or document.get("parameter_source_binding_snapshot_sha256")
        != parent_snapshot_sha256
        or document.get("instance_count") != len(reports_raw)
        or document.get("assigned_system_count") != assigned_count
        or document.get("unassigned_system_count") != len(reports_raw) - assigned_count
    ):
        raise ValueError("partial charge assignment summary mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_DOCUMENT_SCHEMA_ID,
            "parameter_source_binding_snapshot_sha256": parent_snapshot_sha256,
            "assignment_projection_sha256": _sha256(projection_dict),
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("partial charge assignment snapshot digest mismatch")
    return payload


def mmcif_nonpoly_partial_charge_assignment_json_bytes(
    snapshot: MmcifNonpolyPartialChargeAssignmentSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_partial_charge_assignment_document(snapshot))


def write_mmcif_nonpoly_partial_charge_assignment_json(
    path: str | Path,
    snapshot: MmcifNonpolyPartialChargeAssignmentSnapshot,
) -> Path:
    """Atomically write a private canonical charge-assignment document."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(mmcif_nonpoly_partial_charge_assignment_json_bytes(snapshot))
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        directory_fd = os.open(
            destination.parent,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise
    return destination


__all__ = [
    "MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNER_VERSION",
    "MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_LIMITATIONS",
    "MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROFILE_ID",
    "MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_PARTIAL_CHARGE_TOTAL_TOLERANCE_E",
    "MmcifNonpolyPartialChargeAssignmentError",
    "MmcifNonpolyPartialChargeAssignmentInput",
    "MmcifNonpolyPartialChargeAssignmentInstanceReport",
    "MmcifNonpolyPartialChargeAssignmentSnapshot",
    "apply_explicit_mmcif_nonpoly_partial_charge_assignments",
    "mmcif_nonpoly_partial_charge_assignment_document",
    "mmcif_nonpoly_partial_charge_assignment_json_bytes",
    "mmcif_nonpoly_partial_charge_assignment_projection",
    "require_mmcif_nonpoly_partial_charge_assignment_document",
    "write_mmcif_nonpoly_partial_charge_assignment_json",
]
