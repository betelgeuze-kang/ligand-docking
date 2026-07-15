"""Prospective graph/family-disjoint population preflight for SPICE evidence.

This module strictly replays the frozen C1--C4 observation evidence and its
source-review packet, then reports why the current conformer split is not
graph- or family-disjoint.  Strict replay decodes and validates the source
targets, but population and split decisions consume topology and partition
metadata only.  It also freezes topology-only prerequisites for a future
expanded scientific population.  It does not acquire expanded data, use target
values for population decisions, fit a model, validate parameters, or authorize
runtime use.
"""

from __future__ import annotations

from dataclasses import InitVar, asdict, dataclass
import hashlib
import json
import math
from typing import Any, Iterable, Mapping

from .spice_c1c4_quantum_reference import (
    SPICE_C1C4_QUANTUM_REFERENCE_SCHEMA_ID,
    load_spice_c1c4_quantum_reference_evidence,
)
from .spice_c1c4_source_review_packet import (
    SPICE_C1C4_SOURCE_REVIEW_PACKET_SCHEMA_ID,
    load_spice_c1c4_source_review_packet,
)


SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_SCHEMA_ID = (
    "betelgeuze.spice_graph_family_disjoint_population_preflight/1.0.0"
)
SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_ID = (
    "spice_hydrocarbon_target_independent_hierarchical_graph_family_split_"
    "preflight/1.0.0"
)
SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_CLAIM_SCOPE = (
    "prospective_metadata_only_graph_family_split_requirements_no_scientific_evidence"
)

_FROZEN_SCHEMA_ID = SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_SCHEMA_ID
_FROZEN_PROTOCOL_ID = SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_ID
_FROZEN_CLAIM_SCOPE = SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_CLAIM_SCOPE
_FROZEN_SOURCE_SCHEMA_ID = SPICE_C1C4_QUANTUM_REFERENCE_SCHEMA_ID
_FROZEN_SOURCE_REVIEW_PACKET_SCHEMA_ID = SPICE_C1C4_SOURCE_REVIEW_PACKET_SCHEMA_ID

_GROUP_ORDER = ("c", "cc", "ccc", "cccc")
_PARTITION_ORDER = ("fit", "selection", "holdout")
_FAMILY_ID = "neutral_singlet_explicit_h_linear_alkane"
_FACTORY_TOKEN = object()
_GRAPH_HASH_DOMAIN = b"spice-hydrocarbon-canonical-tree-graph-v1\0"
_TOPOLOGY_RECEIPT_HASH_DOMAIN = b"spice-population-topology-receipt-v1\0"

_C1_H3 = "c_single_valence4_c1_h3"
_C2_H2 = "c_single_valence4_c2_h2"
_H_AT_C2_H2 = "h_attached_c_single_valence4_c2_h2"

_C5_NEW_ANGLE_KEYS = ((_C2_H2, _C2_H2, _C2_H2),)
_C5_NEW_PROPER_KEYS = (
    (_C1_H3, _C2_H2, _C2_H2, _C2_H2),
    (_C2_H2, _C2_H2, _C2_H2, _H_AT_C2_H2),
)
_C6_ONLY_NEW_PROPER_KEYS = ((_C2_H2, _C2_H2, _C2_H2, _C2_H2),)
_FROZEN_CURRENT_GRAPH_ROWS = (
    ("c", "aba02557b2c9cb089288307c7ceb2dbfafb65d3f1cf4e43b3cd60193b5474c20"),
    ("cc", "1dd4a184939eb977a437b6e760eae448aef2a3990f09fe51bc04eb927f149293"),
    ("ccc", "e9c44323a148dd0bbe9cd9cc559ca6ae97e98a585bb92d8b7a16cfca6bcc2fd0"),
    ("cccc", "c35a8d7eae753900b4ee0b86669c5b047359122aa7ed8122f612362ae00e19f9"),
)
_FROZEN_TOPOLOGY_RECEIPT_SHA256 = (
    "560e0331afad68873a6d62fb2577f9af6ee7434b656e24c4231811f82238d805"
)

