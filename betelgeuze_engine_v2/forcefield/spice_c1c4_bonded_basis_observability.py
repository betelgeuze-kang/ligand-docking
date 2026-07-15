"""Fit-only bonded-basis numerical observability for frozen SPICE C1--C4.

This module is a non-fitting, non-runtime preflight.  It replays the exact
source-bound target view, constructs predeclared bonded feature directions from
the four admitted molecular graphs, and audits only numerical column
observability on the fit partition.  It emits no coefficients, predictions,
candidate parameters, or physical-identifiability claim.
"""

from __future__ import annotations

from dataclasses import InitVar, asdict, dataclass
from itertools import combinations
import hashlib
import json
import math
import platform
import struct
from typing import Any, Mapping

import numpy as np

from .spice_c1c4_force_matching_targets import (
    SPICE_C1C4_FORCE_MATCHING_TARGET_CORE_SHA256,
    SPICE_C1C4_FORCE_MATCHING_TARGET_SCHEMA_ID,
    SpiceC1C4ForceMatchingTargets,
    SpiceC1C4TargetTopology,
    derive_spice_c1c4_force_matching_targets,
)


SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_SCHEMA_ID = (
    "betelgeuze.spice_c1_c4_bonded_basis_observability/1.0.0"
)
SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_PROTOCOL_ID = (
    "spice_c1_c4_fit_partition_graph_pair_balanced_bonded_basis_observability/1.0.0"
)
SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_CLAIM_SCOPE = (
    "fit_partition_graph_pair_balanced_bonded_design_observability_only"
)
SPICE_C1C4_BONDED_BASIS_PRIMARY_VARIANT_ID = "parity_even_low_order_n1_3"
SPICE_C1C4_BONDED_BASIS_NEAR_NULL_RATIO_GATE = 1.0e-8
SPICE_C1C4_BONDED_BASIS_ENERGY_TARGET_RMS_BINARY64_BE_HEX = "4045541210b48320"
SPICE_C1C4_BONDED_BASIS_FORCE_TARGET_RMS_BINARY64_BE_HEX = "40515b5c68e9628d"

_GROUP_ORDER = ("c", "cc", "ccc", "cccc")
_ROLE_ORDER = ("seed", "related_nearby_lower")
_EXPECTED_TERM_COUNTS = {
    "c": (4, 6, 0),
    "cc": (7, 12, 9),
    "ccc": (10, 18, 18),
    "cccc": (13, 24, 27),
}
_VARIANT_SPECS = (
    ("parity_even_low_order_n1_3", 3, False, True),
    ("phase_complete_low_order_n1_3", 3, True, False),
    ("parity_even_full_allowed_n1_6", 6, False, False),
    ("phase_complete_full_allowed_n1_6", 6, True, False),
)
_FACTORY_TOKEN = object()
_MIN_GEOMETRY_SINE = 1.0e-8
_MIN_BOND_LENGTH_ANGSTROM = 1.0e-8

