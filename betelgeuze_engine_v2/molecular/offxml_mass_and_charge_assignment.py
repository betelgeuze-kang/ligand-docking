"""Fail-closed atom mass and library partial-charge assignment.

The per-atom provenance trace reported that every atom's ``mass_da`` and
``partial_charge_e`` were absent, and the valence assigner had to keep
``partial_charges_assigned=false``: nothing ever produced those two values.

This module produces both, each from a declared source rather than a guess.
Masses come from a frozen reviewed standard-atomic-weight table keyed by atomic
number; an element outside that table fails closed instead of receiving a
fabricated mass.  Partial charges come from a SMIRNOFF ``LibraryCharges``
section, resolved per atom by the same last-declared-match-wins rule the valence
assigner uses.

Coverage is a gate.  Every atom must receive a mass and a charge, and the
assigned charge vector must sum to the system's total formal charge within an
exact binary64 tolerance; a partial assignment or a charge vector that does not
conserve total charge fails closed, because either would silently produce a
physically wrong system.

Assignment attaches reviewed values to atoms.  No energy or force is evaluated,
the reviewed library-charge values carry no calibration review, and no
independent validation exists, so every result stays claim-closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .models import AllAtomSystem
from .offxml_semantic_parser import (
    OffxmlSemanticDocument,
    OffxmlSemanticParameter,
)
from .smirks_pattern_parser import (
    SmirksPatternParserError,
    parse_smirks_pattern,
)
from .smirks_subgraph_matcher import (
    SmirksSubgraphMatcherError,
    match_smirks_query,
)


OFFXML_ATOM_ASSIGNMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_offxml_atom_mass_charge/1.0.0"
)
OFFXML_MASS_CHARGE_ASSIGNMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_offxml_mass_and_charge_assignment/1.0.0"
)
OFFXML_MASS_CHARGE_ASSIGNMENT_PROFILE_ID = (
    "offxml_mass_and_charge_assignment/1.0.0"
)
OFFXML_MASS_CHARGE_ASSIGNMENT_VERSION = "1.0.0"
OFFXML_MASS_CHARGE_LIBRARY_HANDLER = "LibraryCharges"
OFFXML_MASS_CHARGE_TOTAL_TOLERANCE_E = 1.0e-9
OFFXML_MASS_CHARGE_MAX_ATOMS = 512

# Reviewed IUPAC standard atomic weights (Da) for the supported element scope.
# An atomic number absent from this table fails closed.
OFFXML_REVIEWED_STANDARD_ATOMIC_WEIGHTS_DA = {
    1: 1.008,
    6: 12.011,
    7: 14.007,
    8: 15.999,
    9: 18.998403163,
    15: 30.973761998,
    16: 32.06,
    17: 35.45,
    35: 79.904,
    53: 126.90447,
}
OFFXML_REVIEWED_ATOMIC_WEIGHT_SOURCE_ID = (
    "iupac_ciaaw_standard_atomic_weights_2021"
)

OFFXML_MASS_CHARGE_ASSIGNMENT_CONFIGURATION = {
    "schema_id": (
        "betelgeuze.engine_v2_offxml_mass_and_charge_configuration/1.0.0"
    ),
    "mass_source_id": OFFXML_REVIEWED_ATOMIC_WEIGHT_SOURCE_ID,
    "mass_source_policy": "frozen_reviewed_table_keyed_by_atomic_number",
    "supported_atomic_numbers": sorted(
        OFFXML_REVIEWED_STANDARD_ATOMIC_WEIGHTS_DA
    ),
    "isotope_specific_masses_supported": False,
    "charge_handler": OFFXML_MASS_CHARGE_LIBRARY_HANDLER,
    "charge_conflict_resolution": "last_declared_matching_parameter_wins",
    "charge_generation_implemented": False,
    "charge_total_tolerance_e": OFFXML_MASS_CHARGE_TOTAL_TOLERANCE_E,
    "total_formal_charge_conservation_required": True,
    "incomplete_mass_or_charge_coverage_fails_closed": True,
    "energies_or_forces_evaluated": False,
    "charge_values_calibration_reviewed": False,
    "max_atoms": OFFXML_MASS_CHARGE_MAX_ATOMS,
}
OFFXML_MASS_CHARGE_ASSIGNMENT_CONFIGURATION_SHA256 = hashlib.sha256(
    json.dumps(
        OFFXML_MASS_CHARGE_ASSIGNMENT_CONFIGURATION,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
).hexdigest()

OFFXML_MASS_CHARGE_ASSIGNMENT_BLOCKERS = (
    "standard_atomic_weights_are_element_averages_not_isotope_masses",
    "library_charge_values_calibration_not_reviewed",
    "conformer_dependent_charge_generation_not_implemented",
    "assigned_values_not_evaluated_in_any_energy_or_force_term",
    "independent_force_and_energy_validation_missing",
    "independent_scientific_review_missing",
    "validated_refinement_claim_not_authorized",
)

_CLAIM_FLAGS = {
    "atom_masses_assigned": True,
    "partial_charges_assigned": True,
    "mass_coverage_complete": True,
    "charge_coverage_complete": True,
    "total_formal_charge_conserved": True,
    "isotope_specific_masses_assigned": False,
    "charge_generation_implemented": False,
    "energies_or_forces_evaluated": False,
    "charge_values_calibration_reviewed": False,
    "independent_external_review_present": False,
    "benchmark_validated": False,
    "scientifically_validated": False,
    "claim_safe": False,
}


class OffxmlMassAndChargeAssignmentError(ValueError):
    """A mass, charge, coverage, or conservation requirement failed."""


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


def _reviewed_mass(atomic_number: int) -> float:
    mass = OFFXML_REVIEWED_STANDARD_ATOMIC_WEIGHTS_DA.get(atomic_number)
    if mass is None:
        raise OffxmlMassAndChargeAssignmentError(
            f"atomic number {atomic_number} is outside the reviewed mass table"
        )
    return mass


def _library_charges(parameter: OffxmlSemanticParameter) -> tuple[float, ...]:
    """Read ``charge1..chargeN`` from one LibraryCharges entry, in order."""

    values: dict[int, float] = {}
    for row in parameter.quantities:
        attribute = str(row["attribute"])
        if not attribute.startswith("charge"):
            continue
        suffix = attribute[len("charge") :]
        if not suffix.isdigit():
            raise OffxmlMassAndChargeAssignmentError(
                f"library charge attribute {attribute!r} is not charge<N>"
            )
        ordinal = int(suffix)
        if ordinal < 1:
            raise OffxmlMassAndChargeAssignmentError(
                "library charge ordinals are one-based"
            )
        if str(row["unit"]) != "elementary_charge":
            raise OffxmlMassAndChargeAssignmentError(
                f"{attribute} must declare elementary_charge"
            )
        if ordinal in values:
            raise OffxmlMassAndChargeAssignmentError(
                f"{attribute} is declared more than once"
            )
        values[ordinal] = float.fromhex(str(row["value_binary64_hex"]))
    if not values:
        raise OffxmlMassAndChargeAssignmentError(
            f"library charge {parameter.parameter_id!r} declares no charge value"
        )
    if sorted(values) != list(range(1, len(values) + 1)):
        raise OffxmlMassAndChargeAssignmentError(
            f"library charge {parameter.parameter_id!r} ordinals are not contiguous"
        )
    return tuple(values[ordinal] for ordinal in sorted(values))


@dataclass(frozen=True, slots=True, repr=False)
class OffxmlAtomAssignment:
    """One atom's assigned mass and partial charge with their sources."""

    atom_index: int
    element: str
    atomic_number: int
    mass_da: float
    mass_source_id: str
    partial_charge_e: float
    charge_parameter_id: str
    charge_declaration_order: int
    charge_smirks: str
    charge_map_position: int
    superseded_charge_parameter_ids: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            "OffxmlAtomAssignment("
            f"atom_index={self.atom_index}, element={self.element!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        projection = {
            "schema_id": OFFXML_ATOM_ASSIGNMENT_SCHEMA_ID,
            "atom_index": self.atom_index,
            "element": self.element,
            "atomic_number": self.atomic_number,
            "mass_da_binary64_hex": float(self.mass_da).hex(),
            "mass_source_id": self.mass_source_id,
            "isotope_specific_mass_assigned": False,
            "partial_charge_e_binary64_hex": float(self.partial_charge_e).hex(),
            "charge_parameter_id": self.charge_parameter_id,
            "charge_declaration_order": self.charge_declaration_order,
            "charge_smirks": self.charge_smirks,
            "charge_map_position": self.charge_map_position,
            "superseded_charge_parameter_ids": list(
                self.superseded_charge_parameter_ids
            ),
            "superseded_count": len(self.superseded_charge_parameter_ids),
            "values_evaluated_in_energy_term": False,
        }
        return {**projection, "atom_assignment_sha256": _sha256(projection)}


