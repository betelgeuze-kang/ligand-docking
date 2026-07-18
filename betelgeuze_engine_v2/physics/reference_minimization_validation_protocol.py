"""Frozen, execution-disabled CPU minimization validation protocol.

This module freezes case identities, acceptance metrics, implementation-source
dependencies, failure-inclusive accounting, and claim boundaries before any
scientific minimization result is collected.  It deliberately does not provide
a fixture materializer, an independent minimization implementation, trusted
review or operator keys, an execution runner, or a result receipt.

The protocol is implementation-contract evidence only.  It does not validate
caller-supplied parameters, chemical applicability, minimization accuracy,
solvation accuracy, a benchmark, a product route, or customer execution.
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

from . import (
    reference_constrained_minimization,
    reference_forcefield,
    reference_forcefield_v2,
    reference_minimization,
    reference_solvation,
)


CPU_MINIMIZATION_VALIDATION_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.engine_v2_cpu_minimization_validation_protocol/2.0.0"
)
CPU_MINIMIZATION_VALIDATION_PROTOCOL_ID = (
    "cpu_reference_minimization_contract_validation/2.0.0"
)
CPU_MINIMIZATION_VALIDATION_PROTOCOL_VERSION = "2.0.0"
CPU_MINIMIZATION_VALIDATION_PROTOCOL_FROZEN_AT_UTC = "2026-07-19T06:00:00Z"
FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256 = (
    "46c775ea0c815b4414f02d6613984ad7117aa488787fb7f9b23889c591f0812c"
)

CPU_MINIMIZATION_VALIDATION_SCIENTIFIC_BLOCKERS = (
    "protocol_definition_is_not_validation_result_evidence",
    "fixture_materializer_not_implemented",
    "independent_minimization_reference_not_bound",
    "independent_scientific_review_missing",
    "signed_execution_authorization_receipt_missing",
    "trusted_runner_environment_not_bound",
    "production_result_receipt_missing",
    "independent_result_review_missing",
    "reviewed_runtime_parameter_values_not_bound",
    "scientific_parameter_applicability_not_established",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,95}$")


class CPUMinimizationValidationProtocolError(ValueError):
    """The frozen minimization validation protocol or gate drifted."""


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
        raise CPUMinimizationValidationProtocolError(
            "minimization validation protocol is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: str, *, name: str) -> str:
    digest = str(value or "")
    if not _SHA256_RE.fullmatch(digest):
        raise CPUMinimizationValidationProtocolError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return digest


def _module_source_sha256(module: object) -> str:
    path_value = getattr(module, "__file__", None)
    if not isinstance(path_value, str) or not path_value.endswith(".py"):
        raise CPUMinimizationValidationProtocolError(
            "minimization dependency must resolve to Python source"
        )
    path = Path(path_value)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise CPUMinimizationValidationProtocolError(
            "minimization dependency source is unavailable"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class CPUMinimizationValidationMetric:
    """One predefined case-level acceptance metric."""

    metric_id: str
    unit: str
    aggregation: str
    threshold_operator: str
    threshold_value: float

    def __post_init__(self) -> None:
        if not _CASE_ID_RE.fullmatch(self.metric_id):
            raise CPUMinimizationValidationProtocolError("invalid metric_id")
        if not isinstance(self.unit, str) or not self.unit:
            raise CPUMinimizationValidationProtocolError(
                "metric unit must be non-empty"
            )
        if self.aggregation not in {
            "exact_case_value",
            "maximum_over_accepted_steps",
            "maximum_over_required_values",
            "exact_boolean_all_required_values",
        }:
            raise CPUMinimizationValidationProtocolError(
                "unsupported metric aggregation"
            )
        if self.threshold_operator not in {
            "less_than_or_equal",
            "greater_than_or_equal",
            "equal",
        }:
            raise CPUMinimizationValidationProtocolError(
                "unsupported metric threshold operator"
            )
        if isinstance(self.threshold_value, bool) or not isinstance(
            self.threshold_value, (int, float)
        ):
            raise CPUMinimizationValidationProtocolError(
                "metric threshold must be numeric"
            )
        threshold = float(self.threshold_value)
        if not math.isfinite(threshold):
            raise CPUMinimizationValidationProtocolError(
                "metric threshold must be finite"
            )
        object.__setattr__(self, "threshold_value", threshold)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "unit": self.unit,
            "aggregation": self.aggregation,
            "threshold_operator": self.threshold_operator,
            "threshold_value": self.threshold_value,
            "threshold_predefined_before_results": True,
        }


@dataclass(frozen=True, slots=True)
class CPUMinimizationValidationCase:
    """One exact pass or fail-closed minimization protocol case."""

    case_id: str
    lane: str
    evaluator_scope: str
    canonical_input: Mapping[str, Any]
    expected_outcome: str
    required_metric_ids: tuple[str, ...] = ()
    expected_error_code: str | None = None

    def __post_init__(self) -> None:
        if not _CASE_ID_RE.fullmatch(self.case_id):
            raise CPUMinimizationValidationProtocolError("invalid case_id")
        if self.lane not in {
            "unconstrained_v1",
            "constrained_v2",
            "fixed_born_constrained_v2",
            "fail_closed_identity_or_applicability",
        }:
            raise CPUMinimizationValidationProtocolError("unsupported case lane")
        if self.evaluator_scope not in {
            "reference_forcefield_v1",
            "reference_forcefield_v2",
            "reference_forcefield_v2_with_fixed_born",
        }:
            raise CPUMinimizationValidationProtocolError(
                "unsupported evaluator scope"
            )
        canonical_input = dict(self.canonical_input)
        if not canonical_input:
            raise CPUMinimizationValidationProtocolError(
                "case input must be non-empty"
            )
        _canonical_bytes(canonical_input)
        object.__setattr__(self, "canonical_input", canonical_input)
        if len(self.required_metric_ids) != len(set(self.required_metric_ids)):
            raise CPUMinimizationValidationProtocolError(
                "case metric identities must be unique"
            )
        if self.expected_outcome == "pass":
            if not self.required_metric_ids or self.expected_error_code is not None:
                raise CPUMinimizationValidationProtocolError(
                    "passing cases require metrics and no error code"
                )
        elif self.expected_outcome == "fail_closed":
            if self.required_metric_ids or not self.expected_error_code:
                raise CPUMinimizationValidationProtocolError(
                    "fail-closed cases require an error code and no metrics"
                )
        else:
            raise CPUMinimizationValidationProtocolError(
                "case expected_outcome must be pass or fail_closed"
            )

    def projection(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "lane": self.lane,
            "evaluator_scope": self.evaluator_scope,
            "canonical_input": dict(self.canonical_input),
            "expected_outcome": self.expected_outcome,
            "required_metric_ids": list(self.required_metric_ids),
            "expected_error_code": self.expected_error_code,
        }

    @property
    def input_sha256(self) -> str:
        return _sha256(self.projection())

    def to_dict(self) -> dict[str, Any]:
        return {**self.projection(), "input_sha256": self.input_sha256}


@dataclass(frozen=True, slots=True)
class CPUMinimizationValidationAuthorizationDecision:
    """Explicit closed execution and promotion decision."""

    protocol_sha256: str
    blockers: tuple[str, ...]
    execution_authorized: bool = False
    parameter_fitting_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "protocol_sha256",
            _require_sha256(self.protocol_sha256, name="protocol identity"),
        )
        if not self.blockers or len(self.blockers) != len(set(self.blockers)):
            raise CPUMinimizationValidationProtocolError(
                "authorization blockers must be non-empty and unique"
            )
        if self.execution_authorized or self.parameter_fitting_authorized:
            raise CPUMinimizationValidationProtocolError(
                "frozen minimization protocol must remain execution-disabled"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_sha256": self.protocol_sha256,
            "execution_authorized": self.execution_authorized,
            "parameter_fitting_authorized": self.parameter_fitting_authorized,
            "blockers": list(self.blockers),
        }


def _metrics() -> tuple[CPUMinimizationValidationMetric, ...]:
    return (
        CPUMinimizationValidationMetric(
            "accepted_energy_monotonic",
            "boolean",
            "exact_boolean_all_required_values",
            "equal",
            1.0,
        ),
        CPUMinimizationValidationMetric(
            "final_energy_change",
            "kcal/mol",
            "exact_case_value",
            "less_than_or_equal",
            0.0,
        ),
        CPUMinimizationValidationMetric(
            "minimum_required_energy_decrease",
            "kcal/mol",
            "exact_case_value",
            "greater_than_or_equal",
            1.0e-8,
        ),
        CPUMinimizationValidationMetric(
            "final_force_max_abs",
            "kcal/mol/angstrom",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-7,
        ),
        CPUMinimizationValidationMetric(
            "final_tangent_force_max_abs",
            "kcal/mol/angstrom",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-7,
        ),
        CPUMinimizationValidationMetric(
            "constraint_max_abs_residual",
            "angstrom",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-10,
        ),
        CPUMinimizationValidationMetric(
            "checkpoint_resume_bitwise_equal",
            "boolean",
            "exact_boolean_all_required_values",
            "equal",
            1.0,
        ),
        CPUMinimizationValidationMetric(
            "failure_ledger_complete",
            "boolean",
            "exact_boolean_all_required_values",
            "equal",
            1.0,
        ),
        CPUMinimizationValidationMetric(
            "independent_reference_final_coordinate_max_abs_error",
            "angstrom",
            "maximum_over_required_values",
            "less_than_or_equal",
            1.0e-8,
        ),
        CPUMinimizationValidationMetric(
            "independent_reference_final_energy_abs_error",
            "kcal/mol",
            "exact_case_value",
            "less_than_or_equal",
            1.0e-10,
        ),
    )


_BASE_INPUT = {
    "coordinate_dtype": "float64",
    "device": "cpu",
    "model_count": 1,
    "parameter_origin": "synthetic_protocol_values_not_fit_data",
    "maximum_iterations": 64,
    "maximum_backtracks": 16,
    "armijo_coefficient": 1.0e-4,
    "initial_step_angstrom_squared_mol_per_kcal": 1.0e-3,
}


_FIXTURE_PAYLOADS: dict[str, dict[str, Any]] = {
    "two_atom_harmonic_bond": {
        "atoms": [
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
        ],
        "coordinates_angstrom": [[0.0, 0.0, 0.0], [1.4, 0.0, 0.0]],
        "bonds": [[0, 1, 100.0, 1.0]],
        "angles": [],
        "proper_torsions": [],
        "atom_nonbonded": [[0.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
        "pair_scaling": [],
        "nonbonded": {
            "cutoff_angstrom": 4.0,
            "switch_distance_angstrom": 3.0,
            "screening_kappa_per_angstrom": 0.0,
        },
    },
    "four_atom_mixed_terms": {
        "atoms": [
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
            {"element": "O", "formal_charge": 0, "mass_dalton": 15.999},
            {"element": "H", "formal_charge": 0, "mass_dalton": 1.008},
        ],
        "coordinates_angstrom": [
            [0.0, 0.0, 0.0],
            [1.3, 0.1, 0.0],
            [2.2, 1.0, 0.2],
            [3.0, 1.1, 1.0],
        ],
        "bonds": [
            [0, 1, 120.0, 1.1],
            [1, 2, 110.0, 1.2],
            [2, 3, 90.0, 1.0],
        ],
        "angles": [[0, 1, 2, 35.0, 1.95], [1, 2, 3, 30.0, 1.90]],
        "proper_torsions": [[0, 1, 2, 3, 1.5, 2, 0.25]],
        "atom_nonbonded": [
            [0.10, 1.70, 0.15],
            [-0.05, 1.65, 0.14],
            [-0.25, 1.50, 0.12],
            [0.20, 1.10, 0.03],
        ],
        "pair_scaling": [[0, 3, 0.5, 0.8333333333333334]],
        "nonbonded": {
            "cutoff_angstrom": 5.0,
            "switch_distance_angstrom": 4.0,
            "screening_kappa_per_angstrom": 0.2,
        },
    },
    "two_atom_bond_at_equilibrium": {
        "atoms": [
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
        ],
        "coordinates_angstrom": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        "bonds": [[0, 1, 100.0, 1.0]],
        "angles": [],
        "proper_torsions": [],
        "atom_nonbonded": [[0.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
        "pair_scaling": [],
        "nonbonded": {
            "cutoff_angstrom": 4.0,
            "switch_distance_angstrom": 3.0,
            "screening_kappa_per_angstrom": 0.0,
        },
    },
    "three_atom_constrained_angle": {
        "atoms": [
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
        ],
        "coordinates_angstrom": [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.6, 0.8, 0.0],
        ],
        "bonds": [[0, 1, 100.0, 1.0], [1, 2, 100.0, 1.0]],
        "angles": [[0, 1, 2, 30.0, 1.9106332362490186]],
        "proper_torsions": [],
        "impropers": [],
        "distance_constraints": [[0, 1, 1.0], [1, 2, 1.0]],
        "atom_nonbonded": [
            [0.0, 1.7, 0.0],
            [0.0, 1.7, 0.0],
            [0.0, 1.7, 0.0],
        ],
        "pair_scaling": [],
        "nonbonded": {
            "cutoff_angstrom": 4.0,
            "switch_distance_angstrom": 3.0,
            "screening_kappa_per_angstrom": 0.0,
        },
    },
    "three_atom_charged_constrained_angle": {
        "atoms": [
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
        ],
        "coordinates_angstrom": [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.6, 0.8, 0.0],
        ],
        "bonds": [[0, 1, 100.0, 1.0], [1, 2, 100.0, 1.0]],
        "angles": [[0, 1, 2, 30.0, 1.9106332362490186]],
        "proper_torsions": [],
        "impropers": [],
        "distance_constraints": [[0, 1, 1.0], [1, 2, 1.0]],
        "atom_nonbonded": [
            [0.8, 1.7, 0.0],
            [-0.4, 1.7, 0.0],
            [-0.4, 1.7, 0.0],
        ],
        "pair_scaling": [],
        "nonbonded": {
            "cutoff_angstrom": 4.0,
            "switch_distance_angstrom": 3.0,
            "screening_kappa_per_angstrom": 0.0,
        },
        "fixed_born": {
            "effective_radii_angstrom": [1.5, 1.6, 1.7],
            "solute_dielectric": 1.0,
            "solvent_dielectric": 78.5,
            "radius_source_sha256": (
                "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
            ),
        },
    },
    "checkpoint_topology_crosswire": {
        "base_fixture": "four_atom_mixed_terms",
        "checkpoint_topology_sha256": (
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        ),
        "runtime_topology_sha256": (
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        ),
    },
    "checkpoint_parameter_crosswire": {
        "base_fixture": "four_atom_mixed_terms",
        "checkpoint_parameter_sha256": (
            "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
        ),
        "runtime_parameter_sha256": (
            "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
        ),
    },
    "checkpoint_solvation_crosswire": {
        "base_fixture": "three_atom_charged_constrained_angle",
        "checkpoint_solvation_sha256": (
            "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        ),
        "runtime_solvation_sha256": (
            "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        ),
    },
    "periodic_fixed_born_input": {
        "base_fixture": "three_atom_charged_constrained_angle",
        "orthorhombic_cell_angstrom": [10.0, 10.0, 10.0],
        "periodic_axes": [True, True, True],
    },
    "line_search_budget_exhaustion": {
        "base_fixture": "four_atom_mixed_terms",
        "initial_step_angstrom_squared_mol_per_kcal": 1000000.0,
        "maximum_backtracks": 1,
    },
    "constraint_projection_budget_exhaustion": {
        "atoms": [
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
            {"element": "C", "formal_charge": 0, "mass_dalton": 12.011},
        ],
        "coordinates_angstrom": [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
        ],
        "distance_constraints": [[0, 1, 1.0], [1, 2, 1.0], [0, 2, 3.0]],
        "maximum_constraint_projection_iterations": 1,
    },
}


def _fixture_spec_rows() -> list[dict[str, Any]]:
    return [
        {
            "fixture_id": fixture_id,
            "fixture_sha256": _sha256(
                {"fixture_id": fixture_id, "payload": payload}
            ),
            "payload": payload,
        }
        for fixture_id, payload in sorted(_FIXTURE_PAYLOADS.items())
    ]


def _case_input(**updates: Any) -> dict[str, Any]:
    fixture_id = updates.get("fixture")
    if not isinstance(fixture_id, str) or fixture_id not in _FIXTURE_PAYLOADS:
        raise CPUMinimizationValidationProtocolError(
            "case fixture must name one frozen fixture specification"
        )
    fixture_sha256 = _sha256(
        {"fixture_id": fixture_id, "payload": _FIXTURE_PAYLOADS[fixture_id]}
    )
    return {**_BASE_INPUT, **updates, "fixture_sha256": fixture_sha256}


def _cases() -> tuple[CPUMinimizationValidationCase, ...]:
    common = (
        "accepted_energy_monotonic",
        "final_energy_change",
        "minimum_required_energy_decrease",
        "failure_ledger_complete",
        "independent_reference_final_coordinate_max_abs_error",
        "independent_reference_final_energy_abs_error",
    )
    constrained = (
        *common,
        "final_tangent_force_max_abs",
        "constraint_max_abs_residual",
    )
    return (
        CPUMinimizationValidationCase(
            "v1_bonded_energy_decrease",
            "unconstrained_v1",
            "reference_forcefield_v1",
            _case_input(fixture="two_atom_harmonic_bond", atom_count=2),
            "pass",
            (*common, "final_force_max_abs"),
        ),
        CPUMinimizationValidationCase(
            "v1_mixed_term_energy_decrease",
            "unconstrained_v1",
            "reference_forcefield_v1",
            _case_input(fixture="four_atom_mixed_terms", atom_count=4),
            "pass",
            (*common, "final_force_max_abs"),
        ),
        CPUMinimizationValidationCase(
            "v1_checkpoint_restart_exact",
            "unconstrained_v1",
            "reference_forcefield_v1",
            _case_input(fixture="four_atom_mixed_terms", pause_after_iterations=3),
            "pass",
            (*common, "checkpoint_resume_bitwise_equal"),
        ),
        CPUMinimizationValidationCase(
            "v1_initially_converged_noop",
            "unconstrained_v1",
            "reference_forcefield_v1",
            _case_input(fixture="two_atom_bond_at_equilibrium", expected_iterations=0),
            "pass",
            (
                "accepted_energy_monotonic",
                "final_energy_change",
                "final_force_max_abs",
                "failure_ledger_complete",
                "independent_reference_final_coordinate_max_abs_error",
                "independent_reference_final_energy_abs_error",
            ),
        ),
        CPUMinimizationValidationCase(
            "v2_constrained_angle_energy_decrease",
            "constrained_v2",
            "reference_forcefield_v2",
            _case_input(fixture="three_atom_constrained_angle", constraint_count=2),
            "pass",
            constrained,
        ),
        CPUMinimizationValidationCase(
            "v2_constrained_checkpoint_restart_exact",
            "constrained_v2",
            "reference_forcefield_v2",
            _case_input(
                fixture="three_atom_constrained_angle",
                constraint_count=2,
                pause_after_iterations=3,
            ),
            "pass",
            (*constrained, "checkpoint_resume_bitwise_equal"),
        ),
        CPUMinimizationValidationCase(
            "v2_fixed_born_constrained_energy_decrease",
            "fixed_born_constrained_v2",
            "reference_forcefield_v2_with_fixed_born",
            _case_input(
                fixture="three_atom_charged_constrained_angle",
                constraint_count=2,
                fixed_effective_born_radius_source="synthetic_protocol_values",
            ),
            "pass",
            constrained,
        ),
        CPUMinimizationValidationCase(
            "v2_fixed_born_checkpoint_restart_exact",
            "fixed_born_constrained_v2",
            "reference_forcefield_v2_with_fixed_born",
            _case_input(
                fixture="three_atom_charged_constrained_angle",
                constraint_count=2,
                pause_after_iterations=3,
                fixed_effective_born_radius_source="synthetic_protocol_values",
            ),
            "pass",
            (*constrained, "checkpoint_resume_bitwise_equal"),
        ),
        CPUMinimizationValidationCase(
            "checkpoint_topology_crosswire",
            "fail_closed_identity_or_applicability",
            "reference_forcefield_v1",
            _case_input(fixture="checkpoint_topology_crosswire"),
            "fail_closed",
            expected_error_code="checkpoint_topology_fingerprint_mismatch",
        ),
        CPUMinimizationValidationCase(
            "checkpoint_parameter_crosswire",
            "fail_closed_identity_or_applicability",
            "reference_forcefield_v1",
            _case_input(fixture="checkpoint_parameter_crosswire"),
            "fail_closed",
            expected_error_code="checkpoint_parameter_fingerprint_mismatch",
        ),
        CPUMinimizationValidationCase(
            "checkpoint_solvation_crosswire",
            "fail_closed_identity_or_applicability",
            "reference_forcefield_v2_with_fixed_born",
            _case_input(fixture="checkpoint_solvation_crosswire"),
            "fail_closed",
            expected_error_code="checkpoint_solvation_parameter_fingerprint_mismatch",
        ),
        CPUMinimizationValidationCase(
            "fixed_born_periodic_cell_rejected",
            "fail_closed_identity_or_applicability",
            "reference_forcefield_v2_with_fixed_born",
            _case_input(fixture="periodic_fixed_born_input"),
            "fail_closed",
            expected_error_code="periodic_fixed_born_not_supported",
        ),
        CPUMinimizationValidationCase(
            "line_search_budget_exhausted",
            "fail_closed_identity_or_applicability",
            "reference_forcefield_v1",
            _case_input(fixture="line_search_budget_exhaustion", maximum_backtracks=1),
            "fail_closed",
            expected_error_code="line_search_exhausted",
        ),
        CPUMinimizationValidationCase(
            "constraint_projection_budget_exhausted",
            "fail_closed_identity_or_applicability",
            "reference_forcefield_v2",
            _case_input(
                fixture="constraint_projection_budget_exhaustion",
                maximum_constraint_projection_iterations=1,
            ),
            "fail_closed",
            expected_error_code="constraint_projection_exhausted",
        ),
    )


def _dependency_sources() -> dict[str, str]:
    return {
        "reference_constrained_minimization.py": _module_source_sha256(
            reference_constrained_minimization
        ),
        "reference_forcefield.py": _module_source_sha256(reference_forcefield),
        "reference_forcefield_v2.py": _module_source_sha256(reference_forcefield_v2),
        "reference_minimization.py": _module_source_sha256(reference_minimization),
        "reference_solvation.py": _module_source_sha256(reference_solvation),
    }


def _protocol_projection() -> dict[str, Any]:
    metrics = _metrics()
    cases = _cases()
    pass_count = sum(case.expected_outcome == "pass" for case in cases)
    fail_count = sum(case.expected_outcome == "fail_closed" for case in cases)
    source_hashes = _dependency_sources()
    fixture_rows = _fixture_spec_rows()
    return {
        "schema_id": CPU_MINIMIZATION_VALIDATION_PROTOCOL_SCHEMA_ID,
        "protocol_id": CPU_MINIMIZATION_VALIDATION_PROTOCOL_ID,
        "protocol_version": CPU_MINIMIZATION_VALIDATION_PROTOCOL_VERSION,
        "frozen_at_utc": CPU_MINIMIZATION_VALIDATION_PROTOCOL_FROZEN_AT_UTC,
        "status": "frozen_protocol_definition_not_executed",
        "dependencies": {
            "source_sha256": source_hashes,
            "source_set_sha256": _sha256(source_hashes),
            "exact_source_identity_required_at_execution": True,
            "independent_reference_source_sha256": None,
            "independent_reference_artifacts_bound": False,
        },
        "fixture_manifest": {
            "fixture_count": len(fixture_rows),
            "fixture_order": "lexicographic_fixture_id",
            "fixtures": fixture_rows,
            "fixture_manifest_sha256": _sha256(fixture_rows),
            "materializer_implemented": False,
        },
        "case_manifest": {
            "case_count": len(cases),
            "expected_pass_case_count": pass_count,
            "expected_fail_closed_case_count": fail_count,
            "denominator": "all_frozen_cases",
            "failure_rows_retained": True,
            "skipped_cases_allowed": False,
            "case_order_is_semantic": True,
            "cases": [case.to_dict() for case in cases],
            "case_manifest_sha256": _sha256([case.to_dict() for case in cases]),
        },
        "numerical_protocol": {
            "coordinate_dtype": "float64",
            "device": "cpu",
            "energy_unit": "kcal/mol",
            "force_unit": "kcal/mol/angstrom",
            "coordinate_unit": "angstrom",
            "cross_case_averaging_allowed": False,
            "missing_metric_is_failure": True,
            "partial_success_promotion_allowed": False,
            "metrics": [metric.to_dict() for metric in metrics],
            "metric_manifest_sha256": _sha256(
                [metric.to_dict() for metric in metrics]
            ),
        },
        "independent_reference_policy": {
            "required_before_execution": True,
            "implemented": False,
            "source_sha256": None,
            "artifact_manifest_sha256": None,
            "must_not_import": [
                "betelgeuze_engine_v2.physics.reference_minimization",
                "betelgeuze_engine_v2.physics.reference_constrained_minimization",
                "betelgeuze_engine_v2.physics.reference_forcefield",
                "betelgeuze_engine_v2.physics.reference_forcefield_v2",
                "betelgeuze_engine_v2.physics.reference_solvation",
            ],
            "same_evaluator_finite_difference_is_independent_evidence": False,
        },
        "authorization_gate": {
            "execution_authorized": False,
            "parameter_fitting_authorized": False,
            "current_blockers": list(
                CPU_MINIMIZATION_VALIDATION_SCIENTIFIC_BLOCKERS
            ),
        },
        "result_receipt": {
            "created": False,
            "all_case_rows_required": True,
            "failed_case_rows_required": True,
            "raw_observations_required": True,
            "external_authenticity_required": True,
            "independent_result_review_required": True,
        },
        "claim_policy": {
            "protocol_definition_frozen": True,
            "case_identities_frozen": True,
            "acceptance_metrics_predefined": True,
            "failure_rows_retained": True,
            "fixture_materializer_implemented": False,
            "independent_reference_implemented": False,
            "independent_scientific_review_completed": False,
            "execution_authorized": False,
            "validation_results_collected": False,
            "minimization_validated": False,
            "solvated_minimization_validated": False,
            "runtime_parameter_values_independently_reviewed": False,
            "scientific_applicability_established": False,
            "parameter_fitting_authorized": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        },
    }


def cpu_minimization_validation_protocol_document() -> dict[str, Any]:
    """Return the exact frozen protocol with its canonical identity."""

    projection = _protocol_projection()
    digest = _sha256(projection)
    return {**projection, "protocol_sha256": digest}


def cpu_minimization_validation_case_atom_count(case_id: str) -> int:
    """Return the atom count bound by one frozen case's fixture chain."""

    if not isinstance(case_id, str):
        raise CPUMinimizationValidationProtocolError("case_id must be text")
    cases = {case.case_id: case for case in _cases()}
    try:
        fixture_id = cases[case_id].canonical_input["fixture"]
    except KeyError as exc:
        raise CPUMinimizationValidationProtocolError(
            f"unknown CPU minimization validation case: {case_id}"
        ) from exc
    visited: set[str] = set()
    while True:
        if fixture_id in visited:
            raise CPUMinimizationValidationProtocolError(
                "fixture inheritance contains a cycle"
            )
        visited.add(fixture_id)
        payload = _FIXTURE_PAYLOADS[fixture_id]
        coordinates = payload.get("coordinates_angstrom")
        atoms = payload.get("atoms")
        if coordinates is not None or atoms is not None:
            if (
                not isinstance(coordinates, list)
                or not isinstance(atoms, list)
                or not coordinates
                or len(coordinates) != len(atoms)
            ):
                raise CPUMinimizationValidationProtocolError(
                    "fixture atom and coordinate coverage is invalid"
                )
            return len(coordinates)
        base_fixture = payload.get("base_fixture")
        if not isinstance(base_fixture, str) or base_fixture not in _FIXTURE_PAYLOADS:
            raise CPUMinimizationValidationProtocolError(
                "fixture does not resolve to atomic coordinates"
            )
        fixture_id = base_fixture