_PROTOCOL_DOCUMENT: Mapping[str, Any] = {
    "schema_id": SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_SCHEMA_ID,
    "protocol_id": SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_ID,
    "claim_scope": SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_CLAIM_SCOPE,
    "current_baseline": {
        "source_schema_id": SPICE_C1C4_QUANTUM_REFERENCE_SCHEMA_ID,
        "source_review_packet_schema_id": SPICE_C1C4_SOURCE_REVIEW_PACKET_SCHEMA_ID,
        "graph_count": 4,
        "family_count": 1,
        "family_id": _FAMILY_ID,
        "partition_graph_overlap_count": 4,
        "partition_family_overlap_count": 1,
        "graph_disjoint": False,
        "family_disjoint": False,
        "time_disjoint": False,
        "release_disjoint": False,
        "public_holdout_blind_to_humans": False,
        "bond_angle_proper_key_counts": [6, 9, 7],
        "canonical_graph_sha256_by_group": [
            list(row) for row in _FROZEN_CURRENT_GRAPH_ROWS
        ],
        "topology_receipt_sha256": _FROZEN_TOPOLOGY_RECEIPT_SHA256,
    },
    "prerequisite_receipts": {
        "source_review_packet_integrity_required": True,
        "whole_file_stream_receipt_required": True,
        "subset_extraction_receipt_required": True,
        "independent_human_license_decision_required": True,
        "publisher_signature_is_separate_from_byte_integrity": True,
        "current_receipts_close_scientific_admission": False,
    },
    "identity": {
        "graph_identity": (
            "atom_order_independent_labeled_tree_over_atomic_number_bond_order_"
            "molecular_charge_and_multiplicity_with_isotope_and_stereo_"
            "explicitly_absent"
        ),
        "isotope_stereo_scope": "explicitly_absent_only",
        "isotope_or_stereo_present_requires_new_atom_labeled_identity_schema": True,
        "family_taxonomy": (
            "derived_only_from_topology_and_partition_metadata_without_"
            "branching_on_coordinates_energy_or_force_targets"
        ),
        "environment_match_keys_are_graph_or_family_identity": False,
        "canonical_graph_sha256_recipe": {
            "algorithm": "sha256",
            "preimage": "domain_bytes_then_canonical_json_document",
            "domain_hex": _GRAPH_HASH_DOMAIN.hex(),
            "atom_domain": [1, 6],
            "bond_order_domain_and_text": {
                "1.0": "1.0",
                "2.0": "2.0",
                "3.0": "3.0",
            },
            "rooted_node_encoding": (
                "Z{atomic_number}({comma_joined_ascending_lexicographic_child_tokens})"
            ),
            "child_token_encoding": "{bond_order_text}:{child_rooted_node}",
            "canonical_root_choice": (
                "ascending_lexicographic_minimum_rooted_node_over_all_atom_roots"
            ),
            "document_fields": [
                "canonical_tree",
                "isotope_state",
                "molecular_charge",
                "molecular_multiplicity",
                "stereo_state",
            ],
            "molecular_charge_contract": (
                "finite_integer_valued_exact_float_negative_zero_normalized_to_"
                "positive_zero"
            ),
            "molecular_multiplicity_contract": "positive_exact_integer",
            "isotope_state_literal": "explicitly_absent",
            "stereo_state_literal": "explicitly_absent",
            "canonical_json": {
                "sort_keys": True,
                "separators": [",", ":"],
                "ensure_ascii": True,
                "allow_nan": False,
                "encoding": "ascii",
                "trailing_bytes_hex": "0a",
            },
        },
        "topology_receipt_sha256_recipe": {
            "algorithm": "sha256",
            "preimage": "domain_bytes_then_canonical_json_document",
            "domain_hex": _TOPOLOGY_RECEIPT_HASH_DOMAIN.hex(),
            "document_fields": ["family_id", "graph_rows", "key_counts"],
            "graph_rows_group_order": list(_GROUP_ORDER),
            "key_counts_order": ["bond", "angle", "proper"],
            "canonical_json": {
                "sort_keys": True,
                "separators": [",", ":"],
                "ensure_ascii": True,
                "allow_nan": False,
                "encoding": "ascii",
                "trailing_bytes_hex": "0a",
            },
        },
    },
    "split_hierarchy": [
        "release",
        "chemistry_family",
        "parent_or_scaffold",
        "exact_molecular_graph",
        "source_related_conformer_or_geometry_cluster",
        "record",
    ],
    "split_units": {
        "graph_disjoint_lane": "entire_exact_molecular_graph",
        "family_disjoint_lane": "entire_chemistry_family",
        "record_force_scalar_or_related_pair_independent_assignment": False,
    },
    "no_leak": {
        "always_zero_intersections": [
            "record_id",
            "geometry_sha256",
            "qcarchive_molecule_id",
            "qcarchive_molecule_hash",
            "source_pair_or_lineage_id",
            "canonical_graph_sha256",
        ],
        "family_lane_additional_zero_intersection": "chemistry_family_id",
        "same_release_or_time_may_be_called_disjoint": False,
    },
    "linear_coverage_expansion": {
        "current_c1_c4_key_counts": {"bond": 6, "angle": 9, "proper": 7},
        "c5_delta_vs_c1_c4": {"bond": 0, "angle": 1, "proper": 2},
        "c5_new_angle_keys": [list(row) for row in _C5_NEW_ANGLE_KEYS],
        "c5_new_proper_keys": [list(row) for row in _C5_NEW_PROPER_KEYS],
        "c6_delta_vs_c1_c4": {"bond": 0, "angle": 1, "proper": 3},
        "c6_delta_vs_c5": {"bond": 0, "angle": 0, "proper": 1},
        "c6_only_new_proper_keys": [list(row) for row in _C6_ONLY_NEW_PROPER_KEYS],
        "c7_and_longer_add_no_local_keys_after_c1_c6_under_exact_scheme": True,
        "c5_c6_current_status": "outside_current_c1_c4_parameter_key_universe",
        "c5_c6_accuracy_holdout_eligible": False,
        "versioned_applicability_key_basis_observability_expansion_required": True,
        "topology_key_coverage_is_parameter_sufficiency": False,
    },
    "prospective_lanes": {
        "in_family_graph_disjoint": {
            "fit_prerequisite": (
                "whole_c1_c6_graphs_under_a_new_versioned_population_to_cover_"
                "the_declared_local_key_universe"
            ),
            "selection_and_holdout": "whole_distinct_unseen_c7_or_longer_graphs",
            "target_based_reassignment": False,
            "old_public_holdout_reuse_requires_new_version_and_claim_reset": True,
        },
        "family_disjoint": {
            "current_non_linear_families": "ood_or_abstention_only",
            "accuracy_eligibility_requires_separate_versioned_applicability_"
            "coverage_and_observability": True,
            "public_family_challenge_is_blind": False,
        },
    },
    "target_semantics": {
        "source_integrity_replay_decodes_and_validates_target_values": True,
        "population_or_split_decision_uses_target_values": False,
        "energy": "within_graph_relative_energy_or_fit_only_graph_intercept",
        "shared_cross_molecule_absolute_energy_offset": False,
        "source_gradient": "dE_dR_not_force",
        "force_target": "negative_source_gradient",
        "unit_conversion": "existing_versioned_codata_single_round_convention",
        "projection_centering_clipping_or_denoising_without_new_version": False,
    },
    "candidate_sequence": [
        "source_receipts_and_independent_license_review",
        "topology_only_population_inventory",
        "immutable_split_and_threshold_manifest",
        "fit_only_scaling_typing_basis_and_candidate",
        "selection_only_model_choice",
        "freeze_candidate_parameter_and_method_receipts",
        "one_shot_public_graph_holdout",
        "family_ood_or_eligible_family_evaluation",
        "separate_externally_sealed_blind_evaluation",
    ],
    "metrics": {
        "aggregation": "equal_graph_and_when_applicable_equal_family",
        "energy": "pair_block_relative_energy_mae_and_rmse",
        "force": "per_record_then_per_graph_force_rmse",
        "uncertainty_resampling_unit": (
            "outer_graph_or_family_with_source_pair_blocks_nested_within_graph"
        ),
        "source_pair_blocks_are_outer_independent_units": False,
        "force_scalars_are_independent_samples": False,
        "threshold_manifest_sha256_frozen_before_candidate_fit": True,
    },
    "nonpromotion": {
        "expanded_source_data_acquired": False,
        "expanded_target_view_available": False,
        "candidate_fitting_performed": False,
        "candidate_parameter_set_available": False,
        "scientific_validation_performed": False,
        "transferability_established": False,
        "parameterability_assessed": False,
        "production_parameters_available": False,
        "physics_ready": False,
        "runtime_eligible": False,
        "execution_authorized": False,
        "claim_safe": False,
    },
}


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )


