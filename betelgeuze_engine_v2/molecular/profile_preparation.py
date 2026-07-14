"""Source-bound local preparation evidence for one canonical-ingest profile.

This report establishes only that a validated, source-bound canonical graph
satisfies the declared profile's local explicit-hydrogen and valence rules. It
does not establish whole-molecule completeness, environmental chemical state,
parameterability, simulation readiness, or product-claim safety.

The report retains the validated upstream applicability and preparation
objects rather than accepting copied booleans or counts. This makes the local
decision a derived view of those reports and prevents a second, independently
forgeable applicability authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .applicability import (
    CANONICAL_INGEST_APPLICABILITY_SCHEMA_ID,
    EXPLICIT_NEUTRAL_ACYCLIC_SATURATED_HYDROCARBON_PROFILE_ID,
    PARAMETERABILITY_STATUS,
    CanonicalIngestApplicabilityReport,
    _analyze_canonical_ingest_bundle,
)
from .chemistry import (
    CHEMISTRY_COVERAGE_SCHEMA_VERSION,
    ChemistryCoverageReport,
)
from .models import AllAtomSystem
from .preparation import (
    PREPARATION_POLICY_ID,
    PREPARATION_REPORT_SCHEMA_VERSION,
    MolecularPreparationReport,
)
from .topology import CANONICAL_TOPOLOGY_SCHEMA_ID


PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_VERSION = "1.0.0"
PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.profile_local_preparation_evidence/"
    f"{PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_VERSION}"
)
PROFILE_LOCAL_PREPARATION_CLAIM_SCOPE = "canonical_graph_local_valence_evidence_only"

SOURCE_HYDROGEN_INVENTORY_STATUSES = frozenset(
    {
        "invalid_source_binding",
        "complete_relative_to_parsed_source",
        "not_satisfied",
    }
)
PROFILE_HYDROGEN_VALENCE_STATUSES = frozenset(
    {
        "invalid_canonical_state",
        "satisfied_for_declared_canonical_graph",
        "not_satisfied",
    }
)
FORMAL_CHARGE_OBSERVATION_STATUSES = frozenset(
    {
        "invalid_source_binding",
        "source_observed_known_zero_not_assigned",
        "known_zero_origin_not_source_observed",
        "not_satisfied",
    }
)
AROMATICITY_REQUIREMENT_STATUSES = frozenset(
    {
        "invalid_canonical_state",
        "not_applicable_to_acyclic_single_bond_profile",
        "profile_requirements_not_satisfied",
    }
)
PROFILE_LOCAL_EVIDENCE_STATUSES = frozenset({"invalid", "not_satisfied", "satisfied"})

_SOURCE_OBSERVED_FORMAL_CHARGE_ORIGINS_BY_PEDIGREE = {
    ("mmcif", "betelgeuze.mmcif_parser/1.9.0"): frozenset(
        {"metadata_observed_mmcif_atom_site"}
    ),
    (
        "mmcif",
        "betelgeuze.mmcif_nonpoly_component_topology_parser/1.0.0",
    ): frozenset(
        {
            "metadata_observed_mmcif_atom_site",
            "metadata_observed_mmcif_chem_comp_atom",
        }
    ),
    (
        "mmcif",
        "betelgeuze.mmcif_nonpoly_covalent_struct_conn_topology_parser/1.0.0",
    ): frozenset(
        {
            "metadata_observed_mmcif_atom_site",
            "metadata_observed_mmcif_chem_comp_atom",
        }
    ),
    (
        "mmcif",
        "betelgeuze.mmcif_polymer_component_topology_parser/1.0.0",
    ): frozenset(
        {
            "metadata_observed_mmcif_atom_site",
            "metadata_observed_mmcif_chem_comp_atom",
        }
    ),
    ("sdf_v2000", "betelgeuze.sdf_v2000_parser/1.5.0"): frozenset(
        {"metadata_observed_sdf_v2000_atom_block"}
    ),
}
_ORIGINS_THAT_IMPLY_NONZERO_FORMAL_CHARGE = frozenset(
    {
        "metadata_observed_pdb_atom_field",
        "metadata_observed_sdf_v2000_m_chg",
    }
)
_UNASSESSED_STATUS = "unassessed"
_NO_NORMALIZATION_ACTION = "none"


def _source_observed_formal_charge_count(
    preparation: MolecularPreparationReport,
) -> int:
    allowed = _SOURCE_OBSERVED_FORMAL_CHARGE_ORIGINS_BY_PEDIGREE.get(
        (preparation.source_format, preparation.parser_pedigree_id),
        frozenset(),
    )
    return sum(
        count
        for origin, count in preparation.formal_charge_origin_counts
        if origin in allowed
    )


def _expected_statuses(
    applicability: CanonicalIngestApplicabilityReport,
    preparation: MolecularPreparationReport,
) -> dict[str, Any]:
    constraints = dict(applicability.constraint_results)
    identity_valid = applicability.canonical_ingest_status != "invalid"
    profile_supported = applicability.canonical_ingest_status == "supported"
    source_observed_charge_count = _source_observed_formal_charge_count(preparation)
    formal_charge_source_observed = bool(
        identity_valid
        and applicability.parser_observation_self_consistent
        and applicability.source_digest_available
        and constraints["formal_charges_known_zero"]
        and source_observed_charge_count == applicability.atom_count
    )
    source_hydrogen_inventory_status = (
        "invalid_source_binding"
        if not identity_valid
        else "complete_relative_to_parsed_source"
        if constraints["hydrogens_source_observed"]
        else "not_satisfied"
    )
    profile_hydrogen_valence_status = (
        "invalid_canonical_state"
        if not identity_valid
        else "satisfied_for_declared_canonical_graph"
        if (
            constraints["elements_h_c_only"]
            and constraints["single_bonds_only"]
            and constraints["explicit_valence_closed"]
        )
        else "not_satisfied"
    )
    formal_charge_observation_status = (
        "invalid_source_binding"
        if not identity_valid
        else "source_observed_known_zero_not_assigned"
        if formal_charge_source_observed
        else "known_zero_origin_not_source_observed"
        if constraints["formal_charges_known_zero"]
        else "not_satisfied"
    )
    aromaticity_requirement_status = (
        "invalid_canonical_state"
        if not identity_valid
        else "not_applicable_to_acyclic_single_bond_profile"
        if (
            constraints["aromaticity_absent"]
            and constraints["single_bonds_only"]
            and constraints["acyclic_graph"]
        )
        else "profile_requirements_not_satisfied"
    )
    polymer_missing_residue_status = (
        "not_applicable_to_single_nonpolymer_source"
        if (
            profile_supported
            and applicability.source_format == "sdf_v2000"
            and preparation.residue_count == 1
            and preparation.entity_type_counts == (("non_polymer", 1),)
        )
        else _UNASSESSED_STATUS
    )
    profile_local_evidence_satisfied = bool(
        profile_supported and formal_charge_source_observed
    )
    profile_local_evidence_status = (
        "invalid"
        if applicability.canonical_ingest_status == "invalid"
        else "satisfied"
        if profile_local_evidence_satisfied
        else "not_satisfied"
    )
    return {
        "source_hydrogen_inventory_status": source_hydrogen_inventory_status,
        "profile_hydrogen_valence_status": profile_hydrogen_valence_status,
        "formal_charge_observation_status": formal_charge_observation_status,
        "aromaticity_requirement_status": aromaticity_requirement_status,
        "polymer_missing_residue_status": polymer_missing_residue_status,
        "profile_local_evidence_status": profile_local_evidence_status,
        "profile_local_evidence_satisfied": profile_local_evidence_satisfied,
    }


def _expected_blockers(
    *,
    profile_local_evidence_status: str,
    source_hydrogen_inventory_status: str,
    profile_hydrogen_valence_status: str,
    formal_charge_observation_status: str,
    aromaticity_requirement_status: str,
    polymer_missing_residue_status: str,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if profile_local_evidence_status == "invalid":
        blockers.append("profile_local_preparation_evidence_invalid")
    elif profile_local_evidence_status == "not_satisfied":
        blockers.append("profile_local_preparation_evidence_not_satisfied")
    if source_hydrogen_inventory_status != "complete_relative_to_parsed_source":
        blockers.append("source_hydrogen_inventory_not_satisfied")
    if profile_hydrogen_valence_status != ("satisfied_for_declared_canonical_graph"):
        blockers.append("profile_hydrogen_valence_not_satisfied")
    if formal_charge_observation_status != ("source_observed_known_zero_not_assigned"):
        blockers.append("formal_charge_source_observation_not_satisfied")
    if aromaticity_requirement_status != (
        "not_applicable_to_acyclic_single_bond_profile"
    ):
        blockers.append("aromaticity_profile_requirement_not_satisfied")
    blockers.extend(
        (
            "profile_local_evidence_is_not_global_preparation",
            "whole_molecule_atom_completeness_unassessed",
            "hydrogen_completeness_unassessed",
            *(
                ("polymer_missing_residue_completeness_unassessed",)
                if polymer_missing_residue_status == _UNASSESSED_STATUS
                else ()
            ),
            "protonation_environment_unassessed",
            "formal_charge_assignment_unassessed",
            "tautomer_selection_unassessed",
            "aromaticity_perception_unassessed",
            "stereochemistry_assignment_unassessed",
            "electronic_state_unassessed",
            "geometry_quality_unassessed",
            "contextual_roles_unassessed",
            "source_digest_is_not_authentication",
            "normalization_not_attempted",
            "completion_not_attempted",
            "parameterability_not_assessed",
            "preparation_assessment_incomplete",
            "preparation_not_ready",
            "simulation_not_authorized",
            "claim_not_authorized",
        )
    )
    return tuple(blockers)


@dataclass(frozen=True, init=False)
class ProfileLocalPreparationEvidenceReport:
    """Derived local evidence that can only be built by analyzing a system."""

    chemistry_report: ChemistryCoverageReport
    applicability_report: CanonicalIngestApplicabilityReport
    preparation_report: MolecularPreparationReport

    def __init__(self, system: AllAtomSystem) -> None:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        chemistry, preparation, applicability = _analyze_canonical_ingest_bundle(system)
        object.__setattr__(self, "chemistry_report", chemistry)
        object.__setattr__(self, "applicability_report", applicability)
        object.__setattr__(self, "preparation_report", preparation)
        self._validate_bound_reports()

    def _validate_bound_reports(self) -> None:
        if type(self.chemistry_report) is not ChemistryCoverageReport:
            raise TypeError("chemistry_report must be a ChemistryCoverageReport")
        if type(self.applicability_report) is not (CanonicalIngestApplicabilityReport):
            raise TypeError(
                "applicability_report must be a CanonicalIngestApplicabilityReport"
            )
        if type(self.preparation_report) is not MolecularPreparationReport:
            raise TypeError("preparation_report must be a MolecularPreparationReport")
        chemistry = self.chemistry_report
        applicability = self.applicability_report
        preparation = self.preparation_report
        if applicability.profile_id != (
            EXPLICIT_NEUTRAL_ACYCLIC_SATURATED_HYDROCARBON_PROFILE_ID
        ):
            raise ValueError("profile preparation requires the fixed profile")
        if applicability.canonical_topology_schema_id != (CANONICAL_TOPOLOGY_SCHEMA_ID):
            raise ValueError("canonical topology schema mismatch")
        if applicability.chemistry_coverage_schema_version != (
            CHEMISTRY_COVERAGE_SCHEMA_VERSION
        ):
            raise ValueError("chemistry coverage schema version mismatch")
        if applicability.preparation_report_schema_version != (
            PREPARATION_REPORT_SCHEMA_VERSION
        ):
            raise ValueError("preparation report schema version mismatch")
        if preparation.policy_id != PREPARATION_POLICY_ID:
            raise ValueError("preparation policy mismatch")
        if applicability.chemistry_coverage_report_sha256 != (chemistry.report_sha256):
            raise ValueError(
                "applicability must be bound to the supplied chemistry report"
            )
        if applicability.preparation_report_sha256 != preparation.report_sha256:
            raise ValueError(
                "applicability must be bound to the supplied preparation report"
            )
        shared_evidence = {
            "system_schema_id": (
                chemistry.system_schema_id,
                applicability.system_schema_id,
                preparation.system_schema_id,
            ),
            "source_format": (
                applicability.source_format,
                preparation.source_format,
            ),
            "source_sha256": (
                applicability.source_sha256,
                preparation.source_sha256,
            ),
            "source_digest_available": (
                applicability.source_digest_available,
                preparation.source_digest_available,
            ),
            "parser_pedigree_id": (
                applicability.parser_pedigree_id,
                preparation.parser_pedigree_id,
            ),
            "parser_observation_self_consistent": (
                applicability.parser_observation_self_consistent,
                preparation.parser_observation_self_consistent,
            ),
            "canonical_topology_schema_id": (
                chemistry.canonical_topology_schema_id,
                applicability.canonical_topology_schema_id,
                preparation.canonical_topology_schema_id,
            ),
            "canonical_state_valid": (
                chemistry.canonical_validation_valid,
                applicability.canonical_state_valid,
                preparation.canonical_validation_valid,
            ),
            "atom_count": (
                chemistry.atom_count,
                applicability.atom_count,
                preparation.atom_count,
            ),
            "bond_count": (
                chemistry.bond_count,
                applicability.bond_count,
                preparation.bond_count,
            ),
            "component_count": (
                chemistry.component_count,
                applicability.component_count,
            ),
            "element_counts": (
                chemistry.element_counts,
                preparation.element_counts,
            ),
            "net_formal_charge": (
                chemistry.net_formal_charge,
                preparation.net_formal_charge,
            ),
            "hydrogen_atom_count": (
                applicability.hydrogen_atom_count,
                preparation.explicit_hydrogen_count,
            ),
            "source_observed_hydrogen_count": (
                applicability.source_observed_hydrogen_count,
                preparation.metadata_observed_source_hydrogen_count,
            ),
            "adapter_generated_hydrogen_count": (
                applicability.adapter_generated_hydrogen_count,
                preparation.adapter_generated_hydrogen_count,
            ),
            "unknown_hydrogen_origin_count": (
                applicability.unknown_hydrogen_origin_count,
                preparation.unknown_hydrogen_origin_count,
            ),
            "unknown_formal_charge_count": (
                chemistry.unknown_formal_charge_count,
                applicability.unknown_formal_charge_count,
                preparation.unknown_formal_charge_count,
            ),
            "isotope_count": (
                chemistry.isotope_count,
                applicability.isotope_count,
            ),
            "aromatic_atom_count": (
                chemistry.aromatic_atom_count,
                applicability.aromatic_atom_count,
                preparation.observed_aromatic_atom_count,
            ),
            "aromatic_bond_count": (
                chemistry.aromatic_bond_count,
                applicability.aromatic_bond_count,
                preparation.observed_aromatic_bond_count,
            ),
            "graph_representable": (
                chemistry.graph_representable,
                applicability.graph_representable,
            ),
        }
        mismatch = next(
            (
                name
                for name, values in shared_evidence.items()
                if any(value != values[0] for value in values[1:])
            ),
            None,
        )
        if mismatch is not None:
            raise ValueError(
                f"applicability and preparation reports disagree on {mismatch}"
            )
        if (
            applicability.canonical_topology_sha256
            != chemistry.canonical_topology_sha256
            or applicability.canonical_topology_digest_available
            != chemistry.canonical_topology_digest_available
        ):
            raise ValueError(
                "applicability and chemistry reports disagree on topology identity"
            )
        if applicability.canonical_state_valid and (
            applicability.canonical_topology_sha256
            != preparation.canonical_topology_sha256
            or applicability.canonical_topology_digest_available
            != preparation.canonical_topology_digest_available
        ):
            raise ValueError(
                "valid applicability and preparation reports disagree on topology identity"
            )
        element_counts = dict(chemistry.element_counts)
        if applicability.carbon_atom_count != element_counts.get(
            "C", 0
        ) or applicability.hydrogen_atom_count != element_counts.get("H", 0):
            raise ValueError(
                "applicability element diagnostics disagree with chemistry evidence"
            )
        if applicability.canonical_state_valid and (
            applicability.stereo_labeled_atom_count
            != chemistry.assigned_atom_stereo_count
            + chemistry.unknown_atom_stereo_count
            or applicability.stereo_labeled_bond_count
            != chemistry.assigned_bond_stereo_count
            + chemistry.unknown_bond_stereo_count
            + chemistry.bond_stereo_outside_profile_count
        ):
            raise ValueError(
                "applicability stereo diagnostics disagree with chemistry evidence"
            )
        constraint_values = dict(applicability.constraint_results)
        formal_charge_origins = {
            origin for origin, _ in preparation.formal_charge_origin_counts
        }
        if constraint_values["formal_charges_known_zero"] and (
            chemistry.net_formal_charge != 0
            or preparation.net_formal_charge != 0
            or bool(formal_charge_origins & _ORIGINS_THAT_IMPLY_NONZERO_FORMAL_CHARGE)
        ):
            raise ValueError(
                "known-zero applicability contradicts formal-charge evidence"
            )

    @property
    def profile_id(self) -> str:
        return self.applicability_report.profile_id

    @property
    def claim_scope(self) -> str:
        return PROFILE_LOCAL_PREPARATION_CLAIM_SCOPE

    @property
    def system_schema_id(self) -> str:
        return self.applicability_report.system_schema_id

    @property
    def canonical_topology_schema_id(self) -> str:
        return self.applicability_report.canonical_topology_schema_id

    @property
    def canonical_topology_sha256(self) -> str | None:
        return self.applicability_report.canonical_topology_sha256

    @property
    def canonical_topology_digest_available(self) -> bool:
        return self.applicability_report.canonical_topology_digest_available

    @property
    def chemistry_coverage_schema_version(self) -> str:
        return self.applicability_report.chemistry_coverage_schema_version

    @property
    def chemistry_coverage_report_sha256(self) -> str:
        return self.applicability_report.chemistry_coverage_report_sha256

    @property
    def preparation_report_schema_version(self) -> str:
        return self.applicability_report.preparation_report_schema_version

    @property
    def preparation_policy_id(self) -> str:
        return self.preparation_report.policy_id

    @property
    def preparation_report_sha256(self) -> str:
        return self.preparation_report.report_sha256

    @property
    def applicability_schema_id(self) -> str:
        return CANONICAL_INGEST_APPLICABILITY_SCHEMA_ID

    @property
    def applicability_report_sha256(self) -> str:
        return self.applicability_report.report_sha256

    @property
    def applicability_constraint_results(self) -> tuple[tuple[str, bool], ...]:
        return self.applicability_report.constraint_results

    @property
    def applicability_failed_constraint_codes(self) -> tuple[str, ...]:
        return self.applicability_report.failed_constraint_codes

    @property
    def canonical_ingest_status(self) -> str:
        return self.applicability_report.canonical_ingest_status

    @property
    def canonical_ingest_supported(self) -> bool:
        return self.applicability_report.canonical_ingest_supported

    @property
    def source_format(self) -> str:
        return self.applicability_report.source_format

    @property
    def source_sha256(self) -> str | None:
        return self.applicability_report.source_sha256

    @property
    def source_digest_available(self) -> bool:
        return self.applicability_report.source_digest_available

    @property
    def parser_pedigree_id(self) -> str:
        return self.applicability_report.parser_pedigree_id

    @property
    def parser_observation_self_consistent(self) -> bool:
        return self.applicability_report.parser_observation_self_consistent

    @property
    def source_authentication_status(self) -> str:
        return self.applicability_report.source_authentication_status

    @property
    def canonical_state_valid(self) -> bool:
        return self.applicability_report.canonical_state_valid

    @property
    def graph_representable(self) -> bool:
        return self.applicability_report.graph_representable

    @property
    def atom_count(self) -> int:
        return self.applicability_report.atom_count

    @property
    def bond_count(self) -> int:
        return self.applicability_report.bond_count

    @property
    def residue_count(self) -> int:
        return self.preparation_report.residue_count

    @property
    def component_count(self) -> int:
        return self.applicability_report.component_count

    @property
    def carbon_atom_count(self) -> int:
        return self.applicability_report.carbon_atom_count

    @property
    def hydrogen_atom_count(self) -> int:
        return self.applicability_report.hydrogen_atom_count

    @property
    def source_observed_hydrogen_count(self) -> int:
        return self.applicability_report.source_observed_hydrogen_count

    @property
    def adapter_generated_hydrogen_count(self) -> int:
        return self.applicability_report.adapter_generated_hydrogen_count

    @property
    def unknown_hydrogen_origin_count(self) -> int:
        return self.applicability_report.unknown_hydrogen_origin_count

    @property
    def unknown_formal_charge_count(self) -> int:
        return self.applicability_report.unknown_formal_charge_count

    @property
    def nonzero_formal_charge_count(self) -> int:
        return self.applicability_report.nonzero_formal_charge_count

    @property
    def isotope_count(self) -> int:
        return self.applicability_report.isotope_count

    @property
    def aromatic_atom_count(self) -> int:
        return self.applicability_report.aromatic_atom_count

    @property
    def aromatic_bond_count(self) -> int:
        return self.applicability_report.aromatic_bond_count

    @property
    def non_single_bond_count(self) -> int:
        return self.applicability_report.non_single_bond_count

    @property
    def stereo_labeled_atom_count(self) -> int:
        return self.applicability_report.stereo_labeled_atom_count

    @property
    def stereo_labeled_bond_count(self) -> int:
        return self.applicability_report.stereo_labeled_bond_count

    @property
    def valence_violation_count(self) -> int:
        return self.applicability_report.valence_violation_count

    @property
    def formal_charge_origin_counts(self) -> tuple[tuple[str, int], ...]:
        return self.preparation_report.formal_charge_origin_counts

    @property
    def source_observed_formal_charge_count(self) -> int:
        return _source_observed_formal_charge_count(self.preparation_report)

    @property
    def entity_type_counts(self) -> tuple[tuple[str, int], ...]:
        return self.preparation_report.entity_type_counts

    @property
    def _statuses(self) -> dict[str, Any]:
        return _expected_statuses(
            self.applicability_report,
            self.preparation_report,
        )

    @property
    def source_hydrogen_inventory_status(self) -> str:
        return self._statuses["source_hydrogen_inventory_status"]

    @property
    def profile_hydrogen_valence_status(self) -> str:
        return self._statuses["profile_hydrogen_valence_status"]

    @property
    def formal_charge_observation_status(self) -> str:
        return self._statuses["formal_charge_observation_status"]

    @property
    def aromaticity_requirement_status(self) -> str:
        return self._statuses["aromaticity_requirement_status"]

    @property
    def polymer_missing_residue_status(self) -> str:
        return self._statuses["polymer_missing_residue_status"]

    @property
    def profile_local_evidence_status(self) -> str:
        return self._statuses["profile_local_evidence_status"]

    @property
    def profile_local_evidence_satisfied(self) -> bool:
        return self._statuses["profile_local_evidence_satisfied"]

    @property
    def normalization_action(self) -> str:
        return _NO_NORMALIZATION_ACTION

    @property
    def whole_molecule_atom_completeness_status(self) -> str:
        return _UNASSESSED_STATUS

    @property
    def hydrogen_completeness_status(self) -> str:
        return _UNASSESSED_STATUS

    @property
    def protonation_status(self) -> str:
        return _UNASSESSED_STATUS

    @property
    def formal_charge_assignment_status(self) -> str:
        return _UNASSESSED_STATUS

    @property
    def tautomer_status(self) -> str:
        return _UNASSESSED_STATUS

    @property
    def aromaticity_perception_status(self) -> str:
        return _UNASSESSED_STATUS

    @property
    def stereochemistry_assignment_status(self) -> str:
        return _UNASSESSED_STATUS

    @property
    def electronic_state_status(self) -> str:
        return _UNASSESSED_STATUS

    @property
    def geometry_quality_status(self) -> str:
        return _UNASSESSED_STATUS

    @property
    def contextual_role_status(self) -> str:
        return _UNASSESSED_STATUS

    @property
    def parameterability_status(self) -> str:
        return PARAMETERABILITY_STATUS

    @property
    def normalization_attempted(self) -> bool:
        return False

    @property
    def completion_attempted(self) -> bool:
        return False

    @property
    def preparation_assessment_complete(self) -> bool:
        return False

    @property
    def preparation_assessed(self) -> bool:
        return False

    @property
    def preparation_ready(self) -> bool:
        return False

    @property
    def parameterability_assessed(self) -> bool:
        return False

    @property
    def parameterizable(self) -> bool:
        return False

    @property
    def simulation_ready(self) -> bool:
        return False

    @property
    def claim_safe(self) -> bool:
        return False

    @property
    def blockers(self) -> tuple[str, ...]:
        return _expected_blockers(
            profile_local_evidence_status=self.profile_local_evidence_status,
            source_hydrogen_inventory_status=(self.source_hydrogen_inventory_status),
            profile_hydrogen_valence_status=self.profile_hydrogen_valence_status,
            formal_charge_observation_status=(self.formal_charge_observation_status),
            aromaticity_requirement_status=self.aromaticity_requirement_status,
            polymer_missing_residue_status=self.polymer_missing_residue_status,
        )

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_ID,
            "schema_version": PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_VERSION,
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
            "preparation_policy_id": self.preparation_policy_id,
            "preparation_report_sha256": self.preparation_report_sha256,
            "applicability_schema_id": self.applicability_schema_id,
            "applicability_report_sha256": self.applicability_report_sha256,
            "applicability_constraint_results": [
                {"code": code, "passed": passed}
                for code, passed in self.applicability_constraint_results
            ],
            "applicability_failed_constraint_codes": list(
                self.applicability_failed_constraint_codes
            ),
            "canonical_ingest_status": self.canonical_ingest_status,
            "canonical_ingest_supported": self.canonical_ingest_supported,
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
            "residue_count": self.residue_count,
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
            "formal_charge_origin_counts": [
                list(item) for item in self.formal_charge_origin_counts
            ],
            "source_observed_formal_charge_count": (
                self.source_observed_formal_charge_count
            ),
            "entity_type_counts": [list(item) for item in self.entity_type_counts],
            "source_hydrogen_inventory_status": (self.source_hydrogen_inventory_status),
            "profile_hydrogen_valence_status": (self.profile_hydrogen_valence_status),
            "formal_charge_observation_status": (self.formal_charge_observation_status),
            "aromaticity_requirement_status": self.aromaticity_requirement_status,
            "polymer_missing_residue_status": (self.polymer_missing_residue_status),
            "normalization_action": self.normalization_action,
            "whole_molecule_atom_completeness_status": (
                self.whole_molecule_atom_completeness_status
            ),
            "hydrogen_completeness_status": self.hydrogen_completeness_status,
            "protonation_status": self.protonation_status,
            "formal_charge_assignment_status": (self.formal_charge_assignment_status),
            "tautomer_status": self.tautomer_status,
            "aromaticity_perception_status": self.aromaticity_perception_status,
            "stereochemistry_assignment_status": (
                self.stereochemistry_assignment_status
            ),
            "electronic_state_status": self.electronic_state_status,
            "geometry_quality_status": self.geometry_quality_status,
            "contextual_role_status": self.contextual_role_status,
            "parameterability_status": self.parameterability_status,
            "profile_local_evidence_status": self.profile_local_evidence_status,
            "profile_local_evidence_satisfied": (self.profile_local_evidence_satisfied),
            "normalization_attempted": self.normalization_attempted,
            "completion_attempted": self.completion_attempted,
            "preparation_assessment_complete": (self.preparation_assessment_complete),
            "preparation_assessed": self.preparation_assessed,
            "preparation_ready": self.preparation_ready,
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
            self.to_dict()
            == analyze_profile_local_preparation_evidence(system).to_dict()
        )


class ProfileLocalPreparationEvidenceError(RuntimeError):
    """Raised when the fixed profile-local evidence contract is not satisfied."""

    def __init__(self, report: ProfileLocalPreparationEvidenceReport):
        if type(report) is not ProfileLocalPreparationEvidenceReport:
            raise TypeError("report must be a ProfileLocalPreparationEvidenceReport")
        if report.profile_local_evidence_satisfied is True:
            raise ValueError("report must not have satisfied profile-local evidence")
        self.report = report
        self.status = report.profile_local_evidence_status
        self.blockers = report.blockers
        preview = ", ".join(self.blockers[:6]) or "none"
        suffix = "" if len(self.blockers) <= 6 else f", +{len(self.blockers) - 6} more"
        super().__init__(
            "profile-local preparation evidence is not satisfied: "
            f"status={self.status}; blockers={preview}{suffix}"
        )


def analyze_profile_local_preparation_evidence(
    system: AllAtomSystem,
) -> ProfileLocalPreparationEvidenceReport:
    """Build local graph evidence without performing or attesting preparation."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    return ProfileLocalPreparationEvidenceReport(system)


def require_profile_local_preparation_evidence(
    system: AllAtomSystem,
) -> ProfileLocalPreparationEvidenceReport:
    """Require the fixed local evidence without promoting global readiness."""

    report = analyze_profile_local_preparation_evidence(system)
    if type(report) is not ProfileLocalPreparationEvidenceReport:
        raise TypeError("analyzer must return a ProfileLocalPreparationEvidenceReport")
    if report.profile_local_evidence_satisfied is not True:
        raise ProfileLocalPreparationEvidenceError(report)
    return report


__all__ = [
    "AROMATICITY_REQUIREMENT_STATUSES",
    "FORMAL_CHARGE_OBSERVATION_STATUSES",
    "PROFILE_HYDROGEN_VALENCE_STATUSES",
    "PROFILE_LOCAL_EVIDENCE_STATUSES",
    "PROFILE_LOCAL_PREPARATION_CLAIM_SCOPE",
    "PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_ID",
    "PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_VERSION",
    "SOURCE_HYDROGEN_INVENTORY_STATUSES",
    "ProfileLocalPreparationEvidenceError",
    "ProfileLocalPreparationEvidenceReport",
    "analyze_profile_local_preparation_evidence",
    "require_profile_local_preparation_evidence",
]
