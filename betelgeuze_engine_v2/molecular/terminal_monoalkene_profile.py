"""Bounded graph-local evidence for unbranched terminal monoalkenes C2--C8.

This additive profile accepts only parser-owned SDF V2000 systems whose live
graph is a source-explicit-H, neutral, unbranched terminal monoalkene.  It
establishes exact source graph identity and closure of a source bond-order
ledger only.  The carbon path is a connectivity definition, not coordinate
linearity, and the ledger is not independent valence, unsaturation, or
electronic-structure validation.

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


TERMINAL_MONOALKENE_C2_C8_PROFILE_SCHEMA_VERSION = "1.0.0"
TERMINAL_MONOALKENE_C2_C8_PROFILE_SCHEMA_ID = (
    "betelgeuze.terminal_monoalkene_c2_c8_graph_profile/1.0.0"
)
TERMINAL_MONOALKENE_C2_C8_PROFILE_ID = (
    "source_observed_explicit_h_neutral_unbranched_terminal_monoalkene_c2_c8/1.0.0"
)
TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_SCHEMA_ID = (
    "betelgeuze.terminal_monoalkene_c2_c8_graph_projection/1.0.0"
)
TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS = (
    "source_indexed_exact_projection_not_order_independent_graph_isomorphism_identity"
)
TERMINAL_MONOALKENE_C2_C8_PREPARATION_SCOPE = (
    "source_observed_graph_local_unbranched_terminal_monoalkene_identity_"
    "and_bond_order_valence_ledger_only"
)
TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS = (
    "terminal_monoalkene_c2_c8_graph_profile_audit",
)
TERMINAL_MONOALKENE_C2_C8_PROFILE_STATUSES = frozenset(
    {"invalid", "unsupported", "available"}
)
TERMINAL_MONOALKENE_C2_C8_CONSTRAINT_CODES = (
    "current_all_atom_schema",
    "canonical_state_valid",
    "canonical_topology_digest_available",
    "generic_report_versions_current",
    "sdf_v2000_source_pedigree",
    "source_binding_self_consistent",
    "parser_observation_digest_bound",
    "single_component",
    "single_nonpolymer_residue",
    "carbon_count_c2_c8",
    "elements_h_c_only",
    "exact_terminal_monoalkene_formula_c_n_h_2n",
    "formal_charges_source_observed_known_zero",
    "isotopes_absent",
    "atom_maps_absent",
    "partial_charges_absent",
    "typed_stereo_absent",
    "aromaticity_absent",
    "source_observed_hydrogens_only",
    "source_sdf_atom_marker_ledger_exact",
    "carbon_subgraph_connected_simple_path",
    "exact_one_terminal_carbon_double_bond",
    "source_sdf_bond_order_ledger_exact",
    "exact_atom_bond_order_valence_ledger",
    "generic_reports_remain_nonpromoted",
)

_SDF_V2000_PARSER_PEDIGREE_ID = "betelgeuze.sdf_v2000_parser/1.5.0"
_SDF_ATOM_METADATA_KEYS = frozenset(
    {
        "sdf_source_atom_index",
        "sdf_atom_map",
        "hydrogen_origin",
        "formal_charge_source",
    }
)
_SDF_BOND_METADATA_KEYS = frozenset(
    {
        "sdf_source_bond_index",
        "sdf_source_atom_i",
        "sdf_source_atom_j",
        "sdf_bond_type",
    }
)
_SOURCE_AUTHENTICATION_STATUS = "digest_bound_not_authenticated"
_FACTORY_TOKEN = object()
_PROFILE_MIN_CARBONS = 2
_PROFILE_MAX_CARBONS = 8
_UNBRANCHED_PATH_DEFINITION = "unbranched_carbon_simple_path_not_coordinate_geometry"
_BOND_ORDER_LEDGER_SEMANTICS = (
    "source_sdf_annotation_ledger_not_independent_bond_order_valence_"
    "unsaturation_or_electronic_structure_validation"
)
_MOLECULE_LABELS = {
    2: "ethene",
    3: "propene",
    4: "but-1-ene",
    5: "pent-1-ene",
    6: "hex-1-ene",
    7: "hept-1-ene",
    8: "oct-1-ene",
}
_ALWAYS_BLOCKERS = (
    "source_digest_is_not_authentication",
    "profile_bound_c2_c8_is_not_general_alkene_support_or_c9_chemistry_rejection",
    "unbranched_carbon_path_is_not_coordinate_linearity",
    "source_bond_order_ledger_is_not_independent_bond_order_valence_unsaturation_or_electronic_structure_validation",
    "profile_graph_preparation_is_not_global_molecular_preparation",
    "environmental_ph_and_protonation_correctness_not_assessed",
    "tautomer_state_not_assessed",
    "e_z_applicability_and_assignment_not_assessed",
    "cip_substituent_equivalence_not_assessed",
    "conformation_and_geometry_quality_not_assessed",
    "parameterability_not_assessed",
    "force_field_atom_types_not_assigned",
    "partial_charges_not_assigned",
    "force_field_parameters_not_assigned",
    "physics_not_supported",
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


TERMINAL_MONOALKENE_C2_C8_RULE_SET_SCHEMA_ID = (
    "betelgeuze.terminal_monoalkene_c2_c8_graph_rules/1.0.0"
)
_RULE_SET_BYTES = _canonical_json_bytes(
    {
        "schema_id": TERMINAL_MONOALKENE_C2_C8_RULE_SET_SCHEMA_ID,
        "profile_id": TERMINAL_MONOALKENE_C2_C8_PROFILE_ID,
        "preparation_scope": TERMINAL_MONOALKENE_C2_C8_PREPARATION_SCOPE,
        "minimum_carbon_count": _PROFILE_MIN_CARBONS,
        "maximum_carbon_count": _PROFILE_MAX_CARBONS,
        "formula": "C_n_H_2n",
        "carbon_induced_graph": "connected_simple_path",
        "terminal_double_definition": (
            "c2_both_double_endpoints_are_path_endpoints_else_exactly_one"
        ),
        "carbon_bond_state": (
            "exactly_one_terminal_order_2_else_order_1_nonaromatic_stereo_none"
        ),
        "carbon_hydrogen_bond_state": "order_1_nonaromatic_stereo_none",
        "atom_bond_order_valence_ledger": {"carbon": 4, "hydrogen": 1},
        "formal_charge_state": "source_observed_known_zero",
        "source_atom_marker_state": (
            "one_based_sdf_source_index_serial_zero_map_charge_origin_and_hydrogen_origin"
        ),
        "source_atom_metadata_keys": sorted(_SDF_ATOM_METADATA_KEYS),
        "source_bond_metadata_keys": sorted(_SDF_BOND_METADATA_KEYS),
        "path_definition": _UNBRANCHED_PATH_DEFINITION,
        "bond_order_ledger_semantics": _BOND_ORDER_LEDGER_SEMANTICS,
        "graph_projection_identity_semantics": (
            TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS
        ),
        "constraint_codes": list(TERMINAL_MONOALKENE_C2_C8_CONSTRAINT_CODES),
        "consumer_ids": list(TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS),
    }
)
TERMINAL_MONOALKENE_C2_C8_RULE_SET_SHA256 = hashlib.sha256(_RULE_SET_BYTES).hexdigest()


def terminal_monoalkene_c2_c8_rule_set_bytes() -> bytes:
    """Return the immutable graph-profile rule document."""

    return _RULE_SET_BYTES


def _single_nonpolymer_residue(system: AllAtomSystem) -> bool:
    if len(system.residues) != 1 or len(system.chains) != 1:
        return False
    residue = system.residues[0]
    chain = system.chains[0]
    return bool(
        residue.index == 0
        and residue.name == "LIG"
        and residue.chain_index == 0
        and residue.sequence_number == 1
        and residue.insertion_code == ""
        and residue.entity_type == "non_polymer"
        and residue.hetero is True
        and tuple(sorted(residue.atom_indices)) == tuple(range(system.atom_count))
        and set(residue.metadata) == {"source"}
        and residue.metadata.get("source") == "sdf_v2000_single_record"
        and chain.index == 0
        and chain.chain_id == "L"
        and tuple(chain.residue_indices) == (0,)
        and chain.entity_id == "ligand"
        and set(chain.metadata) == {"source"}
        and chain.metadata.get("source") == "sdf_v2000_single_record"
    )


def _component_count(adjacency: list[set[int]]) -> int:
    remaining = set(range(len(adjacency)))
    count = 0
    while remaining:
        count += 1
        first = min(remaining)
        remaining.remove(first)
        stack = [first]
        while stack:
            current = stack.pop()
            for neighbor in sorted(adjacency[current]):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
    return count


def _canonical_carbon_path(
    carbon_adjacency: dict[int, set[int]],
) -> tuple[int, ...]:
    endpoints = sorted(
        index for index, neighbors in carbon_adjacency.items() if len(neighbors) == 1
    )
    if len(endpoints) != 2:
        return ()
    paths: list[tuple[int, ...]] = []
    for start in endpoints:
        path = [start]
        previous: int | None = None
        current = start
        while True:
            choices = sorted(
                carbon_adjacency[current]
                - ({previous} if previous is not None else set())
            )
            if not choices:
                break
            if len(choices) != 1:
                return ()
            previous, current = current, choices[0]
            path.append(current)
        paths.append(tuple(path))
    return min(paths) if paths and paths[0][::-1] == paths[1] else ()


@dataclass(frozen=True, slots=True)
class _GraphEvidence:
    carbon_indices: tuple[int, ...]
    hydrogen_indices: tuple[int, ...]
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
    carbon_path_exact: bool
    terminal_double_exact: bool
    source_atom_marker_ledger_exact: bool
    source_bond_order_ledger_exact: bool
    atom_valence_ledger_exact: bool
    double_bond_index: int | None
    double_bond_source_index: int | None
    double_bond_endpoints: tuple[int, int] | None
    terminal_double_endpoint_count: int
    canonical_carbon_path: tuple[int, ...]
    projection_document: dict[str, Any]


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
    integer_valence_ledger = [0] * atom_count
    carbon_edges: list[tuple[int, int]] = []
    carbon_hydrogen_edges: list[tuple[int, int]] = []
    double_rows: list[tuple[int, int | None, int, int]] = []
    source_bond_order_ledger_exact = True
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
        atom_i_is_c = valid_endpoints and bond.atom_i in carbon_set
        atom_j_is_c = valid_endpoints and bond.atom_j in carbon_set
        atom_i_is_h = valid_endpoints and bond.atom_i in hydrogen_set
        atom_j_is_h = valid_endpoints and bond.atom_j in hydrogen_set
        if atom_i_is_c and atom_j_is_c:
            role = "carbon_carbon"
            carbon_edges.append((bond.atom_i, bond.atom_j))
        elif (atom_i_is_c and atom_j_is_h) or (atom_i_is_h and atom_j_is_c):
            role = "carbon_hydrogen"
            carbon_hydrogen_edges.append((bond.atom_i, bond.atom_j))
        else:
            role = "outside_profile"
        order_integer = (
            1
            if type(bond.order) is float and bond.order == 1.0
            else 2
            if type(bond.order) is float and bond.order == 2.0
            else None
        )
        metadata_source_index = bond.metadata.get("sdf_source_bond_index")
        metadata_atom_i = bond.metadata.get("sdf_source_atom_i")
        metadata_atom_j = bond.metadata.get("sdf_source_atom_j")
        metadata_bond_type = bond.metadata.get("sdf_bond_type")
        metadata_endpoints = (
            {metadata_atom_i - 1, metadata_atom_j - 1}
            if type(metadata_atom_i) is int and type(metadata_atom_j) is int
            else set()
        )
        metadata_exact = bool(
            bond.source == "sdf_v2000"
            and set(bond.metadata) == _SDF_BOND_METADATA_KEYS
            and type(metadata_source_index) is int
            and metadata_source_index == bond.index + 1
            and type(metadata_atom_i) is int
            and type(metadata_atom_j) is int
            and metadata_endpoints == {bond.atom_i, bond.atom_j}
            and type(metadata_bond_type) is int
            and metadata_bond_type == order_integer
        )
        state_exact = bool(
            valid_endpoints
            and order_integer is not None
            and bond.aromatic is False
            and bond.stereo == "none"
            and metadata_exact
            and (
                (role == "carbon_carbon" and order_integer in {1, 2})
                or (role == "carbon_hydrogen" and order_integer == 1)
            )
        )
        source_bond_order_ledger_exact = source_bond_order_ledger_exact and state_exact
        if valid_endpoints and order_integer is not None:
            integer_valence_ledger[bond.atom_i] += order_integer
            integer_valence_ledger[bond.atom_j] += order_integer
        if role == "carbon_carbon" and order_integer == 2:
            source_index = bond.metadata.get("sdf_source_bond_index")
            double_rows.append(
                (
                    bond.index,
                    source_index if type(source_index) is int else None,
                    bond.atom_i,
                    bond.atom_j,
                )
            )
        typed_stereo_absent = typed_stereo_absent and bond.stereo == "none"
        aromaticity_absent = aromaticity_absent and bond.aromatic is False
        bond_rows.append(
            {
                "index": bond.index,
                "atom_indices": [bond.atom_i, bond.atom_j],
                "role": role,
                "order_ieee754_binary64_be": struct.pack(">d", bond.order).hex(),
                "aromatic": bond.aromatic,
                "stereo": bond.stereo,
                "source": bond.source,
                "sdf_source_bond_index": bond.metadata.get("sdf_source_bond_index"),
                "sdf_source_atom_i": bond.metadata.get("sdf_source_atom_i"),
                "sdf_source_atom_j": bond.metadata.get("sdf_source_atom_j"),
                "sdf_bond_type": bond.metadata.get("sdf_bond_type"),
            }
        )
    component_count = _component_count(adjacency) if atom_count else 0
    carbon_adjacency = {
        index: adjacency[index] & carbon_set for index in carbon_indices
    }
    carbon_path_exact = bool(
        len(carbon_indices) >= _PROFILE_MIN_CARBONS
        and len(carbon_edges) == len(carbon_indices) - 1
        and sum(len(neighbors) == 1 for neighbors in carbon_adjacency.values()) == 2
        and all(len(neighbors) in {1, 2} for neighbors in carbon_adjacency.values())
    )
    if carbon_path_exact:
        visited = {carbon_indices[0]}
        stack = [carbon_indices[0]]
        while stack:
            current = stack.pop()
            for neighbor in carbon_adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        carbon_path_exact = visited == carbon_set
    canonical_carbon_path = (
        _canonical_carbon_path(carbon_adjacency) if carbon_path_exact else ()
    )
    double_bond_index = double_rows[0][0] if len(double_rows) == 1 else None
    double_bond_source_index = double_rows[0][1] if len(double_rows) == 1 else None
    double_bond_endpoints = (
        tuple(sorted(double_rows[0][2:])) if len(double_rows) == 1 else None
    )
    terminal_double_endpoint_count = (
        sum(len(carbon_adjacency[index]) == 1 for index in double_bond_endpoints)
        if double_bond_endpoints is not None
        else 0
    )
    terminal_double_exact = bool(
        carbon_path_exact
        and len(double_rows) == 1
        and (
            terminal_double_endpoint_count == 2
            if len(carbon_indices) == 2
            else terminal_double_endpoint_count == 1
        )
    )
    formula_exact = bool(len(hydrogen_indices) == 2 * len(carbon_indices))
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
    source_atom_marker_ledger_exact = all(
        type(atom.serial) is int
        and atom.serial == atom.index + 1
        and set(atom.metadata) == _SDF_ATOM_METADATA_KEYS
        and type(atom.metadata.get("sdf_source_atom_index")) is int
        and atom.metadata.get("sdf_source_atom_index") == atom.index + 1
        and type(atom.metadata.get("sdf_atom_map")) is int
        and atom.metadata.get("sdf_atom_map") == 0
        and type(atom.metadata.get("formal_charge_source")) is str
        and atom.metadata.get("formal_charge_source") == "sdf_v2000_atom_block"
        and type(atom.metadata.get("hydrogen_origin")) is str
        and atom.metadata.get("hydrogen_origin")
        == ("source" if atom.element == "H" else "not_hydrogen")
        for atom in system.atoms
    )
    isotopes_absent = all(atom.isotope_mass_number is None for atom in system.atoms)
    atom_maps_absent = all(atom.atom_map is None for atom in system.atoms)
    partial_charges_absent = all(atom.partial_charge_e is None for atom in system.atoms)
    atom_valence_ledger_exact = bool(
        source_bond_order_ledger_exact
        and elements_h_c_only
        and all(integer_valence_ledger[index] == 4 for index in carbon_indices)
        and all(
            integer_valence_ledger[index] == 1
            and len(adjacency[index]) == 1
            and next(iter(adjacency[index]), None) in carbon_set
            for index in hydrogen_indices
        )
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
            "serial": atom.serial,
            "sdf_source_atom_index": atom.metadata.get("sdf_source_atom_index"),
            "sdf_atom_map": atom.metadata.get("sdf_atom_map"),
            "formal_charge_source": atom.metadata.get("formal_charge_source"),
            "degree": len(adjacency[atom.index]),
            "carbon_neighbor_count": len(adjacency[atom.index] & carbon_set),
            "hydrogen_neighbor_count": len(adjacency[atom.index] & hydrogen_set),
            "integer_bond_order_valence_ledger": integer_valence_ledger[atom.index],
        }
        for atom in system.atoms
    ]
    projection_document = {
        "schema_id": TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_SCHEMA_ID,
        "profile_id": TERMINAL_MONOALKENE_C2_C8_PROFILE_ID,
        "identity_semantics": (
            TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS
        ),
        "path_definition": _UNBRANCHED_PATH_DEFINITION,
        "bond_order_ledger_semantics": _BOND_ORDER_LEDGER_SEMANTICS,
        "atom_count": atom_count,
        "bond_count": len(system.bonds),
        "component_count": component_count,
        "carbon_atom_indices": list(carbon_indices),
        "hydrogen_atom_indices": list(hydrogen_indices),
        "canonical_carbon_path": list(canonical_carbon_path),
        "carbon_edges": [list(edge) for edge in sorted(carbon_edges)],
        "carbon_hydrogen_edges": [list(edge) for edge in sorted(carbon_hydrogen_edges)],
        "double_bond_index": double_bond_index,
        "double_bond_source_index": double_bond_source_index,
        "double_bond_endpoints": (
            list(double_bond_endpoints) if double_bond_endpoints is not None else None
        ),
        "terminal_double_endpoint_count": terminal_double_endpoint_count,
        "atom_rows": atom_rows,
        "bond_rows": sorted(bond_rows, key=lambda row: row["index"]),
        "formula_exact": formula_exact,
        "carbon_path_exact": carbon_path_exact,
        "terminal_double_exact": terminal_double_exact,
        "source_hydrogens_only": source_hydrogens_only,
        "source_zero_charges_exact": source_zero_charges_exact,
        "source_atom_marker_ledger_exact": source_atom_marker_ledger_exact,
        "source_bond_order_ledger_exact": source_bond_order_ledger_exact,
        "atom_valence_ledger_exact": atom_valence_ledger_exact,
    }
    return _GraphEvidence(
        carbon_indices=carbon_indices,
        hydrogen_indices=hydrogen_indices,
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
        carbon_path_exact=carbon_path_exact,
        terminal_double_exact=terminal_double_exact,
        source_atom_marker_ledger_exact=source_atom_marker_ledger_exact,
        source_bond_order_ledger_exact=source_bond_order_ledger_exact,
        atom_valence_ledger_exact=atom_valence_ledger_exact,
        double_bond_index=double_bond_index,
        double_bond_source_index=double_bond_source_index,
        double_bond_endpoints=double_bond_endpoints,
        terminal_double_endpoint_count=terminal_double_endpoint_count,
        canonical_carbon_path=canonical_carbon_path,
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
        "carbon_count_c2_c8": (
            _PROFILE_MIN_CARBONS <= len(graph.carbon_indices) <= _PROFILE_MAX_CARBONS
        ),
        "elements_h_c_only": graph.elements_h_c_only,
        "exact_terminal_monoalkene_formula_c_n_h_2n": graph.formula_exact,
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
        "source_observed_hydrogens_only": bool(
            graph.source_hydrogens_only
            and preparation.get("metadata_observed_source_hydrogen_count")
            == len(graph.hydrogen_indices)
            and preparation.get("adapter_generated_hydrogen_count") == 0
            and preparation.get("unknown_hydrogen_origin_count") == 0
        ),
        "source_sdf_atom_marker_ledger_exact": (graph.source_atom_marker_ledger_exact),
        "carbon_subgraph_connected_simple_path": graph.carbon_path_exact,
        "exact_one_terminal_carbon_double_bond": graph.terminal_double_exact,
        "source_sdf_bond_order_ledger_exact": (graph.source_bond_order_ledger_exact),
        "exact_atom_bond_order_valence_ledger": (graph.atom_valence_ledger_exact),
        "generic_reports_remain_nonpromoted": bool(
            chemistry.get("chemistry_supported") is False
            and chemistry.get("parameterability_assessed") is False
            and chemistry.get("claim_safe") is False
            and preparation.get("preparation_ready") is False
            and preparation.get("claim_safe") is False
        ),
    }
    return tuple(
        (code, bool(values[code]))
        for code in TERMINAL_MONOALKENE_C2_C8_CONSTRAINT_CODES
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
    chemistry = analyze_canonical_chemistry(system).to_dict()
    preparation = analyze_molecular_preparation(system).to_dict()
    graph = _graph_evidence(system)
    constraints = _constraint_results(system, chemistry, preparation, graph)
    status = _status(chemistry, preparation, constraints)
    if status not in TERMINAL_MONOALKENE_C2_C8_PROFILE_STATUSES:
        raise ValueError("unknown terminal monoalkene profile status")
    return _DerivedProfile(system, chemistry, preparation, graph, constraints, status)


def _blockers(
    status: str,
    failed_constraint_codes: tuple[str, ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if status == "invalid":
        blockers.append("terminal_monoalkene_c2_c8_profile_state_invalid")
    elif status == "unsupported":
        blockers.append("terminal_monoalkene_c2_c8_profile_unsupported")
    blockers.extend(
        f"terminal_monoalkene_c2_c8_constraint_failed_{code}"
        for code in failed_constraint_codes
    )
    blockers.extend(_ALWAYS_BLOCKERS)
    return tuple(blockers)


@dataclass(frozen=True, init=False, slots=True)
class TerminalMonoalkeneC2C8ProfileReport:
    """Factory-only self-recomputing graph-local monoalkene report."""

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
            raise TypeError("TerminalMonoalkeneC2C8ProfileReport is factory-only")
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
        failed = tuple(code for code, passed in derived.constraints if not passed)
        return _blockers(derived.status, failed)

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
            "schema_id": TERMINAL_MONOALKENE_C2_C8_PROFILE_SCHEMA_ID,
            "schema_version": TERMINAL_MONOALKENE_C2_C8_PROFILE_SCHEMA_VERSION,
            "profile_id": TERMINAL_MONOALKENE_C2_C8_PROFILE_ID,
            "profile_preparation_scope": (TERMINAL_MONOALKENE_C2_C8_PREPARATION_SCOPE),
            "eligible_consumer_ids": list(TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS),
            "rule_set_schema_id": TERMINAL_MONOALKENE_C2_C8_RULE_SET_SCHEMA_ID,
            "rule_set_sha256": TERMINAL_MONOALKENE_C2_C8_RULE_SET_SHA256,
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
                TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_SCHEMA_ID
            ),
            "graph_projection_identity_semantics": (
                TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS
            ),
            "unbranched_path_definition": _UNBRANCHED_PATH_DEFINITION,
            "bond_order_valence_ledger_semantics": _BOND_ORDER_LEDGER_SEMANTICS,
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
            "canonical_carbon_path": list(derived.graph.canonical_carbon_path),
            "double_bond_index": derived.graph.double_bond_index,
            "double_bond_source_index": derived.graph.double_bond_source_index,
            "double_bond_endpoints": (
                list(derived.graph.double_bond_endpoints)
                if derived.graph.double_bond_endpoints is not None
                else None
            ),
            "terminal_double_endpoint_count": (
                derived.graph.terminal_double_endpoint_count
            ),
            "source_bond_order_ledger_closed": (
                derived.graph.source_bond_order_ledger_exact
            ),
            "source_atom_marker_ledger_closed": (
                derived.graph.source_atom_marker_ledger_exact
            ),
            "atom_bond_order_valence_ledger_closed": (
                derived.graph.atom_valence_ledger_exact
            ),
            "profile_chemistry_supported": available,
            "profile_graph_preparation_ready": available,
            "generic_chemistry_supported": derived.chemistry.get("chemistry_supported"),
            "generic_molecular_preparation_ready": derived.preparation.get(
                "preparation_ready"
            ),
            "global_molecular_preparation_ready": False,
            "e_z_assessed": False,
            "cip_assessed": False,
            "stereochemistry_applicability_assessed": False,
            "source_bond_order_independently_validated": False,
            "electronic_structure_assessed": False,
            "coordinate_linearity_assessed": False,
            "protonation_assessed": False,
            "tautomer_assessed": False,
            "geometry_quality_assessed": False,
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
        return (
            self.to_dict()
            == analyze_terminal_monoalkene_c2_c8_profile(system).to_dict()
        )


class TerminalMonoalkeneC2C8ProfileError(RuntimeError):
    """Raised when the bounded graph-local profile is unavailable."""

    def __init__(self, report: TerminalMonoalkeneC2C8ProfileReport) -> None:
        if type(report) is not TerminalMonoalkeneC2C8ProfileReport:
            raise TypeError("report must be a TerminalMonoalkeneC2C8ProfileReport")
        if report.profile_graph_preparation_ready:
            raise ValueError("report must not already satisfy the profile")
        self.report = report
        self.status = report.status
        self.failed_constraint_codes = report.failed_constraint_codes
        preview = ", ".join(self.failed_constraint_codes[:4]) or self.status
        super().__init__(
            "terminal monoalkene C2-C8 graph profile is unavailable: " + preview
        )


class TerminalMonoalkeneC2C8ConsumerError(ValueError):
    """Raised when a caller is outside the explicit audit-consumer allowlist."""

    def __init__(self, consumer_id: str) -> None:
        if type(consumer_id) is not str:
            raise TypeError("consumer_id must be an exact string")
        self.consumer_id = consumer_id
        self.eligible_consumer_ids = TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS
        super().__init__(
            "terminal monoalkene C2-C8 graph profile consumer is not authorized: "
            f"{consumer_id!r}"
        )


def analyze_terminal_monoalkene_c2_c8_profile(
    system: AllAtomSystem,
) -> TerminalMonoalkeneC2C8ProfileReport:
    """Analyze the bounded graph-local profile without global promotion."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    snapshot = serialize_all_atom_system(system)
    _derive_from_snapshot(snapshot)
    return TerminalMonoalkeneC2C8ProfileReport(
        canonical_system_bytes=snapshot,
        canonical_system_sha256=hashlib.sha256(snapshot).hexdigest(),
        _factory_token=_FACTORY_TOKEN,
    )