_FROZEN_PROTOCOL_BYTES = _canonical_json_bytes(_PROTOCOL_DOCUMENT)
SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_SHA256 = hashlib.sha256(
    _FROZEN_PROTOCOL_BYTES
).hexdigest()
_FROZEN_PROTOCOL_SHA256 = (
    SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_SHA256
)


def spice_graph_family_disjoint_population_preflight_protocol_bytes() -> bytes:
    """Return the immutable canonical prospective-preflight protocol bytes."""

    return _FROZEN_PROTOCOL_BYTES


def spice_graph_family_disjoint_population_preflight_protocol_document() -> dict[
    str, Any
]:
    """Return a detached protocol document."""

    return json.loads(spice_graph_family_disjoint_population_preflight_protocol_bytes())


class SpiceGraphFamilyDisjointPopulationPreflightContractError(ValueError):
    """Raised when topology-only population prerequisites are inconsistent."""


@dataclass(frozen=True, slots=True)
class SpiceGraphFamilyDisjointPopulationPreflightReport:
    _factory_token: InitVar[object]
    schema_id: str
    protocol_id: str
    protocol_sha256: str
    claim_scope: str
    source_schema_id: str
    source_core_sha256: str
    source_artifact_sha256: str
    source_artifact_byte_count: int
    source_review_packet_schema_id: str
    source_review_packet_core_sha256: str
    source_review_packet_artifact_sha256: str
    source_review_packet_artifact_byte_count: int
    source_review_packet_integrity_bound: bool
    current_group_order: tuple[str, ...]
    current_graph_count: int
    current_family_count: int
    current_family_ids: tuple[str, ...]
    current_graph_overlap_count: int
    current_family_overlap_count: int
    current_graph_disjoint: bool
    current_family_disjoint: bool
    current_time_disjoint: bool
    current_release_disjoint: bool
    current_public_holdout_blind_to_humans: bool
    current_canonical_graph_sha256: tuple[tuple[str, str], ...]
    current_topology_receipt_sha256: str
    current_bond_environment_key_count: int
    current_angle_environment_key_count: int
    current_proper_environment_key_count: int
    c5_delta_bond_key_count: int
    c5_delta_angle_key_count: int
    c5_delta_proper_key_count: int
    c5_new_angle_keys: tuple[tuple[str, ...], ...]
    c5_new_proper_keys: tuple[tuple[str, ...], ...]
    c6_vs_c1_c4_delta_bond_key_count: int
    c6_vs_c1_c4_delta_angle_key_count: int
    c6_vs_c1_c4_delta_proper_key_count: int
    c6_vs_c5_delta_bond_key_count: int
    c6_vs_c5_delta_angle_key_count: int
    c6_vs_c5_delta_proper_key_count: int
    c6_only_new_proper_keys: tuple[tuple[str, ...], ...]
    c7_plus_no_new_local_keys_after_c1_c6: bool
    c5_c6_accuracy_holdout_eligible: bool
    c5_c6_ood_or_coverage_expansion_only: bool
    versioned_coverage_expansion_required: bool
    whole_file_stream_receipt_available: bool
    subset_extraction_receipt_available: bool
    license_human_reviewed: bool
    prerequisite_receipts_satisfied: bool
    expanded_source_data_acquired: bool
    expanded_target_view_available: bool
    split_manifest_available: bool
    threshold_manifest_available: bool
    candidate_fitting_performed: bool
    candidate_parameter_set_available: bool
    parameter_family_sufficiency_assessed: bool
    scientific_validation_performed: bool
    reference_validation_performed: bool
    transferability_established: bool
    parameterability_assessed: bool
    parameterizable: bool
    production_parameters_available: bool
    physics_ready: bool
    runtime_eligible: bool
    execution_authorized: bool
    claim_safe: bool

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise TypeError(
                "population-preflight reports are factory-only; replay source and "
                "review packet bytes"
            )


