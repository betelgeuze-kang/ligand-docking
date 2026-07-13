"""Bounded source-bound applicability for linear alkanes C1--C4.

This module is a topology-applicability bridge only.  It recognizes a strict
SDF V2000, explicit-hydrogen, neutral, non-isotopic linear-alkane slice so
later V2-2 contracts can enumerate topological environments and terms.  It
does not assign force-field atom types, partial charges, parameters, physics,
runtime authority, or scientific validity.

The report stores only canonical system snapshot bytes.  Every public view is
recomputed from those bytes and fresh upstream preparation evidence.  Source
and report digests provide deterministic binding, not authentication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from .models import AllAtomSystem
from .profile_preparation import (
    PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_ID,
    ProfileLocalPreparationEvidenceReport,
    analyze_profile_local_preparation_evidence,
)
from .serialization import (
    deserialize_all_atom_system,
    serialize_all_atom_system,
)


_FROZEN_SCHEMA_VERSION = "1.0.0"
_FROZEN_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_force_field_applicability/1.0.0"
)
_FROZEN_PROFILE_ID = (
    "source_bound_sdf_v2000_explicit_h_neutral_linear_alkane_c1_c4/1.0.0"
)
_FROZEN_CLAIM_SCOPE = (
    "bounded_linear_alkane_c1_c4_topological_applicability_only"
)
_FROZEN_SDF_V2000_PARSER_PEDIGREE = (
    "betelgeuze.sdf_v2000_parser/1.5.0"
)
_FROZEN_SOURCE_AUTHENTICATION_STATUS = "digest_bound_not_authenticated"
_FROZEN_CARBON_CHAIN_ORIENTATION_POLICY_ID = (
    "lexicographically_minimum_forward_or_reverse_atom_index_path/1.0.0"
)
_FROZEN_CONSTRAINT_CODES = (
    "upstream_applicability_valid",
    "canonical_state_valid",
    "canonical_ingest_supported",
    "profile_local_evidence_satisfied",
    "sdf_v2000_source_pedigree",
    "source_binding_self_consistent",
    "single_component",
    "single_nonpolymer_residue",
    "carbon_count_c1_c4",
    "elements_h_c_only",
    "exact_linear_alkane_formula",
    "formal_charges_known_zero",
    "isotopes_absent",
    "aromaticity_absent",
    "stereo_absent",
    "single_bonds_only",
    "exact_source_observed_hydrogen_inventory",
    "source_partial_charges_absent",
    "carbon_subgraph_simple_path",
    "exact_carbon_hydrogen_degrees",
)
_FROZEN_STATUSES = frozenset({"invalid", "unsupported", "available"})
_MOLECULE_LABELS = {
    1: "methane",
    2: "ethane",
    3: "propane",
    4: "n_butane",
}

LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_VERSION = (
    _FROZEN_SCHEMA_VERSION
)
LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_ID = _FROZEN_SCHEMA_ID
LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_PROFILE_ID = _FROZEN_PROFILE_ID
LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_CLAIM_SCOPE = (
    _FROZEN_CLAIM_SCOPE
)
LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_CONSTRAINT_CODES = (
    _FROZEN_CONSTRAINT_CODES
)
LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_STATUSES = _FROZEN_STATUSES
LINEAR_ALKANE_C1_C4_CARBON_CHAIN_ORIENTATION_POLICY_ID = (
    _FROZEN_CARBON_CHAIN_ORIENTATION_POLICY_ID
)


def _canonical_json_bytes(document: Any) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_document(document: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(document)).hexdigest()


def _single_nonpolymer_residue(system: AllAtomSystem) -> bool:
    if len(system.residues) != 1:
        return False
    residue = system.residues[0]
    return bool(
        residue.entity_type == "non_polymer"
        and tuple(sorted(residue.atom_indices))
        == tuple(range(system.atom_count))
    )


@dataclass(frozen=True, slots=True)
class _GraphEvidence:
    carbon_indices: tuple[int, ...]
    hydrogen_indices: tuple[int, ...]
    canonical_carbon_chain: tuple[int, ...]
    elements_h_c_only: bool
    formula_exact: bool
    carbon_path_exact: bool
    degrees_exact: bool
    single_bonds_only: bool


def _canonical_carbon_path(
    carbon_indices: tuple[int, ...],
    carbon_adjacency: dict[int, set[int]],
) -> tuple[int, ...]:
    if len(carbon_indices) == 1:
        only = carbon_indices[0]
        return (only,) if not carbon_adjacency[only] else ()
    endpoints = tuple(
        sorted(index for index in carbon_indices if len(carbon_adjacency[index]) == 1)
    )
    if len(endpoints) != 2:
        return ()
    if any(len(carbon_adjacency[index]) not in {1, 2} for index in carbon_indices):
        return ()
    path = [endpoints[0]]
    previous: int | None = None
    current = endpoints[0]
    while True:
        candidates = sorted(carbon_adjacency[current] - ({previous} if previous is not None else set()))
        if not candidates:
            break
        if len(candidates) != 1:
            return ()
        previous, current = current, candidates[0]
        if current in path:
            return ()
        path.append(current)
    if len(path) != len(carbon_indices) or set(path) != set(carbon_indices):
        return ()
    forward = tuple(path)
    reverse = tuple(reversed(forward))
    return min(forward, reverse)


def _graph_evidence(system: AllAtomSystem) -> _GraphEvidence:
    atom_by_index = {atom.index: atom for atom in system.atoms}
    expected_indices = tuple(range(system.atom_count))
    index_contract_valid = tuple(sorted(atom_by_index)) == expected_indices
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
    elements_h_c_only = bool(
        index_contract_valid
        and len(carbon_indices) + len(hydrogen_indices) == system.atom_count
    )
    adjacency = {index: set() for index in expected_indices}
    single_bonds_only = True
    for bond in system.bonds:
        if (
            bond.atom_i not in adjacency
            or bond.atom_j not in adjacency
            or bond.atom_i == bond.atom_j
        ):
            single_bonds_only = False
            continue
        adjacency[bond.atom_i].add(bond.atom_j)
        adjacency[bond.atom_j].add(bond.atom_i)
        if bond.order != 1.0 or bond.aromatic:
            single_bonds_only = False

    carbon_set = set(carbon_indices)
    hydrogen_set = set(hydrogen_indices)
    carbon_adjacency = {
        index: adjacency[index] & carbon_set for index in carbon_indices
    }
    canonical_chain = (
        _canonical_carbon_path(carbon_indices, carbon_adjacency)
        if carbon_indices
        else ()
    )
    carbon_edge_count = sum(len(neighbors) for neighbors in carbon_adjacency.values()) // 2
    carbon_path_exact = bool(
        canonical_chain
        and len(canonical_chain) == len(carbon_indices)
        and carbon_edge_count == len(carbon_indices) - 1
    )
    degrees_exact = bool(
        elements_h_c_only
        and carbon_path_exact
        and all(
            len(adjacency[index]) == 4
            and adjacency[index] <= carbon_set | hydrogen_set
            and len(adjacency[index] & hydrogen_set)
            == 4 - len(carbon_adjacency[index])
            for index in carbon_indices
        )
        and all(
            len(adjacency[index]) == 1
            and next(iter(adjacency[index]), None) in carbon_set
            for index in hydrogen_indices
        )
    )
    formula_exact = bool(
        elements_h_c_only
        and len(carbon_indices) in {1, 2, 3, 4}
        and len(hydrogen_indices) == 2 * len(carbon_indices) + 2
    )
    return _GraphEvidence(
        carbon_indices=carbon_indices,
        hydrogen_indices=hydrogen_indices,
        canonical_carbon_chain=canonical_chain,
        elements_h_c_only=elements_h_c_only,
        formula_exact=formula_exact,
        carbon_path_exact=carbon_path_exact,
        degrees_exact=degrees_exact,
        single_bonds_only=single_bonds_only,
    )


def _constraint_results(
    system: AllAtomSystem,
    profile: ProfileLocalPreparationEvidenceReport,
    graph: _GraphEvidence,
) -> tuple[tuple[str, bool], ...]:
    source_hydrogen_count = len(graph.hydrogen_indices)
    values = {
        "upstream_applicability_valid": profile.canonical_ingest_status != "invalid",
        "canonical_state_valid": profile.canonical_state_valid,
        "canonical_ingest_supported": profile.canonical_ingest_supported,
        "profile_local_evidence_satisfied": profile.profile_local_evidence_satisfied,
        "sdf_v2000_source_pedigree": bool(
            profile.source_format == "sdf_v2000"
            and profile.parser_pedigree_id == _FROZEN_SDF_V2000_PARSER_PEDIGREE
        ),
        "source_binding_self_consistent": bool(
            profile.source_digest_available
            and profile.parser_observation_self_consistent
        ),
        "single_component": profile.component_count == 1,
        "single_nonpolymer_residue": _single_nonpolymer_residue(system),
        "carbon_count_c1_c4": len(graph.carbon_indices) in {1, 2, 3, 4},
        "elements_h_c_only": graph.elements_h_c_only,
        "exact_linear_alkane_formula": graph.formula_exact,
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
        "single_bonds_only": bool(
            graph.single_bonds_only and profile.non_single_bond_count == 0
        ),
        "exact_source_observed_hydrogen_inventory": bool(
            profile.source_observed_hydrogen_count == source_hydrogen_count
            and profile.adapter_generated_hydrogen_count == 0
            and profile.unknown_hydrogen_origin_count == 0
            and profile.source_hydrogen_inventory_status
            == "complete_relative_to_parsed_source"
        ),
        "source_partial_charges_absent": all(
            atom.partial_charge_e is None for atom in system.atoms
        ),
        "carbon_subgraph_simple_path": graph.carbon_path_exact,
        "exact_carbon_hydrogen_degrees": graph.degrees_exact,
    }
    return tuple((code, values[code]) for code in _FROZEN_CONSTRAINT_CODES)


def _applicability_status(
    profile: ProfileLocalPreparationEvidenceReport,
    constraints: tuple[tuple[str, bool], ...],
) -> str:
    if profile.canonical_ingest_status == "invalid" or not profile.canonical_state_valid:
        return "invalid"
    if any(not passed for _, passed in constraints):
        return "unsupported"
    return "available"


def _blockers(
    status: str,
    failed_constraint_codes: tuple[str, ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if status == "invalid":
        blockers.append("linear_alkane_c1_c4_applicability_state_invalid")
    elif status == "unsupported":
        blockers.append("linear_alkane_c1_c4_profile_unsupported")
    blockers.extend(
        f"linear_alkane_c1_c4_constraint_failed_{code}"
        for code in failed_constraint_codes
    )
    blockers.extend(
        (
            "source_digest_is_not_authentication",
            "bounded_profile_is_not_general_alkane_support",
            "topological_applicability_does_not_establish_parameterability",
            "force_field_atom_types_not_assigned",
            "partial_charges_not_assigned",
            "force_field_parameters_not_assigned",
            "scientific_validation_missing",
            "preparation_not_ready",
            "runtime_not_authorized",
            "energy_evaluation_not_authorized",
            "force_evaluation_not_authorized",
            "virial_evaluation_not_authorized",
            "minimization_not_authorized",
            "simulation_not_authorized",
            "claim_not_authorized",
        )
    )
    return tuple(blockers)


@dataclass(frozen=True, slots=True)
class _DerivedApplicability:
    system: AllAtomSystem
    profile: ProfileLocalPreparationEvidenceReport
    graph: _GraphEvidence
    constraints: tuple[tuple[str, bool], ...]
    status: str


def _derive_from_snapshot(snapshot: bytes) -> _DerivedApplicability:
    if type(snapshot) is not bytes:
        raise TypeError("canonical system snapshot must be exact bytes")
    system = deserialize_all_atom_system(snapshot)
    if serialize_all_atom_system(system) != snapshot:
        raise ValueError("stored system snapshot is not canonical")
    profile = analyze_profile_local_preparation_evidence(system)
    graph = _graph_evidence(system)
    constraints = _constraint_results(system, profile, graph)
    status = _applicability_status(profile, constraints)
    if status not in _FROZEN_STATUSES:
        raise ValueError("unknown linear-alkane applicability status")
    return _DerivedApplicability(system, profile, graph, constraints, status)


@dataclass(frozen=True, init=False, slots=True)
class LinearAlkaneC1C4ForceFieldApplicabilityReport:
    """Self-recomputing applicability report for the bounded C1--C4 slice."""

    _canonical_system_bytes: bytes = field(repr=False)
    _canonical_system_sha256: str = field(repr=False)

    def __init__(self, system: AllAtomSystem) -> None:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        snapshot = serialize_all_atom_system(system)
        _derive_from_snapshot(snapshot)
        object.__setattr__(self, "_canonical_system_bytes", snapshot)
        object.__setattr__(
            self,
            "_canonical_system_sha256",
            hashlib.sha256(snapshot).hexdigest(),
        )

    def _derive(self) -> _DerivedApplicability:
        snapshot = self._canonical_system_bytes
        expected_sha256 = self._canonical_system_sha256
        if type(snapshot) is not bytes:
            raise TypeError("canonical system snapshot binding must be exact bytes")
        if (
            type(expected_sha256) is not str
            or len(expected_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_sha256
            )
            or hashlib.sha256(snapshot).hexdigest() != expected_sha256
        ):
            raise ValueError("canonical system snapshot digest binding is inconsistent")
        return _derive_from_snapshot(snapshot)

    @property
    def system(self) -> AllAtomSystem:
        return self._derive().system

    @property
    def profile_id(self) -> str:
        self._derive()
        return _FROZEN_PROFILE_ID

    @property
    def claim_scope(self) -> str:
        self._derive()
        return _FROZEN_CLAIM_SCOPE

    @property
    def canonical_system_snapshot_sha256(self) -> str:
        self._derive()
        return hashlib.sha256(self._canonical_system_bytes).hexdigest()

    @property
    def system_schema_id(self) -> str:
        return self._derive().profile.system_schema_id

    @property
    def canonical_topology_schema_id(self) -> str:
        return self._derive().profile.canonical_topology_schema_id

    @property
    def canonical_topology_sha256(self) -> str | None:
        return self._derive().profile.canonical_topology_sha256

    @property
    def canonical_topology_digest_available(self) -> bool:
        return self._derive().profile.canonical_topology_digest_available

    @property
    def profile_local_preparation_schema_id(self) -> str:
        self._derive()
        return PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_ID

    @property
    def profile_local_preparation_report_sha256(self) -> str:
        return self._derive().profile.report_sha256

    @property
    def upstream_applicability_report_sha256(self) -> str:
        return self._derive().profile.applicability_report_sha256

    @property
    def source_format(self) -> str:
        return self._derive().profile.source_format

    @property
    def source_sha256(self) -> str | None:
        return self._derive().profile.source_sha256

    @property
    def source_digest_available(self) -> bool:
        return self._derive().profile.source_digest_available

    @property
    def parser_pedigree_id(self) -> str:
        return self._derive().profile.parser_pedigree_id

    @property
    def parser_observation_self_consistent(self) -> bool:
        return self._derive().profile.parser_observation_self_consistent

    @property
    def source_authentication_status(self) -> str:
        self._derive()
        return _FROZEN_SOURCE_AUTHENTICATION_STATUS

    @property
    def source_authenticated(self) -> bool:
        self._derive()
        return False

    @property
    def constraint_results(self) -> tuple[tuple[str, bool], ...]:
        return self._derive().constraints

    @property
    def failed_constraint_codes(self) -> tuple[str, ...]:
        return tuple(
            code for code, passed in self._derive().constraints if not passed
        )

    @property
    def applicability_status(self) -> str:
        return self._derive().status

    @property
    def status(self) -> str:
        return self._derive().status

    @property
    def applicable(self) -> bool:
        return self._derive().status == "available"

    @property
    def canonical_ingest_status(self) -> str:
        return self._derive().profile.canonical_ingest_status

    @property
    def profile_local_evidence_status(self) -> str:
        return self._derive().profile.profile_local_evidence_status

    @property
    def atom_count(self) -> int:
        return self._derive().profile.atom_count

    @property
    def bond_count(self) -> int:
        return self._derive().profile.bond_count

    @property
    def residue_count(self) -> int:
        return self._derive().profile.residue_count

    @property
    def component_count(self) -> int:
        return self._derive().profile.component_count

    @property
    def carbon_atom_count(self) -> int:
        return len(self._derive().graph.carbon_indices)

    @property
    def hydrogen_atom_count(self) -> int:
        return len(self._derive().graph.hydrogen_indices)

    @property
    def observed_partial_charge_count(self) -> int:
        return sum(
            atom.partial_charge_e is not None for atom in self._derive().system.atoms
        )

    @property
    def carbon_atom_indices(self) -> tuple[int, ...]:
        derived = self._derive()
        return derived.graph.carbon_indices if derived.status == "available" else ()

    @property
    def hydrogen_atom_indices(self) -> tuple[int, ...]:
        derived = self._derive()
        return derived.graph.hydrogen_indices if derived.status == "available" else ()

    @property
    def canonical_carbon_chain(self) -> tuple[int, ...]:
        derived = self._derive()
        return (
            derived.graph.canonical_carbon_chain
            if derived.status == "available"
            else ()
        )

    @property
    def carbon_chain_orientation_policy_id(self) -> str:
        self._derive()
        return _FROZEN_CARBON_CHAIN_ORIENTATION_POLICY_ID

    @property
    def molecule_label(self) -> str | None:
        derived = self._derive()
        return (
            _MOLECULE_LABELS[len(derived.graph.carbon_indices)]
            if derived.status == "available"
            else None
        )

    @property
    def molecular_formula(self) -> str | None:
        derived = self._derive()
        if derived.status != "available":
            return None
        return (
            f"C{len(derived.graph.carbon_indices)}"
            f"H{len(derived.graph.hydrogen_indices)}"
        )

    @property
    def parameterability_status(self) -> str:
        self._derive()
        return "not_assessed_topological_applicability_only"

    @property
    def atom_typing_status(self) -> str:
        self._derive()
        return "not_assigned"

    @property
    def partial_charge_assignment_status(self) -> str:
        self._derive()
        return "not_assigned"

    @property
    def parameter_set_id(self) -> None:
        self._derive()
        return None

    @property
    def parameter_assignment_sha256(self) -> None:
        self._derive()
        return None

    def _false_gate(self) -> bool:
        self._derive()
        return False

    @property
    def preparation_ready(self) -> bool:
        return self._false_gate()

    @property
    def parameterability_assessed(self) -> bool:
        return self._false_gate()

    @property
    def parameterizable(self) -> bool:
        return self._false_gate()

    @property
    def atom_types_assigned(self) -> bool:
        return self._false_gate()

    @property
    def partial_charges_assigned(self) -> bool:
        return self._false_gate()

    @property
    def force_field_parameters_assigned(self) -> bool:
        return self._false_gate()

    @property
    def global_parameter_coverage_complete(self) -> bool:
        return self._false_gate()

    @property
    def physics_supported(self) -> bool:
        return self._false_gate()

    @property
    def scientific_validity_green(self) -> bool:
        return self._false_gate()

    @property
    def runtime_eligible(self) -> bool:
        return self._false_gate()

    @property
    def execution_authorized(self) -> bool:
        return self._false_gate()

    @property
    def energy_evaluation_authorized(self) -> bool:
        return self._false_gate()

    @property
    def force_evaluation_authorized(self) -> bool:
        return self._false_gate()

    @property
    def virial_evaluation_authorized(self) -> bool:
        return self._false_gate()

    @property
    def minimization_authorized(self) -> bool:
        return self._false_gate()

    @property
    def simulation_ready(self) -> bool:
        return self._false_gate()

    @property
    def claim_safe(self) -> bool:
        return self._false_gate()

    @property
    def blockers(self) -> tuple[str, ...]:
        derived = self._derive()
        failed = tuple(
            code for code, passed in derived.constraints if not passed
        )
        return _blockers(derived.status, failed)

    def _core_dict(self) -> dict[str, Any]:
        derived = self._derive()
        profile = derived.profile
        failed = tuple(
            code for code, passed in derived.constraints if not passed
        )
        available = derived.status == "available"
        carbon_indices = derived.graph.carbon_indices if available else ()
        hydrogen_indices = derived.graph.hydrogen_indices if available else ()
        carbon_chain = (
            derived.graph.canonical_carbon_chain if available else ()
        )
        return {
            "schema_id": _FROZEN_SCHEMA_ID,
            "schema_version": _FROZEN_SCHEMA_VERSION,
            "profile_id": _FROZEN_PROFILE_ID,
            "claim_scope": _FROZEN_CLAIM_SCOPE,
            "canonical_system_snapshot_sha256": hashlib.sha256(
                self._canonical_system_bytes
            ).hexdigest(),
            "system_schema_id": profile.system_schema_id,
            "canonical_topology_schema_id": profile.canonical_topology_schema_id,
            "canonical_topology_sha256": profile.canonical_topology_sha256,
            "canonical_topology_digest_available": (
                profile.canonical_topology_digest_available
            ),
            "profile_local_preparation_schema_id": (
                PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_ID
            ),
            "profile_local_preparation_report_sha256": profile.report_sha256,
            "upstream_applicability_report_sha256": (
                profile.applicability_report_sha256
            ),
            "canonical_ingest_status": profile.canonical_ingest_status,
            "profile_local_evidence_status": profile.profile_local_evidence_status,
            "source_format": profile.source_format,
            "source_sha256": profile.source_sha256,
            "source_digest_available": profile.source_digest_available,
            "parser_pedigree_id": profile.parser_pedigree_id,
            "parser_observation_self_consistent": (
                profile.parser_observation_self_consistent
            ),
            "source_authentication_status": (
                _FROZEN_SOURCE_AUTHENTICATION_STATUS
            ),
            "source_authenticated": False,
            "constraint_results": [
                {"code": code, "passed": passed}
                for code, passed in derived.constraints
            ],
            "failed_constraint_codes": list(failed),
            "applicability_status": derived.status,
            "applicable": available,
            "atom_count": profile.atom_count,
            "bond_count": profile.bond_count,
            "residue_count": profile.residue_count,
            "component_count": profile.component_count,
            "carbon_atom_count": len(derived.graph.carbon_indices),
            "hydrogen_atom_count": len(derived.graph.hydrogen_indices),
            "observed_partial_charge_count": sum(
                atom.partial_charge_e is not None
                for atom in derived.system.atoms
            ),
            "carbon_atom_indices": list(carbon_indices),
            "hydrogen_atom_indices": list(hydrogen_indices),
            "canonical_carbon_chain": list(carbon_chain),
            "carbon_chain_orientation_policy_id": (
                _FROZEN_CARBON_CHAIN_ORIENTATION_POLICY_ID
            ),
            "molecule_label": (
                _MOLECULE_LABELS[len(derived.graph.carbon_indices)]
                if available
                else None
            ),
            "molecular_formula": (
                f"C{len(derived.graph.carbon_indices)}"
                f"H{len(derived.graph.hydrogen_indices)}"
                if available
                else None
            ),
            "parameterability_status": (
                "not_assessed_topological_applicability_only"
            ),
            "atom_typing_status": "not_assigned",
            "partial_charge_assignment_status": "not_assigned",
            "parameter_set_id": None,
            "parameter_assignment_sha256": None,
            "preparation_ready": False,
            "parameterability_assessed": False,
            "parameterizable": False,
            "atom_types_assigned": False,
            "partial_charges_assigned": False,
            "force_field_parameters_assigned": False,
            "global_parameter_coverage_complete": False,
            "physics_supported": False,
            "scientific_validity_green": False,
            "runtime_eligible": False,
            "execution_authorized": False,
            "energy_evaluation_authorized": False,
            "force_evaluation_authorized": False,
            "virial_evaluation_authorized": False,
            "minimization_authorized": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": list(_blockers(derived.status, failed)),
        }

    @property
    def report_sha256(self) -> str:
        return _sha256_document(self._core_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = self._core_dict()
        payload["report_sha256"] = _sha256_document(payload)
        return payload

    def matches_system(self, system: AllAtomSystem) -> bool:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        return self.to_dict() == (
            analyze_linear_alkane_c1_c4_force_field_applicability(system).to_dict()
        )


def analyze_linear_alkane_c1_c4_force_field_applicability(
    system: AllAtomSystem,
) -> LinearAlkaneC1C4ForceFieldApplicabilityReport:
    """Analyze the bounded source-bound C1--C4 topological profile."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    return LinearAlkaneC1C4ForceFieldApplicabilityReport(system)


__all__ = [
    "LINEAR_ALKANE_C1_C4_CARBON_CHAIN_ORIENTATION_POLICY_ID",
    "LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_CLAIM_SCOPE",
    "LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_CONSTRAINT_CODES",
    "LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_PROFILE_ID",
    "LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_ID",
    "LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_VERSION",
    "LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_STATUSES",
    "LinearAlkaneC1C4ForceFieldApplicabilityReport",
    "analyze_linear_alkane_c1_c4_force_field_applicability",
]