_PROTOCOL_DOCUMENT: Mapping[str, Any] = {
    "protocol_id": SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_PROTOCOL_ID,
    "schema_id": SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_SCHEMA_ID,
    "source_target_schema_id": SPICE_C1C4_FORCE_MATCHING_TARGET_SCHEMA_ID,
    "claim_scope": SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_CLAIM_SCOPE,
    "input": "frozen_spice_c1_c4_source_bytes_replayed_through_target_view",
    "topology": {
        "source_fields": ["atomic_numbers", "connectivity"],
        "admission": (
            "neutral_singlet_connected_c_h_single_bond_tree_with_h_degree_one_"
            "to_c_c_valence_four_and_c1_c4_carbon_simple_path"
        ),
        "environment_keys": (
            "graph_neighbor_count_labels_only_not_force_field_types_or_"
            "parameter_identifiers"
        ),
        "observed_key_counts": {"bond": 6, "angle": 9, "proper": 7},
    },
    "basis": {
        "bond": ["0.5*r^2", "-r"],
        "angle": ["0.5*theta^2", "-theta"],
        "proper_primary": ["cos(n*phi),n=1..3,parity_even"],
        "constants_or_intercepts": False,
        "variants": [
            {
                "id": variant_id,
                "max_periodicity": max_periodicity,
                "includes_sine": includes_sine,
                "primary": primary,
            }
            for variant_id, max_periodicity, includes_sine, primary in _VARIANT_SPECS
        ],
        "nonprimary_variants_are_nonselecting_audits": True,
        "target_residual_used_for_variant_selection": False,
    },
    "rows": {
        "partition": "fit_only",
        "order": (
            "group_then_source_pair_then_energy_then_seed_atom_xyz_then_"
            "related_atom_xyz"
        ),
        "energy": "Phi(seed)-Phi(related_nearby_lower)",
        "force": "negative_cartesian_derivative_of_the_same_scalar_Phi",
        "energy_row_count": 60,
        "force_row_count": 3420,
        "total_row_count": 3480,
    },
    "loss_weighting": {
        "scale_source": "fit_partition_targets_only_rms_about_zero",
        "graph_weight": "one_fourth_each",
        "energy_force_class_weight": "one_half_each_within_each_graph",
        "energy_average": "one_fifteenth_over_fit_pairs",
        "force_average": "one_over_30_times_3N_over_pair_roles_and_scalars",
        "selection_or_holdout_used": False,
        "regularization": False,
        "accuracy_tolerance": False,
    },
    "observability": {
        "column_scaling": "fit_only_loss_weighted_l2_norm",
        "svd": "numpy_binary64_full_matrices_false_compute_uv_false",
        "rank_tolerance": "max(row_count,column_count)*eps64*sigma_max",
        "near_null_ratio_gate": SPICE_C1C4_BONDED_BASIS_NEAR_NULL_RATIO_GATE,
        "cross_platform_bitwise_svd_contract": False,
        "null_vectors_serialized": False,
    },
    "nonpromotion": {
        "coefficients_or_predictions": False,
        "candidate_fitting_or_parameter_set": False,
        "bonded_or_physical_parameter_identifiability": False,
        "parameter_family_sufficiency_or_transferability": False,
        "reference_validation_or_production_runtime_claim": False,
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


SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_PROTOCOL_SHA256 = hashlib.sha256(
    _canonical_json_bytes(_PROTOCOL_DOCUMENT)
).hexdigest()


def spice_c1c4_bonded_basis_observability_protocol_bytes() -> bytes:
    """Return immutable canonical bytes for the observability protocol."""

    return _canonical_json_bytes(_PROTOCOL_DOCUMENT)


def spice_c1c4_bonded_basis_observability_protocol_document() -> dict[str, Any]:
    """Return a detached copy of the observability protocol document."""

    return json.loads(spice_c1c4_bonded_basis_observability_protocol_bytes())


class SpiceC1C4BondedBasisObservabilityContractError(ValueError):
    """Raised when source, topology, geometry, or design invariants fail."""


@dataclass(frozen=True, slots=True)
class SpiceC1C4BondedBasisVariantReport:
    variant_id: str
    primary: bool
    parity_even: bool
    includes_sine: bool
    max_periodicity: int
    row_count: int
    column_count: int
    numerical_rank: int
    nullity: int
    singular_value_max: float
    singular_value_min: float
    condition_number: float
    reciprocal_condition_number: float
    rank_tolerance: float
    rank_margin: float
    near_null_ratio_gate: float
    conditional_fit_design_full_column_rank: bool
    unweighted_design_sha256: str
    loss_weighted_column_normalized_design_sha256: str


@dataclass(frozen=True, slots=True)
class SpiceC1C4BondedBasisObservabilityReport:
    _factory_token: InitVar[object]
    schema_id: str
    protocol_id: str
    protocol_sha256: str
    claim_scope: str
    source_target_schema_id: str
    source_target_core_sha256: str
    source_artifact_sha256: str
    source_artifact_byte_count: int
    group_order: tuple[str, ...]
    primary_variant_id: str
    topology_sha256: str
    column_metadata_sha256: str
    row_metadata_sha256: str
    target_vector_sha256: str
    fit_pair_count: int
    fit_force_record_count: int
    fit_energy_row_count: int
    fit_force_row_count: int
    fit_total_row_count: int
    bond_environment_key_count: int
    angle_environment_key_count: int
    proper_environment_key_count: int
    term_counts_by_group: tuple[tuple[str, int, int, int], ...]
    energy_target_rms_kj_per_mol: float
    force_target_rms_kj_per_mol_per_angstrom: float
    energy_target_rms_binary64_be_hex: str
    force_target_rms_binary64_be_hex: str
    variant_reports: tuple[SpiceC1C4BondedBasisVariantReport, ...]
    numpy_version: str
    svd_implementation: str
    python_implementation: str
    platform_machine: str
    selection_or_holdout_used: bool
    target_centering_applied: bool
    regularization_applied: bool
    cross_platform_bitwise_svd_assessed: bool
    conditional_fit_design_full_column_rank: bool
    coefficient_fit_performed: bool
    predictions_computed: bool
    candidate_fitting_performed: bool
    candidate_parameter_set_available: bool
    bonded_parameter_identifiability_established: bool
    physical_parameter_identifiability_established: bool
    parameter_family_sufficiency_assessed: bool
    transferability_established: bool
    reference_validation_performed: bool
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
                "observability reports are factory-only; replay source bytes"
            )


@dataclass(frozen=True, slots=True)
class _CompiledTopology:
    group_id: str
    atomic_numbers: tuple[int, ...]
    bonds: tuple[tuple[int, int, tuple[str, str]], ...]
    angles: tuple[tuple[int, int, int, tuple[str, str, str]], ...]
    propers: tuple[tuple[int, int, int, int, tuple[str, str, str, str]], ...]


@dataclass(frozen=True, slots=True)
class _ColumnDescriptor:
    family: str
    environment_key: tuple[str, ...]
    feature: str
    periodicity: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "environment_key": self.environment_key,
            "feature": self.feature,
            "periodicity": self.periodicity,
        }


@dataclass(frozen=True, slots=True)
class _DesignBundle:
    matrix: np.ndarray
    targets: np.ndarray
    row_weights: np.ndarray
    row_metadata: tuple[dict[str, Any], ...]
    columns: tuple[_ColumnDescriptor, ...]
    topologies: tuple[_CompiledTopology, ...]
    energy_scale: float
    force_scale: float


