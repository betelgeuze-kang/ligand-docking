"""Per-atom parameter-source provenance trace for bound canonical systems.

The source-binding snapshot proves *which reviewed OFFXML release* was bound to
each in-scope canonical system, but it records that binding only at system
granularity.  Nothing stated, atom by atom, which parameter values are actually
present and which are still absent, so a reader could not tell an unparameterized
system from a partially parameterized one.

This module walks every bound system and emits one row per atom: element,
atomic number, formal charge, aromatic and stereo flags, and the exact presence
state of the three per-atom parameter values the reference physics needs
(partial charge, mass, isotope).  Bond rows record order, aromaticity, and
derivation source.  Each row carries the bound system digest and the reviewed
source binding digest, so an atom's provenance resolves to a named release.

The trace is deliberately an absence ledger.  The reviewed source is bound by
identity only: SMIRNOFF semantics are not parsed and no parameter is assigned,
so a complete trace reports full coverage of *declared* provenance and zero
coverage of *assigned* values.  Every result stays claim-closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from betelgeuze_engine_v2.parameter_source_provenance import (
    PARAMETER_SOURCE_ARTIFACT_SHA256,
    PARAMETER_SOURCE_ID,
    PARAMETER_SOURCE_VERSION,
)

from .mmcif_nonpoly_parameter_source_binding import (
    MmcifNonpolyParameterSourceBindingSnapshot,
    parse_mmcif_nonpoly_parameter_source_bindings,
)
from .models import AllAtomSystem
from .serialization import canonical_system_sha256


MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_ATOM_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_atom_parameter_provenance_atom/1.0.0"
)
MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_BOND_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_atom_parameter_provenance_bond/1.0.0"
)
MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_INSTANCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_atom_parameter_provenance_instance/1.0.0"
)
MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_atom_parameter_provenance/1.0.0"
)
MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_PROFILE_ID = (
    "mmcif_nonpoly_atom_parameter_provenance/1.0.0"
)
MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_RUNNER_VERSION = "1.0.0"
MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_MAX_DOCUMENT_BYTES = 16 * 1024 * 1024

MMCIF_NONPOLY_ATOM_PARAMETER_VALUE_IDS = (
    "partial_charge_e",
    "mass_da",
    "isotope_mass_number",
)

MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_CONFIGURATION = {
    "schema_id": (
        "betelgeuze.engine_v2_mmcif_nonpoly_atom_parameter_provenance_configuration/1.0.0"
    ),
    "per_atom_value_ids": list(MMCIF_NONPOLY_ATOM_PARAMETER_VALUE_IDS),
    "declared_provenance_source": "reviewed_offxml_release_identity_binding_only",
    "assigned_value_source": "none_smirnoff_semantics_not_parsed",
    "unbound_instances_retained": True,
    "absence_recorded_per_atom": True,
    "smirnoff_semantics_parsed": False,
    "parameter_values_assigned": False,
    "partial_charges_assigned": False,
    "atom_masses_assigned": False,
}
MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_CONFIGURATION_SHA256 = hashlib.sha256(
    json.dumps(
        MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_CONFIGURATION,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
).hexdigest()

MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_BLOCKERS = (
    "declared_provenance_is_release_identity_not_assigned_parameter_values",
    "smirnoff_semantic_parsing_and_atom_typing_not_implemented",
    "partial_charge_and_atom_mass_assignment_not_implemented",
    "parameter_value_calibration_not_reviewed",
    "independent_force_and_energy_validation_missing",
    "independent_scientific_review_missing",
    "validated_refinement_claim_not_authorized",
)

_CLAIM_FLAGS = {
    "per_atom_declared_provenance_complete": True,
    "per_atom_absence_ledger_complete": True,
    "unbound_instances_retained": True,
    "smirnoff_semantics_parsed": False,
    "parameter_values_assigned": False,
    "partial_charges_assigned": False,
    "atom_masses_assigned": False,
    "independent_external_review_present": False,
    "benchmark_validated": False,
    "scientifically_validated": False,
    "claim_safe": False,
}


class MmcifNonpolyAtomParameterProvenanceError(ValueError):
    """An atom, bond, or instance provenance projection is invalid."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _binary64_hex(value: float | None) -> str | None:
    return None if value is None else float(value).hex()


