"""Frozen CPU reference energy/force validation protocol and closed gate.

The protocol is deliberately frozen before any validation result is collected.
It defines deterministic synthetic implementation-mathematics fixtures,
failure-inclusive case coverage, independent-oracle separation, numerical
tolerances, result-receipt requirements, and the prerequisites for a future
execution authorization.

This module does not materialize fixtures, implement an oracle, run a study,
approve caller-supplied parameter values, establish a scientific chemical
applicability domain, authorize parameter fitting, or promote any scientific,
benchmark, product, or customer claim.  The executable authorization decision
therefore remains fail-closed until a separately reviewed protocol revision
binds all missing artifacts and a signed authorization receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from .reference_parameter_applicability import (
    FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256,
    REFERENCE_PARAMETER_APPLICABILITY_PROFILE_ID,
)


CPU_REFERENCE_VALIDATION_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.engine_v2_cpu_reference_validation_protocol/1.0.0"
)
CPU_REFERENCE_VALIDATION_PROTOCOL_ID = (
    "cpu_reference_energy_force_contract_validation/1.0.0"
)
CPU_REFERENCE_VALIDATION_PROTOCOL_VERSION = "1.0.0"
CPU_REFERENCE_VALIDATION_PROTOCOL_FROZEN_AT_UTC = "2026-07-17T02:51:00Z"
CPU_REFERENCE_VALIDATION_PROTOCOL_REVIEWER_ROLE = "repository_maintainer"
CPU_REFERENCE_VALIDATION_PROTOCOL_REVIEWER_IDENTITY_SHA256 = (
    "ffaaea9cebb5975ed140fa0633ea4cb44e1f241f6bc73c916164c0ea5123b584"
)
FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256 = (
    "1ee318ca1550953022783afa8b88eb66e3698489708c0a96969b855ca2995298"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class CPUReferenceValidationProtocolError(ValueError):
    """The frozen validation protocol, document, or authorization gate drifted."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise CPUReferenceValidationProtocolError(
            "CPU reference validation protocol is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: str, *, name: str) -> str:
    digest = str(value or "")
    if not _SHA256_RE.fullmatch(digest):
        raise CPUReferenceValidationProtocolError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return digest


@dataclass(frozen=True, slots=True)
class CPUReferenceValidationSpec:
    """Canonical immutable fixture or mutation specification."""

    spec_id: str
    kind: str
    canonical_payload_json: str

    def __post_init__(self) -> None:
        if not isinstance(self.spec_id, str) or not self.spec_id:
            raise CPUReferenceValidationProtocolError("spec_id must be non-empty")
        if self.kind not in {"fixture_profile", "mutation_contract"}:
            raise CPUReferenceValidationProtocolError(
                "unsupported validation spec kind"
            )
        try:
            parsed = json.loads(self.canonical_payload_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise CPUReferenceValidationProtocolError(
                "validation spec payload must be JSON"
            ) from exc
        if not isinstance(parsed, dict) or not parsed:
            raise CPUReferenceValidationProtocolError(
                "validation spec payload must be a non-empty object"
            )
        canonical = _canonical_bytes(parsed).decode("ascii")
        if canonical != self.canonical_payload_json:
            raise CPUReferenceValidationProtocolError(
                "validation spec payload must already be canonical JSON"
            )

    @property
    def spec_sha256(self) -> str:
        return _sha256(
            {
                "kind": self.kind,
                "payload": json.loads(self.canonical_payload_json),
                "spec_id": self.spec_id,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "kind": self.kind,
            "spec_sha256": self.spec_sha256,
            "payload": json.loads(self.canonical_payload_json),
        }


def _spec(
    spec_id: str,
    kind: str,
    payload: Mapping[str, Any],
) -> CPUReferenceValidationSpec:
    return CPUReferenceValidationSpec(
        spec_id=spec_id,
        kind=kind,
        canonical_payload_json=_canonical_bytes(dict(payload)).decode("ascii"),
    )


@dataclass(frozen=True, slots=True)
class CPUReferenceValidationMetric:
    """One predefined deterministic acceptance metric."""

    metric_id: str
    unit: str
    direction: str
    aggregation: str
    threshold_operator: str
    threshold_value: float

    def __post_init__(self) -> None:
        if not isinstance(self.metric_id, str) or not self.metric_id:
            raise CPUReferenceValidationProtocolError("metric_id must be non-empty")
        if not isinstance(self.unit, str) or not self.unit:
            raise CPUReferenceValidationProtocolError("metric unit must be non-empty")
        if self.direction not in {"minimize", "exact"}:
            raise CPUReferenceValidationProtocolError("unsupported metric direction")
        if self.aggregation not in {
            "maximum_over_required_values",
            "exact_boolean_all_required_values",
        }:
            raise CPUReferenceValidationProtocolError("unsupported metric aggregation")
        if self.threshold_operator not in {"less_than_or_equal", "equal"}:
            raise CPUReferenceValidationProtocolError(
                "unsupported metric threshold operator"
            )
        if isinstance(self.threshold_value, bool) or not isinstance(
            self.threshold_value, (int, float)
        ):
            raise CPUReferenceValidationProtocolError(
                "metric threshold must be a real number"
            )
        threshold = float(self.threshold_value)
        if not math.isfinite(threshold) or threshold < 0.0:
            raise CPUReferenceValidationProtocolError(
                "metric threshold must be finite and non-negative"
            )
        object.__setattr__(self, "threshold_value", threshold)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "unit": self.unit,
            "direction": self.direction,
            "aggregation": self.aggregation,
            "threshold_operator": self.threshold_operator,
            "threshold_value": self.threshold_value,
            "threshold_predefined_before_results": True,
        }


@dataclass(frozen=True, slots=True)
class CPUReferenceValidationCase:
    """One failure-inclusive case bound to exact fixture and mutation specs."""

    case_id: str
    category: str
    fixture_profile_id: str
    fixture_profile_sha256: str
    mutation_contract_id: str
    mutation_contract_sha256: str
    required_metric_ids: tuple[str, ...]
    expected_outcome: str
    expected_error_code: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("case_id", self.case_id),
            ("category", self.category),
            ("fixture_profile_id", self.fixture_profile_id),
            ("mutation_contract_id", self.mutation_contract_id),
        ):
            if not isinstance(value, str) or not value:
                raise CPUReferenceValidationProtocolError(f"{name} must be non-empty")
        object.__setattr__(
            self,
            "fixture_profile_sha256",
            _require_sha256(
                self.fixture_profile_sha256,
                name="fixture profile identity",
            ),
        )
        object.__setattr__(
            self,
            "mutation_contract_sha256",
            _require_sha256(
                self.mutation_contract_sha256,
                name="mutation contract identity",
            ),
        )
        if self.expected_outcome not in {"pass", "fail_closed"}:
            raise CPUReferenceValidationProtocolError(
                "case expected_outcome must be pass or fail_closed"
            )
        if len(self.required_metric_ids) != len(set(self.required_metric_ids)):
            raise CPUReferenceValidationProtocolError(
                "case metric identities must be unique"
            )
        if self.expected_outcome == "pass":
            if not self.required_metric_ids or self.expected_error_code is not None:
                raise CPUReferenceValidationProtocolError(
                    "passing cases require metrics and no error code"
                )
        elif not self.expected_error_code or self.required_metric_ids:
            raise CPUReferenceValidationProtocolError(
                "fail-closed cases require one error code and no numeric metrics"
            )

    def projection(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "lane": "synthetic_implementation_mathematics",
            "fixture_profile_id": self.fixture_profile_id,
            "fixture_profile_sha256": self.fixture_profile_sha256,
            "mutation_contract_id": self.mutation_contract_id,
            "mutation_contract_sha256": self.mutation_contract_sha256,
            "required_metric_ids": list(self.required_metric_ids),
            "expected_outcome": self.expected_outcome,
            "expected_exception_type": (
                None
                if self.expected_outcome == "pass"
                else "ReferencePhysicsApplicabilityError"
            ),
            "expected_error_code": self.expected_error_code,
        }

    @property
    def input_sha256(self) -> str:
        return _sha256(self.projection())

    def to_dict(self) -> dict[str, Any]:
        payload = self.projection()
        payload["input_sha256"] = self.input_sha256
        return payload


