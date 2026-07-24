"""Preregistered disposition evidence for fixed-Born native endpoint failures.

This offline-only workflow binds the rejected fourteen-case OpenMM native
minimization receipt, reruns only its two fixed-Born failure aliases, and
records a frozen solver/projection probe matrix.  A successful diagnostic
receipt classifies observed sensitivity; it never changes the frozen endpoint
result or authorizes S0 admission.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Any, Mapping, Sequence

from betelgeuze_engine_v2.physics.reference_minimization_validation_materializer import (
    materialize_frozen_cpu_minimization_validation_case,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_protocol import (
    cpu_minimization_validation_protocol_document,
)

from .openmm_reference_materialization import (
    OpenMMReferenceMaterializationError,
    read_openmm_reference_materialization,
    require_openmm_reference_materialization,
)
from .openmm_reference_native_minimization import (
    FROZEN_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256,
    OPENMM_REFERENCE_NATIVE_MINIMIZATION_ENERGY_NONINCREASE_TOLERANCE_KCAL_PER_MOL,
    OpenMMReferenceNativeMinimizationError,
    _component_names,
    _constraint_diagnostics,
    _evaluation_identity,
    _require_endpoint,
    read_openmm_reference_native_minimization_receipt,
    require_openmm_reference_native_minimization_receipt,
)
from .openmm_reference_oracle import (
    OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
    OPENMM_REFERENCE_REQUIRED_PLATFORM,
    OpenMMReferenceOfflineOracleError,
    OpenMMReferenceSession,
    coordinate_f64le_sha256,
    openmm_reference_mapping_contract_document,
)
from .openmm_reference_receipts import (
    OpenMMReferenceReceiptError,
    _comparison,
    _coordinates_from_hex,
    _engine_trace_output,
    _require_comparison,
    _require_engine_or_analytic_output,
    _require_openmm_output,
)


OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_fixed_born_disposition_"
    "configuration/5.0.0"
)
OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_fixed_born_disposition_receipt/5.0.0"
)
OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_PROBE_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_fixed_born_disposition_probe/5.0.0"
)
OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_TRACE_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_fixed_born_disposition_trace/5.0.0"
)
OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_ID = (
    "engine_v2_openmm_reference_fixed_born_disposition_configuration/5.0.0"
)
OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_ID = (
    "engine_v2_openmm_reference_fixed_born_disposition_receipt/5.0.0"
)
MAX_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_BYTES = 32 * 1024 * 1024

FIXED_BORN_FAILURE_CASE_IDS = (
    "v2_fixed_born_constrained_energy_decrease",
    "v2_fixed_born_checkpoint_restart_exact",
)

_PROBE_ROWS = (
    {
        "probe_id": "baseline_protocol",
        "role": "frozen_baseline_reproduction",
        "tolerance_kcal_per_mol_angstrom": 1.0e-8,
        "maximum_iterations": 64,
        "constraint_tolerance_relative": 1.0e-10,
    },
    {
        "probe_id": "iteration_budget_128",
        "role": "iteration_budget_sensitivity",
        "tolerance_kcal_per_mol_angstrom": 1.0e-8,
        "maximum_iterations": 128,
        "constraint_tolerance_relative": 1.0e-10,
    },
    {
        "probe_id": "iteration_budget_256",
        "role": "iteration_budget_sensitivity",
        "tolerance_kcal_per_mol_angstrom": 1.0e-8,
        "maximum_iterations": 256,
        "constraint_tolerance_relative": 1.0e-10,
    },
    {
        "probe_id": "iteration_budget_512",
        "role": "iteration_budget_sensitivity",
        "tolerance_kcal_per_mol_angstrom": 1.0e-8,
        "maximum_iterations": 512,
        "constraint_tolerance_relative": 1.0e-10,
    },
    {
        "probe_id": "iteration_budget_1024",
        "role": "iteration_budget_sensitivity",
        "tolerance_kcal_per_mol_angstrom": 1.0e-8,
        "maximum_iterations": 1024,
        "constraint_tolerance_relative": 1.0e-10,
    },
    {
        "probe_id": "optimizer_tolerance_1e_10",
        "role": "optimizer_stopping_sensitivity",
        "tolerance_kcal_per_mol_angstrom": 1.0e-10,
        "maximum_iterations": 1024,
        "constraint_tolerance_relative": 1.0e-10,
    },
    {
        "probe_id": "optimizer_tolerance_1e_12",
        "role": "optimizer_stopping_sensitivity",
        "tolerance_kcal_per_mol_angstrom": 1.0e-12,
        "maximum_iterations": 1024,
        "constraint_tolerance_relative": 1.0e-10,
    },
    {
        "probe_id": "constraint_tolerance_1e_12",
        "role": "constraint_projection_sensitivity",
        "tolerance_kcal_per_mol_angstrom": 1.0e-12,
        "maximum_iterations": 1024,
        "constraint_tolerance_relative": 1.0e-12,
    },
)

OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_BLOCKERS = (
    "frozen_native_endpoint_health_remains_rejected",
    "diagnostic_sensitivity_is_not_causal_root_cause_proof",
    "optimizer_rejection_count_not_exposed_by_openmm_reporter",
    "production_execution_authorization_missing",
    "second_cpu_host_receipt_missing",
    "independent_human_result_review_missing",
)

FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V1 = (
    "67f1a6025155d8f62cd3d1aa7da2803e229a4dce7871050db6c323f531f0b8c1"
)
FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V2 = (
    "ac601f3cfedd68e24b6507778ea36c1676fb24cacf89c7c2fa73848bf3c68045"
)
FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V3 = (
    "8cbcf0f7872fdd83bdf5339e230094309000af49ca39d79fcaaaa0bf49bd6a48"
)

FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V4 = (
    "2ca9ca3db259eecd94df5a553f934740764bdca3f7d50e2d9d31d4b2695d209e"
)
FROZEN_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256 = (
    "6182cecaa21d5d191baacda1bc9cf7ae7d3cb9eb8b2ca0217757cb23af37c281"
)


class OpenMMReferenceFixedBornDispositionError(RuntimeError):
    """The diagnostic configuration, ancestry, receipt, or file is invalid."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpenMMReferenceFixedBornDispositionError(
            f"{name} must be a real number"
        )
    result = float(value)
    if not math.isfinite(result):
        raise OpenMMReferenceFixedBornDispositionError(f"{name} must be finite")
    return result


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _require_utc(value: object) -> str:
    if not isinstance(value, str):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition timestamp must be UTC text"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition timestamp is invalid"
        ) from exc
    canonical = (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() != timezone.utc.utcoffset(parsed)
        or value != canonical
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition timestamp must use canonical UTC seconds"
        )
    return value


def _module_source_sha256() -> str:
    path = Path(__file__)
    try:
        before = path.stat()
        raw = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition source cannot be read"
        ) from exc
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition source changed while being hashed"
        )
    return hashlib.sha256(raw).hexdigest()


