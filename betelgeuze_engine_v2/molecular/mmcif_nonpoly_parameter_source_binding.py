"""Bind reviewed parameter-source identity to bounded canonical systems.

The binding implemented here is deliberately narrower than parameterization.  It
attaches the frozen OpenFF Sage source identity, immutable artifact digest, and
reviewed candidate-scope declaration to each eligible canonical ``AllAtomSystem``
without parsing OFFXML or assigning parameters, partial charges, or masses.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from betelgeuze_engine_v2.parameter_source_provenance import (
    PARAMETER_SOURCE_PROVENANCE_PROFILE_ID,
    PARAMETER_SOURCE_PROVENANCE_SCHEMA_ID,
    ParameterSourceProvenanceSnapshot,
    parameter_source_provenance_document,
    require_parameter_source_provenance_document,
    reviewed_parameter_source_provenance,
)

from .mmcif_nonpoly_all_atom_systems import (
    MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION,
    MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID,
    MmcifNonpolyAllAtomSystemSnapshot,
    mmcif_nonpoly_all_atom_system_document,
    parse_mmcif_nonpoly_all_atom_systems,
    require_mmcif_nonpoly_all_atom_system_document,
)
from .models import AllAtomSystem
from .serialization import (
    all_atom_system_from_canonical_json,
    canonical_system_json_bytes,
    canonical_system_sha256,
)
from .validation import require_valid_all_atom_system


MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_parameter_source_binding_projection/1.0.0"
)
MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_parameter_source_binding_document/1.0.0"
)
MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROFILE_ID = (
    "bounded_mmcif_reviewed_source_identity_to_canonical_system/1.0.0"
)
MMCIF_NONPOLY_PARAMETER_SOURCE_BINDER_VERSION = "1.0.0"

MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_LIMITATIONS = (
    "source_artifact_not_bundled",
    "offxml_not_parsed",
    "candidate_scope_parameter_coverage_not_validated",
    "applicability_domain_not_validated",
    "parameter_assignment_not_implemented",
    "partial_charge_assignment_not_implemented",
    "atom_masses_not_assigned",
    "fixed_parent_offset_geometry_not_validated",
    "force_energy_and_scientific_validation_missing",
)

_BOUND_STATUS = "reviewed_parameter_source_identity_bound_to_system"
_UNAVAILABLE_STATUS = "not_bound_canonical_system_unavailable"
_OUTSIDE_SCOPE_STATUS = "not_bound_outside_reviewed_candidate_scope"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyParameterSourceBindingError(ValueError):
    """Stable fail-closed source-to-system binding error."""

    def __init__(self, code: str, detail: str):
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(f"mmcif_nonpoly_parameter_source_binding:{self.code}: {self.detail}")


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


def _canonical_system_document(system: AllAtomSystem) -> dict[str, Any]:
    return json.loads(canonical_system_json_bytes(system).decode("ascii"))


def _claim_policy() -> dict[str, bool]:
    return {
        "reviewed_parameter_source_identity_bound": True,
        "immutable_parameter_artifact_digest_bound": True,
        "reviewed_license_identity_bound": True,
        "candidate_scope_contract_checked": True,
        "source_system_identity_preserved": True,
        "canonical_binding_hashes_bound": True,
        "failure_complete_instance_reports": True,
        "source_artifact_bundled": False,
        "runtime_network_fetch_enabled": False,
        "offxml_semantically_parsed": False,
        "parameter_coverage_validated": False,
        "applicability_domain_validated": False,
        "parameter_assignment_implemented": False,
        "partial_charge_assigned": False,
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


def _binding_identity(
    *,
    instance_identity_sha256: str,
    source_system_sha256: str,
    provenance: ParameterSourceProvenanceSnapshot,
) -> dict[str, Any]:
    return {
        "profile_id": MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROFILE_ID,
        "binder_version": MMCIF_NONPOLY_PARAMETER_SOURCE_BINDER_VERSION,
        "instance_identity_sha256": instance_identity_sha256,
        "source_system_sha256": source_system_sha256,
        "parameter_source_provenance_snapshot_sha256": provenance.snapshot_sha256,
        "parameter_source_id": provenance.source_id,
        "parameter_source_version": provenance.source_version,
        "parameter_source_review_status": provenance.review_status,
        "parameter_source_artifact_sha256": provenance.artifact_sha256,
        "parameter_source_license_spdx_id": provenance.license_spdx_id,
        "parameter_source_license_sha256": provenance.license_sha256,
        "candidate_scope": provenance.candidate_scope,
        "candidate_elements": list(provenance.candidate_elements),
        "candidate_bond_orders": list(provenance.candidate_bond_orders),
        "formal_charge_policy": "zero_only",
        "parameter_assignment_status": "not_implemented",
        "partial_charge_assignment_status": "not_implemented",
        "mass_assignment_status": "not_implemented",
    }


def _scope_blockers(
    system: AllAtomSystem,
    provenance: ParameterSourceProvenanceSnapshot,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if any(atom.element not in provenance.candidate_elements for atom in system.atoms):
        blockers.append("element_outside_reviewed_candidate_scope")
    if any(atom.formal_charge != 0 for atom in system.atoms):
        blockers.append("formal_charge_outside_reviewed_candidate_scope")
    allowed_orders = {
        1.0 if value == "single" else 2.0
        for value in provenance.candidate_bond_orders
        if value in {"single", "double"}
    }
    if any(bond.order not in allowed_orders or bond.aromatic for bond in system.bonds):
        blockers.append("bond_order_outside_reviewed_candidate_scope")
    if any(atom.aromatic for atom in system.atoms):
        blockers.append("aromaticity_outside_reviewed_candidate_scope")
    return tuple(blockers)


def _bind_system(
    *,
    system: AllAtomSystem,
    instance_identity_sha256: str,
    provenance: ParameterSourceProvenanceSnapshot,
) -> tuple[AllAtomSystem, str]:
    source_system_sha256 = canonical_system_sha256(system)
    identity = _binding_identity(
        instance_identity_sha256=instance_identity_sha256,
        source_system_sha256=source_system_sha256,
        provenance=provenance,
    )
    binding_sha256 = _sha256(identity)
    binding = {**identity, "binding_sha256": binding_sha256}
    system_metadata = dict(system.metadata)
    system_metadata.update(
        {
            "parameter_source_binding_status": _BOUND_STATUS,
            "parameter_source_binding": binding,
            "parameter_source_binding_sha256": binding_sha256,
            "parameterable": False,
        }
    )
    provenance_metadata = dict(system.provenance.metadata)
    provenance_metadata.update(
        {
            "parameter_source_bound": True,
            "parameter_source_binding_sha256": binding_sha256,
            "parameter_source_provenance_snapshot_sha256": provenance.snapshot_sha256,
            "parameter_assignment_implemented": False,
            "partial_charge_assigned": False,
            "atom_masses_assigned": False,
            "claim_safe": False,
        }
    )
    bound = replace(
        system,
        metadata=system_metadata,
        provenance=replace(system.provenance, metadata=provenance_metadata),
    )
    validation = require_valid_all_atom_system(bound)
    if validation.claim_stage.name.lower() != "contract_valid" or validation.claim_safe:
        raise MmcifNonpolyParameterSourceBindingError(
            "unexpected_claim_promotion",
            "source binding must preserve contract-valid claim-blocked state",
        )
    return bound, binding_sha256


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyParameterSourceBindingInstanceReport:
    instance_identity_sha256: str
    component_id: str
    binding_status: str
    binding_blockers: tuple[str, ...]
    limitations: tuple[str, ...]
    source_system_sha256: str
    binding_sha256: str
    bound_system: AllAtomSystem | None

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyParameterSourceBindingInstanceReport("
            f"component_id={self.component_id!r}, binding_status={self.binding_status!r})"
        )

    @property
    def source_bound(self) -> bool:
        return self.bound_system is not None

    @property
    def bound_system_sha256(self) -> str:
        return "" if self.bound_system is None else canonical_system_sha256(self.bound_system)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_identity_sha256": self.instance_identity_sha256,
            "component_id": self.component_id,
            "binding_status": self.binding_status,
            "binding_blockers": list(self.binding_blockers),
            "limitations": list(self.limitations),
            "source_system_sha256": self.source_system_sha256,
            "binding_sha256": self.binding_sha256,
            "source_bound": self.source_bound,
            "bound_system_sha256": self.bound_system_sha256,
            "canonical_bound_system_document": (
                None
                if self.bound_system is None
                else _canonical_system_document(self.bound_system)
            ),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyParameterSourceBindingSnapshot:
    all_atom_snapshot: MmcifNonpolyAllAtomSystemSnapshot
    parameter_source_snapshot: ParameterSourceProvenanceSnapshot
    instance_reports: tuple[MmcifNonpolyParameterSourceBindingInstanceReport, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyParameterSourceBindingSnapshot("
            f"instance_count={len(self.instance_reports)}, "
            f"bound_system_count={self.bound_system_count})"
        )

    @property
    def bound_system_count(self) -> int:
        return sum(report.source_bound for report in self.instance_reports)

    @property
    def unbound_system_count(self) -> int:
        return len(self.instance_reports) - self.bound_system_count

    @property
    def binding_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_parameter_source_binding_projection(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_DOCUMENT_SCHEMA_ID,
                "all_atom_snapshot_sha256": self.all_atom_snapshot.snapshot_sha256,
                "parameter_source_snapshot_sha256": (
                    self.parameter_source_snapshot.snapshot_sha256
                ),
                "binding_projection_sha256": self.binding_projection_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_sha256": self.all_atom_snapshot.source_sha256,
            "all_atom_snapshot_sha256": self.all_atom_snapshot.snapshot_sha256,
            "parameter_source_snapshot_sha256": (
                self.parameter_source_snapshot.snapshot_sha256
            ),
            "instance_count": len(self.instance_reports),
            "bound_system_count": self.bound_system_count,
            "unbound_system_count": self.unbound_system_count,
            "binding_projection_sha256": self.binding_projection_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def bind_reviewed_parameter_source_to_all_atom_snapshot(
    all_atom_snapshot: MmcifNonpolyAllAtomSystemSnapshot,
    parameter_source_snapshot: ParameterSourceProvenanceSnapshot | None = None,
) -> MmcifNonpolyParameterSourceBindingSnapshot:
    """Bind frozen reviewed source identity to every in-scope canonical system."""

    provenance = parameter_source_snapshot or reviewed_parameter_source_provenance()
    require_mmcif_nonpoly_all_atom_system_document(
        mmcif_nonpoly_all_atom_system_document(all_atom_snapshot)
    )
    require_parameter_source_provenance_document(
        parameter_source_provenance_document(provenance)
    )
    reports: list[MmcifNonpolyParameterSourceBindingInstanceReport] = []
    for parent in all_atom_snapshot.instance_reports:
        if parent.system is None:
            reports.append(
                MmcifNonpolyParameterSourceBindingInstanceReport(
                    instance_identity_sha256=parent.instance_identity_sha256,
                    component_id=parent.component_id,
                    binding_status=_UNAVAILABLE_STATUS,
                    binding_blockers=parent.materialization_blockers,
                    limitations=(),
                    source_system_sha256="",
                    binding_sha256="",
                    bound_system=None,
                )
            )
            continue
        scope_blockers = _scope_blockers(parent.system, provenance)
        if scope_blockers:
            reports.append(
                MmcifNonpolyParameterSourceBindingInstanceReport(
                    instance_identity_sha256=parent.instance_identity_sha256,
                    component_id=parent.component_id,
                    binding_status=_OUTSIDE_SCOPE_STATUS,
                    binding_blockers=scope_blockers,
                    limitations=(),
                    source_system_sha256=canonical_system_sha256(parent.system),
                    binding_sha256="",
                    bound_system=None,
                )
            )
            continue
        bound, binding_sha256 = _bind_system(
            system=parent.system,
            instance_identity_sha256=parent.instance_identity_sha256,
            provenance=provenance,
        )
        reports.append(
            MmcifNonpolyParameterSourceBindingInstanceReport(
                instance_identity_sha256=parent.instance_identity_sha256,
                component_id=parent.component_id,
                binding_status=_BOUND_STATUS,
                binding_blockers=(),
                limitations=MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_LIMITATIONS,
                source_system_sha256=canonical_system_sha256(parent.system),
                binding_sha256=binding_sha256,
                bound_system=bound,
            )
        )
    return MmcifNonpolyParameterSourceBindingSnapshot(
        all_atom_snapshot=all_atom_snapshot,
        parameter_source_snapshot=provenance,
        instance_reports=tuple(reports),
    )


def parse_mmcif_nonpoly_parameter_source_bindings(
    source: str | bytes,
) -> MmcifNonpolyParameterSourceBindingSnapshot:
    return bind_reviewed_parameter_source_to_all_atom_snapshot(
        parse_mmcif_nonpoly_all_atom_systems(source)
    )


def mmcif_nonpoly_parameter_source_binding_projection(
    snapshot: MmcifNonpolyParameterSourceBindingSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROFILE_ID,
        "binder_version": MMCIF_NONPOLY_PARAMETER_SOURCE_BINDER_VERSION,
        "instance_order": "bounded_nonpoly_identity_source_order",
        "instance_reports": [report.to_dict() for report in snapshot.instance_reports],
        **_claim_policy(),
    }


def mmcif_nonpoly_parameter_source_binding_document(
    snapshot: MmcifNonpolyParameterSourceBindingSnapshot,
) -> dict[str, Any]:
    all_atom_document = mmcif_nonpoly_all_atom_system_document(
        snapshot.all_atom_snapshot
    )
    provenance_document = parameter_source_provenance_document(
        snapshot.parameter_source_snapshot
    )
    projection = mmcif_nonpoly_parameter_source_binding_projection(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROFILE_ID,
        "binder_version": MMCIF_NONPOLY_PARAMETER_SOURCE_BINDER_VERSION,
        "all_atom_materialization_document": all_atom_document,
        "all_atom_materialization_document_sha256": _sha256(all_atom_document),
        "parameter_source_provenance_document": provenance_document,
        "parameter_source_provenance_document_sha256": _sha256(provenance_document),
        "binding_projection": projection,
        "binding_projection_sha256": _sha256(projection),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str, *, allow_empty: bool = False) -> str:
    candidate = str(value or "")
    if allow_empty and not candidate:
        return ""
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"parameter source binding {label} digest invalid")
    return candidate


def _system_from_document(payload: Mapping[str, object]) -> AllAtomSystem:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return all_atom_system_from_canonical_json(encoded)


def require_mmcif_nonpoly_parameter_source_binding_document(
    payload: object,
) -> Mapping[str, object]:
    """Verify parent evidence, bound systems, hashes, scope, and non-claims."""

    if not isinstance(payload, Mapping):
        raise ValueError("parameter source binding document must be a mapping")
    document = dict(payload)
    if (
        document.get("schema_id")
        != MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_DOCUMENT_SCHEMA_ID
        or document.get("profile_id")
        != MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROFILE_ID
        or document.get("binder_version")
        != MMCIF_NONPOLY_PARAMETER_SOURCE_BINDER_VERSION
    ):
        raise ValueError("parameter source binding document envelope mismatch")

    parent = document.get("all_atom_materialization_document")
    provenance = document.get("parameter_source_provenance_document")
    projection = document.get("binding_projection")
    if not isinstance(parent, Mapping) or not isinstance(provenance, Mapping):
        raise ValueError("parameter source binding parent evidence missing")
    if not isinstance(projection, Mapping):
        raise ValueError("parameter source binding projection missing")
    require_mmcif_nonpoly_all_atom_system_document(parent)
    require_parameter_source_provenance_document(provenance)
    parent_dict = dict(parent)
    provenance_dict = dict(provenance)
    projection_dict = dict(projection)
    if (
        document.get("all_atom_materialization_document_sha256")
        != _sha256(parent_dict)
        or document.get("parameter_source_provenance_document_sha256")
        != _sha256(provenance_dict)
        or document.get("binding_projection_sha256") != _sha256(projection_dict)
        or projection_dict.get("schema_id")
        != MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROJECTION_SCHEMA_ID
        or projection_dict.get("profile_id")
        != MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROFILE_ID
        or projection_dict.get("binder_version")
        != MMCIF_NONPOLY_PARAMETER_SOURCE_BINDER_VERSION
        or projection_dict.get("instance_order")
        != "bounded_nonpoly_identity_source_order"
        or parent_dict.get("profile_id") != MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID
        or parent_dict.get("materializer_version")
        != MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION
        or provenance_dict.get("schema_id") != PARAMETER_SOURCE_PROVENANCE_SCHEMA_ID
        or provenance_dict.get("profile_id") != PARAMETER_SOURCE_PROVENANCE_PROFILE_ID
    ):
        raise ValueError("parameter source binding evidence identity mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection_dict.get(key) is not expected:
            raise ValueError("parameter source binding claim boundary mismatch")

    parent_projection = parent_dict.get("system_projection")
    if not isinstance(parent_projection, Mapping):
        raise ValueError("parameter source binding parent projection missing")
    parent_reports_raw = parent_projection.get("instance_reports")
    reports_raw = projection_dict.get("instance_reports")
    if not isinstance(parent_reports_raw, list) or not isinstance(reports_raw, list):
        raise ValueError("parameter source binding instance reports missing")
    parent_reports = {
        str(row["instance_identity_sha256"]): dict(row)
        for row in parent_reports_raw
        if isinstance(row, Mapping)
    }
    if len(parent_reports) != len(parent_reports_raw):
        raise ValueError("parameter source binding parent instances invalid")

    bound_count = 0
    seen: set[str] = set()
    parameter_snapshot_sha256 = _require_digest(
        provenance_dict.get("snapshot_sha256"), "parameter provenance"
    )
    for raw in reports_raw:
        if not isinstance(raw, Mapping):
            raise ValueError("parameter source binding instance report invalid")
        report = dict(raw)
        instance = _require_digest(report.get("instance_identity_sha256"), "instance")
        if instance in seen or instance not in parent_reports:
            raise ValueError("parameter source binding instance crosswire")
        seen.add(instance)
        parent_report = parent_reports[instance]
        blockers = report.get("binding_blockers")
        limitations = report.get("limitations")
        if not isinstance(blockers, list) or not isinstance(limitations, list):
            raise ValueError("parameter source binding report lists invalid")
        bound_document = report.get("canonical_bound_system_document")

        if parent_report.get("system_created") is True:
            parent_system_document = parent_report.get("canonical_system_document")
            if not isinstance(parent_system_document, Mapping):
                raise ValueError("parameter source binding parent system missing")
            parent_system = _system_from_document(parent_system_document)
            source_system_sha256 = canonical_system_sha256(parent_system)
            if report.get("source_system_sha256") != source_system_sha256:
                raise ValueError("parameter source binding source system mismatch")
            if report.get("binding_status") == _BOUND_STATUS:
                bound_count += 1
                if blockers or limitations != list(
                    MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_LIMITATIONS
                ):
                    raise ValueError("parameter source binding success boundary invalid")
                if not isinstance(bound_document, Mapping):
                    raise ValueError("parameter source bound system missing")
                bound_system = _system_from_document(bound_document)
                validation = require_valid_all_atom_system(bound_system)
                identity = _binding_identity(
                    instance_identity_sha256=instance,
                    source_system_sha256=source_system_sha256,
                    provenance=reviewed_parameter_source_provenance(),
                )
                binding_sha256 = _sha256(identity)
                binding = {**identity, "binding_sha256": binding_sha256}
                restored = replace(
                    bound_system,
                    metadata=dict(parent_system.metadata),
                    provenance=replace(
                        bound_system.provenance,
                        metadata=dict(parent_system.provenance.metadata),
                    ),
                )
                if (
                    validation.claim_stage.name.lower() != "contract_valid"
                    or validation.claim_safe
                    or report.get("source_bound") is not True
                    or report.get("binding_sha256") != binding_sha256
                    or report.get("bound_system_sha256")
                    != canonical_system_sha256(bound_system)
                    or bound_system.metadata.get("parameter_source_binding") != binding
                    or bound_system.metadata.get("parameter_source_binding_sha256")
                    != binding_sha256
                    or bound_system.metadata.get("parameter_source_binding_status")
                    != _BOUND_STATUS
                    or bound_system.provenance.metadata.get("parameter_source_bound")
                    is not True
                    or bound_system.provenance.metadata.get(
                        "parameter_source_provenance_snapshot_sha256"
                    )
                    != parameter_snapshot_sha256
                    or canonical_system_sha256(restored) != source_system_sha256
                    or any(atom.partial_charge_e is not None for atom in bound_system.atoms)
                    or any(atom.mass_da is not None for atom in bound_system.atoms)
                ):
                    raise ValueError("parameter source bound system identity mismatch")
            elif report.get("binding_status") == _OUTSIDE_SCOPE_STATUS:
                if (
                    not blockers
                    or limitations
                    or bound_document is not None
                    or report.get("source_bound") is not False
                    or report.get("binding_sha256") != ""
                    or report.get("bound_system_sha256") != ""
                ):
                    raise ValueError("outside-scope parameter source binding invalid")
            else:
                raise ValueError("parameter source binding status invalid")
        else:
            if (
                report.get("binding_status") != _UNAVAILABLE_STATUS
                or not blockers
                or limitations
                or bound_document is not None
                or report.get("source_bound") is not False
                or any(
                    report.get(key) != ""
                    for key in (
                        "source_system_sha256",
                        "binding_sha256",
                        "bound_system_sha256",
                    )
                )
            ):
                raise ValueError("unavailable parameter source binding invalid")
    if seen != set(parent_reports):
        raise ValueError("parameter source binding report coverage incomplete")
    if (
        document.get("source_sha256") != parent_dict.get("source_sha256")
        or document.get("all_atom_snapshot_sha256")
        != parent_dict.get("snapshot_sha256")
        or document.get("parameter_source_snapshot_sha256")
        != parameter_snapshot_sha256
        or document.get("instance_count") != len(reports_raw)
        or document.get("bound_system_count") != bound_count
        or document.get("unbound_system_count") != len(reports_raw) - bound_count
    ):
        raise ValueError("parameter source binding summary mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_DOCUMENT_SCHEMA_ID,
            "all_atom_snapshot_sha256": parent_dict.get("snapshot_sha256"),
            "parameter_source_snapshot_sha256": parameter_snapshot_sha256,
            "binding_projection_sha256": _sha256(projection_dict),
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("parameter source binding snapshot digest mismatch")
    return payload


def mmcif_nonpoly_parameter_source_binding_json_bytes(
    snapshot: MmcifNonpolyParameterSourceBindingSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_parameter_source_binding_document(snapshot))


def write_mmcif_nonpoly_parameter_source_binding_json(
    path: str | Path,
    snapshot: MmcifNonpolyParameterSourceBindingSnapshot,
) -> Path:
    """Atomically write a private canonical source-binding document."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(mmcif_nonpoly_parameter_source_binding_json_bytes(snapshot))
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
    "MMCIF_NONPOLY_PARAMETER_SOURCE_BINDER_VERSION",
    "MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_LIMITATIONS",
    "MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROFILE_ID",
    "MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROJECTION_SCHEMA_ID",
    "MmcifNonpolyParameterSourceBindingError",
    "MmcifNonpolyParameterSourceBindingInstanceReport",
    "MmcifNonpolyParameterSourceBindingSnapshot",
    "bind_reviewed_parameter_source_to_all_atom_snapshot",
    "mmcif_nonpoly_parameter_source_binding_document",
    "mmcif_nonpoly_parameter_source_binding_json_bytes",
    "mmcif_nonpoly_parameter_source_binding_projection",
    "parse_mmcif_nonpoly_parameter_source_bindings",
    "require_mmcif_nonpoly_parameter_source_binding_document",
    "write_mmcif_nonpoly_parameter_source_binding_json",
]
