"""Claim-closed 14-case successor observation for minimization stationarity.

The frozen 14-case protocol and its production receipts remain immutable.  This
module reuses the frozen inputs, executes a separately versioned successor
algorithm for the four constrained aliases, retains every failure row, and
binds the same-coordinate OpenMM candidate comparison.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import stat
import sys
from typing import Any, Mapping, Sequence

import torch

from betelgeuze_engine_v2.offline.openmm_reference_constraint_stationarity import (
    FROZEN_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256,
    build_openmm_reference_constraint_stationarity_receipt,
    require_openmm_reference_constraint_stationarity_receipt,
)
from betelgeuze_engine_v2.physics.reference_constraint_stationarity import (
    REFERENCE_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256,
    ReferenceConstraintStationarityConfig,
    minimize_reference_constraint_stationarity,
)
from betelgeuze_engine_v2.physics.reference_constraint_stationarity_independent_oracle import (
    INDEPENDENT_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256,
    IndependentConstraintStationarityConfig,
    evaluate_independent_constraint_stationarity,
)
from betelgeuze_engine_v2.physics.reference_minimization import (
    minimize_reference_force_field,
)
from betelgeuze_engine_v2.physics.reference_minimization_independent_oracle import (
    evaluate_independent_minimization_oracle,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_materializer import (
    materialize_frozen_cpu_minimization_validation_case,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_protocol import (
    FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
    cpu_minimization_validation_protocol_document,
)


REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_minimization_stationarity_successor_config/1.0.0"
)
REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_minimization_stationarity_successor_observation/1.0.0"
)
FROZEN_REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SHA256 = (
    "5c39aa346531d8f3cff378361367f7ff236f2c94c0c4bb3db66a28ec8e27d4f5"
)

REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ENERGY_ERROR_THRESHOLD = 1.0e-10
REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_COORDINATE_ERROR_THRESHOLD = 1.0e-8
REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_FORCE_ERROR_THRESHOLD = 1.0e-8
REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ABSOLUTE_FORCE_THRESHOLD = 1.0e-8
REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONSTRAINT_THRESHOLD = 1.0e-10
REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_TRACE_ENERGY_THRESHOLD = 1.0e-10
REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_TRACE_COORDINATE_THRESHOLD = 1.0e-8
REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ENERGY_RELAXATION = 1.0e-10
REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_MAX_OBSERVATION_BYTES = 16 * 1024**2

REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_SCIENTIFIC_BLOCKERS = (
    "successor_observation_is_not_a_production_validation_receipt",
    "frozen_14_case_production_receipt_not_superseded",
    "native_openmm_lbfgs_status_unchanged_rejected_6_of_8",
    "equal_weight_constraint_scope_only",
    "two_cpu_host_reproduction_missing",
    "independent_result_review_missing",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)

_CONSTRAINED_CASE_IDS = {
    "v2_constrained_angle_energy_decrease",
    "v2_constrained_checkpoint_restart_exact",
    "v2_fixed_born_constrained_energy_decrease",
    "v2_fixed_born_checkpoint_restart_exact",
}
_CHECKPOINT_CASE_PAUSES = {
    "v1_checkpoint_restart_exact": 3,
    "v2_constrained_checkpoint_restart_exact": 3,
    "v2_fixed_born_checkpoint_restart_exact": 3,
}
_SOURCE_PATHS = (
    "betelgeuze_engine_v2/offline/reference_minimization_stationarity_successor.py",
    "betelgeuze_engine_v2/physics/reference_constraint_stationarity.py",
    "betelgeuze_engine_v2/physics/reference_constraint_stationarity_independent_oracle.py",
    "betelgeuze_engine_v2/physics/reference_minimization.py",
    "betelgeuze_engine_v2/physics/reference_minimization_independent_oracle.py",
    "betelgeuze_engine_v2/physics/reference_minimization_validation_protocol.py",
    "betelgeuze_engine_v2/physics/reference_minimization_validation_materializer.py",
    "betelgeuze_engine_v2/offline/openmm_reference_constraint_stationarity.py",
)


class ReferenceMinimizationStationaritySuccessorError(RuntimeError):
    """The successor configuration, execution, or observation is invalid."""


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
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ReferenceMinimizationStationaritySuccessorError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return digest


def _finite(value: object, *, name: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferenceMinimizationStationaritySuccessorError(
            f"{name} must be a finite number"
        )
    number = float(value)
    if not math.isfinite(number):
        raise ReferenceMinimizationStationaritySuccessorError(
            f"{name} must be finite"
        )
    if minimum is not None and number < minimum:
        raise ReferenceMinimizationStationaritySuccessorError(
            f"{name} must be >= {minimum}"
        )
    return number


def _configuration_projection() -> dict[str, object]:
    protocol = cpu_minimization_validation_protocol_document()
    case_order = [
        str(row["case_id"]) for row in protocol["case_manifest"]["cases"]
    ]
    return {
        "schema_id": (
            REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SCHEMA_ID
        ),
        "successor_id": (
            "cpu_reference_minimization_stationarity_successor/1.0.0"
        ),
        "parent_frozen_protocol_sha256": (
            FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256
        ),
        "case_order": case_order,
        "case_count": 14,
        "expected_pass_case_count": 8,
        "expected_fail_closed_case_count": 6,
        "denominator": "all_parent_protocol_cases",
        "execution_lanes": {
            "unconstrained_v1_case_ids": [
                case_id
                for case_id in case_order
                if case_id.startswith("v1_")
            ],
            "stationarity_successor_case_ids": [
                case_id
                for case_id in case_order
                if case_id in _CONSTRAINED_CASE_IDS
            ],
            "preserved_fail_closed_case_ids": [
                case_id
                for case_id in case_order
                if case_id not in _CONSTRAINED_CASE_IDS
                and not case_id.startswith("v1_")
            ],
        },
        "checkpoint_case_pauses": dict(_CHECKPOINT_CASE_PAUSES),
        "operational_stationarity_config_sha256": (
            REFERENCE_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256
        ),
        "independent_stationarity_config_sha256": (
            INDEPENDENT_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256
        ),
        "openmm_same_coordinate_config_sha256": (
            FROZEN_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256
        ),
        "thresholds": {
            "final_energy_abs_error_kcal_per_mol": (
                REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ENERGY_ERROR_THRESHOLD
            ),
            "final_coordinate_max_abs_error_angstrom": (
                REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_COORDINATE_ERROR_THRESHOLD
            ),
            "final_force_or_tangent_abs_error_kcal_per_mol_angstrom": (
                REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_FORCE_ERROR_THRESHOLD
            ),
            "absolute_final_force_or_tangent_kcal_per_mol_angstrom": (
                REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ABSOLUTE_FORCE_THRESHOLD
            ),
            "constraint_max_abs_residual_angstrom": (
                REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONSTRAINT_THRESHOLD
            ),
            "trajectory_energy_max_abs_error_kcal_per_mol": (
                REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_TRACE_ENERGY_THRESHOLD
            ),
            "trajectory_coordinate_max_abs_error_angstrom": (
                REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_TRACE_COORDINATE_THRESHOLD
            ),
            "accepted_energy_relaxation_kcal_per_mol": (
                REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ENERGY_RELAXATION
            ),
        },
        "trajectory_policy": {
            "complete_operational_and_independent_traces_required": True,
            "all_rejected_rows_required": True,
            "accepted_state_alignment_required": True,
            "accepted_or_rejected_class_sequence_required": True,
            "exact_armijo_vs_polish_label_required": False,
            "phase_boundary_label_disagreements_reported": True,
        },
        "claim_policy": {
            "frozen_parent_protocol_superseded": False,
            "frozen_production_receipt_superseded": False,
            "native_openmm_result_superseded": False,
            "validation_receipt": False,
            "scientifically_validated": False,
            "claim_safe": False,
        },
    }


def reference_minimization_stationarity_successor_configuration_document() -> (
    dict[str, object]
):
    """Return the preregistered, result-free successor configuration."""

    projection = _configuration_projection()
    digest = _sha256(projection)
    if (
        digest
        != FROZEN_REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SHA256
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor configuration drifted"
        )
    return {**projection, "configuration_sha256": digest}


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _hash_regular_file(path: Path, *, maximum_bytes: int = 512 * 1024**2) -> str:
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or before.st_size > maximum_bytes
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            f"identity path is not a bounded regular file: {path}"
        )
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    after = path.lstat()
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
        raise ReferenceMinimizationStationaritySuccessorError(
            f"identity path changed while hashing: {path}"
        )
    return digest.hexdigest()


def _source_identity_document() -> dict[str, object]:
    root = _repository_root()
    files = [
        {
            "path": relative,
            "sha256": _hash_regular_file(root / relative),
            "size_bytes": (root / relative).stat().st_size,
        }
        for relative in _SOURCE_PATHS
    ]
    projection = {
        "schema_id": (
            "betelgeuze.engine_v2_minimization_stationarity_successor_sources/"
            "1.0.0"
        ),
        "files": files,
    }
    return {**projection, "source_identity_sha256": _sha256(projection)}


def _environment_identity_document() -> dict[str, object]:
    executable = Path(sys.executable).resolve()
    distributions = {}
    for name in ("cryptography", "numpy", "openmm", "torch"):
        try:
            distributions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            distributions[name] = None
    projection = {
        "schema_id": (
            "betelgeuze.engine_v2_minimization_stationarity_successor_environment/"
            "1.0.0"
        ),
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable_sha256": _hash_regular_file(executable),
        },
        "dependencies": distributions,
        "torch": {
            "version": torch.__version__,
            "git_version": torch.version.git_version,
            "cuda_version": torch.version.cuda,
            "deterministic_algorithms_enabled": (
                torch.are_deterministic_algorithms_enabled()
            ),
        },
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "byteorder": sys.byteorder,
        },
        "execution": {
            "device": "cpu",
            "coordinate_dtype": "float64",
        },
    }
    return {**projection, "environment_identity_sha256": _sha256(projection)}


def _coordinates_from_operational(result: object) -> tuple[
    tuple[float, float, float], ...
]:
    coordinates = result.system.coordinates  # type: ignore[attr-defined]
    return tuple(
        tuple(float(value) for value in row)  # type: ignore[misc]
        for row in coordinates[0].tolist()
    )


def _coordinate_hex(
    coordinates: Sequence[Sequence[float]],
) -> list[list[str]]:
    return [[float(value).hex() for value in row] for row in coordinates]


def _coordinates_from_hex_rows(
    value: object,
    *,
    name: str,
) -> tuple[tuple[float, float, float], ...]:
    if not isinstance(value, list) or not value:
        raise ReferenceMinimizationStationaritySuccessorError(
            f"{name} must cover every atom"
        )
    rows = []
    for row in value:
        if not isinstance(row, list) or len(row) != 3:
            raise ReferenceMinimizationStationaritySuccessorError(
                f"{name} must have [atom,3] shape"
            )
        coordinates = []
        for item in row:
            if not isinstance(item, str):
                raise ReferenceMinimizationStationaritySuccessorError(
                    f"{name} must use canonical binary64 hex"
                )
            try:
                coordinate = float.fromhex(item)
            except ValueError as exc:
                raise ReferenceMinimizationStationaritySuccessorError(
                    f"{name} must use canonical binary64 hex"
                ) from exc
            if not math.isfinite(coordinate) or coordinate.hex() != item:
                raise ReferenceMinimizationStationaritySuccessorError(
                    f"{name} must use canonical finite binary64 hex"
                )
            coordinates.append(coordinate)
        rows.append((coordinates[0], coordinates[1], coordinates[2]))
    return tuple(rows)


def _coordinate_error(
    first: Sequence[Sequence[float]],
    second: Sequence[Sequence[float]],
) -> float:
    if len(first) != len(second):
        raise ReferenceMinimizationStationaritySuccessorError(
            "coordinate atom counts differ"
        )
    return max(
        (
            abs(float(left) - float(right))
            for left_row, right_row in zip(first, second)
            for left, right in zip(left_row, right_row)
        ),
        default=0.0,
    )


def _result_sha256(result: object) -> str:
    value = result.to_dict()  # type: ignore[attr-defined]
    return _sha256(value)


def _counts(result: object) -> tuple[int, int, int]:
    accepted = int(result.accepted_iterations)  # type: ignore[attr-defined]
    rejected = int(
        getattr(
            result,
            "rejected_trials",
            getattr(result, "rejected_evaluations", 0),
        )
    )
    evaluations = int(
        getattr(
            result,
            "energy_evaluation_count",
            getattr(result, "evaluation_count", 0),
        )
    )
    return accepted, rejected, evaluations


def _outcome_class(outcome: str) -> str:
    if outcome == "initial":
        return "initial"
    if outcome == "accepted" or outcome.startswith("accepted_"):
        return "accepted"
    if outcome.startswith("rejected_"):
        return "rejected"
    return "terminal"


def _operational_trace_document(result: object) -> dict[str, object]:
    rows = [row.to_dict() for row in result.observations]  # type: ignore[attr-defined]
    accepted_rows = [
        row
        for row in result.observations  # type: ignore[attr-defined]
        if _outcome_class(row.outcome) in {"initial", "accepted"}
    ]
    accepted_energy = [
        float(row.energy_kcal_per_mol)
        for row in accepted_rows
        if row.energy_kcal_per_mol is not None
    ]
    projection = {
        "trace_source": "operational",
        "attempt_count": len(rows),
        "outcome_sequence": [str(row.outcome) for row in result.observations],  # type: ignore[attr-defined]
        "outcome_class_sequence": [
            _outcome_class(str(row.outcome))
            for row in result.observations  # type: ignore[attr-defined]
        ],
        "accepted_energy_trace_kcal_per_mol": accepted_energy,
        "all_observations": rows,
        "all_failure_rows": [
            row
            for row in rows
            if str(row.get("outcome", "")).startswith("rejected_")
            or row.get("failure_code") is not None
        ],
    }
    return {**projection, "trace_sha256": _sha256(projection)}


def _independent_trace_document(result: object) -> dict[str, object]:
    if hasattr(result, "coordinate_trace"):
        observations = result.coordinate_trace  # type: ignore[attr-defined]
        rows = [row.to_dict() for row in observations]
        accepted_energy = list(
            result.accepted_energy_trace_kcal_per_mol  # type: ignore[attr-defined]
        )
    else:
        observations = result.observations  # type: ignore[attr-defined]
        rows = [row.to_dict() for row in observations]
        accepted_energy = list(
            result.accepted_energy_trace_kcal_per_mol  # type: ignore[attr-defined]
        )
    projection = {
        "trace_source": "independent_oracle",
        "attempt_count": len(rows),
        "outcome_sequence": [str(row.outcome) for row in observations],
        "outcome_class_sequence": [
            _outcome_class(str(row.outcome)) for row in observations
        ],
        "accepted_energy_trace_kcal_per_mol": accepted_energy,
        "all_observations": rows,
        "all_failure_rows": [
            row
            for row in rows
            if str(row.get("outcome", "")).startswith("rejected_")
            or row.get("failure_code") is not None
        ],
    }
    return {**projection, "trace_sha256": _sha256(projection)}


def _operational_accepted_points(
    result: object,
) -> tuple[tuple[str, tuple[tuple[float, float, float], ...], float], ...]:
    points = []
    for row in result.observations:  # type: ignore[attr-defined]
        if _outcome_class(str(row.outcome)) not in {"initial", "accepted"}:
            continue
        if row.energy_kcal_per_mol is None:
            raise ReferenceMinimizationStationaritySuccessorError(
                "accepted operational point omitted energy"
            )
        coordinates = tuple(
            tuple(float.fromhex(value) for value in atom_row)  # type: ignore[misc]
            for atom_row in row.coordinates_angstrom_hex
        )
        points.append((str(row.outcome), coordinates, float(row.energy_kcal_per_mol)))
    return tuple(points)


def _independent_accepted_points(
    result: object,
) -> tuple[tuple[str, tuple[tuple[float, float, float], ...], float], ...]:
    observations = (
        result.coordinate_trace  # type: ignore[attr-defined]
        if hasattr(result, "coordinate_trace")
        else result.observations  # type: ignore[attr-defined]
    )
    points = []
    for row in observations:
        if _outcome_class(str(row.outcome)) not in {"initial", "accepted"}:
            continue
        if row.energy_kcal_per_mol is None:
            raise ReferenceMinimizationStationaritySuccessorError(
                "accepted independent point omitted energy"
            )
        coordinates = (
            row.evaluated_coordinates_angstrom
            if hasattr(row, "evaluated_coordinates_angstrom")
            else row.evaluated_coordinates_angstrom
        )
        points.append(
            (
                str(row.outcome),
                tuple(
                    tuple(float(value) for value in atom_row)  # type: ignore[misc]
                    for atom_row in coordinates
                ),
                float(row.energy_kcal_per_mol),
            )
        )
    return tuple(points)


def _trajectory_comparison(
    operational: object,
    independent: object,
    operational_trace: Mapping[str, object],
    independent_trace: Mapping[str, object],
) -> dict[str, object]:
    operational_points = _operational_accepted_points(operational)
    independent_points = _independent_accepted_points(independent)
    aligned = len(operational_points) == len(independent_points)
    coordinate_error = math.inf
    energy_error = math.inf
    phase_disagreements = 0
    if aligned:
        coordinate_error = max(
            (
                _coordinate_error(op[1], oracle[1])
                for op, oracle in zip(operational_points, independent_points)
            ),
            default=0.0,
        )
        energy_error = max(
            (
                abs(op[2] - oracle[2])
                for op, oracle in zip(operational_points, independent_points)
            ),
            default=0.0,
        )
        phase_disagreements = sum(
            op[0] != oracle[0]
            for op, oracle in zip(operational_points, independent_points)
            if _outcome_class(op[0]) == "accepted"
            and _outcome_class(oracle[0]) == "accepted"
        )
    op_counts = _counts(operational)
    independent_counts = _counts(independent)
    class_equal = (
        operational_trace["outcome_class_sequence"]
        == independent_trace["outcome_class_sequence"]
    )
    metric_passes = {
        "accepted_state_count_equal": aligned,
        "accepted_or_rejected_class_sequence_equal": class_equal,
        "accepted_iteration_count_equal": op_counts[0] == independent_counts[0],
        "rejected_count_equal": op_counts[1] == independent_counts[1],
        "energy_force_evaluation_count_equal": (
            op_counts[2] == independent_counts[2]
        ),
        "trajectory_coordinate_error_within_threshold": (
            coordinate_error
            <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_TRACE_COORDINATE_THRESHOLD
        ),
        "trajectory_energy_error_within_threshold": (
            energy_error
            <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_TRACE_ENERGY_THRESHOLD
        ),
    }
    projection = {
        "operational_trace_sha256": operational_trace["trace_sha256"],
        "independent_trace_sha256": independent_trace["trace_sha256"],
        "accepted_state_count": len(operational_points),
        "attempt_count": {
            "operational": operational_trace["attempt_count"],
            "independent": independent_trace["attempt_count"],
        },
        "counts": {
            "operational": {
                "accepted_iterations": op_counts[0],
                "rejected": op_counts[1],
                "energy_force_evaluations": op_counts[2],
            },
            "independent": {
                "accepted_iterations": independent_counts[0],
                "rejected": independent_counts[1],
                "energy_force_evaluations": independent_counts[2],
            },
        },
        "trajectory_coordinate_max_abs_error_angstrom": coordinate_error,
        "trajectory_energy_max_abs_error_kcal_per_mol": energy_error,
        "exact_outcome_sequence_equal": (
            operational_trace["outcome_sequence"]
            == independent_trace["outcome_sequence"]
        ),
        "accepted_phase_boundary_label_disagreement_count": (
            phase_disagreements
        ),
        "metric_passes": metric_passes,
        "passed": all(metric_passes.values()),
    }
    return {**projection, "comparison_sha256": _sha256(projection)}


def _accepted_points_from_trace_document(
    trace: Mapping[str, object],
) -> tuple[tuple[str, tuple[tuple[float, float, float], ...], float], ...]:
    rows = trace.get("all_observations")
    if not isinstance(rows, list):
        raise ReferenceMinimizationStationaritySuccessorError(
            "trace observations must be a list"
        )
    points = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ReferenceMinimizationStationaritySuccessorError(
                "trace observation must be a mapping"
            )
        outcome = row.get("outcome")
        if not isinstance(outcome, str):
            raise ReferenceMinimizationStationaritySuccessorError(
                "trace outcome must be text"
            )
        if _outcome_class(outcome) not in {"initial", "accepted"}:
            continue
        energy = _finite(
            row.get("energy_kcal_per_mol"),
            name="accepted trace energy",
        )
        coordinate_rows = row.get(
            "evaluated_coordinates_angstrom_hex",
            row.get("coordinates_angstrom_hex"),
        )
        if not isinstance(coordinate_rows, list) or not coordinate_rows:
            raise ReferenceMinimizationStationaritySuccessorError(
                "accepted trace coordinates are missing"
            )
        coordinates = _coordinates_from_hex_rows(
            coordinate_rows,
            name="accepted trace coordinates",
        )
        points.append((outcome, coordinates, energy))
    return tuple(points)


def _require_trace_document(
    value: object,
    *,
    expected_source: str,
) -> tuple[
    dict[str, object],
    tuple[tuple[str, tuple[tuple[float, float, float], ...], float], ...],
    tuple[int, int, int],
]:
    if not isinstance(value, Mapping):
        raise ReferenceMinimizationStationaritySuccessorError(
            "trace document must be a mapping"
        )
    trace = dict(value)
    if trace.get("trace_source") != expected_source:
        raise ReferenceMinimizationStationaritySuccessorError(
            "trace source is cross-wired"
        )
    supplied = _require_sha256(
        trace.get("trace_sha256"),
        name="trace identity",
    )
    projection = {
        key: item for key, item in trace.items() if key != "trace_sha256"
    }
    if supplied != _sha256(projection):
        raise ReferenceMinimizationStationaritySuccessorError(
            "trace digest mismatch"
        )
    rows = trace.get("all_observations")
    if not isinstance(rows, list) or not all(
        isinstance(row, Mapping) for row in rows
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            "trace observations are invalid"
        )
    if any(
        not isinstance(row.get("outcome"), str)
        or _outcome_class(row["outcome"]) == "terminal"
        for row in rows
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            "trace outcome ledger is invalid"
        )
    outcomes = [str(row["outcome"]) for row in rows]
    classes = [_outcome_class(outcome) for outcome in outcomes]
    failure_rows = [
        row
        for row in rows
        if str(row.get("outcome", "")).startswith("rejected_")
        or row.get("failure_code") is not None
    ]
    points = _accepted_points_from_trace_document(trace)
    if (
        trace.get("attempt_count") != len(rows)
        or trace.get("outcome_sequence") != outcomes
        or trace.get("outcome_class_sequence") != classes
        or trace.get("all_failure_rows") != failure_rows
        or trace.get("accepted_energy_trace_kcal_per_mol")
        != [point[2] for point in points]
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            "trace derived ledger mismatch"
        )
    counts = (
        max(0, len(points) - 1),
        sum(outcome == "rejected" for outcome in classes),
        sum(row.get("energy_kcal_per_mol") is not None for row in rows),
    )
    return trace, points, counts


def _maximum_accepted_energy_increase(result: object) -> float:
    trace = [
        row.energy_kcal_per_mol
        for row in result.observations  # type: ignore[attr-defined]
        if _outcome_class(str(row.outcome)) in {"initial", "accepted"}
        and row.energy_kcal_per_mol is not None
    ]
    return max(
        (float(next_value) - float(value) for value, next_value in zip(trace, trace[1:])),
        default=0.0,
    )


def _run_operational_pass_case(
    case: object,
    *,
    pause: int | None = None,
    checkpoint: object | None = None,
) -> object:
    if case.case_id in _CONSTRAINED_CASE_IDS:  # type: ignore[attr-defined]
        return minimize_reference_constraint_stationarity(
            case.system,  # type: ignore[attr-defined]
            case.v2_parameters,  # type: ignore[attr-defined]
            ReferenceConstraintStationarityConfig(),
            solvation_parameters=case.solvation_parameters,  # type: ignore[attr-defined]
            pause_after_accepted_iterations=pause,
            checkpoint=checkpoint,
        )
    return minimize_reference_force_field(
        case.system,  # type: ignore[attr-defined]
        case.base_parameters,  # type: ignore[attr-defined]
        case.minimization_config,  # type: ignore[attr-defined]
        pause_after_accepted_iterations=pause,
        checkpoint=checkpoint,
    )


def _run_independent_pass_case(
    case: object,
    *,
    pause: int | None = None,
    checkpoint: object | None = None,
) -> object:
    source = replace(
        case.independent_oracle_input,  # type: ignore[attr-defined]
        pause_after_accepted_iterations=None,
    )
    if case.case_id in _CONSTRAINED_CASE_IDS:  # type: ignore[attr-defined]
        return evaluate_independent_constraint_stationarity(
            source,
            IndependentConstraintStationarityConfig(),
            pause_after_accepted_iterations=pause,
            checkpoint=checkpoint,
        )
    source = replace(source, pause_after_accepted_iterations=pause)
    return evaluate_independent_minimization_oracle(
        source,
        checkpoint=checkpoint,
    )


def _checkpoint_evidence(
    case: object,
    operational: object,
    independent: object,
) -> dict[str, object]:
    pause = _CHECKPOINT_CASE_PAUSES.get(case.case_id)  # type: ignore[attr-defined]
    if pause is None:
        return {
            "required": False,
            "pause_after_accepted_iterations": None,
            "operational": None,
            "independent": None,
            "passed": True,
        }
    paused_operational = _run_operational_pass_case(case, pause=pause)
    resumed_operational = _run_operational_pass_case(
        case,
        checkpoint=paused_operational.checkpoint,  # type: ignore[attr-defined]
    )
    paused_independent = _run_independent_pass_case(case, pause=pause)
    resumed_independent = _run_independent_pass_case(
        case,
        checkpoint=paused_independent.checkpoint,  # type: ignore[attr-defined]
    )
    operational_equal = (
        resumed_operational.to_dict()  # type: ignore[attr-defined]
        == operational.to_dict()  # type: ignore[attr-defined]
        and resumed_operational.checkpoint.to_dict()  # type: ignore[attr-defined]
        == operational.checkpoint.to_dict()  # type: ignore[attr-defined]
    )
    independent_equal = (
        resumed_independent.to_dict()  # type: ignore[attr-defined]
        == independent.to_dict()  # type: ignore[attr-defined]
        and resumed_independent.checkpoint.to_dict()  # type: ignore[attr-defined]
        == independent.checkpoint.to_dict()  # type: ignore[attr-defined]
    )
    return {
        "required": True,
        "pause_after_accepted_iterations": pause,
        "operational": {
            "paused_status": paused_operational.status,  # type: ignore[attr-defined]
            "paused_checkpoint_sha256": (
                paused_operational.checkpoint.checkpoint_sha256  # type: ignore[attr-defined]
            ),
            "uninterrupted_result_sha256": _result_sha256(operational),
            "resumed_result_sha256": _result_sha256(resumed_operational),
            "uninterrupted_checkpoint_sha256": (
                operational.checkpoint.checkpoint_sha256  # type: ignore[attr-defined]
            ),
            "resumed_checkpoint_sha256": (
                resumed_operational.checkpoint.checkpoint_sha256  # type: ignore[attr-defined]
            ),
            "exact_result_and_checkpoint_equality": operational_equal,
        },
        "independent": {
            "paused_status": paused_independent.status,  # type: ignore[attr-defined]
            "paused_checkpoint_sha256": (
                paused_independent.checkpoint.checkpoint_sha256  # type: ignore[attr-defined]
            ),
            "uninterrupted_result_sha256": _result_sha256(independent),
            "resumed_result_sha256": _result_sha256(resumed_independent),
            "uninterrupted_checkpoint_sha256": (
                independent.checkpoint.checkpoint_sha256  # type: ignore[attr-defined]
            ),
            "resumed_checkpoint_sha256": (
                resumed_independent.checkpoint.checkpoint_sha256  # type: ignore[attr-defined]
            ),
            "exact_result_and_checkpoint_equality": independent_equal,
        },
        "passed": operational_equal and independent_equal,
    }


def _pass_case_row(ordinal: int, protocol_row: Mapping[str, Any]) -> dict[str, object]:
    case = materialize_frozen_cpu_minimization_validation_case(
        str(protocol_row["case_id"])
    )
    operational = _run_operational_pass_case(case)
    independent = _run_independent_pass_case(case)
    operational_trace = _operational_trace_document(operational)
    independent_trace = _independent_trace_document(independent)
    trajectory = _trajectory_comparison(
        operational,
        independent,
        operational_trace,
        independent_trace,
    )
    operational_coordinates = _coordinates_from_operational(operational)
    independent_coordinates = independent.final_coordinates_angstrom  # type: ignore[attr-defined]
    final_coordinate_error = _coordinate_error(
        operational_coordinates,
        independent_coordinates,
    )
    final_energy_error = abs(
        float(operational.final_energy_kcal_per_mol)  # type: ignore[attr-defined]
        - float(independent.final_energy_kcal_per_mol)  # type: ignore[attr-defined]
    )
    constrained = case.case_id in _CONSTRAINED_CASE_IDS
    operational_force = float(
        operational.final_max_tangent_force_kcal_per_mol_angstrom  # type: ignore[attr-defined]
        if constrained
        else operational.final_max_force_kcal_per_mol_angstrom  # type: ignore[attr-defined]
    )
    independent_force = float(
        independent.final_max_tangent_force_kcal_per_mol_angstrom  # type: ignore[attr-defined]
        if constrained
        else independent.final_max_force_kcal_per_mol_angstrom  # type: ignore[attr-defined]
    )
    constraint_residual = (
        float(operational.final_max_constraint_residual_angstrom)  # type: ignore[attr-defined]
        if constrained
        else 0.0
    )
    energy_decrease = float(
        operational.initial_energy_kcal_per_mol  # type: ignore[attr-defined]
        - operational.final_energy_kcal_per_mol  # type: ignore[attr-defined]
    )
    maximum_accepted_energy_increase = _maximum_accepted_energy_increase(
        operational
    )
    checkpoint = _checkpoint_evidence(case, operational, independent)
    initially_converged = case.case_id == "v1_initially_converged_noop"
    absolute_stationarity_required = constrained or initially_converged
    metric_passes = {
        "operational_terminal_status_expected": (
            operational.status == "converged"  # type: ignore[attr-defined]
            if absolute_stationarity_required
            else operational.status in {"converged", "max_iterations_reached"}  # type: ignore[attr-defined]
        ),
        "independent_terminal_status_expected": (
            independent.status == "converged"  # type: ignore[attr-defined]
            if absolute_stationarity_required
            else independent.status in {"converged", "max_iterations_reached"}  # type: ignore[attr-defined]
        ),
        "status_and_failure_code_equal": (
            operational.status == independent.status  # type: ignore[attr-defined]
            and operational.failure_code == independent.failure_code  # type: ignore[attr-defined]
        ),
        "final_energy_error_within_threshold": (
            final_energy_error
            <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ENERGY_ERROR_THRESHOLD
        ),
        "final_coordinate_error_within_threshold": (
            final_coordinate_error
            <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_COORDINATE_ERROR_THRESHOLD
        ),
        "final_force_or_tangent_error_within_threshold": (
            abs(operational_force - independent_force)
            <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_FORCE_ERROR_THRESHOLD
        ),
        "absolute_operational_force_or_tangent_within_threshold": (
            not absolute_stationarity_required
            or operational_force
            <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ABSOLUTE_FORCE_THRESHOLD
        ),
        "absolute_independent_force_or_tangent_within_threshold": (
            not absolute_stationarity_required
            or independent_force
            <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ABSOLUTE_FORCE_THRESHOLD
        ),
        "constraint_residual_within_threshold": (
            constraint_residual
            <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONSTRAINT_THRESHOLD
        ),
        "accepted_energy_relaxation_within_threshold": (
            maximum_accepted_energy_increase
            <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ENERGY_RELAXATION
        ),
        "required_energy_decrease": (
            energy_decrease >= 1.0e-8
            if not initially_converged
            else energy_decrease >= 0.0
        ),
        "trajectory_comparison_passed": bool(trajectory["passed"]),
        "checkpoint_restart_passed": bool(checkpoint["passed"]),
        "all_failure_rows_retained": (
            len(operational_trace["all_failure_rows"])
            == _counts(operational)[1]
            and len(independent_trace["all_failure_rows"])
            == _counts(independent)[1]
        ),
    }
    projection = {
        "ordinal": ordinal,
        "case_id": case.case_id,
        "lane": (
            "constraint_stationarity_successor"
            if constrained
            else "frozen_unconstrained_v1"
        ),
        "case_input_sha256": case.case_input_sha256,
        "runtime_input_sha256": case.runtime_input_sha256,
        "independent_input_sha256": (
            case.independent_oracle_input.input_sha256
        ),
        "expected_outcome": "pass",
        "observed_status": str(operational.status),  # type: ignore[attr-defined]
        "independent_status": str(independent.status),  # type: ignore[attr-defined]
        "expected_error_code": None,
        "observed_error_code": operational.failure_code,  # type: ignore[attr-defined]
        "independent_error_code": independent.failure_code,  # type: ignore[attr-defined]
        "operational_result_sha256": _result_sha256(operational),
        "independent_result_sha256": _result_sha256(independent),
        "final_coordinates": {
            "operational_angstrom_hex": _coordinate_hex(
                operational_coordinates
            ),
            "independent_angstrom_hex": _coordinate_hex(
                independent_coordinates
            ),
            "max_abs_error_angstrom": final_coordinate_error,
        },
        "metrics": {
            "initial_energy_kcal_per_mol": float(
                operational.initial_energy_kcal_per_mol  # type: ignore[attr-defined]
            ),
            "final_energy_kcal_per_mol": float(
                operational.final_energy_kcal_per_mol  # type: ignore[attr-defined]
            ),
            "energy_decrease_kcal_per_mol": energy_decrease,
            "independent_final_energy_kcal_per_mol": float(
                independent.final_energy_kcal_per_mol  # type: ignore[attr-defined]
            ),
            "final_energy_abs_error_kcal_per_mol": final_energy_error,
            "absolute_operational_final_force_or_tangent_kcal_per_mol_angstrom": (
                operational_force
            ),
            "absolute_independent_final_force_or_tangent_kcal_per_mol_angstrom": (
                independent_force
            ),
            "absolute_stationarity_threshold_applicable": (
                absolute_stationarity_required
            ),
            "final_force_or_tangent_abs_error_kcal_per_mol_angstrom": abs(
                operational_force - independent_force
            ),
            "constraint_max_abs_residual_angstrom": constraint_residual,
            "maximum_accepted_energy_increase_kcal_per_mol": (
                maximum_accepted_energy_increase
            ),
            "accepted_iterations": _counts(operational)[0],
            "rejected_count": _counts(operational)[1],
            "energy_force_evaluation_count": _counts(operational)[2],
        },
        "operational_trace": operational_trace,
        "independent_trace": independent_trace,
        "trajectory_comparison": trajectory,
        "checkpoint_restart": checkpoint,
        "metric_passes": metric_passes,
        "case_passed": all(metric_passes.values()),
    }
    return {**projection, "case_observation_sha256": _sha256(projection)}


def _fail_closed_case_row(
    ordinal: int,
    protocol_row: Mapping[str, Any],
) -> dict[str, object]:
    case = materialize_frozen_cpu_minimization_validation_case(
        str(protocol_row["case_id"])
    )
    result = evaluate_independent_minimization_oracle(
        case.independent_oracle_input
    )
    trace = _independent_trace_document(result)
    expected_code = case.expected_error_code
    passed = (
        result.status == "fail_closed"
        and result.failure_code == expected_code
    )
    failure_rows = [
        {
            "source": "independent_oracle_terminal",
            "failure_code": result.failure_code,
        },
        *[
            {"source": "independent_oracle_trace", **row}
            for row in trace["all_failure_rows"]  # type: ignore[union-attr]
        ],
    ]
    projection = {
        "ordinal": ordinal,
        "case_id": case.case_id,
        "lane": "preserved_fail_closed",
        "case_input_sha256": case.case_input_sha256,
        "runtime_input_sha256": case.runtime_input_sha256,
        "independent_input_sha256": (
            case.independent_oracle_input.input_sha256
        ),
        "expected_outcome": "fail_closed",
        "observed_status": result.status,
        "independent_status": result.status,
        "expected_error_code": expected_code,
        "observed_error_code": result.failure_code,
        "independent_error_code": result.failure_code,
        "operational_result_sha256": None,
        "independent_result_sha256": result.result_sha256,
        "metrics": {
            "accepted_iterations": result.accepted_iterations,
            "rejected_count": result.rejected_evaluations,
            "energy_force_evaluation_count": result.evaluation_count,
        },
        "operational_trace": {
            "trace_source": "operational",
            "trace_state": "not_evaluated_expected_fail_closed",
            "attempt_count": 0,
            "all_observations": [],
            "all_failure_rows": [],
        },
        "independent_trace": trace,
        "all_failure_rows": failure_rows,
        "metric_passes": {
            "status_is_fail_closed": result.status == "fail_closed",
            "exact_failure_disposition": result.failure_code == expected_code,
            "terminal_failure_row_retained": len(failure_rows) >= 1,
        },
        "case_passed": passed,
    }
    return {**projection, "case_observation_sha256": _sha256(projection)}


def build_reference_minimization_stationarity_successor_observation(
    *,
    openmm_receipt: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Execute all 14 successor rows and return a claim-closed observation."""

    configuration = (
        reference_minimization_stationarity_successor_configuration_document()
    )
    protocol = cpu_minimization_validation_protocol_document()
    rows = []
    for ordinal, protocol_row in enumerate(
        protocol["case_manifest"]["cases"],
        start=1,
    ):
        if protocol_row["expected_outcome"] == "pass":
            rows.append(_pass_case_row(ordinal, protocol_row))
        else:
            rows.append(_fail_closed_case_row(ordinal, protocol_row))
    openmm = (
        build_openmm_reference_constraint_stationarity_receipt()
        if openmm_receipt is None
        else dict(openmm_receipt)
    )
    openmm = require_openmm_reference_constraint_stationarity_receipt(openmm)
    passed_count = sum(bool(row["case_passed"]) for row in rows)
    pass_rows = [row for row in rows if row["expected_outcome"] == "pass"]
    fail_closed_rows = [
        row for row in rows if row["expected_outcome"] == "fail_closed"
    ]
    projection = {
        "schema_id": (
            REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_OBSERVATION_SCHEMA_ID
        ),
        "configuration": configuration,
        "source_identity": _source_identity_document(),
        "environment_identity": _environment_identity_document(),
        "case_rows": rows,
        "openmm_same_coordinate_candidate_receipt": openmm,
        "summary": {
            "case_denominator": len(rows),
            "case_passed_count": passed_count,
            "case_failed_count": len(rows) - passed_count,
            "expected_pass_denominator": len(pass_rows),
            "expected_pass_passed_count": sum(
                bool(row["case_passed"]) for row in pass_rows
            ),
            "expected_fail_closed_denominator": len(fail_closed_rows),
            "expected_fail_closed_exact_disposition_count": sum(
                bool(row["case_passed"]) for row in fail_closed_rows
            ),
            "checkpoint_case_denominator": len(_CHECKPOINT_CASE_PAUSES),
            "checkpoint_exact_count": sum(
                bool(row["checkpoint_restart"]["passed"])
                for row in pass_rows
                if row["case_id"] in _CHECKPOINT_CASE_PAUSES
            ),
            "all_failure_rows_retained": all(
                (
                    bool(row["metric_passes"]["all_failure_rows_retained"])
                    if row["expected_outcome"] == "pass"
                    else len(row["all_failure_rows"]) >= 1
                )
                for row in rows
            ),
            "openmm_candidate_case_denominator": (
                openmm["summary"]["candidate_case_denominator"]  # type: ignore[index]
            ),
            "openmm_candidate_case_passed_count": (
                openmm["summary"]["candidate_case_passed_count"]  # type: ignore[index]
            ),
            "native_openmm_lbfgs_invoked": False,
            "native_openmm_lbfgs_status": "unchanged_rejected_6_of_8",
            "frozen_14_case_production_receipt_superseded": False,
            "s0_complete": False,
        },
        "candidate_observation": True,
        "validation_receipt": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "scientific_blockers": list(
            REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_SCIENTIFIC_BLOCKERS
        ),
    }
    return {**projection, "observation_sha256": _sha256(projection)}