@dataclass(frozen=True, slots=True, repr=False)
class OffxmlMassAndChargeAssignment:
    """Canonical, claim-closed mass and charge assignment for one system."""

    offxml_document_sha256: str
    system_sha256: str
    total_formal_charge: int
    assigned_charge_total_e: float
    atoms: tuple[OffxmlAtomAssignment, ...]

    def __repr__(self) -> str:
        return f"OffxmlMassAndChargeAssignment(atoms={len(self.atoms)})"

    def _payload(self) -> dict[str, Any]:
        atom_rows = [row.to_dict() for row in self.atoms]
        return {
            "schema_id": OFFXML_MASS_CHARGE_ASSIGNMENT_SCHEMA_ID,
            "profile_id": OFFXML_MASS_CHARGE_ASSIGNMENT_PROFILE_ID,
            "assigner_version": OFFXML_MASS_CHARGE_ASSIGNMENT_VERSION,
            "offxml_document_sha256": self.offxml_document_sha256,
            "system_sha256": self.system_sha256,
            "atom_count": len(atom_rows),
            "assigned_mass_atom_count": len(atom_rows),
            "assigned_charge_atom_count": len(atom_rows),
            "mass_source_id": OFFXML_REVIEWED_ATOMIC_WEIGHT_SOURCE_ID,
            "charge_handler": OFFXML_MASS_CHARGE_LIBRARY_HANDLER,
            "total_formal_charge": self.total_formal_charge,
            "assigned_charge_total_e_binary64_hex": (
                float(self.assigned_charge_total_e).hex()
            ),
            "charge_total_tolerance_e_binary64_hex": (
                float(OFFXML_MASS_CHARGE_TOTAL_TOLERANCE_E).hex()
            ),
            "assigned_mass_total_da_binary64_hex": (
                float(sum(row.mass_da for row in self.atoms)).hex()
            ),
            "atoms": atom_rows,
            "superseded_charge_candidate_count": sum(
                row["superseded_count"] for row in atom_rows
            ),
            "distinct_charge_parameter_ids": sorted(
                {row["charge_parameter_id"] for row in atom_rows}
            ),
            "configuration": dict(OFFXML_MASS_CHARGE_ASSIGNMENT_CONFIGURATION),
            "configuration_sha256": (
                OFFXML_MASS_CHARGE_ASSIGNMENT_CONFIGURATION_SHA256
            ),
            "scientific_blockers": list(
                OFFXML_MASS_CHARGE_ASSIGNMENT_BLOCKERS
            ),
            **_CLAIM_FLAGS,
        }

    @property
    def assignment_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "assignment_sha256": self.assignment_sha256}