def _environment_id(
    atom_index: int,
    atomic_numbers: tuple[int, ...],
    neighbors: tuple[tuple[int, ...], ...],
) -> str:
    atomic_number = atomic_numbers[atom_index]
    if atomic_number == 6:
        carbon_count = sum(
            atomic_numbers[index] == 6 for index in neighbors[atom_index]
        )
        hydrogen_count = sum(
            atomic_numbers[index] == 1 for index in neighbors[atom_index]
        )
        return f"c_single_valence4_c{carbon_count}_h{hydrogen_count}"
    parent = neighbors[atom_index][0]
    carbon_count = sum(atomic_numbers[index] == 6 for index in neighbors[parent])
    hydrogen_count = sum(atomic_numbers[index] == 1 for index in neighbors[parent])
    return f"h_attached_c_single_valence4_c{carbon_count}_h{hydrogen_count}"


def _compile_topology(topology: SpiceC1C4TargetTopology) -> _CompiledTopology:
    if topology.group_id not in _GROUP_ORDER:
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "unexpected SPICE C1-C4 group"
        )
    atomic_numbers = tuple(topology.atomic_numbers)
    if not atomic_numbers or any(value not in (1, 6) for value in atomic_numbers):
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "observability topology must contain only carbon and hydrogen"
        )
    if topology.molecular_charge != 0.0 or topology.molecular_multiplicity != 1:
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "observability topology must be a neutral singlet"
        )

    atom_count = len(atomic_numbers)
    edge_set: set[tuple[int, int]] = set()
    for raw_i, raw_j, order in topology.connectivity:
        if type(raw_i) is not int or type(raw_j) is not int:
            raise SpiceC1C4BondedBasisObservabilityContractError(
                "connectivity endpoints must be integers"
            )
        if not 0 <= raw_i < atom_count or not 0 <= raw_j < atom_count:
            raise SpiceC1C4BondedBasisObservabilityContractError(
                "connectivity endpoint is outside the topology"
            )
        if raw_i == raw_j or order != 1.0:
            raise SpiceC1C4BondedBasisObservabilityContractError(
                "only non-self single bonds are admitted"
            )
        edge = tuple(sorted((raw_i, raw_j)))
        if edge in edge_set:
            raise SpiceC1C4BondedBasisObservabilityContractError(
                "duplicate connectivity edge"
            )
        edge_set.add(edge)
    if len(edge_set) != atom_count - 1:
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "connectivity must be a tree"
        )

    neighbor_lists: list[list[int]] = [[] for _ in atomic_numbers]
    for atom_i, atom_j in edge_set:
        neighbor_lists[atom_i].append(atom_j)
        neighbor_lists[atom_j].append(atom_i)
    neighbors = tuple(tuple(sorted(row)) for row in neighbor_lists)
    visited = {0}
    frontier = [0]
    while frontier:
        current = frontier.pop()
        for neighbor in neighbors[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                frontier.append(neighbor)
    if len(visited) != atom_count:
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "connectivity must be connected"
        )

    carbon_atoms = tuple(index for index, z in enumerate(atomic_numbers) if z == 6)
    if not 1 <= len(carbon_atoms) <= 4:
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "carbon subgraph must contain one through four atoms"
        )
    for atom_index, atomic_number in enumerate(atomic_numbers):
        if atomic_number == 1:
            if (
                len(neighbors[atom_index]) != 1
                or atomic_numbers[neighbors[atom_index][0]] != 6
            ):
                raise SpiceC1C4BondedBasisObservabilityContractError(
                    "hydrogen must have degree one and attach to carbon"
                )
        elif len(neighbors[atom_index]) != 4:
            raise SpiceC1C4BondedBasisObservabilityContractError(
                "carbon must have single-bond valence four"
            )
    carbon_degrees = tuple(
        sum(atomic_numbers[neighbor] == 6 for neighbor in neighbors[index])
        for index in carbon_atoms
    )
    if len(carbon_atoms) == 1:
        valid_carbon_path = carbon_degrees == (0,)
    else:
        valid_carbon_path = (
            carbon_degrees.count(1) == 2
            and all(degree in (1, 2) for degree in carbon_degrees)
            and sum(carbon_degrees) == 2 * (len(carbon_atoms) - 1)
        )
    if not valid_carbon_path:
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "carbon subgraph must be a C1-C4 simple path"
        )

    environments = tuple(
        _environment_id(index, atomic_numbers, neighbors) for index in range(atom_count)
    )
    bonds = tuple(
        (
            atom_i,
            atom_j,
            tuple(sorted((environments[atom_i], environments[atom_j]))),
        )
        for atom_i, atom_j in sorted(edge_set)
    )
    angle_rows: list[tuple[int, int, int, tuple[str, str, str]]] = []
    for center in range(atom_count):
        for outer_i, outer_k in combinations(neighbors[center], 2):
            first, last = sorted((outer_i, outer_k))
            outer_environments = sorted((environments[first], environments[last]))
            angle_rows.append(
                (
                    first,
                    center,
                    last,
                    (
                        outer_environments[0],
                        environments[center],
                        outer_environments[1],
                    ),
                )
            )
    angles = tuple(sorted(angle_rows))

    proper_paths: set[tuple[int, int, int, int]] = set()
    for atom_j, atom_k in sorted(edge_set):
        for atom_i in neighbors[atom_j]:
            if atom_i == atom_k:
                continue
            for atom_l in neighbors[atom_k]:
                if atom_l == atom_j:
                    continue
                path = (atom_i, atom_j, atom_k, atom_l)
                proper_paths.add(min(path, tuple(reversed(path))))
    proper_rows = []
    for path in sorted(proper_paths):
        environment_path = tuple(environments[index] for index in path)
        key = min(environment_path, tuple(reversed(environment_path)))
        proper_rows.append((*path, key))
    propers = tuple(proper_rows)

    expected_counts = _EXPECTED_TERM_COUNTS[topology.group_id]
    if (len(bonds), len(angles), len(propers)) != expected_counts:
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "compiled bonded-term counts do not match the frozen graph"
        )
    return _CompiledTopology(
        group_id=topology.group_id,
        atomic_numbers=atomic_numbers,
        bonds=bonds,
        angles=angles,
        propers=propers,
    )