def _configuration_projection() -> dict[str, Any]:
    native_configuration_sha256 = (
        FROZEN_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256
    )
    protocol = cpu_minimization_validation_protocol_document()
    mapping = openmm_reference_mapping_contract_document()
    protocol_cases = {
        row["case_id"]: row for row in protocol["case_manifest"]["cases"]
    }
    mapping_cases = {row["case_id"]: row for row in mapping["minimization_cases"]}
    case_rows: list[dict[str, Any]] = []
    for case_id in FIXED_BORN_FAILURE_CASE_IDS:
        protocol_case = protocol_cases[case_id]
        mapping_case = mapping_cases[case_id]
        materialized = materialize_frozen_cpu_minimization_validation_case(
            case_id, protocol
        )
        independent = materialized.independent_oracle_input
        case_rows.append(
            {
                "case_id": case_id,
                "case_input_sha256": protocol_case["input_sha256"],
                "runtime_input_sha256": materialized.runtime_input_sha256,
                "fixture_sha256": protocol_case["canonical_input"]["fixture_sha256"],
                "atom_order_sha256": mapping_case["atom_order_sha256"],
                "topology_sha256": mapping_case["topology_sha256"],
                "base_parameter_fingerprint_sha256": mapping_case[
                    "base_parameter_fingerprint_sha256"
                ],
                "v2_parameter_fingerprint_sha256": mapping_case[
                    "v2_parameter_fingerprint_sha256"
                ],
                "solvation_parameter_fingerprint_sha256": mapping_case[
                    "solvation_parameter_fingerprint_sha256"
                ],
                "constraint_count": len(independent.constraints),
                "frozen_tangent_force_max_threshold_kcal_per_mol_angstrom": (
                    independent.force_tolerance_kcal_per_mol_angstrom
                ),
                "frozen_constraint_max_abs_residual_threshold_angstrom": max(
                    (row[3] for row in independent.constraints),
                    default=0.0,
                ),
                "force_projection_max_sweeps": (
                    independent.force_projection_max_sweeps
                ),
                "force_projection_residual_threshold_kcal_per_mol_angstrom": (
                    independent.force_projection_tolerance_kcal_per_mol_angstrom
                ),
            }
        )
    return {
        "schema_id": (
            OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SCHEMA_ID
        ),
        "configuration_id": (
            OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_ID
        ),
        "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
        "required_platform": OPENMM_REFERENCE_REQUIRED_PLATFORM,
        "source_native_minimization_configuration_sha256": (
            native_configuration_sha256
        ),
        "mapping_contract_sha256": mapping["contract_sha256"],
        "minimization_protocol_sha256": protocol["protocol_sha256"],
        "expected_source_native_status": (
            "rejected_offline_native_endpoint_comparison"
        ),
        "expected_failed_case_ids": list(FIXED_BORN_FAILURE_CASE_IDS),
        "protocol_revision": {
            "revision": 5,
            "predecessor_configuration_sha256": (
                FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V4
            ),
            "legacy_configuration_chain_sha256s": [
                FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V3,
                FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V2,
                FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V1
            ],
            "change_scope": (
                "bind_openmm_mapping_1_3_0_and_native_endpoint_1_3_0_"
                "without_probe_or_threshold_change"
            ),
            "reason": (
                "energy-force protocol 1.2.0 refroze source identity while "
                "preserving fixed-Born diagnostic thresholds"
            ),
            "probe_matrix_changed": False,
            "endpoint_health_thresholds_changed": False,
        },
        "case_rows": case_rows,
        "probe_rows": [dict(row) for row in _PROBE_ROWS],
        "classification_order": [
            "baseline_failure_not_reproduced",
            "iteration_budget_sensitivity_resolves_stationarity",
            "optimizer_tolerance_sensitivity_resolves_stationarity",
            "constraint_tolerance_sensitivity_resolves_stationarity",
            "final_constraint_projection_tradeoff_observed",
            "persistent_native_stationarity_mismatch_under_preregistered_probes",
        ],
        "acceptance": {
            "no_reporter_control_exact_native_endpoint_reproduction_required": (
                True
            ),
            "instrumented_baseline_bitwise_endpoint_equality_required": False,
            "instrumented_baseline_original_health_failure_required": True,
            "all_declared_probes_required": True,
            "all_engine_openmm_same_coordinate_mappings_required": True,
            "cross_alias_physics_projection_exactly_equal_required": True,
            "original_endpoint_health_thresholds_unchanged": True,
            "diagnostic_acceptance_does_not_resolve_frozen_endpoint_failure": True,
            "missing_trace_or_metric_is_failure": True,
            "post_observation_tuning_allowed": False,
        },
        "reporter_contract": {
            "callback_count_recorded": True,
            "lbfgs_iteration_index_recorded": True,
            "restraint_stage_transition_recorded": True,
            "energy_trace_recorded": True,
            "maximum_relative_constraint_error_recorded": True,
            "objective_gradient_norm_recorded": True,
            "optimizer_rejection_count_available": False,
        },
        "claim_boundary": {
            "causal_root_cause_proven": False,
            "frozen_native_endpoint_result_replaced": False,
            "threshold_relaxation_authorized": False,
            "s0_admission_authorized": False,
            "s1_admission_authorized": False,
            "scientific_or_product_promotion_authorized": False,
            "scientifically_validated": False,
            "claim_safe": False,
        },
    }


def openmm_reference_fixed_born_disposition_configuration_document() -> dict[str, Any]:
    projection = _configuration_projection()
    observed = _sha256(projection)
    if not FROZEN_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256:
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition configuration hash is not frozen"
        )
    if (
        observed
        != FROZEN_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "frozen fixed-Born disposition configuration hash drifted"
        )
    return {**projection, "configuration_sha256": observed}


def require_openmm_reference_fixed_born_disposition_configuration_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    expected = openmm_reference_fixed_born_disposition_configuration_document()
    if not isinstance(value, Mapping) or _canonical_bytes(
        dict(value)
    ) != _canonical_bytes(expected):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition configuration differs from the frozen document"
        )
    return expected


def _coordinates_from_context(
    session: OpenMMReferenceSession,
) -> tuple[tuple[float, float, float], ...]:
    state = session._context.getState(getPositions=True)
    values = state.getPositions().value_in_unit(session._unit.nanometer)
    return tuple(
        (float(row[0]) * 10.0, float(row[1]) * 10.0, float(row[2]) * 10.0)
        for row in values
    )


def _coordinates_to_hex(
    coordinates: Sequence[Sequence[float]],
) -> list[list[str]]:
    return [[float(value).hex() for value in row] for row in coordinates]


def _coordinate_delta(
    left: Sequence[Sequence[float]],
    right: Sequence[Sequence[float]],
) -> dict[str, float]:
    values = tuple(
        abs(float(left_value) - float(right_value))
        for left_row, right_row in zip(left, right, strict=True)
        for left_value, right_value in zip(left_row, right_row, strict=True)
    )
    return {
        "max_abs_angstrom": max(values, default=0.0),
        "rms_angstrom": math.sqrt(
            sum(value * value for value in values) / len(values)
        )
        if values
        else 0.0,
    }


def _trace_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "callback_count": 0,
            "restraint_stage_count": 0,
            "restraint_stage_transition_count": 0,
            "maximum_reported_lbfgs_iteration_index": None,
            "system_energy_initial_kcal_per_mol": None,
            "system_energy_final_kcal_per_mol": None,
            "system_energy_min_kcal_per_mol": None,
            "system_energy_max_kcal_per_mol": None,
            "maximum_constraint_error_relative": None,
            "objective_gradient_rms_final_kcal_per_mol_angstrom": None,
            "callback_count_exceeds_declared_maximum_iterations": False,
            "optimizer_rejection_count_available": False,
        }
    energies = [
        _finite(row["system_energy_kcal_per_mol"], name="trace system energy")
        for row in rows
    ]
    errors = [
        _finite(
            row["max_constraint_error_relative"],
            name="trace constraint error",
        )
        for row in rows
    ]
    stages = [int(row["restraint_stage_index"]) for row in rows]
    iterations = [int(row["lbfgs_iteration_index"]) for row in rows]
    maximum_iterations = int(rows[0]["declared_maximum_iterations"])
    return {
        "callback_count": len(rows),
        "restraint_stage_count": max(stages) + 1,
        "restraint_stage_transition_count": max(stages),
        "maximum_reported_lbfgs_iteration_index": max(iterations),
        "system_energy_initial_kcal_per_mol": energies[0],
        "system_energy_final_kcal_per_mol": energies[-1],
        "system_energy_min_kcal_per_mol": min(energies),
        "system_energy_max_kcal_per_mol": max(energies),
        "maximum_constraint_error_relative": max(errors),
        "objective_gradient_rms_final_kcal_per_mol_angstrom": _finite(
            rows[-1]["objective_gradient_rms_kcal_per_mol_angstrom"],
            name="trace final gradient RMS",
        ),
        "callback_count_exceeds_declared_maximum_iterations": (
            len(rows) > maximum_iterations
        ),
        "optimizer_rejection_count_available": False,
    }