def require_reference_minimization_stationarity_successor_observation(
    value: object,
    *,
    verify_current_identity: bool = True,
) -> dict[str, object]:
    """Verify identity, all-case accounting, thresholds, and claim closure."""

    if not isinstance(value, Mapping):
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor observation must be a mapping"
        )
    document = dict(value)
    supplied = _require_sha256(
        document.get("observation_sha256"),
        name="successor observation identity",
    )
    projection = {
        key: item
        for key, item in document.items()
        if key != "observation_sha256"
    }
    if supplied != _sha256(projection):
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor observation digest mismatch"
        )
    if (
        document.get("schema_id")
        != REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_OBSERVATION_SCHEMA_ID
        or document.get("configuration")
        != reference_minimization_stationarity_successor_configuration_document()
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor schema or configuration mismatch"
        )
    source = document.get("source_identity")
    environment = document.get("environment_identity")
    if (
        not isinstance(source, Mapping)
        or source.get("source_identity_sha256")
        != _sha256(
            {
                key: item
                for key, item in source.items()
                if key != "source_identity_sha256"
            }
        )
        or not isinstance(environment, Mapping)
        or environment.get("environment_identity_sha256")
        != _sha256(
            {
                key: item
                for key, item in environment.items()
                if key != "environment_identity_sha256"
            }
        )
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor source or environment identity is invalid"
        )
    if verify_current_identity and (
        source != _source_identity_document()
        or environment != _environment_identity_document()
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor identity does not match current source and environment"
        )
    rows = document.get("case_rows")
    summary = document.get("summary")
    protocol_rows = cpu_minimization_validation_protocol_document()[
        "case_manifest"
    ]["cases"]
    protocol_ids = [row["case_id"] for row in protocol_rows]
    if (
        not isinstance(rows, list)
        or len(rows) != 14
        or [row.get("case_id") for row in rows] != protocol_ids
        or not all(isinstance(row, Mapping) for row in rows)
        or not isinstance(summary, Mapping)
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor all-case denominator is invalid"
        )
    for ordinal, (row, protocol_row) in enumerate(
        zip(rows, protocol_rows),
        start=1,
    ):
        case_id = str(protocol_row["case_id"])
        case_digest = _require_sha256(
            row.get("case_observation_sha256"),
            name=f"{case_id} observation identity",
        )
        case_projection = {
            key: item
            for key, item in row.items()
            if key != "case_observation_sha256"
        }
        if case_digest != _sha256(case_projection):
            raise ReferenceMinimizationStationaritySuccessorError(
                f"successor case digest mismatch: {case_id}"
            )
        if (
            row.get("ordinal") != ordinal
            or row.get("case_id") != case_id
            or row.get("case_input_sha256") != protocol_row["input_sha256"]
            or row.get("expected_outcome") != protocol_row["expected_outcome"]
        ):
            raise ReferenceMinimizationStationaritySuccessorError(
                f"successor case identity is cross-wired: {case_id}"
            )
        if row.get("case_passed") is not True:
            raise ReferenceMinimizationStationaritySuccessorError(
                f"successor case did not pass: {case_id}"
            )
        passes = row.get("metric_passes")
        if not isinstance(passes, Mapping) or not all(
            bool(item) for item in passes.values()
        ):
            raise ReferenceMinimizationStationaritySuccessorError(
                f"successor metrics did not pass: {case_id}"
            )
        if protocol_row["expected_outcome"] == "fail_closed":
            expected_code = protocol_row["expected_error_code"]
            independent_trace, _, trace_counts = _require_trace_document(
                row.get("independent_trace"),
                expected_source="independent_oracle",
            )
            metrics = row.get("metrics")
            failure_rows = row.get("all_failure_rows")
            operational_trace = row.get("operational_trace")
            expected_passes = {
                "status_is_fail_closed": True,
                "exact_failure_disposition": True,
                "terminal_failure_row_retained": True,
            }
            if (
                row.get("lane") != "preserved_fail_closed"
                or row.get("observed_status") != "fail_closed"
                or row.get("independent_status") != "fail_closed"
                or row.get("expected_error_code") != expected_code
                or row.get("observed_error_code") != expected_code
                or row.get("independent_error_code") != expected_code
                or row.get("operational_result_sha256") is not None
                or _require_sha256(
                    row.get("independent_result_sha256"),
                    name=f"{case_id} independent result identity",
                )
                != row.get("independent_result_sha256")
                or not isinstance(metrics, Mapping)
                or metrics.get("accepted_iterations") != trace_counts[0]
                or metrics.get("rejected_count") != trace_counts[1]
                or metrics.get("energy_force_evaluation_count")
                != trace_counts[2]
                or not isinstance(failure_rows, list)
                or not failure_rows
                or failure_rows[0]
                != {
                    "source": "independent_oracle_terminal",
                    "failure_code": expected_code,
                }
                or failure_rows[1:]
                != [
                    {"source": "independent_oracle_trace", **failure}
                    for failure in independent_trace["all_failure_rows"]  # type: ignore[union-attr]
                ]
                or operational_trace
                != {
                    "trace_source": "operational",
                    "trace_state": "not_evaluated_expected_fail_closed",
                    "attempt_count": 0,
                    "all_observations": [],
                    "all_failure_rows": [],
                }
                or dict(passes) != expected_passes
            ):
                raise ReferenceMinimizationStationaritySuccessorError(
                    f"fail-closed successor row is inconsistent: {case_id}"
                )
            continue

        metrics = row.get("metrics")
        final_coordinates = row.get("final_coordinates")
        trajectory = row.get("trajectory_comparison")
        checkpoint = row.get("checkpoint_restart")
        if (
            not isinstance(metrics, Mapping)
            or not isinstance(final_coordinates, Mapping)
            or not isinstance(trajectory, Mapping)
            or not isinstance(checkpoint, Mapping)
        ):
            raise ReferenceMinimizationStationaritySuccessorError(
                f"passing successor row is incomplete: {case_id}"
            )
        operational_trace, operational_points, operational_counts = (
            _require_trace_document(
                row.get("operational_trace"),
                expected_source="operational",
            )
        )
        independent_trace, independent_points, independent_counts = (
            _require_trace_document(
                row.get("independent_trace"),
                expected_source="independent_oracle",
            )
        )
        aligned = len(operational_points) == len(independent_points)
        if not aligned:
            raise ReferenceMinimizationStationaritySuccessorError(
                f"successor accepted trajectory is unaligned: {case_id}"
            )
        trajectory_coordinate_error = max(
            (
                _coordinate_error(left[1], right[1])
                for left, right in zip(
                    operational_points,
                    independent_points,
                )
            ),
            default=0.0,
        )
        trajectory_energy_error = max(
            (
                abs(left[2] - right[2])
                for left, right in zip(
                    operational_points,
                    independent_points,
                )
            ),
            default=0.0,
        )
        phase_disagreements = sum(
            left[0] != right[0]
            for left, right in zip(operational_points, independent_points)
            if _outcome_class(left[0]) == "accepted"
            and _outcome_class(right[0]) == "accepted"
        )
        trajectory_passes = {
            "accepted_state_count_equal": True,
            "accepted_or_rejected_class_sequence_equal": (
                operational_trace["outcome_class_sequence"]
                == independent_trace["outcome_class_sequence"]
            ),
            "accepted_iteration_count_equal": (
                operational_counts[0] == independent_counts[0]
            ),
            "rejected_count_equal": (
                operational_counts[1] == independent_counts[1]
            ),
            "energy_force_evaluation_count_equal": (
                operational_counts[2] == independent_counts[2]
            ),
            "trajectory_coordinate_error_within_threshold": (
                trajectory_coordinate_error
                <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_TRACE_COORDINATE_THRESHOLD
            ),
            "trajectory_energy_error_within_threshold": (
                trajectory_energy_error
                <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_TRACE_ENERGY_THRESHOLD
            ),
        }
        trajectory_projection = {
            key: item
            for key, item in trajectory.items()
            if key != "comparison_sha256"
        }
        if (
            _require_sha256(
                trajectory.get("comparison_sha256"),
                name=f"{case_id} trajectory comparison identity",
            )
            != _sha256(trajectory_projection)
            or trajectory.get("operational_trace_sha256")
            != operational_trace["trace_sha256"]
            or trajectory.get("independent_trace_sha256")
            != independent_trace["trace_sha256"]
            or trajectory.get("accepted_state_count")
            != len(operational_points)
            or trajectory.get("attempt_count")
            != {
                "operational": operational_trace["attempt_count"],
                "independent": independent_trace["attempt_count"],
            }
            or trajectory.get("counts")
            != {
                "operational": {
                    "accepted_iterations": operational_counts[0],
                    "rejected": operational_counts[1],
                    "energy_force_evaluations": operational_counts[2],
                },
                "independent": {
                    "accepted_iterations": independent_counts[0],
                    "rejected": independent_counts[1],
                    "energy_force_evaluations": independent_counts[2],
                },
            }
            or trajectory.get(
                "trajectory_coordinate_max_abs_error_angstrom"
            )
            != trajectory_coordinate_error
            or trajectory.get(
                "trajectory_energy_max_abs_error_kcal_per_mol"
            )
            != trajectory_energy_error
            or trajectory.get("exact_outcome_sequence_equal")
            != (
                operational_trace["outcome_sequence"]
                == independent_trace["outcome_sequence"]
            )
            or trajectory.get(
                "accepted_phase_boundary_label_disagreement_count"
            )
            != phase_disagreements
            or trajectory.get("metric_passes") != trajectory_passes
            or trajectory.get("passed") is not all(
                trajectory_passes.values()
            )
        ):
            raise ReferenceMinimizationStationaritySuccessorError(
                f"successor trajectory comparison is inconsistent: {case_id}"
            )

        operational_final_coordinates = _coordinates_from_hex_rows(
            final_coordinates.get("operational_angstrom_hex"),
            name=f"{case_id} operational final coordinates",
        )
        independent_final_coordinates = _coordinates_from_hex_rows(
            final_coordinates.get("independent_angstrom_hex"),
            name=f"{case_id} independent final coordinates",
        )
        final_coordinate_error = _coordinate_error(
            operational_final_coordinates,
            independent_final_coordinates,
        )
        initial_energy = _finite(
            metrics.get("initial_energy_kcal_per_mol"),
            name=f"{case_id} initial energy",
        )
        final_energy = _finite(
            metrics.get("final_energy_kcal_per_mol"),
            name=f"{case_id} final energy",
        )
        independent_final_energy = _finite(
            metrics.get("independent_final_energy_kcal_per_mol"),
            name=f"{case_id} independent final energy",
        )
        operational_force = _finite(
            metrics.get(
                "absolute_operational_final_force_or_tangent_kcal_per_mol_angstrom"
            ),
            name=f"{case_id} operational final force",
            minimum=0.0,
        )
        independent_force = _finite(
            metrics.get(
                "absolute_independent_final_force_or_tangent_kcal_per_mol_angstrom"
            ),
            name=f"{case_id} independent final force",
            minimum=0.0,
        )
        constraint_residual = _finite(
            metrics.get("constraint_max_abs_residual_angstrom"),
            name=f"{case_id} constraint residual",
            minimum=0.0,
        )
        constrained = case_id in _CONSTRAINED_CASE_IDS
        initially_converged = case_id == "v1_initially_converged_noop"
        absolute_stationarity_required = constrained or initially_converged
        accepted_energy = operational_trace[
            "accepted_energy_trace_kcal_per_mol"
        ]
        if not isinstance(accepted_energy, list):
            raise ReferenceMinimizationStationaritySuccessorError(
                f"successor accepted energy trace is invalid: {case_id}"
            )
        maximum_energy_increase = max(
            (
                float(next_value) - float(current)
                for current, next_value in zip(
                    accepted_energy,
                    accepted_energy[1:],
                )
            ),
            default=0.0,
        )
        energy_decrease = initial_energy - final_energy
        expected_passes = {
            "operational_terminal_status_expected": (
                row.get("observed_status") == "converged"
                if absolute_stationarity_required
                else row.get("observed_status")
                in {"converged", "max_iterations_reached"}
            ),
            "independent_terminal_status_expected": (
                row.get("independent_status") == "converged"
                if absolute_stationarity_required
                else row.get("independent_status")
                in {"converged", "max_iterations_reached"}
            ),
            "status_and_failure_code_equal": (
                row.get("observed_status") == row.get("independent_status")
                and row.get("observed_error_code")
                == row.get("independent_error_code")
            ),
            "final_energy_error_within_threshold": (
                abs(final_energy - independent_final_energy)
                <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ENERGY_ERROR_THRESHOLD
            ),
            "final_coordinate_error_within_threshold": (
                final_coordinate_error
                <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_COORDINATE_ERROR_THRESHOLD
            ),
            "final_force_or_tangent_error_within_threshold": (
                abs(operational_force - independent_force)
                <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_FORCE_ERROR_THRESHOLD
            ),
            "absolute_operational_force_or_tangent_within_threshold": (
                not absolute_stationarity_required
                or operational_force
                <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ABSOLUTE_FORCE_THRESHOLD
            ),
            "absolute_independent_force_or_tangent_within_threshold": (
                not absolute_stationarity_required
                or independent_force
                <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ABSOLUTE_FORCE_THRESHOLD
            ),
            "constraint_residual_within_threshold": (
                constraint_residual
                <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONSTRAINT_THRESHOLD
            ),
            "accepted_energy_relaxation_within_threshold": (
                maximum_energy_increase
                <= REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_ENERGY_RELAXATION
            ),
            "required_energy_decrease": (
                energy_decrease >= 1.0e-8
                if not initially_converged
                else energy_decrease >= 0.0
            ),
            "trajectory_comparison_passed": all(
                trajectory_passes.values()
            ),
            "checkpoint_restart_passed": checkpoint.get("passed") is True,
            "all_failure_rows_retained": (
                len(operational_trace["all_failure_rows"])
                == operational_counts[1]
                and len(independent_trace["all_failure_rows"])
                == independent_counts[1]
            ),
        }
        checkpoint_required = case_id in _CHECKPOINT_CASE_PAUSES
        if checkpoint_required:
            operational_checkpoint = checkpoint.get("operational")
            independent_checkpoint = checkpoint.get("independent")
            checkpoint_valid = (
                checkpoint.get("required") is True
                and checkpoint.get("passed") is True
                and checkpoint.get("pause_after_accepted_iterations")
                == _CHECKPOINT_CASE_PAUSES[case_id]
                and isinstance(operational_checkpoint, Mapping)
                and isinstance(independent_checkpoint, Mapping)
                and operational_checkpoint.get("paused_status")
                == "checkpointed"
                and independent_checkpoint.get("paused_status")
                == "checkpointed"
                and operational_checkpoint.get(
                    "exact_result_and_checkpoint_equality"
                )
                is True
                and independent_checkpoint.get(
                    "exact_result_and_checkpoint_equality"
                )
                is True
                and operational_checkpoint.get(
                    "uninterrupted_result_sha256"
                )
                == operational_checkpoint.get("resumed_result_sha256")
                == row.get("operational_result_sha256")
                and operational_checkpoint.get(
                    "uninterrupted_checkpoint_sha256"
                )
                == operational_checkpoint.get("resumed_checkpoint_sha256")
                and independent_checkpoint.get(
                    "uninterrupted_result_sha256"
                )
                == independent_checkpoint.get("resumed_result_sha256")
                == row.get("independent_result_sha256")
                and independent_checkpoint.get(
                    "uninterrupted_checkpoint_sha256"
                )
                == independent_checkpoint.get("resumed_checkpoint_sha256")
            )
        else:
            checkpoint_valid = checkpoint == {
                "required": False,
                "pause_after_accepted_iterations": None,
                "operational": None,
                "independent": None,
                "passed": True,
            }
        if (
            not checkpoint_valid
            or row.get("lane")
            != (
                "constraint_stationarity_successor"
                if constrained
                else "frozen_unconstrained_v1"
            )
            or row.get("expected_error_code") is not None
            or row.get("observed_error_code")
            not in {None, "maximum_iteration_budget_exhausted"}
            or row.get("independent_error_code")
            not in {None, "maximum_iteration_budget_exhausted"}
            or _require_sha256(
                row.get("operational_result_sha256"),
                name=f"{case_id} operational result identity",
            )
            != row.get("operational_result_sha256")
            or _require_sha256(
                row.get("independent_result_sha256"),
                name=f"{case_id} independent result identity",
            )
            != row.get("independent_result_sha256")
            or operational_final_coordinates
            != operational_points[-1][1]
            or independent_final_coordinates
            != independent_points[-1][1]
            or final_coordinates.get("max_abs_error_angstrom")
            != final_coordinate_error
            or metrics.get("energy_decrease_kcal_per_mol")
            != energy_decrease
            or metrics.get("final_energy_abs_error_kcal_per_mol")
            != abs(final_energy - independent_final_energy)
            or metrics.get(
                "final_force_or_tangent_abs_error_kcal_per_mol_angstrom"
            )
            != abs(operational_force - independent_force)
            or metrics.get("absolute_stationarity_threshold_applicable")
            is not absolute_stationarity_required
            or metrics.get(
                "maximum_accepted_energy_increase_kcal_per_mol"
            )
            != maximum_energy_increase
            or metrics.get("accepted_iterations")
            != operational_counts[0]
            or metrics.get("rejected_count") != operational_counts[1]
            or metrics.get("energy_force_evaluation_count")
            != operational_counts[2]
            or dict(passes) != expected_passes
        ):
            raise ReferenceMinimizationStationaritySuccessorError(
                f"passing successor row is inconsistent: {case_id}"
            )
    if (
        summary.get("case_denominator") != 14
        or summary.get("case_passed_count") != 14
        or summary.get("case_failed_count") != 0
        or summary.get("expected_pass_denominator") != 8
        or summary.get("expected_pass_passed_count") != 8
        or summary.get("expected_fail_closed_denominator") != 6
        or summary.get("expected_fail_closed_exact_disposition_count") != 6
        or summary.get("checkpoint_case_denominator") != 3
        or summary.get("checkpoint_exact_count") != 3
        or summary.get("all_failure_rows_retained") is not True
        or summary.get("openmm_candidate_case_denominator") != 4
        or summary.get("openmm_candidate_case_passed_count") != 4
        or summary.get("native_openmm_lbfgs_invoked") is not False
        or summary.get("native_openmm_lbfgs_status")
        != "unchanged_rejected_6_of_8"
        or summary.get("frozen_14_case_production_receipt_superseded")
        is not False
        or summary.get("s0_complete") is not False
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor summary accounting is invalid"
        )
    openmm = document.get("openmm_same_coordinate_candidate_receipt")
    require_openmm_reference_constraint_stationarity_receipt(
        openmm,
        verify_current_sources=verify_current_identity,
    )
    if (
        document.get("candidate_observation") is not True
        or document.get("validation_receipt") is not False
        or document.get("scientifically_validated") is not False
        or document.get("claim_safe") is not False
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor observation overstates its evidence claim"
        )
    return document