def _column_descriptors(
    topologies: tuple[_CompiledTopology, ...],
) -> tuple[_ColumnDescriptor, ...]:
    bond_keys = sorted({row[2] for topology in topologies for row in topology.bonds})
    angle_keys = sorted({row[3] for topology in topologies for row in topology.angles})
    proper_keys = sorted(
        {row[4] for topology in topologies for row in topology.propers}
    )
    if (len(bond_keys), len(angle_keys), len(proper_keys)) != (6, 9, 7):
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "observed environment-key universe must be exactly 6/9/7"
        )
    columns: list[_ColumnDescriptor] = []
    for key in bond_keys:
        columns.extend(
            (
                _ColumnDescriptor("bond", key, "quadratic", 0),
                _ColumnDescriptor("bond", key, "linear", 0),
            )
        )
    for key in angle_keys:
        columns.extend(
            (
                _ColumnDescriptor("angle", key, "quadratic", 0),
                _ColumnDescriptor("angle", key, "linear", 0),
            )
        )
    for key in proper_keys:
        for periodicity in range(1, 7):
            columns.extend(
                (
                    _ColumnDescriptor("proper", key, "cosine", periodicity),
                    _ColumnDescriptor("proper", key, "sine", periodicity),
                )
            )
    if len(columns) != 114:
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "full allowed-family audit must have 114 columns"
        )
    return tuple(columns)


def _coordinates_from_target(raw_hex: str, atom_count: int) -> np.ndarray:
    raw = bytes.fromhex(raw_hex)
    expected_byte_count = atom_count * 3 * 8
    if len(raw) != expected_byte_count:
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "geometry byte count does not match topology"
        )
    coordinates = (
        np.frombuffer(raw, dtype=">f8").astype(np.float64).reshape(atom_count, 3)
    )
    if not np.isfinite(coordinates).all():
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "geometry must contain finite binary64 coordinates"
        )
    return coordinates


def _force_from_target(raw_hex: str, atom_count: int) -> np.ndarray:
    raw = bytes.fromhex(raw_hex)
    expected_byte_count = atom_count * 3 * 8
    if len(raw) != expected_byte_count:
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "force byte count does not match topology"
        )
    force = np.frombuffer(raw, dtype=">f8").astype(np.float64).reshape(atom_count, 3)
    if not np.isfinite(force).all():
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "force target must contain finite binary64 values"
        )
    return force


