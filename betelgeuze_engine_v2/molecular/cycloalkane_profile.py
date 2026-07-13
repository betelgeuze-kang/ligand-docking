"""Bounded graph-local chemistry evidence for unsubstituted cycloalkanes C3--C8.

This additive profile accepts only parser-owned SDF V2000 systems whose live
graph is an explicit-hydrogen, neutral, unsubstituted monocyclic cycloalkane.
It establishes source-observed graph identity and local C/H valence only.  It
does not promote global molecular preparation, environmental protonation,
geometry or conformer quality, parameterability, physics, runtime, or claims.

The public artifact is factory-only and stores a canonical system snapshot.
Every property is recomputed from that snapshot and fresh generic chemistry
and preparation reports.  Digest binding is deterministic evidence, not
source authentication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import json
import struct
from typing import Any

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID

from .chemistry import (
    CHEMISTRY_COVERAGE_SCHEMA_VERSION,
    analyze_canonical_chemistry,
)
from .models import AllAtomSystem
from .observation import PARSER_OBSERVATION_SCHEMA_ID, parser_observation_sha256
from .preparation import (
    PREPARATION_REPORT_SCHEMA_VERSION,
    analyze_molecular_preparation,
)
from .serialization import deserialize_all_atom_system, serialize_all_atom_system


CYCLOALKANE_C3_C8_PROFILE_SCHEMA_VERSION = "1.0.0"
CYCLOALKANE_C3_C8_PROFILE_SCHEMA_ID = "betelgeuze.cycloalkane_c3_c8_graph_profile/1.0.0"
CYCLOALKANE_C3_C8_PROFILE_ID = (
    "source_observed_explicit_h_neutral_unsubstituted_monocyclic_"
    "cycloalkane_c3_c8/1.0.0"
)
CYCLOALKANE_C3_C8_GRAPH_PROJECTION_SCHEMA_ID = (
    "betelgeuze.cycloalkane_c3_c8_graph_projection/1.0.0"
)
CYCLOALKANE_C3_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS = (
    "source_indexed_exact_projection_not_order_independent_graph_isomorphism_identity"
)
CYCLOALKANE_C3_C8_PREPARATION_SCOPE = (
    "source_observed_graph_local_identity_and_valence_only"
)
CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS = ("cycloalkane_c3_c8_graph_profile_audit",)
CYCLOALKANE_C3_C8_PROFILE_STATUSES = frozenset({"invalid", "unsupported", "available"})
CYCLOALKANE_C3_C8_CONSTRAINT_CODES = (
    "current_all_atom_schema",
    "canonical_state_valid",
    "canonical_topology_digest_available",
    "generic_report_versions_current",
    "sdf_v2000_source_pedigree",
    "source_binding_self_consistent",
    "parser_observation_digest_bound",
    "single_component",
    "single_nonpolymer_residue",
    "carbon_count_c3_c8",
    "elements_h_c_only",
    "exact_cycloalkane_formula_c_n_h_2n",
    "formal_charges_source_observed_known_zero",
    "isotopes_absent",
    "atom_maps_absent",
    "partial_charges_absent",
    "typed_stereo_absent",
    "aromaticity_absent",
    "single_bonds_only",
    "source_observed_hydrogens_only",
    "carbon_subgraph_connected_simple_cycle",
    "exact_carbon_hydrogen_degrees",
    "generic_reports_remain_nonpromoted",
)

_SDF_V2000_PARSER_PEDIGREE_ID = "betelgeuze.sdf_v2000_parser/1.5.0"
_SOURCE_AUTHENTICATION_STATUS = "digest_bound_not_authenticated"
_FACTORY_TOKEN = object()
_PROFILE_MIN_CARBONS = 3
_PROFILE_MAX_CARBONS = 8
_MOLECULE_LABELS = {
    3: "cyclopropane",
    4: "cyclobutane",
    5: "cyclopentane",
    6: "cyclohexane",
    7: "cycloheptane",
    8: "cyclooctane",
}
_ALWAYS_BLOCKERS = (
    "source_digest_is_not_authentication",
    "profile_bound_c3_c8_is_not_general_cycloalkane_support",
    "graph_projection_sha256_is_source_indexed_not_order_independent_graph_isomorphism_identity",
    "profile_graph_preparation_is_not_global_molecular_preparation",
    "environmental_ph_and_protonation_correctness_not_assessed",
    "ring_strain_not_assessed",
    "conformation_and_geometry_quality_not_assessed",
    "parameterability_not_assessed",
    "force_field_atom_types_not_assigned",
    "partial_charges_not_assigned",
    "force_field_parameters_not_assigned",
    "runtime_not_authorized",
    "energy_evaluation_not_authorized",
    "force_evaluation_not_authorized",
    "minimization_not_authorized",
    "simulation_not_authorized",
    "claim_not_authorized",
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


CYCLOALKANE_C3_C8_RULE_SET_SCHEMA_ID = "betelgeuze.cycloalkane_c3_c8_graph_rules/1.0.0"
_RULE_SET_BYTES = _canonical_json_bytes(
    {
        "schema_id": CYCLOALKANE_C3_C8_RULE_SET_SCHEMA_ID,
        "profile_id": CYCLOALKANE_C3_C8_PROFILE_ID,
        "preparation_scope": CYCLOALKANE_C3_C8_PREPARATION_SCOPE,
        "minimum_carbon_count": _PROFILE_MIN_CARBONS,
        "maximum_carbon_count": _PROFILE_MAX_CARBONS,
        "formula": "C_n_H_2n",
        "carbon_induced_graph": "connected_simple_cycle",
        "carbon_degree_contract": {"carbon_neighbors": 2, "source_hydrogens": 2},
        "hydrogen_degree": 1,
        "bond_state": "exact_single_nonaromatic_stereo_none",
        "formal_charge_state": "source_observed_known_zero",
        "graph_projection_identity_semantics": (
            CYCLOALKANE_C3_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS
        ),
        "constraint_codes": list(CYCLOALKANE_C3_C8_CONSTRAINT_CODES),
        "consumer_ids": list(CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS),
    }
)
CYCLOALKANE_C3_C8_RULE_SET_SHA256 = hashlib.sha256(_RULE_SET_BYTES).hexdigest()


def cycloalkane_c3_c8_rule_set_bytes() -> bytes:
    """Return the frozen graph-profile rule document."""

    return _RULE_SET_BYTES


def _single_nonpolymer_residue(system: AllAtomSystem) -> bool:
    if len(system.residues) != 1 or len(system.chains) != 1:
        return False
    residue = system.residues[0]
    chain = system.chains[0]
    return bool(
        residue.entity_type == "non_polymer"
        and residue.name == "LIG"
        and residue.hetero is True
        and tuple(sorted(residue.atom_indices)) == tuple(range(system.atom_count))
        and tuple(chain.residue_indices) == (0,)
    )


@dataclass(frozen=True, slots=True)
class _GraphEvidence:
    carbon_indices: tuple[int, ...]
    hydrogen_indices: tuple[int, ...]
    carbon_edges: tuple[tuple[int, int], ...]
    carbon_hydrogen_edges: tuple[tuple[int, int], ...]
    component_count: int
    elements_h_c_only: bool
    formula_exact: bool
    source_hydrogens_only: bool
    source_zero_charges_exact: bool
    isotopes_absent: bool
    atom_maps_absent: bool
    partial_charges_absent: bool
    typed_stereo_absent: bool
    aromaticity_absent: bool
    single_bonds_only: bool
    carbon_cycle_exact: bool
    degrees_exact: bool
    projection_document: dict[str, Any]


def _component_count(adjacency: list[set[int]]) -> int:
    remaining = set(range(len(adjacency)))
    count = 0
    while remaining:
        count += 1
        stack = [min(remaining)]
        remaining.remove(stack[0])
        while stack:
            current = stack.pop()
            for neighbor in sorted(adjacency[current]):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
    return count


def _graph_evidence(system: AllAtomSystem) -> _GraphEvidence:
    atom_count = system.atom_count
    expected_indices = tuple(range(atom_count))
    index_contract = tuple(atom.index for atom in system.atoms) == expected_indices
    carbon_indices = tuple(
        atom.index
        for atom in system.atoms
        if atom.element == "C" and atom.atomic_number == 6
    )
    hydrogen_indices = tuple(
        atom.index
        for atom in system.atoms
        if atom.element == "H" and atom.atomic_number == 1
    )
    carbon_set = set(carbon_indices)
    hydrogen_set = set(hydrogen_indices)
    elements_h_c_only = bool(
        index_contract and len(carbon_indices) + len(hydrogen_indices) == atom_count
    )
    adjacency = [set() for _ in range(atom_count)]
    carbon_edges: list[tuple[int, int]] = []
    carbon_hydrogen_edges: list[tuple[int, int]] = []
    single_bonds_only = True
    typed_stereo_absent = all(atom.stereo == "unspecified" for atom in system.atoms)
    aromaticity_absent = not any(atom.aromatic for atom in system.atoms)
    bond_rows: list[dict[str, Any]] = []
    for bond in system.bonds:
        valid_endpoints = bool(
            type(bond.atom_i) is int
            and type(bond.atom_j) is int
            and 0 <= bond.atom_i < bond.atom_j < atom_count
        )
        if valid_endpoints:
            adjacency[bond.atom_i].add(bond.atom_j)
            adjacency[bond.atom_j].add(bond.atom_i)
            pair = (bond.atom_i, bond.atom_j)
            if bond.atom_i in carbon_set and bond.atom_j in carbon_set:
                carbon_edges.append(pair)
            elif (bond.atom_i in carbon_set and bond.atom_j in hydrogen_set) or (
                bond.atom_j in carbon_set and bond.atom_i in hydrogen_set
            ):
                carbon_hydrogen_edges.append(pair)
        if (
            type(bond.order) is not float
            or bond.order != 1.0
            or bond.aromatic is not False
            or bond.stereo != "none"
            or not valid_endpoints
        ):
            single_bonds_only = False
        typed_stereo_absent = typed_stereo_absent and bond.stereo == "none"
        aromaticity_absent = aromaticity_absent and bond.aromatic is False
        bond_rows.append(
            {
                "index": bond.index,
                "atom_indices": [bond.atom_i, bond.atom_j],
                "order_ieee754_binary64_be": struct.pack(">d", bond.order).hex(),
                "aromatic": bond.aromatic,
                "stereo": bond.stereo,
                "source": bond.source,
            }
        )
    component_count = _component_count(adjacency) if atom_count else 0
    carbon_adjacency = {
        index: adjacency[index] & carbon_set for index in carbon_indices
    }
    carbon_cycle_exact = bool(
        _PROFILE_MIN_CARBONS <= len(carbon_indices) <= _PROFILE_MAX_CARBONS
        and len(carbon_edges) == len(carbon_indices)
        and all(len(carbon_adjacency[index]) == 2 for index in carbon_indices)
    )
    if carbon_cycle_exact:
        visited = {carbon_indices[0]}
        stack = [carbon_indices[0]]
        while stack:
            current = stack.pop()
            for neighbor in carbon_adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        carbon_cycle_exact = visited == carbon_set
    degrees_exact = bool(
        elements_h_c_only
        and carbon_cycle_exact
        and all(
            len(adjacency[index]) == 4
            and len(adjacency[index] & carbon_set) == 2
            and len(adjacency[index] & hydrogen_set) == 2
            for index in carbon_indices
        )
        and all(
            len(adjacency[index]) == 1
            and next(iter(adjacency[index]), None) in carbon_set
            for index in hydrogen_indices
        )
    )
    source_hydrogens_only = bool(
        hydrogen_indices
        and all(
            atom.metadata.get("hydrogen_origin") == "source"
            for atom in system.atoms
            if atom.index in hydrogen_set
        )
    )
    source_zero_charges_exact = all(
        atom.formal_charge_known is True
        and type(atom.formal_charge) is int
        and atom.formal_charge == 0
        and atom.metadata.get("formal_charge_source") == "sdf_v2000_atom_block"
        for atom in system.atoms
    )
    isotopes_absent = all(atom.isotope_mass_number is None for atom in system.atoms)
    atom_maps_absent = all(atom.atom_map is None for atom in system.atoms)
    partial_charges_absent = all(atom.partial_charge_e is None for atom in system.atoms)
    formula_exact = bool(
        _PROFILE_MIN_CARBONS <= len(carbon_indices) <= _PROFILE_MAX_CARBONS
        and len(hydrogen_indices) == 2 * len(carbon_indices)
    )
    atom_rows = [
        {
            "index": atom.index,
            "element": atom.element,
            "atomic_number": atom.atomic_number,
            "formal_charge": atom.formal_charge,
            "formal_charge_known": atom.formal_charge_known,
            "isotope_mass_number": atom.isotope_mass_number,
            "atom_map": atom.atom_map,
            "aromatic": atom.aromatic,
            "stereo": atom.stereo,
            "hydrogen_origin": atom.metadata.get("hydrogen_origin"),
            "degree": len(adjacency[atom.index]) if atom.index < atom_count else -1,
            "carbon_neighbor_count": (
                len(adjacency[atom.index] & carbon_set)
                if atom.index < atom_count
                else -1
            ),
            "hydrogen_neighbor_count": (
                len(adjacency[atom.index] & hydrogen_set)
                if atom.index < atom_count
                else -1
            ),
        }
        for atom in system.atoms
    ]
    projection_document = {
        "schema_id": CYCLOALKANE_C3_C8_GRAPH_PROJECTION_SCHEMA_ID,
        "profile_id": CYCLOALKANE_C3_C8_PROFILE_ID,
        "identity_semantics": (CYCLOALKANE_C3_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS),
        "atom_count": atom_count,
        "bond_count": len(system.bonds),
        "component_count": component_count,
        "carbon_atom_indices": list(carbon_indices),
        "hydrogen_atom_indices": list(hydrogen_indices),
        "carbon_edges": [list(edge) for edge in sorted(carbon_edges)],
        "carbon_hydrogen_edges": [list(edge) for edge in sorted(carbon_hydrogen_edges)],
        "atom_rows": atom_rows,
        "bond_rows": sorted(bond_rows, key=lambda row: row["index"]),
        "formula_exact": formula_exact,
        "carbon_cycle_exact": carbon_cycle_exact,
        "degrees_exact": degrees_exact,
        "source_hydrogens_only": source_hydrogens_only,
        "source_zero_charges_exact": source_zero_charges_exact,
    }
    return _GraphEvidence(
        carbon_indices=carbon_indices,
        hydrogen_indices=hydrogen_indices,
        carbon_edges=tuple(sorted(carbon_edges)),
        carbon_hydrogen_edges=tuple(sorted(carbon_hydrogen_edges)),
        component_count=component_count,
        elements_h_c_only=elements_h_c_only,
        formula_exact=formula_exact,
        source_hydrogens_only=source_hydrogens_only,
        source_zero_charges_exact=source_zero_charges_exact,
        isotopes_absent=isotopes_absent,
        atom_maps_absent=atom_maps_absent,
        partial_charges_absent=partial_charges_absent,
        typed_stereo_absent=typed_stereo_absent,
        aromaticity_absent=aromaticity_absent,
        single_bonds_only=single_bonds_only,
        carbon_cycle_exact=carbon_cycle_exact,
        degrees_exact=degrees_exact,
        projection_document=projection_document,
    )


@dataclass(frozen=True, slots=True)
class _DerivedProfile:
    system: AllAtomSystem
    chemistry: dict[str, Any]
    preparation: dict[str, Any]
    graph: _GraphEvidence
    constraints: tuple[tuple[str, bool], ...]
    status: str


def _constraint_results(
    system: AllAtomSystem,
    chemistry: dict[str, Any],
    preparation: dict[str, Any],
    graph: _GraphEvidence,
) -> tuple[tuple[str, bool], ...]:
    attached_observation_schema_id = system.provenance.metadata.get(
        "parser_observation_schema_id"
    )
    attached_observation_sha256 = system.provenance.metadata.get(
        "parser_observation_sha256"
    )
    recomputed_observation_sha256 = parser_observation_sha256(system)
    values = {
        "current_all_atom_schema": system.schema_id == ALL_ATOM_SCHEMA_ID,
        "canonical_state_valid": bool(
            chemistry.get("canonical_validation_valid") is True
            and preparation.get("canonical_validation_valid") is True
        ),
        "canonical_topology_digest_available": bool(
            chemistry.get("canonical_topology_digest_available") is True
            and preparation.get("canonical_topology_digest_available") is True
            and chemistry.get("canonical_topology_sha256")
            == preparation.get("canonical_topology_sha256")
        ),
        "generic_report_versions_current": bool(
            chemistry.get("schema_version") == CHEMISTRY_COVERAGE_SCHEMA_VERSION
            and preparation.get("schema_version") == PREPARATION_REPORT_SCHEMA_VERSION
        ),
        "sdf_v2000_source_pedigree": bool(
            preparation.get("source_format") == "sdf_v2000"
            and preparation.get("parser_pedigree_id") == _SDF_V2000_PARSER_PEDIGREE_ID
        ),
        "source_binding_self_consistent": bool(
            preparation.get("source_digest_available") is True
            and preparation.get("parser_observation_self_consistent") is True
        ),
        "parser_observation_digest_bound": bool(
            attached_observation_schema_id == PARSER_OBSERVATION_SCHEMA_ID
            and type(attached_observation_sha256) is str
            and hmac.compare_digest(
                attached_observation_sha256,
                recomputed_observation_sha256,
            )
        ),
        "single_component": graph.component_count == 1,
        "single_nonpolymer_residue": _single_nonpolymer_residue(system),
        "carbon_count_c3_c8": (
            _PROFILE_MIN_CARBONS <= len(graph.carbon_indices) <= _PROFILE_MAX_CARBONS
        ),
        "elements_h_c_only": graph.elements_h_c_only,
        "exact_cycloalkane_formula_c_n_h_2n": graph.formula_exact,
        "formal_charges_source_observed_known_zero": bool(
            graph.source_zero_charges_exact
            and chemistry.get("unknown_formal_charge_count") == 0
            and chemistry.get("net_formal_charge") == 0
            and chemistry.get("net_formal_charge_known") is True
            and preparation.get("unknown_formal_charge_count") == 0
            and preparation.get("net_formal_charge") == 0
        ),
        "isotopes_absent": graph.isotopes_absent,
        "atom_maps_absent": graph.atom_maps_absent,
        "partial_charges_absent": graph.partial_charges_absent,
        "typed_stereo_absent": graph.typed_stereo_absent,
        "aromaticity_absent": graph.aromaticity_absent,
        "single_bonds_only": graph.single_bonds_only,
        "source_observed_hydrogens_only": bool(
            graph.source_hydrogens_only
            and preparation.get("metadata_observed_source_hydrogen_count")
            == len(graph.hydrogen_indices)
            and preparation.get("adapter_generated_hydrogen_count") == 0
            and preparation.get("unknown_hydrogen_origin_count") == 0
        ),
        "carbon_subgraph_connected_simple_cycle": graph.carbon_cycle_exact,
        "exact_carbon_hydrogen_degrees": graph.degrees_exact,
        "generic_reports_remain_nonpromoted": bool(
            chemistry.get("chemistry_supported") is False
            and chemistry.get("parameterability_assessed") is False
            and chemistry.get("claim_safe") is False
            and preparation.get("preparation_ready") is False
            and preparation.get("claim_safe") is False
        ),
    }
    return tuple(
        (code, bool(values[code])) for code in CYCLOALKANE_C3_C8_CONSTRAINT_CODES
    )


def _status(
    chemistry: dict[str, Any],
    preparation: dict[str, Any],
    constraints: tuple[tuple[str, bool], ...],
) -> str:
    if (
        chemistry.get("canonical_validation_valid") is not True
        or preparation.get("canonical_validation_valid") is not True
        or preparation.get("parser_observation_self_consistent") is not True
    ):
        return "invalid"
    if any(not passed for _, passed in constraints):
        return "unsupported"
    return "available"


def _derive_from_snapshot(snapshot: bytes) -> _DerivedProfile:
    if type(snapshot) is not bytes:
        raise TypeError("canonical system snapshot must be exact bytes")
    system = deserialize_all_atom_system(snapshot)
    if serialize_all_atom_system(system) != snapshot:
        raise ValueError("stored system snapshot is not canonical")
    chemistry_report = analyze_canonical_chemistry(system)
    preparation_report = analyze_molecular_preparation(system)
    chemistry = chemistry_report.to_dict()
    preparation = preparation_report.to_dict()
    graph = _graph_evidence(system)
    constraints = _constraint_results(system, chemistry, preparation, graph)
    status = _status(chemistry, preparation, constraints)
    if status not in CYCLOALKANE_C3_C8_PROFILE_STATUSES:
        raise ValueError("unknown cycloalkane profile status")
    return _DerivedProfile(system, chemistry, preparation, graph, constraints, status)


def _blockers(
    status: str,
    failed_constraint_codes: tuple[str, ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if status == "invalid":
        blockers.append("cycloalkane_c3_c8_profile_state_invalid")
    elif status == "unsupported":
        blockers.append("cycloalkane_c3_c8_profile_unsupported")
    blockers.extend(
        f"cycloalkane_c3_c8_constraint_failed_{code}"
        for code in failed_constraint_codes
    )
    blockers.extend(_ALWAYS_BLOCKERS)
    return tuple(blockers)


@dataclass(frozen=True, init=False, slots=True)
class CycloalkaneC3C8ProfileReport:
    """Factory-only self-recomputing graph-local cycloalkane report."""

    _canonical_system_bytes: bytes = field(repr=False)
    _canonical_system_sha256: str = field(repr=False)

    def __init__(
        self,
        *,
        canonical_system_bytes: bytes,
        canonical_system_sha256: str,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError("CycloalkaneC3C8ProfileReport is factory-only")
        if type(canonical_system_bytes) is not bytes:
            raise TypeError("canonical_system_bytes must be exact bytes")
        if (
            type(canonical_system_sha256) is not str
            or len(canonical_system_sha256) != 64
            or hashlib.sha256(canonical_system_bytes).hexdigest()
            != canonical_system_sha256
        ):
            raise ValueError("canonical system snapshot digest is inconsistent")
        _derive_from_snapshot(canonical_system_bytes)
        object.__setattr__(self, "_canonical_system_bytes", canonical_system_bytes)
        object.__setattr__(self, "_canonical_system_sha256", canonical_system_sha256)

    def _derive(self) -> _DerivedProfile:
        if type(self._canonical_system_bytes) is not bytes:
            raise TypeError("canonical system snapshot binding must be exact bytes")
        if (
            type(self._canonical_system_sha256) is not str
            or hashlib.sha256(self._canonical_system_bytes).hexdigest()
            != self._canonical_system_sha256
        ):
            raise ValueError("canonical system snapshot digest binding is inconsistent")
        return _derive_from_snapshot(self._canonical_system_bytes)

    @property
    def system(self) -> AllAtomSystem:
        return self._derive().system

    @property
    def status(self) -> str:
        return self._derive().status

    @property
    def profile_chemistry_supported(self) -> bool:
        return self._derive().status == "available"

    @property
    def profile_graph_preparation_ready(self) -> bool:
        return self._derive().status == "available"

    @property
    def failed_constraint_codes(self) -> tuple[str, ...]:
        return tuple(code for code, passed in self._derive().constraints if not passed)

    @property
    def blockers(self) -> tuple[str, ...]:
        derived = self._derive()
        return _blockers(derived.status, self.failed_constraint_codes)

    @property
    def graph_projection_sha256(self) -> str:
        return _sha256_document(self._derive().graph.projection_document)

    @property
    def report_sha256(self) -> str:
        return _sha256_document(self._core_dict())

    def _core_dict(self) -> dict[str, Any]:
        derived = self._derive()
        failed = tuple(code for code, passed in derived.constraints if not passed)
        available = derived.status == "available"
        carbon_count = len(derived.graph.carbon_indices)
        hydrogen_count = len(derived.graph.hydrogen_indices)
        attached_observation_sha256 = derived.system.provenance.metadata.get(
            "parser_observation_sha256"
        )
        recomputed_observation_sha256 = parser_observation_sha256(derived.system)
        return {
            "schema_id": CYCLOALKANE_C3_C8_PROFILE_SCHEMA_ID,
            "schema_version": CYCLOALKANE_C3_C8_PROFILE_SCHEMA_VERSION,
            "profile_id": CYCLOALKANE_C3_C8_PROFILE_ID,
            "profile_preparation_scope": CYCLOALKANE_C3_C8_PREPARATION_SCOPE,
            "eligible_consumer_ids": list(CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS),
            "rule_set_schema_id": CYCLOALKANE_C3_C8_RULE_SET_SCHEMA_ID,
            "rule_set_sha256": CYCLOALKANE_C3_C8_RULE_SET_SHA256,
            "canonical_system_snapshot_sha256": self._canonical_system_sha256,
            "system_schema_id": derived.system.schema_id,
            "canonical_topology_schema_id": derived.chemistry.get(
                "canonical_topology_schema_id"
            ),
            "canonical_topology_sha256": derived.chemistry.get(
                "canonical_topology_sha256"
            ),
            "chemistry_report_schema_version": derived.chemistry.get("schema_version"),
            "chemistry_report_sha256": derived.chemistry.get("report_sha256"),
            "preparation_report_schema_version": derived.preparation.get(
                "schema_version"
            ),
            "preparation_report_sha256": derived.preparation.get("report_sha256"),
            "source_format": derived.preparation.get("source_format"),
            "source_sha256": derived.preparation.get("source_sha256"),
            "source_digest_available": derived.preparation.get(
                "source_digest_available"
            ),
            "parser_pedigree_id": derived.preparation.get("parser_pedigree_id"),
            "parser_observation_self_consistent": derived.preparation.get(
                "parser_observation_self_consistent"
            ),
            "parser_observation_schema_id": derived.system.provenance.metadata.get(
                "parser_observation_schema_id"
            ),
            "attached_parser_observation_sha256": attached_observation_sha256,
            "recomputed_parser_observation_sha256": (recomputed_observation_sha256),
            "parser_observation_sha256_equal": bool(
                type(attached_observation_sha256) is str
                and hmac.compare_digest(
                    attached_observation_sha256,
                    recomputed_observation_sha256,
                )
            ),
            "source_authentication_status": _SOURCE_AUTHENTICATION_STATUS,
            "source_authenticated": False,
            "graph_projection_schema_id": (
                CYCLOALKANE_C3_C8_GRAPH_PROJECTION_SCHEMA_ID
            ),
            "graph_projection_identity_semantics": (
                CYCLOALKANE_C3_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS
            ),
            "graph_projection_sha256": _sha256_document(
                derived.graph.projection_document
            ),
            "graph_projection": derived.graph.projection_document,
            "constraint_results": [
                {"code": code, "passed": passed} for code, passed in derived.constraints
            ],
            "failed_constraint_codes": list(failed),
            "status": derived.status,
            "carbon_atom_count": carbon_count,
            "hydrogen_atom_count": hydrogen_count,
            "molecular_formula": f"C{carbon_count}H{hydrogen_count}",
            "molecule_label": _MOLECULE_LABELS.get(carbon_count) if available else None,
            "profile_chemistry_supported": available,
            "profile_graph_preparation_ready": available,
            "global_molecular_preparation_ready": False,
            "parameterability_assessed": False,
            "parameterizable": False,
            "physics_supported": False,
            "runtime_eligible": False,
            "execution_authorized": False,
            "energy_evaluation_authorized": False,
            "force_evaluation_authorized": False,
            "minimization_authorized": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": list(_blockers(derived.status, failed)),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._core_dict()
        payload["report_sha256"] = _sha256_document(payload)
        return payload

    def matches_system(self, system: AllAtomSystem) -> bool:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        return self.to_dict() == analyze_cycloalkane_c3_c8_profile(system).to_dict()


class CycloalkaneC3C8ProfileError(RuntimeError):
    """Raised when the bounded graph-local profile is required but unavailable."""

    def __init__(self, report: CycloalkaneC3C8ProfileReport) -> None:
        if type(report) is not CycloalkaneC3C8ProfileReport:
            raise TypeError("report must be a CycloalkaneC3C8ProfileReport")
        if report.profile_graph_preparation_ready:
            raise ValueError("report must not already satisfy the profile")
        self.report = report
        self.status = report.status
        self.failed_constraint_codes = report.failed_constraint_codes
        preview = ", ".join(self.failed_constraint_codes[:4]) or self.status
        super().__init__(f"cycloalkane C3-C8 graph profile is unavailable: {preview}")


class CycloalkaneC3C8ConsumerError(ValueError):
    """Raised when a caller is outside the explicit audit-consumer allowlist."""

    def __init__(self, consumer_id: str) -> None:
        if type(consumer_id) is not str:
            raise TypeError("consumer_id must be an exact string")
        self.consumer_id = consumer_id
        self.eligible_consumer_ids = CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS
        super().__init__(
            "cycloalkane C3-C8 graph profile consumer is not authorized: "
            f"{consumer_id!r}"
        )


def analyze_cycloalkane_c3_c8_profile(
    system: AllAtomSystem,
) -> CycloalkaneC3C8ProfileReport:
    """Analyze the bounded graph-local C3--C8 profile without global promotion."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    snapshot = serialize_all_atom_system(system)
    _derive_from_snapshot(snapshot)
    return CycloalkaneC3C8ProfileReport(
        canonical_system_bytes=snapshot,
        canonical_system_sha256=hashlib.sha256(snapshot).hexdigest(),
        _factory_token=_FACTORY_TOKEN,
    )


