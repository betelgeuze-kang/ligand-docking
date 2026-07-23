"""Failure-inclusive OpenMM Reference native minimization endpoint comparison.

This offline-only workflow runs OpenMM ``LocalEnergyMinimizer`` on the eight
executable cases in the frozen fourteen-case minimization matrix.  It retains
the six expected fail-closed rows, re-evaluates every OpenMM endpoint with
Engine v2 at identical coordinates, and records cross-algorithm endpoint
deltas without claiming trajectory or endpoint equivalence.
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
from betelgeuze_engine_v2.physics.reference_minimization_validation_runner import (
    ReferenceMinimizationValidationCoordinateTrace,
)

from .openmm_reference_materialization import (
    OpenMMReferenceMaterializationError,
    read_openmm_reference_materialization,
    require_openmm_reference_materialization,
)
from .openmm_reference_oracle import (
    OPENMM_REFERENCE_NATIVE_MINIMIZATION_SCHEMA_ID,
    OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
    OPENMM_REFERENCE_REQUIRED_PLATFORM,
    OpenMMReferenceOfflineOracleError,
    OpenMMReferenceSession,
    coordinate_f64le_sha256,
    openmm_reference_mapping_contract_document,
    require_openmm_reference_runtime_identity_document,
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


OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_native_minimization_configuration/1.0.0"
)
OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_native_minimization_receipt/1.0.0"
)
OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_ID = (
    "engine_v2_openmm_reference_native_minimization_configuration/1.0.0"
)
OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_ID = (
    "engine_v2_openmm_reference_native_minimization_receipt/1.0.0"
)
MAX_OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_BYTES = 32 * 1024 * 1024
OPENMM_REFERENCE_NATIVE_MINIMIZATION_ENERGY_NONINCREASE_TOLERANCE_KCAL_PER_MOL = (
    1.0e-10
)

# Filled after the configuration projection is reviewed.  This binds only
# protocol/configuration values and is frozen before native endpoint execution.
FROZEN_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256 = (
    "6465f726c408e6df2dd15d318a4cdfc57a8b2edd271ddaa578edcc336110017e"
)

OPENMM_REFERENCE_NATIVE_MINIMIZATION_BLOCKERS = (
    "production_execution_authorization_missing",
    "signed_engine_result_receipts_missing",
    "second_cpu_host_receipt_missing",
    "independent_human_result_review_missing",
    "cross_algorithm_endpoint_equivalence_not_claimed",
    "openmm_iteration_trace_and_checkpoint_restart_not_available",
)


class OpenMMReferenceNativeMinimizationError(RuntimeError):
    """The endpoint configuration, ancestry, receipt, or filesystem is invalid."""


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
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OpenMMReferenceNativeMinimizationError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpenMMReferenceNativeMinimizationError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise OpenMMReferenceNativeMinimizationError(f"{name} must be finite")
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
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization timestamp must be UTC text"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization timestamp is invalid"
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
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization timestamp must use canonical UTC seconds"
        )
    return value


def _module_source_sha256() -> str:
    path = Path(__file__)
    try:
        before = path.stat()
        raw = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization source cannot be read"
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
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization source changed while being hashed"
        )
    return hashlib.sha256(raw).hexdigest()


def _max_rms(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rows = tuple(_finite(value, name="metric value") for value in values)
    return max(abs(value) for value in rows), math.sqrt(
        sum(value * value for value in rows) / len(rows)
    )


def _configuration_projection() -> dict[str, Any]:
    protocol = cpu_minimization_validation_protocol_document()
    mapping = openmm_reference_mapping_contract_document()
    case_rows: list[dict[str, Any]] = []
    for protocol_case, mapping_case in zip(
        protocol["case_manifest"]["cases"],
        mapping["minimization_cases"],
        strict=True,
    ):
        materialized = materialize_frozen_cpu_minimization_validation_case(
            protocol_case["case_id"],
            protocol,
        )
        independent = materialized.independent_oracle_input
        if (
            mapping_case["case_id"] != protocol_case["case_id"]
            or mapping_case["case_input_sha256"] != protocol_case["input_sha256"]
        ):
            raise OpenMMReferenceNativeMinimizationError(
                "native minimization configuration is cross-protocol"
            )
        case_rows.append(
            {
                "case_id": protocol_case["case_id"],
                "case_input_sha256": protocol_case["input_sha256"],
                "runtime_input_sha256": materialized.runtime_input_sha256,
                "expected_outcome": protocol_case["expected_outcome"],
                "expected_error_code": protocol_case["expected_error_code"],
                "disposition": (
                    "execute_openmm_native_endpoint"
                    if protocol_case["expected_outcome"] == "pass"
                    else "not_applicable_engine_contract"
                ),
                "openmm_tolerance_kcal_per_mol_angstrom": (
                    independent.force_tolerance_kcal_per_mol_angstrom
                ),
                "openmm_maximum_iterations": independent.max_iterations,
                "openmm_constraint_tolerance_relative": min(
                    (row[3] / row[2] for row in independent.constraints),
                    default=1.0e-10,
                ),
                "constraint_count": len(independent.constraints),
                "constraint_max_abs_residual_threshold_angstrom": max(
                    (row[3] for row in independent.constraints),
                    default=0.0,
                ),
                "tangent_force_max_threshold_kcal_per_mol_angstrom": (
                    independent.force_tolerance_kcal_per_mol_angstrom
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
        "schema_id": OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SCHEMA_ID,
        "configuration_id": OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_ID,
        "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
        "mapping_contract_sha256": mapping["contract_sha256"],
        "minimization_protocol_sha256": protocol["protocol_sha256"],
        "minimization_case_manifest_sha256": protocol["case_manifest"][
            "case_manifest_sha256"
        ],
        "algorithm": "OpenMM LocalEnergyMinimizer L-BFGS",
        "required_platform": OPENMM_REFERENCE_REQUIRED_PLATFORM,
        "case_rows": case_rows,
        "coverage": {
            "case_count": len(case_rows),
            "executable_case_count": sum(
                row["disposition"] == "execute_openmm_native_endpoint"
                for row in case_rows
            ),
            "not_applicable_case_count": sum(
                row["disposition"] == "not_applicable_engine_contract"
                for row in case_rows
            ),
            "all_failure_rows_retained": True,
        },
        "acceptance": {
            "same_coordinate_engine_openmm_mapping_thresholds": dict(
                mapping["predefined_acceptance"]
            ),
            "native_energy_nonincrease_tolerance_kcal_per_mol": (
                OPENMM_REFERENCE_NATIVE_MINIMIZATION_ENERGY_NONINCREASE_TOLERANCE_KCAL_PER_MOL
            ),
            "native_tangent_force_and_constraint_thresholds_reused_from_frozen_cases": True,
            "final_context_constraint_projection_required": True,
            "missing_case_or_metric_is_failure": True,
            "cross_algorithm_coordinate_delta_is_gated": False,
            "cross_algorithm_energy_delta_is_gated": False,
            "thresholds_predefined_before_endpoint_observation": True,
            "post_observation_tuning_allowed": False,
        },
        "claim_boundary": {
            "engine_trace_equivalence_claimed": False,
            "cross_algorithm_endpoint_equivalence_claimed": False,
            "openmm_checkpoint_restart_equality_claimed": False,
            "production_protocol_execution": False,
            "scientifically_validated": False,
            "claim_safe": False,
        },
    }


def openmm_reference_native_minimization_configuration_document() -> dict[str, Any]:
    projection = _configuration_projection()
    observed = _sha256(projection)
    if (
        FROZEN_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256
        and observed
        != FROZEN_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256
    ):
        raise OpenMMReferenceNativeMinimizationError(
            "frozen native minimization configuration hash drifted"
        )
    return {**projection, "configuration_sha256": observed}


def require_openmm_reference_native_minimization_configuration_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    expected = openmm_reference_native_minimization_configuration_document()
    if not isinstance(value, Mapping) or _canonical_bytes(dict(value)) != _canonical_bytes(
        expected
    ):
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization configuration differs from the frozen document"
        )
    return expected


def _component_names(mapping_case: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(row["component"] for row in mapping_case["component_force_groups"])


def _evaluation_identity(
    mapping_case: Mapping[str, Any],
    *,
    coordinate_sha256: str,
) -> dict[str, object]:
    return {
        "coordinate_f64le_sha256": coordinate_sha256,
        "atom_order_sha256": mapping_case["atom_order_sha256"],
        "system_topology_sha256": mapping_case["topology_sha256"],
        "base_parameter_fingerprint_sha256": mapping_case[
            "base_parameter_fingerprint_sha256"
        ],
        "v2_parameter_fingerprint_sha256": mapping_case[
            "v2_parameter_fingerprint_sha256"
        ],
        "solvation_parameter_fingerprint_sha256": mapping_case[
            "solvation_parameter_fingerprint_sha256"
        ],
    }


def _require_endpoint(
    value: object,
    *,
    mapping_case: Mapping[str, Any],
    materialized: Any,
    tolerance: float,
    maximum_iterations: int,
    constraint_tolerance_relative: float,
) -> tuple[dict[str, Any], tuple[tuple[float, float, float], ...]]:
    if not isinstance(value, Mapping):
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization endpoint must be a mapping"
        )
    endpoint = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    expected_fields = {
        "schema_id",
        "oracle_id",
        "platform",
        "algorithm",
        "tolerance_kcal_per_mol_angstrom",
        "maximum_iterations",
        "constraint_tolerance_relative",
        "final_context_constraint_projection_applied",
        "initial_evaluation",
        "final_coordinates_angstrom_hex",
        "final_evaluation",
        "engine_trace_equivalence_claimed",
        "checkpoint_restart_equality_claimed",
        "scientifically_validated",
        "claim_safe",
        "endpoint_sha256",
    }
    if set(endpoint) != expected_fields:
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization endpoint fields are invalid"
        )
    digest = _require_sha256(endpoint["endpoint_sha256"], name="native endpoint")
    projection = {
        key: item for key, item in endpoint.items() if key != "endpoint_sha256"
    }
    if digest != _sha256(projection):
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization endpoint digest mismatch"
        )
    if (
        endpoint["schema_id"] != OPENMM_REFERENCE_NATIVE_MINIMIZATION_SCHEMA_ID
        or endpoint["oracle_id"] != OPENMM_REFERENCE_OFFLINE_ORACLE_ID
        or endpoint["platform"] != OPENMM_REFERENCE_REQUIRED_PLATFORM
        or endpoint["algorithm"] != "OpenMM LocalEnergyMinimizer L-BFGS"
        or endpoint["tolerance_kcal_per_mol_angstrom"] != tolerance
        or endpoint["maximum_iterations"] != maximum_iterations
        or endpoint["constraint_tolerance_relative"]
        != constraint_tolerance_relative
        or endpoint["final_context_constraint_projection_applied"] is not True
        or any(
            endpoint[name] is not False
            for name in (
                "engine_trace_equivalence_claimed",
                "checkpoint_restart_equality_claimed",
                "scientifically_validated",
                "claim_safe",
            )
        )
    ):
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization endpoint contract drifted"
        )
    final_coordinates = _coordinates_from_hex(
        endpoint["final_coordinates_angstrom_hex"]
    )
    if len(final_coordinates) != mapping_case["atom_count"]:
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization endpoint atom count drifted"
        )
    initial_coordinates = tuple(
        tuple(float(value) for value in row)
        for row in materialized.system.coordinates[0].detach().cpu().tolist()
    )
    names = _component_names(mapping_case)
    _require_openmm_output(
        endpoint["initial_evaluation"],
        component_names=names,
        atom_count=mapping_case["atom_count"],
        expected_identity=_evaluation_identity(
            mapping_case,
            coordinate_sha256=coordinate_f64le_sha256(initial_coordinates),
        ),
    )
    _require_openmm_output(
        endpoint["final_evaluation"],
        component_names=names,
        atom_count=mapping_case["atom_count"],
        expected_identity=_evaluation_identity(
            mapping_case,
            coordinate_sha256=coordinate_f64le_sha256(final_coordinates),
        ),
    )
    return endpoint, final_coordinates


def _minimum_image(
    vector: Sequence[float],
    *,
    periodic_axes: Sequence[bool],
    cell: Sequence[float] | None,
) -> tuple[float, float, float]:
    if cell is None:
        return (float(vector[0]), float(vector[1]), float(vector[2]))
    return tuple(
        float(component)
        - round(float(component) / float(cell[axis])) * float(cell[axis])
        if periodic_axes[axis]
        else float(component)
        for axis, component in enumerate(vector)
    )  # type: ignore[return-value]


def _constraint_diagnostics(
    materialized: Any,
    coordinates: Sequence[Sequence[float]],
    forces: Sequence[Sequence[float]],
) -> dict[str, Any]:
    source = materialized.independent_oracle_input
    constraints = tuple(source.constraints)
    periodic_axes = source.energy_input.periodic_axes
    cell = source.energy_input.orthorhombic_cell_angstrom

    def pair_vector(atom_i: int, atom_j: int) -> tuple[float, float, float]:
        return _minimum_image(
            tuple(
                float(coordinates[atom_i][axis])
                - float(coordinates[atom_j][axis])
                for axis in range(3)
            ),
            periodic_axes=periodic_axes,
            cell=cell,
        )

    constraint_residual = max(
        (
            abs(
                math.sqrt(sum(value * value for value in pair_vector(row[0], row[1])))
                - row[2]
            )
            for row in constraints
        ),
        default=0.0,
    )
    projected = [list(map(float, row)) for row in forces]
    projection_residual = 0.0
    projection_sweeps = 0
    projection_converged = True
    if constraints:
        degrees = [0] * len(projected)
        for atom_i, atom_j, _, _ in constraints:
            degrees[atom_i] += 1
            degrees[atom_j] += 1
        relaxation = max(degrees, default=1)
        projection_converged = False
        for sweep in range(1, source.force_projection_max_sweeps + 1):
            updates = [[0.0, 0.0, 0.0] for _ in projected]
            for atom_i, atom_j, _, _ in constraints:
                vector = pair_vector(atom_i, atom_j)
                distance = math.sqrt(sum(value * value for value in vector))
                if distance <= 1.0e-12:
                    raise OpenMMReferenceNativeMinimizationError(
                        "native endpoint constraint tangent is undefined"
                    )
                direction = tuple(value / distance for value in vector)
                relative = sum(
                    (projected[atom_i][axis] - projected[atom_j][axis])
                    * direction[axis]
                    for axis in range(3)
                )
                for axis in range(3):
                    correction = 0.5 * relative * direction[axis]
                    updates[atom_i][axis] -= correction
                    updates[atom_j][axis] += correction
            for atom in range(len(projected)):
                for axis in range(3):
                    projected[atom][axis] += updates[atom][axis] / relaxation
            residuals = []
            for atom_i, atom_j, _, _ in constraints:
                vector = pair_vector(atom_i, atom_j)
                distance = math.sqrt(sum(value * value for value in vector))
                direction = tuple(value / distance for value in vector)
                residuals.append(
                    abs(
                        sum(
                            (projected[atom_i][axis] - projected[atom_j][axis])
                            * direction[axis]
                            for axis in range(3)
                        )
                    )
                )
            projection_residual = max(residuals, default=0.0)
            projection_sweeps = sweep
            if (
                projection_residual
                <= source.force_projection_tolerance_kcal_per_mol_angstrom
            ):
                projection_converged = True
                break
    tangent_norms = [
        math.sqrt(sum(component * component for component in row)) for row in projected
    ]
    tangent_force_max = max(tangent_norms, default=0.0)
    tangent_force_rms = math.sqrt(
        sum(value * value for value in tangent_norms) / len(tangent_norms)
    )
    return {
        "constraint_max_abs_residual_angstrom": constraint_residual,
        "tangent_force_max_kcal_per_mol_angstrom": tangent_force_max,
        "tangent_force_rms_kcal_per_mol_angstrom": tangent_force_rms,
        "force_projection_residual_kcal_per_mol_angstrom": projection_residual,
        "force_projection_sweeps": projection_sweeps,
        "force_projection_converged": projection_converged,
    }


def _endpoint_delta(
    source_coordinates: Sequence[Sequence[float]],
    endpoint_coordinates: Sequence[Sequence[float]],
    *,
    source_energy: float,
    endpoint_energy: float,
) -> dict[str, Any]:
    if len(source_coordinates) != len(endpoint_coordinates):
        raise OpenMMReferenceNativeMinimizationError(
            "cross-algorithm endpoint coordinate shapes differ"
        )
    coordinate_errors = tuple(
        abs(float(left) - float(right))
        for left_row, right_row in zip(
            source_coordinates, endpoint_coordinates, strict=True
        )
        for left, right in zip(left_row, right_row, strict=True)
    )
    maximum, rms = _max_rms(coordinate_errors)
    return {
        "coordinate_max_abs_delta_angstrom": maximum,
        "coordinate_rms_delta_angstrom": rms,
        "energy_abs_delta_kcal_per_mol": abs(source_energy - endpoint_energy),
        "coordinate_equivalence_threshold_applied": False,
        "energy_equivalence_threshold_applied": False,
        "endpoint_equivalence_claimed": False,
    }


def _evaluated_case_projection(
    *,
    protocol_case: Mapping[str, Any],
    configuration_case: Mapping[str, Any],
    mapping_case: Mapping[str, Any],
    source_trace_case: Mapping[str, Any],
    source_trace: ReferenceMinimizationValidationCoordinateTrace,
    endpoint_value: Mapping[str, Any],
) -> dict[str, Any]:
    materialized = materialize_frozen_cpu_minimization_validation_case(
        protocol_case["case_id"]
    )
    endpoint, endpoint_coordinates = _require_endpoint(
        endpoint_value,
        mapping_case=mapping_case,
        materialized=materialized,
        tolerance=configuration_case["openmm_tolerance_kcal_per_mol_angstrom"],
        maximum_iterations=configuration_case["openmm_maximum_iterations"],
        constraint_tolerance_relative=configuration_case[
            "openmm_constraint_tolerance_relative"
        ],
    )
    if source_trace.trace_state != "evaluated" or not source_trace.steps:
        raise OpenMMReferenceNativeMinimizationError(
            "executable source operational trace is incomplete"
        )
    source_final_step = source_trace.steps[-1]
    source_coordinates = _coordinates_from_hex(
        source_final_step.evaluated_coordinates_angstrom_hex
    )
    if not source_trace_case["steps"]:
        raise OpenMMReferenceNativeMinimizationError(
            "source trace comparison omitted its final step"
        )
    source_final_comparison = source_trace_case["steps"][-1]
    if (
        source_final_comparison["source_step_identity_sha256"]
        != source_final_step.step_identity_sha256
    ):
        raise OpenMMReferenceNativeMinimizationError(
            "source final trace step is cross-wired"
        )
    component_names = _component_names(mapping_case)
    source_engine = _require_engine_or_analytic_output(
        source_final_comparison["engine_evaluation"],
        component_names=component_names,
        atom_count=mapping_case["atom_count"],
    )
    engine_at_endpoint = _engine_trace_output(materialized, endpoint_coordinates)
    engine_at_endpoint = _require_engine_or_analytic_output(
        engine_at_endpoint,
        component_names=component_names,
        atom_count=mapping_case["atom_count"],
    )
    openmm_at_endpoint = endpoint["final_evaluation"]
    same_coordinate_comparison, _, _ = _comparison(
        engine_at_endpoint,
        openmm_at_endpoint,
    )
    _require_comparison(
        same_coordinate_comparison,
        left=engine_at_endpoint,
        right=openmm_at_endpoint,
    )
    diagnostics = _constraint_diagnostics(
        materialized,
        endpoint_coordinates,
        engine_at_endpoint["forces"]["values"],
    )
    initial_energy = _finite(
        endpoint["initial_evaluation"]["total_energy"]["value"],
        name="native initial energy",
    )
    final_energy = _finite(
        endpoint["final_evaluation"]["total_energy"]["value"],
        name="native final energy",
    )
    source_energy = _finite(
        source_engine["total_energy"]["value"],
        name="source endpoint energy",
    )
    endpoint_engine_energy = _finite(
        engine_at_endpoint["total_energy"]["value"],
        name="Engine-at-OpenMM endpoint energy",
    )
    energy_nonincreasing = (
        final_energy
        <= initial_energy
        + OPENMM_REFERENCE_NATIVE_MINIMIZATION_ENERGY_NONINCREASE_TOLERANCE_KCAL_PER_MOL
    )
    tangent_force_passed = (
        diagnostics["tangent_force_max_kcal_per_mol_angstrom"]
        <= configuration_case[
            "tangent_force_max_threshold_kcal_per_mol_angstrom"
        ]
    )
    constraint_passed = (
        diagnostics["constraint_max_abs_residual_angstrom"]
        <= configuration_case[
            "constraint_max_abs_residual_threshold_angstrom"
        ]
    )
    endpoint_health_passed = bool(
        same_coordinate_comparison["passed_predefined_thresholds"]
        and energy_nonincreasing
        and tangent_force_passed
        and constraint_passed
        and diagnostics["force_projection_converged"]
    )
    return {
        "case_id": protocol_case["case_id"],
        "case_input_sha256": protocol_case["input_sha256"],
        "runtime_input_sha256": materialized.runtime_input_sha256,
        "expected_outcome": "pass",
        "expected_error_code": None,
        "disposition": "evaluated_openmm_native_endpoint",
        "source_trace_sha256": source_trace.trace_sha256,
        "source_final_step_identity_sha256": source_final_step.step_identity_sha256,
        "native_endpoint": endpoint,
        "engine_source_endpoint_evaluation": source_engine,
        "engine_at_openmm_endpoint_evaluation": engine_at_endpoint,
        "engine_openmm_same_coordinate_comparison": same_coordinate_comparison,
        "native_endpoint_diagnostics": {
            **diagnostics,
            "energy_change_kcal_per_mol": final_energy - initial_energy,
            "energy_nonincreasing": energy_nonincreasing,
            "tangent_force_threshold_passed": tangent_force_passed,
            "constraint_residual_threshold_passed": constraint_passed,
            "endpoint_health_passed": endpoint_health_passed,
        },
        "cross_algorithm_endpoint_delta": _endpoint_delta(
            source_coordinates,
            endpoint_coordinates,
            source_energy=source_energy,
            endpoint_energy=endpoint_engine_energy,
        ),
        "native_endpoint_executed": True,
        "case_passed_predefined_endpoint_health": endpoint_health_passed,
    }


def _not_applicable_case_projection(
    *,
    protocol_case: Mapping[str, Any],
    source_trace: ReferenceMinimizationValidationCoordinateTrace,
) -> dict[str, Any]:
    if (
        protocol_case["expected_outcome"] != "fail_closed"
        or source_trace.trace_state != "not_evaluated_expected_fail_closed"
        or source_trace.steps
    ):
        raise OpenMMReferenceNativeMinimizationError(
            "expected fail-closed native endpoint disposition drifted"
        )
    materialized = materialize_frozen_cpu_minimization_validation_case(
        protocol_case["case_id"]
    )
    return {
        "case_id": protocol_case["case_id"],
        "case_input_sha256": protocol_case["input_sha256"],
        "runtime_input_sha256": materialized.runtime_input_sha256,
        "expected_outcome": "fail_closed",
        "expected_error_code": protocol_case["expected_error_code"],
        "disposition": "not_applicable_engine_contract",
        "source_trace_sha256": source_trace.trace_sha256,
        "source_final_step_identity_sha256": None,
        "native_endpoint": None,
        "engine_source_endpoint_evaluation": None,
        "engine_at_openmm_endpoint_evaluation": None,
        "engine_openmm_same_coordinate_comparison": None,
        "native_endpoint_diagnostics": None,
        "cross_algorithm_endpoint_delta": None,
        "native_endpoint_executed": False,
        "case_passed_predefined_endpoint_health": True,
    }


def _summary(case_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    evaluated = [
        row
        for row in case_rows
        if row["disposition"] == "evaluated_openmm_native_endpoint"
    ]
    not_applicable = [
        row for row in case_rows if row["disposition"] == "not_applicable_engine_contract"
    ]
    coordinate_maxima = [
        row["cross_algorithm_endpoint_delta"]["coordinate_max_abs_delta_angstrom"]
        for row in evaluated
    ]
    coordinate_rms_values = [
        row["cross_algorithm_endpoint_delta"]["coordinate_rms_delta_angstrom"]
        for row in evaluated
    ]
    energy_deltas = [
        row["cross_algorithm_endpoint_delta"]["energy_abs_delta_kcal_per_mol"]
        for row in evaluated
    ]
    tangent_forces = [
        row["native_endpoint_diagnostics"][
            "tangent_force_max_kcal_per_mol_angstrom"
        ]
        for row in evaluated
    ]
    constraint_residuals = [
        row["native_endpoint_diagnostics"]["constraint_max_abs_residual_angstrom"]
        for row in evaluated
    ]
    return {
        "case_count": len(case_rows),
        "evaluated_case_count": len(evaluated),
        "not_applicable_engine_contract_case_count": len(not_applicable),
        "all_failure_rows_retained": len(case_rows) == 14
        and len(not_applicable) == 6,
        "same_coordinate_mapping_passed_case_count": sum(
            row["engine_openmm_same_coordinate_comparison"][
                "passed_predefined_thresholds"
            ]
            for row in evaluated
        ),
        "energy_nonincreasing_case_count": sum(
            row["native_endpoint_diagnostics"]["energy_nonincreasing"]
            for row in evaluated
        ),
        "endpoint_health_passed_case_count": sum(
            row["case_passed_predefined_endpoint_health"] for row in evaluated
        ),
        "cross_algorithm_coordinate_max_abs_delta_angstrom": max(
            coordinate_maxima, default=0.0
        ),
        "cross_algorithm_coordinate_case_rms_max_angstrom": max(
            coordinate_rms_values, default=0.0
        ),
        "cross_algorithm_energy_abs_delta_max_kcal_per_mol": max(
            energy_deltas, default=0.0
        ),
        "native_tangent_force_max_kcal_per_mol_angstrom": max(
            tangent_forces, default=0.0
        ),
        "native_constraint_max_abs_residual_angstrom": max(
            constraint_residuals, default=0.0
        ),
        "cross_algorithm_endpoint_equivalence_gated": False,
        "all_predefined_endpoint_health_metrics_passed": bool(evaluated)
        and all(row["case_passed_predefined_endpoint_health"] for row in evaluated),
        "complete_failure_inclusive_comparison": len(case_rows) == 14
        and len(evaluated) == 8
        and len(not_applicable) == 6,
    }


def _source_inputs(
    source_materialization: Mapping[str, Any],
    *,
    expected_source_materialization_sha256: str,
) -> tuple[
    dict[str, Any],
    tuple[ReferenceMinimizationValidationCoordinateTrace, ...],
    dict[str, Mapping[str, Any]],
]:
    source = require_openmm_reference_materialization(source_materialization)
    expected = _require_sha256(
        expected_source_materialization_sha256,
        name="expected source materialization",
    )
    if source["materialization_sha256"] != expected:
        raise OpenMMReferenceNativeMinimizationError(
            "source materialization identity differs from caller expectation"
        )
    trace_receipt = source["minimization_trace_receipt"]
    try:
        traces = tuple(
            ReferenceMinimizationValidationCoordinateTrace.from_dict(row)
            for row in trace_receipt["source_operational_traces"]
        )
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise OpenMMReferenceNativeMinimizationError(
            "source operational traces are invalid"
        ) from exc
    trace_cases = {row["case_id"]: row for row in trace_receipt["cases"]}
    if len(traces) != 14 or len(trace_cases) != 14:
        raise OpenMMReferenceNativeMinimizationError(
            "source materialization does not retain all fourteen cases"
        )
    return source, traces, trace_cases


def build_openmm_reference_native_minimization_receipt(
    source_materialization: Mapping[str, Any],
    *,
    expected_source_materialization_sha256: str,
    observed_at_utc: str | None = None,
) -> dict[str, Any]:
    """Execute the frozen failure-inclusive native endpoint comparison."""

    source, traces, source_trace_cases = _source_inputs(
        source_materialization,
        expected_source_materialization_sha256=(
            expected_source_materialization_sha256
        ),
    )
    timestamp = _require_utc(_utc_now() if observed_at_utc is None else observed_at_utc)
    runtime = require_openmm_reference_runtime_identity_document(
        source["energy_force_receipt"]["runtime_identity"],
        reobserve=True,
    )
    configuration = openmm_reference_native_minimization_configuration_document()
    protocol = cpu_minimization_validation_protocol_document()
    mapping = openmm_reference_mapping_contract_document()
    mapping_cases = {row["case_id"]: row for row in mapping["minimization_cases"]}
    configuration_cases = {
        row["case_id"]: row for row in configuration["case_rows"]
    }
    trace_by_case = {trace.case_id: trace for trace in traces}
    case_rows: list[dict[str, Any]] = []
    for protocol_case in protocol["case_manifest"]["cases"]:
        case_id = protocol_case["case_id"]
        source_trace = trace_by_case[case_id]
        if protocol_case["expected_outcome"] == "fail_closed":
            case_rows.append(
                _not_applicable_case_projection(
                    protocol_case=protocol_case,
                    source_trace=source_trace,
                )
            )
            continue
        materialized = materialize_frozen_cpu_minimization_validation_case(
            case_id,
            protocol,
        )
        configuration_case = configuration_cases[case_id]
        with OpenMMReferenceSession(
            materialized.system,
            materialized.base_parameters,
            v2_parameters=materialized.v2_parameters,
            solvation_parameters=materialized.solvation_parameters,
        ) as session:
            endpoint = session.native_minimize_endpoint(
                tolerance_kcal_per_mol_angstrom=configuration_case[
                    "openmm_tolerance_kcal_per_mol_angstrom"
                ],
                maximum_iterations=configuration_case[
                    "openmm_maximum_iterations"
                ],
                constraint_tolerance_relative=configuration_case[
                    "openmm_constraint_tolerance_relative"
                ],
            )
        case_rows.append(
            _evaluated_case_projection(
                protocol_case=protocol_case,
                configuration_case=configuration_case,
                mapping_case=mapping_cases[case_id],
                source_trace_case=source_trace_cases[case_id],
                source_trace=source_trace,
                endpoint_value=endpoint,
            )
        )
    summary = _summary(case_rows)
    status = (
        "accepted_offline_native_endpoint_comparison"
        if summary["complete_failure_inclusive_comparison"]
        and summary["all_predefined_endpoint_health_metrics_passed"]
        else "rejected_offline_native_endpoint_comparison"
    )
    projection = {
        "schema_id": OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_SCHEMA_ID,
        "receipt_id": OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_ID,
        "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
        "observed_at_utc": timestamp,
        "configuration_sha256": configuration["configuration_sha256"],
        "mapping_contract_sha256": mapping["contract_sha256"],
        "minimization_protocol_sha256": protocol["protocol_sha256"],
        "source_materialization_sha256": source["materialization_sha256"],
        "source_materialization_transport_sha256": _sha256(source),
        "source_minimization_trace_receipt_sha256": source[
            "minimization_trace_receipt"
        ]["receipt_sha256"],
        "runtime_identity_sha256": runtime["runtime_identity_sha256"],
        "implementation_source_sha256": _module_source_sha256(),
        "cases": case_rows,
        "summary": summary,
        "status": status,
        "scientific_blockers": list(OPENMM_REFERENCE_NATIVE_MINIMIZATION_BLOCKERS),
        "offline_reference_observation": True,
        "native_minimization_endpoint_executed": True,
        "engine_same_coordinate_re_evaluation_executed": True,
        "cross_algorithm_endpoint_equivalence_claimed": False,
        "engine_trace_equivalence_to_openmm_lbfgs_claimed": False,
        "openmm_checkpoint_restart_equality_claimed": False,
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


def require_openmm_reference_native_minimization_receipt(
    value: Mapping[str, Any],
    *,
    source_materialization: Mapping[str, Any],
    expected_source_materialization_sha256: str,
    reexecute: bool = False,
) -> dict[str, Any]:
    """Verify one receipt and optionally execute every native endpoint again."""

    if not isinstance(value, Mapping):
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization receipt must be a mapping"
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
        "source_minimization_trace_receipt_sha256",
        "runtime_identity_sha256",
        "implementation_source_sha256",
        "cases",
        "summary",
        "status",
        "scientific_blockers",
        "offline_reference_observation",
        "native_minimization_endpoint_executed",
        "engine_same_coordinate_re_evaluation_executed",
        "cross_algorithm_endpoint_equivalence_claimed",
        "engine_trace_equivalence_to_openmm_lbfgs_claimed",
        "openmm_checkpoint_restart_equality_claimed",
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
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization receipt fields are invalid"
        )
    source, traces, source_trace_cases = _source_inputs(
        source_materialization,
        expected_source_materialization_sha256=(
            expected_source_materialization_sha256
        ),
    )
    configuration = openmm_reference_native_minimization_configuration_document()
    protocol = cpu_minimization_validation_protocol_document()
    mapping = openmm_reference_mapping_contract_document()
    if (
        observed["schema_id"]
        != OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_SCHEMA_ID
        or observed["receipt_id"] != OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_ID
        or observed["oracle_id"] != OPENMM_REFERENCE_OFFLINE_ORACLE_ID
        or _require_utc(observed["observed_at_utc"]) != observed["observed_at_utc"]
        or observed["configuration_sha256"]
        != configuration["configuration_sha256"]
        or observed["mapping_contract_sha256"] != mapping["contract_sha256"]
        or observed["minimization_protocol_sha256"] != protocol["protocol_sha256"]
        or observed["source_materialization_sha256"]
        != source["materialization_sha256"]
        or observed["source_materialization_transport_sha256"] != _sha256(source)
        or observed["source_minimization_trace_receipt_sha256"]
        != source["minimization_trace_receipt"]["receipt_sha256"]
        or observed["runtime_identity_sha256"]
        != source["energy_force_receipt"]["runtime_identity"][
            "runtime_identity_sha256"
        ]
        or observed["implementation_source_sha256"] != _module_source_sha256()
    ):
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization receipt ancestry or identity drifted"
        )
    raw_cases = observed["cases"]
    if not isinstance(raw_cases, list) or len(raw_cases) != 14:
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization receipt must retain all fourteen cases"
        )
    configuration_cases = {
        row["case_id"]: row for row in configuration["case_rows"]
    }
    mapping_cases = {row["case_id"]: row for row in mapping["minimization_cases"]}
    traces_by_case = {trace.case_id: trace for trace in traces}
    expected_case_rows: list[dict[str, Any]] = []
    for protocol_case, raw_case in zip(
        protocol["case_manifest"]["cases"], raw_cases, strict=True
    ):
        case_id = protocol_case["case_id"]
        if not isinstance(raw_case, Mapping) or raw_case.get("case_id") != case_id:
            raise OpenMMReferenceNativeMinimizationError(
                "native minimization case order drifted"
            )
        if protocol_case["expected_outcome"] == "fail_closed":
            expected_case = _not_applicable_case_projection(
                protocol_case=protocol_case,
                source_trace=traces_by_case[case_id],
            )
        else:
            endpoint = raw_case.get("native_endpoint")
            if not isinstance(endpoint, Mapping):
                raise OpenMMReferenceNativeMinimizationError(
                    "native minimization endpoint is missing"
                )
            expected_case = _evaluated_case_projection(
                protocol_case=protocol_case,
                configuration_case=configuration_cases[case_id],
                mapping_case=mapping_cases[case_id],
                source_trace_case=source_trace_cases[case_id],
                source_trace=traces_by_case[case_id],
                endpoint_value=endpoint,
            )
        if dict(raw_case) != expected_case:
            raise OpenMMReferenceNativeMinimizationError(
                "native minimization case values drifted"
            )
        expected_case_rows.append(expected_case)
    summary = _summary(expected_case_rows)
    status = (
        "accepted_offline_native_endpoint_comparison"
        if summary["complete_failure_inclusive_comparison"]
        and summary["all_predefined_endpoint_health_metrics_passed"]
        else "rejected_offline_native_endpoint_comparison"
    )
    if (
        observed["summary"] != summary
        or observed["status"] != status
        or observed["scientific_blockers"]
        != list(OPENMM_REFERENCE_NATIVE_MINIMIZATION_BLOCKERS)
        or observed["offline_reference_observation"] is not True
        or observed["native_minimization_endpoint_executed"] is not True
        or observed["engine_same_coordinate_re_evaluation_executed"] is not True
        or any(
            observed[name] is not False
            for name in (
                "cross_algorithm_endpoint_equivalence_claimed",
                "engine_trace_equivalence_to_openmm_lbfgs_claimed",
                "openmm_checkpoint_restart_equality_claimed",
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
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization summary, status, or claim boundary drifted"
        )
    digest = _require_sha256(observed["receipt_sha256"], name="native receipt")
    projection = {
        key: item for key, item in observed.items() if key != "receipt_sha256"
    }
    if digest != _sha256(projection):
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization receipt digest mismatch"
        )
    if reexecute:
        expected = build_openmm_reference_native_minimization_receipt(
            source,
            expected_source_materialization_sha256=(
                expected_source_materialization_sha256
            ),
            observed_at_utc=observed["observed_at_utc"],
        )
        if observed != expected:
            raise OpenMMReferenceNativeMinimizationError(
                "native minimization receipt failed exact reexecution"
            )
    return observed


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OpenMMReferenceNativeMinimizationError(
                "native minimization receipt contains a duplicate JSON key"
            )
        result[key] = value
    return result


def read_openmm_reference_native_minimization_receipt(
    input_path: str | os.PathLike[str],
    *,
    source_materialization: Mapping[str, Any],
    expected_source_materialization_sha256: str,
) -> dict[str, Any]:
    path = Path(input_path)
    try:
        before = path.lstat()
    except OSError as exc:
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization receipt file is unavailable"
        ) from exc
    if path.is_symlink() or not stat.S_ISREG(before.st_mode):
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization receipt must be a regular non-symlink file"
        )
    if (
        before.st_size < 1
        or before.st_size > MAX_OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_BYTES
    ):
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization receipt exceeds its byte bound"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            opened = os.fstat(handle.fileno())
            raw = handle.read(
                MAX_OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_BYTES + 1
            )
            after = os.fstat(handle.fileno())
    except OSError as exc:
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization receipt cannot be read"
        ) from exc
    if (
        opened.st_dev != before.st_dev
        or opened.st_ino != before.st_ino
        or opened.st_size != before.st_size
        or after.st_size != opened.st_size
        or len(raw) != opened.st_size
    ):
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization receipt changed while being read"
        )
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=lambda item: (_ for _ in ()).throw(
                OpenMMReferenceNativeMinimizationError(
                    f"non-finite JSON value {item} is forbidden"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization receipt is not canonical ASCII JSON"
        ) from exc
    if not isinstance(value, dict) or raw != _canonical_bytes(value):
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization receipt is not canonical JSON"
        )
    return require_openmm_reference_native_minimization_receipt(
        value,
        source_materialization=source_materialization,
        expected_source_materialization_sha256=(
            expected_source_materialization_sha256
        ),
    )


def write_openmm_reference_native_minimization_receipt(
    value: Mapping[str, Any],
    output_path: str | os.PathLike[str],
    *,
    source_materialization: Mapping[str, Any],
    expected_source_materialization_sha256: str,
) -> Path:
    receipt = require_openmm_reference_native_minimization_receipt(
        value,
        source_materialization=source_materialization,
        expected_source_materialization_sha256=(
            expected_source_materialization_sha256
        ),
    )
    payload = _canonical_bytes(receipt)
    if len(payload) > MAX_OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_BYTES:
        raise OpenMMReferenceNativeMinimizationError(
            "native minimization receipt exceeds its byte bound"
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
            raise OpenMMReferenceNativeMinimizationError(
                "native minimization receipt output already exists"
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
        "schema_id": OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_SCHEMA_ID,
        "receipt_sha256": value["receipt_sha256"],
        "source_materialization_sha256": value["source_materialization_sha256"],
        "runtime_identity_sha256": value["runtime_identity_sha256"],
        "observed_at_utc": value["observed_at_utc"],
        "status": value["status"],
        "summary": value["summary"],
        "scientific_blockers": value["scientific_blockers"],
        "claim_safe": False,
    }


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-openmm-native-minimization",
        description=(
            "Materialize or verify failure-inclusive OpenMM Reference native "
            "minimization endpoints. This is offline evidence, never a production "
            "authorization or endpoint-equivalence claim."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--source-materialization", required=True)
    materialize.add_argument(
        "--expected-source-materialization-sha256", required=True
    )
    materialize.add_argument("--output", required=True)
    materialize.add_argument("--observed-at-utc")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--source-materialization", required=True)
    verify.add_argument("--expected-source-materialization-sha256", required=True)
    verify.add_argument("--input", required=True)
    verify.add_argument("--reexecute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _cli_parser().parse_args(argv)
    try:
        source = read_openmm_reference_materialization(args.source_materialization)
        if args.command == "materialize":
            receipt = build_openmm_reference_native_minimization_receipt(
                source,
                expected_source_materialization_sha256=(
                    args.expected_source_materialization_sha256
                ),
                observed_at_utc=args.observed_at_utc,
            )
            write_openmm_reference_native_minimization_receipt(
                receipt,
                args.output,
                source_materialization=source,
                expected_source_materialization_sha256=(
                    args.expected_source_materialization_sha256
                ),
            )
        else:
            receipt = read_openmm_reference_native_minimization_receipt(
                args.input,
                source_materialization=source,
                expected_source_materialization_sha256=(
                    args.expected_source_materialization_sha256
                ),
            )
            if args.reexecute:
                receipt = require_openmm_reference_native_minimization_receipt(
                    receipt,
                    source_materialization=source,
                    expected_source_materialization_sha256=(
                        args.expected_source_materialization_sha256
                    ),
                    reexecute=True,
                )
    except (
        OSError,
        OpenMMReferenceMaterializationError,
        OpenMMReferenceNativeMinimizationError,
        OpenMMReferenceOfflineOracleError,
        OpenMMReferenceReceiptError,
        RuntimeError,
    ) as exc:
        print(f"OpenMM native minimization comparison failed: {exc}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(_canonical_bytes(_summary_receipt(receipt)) + b"\n")
    return 0 if receipt["status"].startswith("accepted_") else 3


__all__ = [
    "FROZEN_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256",
    "MAX_OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_BYTES",
    "OPENMM_REFERENCE_NATIVE_MINIMIZATION_BLOCKERS",
    "OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_ID",
    "OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SCHEMA_ID",
    "OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_ID",
    "OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_SCHEMA_ID",
    "OpenMMReferenceNativeMinimizationError",
    "build_openmm_reference_native_minimization_receipt",
    "main",
    "openmm_reference_native_minimization_configuration_document",
    "read_openmm_reference_native_minimization_receipt",
    "require_openmm_reference_native_minimization_configuration_document",
    "require_openmm_reference_native_minimization_receipt",
    "write_openmm_reference_native_minimization_receipt",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
