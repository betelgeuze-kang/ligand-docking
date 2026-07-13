"""Exact source-observed H2O graph evidence without water-role promotion.

This additive profile recognizes one deliberately narrow parser-owned SDF
V2000 graph: one oxygen, two source-observed hydrogens, and two single O-H
bonds with source-observed known-zero formal charges.  It establishes only
source-indexed graph identity and closure of an integer source bond-order
ledger.  It does not establish a water or solvent role, protonation
correctness, geometry, a water model, periodicity, physics, or runtime use.

The public report is factory-only and retains canonical snapshot bytes.  Every
property is recomputed from that snapshot and fresh generic chemistry and
preparation reports.  Digests are deterministic tamper evidence, not source
authentication.
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


EXACT_H2O_GRAPH_PROFILE_SCHEMA_VERSION = "1.0.0"
EXACT_H2O_GRAPH_PROFILE_SCHEMA_ID = "betelgeuze.exact_h2o_graph_profile/1.0.0"
EXACT_H2O_GRAPH_PROFILE_ID = "source_observed_explicit_h_neutral_h2o_graph/1.0.0"
EXACT_H2O_GRAPH_PROJECTION_SCHEMA_ID = "betelgeuze.exact_h2o_graph_projection/1.0.0"
EXACT_H2O_GRAPH_PROJECTION_IDENTITY_SEMANTICS = (
    "source_indexed_exact_projection_not_order_independent_graph_isomorphism_identity"
)
EXACT_H2O_GRAPH_PREPARATION_SCOPE = (
    "source_observed_graph_local_h2o_identity_and_bond_order_valence_ledger_only"
)
EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS = ("exact_h2o_graph_profile_audit",)
EXACT_H2O_GRAPH_PROFILE_STATUSES = frozenset({"invalid", "unsupported", "available"})
EXACT_H2O_GRAPH_CONSTRAINT_CODES = (
    "current_all_atom_schema",
    "canonical_state_valid",
    "canonical_topology_digest_available",
    "generic_report_versions_current",
    "sdf_v2000_source_pedigree",
    "source_binding_self_consistent",
    "parser_observation_digest_bound",
    "single_component",
    "single_nonpolymer_residue",
    "exact_atom_inventory_o1_h2",
    "formal_charges_source_observed_known_zero",
    "isotopes_absent",
    "atom_maps_absent",
    "partial_charges_absent",
    "typed_stereo_absent",
    "aromaticity_absent",
    "source_observed_hydrogens_only",
    "source_sdf_atom_marker_ledger_exact",
    "exact_two_single_oxygen_hydrogen_bonds",
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
_GRAPH_IDENTITY_SEMANTICS = (
    "exact_source_observed_o1_h2_graph_not_water_or_solvent_role_evidence"
)
_BOND_ORDER_LEDGER_SEMANTICS = (
    "source_sdf_annotation_ledger_not_independent_bond_order_valence_"
    "protonation_or_electronic_structure_validation"
)
_FACTORY_TOKEN = object()
_ALWAYS_BLOCKERS = (
    "source_digest_is_not_authentication",
    "h2o_graph_identity_is_not_water_or_solvent_role_evidence",
    "source_bond_order_ledger_is_not_independent_bond_order_valence_protonation_or_electronic_structure_validation",
    "profile_graph_preparation_is_not_global_molecular_preparation",
    "environmental_ph_and_protonation_correctness_not_assessed",
    "autoionization_and_hydration_state_not_assessed",
    "hydrogen_bonding_not_assessed",
    "bond_lengths_angles_conformation_and_geometry_quality_not_assessed",
    "isotope_speciation_not_assessed",
    "parameterability_not_assessed",
    "force_field_atom_types_not_assigned",
    "partial_charges_not_assigned",
    "force_field_parameters_not_assigned",
    "water_model_not_assigned",
    "constraints_not_assigned",
    "pbc_and_periodicity_not_assessed",
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


EXACT_H2O_GRAPH_RULE_SET_SCHEMA_ID = "betelgeuze.exact_h2o_graph_rules/1.0.0"
_RULE_SET_BYTES = _canonical_json_bytes(
    {
        "schema_id": EXACT_H2O_GRAPH_RULE_SET_SCHEMA_ID,
        "profile_id": EXACT_H2O_GRAPH_PROFILE_ID,
        "preparation_scope": EXACT_H2O_GRAPH_PREPARATION_SCOPE,
        "atom_inventory": {"oxygen": 1, "hydrogen": 2, "total": 3},
        "graph": "one_component_with_exactly_two_single_oxygen_hydrogen_bonds",
        "atom_degree": {"oxygen": 2, "hydrogen": 1},
        "atom_bond_order_valence_ledger": {"oxygen": 2, "hydrogen": 1},
        "formal_charge_state": "source_observed_atom_block_known_zero_per_atom",
        "source_atom_metadata_keys": sorted(_SDF_ATOM_METADATA_KEYS),
        "source_bond_metadata_keys": sorted(_SDF_BOND_METADATA_KEYS),
        "graph_identity_semantics": _GRAPH_IDENTITY_SEMANTICS,
        "bond_order_ledger_semantics": _BOND_ORDER_LEDGER_SEMANTICS,
        "graph_projection_identity_semantics": (
            EXACT_H2O_GRAPH_PROJECTION_IDENTITY_SEMANTICS
        ),
        "constraint_codes": list(EXACT_H2O_GRAPH_CONSTRAINT_CODES),
        "consumer_ids": list(EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS),
    }
)
EXACT_H2O_GRAPH_RULE_SET_SHA256 = hashlib.sha256(_RULE_SET_BYTES).hexdigest()


def exact_h2o_graph_rule_set_bytes() -> bytes:
    """Return immutable canonical rule bytes for the bounded profile."""

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


@dataclass(frozen=True, slots=True)
class _GraphEvidence:
    oxygen_indices: tuple[int, ...]
    hydrogen_indices: tuple[int, ...]
    component_count: int
    atom_inventory_exact: bool
    source_zero_charges_exact: bool
    isotopes_absent: bool
    atom_maps_absent: bool
    partial_charges_absent: bool
    typed_stereo_absent: bool
    aromaticity_absent: bool
    source_hydrogens_only: bool
    source_atom_marker_ledger_exact: bool
    exact_two_single_oh_bonds: bool
    source_bond_order_ledger_exact: bool
    atom_valence_ledger_exact: bool
    oxygen_hydrogen_edges: tuple[tuple[int, int], ...]
    projection_document: dict[str, Any]


def _graph_evidence(system: AllAtomSystem) -> _GraphEvidence:
    atom_count = system.atom_count
    expected_indices = tuple(range(atom_count))
    atom_index_contract = tuple(atom.index for atom in system.atoms) == expected_indices
    oxygen_indices = tuple(
        atom.index
        for atom in system.atoms
        if atom.element == "O" and atom.atomic_number == 8
    )
    hydrogen_indices = tuple(
        atom.index
        for atom in system.atoms
        if atom.element == "H" and atom.atomic_number == 1
    )
    oxygen_set = set(oxygen_indices)
    hydrogen_set = set(hydrogen_indices)
    atom_inventory_exact = bool(
        atom_index_contract
        and atom_count == 3
        and len(oxygen_indices) == 1
        and len(hydrogen_indices) == 2
    )
    bond_index_contract = tuple(bond.index for bond in system.bonds) == tuple(
        range(len(system.bonds))
    )
    adjacency = [set() for _ in range(atom_count)]
    integer_valence_ledger = [0] * atom_count
    oh_edges: list[tuple[int, int]] = []
    bond_rows: list[dict[str, Any]] = []
    source_bond_order_ledger_exact = bond_index_contract
    typed_stereo_absent = all(atom.stereo == "unspecified" for atom in system.atoms)
    aromaticity_absent = not any(atom.aromatic for atom in system.atoms)
    for bond in system.bonds:
        valid_endpoints = bool(
            type(bond.atom_i) is int
            and type(bond.atom_j) is int
            and 0 <= bond.atom_i < bond.atom_j < atom_count
        )
        if valid_endpoints:
            adjacency[bond.atom_i].add(bond.atom_j)
            adjacency[bond.atom_j].add(bond.atom_i)
        endpoint_set = {bond.atom_i, bond.atom_j} if valid_endpoints else set()
        role_exact = bool(
            valid_endpoints
            and len(endpoint_set & oxygen_set) == 1
            and len(endpoint_set & hydrogen_set) == 1
        )
        order_integer = 1 if type(bond.order) is float and bond.order == 1.0 else None
        source_index = bond.metadata.get("sdf_source_bond_index")
        source_atom_i = bond.metadata.get("sdf_source_atom_i")
        source_atom_j = bond.metadata.get("sdf_source_atom_j")
        source_bond_type = bond.metadata.get("sdf_bond_type")
        source_endpoint_set = (
            {source_atom_i - 1, source_atom_j - 1}
            if type(source_atom_i) is int and type(source_atom_j) is int
            else set()
        )
        metadata_exact = bool(
            bond.source == "sdf_v2000"
            and set(bond.metadata) == _SDF_BOND_METADATA_KEYS
            and type(source_index) is int
            and source_index == bond.index + 1
            and type(source_atom_i) is int
            and type(source_atom_j) is int
            and source_endpoint_set == endpoint_set
            and type(source_bond_type) is int
            and source_bond_type == 1
        )
        state_exact = bool(
            role_exact
            and order_integer == 1
            and bond.aromatic is False
            and bond.stereo == "none"
            and metadata_exact
        )
        source_bond_order_ledger_exact = source_bond_order_ledger_exact and state_exact
        if valid_endpoints and order_integer is not None:
            integer_valence_ledger[bond.atom_i] += order_integer
            integer_valence_ledger[bond.atom_j] += order_integer
        if role_exact:
            oh_edges.append(tuple(sorted((bond.atom_i, bond.atom_j))))
        typed_stereo_absent = typed_stereo_absent and bond.stereo == "none"
        aromaticity_absent = aromaticity_absent and bond.aromatic is False
        bond_rows.append(
            {
                "index": bond.index,
                "atom_indices": [bond.atom_i, bond.atom_j],
                "role": "oxygen_hydrogen" if role_exact else "outside_profile",
                "order_ieee754_binary64_be": struct.pack(">d", bond.order).hex(),
                "aromatic": bond.aromatic,
                "stereo": bond.stereo,
                "source": bond.source,
                "sdf_source_bond_index": source_index,
                "sdf_source_atom_i": source_atom_i,
                "sdf_source_atom_j": source_atom_j,
                "sdf_bond_type": source_bond_type,
            }
        )
    component_count = _component_count(adjacency) if atom_count else 0
    exact_two_single_oh_bonds = bool(
        atom_inventory_exact
        and component_count == 1
        and len(system.bonds) == 2
        and len(oh_edges) == 2
        and source_bond_order_ledger_exact
        and len(adjacency[oxygen_indices[0]]) == 2
        and all(len(adjacency[index]) == 1 for index in hydrogen_indices)
    )
    source_zero_charges_exact = all(
        atom.formal_charge_known is True
        and type(atom.formal_charge) is int
        and atom.formal_charge == 0
        and atom.metadata.get("formal_charge_source") == "sdf_v2000_atom_block"
        for atom in system.atoms
    )
    source_hydrogens_only = bool(
        len(hydrogen_indices) == 2
        and all(
            atom.metadata.get("hydrogen_origin") == "source"
            for atom in system.atoms
            if atom.index in hydrogen_set
        )
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
        and exact_two_single_oh_bonds
        and all(integer_valence_ledger[index] == 2 for index in oxygen_indices)
        and all(integer_valence_ledger[index] == 1 for index in hydrogen_indices)
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
            "serial": atom.serial,
            "hydrogen_origin": atom.metadata.get("hydrogen_origin"),
            "sdf_source_atom_index": atom.metadata.get("sdf_source_atom_index"),
            "sdf_atom_map": atom.metadata.get("sdf_atom_map"),
            "formal_charge_source": atom.metadata.get("formal_charge_source"),
            "degree": len(adjacency[atom.index]),
            "integer_bond_order_valence_ledger": integer_valence_ledger[atom.index],
        }
        for atom in system.atoms
    ]
    projection_document = {
        "schema_id": EXACT_H2O_GRAPH_PROJECTION_SCHEMA_ID,
        "profile_id": EXACT_H2O_GRAPH_PROFILE_ID,
        "identity_semantics": EXACT_H2O_GRAPH_PROJECTION_IDENTITY_SEMANTICS,
        "graph_identity_semantics": _GRAPH_IDENTITY_SEMANTICS,
        "bond_order_ledger_semantics": _BOND_ORDER_LEDGER_SEMANTICS,
        "atom_count": atom_count,
        "bond_count": len(system.bonds),
        "component_count": component_count,
        "oxygen_atom_indices": list(oxygen_indices),
        "hydrogen_atom_indices": list(hydrogen_indices),
        "oxygen_hydrogen_edges": [list(edge) for edge in sorted(oh_edges)],
        "atom_rows": atom_rows,
        "bond_rows": sorted(bond_rows, key=lambda row: row["index"]),
        "atom_inventory_exact": atom_inventory_exact,
        "exact_two_single_oxygen_hydrogen_bonds": exact_two_single_oh_bonds,
        "source_hydrogens_only": source_hydrogens_only,
        "source_zero_charges_exact": source_zero_charges_exact,
        "source_atom_marker_ledger_exact": source_atom_marker_ledger_exact,
        "source_bond_order_ledger_exact": source_bond_order_ledger_exact,
        "atom_valence_ledger_exact": atom_valence_ledger_exact,
    }
    return _GraphEvidence(
        oxygen_indices=oxygen_indices,
        hydrogen_indices=hydrogen_indices,
        component_count=component_count,
        atom_inventory_exact=atom_inventory_exact,
        source_zero_charges_exact=source_zero_charges_exact,
        isotopes_absent=isotopes_absent,
        atom_maps_absent=atom_maps_absent,
        partial_charges_absent=partial_charges_absent,
        typed_stereo_absent=typed_stereo_absent,
        aromaticity_absent=aromaticity_absent,
        source_hydrogens_only=source_hydrogens_only,
        source_atom_marker_ledger_exact=source_atom_marker_ledger_exact,
        exact_two_single_oh_bonds=exact_two_single_oh_bonds,
        source_bond_order_ledger_exact=source_bond_order_ledger_exact,
        atom_valence_ledger_exact=atom_valence_ledger_exact,
        oxygen_hydrogen_edges=tuple(sorted(oh_edges)),
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
            system.provenance.metadata.get("parser_observation_schema_id")
            == PARSER_OBSERVATION_SCHEMA_ID
            and type(attached_observation_sha256) is str
            and hmac.compare_digest(
                attached_observation_sha256,
                recomputed_observation_sha256,
            )
        ),
        "single_component": graph.component_count == 1,
        "single_nonpolymer_residue": _single_nonpolymer_residue(system),
        "exact_atom_inventory_o1_h2": graph.atom_inventory_exact,
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
            and preparation.get("metadata_observed_source_hydrogen_count") == 2
            and preparation.get("adapter_generated_hydrogen_count") == 0
            and preparation.get("unknown_hydrogen_origin_count") == 0
        ),
        "source_sdf_atom_marker_ledger_exact": (graph.source_atom_marker_ledger_exact),
        "exact_two_single_oxygen_hydrogen_bonds": (graph.exact_two_single_oh_bonds),
        "source_sdf_bond_order_ledger_exact": (graph.source_bond_order_ledger_exact),
        "exact_atom_bond_order_valence_ledger": graph.atom_valence_ledger_exact,
        "generic_reports_remain_nonpromoted": bool(
            chemistry.get("chemistry_supported") is False
            and chemistry.get("parameterability_assessed") is False
            and chemistry.get("claim_safe") is False
            and preparation.get("preparation_ready") is False
            and preparation.get("claim_safe") is False
        ),
    }
    return tuple(
        (code, bool(values[code])) for code in EXACT_H2O_GRAPH_CONSTRAINT_CODES
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
    if status not in EXACT_H2O_GRAPH_PROFILE_STATUSES:
        raise ValueError("unknown exact H2O graph profile status")
    return _DerivedProfile(system, chemistry, preparation, graph, constraints, status)


def _blockers(status: str, failed: tuple[str, ...]) -> tuple[str, ...]:
    blockers: list[str] = []
    if status == "invalid":
        blockers.append("exact_h2o_graph_profile_state_invalid")
    elif status == "unsupported":
        blockers.append("exact_h2o_graph_profile_unsupported")
    blockers.extend(f"exact_h2o_graph_constraint_failed_{code}" for code in failed)
    blockers.extend(_ALWAYS_BLOCKERS)
    return tuple(blockers)


@dataclass(frozen=True, init=False, slots=True)
class ExactH2OGraphProfileReport:
    """Factory-only self-recomputing exact H2O graph-local report."""

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
            raise TypeError("ExactH2OGraphProfileReport is factory-only")
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
        attached_observation_sha256 = derived.system.provenance.metadata.get(
            "parser_observation_sha256"
        )
        recomputed_observation_sha256 = parser_observation_sha256(derived.system)
        return {
            "schema_id": EXACT_H2O_GRAPH_PROFILE_SCHEMA_ID,
            "schema_version": EXACT_H2O_GRAPH_PROFILE_SCHEMA_VERSION,
            "profile_id": EXACT_H2O_GRAPH_PROFILE_ID,
            "profile_preparation_scope": EXACT_H2O_GRAPH_PREPARATION_SCOPE,
            "eligible_consumer_ids": list(EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS),
            "rule_set_schema_id": EXACT_H2O_GRAPH_RULE_SET_SCHEMA_ID,
            "rule_set_sha256": EXACT_H2O_GRAPH_RULE_SET_SHA256,
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
            "parser_observation_schema_id": (
                derived.system.provenance.metadata.get("parser_observation_schema_id")
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
            "graph_projection_schema_id": EXACT_H2O_GRAPH_PROJECTION_SCHEMA_ID,
            "graph_projection_identity_semantics": (
                EXACT_H2O_GRAPH_PROJECTION_IDENTITY_SEMANTICS
            ),
            "h2o_graph_identity_semantics": _GRAPH_IDENTITY_SEMANTICS,
            "bond_order_valence_ledger_semantics": (_BOND_ORDER_LEDGER_SEMANTICS),
            "graph_projection_sha256": _sha256_document(
                derived.graph.projection_document
            ),
            "graph_projection": derived.graph.projection_document,
            "constraint_results": [
                {"code": code, "passed": passed} for code, passed in derived.constraints
            ],
            "failed_constraint_codes": list(failed),
            "status": derived.status,
            "oxygen_atom_count": len(derived.graph.oxygen_indices),
            "hydrogen_atom_count": len(derived.graph.hydrogen_indices),
            "molecular_formula": "H2O" if available else None,
            "molecule_label": "source_observed_h2o_graph" if available else None,
            "oxygen_atom_indices": list(derived.graph.oxygen_indices),
            "hydrogen_atom_indices": list(derived.graph.hydrogen_indices),
            "oxygen_hydrogen_edges": [
                list(edge) for edge in derived.graph.oxygen_hydrogen_edges
            ],
            "source_bond_order_ledger_closed": (
                derived.graph.source_bond_order_ledger_exact
            ),
            "source_atom_marker_ledger_closed": (
                derived.graph.source_atom_marker_ledger_exact
            ),
            "atom_bond_order_valence_ledger_closed": (
                derived.graph.atom_valence_ledger_exact
            ),
            "canonical_water_entity_marker_observed": any(
                residue.entity_type == "water" for residue in derived.system.residues
            ),
            "profile_chemistry_supported": available,
            "profile_graph_preparation_ready": available,
            "generic_chemistry_supported": derived.chemistry.get("chemistry_supported"),
            "generic_molecular_preparation_ready": derived.preparation.get(
                "preparation_ready"
            ),
            "global_molecular_preparation_ready": False,
            "water_role_assessed": False,
            "solvent_role_assessed": False,
            "hydration_state_assessed": False,
            "ph_assessed": False,
            "protonation_correctness_assessed": False,
            "autoionization_assessed": False,
            "hydrogen_bonding_assessed": False,
            "source_bond_order_independently_validated": False,
            "valence_independently_validated": False,
            "electronic_structure_assessed": False,
            "geometry_quality_assessed": False,
            "bond_lengths_assessed": False,
            "bond_angle_assessed": False,
            "conformation_assessed": False,
            "isotope_speciation_assessed": False,
            "parameterability_assessed": False,
            "parameterizable": False,
            "atom_types_assigned": False,
            "partial_charges_assigned": False,
            "force_field_parameters_assigned": False,
            "water_model_assigned": False,
            "constraints_assigned": False,
            "pbc_assessed": False,
            "periodicity_assessed": False,
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
        return self.to_dict() == analyze_exact_h2o_graph_profile(system).to_dict()


class ExactH2OGraphProfileError(RuntimeError):
    """Raised when the bounded exact H2O graph profile is unavailable."""

    def __init__(self, report: ExactH2OGraphProfileReport) -> None:
        if type(report) is not ExactH2OGraphProfileReport:
            raise TypeError("report must be an ExactH2OGraphProfileReport")
        if report.profile_graph_preparation_ready:
            raise ValueError("report must not already satisfy the profile")
        self.report = report
        self.status = report.status
        self.failed_constraint_codes = report.failed_constraint_codes
        preview = ", ".join(self.failed_constraint_codes[:4]) or self.status
        super().__init__("exact H2O graph profile is unavailable: " + preview)


class ExactH2OGraphConsumerError(ValueError):
    """Raised when a caller is outside the audit-only allowlist."""

    def __init__(self, consumer_id: str) -> None:
        if type(consumer_id) is not str:
            raise TypeError("consumer_id must be an exact string")
        self.consumer_id = consumer_id
        self.eligible_consumer_ids = EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS
        super().__init__(
            f"exact H2O graph profile consumer is not authorized: {consumer_id!r}"
        )


def analyze_exact_h2o_graph_profile(
    system: AllAtomSystem,
) -> ExactH2OGraphProfileReport:
    """Analyze exact graph-local H2O evidence without global promotion."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    snapshot = serialize_all_atom_system(system)
    _derive_from_snapshot(snapshot)
    return ExactH2OGraphProfileReport(
        canonical_system_bytes=snapshot,
        canonical_system_sha256=hashlib.sha256(snapshot).hexdigest(),
        _factory_token=_FACTORY_TOKEN,
    )