def assign_offxml_masses_and_charges(
    document: OffxmlSemanticDocument,
    system: AllAtomSystem,
) -> OffxmlMassAndChargeAssignment:
    """Assign a reviewed mass and a library partial charge to every atom."""

    if not isinstance(document, OffxmlSemanticDocument):
        raise OffxmlMassAndChargeAssignmentError(
            "assignment requires a parsed OFFXML semantic document"
        )
    atoms = list(system.atoms)
    if not atoms:
        raise OffxmlMassAndChargeAssignmentError(
            "canonical system declares no atoms"
        )
    if len(atoms) > OFFXML_MASS_CHARGE_MAX_ATOMS:
        raise OffxmlMassAndChargeAssignmentError(
            "canonical system exceeds its atom bound"
        )
    section = next(
        (
            row
            for row in document.handlers
            if row.handler == OFFXML_MASS_CHARGE_LIBRARY_HANDLER
        ),
        None,
    )
    if section is None:
        raise OffxmlMassAndChargeAssignmentError(
            f"OFFXML document omits the {OFFXML_MASS_CHARGE_LIBRARY_HANDLER} "
            "section"
        )
    winners: dict[int, dict[str, Any]] = {}
    seen_ids: set[str] = set()
    for declaration_order, parameter in enumerate(section.parameters):
        if parameter.parameter_id in seen_ids:
            raise OffxmlMassAndChargeAssignmentError(
                f"library charge id {parameter.parameter_id!r} is declared twice"
            )
        seen_ids.add(parameter.parameter_id)
        charges = _library_charges(parameter)
        try:
            query = parse_smirks_pattern(parameter.smirks)
            match_set = match_smirks_query(query, system)
        except (SmirksPatternParserError, SmirksSubgraphMatcherError) as exc:
            raise OffxmlMassAndChargeAssignmentError(
                f"library charge {parameter.parameter_id!r} could not be matched "
                "within the reviewed subset"
            ) from exc
        for match in match_set.matches:
            mapped = match.mapped_atom_indices
            if len(mapped) != len(charges):
                raise OffxmlMassAndChargeAssignmentError(
                    f"library charge {parameter.parameter_id!r} declares "
                    f"{len(charges)} charges for {len(mapped)} mapped atoms"
                )
            for position, atom_index in enumerate(mapped):
                existing = winners.get(atom_index)
                superseded = (
                    list(existing["superseded_charge_parameter_ids"])
                    if existing
                    else []
                )
                if existing is not None and (
                    existing["charge_parameter_id"] != parameter.parameter_id
                ):
                    superseded.append(str(existing["charge_parameter_id"]))
                winners[atom_index] = {
                    "partial_charge_e": charges[position],
                    "charge_parameter_id": parameter.parameter_id,
                    "charge_declaration_order": declaration_order,
                    "charge_smirks": parameter.smirks,
                    "charge_map_position": position,
                    "superseded_charge_parameter_ids": superseded,
                }
    missing = [int(atom.index) for atom in atoms if int(atom.index) not in winners]
    if missing:
        raise OffxmlMassAndChargeAssignmentError(
            f"LibraryCharges leaves atom {missing[0]} without a partial charge"
        )
    rows: list[OffxmlAtomAssignment] = []
    for atom in atoms:
        index = int(atom.index)
        winner = winners[index]
        rows.append(
            OffxmlAtomAssignment(
                atom_index=index,
                element=str(atom.element),
                atomic_number=int(atom.atomic_number),
                mass_da=_reviewed_mass(int(atom.atomic_number)),
                mass_source_id=OFFXML_REVIEWED_ATOMIC_WEIGHT_SOURCE_ID,
                partial_charge_e=float(winner["partial_charge_e"]),
                charge_parameter_id=str(winner["charge_parameter_id"]),
                charge_declaration_order=int(winner["charge_declaration_order"]),
                charge_smirks=str(winner["charge_smirks"]),
                charge_map_position=int(winner["charge_map_position"]),
                superseded_charge_parameter_ids=tuple(
                    str(value)
                    for value in winner["superseded_charge_parameter_ids"]
                ),
            )
        )
    total_formal = sum(int(atom.formal_charge) for atom in atoms)
    assigned_total = sum(row.partial_charge_e for row in rows)
    if abs(assigned_total - total_formal) > OFFXML_MASS_CHARGE_TOTAL_TOLERANCE_E:
        raise OffxmlMassAndChargeAssignmentError(
            "assigned partial charges do not conserve the total formal charge"
        )
    from .serialization import canonical_system_sha256

    return OffxmlMassAndChargeAssignment(
        offxml_document_sha256=document.document_sha256,
        system_sha256=canonical_system_sha256(system),
        total_formal_charge=total_formal,
        assigned_charge_total_e=assigned_total,
        atoms=tuple(rows),
    )