def _run_probe(
    session: OpenMMReferenceSession,
    probe: Mapping[str, Any],
) -> dict[str, Any]:
    tolerance = _finite(
        probe["tolerance_kcal_per_mol_angstrom"],
        name="probe optimizer tolerance",
    )
    maximum_iterations = int(probe["maximum_iterations"])
    constraint_tolerance = _finite(
        probe["constraint_tolerance_relative"],
        name="probe constraint tolerance",
    )
    if (
        tolerance <= 0.0
        or maximum_iterations < 1
        or maximum_iterations > 1_000_000
        or constraint_tolerance <= 0.0
        or constraint_tolerance > 1.0
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition probe bounds are invalid"
        )

    openmm = session._openmm
    rows: list[dict[str, Any]] = []

    class Reporter(openmm.MinimizationReporter):
        def __init__(self) -> None:
            super().__init__()
            self._previous_iteration: int | None = None
            self._previous_strength: float | None = None
            self._stage = 0

        def report(
            self,
            iteration: int,
            coordinates_nm: Sequence[float],
            gradient_kj_per_mol_nm: Sequence[float],
            arguments: Mapping[str, float],
        ) -> bool:
            current_iteration = int(iteration)
            strength = _finite(
                arguments["restraint strength"],
                name="reporter restraint strength",
            )
            if self._previous_iteration is not None and (
                current_iteration <= self._previous_iteration
                or strength != self._previous_strength
            ):
                self._stage += 1
            coordinate_values = tuple(
                _finite(value, name="reporter coordinate") * 10.0
                for value in coordinates_nm
            )
            if len(coordinate_values) % 3:
                raise OpenMMReferenceFixedBornDispositionError(
                    "reporter coordinate shape is invalid"
                )
            coordinate_rows = tuple(
                coordinate_values[index : index + 3]
                for index in range(0, len(coordinate_values), 3)
            )
            gradients = tuple(
                _finite(value, name="reporter gradient") / 41.84
                for value in gradient_kj_per_mol_nm
            )
            gradient_rms = (
                math.sqrt(sum(value * value for value in gradients) / len(gradients))
                if gradients
                else 0.0
            )
            rows.append(
                {
                    "callback_index": len(rows),
                    "restraint_stage_index": self._stage,
                    "lbfgs_iteration_index": current_iteration,
                    "declared_maximum_iterations": maximum_iterations,
                    "coordinate_f64le_sha256": coordinate_f64le_sha256(
                        coordinate_rows
                    ),
                    "system_energy_kcal_per_mol": _finite(
                        arguments["system energy"],
                        name="reporter system energy",
                    )
                    / 4.184,
                    "restraint_energy_kcal_per_mol": _finite(
                        arguments["restraint energy"],
                        name="reporter restraint energy",
                    )
                    / 4.184,
                    "restraint_strength_kcal_per_mol_angstrom2": (
                        strength / 418.4
                    ),
                    "max_constraint_error_relative": _finite(
                        arguments["max constraint error"],
                        name="reporter constraint error",
                    ),
                    "objective_gradient_max_abs_kcal_per_mol_angstrom": max(
                        (abs(value) for value in gradients),
                        default=0.0,
                    ),
                    "objective_gradient_rms_kcal_per_mol_angstrom": gradient_rms,
                }
            )
            self._previous_iteration = current_iteration
            self._previous_strength = strength
            return False

    session._integrator.setConstraintTolerance(constraint_tolerance)
    initial = session.evaluate()
    reporter = Reporter()
    openmm.LocalEnergyMinimizer.minimize(
        session._context,
        tolerance * 41.84,
        maximum_iterations,
        reporter,
    )
    pre_projection_coordinates = _coordinates_from_context(session)
    pre_projection_evaluation = session.evaluate(pre_projection_coordinates)
    session._context.applyConstraints(constraint_tolerance)
    post_projection_coordinates = _coordinates_from_context(session)
    post_projection_evaluation = session.evaluate(post_projection_coordinates)
    trace_projection = {
        "schema_id": OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_TRACE_SCHEMA_ID,
        "rows": rows,
        "summary": _trace_summary(rows),
    }
    trace = {
        **trace_projection,
        "trace_sha256": _sha256(trace_projection),
    }
    projection = {
        "schema_id": OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_PROBE_SCHEMA_ID,
        "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
        "platform": OPENMM_REFERENCE_REQUIRED_PLATFORM,
        "algorithm": "OpenMM LocalEnergyMinimizer L-BFGS",
        "probe_id": probe["probe_id"],
        "role": probe["role"],
        "tolerance_kcal_per_mol_angstrom": tolerance,
        "maximum_iterations": maximum_iterations,
        "constraint_tolerance_relative": constraint_tolerance,
        "initial_evaluation": initial.to_dict(),
        "minimizer_reporter_trace": trace,
        "pre_projection_coordinates_angstrom_hex": _coordinates_to_hex(
            pre_projection_coordinates
        ),
        "pre_projection_evaluation": pre_projection_evaluation.to_dict(),
        "explicit_final_constraint_projection_applied": True,
        "post_projection_coordinates_angstrom_hex": _coordinates_to_hex(
            post_projection_coordinates
        ),
        "post_projection_evaluation": post_projection_evaluation.to_dict(),
        "final_projection_coordinate_delta": _coordinate_delta(
            pre_projection_coordinates,
            post_projection_coordinates,
        ),
        "optimizer_rejection_count_available": False,
        "minimizer_returned_normally": True,
        "frozen_endpoint_result_replaced": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return {**projection, "probe_sha256": _sha256(projection)}


def _require_probe_endpoint(
    value: object,
    *,
    probe: Mapping[str, Any],
    mapping_case: Mapping[str, Any],
    materialized: Any,
) -> tuple[
    dict[str, Any],
    tuple[tuple[float, float, float], ...],
    tuple[tuple[float, float, float], ...],
]:
    if not isinstance(value, Mapping):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition probe must be a mapping"
        )
    endpoint = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    expected_fields = {
        "schema_id",
        "oracle_id",
        "platform",
        "algorithm",
        "probe_id",
        "role",
        "tolerance_kcal_per_mol_angstrom",
        "maximum_iterations",
        "constraint_tolerance_relative",
        "initial_evaluation",
        "minimizer_reporter_trace",
        "pre_projection_coordinates_angstrom_hex",
        "pre_projection_evaluation",
        "explicit_final_constraint_projection_applied",
        "post_projection_coordinates_angstrom_hex",
        "post_projection_evaluation",
        "final_projection_coordinate_delta",
        "optimizer_rejection_count_available",
        "minimizer_returned_normally",
        "frozen_endpoint_result_replaced",
        "scientifically_validated",
        "claim_safe",
        "probe_sha256",
    }
    if set(endpoint) != expected_fields:
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition probe fields are invalid"
        )
    digest = _require_sha256(endpoint["probe_sha256"], name="disposition probe")
    projection = {
        key: item for key, item in endpoint.items() if key != "probe_sha256"
    }
    if digest != _sha256(projection):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition probe digest mismatch"
        )
    if (
        endpoint["schema_id"]
        != OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_PROBE_SCHEMA_ID
        or endpoint["oracle_id"] != OPENMM_REFERENCE_OFFLINE_ORACLE_ID
        or endpoint["platform"] != OPENMM_REFERENCE_REQUIRED_PLATFORM
        or endpoint["algorithm"] != "OpenMM LocalEnergyMinimizer L-BFGS"
        or endpoint["probe_id"] != probe["probe_id"]
        or endpoint["role"] != probe["role"]
        or endpoint["tolerance_kcal_per_mol_angstrom"]
        != probe["tolerance_kcal_per_mol_angstrom"]
        or endpoint["maximum_iterations"] != probe["maximum_iterations"]
        or endpoint["constraint_tolerance_relative"]
        != probe["constraint_tolerance_relative"]
        or endpoint["explicit_final_constraint_projection_applied"] is not True
        or endpoint["optimizer_rejection_count_available"] is not False
        or endpoint["minimizer_returned_normally"] is not True
        or endpoint["frozen_endpoint_result_replaced"] is not False
        or endpoint["scientifically_validated"] is not False
        or endpoint["claim_safe"] is not False
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition probe contract drifted"
        )

    trace = endpoint["minimizer_reporter_trace"]
    if not isinstance(trace, Mapping) or set(trace) != {
        "schema_id",
        "rows",
        "summary",
        "trace_sha256",
    }:
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition reporter trace fields are invalid"
        )
    trace_projection = {
        key: item for key, item in trace.items() if key != "trace_sha256"
    }
    if (
        trace["schema_id"]
        != OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_TRACE_SCHEMA_ID
        or _require_sha256(trace["trace_sha256"], name="reporter trace")
        != _sha256(trace_projection)
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition reporter trace identity drifted"
        )
    rows = trace["rows"]
    if not isinstance(rows, list) or len(rows) > 100_000:
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition reporter rows are invalid"
        )
    expected_row_fields = {
        "callback_index",
        "restraint_stage_index",
        "lbfgs_iteration_index",
        "declared_maximum_iterations",
        "coordinate_f64le_sha256",
        "system_energy_kcal_per_mol",
        "restraint_energy_kcal_per_mol",
        "restraint_strength_kcal_per_mol_angstrom2",
        "max_constraint_error_relative",
        "objective_gradient_max_abs_kcal_per_mol_angstrom",
        "objective_gradient_rms_kcal_per_mol_angstrom",
    }
    previous_iteration: int | None = None
    previous_strength: float | None = None
    expected_stage = 0
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != expected_row_fields:
            raise OpenMMReferenceFixedBornDispositionError(
                "fixed-Born disposition reporter row fields are invalid"
            )
        if (
            isinstance(row["callback_index"], bool)
            or row["callback_index"] != index
            or isinstance(row["restraint_stage_index"], bool)
            or not isinstance(row["restraint_stage_index"], int)
            or isinstance(row["lbfgs_iteration_index"], bool)
            or not isinstance(row["lbfgs_iteration_index"], int)
            or row["lbfgs_iteration_index"] < 0
            or row["declared_maximum_iterations"] != probe["maximum_iterations"]
        ):
            raise OpenMMReferenceFixedBornDispositionError(
                "fixed-Born disposition reporter sequence is invalid"
            )
        strength = _finite(
            row["restraint_strength_kcal_per_mol_angstrom2"],
            name="reporter restraint strength",
        )
        iteration = row["lbfgs_iteration_index"]
        if previous_iteration is not None and (
            iteration <= previous_iteration or strength != previous_strength
        ):
            expected_stage += 1
        if row["restraint_stage_index"] != expected_stage:
            raise OpenMMReferenceFixedBornDispositionError(
                "fixed-Born disposition reporter stage sequence drifted"
            )
        _require_sha256(
            row["coordinate_f64le_sha256"],
            name="reporter coordinate",
        )
        for name in (
            "system_energy_kcal_per_mol",
            "restraint_energy_kcal_per_mol",
            "max_constraint_error_relative",
            "objective_gradient_max_abs_kcal_per_mol_angstrom",
            "objective_gradient_rms_kcal_per_mol_angstrom",
        ):
            observed = _finite(row[name], name=f"reporter {name}")
            if name != "system_energy_kcal_per_mol" and observed < 0.0:
                raise OpenMMReferenceFixedBornDispositionError(
                    "fixed-Born disposition reporter nonnegative metric is invalid"
                )
        previous_iteration = iteration
        previous_strength = strength
    if trace["summary"] != _trace_summary(rows):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition reporter summary drifted"
        )

    pre_coordinates = _coordinates_from_hex(
        endpoint["pre_projection_coordinates_angstrom_hex"]
    )
    post_coordinates = _coordinates_from_hex(
        endpoint["post_projection_coordinates_angstrom_hex"]
    )
    if (
        len(pre_coordinates) != mapping_case["atom_count"]
        or len(post_coordinates) != mapping_case["atom_count"]
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition endpoint atom count drifted"
        )
    initial_coordinates = tuple(
        tuple(float(value) for value in row)
        for row in materialized.system.coordinates[0].detach().cpu().tolist()
    )
    component_names = _component_names(mapping_case)
    for evaluation, coordinates in (
        (endpoint["initial_evaluation"], initial_coordinates),
        (endpoint["pre_projection_evaluation"], pre_coordinates),
        (endpoint["post_projection_evaluation"], post_coordinates),
    ):
        _require_openmm_output(
            evaluation,
            component_names=component_names,
            atom_count=mapping_case["atom_count"],
            expected_identity=_evaluation_identity(
                mapping_case,
                coordinate_sha256=coordinate_f64le_sha256(coordinates),
            ),
        )
    if endpoint["final_projection_coordinate_delta"] != _coordinate_delta(
        pre_coordinates,
        post_coordinates,
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition final projection delta drifted"
        )
    return endpoint, pre_coordinates, post_coordinates