def require_exact_h2o_graph_profile(
    system: AllAtomSystem,
    *,
    consumer_id: str,
) -> ExactH2OGraphProfileReport:
    """Return fresh audit-only graph evidence or raise a typed error."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    if type(consumer_id) is not str:
        raise TypeError("consumer_id must be an exact string")
    if consumer_id not in EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS:
        raise ExactH2OGraphConsumerError(consumer_id)
    report = analyze_exact_h2o_graph_profile(system)
    if not report.profile_graph_preparation_ready:
        raise ExactH2OGraphProfileError(report)
    return report


__all__ = [
    "EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS",
    "EXACT_H2O_GRAPH_CONSTRAINT_CODES",
    "EXACT_H2O_GRAPH_PREPARATION_SCOPE",
    "EXACT_H2O_GRAPH_PROFILE_ID",
    "EXACT_H2O_GRAPH_PROFILE_SCHEMA_ID",
    "EXACT_H2O_GRAPH_PROFILE_SCHEMA_VERSION",
    "EXACT_H2O_GRAPH_PROFILE_STATUSES",
    "EXACT_H2O_GRAPH_PROJECTION_IDENTITY_SEMANTICS",
    "EXACT_H2O_GRAPH_PROJECTION_SCHEMA_ID",
    "EXACT_H2O_GRAPH_RULE_SET_SCHEMA_ID",
    "EXACT_H2O_GRAPH_RULE_SET_SHA256",
    "ExactH2OGraphConsumerError",
    "ExactH2OGraphProfileError",
    "ExactH2OGraphProfileReport",
    "analyze_exact_h2o_graph_profile",
    "exact_h2o_graph_rule_set_bytes",
    "require_exact_h2o_graph_profile",
]