def _fixture_specs() -> tuple[CPUReferenceValidationSpec, ...]:
    common = {
        "coordinate_unit": "angstrom",
        "coordinate_dtype": "float64",
        "energy_unit": "kcal/mol",
        "force_unit": "kcal/mol/angstrom",
        "parameter_origin": "synthetic_protocol_values_not_fit_data",
        "scientifically_validated": False,
        "topology_sha256_materialization_rule": (
            "derive_from_the_exact_materialized_AllAtomSystem"
        ),
    }
    return (
        _spec(
            "bonded_diatomic_v1",
            "fixture_profile",
            {
                **common,
                "atoms": [
                    {"atomic_number": 6, "element": "C", "index": 0},
                    {"atomic_number": 6, "element": "C", "index": 1},
                ],
                "bonds": [[0, 1]],
                "coordinates_angstrom": [[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]],
                "parameters": {
                    "atom_nonbonded": [
                        [0, 3.0, 0.0, 0.0],
                        [1, 3.0, 0.0, 0.0],
                    ],
                    "bonds": [[0, 1, 1.0, 100.0]],
                    "excluded_pairs": [[0, 1]],
                    "cutoff_angstrom": 4.0,
                    "switch_start_angstrom": 3.0,
                },
            },
        ),
        _spec(
            "bonded_triatomic_v1",
            "fixture_profile",
            {
                **common,
                "atoms": [
                    {"atomic_number": 6, "element": "C", "index": 0},
                    {"atomic_number": 6, "element": "C", "index": 1},
                    {"atomic_number": 8, "element": "O", "index": 2},
                ],
                "bonds": [[0, 1], [1, 2]],
                "coordinates_angstrom": [
                    [1.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0],
                    [0.3623577544766736, 0.9320390859672263, 0.0],
                ],
                "parameters": {
                    "atom_nonbonded": [
                        [0, 3.0, 0.0, 0.0],
                        [1, 3.0, 0.0, 0.0],
                        [2, 2.8, 0.0, 0.0],
                    ],
                    "bonds": [[0, 1, 1.0, 100.0], [1, 2, 1.0, 100.0]],
                    "angles": [[0, 1, 2, 1.0, 20.0]],
                    "excluded_pairs": [[0, 1], [0, 2], [1, 2]],
                    "cutoff_angstrom": 4.0,
                    "switch_start_angstrom": 3.0,
                },
            },
        ),
        _spec(
            "proper_torsion_chain_v1",
            "fixture_profile",
            {
                **common,
                "atoms": [
                    {"atomic_number": 6, "element": "C", "index": index}
                    for index in range(4)
                ],
                "bonds": [[0, 1], [1, 2], [2, 3]],
                "coordinates_angstrom": [
                    [0.0, 0.0, 0.0],
                    [1.45, 0.0, 0.0],
                    [2.25, 1.15, 0.0],
                    [3.35, 1.3, 0.85],
                ],
                "parameters": {
                    "atom_nonbonded": [[index, 3.4, 0.0, 0.0] for index in range(4)],
                    "bonds": [
                        [0, 1, 1.45, 200.0],
                        [1, 2, 1.40089257261219, 180.0],
                        [2, 3, 1.3982131454109563, 160.0],
                    ],
                    "angles": [[0, 1, 2, 2.0, 45.0], [1, 2, 3, 2.1, 40.0]],
                    "torsions": [[0, 1, 2, 3, 3, 0.2, 0.5]],
                    "excluded_pairs": [
                        [0, 1],
                        [0, 2],
                        [0, 3],
                        [1, 2],
                        [1, 3],
                        [2, 3],
                    ],
                    "cutoff_angstrom": 6.0,
                    "switch_start_angstrom": 5.0,
                },
            },
        ),
        _spec(
            "nonbonded_pair_v1",
            "fixture_profile",
            {
                **common,
                "atoms": [
                    {"atomic_number": 6, "element": "C", "index": 0},
                    {"atomic_number": 8, "element": "O", "index": 1},
                ],
                "bonds": [],
                "coordinates_angstrom": [[0.0, 0.0, 0.0], [3.5, 0.0, 0.0]],
                "parameters": {
                    "atom_nonbonded": [
                        [0, 3.0, 0.1, 0.3],
                        [1, 3.4, 0.2, -0.2],
                    ],
                    "cutoff_angstrom": 6.0,
                    "switch_start_angstrom": 5.0,
                    "dielectric": 4.0,
                    "screening_kappa_per_angstrom": 0.1,
                },
            },
        ),
        _spec(
            "switch_window_pair_v1",
            "fixture_profile",
            {
                **common,
                "atoms": [
                    {"atomic_number": 6, "element": "C", "index": 0},
                    {"atomic_number": 6, "element": "C", "index": 1},
                ],
                "bonds": [],
                "coordinates_angstrom": [[0.0, 0.0, 0.0], [5.5, 0.0, 0.0]],
                "parameters": {
                    "atom_nonbonded": [
                        [0, 3.0, 0.1, 0.1],
                        [1, 3.0, 0.1, -0.1],
                    ],
                    "cutoff_angstrom": 6.0,
                    "switch_start_angstrom": 5.0,
                    "dielectric": 4.0,
                    "screening_kappa_per_angstrom": 0.1,
                },
            },
        ),
        _spec(
            "orthorhombic_periodic_pair_v1",
            "fixture_profile",
            {
                **common,
                "atoms": [
                    {"atomic_number": 6, "element": "C", "index": 0},
                    {"atomic_number": 6, "element": "C", "index": 1},
                ],
                "bonds": [],
                "coordinates_angstrom": [[0.1, 0.0, 0.0], [9.7, 0.0, 0.0]],
                "orthorhombic_cell_angstrom": [10.0, 10.0, 10.0],
                "periodic_axes": [True, True, True],
                "parameters": {
                    "atom_nonbonded": [
                        [0, 0.3, 0.1, 0.05],
                        [1, 0.3, 0.1, 0.05],
                    ],
                    "cutoff_angstrom": 1.0,
                    "switch_start_angstrom": 0.8,
                },
            },
        ),
        _spec(
            "full_five_term_chain_v1",
            "fixture_profile",
            {
                **common,
                "atoms": [
                    {"atomic_number": 6, "element": "C", "index": index}
                    for index in range(4)
                ],
                "bonds": [[0, 1], [1, 2], [2, 3]],
                "coordinates_angstrom": [
                    [0.0, 0.0, 0.0],
                    [1.45, 0.0, 0.0],
                    [2.25, 1.15, 0.0],
                    [3.35, 1.3, 0.85],
                ],
                "parameters": {
                    "atom_nonbonded": [
                        [0, 3.4, 0.08, -0.15],
                        [1, 3.4, 0.09, 0.1],
                        [2, 3.4, 0.1, 0.1],
                        [3, 3.4, 0.11, -0.05],
                    ],
                    "bonds": [
                        [0, 1, 1.45, 200.0],
                        [1, 2, 1.40089257261219, 180.0],
                        [2, 3, 1.3982131454109563, 160.0],
                    ],
                    "angles": [[0, 1, 2, 2.0, 45.0], [1, 2, 3, 2.1, 40.0]],
                    "torsions": [[0, 1, 2, 3, 3, 0.0, 0.5]],
                    "excluded_pairs": [[0, 1], [0, 2], [1, 2], [1, 3], [2, 3]],
                    "scaled_pairs": [[0, 3, 0.5, 0.8333333333]],
                    "cutoff_angstrom": 6.0,
                    "switch_start_angstrom": 5.0,
                    "dielectric": 4.0,
                    "screening_kappa_per_angstrom": 0.1,
                },
            },
        ),
    )


