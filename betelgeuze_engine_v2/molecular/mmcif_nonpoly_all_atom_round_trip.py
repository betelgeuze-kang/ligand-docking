"""Canonical identity round-trip receipts for bounded prepared systems.

The receipt proves that a charge-assigned ``AllAtomSystem`` survives the Engine
v2 canonical JSON encode/decode/re-encode path byte-for-byte, including topology,
coordinates, source lineage metadata, parameter-source binding, and partial-
charge binary64 values.  It does not re-emit the original mmCIF text or preserve
its lexical spelling, category order, comments, or insignificant whitespace.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tempfile
from typing import Any, Mapping

from .mmcif_nonpoly_partial_charge_assignments import (
    MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNER_VERSION,
    MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROFILE_ID,
    MmcifNonpolyPartialChargeAssignmentSnapshot,
    mmcif_nonpoly_partial_charge_assignment_document,
    require_mmcif_nonpoly_partial_charge_assignment_document,
)
from .models import AllAtomSystem
from .serialization import (
    all_atom_system_from_canonical_json,
    canonical_coordinates_sha256,
    canonical_system_json_bytes,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from .validation import require_valid_all_atom_system


MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_all_atom_round_trip_projection/1.0.0"
)
MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_all_atom_round_trip_document/1.0.0"
)
MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROFILE_ID = (
    "bounded_canonical_json_all_atom_identity_round_trip/1.0.0"
)
MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_VERIFIER_VERSION = "1.0.0"

MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_LIMITATIONS = (
    "original_mmcif_text_not_re_emitted",
    "source_token_spelling_order_comments_and_whitespace_not_preserved",
    "canonical_engine_v2_json_format_only",
    "caller_supplied_partial_charges_not_scientifically_validated",
    "force_field_parameter_assignment_not_implemented",
    "atom_masses_not_assigned",
    "fixed_parent_offset_geometry_not_validated",
    "chemistry_force_energy_and_scientific_validation_missing",
)

_ROUND_TRIPPED_STATUS = "canonical_all_atom_identity_round_trip_verified"
_UNAVAILABLE_STATUS = "not_round_tripped_charge_assigned_system_unavailable"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyAllAtomRoundTripError(ValueError):
    """Stable fail-closed canonical round-trip error."""

    def __init__(self, code: str, detail: str):
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(f"mmcif_nonpoly_all_atom_round_trip:{self.code}: {self.detail}")


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


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _binary64_bits_hex(value: float | None) -> str:
    return "" if value is None else struct.pack(">d", float(value)).hex()


def _claim_policy() -> dict[str, bool]:
    return {
        "canonical_all_atom_json_round_trip_verified": True,
        "canonical_reencoding_byte_identical": True,
        "atom_bond_residue_and_chain_identity_preserved": True,
        "topology_hash_preserved": True,
        "coordinate_hash_preserved": True,
        "source_lineage_metadata_preserved": True,
        "parameter_source_binding_preserved": True,
        "partial_charge_binary64_bits_preserved": True,
        "failure_complete_instance_reports": True,
        "original_mmcif_text_re_emitted": False,
        "source_lexical_tokens_preserved": False,
        "source_category_order_preserved": False,
        "source_comments_and_whitespace_preserved": False,
        "partial_charges_scientifically_validated": False,
        "force_field_parameter_assignment_implemented": False,
        "atom_masses_assigned": False,
        "parameterable": False,
        "coordinate_geometry_validated": False,
        "chemistry_validated": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _identity_projection(system: AllAtomSystem) -> dict[str, Any]:
    return {
        "system_id": system.system_id,
        "system_sha256": canonical_system_sha256(system),
        "topology_sha256": canonical_topology_sha256(system),
        "coordinates_sha256": canonical_coordinates_sha256(system),
        "coordinate_unit": system.coordinate_unit,
        "coordinate_dtype": str(system.coordinates.dtype),
        "model_count": system.model_count,
        "instance_identity_sha256": system.metadata.get(
            "instance_identity_sha256"
        ),
        "source_sha256": system.provenance.source_sha256,
        "system_metadata_sha256": _sha256(dict(system.metadata)),
        "provenance_metadata_sha256": _sha256(dict(system.provenance.metadata)),
        "atoms": [
            {
                "index": atom.index,
                "name": atom.name,
                "element": atom.element,
                "atomic_number": atom.atomic_number,
                "residue_index": atom.residue_index,
                "formal_charge": atom.formal_charge,
                "partial_charge_binary64_bits_hex": _binary64_bits_hex(
                    atom.partial_charge_e
                ),
                "mass_binary64_bits_hex": _binary64_bits_hex(atom.mass_da),
                "isotope_mass_number": atom.isotope_mass_number,
                "serial": atom.serial,
                "altloc": atom.altloc,
                "occupancy_binary64_bits_hex": _binary64_bits_hex(atom.occupancy),
                "b_factor_binary64_bits_hex": _binary64_bits_hex(atom.b_factor),
                "aromatic": atom.aromatic,
                "stereo": atom.stereo,
                "metadata_sha256": _sha256(dict(atom.metadata)),
            }
            for atom in system.atoms
        ],
        "bonds": [
            {
                "index": bond.index,
                "atom_i": bond.atom_i,
                "atom_j": bond.atom_j,
                "order_binary64_bits_hex": _binary64_bits_hex(bond.order),
                "aromatic": bond.aromatic,
                "stereo": bond.stereo,
                "source": bond.source,
                "metadata_sha256": _sha256(dict(bond.metadata)),
            }
            for bond in system.bonds
        ],
        "residues": [
            {
                "index": residue.index,
                "name": residue.name,
                "chain_index": residue.chain_index,
                "sequence_number": residue.sequence_number,
                "atom_indices": list(residue.atom_indices),
                "insertion_code": residue.insertion_code,
                "entity_type": residue.entity_type,
                "hetero": residue.hetero,
                "metadata_sha256": _sha256(dict(residue.metadata)),
            }
            for residue in system.residues
        ],
        "chains": [
            {
                "index": chain.index,
                "chain_id": chain.chain_id,
                "residue_indices": list(chain.residue_indices),
                "entity_id": chain.entity_id,
                "metadata_sha256": _sha256(dict(chain.metadata)),
            }
            for chain in system.chains
        ],
        "provenance": {
            "source_format": system.provenance.source_format,
            "source_id": system.provenance.source_id,
            "source_sha256": system.provenance.source_sha256,
            "parser_name": system.provenance.parser_name,
            "parser_version": system.provenance.parser_version,
            "operations": list(system.provenance.operations),
            "parent_sha256": list(system.provenance.parent_sha256),
            "source_digest_verified": system.provenance.source_digest_verified,
            "transformation_chain_verified": (
                system.provenance.transformation_chain_verified
            ),
            "chemistry_validated": system.provenance.chemistry_validated,
            "scientifically_validated": system.provenance.scientifically_validated,
            "product_qualified": system.provenance.product_qualified,
        },
    }


def _round_trip_evidence(system: AllAtomSystem) -> dict[str, Any]:
    if any(atom.partial_charge_e is None for atom in system.atoms):
        raise MmcifNonpolyAllAtomRoundTripError(
            "partial_charge_coverage_incomplete",
            "round-trip input must carry a partial charge for every atom",
        )
    if not system.metadata.get("parameter_source_binding_sha256"):
        raise MmcifNonpolyAllAtomRoundTripError(
            "parameter_source_binding_missing",
            "round-trip input must retain its parameter-source binding",
        )
    if not system.metadata.get("partial_charge_assignment_input_sha256"):
        raise MmcifNonpolyAllAtomRoundTripError(
            "partial_charge_assignment_binding_missing",
            "round-trip input must retain its charge-assignment binding",
        )
    encoded = canonical_system_json_bytes(system)
    decoded = all_atom_system_from_canonical_json(encoded.decode("ascii"))
    validation = require_valid_all_atom_system(decoded)
    reencoded = canonical_system_json_bytes(decoded)
    source_projection = _identity_projection(system)
    decoded_projection = _identity_projection(decoded)
    if (
        encoded != reencoded
        or source_projection != decoded_projection
        or canonical_system_sha256(system) != canonical_system_sha256(decoded)
        or canonical_topology_sha256(system) != canonical_topology_sha256(decoded)
        or canonical_coordinates_sha256(system)
        != canonical_coordinates_sha256(decoded)
        or validation.claim_stage.name.lower() != "contract_valid"
        or validation.claim_safe
    ):
        raise MmcifNonpolyAllAtomRoundTripError(
            "canonical_round_trip_mismatch",
            "canonical encode/decode/re-encode did not preserve exact identity",
        )
    return {
        "source_system_sha256": canonical_system_sha256(system),
        "canonical_json_sha256": _bytes_sha256(encoded),
        "canonical_json_byte_count": len(encoded),
        "round_trip_system_sha256": canonical_system_sha256(decoded),
        "round_trip_json_sha256": _bytes_sha256(reencoded),
        "topology_sha256": canonical_topology_sha256(system),
        "coordinates_sha256": canonical_coordinates_sha256(system),
        "identity_projection_sha256": _sha256(source_projection),
        "canonical_reencoding_byte_identical": True,
    }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyAllAtomRoundTripInstanceReport:
    instance_identity_sha256: str
    component_id: str
    round_trip_status: str
    round_trip_blockers: tuple[str, ...]
    limitations: tuple[str, ...]
    source_system_sha256: str
    canonical_json_sha256: str
    canonical_json_byte_count: int
    round_trip_system_sha256: str
    round_trip_json_sha256: str
    topology_sha256: str
    coordinates_sha256: str
    identity_projection_sha256: str
    canonical_reencoding_byte_identical: bool

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyAllAtomRoundTripInstanceReport("
            f"component_id={self.component_id!r}, round_trip_status={self.round_trip_status!r})"
        )

    @property
    def round_trip_verified(self) -> bool:
        return self.round_trip_status == _ROUND_TRIPPED_STATUS

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_identity_sha256": self.instance_identity_sha256,
            "component_id": self.component_id,
            "round_trip_status": self.round_trip_status,
            "round_trip_blockers": list(self.round_trip_blockers),
            "limitations": list(self.limitations),
            "round_trip_verified": self.round_trip_verified,
            "source_system_sha256": self.source_system_sha256,
            "canonical_json_sha256": self.canonical_json_sha256,
            "canonical_json_byte_count": self.canonical_json_byte_count,
            "round_trip_system_sha256": self.round_trip_system_sha256,
            "round_trip_json_sha256": self.round_trip_json_sha256,
            "topology_sha256": self.topology_sha256,
            "coordinates_sha256": self.coordinates_sha256,
            "identity_projection_sha256": self.identity_projection_sha256,
            "canonical_reencoding_byte_identical": (
                self.canonical_reencoding_byte_identical
            ),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyAllAtomRoundTripSnapshot:
    partial_charge_assignment_snapshot: MmcifNonpolyPartialChargeAssignmentSnapshot
    instance_reports: tuple[MmcifNonpolyAllAtomRoundTripInstanceReport, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyAllAtomRoundTripSnapshot("
            f"instance_count={len(self.instance_reports)}, "
            f"verified_system_count={self.verified_system_count})"
        )

    @property
    def verified_system_count(self) -> int:
        return sum(report.round_trip_verified for report in self.instance_reports)

    @property
    def unavailable_system_count(self) -> int:
        return len(self.instance_reports) - self.verified_system_count

    @property
    def round_trip_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_all_atom_round_trip_projection(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_DOCUMENT_SCHEMA_ID,
                "partial_charge_assignment_snapshot_sha256": (
                    self.partial_charge_assignment_snapshot.snapshot_sha256
                ),
                "round_trip_projection_sha256": self.round_trip_projection_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        parent = self.partial_charge_assignment_snapshot
        return {
            "source_sha256": (
                parent.parameter_source_binding_snapshot.all_atom_snapshot.source_sha256
            ),
            "partial_charge_assignment_snapshot_sha256": parent.snapshot_sha256,
            "instance_count": len(self.instance_reports),
            "verified_system_count": self.verified_system_count,
            "unavailable_system_count": self.unavailable_system_count,
            "round_trip_projection_sha256": self.round_trip_projection_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def verify_mmcif_nonpoly_all_atom_round_trips(
    partial_charge_assignment_snapshot: MmcifNonpolyPartialChargeAssignmentSnapshot,
) -> MmcifNonpolyAllAtomRoundTripSnapshot:
    """Execute canonical round trips and retain unavailable parent rows."""

    require_mmcif_nonpoly_partial_charge_assignment_document(
        mmcif_nonpoly_partial_charge_assignment_document(
            partial_charge_assignment_snapshot
        )
    )
    reports: list[MmcifNonpolyAllAtomRoundTripInstanceReport] = []
    for parent in partial_charge_assignment_snapshot.instance_reports:
        system = parent.assigned_system
        if system is None:
            reports.append(
                MmcifNonpolyAllAtomRoundTripInstanceReport(
                    instance_identity_sha256=parent.instance_identity_sha256,
                    component_id=parent.component_id,
                    round_trip_status=_UNAVAILABLE_STATUS,
                    round_trip_blockers=parent.assignment_blockers,
                    limitations=(),
                    source_system_sha256="",
                    canonical_json_sha256="",
                    canonical_json_byte_count=0,
                    round_trip_system_sha256="",
                    round_trip_json_sha256="",
                    topology_sha256="",
                    coordinates_sha256="",
                    identity_projection_sha256="",
                    canonical_reencoding_byte_identical=False,
                )
            )
            continue
        evidence = _round_trip_evidence(system)
        reports.append(
            MmcifNonpolyAllAtomRoundTripInstanceReport(
                instance_identity_sha256=parent.instance_identity_sha256,
                component_id=parent.component_id,
                round_trip_status=_ROUND_TRIPPED_STATUS,
                round_trip_blockers=(),
                limitations=MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_LIMITATIONS,
                **evidence,
            )
        )
    return MmcifNonpolyAllAtomRoundTripSnapshot(
        partial_charge_assignment_snapshot=partial_charge_assignment_snapshot,
        instance_reports=tuple(reports),
    )


def mmcif_nonpoly_all_atom_round_trip_projection(
    snapshot: MmcifNonpolyAllAtomRoundTripSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROFILE_ID,
        "verifier_version": MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_VERIFIER_VERSION,
        "instance_order": "bounded_nonpoly_identity_source_order",
        "interchange_format": "betelgeuze_engine_v2_canonical_all_atom_json",
        "instance_reports": [report.to_dict() for report in snapshot.instance_reports],
        **_claim_policy(),
    }


def mmcif_nonpoly_all_atom_round_trip_document(
    snapshot: MmcifNonpolyAllAtomRoundTripSnapshot,
) -> dict[str, Any]:
    parent = mmcif_nonpoly_partial_charge_assignment_document(
        snapshot.partial_charge_assignment_snapshot
    )
    projection = mmcif_nonpoly_all_atom_round_trip_projection(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROFILE_ID,
        "verifier_version": MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_VERIFIER_VERSION,
        "partial_charge_assignment_document": parent,
        "partial_charge_assignment_document_sha256": _sha256(parent),
        "round_trip_projection": projection,
        "round_trip_projection_sha256": _sha256(projection),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str, *, allow_empty: bool = False) -> str:
    candidate = str(value or "")
    if allow_empty and not candidate:
        return ""
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"all-atom round trip {label} digest invalid")
    return candidate


def require_mmcif_nonpoly_all_atom_round_trip_document(
    payload: object,
) -> Mapping[str, object]:
    """Re-execute every embedded canonical round trip and verify the receipt."""

    if not isinstance(payload, Mapping):
        raise ValueError("all-atom round-trip document must be a mapping")
    document = dict(payload)
    if (
        document.get("schema_id")
        != MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_DOCUMENT_SCHEMA_ID
        or document.get("profile_id") != MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROFILE_ID
        or document.get("verifier_version")
        != MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_VERIFIER_VERSION
    ):
        raise ValueError("all-atom round-trip document envelope mismatch")
    parent = document.get("partial_charge_assignment_document")
    projection = document.get("round_trip_projection")
    if not isinstance(parent, Mapping) or not isinstance(projection, Mapping):
        raise ValueError("all-atom round-trip evidence missing")
    require_mmcif_nonpoly_partial_charge_assignment_document(parent)
    parent_dict = dict(parent)
    projection_dict = dict(projection)
    if (
        document.get("partial_charge_assignment_document_sha256")
        != _sha256(parent_dict)
        or document.get("round_trip_projection_sha256") != _sha256(projection_dict)
        or projection_dict.get("schema_id")
        != MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROJECTION_SCHEMA_ID
        or projection_dict.get("profile_id")
        != MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROFILE_ID
        or projection_dict.get("verifier_version")
        != MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_VERIFIER_VERSION
        or projection_dict.get("instance_order")
        != "bounded_nonpoly_identity_source_order"
        or projection_dict.get("interchange_format")
        != "betelgeuze_engine_v2_canonical_all_atom_json"
        or parent_dict.get("profile_id")
        != MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROFILE_ID
        or parent_dict.get("assigner_version")
        != MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNER_VERSION
    ):
        raise ValueError("all-atom round-trip evidence identity mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection_dict.get(key) is not expected:
            raise ValueError("all-atom round-trip claim boundary mismatch")

    parent_projection = parent_dict.get("assignment_projection")
    if not isinstance(parent_projection, Mapping):
        raise ValueError("all-atom round-trip parent projection missing")
    parent_reports_raw = parent_projection.get("instance_reports")
    reports_raw = projection_dict.get("instance_reports")
    if not isinstance(parent_reports_raw, list) or not isinstance(reports_raw, list):
        raise ValueError("all-atom round-trip reports missing")
    parent_reports = {
        str(row["instance_identity_sha256"]): dict(row)
        for row in parent_reports_raw
        if isinstance(row, Mapping)
    }
    if len(parent_reports) != len(parent_reports_raw):
        raise ValueError("all-atom round-trip parent instances invalid")

    verified = 0
    seen: set[str] = set()
    for raw in reports_raw:
        if not isinstance(raw, Mapping):
            raise ValueError("all-atom round-trip instance report invalid")
        report = dict(raw)
        instance = _require_digest(report.get("instance_identity_sha256"), "instance")
        if instance in seen or instance not in parent_reports:
            raise ValueError("all-atom round-trip instance crosswire")
        seen.add(instance)
        parent_report = parent_reports[instance]
        blockers = report.get("round_trip_blockers")
        limitations = report.get("limitations")
        if not isinstance(blockers, list) or not isinstance(limitations, list):
            raise ValueError("all-atom round-trip report lists invalid")
        assigned_payload = parent_report.get("canonical_assigned_system_document")
        if parent_report.get("charge_assigned") is True:
            if not isinstance(assigned_payload, Mapping):
                raise ValueError("all-atom round-trip parent system missing")
            system = all_atom_system_from_canonical_json(
                json.dumps(
                    dict(assigned_payload),
                    ensure_ascii=True,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            evidence = _round_trip_evidence(system)
            expected = {
                "instance_identity_sha256": instance,
                "component_id": parent_report.get("component_id"),
                "round_trip_status": _ROUND_TRIPPED_STATUS,
                "round_trip_blockers": [],
                "limitations": list(MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_LIMITATIONS),
                "round_trip_verified": True,
                **evidence,
            }
            if report != expected:
                raise ValueError("all-atom round-trip receipt mismatch")
            verified += 1
        else:
            expected = {
                "instance_identity_sha256": instance,
                "component_id": parent_report.get("component_id"),
                "round_trip_status": _UNAVAILABLE_STATUS,
                "round_trip_blockers": list(
                    parent_report.get("assignment_blockers") or []
                ),
                "limitations": [],
                "round_trip_verified": False,
                "source_system_sha256": "",
                "canonical_json_sha256": "",
                "canonical_json_byte_count": 0,
                "round_trip_system_sha256": "",
                "round_trip_json_sha256": "",
                "topology_sha256": "",
                "coordinates_sha256": "",
                "identity_projection_sha256": "",
                "canonical_reencoding_byte_identical": False,
            }
            if report != expected:
                raise ValueError("unavailable all-atom round-trip report invalid")
    if seen != set(parent_reports):
        raise ValueError("all-atom round-trip report coverage incomplete")
    parent_snapshot_sha256 = _require_digest(
        parent_dict.get("snapshot_sha256"), "partial charge snapshot"
    )
    if (
        document.get("source_sha256") != parent_dict.get("source_sha256")
        or document.get("partial_charge_assignment_snapshot_sha256")
        != parent_snapshot_sha256
        or document.get("instance_count") != len(reports_raw)
        or document.get("verified_system_count") != verified
        or document.get("unavailable_system_count") != len(reports_raw) - verified
    ):
        raise ValueError("all-atom round-trip summary mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_DOCUMENT_SCHEMA_ID,
            "partial_charge_assignment_snapshot_sha256": parent_snapshot_sha256,
            "round_trip_projection_sha256": _sha256(projection_dict),
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("all-atom round-trip snapshot digest mismatch")
    return payload


def mmcif_nonpoly_all_atom_round_trip_json_bytes(
    snapshot: MmcifNonpolyAllAtomRoundTripSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_all_atom_round_trip_document(snapshot))


def write_mmcif_nonpoly_all_atom_round_trip_json(
    path: str | Path,
    snapshot: MmcifNonpolyAllAtomRoundTripSnapshot,
) -> Path:
    """Atomically write a private canonical round-trip receipt."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(mmcif_nonpoly_all_atom_round_trip_json_bytes(snapshot))
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
    "MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_LIMITATIONS",
    "MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROFILE_ID",
    "MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_VERIFIER_VERSION",
    "MmcifNonpolyAllAtomRoundTripError",
    "MmcifNonpolyAllAtomRoundTripInstanceReport",
    "MmcifNonpolyAllAtomRoundTripSnapshot",
    "mmcif_nonpoly_all_atom_round_trip_document",
    "mmcif_nonpoly_all_atom_round_trip_json_bytes",
    "mmcif_nonpoly_all_atom_round_trip_projection",
    "require_mmcif_nonpoly_all_atom_round_trip_document",
    "verify_mmcif_nonpoly_all_atom_round_trips",
    "write_mmcif_nonpoly_all_atom_round_trip_json",
]
