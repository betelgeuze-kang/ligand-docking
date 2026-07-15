"""Fail-closed canonical-ingest applicability for one explicit chemistry slice.

This module does not assign force-field parameters and does not authorize
simulation.  It answers a narrower V2-1 question: whether a source-bound
canonical graph exactly matches a versioned ingest profile whose constraints
can be checked from typed state alone.  The first profile accepts only one
connected, source-observed-explicit-H, neutral, non-isotopic, stereo-unassigned,
acyclic, saturated hydrocarbon graph.

Source and parser-observation digests provide deterministic internal binding,
not authentication.  Preparation, electronic state, parameterability,
simulation readiness, and scientific claims remain independently blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID

from .chemistry import (
    CHEMISTRY_COVERAGE_SCHEMA_VERSION,
    ChemistryCoverageReport,
    analyze_canonical_chemistry,
)
from .models import AllAtomSystem
from .preparation import (
    PREPARATION_REPORT_SCHEMA_VERSION,
    MolecularPreparationReport,
    analyze_molecular_preparation,
)
from .topology import CANONICAL_TOPOLOGY_SCHEMA_ID


CANONICAL_INGEST_APPLICABILITY_SCHEMA_VERSION = "1.0.0"
CANONICAL_INGEST_APPLICABILITY_SCHEMA_ID = (
    "betelgeuze.canonical_ingest_applicability/"
    f"{CANONICAL_INGEST_APPLICABILITY_SCHEMA_VERSION}"
)
EXPLICIT_NEUTRAL_ACYCLIC_SATURATED_HYDROCARBON_PROFILE_ID = (
    "source_explicit_h_neutral_nonisotopic_stereo_unassigned_"
    "acyclic_saturated_hydrocarbon_ingest_v1"
)
CANONICAL_INGEST_CLAIM_SCOPE = "canonical_ingest_only"
SOURCE_AUTHENTICATION_STATUS = "digest_bound_not_authenticated"
PARAMETERABILITY_STATUS = "not_assessed_no_parameter_set"

_MAX_JSON_INTEGER = (1 << 53) - 1
_IDENTITY_CONSTRAINT_CODES = (
    "system_schema_supported",
    "canonical_state_valid",
    "graph_representable",
    "canonical_topology_digest_available",
    "source_digest_available",
    "recognized_parser_pedigree",
    "parser_observation_self_consistent",
)
_CHEMISTRY_CONSTRAINT_CODES = (
    "single_component",
    "contains_carbon",
    "elements_h_c_only",
    "formal_charges_known_zero",
    "isotopes_absent",
    "aromaticity_absent",
    "single_bonds_only",
    "stereo_absent",
    "acyclic_graph",
    "explicit_valence_closed",
    "hydrogens_source_observed",
)
CANONICAL_INGEST_CONSTRAINT_CODES = (
    *_IDENTITY_CONSTRAINT_CODES,
    *_CHEMISTRY_CONSTRAINT_CODES,
)
_RECOGNIZED_PARSER_PEDIGREES = frozenset(
    {
        ("pdb", "betelgeuze.pdb_parser/1.8.0"),
        ("mmcif", "betelgeuze.mmcif_parser/1.9.0"),
        (
            "mmcif",
            "betelgeuze.mmcif_nonpoly_component_topology_parser/1.0.0",
        ),
        (
            "mmcif",
            "betelgeuze.mmcif_nonpoly_covalent_struct_conn_topology_parser/1.0.0",
        ),
        (
            "mmcif",
            "betelgeuze.mmcif_polymer_component_topology_parser/1.0.0",
        ),
        (
            "mmcif",
            "betelgeuze.mmcif_archive_standard_l_peptide_topology_parser/1.0.0",
        ),
        ("sdf_v2000", "betelgeuze.sdf_v2000_parser/1.5.0"),
        ("smiles", "betelgeuze.smiles_parser/1.4.0"),
    }
)


def _is_lowercase_sha256(value: Any) -> bool:
    return bool(
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _expected_ingest_status(
    constraint_results: tuple[tuple[str, bool], ...],
) -> str:
    values = dict(constraint_results)
    if any(not values[code] for code in _IDENTITY_CONSTRAINT_CODES):
        return "invalid"
    if any(not values[code] for code in _CHEMISTRY_CONSTRAINT_CODES):
        return "unsupported"
    return "supported"


def _expected_blockers(
    *,
    canonical_ingest_status: str,
    failed_constraint_codes: tuple[str, ...],
    preparation_status: str,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if canonical_ingest_status == "invalid":
        blockers.append("canonical_ingest_state_invalid")
    elif canonical_ingest_status == "unsupported":
        blockers.append("canonical_ingest_profile_unsupported")
    blockers.extend(
        f"canonical_ingest_constraint_failed_{code}" for code in failed_constraint_codes
    )
    if preparation_status != "attested":
        blockers.append("preparation_not_ready")
    blockers.extend(
        (
            "source_digest_is_not_authentication",
            "electronic_state_not_typed",
            "parameter_set_not_declared",
            "parameterability_not_assessed",
            "simulation_not_authorized",
            "claim_not_authorized",
        )
    )
    return tuple(blockers)


@dataclass(frozen=True)
class CanonicalIngestApplicabilityReport:
    """Topology- and audit-bound decision for one narrow ingest profile."""

    profile_id: str
    claim_scope: str
    system_schema_id: str
    canonical_topology_schema_id: str
    canonical_topology_sha256: str | None
    canonical_topology_digest_available: bool
    chemistry_coverage_schema_version: str
    chemistry_coverage_report_sha256: str
    preparation_report_schema_version: str
    preparation_report_sha256: str
    source_format: str
    source_sha256: str | None
    source_digest_available: bool
    parser_pedigree_id: str
    parser_observation_self_consistent: bool
    source_authentication_status: str
    canonical_state_valid: bool
    graph_representable: bool
    atom_count: int
    bond_count: int
    component_count: int
    carbon_atom_count: int
    hydrogen_atom_count: int
    source_observed_hydrogen_count: int
    adapter_generated_hydrogen_count: int
    unknown_hydrogen_origin_count: int
    unknown_formal_charge_count: int
    nonzero_formal_charge_count: int
    isotope_count: int
    aromatic_atom_count: int
    aromatic_bond_count: int
    non_single_bond_count: int
    stereo_labeled_atom_count: int
    stereo_labeled_bond_count: int
    valence_violation_count: int
    constraint_results: tuple[tuple[str, bool], ...]
    failed_constraint_codes: tuple[str, ...]
    canonical_ingest_status: str
    canonical_ingest_supported: bool
    preparation_status: str
    preparation_ready: bool
    parameterability_status: str
    parameter_set_id: None
    parameter_assignment_sha256: None
    blockers: tuple[str, ...]
    parameterability_assessed: bool = False
    parameterizable: bool = False
    simulation_ready: bool = False
    claim_safe: bool = False

    def __post_init__(self) -> None:
        if self.profile_id != (
            EXPLICIT_NEUTRAL_ACYCLIC_SATURATED_HYDROCARBON_PROFILE_ID
        ):
            raise ValueError("applicability v1 requires the fixed ingest profile")
        if self.claim_scope != CANONICAL_INGEST_CLAIM_SCOPE:
            raise ValueError("applicability v1 is canonical-ingest-only")
        if type(self.system_schema_id) is not str or not self.system_schema_id:
            raise TypeError("system_schema_id must be a nonempty string")
        if self.canonical_topology_schema_id != CANONICAL_TOPOLOGY_SCHEMA_ID:
            raise ValueError("applicability v1 requires the fixed topology schema")
        if self.chemistry_coverage_schema_version != (
            CHEMISTRY_COVERAGE_SCHEMA_VERSION
        ):
            raise ValueError("chemistry coverage schema version mismatch")
        if self.preparation_report_schema_version != (
            PREPARATION_REPORT_SCHEMA_VERSION
        ):
            raise ValueError("preparation report schema version mismatch")
        for name in (
            "chemistry_coverage_report_sha256",
            "preparation_report_sha256",
        ):
            if not _is_lowercase_sha256(getattr(self, name)):
                raise ValueError(f"{name} must be a lowercase SHA-256")
        if self.canonical_topology_digest_available != (
            self.canonical_topology_sha256 is not None
        ):
            raise ValueError(
                "canonical_topology_digest_available must match the topology digest"
            )
        if self.canonical_topology_sha256 is not None and not _is_lowercase_sha256(
            self.canonical_topology_sha256
        ):
            raise ValueError(
                "canonical_topology_sha256 must be a lowercase SHA-256 or None"
            )
        if self.source_digest_available != (self.source_sha256 is not None):
            raise ValueError("source_digest_available must match source_sha256")
        if self.source_sha256 is not None and not _is_lowercase_sha256(
            self.source_sha256
        ):
            raise ValueError("source_sha256 must be a lowercase SHA-256 or None")
        for name in ("source_format", "parser_pedigree_id"):
            if type(getattr(self, name)) is not str:
                raise TypeError(f"{name} must be a string")
        if self.source_authentication_status != SOURCE_AUTHENTICATION_STATUS:
            raise ValueError("source authentication must remain explicitly unproven")
        boolean_fields = {
            "canonical_topology_digest_available": (
                self.canonical_topology_digest_available
            ),
            "source_digest_available": self.source_digest_available,
            "parser_observation_self_consistent": (
                self.parser_observation_self_consistent
            ),
            "canonical_state_valid": self.canonical_state_valid,
            "graph_representable": self.graph_representable,
            "canonical_ingest_supported": self.canonical_ingest_supported,
            "preparation_ready": self.preparation_ready,
            "parameterability_assessed": self.parameterability_assessed,
            "parameterizable": self.parameterizable,
            "simulation_ready": self.simulation_ready,
            "claim_safe": self.claim_safe,
        }
        invalid_boolean = next(
            (name for name, value in boolean_fields.items() if type(value) is not bool),
            None,
        )
        if invalid_boolean is not None:
            raise TypeError(f"{invalid_boolean} must be a boolean")
        for name in (
            "atom_count",
            "bond_count",
            "component_count",
            "carbon_atom_count",
            "hydrogen_atom_count",
            "source_observed_hydrogen_count",
            "adapter_generated_hydrogen_count",
            "unknown_hydrogen_origin_count",
            "unknown_formal_charge_count",
            "nonzero_formal_charge_count",
            "isotope_count",
            "aromatic_atom_count",
            "aromatic_bond_count",
            "non_single_bond_count",
            "stereo_labeled_atom_count",
            "stereo_labeled_bond_count",
            "valence_violation_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise TypeError(f"{name} must be a non-negative integer")
            if value > _MAX_JSON_INTEGER:
                raise ValueError(f"{name} exceeds the interoperable JSON integer range")
        if self.carbon_atom_count + self.hydrogen_atom_count > self.atom_count:
            raise ValueError("profile element counts cannot exceed atom_count")
        if self.valence_violation_count > self.atom_count:
            raise ValueError("valence_violation_count cannot exceed atom_count")
        atom_subset_counts = (
            self.unknown_formal_charge_count,
            self.nonzero_formal_charge_count,
            self.isotope_count,
            self.aromatic_atom_count,
            self.stereo_labeled_atom_count,
        )
        if any(count > self.atom_count for count in atom_subset_counts):
            raise ValueError("atom diagnostic counts cannot exceed atom_count")
        if (
            self.unknown_formal_charge_count + self.nonzero_formal_charge_count
            > self.atom_count
        ):
            raise ValueError("unknown and nonzero formal-charge counts cannot overlap")
        bond_subset_counts = (
            self.aromatic_bond_count,
            self.non_single_bond_count,
            self.stereo_labeled_bond_count,
        )
        if any(count > self.bond_count for count in bond_subset_counts):
            raise ValueError("bond diagnostic counts cannot exceed bond_count")
        if self.aromatic_bond_count > self.non_single_bond_count:
            raise ValueError("aromatic_bond_count cannot exceed non_single_bond_count")
        if (
            self.source_observed_hydrogen_count
            + self.adapter_generated_hydrogen_count
            + self.unknown_hydrogen_origin_count
            != self.hydrogen_atom_count
        ):
            raise ValueError("hydrogen origin counts must sum to hydrogen_atom_count")
        if self.component_count > self.atom_count or (
            self.atom_count > 0 and self.component_count < 1
        ):
            raise ValueError("component_count must be consistent with atom_count")
        if type(self.constraint_results) is not tuple or not all(
            type(entry) is tuple
            and len(entry) == 2
            and type(entry[0]) is str
            and type(entry[1]) is bool
            for entry in self.constraint_results
        ):
            raise TypeError(
                "constraint_results entries must be immutable string/boolean pairs"
            )
        if (
            tuple(code for code, _ in self.constraint_results)
            != CANONICAL_INGEST_CONSTRAINT_CODES
        ):
            raise ValueError(
                "constraint_results must exactly match the ordered v1 constraints"
            )
        expected_failed = tuple(
            code for code, passed in self.constraint_results if not passed
        )
        if self.failed_constraint_codes != expected_failed:
            raise ValueError(
                "failed_constraint_codes must exactly match constraint_results"
            )
        expected_status = _expected_ingest_status(self.constraint_results)
        if self.canonical_ingest_status != expected_status:
            raise ValueError(
                "canonical_ingest_status must match the constraint results"
            )
        if self.canonical_ingest_supported != (expected_status == "supported"):
            raise ValueError(
                "canonical_ingest_supported must match canonical_ingest_status"
            )
        constraint_values = dict(self.constraint_results)
        derived_constraint_values = {
            "system_schema_supported": self.system_schema_id == ALL_ATOM_SCHEMA_ID,
            "canonical_state_valid": self.canonical_state_valid,
            "graph_representable": self.graph_representable,
            "canonical_topology_digest_available": (
                self.canonical_topology_digest_available
            ),
            "source_digest_available": self.source_digest_available,
            "recognized_parser_pedigree": (
                (self.source_format, self.parser_pedigree_id)
                in _RECOGNIZED_PARSER_PEDIGREES
            ),
            "parser_observation_self_consistent": (
                self.parser_observation_self_consistent
            ),
            "single_component": self.component_count == 1,
            "contains_carbon": self.carbon_atom_count > 0,
            "elements_h_c_only": (
                self.carbon_atom_count + self.hydrogen_atom_count == self.atom_count
            ),
            "formal_charges_known_zero": (
                self.unknown_formal_charge_count == 0
                and self.nonzero_formal_charge_count == 0
            ),
            "isotopes_absent": self.isotope_count == 0,
            "aromaticity_absent": (
                self.aromatic_atom_count == 0 and self.aromatic_bond_count == 0
            ),
            "single_bonds_only": self.non_single_bond_count == 0,
            "stereo_absent": (
                self.stereo_labeled_atom_count == 0
                and self.stereo_labeled_bond_count == 0
            ),
            "acyclic_graph": bool(
                constraint_values["graph_representable"]
                and self.component_count == 1
                and self.atom_count > 0
                and self.bond_count == self.atom_count - 1
            ),
            "explicit_valence_closed": bool(
                constraint_values["graph_representable"]
                and self.valence_violation_count == 0
            ),
            "hydrogens_source_observed": (
                self.source_observed_hydrogen_count == self.hydrogen_atom_count
                and self.adapter_generated_hydrogen_count == 0
                and self.unknown_hydrogen_origin_count == 0
            ),
        }
        if any(
            constraint_values[code] != value
            for code, value in derived_constraint_values.items()
        ):
            raise ValueError(
                "constraint_results disagree with report identity or counts"
            )
        if (
            constraint_values["explicit_valence_closed"]
            and constraint_values["single_bonds_only"]
            and (
                4 * self.carbon_atom_count + self.hydrogen_atom_count
                != 2 * self.bond_count
            )
        ):
            raise ValueError(
                "explicit valence closure disagrees with the graph degree sum"
            )
        canonical_state_valid = dict(self.constraint_results)["canonical_state_valid"]
        expected_preparation_status = (
            "incomplete" if canonical_state_valid else "invalid"
        )
        if self.preparation_status != expected_preparation_status:
            raise ValueError(
                "preparation_status must remain invalid or incomplete in v1"
            )
        if self.preparation_ready:
            raise ValueError("preparation_ready cannot be promoted in v1")
        if self.parameterability_status != PARAMETERABILITY_STATUS:
            raise ValueError("parameterability status cannot be promoted in v1")
        if self.parameter_set_id is not None:
            raise ValueError("parameter_set_id must remain None in v1")
        if self.parameter_assignment_sha256 is not None:
            raise ValueError("parameter_assignment_sha256 must remain None in v1")
        expected_blockers = _expected_blockers(
            canonical_ingest_status=self.canonical_ingest_status,
            failed_constraint_codes=self.failed_constraint_codes,
            preparation_status=self.preparation_status,
        )
        if self.blockers != expected_blockers:
            raise ValueError("blockers must exactly match the ordered v1 blockers")
        if (
            self.parameterability_assessed
            or self.parameterizable
            or self.simulation_ready
            or self.claim_safe
        ):
            raise ValueError(
                "applicability v1 cannot promote parameterability, simulation, or claims"
            )

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": CANONICAL_INGEST_APPLICABILITY_SCHEMA_ID,
            "schema_version": CANONICAL_INGEST_APPLICABILITY_SCHEMA_VERSION,
            "profile_id": self.profile_id,
            "claim_scope": self.claim_scope,
            "system_schema_id": self.system_schema_id,
            "canonical_topology_schema_id": self.canonical_topology_schema_id,
            "canonical_topology_sha256": self.canonical_topology_sha256,
            "canonical_topology_digest_available": (
                self.canonical_topology_digest_available
            ),
            "chemistry_coverage_schema_version": (
                self.chemistry_coverage_schema_version
            ),
            "chemistry_coverage_report_sha256": (self.chemistry_coverage_report_sha256),
            "preparation_report_schema_version": (
                self.preparation_report_schema_version
            ),
            "preparation_report_sha256": self.preparation_report_sha256,
            "source_format": self.source_format,
            "source_sha256": self.source_sha256,
            "source_digest_available": self.source_digest_available,
            "parser_pedigree_id": self.parser_pedigree_id,
            "parser_observation_self_consistent": (
                self.parser_observation_self_consistent
            ),
            "source_authentication_status": self.source_authentication_status,
            "canonical_state_valid": self.canonical_state_valid,
            "graph_representable": self.graph_representable,
            "atom_count": self.atom_count,
            "bond_count": self.bond_count,
            "component_count": self.component_count,
            "carbon_atom_count": self.carbon_atom_count,
            "hydrogen_atom_count": self.hydrogen_atom_count,
            "source_observed_hydrogen_count": (self.source_observed_hydrogen_count),
            "adapter_generated_hydrogen_count": (self.adapter_generated_hydrogen_count),
            "unknown_hydrogen_origin_count": (self.unknown_hydrogen_origin_count),
            "unknown_formal_charge_count": self.unknown_formal_charge_count,
            "nonzero_formal_charge_count": self.nonzero_formal_charge_count,
            "isotope_count": self.isotope_count,
            "aromatic_atom_count": self.aromatic_atom_count,
            "aromatic_bond_count": self.aromatic_bond_count,
            "non_single_bond_count": self.non_single_bond_count,
            "stereo_labeled_atom_count": self.stereo_labeled_atom_count,
            "stereo_labeled_bond_count": self.stereo_labeled_bond_count,
            "valence_violation_count": self.valence_violation_count,
            "constraint_results": [
                {"code": code, "passed": passed}
                for code, passed in self.constraint_results
            ],
            "failed_constraint_codes": list(self.failed_constraint_codes),
            "canonical_ingest_status": self.canonical_ingest_status,
            "canonical_ingest_supported": self.canonical_ingest_supported,
            "preparation_status": self.preparation_status,
            "preparation_ready": self.preparation_ready,
            "parameterability_status": self.parameterability_status,
            "parameter_set_id": self.parameter_set_id,
            "parameter_assignment_sha256": self.parameter_assignment_sha256,
            "parameterability_assessed": self.parameterability_assessed,
            "parameterizable": self.parameterizable,
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
        return (
            self.to_dict() == analyze_canonical_ingest_applicability(system).to_dict()
        )


class CanonicalIngestApplicabilityError(RuntimeError):
    """Raised when canonical ingest is required outside the fixed profile."""

    def __init__(self, report: CanonicalIngestApplicabilityReport):
        self.report = report
        self.failed_constraint_codes = report.failed_constraint_codes
        preview = ", ".join(self.failed_constraint_codes[:6]) or "unknown"
        suffix = (
            ""
            if len(self.failed_constraint_codes) <= 6
            else f", +{len(self.failed_constraint_codes) - 6} more"
        )
        super().__init__(
            f"canonical ingest is not supported by the fixed profile: {preview}{suffix}"
        )


def _profile_constraint_results(
    system: AllAtomSystem,
    chemistry: ChemistryCoverageReport,
    preparation: MolecularPreparationReport,
    *,
    valence_violation_count: int,
) -> tuple[tuple[str, bool], ...]:
    atom_count = len(system.atoms)
    valence_closed = chemistry.graph_representable and valence_violation_count == 0
    stereo_absent = all(
        atom.stereo.strip().upper() in {"", "NONE", "UNSPECIFIED"}
        for atom in system.atoms
    ) and all(
        bond.stereo.strip().upper() in {"", "NONE", "UNSPECIFIED"}
        for bond in system.bonds
    )
    graph_representable = chemistry.graph_representable
    single_component = chemistry.component_count == 1
    acyclic_graph = bool(
        graph_representable
        and single_component
        and atom_count > 0
        and len(system.bonds) == atom_count - 1
    )
    values = {
        "system_schema_supported": system.schema_id == ALL_ATOM_SCHEMA_ID,
        "canonical_state_valid": chemistry.canonical_validation_valid,
        "graph_representable": graph_representable,
        "canonical_topology_digest_available": (
            chemistry.canonical_topology_digest_available
        ),
        "source_digest_available": preparation.source_digest_available,
        "recognized_parser_pedigree": (
            (preparation.source_format, preparation.parser_pedigree_id)
            in _RECOGNIZED_PARSER_PEDIGREES
        ),
        "parser_observation_self_consistent": (
            preparation.parser_observation_self_consistent
        ),
        "single_component": single_component,
        "contains_carbon": any(atom.element == "C" for atom in system.atoms),
        "elements_h_c_only": all(atom.element in {"H", "C"} for atom in system.atoms),
        "formal_charges_known_zero": all(
            atom.formal_charge_known and atom.formal_charge == 0
            for atom in system.atoms
        ),
        "isotopes_absent": chemistry.isotope_count == 0,
        "aromaticity_absent": (
            chemistry.aromatic_atom_count == 0 and chemistry.aromatic_bond_count == 0
        ),
        "single_bonds_only": all(
            bond.order == 1.0 and not bond.aromatic for bond in system.bonds
        ),
        "stereo_absent": stereo_absent,
        "acyclic_graph": acyclic_graph,
        "explicit_valence_closed": valence_closed,
        "hydrogens_source_observed": (
            preparation.metadata_observed_source_hydrogen_count
            == sum(atom.element == "H" for atom in system.atoms)
            and preparation.adapter_generated_hydrogen_count == 0
            and preparation.unknown_hydrogen_origin_count == 0
        ),
    }
    return tuple((code, values[code]) for code in CANONICAL_INGEST_CONSTRAINT_CODES)


def _profile_valence_violation_count(system: AllAtomSystem) -> int:
    valence_sums = [0.0] * len(system.atoms)
    for bond in system.bonds:
        if not (0 <= bond.atom_i < bond.atom_j < len(system.atoms)):
            continue
        valence_sums[bond.atom_i] += bond.order
        valence_sums[bond.atom_j] += bond.order
    violation_count = sum(
        atom.element not in {"H", "C"}
        or valence_sum != (1.0 if atom.element == "H" else 4.0)
        for atom, valence_sum in zip(
            system.atoms,
            valence_sums,
            strict=True,
        )
    )
    return violation_count


def _analyze_canonical_ingest_bundle(
    system: AllAtomSystem,
) -> tuple[
    ChemistryCoverageReport,
    MolecularPreparationReport,
    CanonicalIngestApplicabilityReport,
]:
    """Analyze one system once and return its three mutually bound reports."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    preparation = analyze_molecular_preparation(system)
    chemistry = analyze_canonical_chemistry(system)
    if (
        chemistry.system_schema_id != system.schema_id
        or chemistry.atom_count != len(system.atoms)
        or chemistry.bond_count != len(system.bonds)
        or preparation.system_schema_id != system.schema_id
        or preparation.atom_count != len(system.atoms)
        or preparation.bond_count != len(system.bonds)
        or preparation.source_format != system.provenance.source_format
        or chemistry.canonical_validation_valid
        != preparation.canonical_validation_valid
        or chemistry.element_counts != preparation.element_counts
        or chemistry.unknown_formal_charge_count
        != preparation.unknown_formal_charge_count
        or chemistry.net_formal_charge != preparation.net_formal_charge
        or chemistry.aromatic_atom_count != preparation.observed_aromatic_atom_count
        or chemistry.aromatic_bond_count != preparation.observed_aromatic_bond_count
    ):
        raise ValueError(
            "chemistry and preparation reports must describe the same system"
        )
    if chemistry.canonical_validation_valid and (
        chemistry.canonical_topology_schema_id
        != preparation.canonical_topology_schema_id
        or chemistry.canonical_topology_sha256 != preparation.canonical_topology_sha256
        or chemistry.canonical_topology_digest_available
        != preparation.canonical_topology_digest_available
    ):
        raise ValueError(
            "valid chemistry and preparation reports must share topology identity"
        )
    valence_violation_count = _profile_valence_violation_count(system)
    constraint_results = _profile_constraint_results(
        system,
        chemistry,
        preparation,
        valence_violation_count=valence_violation_count,
    )
    failed_constraint_codes = tuple(
        code for code, passed in constraint_results if not passed
    )
    canonical_ingest_status = _expected_ingest_status(constraint_results)
    preparation_status = (
        "incomplete" if dict(constraint_results)["canonical_state_valid"] else "invalid"
    )
    blockers = _expected_blockers(
        canonical_ingest_status=canonical_ingest_status,
        failed_constraint_codes=failed_constraint_codes,
        preparation_status=preparation_status,
    )
    applicability = CanonicalIngestApplicabilityReport(
        profile_id=(EXPLICIT_NEUTRAL_ACYCLIC_SATURATED_HYDROCARBON_PROFILE_ID),
        claim_scope=CANONICAL_INGEST_CLAIM_SCOPE,
        system_schema_id=system.schema_id,
        canonical_topology_schema_id=CANONICAL_TOPOLOGY_SCHEMA_ID,
        canonical_topology_sha256=chemistry.canonical_topology_sha256,
        canonical_topology_digest_available=(
            chemistry.canonical_topology_digest_available
        ),
        chemistry_coverage_schema_version=CHEMISTRY_COVERAGE_SCHEMA_VERSION,
        chemistry_coverage_report_sha256=chemistry.report_sha256,
        preparation_report_schema_version=PREPARATION_REPORT_SCHEMA_VERSION,
        preparation_report_sha256=preparation.report_sha256,
        source_format=preparation.source_format,
        source_sha256=preparation.source_sha256,
        source_digest_available=preparation.source_digest_available,
        parser_pedigree_id=preparation.parser_pedigree_id,
        parser_observation_self_consistent=(
            preparation.parser_observation_self_consistent
        ),
        source_authentication_status=SOURCE_AUTHENTICATION_STATUS,
        canonical_state_valid=chemistry.canonical_validation_valid,
        graph_representable=chemistry.graph_representable,
        atom_count=len(system.atoms),
        bond_count=len(system.bonds),
        component_count=chemistry.component_count,
        carbon_atom_count=sum(atom.element == "C" for atom in system.atoms),
        hydrogen_atom_count=sum(atom.element == "H" for atom in system.atoms),
        source_observed_hydrogen_count=(
            preparation.metadata_observed_source_hydrogen_count
        ),
        adapter_generated_hydrogen_count=(preparation.adapter_generated_hydrogen_count),
        unknown_hydrogen_origin_count=(preparation.unknown_hydrogen_origin_count),
        unknown_formal_charge_count=chemistry.unknown_formal_charge_count,
        nonzero_formal_charge_count=sum(
            atom.formal_charge_known and atom.formal_charge != 0
            for atom in system.atoms
        ),
        isotope_count=chemistry.isotope_count,
        aromatic_atom_count=chemistry.aromatic_atom_count,
        aromatic_bond_count=chemistry.aromatic_bond_count,
        non_single_bond_count=sum(
            bond.order != 1.0 or bond.aromatic for bond in system.bonds
        ),
        stereo_labeled_atom_count=sum(
            atom.stereo.strip().upper() not in {"", "NONE", "UNSPECIFIED"}
            for atom in system.atoms
        ),
        stereo_labeled_bond_count=sum(
            bond.stereo.strip().upper() not in {"", "NONE", "UNSPECIFIED"}
            for bond in system.bonds
        ),
        valence_violation_count=valence_violation_count,
        constraint_results=constraint_results,
        failed_constraint_codes=failed_constraint_codes,
        canonical_ingest_status=canonical_ingest_status,
        canonical_ingest_supported=canonical_ingest_status == "supported",
        preparation_status=preparation_status,
        preparation_ready=False,
        parameterability_status=PARAMETERABILITY_STATUS,
        parameter_set_id=None,
        parameter_assignment_sha256=None,
        blockers=blockers,
    )
    return chemistry, preparation, applicability