@dataclass(frozen=True, slots=True)
class _TopologyKeys:
    graph_sha256: str
    bond_keys: frozenset[tuple[str, str]]
    angle_keys: frozenset[tuple[str, str, str]]
    proper_keys: frozenset[tuple[str, str, str, str]]


def _canonical_tree_encoding(
    atomic_numbers: tuple[int, ...],
    adjacency: tuple[tuple[tuple[int, str], ...], ...],
    root: int,
    parent: int,
) -> str:
    children = sorted(
        bond_order
        + ":"
        + _canonical_tree_encoding(atomic_numbers, adjacency, child, root)
        for child, bond_order in adjacency[root]
        if child != parent
    )
    return f"Z{atomic_numbers[root]}(" + ",".join(children) + ")"


def _validated_adjacency(
    atomic_numbers: Iterable[int],
    connectivity: Iterable[tuple[int, int, float]],
) -> tuple[tuple[int, ...], tuple[tuple[tuple[int, str], ...], ...]]:
    atoms = tuple(atomic_numbers)
    if not atoms or any(
        type(value) is not int or value not in {1, 6} for value in atoms
    ):
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "topology atoms must be a nonempty exact C/H atomic-number tuple"
        )
    neighbors: list[dict[int, str]] = [dict() for _ in atoms]
    edge_count = 0
    for row in connectivity:
        if type(row) is not tuple or len(row) != 3:
            raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
                "connectivity rows must be exact three-tuples"
            )
        atom_i, atom_j, order = row
        if (
            type(atom_i) is not int
            or type(atom_j) is not int
            or not 0 <= atom_i < len(atoms)
            or not 0 <= atom_j < len(atoms)
            or atom_i == atom_j
            or type(order) is not float
            or order not in {1.0, 2.0, 3.0}
        ):
            raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
                "connectivity row is outside the bounded labeled-tree contract"
            )
        if atom_j in neighbors[atom_i] or atom_i in neighbors[atom_j]:
            raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
                "topology contains a duplicate edge"
            )
        token = format(order, ".1f")
        neighbors[atom_i][atom_j] = token
        neighbors[atom_j][atom_i] = token
        edge_count += 1
    if edge_count != len(atoms) - 1:
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "canonical preflight graph must be a tree"
        )
    seen = {0}
    stack = [0]
    while stack:
        node = stack.pop()
        for child in neighbors[node]:
            if child not in seen:
                seen.add(child)
                stack.append(child)
    if len(seen) != len(atoms):
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "canonical preflight graph must be connected"
        )
    adjacency = tuple(
        tuple(sorted(row.items(), key=lambda item: (item[0], item[1])))
        for row in neighbors
    )
    return atoms, adjacency