def require_terminal_monoalkene_c2_c8_graph_profile(
    system: AllAtomSystem,
    *,
    consumer_id: str,
) -> TerminalMonoalkeneC2C8ProfileReport:
    """Return fresh audit-only graph evidence or raise a typed error."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    if type(consumer_id) is not str:
        raise TypeError("consumer_id must be an exact string")
    if consumer_id not in TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS:
        raise TerminalMonoalkeneC2C8ConsumerError(consumer_id)
    report = analyze_terminal_monoalkene_c2_c8_profile(system)
    if not report.profile_graph_preparation_ready:
        raise TerminalMonoalkeneC2C8ProfileError(report)
    return report


__all__ = [
    "TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS",
    "TERMINAL_MONOALKENE_C2_C8_CONSTRAINT_CODES",
    "TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS",
    "TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_SCHEMA_ID",
    "TERMINAL_MONOALKENE_C2_C8_PREPARATION_SCOPE",
    "TERMINAL_MONOALKENE_C2_C8_PROFILE_ID",
    "TERMINAL_MONOALKENE_C2_C8_PROFILE_SCHEMA_ID",
    "TERMINAL_MONOALKENE_C2_C8_PROFILE_SCHEMA_VERSION",
    "TERMINAL_MONOALKENE_C2_C8_PROFILE_STATUSES",
    "TERMINAL_MONOALKENE_C2_C8_RULE_SET_SCHEMA_ID",
    "TERMINAL_MONOALKENE_C2_C8_RULE_SET_SHA256",
    "TerminalMonoalkeneC2C8ConsumerError",
    "TerminalMonoalkeneC2C8ProfileError",
    "TerminalMonoalkeneC2C8ProfileReport",
    "analyze_terminal_monoalkene_c2_c8_profile",
    "require_terminal_monoalkene_c2_c8_graph_profile",
    "terminal_monoalkene_c2_c8_rule_set_bytes",
]