def offxml_mass_and_charge_assignment_document(
    assignment: OffxmlMassAndChargeAssignment,
) -> dict[str, Any]:
    return assignment.to_dict()


def require_offxml_mass_and_charge_assignment_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a canonical mass/charge document without reassigning."""

    if not isinstance(payload, Mapping):
        raise OffxmlMassAndChargeAssignmentError(
            "mass and charge document must be a mapping"
        )
    document = dict(payload)
    if document.get("schema_id") != OFFXML_MASS_CHARGE_ASSIGNMENT_SCHEMA_ID:
        raise OffxmlMassAndChargeAssignmentError(
            "unsupported mass and charge assignment schema"
        )
    declared = document.pop("assignment_sha256", None)
    if _sha256(document) != declared:
        raise OffxmlMassAndChargeAssignmentError(
            "mass and charge document digest is invalid"
        )
    for field in (
        "isotope_specific_masses_assigned",
        "charge_generation_implemented",
        "energies_or_forces_evaluated",
        "charge_values_calibration_reviewed",
        "scientifically_validated",
        "claim_safe",
    ):
        if document.get(field) is not False:
            raise OffxmlMassAndChargeAssignmentError(
                f"mass and charge document must keep {field}=false"
            )
    atoms = document.get("atoms")
    if not isinstance(atoms, list) or not atoms:
        raise OffxmlMassAndChargeAssignmentError(
            "mass and charge document must retain atom rows"
        )
    if document.get("atom_count") != len(atoms):
        raise OffxmlMassAndChargeAssignmentError(
            "mass and charge document omits atom rows"
        )
    for field in ("assigned_mass_atom_count", "assigned_charge_atom_count"):
        if document.get(field) != len(atoms):
            raise OffxmlMassAndChargeAssignmentError(
                f"mass and charge document publishes incomplete {field}"
            )
    total_formal = document.get("total_formal_charge")
    if type(total_formal) is not int:
        raise OffxmlMassAndChargeAssignmentError(
            "mass and charge document total formal charge is invalid"
        )
    assigned_total = float.fromhex(
        str(document.get("assigned_charge_total_e_binary64_hex"))
    )
    if abs(assigned_total - total_formal) > OFFXML_MASS_CHARGE_TOTAL_TOLERANCE_E:
        raise OffxmlMassAndChargeAssignmentError(
            "mass and charge document publishes a non-conserving charge total"
        )
    for item in atoms:
        if not isinstance(item, Mapping):
            raise OffxmlMassAndChargeAssignmentError(
                "atom assignment row must be a mapping"
            )
        atom = dict(item)
        atom_digest = atom.pop("atom_assignment_sha256", None)
        if _sha256(atom) != atom_digest:
            raise OffxmlMassAndChargeAssignmentError(
                "atom assignment row digest is invalid"
            )
        if atom.get("mass_source_id") != OFFXML_REVIEWED_ATOMIC_WEIGHT_SOURCE_ID:
            raise OffxmlMassAndChargeAssignmentError(
                "atom assignment row names an unreviewed mass source"
            )
    return {**document, "assignment_sha256": declared}


def offxml_reviewed_atomic_weights() -> Mapping[int, float]:
    return dict(OFFXML_REVIEWED_STANDARD_ATOMIC_WEIGHTS_DA)


def offxml_library_charge_values(
    parameter: OffxmlSemanticParameter,
) -> Sequence[float]:
    return _library_charges(parameter)


__all__ = [
    "OFFXML_ATOM_ASSIGNMENT_SCHEMA_ID",
    "OFFXML_MASS_CHARGE_ASSIGNMENT_BLOCKERS",
    "OFFXML_MASS_CHARGE_ASSIGNMENT_CONFIGURATION",
    "OFFXML_MASS_CHARGE_ASSIGNMENT_CONFIGURATION_SHA256",
    "OFFXML_MASS_CHARGE_ASSIGNMENT_PROFILE_ID",
    "OFFXML_MASS_CHARGE_ASSIGNMENT_SCHEMA_ID",
    "OFFXML_MASS_CHARGE_ASSIGNMENT_VERSION",
    "OFFXML_MASS_CHARGE_LIBRARY_HANDLER",
    "OFFXML_MASS_CHARGE_MAX_ATOMS",
    "OFFXML_MASS_CHARGE_TOTAL_TOLERANCE_E",
    "OFFXML_REVIEWED_ATOMIC_WEIGHT_SOURCE_ID",
    "OFFXML_REVIEWED_STANDARD_ATOMIC_WEIGHTS_DA",
    "OffxmlAtomAssignment",
    "OffxmlMassAndChargeAssignment",
    "OffxmlMassAndChargeAssignmentError",
    "assign_offxml_masses_and_charges",
    "offxml_library_charge_values",
    "offxml_mass_and_charge_assignment_document",
    "offxml_reviewed_atomic_weights",
    "require_offxml_mass_and_charge_assignment_document",
]