def write_reference_minimization_stationarity_successor_observation(
    path: Path | str,
    value: Mapping[str, object],
) -> Path:
    """Write one verified observation with secure no-overwrite semantics."""

    verified = require_reference_minimization_stationarity_successor_observation(
        value
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        verified,
        allow_nan=False,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if (
        len(payload.encode("utf-8"))
        > REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_MAX_OBSERVATION_BYTES
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor observation exceeds its bounded file size"
        )
    if destination.is_symlink():
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor observation path must not be a symlink"
        )
    if destination.exists():
        metadata = destination.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ReferenceMinimizationStationaritySuccessorError(
                "successor observation path must be a regular file"
            )
        if (
            metadata.st_size
            > REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_MAX_OBSERVATION_BYTES
        ):
            raise ReferenceMinimizationStationaritySuccessorError(
                "existing successor observation exceeds its bounded file size"
            )
        if destination.read_text(encoding="utf-8") != payload:
            raise ReferenceMinimizationStationaritySuccessorError(
                "refusing to overwrite a different successor observation"
            )
        os.chmod(destination, 0o600)
        return destination
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    created = False
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            created = True
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError as exc:
            raise ReferenceMinimizationStationaritySuccessorError(
                "successor observation path appeared during creation"
            ) from exc
        temporary.unlink()
        directory_fd = os.open(
            destination.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if created and temporary.exists():
            temporary.unlink()
    return destination


def read_reference_minimization_stationarity_successor_observation(
    path: Path | str,
) -> dict[str, object]:
    """Read one private regular-file observation and verify current identity."""

    source = Path(path)
    metadata = source.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor observation must be a regular non-symlink file"
        )
    if metadata.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor observation must not be group/world accessible"
        )
    if (
        metadata.st_size
        > REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_MAX_OBSERVATION_BYTES
    ):
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor observation exceeds its bounded file size"
        )
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationStationaritySuccessorError(
            "successor observation is not readable canonical JSON"
        ) from exc
    return require_reference_minimization_stationarity_successor_observation(
        value
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Build or verify one successor observation from the command line."""

    parser = argparse.ArgumentParser(
        description=(
            "Build or verify the claim-closed 14-case minimization "
            "stationarity successor observation"
        )
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path)
    action.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    if args.output is not None:
        observation = (
            build_reference_minimization_stationarity_successor_observation()
        )
        destination = (
            write_reference_minimization_stationarity_successor_observation(
                args.output,
                observation,
            )
        )
        print(
            json.dumps(
                {
                    "observation_sha256": observation["observation_sha256"],
                    "path": str(destination),
                    "status": "successor_observation_written",
                },
                allow_nan=False,
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 0
    verified = read_reference_minimization_stationarity_successor_observation(
        args.verify
    )
    print(
        json.dumps(
            {
                "observation_sha256": verified["observation_sha256"],
                "path": str(args.verify),
                "status": "successor_observation_verified",
            },
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FROZEN_REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SHA256",
    "REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_OBSERVATION_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_MAX_OBSERVATION_BYTES",
    "ReferenceMinimizationStationaritySuccessorError",
    "build_reference_minimization_stationarity_successor_observation",
    "main",
    "read_reference_minimization_stationarity_successor_observation",
    "reference_minimization_stationarity_successor_configuration_document",
    "require_reference_minimization_stationarity_successor_observation",
    "write_reference_minimization_stationarity_successor_observation",
]