def _phase_projection(
    *,
    materialized: Any,
    mapping_case: Mapping[str, Any],
    configuration_case: Mapping[str, Any],
    coordinates: Sequence[Sequence[float]],
    openmm_evaluation: Mapping[str, Any],
    initial_energy: float,
) -> dict[str, Any]:
    component_names = _component_names(mapping_case)
    engine_evaluation = _require_engine_or_analytic_output(
        _engine_trace_output(materialized, coordinates),
        component_names=component_names,
        atom_count=mapping_case["atom_count"],
    )
    comparison, _, _ = _comparison(engine_evaluation, openmm_evaluation)
    _require_comparison(
        comparison,
        left=engine_evaluation,
        right=openmm_evaluation,
    )
    diagnostics = _constraint_diagnostics(
        materialized,
        coordinates,
        engine_evaluation["forces"]["values"],
    )
    energy = _finite(
        openmm_evaluation["total_energy"]["value"],
        name="probe phase energy",
    )
    energy_nonincreasing = (
        energy
        <= initial_energy
        + OPENMM_REFERENCE_NATIVE_MINIMIZATION_ENERGY_NONINCREASE_TOLERANCE_KCAL_PER_MOL
    )
    tangent_passed = (
        diagnostics["tangent_force_max_kcal_per_mol_angstrom"]
        <= configuration_case[
            "frozen_tangent_force_max_threshold_kcal_per_mol_angstrom"
        ]
    )
    constraint_passed = (
        diagnostics["constraint_max_abs_residual_angstrom"]
        <= configuration_case[
            "frozen_constraint_max_abs_residual_threshold_angstrom"
        ]
    )
    original_endpoint_health_passed = bool(
        comparison["passed_predefined_thresholds"]
        and energy_nonincreasing
        and tangent_passed
        and constraint_passed
        and diagnostics["force_projection_converged"]
    )
    return {
        "coordinates_f64le_sha256": coordinate_f64le_sha256(coordinates),
        "openmm_evaluation": dict(openmm_evaluation),
        "engine_evaluation": engine_evaluation,
        "engine_openmm_same_coordinate_comparison": comparison,
        "constraint_diagnostics": diagnostics,
        "energy_change_from_initial_kcal_per_mol": energy - initial_energy,
        "energy_nonincreasing": energy_nonincreasing,
        "tangent_force_threshold_passed": tangent_passed,
        "constraint_residual_threshold_passed": constraint_passed,
        "original_endpoint_health_passed": original_endpoint_health_passed,
    }