def _canonical_graph_sha256(
    atomic_numbers: Iterable[int],
    connectivity: Iterable[tuple[int, int, float]],
    *,
    molecular_charge: float,
    molecular_multiplicity: int,
    isotope_state: str = "explicitly_absent",
    stereo_state: str = "explicitly_absent",
) -> str:
    """Return an atom-order-independent digest for one bounded labeled tree."""

    atoms, adjacency = _validated_adjacency(atomic_numbers, connectivity)
    if (
        type(molecular_charge) is not float
        or not math.isfinite(molecular_charge)
        or not molecular_charge.is_integer()
    ):
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "molecular charge must be a finite integer-valued exact float"
        )
    if type(molecular_multiplicity) is not int or molecular_multiplicity < 1:
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "molecular multiplicity must be a positive integer"
        )
    if isotope_state != "explicitly_absent" or stereo_state != "explicitly_absent":
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "v1 canonical graph identity requires isotope and stereo explicitly "
            "absent; present identity requires a new atom-labeled isotope/stereo "
            "identity schema"
        )
    canonical_tree = min(
        _canonical_tree_encoding(atoms, adjacency, root, -1)
        for root in range(len(atoms))
    )
    document = {
        "canonical_tree": canonical_tree,
        "isotope_state": isotope_state,
        "molecular_charge": 0.0 if molecular_charge == 0.0 else molecular_charge,
        "molecular_multiplicity": molecular_multiplicity,
        "stereo_state": stereo_state,
    }
    return hashlib.sha256(
        _GRAPH_HASH_DOMAIN + _canonical_json_bytes(document)
    ).hexdigest()