def analyze_canonical_ingest_applicability(
    system: AllAtomSystem,
) -> CanonicalIngestApplicabilityReport:
    """Assess the fixed ingest profile without assigning chemistry parameters."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    _, _, applicability = _analyze_canonical_ingest_bundle(system)
    return applicability


def require_canonical_ingest_applicable(
    system: AllAtomSystem,
) -> CanonicalIngestApplicabilityReport:
    report = analyze_canonical_ingest_applicability(system)
    if not report.canonical_ingest_supported:
        raise CanonicalIngestApplicabilityError(report)
    return report


__all__ = [
    "CANONICAL_INGEST_APPLICABILITY_SCHEMA_ID",
    "CANONICAL_INGEST_APPLICABILITY_SCHEMA_VERSION",
    "CANONICAL_INGEST_CLAIM_SCOPE",
    "CANONICAL_INGEST_CONSTRAINT_CODES",
    "EXPLICIT_NEUTRAL_ACYCLIC_SATURATED_HYDROCARBON_PROFILE_ID",
    "PARAMETERABILITY_STATUS",
    "SOURCE_AUTHENTICATION_STATUS",
    "CanonicalIngestApplicabilityError",
    "CanonicalIngestApplicabilityReport",
    "analyze_canonical_ingest_applicability",
    "require_canonical_ingest_applicable",
]