def _probe_case_projection(
    *,
    raw_probe: Mapping[str, Any],
    probe_configuration: Mapping[str, Any],
    configuration_case: Mapping[str, Any],
    mapping_case: Mapping[str, Any],
    materialized: Any,
) -> dict[str, Any]:
    endpoint, pre_coordinates, post_coordinates = _require_probe_endpoint(
        raw_probe,
        probe=probe_configuration,
        mapping_case=mapping_case,
        materialized=materialized,
    )
    initial_energy = _finite(
        endpoint["initial_evaluation"]["total_energy"]["value"],
        name="probe initial energy",
    )
    pre = _phase_projection(
        materialized=materialized,
        mapping_case=mapping_case,
        configuration_case=configuration_case,
        coordinates=pre_coordinates,
        openmm_evaluation=endpoint["pre_projection_evaluation"],
        initial_energy=initial_energy,
    )
    post = _phase_projection(
        materialized=materialized,
        mapping_case=mapping_case,
        configuration_case=configuration_case,
        coordinates=post_coordinates,
        openmm_evaluation=endpoint["post_projection_evaluation"],
        initial_energy=initial_energy,
    )
    return {
        "probe_id": probe_configuration["probe_id"],
        "role": probe_configuration["role"],
        "probe_endpoint": endpoint,
        "pre_projection": pre,
        "post_projection": post,
        "projection_effect": {
            "coordinate_delta": endpoint["final_projection_coordinate_delta"],
            "energy_delta_kcal_per_mol": (
                post["energy_change_from_initial_kcal_per_mol"]
                - pre["energy_change_from_initial_kcal_per_mol"]
            ),
            "tangent_force_max_delta_kcal_per_mol_angstrom": (
                post["constraint_diagnostics"][
                    "tangent_force_max_kcal_per_mol_angstrom"
                ]
                - pre["constraint_diagnostics"][
                    "tangent_force_max_kcal_per_mol_angstrom"
                ]
            ),
            "constraint_residual_delta_angstrom": (
                post["constraint_diagnostics"][
                    "constraint_max_abs_residual_angstrom"
                ]
                - pre["constraint_diagnostics"][
                    "constraint_max_abs_residual_angstrom"
                ]
            ),
        },
    }


def _classification(
    probes: Sequence[Mapping[str, Any]],
    *,
    baseline_control_exactly_reproduced: bool,
) -> dict[str, Any]:
    by_id = {row["probe_id"]: row for row in probes}
    baseline = by_id["baseline_protocol"]
    if (
        not baseline_control_exactly_reproduced
        or baseline["post_projection"]["original_endpoint_health_passed"]
    ):
        classification = "baseline_failure_not_reproduced"
        resolving_probe_id = None
    else:
        resolving_probe_id = next(
            (
                row["probe_id"]
                for row in probes
                if row["role"] == "iteration_budget_sensitivity"
                and row["post_projection"]["original_endpoint_health_passed"]
            ),
            None,
        )
        if resolving_probe_id is not None:
            classification = (
                "iteration_budget_sensitivity_resolves_stationarity"
            )
        else:
            resolving_probe_id = next(
                (
                    row["probe_id"]
                    for row in probes
                    if row["role"] == "optimizer_stopping_sensitivity"
                    and row["post_projection"]["original_endpoint_health_passed"]
                ),
                None,
            )
            if resolving_probe_id is not None:
                classification = (
                    "optimizer_tolerance_sensitivity_resolves_stationarity"
                )
            else:
                resolving_probe_id = next(
                    (
                        row["probe_id"]
                        for row in probes
                        if row["role"] == "constraint_projection_sensitivity"
                        and row["post_projection"][
                            "original_endpoint_health_passed"
                        ]
                    ),
                    None,
                )
                if resolving_probe_id is not None:
                    classification = (
                        "constraint_tolerance_sensitivity_resolves_stationarity"
                    )
                else:
                    tradeoff = next(
                        (
                            row
                            for row in probes
                            if row["pre_projection"][
                                "tangent_force_threshold_passed"
                            ]
                            and not row["pre_projection"][
                                "constraint_residual_threshold_passed"
                            ]
                            and row["post_projection"][
                                "constraint_residual_threshold_passed"
                            ]
                            and not row["post_projection"][
                                "tangent_force_threshold_passed"
                            ]
                        ),
                        None,
                    )
                    if tradeoff is not None:
                        classification = (
                            "final_constraint_projection_tradeoff_observed"
                        )
                        resolving_probe_id = tradeoff["probe_id"]
                    else:
                        classification = (
                            "persistent_native_stationarity_mismatch_"
                            "under_preregistered_probes"
                        )
                        resolving_probe_id = None
    return {
        "classification": classification,
        "resolving_probe_id": resolving_probe_id,
        "baseline_failure_exactly_reproduced": bool(
            baseline_control_exactly_reproduced
            and not baseline["post_projection"][
                "original_endpoint_health_passed"
            ]
        ),
        "causal_root_cause_proven": False,
        "frozen_endpoint_health_failure_resolved": False,
        "threshold_relaxation_used": False,
    }


def _case_physics_projection(case: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "fixture_sha256": case["fixture_sha256"],
        "atom_order_sha256": case["atom_order_sha256"],
        "topology_sha256": case["topology_sha256"],
        "base_parameter_fingerprint_sha256": case[
            "base_parameter_fingerprint_sha256"
        ],
        "v2_parameter_fingerprint_sha256": case[
            "v2_parameter_fingerprint_sha256"
        ],
        "solvation_parameter_fingerprint_sha256": case[
            "solvation_parameter_fingerprint_sha256"
        ],
        "no_reporter_baseline_control_endpoint": case[
            "no_reporter_baseline_control_endpoint"
        ],
        "probes": case["probes"],
        "disposition": case["disposition"],
    }


