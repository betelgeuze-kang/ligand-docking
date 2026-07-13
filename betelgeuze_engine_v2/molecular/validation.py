"""Fail-closed validation for canonical all-atom systems."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterable

import torch

from betelgeuze_engine_v2.contracts import ContractVersionError, require_compatible_schema
from .models import AllAtomSystem, atomic_number_for_element


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
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
    provenance_claim_safe: bool

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def claim_safe(self) -> bool:
        return bool(self.valid and not self.warnings and self.provenance_claim_safe)

    def raise_for_errors(self, *, warnings_as_errors: bool = False) -> None:
        blocking = self.issues if warnings_as_errors else self.errors
        if blocking:
            raise MolecularValidationError(self, warnings_as_errors=warnings_as_errors)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "valid": self.valid,
            "claim_safe": self.claim_safe,
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
        preview = "; ".join(f"{issue.code}@{issue.location}" for issue in blocking[:6])
        suffix = "" if len(blocking) <= 6 else f"; +{len(blocking) - 6} more"
        super().__init__(f"all-atom system validation failed: {preview}{suffix}")


def _index_issues(values: Iterable[int], *, label: str) -> list[ValidationIssue]:
    indices = [int(value) for value in values]
    expected = list(range(len(indices)))
    if indices == expected:
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
    """Validate referential, chemical, geometry, cell, and provenance invariants.

    Validation is linear in the number of topology records; it never constructs
    an atom-pair matrix.
    """

    issues: list[ValidationIssue] = []

    try:
        require_compatible_schema(system.schema_id)
    except ContractVersionError as exc:
        issues.append(ValidationIssue("error", "unsupported_schema", "schema_id", str(exc)))

    if not system.system_id:
        issues.append(ValidationIssue("warning", "missing_system_id", "system_id", "system_id is empty"))
    if system.coordinate_unit != "angstrom":
        issues.append(
            ValidationIssue(
                "error",
                "unsupported_coordinate_unit",
                "coordinate_unit",
                "canonical engine v2 coordinates must be in Angstrom",
            )
        )
    if not system.has_coordinates:
        issues.append(
            ValidationIssue(
                "warning",
                "coordinates_missing",
                "coordinates",
                "topology-only systems require coordinates before numeric execution",
            )
        )
    if system.atom_count < 1:
        issues.append(ValidationIssue("error", "empty_topology", "atoms", "at least one explicit atom is required"))
    if int(system.coordinates.shape[1]) != system.atom_count:
        issues.append(
            ValidationIssue(
                "error",
                "coordinate_atom_count_mismatch",
                "coordinates",
                f"coordinates contain {int(system.coordinates.shape[1])} atoms "
                f"but topology contains {system.atom_count}",
            )
        )
    if not bool(torch.isfinite(system.coordinates).all().detach().cpu().item()):
        issues.append(ValidationIssue("error", "nonfinite_coordinates", "coordinates", "coordinates must be finite"))

    issues.extend(_index_issues((atom.index for atom in system.atoms), label="atom"))
    issues.extend(_index_issues((bond.index for bond in system.bonds), label="bond"))
    issues.extend(_index_issues((residue.index for residue in system.residues), label="residue"))
    issues.extend(_index_issues((chain.index for chain in system.chains), label="chain"))

    residue_count = len(system.residues)
    chain_count = len(system.chains)
    atom_count = system.atom_count

    atom_maps: dict[int, int] = {}
    for position, atom in enumerate(system.atoms):
        location = f"atoms[{position}]"
        if not atom.name:
            issues.append(ValidationIssue("error", "missing_atom_name", location, "atom name is empty"))
        expected_number = atomic_number_for_element(atom.element)
        if expected_number == 0:
            issues.append(ValidationIssue("error", "unknown_element", location, f"unknown element {atom.element!r}"))
        elif int(atom.atomic_number) != expected_number:
            issues.append(
                ValidationIssue(
                    "error",
                    "element_atomic_number_mismatch",
                    location,
                    f"element {atom.element} has atomic number {expected_number}, not {atom.atomic_number}",
                )
            )
        if atom.residue_index < 0 or atom.residue_index >= residue_count:
            issues.append(
                ValidationIssue(
                    "error",
                    "invalid_atom_residue",
                    location,
                    "atom references an unknown residue",
                )
            )
        if atom.serial is not None and atom.serial < 1:
            issues.append(
                ValidationIssue(
                    "warning",
                    "nonpositive_atom_serial",
                    location,
                    "source serial should be positive",
                )
            )
        if atom.atom_map is not None:
            if atom.atom_map < 1:
                issues.append(
                    ValidationIssue(
                        "error",
                        "nonpositive_atom_map",
                        location,
                        "atom map identifiers must be positive",
                    )
                )
            elif atom.atom_map in atom_maps:
                issues.append(
                    ValidationIssue(
                        "error",
                        "duplicate_atom_map",
                        location,
                        f"atom map {atom.atom_map} is already assigned to atom {atom_maps[atom.atom_map]}",
                    )
                )
            else:
                atom_maps[atom.atom_map] = position
        if atom.partial_charge_e is not None and not _finite_optional(atom.partial_charge_e):
            issues.append(
                ValidationIssue(
                    "error",
                    "nonfinite_partial_charge",
                    location,
                    "partial charge must be finite",
                )
            )
        if not atom.formal_charge_known:
            issues.append(
                ValidationIssue(
                    "warning",
                    "unknown_formal_charge",
                    location,
                    "formal charge is represented by a placeholder and must be resolved before chemistry features",
                )
            )
        if atom.mass_da is not None and (not _finite_optional(atom.mass_da) or float(atom.mass_da) <= 0.0):
            issues.append(ValidationIssue("error", "invalid_atom_mass", location, "mass must be finite and positive"))
        if atom.isotope_mass_number is not None and (
            atom.isotope_mass_number < atom.atomic_number or atom.isotope_mass_number > 350
        ):
            issues.append(
                ValidationIssue(
                    "error",
                    "invalid_isotope_mass_number",
                    location,
                    "isotope mass number must be at least the atomic number and at most 350",
                )
            )
        if atom.occupancy is not None and (
            not _finite_optional(atom.occupancy) or not 0.0 <= float(atom.occupancy) <= 1.0
        ):
            issues.append(ValidationIssue("error", "invalid_occupancy", location, "occupancy must be in [0, 1]"))
        if atom.b_factor is not None and not _finite_optional(atom.b_factor):
            issues.append(ValidationIssue("error", "nonfinite_b_factor", location, "B-factor must be finite"))
        if type(atom.aromatic) is not bool:
            issues.append(
                ValidationIssue(
                    "error",
                    "invalid_atom_aromatic_flag",
                    location,
                    "atom aromatic flag must be a boolean",
                )
            )
        atom_stereo = str(atom.stereo or "").strip().upper()
        if atom_stereo not in _ATOM_STEREO_LABELS:
            issues.append(
                ValidationIssue(
                    "error",
                    "unsupported_atom_stereo",
                    location,
                    f"unsupported atom stereo label {atom.stereo!r}",
                )
            )
        elif atom_stereo in {"R", "S"}:
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
        if not residue.name:
            issues.append(ValidationIssue("error", "missing_residue_name", location, "residue name is empty"))
        if residue.chain_index < 0 or residue.chain_index >= chain_count:
            issues.append(
                ValidationIssue(
                    "error",
                    "invalid_residue_chain",
                    location,
                    "residue references an unknown chain",
                )
            )
        if not _strictly_increasing(residue.atom_indices):
            issues.append(
                ValidationIssue(
                    "error",
                    "noncanonical_residue_atom_membership",
                    location,
                    "residue atom indices must be unique and increasing",
                )
            )
        if not residue.atom_indices:
            issues.append(ValidationIssue("warning", "empty_residue", location, "residue has no atoms"))
        if type(residue.hetero) is not bool:
            issues.append(
                ValidationIssue(
                    "error",
                    "invalid_residue_hetero_flag",
                    location,
                    "residue hetero flag must be a boolean",
                )
            )
        for atom_index in residue.atom_indices:
            if atom_index < 0 or atom_index >= atom_count:
                issues.append(
                    ValidationIssue(
                        "error",
                        "invalid_residue_atom",
                        location,
                        "residue references an unknown atom",
                    )
                )
                continue
            atom_membership[atom_index] += 1
            if system.atoms[atom_index].residue_index != residue.index:
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
            issues.append(
                ValidationIssue(
                    "error",
                    "atom_residue_membership_count",
                    f"atoms[{atom_index}]",
                    f"atom must belong to exactly one residue, observed {count}",
                )
            )

    residue_membership = [0] * residue_count
    chain_ids: set[str] = set()
    for position, chain in enumerate(system.chains):
        location = f"chains[{position}]"
        if not chain.chain_id:
            issues.append(ValidationIssue("warning", "empty_chain_id", location, "chain identifier is empty"))
        elif chain.chain_id in chain_ids:
            issues.append(ValidationIssue("error", "duplicate_chain_id", location, "chain identifiers must be unique"))
        chain_ids.add(chain.chain_id)
        if not _strictly_increasing(chain.residue_indices):
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
                issues.append(
                    ValidationIssue(
                        "error",
                        "invalid_chain_residue",
                        location,
                        "chain references an unknown residue",
                    )
                )
                continue
            residue_membership[residue_index] += 1
            if system.residues[residue_index].chain_index != chain.index:
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
        if (
            bond.atom_i < 0
            or bond.atom_i >= atom_count
            or bond.atom_j < 0
            or bond.atom_j >= atom_count
        ):
            issues.append(ValidationIssue("error", "invalid_bond_atom", location, "bond references an unknown atom"))
            continue
        if bond.atom_i >= bond.atom_j:
            issues.append(
                ValidationIssue(
                    "error",
                    "noncanonical_bond_endpoints",
                    location,
                    "bond endpoints must satisfy atom_i < atom_j",
                )
            )
        pair = (bond.atom_i, bond.atom_j)
        if pair in bond_pairs:
            issues.append(ValidationIssue("error", "duplicate_bond", location, f"duplicate bond {pair}"))
        bond_pairs.add(pair)
        if not math.isfinite(float(bond.order)) or float(bond.order) <= 0.0:
            issues.append(
                ValidationIssue(
                    "error",
                    "invalid_bond_order",
                    location,
                    "bond order must be finite and positive",
                )
            )
        if type(bond.aromatic) is not bool:
            issues.append(
                ValidationIssue(
                    "error",
                    "invalid_bond_aromatic_flag",
                    location,
                    "bond aromatic flag must be a boolean",
                )
            )
        bond_stereo = str(bond.stereo or "").strip().upper()
        if bond_stereo not in _BOND_STEREO_LABELS:
            issues.append(
                ValidationIssue(
                    "error",
                    "unsupported_bond_stereo",
                    location,
                    f"unsupported bond stereo label {bond.stereo!r}",
                )
            )
        if bond_stereo in {"E", "Z"}:
            if bond.aromatic or not math.isclose(float(bond.order), 2.0, rel_tol=0.0, abs_tol=1.0e-6):
                issues.append(
                    ValidationIssue(
                        "error",
                        "incompatible_ez_bond_stereo",
                        location,
                        "E/Z stereo requires a non-aromatic double bond",
                    )
                )
            else:
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
            issues.append(ValidationIssue("error", "nonfinite_unit_cell", "cell", "unit-cell vectors must be finite"))
        else:
            volume = float(torch.linalg.det(vectors.detach().to(dtype=torch.float64, device="cpu")).item())
            if not math.isfinite(volume) or volume <= 1.0e-12:
                issues.append(
                    ValidationIssue(
                        "error",
                        "invalid_unit_cell_volume",
                        "cell",
                        "unit-cell vectors must form a positive right-handed volume",
                    )
                )

    provenance = system.provenance
    if not provenance.preparation_ready:
        issues.append(
            ValidationIssue(
                "warning",
                "preparation_incomplete",
                "provenance.preparation_ready",
                "molecular preparation must be completed before numeric execution",
            )
        )
    provenance_claim_safe = False
    if type(provenance.claim_safe) is not bool:
        issues.append(
            ValidationIssue(
                "error",
                "invalid_provenance_claim_safe_flag",
                "provenance.claim_safe",
                "provenance claim_safe flag must be a boolean",
            )
        )
    else:
        provenance_claim_safe = provenance.claim_safe
    if provenance.source_sha256 and _SHA256_RE.fullmatch(provenance.source_sha256) is None:
        issues.append(
            ValidationIssue(
                "error",
                "invalid_source_sha256",
                "provenance.source_sha256",
                "SHA-256 must be 64 lowercase hex characters",
            )
        )
    for position, digest in enumerate(provenance.parent_sha256):
        if _SHA256_RE.fullmatch(digest) is None:
            issues.append(
                ValidationIssue(
                    "error",
                    "invalid_parent_sha256",
                    f"provenance.parent_sha256[{position}]",
                    "SHA-256 must be 64 lowercase hex characters",
                )
            )
    if provenance_claim_safe and not provenance.source_sha256:
        issues.append(
            ValidationIssue(
                "warning",
                "claim_safe_without_source_digest",
                "provenance",
                "claim-safe provenance should carry an immutable source digest",
            )
        )

    return ValidationReport(
        schema_id=system.schema_id,
        issues=tuple(issues),
        provenance_claim_safe=provenance_claim_safe,
    )


def require_valid_all_atom_system(
    system: AllAtomSystem,
    *,
    warnings_as_errors: bool = False,
) -> ValidationReport:
    report = validate_all_atom_system(system)
    report.raise_for_errors(warnings_as_errors=warnings_as_errors)
    return report