def require_cycloalkane_c3_c8_graph_profile(
    system: AllAtomSystem,
    *,
    consumer_id: str,
) -> CycloalkaneC3C8ProfileReport:
    """Return fresh audit-only graph evidence or raise a typed profile error."""

    if type(consumer_id) is not str:
        raise TypeError("consumer_id must be an exact string")
    if consumer_id not in CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS:
        raise CycloalkaneC3C8ConsumerError(consumer_id)
    report = analyze_cycloalkane_c3_c8_profile(system)
    if not report.profile_graph_preparation_ready:
        raise CycloalkaneC3C8ProfileError(report)
    return report


__all__ = [
    "CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS",
    "CYCLOALKANE_C3_C8_CONSTRAINT_CODES",
    "CYCLOALKANE_C3_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS",
    "CYCLOALKANE_C3_C8_GRAPH_PROJECTION_SCHEMA_ID",
    "CYCLOALKANE_C3_C8_PREPARATION_SCOPE",
    "CYCLOALKANE_C3_C8_PROFILE_ID",
    "CYCLOALKANE_C3_C8_PROFILE_SCHEMA_ID",
    "CYCLOALKANE_C3_C8_PROFILE_SCHEMA_VERSION",
    "CYCLOALKANE_C3_C8_PROFILE_STATUSES",
    "CYCLOALKANE_C3_C8_RULE_SET_SCHEMA_ID",
    "CYCLOALKANE_C3_C8_RULE_SET_SHA256",
    "CycloalkaneC3C8ConsumerError",
    "CycloalkaneC3C8ProfileError",
    "CycloalkaneC3C8ProfileReport",
    "analyze_cycloalkane_c3_c8_profile",
    "cycloalkane_c3_c8_rule_set_bytes",
    "require_cycloalkane_c3_c8_graph_profile",
]