def _atom_row(system: AllAtomSystem, atom: Any) -> dict[str, Any]:
    assigned = {
        value_id: getattr(atom, value_id) is not None
        for value_id in MMCIF_NONPOLY_ATOM_PARAMETER_VALUE_IDS
    }
    projection = {
        "schema_id": MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_ATOM_SCHEMA_ID,
        "atom_index": int(atom.index),
        "atom_name": str(atom.name),
        "element": str(atom.element),
        "atomic_number": int(atom.atomic_number),
        "residue_index": int(atom.residue_index),
        "formal_charge": int(atom.formal_charge),
        "aromatic": bool(atom.aromatic),
        "stereo": "" if atom.stereo is None else str(atom.stereo),
        "declared_parameter_source_id": PARAMETER_SOURCE_ID,
        "declared_parameter_source_version": PARAMETER_SOURCE_VERSION,
        "declared_parameter_source_artifact_sha256": (
            PARAMETER_SOURCE_ARTIFACT_SHA256
        ),
        "declared_provenance_present": True,
        "assigned_parameter_value_ids": [
            value_id for value_id, present in sorted(assigned.items()) if present
        ],
        "absent_parameter_value_ids": [
            value_id for value_id, present in sorted(assigned.items()) if not present
        ],
        "partial_charge_e_binary64_hex": _binary64_hex(atom.partial_charge_e),
        "mass_da_binary64_hex": _binary64_hex(atom.mass_da),
        "isotope_mass_number": atom.isotope_mass_number,
        "any_parameter_value_assigned": any(assigned.values()),
        "every_parameter_value_absent": not any(assigned.values()),
    }
    if int(atom.index) < 0 or int(atom.index) >= len(system.atoms):
        raise MmcifNonpolyAtomParameterProvenanceError(
            "atom index falls outside the canonical system"
        )
    return {**projection, "atom_provenance_sha256": _sha256(projection)}


def _bond_row(bond: Any) -> dict[str, Any]:
    projection = {
        "schema_id": MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_BOND_SCHEMA_ID,
        "bond_index": int(bond.index),
        "atom_i": int(bond.atom_i),
        "atom_j": int(bond.atom_j),
        "order": str(bond.order),
        "aromatic": bool(bond.aromatic),
        "stereo": "" if bond.stereo is None else str(bond.stereo),
        "derivation_source": str(bond.source),
        "declared_parameter_source_id": PARAMETER_SOURCE_ID,
        "bonded_parameters_assigned": False,
    }
    return {**projection, "bond_provenance_sha256": _sha256(projection)}


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyAtomParameterProvenanceInstanceReport:
    """One instance's per-atom provenance trace or its explicit absence."""

    component_id: str
    instance_identity_sha256: str
    binding_status: str
    trace_status: str
    bound_system_sha256: str
    parameter_source_binding_sha256: str
    atom_rows: tuple[dict[str, Any], ...]
    bond_rows: tuple[dict[str, Any], ...]
    trace_blockers: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyAtomParameterProvenanceInstanceReport("
            f"component_id={self.component_id!r}, "
            f"trace_status={self.trace_status!r})"
        )

    @property
    def atom_count(self) -> int:
        return len(self.atom_rows)

    def to_dict(self) -> dict[str, Any]:
        projection = {
            "schema_id": (
                MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_INSTANCE_SCHEMA_ID
            ),
            "component_id": self.component_id,
            "instance_identity_sha256": self.instance_identity_sha256,
            "binding_status": self.binding_status,
            "trace_status": self.trace_status,
            "bound_system_sha256": self.bound_system_sha256,
            "parameter_source_binding_sha256": (
                self.parameter_source_binding_sha256
            ),
            "atom_count": len(self.atom_rows),
            "bond_count": len(self.bond_rows),
            "atom_rows": [dict(row) for row in self.atom_rows],
            "bond_rows": [dict(row) for row in self.bond_rows],
            "trace_blockers": list(self.trace_blockers),
            "declared_provenance_atom_count": sum(
                1 for row in self.atom_rows if row["declared_provenance_present"]
            ),
            "assigned_value_atom_count": sum(
                1 for row in self.atom_rows if row["any_parameter_value_assigned"]
            ),
            "fully_absent_value_atom_count": sum(
                1 for row in self.atom_rows if row["every_parameter_value_absent"]
            ),
        }
        return {
            **projection,
            "instance_provenance_sha256": _sha256(projection),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyAtomParameterProvenanceSnapshot:
    """Every instance's per-atom provenance trace for one bound snapshot."""

    binding_snapshot: MmcifNonpolyParameterSourceBindingSnapshot
    instance_reports: tuple[
        MmcifNonpolyAtomParameterProvenanceInstanceReport, ...
    ]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyAtomParameterProvenanceSnapshot("
            f"instances={len(self.instance_reports)})"
        )

    @property
    def atom_count(self) -> int:
        return sum(row.atom_count for row in self.instance_reports)

    def _payload(self) -> dict[str, Any]:
        reports = [row.to_dict() for row in self.instance_reports]
        traced = [row for row in reports if row["trace_status"] == "traced"]
        return {
            "schema_id": (
                MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_DOCUMENT_SCHEMA_ID
            ),
            "profile_id": MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_PROFILE_ID,
            "runner_version": (
                MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_RUNNER_VERSION
            ),
            "parameter_source_snapshot_sha256": (
                self.binding_snapshot.parameter_source_snapshot.snapshot_sha256
            ),
            "instance_count": len(reports),
            "traced_instance_count": len(traced),
            "untraced_instance_count": len(reports) - len(traced),
            "atom_count": sum(row["atom_count"] for row in reports),
            "bond_count": sum(row["bond_count"] for row in reports),
            "declared_provenance_atom_count": sum(
                row["declared_provenance_atom_count"] for row in reports
            ),
            "assigned_value_atom_count": sum(
                row["assigned_value_atom_count"] for row in reports
            ),
            "fully_absent_value_atom_count": sum(
                row["fully_absent_value_atom_count"] for row in reports
            ),
            "instance_reports": reports,
            "configuration": dict(
                MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_CONFIGURATION
            ),
            "configuration_sha256": (
                MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_CONFIGURATION_SHA256
            ),
            "scientific_blockers": list(
                MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_BLOCKERS
            ),
            **_CLAIM_FLAGS,
        }

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "snapshot_sha256": self.snapshot_sha256}

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict()) + b"\n"

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        source = self.canonical_bytes()
        if len(source) > (
            MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_MAX_DOCUMENT_BYTES
        ):
            raise MmcifNonpolyAtomParameterProvenanceError(
                "atom provenance document exceeds its byte bound"
            )
        output = Path(output_path)
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=str(output.parent),
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(source)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_name, output, follow_symlinks=False)
            except FileExistsError as exc:
                raise MmcifNonpolyAtomParameterProvenanceError(
                    "atom provenance output already exists"
                ) from exc
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        return output


