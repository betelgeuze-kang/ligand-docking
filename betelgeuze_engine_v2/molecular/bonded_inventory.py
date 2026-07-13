"""Exact-methane canonical bond/angle identity inventory.

This module is a contract-only bridge between V2-1 molecular identity and a
future V2-2 force field.  It enumerates graph identities for one deliberately
narrow source-bound methane profile.  It does not assign atom types,
parameters, equilibrium values, energies, forces, constraints, or simulation
authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import combinations
import json
from typing import Any

from .models import AllAtomSystem
from .profile_preparation import (
    PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_ID,
    ProfileLocalPreparationEvidenceReport,
    analyze_profile_local_preparation_evidence,
)


EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_VERSION = "1.0.0"
EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_ID = (
    "betelgeuze.exact_methane_bond_angle_inventory/"
    f"{EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_VERSION}"
)
EXACT_METHANE_BOND_ANGLE_PROFILE_ID = (
    "source_explicit_h_sdf_v2000_exact_methane_bond_angle_identity_v1"
)
EXACT_METHANE_BOND_ANGLE_CLAIM_SCOPE = (
    "canonical_graph_bond_and_angle_identity_only"
)
EXACT_METHANE_BOND_ANGLE_CONSTRAINT_CODES = (
    "upstream_applicability_valid",
    "canonical_state_valid",
    "canonical_ingest_supported",
    "profile_local_evidence_satisfied",
    "sdf_v2000_source_pedigree",
    "source_binding_self_consistent",
    "exact_atom_count",
    "exact_bond_count",
    "single_component",
    "single_nonpolymer_residue",
    "exact_element_counts",
    "formal_charges_known_zero",
    "isotopes_absent",
    "aromaticity_absent",
    "stereo_absent",
    "exact_source_observed_hydrogen_inventory",
    "exact_methane_graph",
)
EXACT_METHANE_BOND_ANGLE_INVENTORY_STATUSES = frozenset(
    {"invalid", "unsupported", "available"}
)

_SDF_V2000_PARSER_PEDIGREE = "betelgeuze.sdf_v2000_parser/1.5.0"
_MAX_JSON_INTEGER = (1 << 53) - 1
_NOT_ASSESSED = "not_assessed"
_ENUMERATED = "enumerated_from_canonical_graph"
_NOT_ENUMERATED = "not_enumerated"


def _validate_atom_index(name: str, value: Any) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0 or value > _MAX_JSON_INTEGER:
        raise ValueError(
            f"{name} must be a non-negative interoperable JSON integer"
        )


@dataclass(frozen=True, order=True)
class CanonicalBondIdentity:
    """One unordered canonical bond endpoint pair, with no parameters."""

    atom_i: int
    atom_j: int

    def __post_init__(self) -> None:
        _validate_atom_index("atom_i", self.atom_i)
        _validate_atom_index("atom_j", self.atom_j)
        if self.atom_i >= self.atom_j:
            raise ValueError("canonical bond identity requires atom_i < atom_j")

    def to_dict(self) -> dict[str, int]:
        return {"atom_i": self.atom_i, "atom_j": self.atom_j}


@dataclass(frozen=True, order=True)
class CanonicalAngleIdentity:
    """One undirected outer-center-outer graph angle, with no parameters."""

    outer_atom_i: int
    center_atom: int
    outer_atom_k: int

    def __post_init__(self) -> None:
        _validate_atom_index("outer_atom_i", self.outer_atom_i)
        _validate_atom_index("center_atom", self.center_atom)
        _validate_atom_index("outer_atom_k", self.outer_atom_k)
        if self.outer_atom_i >= self.outer_atom_k:
            raise ValueError(
                "canonical angle identity requires outer_atom_i < outer_atom_k"
            )
        if self.center_atom in (self.outer_atom_i, self.outer_atom_k):
            raise ValueError("canonical angle identity requires three atoms")

    def to_dict(self) -> dict[str, int]:
        return {
            "outer_atom_i": self.outer_atom_i,
            "center_atom": self.center_atom,
            "outer_atom_k": self.outer_atom_k,
        }


def _exact_methane_graph_identity(
    system: AllAtomSystem,
) -> tuple[
    bool,
    int | None,
    tuple[int, ...],
    tuple[tuple[int, int], ...],
]:
    atom_by_index = {atom.index: atom for atom in system.atoms}
    expected_indices = tuple(range(len(system.atoms)))
    if tuple(sorted(atom_by_index)) != expected_indices:
        return False, None, (), ()

    carbon_indices = tuple(
        sorted(
            atom.index
            for atom in system.atoms
            if atom.element == "C" and atom.atomic_number == 6
        )
    )
    hydrogen_indices = tuple(
        sorted(
            atom.index
            for atom in system.atoms
            if atom.element == "H" and atom.atomic_number == 1
        )
    )
    if len(carbon_indices) != 1 or len(hydrogen_indices) != 4:
        return False, None, (), ()

    edges: list[tuple[int, int]] = []
    degree = {index: 0 for index in expected_indices}
    seen: set[tuple[int, int]] = set()
    for bond in system.bonds:
        atom_i, atom_j = sorted((bond.atom_i, bond.atom_j))
        edge = (atom_i, atom_j)
        if (
            atom_i == atom_j
            or atom_i not in atom_by_index
            or atom_j not in atom_by_index
            or edge in seen
            or bond.order != 1.0
            or bond.aromatic
        ):
            return False, None, (), ()
        if {atom_by_index[atom_i].element, atom_by_index[atom_j].element} != {
            "C",
            "H",
        }:
            return False, None, (), ()
        seen.add(edge)
        edges.append(edge)
        degree[atom_i] += 1
        degree[atom_j] += 1

    carbon_index = carbon_indices[0]
    exact = bool(
        len(edges) == 4
        and degree[carbon_index] == 4
        and all(degree[index] == 1 for index in hydrogen_indices)
        and set(degree) == {carbon_index, *hydrogen_indices}
    )
    if not exact:
        return False, None, (), ()
    return True, carbon_index, hydrogen_indices, tuple(sorted(edges))


def _single_nonpolymer_residue(system: AllAtomSystem) -> bool:
    if len(system.residues) != 1:
        return False
    residue = system.residues[0]
    return bool(
        residue.entity_type == "non_polymer"
        and tuple(sorted(residue.atom_indices))
        == tuple(range(system.atom_count))
    )


def _constraint_results(
    system: AllAtomSystem,
    profile: ProfileLocalPreparationEvidenceReport,
    *,
    exact_graph: bool,
) -> tuple[tuple[str, bool], ...]:
    values = {
        "upstream_applicability_valid": (
            profile.canonical_ingest_status != "invalid"
        ),
        "canonical_state_valid": profile.canonical_state_valid,
        "canonical_ingest_supported": profile.canonical_ingest_supported,
        "profile_local_evidence_satisfied": (
            profile.profile_local_evidence_satisfied
        ),
        "sdf_v2000_source_pedigree": bool(
            profile.source_format == "sdf_v2000"
            and profile.parser_pedigree_id == _SDF_V2000_PARSER_PEDIGREE
        ),
        "source_binding_self_consistent": bool(
            profile.source_digest_available
            and profile.parser_observation_self_consistent
        ),
        "exact_atom_count": profile.atom_count == 5,
        "exact_bond_count": profile.bond_count == 4,
        "single_component": profile.component_count == 1,
        "single_nonpolymer_residue": _single_nonpolymer_residue(system),
        "exact_element_counts": bool(
            profile.carbon_atom_count == 1
            and profile.hydrogen_atom_count == 4
            and profile.atom_count == 5
        ),
        "formal_charges_known_zero": bool(
            profile.unknown_formal_charge_count == 0
            and profile.nonzero_formal_charge_count == 0
            and profile.formal_charge_observation_status
            == "source_observed_known_zero_not_assigned"
        ),
        "isotopes_absent": profile.isotope_count == 0,
        "aromaticity_absent": bool(
            profile.aromatic_atom_count == 0
            and profile.aromatic_bond_count == 0
        ),
        "stereo_absent": bool(
            profile.stereo_labeled_atom_count == 0
            and profile.stereo_labeled_bond_count == 0
        ),
        "exact_source_observed_hydrogen_inventory": bool(
            profile.source_observed_hydrogen_count == 4
            and profile.adapter_generated_hydrogen_count == 0
            and profile.unknown_hydrogen_origin_count == 0
            and profile.source_hydrogen_inventory_status
            == "complete_relative_to_parsed_source"
        ),
        "exact_methane_graph": exact_graph,
    }
    return tuple((code, values[code]) for code in EXACT_METHANE_BOND_ANGLE_CONSTRAINT_CODES)


def _inventory_status(
    profile: ProfileLocalPreparationEvidenceReport,
    constraint_results: tuple[tuple[str, bool], ...],
) -> str:
    if profile.canonical_ingest_status == "invalid":
        return "invalid"
    if any(not passed for _, passed in constraint_results):
        return "unsupported"
    return "available"


def _blockers(
    status: str,
    failed_constraint_codes: tuple[str, ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if status == "invalid":
        blockers.append("bond_angle_inventory_state_invalid")
    elif status == "unsupported":
        blockers.append("exact_methane_bond_angle_inventory_unsupported")
    blockers.extend(
        f"bond_angle_inventory_constraint_failed_{code}"
        for code in failed_constraint_codes
    )
    blockers.extend(
        (
            "source_digest_is_not_authentication",
            "bond_parameters_not_assigned",
            "angle_parameters_not_assigned",
            "proper_torsion_identity_not_assessed",
            "improper_identity_not_assessed",
            "constraint_identity_not_assessed",
            "preparation_not_ready",
            "parameterability_not_assessed",
            "energy_evaluation_not_authorized",
            "force_evaluation_not_authorized",
            "minimization_not_authorized",
            "simulation_not_authorized",
            "claim_not_authorized",
        )
    )
    return tuple(blockers)


@dataclass(frozen=True, init=False)
class ExactMethaneBondAngleInventoryReport:
    """Factory-only graph-identity report for exact source-bound methane."""

    profile_local_preparation_report: ProfileLocalPreparationEvidenceReport
    constraint_results: tuple[tuple[str, bool], ...]
    inventory_status: str
    carbon_atom_index: int | None
    hydrogen_atom_indices: tuple[int, ...]
    bond_identities: tuple[CanonicalBondIdentity, ...]
    angle_identities: tuple[CanonicalAngleIdentity, ...]

    def __init__(self, system: AllAtomSystem) -> None:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        profile = analyze_profile_local_preparation_evidence(system)
        exact_graph, carbon_index, hydrogen_indices, edges = (
            _exact_methane_graph_identity(system)
        )
        constraint_results = _constraint_results(
            system,
            profile,
            exact_graph=exact_graph,
        )
        status = _inventory_status(profile, constraint_results)
        if status == "available":
            assert carbon_index is not None
            bond_identities = tuple(
                CanonicalBondIdentity(*edge) for edge in edges
            )
            angle_identities = tuple(
                CanonicalAngleIdentity(atom_i, carbon_index, atom_k)
                for atom_i, atom_k in combinations(hydrogen_indices, 2)
            )
            exposed_carbon_index = carbon_index
            exposed_hydrogen_indices = hydrogen_indices
        else:
            bond_identities = ()
            angle_identities = ()
            exposed_carbon_index = None
            exposed_hydrogen_indices = ()
        object.__setattr__(self, "profile_local_preparation_report", profile)
        object.__setattr__(self, "constraint_results", constraint_results)
        object.__setattr__(self, "inventory_status", status)
        object.__setattr__(self, "carbon_atom_index", exposed_carbon_index)
        object.__setattr__(
            self,
            "hydrogen_atom_indices",
            exposed_hydrogen_indices,
        )
        object.__setattr__(self, "bond_identities", bond_identities)
        object.__setattr__(self, "angle_identities", angle_identities)
        self._validate()

    def _validate(self) -> None:
        if type(self.profile_local_preparation_report) is not (
            ProfileLocalPreparationEvidenceReport
        ):
            raise TypeError(
                "profile_local_preparation_report must be a factory report"
            )
        if (
            tuple(code for code, _ in self.constraint_results)
            != EXACT_METHANE_BOND_ANGLE_CONSTRAINT_CODES
            or not all(
                type(code) is str and type(passed) is bool
                for code, passed in self.constraint_results
            )
        ):
            raise ValueError("constraint_results must match the fixed schema")
        expected_status = _inventory_status(
            self.profile_local_preparation_report,
            self.constraint_results,
        )
        if self.inventory_status != expected_status:
            raise ValueError("inventory_status must match the constraints")
        if self.inventory_status not in (
            EXACT_METHANE_BOND_ANGLE_INVENTORY_STATUSES
        ):
            raise ValueError("unknown inventory status")
        if self.inventory_status == "available":
            if type(self.carbon_atom_index) is not int:
                raise TypeError("available inventory requires a carbon index")
            if len(self.hydrogen_atom_indices) != 4:
                raise ValueError("available inventory requires four hydrogens")
            expected_bonds = tuple(
                sorted(
                    CanonicalBondIdentity(
                        min(self.carbon_atom_index, hydrogen_index),
                        max(self.carbon_atom_index, hydrogen_index),
                    )
                    for hydrogen_index in self.hydrogen_atom_indices
                )
            )
            expected_angles = tuple(
                CanonicalAngleIdentity(atom_i, self.carbon_atom_index, atom_k)
                for atom_i, atom_k in combinations(
                    self.hydrogen_atom_indices,
                    2,
                )
            )
            if self.bond_identities != expected_bonds:
                raise ValueError("bond identities must be canonical and exact")
            if self.angle_identities != expected_angles:
                raise ValueError("angle identities must be canonical and exact")
        elif any(
            (
                self.carbon_atom_index is not None,
                bool(self.hydrogen_atom_indices),
                bool(self.bond_identities),
                bool(self.angle_identities),
            )
        ):
            raise ValueError("unavailable inventories cannot expose term identities")

    @property
    def profile_id(self) -> str:
        return EXACT_METHANE_BOND_ANGLE_PROFILE_ID

    @property
    def claim_scope(self) -> str:
        return EXACT_METHANE_BOND_ANGLE_CLAIM_SCOPE

    @property
    def system_schema_id(self) -> str:
        return self.profile_local_preparation_report.system_schema_id

    @property
    def canonical_topology_schema_id(self) -> str:
        return self.profile_local_preparation_report.canonical_topology_schema_id

    @property
    def canonical_topology_sha256(self) -> str | None:
        return self.profile_local_preparation_report.canonical_topology_sha256

    @property
    def source_format(self) -> str:
        return self.profile_local_preparation_report.source_format

    @property
    def source_sha256(self) -> str | None:
        return self.profile_local_preparation_report.source_sha256

    @property
    def parser_pedigree_id(self) -> str:
        return self.profile_local_preparation_report.parser_pedigree_id

    @property
    def source_authentication_status(self) -> str:
        return self.profile_local_preparation_report.source_authentication_status

    @property
    def applicability_report_sha256(self) -> str:
        return self.profile_local_preparation_report.applicability_report_sha256

    @property
    def profile_local_preparation_report_sha256(self) -> str:
        return self.profile_local_preparation_report.report_sha256

    @property
    def failed_constraint_codes(self) -> tuple[str, ...]:
        return tuple(
            code for code, passed in self.constraint_results if not passed
        )

    @property
    def bond_identity_status(self) -> str:
        return _ENUMERATED if self.inventory_status == "available" else _NOT_ENUMERATED

    @property
    def angle_identity_status(self) -> str:
        return _ENUMERATED if self.inventory_status == "available" else _NOT_ENUMERATED

    @property
    def proper_torsion_identity_status(self) -> str:
        return _NOT_ASSESSED

    @property
    def improper_identity_status(self) -> str:
        return _NOT_ASSESSED

    @property
    def constraint_identity_status(self) -> str:
        return _NOT_ASSESSED

    @property
    def preparation_ready(self) -> bool:
        return False

    @property
    def parameter_set_id(self) -> None:
        return None

    @property
    def parameter_assignment_sha256(self) -> None:
        return None

    @property
    def parameterability_assessed(self) -> bool:
        return False

    @property
    def parameterizable(self) -> bool:
        return False

    @property
    def physics_supported(self) -> bool:
        return False

    @property
    def energy_evaluation_authorized(self) -> bool:
        return False

    @property
    def force_evaluation_authorized(self) -> bool:
        return False

    @property
    def minimization_authorized(self) -> bool:
        return False

    @property
    def simulation_ready(self) -> bool:
        return False

    @property
    def claim_safe(self) -> bool:
        return False

    @property
    def blockers(self) -> tuple[str, ...]:
        return _blockers(self.inventory_status, self.failed_constraint_codes)

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_ID,
            "schema_version": EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_VERSION,
            "profile_id": self.profile_id,
            "claim_scope": self.claim_scope,
            "system_schema_id": self.system_schema_id,
            "canonical_topology_schema_id": self.canonical_topology_schema_id,
            "canonical_topology_sha256": self.canonical_topology_sha256,
            "source_format": self.source_format,
            "source_sha256": self.source_sha256,
            "parser_pedigree_id": self.parser_pedigree_id,
            "source_authentication_status": self.source_authentication_status,
            "applicability_report_sha256": self.applicability_report_sha256,
            "profile_local_preparation_schema_id": (
                PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_ID
            ),
            "profile_local_preparation_report_sha256": (
                self.profile_local_preparation_report_sha256
            ),
            "constraint_results": [
                {"code": code, "passed": passed}
                for code, passed in self.constraint_results
            ],
            "failed_constraint_codes": list(self.failed_constraint_codes),
            "inventory_status": self.inventory_status,
            "carbon_atom_index": self.carbon_atom_index,
            "hydrogen_atom_indices": list(self.hydrogen_atom_indices),
            "bond_identity_status": self.bond_identity_status,
            "bond_identities": [term.to_dict() for term in self.bond_identities],
            "angle_identity_status": self.angle_identity_status,
            "angle_identities": [term.to_dict() for term in self.angle_identities],
            "proper_torsion_identity_status": (
                self.proper_torsion_identity_status
            ),
            "improper_identity_status": self.improper_identity_status,
            "constraint_identity_status": self.constraint_identity_status,
            "preparation_ready": self.preparation_ready,
            "parameter_set_id": self.parameter_set_id,
            "parameter_assignment_sha256": self.parameter_assignment_sha256,
            "parameterability_assessed": self.parameterability_assessed,
            "parameterizable": self.parameterizable,
            "physics_supported": self.physics_supported,
            "energy_evaluation_authorized": self.energy_evaluation_authorized,
            "force_evaluation_authorized": self.force_evaluation_authorized,
            "minimization_authorized": self.minimization_authorized,
            "simulation_ready": self.simulation_ready,
            "claim_safe": self.claim_safe,
            "blockers": list(self.blockers),
        }

    @property
    def report_sha256(self) -> str:
        payload = json.dumps(
            self._core_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        payload = self._core_dict()
        payload["report_sha256"] = self.report_sha256
        return payload

    def matches_system(self, system: AllAtomSystem) -> bool:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        return self.to_dict() == analyze_exact_methane_bond_angle_inventory(
            system
        ).to_dict()


def analyze_exact_methane_bond_angle_inventory(
    system: AllAtomSystem,
) -> ExactMethaneBondAngleInventoryReport:
    """Enumerate exact-methane bond/angle graph identities only."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    return ExactMethaneBondAngleInventoryReport(system)


__all__ = [
    "CanonicalAngleIdentity",
    "CanonicalBondIdentity",
    "EXACT_METHANE_BOND_ANGLE_CLAIM_SCOPE",
    "EXACT_METHANE_BOND_ANGLE_CONSTRAINT_CODES",
    "EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_ID",
    "EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_VERSION",
    "EXACT_METHANE_BOND_ANGLE_INVENTORY_STATUSES",
    "EXACT_METHANE_BOND_ANGLE_PROFILE_ID",
    "ExactMethaneBondAngleInventoryReport",
    "analyze_exact_methane_bond_angle_inventory",
]