def _case_projection(
    *,
    configuration_case: Mapping[str, Any],
    mapping_case: Mapping[str, Any],
    source_native_case: Mapping[str, Any],
    raw_baseline_control: Mapping[str, Any],
    raw_probes: Sequence[Mapping[str, Any]],
    probe_configurations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    case_id = configuration_case["case_id"]
    materialized = materialize_frozen_cpu_minimization_validation_case(case_id)
    if (
        source_native_case["case_id"] != case_id
        or source_native_case["native_endpoint_executed"] is not True
        or source_native_case["case_passed_predefined_endpoint_health"] is not False
        or source_native_case["native_endpoint_diagnostics"][
            "tangent_force_threshold_passed"
        ]
        is not False
        or source_native_case["native_endpoint_diagnostics"][
            "constraint_residual_threshold_passed"
        ]
        is not True
        or len(raw_probes) != len(probe_configurations)
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born source failure or probe coverage drifted"
        )
    baseline_probe_configuration = probe_configurations[0]
    baseline_control, _ = _require_endpoint(
        raw_baseline_control,
        mapping_case=mapping_case,
        materialized=materialized,
        tolerance=baseline_probe_configuration[
            "tolerance_kcal_per_mol_angstrom"
        ],
        maximum_iterations=baseline_probe_configuration["maximum_iterations"],
        constraint_tolerance_relative=baseline_probe_configuration[
            "constraint_tolerance_relative"
        ],
    )
    probes: list[dict[str, Any]] = []
    for raw_probe, probe_configuration in zip(
        raw_probes, probe_configurations, strict=True
    ):
        probes.append(
            _probe_case_projection(
                raw_probe=raw_probe,
                probe_configuration=probe_configuration,
                configuration_case=configuration_case,
                mapping_case=mapping_case,
                materialized=materialized,
            )
        )
    baseline = probes[0]["probe_endpoint"]
    source_endpoint = source_native_case["native_endpoint"]
    baseline_control_exactly_reproduced = baseline_control == source_endpoint
    instrumented_baseline_bitwise_equal = bool(
        baseline["tolerance_kcal_per_mol_angstrom"]
        == source_endpoint["tolerance_kcal_per_mol_angstrom"]
        and baseline["maximum_iterations"]
        == source_endpoint["maximum_iterations"]
        and baseline["constraint_tolerance_relative"]
        == source_endpoint["constraint_tolerance_relative"]
        and baseline["initial_evaluation"] == source_endpoint["initial_evaluation"]
        and baseline["post_projection_coordinates_angstrom_hex"]
        == source_endpoint["final_coordinates_angstrom_hex"]
        and baseline["post_projection_evaluation"]
        == source_endpoint["final_evaluation"]
    )
    disposition = _classification(
        probes,
        baseline_control_exactly_reproduced=(
            baseline_control_exactly_reproduced
        ),
    )
    provisional = {
        "case_id": case_id,
        "case_input_sha256": configuration_case["case_input_sha256"],
        "runtime_input_sha256": configuration_case["runtime_input_sha256"],
        "fixture_sha256": configuration_case["fixture_sha256"],
        "atom_order_sha256": configuration_case["atom_order_sha256"],
        "topology_sha256": configuration_case["topology_sha256"],
        "base_parameter_fingerprint_sha256": configuration_case[
            "base_parameter_fingerprint_sha256"
        ],
        "v2_parameter_fingerprint_sha256": configuration_case[
            "v2_parameter_fingerprint_sha256"
        ],
        "solvation_parameter_fingerprint_sha256": configuration_case[
            "solvation_parameter_fingerprint_sha256"
        ],
        "source_native_probe_sha256": source_endpoint["endpoint_sha256"],
        "source_native_tangent_force_max_kcal_per_mol_angstrom": (
            source_native_case["native_endpoint_diagnostics"][
                "tangent_force_max_kcal_per_mol_angstrom"
            ]
        ),
        "source_native_constraint_max_abs_residual_angstrom": (
            source_native_case["native_endpoint_diagnostics"][
                "constraint_max_abs_residual_angstrom"
            ]
        ),
        "no_reporter_baseline_control_endpoint": baseline_control,
        "no_reporter_baseline_source_native_endpoint_exactly_reproduced": (
            baseline_control_exactly_reproduced
        ),
        "instrumented_baseline_source_native_endpoint_bitwise_equal": (
            instrumented_baseline_bitwise_equal
        ),
        "probes": probes,
        "disposition": disposition,
    }
    return {
        **provisional,
        "case_physics_projection_sha256": _sha256(
            _case_physics_projection(provisional)
        ),
    }


def _summary(case_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    physics_hashes = [row["case_physics_projection_sha256"] for row in case_rows]
    classifications = [
        row["disposition"]["classification"] for row in case_rows
    ]
    all_mapping_passed = all(
        probe[phase]["engine_openmm_same_coordinate_comparison"][
            "passed_predefined_thresholds"
        ]
        for row in case_rows
        for probe in row["probes"]
        for phase in ("pre_projection", "post_projection")
    )
    all_traces_present = all(
        probe["probe_endpoint"]["minimizer_reporter_trace"]["summary"][
            "callback_count"
        ]
        > 0
        for row in case_rows
        for probe in row["probes"]
    )
    return {
        "case_count": len(case_rows),
        "probe_count_per_case": len(_PROBE_ROWS),
        "total_probe_count": sum(len(row["probes"]) for row in case_rows),
        "exact_failed_case_scope_retained": tuple(
            row["case_id"] for row in case_rows
        )
        == FIXED_BORN_FAILURE_CASE_IDS,
        "no_reporter_baseline_exact_native_endpoint_reproduction_case_count": sum(
            row[
                "no_reporter_baseline_source_native_endpoint_exactly_reproduced"
            ]
            for row in case_rows
        ),
        "instrumented_baseline_bitwise_equal_case_count": sum(
            row["instrumented_baseline_source_native_endpoint_bitwise_equal"]
            for row in case_rows
        ),
        "all_engine_openmm_same_coordinate_mappings_passed": all_mapping_passed,
        "all_reporter_traces_present": all_traces_present,
        "cross_alias_physics_projection_exactly_equal": len(set(physics_hashes))
        == 1,
        "cross_alias_classification_exactly_equal": len(set(classifications)) == 1,
        "classification": classifications[0] if len(set(classifications)) == 1 else None,
        "resolving_probe_id": (
            case_rows[0]["disposition"]["resolving_probe_id"]
            if len(
                {
                    row["disposition"]["resolving_probe_id"]
                    for row in case_rows
                }
            )
            == 1
            else None
        ),
        "failure_disposition_complete": bool(
            len(case_rows) == 2
            and all(
                row["disposition"]["baseline_failure_exactly_reproduced"]
                for row in case_rows
            )
            and all_mapping_passed
            and all_traces_present
            and len(set(physics_hashes)) == 1
            and len(set(classifications)) == 1
            and classifications[0] != "baseline_failure_not_reproduced"
        ),
        "frozen_native_endpoint_health_failure_resolved": False,
        "causal_root_cause_proven": False,
    }


def _source_inputs(
    source_materialization: Mapping[str, Any],
    source_native_receipt: Mapping[str, Any],
    *,
    expected_source_materialization_sha256: str,
    expected_source_native_receipt_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = require_openmm_reference_materialization(source_materialization)
    materialization_sha256 = _require_sha256(
        expected_source_materialization_sha256,
        name="expected source materialization",
    )
    if source["materialization_sha256"] != materialization_sha256:
        raise OpenMMReferenceFixedBornDispositionError(
            "source materialization differs from caller expectation"
        )
    native = require_openmm_reference_native_minimization_receipt(
        source_native_receipt,
        source_materialization=source,
        expected_source_materialization_sha256=materialization_sha256,
    )
    native_sha256 = _require_sha256(
        expected_source_native_receipt_sha256,
        name="expected source native receipt",
    )
    failed_case_ids = tuple(
        row["case_id"]
        for row in native["cases"]
        if row["native_endpoint_executed"]
        and not row["case_passed_predefined_endpoint_health"]
    )
    if (
        native["receipt_sha256"] != native_sha256
        or native["status"]
        != "rejected_offline_native_endpoint_comparison"
        or failed_case_ids != FIXED_BORN_FAILURE_CASE_IDS
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "source native receipt does not retain the exact fixed-Born failures"
        )
    return source, native


def build_openmm_reference_fixed_born_disposition_receipt(
    source_materialization: Mapping[str, Any],
    source_native_receipt: Mapping[str, Any],
    *,
    expected_source_materialization_sha256: str,
    expected_source_native_receipt_sha256: str,
    observed_at_utc: str | None = None,
) -> dict[str, Any]:
    """Execute the frozen fixed-Born failure-disposition probe matrix."""

    source, native = _source_inputs(
        source_materialization,
        source_native_receipt,
        expected_source_materialization_sha256=(
            expected_source_materialization_sha256
        ),
        expected_source_native_receipt_sha256=(
            expected_source_native_receipt_sha256
        ),
    )
    timestamp = _require_utc(_utc_now() if observed_at_utc is None else observed_at_utc)
    configuration = (
        openmm_reference_fixed_born_disposition_configuration_document()
    )
    mapping = openmm_reference_mapping_contract_document()
    mapping_cases = {row["case_id"]: row for row in mapping["minimization_cases"]}
    native_cases = {row["case_id"]: row for row in native["cases"]}
    case_rows: list[dict[str, Any]] = []
    for configuration_case in configuration["case_rows"]:
        case_id = configuration_case["case_id"]
        materialized = materialize_frozen_cpu_minimization_validation_case(case_id)
        baseline_probe_configuration = configuration["probe_rows"][0]
        with OpenMMReferenceSession(
            materialized.system,
            materialized.base_parameters,
            v2_parameters=materialized.v2_parameters,
            solvation_parameters=materialized.solvation_parameters,
        ) as session:
            raw_baseline_control = session.native_minimize_endpoint(
                tolerance_kcal_per_mol_angstrom=baseline_probe_configuration[
                    "tolerance_kcal_per_mol_angstrom"
                ],
                maximum_iterations=baseline_probe_configuration[
                    "maximum_iterations"
                ],
                constraint_tolerance_relative=baseline_probe_configuration[
                    "constraint_tolerance_relative"
                ],
            )
        raw_probes: list[dict[str, Any]] = []
        for probe_configuration in configuration["probe_rows"]:
            with OpenMMReferenceSession(
                materialized.system,
                materialized.base_parameters,
                v2_parameters=materialized.v2_parameters,
                solvation_parameters=materialized.solvation_parameters,
            ) as session:
                raw_probes.append(_run_probe(session, probe_configuration))
        case_rows.append(
            _case_projection(
                configuration_case=configuration_case,
                mapping_case=mapping_cases[case_id],
                source_native_case=native_cases[case_id],
                raw_baseline_control=raw_baseline_control,
                raw_probes=raw_probes,
                probe_configurations=configuration["probe_rows"],
            )
        )
    summary = _summary(case_rows)
    status = (
        "accepted_failure_disposition_evidence"
        if summary["failure_disposition_complete"]
        else "rejected_failure_disposition_evidence"
    )
    projection = {
        "schema_id": OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_SCHEMA_ID,
        "receipt_id": OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_ID,
        "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
        "observed_at_utc": timestamp,
        "configuration_sha256": configuration["configuration_sha256"],
        "mapping_contract_sha256": mapping["contract_sha256"],
        "minimization_protocol_sha256": configuration[
            "minimization_protocol_sha256"
        ],
        "source_materialization_sha256": source["materialization_sha256"],
        "source_materialization_transport_sha256": _sha256(source),
        "source_native_receipt_sha256": native["receipt_sha256"],
        "source_native_receipt_transport_sha256": _sha256(native),
        "runtime_identity_sha256": native["runtime_identity_sha256"],
        "implementation_source_sha256": _module_source_sha256(),
        "cases": case_rows,
        "summary": summary,
        "status": status,
        "scientific_blockers": list(
            OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_BLOCKERS
        ),
        "offline_failure_disposition_observation": True,
        "all_preregistered_probes_executed": True,
        "frozen_native_endpoint_result_replaced": False,
        "frozen_native_endpoint_health_failure_resolved": False,
        "threshold_relaxation_authorized": False,
        "causal_root_cause_proven": False,
        "optimizer_rejection_count_available": False,
        "production_protocol_execution": False,
        "signed_result_receipt": False,
        "independent_review_complete": False,
        "two_host_reproduction_complete": False,
        "s0_accepted": False,
        "s1_admission_authorized": False,
        "scientific_or_product_promotion_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return {**projection, "receipt_sha256": _sha256(projection)}


def require_openmm_reference_fixed_born_disposition_receipt(
    value: Mapping[str, Any],
    *,
    source_materialization: Mapping[str, Any],
    source_native_receipt: Mapping[str, Any],
    expected_source_materialization_sha256: str,
    expected_source_native_receipt_sha256: str,
    reexecute: bool = False,
) -> dict[str, Any]:
    """Verify one disposition receipt and optionally reexecute every probe."""

    if not isinstance(value, Mapping):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition receipt must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    expected_fields = {
        "schema_id",
        "receipt_id",
        "oracle_id",
        "observed_at_utc",
        "configuration_sha256",
        "mapping_contract_sha256",
        "minimization_protocol_sha256",
        "source_materialization_sha256",
        "source_materialization_transport_sha256",
        "source_native_receipt_sha256",
        "source_native_receipt_transport_sha256",
        "runtime_identity_sha256",
        "implementation_source_sha256",
        "cases",
        "summary",
        "status",
        "scientific_blockers",
        "offline_failure_disposition_observation",
        "all_preregistered_probes_executed",
        "frozen_native_endpoint_result_replaced",
        "frozen_native_endpoint_health_failure_resolved",
        "threshold_relaxation_authorized",
        "causal_root_cause_proven",
        "optimizer_rejection_count_available",
        "production_protocol_execution",
        "signed_result_receipt",
        "independent_review_complete",
        "two_host_reproduction_complete",
        "s0_accepted",
        "s1_admission_authorized",
        "scientific_or_product_promotion_authorized",
        "scientifically_validated",
        "claim_safe",
        "receipt_sha256",
    }
    if set(observed) != expected_fields:
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition receipt fields are invalid"
        )
    source, native = _source_inputs(
        source_materialization,
        source_native_receipt,
        expected_source_materialization_sha256=(
            expected_source_materialization_sha256
        ),
        expected_source_native_receipt_sha256=(
            expected_source_native_receipt_sha256
        ),
    )
    configuration = (
        openmm_reference_fixed_born_disposition_configuration_document()
    )
    mapping = openmm_reference_mapping_contract_document()
    if (
        observed["schema_id"]
        != OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_SCHEMA_ID
        or observed["receipt_id"]
        != OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_ID
        or observed["oracle_id"] != OPENMM_REFERENCE_OFFLINE_ORACLE_ID
        or _require_utc(observed["observed_at_utc"])
        != observed["observed_at_utc"]
        or observed["configuration_sha256"]
        != configuration["configuration_sha256"]
        or observed["mapping_contract_sha256"] != mapping["contract_sha256"]
        or observed["minimization_protocol_sha256"]
        != configuration["minimization_protocol_sha256"]
        or observed["source_materialization_sha256"]
        != source["materialization_sha256"]
        or observed["source_materialization_transport_sha256"] != _sha256(source)
        or observed["source_native_receipt_sha256"] != native["receipt_sha256"]
        or observed["source_native_receipt_transport_sha256"] != _sha256(native)
        or observed["runtime_identity_sha256"]
        != native["runtime_identity_sha256"]
        or observed["implementation_source_sha256"] != _module_source_sha256()
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition receipt ancestry or identity drifted"
        )
    raw_cases = observed["cases"]
    if not isinstance(raw_cases, list) or len(raw_cases) != 2:
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition receipt must retain both failure aliases"
        )
    mapping_cases = {row["case_id"]: row for row in mapping["minimization_cases"]}
    native_cases = {row["case_id"]: row for row in native["cases"]}
    expected_case_rows: list[dict[str, Any]] = []
    for configuration_case, raw_case in zip(
        configuration["case_rows"], raw_cases, strict=True
    ):
        case_id = configuration_case["case_id"]
        if not isinstance(raw_case, Mapping) or raw_case.get("case_id") != case_id:
            raise OpenMMReferenceFixedBornDispositionError(
                "fixed-Born disposition case order drifted"
            )
        raw_probes = raw_case.get("probes")
        if not isinstance(raw_probes, list):
            raise OpenMMReferenceFixedBornDispositionError(
                "fixed-Born disposition probe rows are missing"
            )
        raw_baseline_control = raw_case.get(
            "no_reporter_baseline_control_endpoint"
        )
        if not isinstance(raw_baseline_control, Mapping):
            raise OpenMMReferenceFixedBornDispositionError(
                "fixed-Born disposition no-reporter control is missing"
            )
        try:
            expected_case = _case_projection(
                configuration_case=configuration_case,
                mapping_case=mapping_cases[case_id],
                source_native_case=native_cases[case_id],
                raw_baseline_control=raw_baseline_control,
                raw_probes=[
                    row["probe_endpoint"]
                    if isinstance(row, Mapping) and "probe_endpoint" in row
                    else {}
                    for row in raw_probes
                ],
                probe_configurations=configuration["probe_rows"],
            )
        except (
            OpenMMReferenceNativeMinimizationError,
            OpenMMReferenceOfflineOracleError,
            OpenMMReferenceReceiptError,
            RuntimeError,
        ) as exc:
            raise OpenMMReferenceFixedBornDispositionError(
                "fixed-Born disposition case evidence is invalid"
            ) from exc
        if dict(raw_case) != expected_case:
            raise OpenMMReferenceFixedBornDispositionError(
                "fixed-Born disposition case values drifted"
            )
        expected_case_rows.append(expected_case)
    summary = _summary(expected_case_rows)
    status = (
        "accepted_failure_disposition_evidence"
        if summary["failure_disposition_complete"]
        else "rejected_failure_disposition_evidence"
    )
    if (
        observed["summary"] != summary
        or observed["status"] != status
        or observed["scientific_blockers"]
        != list(OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_BLOCKERS)
        or observed["offline_failure_disposition_observation"] is not True
        or observed["all_preregistered_probes_executed"] is not True
        or any(
            observed[name] is not False
            for name in (
                "frozen_native_endpoint_result_replaced",
                "frozen_native_endpoint_health_failure_resolved",
                "threshold_relaxation_authorized",
                "causal_root_cause_proven",
                "optimizer_rejection_count_available",
                "production_protocol_execution",
                "signed_result_receipt",
                "independent_review_complete",
                "two_host_reproduction_complete",
                "s0_accepted",
                "s1_admission_authorized",
                "scientific_or_product_promotion_authorized",
                "scientifically_validated",
                "claim_safe",
            )
        )
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition summary, status, or claim boundary drifted"
        )
    digest = _require_sha256(observed["receipt_sha256"], name="disposition receipt")
    projection = {
        key: item for key, item in observed.items() if key != "receipt_sha256"
    }
    if digest != _sha256(projection):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition receipt digest mismatch"
        )
    if reexecute:
        expected = build_openmm_reference_fixed_born_disposition_receipt(
            source,
            native,
            expected_source_materialization_sha256=(
                expected_source_materialization_sha256
            ),
            expected_source_native_receipt_sha256=(
                expected_source_native_receipt_sha256
            ),
            observed_at_utc=observed["observed_at_utc"],
        )
        if observed != expected:
            raise OpenMMReferenceFixedBornDispositionError(
                "fixed-Born disposition receipt failed exact reexecution"
            )
    return observed


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OpenMMReferenceFixedBornDispositionError(
                "fixed-Born disposition receipt contains a duplicate JSON key"
            )
        result[key] = value
    return result


def read_openmm_reference_fixed_born_disposition_receipt(
    input_path: str | os.PathLike[str],
    *,
    source_materialization: Mapping[str, Any],
    source_native_receipt: Mapping[str, Any],
    expected_source_materialization_sha256: str,
    expected_source_native_receipt_sha256: str,
) -> dict[str, Any]:
    path = Path(input_path)
    try:
        before = path.lstat()
    except OSError as exc:
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition receipt file is unavailable"
        ) from exc
    if path.is_symlink() or not stat.S_ISREG(before.st_mode):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition receipt must be a regular non-symlink file"
        )
    if (
        before.st_size < 1
        or before.st_size
        > MAX_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_BYTES
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition receipt exceeds its byte bound"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(
        os, "O_NOFOLLOW", 0
    )
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            opened = os.fstat(handle.fileno())
            raw = handle.read(
                MAX_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_BYTES + 1
            )
            after = os.fstat(handle.fileno())
    except OSError as exc:
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition receipt cannot be read"
        ) from exc
    if (
        opened.st_dev != before.st_dev
        or opened.st_ino != before.st_ino
        or opened.st_size != before.st_size
        or after.st_size != opened.st_size
        or len(raw) != opened.st_size
    ):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition receipt changed while being read"
        )
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=lambda item: (_ for _ in ()).throw(
                OpenMMReferenceFixedBornDispositionError(
                    f"non-finite JSON value {item} is forbidden"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition receipt is not canonical ASCII JSON"
        ) from exc
    if not isinstance(value, dict) or raw != _canonical_bytes(value):
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition receipt is not canonical JSON"
        )
    return require_openmm_reference_fixed_born_disposition_receipt(
        value,
        source_materialization=source_materialization,
        source_native_receipt=source_native_receipt,
        expected_source_materialization_sha256=(
            expected_source_materialization_sha256
        ),
        expected_source_native_receipt_sha256=(
            expected_source_native_receipt_sha256
        ),
    )