def _feature_value_and_force(
    topology: _CompiledTopology,
    coordinates: np.ndarray,
    columns: tuple[_ColumnDescriptor, ...],
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate the full 114-column scalar basis and its negative Jacobian."""

    atom_count = len(topology.atomic_numbers)
    if coordinates.shape != (atom_count, 3) or not np.isfinite(coordinates).all():
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "coordinates must be finite with shape [atom_count,3]"
        )
    lookup = {
        (
            column.family,
            column.environment_key,
            column.feature,
            column.periodicity,
        ): index
        for index, column in enumerate(columns)
    }
    values = np.zeros(len(columns), dtype=np.float64)
    forces = np.zeros((atom_count, 3, len(columns)), dtype=np.float64)

    for atom_i, atom_j, key in topology.bonds:
        displacement = coordinates[atom_j] - coordinates[atom_i]
        length = float(np.linalg.norm(displacement))
        if not math.isfinite(length) or length <= _MIN_BOND_LENGTH_ANGSTROM:
            raise SpiceC1C4BondedBasisObservabilityContractError(
                "bond feature is singular"
            )
        unit = displacement / length
        quadratic = lookup[("bond", key, "quadratic", 0)]
        linear = lookup[("bond", key, "linear", 0)]
        values[quadratic] += 0.5 * length * length
        values[linear] -= length
        forces[atom_i, :, quadratic] += displacement
        forces[atom_j, :, quadratic] -= displacement
        forces[atom_i, :, linear] -= unit
        forces[atom_j, :, linear] += unit

    for atom_i, atom_j, atom_k, key in topology.angles:
        vector_u = coordinates[atom_i] - coordinates[atom_j]
        vector_v = coordinates[atom_k] - coordinates[atom_j]
        length_u = float(np.linalg.norm(vector_u))
        length_v = float(np.linalg.norm(vector_v))
        if min(length_u, length_v) <= _MIN_BOND_LENGTH_ANGSTROM:
            raise SpiceC1C4BondedBasisObservabilityContractError(
                "angle feature has a singular arm"
            )
        dot = float(np.dot(vector_u, vector_v))
        cross_norm = float(np.linalg.norm(np.cross(vector_u, vector_v)))
        sine = cross_norm / (length_u * length_v)
        if not math.isfinite(sine) or sine <= _MIN_GEOMETRY_SINE:
            raise SpiceC1C4BondedBasisObservabilityContractError(
                "angle feature is singular"
            )
        theta = math.atan2(cross_norm, dot)
        unit_u = vector_u / length_u
        unit_v = vector_v / length_v
        cosine = dot / (length_u * length_v)
        gradient_u = (cosine * unit_u - unit_v) / (length_u * sine)
        gradient_v = (cosine * unit_v - unit_u) / (length_v * sine)
        gradient_j = -(gradient_u + gradient_v)

        quadratic = lookup[("angle", key, "quadratic", 0)]
        linear = lookup[("angle", key, "linear", 0)]
        values[quadratic] += 0.5 * theta * theta
        values[linear] -= theta
        for atom_index, gradient in (
            (atom_i, gradient_u),
            (atom_j, gradient_j),
            (atom_k, gradient_v),
        ):
            forces[atom_index, :, quadratic] -= theta * gradient
            forces[atom_index, :, linear] += gradient

    for atom_i, atom_j, atom_k, atom_l, key in topology.propers:
        bond_1 = coordinates[atom_j] - coordinates[atom_i]
        bond_2 = coordinates[atom_k] - coordinates[atom_j]
        bond_3 = coordinates[atom_l] - coordinates[atom_k]
        bond_1_norm = float(np.linalg.norm(bond_1))
        bond_2_norm = float(np.linalg.norm(bond_2))
        bond_3_norm = float(np.linalg.norm(bond_3))
        if min(bond_1_norm, bond_2_norm, bond_3_norm) <= _MIN_BOND_LENGTH_ANGSTROM:
            raise SpiceC1C4BondedBasisObservabilityContractError(
                "proper feature has a singular bond"
            )
        normal_1 = np.cross(bond_1, bond_2)
        normal_2 = np.cross(bond_2, bond_3)
        normal_1_sq = float(np.dot(normal_1, normal_1))
        normal_2_sq = float(np.dot(normal_2, normal_2))
        sine_1 = math.sqrt(normal_1_sq) / (bond_1_norm * bond_2_norm)
        sine_2 = math.sqrt(normal_2_sq) / (bond_2_norm * bond_3_norm)
        if min(sine_1, sine_2) <= _MIN_GEOMETRY_SINE:
            raise SpiceC1C4BondedBasisObservabilityContractError(
                "proper feature is singular"
            )
        bond_2_unit = bond_2 / bond_2_norm
        phi = math.atan2(
            float(np.dot(np.cross(normal_1, normal_2), bond_2_unit)),
            float(np.dot(normal_1, normal_2)),
        )
        gradient_i = -bond_2_norm * normal_1 / normal_1_sq
        gradient_l = bond_2_norm * normal_2 / normal_2_sq
        bond_2_sq = bond_2_norm * bond_2_norm
        alpha = float(np.dot(bond_1, bond_2)) / bond_2_sq
        beta = float(np.dot(bond_3, bond_2)) / bond_2_sq
        gradient_j = -(1.0 + alpha) * gradient_i + beta * gradient_l
        gradient_k = alpha * gradient_i - (1.0 + beta) * gradient_l
        gradients = (
            (atom_i, gradient_i),
            (atom_j, gradient_j),
            (atom_k, gradient_k),
            (atom_l, gradient_l),
        )
        for periodicity in range(1, 7):
            argument = periodicity * phi
            cosine = math.cos(argument)
            sine = math.sin(argument)
            cosine_index = lookup[("proper", key, "cosine", periodicity)]
            sine_index = lookup[("proper", key, "sine", periodicity)]
            values[cosine_index] += cosine
            values[sine_index] += sine
            for atom_index, gradient in gradients:
                forces[atom_index, :, cosine_index] += periodicity * sine * gradient
                forces[atom_index, :, sine_index] -= periodicity * cosine * gradient

    if not np.isfinite(values).all() or not np.isfinite(forces).all():
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "bonded basis evaluation produced a non-finite value"
        )
    return values, forces


def _float64_be_hex(value: float) -> str:
    return struct.pack(">d", value).hex()


def _array_sha256(value: np.ndarray) -> str:
    array = np.asarray(value, dtype=np.float64)
    if not np.isfinite(array).all():
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "cannot hash a non-finite binary64 array"
        )
    return hashlib.sha256(
        array.astype(">f8", copy=False).tobytes(order="C")
    ).hexdigest()


def _fit_target_scales(
    targets: SpiceC1C4ForceMatchingTargets,
    topologies: Mapping[str, _CompiledTopology],
) -> tuple[float, float]:
    energy_group_means = []
    force_group_means = []
    for group_id in _GROUP_ORDER:
        energies = [
            struct.unpack(
                ">d", bytes.fromhex(row.relative_energy_kj_per_mol_binary64_be_hex)
            )[0]
            for row in targets.relative_energy_targets
            if row.group_id == group_id and row.partition == "fit"
        ]
        if len(energies) != 15:
            raise SpiceC1C4BondedBasisObservabilityContractError(
                "each graph must have exactly 15 fit energy pairs"
            )
        energy_group_means.append(math.fsum(value * value for value in energies) / 15.0)
        atom_count = len(topologies[group_id].atomic_numbers)
        force_scalars: list[float] = []
        for row in targets.force_targets:
            if row.group_id == group_id and row.partition == "fit":
                force_scalars.extend(
                    _force_from_target(
                        row.force_kj_per_mol_per_angstrom_binary64_be_hex,
                        atom_count,
                    ).reshape(-1)
                )
        expected_force_count = 30 * 3 * atom_count
        if len(force_scalars) != expected_force_count:
            raise SpiceC1C4BondedBasisObservabilityContractError(
                "each graph must have 30 fit force records"
            )
        force_group_means.append(
            math.fsum(float(value) * float(value) for value in force_scalars)
            / expected_force_count
        )
    energy_scale = math.sqrt(math.fsum(energy_group_means) / 4.0)
    force_scale = math.sqrt(math.fsum(force_group_means) / 4.0)
    if (
        _float64_be_hex(energy_scale)
        != SPICE_C1C4_BONDED_BASIS_ENERGY_TARGET_RMS_BINARY64_BE_HEX
        or _float64_be_hex(force_scale)
        != SPICE_C1C4_BONDED_BASIS_FORCE_TARGET_RMS_BINARY64_BE_HEX
    ):
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "fit-only target scales do not match the frozen convention"
        )
    return energy_scale, force_scale


def _build_fit_design(targets: SpiceC1C4ForceMatchingTargets) -> _DesignBundle:
    if targets.core_sha256 != SPICE_C1C4_FORCE_MATCHING_TARGET_CORE_SHA256:
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "observability input must be the frozen target view"
        )
    compiled = tuple(_compile_topology(row) for row in targets.topologies)
    if tuple(row.group_id for row in compiled) != _GROUP_ORDER:
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "target topology order does not match the protocol"
        )
    topology_by_group = {row.group_id: row for row in compiled}
    columns = _column_descriptors(compiled)
    energy_scale, force_scale = _fit_target_scales(targets, topology_by_group)

    energy_rows = {
        (row.group_id, row.source_pair_id): row
        for row in targets.relative_energy_targets
        if row.partition == "fit"
    }
    force_rows = {
        (row.group_id, row.source_pair_id, row.role): row
        for row in targets.force_targets
        if row.partition == "fit"
    }
    matrix_rows: list[np.ndarray] = []
    target_values: list[float] = []
    row_weights: list[float] = []
    row_metadata: list[dict[str, Any]] = []
    for group_id in _GROUP_ORDER:
        topology = topology_by_group[group_id]
        atom_count = len(topology.atomic_numbers)
        energy_weight = math.sqrt(0.25 * 0.5 / 15.0) / energy_scale
        force_weight = math.sqrt(0.25 * 0.5 / (30.0 * 3.0 * atom_count)) / force_scale
        pair_ids = sorted(
            pair_id
            for candidate_group, pair_id in energy_rows
            if candidate_group == group_id
        )
        if len(pair_ids) != 15:
            raise SpiceC1C4BondedBasisObservabilityContractError(
                "fit design must contain 15 pairs per graph"
            )
        for pair_id in pair_ids:
            energy_row = energy_rows[(group_id, pair_id)]
            evaluated: dict[str, tuple[np.ndarray, np.ndarray, Any]] = {}
            for role in _ROLE_ORDER:
                target_row = force_rows.get((group_id, pair_id, role))
                if target_row is None:
                    raise SpiceC1C4BondedBasisObservabilityContractError(
                        "fit pair is missing a force role"
                    )
                coordinates = _coordinates_from_target(
                    target_row.geometry_angstrom_binary64_be_hex,
                    atom_count,
                )
                values, basis_forces = _feature_value_and_force(
                    topology, coordinates, columns
                )
                evaluated[role] = (values, basis_forces, target_row)
            seed_values = evaluated["seed"][0]
            related_values = evaluated["related_nearby_lower"][0]
            matrix_rows.append(seed_values - related_values)
            target_values.append(
                struct.unpack(
                    ">d",
                    bytes.fromhex(
                        energy_row.relative_energy_kj_per_mol_binary64_be_hex
                    ),
                )[0]
            )
            row_weights.append(energy_weight)
            row_metadata.append(
                {
                    "group_id": group_id,
                    "source_pair_id": pair_id,
                    "kind": "relative_energy",
                    "role": "seed_minus_related_nearby_lower",
                }
            )
            for role in _ROLE_ORDER:
                _values, basis_forces, target_row = evaluated[role]
                force_target = _force_from_target(
                    target_row.force_kj_per_mol_per_angstrom_binary64_be_hex,
                    atom_count,
                )
                for atom_index in range(atom_count):
                    for axis in range(3):
                        matrix_rows.append(basis_forces[atom_index, axis, :].copy())
                        target_values.append(float(force_target[atom_index, axis]))
                        row_weights.append(force_weight)
                        row_metadata.append(
                            {
                                "group_id": group_id,
                                "source_pair_id": pair_id,
                                "kind": "force",
                                "role": role,
                                "atom_index": atom_index,
                                "axis": axis,
                            }
                        )
    matrix = np.stack(matrix_rows).astype(np.float64, copy=False)
    target_vector = np.asarray(target_values, dtype=np.float64)
    weights = np.asarray(row_weights, dtype=np.float64)
    if matrix.shape != (3480, 114) or target_vector.shape != (3480,):
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "fit design must have shape 3480 by 114 before variant projection"
        )
    if not np.isfinite(matrix).all() or not np.isfinite(weights).all():
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "fit design and weights must be finite"
        )
    return _DesignBundle(
        matrix=matrix,
        targets=target_vector,
        row_weights=weights,
        row_metadata=tuple(row_metadata),
        columns=columns,
        topologies=compiled,
        energy_scale=energy_scale,
        force_scale=force_scale,
    )


def _variant_column_indices(
    columns: tuple[_ColumnDescriptor, ...],
    max_periodicity: int,
    includes_sine: bool,
) -> tuple[int, ...]:
    return tuple(
        index
        for index, column in enumerate(columns)
        if column.family != "proper"
        or (
            column.periodicity <= max_periodicity
            and (column.feature != "sine" or includes_sine)
        )
    )


def _analyze_variant(
    bundle: _DesignBundle,
    *,
    variant_id: str,
    max_periodicity: int,
    includes_sine: bool,
    primary: bool,
) -> SpiceC1C4BondedBasisVariantReport:
    indices = _variant_column_indices(
        bundle.columns,
        max_periodicity=max_periodicity,
        includes_sine=includes_sine,
    )
    expected_count = {
        (3, False): 51,
        (3, True): 72,
        (6, False): 72,
        (6, True): 114,
    }[(max_periodicity, includes_sine)]
    if len(indices) != expected_count:
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "variant column count does not match the protocol"
        )
    design = bundle.matrix[:, indices]
    weighted = design * bundle.row_weights[:, None]
    column_norms = np.asarray(
        [
            math.sqrt(
                math.fsum(float(value) * float(value) for value in weighted[:, index])
            )
            for index in range(weighted.shape[1])
        ],
        dtype=np.float64,
    )
    if not np.isfinite(column_norms).all() or np.any(column_norms <= 0.0):
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "every fit-only weighted design column must have positive L2 norm"
        )
    normalized = weighted / column_norms[None, :]
    singular_values = np.linalg.svd(
        normalized,
        full_matrices=False,
        compute_uv=False,
    )
    if (
        singular_values.shape != (len(indices),)
        or not np.isfinite(singular_values).all()
    ):
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "SVD did not return one finite value per column"
        )
    singular_value_max = float(singular_values[0])
    singular_value_min = float(singular_values[-1])
    tolerance = max(normalized.shape) * np.finfo(np.float64).eps * singular_value_max
    numerical_rank = int(np.count_nonzero(singular_values > tolerance))
    nullity = len(indices) - numerical_rank
    reciprocal_condition = singular_value_min / singular_value_max
    condition_number = singular_value_max / singular_value_min
    full_column_rank = (
        numerical_rank == len(indices)
        and reciprocal_condition >= SPICE_C1C4_BONDED_BASIS_NEAR_NULL_RATIO_GATE
    )
    return SpiceC1C4BondedBasisVariantReport(
        variant_id=variant_id,
        primary=primary,
        parity_even=not includes_sine,
        includes_sine=includes_sine,
        max_periodicity=max_periodicity,
        row_count=normalized.shape[0],
        column_count=normalized.shape[1],
        numerical_rank=numerical_rank,
        nullity=nullity,
        singular_value_max=singular_value_max,
        singular_value_min=singular_value_min,
        condition_number=condition_number,
        reciprocal_condition_number=reciprocal_condition,
        rank_tolerance=tolerance,
        rank_margin=singular_value_min / tolerance,
        near_null_ratio_gate=SPICE_C1C4_BONDED_BASIS_NEAR_NULL_RATIO_GATE,
        conditional_fit_design_full_column_rank=full_column_rank,
        unweighted_design_sha256=_array_sha256(design),
        loss_weighted_column_normalized_design_sha256=_array_sha256(normalized),
    )


def analyze_spice_c1c4_bonded_basis_observability(
    source_bytes: bytes,
) -> SpiceC1C4BondedBasisObservabilityReport:
    """Replay source bytes and audit fit-only bonded design observability."""

    targets = derive_spice_c1c4_force_matching_targets(source_bytes)
    bundle = _build_fit_design(targets)
    variants = tuple(
        _analyze_variant(
            bundle,
            variant_id=variant_id,
            max_periodicity=max_periodicity,
            includes_sine=includes_sine,
            primary=primary,
        )
        for variant_id, max_periodicity, includes_sine, primary in _VARIANT_SPECS
    )
    if not all(row.conditional_fit_design_full_column_rank for row in variants):
        raise SpiceC1C4BondedBasisObservabilityContractError(
            "a predeclared fit design variant failed the observability gate"
        )
    topology_document = {
        "topologies": [
            {
                "group_id": row.group_id,
                "atomic_numbers": row.atomic_numbers,
                "bonds": row.bonds,
                "angles": row.angles,
                "propers": row.propers,
            }
            for row in bundle.topologies
        ]
    }
    column_document = {"columns": [row.to_dict() for row in bundle.columns]}
    row_document = {"rows": bundle.row_metadata}
    return SpiceC1C4BondedBasisObservabilityReport(
        _factory_token=_FACTORY_TOKEN,
        schema_id=SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_SCHEMA_ID,
        protocol_id=SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_PROTOCOL_ID,
        protocol_sha256=SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_PROTOCOL_SHA256,
        claim_scope=SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_CLAIM_SCOPE,
        source_target_schema_id=targets.schema_id,
        source_target_core_sha256=targets.core_sha256,
        source_artifact_sha256=targets.source_artifact_sha256,
        source_artifact_byte_count=targets.source_artifact_byte_count,
        group_order=_GROUP_ORDER,
        primary_variant_id=SPICE_C1C4_BONDED_BASIS_PRIMARY_VARIANT_ID,
        topology_sha256=hashlib.sha256(
            _canonical_json_bytes(topology_document)
        ).hexdigest(),
        column_metadata_sha256=hashlib.sha256(
            _canonical_json_bytes(column_document)
        ).hexdigest(),
        row_metadata_sha256=hashlib.sha256(
            _canonical_json_bytes(row_document)
        ).hexdigest(),
        target_vector_sha256=_array_sha256(bundle.targets),
        fit_pair_count=60,
        fit_force_record_count=120,
        fit_energy_row_count=60,
        fit_force_row_count=3420,
        fit_total_row_count=3480,
        bond_environment_key_count=6,
        angle_environment_key_count=9,
        proper_environment_key_count=7,
        term_counts_by_group=tuple(
            (
                row.group_id,
                len(row.bonds),
                len(row.angles),
                len(row.propers),
            )
            for row in bundle.topologies
        ),
        energy_target_rms_kj_per_mol=bundle.energy_scale,
        force_target_rms_kj_per_mol_per_angstrom=bundle.force_scale,
        energy_target_rms_binary64_be_hex=_float64_be_hex(bundle.energy_scale),
        force_target_rms_binary64_be_hex=_float64_be_hex(bundle.force_scale),
        variant_reports=variants,
        numpy_version=np.__version__,
        svd_implementation="numpy.linalg.svd",
        python_implementation=platform.python_implementation(),
        platform_machine=platform.machine(),
        selection_or_holdout_used=False,
        target_centering_applied=False,
        regularization_applied=False,
        cross_platform_bitwise_svd_assessed=False,
        conditional_fit_design_full_column_rank=True,
        coefficient_fit_performed=False,
        predictions_computed=False,
        candidate_fitting_performed=False,
        candidate_parameter_set_available=False,
        bonded_parameter_identifiability_established=False,
        physical_parameter_identifiability_established=False,
        parameter_family_sufficiency_assessed=False,
        transferability_established=False,
        reference_validation_performed=False,
        parameterability_assessed=False,
        parameterizable=False,
        production_parameters_available=False,
        physics_ready=False,
        runtime_eligible=False,
        execution_authorized=False,
        claim_safe=False,
    )


def derive_spice_c1c4_bonded_basis_observability(
    source_bytes: bytes,
) -> SpiceC1C4BondedBasisObservabilityReport:
    """Alias the single factory for callers that use derive terminology."""

    return analyze_spice_c1c4_bonded_basis_observability(source_bytes)


def serialize_spice_c1c4_bonded_basis_observability_report(
    source_bytes: bytes,
) -> bytes:
    """Serialize the environment-local, non-bitwise-SVD report canonically."""

    return _canonical_json_bytes(
        asdict(analyze_spice_c1c4_bonded_basis_observability(source_bytes))
    )


__all__ = [
    "SPICE_C1C4_BONDED_BASIS_ENERGY_TARGET_RMS_BINARY64_BE_HEX",
    "SPICE_C1C4_BONDED_BASIS_FORCE_TARGET_RMS_BINARY64_BE_HEX",
    "SPICE_C1C4_BONDED_BASIS_NEAR_NULL_RATIO_GATE",
    "SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_CLAIM_SCOPE",
    "SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_PROTOCOL_ID",
    "SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_PROTOCOL_SHA256",
    "SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_SCHEMA_ID",
    "SPICE_C1C4_BONDED_BASIS_PRIMARY_VARIANT_ID",
    "SpiceC1C4BondedBasisObservabilityContractError",
    "SpiceC1C4BondedBasisObservabilityReport",
    "SpiceC1C4BondedBasisVariantReport",
    "analyze_spice_c1c4_bonded_basis_observability",
    "derive_spice_c1c4_bonded_basis_observability",
    "serialize_spice_c1c4_bonded_basis_observability_report",
    "spice_c1c4_bonded_basis_observability_protocol_bytes",
    "spice_c1c4_bonded_basis_observability_protocol_document",
]
