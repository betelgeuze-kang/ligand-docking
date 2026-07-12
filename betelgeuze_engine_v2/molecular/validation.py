"""Fail-closed validation for canonical all-atom systems."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import torch

from betelgeuze_engine_v2.contracts import (
    ClaimStage,
    ContractVersionError,
    require_compatible_schema,
)
from .models import AllAtomSystem, atomic_number_for_element
from .serialization import CanonicalSerializationError, canonical_system_sha256


_ATOM_STEREO_LABELS = {"UNSPECIFIED", "UNKNOWN", "NONE", "R", "S"}
_BOND_STEREO_LABELS = {
    "NONE",
    "UNSPECIFIED",
    "UNKNOWN",
    "E",
    "Z",
    "CIS",
    "TRANS",
    "UP",
    "DOWN",
    "EITHER",
}


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    location: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    schema_id: str
    issues: tuple[ValidationIssue, ...]
    schema_compatible: bool
    topology_consistent: bool
    coordinates_valid: bool
    provenance_digest_present: bool
    provenance_verified: bool
    stereochemistry_declared: bool
    stereochemistry_geometry_verified: bool
    chemistry_validated: bool
    scientific_claim_ready: bool
    product_qualified: bool
    system_sha256: str | None

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def valid(self) -> bool:
        return bool(
            not self.errors
            and self.schema_compatible
            and self.topology_consistent
            and self.coordinates_valid
        )

    @property
    def claim_stage(self) -> ClaimStage:
        if not self.valid:
            return ClaimStage.INVALID
        if self.product_qualified and self.scientific_claim_ready:
            return ClaimStage.PRODUCT_QUALIFIED
        if self.scientific_claim_ready:
            return ClaimStage.SCIENTIFICALLY_VALIDATED
        if self.chemistry_validated and self.provenance_verified:
            return ClaimStage.CHEMISTRY_VALIDATED
        if self.provenance_verified:
            return ClaimStage.PROVENANCE_VERIFIED
        return ClaimStage.CONTRACT_VALID

    @property
    def claim_safe(self) -> bool:
        """Compatibility alias for older callers."""

        return self.claim_stage.claim_safe

    def raise_for_errors(self, *, warnings_as_errors: bool = False) -> None:
        blocking = self.issues if warnings_as_errors else self.errors
        if blocking:
            raise MolecularValidationError(self, warnings_as_errors=warnings_as_errors)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "valid": self.valid,
            "claim_stage": self.claim_stage.name.lower(),
            "claim_safe": self.claim_safe,
            "schema_compatible": self.schema_compatible,
            "topology_consistent": self.topology_consistent,
            "coordinates_valid": self.coordinates_valid,
            "provenance_digest_present": self.provenance_digest_present,
            "provenance_verified": self.provenance_verified,
            "stereochemistry_declared": self.stereochemistry_declared,
            "stereochemistry_geometry_verified": self.stereochemistry_geometry_verified,
            "chemistry_validated": self.chemistry_validated,
            "scientific_claim_ready": self.scientific_claim_ready,
            "product_qualified": self.product_qualified,
            "system_sha256": self.system_sha256,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "location": issue.location,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }


class MolecularValidationError(ValueError):
    def __init__(self, report: ValidationReport, *, warnings_as_errors: bool = False):
        self.report = report
        self.warnings_as_errors = bool(warnings_as_errors)
        blocking = report.issues if warnings_as_errors else report.errors
        preview = "; ".join(
            f"{issue.code}@{issue.location}" for issue in blocking[:6]
        )
        suffix = "" if len(blocking) <= 6 else f"; +{len(blocking) - 6} more"
        super().__init__(f"all-atom system validation failed: {preview}{suffix}")


def _index_issues(values: Iterable[int], *, label: str) -> list[ValidationIssue]:
    indices = [int(value) for value in values]
    if indices == list(range(len(indices))):
        return []
    return [
        ValidationIssue(
            "error",
            f"noncanonical_{label}_indices",
            label,
            f"{label} indices must be contiguous and ordered from zero",
        )
    ]


def _finite_optional(value: float | None) -> bool:
    return value is None or math.isfinite(float(value))


def _strictly_increasing(values: tuple[int, ...]) -> bool:
    return all(first < second for first, second in zip(values, values[1:]))


def validate_all_atom_system(system: AllAtomSystem) -> ValidationReport:
    """Validate contract, topology, coordinates, provenance, and claim stages.

    The implementation is linear in topology records and never constructs an
    atom-pair matrix. Chemistry and scientific readiness are not inferred from
    structural bookkeeping alone.
    """

    issues: list[ValidationIssue] = []
    schema_compatible = True
    topology_consistent = True
    coordinates_valid = True
    stereochemistry_declared = False
    stereochemistry_geometry_verified = True

    try:
        require_compatible_schema(system.schema_id)
    except ContractVersionError as exc:
        schema_compatible = False
        issues.append(
            ValidationIssue("error", "unsupported_schema", "schema_id", str(exc))
        )

    if not system.system_id:
        issues.append(
            ValidationIssue("warning", "missing_system_id", "system_id", "system_id is empty")
        )
    if system.coordinate_unit != "angstrom":
        coordinates_valid = False
        issues.append(
            ValidationIssue(
                "error",
                "unsupported_coordinate_unit",
                "coordinate_unit",
                "canonical Engine v2 coordinates must be in Angstrom",
            )
        )
    if system.model_count < 1:
        coordinates_valid = False
        issues.append(
            ValidationIssue(
                "error",
                "empty_coordinate_ensemble",
                "coordinates",
                "at least one coordinate model is required",
            )
        )
    if system.atom_count < 1:
        topology_consistent = False
        issues.append(
            ValidationIssue("error", "empty_topology", "atoms", "at least one explicit atom is required")
        )
    if int(system.coordinates.shape[1]) != system.atom_count:
        coordinates_valid = False
        issues.append(
            ValidationIssue(
                "error",
                "coordinate_atom_count_mismatch",
                "coordinates",
                f"coordinates contain {int(system.coordinates.shape[1])} atoms but topology contains {system.atom_count}",
            )
        )
    if not bool(torch.isfinite(system.coordinates).all().detach().cpu().item()):
        coordinates_valid = False
        issues.append(
            ValidationIssue("error", "nonfinite_coordinates", "coordinates", "coordinates must be finite")
        )

    for label, values in (
        ("atom", (atom.index for atom in system.atoms)),
        ("bond", (bond.index for bond in system.bonds)),
        ("residue", (residue.index for residue in system.residues)),
        ("chain", (chain.index for chain in system.chains)),
    ):
        found = _index_issues(values, label=label)
        if found:
            topology_consistent = False
            issues.extend(found)

    atom_count = system.atom_count
    residue_count = len(system.residues)
    chain_count = len(system.chains)

    for position, atom in enumerate(system.atoms):
        location = f"atoms[{position}]"
        if not atom.name:
            topology_consistent = False
            issues.append(ValidationIssue("error", "missing_atom_name", location, "atom name is empty"))
        expected_number = atomic_number_for_element(atom.element)
        if expected_number == 0:
            topology_consistent = False
            issues.append(ValidationIssue("error", "unknown_element", location, f"unknown element {atom.element!r}"))
        elif atom.atomic_number != expected_number:
            topology_consistent = False
            issues.append(
                ValidationIssue(
                    "error",
                    "element_atomic_number_mismatch",
                    location,
                    f"element {atom.element} has atomic number {expected_number}, not {atom.atomic_number}",
                )
            )
        if atom.residue_index < 0 or atom.residue_index >= residue_count:
            topology_consistent = False
            issues.append(
                ValidationIssue("error", "invalid_atom_residue", location, "atom references an unknown residue")
            )
        if atom.partial_charge_e is not None and not _finite_optional(atom.partial_charge_e):
            issues.append(
                ValidationIssue("error", "nonfinite_partial_charge", location, "partial charge must be finite")
            )
        if atom.mass_da is not None and (
            not _finite_optional(atom.mass_da) or float(atom.mass_da) <= 0.0
        ):
            issues.append(ValidationIssue("error", "invalid_atom_mass", location, "mass must be finite and positive"))
        if atom.occupancy is not None and (
            not _finite_optional(atom.occupancy)
            or not 0.0 <= float(atom.occupancy) <= 1.0
        ):
            issues.append(ValidationIssue("error", "invalid_occupancy", location, "occupancy must be in [0, 1]"))
        atom_stereo = str(atom.stereo or "").strip().upper()
        if atom_stereo not in _ATOM_STEREO_LABELS:
            topology_consistent = False
            issues.append(
                ValidationIssue("error", "unsupported_atom_stereo", location, f"unsupported atom stereo label {atom.stereo!r}")
            )
        elif atom_stereo in {"R", "S"}:
            stereochemistry_declared = True
            stereochemistry_geometry_verified = False
            issues.append(
                ValidationIssue(
                    "warning",
                    "atom_stereo_geometry_unverified",
                    location,
                    "R/S label is typed but has not been checked against coordinates",
                )
            )

    atom_membership = [0] * atom_count
    for position, residue in enumerate(system.residues):
        location = f"residues[{position}]"
        if residue.chain_index < 0 or residue.chain_index >= chain_count:
            topology_consistent = False
            issues.append(
                ValidationIssue("error", "invalid_residue_chain", location, "residue references an unknown chain")
            )
        if not _strictly_increasing(residue.atom_indices):
            topology_consistent = False
            issues.append(
                ValidationIssue(
                    "error",
                    "noncanonical_residue_atom_membership",
                    location,
                    "residue atom indices must be unique and increasing",
                )
            )
        for atom_index in residue.atom_indices:
            if atom_index < 0 or atom_index >= atom_count:
                topology_consistent = False
                issues.append(
                    ValidationIssue("error", "invalid_residue_atom", location, "residue references an unknown atom")
                )
                continue
            atom_membership[atom_index] += 1
            if system.atoms[atom_index].residue_index != residue.index:
                topology_consistent = False
                issues.append(
                    ValidationIssue(
                        "error",
                        "atom_residue_membership_mismatch",
                        location,
                        f"atom {atom_index} points to residue {system.atoms[atom_index].residue_index}",
                    )
                )
    for atom_index, count in enumerate(atom_membership):
        if count != 1:
            topology_consistent = False
            issues.append(
                ValidationIssue(
                    "error",
                    "atom_residue_membership_count",
                    f"atoms[{atom_index}]",
                    f"atom must belong to exactly one residue, observed {count}",
                )
            )

    residue_membership = [0] * residue_count
    seen_chain_ids: set[str] = set()
    for position, chain in enumerate(system.chains):
        location = f"chains[{position}]"
        if chain.chain_id in seen_chain_ids:
            topology_consistent = False
            issues.append(ValidationIssue("error", "duplicate_chain_id", location, "chain identifiers must be unique"))
        seen_chain_ids.add(chain.chain_id)
        if not _strictly_increasing(chain.residue_indices):
            topology_consistent = False
            issues.append(
                ValidationIssue(
                    "error",
                    "noncanonical_chain_residue_membership",
                    location,
                    "chain residue indices must be unique and increasing",
                )
            )
        for residue_index in chain.residue_indices:
            if residue_index < 0 or residue_index >= residue_count:
                topology_consistent = False
                issues.append(
                    ValidationIssue("error", "invalid_chain_residue", location, "chain references an unknown residue")
                )
                continue
            residue_membership[residue_index] += 1
            if system.residues[residue_index].chain_index != chain.index:
                topology_consistent = False
                issues.append(
                    ValidationIssue(
                        "error",
                        "residue_chain_membership_mismatch",
                        location,
                        f"residue {residue_index} points to chain {system.residues[residue_index].chain_index}",
                    )
                )
    for residue_index, count in enumerate(residue_membership):
        if count != 1:
            topology_consistent = False
            issues.append(
                ValidationIssue(
                    "error",
                    "residue_chain_membership_count",
                    f"residues[{residue_index}]",
                    f"residue must belong to exactly one chain, observed {count}",
                )
            )

    bond_pairs: set[tuple[int, int]] = set()
    for position, bond in enumerate(system.bonds):
        location = f"bonds[{position}]"
        if not (0 <= bond.atom_i < atom_count and 0 <= bond.atom_j < atom_count):
            topology_consistent = False
            issues.append(ValidationIssue("error", "invalid_bond_atom", location, "bond references an unknown atom"))
            continue
        if bond.atom_i >= bond.atom_j:
            topology_consistent = False
            issues.append(
                ValidationIssue("error", "noncanonical_bond_endpoints", location, "bond endpoints must satisfy atom_i < atom_j")
            )
        pair = (bond.atom_i, bond.atom_j)
        if pair in bond_pairs:
            topology_consistent = False
            issues.append(ValidationIssue("error", "duplicate_bond", location, f"duplicate bond {pair}"))
        bond_pairs.add(pair)
        if not math.isfinite(float(bond.order)) or float(bond.order) <= 0.0:
            topology_consistent = False
            issues.append(ValidationIssue("error", "invalid_bond_order", location, "bond order must be finite and positive"))
        bond_stereo = str(bond.stereo or "").strip().upper()
        if bond_stereo not in _BOND_STEREO_LABELS:
            topology_consistent = False
            issues.append(
                ValidationIssue("error", "unsupported_bond_stereo", location, f"unsupported bond stereo label {bond.stereo!r}")
            )
        elif bond_stereo in {"E", "Z"}:
            stereochemistry_declared = True
            if bond.aromatic or not math.isclose(float(bond.order), 2.0, abs_tol=1.0e-6):
                topology_consistent = False
                issues.append(
                    ValidationIssue(
                        "error",
                        "incompatible_ez_bond_stereo",
                        location,
                        "E/Z stereo requires a non-aromatic double bond",
                    )
                )
            else:
                stereochemistry_geometry_verified = False
                issues.append(
                    ValidationIssue(
                        "warning",
                        "bond_stereo_geometry_unverified",
                        location,
                        "E/Z label is typed but has not been checked against coordinates",
                    )
                )

    if system.cell is not None:
        vectors = system.cell.vectors
        if not bool(torch.isfinite(vectors).all().detach().cpu().item()):
            coordinates_valid = False
            issues.append(ValidationIssue("error", "nonfinite_unit_cell", "cell", "unit-cell vectors must be finite"))
        else:
            volume = float(torch.linalg.det(vectors.detach().to(dtype=torch.float64, device="cpu")).item())
            if not math.isfinite(volume) or volume <= 1.0e-12:
                coordinates_valid = False
                issues.append(
                    ValidationIssue(
                        "error",
                        "invalid_unit_cell_volume",
                        "cell",
                        "unit-cell vectors must form a positive right-handed volume",
                    )
                )

    provenance = system.provenance
    provenance_digest_present = bool(provenance.source_sha256)
    provenance_verified = bool(provenance.provenance_verified)
    if provenance.source_digest_verified and not provenance_digest_present:
        issues.append(
            ValidationIssue(
                "error",
                "verified_source_digest_missing",
                "provenance",
                "source digest cannot be verified when it is absent",
            )
        )
        provenance_verified = False

    system_digest: str | None = None
    try:
        system_digest = canonical_system_sha256(system)
    except CanonicalSerializationError as exc:
        issues.append(
            ValidationIssue("error", "canonical_serialization_failed", "system", str(exc))
        )

    chemistry_validated = bool(provenance.chemistry_validated and provenance_verified)
    scientific_claim_ready = bool(
        provenance.scientifically_validated
        and chemistry_validated
        and stereochemistry_geometry_verified
        and not any(issue.severity == "error" for issue in issues)
    )
    product_qualified = bool(provenance.product_qualified and scientific_claim_ready)

    return ValidationReport(
        schema_id=system.schema_id,
        issues=tuple(issues),
        schema_compatible=schema_compatible,
        topology_consistent=topology_consistent,
        coordinates_valid=coordinates_valid,
        provenance_digest_present=provenance_digest_present,
        provenance_verified=provenance_verified,
        stereochemistry_declared=stereochemistry_declared,
        stereochemistry_geometry_verified=stereochemistry_geometry_verified,
        chemistry_validated=chemistry_validated,
        scientific_claim_ready=scientific_claim_ready,
        product_qualified=product_qualified,
        system_sha256=system_digest,
    )


def require_valid_all_atom_system(
    system: AllAtomSystem,
    *,
    warnings_as_errors: bool = False,
) -> ValidationReport:
    report = validate_all_atom_system(system)
    report.raise_for_errors(warnings_as_errors=warnings_as_errors)
    return report