def write_openmm_reference_fixed_born_disposition_receipt(
    value: Mapping[str, Any],
    output_path: str | os.PathLike[str],
    *,
    source_materialization: Mapping[str, Any],
    source_native_receipt: Mapping[str, Any],
    expected_source_materialization_sha256: str,
    expected_source_native_receipt_sha256: str,
) -> Path:
    receipt = require_openmm_reference_fixed_born_disposition_receipt(
        value,
        source_materialization=source_materialization,
        source_native_receipt=source_native_receipt,
        expected_source_materialization_sha256=(
            expected_source_materialization_sha256
        ),
        expected_source_native_receipt_sha256=(
            expected_source_native_receipt_sha256
        ),
    )
    payload = _canonical_bytes(receipt)
    if len(payload) > MAX_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_BYTES:
        raise OpenMMReferenceFixedBornDispositionError(
            "fixed-Born disposition receipt exceeds its byte bound"
        )
    output = Path(output_path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise OpenMMReferenceFixedBornDispositionError(
                "fixed-Born disposition receipt output already exists"
            ) from exc
        directory_descriptor = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


def _summary_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_SCHEMA_ID,
        "receipt_sha256": value["receipt_sha256"],
        "source_materialization_sha256": value["source_materialization_sha256"],
        "source_native_receipt_sha256": value["source_native_receipt_sha256"],
        "runtime_identity_sha256": value["runtime_identity_sha256"],
        "observed_at_utc": value["observed_at_utc"],
        "status": value["status"],
        "summary": value["summary"],
        "scientific_blockers": value["scientific_blockers"],
        "claim_safe": False,
    }


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-openmm-fixed-born-disposition",
        description=(
            "Materialize or verify the preregistered fixed-Born native endpoint "
            "failure disposition. This never replaces the rejected endpoint or "
            "authorizes S0 admission."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--source-materialization", required=True)
    materialize.add_argument(
        "--expected-source-materialization-sha256", required=True
    )
    materialize.add_argument("--source-native-receipt", required=True)
    materialize.add_argument(
        "--expected-source-native-receipt-sha256", required=True
    )
    materialize.add_argument("--output", required=True)
    materialize.add_argument("--observed-at-utc")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--source-materialization", required=True)
    verify.add_argument("--expected-source-materialization-sha256", required=True)
    verify.add_argument("--source-native-receipt", required=True)
    verify.add_argument("--expected-source-native-receipt-sha256", required=True)
    verify.add_argument("--input", required=True)
    verify.add_argument("--reexecute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _cli_parser().parse_args(argv)
    try:
        source = read_openmm_reference_materialization(args.source_materialization)
        native = read_openmm_reference_native_minimization_receipt(
            args.source_native_receipt,
            source_materialization=source,
            expected_source_materialization_sha256=(
                args.expected_source_materialization_sha256
            ),
        )
        if args.command == "materialize":
            receipt = build_openmm_reference_fixed_born_disposition_receipt(
                source,
                native,
                expected_source_materialization_sha256=(
                    args.expected_source_materialization_sha256
                ),
                expected_source_native_receipt_sha256=(
                    args.expected_source_native_receipt_sha256
                ),
                observed_at_utc=args.observed_at_utc,
            )
            write_openmm_reference_fixed_born_disposition_receipt(
                receipt,
                args.output,
                source_materialization=source,
                source_native_receipt=native,
                expected_source_materialization_sha256=(
                    args.expected_source_materialization_sha256
                ),
                expected_source_native_receipt_sha256=(
                    args.expected_source_native_receipt_sha256
                ),
            )
        else:
            receipt = read_openmm_reference_fixed_born_disposition_receipt(
                args.input,
                source_materialization=source,
                source_native_receipt=native,
                expected_source_materialization_sha256=(
                    args.expected_source_materialization_sha256
                ),
                expected_source_native_receipt_sha256=(
                    args.expected_source_native_receipt_sha256
                ),
            )
            if args.reexecute:
                receipt = (
                    require_openmm_reference_fixed_born_disposition_receipt(
                        receipt,
                        source_materialization=source,
                        source_native_receipt=native,
                        expected_source_materialization_sha256=(
                            args.expected_source_materialization_sha256
                        ),
                        expected_source_native_receipt_sha256=(
                            args.expected_source_native_receipt_sha256
                        ),
                        reexecute=True,
                    )
                )
    except (
        OSError,
        OpenMMReferenceFixedBornDispositionError,
        OpenMMReferenceMaterializationError,
        OpenMMReferenceNativeMinimizationError,
        OpenMMReferenceOfflineOracleError,
        OpenMMReferenceReceiptError,
        RuntimeError,
    ) as exc:
        print(f"OpenMM fixed-Born disposition failed: {exc}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(_canonical_bytes(_summary_receipt(receipt)) + b"\n")
    return 0 if receipt["status"].startswith("accepted_") else 3


__all__ = [
    "FIXED_BORN_FAILURE_CASE_IDS",
    "FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V1",
    "FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V2",
    "FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V3",
    "FROZEN_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256",
    "MAX_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_BYTES",
    "OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_BLOCKERS",
    "OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_ID",
    "OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SCHEMA_ID",
    "OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_PROBE_SCHEMA_ID",
    "OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_ID",
    "OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_SCHEMA_ID",
    "OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_TRACE_SCHEMA_ID",
    "OpenMMReferenceFixedBornDispositionError",
    "build_openmm_reference_fixed_born_disposition_receipt",
    "main",
    "openmm_reference_fixed_born_disposition_configuration_document",
    "read_openmm_reference_fixed_born_disposition_receipt",
    "require_openmm_reference_fixed_born_disposition_configuration_document",
    "require_openmm_reference_fixed_born_disposition_receipt",
    "write_openmm_reference_fixed_born_disposition_receipt",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