def _mutation_specs() -> tuple[CPUReferenceValidationSpec, ...]:
    return (
        _spec("identity_v1", "mutation_contract", {"operation": "none"}),
        _spec(
            "switch_boundary_triplet_v1",
            "mutation_contract",
            {
                "pair": [0, 1],
                "distances_angstrom": [5.9999, 6.0, 6.0001],
                "parameter_cutoff_angstrom": 6.0,
                "switch_start_angstrom": 5.0,
                "compare_energy_and_force_continuity": True,
            },
        ),
        _spec(
            "minimum_image_direct_equivalent_v1",
            "mutation_contract",
            {
                "periodic_coordinates_angstrom": [
                    [0.1, 0.0, 0.0],
                    [9.7, 0.0, 0.0],
                ],
                "periodic_cell_angstrom": [10.0, 10.0, 10.0],
                "direct_coordinates_angstrom": [
                    [0.1, 0.0, 0.0],
                    [-0.3, 0.0, 0.0],
                ],
                "direct_cell": None,
                "rebind_each_topology_sha256": True,
                "compare_energy_and_force": True,
            },
        ),
        _spec(
            "central_difference_all_coordinates_v1",
            "mutation_contract",
            {
                "coordinate_step_angstrom": 1.0e-5,
                "derivative": "negative_two_sided_central_difference",
                "scope": "every_nonsingular_batch_atom_cartesian_component",
            },
        ),
        _spec(
            "rigid_translation_v1",
            "mutation_contract",
            {"translation_angstrom": [4.0, -3.0, 2.0]},
        ),
        _spec(
            "rigid_rotation_v1",
            "mutation_contract",
            {
                "rotation_matrix": [
                    [0.0, -1.0, 0.0],
                    [1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                "force_comparison": "covariant_rotation",
            },
        ),
        _spec(
            "atom_permutation_v1",
            "mutation_contract",
            {
                "new_to_old_atom_indices": [3, 1, 0, 2],
                "remap": [
                    "atoms",
                    "coordinates",
                    "bonds",
                    "angles",
                    "torsions",
                    "nonbonded_parameters",
                    "excluded_pairs",
                    "scaled_pairs",
                ],
                "force_comparison": "inverse_permutation_equivariance",
            },
        ),
        _spec(
            "same_environment_repeat_v1",
            "mutation_contract",
            {"repeat_count": 3, "comparison": "binary64_bitwise_identity"},
        ),
        _spec(
            "topology_element_crosswire_v1",
            "mutation_contract",
            {"atom_index": 0, "replace_atomic_number": 8, "replace_element": "O"},
        ),
        _spec(
            "drop_last_nonbonded_parameter_v1",
            "mutation_contract",
            {"operation": "remove_highest_atom_index_nonbonded_row"},
        ),
        _spec(
            "drop_last_bond_parameter_v1",
            "mutation_contract",
            {"operation": "remove_last_bond_parameter_row"},
        ),
        _spec(
            "drop_last_angle_parameter_v1",
            "mutation_contract",
            {"operation": "remove_last_angle_parameter_row"},
        ),
        _spec(
            "drop_last_torsion_parameter_v1",
            "mutation_contract",
            {"operation": "remove_last_torsion_parameter_row"},
        ),
        _spec(
            "stale_neighbor_graph_v1",
            "mutation_contract",
            {
                "build_neighbor_coordinates_angstrom": [
                    [0.0, 0.0, 0.0],
                    [10.0, 0.0, 0.0],
                    [20.0, 0.0, 0.0],
                    [30.0, 0.0, 0.0],
                ],
                "evaluate_against_fixture_coordinates": True,
            },
        ),
        _spec(
            "short_neighbor_cutoff_v1",
            "mutation_contract",
            {"neighbor_cutoff_angstrom": 4.0, "parameter_cutoff_angstrom": 6.0},
        ),
        _spec(
            "atom_capacity_overflow_v1",
            "mutation_contract",
            {"applicability_max_atoms": 3, "fixture_atom_count": 4},
        ),
        _spec(
            "minimum_pair_distance_violation_v1",
            "mutation_contract",
            {
                "pair": [0, 1],
                "distance_angstrom": 1.0e-8,
                "minimum_pair_distance_angstrom": 1.0e-6,
            },
        ),
        _spec(
            "periodic_half_box_cutoff_v1",
            "mutation_contract",
            {
                "orthorhombic_cell_angstrom": [10.0, 10.0, 10.0],
                "parameter_cutoff_angstrom": 5.0,
                "required_relation": "cutoff_strictly_less_than_half_smallest_box",
            },
        ),
        _spec(
            "zero_length_angle_vector_v1",
            "mutation_contract",
            {
                "coincident_atom_indices": [0, 1],
                "expected_singularity": "angle_zero_length_vector",
            },
        ),
        _spec(
            "collinear_torsion_v1",
            "mutation_contract",
            {
                "coordinates_angstrom": [
                    [0.0, 0.0, 0.0],
                    [1.0, 0.0, 0.0],
                    [2.0, 0.0, 0.0],
                    [3.0, 0.0, 0.0],
                ],
                "expected_singularity": "torsion_undefined_for_collinear_atoms",
            },
        ),
    )


def _metrics() -> tuple[CPUReferenceValidationMetric, ...]:
    values = (
        (
            "energy_oracle_max_abs_error",
            "kcal/mol",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-10,
        ),
        (
            "energy_oracle_max_rel_error",
            "dimensionless",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-10,
        ),
        (
            "force_oracle_max_component_abs_error",
            "kcal/mol/angstrom",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-8,
        ),
        (
            "force_oracle_max_component_rel_error",
            "dimensionless",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-8,
        ),
        (
            "finite_difference_force_max_abs_error",
            "kcal/mol/angstrom",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            2.0e-4,
        ),
        (
            "finite_difference_force_max_rel_error",
            "dimensionless",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            2.0e-4,
        ),
        (
            "translation_energy_abs_drift",
            "kcal/mol",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-9,
        ),
        (
            "translation_force_max_abs_drift",
            "kcal/mol/angstrom",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            2.0e-8,
        ),
        (
            "rotation_energy_abs_drift",
            "kcal/mol",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-9,
        ),
        (
            "rotation_force_covariance_max_abs_error",
            "kcal/mol/angstrom",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            2.0e-8,
        ),
        (
            "permutation_energy_abs_drift",
            "kcal/mol",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-9,
        ),
        (
            "permutation_force_equivariance_max_abs_error",
            "kcal/mol/angstrom",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            2.0e-8,
        ),
        (
            "net_force_norm",
            "kcal/mol/angstrom",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            2.0e-8,
        ),
        (
            "switch_cutoff_energy_abs",
            "kcal/mol",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-9,
        ),
        (
            "switch_cutoff_force_max_abs",
            "kcal/mol/angstrom",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-5,
        ),
        (
            "minimum_image_energy_abs_error",
            "kcal/mol",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-12,
        ),
        (
            "minimum_image_force_max_abs_error",
            "kcal/mol/angstrom",
            "minimize",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-10,
        ),
        (
            "repeat_energy_bitwise_equal",
            "boolean",
            "exact",
            "exact_boolean_all_required_values",
            "equal",
            1.0,
        ),
        (
            "repeat_force_bitwise_equal",
            "boolean",
            "exact",
            "exact_boolean_all_required_values",
            "equal",
            1.0,
        ),
    )
    return tuple(CPUReferenceValidationMetric(*row) for row in values)


def _cases(
    fixtures: tuple[CPUReferenceValidationSpec, ...],
    mutations: tuple[CPUReferenceValidationSpec, ...],
) -> tuple[CPUReferenceValidationCase, ...]:
    fixture_map = {row.spec_id: row for row in fixtures}
    mutation_map = {row.spec_id: row for row in mutations}

    def case(
        case_id: str,
        category: str,
        fixture_id: str,
        mutation_id: str,
        metric_ids: tuple[str, ...] = (),
        error_code: str | None = None,
    ) -> CPUReferenceValidationCase:
        fixture = fixture_map[fixture_id]
        mutation = mutation_map[mutation_id]
        return CPUReferenceValidationCase(
            case_id=case_id,
            category=category,
            fixture_profile_id=fixture.spec_id,
            fixture_profile_sha256=fixture.spec_sha256,
            mutation_contract_id=mutation.spec_id,
            mutation_contract_sha256=mutation.spec_sha256,
            required_metric_ids=metric_ids,
            expected_outcome="fail_closed" if error_code else "pass",
            expected_error_code=error_code,
        )

    oracle = (
        "energy_oracle_max_abs_error",
        "energy_oracle_max_rel_error",
        "force_oracle_max_component_abs_error",
        "force_oracle_max_component_rel_error",
    )
    finite_difference = (
        "finite_difference_force_max_abs_error",
        "finite_difference_force_max_rel_error",
    )
    return (
        case(
            "bond_energy_force",
            "analytic_term",
            "bonded_diatomic_v1",
            "identity_v1",
            oracle,
        ),
        case(
            "angle_energy_force",
            "analytic_term",
            "bonded_triatomic_v1",
            "identity_v1",
            oracle,
        ),
        case(
            "proper_torsion_energy_force",
            "analytic_term",
            "proper_torsion_chain_v1",
            "identity_v1",
            oracle,
        ),
        case(
            "lennard_jones_energy_force",
            "analytic_term",
            "nonbonded_pair_v1",
            "identity_v1",
            oracle,
        ),
        case(
            "screened_coulomb_energy_force",
            "analytic_term",
            "nonbonded_pair_v1",
            "identity_v1",
            oracle,
        ),
        case(
            "lorentz_berthelot_mixing",
            "pair_semantics",
            "nonbonded_pair_v1",
            "identity_v1",
            oracle,
        ),
        case(
            "explicit_pair_scaling",
            "pair_semantics",
            "full_five_term_chain_v1",
            "identity_v1",
            oracle,
        ),
        case(
            "quintic_switch_window_and_cutoff",
            "pair_semantics",
            "switch_window_pair_v1",
            "switch_boundary_triplet_v1",
            (*oracle, "switch_cutoff_energy_abs", "switch_cutoff_force_max_abs"),
        ),
        case(
            "orthorhombic_minimum_image",
            "periodic_semantics",
            "orthorhombic_periodic_pair_v1",
            "minimum_image_direct_equivalent_v1",
            (
                *oracle,
                "minimum_image_energy_abs_error",
                "minimum_image_force_max_abs_error",
            ),
        ),
        case(
            "full_five_term_composition",
            "composition",
            "full_five_term_chain_v1",
            "identity_v1",
            (*oracle, "net_force_norm"),
        ),
        case(
            "full_force_central_difference",
            "gradient",
            "full_five_term_chain_v1",
            "central_difference_all_coordinates_v1",
            finite_difference,
        ),
        case(
            "rigid_translation_invariance",
            "invariance",
            "full_five_term_chain_v1",
            "rigid_translation_v1",
            (
                "translation_energy_abs_drift",
                "translation_force_max_abs_drift",
                "net_force_norm",
            ),
        ),
        case(
            "rigid_rotation_invariance",
            "invariance",
            "full_five_term_chain_v1",
            "rigid_rotation_v1",
            ("rotation_energy_abs_drift", "rotation_force_covariance_max_abs_error"),
        ),
        case(
            "atom_permutation_equivariance",
            "invariance",
            "full_five_term_chain_v1",
            "atom_permutation_v1",
            (
                "permutation_energy_abs_drift",
                "permutation_force_equivariance_max_abs_error",
            ),
        ),
        case(
            "same_environment_repeat_determinism",
            "determinism",
            "full_five_term_chain_v1",
            "same_environment_repeat_v1",
            ("repeat_energy_bitwise_equal", "repeat_force_bitwise_equal"),
        ),
        case(
            "topology_identity_crosswire",
            "fail_closed",
            "full_five_term_chain_v1",
            "topology_element_crosswire_v1",
            error_code="parameter_topology_identity_mismatch",
        ),
        case(
            "missing_nonbonded_parameter",
            "fail_closed",
            "full_five_term_chain_v1",
            "drop_last_nonbonded_parameter_v1",
            error_code="nonbonded_parameters_do_not_cover_all_atoms",
        ),
        case(
            "missing_bond_parameter",
            "fail_closed",
            "full_five_term_chain_v1",
            "drop_last_bond_parameter_v1",
            error_code="bond_parameters_do_not_exactly_cover_system_bonds",
        ),
        case(
            "missing_angle_parameter",
            "fail_closed",
            "full_five_term_chain_v1",
            "drop_last_angle_parameter_v1",
            error_code="angle_parameters_do_not_exactly_cover_system_topology",
        ),
        case(
            "missing_torsion_parameter",
            "fail_closed",
            "full_five_term_chain_v1",
            "drop_last_torsion_parameter_v1",
            error_code="torsion_parameters_do_not_exactly_cover_system_topology",
        ),
        case(
            "stale_neighbor_graph",
            "fail_closed",
            "full_five_term_chain_v1",
            "stale_neighbor_graph_v1",
            error_code="neighbor_graph_not_bound_to_current_system",
        ),
        case(
            "neighbor_cutoff_too_short",
            "fail_closed",
            "full_five_term_chain_v1",
            "short_neighbor_cutoff_v1",
            error_code="neighbor_cutoff_shorter_than_parameter_cutoff",
        ),
        case(
            "atom_capacity_overflow",
            "fail_closed",
            "full_five_term_chain_v1",
            "atom_capacity_overflow_v1",
            error_code="atom_count_outside_applicability_domain",
        ),
        case(
            "minimum_pair_distance_violation",
            "fail_closed",
            "nonbonded_pair_v1",
            "minimum_pair_distance_violation_v1",
            error_code="nonbonded_pair_below_minimum_pair_distance_angstrom",
        ),
        case(
            "periodic_half_box_cutoff",
            "fail_closed",
            "orthorhombic_periodic_pair_v1",
            "periodic_half_box_cutoff_v1",
            error_code="periodic_cutoff_not_below_half_smallest_box_length",
        ),
        case(
            "zero_length_angle_vector",
            "fail_closed",
            "bonded_triatomic_v1",
            "zero_length_angle_vector_v1",
            error_code="angle_zero_length_vector",
        ),
        case(
            "collinear_torsion",
            "fail_closed",
            "proper_torsion_chain_v1",
            "collinear_torsion_v1",
            error_code="torsion_undefined_for_collinear_atoms",
        ),
    )


_BLOCKERS = (
    "fixture_materializer_not_implemented",
    "independent_analytic_oracle_not_implemented",
    "oracle_source_identity_not_bound",
    "reviewed_runtime_parameter_values_not_bound",
    "scientific_parameter_applicability_domain_not_established",
    "scientific_holdout_case_manifest_not_frozen",
    "independent_scientific_review_missing",
    "signed_execution_authorization_receipt_missing",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "minimization_validation_protocol_missing",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


def _claim_policy() -> dict[str, bool]:
    return {
        "protocol_definition_frozen": True,
        "synthetic_case_identities_frozen": True,
        "acceptance_thresholds_predefined": True,
        "failure_rows_retained": True,
        "fixture_materializer_implemented": False,
        "independent_oracle_implemented": False,
        "independent_scientific_review_completed": False,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
        "force_or_energy_validated": False,
        "runtime_parameter_values_independently_reviewed": False,
        "scientific_applicability_established": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "minimization_validated": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


@dataclass(frozen=True, slots=True)
class CPUReferenceValidationProtocol:
    """Immutable pre-result protocol for CPU reference implementation checks."""

    schema_id: str
    protocol_id: str
    protocol_version: str
    frozen_at_utc: str
    reviewer_role: str
    reviewer_identity_sha256: str
    h5_applicability_record_sha256: str
    fixtures: tuple[CPUReferenceValidationSpec, ...]
    mutations: tuple[CPUReferenceValidationSpec, ...]
    metrics: tuple[CPUReferenceValidationMetric, ...]
    cases: tuple[CPUReferenceValidationCase, ...]
    superseded: bool = False
    revoked: bool = False

    def __post_init__(self) -> None:
        if self.schema_id != CPU_REFERENCE_VALIDATION_PROTOCOL_SCHEMA_ID:
            raise CPUReferenceValidationProtocolError(
                "unsupported CPU reference validation protocol schema"
            )
        if self.protocol_id != CPU_REFERENCE_VALIDATION_PROTOCOL_ID:
            raise CPUReferenceValidationProtocolError(
                "unsupported CPU reference validation protocol identity"
            )
        if self.protocol_version != CPU_REFERENCE_VALIDATION_PROTOCOL_VERSION:
            raise CPUReferenceValidationProtocolError(
                "unsupported CPU reference validation protocol version"
            )
        if not _UTC_RE.fullmatch(self.frozen_at_utc):
            raise CPUReferenceValidationProtocolError(
                "protocol timestamp must be second-resolution UTC"
            )
        if not self.reviewer_role:
            raise CPUReferenceValidationProtocolError(
                "protocol reviewer role must be non-empty"
            )
        object.__setattr__(
            self,
            "reviewer_identity_sha256",
            _require_sha256(self.reviewer_identity_sha256, name="reviewer identity"),
        )
        object.__setattr__(
            self,
            "h5_applicability_record_sha256",
            _require_sha256(
                self.h5_applicability_record_sha256,
                name="H5 applicability record identity",
            ),
        )
        fixture_map = {row.spec_id: row.spec_sha256 for row in self.fixtures}
        mutation_map = {row.spec_id: row.spec_sha256 for row in self.mutations}
        metric_ids = {row.metric_id for row in self.metrics}
        if (
            not fixture_map
            or len(fixture_map) != len(self.fixtures)
            or not mutation_map
            or len(mutation_map) != len(self.mutations)
            or not metric_ids
            or len(metric_ids) != len(self.metrics)
        ):
            raise CPUReferenceValidationProtocolError(
                "protocol fixture, mutation, and metric identities must be unique"
            )
        if not self.cases or len({row.case_id for row in self.cases}) != len(
            self.cases
        ):
            raise CPUReferenceValidationProtocolError(
                "protocol case identities must be explicit and unique"
            )
        for row in self.cases:
            if fixture_map.get(row.fixture_profile_id) != row.fixture_profile_sha256:
                raise CPUReferenceValidationProtocolError(
                    "case fixture identity does not match the frozen manifest"
                )
            if (
                mutation_map.get(row.mutation_contract_id)
                != row.mutation_contract_sha256
            ):
                raise CPUReferenceValidationProtocolError(
                    "case mutation identity does not match the frozen manifest"
                )
            if not set(row.required_metric_ids).issubset(metric_ids):
                raise CPUReferenceValidationProtocolError(
                    "case references an unknown validation metric"
                )
        if type(self.superseded) is not bool or type(self.revoked) is not bool:
            raise CPUReferenceValidationProtocolError(
                "protocol review state flags must be booleans"
            )
        if self.superseded or self.revoked:
            raise CPUReferenceValidationProtocolError(
                "the frozen CPU reference validation protocol cannot be "
                "superseded or revoked"
            )

    @property
    def fixture_manifest_sha256(self) -> str:
        return _sha256(
            {
                "fixtures": [row.to_dict() for row in self.fixtures],
                "mutations": [row.to_dict() for row in self.mutations],
                "cases": [row.to_dict() for row in self.cases],
            }
        )

    def projection(self) -> dict[str, Any]:
        pass_count = sum(row.expected_outcome == "pass" for row in self.cases)
        failure_count = len(self.cases) - pass_count
        return {
            "schema_id": self.schema_id,
            "protocol_id": self.protocol_id,
            "protocol_version": self.protocol_version,
            "frozen_at_utc": self.frozen_at_utc,
            "purpose": {
                "scope": "cpu_reference_energy_force_contract_validation",
                "protocol_definition_only": True,
                "result_collection_performed": False,
                "enables_new_physics_execution": False,
                "authorizes_validation_execution": False,
                "authorizes_parameter_fitting_proposal": False,
                "authorizes_parameter_fitting": False,
            },
            "dependencies": {
                "h5_applicability_profile_id": (
                    REFERENCE_PARAMETER_APPLICABILITY_PROFILE_ID
                ),
                "h5_applicability_record_sha256": (self.h5_applicability_record_sha256),
                "exact_h5_document_required_at_execution": True,
                "exact_h5_runtime_source_verification_required_at_execution": True,
                "dependency_claim_status_inherited": False,
            },
            "validation_lanes": {
                "synthetic_implementation_mathematics": {
                    "status": "protocol_frozen_not_executed",
                    "purpose": (
                        "validate_implemented_equations_gradients_invariance_"
                        "determinism_and_fail_closed_admission"
                    ),
                    "parameter_origin": "synthetic_protocol_values_not_fit_data",
                    "can_establish_physical_parameter_accuracy": False,
                    "can_establish_chemical_applicability": False,
                },
                "scientific_parameterized_force_field": {
                    "status": "not_ready_for_protocol_execution",
                    "case_manifest_frozen": False,
                    "reviewed_runtime_parameter_values_bound": False,
                    "chemical_applicability_domain_frozen": False,
                    "independent_holdout_frozen": False,
                    "independent_reference_artifacts_bound": False,
                    "result_collection_allowed": False,
                },
            },
            "fixture_manifest": {
                "status": "specification_only_materializer_not_implemented",
                "fixture_manifest_sha256": self.fixture_manifest_sha256,
                "fixture_count": len(self.fixtures),
                "mutation_count": len(self.mutations),
                "case_count": len(self.cases),
                "expected_pass_case_count": pass_count,
                "expected_fail_closed_case_count": failure_count,
                "denominator": "all_frozen_cases",
                "skipped_cases_allowed": False,
                "failure_rows_retained": True,
                "fixtures": [row.to_dict() for row in self.fixtures],
                "mutations": [row.to_dict() for row in self.mutations],
                "cases": [row.to_dict() for row in self.cases],
            },
            "numerical_protocol": {
                "coordinate_dtype": "float64",
                "energy_unit": "kcal/mol",
                "force_unit": "kcal/mol/angstrom",
                "force_definition": "negative_coordinate_gradient_of_total_energy",
                "finite_difference": {
                    "method": "two_sided_central_difference",
                    "coordinate_step_angstrom": 1.0e-5,
                    "comparison_scope": (
                        "every_nonsingular_batch_atom_cartesian_component"
                    ),
                },
                "relative_error_denominator": ("max(abs(independent_reference),1e-12)"),
                "metric_aggregation": (
                    "every_required_value_and_every_case_must_pass_individually"
                ),
                "cross_case_averaging_allowed": False,
                "missing_metric_is_failure": True,
                "metrics": [row.to_dict() for row in self.metrics],
            },
            "independent_oracle_policy": {
                "required_before_execution": True,
                "implemented": False,
                "source_sha256": None,
                "artifact_sha256": None,
                "must_be_separate_source_file": True,
                "must_not_import": [
                    "betelgeuze_engine_v2.physics.reference_forcefield",
                    "betelgeuze_engine_v2.physics.reference_validation_protocol",
                ],
                "allowed_role": (
                    "independent_scalar_analytic_equations_and_derivatives_only"
                ),
                "external_molecular_solver_required": False,
                "independent_reviewer_identity_must_differ_from_"
                "implementation_author": True,
            },
            "execution_environment_receipt": {
                "cpu_only": True,
                "python_versions": ["3.10", "3.11", "3.12"],
                "torch_version": "2.6.0",
                "numpy_version": "1.26.4",
                "network_access_allowed": False,
                "gpu_visibility_required_empty": True,
                "exact_code_commit_required": True,
                "dependency_artifact_sha256_required": True,
                "environment_fingerprint_sha256_required": True,
                "command_argv_required": True,
                "seed_required": True,
                "thread_count_required": True,
            },
            "result_receipt": {
                "created": False,
                "result_schema_frozen": False,
                "required_future_fields": [
                    "protocol_sha256",
                    "h5_applicability_record_sha256",
                    "fixture_manifest_sha256",
                    "code_commit_sha",
                    "dependency_artifact_sha256_rows",
                    "environment_fingerprint_sha256",
                    "command_argv",
                    "seed",
                    "case_input_sha256",
                    "case_status",
                    "component_energy_values_and_units",
                    "total_energy_value_and_unit",
                    "force_array_shape_dtype_unit_and_sha256",
                    "metric_values",
                    "expected_and_observed_error_codes",
                    "artifact_path_confinement_verification",
                    "reviewer_identity_sha256",
                    "reviewed_at_utc",
                    "supersession_and_revocation_state",
                ],
                "case_order_must_match_protocol": True,
                "all_failure_rows_must_remain_in_denominator": True,
                "partial_result_promotion_allowed": False,
            },
            "authorization_gate": {
                "status": "closed",
                "validation_execution_authorized": False,
                "parameter_fitting_proposal_authorized": False,
                "parameter_fitting_authorized": False,
                "signed_authorization_receipt_schema_frozen": False,
                "signed_authorization_receipt_present": False,
                "required_before_opening": [
                    "exact_protocol_and_h5_dependency_verified",
                    "fixture_materializer_implemented_and_source_sha256_bound",
                    "independent_oracle_implemented_and_source_sha256_bound",
                    "scientific_lane_case_manifest_frozen_before_results",
                    "reviewed_runtime_parameter_values_and_provenance_bound",
                    "scientific_applicability_domain_frozen",
                    "independent_scientific_reviewer_acceptance_recorded",
                    "signed_nonexpired_authorization_receipt_verified",
                    "supersession_and_revocation_chain_clear",
                ],
                "current_blockers": list(_BLOCKERS),
            },
            "review": {
                "status": "maintainer_reviewed_protocol_boundary_only",
                "frozen_at_utc": self.frozen_at_utc,
                "reviewer_role": self.reviewer_role,
                "reviewer_identity_sha256": self.reviewer_identity_sha256,
                "independent_scientific_review_completed": False,
                "superseded": self.superseded,
                "revoked": self.revoked,
                "supersession_protocol_sha256": None,
                "revocation_reason": None,
            },
            "claim_policy": _claim_policy(),
            "blockers": list(_BLOCKERS),
        }

    @property
    def protocol_sha256(self) -> str:
        return _sha256(self.projection())

    def to_dict(self) -> dict[str, Any]:
        payload = self.projection()
        payload["protocol_sha256"] = self.protocol_sha256
        return payload


def _build_protocol() -> CPUReferenceValidationProtocol:
    fixtures = _fixture_specs()
    mutations = _mutation_specs()
    return CPUReferenceValidationProtocol(
        schema_id=CPU_REFERENCE_VALIDATION_PROTOCOL_SCHEMA_ID,
        protocol_id=CPU_REFERENCE_VALIDATION_PROTOCOL_ID,
        protocol_version=CPU_REFERENCE_VALIDATION_PROTOCOL_VERSION,
        frozen_at_utc=CPU_REFERENCE_VALIDATION_PROTOCOL_FROZEN_AT_UTC,
        reviewer_role=CPU_REFERENCE_VALIDATION_PROTOCOL_REVIEWER_ROLE,
        reviewer_identity_sha256=(
            CPU_REFERENCE_VALIDATION_PROTOCOL_REVIEWER_IDENTITY_SHA256
        ),
        h5_applicability_record_sha256=(
            FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256
        ),
        fixtures=fixtures,
        mutations=mutations,
        metrics=_metrics(),
        cases=_cases(fixtures, mutations),
    )


def frozen_cpu_reference_validation_protocol() -> CPUReferenceValidationProtocol:
    """Return the immutable pre-result protocol and reject constant drift."""

    protocol = _build_protocol()
    if protocol.protocol_sha256 != FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256:
        raise CPUReferenceValidationProtocolError(
            "frozen CPU reference validation protocol SHA-256 drifted"
        )
    return protocol


def cpu_reference_validation_protocol_document(
    protocol: CPUReferenceValidationProtocol | None = None,
) -> dict[str, Any]:
    """Return a detached canonical JSON-compatible protocol document."""

    selected = protocol or frozen_cpu_reference_validation_protocol()
    payload = selected.to_dict()
    projection = {
        key: value for key, value in payload.items() if key != "protocol_sha256"
    }
    if payload["protocol_sha256"] != _sha256(projection):
        raise CPUReferenceValidationProtocolError(
            "CPU reference validation protocol digest is inconsistent"
        )
    return json.loads(_canonical_bytes(payload).decode("ascii"))


def require_cpu_reference_validation_protocol_document(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    """Require exact equality with the frozen pre-result protocol document."""

    if not isinstance(document, Mapping):
        raise CPUReferenceValidationProtocolError(
            "CPU reference validation protocol document must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(document)).decode("ascii"))
    digest = observed.get("protocol_sha256")
    _require_sha256(digest, name="protocol_sha256")
    projection = {
        key: value for key, value in observed.items() if key != "protocol_sha256"
    }
    if digest != _sha256(projection):
        raise CPUReferenceValidationProtocolError(
            "CPU reference validation protocol document digest mismatch"
        )
    expected = cpu_reference_validation_protocol_document()
    if observed != expected:
        raise CPUReferenceValidationProtocolError(
            "CPU reference validation document does not match the frozen protocol"
        )
    return observed


@dataclass(frozen=True, slots=True)
class CPUReferenceValidationAuthorizationDecision:
    """Executable fail-closed authorization decision for the frozen protocol."""

    protocol_sha256: str
    validation_execution_authorized: bool
    parameter_fitting_proposal_authorized: bool
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "protocol_sha256",
            _require_sha256(self.protocol_sha256, name="authorization protocol"),
        )
        if (
            type(self.validation_execution_authorized) is not bool
            or type(self.parameter_fitting_proposal_authorized) is not bool
        ):
            raise CPUReferenceValidationProtocolError(
                "authorization values must be booleans"
            )
        if not self.blockers:
            raise CPUReferenceValidationProtocolError(
                "closed authorization decision must retain blockers"
            )
        if (
            self.validation_execution_authorized
            or self.parameter_fitting_proposal_authorized
        ):
            raise CPUReferenceValidationProtocolError(
                "the frozen pre-result protocol cannot authorize execution or fitting"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_sha256": self.protocol_sha256,
            "validation_execution_authorized": (self.validation_execution_authorized),
            "parameter_fitting_proposal_authorized": (
                self.parameter_fitting_proposal_authorized
            ),
            "blockers": list(self.blockers),
        }


def cpu_reference_validation_authorization_decision(
    protocol_document: Mapping[str, Any] | None = None,
) -> CPUReferenceValidationAuthorizationDecision:
    """Evaluate the current exact protocol and return its closed gate decision."""

    if protocol_document is None:
        document = cpu_reference_validation_protocol_document()
    else:
        document = require_cpu_reference_validation_protocol_document(protocol_document)
    gate = document["authorization_gate"]
    if gate["status"] != "closed" or gate["current_blockers"] != list(_BLOCKERS):
        raise CPUReferenceValidationProtocolError(
            "CPU reference validation authorization gate drifted"
        )
    return CPUReferenceValidationAuthorizationDecision(
        protocol_sha256=document["protocol_sha256"],
        validation_execution_authorized=False,
        parameter_fitting_proposal_authorized=False,
        blockers=_BLOCKERS,
    )


def require_cpu_reference_validation_execution_authorized(
    protocol_document: Mapping[str, Any] | None = None,
) -> None:
    """Fail closed until a reviewed future protocol explicitly opens the gate."""

    decision = cpu_reference_validation_authorization_decision(protocol_document)
    raise CPUReferenceValidationProtocolError(
        "CPU reference validation execution is not authorized: "
        + ", ".join(decision.blockers)
    )


def cpu_reference_validation_protocol_json_bytes() -> bytes:
    """Serialize the frozen protocol as canonical private-artifact JSON bytes."""

    return _canonical_bytes(cpu_reference_validation_protocol_document()) + b"\n"


def write_cpu_reference_validation_protocol_json(
    path: str | os.PathLike[str],
) -> str:
    """Atomically write the frozen protocol with owner-only permissions."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise CPUReferenceValidationProtocolError(
            "refusing to replace a symlink destination"
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(cpu_reference_validation_protocol_json_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        if destination.is_symlink():
            raise CPUReferenceValidationProtocolError(
                "refusing to replace a symlink destination"
            )
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()
    return FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256


__all__ = [
    "CPU_REFERENCE_VALIDATION_PROTOCOL_ID",
    "CPU_REFERENCE_VALIDATION_PROTOCOL_SCHEMA_ID",
    "CPU_REFERENCE_VALIDATION_PROTOCOL_VERSION",
    "FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256",
    "CPUReferenceValidationAuthorizationDecision",
    "CPUReferenceValidationCase",
    "CPUReferenceValidationMetric",
    "CPUReferenceValidationProtocol",
    "CPUReferenceValidationProtocolError",
    "CPUReferenceValidationSpec",
    "cpu_reference_validation_authorization_decision",
    "cpu_reference_validation_protocol_document",
    "cpu_reference_validation_protocol_json_bytes",
    "frozen_cpu_reference_validation_protocol",
    "require_cpu_reference_validation_execution_authorized",
    "require_cpu_reference_validation_protocol_document",
    "write_cpu_reference_validation_protocol_json",
]