def cpu_minimization_validation_protocol_json_bytes() -> bytes:
    """Return canonical ASCII JSON with one trailing newline."""

    return _canonical_bytes(cpu_minimization_validation_protocol_document()) + b"\n"


def require_cpu_minimization_validation_protocol_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Require byte-semantic equality with the frozen protocol."""

    if not isinstance(value, Mapping):
        raise CPUMinimizationValidationProtocolError(
            "minimization validation protocol document must be a mapping"
        )
    candidate = dict(value)
    supplied_digest = _require_sha256(
        candidate.get("protocol_sha256", ""), name="protocol identity"
    )
    projection = {
        key: item for key, item in candidate.items() if key != "protocol_sha256"
    }
    if _sha256(projection) != supplied_digest:
        raise CPUMinimizationValidationProtocolError("protocol digest mismatch")
    frozen = cpu_minimization_validation_protocol_document()
    if supplied_digest != FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256:
        raise CPUMinimizationValidationProtocolError(
            "protocol identity does not match frozen identity"
        )
    if candidate != frozen:
        raise CPUMinimizationValidationProtocolError(
            "protocol document does not match frozen definition"
        )
    return frozen


def cpu_minimization_validation_authorization_decision(
    value: Mapping[str, Any] | None = None,
) -> CPUMinimizationValidationAuthorizationDecision:
    """Return the explicit closed decision for the exact protocol."""

    document = require_cpu_minimization_validation_protocol_document(
        cpu_minimization_validation_protocol_document() if value is None else value
    )
    return CPUMinimizationValidationAuthorizationDecision(
        protocol_sha256=document["protocol_sha256"],
        blockers=tuple(document["authorization_gate"]["current_blockers"]),
    )


def require_cpu_minimization_validation_execution_authorized(
    value: Mapping[str, Any] | None = None,
) -> None:
    """Always fail closed for the current frozen protocol."""

    decision = cpu_minimization_validation_authorization_decision(value)
    raise CPUMinimizationValidationProtocolError(
        "CPU minimization validation execution is not authorized; blockers: "
        + ", ".join(decision.blockers)
    )


def write_cpu_minimization_validation_protocol_json(
    path: str | os.PathLike[str],
) -> Path:
    """Atomically write the canonical frozen protocol with mode 0644."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = cpu_minimization_validation_protocol_json_bytes()
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o644)
        os.replace(temporary_name, destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
    return destination


__all__ = [
    "CPU_MINIMIZATION_VALIDATION_PROTOCOL_FROZEN_AT_UTC",
    "CPU_MINIMIZATION_VALIDATION_PROTOCOL_ID",
    "CPU_MINIMIZATION_VALIDATION_PROTOCOL_SCHEMA_ID",
    "CPU_MINIMIZATION_VALIDATION_PROTOCOL_VERSION",
    "CPU_MINIMIZATION_VALIDATION_SCIENTIFIC_BLOCKERS",
    "FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256",
    "CPUMinimizationValidationAuthorizationDecision",
    "CPUMinimizationValidationCase",
    "CPUMinimizationValidationMetric",
    "CPUMinimizationValidationProtocolError",
    "cpu_minimization_validation_authorization_decision",
    "cpu_minimization_validation_case_atom_count",
    "cpu_minimization_validation_protocol_document",
    "cpu_minimization_validation_protocol_json_bytes",
    "require_cpu_minimization_validation_execution_authorized",
    "require_cpu_minimization_validation_protocol_document",
    "write_cpu_minimization_validation_protocol_json",
]