def trace_mmcif_nonpoly_atom_parameter_provenance(
    binding_snapshot: MmcifNonpolyParameterSourceBindingSnapshot,
) -> MmcifNonpolyAtomParameterProvenanceSnapshot:
    """Emit one per-atom provenance row for every bound canonical system."""

    reports: list[MmcifNonpolyAtomParameterProvenanceInstanceReport] = []
    for parent in binding_snapshot.instance_reports:
        if parent.bound_system is None:
            reports.append(
                MmcifNonpolyAtomParameterProvenanceInstanceReport(
                    component_id=parent.component_id,
                    instance_identity_sha256=parent.instance_identity_sha256,
                    binding_status=parent.binding_status,
                    trace_status="untraced_source_not_bound",
                    bound_system_sha256="",
                    parameter_source_binding_sha256="",
                    atom_rows=(),
                    bond_rows=(),
                    trace_blockers=tuple(parent.binding_blockers),
                )
            )
            continue
        system = parent.bound_system
        binding_digest = str(
            system.metadata.get("parameter_source_binding_sha256", "")
        )
        if binding_digest != parent.binding_sha256 or not binding_digest:
            raise MmcifNonpolyAtomParameterProvenanceError(
                "bound system does not carry its parameter-source binding digest"
            )
        observed_system_sha256 = canonical_system_sha256(system)
        if observed_system_sha256 != parent.bound_system_sha256:
            raise MmcifNonpolyAtomParameterProvenanceError(
                "bound system digest changed during provenance tracing"
            )
        atom_rows = tuple(_atom_row(system, atom) for atom in system.atoms)
        if tuple(row["atom_index"] for row in atom_rows) != tuple(
            range(len(atom_rows))
        ):
            raise MmcifNonpolyAtomParameterProvenanceError(
                "atom provenance rows are not a contiguous atom projection"
            )
        bond_rows = tuple(_bond_row(bond) for bond in system.bonds)
        reports.append(
            MmcifNonpolyAtomParameterProvenanceInstanceReport(
                component_id=parent.component_id,
                instance_identity_sha256=parent.instance_identity_sha256,
                binding_status=parent.binding_status,
                trace_status="traced",
                bound_system_sha256=observed_system_sha256,
                parameter_source_binding_sha256=binding_digest,
                atom_rows=atom_rows,
                bond_rows=bond_rows,
                trace_blockers=(),
            )
        )
    if len(reports) != len(binding_snapshot.instance_reports):
        raise MmcifNonpolyAtomParameterProvenanceError(
            "atom provenance must retain every bound-snapshot instance"
        )
    return MmcifNonpolyAtomParameterProvenanceSnapshot(
        binding_snapshot=binding_snapshot,
        instance_reports=tuple(reports),
    )