def _topology_keys(
    atomic_numbers: Iterable[int],
    connectivity: Iterable[tuple[int, int, float]],
    *,
    molecular_charge: float = 0.0,
    molecular_multiplicity: int = 1,
) -> _TopologyKeys:
    atoms, adjacency_with_orders = _validated_adjacency(atomic_numbers, connectivity)
    if molecular_charge != 0.0 or molecular_multiplicity != 1:
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "linear-alkane key projection requires a neutral singlet"
        )
    adjacency = tuple(tuple(child for child, _ in row) for row in adjacency_with_orders)
    if any(order != "1.0" for row in adjacency_with_orders for _, order in row):
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "linear-alkane key projection requires single bonds"
        )
    carbon_indices = tuple(index for index, value in enumerate(atoms) if value == 6)
    if not 1 <= len(carbon_indices):
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "linear-alkane key projection requires carbon"
        )
    environments: list[str] = []
    for atom_index, atomic_number in enumerate(atoms):
        if atomic_number == 6:
            center = atom_index
        else:
            if len(adjacency[atom_index]) != 1:
                raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
                    "hydrogen must have degree one"
                )
            center = adjacency[atom_index][0]
            if atoms[center] != 6:
                raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
                    "hydrogen must be attached to carbon"
                )
        carbon_neighbors = sum(atoms[row] == 6 for row in adjacency[center])
        hydrogen_neighbors = sum(atoms[row] == 1 for row in adjacency[center])
        if len(adjacency[center]) != 4:
            raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
                "carbon must have graph valence four"
            )
        prefix = (
            "c_single_valence4_"
            if atomic_number == 6
            else "h_attached_c_single_valence4_"
        )
        environments.append(f"{prefix}c{carbon_neighbors}_h{hydrogen_neighbors}")
    carbon_degrees = tuple(
        sum(atoms[neighbor] == 6 for neighbor in adjacency[index])
        for index in carbon_indices
    )
    if len(carbon_indices) == 1:
        expected_carbon_degrees = (0,)
    else:
        expected_carbon_degrees = tuple(
            sorted((1, 1, *(2 for _ in range(len(carbon_indices) - 2))))
        )
    if tuple(sorted(carbon_degrees)) != expected_carbon_degrees:
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "carbon subgraph must be a simple path"
        )

    bonds = {
        tuple(sorted((environments[atom_i], environments[atom_j])))
        for atom_i, row in enumerate(adjacency)
        for atom_j in row
        if atom_i < atom_j
    }
    angles = {
        (
            min(environments[outer_i], environments[outer_k]),
            environments[center],
            max(environments[outer_i], environments[outer_k]),
        )
        for center, row in enumerate(adjacency)
        for outer_position, outer_i in enumerate(row)
        for outer_k in row[outer_position + 1 :]
    }
    proper_keys: set[tuple[str, str, str, str]] = set()
    for atom_j, row in enumerate(adjacency):
        for atom_k in row:
            if atom_j >= atom_k:
                continue
            for atom_i in adjacency[atom_j]:
                if atom_i == atom_k:
                    continue
                for atom_l in adjacency[atom_k]:
                    if atom_l == atom_j:
                        continue
                    values = (
                        environments[atom_i],
                        environments[atom_j],
                        environments[atom_k],
                        environments[atom_l],
                    )
                    proper_keys.add(min(values, tuple(reversed(values))))
    return _TopologyKeys(
        graph_sha256=_canonical_graph_sha256(
            atoms,
            tuple(
                (atom_i, atom_j, float(order))
                for atom_i, row in enumerate(adjacency_with_orders)
                for atom_j, order in row
                if atom_i < atom_j
            ),
            molecular_charge=molecular_charge,
            molecular_multiplicity=molecular_multiplicity,
        ),
        bond_keys=frozenset(bonds),
        angle_keys=frozenset(angles),
        proper_keys=frozenset(proper_keys),
    )


def _linear_alkane_topology(
    carbon_count: int,
) -> tuple[tuple[int, ...], tuple[tuple[int, int, float], ...]]:
    if type(carbon_count) is not int or carbon_count < 1:
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "carbon_count must be a positive integer"
        )
    atoms = [6] * carbon_count
    bonds: list[tuple[int, int, float]] = [
        (index, index + 1, 1.0) for index in range(carbon_count - 1)
    ]
    for carbon_index in range(carbon_count):
        hydrogen_count = (
            4
            if carbon_count == 1
            else 3
            if carbon_index in {0, carbon_count - 1}
            else 2
        )
        for _ in range(hydrogen_count):
            hydrogen_index = len(atoms)
            atoms.append(1)
            bonds.append((carbon_index, hydrogen_index, 1.0))
    return tuple(atoms), tuple(bonds)


def _linear_alkane_key_universe(
    maximum_carbon_count: int,
) -> tuple[
    frozenset[tuple[str, str]],
    frozenset[tuple[str, str, str]],
    frozenset[tuple[str, str, str, str]],
]:
    bonds: set[tuple[str, str]] = set()
    angles: set[tuple[str, str, str]] = set()
    propers: set[tuple[str, str, str, str]] = set()
    for carbon_count in range(1, maximum_carbon_count + 1):
        atoms, connectivity = _linear_alkane_topology(carbon_count)
        keys = _topology_keys(atoms, connectivity)
        bonds.update(keys.bond_keys)
        angles.update(keys.angle_keys)
        propers.update(keys.proper_keys)
    return frozenset(bonds), frozenset(angles), frozenset(propers)


def _overlap_count(values: tuple[frozenset[str], ...]) -> int:
    return len(
        (values[0] & values[1]) | (values[0] & values[2]) | (values[1] & values[2])
    )


def analyze_spice_graph_family_disjoint_population_preflight(
    source_bytes: bytes,
    source_review_packet_bytes: bytes,
) -> SpiceGraphFamilyDisjointPopulationPreflightReport:
    """Replay source integrity and return a metadata-decided population-gap report."""

    corpus = load_spice_c1c4_quantum_reference_evidence(source_bytes)
    packet = load_spice_c1c4_source_review_packet(
        source_bytes,
        source_review_packet_bytes,
    )
    if tuple(group.group_id for group in corpus.groups) != _GROUP_ORDER:
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "source group order does not match the prospective protocol"
        )
    if (
        packet.schema_id != _FROZEN_SOURCE_REVIEW_PACKET_SCHEMA_ID
        or packet.expected_group_ids != _GROUP_ORDER
    ):
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "source-review packet group binding does not match source"
        )

    topology_rows: list[tuple[str, _TopologyKeys]] = []
    graph_sets: list[set[str]] = [set() for _ in _PARTITION_ORDER]
    family_sets: list[set[str]] = [set() for _ in _PARTITION_ORDER]
    for expected_carbon_count, group in enumerate(corpus.groups, start=1):
        if sum(value == 6 for value in group.atomic_numbers) != expected_carbon_count:
            raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
                "source group carbon count does not match C1--C4 order"
            )
        keys = _topology_keys(
            group.atomic_numbers,
            group.connectivity,
            molecular_charge=group.molecular_charge,
            molecular_multiplicity=group.molecular_multiplicity,
        )
        topology_rows.append((group.group_id, keys))
        for partition_index, partition in enumerate(_PARTITION_ORDER):
            if any(record.partition == partition for record in group.records):
                graph_sets[partition_index].add(keys.graph_sha256)
                family_sets[partition_index].add(_FAMILY_ID)

    current_bonds = frozenset(key for _, row in topology_rows for key in row.bond_keys)
    current_angles = frozenset(
        key for _, row in topology_rows for key in row.angle_keys
    )
    current_propers = frozenset(
        key for _, row in topology_rows for key in row.proper_keys
    )
    generated_c1_c4 = _linear_alkane_key_universe(4)
    if (current_bonds, current_angles, current_propers) != generated_c1_c4:
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "source C1--C4 topology keys do not match the exact prospective projection"
        )
    if tuple(map(len, generated_c1_c4)) != (6, 9, 7):
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "current key universe does not match 6/9/7"
        )

    c1_c5 = _linear_alkane_key_universe(5)
    c1_c6 = _linear_alkane_key_universe(6)
    c1_c7 = _linear_alkane_key_universe(7)
    c1_c8 = _linear_alkane_key_universe(8)
    c5_delta = tuple(c1_c5[index] - generated_c1_c4[index] for index in range(3))
    c6_delta = tuple(c1_c6[index] - generated_c1_c4[index] for index in range(3))
    c6_vs_c5 = tuple(c1_c6[index] - c1_c5[index] for index in range(3))
    if (
        tuple(map(len, c5_delta)) != (0, 1, 2)
        or tuple(map(len, c6_delta)) != (0, 1, 3)
        or tuple(map(len, c6_vs_c5)) != (0, 0, 1)
        or c1_c7 != c1_c6
        or c1_c8 != c1_c6
    ):
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "projected C5--C8 key deltas do not match the frozen protocol"
        )
    if (
        tuple(sorted(c5_delta[1])) != _C5_NEW_ANGLE_KEYS
        or tuple(sorted(c5_delta[2])) != _C5_NEW_PROPER_KEYS
        or tuple(sorted(c6_vs_c5[2])) != (_C6_ONLY_NEW_PROPER_KEYS)
    ):
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "projected new key identities do not match the frozen protocol"
        )

    graph_frozen = tuple(frozenset(row) for row in graph_sets)
    family_frozen = tuple(frozenset(row) for row in family_sets)
    graph_overlap = _overlap_count(graph_frozen)
    family_overlap = _overlap_count(family_frozen)
    if graph_overlap != 4 or family_overlap != 1:
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "current source no longer demonstrates the declared overlap gap"
        )
    graph_rows = tuple((group_id, row.graph_sha256) for group_id, row in topology_rows)
    if graph_rows != _FROZEN_CURRENT_GRAPH_ROWS:
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "current canonical graph digests do not match the frozen protocol"
        )
    topology_document = {
        "family_id": _FAMILY_ID,
        "graph_rows": graph_rows,
        "key_counts": [len(current_bonds), len(current_angles), len(current_propers)],
    }
    topology_receipt_sha256 = hashlib.sha256(
        _TOPOLOGY_RECEIPT_HASH_DOMAIN + _canonical_json_bytes(topology_document)
    ).hexdigest()
    if topology_receipt_sha256 != _FROZEN_TOPOLOGY_RECEIPT_SHA256:
        raise SpiceGraphFamilyDisjointPopulationPreflightContractError(
            "current topology receipt does not match the frozen protocol"
        )
    return SpiceGraphFamilyDisjointPopulationPreflightReport(
        _factory_token=_FACTORY_TOKEN,
        schema_id=_FROZEN_SCHEMA_ID,
        protocol_id=_FROZEN_PROTOCOL_ID,
        protocol_sha256=_FROZEN_PROTOCOL_SHA256,
        claim_scope=_FROZEN_CLAIM_SCOPE,
        source_schema_id=_FROZEN_SOURCE_SCHEMA_ID,
        source_core_sha256=corpus.core_sha256,
        source_artifact_sha256=corpus.artifact_sha256,
        source_artifact_byte_count=corpus.artifact_byte_count,
        source_review_packet_schema_id=packet.schema_id,
        source_review_packet_core_sha256=packet.core_sha256,
        source_review_packet_artifact_sha256=packet.artifact_sha256,
        source_review_packet_artifact_byte_count=packet.artifact_byte_count,
        source_review_packet_integrity_bound=True,
        current_group_order=_GROUP_ORDER,
        current_graph_count=len(topology_rows),
        current_family_count=1,
        current_family_ids=(_FAMILY_ID,),
        current_graph_overlap_count=graph_overlap,
        current_family_overlap_count=family_overlap,
        current_graph_disjoint=False,
        current_family_disjoint=False,
        current_time_disjoint=False,
        current_release_disjoint=False,
        current_public_holdout_blind_to_humans=False,
        current_canonical_graph_sha256=graph_rows,
        current_topology_receipt_sha256=topology_receipt_sha256,
        current_bond_environment_key_count=len(current_bonds),
        current_angle_environment_key_count=len(current_angles),
        current_proper_environment_key_count=len(current_propers),
        c5_delta_bond_key_count=len(c5_delta[0]),
        c5_delta_angle_key_count=len(c5_delta[1]),
        c5_delta_proper_key_count=len(c5_delta[2]),
        c5_new_angle_keys=tuple(sorted(c5_delta[1])),
        c5_new_proper_keys=tuple(sorted(c5_delta[2])),
        c6_vs_c1_c4_delta_bond_key_count=len(c6_delta[0]),
        c6_vs_c1_c4_delta_angle_key_count=len(c6_delta[1]),
        c6_vs_c1_c4_delta_proper_key_count=len(c6_delta[2]),
        c6_vs_c5_delta_bond_key_count=len(c6_vs_c5[0]),
        c6_vs_c5_delta_angle_key_count=len(c6_vs_c5[1]),
        c6_vs_c5_delta_proper_key_count=len(c6_vs_c5[2]),
        c6_only_new_proper_keys=tuple(sorted(c6_vs_c5[2])),
        c7_plus_no_new_local_keys_after_c1_c6=True,
        c5_c6_accuracy_holdout_eligible=False,
        c5_c6_ood_or_coverage_expansion_only=True,
        versioned_coverage_expansion_required=True,
        whole_file_stream_receipt_available=False,
        subset_extraction_receipt_available=False,
        license_human_reviewed=False,
        prerequisite_receipts_satisfied=False,
        expanded_source_data_acquired=False,
        expanded_target_view_available=False,
        split_manifest_available=False,
        threshold_manifest_available=False,
        candidate_fitting_performed=False,
        candidate_parameter_set_available=False,
        parameter_family_sufficiency_assessed=False,
        scientific_validation_performed=False,
        reference_validation_performed=False,
        transferability_established=False,
        parameterability_assessed=False,
        parameterizable=False,
        production_parameters_available=False,
        physics_ready=False,
        runtime_eligible=False,
        execution_authorized=False,
        claim_safe=False,
    )


def serialize_spice_graph_family_disjoint_population_preflight_report(
    source_bytes: bytes,
    source_review_packet_bytes: bytes,
) -> bytes:
    """Serialize the deterministic factory-only prospective-preflight report."""

    return _canonical_json_bytes(
        asdict(
            analyze_spice_graph_family_disjoint_population_preflight(
                source_bytes,
                source_review_packet_bytes,
            )
        )
    )


__all__ = [
    "SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_CLAIM_SCOPE",
    "SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_ID",
    "SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_SHA256",
    "SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_SCHEMA_ID",
    "SpiceGraphFamilyDisjointPopulationPreflightContractError",
    "SpiceGraphFamilyDisjointPopulationPreflightReport",
    "analyze_spice_graph_family_disjoint_population_preflight",
    "serialize_spice_graph_family_disjoint_population_preflight_report",
    "spice_graph_family_disjoint_population_preflight_protocol_bytes",
    "spice_graph_family_disjoint_population_preflight_protocol_document",
]