def parse_mmcif_nonpoly_atom_parameter_provenance(
    source: str | bytes,
) -> MmcifNonpolyAtomParameterProvenanceSnapshot:
    """Parse one mmCIF source and trace per-atom parameter provenance."""

    return trace_mmcif_nonpoly_atom_parameter_provenance(
        parse_mmcif_nonpoly_parameter_source_bindings(source)
    )


def mmcif_nonpoly_atom_parameter_provenance_document(
    snapshot: MmcifNonpolyAtomParameterProvenanceSnapshot,
) -> dict[str, Any]:
    return snapshot.to_dict()


def require_mmcif_nonpoly_atom_parameter_provenance_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a canonical per-atom provenance document without re-parsing."""

    if not isinstance(payload, Mapping):
        raise MmcifNonpolyAtomParameterProvenanceError(
            "atom provenance document must be a mapping"
        )
    document = dict(payload)
    if document.get("schema_id") != (
        MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_DOCUMENT_SCHEMA_ID
    ):
        raise MmcifNonpolyAtomParameterProvenanceError(
            "unsupported atom provenance schema"
        )
    declared = document.pop("snapshot_sha256", None)
    if _sha256(document) != declared:
        raise MmcifNonpolyAtomParameterProvenanceError(
            "atom provenance document digest is invalid"
        )
    for field in (
        "smirnoff_semantics_parsed",
        "parameter_values_assigned",
        "partial_charges_assigned",
        "atom_masses_assigned",
        "scientifically_validated",
        "claim_safe",
    ):
        if document.get(field) is not False:
            raise MmcifNonpolyAtomParameterProvenanceError(
                f"atom provenance document must keep {field}=false"
            )
    reports = document.get("instance_reports")
    if not isinstance(reports, list) or not reports:
        raise MmcifNonpolyAtomParameterProvenanceError(
            "atom provenance document must retain instance reports"
        )
    for item in reports:
        if not isinstance(item, Mapping):
            raise MmcifNonpolyAtomParameterProvenanceError(
                "atom provenance instance report must be a mapping"
            )
        instance = dict(item)
        instance_digest = instance.pop("instance_provenance_sha256", None)
        if _sha256(instance) != instance_digest:
            raise MmcifNonpolyAtomParameterProvenanceError(
                "atom provenance instance digest is invalid"
            )
    return {**document, "snapshot_sha256": declared}


def mmcif_nonpoly_atom_parameter_provenance_json_bytes(
    snapshot: MmcifNonpolyAtomParameterProvenanceSnapshot,
) -> bytes:
    return snapshot.canonical_bytes()


def write_mmcif_nonpoly_atom_parameter_provenance_json(
    snapshot: MmcifNonpolyAtomParameterProvenanceSnapshot,
    output_path: str | os.PathLike[str],
) -> Path:
    return snapshot.write_json(output_path)


def mmcif_nonpoly_atom_parameter_provenance_value_ids() -> Sequence[str]:
    return MMCIF_NONPOLY_ATOM_PARAMETER_VALUE_IDS


__all__ = [
    "MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_ATOM_SCHEMA_ID",
    "MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_BLOCKERS",
    "MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_BOND_SCHEMA_ID",
    "MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_CONFIGURATION",
    "MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_CONFIGURATION_SHA256",
    "MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_INSTANCE_SCHEMA_ID",
    "MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_MAX_DOCUMENT_BYTES",
    "MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_PROFILE_ID",
    "MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_RUNNER_VERSION",
    "MMCIF_NONPOLY_ATOM_PARAMETER_VALUE_IDS",
    "MmcifNonpolyAtomParameterProvenanceError",
    "MmcifNonpolyAtomParameterProvenanceInstanceReport",
    "MmcifNonpolyAtomParameterProvenanceSnapshot",
    "mmcif_nonpoly_atom_parameter_provenance_document",
    "mmcif_nonpoly_atom_parameter_provenance_json_bytes",
    "mmcif_nonpoly_atom_parameter_provenance_value_ids",
    "parse_mmcif_nonpoly_atom_parameter_provenance",
    "require_mmcif_nonpoly_atom_parameter_provenance_document",
    "trace_mmcif_nonpoly_atom_parameter_provenance",
    "write_mmcif_nonpoly_atom_parameter_provenance_json",
]
